"""
AEWC Radar Command Messages

Defines command message types for AEWC radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict

class aewc_radarCommand(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, command, **kwargs):
        super().__init__(message_type="aewc_radarCommand", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.command = command

class aewc_radarModeChangeRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="aewc_radarModeChangeRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class aewc_radarModeChangeResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="aewc_radarModeChangeResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class aewc_radarTrackRequest(BaseMessage):
    def __init__(self, command_uuid: str, radar_name: str, track_parameters: Dict = None, **kwargs):
        """
        Initialize track request message.
        
        Args:
            command_uuid: Unique identifier for this request
            radar_name: Name of the AEWC radar
            track_parameters: Optional parameters for tracking (volume, priority, etc.)
        """
        super().__init__(message_type="aewc_radarTrackRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_parameters = track_parameters or {}

class aewc_radarTrackResponse(BaseMessage):
    def __init__(self, command_uuid: str, status_uuid: str, radar_name: str, track_id: int,
                 position: tuple, velocity: tuple, classification: str, is_stealth: bool, **kwargs):
        """
        Initialize track response message.
        
        Args:
            command_uuid: UUID of the original request
            status_uuid: Unique identifier for this response
            radar_name: Name of the AEWC radar
            track_id: Unique identifier for the track
            position: (x, y, z) position in meters
            velocity: (vx, vy, vz) velocity in m/s
            classification: Target classification
            is_stealth: Whether target exhibits stealth characteristics
        """
        super().__init__(message_type="aewc_radarTrackResponse", command_uuid=command_uuid,
                        status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_id = track_id
        self.position = position
        self.velocity = velocity
        self.classification = classification
        self.is_stealth = is_stealth

class aewc_radarSectorScanRequest(BaseMessage):
    def __init__(self, command_uuid: str, radar_name: str, sector_parameters: Dict, **kwargs):
        """
        Initialize sector scan request message.
        
        Args:
            command_uuid: Unique identifier for this request
            radar_name: Name of the AEWC radar
            sector_parameters: Parameters defining the scan sector
                - azimuth_start: Start azimuth angle
                - azimuth_end: End azimuth angle
                - elevation_min: Minimum elevation angle
                - elevation_max: Maximum elevation angle
                - priority: Scan priority level
        """
        super().__init__(message_type="aewc_radarSectorScanRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.sector_parameters = sector_parameters

class aewc_radarSectorScanResponse(BaseMessage):
    def __init__(self, command_uuid: str, status_uuid: str, radar_name: str,
                 sector_data: Dict, scan_complete: bool, **kwargs):
        """
        Initialize sector scan response message.
        
        Args:
            command_uuid: UUID of the original request
            status_uuid: Unique identifier for this response
            radar_name: Name of the AEWC radar
            sector_data: Data from the sector scan
            scan_complete: Whether the sector scan is complete
        """
        super().__init__(message_type="aewc_radarSectorScanResponse", command_uuid=command_uuid,
                        status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.sector_data = sector_data
        self.scan_complete = scan_complete

# Register message types
register_message_type("aewc_radarCommand", aewc_radarCommand)
register_message_type("aewc_radarModeChangeRequest", aewc_radarModeChangeRequest)
register_message_type("aewc_radarModeChangeResponse", aewc_radarModeChangeResponse)
register_message_type("aewc_radarTrackRequest", aewc_radarTrackRequest)
register_message_type("aewc_radarTrackResponse", aewc_radarTrackResponse)
register_message_type("aewc_radarSectorScanRequest", aewc_radarSectorScanRequest)
register_message_type("aewc_radarSectorScanResponse", aewc_radarSectorScanResponse)
