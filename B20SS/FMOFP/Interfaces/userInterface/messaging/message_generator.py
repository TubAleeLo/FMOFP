"""
Message Generator

Handles loading and filling message templates for display communication.
Uses display-local message types and constants for consistent message handling.
"""
import os
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Union

# Import display-local modules
from .display_message_types import (
    DISPLAY_COMMAND_TYPE_SHOW,
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE,
    DISPLAY_COMMAND_TYPE_ACKNOWLEDGMENT,
    DISPLAY_MESSAGE_TYPE_COMMAND,
    DISPLAY_MESSAGE_TYPE_ACKNOWLEDGMENT
)
from .display_address_utils import (
    DISPLAY_RT_ADDRESS,
    DISPLAY_SHOW_SUBADDRESS,
    DISPLAY_MODE_SUBADDRESS,
    get_rt_address_name,
    get_subaddress_name
)

# Import display types and modes
from ..displays.base_display import DisplayType, DisplayMode

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Mapping of display types to their enums - centralized for easier maintenance
DISPLAY_TYPES = {
    'pfd': DisplayType.PFD,
    'mfd': DisplayType.MFD,
    'eicas': DisplayType.EICAS,
    'radar_display': DisplayType.RADAR,
    'tsd': DisplayType.TSD,
    'sms': DisplayType.SMS
}


# Command type to command value mapping - centralized for easier maintenance
COMMAND_VALUE_MAP = {
    DISPLAY_COMMAND_TYPE_SHOW: '001',
    'show': '001',
    DISPLAY_COMMAND_TYPE_MODE: '010',
    'mode': '010'
}

class MessageGenerator:
    def __init__(self):
        self.templates = {}
        self.template_dir = os.path.join(os.path.dirname(__file__), 'message_templates')
        self._load_templates()

    def _load_templates(self):
        """Load all XML templates from the template directory."""
        try:
            for filename in os.listdir(self.template_dir):
                if filename.endswith('.xml'):
                    template_name = filename[:-4]  # Remove .xml extension
                    template_path = os.path.join(self.template_dir, filename)
                    with open(template_path, 'r') as f:
                        self.templates[template_name] = f.read()
                    logger.info(f"Loaded message template: {template_name}")
        except Exception as e:
            logger.error(f"Error loading message templates: {e}")
            raise

    def generate_message(self, template_name: str, params: Dict[str, str]) -> str:
        """
        Generate a message by filling a template with parameters.
        
        Args:
            template_name: Name of the template to use (without .xml extension)
            params: Dictionary of parameters to fill in the template
            
        Returns:
            Filled XML message as a string
        """
        try:
            if template_name not in self.templates:
                raise ValueError(f"Template not found: {template_name}")
                
            # Get template and fill in parameters
            template = self.templates[template_name]
            message = template.format(**params)
            
            # Validate the generated XML
            try:
                ET.fromstring(message)
            except ET.ParseError as e:
                logger.error(f"Generated invalid XML: {message}")
                raise
                
            logger.info(f"Generated message from template {template_name}")
            return message
            
        except KeyError as e:
            logger.error(f"Missing required parameter: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating message: {e}")
            raise

    def generate_display_command(self, display_type: str, command_type: str, mode: str = None, request_id: str = None) -> str:
        """
        Generate a display command message.
        Uses display-local message types and constants for consistent message handling.
        
        Args:
            display_type: Type of display ('pfd', 'mfd', etc.)
            command_type: Type of command ('show', 'mode')
            mode: Display mode (optional, only for mode commands)
            request_id: Optional request ID for tracking (generated if not provided)
            
        Returns:
            XML message string
        """
        try:
            # Validate display type
            if display_type not in DISPLAY_TYPES:
                raise ValueError(f"[MSG_GEN] Invalid display type: {display_type}")

            # Validate command type and use standardized constants
            standardized_command_type = command_type
            if command_type == 'show':
                standardized_command_type = DISPLAY_COMMAND_TYPE_SHOW
            elif command_type == 'mode':
                standardized_command_type = DISPLAY_COMMAND_TYPE_MODE
                
            if standardized_command_type not in [DISPLAY_COMMAND_TYPE_SHOW, DISPLAY_COMMAND_TYPE_MODE]:
                raise ValueError(f"[MSG_GEN] Invalid command type: {command_type}")

            # Get command parameters based on type using centralized maps
            command_value = COMMAND_VALUE_MAP.get(command_type, '000')
            tr_bit = '0' if command_type == 'show' else '1'  # BC to RT for show, RT to BC for mode
            
            # Use standard metadata-based approach for command types (MIL-STD-1553B compliant)
            # Commands are identified in message metadata
            metadata = {
                'command_type': standardized_command_type,
                'request_id': request_id
            }
            
            # Generate request ID if not provided
            if not request_id:
                request_id = str(uuid.uuid4())

            # Validate mode if provided
            if command_type == 'mode':
                if not mode:
                    raise ValueError("Mode required for mode command")
                try:
                    mode_enum = DisplayMode[mode.upper()]
                except KeyError:
                    raise ValueError(f"Invalid mode: {mode}")


            display_subaddress = DISPLAY_SHOW_SUBADDRESS
            
            # Generate command message with proper 1553B format using standardized message types
            params = {
                'message_header': command_type,
                'sending_system': 'display_control',
                'destination': display_type,
                'message_type': DISPLAY_MESSAGE_TYPE_COMMAND,
                'command': f"{command_type}_display",
                'display_type': display_type,
                'mode': mode if mode else '',
                'command_value': command_value,
                'tr_bit': tr_bit,
                'subaddress': display_subaddress,
                'request_id': request_id,
                'timestamp': str(time.time()),
                'metadata': metadata
            }
            return self.generate_message('display_command', params)

        except Exception as e:
            logger.error(f"Error generating display command: {e}")
            raise

    def generate_command_acknowledgment(self, display_type: str, command: str, status: str = "success", request_id: str = None) -> str:
        """
        Generate a command acknowledgment message.
        Uses display-local message types and constants for consistent message handling.
        
        Args:
            display_type: Type of display ('pfd', 'mfd', etc.)
            command: The command being acknowledged
            status: Status of the command execution (default: "success")
            request_id: Optional request ID for tracking (generated if not provided)
            
        Returns:
            XML message string
        """
        try:
            # Validate display type
            if display_type not in DISPLAY_TYPES:
                raise ValueError(f"[MSG_GEN] Invalid display type: {display_type}")

            # Map command to standardized command type
            command_type = None
            if command == "show_display":
                command_type = DISPLAY_COMMAND_TYPE_SHOW
            elif command == "set_mode":
                command_type = DISPLAY_COMMAND_TYPE_MODE
            else:
                raise ValueError(f"[MSG_GEN] Invalid command: {command}")
                
            # Get command value and metadata based on command using centralized maps
            command_value = COMMAND_VALUE_MAP.get(command_type, "000")
            tr_bit = "1"  # RT to BC for acknowledgments
            
            # Use standard metadata-based approach for command types
            metadata = {
                'command_type': command_type,
                'request_id': request_id,
                'status': status
            }
            
            # Use display subaddress
            display_subaddress = DISPLAY_SHOW_SUBADDRESS
            
            # Generate request ID if not provided
            if not request_id:
                request_id = str(uuid.uuid4())

            # Generate acknowledgment message with proper 1553B format using standardized message types
            params = {
                'message_header': DISPLAY_COMMAND_TYPE_ACKNOWLEDGMENT,
                'sending_system': display_type,
                'destination': 'display_control',
                'message_type': DISPLAY_MESSAGE_TYPE_ACKNOWLEDGMENT,
                'type': DISPLAY_COMMAND_TYPE_ACKNOWLEDGMENT,
                'command': command,
                'status': status,
                'timestamp': str(time.time()),
                'command_value': command_value,
                'tr_bit': tr_bit,
                'subaddress': display_subaddress,
                'request_id': request_id,
                'metadata': metadata
            }
            return self.generate_message('display_acknowledgment', params)

        except Exception as e:
            logger.error(f"Error generating command acknowledgment: {e}")
            raise

    def validate_mode(self, mode: str) -> bool:
        """
        Validate if a mode is valid.
        
        Args:
            mode: Mode to validate
            
        Returns:
            True if mode is valid, False otherwise
        """
        try:
            return mode.upper() in DisplayMode.__members__
        except Exception:
            return False

# Global instance
_message_generator = None

def get_message_generator() -> MessageGenerator:
    """Get the global MessageGenerator instance."""
    global _message_generator
    if _message_generator is None:
        _message_generator = MessageGenerator()
    return _message_generator
