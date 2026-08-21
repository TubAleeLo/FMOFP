"""
Message Generator

Handles loading and filling message templates for radar communication.
"""
import os
import time
import xml.etree.ElementTree as ET
from typing import Dict
from FMOFP.Systems.radarManagement.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode
)
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Mapping of radar types to their mode enums
RADAR_MODE_MAP = {
    'weather_radar': weather_radarMode,
    'tfr_radar': tfr_radarMode,
    'sar_radar': sar_radarMode,
    'targeting_radar': targeting_radarMode,
    'aewc_radar': aewc_radarMode
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

    def generate_radar_command(self, radar_type: str, mode: str) -> str:
        """
        Generate a radar command message for mode changes.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            mode: The mode to set (must be valid for the radar type)
            
        Returns:
            XML message string
        """
        try:
            # Validate radar type
            if radar_type not in RADAR_MODE_MAP:
                raise ValueError(f"Invalid radar type: {radar_type}")

            # Get mode enum for this radar type
            mode_enum = RADAR_MODE_MAP[radar_type]

            # Validate mode
            if isinstance(mode, str):
                try:
                    mode_enum[mode]  # Validate mode exists
                except KeyError:
                    raise ValueError(f"Invalid mode '{mode}' for {radar_type}")
            elif isinstance(mode, mode_enum):
                mode = mode.name
            else:
                raise ValueError(f"Invalid mode type for {radar_type}: {type(mode)}")

            # Generate command message
            params = {
                'message_header': 'mode_change',
                'sending_system': 'radar_control',
                'destination': radar_type,
                'message_type': f'{radar_type}Command',
                'command': f'set_mode {mode}'
            }
            return self.generate_message('radar_command', params)

        except Exception as e:
            logger.error(f"Error generating radar command: {e}")
            raise

    def generate_command_acknowledgment(self, radar_type: str, command: str, status: str = "success") -> str:
        """
        Generate a command acknowledgment message.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            command: The command being acknowledged
            status: Status of the command execution (default: "success")
            
        Returns:
            XML message string
        """
        try:
            # Validate radar type
            if radar_type not in RADAR_MODE_MAP:
                raise ValueError(f"Invalid radar type: {radar_type}")

            # Generate acknowledgment message
            params = {
                'message_header': 'command_acknowledgment',
                'sending_system': radar_type,
                'destination': 'radar_control',
                'message_type': f'{radar_type}Acknowledgment',
                'type': 'command_acknowledgment',
                'command': command,
                'status': status,
                'timestamp': str(time.time())
            }
            return self.generate_message('radar_acknowledgment', params)

        except Exception as e:
            logger.error(f"Error generating command acknowledgment: {e}")
            raise

    def generate_radar_status_request(self, radar_type: str) -> str:
        """
        Generate a radar status request message.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            
        Returns:
            XML message string
        """
        try:
            # Validate radar type
            if radar_type not in RADAR_MODE_MAP:
                raise ValueError(f"Invalid radar type: {radar_type}")

            params = {
                'message_header': 'status_request',
                'sending_system': 'radar_control',
                'destination': radar_type,
                'message_type': f'{radar_type}Status'
            }
            return self.generate_message('radar_command', params)

        except Exception as e:
            logger.error(f"Error generating status request: {e}")
            raise

    def generate_radar_data_request(self, radar_type: str) -> str:
        """
        Generate a radar data request message.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            
        Returns:
            XML message string
        """
        try:
            # Validate radar type
            if radar_type not in RADAR_MODE_MAP:
                raise ValueError(f"Invalid radar type: {radar_type}")

            params = {
                'message_header': 'data_request',
                'sending_system': 'radar_control',
                'destination': radar_type,
                'message_type': f'{radar_type}Data'
            }
            return self.generate_message('radar_command', params)

        except Exception as e:
            logger.error(f"Error generating data request: {e}")
            raise

    def validate_mode(self, radar_type: str, mode: str) -> bool:
        """
        Validate if a mode is valid for a given radar type.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            mode: Mode to validate
            
        Returns:
            True if mode is valid, False otherwise
        """
        try:
            if radar_type not in RADAR_MODE_MAP:
                return False
            mode_enum = RADAR_MODE_MAP[radar_type]
            return mode in [m.name for m in mode_enum]
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
