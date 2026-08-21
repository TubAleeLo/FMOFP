from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage
from dataclasses import dataclass

@dataclass 
class tfr_radarElevation(BaseMessage):
    distance: float = 0
    elevation: float = 0
    