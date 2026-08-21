"""
Centralized message type definitions for the Flight Management System.
These constants should be used throughout the codebase instead of string literals.
This ensures consistency with MIL-STD-1553B protocol requirements.

Following the same pattern as the radar messaging system.
"""

# FMS Message Types
FMS_MODE_CHANGE_REQUEST = 'fms_modeChangeRequest'
FMS_MODE_CHANGE_RESPONSE = 'fms_modeChangeResponse'
FMS_STATUS_REQUEST = 'fms_statusRequest'
FMS_STATUS_RESPONSE = 'fms_statusResponse'
FMS_ATTITUDE_UPDATE_REQUEST = 'fms_attitudeUpdateRequest'
FMS_ATTITUDE_UPDATE_RESPONSE = 'fms_attitudeUpdateResponse'
FMS_NAVIGATION_UPDATE_REQUEST = 'fms_navigationUpdateRequest'
FMS_NAVIGATION_UPDATE_RESPONSE = 'fms_navigationUpdateResponse'
FMS_MANEUVER_REQUEST = 'fms_maneuverRequest'
FMS_MANEUVER_RESPONSE = 'fms_maneuverResponse'
FMS_COMMAND = 'fmsCommand'
FMS_DATA = 'fmsData'

# FCS Message Types
FCS_CONTROL_INPUT_REQUEST = 'fcs_controlInputRequest'
FCS_CONTROL_INPUT_RESPONSE = 'fcs_controlInputResponse'
FCS_ORIENTATION_DATA_REQUEST = 'fcs_orientationDataRequest'
FCS_ORIENTATION_DATA_RESPONSE = 'fcs_orientationDataResponse'
FCS_STATUS_REQUEST = 'fcs_statusRequest'
FCS_STATUS_RESPONSE = 'fcs_statusResponse'
FCS_MODE_CHANGE_REQUEST = 'fcs_modeChangeRequest'
FCS_MODE_CHANGE_RESPONSE = 'fcs_modeChangeResponse'

# Command Types
COMMAND_TYPE_MODE_CHANGE = 'mode_change'
COMMAND_TYPE_MODE_CHANGE_COMPLETE = 'mode_change_complete'
COMMAND_TYPE_DATA_REQUEST = 'data_request'
COMMAND_TYPE_DATA_RESPONSE = 'data_response'
COMMAND_TYPE_STATUS_REQUEST = 'status_request'
COMMAND_TYPE_STATUS_RESPONSE = 'status_response'
COMMAND_TYPE_ATTITUDE_UPDATE = 'attitude_update'
COMMAND_TYPE_NAVIGATION_UPDATE = 'navigation_update'
COMMAND_TYPE_MANEUVER_REQUEST = 'maneuver_request'
COMMAND_TYPE_CONTROL_INPUT = 'control_input'
COMMAND_TYPE_CONTROL_INPUT_COMPLETE = 'control_input_complete'
COMMAND_TYPE_ORIENTATION_DATA = 'orientation_data'

# Helper functions for message type detection
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
    return (msg_type_lower == FMS_MODE_CHANGE_REQUEST.lower() or 
            msg_type_lower == FMS_MODE_CHANGE_RESPONSE.lower() or 
            'modechange' in msg_type_lower.replace('_', '') or
            'mode_change' in msg_type_lower)


def is_attitude_update_message(message):
    """
    Check if a message is an attitude update message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is an attitude update message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == FMS_ATTITUDE_UPDATE_REQUEST.lower() or 
            msg_type_lower == FMS_ATTITUDE_UPDATE_RESPONSE.lower() or 
            'attitude' in msg_type_lower)


def is_status_message(message):
    """
    Check if a message is a status message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a status message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == FMS_STATUS_REQUEST.lower() or 
            msg_type_lower == FMS_STATUS_RESPONSE.lower() or 
            msg_type_lower == FCS_STATUS_REQUEST.lower() or
            msg_type_lower == FCS_STATUS_RESPONSE.lower() or
            'status' in msg_type_lower)


def is_control_input_message(message):
    """
    Check if a message is a flight control input message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a control input message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == FCS_CONTROL_INPUT_REQUEST.lower() or 
            msg_type_lower == FCS_CONTROL_INPUT_RESPONSE.lower() or 
            'controlinput' in msg_type_lower.replace('_', '') or
            'control_input' in msg_type_lower)


def is_orientation_data_message(message):
    """
    Check if a message is an orientation data message.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is an orientation data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == FCS_ORIENTATION_DATA_REQUEST.lower() or 
            msg_type_lower == FCS_ORIENTATION_DATA_RESPONSE.lower() or 
            'orientationdata' in msg_type_lower.replace('_', '') or
            'orientation_data' in msg_type_lower)
