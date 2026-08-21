"""
Futuristic Primary Flight Display with enhanced visuals and tactical overlays

NOTE (production readiness re-analysis, August 2026): confirmed dead code,
not a bug. pfd_display_factory.py imports FuturisticPFD but its
create_display() only ever branches on "holographic" vs. default
"standard" -- there is no "futuristic" branch, so this class is never
actually instantiated. This reads as an intentional product decision to
retire the futuristic PFD theme rather than an oversight:
theme_manager.py's get_available_display_types() explicitly returns only
["standard", "holographic"], and futuristic_mfd.py's sibling class isn't
even imported by mfd_display_factory.py at all. See PLANNING.md's
Implemented-but-Unwired Subsystems table for the full writeup, including
the other two files (mfd.py, settings_panel.py) with explicit
"removed/changed from futuristic" comments that corroborate this. Left in
place rather than deleted since removing code isn't part of this pass;
flagged here so a future maintainer doesn't mistake this for an
unfinished feature waiting to be wired up.
"""
from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics, QPainterPath, QLinearGradient
from .pfd import PrimaryFlightDisplay
from .visual.theme_manager import get_theme_manager, DisplayTheme
from .visual.effects import VisualEffects
import math
import time
import traceback
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class FuturisticPFD(PrimaryFlightDisplay):
    """Enhanced futuristic primary flight display with advanced visuals and tactical overlays"""
    
    def __init__(self, parent=None):
        """Initialize futuristic primary flight display"""
        super().__init__(parent)
        
        # Set theme to futuristic
        self._theme_manager.set_theme(DisplayTheme.FUTURISTIC)
        
        # Enhanced visual effects
        self._visual_effects = VisualEffects()
        
        # Animation update timer
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(16)  # ~60 FPS
        self._animation_timer.timeout.connect(self._update_animations)
        self._animation_timer.start()
        
        # Last update time for animations
        self._last_update_time = time.time()
        
        # Enhanced display properties
        self.use_enhanced_visuals = True
        self.use_tactical_overlays = True
        self.use_enhanced_targeting = True
        self.use_threat_prioritization = True
        self.use_predictive_tracking = True
        
        # Animation properties
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
    
    def _update_animations(self):
        """Update animations and effects"""
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Update scan line position
        self.scan_line_position = (self.scan_line_position + delta_time * 0.5) % 1.0
        
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
    
    def paint_display(self, painter: QPainter):
        """Paint the Futuristic Primary Flight Display"""
        try:
            # Clear the entire rect with a completely opaque black to prevent overlapping displays
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(0, 0, 0, 255))
            painter.restore()
            
            # Get theme parameters
            use_enhanced_visuals = self._theme_manager.get_style_param("use_gradients", True)
            
            if use_enhanced_visuals:
                # Draw futuristic PFD
                self._draw_futuristic_pfd(painter)
            else:
                # Fall back to standard PFD
                super().paint_display(painter)
                
        except Exception as e:
            logger.error(f"Futuristic PFD paint error: {str(e)}")
            logger.error(traceback.format_exc())
            raise  # Let base class handle the error display
    
    def _draw_futuristic_pfd(self, painter: QPainter):
        """Draw futuristic PFD with enhanced visuals"""
        # Save state
        painter.save()
        
        try:
            # Draw enhanced background
            self._draw_enhanced_background(painter)
            
            # Draw attitude indicator
            self._draw_enhanced_attitude_indicator(painter)
            
            # Draw heading indicator
            self._draw_enhanced_heading_indicator(painter)
            
            # Draw altitude tape
            self._draw_enhanced_altitude_tape(painter)
            
            # Draw airspeed tape
            self._draw_enhanced_airspeed_tape(painter)
            
            # Draw tactical indicators
            self._draw_enhanced_tactical_indicators(painter)
            
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
    
    def _draw_enhanced_background(self, painter: QPainter):
        """Draw enhanced background with grid"""
        # Fill background
        painter.fillRect(self.rect(), self._theme_manager.get_color("background"))
        
        # Draw grid
        grid_type = self._theme_manager.get_style_param("grid_type", "circular")
        
        if grid_type == "circular":
            # Draw circular grid
            center_x = self.width() / 2
            center_y = self.height() / 2
            max_radius = min(self.width(), self.height()) * 0.45
            
            # Draw concentric circles
            for i in range(1, 5):
                radius = max_radius * (i / 4.0)
                
                pen = QPen(self._theme_manager.get_color("grid"))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(center_x, center_y), radius, radius)
            
            # Draw radial lines
            for i in range(0, 8):
                angle = i * (math.pi / 4.0)
                x = center_x + max_radius * math.cos(angle)
                y = center_y + max_radius * math.sin(angle)
                
                painter.drawLine(QPointF(center_x, center_y), QPointF(x, y))
    
    def _draw_scan_line(self, painter: QPainter):
        """Draw animated scan line effect"""
        # Calculate scan line position
        scan_y = self.height() * self.scan_line_position
        
        # Create scan color with pulse effect
        scan_color = QColor(self._theme_manager.get_color("data_primary"))
        scan_color.setAlpha(100)  # Semi-transparent
        
        # Draw scan line
        pen = QPen(scan_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, scan_y), QPointF(self.width(), scan_y))
    
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
            
            # Draw sky and ground
            sky_color = self._theme_manager.get_color("sky")
            ground_color = self._theme_manager.get_color("ground")
            
            # Enhanced sky gradient
            sky_gradient = QLinearGradient(0, -horizon_height, 0, 0)
            sky_gradient.setColorAt(0, sky_color)
            sky_gradient.setColorAt(1, sky_color.lighter(110))
            
            # Enhanced ground gradient
            ground_gradient = QLinearGradient(0, 0, 0, horizon_height)
            ground_gradient.setColorAt(0, ground_color)
            ground_gradient.setColorAt(1, ground_color.darker(110))
            
            # Draw sky and ground with gradients
            sky_rect = QRectF(-horizon_width, -horizon_height, horizon_width * 2, horizon_height)
            ground_rect = QRectF(-horizon_width, 0, horizon_width * 2, horizon_height)
            
            painter.fillRect(sky_rect, sky_gradient)
            painter.fillRect(ground_rect, ground_gradient)
            
            # Draw horizon line
            pen = QPen(self._theme_manager.get_color("horizon_line"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(QPointF(-horizon_width, 0), QPointF(horizon_width, 0))
            
            # Draw pitch ladder
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
                pen = QPen(self._theme_manager.get_color("hud"))
                pen.setWidth(2)
                painter.setPen(pen)
            else:
                # Minor pitch lines (5, 15 degrees)
                pen = QPen(self._theme_manager.get_color("hud"))
                pen.setWidth(1)
                painter.setPen(pen)
            
            painter.drawLine(QPointF(-line_width, y), QPointF(line_width, y))
            
            # Draw pitch number with enhanced visuals
            if pitch != 0:
                text_width = 25
                left_rect = QRectF(-line_width - text_width, y - 10, text_width, 20)
                right_rect = QRectF(line_width + 5, y - 10, text_width, 20)
                
                painter.setPen(self._theme_manager.get_color("hud"))
                painter.drawText(left_rect, Qt.AlignmentFlag.AlignRight, str(abs(pitch)))
                painter.drawText(right_rect, Qt.AlignmentFlag.AlignLeft, str(abs(pitch)))
    
    def _draw_aircraft_reference(self, painter: QPainter):
        """Draw enhanced aircraft reference symbol"""
        # Get theme parameters
        use_angular_design = self._theme_manager.get_style_param("use_angular_design", False)
        
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
            
            # Draw path
            pen = QPen(aircraft_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawPath(path)
        else:
            # Traditional aircraft symbol
            size = 15
            
            # Draw horizontal line
            pen = QPen(aircraft_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(QPointF(-size, 0), QPointF(size, 0))
            
            # Draw vertical line
            painter.drawLine(QPointF(0, -size/2), QPointF(0, size/2))
    
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
        background_color = QColor(0, 0, 0, 180)
        painter.fillRect(box_rect, background_color)
        
        # Draw box border
        pen = QPen(self._theme_manager.get_color("hud"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(box_rect)
        
        # Draw current heading
        text_rect = QRectF(
            center_x - box_width/2,
            heading_y - box_height/2,
            box_width,
            box_height
        )
        painter.setPen(self._theme_manager.get_color("heading_indicator"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.heading):03d}°")
        
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
                    pen = QPen(self._theme_manager.get_color("heading_indicator"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
                    
                    # Draw heading value
                    text_rect = QRectF(x_pos - 15, heading_y - box_height - 15, 30, 15)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(tick_heading):03d}")
                else:
                    # Minor ticks
                    pen = QPen(self._theme_manager.get_color("hud"))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_altitude_tape(self, painter: QPainter):
        """Draw enhanced altitude tape"""
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
        background_color = QColor(0, 0, 0, 180)
        painter.fillRect(box_rect, background_color)
        
        # Draw box border
        pen = QPen(self._theme_manager.get_color("altitude_tape"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(box_rect)
        
        # Draw current altitude
        text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
        painter.setPen(self._theme_manager.get_color("altitude_tape"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.altitude):05d}")
        
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
                    pen = QPen(self._theme_manager.get_color("altitude_tape"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
                    
                    # Draw altitude value
                    text_rect = QRectF(tape_x + 20, y_pos - 10, tape_width - 40, 20)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(tick_alt):05d}")
                else:
                    # Minor ticks
                    pen = QPen(self._theme_manager.get_color("hud"))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_airspeed_tape(self, painter: QPainter):
        """Draw enhanced airspeed tape"""
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
        background_color = QColor(0, 0, 0, 180)
        painter.fillRect(box_rect, background_color)
        
        # Draw box border
        pen = QPen(self._theme_manager.get_color("airspeed_tape"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(box_rect)
        
        # Draw current airspeed
        text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
        painter.setPen(self._theme_manager.get_color("airspeed_tape"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.airspeed):03d}")
        
        # Draw mach number (aircraft specific)
        mach_rect = QRectF(tape_x, tape_y + box_height/2 + 5, tape_width - 10, 20)
        painter.setPen(self._theme_manager.get_color("hud"))
        painter.drawText(mach_rect, Qt.AlignmentFlag.AlignLeft, f"M{self.mach:.3f}")
        
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
                    pen = QPen(self._theme_manager.get_color("airspeed_tape"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
                    
                    # Draw speed value
                    text_rect = QRectF(tape_x + 10, y_pos - 10, tape_width - 20, 20)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(tick_speed):03d}")
                else:
                    # Minor ticks
                    pen = QPen(self._theme_manager.get_color("hud"))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(tick_line)
    
    def _draw_enhanced_tactical_indicators(self, painter: QPainter):
        """Draw enhanced tactical indicators"""
        # Calculate positions based on window size
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
        """Draw enhanced tactical indicator"""
        # Determine color based on value
        if current_value > critical_threshold:
            color = self._theme_manager.get_color("critical")
        elif current_value > warning_threshold:
            color = self._theme_manager.get_color("warning")
        elif current_value > normal_threshold:
            color = self._theme_manager.get_color("energy_state")  # Yellow for elevated but not warning
        else:
            color = self._theme_manager.get_color("hud")  # Normal color
        
        # Draw background
        bg_rect = QRectF(x - width - 5, y - 12, width + 10, 24)
        background_color = QColor(0, 0, 0, 180)
        painter.fillRect(bg_rect, background_color)
        
        # Draw border
        pen = QPen(self._theme_manager.get_color("hud"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(bg_rect)
        
        # Draw label
        label_rect = QRectF(x - width, y - 7, width - 40, 15)
        painter.setPen(self._theme_manager.get_color("hud"))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight, label)
        
        # Draw value
        value_rect = QRectF(x - 40, y - 7, 40, 15)
        painter.setPen(color)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignRight, value)
    
    def _draw_tactical_overlays(self, painter: QPainter):
        """Draw tactical overlays"""
        # Draw threat indicator if threat level is significant
        if self.tactical_data["threat_level"] > 2:
            self._draw_threat_indicator(painter)
        
        # Draw weapon status indicator
        if self.tactical_data["weapon_status"] != "SAFE":
            self._draw_weapon_status_indicator(painter)
    
    def _draw_threat_indicator(self, painter: QPainter):
        """Draw threat direction indicator"""
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
        
        # Draw path
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._theme_manager.get_color("tactical_overlay"))
        painter.drawPath(threat_path)
    
    def _draw_weapon_status_indicator(self, painter: QPainter):
        """Draw weapon status indicator"""
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
        
        # Draw status text
        status_rect = QRectF(status_x - 50, status_y - 10, 100, 20)
        painter.setPen(status_color)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, weapon_status)
