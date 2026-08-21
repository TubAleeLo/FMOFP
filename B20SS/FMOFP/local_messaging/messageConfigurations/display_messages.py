"""
Display Message Configurations

Defines message formats for display system commands and responses.
Follows similar pattern to radar messages but adapted for display operations.
"""

from typing import Dict, Any
from .base_message import BaseMessage
from ...Interfaces.userInterface.displays.base_display import DisplayType, DisplayMode

class DisplayMessage(BaseMessage):
    """Base class for all display messages."""
    MESSAGE_TYPE = "DISPLAY"
    
    def __init__(self):
        super().__init__()
        self.message_type = self.MESSAGE_TYPE

    def validate(self) -> bool:
        """Validate base message attributes."""
        return bool(self.message_type)

class DisplayCommand(DisplayMessage):
    """Base class for display command messages."""
    def __init__(self, display_type: str):
        super().__init__()
        self.display_type = DisplayType[display_type.upper()]
        self.command_type = None

    def validate(self) -> bool:
        """Validate command attributes."""
        return super().validate() and bool(self.display_type) and bool(self.command_type)

class ShowDisplayCommand(DisplayCommand):
    """Command to show a specific display."""
    def __init__(self, display_type: str):
        super().__init__(display_type)
        self.command_type = "SHOW"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Command type (8 bits): 00000001 for show display
        - Display type (8 bits): Enum value
        - Padding (8 bits): Zeros
        """
        command = "00000001"  # Show display command
        display_bits = format(self.display_type.value, '08b')
        padding = "00000000"
        return command + display_bits + padding

class SetDisplayModeCommand(DisplayCommand):
    """Command to set display mode."""
    def __init__(self, display_type: str, mode: DisplayMode):
        super().__init__(display_type)
        self.command_type = "SET_MODE"
        self.mode = mode

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Command type (8 bits): 00000010 for set mode
        - Display type (8 bits): Enum value
        - Mode (8 bits): Enum value
        """
        command = "00000010"  # Set mode command
        display_bits = format(self.display_type.value, '08b')
        mode_bits = format(self.mode.value, '08b')
        return command + display_bits + mode_bits

class DisplayResponse(DisplayMessage):
    """Base class for display response messages."""
    def __init__(self, success: bool = True, error: str = None):
        super().__init__()
        self.success = success
        self.error = error
        self.response_type = None

    def validate(self) -> bool:
        """Validate response attributes."""
        return super().validate() and self.response_type is not None

class DisplayShownResponse(DisplayResponse):
    """Response to show display command."""
    def __init__(self, success: bool = True, error: str = None):
        super().__init__(success, error)
        self.response_type = "SHOWN"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Response type (8 bits): 00000001 for display shown
        - Success flag (8 bits): 1 for success, 0 for failure
        - Error/padding (8 bits): All 1s for error, 0s for success
        """
        response_type = "00000001"  # Display shown response
        success_bit = "00000001" if self.success else "00000000"
        error_bits = "00000000" if self.success else "11111111"
        return response_type + success_bit + error_bits

class DisplayModeSetResponse(DisplayResponse):
    """Response to set mode command."""
    def __init__(self, success: bool = True, error: str = None):
        super().__init__(success, error)
        self.response_type = "MODE_SET"

    def to_binary(self) -> str:
        """Convert to binary format.
        Format:
        - Response type (8 bits): 00000010 for mode set
        - Success flag (8 bits): 1 for success, 0 for failure
        - Error/padding (8 bits): All 1s for error, 0s for success
        """
        response_type = "00000010"  # Mode set response
        success_bit = "00000001" if self.success else "00000000"
        error_bits = "00000000" if self.success else "11111111"
        return response_type + success_bit + error_bits

def create_display_command(command_type: str, **kwargs) -> DisplayCommand:
    """Factory function for creating display commands."""
    command_map = {
        "show_display": ShowDisplayCommand,
        "set_mode": SetDisplayModeCommand
    }
    
    if command_type not in command_map:
        raise ValueError(f"Unknown command type: {command_type}")
        
    command_class = command_map[command_type]
    return command_class(**kwargs)

def create_display_response(response_type: str, **kwargs) -> DisplayResponse:
    """Factory function for creating display responses."""
    response_map = {
        "display_shown": DisplayShownResponse,
        "mode_set": DisplayModeSetResponse
    }
    
    if response_type not in response_map:
        raise ValueError(f"Unknown response type: {response_type}")
        
    response_class = response_map[response_type]
    return response_class(**kwargs)
