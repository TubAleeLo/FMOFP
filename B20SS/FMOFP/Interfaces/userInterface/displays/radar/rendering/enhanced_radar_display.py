"""
Enhanced Radar Display

Integrates the advanced rendering engine with the WeatherRadarDisplay class.
Provides a bridge between the existing display system and the new rendering capabilities.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QBrush, QPainterPath
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
import math
import time
import uuid
import copy

from Utils.logger.sys_logger import get_logger

# Import rendering components
from .radar_rendering_engine import RadarRenderingEngine

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from ..weather_radar_display import WeatherRadarDisplay

logger = get_logger()

class EnhancedRadarDisplay:
    """
    Integration class that connects the WeatherRadarDisplay with the advanced rendering engine.
    Provides a bridge between the existing display system and the new rendering capabilities.
    """
    
    def __init__(self, weather_radar_display: 'WeatherRadarDisplay'):
        """
        Initialize the enhanced radar display.
        
        Args:
            weather_radar_display: The WeatherRadarDisplay instance to enhance
        """
        self.weather_radar_display = weather_radar_display
        
        # Create rendering engine
        self.rendering_engine = RadarRenderingEngine(weather_radar_display)
        
        # Initialize rendering engine
        self.rendering_engine.initialize()
        
        # Set default quality level
        self.rendering_engine.set_rendering_quality(3)  # Medium quality
        
        # Flag to enable/disable enhanced rendering
        self.enhanced_rendering_enabled = True
        
        # Store original render method for fallback
        self._original_render_method = weather_radar_display.render
        
        # Replace render method with enhanced version
        self._patch_render_method()
        
        logger.info("[ENHANCED_RADAR] Initialized EnhancedRadarDisplay")
        
    def _patch_render_method(self):
        """
        Replace the original render method with the enhanced version.
        This allows us to intercept rendering calls and use our advanced rendering engine.
        """
        try:
            # Store reference to self for use in the replacement method
            enhanced_display = self
            
            # Define replacement render method
            def enhanced_render(self_display, data: Dict[str, Any]):
                """
                Enhanced render method that uses the advanced rendering engine.
                Falls back to the original method if enhanced rendering is disabled.
                
                Args:
                    data: Display data to render
                """
                try:
                    # Check if enhanced rendering is enabled
                    if enhanced_display.enhanced_rendering_enabled:
                        # Extract precipitation, VIL, and cell data
                        precipitation_data = enhanced_display._extract_precipitation_data(data)
                        vil_data = enhanced_display._extract_vil_data(data)
                        cell_data = enhanced_display._extract_cell_data(data)
                        
                        # Get painter and rect from display
                        if hasattr(self_display, 'painter') and hasattr(self_display, 'rect'):
                            painter = self_display.painter
                            rect = self_display.rect
                        else:
                            # Fall back to original render method if painter or rect is not available
                            logger.warning("[ENHANCED_RADAR] Painter or rect not available, falling back to original render method")
                            return enhanced_display._original_render_method(data)
                        
                        # Use rendering engine to render the frame
                        enhanced_display.rendering_engine.render_frame(
                            painter, 
                            rect, 
                            precipitation_data, 
                            vil_data,
                            cell_data
                        )
                        
                        logger.debug("[ENHANCED_RADAR] Rendered frame with enhanced rendering engine")
                        return True
                    else:
                        # Fall back to original render method
                        return enhanced_display._original_render_method(data)
                except Exception as e:
                    logger.error(f"[ENHANCED_RADAR] Error in enhanced render method: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # Fall back to original render method
                    logger.warning("[ENHANCED_RADAR] Falling back to original render method")
                    return enhanced_display._original_render_method(data)
            
            # Replace the render method
            self.weather_radar_display.render = enhanced_render.__get__(self.weather_radar_display)
            
            logger.info("[ENHANCED_RADAR] Successfully patched render method")
            
        except Exception as e:
            logger.error(f"[ENHANCED_RADAR] Error patching render method: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _extract_precipitation_data(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Extract precipitation data from the display data.
        
        Args:
            data: Display data
            
        Returns:
            List of precipitation data points
        """
        try:
            # Initialize empty list
            precipitation_data = []
            
            # Check if data is None
            if data is None:
                return precipitation_data
                
            # Check if precipitation data is available in the display data
            if 'precipitation_data' in data:
                # Direct access
                precipitation_data = data['precipitation_data']
            elif '_precipitation_data' in data:
                # Access via private attribute
                precipitation_data = data['_precipitation_data']
            elif hasattr(self.weather_radar_display, '_precipitation_data'):
                # Access via display attribute
                precipitation_data = self.weather_radar_display._precipitation_data
            elif 'radar_data' in data and 'precipitation' in data['radar_data']:
                # Access via nested structure
                precipitation_data = data['radar_data']['precipitation']
            
            # Ensure precipitation_data is a list
            if not isinstance(precipitation_data, list):
                logger.warning(f"[ENHANCED_RADAR] Precipitation data is not a list: {type(precipitation_data)}")
                precipitation_data = []
                
            # Create a deep copy to avoid modifying the original data
            precipitation_data = copy.deepcopy(precipitation_data)
            
            # Log the number of precipitation data points
            logger.debug(f"[ENHANCED_RADAR] Extracted {len(precipitation_data)} precipitation data points")
            
            return precipitation_data
            
        except Exception as e:
            logger.error(f"[ENHANCED_RADAR] Error extracting precipitation data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
    def _extract_vil_data(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Extract VIL data from the display data.
        
        Args:
            data: Display data
            
        Returns:
            List of VIL data points
        """
        try:
            # Initialize empty list
            vil_data = []
            
            # Check if data is None
            if data is None:
                return vil_data
                
            # Check if VIL data is available in the display data
            if 'vil_data' in data:
                # Direct access
                vil_data = data['vil_data']
            elif '_vil_data' in data:
                # Access via private attribute
                vil_data = data['_vil_data']
            elif hasattr(self.weather_radar_display, '_vil_data'):
                # Access via display attribute
                vil_data = self.weather_radar_display._vil_data
            elif 'radar_data' in data and 'vil' in data['radar_data']:
                # Access via nested structure
                vil_data = data['radar_data']['vil']
            
            # Ensure vil_data is a list
            if not isinstance(vil_data, list):
                logger.warning(f"[ENHANCED_RADAR] VIL data is not a list: {type(vil_data)}")
                vil_data = []
                
            # Create a deep copy to avoid modifying the original data
            vil_data = copy.deepcopy(vil_data)
            
            # Log the number of VIL data points
            logger.debug(f"[ENHANCED_RADAR] Extracted {len(vil_data)} VIL data points")
            
            return vil_data
            
        except Exception as e:
            logger.error(f"[ENHANCED_RADAR] Error extracting VIL data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
    def enable_enhanced_rendering(self, enabled: bool = True):
        """
        Enable or disable enhanced rendering.
        
        Args:
            enabled: Whether to enable enhanced rendering
        """
        self.enhanced_rendering_enabled = enabled
        logger.info(f"[ENHANCED_RADAR] Enhanced rendering {'enabled' if enabled else 'disabled'}")
        
    def set_rendering_quality(self, quality_level: int):
        """
        Set the rendering quality level.
        
        Args:
            quality_level: Quality level (1-5)
        """
        self.rendering_engine.set_rendering_quality(quality_level)
        logger.info(f"[ENHANCED_RADAR] Set rendering quality to level {quality_level}")
        
    def _extract_cell_data(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Extract storm cell data from the display data.
        
        Args:
            data: Display data
            
        Returns:
            List of cell data points
        """
        try:
            # Initialize empty list
            cell_data = []
            
            # Check if data is None
            if data is None:
                return cell_data
                
            # Check if cell data is available in the display data
            if 'cell_data' in data:
                # Direct access
                cell_data = data['cell_data']
            elif '_cell_data' in data:
                # Access via private attribute
                cell_data = data['_cell_data']
            elif hasattr(self.weather_radar_display, '_cell_data'):
                # Access via display attribute
                cell_data = self.weather_radar_display._cell_data
            elif 'radar_data' in data and 'cells' in data['radar_data']:
                # Access via nested structure
                cell_data = data['radar_data']['cells']
            
            # Ensure cell_data is a list
            if not isinstance(cell_data, list):
                logger.warning(f"[ENHANCED_RADAR] Cell data is not a list: {type(cell_data)}")
                cell_data = []
                
            # Create a deep copy to avoid modifying the original data
            cell_data = copy.deepcopy(cell_data)
            
            # Log the number of cell data points
            logger.debug(f"[ENHANCED_RADAR] Extracted {len(cell_data)} cell data points")
            
            return cell_data
            
        except Exception as e:
            logger.error(f"[ENHANCED_RADAR] Error extracting cell data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
    def update_data(self, data_type: str, data_points: List[Dict]):
        """
        Update a specific data type in the rendering engine.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', 'cells', etc.)
            data_points: List of data points
        """
        self.rendering_engine.update_data(data_type, data_points)
        logger.debug(f"[ENHANCED_RADAR] Updated {data_type} data with {len(data_points)} points")
        
    def set_particle_rendering(self, enabled: bool = True):
        """
        Enable or disable particle-based rendering.
        
        Args:
            enabled: Whether to enable particle rendering
        """
        self.rendering_engine.set_particle_rendering(enabled)
        logger.info(f"[ENHANCED_RADAR] Particle rendering {'enabled' if enabled else 'disabled'}")
        
    def set_wind_parameters(self, direction: float, speed: float):
        """
        Set wind direction and speed for particle animation.
        
        Args:
            direction: Wind direction in degrees (0 = east, 90 = north)
            speed: Wind speed in pixels per second
        """
        self.rendering_engine.set_wind_parameters(direction, speed)
        logger.info(f"[ENHANCED_RADAR] Set wind parameters: direction={direction}, speed={speed}")
        
    def set_turbulence(self, turbulence: float):
        """
        Set turbulence factor for particle animation.
        
        Args:
            turbulence: Turbulence factor (0.0-1.0)
        """
        self.rendering_engine.set_turbulence(turbulence)
        logger.info(f"[ENHANCED_RADAR] Set turbulence to {turbulence}")
