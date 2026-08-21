"""
Display-specific precipitation data message definitions.
"""

import time
from typing import Dict, Any, Optional, Tuple, List, Union
from .display_message_base import DisplayBaseMessage
from ..display_message_types import DISPLAY_PRECIPITATION_DATA
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayPrecipitationData(DisplayBaseMessage):
    """Display-specific precipitation data message."""
    
    # Precipitation types
    PRECIP_TYPE_RAIN = 'rain'
    PRECIP_TYPE_SNOW = 'snow'
    PRECIP_TYPE_HAIL = 'hail'
    PRECIP_TYPE_SLEET = 'sleet'
    PRECIP_TYPE_MIXED = 'mixed'
    
    def __init__(self, position: Optional[Tuple[float, float]] = None, 
                 precip_type: Optional[str] = None, 
                 rate: Optional[float] = None, 
                 intensity: Optional[float] = None,
                 altitude: Optional[float] = None,
                 coverage: Optional[float] = None,
                 show_values: bool = True, 
                 color_scale: Optional[List[str]] = None,
                 data_points: Optional[List[Dict[str, Any]]] = None,
                 request_id: Optional[str] = None, 
                 timestamp: Optional[float] = None, 
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a precipitation data message.
        
        Args:
            position: Geographical position (latitude, longitude)
            precip_type: Type of precipitation (rain, snow, hail, sleet, mixed)
            rate: Precipitation rate in mm/h
            intensity: Intensity value (0.0 to 1.0)
            altitude: Altitude in feet
            coverage: Coverage area in square miles
            show_values: Whether to show values on display
            color_scale: List of color values for display
            data_points: List of individual data points
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        super().__init__(request_id, timestamp, metadata, DISPLAY_PRECIPITATION_DATA)
        self.position = position or (0.0, 0.0)
        self.precip_type = precip_type or self.PRECIP_TYPE_RAIN
        self.rate = rate or 0.0
        self.intensity = intensity or 0.0
        self.altitude = altitude or 0.0
        self.coverage = coverage or 0.0
        self.show_values = show_values
        self.color_scale = color_scale or []
        self.data_points = data_points or []
        
        # Add precipitation-specific metadata
        self.add_metadata('data_type', 'precipitation')
        self.add_metadata('precip_type', self.precip_type)
        self.add_metadata('rate_unit', 'mm/h')
        
        # Log creation with precipitation-specific details
        logger.debug(f"Created precipitation data message with type={self.precip_type}, rate={self.rate} mm/h, position={self.position}")
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dict: Dictionary representation of the message
        """
        data = super().to_dict()
        data.update({
            'position': self.position,
            'precip_type': self.precip_type,
            'rate': self.rate,
            'intensity': self.intensity,
            'altitude': self.altitude,
            'coverage': self.coverage,
            'show_values': self.show_values,
            'color_scale': self.color_scale,
            'data_points': self.data_points
        })
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayPrecipitationData':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            DisplayPrecipitationData: New message instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
            
        return cls(
            position=data.get('position'),
            precip_type=data.get('precip_type'),
            rate=data.get('rate'),
            intensity=data.get('intensity'),
            altitude=data.get('altitude'),
            coverage=data.get('coverage'),
            show_values=data.get('show_values', True),
            color_scale=data.get('color_scale'),
            data_points=data.get('data_points'),
            request_id=data.get('request_id'),
            timestamp=data.get('timestamp'),
            metadata=data.get('metadata')
        )
        
    @classmethod
    def from_weather_radar_response(cls, response: Dict[str, Any]) -> 'DisplayPrecipitationData':
        """
        Create precipitation data message from weather radar response.
        
        Args:
            response: Weather radar response data
            
        Returns:
            DisplayPrecipitationData: New message instance
            
        Raises:
            ValueError: If response is not a dictionary or is missing required fields
        """
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
            
        # Extract precipitation data from response
        precip_data = response.get('data', {}).get('precipitation_data', {})
        if not precip_data:
            raise ValueError("Response missing precipitation data")
            
        # Extract metadata
        metadata = response.get('metadata', {})
        if 'transaction_id' not in metadata:
            metadata['transaction_id'] = response.get('request_id', '')
            
        # Create precipitation data message
        return cls(
            position=precip_data.get('position'),
            precip_type=precip_data.get('type'),
            rate=precip_data.get('rate'),
            intensity=precip_data.get('intensity'),
            altitude=precip_data.get('altitude'),
            coverage=precip_data.get('coverage'),
            show_values=precip_data.get('show_values', True),
            color_scale=precip_data.get('color_scale'),
            data_points=precip_data.get('data_points'),
            request_id=response.get('request_id'),
            timestamp=response.get('timestamp'),
            metadata=metadata
        )
        
    def get_intensity_level(self) -> str:
        """
        Get intensity level description based on precipitation rate.
        
        Returns:
            str: Intensity level description
        """
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
            
    def __str__(self) -> str:
        """
        Get string representation of the message.
        
        Returns:
            str: String representation
        """
        return f"DisplayPrecipitationData(request_id={self.request_id}, type={self.precip_type}, rate={self.rate} mm/h, intensity={self.get_intensity_level()})"
