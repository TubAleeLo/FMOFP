"""
Airborne Early Warning and Control (AEWC) radar display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from typing import Dict, List
import math
import traceback
from .targeting_radar_display import TargetingRadarDisplay
from Systems.radarManagement.radar_enums import aewc_radarMode
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class AEWCRadarDisplay(TargetingRadarDisplay):
    """AEWC display with extended range and stealth tracking"""
    
    def __init__(self):
        super().__init__()
        # Extended range for AEWC
        self.range_scale = 200  # nautical miles
        
        # Additional colors for AEWC-specific features
        self._stealth_color = QColor(128, 0, 128)  # Purple for stealth targets
        self._track_history_color = QColor(0, 255, 0, 50)  # Faded green
        self._sector_scan_color = QColor(0, 255, 0, 30)  # Very faded green
        
        # Track history settings
        self._max_history_points = 10
        self._track_histories: Dict[int, List[tuple]] = {}
        
        # Current mode
        self._current_mode = aewc_radarMode.STANDBY

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw AEWC specific elements"""
        try:
            # Get current mode
            mode = data.get('mode', aewc_radarMode.STANDBY)
            self._current_mode = mode
            
            # Draw base elements
            self._draw_range_rings(painter, rect)
            
            # Draw mode-specific elements
            if mode == aewc_radarMode.SEARCH:
                self._draw_search_mode(painter, rect, data)
            elif mode == aewc_radarMode.TRACK:
                self._draw_track_mode(painter, rect, data)
            elif mode == aewc_radarMode.GROUND_MAPPING:
                self._draw_ground_mapping_mode(painter, rect, data)
            else:
                self._draw_standby_mode(painter, rect)
                
            # Draw common elements
            self._draw_mode_indicator(painter, rect)
            self._draw_status_indicators(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing AEWC elements: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _draw_range_rings(self, painter: QPainter, rect: QRectF):
        """Draw extended range rings"""
        try:
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3
            
            # Draw main range rings
            painter.setPen(QPen(self.hud_color, 1, Qt.PenStyle.DotLine))
            
            # Draw range rings at different intervals
            ranges = [radius/4, radius/2, radius*3/4, radius]
            for r in ranges:
                ring_rect = QRectF(
                    center.x() - r,
                    center.y() - r,
                    r * 2,
                    r * 2
                )
                painter.drawEllipse(ring_rect)
                
                # Draw range labels using QRectF - positioned at top-right to avoid overlap with cardinal directions
                range_nm = int(self.range_scale * (r/radius))
                
                # Position at 45 degrees (top-right) to avoid overlap with N cardinal direction
                label_angle = math.radians(45)
                label_x = center.x() + r * math.cos(label_angle) - 20
                label_y = center.y() - r * math.sin(label_angle) - 15
                
                label_rect = QRectF(
                    label_x,  # x - positioned at 45 degrees
                    label_y,  # y - positioned at 45 degrees
                    40,  # width
                    15   # height
                )
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{range_nm}nm"
                )
                
            # Draw cardinal points using QRectF
            points = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
            for label, angle in points:
                rad_angle = math.radians(angle - 90)
                point_x = center.x() + radius * 1.1 * math.cos(rad_angle)
                point_y = center.y() + radius * 1.1 * math.sin(rad_angle)
                label_rect = QRectF(
                    point_x - 10,  # x
                    point_y - 10,  # y
                    20,  # width
                    20   # height
                )
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
                
        except Exception as e:
            logger.error(f"Error drawing range rings: {str(e)}")
            raise

    def _draw_search_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw search mode with wide area surveillance"""
        try:
            # Draw track histories first
            self._update_track_histories(data.get('targets', []))
            self._draw_track_histories(painter, rect)
            
            # Draw current tracks
            for target in data.get('targets', []):
                self._draw_target(painter, rect, target)
                
            # Draw sector scan indicator
            if 'scan_sector' in data:
                self._draw_sector_scan(painter, rect, data['scan_sector'])
                
        except Exception as e:
            logger.error(f"Error drawing search mode: {str(e)}")
            raise

    def _draw_track_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw track mode with focused target tracking"""
        try:
            # Draw track histories
            self._update_track_histories(data.get('targets', []))
            self._draw_track_histories(painter, rect)
            
            # Draw current tracks
            for target in data.get('targets', []):
                self._draw_target(painter, rect, target)
                
            # Draw track focus indicators
            if 'priority_tracks' in data:
                self._draw_priority_tracks(painter, rect, data['priority_tracks'])
                
        except Exception as e:
            logger.error(f"Error drawing track mode: {str(e)}")
            raise

    def _draw_target(self, painter: QPainter, rect: QRectF, target: Dict):
        """Draw AEWC-specific target representation"""
        try:
            # Get target position in screen coordinates
            pos = target.get('position', (0, 0, 0))
            screen_pos = self.world_to_screen(
                (pos[0], pos[1]), 
                rect.center(), 
                min(rect.width(), rect.height())/3,
                self.range_scale
            )
            
            # Set color based on stealth status
            is_stealth = target.get('is_stealth', False)
            if is_stealth:
                painter.setPen(QPen(self._stealth_color, 2))
                self._draw_stealth_symbol(painter, screen_pos)
            else:
                # Use standard target drawing for non-stealth targets
                super()._draw_target(painter, rect, target)
                
        except Exception as e:
            logger.error(f"Error drawing target: {str(e)}")
            raise

    def _draw_stealth_symbol(self, painter: QPainter, pos: QPointF):
        """Draw special symbol for stealth targets"""
        try:
            size = self._symbol_size
            
            # Draw stealth aircraft shape (diamond with internal cross)
            points = [
                QPointF(pos.x(), pos.y() - size/2),  # Top
                QPointF(pos.x() + size/2, pos.y()),  # Right
                QPointF(pos.x(), pos.y() + size/2),  # Bottom
                QPointF(pos.x() - size/2, pos.y())   # Left
            ]
            painter.drawPolygon(points)
            
            # Draw internal cross
            painter.drawLine(
                QPointF(pos.x() - size/4, pos.y()),
                QPointF(pos.x() + size/4, pos.y())
            )
            painter.drawLine(
                QPointF(pos.x(), pos.y() - size/4),
                QPointF(pos.x(), pos.y() + size/4)
            )
            
        except Exception as e:
            logger.error(f"Error drawing stealth symbol: {str(e)}")
            raise

    def _update_track_histories(self, targets: List[Dict]):
        """Update track history for each target"""
        try:
            for target in targets:
                track_id = target.get('id')
                if track_id is None:
                    continue
                    
                position = target.get('position')
                if position is None:
                    continue
                    
                if track_id not in self._track_histories:
                    self._track_histories[track_id] = []
                    
                history = self._track_histories[track_id]
                history.append(position)
                
                # Limit history length
                if len(history) > self._max_history_points:
                    history.pop(0)
                    
        except Exception as e:
            logger.error(f"Error updating track histories: {str(e)}")
            raise

    def _draw_track_histories(self, painter: QPainter, rect: QRectF):
        """Draw historical tracks for each target"""
        try:
            painter.setPen(QPen(self._track_history_color, 1))
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3
            
            for track_id, history in self._track_histories.items():
                if len(history) < 2:
                    continue
                    
                # Convert positions to screen coordinates
                points = [
                    self.world_to_screen(
                        (pos[0], pos[1]),
                        center,
                        radius,
                        self.range_scale
                    )
                    for pos in history
                ]
                
                # Draw track line
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])
                    
        except Exception as e:
            logger.error(f"Error drawing track histories: {str(e)}")
            raise

    def _draw_sector_scan(self, painter: QPainter, rect: QRectF, sector: Dict):
        """Draw current radar scan sector"""
        try:
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3
            
            start_angle = sector.get('start_angle', 0)
            span_angle = sector.get('span_angle', 360)
            
            # Draw scan arc
            painter.setPen(QPen(self.hud_color, 1, Qt.PenStyle.DashLine))
            
            # Create sector path
            path = QPainterPath()
            path.moveTo(center)
            path.arcTo(
                QRectF(
                    center.x() - radius,
                    center.y() - radius,
                    radius * 2,
                    radius * 2
                ),
                start_angle,
                span_angle
            )
            path.lineTo(center)
            
            # Fill sector
            painter.setBrush(self._sector_scan_color)
            painter.drawPath(path)
            
            # Draw angle labels
            painter.drawText(
                QRectF(center.x() - 50, center.y() - radius - 20, 100, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"{start_angle}° - {start_angle + span_angle}°"
            )
            
        except Exception as e:
            logger.error(f"Error drawing scan sector: {str(e)}")
            raise

    def _draw_priority_tracks(self, painter: QPainter, rect: QRectF, 
                            priority_tracks: List[int]):
        """Draw indicators for priority tracks"""
        try:
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3
            
            # Draw highlight for priority tracks
            painter.setPen(QPen(self._warning_color, 2, Qt.PenStyle.DashLine))
            
            for track_id in priority_tracks:
                # Find track in current targets
                for target in self.radar_data.get('targets', []):
                    if target.get('id') == track_id:
                        pos = target.get('position')
                        if pos:
                            screen_pos = self.world_to_screen(
                                (pos[0], pos[1]),
                                center,
                                radius,
                                self.range_scale
                            )
                            
                            # Draw highlight circle
                            highlight_radius = self._symbol_size * 1.5
                            painter.drawEllipse(
                                screen_pos,
                                highlight_radius,
                                highlight_radius
                            )
                            break
                            
        except Exception as e:
            logger.error(f"Error drawing priority tracks: {str(e)}")
            raise

    def _draw_standby_mode(self, painter: QPainter, rect: QRectF):
        """Draw standby mode display"""
        try:
            painter.setPen(self.warning_color)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "AEWC RADAR STANDBY"
            )
        except Exception as e:
            logger.error(f"Error drawing standby mode: {str(e)}")
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
            # Draw track count
            track_count = len(data.get('targets', []))
            painter.setPen(self.hud_color)
            painter.drawText(
                QRectF(rect.left(), rect.bottom() - 30, rect.width(), 30),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                f"Tracks: {track_count}"
            )
            
            # Draw stealth track count
            stealth_count = sum(
                1 for t in data.get('targets', [])
                if t.get('is_stealth', False)
            )
            if stealth_count > 0:
                painter.setPen(self._stealth_color)
                painter.drawText(
                    QRectF(rect.left(), rect.bottom() - 60, rect.width(), 30),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    f"Stealth: {stealth_count}"
                )
            
        except Exception as e:
            logger.error(f"Error drawing status indicators: {str(e)}")
            raise
