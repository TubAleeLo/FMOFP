"""
Weather radar echo top data message configuration

Contains Echo Top data structures for displaying cloud top heights.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import uuid
import time
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class WeatherRadarEchoTopData:
    """Echo top data structure showing cloud top heights"""
    position: Tuple[float, float] = (0.0, 0.0)  # (x, y) in nm
    height: float = 0.0  # in hundreds of feet
    intensity: float = 0.0  # 0-1 scale
    show_values: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique identifier
    timestamp: float = field(default_factory=time.time)  # Timestamp of data
    additional_info: Optional[Dict[str, Any]] = field(default_factory=dict)  # Additional metadata

    def to_data_words(self) -> List[str]:
        """Convert to data words for 1553B message"""
        # Word 1: Position [X: 8 bits][Y: 8 bits] - same as VIL/precipitation
        x_scaled = min(255, int(self.position[0] * 10))  # Scale to 0.1 nm resolution
        y_scaled = min(255, int(self.position[1] * 10))
        word1 = format((x_scaled << 8) | y_scaled, '016b')
        
        # Word 2: [Height: 10 bits][Intensity: 5 bits][Show: 1 bit]
        height_val = min(1023, int(self.height * 10))  # 10 bits, resolution of 0.1 (0-102.3 thousand feet)
        intensity_val = min(31, round(self.intensity * 31))  # 5 bits for intensity
        show_bit = 1 if self.show_values else 0
        
        word2 = format(
            (height_val << 6) | (intensity_val << 1) | show_bit,
            '016b'
        )
        
        return [word1, word2]

    @classmethod
    def from_data_words(cls, data_words: List[str]) -> 'WeatherRadarEchoTopData':
        """Create object from 1553B data words"""
        if len(data_words) != 2:
            raise ValueError(f"Expected 2 data words, got {len(data_words)}")
            
        # Word 1: Position [X: 8 bits][Y: 8 bits]
        word1 = int(data_words[0], 2)  # Convert binary string to integer
        x_scaled = (word1 >> 8) & 0xFF  # Extract X from top 8 bits
        y_scaled = word1 & 0xFF         # Extract Y from bottom 8 bits
        
        # Convert scaled position back to nm
        x = x_scaled / 10.0  # Convert from 0.1 nm resolution
        y = y_scaled / 10.0
        
        # Word 2: [Height: 10 bits][Intensity: 5 bits][Show: 1 bit]
        word2 = int(data_words[1], 2)  # Convert binary string to integer
        height_val = (word2 >> 6) & 0x3FF      # Extract height from top 10 bits
        intensity_val = (word2 >> 1) & 0x1F    # Extract intensity from next 5 bits
        show_bit = word2 & 0x1               # Extract show from last bit
        
        # Convert scaled values back to original units
        height = height_val / 10.0        # Each bit = 0.1 thousand feet
        intensity = intensity_val / 31.0  # Map 0-31 back to 0-1
        show_values = bool(show_bit)
        
        return cls(
            position=(x, y),
            height=height,
            intensity=intensity,
            show_values=show_values
        )

class weather_radarEchoTopRequest(BaseMessage):
    """Echo top data request message"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_uuid: str = None, scan_parameters: Dict = None, **kwargs):
        """Initialize echo top data request message.
        
        Args:
            message_header: Message header identifier
            sending_system: Name of sending system
            destination: Name of destination system
            request_uuid: Unique identifier for this request
            scan_parameters: Dictionary of scan parameters
        """
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type="weather_radarEchoTopRequest",
            command_name="WEATHER_RADAR_ECHO_TOP_DATA",  # Add command name
            **kwargs
        )
        self.request_uuid = request_uuid
        self.scan_parameters = scan_parameters or {}

    def validate(self):
        """Validate echo top request message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not isinstance(self.scan_parameters, dict):
            raise ValueError("scan_parameters must be a dictionary")

class weather_radarEchoTopResponse(BaseMessage):
    """Echo top data response message"""
    def __init__(self, message_header: str, sending_system: str, destination: str, request_uuid: str, 
                 response_uuid: str = None, echo_top_data: List[WeatherRadarEchoTopData] = None, **kwargs):
        """Initialize echo top data response message.
        
        Args:
            message_header: Message header identifier
            sending_system: Name of sending system
            destination: Name of destination system
            request_uuid: UUID of the original request
            response_uuid: Unique identifier for this response
            echo_top_data: List of echo top data objects
        """
        super().__init__(
            message_header=message_header,
            sending_system=sending_system,
            destination=destination,
            message_type="weather_radarEchoTopResponse",
            command_name="WEATHER_RADAR_ECHO_TOP_DATA",  # Add command name
            **kwargs
        )
        self.request_uuid = request_uuid
        self.response_uuid = response_uuid
        self.echo_top_data = echo_top_data or []

    def validate(self):
        """Validate echo top response message"""
        super().validate()
        if not self.request_uuid:
            raise ValueError("request_uuid is required")
        if not self.response_uuid:
            raise ValueError("response_uuid is required")
        if not isinstance(self.echo_top_data, list):
            raise ValueError("echo_top_data must be a list")
        for data in self.echo_top_data:
            if not isinstance(data, WeatherRadarEchoTopData):
                raise ValueError("All items in echo_top_data must be WeatherRadarEchoTopData objects")

# Register message types
register_message_type("weather_radarEchoTopRequest", weather_radarEchoTopRequest)
register_message_type("weather_radarEchoTopResponse", weather_radarEchoTopResponse)
