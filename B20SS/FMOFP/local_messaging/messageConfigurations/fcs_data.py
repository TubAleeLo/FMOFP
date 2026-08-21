"""
Flight Control System Data Messages

Defines data message types for FCS communication.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
import time
import uuid

from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.local_messaging.command_word_map_fcs import get_fcs_command_word
from FMOFP.local_messaging.message_types_fcs import (
    FCS_CONTROL_INPUT_REQUEST,
    FCS_CONTROL_INPUT_RESPONSE,
    FCS_STATUS_REQUEST,
    FCS_STATUS_RESPONSE
)

class fcs_baseData(BaseMessage):
    """Base class for all FCS data messages"""
    def __init__(self, message_header, sending_system, destination, message_type, data, **kwargs):
        super().__init__(message_type="fcs_baseData", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.data = data or {}

class fcs_controlSurfaceRequest(BaseMessage):
    """Control surface request message"""
    def __init__(self, message_header, sending_system, destination, request_uuid=None, 
                 surface_data=None, **kwargs):
        """
        Initialize control surface request.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Unique identifier for request
            surface_data: Dictionary with surface control data
        """
        super().__init__(
            message_type="fcs_controlSurfaceRequest",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FCS_CONTROL_INPUT_REQUEST,
            **kwargs
        )
        self.request_uuid = request_uuid or str(uuid.uuid4())
        self.surface_data = surface_data or {}
        
    def validate(self):
        """Validate control surface request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.surface_data, dict):
            raise ValueError("surface_data must be a dictionary")
        if "surface" not in self.surface_data:
            raise ValueError("surface_data must contain a 'surface' key")
        if "position" not in self.surface_data:
            raise ValueError("surface_data must contain a 'position' key")
            
    def encode_1553b(self):
        """Encode message for 1553B transmission"""
        command_word = get_fcs_command_word(FCS_CONTROL_INPUT_REQUEST).value
        
        # Format: [command_word, surface_id, position_value, rate_value, flags]
        surface_map = {
            "aileron": 0x01,
            "elevator": 0x02,
            "rudder": 0x03,
            "flaps": 0x04,
            "spoilers": 0x05,
            "speedbrake": 0x06,
            "trim": 0x07
        }
        
        surface_id = surface_map.get(self.surface_data.get("surface", "").lower(), 0x00)
        position = int(self.surface_data.get("position", 0) * 100) & 0xFFFF  # Scale by 100
        rate = int(self.surface_data.get("rate", 0) * 100) & 0xFFFF if "rate" in self.surface_data else 0
        flags = 0x0001 if self.surface_data.get("override", False) else 0x0000
        
        return [command_word, surface_id, position, rate, flags]

class fcs_controlSurfaceResponse(BaseMessage):
    """Control surface response message"""
    def __init__(self, message_header, sending_system, destination, request_uuid, 
                 response_uuid=None, status=None, surface_data=None, **kwargs):
        """
        Initialize control surface response.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Original request UUID
            response_uuid: Unique identifier for response
            status: Status code ("SUCCESS", "ERROR", etc.)
            surface_data: Dictionary with current surface control data
        """
        super().__init__(
            message_type="fcs_controlSurfaceResponse",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FCS_CONTROL_INPUT_RESPONSE,
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid or str(uuid.uuid4())
        self.status = status or "SUCCESS"
        self.surface_data = surface_data or {}
        
    def validate(self):
        """Validate control surface response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.surface_data, dict):
            raise ValueError("surface_data must be a dictionary")

# Register message types
register_message_type("fcs_baseData", fcs_baseData)
register_message_type("fcs_controlSurfaceRequest", fcs_controlSurfaceRequest)
register_message_type("fcs_controlSurfaceResponse", fcs_controlSurfaceResponse)
