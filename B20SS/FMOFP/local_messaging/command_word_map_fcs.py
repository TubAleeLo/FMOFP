"""
Command Word Map for Flight Control System

This module defines the command word mappings for the Flight Control System
to ensure proper integration with the MIL-STD-1553B protocol.
"""

class CommandWord:
    """
    Defines a 1553B command word with name, value, and description.
    """
    def __init__(self, name, value, description=None):
        self.name = name
        self.value = value  
        self.description = description or ""
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

# Command word constants for Flight Control System
FCS_BASE_COMMAND = 0x4000  # Base command value for FCS commands - different range from FMS

# Flight Control System command words
FCS_COMMAND_WORDS = {
    FCS_CONTROL_INPUT_REQUEST: CommandWord(
        name=FCS_CONTROL_INPUT_REQUEST,
        value=FCS_BASE_COMMAND + 0x01,  # 0x4001
        description="Request to set control input for flight control surfaces"
    ),
    FCS_CONTROL_INPUT_RESPONSE: CommandWord(
        name=FCS_CONTROL_INPUT_RESPONSE,
        value=FCS_BASE_COMMAND + 0x02,  # 0x4002
        description="Response to control input request"
    ),
    FCS_ORIENTATION_DATA_REQUEST: CommandWord(
        name=FCS_ORIENTATION_DATA_REQUEST,
        value=FCS_BASE_COMMAND + 0x03,  # 0x4003
        description="Request for aircraft orientation data"
    ),
    FCS_ORIENTATION_DATA_RESPONSE: CommandWord(
        name=FCS_ORIENTATION_DATA_RESPONSE,
        value=FCS_BASE_COMMAND + 0x04,  # 0x4004
        description="Response containing aircraft orientation data"
    ),
    FCS_STATUS_REQUEST: CommandWord(
        name=FCS_STATUS_REQUEST,
        value=FCS_BASE_COMMAND + 0x05,  # 0x4005
        description="Request for flight control system status"
    ),
    FCS_STATUS_RESPONSE: CommandWord(
        name=FCS_STATUS_RESPONSE,
        value=FCS_BASE_COMMAND + 0x06,  # 0x4006
        description="Response with flight control system status information"
    ),
    FCS_MODE_CHANGE_REQUEST: CommandWord(
        name=FCS_MODE_CHANGE_REQUEST,
        value=FCS_BASE_COMMAND + 0x07,  # 0x4007
        description="Request to change flight control system mode"
    ),
    FCS_MODE_CHANGE_RESPONSE: CommandWord(
        name=FCS_MODE_CHANGE_RESPONSE,
        value=FCS_BASE_COMMAND + 0x08,  # 0x4008
        description="Response to flight control system mode change request"
    )
}

# Dictionary mapping command word values to command word names
# Used for lookups when decoding 1553B messages
FCS_COMMAND_VALUE_MAP = {cmd.value: name for name, cmd in FCS_COMMAND_WORDS.items()}

def get_fcs_command_word(name):
    """
    Get command word by name
    
    Args:
        name: The name of the command word to retrieve
        
    Returns:
        CommandWord or None if not found
    """
    return FCS_COMMAND_WORDS.get(name)

def get_fcs_command_name(value):
    """
    Get command name by value
    
    Args:
        value: The value of the command word to look up
        
    Returns:
        str: Command name or None if not found
    """
    return FCS_COMMAND_VALUE_MAP.get(value)

def register_fcs_command_words():
    """
    Register FCS command words with the global command registry
    """
    from FMOFP.local_messaging.command_word_map import COMMAND_REGISTRY
    
    # Register each FCS command word in the global registry
    for name, cmd_word in FCS_COMMAND_WORDS.items():
        hex_value = f"0x{cmd_word.value:04X}"
        COMMAND_REGISTRY[name] = hex_value
