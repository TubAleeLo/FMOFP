"""
Weather Radar VIL (Vertically Integrated Liquid) Data Message Type

Defines message type for weather radar VIL data communication.
"""
from dataclasses import dataclass, field
import time
from typing import Dict, Any
import FMOFP.Utils.common.fetching as fetching
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage

@dataclass
class WeatherRadarVILData(BaseMessage):
    """VIL (Vertically Integrated Liquid) data from weather radar"""
    message_header: str = "weather_data"
    destination: str = "weather_radar"
    message_type: str = "vil_data"
    sending_system: str = "RadarMessageHandler"
    
    # Required fields
    position: tuple = field(default=(0.0, 0.0))  # (x, y) in nm
    value: float = field(default=0.0)  # VIL value in kg/m²
    layer_count: int = field(default=0)  # Number of layers
    intensity: float = field(default=0.0)  # 0-1 scale
    show_values: bool = field(default=False)  # Display flag
    
    # Optional fields with defaults
    request_id: str = field(default_factory=lambda: str(time.time()))
    timestamp: float = field(default_factory=time.time)
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert VIL data to dictionary format"""
        base_dict = super().to_dict()
        base_dict.update({
            "position": self.position,
            "value": self.value,
            "layer_count": self.layer_count,
            "intensity": self.intensity,
            "show_values": self.show_values,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "additional_info": self.additional_info
        })
        return base_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherRadarVILData':
        """Create VIL data from dictionary"""
        return cls(
            message_header=data.get("message_header", "weather_data"),
            destination=data.get("destination", "weather_radar"),
            message_type=data.get("message_type", "vil_data"),
            sending_system=data.get("sending_system", "RadarMessageHandler"),
            position=data.get("position", (0.0, 0.0)),
            value=data.get("value", 0.0),
            layer_count=data.get("layer_count", 0),
            intensity=data.get("intensity", 0.0),
            show_values=data.get("show_values", False),
            request_id=data.get("request_id", str(time.time())),
            timestamp=data.get("timestamp", time.time()),
            additional_info=data.get("additional_info", {})
        )
