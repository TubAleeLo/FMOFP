from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json
import time

@dataclass
class FMSBaseMessage:
    """Base class for all FMS messages"""
    message_type: str = "fms_message"
    timestamp: float = field(default_factory=time.time)
    
    def validate(self) -> bool:
        """Validate message fields"""
        return self.message_type is not None and self.timestamp is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "message_type": self.message_type,
            "timestamp": self.timestamp
        }
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        if "message_type" in data:
            self.message_type = data["message_type"]
        if "timestamp" in data:
            self.timestamp = data["timestamp"]
    
    def to_binary(self) -> bytes:
        """Convert message to binary format for transmission"""
        return json.dumps(self.to_dict()).encode('utf-8')

@dataclass
class FMSFlightDataMessage(FMSBaseMessage):
    """Flight data message with attitude and velocity parameters"""
    message_type: str = "fms_flightData"
    attitude: Dict[str, float] = field(default_factory=dict)  # Roll, pitch, yaw
    velocity: Dict[str, float] = field(default_factory=dict)  # Airspeed, vertical speed, etc.
    navigation: Dict[str, Any] = field(default_factory=dict)  # Position, heading, etc.
    tactical: Dict[str, Any] = field(default_factory=dict)    # parameters
    
    def validate(self) -> bool:
        """Validate flight data message"""
        return (super().validate() and 
                isinstance(self.attitude, dict) and 
                isinstance(self.velocity, dict) and
                isinstance(self.navigation, dict))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = super().to_dict()
        result.update({
            "attitude": self.attitude,
            "velocity": self.velocity,
            "navigation": self.navigation,
            "tactical": self.tactical
        })
        return result
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        super().from_dict(data)
        if "attitude" in data:
            self.attitude = data["attitude"]
        if "velocity" in data:
            self.velocity = data["velocity"]
        if "navigation" in data:
            self.navigation = data["navigation"]
        if "tactical" in data:
            self.tactical = data["tactical"]

@dataclass
class FMSCommandRequest(FMSBaseMessage):
    """Command request for flight management system"""
    message_type: str = "fms_commandRequest"
    command_type: str = ""  # Type of command (SET_MODE, UPDATE_ATTITUDE, etc.)
    parameters: Dict[str, Any] = field(default_factory=dict)  # Command parameters
    request_id: str = ""  # Unique request ID for tracking
    
    def validate(self) -> bool:
        """Validate command request message"""
        return (super().validate() and 
                self.command_type and 
                isinstance(self.parameters, dict))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = super().to_dict()
        result.update({
            "command_type": self.command_type,
            "parameters": self.parameters,
            "request_id": self.request_id
        })
        return result
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        super().from_dict(data)
        if "command_type" in data:
            self.command_type = data["command_type"]
        if "parameters" in data:
            self.parameters = data["parameters"]
        if "request_id" in data:
            self.request_id = data["request_id"]

@dataclass
class FMSCommandResponse(FMSBaseMessage):
    """Response to a command request"""
    message_type: str = "fms_commandResponse"
    status: str = ""  # SUCCESS, ERROR, etc.
    request_id: str = ""  # Original request ID
    message: str = ""  # Status message
    data: Dict[str, Any] = field(default_factory=dict)  # Response data
    
    def validate(self) -> bool:
        """Validate command response message"""
        return (super().validate() and 
                self.status and 
                self.request_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = super().to_dict()
        result.update({
            "status": self.status,
            "request_id": self.request_id,
            "message": self.message,
            "data": self.data
        })
        return result
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        super().from_dict(data)
        if "status" in data:
            self.status = data["status"]
        if "request_id" in data:
            self.request_id = data["request_id"]
        if "message" in data:
            self.message = data["message"]
        if "data" in data:
            self.data = data["data"]

@dataclass
class FMSModeChangeRequest(FMSCommandRequest):
    """Request to change FMS mode"""
    message_type: str = "fms_modeChangeRequest"
    command_type: str = "SET_MODE"
    mode_name: str = field(default="")
    metadata: Dict[str, Any] = field(default_factory=dict)  # Add explicit metadata field
    
    def __post_init__(self):
        """Set mode parameter if provided"""
        # Initialize parameters if not already initialized
        if not hasattr(self, 'parameters') or self.parameters is None:
            self.parameters = {}
            
        # Handle the mode parameter that may have been passed directly
        if "mode" in self.__dict__:
            # If mode was passed to constructor, store it in mode_name
            self.mode_name = self.__dict__.pop("mode")
            
        # Set mode in parameters dictionary for backward compatibility
        if self.mode_name:
            self.parameters["mode"] = self.mode_name
        # If mode was provided in parameters but not as direct attribute
        elif "mode" in self.parameters and not self.mode_name:
            self.mode_name = self.parameters["mode"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary, ensuring mode is included"""
        result = super().to_dict()
        # Use mode_name internally but expose as mode in the dictionary
        result["mode"] = self.mode_name
        # Include metadata if present
        if hasattr(self, 'metadata') and self.metadata:
            result["metadata"] = self.metadata
        return result

@dataclass
class FMSModeChangeResponse(FMSCommandResponse):
    """Response to a mode change request"""
    message_type: str = "fms_modeChangeResponse"
    old_mode: str = ""  # Previous mode
    new_mode: str = ""  # New mode
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = super().to_dict()
        result.update({
            "old_mode": self.old_mode,
            "new_mode": self.new_mode
        })
        return result
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        super().from_dict(data)
        if "old_mode" in data:
            self.old_mode = data["old_mode"]
        if "new_mode" in data:
            self.new_mode = data["new_mode"]

@dataclass
class FMSAttitudeUpdateRequest(FMSCommandRequest):
    """Request to update aircraft attitude"""
    message_type: str = "fms_attitudeUpdateRequest"
    command_type: str = "UPDATE_ATTITUDE"

@dataclass
class FMSNavigationUpdateRequest(FMSCommandRequest):
    """Request to update navigation parameters"""
    message_type: str = "fms_navigationUpdateRequest"
    command_type: str = "SET_AUTOPILOT"

@dataclass
class FMSStatusRequest(FMSCommandRequest):
    """Request for FMS status"""
    message_type: str = "fms_statusRequest"
    command_type: str = "GET_STATUS"

@dataclass
class FMSStatusResponse(FMSCommandResponse):
    """Response with FMS status"""
    message_type: str = "fms_statusResponse"
    mode: str = ""  # Current FMS mode
    health: str = ""  # System health status
    warnings: List[str] = field(default_factory=list)  # Active warnings
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = super().to_dict()
        result.update({
            "mode": self.mode,
            "health": self.health,
            "warnings": self.warnings
        })
        return result
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load message from dictionary"""
        super().from_dict(data)
        if "mode" in data:
            self.mode = data["mode"]
        if "health" in data:
            self.health = data["health"]
        if "warnings" in data:
            self.warnings = data["warnings"]

@dataclass
class FMSManeuverRequest(FMSCommandRequest):
    """Request to execute a flight maneuver"""
    message_type: str = "fms_maneuverRequest"
    command_type: str = "EXECUTE_MANEUVER"
    maneuver_type: str = ""  # Type of maneuver
    
    def __post_init__(self):
        """Set maneuver_type in parameters"""
        if self.maneuver_type:
            self.parameters["maneuver_type"] = self.maneuver_type

# Factory function to create messages from type
def create_fms_message(message_type: str, **kwargs) -> FMSBaseMessage:
    """
    Create an FMS message of the specified type
    
    Args:
        message_type (str): Type of message to create
        **kwargs: Message parameters
        
    Returns:
        FMSBaseMessage: The created message
    """
    # Message type mapping
    message_classes = {
        "fms_flightData": FMSFlightDataMessage,
        "fms_commandRequest": FMSCommandRequest,
        "fms_commandResponse": FMSCommandResponse,
        "fms_modeChangeRequest": FMSModeChangeRequest,
        "fms_modeChangeResponse": FMSModeChangeResponse,
        "fms_attitudeUpdateRequest": FMSAttitudeUpdateRequest,
        "fms_navigationUpdateRequest": FMSNavigationUpdateRequest,
        "fms_statusRequest": FMSStatusRequest,
        "fms_statusResponse": FMSStatusResponse,
        "fms_maneuverRequest": FMSManeuverRequest
    }
    
    # Create message of appropriate type
    if message_type in message_classes:
        return message_classes[message_type](**kwargs)
    else:
        # Default to base message
        return FMSBaseMessage(message_type=message_type, **kwargs)

# Message registry for type lookup
_message_registry = {}

def register_message_type(message_class):
    """Register a message class in the registry"""
    _message_registry[message_class.__name__] = message_class
    return message_class

# Register all message classes
for cls in [
    FMSBaseMessage,
    FMSFlightDataMessage,
    FMSCommandRequest,
    FMSCommandResponse,
    FMSModeChangeRequest,
    FMSModeChangeResponse,
    FMSAttitudeUpdateRequest,
    FMSNavigationUpdateRequest,
    FMSStatusRequest, 
    FMSStatusResponse,
    FMSManeuverRequest
]:
    register_message_type(cls)
