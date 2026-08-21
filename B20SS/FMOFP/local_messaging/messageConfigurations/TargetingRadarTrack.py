from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage
from dataclasses import dataclass

@dataclass
class targeting_radarTrack(BaseMessage):
    track_id: int = 0
    position: tuple[float, float, float] = (0, 0, 0)
    velocity: tuple[float, float, float] = (0, 0, 0)
    identity: str = ""
    classification: str = ""
    