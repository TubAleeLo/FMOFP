"""
Weather Radar Data Message Definitions

Contains radar-local implementations of weather data messages to maintain proper system boundaries.
Defines data classes and message types for:
- Precipitation data
- VIL (Vertically Integrated Liquid) data
- Request and response message formats
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import uuid
import time

from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import (
    RadarBaseMessage,
    register_message_type
)

# Import message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    COMMAND_TYPE_PRECIPITATION_DATA,
    COMMAND_TYPE_VIL_DATA,
    COMMAND_TYPE_DATA_REQUEST
)

@dataclass
class PrecipitationData:
    """Precipitation data structure for weather radar"""
    position: Tuple[float, float] = (0.0, 0.0)  # (x, y) in nm
    type: str = "unknown"  # rain, snow, hail, etc.
    rate: float = 0.0  # mm/hr
    intensity: float = 0.0  # 0-1 scale
    show_values: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique identifier
    timestamp: float = field(default_factory=time.time)  # Timestamp of data
    additional_info: Optional[Dict[str, Any]] = field(default_factory=dict)  # Additional metadata

    def to_data_words(self) -> List[str]:
        """Convert to two data words for 1553B message"""
        # Word 1: Position [X: 8 bits][Y: 8 bits]
        x_scaled = min(255, int(self.position[0] * 10))  # Scale to 0.1 nm resolution
        y_scaled = min(255, int(self.position[1] * 10))
        word1 = format((x_scaled << 8) | y_scaled, '016b')
        
        # Word 2: [Type: 2 bits][Rate: 7 bits][Intensity: 6 bits][Show: 1 bit]
        type_bits = {'rain': 0b00, 'snow': 0b01, 'hail': 0b10, 'mixed': 0b11}
        type_val = type_bits.get(self.type, 0b00)
        rate_val = min(127, round(self.rate / 2.0))  # 7 bits for rate (each bit = 2 mm/hr)
        intensity_val = min(63, round(self.intensity * 63))  # 6 bits for intensity (0-1 mapped to 0-63)
        show_bit = 1 if self.show_values else 0
        
        word2 = format(
            (type_val << 14) | (rate_val << 7) | (intensity_val << 1) | show_bit,
            '016b'
        )
        
        return [word1, word2]

    @classmethod
    def from_data_words(cls, data_words: List[str]) -> 'PrecipitationData':
        """Create PrecipitationData object from 1553B data words"""
        if len(data_words) != 2:
            raise ValueError(f"Expected 2 data words, got {len(data_words)}")
            
        # Word 1: Position [X: 8 bits][Y: 8 bits]
        word1 = int(data_words[0], 2)  # Convert binary string to integer
        x_scaled = (word1 >> 8) & 0xFF  # Extract X from top 8 bits
        y_scaled = word1 & 0xFF         # Extract Y from bottom 8 bits
        
        # Convert scaled position back to nm
        x = x_scaled / 10.0  # Convert from 0.1 nm resolution
        y = y_scaled / 10.0
        
        # Word 2: [Type: 2 bits][Rate: 7 bits][Intensity: 6 bits][Show: 1 bit]
        word2 = int(data_words[1], 2)  # Convert binary string to integer
        type_val = (word2 >> 14) & 0b11      # Extract type from top 2 bits
        rate_val = (word2 >> 7) & 0x7F       # Extract rate from next 7 bits
        intensity_val = (word2 >> 1) & 0x3F   # Extract intensity from next 6 bits
        show_bit = word2 & 0x1               # Extract show from last bit
        
        # Convert type bits back to string
        type_map = {0b00: 'rain', 0b01: 'snow', 0b10: 'hail', 0b11: 'mixed'}
        precip_type = type_map[type_val]
        
        # Convert scaled values back to original units
        rate = rate_val * 2.0        # Each bit = 2 mm/hr
        intensity = intensity_val / 63.0  # Map 0-63 back to 0-1
        show_values = bool(show_bit)
        
        return cls(
            position=(x, y),
            type=precip_type,
            rate=rate,
            intensity=intensity,
            show_values=show_values
        )

@dataclass
class WeatherRadarVILData:
    """VIL (Vertically Integrated Liquid) data structure for weather radar"""
    position: Tuple[float, float] = (0.0, 0.0)  # (x, y) in nm
    value: float = 0.0  # kg/m²
    layer_count: int = 0  # Number of layers integrated
    intensity: float = 0.0  # 0-1 scale
    show_values: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique identifier
    timestamp: float = field(default_factory=time.time)  # Timestamp of data
    additional_info: Optional[Dict[str, Any]] = field(default_factory=dict)  # Additional metadata

    def to_data_words(self) -> List[str]:
        """Convert to two data words for 1553B message"""
        # Word 1: Position [X: 8 bits][Y: 8 bits]
        x_scaled = min(255, int(self.position[0] * 10))  # Scale to 0.1 nm resolution
        y_scaled = min(255, int(self.position[1] * 10))
        word1 = format((x_scaled << 8) | y_scaled, '016b')
        
        # Word 2: [Value: 7 bits][Layer Count: 4 bits][Intensity: 4 bits][Show: 1 bit]
        value_val = min(127, round(self.value * 2))  # 7 bits for value (0.5 kg/m² resolution)
        layer_val = min(15, self.layer_count)  # 4 bits for layer count (max 15)
        intensity_val = min(15, round(self.intensity * 15))  # 4 bits for intensity (0-1 mapped to 0-15)
        show_bit = 1 if self.show_values else 0
        
        # Pack word2 differently from precipitation data to avoid confusion:
        # [Value: 7 bits][Layer: 4 bits][Intensity: 4 bits][Show: 1 bit]
        word2 = format(
            (value_val << 9) |           # Value in top 7 bits
            (layer_val << 5) |           # Layer count in next 4 bits
            (intensity_val << 1) |       # Intensity in next 4 bits
            show_bit,                    # Show bit in last bit
            '016b'
        )
        
        return [word1, word2]

    @classmethod
    def from_data_words(cls, data_words: List[str]) -> 'WeatherRadarVILData':
        """Create WeatherRadarVILData object from 1553B data words"""
        if len(data_words) != 2:
            raise ValueError(f"Expected 2 data words, got {len(data_words)}")
            
        # Word 1: Position [X: 8 bits][Y: 8 bits]
        word1 = int(data_words[0], 2)  # Convert binary string to integer
        x_scaled = (word1 >> 8) & 0xFF  # Extract X from top 8 bits
        y_scaled = word1 & 0xFF         # Extract Y from bottom 8 bits
        
        # Convert scaled position back to nm
        x = x_scaled / 10.0  # Convert from 0.1 nm resolution
        y = y_scaled / 10.0
        
        # Word 2: [Value: 7 bits][Layer Count: 4 bits][Intensity: 4 bits][Show: 1 bit]
        word2 = int(data_words[1], 2)  # Convert binary string to integer
        value_val = (word2 >> 9) & 0x7F      # Extract value from top 7 bits
        layer_val = (word2 >> 5) & 0xF       # Extract layer count from next 4 bits
        intensity_val = (word2 >> 1) & 0xF    # Extract intensity from next 4 bits
        show_bit = word2 & 0x1               # Extract show from last bit
        
        # Convert scaled values back to original units
        value = value_val / 2.0        # Each bit = 0.5 kg/m²
        intensity = intensity_val / 15.0  # Map 0-15 back to 0-1
        show_values = bool(show_bit)
        
        return cls(
            position=(x, y),
            value=value,
            layer_count=layer_val,
            intensity=intensity,
            show_values=show_values
        )

class WeatherRadarPrecipitationRequest(RadarBaseMessage):
    """Precipitation data request message for weather radar"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_id: str = None, 
                 scan_parameters: Dict[str, Any] = None, **kwargs):
        """Initialize precipitation data request message"""
        # Set up standard values for message fields
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type=WEATHER_RADAR_PRECIPITATION_REQUEST,
            command_type=COMMAND_TYPE_DATA_REQUEST,
            command_name="WEATHER_RADAR_PRECIPITATION_DATA",
            request_id=request_id or str(uuid.uuid4()),
            **kwargs
        )
        
        # Set specific fields for this message type
        self.scan_parameters = scan_parameters or {}

    def validate(self):
        """Validate precipitation request message"""
        super().validate()
        if not isinstance(self.scan_parameters, dict):
            raise ValueError("scan_parameters must be a dictionary")

class WeatherRadarPrecipitationResponse(RadarBaseMessage):
    """Precipitation data response message for weather radar"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_id: str, 
                 response_uuid: str = None, precipitation_data: List[PrecipitationData] = None, **kwargs):
        """Initialize precipitation data response message"""
        # Remove command_type and command_name from kwargs if they exist to prevent duplicate parameters
        kwargs_copy = kwargs.copy()
        if 'command_type' in kwargs_copy:
            del kwargs_copy['command_type']
        if 'command_name' in kwargs_copy:
            del kwargs_copy['command_name']
            
        # Set up standard values for message fields
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type=WEATHER_RADAR_PRECIPITATION_RESPONSE,
            command_type=COMMAND_TYPE_PRECIPITATION_DATA,
            command_name="WEATHER_RADAR_PRECIPITATION_DATA",
            request_id=request_id,
            response_uuid=response_uuid or str(uuid.uuid4()),
            **kwargs_copy
        )
        
        # Set specific fields for this message type
        self.precipitation_data = precipitation_data or []
        
        # Add additional metadata specific to precipitation data
        if not self.metadata:
            self.metadata = {}
        self.metadata['precipitation_message'] = True
        self.metadata['data_type'] = 'precipitation'

    def validate(self):
        """Validate precipitation response message"""
        super().validate()
        if not isinstance(self.precipitation_data, list):
            raise ValueError("precipitation_data must be a list")
        for data in self.precipitation_data:
            if not isinstance(data, PrecipitationData):
                raise ValueError("All items in precipitation_data must be PrecipitationData objects")

class WeatherRadarVILRequest(RadarBaseMessage):
    """VIL data request message for weather radar"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_id: str = None, 
                 scan_parameters: Dict[str, Any] = None, **kwargs):
        """Initialize VIL data request message"""
        # Set up standard values for message fields
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type=WEATHER_RADAR_VIL_REQUEST,
            command_type=COMMAND_TYPE_DATA_REQUEST,
            command_name="WEATHER_RADAR_VIL_DATA",
            request_id=request_id or str(uuid.uuid4()),
            **kwargs
        )
        
        # Set specific fields for this message type
        self.scan_parameters = scan_parameters or {}

    def validate(self):
        """Validate VIL request message"""
        super().validate()
        if not isinstance(self.scan_parameters, dict):
            raise ValueError("scan_parameters must be a dictionary")

class WeatherRadarVILResponse(RadarBaseMessage):
    """VIL data response message for weather radar"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_id: str, 
                 response_uuid: str = None, vil_data: List[WeatherRadarVILData] = None, **kwargs):
        """Initialize VIL data response message"""
        # Remove command_type and command_name from kwargs if they exist to prevent duplicate parameters
        kwargs_copy = kwargs.copy()
        if 'command_type' in kwargs_copy:
            del kwargs_copy['command_type']
        if 'command_name' in kwargs_copy:
            del kwargs_copy['command_name']
            
        # Set up standard values for message fields
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type=WEATHER_RADAR_VIL_RESPONSE,
            command_type=COMMAND_TYPE_VIL_DATA,
            command_name="WEATHER_RADAR_VIL_DATA",
            request_id=request_id,
            response_uuid=response_uuid or str(uuid.uuid4()),
            **kwargs_copy
        )
        
        # Set specific fields for this message type
        self.vil_data = vil_data or []
        
        # Add additional metadata specific to VIL data
        if not self.metadata:
            self.metadata = {}
        self.metadata['vil_message'] = True
        self.metadata['data_type'] = 'vil'

    def validate(self):
        """Validate VIL response message"""
        super().validate()
        if not isinstance(self.vil_data, list):
            raise ValueError("vil_data must be a list")
        for data in self.vil_data:
            if not isinstance(data, WeatherRadarVILData):
                raise ValueError("All items in vil_data must be WeatherRadarVILData objects")

# Register message types for factory creation
register_message_type(WEATHER_RADAR_PRECIPITATION_REQUEST, WeatherRadarPrecipitationRequest)
register_message_type(WEATHER_RADAR_PRECIPITATION_RESPONSE, WeatherRadarPrecipitationResponse)
register_message_type(WEATHER_RADAR_VIL_REQUEST, WeatherRadarVILRequest)
register_message_type(WEATHER_RADAR_VIL_RESPONSE, WeatherRadarVILResponse)
