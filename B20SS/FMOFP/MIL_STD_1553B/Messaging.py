"""
MIL-STD-1553B Messaging System

Handles MIL-STD-1553B message formatting and routing.
"""

import os
import time
import threading
import traceback
import asyncio
import xml.etree.ElementTree as ET
from FMOFP.Utils.common import fetching
from typing import Any, Dict, Optional, List
from FMOFP.Systems.comms.messaging_service import get_comms_service
from FMOFP.core.event_driven_communication import get_event_bus, Event
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_connect.BC_socket import get_bc_sender, get_bc_listener
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct, BC_deconstruct
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.operation_tracker import track_operation

logger = get_logger().logger

class send1553Msg:
    def __init__(self):
        self.bcm = BusControllerModule()
        self.sent_frames = []
        self._lock = threading.Lock()


    #   PRIMARY method to send messages from local system to the bus controller -> RTs
    async def send_message(self, command: str, data: List[str], request_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[List[str]]:
        """Send a MIL-STD-1553B message.

        Args:
            command: Command word (16-bit binary string)
            data: List of data words (16-bit binary strings)
            request_id: Optional request ID for tracking responses
            metadata: Optional metadata dictionary to encode into data words

        Returns:
            Optional[str]: Message ID if sent successfully, None otherwise
        """
        try:
            # Normalize command
            if isinstance(command, list) and len(command) == 1:
                command = command[0]

            # Normalize data
            if not isinstance(data, list):
                data = [data]

            # Log command details
            logger.debug(f"Sending command: {command}")
            logger.debug(f"Sending data: {data}")
            logger.debug(f"Request ID: {request_id}")
            if not metadata:
                raise ValueError("No metadata provided")

            logger.debug(f"Metadata: {metadata}")

            # Send command through bus controller
            sent_frame = await self.bcm._sendCommandComms(command, data, request_id, metadata)

            # Track sent frame
            if sent_frame:
                with self._lock:
                    self.sent_frames.append(sent_frame)
                return sent_frame

            return None

        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            logger.error(traceback.format_exc())
            return None

class BusControllerModule:
    # Sync patterns according to MIL-STD-1553B
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern (same as command)

    def __init__(self):
        # NOTE: self.messaging_service was previously bound to
        # get_comms_service() (the radio/satcom/datalink simulator), which
        # has no publish() method at all - the one call site below
        # (publishing a status word event) would have raised
        # "AttributeError: 'CommsService' object has no attribute 'publish'"
        # the moment it was reached. self.messaging_service isn't used for
        # anything else in this class (no radio/satcom calls), confirming
        # this was meant to be an event bus, not the comms service. Bound to
        # the actual EventBus, matching the publish() pattern used correctly
        # elsewhere in the codebase (e.g. base_radar_data_handler.py).
        self.messaging_service = get_event_bus()
        self.bcc = BC_construct()
        self.bcd = BC_deconstruct()
        self.bcs = get_bc_sender()
        self.bcl = get_bc_listener()
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self._lock = threading.Lock()

    def calculate_parity(self, word: str) -> str:
        """Calculate odd parity bit for a binary word."""
        return '1' if word.count('1') % 2 == 0 else '0'

    def add_sync_and_parity(self, word: str, is_command: bool = True) -> str:
        """Add sync pattern and parity bit to a 16-bit word."""
        sync = self.COMMAND_SYNC if is_command else self.DATA_SYNC
        word_with_sync = sync + word
        parity = self.calculate_parity(word_with_sync)
        result = word_with_sync + parity

        # Validate the result has odd parity
        ones_count = result.count('1')
        if ones_count % 2 != 1:
            logger.error(f"Invalid parity in constructed word: {result}")
            # Fix parity if needed
            result = result[:-1] + ('0' if result[:-1].count('1') % 2 == 1 else '1')
            logger.info(f"Corrected word parity: {result}")

        return result

    async def _sendCommandComms(self, command: str, data: List[str], request_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[List[str]]:
        """
        Send command and data words to RT.

        Args:
            command: Command word (16-bit binary string)
            data: List of data words (16-bit binary strings)
            request_id: Optional request ID for tracking responses
            metadata: Optional metadata dictionary to encode into data words
        """
        for attempt in range(self.max_retries):
            try:
                # Check command format
                command = self.commandCheck(command)

                # Get command components
                RT_address, t_or_r, sub_add_or_mode_code, data_word_count = self.formatCommand(command)
                logger.debug(f"RT address: {RT_address}")
                logger.debug(f"T/R flag: {t_or_r}")
                logger.debug(f"Subaddress/mode code: {sub_add_or_mode_code}")
                logger.debug(f"Data word count: {data_word_count}")

                # Format command frame
                command_frame = self.add_sync_and_parity(command, True)
                logger.debug(f"Command frame: {command_frame}")

                # Encode metadata if provided
                metadata_data_words = []
                if metadata:
                    try:
                        # Import metadata codec
                        from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec

                        # Add debug logging
                        logger.info(f"[MESSAGING] Encoding metadata: {metadata}")

                        # Just ensure command_name is in metadata if it exists
                        if 'command_type' in metadata:
                            logger.info(f"[MESSAGING] Found command_name in metadata: {metadata['command_type']}")
                        else:
                            raise ValueError("No metadata in message")

                        # Check for precipitation indicators
                        if 'command_type' in metadata and 'PRECIP' in str(metadata['command_type']):
                            metadata['precipitation_message'] = True
                            metadata['command_type'] = 'precipitation_data'
                            logger.info(f"[MESSAGING] Added precipitation_message flag to metadata based on command_name")

                        # Encode metadata into data words
                        metadata_data_words = MetadataCodec.encode_metadata(metadata)
                        logger.info(f"[MESSAGING] Encoded metadata into {len(metadata_data_words)} data words: {metadata_data_words}")

                    except Exception as e:
                        logger.error(f"Error encoding metadata: {e}")
                        logger.error(traceback.format_exc())
                        # Continue without metadata if encoding fails

                # Format data frames (metadata + regular data)
                all_data = metadata_data_words + data
                data_frames = []
                for data_word in all_data:
                    # Convert data word to 16-bit binary
                    if isinstance(data_word, int):
                        data_word = format(data_word, '016b')
                    elif isinstance(data_word, str):
                        # Strip existing sync/parity
                        if len(data_word) == 20:
                            data_word = data_word[3:-1]
                        # Ensure 16-bit length
                        if len(data_word) != 16:
                            data_word = format(int(data_word, 2), '016b')

                    # Add sync and parity
                    data_frame = self.add_sync_and_parity(data_word, False)
                    logger.debug(f"Data frame: {data_frame}")
                    data_frames.append(data_frame)

                # Combine frames
                frames = [command_frame] + data_frames
                logger.debug(f"Complete frame list: {frames}")

                # Send frames with request_id and metadata

                message = {
                    'frames': frames,
                    'request_id': request_id,
                    'metadata': metadata,
                    'message_type': metadata.get('message_type') if metadata else None
                }
                logger.info(f"[MESSAGING] Added metadata to message dictionary: {metadata}")

                if self.bcs.BC_send_message(message):
                    # Wait for RT response
                    await asyncio.sleep(0.1)

                    # Check for RT response
                    if self.bcl.data_received:
                        response = self.bcl.data_received.pop(0)
                        try:
                            # Check for status word
                            if isinstance(response, list) and response:
                                first_frame = response[0]
                                if first_frame.startswith('100'):
                                    status_word = self.bcd.deconstruct_status_word(first_frame)
                                    if status_word:
                                        logger.info(f"BC received status word: {status_word}")
                                        # Create complete status word message
                                        status_message = {
                                            "status_word": status_word,
                                            "request_id": request_id,
                                            "timestamp": time.time(),
                                            "command_type": "mode_change",  # Based on data word count
                                            "radar_type": "weather_radar",  # Based on subaddress
                                            "status": "acknowledged",
                                            "additional_info": {
                                                "original_frame": first_frame,
                                                "rt_address": status_word.get('rt_address'),
                                                "dynamic_bus_control": status_word.get('dynamic_bus_control'),
                                                "terminal_flag": status_word.get('terminal_flag')
                                            }
                                        }
                                        # Publish status word message.
                                        # EventBus.publish() is synchronous
                                        # (see event_driven_communication.py)
                                        # and takes an Event, not a
                                        # (topic, data) pair.
                                        self.messaging_service.publish(Event(topic="status_word", data=status_message))
                                        logger.info(f"Published status word message: {status_message}")
                        except Exception as e:
                            logger.error(f"Error processing RT response: {str(e)}")

                    # Publish frames with request_id
                    message_data = {
                        "frames": frames,
                        "timestamp": time.time()
                    }
                    if request_id:
                        message_data["request_id"] = request_id
                    logger.debug(f"[1553B] Frames sent: request_id={request_id}, frame_count={len(frames)}")
                    return frames

                else:
                    logger.warning(f"Failed to send message, attempt {attempt + 1} of {self.max_retries}")

            except Exception as e:
                logger.error(f"Error in _sendCommandComms, attempt {attempt + 1}: {str(e)}")
                logger.error(traceback.format_exc())
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

        return None

    def commandCheck(self, received: Any) -> str:
        """Validate and format command word."""
        try:
            # Extract command from dict
            if isinstance(received, dict):
                received = received.get('command_word', '')
                logger.info(f"Extracted command word: {received}")

            # Check if already valid binary
            if isinstance(received, str) and len(received) == 16 and set(received) <= {'0', '1'}:
                return received

            # Handle hex format
            if isinstance(received, str) and received.startswith('0x'):
                received = received[2:]

            # Convert to binary
            if isinstance(received, str) and all(c in '0123456789abcdefABCDEF' for c in received):
                binary_command = format(int(received, 16), '016b')
                logger.info(f"Converted hex {received} to binary")
            elif isinstance(received, int):
                binary_command = format(received, '016b')
            else:
                raise ValueError(f"Invalid command format: {received}")

            # Validate length
            if len(binary_command) != 16:
                raise ValueError("Command must be 16 bits")

            return binary_command

        except Exception as e:
            logger.error(f"Error in commandCheck: {str(e)}")
            logger.error(f"Received: {received}")
            logger.error(traceback.format_exc())
            raise

    def formatCommand(self, command: str) -> tuple:
        """Format command word components."""
        try:
            RT_address = command[:5]
            t_or_r = command[5]
            sub_add_or_mode_code = command[6:11]
            data_word_count = command[11:]
            return RT_address, t_or_r, sub_add_or_mode_code, data_word_count
        except Exception as e:
            logger.error(f"Error formatting command: {str(e)}")
            raise

class ScheduleMessage:
    # Class-level variables to track message rate loading
    _message_rates_loaded = False
    _message_rates_lock = threading.Lock()
    _shared_message_rates = {}

    def __init__(self):
        from FMOFP.Utils.common.thread_manager import ThreadManager
        self.thread_manager = ThreadManager()
        self.major_frame_time = 1000  # Default value, can be changed later
        self.minor_frame_times = [100, 200, 300, 400]  # Default values, can be changed later
        self.tasks = []
        self.bcm = BusControllerModule()
        self.running = False
        self.message_rates = {}

        # Load message rates only once
        self.load_message_rates()

        # Only add the periodic loader thread if we're the first instance
        if not ScheduleMessage._message_rates_loaded:
            self.thread_manager.add_thread("MessageRateLoader", self.periodic_load_message_rates)

        self.scheduler = Schedule(self.major_frame_time, self.minor_frame_times)

    def load_message_rates(self):
        def _load_message_rates_impl():
            # Load message rates from file
            fmofp_path = fetching.fetch_fmofp_path()
            config_file = os.path.join(fmofp_path, 'messageRateConfig.xml')
            try:
                logger.info(f"Attempting to load message rates from: {config_file}")
                tree = ET.parse(config_file)
                root = tree.getroot()
                new_rates = {}
                try:
                    for msg_type in root.findall('*'):
                        msg_name = msg_type.tag
                        rate_element = msg_type.find('rate_hz')
                        if rate_element is not None and rate_element.text is not None:
                            rate_hz = float(rate_element.text)
                            new_rates[msg_name] = rate_hz

                    if new_rates:
                        self.message_rates = new_rates
                        # Store in class-level shared dictionary
                        ScheduleMessage._shared_message_rates = new_rates.copy()
                        # Mark as loaded
                        ScheduleMessage._message_rates_loaded = True
                        logger.info(f"Message rates loaded successfully from {config_file}")
                        logger.info(f"Loaded message rates: {self.message_rates}")
                        return new_rates
                    else:
                        raise ValueError("No valid message rates found in the configuration file")
                except (FileNotFoundError, ValueError) as e:
                    logger.error(f"Error loading message rates: {str(e)}")
                    if not self.message_rates:
                        return self.set_default_rates()
            except ET.ParseError as e:
                logger.error(f"XML parsing error in {config_file}: {str(e)}")
                logger.error("Please check the formatting of the 'messageRateConfig.xml' file.")
                if not self.message_rates:
                    return self.set_default_rates()
            except Exception as e:
                logger.error(f"Unexpected error loading message rates: {str(e)}")
                logger.error(traceback.format_exc())
                if not self.message_rates:
                    return self.set_default_rates()

        # Use the class lock to prevent race conditions
        with ScheduleMessage._message_rates_lock:
            # If message rates are already loaded, use the shared rates
            if ScheduleMessage._message_rates_loaded:
                logger.info("Message rates already loaded, using cached values")
                self.message_rates = ScheduleMessage._shared_message_rates.copy()
                return self.message_rates

        # Track this operation to ensure it only happens once
        result = track_operation('message_rates_load', 'messageRateConfig.xml', _load_message_rates_impl)

        # If operation was already completed, use the shared rates
        if result is None and ScheduleMessage._message_rates_loaded:
            self.message_rates = ScheduleMessage._shared_message_rates.copy()

        return self.message_rates

    def set_default_rates(self):
        default_rates = {
            'status_msg': 1,
            'alert_msg': 5,
            'data_msg': 10,
            'command_msg': 2,
            'log_msg': 0.5
        }

        # Set instance and class-level rates
        self.message_rates = default_rates.copy()

        # Use the class lock to prevent race conditions
        with ScheduleMessage._message_rates_lock:
            # Only update shared rates if not already set
            if not ScheduleMessage._message_rates_loaded:
                ScheduleMessage._shared_message_rates = default_rates.copy()
                ScheduleMessage._message_rates_loaded = True

        logger.info("Using default message rates")
        logger.info(f"Default message rates: {self.message_rates}")
        return default_rates

    def periodic_load_message_rates(self):
        while self.running:
            # Wait up to 5 minutes between reloads, but re-check self.running
            # every second instead of blocking in a single time.sleep(300).
            # A flat 300s sleep can't be interrupted by clearing self.running,
            # so ScheduleMessage.stop() -- which sets self.running = False and
            # then does a blocking, timeout-less thread_manager.stop_thread()
            # join on this exact thread -- could hang graceful shutdown for
            # up to 5 minutes (confirmed live: this was one of several
            # shutdown-hang causes found and fixed together; see PLANNING.md).
            for _ in range(300):
                if not self.running:
                    return
                time.sleep(1)

            # Reset the loaded flag to force a reload
            with ScheduleMessage._message_rates_lock:
                ScheduleMessage._message_rates_loaded = False

            # Reload the rates
            self.load_message_rates()

    def start(self):
        # Start the Scheduler
        try:
            logger.info("Starting scheduler...")
            self.running = True
            self.thread_manager.start_all_threads()
            self.scheduler.start()
            logger.info("Scheduler started.")
        except Exception as e:
            logger.error(f"Failed to start scheduler with error: {e}")
            logger.debug(traceback.format_exc())

    def stop(self):
        logger.info("Stopping ScheduleMessage...")
        self.running = False
        self.thread_manager.stop_all_threads()
        if hasattr(self, 'scheduler'):
            self.scheduler.stop()
        logger.info("ScheduleMessage stopped.")

class Schedule:
    def __init__(self, major_frame_time, minor_frame_times):
        from FMOFP.Utils.common.thread_manager import ThreadManager
        self.major_frame_time = major_frame_time
        self.minor_frame_times = minor_frame_times
        self.minor_frame_tasks = [None] * len(minor_frame_times)
        self.thread_manager = ThreadManager()
        self.running = False

    def set_minor_frame_task(self, index, task):
        self.minor_frame_tasks[index] = task

    def start(self):
        self.running = True
        self.thread_manager.add_thread("Major Frame", self.run_major_frame)
        self.thread_manager.start_all_threads()

    def run_major_frame(self):
        while self.running:
            start_time = time.time()
            for i, task in enumerate(self.minor_frame_tasks):
                if task and self.running:
                    try:
                        task()
                    except Exception as e:
                        logger.error(f"Error in minor frame task {i}: {str(e)}")
            elapsed_time = time.time() - start_time
            remaining_time = self.major_frame_time - elapsed_time
            if remaining_time > 0 and self.running:
                # Sleep in <=1s increments, re-checking self.running each
                # time, instead of one long time.sleep(remaining_time). A
                # single blocking sleep can't be interrupted by clearing
                # self.running, so with the default major_frame_time=1000
                # this thread could be asleep for up to ~1000s when stop()
                # is called -- and thread_manager.stop_thread("Major Frame")
                # does a blocking, timeout-less thread.join(), so graceful
                # shutdown would hang for up to that long (confirmed live;
                # see PLANNING.md). This preserves the exact same total
                # sleep duration, just makes it interruptible.
                remaining = remaining_time
                while remaining > 0 and self.running:
                    step = min(1.0, remaining)
                    time.sleep(step)
                    remaining -= step

    def stop(self):
        logger.info("Stopping Schedule...")
        self.running = False
        self.thread_manager.stop_all_threads()
        logger.info("Schedule stopped.")

# Create instances of the messaging classes
bus_controller_module = BusControllerModule()
send_1553_msg = send1553Msg()
schedule_message = ScheduleMessage()

def get_bus_controller_module():
    """Get global BusControllerModule instance."""
    return bus_controller_module

def get_send_1553_msg():
    """Get global send1553Msg instance."""
    return send_1553_msg

def get_schedule_message():
    return schedule_message
