"""
Radar-specific MIL-STD-1553B message handling helpers.
Provides functionality for decoding and encoding 1553B messages on the radar side.
"""

from typing import Dict
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class Radar1553BHelpers:
    # Constants for word sizes
    COMMAND_WORD_SIZE = 20  # bits (3 sync + 16 data + 1 parity)
    STATUS_WORD_SIZE = 20   # bits (3 sync + 16 data + 1 parity)
    DATA_WORD_SIZE = 20     # bits (3 sync + 16 data + 1 parity)
    
    # Bit positions in command word
    CMD_RT_ADDR_START = 3  # Start after sync bits (100)
    CMD_RT_ADDR_END = 8    # End after 5 bits of RT address
    CMD_TR_BIT_POS = 8     # T/R bit follows RT address
    CMD_SUBADDR_START = 9  # Subaddress follows T/R bit
    CMD_SUBADDR_END = 14   # End after 5 bits of subaddress
    CMD_WORDCOUNT_START = 14  # Word count follows subaddress
    CMD_WORDCOUNT_END = 19    # End after 5 bits of word count
    
    # Bit positions in status word
    STATUS_RT_ADDR_START = 3  # Start after sync bits (100)
    STATUS_RT_ADDR_END = 8    # End after 5 bits of RT address
    STATUS_MSG_ERR_POS = 8    # Message error bit follows RT address
    STATUS_INSTR_BIT_POS = 9  # Instrumentation bit follows message error bit
    STATUS_SRV_REQ_POS = 10   # Service request bit follows instrumentation bit
    STATUS_RESERVED = 11      # Reserved bits start position
    STATUS_BUSY_POS = 12      # Busy bit position
    STATUS_SUBSYS_FLAG_POS = 13  # Subsystem flag bit position
    STATUS_DYNAMIC_BUS_POS = 14  # Dynamic bus control bit position
    STATUS_TERM_FLAG_POS = 15    # Terminal flag bit position
    STATUS_PARITY_POS = 19       # Parity bit is the last bit

    @classmethod
    def decode_command_word(cls, command_word: str) -> Dict:
        """
        Decode a 1553B command word binary string into its components.
        
        Args:
            command_word: Binary string of length 20 (3 sync + 16 data + 1 parity)
            
        Returns:
            Dictionary containing decoded command word fields
        """
        try:
            if not isinstance(command_word, str) or len(command_word) != cls.COMMAND_WORD_SIZE:
                raise ValueError(f"Command word must be a {cls.COMMAND_WORD_SIZE}-bit binary string")
            
            # Verify sync bits (first 3 bits should be '100')
            if command_word[:3] != '100':
                raise ValueError("Invalid sync bits in command word")
                
            decoded = {
                'sync': command_word[:3],
                'rt_address': int(command_word[cls.CMD_RT_ADDR_START:cls.CMD_RT_ADDR_END], 2),
                'tr_bit': int(command_word[cls.CMD_TR_BIT_POS]),
                'subaddress_mode': int(command_word[cls.CMD_SUBADDR_START:cls.CMD_SUBADDR_END], 2),
                'word_count_mode': int(command_word[cls.CMD_WORDCOUNT_START:cls.CMD_WORDCOUNT_END], 2),
                'parity': int(command_word[-1])
            }
            
            logger.info(f"Decoded command word: {decoded}")
            return decoded
            
        except Exception as e:
            logger.error(f"Error decoding command word: {str(e)}")
            raise

    @classmethod
    def decode_data_word(cls, data_word: str) -> Dict:
        """
        Decode a 1553B data word binary string.
        
        Args:
            data_word: Binary string of length 20 (3 sync + 16 data + 1 parity)
            
        Returns:
            Dictionary containing decoded data word fields
        """
        try:
            if not isinstance(data_word, str) or len(data_word) != cls.DATA_WORD_SIZE:
                raise ValueError(f"Data word must be a {cls.DATA_WORD_SIZE}-bit binary string")
            
            # Verify sync bits (first 3 bits should be '001')
            if data_word[:3] != '001':
                raise ValueError("Invalid sync bits in data word")
                
            decoded = {
                'sync': data_word[:3],
                'data': int(data_word[3:-1], 2),  # Exclude sync bits and parity
                'parity': int(data_word[-1])
            }
            
            logger.info(f"Decoded data word: {decoded}")
            return decoded
            
        except Exception as e:
            logger.error(f"Error decoding data word: {str(e)}")
            raise

    @classmethod
    def construct_status_word(cls, rt_address: int, message_error: bool = False,
                            instrumentation: bool = False, service_request: bool = False,
                            busy: bool = False, subsystem_flag: bool = False,
                            terminal_flag: bool = False) -> str:
        """
        Construct a 1553B status word binary string.
        
        Args:
            rt_address: Remote Terminal address (5 bits)
            message_error: Message error bit
            instrumentation: Instrumentation bit
            service_request: Service request bit
            busy: Busy bit
            subsystem_flag: Subsystem flag bit
            terminal_flag: Terminal flag bit
            
        Returns:
            Binary string representing the status word
        """
        try:
            if not 0 <= rt_address <= 31:
                raise ValueError("RT address must be within 5-bit range (0-31)")
            
            # Start with sync bits '100'
            status_word = '100'
            
            # Add RT address (5 bits)
            status_word += format(rt_address, '05b')
            
            # Add status bits
            status_word += '1' if message_error else '0'
            status_word += '1' if instrumentation else '0'
            status_word += '1' if service_request else '0'
            status_word += '0'  # Reserved bit
            status_word += '1' if busy else '0'
            status_word += '1' if subsystem_flag else '0'
            status_word += '1' if terminal_flag else '0'
            
            # Add remaining bits including parity
            status_word += '000'  # Reserved bits
            
            # Calculate and add parity bit
            parity = sum(int(bit) for bit in status_word) % 2
            status_word += str(parity)
            
            logger.debug(f"Built status word: {status_word}")
            return status_word
            
        except Exception as e:
            logger.error(f"Error constructing status word: {str(e)}")
            raise ValueError(f"Error constructing status word: {str(e)}")

    @classmethod
    def validate_word(cls, word: str, word_type: str) -> bool:
        """
        Validate a 1553B word's format and parity.
        
        Args:
            word: Binary string to validate
            word_type: Type of word ('command', 'status', or 'data')
            
        Returns:
            True if word is valid, False otherwise
        """
        try:
            if not isinstance(word, str):
                return False
                
            # Check word length based on word type
            if word_type == 'command' and len(word) != cls.COMMAND_WORD_SIZE:
                return False
            elif word_type == 'status' and len(word) != cls.STATUS_WORD_SIZE:
                return False
            elif word_type == 'data' and len(word) != cls.DATA_WORD_SIZE:
                return False
                
            # Check sync bits
            if word_type == 'command' and word[:3] != '100':
                return False
            elif word_type == 'status' and word[:3] != '100':
                return False
            elif word_type == 'data' and word[:3] != '001':
                return False
                
            # Check parity
            parity = sum(int(bit) for bit in word) % 2
            if parity != 0:  # Even parity check
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating {word_type} word: {str(e)}")
            return False
