"""
Weather Radar Echo Top Data Message Type

Defines message type for weather radar echo top data communication.
"""
from dataclasses import dataclass, field
import time
from typing import Dict, Any
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage

@dataclass
class WeatherRadarEchoTopData(BaseMessage):
    """Echo top data from weather radar"""
    message_header: str = "weather_data"
    destination: str = "weather_radar"
    message_type: str = "echo_top_data"
    sending_system: str = "RadarMessageHandler"
    echo_top_data: Dict[str, Any] = field(default_factory=dict)  # Echo top measurements
    data_uuid: str = field(default_factory=lambda: str(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert echo top data to dictionary format"""
        base_dict = super().to_dict()
        base_dict.update({
            "echo_top_data": self.echo_top_data,
            "data_uuid": self.data_uuid
        })
        return base_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherRadarEchoTopData':
        """Create echo top data from dictionary"""
        return cls(
            message_header=data.get("message_header", "weather_data"),
            destination=data.get("destination", "weather_radar"),
            message_type=data.get("message_type", "echo_top_data"),
            sending_system=data.get("sending_system", "RadarMessageHandler"),
            echo_top_data=data.get("echo_top_data", {}),
            data_uuid=data.get("data_uuid", str(time.time()))
        )
