"""
TFR Radar Message Definitions

Contains radar-local message classes for Terrain Following Radar data.
"""

from typing import Dict, List, Tuple, Any, Optional
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import RadarBaseMessage
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    TFR_RADAR_ELEVATION_PROFILE,
    TFR_RADAR_TERRAIN_WARNING,
    COMMAND_TYPE_ELEVATION_DATA,
    COMMAND_TYPE_TERRAIN_WARNING
)

class TFRRadarElevationProfile(RadarBaseMessage):
    """Message class for TFR radar elevation profile data."""
    
    def __init__(self, data_uuid: str, profile_data: List[Tuple[float, float]], 
                 scan_width: float, **kwargs):
        """
        Initialize TFR radar elevation profile message.
        
        Args:
            data_uuid: Unique identifier for this data message
            profile_data: List of (distance, elevation) tuples
            scan_width: Width of the scan in meters
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=TFR_RADAR_ELEVATION_PROFILE,
            command_type=COMMAND_TYPE_ELEVATION_DATA,
            command_name="TFR_RADAR_ELEVATION_PROFILE",
            **kwargs
        )
        self.data_uuid = data_uuid
        self.profile_data = profile_data
        self.scan_width = scan_width
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'data_uuid': self.data_uuid,
            'profile_data': self.profile_data,
            'scan_width': self.scan_width
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'TFRRadarElevationProfile':
        """Create message from dictionary representation."""
        return cls(
            data_uuid=data.get('data_uuid', ''),
            profile_data=data.get('profile_data', []),
            scan_width=data.get('scan_width', 0.0),
            message_header=data.get('message_header', 'elevation_profile'),
            sending_system=data.get('sending_system', 'tfr_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )

class TFRRadarTerrainWarning(RadarBaseMessage):
    """Message class for TFR radar terrain warnings."""
    
    def __init__(self, warning_uuid: str, warning_type: str, 
                 distance: float, elevation: float, **kwargs):
        """
        Initialize TFR radar terrain warning message.
        
        Args:
            warning_uuid: Unique identifier for this warning message
            warning_type: Type of terrain warning (e.g., 'HIGH_TERRAIN', 'STEEP_TERRAIN')
            distance: Distance to the terrain feature in meters
            elevation: Elevation of the terrain feature in meters
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=TFR_RADAR_TERRAIN_WARNING,
            command_type=COMMAND_TYPE_TERRAIN_WARNING,
            command_name="TFR_RADAR_TERRAIN_WARNING",
            **kwargs
        )
        self.warning_uuid = warning_uuid
        self.warning_type = warning_type
        self.distance = distance
        self.elevation = elevation
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'warning_uuid': self.warning_uuid,
            'warning_type': self.warning_type,
            'distance': self.distance,
            'elevation': self.elevation
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'TFRRadarTerrainWarning':
        """Create message from dictionary representation."""
        return cls(
            warning_uuid=data.get('warning_uuid', ''),
            warning_type=data.get('warning_type', ''),
            distance=data.get('distance', 0.0),
            elevation=data.get('elevation', 0.0),
            message_header=data.get('message_header', 'terrain_warning'),
            sending_system=data.get('sending_system', 'tfr_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )
