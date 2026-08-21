"""
FMS Response Service

Handles responses to FMS-related messages.
Central coordination for routing FMS response messages.
"""

import asyncio
import time
import threading
from typing import Dict, Any, Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class FMSResponseService:
    """
    Response service for FMS
    
    Handles routing of messages sent in response to FMS requests.
    """
    def __init__(self):
        """Initialize FMS Response Service"""
        self.lock = threading.Lock()
        self.response_callbacks = {}  # request_id -> callback
        self.response_timeout = 10.0  # 10 second timeout
        
        # Import message routing service
        from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
        self.routing_service = get_message_routing_service()
        
        logger.info("FMS Response Service initialized")
    
    async def register_response_callback(self, request_id: str, callback):
        """Register a callback to receive a specific response."""
        with self.lock:
            self.response_callbacks[request_id] = {
                'callback': callback,
                'timestamp': time.time()
            }
            logger.info(f"Registered response callback for request {request_id}")
    
    async def send_response(self, request_id: str, response: Dict[str, Any]) -> bool:
        """Send a response message to a registered callback."""
        if request_id is None:
            logger.warning("Cannot send response - request_id is None")
            return False
            
        with self.lock:
            # If there's a callback, invoke it
            if request_id in self.response_callbacks:
                callback_info = self.response_callbacks.pop(request_id)
                callback = callback_info['callback']
                try:
                    # Call the callback with the response
                    if asyncio.iscoroutinefunction(callback):
                        await callback(response)
                    else:
                        callback(response)
                    logger.info(f"Response sent to callback for request {request_id}")
                    return True
                except Exception as e:
                    logger.error(f"Error invoking callback for request {request_id}: {e}")
                    return False
            else:
                # No callback found, route response through standard channels
                # For FMS responses, this typically means sending via event bus
                await self.routing_service.route_generic_message("fms_response", response)
                logger.info(f"Response routed generically for request {request_id}")
                return True
    
    def cleanup_expired_callbacks(self):
        """Clean up expired response callbacks."""
        with self.lock:
            current_time = time.time()
            expired_callbacks = [
                request_id for request_id, info in self.response_callbacks.items()
                if current_time - info['timestamp'] > self.response_timeout
            ]
            
            for request_id in expired_callbacks:
                logger.warning(f"Response callback for request {request_id} expired")
                del self.response_callbacks[request_id]
    
    async def route_fms_mode_change(self, data: Dict[str, Any]) -> bool:
        """Route FMS mode change message."""
        return await self.routing_service.route_fms_mode_change(data)
    
    async def route_fms_attitude_update(self, data: Dict[str, Any]) -> bool:
        """Route FMS attitude update message."""
        return await self.routing_service.route_fms_attitude_update(data)
    
    async def route_fms_navigation_update(self, data: Dict[str, Any]) -> bool:
        """Route FMS navigation update message."""
        return await self.routing_service.route_fms_navigation_update(data)
    
    async def route_fms_flight_data(self, data: Dict[str, Any]) -> bool:
        """Route FMS flight data message."""
        return await self.routing_service.route_fms_flight_data(data)
    
    async def route_fms_tactical_data(self, data: Dict[str, Any]) -> bool:
        """Route FMS tactical data message."""
        return await self.routing_service.route_fms_tactical_data(data)
    
    async def route_status_word(self, data: Dict[str, Any]) -> bool:
        """Route status word message."""
        return await self.routing_service.route_status_word(data)

# Singleton instance
_fms_response_service = None

def get_fms_response_service():
    """Get singleton instance of FMS Response Service"""
    global _fms_response_service
    if _fms_response_service is None:
        _fms_response_service = FMSResponseService()
    return _fms_response_service
