"""
Base class for all message handlers.
Provides standardized message type identification logic and handler interface.
"""

from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class BaseMessageHandler:
    """Base class for all message handlers."""
    
    def __init__(self):
        """Initialize the handler."""
        # List of message types this handler can process
        # Should be overridden by subclasses
        self.message_types = []
        
    def can_handle(self, message):
        """
        Determine if this handler can process the message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if this handler can process the message, False otherwise
        """
        message_type = get_message_type(message)
        if not message_type:
            logger.debug(f"Message has no message_type, cannot be handled: {message}")
            return False
        
        # Case-insensitive comparison with all supported message types    
        for mt in self.message_types:
            if isinstance(mt, str) and message_type.lower() == mt.lower():
                logger.debug(f"Handler can process message type: {message_type}")
                return True
        
        logger.debug(f"Handler cannot process message type: {message_type}")
        return False
        
    def handle_message(self, message):
        """
        Handle the message. Must be implemented by subclasses.
        
        Args:
            message: The message to handle
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        raise NotImplementedError("Subclasses must implement handle_message")
    
    def pre_process_message(self, message):
        """
        Pre-process a message before handling.
        Can be overridden by subclasses to add custom pre-processing.
        
        Args:
            message: The message to process
            
        Returns:
            dict: The processed message
        """
        # Default implementation just returns the message unchanged
        return message
    
    def post_process_result(self, result, original_message):
        """
        Post-process the result of handling a message.
        Can be overridden by subclasses to add custom post-processing.
        
        Args:
            result: The result of handling the message
            original_message: The original message that was handled
            
        Returns:
            Any: The processed result
        """
        # Default implementation just returns the result unchanged
        return result
    
    def validate_message(self, message):
        """
        Validate that a message has all required fields.
        Can be overridden by subclasses for specific validation rules.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if the message is valid, False otherwise
        """
        # Basic validation: message must have a message_type
        if not get_message_type(message):
            logger.warning("Message missing required message_type field")
            return False
        
        # Default implementation just checks if we can handle it
        return self.can_handle(message)

    def __str__(self):
        """String representation of the handler."""
        return f"{self.__class__.__name__} (handles: {', '.join(self.message_types)})"
