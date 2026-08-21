"""
Futuristic Multi-Function Display

Advanced MFD implementation with futuristic visual elements
and enhanced tactical displays.

NOTE (production readiness re-analysis, August 2026): confirmed dead
code, not a bug -- mfd_display_factory.py doesn't even import this class
(its create_display() only branches on "holographic" vs. default
"standard", same as pfd_display_factory.py's sibling gap for
FuturisticPFD). theme_manager.py's get_available_display_types()
explicitly returns only ["standard", "holographic"], and other files
(mfd.py, settings_panel.py) carry explicit "removed/changed from
futuristic" comments -- this reads as an intentional product decision to
retire the futuristic theme, not an unfinished feature. See PLANNING.md's
Implemented-but-Unwired Subsystems table for the full writeup. Left in
place rather than deleted, since removing code isn't part of this pass.
"""

import time
import math
import random
import traceback
from typing import Dict, Any, List, Tuple, Optional
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QRadialGradient, QPainterPath
from .mfd import MultiFunctionDisplay, RadarData, RadarType
from .visual.enhanced_effects import get_enhanced_visual_effects
from .visual.theme_manager import get_theme_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class FuturisticMFD(MultiFunctionDisplay):
    """Enhanced futuristic multi-function display with advanced visuals"""

    def __init__(self, parent=None):
        """Initialize futuristic multi-function display"""
        super().__init__(parent)

        # Set theme to futuristic
        self._theme_manager = get_theme_manager()
        self._theme_manager.set_theme("futuristic")

        # Get enhanced visual effects
        self._visual_effects = get_enhanced_visual_effects()

        # Animation properties
        self._animation_time = 0
        self._scan_angle = 0
        self._pulse_factor = 0
        self._glow_intensity = 0.7
        self._last_animation_update = time.time()

        # Tactical data
        self._tactical_targets = self._generate_sample_targets()
        self._terrain_data = self._generate_sample_terrain_data()

        # Connect to visual node tree
        self._connect_to_visual_nodes()

        logger.info("Futuristic MFD initialized")

    def _connect_to_visual_nodes(self):
        """Connect to visual node tree for real-time updates"""
        try:
            from .display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()

            # Connect to radar visual nodes
            for radar_type in ["weather_radar", "targeting_radar", "tfr_radar", "sar_radar", "aewc_radar"]:
                radar_node = tree_manager.get_radar_node(radar_type)
                if radar_node:
                    visual_node = radar_node.get_child("visual")
                    if visual_node:
                        visual_node.add_subscriber(self._handle_visual_update)
                        logger.info(f"Connected to visual node for {radar_type}")
        except Exception as e:
            logger.error(f"Error connecting to visual nodes: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_visual_update(self, node_name, value):
        """Handle visual node updates"""
        try:
            # Update display based on visual node changes
            self.update()
            logger.info(f"Updated display based on visual node: {node_name}")
        except Exception as e:
            logger.error(f"Error handling visual update: {str(e)}")
            logger.error(traceback.format_exc())

    def _update_animations(self):
        """Update animation values"""
        current_time = time.time()
        elapsed = current_time - self._last_animation_update
        self._last_animation_update = current_time

        # Update animation time
        self._animation_time += elapsed

        # Update scan angle
        self._scan_angle = (self._scan_angle + elapsed * 45) % 360

        # Update pulse factor (0.0 to 1.0)
        self._pulse_factor = (math.sin(self._animation_time * 2) + 1) / 2

        # Update glow intensity
        self._glow_intensity = 0.5 + 0.3 * self._pulse_factor

    def update_scan_angle(self):
        """Update the radar scan angle"""
        self._scan_angle = (self._scan_angle + 2) % 360
        self.update()

    def paint_display(self, painter: QPainter):
        """Paint the futuristic MFD display"""
        # Clear the entire rect with a completely opaque black to prevent overlapping displays
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(0, 0, 0, 255))
        painter.restore()

        # Update animations
        self._update_animations()

        # Get colors from theme
        background_color = QColor(self._theme_manager.get_color("background"))
        text_color = QColor(self._theme_manager.get_color("text"))
        accent_color = QColor(self._theme_manager.get_color("accent"))
        highlight_color = QColor(self._theme_manager.get_color("highlight"))

        # Create enhanced colors with glow
        glow_color = QColor(accent_color)
        glow_color.setAlphaF(self._glow_intensity * 0.7)

        highlight_glow = QColor(highlight_color)
        highlight_glow.setAlphaF(self._glow_intensity * 0.9)

        # Draw background with enhanced effects
        self._visual_effects.draw_layered_background(
            painter,
            self.rect(),
            background_color,
            glow_color,
            self._pulse_factor
        )

        # Calculate content area dimensions
        title_height = float(self.height()) / 12
        menu_width = float(self.width()) / 5
        margin = 20.0

        content_rect = QRectF(
            menu_width + margin,
            title_height + margin,
            float(self.width()) - menu_width - margin * 2,
            float(self.height()) - title_height - margin * 2
        )

        # Draw page content based on current page
        if self.current_page.value.lower() == "radar":
            self.draw_radar_page(painter, content_rect)
        elif self.current_page.value.lower() == "nav":
            self.draw_nav_page(painter, content_rect)
        elif self.current_page.value.lower() == "systems":
            self.draw_systems_page(painter, content_rect)
        elif self.current_page.value.lower() == "weapons":
            self.draw_weapons_page(painter, content_rect)
        elif self.current_page.value.lower() == "comms":
            self.draw_comms_page(painter, content_rect)
        elif self.current_page.value.lower() == "mission":
            self.draw_mission_page(painter, content_rect)
        elif self.current_page.value.lower() == "settings":
            self.draw_settings_page(painter, content_rect)

        # Draw title with enhanced effects
        title_rect = QRect(0, 0, self.width(), 40)
        self._visual_effects.draw_enhanced_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"MFD - {self.current_page.value}",
            highlight_color,
            glow_color,
            self._pulse_factor
        )

        # Draw menu with enhanced effects
        self.draw_menu(painter)

        # Draw tactical data overlay
        self._draw_tactical_overlay(painter)

        # Draw scan line animation
        if self.current_page.value.lower() == "radar" and hasattr(self, 'radar_data') and hasattr(self.radar_data, 'mode'):
            self.draw_scan_line(painter)

    def draw_radar_page(self, painter: QPainter, rect: QRectF):
        """Draw the radar page with futuristic enhancements"""
        # Call parent method first
        super().draw_radar_page(painter, rect)

        # Add futuristic enhancements
        if hasattr(self, 'radar_data') and hasattr(self.radar_data, 'mode'):
            # Draw enhanced radar frame
            self._draw_enhanced_radar_frame(painter)

            # Draw data fusion overlay
            self._draw_data_fusion_overlay(painter)

    def _draw_enhanced_radar_frame(self, painter: QPainter):
        """Draw enhanced radar frame with futuristic elements"""
        # Get colors
        accent_color = QColor(self._theme_manager.get_color("accent"))
        highlight_color = QColor(self._theme_manager.get_color("highlight"))

        # Create glow colors
        glow_color = QColor(accent_color)
        glow_color.setAlphaF(self._glow_intensity * 0.7)

        # Get radar display area
        radar_rect = self._get_radar_display_rect()

        # Draw hexagonal grid - extract center and radius from rect
        center = QPointF(radar_rect.center())
        radius = min(radar_rect.width(), radar_rect.height()) / 2

        self._visual_effects.draw_hexagonal_grid(
            painter,
            center,
            radius,
            accent_color,
            4  # Use integer for rings parameter
        )

        # Draw angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            radar_rect,
            color=highlight_color,
            glow=True
        )

    def _draw_data_fusion_overlay(self, painter: QPainter):
        """Draw data fusion overlay with tactical information"""
        # Only draw if in surveillance or mapping mode
        if not hasattr(self, 'radar_data') or not hasattr(self.radar_data, 'mode'):
            return

        mode_str = str(self.radar_data.mode)
        if "SURVEILLANCE" not in mode_str and "MAPPING" not in mode_str:
            return

        # Get colors
        highlight_color = QColor(self._theme_manager.get_color("highlight"))
        warning_color = QColor(self._theme_manager.get_color("warning"))

        # Create glow colors
        glow_color = QColor(highlight_color)
        glow_color.setAlphaF(self._glow_intensity * 0.7)

        warning_glow = QColor(warning_color)
        warning_glow.setAlphaF(self._glow_intensity * 0.7)

        # Get radar display area
        radar_rect = self._get_radar_display_rect()
        center_x = radar_rect.center().x()
        center_y = radar_rect.center().y()
        radius = min(radar_rect.width(), radar_rect.height()) / 2 - 10

        # Get radar data from parent class
        radar_data = self.radar_data

        # Draw tactical targets
        for target in self._tactical_targets:
            # Calculate position
            angle = math.radians(target["bearing"])
            distance_factor = target["distance"] / 100.0  # Normalize to 0-1
            x = center_x + math.sin(angle) * radius * distance_factor
            y = center_y - math.cos(angle) * radius * distance_factor

            # Draw target
            self._draw_target_symbol(
                painter,
                QPointF(x, y),
                target["type"],
                target["threat_level"],
                warning_color,
                warning_glow
            )

    def _draw_target_symbol(self, painter: QPainter, position: QPointF, target_type: str,
                           threat_level: int, color: QColor, glow_color: QColor):
        """Draw a tactical target symbol"""
        # Set up painter
        painter.save()

        # Determine size based on threat level (1-5)
        size = 6 + threat_level * 2

        # Draw different symbols based on target type
        if target_type == "air":
            # Draw triangle for air targets
            path = QPainterPath()
            path.moveTo(position.x(), position.y() - size)
            path.lineTo(position.x() + size, position.y() + size)
            path.lineTo(position.x() - size, position.y() + size)
            path.closeSubpath()

            # Draw with glow effect
            pen = QPen(glow_color, 2)
            painter.setPen(pen)
            painter.drawPath(path)

            pen = QPen(color, 1)
            painter.setPen(pen)
            painter.drawPath(path)

        elif target_type == "ground":
            # Draw square for ground targets
            rect = QRect(
                int(position.x() - size/2),
                int(position.y() - size/2),
                size,
                size
            )

            # Draw with glow effect
            pen = QPen(glow_color, 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            pen = QPen(color, 1)
            painter.setPen(pen)
            painter.drawRect(rect)

        elif target_type == "naval":
            # Draw diamond for naval targets
            path = QPainterPath()
            path.moveTo(position.x(), position.y() - size)
            path.lineTo(position.x() + size, position.y())
            path.lineTo(position.x(), position.y() + size)
            path.lineTo(position.x() - size, position.y())
            path.closeSubpath()

            # Draw with glow effect
            pen = QPen(glow_color, 2)
            painter.setPen(pen)
            painter.drawPath(path)

            pen = QPen(color, 1)
            painter.setPen(pen)
            painter.drawPath(path)

        # Draw threat level indicator
        if threat_level >= 3:
            # Draw pulsing circle for high threats
            pulse_size = size + 4 + int(self._pulse_factor * 3)

            # Adjust alpha based on pulse
            pulse_color = QColor(color)
            pulse_color.setAlphaF(0.7 - self._pulse_factor * 0.5)

            pen = QPen(pulse_color, 1)
            painter.setPen(pen)
            painter.drawEllipse(position, pulse_size, pulse_size)

        painter.restore()

    def draw_scan_line(self, painter: QPainter):
        """Draw animated radar scan line"""
        # Get radar display area
        radar_rect = self._get_radar_display_rect()
        center_x = radar_rect.center().x()
        center_y = radar_rect.center().y()
        radius = min(radar_rect.width(), radar_rect.height()) / 2 - 10

        # Get colors
        highlight_color = QColor(self._theme_manager.get_color("highlight"))

        # Create gradient for scan line
        gradient = QLinearGradient()
        gradient.setStart(center_x, center_y)

        # Calculate end point based on scan angle
        end_x = center_x + math.sin(math.radians(self._scan_angle)) * radius
        end_y = center_y - math.cos(math.radians(self._scan_angle)) * radius
        gradient.setFinalStop(end_x, end_y)

        # Set gradient colors
        gradient.setColorAt(0, QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 180))
        gradient.setColorAt(0.8, QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 100))
        gradient.setColorAt(1, QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 0))

        # Draw scan line
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))

        # Create scan line path
        path = QPainterPath()
        path.moveTo(center_x, center_y)
        path.lineTo(end_x, end_y)

        # Add arc to create a wedge
        sweep_angle = 30  # Degrees
        start_angle = self._scan_angle - sweep_angle / 2
        path.arcTo(
            QRectF(radar_rect).adjusted(10, 10, -10, -10),
            -start_angle,
            -sweep_angle
        )
        path.closeSubpath()

        # Draw the path
        painter.drawPath(path)
        painter.restore()

    def _draw_tactical_overlay(self, painter: QPainter):
        """Draw tactical data overlay in corner of display"""
        # Get colors
        text_color = QColor(self._theme_manager.get_color("text"))
        accent_color = QColor(self._theme_manager.get_color("accent"))

        # Create glow color
        glow_color = QColor(accent_color)
        glow_color.setAlphaF(self._glow_intensity * 0.7)

        # Draw tactical data box in top-right corner
        box_rect = QRect(self.width() - 200, 50, 190, 120)

        # Draw box with enhanced effects
        self._visual_effects.draw_enhanced_rect(
            painter,
            box_rect,
            color=accent_color,
            fill=True,
            fill_color=QColor(0, 0, 0, 120),
            glow=True
        )

        # Draw tactical data
        font = QFont("Arial", 9)
        painter.setFont(font)

        # Draw title
        title_rect = QRect(box_rect.left(), box_rect.top(), box_rect.width(), 25)
        self._visual_effects.draw_enhanced_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "TACTICAL DATA",
            text_color,
            glow_color,
            self._pulse_factor
        )

        # Draw data lines
        y_offset = box_rect.top() + 30
        line_height = 18

        # Count targets by type
        air_targets = sum(1 for t in self._tactical_targets if t["type"] == "air")
        ground_targets = sum(1 for t in self._tactical_targets if t["type"] == "ground")
        naval_targets = sum(1 for t in self._tactical_targets if t["type"] == "naval")

        # Count high threat targets
        high_threats = sum(1 for t in self._tactical_targets if t["threat_level"] >= 4)

        # Draw data
        data_items = [
            f"AIR TARGETS: {air_targets}",
            f"GROUND TARGETS: {ground_targets}",
            f"NAVAL TARGETS: {naval_targets}",
            f"HIGH THREATS: {high_threats}"
        ]

        for item in data_items:
            text_rect = QRect(box_rect.left() + 10, y_offset, box_rect.width() - 20, line_height)
            self._visual_effects.draw_enhanced_text(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignLeft,
                item,
                text_color,
                glow_color,
                self._pulse_factor
            )
            y_offset += line_height

    def _get_radar_display_rect(self) -> QRect:
        """Get the rectangle for the radar display area"""
        # Calculate radar display area (centered in the display area)
        title_height = 40
        menu_height = 40
        display_height = self.height() - title_height - menu_height
        display_width = self.width()

        # Make it square
        size = min(display_width, display_height) - 40

        # Center in the display area
        left = (display_width - size) // 2
        top = title_height + (display_height - size) // 2

        return QRect(left, top, size, size)

    def _generate_sample_targets(self) -> List[Dict[str, Any]]:
        """Generate sample tactical targets for demonstration"""
        targets = []

        # Generate random targets
        for _ in range(15):
            target_type = random.choice(["air", "ground", "naval"])
            bearing = random.uniform(0, 360)
            distance = random.uniform(20, 100)
            threat_level = random.randint(1, 5)

            targets.append({
                "type": target_type,
                "bearing": bearing,
                "distance": distance,
                "threat_level": threat_level
            })

        return targets

    def _generate_sample_terrain_data(self) -> List[Dict[str, Any]]:
        """Generate sample terrain data for demonstration"""
        terrain_data = []

        # Generate a grid of terrain points
        for x in range(0, 100, 5):
            for y in range(0, 100, 5):
                # Generate elevation using simplex noise approximation
                elevation = (
                    math.sin(x * 0.05) * math.cos(y * 0.05) * 0.5 +
                    math.sin(x * 0.02 + y * 0.03) * 0.3 +
                    math.sin(x * 0.1) * math.sin(y * 0.1) * 0.2
                )

                # Normalize to 0-1 range
                elevation = (elevation + 1) / 2

                # Scale to realistic elevation (0-3000m)
                elevation *= 3000

                terrain_data.append({
                    "x": x,
                    "y": y,
                    "elevation": elevation
                })

        return terrain_data
