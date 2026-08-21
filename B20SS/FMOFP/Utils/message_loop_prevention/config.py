"""
Message Loop Prevention Configuration

This module provides configuration options for the message loop prevention system.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

# Get logger
try:
    from FMOFP.Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    # Fall back to standard logging if system logger not available
    logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    # General settings
    "enabled": True,
    "log_level": "warning",
    
    # Message tracking settings
    "max_tracked_messages": 1000,
    "expiration_time": 60.0,  # seconds
    
    # Service-specific settings
    "services": {
        "vil_handler": {
            "enabled": True,
            "max_tracked_messages": 500,
            "expiration_time": 30.0
        },
        "vil_response_service": {
            "enabled": True,
            "max_tracked_messages": 500,
            "expiration_time": 30.0
        },
        "precipitation_handler": {
            "enabled": True,
            "max_tracked_messages": 500,
            "expiration_time": 30.0
        },
        "unified_router": {
            "enabled": True,
            "max_tracked_messages": 1000,
            "expiration_time": 60.0
        }
    },
    
    # Category-specific settings
    "categories": {
        "vil": {
            "enabled": True,
            "max_tracked_messages": 500,
            "expiration_time": 30.0
        },
        "precipitation": {
            "enabled": True,
            "max_tracked_messages": 500,
            "expiration_time": 30.0
        },
        "mode_change": {
            "enabled": True,
            "max_tracked_messages": 200,
            "expiration_time": 20.0
        }
    }
}

class MessageLoopPreventionConfig:
    """Configuration for message loop prevention."""
    
    _instance = None  # Singleton instance
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = MessageLoopPreventionConfig()
        return cls._instance
    
    def __init__(self):
        """Initialize with default configuration."""
        self._config = DEFAULT_CONFIG.copy()
        self._config_file = None
        self._loaded = False
        
        # Try to load configuration from environment variable
        config_file = os.environ.get('MESSAGE_LOOP_PREVENTION_CONFIG')
        if config_file:
            self.load_from_file(config_file)
    
    def load_from_file(self, file_path: str) -> bool:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            bool: True if configuration was loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Configuration file not found: {file_path}")
                return False
                
            with open(file_path, 'r') as f:
                config = json.load(f)
                
            # Update configuration
            self._update_config(config)
            self._config_file = file_path
            self._loaded = True
            
            logger.info(f"Loaded message loop prevention configuration from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading configuration from {file_path}: {e}")
            return False
    
    def _update_config(self, config: Dict[str, Any]):
        """
        Update configuration with new values.
        
        Args:
            config: New configuration values
        """
        # Update top-level settings
        for key in ['enabled', 'log_level', 'max_tracked_messages', 'expiration_time']:
            if key in config:
                self._config[key] = config[key]
        
        # Update service-specific settings
        if 'services' in config:
            for service, settings in config['services'].items():
                if service not in self._config['services']:
                    self._config['services'][service] = {}
                for key, value in settings.items():
                    self._config['services'][service][key] = value
        
        # Update category-specific settings
        if 'categories' in config:
            for category, settings in config['categories'].items():
                if category not in self._config['categories']:
                    self._config['categories'][category] = {}
                for key, value in settings.items():
                    self._config['categories'][category][key] = value
    
    def save_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Save configuration to a JSON file.
        
        Args:
            file_path: Path to the configuration file, or None to use the previously loaded file
            
        Returns:
            bool: True if configuration was saved successfully, False otherwise
        """
        try:
            if file_path is None:
                if self._config_file is None:
                    logger.warning("No configuration file specified")
                    return False
                file_path = self._config_file
                
            with open(file_path, 'w') as f:
                json.dump(self._config, f, indent=2)
                
            logger.info(f"Saved message loop prevention configuration to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {file_path}: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration.
        
        Returns:
            Dict[str, Any]: Current configuration
        """
        return self._config.copy()
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dict[str, Any]: Service configuration, or default configuration if service not found
        """
        if service_name in self._config['services']:
            # Start with default values
            config = {
                'enabled': self._config['enabled'],
                'max_tracked_messages': self._config['max_tracked_messages'],
                'expiration_time': self._config['expiration_time']
            }
            # Override with service-specific values
            config.update(self._config['services'][service_name])
            return config
        else:
            # Return default configuration
            return {
                'enabled': self._config['enabled'],
                'max_tracked_messages': self._config['max_tracked_messages'],
                'expiration_time': self._config['expiration_time']
            }
    
    def get_category_config(self, category: str) -> Dict[str, Any]:
        """
        Get configuration for a specific category.
        
        Args:
            category: Name of the category
            
        Returns:
            Dict[str, Any]: Category configuration, or default configuration if category not found
        """
        if category in self._config['categories']:
            # Start with default values
            config = {
                'enabled': self._config['enabled'],
                'max_tracked_messages': self._config['max_tracked_messages'],
                'expiration_time': self._config['expiration_time']
            }
            # Override with category-specific values
            config.update(self._config['categories'][category])
            return config
        else:
            # Return default configuration
            return {
                'enabled': self._config['enabled'],
                'max_tracked_messages': self._config['max_tracked_messages'],
                'expiration_time': self._config['expiration_time']
            }
    
    def update_config(self, config: Dict[str, Any]):
        """
        Update configuration with new values.
        
        Args:
            config: New configuration values
        """
        self._update_config(config)
        
        # Save to file if one was previously loaded
        if self._loaded and self._config_file:
            self.save_to_file(self._config_file)
    
    def is_enabled(self) -> bool:
        """
        Check if message loop prevention is enabled.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        return self._config['enabled']
    
    def is_service_enabled(self, service_name: str) -> bool:
        """
        Check if message loop prevention is enabled for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            bool: True if enabled, False otherwise
        """
        if not self._config['enabled']:
            return False
            
        if service_name in self._config['services']:
            return self._config['services'][service_name].get('enabled', True)
        else:
            return True
    
    def is_category_enabled(self, category: str) -> bool:
        """
        Check if message loop prevention is enabled for a specific category.
        
        Args:
            category: Name of the category
            
        Returns:
            bool: True if enabled, False otherwise
        """
        if not self._config['enabled']:
            return False
            
        if category in self._config['categories']:
            return self._config['categories'][category].get('enabled', True)
        else:
            return True

def get_config() -> MessageLoopPreventionConfig:
    """Get the singleton instance of MessageLoopPreventionConfig."""
    return MessageLoopPreventionConfig.get_instance()
