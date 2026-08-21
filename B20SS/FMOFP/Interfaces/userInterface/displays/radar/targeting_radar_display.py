"""
Targeting radar display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt6.QtGui import QPainter, QColor, QPen
from typing import Dict, Tuple
import math
import traceback
from .base_radar_display import BaseRadarDisplay
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class TargetingRadarDisplay(BaseRadarDisplay):
    def __init__(self):
        super().__init__()
        self._symbol_size = 15
        self._identity_colors = {
            'FRIENDLY': QColor(0, 255, 0),    # Green
            'HOSTILE': QColor(255, 0, 0),     # Red
            None: QColor(255, 255, 0),   # Yellow
            'NEUTRAL': QColor(0, 255, 255)    # Cyan
        }
        self._classification_symbols = {
            'FIXED_WING': self._draw_fixed_wing_symbol,
            'ROTARY_WING': self._draw_rotary_wing_symbol,
            'SURFACE': self._draw_surface_symbol,
            None: self._draw_unknown_symbol
        }

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw targeting radar specific elements"""
        try:
            # Calculate radar display area
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3
            
            # Draw base elements
            self.draw_range_rings(painter, center, radius)
            
            # Draw targets
            targets = data.get('targets', [])
            for target in targets:
                self._draw_target(painter, center, radius, target)
                
        except Exception as e:
            logger.error(f"Error drawing targeting radar elements: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _draw_target(self, painter: QPainter, center: QPointF, radius: float, 
                    target: Dict):
        """Draw a single target with its associated data"""
        try:
            # Get target position in screen coordinates
            pos = target.get('position', (0, 0, 0))
            screen_pos = self.world_to_screen(
                (pos[0], pos[1]), 
                center, 
                radius, 
                self.range_scale
            )
            
            # Set color based on identity
            identity = target.get('identity', None)
            color = self._identity_colors.get(identity, self._identity_colors[None])
            painter.setPen(QPen(color, 2))
            
            # Draw classification symbol
            classification = target.get('classification', None)
            symbol_func = self._classification_symbols.get(
                classification, 
                self._classification_symbols[None]
            )
            symbol_func(painter, screen_pos)
            
            # Draw target ID using QRectF
            id_rect = QRectF(
                screen_pos.x() + self._symbol_size,
                screen_pos.y() - self._symbol_size - 15,
                30,  # width
                15   # height
            )
            painter.drawText(
                id_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"#{target.get('id', '?')}"
            )
            
            # Draw velocity vector if available
            vel = target.get('velocity', (0, 0, 0))
            if vel[0] != 0 or vel[1] != 0:
                self._draw_velocity_vector(painter, screen_pos, vel)
                
        except Exception as e:
            logger.error(f"Error drawing target: {str(e)}")
            raise

    def _draw_fixed_wing_symbol(self, painter: QPainter, pos: QPointF):
        """Draw fixed wing aircraft symbol"""
        try:
            size = self._symbol_size
            # Draw aircraft shape (triangle with horizontal line)
            points = [
                QPointF(pos.x(), pos.y() - size/2),  # Top
                QPointF(pos.x() - size/2, pos.y() + size/2),  # Bottom left
                QPointF(pos.x() + size/2, pos.y() + size/2)   # Bottom right
            ]
            painter.drawPolygon(points)
            # Draw wings
            painter.drawLine(
                QPointF(pos.x() - size/2, pos.y()),
                QPointF(pos.x() + size/2, pos.y())
            )
        except Exception as e:
            logger.error(f"Error drawing fixed wing symbol: {str(e)}")
            raise

    def _draw_rotary_wing_symbol(self, painter: QPainter, pos: QPointF):
        """Draw rotary wing aircraft symbol"""
        try:
            size = self._symbol_size
            # Draw circle with rotor blades
            painter.drawEllipse(
                QRectF(pos.x() - size/3, pos.y() - size/3, 2*size/3, 2*size/3)
            )
            # Draw rotor blades
            for angle in [0, 45, 90, 135]:
                rad = math.radians(angle)
                painter.drawLine(
                    QPointF(pos.x() + size/2 * math.cos(rad),
                           pos.y() + size/2 * math.sin(rad)),
                    QPointF(pos.x() - size/2 * math.cos(rad),
                           pos.y() - size/2 * math.sin(rad))
                )
        except Exception as e:
            logger.error(f"Error drawing rotary wing symbol: {str(e)}")
            raise

    def _draw_surface_symbol(self, painter: QPainter, pos: QPointF):
        """Draw surface target symbol"""
        try:
            size = self._symbol_size
            painter.drawRect(
                QRectF(pos.x() - size/2, pos.y() - size/2, size, size)
            )
        except Exception as e:
            logger.error(f"Error drawing surface symbol: {str(e)}")
            raise

    def _draw_unknown_symbol(self, painter: QPainter, pos: QPointF):
        """Draw unknown target symbol"""
        try:
            size = self._symbol_size
            symbol_rect = QRectF(pos.x() - size/2, pos.y() - size/2, size, size)
            painter.drawEllipse(symbol_rect)
            painter.drawText(
                symbol_rect,
                Qt.AlignmentFlag.AlignCenter,
                "?"
            )
        except Exception as e:
            logger.error(f"Error drawing unknown symbol: {str(e)}")
            raise

    def _draw_velocity_vector(self, painter: QPainter, pos: QPointF, 
                            velocity: Tuple[float, float, float]):
        """Draw velocity vector for target"""
        try:
            # Calculate vector magnitude and direction
            speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
            angle = math.atan2(velocity[1], velocity[0])
            
            # Scale vector length (limit to reasonable size)
            vector_length = min(speed * 5, 30)
            
            # Calculate end point
            end_x = pos.x() + vector_length * math.cos(angle)
            end_y = pos.y() + vector_length * math.sin(angle)
            
            # Draw vector
            painter.drawLine(QLineF(pos, QPointF(end_x, end_y)))
            
            # Draw arrowhead
            if speed > 0:
                self._draw_arrowhead(painter, QPointF(end_x, end_y), angle)
                
        except Exception as e:
            logger.error(f"Error drawing velocity vector: {str(e)}")
            raise

    def _draw_arrowhead(self, painter: QPainter, pos: QPointF, angle: float):
        """Draw arrowhead at the end of a vector"""
        try:
            arrow_size = 8
            arrow_angle = math.pi / 6  # 30 degrees
            
            # Calculate arrowhead points
            p1 = QPointF(
                pos.x() - arrow_size * math.cos(angle - arrow_angle),
                pos.y() - arrow_size * math.sin(angle - arrow_angle)
            )
            p2 = QPointF(
                pos.x() - arrow_size * math.cos(angle + arrow_angle),
                pos.y() - arrow_size * math.sin(angle + arrow_angle)
            )
            
            # Draw arrowhead
            points = [pos, p1, p2]
            painter.drawPolygon(points)
            
        except Exception as e:
            logger.error(f"Error drawing arrowhead: {str(e)}")
            raise
