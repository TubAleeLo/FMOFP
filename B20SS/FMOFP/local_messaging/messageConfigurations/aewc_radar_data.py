"""
AEWC Radar Data Message Configuration

This module defines message structures for AEWC (Airborne Early Warning and Control) radar data communications.
"""

import datetime
from typing import Dict, Any, Optional, List, Union

from .base_message import BaseMessage, register_message_type


class aewc_radarTrackRequest(BaseMessage):
    """
    Request for track data from AEWC radar.
    """
    
    def __init__(self, message_header="data_request", sending_system=None, destination=None, 
                 request_uuid=None, track_parameters=None):
        """
        Initialize an AEWC radar track request message.
        
        Args:
            message_header: Message header type
            sending_system: System sending the message
            destination: Target system for the message
            request_uuid: Unique identifier for the request
            track_parameters: Dictionary of track parameters
        """
        # NOTE: previously called with positional args, which silently
        #   mis-assigned into the wrong BaseMessage fields (sending_system's
        #   value landed in `timestamp`, destination's value landed in
        #   `message_uuid`) since BaseMessage's field order does not match this
        #   argument order. sending_system/destination were therefore always
        #   None on every instance of this class. Fixed to use keyword args.
        super().__init__(message_header=message_header, sending_system=sending_system,
                          destination=destination, request_uuid=request_uuid)
        
        self.track_parameters = track_parameters or {}
        self.command_type = "track_data"
        
    def serialize(self) -> Dict[str, Any]:
        """Serialize the message to a dictionary."""
        data = super().serialize()
        data.update({
            "track_parameters": self.track_parameters,
            "command_type": self.command_type
        })
        return data
        
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'aewc_radarTrackRequest':
        """
        Deserialize a dictionary to an AEWC radar track request.
        
        Args:
            data: Dictionary containing serialized data
            
        Returns:
            An AEWC radar track request instance
        """
        instance = cls(
            message_header=data.get('message_header', 'data_request'),
            sending_system=data.get('sending_system'),
            destination=data.get('destination'),
            request_uuid=data.get('request_uuid'),
            track_parameters=data.get('track_parameters', {})
        )
        
        if 'command_type' in data:
            instance.command_type = data['command_type']
            
        # Transfer metadata if present
        if 'metadata' in data:
            instance.metadata = data['metadata']
            
        return instance


class aewc_radarSectorScanRequest(BaseMessage):
    """
    Request for sector scan from AEWC radar.
    """
    
    def __init__(self, message_header="data_request", sending_system=None, destination=None, 
                 request_uuid=None, sector_parameters=None):
        """
        Initialize an AEWC radar sector scan request message.
        
        Args:
            message_header: Message header type
            sending_system: System sending the message
            destination: Target system for the message
            request_uuid: Unique identifier for the request
            sector_parameters: Dictionary of sector scan parameters
        """
        # NOTE: previously called with positional args, which silently
        #   mis-assigned into the wrong BaseMessage fields (sending_system's
        #   value landed in `timestamp`, destination's value landed in
        #   `message_uuid`) since BaseMessage's field order does not match this
        #   argument order. sending_system/destination were therefore always
        #   None on every instance of this class. Fixed to use keyword args.
        super().__init__(message_header=message_header, sending_system=sending_system,
                          destination=destination, request_uuid=request_uuid)
        
        self.sector_parameters = sector_parameters or {}
        self.command_type = "sector_scan"
        
    def serialize(self) -> Dict[str, Any]:
        """Serialize the message to a dictionary."""
        data = super().serialize()
        data.update({
            "sector_parameters": self.sector_parameters,
            "command_type": self.command_type
        })
        return data
        
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'aewc_radarSectorScanRequest':
        """
        Deserialize a dictionary to an AEWC radar sector scan request.
        
        Args:
            data: Dictionary containing serialized data
            
        Returns:
            An AEWC radar sector scan request instance
        """
        instance = cls(
            message_header=data.get('message_header', 'data_request'),
            sending_system=data.get('sending_system'),
            destination=data.get('destination'),
            request_uuid=data.get('request_uuid'),
            sector_parameters=data.get('sector_parameters', {})
        )
        
        if 'command_type' in data:
            instance.command_type = data['command_type']
            
        # Transfer metadata if present
        if 'metadata' in data:
            instance.metadata = data['metadata']
            
        return instance


class aewc_radarTrackResponse(BaseMessage):
    """
    Response with track data from AEWC radar.
    """
    
    def __init__(self, message_header="data_response", sending_system=None, destination=None, 
                 request_uuid=None, track_data=None):
        """
        Initialize an AEWC radar track response message.
        
        Args:
            message_header: Message header type
            sending_system: System sending the message
            destination: Target system for the message
            request_uuid: Unique identifier for the request
            track_data: Dictionary or list of dictionaries containing track data
        """
        # NOTE: previously called with positional args, which silently
        #   mis-assigned into the wrong BaseMessage fields (sending_system's
        #   value landed in `timestamp`, destination's value landed in
        #   `message_uuid`) since BaseMessage's field order does not match this
        #   argument order. sending_system/destination were therefore always
        #   None on every instance of this class. Fixed to use keyword args.
        super().__init__(message_header=message_header, sending_system=sending_system,
                          destination=destination, request_uuid=request_uuid)
        
        self.track_data = track_data or []
        self.command_type = "track_data"
        
    def serialize(self) -> Dict[str, Any]:
        """Serialize the message to a dictionary."""
        data = super().serialize()
        data.update({
            "track_data": self.track_data,
            "command_type": self.command_type
        })
        return data
        
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'aewc_radarTrackResponse':
        """
        Deserialize a dictionary to an AEWC radar track response.
        
        Args:
            data: Dictionary containing serialized data
            
        Returns:
            An AEWC radar track response instance
        """
        instance = cls(
            message_header=data.get('message_header', 'data_response'),
            sending_system=data.get('sending_system'),
            destination=data.get('destination'),
            request_uuid=data.get('request_uuid'),
            track_data=data.get('track_data', [])
        )
        
        if 'command_type' in data:
            instance.command_type = data['command_type']
            
        # Transfer metadata if present
        if 'metadata' in data:
            instance.metadata = data['metadata']
            
        return instance


class aewc_radarSectorScanResponse(BaseMessage):
    """
    Response with sector scan data from AEWC radar.
    """
    
    def __init__(self, message_header="data_response", sending_system=None, destination=None, 
                 request_uuid=None, sector_data=None):
        """
        Initialize an AEWC radar sector scan response message.
        
        Args:
            message_header: Message header type
            sending_system: System sending the message
            destination: Target system for the message
            request_uuid: Unique identifier for the request
            sector_data: Sector scan data
        """
        # NOTE: previously called with positional args, which silently
        #   mis-assigned into the wrong BaseMessage fields (sending_system's
        #   value landed in `timestamp`, destination's value landed in
        #   `message_uuid`) since BaseMessage's field order does not match this
        #   argument order. sending_system/destination were therefore always
        #   None on every instance of this class. Fixed to use keyword args.
        super().__init__(message_header=message_header, sending_system=sending_system,
                          destination=destination, request_uuid=request_uuid)
        
        self.sector_data = sector_data or {}
        self.command_type = "sector_scan"
        
    def serialize(self) -> Dict[str, Any]:
        """Serialize the message to a dictionary."""
        data = super().serialize()
        data.update({
            "sector_data": self.sector_data,
            "command_type": self.command_type
        })
        return data
        
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'aewc_radarSectorScanResponse':
        """
        Deserialize a dictionary to an AEWC radar sector scan response.
        
        Args:
            data: Dictionary containing serialized data
            
        Returns:
            An AEWC radar sector scan response instance
        """
        instance = cls(
            message_header=data.get('message_header', 'data_response'),
            sending_system=data.get('sending_system'),
            destination=data.get('destination'),
            request_uuid=data.get('request_uuid'),
            sector_data=data.get('sector_data', {})
        )
        
        if 'command_type' in data:
            instance.command_type = data['command_type']
            
        # Transfer metadata if present
        if 'metadata' in data:
            instance.metadata = data['metadata']
            
        return instance


class aewc_radarSectorData(BaseMessage):
    """
    Live sector scan data update from AEWC radar.

    Added because RadarMessageHandler._handle_aewc_sector_data() constructs this
    class (data_uuid, sector_id, scan_data, detected_tracks, timestamp) but it did
    not exist anywhere in the codebase - every AEWC sector data update raised a
    NameError, silently caught and logged by the handler's own try/except, meaning
    AEWC sector scan data was never actually processed downstream.
    """

    def __init__(self, data_uuid: str, sector_id: Any, scan_data: Any = None,
                 detected_tracks: Optional[List] = None, **kwargs):
        """
        Initialize AEWC radar sector data message.

        Args:
            data_uuid: Unique identifier for this data message
            sector_id: Identifier of the scanned sector
            scan_data: Raw/processed sector scan data
            detected_tracks: List of tracks detected within this sector
        """
        super().__init__(message_type="aewc_radarSectorData", data_uuid=data_uuid, **kwargs)
        self.sector_id = sector_id
        self.scan_data = scan_data or {}
        self.detected_tracks = detected_tracks or []


class aewc_radarStealthData(BaseMessage):
    """
    Stealth-target assessment data from AEWC radar.

    Added because RadarMessageHandler._handle_aewc_sector_data() constructs this
    class (data_uuid, track_id, stealth_metrics, confidence, timestamp) for
    stealth-flagged targets within a sector, but it did not exist anywhere in the
    codebase - every such update raised a NameError, silently caught and logged
    by the handler's own try/except, meaning AEWC stealth-target data was never
    actually processed downstream.
    """

    def __init__(self, data_uuid: str, track_id: Any, stealth_metrics: Optional[Dict] = None,
                 confidence: float = 0.0, **kwargs):
        """
        Initialize AEWC radar stealth data message.

        Args:
            data_uuid: Unique identifier for this data message
            track_id: Identifier of the stealth-flagged track
            stealth_metrics: Dictionary of stealth-related metrics
            confidence: Confidence score for the stealth classification
        """
        super().__init__(message_type="aewc_radarStealthData", data_uuid=data_uuid, **kwargs)
        self.track_id = track_id
        self.stealth_metrics = stealth_metrics or {}
        self.confidence = confidence


# Register message types
register_message_type("aewc_radarTrackRequest", aewc_radarTrackRequest)
register_message_type("aewc_radarSectorScanRequest", aewc_radarSectorScanRequest)
register_message_type("aewc_radarTrackResponse", aewc_radarTrackResponse)
register_message_type("aewc_radarSectorScanResponse", aewc_radarSectorScanResponse)
register_message_type("aewc_radarSectorData", aewc_radarSectorData)
register_message_type("aewc_radarStealthData", aewc_radarStealthData)
