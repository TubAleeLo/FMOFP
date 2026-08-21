"""
TFR Radar Status Messages

Defines status message types for TFR radar communication.
"""

from .base_message import BaseMessage, register_message_type

class tfr_radarStatus(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, **kwargs):
        super().__init__(message_type="tfr_radarStatus", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type

class tfr_radarStatusRequest(BaseMessage):
    def __init__(self, query_uuid, dest_radar, radar_name, message_header, destination, sending_system, **kwargs):
        super().__init__(message_type="tfr_radarStatusRequest", query_uuid=query_uuid, message_header=message_header, 
                        destination=destination, sending_system=sending_system, **kwargs)
        self.dest_radar = dest_radar
        self.radar_name = radar_name

class tfr_radarStatusResponse(BaseMessage):
    def __init__(self, query_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="tfr_radarStatusResponse", query_uuid=query_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class tfr_radarDiagnostic(BaseMessage):
    def __init__(self, diagnostic_uuid, diagnostic_data, **kwargs):
        super().__init__(message_type="tfr_radarDiagnostic", diagnostic_uuid=diagnostic_uuid, **kwargs)
        self.diagnostic_data = diagnostic_data

class tfr_radarError(BaseMessage):
    def __init__(self, error_uuid, error_code, error_message, **kwargs):
        super().__init__(message_type="tfr_radarError", error_uuid=error_uuid, **kwargs)
        self.error_code = error_code
        self.error_message = error_message

class tfr_radarAlert(BaseMessage):
    def __init__(self, alert_uuid, alert_type, alert_message, **kwargs):
        super().__init__(message_type="tfr_radarAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.alert_message = alert_message

# Register message types
register_message_type("tfr_radarStatus", tfr_radarStatus)
register_message_type("tfr_radarStatusRequest", tfr_radarStatusRequest)
register_message_type("tfr_radarStatusResponse", tfr_radarStatusResponse)
register_message_type("tfr_radarDiagnostic", tfr_radarDiagnostic)
register_message_type("tfr_radarError", tfr_radarError)
register_message_type("tfr_radarAlert", tfr_radarAlert)
