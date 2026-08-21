"""
Mode Change Handler

Specialized handler for mode change messages that follows the standard handler pattern.
Processes mode change requests and responses for various radar systems.
"""

import uuid
import traceback
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.handlers.base_message_handler import BaseMessageHandler
from FMOFP.local_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST,
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    TFR_RADAR_MODE_CHANGE_REQUEST,
    TFR_RADAR_MODE_CHANGE_RESPONSE,
    SAR_RADAR_MODE_CHANGE_REQUEST,
    SAR_RADAR_MODE_CHANGE_RESPONSE,
    TARGETING_RADAR_MODE_CHANGE_REQUEST,
    TARGETING_RADAR_MODE_CHANGE_RESPONSE,
    AEWC_RADAR_MODE_CHANGE_REQUEST,
    AEWC_RADAR_MODE_CHANGE_RESPONSE,
    DISPLAY_MODE_REQUEST,
    DISPLAY_MODE_RESPONSE,
    COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    is_mode_change_message
)
from FMOFP.local_messaging.address_utils import (
    get_rt_address,
    get_subaddress
)

logger = get_logger()

# Singleton instance
_mode_change_handler = None

def get_mode_change_handler():
    """
    Get singleton instance of the ModeChangeHandler.
    
    Returns:
        ModeChangeHandler: Singleton instance of the mode change handler
    """
    global _mode_change_handler
    if _mode_change_handler is None:
        _mode_change_handler = ModeChangeHandler()
    return _mode_change_handler

class ModeChangeHandler(BaseMessageHandler):
    """
    Handler for mode change messages.
    
    Processes mode change requests and responses for various radar systems
    following a standardized pattern.
    """
    
    def __init__(self):
        """Initialize the handler with supported message types."""
        super().__init__()
        
        # List of message types this handler can process
        self.supported_message_types = [
            # Weather Radar
            WEATHER_RADAR_MODE_CHANGE_REQUEST,
            WEATHER_RADAR_MODE_CHANGE_RESPONSE,
            # TFR Radar
            TFR_RADAR_MODE_CHANGE_REQUEST,
            TFR_RADAR_MODE_CHANGE_RESPONSE,
            # SAR Radar
            SAR_RADAR_MODE_CHANGE_REQUEST,
            SAR_RADAR_MODE_CHANGE_RESPONSE,
            # Targeting Radar
            TARGETING_RADAR_MODE_CHANGE_REQUEST,
            TARGETING_RADAR_MODE_CHANGE_RESPONSE,
            # AEWC Radar
            AEWC_RADAR_MODE_CHANGE_REQUEST,
            AEWC_RADAR_MODE_CHANGE_RESPONSE,
            # Display
            DISPLAY_MODE_REQUEST,
            DISPLAY_MODE_RESPONSE
        ]
        
        # Radar type to message type mapping for requests
        self.radar_request_mapping = {
            'weather': WEATHER_RADAR_MODE_CHANGE_REQUEST,
            'tfr': TFR_RADAR_MODE_CHANGE_REQUEST,
            'sar': SAR_RADAR_MODE_CHANGE_REQUEST,
            'targeting': TARGETING_RADAR_MODE_CHANGE_REQUEST,
            'aewc': AEWC_RADAR_MODE_CHANGE_REQUEST
        }
        
        # Radar type to message type mapping for responses
        self.radar_response_mapping = {
            'weather': WEATHER_RADAR_MODE_CHANGE_RESPONSE,
            'tfr': TFR_RADAR_MODE_CHANGE_RESPONSE,
            'sar': SAR_RADAR_MODE_CHANGE_RESPONSE,
            'targeting': TARGETING_RADAR_MODE_CHANGE_RESPONSE,
            'aewc': AEWC_RADAR_MODE_CHANGE_RESPONSE
        }
        
        # Valid radar modes
        self.valid_radar_modes = {
            'STANDBY',
            'SURVEILLANCE',
            'MAPPING',
            'TURBULENCE',
            'WINDSHEAR',
            'NORMAL',
            'TEST'
        }
        
        logger.info("Mode Change Handler initialized with supported message types")
    def get_message_type(self, message):
        """
        Extract message type from a message.
        Handles different message formats.
        
        Args:
            message: The message to extract type from
            
        Returns:
            str: Message type or None if not found
        """
        # Check if it's a dictionary
        if isinstance(message, dict):
            # Try direct message_type field
            if 'message_type' in message:
                return message['message_type']
            
            # Try metadata.message_type
            if 'metadata' in message and isinstance(message['metadata'], dict):
                if 'message_type' in message['metadata']:
                    return message['metadata']['message_type']
            
            # Try additional_info.message_type (for backward compatibility)
            if 'additional_info' in message and isinstance(message['additional_info'], dict):
                if 'message_type' in message['additional_info']:
                    return message['additional_info']['message_type']
        
        # Check if it's an object with message_type attribute
        if hasattr(message, 'message_type'):
            return message.message_type
        
        # Check if it's an object with metadata attribute
        if hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
            return message.metadata.get('message_type')
        
        # If we can't find a message type, return None
        logger.warning("[MODE_HANDLER] Could not determine message type")
        return None
        
    def can_handle(self, message):
        """
        Determine if this handler can process the message.
        Enhanced version with fallback to is_mode_change_message.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if this handler can process the message, False otherwise
        """
        # First check using standard method
        if super().can_handle(message):
            return True
            
        # Fallback to flexible pattern matching for mode change messages
        return is_mode_change_message(message)
    
    async def handle_message(self, message):
        """
        Handle a mode change message.
        
        Args:
            message: The message to handle
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        try:
            # Get base message details
            message_type = self.get_message_type(message)
            
            # Log handling attempt
            logger.info(f"[MODE_HANDLER] Handling message type: {message_type}")
            
            # Determine if request or response
            is_request = False
            is_response = False
            
            # Check message type to determine direction
            for prefix in self.radar_request_mapping.values():
                if message_type and message_type.lower() == prefix.lower():
                    is_request = True
                    break
                    
            for prefix in self.radar_response_mapping.values():
                if message_type and message_type.lower() == prefix.lower():
                    is_response = True
                    break
            
            # Display message handling
            if message_type and message_type.lower() == DISPLAY_MODE_REQUEST.lower():
                is_request = True
            elif message_type and message_type.lower() == DISPLAY_MODE_RESPONSE.lower():
                is_response = True
            
            # Handle based on direction
            if is_request:
                return await self._handle_mode_change_request(message)
            elif is_response:
                return await self._handle_mode_change_response(message)
            else:
                # Try generic handling for unrecognized patterns
                return await self._handle_generic_mode_change(message)
                
        except Exception as e:
            logger.error(f"[MODE_HANDLER] Error handling mode change message: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _handle_mode_change_request(self, message):
        """
        Handle a mode change request message.
        
        Args:
            message: The mode change request message
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        try:
            # Extract basic message properties
            message_type = self.get_message_type(message)
            logger.info(f"[MODE_HANDLER] Processing mode change request: {message_type}")
            
            # Pre-process message to ensure it has the correct structure
            processed_message = self._preprocess_mode_message(message)
            
            # Validate mode if present
            if 'mode' in processed_message:
                if not self._validate_mode(processed_message['mode']):
                    logger.warning(f"[MODE_HANDLER] Invalid mode: {processed_message['mode']}")
                    # Still proceed with processing, as the receiving system should validate
            
            # Ensure transaction ID is present
            transaction_id = self.get_transaction_id(processed_message)
            if not transaction_id:
                # Generate a new transaction ID
                transaction_id = str(uuid.uuid4())
                # Add to processed message
                if 'metadata' not in processed_message:
                    processed_message['metadata'] = {}
                processed_message['metadata']['transaction_id'] = transaction_id
                
                # Also add to additional_info for backward compatibility
                if 'additional_info' not in processed_message:
                    processed_message['additional_info'] = {}
                processed_message['additional_info']['transaction_id'] = transaction_id
            
            # Add command type if not present
            if 'command_type' not in processed_message:
                processed_message['command_type'] = COMMAND_TYPE_MODE_CHANGE
            

            
            # Route to appropriate service based on radar type
            if 'radar_type' in processed_message:
                radar_type = processed_message['radar_type'].lower()
                if radar_type in self.radar_request_mapping:
                    # Set or update the message type based on radar type
                    processed_message['message_type'] = self.radar_request_mapping[radar_type]
                    
                    # Add to metadata too
                    if 'metadata' not in processed_message:
                        processed_message['metadata'] = {}
                    processed_message['metadata']['message_type'] = processed_message['message_type']
                    logger.info(f"[MODE_HANDLER] Set message type to {processed_message['message_type']} based on radar type {radar_type}")
            
            # Forward to appropriate service
            # In a real implementation, this would call a response service adapter
            # await response_service_adapter.handle_mode_change(processed_message)
            
            logger.info(f"[MODE_HANDLER] Successfully processed mode change request with transaction ID {transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"[MODE_HANDLER] Error handling mode change request: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _handle_mode_change_response(self, message):
        """
        Handle a mode change response message.
        
        Args:
            message: The mode change response message
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        try:
            # Extract basic message properties
            message_type = self.get_message_type(message)
            logger.info(f"[MODE_HANDLER] Processing mode change response: {message_type}")
            
            # Pre-process message to ensure it has the correct structure
            processed_message = self._preprocess_mode_message(message)
            
            # Verify transaction ID is present for tracking
            transaction_id = self.get_transaction_id(processed_message)
            if not transaction_id:
                logger.warning("[MODE_HANDLER] Mode change response missing transaction ID")
                # Create one anyway for internal tracking
                transaction_id = str(uuid.uuid4())
                # Add to processed message
                if 'metadata' not in processed_message:
                    processed_message['metadata'] = {}
                processed_message['metadata']['transaction_id'] = transaction_id
            
            # Add command type if not present
            if 'command_type' not in processed_message:
                processed_message['command_type'] = COMMAND_TYPE_MODE_CHANGE_COMPLETE
            
            # Update response status if not present
            if 'status' not in processed_message:
                # Default to success if nothing indicates otherwise
                processed_message['status'] = 'success'
                
                # Add to metadata too
                if 'metadata' not in processed_message:
                    processed_message['metadata'] = {}
                processed_message['metadata']['status'] = processed_message['status']
            
            # Forward to appropriate service
            # In a real implementation, this would call a response service
            # await response_service.process_mode_change_response(processed_message)
            
            logger.info(f"[MODE_HANDLER] Successfully processed mode change response with transaction ID {transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"[MODE_HANDLER] Error handling mode change response: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _handle_generic_mode_change(self, message):
        """
        Handle a mode change message that doesn't match specific patterns.
        Attempts to determine if it's a request or response based on content.
        
        Args:
            message: The mode change message
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        try:
            # Log handling attempt
            logger.info("[MODE_HANDLER] Handling generic mode change message")
            
            # Create a copy to avoid modifying original
            processed_message = message.copy() if isinstance(message, dict) else message
            
            # Try to determine if this is a request or response
            is_request = False
            is_response = False
            
            # Check for clues
            if isinstance(message, dict):
                # Check command type
                command_type = message.get('command_type', '')
                if command_type:
                    if command_type.lower() == COMMAND_TYPE_MODE_CHANGE.lower():
                        is_request = True
                    elif command_type.lower() == COMMAND_TYPE_MODE_CHANGE_COMPLETE.lower():
                        is_response = True
                
                # Check metadata
                if 'metadata' in message and isinstance(message['metadata'], dict):
                    metadata_command_type = message['metadata'].get('command_type', '')
                    if metadata_command_type:
                        if metadata_command_type.lower() == COMMAND_TYPE_MODE_CHANGE.lower():
                            is_request = True
                        elif metadata_command_type.lower() == COMMAND_TYPE_MODE_CHANGE_COMPLETE.lower():
                            is_response = True
                
                # Check message_type for patterns
                message_type = self.get_message_type(message)
                if message_type:
                    if 'request' in message_type.lower():
                        is_request = True
                    elif 'response' in message_type.lower():
                        is_response = True
                
                # Check for mode field - indicates likely request
                if 'mode' in message:
                    is_request = True
                
                # Check for status field - indicates likely response
                if 'status' in message:
                    is_response = True
            
            # Route based on determination
            if is_request:
                logger.info("[MODE_HANDLER] Treating as mode change request")
                return await self._handle_mode_change_request(processed_message)
            elif is_response:
                logger.info("[MODE_HANDLER] Treating as mode change response")
                return await self._handle_mode_change_response(processed_message)
            else:
                # Default to treating as request if we can't determine
                logger.warning("[MODE_HANDLER] Could not determine if request or response - defaulting to request")
                return await self._handle_mode_change_request(processed_message)
                
        except Exception as e:
            logger.error(f"[MODE_HANDLER] Error handling generic mode change message: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _preprocess_mode_message(self, message):
        """
        Preprocess a mode message to ensure it has the correct structure.
        
        Args:
            message: The message to preprocess
            
        Returns:
            dict: The preprocessed message
        """
        # Create a copy to avoid modifying original
        if isinstance(message, dict):
            processed_message = message.copy()
        else:
            # If not a dict, convert to one
            processed_message = {'original_object': message}
            
            # Try to extract fields from object
            if hasattr(message, 'message_type'):
                processed_message['message_type'] = message.message_type
            if hasattr(message, 'command_type'):
                processed_message['command_type'] = message.command_type
            if hasattr(message, 'mode'):
                processed_message['mode'] = message.mode
            if hasattr(message, 'radar_type'):
                processed_message['radar_type'] = message.radar_type
            if hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                processed_message['metadata'] = message.metadata.copy()
        
        # Ensure metadata exists
        if 'metadata' not in processed_message:
            processed_message['metadata'] = {}
            
        # Ensure additional_info exists (for backward compatibility)
        if 'additional_info' not in processed_message:
            processed_message['additional_info'] = {}
        
        # Extract radar type from message type if not directly specified
        if 'radar_type' not in processed_message:
            message_type = self.get_message_type(processed_message)
            if message_type:
                # Try to extract radar type from message type
                for radar_type in self.radar_request_mapping.keys():
                    if radar_type in message_type.lower():
                        processed_message['radar_type'] = radar_type
                        break
        
        # Extract mode from message if in metadata but not in main message
        if 'mode' not in processed_message and 'metadata' in processed_message:
            if 'mode' in processed_message['metadata']:
                processed_message['mode'] = processed_message['metadata']['mode']
        
        # Copy important fields to metadata for consistent access
        for field in ['message_type', 'command_type', 'mode', 'radar_type']:
            if field in processed_message and field not in processed_message['metadata']:
                processed_message['metadata'][field] = processed_message[field]
        
        return processed_message
    
    def _validate_mode(self, mode):
        """
        Validate if a mode is valid.
        
        Args:
            mode: The mode to validate
            
        Returns:
            bool: True if the mode is valid, False otherwise
        """
        if not mode:
            return False
            
        # Convert to uppercase for consistent comparison
        normalized_mode = mode.upper() if isinstance(mode, str) else str(mode).upper()
        
        # Check against valid modes
        return normalized_mode in self.valid_radar_modes
