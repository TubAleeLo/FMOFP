"""
Radar Rendering Package

Provides advanced rendering capabilities for weather radar displays.
"""

from .radar_rendering_engine import RadarRenderingEngine
from .weather_data_buffer_manager import WeatherDataBufferManager
from .radar_point_renderer import RadarPointRenderer
# Import EnhancedRadarDisplay at the end to avoid circular imports
from .animation_controller import get_animation_controller
from .spatial_partitioning import get_spatial_grid, get_dirty_region_tracker
from .particle_system import get_particle_system
from .particle_renderer import get_particle_renderer

# Deferred import to avoid circular dependency
def get_enhanced_radar_display():
    from .enhanced_radar_display import EnhancedRadarDisplay
    return EnhancedRadarDisplay

__all__ = [
    'RadarRenderingEngine', 
    'WeatherDataBufferManager', 
    'RadarPointRenderer', 
    'get_enhanced_radar_display',
    'get_animation_controller',
    'get_spatial_grid',
    'get_dirty_region_tracker',
    'get_particle_system',
    'get_particle_renderer'
]
