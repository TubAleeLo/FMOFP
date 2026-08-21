'''
Detects and classifies TFR radar messages based on their type.
This module is designed to determine the type of TFR radar message received
and route it to the appropriate handler following consistent standards
as per the messaging consistency implementation plan.
'''

from typing import Dict, Any, Tuple, List, Optional, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_enums import tfr_radarMode
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    TFR_RADAR_MODE_CHANGE_REQUEST, TFR_RADAR_MODE_CHANGE_RESPONSE,
    TFR_RADAR_STATUS_REQUEST, TFR_RADAR_STATUS_RESPONSE,
    TFR_RADAR_ELEVATION_DATA_REQUEST, TFR_RADAR_ELEVATION_DATA_RESPONSE,
    TFR_RADAR_ELEVATION_PROFILE, TFR_RADAR_TERRAIN_WARNING,
    TFR_RADAR_COMMAND, TFR_RADAR_DATA,
    COMMAND_TYPE_MODE_CHANGE, COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    COMMAND_TYPE_DATA_REQUEST, COMMAND_TYPE_ELEVATION_DATA,
    COMMAND_TYPE_TERRAIN_WARNING,
    # Import standardized helper functions
    get_message_type,
    is_message_type,
    is_mode_change_message
)

logger = get_logger()


class tfr_message_type_detector:
    '''
    Detects and classifies TFR radar messages based on their type.
    This module is designed to determine the type of TFR radar message received
    and route it to the appropriate handler following standardized patterns.
    
    Implements consistent message type detection using standardized helper functions
    from message_types.py.
    '''

    def __init__(self) -> None:
        '''
        Initializes the TFR message type detector.
        Sets up the command and message type dictionary for classification.
        '''
        # Handler mapping for direct command type routing
        self._handler_dictionary = {
            TFR_RADAR_COMMAND: 'tfr_radarCommandHandler',
            COMMAND_TYPE_ELEVATION_DATA: 'elevationDataHandler',
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: 'modeChangeCompletionHandler',
            COMMAND_TYPE_TERRAIN_WARNING: 'terrainWarningHandler'
        }
        
        # Command type mapping for command categorization
        self._command_type_dict = {
            COMMAND_TYPE_MODE_CHANGE: ['tfr_radarMode'],
            COMMAND_TYPE_DATA_REQUEST: [TFR_RADAR_DATA],
            TFR_RADAR_COMMAND: [TFR_RADAR_COMMAND],
            COMMAND_TYPE_ELEVATION_DATA: ['elevation_data'],
            COMMAND_TYPE_MODE_CHANGE_COMPLETE: ['mode_change_completion'],
            COMMAND_TYPE_TERRAIN_WARNING: ['terrain_warning']
        }
        
        # Message type mapping for message categorization
        self._message_type_dict = {
            'status': [TFR_RADAR_STATUS_REQUEST, TFR_RADAR_STATUS_RESPONSE],
            'mode': [TFR_RADAR_MODE_CHANGE_REQUEST, TFR_RADAR_MODE_CHANGE_RESPONSE],
            'command': [TFR_RADAR_COMMAND],
            'data': [TFR_RADAR_DATA],
            'elevation': [TFR_RADAR_ELEVATION_DATA_REQUEST, TFR_RADAR_ELEVATION_DATA_RESPONSE, TFR_RADAR_ELEVATION_PROFILE],
            'terrain': [TFR_RADAR_TERRAIN_WARNING],
            'tfr_radar': ['tfr_radar']
        }
        
        # Initialize radar mode
        self.mode = tfr_radarMode.INITIALIZING if hasattr(tfr_radarMode, 'INITIALIZING') else tfr_radarMode.STANDBY


    def detect_message_type(self, message: Union[Dict[str, Any], object]) -> str:
        '''
        Detects the command and message type of the TFR radar message.
        Returns which handler to use based on command and message type.
        
        Uses standardized message type detection functions for consistency.

        Parameters:
            message: The TFR radar message to be classified (dict or object).

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
            
        logger.info(f"[TFR] Processing message with type: {msg_type}, command type: {cmd_type}")
        
        # Use standardized type checking functions first
        if is_mode_change_message(message):
            logger.info("[TFR] Detected mode change message via is_mode_change_message()")
            return "mode_handler"
                
        # Check for elevation data messages
        if self._is_elevation_data_message(message):
            logger.info("[TFR] Detected elevation data message")
            return "elevation_handler"
            
        # Check for terrain warning messages
        if self._is_terrain_warning_message(message):
            logger.info("[TFR] Detected terrain warning message")
            return "terrain_warning_handler"
        
        # Fall back to traditional message type checking
        if msg_type == TFR_RADAR_COMMAND:
            # This is a command message for the TFR radar
            logger.info("[TFR] TFR radar command message detected")
            logger.info(f"[TFR] Command type: {cmd_type}, Message type: {msg_type}")
            
            if cmd_type == COMMAND_TYPE_MODE_CHANGE:
                # Handle mode change command
                logger.info("[TFR] Mode change command detected")
                return 'mode_handler'
        
        if cmd_type == COMMAND_TYPE_DATA_REQUEST:
            # Handle data requests
            logger.info("[TFR] Data request received")
            
            if is_message_type(message, TFR_RADAR_ELEVATION_DATA_REQUEST):
                # Handle elevation data request
                logger.info("[TFR] Received elevation data request")
                return "elevation_handler"
            
            elif self._is_terrain_warning_message(message):
                # Handle terrain warning request
                logger.info("[TFR] Received terrain warning request")
                return "terrain_warning_handler"
        
        # Unknown message type
        logger.error(f"[TFR] Cannot determine handler for Command type: {cmd_type}, Message type: {msg_type}")
        return "unknown_handler"
    
    def _is_elevation_data_message(self, message: Union[Dict[str, Any], object]) -> bool:
        """
        Check if a message is an elevation data message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is an elevation data message, False otherwise
        """
        msg_type = get_message_type(message)
        if not msg_type:
            return False
        
        msg_type_lower = msg_type.lower()
        return (msg_type_lower == TFR_RADAR_ELEVATION_DATA_REQUEST.lower() or 
                msg_type_lower == TFR_RADAR_ELEVATION_DATA_RESPONSE.lower() or 
                msg_type_lower == TFR_RADAR_ELEVATION_PROFILE.lower() or
                'elevation' in msg_type_lower)
    
    def _is_terrain_warning_message(self, message: Union[Dict[str, Any], object]) -> bool:
        """
        Check if a message is a terrain warning message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a terrain warning message, False otherwise
        """
        msg_type = get_message_type(message)
        if not msg_type:
            return False
        
        msg_type_lower = msg_type.lower()
        return (msg_type_lower == TFR_RADAR_TERRAIN_WARNING.lower() or 
                'terrain' in msg_type_lower or
                'warning' in msg_type_lower)
    
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
