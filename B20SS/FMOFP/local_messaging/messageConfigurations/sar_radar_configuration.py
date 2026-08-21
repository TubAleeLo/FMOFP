"""
SAR Radar Configuration Messages

Defines configuration message types for SAR radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List, Tuple

class sar_radarConfiguration(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, config_data: Dict, **kwargs):
        super().__init__(message_type="sar_radarConfiguration", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.config_data = config_data

class sar_radarConfigRequest(BaseMessage):
    def __init__(self, request_uuid: str, config_type: str, **kwargs):
        """
        Initialize configuration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            config_type: Type of configuration requested 
                        ("STRIPMAP", "SPOTLIGHT", "SCANSAR", "PROCESSING")
        """
        super().__init__(message_type="sar_radarConfigRequest", request_uuid=request_uuid, **kwargs)
        self.config_type = config_type

class sar_radarConfigResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, config_type: str, config_data: Dict, **kwargs):
        """
        Initialize configuration response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            config_type: Type of configuration being returned
            config_data: Dictionary containing the configuration data
        """
        super().__init__(message_type="sar_radarConfigResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.config_type = config_type
        self.config_data = config_data

class sar_radarConfigUpdate(BaseMessage):
    def __init__(self, update_uuid: str, config_type: str, config_updates: Dict, **kwargs):
        """
        Initialize configuration update message.
        
        Args:
            update_uuid: Unique identifier for this update
            config_type: Type of configuration being updated
            config_updates: Dictionary containing the configuration updates
        """
        super().__init__(message_type="sar_radarConfigUpdate", update_uuid=update_uuid, **kwargs)
        self.config_type = config_type
        self.config_updates = config_updates

class sar_radarStripMapConfig(BaseMessage):
    def __init__(self, config_uuid: str, swath_width: float, resolution: float, 
                 pulse_repetition_freq: float, **kwargs):
        """
        Initialize StripMap mode configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            swath_width: Width of strip in meters
            resolution: Desired resolution in meters
            pulse_repetition_freq: PRF in Hz
        """
        super().__init__(message_type="sar_radarStripMapConfig", config_uuid=config_uuid, **kwargs)
        self.swath_width = swath_width
        self.resolution = resolution
        self.pulse_repetition_freq = pulse_repetition_freq

class sar_radarSpotlightConfig(BaseMessage):
    def __init__(self, config_uuid: str, spot_size: float, resolution: float,
                 integration_time: float, **kwargs):
        """
        Initialize Spotlight mode configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            spot_size: Size of spotlight area in meters
            resolution: Desired resolution in meters
            integration_time: Integration time in seconds
        """
        super().__init__(message_type="sar_radarSpotlightConfig", config_uuid=config_uuid, **kwargs)
        self.spot_size = spot_size
        self.resolution = resolution
        self.integration_time = integration_time

class sar_radarScanSARConfig(BaseMessage):
    def __init__(self, config_uuid: str, num_subswaths: int, swath_width: float,
                 burst_duration: float, **kwargs):
        """
        Initialize ScanSAR mode configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            num_subswaths: Number of subswaths
            swath_width: Width of each subswath in meters
            burst_duration: Duration of each burst in seconds
        """
        super().__init__(message_type="sar_radarScanSARConfig", config_uuid=config_uuid, **kwargs)
        self.num_subswaths = num_subswaths
        self.swath_width = swath_width
        self.burst_duration = burst_duration

class sar_radarConfigAcknowledgment(BaseMessage):
    def __init__(self, update_uuid: str, status: str, message: str = "", **kwargs):
        """
        Initialize configuration acknowledgment message.
        
        Args:
            update_uuid: UUID of the configuration update being acknowledged
            status: Status of the update ("SUCCESS", "FAILURE")
            message: Optional status message
        """
        super().__init__(message_type="sar_radarConfigAcknowledgment", update_uuid=update_uuid, **kwargs)
        self.status = status
        self.message = message

# Register message types
register_message_type("sar_radarConfiguration", sar_radarConfiguration)
register_message_type("sar_radarConfigRequest", sar_radarConfigRequest)
register_message_type("sar_radarConfigResponse", sar_radarConfigResponse)
register_message_type("sar_radarConfigUpdate", sar_radarConfigUpdate)
register_message_type("sar_radarStripMapConfig", sar_radarStripMapConfig)
register_message_type("sar_radarSpotlightConfig", sar_radarSpotlightConfig)
register_message_type("sar_radarScanSARConfig", sar_radarScanSARConfig)
register_message_type("sar_radarConfigAcknowledgment", sar_radarConfigAcknowledgment)
