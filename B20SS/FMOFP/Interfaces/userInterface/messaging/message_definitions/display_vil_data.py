"""
Display-specific VIL data message definitions.
"""

import time
from typing import Dict, Any, Optional, Tuple, List, Union
from .display_message_base import DisplayBaseMessage
from ..display_message_types import DISPLAY_VIL_DATA
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayVILData(DisplayBaseMessage):
    """Display-specific VIL (Vertically Integrated Liquid) data message."""
    
    def __init__(self, position: Optional[Tuple[float, float]] = None, 
                 value: Optional[float] = None, 
                 layer_count: Optional[int] = None, 
                 intensity: Optional[float] = None,
                 altitude: Optional[float] = None,
                 show_values: bool = True, 
                 color_scale: Optional[List[str]] = None,
                 data_points: Optional[List[Dict[str, Any]]] = None,
                 request_id: Optional[str] = None, 
                 timestamp: Optional[float] = None, 
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a VIL data message.
        
        Args:
            position: Geographical position (latitude, longitude)
            value: VIL value in kg/m²
            layer_count: Number of layers in the VIL data
            intensity: Intensity value (0.0 to 1.0)
            altitude: Altitude in feet
            show_values: Whether to show values on display
            color_scale: List of color values for display
            data_points: List of individual data points
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        super().__init__(request_id, timestamp, metadata, DISPLAY_VIL_DATA)
        self.position = position or (0.0, 0.0)
        self.value = value or 0.0
        self.layer_count = layer_count or 0
        self.intensity = intensity or 0.0
        self.altitude = altitude or 0.0
        self.show_values = show_values
        self.color_scale = color_scale or []
        self.data_points = data_points or []
        
        # Add VIL-specific metadata
        self.add_metadata('data_type', 'vil')
        self.add_metadata('value_unit', 'kg/m²')
        
        # Log creation with VIL-specific details
        logger.debug(f"Created VIL data message with value={self.value} kg/m², position={self.position}")
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dict: Dictionary representation of the message
        """
        data = super().to_dict()
        data.update({
            'position': self.position,
            'value': self.value,
            'layer_count': self.layer_count,
            'intensity': self.intensity,
            'altitude': self.altitude,
            'show_values': self.show_values,
            'color_scale': self.color_scale,
            'data_points': self.data_points
        })
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayVILData':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            DisplayVILData: New message instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
            
        return cls(
            position=data.get('position'),
            value=data.get('value'),
            layer_count=data.get('layer_count'),
            intensity=data.get('intensity'),
            altitude=data.get('altitude'),
            show_values=data.get('show_values', True),
            color_scale=data.get('color_scale'),
            data_points=data.get('data_points'),
            request_id=data.get('request_id'),
            timestamp=data.get('timestamp'),
            metadata=data.get('metadata')
        )
        
    @classmethod
    def from_weather_radar_response(cls, response: Dict[str, Any]) -> 'DisplayVILData':
        """
        Create VIL data message from weather radar response.
        
        Args:
            response: Weather radar response data
            
        Returns:
            DisplayVILData: New message instance
            
        Raises:
            ValueError: If response is not a dictionary or is missing required fields
        """
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
            
        # Extract VIL data from response
        vil_data = response.get('data', {}).get('vil_data', {})
        if not vil_data:
            raise ValueError("Response missing VIL data")
            
        # Extract metadata
        metadata = response.get('metadata', {})
        if 'transaction_id' not in metadata:
            metadata['transaction_id'] = response.get('request_id', '')
            
        # Create VIL data message
        return cls(
            position=vil_data.get('position'),
            value=vil_data.get('value'),
            layer_count=vil_data.get('layer_count'),
            intensity=vil_data.get('intensity'),
            altitude=vil_data.get('altitude'),
            show_values=vil_data.get('show_values', True),
            color_scale=vil_data.get('color_scale'),
            data_points=vil_data.get('data_points'),
            request_id=response.get('request_id'),
            timestamp=response.get('timestamp'),
            metadata=metadata
        )
        
    def get_intensity_level(self) -> str:
        """
        Get intensity level description based on VIL value.
        
        Returns:
            str: Intensity level description
        """
        if self.value < 1.0:
            return "Low"
        elif self.value < 10.0:
            return "Moderate"
        elif self.value < 30.0:
            return "High"
        else:
            return "Extreme"
            
    def __str__(self) -> str:
        """
        Get string representation of the message.
        
        Returns:
            str: String representation
        """
        return f"DisplayVILData(request_id={self.request_id}, value={self.value} kg/m², intensity={self.get_intensity_level()})"
