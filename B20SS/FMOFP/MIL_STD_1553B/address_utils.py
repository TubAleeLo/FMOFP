"""
MIL-STD-1553B Address Utilities

Provides utility functions for working with RT addresses and subaddresses.
These functions mirror those in local_messaging/address_utils.py to avoid
cross-module dependencies.
"""

import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Path to the address book XML file - use absolute path for reliability
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))
ADDRESS_BOOK_PATH = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'address_book.xml')

# Cache for address lookups to improve performance
_address_cache = {}
_subaddress_cache = {}

# Define RT address constants for critical system components
RT_ADDRESS_RADAR = 9
RT_ADDRESS_DISPLAYS = 11
RT_ADDRESS_FMS = 12
RT_ADDRESS_AVIONICS = 1
RT_ADDRESS_COMMS = 2
RT_ADDRESS_ENGINE = 3

# Define subaddress constants for common operations
SUBADDRESS_FC = 10
SUBADDRESS_FM = 15   

SUBADDRESS_WEATHER_RADAR = 1
SUBADDRESS_TFR_RADAR = 2
SUBADDRESS_SAR_RADAR = 3
SUBADDRESS_TARGETING_RADAR = 4
SUBADDRESS_AEWC_RADAR = 5
SUBADDRESS_MODE_CODES = 31


def get_rt_address(system_id):
    """
    Get RT address for a system ID.
    
    Args:
        system_id: The system ID (e.g., 'radar', 'displays')
        
    Returns:
        int: RT address
    """
    # Check for known system IDs first for performance
    system_id_lower = system_id.lower()
    
    # Fast lookup for common systems
    if system_id_lower == 'radar':
        return RT_ADDRESS_RADAR
    elif system_id_lower == 'displays':
        return RT_ADDRESS_DISPLAYS
    elif system_id_lower == 'flightmanagementsystem':
        return RT_ADDRESS_FMS
    elif system_id_lower == 'avionics':
        return RT_ADDRESS_AVIONICS
    elif system_id_lower == 'comms':
        return RT_ADDRESS_COMMS
    elif system_id_lower == 'enginemanagement':
        return RT_ADDRESS_ENGINE
    
    # Check cache next
    if system_id_lower in _address_cache:
        return _address_cache[system_id_lower]
    
    try:
        # Parse address book XML as fallback
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find system element
        for system in root.findall('system'):
            if system.get('id').lower() == system_id_lower:
                address = int(system.find('address').text)
                _address_cache[system_id_lower] = address
                return address
                
        # Case-insensitive fallback
        for system in root.findall('system'):
            if system.get('id').lower() == system_id_lower:
                logger.debug(f"Using case-insensitive match for system ID: {system_id}")
                address = int(system.find('address').text)
                _address_cache[system_id_lower] = address
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
    # Check for known subaddress IDs first for performance
    subaddress_id_lower = subaddress_id.lower()
    
    # Fast lookup for common subaddresses
    if subaddress_id_lower == 'mode':
        return SUBADDRESS_MODE_CODES
    elif subaddress_id_lower == 'flight_management':
        return SUBADDRESS_FM
    elif subaddress_id_lower == 'flight_control':
        return SUBADDRESS_FC
    elif subaddress_id_lower == 'weather_radar':
        return SUBADDRESS_WEATHER_RADAR
    elif subaddress_id_lower == 'tfr_radar':
        return SUBADDRESS_TFR_RADAR
    elif subaddress_id_lower == 'sar_radar':
        return SUBADDRESS_SAR_RADAR
    elif subaddress_id_lower == 'targeting_radar':
        return SUBADDRESS_TARGETING_RADAR
    elif subaddress_id_lower == 'aewc_radar':
        return SUBADDRESS_AEWC_RADAR
    elif subaddress_id_lower == 'mode_codes':
        return SUBADDRESS_MODE_CODES
    
    # Check cache next
    if subaddress_id_lower in _subaddress_cache:
        return _subaddress_cache[subaddress_id_lower]
    
    try:
        # Parse address book XML as fallback
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find subaddress element
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id_lower:
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[subaddress_id_lower] = value
                return value
                
        # Case-insensitive fallback
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id_lower:
                logger.debug(f"Using case-insensitive match for subaddress ID: {subaddress_id}")
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[subaddress_id_lower] = value
                return value
                
        raise ValueError(f"Subaddress ID '{subaddress_id}' not found in address book")
    except Exception as e:
        logger.error(f"Error getting subaddress for ID '{subaddress_id}': {e}")
        raise


def get_rt_subaddress_pair(system_id, subaddress_id):
    """
    Get RT address and subaddress as a tuple.
    
    Args:
        system_id: The system ID (e.g., 'radar', 'displays')
        subaddress_id: The subaddress ID (e.g., 'weather_radar', 'mode')
        
    Returns:
        tuple: (RT address, subaddress)
    """
    rt_address = get_rt_address(system_id)
    subaddress = get_subaddress(subaddress_id)
    return (rt_address, subaddress)


def is_valid_rt_address(rt_address):
    """
    Check if an RT address is valid (exists in address book).
    
    Args:
        rt_address: The RT address to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Fast validation for known RT addresses
    if rt_address in [RT_ADDRESS_RADAR, RT_ADDRESS_DISPLAYS, RT_ADDRESS_FMS, 
                      RT_ADDRESS_AVIONICS, RT_ADDRESS_COMMS, RT_ADDRESS_ENGINE]:
        return True
    
    # Check full range
    if 0 <= rt_address <= 31:
        try:
            # Parse address book XML
            tree = ET.parse(ADDRESS_BOOK_PATH)
            root = tree.getroot()
            
            # Find any system with this address
            for system in root.findall('system'):
                if int(system.find('address').text) == rt_address:
                    return True
                    
            # Not found but in valid range - log warning
            logger.warning(f"RT address {rt_address} is in valid range but not assigned in address book")
            return True  # Still valid per MIL-STD-1553B, just not assigned
        except Exception as e:
            logger.error(f"Error checking RT address {rt_address}: {e}")
            return False
    else:
        # Outside valid range
        return False


def is_valid_subaddress(subaddress):
    """
    Check if a subaddress is valid (exists in address book).
    
    Args:
        subaddress: The subaddress to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Fast validation for known subaddresses
    if subaddress in [SUBADDRESS_FC, SUBADDRESS_FM, SUBADDRESS_MODE_CODES,
                     SUBADDRESS_WEATHER_RADAR, SUBADDRESS_TFR_RADAR, 
                     SUBADDRESS_SAR_RADAR, SUBADDRESS_TARGETING_RADAR,
                     SUBADDRESS_AEWC_RADAR]:
        return True
    
    # Check full range
    if 0 <= subaddress <= 31:
        try:
            # Parse address book XML
            tree = ET.parse(ADDRESS_BOOK_PATH)
            root = tree.getroot()
            
            # Find any subaddress element with this value
            for sa in root.findall('subaddress'):
                if int(sa.find('subaddress').text) == subaddress:
                    return True
                    
            # Not found but in valid range - log warning
            logger.warning(f"Subaddress {subaddress} is in valid range but not assigned in address book")
            return True  # Still valid per MIL-STD-1553B, just not assigned
        except Exception as e:
            logger.error(f"Error checking subaddress {subaddress}: {e}")
            return False
    else:
        # Outside valid range
        return False


def get_system_id_by_rt_address(rt_address):
    """
    Get system ID from RT address.
    
    Args:
        rt_address: The RT address
        
    Returns:
        str: System ID
    """
    # Fast lookup for known RT addresses
    if rt_address == RT_ADDRESS_RADAR:
        return 'radar'
    elif rt_address == RT_ADDRESS_DISPLAYS:
        return 'displays'
    elif rt_address == RT_ADDRESS_FMS:
        return 'flightManagementSystem'
    elif rt_address == RT_ADDRESS_AVIONICS:
        return 'avionics'
    elif rt_address == RT_ADDRESS_COMMS:
        return 'comms'
    elif rt_address == RT_ADDRESS_ENGINE:
        return 'enginemanagement'
    
    try:
        # Parse address book XML as fallback
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find system with this address
        for system in root.findall('system'):
            if int(system.find('address').text) == rt_address:
                return system.get('id')
                
        return None
    except Exception as e:
        logger.error(f"Error getting system ID for RT address {rt_address}: {e}")
        return None


def get_subaddress_id_by_value(subaddress_value):
    """
    Get subaddress ID from subaddress value.
    
    Args:
        subaddress_value: The subaddress value
        
    Returns:
        str: Subaddress ID
    """
    # Fast lookup for known subaddress values
    if subaddress_value == SUBADDRESS_MODE_CODES:
        return 'mode_code'
    elif subaddress_value == SUBADDRESS_FC:
        return 'flight_control'
    elif subaddress_value == SUBADDRESS_FM:
        return 'flight_management'
    elif subaddress_value == SUBADDRESS_WEATHER_RADAR:
        return 'weather_radar'
    elif subaddress_value == SUBADDRESS_TFR_RADAR:
        return 'tfr_radar'
    elif subaddress_value == SUBADDRESS_SAR_RADAR:
        return 'sar_radar'
    elif subaddress_value == SUBADDRESS_TARGETING_RADAR:
        return 'targeting_radar'
    elif subaddress_value == SUBADDRESS_AEWC_RADAR:
        return 'aewc_radar'
    
    try:
        # Parse address book XML as fallback
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find subaddress element with this value
        for sa in root.findall('subaddress'):
            if int(sa.find('subaddress').text) == subaddress_value:
                return sa.get('id')
                
        return None
    except Exception as e:
        logger.error(f"Error getting subaddress ID for value {subaddress_value}: {e}")
        return None


def clear_cache():
    """Clear the address and subaddress caches."""
    global _address_cache, _subaddress_cache
    _address_cache = {}
    _subaddress_cache = {}


def reload_address_book():
    """
    Reload the address book and clear caches.
    Call this if the address book has been updated.
    """
    clear_cache()
    
    
def validate_mil_std_1553b_address(rt_address, subaddress):
    """
    Validate both RT address and subaddress according to MIL-STD-1553B standard.
    
    Args:
        rt_address: RT address to validate
        subaddress: Subaddress to validate
        
    Returns:
        bool: True if both are valid, False otherwise
    """
    # Check RT address range (5 bits, 0-31)
    if not (0 <= rt_address <= 31):
        logger.error(f"Invalid RT address: {rt_address} (must be 0-31)")
        return False
        
    # Check subaddress range (5 bits, 0-31)
    if not (0 <= subaddress <= 31):
        logger.error(f"Invalid subaddress: {subaddress} (must be 0-31)")
        return False
        
    # All checks passed
    return True
