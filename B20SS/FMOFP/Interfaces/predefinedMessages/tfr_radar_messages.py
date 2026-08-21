"""
TFR (Terrain Following Radar) Messages Module

Provides predefined messages for the TFR radar system.
"""

import asyncio
import uuid
import traceback
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.Interfaces.predefinedMessages.radar_enums import tfr_radarMode


class TFRRadarMessages(PredefinedMessagesBase):
    """
    Class for predefined TFR radar messages.
    Provides methods for creating and sending TFR radar messages.
    """
    
    async def tfr_radar_to_active_mode(self):
        """
        Set the TFR radar to ACTIVE mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting TFR radar to ACTIVE mode")
        active_mode = tfr_radarMode.ACTIVE
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="tfr_radar",
            request_type="mode_change",
            data=active_mode
        )
        
        self.logger.info(f"TFR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def tfr_radar_to_standby_mode(self):
        """
        Set the TFR radar to STANDBY mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting TFR radar to STANDBY mode")
        standby_mode = tfr_radarMode.STANDBY
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="tfr_radar",
            request_type="mode_change",
            data=standby_mode
        )
        
        self.logger.info(f"TFR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def set_tfr_radar_mode(self, mode_name):
        """
        Set the TFR radar to the specified mode.
        
        Args:
            mode_name: The name of the mode (e.g., 'ACTIVE', 'STANDBY')
            
        Returns:
            The request ID for the mode change request
        """
        # Convert string to enum value
        try:
            if isinstance(mode_name, str):
                mode = getattr(tfr_radarMode, mode_name.upper())
            elif isinstance(mode_name, int):
                mode = tfr_radarMode(mode_name)
            elif isinstance(mode_name, tfr_radarMode):
                mode = mode_name
            else:
                raise ValueError(f"Invalid mode type: {type(mode_name)}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Invalid TFR radar mode: {mode_name}")
            raise ValueError(f"Invalid TFR radar mode: {mode_name}")
            
        self.logger.info(f"Setting TFR radar to {mode.name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="tfr_radar",
            request_type="mode_change",
            data=mode
        )
        
        self.logger.info(f"TFR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def request_tfr_radar_status(self):
        """
        Send a status request to the TFR radar.
            
        Returns:
            The request ID for the status request
        """
        self.logger.info("Sending status request to TFR radar")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="tfr_radar",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"Status request sent to TFR radar with ID: {request_id}")
        return request_id
    
    def create_tfr_elevation_data_request(self, scan_parameters=None, **kwargs):
        """
        Create a TFR elevation data request.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted TFR elevation data request
        """
        from FMOFP.local_messaging.messageConfigurations.tfr_radar_data import tfr_radarElevationDataRequest
        from FMOFP.local_messaging.message_types import BaseMessageType, TFR_RADAR_ELEVATION_DATA_REQUEST
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        scan_parameters = scan_parameters or {"mode": "ACTIVE"}
        
        # Apply default values for scan parameters if needed
        if "range_start" not in scan_parameters:
            scan_parameters["range_start"] = 0.0
        if "range_end" not in scan_parameters:
            scan_parameters["range_end"] = 10000.0
        if "scan_width" not in scan_parameters:
            scan_parameters["scan_width"] = 1000.0
        if "resolution" not in scan_parameters:
            scan_parameters["resolution"] = 10.0
            
        self.logger.info(f"Creating TFR elevation data request with UUID: {request_uuid}")
        
        # Create the request object
        elevation_request = tfr_radarElevationDataRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="tfr_radar",
            request_uuid=request_uuid,
            scan_parameters=scan_parameters
        )
        
        # Add command type - crucial for routing
        elevation_request.command_type = "elevation_data"
        
        # Add message_type for consistency
        elevation_request.message_type = TFR_RADAR_ELEVATION_DATA_REQUEST
        
        # Add base_message_type for compatibility with systems expecting enum value
        elevation_request.base_message_type = BaseMessageType.RADAR_DATA
        
        # Add comprehensive metadata
        elevation_request.metadata = {
            "source": "predefined_messages",
            "data_type": "elevation_data",
            "test_identifier": f"tfr_elev_req_{request_uuid[-8:]}",
            "message_type": TFR_RADAR_ELEVATION_DATA_REQUEST,
            "command_type": "elevation_data",
            "command_name": "TFR_RADAR_ELEVATION_DATA",
            "request_id": request_uuid
        }
        
        return elevation_request
        
    async def request_elevation_data(self, scan_parameters=None, **kwargs):
        """
        Send an elevation data request to the TFR radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the elevation data request
        """
        try:
            # Create and configure the elevation data request object
            elevation_request = self.create_tfr_elevation_data_request(scan_parameters, **kwargs)
            
            # Add command_type for RadarMessageHandler to recognize properly
            elevation_request.command_type = "data"
            
            # Add proper metadata for processing by RT
            if not hasattr(elevation_request, 'metadata') or not elevation_request.metadata:
                elevation_request.metadata = {}
                
            elevation_request.metadata.update({
                "command_type": "data",
                "command_name": "TFR_RADAR_ELEVATION_DATA",
                "data_type": "elevation_data"
            })
            
            self.logger.info("Sending elevation data request to TFR radar")
            
            # Send request with parameters expected by RadarMessageHandler
            request_id = await self.radar_handler.send_request(
                radar_name="tfr_radar",
                request_type="data",
                data=elevation_request
            )
            
            self.logger.info(f"Elevation data request sent with ID: {request_id}")
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error sending elevation data request: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    async def request_tfr_elevation_data(self, scan_parameters=None, **kwargs):
        """
        Send an elevation data request to the TFR radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the elevation data request
        """
        try:
            # Create the elevation data request
            elevation_request = self.create_tfr_elevation_data_request(scan_parameters, **kwargs)
            
            # Set command_type properly for routing
            elevation_request.command_type = "data"
            
            self.logger.info("Sending elevation data request to TFR radar")
            
            # Send data request
            request_id = await self.radar_handler.send_request(
                "tfr_radar",      # Target system
                "data",           # Command type
                elevation_request # Send request object
            )
            
            self.logger.info(f"Elevation data request sent with ID: {request_id}")
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error sending elevation data request: {e}")
            self.logger.error(traceback.format_exc())
            return None
        
    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for TFR radar.
        
        This is used by the RadarMessenger for direct message handling.
        
        Args:
            message: The message to process
            
        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            self.logger.info(f"[TFR_RADAR] Synchronously processing message with ID: {id(message)}")
            
            # Log message details for debugging
            if hasattr(message, 'message_type'):
                self.logger.info(f"[TFR_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                self.logger.info(f"[TFR_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                self.logger.info(f"[TFR_RADAR] Command name: {message.command_name}")
                
            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}
                
            # Mark as processed by TFR radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []
                    
                if 'tfr_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('tfr_radar')
            
            # For logging purposes
            self.logger.info(f"[TFR_RADAR] Message successfully processed")
            return True
            
        except Exception as e:
            self.logger.error(f"[TFR_RADAR] Error processing message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
