"""
Precipitation message type definitions
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class PrecipitationMessage:
    """Base class for precipitation messages"""
    request_id: str
    message_type: str
    command_word: str
    data: Any

@dataclass
class PrecipitationDataMessage(PrecipitationMessage):
    """Message containing precipitation data"""
    position: tuple
    precip_type: str
    rate: float
    intensity: float
    show_values: bool
    additional_info: Optional[Dict[str, Any]] = None

@dataclass
class PrecipitationStatusMessage(PrecipitationMessage):
    """Message containing precipitation status"""
    status: str
    timestamp: float
    additional_info: Optional[Dict[str, Any]] = None
