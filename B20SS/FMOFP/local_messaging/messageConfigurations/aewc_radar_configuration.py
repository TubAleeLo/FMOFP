"""
AEWC Radar Configuration Messages

Defines configuration message types for AEWC radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import Dict, List, Tuple

class aewc_radarConfiguration(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, config_data: Dict, **kwargs):
        super().__init__(message_type="aewc_radarConfiguration", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.config_data = config_data

class aewc_radarConfigRequest(BaseMessage):
    def __init__(self, request_uuid: str, config_type: str, **kwargs):
        """
        Initialize configuration request message.
        
        Args:
            request_uuid: Unique identifier for this request
            config_type: Type of configuration requested 
                        ("SURVEILLANCE", "TRACK", "PROCESSING", "SECTOR")
        """
        super().__init__(message_type="aewc_radarConfigRequest", request_uuid=request_uuid, **kwargs)
        self.config_type = config_type

class aewc_radarConfigResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, config_type: str, config_data: Dict, **kwargs):
        """
        Initialize configuration response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            config_type: Type of configuration being returned
            config_data: Dictionary containing the configuration data
        """
        super().__init__(message_type="aewc_radarConfigResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.config_type = config_type
        self.config_data = config_data

class aewc_radarConfigUpdate(BaseMessage):
    def __init__(self, update_uuid: str, config_type: str, config_updates: Dict, **kwargs):
        """
        Initialize configuration update message.
        
        Args:
            update_uuid: Unique identifier for this update
            config_type: Type of configuration being updated
            config_updates: Dictionary containing the configuration updates
        """
        super().__init__(message_type="aewc_radarConfigUpdate", update_uuid=update_uuid, **kwargs)
        self.config_type = config_type
        self.config_updates = config_updates

class aewc_radarSurveillanceConfig(BaseMessage):
    def __init__(self, config_uuid: str, coverage_volume: Dict, scan_strategy: str,
                 priority_sectors: List[Dict], **kwargs):
        """
        Initialize surveillance configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            coverage_volume: Coverage volume parameters
            scan_strategy: Scan strategy type
            priority_sectors: List of priority sectors
        """
        super().__init__(message_type="aewc_radarSurveillanceConfig", config_uuid=config_uuid, **kwargs)
        self.coverage_volume = coverage_volume
        self.scan_strategy = scan_strategy
        self.priority_sectors = priority_sectors

class aewc_radarTrackConfig(BaseMessage):
    def __init__(self, config_uuid: str, max_tracks: int, track_priorities: Dict,
                 stealth_detection_params: Dict, **kwargs):
        """
        Initialize track configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            max_tracks: Maximum number of simultaneous tracks
            track_priorities: Track priority configuration
            stealth_detection_params: Stealth detection parameters
        """
        super().__init__(message_type="aewc_radarTrackConfig", config_uuid=config_uuid, **kwargs)
        self.max_tracks = max_tracks
        self.track_priorities = track_priorities
        self.stealth_detection_params = stealth_detection_params

class aewc_radarSectorConfig(BaseMessage):
    def __init__(self, config_uuid: str, sector_definitions: List[Dict],
                 scan_patterns: Dict, revisit_intervals: Dict, **kwargs):
        """
        Initialize sector configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            sector_definitions: List of sector definitions
            scan_patterns: Scan patterns for each sector type
            revisit_intervals: Revisit intervals for each sector
        """
        super().__init__(message_type="aewc_radarSectorConfig", config_uuid=config_uuid, **kwargs)
        self.sector_definitions = sector_definitions
        self.scan_patterns = scan_patterns
        self.revisit_intervals = revisit_intervals

class aewc_radarProcessingConfig(BaseMessage):
    def __init__(self, config_uuid: str, detection_thresholds: Dict,
                 clutter_map_params: Dict, tracking_filters: Dict, **kwargs):
        """
        Initialize processing configuration.
        
        Args:
            config_uuid: Unique identifier for this configuration
            detection_thresholds: Detection threshold parameters
            clutter_map_params: Clutter mapping parameters
            tracking_filters: Track filtering parameters
        """
        super().__init__(message_type="aewc_radarProcessingConfig", config_uuid=config_uuid, **kwargs)
        self.detection_thresholds = detection_thresholds
        self.clutter_map_params = clutter_map_params
        self.tracking_filters = tracking_filters

class aewc_radarConfigAcknowledgment(BaseMessage):
    def __init__(self, update_uuid: str, status: str, message: str = "", **kwargs):
        """
        Initialize configuration acknowledgment message.
        
        Args:
            update_uuid: UUID of the configuration update being acknowledged
            status: Status of the update ("SUCCESS", "FAILURE")
            message: Optional status message
        """
        super().__init__(message_type="aewc_radarConfigAcknowledgment", update_uuid=update_uuid, **kwargs)
        self.status = status
        self.message = message

# Register message types
register_message_type("aewc_radarConfiguration", aewc_radarConfiguration)
register_message_type("aewc_radarConfigRequest", aewc_radarConfigRequest)
register_message_type("aewc_radarConfigResponse", aewc_radarConfigResponse)
register_message_type("aewc_radarConfigUpdate", aewc_radarConfigUpdate)
register_message_type("aewc_radarSurveillanceConfig", aewc_radarSurveillanceConfig)
register_message_type("aewc_radarTrackConfig", aewc_radarTrackConfig)
register_message_type("aewc_radarSectorConfig", aewc_radarSectorConfig)
register_message_type("aewc_radarProcessingConfig", aewc_radarProcessingConfig)
register_message_type("aewc_radarConfigAcknowledgment", aewc_radarConfigAcknowledgment)
