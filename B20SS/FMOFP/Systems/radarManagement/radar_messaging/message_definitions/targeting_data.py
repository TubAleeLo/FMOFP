"""
Targeting Radar Message Definitions

Contains radar-local message classes for Targeting Radar data.
"""

from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import RadarBaseMessage
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    TARGETING_RADAR_TRACK_REQUEST,
    TARGETING_RADAR_TRACK_RESPONSE,
    TARGETING_RADAR_LOCK_REQUEST,
    TARGETING_RADAR_LOCK_RESPONSE
)

class TargetingRadarTrackData(RadarBaseMessage):
    """Message class for targeting radar track data."""
    
    def __init__(self, track_uuid: str, target_position: Tuple[float, float, float],
                 target_velocity: Tuple[float, float, float], target_id: str = None,
                 confidence: float = 1.0, **kwargs):
        """
        Initialize targeting radar track data message.
        
        Args:
            track_uuid: Unique identifier for this track
            target_position: 3D position of the target (x, y, z) in meters
            target_velocity: 3D velocity of the target (vx, vy, vz) in m/s
            target_id: Optional target identifier
            confidence: Track confidence level (0.0-1.0)
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=TARGETING_RADAR_TRACK_RESPONSE,
            command_type='track_data',
            command_name="TARGETING_RADAR_TRACK",
            **kwargs
        )
        self.track_uuid = track_uuid
        self.target_position = target_position
        self.target_velocity = target_velocity
        self.target_id = target_id
        self.confidence = confidence
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'track_uuid': self.track_uuid,
            'target_position': self.target_position,
            'target_velocity': self.target_velocity,
            'target_id': self.target_id,
            'confidence': self.confidence
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'TargetingRadarTrackData':
        """Create message from dictionary representation."""
        return cls(
            track_uuid=data.get('track_uuid', ''),
            target_position=data.get('target_position', (0.0, 0.0, 0.0)),
            target_velocity=data.get('target_velocity', (0.0, 0.0, 0.0)),
            target_id=data.get('target_id'),
            confidence=data.get('confidence', 1.0),
            message_header=data.get('message_header', 'track_data'),
            sending_system=data.get('sending_system', 'targeting_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )

class TargetingRadarLockData(RadarBaseMessage):
    """Message class for targeting radar lock data."""
    
    def __init__(self, lock_uuid: str, target_position: Tuple[float, float, float],
                 lock_status: str, target_id: str = None, lock_time: float = None,
                 **kwargs):
        """
        Initialize targeting radar lock data message.
        
        Args:
            lock_uuid: Unique identifier for this lock
            target_position: 3D position of the locked target (x, y, z) in meters
            lock_status: Status of the lock ('ACQUIRING', 'LOCKED', 'LOST')
            target_id: Optional target identifier
            lock_time: Time when lock was acquired
            **kwargs: Additional parameters passed to base class
        """
        super().__init__(
            message_type=TARGETING_RADAR_LOCK_RESPONSE,
            command_type='lock_data',
            command_name="TARGETING_RADAR_LOCK",
            **kwargs
        )
        self.lock_uuid = lock_uuid
        self.target_position = target_position
        self.lock_status = lock_status
        self.target_id = target_id
        self.lock_time = lock_time or 0.0
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary representation."""
        base_dict = super().to_dict()
        message_dict = {
            'lock_uuid': self.lock_uuid,
            'target_position': self.target_position,
            'lock_status': self.lock_status,
            'target_id': self.target_id,
            'lock_time': self.lock_time
        }
        return {**base_dict, **message_dict}
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'TargetingRadarLockData':
        """Create message from dictionary representation."""
        return cls(
            lock_uuid=data.get('lock_uuid', ''),
            target_position=data.get('target_position', (0.0, 0.0, 0.0)),
            lock_status=data.get('lock_status', 'LOST'),
            target_id=data.get('target_id'),
            lock_time=data.get('lock_time'),
            message_header=data.get('message_header', 'lock_data'),
            sending_system=data.get('sending_system', 'targeting_radar'),
            destination=data.get('destination', 'radar_handler'),
            request_id=data.get('request_id', ''),
            response_uuid=data.get('response_uuid', '')
        )
