"""
Targeting Radar Maintenance Messages

Defines maintenance and diagnostic message types for targeting radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List

class targeting_radarMaintenance(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, maintenance_data: Dict, **kwargs):
        super().__init__(message_type="targeting_radarMaintenance", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.maintenance_data = maintenance_data

class targeting_radarDiagnosticRequest(BaseMessage):
    def __init__(self, request_uuid: str, diagnostic_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize diagnostic request message.
        
        Args:
            request_uuid: Unique identifier for this request
            diagnostic_type: Type of diagnostic test 
                           ("SELF_TEST", "CALIBRATION", "TRACK_QUALITY", "RF")
            parameters: Optional parameters for the diagnostic test
        """
        super().__init__(message_type="targeting_radarDiagnosticRequest", request_uuid=request_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.parameters = parameters or {}

class targeting_radarDiagnosticResponse(BaseMessage):
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
        super().__init__(message_type="targeting_radarDiagnosticResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.results = results
        self.status = status

class targeting_radarMaintenanceAlert(BaseMessage):
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
        super().__init__(message_type="targeting_radarMaintenanceAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.severity = severity
        self.components = components
        self.description = description

class targeting_radarCalibrationRequest(BaseMessage):
    def __init__(self, request_uuid: str, calibration_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize calibration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            calibration_type: Type of calibration 
                            ("RANGE", "ANGLE", "DOPPLER", "FULL")
            parameters: Optional calibration parameters
        """
        super().__init__(message_type="targeting_radarCalibrationRequest", request_uuid=request_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.parameters = parameters or {}

class targeting_radarCalibrationResponse(BaseMessage):
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
        super().__init__(message_type="targeting_radarCalibrationResponse", request_uuid=request_uuid,
                        response_uuid=response_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.results = results
        self.status = status

class targeting_radarPerformanceMetrics(BaseMessage):
    def __init__(self, metrics_uuid: str, metrics: Dict, timestamp: float, **kwargs):
        """
        Initialize performance metrics message.
        
        Args:
            metrics_uuid: Unique identifier for this metrics report
            metrics: Dictionary containing performance metrics
                - track_metrics: Track-related performance metrics
                - rf_metrics: RF system performance metrics
                - processing_metrics: Signal processing performance metrics
                - timing_metrics: Timing and synchronization metrics
            timestamp: Unix timestamp when metrics were collected
        """
        super().__init__(message_type="targeting_radarPerformanceMetrics", metrics_uuid=metrics_uuid, **kwargs)
        self.metrics = metrics
        self.timestamp = timestamp

class targeting_radarHealthStatus(BaseMessage):
    def __init__(self, status_uuid: str, subsystem_status: Dict, overall_health: str,
                 maintenance_required: bool, maintenance_items: List[Dict], **kwargs):
        """
        Initialize health status message.
        
        Args:
            status_uuid: Unique identifier for this status report
            subsystem_status: Status of each subsystem
            overall_health: Overall health status
            maintenance_required: Whether maintenance is required
            maintenance_items: List of maintenance items if required
        """
        super().__init__(message_type="targeting_radarHealthStatus", status_uuid=status_uuid, **kwargs)
        self.subsystem_status = subsystem_status
        self.overall_health = overall_health
        self.maintenance_required = maintenance_required
        self.maintenance_items = maintenance_items

# Register message types
register_message_type("targeting_radarMaintenance", targeting_radarMaintenance)
register_message_type("targeting_radarDiagnosticRequest", targeting_radarDiagnosticRequest)
register_message_type("targeting_radarDiagnosticResponse", targeting_radarDiagnosticResponse)
register_message_type("targeting_radarMaintenanceAlert", targeting_radarMaintenanceAlert)
register_message_type("targeting_radarCalibrationRequest", targeting_radarCalibrationRequest)
register_message_type("targeting_radarCalibrationResponse", targeting_radarCalibrationResponse)
register_message_type("targeting_radarPerformanceMetrics", targeting_radarPerformanceMetrics)
register_message_type("targeting_radarHealthStatus", targeting_radarHealthStatus)
