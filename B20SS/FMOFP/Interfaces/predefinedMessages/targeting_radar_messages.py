"""
Targeting Radar Messages Module

Provides predefined messages for the targeting radar system.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.Interfaces.predefinedMessages.radar_enums import targeting_radarMode


class TargetingRadarMessages(PredefinedMessagesBase):
    """
    Class for predefined targeting radar messages.
    Provides methods for creating and sending targeting radar messages.
    """
    
    async def targeting_radar_to_tracking_mode(self):
        """
        Set the targeting radar to TRACKING mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting targeting radar to TRACKING mode")
        tracking_mode = targeting_radarMode.TRACKING
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="targeting_radar",
            request_type="mode_change",
            data=tracking_mode
        )
        
        self.logger.info(f"Targeting radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def targeting_radar_to_search_mode(self):
        """
        Set the targeting radar to SEARCH mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting targeting radar to SEARCH mode")
        search_mode = targeting_radarMode.SEARCH
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="targeting_radar",
            request_type="mode_change",
            data=search_mode
        )
        
        self.logger.info(f"Targeting radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def targeting_radar_to_standby_mode(self):
        """
        Set the targeting radar to STANDBY mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting targeting radar to STANDBY mode")
        standby_mode = targeting_radarMode.STANDBY
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="targeting_radar",
            request_type="mode_change",
            data=standby_mode
        )
        
        self.logger.info(f"Targeting radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def set_targeting_radar_mode(self, mode_name):
        """
        Set the targeting radar to the specified mode.
        
        Args:
            mode_name: The name of the mode (e.g., 'TRACKING', 'SEARCH', 'STANDBY')
            
        Returns:
            The request ID for the mode change request
        """
        # Convert string to enum value
        try:
            if isinstance(mode_name, str):
                mode = getattr(targeting_radarMode, mode_name.upper())
            elif isinstance(mode_name, int):
                mode = targeting_radarMode(mode_name)
            elif isinstance(mode_name, targeting_radarMode):
                mode = mode_name
            else:
                raise ValueError(f"Invalid mode type: {type(mode_name)}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Invalid targeting radar mode: {mode_name}")
            raise ValueError(f"Invalid targeting radar mode: {mode_name}")
            
        self.logger.info(f"Setting targeting radar to {mode.name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="targeting_radar",
            request_type="mode_change",
            data=mode
        )
        
        self.logger.info(f"Targeting radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def request_targeting_radar_status(self):
        """
        Send a status request to the targeting radar.
            
        Returns:
            The request ID for the status request
        """
        self.logger.info("Sending status request to targeting radar")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="targeting_radar",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"Status request sent to targeting radar with ID: {request_id}")
        return request_id
    
    def create_targeting_radar_track_request(self, track_parameters=None, **kwargs):
        """
        Create a targeting radar track data request.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted targeting radar track request
        """
        from FMOFP.local_messaging.messageConfigurations.targeting_radar_data import targeting_radarTrackRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        track_parameters = track_parameters or {"mode": "TRACKING"}
        
        self.logger.info(f"Creating targeting radar track request with UUID: {request_uuid}")
        
        track_request = targeting_radarTrackRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="targeting_radar",
            request_uuid=request_uuid,
            track_parameters=track_parameters
        )
        
        # Add command type
        track_request.command_type = "track_data"
        
        # Add metadata
        track_request.metadata = {
            "source": "predefined_messages",
            "data_type": "track_data",
            "test_identifier": f"targeting_track_req_{request_uuid[-8:]}",
            "message_type": "targeting_radarTrackRequest"
        }
        
        return track_request
    
    async def request_targeting_radar_track_data(self, track_parameters=None, **kwargs):
        """
        Send a track data request to the targeting radar.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the track data request
        """
        track_request = self.create_targeting_radar_track_request(track_parameters, **kwargs)
        
        self.logger.info("Sending track data request to targeting radar")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "targeting_radar",  # Target system
            "data",             # Command type
            track_request       # Send request object
        )
        
        self.logger.info(f"Track data request sent with ID: {request_id}")
        return request_id
    
    async def request_track_data(self, track_parameters=None, **kwargs):
        """
        Alias for request_targeting_radar_track_data.
        Added for compatibility with test functions.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the track data request
        """
        return await self.request_targeting_radar_track_data(track_parameters, **kwargs)
    
    def create_targeting_radar_lock_request(self, lock_parameters=None, **kwargs):
        """
        Create a targeting radar lock request.
        
        Args:
            lock_parameters: Dictionary of lock parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted targeting radar lock request
        """
        from FMOFP.local_messaging.messageConfigurations.targeting_radar_data import targeting_radarLockRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        lock_parameters = lock_parameters or {"track_id": kwargs.get('track_id')}
        
        self.logger.info(f"Creating targeting radar lock request with UUID: {request_uuid}")
        
        lock_request = targeting_radarLockRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="targeting_radar",
            request_uuid=request_uuid,
            lock_parameters=lock_parameters
        )
        
        # Add command type
        lock_request.command_type = "lock_request"
        
        # Add metadata
        lock_request.metadata = {
            "source": "predefined_messages",
            "data_type": "lock_request",
            "test_identifier": f"targeting_lock_req_{request_uuid[-8:]}",
            "message_type": "targeting_radarLockRequest"
        }
        
        return lock_request
    
    async def request_targeting_radar_lock(self, track_id, lock_parameters=None, **kwargs):
        """
        Send a lock request to the targeting radar.
        
        Args:
            track_id: ID of the track to lock onto
            lock_parameters: Dictionary of lock parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the lock request
        """
        if lock_parameters is None:
            lock_parameters = {"track_id": track_id}
        else:
            lock_parameters['track_id'] = track_id
            
        lock_request = self.create_targeting_radar_lock_request(lock_parameters, **kwargs)
        
        self.logger.info(f"Sending lock request to targeting radar for track {track_id}")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "targeting_radar",  # Target system
            "data",             # Command type
            lock_request        # Send request object
        )
        
        self.logger.info(f"Lock request sent with ID: {request_id}")
        return request_id
        
    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for targeting radar.
        
        This is used by the RadarMessenger for direct message handling.
        
        Args:
            message: The message to process
            
        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            self.logger.info(f"[TARGETING_RADAR] Synchronously processing message with ID: {id(message)}")
            
            # Log message details for debugging
            if hasattr(message, 'message_type'):
                self.logger.info(f"[TARGETING_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                self.logger.info(f"[TARGETING_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                self.logger.info(f"[TARGETING_RADAR] Command name: {message.command_name}")
                
            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}
                
            # Mark as processed by targeting radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []
                    
                if 'targeting_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('targeting_radar')
            
            # For logging purposes
            self.logger.info(f"[TARGETING_RADAR] Message successfully processed")
            return True
            
        except Exception as e:
            self.logger.error(f"[TARGETING_RADAR] Error processing message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
