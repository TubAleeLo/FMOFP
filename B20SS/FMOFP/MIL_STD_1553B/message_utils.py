"""
MIL-STD-1553B Message Type Utilities

Provides utility functions for working with message types in MIL-STD-1553B messages.
These functions mirror those in local_messaging/message_types.py to avoid
cross-module dependencies.
"""

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Weather Radar Message Types
WEATHER_RADAR_MODE_CHANGE_REQUEST = 'weather_radarModeChangeRequest'
WEATHER_RADAR_MODE_CHANGE_RESPONSE = 'weather_radarModeChangeResponse'
WEATHER_RADAR_STATUS_REQUEST = 'weather_radarStatusRequest'
WEATHER_RADAR_STATUS_RESPONSE = 'weather_radarStatusResponse'
WEATHER_RADAR_VIL_REQUEST = 'weather_radarVILRequest'
WEATHER_RADAR_VIL_RESPONSE = 'weather_radarVILResponse'
WEATHER_RADAR_PRECIPITATION_REQUEST = 'weather_radarPrecipitationRequest'
WEATHER_RADAR_PRECIPITATION_RESPONSE = 'weather_radarPrecipitationResponse'

# Display Message Types
DISPLAY_MODE_REQUEST = 'display_mode_request'
DISPLAY_MODE_RESPONSE = 'display_mode_response'
DISPLAY_MODE_CHANGE = 'mode_change'
DISPLAY_MODE_CHANGE_COMPLETION = 'mode_change_completion'

# Command Types
COMMAND_TYPE_MODE_CHANGE = 'mode_change'
COMMAND_TYPE_MODE_CHANGE_COMPLETE = 'mode_change_complete'
COMMAND_TYPE_DATA_REQUEST = 'data_request'
COMMAND_TYPE_DATA_RESPONSE = 'data_response'
COMMAND_TYPE_VIL_DATA = 'vil_data'
COMMAND_TYPE_PRECIPITATION_DATA = 'precipitation_data'


def get_message_type(message):
    """
    Extract message type from various message formats.
    
    Args:
        message: The message object, which could be a dict, object, or other format
        
    Returns:
        str: The message type or None if not found
    """
    if isinstance(message, dict):
        # Check direct message_type key
        if 'message_type' in message:
            return message['message_type']
        
        # Check in metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            msg_type = message['metadata'].get('message_type')
            if msg_type:
                return msg_type
        
        # Check in additional_info (legacy format)
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            return message['additional_info'].get('message_type')
    
    # Handle object attributes
    elif hasattr(message, 'message_type'):
        return message.message_type
    elif hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
        return message.metadata.get('message_type')
    
    return None


def is_message_type(message, expected_type):
    """
    Check if message matches expected type, with case-insensitive comparison.
    
    Args:
        message: The message to check
        expected_type: The expected message type
        
    Returns:
        bool: True if the message type matches, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type or not expected_type:
        return False
    
    return msg_type.lower() == expected_type.lower()


def is_vil_message(message):
    """
    Check if a message is a VIL data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a VIL data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == WEATHER_RADAR_VIL_REQUEST.lower() or 
            msg_type_lower == WEATHER_RADAR_VIL_RESPONSE.lower() or 
            'vil' in msg_type_lower)


def is_precipitation_message(message):
    """
    Check if a message is a precipitation data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a precipitation data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == WEATHER_RADAR_PRECIPITATION_REQUEST.lower() or 
            msg_type_lower == WEATHER_RADAR_PRECIPITATION_RESPONSE.lower() or 
            'precipitation' in msg_type_lower)


def is_mode_change_message(message):
    """
    Check if a message is a mode change message.
    
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

# Additional MIL-STD-1553B specific message utilities

def get_command_type(message):
    """
    Extract command type from message.
    
    Args:
        message: The message to check
        
    Returns:
        str: Command type or None if not found
    """
    if isinstance(message, dict):
        if 'command_type' in message:
            return message['command_type']
        
        if 'metadata' in message and isinstance(message['metadata'], dict):
            cmd_type = message['metadata'].get('command_type')
            if cmd_type:
                return cmd_type
                
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            return message['additional_info'].get('command_type')
    
    elif hasattr(message, 'command_type'):
        return message.command_type
    
    return None


def is_transfer_message(message):
    """
    Check if a message is part of a block transfer.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is part of a transfer, False otherwise
    """
    if isinstance(message, dict):
        # Check direct transfer flags
        if any(key in message for key in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']):
            return True
            
        # Check metadata for transfer flags
        if 'metadata' in message and isinstance(message['metadata'], dict):
            if any(key in message['metadata'] for key in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']):
                return True
        
        # Check by transfer-related message types
        msg_type = get_message_type(message)
        if msg_type and any(transfer_type in msg_type.lower() for transfer_type in ['transfer_init', 'transfer_data', 'transfer_complete']):
            return True
    
    return False
