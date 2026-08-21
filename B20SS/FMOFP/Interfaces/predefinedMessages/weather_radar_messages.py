"""
Weather Radar Messages Module

Provides predefined messages for the weather radar system.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any

from FMOFP.Interfaces.predefinedMessages.message_base import PredefinedMessagesBase
from FMOFP.Interfaces.predefinedMessages.radar_enums import weather_radarMode


class WeatherRadarMessages(PredefinedMessagesBase):
    """
    Class for predefined weather radar messages.
    Provides methods for creating and sending weather radar messages.
    """
    
    def create_weather_radar_mode_change_request(self, mode, **kwargs):
        """
        Create a weather radar mode change request.
        
        Args:
            mode: The mode to change to (use weather_radarMode enum)
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted mode change request
        """
        
        # Validate mode
        if isinstance(mode, int):
            mode = weather_radarMode(mode)
        elif isinstance(mode, str):
            mode = getattr(weather_radarMode, mode.upper())
        elif not isinstance(mode, weather_radarMode):
            raise ValueError(f"Invalid mode type: {type(mode)}")
            
        self.logger.info(f"Creating weather radar mode change request: {mode.name}")
        
        return mode
    
    async def weather_radar_to_surveillance_mode(self):
        """
        Set the weather radar to SURVEILLANCE mode.
        
        Returns:
            The request ID for the mode change request
        """
        
        self.logger.info("Setting weather radar to SURVEILLANCE mode")
        surveillance_mode = weather_radarMode.SURVEILLANCE
        
        # Check if radar handler is initialized
        if not self.radar_handler:
            self.logger.error("Radar handler not initialized")
            raise RuntimeError("Radar handler not initialized")
            
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="weather_radar",
            request_type="mode_change",
            data=surveillance_mode
        )
        
        self.logger.info(f"Weather radar mode change request sent with ID: {request_id}")
        return request_id
    
    async def weather_radar_to_standby_mode(self):
        """
        Set the weather radar to STANDBY mode.
        
        Returns:
            The request ID for the mode change request
        """
        
        self.logger.info("Setting weather radar to STANDBY mode")
        standby_mode = weather_radarMode.STANDBY
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="weather_radar",
            request_type="mode_change",
            data=standby_mode
        )
        
        self.logger.info(f"Weather radar mode change request sent with ID: {request_id}")
        return request_id
        
    async def set_weather_radar_mode(self, mode_name):
        """
        Set the weather radar to the specified mode.
        
        Args:
            mode_name: The name of the mode (e.g., 'SURVEILLANCE', 'STANDBY')
            
        Returns:
            The request ID for the mode change request
        """
        
        # Convert string to enum value
        try:
            if isinstance(mode_name, str):
                mode = getattr(weather_radarMode, mode_name.upper())
            elif isinstance(mode_name, int):
                mode = weather_radarMode(mode_name)
            elif isinstance(mode_name, weather_radarMode):
                mode = mode_name
            else:
                raise ValueError(f"Invalid mode type: {type(mode_name)}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Invalid weather radar mode: {mode_name}")
            raise ValueError(f"Invalid weather radar mode: {mode_name}")
            
        self.logger.info(f"Setting weather radar to {mode.name} mode")
        
        # Send mode change request
        request_id = await self.radar_handler.send_request(
            radar_name="weather_radar",
            request_type="mode_change",
            data=mode
        )
        
        self.logger.info(f"Weather radar mode change request sent with ID: {request_id}")
        return request_id

    def create_precipitation_request(self, scan_parameters=None, **kwargs):
        """
        Create a precipitation data request.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted precipitation request
        """
        from FMOFP.local_messaging.messageConfigurations.weather_radar_data import weather_radarPrecipitationRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        scan_parameters = scan_parameters or {"mode": "SURVEILLANCE"}
        
        self.logger.info(f"Creating precipitation request with UUID: {request_uuid}")
        
        precip_request = weather_radarPrecipitationRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="weather_radar",
            request_uuid=request_uuid,
            scan_parameters=scan_parameters
        )
        
        # Add command type
        precip_request.command_type = "precipitation_data"
        
        # Add metadata
        precip_request.metadata = {
            "source": "predefined_messages",
            "data_type": "precipitation",
            "test_identifier": f"precip_req_{request_uuid[-8:]}",
            "message_type": "weather_radarPrecipitationRequest"
        }
        
        return precip_request
    
    async def request_precipitation_data(self, scan_parameters=None, **kwargs):
        """
        Send a precipitation data request to the weather radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the precipitation data request
        """
        precip_request = self.create_precipitation_request(scan_parameters, **kwargs)
        
        self.logger.info("Sending precipitation data request to weather radar")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            precip_request   # Send request object
        )
        
        self.logger.info(f"Precipitation data request sent with ID: {request_id}")
        return request_id
    
    def create_vil_request(self, scan_parameters=None, **kwargs):
        """
        Create a VIL data request.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted VIL request
        """
        from FMOFP.local_messaging.messageConfigurations.weather_radar_data import weather_radarVILRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        scan_parameters = scan_parameters or {"mode": "SURVEILLANCE"}
        
        self.logger.info(f"Creating VIL request with UUID: {request_uuid}")
        
        vil_request = weather_radarVILRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="weather_radar",
            request_uuid=request_uuid,
            scan_parameters=scan_parameters
        )
        
        # Add command type
        vil_request.command_type = "vil_data"
        
        # Add metadata
        vil_request.metadata = {
            "source": "predefined_messages",
            "data_type": "vil",
            "message_type": "weather_radarVILRequest",
            "test_identifier": f"vil_req_{request_uuid[-8:]}",
        }
        
        return vil_request
    
    async def request_vil_data(self, scan_parameters=None, **kwargs):
        """
        Send a VIL data request to the weather radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the VIL data request
        """
        vil_request = self.create_vil_request(scan_parameters, **kwargs)
        
        self.logger.info("Sending VIL data request to weather radar")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            vil_request      # Send request object
        )
        
        self.logger.info(f"VIL data request sent with ID: {request_id}")
        return request_id
    
    def create_echo_top_request(self, scan_parameters=None, **kwargs):
        """
        Create an echo top data request.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            A properly formatted echo top request
        """
        from FMOFP.local_messaging.messageConfigurations.weather_radar_data_echo_top import weather_radarEchoTopRequest
        
        request_uuid = kwargs.get('request_uuid') or str(uuid.uuid4())
        scan_parameters = scan_parameters or {"mode": "SURVEILLANCE"}
        
        self.logger.info(f"Creating echo top request with UUID: {request_uuid}")
        
        echo_top_request = weather_radarEchoTopRequest(
            message_header="data_request",
            sending_system="PredefinedMessages",
            destination="weather_radar",
            request_uuid=request_uuid,
            scan_parameters=scan_parameters
        )
        
        # Add command type
        echo_top_request.command_type = "echo_top_data"
        
        # Add metadata
        echo_top_request.metadata = {
            "source": "predefined_messages",
            "data_type": "echo_top",
            "message_type": "weather_radarEchoTopRequest",
            "test_identifier": f"echo_top_req_{request_uuid[-8:]}",
        }
        
        return echo_top_request
    
    async def request_echo_top_data(self, scan_parameters=None, **kwargs):
        """
        Send an echo top data request to the weather radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the echo top data request
        """
        echo_top_request = self.create_echo_top_request(scan_parameters, **kwargs)
        
        self.logger.info("Sending echo top data request to weather radar")
        
        # Send data request
        request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            echo_top_request # Send request object
        )
        
        self.logger.info(f"Echo top data request sent with ID: {request_id}")
        return request_id
    
    async def request_combined_precipitation_vil_data(self, scan_parameters=None, **kwargs):
        """
        Send both precipitation and VIL data requests to the weather radar.
        
        Args:
            scan_parameters: Dictionary of scan parameters
            **kwargs: Additional parameters for the requests
            
        Returns:
            Tuple of request IDs for the precipitation and VIL data requests
        """
        # Ensure radar is in SURVEILLANCE mode
        await self.weather_radar_to_surveillance_mode()
        
        # Wait for mode change to take effect
        await asyncio.sleep(1.5)
        
        # Create precipitation request
        precip_request = self.create_precipitation_request(scan_parameters, **kwargs)
        
        # Send precipitation request
        self.logger.info("Sending precipitation data request")
        precip_request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            precip_request   # Send request object
        )
        self.logger.info(f"Precipitation request sent with ID: {precip_request_id}")
        
        # Wait minimally between requests
        await asyncio.sleep(0.01)
        
        # Create VIL request
        vil_request = self.create_vil_request(scan_parameters, **kwargs)
        
        # Send VIL request
        self.logger.info("Sending VIL data request")
        vil_request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            vil_request      # Send request object
        )
        self.logger.info(f"VIL request sent with ID: {vil_request_id}")
        
        return (precip_request_id, vil_request_id)
