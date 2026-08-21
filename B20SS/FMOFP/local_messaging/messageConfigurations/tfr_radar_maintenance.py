"""
TFR Radar Maintenance Messages

Defines maintenance and diagnostic message types for TFR radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List

class tfr_radarMaintenance(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, maintenance_data: Dict, **kwargs):
        super().__init__(message_type="tfr_radarMaintenance", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.maintenance_data = maintenance_data

class tfr_radarDiagnosticRequest(BaseMessage):
    def __init__(self, request_uuid: str, diagnostic_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize diagnostic request message.
        
        Args:
            request_uuid: Unique identifier for this request
            diagnostic_type: Type of diagnostic test ("SELF_TEST", "CALIBRATION", "PERFORMANCE")
            parameters: Optional parameters for the diagnostic test
        """
        super().__init__(message_type="tfr_radarDiagnosticRequest", request_uuid=request_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.parameters = parameters or {}

class tfr_radarDiagnosticResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, diagnostic_type: str, 
                 results: Dict, status: str, **kwargs):
        """
        Initialize diagnostic response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            diagnostic_type: Type of diagnostic test performed
            results: Dictionary containing test results
            status: Overall status of the diagnostic ("PASS", "FAIL", "WARNING")
        """
        super().__init__(message_type="tfr_radarDiagnosticResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.results = results
        self.status = status

class tfr_radarMaintenanceAlert(BaseMessage):
    def __init__(self, alert_uuid: str, alert_type: str, severity: str, 
                 components: List[str], description: str, **kwargs):
        """
        Initialize maintenance alert message.
        
        Args:
            alert_uuid: Unique identifier for this alert
            alert_type: Type of maintenance alert
            severity: Alert severity ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            components: List of affected components
            description: Detailed description of the maintenance issue
        """
        super().__init__(message_type="tfr_radarMaintenanceAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.severity = severity
        self.components = components
        self.description = description

class tfr_radarCalibrationRequest(BaseMessage):
    def __init__(self, request_uuid: str, calibration_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize calibration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            calibration_type: Type of calibration ("ELEVATION", "RANGE", "FULL")
            parameters: Optional calibration parameters
        """
        super().__init__(message_type="tfr_radarCalibrationRequest", request_uuid=request_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.parameters = parameters or {}

class tfr_radarCalibrationResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, calibration_type: str,
                 results: Dict, status: str, **kwargs):
        """
        Initialize calibration response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            calibration_type: Type of calibration performed
            results: Dictionary containing calibration results
            status: Status of the calibration ("SUCCESS", "FAILURE", "PARTIAL")
        """
        super().__init__(message_type="tfr_radarCalibrationResponse", request_uuid=request_uuid,
                        response_uuid=response_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.results = results
        self.status = status

# Register message types
register_message_type("tfr_radarMaintenance", tfr_radarMaintenance)
register_message_type("tfr_radarDiagnosticRequest", tfr_radarDiagnosticRequest)
register_message_type("tfr_radarDiagnosticResponse", tfr_radarDiagnosticResponse)
register_message_type("tfr_radarMaintenanceAlert", tfr_radarMaintenanceAlert)
register_message_type("tfr_radarCalibrationRequest", tfr_radarCalibrationRequest)
register_message_type("tfr_radarCalibrationResponse", tfr_radarCalibrationResponse)
