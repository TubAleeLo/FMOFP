"""
Weather Radar Turbulence Data Message Type

Defines message type for weather radar turbulence data communication.
"""
from dataclasses import dataclass, field
import time
from typing import Dict, Any
import FMOFP.Utils.common.fetching as fetching
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage

@dataclass
class WeatherRadarTurbulenceData(BaseMessage):
    """Turbulence data from weather radar"""
    message_header: str = "weather_data"
    destination: str = "weather_radar"
    message_type: str = "turbulence_data"
    sending_system: str = "RadarMessageHandler"
    turbulence_data: Dict[str, Any] = field(default_factory=dict)  # Turbulence measurements
    data_uuid: str = field(default_factory=lambda: str(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert turbulence data to dictionary format"""
        base_dict = super().to_dict()
        base_dict.update({
            "turbulence_data": self.turbulence_data,
            "data_uuid": self.data_uuid
        })
        return base_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherRadarTurbulenceData':
        """Create turbulence data from dictionary"""
        return cls(
            message_header=data.get("message_header", "weather_data"),
            destination=data.get("destination", "weather_radar"),
            message_type=data.get("message_type", "turbulence_data"),
            sending_system=data.get("sending_system", "RadarMessageHandler"),
            turbulence_data=data.get("turbulence_data", {}),
            data_uuid=data.get("data_uuid", str(time.time()))
        )
