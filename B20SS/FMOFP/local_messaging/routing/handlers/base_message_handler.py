"""
Base Message Handler

Provides a standard base class for all message handlers in the FMOFP system.
This ensures consistent message handling patterns and reduces duplicate code.
"""

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.message_types import (
    get_message_type, is_message_type
)

logger = get_logger()

class BaseMessageHandler:
    """
    Base class for all message handlers.
    
    Provides standard message handling patterns and utilities to ensure
    consistent behavior across all handler implementations.
    """
    
    def __init__(self):
        """Initialize the handler with supported message types."""
        # List of message types this handler can process
        self.supported_message_types = []
        
        # Set of already processed transaction IDs to prevent loops
        self._processed_transactions = set()
        
        # Maximum size of transaction cache to prevent memory leaks
        self._max_transaction_cache = 1000
        
        logger.info(f"Initialized {self.__class__.__name__}")
    
    def can_handle(self, message):
        """
        Determine if this handler can process the message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if this handler can process the message, False otherwise
        """
        # Get message type
        message_type = get_message_type(message)
        if not message_type:
            return False
            
        # Check if message type is in supported types
        for supported_type in self.supported_message_types:
            if is_message_type(message, supported_type):
                return True
                
        return False
    
    def get_transaction_id(self, message):
        """
        Extract transaction ID from message.
        
        Args:
            message: The message to extract transaction ID from
            
        Returns:
            str: Transaction ID or None if not found
        """
        # Try metadata first (preferred location)
        if isinstance(message, dict):
            # Check in metadata
            if 'metadata' in message and isinstance(message['metadata'], dict):
                if 'transaction_id' in message['metadata']:
                    return message['metadata']['transaction_id']
            
            # Check in additional_info (legacy format)
            if 'additional_info' in message and isinstance(message['additional_info'], dict):
                if 'transaction_id' in message['additional_info']:
                    return message['additional_info']['transaction_id']
                    
        # Try object attributes
        elif hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
            transaction_id = message.metadata.get('transaction_id')
            if transaction_id:
                return transaction_id
                
        # Not found
        return None
    
    def is_already_processed(self, message):
        """
        Check if a message has already been processed.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if already processed, False otherwise
        """
        # Get transaction ID
        transaction_id = self.get_transaction_id(message)
        if not transaction_id:
            # No transaction ID, assume not processed
            return False
            
        # Check if in processed transactions
        return transaction_id in self._processed_transactions
    
    def mark_as_processed(self, message):
        """
        Mark a message as processed to prevent loops.
        
        Args:
            message: The message to mark
        """
        # Get transaction ID
        transaction_id = self.get_transaction_id(message)
        if not transaction_id:
            # No transaction ID, can't mark
            return
            
        # Add to processed transactions
        self._processed_transactions.add(transaction_id)
        
        # Prevent memory leak by limiting cache size
        if len(self._processed_transactions) > self._max_transaction_cache:
            # Remove oldest entries (approximation by converting to list and slicing)
            self._processed_transactions = set(list(self._processed_transactions)[-self._max_transaction_cache:])
    
    def add_processing_flags(self, message):
        """
        Add processing flags to message to prevent loops.
        
        Args:
            message: The message to add flags to
            
        Returns:
            dict: Modified message with processing flags
        """
        if isinstance(message, dict):
            # Ensure metadata exists
            if 'metadata' not in message:
                message['metadata'] = {}
                
            # Add processing flag
            message['metadata'][f'_processed_by_{self.__class__.__name__}'] = True
            
        return message
    
    def handle_message(self, message):
        """
        Handle a message. Must be implemented by subclasses.
        
        Args:
            message: The message to handle
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        raise NotImplementedError("Subclasses must implement handle_message")
    
    async def process(self, message):
        """
        Process a message.
        
        This is the main entry point for message processing. It performs
        standard checks and then calls the handler-specific handle_message.
        
        Args:
            message: The message to process
            
        Returns:
            bool: True if message was processed, False otherwise
        """
        # Check if this handler can handle the message
        if not self.can_handle(message):
            return False
            
        # Check if already processed to prevent loops
        if self.is_already_processed(message):
            logger.info(f"{self.__class__.__name__}: Skipping already processed message")
            return True
            
        # Try to handle the message
        try:
            # Add processing flags
            message = self.add_processing_flags(message)
            
            # Mark as processed
            self.mark_as_processed(message)
            
            # Handle the message
            result = await self.handle_message(message)
            
            # Log result
            if result:
                logger.info(f"{self.__class__.__name__}: Successfully handled message of type: {get_message_type(message)}")
            else:
                logger.warning(f"{self.__class__.__name__}: Failed to handle message of type: {get_message_type(message)}")
                
            return result
            
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: Error handling message: {e}")
            return False
