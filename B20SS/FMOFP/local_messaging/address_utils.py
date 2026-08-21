"""
Utilities for working with RT addresses and subaddresses.
These functions should be used throughout the codebase instead of hardcoded values.
"""

import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Path to the address book XML file - use absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))
ADDRESS_BOOK_PATH = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'address_book.xml')

# Cache for address lookups to improve performance
_address_cache = {}
_subaddress_cache = {}


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
    try:
        # Parse address book XML
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find any system with this address
        for system in root.findall('system'):
            if int(system.find('address').text) == rt_address:
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking RT address {rt_address}: {e}")
        return False


def is_valid_subaddress(subaddress):
    """
    Check if a subaddress is valid (exists in address book).
    
    Args:
        subaddress: The subaddress to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Parse address book XML
        tree = ET.parse(ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find any subaddress element with this value
        for sa in root.findall('subaddress'):
            if int(sa.find('subaddress').text) == subaddress:
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking subaddress {subaddress}: {e}")
        return False


def get_system_id_by_rt_address(rt_address):
    """
    Get system ID from RT address.
    
    Args:
        rt_address: The RT address
        
    Returns:
        str: System ID
    """
    try:
        # Parse address book XML
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
    try:
        # Parse address book XML
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
