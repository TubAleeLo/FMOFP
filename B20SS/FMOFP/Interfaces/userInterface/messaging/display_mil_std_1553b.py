"""
Display-specific MIL-STD-1553B message class.

This is a local version of the MIL_STD_1553B_Message class for use within the display system,
which avoids direct dependencies on the MIL_STD_1553B module.
Uses display-local message types and constants for consistent message handling.
"""

import time
import uuid
import traceback
from typing import Dict, Any, Optional, List, Union

# Import display-local modules
from .display_message_types import translate_message_type
from .display_address_utils import get_rt_address_name, get_subaddress_name

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayMIL_STD_1553B_Message:
    """
    Display-specific implementation of MIL-STD-1553B message.
    
    This class provides the same interface as the original MIL_STD_1553B_Message class,
    but is implemented within the display system boundary.
    Uses display-local message types and constants for consistent message handling.
    
    Notes:
        - Provides both 'subaddress' and 'sub_address' attributes for compatibility
        - Both attributes refer to the same value and are kept in sync
    """
    
    def __init__(self, 
                 rt_address: Optional[str] = None,
                 subaddress: Optional[int] = None,
                 tr_bit: Optional[bool] = None,
                 word_count: Optional[int] = None,
                 data: Optional[Union[str, List[str], Dict[str, Any]]] = None,
                 command_word: Optional[str] = None,
                 status_word: Optional[str] = None,
                 message_type: Optional[str] = None,
                 command_type: Optional[str] = None,
                 request_id: Optional[str] = None,
                 timestamp: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 sub_address: Optional[int] = None):  # Added for compatibility
        """
        Initialize a MIL-STD-1553B message.
        
        Args:
            rt_address: Remote terminal address (binary string)
            subaddress: Subaddress value
            tr_bit: Transmit/receive bit (True for RT to BC, False for BC to RT)
            word_count: Number of data words
            data: Message data (binary string, list of binary strings, or dictionary)
            command_word: Command word (binary string)
            status_word: Status word (binary string)
            message_type: Type of message
            command_type: Type of command
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        try:
            self.rt_address = rt_address
            # Use either subaddress or sub_address, prioritizing subaddress if both are provided
            self._subaddress = subaddress if subaddress is not None else sub_address
            self.tr_bit = tr_bit
            self.word_count = word_count
            self.data = data
            self.command_word = command_word
            self.status_word = status_word
            
            # Translate message type using display-local function
            self.message_type = translate_message_type(message_type) if message_type else None
            
            # If command_type is not provided but message_type is, use message_type as command_type
            self.command_type = command_type or self.message_type
            
            self.request_id = request_id or str(uuid.uuid4())
            self.timestamp = timestamp or time.time()
            self.metadata = metadata or {}
            self.data_word_count = 0
            
            # Set data word count if data is provided
            if isinstance(data, list):
                self.data_word_count = len(data)
            elif isinstance(data, str):
                # For binary string data, calculate word count based on 16-bit words
                if all(c in '01' for c in data):
                    self.data_word_count = (len(data) + 15) // 16  # Round up to nearest 16 bits
                else:
                    self.data_word_count = 1  # Treat as a single word
            elif isinstance(data, dict):
                self.data_word_count = 1  # Treat dictionary as a single word
                
            # Add RT address name and subaddress name to metadata if available
            if self.rt_address:
                # Handle both string and integer rt_address
                if isinstance(self.rt_address, str) and self.rt_address.strip():
                    rt_name = get_rt_address_name(self.rt_address)
                    if rt_name:
                        if not self.metadata:
                            self.metadata = {}
                        self.metadata['rt_name'] = rt_name
                elif isinstance(self.rt_address, int):
                    rt_name = get_rt_address_name(str(self.rt_address))
                    if rt_name:
                        if not self.metadata:
                            self.metadata = {}
                        self.metadata['rt_name'] = rt_name
                    
            if self.subaddress is not None:
                sa_name = get_subaddress_name(self.subaddress)
                if sa_name:
                    if not self.metadata:
                        self.metadata = {}
                    self.metadata['subaddress_name'] = sa_name
                
            # Log creation
            logger.debug(f"Created DisplayMIL_STD_1553B_Message with request_id={self.request_id}, "
                        f"message_type={self.message_type}, rt_address={self.rt_address}, "
                        f"subaddress={self.subaddress}")
        except Exception as e:
            logger.error(f"Error initializing DisplayMIL_STD_1553B_Message: {str(e)}")
            logger.error(traceback.format_exc())
            # Set default values on error
            self.rt_address = None
            self.subaddress = None
            self.tr_bit = None
            self.word_count = 0
            self.data = None
            self.command_word = None
            self.status_word = None
            self.message_type = None
            self.command_type = None
            self.request_id = str(uuid.uuid4())
            self.timestamp = time.time()
            self.metadata = {'error': str(e)}
            self.data_word_count = 0
        
    # Add property accessors for subaddress/sub_address to keep them in sync
    @property
    def subaddress(self) -> Optional[int]:
        """Get subaddress value."""
        return self._subaddress
    
    @subaddress.setter
    def subaddress(self, value: Optional[int]):
        """Set subaddress value and sync with sub_address."""
        self._subaddress = value
    
    @property
    def sub_address(self) -> Optional[int]:
        """Get sub_address value (alias for subaddress)."""
        return self._subaddress
    
    @sub_address.setter
    def sub_address(self, value: Optional[int]):
        """Set sub_address value and sync with subaddress."""
        self._subaddress = value
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dict: Dictionary representation of the message
        """
        try:
            return {
                'rt_address': self.rt_address,
                'subaddress': self.subaddress,
                'sub_address': self.sub_address,  # Include both formats for compatibility
                'tr_bit': self.tr_bit,
                'word_count': self.word_count,
                'data': self.data,
                'command_word': self.command_word,
                'status_word': self.status_word,
                'message_type': self.message_type,
                'command_type': self.command_type,
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'metadata': self.metadata,
                'data_word_count': self.data_word_count
            }
        except Exception as e:
            logger.error(f"Error converting DisplayMIL_STD_1553B_Message to dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal dict on error
            return {
                'error': str(e),
                'request_id': getattr(self, 'request_id', str(uuid.uuid4())),
                'timestamp': time.time()
            }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayMIL_STD_1553B_Message':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            DisplayMIL_STD_1553B_Message: New message instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("Data must be a dictionary")
                
            # Translate message type if present
            message_type = data.get('message_type')
            if message_type:
                message_type = translate_message_type(message_type)
                
            return cls(
                rt_address=data.get('rt_address'),
                subaddress=data.get('subaddress'),
                tr_bit=data.get('tr_bit'),
                word_count=data.get('word_count'),
                data=data.get('data'),
                command_word=data.get('command_word'),
                status_word=data.get('status_word'),
                message_type=message_type,
                command_type=data.get('command_type'),
                request_id=data.get('request_id'),
                timestamp=data.get('timestamp'),
                metadata=data.get('metadata')
            )
        except Exception as e:
            logger.error(f"Error creating DisplayMIL_STD_1553B_Message from dict: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'original_data': str(data)[:100] + '...' if isinstance(data, dict) and len(str(data)) > 100 else str(data)}
            )
        
    @classmethod
    def from_original_message(cls, message: Any) -> 'DisplayMIL_STD_1553B_Message':
        """
        Create a DisplayMIL_STD_1553B_Message from an original MIL_STD_1553B_Message.
        
        Args:
            message: Original MIL_STD_1553B_Message instance
            
        Returns:
            DisplayMIL_STD_1553B_Message: New message instance
        """
        try:
            # Extract all available attributes from the original message
            attributes = {}
            for attr in ['rt_address', 'subaddress', 'tr_bit', 'word_count', 
                        'data', 'command_word', 'status_word', 'message_type', 
                        'command_type', 'request_id', 'timestamp', 'metadata',
                        'data_word_count']:
                if hasattr(message, attr):
                    attributes[attr] = getattr(message, attr)
                    
            # Ensure metadata is a dictionary
            if 'metadata' not in attributes or not attributes['metadata']:
                attributes['metadata'] = {}
            elif not isinstance(attributes['metadata'], dict):
                attributes['metadata'] = {'original_metadata': str(attributes['metadata'])}
                
            # Add original message type if available
            if 'message_type' in attributes and attributes['message_type']:
                attributes['metadata']['original_message_type'] = attributes['message_type']
                # Translate message type
                attributes['message_type'] = translate_message_type(attributes['message_type'])
            
            # Handle both subaddress and sub_address for compatibility
            if 'subaddress' in attributes:
                subaddress = attributes['subaddress']
            elif 'sub_address' in attributes:
                subaddress = attributes['sub_address']
                attributes['subaddress'] = subaddress
            else:
                subaddress = None
                
            # Create new message with extracted attributes
            return cls(**attributes)
        except Exception as e:
            logger.error(f"Error converting original message to DisplayMIL_STD_1553B_Message: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal instance on error
            return cls(
                metadata={'error': str(e), 'conversion_error': True}
            )
        
    def is_valid(self) -> bool:
        """
        Check if this is a valid message that should be processed.
        
        Returns:
            bool: True if the message is valid, False otherwise
        """
        try:
            # Check for required fields
            if not self.rt_address:
                return False
                
            if self.subaddress is None:
                return False
                
            # Check for error in metadata
            if self.metadata and isinstance(self.metadata, dict) and 'error' in self.metadata:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking if message is valid: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """
        Get string representation of the message.
        
        Returns:
            str: String representation
        """
        rt_name = ""
        if self.rt_address and hasattr(self, 'metadata') and isinstance(self.metadata, dict) and 'rt_name' in self.metadata:
            rt_name = f", rt_name={self.metadata['rt_name']}"
            
        sa_name = ""
        if self.subaddress is not None and hasattr(self, 'metadata') and isinstance(self.metadata, dict) and 'subaddress_name' in self.metadata:
            sa_name = f", sa_name={self.metadata['subaddress_name']}"
            
        valid_status = "VALID" if self.is_valid() else "INVALID"
        
        return (f"DisplayMIL_STD_1553B_Message(request_id={self.request_id}, "
                f"message_type={self.message_type}, command_type={self.command_type}, "
                f"rt_address={self.rt_address}{rt_name}, subaddress={self.subaddress}{sa_name}, "
                f"{valid_status})")
