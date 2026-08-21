"""
Predefined Messages Package

This package provides a central interface for sending predefined messages to various
systems in the FMOFP. It handles the complexity of message creation, formatting,
and routing, providing a clean API for other components to use.

Usage:
    from FMOFP.Interfaces.predefinedMessages import get_messages
    
    async def example():
        # Get the global Messages instance
        messages = get_messages()
        
        # Initialize the Messages system
        await messages.initialize()
        
        # Send a message
        request_id = await messages.set_weather_radar_mode("SURVEILLANCE")
"""

# Import the main Messages class and singleton getter
from FMOFP.Interfaces.predefinedMessages.Messages import Messages, get_messages

# Import all radar enums for easy access
from FMOFP.Interfaces.predefinedMessages.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode,
    RadarMode
)

__all__ = [
    # Main message interface
    'Messages',
    'get_messages',
    
    # Radar mode enums
    'weather_radarMode',
    'tfr_radarMode',
    'sar_radarMode',
    'targeting_radarMode',
    'aewc_radarMode',
    'RadarMode',
    
    # Individual message classes if needed
    'WeatherRadarMessages',
    'TFRRadarMessages',
    'SARRadarMessages',
    'TargetingRadarMessages',
    'AEWCRadarMessages',
    'FCSMessages',
    'FMSMessages',
]

# Import individual message classes
from FMOFP.Interfaces.predefinedMessages.weather_radar_messages import WeatherRadarMessages
from FMOFP.Interfaces.predefinedMessages.tfr_radar_messages import TFRRadarMessages
from FMOFP.Interfaces.predefinedMessages.sar_radar_messages import SARRadarMessages
from FMOFP.Interfaces.predefinedMessages.targeting_radar_messages import TargetingRadarMessages
from FMOFP.Interfaces.predefinedMessages.aewc_radar_messages import AEWCRadarMessages
from FMOFP.Interfaces.predefinedMessages.fcs_messages import FCSMessages
from FMOFP.Interfaces.predefinedMessages.fms_messages import FMSMessages
