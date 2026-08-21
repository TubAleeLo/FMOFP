"""
SAR Radar Message Definitions

Contains radar-local message classes for Synthetic Aperture Radar data.
"""

from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import RadarBaseMessage
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    SAR_RADAR_IMAGERY_REQUEST,
    SAR_RADAR_IMAGERY_RESPONSE
)

class SARRadarImagery(RadarBaseMessage):
    """Message class for SAR radar imagery data."""
    
    def __init__(self, image_uuid: str, image_data: Union[np.ndarray, List], 
                 resolution: float, geo_reference: Dict[str, float] = None, **kwargs):
        """
        Initialize SAR radar imagery message.
        
        Args:
            image_uuid: Unique identifier for this imagery message
            image_data: Numpy array or list containing image data
            resolution: Resolution of the image in meters per pixel
            geo_reference: Dictionary with geo-reference information (e.g., lat/lon bounds)
            **kwargs: Additional parameters passed to base class
        """
        # Ensure message types are properly set
        super().__init__(
            message_type=SAR_RADAR_IMAGERY_RESPONSE,
            command_type='imagery_data',
            command_name="SAR_RADAR_IMAGERY",
            **kwargs
        )
        self.image_uuid = image_uuid
        
        # Handle different image data types
        if isinstance(image_data, np.ndarray):
            self.image_data = image_data.tolist()  # Convert to list for serialization
            self.image_shape = image_data.shape
        else:
            self.image_data = image_data
            # Try to infer shape if possible
            if hasattr(image_data, 'shape'):
                self.image_shape = image_data.shape
            else:
                self.image_shape = (len(image_data), len(image_data[0]) if image_data and isinstance(image_data[0], (list, tuple)) else 1)
                
        self.resolution = resolution
        self.geo_reference = geo_reference or {}
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'image_uuid': self.image_uuid,
            'image_data': self.image_data,
            'image_shape': self.image_shape,
            'resolution': self.resolution,
            'geo_reference': self.geo_reference
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'SARRadarImagery':
        """Create message from dictionary representation."""
        return cls(
            image_uuid=data.get('image_uuid', ''),
            image_data=data.get('image_data', []),
            resolution=data.get('resolution', 1.0),
            geo_reference=data.get('geo_reference', {}),
            message_header=data.get('message_header', 'sar_imagery'),
            sending_system=data.get('sending_system', 'sar_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )
        
    def get_numpy_image(self) -> np.ndarray:
        """
        Convert image data back to numpy array using the stored shape information.
        
        Returns:
            np.ndarray: Image data as numpy array
        """
        if isinstance(self.image_data, np.ndarray):
            return self.image_data
            
        return np.array(self.image_data).reshape(self.image_shape)
