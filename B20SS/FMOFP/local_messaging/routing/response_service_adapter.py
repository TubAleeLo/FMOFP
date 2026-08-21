"""
Response Service Adapter

Provides a unified interface to response services for special case handlers.
Enables UnifiedRouter to access functionality from MessageRoutingService.
"""

import asyncio
import traceback
from typing import Dict, Any

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class ResponseServiceAdapter:
    """Adapter for response services to be used by special case handlers."""
    
    def __init__(self):
        # Initialize service references to None - will get them on demand
        self.radar_response_service = None
        self.display_response_service = None
        self._vil_service = None
        self._precipitation_service = None
        
        logger.info("ResponseServiceAdapter initialized")
        
    async def handle_status_word(self, message: Dict[str, Any]) -> bool:
        """
        Handle status word using radar response service.
        
        Args:
            message: The status word message
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Get radar response service
            await self._ensure_radar_response_service()
            if not self.radar_response_service:
                logger.error("Radar response service not available")
                return False
                
            # Handle status word
            await self.radar_response_service.handle_status_word_async(message)
            return True
        except Exception as e:
            logger.error(f"Error handling status word: {e}")
            logger.error(traceback.format_exc())
            return False
        
    async def handle_mode_change(self, message: Dict[str, Any]) -> bool:
        """
        Handle mode change using radar response service.
        
        Args:
            message: The mode change message
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Get radar response service
            await self._ensure_radar_response_service()
            if not self.radar_response_service:
                logger.error("Radar response service not available")
                return False
                
            # Handle mode change
            await self.radar_response_service.handle_mode_change_data(message)
            return True
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")
            logger.error(traceback.format_exc())
            return False
        
    async def handle_display_command(self, message: Dict[str, Any]) -> bool:
        """
        Handle display command using display response service.
        
        Args:
            message: The display command message
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Get display response service
            await self._ensure_display_response_service()
            if not self.display_response_service:
                logger.error("Display response service not available")
                return False
            
            # Log critical fields before handling
            logger.info(f"[RESPONSE_ADAPTER] Display command - request_id: {message.get('request_id')}, command_name: {message.get('command_name')}")
            
            # Ensure command_name is preserved in metadata
            if 'metadata' not in message:
                message['metadata'] = {}
                
            if 'command_name' in message and message['command_name']:
                message['metadata']['command_name'] = message['command_name']
                logger.info(f"[RESPONSE_ADAPTER] Preserved command_name in metadata: {message['command_name']}")
                
            if 'request_id' in message and message['request_id']:
                message['metadata']['request_id'] = message['request_id']
                logger.info(f"[RESPONSE_ADAPTER] Preserved request_id in metadata: {message['request_id']}")
                
            # Handle display command
            await self.display_response_service.handle_display_command(message, from_display_handler=True)
            return True
        except Exception as e:
            logger.error(f"Error handling display command: {e}")
            logger.error(traceback.format_exc())
            return False
        
    async def handle_vil_data(self, message: Dict[str, Any]) -> bool:
        """
        Handle VIL data using VIL response service.
        
        Args:
            message: The VIL data message
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Get VIL service
            vil_service = await self._ensure_vil_service()
            if not vil_service:
                logger.error("VIL service not available")
                return False
            
            # Log critical fields before handling
            logger.info(f"[RESPONSE_ADAPTER] VIL data - request_id: {message.get('request_id')}, command_name: {message.get('command_name')}")
            
            # Ensure command_name is preserved in metadata
            if 'metadata' not in message:
                message['metadata'] = {}
                
            if 'command_name' in message and message['command_name']:
                message['metadata']['command_name'] = message['command_name']
                logger.info(f"[RESPONSE_ADAPTER] Preserved command_name in VIL metadata: {message['command_name']}")
                
            if 'request_id' in message and message['request_id']:
                message['metadata']['request_id'] = message['request_id']
                logger.info(f"[RESPONSE_ADAPTER] Preserved request_id in VIL metadata: {message['request_id']}")
                
            # Handle VIL data
            await vil_service.handle_vil_data(message)
            return True
        except Exception as e:
            logger.error(f"Error handling VIL data: {e}")
            logger.error(traceback.format_exc())
            return False
        
    async def handle_precipitation_data(self, message: Dict[str, Any]) -> bool:
        """
        Handle precipitation data using precipitation response service.
        
        Args:
            message: The precipitation data message
            
        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Get precipitation service
            precip_service = await self._ensure_precipitation_service()
            if not precip_service:
                logger.error("Precipitation service not available")
                return False
                
            # Log critical fields before handling
            logger.info(f"[RESPONSE_ADAPTER] Precipitation data - request_id: {message.get('request_id')}, command_name: {message.get('command_name')}")
            
            # Ensure command_name is preserved in metadata
            if 'metadata' not in message:
                message['metadata'] = {}
                
            if 'command_name' in message and message['command_name']:
                message['metadata']['command_name'] = message['command_name']
                logger.info(f"[RESPONSE_ADAPTER] Preserved command_name in precipitation metadata: {message['command_name']}")
                
            if 'request_id' in message and message['request_id']:
                message['metadata']['request_id'] = message['request_id']
                logger.info(f"[RESPONSE_ADAPTER] Preserved request_id in precipitation metadata: {message['request_id']}")
                
            # Handle precipitation data
            await precip_service.handle_precipitation_data(message)
            return True
        except Exception as e:
            logger.error(f"Error handling precipitation data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    # Helper methods
    
    async def _ensure_radar_response_service(self):
        """Ensure radar response service is available."""
        if not self.radar_response_service:
            # Get radar response service
            from FMOFP.local_messaging.routing.response_services.system_response_services.RadarResponseService import get_radar_response_service
            self.radar_response_service = get_radar_response_service()
            
            if not self.radar_response_service:
                logger.error("Failed to get radar response service")
        
    async def _ensure_display_response_service(self):
        """Ensure display response service is available."""
        if not self.display_response_service:
            # Get display response service
            from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
            self.display_response_service = get_display_response_service()
            
            if not self.display_response_service:
                logger.error("Failed to get display response service")
    
    async def _ensure_vil_service(self):
        """
        Ensure VIL service is available, creating it if necessary.
        
        Returns:
            The VIL service instance
        """
        if not self._vil_service:
            # Try to get it from the system manager
            from FMOFP.core.system_manager import get_system_manager
            system_manager = get_system_manager()
            self._vil_service = system_manager.get_component('vil_response_service')
            
            if not self._vil_service:
                logger.warning("[VIL_FLOW] VIL Response Service not found in system manager - creating fallback instance")
                # Create a new VIL Response Service instance
                from FMOFP.local_messaging.routing.response_services.data_response_services.vil_response_service import VILResponseService
                from FMOFP.storage.DBM import DatabaseManager
                
                # Get radar database
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')
                
                # Create VIL service
                self._vil_service = VILResponseService(radar_db)
                
                # Start the service
                event_loop = asyncio.get_event_loop()
                await self._vil_service.start(event_loop=event_loop)
                
                # Register with system manager
                system_manager.register_component('vil_response_service', self._vil_service)
                logger.info("[VIL_FLOW] Created and registered new VIL Response Service instance")
            else:
                logger.info("[VIL_FLOW] Retrieved VIL Response Service from system manager")
        
        return self._vil_service
        
    async def _ensure_precipitation_service(self):
        """
        Ensure Precipitation service is available, creating it if necessary.
        
        Returns:
            The Precipitation service instance
        """
        # Try to get it from the system manager
        from FMOFP.core.system_manager import get_system_manager
        system_manager = get_system_manager()
        precip_service = system_manager.get_component('precipitation_response_service')
        
        if not precip_service:
            logger.warning("[PRECIP_FLOW] Precipitation Response Service not found in system manager - creating fallback instance")
            # Create a new Precipitation Response Service instance
            from FMOFP.local_messaging.routing.response_services.data_response_services.precipitation_response_service import get_precipitation_response_service
            
            # Get the service using the singleton
            precip_service = get_precipitation_response_service()
            
            # Start the service
            event_loop = asyncio.get_event_loop()
            await precip_service.start(event_loop=event_loop)
            
            # Register with system manager
            system_manager.register_component('precipitation_response_service', precip_service)
            logger.info("[PRECIP_FLOW] Created and registered new Precipitation Response Service instance")
        else:
            logger.info("[PRECIP_FLOW] Retrieved Precipitation Response Service from system manager")
        
        return precip_service

def get_response_service_adapter():
    """Get a new instance of ResponseServiceAdapter."""
    return ResponseServiceAdapter()
