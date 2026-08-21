"""
TFR Radar Configuration Messages

Defines configuration message types for TFR radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict

class tfr_radarConfiguration(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, config_data: Dict, **kwargs):
        super().__init__(message_type="tfr_radarConfiguration", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.config_data = config_data

class tfr_radarConfigRequest(BaseMessage):
    def __init__(self, request_uuid: str, config_type: str, **kwargs):
        """
        Initialize configuration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            config_type: Type of configuration requested ("SCAN", "CLEARANCE", "PROCESSING")
        """
        super().__init__(message_type="tfr_radarConfigRequest", request_uuid=request_uuid, **kwargs)
        self.config_type = config_type

class tfr_radarConfigResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, config_type: str, config_data: Dict, **kwargs):
        """
        Initialize configuration response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            config_type: Type of configuration being returned
            config_data: Dictionary containing the configuration data
        """
        super().__init__(message_type="tfr_radarConfigResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.config_type = config_type
        self.config_data = config_data

class tfr_radarConfigUpdate(BaseMessage):
    def __init__(self, update_uuid: str, config_type: str, config_updates: Dict, **kwargs):
        """
        Initialize configuration update message.
        
        Args:
            update_uuid: Unique identifier for this update
            config_type: Type of configuration being updated
            config_updates: Dictionary containing the configuration updates
        """
        super().__init__(message_type="tfr_radarConfigUpdate", update_uuid=update_uuid, **kwargs)
        self.config_type = config_type
        self.config_updates = config_updates

class tfr_radarConfigAcknowledgment(BaseMessage):
    def __init__(self, update_uuid: str, status: str, message: str = "", **kwargs):
        """
        Initialize configuration acknowledgment message.
        
        Args:
            update_uuid: UUID of the configuration update being acknowledged
            status: Status of the update ("SUCCESS", "FAILURE")
            message: Optional status message
        """
        super().__init__(message_type="tfr_radarConfigAcknowledgment", update_uuid=update_uuid, **kwargs)
        self.status = status
        self.message = message

# Register message types
register_message_type("tfr_radarConfiguration", tfr_radarConfiguration)
register_message_type("tfr_radarConfigRequest", tfr_radarConfigRequest)
register_message_type("tfr_radarConfigResponse", tfr_radarConfigResponse)
register_message_type("tfr_radarConfigUpdate", tfr_radarConfigUpdate)
register_message_type("tfr_radarConfigAcknowledgment", tfr_radarConfigAcknowledgment)
