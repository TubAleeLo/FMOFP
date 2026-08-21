"""
SAR Radar Command Messages

Defines command message types for SAR radar communication.
"""

from .base_message import BaseMessage, register_message_type

class sar_radarCommand(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, command, **kwargs):
        super().__init__(message_type="sar_radarCommand", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.command = command

class sar_radarModeChangeRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="sar_radarModeChangeRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class sar_radarModeChangeResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="sar_radarModeChangeResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class sar_radarImageryRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, scan_parameters: dict = None, **kwargs):
        """
        Initialize imagery request message.
        
        Args:
            command_uuid: Unique identifier for this request
            radar_name: Name of the SAR radar
            scan_parameters: Optional parameters for the scan (resolution, area, etc.)
        """
        super().__init__(message_type="sar_radarImageryRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.scan_parameters = scan_parameters or {}

class sar_radarImageryResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, image_data: bytes,
                 corner_points: list, resolution: float, **kwargs):
        """
        Initialize imagery response message.
        
        Args:
            command_uuid: UUID of the original request
            status_uuid: Unique identifier for this response
            radar_name: Name of the SAR radar
            image_data: Raw image data bytes
            corner_points: List of (lat, lon) tuples defining image corners
            resolution: Ground resolution in meters per pixel
        """
        super().__init__(message_type="sar_radarImageryResponse", command_uuid=command_uuid, 
                        status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.image_data = image_data
        self.corner_points = corner_points
        self.resolution = resolution

# Register message types
register_message_type("sar_radarCommand", sar_radarCommand)
register_message_type("sar_radarModeChangeRequest", sar_radarModeChangeRequest)
register_message_type("sar_radarModeChangeResponse", sar_radarModeChangeResponse)
register_message_type("sar_radarImageryRequest", sar_radarImageryRequest)
register_message_type("sar_radarImageryResponse", sar_radarImageryResponse)
