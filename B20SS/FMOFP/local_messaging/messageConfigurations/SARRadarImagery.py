from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage  
from dataclasses import dataclass, field

@dataclass
class sar_radarImagery(BaseMessage):
    image_data: bytes = b""
    corner_points: list[tuple[float, float]] = field(default_factory=list)  
    resolution: float = 0
    