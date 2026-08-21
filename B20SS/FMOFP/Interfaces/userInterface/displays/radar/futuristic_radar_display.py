"""
Futuristic radar display with advanced visual effects
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont, QFontMetrics
from typing import Dict, List, Optional, Tuple, Any
import math
import time
import random
from .base_radar_display import BaseRadarDisplay
from ..visual.theme_manager import get_theme_manager, DisplayTheme
from ..visual.effects import VisualEffects
from ..visual.animation_controller import AnimationController, TransitionGroup
from ..visual.settings_panel import SettingsPanel
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class FuturisticRadarDisplay(BaseRadarDisplay):
    """Advanced radar display with futuristic styling"""
    
    def __init__(self):
        """Initialize futuristic radar display"""
        super().__init__()
        
        # Update colors from theme but don't change the theme itself
        self.update_colors_from_theme()
        
        # Enhanced visual effects
        self._visual_effects = VisualEffects()
        
        # Animation controller
        self._animation_controller = AnimationController()
        self._animation_controller.start()
        
        # Animation update timer
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(16)  # ~60 FPS
        self._animation_timer.timeout.connect(self._update_animations)
        self._animation_timer.start()
        
        # Last update time for animations
        self._last_update_time = time.time()
        
        # Display properties
        self.side_panel_width = 0  # Start collapsed
        self.side_panel_target = 150  # Target width when expanded
        self.hexagonal_grid = True
        self.show_3d_terrain = True
        self.data_fusion_level = 1  # 1-3, controls overlay complexity
        
        # Radar sweep animation
        self.sweep_angle = 0.0
        self.sweep_speed = 45.0  # degrees per second
        
        # Pulse effect for important elements
        self.pulse_factor = 1.0
        self.pulse_rate = 1.5  # cycles per second
        
        # Threat tracking
        self.tracked_threats = []
        
        # Data visualization
        self.terrain_data = self._generate_sample_terrain_data(24)
        self.signal_strength_data = self._generate_sample_signal_data(48)
        
        # Settings panel
        self._settings_panel = SettingsPanel()
        self._setup_settings_panel()
        
        # Options button
        self.show_options_button = True
        self.options_button_rect = QRectF(0, 0, 30, 30)  # Will be positioned in draw_display
        
        # Initialize animations
        self._init_animations()
        
    def _setup_settings_panel(self):
        """Set up settings panel with callbacks"""
        # Theme setting
        self._settings_panel.set_option_callback("theme", self._on_theme_changed)
        
        # Grid type setting
        self._settings_panel.set_option_callback("grid_type", self._on_grid_type_changed)
        
        # Glow effects setting
        self._settings_panel.set_option_callback("use_glow", self._on_glow_changed)
        
        # Animations setting
        self._settings_panel.set_option_callback("use_animations", self._on_animations_changed)
        
        # Terrain setting
        self._settings_panel.set_option_callback("show_terrain", self._on_terrain_changed)
        
        # Side panel setting
        self._settings_panel.set_option_callback("show_side_panel", self._on_side_panel_changed)
        
        # Information density setting
        self._settings_panel.set_option_callback("information_density", self._on_density_changed)
        
        # Data fusion level setting
        self._settings_panel.set_option_callback("data_fusion_level", self._on_fusion_level_changed)
        
        # Range scale setting
        self._settings_panel.set_option_callback("range_scale", self._on_range_scale_changed)
        
    def _on_theme_changed(self, theme_name: str):
        """Handle theme change"""
        theme_map = {
            "classic": DisplayTheme.CLASSIC,
            "modern": DisplayTheme.MODERN,
            "night": DisplayTheme.NIGHT,
            "futuristic": DisplayTheme.FUTURISTIC
        }
        
        if theme_name in theme_map:
            self._theme_manager.set_theme(theme_map[theme_name])
            self.update_colors_from_theme()
            
    def _on_grid_type_changed(self, grid_type: str):
        """Handle grid type change"""
        # Update theme style parameter
        theme = self._theme_manager.get_current_theme()
        theme_data = self._theme_manager._themes[theme]
        if "styles" in theme_data:
            theme_data["styles"]["grid_type"] = grid_type
            
    def _on_glow_changed(self, use_glow: bool):
        """Handle glow effects change"""
        # Update theme style parameter
        theme = self._theme_manager.get_current_theme()
        theme_data = self._theme_manager._themes[theme]
        if "styles" in theme_data:
            theme_data["styles"]["use_gradients"] = use_glow
            
    def _on_animations_changed(self, use_animations: bool):
        """Handle animations change"""
        # Update theme style parameter
        theme = self._theme_manager.get_current_theme()
        theme_data = self._theme_manager._themes[theme]
        if "styles" in theme_data:
            theme_data["styles"]["use_animations"] = use_animations
            
    def _on_terrain_changed(self, show_terrain: bool):
        """Handle terrain visualization change"""
        self.show_3d_terrain = show_terrain
        
    def _on_side_panel_changed(self, show_panel: bool):
        """Handle side panel change"""
        if show_panel:
            # Show panel
            self._animation_controller.create_animation(
                "side_panel_width",
                self.side_panel_width,
                self.side_panel_target,
                0.3,
                lambda value: self._set_side_panel_width(value)
            )
        else:
            # Hide panel
            self._animation_controller.create_animation(
                "side_panel_width",
                self.side_panel_width,
                0.0,
                0.3,
                lambda value: self._set_side_panel_width(value)
            )
            
    def _on_density_changed(self, density: str):
        """Handle information density change"""
        # Update theme style parameter
        theme = self._theme_manager.get_current_theme()
        theme_data = self._theme_manager._themes[theme]
        if "styles" in theme_data:
            theme_data["styles"]["information_density"] = density
            
    def _on_fusion_level_changed(self, level: int):
        """Handle data fusion level change"""
        self.data_fusion_level = level
        
    def _on_range_scale_changed(self, scale: int):
        """Handle range scale change"""
        self.range_scale = scale
    
    def _init_animations(self):
        """Initialize animations for display elements"""
        # Side panel animation
        self._animation_controller.create_animation(
            "side_panel_width",
            0.0,  # Start collapsed
            self.side_panel_target,  # Target width
            0.3,  # Duration in seconds
            lambda value: self._set_side_panel_width(value),
            None,
            QEasingCurve.Type.OutCubic
        )
    
    def _set_side_panel_width(self, width: float):
        """Set side panel width (animation callback)"""
        self.side_panel_width = width
    
    def _update_animations(self):
        """Update animations and effects"""
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Update visual effects animations
        self._visual_effects.update_animation_time(delta_time)
        
        # Update radar sweep
        self.sweep_angle = (self.sweep_angle + self.sweep_speed * delta_time) % 360.0
        
        # Update pulse effect
        self.pulse_factor = self._visual_effects.get_pulse_factor(
            rate=self.pulse_rate,
            min_value=0.7,
            max_value=1.0
        )
    
    def draw_display(self, painter: QPainter, rect: QRectF, data: Dict = None):
        """Override draw_display to add settings panel and options button"""
        # Call parent method to draw base display
        super().draw_display(painter, rect, data)
        
        # Position options button in top-right corner
        button_size = 30
        self.options_button_rect = QRectF(
            rect.right() - button_size - 10,
            rect.top() + 10,
            button_size,
            button_size
        )
        
        # Draw options button
        if self.show_options_button:
            self._draw_options_button(painter, self.options_button_rect)
        
        # Draw settings panel if visible
        if self._settings_panel.visible:
            # Update settings panel animation
            self._settings_panel.update(0.016)  # ~60 FPS
            
            # Draw settings panel
            self._settings_panel.draw(painter, rect)
    
    def _draw_options_button(self, painter: QPainter, rect: QRectF):
        """Draw options button"""
        # Save painter state
        painter.save()
        
        try:
            # Draw button background
            background_color = QColor(self._theme_manager.get_color("overlay_background"))
            painter.fillRect(rect, background_color)
            
            # Draw button frame
            self._visual_effects.draw_angular_frame(
                painter,
                rect,
                color=self._theme_manager.get_color("hud"),
                corner_style="angular",
                glow=True
            )
            
            # Draw gear icon
            # Calculate center and radius
            center_x = rect.x() + rect.width() / 2
            center_y = rect.y() + rect.height() / 2
            radius = min(rect.width(), rect.height()) * 0.3
            
            # Draw outer circle
            outer_rect = QRectF(
                center_x - radius,
                center_y - radius,
                radius * 2,
                radius * 2
            )
            
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                outer_rect,
                color=self._theme_manager.get_color("hud"),
                fill=False,
                glow=True
            )
            
            # Draw inner circle
            inner_radius = radius * 0.5
            inner_rect = QRectF(
                center_x - inner_radius,
                center_y - inner_radius,
                inner_radius * 2,
                inner_radius * 2
            )
            
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                inner_rect,
                color=self._theme_manager.get_color("hud"),
                fill=True,
                glow=False
            )
            
            # Draw gear teeth
            num_teeth = 8
            for i in range(num_teeth):
                angle = 2 * math.pi * i / num_teeth
                
                # Calculate tooth position
                tooth_x = center_x + radius * 1.3 * math.cos(angle)
                tooth_y = center_y + radius * 1.3 * math.sin(angle)
                
                # Draw tooth line
                self._visual_effects.draw_enhanced_line(
                    painter,
                    QPointF(center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)),
                    QPointF(tooth_x, tooth_y),
                    color=self._theme_manager.get_color("hud"),
                    width=1.5,
                    glow=True
                )
        finally:
            # Restore painter state
            painter.restore()
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Convert event position to QPointF
        pos = QPointF(event.position())
        
        # Check if settings panel is visible and handle click
        if self._settings_panel.visible:
            if self._settings_panel.handle_click(pos):
                # Click was handled by settings panel
                self.update()
                return
        
        # Check if options button was clicked
        if self.options_button_rect.contains(pos):
            # Show settings panel
            self._settings_panel.show((self.width() / 2 - 150, self.height() / 2 - 200))
            self.update()
            return
        
        # Pass event to parent class
        super().mousePressEvent(event)
    
    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw radar display with futuristic styling"""
       
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(rect, QColor(0, 0, 0, 255))
        painter.restore()
        
        # Get theme parameters
        use_gradients = self._theme_manager.get_style_param("use_gradients", True)
        use_angular_design = self._theme_manager.get_style_param("use_angular_design", True)
        grid_type = self._theme_manager.get_style_param("grid_type", "hexagonal")
        
        # Calculate radar center and radius
        center_x = rect.width() * 0.5
        center_y = rect.height() * 0.5
        
        # Adjust for side panel if visible
        if self.side_panel_width > 0:
            center_x = (rect.width() - self.side_panel_width) * 0.5
        
        center = QPointF(center_x, center_y)
        radius = min(center_x, center_y) * 0.85
        
        # Draw layered background
        self._visual_effects.draw_layered_background(
            painter, 
            rect,
            base_color=self._theme_manager.get_color("background"),
            grid_color=self._theme_manager.get_color("grid"),
            grid_type=grid_type
        )
        
        # Draw radar frame
        self._draw_radar_frame(painter, center, radius)
        
        # Draw grid based on style
        if grid_type == "hexagonal":
            self._visual_effects.draw_hexagonal_grid(
                painter, 
                center, 
                radius,
                color=self._theme_manager.get_color("grid"),
                rings=4,
                glow=use_gradients
            )
        else:
            # Draw traditional range rings
            self.draw_range_rings(painter, center, radius)
        
        # Draw cardinal directions
        self._draw_cardinal_directions(painter, center, radius)
        
        # Draw radar sweep
        self._draw_radar_sweep(painter, center, radius)
        
        # Draw terrain if enabled
        if self.show_3d_terrain:
            self._draw_terrain_visualization(painter, rect)
        
        # Draw tracked objects
        self._draw_tracked_objects(painter, center, radius, data)
        
        # Draw data fusion overlay based on level
        if self.data_fusion_level > 0:
            self._draw_data_fusion_overlay(painter, rect, data)
        
        # Draw side panel if visible
        if self.side_panel_width > 0:
            self._draw_side_panel(painter, rect)
        
        # Draw mode indicator and status
        self._draw_mode_indicator(painter, rect)
    
    def _draw_radar_frame(self, painter: QPainter, center: QPointF, radius: float):
        """Draw radar frame with angular styling"""
        # Get styling parameters
        use_angular_design = self._theme_manager.get_style_param("use_angular_design", True)
        corner_style = "angular" if use_angular_design else "rounded"
        
        # Create frame rect
        frame_rect = QRectF(
            center.x() - radius - 10,
            center.y() - radius - 10,
            (radius + 10) * 2,
            (radius + 10) * 2
        )
        
        # Draw frame with angular corners
        self._visual_effects.draw_angular_frame(
            painter,
            frame_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style=corner_style,
            glow=True
        )
        
        # Draw inner circle for radar area
        self._visual_effects.draw_enhanced_ellipse(
            painter,
            QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2
            ),
            color=self._theme_manager.get_color("grid"),
            glow=False
        )
    
    def _draw_cardinal_directions(self, painter: QPainter, center: QPointF, radius: float):
        """Draw cardinal directions with enhanced styling"""
        # Save painter state
        painter.save()
        
        try:
            # Set up text properties
            font = self._theme_manager.get_font("data")
            painter.setFont(font)
            
            # Draw cardinal directions
            directions = [
                ("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
                ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)
            ]
            
            for label, angle in directions:
                # Calculate position
                rad_angle = math.radians(angle)
                pos_x = center.x() + (radius + 20) * math.sin(rad_angle)
                pos_y = center.y() - (radius + 20) * math.cos(rad_angle)
                
                # Create text rect
                text_rect = QRectF(pos_x - 15, pos_y - 10, 30, 20)
                
                # Draw text with glow
                self._visual_effects.draw_enhanced_text(
                    painter,
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                    glow=True,
                    glow_color=self._theme_manager.get_color("hud")
                )
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_radar_sweep(self, painter: QPainter, center: QPointF, radius: float):
        """Draw animated radar sweep line"""
        # Save painter state
        painter.save()
        
        try:
            # Calculate sweep endpoint
            sweep_rad = math.radians(self.sweep_angle)
            end_x = center.x() + radius * math.sin(sweep_rad)
            end_y = center.y() - radius * math.cos(sweep_rad)
            
            # Create sweep color with pulse effect
            sweep_color = QColor(self._theme_manager.get_color("data_primary"))
            
            # Draw sweep line with glow
            self._visual_effects.draw_enhanced_line(
                painter,
                center,
                QPointF(end_x, end_y),
                color=sweep_color,
                width=2.0,
                glow=True
            )
            
            # Draw sweep arc (fading trail)
            path = QPainterPath()
            path.moveTo(center)
            
            # Calculate arc angles
            start_angle = (self.sweep_angle - 30) % 360
            if start_angle > self.sweep_angle:
                start_angle -= 360
                
            # Create arc path
            path.arcTo(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
                90 - start_angle,  # Start angle (Qt uses different angle system)
                -30  # Sweep 30 degrees
            )
            path.lineTo(center)
            
            # Create gradient brush for arc
            arc_color = QColor(sweep_color)
            arc_color.setAlpha(100)
            
            # Draw arc with semi-transparency
            painter.setBrush(QBrush(arc_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_tracked_objects(self, painter: QPainter, center: QPointF, radius: float, data: Dict):
        """Draw tracked objects on radar"""
        # Check if data is None or empty
        if data is None or not data:
            # No data to display
            return
            
        # Get the current radar mode to ensure we only show relevant objects
        current_mode = data.get('mode')
        if current_mode is None:
            # No mode specified, can't determine what to display
            return
            
        # Sample tracked objects if not provided in data
        tracked_objects = data.get("tracked_objects", self._generate_sample_tracked_objects())
        
        # Save painter state
        painter.save()
        
        try:
            for obj in tracked_objects:
                # Get object properties
                obj_type = obj.get("type", "unknown")
                position = obj.get("position", (0, 0))  # (x, y) in radar space
                velocity = obj.get("velocity", (0, 0))  # (vx, vy) in radar space
                threat_level = obj.get("threat_level", 0)  # 0-10
                
                # Convert position to screen coordinates
                screen_pos = self.world_to_screen(position, center, radius, self.range_scale)
                
                # Determine color based on object type
                if obj_type == "friendly":
                    color = self._theme_manager.get_color("friendly")
                elif obj_type == "enemy":
                    color = self._theme_manager.get_color("enemy")
                else:
                    color = self._theme_manager.get_color("neutral")
                
                # Apply pulse effect to high threat objects
                glow = threat_level > 5
                
                # Draw object based on type
                if obj_type == "friendly":
                    self._draw_friendly_object(painter, screen_pos, color, glow)
                elif obj_type == "enemy":
                    self._draw_enemy_object(painter, screen_pos, color, glow, threat_level)
                else:
                    self._draw_neutral_object(painter, screen_pos, color, glow)
                
                # Draw velocity vector if moving
                if velocity[0] != 0 or velocity[1] != 0:
                    # Scale velocity for display
                    vel_scale = 2.0
                    vel_x = screen_pos.x() + velocity[0] * vel_scale
                    vel_y = screen_pos.y() - velocity[1] * vel_scale
                    
                    # Draw velocity line
                    self._visual_effects.draw_enhanced_line(
                        painter,
                        screen_pos,
                        QPointF(vel_x, vel_y),
                        color=color,
                        width=1.0,
                        glow=False
                    )
                
                # Draw threat ring for high threat objects
                if threat_level > 7:
                    # Calculate ring size based on threat level
                    ring_size = 10 + threat_level * 2
                    
                    # Create ring rect
                    ring_rect = QRectF(
                        screen_pos.x() - ring_size,
                        screen_pos.y() - ring_size,
                        ring_size * 2,
                        ring_size * 2
                    )
                    
                    # Draw pulsing ring
                    ring_color = QColor(color)
                    ring_color.setAlpha(int(100 * self.pulse_factor))
                    
                    self._visual_effects.draw_enhanced_ellipse(
                        painter,
                        ring_rect,
                        color=ring_color,
                        glow=True
                    )
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_friendly_object(self, painter: QPainter, position: QPointF, color: QColor, glow: bool):
        """Draw friendly object symbol (circle)"""
        # Create object rect
        rect = QRectF(position.x() - 4, position.y() - 4, 8, 8)
        
        # Draw circle with fill
        self._visual_effects.draw_enhanced_ellipse(
            painter,
            rect,
            color=color,
            fill=True,
            glow=glow
        )
    
    def _draw_enemy_object(self, painter: QPainter, position: QPointF, color: QColor, glow: bool, threat_level: int):
        """Draw enemy object symbol (diamond)"""
        # Create diamond path
        path = QPainterPath()
        size = 5 + threat_level * 0.3  # Size based on threat level
        
        path.moveTo(position.x(), position.y() - size)  # Top
        path.lineTo(position.x() + size, position.y())  # Right
        path.lineTo(position.x(), position.y() + size)  # Bottom
        path.lineTo(position.x() - size, position.y())  # Left
        path.closeSubpath()
        
        # Draw diamond with fill
        self._visual_effects.draw_enhanced_path(
            painter,
            path,
            color=color,
            fill=True,
            glow=glow
        )
    
    def _draw_neutral_object(self, painter: QPainter, position: QPointF, color: QColor, glow: bool):
        """Draw neutral object symbol (square)"""
        # Create object rect
        rect = QRectF(position.x() - 4, position.y() - 4, 8, 8)
        
        # Draw square with fill
        self._visual_effects.draw_enhanced_rect(
            painter,
            rect,
            color=color,
            fill=True
        )
    
    def _draw_terrain_visualization(self, painter: QPainter, rect: QRectF):
        """Draw 3D terrain visualization at bottom of display"""
        # Save painter state
        painter.save()
        
        try:
            # Create visualization rect at bottom of display
            viz_height = rect.height() * 0.15
            viz_rect = QRectF(
                rect.x() + 10,
                rect.bottom() - viz_height - 10,
                rect.width() - 20 - self.side_panel_width,
                viz_height
            )
            
            # Draw terrain data visualization
            self._visual_effects.draw_data_visualization(
                painter,
                viz_rect,
                self.terrain_data,
                color=self._theme_manager.get_color("data_secondary"),
                style="angular" if self._theme_manager.get_style_param("use_angular_design", True) else "modern",
                fill=True,
                glow=True
            )
            
            # Draw frame around visualization
            self._visual_effects.draw_angular_frame(
                painter,
                viz_rect,
                color=self._theme_manager.get_color("hud"),
                corner_style="angular" if self._theme_manager.get_style_param("use_angular_design", True) else "rounded",
                glow=False
            )
            
            # Draw label
            label_rect = QRectF(
                viz_rect.x(),
                viz_rect.y() - 20,
                100,
                20
            )
            
            self._visual_effects.draw_enhanced_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "TERRAIN PROFILE",
                glow=True,
                glow_color=self._theme_manager.get_color("hud")
            )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_data_fusion_overlay(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw data fusion overlay with additional information"""
        # Check if data is None or empty
        if data is None or not data:
            # No data to display
            return
            
        # Get the current radar mode to ensure we only show relevant overlays
        current_mode = data.get('mode')
        if current_mode is None:
            # No mode specified, can't determine what to display
            return
            
        # Save painter state
        painter.save()
        
        try:
            # Draw signal strength graph in top-right corner
            if self.data_fusion_level >= 2:
                self._draw_signal_strength_graph(painter, rect)
            
            # Draw threat assessment in bottom-left corner
            if self.data_fusion_level >= 1:
                self._draw_threat_assessment(painter, rect, data)
            
            # Draw advanced targeting info for level 3
            if self.data_fusion_level >= 3:
                self._draw_targeting_info(painter, rect, data)
                
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_signal_strength_graph(self, painter: QPainter, rect: QRectF):
        """Draw signal strength graph in top-right corner"""
        # Create graph rect
        graph_width = 150
        graph_height = 60
        
        # Adjust for side panel
        x_pos = rect.right() - graph_width - 10
        if self.side_panel_width > 0:
            x_pos = rect.right() - self.side_panel_width - graph_width - 10
            
        graph_rect = QRectF(
            x_pos,
            rect.y() + 10,
            graph_width,
            graph_height
        )
        
        # Draw background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(graph_rect, background_color)
        
        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            graph_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )
        
        # Draw signal data
        data_rect = QRectF(
            graph_rect.x() + 5,
            graph_rect.y() + 15,
            graph_rect.width() - 10,
            graph_rect.height() - 20
        )
        
        self._visual_effects.draw_data_visualization(
            painter,
            data_rect,
            self.signal_strength_data,
            color=self._theme_manager.get_color("data_primary"),
            style="angular",
            fill=True,
            glow=True
        )
        
        # Draw label
        label_rect = QRectF(
            graph_rect.x() + 5,
            graph_rect.y() + 2,
            graph_rect.width() - 10,
            15
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "SIGNAL STRENGTH",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
    
    def _draw_threat_assessment(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw threat assessment information"""
        # Get threat data
        threat_level = data.get("threat_level", random.randint(1, 10))
        threat_direction = data.get("threat_direction", random.randint(0, 359))
        
        # Create threat assessment rect
        assess_width = 150
        assess_height = 80
        
        assess_rect = QRectF(
            rect.x() + 10,
            rect.bottom() - assess_height - 10,
            assess_width,
            assess_height
        )
        
        # Draw background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(assess_rect, background_color)
        
        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            assess_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )
        
        # Draw label
        label_rect = QRectF(
            assess_rect.x() + 5,
            assess_rect.y() + 2,
            assess_rect.width() - 10,
            15
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "THREAT ASSESSMENT",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw threat level
        level_rect = QRectF(
            assess_rect.x() + 5,
            assess_rect.y() + 20,
            assess_rect.width() - 10,
            15
        )
        
        # Determine threat color
        if threat_level < 4:
            threat_color = self._theme_manager.get_color("friendly")
        elif threat_level < 7:
            threat_color = self._theme_manager.get_color("warning")
        else:
            threat_color = self._theme_manager.get_color("enemy")
        
        # Draw threat level text
        self._visual_effects.draw_enhanced_text(
            painter,
            level_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"LEVEL: {threat_level}/10",
            glow=threat_level > 7,
            glow_color=threat_color
        )
        
        # Draw threat direction
        dir_rect = QRectF(
            assess_rect.x() + 5,
            assess_rect.y() + 40,
            assess_rect.width() - 10,
            15
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            dir_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"DIRECTION: {threat_direction}°",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw threat bar
        bar_rect = QRectF(
            assess_rect.x() + 5,
            assess_rect.y() + 60,
            assess_rect.width() - 10,
            10
        )
        
        # Draw background bar
        painter.fillRect(bar_rect, QColor(30, 30, 30))
        
        # Draw filled portion
        filled_width = bar_rect.width() * (threat_level / 10.0)
        filled_rect = QRectF(
            bar_rect.x(),
            bar_rect.y(),
            filled_width,
            bar_rect.height()
        )
        
        painter.fillRect(filled_rect, threat_color)
        
        # Draw bar frame
        painter.setPen(self._theme_manager.get_color("hud"))
        painter.drawRect(bar_rect)
    
    def _draw_targeting_info(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw advanced targeting information"""
        # Get target data
        target = data.get("primary_target", self._generate_sample_target())
        
        if not target:
            return
            
        # Create targeting info rect
        target_width = 200
        target_height = 120
        
        # Position in top-right instead of top-left to avoid corner element overlap
        target_rect = QRectF(
            rect.right() - target_width - 60,  # Move to right side, leave space for buttons
            rect.y() + 50,                     # Move down to avoid top buttons
            target_width,
            target_height
        )
        
        # Draw background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(target_rect, background_color)
        
        # Draw frame with glow if locked
        is_locked = target.get("locked", False)
        
        self._visual_effects.draw_angular_frame(
            painter,
            target_rect,
            color=self._theme_manager.get_color("enemy") if is_locked else self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=is_locked
        )
        
        # Draw label
        label_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + 2,
            target_rect.width() - 10,
            15
        )
        
        label_text = "TARGET LOCKED" if is_locked else "TARGET TRACKING"
        
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label_text,
            glow=is_locked,
            glow_color=self._theme_manager.get_color("enemy") if is_locked else self._theme_manager.get_color("hud")
        )
        
        # Draw target info
        y_offset = 25
        line_height = 18
        
        # Target ID
        id_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + y_offset,
            target_rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            id_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"ID: {target.get('id', 'UNKNOWN')}",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        y_offset += line_height
        
        # Target type
        type_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + y_offset,
            target_rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            type_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"TYPE: {target.get('type', 'UNKNOWN')}",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        y_offset += line_height
        
        # Target range
        range_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + y_offset,
            target_rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            range_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"RANGE: {target.get('range', 0):.1f} NM",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        y_offset += line_height
        
        # Target speed
        speed_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + y_offset,
            target_rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            speed_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"SPEED: {target.get('speed', 0):.0f} KTS",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        y_offset += line_height
        
        # Target heading
        heading_rect = QRectF(
            target_rect.x() + 5,
            target_rect.y() + y_offset,
            target_rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            heading_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"HEADING: {target.get('heading', 0):.0f}°",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
    
    def _draw_side_panel(self, painter: QPainter, rect: QRectF):
        """Draw side panel with additional controls and information"""
        if self.side_panel_width <= 0:
            return
            
        # Create side panel rect
        panel_rect = QRectF(
            rect.right() - self.side_panel_width,
            rect.y(),
            self.side_panel_width,
            rect.height()
        )
        
        # Draw panel background
        background_color = QColor(self._theme_manager.get_color("menu_background"))
        painter.fillRect(panel_rect, background_color)
        
        # Draw panel border
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(panel_rect.x(), panel_rect.y()),
            QPointF(panel_rect.x(), panel_rect.bottom()),
            color=self._theme_manager.get_color("hud"),
            width=2.0,
            glow=True
        )
        
        # Draw panel title
        title_rect = QRectF(
            panel_rect.x() + 5,
            panel_rect.y() + 10,
            panel_rect.width() - 10,
            20
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "RADAR CONTROLS",
            glow=True,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw control sections
        y_offset = 40
        section_height = 30
        
        # Range control
        self._draw_panel_section(
            painter,
            panel_rect,
            y_offset,
            section_height,
            "RANGE",
            f"{self.range_scale} NM"
        )
        y_offset += section_height + 10
        
        # Mode control
        self._draw_panel_section(
            painter,
            panel_rect,
            y_offset,
            section_height,
            "MODE",
            "SURVEILLANCE"
        )
        y_offset += section_height + 10
        
        # Grid type control
        grid_type = self._theme_manager.get_style_param("grid_type", "hexagonal")
        grid_type_display = grid_type.upper()
        self._draw_panel_section(
            painter,
            panel_rect,
            y_offset,
            section_height,
            "GRID",
            grid_type_display
        )
        y_offset += section_height + 10
        
        # Data fusion level control
        self._draw_panel_section(
            painter,
            panel_rect,
            y_offset,
            section_height,
            "DATA FUSION",
            f"LEVEL {self.data_fusion_level}"
        )
        y_offset += section_height + 10
        
        # Terrain toggle
        terrain_status = "ON" if self.show_3d_terrain else "OFF"
        self._draw_panel_section(
            painter,
            panel_rect,
            y_offset,
            section_height,
            "TERRAIN",
            terrain_status
        )
        y_offset += section_height + 10
        
        # System status
        status_rect = QRectF(
            panel_rect.x() + 5,
            panel_rect.bottom() - 60,
            panel_rect.width() - 10,
            50
        )
        
        self._draw_system_status(painter, status_rect)
    
    def _draw_panel_section(self, painter: QPainter, panel_rect: QRectF, y_offset: float, 
                          height: float, label: str, value: str):
        """Draw a control section in the side panel"""
        # Create section rect
        section_rect = QRectF(
            panel_rect.x() + 5,
            panel_rect.y() + y_offset,
            panel_rect.width() - 10,
            height
        )
        
        # Draw section background
        background_color = QColor(self._theme_manager.get_color("menu_highlight"))
        painter.fillRect(section_rect, background_color)
        
        # Draw section border
        self._visual_effects.draw_angular_frame(
            painter,
            section_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )
        
        # Draw label
        label_rect = QRectF(
            section_rect.x() + 5,
            section_rect.y() + 2,
            section_rect.width() / 2 - 10,
            section_rect.height() - 4
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw value
        value_rect = QRectF(
            section_rect.x() + section_rect.width() / 2,
            section_rect.y() + 2,
            section_rect.width() / 2 - 5,
            section_rect.height() - 4
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            value_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            value,
            glow=True,
            glow_color=self._theme_manager.get_color("data_primary")
        )
    
    def _draw_system_status(self, painter: QPainter, rect: QRectF):
        """Draw system status information"""
        # Draw background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(rect, background_color)
        
        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )
        
        # Draw status label
        label_rect = QRectF(
            rect.x() + 5,
            rect.y() + 2,
            rect.width() - 10,
            15
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "SYSTEM STATUS",
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw status items
        y_offset = 20
        line_height = 15
        
        # System health
        health_rect = QRectF(
            rect.x() + 5,
            rect.y() + y_offset,
            rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            health_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "HEALTH: NOMINAL",
            glow=False,
            glow_color=self._theme_manager.get_color("friendly")
        )
        
        y_offset += line_height
        
        # Signal quality
        signal_rect = QRectF(
            rect.x() + 5,
            rect.y() + y_offset,
            rect.width() - 10,
            line_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            signal_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "SIGNAL: 98%",
            glow=False,
            glow_color=self._theme_manager.get_color("friendly")
        )
    
    def _draw_mode_indicator(self, painter: QPainter, rect: QRectF):
        """Draw radar mode indicator"""
        # Create mode indicator rect
        indicator_width = 200
        indicator_height = 30
        
        indicator_rect = QRectF(
            rect.x() + (rect.width() - indicator_width) / 2,
            rect.y() + 10,
            indicator_width,
            indicator_height
        )
        
        # Draw background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(indicator_rect, background_color)
        
        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            indicator_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True
        )
        
        # Draw mode text
        self._visual_effects.draw_enhanced_text(
            painter,
            indicator_rect,
            Qt.AlignmentFlag.AlignCenter,
            "SURVEILLANCE MODE",
            glow=True,
            glow_color=self._theme_manager.get_color("hud")
        )
    
    def _generate_sample_terrain_data(self, points: int) -> List[float]:
        """Generate sample terrain data for visualization"""
        import random
        
        # Generate terrain with some randomness but overall mountain-like shape
        data = []
        
        # Base terrain shape (mountain-like)
        for i in range(points):
            # Position in range (0 to 1)
            x = i / (points - 1)
            
            # Base height (mountain in middle)
            base_height = 1.0 - abs(x - 0.5) * 2.0
            
            # Add some randomness
            random_factor = random.uniform(-0.2, 0.2)
            
            # Calculate final height
            height = max(0.1, min(1.0, base_height * 0.8 + random_factor))
            
            data.append(height)
            
        return data
    
    def _generate_sample_signal_data(self, points: int) -> List[float]:
        """Generate sample signal strength data for visualization"""
        import random
        import math
        
        # Generate signal data with some randomness but overall wave-like pattern
        data = []
        
        # Base signal pattern (sine wave)
        for i in range(points):
            # Position in range (0 to 1)
            x = i / (points - 1)
            
            # Base signal (sine wave)
            base_signal = (math.sin(x * 6.0) + 1.0) / 2.0
            
            # Add some randomness
            random_factor = random.uniform(-0.1, 0.1)
            
            # Calculate final signal strength
            signal = max(0.1, min(1.0, base_signal + random_factor))
            
            data.append(signal)
            
        return data
    
    def _generate_sample_tracked_objects(self) -> List[Dict]:
        """Generate sample tracked objects for display"""
        # Create a mix of friendly, enemy, and neutral objects
        objects = []
        
        # Add some friendly objects
        for i in range(3):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, self.range_scale * 0.8)
            
            x = distance * math.sin(angle)
            y = distance * math.cos(angle)
            
            vx = random.uniform(-0.5, 0.5)
            vy = random.uniform(-0.5, 0.5)
            
            objects.append({
                "type": "friendly",
                "position": (x, y),
                "velocity": (vx, vy),
                "threat_level": random.randint(0, 3)
            })
        
        # Add some enemy objects
        for i in range(2):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(self.range_scale * 0.5, self.range_scale * 0.9)
            
            x = distance * math.sin(angle)
            y = distance * math.cos(angle)
            
            vx = random.uniform(-0.8, 0.8)
            vy = random.uniform(-0.8, 0.8)
            
            objects.append({
                "type": "enemy",
                "position": (x, y),
                "velocity": (vx, vy),
                "threat_level": random.randint(6, 10)
            })
        
        # Add some neutral objects
        for i in range(4):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(10, self.range_scale * 0.95)
            
            x = distance * math.sin(angle)
            y = distance * math.cos(angle)
            
            vx = random.uniform(-0.3, 0.3)
            vy = random.uniform(-0.3, 0.3)
            
            objects.append({
                "type": "neutral",
                "position": (x, y),
                "velocity": (vx, vy),
                "threat_level": random.randint(1, 5)
            })
            
        return objects
    
    def _generate_sample_target(self) -> Dict:
        """Generate sample primary target data"""
        # Randomly decide if target is locked
        is_locked = random.random() > 0.7
        
        # Generate target data
        target = {
            "id": f"TGT-{random.randint(1000, 9999)}",
            "type": "FIGHTER" if random.random() > 0.5 else "UAV",
            "range": random.uniform(10, self.range_scale * 0.8),
            "speed": random.uniform(300, 800),
            "heading": random.uniform(0, 359),
            "locked": is_locked
        }
        
        return target
        
    def cleanup(self):
        """Clean up resources and stop animations"""
        try:
            logger.info("[FUTURISTIC_RADAR] Cleaning up resources and stopping animations")
            
            # Stop animation timer
            if hasattr(self, '_animation_timer') and self._animation_timer:
                try:
                    self._animation_timer.stop()
                    logger.info("[FUTURISTIC_RADAR] Stopped animation timer")
                except Exception as timer_error:
                    logger.error(f"[FUTURISTIC_RADAR] Error stopping animation timer: {str(timer_error)}")
            
            # Stop animation controller with robust method detection
            if hasattr(self, '_animation_controller') and self._animation_controller:
                animation_controller_stopped = False
                
                # Try cancel_all_animations first (preferred method)
                if hasattr(self._animation_controller, 'cancel_all_animations'):
                    try:
                        self._animation_controller.cancel_all_animations()
                        logger.info("[FUTURISTIC_RADAR] Cancelled all animations in controller")
                        animation_controller_stopped = True
                    except Exception as cancel_error:
                        logger.error(f"[FUTURISTIC_RADAR] Error cancelling animations: {str(cancel_error)}")
                
                # Try stop method as fallback
                if not animation_controller_stopped and hasattr(self._animation_controller, 'stop'):
                    try:
                        self._animation_controller.stop()
                        logger.info("[FUTURISTIC_RADAR] Stopped animation controller")
                        animation_controller_stopped = True
                    except Exception as stop_error:
                        logger.error(f"[FUTURISTIC_RADAR] Error stopping animation controller: {str(stop_error)}")
                
                # If both methods failed, try to set is_running to False directly
                if not animation_controller_stopped and hasattr(self._animation_controller, '_is_running'):
                    try:
                        self._animation_controller._is_running = False
                        logger.info("[FUTURISTIC_RADAR] Forced animation controller to stop by setting _is_running to False")
                        animation_controller_stopped = True
                    except Exception as attr_error:
                        logger.error(f"[FUTURISTIC_RADAR] Error setting _is_running attribute: {str(attr_error)}")
                
                # If all methods failed, log a warning
                if not animation_controller_stopped:
                    logger.warning("[FUTURISTIC_RADAR] Could not stop animation controller using any available method")
                
            # Clear any other resources that need cleanup
            if hasattr(self, '_settings_panel'):
                try:
                    self._settings_panel.visible = False
                    logger.info("[FUTURISTIC_RADAR] Hidden settings panel")
                except Exception as panel_error:
                    logger.error(f"[FUTURISTIC_RADAR] Error hiding settings panel: {str(panel_error)}")
            
            # Set running flag to false
            self._running = False
            
            logger.info("[FUTURISTIC_RADAR] Cleanup complete")
        except Exception as e:
            logger.error(f"[FUTURISTIC_RADAR] Error during cleanup: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Ensure running flag is set to false even if cleanup fails
            try:
                self._running = False
            except Exception:
                logger.debug("FuturisticRadarDisplay: failed to set _running=False during cleanup", exc_info=True)
    
    def stop(self):
        """Stop the display and clean up resources"""
        logger.info("[FUTURISTIC_RADAR] Stopping display")
        self._running = False
        self.cleanup()
