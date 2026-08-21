"""
Radar Point Renderer

Renders individual weather data points using advanced techniques.
Supports multiple rendering methods including Gaussian kernels.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QBrush, QPainterPath, QRadialGradient
from typing import Dict, List, Any, Optional, Tuple
import math
import time
import uuid
import numpy as np

from Utils.logger.sys_logger import get_logger

logger = get_logger()

class RadarPointRenderer:
    """
    Renders individual weather data points using advanced techniques.
    Supports multiple rendering methods including Gaussian kernels.
    """
    
    def __init__(self):
        """Initialize renderer with default settings."""
        self.settings = {
            'quality_level': 3,  # 1-5
            'gaussian_sigma_factor': 0.3,
            'precipitation_kernel_size_factor': 1.0,
            'vil_kernel_size_factor': 0.8,
            'texture_enabled': True,
            'noise_factor': 0.1,
            'animation_enabled': True,
            'animation_speed': 1.0,
            'pulse_frequency': 0.5,
            'color_variation_factor': 0.1
        }
        
        # Cache for pre-computed kernels
        self.cached_kernels = {}
        
        # Track last kernel generation time for cache management
        self.last_cache_cleanup = time.time()
        self.cache_cleanup_interval = 60.0  # Clean up cache every minute
        
        # Initialize color maps
        self._initialize_color_maps()
        
        logger.info("[RADAR_POINT_RENDERER] Initialized with default settings")
        
    def _initialize_color_maps(self):
        """Initialize color maps for different data types."""
        # Precipitation color map
        self.precipitation_colors = {
            'rain': {
                'SEVERE': QColor(255, 0, 0, 200),      # Red
                'MODERATE': QColor(255, 165, 0, 180),  # Orange
                'LIGHT': QColor(255, 255, 0, 160),     # Yellow
                'VERY_LIGHT': QColor(0, 255, 0, 140)   # Green
            },
            'snow': {
                'SEVERE': QColor(255, 255, 255, 200),  # White
                'MODERATE': QColor(200, 200, 255, 180),  # Light blue
                'LIGHT': QColor(180, 180, 255, 160),   # Lighter blue
                'VERY_LIGHT': QColor(220, 220, 255, 140)  # Very light blue
            },
            'hail': {
                'SEVERE': QColor(255, 0, 255, 200),    # Magenta
                'MODERATE': QColor(200, 0, 200, 180),  # Purple
                'LIGHT': QColor(180, 0, 180, 160),     # Light purple
                'VERY_LIGHT': QColor(160, 0, 160, 140)  # Very light purple
            },
            'mixed': {
                'SEVERE': QColor(128, 0, 255, 200),    # Purple
                'MODERATE': QColor(100, 0, 200, 180),  # Dark purple
                'LIGHT': QColor(80, 0, 180, 160),      # Medium purple
                'VERY_LIGHT': QColor(60, 0, 160, 140)  # Light purple
            },
            'default': {
                'SEVERE': QColor(128, 128, 128, 200),  # Gray
                'MODERATE': QColor(100, 100, 100, 180),  # Dark gray
                'LIGHT': QColor(80, 80, 80, 160),      # Medium gray
                'VERY_LIGHT': QColor(60, 60, 60, 140)  # Light gray
            }
        }
        
        # VIL color map
        self.vil_colors = {
            'HIGH': QColor(255, 0, 0, 200),       # Red
            'MEDIUM': QColor(255, 165, 0, 180),   # Orange
            'LOW': QColor(255, 255, 0, 160),      # Yellow
            'MINIMAL': QColor(0, 255, 0, 140)     # Green
        }
        
        # NEXRAD-inspired color map for reflectivity
        self.reflectivity_colors = [
            QColor(0, 255, 0, 140),    # Light green (15-20 dBZ)
            QColor(0, 200, 0, 150),    # Medium green (20-25 dBZ)
            QColor(0, 150, 0, 160),    # Dark green (25-30 dBZ)
            QColor(255, 255, 0, 170),  # Yellow (30-35 dBZ)
            QColor(255, 200, 0, 180),  # Light orange (35-40 dBZ)
            QColor(255, 150, 0, 190),  # Dark orange (40-45 dBZ)
            QColor(255, 100, 0, 200),  # Red-orange (45-50 dBZ)
            QColor(255, 0, 0, 210),    # Red (50-55 dBZ)
            QColor(200, 0, 0, 220),    # Dark red (55-60 dBZ)
            QColor(150, 0, 150, 230),  # Purple (60-65 dBZ)
            QColor(100, 0, 200, 240)   # Dark purple (>65 dBZ)
        ]
        
    def render_point(self, painter: QPainter, point_data: Dict[str, Any], data_type: str):
        """
        Render a single data point.
        
        Args:
            painter: QPainter to render with
            point_data: Data point to render
            data_type: Type of data ('precipitation', 'vil', etc.)
        """
        try:
            # Extract position
            position = point_data.get('position')
            if not isinstance(position, QPointF):
                # Convert tuple/list to QPointF
                if isinstance(position, (tuple, list)) and len(position) >= 2:
                    position = QPointF(position[0], position[1])
                else:
                    logger.error(f"[RADAR_POINT_RENDERER] Invalid position format: {position}")
                    return
            
            # Determine rendering method based on data type
            if data_type == 'precipitation':
                self._render_precipitation_point(painter, position, point_data)
            elif data_type == 'vil':
                self._render_vil_point(painter, position, point_data)
            else:
                logger.warning(f"[RADAR_POINT_RENDERER] Unknown data type: {data_type}")
                
        except Exception as e:
            logger.error(f"[RADAR_POINT_RENDERER] Error rendering point: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _render_precipitation_point(self, painter: QPainter, position: QPointF, point_data: Dict[str, Any]):
        """
        Render a precipitation data point.
        
        Args:
            painter: QPainter to render with
            position: Position to render at
            point_data: Precipitation data
        """
        try:
            # Extract properties
            precip_type = point_data.get('type', 'rain')
            intensity = point_data.get('intensity', 0.5)
            rate = point_data.get('rate', 20.0)
            
            # Determine intensity level
            intensity_level = self._get_intensity_level(intensity)
            
            # Get color based on type and intensity
            color_map = self.precipitation_colors.get(precip_type, self.precipitation_colors['default'])
            base_color = color_map[intensity_level]
            
            # Apply color variation for more natural appearance
            color = self._apply_color_variation(base_color)
            
            # Calculate kernel size based on intensity and rate
            kernel_size = 15 + intensity * 10 + min(rate / 10, 5)
            kernel_size *= self.settings['precipitation_kernel_size_factor']
            
            # Apply animation effects if enabled
            if self.settings['animation_enabled']:
                # Pulse effect based on time
                pulse_factor = self._calculate_pulse_factor()
                kernel_size *= 1.0 + pulse_factor * 0.1
                
                # Adjust alpha for pulsing effect
                alpha = color.alpha()
                color.setAlpha(int(alpha * (0.9 + pulse_factor * 0.2)))
            
            # Render using Gaussian kernel
            self._render_gaussian_kernel(
                painter, 
                position, 
                kernel_size, 
                color, 
                self.settings['gaussian_sigma_factor']
            )
            
            # Add texture if enabled
            if self.settings['texture_enabled']:
                self._add_texture(painter, position, kernel_size, color)
                
        except Exception as e:
            logger.error(f"[RADAR_POINT_RENDERER] Error rendering precipitation point: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _render_vil_point(self, painter: QPainter, position: QPointF, point_data: Dict[str, Any]):
        """
        Render a VIL data point.
        
        Args:
            painter: QPainter to render with
            position: Position to render at
            point_data: VIL data
        """
        try:
            # Extract properties
            value = point_data.get('value', 20.0)
            intensity = point_data.get('intensity', 0.7)
            
            # Determine VIL level based on value
            vil_level = 'MINIMAL'
            if value > 30:
                vil_level = 'HIGH'
            elif value > 20:
                vil_level = 'MEDIUM'
            elif value > 10:
                vil_level = 'LOW'
            
            # Get color based on VIL level
            base_color = self.vil_colors[vil_level]
            
            # Apply color variation for more natural appearance
            color = self._apply_color_variation(base_color)
            
            # Calculate kernel size based on intensity and value
            kernel_size = 12 + intensity * 8 + min(value / 10, 4)
            kernel_size *= self.settings['vil_kernel_size_factor']
            
            # Apply animation effects if enabled
            if self.settings['animation_enabled']:
                # Pulse effect based on time
                pulse_factor = self._calculate_pulse_factor()
                kernel_size *= 1.0 + pulse_factor * 0.1
                
                # Adjust alpha for pulsing effect
                alpha = color.alpha()
                color.setAlpha(int(alpha * (0.9 + pulse_factor * 0.2)))
            
            # Render using Gaussian kernel
            self._render_gaussian_kernel(
                painter, 
                position, 
                kernel_size, 
                color, 
                self.settings['gaussian_sigma_factor']
            )
            
            # Add texture if enabled
            if self.settings['texture_enabled']:
                self._add_texture(painter, position, kernel_size, color)
                
        except Exception as e:
            logger.error(f"[RADAR_POINT_RENDERER] Error rendering VIL point: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _render_gaussian_kernel(self, painter: QPainter, center: QPointF, size: float, color: QColor, sigma_factor: float = 0.3):
        """
        Render a Gaussian kernel at the specified position.
        
        Args:
            painter: QPainter to render with
            center: Center position
            size: Size of the kernel
            color: Color for the kernel
            sigma_factor: Controls the spread of the Gaussian (smaller = sharper)
        """
        try:
            # Calculate sigma based on size
            sigma = size * sigma_factor
            
            # Try to get cached kernel
            cache_key = f"{int(size)}_{color.rgba()}_{sigma:.2f}"
            gradient = self.cached_kernels.get(cache_key)
            
            if gradient is None:
                # Create new gradient
                gradient = QRadialGradient(size, size, size)
                gradient.setCoordinateMode(QRadialGradient.CoordinateMode.ObjectBoundingMode)
                
                # Calculate stops for Gaussian approximation
                stops = 12  # Increased from 8 for smoother gradient
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
                
                # Cache the gradient
                self.cached_kernels[cache_key] = gradient
                
                # Clean up cache if it's getting too large
                if len(self.cached_kernels) > 100:
                    current_time = time.time()
                    if current_time - self.last_cache_cleanup > self.cache_cleanup_interval:
                        # Keep only the 50 most recent kernels
                        self.cached_kernels = dict(list(self.cached_kernels.items())[-50:])
                        self.last_cache_cleanup = current_time
                        logger.info(f"[RADAR_POINT_RENDERER] Cleaned up kernel cache, kept {len(self.cached_kernels)} kernels")
            
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
            logger.error(f"[RADAR_POINT_RENDERER] Error rendering Gaussian kernel: {str(e)}")
            
    def _add_texture(self, painter: QPainter, center: QPointF, size: float, color: QColor):
        """
        Add texture to a rendered point for more realistic appearance.
        
        Args:
            painter: QPainter to render with
            center: Center position
            size: Size of the point
            color: Base color
        """
        try:
            # Save painter state
            painter.save()
            
            # Set composition mode for texture overlay
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Create noise texture
            noise_factor = self.settings['noise_factor']
            
            # Generate random noise points
            num_points = int(size * 2)
            for _ in range(num_points):
                # Random position within the point
                angle = np.random.uniform(0, 2 * np.pi)
                distance = np.random.uniform(0, size * 0.9)
                
                x = center.x() + distance * np.cos(angle)
                y = center.y() + distance * np.sin(angle)
                
                # Random size and opacity
                point_size = np.random.uniform(1, 3)
                opacity = np.random.uniform(0.1, 0.3) * noise_factor
                
                # Create noise color
                noise_color = QColor(color)
                noise_color.setAlpha(int(noise_color.alpha() * opacity))
                
                # Draw noise point
                noise_rect = QRectF(
                    x - point_size/2,
                    y - point_size/2,
                    point_size,
                    point_size
                )
                
                painter.setBrush(QBrush(noise_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(noise_rect)
            
            # Restore painter state
            painter.restore()
            
        except Exception as e:
            logger.error(f"[RADAR_POINT_RENDERER] Error adding texture: {str(e)}")
            
    def _get_intensity_level(self, intensity: float) -> str:
        """
        Get intensity level string based on intensity value.
        
        Args:
            intensity: Intensity value (0.0-1.0)
            
        Returns:
            Intensity level string
        """
        if intensity > 0.8:
            return 'SEVERE'
        elif intensity > 0.6:
            return 'MODERATE'
        elif intensity > 0.3:
            return 'LIGHT'
        else:
            return 'VERY_LIGHT'
            
    def _apply_color_variation(self, base_color: QColor) -> QColor:
        """
        Apply slight color variation for more natural appearance.
        
        Args:
            base_color: Base color
            
        Returns:
            Color with variation applied
        """
        # Get variation factor from settings
        variation_factor = self.settings['color_variation_factor']
        
        # Apply random variation to RGB components
        r = base_color.red()
        g = base_color.green()
        b = base_color.blue()
        a = base_color.alpha()
        
        # Calculate variation range
        var_range = int(20 * variation_factor)
        
        # Apply variation
        r = max(0, min(255, r + np.random.randint(-var_range, var_range)))
        g = max(0, min(255, g + np.random.randint(-var_range, var_range)))
        b = max(0, min(255, b + np.random.randint(-var_range, var_range)))
        
        # Create new color
        return QColor(r, g, b, a)
        
    def _calculate_pulse_factor(self) -> float:
        """
        Calculate pulse factor based on time for animation effects.
        
        Returns:
            Pulse factor (0.0-1.0)
        """
        # Calculate pulse based on time
        frequency = self.settings['pulse_frequency']
        speed = self.settings['animation_speed']
        
        # Use sine wave for smooth pulsing
        return 0.5 + 0.5 * math.sin(time.time() * frequency * speed * 2 * math.pi)
        
    def update_settings(self, settings: Dict[str, Any]):
        """
        Update renderer settings.
        
        Args:
            settings: New settings
        """
        # Update settings
        self.settings.update(settings)
        
        # Clear kernel cache when settings change
        self.cached_kernels = {}
        
        logger.info(f"[RADAR_POINT_RENDERER] Updated settings: {settings}")
