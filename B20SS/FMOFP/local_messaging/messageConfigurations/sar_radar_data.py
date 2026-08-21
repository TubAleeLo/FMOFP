"""
SAR Radar Data Messages

Defines data message types for SAR radar communication.
"""

from .base_message import BaseMessage, register_message_type
from typing import List, Tuple, Dict

class sar_radarData(BaseMessage):
    def __init__(self, message_header, sending_system, destination, message_type, data, **kwargs):
        super().__init__(message_type="sar_radarData", **kwargs)
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        self.message_type = message_type
        self.data = data

class sar_radarImagery(BaseMessage):
    def __init__(self, data_uuid: str, image_data: bytes, corner_points: List[Tuple[float, float]], 
                 resolution: float, metadata: Dict = None, **kwargs):
        """
        Initialize SAR imagery data message.
        
        Args:
            data_uuid: Unique identifier for this data message
            image_data: Raw SAR image data bytes
            corner_points: List of (lat, lon) tuples defining image corners
            resolution: Ground resolution in meters per pixel
            metadata: Optional metadata about the image
        """
        super().__init__(message_type="sar_radarImagery", data_uuid=data_uuid, **kwargs)
        self.image_data = image_data
        self.corner_points = corner_points
        self.resolution = resolution
        self.metadata = metadata or {}

class sar_radarStripMap(BaseMessage):
    def __init__(self, data_uuid: str, strip_data: bytes, start_coord: Tuple[float, float],
                 end_coord: Tuple[float, float], width: float, resolution: float, **kwargs):
        """
        Initialize strip map data message.
        
        Args:
            data_uuid: Unique identifier for this data message
            strip_data: Raw strip map data bytes
            start_coord: (lat, lon) of strip start
            end_coord: (lat, lon) of strip end
            width: Width of strip in meters
            resolution: Ground resolution in meters per pixel
        """
        super().__init__(message_type="sar_radarStripMap", data_uuid=data_uuid, **kwargs)
        self.strip_data = strip_data
        self.start_coord = start_coord
        self.end_coord = end_coord
        self.width = width
        self.resolution = resolution

class sar_radarSpotlight(BaseMessage):
    def __init__(self, data_uuid: str, spotlight_data: bytes, center_coord: Tuple[float, float],
                 radius: float, resolution: float, integration_time: float, **kwargs):
        """
        Initialize spotlight mode data message.
        
        Args:
            data_uuid: Unique identifier for this data message
            spotlight_data: Raw spotlight mode data bytes
            center_coord: (lat, lon) of spotlight center
            radius: Radius of spotlight area in meters
            resolution: Ground resolution in meters per pixel
            integration_time: Integration time in seconds
        """
        super().__init__(message_type="sar_radarSpotlight", data_uuid=data_uuid, **kwargs)
        self.spotlight_data = spotlight_data
        self.center_coord = center_coord
        self.radius = radius
        self.resolution = resolution
        self.integration_time = integration_time

class sar_radarScanSAR(BaseMessage):
    def __init__(self, data_uuid: str, scan_data: bytes, swath_coords: List[Tuple[float, float]],
                 swath_width: float, resolution: float, **kwargs):
        """
        Initialize ScanSAR mode data message.
        
        Args:
            data_uuid: Unique identifier for this data message
            scan_data: Raw ScanSAR data bytes
            swath_coords: List of (lat, lon) coordinates defining the swath
            swath_width: Width of each swath in meters
            resolution: Ground resolution in meters per pixel
        """
        super().__init__(message_type="sar_radarScanSAR", data_uuid=data_uuid, **kwargs)
        self.scan_data = scan_data
        self.swath_coords = swath_coords
        self.swath_width = swath_width
        self.resolution = resolution

class sar_radarDataRequest(BaseMessage):
    def __init__(self, request_uuid: str, data_type: str, scan_parameters: Dict, **kwargs):
        """
        Initialize data request message.
        
        Args:
            request_uuid: Unique identifier for this request
            data_type: Type of data requested ("STRIPMAP", "SPOTLIGHT", "SCANSAR")
            scan_parameters: Dictionary of scan parameters
        """
        super().__init__(message_type="sar_radarDataRequest", request_uuid=request_uuid, **kwargs)
        self.data_type = data_type
        self.scan_parameters = scan_parameters

class sar_radarImageryRequest(BaseMessage):
    def __init__(self, request_uuid: str = None, area: Dict = None, resolution: float = 1.0, 
                 mode: str = "STRIPMAP", scan_parameters: Dict = None, 
                 message_header: str = None, sending_system: str = None, 
                 destination: str = None, **kwargs):
        """
        Initialize SAR imagery request message.
        
        Args:
            request_uuid: Unique identifier for this request
            area: Dictionary with corner coordinates or center point and radius
            resolution: Desired resolution in meters per pixel
            mode: SAR mode ("STRIPMAP", "SPOTLIGHT", "SCANSAR")
            scan_parameters: Dictionary of scan parameters (overrides individual parameters if provided)
            message_header: Message header
            sending_system: Sending system name
            destination: Destination system name
        """
        # Generate UUID if not provided
        if request_uuid is None:
            import uuid
            request_uuid = str(uuid.uuid4())
            
        super().__init__(message_type="sar_radarImageryRequest", request_uuid=request_uuid, **kwargs)
        
        # Store message routing information
        self.message_header = message_header
        self.sending_system = sending_system
        self.destination = destination
        
        # Default area if none provided
        default_area = {"center": (0.0, 0.0), "radius": 5000.0}
        
        # Process scan parameters if provided
        if scan_parameters and isinstance(scan_parameters, dict):
            # Extract parameters from scan_parameters
            self.area = scan_parameters.get('area', area or default_area)
            self.resolution = scan_parameters.get('resolution', resolution)
            self.mode = scan_parameters.get('mode', mode)
            
            # Store the original scan parameters
            self.scan_parameters = scan_parameters
        else:
            # Use directly provided parameters
            self.area = area or default_area
            self.resolution = resolution
            self.mode = mode
            
            # Create scan_parameters from the individual parameters
            self.scan_parameters = {
                'area': self.area,
                'resolution': resolution,
                'mode': mode
            }

class sar_radarDataResponse(BaseMessage):
    def __init__(self, request_uuid: str, response_uuid: str, data_type: str, data: Dict, **kwargs):
        """
        Initialize data response message.
        
        Args:
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            data_type: Type of data being returned
            data: Dictionary containing the requested data
        """
        super().__init__(message_type="sar_radarDataResponse", request_uuid=request_uuid,
                        response_uuid=response_uuid, **kwargs)
        self.data_type = data_type
        self.data = data

# Register message types
register_message_type("sar_radarData", sar_radarData)
register_message_type("sar_radarImagery", sar_radarImagery)
register_message_type("sar_radarStripMap", sar_radarStripMap)
register_message_type("sar_radarSpotlight", sar_radarSpotlight)
register_message_type("sar_radarScanSAR", sar_radarScanSAR)
register_message_type("sar_radarDataRequest", sar_radarDataRequest)
register_message_type("sar_radarDataResponse", sar_radarDataResponse)
register_message_type("sar_radarImageryRequest", sar_radarImageryRequest)
