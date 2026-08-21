"""
FMS Data Message Configurations

This module provides message classes for FMS data including:
- Attitude updates (pitch, roll, yaw)
- Navigation updates (position, altitude, heading)
- Maneuver requests
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
import uuid

from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.local_messaging.command_word_map_fms import get_fms_command_word
from FMOFP.local_messaging.message_types import (
    FMS_ATTITUDE_UPDATE_REQUEST,
    FMS_ATTITUDE_UPDATE_RESPONSE,
    FMS_NAVIGATION_UPDATE_REQUEST,
    FMS_NAVIGATION_UPDATE_RESPONSE,
    FMS_MANEUVER_REQUEST,
    FMS_MANEUVER_RESPONSE
)

# Import existing message utility functions as reference
from FMOFP.local_messaging.messageConfigurations.fms_attitude_data import (
    create_fms_attitude_data_message,
    encode_fms_attitude_data
)
from FMOFP.local_messaging.messageConfigurations.fms_navigation_data import (
    create_fms_navigation_data_message,
    encode_fms_navigation_data
)

class fms_attitudeUpdateRequest(BaseMessage):
    """Attitude update request message"""
    def __init__(self, message_header, sending_system, destination, request_uuid=None, 
                 attitude_data=None, **kwargs):
        """
        Initialize attitude update request.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Unique identifier for request
            attitude_data: Dictionary with attitude data (pitch, roll, yaw)
        """
        super().__init__(
            message_type="fms_attitudeUpdateRequest",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_ATTITUDE_UPDATE_REQUEST,
            **kwargs
        )
        self.request_uuid = request_uuid or str(uuid.uuid4())
        self.attitude_data = attitude_data or {}
        
    def validate(self):
        """Validate attitude update request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.attitude_data, dict):
            raise ValueError("attitude_data must be a dictionary")
            
    def encode_1553b(self):
        """Encode message for 1553B transmission"""
        command_word = get_fms_command_word(FMS_ATTITUDE_UPDATE_REQUEST).value
        
        # Get roll, pitch, yaw values with defaults
        roll = float(self.attitude_data.get("roll", 0.0))
        pitch = float(self.attitude_data.get("pitch", 0.0))
        yaw = float(self.attitude_data.get("yaw", 0.0))
        
        # Scale values to fit in 16-bit integers (scale by 100 for 2 decimal places)
        roll_int = int(roll * 100) & 0xFFFF
        pitch_int = int(pitch * 100) & 0xFFFF
        yaw_int = int(yaw * 100) & 0xFFFF
        
        # Construct data words
        data_words = [0x0501, roll_int, pitch_int, yaw_int]
        
        return [command_word] + data_words

class fms_attitudeUpdateResponse(BaseMessage):
    """Attitude update response message"""
    def __init__(self, message_header, sending_system, destination, request_uuid, 
                 response_uuid=None, status=None, attitude_data=None, **kwargs):
        """
        Initialize attitude update response.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Original request UUID
            response_uuid: Unique identifier for response
            status: Status code ("SUCCESS", "ERROR", etc.)
            attitude_data: Dictionary with current attitude data
        """
        super().__init__(
            message_type="fms_attitudeUpdateResponse",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_ATTITUDE_UPDATE_RESPONSE,
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid or str(uuid.uuid4())
        self.status = status or "SUCCESS"
        self.attitude_data = attitude_data or {}
        
    def validate(self):
        """Validate attitude update response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.attitude_data, dict):
            raise ValueError("attitude_data must be a dictionary")

class fms_navigationUpdateRequest(BaseMessage):
    """Navigation update request message"""
    def __init__(self, message_header, sending_system, destination, request_uuid=None, 
                 navigation_data=None, **kwargs):
        """
        Initialize navigation update request.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Unique identifier for request
            navigation_data: Dictionary with navigation data (position, etc.)
        """
        super().__init__(
            message_type="fms_navigationUpdateRequest",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_NAVIGATION_UPDATE_REQUEST,
            **kwargs
        )
        self.request_uuid = request_uuid or str(uuid.uuid4())
        self.navigation_data = navigation_data or {}
        
    def validate(self):
        """Validate navigation update request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.navigation_data, dict):
            raise ValueError("navigation_data must be a dictionary")
            
    def encode_1553b(self):
        """Encode message for 1553B transmission"""
        command_word = get_fms_command_word(FMS_NAVIGATION_UPDATE_REQUEST).value
        
        # Get navigation values with defaults
        latitude = float(self.navigation_data.get("latitude", 0.0))
        longitude = float(self.navigation_data.get("longitude", 0.0))
        altitude = float(self.navigation_data.get("altitude", 0.0))
        heading = float(self.navigation_data.get("heading", 0.0))
        
        # Scale values
        lat_adjusted = (latitude + 90.0) % 180.0
        lon_adjusted = (longitude + 180.0) % 360.0
        
        lat_int = int(lat_adjusted * 100) & 0xFFFF
        lon_int = int(lon_adjusted * 100) & 0xFFFF
        alt_int = min(65535, max(0, int(altitude))) & 0xFFFF
        hdg_int = int((heading % 360.0) * 100) & 0xFFFF
        
        # Construct data words
        data_words = [0x0502, lat_int, lon_int, alt_int, hdg_int]
        
        return [command_word] + data_words

class fms_navigationUpdateResponse(BaseMessage):
    """Navigation update response message"""
    def __init__(self, message_header, sending_system, destination, request_uuid, 
                 response_uuid=None, status=None, navigation_data=None, **kwargs):
        """
        Initialize navigation update response.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Original request UUID
            response_uuid: Unique identifier for response
            status: Status code ("SUCCESS", "ERROR", etc.)
            navigation_data: Dictionary with current navigation data
        """
        super().__init__(
            message_type="fms_navigationUpdateResponse",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_NAVIGATION_UPDATE_RESPONSE,
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid or str(uuid.uuid4())
        self.status = status or "SUCCESS"
        self.navigation_data = navigation_data or {}
        
    def validate(self):
        """Validate navigation update response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.navigation_data, dict):
            raise ValueError("navigation_data must be a dictionary")

class fms_maneuverRequest(BaseMessage):
    """Maneuver request message"""
    def __init__(self, message_header, sending_system, destination, request_uuid=None, 
                 maneuver_data=None, **kwargs):
        """
        Initialize maneuver request.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Unique identifier for request
            maneuver_data: Dictionary with maneuver data
        """
        super().__init__(
            message_type="fms_maneuverRequest",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_MANEUVER_REQUEST,
            **kwargs
        )
        self.request_uuid = request_uuid or str(uuid.uuid4())
        self.maneuver_data = maneuver_data or {}
        
    def validate(self):
        """Validate maneuver request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.maneuver_data, dict):
            raise ValueError("maneuver_data must be a dictionary")
        if "type" not in self.maneuver_data:
            raise ValueError("maneuver_data must contain a 'type' key")
            
    def encode_1553b(self):
        """Encode message for 1553B transmission"""
        command_word = get_fms_command_word(FMS_MANEUVER_REQUEST).value
        
        # Define maneuver type codes
        maneuver_types = {
            "turn": 0x01,
            "climb": 0x02,
            "descend": 0x03,
            "level_off": 0x04,
            "accelerate": 0x05,
            "decelerate": 0x06
        }
        
        # Get maneuver type and convert to code
        maneuver_type = self.maneuver_data.get("type", "").lower()
        type_code = maneuver_types.get(maneuver_type, 0x00)
        
        # Get parameters
        params = self.maneuver_data.get("params", {})
        param1 = int(params.get("param1", 0)) & 0xFFFF
        param2 = int(params.get("param2", 0)) & 0xFFFF
        
        # Construct data words
        data_words = [0x0503, type_code, param1, param2]
        
        return [command_word] + data_words

class fms_maneuverResponse(BaseMessage):
    """Maneuver response message"""
    def __init__(self, message_header, sending_system, destination, request_uuid, 
                 response_uuid=None, status=None, maneuver_data=None, **kwargs):
        """
        Initialize maneuver response.
        
        Args:
            message_header: Message header
            sending_system: Sending system ID
            destination: Destination system ID
            request_uuid: Original request UUID
            response_uuid: Unique identifier for response
            status: Status code ("SUCCESS", "ERROR", etc.)
            maneuver_data: Dictionary with maneuver response data
        """
        super().__init__(
            message_type="fms_maneuverResponse",
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            command_name=FMS_MANEUVER_RESPONSE,
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid or str(uuid.uuid4())
        self.status = status or "SUCCESS"
        self.maneuver_data = maneuver_data or {}
        
    def validate(self):
        """Validate maneuver response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.maneuver_data, dict):
            raise ValueError("maneuver_data must be a dictionary")

# Register message types
register_message_type("fms_attitudeUpdateRequest", fms_attitudeUpdateRequest)
register_message_type("fms_attitudeUpdateResponse", fms_attitudeUpdateResponse)
register_message_type("fms_navigationUpdateRequest", fms_navigationUpdateRequest)
register_message_type("fms_navigationUpdateResponse", fms_navigationUpdateResponse)
register_message_type("fms_maneuverRequest", fms_maneuverRequest)
register_message_type("fms_maneuverResponse", fms_maneuverResponse)
