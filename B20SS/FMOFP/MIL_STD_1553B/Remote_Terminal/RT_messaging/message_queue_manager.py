"""
Message Queue Manager
ONE WAY QUEUE! Does not send message back to the Bus Controller.
Manages system-specific message queues to prevent race conditions between systems.
"""

import threading
import time
import copy
import traceback
from collections import deque
from typing import List
from xml.etree import ElementTree as ET
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class MessageQueueManager:
    _instance = None
    _lock = threading.RLock()  # Class-level lock for thread safety
    _initialized = False
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MessageQueueManager, cls).__new__(cls)
                logger.info("[MSG_Q_MGR] MessageQueueManager instance created")
            return cls._instance
    
    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                logger.info("[MSG_Q_MGR] MessageQueueManager initializing...")
                # Get the RT_Listener instance from Remote_Terminal
                from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import Remote_Terminal
                rt_instance = Remote_Terminal()
                self.rt_listener = rt_instance.rt_listener
                logger.info(f"[MSG_Q_MGR] MessageQueueManager using RT_Listener instance from Remote_Terminal: {id(self.rt_listener)}")
                
                # Initialize system queues for all known systems
                self.system_queues = {
                    'radar': deque(),        # Queue for radar messages
                    'display': deque(),      # Queue for display messages
                    'navigation': deque(),   # Queue for navigation messages
                    'communication': deque(), # Queue for communication messages
                    'power': deque(),        # Queue for power management messages
                    'environmental': deque(), # Queue for environmental control messages
                    'fms': deque(),          # Queue for flight management system messages
                    'flightmanagementsystem': deque()  # Queue for FMS messages matching system ID
                }
                
                # Initialize locks for all queues
                self.queue_locks = {system: threading.Lock() for system in self.system_queues}
                
                self.running = False
                self.thread = None
                self.address_book = self._load_address_book()
                
                # Add logging throttling
                self.last_log_time = 0
                self.log_interval = 10.0 
                
                # Add health monitoring
                self.last_health_check = 0
                self.health_check_interval = 10.0  # Check health every 5 seconds
                self.message_count = 0
                self.route_count = 0
                
                # Add detailed message tracking
                self._interval_message_types = {}  # Track message types between log intervals
                self._interval_destinations = {}   # Track destinations between log intervals
                self._last_message_count = 0
                self._last_route_count = 0
                
                # Add message history tracking
                self._message_history = {system: [] for system in self.system_queues}  # Track last 10 messages per queue
                self._message_history_max_size = 100
                
                self.__class__._initialized = True
                logger.info("[MSG_Q_MGR] MessageQueueManager initialized with queues: " + ", ".join(self.system_queues.keys()))
    
    def _load_address_book(self):
        """Load address book from XML."""
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
                    
            logger.info("[MSG_Q_MGR] MessageQueueManager: Address book loaded successfully")
            return address_book
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] MessageQueueManager: Error loading address book: {str(e)}")
            raise
    
    def get_radar_address(self):
        """Get RT address for radar system from address book."""
        return int(self.address_book["radar"]["address"])
    
    def get_display_address(self):
        """Get RT address for display system from address book."""
        return int(self.address_book["displays"]["address"])
    
    def start(self):
        """Start the message routing thread."""
        with self.__class__._lock:
            # Check if already running
            if self.running and self.thread and self.thread.is_alive():
                logger.info("[MSG_Q_MGR] MessageQueueManager already running")
                return
            
            # Check for existing thread with same name
            for thread in threading.enumerate():
                if thread.name == "MessageQueueManager" and thread.is_alive():
                    logger.info("[MSG_Q_MGR] MessageQueueManager thread already exists")
                    self.thread = thread
                    self.running = True
                    return
            
            # Create and start new thread
            logger.info("[MSG_Q_MGR] Starting new MessageQueueManager thread")
            self.running = True
            self.thread = threading.Thread(target=self._route_messages_loop, name="MessageQueueManager")
            self.thread.daemon = True
            self.thread.start()
            logger.info("[MSG_Q_MGR] MessageQueueManager thread started")
            self.running = True
            return
        
        
    def stop(self):
        """Stop the message routing thread."""
        with self.__class__._lock:
            if not self.running:
                logger.info("[MSG_Q_MGR] MessageQueueManager already stopped")
                return
                
            logger.info("[MSG_Q_MGR] Stopping MessageQueueManager")
            self.running = False
            
            if self.thread and self.thread.is_alive():
                try:
                    self.thread.join(timeout=2.0)
                    if self.thread.is_alive():
                        logger.warning("[MSG_Q_MGR] MessageQueueManager thread did not terminate within timeout")
                    else:
                        logger.info("[MSG_Q_MGR] MessageQueueManager thread terminated successfully")
                except Exception as e:
                    logger.error(f"[MSG_Q_MGR] Error stopping MessageQueueManager thread: {e}")
            
            self.thread = None
            logger.info("[MSG_Q_MGR] MessageQueueManager stopped")
    
    def _route_messages_loop(self):
        """Main message routing loop."""
        logger.info("[MSG_Q_MGR] MessageQueueManager routing loop started")
        thread_id = threading.get_ident()
        logger.info(f"[MSG_Q_MGR] MessageQueueManager running in thread ID: {thread_id}")
        
        # Log initial state
        self._log_queue_status(force=True)
        
        while self.running:
            try:
                message = None
                current_time = time.time()
                should_log = (current_time - self.last_log_time) >= self.log_interval
                
                # Log queue status periodically
                if should_log:
                    self._log_queue_status(force=True)
                
                # Get message from RT_Listener queue
                if should_log:
                    logger.info("[MSG_Q_MGR] MessageQueueManager checking RT_Listener processed_messages queue")
                
                # Always refresh RT_Listener reference to ensure we're using the same instance as Remote_Terminal
                previous_rt_listener_id = id(self.rt_listener) if self.rt_listener else None
                
                # Get the RT_Listener instance from Remote_Terminal
                from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import Remote_Terminal
                rt_instance = Remote_Terminal()
                self.rt_listener = rt_instance.rt_listener
                
                current_rt_listener_id = id(self.rt_listener)
                
                # Log if the instance changed
                if previous_rt_listener_id and previous_rt_listener_id != current_rt_listener_id:
                    logger.warning(f"[MSG_Q_MGR] RT_Listener instance changed: {previous_rt_listener_id} -> {current_rt_listener_id}")
                elif should_log:
                    logger.info(f"[MSG_Q_MGR] Using RT_Listener instance: {current_rt_listener_id}")
                
                # Verify RT_Listener is available
                if not self.rt_listener:
                    logger.error("[MSG_Q_MGR] RT_Listener is not available")
                    time.sleep(0.05)
                    continue
                
                # Check if RT_Listener has processed_messages attribute
                if not hasattr(self.rt_listener, 'processed_messages'):
                    logger.error("[MSG_Q_MGR] RT_Listener does not have processed_messages attribute")
                    time.sleep(0.1)
                    continue
                
                # Check if message_lock is available
                if not hasattr(self.rt_listener, 'message_lock'):
                    logger.error("[MSG_Q_MGR] RT_Listener does not have message_lock attribute")
                    time.sleep(0.1)
                    continue
                
                # Log the RT_Listener's processed_messages queue size and instance ID
                with self.rt_listener.message_lock:
                    
                    rt_queue_size = len(self.rt_listener.processed_messages) if hasattr(self.rt_listener.processed_messages, '__len__') else None
                    if should_log:
                        logger.info(f"[MSG_Q_MGR] MessageQueueManager checking RT_Listener (id: {id(self.rt_listener)}) processed_messages queue size: {rt_queue_size}")
                    
                    # If queue has messages, log more details
                    if rt_queue_size > 0:
                        logger.info(f"[MSG_Q_MGR] RT_Listener has {rt_queue_size} messages in queue")
                        # Log the first message in the queue without removing it
                        if self.rt_listener.processed_messages:
                            first_message = self.rt_listener.processed_messages[0]
                            logger.info(f"[MSG_Q_MGR] First message in queue: {type(first_message).__name__}")
                            if isinstance(first_message, MIL_STD_1553B_Message):
                                logger.info(f"[MSG_Q_MGR] First message details: rt_address={first_message.rt_address}, sub_address={first_message.sub_address}")
                                if hasattr(first_message, 'message_type'):
                                    logger.info(f"[MSG_Q_MGR] First message type: {first_message.message_type}")
                
                try:
                    # Get message from RT_Listener queue with lock
                    message = None
                    with self.rt_listener.message_lock:
                        if self.rt_listener.processed_messages:
                            message = self.rt_listener.processed_messages.pop(0)
                            self.message_count += 1
                            logger.info(f"[MSG_Q_MGR] MessageQueueManager found message in RT_Listener queue: {type(message).__name__}")
                            
                            # Track message type for interval reporting
                            if isinstance(message, MIL_STD_1553B_Message) and hasattr(message, 'message_type'):
                                msg_type = str(message.message_type)
                                self._interval_message_types[msg_type] = self._interval_message_types.get(msg_type, 0) + 1
                            elif isinstance(message, dict) and 'message_type' in message:
                                msg_type = str(message.get('message_type'))
                                self._interval_message_types[msg_type] = self._interval_message_types.get(msg_type, 0) + 1
                            else:
                                msg_type = type(message).__name__
                                self._interval_message_types[msg_type] = self._interval_message_types.get(msg_type, 0) + 1    #MODE CHANGES COME THROUGH HERE - NOTE TO REMOVE LATER

                            # Log more details about the message
                            if isinstance(message, MIL_STD_1553B_Message):
                                logger.info(f"[MSG_Q_MGR] Message details: rt_address={message.rt_address}, sub_address={message.sub_address}")
                                if hasattr(message, 'message_type'):
                                    logger.info(f"Message type: {message.message_type}")
                                if hasattr(message, 'command_type'):
                                    logger.info(f"Command type: {message.command_type}")
                                if hasattr(message, 'request_id'):
                                    logger.info(f"Request ID: {message.request_id}")
                                if hasattr(message, 'command_name'):
                                    logger.info(f"Command name: {message.command_name}")
                                if hasattr(message, 'data'):
                                    logger.info(f"Data: {message.data}")


                except Exception as e:
                    logger.error(f"[MSG_Q_MGR] Error accessing RT_Listener queue: {e}")
                    logger.error(traceback.format_exc())
                    time.sleep(0.1)  # Sleep on error
                    continue
                
                if message:
                    # Determine destination system(s)
                    try:
                        destinations = self._determine_destinations(message)
                        if should_log or not destinations:
                            logger.info(f"[MSG_Q_MGR] MessageQueueManager determined destinations: {destinations}")
                        
                        # Track destinations for interval reporting
                        for dest in destinations:
                            self._interval_destinations[dest] = self._interval_destinations.get(dest, 0) + 1
                        
                        # Route message to each destination queue
                        for dest in destinations:
                            self._route_to_queue(message, dest)
                            self.route_count += 1
                    except Exception as e:
                        logger.error(f"[MSG_Q_MGR] Error determining destinations or routing message: {e}")
                        logger.error(traceback.format_exc())
                
                # Perform health check periodically
                if (current_time - self.last_health_check) >= self.health_check_interval:
                    self._check_health()
                    self.last_health_check = current_time
                
                # Update log time if needed
                if should_log:
                    self.last_log_time = current_time
                
                time.sleep(0.01)  # Small sleep to prevent tight loop
                
            except Exception as e:
                logger.error(f"[MSG_Q_MGR] Error in MessageQueueManager routing loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(0.1)  # Sleep longer on error
    
    def _log_queue_status(self, force=False):
        """Log the status of all queues with detailed message type information."""
        current_time = time.time()
        if force or (current_time - self.last_log_time) >= self.log_interval:
            # Log queue sizes with explicit locking to ensure accurate counts
            queue_sizes = {}
            for system, queue in self.system_queues.items():
                with self.queue_locks[system]:
                    queue_size = len(queue)
                    # Add detailed information if queue has messages
                    if queue_size > 0 and queue:
                        first_message = queue[0]
                        # Extract command name and message type
                        cmd_name = None
                        msg_type = None
                        
                        if isinstance(first_message, dict):
                            cmd_name = first_message.get('command_name', 'Unknown')
                            msg_type = first_message.get('message_type', 'Unknown')
                        elif hasattr(first_message, 'command_name') and hasattr(first_message, 'message_type'):
                            cmd_name = first_message.command_name
                            msg_type = first_message.message_type
                        
                        # Add details to queue size
                        if cmd_name and msg_type:
                            queue_sizes[system] = f"{queue_size} ({cmd_name}, {msg_type})"
                        else:
                            queue_sizes[system] = queue_size
                    else:
                        queue_sizes[system] = queue_size
            
            logger.info(f"[MSG_Q_MGR] MessageQueueManager queue status: {queue_sizes}")
            
            # Log RT_Listener queue status
            if hasattr(self.rt_listener, 'processed_messages'):
                rt_queue_size = len(self.rt_listener.processed_messages) if hasattr(self.rt_listener.processed_messages, '__len__') else None
                logger.info(f"[MSG_Q_MGR] RT_Listener processed_messages queue size: {rt_queue_size}")
            
            # Log message counts
            new_messages = self.message_count - self._last_message_count
            new_routes = self.route_count - self._last_route_count
            logger.info(f"[MSG_Q_MGR] MessageQueueManager stats: messages processed={self.message_count} (+{new_messages}), messages routed={self.route_count} (+{new_routes})")
            
            # Log message types processed in this interval
            if self._interval_message_types:
                logger.info(f"[MSG_Q_MGR] Message types processed in this interval:")
                for msg_type, count in self._interval_message_types.items():
                    logger.info(f"[MSG_Q_MGR]   - {msg_type}: {count}")
            
            # Log destinations in this interval
            if self._interval_destinations:
                logger.info(f"[MSG_Q_MGR] Message destinations in this interval:")
                for dest, count in self._interval_destinations.items():
                    logger.info(f"[MSG_Q_MGR]   - {dest}: {count}")
            
            # Log recent message history for each queue with enhanced details
            for system, history in self._message_history.items():
                if history:
                    logger.info(f"[MSG_Q_MGR] Recent messages for {system} queue ({len(history)} entries):")
                    for i, entry in enumerate(history[-3:]):  # we want to show all the ones that happened in this interval
                        # Handle both old format (string) and new format (dict)
                        if isinstance(entry, str):
                            # Old format - just log as is
                            logger.info(f"[MSG_Q_MGR]   {i+1}. {entry}")
                            continue
                            
                        # New format - extract detailed information
                        msg_obj = entry.get('message_object')
                        if not msg_obj:
                            # Skip if no message object
                            continue
                            
                        # Build detailed message info
                        msg_info = f"Type: {entry.get('type', 'Unknown')}"
                        
                        # Add command name and message type for better visibility
                        if isinstance(msg_obj, MIL_STD_1553B_Message):
                            if hasattr(msg_obj, 'command_name'):
                                msg_info += f", command_name: {msg_obj.command_name}"
                            if hasattr(msg_obj, 'message_type'):
                                msg_info += f", message_type: {msg_obj.message_type}"
                            if hasattr(msg_obj, 'command_type'):
                                msg_info += f", command_type: {msg_obj.command_type}"
                            if hasattr(msg_obj, 'rt_address'):
                                msg_info += f", rt_address: {msg_obj.rt_address}"
                            if hasattr(msg_obj, 'sub_address'):
                                msg_info += f", sub_address: {msg_obj.sub_address}"
                        elif isinstance(msg_obj, dict):
                            if 'command_name' in msg_obj:
                                msg_info += f", command_name: {msg_obj['command_name']}"
                            if 'message_type' in msg_obj:
                                msg_info += f", message_type: {msg_obj['message_type']}"
                            if 'command_type' in msg_obj:
                                msg_info += f", command_type: {msg_obj['command_type']}"
                            if 'rt_address' in msg_obj:
                                msg_info += f", rt_address: {msg_obj['rt_address']}"
                            if 'sub_address' in msg_obj:
                                msg_info += f", sub_address: {msg_obj['sub_address']}"
                        
                        # Add timestamp
                        msg_info += f", timestamp: {entry.get('timestamp', 'Unknown')}"
                        
                        logger.info(f"[MSG_Q_MGR]   {i+1}. {msg_info}")
            
            # Reset interval counters
            self._last_message_count = self.message_count
            self._last_route_count = self.route_count
            self._interval_message_types = {}
            self._interval_destinations = {}
            self.last_log_time = current_time
    
    def _check_health(self):
        """Check the health of the MessageQueueManager."""
        try:
            # Check RT_Listener
            rt_listener_healthy = hasattr(self.rt_listener, 'processed_messages')
            
            # Check thread status
            thread_healthy = self.thread and self.thread.is_alive()
            
            # Check queue locks
            locks_healthy = all(system in self.queue_locks for system in self.system_queues)
            
            # Log health status
            logger.info(f"[MSG_Q_MGR] MessageQueueManager health check: RT_Listener={rt_listener_healthy}, thread={thread_healthy}, locks={locks_healthy}")
            
            # Check if we're receiving messages
            if self.message_count == 0:
                logger.warning("[MSG_Q_MGR] MessageQueueManager has not processed any messages")
            
            # Check if we're routing messages
            if self.route_count == 0:
                logger.warning("[MSG_Q_MGR] MessageQueueManager has not routed any messages")
                
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error in health check: {e}")
    
    def _determine_destinations(self, message) -> List[str]:
        """Determine which system queues should receive this message using the unified router exclusively."""
        try:
            # Log detailed message information for debugging
            logger.info(f"[MSG_Q_MGR] MessageQueueManager processing message of type: {type(message).__name__}")
            
            # Use the unified router to determine destinations
            try:
                # Import the route resolver from the unified router
                from FMOFP.local_messaging.routing.route_resolver import get_route_resolver
                resolver = get_route_resolver()
                
                # Resolve routes using the unified router's resolver
                destinations = resolver.resolve_routes(message)
                
                if destinations:
                    logger.info(f"[MSG_Q_MGR] Destinations determined by unified router: {destinations}")
                    return destinations
                else:
                    logger.warning(f"[MSG_Q_MGR] No destinations found by unified router")
                    logger.error(f"[MSG_Q_MGR] Message will not be processed - NO FALLBACK TO LEGACY ROUTING")
                    # Do not fall back to legacy routing if unified router fails
                    return []
            except Exception as router_error:
                logger.error(f"[MSG_Q_MGR] Error using unified router: {router_error}")
                logger.error(traceback.format_exc())
                logger.error(f"[MSG_Q_MGR] Message will not be processed - NO FALLBACK TO LEGACY ROUTING")
                # Even in case of exception, do not fall back to legacy routing
                return []
            
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error determining destinations: {e}")
            logger.error(traceback.format_exc())
            # Even in case of exception, do not fall back to legacy routing
            return []
            
    def _legacy_determine_destinations(self, message) -> List[str]:
        """Legacy method to determine destinations (used as fallback only)."""
        try:
            logger.info(f"[MSG_Q_MGR] Using legacy destination determination")
            
            destinations = []
            
            # First check for special cases
            special_case_destinations = self._check_special_case_routing(message)
            if special_case_destinations:
                logger.info(f"[MSG_Q_MGR] Special case routing applied: {special_case_destinations}")
                return special_case_destinations
            
            # Then check RT address-based routing
            rt_destinations = self._route_by_rt_address(message)
            if rt_destinations:
                destinations.extend(rt_destinations)
                
            # Then check content-based routing
            content_destinations = self._route_by_content(message)
            for dest in content_destinations:
                if dest not in destinations:
                    destinations.append(dest)
                    
            if destinations:
                logger.info(f"[MSG_Q_MGR] Legacy destinations determined: {destinations}")
            else:
                logger.warning(f"[MSG_Q_MGR] No destinations found by legacy routing")
                
            return destinations
                
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error in legacy destination determination: {e}")
            logger.error(traceback.format_exc())
            return []
            
    def _check_special_case_routing(self, message) -> List[str]:
        """Check if message requires special case routing."""
        try:
            # Check for VIL data messages
            if self._is_vil_message(message):
                logger.info(f"[MSG_Q_MGR] Detected VIL data message")
                return ['radar', 'display']
                
            # Check for precipitation data messages
            if self._is_precipitation_message(message):
                logger.info(f"[MSG_Q_MGR] Detected precipitation data message")
                return ['radar', 'display']
                
            # Check for mode change messages
            if self._is_mode_change_message(message):
                logger.info(f"[MSG_Q_MGR] Detected mode change message")
                return ['radar', 'display']
                
            return []
            
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error in special case routing: {e}")
            logger.error(traceback.format_exc())
            return []
            
    def _is_vil_message(self, message) -> bool:
        """Check if message is a VIL data message."""
        # Check message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        # VIL message types
        vil_message_types = [
            'weather_radarVILResponse',
            'weather_radarVILRequest',
            'vil_data'
        ]
        
        if message_type and str(message_type) in vil_message_types:
            return True
            
        # Check command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        # VIL command names
        vil_command_names = [
            'radar_vilData',
            'displays_vilData',
            'WEATHER_RADAR_VIL_DATA'
        ]
        
        if command_name and str(command_name) in vil_command_names:
            return True
            
        # Check for VIL data in message
        if isinstance(message, dict) and 'vil_data' in message:
            return True
        elif hasattr(message, 'vil_data'):
            return True
            
        # Check metadata
        metadata = None
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
        elif hasattr(message, 'metadata'):
            metadata = message.metadata
            
        if metadata and isinstance(metadata, dict) and 'vil_data' in metadata:
            return True
            
        return False
        
    def _is_precipitation_message(self, message) -> bool:
        """Check if message is a precipitation data message."""
        # Check message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        # Precipitation message types
        precip_message_types = [
            'weather_radarPrecipitationResponse',
            'weather_radarPrecipitationRequest',
            'precipitation_data'
        ]
        
        if message_type and str(message_type) in precip_message_types:
            return True
            
        # Check command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        # Precipitation command names
        precip_command_names = [
            'radar_precipitationData',
            'displays_precipitationData',
            'WEATHER_RADAR_PRECIPITATION_DATA'
        ]
        
        if command_name and str(command_name) in precip_command_names:
            return True
            
        # Check for precipitation data in message
        if isinstance(message, dict) and 'precipitation_data' in message:
            return True
        elif hasattr(message, 'precipitation_data'):
            return True
            
        # Check metadata
        metadata = None
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
        elif hasattr(message, 'metadata'):
            metadata = message.metadata
            
        if metadata and isinstance(metadata, dict) and 'precipitation_message' in metadata:
            return True
            
        return False
        
    def _is_mode_change_message(self, message) -> bool:
        """Check if message is a mode change message."""
        # Check message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        # Mode change message types
        mode_message_types = [
            'weather_radarModeChangeRequest',
            'weather_radarModeChangeResponse',
            'display_mode_request',
            'mode_change',
            'mode_change_completion'
        ]
        
        if message_type and any(mode_type in str(message_type) for mode_type in ['mode', 'Mode']):
            return True
            
        # Check command type
        command_type = None
        if isinstance(message, dict):
            command_type = message.get('command_type')
        elif hasattr(message, 'command_type'):
            command_type = message.command_type
            
        if command_type and any(mode_type in str(command_type) for mode_type in ['mode', 'Mode']):
            return True
            
        # Check command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        # Mode change command names
        mode_command_names = [
            'radar_modeChange',
            'displays_modeChange',
            'WEATHER_RADAR_MODE_CHANGE',
            'DISPLAY_MODE_CHANGE'
        ]
        
        if command_name and any(mode_name in str(command_name) for mode_name in ['MODE', 'Mode', 'mode']):
            return True
            
        return False
        
    def _route_by_rt_address(self, message) -> List[str]:
        """Route message based on RT address."""
        destinations = []
        
        # Get RT address
        rt_address = None
        if isinstance(message, dict):
            rt_address = message.get('rt_address')
        elif hasattr(message, 'rt_address'):
            rt_address = message.rt_address
            
        if rt_address is None:
            return destinations
            
        # Get radar address
        radar_address = self.get_radar_address()
        
        # Get display address
        display_address = self.get_display_address()
        
        # Route based on RT address
        if rt_address == radar_address or rt_address == 9:
            destinations.append('radar')
            logger.info(f"[MSG_Q_MGR] Message with RT address {rt_address} matches radar address {radar_address}")
            
        if rt_address == display_address or rt_address == 11:
            destinations.append('display')
            logger.info(f"[MSG_Q_MGR] Message with RT address {rt_address} matches display address {display_address}")
            
        return destinations
        
    def _route_by_content(self, message) -> List[str]:
        """Route message based on content."""
        destinations = []
        
        # Check message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        if message_type:
            # Check for radar indicators
            if 'radar' in str(message_type).lower():
                if 'radar' not in destinations:
                    destinations.append('radar')
                    
            # Check for display indicators
            if 'display' in str(message_type).lower():
                if 'display' not in destinations:
                    destinations.append('display')
                    
        # Check command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        if command_name:
            # Check for radar indicators
            if 'RADAR' in str(command_name):
                if 'radar' not in destinations:
                    destinations.append('radar')
                    
            # Check for display indicators
            if 'DISPLAY' in str(command_name):
                if 'display' not in destinations:
                    destinations.append('display')
                    
        # Check status word for RT address
        status_word = None
        if isinstance(message, dict):
            status_word = message.get('status_word')
        elif hasattr(message, 'status_word'):
            status_word = message.status_word
            
        if status_word and isinstance(status_word, dict):
            rt_address = status_word.get('rt_address')
            if rt_address == 9:
                if 'radar' not in destinations:
                    destinations.append('radar')
            elif rt_address == 11:
                if 'display' not in destinations:
                    destinations.append('display')
                    
        return destinations
        
    def _route_to_queue(self, message, destination):
        """Route a message to the specified destination queue."""
        try:
            if destination not in self.system_queues:
                logger.error(f"Unknown destination queue: {destination}")
                return
            
            # Create a copy of the message to prevent shared references
            message_copy = copy.deepcopy(message)
            
            # Add routing metadata
            if isinstance(message_copy, dict) and 'metadata' not in message_copy:
                message_copy['metadata'] = {}
            if isinstance(message_copy, dict):
                message_copy['metadata'] = message_copy.get('metadata', {})
                
                # Check if this system has already processed this message
                processed_systems = message_copy['metadata'].get('processed_by', [])
                if destination in processed_systems:
                    logger.info(f"[MSG_Q_MGR] Message already processed by {destination}, skipping")
                    return
                
                # Add this system to the processed list
                processed_systems.append(destination)
                message_copy['metadata']['processed_by'] = processed_systems
                message_copy['metadata']['routed_to'] = destination
                message_copy['metadata']['routing_timestamp'] = time.time()
            elif hasattr(message_copy, 'metadata'):
                message_copy.metadata = getattr(message_copy, 'metadata', {})
                
                # Check if this system has already processed this message
                processed_systems = message_copy.metadata.get('processed_by', [])
                if destination in processed_systems:
                    logger.info(f"[MSG_Q_MGR] Message already processed by {destination}, skipping")
                    return
                
                # Add this system to the processed list
                processed_systems.append(destination)
                message_copy.metadata['processed_by'] = processed_systems
                message_copy.metadata['routed_to'] = destination
                message_copy.metadata['routing_timestamp'] = time.time()
            else:
                # Add metadata attribute if it doesn't exist
                processed_systems = []
                processed_systems.append(destination)
                setattr(message_copy, 'metadata', {
                    'processed_by': processed_systems,
                    'routed_to': destination,
                    'routing_timestamp': time.time()
                })
            
            if isinstance(message_copy, MIL_STD_1553B_Message):
                request_id = message_copy.request_id
            elif isinstance(message_copy, dict):
                request_id = message_copy.get('request_id')
            else:
                raise ValueError("[MSG_Q_MGR] No request ID found in message")

            try:
                with self.queue_locks[destination]:
                    # Add to queue
                    self.system_queues[destination].append(message_copy)
                    queue_size = len(self.system_queues[destination])
                    logger.info(f"[MSG_Q_MGR] Routed message to {destination} queue, queue size: {queue_size}")
                    
                    # Clear existing history to ensure all entries are in the new format
                    self._message_history[destination] = []
                    
                    # Store the complete message object in history for better details
                    history_entry = {
                        'type': type(message_copy).__name__,
                        'message_object': message_copy,
                        'timestamp': time.time()
                    }
                    
                    # Add to history
                    self._message_history[destination].append(history_entry)
                    
                    # Trim history if needed
                    if len(self._message_history[destination]) > self._message_history_max_size:
                        self._message_history[destination] = self._message_history[destination][-self._message_history_max_size:]
                    
                # Log message details
                if isinstance(message_copy, MIL_STD_1553B_Message):
                    logger.info(f"[MSG_Q_MGR] Routed MIL_STD_1553B_Message: rt_address={message_copy.rt_address}, sub_address={message_copy.sub_address}")
                    if hasattr(message_copy, 'message_type'):
                        logger.info(f"[MSG_Q_MGR] Routed message type: {message_copy.message_type}")
                    if hasattr(message_copy, 'command_type'):
                        logger.info(f"[MSG_Q_MGR] Routed command type: {message_copy.command_type}")
                    if hasattr(message_copy, 'command_name'):
                        logger.info(f"[MSG_Q_MGR] Routed command name: {message_copy.command_name}")
                    
                    # Enhanced logging for data field
                    if hasattr(message_copy, 'data'):
                        data_type = type(message_copy.data).__name__
                        data_length = len(message_copy.data) if hasattr(message_copy.data, '__len__') else 'N/A'
                        logger.debug(f"[PRECIPITATION_DEBUG] Message has data of type {data_type}, length {data_length}")
                        
                        # Check for precipitation data
                        if hasattr(message_copy, 'command_type') and 'precipitation' in str(message_copy.command_type).lower():
                            logger.debug(f"[PRECIPITATION_DEBUG] Precipitation message has data: {message_copy.data}")
                    
                    if destination == 'display':
                        logger.info(f"[MSG_Q_MGR] *** DISPLAY QUEUE *** Message added to display queue: rt_address={message_copy.rt_address}, sub_address={message_copy.sub_address}, command_type={message_copy.command_type}")
                        
                        # Detailed logging for precipitation messages to display
                        if hasattr(message_copy, 'command_type') and 'precipitation' in str(message_copy.command_type).lower():
                            logger.debug(f"[PRECIPITATION_DEBUG] Added precipitation message to DISPLAY queue with data: {message_copy.data if hasattr(message_copy, 'data') else 'NO DATA'}")
                            
                            # Check metadata for binary encoding flags
                            if hasattr(message_copy, 'metadata') and isinstance(message_copy.metadata, dict):
                                binary_flag = message_copy.metadata.get('binary_encoded', False)
                                logger.debug(f"[PRECIPITATION_DEBUG] Message has binary_encoded={binary_flag}")
                            
                elif isinstance(message_copy, dict):
                    logger.info(f"[MSG_Q_MGR] Routed dict message: rt_address={message_copy.get('rt_address')}, type={message_copy.get('message_type')}, command_type={message_copy.get('command_type')}")
                    
                    # Enhanced logging for data field
                    if 'data' in message_copy:
                        data_type = type(message_copy['data']).__name__
                        data_length = len(message_copy['data']) if hasattr(message_copy['data'], '__len__') else 'N/A'
                        logger.debug(f"[PRECIPITATION_DEBUG] Dict message has data of type {data_type}, length {data_length}")
                        
                        # Check for precipitation data
                        if message_copy.get('command_type') and 'precipitation' in str(message_copy.get('command_type')).lower():
                            logger.debug(f"[PRECIPITATION_DEBUG] Precipitation dict message has data: {message_copy['data']}")
                    
                    if destination == 'display':
                        logger.info(f"[MSG_Q_MGR] *** DISPLAY QUEUE *** Dict message added to display queue: rt_address={message_copy.get('rt_address')}, type={message_copy.get('message_type')}, command_type={message_copy.get('command_type')}")
                        
                        # Detailed logging for precipitation messages to display
                        if message_copy.get('command_type') and 'precipitation' in str(message_copy.get('command_type')).lower():
                            logger.debug(f"[PRECIPITATION_DEBUG] Added precipitation dict message to DISPLAY queue with data: {message_copy.get('data', 'NO DATA')}")
            except Exception as e:
                logger.error(f"[MSG_Q_MGR] Error acquiring lock for {destination} queue: {e}")
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error routing message to {destination}: {e}")
            logger.error(traceback.format_exc())
    
    def get_message(self, system):
        """Get a message from the specified system queue."""
        try:
            if system not in self.system_queues:
                logger.error(f"[MSG_Q_MGR] Unknown system queue: {system}")
                return None
            
            try:
                with self.queue_locks[system]:
                    if self.system_queues[system]:
                        message = self.system_queues[system].popleft()
                        queue_size = len(self.system_queues[system])
                        logger.info(f"[MSG_Q_MGR] Retrieved message from {system} queue, remaining: {queue_size}")
                        
                        # Log message details
                        if isinstance(message, MIL_STD_1553B_Message):
                            logger.info(f"[MSG_Q_MGR] Retrieved MIL_STD_1553B_Message: rt_address={message.rt_address}, sub_address={message.sub_address}")
                        elif isinstance(message, dict):
                            logger.info(f"[MSG_Q_MGR] Retrieved dict message: rt_address={message.get('rt_address')}, type={message.get('message_type')}")
                        
                        # Return a tuple of (system, message) instead of just the message
                        # Ensure the message is a dictionary to avoid type errors
                        if not isinstance(message, dict) and hasattr(message, '__dict__'):
                            # Import copy for deep copying nested structures
                            import copy
                            
                            # Start with a deep copy of __dict__ to handle nested structures
                            message_dict = copy.deepcopy(message.__dict__)
                            
                            # List of critical fields that must be preserved
                            critical_fields = [
                                'request_id', 'command_name', 'message_type', 'command_type',
                                'rt_address', 'sub_address', 'data'
                            ]
                            
                            # Explicitly preserve critical fields
                            for field in critical_fields:
                                if hasattr(message, field) and getattr(message, field) is not None:
                                    message_dict[field] = getattr(message, field)
                            
                            # Ensure metadata is properly preserved
                            if hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                                if 'metadata' not in message_dict or message_dict['metadata'] is None:
                                    message_dict['metadata'] = {}
                                
                                # Deep copy metadata to ensure all nested structures are preserved
                                message_dict['metadata'] = copy.deepcopy(message.metadata)
                                
                                # Extract ALL critical fields from metadata as a fallback
                                critical_fields = [
                                    'request_id', 'command_name', 'message_type', 'command_type',
                                    'rt_address', 'sub_address', 'data', 'destination'
                                ]
                                
                                for field in critical_fields:
                                    if field in message.metadata and (field not in message_dict or message_dict[field] is None):
                                        message_dict[field] = message.metadata[field]
                                        logger.info(f"[MSG_Q_MGR] Extracted {field} from metadata: {message_dict[field]}")
                                
                                # Ensure metadata is included in the output dictionary regardless
                                if 'metadata' not in message_dict:
                                    message_dict['metadata'] = {}
                                
                                # Copy metadata to ensure it's preserved
                                message_dict['metadata'] = copy.deepcopy(message.metadata)
                            
                            # Preserve any remaining attributes that might be properties
                            for attr in dir(message):
                                if not attr.startswith('_') and not callable(getattr(message, attr)) and attr not in message_dict:
                                    message_dict[attr] = getattr(message, attr)
                            
                            # Log detailed information about the conversion with all critical fields
                            logger.info(f"[MSG_Q_MGR] Converted {type(message).__name__} to dictionary for {system}")
                            logger.info(f"[MSG_Q_MGR] Preserved fields - request_id: {message_dict.get('request_id')}, command_name: {message_dict.get('command_name')}")
                            
                            # Add final verification for critical fields
                            if not message_dict.get('request_id'):
                                logger.warning(f"[MSG_Q_MGR] Critical field 'request_id' is missing or None after conversion!")
                            if not message_dict.get('command_name'):
                                logger.warning(f"[MSG_Q_MGR] Critical field 'command_name' is missing or None after conversion!")
                            if isinstance(message_dict['metadata'], dict) and 'command_name' in message_dict['metadata']:
                                # If command_name is in metadata, use it
                                if 'command_name' not in message_dict:
                                    message_dict['command_name'] = message_dict['metadata']['command_name']
                                # Determine command_name by command_type and message_type in metadata
                            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                                command_Type = message_dict['metadata'].get('command_type')
                                message_Type = message_dict['metadata'].get('message_type')

                                if command_Type and message_Type:
                                    if command_Type == 'show':
                                        if message_Type == 'weather_radarPrecipitationRequest':
                                            message_dict['command_name'] = 'WEATHER_RADAR_PRECIPITATION_REQUEST'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'weather_radarPrecipitationRequest'
                                        elif message_Type == 'weather_radarPrecipitationResponse':
                                            message_dict['command_name'] = 'WEATHER_RADAR_PRECIPITATION_RESPONSE'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'weather_radarPrecipitationResponse'
                                        elif message_Type == 'weather_radarVILRequest':
                                            message_dict['command_name'] = 'WEATHER_RADAR_VIL_REQUEST'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'weather_radarVILRequest'
                                        elif message_Type == 'weather_radarVILResponse':
                                            message_dict['command_name'] = 'WEATHER_RADAR_VIL_RESPONSE'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'weather_radarVILResponse'
                                        elif message_Type == 'vil_data':
                                            message_dict['command_name'] = 'VIL_DATA'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'vil_data'
                                        elif message_Type == 'precipitation_data':
                                            message_dict['command_name'] = 'PRECIPITATION_DATA'
                                            message_dict['command_type'] = 'data'
                                            message_dict['message_type'] = 'precipitation_data'
                                        
                                        else:
                                            raise ValueError(f"[MSG_Q_MGR] command name was not determined by command type {command_Type} and message type {message_Type}")
                                # If not in metadata, try to infer from message type
                                elif message_dict.get('message_type') and 'radarMode' in message_dict.get('message_type', ''):
                                    logger.warning(f"[MSG_Q_MGR] Inferring command_name for mode change message")
                                    # Extract radar type from message_type (e.g., weather_radarModeChangeCompletion -> WEATHER_RADAR)
                                    if 'weather' in message_dict.get('message_type', '').lower():
                                        message_dict['command_name'] = 'WEATHER_RADAR_MODE_CHANGE_COMPLETION'
                                        logger.info(f"[MSG_Q_MGR] Added command_name: {message_dict['command_name']}")
                                    elif 'tfr' in message_dict.get('message_type', '').lower():
                                        message_dict['command_name'] = 'TFR_RADAR_MODE_CHANGE_COMPLETION'
                                        logger.info(f"[MSG_Q_MGR] Added command_name: {message_dict['command_name']}")
                                    elif 'sar' in message_dict.get('message_type', '').lower():
                                        message_dict['command_name'] = 'SAR_RADAR_MODE_CHANGE_COMPLETION'
                                        logger.info(f"[MSG_Q_MGR] Added command_name: {message_dict['command_name']}")
                                    elif 'target' in message_dict.get('message_type', '').lower():
                                        message_dict['command_name'] = 'TARGETING_RADAR_MODE_CHANGE_COMPLETION'
                                        logger.info(f"[MSG_Q_MGR] Added command_name: {message_dict['command_name']}")
                            
                            return (system, message_dict)
                        return (system, message)
            except Exception as e:
                logger.error(f"[MSG_Q_MGR] Error acquiring lock for {system} queue: {e}")
                logger.error(traceback.format_exc())
            
            return None
        except Exception as e:
            logger.error(f"[MSG_Q_MGR] Error getting message from {system} queue: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def get_queue_size(self, system):
        """Get the current size of the specified system queue."""
        if system not in self.system_queues:
            logger.error(f"[MSG_Q_MGR] Unknown system queue: {system}")
            return 0
        
        with self.queue_locks[system]:
            return len(self.system_queues[system])

    def add_system_queue(self, system):
        """Add a new system queue if it doesn't already exist."""
        with self.__class__._lock:
            if system in self.system_queues:
                logger.info(f"[MSG_Q_MGR] System queue '{system}' already exists")
                return True
            
            # Add new queue and lock
            self.system_queues[system] = deque()
            self.queue_locks[system] = threading.Lock()
            self._message_history[system] = []
            
            logger.info(f"[MSG_Q_MGR] Added new system queue: {system}")
            return True

# Global instance with thread-safe initialization
_message_queue_manager = None
_manager_lock = threading.Lock()

def get_message_queue_manager():
    """Get the global MessageQueueManager instance."""
    global _message_queue_manager
    with _manager_lock:
        if _message_queue_manager is None:
            _message_queue_manager = MessageQueueManager()
            logger.info("[MSG_Q_MGR] Global MessageQueueManager instance created")
        return _message_queue_manager
