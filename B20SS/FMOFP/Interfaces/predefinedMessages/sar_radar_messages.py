"""
SAR (Synthetic Aperture Radar) Messages Module

Provides predefined messages for the SAR radar system.
"""

import asyncio
import uuid
import traceback
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.Interfaces.predefinedMessages.radar_enums import sar_radarMode


class SARRadarMessages(PredefinedMessagesBase):
    """
    Class for predefined SAR radar messages.
    Provides methods for creating and sending SAR radar messages.
    """
    
    async def sar_radar_to_stripmap_mode(self):
        """
        Set the SAR radar to STRIPMAP mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting SAR radar to STRIPMAP mode")
        stripmap_mode = sar_radarMode.STRIPMAP
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="sar_radar",
            request_type="mode_change",
            data=stripmap_mode
        )
        
        self.logger.info(f"SAR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def sar_radar_to_spotlight_mode(self):
        """
        Set the SAR radar to SPOTLIGHT mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting SAR radar to SPOTLIGHT mode")
        spotlight_mode = sar_radarMode.SPOTLIGHT
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="sar_radar",
            request_type="mode_change",
            data=spotlight_mode
        )
        
        self.logger.info(f"SAR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def sar_radar_to_standby_mode(self):
        """
        Set the SAR radar to STANDBY mode.
        
        Returns:
            The request ID for the mode change request
        """
        self.logger.info("Setting SAR radar to STANDBY mode")
        standby_mode = sar_radarMode.STANDBY
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="sar_radar",
            request_type="mode_change",
            data=standby_mode
        )
        
        self.logger.info(f"SAR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def set_sar_radar_mode(self, mode_name):
        """
        Set the SAR radar to the specified mode.
        
        Args:
            mode_name: The name of the mode (e.g., 'STRIPMAP', 'SPOTLIGHT')
            
        Returns:
            The request ID for the mode change request
        """
        # Convert string to enum value
        try:
            if isinstance(mode_name, str):
                mode = getattr(sar_radarMode, mode_name.upper())
            elif isinstance(mode_name, int):
                mode = sar_radarMode(mode_name)
            elif isinstance(mode_name, sar_radarMode):
                mode = mode_name
            else:
                raise ValueError(f"Invalid mode type: {type(mode_name)}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Invalid SAR radar mode: {mode_name}")
            raise ValueError(f"Invalid SAR radar mode: {mode_name}")
            
        self.logger.info(f"Setting SAR radar to {mode.name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="sar_radar",
            request_type="mode_change",
            data=mode
        )
        
        self.logger.info(f"SAR radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def request_sar_radar_status(self):
        """
        Send a status request to the SAR radar.
            
        Returns:
            The request ID for the status request
        """
        self.logger.info("Sending status request to SAR radar")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="sar_radar",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"Status request sent to SAR radar with ID: {request_id}")
        return request_id
        
    def create_sar_imagery_request(self, scan_parameters=None, **kwargs):
        """
        Create a SAR imagery data request.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted SAR imagery data request
        """
        from FMOFP.local_messaging.messageConfigurations.sar_radar_data import sar_radarImageryRequest
        from FMOFP.local_messaging.message_types import BaseMessageType, SAR_RADAR_IMAGERY_REQUEST
        
        # Generate request UUID if not provided
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        # Default parameters for SAR imagery
        scan_parameters = scan_parameters or {"mode": "STRIPMAP"}
        
        # Apply default values for scan parameters if needed
        if "area" not in scan_parameters:
            scan_parameters["area"] = {"center": (0.0, 0.0), "radius": 5000.0}
        if "resolution" not in scan_parameters:
            scan_parameters["resolution"] = 1.0
        if "mode" not in scan_parameters:
            scan_parameters["mode"] = "STRIPMAP"
            
        self.logger.info(f"Creating SAR imagery request with UUID: {request_uuid}")
        
        # Create the request object with comprehensive parameter handling
        imagery_request = sar_radarImageryRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="sar_radar",
            request_uuid=request_uuid,
            scan_parameters=scan_parameters,
            area=scan_parameters.get("area"),
            resolution=scan_parameters.get("resolution"),
            mode=scan_parameters.get("mode")
        )
        
        # Add command type - crucial for routing
        imagery_request.command_type = "imagery_data"
        
        # Add message_type for consistency
        imagery_request.message_type = SAR_RADAR_IMAGERY_REQUEST
        
        # Add base_message_type for compatibility with systems expecting enum value
        imagery_request.base_message_type = BaseMessageType.RADAR_DATA
        
        # Add comprehensive metadata for reliable message routing and tracking
        imagery_request.metadata = {
            "source": "predefined_messages",
            "data_type": "imagery_data",
            "test_identifier": f"sar_img_req_{request_uuid[-8:]}",
            "message_type": SAR_RADAR_IMAGERY_REQUEST,
            "command_type": "imagery_data",
            "command_name": "SAR_RADAR_IMAGERY_DATA",
            "request_id": request_uuid
        }
        
        return imagery_request
    
    async def request_imagery_data(self, scan_parameters=None, **kwargs):
        """
        Send an imagery data request to the SAR radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the imagery data request
        """
        try:
            # Create and configure the imagery data request object
            imagery_request = self.create_sar_imagery_request(scan_parameters, **kwargs)
            
            # Add command_type to match what RadarMessageHandler expects
            imagery_request.command_type = "data"
            
            # Add proper metadata for processing by RT
            if not hasattr(imagery_request, 'metadata') or not imagery_request.metadata:
                imagery_request.metadata = {}
                
            imagery_request.metadata.update({
                "command_type": "data",
                "command_name": "SAR_RADAR_IMAGERY_DATA",
                "data_type": "imagery_data"
            })
            
            self.logger.info("Sending imagery data request to SAR radar")
            
            # Send request with only the parameters the RadarMessageHandler expects
            request_id = await self.radar_handler.send_request(
                radar_name="sar_radar",
                request_type="data",
                data=imagery_request
            )
            
            self.logger.info(f"Imagery data request sent with ID: {request_id}")
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error sending imagery data request: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None
        
    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for SAR radar.
        
        This is used by the RadarMessenger for direct message handling.
        
        Args:
            message: The message to process
            
        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            self.logger.info(f"[SAR_RADAR] Synchronously processing message with ID: {id(message)}")
            
            # Log message details for debugging
            if hasattr(message, 'message_type'):
                self.logger.info(f"[SAR_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                self.logger.info(f"[SAR_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                self.logger.info(f"[SAR_RADAR] Command name: {message.command_name}")
                
            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}
                
            # Mark as processed by SAR radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []
                    
                if 'sar_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('sar_radar')
            
            # For logging purposes
            self.logger.info(f"[SAR_RADAR] Message successfully processed")
            return True
            
        except Exception as e:
            self.logger.error(f"[SAR_RADAR] Error processing message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
