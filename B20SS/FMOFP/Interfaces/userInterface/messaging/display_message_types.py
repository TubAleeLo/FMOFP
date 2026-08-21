"""
Display-specific message type constants and utilities.

This module contains centralized constants and utilities for working with message types
in the display system. All message type references should use these constants instead of
hardcoded strings to ensure consistency throughout the system.

This is critical for compliance with the MIL-STD-1553B protocol, which requires proper
message type identification and handling.
"""

from typing import Any, Dict, Optional, Union
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Display Command Types - Used in message metadata per MIL-STD-1553B requirements
DISPLAY_COMMAND_TYPE_SHOW = 'show'
DISPLAY_COMMAND_TYPE_MODE = 'mode'
DISPLAY_COMMAND_TYPE_DATA = 'data'
DISPLAY_COMMAND_TYPE_STATUS = 'status'
DISPLAY_COMMAND_TYPE_MODE_CHANGE = 'mode_change'
DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE = 'mode_change_complete'
DISPLAY_COMMAND_TYPE_VIL_DATA = 'vil_data'
DISPLAY_COMMAND_TYPE_PRECIPITATION_DATA = 'precipitation_data'

# Weather Radar Modes
WEATHER_RADAR_MODE_STANDBY = 'STANDBY'
WEATHER_RADAR_MODE_ACTIVE = 'ACTIVE'    # General active mode
WEATHER_RADAR_MODE_SURVEILLANCE = 'SURVEILLANCE' 
WEATHER_RADAR_MODE_WINDSHEAR = 'WINDSHEAR'
WEATHER_RADAR_MODE_TURBULENCE = 'TURBULENCE'
WEATHER_RADAR_MODE_MAPPING = 'MAPPING'
WEATHER_RADAR_MODE_TEST = 'TEST'
WEATHER_RADAR_MODE_NORMAL = 'NORMAL'    # Normal operation mode

# Weather Radar Message Types
WEATHER_RADAR_MODE_CHANGE_REQUEST = 'weather_radarModeChangeRequest'
WEATHER_RADAR_MODE_CHANGE_RESPONSE = 'weather_radarModeChangeResponse'
WEATHER_RADAR_STATUS_REQUEST = 'weather_radarStatusRequest'
WEATHER_RADAR_STATUS_RESPONSE = 'weather_radarStatusResponse'
WEATHER_RADAR_VIL_REQUEST = 'weather_radarVILRequest'
WEATHER_RADAR_VIL_RESPONSE = 'weather_radarVILResponse'
WEATHER_RADAR_PRECIPITATION_REQUEST = 'weather_radarPrecipitationRequest'
WEATHER_RADAR_PRECIPITATION_RESPONSE = 'weather_radarPrecipitationResponse'
WEATHER_RADAR_ECHO_TOP_REQUEST = 'weather_radarEchoTopRequest'
WEATHER_RADAR_ECHO_TOP_RESPONSE = 'weather_radarEchoTopResponse'
WEATHER_RADAR_STORM_CELL_REQUEST = 'weather_radarStormCellRequest'
WEATHER_RADAR_STORM_CELL_RESPONSE = 'weather_radarStormCellResponse'

# Display System Message Types
DISPLAY_MODE_REQUEST = 'display_mode_request'
DISPLAY_MODE_RESPONSE = 'display_mode_response'
DISPLAY_STATUS_REQUEST = 'display_status_request'
DISPLAY_STATUS_RESPONSE = 'display_status_response'
DISPLAY_DATA_REQUEST = 'display_data_request'
DISPLAY_DATA_RESPONSE = 'display_data_response'
DISPLAY_MODE_CHANGE = 'display_mode_change'
DISPLAY_MODE_CHANGE_COMPLETION = 'display_mode_change_completion'

# Special Data Type Message Types
DISPLAY_VIL_DATA = 'display_vil_data'
DISPLAY_PRECIPITATION_DATA = 'display_precipitation_data'
DISPLAY_ECHO_TOP_DATA = 'display_echo_top_data'
DISPLAY_STORM_CELL_DATA = 'display_storm_cell_data'
DISPLAY_TERRAIN_DATA = 'display_terrain_data'
DISPLAY_IMAGERY_DATA = 'display_imagery_data'
DISPLAY_TRACK_DATA = 'display_track_data'
DISPLAY_SECTOR_SCAN_DATA = 'display_sector_scan_data'
DISPLAY_MODE_CHANGE = 'display_mode_change'

# Completion/status/transfer message types used by DisplayMetadataDecoder's
# DISPLAY_MESSAGE_TYPE_MAP. These values are unchanged from the raw string
# literals they replace - they are also used as literal strings ('status_word',
# 'transfer_init'/'transfer_data'/'transfer_complete', 'precipitation_completion',
# 'vil_completion', 'display_data') in many other files across BC.py, the
# local_messaging routing layer, and weather_message_type_detector.py, so the
# values themselves must not change; this only gives the display decoder a
# named constant instead of an inline magic string, matching the pattern
# already used for the other entries in that map.
DISPLAY_PRECIPITATION_COMPLETION = 'precipitation_completion'
DISPLAY_VIL_COMPLETION = 'vil_completion'
DISPLAY_STATUS_WORD = 'status_word'
DISPLAY_TRANSFER_INIT = 'transfer_init'
DISPLAY_TRANSFER_DATA = 'transfer_data'
DISPLAY_TRANSFER_COMPLETE = 'transfer_complete'
DISPLAY_DATA_MESSAGE_TYPE = 'display_data'

# Message Type Mapping - for translation between core system and display system
MESSAGE_TYPE_MAPPING = {
    # Weather radar translations
    WEATHER_RADAR_VIL_RESPONSE: DISPLAY_VIL_DATA,
    'weather_radarVIL': DISPLAY_VIL_DATA,
    'vilData': DISPLAY_VIL_DATA,
    'vil_data': DISPLAY_VIL_DATA,
    
    WEATHER_RADAR_PRECIPITATION_RESPONSE: DISPLAY_PRECIPITATION_DATA,
    'weather_radarPrecipitation': DISPLAY_PRECIPITATION_DATA,
    'precipitationData': DISPLAY_PRECIPITATION_DATA,
    'precipitation_data': DISPLAY_PRECIPITATION_DATA,
    
    WEATHER_RADAR_ECHO_TOP_RESPONSE: DISPLAY_ECHO_TOP_DATA,
    'echo_top': DISPLAY_ECHO_TOP_DATA,
    'echo_top_data': DISPLAY_ECHO_TOP_DATA,
    
    WEATHER_RADAR_STORM_CELL_RESPONSE: DISPLAY_STORM_CELL_DATA,
    'storm_cell': DISPLAY_STORM_CELL_DATA,
    'storm_cell_data': DISPLAY_STORM_CELL_DATA,
    
    # Display translations
    'displayMode': DISPLAY_MODE_REQUEST,
    'display_mode': DISPLAY_MODE_REQUEST,
    'displayStatus': DISPLAY_STATUS_REQUEST,
    'display_status': DISPLAY_STATUS_REQUEST,
    'displayData': DISPLAY_DATA_REQUEST,
    'display_data': DISPLAY_DATA_REQUEST,
    
    # Mode change translations
    'modeChange': DISPLAY_MODE_CHANGE,
    'mode_change': DISPLAY_MODE_CHANGE,
    'modeChangeCompletion': DISPLAY_MODE_CHANGE_COMPLETION,
    'mode_change_completion': DISPLAY_MODE_CHANGE_COMPLETION,
    
    # Status word translation
    'status_word': 'display_status_word'
}

def get_message_type(message: Any) -> Optional[str]:
    """
    Extract message type from various message formats.
    
    Args:
        message: Message object or dictionary
        
    Returns:
        str: Message type or None if not found
    """
    if not message:
        return None
        
    # Extract from dictionary message
    if isinstance(message, dict):
        # Check top-level message_type field
        if 'message_type' in message:
            return message['message_type']
            
        # Check in metadata dictionary
        if 'metadata' in message and isinstance(message['metadata'], dict):
            msg_type = message['metadata'].get('message_type')
            if msg_type:
                return msg_type
                
        # Check in additional_info dictionary
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            msg_type = message['additional_info'].get('message_type')
            if msg_type:
                return msg_type
    
    # Extract from object attributes
    elif hasattr(message, 'message_type'):
        return message.message_type
        
    # Check object metadata
    elif hasattr(message, 'metadata'):
        metadata = message.metadata
        if isinstance(metadata, dict) and 'message_type' in metadata:
            return metadata['message_type']
            
    # Check object additional_info
    elif hasattr(message, 'additional_info'):
        additional_info = message.additional_info
        if isinstance(additional_info, dict) and 'message_type' in additional_info:
            return additional_info['message_type']
    
    # No message type found
    return None

def get_command_type(message: Any) -> Optional[str]:
    """
    Extract command type from message metadata or determine based on message type.
    
    Args:
        message: Message object or dictionary
        
    Returns:
        str: Command type or None if not found
    """
    if not message:
        return None
        
    # Extract from dictionary message
    if isinstance(message, dict):
        # Check top-level command_type field
        if 'command_type' in message:
            return message['command_type']
            
        # Check in metadata dictionary
        if 'metadata' in message and isinstance(message['metadata'], dict):
            cmd_type = message['metadata'].get('command_type')
            if cmd_type:
                return cmd_type
                
        # Check in additional_info dictionary
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            cmd_type = message['additional_info'].get('command_type')
            if cmd_type:
                return cmd_type
    
    # Extract from object attributes
    elif hasattr(message, 'command_type'):
        return message.command_type
        
    # Check object metadata
    elif hasattr(message, 'metadata'):
        metadata = message.metadata
        if isinstance(metadata, dict) and 'command_type' in metadata:
            return metadata['command_type']
            
    # Check object additional_info
    elif hasattr(message, 'additional_info'):
        additional_info = message.additional_info
        if isinstance(additional_info, dict) and 'command_type' in additional_info:
            return additional_info['command_type']
    
    # If no command_type found, try to derive from message_type
    message_type = get_message_type(message)
    if not message_type:
        return None
        
    # Derive command type from message type
    message_type_lower = message_type.lower()
    
    if 'mode' in message_type_lower and 'change' in message_type_lower:
        return DISPLAY_COMMAND_TYPE_MODE
    elif 'data' in message_type_lower:
        return DISPLAY_COMMAND_TYPE_DATA
    elif 'status' in message_type_lower:
        return DISPLAY_COMMAND_TYPE_STATUS
    elif 'show' in message_type_lower:
        return DISPLAY_COMMAND_TYPE_SHOW
    
    # No command type found
    return None

def is_message_type(message: Any, expected_type: str) -> bool:
    """
    Check if message has expected message type.
    
    Args:
        message: Message object or dictionary
        expected_type: Expected message type
        
    Returns:
        bool: True if message matches expected type
    """
    if not expected_type:
        return False
        
    msg_type = get_message_type(message)
    if not msg_type:
        return False
        
    # Case-insensitive comparison
    return msg_type.lower() == expected_type.lower()

def is_command_type(message: Any, expected_type: str) -> bool:
    """
    Check if message has expected command type.
    
    Args:
        message: Message object or dictionary
        expected_type: Expected command type
        
    Returns:
        bool: True if message matches expected command type
    """
    if not expected_type:
        return False
        
    cmd_type = get_command_type(message)
    if not cmd_type:
        return False
        
    # Case-insensitive comparison
    return cmd_type.lower() == expected_type.lower()

def is_vil_message(message: Any) -> bool:
    """
    Check if message is a VIL data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a VIL data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    # Check if message type matches VIL data constants
    msg_type_lower = msg_type.lower()
    return ('vil' in msg_type_lower or 
            msg_type_lower == WEATHER_RADAR_VIL_RESPONSE.lower() or
            msg_type_lower == WEATHER_RADAR_VIL_REQUEST.lower() or
            msg_type_lower == DISPLAY_VIL_DATA.lower())

def is_precipitation_message(message: Any) -> bool:
    """
    Check if message is a precipitation data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a precipitation data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    # Check if message type matches precipitation data constants
    msg_type_lower = msg_type.lower()
    return ('precipitation' in msg_type_lower or
            msg_type_lower == WEATHER_RADAR_PRECIPITATION_RESPONSE.lower() or
            msg_type_lower == WEATHER_RADAR_PRECIPITATION_REQUEST.lower() or
            msg_type_lower == DISPLAY_PRECIPITATION_DATA.lower())

def is_echo_top_message(message: Any) -> bool:
    """
    Check if message is an echo top data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is an echo top data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    # Check if message type matches echo top data constants
    msg_type_lower = msg_type.lower()
    return ('echo_top' in msg_type_lower or
            msg_type_lower == WEATHER_RADAR_ECHO_TOP_RESPONSE.lower() or
            msg_type_lower == WEATHER_RADAR_ECHO_TOP_REQUEST.lower() or
            msg_type_lower == DISPLAY_ECHO_TOP_DATA.lower())

def is_storm_cell_message(message: Any) -> bool:
    """
    Check if message is a storm cell data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a storm cell data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    # Check if message type matches storm cell data constants
    msg_type_lower = msg_type.lower()
    return ('storm_cell' in msg_type_lower or
            msg_type_lower == WEATHER_RADAR_STORM_CELL_RESPONSE.lower() or
            msg_type_lower == WEATHER_RADAR_STORM_CELL_REQUEST.lower() or
            msg_type_lower == DISPLAY_STORM_CELL_DATA.lower())

def is_mode_change_message(message: Any) -> bool:
    """
    Check if message is a mode change message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a mode change message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return ('modechange' in msg_type_lower.replace('_', '') or
            'mode_change' in msg_type_lower)

def translate_message_type(message_type):
    """
    Translate a message type to its display-specific equivalent.
    
    Args:
        message_type: The original message type
        
    Returns:
        str: The translated message type, or the original if no translation exists
    """
    if not message_type:
        return None
        
    # Check if there's a direct mapping
    if message_type in MESSAGE_TYPE_MAPPING:
        translated_type = MESSAGE_TYPE_MAPPING[message_type]
        logger.debug(f"Translated message type: {message_type} -> {translated_type}")
        return translated_type
        
    # Check for partial matches
    message_type_lower = message_type.lower()
    
    # Check for VIL data
    if 'vil' in message_type_lower:
        logger.debug(f"Translated message type based on partial match: {message_type} -> {DISPLAY_VIL_DATA}")
        return DISPLAY_VIL_DATA
        
    # Check for precipitation data
    if 'precipitation' in message_type_lower:
        logger.debug(f"Translated message type based on partial match: {message_type} -> {DISPLAY_PRECIPITATION_DATA}")
        return DISPLAY_PRECIPITATION_DATA
        
    # Check for echo top data
    if 'echo_top' in message_type_lower:
        logger.debug(f"Translated message type based on partial match: {message_type} -> {DISPLAY_ECHO_TOP_DATA}")
        return DISPLAY_ECHO_TOP_DATA
        
    # Check for storm cell data
    if 'storm_cell' in message_type_lower:
        logger.debug(f"Translated message type based on partial match: {message_type} -> {DISPLAY_STORM_CELL_DATA}")
        return DISPLAY_STORM_CELL_DATA
        
    # Check for mode change
    if 'mode_change' in message_type_lower:
        logger.debug(f"Translated message type based on partial match: {message_type} -> {DISPLAY_MODE_CHANGE}")
        return DISPLAY_MODE_CHANGE
        
    # No translation found, return original
    return message_type

def get_command_type(message):
    """
    Extract command type from various message formats.
    
    Args:
        message: The message object, which could be a dict, object, or other format
        
    Returns:
        str: The command type or None if not found
    """
    if isinstance(message, dict):
        # Check direct command_type key
        if 'command_type' in message:
            return message['command_type']
        
        # Check in metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            cmd_type = message['metadata'].get('command_type')
            if cmd_type:
                return cmd_type
        
        # Check in additional_info (legacy format)
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            return message['additional_info'].get('command_type')
    
    # Handle object attributes
    elif hasattr(message, 'command_type'):
        return message.command_type
    elif hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
        return message.metadata.get('command_type')
    
    return None

def is_command_type(message, expected_type):
    """
    Check if message command type matches expected type, with case-insensitive comparison.
    
    Args:
        message: The message to check
        expected_type: The expected command type
        
    Returns:
        bool: True if the command type matches, False otherwise
    """
    cmd_type = get_command_type(message)
    if not cmd_type or not expected_type:
        return False
    
    return cmd_type.lower() == expected_type.lower()
