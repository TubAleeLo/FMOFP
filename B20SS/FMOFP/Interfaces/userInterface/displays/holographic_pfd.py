"""
Holographic Primary Flight Display with advanced 3D visualization and tactical overlays
"""
from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics, QPainterPath, QLinearGradient, QRadialGradient, QTransform
from .holographic_display import HolographicDisplay
from .base_display import DisplayType
from .visual.enhanced_theme_manager import get_enhanced_theme_manager, EnhancedDisplayTheme
from .visual.enhanced_effects import get_enhanced_visual_effects
import math
import time
import random
import threading
import traceback
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class HolographicPFD(HolographicDisplay):
    """Advanced holographic primary flight display with 3D visualization and tactical overlays"""
    
    def __init__(self, parent=None):
        """Initialize holographic primary flight display"""
        super().__init__(DisplayType.PFD, parent=parent)
        
        # Set theme to holographic
        self._theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)
        
        # Initialize flight data
        self.altitude = 30000
        self.target_altitude = 30000
        self.vertical_speed = 0
        self.airspeed = 450
        self.target_airspeed = 450
        self.mach = 0.85
        self.heading = 45
        self.pitch = 0
        self.roll = 0
        self.g_force = 1.0
        self.aoa = 5.0
        self.energy_state = 75
        
        # Animation update timer
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(16)  # ~60 FPS
        self._animation_timer.timeout.connect(self._update_animations)
        self._animation_timer.start()
        
        # Last update time for animations
        self._last_update_time = time.time()
        
        # Manual animation timer as a fallback
        from FMOFP.manual_animation_timer import ManualAnimationTimer
        self._manual_animation_timer = ManualAnimationTimer(update_interval=16)  # ~60 FPS
        
        # Enhanced display properties
        self.use_holographic_elements = True
        self.use_parallax_effects = True
        self.use_dynamic_focus = True
        self.use_tactical_overlays = True
        self.use_enhanced_targeting = True
        self.use_threat_prioritization = True
        self.use_predictive_tracking = True
        self.use_environmental_awareness = True
        
        # Holographic display properties
        self.holo_rotation = 0.0  # Rotation angle for 3D effect
        self.holo_rotation_speed = 5.0  # Degrees per second
        self.holo_elevation = 30.0  # Elevation angle for 3D view
        self.holo_perspective = 0.3  # Perspective factor (0.0 to 1.0)
        self.holo_layer_separation = 0.1  # Separation between layers
        self.holo_layers = 3  # Number of layers in holographic display
        
        # Animation properties
        self.layer_animation_offset = 0.0  # Animation offset for layer effects
        self.scan_line_position = 0.0  # Position of scanning line effect
        self.data_refresh_progress = 0.0  # Progress of data refresh animation
        
        # Tactical data
        self.tactical_data = {
            "threat_level": 0,
            "threat_direction": 0,
            "weapon_status": "SAFE",
            "countermeasures": 100,
            "fuel_state": 85,
            "engine_status": "NOMINAL",
            "stealth_mode": False,
            "ecm_status": "STANDBY",
            "target_lock": None,
            "waypoints": []
        }
        
        # Initialize animation controller
        from .visual.animation_controller import AnimationController
        self._animation_controller = AnimationController()
        
        # Initialize animations
        self._init_animations()
        
        # Set up manual animations as a fallback
        self._setup_manual_animations()
    
    def _setup_manual_animations(self):
        """Set up manual animations as a fallback"""
        logger.info("Setting up manual animations for PFD")
        
        # Add scan line animation
        self._manual_animation_timer.add_animation(
            "scan_line",
            lambda value: self._set_scan_line_position_manual(value),
            speed=0.5  # Complete cycle every 2 seconds
        )
        
        # Add rotation animation
        self._manual_animation_timer.add_animation(
            "holo_rotation",
            lambda value: self._set_holo_rotation_manual(value * 360.0),
            speed=0.1  # Complete cycle every 10 seconds
        )
        
        # Add layer offset animation
        self._manual_animation_timer.add_animation(
            "layer_offset",
            lambda value: self._set_layer_animation_offset_manual(value),
            speed=0.2  # Complete cycle every 5 seconds
        )
        
        # Start the manual animation timer
        self._manual_animation_timer.start()
        
    def _set_scan_line_position_manual(self, value):
        """Set scan line position from manual animation"""
        self.scan_line_position = value
        self.update()  # Request repaint
        
    def _set_holo_rotation_manual(self, value):
        """Set holographic rotation angle from manual animation"""
        self.holo_rotation = value
        self.update()  # Request repaint
        
    def _set_layer_animation_offset_manual(self, value):
        """Set layer animation offset from manual animation"""
        self.layer_animation_offset = value
        self.update()  # Request repaint
    
    def _init_animations(self):
        """Initialize animations for display elements"""
        # Rotation animation
        self._animation_controller.create_animation(
            "holo_rotation",
            0.0,
            360.0,
            360.0 / self.holo_rotation_speed,
            lambda value: self._set_holo_rotation(value),
            None,
            QEasingCurve.Type.Linear
        )
        
        # Scan line animation
        self._animation_controller.create_animation(
            "scan_line",
            0.0,
            1.0,
            2.0,
            lambda value: self._set_scan_line_position(value),
            None,
            QEasingCurve.Type.Linear
        )
        
        # Layer offset animation
        self._animation_controller.create_animation(
            "layer_offset",
            0.0,
            1.0,
            5.0,
            lambda value: self._set_layer_animation_offset(value),
            None,
            QEasingCurve.Type.Linear
        )
    
    def _set_holo_rotation(self, value):
        """Set holographic rotation angle"""
        self.holo_rotation = value
    
    def _set_scan_line_position(self, value):
        """Set scan line position"""
        self.scan_line_position = value
    
    def _set_layer_animation_offset(self, value):
        """Set layer animation offset"""
        self.layer_animation_offset = value
    
    def _update_animations(self):
        """Update animations and effects"""
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Update visual effects animations
        self._visual_effects.update_animation_time(delta_time)
        
        # Update data refresh progress
        self.data_refresh_progress = (self.data_refresh_progress + delta_time * 0.2) % 1.0
        
        # Request a repaint
        self.update()
    
    def cleanup(self):
        """Clean up resources"""
        super().cleanup()
        
        # Stop animation timer
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = None
        
        # Stop animation controller
        if self._animation_controller:
            self._animation_controller.stop()
            self._animation_controller = None
            
        # Stop manual animation timer
        if self._manual_animation_timer:
            self._manual_animation_timer.stop()
            self._manual_animation_timer = None
            logger.info("Stopped manual animation timer")
    
    def paint_display(self, painter: QPainter):
        """Paint the Holographic Primary Flight Display"""
        try:
            # Get theme parameters
            use_holographic_elements = self._theme_manager.get_style_param("use_holographic_elements", True)
            
            if use_holographic_elements:
                # Draw holographic PFD
                self._draw_holographic_pfd(painter)
            else:
                # Fall back to standard PFD
                super().paint_display(painter)
                
        except Exception as e:
            logger.error(f"Holographic PFD paint error: {str(e)}")
            logger.error(traceback.format_exc())
            raise  # Let base class handle the error display
    
    def _draw_holographic_pfd(self, painter: QPainter):
        """Draw holographic PFD with 3D layered effect"""
        # Save state
        painter.save()
        
        try:
            # Draw layered background
            self._visual_effects.draw_layered_background(
                painter, 
                self.rect(),
                base_color=self._theme_manager.get_color("background"),
                grid_color=self._theme_manager.get_color("grid"),
                grid_type=self._theme_manager.get_style_param("grid_type", "hexagonal")
            )
            
            # Draw holographic layers
            for layer in range(self.holo_layers):
                # Calculate layer offset
                layer_offset = (layer / (self.holo_layers - 1)) * self.holo_layer_separation
                layer_z = layer_offset * 2.0 - 1.0  # -1.0 to 1.0
                
                # Apply animation offset
                animation_phase = (self.layer_animation_offset + layer / self.holo_layers) % 1.0
                layer_animation = math.sin(animation_phase * 2.0 * math.pi) * 0.05
                
                # Calculate layer transform
                layer_scale = 1.0 - layer_z * self.holo_perspective
                layer_opacity = 1.0 - abs(layer_z) * 0.5
                
                # Apply transform
                painter.save()
                
                # Translate to center
                center_x = self.width() / 2
                center_y = self.height() / 2
                painter.translate(center_x, center_y)
                
                # Apply rotation for 3D effect
                layer_rotation = self.holo_rotation * layer_z * 0.2
                painter.rotate(layer_rotation)
                
                # Apply scale
                painter.scale(layer_scale, layer_scale)
                
                # Translate back
                painter.translate(-center_x, -center_y)
                
                # Set layer opacity
                painter.setOpacity(layer_opacity)
                
                # Draw layer elements
                self._draw_pfd_layer(
                    painter, 
                    layer, 
                    layer_z + layer_animation
                )
                
                painter.restore()
            
            # Draw holographic frame
            self._draw_holographic_frame(painter)
            
            # Draw scan line effect
            self._draw_scan_line(painter)
            
            # Draw tactical overlays
            if self.use_tactical_overlays:
                self._draw_tactical_overlays(painter)
            
            # Draw flight mode indicator
            self.draw_flight_mode_indicator(painter)
            
            # Draw envelope warnings
            self.draw_envelope_warnings(painter)
            
        finally:
            # Restore state
            painter.restore()
    
    def _draw_pfd_layer(self, painter: QPainter, layer: int, layer_z: float):
        """Draw elements for a specific holographic layer"""
        # Different elements on different layers
        if layer == 0:  # Bottom layer
            # Draw attitude indicator background
            self._draw_enhanced_attitude_background(painter)
            
            # Draw grid
            grid_type = self._theme_manager.get_style_param("grid_type", "hexagonal")
            
            if grid_type == "hexagonal":
                # Calculate center and radius for hexagonal grid
                center_x = self.width() / 2
                center_y = self.height() / 2
                radius = min(self.width(), self.height()) * 0.4
                
                self._visual_effects.draw_hexagonal_grid(
                    painter, 
                    QPointF(center_x, center_y), 
                    radius,
                    color=self._theme_manager.get_color("grid"),
                    rings=4,
                    glow=True
                )
                
        elif layer == 1:  # Middle layer
            # Draw attitude indicator
            self._draw_enhanced_attitude_indicator(painter)
            
            # Draw heading indicator
            self._draw_enhanced_heading_indicator(painter)
            
        elif layer == 2:  # Top layer
            # Draw altitude tape
            self._draw_enhanced_altitude_tape(painter)
            
            # Draw airspeed tape
            self._draw_enhanced_airspeed_tape(painter)
            
            # Draw tactical indicators
            self._draw_enhanced_tactical_indicators(painter)
    
    def _draw_scan_line(self, painter: QPainter):
        """Draw animated scan line effect"""
        # Calculate scan line position
        scan_y = self.height() * self.scan_line_position
        
        # Create scan color with pulse effect
        scan_color = QColor(self._theme_manager.get_color("data_primary"))
        scan_color.setAlpha(100)  # Semi-transparent
        
        # Draw scan line with glow
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(0, scan_y),
            QPointF(self.width(), scan_y),
            color=scan_color,
            width=2.0,
            glow=True
        )
    
    def _draw_holographic_frame(self, painter: QPainter):
        """Draw holographic frame around display"""
        # Create frame rect
        frame_rect = self.rect().adjusted(5, 5, -5, -5)
        
        # Draw angular frame with glow
        self._visual_effects.draw_angular_frame(
            painter,
            frame_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True
        )
        
        # Draw holographic elements in corners
        self._draw_corner_elements(painter)
    
    def _draw_corner_elements(self, painter: QPainter):
        """Draw holographic elements in corners of display"""
        # Calculate corner positions
        corner_size = 40
        
        # Top-left corner
        tl_rect = QRectF(
            10,
            10,
            corner_size,
            corner_size
        )
        
        # Top-right corner
        tr_rect = QRectF(
            self.width() - corner_size - 10,
            10,
            corner_size,
            corner_size
        )
        
        # Bottom-left corner
        bl_rect = QRectF(
            10,
            self.height() - corner_size - 10,
            corner_size,
            corner_size
        )
        
        # Bottom-right corner
        br_rect = QRectF(
            self.width() - corner_size - 10,
            self.height() - corner_size - 10,
            corner_size,
            corner_size
        )
        
        # Draw corner elements
        self._draw_corner_element(painter, tl_rect, "TL")
        self._draw_corner_element(painter, tr_rect, "TR")
        self._draw_corner_element(painter, bl_rect, "BL")
        self._draw_corner_element(painter, br_rect, "BR")
    
    def _draw_corner_element(self, painter: QPainter, rect: QRectF, corner: str):
        """Draw holographic element in a corner"""
        # Save state
        painter.save()
        
        try:
            # Get corner center
            center_x = rect.x() + rect.width() / 2
            center_y = rect.y() + rect.height() / 2
            
            # Draw different elements based on corner
            if corner == "TL":
                # Draw system status indicator
                self._draw_system_status(painter, rect)
            elif corner == "TR":
                # Draw data refresh indicator
                self._draw_data_refresh_indicator(painter, rect)
            elif corner == "BL":
                # Draw fuel status
                self._draw_fuel_status(painter, rect)
            elif corner == "BR":
                # Draw tactical status
                self._draw_tactical_status(painter, rect)
                
        finally:
            # Restore state
            painter.restore()
    
    def _draw_system_status(self, painter: QPainter, rect: QRectF):
        """Draw system status indicator"""
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
        
        # Draw status text
        status_rect = rect.adjusted(5, 5, -5, -5)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignCenter,
            "SYS OK",
            glow=True,
            glow_color=self._theme_manager.get_color("system_normal")
        )
    
    def _draw_data_refresh_indicator(self, painter: QPainter, rect: QRectF):
        """Draw data refresh indicator"""
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
        
        # Draw refresh progress
        progress_rect = rect.adjusted(5, rect.height() - 10, -5, -5)
        
        # Calculate progress width
        progress_width = progress_rect.width() * self.data_refresh_progress
        
        # Draw progress bar
        progress_fill_rect = QRectF(
            progress_rect.x(),
            progress_rect.y(),
            progress_width,
            progress_rect.height()
        )
        
        painter.fillRect(progress_fill_rect, self._theme_manager.get_color("data_primary"))
        
        # Draw refresh text
        text_rect = rect.adjusted(5, 5, -5, -15)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            "DATA",
            glow=True,
            glow_color=self._theme_manager.get_color("data_primary")
        )
    
    def _draw_fuel_status(self, painter: QPainter, rect: QRectF):
        """Draw fuel status indicator"""
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
        
        # Draw fuel level
        fuel_level = self.tactical_data["fuel_state"]
        
        # Determine color based on fuel level
        if fuel_level < 20:
            fuel_color = self._theme_manager.get_color("critical")
        elif fuel_level < 40:
            fuel_color = self._theme_manager.get_color("warning")
        else:
            fuel_color = self._theme_manager.get_color("system_normal")
        
        # Draw fuel text
        text_rect = rect.adjusted(5, 5, -5, -5)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{fuel_level}%",
            glow=fuel_level < 40,
            glow_color=fuel_color
        )
    
    def _draw_tactical_status(self, painter: QPainter, rect: QRectF):
        """Draw tactical status indicator"""
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
        
        # Draw weapon status
        weapon_status = self.tactical_data["weapon_status"]
        
        # Determine color based on weapon status
        if weapon_status == "ARMED":
            status_color = self._theme_manager.get_color("warning")
            glow = True
        elif weapon_status == "FIRING":
            status_color = self._theme_manager.get_color("critical")
            glow = True
        else:  # SAFE
            status_color = self._theme_manager.get_color("system_normal")
            glow = False
        
        # Draw status text
        text_rect = rect.adjusted(5, 5, -5, -5)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            weapon_status,
            glow=glow,
            glow_color=status_color
        )
    
    def _draw_enhanced_attitude_background(self, painter: QPainter):
        """Draw enhanced attitude indicator background"""
        # Calculate center point
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Calculate horizon size based on window size
        horizon_width = min(self.width() / 3, 300)
        horizon_height = min(self.height() / 3, 200)
        
        # Save state
        painter.save()
        
        try:
            # Move to center and rotate for roll
            painter.translate(center_x, center_y)
            painter.rotate(-self.roll)
            
            # Enhanced sky gradient
            sky_gradient = QLinearGradient(0, -horizon_height, 0, 0)
            sky_color = self._theme_manager.get_color("sky")
            
            # Create darker color for upper sky
            upper_sky = QColor(sky_color)
            upper_sky.setRed(max(0, upper_sky.red() - 30))
            upper_sky.setGreen(max(0, upper_sky.green() - 20))
            upper_sky.setBlue(max(0, upper_sky.blue() - 10))
            
            sky_gradient.setColorAt(0, upper_sky)
            sky_gradient.setColorAt(1, sky_color)
            
            # Enhanced ground gradient
            ground_gradient = QLinearGradient(0, 0, 0, horizon_height)
            ground_color = self._theme_manager.get_color("ground")
            
            # Create darker color for lower ground
            lower_ground = QColor(ground_color)
            lower_ground.setRed(max(0, lower_ground.red() - 20))
            lower_ground.setGreen(max(0, lower_ground.green() - 20))
            lower_ground.setBlue(max(0, lower_ground.blue() - 20))
            
            ground_gradient.setColorAt(0, ground_color)
            ground_gradient.setColorAt(1, lower_ground)
            
            # Draw sky and ground with gradients
            sky_rect = QRectF(-horizon_width, -horizon_height, horizon_width * 2, horizon_height)
            ground_rect = QRectF(-horizon_width, 0, horizon_width * 2, horizon_height)
            
            painter.fillRect(sky_rect, sky_gradient)
            painter.fillRect(ground_rect, ground_gradient)
            
            # Draw horizon line with glow effect
            horizon_line = QLineF(QPointF(-horizon_width, 0), QPointF(horizon_width, 0))
            self._visual_effects.draw_enhanced_line(
                painter,
                horizon_line.p1(),
                horizon_line.p2(),
                color=self._theme_manager.get_color("horizon_line"),
                width=2.0,
                glow=True
            )
            
        finally:
            # Restore state
            painter.restore()
    
    def _draw_enhanced_attitude_indicator(self, painter: QPainter):
        """Draw enhanced attitude indicator"""
        # Calculate center point
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Calculate horizon size based on window size
        horizon_width = min(self.width() / 3, 300)
        horizon_height = min(self.height() / 3, 200)
        
        # Save state
        painter.save()
        
        try:
            # Move to center and rotate for roll
            painter.translate(center_x, center_y)
            painter.rotate(-self.roll)
            
            # Draw enhanced pitch ladder
            self._draw_enhanced_pitch_ladder(painter, horizon_width)
            
            # Draw aircraft reference symbol
            self._draw_aircraft_reference(painter)
            
        finally:
            # Restore state
            painter.restore()
    
    def _draw_enhanced_pitch_ladder(self, painter: QPainter, horizon_width: float):
        """Draw enhanced pitch ladder"""
        # Calculate pitch line spacing based on window size
        pitch_spacing = min(self.height() / 30, 4)  # pixels per degree
        
        # Adjust for current pitch
        pitch_offset = self.pitch * pitch_spacing
        
        # Draw pitch lines every 5 degrees with enhanced visuals
        for pitch in range(-40, 41, 5):
            y = -pitch * pitch_spacing + pitch_offset
            
            # Skip if outside visible area
            if abs(y) > horizon_width:
                continue
            
            # Determine line width based on pitch value
            line_width = horizon_width/2.5 if pitch % 10 == 0 else horizon_width/3.5
            
            # Draw main line with enhanced visuals
            if pitch == 0:
                # Horizon line already drawn
                continue
            elif pitch % 10 == 0:
                # Major pitch lines (10, 20 degrees)
                # Draw with glow effect
                line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                self._visual_effects.draw_enhanced_line(
                    painter,
                    line.p1(),
                    line.p2(),
                    color=self._theme_manager.get_color("hud"),
                    width=1.5,
                    glow=True
                )
            else:
                # Minor pitch lines (5, 15 degrees)
                line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                painter.setPen(self._theme_manager.get_color("hud"))
                painter.drawLine(line)
            
            # Draw pitch number with enhanced visuals
            if pitch != 0:
                text_width = 25
                left_rect = QRectF(-line_width - text_width, y - 10, text_width, 20)
                right_rect = QRectF(line_width + 5, y - 10, text_width, 20)
                
                if abs(pitch) % 10 == 0:
                    # Draw major pitch numbers with glow
                    self._visual_effects.draw_enhanced_text(
                        painter,
                        left_rect,
                        Qt.AlignmentFlag.AlignRight,
                        str(abs(pitch)),
                        glow=True,
                        glow_color=self._theme_manager.get_color("hud")
                    )
                    
                    self._visual_effects.draw_enhanced_text(
                        painter,
                        right_rect,
                        Qt.AlignmentFlag.AlignLeft,
                        str(abs(pitch)),
                        glow=True,
                        glow_color=self._theme_manager.get_color("hud")
                    )
                else:
                    # Draw regular
                    painter.setPen(self._theme_manager.get_color("hud"))
                    painter.drawText(left_rect, Qt.AlignmentFlag.AlignRight, str(abs(pitch)))
                    painter.drawText(right_rect, Qt.AlignmentFlag.AlignLeft, str(abs(pitch)))
    
    def _draw_aircraft_reference(self, painter: QPainter):
        """Draw enhanced aircraft reference symbol"""
        # Get theme parameters
        use_angular_design = self._theme_manager.get_style_param("use_angular_design", True)
        
        # Set color for aircraft symbol
        aircraft_color = self._theme_manager.get_color("hud")
        
        # Draw aircraft symbol based on design style
        if use_angular_design:
            # Angular aircraft symbol
            size = 20
            
            # Create path for angular aircraft
            path = QPainterPath()
            
            # Left wing
            path.moveTo(-size, 0)
            path.lineTo(-size/2, 0)
            
            # Fuselage
            path.lineTo(-size/4, -size/4)
            path.lineTo(0, -size/4)
            path.lineTo(size/4, -size/4)
            path.lineTo(size/2, 0)
            
            # Right wing
            path.lineTo(size, 0)
            
            # Draw with glow
            self._visual_effects.draw_enhanced_path(
                painter,
                path,
                color=aircraft_color,
                fill=False,
                glow=True
            )
        else:
            # Traditional aircraft symbol
            size = 15
            
            # Draw horizontal line
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(-size, 0),
                QPointF(size, 0),
                color=aircraft_color,
                width=2.0,
                glow=True
            )
            
            # Draw vertical line
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(0, -size/2),
                QPointF(0, size/2),
                color=aircraft_color,
                width=2.0,
                glow=True
            )
    
    def _draw_enhanced_heading_indicator(self, painter: QPainter):
        """Draw enhanced heading indicator"""
        # Calculate positions based on window size
        center_x = self.width() / 2
        heading_y = self.height() / 10
        box_width = min(self.width() / 16, 50)
        box_height = 30
        
        # Draw heading box with enhanced visuals
        box_rect = QRectF(
            center_x - box_width/2,
            heading_y - box_height/2,
            box_width,
            box_height
        )
        
        # Draw box with gradient background
        self._visual_effects.draw_rect(
            painter,
            box_rect,
            color=self._theme_manager.get_color("hud"),
            fill=True,
            fill_color=QColor(0, 0, 0, 180),
            corner_radius=self._theme_manager.get_style_param("corner_radius", 0.0)
        )
        
        # Draw current heading with glow effect
        text_rect = QRectF(
            center_x - box_width/2,
            heading_y - box_height/2,
            box_width,
            box_height
        )
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self.heading):03d}°",
            glow=True,
            glow_color=self._theme_manager.get_color("heading_indicator")
        )
        
        # Draw compass ticks with enhanced visuals
        tick_spacing = box_width * 1.2
        for i in range(-3, 4):
            tick_heading = (self.heading + (i * 10)) % 360
            x_pos = center_x + (i * tick_spacing)
            
            if i != 0:  # Don't draw over the main heading
                # Draw tick mark
                tick_line = QLineF(
                    QPointF(x_pos, heading_y - box_height/2),
                    QPointF(x_pos, heading_y - box_height/4)
                )
                
                if i % 2 == 0:
                    # Major ticks (every 20 degrees)
                    self._visual_effects.draw_enhanced_line(
                        painter,
                        tick_line.p1(),
                        tick_line.p2(),
                        color=self._theme_manager.get_color("heading_indicator"),
                        width=1.5,
                        glow=True
                    )
                    
                    # Draw heading value
                    text_rect = QRectF(x_pos - 15, heading_y - box_height - 15, 30, 15)
                    self._visual_effects.draw_enhanced_text(
                        painter,
                        text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{int(tick_heading):03d}",
                        glow=False,
                        glow_color=self._theme_manager.get_color("heading_indicator")
                    )
                else:
                    # Minor ticks
                    painter.setPen(self._theme_manager.get_color("hud"))
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_altitude_tape(self, painter: QPainter):
        """Draw enhanced altitude tape with holographic effects"""
        # Calculate positions based on window size
        tape_width = min(self.width() / 8, 80)
        tape_x = self.width() - tape_width - 20
        tape_y = self.height() / 2
        
        # Get theme parameters
        corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)
        
        # Draw altitude box with enhanced visuals
        box_height = 30
        box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)
        
        # Draw box with gradient background
        self._visual_effects.draw_rect(
            painter,
            box_rect,
            color=self._theme_manager.get_color("altitude_tape"),
            fill=True,
            fill_color=QColor(0, 0, 0, 180),
            corner_radius=corner_radius
        )
        
        # Draw current altitude with glow effect
        text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self.altitude):05d}",
            glow=True,
            glow_color=self._theme_manager.get_color("altitude_tape")
        )
        
        # Draw target altitude if different from current
        if abs(self.target_altitude - self.altitude) > 100:
            target_y = tape_y + ((self.altitude - self.target_altitude) / 100) * (box_height * 0.8)
            
            # Draw target marker
            target_width = 8
            target_height = 12
            target_x = tape_x + tape_width - 5
            
            # Create triangle pointing to tape
            target_path = QPainterPath()
            target_path.moveTo(target_x, target_y)
            target_path.lineTo(target_x - target_width, target_y - target_height/2)
            target_path.lineTo(target_x - target_width, target_y + target_height/2)
            target_path.closeSubpath()
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._theme_manager.get_color("target_tracking"))
            painter.drawPath(target_path)
            
            # Draw small text with target value
            text_rect = QRectF(tape_x, target_y - 8, tape_width - 20, 16)
            painter.setPen(self._theme_manager.get_color("target_tracking"))
            painter.setFont(QFont("Arial", 7))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight, f"{int(self.target_altitude):05d}")
            painter.setFont(QFont("Arial", 8))  # Reset font
        
        # Draw vertical speed indicator
        if abs(self.vertical_speed) > 50:
            vs_x = tape_x - 15
            vs_y = tape_y
            vs_width = 12
            vs_height = 50
            
            # Normalize vertical speed for display
            normalized_vs = max(-1.0, min(1.0, self.vertical_speed / 2000))
            arrow_height = normalized_vs * (vs_height / 2)
            
            # Draw arrow path
            vs_path = QPainterPath()
            if normalized_vs > 0:
                # Up arrow
                vs_path.moveTo(vs_x, vs_y - arrow_height)
                vs_path.lineTo(vs_x - vs_width/2, vs_y)
                vs_path.lineTo(vs_x + vs_width/2, vs_y)
            else:
                # Down arrow
                vs_path.moveTo(vs_x, vs_y - arrow_height)
                vs_path.lineTo(vs_x - vs_width/2, vs_y)
                vs_path.lineTo(vs_x + vs_width/2, vs_y)
            
            vs_path.closeSubpath()
            
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Color based on climb/descent
            if normalized_vs > 0:
                painter.setBrush(self._theme_manager.get_color("system_normal"))  # Green for climb
            else:
                painter.setBrush(self._theme_manager.get_color("warning"))  # Orange for descent
            
            painter.drawPath(vs_path)
            
            # Draw text with vertical speed value
            text_rect = QRectF(vs_x - 25, vs_y - arrow_height - 10, 50, 20)
            painter.setPen(self._theme_manager.get_color("hud"))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{abs(int(self.vertical_speed))}")
        
        # Draw altitude ticks with enhanced visuals
        tick_spacing = box_height * 0.8
        for i in range(-5, 6):
            tick_alt = self.altitude + (i * 100)
            y_pos = tape_y + (i * tick_spacing)
            
            if i != 0:  # Don't draw over the main altitude
                # Draw tick mark
                tick_line = QLineF(
                    QPointF(tape_x + tape_width - 20, y_pos),
                    QPointF(tape_x + tape_width - 10, y_pos)
                )
                
                if i % 2 == 0:
                    # Major ticks (every 200 ft)
                    self._visual_effects.draw_enhanced_line(
                        painter,
                        tick_line.p1(),
                        tick_line.p2(),
                        color=self._theme_manager.get_color("altitude_tape"),
                        width=1.5,
                        glow=False
                    )
                    
                    # Draw altitude value
                    text_rect = QRectF(tape_x + 20, y_pos - 10, tape_width - 40, 20)
                    self._visual_effects.draw_enhanced_text(
                        painter,
                        text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{int(tick_alt):05d}",
                        glow=False,
                        glow_color=self._theme_manager.get_color("altitude_tape")
                    )
                else:
                    # Minor ticks
                    painter.setPen(self._theme_manager.get_color("hud"))
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_airspeed_tape(self, painter: QPainter):
        """Draw enhanced airspeed tape with holographic effects"""
        # Calculate positions based on window size
        tape_width = min(self.width() / 8, 70)
        tape_x = 20
        tape_y = self.height() / 2
        
        # Get theme parameters
        corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)
        
        # Draw airspeed box with enhanced visuals
        box_height = 30
        box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)
        
        # Draw box with gradient background
        self._visual_effects.draw_rect(
            painter,
            box_rect,
            color=self._theme_manager.get_color("airspeed_tape"),
            fill=True,
            fill_color=QColor(0, 0, 0, 180),
            corner_radius=corner_radius
        )
        
        # Draw current airspeed with glow effect
        text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self.airspeed):03d}",
            glow=True,
            glow_color=self._theme_manager.get_color("airspeed_tape")
        )
        
        # Draw mach number (aircraft specific) - repositioned to avoid overlap
        mach_rect = QRectF(tape_x, tape_y + box_height/2 + 5, tape_width - 10, 20)
        painter.setPen(self._theme_manager.get_color("hud"))
        painter.drawText(mach_rect, Qt.AlignmentFlag.AlignLeft, f"M{self.mach:.3f}")
        
        # Draw target airspeed if different from current
        if abs(self.target_airspeed - self.airspeed) > 5:
            target_y = tape_y + ((self.airspeed - self.target_airspeed) / 10) * (box_height * 0.8)
            
            # Draw target marker
            target_width = 8
            target_height = 12
            target_x = tape_x - 5
            
            # Create triangle pointing to tape
            target_path = QPainterPath()
            target_path.moveTo(target_x, target_y)
            target_path.lineTo(target_x + target_width, target_y - target_height/2)
            target_path.lineTo(target_x + target_width, target_y + target_height/2)
            target_path.closeSubpath()
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._theme_manager.get_color("target_tracking"))
            painter.drawPath(target_path)
            
            # Draw small text with target value
            text_rect = QRectF(tape_x, target_y - 8, tape_width - 20, 16)
            painter.setPen(self._theme_manager.get_color("target_tracking"))
            painter.setFont(QFont("Arial", 7))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, f"{int(self.target_airspeed):03d}")
            painter.setFont(QFont("Arial", 8))  # Reset font
        
        # Draw speed ticks with enhanced visuals
        tick_spacing = box_height * 0.8
        for i in range(-5, 6):
            tick_speed = self.airspeed + (i * 10)
            y_pos = tape_y + (i * tick_spacing)
            
            if i != 0:  # Don't draw over the main speed
                # Draw tick mark
                tick_line = QLineF(
                    QPointF(tape_x - 10, y_pos),
                    QPointF(tape_x, y_pos)
                )
                
                if i % 2 == 0:
                    # Major ticks (every 20 knots)
                    self._visual_effects.draw_enhanced_line(
                        painter,
                        tick_line.p1(),
                        tick_line.p2(),
                        color=self._theme_manager.get_color("airspeed_tape"),
                        width=1.5,
                        glow=False
                    )
                    
                    # Draw speed value
                    text_rect = QRectF(tape_x + 10, y_pos - 10, tape_width - 20, 20)
                    self._visual_effects.draw_enhanced_text(
                        painter,
                        text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{int(tick_speed):03d}",
                        glow=False,
                        glow_color=self._theme_manager.get_color("airspeed_tape")
                    )
                else:
                    # Minor ticks
                    painter.setPen(self._theme_manager.get_color("hud"))
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_tactical_indicators(self, painter: QPainter):
        """Draw enhanced tactical indicators with holographic effects"""
        # Calculate positions based on window size - moved to bottom of display
        left_margin = 20
        tactical_x = left_margin + 120  # Position on left side of display
        tactical_y_start = self.height() - 100  # Position at bottom of display
        tactical_spacing = 30
        tactical_width = 120
        
        # Draw tactical indicators with enhanced visuals
        # 1. G-Force indicator
        g_force_y = tactical_y_start
        self._draw_enhanced_tactical_value(
            painter, 
            "G-FORCE", 
            f"{self.g_force:.1f}",
            tactical_x, 
            g_force_y, 
            tactical_width,
            self.g_force,
            2.0,  # Normal G threshold
            6.0,  # Warning G threshold
            8.0   # Critical G threshold
        )
        
        # 2. Angle of Attack (AOA) indicator
        aoa_y = tactical_y_start + tactical_spacing
        self._draw_enhanced_tactical_value(
            painter, 
            "AOA", 
            f"{self.aoa:.1f}°",
            tactical_x, 
            aoa_y, 
            tactical_width,
            self.aoa,
            10.0,  # Normal AOA threshold
            18.0,  # Warning AOA threshold
            22.0   # Critical AOA threshold
        )
        
        # 3. Energy state indicator
        energy_y = tactical_y_start + tactical_spacing * 2
        self._draw_enhanced_tactical_value(
            painter, 
            "ENERGY", 
            f"{self.energy_state}%",
            tactical_x, 
            energy_y, 
            tactical_width,
            self.energy_state,
            30.0,  # Low energy threshold
            60.0,  # Medium energy threshold
            90.0   # High energy threshold
        )
    
    def _draw_enhanced_tactical_value(self, painter: QPainter, label: str, value: str, 
                                    x: float, y: float, width: float, 
                                    current_value: float, normal_threshold: float, 
                                    warning_threshold: float, critical_threshold: float):
        """Draw enhanced tactical indicator with holographic effects"""
        # Determine color based on value
        if current_value > critical_threshold:
            color = self._theme_manager.get_color("critical")
            glow = True
        elif current_value > warning_threshold:
            color = self._theme_manager.get_color("warning")
            glow = True
        elif current_value > normal_threshold:
            color = self._theme_manager.get_color("energy_state")  # Yellow for elevated but not warning
            glow = False
        else:
            color = self._theme_manager.get_color("hud")  # Normal color
            glow = False
        
        # Draw background with angular frame
        bg_rect = QRectF(x - width - 5, y - 12, width + 10, 24)
        
        self._visual_effects.draw_rect(
            painter,
            bg_rect,
            color=self._theme_manager.get_color("hud"),
            fill=True,
            fill_color=QColor(0, 0, 0, 180),
            corner_radius=0.0
        )
        
        # Draw label
        label_rect = QRectF(x - width, y - 7, width - 40, 15)
        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignRight,
            label,
            glow=False,
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw value
        value_rect = QRectF(x - 40, y - 7, 40, 15)
        self._visual_effects.draw_enhanced_text(
            painter,
            value_rect,
            Qt.AlignmentFlag.AlignRight,
            value,
            glow=glow,
            glow_color=color
        )
    
    def _draw_tactical_overlays(self, painter: QPainter):
        """Draw tactical overlays with holographic effects"""
        # Draw threat indicator if threat level is significant
        if self.tactical_data["threat_level"] > 2:
            self._draw_threat_indicator(painter)
        
        # Draw weapon status indicator
        if self.tactical_data["weapon_status"] != "SAFE":
            self._draw_weapon_status_indicator(painter)
    
    def _draw_threat_indicator(self, painter: QPainter):
        """Draw threat direction indicator with holographic effects"""
        # Calculate center and radius
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) * 0.45
        
        # Get threat data
        threat_level = self.tactical_data["threat_level"]
        threat_direction = self.tactical_data["threat_direction"]
        
        # Calculate threat position on perimeter
        angle_rad = math.radians(threat_direction)
        threat_x = center_x + radius * math.sin(angle_rad)
        threat_y = center_y - radius * math.cos(angle_rad)
        
        # Draw threat indicator
        threat_size = 15 + threat_level * 2  # Size based on threat level
        
        # Create threat marker path
        threat_path = QPainterPath()
        threat_path.moveTo(threat_x, threat_y)
        threat_path.lineTo(threat_x - threat_size/2, threat_y - threat_size/2)
        threat_path.lineTo(threat_x + threat_size/2, threat_y - threat_size/2)
        threat_path.closeSubpath()
        
        # Draw with glow
        self._visual_effects.draw_enhanced_path(
            painter,
            threat_path,
            color=self._theme_manager.get_color("tactical_overlay"),
            fill=True,
            glow=True
        )
    
    def _draw_weapon_status_indicator(self, painter: QPainter):
        """Draw weapon status indicator with holographic effects"""
        # Calculate position
        status_x = self.width() / 2
        status_y = self.height() - 20
        
        # Get weapon status
        weapon_status = self.tactical_data["weapon_status"]
        
        # Determine color based on status
        if weapon_status == "ARMED":
            status_color = self._theme_manager.get_color("warning")
        elif weapon_status == "FIRING":
            status_color = self._theme_manager.get_color("critical")
        else:
            status_color = self._theme_manager.get_color("hud")
        
        # Draw status text with glow
        status_rect = QRectF(status_x - 50, status_y - 10, 100, 20)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignCenter,
            weapon_status,
            glow=True,
            glow_color=status_color
        )
    
    def draw_flight_mode_indicator(self, painter: QPainter):
        """Draw flight mode indicator with holographic effects"""
        # Calculate position
        mode_x = self.width() / 2
        mode_y = 20
        
        # Example flight modes
        flight_mode = "CRUISE"
        autopilot_mode = "ENGAGED"
        
        # Draw mode text with glow
        mode_rect = QRectF(mode_x - 100, mode_y - 10, 200, 20)
        
        self._visual_effects.draw_enhanced_text(
            painter,
            mode_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{flight_mode} - AP {autopilot_mode}",
            glow=True,
            glow_color=self._theme_manager.get_color("data_primary")
        )
    
    def draw_envelope_warnings(self, painter: QPainter):
        """Draw flight envelope warnings with holographic effects"""
        # Check for envelope violations
        warnings = []
        
        # Example envelope checks
        if self.airspeed > 500:
            warnings.append("OVERSPEED")
        if self.g_force > 7.0:
            warnings.append("G-LIMIT")
        if self.aoa > 20.0:
            warnings.append("AOA HIGH")
        
        # Draw warnings if any
        if warnings:
            # Calculate position
            warning_x = self.width() / 2
            warning_y = 50
            
            # Draw warning text with glow
            warning_rect = QRectF(warning_x - 150, warning_y - 15, 300, 30)
            
            self._visual_effects.draw_enhanced_text(
                painter,
                warning_rect,
                Qt.AlignmentFlag.AlignCenter,
                " - ".join(warnings),
                glow=True,
                glow_color=self._theme_manager.get_color("critical")
            )
