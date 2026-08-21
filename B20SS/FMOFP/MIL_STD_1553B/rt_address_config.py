"""
RT Address Configuration for MIL-STD-1553B

This module now acts as a proxy to the centralized address_utils module,
maintaining backward compatibility while ensuring all code uses the same
address and subaddress values.
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, Tuple
import threading
from Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.operation_tracker import track_operation, is_operation_completed
from FMOFP.local_messaging.address_utils import (
    get_rt_address as utils_get_rt_address,
    get_subaddress as utils_get_subaddress,
    get_rt_subaddress_pair as utils_get_rt_subaddress_pair,
    is_valid_rt_address,
    is_valid_subaddress
)

logger = get_logger()

# Default RT address configuration
DEFAULT_RT_CONFIG = {
    # System RT addresses
    'radar_system': 9,
    'display_system': 11,
    'navigation_system': 12,
    'targeting_radar': 13,
    'sar_radar': 14,
    'tfr_radar': 15,
    'aewc_radar': 16,
    'flightManagementSystem': 17,
    
    # Subaddresses for various systems
    'subaddresses': {
        # Radar subaddresses
        'weather_radar': 1,
        'tfr_radar': 2,
        'sar_radar': 3,
        'targeting_radar': 4,
        'aewc_radar': 5,

        # Display subaddresses
        
        'pfd': 11,
        'mfd': 12,
        'eicas': 13,
        'radar_display': 14,
        'tsd': 15,
        'sms': 16,

        # General subaddresses
        
    }
}

# Singleton instance with thread-safe initialization
_rt_config = None
_config_lock = threading.Lock()

def _load_rt_config_from_file() -> Dict[str, Any]:
    """Load RT address configuration from XML file."""
    try:
        # Default to built-in configuration
        config = DEFAULT_RT_CONFIG.copy()
        
        # Try to load from configuration file
        config_file = os.path.join(os.path.join('FMOFP', 'rtAddressConfig.xml'))
        
        if not os.path.exists(config_file):
            logger.warning(f"RT address configuration file not found: {config_file}")
            # Try to load from address book
            address_book_file = os.path.join(os.path.join('FMOFP', 'local_messaging', 'messageConfigurations', 'address_book.xml'))
            if os.path.exists(address_book_file):
                logger.info(f"Loading RT address configuration from address book: {address_book_file}")
                return _load_from_address_book(address_book_file)
            else:
                logger.warning(f"Address book file not found: {address_book_file}")
                return config

        COMMAND_REGISTRY_PATH = os.path.join('FMOFP', 'local_messaging', 'messageConfigurations', 'command_registry.xml')
        tree = ET.parse(config_file)
        root = tree.getroot()
        
        # Load RT addresses
        for system in root.findall('rt_addresses/system'):
            name = system.get('name')
            address = int(system.get('address'))
            if name and address is not None:
                config[name] = address
                
        # Load subaddresses
        for subaddr in root.findall('subaddresses/subaddress'):
            name = subaddr.get('name')
            address = int(subaddr.get('address'))
            if name and address is not None:
                config['subaddresses'][name] = address
                
        logger.info("Successfully loaded RT address configuration from file")
        return config
        
    except Exception as e:
        logger.error(f"Error loading RT address configuration: {e}")
        # Return default configuration on error
        return DEFAULT_RT_CONFIG

def _load_from_address_book(address_book_file: str) -> Dict[str, Any]:
    """Load RT address configuration from address_book.xml file."""
    try:
        # Start with default configuration
        config = DEFAULT_RT_CONFIG.copy()
        
        tree = ET.parse(address_book_file)
        root = tree.getroot()
        
        # Load system addresses
        for system in root.findall('system'):
            system_id = system.get('id')
            name_elem = system.find('name')
            address_elem = system.find('address')
            
            if name_elem is not None and address_elem is not None:
                address = int(address_elem.text)
                
                # Map system IDs to our configuration keys
                if system_id == 'radar':
                    config['weather_radar'] = address
                    config['targeting_radar'] = address
                    config['sar_radar'] = address
                    config['tfr_radar'] = address
                    config['aewc_radar'] = address
                elif system_id == 'displays':
                    config['display_system'] = address
                elif system_id == 'nav':
                    config['navigation_system'] = address
                elif system_id == 'flightmanagementsys':
                    config['flightManagementSystem'] = address
        
        # Load radar subaddresses
        for subaddr in root.findall('subaddress'):
            subaddr_id = subaddr.get('id')
            subaddress_elem = subaddr.find('subaddress')
            
            if subaddress_elem is not None:
                subaddress = int(subaddress_elem.text)
                
                # Map subaddress IDs to our configuration keys
                if subaddr_id == 'mode':
                    config['subaddresses']['mode_change'] = subaddress
                    logger.info(f"Updated mode_change subaddress to {subaddress} from address book")
                elif subaddr_id == 'data':
                    config['subaddresses']['data'] = subaddress
                elif subaddr_id == 'status':
                    config['subaddresses']['status'] = subaddress
        
        logger.info("Successfully loaded RT address configuration from address book")
        return config
        
    except Exception as e:
        logger.error(f"Error loading RT address configuration from address book: {e}")
        # Return default configuration on error
        return DEFAULT_RT_CONFIG

class RTAddressConfig:
    """RT Address Configuration Manager"""
    
    def __init__(self):
        """Initialize RT address configuration."""
        self.config = self._load_config()
        logger.info("RT address configuration initialized")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load RT address configuration with operation tracking."""
        def _load_config_impl():
            return _load_rt_config_from_file()
            
        # Use operation tracker to ensure this only happens once
        result = track_operation('rt_address_config_load', 'mil_std_1553b', _load_config_impl)
        if result is None:
            # If already loaded, get the result from a previous call
            if is_operation_completed('rt_address_config_load', 'mil_std_1553b'):
                logger.info("RT address configuration already loaded, using cached values")
                # Load the configuration again to get the data
                return _load_config_impl()
        return result
        
    def get_rt_address(self, system_name: str) -> int:
        """Get RT address for a system."""
        address = self.config.get(system_name)
        if address is None:
            logger.warning(f"RT address not found for system: {system_name}, using default")
            # Return a default address if not found
            address = 0
        return address
        
    def get_subaddress(self, function_name: str) -> int:
        """Get subaddress for a function."""
        subaddress = self.config.get('subaddresses', {}).get(function_name)
        if subaddress is None:
            logger.warning(f"Subaddress not found for function: {function_name}, using default")
            # Return a default subaddress if not found
            subaddress = 0
        return subaddress
        
    def get_rt_subaddress_pair(self, system_name: str, function_name: str) -> Tuple[int, int]:
        """Get RT address and subaddress pair for a system and function."""
        rt_address = self.get_rt_address(system_name)
        subaddress = self.get_subaddress(function_name)
        return rt_address, subaddress
        
    def get_config(self) -> Dict[str, Any]:
        """Get the complete RT address configuration."""
        return self.config.copy()

def get_rt_address_config() -> RTAddressConfig:
    """Get the global RTAddressConfig instance."""
    global _rt_config
    
    # Fast path - check if instance exists without lock
    if _rt_config is not None:
        return _rt_config
    
    # Slow path - acquire lock and create instance if needed
    with _config_lock:
        # Check again in case another thread created the instance
        if _rt_config is None:
            logger.info("Creating new global RTAddressConfig instance")
            _rt_config = RTAddressConfig()
        
    return _rt_config

# Helper functions for common operations - now delegates to address_utils
def get_rt_address(system_name: str) -> int:
    """
    Get RT address for a system.
    Now delegates to the centralized address_utils module.
    
    Args:
        system_name: The system ID (e.g., 'radar', 'displays')
        
    Returns:
        int: RT address
    """
    try:
        # First try the new centralized system
        return utils_get_rt_address(system_name)
    except Exception as e:
        # Fall back to legacy system if there's any issue
        logger.warning(f"Error using address_utils for RT address, falling back to legacy: {e}")
        return get_rt_address_config().get_rt_address(system_name)
    
def get_subaddress(function_name: str) -> int:
    """
    Get subaddress for a function.
    Now delegates to the centralized address_utils module.
    
    Args:
        function_name: The subaddress ID (e.g., 'weather_radar', 'mode')
        
    Returns:
        int: Subaddress value
    """
    try:
        # First try the new centralized system
        return utils_get_subaddress(function_name)
    except Exception as e:
        # Fall back to legacy system if there's any issue
        logger.warning(f"Error using address_utils for subaddress, falling back to legacy: {e}")
        return get_rt_address_config().get_subaddress(function_name)
    
def get_rt_subaddress_pair(system_name: str, function_name: str) -> Tuple[int, int]:
    """
    Get RT address and subaddress pair for a system and function.
    Now delegates to the centralized address_utils module.
    
    Args:
        system_name: The system ID (e.g., 'radar', 'displays')
        function_name: The subaddress ID (e.g., 'weather_radar', 'mode')
        
    Returns:
        tuple: (RT address, subaddress)
    """
    try:
        # First try the new centralized system
        return utils_get_rt_subaddress_pair(system_name, function_name)
    except Exception as e:
        # Fall back to legacy system if there's any issue
        logger.warning(f"Error using address_utils for RT-SA pair, falling back to legacy: {e}")
        return get_rt_address_config().get_rt_subaddress_pair(system_name, function_name)
