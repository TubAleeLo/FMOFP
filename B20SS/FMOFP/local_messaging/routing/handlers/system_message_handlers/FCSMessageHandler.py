"""
FCS Message Handler

Handles LOCAL Flight Control System-related messages using the 1553B messaging system.
Manages communication between the main system and the flight control system.
"""
import asyncio
import sys
import time
import uuid
import traceback
import threading
from typing import Dict, Any, Optional, List, Tuple, Union
import xml.etree.ElementTree as ET
from FMOFP.local_messaging.routing.handlers.sync_handler.AsyncMessageHandler import AsyncMessageHandler
from FMOFP.core.event_driven_communication import get_event_bus
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.message_types_fcs import (
    FCS_CONTROL_INPUT_REQUEST,
    FCS_CONTROL_INPUT_RESPONSE,
    FCS_ORIENTATION_DATA_REQUEST,
    FCS_ORIENTATION_DATA_RESPONSE,
    FCS_STATUS_REQUEST,
    FCS_STATUS_RESPONSE,
    FCS_MODE_CHANGE_REQUEST,
    FCS_MODE_CHANGE_RESPONSE
)
# Import message loop prevention middleware
from FMOFP.Utils.message_loop_prevention.middleware import get_loop_prevention_middleware, MessageLoopPreventionMiddleware
# Import 1553B messaging components
from FMOFP.MIL_STD_1553B.Messaging import send1553Msg
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
from FMOFP.local_messaging.command_word_map_fcs import FCS_COMMAND_WORDS, get_fcs_command_word
from FMOFP.local_messaging.command_word_map import register_command_word, validate_command_word

logger = get_logger()

# Import command word maps from main module
from FMOFP.local_messaging.command_word_map import (
    MODE_REQUEST_MAP, STATUS_REQUEST_MAP, DATA_REQUEST_MAP
)

class PendingRequest:
    """Class to track pending requests to the FCS"""
    def __init__(self, request_id: str, command_type: str, timestamp: float, timeout: float = 5.0):
        self.request_id = request_id
        self.command_type = command_type
        self.timestamp = timestamp
        self.timeout = timeout
        self.retry_count = 0
        self.max_retries = 3
        self.response = None
        self.error = None
        self.completed = False
        
    def is_expired(self) -> bool:
        """Check if request has expired"""
        return time.time() > self.timestamp + self.timeout
        
    def should_retry(self) -> bool:
        """Check if request should be retried"""
        return not self.completed and self.retry_count < self.max_retries
        
    def increment_retry(self) -> int:
        """Increment retry count and return new count"""
        self.retry_count += 1
        return self.retry_count
        
    def set_error_state(self, error: str) -> None:
        """Set error state"""
        self.error = error
        self.completed = True
        
    def set_response(self, response: Dict[str, Any]) -> None:
        """Set response data"""
        self.response = response
        self.completed = True

class FCSMessageHandler:
    """
    Message handler for the Flight Control System
    
    Processes incoming messages and routes them to the appropriate
    components of the Flight Control System.
    """
    def __init__(self):
        self.async_handler = None
        self.response_service = None
        self.fcs_db = None
        self.lock = threading.Lock()
        self.started = False
        self.pending_requests = {}  # request_id -> PendingRequest
        self.cleanup_timer = None
        self.logger = logger.logger  # Direct access to logger
        self.event_bus = get_event_bus()
        
        # Initialize 1553B messaging components
        self.sendMsg = send1553Msg()
        self.bc_construct = BC_construct()
        
        # Initialize loop prevention middleware
        try:
            self.loop_prevention = get_loop_prevention_middleware()
            
            # Register FCS-specific message categories for loop prevention
            if self.loop_prevention:
                self._register_fcs_loop_prevention_categories()
                logger.info("FCS Message Handler integrated with enhanced loop prevention middleware")
            else:
                # Create a new middleware instance if global one not available
                self.loop_prevention = MessageLoopPreventionMiddleware()
                self._register_fcs_loop_prevention_categories()
                logger.info("Created dedicated FCS loop prevention middleware")
        except Exception as e:
            logger.error(f"Failed to initialize loop prevention middleware: {e}")
            self.loop_prevention = None
            
        # Import FCS components here to avoid circular imports
        from FMOFP.Systems.flightManagementSys.flightControlSys.flight_control_system import get_flight_control_system
        
        # Import the FCS command word mapping to ensure it's registered
        from FMOFP.local_messaging.command_word_map_fcs import register_fcs_command_words
        
        # Ensure FCS command words are registered
        register_fcs_command_words()
        
        self.fcs = get_flight_control_system()
            
    def _register_fcs_loop_prevention_categories(self):
        """Register FCS-specific message categories for loop prevention"""
        if not self.loop_prevention:
            return
            
        # Check if the middleware supports category registration
        if not hasattr(self.loop_prevention, 'register_category'):
            logger.warning("Loop prevention middleware does not support category registration - using default logic")
            return
            
        try:
            # Register message categories for FCS-specific message types
            categories = {
                'fcs_orientation': {'type': 'FCS data', 'priority': 'high', 'max_processing': 1},
                'fcs_control_input': {'type': 'FCS control', 'priority': 'highest', 'max_processing': 1},
                'fcs_status': {'type': 'FCS status', 'priority': 'medium', 'max_processing': 1},
                'fcs_mode': {'type': 'FCS control', 'priority': 'highest', 'max_processing': 1},
                'fcs_command': {'type': 'FCS control', 'priority': 'highest', 'max_processing': 1}
            }
            
            for category, settings in categories.items():
                self.loop_prevention.register_category(
                    category,
                    category_type=settings['type'],
                    priority=settings['priority'],
                    max_simultaneous_processing=settings['max_processing']
                )
                
            logger.info(f"Registered {len(categories)} FCS-specific categories with loop prevention middleware")
        except Exception as e:
            logger.error(f"Failed to register FCS categories with loop prevention middleware: {e}")
        
    async def send_request(self, system_name: str, request_type: str, data: Any = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Send a request to the FCS system.
        
        Args:
            system_name (str): Target system name (usually "flight_control_system")
            request_type (str): Type of request ("mode_change", "control_input", etc.)
            data (Any): Request data (mode name for mode_change, parameters for other types)
            metadata (dict): Optional metadata for request tracking
            
        Returns:
            str: Request ID for tracking and response correlation
        """
        logger.info(f"[FCS_MSGR] Sending {request_type} request to {system_name}")
        
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Initialize metadata if not provided
        if metadata is None:
            metadata = {}
        
        # Add request ID to metadata for tracing
        metadata["request_id"] = request_id
        metadata["timestamp"] = timestamp
        
        # Store pending request for tracking and timeout management
        pending_request = PendingRequest(
            request_id=request_id,
            command_type=request_type,
            timestamp=timestamp
        )
        self.pending_requests[request_id] = pending_request
        
        try:
            # Determine appropriate command word and data words based on request type
            command_word = None
            data_words = []
            msg_type = None
            
            if request_type == "mode_change":
                # Get appropriate command word from FCS_COMMAND_WORDS
                cmd_word_obj = get_fcs_command_word(FCS_MODE_CHANGE_REQUEST)
                if cmd_word_obj:
                    command_word = format(cmd_word_obj.value, '016b')
                else:
                    logger.error(f"[FCS_MSGR] No mode change command word found")
                    return None
                    
                # Pack mode data into binary format
                data_words = self._pack_mode_data(data)
                msg_type = "flight_control_systemCommand"
                logger.info(f"[FCS_MSGR] Using command word {command_word} for mode change to {data}")
                
            elif request_type == "status":
                # Get appropriate command word from FCS_COMMAND_WORDS
                cmd_word_obj = get_fcs_command_word(FCS_STATUS_REQUEST)
                if cmd_word_obj:
                    command_word = format(cmd_word_obj.value, '016b')
                else:
                    logger.error(f"[FCS_MSGR] No status request command word found")
                    return None
                    
                msg_type = "flight_control_systemStatusRequest"
                logger.info(f"[FCS_MSGR] Using command word {command_word} for status request")
                
            elif request_type == "control_input":
                # Get appropriate command word from FCS_COMMAND_WORDS
                cmd_word_obj = get_fcs_command_word(FCS_CONTROL_INPUT_REQUEST)
                if cmd_word_obj:
                    command_word = format(cmd_word_obj.value, '016b')
                else:
                    logger.error(f"[FCS_MSGR] No control input command word found")
                    return None
                    
                # Pack control input data into data words
                data_words = self._pack_control_input_data(data)
                msg_type = "flight_control_systemControlInputRequest"
                logger.info(f"[FCS_MSGR] Using command word {command_word} for control input")
                
            elif request_type == "orientation_data":
                # Get appropriate command word from FCS_COMMAND_WORDS
                cmd_word_obj = get_fcs_command_word(FCS_ORIENTATION_DATA_REQUEST)
                if cmd_word_obj:
                    command_word = format(cmd_word_obj.value, '016b')
                else:
                    logger.error(f"[FCS_MSGR] No orientation data command word found")
                    return None
                    
                msg_type = "flight_control_systemOrientationDataRequest"
                logger.info(f"[FCS_MSGR] Using command word {command_word} for orientation data request")
                
            else:
                logger.error(f"[FCS_MSGR] Unknown request type: {request_type}")
                return None
            
            # Create appropriate metadata for 1553B message
            msg_metadata = {
                'message_header': request_type,
                'command_name': f"FCS_{request_type.upper()}",
                'command_type': request_type,
                'message_type': msg_type,
                'sending_system': "FCSMessageHandler",
                'destination': system_name,
                'request_id': request_id
            }
            
            # Update with user-provided metadata
            if metadata:
                msg_metadata.update(metadata)
                
            # Send message through 1553B bus
            logger.info(f"[FCS_MSGR] Sending 1553B message: cmd={command_word}, data={data_words}")
            result = await self.sendMsg.send_message(command_word, data_words, request_id, msg_metadata)
            
            if result is None:
                logger.error("[FCS_MSGR] Failed to send message through 1553B")
                del self.pending_requests[request_id]
                return None
                
            logger.info("[FCS_MSGR] Successfully sent message through 1553B")
            return request_id
            
        except Exception as e:
            logger.error(f"[FCS_MSGR] Error sending request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Clean up pending request on error
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
                
            return None
            
    def _pack_mode_data(self, data: Any) -> list:
        """Pack FCS mode data into binary format for message transmission."""
        mode_value = None
        mode_name = None
        
        # Extract mode name from data based on its type
        if isinstance(data, dict) and 'mode_name' in data:
            mode_name = data['mode_name']
            logger.info(f"[FCS_MSGR] Mode name extracted from dictionary: {mode_name}")
        elif hasattr(data, 'value'):
            mode_value = data.value
            mode_name = data.name if hasattr(data, 'name') else str(data.value)
            logger.info(f"[FCS_MSGR] Mode value found from enum: {mode_name} {mode_value}")
        elif isinstance(data, str):
            mode_name = data
            logger.info(f"[FCS_MSGR] Mode name as string: {mode_name}")
        
            # Map mode name to value - aligned with address_book.xml and FMSMessageHandler
            if mode_value is None:
                # Map string mode to value based on standardized mode values
                mode_map = {
                    "NORMAL": 0,     # Aligned with FMSMessageHandler
                    "COMBAT": 1,     # Aligned with FMSMessageHandler
                    "PRECISION": 2,  # Aligned with FMSMessageHandler
                    "AUTOPILOT": 3,  # Aligned with FMSMessageHandler
                    "TERRAIN": 4,    # Aligned with FMSMessageHandler
                    "EMERGENCY": 5,  # Aligned with FMSMessageHandler
                    "STANDBY": 0     # Treated as NORMAL
                }
                if mode_name:
                    mode_value = mode_map.get(mode_name.upper(), 0)
                    logger.info(f"[FCS_MSGR] Mapped mode {mode_name} to value: {mode_value}")
                else:
                    # Default to NORMAL mode value as fallback
                    mode_value = 0  # NORMAL mode
                    logger.info(f"[FCS_MSGR] Using default mode value: {mode_value}")
            
        # Format as 16-bit binary string
        return [format(mode_value, '016b')]
        
    def _pack_control_input_data(self, data: Any) -> list:
        """Pack control input data into binary format for message transmission."""
        # Extract control surface and value information
        control_type = None
        control_value = 0.0
        
        if isinstance(data, dict):
            control_type = data.get('control_type')
            control_value = data.get('value', 0.0)
        
        if not control_type:
            logger.error("[FCS_MSGR] Missing control_type in control input data")
            return [format(0, '016b'), format(0, '016b')]
        
        # Map control type to code
        control_map = {
            "aileron": 1,
            "elevator": 2,
            "rudder": 3,
            "throttle": 4,
            "flaps": 5,
            "speedbrake": 6,
            "gear": 7
        }
        
        control_code = control_map.get(control_type.lower(), 0)
        
        # Scale control value from float [-1.0, 1.0] to int [0, 1000]
        # Center point is 500 (0.0), full negative is 0 (-1.0), full positive is 1000 (1.0)
        scaled_value = int((control_value + 1.0) * 500)
        scaled_value = max(0, min(1000, scaled_value))  # Clamp to valid range
        
        # Pack into data words
        return [format(control_code, '016b'), format(scaled_value, '016b')]
        
    def set_async_handler(self, async_handler):
        """Set the async message handler"""
        self.async_handler = async_handler
        self._register_message_handlers()
        logger.info("FCS Message Handler connected to async handler")
        
    def set_response_service(self, response_service):
        """Set the response service"""
        self.response_service = response_service
        logger.info("FCS Message Handler connected to response service")
        
    def _register_message_handlers(self):
        """Register message handlers with the async handler"""
        if not self.async_handler:
            logger.warning("Cannot register FCS message handlers - async handler not set")
            return
            
        # Register the FCS system with the async handler first
        fcs_system = self.async_handler.register_system("flight_control_system")
        
        # Register handlers for various FCS message types with command words from FCS_COMMAND_WORDS
        # Map handlers to command words
        command_handlers = {
            FCS_MODE_CHANGE_REQUEST: self._handle_mode_change_request,
            FCS_MODE_CHANGE_RESPONSE: self._handle_mode_change_response,
            FCS_CONTROL_INPUT_REQUEST: self._handle_control_input_request,
            FCS_CONTROL_INPUT_RESPONSE: self._handle_control_input_response,
            FCS_ORIENTATION_DATA_REQUEST: self._handle_orientation_data_request,
            FCS_ORIENTATION_DATA_RESPONSE: self._handle_orientation_data_response,
            FCS_STATUS_REQUEST: self._handle_status_request,
            FCS_STATUS_RESPONSE: self._handle_status_response
        }
        
        # Register each handler with the appropriate command word
        for command_name, handler in command_handlers.items():
            try:
                cmd_word_obj = get_fcs_command_word(command_name)
                if cmd_word_obj:
                    command_word = format(cmd_word_obj.value, '016b')  # Convert to binary string
                    fcs_system.register_handler(command_word, handler)
                    logger.info(f"Registered handler for {command_name} with command word {command_word}")
                else:
                    logger.warning(f"Command name {command_name} not found in FCS_COMMAND_WORDS")
            except Exception as e:
                logger.error(f"Error registering handler for {command_name}: {e}")
        
        logger.info("FCS message handlers registered")
        
    async def _handle_mode_change_request(self, message):
        """
        Handle FCS mode change request
        
        Args:
            message: The mode change request
            
        Returns:
            dict: Mode change result
        """
        try:
            # Check for message loops if middleware is available
            if self.loop_prevention:
                transaction_id = self._create_transaction_id(message, "mode_change")
                should_process, enhanced_message = self.loop_prevention.process_message(
                    message, 
                    "fcs_mode_handler",
                    transaction_id=transaction_id,
                    category="fcs_mode"
                )
                if not should_process:
                    logger.warning(f"Breaking loop - FCS mode change message already processed")
                    return {"status": "SKIPPED", "message": "Message loop detected"}
                    
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
                
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid mode change message format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            # Extract mode value from the binary data word
            try:
                mode_value = None
                if 'data' in message and isinstance(message['data'], str):
                    # Data is a binary string
                    mode_value = int(message['data'], 2)
                    logger.info(f"[FCS] Extracted mode value from binary data: {mode_value}")
                elif 'parameters' in message and 'mode_name' in message['parameters']:
                    # Data is in parameters dictionary
                    mode_name = message['parameters']['mode_name']
                    # Align mode map with the one in _pack_mode_data and in address_book.xml
                    mode_map = {
                        "NORMAL": 0,     # Aligned with FMSMessageHandler and address_book.xml
                        "COMBAT": 1,     # Aligned with FMSMessageHandler and address_book.xml
                        "PRECISION": 2,  # Aligned with FMSMessageHandler and address_book.xml
                        "AUTOPILOT": 3,  # Aligned with FMSMessageHandler and address_book.xml
                        "TERRAIN": 4,    # Aligned with FMSMessageHandler and address_book.xml
                        "EMERGENCY": 5,  # Aligned with FMSMessageHandler and address_book.xml
                        "STANDBY": 0     # Treated as NORMAL
                    }
                    mode_value = mode_map.get(mode_name.upper(), 0)
                    logger.info(f"[FCS] Extracted mode value from parameters: {mode_value} ({mode_name})")
                else:
                    logger.warning("[FCS] No mode value found in message")
                    return {"status": "ERROR", "message": "No mode value specified"}
            except Exception as e:
                logger.error(f"[FCS] Error extracting mode value: {e}")
                return {"status": "ERROR", "message": f"Error extracting mode value: {str(e)}"}
                
            request_id = message.get('request_id', None)
            
            logger.info(f"[FCS] Handling mode change request with mode value: {mode_value} (request_id: {request_id})")
            
            # Process mode change through FCS
            if self.fcs:
                old_mode = self.fcs.mode
                result = self.fcs.change_mode(mode_value)
                new_mode = self.fcs.mode
                
                success = result.get('success', False)
                
                # Create response - format depends on what process_command returns
                response = {
                    "status": "SUCCESS" if success else "ERROR",
                    "message": result.get('message', ''),
                    "request_id": request_id,
                    "old_mode": old_mode,
                    "new_mode": new_mode
                }
                
                # Send response
                if self.response_service:
                    await self.response_service.send_response(request_id, response)
                
                logger.info(f"[FCS] Mode change {'successful' if success else 'failed'}: {old_mode} -> {new_mode}")
                
                # Return result for internal processing
                return response
            else:
                logger.warning("[FCS] Flight Control System not available, mode change not processed")
                return {"status": "ERROR", "message": "Flight Control System not available"}
                
        except Exception as e:
            logger.error(f"[FCS] Error handling mode change request: {e}")
            logger.error(traceback.format_exc())
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_mode_change_response(self, message):
        """
        Handle FCS mode change response
        
        Args:
            message: The mode change response
            
        Returns:
            dict: Status of processing
        """
        try:
            # This method mainly processes incoming responses from the FCS back to requestors
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid mode change response format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            # Complete pending request if it exists
            if request_id in self.pending_requests:
                pending_request = self.pending_requests.pop(request_id)
                pending_request.set_response(message)
                logger.info(f"[FCS] Completed pending request: {request_id}")
                
            return {"status": "SUCCESS", "message": "Mode change response processed"}
            
        except Exception as e:
            logger.error(f"[FCS] Error handling mode change response: {e}")
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_control_input_request(self, message):
        """
        Handle FCS control input request
        
        Args:
            message: The control input request
            
        Returns:
            dict: Control input result
        """
        try:
            # Check for message loops if middleware is available
            if self.loop_prevention:
                transaction_id = self._create_transaction_id(message, "control_input")
                should_process, enhanced_message = self.loop_prevention.process_message(
                    message, 
                    "fcs_control_input_handler",
                    transaction_id=transaction_id,
                    category="fcs_control_input"
                )
                if not should_process:
                    logger.warning(f"Breaking loop - FCS control input message already processed")
                    return {"status": "SKIPPED", "message": "Message loop detected"}
                    
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
                
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid control input message format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            # Extract control input data
            control_surface = None
            control_value = 0.0
            
            # Check if control data is in parameters or data words
            if 'parameters' in message:
                control_surface = message['parameters'].get('control_type')
                control_value = message['parameters'].get('value', 0.0)
            elif 'data' in message:
                # Try to parse binary data words
                data_words = message.get('data_words', [])
                if len(data_words) >= 2:
                    try:
                        control_code = int(data_words[0], 2)
                        scaled_value = int(data_words[1], 2)
                        
                        # Map control code to control type
                        control_map = {
                            1: "aileron",
                            2: "elevator",
                            3: "rudder",
                            4: "throttle",
                            5: "flaps",
                            6: "speedbrake",
                            7: "gear"
                        }
                        
                        control_surface = control_map.get(control_code)
                        
                        # Convert scaled value back to float range [-1.0, 1.0]
                        control_value = (scaled_value / 500.0) - 1.0
                        control_value = max(-1.0, min(1.0, control_value))  # Ensure valid range
                    except Exception as e:
                        logger.error(f"[FCS] Error parsing control input data words: {e}")
                        return {"status": "ERROR", "message": f"Error parsing control input data: {str(e)}"}
            
            if not control_surface:
                logger.warning("[FCS] No control surface specified in control input request")
                return {"status": "ERROR", "message": "No control surface specified"}
                
            request_id = message.get('request_id', None)
            
            logger.info(f"[FCS] Handling control input request: {control_surface}={control_value} (request_id: {request_id})")
            
            # Process control input through FCS
            if self.fcs:
                result = self.fcs.set_control_input(control_surface, control_value)
                
                success = result.get('success', False)
                
                # Create response
                response = {
                    "status": "SUCCESS" if success else "ERROR",
                    "message": result.get('message', ''),
                    "request_id": request_id,
                    "control_surface": control_surface,
                    "control_value": control_value,
                    "actual_value": result.get('actual_value', control_value)
                }
                
                # Send response
                if self.response_service:
                    await self.response_service.send_response(request_id, response)
                
                logger.info(f"[FCS] Control input {'set successfully' if success else 'failed'}")
                
                # Return result for internal processing
                return response
            else:
                logger.warning("[FCS] Flight Control System not available, control input not processed")
                return {"status": "ERROR", "message": "Flight Control System not available"}
                
        except Exception as e:
            logger.error(f"[FCS] Error handling control input request: {e}")
            logger.error(traceback.format_exc())
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_control_input_response(self, message):
        """
        Handle FCS control input response
        
        Args:
            message: The control input response
            
        Returns:
            dict: Status of processing
        """
        try:
            # This method mainly processes incoming responses from the FCS back to requestors
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid control input response format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            # Complete pending request if it exists
            if request_id in self.pending_requests:
                pending_request = self.pending_requests.pop(request_id)
                pending_request.set_response(message)
                logger.info(f"[FCS] Completed pending request: {request_id}")
                
            return {"status": "SUCCESS", "message": "Control input response processed"}
            
        except Exception as e:
            logger.error(f"[FCS] Error handling control input response: {e}")
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_orientation_data_request(self, message):
        """
        Handle FCS orientation data request
        
        Args:
            message: The orientation data request
            
        Returns:
            dict: Orientation data result
        """
        try:
            # Check for message loops if middleware is available
            if self.loop_prevention:
                transaction_id = self._create_transaction_id(message, "orientation_data")
                should_process, enhanced_message = self.loop_prevention.process_message(
                    message, 
                    "fcs_orientation_data_handler",
                    transaction_id=transaction_id,
                    category="fcs_orientation"
                )
                if not should_process:
                    logger.warning(f"Breaking loop - FCS orientation data message already processed")
                    return {"status": "SKIPPED", "message": "Message loop detected"}
                    
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
                
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid orientation data message format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            logger.info(f"[FCS] Handling orientation data request (request_id: {request_id})")
            
            # Get orientation data through FCS
            if self.fcs:
                orientation_data = self.fcs.get_orientation_data()
                
                # Create response
                response = {
                    "status": "SUCCESS",
                    "message": "Orientation data retrieved",
                    "request_id": request_id,
                    "data": orientation_data
                }
                
                # Send response
                if self.response_service:
                    await self.response_service.send_response(request_id, response)
                
                logger.info(f"[FCS] Orientation data retrieved successfully")
                
                # Return result for internal processing
                return response
            else:
                logger.warning("[FCS] Flight Control System not available, orientation data not retrieved")
                return {"status": "ERROR", "message": "Flight Control System not available"}
                
        except Exception as e:
            logger.error(f"[FCS] Error handling orientation data request: {e}")
            logger.error(traceback.format_exc())
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_orientation_data_response(self, message):
        """
        Handle FCS orientation data response
        
        Args:
            message: The orientation data response
            
        Returns:
            dict: Status of processing
        """
        try:
            # This method mainly processes incoming responses from the FCS back to requestors
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid orientation data response format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            # Complete pending request if it exists
            if request_id in self.pending_requests:
                pending_request = self.pending_requests.pop(request_id)
                pending_request.set_response(message)
                logger.info(f"[FCS] Completed pending request: {request_id}")
                
            return {"status": "SUCCESS", "message": "Orientation data response processed"}
            
        except Exception as e:
            logger.error(f"[FCS] Error handling orientation data response: {e}")
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_status_request(self, message):
        """
        Handle FCS status request
        
        Args:
            message: The status request
            
        Returns:
            dict: Status result
        """
        try:
            # Check for message loops if middleware is available
            if self.loop_prevention:
                transaction_id = self._create_transaction_id(message, "status")
                should_process, enhanced_message = self.loop_prevention.process_message(
                    message, 
                    "fcs_status_handler",
                    transaction_id=transaction_id,
                    category="fcs_status"
                )
                if not should_process:
                    logger.warning(f"Breaking loop - FCS status message already processed")
                    return {"status": "SKIPPED", "message": "Message loop detected"}
                    
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
                
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid status request format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            logger.info(f"[FCS] Handling status request (request_id: {request_id})")
            
            # Get status through FCS
            if self.fcs:
                status_data = self.fcs.get_status()
                
                # Create response
                response = {
                    "status": "SUCCESS",
                    "message": "Status retrieved",
                    "request_id": request_id,
                    "data": status_data
                }
                
                # Send response
                if self.response_service:
                    await self.response_service.send_response(request_id, response)
                
                logger.info(f"[FCS] Status retrieved successfully")
                
                # Return result for internal processing
                return response
            else:
                logger.warning("[FCS] Flight Control System not available, status not retrieved")
                return {"status": "ERROR", "message": "Flight Control System not available"}
                
        except Exception as e:
            logger.error(f"[FCS] Error handling status request: {e}")
            logger.error(traceback.format_exc())
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
            
    async def _handle_status_response(self, message):
        """
        Handle FCS status response
        
        Args:
            message: The status response
            
        Returns:
            dict: Status of processing
        """
        try:
            # This method mainly processes incoming responses from the FCS back to requestors
            if not isinstance(message, dict):
                if hasattr(message, 'to_dict'):
                    message = message.to_dict()
                else:
                    logger.warning(f"Invalid status response format: {type(message)}")
                    return {"status": "ERROR", "message": "Invalid message format"}
            
            request_id = message.get('request_id', None)
            
            # Complete pending request if it exists
            if request_id in self.pending_requests:
                pending_request = self.pending_requests.pop(request_id)
                pending_request.set_response(message)
                logger.info(f"[FCS] Completed pending request: {request_id}")
                
            return {"status": "SUCCESS", "message": "Status response processed"}
            
        except Exception as e:
            logger.error(f"[FCS] Error handling status response: {e}")
            return {"status": "ERROR", "message": f"Exception: {str(e)}"}
    
    def _create_transaction_id(self, message, message_subtype):
        """
        Create a unique transaction ID for message loop prevention
        
        Args:
            message (dict): The message to create a transaction ID for
            message_subtype (str): The subtype of the message (e.g., 'command', 'mode_change')
            
        Returns:
            str: A unique transaction ID
        """
        # Extract key fields for transaction ID
        if isinstance(message, dict):
            message_type = message.get('message_type', '')
            request_id = message.get('request_id', '')
            command_type = message.get('command_type', '')
            
            # Use existing transaction ID if available
            if message.get('metadata', {}).get('transaction_id'):
                existing_id = message.get('metadata', {}).get('transaction_id')
                # Only reuse if it's for the same message type to avoid cross-type loop issues
                if f"_{message_subtype}" in existing_id:
                    return existing_id
            
            # Create a unique composite ID
            return f"{request_id}_{message_type}_{command_type}_{message_subtype}"
        
        # Fallback for non-dict messages
        return f"{id(message)}_{message_subtype}"
    
    def _start_cleanup_timer(self):
        """Start the cleanup timer for pending requests"""
        if self.cleanup_timer and self.cleanup_timer.is_alive():
            return  # Timer already running
            
        self.cleanup_timer = threading.Timer(1.0, self._cleanup_pending_requests)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
    
    def _cleanup_pending_requests(self):
        """Clean up expired pending requests"""
        try:
            with self.lock:
                expired_requests = []
                retry_requests = []
                
                # Identify expired and retry requests
                for request_id, request in self.pending_requests.items():
                    if request.is_expired():
                        if request.should_retry():
                            retry_requests.append(request_id)
                        else:
                            expired_requests.append(request_id)
                
                # Handle retries
                for request_id in retry_requests:
                    request = self.pending_requests[request_id]
                    retry_count = request.increment_retry()
                    logger.warning(f"Retrying request {request_id} (retry {retry_count}/{request.max_retries})")
                    
                    # Re-issue the request
                    # Implementation would depend on the specific request type
                
                # Remove expired requests
                for request_id in expired_requests:
                    request = self.pending_requests.pop(request_id)
                    logger.warning(f"Request {request_id} expired after {request.max_retries} retries")
                    
                    # Notify of failure
                    if request.command_type and self.response_service:
                        response = {
                            "status": "ERROR",
                            "request_id": request_id,
                            "message": "Request timed out",
                            "data": {}
                        }
                        
                        # Send failure response
                        asyncio.run_coroutine_threadsafe(
                            self.response_service.send_response(request_id, response),
                            asyncio.get_event_loop()
                        )
        except Exception as e:
            logger.error(f"Error cleaning up pending requests: {e}")
        finally:
            # Restart the timer if still running
            if self.started:
                self._start_cleanup_timer()
    
    def start(self):
        """Start the FCS message handler"""
        if self.started:
            logger.warning("FCS Message Handler already started")
            return False
            
        self.started = True
        
        # Start cleanup timer
        self._start_cleanup_timer()
        
        logger.info("FCS Message Handler started")
        return True
    
    def stop(self):
        """Stop the FCS message handler"""
        if not self.started:
            logger.warning("FCS Message Handler already stopped")
            return False
            
        self.started = False
        
        # Stop cleanup timer
        if self.cleanup_timer:
            self.cleanup_timer.cancel()
            self.cleanup_timer = None
        
        logger.info("FCS Message Handler stopped")
        return True
    
    def is_healthy(self):
        """Check if handler is healthy"""
        fcs_healthy = self.fcs and hasattr(self.fcs, 'check_health') and self.fcs.check_health()
        
        return self.started and fcs_healthy

# Singleton instance
_fcs_message_handler = None

def get_fcs_message_handler():
    """Get singleton instance of FCS Message Handler"""
    global _fcs_message_handler
    if _fcs_message_handler is None:
        _fcs_message_handler = FCSMessageHandler()
    return _fcs_message_handler
