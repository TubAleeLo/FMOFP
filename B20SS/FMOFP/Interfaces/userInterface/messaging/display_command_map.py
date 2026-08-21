"""
Display Command Map

Defines command word constants and utilities for the display system.
Uses centralized message types and address utilities instead of dynamic registration.
"""

import os
from typing import Dict, Optional
from ..displays.base_display import DisplayType
from .display_address_utils import (
    DISPLAY_SYSTEM_ID,
    PFD_SUBADDRESS,
    MFD_SUBADDRESS,
    EICAS_SUBADDRESS,
    RADAR_DISPLAY_SUBADDRESS,
    TSD_SUBADDRESS,
    SMS_SUBADDRESS,
    DISPLAY_SUBADDRESS_MAP,
    get_display_subaddress
)
from .display_message_types import (
    DISPLAY_COMMAND_TYPE_SHOW,
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_DATA,
    DISPLAY_COMMAND_TYPE_STATUS,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE
)
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Define display types and message types
DISPLAY_TYPES = {
    'pfd': DisplayType.PFD,
    'mfd': DisplayType.MFD,
    'eicas': DisplayType.EICAS,
    'radar_display': DisplayType.RADAR,
    'weather_radar': DisplayType.RADAR,  # Add weather_radar mapping - will become a sub-type of display later
    'tsd': DisplayType.TSD,
    'sms': DisplayType.SMS
}

# Message types using constants
MESSAGE_TYPES = [
    DISPLAY_COMMAND_TYPE_SHOW,
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_DATA,
    DISPLAY_COMMAND_TYPE_STATUS
]

# Display subaddresses from address utilities
DISPLAY_SUBADDRESSES = DISPLAY_SUBADDRESS_MAP

# Command word cache for performance
COMMAND_WORD_CACHE: Dict[str, str] = {}

def construct_command_word(rt_address: int, t_r_bit: int, subaddress: int, word_count: int) -> str:
    """
    Construct a MIL-STD-1553B command word from components.
    
    Args:
        rt_address: 5-bit RT address (0-31)
        t_r_bit: Transmit/receive bit (0=transmit, 1=receive)
        subaddress: 5-bit subaddress (1-30, 0/31 for mode codes)
        word_count: 5-bit word count (1-32, 0 means 32)
        
    Returns:
        str: Binary command word
    """
    # Validate inputs
    if rt_address < 0 or rt_address > 31:
        raise ValueError(f"Invalid RT address: {rt_address}")
    
    if t_r_bit not in [0, 1]:
        raise ValueError(f"Invalid T/R bit: {t_r_bit}")
    
    if subaddress < 0 or subaddress > 31:
        raise ValueError(f"Invalid subaddress: {subaddress}")
    
    if word_count < 0 or word_count > 32:
        raise ValueError(f"Invalid word count: {word_count}")
    
    # Convert to 0 for word count of 32
    if word_count == 32:
        word_count = 0
    
    # Format components as binary strings
    rt_address_bin = format(rt_address, '05b')
    t_r_bit_bin = format(t_r_bit, '01b')
    subaddress_bin = format(subaddress, '05b')
    word_count_bin = format(word_count, '05b')
    
    # Combine components
    return rt_address_bin + t_r_bit_bin + subaddress_bin + word_count_bin

def get_command_word(display_id: str, t_r_bit: int, command_type: str) -> str:
    """
    Get a command word for the specified display and command type.
    
    Args:
        display_id: Display identifier (e.g., 'pfd', 'mfd')
        t_r_bit: Transmit/receive bit (0=transmit, 1=receive)
        command_type: Type of command (e.g., 'show', 'mode', 'data')
        
    Returns:
        str: Binary command word
    """
    # Create cache key
    cache_key = f"{display_id}_{t_r_bit}_{command_type}"
    
    # Check cache
    if cache_key in COMMAND_WORD_CACHE:
        return COMMAND_WORD_CACHE[cache_key]
    
    # Get RT address for display system
    rt_address = 11  # Display system RT address is 11 (binary 01011)
    
    # Get subaddress for display type
    try:
        subaddress = get_display_subaddress(display_id)
    except ValueError as e:
        logger.error(f"Invalid display ID '{display_id}': {e}")
        raise ValueError(f"Invalid display ID: {display_id}")
    
    # Determine word count based on command type
    if command_type == DISPLAY_COMMAND_TYPE_SHOW:
        word_count = 1
    elif command_type == DISPLAY_COMMAND_TYPE_MODE or command_type == DISPLAY_COMMAND_TYPE_MODE_CHANGE:
        word_count = 2  # Mode value + command type
    elif command_type == DISPLAY_COMMAND_TYPE_DATA:
        word_count = 3  # Default data word count
    elif command_type == DISPLAY_COMMAND_TYPE_STATUS:
        word_count = 1
    else:
        raise ValueError(f"Invalid command type: {command_type}")
    
    # Construct command word
    command_word = construct_command_word(rt_address, t_r_bit, subaddress, word_count)
    
    # Cache result
    COMMAND_WORD_CACHE[cache_key] = command_word
    
    return command_word

# Define command word constants for each display type and message type
# PFD Command Words
PFD_SHOW_REQUEST = get_command_word('pfd', 0, DISPLAY_COMMAND_TYPE_SHOW)
PFD_SHOW_RESPONSE = get_command_word('pfd', 1, DISPLAY_COMMAND_TYPE_SHOW)
PFD_MODE_REQUEST = get_command_word('pfd', 0, DISPLAY_COMMAND_TYPE_MODE)
PFD_MODE_RESPONSE = get_command_word('pfd', 1, DISPLAY_COMMAND_TYPE_MODE)
PFD_DATA_REQUEST = get_command_word('pfd', 0, DISPLAY_COMMAND_TYPE_DATA)
PFD_DATA_RESPONSE = get_command_word('pfd', 1, DISPLAY_COMMAND_TYPE_DATA)
PFD_STATUS_REQUEST = get_command_word('pfd', 0, DISPLAY_COMMAND_TYPE_STATUS)
PFD_STATUS_RESPONSE = get_command_word('pfd', 1, DISPLAY_COMMAND_TYPE_STATUS)

# MFD Command Words
MFD_SHOW_REQUEST = get_command_word('mfd', 0, DISPLAY_COMMAND_TYPE_SHOW)
MFD_SHOW_RESPONSE = get_command_word('mfd', 1, DISPLAY_COMMAND_TYPE_SHOW)
MFD_MODE_REQUEST = get_command_word('mfd', 0, DISPLAY_COMMAND_TYPE_MODE)
MFD_MODE_RESPONSE = get_command_word('mfd', 1, DISPLAY_COMMAND_TYPE_MODE)
MFD_DATA_REQUEST = get_command_word('mfd', 0, DISPLAY_COMMAND_TYPE_DATA)
MFD_DATA_RESPONSE = get_command_word('mfd', 1, DISPLAY_COMMAND_TYPE_DATA)
MFD_STATUS_REQUEST = get_command_word('mfd', 0, DISPLAY_COMMAND_TYPE_STATUS)
MFD_STATUS_RESPONSE = get_command_word('mfd', 1, DISPLAY_COMMAND_TYPE_STATUS)

# EICAS Command Words
EICAS_SHOW_REQUEST = get_command_word('eicas', 0, DISPLAY_COMMAND_TYPE_SHOW)
EICAS_SHOW_RESPONSE = get_command_word('eicas', 1, DISPLAY_COMMAND_TYPE_SHOW)
EICAS_MODE_REQUEST = get_command_word('eicas', 0, DISPLAY_COMMAND_TYPE_MODE)
EICAS_MODE_RESPONSE = get_command_word('eicas', 1, DISPLAY_COMMAND_TYPE_MODE)
EICAS_DATA_REQUEST = get_command_word('eicas', 0, DISPLAY_COMMAND_TYPE_DATA)
EICAS_DATA_RESPONSE = get_command_word('eicas', 1, DISPLAY_COMMAND_TYPE_DATA)
EICAS_STATUS_REQUEST = get_command_word('eicas', 0, DISPLAY_COMMAND_TYPE_STATUS)
EICAS_STATUS_RESPONSE = get_command_word('eicas', 1, DISPLAY_COMMAND_TYPE_STATUS)

# Radar Display Command Words
RADAR_DISPLAY_SHOW_REQUEST = get_command_word('radar_display', 0, DISPLAY_COMMAND_TYPE_SHOW)
RADAR_DISPLAY_SHOW_RESPONSE = get_command_word('radar_display', 1, DISPLAY_COMMAND_TYPE_SHOW)
RADAR_DISPLAY_MODE_REQUEST = get_command_word('radar_display', 0, DISPLAY_COMMAND_TYPE_MODE)
RADAR_DISPLAY_MODE_RESPONSE = get_command_word('radar_display', 1, DISPLAY_COMMAND_TYPE_MODE)
RADAR_DISPLAY_DATA_REQUEST = get_command_word('radar_display', 0, DISPLAY_COMMAND_TYPE_DATA)
RADAR_DISPLAY_DATA_RESPONSE = get_command_word('radar_display', 1, DISPLAY_COMMAND_TYPE_DATA)
RADAR_DISPLAY_STATUS_REQUEST = get_command_word('radar_display', 0, DISPLAY_COMMAND_TYPE_STATUS)
RADAR_DISPLAY_STATUS_RESPONSE = get_command_word('radar_display', 1, DISPLAY_COMMAND_TYPE_STATUS)

# TSD Command Words
TSD_SHOW_REQUEST = get_command_word('tsd', 0, DISPLAY_COMMAND_TYPE_SHOW)
TSD_SHOW_RESPONSE = get_command_word('tsd', 1, DISPLAY_COMMAND_TYPE_SHOW)
TSD_MODE_REQUEST = get_command_word('tsd', 0, DISPLAY_COMMAND_TYPE_MODE)
TSD_MODE_RESPONSE = get_command_word('tsd', 1, DISPLAY_COMMAND_TYPE_MODE)
TSD_DATA_REQUEST = get_command_word('tsd', 0, DISPLAY_COMMAND_TYPE_DATA)
TSD_DATA_RESPONSE = get_command_word('tsd', 1, DISPLAY_COMMAND_TYPE_DATA)
TSD_STATUS_REQUEST = get_command_word('tsd', 0, DISPLAY_COMMAND_TYPE_STATUS)
TSD_STATUS_RESPONSE = get_command_word('tsd', 1, DISPLAY_COMMAND_TYPE_STATUS)

# SMS Command Words
SMS_SHOW_REQUEST = get_command_word('sms', 0, DISPLAY_COMMAND_TYPE_SHOW)
SMS_SHOW_RESPONSE = get_command_word('sms', 1, DISPLAY_COMMAND_TYPE_SHOW)
SMS_MODE_REQUEST = get_command_word('sms', 0, DISPLAY_COMMAND_TYPE_MODE)
SMS_MODE_RESPONSE = get_command_word('sms', 1, DISPLAY_COMMAND_TYPE_MODE)
SMS_DATA_REQUEST = get_command_word('sms', 0, DISPLAY_COMMAND_TYPE_DATA)
SMS_DATA_RESPONSE = get_command_word('sms', 1, DISPLAY_COMMAND_TYPE_DATA)
SMS_STATUS_REQUEST = get_command_word('sms', 0, DISPLAY_COMMAND_TYPE_STATUS)
SMS_STATUS_RESPONSE = get_command_word('sms', 1, DISPLAY_COMMAND_TYPE_STATUS)

# Create request maps for basic message types
SHOW_REQUEST_MAP = {
    'pfd': PFD_SHOW_REQUEST,
    'mfd': MFD_SHOW_REQUEST,
    'eicas': EICAS_SHOW_REQUEST,
    'radar_display': RADAR_DISPLAY_SHOW_REQUEST,
    'weather_radar': RADAR_DISPLAY_SHOW_REQUEST,  # Alias for radar_display
    'tsd': TSD_SHOW_REQUEST,
    'sms': SMS_SHOW_REQUEST
}

MODE_REQUEST_MAP = {
    'pfd': PFD_MODE_REQUEST,
    'mfd': MFD_MODE_REQUEST,
    'eicas': EICAS_MODE_REQUEST,
    'radar_display': RADAR_DISPLAY_MODE_REQUEST,
    'weather_radar': RADAR_DISPLAY_MODE_REQUEST,  # Alias for radar_display
    'tsd': TSD_MODE_REQUEST,
    'sms': SMS_MODE_REQUEST
}

DATA_REQUEST_MAP = {
    'pfd': PFD_DATA_REQUEST,
    'mfd': MFD_DATA_REQUEST,
    'eicas': EICAS_DATA_REQUEST,
    'radar_display': RADAR_DISPLAY_DATA_REQUEST,
    'weather_radar': RADAR_DISPLAY_DATA_REQUEST,  # Alias for radar_display
    'tsd': TSD_DATA_REQUEST,
    'sms': SMS_DATA_REQUEST
}

STATUS_REQUEST_MAP = {
    'pfd': PFD_STATUS_REQUEST,
    'mfd': MFD_STATUS_REQUEST,
    'eicas': EICAS_STATUS_REQUEST,
    'radar_display': RADAR_DISPLAY_STATUS_REQUEST,
    'weather_radar': RADAR_DISPLAY_STATUS_REQUEST,  # Alias for radar_display
    'tsd': TSD_STATUS_REQUEST,
    'sms': SMS_STATUS_REQUEST
}

def get_display_command_word(display_id: str, command_type: str) -> str:
    """
    Get command word for display command.
    
    Args:
        display_id: Display identifier (e.g., 'pfd', 'mfd')
        command_type: Type of command ('show', 'mode', 'mode_change', 'data', 'status')
        
    Returns:
        Command word binary string
        
    Raises:
        ValueError: If display_id or command_type is invalid
    """
    # Normalize inputs
    display_id = display_id.lower()
    command_type = command_type.lower()
    
    if display_id not in DISPLAY_TYPES:
        raise ValueError(f"Invalid display ID: {display_id}")
        
    if command_type == DISPLAY_COMMAND_TYPE_SHOW:
        return SHOW_REQUEST_MAP[display_id]
    elif command_type == DISPLAY_COMMAND_TYPE_MODE or command_type == DISPLAY_COMMAND_TYPE_MODE_CHANGE:
        return MODE_REQUEST_MAP[display_id]
    elif command_type == DISPLAY_COMMAND_TYPE_DATA:
        return DATA_REQUEST_MAP[display_id]
    elif command_type == DISPLAY_COMMAND_TYPE_STATUS:
        return STATUS_REQUEST_MAP[display_id]
    else:
        raise ValueError(f"Invalid command type: {command_type}")

def validate_command_word(command_word: str) -> bool:
    """
    Validate a command word against MIL-STD-1553B requirements.
    
    Args:
        command_word: The command word to validate
        
    Returns:
        bool: True if the command word is valid, False otherwise
    """
    # Check length
    if len(command_word) != 16:
        logger.error(f"Invalid command word length: {len(command_word)}")
        return False
    
    # Check if it's a binary string
    if not all(c in '01' for c in command_word):
        logger.error(f"Command word contains non-binary characters: {command_word}")
        return False
    
    # Extract fields
    rt_address = int(command_word[0:5], 2)
    t_r_bit = int(command_word[5:6], 2)
    subaddress = int(command_word[6:11], 2)
    word_count = int(command_word[11:16], 2)
    
    # Validate RT address
    if rt_address < 0 or rt_address > 31:
        logger.error(f"Invalid RT address: {rt_address}")
        return False
    
    # Validate T/R bit
    if t_r_bit not in [0, 1]:
        logger.error(f"Invalid T/R bit: {t_r_bit}")
        return False
    
    # Validate subaddress
    if subaddress < 0 or subaddress > 31:
        logger.error(f"Invalid subaddress: {subaddress}")
        return False
    
    # Validate word count
    if word_count < 0 or word_count > 31:
        logger.error(f"Invalid word count: {word_count}")
        return False
    
    return True

# Include mode_change in the export list for clarity
MESSAGE_TYPES_EXTENDED = MESSAGE_TYPES + [DISPLAY_COMMAND_TYPE_MODE_CHANGE]

# Export all command word constants and maps
__all__ = [
    'DISPLAY_TYPES',
    'MESSAGE_TYPES',
    'MESSAGE_TYPES_EXTENDED',
    'SHOW_REQUEST_MAP',
    'MODE_REQUEST_MAP',
    'DATA_REQUEST_MAP',
    'STATUS_REQUEST_MAP',
    'get_display_command_word',
    'get_command_word',
    'construct_command_word',
    'validate_command_word',
    # PFD Command Words
    'PFD_SHOW_REQUEST',
    'PFD_SHOW_RESPONSE',
    'PFD_MODE_REQUEST',
    'PFD_MODE_RESPONSE',
    'PFD_DATA_REQUEST',
    'PFD_DATA_RESPONSE',
    'PFD_STATUS_REQUEST',
    'PFD_STATUS_RESPONSE',
    # MFD Command Words
    'MFD_SHOW_REQUEST',
    'MFD_SHOW_RESPONSE',
    'MFD_MODE_REQUEST',
    'MFD_MODE_RESPONSE',
    'MFD_DATA_REQUEST',
    'MFD_DATA_RESPONSE',
    'MFD_STATUS_REQUEST',
    'MFD_STATUS_RESPONSE',
    # EICAS Command Words
    'EICAS_SHOW_REQUEST',
    'EICAS_SHOW_RESPONSE',
    'EICAS_MODE_REQUEST',
    'EICAS_MODE_RESPONSE',
    'EICAS_DATA_REQUEST',
    'EICAS_DATA_RESPONSE',
    'EICAS_STATUS_REQUEST',
    'EICAS_STATUS_RESPONSE',
    # Radar Display Command Words
    'RADAR_DISPLAY_SHOW_REQUEST',
    'RADAR_DISPLAY_SHOW_RESPONSE',
    'RADAR_DISPLAY_MODE_REQUEST',
    'RADAR_DISPLAY_MODE_RESPONSE',
    'RADAR_DISPLAY_DATA_REQUEST',
    'RADAR_DISPLAY_DATA_RESPONSE',
    'RADAR_DISPLAY_STATUS_REQUEST',
    'RADAR_DISPLAY_STATUS_RESPONSE',
    # TSD Command Words
    'TSD_SHOW_REQUEST',
    'TSD_SHOW_RESPONSE',
    'TSD_MODE_REQUEST',
    'TSD_MODE_RESPONSE',
    'TSD_DATA_REQUEST',
    'TSD_DATA_RESPONSE',
    'TSD_STATUS_REQUEST',
    'TSD_STATUS_RESPONSE',
    # SMS Command Words
    'SMS_SHOW_REQUEST',
    'SMS_SHOW_RESPONSE',
    'SMS_MODE_REQUEST',
    'SMS_MODE_RESPONSE',
    'SMS_DATA_REQUEST',
    'SMS_DATA_RESPONSE',
    'SMS_STATUS_REQUEST',
    'SMS_STATUS_RESPONSE'
]
