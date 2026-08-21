"""
Radar Management Message Definitions

This package contains radar-local message definitions to maintain proper system boundaries.
"""

# Import all message classes for easy access
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.radar_base_message import (
    RadarBaseMessage,
    register_message_type,
    create_message,
    MESSAGE_REGISTRY
)

from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.weather_data import (
    PrecipitationData,
    WeatherRadarVILData,
    WeatherRadarPrecipitationRequest,
    WeatherRadarPrecipitationResponse,
    WeatherRadarVILRequest,
    WeatherRadarVILResponse
)

# Re-export message types
__all__ = [
    'RadarBaseMessage',
    'register_message_type',
    'create_message', 
    'MESSAGE_REGISTRY',
    'PrecipitationData',
    'WeatherRadarVILData',
    'WeatherRadarPrecipitationRequest',
    'WeatherRadarPrecipitationResponse',
    'WeatherRadarVILRequest',
    'WeatherRadarVILResponse'
]
