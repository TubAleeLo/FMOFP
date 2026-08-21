"""
Display Metadata Decoder

Extends the MIL-STD-1553B Metadata Codec with display-specific message type translations.
Uses display-local message types and constants for consistent message handling.
"""

import traceback
from typing import Dict, Any, Optional, Union

# Import display-local modules
from .display_message_types import (
    DISPLAY_VIL_DATA, DISPLAY_PRECIPITATION_DATA, DISPLAY_ECHO_TOP_DATA,
    DISPLAY_COMMAND_TYPE_MODE, DISPLAY_COMMAND_TYPE_MODE_CHANGE, DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    DISPLAY_PRECIPITATION_COMPLETION, DISPLAY_VIL_COMPLETION, DISPLAY_STATUS_WORD,
    DISPLAY_TRANSFER_INIT, DISPLAY_TRANSFER_DATA, DISPLAY_TRANSFER_COMPLETE, DISPLAY_DATA_MESSAGE_TYPE,
    translate_message_type as translate_type, is_precipitation_message, is_vil_message
)

# Import MIL-STD-1553B Metadata Codec
from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayMetadataDecoder:
    """
    Display-specific metadata decoder that extends the functionality of MetadataCodec
    with display-specific message type translations.
    Uses display-local message types and constants for consistent message handling.
    """
    
    # Use constants from display_message_types instead of hardcoded strings
    DISPLAY_MESSAGE_TYPE_MAP = {
        # Standard mappings
        "weather_radarCommand": DISPLAY_COMMAND_TYPE_MODE_CHANGE,
        "weather_radarModeChangeRequest": DISPLAY_COMMAND_TYPE_MODE_CHANGE,
        "weather_radarModeChangeCompletion": DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE,
        
        # Precipitation message types
        "weather_radarPrecipitationRequest": DISPLAY_PRECIPITATION_DATA,
        "weather_radarPrecipitationResponse": DISPLAY_PRECIPITATION_DATA,
        "weather_radarPrecipitationCompletion": DISPLAY_PRECIPITATION_COMPLETION,
        
        # VIL message types
        "weather_radarVILRequest": DISPLAY_VIL_DATA,
        "weather_radarVILResponse": DISPLAY_VIL_DATA,
        "weather_radarVILCompletion": DISPLAY_VIL_COMPLETION,
        
        # Explicitly defined message types to replace dynamic type generation
        DISPLAY_COMMAND_TYPE_MODE_CHANGE: DISPLAY_COMMAND_TYPE_MODE_CHANGE,
        DISPLAY_PRECIPITATION_DATA: DISPLAY_PRECIPITATION_DATA,
        DISPLAY_VIL_DATA: DISPLAY_VIL_DATA,
        # NOTE: status_word/transfer_*/display_data are also used as raw
        # string literals in many other files (BC.py, routing_registry.py,
        # weather_message_type_detector.py, precipitation_data_handler.py,
        # etc.) - the values below are intentionally unchanged from those
        # literals, this only gives this map named constants instead of
        # inline magic strings for consistency with the entries above.
        DISPLAY_STATUS_WORD: DISPLAY_STATUS_WORD,
        DISPLAY_TRANSFER_INIT: DISPLAY_TRANSFER_INIT,
        DISPLAY_TRANSFER_DATA: DISPLAY_TRANSFER_DATA,
        DISPLAY_TRANSFER_COMPLETE: DISPLAY_TRANSFER_COMPLETE,
        DISPLAY_DATA_MESSAGE_TYPE: DISPLAY_DATA_MESSAGE_TYPE,
        "display_precipitation_data": DISPLAY_PRECIPITATION_DATA,
        "display_vil_data": DISPLAY_VIL_DATA
    }
    
    @classmethod
    def translate_message_type(cls, message_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Translate a message type to its display-specific equivalent.
        Uses display-local message types and constants for consistent message handling.
        
        Args:
            message_type: The original message type
            context: Optional context metadata for context-aware translation
            
        Returns:
            str: The translated message type for display system
        """
        try:
            if not message_type:
                return None
                
            # Special handling for status_word based on context
            if message_type == "status_word":
                # If we have context with command_type, use it to determine the appropriate translation
                if context and isinstance(context, dict):
                    command_type = context.get('command_type')
                    
                    # Translate status words based on the command_type they're acknowledging
                    if command_type == DISPLAY_PRECIPITATION_DATA or is_precipitation_message({"command_type": command_type}):
                        translated_type = "precipitation_acknowledgment"
                        logger.info(f"[DISPLAY_DECODER] Status word for precipitation data: {message_type} -> {translated_type}")
                        return translated_type
                    elif command_type == 'data' or command_type == 'data_command':
                        translated_type = "data_acknowledgment"
                        logger.info(f"[DISPLAY_DECODER] Status word for general data command: {message_type} -> {translated_type}")
                        return translated_type
                    elif command_type == DISPLAY_VIL_DATA or is_vil_message({"command_type": command_type}):
                        translated_type = "vil_acknowledgment"
                        logger.info(f"[DISPLAY_DECODER] Status word for VIL data: {message_type} -> {translated_type}")
                        return translated_type
                    else:
                        # Log warning but don't raise exception - return original type instead
                        logger.warning(f"[DISPLAY_DECODER] Unknown command_type for status_word: {command_type}")
                        return message_type
                    
            # Check for hardcoded mappings
            if message_type in cls.DISPLAY_MESSAGE_TYPE_MAP:
                translated_type = cls.DISPLAY_MESSAGE_TYPE_MAP[message_type]
                logger.info(f"[DISPLAY_DECODER] Translated message_type: {message_type} -> {translated_type}")
                return translated_type
            
            # Use helper function from display_message_types
            # Check for precipitation-related message types
            if is_precipitation_message({"message_type": message_type}):
                translated_type = DISPLAY_PRECIPITATION_DATA
                logger.info(f"[DISPLAY_DECODER] Precipitation message detected: {message_type} -> {translated_type}")
                return translated_type
                
            # Check for VIL-related message types
            if is_vil_message({"message_type": message_type}):
                translated_type = DISPLAY_VIL_DATA
                logger.info(f"[DISPLAY_DECODER] VIL message detected: {message_type} -> {translated_type}")
                return translated_type
                
            # Use centralized translate_message_type function
            translated_type = translate_type(message_type)
            if translated_type != message_type:
                logger.info(f"[DISPLAY_DECODER] Translated via central function: {message_type} -> {translated_type}")
                return translated_type
                
            # Return original if no mapping exists
            return message_type
            
        except Exception as e:
            logger.error(f"[DISPLAY_DECODER] Error translating message type: {str(e)}")
            logger.error(traceback.format_exc())
            # Return original message type on error
            return message_type
    
    @classmethod
    def decode_metadata(cls, data_words: list) -> Dict[str, Any]:
        """
        Decode metadata from data words and translate message types for display system.
        Uses display-local message types and constants for consistent message handling.
        
        Args:
            data_words: List of data words to decode
            
        Returns:
            Dict[str, Any]: Decoded metadata with translated message types
        """
        try:
            # Use the base MetadataCodec to decode the metadata
            metadata = MetadataCodec.decode_metadata(data_words)
            
            # Translate message type if present
            if metadata and 'message_type' in metadata:
                original_type = metadata['message_type']
                
                # Pass the entire metadata as context for context-aware translation
                metadata['message_type'] = cls.translate_message_type(original_type, context=metadata)
                
                # Store original message type for reference
                metadata['original_message_type'] = original_type
                
            # Ensure metadata has a command_type if message_type is present
            if metadata and 'message_type' in metadata and 'command_type' not in metadata:
                metadata['command_type'] = metadata['message_type']
                
            return metadata
            
        except Exception as e:
            logger.error(f"[DISPLAY_DECODER] Error decoding metadata: {str(e)}")
            logger.error(traceback.format_exc())
            # Return empty dict on error
            return {}
    
    @classmethod
    def process_message(cls, message: Union[Dict[str, Any], Any]) -> Union[Dict[str, Any], Any]:
        """
        Process a message by translating its message type for display system.
        Uses display-local message types and constants for consistent message handling.
        
        Args:
            message: The message to process
            
        Returns:
            Dict[str, Any]: The processed message with translated message type
        """
        try:
            if not message:
                return message
                
            # Make a copy of the message to avoid modifying the original
            processed_message = message.copy() if isinstance(message, dict) else message
            
            # Translate message type if present
            if isinstance(processed_message, dict) and 'message_type' in processed_message:
                original_type = processed_message['message_type']
                processed_message['message_type'] = cls.translate_message_type(original_type, context=processed_message)
                
                # Store original message type for reference
                if 'original_message_type' not in processed_message:
                    processed_message['original_message_type'] = original_type
                    
            # Ensure message has a command_type if message_type is present
            if isinstance(processed_message, dict) and 'message_type' in processed_message and 'command_type' not in processed_message:
                processed_message['command_type'] = processed_message['message_type']
                    
            return processed_message
            
        except Exception as e:
            logger.error(f"[DISPLAY_DECODER] Error processing message: {str(e)}")
            logger.error(traceback.format_exc())
            # Return original message on error
            return message

# Singleton instance
_display_metadata_decoder = None

def get_display_metadata_decoder() -> DisplayMetadataDecoder:
    """Get the singleton instance of DisplayMetadataDecoder."""
    global _display_metadata_decoder
    if _display_metadata_decoder is None:
        _display_metadata_decoder = DisplayMetadataDecoder()
    return _display_metadata_decoder
