"""
Display Data Message Configurations

Defines message formats for display data communication.
These messages handle the data needed to update display content.
"""

from typing import Dict, Any
from .base_message import BaseMessage
from ...Interfaces.userInterface.displays.base_display import DisplayType

class DisplayDataMessage(BaseMessage):
    """Base class for display data messages."""
    MESSAGE_TYPE = "DISPLAY_DATA"
    
    def __init__(self, display_type: str):
        super().__init__()
        self.message_type = self.MESSAGE_TYPE
        self.display_type = DisplayType[display_type.upper()]

    def validate(self) -> bool:
        """Validate base message attributes."""
        return super().validate() and bool(self.display_type)

class DisplayDataRequest(DisplayDataMessage):
    """Request for display data update."""
    def __init__(self, display_type: str, data_type: str):
        super().__init__(display_type)
        self.data_type = data_type
        self.request_type = "DATA_REQUEST"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Request type (8 bits): 00000011 for data request
        - Display type (8 bits): Enum value
        - Data type (8 bits): Type identifier
        """
        request = "00000011"  # Data request
        display_bits = format(self.display_type.value, '08b')
        data_type_bits = format(self._get_data_type_code(), '08b')
        return request + display_bits + data_type_bits

    def _get_data_type_code(self) -> int:
        """Convert data type string to code."""
        type_map = {
            'navigation': 1,
            'engine': 2,
            'radar': 3,
            'tactical': 4,
            'stores': 5,
            'system': 6
        }
        return type_map.get(self.data_type.lower(), 0)

class DisplayDataUpdate(DisplayDataMessage):
    """Data update for display."""
    def __init__(self, display_type: str, data_type: str, data: Dict[str, Any]):
        super().__init__(display_type)
        self.data_type = data_type
        self.data = data
        self.update_type = "DATA_UPDATE"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Update type (8 bits): 00000100 for data update
        - Display type (8 bits): Enum value
        - Data type (8 bits): Type identifier
        """
        update = "00000100"  # Data update
        display_bits = format(self.display_type.value, '08b')
        data_type_bits = format(self._get_data_type_code(), '08b')
        return update + display_bits + data_type_bits

    def _get_data_type_code(self) -> int:
        """Convert data type string to code."""
        type_map = {
            'navigation': 1,
            'engine': 2,
            'radar': 3,
            'tactical': 4,
            'stores': 5,
            'system': 6
        }
        return type_map.get(self.data_type.lower(), 0)

class DisplayDataSubscription(DisplayDataMessage):
    """Subscribe/unsubscribe to display data updates."""
    def __init__(self, display_type: str, data_type: str, subscribe: bool = True):
        super().__init__(display_type)
        self.data_type = data_type
        self.subscribe = subscribe
        self.subscription_type = "DATA_SUBSCRIPTION"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Subscription type (8 bits): 00000101 for subscription
        - Display type (8 bits): Enum value
        - Data type (8 bits): Type identifier + subscription flag
        """
        subscription = "00000101"  # Subscription
        display_bits = format(self.display_type.value, '08b')
        data_type_code = self._get_data_type_code()
        if self.subscribe:
            data_type_code |= 0x80  # Set high bit for subscribe
        data_type_bits = format(data_type_code, '08b')
        return subscription + display_bits + data_type_bits

    def _get_data_type_code(self) -> int:
        """Convert data type string to code."""
        type_map = {
            'navigation': 1,
            'engine': 2,
            'radar': 3,
            'tactical': 4,
            'stores': 5,
            'system': 6
        }
        return type_map.get(self.data_type.lower(), 0)

def create_display_data_message(message_type: str, **kwargs) -> DisplayDataMessage:
    """Factory function for creating display data messages."""
    message_map = {
        "data_request": DisplayDataRequest,
        "data_update": DisplayDataUpdate,
        "data_subscription": DisplayDataSubscription
    }
    
    if message_type not in message_map:
        raise ValueError(f"Unknown message type: {message_type}")
        
    message_class = message_map[message_type]
    return message_class(**kwargs)
