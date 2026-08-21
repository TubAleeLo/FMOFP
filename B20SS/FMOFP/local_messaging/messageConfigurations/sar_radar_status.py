"""
SAR Radar Status Messages

Defines status message types for SAR radar communication.
"""

from .base_message import BaseMessage, register_message_type

class sar_radarStatus(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, **kwargs):
        super().__init__(message_type="sar_radarStatus", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type

class sar_radarStatusRequest(BaseMessage):
    def __init__(self, query_uuid, dest_radar, radar_name, message_header, destination, sending_system, **kwargs):
        super().__init__(message_type="sar_radarStatusRequest", query_uuid=query_uuid, message_header=message_header, 
                        destination=destination, sending_system=sending_system, **kwargs)
        self.dest_radar = dest_radar
        self.radar_name = radar_name

class sar_radarStatusResponse(BaseMessage):
    def __init__(self, query_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="sar_radarStatusResponse", query_uuid=query_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class sar_radarDiagnostic(BaseMessage):
    def __init__(self, diagnostic_uuid, diagnostic_data, **kwargs):
        super().__init__(message_type="sar_radarDiagnostic", diagnostic_uuid=diagnostic_uuid, **kwargs)
        self.diagnostic_data = diagnostic_data

class sar_radarError(BaseMessage):
    def __init__(self, error_uuid, error_code, error_message, **kwargs):
        super().__init__(message_type="sar_radarError", error_uuid=error_uuid, **kwargs)
        self.error_code = error_code
        self.error_message = error_message

class sar_radarAlert(BaseMessage):
    def __init__(self, alert_uuid, alert_type, alert_message, **kwargs):
        super().__init__(message_type="sar_radarAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.alert_message = alert_message

class sar_radarImageQuality(BaseMessage):
    def __init__(self, quality_uuid: str, quality_metrics: dict, **kwargs):
        """
        Initialize image quality message.
        
        Args:
            quality_uuid: Unique identifier for this quality report
            quality_metrics: Dictionary containing image quality metrics
                - resolution: Ground resolution achieved
                - contrast: Image contrast ratio
                - snr: Signal-to-noise ratio
                - focus_quality: Focus quality metric
        """
        super().__init__(message_type="sar_radarImageQuality", quality_uuid=quality_uuid, **kwargs)
        self.quality_metrics = quality_metrics

class sar_radarProcessingStatus(BaseMessage):
    def __init__(self, status_uuid: str, processing_stage: str, completion_percentage: float, 
                 estimated_time_remaining: float, **kwargs):
        """
        Initialize processing status message.
        
        Args:
            status_uuid: Unique identifier for this status
            processing_stage: Current processing stage
            completion_percentage: Percentage complete (0-100)
            estimated_time_remaining: Estimated seconds remaining
        """
        super().__init__(message_type="sar_radarProcessingStatus", status_uuid=status_uuid, **kwargs)
        self.processing_stage = processing_stage
        self.completion_percentage = completion_percentage
        self.estimated_time_remaining = estimated_time_remaining

# Register message types
register_message_type("sar_radarStatus", sar_radarStatus)
register_message_type("sar_radarStatusRequest", sar_radarStatusRequest)
register_message_type("sar_radarStatusResponse", sar_radarStatusResponse)
register_message_type("sar_radarDiagnostic", sar_radarDiagnostic)
register_message_type("sar_radarError", sar_radarError)
register_message_type("sar_radarAlert", sar_radarAlert)
register_message_type("sar_radarImageQuality", sar_radarImageQuality)
register_message_type("sar_radarProcessingStatus", sar_radarProcessingStatus)
