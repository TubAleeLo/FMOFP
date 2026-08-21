"""
RadarMessenger - Direct Message Handler

Handles radar messages by directly routing commands to the appropriate radar system.
Implements consistent addressing using the address_utils module to ensure MIL-STD-1553B protocol compliance.
"""

import time
import traceback
import threading
import asyncio
from typing import Optional, Tuple
from xml.etree import ElementTree as ET
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_listener
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.message_queue_manager import get_message_queue_manager
from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
    get_rt_address, 
    get_subaddress, 
    get_rt_subaddress_pair_for_radar,
    is_radar_subsystem,
    get_system_id_for_addressing
)
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST, WEATHER_RADAR_MODE_CHANGE_RESPONSE, WEATHER_RADAR_STATUS_REQUEST, WEATHER_RADAR_STATUS_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST, WEATHER_RADAR_VIL_RESPONSE, WEATHER_RADAR_PRECIPITATION_REQUEST,  WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_ECHO_TOP_REQUEST, WEATHER_RADAR_ECHO_TOP_RESPONSE, WEATHER_RADAR_STORM_CELL_REQUEST, WEATHER_RADAR_STORM_CELL_RESPONSE,
    TFR_RADAR_MODE_CHANGE_REQUEST, TFR_RADAR_MODE_CHANGE_RESPONSE, TFR_RADAR_STATUS_REQUEST,  TFR_RADAR_STATUS_RESPONSE,
    TFR_RADAR_ELEVATION_DATA_REQUEST, TFR_RADAR_ELEVATION_DATA_RESPONSE,
    SAR_RADAR_MODE_CHANGE_REQUEST, SAR_RADAR_MODE_CHANGE_RESPONSE, SAR_RADAR_STATUS_REQUEST, SAR_RADAR_STATUS_RESPONSE,
    TARGETING_RADAR_MODE_CHANGE_REQUEST, TARGETING_RADAR_MODE_CHANGE_RESPONSE, TARGETING_RADAR_STATUS_REQUEST, TARGETING_RADAR_STATUS_RESPONSE,
    AEWC_RADAR_MODE_CHANGE_REQUEST,  AEWC_RADAR_MODE_CHANGE_RESPONSE, AEWC_RADAR_STATUS_REQUEST, AEWC_RADAR_STATUS_RESPONSE,
    
    # Command Types
    WEATHER_RADAR_COMMAND, WEATHER_RADAR_DATA,
    TFR_RADAR_COMMAND, TFR_RADAR_DATA,
    SAR_RADAR_COMMAND, SAR_RADAR_DATA,
    TARGETING_RADAR_COMMAND, TARGETING_RADAR_DATA,
    AEWC_RADAR_COMMAND, AEWC_RADAR_DATA,
    
    # Helper functions
    get_message_type,
    is_message_type,
    is_vil_message,
    is_precipitation_message,
    is_mode_change_message
)
# Import from display-local radar enums
from FMOFP.Interfaces.userInterface.displays.radar.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode
)
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Mapping of radar types to their mode enums
RADAR_MODE_MAP = {
    'weather_radar': weather_radarMode,
    'tfr_radar': tfr_radarMode,
    'sar_radar': sar_radarMode,
    'targeting_radar': targeting_radarMode,
    'aewc_radar': aewc_radarMode
}

class RadarMessenger:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RadarMessenger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Get the RT_Listener instance from Remote_Terminal
            from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import Remote_Terminal
            rt_instance = Remote_Terminal()
            self.rt_listener = rt_instance.rt_listener
            logger.info(f"[RADAR_MSGR] Initialized with RT_Listener instance from Remote_Terminal: {id(self.rt_listener)}")
            
            self.radar_control = None  # Will be set by RadarControl
            self.address_book = self.load_address_book()
            self.running = False
            self._lock = threading.Lock()
            self._thread_started = threading.Event()  # Event to track thread start
            self._initialized = True

    def set_radar_control(self, radar_control):
        """Set radar control for direct message handling."""
        with self._lock:
            self.radar_control = radar_control
            logger.info("[RADAR_MSGR] Radar control system connected")

    def load_address_book(self):
        try:
            address_book_tree = ET.parse('FMOFP/local_messaging/messageConfigurations/address_book.xml')
            address_book_root = address_book_tree.getroot()
            address_book = {}
            for system in address_book_root.findall('system'):
                system_id = system.get('id')
                system_name = system.find('name').text
                address_book[system_id] = {
                    'name': system_name,
                    'address': system.find('address').text,
                    'subaddresses': {}
                }
            
            # Load subaddresses
            for subaddr in address_book_root.findall('subaddress'):
                subaddr_id = subaddr.get('id')
                subaddr_name = subaddr.find('name').text
                subaddr_value = subaddr.find('subaddress').text
                for system in address_book.values():
                    system['subaddresses'][subaddr_id] = {
                        'name': subaddr_name,
                        'value': subaddr_value
                    }
                    
            logger.info("[RADAR_MSGR] Address book loaded successfully")
            return address_book
        except Exception as e:
            logger.error(f"[RADAR_MSGR] Error loading address book: {str(e)}")
            raise

    def get_radar_address(self):
        """Get RT address for radar system using address utilities."""
        try:
            # Use address utilities for consistent addressing
            radar_address = get_rt_address('radar')
            logger.info(f"[RADAR_MSGR] Got radar address {radar_address} from address utilities")
            return radar_address
        except Exception as e:
            logger.warning(f"[RADAR_MSGR] Error getting radar address from utilities: {e}")
            # Fallback to cached value from address book if available
            if "radar" in self.address_book:
                try:
                    radar_address = int(self.address_book["radar"]["address"])
                    logger.info(f"[RADAR_MSGR] Using fallback radar address {radar_address} from address book")
                    return radar_address
                except (ValueError, KeyError) as e2:
                    logger.error(f"[RADAR_MSGR] Error extracting radar address from address book: {e2}")
            return 9  # Default radar address
                    

    def get_subaddress_info(self, sub_address: int) -> Tuple[Optional[str], Optional[str]]:
        """Get radar type and name from subaddress using address utilities."""
        try:
            # Try centralized address utilities first for consistent addressing
            from FMOFP.local_messaging.address_utils import get_subaddress_id_by_value
            subaddr_id = get_subaddress_id_by_value(sub_address)
            if subaddr_id:
                # Find the name from the address book
                for system in self.address_book.values():
                    for id, info in system['subaddresses'].items():
                        if id == subaddr_id:
                            logger.info(f"[RADAR_MSGR] Found subaddress {sub_address} mapped to ID {subaddr_id} with name {info['name']}")
                            return subaddr_id, info['name']
                
                # If found in utility but not in address book, log the discrepancy
                logger.warning(f"[RADAR_MSGR] Subaddress ID {subaddr_id} found by utility but not in local address book")
                return subaddr_id, None
        except Exception as e:
            logger.warning(f"[RADAR_MSGR] Error using address utilities for subaddress {sub_address}: {e}")
        
        # Fallback to direct lookup from address book    
        logger.info(f"[RADAR_MSGR] Falling back to direct address book lookup for subaddress {sub_address}")
        for system in self.address_book.values():
            for subaddr_id, info in system['subaddresses'].items():
                if info['value'] == str(sub_address):
                    logger.info(f"[RADAR_MSGR] Found subaddress {sub_address} directly in address book: {subaddr_id}, {info['name']}")
                    return subaddr_id, info['name']
        
        logger.warning(f"[RADAR_MSGR] Subaddress {sub_address} not found in any lookup method")
        return None, None

    def _message_loop(self):
        """Main message processing loop."""

        thread_id = threading.get_ident()
        logger.info(f"=== Starting RadarMessenger thread (ID: {thread_id}) ===")
        
        # Signal that the thread has started IMMEDIATELY
        # This is critical to avoid timeout in the start() method
        self._thread_started.set()
        logger.info("RadarMessenger thread signaled start")
        
        # Add throttling for logging
        last_log_time = 0
        log_interval = 10.0 
        
        # Add message counters for monitoring
        message_count = 0
        processed_count = 0
        
        # Initialize queue_manager as None before the try block
        queue_manager = None
        radar_address = 9  # Default radar address
        
        # All validation and setup code is now in a try/except block
        # This ensures the thread won't crash if there are issues during setup
        try:
            # Get queue manager
            queue_manager = get_message_queue_manager()
            if not queue_manager:
                logger.warning("Failed to get MessageQueueManager instance, will retry later")
            else:
                logger.info(f"RadarMessenger obtained MessageQueueManager instance: {id(queue_manager)}")
                # Verify queue manager is running
                if not hasattr(queue_manager, 'running') or not queue_manager.running:
                    logger.warning("MessageQueueManager is not running")
                    # Try to start it
                    try:
                        queue_manager.start()
                        logger.info("Started MessageQueueManager from RadarMessenger")
                    except Exception as e:
                        logger.warning(f"Failed to start MessageQueueManager: {e}")
                        logger.warning(traceback.format_exc())
            
                # Log initial state
                try:
                    radar_address = self.get_radar_address()
                    logger.info(f"[RADAR_MSGR] Looking for messages with RT address: {radar_address}")
                    logger.info(f"[RADAR_MSGR] Queue manager running: {queue_manager.running}")
                except Exception as e:
                    logger.warning(f"[RADAR_MSGR] Error getting radar address: {e}")
                    # Continue with default address
                
                # Check if radar queue exists
                if not hasattr(queue_manager, 'system_queues') or 'radar' not in queue_manager.system_queues:
                    logger.warning("Radar queue not found in MessageQueueManager, will use limited functionality")
                else:
                    logger.info("RadarMessenger verified radar queue exists in MessageQueueManager")
        except Exception as e:
            logger.error(f"Error during RadarMessenger initialization: {e}")
            logger.error(traceback.format_exc())
            logger.warning("RadarMessenger will operate with limited functionality")
        
        while self.running:
            try:
                # Log status periodically
                current_time = time.time()
                should_log = (current_time - last_log_time) >= log_interval
                
                if should_log:
                    # Log queue status
                    radar_queue_size = queue_manager.get_queue_size('radar')
                    logger.info(f"[RADAR_MSGR] Radar queue size: {radar_queue_size}")
                    logger.info(f"[RADAR_MSGR] Messages processed: {message_count}, Successfully processed: {processed_count}")
                    logger.info(f"[RADAR_MSGR] Looking for messages with RT address: {radar_address}")
                    last_log_time = current_time
                
                # Get message from radar queue
                try:
                    message_data = queue_manager.get_message('radar')
                    if message_data:
                        # Unpack the tuple (system, message) if message_data is a tuple
                        if isinstance(message_data, tuple) and len(message_data) == 2:
                            logger.info(f"[RADAR_MSGR] Received tuple from queue manager, unpacking")
                            system, message = message_data
                            logger.info(f"[RADAR_MSGR] Unpacked message from system: {system}")
                        else:
                            # Handle legacy case where message might not be a tuple
                            logger.info(f"[RADAR_MSGR] Received non-tuple data from queue manager")
                            message = message_data
                        
                        message_count += 1
                        
                        # Enhanced logging with more detailed message information
                        logger.info(f"[RADAR_MSGR] Processing message from radar queue: {type(message).__name__}")

                        # Check if message is not an object, it is a diction and needs to be converted
                        if not isinstance(message, MIL_STD_1553B_Message):
                            try:
                                message = self.convert_from_dict(message)
                            except Exception as e:
                                logger.error(f"[RADAR_MSGR] Error converting message from dict: {e}")
                                logger.error(traceback.format_exc())
                                continue

                        if isinstance(message, MIL_STD_1553B_Message) and hasattr(message, 'rt_address'):
                            logger.info(f"[RADAR_MSGR] Received message: rt={message.rt_address}")
                            if hasattr(message, 'data'):
                                logger.info(f"[RADAR_MSGR] Message data: {message.data}")
                            if hasattr(message, 'command_type'):
                                logger.info(f"[RADAR_MSGR] Command type: {message.command_type}")
                            if hasattr(message, 'message_type'):
                                logger.info(f"[RADAR_MSGR] Message type: {message.message_type}")
                            
                            # Add more detailed message tracking
                            logger.info(f"[RADAR_MSGR] *** DETAILED MESSAGE INFO ***")
                            logger.info(f"[RADAR_MSGR] Message ID: {id(message)}")
                            logger.info(f"[RADAR_MSGR] Message attributes:")
                            for attr_name in dir(message):
                                if not attr_name.startswith('_') and not callable(getattr(message, attr_name)):
                                    attr_value = getattr(message, attr_name)
                                    logger.info(f"[RADAR_MSGR]   - {attr_name}: {attr_value}")

                            # Process the message based on its type
                            try:
                                if isinstance(message, MIL_STD_1553B_Message):
                                    # Already a MIL_STD_1553B_Message, but ensure all metadata is preserved
                                    logger.info(f"[RADAR_MSGR] Ensuring metadata is preserved for existing MIL_STD_1553B_Message")
                                    mil_std_msg = self._convert_to_mil_std_message(message)
                                    logger.info(f"[RADAR_MSGR] Processing MIL_STD_1553B_Message directly without re-routing")
                                    
                                    # Extract radar type directly without calling route_message to avoid recursion
                                    radar_type = None
                                    
                                    # ONLY check for processed_by flag if message is also MARKED as completed
                                    # This prevents breaking out too early before radar actually processes message
                                    if (hasattr(mil_std_msg, 'metadata') and 
                                        isinstance(mil_std_msg.metadata, dict) and 
                                        'processed_by' in mil_std_msg.metadata and
                                        'processing_complete' in mil_std_msg.metadata and
                                        mil_std_msg.metadata.get('processing_complete') == True):
                                        
                                        if 'radar' in mil_std_msg.metadata['processed_by']:
                                            logger.info(f"[RADAR_MSGR] Breaking loop - message already fully processed by radar system")
                                            processed_count += 1
                                            continue
                                        
                                    # Try to identify radar type from message_type using standard constants
                                    if hasattr(mil_std_msg, 'message_type'):
                                        msg_type = str(mil_std_msg.message_type).lower()
                                        logger.info(f"[RADAR_MSGR] Checking message_type: {msg_type}")
                                        
                                        # Check against standardized message type constants
                                        # First check for direct command messages which are most specific
                                        if TFR_RADAR_COMMAND.lower() == msg_type:
                                            radar_type = 'tfr_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='tfr_radar' from exact command match")
                                        elif SAR_RADAR_COMMAND.lower() == msg_type:
                                            radar_type = 'sar_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='sar_radar' from exact command match")
                                        elif TARGETING_RADAR_COMMAND.lower() == msg_type:
                                            radar_type = 'targeting_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='targeting_radar' from exact command match")
                                        elif AEWC_RADAR_COMMAND.lower() == msg_type:
                                            radar_type = 'aewc_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='aewc_radar' from exact command match")
                                        elif 'tfr_radarcommand' == msg_type:
                                            radar_type = 'tfr_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='tfr_radar' from lowercase command match")
                                        elif 'sar_radarcommand' == msg_type:
                                            radar_type = 'sar_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='sar_radar' from lowercase command match")
                                        elif 'targeting_radarcommand' == msg_type:
                                            radar_type = 'targeting_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='targeting_radar' from lowercase command match")
                                        elif 'aewc_radarcommand' == msg_type:
                                            radar_type = 'aewc_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='aewc_radar' from lowercase command match")
                                        # Then check standardized request/response patterns
                                        elif (WEATHER_RADAR_MODE_CHANGE_REQUEST.lower() in msg_type or 
                                              WEATHER_RADAR_MODE_CHANGE_RESPONSE.lower() in msg_type or
                                              WEATHER_RADAR_STATUS_REQUEST.lower() in msg_type or
                                              WEATHER_RADAR_STATUS_RESPONSE.lower() in msg_type or
                                              WEATHER_RADAR_VIL_REQUEST.lower() in msg_type or
                                              WEATHER_RADAR_VIL_RESPONSE.lower() in msg_type or
                                              WEATHER_RADAR_PRECIPITATION_REQUEST.lower() in msg_type or
                                              WEATHER_RADAR_PRECIPITATION_RESPONSE.lower() in msg_type):
                                            radar_type = 'weather_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='weather_radar' from message_type")
                                        elif (TFR_RADAR_MODE_CHANGE_REQUEST.lower() in msg_type or
                                              TFR_RADAR_MODE_CHANGE_RESPONSE.lower() in msg_type or
                                              TFR_RADAR_STATUS_REQUEST.lower() in msg_type or
                                              TFR_RADAR_STATUS_RESPONSE.lower() in msg_type or
                                              TFR_RADAR_ELEVATION_DATA_REQUEST.lower() in msg_type or
                                              TFR_RADAR_ELEVATION_DATA_RESPONSE.lower() in msg_type):
                                            radar_type = 'tfr_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='tfr_radar' from message_type")
                                        elif (SAR_RADAR_MODE_CHANGE_REQUEST.lower() in msg_type or
                                              SAR_RADAR_MODE_CHANGE_RESPONSE.lower() in msg_type or
                                              SAR_RADAR_STATUS_REQUEST.lower() in msg_type or
                                              SAR_RADAR_STATUS_RESPONSE.lower() in msg_type):
                                            radar_type = 'sar_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='sar_radar' from message_type")
                                        elif (TARGETING_RADAR_MODE_CHANGE_REQUEST.lower() in msg_type or
                                              TARGETING_RADAR_MODE_CHANGE_RESPONSE.lower() in msg_type or
                                              TARGETING_RADAR_STATUS_REQUEST.lower() in msg_type or
                                              TARGETING_RADAR_STATUS_RESPONSE.lower() in msg_type):
                                            radar_type = 'targeting_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='targeting_radar' from message_type")
                                        elif (AEWC_RADAR_MODE_CHANGE_REQUEST.lower() in msg_type or
                                              AEWC_RADAR_MODE_CHANGE_RESPONSE.lower() in msg_type or
                                              AEWC_RADAR_STATUS_REQUEST.lower() in msg_type or
                                              AEWC_RADAR_STATUS_RESPONSE.lower() in msg_type):
                                            radar_type = 'aewc_radar'
                                            logger.info(f"[RADAR_MSGR] Identified radar_type='aewc_radar' from message_type")
                                        
                                        # If not found in message type, try command_name
                                        if not radar_type and hasattr(mil_std_msg, 'command_name'):
                                            cmd_name = str(mil_std_msg.command_name).upper()
                                            logger.info(f"[RADAR_MSGR] Checking command_name: {cmd_name}")
                                            if 'WEATHER' in cmd_name:
                                                radar_type = 'weather_radar'
                                                logger.info(f"[RADAR_MSGR] Identified radar_type='weather_radar' from command_name")
                                            elif 'TFR' in cmd_name:
                                                radar_type = 'tfr_radar'
                                                logger.info(f"[RADAR_MSGR] Identified radar_type='tfr_radar' from command_name")
                                            elif 'SAR' in cmd_name:
                                                radar_type = 'sar_radar'
                                                logger.info(f"[RADAR_MSGR] Identified radar_type='sar_radar' from command_name")
                                            elif 'TARGETING' in cmd_name:
                                                radar_type = 'targeting_radar'
                                                logger.info(f"[RADAR_MSGR] Identified radar_type='targeting_radar' from command_name")
                                            elif 'AEWC' in cmd_name:
                                                radar_type = 'aewc_radar'
                                                logger.info(f"[RADAR_MSGR] Identified radar_type='aewc_radar' from command_name")

                                        if radar_type and self.radar_control and hasattr(self.radar_control, 'radars'):
                                            radar = self.radar_control.radars.get(radar_type)
                                            if radar:
                                                logger.info(f"[RADAR_MSGR] Directly calling receive_message on {radar_type}")
                                                
                                                # Set proper metadata before processing
                                                if not hasattr(mil_std_msg, 'metadata'):
                                                    mil_std_msg.metadata = {}
                                                
                                                # Process the message
                                                process_result = radar.receive_message_sync(mil_std_msg)
                                                
                                                # Mark as fully processed AFTER actual processing
                                                if not hasattr(mil_std_msg, 'metadata'):
                                                    mil_std_msg.metadata = {}
                                                    
                                                if 'processed_by' not in mil_std_msg.metadata:
                                                    mil_std_msg.metadata['processed_by'] = []
                                                
                                                if 'radar' not in mil_std_msg.metadata['processed_by']:
                                                    mil_std_msg.metadata['processed_by'].append('radar')
                                                
                                                # Critical flag to mark complete processing
                                                mil_std_msg.metadata['processing_complete'] = True
                                                
                                                logger.info(f"[RADAR_MSGR] Message successfully processed by {radar_type}")
                                            else:
                                                logger.error(f"[RADAR_MSGR] Radar type {radar_type} not found in radar control system")
                                        else:
                                            logger.error(f"[RADAR_MSGR] Could not determine radar type or radar control not available")
                                        
                                        processed_count += 1
                                elif isinstance(message, dict):
                                    raise ValueError("[RADAR_MSGR] Message is still dictionary after conversion")
                                else:
                                    logger.warning(f"[RADAR_MSGR] Unsupported message type: {type(message)}")
                            except Exception as e:
                                logger.error(f"[RADAR_MSGR] Error processing message: {e}")
                                logger.error(traceback.format_exc())
                except Exception as e:
                    logger.error(f"[RADAR_MSGR] Error getting message from queue: {e}")
                    logger.error(traceback.format_exc())
                
                # Prevent tight loop but don't sleep too long
                time.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"[RADAR_MSGR] Error processing messages: {str(e)}")
                logger.error(traceback.format_exc())
                if not self.running:
                    break
                time.sleep(.01)  # Sleep longer on error
            
        logger.info(f"=== RadarMessenger thread (ID: {thread_id}) ended ===")
        
    def convert_from_dict(self, message_dict):
        """Convert a dictionary message to a MIL_STD_1553B_Message object."""
        try:
            from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
            
            # Extract required fields
            rt_address = message_dict.get('rt_address', 9)  # Default to radar address
            sub_address = message_dict.get('subaddress') or message_dict.get('sub_address', 1)  # Default to data subaddress
            data = message_dict.get('data', [0])  # Default to empty data
            
            # Create MIL_STD_1553B_Message
            message = MIL_STD_1553B_Message(
                rt_address=rt_address,
                sub_address=sub_address,
                data=data
            )
            
            # Copy all other fields as attributes
            for key, value in message_dict.items():
                if key not in ['rt_address', 'subaddress', 'sub_address', 'data']:
                    setattr(message, key, value)
            
            return message
        except Exception as e:
            logger.error(f"[RADAR_MSGR] Error converting dict to MIL_STD_1553B_Message: {e}")
            logger.error(traceback.format_exc())
            raise

    def _convert_to_mil_std_message(self, message):
        """Convert various message formats to a standardized MIL_STD_1553B_Message.
        
        This method ensures all metadata fields (request_id, command_name, etc.)
        are properly preserved during conversion.
        
        Args:
            message: Dictionary or object message to convert
            
        Returns:
            MIL_STD_1553B_Message: Standardized message with preserved metadata
        """
        # NOTE: previously flagged as "create a local copy of this file,
        # replace import". Investigated: MIL_STD_1553B_Message is the actual
        # wire-message class used across the whole simulation - radar,
        # displays, FMS, and the BC/RT listeners all construct, pass, and
        # isinstance()-check this exact type when messages cross subsystem
        # boundaries. A radar-local copy would be a different class at
        # runtime, breaking every isinstance()/interop check against
        # messages built or consumed elsewhere and fragmenting the one wire
        # format all systems must share. This shared import is intentional
        # and correct; not duplicating it.
        from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
        
        # Initialize result values
        rt_address = None
        sub_address = None
        data = None
        metadata = {}
        
        # Step 1: Extract all fields based on message type (dict or object)
        if isinstance(message, dict):
            # Dictionary case - extract all possible fields
            rt_address = message.get('rt_address')
            
            # Handle subaddress variations
            sub_address = message.get('subaddress')
            if sub_address is None:
                sub_address = message.get('sub_address')
                
            data = message.get('data')
            
            # Extract dictionary metadata
            if 'metadata' in message and isinstance(message.get('metadata'), dict):
                metadata.update(message['metadata'])
                
            # Capture all other fields
            for field in message:
                if field not in ['rt_address', 'subaddress', 'sub_address', 'data', 'metadata']:
                    metadata[field] = message[field]
                    
        elif isinstance(message, MIL_STD_1553B_Message):
            # MIL_STD_1553B_Message case - extract standard fields
            rt_address = message.rt_address
            sub_address = message.sub_address
            data = message.data
            
            # Extract all other attributes as metadata
            for attr in dir(message):
                if not attr.startswith('_') and attr not in ['rt_address', 'sub_address', 'data']:
                    if not callable(getattr(message, attr)):
                        metadata[attr] = getattr(message, attr)
        else:
            # Object case (not MIL_STD_1553B_Message)
            if hasattr(message, 'rt_address'):
                rt_address = getattr(message, 'rt_address')
                
            if hasattr(message, 'subaddress'):
                sub_address = getattr(message, 'subaddress')
            elif hasattr(message, 'sub_address'):
                sub_address = getattr(message, 'sub_address')
                
            if hasattr(message, 'data'):
                data = getattr(message, 'data')
                
            # Extract object metadata
            if hasattr(message, 'metadata') and isinstance(getattr(message, 'metadata'), dict):
                metadata.update(getattr(message, 'metadata'))
                
            # Capture all other fields
            for attr in dir(message):
                if not attr.startswith('_') and attr not in ['rt_address', 'subaddress', 'sub_address', 'data', 'metadata']:
                    if not callable(getattr(message, attr)):
                        metadata[attr] = getattr(message, attr)
        
        # Step 2: Handle default values and validations
        # For mode_change_completion messages, use subaddress 4 (standard for radar mode changes)
        if sub_address is None:
            if metadata.get('command_type') == 'mode_change_completion':
                sub_address = 4  # Standard subaddress for radar mode changes
                logger.info(f"[RADAR_MSGR] Using default subaddress 4 for mode_change_completion")
            else:
                # Last resort default
                sub_address = 1
                logger.warning(f"[RADAR_MSGR] No subaddress found, using default: 1")
                
        if rt_address is None:
            rt_address = 9  # Default radar address
            logger.warning(f"[RADAR_MSGR] No RT address found, using default: 9")
            
        if data is None:
            data = [0]  # Default empty data
            logger.warning(f"[RADAR_MSGR] No data found, using default empty data")
        
        # Step 3: Create the MIL_STD_1553B_Message
        mil_std_message = MIL_STD_1553B_Message(
            rt_address=rt_address,
            sub_address=sub_address,
            data=data
        )
        
        # Step 4: Preserve ALL metadata fields by copying them to the message
        preserved_fields = []
        
        for field, value in metadata.items():
            if value is not None:  # Only copy non-None values
                setattr(mil_std_message, field, value)
                preserved_fields.append(field)
        
        # Log critical fields for debugging
        critical_fields = ['request_id', 'command_name', 'message_type', 'command_type']
        for field in critical_fields:
            if hasattr(mil_std_message, field) and getattr(mil_std_message, field) is not None:
                logger.info(f"[RADAR_MSGR] Preserved critical field: {field}={getattr(mil_std_message, field)}")
        
        # Handle specific logging for mode messages
        if metadata.get('command_type') == 'mode':
            mode_value = None
            if isinstance(data, str) and data.isdigit():
                mode_value = int(data)
            elif isinstance(data, int):
                mode_value = data
            elif isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if isinstance(first_item, str) and first_item.isdigit():
                    mode_value = int(first_item)
                elif isinstance(first_item, int):
                    mode_value = first_item
                    
            if mode_value is not None:
                # Get mode name from enum
                mode_name = None
                try:
                    from Systems.radarManagement.radar_enums import weather_radarMode
                    mode_name = weather_radarMode(mode_value).name
                    logger.info(f"[RADAR_MSGR] Mode identified as {mode_name} (value: {mode_value})")
                except (ValueError, AttributeError):
                    mode_name = f"UNKNOWN_MODE_{mode_value}"
                    logger.warning(f"[RADAR_MSGR] Unknown mode value: {mode_value}")
        
        # Log overall results
        logger.info(f"[RADAR_MSGR] Converted message to MIL_STD_1553B_Message with {len(preserved_fields)} preserved fields")
        
        return mil_std_message
        
    def route_message(self, message: MIL_STD_1553B_Message):
        """Route incoming messages directly to appropriate radar system."""
        try:
            # Log incoming message details
            logger.info(f"[RADAR_MSG] Received message with RT address: {message.rt_address}")
            logger.info(f"[RADAR_MSG] Message data: {message.data}")
            logger.info(f"[RADAR_MSG] Message type: {message.message_type if hasattr(message, 'message_type') else None}")
            logger.info(f"[RADAR_MSG] Command type: {message.command_type if hasattr(message, 'command_type') else None}")
            
            # Check if this message is for radar system using address utilities
            try:
                radar_address = get_rt_address('radar')
                logger.info(f"[RADAR_MSG] Expected radar address from utilities: {radar_address}")
                
                # Check if message is for radar (now using resolved address)
                if message.rt_address != radar_address and message.rt_address != 9:
                    logger.warning(f"[RADAR_MSG] Message RT address {message.rt_address} does not match radar address {radar_address} or 9")
                    
                    # Check if message has radar-related message type or command name
                    is_radar_message = False
                    
                    # Check message type
                    if hasattr(message, 'message_type') and message.message_type:
                        msg_type = str(message.message_type).lower()
                        if 'radar' in msg_type or 'weather' in msg_type:
                            is_radar_message = True
                            logger.info(f"[RADAR_MSG] Detected radar message from message_type: {message.message_type}")
                    
                    # Check command name
                    if hasattr(message, 'command_name') and message.command_name:
                        cmd_name = str(message.command_name)
                        if 'RADAR' in cmd_name or 'WEATHER' in cmd_name:
                            is_radar_message = True
                            logger.info(f"[RADAR_MSG] Detected radar message from command_name: {message.command_name}")
                    
                    # Check metadata
                    if hasattr(message, 'metadata') and message.metadata:
                        metadata = message.metadata
                        if isinstance(metadata, dict):
                            if 'message_type' in metadata and ('radar' in str(metadata['message_type']).lower() or 'weather' in str(metadata['message_type']).lower()):
                                    is_radar_message = True
                                    logger.info(f"[RADAR_MSG] Detected radar message from metadata.message_type: {metadata['message_type']}")
                            if 'command_name' in metadata and ('RADAR' in str(metadata['command_name']) or 'WEATHER' in str(metadata['command_name'])):
                                is_radar_message = True
                                logger.info(f"[RADAR_MSG] Detected radar message from metadata.command_name: {metadata['command_name']}")
                
                    # If not a radar message, return
                    if not is_radar_message:
                        logger.warning(f"[RADAR_MSG] Message is not a radar message, skipping")
                        return
                    
                    # If it is a radar message, log and continue processing
                    logger.info(f"[RADAR_MSG] Processing radar message despite RT address mismatch")
            except Exception as e:
                logger.error(f"[RADAR_MSG] Error resolving radar address with utilities: {e}")
                logger.error(traceback.format_exc())
                
                # Unable to resolve radar address properly, rely on message content analysis
                logger.warning(f"[RADAR_MSG] Message RT address {message.rt_address} does not match expected radar address from address utilities")
                
                # Same checks for radar message type despite address mismatch
                is_radar_message = False
                
                # Check message type
                if hasattr(message, 'message_type') and message.message_type:
                    msg_type = str(message.message_type).lower()
                    if 'radar' in msg_type or 'weather' in msg_type:
                        is_radar_message = True
                        logger.info(f"[RADAR_MSG] Detected radar message from message_type: {message.message_type}")
                
                # Check command name
                if hasattr(message, 'command_name') and message.command_name:
                    cmd_name = str(message.command_name)
                    if 'RADAR' in cmd_name or 'WEATHER' in cmd_name:
                        is_radar_message = True
                        logger.info(f"[RADAR_MSG] Detected radar message from command_name: {message.command_name}")
                
                # Check metadata
                if hasattr(message, 'metadata') and message.metadata:
                    metadata = message.metadata
                    if isinstance(metadata, dict):
                        if 'message_type' in metadata and ('radar' in str(metadata['message_type']).lower() or 'weather' in str(metadata['message_type']).lower()):
                            is_radar_message = True
                            logger.info(f"[RADAR_MSG] Detected radar message from metadata.message_type: {metadata['message_type']}")
                        if 'command_name' in metadata and ('RADAR' in str(metadata['command_name']) or 'WEATHER' in str(metadata['command_name'])):
                            is_radar_message = True
                            logger.info(f"[RADAR_MSG] Detected radar message from metadata.command_name: {metadata['command_name']}")
                
                # If not a radar message, return
                if not is_radar_message:
                    logger.warning(f"[RADAR_MSG] Message is not a radar message, skipping")
                    return
            
            # Verify radar control is available
            if not self.radar_control:
                logger.error("[RADAR_MSGR] No radar control system connected")
                return

            # Get radar type from message type or subaddress
            radar_type = None
            
            # Log message attributes for debugging
            logger.info(f"[RADAR_MSG] Message attributes for radar type identification:")
            if hasattr(message, 'message_type'):
                logger.info(f"[RADAR_MSG] message_type: {message.message_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[RADAR_MSG] command_name: {message.command_name}")
            if hasattr(message, 'command_type'):
                logger.info(f"[RADAR_MSG] command_type: {message.command_type}")
            if hasattr(message, 'destination'):
                logger.info(f"[RADAR_MSG] destination: {message.destination}")
            
            # Try to identify radar type from message type using standardized helpers
            msg_type = get_message_type(message)
            logger.info(f"[RADAR_MSG] Checking message_type using get_message_type(): {msg_type}")
            
            if msg_type:
                # Use standardized helper functions first
                if is_vil_message(message):
                    radar_type = 'weather_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='weather_radar' from is_vil_message() check")
                elif is_precipitation_message(message):
                    radar_type = 'weather_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='weather_radar' from is_precipitation_message() check")
                elif is_mode_change_message(message):
                    # Check specific radar type for mode change
                    msg_type_lower = str(msg_type).lower()
                    if 'weather' in msg_type_lower:
                        radar_type = 'weather_radar'
                    elif 'tfr' in msg_type_lower:
                        radar_type = 'tfr_radar'
                    elif 'sar' in msg_type_lower:
                        radar_type = 'sar_radar'
                    elif 'targeting' in msg_type_lower:
                        radar_type = 'targeting_radar'
                    elif 'aewc' in msg_type_lower:
                        radar_type = 'aewc_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='{radar_type}' from is_mode_change_message() check")
                # First check for direct command matches to handle exact matches for all radar types
                elif msg_type == TFR_RADAR_COMMAND.lower():
                    radar_type = 'tfr_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='tfr_radar' from exact TFR command match")
                elif msg_type == SAR_RADAR_COMMAND.lower():
                    radar_type = 'sar_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='sar_radar' from exact SAR command match")
                elif msg_type == TARGETING_RADAR_COMMAND.lower():
                    radar_type = 'targeting_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='targeting_radar' from exact TARGETING command match")
                elif msg_type == AEWC_RADAR_COMMAND.lower():
                    radar_type = 'aewc_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='aewc_radar' from exact AEWC command match")
                # Check for radar-specific command formats without constants
                elif msg_type == 'tfr_radarcommand':
                    radar_type = 'tfr_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='tfr_radar' from lowercase command")
                elif msg_type == 'sar_radarcommand':
                    radar_type = 'sar_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='sar_radar' from lowercase command")
                elif msg_type == 'targeting_radarcommand':
                    radar_type = 'targeting_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='targeting_radar' from lowercase command")
                elif msg_type == 'aewc_radarcommand':
                    radar_type = 'aewc_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='aewc_radar' from lowercase command")
                # Fall back to string matching if needed
                elif 'weather_radar' in str(msg_type).lower():
                    radar_type = 'weather_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='weather_radar' from message_type")
                elif 'tfr_radar' in str(msg_type).lower():
                    radar_type = 'tfr_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='tfr_radar' from message_type")
                elif 'sar_radar' in str(msg_type).lower():
                    radar_type = 'sar_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='sar_radar' from message_type")
                elif 'targeting_radar' in str(msg_type).lower():
                    radar_type = 'targeting_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='targeting_radar' from message_type")
                elif 'aewc_radar' in str(msg_type).lower():
                    radar_type = 'aewc_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='aewc_radar' from message_type")
            
            # If not found in message_type, try command_name
            if not radar_type and hasattr(message, 'command_name'):
                cmd_name = str(message.command_name).upper()
                logger.info(f"[RADAR_MSG] Checking command_name: {cmd_name}")
                if 'WEATHER' in cmd_name:
                    radar_type = 'weather_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='weather_radar' from command_name")
                elif 'TFR' in cmd_name:
                    radar_type = 'tfr_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='tfr_radar' from command_name")
                elif 'SAR' in cmd_name:
                    radar_type = 'sar_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='sar_radar' from command_name")
                elif 'TARGETING' in cmd_name:
                    radar_type = 'targeting_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='targeting_radar' from command_name")
                elif 'AEWC' in cmd_name:
                    radar_type = 'aewc_radar'
                    logger.info(f"[RADAR_MSG] Identified radar_type='aewc_radar' from command_name")

            # If not found in message type or command_name, try subaddress
            if not radar_type:
                subaddr_type, subaddr_name = self.get_subaddress_info(message.sub_address)
                logger.info(f"[RADAR_MSG] Checking subaddress {message.sub_address}: type={subaddr_type}, name={subaddr_name}")
                if subaddr_type:
                    radar_type = subaddr_type
                    logger.info(f"[RADAR_MSG] Identified radar_type='{radar_type}' from subaddress")
                    
            # If still not found, default to weather_radar for RT address 9
            if not radar_type and message.rt_address == 9:
                logger.info(f"[RADAR_MSG] Defaulting to radar_type='weather_radar' for RT address 9")
                radar_type = 'weather_radar'

            if not radar_type:
                logger.error(f"[RADAR_MSGR] Could not determine radar type from message: {message}")
                return

            # Log the identified radar type
            logger.info(f"[RADAR_MSG] Final identified radar_type: '{radar_type}'")
            
            # Log available radar types in radar_control.radars
            if self.radar_control and hasattr(self.radar_control, 'radars'):
                available_radars = list(self.radar_control.radars.keys())
                logger.info(f"[RADAR_MSG] Available radar types in radar_control.radars: {available_radars}")
                
                # Check if the identified radar_type exists in radar_control.radars
                if radar_type in available_radars:
                    logger.info(f"[RADAR_MSG] Identified radar_type '{radar_type}' exists in radar_control.radars")
                else:
                    logger.error(f"[RADAR_MSG] Identified radar_type '{radar_type}' NOT FOUND in radar_control.radars")
                    
                    # Try to find a matching radar by name
                    for key, radar_obj in self.radar_control.radars.items():
                        if hasattr(radar_obj, 'name') and radar_obj.name == radar_type:
                            logger.info(f"[RADAR_MSG] Found radar with name='{radar_type}' under key='{key}'")
                            radar_type = key
                            break
            else:
                logger.error(f"[RADAR_MSG] radar_control or radar_control.radars not available")

            # Get radar instance
            radar = None
            if self.radar_control and hasattr(self.radar_control, 'radars'):
                radar = self.radar_control.radars.get(radar_type)
                
            if not radar:
                logger.error(f"[RADAR_MSGR] {radar_type} not found in radar control system")
                # Log available radar types
                if self.radar_control and hasattr(self.radar_control, 'radars'):
                    logger.error(f"[RADAR_MSGR] Available radar types: {list(self.radar_control.radars.keys())}")
                    
                    # Try to find a radar by class name
                    for key, radar_obj in self.radar_control.radars.items():
                        class_name = radar_obj.__class__.__name__.lower()
                        logger.info(f"[RADAR_MSG] Checking radar '{key}' with class '{class_name}'")
                        if 'weather' in class_name and radar_type == 'weather_radar':
                            logger.info(f"[RADAR_MSG] Found weather radar under key '{key}'")
                            radar = radar_obj
                            radar_type = key
                            break
                        elif radar_type in class_name:
                            logger.info(f"[RADAR_MSG] Found matching radar under key '{key}'")
                            radar = radar_obj
                            radar_type = key
                            break
            
            # Forward the message to the radar instance
            if radar:
                logger.info(f"[RADAR_MSG] Forwarding message to {radar_type}")
                
                # Ensure message has proper metadata
                if not hasattr(message, 'metadata'):
                    message.metadata = {}
                
                if isinstance(message.metadata, dict):
                    if 'processed_by' not in message.metadata:
                        message.metadata['processed_by'] = []
                        
                    if 'radar_messenger' not in message.metadata['processed_by']:
                        message.metadata['processed_by'].append('radar_messenger')
                
                # Forward to the radar for processing
                try:
                    radar.receive_message(message)
                    logger.info(f"[RADAR_MSG] Message successfully forwarded to {radar_type}")
                except Exception as e:
                    logger.error(f"[RADAR_MSG] Error forwarding message to {radar_type}: {e}")
                    logger.error(traceback.format_exc())
            else:
                logger.error(f"[RADAR_MSG] No radar instance found for {radar_type}")
                
        except Exception as e:
            logger.error(f"[RADAR_MSG] Error routing message: {e}")
            logger.error(traceback.format_exc())
            
    def start(self):
        """Start the radar messenger message handling loop."""
        try:
            with self._lock:
                if self.running:
                    logger.warning("[RADAR_MSGR] RadarMessenger already running, ignoring start request")
                    return
                    
                self.running = True
                self._thread_started.clear()
                
                # Start message handling thread
                self.message_thread = threading.Thread(
                    target=self._message_loop,
                    name="RadarMessengerThread",
                    daemon=True
                )
                self.message_thread.start()
                
                # Wait for thread to signal it has started (with timeout)
                start_timeout = 5.0  # seconds
                if not self._thread_started.wait(start_timeout):
                    logger.error(f"[RADAR_MSGR] Thread start timeout after {start_timeout} seconds")
                    self.running = False
                    raise RuntimeError(f"RadarMessenger thread failed to start within {start_timeout} seconds")
                    
                logger.info("[RADAR_MSGR] RadarMessenger started successfully")
        except Exception as e:
            self.running = False
            logger.error(f"[RADAR_MSGR] Error starting RadarMessenger: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def stop(self):
        """Stop the radar messenger message handling loop."""
        try:
            with self._lock:
                if not self.running:
                    logger.warning("[RADAR_MSGR] RadarMessenger not running, ignoring stop request")
                    return
                    
                logger.info("[RADAR_MSGR] Stopping RadarMessenger...")
                self.running = False
                
                # Wait for message thread to end with timeout
                if hasattr(self, 'message_thread') and self.message_thread and self.message_thread.is_alive():
                    stop_timeout = 5.0  # seconds
                    self.message_thread.join(stop_timeout)
                    
                    if self.message_thread.is_alive():
                        logger.warning(f"[RADAR_MSGR] Thread did not terminate within {stop_timeout} seconds")
                    else:
                        logger.info("[RADAR_MSGR] RadarMessenger thread terminated successfully")
                else:
                    logger.info("[RADAR_MSGR] No active message thread found")
                    
                logger.info("[RADAR_MSGR] RadarMessenger stopped")
        except Exception as e:
            logger.error(f"[RADAR_MSGR] Error stopping RadarMessenger: {e}")
            logger.error(traceback.format_exc())

# Add this at the end of radarMessenger.py
def get_radar_messenger():
    """Get the global RadarMessenger instance."""
    return RadarMessenger()
