"""
Radar display package.
"""
from .base_radar_display import BaseRadarDisplay
# Import other radar displays but defer WeatherRadarDisplay to avoid circular imports
from .targeting_radar_display import TargetingRadarDisplay
from .tfr_radar_display import TFRRadarDisplay
from .sar_radar_display import SARRadarDisplay
from .aewc_radar_display import AEWCRadarDisplay
from .radar_display_factory import RadarDisplayFactory
from .mode_handlers import (
    WeatherRadarModeHandler,
    SARRadarModeHandler,
    TFRRadarModeHandler,
    TargetingRadarModeHandler,
    AEWCRadarModeHandler
)

# Deferred import to avoid circular dependency
def get_weather_radar_display():
    from .weather_radar_display import WeatherRadarDisplay
    return WeatherRadarDisplay

__all__ = [
    'BaseRadarDisplay',
    'get_weather_radar_display',  # Use function instead of direct class
    'TargetingRadarDisplay',
    'TFRRadarDisplay',
    'SARRadarDisplay',
    'AEWCRadarDisplay',
    'RadarDisplayFactory',
    'WeatherRadarModeHandler',
    'SARRadarModeHandler',
    'TFRRadarModeHandler',
    'TargetingRadarModeHandler',
    'AEWCRadarModeHandler'
]
