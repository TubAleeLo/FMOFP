"""
AEWC (Airborne Early Warning and Control) Radar Messages Module

Provides predefined messages for the AEWC radar system.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.Interfaces.predefinedMessages.radar_enums import aewc_radarMode


class AEWCRadarMessages(PredefinedMessagesBase):
    """
    Class for predefined AEWC radar messages.
    Provides methods for creating and sending AEWC radar messages.
    """
    
    async def aewc_radar_to_surveillance_mode(self):
        """
        Set the AEWC radar to SURVEILLANCE mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting AEWC radar to SURVEILLANCE mode")
        surveillance_mode = aewc_radarMode.SURVEILLANCE
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="aewc_radar",
            request_type="mode_change",
            data=surveillance_mode
        )
        
        self.logger.info(f"AEWC radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def aewc_radar_to_tracking_mode(self):
        """
        Set the AEWC radar to TRACKING mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting AEWC radar to TRACKING mode")
        tracking_mode = aewc_radarMode.TRACKING
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="aewc_radar",
            request_type="mode_change",
            data=tracking_mode
        )
        
        self.logger.info(f"AEWC radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def aewc_radar_to_standby_mode(self):
        """
        Set the AEWC radar to STANDBY mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting AEWC radar to STANDBY mode")
        standby_mode = aewc_radarMode.STANDBY
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="aewc_radar",
            request_type="mode_change",
            data=standby_mode
        )
        
        self.logger.info(f"AEWC radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def set_aewc_radar_mode(self, mode_name):
        """
        Set the AEWC radar to the specified mode.
        
        Args:
            mode_name: The name of the mode (e.g., 'SURVEILLANCE', 'TRACKING', 'STANDBY')
            
        Returns:
            The request ID for the mode change request
        """
        # Convert string to enum value
        try:
            if isinstance(mode_name, str):
                mode = getattr(aewc_radarMode, mode_name.upper())
            elif isinstance(mode_name, int):
                mode = aewc_radarMode(mode_name)
            elif isinstance(mode_name, aewc_radarMode):
                mode = mode_name
            else:
                raise ValueError(f"Invalid mode type: {type(mode_name)}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Invalid AEWC radar mode: {mode_name}")
            raise ValueError(f"Invalid AEWC radar mode: {mode_name}")
            
        self.logger.info(f"Setting AEWC radar to {mode.name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="aewc_radar",
            request_type="mode_change",
            data=mode
        )
        
        self.logger.info(f"AEWC radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def request_aewc_radar_status(self):
        """
        Send a status request to the AEWC radar.
            
        Returns:
            The request ID for the status request
        """
        self.logger.info("Sending status request to AEWC radar")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="aewc_radar",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"Status request sent to AEWC radar with ID: {request_id}")
        return request_id
    
    def create_aewc_radar_track_request(self, track_parameters=None, **kwargs):
        """
        Create an AEWC radar track data request.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted AEWC radar track request
        """
        from FMOFP.local_messaging.messageConfigurations.aewc_radar_data import aewc_radarTrackRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        track_parameters = track_parameters or {"mode": "TRACKING"}
        
        self.logger.info(f"Creating AEWC radar track request with UUID: {request_uuid}")
        
        track_request = aewc_radarTrackRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="aewc_radar",
            request_uuid=request_uuid,
            track_parameters=track_parameters
        )
        
        # Add command type
        track_request.command_type = "track_data"
        
        # Add metadata
        track_request.metadata = {
            "source": "predefined_messages",
            "data_type": "track_data",
            "test_identifier": f"aewc_track_req_{request_uuid[-8:]}",
            "message_type": "aewc_radarTrackRequest"
        }
        
        return track_request
    
    async def request_aewc_radar_track_data(self, track_parameters=None, **kwargs):
        """
        Send a track data request to the AEWC radar.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the track data request
        """
        track_request = self.create_aewc_radar_track_request(track_parameters, **kwargs)
        
        self.logger.info("Sending track data request to AEWC radar")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "aewc_radar",     # Target system
            "data",           # Command type
            track_request     # Send request object
        )
        
        self.logger.info(f"Track data request sent with ID: {request_id}")
        return request_id
    
    def create_aewc_radar_sector_scan_request(self, sector_parameters=None, **kwargs):
        """
        Create an AEWC radar sector scan request.
        
        Args:
            sector_parameters: Dictionary of sector scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted AEWC radar sector scan request
        """
        from FMOFP.local_messaging.messageConfigurations.aewc_radar_data import aewc_radarSectorScanRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        sector_parameters = sector_parameters or {
            "azimuth_start": kwargs.get('azimuth_start', 0),
            "azimuth_end": kwargs.get('azimuth_end', 90),
            "elevation": kwargs.get('elevation', 0)
        }
        
        self.logger.info(f"Creating AEWC radar sector scan request with UUID: {request_uuid}")
        
        sector_request = aewc_radarSectorScanRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="aewc_radar",
            request_uuid=request_uuid,
            sector_parameters=sector_parameters
        )
        
        # Add command type
        sector_request.command_type = "sector_scan"
        
        # Add metadata
        sector_request.metadata = {
            "source": "predefined_messages",
            "data_type": "sector_scan",
            "test_identifier": f"aewc_sector_req_{request_uuid[-8:]}",
            "message_type": "aewc_radarSectorScanRequest"
        }
        
        return sector_request
    
    async def request_aewc_radar_sector_scan(self, azimuth_start=0, azimuth_end=90, elevation=0, **kwargs):
        """
        Send a sector scan request to the AEWC radar.
        
        Args:
            azimuth_start: Starting azimuth angle in degrees
            azimuth_end: Ending azimuth angle in degrees
            elevation: Elevation angle in degrees
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the sector scan request
        """
        sector_parameters = {
            "azimuth_start": azimuth_start,
            "azimuth_end": azimuth_end,
            "elevation": elevation
        }
        
        sector_request = self.create_aewc_radar_sector_scan_request(sector_parameters, **kwargs)
        
        self.logger.info(f"Sending sector scan request to AEWC radar ({azimuth_start}° to {azimuth_end}° at {elevation}° elevation)")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "aewc_radar",     # Target system
            "data",           # Command type
            sector_request    # Send request object
        )
        
        self.logger.info(f"Sector scan request sent with ID: {request_id}")
        return request_id
        
    async def request_sector_scan(self, azimuth_start=0, azimuth_end=90, elevation=0, **kwargs):
        """
        Alias for request_aewc_radar_sector_scan.
        Added for compatibility with test functions.
        
        Args:
            azimuth_start: Starting azimuth angle in degrees
            azimuth_end: Ending azimuth angle in degrees
            elevation: Elevation angle in degrees
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the sector scan request
        """
        return await self.request_aewc_radar_sector_scan(azimuth_start, azimuth_end, elevation, **kwargs)
        
    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for AEWC radar.
        
        This is used by the RadarMessenger for direct message handling.
        
        Args:
            message: The message to process
            
        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            self.logger.info(f"[AEWC_RADAR] Synchronously processing message with ID: {id(message)}")
            
            # Log message details for debugging
            if hasattr(message, 'message_type'):
                self.logger.info(f"[AEWC_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                self.logger.info(f"[AEWC_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                self.logger.info(f"[AEWC_RADAR] Command name: {message.command_name}")
                
            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}
                
            # Mark as processed by AEWC radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []
                    
                if 'aewc_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('aewc_radar')
            
            # For logging purposes
            self.logger.info(f"[AEWC_RADAR] Message successfully processed")
            return True
            
        except Exception as e:
            self.logger.error(f"[AEWC_RADAR] Error processing message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
