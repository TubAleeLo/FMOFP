"""
TFR Radar Data Messages

Defines data message types for TFR radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import List, Tuple

class tfr_radarData(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, data, **kwargs):
        super().__init__(message_type="tfr_radarData", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.data = data

class tfr_radarElevationProfile(BaseMessage):
    def __init__(self, data_uuid: str, profile_data: List[Tuple[float, float]], scan_width: float, **kwargs):
        """
        Initialize elevation profile data.
        
        Args:
            data_uuid: Unique identifier for this data message
            profile_data: List of (distance, elevation) tuples in meters
            scan_width: Width of terrain scan in meters
        """
        super().__init__(message_type="tfr_radarElevationProfile", data_uuid=data_uuid, **kwargs)
        self.profile_data = profile_data
        self.scan_width = scan_width

class tfr_radarTerrainWarning(BaseMessage):
    def __init__(self, warning_uuid: str, warning_type: str, distance: float, elevation: float, **kwargs):
        """
        Initialize terrain warning message.
        
        Args:
            warning_uuid: Unique identifier for this warning
            warning_type: Type of warning (e.g., "OBSTACLE", "TERRAIN", "CLEARANCE")
            distance: Distance to terrain feature in meters
            elevation: Elevation of terrain feature in meters
        """
        super().__init__(message_type="tfr_radarTerrainWarning", warning_uuid=warning_uuid, **kwargs)
        self.warning_type = warning_type
        self.distance = distance
        self.elevation = elevation

class tfr_radarDataRequest(BaseMessage):
    def __init__(self, request_uuid: str, data_type: str, scan_parameters: dict, **kwargs):
        """
        Initialize data request message.
        
        Args:
            request_uuid: Unique identifier for this request
            data_type: Type of data requested ("ELEVATION", "WARNING")
            scan_parameters: Dictionary of scan parameters (range, width, etc.)
        """
        super().__init__(message_type="tfr_radarDataRequest", request_uuid=request_uuid, **kwargs)
        self.data_type = data_type
        self.scan_parameters = scan_parameters

class tfr_radarElevationDataRequest(BaseMessage):
    def __init__(self, request_uuid: str = None, range_start: float = 0.0, range_end: float = 10000.0, 
                 scan_width: float = 1000.0, resolution: float = 10.0, scan_parameters: dict = None, 
                 message_header: str = None, sending_system: str = None, destination: str = None, **kwargs):
        """
        Initialize elevation data request message.
        
        Args:
            request_uuid: Unique identifier for this request
            range_start: Start range in meters
            range_end: End range in meters
            scan_width: Width of terrain scan in meters
            resolution: Resolution of scan in meters
            scan_parameters: Dictionary of scan parameters (overrides individual parameters if provided)
            message_header: Message header
            sending_system: Sending system name
            destination: Destination system name
        """
        # Generate UUID if not provided
        if request_uuid is None:
            import uuid
            request_uuid = str(uuid.uuid4())
            
        super().__init__(message_type="tfr_radarElevationDataRequest", request_uuid=request_uuid, **kwargs)
        
        # Store message routing information
        self.message_header = message_header
        self.sending_system = sending_system 
        self.destination = destination
        
        # Process scan parameters if provided
        if scan_parameters and isinstance(scan_parameters, dict):
            # Extract parameters from scan_parameters
            self.range_start = scan_parameters.get('range_start', range_start)
            self.range_end = scan_parameters.get('range_end', range_end)
            self.scan_width = scan_parameters.get('scan_width', scan_width)
            self.resolution = scan_parameters.get('resolution', resolution)
            
            # Store the original scan parameters
            self.scan_parameters = scan_parameters
        else:
            # Use directly provided parameters
            self.range_start = range_start
            self.range_end = range_end
            self.scan_width = scan_width
            self.resolution = resolution
            
            # Create scan_parameters from the individual parameters
            self.scan_parameters = {
                'range_start': range_start,
                'range_end': range_end,
                'scan_width': scan_width,
                'resolution': resolution
            }

class tfr_radarDataResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, data_type: str, data: dict, **kwargs):
        """
        Initialize data response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            data_type: Type of data being returned
            data: Dictionary containing the requested data
        """
        super().__init__(message_type="tfr_radarDataResponse", request_uuid=request_uuid, 
                        response_uuid=response_uuid, **kwargs)
        self.data_type = data_type
        self.data = data

# Register message types
register_message_type("tfr_radarData", tfr_radarData)
register_message_type("tfr_radarElevationProfile", tfr_radarElevationProfile)
register_message_type("tfr_radarTerrainWarning", tfr_radarTerrainWarning)
register_message_type("tfr_radarDataRequest", tfr_radarDataRequest)
register_message_type("tfr_radarDataResponse", tfr_radarDataResponse)
register_message_type("tfr_radarElevationDataRequest", tfr_radarElevationDataRequest)
