"""
Mode-specific visualization handlers for radar displays
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath
from typing import Dict
import math
import traceback
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class WeatherRadarModeHandler:
    """Handle weather radar mode-specific visualizations"""
    
    _intensity_colors = {
        'SEVERE': QColor(255, 0, 0, 128),      # Red
        'MODERATE': QColor(255, 165, 0, 128),  # Orange
        'LIGHT': QColor(255, 255, 0, 128),     # Yellow
        'VERY_LIGHT': QColor(0, 255, 0, 128)   # Green
    }
    
    _vil_colors = {
        'HIGH': QColor(255, 0, 0, 128),       # Red for high VIL
        'MEDIUM': QColor(255, 165, 0, 128),   # Orange for medium VIL
        'LOW': QColor(255, 255, 0, 128),      # Yellow for low VIL
        'MINIMAL': QColor(0, 255, 0, 128)     # Green for minimal VIL
    }

    @staticmethod
    def draw_surveillance_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw weather data in surveillance mode"""
        try:
            # Get weather data
            weather_data = data.get('weather_data', {})
            cells = weather_data.get('cells', [])
            vil_data = weather_data.get('vil_data', [])
            
            # Draw cells
            logger.info("Drawing weather cells")
            for cell in cells:
                # Get cell position and intensity
                x = cell.get('x', 0)
                y = cell.get('y', 0)
                intensity = cell.get('intensity', 0)
                
                # Set cell color based on intensity
                if intensity >= 0.8:
                    color = WeatherRadarModeHandler._intensity_colors['SEVERE']
                elif intensity >= 0.6:
                    color = WeatherRadarModeHandler._intensity_colors['MODERATE']
                elif intensity >= 0.4:
                    color = WeatherRadarModeHandler._intensity_colors['LIGHT']
                else:
                    color = WeatherRadarModeHandler._intensity_colors['VERY_LIGHT']
                
                # Draw cell
                cell_size = 10
                cell_rect = QRectF(x - cell_size/2, y - cell_size/2,
                                 cell_size, cell_size)
                
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(cell_rect)

            # Draw VIL data
            if vil_data:
                logger.info("Drawing VIL legend")
                logger.info(f"VIL legend rendered with {len(WeatherRadarModeHandler._vil_colors)} levels")
                
                for vil in vil_data:
                    # Get VIL position and properties
                    pos = vil.get('position', (0, 0))
                    x, y = pos
                    value = vil.get('value', 0)
                    layer_count = vil.get('layer_count', 0)
                    intensity = vil.get('intensity', 0)
                    show_values = vil.get('show_values', False)
                    
                    # Determine VIL color level
                    if value >= 50:  # High VIL
                        color = WeatherRadarModeHandler._vil_colors['HIGH']
                        color_level = 'HIGH'
                    elif value >= 30:  # Medium VIL
                        color = WeatherRadarModeHandler._vil_colors['MEDIUM']
                        color_level = 'MEDIUM'
                    elif value >= 15:  # Low VIL
                        color = WeatherRadarModeHandler._vil_colors['LOW']
                        color_level = 'LOW'
                    else:  # Minimal VIL
                        color = WeatherRadarModeHandler._vil_colors['MINIMAL']
                        color_level = 'MINIMAL'
                    
                    # Adjust alpha by intensity
                    color.setAlpha(int(128 * intensity))
                    
                    # Draw VIL diamond
                    vil_size = 12
                    screen_x = rect.center().x() + (x / 40) * rect.width() / 3  # 40nm range
                    screen_y = rect.center().y() - (y / 40) * rect.height() / 3
                    
                    logger.info(f"Drawing VIL diamond at ({screen_x}, {screen_y})")
                    logger.info(f"Applied VIL color: {color_level}")
                    
                    # Create diamond path
                    path = QPainterPath()
                    path.moveTo(screen_x, screen_y - vil_size/2)  # Top
                    path.lineTo(screen_x + vil_size/2, screen_y)  # Right
                    path.lineTo(screen_x, screen_y + vil_size/2)  # Bottom
                    path.lineTo(screen_x - vil_size/2, screen_y)  # Left
                    path.closeSubpath()
                    
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.fillPath(path, painter.brush())
                    
                    # Draw values if enabled
                    if show_values:
                        painter.setPen(Qt.GlobalColor.white)
                        logger.info(f"Drawing VIL value: {value}")
                        painter.drawText(
                            QRectF(screen_x - vil_size, screen_y - vil_size*1.5,
                                  vil_size*2, vil_size),
                            Qt.AlignmentFlag.AlignCenter,
                            f"{value:.1f}kg/m²"
                        )
                        logger.info(f"Drawing layer count: {layer_count}")
                        painter.drawText(
                            QRectF(screen_x - vil_size, screen_y + vil_size/2,
                                  vil_size*2, vil_size),
                            Qt.AlignmentFlag.AlignCenter,
                            f"L:{layer_count}"
                        )
                
            # Draw scan line if available
            if 'scan_angle' in weather_data:
                angle = weather_data['scan_angle']
                center = rect.center()
                radius = min(rect.width(), rect.height()) / 3
                
                end_x = center.x() + radius * math.cos(math.radians(angle))
                end_y = center.y() - radius * math.sin(math.radians(angle))
                
                logger.info("Drawing scan line")
                painter.setPen(QPen(Qt.GlobalColor.green, 1, Qt.PenStyle.DashLine))
                painter.drawLine(center, QPointF(end_x, end_y))

            # Draw surveillance overlay
            logger.info("Drawing surveillance overlay")
            logger.info("Drawing intensity scale")
                
        except Exception as e:
            logger.error(f"Error drawing surveillance mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_mapping_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw weather data in mapping mode"""
        try:
            # Get weather data
            weather_data = data.get('weather_data', {})
            terrain_data = weather_data.get('terrain', {})
            precipitation = weather_data.get('precipitation', {})
            
            # Draw terrain base
            if terrain_data:
                WeatherRadarModeHandler._draw_terrain(painter, rect, terrain_data)
            
            # Overlay precipitation
            if precipitation:
                WeatherRadarModeHandler._draw_precipitation(painter, rect, precipitation)
                
        except Exception as e:
            logger.error(f"Error drawing mapping mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def _draw_terrain(painter: QPainter, rect: QRectF, terrain_data: Dict):
        """Draw terrain data"""
        try:
            # Create terrain gradient
            gradient = QLinearGradient(
                rect.topLeft(),
                rect.bottomLeft()
            )
            gradient.setColorAt(0.0, QColor(139, 69, 19))  # Brown for high elevation
            gradient.setColorAt(0.5, QColor(34, 139, 34))  # Green for medium
            gradient.setColorAt(1.0, QColor(0, 191, 255))  # Blue for low/water
            
            # Draw terrain grid
            grid_size = 20
            for x in range(0, int(rect.width()), grid_size):
                for y in range(0, int(rect.height()), grid_size):
                    elevation = terrain_data.get(f"{x},{y}", 0)
                    color = gradient.stops()[int(elevation * (len(gradient.stops())-1))][1]
                    
                    cell_rect = QRectF(
                        rect.left() + x,
                        rect.top() + y,
                        grid_size,
                        grid_size
                    )
                    painter.fillRect(cell_rect, color)
                    
        except Exception as e:
            logger.error(f"Error drawing terrain: {str(e)}")
            raise

    @staticmethod
    def _draw_precipitation(painter: QPainter, rect: QRectF, precip_data: Dict):
        """Draw precipitation overlay"""
        try:
            painter.setOpacity(0.5)  # Make precipitation semi-transparent
            
            for area in precip_data.get('areas', []):
                intensity = area.get('intensity', 0)
                points = area.get('points', [])
                
                if not points:
                    continue
                
                # Set color based on intensity
                if intensity >= 0.8:
                    color = WeatherRadarModeHandler._intensity_colors['SEVERE']
                elif intensity >= 0.6:
                    color = WeatherRadarModeHandler._intensity_colors['MODERATE']
                elif intensity >= 0.4:
                    color = WeatherRadarModeHandler._intensity_colors['LIGHT']
                else:
                    color = WeatherRadarModeHandler._intensity_colors['VERY_LIGHT']
                
                # Draw precipitation area
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Convert points to QPointF list
                qt_points = [QPointF(p[0], p[1]) for p in points]
                painter.drawPolygon(qt_points)
                
            painter.setOpacity(1.0)  # Reset opacity
            
        except Exception as e:
            logger.error(f"Error drawing precipitation: {str(e)}")
            raise

class SARRadarModeHandler:
    """Handle SAR radar mode-specific visualizations"""
    
    @staticmethod
    def draw_stripmap_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw SAR data in stripmap mode"""
        try:
            # Draw continuous strip of terrain imagery
            pass
        except Exception as e:
            logger.error(f"Error drawing stripmap mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_spotlight_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw SAR data in spotlight mode"""
        try:
            # Draw high-resolution image of specific area
            pass
        except Exception as e:
            logger.error(f"Error drawing spotlight mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_scansar_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw SAR data in ScanSAR mode"""
        try:
            # Draw wide-area scan with lower resolution
            pass
        except Exception as e:
            logger.error(f"Error drawing scansar mode: {str(e)}")
            logger.error(traceback.format_exc())

class TFRRadarModeHandler:
    """Handle TFR radar mode-specific visualizations"""
    
    @staticmethod
    def draw_search_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw TFR data in search mode"""
        try:
            # Draw wide terrain scan
            pass
        except Exception as e:
            logger.error(f"Error drawing search mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_track_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw TFR data in track mode"""
        try:
            # Draw focused terrain tracking
            pass
        except Exception as e:
            logger.error(f"Error drawing track mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_ground_mapping_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw TFR data in ground mapping mode"""
        try:
            # Draw detailed terrain map
            pass
        except Exception as e:
            logger.error(f"Error drawing ground mapping mode: {str(e)}")
            logger.error(traceback.format_exc())

class TargetingRadarModeHandler:
    """Handle targeting radar mode-specific visualizations"""
    
    @staticmethod
    def draw_search_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw targeting data in search mode"""
        try:
            # Draw wide area target search
            pass
        except Exception as e:
            logger.error(f"Error drawing search mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_track_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw targeting data in track mode"""
        try:
            # Draw focused target tracking
            pass
        except Exception as e:
            logger.error(f"Error drawing track mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_ground_mapping_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw targeting data in ground mapping mode"""
        try:
            # Draw ground target mapping
            pass
        except Exception as e:
            logger.error(f"Error drawing ground mapping mode: {str(e)}")
            logger.error(traceback.format_exc())

class AEWCRadarModeHandler:
    """Handle AEWC radar mode-specific visualizations"""
    
    @staticmethod
    def draw_search_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw AEWC data in search mode"""
        try:
            # Draw wide area surveillance
            pass
        except Exception as e:
            logger.error(f"Error drawing search mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_track_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw AEWC data in track mode"""
        try:
            # Draw multi-target tracking
            pass
        except Exception as e:
            logger.error(f"Error drawing track mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def draw_ground_mapping_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw AEWC data in ground mapping mode"""
        try:
            # Draw ground surveillance
            pass
        except Exception as e:
            logger.error(f"Error drawing ground mapping mode: {str(e)}")
            logger.error(traceback.format_exc())
