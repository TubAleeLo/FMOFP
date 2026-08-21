"""
Radar Rendering Engine

Provides advanced rendering capabilities for weather radar displays.
Implements realistic visualization of weather phenomena.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QBrush, QPainterPath
from typing import Dict, List, Any, Optional, Tuple
import math
import time
import uuid
import numpy as np

from Utils.logger.sys_logger import get_logger

# Import implemented components
from .weather_data_buffer_manager import WeatherDataBufferManager
from .radar_point_renderer import RadarPointRenderer
from .particle_renderer import get_particle_renderer
from .animation_controller import get_animation_controller
from .spatial_partitioning import get_spatial_grid, get_dirty_region_tracker

# Import will be added when these classes are implemented
# from .meteorological_blender import MeteorologicalBlender
# from .temporal_integration_buffer import TemporalIntegrationBuffer
# from .radar_rendering_settings import RadarRenderingSettings

logger = get_logger()

class RadarRenderingEngine:
    """
    Core rendering engine for advanced weather radar visualization.
    Manages buffers, coordinates rendering processes, and optimizes performance.
    """
    
    def __init__(self, parent_display):
        """
        Initialize the rendering engine.
        
        Args:
            parent_display: The parent radar display widget
        """
        self.parent_display = parent_display
        
        # Initialize implemented components
        self.buffer_manager = WeatherDataBufferManager()
        self.point_renderer = RadarPointRenderer()
        self.particle_renderer = get_particle_renderer()
        self.animation_controller = get_animation_controller()
        self.spatial_grid = get_spatial_grid()
        self.dirty_region_tracker = get_dirty_region_tracker()
        
        # Placeholder for components that will be implemented later
        self.blender = None         # Will be MeteorologicalBlender
        self.settings = None        # Will be RadarRenderingSettings
        self.history_buffer = None  # Will be TemporalIntegrationBuffer
        
        # Temporary implementation for initial testing
        self._initialize_temporary_components()
        
        # Set rendering mode (traditional or particle-based)
        self.use_particle_rendering = True
        
        logger.info("[RADAR_RENDERING] Initialized RadarRenderingEngine with RadarPointRenderer and ParticleRenderer")
        
    def _initialize_temporary_components(self):
        """Initialize temporary components for testing."""
        # Simple settings dictionary until RadarRenderingSettings is implemented
        self.settings = {
            'quality_level': 3,  # 1-5
            'enable_animations': True,
            'enable_blending': True,
            'enable_temporal_integration': True,
            'precipitation_kernel_size_factor': 1.0,
            'vil_kernel_size_factor': 0.8,
            'gaussian_sigma_factor': 0.3,
            'blend_distance_factor': 1.5,
            'animation_speed': 1.0,
            'pulse_frequency': 0.5,
            'color_variation_factor': 0.1,
            'use_particle_rendering': True,
            'wind_direction': 45.0,  # degrees (0 = east, 90 = north)
            'wind_speed': 20.0,      # pixels per second
            'turbulence': 0.2        # random movement factor
        }
        
        # Create temporary buffer
        self._temp_buffer = None
        self._temp_buffer_size = QSize(0, 0)
        
        # Temporary data storage
        self._precipitation_data = []
        self._vil_data = []
        
        logger.info("[RADAR_RENDERING] Initialized temporary components")
        
    def initialize(self):
        """Initialize all rendering components and buffers."""
        # Initialize buffers with parent display size
        if self.parent_display is not None:
            size = QSize(self.parent_display.width(), self.parent_display.height())
            self.buffer_manager.initialize_buffers(size)
            
        logger.info("[RADAR_RENDERING] Engine initialization complete")
        
    def render_frame(self, painter: QPainter, rect: QRectF, precipitation_data: List[Dict], 
                    vil_data: List[Dict], cell_data: List[Dict] = None):
        """
        Render a complete frame with all weather data.
        
        Args:
            painter: QPainter to render with
            rect: Target rectangle
            precipitation_data: List of precipitation data points
            vil_data: List of VIL data points
        """
        try:
            # Store data for reference
            self._precipitation_data = precipitation_data
            self._vil_data = vil_data
            self._cell_data = cell_data if cell_data is not None else []
            
            # Ensure buffer manager is initialized with the correct size
            buffer_size = QSize(int(rect.width()), int(rect.height()))
            self.buffer_manager.initialize_buffers(buffer_size)
            
            # Check if we should use particle rendering
            if self.use_particle_rendering and self.settings['use_particle_rendering']:
                # Use particle renderer for all data types
                self.particle_renderer.render_all(painter, precipitation_data, vil_data, self._cell_data)
                
                logger.debug(f"[RADAR_RENDERING] Rendered frame with particle renderer: {len(precipitation_data)} precipitation points, {len(vil_data)} VIL points, {len(self._cell_data)} cell points")
            else:
                # Use traditional buffer-based rendering
                # Clear all buffers
                self.buffer_manager.clear_buffer()
                
                # Get buffer painters for each data type
                precip_painter = self.buffer_manager.get_buffer_painter('precipitation')
                vil_painter = self.buffer_manager.get_buffer_painter('vil')
                cell_painter = self.buffer_manager.get_buffer_painter('cells')
                
                if precip_painter is not None:
                    # Render precipitation data
                    self._render_precipitation_data(precip_painter, precipitation_data)
                    precip_painter.end()
                    
                if vil_painter is not None:
                    # Render VIL data
                    self._render_vil_data(vil_painter, vil_data)
                    vil_painter.end()
                    
                if cell_painter is not None and self._cell_data:
                    # Render cell data
                    self._render_cell_data(cell_painter, self._cell_data)
                    cell_painter.end()
                    
                # Composite all layers
                composite_buffer = self.buffer_manager.composite_layers()
                
                # Draw composite buffer to main painter
                painter.drawImage(rect.topLeft(), composite_buffer)
                
                logger.debug(f"[RADAR_RENDERING] Rendered frame with traditional renderer: {len(precipitation_data)} precipitation points, {len(vil_data)} VIL points, {len(self._cell_data)} cell points")
            
        except Exception as e:
            logger.error(f"[RADAR_RENDERING] Error rendering frame: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _render_precipitation_data(self, painter: QPainter, precipitation_data: List[Dict]):
        """
        Render precipitation data to the buffer.
        
        Args:
            painter: QPainter to render with
            precipitation_data: List of precipitation data points
        """
        try:
            # Update point renderer settings from engine settings
            self.point_renderer.update_settings({
                'precipitation_kernel_size_factor': self.settings['precipitation_kernel_size_factor'],
                'gaussian_sigma_factor': self.settings['gaussian_sigma_factor'],
                'animation_enabled': self.settings['enable_animations'],
                'animation_speed': self.settings['animation_speed'],
                'pulse_frequency': self.settings['pulse_frequency'],
                'color_variation_factor': self.settings['color_variation_factor']
            })
            
            # Render each precipitation data point using the point renderer
            for precip in precipitation_data:
                # Convert position to QPointF if needed
                position = precip.get('position', (0.0, 0.0))
                if isinstance(position, tuple) and len(position) >= 2:
                    # Create a copy of the data with QPointF position
                    precip_data = precip.copy()
                    precip_data['position'] = QPointF(position[0], position[1])
                    
                    # Render the point
                    self.point_renderer.render_point(painter, precip_data, 'precipitation')
                
        except Exception as e:
            logger.error(f"[RADAR_RENDERING] Error rendering precipitation: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _render_vil_data(self, painter: QPainter, vil_data: List[Dict]):
        """
        Render VIL data to the buffer.
        
        Args:
            painter: QPainter to render with
            vil_data: List of VIL data points
        """
        try:
            # Update point renderer settings from engine settings
            self.point_renderer.update_settings({
                'vil_kernel_size_factor': self.settings['vil_kernel_size_factor'],
                'gaussian_sigma_factor': self.settings['gaussian_sigma_factor'],
                'animation_enabled': self.settings['enable_animations'],
                'animation_speed': self.settings['animation_speed'],
                'pulse_frequency': self.settings['pulse_frequency'],
                'color_variation_factor': self.settings['color_variation_factor']
            })
            
            # Render each VIL data point using the point renderer
            for vil in vil_data:
                # Convert position to QPointF if needed
                position = vil.get('position', (0.0, 0.0))
                if isinstance(position, tuple) and len(position) >= 2:
                    # Create a copy of the data with QPointF position
                    vil_data_point = vil.copy()
                    vil_data_point['position'] = QPointF(position[0], position[1])
                    
                    # Render the point
                    self.point_renderer.render_point(painter, vil_data_point, 'vil')
                
        except Exception as e:
            logger.error(f"[RADAR_RENDERING] Error rendering VIL: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _draw_gaussian_blob(self, painter: QPainter, center: QPointF, size: float, color: QColor, sigma_factor: float = 0.3):
        """
        Draw a Gaussian blob at the specified position.
        
        Args:
            painter: QPainter to render with
            center: Center position of the blob
            size: Size of the blob
            color: Color of the blob
            sigma_factor: Controls the spread of the Gaussian (smaller = sharper)
        """
        try:
            # Calculate sigma based on size
            sigma = size * sigma_factor
            
            # Create radial gradient for Gaussian approximation
            gradient = self._create_gaussian_gradient(size, color, sigma)
            
            # Draw the blob
            blob_rect = QRectF(
                center.x() - size,
                center.y() - size,
                size * 2,
                size * 2
            )
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(blob_rect)
            
        except Exception as e:
            logger.error(f"[RADAR_RENDERING] Error drawing Gaussian blob: {str(e)}")
            
    def _create_gaussian_gradient(self, size: float, color: QColor, sigma: float):
        """
        Create a radial gradient that approximates a Gaussian distribution.
        
        Args:
            size: Size of the gradient
            color: Center color
            sigma: Sigma parameter for the Gaussian
            
        Returns:
            QRadialGradient configured for Gaussian appearance
        """
        from PyQt6.QtGui import QRadialGradient
        
        # Create gradient
        gradient = QRadialGradient(size, size, size)
        gradient.setCoordinateMode(QRadialGradient.CoordinateMode.ObjectBoundingMode)
        
        # Calculate stops for Gaussian approximation
        stops = 8  # Number of gradient stops
        for i in range(stops):
            # Position from center (0.0) to edge (1.0)
            pos = i / (stops - 1)
            
            # Calculate Gaussian value at this position
            # exp(-0.5 * (x/sigma)^2)
            gaussian_value = math.exp(-0.5 * (pos / sigma) ** 2)
            
            # Create color with alpha adjusted by Gaussian value
            stop_color = QColor(color)
            stop_color.setAlpha(int(color.alpha() * gaussian_value))
            
            # Add stop to gradient
            gradient.setColorAt(pos, stop_color)
            
        return gradient
        
    def _render_cell_data(self, painter: QPainter, cell_data: List[Dict]):
        """
        Render cell data to the buffer.
        
        Args:
            painter: QPainter to render with
            cell_data: List of cell data points
        """
        try:
            # Update point renderer settings from engine settings
            self.point_renderer.update_settings({
                'quality_level': self.settings['quality_level'],
                'gaussian_sigma_factor': self.settings['gaussian_sigma_factor'],
                'animation_enabled': self.settings['enable_animations'],
                'animation_speed': self.settings['animation_speed'],
                'pulse_frequency': self.settings['pulse_frequency'],
                'color_variation_factor': self.settings['color_variation_factor']
            })
            
            # Render each cell data point using the point renderer
            for cell in cell_data:
                # Convert position to QPointF if needed
                position = cell.get('position', (0.0, 0.0))
                if isinstance(position, tuple) and len(position) >= 2:
                    # Create a copy of the data with QPointF position
                    cell_data_point = cell.copy()
                    cell_data_point['position'] = QPointF(position[0], position[1])
                    
                    # Render the point
                    self.point_renderer.render_point(painter, cell_data_point, 'cells')
                
        except Exception as e:
            logger.error(f"[RADAR_RENDERING] Error rendering cells: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def update_data(self, data_type: str, data_points: List[Dict]):
        """
        Update a specific data type in the rendering engine.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', etc.)
            data_points: List of data points
        """
        # Store data for reference
        if data_type == 'precipitation':
            self._precipitation_data = data_points
        elif data_type == 'vil':
            self._vil_data = data_points
        elif data_type == 'cells':
            self._cell_data = data_points
            
        # Check if we should use particle rendering
        if self.use_particle_rendering and self.settings['use_particle_rendering']:
            # Update data in particle renderer
            if data_type == 'precipitation':
                self.particle_renderer.render_precipitation(None, data_points)
            elif data_type == 'vil':
                self.particle_renderer.render_vil(None, data_points)
            elif data_type == 'cells':
                self.particle_renderer.render_cells(None, data_points)
        else:
            # Use traditional buffer-based rendering
            # Clear the specific buffer
            self.buffer_manager.clear_buffer(data_type)
            
            # Get buffer painter
            buffer_painter = self.buffer_manager.get_buffer_painter(data_type)
            if buffer_painter is not None:
                # Render data to buffer
                if data_type == 'precipitation':
                    self._render_precipitation_data(buffer_painter, data_points)
                elif data_type == 'vil':
                    self._render_vil_data(buffer_painter, data_points)
                elif data_type == 'cells':
                    self._render_cell_data(buffer_painter, data_points)
                    
                # End painting
                buffer_painter.end()
            
        logger.debug(f"[RADAR_RENDERING] Updated {data_type} data with {len(data_points)} points")
        
    def set_rendering_quality(self, quality_level: int):
        """
        Set the rendering quality level.
        
        Args:
            quality_level: Quality level (1-5)
        """
        # Ensure quality level is within valid range
        quality_level = max(1, min(5, quality_level))
        
        # Update settings
        self.settings['quality_level'] = quality_level
        
        # Update particle renderer quality
        if self.particle_renderer:
            self.particle_renderer.set_quality_level(quality_level)
        
        # Adjust other settings based on quality level
        if quality_level == 1:  # Low
            self.settings['precipitation_kernel_size_factor'] = 0.7
            self.settings['vil_kernel_size_factor'] = 0.6
            self.settings['gaussian_sigma_factor'] = 0.4  # Wider, less detailed
            self.settings['blend_distance_factor'] = 1.0
            self.settings['wind_speed'] = 15.0
            self.settings['turbulence'] = 0.1
            texture_enabled = False
            noise_factor = 0.05
        elif quality_level == 2:  # Medium-Low
            self.settings['precipitation_kernel_size_factor'] = 0.8
            self.settings['vil_kernel_size_factor'] = 0.7
            self.settings['gaussian_sigma_factor'] = 0.35
            self.settings['blend_distance_factor'] = 1.2
            self.settings['wind_speed'] = 17.5
            self.settings['turbulence'] = 0.15
            texture_enabled = True
            noise_factor = 0.08
        elif quality_level == 3:  # Medium (default)
            self.settings['precipitation_kernel_size_factor'] = 1.0
            self.settings['vil_kernel_size_factor'] = 0.8
            self.settings['gaussian_sigma_factor'] = 0.3
            self.settings['blend_distance_factor'] = 1.5
            self.settings['wind_speed'] = 20.0
            self.settings['turbulence'] = 0.2
            texture_enabled = True
            noise_factor = 0.1
        elif quality_level == 4:  # High
            self.settings['precipitation_kernel_size_factor'] = 1.2
            self.settings['vil_kernel_size_factor'] = 0.9
            self.settings['gaussian_sigma_factor'] = 0.25
            self.settings['blend_distance_factor'] = 1.8
            self.settings['wind_speed'] = 22.5
            self.settings['turbulence'] = 0.25
            texture_enabled = True
            noise_factor = 0.15
        elif quality_level == 5:  # Ultra
            self.settings['precipitation_kernel_size_factor'] = 1.5
            self.settings['vil_kernel_size_factor'] = 1.0
            self.settings['gaussian_sigma_factor'] = 0.2  # Narrower, more detailed
            self.settings['blend_distance_factor'] = 2.0
            self.settings['wind_speed'] = 25.0
            self.settings['turbulence'] = 0.3
            texture_enabled = True
            noise_factor = 0.2
            
        # Update point renderer settings
        self.point_renderer.update_settings({
            'quality_level': quality_level,
            'precipitation_kernel_size_factor': self.settings['precipitation_kernel_size_factor'],
            'vil_kernel_size_factor': self.settings['vil_kernel_size_factor'],
            'gaussian_sigma_factor': self.settings['gaussian_sigma_factor'],
            'texture_enabled': texture_enabled,
            'noise_factor': noise_factor,
            'animation_enabled': self.settings['enable_animations'],
            'animation_speed': self.settings['animation_speed'],
            'pulse_frequency': self.settings['pulse_frequency'],
            'color_variation_factor': self.settings['color_variation_factor']
        })
        
        # Update particle renderer settings
        if self.particle_renderer:
            self.particle_renderer.update_settings({
                'quality_level': quality_level,
                'wind_speed': self.settings['wind_speed'],
                'turbulence': self.settings['turbulence']
            })
            
        logger.info(f"[RADAR_RENDERING] Set rendering quality to level {quality_level}")
        
    def set_particle_rendering(self, enabled: bool):
        """
        Enable or disable particle-based rendering.
        
        Args:
            enabled: Whether to enable particle rendering
        """
        self.use_particle_rendering = enabled
        self.settings['use_particle_rendering'] = enabled
        
        if self.particle_renderer:
            self.particle_renderer.enable_particles(enabled)
            
        logger.info(f"[RADAR_RENDERING] {'Enabled' if enabled else 'Disabled'} particle rendering")
        
    def set_wind_parameters(self, direction: float, speed: float):
        """
        Set wind direction and speed for particle animation.
        
        Args:
            direction: Wind direction in degrees (0 = east, 90 = north)
            speed: Wind speed in pixels per second
        """
        self.settings['wind_direction'] = direction
        self.settings['wind_speed'] = speed
        
        if self.particle_renderer:
            self.particle_renderer.set_wind_parameters(direction, speed)
            
        logger.info(f"[RADAR_RENDERING] Set wind parameters: direction={direction}, speed={speed}")
        
    def set_turbulence(self, turbulence: float):
        """
        Set turbulence factor for particle animation.
        
        Args:
            turbulence: Turbulence factor (0.0-1.0)
        """
        # Ensure turbulence is within valid range
        turbulence = max(0.0, min(1.0, turbulence))
        
        self.settings['turbulence'] = turbulence
        
        if self.particle_renderer:
            self.particle_renderer.set_turbulence(turbulence)
            
        logger.info(f"[RADAR_RENDERING] Set turbulence to {turbulence}")
