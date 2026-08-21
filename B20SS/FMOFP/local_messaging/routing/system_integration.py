"""
System Integration

Integrates the Unified Router with the system manager.
Provides functions to register the router with the system manager.
"""

import traceback
from typing import Dict, Any, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.unified_router import get_unified_router

logger = get_logger()

def register_with_system_manager():
    """Register the Unified Router with the system manager."""
    try:
        # Import here to avoid circular imports
        from FMOFP.core.system_manager import get_system_manager
        
        # Get system manager
        system_manager = get_system_manager()
        
        # Get unified router
        unified_router = get_unified_router()
        
        # Register router with system manager
        system_manager.register_component('unified_router', unified_router)
        
        # Register route_message function as a message handler
        system_manager.register_message_handler('route_message', unified_router.route_message)
        
        # Register special case handlers with system manager
        for handler_name, handler in unified_router.special_case_handlers.items():
            system_manager.register_component(handler_name, handler)
            logger.info(f"Registered special case handler: {handler_name}")
        
        logger.info("Unified Router registered with system manager")
        return True
    except Exception as e:
        logger.error(f"Error registering Unified Router with system manager: {e}")
        logger.error(traceback.format_exc())
        return False

def initialize_routing_system():
    """Initialize the routing system."""
    try:
        # Get unified router
        unified_router = get_unified_router()
        
        # Register with system manager
        register_result = register_with_system_manager()
        
        # Initialize message dispatcher
        from FMOFP.local_messaging.routing.message_dispatcher import get_message_dispatcher
        dispatcher = get_message_dispatcher()
        dispatcher.initialize()
        
        # Initialize response service adapter
        from FMOFP.local_messaging.routing.response_service_adapter import get_response_service_adapter
        response_adapter = get_response_service_adapter()
        
        # Register the response service adapter with the system manager
        from FMOFP.core.system_manager import get_system_manager
        system_manager = get_system_manager()
        system_manager.register_component('response_service_adapter', response_adapter)
        
        # Log successful initialization
        logger.info("Unified routing system initialized successfully")
        logger.info(f"Unified router instance: {id(unified_router)}")
        logger.info(f"Message dispatcher instance: {id(dispatcher)}")
        logger.info(f"Response service adapter instance: {id(response_adapter)}")
        
        # Verify special case handlers
        for handler_name, handler in unified_router.special_case_handlers.items():
            logger.info(f"Verified special case handler: {handler_name} (ID: {id(handler)})")
        
        return register_result
    except Exception as e:
        logger.error(f"Error initializing routing system: {e}")
        logger.error(traceback.format_exc())
        return False

def route_message(message: Union[Dict[str, Any], Any]) -> bool:
    """
    Route a message using the Unified Router.
    
    This is the primary entry point for all message routing in the system.
    
    Args:
        message: The message to route
        
    Returns:
        bool: True if the message was routed successfully, False otherwise
    """
    try:
        # Log basic information about the message
        message_type = None
        command_type = None
        request_id = None
        
        if isinstance(message, dict):
            message_type = message.get('message_type')
            command_type = message.get('command_type') 
            request_id = message.get('request_id')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            command_type = getattr(message, 'command_type', None)
            request_id = getattr(message, 'request_id', None)
            
        logger.info(f"[ROUTE INTEGRATION] Routing message: type={message_type}, command={command_type}, id={request_id}")
        
        # Get unified router
        unified_router = get_unified_router()
        
        # Route message
        result = unified_router.route_message(message)
        
        # Log result
        if result:
            logger.info(f"[ROUTE INTEGRATION] Successfully routed message: type={message_type}, id={request_id}")
        else:
            logger.error(f"[ROUTE INTEGRATION] Failed to route message: type={message_type}, id={request_id}")
            
        return result
    except Exception as e:
        logger.error(f"Error routing message: {e}")
        logger.error(traceback.format_exc())
        return False
