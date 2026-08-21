"""
Command Word Map

Maps command words to their handlers and provides command word construction utilities.
Also provides command name registry for unique message identification.
"""

from typing import Callable, Dict
import os
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.command_word_map_tools import parse_address_book, parse_command_registry
from FMOFP.Utils.common.operation_tracker import track_operation
from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
from FMOFP.local_messaging.message_types import (
    # Weather Radar Messages
    WEATHER_RADAR_MODE_CHANGE_REQUEST,
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_STATUS_REQUEST,
    WEATHER_RADAR_STATUS_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    
    # Helper functions
    get_message_type,
    is_message_type,
    is_vil_message,
    is_precipitation_message,
    is_mode_change_message
)

# Import Flight Control System message types from local file
from FMOFP.local_messaging.message_types_fcs import (
    FCS_CONTROL_INPUT_REQUEST,
    FCS_CONTROL_INPUT_RESPONSE,
    FCS_ORIENTATION_DATA_REQUEST,
    FCS_ORIENTATION_DATA_RESPONSE,
    FCS_STATUS_REQUEST,
    FCS_STATUS_RESPONSE,
    FCS_MODE_CHANGE_REQUEST,
    FCS_MODE_CHANGE_RESPONSE
)

# Import Flight Control System command words
from FMOFP.local_messaging.command_word_map_fcs import FCS_COMMAND_WORDS, FCS_COMMAND_VALUE_MAP

logger = get_logger()

COMMAND_WORD_MAP: Dict[str, Callable] = {}
COMMAND_WORD_CACHE = {}

# Path to the address book XML file - use absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))
ADDRESS_BOOK_PATH = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'address_book.xml')
COMMAND_REGISTRY_PATH = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'command_registry.xml')

def _initialize_module():
    """Initialize the module once using operation tracking."""
    def _initialize_impl():
        logger.debug("Initializing command word map")
        return True
    
    # Track this operation to ensure it only happens once
    return track_operation('cmd_word_map_init', 'global', _initialize_impl)

# Call initialization at import time
_initialize_module()

# Load the address book and command registry
ADDRESS_BOOK = parse_address_book(ADDRESS_BOOK_PATH)
COMMAND_REGISTRY = parse_command_registry(COMMAND_REGISTRY_PATH)

# Define radar types and message types
RADAR_TYPES = ['weather_radar', 'tfr_radar', 'sar_radar', 'targeting_radar', 'aewc_radar']
MESSAGE_TYPES = ['status', 'mode', 'data']

# Define display types and message types
DISPLAY_TYPES = ['pfd', 'mfd', 'eicas', 'radar_display', 'tsd', 'sms']
DISPLAY_MESSAGE_TYPES = ['show', 'mode', 'data']

# Define weather radar data types
WEATHER_DATA_TYPES = ['echo_top', 'shear', 'turbulence', 'vil', 'precipitation']

# Define flight control system types
FCS_TYPES = ['flight_control_system', 'control_surface_manager', 'attitude_calculator', 'flight_dynamics_processor']
FCS_MESSAGE_TYPES = ['control_input', 'orientation_data', 'mode', 'status']


def validate_command_word(command_word: str) -> str:
    """
    Validate and format command words.
    
    Args:
        command_word: The command word to validate
        
    Returns:
        str: The validated and formatted command word
    """
    # Handling for status words (which start with '100')
    if isinstance(command_word, str) and len(command_word) == 20 and command_word.startswith('100'):
        # This is a status word, not a command word
        rt_address = int(command_word[3:8], 2) if len(command_word) >= 8 else None
        logger.info(f"Validated status word with RT address: {rt_address}")
        return command_word
        
    # Regular command word validation
    if isinstance(command_word, str):
        if len(command_word) == 16 and set(command_word) <= {'0', '1'}:
            return command_word
        elif command_word.startswith('0x'):
            return format(int(command_word, 16), '016b')
        elif command_word.lower() in COMMAND_REGISTRY:
            return format(int(COMMAND_REGISTRY[command_word.lower()], 16), '016b')
        elif command_word in globals():
            return globals()[command_word]
        else:
            raise ValueError(f"Invalid command word format: {command_word}")
    elif isinstance(command_word, int):
        return format(command_word, '016b')
    else:
        raise ValueError(f"Invalid command word format: {command_word}")


def extract_command_word(message: Dict) -> str:
    """
    Extract the command word from a 1553 message.
    
    Args:
        message: The message to extract from
        
    Returns:
        str: The extracted command word
    """
    command_word = message.get('command_word')
    if command_word:
        return validate_command_word(command_word)
    else:
        raise ValueError("Command word not found in the message")


def register_message_handler(command_word: str, handler: Callable) -> None:
    """
    Register a message handler for a specific command word.
    
    Args:
        command_word: The command word to register
        handler: The handler function
    """
    COMMAND_WORD_MAP[validate_command_word(command_word)] = handler


def _get_command_type(command_word: str, message: Dict = None) -> str:
    """
    Determine command type from command word structure.
    
    Args:
        command_word: The command word to parse
        message: Optional message containing additional info
        
    Returns:
        str: The determined command type
        
    Raises:
        ValueError: If command type cannot be determined
    """
    logger.info(f"[CMD] Parsing command word: {command_word}")
    
    # First prioritize using message_types helper functions if message is provided
    if message is not None:
        # Use the standardized helpers from message_types
        if is_mode_change_message(message):
            logger.info("[CMD] Identified mode command using is_mode_change_message")
            return 'mode'
        elif is_precipitation_message(message):
            logger.info("[CMD] Identified precipitation data using is_precipitation_message")
            return 'precipitation_data'
        elif is_vil_message(message):
            logger.info("[CMD] Identified VIL data using is_vil_message")
            return 'vil_data'
    
    # If that didn't work, check command registry for exact match
    binary_cmd = command_word[-16:] if len(command_word) > 16 else command_word
    for name, value in COMMAND_REGISTRY.items():
        # Convert registry value to binary
        registry_binary = format(int(value, 16), '016b')
        if binary_cmd == registry_binary:
            if 'modechange' in name.lower() or 'mode_request' in name.lower() or 'mode_change' in name.lower():
                logger.info(f"[CMD] Identified mode command from registry: {name}")
                return 'mode'
            elif 'status' in name.lower():
                logger.info(f"[CMD] Identified status command from registry: {name}")
                return 'status'
            elif 'data' in name.lower():
                if 'precipitation' in name.lower():
                    logger.info(f"[CMD] Identified precipitation data from registry: {name}")
                    return 'precipitation_data'
                elif 'vil' in name.lower():
                    logger.info(f"[CMD] Identified VIL data from registry: {name}")
                    return 'vil_data'
                else:
                    logger.info(f"[CMD] Identified data command from registry: {name}")
                    return 'data'
    
    # If no registry match, parse command word structure as a last resort
    rt_address = int(command_word[0:5], 2)  # First 5 bits
    tr_bit = int(command_word[5:6], 2)      # T/R bit
    subaddress = int(command_word[6:11], 2) # Bits 6-10 after T/R bit
    word_count = int(command_word[11:16], 2) # Last 5 bits
    
    logger.info(f"[CMD] Parsed fields: RT={rt_address}, T/R={tr_bit}, SA={subaddress}, WC={word_count}")
    
    # Check for display commands using address_utils for RT address lookup
    try:
        displays_rt = get_rt_address('displays')
        if rt_address == displays_rt:
            # Check if this subaddress corresponds to any display subsystem
            for display_type in DISPLAY_TYPES:
                try:
                    display_sa = get_subaddress(display_type)
                    if subaddress == display_sa:
                        logger.info(f"[CMD] Identified display command for {display_type}")
                        return 'mode'
                except ValueError:
                    continue
    except ValueError:
        logger.warning("[CMD] Could not retrieve 'displays' RT address")
    
    # Check radar commands using address_utils
    try:
        radar_rt = get_rt_address('radar')
        if rt_address == radar_rt:
            for radar_type in RADAR_TYPES:
                try:
                    radar_sa = get_subaddress(radar_type)
                    if subaddress == radar_sa:
                        if word_count == 1:
                            logger.info(f"[CMD] Identified {radar_type} status command")
                            return 'status'
                        elif word_count == 2:
                            # For weather radar, we need more information to distinguish data types
                            if radar_type == 'weather_radar' and message:
                                # Try to determine if this is precipitation or VIL data
                                if isinstance(message, dict) and 'data' in message:
                                    data = message.get('data')
                                    if isinstance(data, list) and len(data) == 2:
                                        try:
                                            data_word = int(data[1], 2)
                                            type_bits = (data_word >> 14) & 0x3  # Top 2 bits
                                            if type_bits in [0, 1, 2, 3]:  # Precipitation types
                                                return 'precipitation_data'
                                            else:
                                                return 'vil_data'
                                        except ValueError:
                                            pass
                            logger.info(f"[CMD] Identified {radar_type} mode command")
                            return 'mode'
                        else:
                            logger.info(f"[CMD] Identified {radar_type} data command")
                            return 'data'
                except ValueError:
                    continue
    except ValueError:
        logger.warning("[CMD] Could not retrieve 'radar' RT address")
    
    # If no pattern matched, this is an error
    logger.error(f"[CMD] Could not determine command type for RT={rt_address}, SA={subaddress}, WC={word_count}")
    raise ValueError(f"Could not determine command type for command word {command_word}")


def register_command_word(system_id: str, t_or_r: int, subaddress_name: str, message_type: str, data_type: str = None) -> str:
    """
    Register a command word with the system.
    
    Args:
        system_id: The system ID (e.g., 'radar', 'displays')
        t_or_r: Transmit/receive bit (0=transmit, 1=receive)
        subaddress_name: The subaddress name (must be a valid subsystem)
        message_type: The message type (e.g., 'mode', 'status', 'data')
        data_type: Optional data type for data messages
        
    Returns:
        str: The binary command word
    """
    # Create a cache key based on the parameters
    cache_key = f"{system_id}_{t_or_r}_{subaddress_name}_{message_type}_{data_type}"
    
    # Check if this command word is already in the cache
    if cache_key in COMMAND_WORD_CACHE:
        return COMMAND_WORD_CACHE[cache_key]
    
    # Get RT address using address_utils instead of direct lookup
    try:
        rt_address = get_rt_address(system_id)
    except ValueError as e:
        logger.error(f"System ID '{system_id}' not found: {e}")
        raise ValueError(f"System ID '{system_id}' not found in address book")
    
    # Get subaddress using address_utils
    try:
        subaddress = get_subaddress(subaddress_name)
    except ValueError as e:
        logger.error(f"Subaddress '{subaddress_name}' not found: {e}")
        raise ValueError(f"Subaddress '{subaddress_name}' not found for system {system_id}")

    rt_address_bin = format(rt_address, '05b')
    t_or_r_bin = format(t_or_r, '01b')
    subaddress_bin = format(subaddress, '05b')

    # Use the message type and data type to set the word count
    if message_type == 'status':
        word_count = 1
    elif message_type == 'mode':
        word_count = 2  # Mode value + command type
    elif message_type == 'data':
        if data_type == 'echo_top':
            word_count = 4  # Type word + 3 data values
        elif data_type == 'shear':
            word_count = 4  # Type word + 3 data values
        elif data_type == 'turbulence':
            word_count = 5  # Type word + 4 data values
        elif data_type == 'vil':
            word_count = 2  # Two words: position word + data word
        elif data_type == 'precipitation':
            word_count = 2  # Two words: position word + data word
        else:
            word_count = 3  # Default data word count
    # Display message types
    elif message_type == 'show':
        word_count = 1  # Just the command type
    else:
        raise ValueError(f"Invalid message type: {message_type}")

    word_count_bin = format(word_count, '05b')
    command_word_bin = rt_address_bin + t_or_r_bin + subaddress_bin + word_count_bin
    
    # Store in cache before returning
    COMMAND_WORD_CACHE[cache_key] = command_word_bin
    logger.debug(f"[CMD REG] Created and cached new command word for {cache_key}")
    return command_word_bin


# Create radar command word constants - using actual subsystem names instead of 'mode'
for radar_type in RADAR_TYPES:
    # Create mode commands
    mode_request = f'{radar_type.upper()}_MODE_REQUEST'
    mode_response = f'{radar_type.upper()}_MODE_RESPONSE'
    mode_update = f'{radar_type.upper()}_MODE_UPDATE'
    
    # Use command registry values if available
    request_value = COMMAND_REGISTRY.get(f"{radar_type}modechangerequest")
    if request_value:
        globals()[mode_request] = format(int(request_value, 16), '016b')
    else:
        # Use the actual radar type as the subaddress name
        globals()[mode_request] = register_command_word('radar', 0, radar_type, 'mode')
        
    response_value = COMMAND_REGISTRY.get(f"{radar_type}modechangeresponse")
    if response_value:
        globals()[mode_response] = format(int(response_value, 16), '016b')
    else:
        globals()[mode_response] = register_command_word('radar', 1, radar_type, 'mode')
        
    # Updates use same format as requests
    globals()[mode_update] = globals()[mode_request]
    
    # Create status commands
    status_request = f'{radar_type.upper()}_STATUS_REQUEST'
    status_response = f'{radar_type.upper()}_STATUS_RESPONSE'
    status_update = f'{radar_type.upper()}_STATUS_UPDATE'
    
    request_value = COMMAND_REGISTRY.get(f"{radar_type}statusrequest")
    if request_value:
        globals()[status_request] = format(int(request_value, 16), '016b')
    else:
        globals()[status_request] = register_command_word('radar', 0, radar_type, 'status')
        
    response_value = COMMAND_REGISTRY.get(f"{radar_type}statusresponse")
    if response_value:
        globals()[status_response] = format(int(response_value, 16), '016b')
    else:
        globals()[status_response] = register_command_word('radar', 1, radar_type, 'status')
        
    # Updates use same format as requests
    globals()[status_update] = globals()[status_request]
    
    # Create data commands
    data_request = f'{radar_type.upper()}_DATA_REQUEST'
    data_response = f'{radar_type.upper()}_DATA_RESPONSE'
    data_update = f'{radar_type.upper()}_DATA_UPDATE'
    
    request_value = COMMAND_REGISTRY.get(f"{radar_type}datarequest")
    if request_value:
        globals()[data_request] = format(int(request_value, 16), '016b')
    else:
        globals()[data_request] = register_command_word('radar', 0, radar_type, 'data')
        
    response_value = COMMAND_REGISTRY.get(f"{radar_type}dataresponse")
    if response_value:
        globals()[data_response] = format(int(response_value, 16), '016b')
    else:
        globals()[data_response] = register_command_word('radar', 1, radar_type, 'data')
        
    # Updates use same format as requests
    globals()[data_update] = globals()[data_request]


# Create display command word constants - using actual subsystem names instead of 'mode'
for display_type in DISPLAY_TYPES:
    # Create mode commands
    mode_request = f'{display_type.upper()}_MODE_REQUEST'
    mode_response = f'{display_type.upper()}_MODE_RESPONSE'
    mode_update = f'{display_type.upper()}_MODE_UPDATE'
    
    # Use the actual display type as the subaddress
    # This is the critical fix for the 'mode' subaddress issue
    request_value = COMMAND_REGISTRY.get(f"{display_type}_mode_request")
    if request_value:
        globals()[mode_request] = format(int(request_value, 16), '016b')
    else:
        globals()[mode_request] = register_command_word('displays', 0, display_type, 'mode')
        
    response_value = COMMAND_REGISTRY.get(f"{display_type}_mode_response") 
    if response_value:
        globals()[mode_response] = format(int(response_value, 16), '016b')
    else:
        globals()[mode_response] = register_command_word('displays', 1, display_type, 'mode')
        
    # Updates use same format as requests
    globals()[mode_update] = globals()[mode_request]


################
### REQUESTS ###
################

# Create request maps for basic message types
MODE_REQUEST_MAP = {
    radar_type: globals()[f"{radar_type.upper()}_MODE_REQUEST"]
    for radar_type in RADAR_TYPES
}

# Add Flight Control System to the mode request map
for fcs_type in FCS_TYPES:
    # Use string lookup instead of direct variable reference
    MODE_REQUEST_MAP[fcs_type] = FCS_COMMAND_WORDS.get(FCS_MODE_CHANGE_REQUEST, {}).value

STATUS_REQUEST_MAP = {
    radar_type: globals()[f"{radar_type.upper()}_STATUS_REQUEST"]
    for radar_type in RADAR_TYPES
}

# Add Flight Control System to the status request map
for fcs_type in FCS_TYPES:
    # Use string lookup instead of direct variable reference
    STATUS_REQUEST_MAP[fcs_type] = FCS_COMMAND_WORDS.get(FCS_STATUS_REQUEST, {}).value

DATA_REQUEST_MAP = {
    radar_type: globals()[f"{radar_type.upper()}_DATA_REQUEST"]
    for radar_type in RADAR_TYPES
}

# Create display request maps
DISPLAY_MODE_REQUEST_MAP = {
    display_type: globals()[f"{display_type.upper()}_MODE_REQUEST"]
    for display_type in DISPLAY_TYPES
}

# Create weather radar specific data command words
for data_type in WEATHER_DATA_TYPES:
    request_name = f'WEATHER_RADAR_{data_type.upper()}_DATA_REQUEST'
    response_name = f'WEATHER_RADAR_{data_type.upper()}_DATA_RESPONSE'
    
    # Use command registry values if available
    request_value = COMMAND_REGISTRY.get(f"weather_radar{data_type}datarequest")
    response_value = COMMAND_REGISTRY.get(f"weather_radar{data_type}dataresponse")
    
    if request_value and response_value:
        globals()[request_name] = format(int(request_value, 16), '016b')
        globals()[response_name] = format(int(response_value, 16), '016b')
    else:
        globals()[request_name] = register_command_word('radar', 0, 'weather_radar', 'data', data_type)
        globals()[response_name] = register_command_word('radar', 1, 'weather_radar', 'data', data_type)

# Create weather radar data request map
WEATHER_DATA_REQUEST_MAP = {}
for data_type in WEATHER_DATA_TYPES:
    request_name = f"weather_radar{data_type}datarequest"
    request_value = COMMAND_REGISTRY.get(request_name)
    if request_value:
        # For registry values, use address_utils for consistency
        try:
            radar_rt = get_rt_address('radar')
            weather_radar_sa = get_subaddress('weather_radar')
            
            # Set word count based on data type
            word_count = 2 if data_type in ['vil', 'precipitation'] else 3
            
            # Construct command word with correct RT address
            rt_address_bin = format(radar_rt, '05b')
            t_or_r_bin = '0'  # Request
            subaddress_bin = format(weather_radar_sa, '05b')
            word_count_bin = format(word_count, '05b')
            
            binary_cmd = rt_address_bin + t_or_r_bin + subaddress_bin + word_count_bin
            logger.info(f"[CMD] Created {data_type} request with RT={radar_rt}: {binary_cmd}")
            WEATHER_DATA_REQUEST_MAP[data_type] = binary_cmd
        except ValueError as e:
            logger.error(f"[CMD] Error creating {data_type} request: {e}")
            # Fallback to old approach
            binary_cmd = register_command_word('radar', 0, 'weather_radar', 'data', data_type)
            WEATHER_DATA_REQUEST_MAP[data_type] = binary_cmd
    else:
        # Use register_command_word for consistency
        binary_cmd = register_command_word('radar', 0, 'weather_radar', 'data', data_type)
        WEATHER_DATA_REQUEST_MAP[data_type] = binary_cmd


# Export all command word constants and maps
__all__ = [
    'RADAR_TYPES',
    'MESSAGE_TYPES',
    'DISPLAY_TYPES',
    'DISPLAY_MESSAGE_TYPES',
    'WEATHER_DATA_TYPES',
    'FCS_TYPES',
    'FCS_MESSAGE_TYPES',
    'ADDRESS_BOOK',
    'COMMAND_REGISTRY',
    'MODE_REQUEST_MAP',
    'STATUS_REQUEST_MAP',
    'DATA_REQUEST_MAP',
    'DISPLAY_MODE_REQUEST_MAP',
    'WEATHER_DATA_REQUEST_MAP',
    'FCS_COMMAND_WORDS',   # Add FCS command words
    'FCS_COMMAND_VALUE_MAP',  # Add FCS command word map
    'validate_command_word',
    'extract_command_word',
    'register_message_handler',
    'register_command_word',
    'get_rt_address',  # Add address_utils functions
    'get_subaddress',
] + [f"{rt.upper()}_{mt.upper()}_{t}" 
     for rt in RADAR_TYPES + DISPLAY_TYPES
     for mt in MESSAGE_TYPES 
     for t in ['REQUEST', 'RESPONSE', 'UPDATE']] + [
    f"WEATHER_RADAR_{dt.upper()}_DATA_{t}"
    for dt in WEATHER_DATA_TYPES
    for t in ['REQUEST', 'RESPONSE']
]
