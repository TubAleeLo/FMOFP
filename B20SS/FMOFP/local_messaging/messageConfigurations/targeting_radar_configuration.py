"""
Targeting Radar Configuration Messages

Defines configuration message types for targeting radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List, Tuple

class targeting_radarConfiguration(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, config_data: Dict, **kwargs):
        super().__init__(message_type="targeting_radarConfiguration", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.config_data = config_data

class targeting_radarConfigRequest(BaseMessage):
    def __init__(self, request_uuid: str, config_type: str, **kwargs):
        """
        Initialize configuration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            config_type: Type of configuration requested 
                        ("SEARCH", "TRACK", "PROCESSING", "WAVEFORM")
        """
        super().__init__(message_type="targeting_radarConfigRequest", request_uuid=request_uuid, **kwargs)
        self.config_type = config_type

class targeting_radarConfigResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, config_type: str, config_data: Dict, **kwargs):
        """
        Initialize configuration response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            config_type: Type of configuration being returned
            config_data: Dictionary containing the configuration data
        """
        super().__init__(message_type="targeting_radarConfigResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.config_type = config_type
        self.config_data = config_data

class targeting_radarConfigUpdate(BaseMessage):
    def __init__(self, update_uuid: str, config_type: str, config_updates: Dict, **kwargs):
        """
        Initialize configuration update message.
        
        Args:
            update_uuid: Unique identifier for this update
            config_type: Type of configuration being updated
            config_updates: Dictionary containing the configuration updates
        """
        super().__init__(message_type="targeting_radarConfigUpdate", update_uuid=update_uuid, **kwargs)
        self.config_type = config_type
        self.config_updates = config_updates

class targeting_radarSearchConfig(BaseMessage):
    def __init__(self, config_uuid: str, search_volume: Dict, revisit_rate: float,
                 priority_zones: List[Dict], **kwargs):
        """
        Initialize search configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            search_volume: Search volume parameters (azimuth, elevation ranges)
            revisit_rate: Search volume revisit rate in Hz
            priority_zones: List of priority search zones
        """
        super().__init__(message_type="targeting_radarSearchConfig", config_uuid=config_uuid, **kwargs)
        self.search_volume = search_volume
        self.revisit_rate = revisit_rate
        self.priority_zones = priority_zones

class targeting_radarTrackConfig(BaseMessage):
    def __init__(self, config_uuid: str, max_tracks: int, track_priorities: Dict,
                 track_filters: Dict, **kwargs):
        """
        Initialize track configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            max_tracks: Maximum number of simultaneous tracks
            track_priorities: Track priority configuration
            track_filters: Track filtering parameters
        """
        super().__init__(message_type="targeting_radarTrackConfig", config_uuid=config_uuid, **kwargs)
        self.max_tracks = max_tracks
        self.track_priorities = track_priorities
        self.track_filters = track_filters

class targeting_radarWaveformConfig(BaseMessage):
    def __init__(self, config_uuid: str, prf: float, pulse_width: float,
                 frequency: float, bandwidth: float, **kwargs):
        """
        Initialize waveform configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            prf: Pulse Repetition Frequency in Hz
            pulse_width: Pulse width in seconds
            frequency: Center frequency in Hz
            bandwidth: Bandwidth in Hz
        """
        super().__init__(message_type="targeting_radarWaveformConfig", config_uuid=config_uuid, **kwargs)
        self.prf = prf
        self.pulse_width = pulse_width
        self.frequency = frequency
        self.bandwidth = bandwidth

class targeting_radarConfigAcknowledgment(BaseMessage):
    def __init__(self, update_uuid: str, status: str, message: str = "", **kwargs):
        """
        Initialize configuration acknowledgment message.
        
        Args:
            update_uuid: UUID of the configuration update being acknowledged
            status: Status of the update ("SUCCESS", "FAILURE")
            message: Optional status message
        """
        super().__init__(message_type="targeting_radarConfigAcknowledgment", update_uuid=update_uuid, **kwargs)
        self.status = status
        self.message = message

# Register message types
register_message_type("targeting_radarConfiguration", targeting_radarConfiguration)
register_message_type("targeting_radarConfigRequest", targeting_radarConfigRequest)
register_message_type("targeting_radarConfigResponse", targeting_radarConfigResponse)
register_message_type("targeting_radarConfigUpdate", targeting_radarConfigUpdate)
register_message_type("targeting_radarSearchConfig", targeting_radarSearchConfig)
register_message_type("targeting_radarTrackConfig", targeting_radarTrackConfig)
register_message_type("targeting_radarWaveformConfig", targeting_radarWaveformConfig)
register_message_type("targeting_radarConfigAcknowledgment", targeting_radarConfigAcknowledgment)
