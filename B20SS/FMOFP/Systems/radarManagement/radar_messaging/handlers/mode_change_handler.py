"""
Handler for radar mode change messages.
"""

import threading
import traceback
import time
from typing import Dict, Any, List, Optional
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_messaging.base_message_handler import BaseMessageHandler
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
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
    COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    is_mode_change_message
)
from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
    get_rt_address, 
    get_subaddress, 
    get_rt_subaddress_pair_for_radar,
    is_radar_subsystem
)

logger = get_logger()

class ModeChangeHandler(BaseMessageHandler):
    """Handler for radar mode change messages"""
    _instance = None

    _lock = threading.Lock()

    def __new__(cls):
        # Double-checked locking to prevent a TOCTOU race where multiple
        # threads concurrently pass the `cls._instance is None` check
        # before either assignment lands, producing duplicate instances.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModeChangeHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the handler"""
        super().__init__()
        # Initialize message types that this handler can process
        self.message_types = [
            # Weather Radar Mode Changes
            WEATHER_RADAR_MODE_CHANGE_REQUEST,
            WEATHER_RADAR_MODE_CHANGE_RESPONSE,
            # TFR Radar Mode Changes
            TFR_RADAR_MODE_CHANGE_REQUEST,
            TFR_RADAR_MODE_CHANGE_RESPONSE,
            # SAR Radar Mode Changes
            SAR_RADAR_MODE_CHANGE_REQUEST,
            SAR_RADAR_MODE_CHANGE_RESPONSE,
            # Targeting Radar Mode Changes
            TARGETING_RADAR_MODE_CHANGE_REQUEST,
            TARGETING_RADAR_MODE_CHANGE_RESPONSE,
            # AEWC Radar Mode Changes
            AEWC_RADAR_MODE_CHANGE_REQUEST,
            AEWC_RADAR_MODE_CHANGE_RESPONSE
        ]
        
        # Map of radar types to their corresponding message types
        self.radar_message_map = {
            'weather': (WEATHER_RADAR_MODE_CHANGE_REQUEST, WEATHER_RADAR_MODE_CHANGE_RESPONSE),
            'tfr': (TFR_RADAR_MODE_CHANGE_REQUEST, TFR_RADAR_MODE_CHANGE_RESPONSE),
            'sar': (SAR_RADAR_MODE_CHANGE_REQUEST, SAR_RADAR_MODE_CHANGE_RESPONSE),
            'targeting': (TARGETING_RADAR_MODE_CHANGE_REQUEST, TARGETING_RADAR_MODE_CHANGE_RESPONSE),
            'aewc': (AEWC_RADAR_MODE_CHANGE_REQUEST, AEWC_RADAR_MODE_CHANGE_RESPONSE)
        }

    def _get_radar_type_from_message(self, message):
        """
        Determine the radar type based on the message type.
        
        Args:
            message: The message to analyze
            
        Returns:
            str: The radar type or None if not found
        """
        # Extract message type using helper function
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
        message_type = get_message_type(message)
        
        if not message_type:
            return None
            
        message_type_lower = message_type.lower()
        
        # Check each radar type's message types
        for radar_type, (request_type, response_type) in self.radar_message_map.items():
            if message_type_lower == request_type.lower() or message_type_lower == response_type.lower():
                return radar_type
                
        # If not found in the map, try to extract from the message type string
        if 'weather' in message_type_lower:
            return 'weather'
        elif 'tfr' in message_type_lower:
            return 'tfr'
        elif 'sar' in message_type_lower:
            return 'sar'
        elif 'targeting' in message_type_lower:
            return 'targeting'
        elif 'aewc' in message_type_lower:
            return 'aewc'
            
        return None

    def _is_request_message(self, message):
        """
        Determine if the message is a mode change request.
        
        Args:
            message: The message to analyze
            
        Returns:
            bool: True if the message is a request, False if it's a response
        """
        # Extract message type using helper function
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
        message_type = get_message_type(message)
        
        if not message_type:
            return False
            
        message_type_lower = message_type.lower()
        
        # Check if it's a request message type
        for radar_type, (request_type, _) in self.radar_message_map.items():
            if message_type_lower == request_type.lower():
                return True
                
        # Check the command type if available
        command_type = getattr(message, 'command_type', None)
        if command_type:
            return command_type.lower() == COMMAND_TYPE_MODE_CHANGE.lower()
            
        # If 'request' is in the message type but 'response' isn't, it's likely a request
        return 'request' in message_type_lower and 'response' not in message_type_lower

    def validate_message(self, message):
        """
        Validate if the message is a valid mode change message.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if message is valid, False otherwise
        """
        try:
            # Check if the message has a message_type that we can handle
            from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
            message_type = get_message_type(message)
            if not message_type:
                logger.warning(f"[MODE_HANDLER] Message has no message_type: {message}")
                return False
                
            # Check if the message type is one we can handle based on our message_types list
            if not self.can_handle(message):
                # Use more flexible check with is_mode_change_message if specific type check fails
                if not is_mode_change_message(message):
                    logger.warning(f"[MODE_HANDLER] Message type {message_type} is not a mode change message")
                    return False
            
            # Determine the radar type - if we can't identify the radar type, it's not valid
            radar_type = self._get_radar_type_from_message(message)
            if not radar_type:
                logger.warning(f"[MODE_HANDLER] Could not determine radar type from message type: {message_type}")
                return False
            
            # For request messages, check for required attributes
            if self._is_request_message(message):
                # Check for mode attribute if it's a dictionary
                if isinstance(message, dict) and 'mode' not in message:
                    logger.warning(f"[MODE_HANDLER] Mode change request missing mode attribute")
                    return False
                
                # If it's an object, check for mode attribute
                if hasattr(message, '__dict__') and not hasattr(message, 'mode'):
                    logger.warning(f"[MODE_HANDLER] Mode change request missing mode attribute")
                    return False
            
            logger.info(f"[MODE_HANDLER] Message validated as a valid mode change message for {radar_type} radar")
            return True
            
        except Exception as e:
            logger.error(f"[MODE_HANDLER] Error validating mode change message: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def handle_message(self, message):
        """
        Handle a mode change message.
        Implementation of the abstract method from BaseMessageHandler.
        
        Args:
            message: The message to handle
            
        Returns:
            bool: True if message was handled successfully, False otherwise
        """
        if not self.validate_message(message):
            logger.warning(f"Invalid mode change message: {message}")
            return False
            
        try:
            # Pre-process the message
            processed_message = self.pre_process_message(message)
            
            # Determine the radar type
            radar_type = self._get_radar_type_from_message(processed_message)
            if not radar_type:
                logger.warning(f"Could not determine radar type from message: {processed_message}")
                return False
            
            # Determine if this is a request or response message
            is_request = self._is_request_message(processed_message)
            
            if is_request:
                # Handle mode change request
                logger.info(f"[MODE_HANDLER] Handling {radar_type} radar mode change request")
                # Process the request logic here
                # This could involve updating the radar mode and sending a response
                return True
                
            else:
                # Handle mode change response
                logger.info(f"[MODE_HANDLER] Handling {radar_type} radar mode change response")
                # Process the response logic here
                # This could involve updating the UI or triggering other actions
                return True
            
        except Exception as e:
            logger.error(f"Error handling mode change message: {e}")
            traceback.print_exc()
            return False

    def _get_command_word(self, radar_type, is_request=True):
        """
        Generate command word for mode change message.
        
        Args:
            radar_type: The type of radar (weather, tfr, etc.)
            is_request: Whether this is a request (True) or response (False)
            
        Returns:
            str: The command word
        """
        from FMOFP.local_messaging.command_word_map import register_command_word
        
        # Use address utility functions instead of hardcoded values
        radar_rt = get_rt_address('radar')
        mode_sa = get_subaddress('mode')
        
        command_type = 'mode_change' if is_request else 'mode_change_complete'
        
        return register_command_word('radar', 0, 'mode', command_type, radar_type)
