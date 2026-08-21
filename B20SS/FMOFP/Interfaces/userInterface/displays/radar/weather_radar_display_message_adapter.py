"""
Weather Radar Display Message Adapter

Normalizes various message formats for the weather radar display system.
Uses display-local message types and constants for consistent message handling.
"""

import time
from typing import Any, Dict, Union, Optional

# Import display-local modules
from ...messaging.display_message_types import (
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE,
    DISPLAY_VIL_DATA,
    DISPLAY_PRECIPITATION_DATA,
    is_precipitation_message,
    is_vil_message
)
from ...messaging.display_address_utils import (
    DISPLAY_RT_ADDRESS,
    WEATHER_RADAR_RT_ADDRESS
)

# Import radar enums
from .radar_enums import weather_radarMode

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Constants for message types - centralized for easier maintenance
MESSAGE_TYPE_VIL = 'vil_data'
MESSAGE_TYPE_PRECIPITATION = 'precipitation_data'
MESSAGE_TYPE_MODE_CHANGE = 'mode_change'
DATA_TYPE_VIL = 'vil'
DATA_TYPE_PRECIPITATION = 'precipitation'
SOURCE_SYSTEM_WEATHER_RADAR = 'weather_radar'

class WeatherRadarDisplayMessageAdapter:
    """Adapts various message formats for the weather radar display system."""
    
    @staticmethod
    def normalize_message(message: Any) -> Dict[str, Any]:
        """
        Normalize any message to a standard format for the display system.
        
        Args:
            message: The message to normalize
            
        Returns:
            Dict: A normalized message dictionary
        """
        # Extract command_type from message if it exists
        command_type = None
        if isinstance(message, dict) and 'command_type' in message:
            command_type = message['command_type']
        elif hasattr(message, 'command_type'):
            command_type = message.command_type
            
        # Log the original command_type for debugging
        if command_type:
            logger.info(f"[DISPLAY_ADAPTER] Original message command_type: {command_type}")
            
        # Check for precipitation_message flag in metadata
        has_precipitation_flag = False
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
            if isinstance(metadata, dict) and 'precipitation_message' in metadata:
                has_precipitation_flag = True
                logger.info("[DISPLAY_ADAPTER] Found precipitation_message flag in metadata")
                # Force command_type to precipitation_data for consistent routing
                command_type = 'precipitation_data'
        elif hasattr(message, 'metadata'):
            metadata = message.metadata
            if isinstance(metadata, dict) and 'precipitation_message' in metadata:
                has_precipitation_flag = True
                logger.info("[DISPLAY_ADAPTER] Found precipitation_message flag in metadata attribute")
                # Force command_type to precipitation_data for consistent routing
                command_type = 'precipitation_data'
                
        # Determine message type and call appropriate specialized normalizer
        if command_type:
            if command_type == DISPLAY_COMMAND_TYPE_MODE:
                return WeatherRadarDisplayMessageAdapter.normalize_mode_message(message)
            elif command_type == 'data':
                # Check for VIL data
                if WeatherRadarDisplayMessageAdapter._is_vil_data(message):
                    return WeatherRadarDisplayMessageAdapter.normalize_vil_data(message)
                # Check for precipitation data
                elif WeatherRadarDisplayMessageAdapter._is_precipitation_data(message):
                    return WeatherRadarDisplayMessageAdapter.normalize_precipitation_data(message)
            elif command_type == DISPLAY_PRECIPITATION_DATA:
                # Force to precipitation_data for consistent routing
                logger.info("[DISPLAY_ADAPTER] Detected precipitation data from command_type")
                return WeatherRadarDisplayMessageAdapter.normalize_precipitation_data(message)
            elif command_type == DISPLAY_VIL_DATA:
                # Force to vil_data for consistent routing
                logger.info("[DISPLAY_ADAPTER] Detected VIL data from command_type")
                return WeatherRadarDisplayMessageAdapter.normalize_vil_data(message)
        
        # If we can't determine the type, try to infer it
        if WeatherRadarDisplayMessageAdapter._is_mode_message(message):
            return WeatherRadarDisplayMessageAdapter.normalize_mode_message(message)
        elif WeatherRadarDisplayMessageAdapter._is_vil_data(message):
            return WeatherRadarDisplayMessageAdapter.normalize_vil_data(message)
        elif WeatherRadarDisplayMessageAdapter._is_precipitation_data(message) or has_precipitation_flag:
            return WeatherRadarDisplayMessageAdapter.normalize_precipitation_data(message)
        
        # Default to a generic normalized message with command_type preserved
        normalized = {
            'message_type': None,
            'data': message,
            'timestamp': time.time()
        }
        
        # Preserve command_type if it exists
        if command_type:
            normalized['command_type'] = command_type
            logger.info(f"[DISPLAY_ADAPTER] Preserved command_type in default case: {command_type}")
            
        return normalized
    
    @staticmethod
    def normalize_mode_message(mode_data: Union[Dict[str, Any], str, Any]) -> Dict[str, Any]:
        """
        Normalize mode message to standard format.
        
        Args:
            mode_data: Mode data in various formats
            
        Returns:
            Dict: Normalized mode data
        """
        try:
            # Initialize with default values using centralized constants
            normalized = {
                'current_mode': None,
                'mode_value': None,
                'source_system': SOURCE_SYSTEM_WEATHER_RADAR,
                'timestamp': time.time(),
                'force_update': False,
                'rt_address': None,
                'message_type': MESSAGE_TYPE_MODE_CHANGE,
                'command_type': DISPLAY_COMMAND_TYPE_MODE_CHANGE
            }
            
            # Handle string mode data
            if isinstance(mode_data, str):
                normalized['current_mode'] = mode_data
                logger.info(f"[DISPLAY_ADAPTER] Normalized string mode: {mode_data}")
            
            # Handle dictionary mode data
            elif isinstance(mode_data, dict):
                # Extract mode information
                normalized['current_mode'] = mode_data.get('current_mode', mode_data.get('mode'))
                normalized['mode_value'] = mode_data.get('mode_value')
                normalized['source_system'] = mode_data.get('source_system', normalized['source_system'])
                normalized['force_update'] = mode_data.get('force_update', False)
                normalized['rt_address'] = mode_data.get('rt_address')
                
                # Extract request_id if present
                if 'request_id' in mode_data:
                    normalized['request_id'] = mode_data['request_id']
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized dict mode: {normalized['current_mode']}")
            
            # Handle object mode data
            elif hasattr(mode_data, 'current_mode') or hasattr(mode_data, 'mode'):
                # Get current_mode attribute
                if hasattr(mode_data, 'current_mode'):
                    normalized['current_mode'] = mode_data.current_mode
                elif hasattr(mode_data, 'mode'):
                    normalized['current_mode'] = mode_data.mode
                
                # Get other attributes if available
                if hasattr(mode_data, 'mode_value'):
                    normalized['mode_value'] = mode_data.mode_value
                if hasattr(mode_data, 'source_system'):
                    normalized['source_system'] = mode_data.source_system
                if hasattr(mode_data, 'force_update'):
                    normalized['force_update'] = mode_data.force_update
                if hasattr(mode_data, 'rt_address'):
                    normalized['rt_address'] = mode_data.rt_address
                if hasattr(mode_data, 'request_id'):
                    normalized['request_id'] = mode_data.request_id
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized object mode: {normalized['current_mode']}")
            
            # Handle weather_radarMode enum
            elif isinstance(mode_data, weather_radarMode):
                normalized['current_mode'] = mode_data.name
                normalized['mode_value'] = mode_data.value
                logger.info(f"[DISPLAY_ADAPTER] Normalized enum mode: {normalized['current_mode']}")
            
            # Handle integer mode value
            elif isinstance(mode_data, int):
                try:
                    mode_enum = weather_radarMode(mode_data)
                    normalized['current_mode'] = mode_enum.name
                    normalized['mode_value'] = mode_data
                    logger.info(f"[DISPLAY_ADAPTER] Normalized int mode: {normalized['current_mode']}")
                except ValueError:
                    logger.error(f"[DISPLAY_ADAPTER] Invalid mode value: {mode_data}")
            
            # Map RT address to weather radar if needed using centralized constants
            if normalized['rt_address'] == WEATHER_RADAR_RT_ADDRESS:
                logger.info(f"[DISPLAY_ADAPTER] Mapped RT address {WEATHER_RADAR_RT_ADDRESS} to weather radar")
                normalized['source_system'] = SOURCE_SYSTEM_WEATHER_RADAR
            
            # Validate the normalized mode
            if not normalized['current_mode']:
                logger.error("[DISPLAY_ADAPTER] Failed to normalize mode data")
                return normalized
            
            # Ensure mode is uppercase for enum lookup
            if isinstance(normalized['current_mode'], str):
                normalized['current_mode'] = normalized['current_mode'].upper()
            
            # Try to get mode value if not already set
            if normalized['mode_value'] is None and normalized['current_mode']:
                try:
                    mode_enum = getattr(weather_radarMode, normalized['current_mode'])
                    normalized['mode_value'] = mode_enum.value
                    logger.info(f"[DISPLAY_ADAPTER] Set mode value: {normalized['mode_value']}")
                except (AttributeError, ValueError):
                    logger.warning(f"[DISPLAY_ADAPTER] Could not get mode value for: {normalized['current_mode']}")
            
            return normalized
            
        except Exception as e:
            logger.error(f"[DISPLAY_ADAPTER] Error normalizing mode message: {str(e)}")
            return {
                'current_mode': 'STANDBY',  # Default to STANDBY on error
                'mode_value': 1,
                'source_system': SOURCE_SYSTEM_WEATHER_RADAR,
                'timestamp': time.time(),
                'message_type': MESSAGE_TYPE_MODE_CHANGE,
                'command_type': DISPLAY_COMMAND_TYPE_MODE_CHANGE,
                'force_update': True,  # Force update on error
                'error': str(e)
            }
    
    @staticmethod
    def normalize_vil_data(vil_data: Any) -> Dict[str, Any]:
        """
        Normalize VIL data to standard format.
        
        Args:
            vil_data: VIL data in various formats
            
        Returns:
            Dict: Normalized VIL data
        """
        try:
            # Initialize with default values using centralized constants
            normalized = {
                'data_type': DATA_TYPE_VIL,
                'data': [],
                'source_system': SOURCE_SYSTEM_WEATHER_RADAR,
                'timestamp': time.time(),
                'message_type': MESSAGE_TYPE_VIL,
                'command_type': DISPLAY_VIL_DATA,
                'rt_address': None,
                'show_values': True
            }
            
            # Handle dictionary VIL data
            if isinstance(vil_data, dict):
                # Extract VIL data list
                if 'data' in vil_data:
                    normalized['data'] = vil_data['data']
                elif 'vil_data' in vil_data:
                    normalized['data'] = vil_data['vil_data']
                
                # Extract other fields
                normalized['source_system'] = vil_data.get('source_system', normalized['source_system'])
                normalized['rt_address'] = vil_data.get('rt_address')
                normalized['show_values'] = vil_data.get('show_values', True)
                
                # Extract request_id if present
                if 'request_id' in vil_data:
                    normalized['request_id'] = vil_data['request_id']
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized dict VIL data with {len(normalized['data'])} points")
            
            # Handle object VIL data
            elif hasattr(vil_data, 'data') or hasattr(vil_data, 'vil_data'):
                # Get data attribute
                if hasattr(vil_data, 'data'):
                    normalized['data'] = vil_data.data
                elif hasattr(vil_data, 'vil_data'):
                    normalized['data'] = vil_data.vil_data
                
                # Get other attributes if available
                if hasattr(vil_data, 'source_system'):
                    normalized['source_system'] = vil_data.source_system
                if hasattr(vil_data, 'rt_address'):
                    normalized['rt_address'] = vil_data.rt_address
                if hasattr(vil_data, 'show_values'):
                    normalized['show_values'] = vil_data.show_values
                if hasattr(vil_data, 'request_id'):
                    normalized['request_id'] = vil_data.request_id
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized object VIL data with {len(normalized['data'])} points")
            
            # Handle list VIL data (direct list of VIL points)
            elif isinstance(vil_data, list):
                normalized['data'] = vil_data
                logger.info(f"[DISPLAY_ADAPTER] Normalized list VIL data with {len(normalized['data'])} points")
            
            # Handle single VIL data point
            elif hasattr(vil_data, 'position') or (isinstance(vil_data, dict) and 'position' in vil_data):
                normalized['data'] = [vil_data]
                logger.info("[DISPLAY_ADAPTER] Normalized single VIL data point")
            
            # Map RT address to weather radar if needed using centralized constants
            if normalized['rt_address'] == WEATHER_RADAR_RT_ADDRESS:
                logger.info(f"[DISPLAY_ADAPTER] Mapped RT address {WEATHER_RADAR_RT_ADDRESS} to weather radar")
                normalized['source_system'] = SOURCE_SYSTEM_WEATHER_RADAR
            
            # Ensure data is a list
            if not isinstance(normalized['data'], list):
                normalized['data'] = [normalized['data']] if normalized['data'] else []
            

            
            return normalized
            
        except Exception as e:
            logger.error(f"[DISPLAY_ADAPTER] Error normalizing VIL data: {str(e)}")

    
    @staticmethod
    def normalize_precipitation_data(precip_data: Any) -> Dict[str, Any]:
        """
        Normalize precipitation data to standard format.
        
        Args:
            precip_data: Precipitation data in various formats
            
        Returns:
            Dict: Normalized precipitation data
        """
        try:
            # Initialize with default values using centralized constants
            normalized = {
                'data_type': DATA_TYPE_PRECIPITATION,
                'data': [],
                'source_system': SOURCE_SYSTEM_WEATHER_RADAR,
                'timestamp': time.time(),
                'message_type': MESSAGE_TYPE_PRECIPITATION,
                'command_type': DISPLAY_PRECIPITATION_DATA,  # Always set command_type
                'rt_address': None,
                'show_values': True,
                'metadata': {
                    'precipitation_message': True,  # Add precipitation_message flag
                    'command_type': DISPLAY_PRECIPITATION_DATA  # Also set command_type in metadata
                }
            }
            
            # Log that we're normalizing precipitation data with command_type
            logger.info("[DISPLAY_ADAPTER] Normalizing precipitation data with command_type=precipitation_data")
            
            # Handle dictionary precipitation data
            if isinstance(precip_data, dict):
                # Extract precipitation data list
                if 'data' in precip_data:
                    normalized['data'] = precip_data['data']
                elif 'precipitation_data' in precip_data:
                    normalized['data'] = precip_data['precipitation_data']
                
                # Extract other fields
                normalized['source_system'] = precip_data.get('source_system', normalized['source_system'])
                normalized['rt_address'] = precip_data.get('rt_address')
                normalized['show_values'] = precip_data.get('show_values', True)
                
                # Extract request_id if present
                if 'request_id' in precip_data:
                    normalized['request_id'] = precip_data['request_id']
                    
                # Preserve command_type if it exists (but ensure it's precipitation_data)
                if 'command_type' in precip_data:
                    # Always set to precipitation_data for consistent routing
                    normalized['command_type'] = 'precipitation_data'
                    normalized['metadata']['command_type'] = 'precipitation_data'
                    
                # Preserve metadata if it exists
                if 'metadata' in precip_data and isinstance(precip_data['metadata'], dict):
                    # Merge with our metadata, preserving precipitation_message flag
                    for key, value in precip_data['metadata'].items():
                        if key != 'precipitation_message' and key != 'command_type':
                            normalized['metadata'][key] = value
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized dict precipitation data with {len(normalized['data'])} points")
            
            # Handle object precipitation data
            elif hasattr(precip_data, 'data') or hasattr(precip_data, 'precipitation_data'):
                # Get data attribute
                if hasattr(precip_data, 'data'):
                    normalized['data'] = precip_data.data
                elif hasattr(precip_data, 'precipitation_data'):
                    normalized['data'] = precip_data.precipitation_data
                
                # Get other attributes if available
                if hasattr(precip_data, 'source_system'):
                    normalized['source_system'] = precip_data.source_system
                if hasattr(precip_data, 'rt_address'):
                    normalized['rt_address'] = precip_data.rt_address
                if hasattr(precip_data, 'show_values'):
                    normalized['show_values'] = precip_data.show_values
                if hasattr(precip_data, 'request_id'):
                    normalized['request_id'] = precip_data.request_id
                
                logger.info(f"[DISPLAY_ADAPTER] Normalized object precipitation data with {len(normalized['data'])} points")
            
            # Handle list precipitation data (direct list of precipitation points)
            elif isinstance(precip_data, list):
                normalized['data'] = precip_data
                logger.info(f"[DISPLAY_ADAPTER] Normalized list precipitation data with {len(normalized['data'])} points")
            
            # Handle single precipitation data point
            elif hasattr(precip_data, 'position') or (isinstance(precip_data, dict) and 'position' in precip_data):
                normalized['data'] = [precip_data]
                logger.info("[DISPLAY_ADAPTER] Normalized single precipitation data point")
            
            # Map RT address to weather radar if needed using centralized constants
            if normalized['rt_address'] == WEATHER_RADAR_RT_ADDRESS:
                logger.info(f"[DISPLAY_ADAPTER] Mapped RT address {WEATHER_RADAR_RT_ADDRESS} to weather radar")
                normalized['source_system'] = SOURCE_SYSTEM_WEATHER_RADAR
            
            # Ensure data is a list
            if not isinstance(normalized['data'], list):
                normalized['data'] = [normalized['data']] if normalized['data'] else []
            
            # Log the normalized message structure
            logger.info(f"[DISPLAY_ADAPTER] Normalized precipitation data with command_type={normalized['command_type']}")
            logger.info(f"[DISPLAY_ADAPTER] Added precipitation_message flag to metadata")
            
            return normalized
            
        except Exception as e:
            logger.error(f"[DISPLAY_ADAPTER] Error normalizing precipitation data: {str(e)}")
            # Return a basic normalized message with empty data using centralized constants
            return {
                'data_type': DATA_TYPE_PRECIPITATION,
                'data': [],
                'source_system': SOURCE_SYSTEM_WEATHER_RADAR,
                'timestamp': time.time(),
                'message_type': MESSAGE_TYPE_PRECIPITATION,
                'command_type': DISPLAY_PRECIPITATION_DATA,
                'error': str(e),
                'force_update': True  # Force update on error
            }
    
    @staticmethod
    def _is_mode_message(message: Any) -> bool:
        """
        Determine if a message is a mode change message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a mode change message
        """
        # Check dictionary message
        if isinstance(message, dict):
            # Check for mode-related keys
            if any(key in message for key in ['mode', 'current_mode']):
                return True
            # Check for command_type
            if message.get('command_type') == DISPLAY_COMMAND_TYPE_MODE:
                return True
            # Check for message_type
            if 'message_type' in message and 'mode' in str(message['message_type']).lower():
                return True
        
        # Check object message
        if hasattr(message, 'command_type') and message.command_type == DISPLAY_COMMAND_TYPE_MODE:
            return True
        if hasattr(message, 'message_type') and 'mode' in str(message.message_type).lower():
            return True
        if hasattr(message, 'mode') or hasattr(message, 'current_mode'):
            return True
        
        # Check if it's a weather_radarMode enum
        if isinstance(message, weather_radarMode):
            return True
        
        return False
    
    @staticmethod
    def _is_vil_data(message: Any) -> bool:
        """
        Determine if a message contains VIL data.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message contains VIL data
        """
        # Use the display-local helper function first
        if is_vil_message(message):
            return True
            
        # Additional checks for VIL data
        # Check dictionary message
        if isinstance(message, dict):
            # Check for VIL-related keys
            if any(key in message for key in ['vil', 'vil_data']):
                return True
            # Check for data_type
            if message.get('data_type') == DATA_TYPE_VIL:
                return True
            # Check for message_type
            if 'message_type' in message and 'vil' in str(message['message_type']).lower():
                return True
            # Check for command_type and data
            if message.get('command_type') == 'data' and isinstance(message.get('data'), list):
                # Check if data has position and value attributes typical of VIL data
                for item in message.get('data', []):
                    if isinstance(item, dict) and 'position' in item and 'value' in item:
                        return True
        
        # Check object message
        if hasattr(message, 'data_type') and message.data_type == DATA_TYPE_VIL:
            return True
        if hasattr(message, 'message_type') and 'vil' in str(message.message_type).lower():
            return True
        if hasattr(message, 'vil') or hasattr(message, 'vil_data'):
            return True
        
        # Check class name
        if hasattr(message, '__class__'):
            class_name = message.__class__.__name__.lower()
            if 'vil' in class_name:
                return True
        
        return False
    
    @staticmethod
    def _is_precipitation_data(message: Any) -> bool:
        """
        Determine if a message contains precipitation data.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message contains precipitation data
        """
        # Use the display-local helper function first
        if is_precipitation_message(message):
            return True
            
        # Additional checks for precipitation data
        # Check dictionary message
        if isinstance(message, dict):
            # Check for precipitation-related keys
            if any(key in message for key in ['precipitation', 'precipitation_data', 'precip']):
                return True
            # Check for data_type
            if message.get('data_type') == DATA_TYPE_PRECIPITATION:
                return True
            # Check for message_type
            if 'message_type' in message and any(term in str(message['message_type']).lower() for term in ['precipitation', 'precip']):
                return True
        
        # Check object message
        if hasattr(message, 'data_type') and message.data_type == DATA_TYPE_PRECIPITATION:
            return True
        if hasattr(message, 'message_type') and any(term in str(message.message_type).lower() for term in ['precipitation', 'precip']):
            return True
        if hasattr(message, 'precipitation') or hasattr(message, 'precipitation_data') or hasattr(message, 'precip'):
            return True
        
        # Check class name
        if hasattr(message, '__class__'):
            class_name = message.__class__.__name__.lower()
            if 'precipitation' in class_name or 'precip' in class_name:
                return True
        
        return False

# Singleton instance
_weather_radar_display_message_adapter = None

def get_weather_radar_display_message_adapter():
    """Get the singleton instance of WeatherRadarDisplayMessageAdapter."""
    global _weather_radar_display_message_adapter
    if _weather_radar_display_message_adapter is None:
        _weather_radar_display_message_adapter = WeatherRadarDisplayMessageAdapter()
    return _weather_radar_display_message_adapter
