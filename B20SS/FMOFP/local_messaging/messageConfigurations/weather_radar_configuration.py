from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarStatus(BaseMessage):
    status: str = ""

register_message_type("weather_radarStatus", weather_radarStatus)