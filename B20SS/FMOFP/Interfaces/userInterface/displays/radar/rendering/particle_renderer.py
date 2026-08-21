"""
Particle-based Renderer for Weather Radar Visualization

Integrates the particle system with the radar rendering engine to provide
realistic, fluid-like visualization of weather phenomena.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QBrush, QPainterPath
from typing import Dict, List, Any, Optional, Tuple
import math
import time
import uuid

from Utils.logger.sys_logger import get_logger

# Import particle system
from .particle_system import get_particle_system
from .animation_controller import get_animation_controller

logger = get_logger()

class ParticleRenderer:
    """
    Renders weather data using the particle system.
    
    This class integrates the particle system with the radar rendering engine,
    providing a more realistic visualization of weather phenomena.
    """
    
    def __init__(self):
        """Initialize the particle renderer."""
        # Get particle system
        self.particle_system = get_particle_system()
        
        # Get animation controller
        self.animation_controller = get_animation_controller()
        
        # Settings
        self.settings = {
            'enable_particles': True,
            'quality_level': 3,  # 1-5
            'wind_direction': 45.0,  # degrees (0 = east, 90 = north)
            'wind_speed': 20.0,  # pixels per second
            'turbulence': 0.2,  # random movement factor
            'enable_clustering': True,
            'enable_wind': True,
            'enable_turbulence': True
        }
        
        # Statistics
        self.stats = {
            'render_time': 0.0,
            'update_time': 0.0,
            'precipitation_points': 0,
            'vil_points': 0,
            'cell_points': 0
        }
        
        # Apply settings to animation controller
        self._apply_settings_to_animation_controller()
        
        logger.info("[PARTICLE_RENDERER] Initialized")
        
    def _apply_settings_to_animation_controller(self):
        """Apply settings to animation controller."""
        try:
            # Set wind direction and speed
            self.animation_controller.set_parameter('wind_direction', self.settings['wind_direction'])
            self.animation_controller.set_parameter('wind_speed', self.settings['wind_speed'])
            
            # Set turbulence
            self.animation_controller.set_parameter('turbulence', self.settings['turbulence'])
            
            # Set animation speed based on quality level
            animation_speed = 1.0
            if self.settings['quality_level'] == 1:
                animation_speed = 0.8  # Slower for low quality
            elif self.settings['quality_level'] == 2:
                animation_speed = 0.9
            elif self.settings['quality_level'] == 3:
                animation_speed = 1.0  # Normal for medium quality
            elif self.settings['quality_level'] == 4:
                animation_speed = 1.1
            elif self.settings['quality_level'] == 5:
                animation_speed = 1.2  # Faster for high quality
                
            self.animation_controller.set_parameter('animation_speed', animation_speed)
            
            logger.info(f"[PARTICLE_RENDERER] Applied settings to animation controller")
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error applying settings to animation controller: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def update_settings(self, settings: Dict[str, Any]):
        """
        Update renderer settings.
        
        Args:
            settings: New settings
        """
        # Update settings
        self.settings.update(settings)
        
        # Apply settings to particle system
        self.particle_system.set_quality_level(self.settings['quality_level'])
        
        # Apply settings to animation controller
        self._apply_settings_to_animation_controller()
        
        logger.info(f"[PARTICLE_RENDERER] Updated settings: {settings}")
        
    def render_precipitation(self, painter: QPainter, precipitation_data: List[Dict[str, Any]]):
        """
        Render precipitation data using particles.
        
        Args:
            painter: QPainter to render with
            precipitation_data: List of precipitation data points
        """
        try:
            start_time = time.time()
            
            # Skip if particles are disabled
            if not self.settings['enable_particles']:
                return
                
            # Update precipitation data in particle system
            self.particle_system.update_data('precipitation', precipitation_data)
            
            # Render precipitation particles
            self.particle_system.render(painter, 'precipitation')
            
            # Update statistics
            self.stats['render_time'] = time.time() - start_time
            self.stats['precipitation_points'] = len(precipitation_data)
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error rendering precipitation: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def render_vil(self, painter: QPainter, vil_data: List[Dict[str, Any]]):
        """
        Render VIL data using particles.
        
        Args:
            painter: QPainter to render with
            vil_data: List of VIL data points
        """
        try:
            start_time = time.time()
            
            # Skip if particles are disabled
            if not self.settings['enable_particles']:
                return
                
            # Update VIL data in particle system
            self.particle_system.update_data('vil', vil_data)
            
            # Render VIL particles
            self.particle_system.render(painter, 'vil')
            
            # Update statistics
            self.stats['render_time'] = time.time() - start_time
            self.stats['vil_points'] = len(vil_data)
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error rendering VIL: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def render_cells(self, painter: QPainter, cell_data: List[Dict[str, Any]]):
        """
        Render storm cell data using particles.
        
        Args:
            painter: QPainter to render with
            cell_data: List of storm cell data points
        """
        try:
            start_time = time.time()
            
            # Skip if particles are disabled
            if not self.settings['enable_particles']:
                return
                
            # Update cell data in particle system
            self.particle_system.update_data('cells', cell_data)
            
            # Render cell particles
            self.particle_system.render(painter, 'cells')
            
            # Update statistics
            self.stats['render_time'] = time.time() - start_time
            self.stats['cell_points'] = len(cell_data)
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error rendering cells: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def render_all(self, painter: QPainter, precipitation_data: List[Dict[str, Any]], 
                  vil_data: List[Dict[str, Any]], cell_data: List[Dict[str, Any]]):
        """
        Render all weather data using particles.
        
        Args:
            painter: QPainter to render with
            precipitation_data: List of precipitation data points
            vil_data: List of VIL data points
            cell_data: List of storm cell data points
        """
        try:
            start_time = time.time()
            
            # Skip if particles are disabled
            if not self.settings['enable_particles']:
                return
                
            # Update all data in particle system
            self.particle_system.update_data('precipitation', precipitation_data)
            self.particle_system.update_data('vil', vil_data)
            self.particle_system.update_data('cells', cell_data)
            
            # Render all particles
            self.particle_system.render(painter)
            
            # Update statistics
            self.stats['render_time'] = time.time() - start_time
            self.stats['precipitation_points'] = len(precipitation_data)
            self.stats['vil_points'] = len(vil_data)
            self.stats['cell_points'] = len(cell_data)
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error rendering all data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def clear_data(self):
        """Clear all data in the particle system."""
        try:
            self.particle_system.clear_data()
            
            # Reset statistics
            self.stats['precipitation_points'] = 0
            self.stats['vil_points'] = 0
            self.stats['cell_points'] = 0
            
            logger.info("[PARTICLE_RENDERER] Cleared all data")
            
        except Exception as e:
            logger.error(f"[PARTICLE_RENDERER] Error clearing data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def set_quality_level(self, quality_level: int):
        """
        Set the quality level for particle rendering.
        
        Args:
            quality_level: Quality level (1-5)
        """
        # Ensure quality level is within valid range
        quality_level = max(1, min(5, quality_level))
        
        # Update settings
        self.settings['quality_level'] = quality_level
        
        # Apply to particle system
        self.particle_system.set_quality_level(quality_level)
        
        # Apply settings to animation controller
        self._apply_settings_to_animation_controller()
        
        logger.info(f"[PARTICLE_RENDERER] Set quality level to {quality_level}")
        
    def set_wind_parameters(self, direction: float, speed: float):
        """
        Set wind direction and speed.
        
        Args:
            direction: Wind direction in degrees (0 = east, 90 = north)
            speed: Wind speed in pixels per second
        """
        # Update settings
        self.settings['wind_direction'] = direction
        self.settings['wind_speed'] = speed
        
        # Apply to animation controller
        self.animation_controller.set_parameter('wind_direction', direction)
        self.animation_controller.set_parameter('wind_speed', speed)
        
        logger.info(f"[PARTICLE_RENDERER] Set wind parameters: direction={direction}, speed={speed}")
        
    def set_turbulence(self, turbulence: float):
        """
        Set turbulence factor.
        
        Args:
            turbulence: Turbulence factor (0.0-1.0)
        """
        # Ensure turbulence is within valid range
        turbulence = max(0.0, min(1.0, turbulence))
        
        # Update settings
        self.settings['turbulence'] = turbulence
        
        # Apply to animation controller
        self.animation_controller.set_parameter('turbulence', turbulence)
        
        logger.info(f"[PARTICLE_RENDERER] Set turbulence to {turbulence}")
        
    def enable_particles(self, enabled: bool = True):
        """
        Enable or disable particle rendering.
        
        Args:
            enabled: Whether to enable particle rendering
        """
        self.settings['enable_particles'] = enabled
        logger.info(f"[PARTICLE_RENDERER] {'Enabled' if enabled else 'Disabled'} particle rendering")
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the particle renderer.
        
        Returns:
            Dictionary of statistics
        """
        # Get particle system stats
        particle_stats = self.particle_system.get_stats()
        
        # Merge with renderer stats
        stats = self.stats.copy()
        stats.update({
            'total_particles': particle_stats.get('total_particles', 0),
            'active_data_points': particle_stats.get('active_data_points', 0),
            'particle_update_time': particle_stats.get('update_time', 0.0),
            'particle_render_time': particle_stats.get('render_time', 0.0)
        })
        
        return stats


# Singleton instance
_particle_renderer = None

def get_particle_renderer() -> ParticleRenderer:
    """
    Get the singleton particle renderer instance.
    
    Returns:
        ParticleRenderer instance
    """
    global _particle_renderer
    if _particle_renderer is None:
        _particle_renderer = ParticleRenderer()
    return _particle_renderer
