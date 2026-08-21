"""
Terrain Following Radar (TFR) display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from typing import Dict, List
import traceback
from .base_radar_display import BaseRadarDisplay
from .tfr_mode_handler import TFRModeHandler
from Systems.radarManagement.radar_enums import tfr_radarMode
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class TFRRadarDisplay(BaseRadarDisplay):
    """TFR display with vertical profile view"""
    
    def __init__(self):
        super().__init__()
        self.max_range = 10_000  # meters
        self.max_elevation = 5_000  # meters
        self.grid_spacing = 1_000  # meters
        self._terrain_color = QColor(139, 69, 19)  # Brown
        self._warning_zones = [
            (500, QColor(255, 0, 0, 100)),    # Red zone (too close)
            (1000, QColor(255, 255, 0, 100))  # Yellow zone (caution)
        ]
        self._current_mode = tfr_radarMode.STANDBY
        self._warning_color = QColor(255, 255, 0)  # Yellow
        self._critical_color = QColor(255, 0, 0)   # Red
        self._safe_color = QColor(0, 255, 0)       # Green

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw TFR specific elements"""
        try:
            # Get current mode
            mode = data.get('mode', tfr_radarMode.STANDBY)
            self._current_mode = mode
            
            # Draw mode-specific elements
            if mode == tfr_radarMode.SEARCH:
                self._draw_search_mode(painter, rect, data)
            elif mode == tfr_radarMode.TRACK:
                self._draw_track_mode(painter, rect, data)
            elif mode == tfr_radarMode.GROUND_MAPPING:
                self._draw_ground_mapping_mode(painter, rect, data)
            else:
                self._draw_standby_mode(painter, rect)
                
            # Draw common elements
            self._draw_mode_indicator(painter, rect)
            self._draw_status_indicators(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing TFR elements: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _draw_grid(self, painter: QPainter, rect: QRectF):
        """Draw range and elevation grid"""
        try:
            painter.setPen(QPen(self.hud_color, 1, Qt.PenStyle.DotLine))
            
            # Draw horizontal grid lines (elevation)
            for elevation in range(0, self.max_elevation + 1, self.grid_spacing):
                y = self._elevation_to_y(elevation, rect)
                painter.drawLine(
                    QPointF(rect.left(), y),
                    QPointF(rect.right(), y)
                )
                # Draw elevation labels using QRectF
                label_rect = QRectF(
                    rect.left() + 5,  # x
                    y - 15,  # y
                    40,  # width
                    15   # height
                )
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"{elevation}m"
                )
                
            # Draw vertical grid lines (range)
            for distance in range(0, self.max_range + 1, self.grid_spacing):
                x = self._distance_to_x(distance, rect)
                painter.drawLine(
                    QPointF(x, rect.top()),
                    QPointF(x, rect.bottom())
                )
                # Draw range labels using QRectF
                label_rect = QRectF(
                    x - 30,  # x
                    rect.bottom() - 20,  # y
                    60,  # width
                    15   # height
                )
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{distance}m"
                )
                
        except Exception as e:
            logger.error(f"Error drawing grid: {str(e)}")
            raise

    def _draw_terrain_profile(self, painter: QPainter, rect: QRectF, 
                            terrain_data: List[Dict]):
        """Draw terrain elevation profile"""
        try:
            # Create terrain path
            path = QPainterPath()
            
            # Start at bottom left
            path.moveTo(rect.left(), rect.bottom())
            
            # Add terrain points
            for point in terrain_data:
                x = self._distance_to_x(point['distance'], rect)
                y = self._elevation_to_y(point['elevation'], rect)
                path.lineTo(x, y)
            
            # Close path at bottom right
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            
            # Fill terrain
            painter.setBrush(self._terrain_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            
            # Draw terrain outline
            painter.setPen(QPen(self.hud_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
        except Exception as e:
            logger.error(f"Error drawing terrain profile: {str(e)}")
            raise

    def _draw_warning_zones(self, painter: QPainter, rect: QRectF):
        """Draw terrain clearance warning zones"""
        try:
            for clearance, color in self._warning_zones:
                # Create warning zone path
                path = QPainterPath()
                path.moveTo(rect.left(), rect.bottom())
                
                # Add terrain points offset by clearance
                for point in self.radar_data.get('tfr_data', []):
                    x = self._distance_to_x(point['distance'], rect)
                    y = self._elevation_to_y(point['elevation'] + clearance, rect)
                    path.lineTo(x, y)
                
                # Fill warning zone
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)
                
        except Exception as e:
            logger.error(f"Error drawing warning zones: {str(e)}")
            raise

    def _draw_altitude_indicator(self, painter: QPainter, rect: QRectF, 
                               altitude: float):
        """Draw current aircraft altitude indicator"""
        try:
            y = self._elevation_to_y(altitude, rect)
            
            # Draw altitude line
            painter.setPen(QPen(self.hud_color, 2, Qt.PenStyle.DashLine))
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
            
            # Draw altitude label using QRectF
            label_rect = QRectF(
                rect.right() - 80,  # x
                y - 15,  # y
                70,  # width
                15   # height
            )
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"ALT {altitude}m"
            )
            
        except Exception as e:
            logger.error(f"Error drawing altitude indicator: {str(e)}")
            raise

    def _distance_to_x(self, distance: float, rect: QRectF) -> float:
        """Convert distance to x-coordinate"""
        try:
            return rect.left() + (distance / self.max_range) * rect.width()
        except Exception as e:
            logger.error(f"Error converting distance to x: {str(e)}")
            return rect.left()

    def _elevation_to_y(self, elevation: float, rect: QRectF) -> float:
        """Convert elevation to y-coordinate"""
        try:
            # Invert y-axis since Qt's origin is top-left
            return rect.bottom() - (elevation / self.max_elevation) * rect.height()
        except Exception as e:
            logger.error(f"Error converting elevation to y: {str(e)}")
            return rect.bottom()


    def _draw_search_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw search mode with wide terrain scan"""
        try:
            # Use TFR mode handler for terrain visualization
            TFRModeHandler.draw_search_mode(painter, rect, data)
            
            # Add search mode specific overlays
            self._draw_search_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing search mode: {str(e)}")
            raise

    def _draw_track_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw track mode with focused terrain tracking"""
        try:
            # Use TFR mode handler for terrain visualization
            TFRModeHandler.draw_search_mode(painter, rect, data)  # Base terrain view
            
            # Add track mode specific elements
            self._draw_track_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing track mode: {str(e)}")
            raise

    def _draw_ground_mapping_mode(self, painter: QPainter, rect: QRectF, 
                                data: Dict):
        """Draw ground mapping mode"""
        try:
            # Use TFR mode handler for terrain visualization
            TFRModeHandler.draw_search_mode(painter, rect, data)  # Base terrain view
            
            # Add ground mapping specific elements
            self._draw_mapping_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing ground mapping mode: {str(e)}")
            raise

    def _draw_standby_mode(self, painter: QPainter, rect: QRectF):
        """Draw standby mode display"""
        try:
            painter.setPen(self.warning_color)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "TFR STANDBY"
            )
        except Exception as e:
            logger.error(f"Error drawing standby mode: {str(e)}")
            raise

    def _draw_search_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw search mode specific overlay elements"""
        try:
            # Draw scan coverage indicator
            if 'scan_coverage' in data:
                coverage = data['scan_coverage']
                painter.setPen(QPen(self._safe_color, 1, Qt.PenStyle.DashLine))
                
                # Draw coverage arc at top of display
                arc_height = 30
                arc_rect = QRectF(
                    rect.left(),
                    rect.top(),
                    rect.width(),
                    arc_height
                )
                # Convert coverage to degrees (assuming coverage is 0-1)
                span_angle = int(coverage * 180 * 16)  # Qt uses 1/16th degrees
                painter.drawArc(arc_rect, -90 * 16, span_angle)
                
        except Exception as e:
            logger.error(f"Error drawing search overlay: {str(e)}")
            raise

    def _draw_track_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw track mode specific overlay elements"""
        try:
            # Draw tracking box
            if 'track_box' in data:
                box = data['track_box']
                painter.setPen(QPen(self._safe_color, 2))
                painter.drawRect(QRectF(
                    box['x'], box['y'],
                    box['width'], box['height']
                ))
                
            # Draw climb/descent indicators
            if 'vertical_guidance' in data:
                guidance = data['vertical_guidance']
                self._draw_vertical_guidance(painter, rect, guidance)
                
        except Exception as e:
            logger.error(f"Error drawing track overlay: {str(e)}")
            raise

    def _draw_mapping_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw ground mapping mode specific overlay elements"""
        try:
            # Draw mapping grid
            grid_spacing = 50  # pixels
            painter.setPen(QPen(self.hud_color, 1, Qt.PenStyle.DotLine))
            
            # Draw vertical grid lines
            for x in range(int(rect.left()), int(rect.right()), grid_spacing):
                painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
                
            # Draw horizontal grid lines
            for y in range(int(rect.top()), int(rect.bottom()), grid_spacing):
                painter.drawLine(int(rect.left()), y, int(rect.right()), y)
                
        except Exception as e:
            logger.error(f"Error drawing mapping overlay: {str(e)}")
            raise

    def _draw_vertical_guidance(self, painter: QPainter, rect: QRectF, 
                              guidance: Dict):
        """Draw climb/descent guidance indicators"""
        try:
            # Draw vertical rate arrow
            rate = guidance.get('vertical_rate', 0)  # m/s
            if abs(rate) > 0.1:  # Only draw if significant vertical rate
                # Convert rate to screen coordinates
                arrow_length = min(abs(rate) * 10, 50)  # Scale and limit length
                arrow_width = 20
                
                # Draw arrow based on direction
                center_x = rect.right() - 30
                center_y = rect.center().y()
                
                if rate > 0:  # Climbing
                    points = [
                        QPointF(center_x, center_y - arrow_length),
                        QPointF(center_x - arrow_width/2, center_y),
                        QPointF(center_x + arrow_width/2, center_y)
                    ]
                else:  # Descending
                    points = [
                        QPointF(center_x, center_y + arrow_length),
                        QPointF(center_x - arrow_width/2, center_y),
                        QPointF(center_x + arrow_width/2, center_y)
                    ]
                
                # Draw arrow
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._safe_color)
                painter.drawPolygon(points)
                
                # Draw rate text
                painter.setPen(self.hud_color)
                painter.drawText(
                    QRectF(center_x - 40, center_y - 60, 80, 20),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{abs(rate):.1f} m/s"
                )
                
        except Exception as e:
            logger.error(f"Error drawing vertical guidance: {str(e)}")
            raise

    def _draw_mode_indicator(self, painter: QPainter, rect: QRectF):
        """Draw current mode indicator"""
        try:
            mode_text = self._current_mode.name if hasattr(self._current_mode, 'name') else None
            painter.setPen(self.hud_color)
            painter.drawText(
                QRectF(rect.left(), rect.top(), rect.width(), 30),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                f"Mode: {mode_text}"
            )
        except Exception as e:
            logger.error(f"Error drawing mode indicator: {str(e)}")
            raise

    def _draw_status_indicators(self, painter: QPainter, rect: QRectF, 
                              data: Dict):
        """Draw system status indicators"""
        try:
            # Draw terrain clearance status
            clearance = data.get('terrain_clearance', 0)
            status_color = (
                self._critical_color if clearance < 150 else
                self._warning_color if clearance < 300 else
                self._safe_color
            )
            
            painter.setPen(status_color)
            painter.drawText(
                QRectF(rect.left(), rect.bottom() - 30, rect.width(), 30),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                f"Clearance: {clearance:.0f}m"
            )
            
            # Draw system health indicator
            health = data.get('system_health', None)
            health_color = (
                self._safe_color if health == 'NORMAL' else
                self._warning_color if health == 'DEGRADED' else
                self._critical_color
            )
            
            painter.setPen(health_color)
            painter.drawText(
                QRectF(rect.left(), rect.top(), rect.width(), 30),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                f"Health: {health}"
            )
            
        except Exception as e:
            logger.error(f"Error drawing status indicators: {str(e)}")
            raise
