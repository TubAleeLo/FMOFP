"""
AEWC Radar Message Definitions

Contains radar-local message classes for Airborne Early Warning and Control Radar data.
"""

from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import RadarBaseMessage
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    AEWC_RADAR_TRACK_REQUEST,
    AEWC_RADAR_TRACK_RESPONSE,
    AEWC_RADAR_SECTOR_SCAN_REQUEST,
    AEWC_RADAR_SECTOR_SCAN_RESPONSE
)

class AEWCRadarTrackData(RadarBaseMessage):
    """Message class for AEWC radar track data."""
    
    def __init__(self, track_uuid: str, track_positions: List[Tuple[float, float, float]],
                 track_velocities: List[Tuple[float, float, float]], track_timestamps: List[float],
                 track_id: str = None, track_type: str = 'UNKNOWN', track_confidence: float = 1.0,
                 **kwargs):
        """
        Initialize AEWC radar track data message.
        
        Args:
            track_uuid: Unique identifier for this track
            track_positions: List of 3D positions (x, y, z) in meters
            track_velocities: List of 3D velocities (vx, vy, vz) in m/s
            track_timestamps: List of timestamps for each position
            track_id: Optional track identifier (e.g., IFF, squawk code)
            track_type: Track classification (e.g., 'FRIENDLY', 'HOSTILE', 'UNKNOWN')
            track_confidence: Track confidence level (0.0-1.0)
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=AEWC_RADAR_TRACK_RESPONSE,
            command_type='track_data',
            command_name="AEWC_RADAR_TRACK",
            **kwargs
        )
        self.track_uuid = track_uuid
        self.track_positions = track_positions
        self.track_velocities = track_velocities
        self.track_timestamps = track_timestamps
        self.track_id = track_id
        self.track_type = track_type
        self.track_confidence = track_confidence
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'track_uuid': self.track_uuid,
            'track_positions': self.track_positions,
            'track_velocities': self.track_velocities,
            'track_timestamps': self.track_timestamps,
            'track_id': self.track_id,
            'track_type': self.track_type,
            'track_confidence': self.track_confidence
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'AEWCRadarTrackData':
        """Create message from dictionary representation."""
        return cls(
            track_uuid=data.get('track_uuid', ''),
            track_positions=data.get('track_positions', []),
            track_velocities=data.get('track_velocities', []),
            track_timestamps=data.get('track_timestamps', []),
            track_id=data.get('track_id'),
            track_type=data.get('track_type', 'UNKNOWN'),
            track_confidence=data.get('track_confidence', 1.0),
            message_header=data.get('message_header', 'track_data'),
            sending_system=data.get('sending_system', 'aewc_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )

class AEWCRadarSectorScan(RadarBaseMessage):
    """Message class for AEWC radar sector scan data."""
    
    def __init__(self, scan_uuid: str, sector_data: Union[np.ndarray, List], 
                 sector_bounds: Dict[str, float], scan_resolution: float,
                 scan_timestamp: float = None, **kwargs):
        """
        Initialize AEWC radar sector scan data message.
        
        Args:
            scan_uuid: Unique identifier for this sector scan
            sector_data: 2D array or list of sector scan data
            sector_bounds: Dictionary with sector boundaries (e.g., 'azimuth_start', 'azimuth_end')
            scan_resolution: Angular resolution of the scan in degrees
            scan_timestamp: Timestamp when the scan was performed
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=AEWC_RADAR_SECTOR_SCAN_RESPONSE,
            command_type='sector_scan_data',
            command_name="AEWC_RADAR_SECTOR_SCAN",
            **kwargs
        )
        self.scan_uuid = scan_uuid
        
        # Handle different data types
        if isinstance(sector_data, np.ndarray):
            self.sector_data = sector_data.tolist()  # Convert to list for serialization
            self.data_shape = sector_data.shape
        else:
            self.sector_data = sector_data
            # Try to infer shape if possible
            if hasattr(sector_data, 'shape'):
                self.data_shape = sector_data.shape
            else:
                self.data_shape = (len(sector_data), len(sector_data[0]) if sector_data and isinstance(sector_data[0], (list, tuple)) else 1)
                
        self.sector_bounds = sector_bounds
        self.scan_resolution = scan_resolution
        self.scan_timestamp = scan_timestamp or 0.0
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'scan_uuid': self.scan_uuid,
            'sector_data': self.sector_data,
            'data_shape': self.data_shape,
            'sector_bounds': self.sector_bounds,
            'scan_resolution': self.scan_resolution,
            'scan_timestamp': self.scan_timestamp
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'AEWCRadarSectorScan':
        """Create message from dictionary representation."""
        return cls(
            scan_uuid=data.get('scan_uuid', ''),
            sector_data=data.get('sector_data', []),
            sector_bounds=data.get('sector_bounds', {}),
            scan_resolution=data.get('scan_resolution', 1.0),
            scan_timestamp=data.get('scan_timestamp'),
            message_header=data.get('message_header', 'sector_scan'),
            sending_system=data.get('sending_system', 'aewc_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )
        
    def get_numpy_data(self) -> np.ndarray:
        """
        Convert sector data back to numpy array using the stored shape information.
        
        Returns:
            np.ndarray: Sector data as numpy array
        """
        if isinstance(self.sector_data, np.ndarray):
            return self.sector_data
            
        return np.array(self.sector_data).reshape(self.data_shape)
