"""
Utilities for working with RT addresses and subaddresses.
These functions should be used throughout the codebase instead of hardcoded values.
Provides handling for radar subsystems according to MIL-STD-1553B protocol.
"""

import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Path to the address book XML file
ADDRESS_BOOK_PATH = os.path.join('FMOFP', 'Systems', 'radarManagement', 'radar_messaging', 'radar_address_book.xml')

# List of radar subsystem IDs
RADAR_SUBSYSTEMS = ['weather_radar', 'tfr_radar', 'sar_radar', 'targeting_radar', 'aewc_radar']

# Cache for address lookups
_address_cache = {}
_subaddress_cache = {}
_is_subsystem_cache = {}

def is_radar_subsystem(system_name):
    """
    Check if a system name is a radar subsystem.
    
    Args:
        system_name: The system name to check
        
    Returns:
        bool: True if the system is a radar subsystem, False otherwise
    """
    if not system_name:
        return False
        
    system_name_lower = system_name.lower()
    
    # Check cache first
    if system_name_lower in _is_subsystem_cache:
        return _is_subsystem_cache[system_name_lower]
    
    # Check if the system name is in the radar subsystems list
    result = any(subsys in system_name_lower for subsys in RADAR_SUBSYSTEMS)
    
    # Cache the result
    _is_subsystem_cache[system_name_lower] = result
    
    return result

def get_system_id_for_addressing(system_name):
    """
    Get the correct system ID to use for addressing.
    For radar subsystems, returns 'radar'.
    For other systems, returns the original system name.
    
    Args:
        system_name: The system name
        
    Returns:
        str: The system ID to use for addressing
    """
    if not system_name:
        return system_name
        
    if is_radar_subsystem(system_name):
        logger.debug(f"Treating '{system_name}' as a radar subsystem, using 'radar' as system ID")
        return 'radar'
        
    return system_name

def get_rt_address(system_id):
    """
    Get RT address for a system ID.
    
    Args:
        system_id: The system ID (e.g., 'radar', 'displays')
        
    Returns:
        int: RT address
    """
    system_id = system_id.lower()
    
    # Check cache first
    if system_id in _address_cache:
        return _address_cache[system_id]
    
    try:
        # Parse address book XML
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find system element
        for system in root.findall('system'):
            if system.get('id').lower() == system_id:
                address = int(system.find('address').text)
                _address_cache[system_id] = address
                return address
                
        # Case-insensitive fallback
        for system in root.findall('system'):
            if system.get('id').lower() == system_id.lower():
                logger.debug(f"Using case-insensitive match for system ID: {system_id}")
                address = int(system.find('address').text)
                _address_cache[system_id] = address
                return address
                
        raise ValueError(f"System ID '{system_id}' not found in address book")
    except Exception as e:
        logger.error(f"Error getting RT address for system '{system_id}': {e}")
        raise
        
def get_subaddress(subaddress_id):
    """
    Get subaddress value for a subaddress ID.
    
    Args:
        subaddress_id: The subaddress ID (e.g., 'weather_radar', 'mode')
        
    Returns:
        int: Subaddress value
    """
    subaddress_id = subaddress_id.lower()
    
    # Check cache first
    if subaddress_id in _subaddress_cache:
        return _subaddress_cache[subaddress_id]
    
    try:
        # Parse address book XML
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find subaddress element
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id:
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[subaddress_id] = value
                return value
                
        # Case-insensitive fallback
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id.lower():
                logger.debug(f"Using case-insensitive match for subaddress ID: {subaddress_id}")
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[subaddress_id] = value
                return value
                
        raise ValueError(f"Subaddress ID '{subaddress_id}' not found in address book")
    except Exception as e:
        logger.error(f"Error getting subaddress for ID '{subaddress_id}': {e}")
        raise

def get_subaddress_id_by_value(subaddress_value):
    """
    Get subaddress ID for a given subaddress value.
    
    Args:
        subaddress_value: The subaddress value (1-31)
        
    Returns:
        str: Subaddress ID or None if not found
    """
    try:
        # Parse address book XML
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Convert to string for comparison if needed
        if not isinstance(subaddress_value, str):
            subaddress_value = str(subaddress_value)
        
        # Find subaddress element with matching value
        for subaddress in root.findall('subaddress'):
            if subaddress.find('subaddress').text == subaddress_value:
                return subaddress.get('id')
                
        # If not found with exact match, try as an integer
        try:
            subaddress_int = int(subaddress_value)
            for subaddress in root.findall('subaddress'):
                if int(subaddress.find('subaddress').text) == subaddress_int:
                    return subaddress.get('id')
        except (ValueError, TypeError):
            pass
                
        logger.warning(f"No subaddress ID found for value '{subaddress_value}'")
        return None
    except Exception as e:
        logger.error(f"Error getting subaddress ID for value '{subaddress_value}': {e}")
        return None

def get_rt_subaddress_pair_for_radar(system_name, subaddress_id):
    """
    Get the RT address and subaddress pair for a radar system or subsystem.
    Handles the special case of radar subsystems.
    
    Args:
        system_name: The system name (e.g., 'weather_radar', 'tfr_radar')
        subaddress_id: The subaddress ID
        
    Returns:
        tuple: (rt_address, subaddress)
    """
    # Determine the correct system ID for addressing
    actual_system_id = get_system_id_for_addressing(system_name)
    
    # Get addresses with fallback mechanisms
    try:
        rt_address = get_rt_address(actual_system_id)
        
        # For radar subsystems, use the subsystem name as the subaddress ID if not specified or if using completion
        if is_radar_subsystem(system_name) and subaddress_id in ['mode_change_completion', 'completion', None]:
            # Extract subsystem name from the original system_name
            for subsys in RADAR_SUBSYSTEMS:
                if subsys in system_name.lower():
                    logger.debug(f"Using '{subsys}' as subaddress ID for radar subsystem '{system_name}'")
                    subaddress_id = subsys
                    break
        
        subaddress = get_subaddress(subaddress_id)
        return rt_address, subaddress
        
    except Exception as e:
        logger.warning(f"Error getting RT/SA addresses for {system_name}/{subaddress_id}: {e}")
        
        # Fallback to defaults if lookup fails
        if actual_system_id == 'radar':
            logger.info(f"Using fallback RT=9, SA=1 for radar system '{system_name}'")
            return 9, 1  # Default radar RT address = 9, default subaddress = 1
        elif 'display' in actual_system_id.lower():
            logger.info(f"Using fallback RT=11, SA=1 for display system '{system_name}'")
            return 11, 1  # Default display RT address = 11, default subaddress = 1
        else:
            logger.error(f"Cannot resolve RT/SA addresses for {system_name}/{subaddress_id}: {e}")
            raise ValueError(f"Cannot resolve RT/SA addresses for {system_name}/{subaddress_id}: {e}")
