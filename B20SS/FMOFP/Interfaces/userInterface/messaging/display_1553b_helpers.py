"""
Display-specific MIL-STD-1553B message handling helpers.
Provides functionality for decoding and encoding 1553B messages on the display side.
"""

from typing import Dict, Tuple, Union
from ..displays.base_display import DisplayType, DisplayMode
from .display_address_utils import (
    DISPLAY_RT_ADDRESS,
    get_display_rt_address,
    get_display_subaddress,
    get_display_id_by_subaddress
)
from .display_message_types import (
    get_command_type,
    DISPLAY_COMMAND_TYPE_SHOW,
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_DATA,
    DISPLAY_COMMAND_TYPE_STATUS
)
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class Display1553BHelpers:
    # Constants for word sizes
    COMMAND_WORD_SIZE = 20  # bits (including sync and parity)
    STATUS_WORD_SIZE = 20   # bits (including sync and parity)
    DATA_WORD_SIZE = 20     # bits (including sync and parity)
    
    # Sync patterns
    SYNC_RT_TO_BC = '100'  # RT to BC sync pattern
    SYNC_BC_TO_RT = '100'  # BC to RT sync pattern
    SYNC_DATA = '001'      # Data word sync pattern
    
    # RT address for display system - use address utility
    RT_ADDRESS = DISPLAY_RT_ADDRESS
    
    # Bit positions in command word
    CMD_RT_ADDR_START = 3
    CMD_RT_ADDR_END = 8
    CMD_TR_BIT_POS = 8
    CMD_SUBADDR_START = 9
    CMD_SUBADDR_END = 14
    CMD_WORDCOUNT_START = 14
    CMD_WORDCOUNT_END = 19
    CMD_PARITY_POS = 19
    
    # Bit positions in status word
    STATUS_RT_ADDR_START = 3
    STATUS_RT_ADDR_END = 8
    STATUS_MSG_ERR_POS = 8
    STATUS_INSTR_BIT_POS = 9
    STATUS_SRV_REQ_POS = 10
    STATUS_RESERVED = 11
    STATUS_BUSY_POS = 12
    STATUS_SUBSYS_FLAG_POS = 13
    STATUS_DYNAMIC_BUS_POS = 14
    STATUS_TERM_FLAG_POS = 15
    STATUS_PARITY_POS = 19

    @classmethod
    def calculate_parity(cls, bits: str) -> str:
        """Calculate odd parity bit for a binary string according to MIL-STD-1553B."""
        try:
            # Count number of 1s
            ones = sum(int(bit) for bit in bits)
            # Return parity bit to make total number of 1s odd (MIL-STD-1553B uses odd parity)
            return '0' if ones % 2 else '1'
        except Exception as e:
            logger.error(f"Error calculating parity: {str(e)}")
            raise

    @classmethod
    def construct_status_word(cls, message_error: bool = False,
                            instrumentation: bool = False, service_request: bool = False,
                            busy: bool = False, subsystem_flag: bool = False,
                            terminal_flag: bool = False) -> str:
        """
        Construct a 1553B status word binary string.
        
        Args:
            message_error: Message error bit
            instrumentation: Instrumentation bit
            service_request: Service request bit
            busy: Busy bit
            subsystem_flag: Subsystem flag bit
            terminal_flag: Terminal flag bit
            
        Returns:
            Binary string representing the status word
            
        Raises:
            ValueError: If any parameter is invalid
        """
        try:
            # Start with sync pattern
            status_word = list(cls.SYNC_RT_TO_BC)
            
            # Add RT address - convert to binary string if needed
            rt_address_binary = cls.RT_ADDRESS
            if isinstance(rt_address_binary, int):
                # Convert to 5-bit binary string (standard RT address length in 1553B)
                rt_address_binary = format(rt_address_binary, '05b')
            
            # Now extend with the binary representation
            status_word.extend(rt_address_binary)
            
            # Add status bits
            status_word.append('1' if message_error else '0')
            status_word.append('1' if instrumentation else '0')
            status_word.append('1' if service_request else '0')
            status_word.append('0')  # Reserved bit
            status_word.append('1' if busy else '0')
            status_word.append('1' if subsystem_flag else '0')
            status_word.append('0')  # Dynamic bus control acceptance
            status_word.append('1' if terminal_flag else '0')
            status_word.extend('000')  # Reserved bits
            
            # Calculate and add parity
            status_bits = ''.join(status_word)
            parity = cls.calculate_parity(status_bits)
            status_word.append(parity)
            
            result = ''.join(status_word)
            if len(result) != cls.STATUS_WORD_SIZE:
                raise ValueError(f"[1553] Invalid status word length: {len(result)}")
                
            logger.debug(f"[1553] RT constructed status word: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[1553] Error constructing status word: {str(e)}")
            raise

    @classmethod
    def construct_bc_poll_frame(cls) -> str:
        """
        Construct a BC poll frame for display system.
        
        Returns:
            Binary string representing the BC poll frame
            
        Raises:
            ValueError: If frame construction fails
        """
        try:
            # Start with sync pattern
            frame = list(cls.SYNC_BC_TO_RT)
            
            # Add RT address
            frame.extend(cls.RT_ADDRESS)
            
            # Add T/R bit (1 for RT to BC)
            frame.append('1')
            
            # Add subaddress (00000 for mode code)
            frame.extend('00000')
            
            # Add word count (00000)
            frame.extend('00000')
            
            # Calculate and add parity
            frame_bits = ''.join(frame)
            parity = cls.calculate_parity(frame_bits)
            frame.append(parity)
            
            result = ''.join(frame)
            if len(result) != cls.COMMAND_WORD_SIZE:
                raise ValueError(f"[1553] Invalid BC poll frame length: {len(result)}")
                
            logger.debug(f"[1553] BC poll frame constructed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[1553] Error constructing BC poll frame: {str(e)}")
            raise

    @classmethod
    def validate_status_word(cls, status_word: str) -> Tuple[bool, Dict[str, bool]]:
        """
        Validate a status word and extract its components.
        
        Args:
            status_word: Binary string status word
            
        Returns:
            Tuple of (is_valid, components_dict)
            
        Raises:
            ValueError: If status word format is invalid
        """
        try:
            if not isinstance(status_word, str):
                logger.error("[1553] Status word must be a string")
                return False, {}
                
            if len(status_word) != cls.STATUS_WORD_SIZE:
                logger.error(f"[1553] Invalid status word length: {len(status_word)}")
                return False, {}
                
            # Verify sync pattern
            if status_word[:3] != cls.SYNC_RT_TO_BC:
                logger.error(f"[1553] Invalid sync pattern: {status_word[:3]}")
                return False, {}
                
            # Verify RT address
            if status_word[cls.STATUS_RT_ADDR_START:cls.STATUS_RT_ADDR_END] != cls.RT_ADDRESS:
                logger.error("[1553] Invalid RT address")
                return False, {}
                
            # Extract components
            components = {
                'message_error': bool(int(status_word[cls.STATUS_MSG_ERR_POS])),
                'instrumentation': bool(int(status_word[cls.STATUS_INSTR_BIT_POS])),
                'service_request': bool(int(status_word[cls.STATUS_SRV_REQ_POS])),
                'busy': bool(int(status_word[cls.STATUS_BUSY_POS])),
                'subsystem_flag': bool(int(status_word[cls.STATUS_SUBSYS_FLAG_POS])),
                'terminal_flag': bool(int(status_word[cls.STATUS_TERM_FLAG_POS]))
            }
            
            # Verify parity
            expected_parity = cls.calculate_parity(status_word[:-1])
            actual_parity = status_word[-1]
            if expected_parity != actual_parity:
                logger.error("[1553] Parity check failed")
                return False, components
                
            return True, components
            
        except Exception as e:
            logger.error(f"[1553] Error validating status word: {str(e)}")
            return False, {}

def get_display_type(display_name: str) -> Union[DisplayType, None]:
    """
    Convert display name to DisplayType enum.
    
    Args:
        display_name: Name of the display
        
    Returns:
        DisplayType enum or None if invalid
        
    Raises:
        ValueError: If display name is invalid
    """
    try:
        # Normalize display name
        display_name = display_name.lower()
        
        # If it's already a DisplayType name, just use it
        if hasattr(DisplayType, display_name.upper()):
            logger.debug(f"Found direct DisplayType match: {display_name.upper()}")
            return DisplayType[display_name.upper()]
            
        # Try legacy format (with display_ prefix)
        type_name = display_name.replace('display_', '').upper()
        if hasattr(DisplayType, type_name):
            logger.debug(f"[1553] Found legacy format match: {type_name}")
            return DisplayType[type_name]
            
        # Handle special cases with mapping
        special_cases = {
            'radar_display': DisplayType.RADAR,
            'weather_radar': DisplayType.RADAR,  # Add weather_radar mapping
            # Add any other special cases here if needed
        }
        
        if display_name in special_cases:
            logger.debug(f"[1553] Found special case match: {display_name} -> {special_cases[display_name]}")
            return special_cases[display_name]
            
        # Try to get subaddress for display name
        try:
            subaddress = get_display_subaddress(display_name)
            if subaddress:
                # Map subaddress to DisplayType
                if display_name == 'pfd':
                    return DisplayType.PFD
                elif display_name == 'mfd':
                    return DisplayType.MFD
                elif display_name == 'eicas':
                    return DisplayType.EICAS
                elif display_name in ('radar_display', 'weather_radar'):
                    return DisplayType.RADAR
                elif display_name == 'tsd':
                    return DisplayType.TSD
                elif display_name == 'sms':
                    return DisplayType.SMS
        except ValueError:
            # If get_display_subaddress fails, continue to next check
            pass
            
        # If we get here, it's truly invalid
        raise ValueError(f"[1553] Invalid display type: {display_name}")
        
    except Exception as e:
        logger.error(f"[1553] Error getting display type: {str(e)}")
        logger.error(f"[1553] Failed to convert '{display_name}' to DisplayType")
        return None

def get_display_mode(mode_data: str) -> Union[DisplayMode, None]:
    """
    Convert binary mode data to DisplayMode enum.
    
    Args:
        mode_data: Binary string containing mode value
        
    Returns:
        DisplayMode enum or None if invalid
        
    Raises:
        ValueError: If mode data is invalid
    """
    try:
        # Extract actual data bits (skip sync and parity)
        if len(mode_data) == 20:  # Full data word
            data_bits = mode_data[3:-1]  # Remove sync and parity
        else:
            data_bits = mode_data
            
        # Convert to integer
        data_value = int(data_bits, 2)
        
        # Mode value is in upper byte, command type is in lower byte
        # Extract just the mode value from the upper byte
        mode_value = (data_value >> 8) & 0xFF
        
        # Log the extraction for debugging
        logger.info(f"[1553] Extracted mode value {mode_value} from data value {data_value}")
        
        # Validate mode value
        if not hasattr(DisplayMode, str(mode_value)):
            raise ValueError(f"[1553] Invalid mode value: {mode_value}")
            
        return DisplayMode(mode_value)
        
    except Exception as e:
        logger.error(f"[1553] Error getting display mode: {str(e)}")
        return None

def parse_command_data(data: str) -> Tuple[str, str]:
    """
    Parse command type and data from message data.
    Handles data word format according to MIL-STD-1553B.
    
    Args:
        data: Binary string containing command data
        
    Returns:
        Tuple of (command_type, command_data)
        
    Raises:
        ValueError: If data format is invalid
    """
    try:
        if not isinstance(data, str):
            raise ValueError("[1553] Data must be a string")
            
        # Skip sync pattern if present
        if len(data) == 20:  # Full data word
            if data[:3] != Display1553BHelpers.SYNC_DATA:
                raise ValueError(f"[1553] Invalid sync pattern: {data[:3]}")
            data = data[3:-1]  # Remove sync and parity
            
        if len(data) != 16:
            raise ValueError(f"[1553] Invalid data length: {len(data)}")
            
        command_type = data[:8]  # First byte for command type
        command_data = data[8:]  # Remaining data
        return command_type, command_data
        
    except Exception as e:
        logger.error(f"[1553] Error parsing command data: {str(e)}")
        return '', ''
