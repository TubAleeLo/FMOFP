import xml.etree.ElementTree as ET
from typing import Dict, Optional
from FMOFP.local_messaging.command_name_registry import COMMAND_NAMES
from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()


def get_command_name(message_type: str, command_word: Optional[str] = None) -> Optional[str]:
    """
    Get command name from message type or command word.
    
    Args:
        message_type: The message type to look up
        command_word: Optional command word to help identify specific commands
        
    Returns:
        Command name if found, None otherwise
    """
    # First try exact message type match
    for cmd_name, cmd_info in COMMAND_NAMES.items():
        if cmd_info['message_type'] == message_type:
            return cmd_name
            
    # If no match and command word provided, try matching command word
    if command_word:
        # Convert hex to binary if needed
        if command_word.startswith('0x'):
            binary_cmd = format(int(command_word, 16), '016b')
        else:
            binary_cmd = command_word[-16:] if len(command_word) > 16 else command_word
            
        for cmd_name, cmd_info in COMMAND_NAMES.items():
            cmd_hex = cmd_info['command_hex']
            cmd_binary = format(int(cmd_hex, 16), '016b')
            if binary_cmd == cmd_binary:
                return cmd_name
                
    return None

def validate_command_name(command_name: str) -> bool:
    """
    Validate that a command name exists in the registry.
    
    Args:
        command_name: The command name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return command_name in COMMAND_NAMES

# Function to parse the address book XML file and return a dictionary of system addresses and subaddresses
def parse_address_book(path: str) -> Dict[str, Dict[str, Dict[str, str]]]:
    tree = ET.parse(path)
    root = tree.getroot()
    address_book = {}
    for system in root.findall('system'):
        system_id = system.get('id').lower()
        address = system.find('address').text
        address_book[system_id] = {'address': address, 'subaddresses': {}}
    
    for subaddress in root.findall('subaddress'):
        subaddress_id = subaddress.get('id').lower()
        subaddress_value = subaddress.find('subaddress').text
        for system in address_book.values():
            system['subaddresses'][subaddress_id] = subaddress_value

    return address_book

# Function to parse the command registry XML file and return a dictionary of command names and values
def parse_command_registry(path: str) -> Dict[str, str]:
    tree = ET.parse(path)
    root = tree.getroot()
    command_registry = {}
    for command in root.findall('command'):
        name = command.find('name').text.lower()
        value = command.find('value').text
        command_registry[name] = value
    return command_registry
