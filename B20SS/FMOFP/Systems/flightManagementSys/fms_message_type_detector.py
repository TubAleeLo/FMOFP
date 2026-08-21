'''
Detects and classifies FMS messages based on their type.
This module is designed to determine the type of FMS message received
and route it to the appropriate handler following consistent standards.
'''

from typing import Dict, Any, Tuple, List, Optional, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.fms_messaging.message_types import (
    # FMS message types
    FMS_MODE_CHANGE_REQUEST, FMS_MODE_CHANGE_RESPONSE,
    FMS_STATUS_REQUEST, FMS_STATUS_RESPONSE,
    FMS_ATTITUDE_UPDATE_REQUEST, FMS_ATTITUDE_UPDATE_RESPONSE,
    FMS_NAVIGATION_UPDATE_REQUEST, FMS_NAVIGATION_UPDATE_RESPONSE,
    FMS_MANEUVER_REQUEST, FMS_MANEUVER_RESPONSE,
    FMS_COMMAND, FMS_DATA,
    
    # FCS message types
    FCS_CONTROL_INPUT_REQUEST, FCS_CONTROL_INPUT_RESPONSE,
    FCS_ORIENTATION_DATA_REQUEST, FCS_ORIENTATION_DATA_RESPONSE,
    FCS_STATUS_REQUEST, FCS_STATUS_RESPONSE,
    FCS_MODE_CHANGE_REQUEST, FCS_MODE_CHANGE_RESPONSE,
    
    # Command types
    COMMAND_TYPE_MODE_CHANGE, COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    COMMAND_TYPE_DATA_REQUEST, COMMAND_TYPE_DATA_RESPONSE,
    COMMAND_TYPE_STATUS_REQUEST, COMMAND_TYPE_STATUS_RESPONSE,
    COMMAND_TYPE_ATTITUDE_UPDATE, COMMAND_TYPE_NAVIGATION_UPDATE,
    COMMAND_TYPE_MANEUVER_REQUEST, COMMAND_TYPE_CONTROL_INPUT,
    COMMAND_TYPE_CONTROL_INPUT_COMPLETE, COMMAND_TYPE_ORIENTATION_DATA,
    
    # Import standardized helper functions
    get_message_type,
    is_message_type,
    is_mode_change_message,
    is_attitude_update_message,
    is_status_message,
    is_control_input_message,
    is_orientation_data_message
)

logger = get_logger()

class fms_message_type_detector:
    '''
    Detects and classifies FMS messages based on their type.
    This module is designed to determine the type of FMS message received
    and route it to the appropriate handler following standardized patterns.
    
    Implements consistent message type detection using standardized helper functions
    from message_types.py.
    '''

    def __init__(self) -> None:
        '''
        Initializes the FMS message type detector.
        Sets up the command and message type dictionary for classification.
        '''
        # Handler mapping for direct command type routing
        self._handler_dictionary = {
            FMS_COMMAND: 'fms_commandHandler',
            COMMAND_TYPE_MODE_CHANGE: 'mode_handler',
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: 'modeChangeCompletionHandler',
            COMMAND_TYPE_STATUS_REQUEST: 'status_handler',
            COMMAND_TYPE_STATUS_RESPONSE: 'status_handler',
            COMMAND_TYPE_ATTITUDE_UPDATE: 'attitude_handler',
            COMMAND_TYPE_NAVIGATION_UPDATE: 'navigation_handler',
            COMMAND_TYPE_MANEUVER_REQUEST: 'maneuver_handler',
            # FCS handlers
            COMMAND_TYPE_CONTROL_INPUT: 'control_input_handler',
            COMMAND_TYPE_CONTROL_INPUT_COMPLETE: 'control_input_completion_handler',
            COMMAND_TYPE_ORIENTATION_DATA: 'orientation_data_handler',
            FCS_MODE_CHANGE_REQUEST: 'fcs_mode_handler',
            FCS_STATUS_REQUEST: 'fcs_status_handler'
        }
        
        # Command type mapping for command categorization
        self._command_type_dict = {
            COMMAND_TYPE_MODE_CHANGE: ['mode_change'],
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: ['mode_change_completion'],
            COMMAND_TYPE_STATUS_REQUEST: ['status_request'],
            COMMAND_TYPE_STATUS_RESPONSE: ['status_response'],
            COMMAND_TYPE_DATA_REQUEST: [FMS_DATA],
            COMMAND_TYPE_DATA_RESPONSE: [FMS_DATA],
            COMMAND_TYPE_ATTITUDE_UPDATE: ['attitude_update'],
            COMMAND_TYPE_NAVIGATION_UPDATE: ['navigation_update'],
            COMMAND_TYPE_MANEUVER_REQUEST: ['maneuver_request'],
            COMMAND_TYPE_CONTROL_INPUT: ['control_input'],
            COMMAND_TYPE_CONTROL_INPUT_COMPLETE: ['control_input_completion'],
            COMMAND_TYPE_ORIENTATION_DATA: ['orientation_data'],
            FMS_COMMAND: [FMS_COMMAND]
        }
        
        # Message type mapping for message categorization
        self._message_type_dict = {
            'mode': [FMS_MODE_CHANGE_REQUEST, FMS_MODE_CHANGE_RESPONSE, 
                     FCS_MODE_CHANGE_REQUEST, FCS_MODE_CHANGE_RESPONSE],
            'status': [FMS_STATUS_REQUEST, FMS_STATUS_RESPONSE, 
                       FCS_STATUS_REQUEST, FCS_STATUS_RESPONSE],
            'attitude': [FMS_ATTITUDE_UPDATE_REQUEST, FMS_ATTITUDE_UPDATE_RESPONSE],
            'navigation': [FMS_NAVIGATION_UPDATE_REQUEST, FMS_NAVIGATION_UPDATE_RESPONSE],
            'maneuver': [FMS_MANEUVER_REQUEST, FMS_MANEUVER_RESPONSE],
            'control_input': [FCS_CONTROL_INPUT_REQUEST, FCS_CONTROL_INPUT_RESPONSE],
            'orientation_data': [FCS_ORIENTATION_DATA_REQUEST, FCS_ORIENTATION_DATA_RESPONSE],
            'command': [FMS_COMMAND],
            'data': [FMS_DATA],
            'fms': ['fms'],
            'fcs': ['fcs']
        }
        
        # Initialize FMS mode
        self.mode = "INITIALIZING"

    def detect_message_type(self, message: Union[Dict[str, Any], object]) -> str:
        '''
        Detects the command and message type of the FMS message.
        Returns which handler to use based on command and message type.
        
        Uses standardized message type detection functions for consistency.

        Parameters:
            message: The FMS message to be classified (dict or object).

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
            
        logger.info(f"[FMS] Processing message with type: {msg_type}, command type: {cmd_type}")
        
        # Use standardized type checking functions first
        if is_mode_change_message(message):
            logger.info("[FMS] Detected mode change message via is_mode_change_message()")
            # Check if request or response
            if is_message_type(message, FMS_MODE_CHANGE_REQUEST):
                logger.info("[FMS] Received mode change request")
                return "mode_handler"
            else:
                logger.info("[FMS] Received mode change response")
                return "mode_handler"
                
        elif is_attitude_update_message(message):
            logger.info("[FMS] Detected attitude update message via is_attitude_update_message()")
            # Check if request or response
            if is_message_type(message, FMS_ATTITUDE_UPDATE_REQUEST):
                logger.info("[FMS] Received attitude update request")
                return "attitude_handler"
            else:
                logger.info("[FMS] Received attitude update response")
                return "attitude_handler"
                
        elif is_status_message(message):
            logger.info("[FMS] Detected status message via is_status_message()")
            # Check if FCS status
            if is_message_type(message, FCS_STATUS_REQUEST) or is_message_type(message, FCS_STATUS_RESPONSE):
                logger.info("[FMS] FCS status message detected")
                return "fcs_status_handler"
            return "status_handler"
            
        elif is_control_input_message(message):
            logger.info("[FMS] Detected control input message via is_control_input_message()")
            # Check if request or response
            if is_message_type(message, FCS_CONTROL_INPUT_REQUEST):
                logger.info("[FMS] Received control input request")
                return "control_input_handler"
            else:
                logger.info("[FMS] Received control input response")
                return "control_input_handler"
                
        elif is_orientation_data_message(message):
            logger.info("[FMS] Detected orientation data message via is_orientation_data_message()")
            # Check if request or response
            if is_message_type(message, FCS_ORIENTATION_DATA_REQUEST):
                logger.info("[FMS] Received orientation data request")
                return "orientation_data_handler"
            else:
                logger.info("[FMS] Received orientation data response")
                return "orientation_data_handler"
        
        # Fall back to traditional message type checking
        if msg_type == FMS_COMMAND:
            # This is a command message for the FMS
            logger.info("[FMS] FMS command message detected")
            logger.info(f"[FMS] Command type: {cmd_type}, Message type: {msg_type}")
            
            if cmd_type == COMMAND_TYPE_MODE_CHANGE:
                # Handle mode change command
                logger.info("[FMS] Mode change command detected")
                return 'mode_handler'
            elif cmd_type == COMMAND_TYPE_ATTITUDE_UPDATE:
                # Handle attitude update command
                logger.info("[FMS] Attitude update command detected")
                return 'attitude_handler'
            elif cmd_type == COMMAND_TYPE_NAVIGATION_UPDATE:
                # Handle navigation update command
                logger.info("[FMS] Navigation update command detected")
                return 'navigation_handler'
            elif cmd_type == COMMAND_TYPE_MANEUVER_REQUEST:
                # Handle maneuver request command
                logger.info("[FMS] Maneuver request command detected")
                return 'maneuver_handler'
            elif cmd_type == COMMAND_TYPE_STATUS_REQUEST:
                # Handle status request command
                logger.info("[FMS] Status request command detected")
                return 'status_handler'
        
        if cmd_type == COMMAND_TYPE_DATA_REQUEST:
            # Handle data requests
            logger.info("[FMS] Data request received")
            
            if is_message_type(message, FMS_ATTITUDE_UPDATE_REQUEST):
                # Handle attitude update data request
                logger.info("[FMS] Received attitude update data request")
                return "attitude_handler"
            
            elif is_message_type(message, FMS_NAVIGATION_UPDATE_REQUEST):
                # Handle navigation update data request
                logger.info("[FMS] Received navigation update data request")
                return "navigation_handler"
            
            elif is_message_type(message, FMS_MANEUVER_REQUEST):
                # Handle maneuver request data
                logger.info("[FMS] Received maneuver request data")
                return "maneuver_handler"
            
            elif is_message_type(message, FMS_STATUS_REQUEST):
                # Handle status request
                logger.info("[FMS] Received status request")
                return "status_handler"
                
            elif is_message_type(message, FCS_CONTROL_INPUT_REQUEST):
                # Handle control input request data
                logger.info("[FMS] Received control input request data")
                return "control_input_handler"
                
            elif is_message_type(message, FCS_ORIENTATION_DATA_REQUEST):
                # Handle orientation data request
                logger.info("[FMS] Received orientation data request")
                return "orientation_data_handler"
        
        # Unknown message type
        logger.error(f"[FMS] Cannot determine handler for Command type: {cmd_type}, Message type: {msg_type}")
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
