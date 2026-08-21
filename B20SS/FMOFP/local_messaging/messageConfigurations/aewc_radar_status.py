"""
AEWC Radar Status Messages

Defines status message types for AEWC radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List

class aewc_radarStatus(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, **kwargs):
        super().__init__(message_type="aewc_radarStatus", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type

class aewc_radarStatusRequest(BaseMessage):
    def __init__(self, query_uuid, dest_radar, radar_name, message_header, destination, sending_system, **kwargs):
        super().__init__(message_type="aewc_radarStatusRequest", query_uuid=query_uuid, message_header=message_header, 
                        destination=destination, sending_system=sending_system, **kwargs)
        self.dest_radar = dest_radar
        self.radar_name = radar_name

class aewc_radarStatusResponse(BaseMessage):
    def __init__(self, query_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="aewc_radarStatusResponse", query_uuid=query_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class aewc_radarDiagnostic(BaseMessage):
    def __init__(self, diagnostic_uuid, diagnostic_data, **kwargs):
        super().__init__(message_type="aewc_radarDiagnostic", diagnostic_uuid=diagnostic_uuid, **kwargs)
        self.diagnostic_data = diagnostic_data

class aewc_radarError(BaseMessage):
    def __init__(self, error_uuid, error_code, error_message, **kwargs):
        super().__init__(message_type="aewc_radarError", error_uuid=error_uuid, **kwargs)
        self.error_code = error_code
        self.error_message = error_message

class aewc_radarAlert(BaseMessage):
    def __init__(self, alert_uuid, alert_type, alert_message, **kwargs):
        super().__init__(message_type="aewc_radarAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.alert_message = alert_message

class aewc_radarTrackQuality(BaseMessage):
    def __init__(self, quality_uuid: str, track_id: int, quality_metrics: Dict, **kwargs):
        """
        Initialize track quality message.
        
        Args:
            quality_uuid: Unique identifier for this quality report
            track_id: ID of the track being assessed
            quality_metrics: Dictionary containing track quality metrics
                - snr: Signal-to-noise ratio
                - stealth_confidence: Confidence in stealth classification
                - track_stability: Track stability metric
                - range_accuracy: Range measurement accuracy
                - altitude_accuracy: Altitude measurement accuracy
        """
        super().__init__(message_type="aewc_radarTrackQuality", quality_uuid=quality_uuid, **kwargs)
        self.track_id = track_id
        self.quality_metrics = quality_metrics

class aewc_radarSectorStatus(BaseMessage):
    def __init__(self, status_uuid: str, sector_id: str, coverage_metrics: Dict,
                 scan_progress: float, active_tracks: List[int], **kwargs):
        """
        Initialize sector status message.
        
        Args:
            status_uuid: Unique identifier for this status
            sector_id: Identifier for the sector being monitored
            coverage_metrics: Metrics about sector coverage
            scan_progress: Progress of current scan (0.0 to 1.0)
            active_tracks: List of track IDs in this sector
        """
        super().__init__(message_type="aewc_radarSectorStatus", status_uuid=status_uuid, **kwargs)
        self.sector_id = sector_id
        self.coverage_metrics = coverage_metrics
        self.scan_progress = scan_progress
        self.active_tracks = active_tracks

class aewc_radarTrackFile(BaseMessage):
    def __init__(self, file_uuid: str, track_id: int, track_history: List[Dict],
                 track_classification: str, stealth_history: List[bool], **kwargs):
        """
        Initialize track file message.
        
        Args:
            file_uuid: Unique identifier for this track file
            track_id: ID of the track
            track_history: List of historical track points
            track_classification: Classification of the track
            stealth_history: History of stealth detections
        """
        super().__init__(message_type="aewc_radarTrackFile", file_uuid=file_uuid, **kwargs)
        self.track_id = track_id
        self.track_history = track_history
        self.track_classification = track_classification
        self.stealth_history = stealth_history

class aewc_radarCoverageMap(BaseMessage):
    def __init__(self, map_uuid: str, coverage_data: Dict, timestamp: float,
                 blind_zones: List[Dict], interference_zones: List[Dict], **kwargs):
        """
        Initialize coverage map message.
        
        Args:
            map_uuid: Unique identifier for this coverage map
            coverage_data: Radar coverage data
            timestamp: Unix timestamp of the map
            blind_zones: List of areas with no coverage
            interference_zones: List of areas with interference
        """
        super().__init__(message_type="aewc_radarCoverageMap", map_uuid=map_uuid, **kwargs)
        self.coverage_data = coverage_data
        self.timestamp = timestamp
        self.blind_zones = blind_zones
        self.interference_zones = interference_zones

# Register message types
register_message_type("aewc_radarStatus", aewc_radarStatus)
register_message_type("aewc_radarStatusRequest", aewc_radarStatusRequest)
register_message_type("aewc_radarStatusResponse", aewc_radarStatusResponse)
register_message_type("aewc_radarDiagnostic", aewc_radarDiagnostic)
register_message_type("aewc_radarError", aewc_radarError)
register_message_type("aewc_radarAlert", aewc_radarAlert)
register_message_type("aewc_radarTrackQuality", aewc_radarTrackQuality)
register_message_type("aewc_radarSectorStatus", aewc_radarSectorStatus)
register_message_type("aewc_radarTrackFile", aewc_radarTrackFile)
register_message_type("aewc_radarCoverageMap", aewc_radarCoverageMap)
