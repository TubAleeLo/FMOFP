"""
Flight Management System (FMS) Messages Module

Provides predefined messages for the FMS system.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.local_messaging.messageConfigurations.fms_data import (
    fms_attitudeUpdateRequest,
    fms_maneuverRequest, 
    fms_navigationUpdateRequest
)


class FMSMessages(PredefinedMessagesBase):
    """
    Class for predefined FMS messages.
    Provides methods for creating and sending FMS messages.
    """
    
    async def fms_mode_change(self, mode_name):
        """
        Change the mode of the Flight Management System.
        
        Args:
            mode_name: The name of the mode to change to
            
        Returns:
            The request ID for the mode change request
        """
        self.logger.info(f"Setting FMS to {mode_name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="flightManagementSystem",
            request_type="mode_change",
            data=mode_name
        )
        
        self.logger.info(f"FMS mode change request sent with ID: {request_id}")
        return request_id
    
    async def fms_request_status(self):
        """
        Request the current status of the Flight Management System.
        
        Returns:
            The request ID for the status request
        """
        self.logger.info("Requesting FMS status")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="flightManagementSystem",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"FMS status request sent with ID: {request_id}")
        return request_id
        
    async def request_status(self):
        """
        Alias for fms_request_status.
        Added for compatibility with test functions.
        
        Returns:
            The request ID for the status request
        """
        return await self.fms_request_status()
    
    def create_attitude_update_request(self, attitude_data, **kwargs):
        """
        Create an attitude update request for the FMS.
        
        Args:
            attitude_data: Dictionary containing attitude data (pitch, roll, yaw)
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted attitude update request
        """
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FMS attitude update request with UUID: {request_uuid}")
        
        attitude_request = fms_attitudeUpdateRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightManagementSystem",
            request_uuid=request_uuid,
            attitude_data=attitude_data
        )
        
        # Add command type
        attitude_request.command_type = "attitude_update"
        
        # Add metadata
        attitude_request.metadata = {
            "source": "predefined_messages",
            "data_type": "attitude_update",
            "test_identifier": f"fms_attitude_req_{request_uuid[-8:]}",
            "message_type": "fms_attitudeUpdateRequest"
        }
        
        return attitude_request
    
    async def request_attitude_update(self, pitch=0.0, roll=0.0, yaw=0.0, **kwargs):
        """
        Send an attitude update request to the FMS.
        
        Args:
            pitch: Pitch angle in degrees
            roll: Roll angle in degrees
            yaw: Yaw angle in degrees
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the attitude update request
        """
        attitude_data = {
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw
        }
        
        attitude_request = self.create_attitude_update_request(attitude_data, **kwargs)
        
        self.logger.info(f"Sending attitude update request to FMS (pitch: {pitch}°, roll: {roll}°, yaw: {yaw}°)")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightManagementSystem",  # Target system
            "data",                    # Command type
            attitude_request           # Send request object
        )
        
        self.logger.info(f"Attitude update request sent with ID: {request_id}")
        return request_id
        
    async def update_attitude(self, attitude_data=None, **kwargs):
        """
        Alias for request_attitude_update.
        Added for compatibility with test functions.
        
        Args:
            attitude_data: Dictionary containing attitude data (pitch, roll, yaw)
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the attitude update request
        """
        attitude_data = attitude_data or {}
        pitch = attitude_data.get('roll', kwargs.get('pitch', 0.0))
        roll = attitude_data.get('roll', kwargs.get('roll', 0.0))
        yaw = attitude_data.get('yaw', kwargs.get('yaw', 0.0))
        
        return await self.request_attitude_update(pitch, roll, yaw, **kwargs)
    
    def create_navigation_update_request(self, navigation_data, **kwargs):
        """
        Create a navigation update request for the FMS.
        
        Args:
            navigation_data: Dictionary containing navigation data (position, velocity, etc.)
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted navigation update request
        """
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FMS navigation update request with UUID: {request_uuid}")
        
        navigation_request = fms_navigationUpdateRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightManagementSystem",
            request_uuid=request_uuid,
            navigation_data=navigation_data
        )
        
        # Add command type
        navigation_request.command_type = "navigation_update"
        
        # Add metadata
        navigation_request.metadata = {
            "source": "predefined_messages",
            "data_type": "navigation_update",
            "test_identifier": f"fms_nav_req_{request_uuid[-8:]}",
            "message_type": "fms_navigationUpdateRequest"
        }
        
        return navigation_request
    
    async def request_navigation_update(self, latitude=0.0, longitude=0.0, altitude=0.0, 
                                        heading=0.0, airspeed=0.0, **kwargs):
        """
        Send a navigation update request to the FMS.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            altitude: Altitude in feet
            heading: Heading in degrees
            airspeed: Airspeed in knots
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the navigation update request
        """
        navigation_data = {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "heading": heading,
            "airspeed": airspeed
        }
        
        navigation_request = self.create_navigation_update_request(navigation_data, **kwargs)
        
        self.logger.info(f"Sending navigation update request to FMS (lat: {latitude}, lon: {longitude}, alt: {altitude}ft)")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightManagementSystem",  # Target system
            "data",                    # Command type
            navigation_request         # Send request object
        )
        
        self.logger.info(f"Navigation update request sent with ID: {request_id}")
        return request_id
        
    async def update_navigation(self, nav_data=None, **kwargs):
        """
        Alias for request_navigation_update.
        Added for compatibility with test functions.
        
        Args:
            nav_data: Dictionary containing navigation data
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the navigation update request
        """
        nav_data = nav_data or {}
        latitude = nav_data.get('latitude', kwargs.get('latitude', 0.0))
        longitude = nav_data.get('longitude', kwargs.get('longitude', 0.0))
        altitude = nav_data.get('altitude', kwargs.get('altitude', 0.0))
        heading = nav_data.get('heading', kwargs.get('heading', 0.0))
        airspeed = nav_data.get('airspeed', kwargs.get('airspeed', 0.0))
        
        return await self.request_navigation_update(
            latitude, longitude, altitude, heading, airspeed, **kwargs
        )
        
    def create_maneuver_request(self, maneuver_data, **kwargs):
        """
        Create a maneuver request for the FMS.
        
        Args:
            maneuver_data: Dictionary containing maneuver data
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted maneuver request
        """
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FMS maneuver request with UUID: {request_uuid}")
        
        maneuver_request = fms_maneuverRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightManagementSystem",
            request_uuid=request_uuid,
            maneuver_data=maneuver_data
        )
        
        # Add command type
        maneuver_request.command_type = "maneuver"
        
        # Add metadata
        maneuver_request.metadata = {
            "source": "predefined_messages",
            "data_type": "maneuver",
            "test_identifier": f"fms_maneuver_req_{request_uuid[-8:]}",
            "message_type": "fms_maneuverRequest"
        }
        
        return maneuver_request
    
    async def request_maneuver(self, maneuver_type, maneuver_params=None, **kwargs):
        """
        Send a maneuver request to the FMS.
        
        Args:
            maneuver_type: Type of maneuver (e.g., 'turn', 'climb', 'descend')
            maneuver_params: Dictionary of maneuver parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the maneuver request
        """
        maneuver_params = maneuver_params or {}
        
        maneuver_data = {
            "type": maneuver_type,
            "params": maneuver_params
        }
        
        maneuver_request = self.create_maneuver_request(maneuver_data, **kwargs)
        
        self.logger.info(f"Sending maneuver request to FMS (type: {maneuver_type})")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightManagementSystem",  # Target system
            "data",                    # Command type
            maneuver_request           # Send request object
        )
        
        self.logger.info(f"Maneuver request sent with ID: {request_id}")
        return request_id
        
    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for the Flight Management System.
        
        This is used by the RadarMessenger for direct message handling.
        
        Args:
            message: The message to process
            
        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            self.logger.info(f"[FMS] Synchronously processing message with ID: {id(message)}")
            
            # Log message details for debugging
            if hasattr(message, 'message_type'):
                self.logger.info(f"[FMS] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                self.logger.info(f"[FMS] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                self.logger.info(f"[FMS] Command name: {message.command_name}")
                
            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}
                
            # Mark as processed by FMS
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []
                    
                if 'flightManagementSystem' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('flightManagementSystem')
            
            # For logging purposes
            self.logger.info(f"[FMS] Message successfully processed")
            return True
            
        except Exception as e:
            self.logger.error(f"[FMS] Error processing message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
