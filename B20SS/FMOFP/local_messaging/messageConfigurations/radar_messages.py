from .base_message import BaseMessage, register_message_type

class RadarSystemStatusRequest(BaseMessage):
    def __init__(self, query_uuid, dest_radar, radar_name, message_header, destination, sending_system, **kwargs):
        super().__init__(message_type="RadarSystemStatusRequest", query_uuid=query_uuid, message_header=message_header, destination=destination, sending_system=sending_system, **kwargs)
        self.dest_radar = dest_radar
        self.radar_name = radar_name

class RadarSystemStatusResponse(BaseMessage):
    def __init__(self, query_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="RadarSystemStatusResponse", query_uuid=query_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class RadarModeChangeRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="RadarModeChangeRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class RadarModeChangeResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="RadarModeChangeResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class RadarTargetDataMessage(BaseMessage):
    def __init__(self, targets, **kwargs):
        super().__init__(message_type="RadarTargetDataMessage", **kwargs)
        self.targets = targets

class RadarCommandAcknowledgment(BaseMessage):
    def __init__(self, command_uuid, status_uuid, status, **kwargs):
        super().__init__(message_type="RadarCommandAcknowledgment", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.status = status

class RadarStatusMessage(BaseMessage):
    def __init__(self, status_uuid, status, **kwargs):
        super().__init__(message_type="RadarStatusMessage", status_uuid=status_uuid, **kwargs)
        self.status = status

# Register the message types
register_message_type("RadarSystemStatusRequest", RadarSystemStatusRequest)
register_message_type("RadarSystemStatusResponse", RadarSystemStatusResponse)
register_message_type("RadarModeChangeRequest", RadarModeChangeRequest)
register_message_type("RadarModeChangeResponse", RadarModeChangeResponse)
register_message_type("RadarTargetDataMessage", RadarTargetDataMessage)
register_message_type("RadarCommandAcknowledgment", RadarCommandAcknowledgment)
register_message_type("RadarStatusMessage", RadarStatusMessage)
