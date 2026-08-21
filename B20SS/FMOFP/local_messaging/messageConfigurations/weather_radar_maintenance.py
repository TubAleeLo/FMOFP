from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type

@dataclass
class weather_radarMaintenance(BaseMessage):
    maintenance_info: str = ""

register_message_type("weather_radarMaintenance", weather_radarMaintenance)