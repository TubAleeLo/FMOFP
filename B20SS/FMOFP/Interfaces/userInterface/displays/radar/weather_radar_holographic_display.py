"""
Holographic weather radar display with realistic 3D visualization of precipitation and VIL data.
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QEasingCurve, QEvent
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QRadialGradient, QTransform, QPainterPath, QImage, QLinearGradient
from PyQt6.QtWidgets import QApplication


from typing import Dict, List, Optional, Tuple, Any, Union
import math
import time
import random
import uuid
import copy
import traceback

from .holographic_radar_display import HolographicRadarDisplay
from Utils.logger.sys_logger import get_logger
from core.event_driven_communication import get_event_bus, Event

# Import rendering components
from .rendering import get_animation_controller
from .rendering import get_spatial_grid, get_dirty_region_tracker
from .rendering.particle_system import ParticleSystem
from .rendering.particle_renderer import ParticleRenderer

logger = get_logger()

class RadarSelectionMenu:
    """Tactical-style radar selection menu with military-grade reliability."""
    
    def __init__(self, parent_display):
        """Initialize the radar selection menu.
        
        Args:
            parent_display: Parent radar display that owns this menu
        """
        self.parent_display = parent_display
        self.visible = False
        self._menu_rect = QRectF()
        self._animation_progress = 0.0
        self._animation_start_time = 0.0
        self._selected_index = -1
        self._hover_index = -1
        
        # Advanced menu styling
        self._accent_color = QColor(0, 170, 255)  # Military blue
        self._background_opacity = 0.85
        self._grid_offset = 0.0
        self._pulse_opacity = 0.7
        self._scan_line_position = 0.0
        
        # Radar options with validation status
        self._radar_options = self._get_available_radar_systems()
        
        # Precise timers for animations
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(16)  # ~60 fps
        self._animation_timer.timeout.connect(self._update_animation)
        
        # Animation synchronization
        self._last_frame_time = time.time()
        
        # Pulse timer for tactical effects
        self._pulse_timer = QTimer()
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start()
        
        logger.info("[RADAR_MENU] Initialized radar selection menu")
    
    def _get_available_radar_systems(self):
        """Query display tree for available radar systems.
        
        Performs verification of radar system availability and status.
        
        Returns:
            List of validated radar system options
        """
        options = []
        # Get display tree manager
        try:
            from ..display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()
            
            # Core radar systems with availability verification
            radar_systems = [
                {"name": "WEATHER RADAR", "id": "weather_radar", "status": "ACTIVE"},
                {"name": "SAR", "id": "sar_radar", "status": "STANDBY"},
                {"name": "TFR", "id": "tfr_radar", "status": "STANDBY"},
                {"name": "AEWC", "id": "aewc_radar", "status": "STANDBY"},
                {"name": "TARGETING", "id": "targeting_radar", "status": "STANDBY"}
            ]
            
            # Validate each system's availability in the display tree
            for system in radar_systems:
                radar_node = tree_manager.root.get_child(system["id"])
                if radar_node:
                    system["available"] = True
                    options.append(system)
                else:
                    logger.warning(f"[RADAR_MENU] Radar system not found in display tree: {system['id']}")
                    system["available"] = False
                    # Still include unavailable systems, but mark them
                    options.append(system)
            
            logger.info(f"[RADAR_MENU] Found {len(options)} radar systems")
            return options
        except Exception as e:
            logger.error(f"[RADAR_MENU] Error querying radar systems: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Fallback to default options
            fallback_options = [
                {"name": "WEATHER RADAR", "id": "weather_radar", "status": "ACTIVE", "available": True},
                {"name": "SAR", "id": "sar_radar", "status": "STANDBY", "available": False},
                {"name": "TFR", "id": "tfr_radar", "status": "STANDBY", "available": False},
                {"name": "AEWC", "id": "aewc_radar", "status": "STANDBY", "available": False},
                {"name": "TARGETING", "id": "targeting_radar", "status": "STANDBY", "available": False}
            ]
            logger.info(f"[RADAR_MENU] Using fallback radar systems list")
            return fallback_options
    
    def show(self, position=None):
        """Show the radar selection menu.
        
        Args:
            position: Optional position to show menu at, otherwise centered
        """
        if self.visible:
            return
        
        self.visible = True
        self._animation_progress = 0.0
        self._animation_start_time = time.time()
        self._scan_line_position = 0.0
        
        # Set position if provided
        if position:
            self._menu_rect = QRectF(
                position.x() - 150,  # Center horizontally
                position.y() - 200,  # Show above click position
                300,  # Width
                400   # Height
            )
        else:
            # Center in parent display
            if self.parent_display:
                parent_width = self.parent_display.width()
                parent_height = self.parent_display.height()
                self._menu_rect = QRectF(
                    (parent_width - 300) / 2,
                    (parent_height - 400) / 2,
                    300,  # Width
                    400   # Height
                )
            else:
                # Default positioning
                self._menu_rect = QRectF(250, 100, 300, 400)
        
        # Start animation
        self._animation_timer.start()
        logger.info(f"[RADAR_MENU] Showing menu at {self._menu_rect.x():.1f}, {self._menu_rect.y():.1f}")
    
    def hide(self):
        """Hide the radar selection menu."""
        if not self.visible:
            return
        
        # Start closing animation
        self._animation_start_time = time.time()
        self._animation_timer.start()
        logger.info("[RADAR_MENU] Hiding menu")
    
    def is_visible(self):
        """Check if menu is visible."""
        return self.visible
    
    def _update_animation(self):
        """Update menu animation."""
        current_time = time.time()
        elapsed = current_time - self._animation_start_time
        
        # Calculate animation progress
        if self.visible:
            # Opening animation
            self._animation_progress = min(1.0, elapsed * 3.0)  # 1/3 second animation
            self._scan_line_position = min(1.0, elapsed * 4.5)  # 2/9 second scan line
            
            # Stop timer when animation completes
            if self._animation_progress >= 1.0:
                self._animation_timer.stop()
        else:
            # Closing animation
            self._animation_progress = max(0.0, 1.0 - elapsed * 3.0)
            self._scan_line_position = max(0.0, 1.0 - elapsed * 4.5)
            
            # Completely hide when animation completes
            if self._animation_progress <= 0.0:
                self.visible = False
                self._animation_timer.stop()
                logger.info("[RADAR_MENU] Menu hidden")
    
    def _update_pulse(self):
        """Update pulse effect for tactical styling."""
        # Update pulse opacity for accent elements
        self._pulse_opacity = 0.6 + 0.4 * abs(math.sin(time.time() * 2.0))
        
        # Update grid offset for tactical styling
        self._grid_offset = (self._grid_offset + 0.5) % 20.0
    
    def draw(self, painter):
        """Draw the radar selection menu.
        
        Args:
            painter: QPainter to use for drawing
        """
        if not self.visible and self._animation_progress <= 0.0:
            return
        
        try:
            # Save painter state
            painter.save()
            
            # Calculate animated rectangle
            animated_height = self._menu_rect.height() * self._animation_progress
            animated_rect = QRectF(
                self._menu_rect.x(),
                self._menu_rect.y() + (self._menu_rect.height() - animated_height) / 2,
                self._menu_rect.width(),
                animated_height
            )
            
            # Draw menu background with tactical styling
            self._draw_menu_background(painter, animated_rect)
            
            # Draw menu items if animation is at least 50% complete
            if self._animation_progress >= 0.5:
                self._draw_menu_items(painter, animated_rect)
            
            # Draw scan line during animation
            if self._animation_progress < 1.0 and self.visible:
                self._draw_scan_line(painter, animated_rect, self._scan_line_position)
            
            # Restore painter state
            painter.restore()
        except Exception as e:
            logger.error(f"[RADAR_MENU] Error drawing menu: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_menu_background(self, painter, rect):
        """Draw menu background with tactical styling.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
        """
        # Create background path with angular corners
        path = QPainterPath()
        corner_size = 15
        
        path.moveTo(rect.left() + corner_size, rect.top())
        path.lineTo(rect.right() - corner_size, rect.top())
        path.lineTo(rect.right(), rect.top() + corner_size)
        path.lineTo(rect.right(), rect.bottom() - corner_size)
        path.lineTo(rect.right() - corner_size, rect.bottom())
        path.lineTo(rect.left() + corner_size, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - corner_size)
        path.lineTo(rect.left(), rect.top() + corner_size)
        path.closeSubpath()
        
        # Fill with semi-transparent black
        background_color = QColor(0, 0, 0, int(220 * self._animation_progress))
        painter.fillPath(path, background_color)
        
        # Draw border with accent color
        border_color = QColor(self._accent_color)
        border_color.setAlphaF(self._pulse_opacity * self._animation_progress)
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)
        
        # Draw title
        title_rect = QRectF(
            rect.left() + 10,
            rect.top() + 10,
            rect.width() - 20,
            30
        )
        
        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont("Arial", 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "RADAR SYSTEMS")
        
        # Draw subtle grid pattern
        self._draw_tactical_grid(painter, rect)
    
    def _draw_tactical_grid(self, painter, rect):
        """Draw tactical grid overlay for military styling.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
        """
        # Save painter state
        painter.save()
        
        # Set up grid pen
        grid_pen = QPen(self._accent_color)
        grid_pen.setWidth(1)
        grid_opacity = 0.1 * self._animation_progress
        grid_color = QColor(self._accent_color)
        grid_color.setAlphaF(grid_opacity)
        grid_pen.setColor(grid_color)
        painter.setPen(grid_pen)
        
        # Draw horizontal grid lines
        grid_spacing = 20
        offset_y = self._grid_offset
        y = rect.top() + offset_y
        while y < rect.bottom():
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
            y += grid_spacing
            
        # Draw vertical grid lines
        offset_x = self._grid_offset
        x = rect.left() + offset_x
        while x < rect.right():
            painter.drawLine(
                QPointF(x, rect.top()),
                QPointF(x, rect.bottom())
            )
            x += grid_spacing
        
        # Restore painter state
        painter.restore()
    
    def _draw_menu_items(self, painter, rect):
        """Draw radar selection menu items.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
        """
        # Calculate item layout
        content_rect = QRectF(
            rect.left() + 20,
            rect.top() + 50,  # Below title
            rect.width() - 40,
            rect.height() - 70  # Leave space at bottom
        )
        
        # Calculate item height
        item_count = len(self._radar_options)
        item_height = min(60, content_rect.height() / max(1, item_count))
        spacing = 10
        
        # Draw each menu item
        for i, option in enumerate(self._radar_options):
            item_y = content_rect.top() + i * (item_height + spacing)
            item_rect = QRectF(
                content_rect.left(),
                item_y,
                content_rect.width(),
                item_height
            )
            
            # Check if this is the selected or hovered item
            is_selected = i == self._selected_index
            is_hovered = i == self._hover_index
            
            # Draw item background
            self._draw_menu_item_background(painter, item_rect, option, is_selected, is_hovered)
            
            # Draw item content
            self._draw_menu_item_content(painter, item_rect, option, is_selected, is_hovered)
    
    def _draw_menu_item_background(self, painter, rect, option, is_selected, is_hovered):
        """Draw menu item background with tactical styling.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
            option: Radar option data
            is_selected: Whether this item is selected
            is_hovered: Whether this item is being hovered over
        """
        # Create item path with angular corners
        path = QPainterPath()
        corner_size = 10
        
        path.moveTo(rect.left() + corner_size, rect.top())
        path.lineTo(rect.right() - corner_size, rect.top())
        path.lineTo(rect.right(), rect.top() + corner_size)
        path.lineTo(rect.right(), rect.bottom() - corner_size)
        path.lineTo(rect.right() - corner_size, rect.bottom())
        path.lineTo(rect.left() + corner_size, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - corner_size)
        path.lineTo(rect.left(), rect.top() + corner_size)
        path.closeSubpath()
        
        # Determine background color based on selection/hover state
        background_color = QColor(10, 10, 10, 150)  # Default
        
        if is_selected:
            # Selected item gets accent color
            background_color = QColor(self._accent_color)
            background_color.setAlpha(100)
        elif is_hovered:
            # Hovered item gets brighter
            background_color = QColor(30, 30, 30, 180)
        
        # Apply availability status
        available = option.get("available", False)
        if not available:
            # Darken unavailable items
            background_color = QColor(20, 20, 20, 100)
        
        # Fill background
        painter.fillPath(path, background_color)
        
        # Draw border with color based on status
        border_color = QColor(100, 100, 100, 150)  # Default
        
        if is_selected:
            # Selected item gets pulsing accent color
            border_color = QColor(self._accent_color)
            border_color.setAlphaF(self._pulse_opacity)
        elif is_hovered:
            # Hovered item gets accent color
            border_color = QColor(self._accent_color)
            border_color.setAlpha(150)
        elif option.get("status") == "ACTIVE":
            # Active item gets green border
            border_color = QColor(0, 180, 0, 150)
        elif option.get("status") == "STANDBY":
            # Standby item gets yellow border
            border_color = QColor(180, 180, 0, 150)
        
        # Apply availability status
        if not available:
            # Unavailable items get red border
            border_color = QColor(180, 0, 0, 150)
        
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)
    
    def _draw_menu_item_content(self, painter, rect, option, is_selected, is_hovered):
        """Draw menu item content with tactical styling.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
            option: Radar option data
            is_selected: Whether this item is selected
            is_hovered: Whether this item is being hovered over
        """
        # Get item properties
        name = option.get("name", "UNKNOWN")
        status = option.get("status", "OFFLINE")
        available = option.get("available", False)
        
        # Set text color based on selection/hover state
        if is_selected:
            text_color = QColor(255, 255, 255, 255)  # Bright white
        elif is_hovered:
            text_color = QColor(220, 220, 220, 255)  # Light gray
        else:
            text_color = QColor(180, 180, 180, 255)  # Medium gray
        
        # Apply availability status
        if not available:
            # Unavailable items get darker text
            text_color = QColor(100, 100, 100, 255)
        
        painter.setPen(QPen(text_color))
        
        # Draw radar name
        name_rect = QRectF(
            rect.left() + 10,
            rect.top() + 5,
            rect.width() - 20,
            rect.height() * 0.6
        )
        
        font = QFont("Arial", 10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        
        # Draw status indicator
        status_rect = QRectF(
            rect.left() + 10,
            rect.top() + rect.height() * 0.6,
            rect.width() - 20,
            rect.height() * 0.4
        )
        
        # Set status color
        if status == "ACTIVE":
            status_color = QColor(0, 180, 0, 255)  # Green
            status_text = "ACTIVE"
        elif status == "STANDBY":
            status_color = QColor(180, 180, 0, 255)  # Yellow
            status_text = "STANDBY"
        else:
            status_color = QColor(180, 0, 0, 255)  # Red
            status_text = "OFFLINE"
        
        # Apply availability status
        if not available:
            status_color = QColor(180, 0, 0, 255)  # Red
            status_text = "UNAVAILABLE"
        
        # Draw status text
        status_font = QFont("Arial", 8)
        painter.setFont(status_font)
        painter.setPen(QPen(status_color))
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"STATUS: {status_text}")
        
        # Draw decorative elements
        if is_selected or is_hovered:
            # Draw angle bracket on left side
            painter.setPen(QPen(self._accent_color, 2))
            
            # Left bracket
            left_x = rect.left() - 5
            top_y = rect.top() + 5
            bottom_y = rect.bottom() - 5
            mid_y = (top_y + bottom_y) / 2
            
            path = QPainterPath()
            path.moveTo(left_x, mid_y)
            path.lineTo(left_x + 5, top_y)
            path.moveTo(left_x, mid_y)
            path.lineTo(left_x + 5, bottom_y)
            
            painter.drawPath(path)
            
            # Right bracket
            right_x = rect.right() + 5
            
            path = QPainterPath()
            path.moveTo(right_x, mid_y)
            path.lineTo(right_x - 5, top_y)
            path.moveTo(right_x, mid_y)
            path.lineTo(right_x - 5, bottom_y)
            
            painter.drawPath(path)
    
    def _draw_scan_line(self, painter, rect, position):
        """Draw scan line animation during menu open/close.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle to draw in
            position: Position of scan line (0.0-1.0)
        """
        # Calculate scan line y-position
        y = rect.top() + rect.height() * position
        
        # Draw scan line
        painter.setPen(QPen(self._accent_color, 2))
        painter.drawLine(
            QPointF(rect.left(), y),
            QPointF(rect.right(), y)
        )
        
        # Add glow effect
        glow_gradient = QLinearGradient(
            0, y - 5,
            0, y + 5
        )
        glow_color = QColor(self._accent_color)
        glow_color.setAlpha(100)
        glow_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        glow_gradient.setColorAt(0.5, glow_color)
        glow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawRect(QRectF(
            rect.left(),
            y - 5,
            rect.width(),
            10
        ))
    
    def handle_click(self, position):
        """Handle mouse click at the specified position.
        
        Args:
            position: Click position (QPointF)
            
        Returns:
            True if click was handled, None if no action, radar ID if radar was selected
        """
        try:
            # If menu is not visible, ignore click
            if not self.visible:
                return False
            
            # Check if click is within menu
            if not self._menu_rect.contains(position):
                # Click outside menu, hide it
                self.hide()
                return True
            
            # Calculate item layout
            content_rect = QRectF(
                self._menu_rect.left() + 20,
                self._menu_rect.top() + 50,  # Below title
                self._menu_rect.width() - 40,
                self._menu_rect.height() - 70  # Leave space at bottom
            )
            
            # Calculate item height
            item_count = len(self._radar_options)
            item_height = min(60, content_rect.height() / max(1, item_count))
            spacing = 10
            
            # Check each menu item
            for i, option in enumerate(self._radar_options):
                item_y = content_rect.top() + i * (item_height + spacing)
                item_rect = QRectF(
                    content_rect.left(),
                    item_y,
                    content_rect.width(),
                    item_height
                )
                
                if item_rect.contains(position):
                    # Item clicked, check if it's available
                    if option.get("available", False):
                        # Select this item
                        self._selected_index = i
                        
                        # Hide menu
                        self.hide()
                        
                        # Return radar ID
                        radar_id = option.get("id")
                        logger.info(f"[RADAR_MENU] Selected radar: {radar_id}")
                        return radar_id
                    else:
                        # Item is unavailable
                        logger.info(f"[RADAR_MENU] Clicked unavailable radar: {option.get('name')}")
                        return None
            
            # No item clicked
            return True
        except Exception as e:
            logger.error(f"[RADAR_MENU] Error handling click: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def handle_hover(self, position):
        """Handle mouse hover at the specified position.
        
        Args:
            position: Hover position (QPointF)
            
        Returns:
            True if hover state changed, False otherwise
        """
        try:
            # If menu is not visible, ignore hover
            if not self.visible:
                return False
            
            old_hover_index = self._hover_index
            self._hover_index = -1
            
            # Check if hover is within menu
            if not self._menu_rect.contains(position):
                return old_hover_index != self._hover_index
            
            # Calculate item layout
            content_rect = QRectF(
                self._menu_rect.left() + 20,
                self._menu_rect.top() + 50,  # Below title
                self._menu_rect.width() - 40,
                self._menu_rect.height() - 70  # Leave space at bottom
            )
            
            # Calculate item height
            item_count = len(self._radar_options)
            item_height = min(60, content_rect.height() / max(1, item_count))
            spacing = 10
            
            # Check each menu item
            for i, _ in enumerate(self._radar_options):
                item_y = content_rect.top() + i * (item_height + spacing)
                item_rect = QRectF(
                    content_rect.left(),
                    item_y,
                    content_rect.width(),
                    item_height
                )
                
                if item_rect.contains(position):
                    self._hover_index = i
                    break
            
            return old_hover_index != self._hover_index
        except Exception as e:
            logger.error(f"[RADAR_MENU] Error handling hover: {str(e)}")
            logger.error(traceback.format_exc())
            return False

class WeatherRadarHolographicDisplay(HolographicRadarDisplay):
    """Holographic weather radar display with realistic 3D visualization."""
    
    def __init__(self):
        """Initialize holographic weather radar display."""
        # Add holographic display properties needed by parent class
        # These must be defined BEFORE calling super().__init__()
        self.holo_rotation = 0.0  # Rotation angle for 3D effect
        self.holo_rotation_speed = 5.0  # Degrees per second
        self.holo_elevation = 30.0  # Elevation angle for 3D view
        self.holo_perspective = 0.3  # Perspective factor (0.0 to 1.0)
        self.holo_layer_separation = 0.1  # Separation between layers
        self.holo_layers = 3  # Number of layers in holographic display
        
        # Initialize radar selection menu
        self._radar_selection_menu = RadarSelectionMenu(self)
        self._radar_button_rect = QRectF(0, 0, 0, 0)  # Will be updated in draw_navigation
        
        # Add feature flags needed by parent class
        self.use_parallax_effects = True
        self.use_dynamic_focus = True
        self.use_tactical_overlays = True
        self.use_enhanced_targeting = True
        self.use_threat_prioritization = True
        self.use_predictive_tracking = True
        self.use_environmental_awareness = True
        
        # Now call the parent constructor
        super().__init__()
        
        # Get display tree manager
        from ..display_nodes.display_tree_manager import get_display_tree_manager
        self.tree = get_display_tree_manager()
        self._subscribers_setup = False
        
        # Get the data coordinator for persistent data storage
        from .radar_display_data_coordinator import get_radar_display_data_coordinator
        self._data_coordinator = get_radar_display_data_coordinator()
        
        # Get log throttler to manage logging frequency
        from ..log_throttler import get_log_throttler
        self._log_throttler = get_log_throttler()
        
        # Initialize data storage
        self._precipitation_data = []
        self._vil_data = []
        self._cell_data = []
        
        # Initialize visual elements with default values
        self._visual_elements = {
            'show_vil': True,
            'show_vil_values': True,
            'show_precipitation_values': True,
            'show_cell_values': True
        }
        
        # Add persistence timers to keep VIL data visible longer
        self._vil_persist_time = 5.0  # Keep VIL data visible for 5 seconds
        self._vil_data_timestamp = {}  # Track when each VIL point was received
        self._vil_data_backup = []     # Backup storage for VIL data
        
        # VIL data statistics for logging
        self._vil_data_stats = {
            'received_count': 0,
            'stored_count': 0,
            'drawn_count': 0,
            'last_stats_reset': 0,
            'stats_interval': 60.0  # Reset stats every minute
        }
        
        # Initialize advanced animation controller
        self._animation_controller = get_animation_controller()
        
        # Initialize spatial partitioning
        self._spatial_grid = get_spatial_grid()
        self._dirty_region_tracker = get_dirty_region_tracker()
        
        # Initialize enhanced particle system
        self._weather_particles = {
            'precipitation': {},  # Dict of precipitation_id -> list of particles
            'vil': {}            # Dict of vil_id -> list of particles
        }
        self._last_particle_update = time.time()
        
        # Add particle system settings for different precipitation types
        self._particle_settings = {
            'rain': {
                'velocity_range': [-2, 2, 15, 25],  # [min_x, max_x, min_y, max_y]
                'size_range': [1, 3],
                'lifetime_range': [0.5, 1.5],
                'color_factor': 0.8,  # Slightly transparent
                'shape': 'ellipse',
                'aspect_ratio': 1.5   # Elongated vertically
            },
            'snow': {
                'velocity_range': [-5, 5, 5, 10],
                'size_range': [2, 4],
                'lifetime_range': [1.5, 3.0],
                'color_factor': 0.7,
                'shape': 'hexagon',
                'aspect_ratio': 1.0
            },
            'hail': {
                'velocity_range': [-1, 1, 25, 35],
                'size_range': [2, 5],
                'lifetime_range': [0.3, 0.8],
                'color_factor': 0.9,
                'shape': 'circle_cluster',
                'aspect_ratio': 1.0
            },
            'default': {
                'velocity_range': [-3, 3, 10, 20],
                'size_range': [1, 4],
                'lifetime_range': [0.8, 2.0],
                'color_factor': 0.8,
                'shape': 'circle',
                'aspect_ratio': 1.0
            }
        }
        
        # Particle system performance settings
        self._max_particles_per_system = 100  # Performance limit
        self._particle_emission_rate = 10.0   # Particles per second
        self._last_emission_time = time.time()
        
        # Weather evolution settings
        self._weather_evolution_time = 0.0
        
        # Feature flags for enhanced visualization
        self._use_texture_rendering = True
        self._use_enhanced_particles = True
        self._use_turbulent_edges = True
        self._use_atmospheric_scattering = True
        
        # Connect animation controller signals
        self._animation_controller.animation_updated.connect(self._handle_animation_update)
        
        # Optimization settings
        self._use_spatial_partitioning = True
        self._use_dirty_regions = True
        
        # Display settings
        self._intensity_colors = {
            'SEVERE': QColor(255, 0, 0, 128),      # Red
            'MODERATE': QColor(255, 165, 0, 128),  # Orange
            'LIGHT': QColor(255, 255, 0, 128),     # Yellow
            'VERY_LIGHT': QColor(0, 255, 0, 128)   # Green
        }
        self._precipitation_colors = {
            'hail': QColor(255, 0, 255, 128),      # Magenta
            'heavy_rain': QColor(255, 0, 0, 128),  # Red
            'rain': QColor(0, 0, 255, 128),        # Blue
            'snow': QColor(255, 255, 255, 128),    # White
            'mixed': QColor(128, 0, 255, 128),     # Purple
            None: QColor(128, 128, 128, 128)       # Gray
        }
        self._vil_colors = {
            'HIGH': QColor(255, 0, 0, 128),       # Red for high VIL
            'MEDIUM': QColor(255, 165, 0, 128),   # Orange for medium VIL
            'LOW': QColor(255, 255, 0, 128),      # Yellow for low VIL
            'MINIMAL': QColor(0, 255, 0, 128)     # Green for minimal VIL
        }
        
        # Add weather-specific holographic settings
        self._weather_layer_count = 3  # Number of weather data layers
        self._weather_layer_separation = 0.2  # Separation between weather layers
        self._weather_perspective = 0.4  # Perspective factor for weather data
        
        # Weather animation settings
        self._weather_rotation = 0.0  # Current rotation angle
        self._weather_rotation_speed = 3.0  # Degrees per second
        self._weather_pulse_factor = 0.0  # Pulse effect for weather data
        self._weather_pulse_speed = 2.0  # Pulse cycles per second
        
        # Add holographic display properties needed by parent class
        self.holo_rotation = 0.0  # Rotation angle for 3D effect
        self.holo_rotation_speed = 5.0  # Degrees per second
        self.holo_elevation = 30.0  # Elevation angle for 3D view
        self.holo_perspective = 0.3  # Perspective factor (0.0 to 1.0)
        self.holo_layer_separation = 0.1  # Separation between layers
        self.holo_layers = 3  # Number of layers in holographic display
        # Add manual animation timer for fallback animation
        self._manual_animation_timer = QTimer()
        self._manual_animation_timer.setInterval(16)  # ~60 fps
        self._manual_animation_timer.timeout.connect(self._manual_animation_update)
        
        # Initialize sweep angle for direct animation
        self._direct_sweep_angle = 0.0
        
        # Add cleanup timer for expired data points
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start(5000)  # Run cleanup every 5 seconds
        
        # Start manual animation timer
        self._manual_animation_timer.start()
        
        # Initialize textures if texture rendering is enabled
        if self._use_texture_rendering:
            self._initialize_textures()
        
        logger.info("[WEATHER_HOLO] Initialized enhanced holographic weather radar display")

    def cleanup(self):
        """Clean up resources and stop animations.

        FuturisticRadarDisplay.cleanup() (inherited) only knows about the
        single `_animation_timer` it defines itself -- it has no knowledge
        of this subclass's own `_manual_animation_timer`/`_cleanup_timer`,
        or of the composed `RadarSelectionMenu`'s `_animation_timer`/
        `_pulse_timer`. All four are unparented QTimer() instances (no Qt
        parent for automatic C++-side cleanup), started immediately and
        never otherwise stopped anywhere in this file. RadarDisplayFactory
        calls `cleanup()` (when present) then `gc.collect()` when evicting
        a cached display on a holographic<->standard display-type switch
        (confirmed live: gc.collect() does successfully reclaim the whole
        widget+timer reference-cycle graph even without this), but relying
        solely on GC to indirectly stop timers -- rather than stopping them
        explicitly at the moment cleanup() is actually called -- is fragile
        and leaves them ticking (wasted CPU, and a wider window before
        reclamation) for longer than necessary. Explicitly stop all of them
        here, then call up to the inherited cleanup() for _animation_timer
        and everything else it already handles correctly.
        """
        try:
            if hasattr(self, '_manual_animation_timer') and self._manual_animation_timer:
                self._manual_animation_timer.stop()
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer:
                self._cleanup_timer.stop()
            if hasattr(self, '_radar_selection_menu') and self._radar_selection_menu:
                menu = self._radar_selection_menu
                if hasattr(menu, '_animation_timer') and menu._animation_timer:
                    menu._animation_timer.stop()
                if hasattr(menu, '_pulse_timer') and menu._pulse_timer:
                    menu._pulse_timer.stop()
            logger.info("[WEATHER_HOLO] Stopped manual animation, cleanup, and radar-selection-menu timers")
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error stopping WeatherRadarHolographicDisplay-specific timers: {str(e)}")

        super().cleanup()

    async def initialize_display(self):
        """Initialize display and set up subscribers."""
        try:
            # Check if parent has initialize_display method before calling it
            if hasattr(super(), 'initialize_display'):
                await super().initialize_display()
            else:
                logger.info("[WEATHER_HOLO] Parent class does not have initialize_display method")
            
            # Initialize tree if needed
            if not self.tree._initialized:
                await self.tree.initialize()
                
            # Setup subscribers if not already done
            if not self._subscribers_setup:
                await self._setup_node_subscribers()
                self._subscribers_setup = True
                logger.info("[WEATHER_HOLO] Subscribers setup complete")
                
            # Verify node structure and subscriptions
            await self._verify_node_structure()
            
            # Fix: Explicitly ensure animation controllers are active
            self._ensure_animation_controllers_active()
                
            logger.info("[WEATHER_HOLO] Display initialization complete")
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error initializing display: {str(e)}")
            logger.error(traceback.format_exc())
            raise
            
    def _ensure_animation_controllers_active(self):
        """Ensure all animation controllers are properly initialized and running."""
        logger.info("[WEATHER_HOLO] Ensuring animation controllers are active")
        
        # Check parent class animation controller
        parent_controller_active = False
        if hasattr(self, '_animation_controller') and self._animation_controller:
            if hasattr(self._animation_controller, 'is_running'):
                parent_controller_active = self._animation_controller.is_running()
            else:
                # Fallback check if is_running method is missing
                parent_controller_active = getattr(self._animation_controller, '_is_running', False)
            
            # Start if not running
            if not parent_controller_active:
                logger.warning("[WEATHER_HOLO] Animation controller not running, restarting it")
                if hasattr(self._animation_controller, 'start'):
                    self._animation_controller.start()
                    
                # Cancel any existing animations to ensure a clean start
                if hasattr(self._animation_controller, 'cancel_all_animations'):
                    self._animation_controller.cancel_all_animations()
                    
                # Start radar sweep animation
                self._start_sweep_animation()
                
        # Diagnostic logging
        logger.info(f"[WEATHER_HOLO] Animation controller active: {parent_controller_active}")
        
        # Make sure manual animation timer is running as fallback
        if hasattr(self, '_manual_animation_timer'):
            if not self._manual_animation_timer.isActive():
                logger.info("[WEATHER_HOLO] Starting manual animation timer as fallback")
                self._manual_animation_timer.start()
                
    def _start_sweep_animation(self):
        """Start radar sweep animation."""
        logger.info("[WEATHER_HOLO] Starting radar sweep animation")
        
        # First try to use animation controller from parent class
        try:
            # Create continuous animation for radar sweep
            if hasattr(self._animation_controller, 'create_animation'):
                self._animation_controller.create_animation(
                    "sweep_angle",              # Animation ID
                    0.0,                        # Start value
                    360.0,                      # End value 
                    8.0,                        # Duration in seconds
                    lambda value: self._set_sweep_angle(value),  # Update callback
                    lambda: self._restart_sweep_animation(),     # Completion callback
                    QEasingCurve.Type.Linear    # Linear animation
                )
                logger.info("[WEATHER_HOLO] Sweep animation started with animation controller")
                return True
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error starting sweep animation: {str(e)}")
            
        # Fallback to manual animation timer - just start it if not running
        try:
            if hasattr(self, '_manual_animation_timer'):
                # Start the timer if not already running
                if not self._manual_animation_timer.isActive():
                    self._manual_animation_timer.start()
                logger.info("[WEATHER_HOLO] Sweep animation started with manual timer")
                return True
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error starting manual sweep animation: {str(e)}")
            
        # If both methods failed, use direct update in paintEvent
        logger.warning("[WEATHER_HOLO] Using direct paintEvent updates for sweep animation")
        return False
        
    def _restart_sweep_animation(self):
        """Restart radar sweep animation to create continuous effect."""
        logger.info("[WEATHER_HOLO] Restarting radar sweep animation")
        self._start_sweep_animation()
        
    def _set_sweep_angle(self, value):
        """Set radar sweep angle."""
        # Update our local sweep angle
        self.sweep_angle = value
        
        # Also update parent class sweep angle if accessible
        try:
            if hasattr(super(), 'sweep_angle'):
                super().sweep_angle = value
        except Exception:
            logger.debug("HolographicWeatherRadarDisplay: super().sweep_angle not settable", exc_info=True)

        # Request a repaint
        self.update()
        
    def _set_sweep_angle_manual(self, value):
        """Set radar sweep angle from manual timer."""
        self.sweep_angle = value
        
        # Also update parent class sweep angle if accessible
        try:
            if hasattr(super(), 'sweep_angle'):
                super().sweep_angle = value
        except Exception:
            logger.debug("HolographicWeatherRadarDisplay: super().sweep_angle not settable", exc_info=True)

        # Request a repaint
        self.update()
    
    async def _setup_node_subscribers(self):
        """Set up node subscribers for state updates."""
        try:
            # Get weather radar nodes
            weather = self.tree.root.get_child("weather_radar")
            if not weather:
                logger.error("[WEATHER_HOLO] Weather radar node not found")
                return
                
            # Subscribe to mode updates
            mode_node = weather.get_child("mode")
            if mode_node:
                # Track subscriber count before and after
                mode_subscribers_before = len(mode_node.subscribers)
                mode_node.add_subscriber(self._handle_mode_update)
                mode_subscribers_after = len(mode_node.subscribers)
                logger.info(f"[WEATHER_HOLO] Subscribed to mode updates: before={mode_subscribers_before}, after={mode_subscribers_after}")
            else:
                logger.error("[WEATHER_HOLO] Mode node not found during subscription setup")
            
            # Subscribe to visual updates
            visual_node = weather.get_child("visual")
            if visual_node:
                # Track subscriber count before and after
                visual_subscribers_before = len(visual_node.subscribers)
                visual_node.add_subscriber(self._handle_visual_update)
                visual_subscribers_after = len(visual_node.subscribers)
                logger.info(f"[WEATHER_HOLO] Subscribed to visual updates: before={visual_subscribers_before}, after={visual_subscribers_after}")
            else:
                logger.error("[WEATHER_HOLO] Visual node not found during subscription setup")
            
            # Subscribe to data updates
            data_node = weather.get_child("data")
            if data_node:
                # Track all subscription results
                subscription_results = {}
                
                # Ensure data nodes exist, create them if needed
                for data_type in ["precipitation", "vil", "cells"]:
                    node = data_node.get_child(data_type)
                    if not node:
                        # Node doesn't exist, create it
                        from ..display_nodes.display_node_base import DisplayNode
                        node = DisplayNode(data_type, parent=data_node)
                        data_node.add_child(node)
                        logger.info(f"[WEATHER_HOLO] Created missing {data_type} node")
                    
                    # Track subscriber count before and after
                    subscribers_before = len(node.subscribers)
                    
                    # Ensure this instance isn't already subscribed
                    already_subscribed = False
                    for subscriber in node.subscribers:
                        if hasattr(subscriber, '__self__') and subscriber.__self__ is self and subscriber.__func__ is self._handle_data_update.__func__:
                            already_subscribed = True
                            logger.info(f"[WEATHER_HOLO] Already subscribed to {data_type} updates")
                            break
                    
                    if not already_subscribed:
                        node.add_subscriber(self._handle_data_update)
                    
                    subscribers_after = len(node.subscribers)
                    
                    # Store subscription result
                    subscription_results[data_type] = {
                        "success": subscribers_after > subscribers_before or already_subscribed,
                        "before": subscribers_before,
                        "after": subscribers_after,
                        "already_subscribed": already_subscribed
                    }
                    
                    logger.info(f"[WEATHER_HOLO] Subscribed to {data_type} updates: before={subscribers_before}, after={subscribers_after}")
                
                # Log overall subscription results
                logger.info(f"[WEATHER_HOLO] Data subscription results: {subscription_results}")
                
                # Verify subscriptions were successful
                for data_type, result in subscription_results.items():
                    if not result.get("success", False):
                        logger.error(f"[WEATHER_HOLO] Failed to subscribe to {data_type} updates")
                        # Try one more time with a different approach
                        node = data_node.get_child(data_type)
                        if node:
                            node.subscribers.add(self._handle_data_update)
                            logger.info(f"[WEATHER_HOLO] Forced subscription to {data_type} node")
            else:
                # Create data node if it doesn't exist
                from ..display_nodes.display_node_base import DisplayNode
                data_node = DisplayNode("data", parent=weather)
                weather.add_child(data_node)
                logger.info("[WEATHER_HOLO] Created missing data node")
                
                # Recursively call this method to set up subscribers for the newly created node
                await self._setup_node_subscribers()
                        
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error setting up subscribers: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _verify_node_structure(self):
        """Verify node structure and subscriptions."""
        try:
            logger.info("[WEATHER_HOLO] Verifying node structure and subscriptions")
            
            # Get weather radar node
            weather = self.tree.root.get_child("weather_radar")
            if not weather:
                logger.error("[WEATHER_HOLO] Weather radar node not found during verification")
                return
                
            # Verify data node and its children
            data_node = weather.get_child("data")
            if not data_node:
                logger.error("[WEATHER_HOLO] Data node not found during verification")
                return
                
            # Verify data node children and their subscribers
            for data_type in ["precipitation", "vil", "cells"]:
                node = data_node.get_child(data_type)
                if not node:
                    logger.error(f"[WEATHER_HOLO] {data_type} node not found during verification")
                    continue
                    
                # Check if this instance is subscribed
                is_subscribed = False
                for subscriber in node.subscribers:
                    if hasattr(subscriber, '__self__') and subscriber.__self__ is self:
                        is_subscribed = True
                        break
                        
                if not is_subscribed:
                    logger.error(f"[WEATHER_HOLO] Not subscribed to {data_type} node")
                    # Force subscription
                    node.add_subscriber(self._handle_data_update)
                    logger.info(f"[WEATHER_HOLO] Forced subscription to {data_type} node")
                else:
                    logger.info(f"[WEATHER_HOLO] Verified subscription to {data_type} node")
                    
            logger.info("[WEATHER_HOLO] Node structure and subscription verification complete")
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error verifying node structure: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_mode_update(self, node_name: str, mode_data: Union[Dict[str, Any], str]) -> None:
        """Handle mode state updates.
        
        Args:
            node_name: Name of updated node
            mode_data: New mode state (can be dict or string)
        """
        try:
            # Use throttled logging for mode updates
            should_log, _ = self._log_throttler.should_log("mode_update", 1.0)
            if should_log:
                logger.info(f"[WEATHER_HOLO] Mode update received from {node_name}: {mode_data}")
            
            # Use the message adapter to normalize the mode data
            from .weather_radar_display_message_adapter import get_weather_radar_display_message_adapter
            adapter = get_weather_radar_display_message_adapter()
            normalized_mode = adapter.normalize_mode_message(mode_data)
            
            # Log the normalized mode data (throttled)
            should_log, _ = self._log_throttler.should_log("normalized_mode", 10.0)
            if should_log:
                logger.info(f"[WEATHER_HOLO] Normalized mode data: {normalized_mode}")
            
            # Get the current mode from the normalized data
            current_mode = normalized_mode['current_mode']
            mode_value = normalized_mode['mode_value']
            source_system = normalized_mode['source_system']
            force_update = normalized_mode.get('force_update', False)
            
            if not current_mode:
                logger.error("[WEATHER_HOLO] Mode update missing current_mode")
                return
                
            # Convert to enum if needed
            try:
                # Import radar enums
                from Systems.radarManagement.radar_enums import weather_radarMode
                
                # If it's already an enum instance, use it directly
                if isinstance(current_mode, weather_radarMode):
                    new_mode = current_mode
                else:
                    # Try to get the enum by name
                    new_mode = getattr(weather_radarMode, current_mode)
                
                # Throttled mode logging
                should_log, _ = self._log_throttler.should_log("found_mode", 10.0)
                if should_log:
                    logger.info(f"[WEATHER_HOLO] Found mode enum: {new_mode.name}")
            except AttributeError:
                # Handle fallback with more robust error handling
                logger.error(f"[WEATHER_HOLO] Mode enum lookup failed for {current_mode}")
                try:
                    # Import radar enums
                    from Systems.radarManagement.radar_enums import weather_radarMode
                    
                    # Map mode value to enum
                    mode_map = {
                        'STANDBY': weather_radarMode.STANDBY,
                        'SURVEILLANCE': weather_radarMode.SURVEILLANCE,
                        'MAPPING': weather_radarMode.MAPPING,
                        'TURBULENCE': weather_radarMode.TURBULENCE,
                        'WINDSHEAR': weather_radarMode.WINDSHEAR
                    }
                    if isinstance(current_mode, str):
                        new_mode = mode_map.get(current_mode.upper())
                    else:
                        new_mode = mode_map.get(current_mode.name.upper())
                    if not new_mode:
                        logger.error(f"[WEATHER_HOLO] Invalid mode: {current_mode}")
                        return
                    logger.info(f"[WEATHER_HOLO] Mapped mode to enum: {new_mode.name}")
                except Exception as e:
                    logger.error(f"[WEATHER_HOLO] Mode mapping failed: {str(e)}")
                    return

            # Check if mode is actually changing or force_update is set
            if self._current_mode != new_mode or force_update:
                # Force mode update - important state change, always log
                logger.info(f"[WEATHER_HOLO] Forcing mode update to: {new_mode.name}")
                self._previous_mode = self._current_mode
                self._current_mode = new_mode
                self._mode_transition_time = time.time()
                
                # Use the VisualSettingsManager to apply mode-specific settings
                # Use the async version since we're in an async method
                from ..utils.visual_settings_manager import get_visual_settings_manager
                manager = get_visual_settings_manager("weather_radar")
                await manager.apply_mode_settings_async(new_mode.name)
                
                # Update local visual elements from the settings manager
                self._visual_elements = manager.get_settings()
                
                # Log with throttling
                should_log, _ = self._log_throttler.should_log("applied_settings", 10.0)
                if should_log:
                    logger.info(f"[WEATHER_HOLO] Applied {new_mode.name} settings using VisualSettingsManager")
                
                # Force display update
                self.update()
                if hasattr(self, 'repaint'):
                    self.repaint()
                
                should_log, _ = self._log_throttler.should_log("forced_update", 10.0)
                if should_log:
                    logger.info("[WEATHER_HOLO] Forced display update")
            else:
                # Mode already set, throttled logging
                should_log, _ = self._log_throttler.should_log("mode_unchanged", 30.0)
                if should_log:
                    logger.debug(f"[WEATHER_HOLO] Mode already set to {new_mode.name}, no update needed")
        
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error handling mode update: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_visual_update(self, node_name: str, visual_data: Dict[str, Any]) -> None:
        """Handle visual state updates.
        
        Args:
            node_name: Name of updated node
            visual_data: New visual state
        """
        try:
            # Throttled logging for visual updates
            should_log, _ = self._log_throttler.should_log("visual_update", 15.0)
            if should_log:
                logger.info(f"[WEATHER_HOLO] Visual update from {node_name}")
            
            # Enhanced logging for visual elements
            old_show_vil = self._visual_elements.get('show_vil', False)
            new_show_vil = visual_data.get('show_vil', False)
            
            # Update the settings manager
            from ..utils.visual_settings_manager import get_visual_settings_manager
            manager = get_visual_settings_manager("weather_radar")
            await manager.update_settings_async(visual_data, apply_to_node=False)
            
            # Store visual elements locally for backward compatibility
            self._visual_elements = manager.get_settings()
            
            # Log changes to show_vil flag (only if changed)
            if old_show_vil != new_show_vil:
                logger.info(f"[WEATHER_HOLO] show_vil flag changed: {old_show_vil} -> {new_show_vil}")
            
            # Ensure VIL is always visible in SURVEILLANCE mode
            if hasattr(self, '_current_mode') and self._current_mode and self._current_mode.name == 'SURVEILLANCE':
                if not self._visual_elements.get('show_vil', False):
                    # Update both local copy and settings manager
                    self._visual_elements['show_vil'] = True
                    self._visual_elements['show_vil_values'] = True
                    await manager.update_settings_async({
                        'show_vil': True,
                        'show_vil_values': True
                    }, apply_to_node=False)
                    logger.info("[WEATHER_HOLO] Forced show_vil=True in SURVEILLANCE mode")
            
            # Log final visual state (with throttling)
            should_log, _ = self._log_throttler.should_log("final_visual", 30.0)
            if should_log:
                logger.info("[WEATHER_HOLO] Applied visual settings")
            
            # Create and publish update event
            from core.event_driven_communication import get_event_bus, Event
            event_bus = get_event_bus()
            event = Event('weather_radar_update', {})
            event_bus.publish(event)
            
            should_log, _ = self._log_throttler.should_log("published_event", 30.0)
            if should_log:
                logger.info("[WEATHER_HOLO] Published visual update event")
            
            # Force display update
            self.update()
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error handling visual update: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_data_update(self, node_name: str, data: Any) -> None:
        """Handle data state updates.
        
        Args:
            node_name: Name of updated node
            data: New data state
        """
        try:
            # Check if we should log detailed entry for this update
            should_log_entry, _ = self._log_throttler.should_log(f"data_update_entry_{node_name}", 30.0)
            if should_log_entry:
                logger.info(f"[WEATHER_HOLO] DATA UPDATE RECEIVED: node={node_name}, data_type={type(data)}")
            
            # Track message counts for statistics based on node name
            if "precipitation" in node_name:
                # Process precipitation data
                processed_data = await self._process_precipitation_data(data)
                if processed_data:
                    self._precipitation_data = processed_data
                    logger.info(f"[WEATHER_HOLO] Processed {len(processed_data)} precipitation data points")
                else:
                    logger.info("[WEATHER_HOLO] No precipitation data processed")
                    
            elif "vil" in node_name:
                # Process VIL data
                processed_data = await self._process_vil_data(data)
                if processed_data:
                    self._vil_data = processed_data
                    logger.info(f"[WEATHER_HOLO] Processed {len(processed_data)} VIL data points")
                else:
                    logger.info("[WEATHER_HOLO] No VIL data processed")
                    
            elif "cells" in node_name:
                # Process cell data
                processed_data = await self._process_cell_data(data)
                if processed_data:
                    self._cell_data = processed_data
                    logger.info(f"[WEATHER_HOLO] Processed {len(processed_data)} cell data points")
                else:
                    logger.info("[WEATHER_HOLO] No cell data processed")
            
            # Request display update
            self.update()
            if hasattr(self, 'repaint'):
                self.repaint()
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error handling data update: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _process_precipitation_data(self, data: Any) -> List[Dict[str, Any]]:
        """Process precipitation data for holographic display.
        
        Args:
            data: Precipitation data in various formats
            
        Returns:
            Processed precipitation data list
        """
        try:
            # Store current timestamp for data persistence
            current_time = time.time()
            
            # Extract precipitation data from various formats
            extracted_precip_data = []  # Store extracted data here first
            precip_data_found = False
            
            # Format 1: Direct list of precipitation data points
            if isinstance(data, list) and len(data) > 0:
                logger.info(f"[WEATHER_HOLO] Found list of {len(data)} precipitation data points")
                extracted_precip_data = data
                precip_data_found = True
            
            # Format 2: Data object with 'data' attribute containing precipitation list
            elif hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
                logger.info(f"[WEATHER_HOLO] Extracting {len(data.data)} precipitation points from data.data")
                extracted_precip_data = data.data
                precip_data_found = True

                logger.info(f"[WEATHER_HOLO] Created {len(extracted_precip_data)} precipitation data points from integer/binary value")
                precip_data_found = True
                
            # Format 3: Dictionary with additional_info.weather_data.precipitation_data
            elif isinstance(data, dict) and 'additional_info' in data:
                logger.info("[WEATHER_HOLO] Found dictionary with additional_info")
                additional_info = data['additional_info']
                
                if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                    weather_data = additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info dict: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'precipitation_data' in weather_data and isinstance(weather_data['precipitation_data'], list):
                        precip_data_list = weather_data['precipitation_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(precip_data_list)} precipitation points in weather_data dict")
                        extracted_precip_data = precip_data_list
                        precip_data_found = True
            
            # Format 4: Object with additional_info attribute containing weather_data
            elif hasattr(data, 'additional_info') and data.additional_info is not None:
                logger.info("[WEATHER_HOLO] Found object with additional_info attribute")
                
                # Handle both dictionary and object attribute access
                if isinstance(data.additional_info, dict) and 'weather_data' in data.additional_info:
                    weather_data = data.additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'precipitation_data' in weather_data and isinstance(weather_data['precipitation_data'], list):
                        precip_data_list = weather_data['precipitation_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(precip_data_list)} precipitation points in weather_data")
                        extracted_precip_data = precip_data_list
                        precip_data_found = True
            
            # If we found precipitation data, process and store it
            if precip_data_found and extracted_precip_data:
                # Extract request_id from the data if available
                request_id = None
                if isinstance(data, dict) and 'request_id' in data:
                    request_id = data['request_id']
                elif hasattr(data, 'request_id'):
                    request_id = data.request_id
                
                # Process precipitation data to ensure correct format
                processed_precip_data = []
                for precip_item in extracted_precip_data:
                    # Convert to dictionary if it's an object
                    if not isinstance(precip_item, dict) and hasattr(precip_item, '__dict__'):
                        precip_dict = vars(precip_item)
                    else:
                        precip_dict = precip_item if isinstance(precip_item, dict) else {}
                    
                    # Ensure position is properly formatted
                    position = None
                    if isinstance(precip_item, dict) and 'position' in precip_item:
                        position = precip_item['position']
                    elif hasattr(precip_item, 'position'):
                        position = precip_item.position
                    
                    # Convert position to tuple
                    if position is not None:
                        if hasattr(position, 'tolist'):  # numpy array
                            precip_dict['position'] = tuple(position.tolist())
                        elif isinstance(position, (list, tuple)) and len(position) >= 2:
                            precip_dict['position'] = tuple(position)
                        else:
                            precip_dict['position'] = (0.0, 0.0)  # Default position
                    else:
                        precip_dict['position'] = (0.0, 0.0)  # Default position
                    
                    # Ensure required fields have default values if missing
                    if 'type' not in precip_dict:
                        precip_dict['type'] = 'rain'  # Default type
                    if 'rate' not in precip_dict:
                        precip_dict['rate'] = 20.0  # Default rate
                    if 'intensity' not in precip_dict:
                        precip_dict['intensity'] = 0.5  # Default intensity
                    if 'show_values' not in precip_dict:
                        precip_dict['show_values'] = True  # Default to showing values
                    
                    # Add unique ID if missing
                    if 'id' not in precip_dict:
                        precip_dict['id'] = f"precip_{str(uuid.uuid4())[:8]}"
                    
                    processed_precip_data.append(precip_dict)
                
                # Store the processed data using the coordinator
                try:
                    logger.info(f"[WEATHER_HOLO] Storing {len(processed_precip_data)} precipitation data points")
                    stored_count = self._data_coordinator.store_data('precipitation', processed_precip_data, request_id)
                    logger.info(f"[WEATHER_HOLO] Stored {stored_count} precipitation data points")
                    
                    # Get the data back from the coordinator
                    return self._data_coordinator.get_data('precipitation', use_backup=False)
                except Exception as e:
                    logger.error(f"[WEATHER_HOLO] Error storing precipitation data: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Fallback to direct return
                    return processed_precip_data
            
            # If no precipitation data found, return empty list
            return []
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error processing precipitation data: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def _process_vil_data(self, data: Any) -> List[Dict[str, Any]]:
        """Process VIL (Vertically Integrated Liquid) data for holographic display.
        
        Args:
            data: VIL data in various formats
            
        Returns:
            Processed VIL data list
        """
        try:
            # Store current timestamp for data persistence
            current_time = time.time()
            
            # Extract VIL data from various formats
            extracted_vil_data = []  # Store extracted data here first
            vil_data_found = False
            
            # Format 1: Direct list of VIL data points
            if isinstance(data, list) and len(data) > 0:
                logger.info(f"[WEATHER_HOLO] Found list of {len(data)} VIL data points")
                extracted_vil_data = data
                vil_data_found = True
            
            # Format 2: Data object with 'data' attribute containing VIL list
            elif hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
                logger.info(f"[WEATHER_HOLO] Extracting {len(data.data)} VIL points from data.data")
                extracted_vil_data = data.data
                vil_data_found = True
                
            # Format 3: Command type format
            elif hasattr(data, 'command_type') and isinstance(data.command_type, dict) and data.command_type.get('type') == 'vil':
                logger.info("[WEATHER_HOLO] Found command_type VIL format")
                
                # Special handling for this specific format
                if hasattr(data, 'data') and isinstance(data.data, list):
                    logger.info(f"[WEATHER_HOLO] Found {len(data.data)} VIL data points in command_type format")
                    extracted_vil_data = data.data
                else:
                    logger.info("[WEATHER_HOLO] Using single data item from command_type format")
                    extracted_vil_data = [data]
                vil_data_found = True
                
            # Format 4: Dictionary with additional_info.weather_data.vil_data
            elif isinstance(data, dict) and 'additional_info' in data:
                logger.info("[WEATHER_HOLO] Found dictionary with additional_info")
                additional_info = data['additional_info']
                
                if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                    weather_data = additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info dict: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                        vil_data_list = weather_data['vil_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(vil_data_list)} VIL points in weather_data dict")
                        extracted_vil_data = vil_data_list
                        vil_data_found = True
            
            # Format 5: Object with additional_info attribute containing weather_data
            elif hasattr(data, 'additional_info') and data.additional_info is not None:
                logger.info("[WEATHER_HOLO] Found object with additional_info attribute")
                
                # Handle both dictionary and object attribute access
                if isinstance(data.additional_info, dict) and 'weather_data' in data.additional_info:
                    weather_data = data.additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                        vil_data_list = weather_data['vil_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(vil_data_list)} VIL points in weather_data")
                        extracted_vil_data = vil_data_list
                        vil_data_found = True
                elif hasattr(data.additional_info, 'weather_data'):
                    weather_data = data.additional_info.weather_data
                    logger.info(f"[WEATHER_HOLO] Found weather_data attribute in additional_info")
                    
                    if hasattr(weather_data, 'vil_data') and isinstance(weather_data.vil_data, list):
                        vil_data_list = weather_data.vil_data
                        logger.info(f"[WEATHER_HOLO] Found {len(vil_data_list)} VIL points in weather_data attribute")
                        extracted_vil_data = vil_data_list
                        vil_data_found = True
            
            # Format 6: Object with weather_data attribute
            elif hasattr(data, 'weather_data') and data.weather_data is not None:
                logger.info("[WEATHER_HOLO] Found object with weather_data attribute")
                
                if hasattr(data.weather_data, 'vil_data'):
                    logger.info("[WEATHER_HOLO] Found weather_data.vil_data format")
                    extracted_vil_data = data.weather_data.vil_data
                    vil_data_found = True
            
            # If we found VIL data, process and store it
            if vil_data_found and extracted_vil_data:
                # Extract request_id from the data if available
                request_id = None
                if isinstance(data, dict) and 'request_id' in data:
                    request_id = data['request_id']
                elif hasattr(data, 'request_id'):
                    request_id = data.request_id
                
                # Process VIL data to ensure correct format
                processed_vil_data = []
                for vil_item in extracted_vil_data:
                    # Convert to dictionary if it's an object
                    if not isinstance(vil_item, dict) and hasattr(vil_item, '__dict__'):
                        vil_dict = vars(vil_item)
                    else:
                        vil_dict = vil_item if isinstance(vil_item, dict) else {}
                    
                    # Ensure position is properly formatted
                    position = None
                    if isinstance(vil_item, dict) and 'position' in vil_item:
                        position = vil_item['position']
                    elif hasattr(vil_item, 'position'):
                        position = vil_item.position
                    
                    # Convert position to tuple
                    if position is not None:
                        if hasattr(position, 'tolist'):  # numpy array
                            vil_dict['position'] = tuple(position.tolist())
                        elif isinstance(position, (list, tuple)) and len(position) >= 2:
                            vil_dict['position'] = tuple(position)
                        else:
                            vil_dict['position'] = (0.0, 0.0)  # Default position
                    else:
                        vil_dict['position'] = (0.0, 0.0)  # Default position
                    
                    # Ensure required fields have default values if missing
                    if 'value' not in vil_dict:
                        vil_dict['value'] = 20.0  # Default VIL value
                    if 'intensity' not in vil_dict:
                        vil_dict['intensity'] = 0.7  # Default intensity
                    if 'layer_count' not in vil_dict:
                        vil_dict['layer_count'] = 3  # Default layer count
                    if 'show_values' not in vil_dict:
                        vil_dict['show_values'] = True  # Default to showing values
                    
                    # Add unique ID if missing
                    if 'id' not in vil_dict:
                        vil_dict['id'] = f"vil_{str(uuid.uuid4())[:8]}"
                    
                    # Store timestamp for persistence
                    self._vil_data_timestamp[vil_dict['id']] = current_time
                    
                    processed_vil_data.append(vil_dict)
                
                # Update VIL stats
                self._vil_data_stats['received_count'] += 1
                
                # Store the processed data using the coordinator
                try:
                    logger.info(f"[WEATHER_HOLO] Storing {len(processed_vil_data)} VIL data points")
                    stored_count = self._data_coordinator.store_data('vil', processed_vil_data, request_id)
                    logger.info(f"[WEATHER_HOLO] Stored {stored_count} VIL data points")
                    
                    # Update stats
                    self._vil_data_stats['stored_count'] += stored_count
                    
                    # Create backup copy
                    self._vil_data_backup = copy.deepcopy(processed_vil_data)
                    
                    # Get the data back from the coordinator
                    return self._data_coordinator.get_data('vil', use_backup=True)
                except Exception as e:
                    logger.error(f"[WEATHER_HOLO] Error storing VIL data: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Fallback to direct return
                    return processed_vil_data
            
            # If no VIL data found but we have backup, use it
            elif hasattr(self, '_vil_data_backup') and self._vil_data_backup:
                # Filter out expired data points
                current_backup = []
                for vil_item in self._vil_data_backup:
                    vil_id = vil_item.get('id')
                    if vil_id in self._vil_data_timestamp:
                        # Check if data point is still fresh
                        if current_time - self._vil_data_timestamp[vil_id] < self._vil_persist_time:
                            current_backup.append(vil_item)
                
                logger.info(f"[WEATHER_HOLO] Using {len(current_backup)} VIL data points from backup")
                return current_backup
            
            # If no VIL data found and no backup, return empty list
            return []
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error processing VIL data: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def _process_cell_data(self, data: Any) -> List[Dict[str, Any]]:
        """Process cell data for holographic display.
        
        Args:
            data: Cell data in various formats
            
        Returns:
            Processed cell data list
        """
        try:
            # Extract cell data from various formats
            extracted_cell_data = []  # Store extracted data here first
            cell_data_found = False
            
            # Format 1: Direct list of cell data points
            if isinstance(data, list) and len(data) > 0:
                logger.info(f"[WEATHER_HOLO] Found list of {len(data)} cell data points")
                extracted_cell_data = data
                cell_data_found = True
            
            # Format 2: Data object with 'data' attribute containing cell list
            elif hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
                logger.info(f"[WEATHER_HOLO] Extracting {len(data.data)} cell points from data.data")
                extracted_cell_data = data.data
                cell_data_found = True
                
            # Format 3: Dictionary with additional_info.weather_data.cell_data
            elif isinstance(data, dict) and 'additional_info' in data:
                logger.info("[WEATHER_HOLO] Found dictionary with additional_info")
                additional_info = data['additional_info']
                
                if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                    weather_data = additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info dict: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'cell_data' in weather_data and isinstance(weather_data['cell_data'], list):
                        cell_data_list = weather_data['cell_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(cell_data_list)} cell points in weather_data dict")
                        extracted_cell_data = cell_data_list
                        cell_data_found = True
            
            # Format 4: Object with additional_info attribute containing weather_data
            elif hasattr(data, 'additional_info') and data.additional_info is not None:
                logger.info("[WEATHER_HOLO] Found object with additional_info attribute")
                
                # Handle both dictionary and object attribute access
                if isinstance(data.additional_info, dict) and 'weather_data' in data.additional_info:
                    weather_data = data.additional_info['weather_data']
                    logger.info(f"[WEATHER_HOLO] Found weather_data in additional_info: {weather_data}")
                    
                    if isinstance(weather_data, dict) and 'cell_data' in weather_data and isinstance(weather_data['cell_data'], list):
                        cell_data_list = weather_data['cell_data']
                        logger.info(f"[WEATHER_HOLO] Found {len(cell_data_list)} cell points in weather_data")
                        extracted_cell_data = cell_data_list
                        cell_data_found = True
                elif hasattr(data.additional_info, 'weather_data'):
                    weather_data = data.additional_info.weather_data
                    logger.info(f"[WEATHER_HOLO] Found weather_data attribute in additional_info")
                    
                    if hasattr(weather_data, 'cell_data') and isinstance(weather_data.cell_data, list):
                        cell_data_list = weather_data.cell_data
                        logger.info(f"[WEATHER_HOLO] Found {len(cell_data_list)} cell points in weather_data attribute")
                        extracted_cell_data = cell_data_list
                        cell_data_found = True
            
            # If we found cell data, process and store it
            if cell_data_found and extracted_cell_data:
                # Extract request_id from the data if available
                request_id = None
                if isinstance(data, dict) and 'request_id' in data:
                    request_id = data['request_id']
                elif hasattr(data, 'request_id'):
                    request_id = data.request_id
                
                # Process cell data to ensure correct format
                processed_cell_data = []
                for cell_item in extracted_cell_data:
                    # Convert to dictionary if it's an object
                    if not isinstance(cell_item, dict) and hasattr(cell_item, '__dict__'):
                        cell_dict = vars(cell_item)
                    else:
                        cell_dict = cell_item if isinstance(cell_item, dict) else {}
                    
                    # Ensure position is properly formatted
                    position = None
                    if isinstance(cell_item, dict) and 'position' in cell_item:
                        position = cell_item['position']
                    elif hasattr(cell_item, 'position'):
                        position = cell_item.position
                    
                    # Convert position to tuple
                    if position is not None:
                        if hasattr(position, 'tolist'):  # numpy array
                            cell_dict['position'] = tuple(position.tolist())
                        elif isinstance(position, (list, tuple)) and len(position) >= 2:
                            cell_dict['position'] = tuple(position)
                        else:
                            cell_dict['position'] = (0.0, 0.0)  # Default position
                    else:
                        cell_dict['position'] = (0.0, 0.0)  # Default position
                    
                    # Ensure required fields have default values if missing
                    if 'intensity' not in cell_dict:
                        cell_dict['intensity'] = 0.8  # Default intensity
                    if 'movement_direction' not in cell_dict:
                        cell_dict['movement_direction'] = 0.0  # Default direction
                    if 'movement_speed' not in cell_dict:
                        cell_dict['movement_speed'] = 0.0  # Default speed
                    
                    # Add unique ID if missing
                    if 'id' not in cell_dict:
                        cell_dict['id'] = f"cell_{str(uuid.uuid4())[:8]}"
                    
                    processed_cell_data.append(cell_dict)
                
                # Store the processed data using the coordinator
                try:
                    logger.info(f"[WEATHER_HOLO] Storing {len(processed_cell_data)} cell data points")
                    stored_count = self._data_coordinator.store_data('cells', processed_cell_data, request_id)
                    logger.info(f"[WEATHER_HOLO] Stored {stored_count} cell data points")
                    
                    # Get the data back from the coordinator
                    return self._data_coordinator.get_data('cells', use_backup=False)
                except Exception as e:
                    logger.error(f"[WEATHER_HOLO] Error storing cell data: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Fallback to direct return
                    return processed_cell_data
            
            # If no cell data found, return empty list
            return []
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error processing cell data: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def paint_display(self, painter: QPainter):
        """Paint the holographic weather radar display.
        
        This method is called by the BaseDisplay.paintEvent method.
        """
        try:
            # Get the rectangle for the entire widget
            rect = QRectF(0, 0, self.width(), self.height())
            
            # Prepare data for drawing
            data = {
                'precipitation_data': self._precipitation_data,
                'vil_data': self._vil_data,
                'cell_data': self._cell_data,
                'mode': getattr(self, '_current_mode', None)
            }
            
            # Draw the display using the parent class method
            self.draw_display(painter, rect, data)
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in paint_display: {str(e)}")
            logger.error(traceback.format_exc())
            
    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw weather radar elements with holographic effects.
        
        This method overrides the parent class method to add weather-specific visualization.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle area to draw in
            data: Display data dictionary
        """
        try:
            # Call parent method to draw base holographic radar elements
            super().draw_radar_elements(painter, rect, data)
            
            # Get center and radius for radar display
            center_x = rect.width() * 0.5
            center_y = rect.height() * 0.5
            
            # Adjust for side panel if visible
            if hasattr(self, 'side_panel_width') and self.side_panel_width > 0:
                center_x = (rect.width() - self.side_panel_width) * 0.5
            
            center = QPointF(center_x, center_y)
            radius = min(center_x, center_y) * 0.85
            
            # Draw weather-specific elements
            
            # Draw precipitation data if available
            if hasattr(self, '_precipitation_data') and self._precipitation_data:
                if hasattr(self, '_use_texture_rendering') and self._use_texture_rendering and hasattr(self, '_rain_texture'):
                    # Use texture-based rendering if available
                    self._draw_precipitation_with_texture(painter)
                else:
                    # Fall back to basic rendering
                    self._draw_precipitation_data(painter)
            
            # Draw VIL data if available and enabled
            if hasattr(self, '_vil_data') and self._vil_data and hasattr(self, '_visual_elements') and self._visual_elements.get('show_vil', True):
                if hasattr(self, '_use_texture_rendering') and self._use_texture_rendering and hasattr(self, '_cloud_texture'):
                    # Use texture-based rendering if available
                    self._draw_vil_with_texture(painter)
                else:
                    # Fall back to basic rendering
                    self._draw_vil_data(painter)
            
            # Draw cell data if available
            if hasattr(self, '_cell_data') and self._cell_data:
                self._draw_cell_data(painter)
            
            # Draw particles if enabled
            if hasattr(self, '_use_enhanced_particles') and self._use_enhanced_particles:
                self._draw_particles(painter)
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing radar elements: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_precipitation_data(self, painter: QPainter) -> None:
        """Draw precipitation data with realistic visualization.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Draw each precipitation data point
            for precip_data in self._precipitation_data:
                # Get position
                position = precip_data.get('position', (0, 0))
                x, y = position
                
                # Convert to screen coordinates
                screen_x = center_x + x
                screen_y = center_y + y
                
                # Get precipitation type and intensity
                precip_type = precip_data.get('type', 'rain')
                intensity = precip_data.get('intensity', 0.5)
                
                # Get color based on precipitation type
                color = self._precipitation_colors.get(precip_type, self._precipitation_colors[None])
                
                # Create radial gradient for realistic precipitation
                gradient = QRadialGradient(screen_x, screen_y, 20.0 * intensity)
                gradient.setColorAt(0, color)
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                
                # Draw precipitation with gradient
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Apply rotation for animation effect
                painter.save()
                painter.translate(screen_x, screen_y)
                painter.rotate(self._weather_rotation)
                
                # Draw multiple layers for 3D effect
                for layer in range(self._weather_layer_count):
                    # Calculate layer scale based on perspective
                    layer_scale = 1.0 - (layer * self._weather_perspective)
                    
                    # Calculate layer offset for 3D effect
                    layer_offset = layer * self._weather_layer_separation
                    
                    # Draw precipitation shape based on type
                    if precip_type == 'rain':
                        # Draw elongated ellipse for rain
                        painter.drawEllipse(QPointF(0, 0), 15.0 * intensity * layer_scale, 25.0 * intensity * layer_scale)
                    elif precip_type == 'snow':
                        # Draw hexagon for snow
                        for i in range(6):
                            angle1 = i * 60.0
                            angle2 = (i + 1) * 60.0
                            x1 = 20.0 * intensity * layer_scale * math.cos(math.radians(angle1))
                            y1 = 20.0 * intensity * layer_scale * math.sin(math.radians(angle1))
                            x2 = 20.0 * intensity * layer_scale * math.cos(math.radians(angle2))
                            y2 = 20.0 * intensity * layer_scale * math.sin(math.radians(angle2))
                            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                    elif precip_type == 'hail':
                        # Draw multiple small circles for hail
                        for i in range(5):
                            hail_x = (i % 3 - 1) * 10.0 * layer_scale
                            hail_y = (i // 3 - 1) * 10.0 * layer_scale
                            painter.drawEllipse(QPointF(hail_x, hail_y), 5.0 * intensity * layer_scale, 5.0 * intensity * layer_scale)
                    else:
                        # Default to circle for other types
                        painter.drawEllipse(QPointF(0, 0), 20.0 * intensity * layer_scale, 20.0 * intensity * layer_scale)
                
                # Restore painter state
                painter.restore()
                
                # Draw value if enabled
                if precip_data.get('show_values', True) and self._visual_elements.get('show_precipitation_values', True):
                    rate = precip_data.get('rate', 0.0)
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.setFont(QFont('Arial', 8))
                    painter.drawText(QRectF(screen_x - 15, screen_y + 25, 30, 15), Qt.AlignmentFlag.AlignCenter, f"{rate:.1f}")
                    
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing precipitation data: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_vil_data(self, painter: QPainter) -> None:
        """Draw VIL data with realistic visualization.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Update VIL stats
            self._vil_data_stats['drawn_count'] = len(self._vil_data)
            
            # Draw each VIL data point
            for vil_data in self._vil_data:
                # Get position
                position = vil_data.get('position', (0, 0))
                x, y = position
                
                # Convert to screen coordinates
                screen_x = center_x + x
                screen_y = center_y + y
                
                # Get VIL value and intensity
                vil_value = vil_data.get('value', 0.0)
                intensity = vil_data.get('intensity', 0.7)
                
                # Determine VIL category based on value
                if vil_value >= 50.0:
                    vil_category = 'HIGH'
                elif vil_value >= 30.0:
                    vil_category = 'MEDIUM'
                elif vil_value >= 10.0:
                    vil_category = 'LOW'
                else:
                    vil_category = 'MINIMAL'
                
                # Get color based on VIL category
                color = self._vil_colors.get(vil_category, self._vil_colors['LOW'])
                
                # Create radial gradient for realistic VIL
                gradient = QRadialGradient(screen_x, screen_y, 30.0 * intensity)
                gradient.setColorAt(0, color)
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                
                # Draw VIL with gradient
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Apply rotation and pulse for animation effect
                painter.save()
                painter.translate(screen_x, screen_y)
                painter.rotate(-self._weather_rotation * 0.5)  # Rotate in opposite direction
                
                # Apply pulse effect
                pulse_scale = 1.0 + 0.2 * self._weather_pulse_factor
                
                # Draw multiple layers for 3D effect
                layer_count = vil_data.get('layer_count', self._weather_layer_count)
                for layer in range(layer_count):
                    # Calculate layer scale based on perspective
                    layer_scale = 1.0 - (layer * self._weather_perspective)
                    
                    # Calculate layer offset for 3D effect
                    layer_offset = layer * self._weather_layer_separation
                    
                    # Draw VIL shape (cloud-like)
                    painter.save()
                    painter.scale(pulse_scale * layer_scale, pulse_scale * layer_scale)
                    
                    # Draw cloud-like shape for VIL
                    path = QPainterPath()
                    path.moveTo(0, 0)
                    
                    # Draw cloud-like shape with multiple arcs
                    for i in range(8):
                        angle = i * 45.0
                        radius = 20.0 + 5.0 * math.sin(angle * 2.0)
                        x = radius * math.cos(math.radians(angle))
                        y = radius * math.sin(math.radians(angle))
                        path.lineTo(x, y)
                    
                    path.closeSubpath()
                    painter.drawPath(path)
                    
                    painter.restore()
                
                # Restore painter state
                painter.restore()
                
                # Draw value if enabled
                if vil_data.get('show_values', True) and self._visual_elements.get('show_vil_values', True):
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.setFont(QFont('Arial', 8))
                    painter.drawText(QRectF(screen_x - 15, screen_y + 35, 30, 15), Qt.AlignmentFlag.AlignCenter, f"{vil_value:.1f}")
                    
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing VIL data: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_cell_data(self, painter: QPainter) -> None:
        """Draw cell data with realistic visualization.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Draw each cell data point
            for cell_data in self._cell_data:
                # Get position
                position = cell_data.get('position', (0, 0))
                x, y = position
                
                # Convert to screen coordinates
                screen_x = center_x + x
                screen_y = center_y + y
                
                # Get cell intensity and movement
                intensity = cell_data.get('intensity', 0.8)
                movement_direction = cell_data.get('movement_direction', 0.0)
                movement_speed = cell_data.get('movement_speed', 0.0)
                
                # Draw cell with realistic visualization
                painter.save()
                painter.translate(screen_x, screen_y)
                
                # Draw cell outline
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(0, 0), 30.0 * intensity, 30.0 * intensity)
                
                # Draw movement vector if speed > 0
                if movement_speed > 0:
                    # Calculate vector endpoint
                    vector_length = movement_speed * 0.5  # Scale factor
                    end_x = vector_length * math.sin(math.radians(movement_direction))
                    end_y = -vector_length * math.cos(math.radians(movement_direction))
                    
                    # Draw movement vector
                    painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
                    painter.drawLine(QPointF(0, 0), QPointF(end_x, end_y))
                    
                    # Draw arrowhead
                    painter.save()
                    painter.translate(end_x, end_y)
                    painter.rotate(movement_direction)
                    
                    # Draw arrowhead
                    arrow_path = QPainterPath()
                    arrow_path.moveTo(0, 0)
                    arrow_path.lineTo(-5, -10)
                    arrow_path.lineTo(5, -10)
                    arrow_path.closeSubpath()
                    
                    painter.setBrush(QBrush(Qt.GlobalColor.yellow))
                    painter.drawPath(arrow_path)
                    
                    painter.restore()
                
                # Restore painter state
                painter.restore()
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing cell data: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _handle_animation_update(self, animation_state: Dict[str, Any]) -> None:
        """Handle animation updates from the animation controller.
        
        Args:
            animation_state: Dictionary with animation state including delta_time
        """
        try:
            # Extract delta_time from animation_state
            if isinstance(animation_state, dict) and 'dt' in animation_state:
                delta_time = animation_state['dt']
            else:
                # Default to 60 FPS if animation_state is invalid
                delta_time = 0.016  # ~60 FPS as a safe default
                
            # Ensure delta_time is a float
            if not isinstance(delta_time, float):
                # If it's not a float, convert it or use default
                try:
                    delta_time = float(delta_time)
                except (ValueError, TypeError):
                    delta_time = 0.016  # ~60 FPS as a safe default
            
            # Ensure _weather_rotation_speed is a float, not a dict
            rotation_speed = 3.0  # Default value
            if not isinstance(self._weather_rotation_speed, (int, float)):
                # Store the correct value for future use
                self._weather_rotation_speed = rotation_speed
            else:
                rotation_speed = self._weather_rotation_speed
                
            self._weather_rotation += rotation_speed * delta_time
            if self._weather_rotation >= 360.0:
                self._weather_rotation -= 360.0
                
            # Update pulse effect
            self._weather_pulse_factor = 0.5 + 0.5 * math.sin(time.time() * self._weather_pulse_speed)
            
            # Update weather evolution
            self._update_weather_evolution(delta_time)
            
            # Update particle systems
            current_time = time.time()
            if current_time - self._last_particle_update > 0.05:  # 20 FPS max for particle updates
                self._last_particle_update = current_time
                self._update_particles(delta_time)
                
                # Check if it's time to emit new particles
                if current_time - self._last_emission_time > 1.0 / self._particle_emission_rate:
                    self._last_emission_time = current_time
                    self._emit_particles()
                
            # Force display update
            self.update()  # Use update() instead of repaint() for compatibility
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error handling animation update: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _update_weather_evolution(self, delta_time: float) -> None:
        """Update weather system evolution over time.
        
        Args:
            delta_time: Time since last update in seconds
        """
        try:
            # Update evolution time
            self._weather_evolution_time += delta_time
            
            # Apply subtle changes to precipitation and VIL data based on time
            evolution_factor = math.sin(self._weather_evolution_time * 0.1) * 0.2  # -0.2 to 0.2 range
            
            # Apply evolution to precipitation data
            for precip_data in self._precipitation_data:
                # Get original position
                position = precip_data.get('position', (0, 0))
                x, y = position
                
                # Apply subtle drift based on evolution time
                drift_x = math.sin(self._weather_evolution_time * 0.2 + x * 0.1) * 0.5
                drift_y = math.cos(self._weather_evolution_time * 0.15 + y * 0.1) * 0.5
                
                # Update position with drift
                new_x = x + drift_x * delta_time
                new_y = y + drift_y * delta_time
                
                # Store updated position
                precip_data['position'] = (new_x, new_y)
                
                # Apply subtle intensity changes
                intensity = precip_data.get('intensity', 0.5)
                intensity_change = evolution_factor * 0.05  # Small change
                new_intensity = max(0.1, min(1.0, intensity + intensity_change))
                precip_data['intensity'] = new_intensity
            
            # Apply evolution to VIL data
            for vil_data in self._vil_data:
                # Get original position
                position = vil_data.get('position', (0, 0))
                x, y = position
                
                # Apply subtle drift based on evolution time (slower than precipitation)
                drift_x = math.sin(self._weather_evolution_time * 0.1 + x * 0.05) * 0.3
                drift_y = math.cos(self._weather_evolution_time * 0.08 + y * 0.05) * 0.3
                
                # Update position with drift
                new_x = x + drift_x * delta_time
                new_y = y + drift_y * delta_time
                
                # Store updated position
                vil_data['position'] = (new_x, new_y)
                
                # Apply subtle value changes
                value = vil_data.get('value', 20.0)
                value_change = evolution_factor * value * 0.02  # Small percentage change
                new_value = max(5.0, min(60.0, value + value_change))
                vil_data['value'] = new_value
                
                # Apply subtle intensity changes
                intensity = vil_data.get('intensity', 0.7)
                intensity_change = evolution_factor * 0.03  # Small change
                new_intensity = max(0.3, min(1.0, intensity + intensity_change))
                vil_data['intensity'] = new_intensity
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error updating weather evolution: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _emit_particles(self) -> None:
        """Emit new particles for precipitation, VIL, and cell data."""
        try:
            # Emit particles for precipitation data
            for precip_data in self._precipitation_data:
                precip_id = precip_data.get('id')
                if not precip_id:
                    continue
                
                # Check if we already have particles for this precipitation
                if precip_id not in self._weather_particles['precipitation']:
                    # Create new particle list
                    self._weather_particles['precipitation'][precip_id] = []
                
                # Get current particle count
                current_count = len(self._weather_particles['precipitation'][precip_id])
                
                # Calculate how many particles to emit based on intensity
                intensity = precip_data.get('intensity', 0.5)
                target_count = int(self._max_particles_per_system * intensity)
                
                # Emit particles if below target count
                if current_count < target_count:
                    # Calculate how many to emit this frame
                    emit_count = min(5, target_count - current_count)  # Max 5 per frame for performance
                    
                    # Generate new particles
                    new_particles = self._generate_precipitation_particles(precip_data, emit_count)
                    
                    # Add to particle list
                    self._weather_particles['precipitation'][precip_id].extend(new_particles)
            
            # Emit particles for VIL data
            for vil_data in self._vil_data:
                vil_id = vil_data.get('id')
                if not vil_id:
                    continue
                
                # Check if we already have particles for this VIL
                if vil_id not in self._weather_particles['vil']:
                    # Create new particle list
                    self._weather_particles['vil'][vil_id] = []
                
                # Get current particle count
                current_count = len(self._weather_particles['vil'][vil_id])
                
                # Calculate how many particles to emit based on value and intensity
                value = vil_data.get('value', 20.0)
                intensity = vil_data.get('intensity', 0.7)
                target_count = int(self._max_particles_per_system * (value / 60.0) * intensity)
                
                # Emit particles if below target count
                if current_count < target_count:
                    # Calculate how many to emit this frame
                    emit_count = min(3, target_count - current_count)  # Max 3 per frame for performance
                    
                    # Generate new particles
                    new_particles = self._generate_vil_particles(vil_data, emit_count)
                    
                    # Add to particle list
                    self._weather_particles['vil'][vil_id].extend(new_particles)
            
            # Emit particles for cell data
            if 'cells' not in self._weather_particles:
                self._weather_particles['cells'] = {}
                
            for cell_data in self._cell_data:
                cell_id = cell_data.get('id')
                if not cell_id:
                    continue
                
                # Check if we already have particles for this cell
                if cell_id not in self._weather_particles['cells']:
                    # Create new particle list
                    self._weather_particles['cells'][cell_id] = []
                
                # Get current particle count
                current_count = len(self._weather_particles['cells'][cell_id])
                
                # Calculate how many particles to emit based on intensity
                intensity = cell_data.get('intensity', 0.8)
                movement_speed = cell_data.get('movement_speed', 0.0)
                
                # More particles for faster-moving cells
                speed_factor = 1.0 + (movement_speed / 10.0)
                target_count = int(self._max_particles_per_system * intensity * speed_factor)
                
                # Emit particles if below target count
                if current_count < target_count:
                    # Calculate how many to emit this frame
                    emit_count = min(4, target_count - current_count)  # Max 4 per frame for performance
                    
                    # Generate new particles
                    new_particles = self._generate_cell_particles(cell_data, emit_count)
                    
                    # Add to particle list
                    self._weather_particles['cells'][cell_id].extend(new_particles)
                    
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error emitting particles: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _update_particles(self, delta_time: float) -> None:
        """Update particle systems for precipitation, VIL, and cell data.
        
        Args:
            delta_time: Time since last update in seconds
        """
        try:
            # Update precipitation particles
            if 'precipitation' in self._weather_particles:
                for precip_id, particles in self._weather_particles['precipitation'].items():
                    for particle in particles:
                        # Apply gravity and wind
                        particle['velocity'][1] += 9.8 * delta_time  # Gravity
                        particle['position'][0] += particle['velocity'][0] * delta_time
                        particle['position'][1] += particle['velocity'][1] * delta_time
                        
                        # Apply rotation
                        particle['rotation'] += particle['rotation_speed'] * delta_time
                        
                        # Update lifetime
                        particle['lifetime'] -= delta_time
                    
                    # Filter out expired particles
                    self._weather_particles['precipitation'][precip_id] = [
                        p for p in particles if p['lifetime'] > 0.0
                    ]
                    
            # Update VIL particles
            if 'vil' in self._weather_particles:
                for vil_id, particles in self._weather_particles['vil'].items():
                    for particle in particles:
                        # Apply upward movement for VIL (rising air)
                        particle['velocity'][1] -= 2.0 * delta_time  # Upward force
                        particle['position'][0] += particle['velocity'][0] * delta_time
                        particle['position'][1] += particle['velocity'][1] * delta_time
                        
                        # Apply rotation and scale pulsing
                        particle['rotation'] += particle['rotation_speed'] * delta_time
                        
                        # Apply pulse effect if available
                        if 'pulse_factor' in particle and 'pulse_speed' in particle:
                            pulse_phase = time.time() * particle['pulse_speed']
                            particle['pulse_factor'] = 1.0 + 0.2 * math.sin(pulse_phase)
                        
                        # Update lifetime
                        particle['lifetime'] -= delta_time
                    
                    # Filter out expired particles
                    self._weather_particles['vil'][vil_id] = [
                        p for p in particles if p['lifetime'] > 0.0
                    ]
            
            # Update cell particles
            if 'cells' in self._weather_particles:
                for cell_id, particles in self._weather_particles['cells'].items():
                    for particle in particles:
                        # Get spiral motion parameters
                        spiral_radius = particle.get('spiral_radius', 0.0)
                        spiral_speed = particle.get('spiral_speed', 0.0)
                        spiral_phase = particle.get('spiral_phase', 0.0)
                        
                        # Update spiral phase
                        particle['spiral_phase'] = spiral_phase + spiral_speed * delta_time
                        
                        # Calculate spiral motion offset
                        spiral_x = spiral_radius * math.cos(particle['spiral_phase'])
                        spiral_y = spiral_radius * math.sin(particle['spiral_phase'])
                        
                        # Apply base velocity and spiral motion
                        particle['position'][0] += particle['velocity'][0] * delta_time + spiral_x * delta_time
                        particle['position'][1] += particle['velocity'][1] * delta_time + spiral_y * delta_time
                        
                        # Apply rotation
                        particle['rotation'] += particle['rotation_speed'] * delta_time
                        
                        # Update lifetime
                        particle['lifetime'] -= delta_time
                    
                    # Filter out expired particles
                    self._weather_particles['cells'][cell_id] = [
                        p for p in particles if p['lifetime'] > 0.0
                    ]
            
            # Remove empty particle lists
            for data_type in list(self._weather_particles.keys()):
                for data_id in list(self._weather_particles[data_type].keys()):
                    if not self._weather_particles[data_type][data_id]:
                        del self._weather_particles[data_type][data_id]
                        
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error updating particles: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _initialize_textures(self):
        """Initialize textures for weather visualization."""
        try:
            # Create cloud texture
            self._cloud_texture = self._generate_cloud_texture()
            
            # Create precipitation textures
            self._rain_texture = self._generate_rain_texture()
            self._snow_texture = self._generate_snow_texture()
            self._hail_texture = self._generate_hail_texture()
            
            # Create noise texture for turbulence effects
            self._noise_texture = self._generate_noise_texture()
            
            logger.info("[WEATHER_HOLO] Initialized weather textures")
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error initializing textures: {str(e)}")
            logger.error(traceback.format_exc())
            # Set flag to disable texture rendering
            self._use_texture_rendering = False
    
    def _generate_cloud_texture(self):
        """Generate a cloud-like texture using multiple radial gradients."""
        # Create a QImage for the texture
        texture_size = 256
        image = QImage(texture_size, texture_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Generate cloud-like texture using multiple radial gradients
        for _ in range(15):
            # Random position and size
            x = random.randint(0, texture_size)
            y = random.randint(0, texture_size)
            radius = random.randint(30, 80)
            
            # Create radial gradient
            gradient = QRadialGradient(x, y, radius)
            gradient.setColorAt(0, QColor(255, 255, 255, random.randint(100, 180)))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            
            # Draw gradient
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x, y), radius, radius)
        
        painter.end()
        return image
    
    def _generate_rain_texture(self):
        """Generate a texture for rain visualization."""
        # Create a QImage for the texture
        texture_size = 128
        image = QImage(texture_size, texture_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw rain streaks
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        for _ in range(50):
            x = random.randint(0, texture_size)
            y = random.randint(0, texture_size)
            length = random.randint(10, 30)
            painter.drawLine(x, y, x, y + length)
        
        painter.end()
        return image
    
    def _generate_snow_texture(self):
        """Generate a texture for snow visualization."""
        # Create a QImage for the texture
        texture_size = 128
        image = QImage(texture_size, texture_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw snowflakes
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.setPen(Qt.PenStyle.NoPen)
        
        for _ in range(40):
            x = random.randint(0, texture_size)
            y = random.randint(0, texture_size)
            size = random.randint(2, 6)
            
            # Draw a snowflake (simple hexagon)
            for i in range(3):
                angle = i * 60.0
                x1 = x + size * math.cos(math.radians(angle))
                y1 = y + size * math.sin(math.radians(angle))
                x2 = x + size * math.cos(math.radians(angle + 180))
                y2 = y + size * math.sin(math.radians(angle + 180))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        painter.end()
        return image
    
    def _generate_hail_texture(self):
        """Generate a texture for hail visualization."""
        # Create a QImage for the texture
        texture_size = 128
        image = QImage(texture_size, texture_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw hail particles
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(QPen(QColor(200, 200, 200, 150), 1))
        
        for _ in range(30):
            x = random.randint(0, texture_size)
            y = random.randint(0, texture_size)
            size = random.randint(3, 8)
            painter.drawEllipse(QPointF(x, y), size, size)
        
        painter.end()
        return image
    
    def _generate_noise_texture(self):
        """Generate a noise texture for turbulence effects."""
        # Create a QImage for the texture
        texture_size = 256
        image = QImage(texture_size, texture_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the image
        painter = QPainter(image)
        
        # Generate Perlin-like noise
        for y in range(texture_size):
            for x in range(texture_size):
                # Simple noise function
                nx = x / texture_size
                ny = y / texture_size
                
                # Combine multiple frequencies
                value = 0.0
                value += math.sin(nx * 10) * math.sin(ny * 10) * 0.5
                value += math.sin(nx * 20 + 0.5) * math.sin(ny * 20 + 0.5) * 0.25
                value += math.sin(nx * 40 + 1.0) * math.sin(ny * 40 + 1.0) * 0.125
                
                # Normalize to 0-1 range
                value = (value + 1.0) * 0.5
                
                # Convert to grayscale color
                gray = int(value * 255)
                color = QColor(gray, gray, gray, 255)
                
                # Set pixel
                image.setPixelColor(x, y, color)
        
        painter.end()
        return image
    
    def _generate_precipitation_particles(self, precip_data, count=None):
        """Generate particles for precipitation data based on type and intensity.
        
        Args:
            precip_data: Precipitation data dictionary
            count: Optional count override, otherwise calculated from intensity
            
        Returns:
            List of particle dictionaries
        """
        try:
            # Get precipitation properties
            position = precip_data.get('position', (0, 0))
            precip_type = precip_data.get('type', 'rain')
            intensity = precip_data.get('intensity', 0.5)
            precip_id = precip_data.get('id', f"precip_{str(uuid.uuid4())[:8]}")
            
            # Get particle settings for this precipitation type
            settings = self._particle_settings.get(precip_type, self._particle_settings['default'])
            
            # Calculate number of particles based on intensity if not specified
            if count is None:
                count = int(20 * intensity)
                # Limit particle count for performance
                count = min(count, self._max_particles_per_system)
            
            # Create particles with type-specific behavior
            particles = []
            for _ in range(count):
                # Random offset within precipitation area
                radius = 15.0 * intensity
                angle = random.uniform(0, 2 * math.pi)
                offset_x = radius * math.cos(angle) * random.uniform(0.3, 1.0)
                offset_y = radius * math.sin(angle) * random.uniform(0.3, 1.0)
                
                # Get velocity range from settings
                vel_x_min, vel_x_max, vel_y_min, vel_y_max = settings['velocity_range']
                
                # Create particle with type-specific properties
                particle = {
                    'position': [position[0] + offset_x, position[1] + offset_y],
                    'velocity': [
                        random.uniform(vel_x_min, vel_x_max),
                        random.uniform(vel_y_min, vel_y_max)
                    ],
                    'size': random.uniform(*settings['size_range']),
                    'lifetime': random.uniform(*settings['lifetime_range']),
                    'max_lifetime': random.uniform(*settings['lifetime_range']),  # Store original lifetime
                    'type': precip_type,
                    'shape': settings['shape'],
                    'aspect_ratio': settings['aspect_ratio'],
                    'opacity': random.uniform(0.7, 1.0) * settings['color_factor'],
                    'z_depth': random.uniform(0.0, 1.0),  # For 3D sorting
                    'rotation': random.uniform(0, 360),
                    'rotation_speed': random.uniform(-20, 20),
                    'precip_id': precip_id
                }
                
                particles.append(particle)
            
            return particles
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error generating precipitation particles: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def _generate_vil_particles(self, vil_data, count=None):
        """Generate cloud-like particles for VIL data.
        
        Args:
            vil_data: VIL data dictionary
            count: Optional count override, otherwise calculated from value
            
        Returns:
            List of particle dictionaries
        """
        try:
            # Get VIL properties
            position = vil_data.get('position', (0, 0))
            vil_value = vil_data.get('value', 20.0)
            intensity = vil_data.get('intensity', 0.7)
            vil_id = vil_data.get('id', f"vil_{str(uuid.uuid4())[:8]}")
            
            # Determine VIL category and color
            if vil_value >= 50.0:
                vil_category = 'HIGH'
            elif vil_value >= 30.0:
                vil_category = 'MEDIUM'
            elif vil_value >= 10.0:
                vil_category = 'LOW'
            else:
                vil_category = 'MINIMAL'
            
            # Calculate number of particles based on VIL value if not specified
            if count is None:
                count = int(10 + vil_value / 5)
                # Limit particle count for performance
                count = min(count, self._max_particles_per_system)
            
            # Create cloud-like particles
            particles = []
            for _ in range(count):
                # Random offset within VIL area
                radius = 25.0 * intensity
                angle = random.uniform(0, 2 * math.pi)
                offset_x = radius * math.cos(angle) * random.uniform(0.3, 1.0)
                offset_y = radius * math.sin(angle) * random.uniform(0.3, 1.0)
                
                # Cloud particles move slowly with some upward drift
                particle = {
                    'position': [position[0] + offset_x, position[1] + offset_y],
                    'velocity': [
                        random.uniform(-2, 2),
                        random.uniform(-5, -1)  # Upward drift
                    ],
                    'size': random.uniform(5, 15) * (0.5 + intensity * 0.5),
                    'lifetime': random.uniform(2.0, 5.0),
                    'max_lifetime': random.uniform(2.0, 5.0),
                    'type': 'cloud',
                    'category': vil_category,
                    'shape': 'cloud',
                    'opacity': random.uniform(0.6, 0.9),
                    'z_depth': random.uniform(0.0, 1.0),
                    'rotation': random.uniform(0, 360),
                    'rotation_speed': random.uniform(-10, 10),
                    'pulse_factor': random.uniform(0.8, 1.2),
                    'pulse_speed': random.uniform(0.5, 1.5),
                    'vil_id': vil_id
                }
                
                particles.append(particle)
            
            return particles
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error generating VIL particles: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def _generate_cell_particles(self, cell_data, count=None):
        """Generate particles for weather cell visualization.
        
        Args:
            cell_data: Cell data dictionary
            count: Optional count override, otherwise calculated from intensity
            
        Returns:
            List of particle dictionaries
        """
        try:
            # Get cell properties
            position = cell_data.get('position', (0, 0))
            intensity = cell_data.get('intensity', 0.8)
            movement_direction = cell_data.get('movement_direction', 0.0)
            movement_speed = cell_data.get('movement_speed', 0.0)
            cell_id = cell_data.get('id', f"cell_{str(uuid.uuid4())[:8]}")
            
            # Calculate number of particles based on intensity if not specified
            if count is None:
                count = int(15 * intensity)
                # Limit particle count for performance
                count = min(count, self._max_particles_per_system)
            
            # Create cell particles with movement-based behavior
            particles = []
            for _ in range(count):
                # Random offset within cell area
                radius = 25.0 * intensity * random.uniform(0.3, 1.0)
                angle = random.uniform(0, 2 * math.pi)
                offset_x = radius * math.cos(angle)
                offset_y = radius * math.sin(angle)
                
                # Calculate particle velocity based on cell movement
                # Convert movement direction to radians
                movement_rad = math.radians(movement_direction)
                
                # Base velocity components from movement direction and speed
                base_vel_x = math.sin(movement_rad) * movement_speed * 0.2
                base_vel_y = -math.cos(movement_rad) * movement_speed * 0.2  # Negative for upward movement
                
                # Add random variation
                vel_x = base_vel_x + random.uniform(-2, 2)
                vel_y = base_vel_y + random.uniform(-2, 2)
                
                # Create particle with cell-specific properties
                particle = {
                    'position': [position[0] + offset_x, position[1] + offset_y],
                    'velocity': [vel_x, vel_y],
                    'size': random.uniform(3, 8) * intensity,
                    'lifetime': random.uniform(1.0, 3.0),
                    'max_lifetime': random.uniform(1.0, 3.0),
                    'type': 'cell',
                    'shape': 'circle',
                    'opacity': random.uniform(0.5, 0.9),
                    'z_depth': random.uniform(0.0, 1.0),
                    'rotation': random.uniform(0, 360),
                    'rotation_speed': random.uniform(-15, 15),
                    'color_shift': random.uniform(0.8, 1.2),  # For color variation
                    'cell_id': cell_id
                }
                
                # Add spiral motion parameters for more dynamic movement
                particle['spiral_radius'] = random.uniform(5, 15) * intensity
                particle['spiral_speed'] = random.uniform(0.5, 2.0)
                particle['spiral_phase'] = random.uniform(0, 2 * math.pi)
                
                particles.append(particle)
            
            return particles
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error generating cell particles: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def _draw_particles(self, painter: QPainter) -> None:
        """Draw all weather particles with proper depth sorting.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Collect all particles for depth sorting
            all_particles = []
            
            # Add precipitation particles
            if 'precipitation' in self._weather_particles:
                for particles in self._weather_particles['precipitation'].values():
                    all_particles.extend(particles)
            
            # Add VIL particles
            if 'vil' in self._weather_particles:
                for particles in self._weather_particles['vil'].values():
                    all_particles.extend(particles)
            
            # Add cell particles
            if 'cells' in self._weather_particles:
                for particles in self._weather_particles['cells'].values():
                    all_particles.extend(particles)
            
            # Sort particles by z_depth (back to front)
            all_particles.sort(key=lambda p: p.get('z_depth', 0.0))
            
            # Draw each particle
            for particle in all_particles:
                # Get particle properties
                pos_x, pos_y = particle.get('position', [0, 0])
                screen_x = center_x + pos_x
                screen_y = center_y + pos_y
                size = particle.get('size', 2.0)
                opacity = particle.get('opacity', 0.8)
                rotation = particle.get('rotation', 0.0)
                
                # Apply pulse factor for VIL particles
                if 'pulse_factor' in particle:
                    size *= particle.get('pulse_factor', 1.0)
                
                # Get color based on particle type
                if particle.get('type') == 'cloud':
                    # VIL particle
                    category = particle.get('category', 'LOW')
                    color = self._vil_colors.get(category, self._vil_colors['LOW'])
                elif particle.get('type') == 'cell':
                    # Cell particle - use yellow color with color shift
                    color_shift = particle.get('color_shift', 1.0)
                    color = QColor(
                        min(255, int(255 * color_shift)),  # Red component
                        min(255, int(255 * color_shift)),  # Green component
                        0,                                  # Blue component
                        128                                 # Alpha
                    )
                else:
                    # Precipitation particle
                    precip_type = particle.get('type', 'rain')
                    color = self._precipitation_colors.get(precip_type, self._precipitation_colors[None])
                
                # Adjust color opacity
                color = QColor(color)
                color.setAlphaF(opacity)
                
                # Save painter state
                painter.save()
                
                # Apply translation and rotation
                painter.translate(screen_x, screen_y)
                painter.rotate(rotation)
                
                # Set brush and pen
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Draw particle based on shape
                shape = particle.get('shape', 'circle')
                aspect_ratio = particle.get('aspect_ratio', 1.0)
                
                if shape == 'circle':
                    painter.drawEllipse(QPointF(0, 0), size, size)
                elif shape == 'ellipse':
                    painter.drawEllipse(QPointF(0, 0), size, size * aspect_ratio)
                elif shape == 'hexagon':
                    # Draw hexagon
                    for i in range(6):
                        angle1 = i * 60.0
                        angle2 = (i + 1) * 60.0
                        x1 = size * math.cos(math.radians(angle1))
                        y1 = size * math.sin(math.radians(angle1))
                        x2 = size * math.cos(math.radians(angle2))
                        y2 = size * math.sin(math.radians(angle2))
                        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                elif shape == 'circle_cluster':
                    # Draw multiple small circles for hail
                    for i in range(3):
                        offset_x = (i % 2 - 0.5) * size * 0.7
                        offset_y = (i // 2 - 0.5) * size * 0.7
                        painter.drawEllipse(QPointF(offset_x, offset_y), size * 0.5, size * 0.5)
                elif shape == 'cloud':
                    # Draw cloud-like shape
                    path = QPainterPath()
                    path.moveTo(0, 0)
                    
                    # Draw cloud-like shape with multiple arcs
                    for i in range(8):
                        angle = i * 45.0
                        radius = size * (0.8 + 0.2 * math.sin(angle * 2.0))
                        x = radius * math.cos(math.radians(angle))
                        y = radius * math.sin(math.radians(angle))
                        path.lineTo(x, y)
                    
                    path.closeSubpath()
                    painter.drawPath(path)
                
                # Restore painter state
                painter.restore()
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing particles: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_precipitation_with_texture(self, painter: QPainter) -> None:
        """Draw precipitation data using texture-based rendering.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Draw each precipitation data point
            for precip_data in self._precipitation_data:
                # Get position
                position = precip_data.get('position', (0, 0))
                x, y = position
                
                # Convert to screen coordinates
                screen_x = center_x + x
                screen_y = center_y + y
                
                # Get precipitation type and intensity
                precip_type = precip_data.get('type', 'rain')
                intensity = precip_data.get('intensity', 0.5)
                
                # Get color based on precipitation type
                color = self._precipitation_colors.get(precip_type, self._precipitation_colors[None])
                
                # Get appropriate texture
                if precip_type == 'rain':
                    texture = self._rain_texture
                elif precip_type == 'snow':
                    texture = self._snow_texture
                elif precip_type == 'hail':
                    texture = self._hail_texture
                else:
                    texture = self._rain_texture  # Default
                
                # Calculate size based on intensity
                size = 30.0 + intensity * 20.0
                
                # Save painter state
                painter.save()
                
                # Apply rotation and translation
                painter.translate(screen_x, screen_y)
                painter.rotate(self._weather_rotation)
                
                # Apply turbulent edge effect if enabled
                if self._use_turbulent_edges:
                    # Calculate turbulence factor based on time
                    turbulence_time = time.time() * 0.5
                    turbulence_factor = 0.1 * math.sin(turbulence_time)
                    
                    # Apply turbulence to size
                    size *= (1.0 + turbulence_factor)
                
                # Draw multiple layers for 3D effect
                for layer in range(self._weather_layer_count):
                    # Calculate layer scale based on perspective
                    layer_scale = 1.0 - (layer * self._weather_perspective)
                    
                    # Calculate layer size
                    layer_size = size * layer_scale
                    
                    # Draw texture with color overlay
                    painter.setOpacity(0.7 * layer_scale)
                    
                    # Draw texture
                    texture_rect = QRectF(-layer_size, -layer_size, layer_size*2, layer_size*2)
                    painter.drawImage(texture_rect, texture)
                    
                    # Apply color overlay using composition mode
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
                    painter.fillRect(texture_rect, color)
                    
                    # Reset composition mode
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
                # Apply atmospheric scattering if enabled
                if self._use_atmospheric_scattering:
                    # Calculate distance factor (0-1 range)
                    distance_factor = 0.5  # Middle distance
                    
                    # Apply scattering effect
                    self._apply_atmospheric_scattering(painter, QRectF(-size*1.5, -size*1.5, size*3, size*3), color, distance_factor)
                
                # Restore painter state
                painter.restore()
                
                # Draw value if enabled
                if precip_data.get('show_values', True) and self._visual_elements.get('show_precipitation_values', True):
                    rate = precip_data.get('rate', 0.0)
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.setFont(QFont('Arial', 8))
                    painter.drawText(QRectF(screen_x - 15, screen_y + 25, 30, 15), 
                                    Qt.AlignmentFlag.AlignCenter, f"{rate:.1f}")
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing precipitation with texture: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _draw_vil_with_texture(self, painter: QPainter) -> None:
        """Draw VIL data using texture-based rendering.
        
        Args:
            painter: QPainter to use for drawing
        """
        try:
            # Get center of display
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Update VIL stats
            self._vil_data_stats['drawn_count'] = len(self._vil_data)
            
            # Draw each VIL data point
            for vil_data in self._vil_data:
                # Get position
                position = vil_data.get('position', (0, 0))
                x, y = position
                
                # Convert to screen coordinates
                screen_x = center_x + x
                screen_y = center_y + y
                
                # Get VIL value and intensity
                vil_value = vil_data.get('value', 0.0)
                intensity = vil_data.get('intensity', 0.7)
                
                # Determine VIL category based on value
                if vil_value >= 50.0:
                    vil_category = 'HIGH'
                elif vil_value >= 30.0:
                    vil_category = 'MEDIUM'
                elif vil_value >= 10.0:
                    vil_category = 'LOW'
                else:
                    vil_category = 'MINIMAL'
                
                # Get color based on VIL category
                color = self._vil_colors.get(vil_category, self._vil_colors['LOW'])
                
                # Calculate size based on VIL value
                size = 30.0 + vil_value * 0.5
                
                # Apply pulse effect
                pulse_scale = 1.0 + 0.2 * self._weather_pulse_factor
                size *= pulse_scale
                
                # Save painter state
                painter.save()
                
                # Apply rotation and translation
                painter.translate(screen_x, screen_y)
                painter.rotate(-self._weather_rotation * 0.5)  # Counter-rotation
                
                # Apply turbulent edge effect if enabled
                if self._use_turbulent_edges:
                    # Calculate turbulence factor based on time
                    turbulence_time = time.time() * 0.3
                    turbulence_factor = 0.15 * math.sin(turbulence_time)
                    
                    # Apply turbulence to size
                    size *= (1.0 + turbulence_factor)
                
                # Draw multiple layers for 3D effect
                for layer in range(self._weather_layer_count):
                    # Calculate layer scale based on perspective
                    layer_scale = 1.0 - (layer * self._weather_perspective)
                    
                    # Calculate layer size
                    layer_size = size * layer_scale
                    
                    # Draw cloud texture with color overlay
                    painter.setOpacity(0.8 * layer_scale)
                    
                    # Draw texture
                    texture_rect = QRectF(-layer_size, -layer_size, layer_size*2, layer_size*2)
                    painter.drawImage(texture_rect, self._cloud_texture)
                    
                    # Apply color overlay using composition mode
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
                    painter.fillRect(texture_rect, color)
                    
                    # Reset composition mode
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
                # Apply atmospheric scattering if enabled
                if self._use_atmospheric_scattering:
                    # Calculate distance factor (0-1 range)
                    distance_factor = 0.3  # Closer distance for VIL
                    
                    # Apply scattering effect
                    self._apply_atmospheric_scattering(painter, QRectF(-size*1.5, -size*1.5, size*3, size*3), color, distance_factor)
                
                # Restore painter state
                painter.restore()
                
                # Draw value if enabled
                if vil_data.get('show_values', True) and self._visual_elements.get('show_vil_values', True):
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.setFont(QFont('Arial', 8))
                    painter.drawText(QRectF(screen_x - 15, screen_y + 35, 30, 15), 
                                    Qt.AlignmentFlag.AlignCenter, f"{vil_value:.1f}")
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing VIL with texture: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _calculate_turbulent_edge(self, angle, time_factor=1.0, base_amplitude=5.0):
        """Calculate turbulent edge displacement for a given angle.
        
        Args:
            angle: Angle in degrees
            time_factor: Time factor for animation speed
            base_amplitude: Base amplitude of turbulence
            
        Returns:
            Displacement amount
        """
        # Convert angle to radians
        rad_angle = math.radians(angle)
        
        # Calculate time-based phase
        phase = time.time() * time_factor
        
        # Combine multiple frequencies for natural turbulence
        turbulence = 0.0
        turbulence += math.sin(rad_angle * 3 + phase) * 0.5
        turbulence += math.sin(rad_angle * 7 + phase * 1.3) * 0.3
        turbulence += math.sin(rad_angle * 11 + phase * 0.7) * 0.2
        
        # Scale by base amplitude
        return base_amplitude * turbulence
    
    def _create_turbulent_path(self, center, base_radius, points=16, turbulence_amplitude=5.0, time_factor=1.0):
        """Create a path with turbulent edges.
        
        Args:
            center: Center point (QPointF)
            base_radius: Base radius of the shape
            points: Number of points around the perimeter
            turbulence_amplitude: Amplitude of turbulence
            time_factor: Time factor for animation speed
            
        Returns:
            QPainterPath with turbulent edges
        """
        path = QPainterPath()
        
        # Calculate first point
        angle = 0.0
        turbulence = self._calculate_turbulent_edge(angle, time_factor, turbulence_amplitude)
        radius = base_radius + turbulence
        x = center.x() + radius * math.cos(math.radians(angle))
        y = center.y() + radius * math.sin(math.radians(angle))
        
        # Start path
        path.moveTo(x, y)
        
        # Add remaining points
        for i in range(1, points):
            angle = i * (360.0 / points)
            turbulence = self._calculate_turbulent_edge(angle, time_factor, turbulence_amplitude)
            radius = base_radius + turbulence
            x = center.x() + radius * math.cos(math.radians(angle))
            y = center.y() + radius * math.sin(math.radians(angle))
            path.lineTo(x, y)
        
        # Close path
        path.closeSubpath()
        
        return path
    
    def _apply_atmospheric_scattering(self, painter, rect, color, distance_factor=1.0):
        """Apply atmospheric scattering effect to simulate radar energy scattering.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle area to apply effect to
            color: Base color
            distance_factor: Factor representing distance (0.0-1.0)
        """
        # Save painter state
        painter.save()
        
        # Calculate scattering parameters based on distance
        scatter_opacity = 0.3 * distance_factor
        scatter_radius = 10.0 * distance_factor
        
        # Create a radial gradient for scattering effect
        center = QPointF(rect.center())
        gradient = QRadialGradient(center, rect.width() * 0.5)
        
        # Create scattered color (shift toward blue for atmospheric effect)
        scattered_color = QColor(color)
        scattered_color.setBlue(min(255, scattered_color.blue() + int(50 * distance_factor)))
        scattered_color.setAlpha(int(color.alpha() * scatter_opacity))
        
        # Set up gradient
        gradient.setColorAt(0, scattered_color)
        gradient.setColorAt(1, QColor(scattered_color.red(), scattered_color.green(), 
                                    scattered_color.blue(), 0))
        
        # Draw scattering effect
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw slightly larger than the original rect to create glow effect
        expanded_rect = QRectF(
            rect.x() - scatter_radius,
            rect.y() - scatter_radius,
            rect.width() + scatter_radius * 2,
            rect.height() + scatter_radius * 2
        )
        painter.drawEllipse(expanded_rect)
        
        # Restore painter state
        painter.restore()
    
    def update(self):
        """Implement update method to handle animation callbacks."""
        try:
            # Call QWidget's update method if we're inheriting from it
            if hasattr(super(), 'update'):
                logger.debug("[WEATHER_HOLO] Calling parent update method via super()")
                super().update()
            # Make sure we call repaint to force a visual refresh
            if hasattr(self, 'repaint'):
                self.repaint()
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in update method: {str(e)}")
            logger.error(traceback.format_exc())
            
    def draw_display(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw the holographic weather radar display.
        
        This method overrides the parent class method to add weather-specific visualization.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle area to draw in
            data: Display data dictionary
        """
        try:
            # Call parent draw_display method to handle base drawing
            super().draw_display(painter, rect, data)
            
            # Draw radar selection menu if visible
            if hasattr(self, '_radar_selection_menu'):
                self._radar_selection_menu.draw(painter)
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in draw_display: {str(e)}")
            logger.error(traceback.format_exc())
    
    def draw_navigation(self, painter: QPainter, rect: QRectF):
        """Draw navigation elements with military styling.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle area to draw in
        """
        try:
            # Save painter state for safety
            painter.save()
            
            # First call the parent method to ensure base navigation is drawn
            if hasattr(super(), 'draw_navigation'):
                super().draw_navigation(painter, rect)
            
            # The parent class is already drawing the bottom navigation bar
            # We need to add our radar button differently - add it in the top right corner
            # for better visibility and to avoid conflicting with existing UI elements
            
            # Calculate button dimensions - make it larger and more obvious
            button_width = 150
            button_height = 70
            padding = 15
            
            # Position in the top-right corner where it's more visible
            button_x = rect.width() - button_width - padding
            button_y = padding
            
            # Store radar button rect for click detection
            self._radar_button_rect = QRectF(button_x, button_y, button_width, button_height)
            
            radar_color = QColor(0, 255, 255)  # Brightest cyan
            
            # Create dynamic pulsing background with gradient
            pulse_time = time.time() * 4.0 
            pulse_intensity = 0.6 + 0.4 * math.sin(pulse_time)
            
            gradient = QLinearGradient(button_x, button_y, button_x, button_y + button_height)
            gradient.setColorAt(0, QColor(0, 100 + int(70 * pulse_intensity), 180, 230))    # dynamic top
            gradient.setColorAt(1, QColor(0, 150 + int(80 * pulse_intensity), 220, 230))    # dynamic bottom
            
            # Set up painter for button
            painter.setBrush(QBrush(gradient))
            
            # Animated glowing border with pulsing
            glow_intensity = 0.7 + 0.3 * math.sin(pulse_time * 1.5)  # pulsing
            border_width = 2.0 + math.sin(pulse_time) * 1.0  # Dynamic border width
            border_pen = QPen(QColor(40, 255, 255, int(255 * glow_intensity)), border_width)
            painter.setPen(border_pen)
            
            # Draw button with tactical angular corners
            path = QPainterPath()
            corner_size = 10  # Large angular corners for look
            
            # Create button path with angular styling
            path.moveTo(button_x + corner_size, button_y)
            path.lineTo(button_x + button_width - corner_size, button_y)
            path.lineTo(button_x + button_width, button_y + corner_size)
            path.lineTo(button_x + button_width, button_y + button_height - corner_size)
            path.lineTo(button_x + button_width - corner_size, button_y + button_height)
            path.lineTo(button_x + corner_size, button_y + button_height)
            path.lineTo(button_x, button_y + button_height - corner_size)
            path.lineTo(button_x, button_y + corner_size)
            path.closeSubpath()
            
            # Draw button with glow effect
            painter.drawPath(path)
            
            # Draw button text with glow
            text_color = QColor(255, 255, 255)  # Bright white text
            painter.setPen(QPen(text_color))
            font = QFont("Arial", 14)  # Larger, more visible font
            font.setBold(True)
            painter.setFont(font)
            
            # Draw "SELECT" text first
            select_rect = QRectF(
                button_x, 
                button_y + 5,  # Top padding
                button_width, 
                button_height / 2 - 5
            )
            painter.drawText(select_rect, Qt.AlignmentFlag.AlignCenter, "SELECT")
            
            # Draw "RADAR" text below
            radar_rect = QRectF(
                button_x, 
                button_y + button_height / 2, 
                button_width, 
                button_height / 2
            )
            painter.drawText(radar_rect, Qt.AlignmentFlag.AlignCenter, "RADAR")
            
            # Add tactical decoration elements
            # Left bracket
            painter.setPen(QPen(radar_color, 2))
            painter.drawLine(
                QPointF(button_x - 5, button_y + 10),
                QPointF(button_x - 15, button_y + 10)
            )
            painter.drawLine(
                QPointF(button_x - 15, button_y + 10),
                QPointF(button_x - 15, button_y + button_height - 10)
            )
            painter.drawLine(
                QPointF(button_x - 15, button_y + button_height - 10),
                QPointF(button_x - 5, button_y + button_height - 10)
            )
            
            # Right bracket
            painter.drawLine(
                QPointF(button_x + button_width + 5, button_y + 10),
                QPointF(button_x + button_width + 15, button_y + 10)
            )
            painter.drawLine(
                QPointF(button_x + button_width + 15, button_y + 10),
                QPointF(button_x + button_width + 15, button_y + button_height - 10)
            )
            painter.drawLine(
                QPointF(button_x + button_width + 15, button_y + button_height - 10),
                QPointF(button_x + button_width + 5, button_y + button_height - 10)
            )
            
            # Restore painter state
            painter.restore()
            
            # Log that we drew the button for debugging
            logger.info(f"[WEATHER_HOLO] Drew SELECT RADAR button at ({button_x}, {button_y}) with size {button_width}x{button_height}")
            
            # Also draw a radar sweep line that moves regardless of animation controller status
            self._draw_direct_sweep_line(painter, rect)
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing navigation: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _draw_direct_sweep_line(self, painter: QPainter, rect: QRectF):
        """Draw radar sweep line using direct time-based animation.
        
        This provides a fallback animation method that works even if the animation
        controller is not functioning properly.
        
        Args:
            painter: QPainter to use for drawing
            rect: Rectangle area to draw in
        """
        try:
            # Calculate center of radar display
            center_x = rect.width() / 2
            center_y = rect.height() / 2
            radius = min(center_x, center_y) * 0.6  # Slightly smaller radius for sweep line
            
            # Calculate sweep angle based on current time (complete rotation every 8 seconds)
            sweep_angle = (time.time() % 8.0) / 8.0 * 360.0
            
            # Calculate sweep endpoint
            sweep_rad = math.radians(sweep_angle)
            end_x = center_x + radius * math.sin(sweep_rad)
            end_y = center_y - radius * math.cos(sweep_rad)
            
            # Draw sweep line with glowing effect
            sweep_color = QColor(0, 170, 255)  # Bright blue
            
            # Draw main line
            painter.setPen(QPen(sweep_color, 2))
            painter.drawLine(QPointF(center_x, center_y), QPointF(end_x, end_y))
            
            # Draw fading trail (30 degree arc)
            trail_angle = (sweep_angle - 30) % 360
            if trail_angle > sweep_angle:
                trail_angle -= 360
                
            # Create semi-transparent color for trail
            trail_color = QColor(sweep_color)
            trail_color.setAlpha(80)
            painter.setPen(QPen(trail_color, 1))
            
            # Draw 10 lines for trail with decreasing opacity
            for i in range(10):
                trail_progress = i / 10.0  # 0.0 to 0.9
                angle = sweep_angle - trail_progress * 30.0
                angle_rad = math.radians(angle)
                
                trail_x = center_x + radius * math.sin(angle_rad)
                trail_y = center_y - radius * math.cos(angle_rad)
                
                # Decrease opacity for lines further from sweep
                line_opacity = 1.0 - trail_progress
                trail_pen = QPen(trail_color)
                trail_pen.setWidth(1)
                trail_pen.setColor(QColor(trail_color.red(), trail_color.green(), 
                                         trail_color.blue(), int(line_opacity * 80)))
                painter.setPen(trail_pen)
                
                painter.drawLine(QPointF(center_x, center_y), QPointF(trail_x, trail_y))
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error drawing direct sweep line: {str(e)}")
    
    def mousePressEvent(self, event):
        """Handle mouse press events for the holographic display.
        
        Handles clicks on the radar selection menu and RADAR button, then
        delegates to parent class for standard handling of other UI elements.
        
        Args:
            event: Mouse event with position information
        """
        try:
            # Convert event position to QPointF for consistency
            pos = QPointF(event.position())
            
            # Log all click events and current button positions with details
            logger.info(f"[WEATHER_HOLO] Mouse press at ({pos.x():.1f}, {pos.y():.1f})")
            if hasattr(self, '_radar_button_rect'):
                logger.info(f"[WEATHER_HOLO] RADAR button rect: x={self._radar_button_rect.x():.1f}, y={self._radar_button_rect.y():.1f}, w={self._radar_button_rect.width():.1f}, h={self._radar_button_rect.height():.1f}, contains={self._radar_button_rect.contains(pos)}")
            
            # First priority: Check settings panel (from parent class)
            if hasattr(self, '_settings_panel') and self._settings_panel.visible:
                if self._settings_panel.handle_click(pos):
                    # Click was handled by settings panel
                    event.accept()
                    self.update()
                    return
            
            # Second priority: Handle radar selection menu if visible
            if hasattr(self, '_radar_selection_menu') and self._radar_selection_menu.visible:
                # Handle click with radar selection menu
                result = self._radar_selection_menu.handle_click(pos)
                
                # If result is a string, it's a radar ID to switch to
                if isinstance(result, str):
                    self._switch_to_radar(result)
                    event.accept()
                    return
                elif result:
                    # Click was handled by the menu somehow (e.g., menu area but no action)
                    event.accept()
                    self.update()  # Request repaint to reflect any changes
                    return
            
            # Third priority: Check if RADAR button was clicked
            if hasattr(self, '_radar_button_rect') and self._radar_button_rect.contains(pos):
                logger.info("[WEATHER_HOLO] RADAR button clicked!")
                self._show_radar_selection_menu(pos)
                event.accept()
                self.update()  # Request repaint to show menu
                return
                
            # Fourth priority: Check if options button was clicked (from parent class)
            if hasattr(self, 'options_button_rect') and self.options_button_rect.contains(pos):
                # Show settings panel
                logger.info("[WEATHER_HOLO] Options button clicked")
                
                # Position settings panel properly
                if hasattr(self, '_settings_panel'):
                    panel_x = self.width() / 2 - 150
                    panel_y = self.height() / 2 - 200
                    self._settings_panel.show((panel_x, panel_y))
                    
                event.accept()
                self.update()
                return
                
            # Fall back to parent class event handling for everything else
            logger.info("[WEATHER_HOLO] Delegating to parent mousePressEvent")
            super().mousePressEvent(event)
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in mousePressEvent: {str(e)}")
            logger.error(traceback.format_exc())
            # Let parent handle it as a fallback
            super().mousePressEvent(event)
    
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click at the specified position.
        
        This method serves as a compatibility layer for components that
        don't use Qt's event system directly. It mirrors the mousePressEvent
        logic but returns boolean values instead of calling event.accept().
        
        Args:
            pos: Click position (QPointF)
            
        Returns:
            True if click was handled, False otherwise
        """
        try:
            # First priority: Handle radar selection menu if visible
            if hasattr(self, '_radar_selection_menu') and self._radar_selection_menu.visible:
                # Handle click with radar selection menu
                result = self._radar_selection_menu.handle_click(pos)
                
                # If result is a string, it's a radar ID to switch to
                if isinstance(result, str):
                    self._switch_to_radar(result)
                    self.update()  # Request repaint to reflect changes
                    return True
                elif result:
                    # Click was handled by the menu
                    self.update()  # Request repaint to reflect changes
                    return True
            
            # Second priority: Check if RADAR button was clicked
            if hasattr(self, '_radar_button_rect') and self._radar_button_rect.contains(pos):
                logger.info("[WEATHER_HOLO] RADAR button clicked")
                self._show_radar_selection_menu(pos)
                self.update()  # Request repaint to show menu
                return True
            
            # If we get here, let parent class handle the click
            # First check if parent has handle_click method
            if hasattr(super(), 'handle_click'):
                return super().handle_click(pos)
            return False  # No handler found
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error handling click: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _show_radar_selection_menu(self, pos: QPointF) -> None:
        """Show radar selection menu.
        
        Args:
            pos: Position to show menu at
        """
        try:
            if hasattr(self, '_radar_selection_menu'):
                # Position the menu at a more visible location relative to the button
                menu_pos = QPointF(
                    self._radar_button_rect.center().x() - 150,  # Center on button
                    self._radar_button_rect.bottom() + 20  # Below button
                )
                
                # Make sure menu is fully visible within the display
                if menu_pos.x() < 10:
                    menu_pos.setX(10)
                if menu_pos.x() + 300 > self.width() - 10:  # Assuming menu width of 300
                    menu_pos.setX(self.width() - 310)
                
                # Update the radar system options before showing
                if hasattr(self._radar_selection_menu, '_radar_options'):
                    self._radar_selection_menu._radar_options = self._radar_selection_menu._get_available_radar_systems()
                
                # Show the menu at the calculated position
                self._radar_selection_menu.show(menu_pos)
                logger.info(f"[WEATHER_HOLO] Showing radar selection menu at {menu_pos.x():.1f}, {menu_pos.y():.1f}")
                
                # Force a repaint to make sure menu appears immediately
                self.update()
                if hasattr(self, 'repaint'):
                    self.repaint()
                
                # Try to find parent MFD and ensure it's in RADAR mode
                self._ensure_mfd_in_radar_mode()
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error showing radar selection menu: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _ensure_mfd_in_radar_mode(self):
        """Find the parent MFD and ensure it's in RADAR mode"""
        try:
            # Create and publish the MFD mode event
            from core.event_driven_communication import get_event_bus, Event
            event_bus = get_event_bus()
            
            # Send an event to switch the MFD to RADAR mode
            mode_event = Event('set_mfd_mode', {
                'mode': 'RADAR',
                'source': 'weather_radar_holographic_display'
            })
            event_bus.publish(mode_event)
            logger.info("[WEATHER_HOLO] Published event to set MFD to RADAR mode")
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error ensuring MFD RADAR mode: {str(e)}")
    
    def _switch_to_radar(self, radar_id: str) -> None:
        """Switch to the specified radar display.
        
        Args:
            radar_id: ID of the radar display to switch to
        """
        try:
            logger.info(f"[WEATHER_HOLO] Switching to radar: {radar_id}")
            
            # Get display tree manager
            from ..display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()
            
            # Get the radar node
            radar_node = tree_manager.root.get_child(radar_id)
            if not radar_node:
                logger.error(f"[WEATHER_HOLO] Radar node not found: {radar_id}")
                return
            
            # Get current display mode from the radar node
            mode_node = radar_node.get_child("mode")
            current_mode = "STANDBY"  # Default to STANDBY
            if mode_node and hasattr(mode_node, 'value'):
                current_mode = mode_node.value
            
            # Create event to switch display
            from core.event_driven_communication import get_event_bus, Event
            event_bus = get_event_bus()
            
            # Construct the display change event
            event_data = {
                "display_type": radar_id,
                "mode": current_mode,
                "source": "radar_selection_menu"
            }
            
            # Create and publish the event
            switch_event = Event('switch_display', event_data)
            event_bus.publish(switch_event)
            
            logger.info(f"[WEATHER_HOLO] Published display switch event to {radar_id} in {current_mode} mode")
            
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error switching to radar: {str(e)}")
            logger.error(traceback.format_exc())

    def paintEvent(self, event):
        """Handle paint events for the holographic display.
        
        Args:
            event: Paint event
        """
        try:
            # Accept the event to prevent further propagation
            if hasattr(event, 'accept'):
                event.accept()
            
            # Since this class doesn't inherit from QWidget/QPaintDevice,
            # we can't use QPainter on it directly. Instead, we'll just call
            # the paint_display method which will be handled by the parent class.
            
            # If we were rendering to a QImage, we could do:
            # image = QImage(800, 600, QImage.Format.Format_ARGB32)
            # image.fill(QColor(0, 0, 0, 0))
            # painter = QPainter(image)
            # self.paint_display(painter)
            # painter.end()
            
            # Throttle logging - only log paint events occasionally
            current_time = time.time()
            if not hasattr(self, '_last_paint_log_time'):
                self._last_paint_log_time = 0
                
            # Log only once every 5 seconds
            if current_time - self._last_paint_log_time > 10.0:
                self._last_paint_log_time = current_time
                logger.debug("[WEATHER_HOLO] Received paint event, notifying parent for redraw")
            
            # Call update method if available (this will trigger a repaint in Qt widgets)
            if hasattr(self, 'update'):
                self.update()
            
            # Notify animation controller to continue animations
            if hasattr(self, '_animation_controller') and self._animation_controller is not None:
                try:
                    self._animation_controller.animation_updated.emit({'dt': 0.016})
                    
                    # Only log animation controller updates occasionally
                    if current_time - self._last_paint_log_time > 10.0:
                        logger.debug("[WEATHER_HOLO] Notified animation controller")
                except Exception as e:
                    # Still log errors immediately
                    logger.error(f"[WEATHER_HOLO] Error notifying animation controller: {str(e)}")
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in paintEvent: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _manual_animation_update(self) -> None:
        """Handle manual animation timer update.
        
        This provides a fallback animation system for when the main animation controller fails.
        """
        try:
            # Update direct sweep angle 
            self._direct_sweep_angle = (self._direct_sweep_angle + 2.0) % 360.0
            
            # Update weather rotation
            self._weather_rotation += 0.5
            if self._weather_rotation >= 360.0:
                self._weather_rotation -= 360.0
                
            # Update pulse effect
            self._weather_pulse_factor = 0.5 + 0.5 * math.sin(time.time() * self._weather_pulse_speed)
            
            # Force display update
            self.update()
            if hasattr(self, 'repaint'):
                self.repaint()
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in manual animation update: {str(e)}")
            
    def _periodic_cleanup(self) -> None:
        """Perform periodic cleanup of expired data points."""
        try:
            # Get current time
            current_time = time.time()
            
            # Clean up expired VIL data timestamps
            expired_vil_ids = []
            for vil_id, timestamp in self._vil_data_timestamp.items():
                if current_time - timestamp > self._vil_persist_time:
                    expired_vil_ids.append(vil_id)
                    
            # Remove expired VIL IDs
            for vil_id in expired_vil_ids:
                self._vil_data_timestamp.pop(vil_id, None)
                
            # Reset VIL stats if needed
            if current_time - self._vil_data_stats['last_stats_reset'] > self._vil_data_stats['stats_interval']:
                self._vil_data_stats['received_count'] = 0
                self._vil_data_stats['stored_count'] = 0
                self._vil_data_stats['drawn_count'] = 0
                self._vil_data_stats['last_stats_reset'] = current_time
                logger.info("[WEATHER_HOLO] Reset VIL data statistics")
                
            # Log current stats
            logger.info(f"[WEATHER_HOLO] VIL stats: received={self._vil_data_stats['received_count']}, "
                        f"stored={self._vil_data_stats['stored_count']}, "
                        f"drawn={self._vil_data_stats['drawn_count']}")
                
        except Exception as e:
            logger.error(f"[WEATHER_HOLO] Error in periodic cleanup: {str(e)}")
            logger.error(traceback.format_exc())
