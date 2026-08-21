"""
TFR Radar Command Messages

Defines command message types for TFR radar communication.
"""

from .base_message import BaseMessage, register_message_type

class tfr_radarCommand(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, command, **kwargs):
        super().__init__(message_type="tfr_radarCommand", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.command = command

class tfr_radarModeChangeRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="tfr_radarModeChangeRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class tfr_radarModeChangeResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="tfr_radarModeChangeResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class tfr_radarElevationDataRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, **kwargs):
        super().__init__(message_type="tfr_radarElevationDataRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name

class tfr_radarElevationDataResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, elevation_data, **kwargs):
        super().__init__(message_type="tfr_radarElevationDataResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.elevation_data = elevation_data

# Register message types
register_message_type("tfr_radarCommand", tfr_radarCommand)
register_message_type("tfr_radarModeChangeRequest", tfr_radarModeChangeRequest)
register_message_type("tfr_radarModeChangeResponse", tfr_radarModeChangeResponse)
register_message_type("tfr_radarElevationDataRequest", tfr_radarElevationDataRequest)
register_message_type("tfr_radarElevationDataResponse", tfr_radarElevationDataResponse)
