from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarInitialization(BaseMessage):
    init_parameters: dict = None

register_message_type("weather_radarInitialization", weather_radarInitialization)