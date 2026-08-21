"""
Synthetic Aperture Radar (SAR) display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QByteArray
from PyQt6.QtGui import (QPainter, QColor, QPen, QImage, QTransform)
from typing import Dict, List, Optional
import traceback
from .base_radar_display import BaseRadarDisplay
from Systems.radarManagement.radar_enums import sar_radarMode
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class SARRadarDisplay(BaseRadarDisplay):
    """SAR display with image rendering capabilities"""
    
    def __init__(self):
        super().__init__()
        self._current_mode = sar_radarMode.STANDBY
        self._current_image: Optional[QImage] = None
        self._image_transform = QTransform()
        self._grid_color = QColor(0, 255, 0, 80)  # Semi-transparent green
        self._corner_color = QColor(255, 255, 0)  # Yellow
        self._resolution_text_color = QColor(0, 255, 0)  # Green

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw SAR specific elements"""
        try:
            # Get current mode
            mode = data.get('mode', sar_radarMode.STANDBY)
            self._current_mode = mode
            
            # Update SAR image if new data available
            image_data = data.get('image_data')
            if image_data:
                self._update_image(image_data)
            
            # Draw mode-specific elements
            if mode == sar_radarMode.STRIPMAP:
                self._draw_stripmap_mode(painter, rect, data)
            elif mode == sar_radarMode.SPOTLIGHT:
                self._draw_spotlight_mode(painter, rect, data)
            elif mode == sar_radarMode.SCANSAR:
                self._draw_scansar_mode(painter, rect, data)
            else:
                self._draw_standby_mode(painter, rect)
                
            # Draw common elements
            self._draw_mode_indicator(painter, rect)
            self._draw_resolution_indicator(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing SAR elements: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _update_image(self, image_data: bytes):
        """Update the SAR image from raw data"""
        try:
            # Convert bytes to QImage
            byte_array = QByteArray(image_data)
            new_image = QImage.fromData(byte_array)
            
            if new_image.isNull():
                logger.error("Failed to create valid image from data")
                return
                
            self._current_image = new_image
            
        except Exception as e:
            logger.error(f"Error updating SAR image: {str(e)}")
            self._current_image = None

    def _draw_stripmap_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw stripmap mode with continuous terrain imagery"""
        try:
            if self._current_image:
                # Calculate scaling to fit rect while maintaining aspect ratio
                self._draw_sar_image(painter, rect)
                
            # Draw stripmap specific overlays
            self._draw_stripmap_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing stripmap mode: {str(e)}")
            raise

    def _draw_spotlight_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw spotlight mode with high-resolution area focus"""
        try:
            if self._current_image:
                # Draw high-resolution image
                self._draw_sar_image(painter, rect)
                
            # Draw spotlight specific overlays
            self._draw_spotlight_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing spotlight mode: {str(e)}")
            raise

    def _draw_scansar_mode(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw ScanSAR mode with wide area coverage"""
        try:
            if self._current_image:
                # Draw wide-area scan image
                self._draw_sar_image(painter, rect)
                
            # Draw ScanSAR specific overlays
            self._draw_scansar_overlay(painter, rect, data)
            
        except Exception as e:
            logger.error(f"Error drawing scansar mode: {str(e)}")
            raise

    def _draw_sar_image(self, painter: QPainter, rect: QRectF):
        """Draw the SAR image with proper scaling"""
        try:
            if not self._current_image:
                return
                
            # Calculate scaling to fit rect while maintaining aspect ratio
            image_aspect = self._current_image.width() / self._current_image.height()
            rect_aspect = rect.width() / rect.height()
            
            if image_aspect > rect_aspect:
                # Image is wider than rect
                scale_x = rect.width() / self._current_image.width()
                scale_y = scale_x
            else:
                # Image is taller than rect
                scale_y = rect.height() / self._current_image.height()
                scale_x = scale_y
                
            # Update transform
            self._image_transform = QTransform()
            self._image_transform.translate(rect.center().x(), rect.center().y())
            self._image_transform.scale(scale_x, scale_y)
            self._image_transform.translate(-self._current_image.width()/2, 
                                         -self._current_image.height()/2)
            
            # Draw image
            painter.setTransform(self._image_transform)
            painter.drawImage(0, 0, self._current_image)
            painter.resetTransform()
            
        except Exception as e:
            logger.error(f"Error drawing SAR image: {str(e)}")
            raise

    def _draw_stripmap_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw stripmap mode specific overlay elements"""
        try:
            # Draw scan progress indicator
            if 'scan_progress' in data:
                progress = data['scan_progress']  # 0 to 1
                progress_height = 10
                progress_rect = QRectF(
                    rect.left(),
                    rect.bottom() - progress_height,
                    rect.width() * progress,
                    progress_height
                )
                painter.fillRect(progress_rect, self._grid_color)
                
            # Draw corner points if available
            corner_points = data.get('corner_points', [])
            if corner_points:
                self._draw_corner_points(painter, rect, corner_points)
                
        except Exception as e:
            logger.error(f"Error drawing stripmap overlay: {str(e)}")
            raise

    def _draw_spotlight_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw spotlight mode specific overlay elements"""
        try:
            # Draw focus area box
            if 'focus_area' in data:
                focus = data['focus_area']
                painter.setPen(QPen(self._corner_color, 2))
                painter.drawRect(QRectF(
                    focus['x'], focus['y'],
                    focus['width'], focus['height']
                ))
                
            # Draw resolution indicator
            resolution = data.get('resolution', 0)
            if resolution > 0:
                painter.setPen(self._resolution_text_color)
                painter.drawText(
                    QRectF(rect.left(), rect.bottom() - 30, rect.width(), 30),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                    f"Resolution: {resolution:.1f}m"
                )
                
        except Exception as e:
            logger.error(f"Error drawing spotlight overlay: {str(e)}")
            raise

    def _draw_scansar_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw ScanSAR mode specific overlay elements"""
        try:
            # Draw scan sectors
            if 'scan_sectors' in data:
                sectors = data['scan_sectors']
                painter.setPen(QPen(self._grid_color, 1, Qt.PenStyle.DotLine))
                
                for sector in sectors:
                    # Draw sector boundaries
                    start_angle = sector['start_angle']
                    span_angle = sector['span_angle']
                    
                    # Convert angles to Qt's 1/16th degree system
                    start_angle_16 = int(start_angle * 16)
                    span_angle_16 = int(span_angle * 16)
                    
                    painter.drawArc(rect, start_angle_16, span_angle_16)
                    
        except Exception as e:
            logger.error(f"Error drawing scansar overlay: {str(e)}")
            raise

    def _draw_corner_points(self, painter: QPainter, rect: QRectF, 
                          corner_points: List[tuple]):
        """Draw corner point markers"""
        try:
            painter.setPen(QPen(self._corner_color, 2))
            
            # Draw corner points
            for point in corner_points:
                screen_pos = self.world_to_screen(point, rect.center(), 
                                                min(rect.width(), rect.height())/2,
                                                self.range_scale)
                
                # Draw corner marker (cross)
                size = 10
                painter.drawLine(
                    QPointF(screen_pos.x() - size, screen_pos.y()),
                    QPointF(screen_pos.x() + size, screen_pos.y())
                )
                painter.drawLine(
                    QPointF(screen_pos.x(), screen_pos.y() - size),
                    QPointF(screen_pos.x(), screen_pos.y() + size)
                )
                
            # Draw corner point polygon
            if len(corner_points) > 2:
                points = [
                    self.world_to_screen(p, rect.center(),
                                       min(rect.width(), rect.height())/2,
                                       self.range_scale)
                    for p in corner_points
                ]
                painter.drawPolygon(points)
                
        except Exception as e:
            logger.error(f"Error drawing corner points: {str(e)}")
            raise

    def _draw_standby_mode(self, painter: QPainter, rect: QRectF):
        """Draw standby mode display"""
        try:
            painter.setPen(self.warning_color)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "SAR STANDBY"
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

    def _draw_resolution_indicator(self, painter: QPainter, rect: QRectF, 
                                 data: Dict):
        """Draw resolution scale indicator"""
        try:
            resolution = data.get('resolution', 0)
            if resolution > 0:
                # Draw resolution text
                painter.setPen(self._resolution_text_color)
                painter.drawText(
                    rect.adjusted(10, 10, -10, -10),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                    f"Resolution: {resolution:.1f}m"
                )
                
                # Draw scale bar
                bar_width = 100  # pixels
                bar_height = 5
                bar_rect = QRectF(
                    rect.right() - bar_width - 10,
                    rect.top() + 30,
                    bar_width,
                    bar_height
                )
                painter.fillRect(bar_rect, self._resolution_text_color)
                
                # Draw scale label
                scale_distance = bar_width * resolution  # meters
                painter.drawText(
                    QRectF(bar_rect.left(), bar_rect.bottom() + 5,
                          bar_rect.width(), 20),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{int(scale_distance)}m"
                )
                
        except Exception as e:
            logger.error(f"Error drawing resolution indicator: {str(e)}")
            raise
