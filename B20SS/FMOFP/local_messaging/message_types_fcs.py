"""
Flight Control System Message Types

This module defines the message type constants for the Flight Control System
to ensure proper integration with the MIL-STD-1553B protocol.
"""

# Flight Control System Control Input Messages
FCS_CONTROL_INPUT_REQUEST = "FCS_CONTROL_INPUT_REQUEST"
FCS_CONTROL_INPUT_RESPONSE = "FCS_CONTROL_INPUT_RESPONSE"

# Flight Control System Orientation Data Messages
FCS_ORIENTATION_DATA_REQUEST = "FCS_ORIENTATION_DATA_REQUEST"
FCS_ORIENTATION_DATA_RESPONSE = "FCS_ORIENTATION_DATA_RESPONSE"

# Flight Control System Status Messages
FCS_STATUS_REQUEST = "FCS_STATUS_REQUEST"
FCS_STATUS_RESPONSE = "FCS_STATUS_RESPONSE"

# Flight Control System Mode Change Messages
FCS_MODE_CHANGE_REQUEST = "FCS_MODE_CHANGE_REQUEST"
FCS_MODE_CHANGE_RESPONSE = "FCS_MODE_CHANGE_RESPONSE"

# Helper functions for message type detection
def is_control_input_message(message):
    """Check if a message is a control input message"""
    if not isinstance(message, dict):
        return False
    
    message_type = message.get('message_type', '').lower()
    command_type = message.get('command_type', '').lower()
    
    return (
        'control_input' in message_type or
        'control_input' in command_type or
        message.get('command_word') == FCS_CONTROL_INPUT_REQUEST
    )

def is_orientation_data_message(message):
    """Check if a message is an orientation data message"""
    if not isinstance(message, dict):
        return False
    
    message_type = message.get('message_type', '').lower()
    command_type = message.get('command_type', '').lower()
    
    return (
        'orientation_data' in message_type or
        'orientation_data' in command_type or
        message.get('command_word') == FCS_ORIENTATION_DATA_REQUEST
    )

def is_fcs_status_message(message):
    """Check if a message is a FCS status message"""
    if not isinstance(message, dict):
        return False
    
    message_type = message.get('message_type', '').lower()
    command_type = message.get('command_type', '').lower()
    
    return (
        'fcs_status' in message_type or
        'status' in command_type or
        message.get('command_word') == FCS_STATUS_REQUEST
    )

def is_fcs_mode_change_message(message):
    """Check if a message is a FCS mode change message"""
    if not isinstance(message, dict):
        return False
    
    message_type = message.get('message_type', '').lower()
    command_type = message.get('command_type', '').lower()
    
    return (
        'fcs_mode' in message_type or
        'mode_change' in command_type or
        message.get('command_word') == FCS_MODE_CHANGE_REQUEST
    )
