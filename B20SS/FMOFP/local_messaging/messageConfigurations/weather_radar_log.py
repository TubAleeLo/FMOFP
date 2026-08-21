from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarLog(BaseMessage):
    log_message: str = ""

register_message_type("weather_radarLog", weather_radarLog)