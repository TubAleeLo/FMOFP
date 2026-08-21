import threading
import time
import traceback
from typing import Dict, Any, Optional, List, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.core.event_driven_communication import get_event_bus
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_sender, get_rt_listener
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.message_queue_manager import get_message_queue_manager
from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
from FMOFP.Systems.flightManagementSys.fmsControl import get_fms_control

logger = get_logger()

class FMSMessenger:
    """
    Messenger for the Flight Management System

    Handles communication between the FMS and other systems using the MIL-STD-1553B protocol.
    """
    def __init__(self):
        self.fms = None
        self.fms_control = None
        self.event_bus = get_event_bus()
        self.address_book = {}
        self.lock = threading.Lock()
        self.running = False

        # Get RT components like radarMessenger and displayMessenger
        from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import Remote_Terminal
        rt_instance = Remote_Terminal()
        self.rt_listener = rt_instance.rt_listener
        self.rt_sender = get_rt_sender()
        logger.info(f"FMS Messenger initialized with RT_Listener instance: {id(self.rt_listener)}")

        self.rt_address = None  # Will be loaded from config
        # Subaddresses correspond to subsystems within the FMS
        self.subaddresses = {
            "fms_control": 0,     # Main FMS control subsystem
            "flight_data": 1,     # Flight data subsystem
            "navigation_data": 2, # Navigation subsystem
            "command_control": 3, # Command and control subsystem
            "status": 4           # Status reporting subsystem
        }

        # Load RT addresses from config
        self.load_address_book()

    def load_address_book(self):
        """Load RT addresses from configuration"""
        try:
            from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_address_config
            rt_config = get_rt_address_config()
            # Get the Flight Management System address from the RT config
            self.rt_address = rt_config.get_rt_address('flightManagementSystem')

            # Update address book with addresses from config
            self.address_book = {
                "flightManagementSystem": self.rt_address,
                "flight_control_computer": rt_config.get_rt_address('flight_control_system'),
                "display_system": rt_config.get_rt_address('display_system'),
                "navigation_system": rt_config.get_rt_address('navigation_system'),
            }
            logger.info(f"FMS Messenger address book loaded, using RT address {self.rt_address}")
        except Exception as e:
            logger.error(f"Error loading address book: {e}")
            # Fallback to default addresses
            self.rt_address = 17  # FMS default RT address from address book
            self.address_book = {
                "flightManagementSystem": self.rt_address,
                "flight_control_computer": 5,  # Flight Control System address
                "display_system": 11,
                "navigation_system": 7,  # Navigation System address
            }
            logger.warning(f"Using fallback address book with RT address {self.rt_address}")

    def set_fms(self, fms):
        """Set the FMS reference"""
        self.fms = fms
        logger.info("FMS reference set in messenger")

    def set_fms_control(self, fms_control):
        """Set the FMS Control reference"""
        self.fms_control = fms_control
        logger.info("FMS Control reference set in messenger")

    def send_fms_data(self, fms_data: Dict[str, Any]):
        """
        Send FMS data to other systems

        Args:
            fms_data (dict): Flight data to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Prepare message for sending via MIL-STD-1553B
            message = MIL_STD_1553B_Message(
                self.rt_address,
                self.subaddresses["flight_data"],
                fms_data
            )

            # Send message to all subscribed systems
            return self._route_to_systems(message)
        except Exception as e:
            logger.error(f"Error sending FMS data: {e}")
            return False

    def send_navigation_data(self, nav_data: Dict[str, Any]):
        """
        Send navigation data to other systems

        Args:
            nav_data (dict): Navigation data to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Extract just navigation-related data
            message = MIL_STD_1553B_Message(
                self.rt_address,
                self.subaddresses["navigation_data"],
                nav_data
            )

            # Send to navigation system and displays
            return self._route_to_systems(message, ["display_system", "navigation_system"])
        except Exception as e:
            logger.error(f"Error sending navigation data: {e}")
            return False

    def send_status_update(self, status_data: Dict[str, Any]):
        """
        Send FMS status update to other systems

        Args:
            status_data (dict): Status data to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            message = MIL_STD_1553B_Message(
                self.rt_address,
                self.subaddresses["status"],
                status_data
            )

            # Send status to all systems
            return self._route_to_systems(message)
        except Exception as e:
            logger.error(f"Error sending status update: {e}")
            return False

    def _send_as_block_transfer(self, data: List[int],
                                rt_address: int, sub_address: int,
                                message_type: str = 'fms_data',
                                request_id: str = None) -> bool:
        """
        Chunk *data* (a list of 16-bit integers) into ≤32-word 1553B blocks and
        send each block through RT_send_message, which already implements the
        full init / data / complete block-transfer protocol in _send_large_message.

        This replaces the previous silent truncation of payloads that exceeded
        MIL-STD-1553B's 32-word per-message limit.

        Args:
            data:         Complete word list (may exceed 32 words).
            rt_address:   Destination RT address.
            sub_address:  Destination sub-address.
            message_type: Message-type tag for routing metadata.
            request_id:   Transfer UUID (generated if not supplied).

        Returns:
            True if every block was accepted by RT_send_message, else False.
        """
        import uuid as _uuid
        if not request_id:
            request_id = str(_uuid.uuid4())

        MAX_WORDS = 32  # MIL-STD-1553B hard limit per message

        # Build one large data message — RT_send_message's _send_large_message
        # will split it into compliant blocks automatically when len > 33 frames.
        message_dict = {
            'data':       data,
            'request_id': request_id,
            'rt_address': rt_address,
            'sub_address': sub_address,
            'metadata': {
                'message_type': message_type,
                'command_type': 'fms_block_data',
                'is_block_transfer': True,
                'total_words': len(data),
            },
        }

        num_blocks = (len(data) + MAX_WORDS - 1) // MAX_WORDS
        logger.info(
            f"[FMS_BLOCK] Sending {len(data)} words as {num_blocks} block(s) "
            f"for request_id={request_id}"
        )
        result = self.rt_sender.RT_send_message(message_dict)
        if result:
            logger.info(f"[FMS_BLOCK] Block transfer complete for request_id={request_id}")
        else:
            logger.error(f"[FMS_BLOCK] Block transfer failed for request_id={request_id}")
        return result

    def _serialize_message_data(self, data: Any) -> Union[str, List[int]]:
        """
        Serialize message data to a format compatible with MIL-STD-1553B.

        For payloads that exceed the 32-word per-message limit, the caller
        should use _send_as_block_transfer() instead of relying on this method,
        which returns at most 32 words.  _route_to_systems() handles this
        automatically: it calls _send_as_block_transfer() whenever the
        serialised length would exceed the limit.

        Args:
            data: The data to serialize

        Returns:
            Union[str, List[int]]: Binary string or list of integers
              (capped at 32 words — use _send_as_block_transfer for larger payloads)
        """
        try:
            # MIL-STD-1553B limits: 1 command word + max 32 data words
            MAX_DATA_WORDS = 32

            # If already a string, convert to binary format
            if isinstance(data, str):
                # Ensure the string is a valid binary string
                if all(c in '01' for c in data):
                    # Check length to ensure it fits within MIL-STD-1553B limits
                    if len(data) <= 16 * (MAX_DATA_WORDS + 1):  # +1 for command word
                        return data
                    else:
                        # Oversized binary strings are handled via block transfer in
                        # _route_to_systems; return the first frame only as a fallback
                        # so the caller still gets a valid (non-empty) return value.
                        logger.info(
                            f"[FMS_SERIAL] Binary string {len(data)} bits exceeds limit; "
                            "block transfer will handle full payload via _route_to_systems"
                        )
                        return data[:16 * (MAX_DATA_WORDS + 1)]
                else:
                    logger.warning("Invalid binary string, contains non-binary characters")
                    return "0" * 16  # Return a default binary string

            # If already a list of integers, return up to MAX_DATA_WORDS.
            # Oversized lists are sent in full via _send_as_block_transfer in
            # _route_to_systems — no data is lost.
            if isinstance(data, list) and all(isinstance(i, int) for i in data):
                if len(data) <= MAX_DATA_WORDS:
                    return data
                else:
                    logger.info(
                        f"[FMS_SERIAL] Word list {len(data)} words exceeds 32-word limit; "
                        "block transfer will handle full payload via _route_to_systems"
                    )
                    return data[:MAX_DATA_WORDS]

            # Convert dictionary to list of integers
            if isinstance(data, dict):
                # Convert each key-value pair to an integer
                result = []

                # Simple header word to identify data type (0x1000 = FMS data)
                result.append(0x1000)

                # Process each key-value pair, but limit to MAX_DATA_WORDS - 1 (to account for header)
                remaining_words = MAX_DATA_WORDS - 1

                # Process high-priority data first
                priority_keys = ['attitude', 'velocity', 'navigation', 'tactical', 'status']
                for key in priority_keys:
                    if key in data and remaining_words > 0:
                        if isinstance(data[key], dict):
                            # Process each subkey
                            for subkey, subvalue in data[key].items():
                                if remaining_words <= 0:
                                    break
                                # Only include numeric values
                                if isinstance(subvalue, (int, float)):
                                    # Scale and convert to int (preserve 2 decimal places)
                                    int_value = int(subvalue * 100) & 0xFFFF
                                    result.append(int_value)
                                    remaining_words -= 1

                # Process any remaining simple key-value pairs
                for key, value in data.items():
                    if key not in priority_keys and remaining_words > 0:
                        if isinstance(value, (int, float)):
                            # Direct conversion for simple types
                            int_value = int(value) & 0xFFFF
                            result.append(int_value)
                            remaining_words -= 1

                logger.info(f"Serialized data to {len(result)} data words")
                return result

            # Default fallback for other types - convert to a simple integer
            return [0x0000]  # Default data word

        except Exception as e:
            logger.error(f"Error serializing message data: {e}")
            logger.error(traceback.format_exc())
            return [0x0000]  # Default on error

    def _route_to_systems(self, message: MIL_STD_1553B_Message, target_systems=None):
        """
        Route a message to specific systems or all systems

        Args:
            message (MIL_STD_1553B_Message): Message to route
            target_systems (list): List of system names to send to (None = all)

        Returns:
            bool: True if message routed successfully, False otherwise
        """
        try:
            # If no target systems specified, send to all default targets
            if target_systems is None:
                # Default targets: display system and flight control computer
                target_systems = ["display_system", "flight_control_computer"]
                logger.info(f"FMS Messenger: Using default targets: {target_systems}")

            success = True
            for system in target_systems:
                if system in self.address_book:
                    # Create a copy of the message with the target RT address
                    target_rt_address = self.address_book[system]

                    # ── Block-transfer path for large payloads ────────────────
                    # Check raw data size BEFORE serialising so nothing is lost.
                    raw_data = message.data if hasattr(message, 'data') else None
                    needs_block_transfer = (
                        isinstance(raw_data, list)
                        and all(isinstance(i, int) for i in raw_data)
                        and len(raw_data) > 32
                    )
                    if not needs_block_transfer and isinstance(raw_data, str):
                        needs_block_transfer = (
                            all(c in '01' for c in raw_data)
                            and len(raw_data) > 16 * 33
                        )

                    if needs_block_transfer:
                        # Convert binary string to word list if needed
                        if isinstance(raw_data, str):
                            word_list = [
                                int(raw_data[i:i+16], 2)
                                for i in range(0, len(raw_data) - 15, 16)
                            ]
                        else:
                            word_list = raw_data

                        msg_type = getattr(message, 'message_type', 'fms_data') or 'fms_data'
                        logger.info(
                            f"FMS Messenger: Payload {len(word_list)} words > 32, "
                            f"routing {system} (RT {target_rt_address}) via block transfer"
                        )
                        if self._send_as_block_transfer(
                            word_list, target_rt_address,
                            message.sub_address, msg_type
                        ):
                            logger.info(f"FMS Messenger: Block transfer to {system} succeeded")
                        else:
                            success = False
                            logger.error(f"FMS Messenger: Block transfer to {system} failed")
                        continue   # next system in loop
                    # ─────────────────────────────────────────────────────────

                    # Standard single-message path (≤ 32 words)
                    serialized_data = self._serialize_message_data(message.data)

                    # Create message with target address and properly formatted data
                    target_message = MIL_STD_1553B_Message(
                        rt_address=target_rt_address,
                        sub_address=message.sub_address,
                        data=serialized_data
                    )

                    # Add any additional attributes from the original message
                    if hasattr(message, 'message_type'):
                        target_message.message_type = message.message_type
                    if hasattr(message, 'command_type'):
                        target_message.command_type = message.command_type

                    # Send via RT_sender
                    if self.rt_sender.RT_send_message(target_message):
                        logger.info(f"FMS Messenger: Successfully sent message to {system} (RT {target_rt_address})")
                    else:
                        success = False
                        logger.warning(f"FMS Messenger: Failed to send message to {system} (RT {target_rt_address})")
                else:
                    logger.warning(f"FMS Messenger: Unknown system in routing: {system}")
                    success = False

            return success
        except Exception as e:
            logger.error(f"FMS Messenger: Error routing message: {e}")
            logger.error(traceback.format_exc())
            return False

    def receive_message(self, message):
        """
        Receive an incoming message and forward it to the appropriate handler.
        This function only handles the reception, logging, and routing of messages.

        Args:
            message: The received message

        Returns:
            bool: True if message was successfully received and forwarded
        """
        try:
            # Handle tuple format from MessageQueueManager
            if isinstance(message, tuple) and len(message) == 2:
                system, message = message
                logger.info(f"[FMS_MSGR] Received message from '{system}' queue: {type(message).__name__}")

            # Log the received message
            logger.info(f"[FMS_MSGR] Processing incoming message: {type(message).__name__}")

            # Extract message identifiers for logging
            request_id = self._extract_request_id(message)
            message_type = self._extract_message_type(message)
            command_type = self._extract_command_type(message)

            # Log basic message details
            logger.info(f"[FMS_MSGR] Message details - request_id: {request_id}, type: {message_type}, command: {command_type}")

            # Forward the message to the FMS system
            if self.fms:
                try:
                    logger.info(f"[FMS_MSGR] Forwarding message to FMS system")
                    # Just forward the message to the FMS - processing happens there
                    result = self.fms.receive_message(message)
                    logger.info(f"[FMS_MSGR] FMS processed message: {result}")
                    return True
                except Exception as e:
                    logger.error(f"[FMS_MSGR] Error in FMS message processing: {e}")
                    logger.error(traceback.format_exc())
                    # If FMS processing fails, try FMS Control as fallback

            # If no FMS or FMS processing failed, try FMS Control
            if self.fms_control:
                try:
                    logger.info(f"[FMS_MSGR] Forwarding message to FMS Control system")
                    # Convert the message to something FMSControl can handle
                    if command_type:
                        # Extract parameters based on message format
                        parameters = self._extract_parameters(message)

                        # Process command directly through FMS Control
                        result = self.fms_control.process_command(command_type, parameters)
                        logger.info(f"[FMS_MSGR] FMS Control processed command: {result}")
                        return True
                    else:
                        logger.warning(f"[FMS_MSGR] No command type found in message, can't process via FMS Control")
                        return False
                except Exception as e:
                    logger.error(f"[FMS_MSGR] Error in FMS Control message processing: {e}")
                    logger.error(traceback.format_exc())
                    return False

            # If neither FMS nor FMS Control could process the message
            logger.warning(f"[FMS_MSGR] No handler available for message")
            return False

        except Exception as e:
            logger.error(f"[FMS_MSGR] Error processing message: {e}")
            logger.error(traceback.format_exc())
            return False

    def _extract_request_id(self, message):
        """Extract request_id from a message regardless of format"""
        try:
            # Try various locations where request_id might be found
            if isinstance(message, dict) and 'request_id' in message:
                return message['request_id']
            elif hasattr(message, 'request_id'):
                return message.request_id
            elif hasattr(message, 'data') and isinstance(message.data, dict) and 'request_id' in message.data:
                return message.data['request_id']
            elif isinstance(message, dict) and 'metadata' in message and isinstance(message['metadata'], dict) and 'request_id' in message['metadata']:
                return message['metadata']['request_id']
            return None
        except Exception:
            return None

    def _extract_message_type(self, message):
        """Extract message_type from a message regardless of format"""
        try:
            # Try various locations where message_type might be found
            if isinstance(message, dict) and 'message_type' in message:
                return message['message_type']
            elif hasattr(message, 'message_type'):
                return message.message_type
            return None
        except Exception:
            return None

    def _extract_command_type(self, message):
        """Extract command_type from a message regardless of format"""
        try:
            # Try various locations where command_type might be found
            if isinstance(message, dict) and 'command_type' in message:
                return message['command_type']
            elif hasattr(message, 'command_type'):
                return message.command_type
            elif hasattr(message, 'data') and isinstance(message.data, dict) and 'command_type' in message.data:
                return message.data['command_type']
            return None
        except Exception:
            return None

    def _extract_parameters(self, message):
        """Extract parameters from a message regardless of format"""
        try:
            # Initialize with empty parameters
            parameters = {}

            # Extract from dictionary format
            if isinstance(message, dict):
                # Add the original message for reference
                parameters['original_message'] = message

                # Extract data if available
                if 'data' in message:
                    parameters['data'] = message['data']

                # Extract parameters from data or metadata
                if isinstance(message.get('data'), dict) and 'parameters' in message['data']:
                    parameters.update(message['data']['parameters'])
                elif 'parameters' in message:
                    parameters.update(message['parameters'])

            # Extract from object format
            elif hasattr(message, 'data'):
                # Add the original message for reference
                parameters['original_message'] = message

                # Extract parameters from data attribute
                if isinstance(message.data, dict):
                    parameters['data'] = message.data
                    if 'parameters' in message.data:
                        parameters.update(message.data['parameters'])
                else:
                    parameters['data'] = message.data

            return parameters
        except Exception as e:
            logger.error(f"[FMS_MSGR] Error extracting parameters: {e}")
            return {'error': str(e), 'original_message': message}

    def _deserialize_data_words(self, data_words):
        """
        Deserialize data words from MIL-STD-1553B message to parameters

        Args:
            data_words: List of 16-bit data words

        Returns:
            dict: Deserialized parameters
        """
        try:
            # Check if data_words is a list of integers
            if not isinstance(data_words, list) or not all(isinstance(word, int) for word in data_words):
                logger.warning(f"[FMS_MSGR] Invalid data words format: {data_words}")
                return {}

            # First word is header (0x1000 for FMS data)
            if len(data_words) == 0 or data_words[0] != 0x1000:
                logger.warning(f"[FMS_MSGR] Invalid FMS data header: {data_words[0] if data_words else 'empty'}")
                return {}

            # Skip header and process remaining words
            data_words = data_words[1:]

            # Create parameters dictionary
            parameters = {
                'attitude': {},
                'velocity': {},
                'navigation': {},
                'tactical': {}
            }

            # Process data words based on expected format
            # This should match the format used in send_fms_data
            if len(data_words) >= 3:
                # Attitude data (roll, pitch, yaw)
                parameters['attitude']['roll'] = data_words[0] / 100.0
                parameters['attitude']['pitch'] = data_words[1] / 100.0
                parameters['attitude']['yaw'] = data_words[2] / 100.0

            if len(data_words) >= 5:
                # Velocity data (airspeed, vertical speed)
                parameters['velocity']['airspeed'] = data_words[3]
                parameters['velocity']['vertical_speed'] = data_words[4]

            if len(data_words) >= 7:
                # Navigation data (altitude, heading)
                parameters['navigation']['altitude'] = data_words[5]
                parameters['navigation']['heading'] = data_words[6] / 10.0

            if len(data_words) >= 10:
                # Tactical data (g-force, aoa, energy state)
                parameters['tactical']['g_force'] = data_words[7] / 100.0
                parameters['tactical']['aoa'] = data_words[8] / 100.0
                parameters['tactical']['energy_state'] = data_words[9]

            if len(data_words) >= 11:
                # Mode
                mode_int = data_words[10]
                mode_map = {
                    0: "NORMAL",
                    1: "COMBAT",
                    2: "STEALTH",
                    3: "TRAINING",
                    4: "EMERGENCY"
                }
                parameters['tactical']['mode'] = mode_map.get(mode_int, "NORMAL")

            return parameters
        except Exception as e:
            logger.error(f"[FMS_MSGR] Error deserializing data words: {e}")
            logger.error(traceback.format_exc())
            return {}

    def publish_to_event_bus(self, topic, data):
        """
        Publish data to the event bus

        Args:
            topic (str): Event topic
            data (dict): Event data

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            if self.event_bus:
                self.event_bus.publish(topic, data)
                return True
            else:
                logger.warning("Event bus not available for publishing")
                return False
        except Exception as e:
            logger.error(f"Error publishing to event bus: {e}")
            return False

    def start(self):
        """Start the FMS messenger"""
        if not self.running:
            try:
                # Initialize and start the Message Queue Manager
                queue_manager = get_message_queue_manager()
                if not queue_manager:
                    raise RuntimeError("Failed to get MessageQueueManager instance")

                # Ensure the FMS queue is set up in the message queue manager
                if not hasattr(queue_manager, 'system_queues') or 'fms' not in queue_manager.system_queues:
                    logger.info("[FMS_MSGR] Setting up FMS queue in message queue manager")
                    queue_manager.add_system_queue('fms')

                # Start the queue manager if it's not already running
                if not hasattr(queue_manager, 'running') or not queue_manager.running:
                    logger.info("[FMS_MSGR] Starting MessageQueueManager")
                    queue_manager.start()

                    # Wait for queue manager to start (up to 2 seconds)
                    start_time = time.time()
                    while (not hasattr(queue_manager, 'running') or not queue_manager.running) and (time.time() - start_time < 2.0):
                        time.sleep(0.1)

                    if not hasattr(queue_manager, 'running') or not queue_manager.running:
                        logger.error("[FMS_MSGR] MessageQueueManager failed to start within timeout")
                        raise RuntimeError("MessageQueueManager failed to start")

                    logger.info("[FMS_MSGR] MessageQueueManager started successfully")
                else:
                    logger.info("[FMS_MSGR] MessageQueueManager already running")

                # Start message processing thread
                thread_name = "FMSMessenger"
                from Utils.common.thread_manager import thread_manager

                # Define the message processing function
                def process_messages():
                    # Track message counts for monitoring
                    message_count = 0
                    processed_count = 0
                    thread_id = threading.get_ident()

                    logger.info(f"[FMS_MSGR] Starting message processing thread (ID: {thread_id})")

                    # Log which queues we're monitoring
                    logger.info(f"[FMS_MSGR] Monitoring queues: 'fms' and 'flightmanagementsystem'")

                    # Log periodic status updates
                    last_status_log = time.time()
                    status_interval = 10.0  # Log status every 10 seconds

                    while self.running:
                        try:
                            current_time = time.time()
                            should_log = current_time - last_status_log >= status_interval

                            # Log periodic status
                            if should_log:
                                logger.info(f"[FMS_MSGR] FMS Messenger thread still running, waiting for messages...")
                                logger.info(f"[FMS_MSGR] Messages processed: {message_count}, Successfully processed: {processed_count}")

                                # Log queue sizes for monitoring
                                if queue_manager and hasattr(queue_manager, 'get_queue_size'):
                                    fms_queue_size = queue_manager.get_queue_size('fms')
                                    flightmanagementsystem_queue_size = queue_manager.get_queue_size('flightmanagementsystem')
                                    logger.info(f"[FMS_MSGR] Queue sizes - fms: {fms_queue_size}, flightmanagementsystem: {flightmanagementsystem_queue_size}")

                                last_status_log = current_time

                            # Try 'fms' queue first
                            message = queue_manager.get_message('fms')
                            if message:
                                message_count += 1
                                logger.info(f"[FMS_MSGR] Processing message from 'fms' queue: {type(message).__name__}")
                                if self.receive_message(message):
                                    processed_count += 1
                            else:
                                # If no message in 'fms' queue, try 'flightmanagementsystem' queue
                                message = queue_manager.get_message('flightmanagementsystem')
                                if message:
                                    message_count += 1
                                    logger.info(f"[FMS_MSGR] Processing message from 'flightmanagementsystem' queue: {type(message).__name__}")
                                    if self.receive_message(message):
                                        processed_count += 1
                                elif should_log:
                                    logger.info("[FMS_MSGR] No messages found in queues")

                            # Prevent tight loop
                            time.sleep(0.01)
                        except Exception as e:
                            logger.error(f"[FMS_MSGR] Error processing message: {e}")
                            logger.error(traceback.format_exc())
                            time.sleep(0.1)  # Sleep longer on error

                # Add and start the thread
                thread_manager.add_thread(name=thread_name, target=process_messages)
                thread_manager.start_thread(thread_name)

                self.running = True
                logger.info("[FMS_MSGR] FMS Messenger started")
                return True
            except Exception as e:
                logger.error(f"[FMS_MSGR] Error starting FMS Messenger: {e}")
                logger.error(traceback.format_exc())
                return False
        else:
            logger.warning("[FMS_MSGR] FMS Messenger already running")
            return False

    def stop(self):
        """Stop the FMS messenger"""
        if self.running:
            self.running = False
            logger.info("FMS Messenger stopped")
            return True
        else:
            logger.warning("FMS Messenger already stopped")
            return False

    def is_healthy(self):
        """Check messenger health"""
        # Simple check - in a real implementation, would check connections
        return self.running and (self.fms is not None or self.fms_control is not None)

# Singleton pattern
_fms_messenger = None

def get_fms_messenger():
    """Get singleton instance of FMS Messenger"""
    global _fms_messenger
    if _fms_messenger is None:
        _fms_messenger = FMSMessenger()
    return _fms_messenger
