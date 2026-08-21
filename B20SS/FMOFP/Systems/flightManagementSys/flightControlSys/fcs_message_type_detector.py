'''
Detects and classifies Flight Control System messages based on their type.
This module is designed to determine the type of FCS message received
and route it to the appropriate handler following consistent standards.
'''

from typing import Dict, Any, Tuple, List, Optional, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.fms_messaging.message_types import (
    # FCS message types
    FCS_CONTROL_INPUT_REQUEST, FCS_CONTROL_INPUT_RESPONSE,
    FCS_ORIENTATION_DATA_REQUEST, FCS_ORIENTATION_DATA_RESPONSE,
    FCS_STATUS_REQUEST, FCS_STATUS_RESPONSE,
    FCS_MODE_CHANGE_REQUEST, FCS_MODE_CHANGE_RESPONSE,
    
    # Command types
    COMMAND_TYPE_CONTROL_INPUT, COMMAND_TYPE_CONTROL_INPUT_COMPLETE,
    COMMAND_TYPE_ORIENTATION_DATA, COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_STATUS_REQUEST, COMMAND_TYPE_STATUS_RESPONSE,
    
    # Helper functions
    get_message_type,
    is_message_type,
    is_control_input_message,
    is_orientation_data_message,
    is_status_message
)

logger = get_logger()

class fcs_message_type_detector:
    '''
    Detects and classifies FCS messages based on their type.
    
    This module implements consistent message type detection using standardized helper functions
    from message_types.py to ensure uniform message processing across the system.
    '''

    def __init__(self) -> None:
        '''
        Initializes the FCS message type detector.
        Sets up command and message type dictionaries for classification.
        '''
        # Handler mapping for direct command type routing
        self._handler_dictionary = {
            COMMAND_TYPE_CONTROL_INPUT: 'control_input_handler',
            COMMAND_TYPE_CONTROL_INPUT_COMPLETE: 'control_input_completion_handler',
            COMMAND_TYPE_ORIENTATION_DATA: 'orientation_data_handler',
            COMMAND_TYPE_MODE_CHANGE: 'mode_handler',
            COMMAND_TYPE_STATUS_REQUEST: 'status_handler',
            COMMAND_TYPE_STATUS_RESPONSE: 'status_handler'
        }
        
        # Command type mapping for command categorization
        self._command_type_dict = {
            COMMAND_TYPE_CONTROL_INPUT: ['control_input'],
            COMMAND_TYPE_CONTROL_INPUT_COMPLETE: ['control_input_completion'],
            COMMAND_TYPE_ORIENTATION_DATA: ['orientation_data'],
            COMMAND_TYPE_MODE_CHANGE: ['mode_change'],
            COMMAND_TYPE_STATUS_REQUEST: ['status_request'],
            COMMAND_TYPE_STATUS_RESPONSE: ['status_response']
        }
        
        # Message type mapping for message categorization
        self._message_type_dict = {
            'control_input': [FCS_CONTROL_INPUT_REQUEST, FCS_CONTROL_INPUT_RESPONSE],
            'orientation_data': [FCS_ORIENTATION_DATA_REQUEST, FCS_ORIENTATION_DATA_RESPONSE],
            'mode': [FCS_MODE_CHANGE_REQUEST, FCS_MODE_CHANGE_RESPONSE],
            'status': [FCS_STATUS_REQUEST, FCS_STATUS_RESPONSE]
        }
        
        # Initialize FCS mode
        self.mode = "NORMAL"

    def detect_message_type(self, message: Union[Dict[str, Any], object]) -> str:
        '''
        Detects the command and message type of the FCS message.
        Returns which handler to use based on command and message type.
        
        Uses standardized message type detection functions for consistency.

        Parameters:
            message: The FCS message to be classified (dict or object).

        Returns:
            str: The handler type to use for this message.
        '''
        # Extract message type using standard helper function
        msg_type = get_message_type(message)
        
        # Extract command type - handle both dict and object patterns
        if isinstance(message, dict):
            cmd_type = message.get('command_type')
        elif hasattr(message, 'command_type'):
            cmd_type = message.command_type
        else:
            cmd_type = None
            
        logger.info(f"[FCS] Processing message with type: {msg_type}, command type: {cmd_type}")
        
        # Use standardized type checking functions first for more reliable detection
        if is_control_input_message(message):
            logger.info("[FCS] Detected control input message via is_control_input_message()")
            # Check if request or response
            if is_message_type(message, FCS_CONTROL_INPUT_REQUEST):
                logger.info("[FCS] Received control input request")
                return "control_input_handler"
            else:
                logger.info("[FCS] Received control input response")
                return "control_input_handler"
        
        elif is_orientation_data_message(message):
            logger.info("[FCS] Detected orientation data message via is_orientation_data_message()")
            # Check if request or response
            if is_message_type(message, FCS_ORIENTATION_DATA_REQUEST):
                logger.info("[FCS] Received orientation data request")
                return "orientation_data_handler"
            else:
                logger.info("[FCS] Received orientation data response")
                return "orientation_data_handler"
        
        elif is_status_message(message):
            logger.info("[FCS] Detected status message via is_status_message()")
            # Check if FCS status specifically
            if is_message_type(message, FCS_STATUS_REQUEST) or is_message_type(message, FCS_STATUS_RESPONSE):
                logger.info("[FCS] Received FCS status message")
                return "status_handler"
            
        # Fall back to traditional message type checking
        if msg_type:
            # Check for known message types
            if msg_type == FCS_CONTROL_INPUT_REQUEST:
                logger.info("[FCS] Received control input request via direct type check")
                return "control_input_handler"
                
            elif msg_type == FCS_ORIENTATION_DATA_REQUEST:
                logger.info("[FCS] Received orientation data request via direct type check")
                return "orientation_data_handler"
                
            elif msg_type == FCS_MODE_CHANGE_REQUEST:
                logger.info("[FCS] Received mode change request via direct type check")
                return "mode_handler"
                
            elif msg_type == FCS_STATUS_REQUEST:
                logger.info("[FCS] Received status request via direct type check")
                return "status_handler"
        
        # Command type-based routing as a last resort
        if cmd_type and cmd_type in self._handler_dictionary:
            handler = self._handler_dictionary[cmd_type]
            logger.info(f"[FCS] Routing message to {handler} based on command type: {cmd_type}")
            return handler
        
        # Unknown message type
        logger.error(f"[FCS] Cannot determine handler for Command type: {cmd_type}, Message type: {msg_type}")
        return "unknown_handler"
    
    def get_category_for_message_type(self, message: Union[Dict[str, Any], object]) -> Optional[str]:
        """
        Categorizes a message by its message type.
        
        Parameters:
            message: The message to categorize
            
        Returns:
            str or None: The category name or None if not categorized
        """
        msg_type = get_message_type(message)
        if not msg_type:
            return None
            
        # Lowercase for case-insensitive comparison
        msg_type_lower = msg_type.lower()
        
        # Check each category
        for category, types in self._message_type_dict.items():
            for type_val in types:
                if type_val.lower() == msg_type_lower:
                    return category
                    
        return None
