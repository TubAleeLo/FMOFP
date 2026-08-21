"""
Base class for display-specific message definitions.
"""

import time
import uuid
from typing import Dict, Any, Optional
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayBaseMessage:
    """Base class for all display messages."""
    
    def __init__(self, request_id: Optional[str] = None, timestamp: Optional[float] = None, 
                 metadata: Optional[Dict[str, Any]] = None, message_type: Optional[str] = None):
        """
        Initialize a base display message.
        
        Args:
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
            message_type: Type of message
        """
        self.request_id = request_id or str(uuid.uuid4())
        self.timestamp = timestamp or time.time()
        self.metadata = metadata or {}
        self.message_type = message_type
        
        # Ensure metadata has transaction_id
        if 'transaction_id' not in self.metadata:
            self.metadata['transaction_id'] = str(uuid.uuid4())
            
        # Log creation
        logger.debug(f"Created {self.__class__.__name__} with request_id={self.request_id}")
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dict: Dictionary representation of the message
        """
        return {
            'request_id': self.request_id,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'message_type': self.message_type
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayBaseMessage':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            DisplayBaseMessage: New message instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
            
        return cls(
            request_id=data.get('request_id'),
            timestamp=data.get('timestamp'),
            metadata=data.get('metadata'),
            message_type=data.get('message_type')
        )
        
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the message.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata from the message.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Any: Metadata value or default
        """
        return self.metadata.get(key, default)
        
    def has_metadata(self, key: str) -> bool:
        """
        Check if message has metadata key.
        
        Args:
            key: Metadata key
            
        Returns:
            bool: True if key exists, False otherwise
        """
        return key in self.metadata
        
    def get_transaction_id(self) -> str:
        """
        Get transaction ID from metadata.
        
        Returns:
            str: Transaction ID
        """
        return self.metadata.get('transaction_id', '')
        
    def __str__(self) -> str:
        """
        Get string representation of the message.
        
        Returns:
            str: String representation
        """
        return f"{self.__class__.__name__}(request_id={self.request_id}, message_type={self.message_type})"
