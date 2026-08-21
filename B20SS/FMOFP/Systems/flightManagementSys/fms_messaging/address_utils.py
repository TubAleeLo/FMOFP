"""
FMS-specific address utility functions.

These utilities parse the FMS address book XML file for RT addresses and subaddresses.
This maintains system separation and avoids hardcoding values.
"""

import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Path to the FMS address book XML file - use absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
FMS_ADDRESS_BOOK_PATH = os.path.join(current_dir, 'fms_address_book.xml')

# Path to the global address book for cross-system communication
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
GLOBAL_ADDRESS_BOOK_PATH = os.path.join(PROJECT_ROOT, 'local_messaging', 'messageConfigurations', 'address_book.xml')

# Cache for address lookups to improve performance
_address_cache = {}
_subaddress_cache = {}


def get_fms_address():
    """
    Get the FMS system RT address.
    
    Returns:
        int: RT address for FMS
    """
    # Check cache first
    if 'fms' in _address_cache:
        return _address_cache['fms']
    
    try:
        # Parse FMS address book XML
        tree = ET.parse(FMS_ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find the FMS system element
        for system in root.findall('system'):
            if system.get('id').lower() == 'flightmanagementsystem':
                address = int(system.find('address').text)
                _address_cache['fms'] = address
                return address
                
        raise ValueError("FMS system not found in FMS address book")
    except Exception as e:
        logger.error(f"Error getting FMS address: {e}")
        raise


def get_fms_subaddress(subaddress_id):
    """
    Get subaddress value for a FMS subaddress ID.
    
    Args:
        subaddress_id: The subaddress ID (e.g., 'fms_control')
        
    Returns:
        int: Subaddress value
    """
    subaddress_id = subaddress_id.lower()
    
    # Check cache first
    cache_key = f"fms_{subaddress_id}"
    if cache_key in _subaddress_cache:
        return _subaddress_cache[cache_key]
    
    try:
        # Parse FMS address book XML
        tree = ET.parse(FMS_ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find subaddress element
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id:
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[cache_key] = value
                return value
                
        # Case-insensitive fallback
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id.lower():
                logger.debug(f"Using case-insensitive match for subaddress ID: {subaddress_id}")
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[cache_key] = value
                return value
                
        raise ValueError(f"Subaddress ID '{subaddress_id}' not found in FMS address book")
    except Exception as e:
        logger.error(f"Error getting FMS subaddress for ID '{subaddress_id}': {e}")
        raise


def get_message_subaddress(message_type):
    """
    Get the subaddress associated with a specific message type.
    
    Args:
        message_type: The message type ID (e.g., 'fms_modeChangeResponse')
        
    Returns:
        int: Subaddress value for this message type
    """
    message_type = message_type.lower()
    
    # Check cache first
    cache_key = f"msg_{message_type}"
    if cache_key in _subaddress_cache:
        return _subaddress_cache[cache_key]
    
    try:
        # Parse FMS address book XML
        tree = ET.parse(FMS_ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find message type element
        for msg_type in root.findall('messageType'):
            if msg_type.get('id').lower() == message_type:
                # Get subaddress ID for this message type
                subaddress_id = msg_type.find('subaddress').text
                # Look up the actual subaddress value
                return get_fms_subaddress(subaddress_id)
                
        # Case-insensitive fallback
        for msg_type in root.findall('messageType'):
            if msg_type.get('id').lower() == message_type.lower():
                logger.debug(f"Using case-insensitive match for message type: {message_type}")
                subaddress_id = msg_type.find('subaddress').text
                return get_fms_subaddress(subaddress_id)
                
        raise ValueError(f"Message type '{message_type}' not found in FMS address book")
    except Exception as e:
        logger.error(f"Error getting subaddress for message type '{message_type}': {e}")
        raise


def get_external_system_address(system_id):
    """
    Get RT address for an external system ID from the global address book.
    Used for cross-system communication.
    
    Args:
        system_id: The system ID (e.g., 'displays')
        
    Returns:
        int: RT address for the external system
    """
    system_id = system_id.lower()
    
    # Check cache first
    cache_key = f"ext_{system_id}"
    if cache_key in _address_cache:
        return _address_cache[cache_key]
    
    try:
        # Parse global address book XML
        tree = ET.parse(GLOBAL_ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find system element
        for system in root.findall('system'):
            if system.get('id').lower() == system_id:
                address = int(system.find('address').text)
                _address_cache[cache_key] = address
                return address
                
        # Case-insensitive fallback
        for system in root.findall('system'):
            if system.get('id').lower() == system_id.lower():
                logger.debug(f"Using case-insensitive match for external system ID: {system_id}")
                address = int(system.find('address').text)
                _address_cache[cache_key] = address
                return address
                
        raise ValueError(f"External system ID '{system_id}' not found in global address book")
    except Exception as e:
        logger.error(f"Error getting RT address for external system '{system_id}': {e}")
        raise


def get_external_subaddress(subaddress_id):
    """
    Get subaddress value for an external subaddress ID from the global address book.
    Used for cross-system communication.
    
    Args:
        subaddress_id: The subaddress ID (e.g., 'radar_display')
        
    Returns:
        int: Subaddress value for the external subaddress
    """
    subaddress_id = subaddress_id.lower()
    
    # Check cache first
    cache_key = f"ext_sub_{subaddress_id}"
    if cache_key in _subaddress_cache:
        return _subaddress_cache[cache_key]
    
    try:
        # Parse global address book XML
        tree = ET.parse(GLOBAL_ADDRESS_BOOK_PATH)
        root = tree.getroot()
        
        # Find subaddress element
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id:
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[cache_key] = value
                return value
                
        # Case-insensitive fallback
        for subaddress in root.findall('subaddress'):
            if subaddress.get('id').lower() == subaddress_id.lower():
                logger.debug(f"Using case-insensitive match for external subaddress ID: {subaddress_id}")
                value = int(subaddress.find('subaddress').text)
                _subaddress_cache[cache_key] = value
                return value
                
        raise ValueError(f"External subaddress ID '{subaddress_id}' not found in global address book")
    except Exception as e:
        logger.error(f"Error getting external subaddress for ID '{subaddress_id}': {e}")
        raise


def clear_cache():
    """Clear the address and subaddress caches."""
    global _address_cache, _subaddress_cache
    _address_cache = {}
    _subaddress_cache = {}


def reload_address_books():
    """
    Reload both FMS and global address books and clear caches.
    Call this if the address books have been updated.
    """
    clear_cache()
