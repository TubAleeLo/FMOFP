from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarHeartbeat(BaseMessage):
    heartbeat_info: str = ""

register_message_type("weather_radarHeartbeat", weather_radarHeartbeat)