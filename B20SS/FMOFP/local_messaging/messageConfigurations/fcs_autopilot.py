"""
Flight Control System Autopilot Messages

Defines message types for FCS autopilot management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
import uuid

from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.local_messaging.command_word_map_fcs import get_fcs_command_word
from FMOFP.local_messaging.message_types_fcs import (
    FCS_CONTROL_INPUT_REQUEST,
    FCS_CONTROL_INPUT_RESPONSE
)

class fcs_autoPilotRequest(BaseMessage):
    """Autopilot request message"""
    def __init__(self, message_header, sending_system, destination, request_uuid=None, 
                 autopilot_data=None, **kwargs):
        """
        Initialize autopilot request.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Unique identifier for request
            autopilot_data: Dictionary with autopilot command data
        """
        super().__init__(
            message_type="fcs_autoPilotRequest",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FCS_CONTROL_INPUT_REQUEST,  # Use control input command
            **kwargs
        )
        self.request_uuid = request_uuid or str(uuid.uuid4())
        self.autopilot_data = autopilot_data or {}
        
    def validate(self):
        """Validate autopilot request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.autopilot_data, dict):
            raise ValueError("autopilot_data must be a dictionary")
        if "command" not in self.autopilot_data:
            raise ValueError("autopilot_data must contain a 'command' key")
            
    def encode_1553b(self):
        """Encode message for 1553B transmission"""
        command_word = get_fcs_command_word(FCS_CONTROL_INPUT_REQUEST).value
        
        # Special command ID for autopilot
        command_id = 0xA0  # Autopilot command identifier (0xA0 = 160)
        
        # Command mapping
        ap_command_map = {
            "engage": 0x01,
            "disengage": 0x02,
            "altitude_hold": 0x03,
            "heading_hold": 0x04,
            "airspeed_hold": 0x05,
            "vertical_speed": 0x06,
            "nav_mode": 0x07,
            "approach_mode": 0x08
        }
        
        ap_command = ap_command_map.get(self.autopilot_data.get("command", "").lower(), 0x00)
        
        # Target value (for altitude, heading, etc.)
        target = int(self.autopilot_data.get("target", 0)) & 0xFFFF if "target" in self.autopilot_data else 0
        
        # Flags for additional options
        flags = 0x0000
        
        return [command_word, command_id, ap_command, target, flags]

class fcs_autoPilotResponse(BaseMessage):
    """Autopilot response message"""
    def __init__(self, message_header, sending_system, destination, request_uuid, 
                 response_uuid=None, status=None, autopilot_data=None, **kwargs):
        """
        Initialize autopilot response.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Original request UUID
            response_uuid: Unique identifier for response
            status: Status code ("SUCCESS", "ERROR", etc.)
            autopilot_data: Dictionary with current autopilot data
        """
        super().__init__(
            message_type="fcs_autoPilotResponse",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FCS_CONTROL_INPUT_RESPONSE,  # Use control input response
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid or str(uuid.uuid4())
        self.status = status or "SUCCESS"
        self.autopilot_data = autopilot_data or {}
        
    def validate(self):
        """Validate autopilot response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.autopilot_data, dict):
            raise ValueError("autopilot_data must be a dictionary")

# Register message types
register_message_type("fcs_autoPilotRequest", fcs_autoPilotRequest)
register_message_type("fcs_autoPilotResponse", fcs_autoPilotResponse)
