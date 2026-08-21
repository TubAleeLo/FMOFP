"""
Display-specific utilities for working with RT addresses and subaddresses.
These utilities should be used throughout the display system instead of hardcoded values.
"""

import os
# NOTE: both imports below were previously flagged as "check for a
# display-local version, if not create a mirror'd local version". Checked:
# no display-local version exists, and there shouldn't be one - address_utils
# is the single shared RT-address/subaddress table every subsystem (radar,
# FMS, displays) must agree on, and message_types defines the shared command
# type vocabulary used on the wire. Duplicating either per-subsystem would
# let the display system silently drift out of sync with the addresses/
# command types every other system uses, which is precisely the kind of
# cross-system inconsistency a single shared address/type table exists to
# prevent. These shared imports are intentional and correct as-is.
from FMOFP.local_messaging.address_utils import (
    get_rt_address,
    get_subaddress,
    get_rt_subaddress_pair,
    is_valid_rt_address,
    is_valid_subaddress,
    get_system_id_by_rt_address,
    get_subaddress_id_by_value
)
from FMOFP.local_messaging.message_types import (
    COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_DATA_REQUEST,
    COMMAND_TYPE_DATA_RESPONSE,
    get_message_type
)
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Display system constants
DISPLAY_SYSTEM_ID = 'displays'
DISPLAY_RT_ADDRESS = get_rt_address(DISPLAY_SYSTEM_ID)

# Radar system constants
RADAR_SYSTEM_ID = 'radar'
RADAR_RT_ADDRESS = get_rt_address(RADAR_SYSTEM_ID)
WEATHER_RADAR_RT_ADDRESS = RADAR_RT_ADDRESS

# Display subaddress constants
PFD_SUBADDRESS = get_subaddress('pfd')
MFD_SUBADDRESS = get_subaddress('mfd')
EICAS_SUBADDRESS = get_subaddress('eicas')
RADAR_DISPLAY_SUBADDRESS = get_subaddress('radar_display')
TSD_SUBADDRESS = get_subaddress('tsd')
SMS_SUBADDRESS = get_subaddress('sms')

# Command types should be handled in message metadata, not as subaddresses
# This is required for MIL-STD-1553B compliance where subaddresses only identify subsystems

# Command Type Utils
def get_command_type(message):
    """
    Extract command type from message metadata.
    
    Args:
        message: The message to extract command type from
        
    Returns:
        str: Command type or None if not found
    """
    if isinstance(message, dict):
        if 'metadata' in message and isinstance(message['metadata'], dict):
            return message['metadata'].get('command_type')
        elif 'additional_info' in message and isinstance(message['additional_info'], dict):
            return message['additional_info'].get('command_type')
    elif hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
        return message.metadata.get('command_type')
    return None

def is_command_type(message, expected_type):
    """
    Check if message has the expected command type.
    
    Args:
        message: The message to check
        expected_type: The expected command type
        
    Returns:
        bool: True if the message has the expected command type, False otherwise
    """
    cmd_type = get_command_type(message)
    if not cmd_type or not expected_type:
        return False
    return cmd_type.lower() == expected_type.lower()

def is_mode_command(message):
    """
    Check if a message is a mode command.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a mode command, False otherwise
    """
    return is_command_type(message, COMMAND_TYPE_MODE_CHANGE)

def is_data_request_command(message):
    """
    Check if a message is a data request command.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a data request command, False otherwise
    """
    return is_command_type(message, COMMAND_TYPE_DATA_REQUEST)

def is_data_response_command(message):
    """
    Check if a message is a data response command.
    
    Args:
        message: The message to check
        
    Returns:
        bool: True if the message is a data response command, False otherwise
    """
    return is_command_type(message, COMMAND_TYPE_DATA_RESPONSE)

# Radar subaddress constants
WEATHER_RADAR_SUBADDRESS = get_subaddress('weather_radar')
TFR_RADAR_SUBADDRESS = get_subaddress('tfr_radar')
SAR_RADAR_SUBADDRESS = get_subaddress('sar_radar')
TARGETING_RADAR_SUBADDRESS = get_subaddress('targeting_radar')
AEWC_RADAR_SUBADDRESS = get_subaddress('aewc_radar')

# Display subaddress mapping
DISPLAY_SUBADDRESS_MAP = {
    'pfd': PFD_SUBADDRESS,
    'mfd': MFD_SUBADDRESS,
    'eicas': EICAS_SUBADDRESS,
    'radar_display': RADAR_DISPLAY_SUBADDRESS,
    'weather_radar': RADAR_DISPLAY_SUBADDRESS,  # Alias for radar_display
    'tsd': TSD_SUBADDRESS,
    'sms': SMS_SUBADDRESS
}

# Radar subaddress mapping
RADAR_SUBADDRESS_MAP = {
    'weather_radar': WEATHER_RADAR_SUBADDRESS,
    'tfr_radar': TFR_RADAR_SUBADDRESS,
    'sar_radar': SAR_RADAR_SUBADDRESS,
    'targeting_radar': TARGETING_RADAR_SUBADDRESS,
    'aewc_radar': AEWC_RADAR_SUBADDRESS
}

# RT Address and Subaddress Name Resolvers
def get_rt_address_name(rt_address):
    """
    Get the name of an RT address.
    
    Args:
        rt_address: RT address (binary string or integer)
        
    Returns:
        str: Name of the RT address or None if not found
    """
    if isinstance(rt_address, str):
        # First check if it's a pure binary string (contains only 0's and 1's)
        if all(c in '01' for c in rt_address):
            try:
                rt_address = int(rt_address, 2)
            except ValueError:
                return None
        else:
            # Otherwise, treat as decimal
            try:
                rt_address = int(rt_address)
            except ValueError:
                return None
    
    # Convert DISPLAY_RT_ADDRESS to int accounting for if it's already an int or a binary string
    display_rt_int = DISPLAY_RT_ADDRESS
    if isinstance(DISPLAY_RT_ADDRESS, str):
        try:
            if all(c in '01' for c in DISPLAY_RT_ADDRESS):
                display_rt_int = int(DISPLAY_RT_ADDRESS, 2)
            else:
                display_rt_int = int(DISPLAY_RT_ADDRESS)
        except (ValueError, TypeError):
            logger.error(f"Invalid DISPLAY_RT_ADDRESS format: {DISPLAY_RT_ADDRESS}")
    
    # Convert RADAR_RT_ADDRESS to int accounting for if it's already an int or a binary string
    radar_rt_int = RADAR_RT_ADDRESS
    if isinstance(RADAR_RT_ADDRESS, str):
        try:
            if all(c in '01' for c in RADAR_RT_ADDRESS):
                radar_rt_int = int(RADAR_RT_ADDRESS, 2)
            else:
                radar_rt_int = int(RADAR_RT_ADDRESS)
        except (ValueError, TypeError):
            logger.error(f"Invalid RADAR_RT_ADDRESS format: {RADAR_RT_ADDRESS}")
    
    if rt_address == display_rt_int:
        return DISPLAY_SYSTEM_ID
    elif rt_address == radar_rt_int:
        return RADAR_SYSTEM_ID
    
    # Use global address resolver as fallback
    try:
        return get_system_id_by_rt_address(rt_address)
    except Exception:
        return None

def get_subaddress_name(subaddress):
    """
    Get the name of a subaddress.
    
    Args:
        subaddress: Subaddress value
        
    Returns:
        str: Name of the subaddress or None if not found
    """
    # Check display subaddresses
    display_id = get_display_id_by_subaddress(subaddress)
    if display_id:
        return f"display:{display_id}"
    
    # Check radar subaddresses
    radar_type = get_radar_type_by_subaddress(subaddress)
    if radar_type:
        return f"radar:{radar_type}"
    
    # Use global subaddress resolver as fallback
    try:
        return get_subaddress_id_by_value(subaddress)
    except Exception:
        return None

# Other Helper functions
def get_display_rt_address():
    """
    Get RT address for display system.
    
    Returns:
        str: Binary string representation of the RT address
    """
    return DISPLAY_RT_ADDRESS

def get_radar_rt_address():
    """
    Get RT address for radar system.
    
    Returns:
        str: Binary string representation of the RT address
    """
    return RADAR_RT_ADDRESS

def get_display_subaddress(display_id):
    """
    Get subaddress for a display type.
    
    Args:
        display_id: Display identifier (e.g., 'pfd', 'mfd')
        
    Returns:
        int: Subaddress value
        
    Raises:
        ValueError: If display_id is invalid
    """
    display_id = display_id.lower()
    if display_id not in DISPLAY_SUBADDRESS_MAP:
        raise ValueError(f"Invalid display ID: {display_id}")
    return DISPLAY_SUBADDRESS_MAP[display_id]


def get_radar_subaddress(radar_type):
    """
    Get subaddress for a radar type.
    
    Args:
        radar_type: Radar type (e.g., 'weather_radar', 'tfr_radar')
        
    Returns:
        int: Subaddress value
        
    Raises:
        ValueError: If radar_type is invalid
    """
    radar_type = radar_type.lower()
    if radar_type not in RADAR_SUBADDRESS_MAP:
        raise ValueError(f"Invalid radar type: {radar_type}")
    return RADAR_SUBADDRESS_MAP[radar_type]

def get_display_id_by_subaddress(subaddress):
    """
    Get display ID for a subaddress value.
    
    Args:
        subaddress: Subaddress value
        
    Returns:
        str: Display ID or None if not found
    """
    for display_id, addr in DISPLAY_SUBADDRESS_MAP.items():
        if addr == subaddress:
            return display_id
    return None


def get_radar_type_by_subaddress(subaddress):
    """
    Get radar type for a subaddress value.
    
    Args:
        subaddress: Subaddress value
        
    Returns:
        str: Radar type or None if not found
    """
    for radar_type, addr in RADAR_SUBADDRESS_MAP.items():
        if addr == subaddress:
            return radar_type
    return None

def is_display_rt_address(rt_address):
    """
    Check if an RT address is for the display system.
    
    Args:
        rt_address: RT address to check
        
    Returns:
        bool: True if the RT address is for the display system, False otherwise
    """
    if isinstance(rt_address, str):
        try:
            rt_address = int(rt_address, 2)
        except ValueError:
            try:
                rt_address = int(rt_address)
            except ValueError:
                return False
    
    # Convert DISPLAY_RT_ADDRESS to int accounting for if it's already an int or a binary string
    display_rt_int = DISPLAY_RT_ADDRESS
    if isinstance(DISPLAY_RT_ADDRESS, str):
        try:
            if all(c in '01' for c in DISPLAY_RT_ADDRESS):
                display_rt_int = int(DISPLAY_RT_ADDRESS, 2)
            else:
                display_rt_int = int(DISPLAY_RT_ADDRESS)
        except (ValueError, TypeError):
            logger.error(f"Invalid DISPLAY_RT_ADDRESS format: {DISPLAY_RT_ADDRESS}")
    
    return rt_address == display_rt_int

def is_radar_rt_address(rt_address):
    """
    Check if an RT address is for the radar system.
    
    Args:
        rt_address: RT address to check
        
    Returns:
        bool: True if the RT address is for the radar system, False otherwise
    """
    if isinstance(rt_address, str):
        try:
            rt_address = int(rt_address, 2)
        except ValueError:
            try:
                rt_address = int(rt_address)
            except ValueError:
                return False
    
    # Convert RADAR_RT_ADDRESS to int accounting for if it's already an int or a binary string
    radar_rt_int = RADAR_RT_ADDRESS
    if isinstance(RADAR_RT_ADDRESS, str):
        try:
            if all(c in '01' for c in RADAR_RT_ADDRESS):
                radar_rt_int = int(RADAR_RT_ADDRESS, 2)
            else:
                radar_rt_int = int(RADAR_RT_ADDRESS)
        except (ValueError, TypeError):
            logger.error(f"Invalid RADAR_RT_ADDRESS format: {RADAR_RT_ADDRESS}")
    
    return rt_address == radar_rt_int

def is_display_subaddress(subaddress):
    """
    Check if a subaddress is for a display.
    
    Args:
        subaddress: Subaddress to check
        
    Returns:
        bool: True if the subaddress is for a display, False otherwise
    """
    return subaddress in DISPLAY_SUBADDRESS_MAP.values()


def is_radar_subaddress(subaddress):
    """
    Check if a subaddress is for a radar.
    
    Args:
        subaddress: Subaddress to check
        
    Returns:
        bool: True if the subaddress is for a radar, False otherwise
    """
    return subaddress in RADAR_SUBADDRESS_MAP.values()

def get_subaddress_info(rt_address, subaddress):
    """
    Get information about a subaddress based on RT address and subaddress value.
    
    Args:
        rt_address: RT address
        subaddress: Subaddress value
        
    Returns:
        tuple: (system_type, entity_id) or (None, None) if not found
        
    Note:
        Command types are now included in message metadata, not as subaddresses
    """
    # Convert RT address to integer if it's a binary string
    if isinstance(rt_address, str):
        try:
            rt_address = int(rt_address, 2)
        except ValueError:
            try:
                rt_address = int(rt_address)
            except ValueError:
                return None, None
    
    # Check if it's a display RT address
    if is_display_rt_address(rt_address):
        # Check if it's a display subaddress
        display_id = get_display_id_by_subaddress(subaddress)
        if display_id:
            return 'display', display_id
    
    # Check if it's a radar RT address
    elif is_radar_rt_address(rt_address):
        # Check if it's a radar subaddress
        radar_type = get_radar_type_by_subaddress(subaddress)
        if radar_type:
            return 'radar', radar_type
    
    # Not found
    return None, None
