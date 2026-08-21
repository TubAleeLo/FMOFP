"""
Targeting Radar Command Messages

Defines command message types for targeting radar communication.
"""

from .base_message import BaseMessage, register_message_type

class targeting_radarCommand(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, command, **kwargs):
        super().__init__(message_type="targeting_radarCommand", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.command = command

class targeting_radarModeChangeRequest(BaseMessage):
    def __init__(self, command_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="targeting_radarModeChangeRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class targeting_radarModeChangeResponse(BaseMessage):
    def __init__(self, command_uuid, status_uuid, radar_name, mode, **kwargs):
        super().__init__(message_type="targeting_radarModeChangeResponse", command_uuid=command_uuid, status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.mode = mode

class targeting_radarTrackRequest(BaseMessage):
    def __init__(self, command_uuid: str, radar_name: str, track_parameters: dict = None, **kwargs):
        """
        Initialize track request message.
        
        Args:
            command_uuid: Unique identifier for this request
            radar_name: Name of the targeting radar
            track_parameters: Optional parameters for tracking (search volume, priority, etc.)
        """
        super().__init__(message_type="targeting_radarTrackRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_parameters = track_parameters or {}

class targeting_radarTrackResponse(BaseMessage):
    def __init__(self, command_uuid: str, status_uuid: str, radar_name: str, track_id: int,
                 position: tuple, velocity: tuple, classification: str, **kwargs):
        """
        Initialize track response message.
        
        Args:
            command_uuid: UUID of the original request
            status_uuid: Unique identifier for this response
            radar_name: Name of the targeting radar
            track_id: Unique identifier for the track
            position: (x, y, z) position in meters
            velocity: (vx, vy, vz) velocity in m/s
            classification: Target classification
        """
        super().__init__(message_type="targeting_radarTrackResponse", command_uuid=command_uuid,
                        status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_id = track_id
        self.position = position
        self.velocity = velocity
        self.classification = classification

class targeting_radarLockRequest(BaseMessage):
    def __init__(self, command_uuid: str, radar_name: str, track_id: int, **kwargs):
        """
        Initialize lock request message.
        
        Args:
            command_uuid: Unique identifier for this request
            radar_name: Name of the targeting radar
            track_id: ID of track to lock onto
        """
        super().__init__(message_type="targeting_radarLockRequest", command_uuid=command_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_id = track_id

class targeting_radarLockResponse(BaseMessage):
    def __init__(self, command_uuid: str, status_uuid: str, radar_name: str, track_id: int,
                 lock_status: str, **kwargs):
        """
        Initialize lock response message.
        
        Args:
            command_uuid: UUID of the original request
            status_uuid: Unique identifier for this response
            radar_name: Name of the targeting radar
            track_id: ID of locked track
            lock_status: Status of lock attempt ("ACQUIRED", "FAILED", "LOST")
        """
        super().__init__(message_type="targeting_radarLockResponse", command_uuid=command_uuid,
                        status_uuid=status_uuid, **kwargs)
        self.radar_name = radar_name
        self.track_id = track_id
        self.lock_status = lock_status

# Register message types
register_message_type("targeting_radarCommand", targeting_radarCommand)
register_message_type("targeting_radarModeChangeRequest", targeting_radarModeChangeRequest)
register_message_type("targeting_radarModeChangeResponse", targeting_radarModeChangeResponse)
register_message_type("targeting_radarTrackRequest", targeting_radarTrackRequest)
register_message_type("targeting_radarTrackResponse", targeting_radarTrackResponse)
register_message_type("targeting_radarLockRequest", targeting_radarLockRequest)
register_message_type("targeting_radarLockResponse", targeting_radarLockResponse)
