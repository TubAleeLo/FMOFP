import xml.etree.ElementTree as ET
import logging
from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.local_messaging.routing.handlers.sync_handler.AsyncMessageHandler import AsyncMessageHandler
from FMOFP.local_messaging.command_word_map import COMMAND_REGISTRY, register_command_word

# Register all necessary message types for local messaging
@dataclass
class weather_radarCommand(BaseMessage):
    """Command message for weather radar operations"""
    command: str = ""  # Command type (e.g., "set_mode")
    mode: str = ""  # Mode for mode change commands
    parameters: dict = None  # Additional parameters

    def to_xml(self):
        """Convert to XML format as specified in message flow description"""
        root = ET.Element("message")
        
        sender = ET.SubElement(root, "sender")
        sender.text = self.sending_system
        
        receiver = ET.SubElement(root, "receiver")
        receiver.text = self.destination
        
        content = ET.SubElement(root, "content")
        
        type_elem = ET.SubElement(content, "type")
        type_elem.text = "command"
        
        command_elem = ET.SubElement(content, "command")
        command_elem.text = self.command
        
        if self.mode:
            mode_elem = ET.SubElement(content, "mode")
            mode_elem.text = self.mode
            
        return ET.tostring(root, encoding='unicode')

    def get_command_word(self):
        """Get properly formatted 16-bit command word"""
        if self.command == "set_mode":
            # Use command registry for mode change request
            command_name = "weather_radar_mode_request"
            if command_name.lower() in COMMAND_REGISTRY:
                return format(int(COMMAND_REGISTRY[command_name.lower()], 16), '016b')
            # Fallback to constructing command word.
            # NOTE (production readiness re-analysis, August 2026): this called
            # an undefined `construct_command_word` -- never imported, never
            # defined anywhere in this module or the codebase (there are two
            # unrelated same-named functions elsewhere -- a BC_msg.py instance
            # method with a completely different signature, and standalone
            # helpers in the two display_command_map.py files -- neither is
            # what this call site's 4 positional args (`'radar', 0,
            # 'weather_radar', 'mode'`) match). Found via
            # `ruff check --select F821` (undefined-name). The signature that
            # actually matches is register_command_word(system_id, t_or_r,
            # subaddress_name, message_type) from this same command_word_map
            # module (already imported above for COMMAND_REGISTRY) -- it takes
            # the identical 4 args in the identical order and returns a binary
            # command-word string, exactly what get_command_word() needs here.
            # This is a low-traffic fallback (only reached if
            # 'weather_radar_mode_request' is ever missing from
            # COMMAND_REGISTRY, which it isn't in the current registry), so it
            # had never been exercised.
            return register_command_word('radar', 0, 'weather_radar', 'mode')
        return None

register_message_type("weather_radarCommand", weather_radarCommand)

@dataclass
class weather_radarStatus(BaseMessage):
    """Status message for weather radar operations"""
    status: str = ""  # Current status
    mode: str = ""  # Current mode
    health: str = ""  # Health status

    def to_xml(self):
        root = ET.Element("message")
        
        sender = ET.SubElement(root, "sender")
        sender.text = self.sending_system
        
        receiver = ET.SubElement(root, "receiver")
        receiver.text = self.destination
        
        content = ET.SubElement(root, "content")
        
        type_elem = ET.SubElement(content, "type")
        type_elem.text = "status"
        
        status_elem = ET.SubElement(content, "status")
        status_elem.text = self.status
        
        mode_elem = ET.SubElement(content, "mode")
        mode_elem.text = self.mode
        
        health_elem = ET.SubElement(content, "health")
        health_elem.text = self.health
        
        return ET.tostring(root, encoding='unicode')

    def get_command_word(self):
        """Get properly formatted 16-bit command word"""
        command_name = "weather_radar_status_request"
        if command_name.lower() in COMMAND_REGISTRY:
            return format(int(COMMAND_REGISTRY[command_name.lower()], 16), '016b')
        
        else:
            # Register the weather_radarStatusRequest command in the COMMAND_REGISTRY
            COMMAND_REGISTRY["weather_radarStatusRequest"] = "0x2004"
            return format(int(COMMAND_REGISTRY["weather_radarStatusRequest"], 16), '016b')

register_message_type("weather_radarStatus", weather_radarStatus)

# Load address book for system identification
try:
    # Try to load the address book from the file
    address_book_tree = ET.parse('FMOFP/local_messaging/messageConfigurations/address_book.xml')
    address_book_root = address_book_tree.getroot()

    # Create system address mapping
    address_book = {}
    for system in address_book_root.findall('system'):
        system_info = {
            'name': system.find('name').text,
            'address': system.find('address').text
        }
        
        # Check if port element exists before accessing its text
        port_elem = system.find('port')
        if port_elem is not None:
            system_info['port'] = port_elem.text
        else:
            # Use default port based on system ID
            if system.get('id') == 'radar':
                system_info['port'] = '5001'
            elif system.get('id') == 'displays':
                system_info['port'] = '5002'
            else:
                system_info['port'] = '5000'  # Default port for other systems
        
        address_book[system.get('id')] = system_info

    # Create subaddress mapping
    subaddresses = {}
    for subaddr in address_book_root.findall('subaddress'):
        subaddresses[subaddr.get('id')] = {
            'name': subaddr.find('name').text,
            'subaddress': subaddr.find('subaddress').text
        }
except FileNotFoundError:
    # If the file is not found, create a mock address book
    logging.warning("Address book file not found. Using default values.")
    
    # Create a mock address book with default values
    address_book = {
        'radar': {
            'name': 'Radar System',
            'address': '9',
            'port': '5001'
        },
        'displays': {
            'name': 'Display System',
            'address': '11',
            'port': '5002'
        }
    }
    
    # Create mock subaddresses
    subaddresses = {
        'weather_radar': {
            'name': 'Weather Radar',
            'subaddress': '1'
        },
        'mode': {
            'name': 'Mode',
            'subaddress': '2'
        }
    }

def send_radar_message(message: BaseMessage, async_handler: AsyncMessageHandler):
    """
    Send a radar message using AsyncMessageHandler.
    
    :param message: The message to send
    :param async_handler: The AsyncMessageHandler instance
    """
    if not isinstance(message, BaseMessage):
        raise ValueError("Message must be a BaseMessage instance")
    
    # Get proper 16-bit command word
    command_word = message.get_command_word()
    if not command_word:
        raise ValueError("Could not get valid command word for message")
    
    # Convert message to XML format
    xml_message = message.to_xml()
    
    # Create message data for AsyncMessageHandler
    msg_data = {
        'command_word': command_word,  # Now using proper 16-bit command word
        'data': xml_message
    }
    
    # Queue message in AsyncMessageHandler
    async_handler.add_message("radar", msg_data)
    
    logging.info(f"Queued radar message with command word: {command_word}")

logging.info("Weather radar message types registered")
logging.info("Address book and subaddresses loaded")
