"""
Radar Command Word Map

Maps command words specifically for radar systems.
Based on FMOFP/Msg_handler/local_messaging/command_word_map.py but
maintains physical separation between Bus Controller and Remote Terminal systems.
"""

import logging
from typing import Dict, Optional

from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Radar types
RADAR_TYPES = ['weather_radar', 'tfr_radar', 'sar_radar', 'targeting_radar', 'aewc_radar']

# Weather radar data types
WEATHER_DATA_TYPES = ['echo_top', 'shear', 'turbulence', 'vil', 'precipitation']

# Command word patterns for weather radar data types
# These are the standard patterns used by the Bus Controller
WEATHER_DATA_COMMAND_PATTERNS = {
    'vil': '01001000001',  # RT=9, SA=1, WC=2
    'precipitation': '01001000001',  # RT=9, SA=1, WC=2
    'echo_top': '01001000001',  # RT=9, SA=1, WC=4
    'shear': '01001000001',  # RT=9, SA=1, WC=4
    'turbulence': '01001000001'  # RT=9, SA=1, WC=5
}

# Command word patterns for radar mode changes
# These are the standard patterns used by the Bus Controller
RADAR_MODE_COMMAND_PATTERNS = {
    'weather_radar': '01001000010',  # RT=9, SA=2, WC=2
    'tfr_radar': '01001000010',  # RT=9, SA=2, WC=2
    'sar_radar': '01001000010',  # RT=9, SA=2, WC=2
    'targeting_radar': '01001000010',  # RT=9, SA=2, WC=2
    'aewc_radar': '01001000010'  # RT=9, SA=2, WC=2
}

def is_weather_data_command(command_word: str, data_type: Optional[str] = None) -> bool:
    """
    Check if a command word is for weather radar data.
    
    Args:
        command_word: The command word to check
        data_type: Optional specific data type to check for
        
    Returns:
        bool: True if the command word is for weather radar data
    """
    # Normalize command word by removing sync bits if present
    if len(command_word) > 16 and command_word.startswith('100'):
        normalized_cmd = command_word[3:]
    else:
        normalized_cmd = command_word[-16:] if len(command_word) >= 16 else command_word
    
    # Extract RT address, subaddress, and word count
    try:
        rt_address = int(normalized_cmd[0:5], 2)
        subaddress = int(normalized_cmd[6:11], 2)
        word_count = int(normalized_cmd[11:16], 2)
        
        # Check if this is a weather radar data command
        if rt_address == 9 and subaddress == 1:
            # If specific data type is provided, check word count
            if data_type:
                if data_type in ['vil', 'precipitation'] and word_count == 2:
                    return True
                elif data_type in ['echo_top', 'shear'] and word_count == 4:
                    return True
                elif data_type == 'turbulence' and word_count == 5:
                    return True
                return False
            # Otherwise, any weather radar data command is valid
            return True
    except (ValueError, IndexError):
        return False
    
    return False

def is_radar_mode_command(command_word: str, radar_type: Optional[str] = None) -> bool:
    """
    Check if a command word is for radar mode change.
    
    Args:
        command_word: The command word to check
        radar_type: Optional specific radar type to check for
        
    Returns:
        bool: True if the command word is for radar mode change
    """
    # Normalize command word by removing sync bits if present
    if len(command_word) > 16 and command_word.startswith('100'):
        normalized_cmd = command_word[3:]
    else:
        normalized_cmd = command_word[-16:] if len(command_word) >= 16 else command_word
    
    # Extract RT address, subaddress, and word count
    try:
        rt_address = int(normalized_cmd[0:5], 2)
        subaddress = int(normalized_cmd[6:11], 2)
        word_count = int(normalized_cmd[11:16], 2)
        
        # Check if this is a radar mode command
        if rt_address == 9 and subaddress == 2 and word_count == 2:
            # If specific radar type is provided, check pattern
            if radar_type and radar_type in RADAR_TYPES:
                pattern = RADAR_MODE_COMMAND_PATTERNS[radar_type]
                return normalized_cmd.startswith(pattern)
            # Otherwise, any radar mode command is valid
            return True
    except (ValueError, IndexError):
        return False
    
    return False

def get_data_type_from_command(command_word: str) -> Optional[str]:
    """
    Get the data type from a command word.
    
    Args:
        command_word: The command word to check
        
    Returns:
        Optional[str]: The data type if found, None otherwise
    """
    # Check each data type
    for data_type in WEATHER_DATA_TYPES:
        if is_weather_data_command(command_word, data_type):
            return data_type
    
    return None

def get_radar_type_from_command(command_word: str) -> Optional[str]:
    """
    Get the radar type from a command word.
    
    Args:
        command_word: The command word to check
        
    Returns:
        Optional[str]: The radar type if found, None otherwise
    """
    # Check each radar type
    for radar_type in RADAR_TYPES:
        if is_radar_mode_command(command_word, radar_type):
            return radar_type
    
    return None
