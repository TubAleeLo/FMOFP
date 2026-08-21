"""
Unified Router

Central routing component for the FMOFP system.
Integrates validator, resolver, transformer, and dispatcher components.
"""

import threading
import traceback
from typing import Dict, Any, Optional, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.routing_registry import get_routing_registry
from FMOFP.local_messaging.routing.message_validator import get_message_validator
from FMOFP.local_messaging.routing.route_resolver import get_route_resolver
from FMOFP.local_messaging.routing.message_transformer import get_message_transformer
from FMOFP.local_messaging.routing.message_dispatcher import get_message_dispatcher 

logger = get_logger()

class UnifiedRouter:
    _instance = None
    _lock = threading.RLock()
    _initialized = False
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(UnifiedRouter, cls).__new__(cls)
            return cls._instance
    
    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.logger = get_logger()
                
                # Initialize routing registry
                self.routing_registry = get_routing_registry()
                self.routing_registry.load_from_xml(
                    'FMOFP/local_messaging/messageConfigurations/address_book.xml',
                    'FMOFP/local_messaging/messageConfigurations/command_registry.xml'
                )
                
                # Initialize components
                self.validator = get_message_validator()
                self.resolver = get_route_resolver()
                self.transformer = get_message_transformer()
                self.dispatcher = get_message_dispatcher()
                
                # Initialize special case handlers
                self.special_case_handlers = {}
                self._initialize_special_case_handlers()
                
                # Initialize display outgoing router
                from FMOFP.local_messaging.routing.display_outgoing_router import get_display_outgoing_router
                self.display_outgoing_router = get_display_outgoing_router()
                
                self.__class__._initialized = True
                self.logger.info("[UNIFIED ROUTER] UnifiedRouter initialized")
                
    def _initialize_special_case_handlers(self):
        """Initialize special case handlers with ResponseServiceAdapter."""
        # Initialize the response service adapter
        from FMOFP.local_messaging.routing.response_service_adapter import get_response_service_adapter
        response_service_adapter = get_response_service_adapter()
        
        # Import handlers
        from FMOFP.local_messaging.routing.handlers import (
            get_vil_handler,
            get_precipitation_handler,
            get_mode_change_handler
        )
        
        # Initialize handlers with the response service adapter
        self.special_case_handlers['vil_handler'] = get_vil_handler()
        self.special_case_handlers['precipitation_handler'] = get_precipitation_handler()
        self.special_case_handlers['mode_change_handler'] = get_mode_change_handler()
        
        self.logger.info(f"[UNIFIED ROUTER] Initialized {len(self.special_case_handlers)} special case handlers with ResponseServiceAdapter")
        
    def display_outgoing_router_route_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route a message through the display outgoing router.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Call the display outgoing router's route_message method
            result = self.display_outgoing_router.route_message(message)
            return result
        except Exception as e:
            self.logger.error(f"[UNIFIED ROUTER] Error routing message through display outgoing router: {e}")
            self.logger.error(traceback.format_exc())
            return False
        
    def route_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route a message to the appropriate destinations.

        Args:
            message: The message to route

        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Check if this message is marked for final delivery to display
            if self._is_final_delivery_to_display(message):
                self.logger.info("[UNIFIED ROUTER] Message marked for final delivery to display, using DisplayOutgoingRouter")
                result = self.display_outgoing_router_route_message(message)
                return result

            # Use message loop prevention middleware
            try:
                from FMOFP.Utils.message_loop_prevention.middleware import get_loop_prevention_middleware
                middleware = get_loop_prevention_middleware()
                
                # Check for loops using middleware
                should_process, enhanced_message = middleware.process_message(
                    message, 'unified_router')
                
                if not should_process:
                    self.logger.warning("[UNIFIED ROUTER] Breaking loop - message already processed")
                    return False
                    
                # Continue with normal routing using enhanced message
                message = enhanced_message
            except ImportError:
                # If middleware is not available, continue with original message
                self.logger.warning("[UNIFIED ROUTER] Message loop prevention middleware not available")
                pass

            # Validate message
            if not self.validator.validate_message(message):
                self.logger.error("[UNIFIED ROUTER] Message validation failed")
                return False

            # Check for special cases
            special_case = self._check_special_case(message)
            if special_case:
                handler_id = special_case['handler']
                handler = self.special_case_handlers.get(handler_id)
                if handler:
                    self.logger.info(f"[UNIFIED ROUTER] Using special case handler: {handler_id}")

                    # Get result from handler
                    result = handler.handle_message(message)

                    # Check if result is a coroutine
                    import asyncio
                    if asyncio.iscoroutine(result):
                        self.logger.warning(f"[UNIFIED ROUTER] Handler {handler_id} returned a coroutine, scheduling it to run")
                        try:
                            # Check if we're in a running event loop
                            loop = asyncio.get_running_loop()
                            # We're in a running loop, so create a task
                            asyncio.create_task(result)
                            self.logger.warning(f"[UNIFIED ROUTER] Created task for {handler_id}'s coroutine")
                        except RuntimeError:
                            # No running event loop, create one
                            self.logger.warning(f"[UNIFIED ROUTER] No running event loop, creating one for {handler_id}'s coroutine")
                            loop = asyncio.new_event_loop()
                            loop.run_until_complete(result)

                        # Return success since we've scheduled the coroutine
                        return True

                    # If it's not a coroutine, return the result directly
                    return result
                else:
                    self.logger.warning(f"[UNIFIED ROUTER] Special case handler {handler_id} not found, using default routing")

            # Determine destinations
            destinations = self.resolver.resolve_routes(message)
            if not destinations:
                self.logger.warning("[UNIFIED ROUTER] No destinations found for message")
                return False

            # Transform message for each destination
            transformed_messages = self.transformer.transform_message(message, destinations)

            # Dispatch messages
            success = True
            for destination, transformed_message in transformed_messages.items():
                if not self.dispatcher.dispatch_message(destination, transformed_message):
                    self.logger.error(f"[UNIFIED ROUTER] Failed to dispatch message to {destination}")
                    success = False

            return success

        except Exception as e:
            self.logger.error(f"[UNIFIED ROUTER] Error routing message: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _is_final_delivery_to_display(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Check if a message is marked for final delivery to the display system.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is marked for final delivery to display, False otherwise
        """
        # Check metadata for final_delivery flag
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
            if isinstance(metadata, dict):
                # Check for explicit final_delivery flag
                if 'final_delivery' in metadata and metadata['final_delivery'] is True:
                    return True
                    
                # Check for final_delivery_to_display flag
                if 'final_delivery_to_display' in metadata and metadata['final_delivery_to_display'] is True:
                    return True
                    
                # Check for destination and routed_to flags
                if 'destination' in metadata and metadata['destination'] == 'display_system' and 'routed_to' in metadata and metadata['routed_to'] == 'display':
                    # Check if this is a mode change completion message
                    command_type = None
                    if 'command_type' in message:
                        command_type = message['command_type']
                    elif 'command_type' in metadata:
                        command_type = metadata['command_type']
                        
                    if command_type == 'mode_change_completion':
                        return True
        
        # Check object attributes for final_delivery flag
        elif hasattr(message, 'metadata') and message.metadata:
            metadata = message.metadata
            if isinstance(metadata, dict):
                # Check for explicit final_delivery flag
                if 'final_delivery' in metadata and metadata['final_delivery'] is True:
                    return True
                    
                # Check for final_delivery_to_display flag
                if 'final_delivery_to_display' in metadata and metadata['final_delivery_to_display'] is True:
                    return True
                    
                # Check for destination and routed_to flags
                if 'destination' in metadata and metadata['destination'] == 'display_system' and 'routed_to' in metadata and metadata['routed_to'] == 'display':
                    # Check if this is a mode change completion message
                    command_type = None
                    if hasattr(message, 'command_type'):
                        command_type = message.command_type
                    elif 'command_type' in metadata:
                        command_type = metadata['command_type']
                        
                    if command_type == 'mode_change_completion':
                        return True
        
        return False
        
    def _extract_field(self, message, field_name):
        """
        Extract a field from a message or message metadata.
        
        Args:
            message: The message to extract from
            field_name: The name of the field to extract
            
        Returns:
            The field value, or None if not found
        """
        if isinstance(message, dict):
            # Check top level
            if field_name in message:
                return message[field_name]
                
            # Check metadata
            if 'metadata' in message and isinstance(message['metadata'], dict):
                if field_name in message['metadata']:
                    return message['metadata'][field_name]
        elif hasattr(message, field_name):
            # Check object attribute
            return getattr(message, field_name)
            
        # Not found
        return None
    
    def _check_special_case(self, message: Union[Dict[str, Any], Any]) -> Optional[Dict[str, Any]]:
        """
        Check if a message is a special case.
        
        Args:
            message: The message to check
            
        Returns:
            Optional[Dict[str, Any]]: Special case information, or None if not a special case
        """
        # Check for loop prevention flags
        if isinstance(message, dict) and 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            if metadata.get('_processed_by_vil_handler') or \
               metadata.get('_processed_by_precipitation_handler') or \
               metadata.get('_processed_by_mode_change_handler'):
                self.logger.warning("[UNIFIED ROUTER] Detected routing loop - message already processed by a handler")
                return None
        elif hasattr(message, 'metadata') and message.metadata:
            metadata = message.metadata
            if isinstance(metadata, dict) and (
                metadata.get('_processed_by_vil_handler') or 
                metadata.get('_processed_by_precipitation_handler') or 
                metadata.get('_processed_by_mode_change_handler')):
                self.logger.warning("[UNIFIED ROUTER] Detected routing loop - message already processed by a handler")
                return None
                
        # Get message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        # Check if message type is a special case
        if message_type:
            special_case = self.routing_registry.get_special_case(message_type)
            if special_case:
                self.logger.info(f"[UNIFIED ROUTER] Found special case for message type: {message_type}")
                return special_case
                
        # Get command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        # Check if command name is a special case
        if command_name:
            for case_id, case in self.routing_registry.special_cases.items():
                if 'command_names' in case and command_name in case['command_names']:
                    self.logger.info(f"[UNIFIED ROUTER] Found special case for command name: {command_name}")
                    return case
        
        # Check for explicit command types
        command_type = None
        if isinstance(message, dict):
            command_type = message.get('command_type')
        elif hasattr(message, 'command_type'):
            command_type = message.command_type
            
        # Check command type for specific handlers
        if command_type:
            # Use exact matching patterns for VIL data
            if command_type == 'vil_data' or command_type == 'weather_radar_vil_data':
                self.logger.info(f"[UNIFIED ROUTER] Found special case for VIL data: {command_type}")
                return self.routing_registry.special_cases.get('vil_data')
                
            # Use exact matching patterns for precipitation data
            elif command_type == 'precipitation_data' or command_type == 'weather_radar_precipitation_data':
                # Check if this is an acknowledgment/status word
                message_type = self._extract_field(message, 'message_type')
                if message_type and ('statusword' in message_type.lower() or 'acknowledgment' in message_type.lower() or 'response' in message_type.lower()):
                    self.logger.info(f"[UNIFIED ROUTER] Skipping special case handling for precipitation acknowledgment: {message_type}")
                    return None  # Skip special case routing for acknowledgments
                
                self.logger.info(f"[UNIFIED ROUTER] Found special case for precipitation data: {command_type}")
                return self.routing_registry.special_cases.get('precipitation_data')
                
            # Use exact matching patterns for mode change
            elif command_type == 'mode_change' or command_type == 'weather_radar_mode_change':
                self.logger.info(f"[UNIFIED ROUTER] Found special case for mode change: {command_type}")
                return self.routing_registry.special_cases.get('mode_change')
                
        # Check for block transfer metadata for more accurate message classification
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
            if isinstance(metadata, dict):
                # Check block transfer metadata for VIL data
                if (metadata.get('block_transfer_complete') and 
                    (metadata.get('vil_data') or metadata.get('vil_data_available') or
                     metadata.get('vil_objects') or metadata.get('vil_message'))):
                    self.logger.info(f"[UNIFIED ROUTER] Found special case for VIL block transfer data based on metadata")
                    return self.routing_registry.special_cases.get('vil_data')
                    
                # Check block transfer metadata for precipitation data
                elif (metadata.get('block_transfer_complete') and 
                     (metadata.get('precipitation_data') or metadata.get('precipitation_objects') or
                      metadata.get('precip_data_available') or metadata.get('precipitation_message'))):
                    self.logger.info(f"[UNIFIED ROUTER] Found special case for precipitation block transfer data based on metadata")
                    return self.routing_registry.special_cases.get('precipitation_data')
        
        # Also check message attributes for object-style messages
        elif hasattr(message, 'metadata') and message.metadata:
            metadata = message.metadata
            if isinstance(metadata, dict):
                # Check block transfer metadata for VIL data
                if (metadata.get('block_transfer_complete') and 
                    (metadata.get('vil_data') or metadata.get('vil_data_available') or 
                     metadata.get('vil_objects') or metadata.get('vil_message'))):
                    self.logger.info(f"[UNIFIED ROUTER] Found special case for VIL block transfer data based on object metadata")
                    return self.routing_registry.special_cases.get('vil_data')
                    
                # Check block transfer metadata for precipitation data
                elif (metadata.get('block_transfer_complete') and 
                     (metadata.get('precipitation_data') or metadata.get('precipitation_objects') or
                      metadata.get('precip_data_available') or metadata.get('precipitation_message'))):
                    self.logger.info(f"[UNIFIED ROUTER] Found special case for precipitation block transfer data based on object metadata")
                    return self.routing_registry.special_cases.get('precipitation_data')
            
        return None

def get_unified_router():
    """Get the singleton instance of UnifiedRouter."""
    return UnifiedRouter()
