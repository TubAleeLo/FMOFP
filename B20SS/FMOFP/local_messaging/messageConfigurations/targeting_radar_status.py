"""
Targeting Radar Status Messages

Defines status message types for targeting radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List

class targeting_radarStatus(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, **kwargs):
        super().__init__(message_type="targeting_radarStatus", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type

class targeting_radarStatusRequest(BaseMessage):
    def __init__(self, query_uuid, dest_radar, radar_name, message_header, destination, sending_system, **kwargs):
        super().__init__(message_type="targeting_radarStatusRequest", query_uuid=query_uuid, message_header=message_header, 
                        destination=destination, sending_system=sending_system, **kwargs)
        self.dest_radar = dest_radar
        self.radar_name = radar_name

class targeting_radarStatusResponse(BaseMessage):
    def __init__(self, query_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="targeting_radarStatusResponse", query_uuid=query_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class targeting_radarDiagnostic(BaseMessage):
    def __init__(self, diagnostic_uuid, diagnostic_data, **kwargs):
        super().__init__(message_type="targeting_radarDiagnostic", diagnostic_uuid=diagnostic_uuid, **kwargs)
        self.diagnostic_data = diagnostic_data

class targeting_radarError(BaseMessage):
    def __init__(self, error_uuid, error_code, error_message, **kwargs):
        super().__init__(message_type="targeting_radarError", error_uuid=error_uuid, **kwargs)
        self.error_code = error_code
        self.error_message = error_message

class targeting_radarAlert(BaseMessage):
    def __init__(self, alert_uuid, alert_type, alert_message, **kwargs):
        super().__init__(message_type="targeting_radarAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.alert_message = alert_message

class targeting_radarTrackQuality(BaseMessage):
    def __init__(self, quality_uuid: str, track_id: int, quality_metrics: Dict, **kwargs):
        """
        Initialize track quality message.
        
        Args:
            quality_uuid: Unique identifier for this quality report
            track_id: ID of the track being assessed
            quality_metrics: Dictionary containing track quality metrics
                - snr: Signal-to-noise ratio
                - range_accuracy: Range measurement accuracy
                - angle_accuracy: Angular measurement accuracy
                - velocity_accuracy: Velocity measurement accuracy
                - track_stability: Track stability metric
        """
        super().__init__(message_type="targeting_radarTrackQuality", quality_uuid=quality_uuid, **kwargs)
        self.track_id = track_id
        self.quality_metrics = quality_metrics

class targeting_radarLockStatus(BaseMessage):
    def __init__(self, status_uuid: str, track_id: int, lock_quality: float,
                 jamming_indication: bool, track_confidence: float, **kwargs):
        """
        Initialize lock status message.
        
        Args:
            status_uuid: Unique identifier for this status
            track_id: ID of the locked track
            lock_quality: Quality of the lock (0.0 to 1.0)
            jamming_indication: Whether jamming is detected
            track_confidence: Confidence in track maintenance (0.0 to 1.0)
        """
        super().__init__(message_type="targeting_radarLockStatus", status_uuid=status_uuid, **kwargs)
        self.track_id = track_id
        self.lock_quality = lock_quality
        self.jamming_indication = jamming_indication
        self.track_confidence = track_confidence

class targeting_radarTrackFile(BaseMessage):
    def __init__(self, file_uuid: str, track_id: int, track_history: List[Dict],
                 track_classification: str, track_priority: int, **kwargs):
        """
        Initialize track file message.
        
        Args:
            file_uuid: Unique identifier for this track file
            track_id: ID of the track
            track_history: List of historical track points
            track_classification: Classification of the track
            track_priority: Priority level of the track
        """
        super().__init__(message_type="targeting_radarTrackFile", file_uuid=file_uuid, **kwargs)
        self.track_id = track_id
        self.track_history = track_history
        self.track_classification = track_classification
        self.track_priority = track_priority

# Register message types
register_message_type("targeting_radarStatus", targeting_radarStatus)
register_message_type("targeting_radarStatusRequest", targeting_radarStatusRequest)
register_message_type("targeting_radarStatusResponse", targeting_radarStatusResponse)
register_message_type("targeting_radarDiagnostic", targeting_radarDiagnostic)
register_message_type("targeting_radarError", targeting_radarError)
register_message_type("targeting_radarAlert", targeting_radarAlert)
register_message_type("targeting_radarTrackQuality", targeting_radarTrackQuality)
register_message_type("targeting_radarLockStatus", targeting_radarLockStatus)
register_message_type("targeting_radarTrackFile", targeting_radarTrackFile)
