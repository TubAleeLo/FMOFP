"""
Flight Control System (FCS) Messages Module

Provides predefined messages for the FCS system.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.local_messaging.messageConfigurations.fcs_data import fcs_controlSurfaceRequest
from FMOFP.local_messaging.messageConfigurations.fcs_flight_mode import fcs_flightModeRequest
from FMOFP.local_messaging.messageConfigurations.fcs_autopilot import fcs_autoPilotRequest


class FCSMessages(PredefinedMessagesBase):
    """
    Class for predefined FCS messages.
    Provides methods for creating and sending FCS messages.
    """
    
    async def fcs_mode_change(self, mode_name):
        """
        Change the mode of the Flight Control System.
        
        Args:
            mode_name: The name of the mode to change to
            
        Returns:
            The request ID for the mode change request
        """
        self.logger.info(f"Setting FCS to {mode_name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="flightControlSystem",
            request_type="mode_change",
            data=mode_name
        )
        
        self.logger.info(f"FCS mode change request sent with ID: {request_id}")
        return request_id
    
    async def fcs_request_status(self):
        """
        Request the current status of the Flight Control System.
        
        Returns:
            The request ID for the status request
        """
        self.logger.info("Requesting FCS status")
        
        # Send status request
        request_id = await self.radar_handler.send_request(
            radar_name="flightControlSystem",
            request_type="status",
            data=None
        )
        
        self.logger.info(f"FCS status request sent with ID: {request_id}")
        return request_id
    
    def create_control_surface_request(self, surface_data, **kwargs):
        """
        Create a control surface command request for the FCS.
        
        Args:
            surface_data: Dictionary containing control surface data
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted control surface request
        """
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FCS control surface request with UUID: {request_uuid}")
        
        surface_request = fcs_controlSurfaceRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightControlSystem",
            request_uuid=request_uuid,
            surface_data=surface_data
        )
        
        # Add command type
        surface_request.command_type = "control_surface"
        
        # Add metadata
        surface_request.metadata = {
            "source": "predefined_messages",
            "data_type": "control_surface",
            "test_identifier": f"fcs_surface_req_{request_uuid[-8:]}",
            "message_type": "fcs_controlSurfaceRequest"
        }
        
        return surface_request
    
    async def request_control_surface_change(self, surface_name, position, rate=None, **kwargs):
        """
        Send a control surface change request to the FCS.
        
        Args:
            surface_name: Name of the control surface (e.g., 'aileron', 'elevator', 'rudder')
            position: Position value for the surface (degrees or percentage)
            rate: Optional rate of movement (degrees or percentage per second)
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the control surface request
        """
        surface_data = {
            "surface": surface_name,
            "position": position
        }
        
        if rate is not None:
            surface_data["rate"] = rate
        
        surface_request = self.create_control_surface_request(surface_data, **kwargs)
        
        self.logger.info(f"Sending control surface request to FCS ({surface_name}: {position})")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightControlSystem",  # Target system
            "data",                 # Command type
            surface_request         # Send request object
        )
        
        self.logger.info(f"Control surface request sent with ID: {request_id}")
        return request_id
    
    def create_flight_mode_request(self, mode_data, **kwargs):
        """
        Create a flight mode request for the FCS.
        
        Args:
            mode_data: Dictionary containing flight mode data
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted flight mode request
        """
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FCS flight mode request with UUID: {request_uuid}")
        
        mode_request = fcs_flightModeRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightControlSystem",
            request_uuid=request_uuid,
            mode_data=mode_data
        )
        
        # Add command type
        mode_request.command_type = "flight_mode"
        
        # Add metadata
        mode_request.metadata = {
            "source": "predefined_messages",
            "data_type": "flight_mode",
            "test_identifier": f"fcs_mode_req_{request_uuid[-8:]}",
            "message_type": "fcs_flightModeRequest"
        }
        
        return mode_request
    
    async def request_flight_mode_change(self, mode_name, mode_params=None, **kwargs):
        """
        Send a flight mode change request to the FCS.
        
        Args:
            mode_name: Name of the flight mode (e.g., 'normal', 'approach', 'takeoff')
            mode_params: Optional dictionary of mode parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the flight mode request
        """
        mode_data = {
            "mode": mode_name
        }
        
        if mode_params is not None:
            mode_data.update(mode_params)
        
        mode_request = self.create_flight_mode_request(mode_data, **kwargs)
        
        self.logger.info(f"Sending flight mode request to FCS (mode: {mode_name})")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightControlSystem",  # Target system
            "data",                 # Command type
            mode_request            # Send request object
        )
        
        self.logger.info(f"Flight mode request sent with ID: {request_id}")
        return request_id
        
    def create_autopilot_request(self, autopilot_data, **kwargs):
        """
        Create an autopilot command request for the FCS.
        
        Args:
            autopilot_data: Dictionary containing autopilot data
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted autopilot request
        """
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        
        self.logger.info(f"Creating FCS autopilot request with UUID: {request_uuid}")
        
        autopilot_request = fcs_autoPilotRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="flightControlSystem",
            request_uuid=request_uuid,
            autopilot_data=autopilot_data
        )
        
        # Add command type
        autopilot_request.command_type = "autopilot"
        
        # Add metadata
        autopilot_request.metadata = {
            "source": "predefined_messages",
            "data_type": "autopilot",
            "test_identifier": f"fcs_ap_req_{request_uuid[-8:]}",
            "message_type": "fcs_autoPilotRequest"
        }
        
        return autopilot_request
    
    async def request_autopilot_command(self, command, target=None, **kwargs):
        """
        Send an autopilot command to the FCS.
        
        Args:
            command: Autopilot command (e.g., 'engage', 'disengage', 'altitude_hold')
            target: Optional target value for the command (e.g., altitude in feet)
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the autopilot request
        """
        autopilot_data = {
            "command": command
        }
        
        if target is not None:
            autopilot_data["target"] = target
        
        autopilot_request = self.create_autopilot_request(autopilot_data, **kwargs)
        
        target_info = f" with target {target}" if target is not None else ""
        self.logger.info(f"Sending autopilot command to FCS ({command}{target_info})")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "flightControlSystem",  # Target system
            "data",                 # Command type
            autopilot_request       # Send request object
        )
        
        self.logger.info(f"Autopilot command sent with ID: {request_id}")
        return request_id
