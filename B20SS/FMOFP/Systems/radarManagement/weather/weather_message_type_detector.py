'''
Detects and classifies weather messages based on their type.
This module is designed to determine the type of weather message received
and route it to the appropriate handler following consistent standards
as per the messaging consistency implementation plan.
'''

from typing import Dict, Any, Tuple, List, Optional, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_enums import weather_radarMode
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST, WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_STATUS_REQUEST, WEATHER_RADAR_STATUS_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST, WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST, WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_ECHO_TOP_REQUEST, WEATHER_RADAR_ECHO_TOP_RESPONSE,
    WEATHER_RADAR_STORM_CELL_REQUEST, WEATHER_RADAR_STORM_CELL_RESPONSE,
    WEATHER_RADAR_COMMAND, WEATHER_RADAR_DATA,
    COMMAND_TYPE_MODE_CHANGE, COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    COMMAND_TYPE_DATA_REQUEST,
    COMMAND_TYPE_PRECIPITATION_DATA, COMMAND_TYPE_PRECIPITATION_COMPLETION,
    COMMAND_TYPE_VIL_DATA,
    # Import standardized helper functions
    get_message_type,
    is_message_type,
    is_vil_message,
    is_precipitation_message,
    is_mode_change_message
)

logger = get_logger()



class weather_message_type_detector:
    '''
    Detects and classifies weather messages based on their type.
    This module is designed to determine the type of weather message received
    and route it to the appropriate handler following standardized patterns.
    
    Implements consistent message type detection using standardized helper functions
    from message_types.py.
    '''

    def __init__(self) -> None:
        '''
        Initializes the weather message type detector.
        Sets up the command and message type dictionary for classification.
        '''
        # Handler mapping for direct command type routing
        self._handler_dictionary = {
            WEATHER_RADAR_COMMAND: 'weather_radarCommandHandler',
            COMMAND_TYPE_PRECIPITATION_DATA: 'precipitationDataHandler',
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: 'modeChangeCompletionHandler',
            COMMAND_TYPE_PRECIPITATION_COMPLETION: 'precipitationCompletionHandler',
            COMMAND_TYPE_VIL_DATA: 'vilDataHandler'
        }
        
        # Command type mapping for command categorization
        self._command_type_dict = {
            COMMAND_TYPE_MODE_CHANGE: ['weather_radarMode'],
            COMMAND_TYPE_DATA_REQUEST: [WEATHER_RADAR_DATA],
            WEATHER_RADAR_COMMAND: [WEATHER_RADAR_COMMAND],
            COMMAND_TYPE_PRECIPITATION_DATA: ['precipitation_data'],
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: ['mode_change_completion'],
            COMMAND_TYPE_PRECIPITATION_COMPLETION: ['precipitation_completion'],
            COMMAND_TYPE_VIL_DATA: ['vil_data']
        }
        
        # Message type mapping for message categorization
        self._message_type_dict = {
            'status': [WEATHER_RADAR_STATUS_REQUEST, WEATHER_RADAR_STATUS_RESPONSE],
            'mode': [WEATHER_RADAR_MODE_CHANGE_REQUEST, WEATHER_RADAR_MODE_CHANGE_RESPONSE],
            'command': [WEATHER_RADAR_COMMAND],
            'data': [WEATHER_RADAR_DATA],
            'precipitation': [WEATHER_RADAR_PRECIPITATION_REQUEST, WEATHER_RADAR_PRECIPITATION_RESPONSE],
            'vil': [WEATHER_RADAR_VIL_REQUEST, WEATHER_RADAR_VIL_RESPONSE],
            'echo_top': [WEATHER_RADAR_ECHO_TOP_REQUEST, WEATHER_RADAR_ECHO_TOP_RESPONSE],
            'storm_cell': [WEATHER_RADAR_STORM_CELL_REQUEST, WEATHER_RADAR_STORM_CELL_RESPONSE],
            'weather_radar': ['weather_radar']
        }
        
        # Initialize radar mode
        self.mode = weather_radarMode.INITIALIZING


    def detect_message_type(self, message: Union[Dict[str, Any], object]) -> str:
        '''
        Detects the command and message type of the weather message.
        Returns which handler to use based on command and message type.
        
        Uses standardized message type detection functions for consistency.

        Parameters:
            message: The weather message to be classified (dict or object).

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
            
        logger.info(f"[WEATHER] Processing message with type: {msg_type}, command type: {cmd_type}")
        
        # Use standardized type checking functions first
        if is_vil_message(message):
            logger.info("[WEATHER][VIL_FLOW] Detected VIL message via is_vil_message()")
            # Check if request or response
            if is_message_type(message, WEATHER_RADAR_VIL_REQUEST):
                logger.info("[WEATHER][VIL_FLOW] Received VIL data request")
                return "vil_handler"
            else:
                logger.info("[WEATHER][VIL_FLOW] Received VIL data response")
                return "vil_handler"
                
        elif is_precipitation_message(message):
            logger.info("[WEATHER][PRECIP_FLOW] Detected precipitation message via is_precipitation_message()")
            # Check if request or response
            if is_message_type(message, WEATHER_RADAR_PRECIPITATION_REQUEST):
                logger.info("[WEATHER][PRECIP_FLOW] Received precipitation data request")
                return "precipitation_handler"
            else:
                logger.info("[WEATHER][PRECIP_FLOW] Received precipitation data response")
                return "precipitation_handler"
                
        elif is_mode_change_message(message):
            logger.info("[WEATHER] Detected mode change message via is_mode_change_message()")
            return "mode_handler"
        
        # Fall back to traditional message type checking
        if msg_type == WEATHER_RADAR_COMMAND:
            # This is a command message for the weather radar
            logger.info("[WEATHER] Weather radar command message detected")
            logger.info(f"[WEATHER] Command type: {cmd_type}, Message type: {msg_type}")
            
            if cmd_type == COMMAND_TYPE_MODE_CHANGE:
                # Handle mode change command
                logger.info("[WEATHER] Mode change command detected")
                return 'mode_handler'
        
        if cmd_type == COMMAND_TYPE_DATA_REQUEST:
            # Handle data requests
            logger.info("[WEATHER] Data request received")
            
            if is_message_type(message, WEATHER_RADAR_PRECIPITATION_REQUEST):
                # Handle precipitation data request
                logger.info("[WEATHER][PRECIP_FLOW] Received precipitation data request")
                return "precipitation_handler"
            
            elif is_message_type(message, WEATHER_RADAR_VIL_REQUEST):
                # Handle VIL data request
                logger.info("[WEATHER][VIL_FLOW] Received VIL data request")
                return "vil_handler"
            
            elif is_message_type(message, WEATHER_RADAR_ECHO_TOP_REQUEST):
                # Handle Echo Top data request
                logger.info("[WEATHER][ECHO_TOP] Received Echo Top data request")
                return "echo_top_handler"
            
            elif is_message_type(message, WEATHER_RADAR_STORM_CELL_REQUEST):
                # Handle Storm Cell data request
                logger.info("[WEATHER][STORM_CELL] Received Storm Cell data request")
                return "storm_cell_handler"
        
        # Unknown message type
        logger.error(f"[WEATHER] Cannot determine handler for Command type: {cmd_type}, Message type: {msg_type}")
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
