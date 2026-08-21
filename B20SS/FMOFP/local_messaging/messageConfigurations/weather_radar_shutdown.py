from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarShutdown(BaseMessage):
    shutdown_parameters: dict = None

register_message_type("weather_radarShutdown", weather_radarShutdown)