"""
Terrain Following Radar (TFR) mode-specific visualization handler
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen,
                        QPainterPath)
from typing import Dict, List
import traceback
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class TFRModeHandler:
    """Handle TFR mode-specific visualizations"""
    
    # Colors for different elements
    _colors = {
        'terrain': QColor(139, 69, 19),  # Brown
        'warning': QColor(255, 0, 0, 128),  # Semi-transparent red
        'caution': QColor(255, 255, 0, 128),  # Semi-transparent yellow
        'clearance': QColor(0, 255, 0),  # Green
        'grid': QColor(0, 255, 0, 64),  # Faded green
        'current_alt': QColor(0, 255, 255)  # Cyan
    }
    
    # Warning zones (in meters)
    _warning_zones = {
        'critical': 150,  # Meters above terrain
        'warning': 300,
        'caution': 500
    }

    @staticmethod
    def draw_search_mode(painter: QPainter, rect: QRectF, data: Dict):
        """Draw TFR data in search mode - wide area terrain scan"""
        try:
            # Draw base elements
            TFRModeHandler._draw_grid(painter, rect)
            TFRModeHandler._draw_warning_zones(painter, rect)
            
            # Draw terrain profile if data available
            terrain_data = data.get('tfr_data', [])
            if terrain_data:
                TFRModeHandler._draw_terrain_profile(painter, rect, terrain_data)
            
            # Draw current altitude if available
            if 'current_altitude' in data:
                TFRModeHandler._draw_current_altitude(
                    painter, rect, data['current_altitude']
                )
                
            # Draw clearance line if available
            if 'clearance_altitude' in data:
                TFRModeHandler._draw_clearance_line(
                    painter, rect, data['clearance_altitude']
                )
                
        except Exception as e:
            logger.error(f"Error drawing TFR search mode: {str(e)}")
            logger.error(traceback.format_exc())

    @staticmethod
    def _draw_grid(painter: QPainter, rect: QRectF):
        """Draw elevation/distance grid"""
        try:
            painter.setPen(QPen(TFRModeHandler._colors['grid'], 1, 
                              Qt.PenStyle.DotLine))
            
            # Draw horizontal grid lines (elevation)
            grid_spacing = 100  # meters
            for elevation in range(0, 2001, grid_spacing):  # Up to 2000m
                y = TFRModeHandler._elevation_to_y(elevation, rect)
                painter.drawLine(
                    QPointF(rect.left(), y),
                    QPointF(rect.right(), y)
                )
                # Draw elevation labels
                painter.drawText(
                    QPointF(rect.left() + 5, y - 5),
                    f"{elevation}m"
                )
            
            # Draw vertical grid lines (distance)
            for distance in range(0, 10001, 1000):  # Every 1km up to 10km
                x = TFRModeHandler._distance_to_x(distance, rect)
                painter.drawLine(
                    QPointF(x, rect.top()),
                    QPointF(x, rect.bottom())
                )
                # Draw distance labels
                painter.drawText(
                    QPointF(x - 20, rect.bottom() - 5),
                    f"{distance/1000:.1f}km"
                )
                
        except Exception as e:
            logger.error(f"Error drawing TFR grid: {str(e)}")
            raise

    @staticmethod
    def _draw_warning_zones(painter: QPainter, rect: QRectF):
        """Draw terrain clearance warning zones"""
        try:
            # Draw warning zones from bottom up
            zones = [
                (TFRModeHandler._warning_zones['critical'],
                 TFRModeHandler._colors['warning']),
                (TFRModeHandler._warning_zones['warning'],
                 TFRModeHandler._colors['caution']),
                (TFRModeHandler._warning_zones['caution'],
                 QColor(255, 255, 0, 32))  # Very faint yellow
            ]
            
            for height, color in zones:
                y = TFRModeHandler._elevation_to_y(height, rect)
                zone_rect = QRectF(
                    rect.left(),
                    rect.bottom(),
                    rect.width(),
                    rect.bottom() - y
                )
                painter.fillRect(zone_rect, color)
                
        except Exception as e:
            logger.error(f"Error drawing warning zones: {str(e)}")
            raise

    @staticmethod
    def _draw_terrain_profile(painter: QPainter, rect: QRectF, 
                            terrain_data: List[Dict]):
        """Draw terrain elevation profile"""
        try:
            # Create terrain path
            path = QPainterPath()
            
            # Start at bottom left
            path.moveTo(rect.left(), rect.bottom())
            
            # Add terrain points
            for point in terrain_data:
                x = TFRModeHandler._distance_to_x(point['distance'], rect)
                y = TFRModeHandler._elevation_to_y(point['elevation'], rect)
                path.lineTo(x, y)
            
            # Close path at bottom right
            path.lineTo(rect.right(), rect.bottom())
            
            # Fill terrain
            painter.setBrush(TFRModeHandler._colors['terrain'])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            
            # Draw terrain outline
            painter.setPen(QPen(TFRModeHandler._colors['terrain'].darker(), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
        except Exception as e:
            logger.error(f"Error drawing terrain profile: {str(e)}")
            raise

    @staticmethod
    def _draw_current_altitude(painter: QPainter, rect: QRectF, altitude: float):
        """Draw current aircraft altitude indicator"""
        try:
            y = TFRModeHandler._elevation_to_y(altitude, rect)
            
            # Draw altitude line
            painter.setPen(QPen(TFRModeHandler._colors['current_alt'], 2, 
                              Qt.PenStyle.DashLine))
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
            
            # Draw altitude label
            painter.drawText(
                QPointF(rect.right() - 60, y - 5),
                f"ALT {altitude:.0f}m"
            )
            
        except Exception as e:
            logger.error(f"Error drawing current altitude: {str(e)}")
            raise

    @staticmethod
    def _draw_clearance_line(painter: QPainter, rect: QRectF, 
                            clearance: float):
        """Draw minimum clearance altitude line"""
        try:
            y = TFRModeHandler._elevation_to_y(clearance, rect)
            
            # Draw clearance line
            painter.setPen(QPen(TFRModeHandler._colors['clearance'], 2, 
                              Qt.PenStyle.DotLine))
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
            
            # Draw clearance label
            painter.drawText(
                QPointF(rect.left() + 5, y - 5),
                f"MIN {clearance:.0f}m"
            )
            
        except Exception as e:
            logger.error(f"Error drawing clearance line: {str(e)}")
            raise

    @staticmethod
    def _elevation_to_y(elevation: float, rect: QRectF) -> float:
        """Convert elevation to y-coordinate"""
        try:
            max_elevation = 2000  # meters
            # Invert y-axis since Qt's origin is top-left
            return rect.bottom() - (elevation / max_elevation) * rect.height()
        except Exception as e:
            logger.error(f"Error converting elevation to y: {str(e)}")
            return rect.bottom()

    @staticmethod
    def _distance_to_x(distance: float, rect: QRectF) -> float:
        """Convert distance to x-coordinate"""
        try:
            max_distance = 10000  # meters
            return rect.left() + (distance / max_distance) * rect.width()
        except Exception as e:
            logger.error(f"Error converting distance to x: {str(e)}")
            return rect.left()
