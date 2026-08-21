"""
FMS Command Word Map

Maps FMS-specific command words and provides registration functions.
Compatible with the main command_word_map system.
"""

from typing import Dict, Callable
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.command_word_map import register_command_word, validate_command_word, extract_command_word

logger = get_logger()

# FMS Command Word Constants
FMS_COMMAND_WORDS = {}
FMS_COMMAND_NAME_MAP = {}

# Define FMS data types and message types
FMS_DATA_TYPES = ['attitude', 'navigation', 'velocity', 'tactical', 'maneuver']
FMS_MESSAGE_TYPES = ['status', 'mode', 'data']

# Dictionary to map variant FMS system IDs to primary ID
FMS_SYSTEM_ID_MAP = {
    'flightmanagementsys': 'flightmanagementsystem',  # Map to the ID that works with address_book.xml
    'flightManagementSystem': 'flightmanagementsystem',  # Primary ID that works with address_book.xml
    'FlightManagementSystem': 'flightmanagementsystem',
    'flightmanagementsystem': 'flightmanagementsystem',  # Exact match as in address_book.xml
    'fms': 'flightmanagementsystem'
}

def normalize_system_id(system_id):
    """
    Normalize system ID to handle variant forms
    
    Args:
        system_id (str): The system ID to normalize
        
    Returns:
        str: The normalized system ID
    """
    # Convert to lowercase for case-insensitive matching
    system_id_lower = system_id.lower()
    
    # Check if it's a recognized variant
    if system_id_lower in FMS_SYSTEM_ID_MAP:
        normalized_id = FMS_SYSTEM_ID_MAP[system_id_lower]
        if normalized_id != system_id:
            logger.info(f"Normalizing system ID variant '{system_id}' to '{normalized_id}'")
        return normalized_id
    
    # If not recognized, return the original
    return system_id

def register_fms_command_words():
    """Register all FMS command words with the system"""
    global FMS_COMMAND_WORDS, FMS_COMMAND_NAME_MAP
    
    # Access the address book to verify the system ID exists
    from FMOFP.local_messaging.command_word_map import ADDRESS_BOOK
    
    # Define system address - should match address_book.xml
    # Use the primary ID directly to ensure consistency
    system_id = 'flightmanagementsystem'  # Lowercase to match address_book.xml

    logger.info(f"Registering FMS command words using system ID: {system_id}")
    
    try:
        # ==== Define command words ====
        
        # Status commands
        FMS_COMMAND_WORDS["FMS_STATUS_REQUEST"] = int(register_command_word(system_id, 0, 'fms', 'status'), 2)
        FMS_COMMAND_WORDS["FMS_STATUS_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'status'), 2)
        
        # Mode commands - use names that match command_registry.xml
        FMS_COMMAND_WORDS["FMS_MODE_CHANGE"] = int(register_command_word(system_id, 0, 'fms', 'mode'), 2)
        FMS_COMMAND_WORDS["FMS_MODE_CHANGE_COMPLETE"] = int(register_command_word(system_id, 1, 'fms', 'mode'), 2)
        
        # Generic command (using 'mode' type since it's a control command)
        FMS_COMMAND_WORDS["FMS_COMMAND"] = int(register_command_word(system_id, 0, 'fms', 'mode'), 2)
        FMS_COMMAND_WORDS["FMS_COMMAND_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'mode'), 2)
        
        # Flight data commands
        FMS_COMMAND_WORDS["FMS_FLIGHT_DATA"] = int(register_command_word(system_id, 0, 'fms', 'data'), 2)
        FMS_COMMAND_WORDS["FMS_FLIGHT_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data'), 2)
        
        # Attitude data
        FMS_COMMAND_WORDS["FMS_UPDATE_ATTITUDE"] = int(register_command_word(system_id, 0, 'fms', 'data', 'attitude'), 2)
        FMS_COMMAND_WORDS["FMS_ATTITUDE_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'attitude'), 2)
        
        # Navigation data
        FMS_COMMAND_WORDS["FMS_UPDATE_NAVIGATION"] = int(register_command_word(system_id, 0, 'fms', 'data', 'navigation'), 2)
        FMS_COMMAND_WORDS["FMS_NAVIGATION_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'navigation'), 2)
        
        # Velocity data
        FMS_COMMAND_WORDS["FMS_UPDATE_VELOCITY"] = int(register_command_word(system_id, 0, 'fms', 'data', 'velocity'), 2)
        FMS_COMMAND_WORDS["FMS_VELOCITY_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'velocity'), 2)
        
        # Tactical data
        FMS_COMMAND_WORDS["FMS_TACTICAL_STATUS"] = int(register_command_word(system_id, 0, 'fms', 'data', 'tactical'), 2)
        FMS_COMMAND_WORDS["FMS_TACTICAL_STATUS_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'tactical'), 2)
        
        # Execute maneuver command (using 'data' type with 'maneuver' subtype)
        FMS_COMMAND_WORDS["FMS_EXECUTE_MANEUVER"] = int(register_command_word(system_id, 0, 'fms', 'data', 'maneuver'), 2)
        FMS_COMMAND_WORDS["FMS_EXECUTE_MANEUVER_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'maneuver'), 2)
        
        # Create reverse mapping for name lookup
        FMS_COMMAND_NAME_MAP = {v: k for k, v in FMS_COMMAND_WORDS.items()}
        
        logger.info(f"Registered {len(FMS_COMMAND_WORDS)} FMS command words")
        
        # Update global command maps with FMS entries
        update_command_maps()
        
        return FMS_COMMAND_WORDS
    except ValueError as e:
        # Handle system ID errors specifically
        if "not found in address book" in str(e):
            original_id = str(e).split("System ID ")[1].split(" not found")[0]
            normalized_id = normalize_system_id(original_id)
            
            if normalized_id != original_id:
                # If normalization changed the ID, try again with normalized ID
                logger.warning(f"System ID '{original_id}' not found. Trying with normalized ID '{normalized_id}'")
                try:
                    # Recursive call with normalized ID
                    return register_fms_command_words_with_id(normalized_id)
                except Exception as inner_e:
                    # If that also fails, provide helpful error message
                    logger.error(f"Failed to register FMS command words with normalized ID '{normalized_id}': {inner_e}")
                    raise ValueError(f"FMS system ID error: '{original_id}' not found in address book. "
                                    f"Normalized to '{normalized_id}' but still failed. "
                                    f"Check address_book.xml for valid system IDs.") from inner_e
            else:
                # If normalization didn't change the ID, provide diagnostic information
                logger.error(f"System ID '{original_id}' not found in address book and could not be normalized")
                logger.error("Available system IDs in FMS_SYSTEM_ID_MAP: " + ", ".join(FMS_SYSTEM_ID_MAP.keys()))
                raise ValueError(f"FMS system ID error: '{original_id}' not found in address book. "
                                f"Check address_book.xml for valid system IDs.") from e
        else:
            # For other errors, add context but propagate original error
            logger.error(f"Error registering FMS command words: {e}")
            raise ValueError(f"Error registering FMS command words: {e}") from e
        
def register_fms_command_words_with_id(system_id):
    """
    Register FMS command words with a specific system ID
    
    Args:
        system_id (str): The system ID to use
    
    Returns:
        dict: The registered command words
    """
    global FMS_COMMAND_WORDS, FMS_COMMAND_NAME_MAP
    
    # Clear existing command words to avoid duplicates
    FMS_COMMAND_WORDS.clear()
    
    # Status commands
    FMS_COMMAND_WORDS["FMS_STATUS_REQUEST"] = int(register_command_word(system_id, 0, 'fms', 'status'), 2)
    FMS_COMMAND_WORDS["FMS_STATUS_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'status'), 2)
    
    # Mode commands - use names that match command_registry.xml
    FMS_COMMAND_WORDS["FMS_MODE_CHANGE"] = int(register_command_word(system_id, 0, 'fms', 'mode'), 2)
    FMS_COMMAND_WORDS["FMS_MODE_CHANGE_COMPLETE"] = int(register_command_word(system_id, 1, 'fms', 'mode'), 2)
    
    # Generic command (using 'mode' type since it's a control command)
    FMS_COMMAND_WORDS["FMS_COMMAND"] = int(register_command_word(system_id, 0, 'fms', 'mode'), 2)
    FMS_COMMAND_WORDS["FMS_COMMAND_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'mode'), 2)
    
    # Flight data commands
    FMS_COMMAND_WORDS["FMS_FLIGHT_DATA"] = int(register_command_word(system_id, 0, 'fms', 'data'), 2)
    FMS_COMMAND_WORDS["FMS_FLIGHT_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data'), 2)
    
    # Attitude data
    FMS_COMMAND_WORDS["FMS_UPDATE_ATTITUDE"] = int(register_command_word(system_id, 0, 'fms', 'data', 'attitude'), 2)
    FMS_COMMAND_WORDS["FMS_ATTITUDE_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'attitude'), 2)
    
    # Navigation data
    FMS_COMMAND_WORDS["FMS_UPDATE_NAVIGATION"] = int(register_command_word(system_id, 0, 'fms', 'data', 'navigation'), 2)
    FMS_COMMAND_WORDS["FMS_NAVIGATION_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'navigation'), 2)
    
    # Velocity data
    FMS_COMMAND_WORDS["FMS_UPDATE_VELOCITY"] = int(register_command_word(system_id, 0, 'fms', 'data', 'velocity'), 2)
    FMS_COMMAND_WORDS["FMS_VELOCITY_DATA_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'velocity'), 2)
    
    # Tactical data
    FMS_COMMAND_WORDS["FMS_TACTICAL_STATUS"] = int(register_command_word(system_id, 0, 'fms', 'data', 'tactical'), 2)
    FMS_COMMAND_WORDS["FMS_TACTICAL_STATUS_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'tactical'), 2)
    
    # Execute maneuver command (using 'data' type with 'maneuver' subtype)
    FMS_COMMAND_WORDS["FMS_EXECUTE_MANEUVER"] = int(register_command_word(system_id, 0, 'fms', 'data', 'maneuver'), 2)
    FMS_COMMAND_WORDS["FMS_EXECUTE_MANEUVER_RESPONSE"] = int(register_command_word(system_id, 1, 'fms', 'data', 'maneuver'), 2)
    
    # Create reverse mapping for name lookup
    FMS_COMMAND_NAME_MAP = {v: k for k, v in FMS_COMMAND_WORDS.items()}
    
    logger.info(f"Registered {len(FMS_COMMAND_WORDS)} FMS command words using system ID '{system_id}'")
    
    # Update global command maps with FMS entries
    update_command_maps()
    
    return FMS_COMMAND_WORDS

def get_fms_command_name(command_word: int) -> str:
    """Get the name of an FMS command word"""
    if isinstance(command_word, str):
        # Try to convert from binary string to int
        try:
            command_word = int(command_word, 2)
        except ValueError:
            # If conversion fails, check if it's a hex string
            if command_word.startswith('0x'):
                try:
                    command_word = int(command_word, 16)
                except ValueError:
                    pass
    
    # Return the name if found, otherwise return None
    return FMS_COMMAND_NAME_MAP.get(command_word)

def get_fms_command_word(command_name: str) -> int:
    """Get the command word corresponding to a command name"""
    # Normalize to uppercase for consistency
    command_name = command_name.upper()
    
    # Return the command word if found, otherwise return None
    return FMS_COMMAND_WORDS.get(command_name)

def is_fms_command(command_word) -> bool:
    """Check if a command word is an FMS command"""
    if isinstance(command_word, str):
        # Try to convert from binary string to int
        try:
            command_word = int(command_word, 2)
        except ValueError:
            # If conversion fails, check if it's a hex string
            if command_word.startswith('0x'):
                try:
                    command_word = int(command_word, 16)
                except ValueError:
                    pass
    
    # Check if the command word is in the FMS command word map
    return command_word in FMS_COMMAND_NAME_MAP

def update_command_maps():
    """Update global command maps with FMS entries"""
    from FMOFP.local_messaging.command_word_map import MODE_REQUEST_MAP, STATUS_REQUEST_MAP, DATA_REQUEST_MAP
    
    # Add FMS entries to MODE_REQUEST_MAP for different ID variants
    MODE_REQUEST_MAP['flightmanagementsystem'] = format(FMS_COMMAND_WORDS["FMS_MODE_CHANGE"], '016b')
    MODE_REQUEST_MAP['flightManagementSystem'] = format(FMS_COMMAND_WORDS["FMS_MODE_CHANGE"], '016b')
    # Also add with shortened form for compatibility
    MODE_REQUEST_MAP['fms'] = format(FMS_COMMAND_WORDS["FMS_MODE_CHANGE"], '016b')
    
    # Also update STATUS_REQUEST_MAP with FMS entries
    STATUS_REQUEST_MAP['flightmanagementsystem'] = format(FMS_COMMAND_WORDS["FMS_STATUS_REQUEST"], '016b')
    STATUS_REQUEST_MAP['flightManagementSystem'] = format(FMS_COMMAND_WORDS["FMS_STATUS_REQUEST"], '016b')
    STATUS_REQUEST_MAP['fms'] = format(FMS_COMMAND_WORDS["FMS_STATUS_REQUEST"], '016b')
    
    # Update DATA_REQUEST_MAP with FMS entries
    DATA_REQUEST_MAP['flightmanagementsystem'] = format(FMS_COMMAND_WORDS["FMS_FLIGHT_DATA"], '016b')
    DATA_REQUEST_MAP['flightManagementSystem'] = format(FMS_COMMAND_WORDS["FMS_FLIGHT_DATA"], '016b')
    DATA_REQUEST_MAP['fms'] = format(FMS_COMMAND_WORDS["FMS_FLIGHT_DATA"], '016b')
    
    logger.info(f"Updated global command maps with FMS entries")

# Create FMS data request map
FMS_DATA_REQUEST_MAP = {}

# Export functions and dictionaries
__all__ = [
    'FMS_COMMAND_WORDS',
    'FMS_DATA_TYPES',
    'FMS_MESSAGE_TYPES',
    'FMS_SYSTEM_ID_MAP',
    'register_fms_command_words',
    'register_fms_command_words_with_id',
    'normalize_system_id',
    'get_fms_command_name',
    'get_fms_command_word',
    'is_fms_command',
    'update_command_maps',
    'FMS_DATA_REQUEST_MAP'
]
