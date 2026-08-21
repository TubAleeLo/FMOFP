"""
Predefined Messages Module

Provides a central access point to all predefined message types in the FMOFP system.
This module handles the initialization and aggregation of all message subsystems.
"""

import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, Tuple, Union

# Import all message subsystems
from FMOFP.Interfaces.predefinedMessages.weather_radar_messages import WeatherRadarMessages
from FMOFP.Interfaces.predefinedMessages.tfr_radar_messages import TFRRadarMessages
from FMOFP.Interfaces.predefinedMessages.sar_radar_messages import SARRadarMessages
from FMOFP.Interfaces.predefinedMessages.targeting_radar_messages import TargetingRadarMessages
from FMOFP.Interfaces.predefinedMessages.aewc_radar_messages import AEWCRadarMessages
from FMOFP.Interfaces.predefinedMessages.fcs_messages import FCSMessages
from FMOFP.Interfaces.predefinedMessages.fms_messages import FMSMessages

# Import radar enums for easy access
from FMOFP.Interfaces.predefinedMessages.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode,
    RadarMode
)

# Import radar message handler
from FMOFP.local_messaging.routing.handlers.system_message_handlers.RadarMessageHandler import get_radar_message_handler

# Import logging utilities
from FMOFP.Utils.logger.sys_logger import get_logger


class Messages:
    """
    Central access point for all predefined messages in the FMOFP system.
    
    This class initializes and provides access to all predefined message subsystems,
    handling the complexity of setting up message handlers and providing a clean API.
    """
    
    def __init__(self):
        """Initialize the Messages class and all message subsystems."""
        self.logger = get_logger()
        self.logger.info("Initializing Predefined Messages system")
        
        # Get the radar message handler
        self._radar_handler = None
        self._initialized = False
        
        # Message subsystems (initialized in _initialize)
        self.weather_radar = None
        self.tfr_radar = None
        self.sar_radar = None
        self.targeting_radar = None
        self.aewc_radar = None
        self.fcs = None
        self.fms = None
    
    async def initialize(self):
        """
        Initialize all message subsystems asynchronously.
        
        This method must be called before using any of the message subsystems.
        It sets up the message handlers and initializes all predefined message classes.
        """
        if self._initialized:
            self.logger.info("Predefined Messages system already initialized")
            return
            
        self.logger.info("Starting asynchronous initialization of Predefined Messages system")
        
        # Get the radar message handler
        try:
            self._radar_handler = get_radar_message_handler()
            self.logger.info("Radar message handler retrieved successfully")
        except Exception as e:
            self.logger.error(f"Error retrieving radar message handler: {e}")
            raise RuntimeError("Failed to initialize Predefined Messages system: radar message handler unavailable")
        
        # Initialize all message subsystems with the radar handler
        try:
            # First create all instances
            self.weather_radar = WeatherRadarMessages()
            self.tfr_radar = TFRRadarMessages()
            self.sar_radar = SARRadarMessages()
            self.targeting_radar = TargetingRadarMessages()
            self.aewc_radar = AEWCRadarMessages()
            self.fcs = FCSMessages()
            self.fms = FMSMessages()
            
            # Then initialize each instance with proper error handling
            try:
                await self.weather_radar.initialize(self._radar_handler)
                self.logger.info("Weather radar messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing weather radar messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.tfr_radar.initialize(self._radar_handler)
                self.logger.info("TFR radar messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing TFR radar messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.sar_radar.initialize(self._radar_handler)
                self.logger.info("SAR radar messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing SAR radar messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.targeting_radar.initialize(self._radar_handler)
                self.logger.info("Targeting radar messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing targeting radar messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.aewc_radar.initialize(self._radar_handler)
                self.logger.info("AEWC radar messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing AEWC radar messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.fcs.initialize(self._radar_handler)
                self.logger.info("FCS messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing FCS messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
                
            try:
                await self.fms.initialize(self._radar_handler)
                self.logger.info("FMS messages initialized")
            except Exception as e:
                self.logger.error(f"Error initializing FMS messages: {e}")
                self.logger.error(traceback.format_exc())
                raise
            
            self._initialized = True
            self.logger.info("Predefined Messages system initialization complete")
        except Exception as e:
            self.logger.error(f"Error initializing message subsystems: {e}")
            raise RuntimeError(f"Failed to initialize Predefined Messages system: {e}")
    
    async def is_initialized(self) -> bool:
        """
        Check if the Messages system is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized and self._radar_handler is not None
    
    async def _ensure_initialized(self):
        """
        Ensure the Messages system is initialized before use.
        
        Raises:
            RuntimeError: If the system is not initialized
        """
        if not await self.is_initialized():
            raise RuntimeError("Predefined Messages system not initialized. Call initialize() first.")
    
    # Weather radar convenience methods
    async def set_weather_radar_mode(self, mode_name: Union[str, int, weather_radarMode]) -> str:
        """
        Set the weather radar to the specified mode.
        
        Args:
            mode_name: The mode to set (name, value, or enum)
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.weather_radar.set_weather_radar_mode(mode_name)
    
    async def request_precipitation_data(self, scan_parameters=None, **kwargs) -> str:
        """
        Request precipitation data from the weather radar.
        
        Args:
            scan_parameters: Parameters for the scan
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the data request
        """
        await self._ensure_initialized()
        return await self.weather_radar.request_precipitation_data(scan_parameters, **kwargs)
    
    async def request_vil_data(self, scan_parameters=None, **kwargs) -> str:
        """
        Request VIL data from the weather radar.
        
        Args:
            scan_parameters: Parameters for the scan
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the data request
        """
        await self._ensure_initialized()
        return await self.weather_radar.request_vil_data(scan_parameters, **kwargs)
    
    # TFR radar convenience methods
    async def set_tfr_radar_mode(self, mode_name: Union[str, int, tfr_radarMode]) -> str:
        """
        Set the TFR radar to the specified mode.
        
        Args:
            mode_name: The mode to set (name, value, or enum)
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.tfr_radar.set_tfr_radar_mode(mode_name)
    
    async def request_elevation_data(self, scan_parameters=None, **kwargs) -> str:
        """
        Request elevation data from the TFR radar.
        
        Args:
            scan_parameters: Parameters for the scan
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the data request
        """
        await self._ensure_initialized()
        try:
            return await self.tfr_radar.request_tfr_elevation_data(scan_parameters, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in request_elevation_data: {e}")
            self.logger.error(traceback.format_exc())
            # Fallback to the standard method if needed
            return await self.tfr_radar.request_elevation_data(scan_parameters, **kwargs)
    
    # SAR radar convenience methods
    async def set_sar_radar_mode(self, mode_name: Union[str, int, sar_radarMode]) -> str:
        """
        Set the SAR radar to the specified mode.
        
        Args:
            mode_name: The mode to set (name, value, or enum)
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.sar_radar.set_sar_radar_mode(mode_name)
    
    async def request_imagery_data(self, scan_parameters=None, **kwargs) -> str:
        """
        Request imagery data from the SAR radar.
        
        Args:
            scan_parameters: Parameters for the scan
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the data request
        """
        await self._ensure_initialized()
        return await self.sar_radar.request_imagery_data(scan_parameters, **kwargs)
    
    # Targeting radar convenience methods
    async def set_targeting_radar_mode(self, mode_name: Union[str, int, targeting_radarMode]) -> str:
        """
        Set the targeting radar to the specified mode.
        
        Args:
            mode_name: The mode to set (name, value, or enum)
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.targeting_radar.set_targeting_radar_mode(mode_name)
    
    async def request_targeting_radar_track_data(self, track_parameters=None, **kwargs) -> str:
        """
        Send a track data request to the targeting radar.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the track data request
        """
        await self._ensure_initialized()
        return await self.targeting_radar.request_track_data(track_parameters, **kwargs)
    
    async def request_track_data(self, track_parameters=None, **kwargs) -> str:
        """
        Alias for request_targeting_radar_track_data.
        Added for compatibility with test functions.
        
        Args:
            track_parameters: Dictionary of track parameters
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the track data request
        """
        await self._ensure_initialized()
        return await self.targeting_radar.request_track_data(track_parameters, **kwargs)
        
    async def request_targeting_radar_lock(self, track_id: str, lock_parameters=None, **kwargs) -> str:
        """
        Request a lock on a target from the targeting radar.
        
        Args:
            track_id: The ID of the track to lock onto
            lock_parameters: Parameters for the lock
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the lock request
        """
        await self._ensure_initialized()
        return await self.targeting_radar.request_targeting_radar_lock(track_id, lock_parameters, **kwargs)
    
    # AEWC radar convenience methods
    async def set_aewc_radar_mode(self, mode_name: Union[str, int, aewc_radarMode]) -> str:
        """
        Set the AEWC radar to the specified mode.
        
        Args:
            mode_name: The mode to set (name, value, or enum)
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.aewc_radar.set_aewc_radar_mode(mode_name)
    
    async def request_aewc_radar_sector_scan(self, azimuth_start=0, azimuth_end=90, elevation=0, **kwargs) -> str:
        """
        Request a sector scan from the AEWC radar.
        
        Args:
            azimuth_start: Starting azimuth angle in degrees
            azimuth_end: Ending azimuth angle in degrees
            elevation: Elevation angle in degrees
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the sector scan request
        """
        await self._ensure_initialized()
        return await self.aewc_radar.request_aewc_radar_sector_scan(azimuth_start, azimuth_end, elevation, **kwargs)
        
    async def request_sector_scan(self, azimuth_start=0, azimuth_end=90, elevation=0, **kwargs) -> str:
        """
        Alias for request_aewc_radar_sector_scan.
        Added for compatibility with test functions.
        
        Args:
            azimuth_start: Starting azimuth angle in degrees
            azimuth_end: Ending azimuth angle in degrees
            elevation: Elevation angle in degrees
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the sector scan request
        """
        await self._ensure_initialized()
        return await self.aewc_radar.request_sector_scan(azimuth_start, azimuth_end, elevation, **kwargs)
    
    # FCS convenience methods
    async def request_control_surface_change(self, surface_name, position, rate=None, **kwargs) -> str:
        """
        Request a control surface change from the FCS.
        
        Args:
            surface_name: Name of the control surface
            position: Position value
            rate: Rate of movement
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the surface change request
        """
        await self._ensure_initialized()
        return await self.fcs.request_control_surface_change(surface_name, position, rate, **kwargs)
    
    async def request_flight_mode_change(self, mode_name, mode_params=None, **kwargs) -> str:
        """
        Request a flight mode change from the FCS.
        
        Args:
            mode_name: Name of the flight mode
            mode_params: Parameters for the mode
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the mode change request
        """
        await self._ensure_initialized()
        return await self.fcs.request_flight_mode_change(mode_name, mode_params, **kwargs)
        
    async def request_autopilot_command(self, command_type, target_value=None, **kwargs) -> str:
        """
        Request an autopilot command from the FCS.
        
        Args:
            command_type: Type of autopilot command (e.g., 'altitude_hold')
            target_value: Target value for the command (e.g., altitude in feet)
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the autopilot command request
        """
        await self._ensure_initialized()
        return await self.fcs.request_autopilot_command(command_type, target_value, **kwargs)
    
    # FMS convenience methods
    async def request_attitude_update(self, pitch=0.0, roll=0.0, yaw=0.0, **kwargs) -> str:
        """
        Send an attitude update request to the FMS.
        
        Args:
            pitch: Pitch angle in degrees
            roll: Roll angle in degrees
            yaw: Yaw angle in degrees
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the attitude update request
        """
        await self._ensure_initialized()
        return await self.fms.request_attitude_update(pitch, roll, yaw, **kwargs)
    
    async def update_attitude(self, attitude_data=None, **kwargs) -> str:
        """
        Alias for request_attitude_update.
        
        Args:
            attitude_data: Dictionary containing attitude data
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the attitude update request
        """
        await self._ensure_initialized()
        return await self.fms.update_attitude(attitude_data, **kwargs)
    
    async def request_navigation_update(self, latitude=0.0, longitude=0.0, altitude=0.0, 
                                 heading=0.0, airspeed=0.0, **kwargs) -> str:
        """
        Request a navigation update from the FMS.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            altitude: Altitude in feet
            heading: Heading in degrees
            airspeed: Airspeed in knots
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the navigation update request
        """
        await self._ensure_initialized()
        return await self.fms.request_navigation_update(
            latitude, longitude, altitude, heading, airspeed, **kwargs
        )
        
    async def update_navigation(self, nav_data=None, **kwargs) -> str:
        """
        Alias for request_navigation_update.
        
        Args:
            nav_data: Dictionary containing navigation data
            **kwargs: Additional parameters for the request
            
        Returns:
            The request ID for the navigation update request
        """
        await self._ensure_initialized()
        return await self.fms.update_navigation(nav_data, **kwargs)
    
    async def request_maneuver(self, maneuver_type, maneuver_params=None, **kwargs) -> str:
        """
        Request a maneuver from the FMS.
        
        Args:
            maneuver_type: Type of maneuver
            maneuver_params: Parameters for the maneuver
            **kwargs: Additional parameters
            
        Returns:
            The request ID for the maneuver request
        """
        await self._ensure_initialized()
        return await self.fms.request_maneuver(maneuver_type, maneuver_params, **kwargs)


# Create a singleton instance for global access
_messages_instance = None

def get_messages() -> Messages:
    """
    Get the global Messages instance.
    
    Returns:
        The global Messages instance
    """
    global _messages_instance
    if _messages_instance is None:
        _messages_instance = Messages()
    return _messages_instance
