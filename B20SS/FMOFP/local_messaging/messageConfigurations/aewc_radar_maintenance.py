"""
AEWC Radar Maintenance Messages

Defines maintenance and diagnostic message types for AEWC radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List

class aewc_radarMaintenance(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, maintenance_data: Dict, **kwargs):
        super().__init__(message_type="aewc_radarMaintenance", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.maintenance_data = maintenance_data

class aewc_radarDiagnosticRequest(BaseMessage):
    def __init__(self, request_uuid: str, diagnostic_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize diagnostic request message.
        
        Args:
            request_uuid: Unique identifier for this request
            diagnostic_type: Type of diagnostic test 
                           ("SELF_TEST", "CALIBRATION", "COVERAGE", "PROCESSING")
            parameters: Optional parameters for the diagnostic test
        """
        super().__init__(message_type="aewc_radarDiagnosticRequest", request_uuid=request_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.parameters = parameters or {}

class aewc_radarDiagnosticResponse(BaseMessage):
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
        super().__init__(message_type="aewc_radarDiagnosticResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.diagnostic_type = diagnostic_type
        self.results = results
        self.status = status

class aewc_radarMaintenanceAlert(BaseMessage):
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
        super().__init__(message_type="aewc_radarMaintenanceAlert", alert_uuid=alert_uuid, **kwargs)
        self.alert_type = alert_type
        self.severity = severity
        self.components = components
        self.description = description

class aewc_radarCalibrationRequest(BaseMessage):
    def __init__(self, request_uuid: str, calibration_type: str, parameters: Dict = None, **kwargs):
        """
        Initialize calibration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            calibration_type: Type of calibration 
                            ("ARRAY", "RECEIVER", "PROCESSOR", "FULL")
            parameters: Optional calibration parameters
        """
        super().__init__(message_type="aewc_radarCalibrationRequest", request_uuid=request_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.parameters = parameters or {}

class aewc_radarCalibrationResponse(BaseMessage):
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
        super().__init__(message_type="aewc_radarCalibrationResponse", request_uuid=request_uuid,
                        response_uuid=response_uuid, **kwargs)
        self.calibration_type = calibration_type
        self.results = results
        self.status = status

class aewc_radarPerformanceMetrics(BaseMessage):
    def __init__(self, metrics_uuid: str, metrics: Dict, timestamp: float, **kwargs):
        """
        Initialize performance metrics message.
        
        Args:
            metrics_uuid: Unique identifier for this metrics report
            metrics: Dictionary containing performance metrics
                - coverage_metrics: Coverage performance metrics
                - tracking_metrics: Track management metrics
                - processing_metrics: Signal processing metrics
                - system_metrics: System health metrics
            timestamp: Unix timestamp when metrics were collected
        """
        super().__init__(message_type="aewc_radarPerformanceMetrics", metrics_uuid=metrics_uuid, **kwargs)
        self.metrics = metrics
        self.timestamp = timestamp

class aewc_radarCoverageTest(BaseMessage):
    def __init__(self, test_uuid: str, test_type: str, coverage_results: Dict,
                 blind_zones: List[Dict], test_timestamp: float, **kwargs):
        """
        Initialize coverage test message.
        
        Args:
            test_uuid: Unique identifier for this test
            test_type: Type of coverage test performed
            coverage_results: Results of coverage analysis
            blind_zones: Detected blind zones or coverage gaps
            test_timestamp: Unix timestamp of the test
        """
        super().__init__(message_type="aewc_radarCoverageTest", test_uuid=test_uuid, **kwargs)
        self.test_type = test_type
        self.coverage_results = coverage_results
        self.blind_zones = blind_zones
        self.test_timestamp = test_timestamp

class aewc_radarHealthStatus(BaseMessage):
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
        super().__init__(message_type="aewc_radarHealthStatus", status_uuid=status_uuid, **kwargs)
        self.subsystem_status = subsystem_status
        self.overall_health = overall_health
        self.maintenance_required = maintenance_required
        self.maintenance_items = maintenance_items

# Register message types
register_message_type("aewc_radarMaintenance", aewc_radarMaintenance)
register_message_type("aewc_radarDiagnosticRequest", aewc_radarDiagnosticRequest)
register_message_type("aewc_radarDiagnosticResponse", aewc_radarDiagnosticResponse)
register_message_type("aewc_radarMaintenanceAlert", aewc_radarMaintenanceAlert)
register_message_type("aewc_radarCalibrationRequest", aewc_radarCalibrationRequest)
register_message_type("aewc_radarCalibrationResponse", aewc_radarCalibrationResponse)
register_message_type("aewc_radarPerformanceMetrics", aewc_radarPerformanceMetrics)
register_message_type("aewc_radarCoverageTest", aewc_radarCoverageTest)
register_message_type("aewc_radarHealthStatus", aewc_radarHealthStatus)
