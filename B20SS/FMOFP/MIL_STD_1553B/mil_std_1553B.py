"""
MIL-STD-1553B Message Format Implementation

Handles message formatting and validation according to MIL-STD-1553B standard.
Improved implementation to ensure protocol compliance and consistent metadata handling.
"""

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.message_utils import (
    get_message_type, is_mode_change_message,
    is_vil_message, is_precipitation_message
)
from FMOFP.MIL_STD_1553B.address_utils import (
    get_rt_address, get_subaddress,
    is_valid_rt_address, is_valid_subaddress,
    validate_mil_std_1553b_address
)

logger = get_logger()

class MIL_STD_1553B_Message:
    """
    MIL-STD-1553B Message class with enhanced protocol compliance.
    
    This class represents a MIL-STD-1553B message with proper RT/SA addressing
    and protocol validation according to the  standard.
    """
    
    # MIL-STD-1553B Constants
    COMMAND_WORD_SIZE = 16  # bits
    DATA_WORD_SIZE = 16  # bits
    MAX_DATA_WORDS = 32
    STATUS_WORD_SIZE = 16  # bits
    BLOCK_STATUS_FLAG_BIT = 8  # Block status flag bit in status word
    SERVICE_REQUEST_BIT = 11  # Service request bit in status word
    
    # Message Direction Constants
    BC_TO_RT = 0  # Bus Controller to Remote Terminal
    RT_TO_BC = 1  # Remote Terminal to Bus Controller
    RT_TO_RT = 2  # Remote Terminal to Remote Terminal
    
    # Transfer Types
    STANDARD_TRANSFER = 0
    BLOCK_TRANSFER = 1
    
    def __init__(self, rt_address, sub_address, data, message_type=None, original_message_type=None, 
                 command_type=None, command_name=None, data_word_count=None, metadata=None,
                 direction=0, transfer_type=0):
        """Initialize MIL-STD-1553B message.
        
        Args:
            rt_address (int): Remote Terminal address (0-31)
            sub_address (int): Subaddress (0-31, 31 for mode codes)
            data (str|list): Binary string or list of integers
            message_type (str, optional): Message type identifier
            original_message_type (str, optional): Original message type before RT processing
            command_type (str, optional): Command type identifier (mode, data, status, etc.)
            command_name (str, optional): Command name for specific command identification
            data_word_count (int, optional): Number of data words in this message
            metadata (dict, optional): Additional metadata for message routing and processing
            direction (int, optional): Message direction (0=BC->RT, 1=RT->BC, 2=RT->RT)
            transfer_type (int, optional): Transfer type (0=standard, 1=block)
        """
        # Validate RT address
        if not isinstance(rt_address, int) or not (0 <= rt_address <= 31):
            raise ValueError(f"RT address must be within 5-bit range (0-31), got {rt_address}")
        
        # Validate subaddress
        if not isinstance(sub_address, int) or not (0 <= sub_address <= 31):
            raise ValueError(f"Subaddress must be within 5-bit range (0-31), got {sub_address}")
        
        # Store core fields
        self.rt_address = rt_address
        self.sub_address = sub_address
        self.message_type = message_type
        self.original_message_type = original_message_type
        self.command_type = command_type
        self.command_name = command_name
        self.data_word_count = data_word_count
        self.direction = direction
        self.transfer_type = transfer_type
        
        # Initialize metadata dictionary with default fields if not provided
        self.metadata = metadata if metadata is not None else {}
        
        # Ensure critical fields are in metadata for consistent access
        # This allows unified access pattern via metadata
        if command_type and 'command_type' not in self.metadata:
            self.metadata['command_type'] = command_type
        if command_name and 'command_name' not in self.metadata:
            self.metadata['command_name'] = command_name
        if message_type and 'message_type' not in self.metadata:
            self.metadata['message_type'] = message_type
        if original_message_type and 'original_message_type' not in self.metadata:
            self.metadata['original_message_type'] = original_message_type
        if 'rt_address' not in self.metadata:
            self.metadata['rt_address'] = rt_address
        if 'sub_address' not in self.metadata:
            self.metadata['sub_address'] = sub_address
        if direction is not None and 'direction' not in self.metadata:
            self.metadata['direction'] = direction
        if transfer_type is not None and 'transfer_type' not in self.metadata:
            self.metadata['transfer_type'] = transfer_type
        
        # Process data based on its type
        if isinstance(data, str):
            # Assume data is a binary string
            if len(data) > self.MAX_DATA_WORDS * self.DATA_WORD_SIZE:
                raise ValueError(f"Data exceeds maximum allowed size of {self.MAX_DATA_WORDS} words")
            self.data = data
        elif isinstance(data, list):
            # Assume data is a list of integers
            if len(data) > self.MAX_DATA_WORDS:
                raise ValueError(f"Data exceeds maximum allowed size of {self.MAX_DATA_WORDS} words")
            # Convert list of integers to binary string
            self.data = ''.join(format(word, f'0{self.DATA_WORD_SIZE}b') for word in data)
        else:
            raise ValueError(f"Data must be either a binary string or a list of integers, got {type(data)}")
        
        # Calculate word count if not specified
        if self.data_word_count is None:
            self.data_word_count = len(self.data) // self.DATA_WORD_SIZE
            self.metadata['data_word_count'] = self.data_word_count

    def to_binary(self):
        """
        Convert message to binary format according to MIL-STD-1553B.
        
        Returns:
            str: Binary representation of the message
        """
        # Format command word: RT address (5 bits) + T/R bit (1 bit) + Subaddress (5 bits) + Word Count (5 bits)
        t_r_bit = '1' if self.direction == self.RT_TO_BC else '0'
        command_word = format(self.rt_address, '05b') + t_r_bit + format(self.sub_address, '05b') + format(self.data_word_count, '05b')
        
        # For standard transfers, simply append the data
        if self.transfer_type == self.STANDARD_TRANSFER:
            return command_word + self.data
        
        # For block transfers, insert block status word
        else:
            # Create block status word - bit 8 set for block transfer
            status_word = format(self.rt_address, '05b') + '00000' + '1' + '00000'
            return command_word + status_word + self.data

    @classmethod
    def from_binary(cls, binary_data, message_type=None, metadata=None):
        """
        Create message from binary data according to MIL-STD-1553B.
        
        Args:
            binary_data (str): Binary string containing command word and data
            message_type (str, optional): Message type identifier
            metadata (dict, optional): Additional metadata for message
            
        Returns:
            MIL_STD_1553B_Message: Parsed message object
        """
        if len(binary_data) < cls.COMMAND_WORD_SIZE:
            raise ValueError(f"Invalid frame size: too short for command word, got {len(binary_data)} bits")
        
        # Parse command word
        command_word = binary_data[:cls.COMMAND_WORD_SIZE]
        rt_address = int(command_word[:5], 2)
        t_r_bit = int(command_word[5], 2)
        sub_address = int(command_word[6:11], 2)
        word_count = int(command_word[11:], 2)
        
        # Set direction based on T/R bit
        direction = cls.RT_TO_BC if t_r_bit == 1 else cls.BC_TO_RT
        
        # Calculate expected length
        expected_length = cls.COMMAND_WORD_SIZE + word_count * cls.DATA_WORD_SIZE
        
        # Check for block transfer format
        transfer_type = cls.STANDARD_TRANSFER
        data_start = cls.COMMAND_WORD_SIZE
        
        # If this looks like a block transfer (status word present)
        if len(binary_data) >= expected_length + cls.STATUS_WORD_SIZE:
            # Check if status word has block transfer bit set
            status_word = binary_data[cls.COMMAND_WORD_SIZE:cls.COMMAND_WORD_SIZE + cls.STATUS_WORD_SIZE]
            if status_word[cls.BLOCK_STATUS_FLAG_BIT] == '1':
                transfer_type = cls.BLOCK_TRANSFER
                data_start = cls.COMMAND_WORD_SIZE + cls.STATUS_WORD_SIZE
                expected_length += cls.STATUS_WORD_SIZE
        
        # Validate message length
        if len(binary_data) != expected_length:
            raise ValueError(f"Invalid frame size: expected {expected_length} bits, got {len(binary_data)}")
        
        # Extract data portion
        data = binary_data[data_start:]
        
        # Create metadata if not provided
        if metadata is None:
            metadata = {}
        
        # Add decoded fields to metadata
        metadata['direction'] = direction
        metadata['transfer_type'] = transfer_type
        metadata['data_word_count'] = word_count
        
        # Create message object
        return cls(rt_address, sub_address, data, message_type, 
                  data_word_count=word_count, metadata=metadata,
                  direction=direction, transfer_type=transfer_type)

    @classmethod
    def from_dict(cls, message_dict):
        """
        Create message from dictionary representation.
        
        Args:
            message_dict (dict): Dictionary containing message fields
            
        Returns:
            MIL_STD_1553B_Message: Constructed message object
        """
        # Extract required fields
        rt_address = message_dict.get('rt_address')
        sub_address = message_dict.get('sub_address')
        data = message_dict.get('data', '')
        
        # Validate required fields
        if rt_address is None or sub_address is None:
            raise ValueError("Message dictionary must contain 'rt_address' and 'sub_address'")
        
        # Extract optional fields
        message_type = message_dict.get('message_type')
        command_type = message_dict.get('command_type')
        command_name = message_dict.get('command_name')
        original_message_type = message_dict.get('original_message_type')
        data_word_count = message_dict.get('data_word_count')
        direction = message_dict.get('direction', cls.BC_TO_RT)
        transfer_type = message_dict.get('transfer_type', cls.STANDARD_TRANSFER)
        
        # Extract metadata, merging from multiple possible locations
        metadata = {}
        
        # Add fields from metadata if present
        if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
            metadata.update(message_dict['metadata'])
        
        # Add fields from additional_info if present (legacy format)
        if 'additional_info' in message_dict and isinstance(message_dict['additional_info'], dict):
            metadata.update(message_dict['additional_info'])
        
        # Create message object
        return cls(rt_address, sub_address, data, message_type, original_message_type,
                  command_type, command_name, data_word_count, metadata,
                  direction, transfer_type)

    def to_dict(self):
        """
        Convert message to dictionary representation.
        
        Returns:
            dict: Dictionary containing message fields
        """
        # Create base dictionary with core fields
        result = {
            'rt_address': self.rt_address,
            'sub_address': self.sub_address,
            'data': self.data,
            'message_type': self.message_type,
            'command_type': self.command_type,
            'command_name': self.command_name,
            'metadata': self.metadata.copy()  # Copy to avoid modifying original
        }
        
        # Add optional fields if present
        if self.original_message_type:
            result['original_message_type'] = self.original_message_type
        
        if self.data_word_count is not None:
            result['data_word_count'] = self.data_word_count
            
        # Add direction and transfer type
        result['direction'] = self.direction
        result['transfer_type'] = self.transfer_type
        
        # For backward compatibility, include core fields in additional_info
        result['additional_info'] = {
            'message_type': self.message_type,
            'command_type': self.command_type,
            'command_name': self.command_name,
            'rt_address': self.rt_address,
            'sub_address': self.sub_address
        }
        
        return result

    def is_mode_code(self):
        """
        Check if this message contains a mode code command.
        In MIL-STD-1553B, subaddress 31 (0x1F) is reserved for mode codes.
        
        Returns:
            bool: True if message contains a mode code, False otherwise
        """
        return self.sub_address == 31

    def is_block_transfer(self):
        """
        Check if this message is a block transfer.
        
        Returns:
            bool: True if message is a block transfer, False otherwise
        """
        return self.transfer_type == self.BLOCK_TRANSFER

    def is_mode_change(self):
        """
        Check if this message is a mode change message.
        Uses consistent pattern detection from message_types module.
        
        Returns:
            bool: True if message is a mode change message, False otherwise
        """
        return is_mode_change_message(self.to_dict())

    def is_vil_data(self):
        """
        Check if this message contains VIL data.
        Uses consistent pattern detection from message_types module.
        
        Returns:
            bool: True if message contains VIL data, False otherwise
        """
        return is_vil_message(self.to_dict())

    def is_precipitation_data(self):
        """
        Check if this message contains precipitation data.
        Uses consistent pattern detection from message_types module.
        
        Returns:
            bool: True if message contains precipitation data, False otherwise
        """
        return is_precipitation_message(self.to_dict())

    def __str__(self):
        """String representation of message."""
        direction_str = "RT→BC" if self.direction == self.RT_TO_BC else "BC→RT"
        transfer_str = "Block" if self.transfer_type == self.BLOCK_TRANSFER else "Standard"
        
        return (f"MIL-STD-1553B Message: RT={self.rt_address}, "
                f"SA={self.sub_address}, Type={self.message_type}, "
                f"Dir={direction_str}, Transfer={transfer_str}, "
                f"Words={self.data_word_count}")

    def __repr__(self):
        """Detailed string representation of message."""
        return (f"MIL_STD_1553B_Message(rt_address={self.rt_address}, "
                f"sub_address={self.sub_address}, data='{self.data[:20]}...', "
                f"message_type='{self.message_type}', direction={self.direction}, "
                f"transfer_type={self.transfer_type})")

logger.info("Enhanced MIL_STD_1553B_Message class loaded with protocol compliance features")
