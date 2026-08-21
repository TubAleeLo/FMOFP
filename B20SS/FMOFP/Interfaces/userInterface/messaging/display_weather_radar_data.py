"""
Display-specific weather radar data classes.

These are local versions of the weather radar data classes for use within the display system,
which avoids direct dependencies on the local_messaging.messageConfigurations module.
Uses display-local message types and constants for consistent message handling.
"""

import time
import uuid
import traceback
from typing import Dict, Any, Optional, Tuple, List, Union

# Import display-local modules
from .display_message_types import (
    DISPLAY_VIL_DATA, DISPLAY_PRECIPITATION_DATA,
    is_vil_message, is_precipitation_message
)

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayWeatherRadarVILData:
    """
    Display-specific implementation of VIL (Vertically Integrated Liquid) data.
    
    This class provides the same interface as the original WeatherRadarVILData class,
    but is implemented within the display system boundary.
    Uses display-local message types and constants for consistent message handling.
    """
    
    # Message type constant
    MESSAGE_TYPE = DISPLAY_VIL_DATA
    
    def __init__(self, 
                 position: Optional[Tuple[float, float]] = None,
                 value: Optional[float] = None,
                 layer_count: Optional[int] = None,
                 intensity: Optional[float] = None,
                 altitude: Optional[float] = None,
                 show_values: bool = True,
                 color_scale: Optional[List[str]] = None,
                 request_id: Optional[str] = None,
                 timestamp: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize VIL data.
        
        Args:
            position: Geographical position (latitude, longitude)
            value: VIL value in kg/m²
            layer_count: Number of layers in the VIL data
            intensity: Intensity value (0.0 to 1.0)
            altitude: Altitude in feet
            show_values: Whether to show values on display
            color_scale: List of color values for display
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        try:
            self.position = position or (0.0, 0.0)
            self.value = value or 0.0
            self.layer_count = layer_count or 0
            self.intensity = intensity or 0.0
            self.altitude = altitude or 0.0
            self.show_values = show_values
            self.color_scale = color_scale or []
            self.request_id = request_id or str(uuid.uuid4())
            self.timestamp = timestamp or time.time()
            self.metadata = metadata or {}
            
            # Add message type to metadata
            if self.metadata is None:
                self.metadata = {}
            self.metadata['message_type'] = self.MESSAGE_TYPE
            self.message_type = self.MESSAGE_TYPE
            
            # Log creation
            logger.debug(f"Created DisplayWeatherRadarVILData with value={self.value} kg/m², position={self.position}")
            
            # Note: We need to filter out anything in a default position (0.0, 0.0),
            # as it's broken data and in real life that wouldn't be accepted.
            if self.position == (0.0, 0.0):
                logger.warning(f"DisplayWeatherRadarVILData created with default position (0.0, 0.0) - this is likely invalid data")
                self.metadata['invalid_position'] = True
        except Exception as e:
            logger.error(f"Error initializing DisplayWeatherRadarVILData: {str(e)}")
            logger.error(traceback.format_exc())
            # Set default values on error
            self.position = (0.0, 0.0)
            self.value = 0.0
            self.layer_count = 0
            self.intensity = 0.0
            self.altitude = 0.0
            self.show_values = True
            self.color_scale = []
            self.request_id = str(uuid.uuid4())
            self.timestamp = time.time()
            self.metadata = {'message_type': self.MESSAGE_TYPE, 'error': str(e)}
            self.message_type = self.MESSAGE_TYPE
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert VIL data to dictionary.
        
        Returns:
            Dict: Dictionary representation of the VIL data
        """
        try:
            result = {
                'position': self.position,
                'value': self.value,
                'layer_count': self.layer_count,
                'intensity': self.intensity,
                'altitude': self.altitude,
                'show_values': self.show_values,
                'color_scale': self.color_scale,
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'metadata': self.metadata,
                'message_type': self.MESSAGE_TYPE
            }
            return result
        except Exception as e:
            logger.error(f"Error converting DisplayWeatherRadarVILData to dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal dict on error
            return {
                'message_type': self.MESSAGE_TYPE,
                'error': str(e),
                'request_id': getattr(self, 'request_id', str(uuid.uuid4())),
                'timestamp': time.time()
            }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayWeatherRadarVILData':
        """
        Create VIL data from dictionary.
        
        Args:
            data: Dictionary containing VIL data
            
        Returns:
            DisplayWeatherRadarVILData: New VIL data instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("Data must be a dictionary")
                
            # Verify this is a VIL data message
            if 'message_type' in data and not is_vil_message(data):
                logger.warning(f"Converting non-VIL message to VIL data: {data.get('message_type')}")
                
            # Extract metadata if available
            metadata = data.get('metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}
                
            # Ensure message_type is in metadata
            metadata['message_type'] = cls.MESSAGE_TYPE
                
            return cls(
                position=data.get('position'),
                value=data.get('value'),
                layer_count=data.get('layer_count'),
                intensity=data.get('intensity'),
                altitude=data.get('altitude'),
                show_values=data.get('show_values', True),
                color_scale=data.get('color_scale'),
                request_id=data.get('request_id'),
                timestamp=data.get('timestamp'),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error creating DisplayWeatherRadarVILData from dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'original_data': str(data)[:100] + '...' if isinstance(data, dict) and len(str(data)) > 100 else str(data)}
            )
        
    @classmethod
    def from_original_data(cls, data: Any) -> 'DisplayWeatherRadarVILData':
        """
        Create DisplayWeatherRadarVILData from an original WeatherRadarVILData.
        
        Args:
            data: Original WeatherRadarVILData instance
            
        Returns:
            DisplayWeatherRadarVILData: New VIL data instance
        """
        try:
            # Extract all available attributes from the original data
            attributes = {}
            for attr in ['position', 'value', 'layer_count', 'intensity', 'altitude', 
                        'show_values', 'color_scale', 'request_id', 'timestamp', 'metadata']:
                if hasattr(data, attr):
                    attributes[attr] = getattr(data, attr)
                    
            # Ensure metadata is a dictionary
            if 'metadata' not in attributes or not attributes['metadata']:
                attributes['metadata'] = {}
            elif not isinstance(attributes['metadata'], dict):
                attributes['metadata'] = {'original_metadata': str(attributes['metadata'])}
                
            # Add message type to metadata
            attributes['metadata']['message_type'] = cls.MESSAGE_TYPE
            
            # Add original message type if available
            if hasattr(data, 'message_type'):
                attributes['metadata']['original_message_type'] = getattr(data, 'message_type')
                
            # Create new VIL data with extracted attributes
            return cls(**attributes)
        except Exception as e:
            logger.error(f"Error converting original data to DisplayWeatherRadarVILData: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'conversion_error': True}
            )
        
    def is_valid(self) -> bool:
        """
        Check if this is valid data that should be processed.
        
        Returns:
            bool: True if the data is valid, False otherwise
        """
        try:
            # Check for default position (0.0, 0.0) which indicates invalid data
            if self.position == (0.0, 0.0):
                return False
                
            # Check for other invalid conditions
            if self.value <= 0.0 and self.intensity <= 0.0:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking if VIL data is valid: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """
        Get string representation of the VIL data.
        
        Returns:
            str: String representation
        """
        valid_status = "VALID" if self.is_valid() else "INVALID"
        return (f"DisplayWeatherRadarVILData(value={self.value} kg/m², "
                f"position={self.position}, intensity={self.intensity}, "
                f"request_id={self.request_id}, {valid_status})")


class DisplayPrecipitationData:
    """
    Display-specific implementation of precipitation data.
    
    This class provides the same interface as the original PrecipitationData class,
    but is implemented within the display system boundary.
    Uses display-local message types and constants for consistent message handling.
    """
    
    # Message type constant
    MESSAGE_TYPE = DISPLAY_PRECIPITATION_DATA
    
    # Precipitation types
    PRECIP_TYPE_RAIN = 'rain'
    PRECIP_TYPE_SNOW = 'snow'
    PRECIP_TYPE_HAIL = 'hail'
    PRECIP_TYPE_SLEET = 'sleet'
    PRECIP_TYPE_MIXED = 'mixed'
    
    def __init__(self, 
                 position: Optional[Tuple[float, float]] = None,
                 precip_type: Optional[str] = None,
                 rate: Optional[float] = None,
                 intensity: Optional[float] = None,
                 altitude: Optional[float] = None,
                 coverage: Optional[float] = None,
                 show_values: bool = True,
                 color_scale: Optional[List[str]] = None,
                 request_id: Optional[str] = None,
                 timestamp: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize precipitation data.
        
        Args:
            position: Geographical position (latitude, longitude)
            precip_type: Type of precipitation (rain, snow, hail, sleet, mixed)
            rate: Precipitation rate in mm/h
            intensity: Intensity value (0.0 to 1.0)
            altitude: Altitude in feet
            coverage: Coverage area in square miles
            show_values: Whether to show values on display
            color_scale: List of color values for display
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        try:
            self.position = position or (0.0, 0.0)
            self.precip_type = precip_type or self.PRECIP_TYPE_RAIN
            self.rate = rate or 0.0
            self.intensity = intensity or 0.0
            self.altitude = altitude or 0.0
            self.coverage = coverage or 0.0
            self.show_values = show_values
            self.color_scale = color_scale or []
            self.request_id = request_id or str(uuid.uuid4())
            self.timestamp = timestamp or time.time()
            self.metadata = metadata or {}
            
            # Add message type to metadata
            if self.metadata is None:
                self.metadata = {}
            self.metadata['message_type'] = self.MESSAGE_TYPE
            self.message_type = self.MESSAGE_TYPE
            
            # Log creation
            logger.debug(f"Created DisplayPrecipitationData with type={self.precip_type}, rate={self.rate} mm/h, position={self.position}")
            
            # Note: We need to filter out anything in a default position (0.0, 0.0),
            # as it's broken data and in real life that wouldn't be accepted.
            if self.position == (0.0, 0.0):
                logger.warning(f"DisplayPrecipitationData created with default position (0.0, 0.0) - this is likely invalid data")
                self.metadata['invalid_position'] = True
        except Exception as e:
            logger.error(f"Error initializing DisplayPrecipitationData: {str(e)}")
            logger.error(traceback.format_exc())
            # Set default values on error
            self.position = (0.0, 0.0)
            self.precip_type = self.PRECIP_TYPE_RAIN
            self.rate = 0.0
            self.intensity = 0.0
            self.altitude = 0.0
            self.coverage = 0.0
            self.show_values = True
            self.color_scale = []
            self.request_id = str(uuid.uuid4())
            self.timestamp = time.time()
            self.metadata = {'message_type': self.MESSAGE_TYPE, 'error': str(e)}
            self.message_type = self.MESSAGE_TYPE
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert precipitation data to dictionary.
        
        Returns:
            Dict: Dictionary representation of the precipitation data
        """
        try:
            result = {
                'position': self.position,
                'precip_type': self.precip_type,
                'rate': self.rate,
                'intensity': self.intensity,
                'altitude': self.altitude,
                'coverage': self.coverage,
                'show_values': self.show_values,
                'color_scale': self.color_scale,
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'metadata': self.metadata,
                'message_type': self.MESSAGE_TYPE
            }
            return result
        except Exception as e:
            logger.error(f"Error converting DisplayPrecipitationData to dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal dict on error
            return {
                'message_type': self.MESSAGE_TYPE,
                'error': str(e),
                'request_id': getattr(self, 'request_id', str(uuid.uuid4())),
                'timestamp': time.time()
            }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayPrecipitationData':
        """
        Create precipitation data from dictionary.
        
        Args:
            data: Dictionary containing precipitation data
            
        Returns:
            DisplayPrecipitationData: New precipitation data instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("Data must be a dictionary")
                
            # Verify this is a precipitation data message
            if 'message_type' in data and not is_precipitation_message(data):
                logger.warning(f"Converting non-precipitation message to precipitation data: {data.get('message_type')}")
                
            # Extract metadata if available
            metadata = data.get('metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}
                
            # Ensure message_type is in metadata
            metadata['message_type'] = cls.MESSAGE_TYPE
                
            return cls(
                position=data.get('position'),
                precip_type=data.get('precip_type'),
                rate=data.get('rate'),
                intensity=data.get('intensity'),
                altitude=data.get('altitude'),
                coverage=data.get('coverage'),
                show_values=data.get('show_values', True),
                color_scale=data.get('color_scale'),
                request_id=data.get('request_id'),
                timestamp=data.get('timestamp'),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error creating DisplayPrecipitationData from dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'original_data': str(data)[:100] + '...' if isinstance(data, dict) and len(str(data)) > 100 else str(data)}
            )
        
    @classmethod
    def from_original_data(cls, data: Any) -> 'DisplayPrecipitationData':
        """
        Create DisplayPrecipitationData from an original PrecipitationData.
        
        Args:
            data: Original PrecipitationData instance
            
        Returns:
            DisplayPrecipitationData: New precipitation data instance
        """
        try:
            # Extract all available attributes from the original data
            attributes = {}
            for attr in ['position', 'precip_type', 'rate', 'intensity', 'altitude', 
                        'coverage', 'show_values', 'color_scale', 'request_id', 
                        'timestamp', 'metadata']:
                if hasattr(data, attr):
                    attributes[attr] = getattr(data, attr)
                    
            # Ensure metadata is a dictionary
            if 'metadata' not in attributes or not attributes['metadata']:
                attributes['metadata'] = {}
            elif not isinstance(attributes['metadata'], dict):
                attributes['metadata'] = {'original_metadata': str(attributes['metadata'])}
                
            # Add message type to metadata
            attributes['metadata']['message_type'] = cls.MESSAGE_TYPE
            
            # Add original message type if available
            if hasattr(data, 'message_type'):
                attributes['metadata']['original_message_type'] = getattr(data, 'message_type')
                
            # Create new precipitation data with extracted attributes
            return cls(**attributes)
        except Exception as e:
            logger.error(f"Error converting original data to DisplayPrecipitationData: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'conversion_error': True}
            )
        
    def get_intensity_level(self) -> str:
        """
        Get intensity level description based on precipitation rate.
        
        Returns:
            str: Intensity level description
        """
        try:
            if self.precip_type == self.PRECIP_TYPE_RAIN:
                if self.rate < 2.5:
                    return "Light"
                elif self.rate < 10.0:
                    return "Moderate"
                elif self.rate < 50.0:
                    return "Heavy"
                else:
                    return "Violent"
            elif self.precip_type == self.PRECIP_TYPE_SNOW:
                if self.rate < 1.0:
                    return "Light"
                elif self.rate < 5.0:
                    return "Moderate"
                else:
                    return "Heavy"
            elif self.precip_type == self.PRECIP_TYPE_HAIL:
                if self.rate < 2.0:
                    return "Small"
                elif self.rate < 5.0:
                    return "Medium"
                else:
                    return "Large"
            else:
                return "Unknown"
        except Exception as e:
            logger.error(f"Error getting intensity level: {str(e)}")
            return "Error"
        
    def is_valid(self) -> bool:
        """
        Check if this is valid data that should be processed.
        
        Returns:
            bool: True if the data is valid, False otherwise
        """
        try:
            # Check for default position (0.0, 0.0) which indicates invalid data
            if self.position == (0.0, 0.0):
                return False
                
            # Check for other invalid conditions
            if self.rate <= 0.0 and self.intensity <= 0.0 and self.coverage <= 0.0:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking if precipitation data is valid: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """
        Get string representation of the precipitation data.
        
        Returns:
            str: String representation
        """
        valid_status = "VALID" if self.is_valid() else "INVALID"
        return (f"DisplayPrecipitationData(type={self.precip_type}, rate={self.rate} mm/h, "
                f"position={self.position}, intensity={self.intensity}, {valid_status})")
