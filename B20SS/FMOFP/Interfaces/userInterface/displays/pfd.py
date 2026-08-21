from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics, QLinearGradient, QPainterPath
from .base_display import BaseDisplay, DisplayType
import math
import threading
import time
import traceback
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
from FMOFP.Systems.flightManagementSys.fmsControl import get_fms_control

logger = get_logger()

class PrimaryFlightDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(DisplayType.PFD, parent=parent)
        # Basic flight parameters
        self.altitude = 30000
        self.airspeed = 450
        self.heading = 45
        self.pitch = 0
        self.roll = 0

        # Extended flight parameters from FMS
        self.vertical_speed = 0     # feet per minute
        self.mach = 0.75            # Mach number
        self.g_force = 1.0          # G-force
        self.aoa = 0                # Angle of attack in degrees
        self.sideslip = 0           # Sideslip angle in degrees
        self.energy_state = 50      # Energy state (0-100)

        # Flight mode from FMS
        self.flight_mode = "NORMAL"  # Current FMS mode
        self.warnings = []           # Active warnings

        # Autopilot target values
        self.target_altitude = 30000
        self.target_airspeed = 450
        self.target_heading = 45
        self.target_vertical_speed = 0

        # Envelope warnings
        self.envelope_warnings = []

        # Colors for display elements
        self.warning_color = QColor(255, 80, 0)   # Orange for warnings
        self.target_color = QColor(0, 255, 150)   # Green for target values
        self.energy_color = QColor(255, 255, 0)   # Yellow for energy state
        self.critical_color = QColor(255, 0, 0)   # Red for critical indicators

        # Connect to FMS
        self.fms = get_flightManagementSystem()
        self.fms_control = get_fms_control()

        # Data update timer
        self.update_timer = None
        self.lock = threading.Lock()

        # Start data update timer
        self.start_fms_updates()

    def start_fms_updates(self):
        """Start timer to update flight data from FMS"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_flight_data)
        self.update_timer.start(16)  # Update at ~60Hz
        logger.info("PFD started FMS data updates")

    def update_flight_data(self):
        """Update flight parameters from FMS"""
        try:
            with self.lock:
                if self.fms:
                    # Get current flight data
                    flight_data = self.fms.get_flight_data()

                    # Update attitude
                    if 'attitude' in flight_data:
                        self.roll = flight_data['attitude'].get('roll', self.roll)
                        self.pitch = flight_data['attitude'].get('pitch', self.pitch)

                    # Update velocity
                    if 'velocity' in flight_data:
                        self.airspeed = flight_data['velocity'].get('airspeed', self.airspeed)
                        self.vertical_speed = flight_data['velocity'].get('vertical_speed', self.vertical_speed)
                        self.mach = flight_data['velocity'].get('mach', self.mach)

                    # Update navigation
                    if 'navigation' in flight_data:
                        self.heading = flight_data['navigation'].get('heading', self.heading)
                        self.altitude = flight_data['navigation'].get('altitude', self.altitude)

                    # Update tactical
                    if 'tactical' in flight_data:
                        self.g_force = flight_data['tactical'].get('g_force', self.g_force)
                        self.aoa = flight_data['tactical'].get('aoa', self.aoa)
                        self.energy_state = flight_data['tactical'].get('energy_state', self.energy_state)

                    # Update status
                    if 'status' in flight_data:
                        self.flight_mode = flight_data['status'].get('mode', self.flight_mode)

                if self.fms_control:
                    # Get tactical status for enhanced data
                    tactical_status = self.fms_control.get_tactical_status()
                    if tactical_status:
                        # Update envelope warnings
                        self.envelope_warnings = tactical_status.get('envelope_warnings', [])

                        # Update target values if available
                        if 'profile_limits' in tactical_status:
                            self.max_g_force = tactical_status['profile_limits'].get('max_g_force', 9.0)
                            self.max_aoa = tactical_status['profile_limits'].get('max_aoa', 25.0)

                # Request a repaint
                self.update()

        except Exception as e:
            logger.error(f"Error updating PFD from FMS: {e}")

    def cleanup(self):
        """Clean up resources"""
        if self.update_timer:
            self.update_timer.stop()
            self.update_timer = None

    def paint_display(self, painter: QPainter):
        """Paint the Primary Flight Display"""
        try:
            # Draw main elements in order
            self.draw_attitude_indicator(painter)
            self.draw_altitude_tape(painter)
            self.draw_airspeed_tape(painter)
            self.draw_heading_indicator(painter)

            # Draw  elements
            self.draw_flight_mode_indicator(painter)
            self.draw_tactical_indicators(painter)
            self.draw_envelope_warnings(painter)

        except Exception as e:
            logger.error(f"PFD paint error: {str(e)}")
            logger.error(traceback.format_exc())
            raise  # Let base class handle the error display

    def draw_attitude_indicator(self, painter: QPainter):
        """Draw attitude indicator with enhanced visuals"""
        try:
            # Calculate center point
            center_x = self.width() / 2
            center_y = self.height() / 2

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Save state
            painter.save()

            # Move to center and rotate for roll
            painter.translate(center_x, center_y)
            painter.rotate(-self.roll)

            # Calculate horizon size based on window size
            horizon_width = min(self.width() / 4, 300)
            horizon_height = min(self.height() / 4, 200)

            if use_gradients:
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
                self.draw_line(
                    painter, horizon_line.p1(), horizon_line.p2(),
                    width=2.0,
                    glow=True
                )

                # Draw enhanced pitch ladder
                self.draw_enhanced_pitch_ladder(painter, horizon_width)
            else:
                # Fall back to original drawing
                # Draw artificial horizon
                sky_rect = QRectF(-horizon_width, -horizon_height, horizon_width * 2, horizon_height)
                ground_rect = QRectF(-horizon_width, 0, horizon_width * 2, horizon_height)

                # Draw sky
                sky_color = QColor(0, 128, 255)
                painter.fillRect(sky_rect, sky_color)

                # Draw ground
                ground_color = QColor(139, 69, 19)
                painter.fillRect(ground_rect, ground_color)

                # Draw horizon line using QLineF
                painter.setPen(QPen(self.hud_color, 2))
                horizon_line = QLineF(QPointF(-horizon_width, 0), QPointF(horizon_width, 0))
                painter.drawLine(horizon_line)

                # Draw original pitch ladder
                self.draw_pitch_ladder(painter, horizon_width)

            # Restore state
            painter.restore()

        except Exception as e:
            logger.error(f"Error drawing attitude indicator: {str(e)}")
            raise

    def draw_pitch_ladder(self, painter: QPainter, horizon_width: float):
        """Draw pitch ladder lines (original version)"""
        try:
            painter.setPen(QPen(self.hud_color, 1))

            # Calculate pitch line spacing based on window size
            pitch_spacing = min(self.height() / 30, 4)  # pixels per degree

            # Draw pitch lines every 5 degrees
            for pitch in range(-20, 21, 5):
                y = -pitch * pitch_spacing

                # Draw main line using QLineF
                line_width = horizon_width/3 if pitch % 10 == 0 else horizon_width/4
                line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                painter.drawLine(line)

                # Draw pitch number
                if pitch != 0 and abs(pitch) <= 20:
                    text_width = 25
                    # Convert coordinates to QPointF for text positioning
                    left_point = QPointF(-line_width - text_width, y + 5)
                    right_point = QPointF(line_width + 5, y + 5)
                    painter.drawText(left_point, str(abs(pitch)))
                    painter.drawText(right_point, str(abs(pitch)))

        except Exception as e:
            logger.error(f"Error drawing pitch ladder: {str(e)}")
            raise

    def draw_enhanced_pitch_ladder(self, painter: QPainter, horizon_width: float):
        """Draw pitch ladder with enhanced visuals"""
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Calculate pitch line spacing based on window size
            pitch_spacing = min(self.height() / 30, 4)  # pixels per degree

            # Draw pitch lines every 5 degrees with enhanced visuals
            for pitch in range(-20, 21, 5):
                y = -pitch * pitch_spacing

                # Determine line width based on pitch value
                line_width = horizon_width/2.5 if pitch % 10 == 0 else horizon_width/3.5

                # Draw main line with enhanced visuals
                if pitch == 0:
                    # Horizon line already drawn
                    continue
                elif pitch % 10 == 0:
                    # Major pitch lines (10, 20 degrees)
                    if use_gradients:
                        # Draw with glow effect
                        line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                        self.draw_line(
                            painter, line.p1(), line.p2(),
                            width=1.5,
                            glow=True
                        )
                    else:
                        # Fall back to original
                        line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                        painter.drawLine(line)
                else:
                    # Minor pitch lines (5, 15 degrees)
                    line = QLineF(QPointF(-line_width, y), QPointF(line_width, y))
                    painter.drawLine(line)

                # Draw pitch number with enhanced visuals
                if pitch != 0 and abs(pitch) <= 20:
                    text_width = 25
                    left_rect = QRectF(-line_width - text_width, y - 10, text_width, 20)
                    right_rect = QRectF(line_width + 5, y - 10, text_width, 20)

                    if use_gradients and abs(pitch) % 10 == 0:
                        # Draw major pitch numbers with glow
                        self.draw_text(
                            painter, left_rect,
                            Qt.AlignmentFlag.AlignRight,
                            str(abs(pitch)),
                            glow=True
                        )

                        self.draw_text(
                            painter, right_rect,
                            Qt.AlignmentFlag.AlignLeft,
                            str(abs(pitch)),
                            glow=True
                        )
                    else:
                        # Draw regular or fall back to original
                        painter.drawText(left_rect, Qt.AlignmentFlag.AlignRight, str(abs(pitch)))
                        painter.drawText(right_rect, Qt.AlignmentFlag.AlignLeft, str(abs(pitch)))

            # Add perspective grid lines for enhanced depth perception
            if use_gradients:
                # Draw grid lines that converge at horizon
                grid_color = QColor(self.hud_color)
                grid_color.setAlpha(80)  # Semi-transparent
                painter.setPen(grid_color)

                # Draw vertical grid lines
                for x in range(-3, 4):
                    if x == 0:
                        continue  # Skip center line

                    x_pos = x * (horizon_width / 4)

                    # Calculate top and bottom points with perspective
                    top_y = -horizon_width / 2
                    bottom_y = horizon_width / 2

                    # Adjust x position for perspective effect
                    perspective_factor = 0.3
                    top_x = x_pos * (1 - perspective_factor)
                    bottom_x = x_pos * (1 + perspective_factor)

                    # Draw perspective line
                    painter.drawLine(QPointF(top_x, top_y), QPointF(bottom_x, bottom_y))

        except Exception as e:
            logger.error(f"Error drawing enhanced pitch ladder: {str(e)}")
            raise

    def draw_altitude_tape(self, painter: QPainter):
        """Draw scrolling altitude tape with enhanced visuals"""
        try:
            # Calculate positions based on window size
            tape_width = min(self.width() / 8, 80)
            tape_x = self.width() - tape_width - 20
            tape_y = self.height() / 2

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            if use_gradients:
                # Draw altitude box with enhanced visuals
                box_height = 30
                box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)

                # Draw box with gradient background
                self.draw_rect(
                    painter, box_rect,
                    fill=True,
                    fill_color=QColor(0, 0, 0, 180),
                    corner_radius=corner_radius
                )

                # Draw current altitude with glow effect
                text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
                self.draw_text(
                    painter, text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{int(self.altitude):05d}",
                    glow=True
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
                    painter.setBrush(self.target_color)
                    painter.drawPath(target_path)

                    # Draw small text with target value
                    text_rect = QRectF(tape_x, target_y - 8, tape_width - 20, 16)
                    painter.setPen(self.target_color)
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
                        painter.setBrush(self.target_color)  # Green for climb
                    else:
                        painter.setBrush(self.warning_color)  # Orange for descent

                    painter.drawPath(vs_path)

                    # Draw text with vertical speed value
                    text_rect = QRectF(vs_x - 25, vs_y - arrow_height - 10, 50, 20)
                    painter.setPen(self.hud_color)
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
                            self.draw_line(
                                painter, tick_line.p1(), tick_line.p2(),
                                width=1.5,
                                glow=False
                            )

                            # Draw altitude value
                            text_rect = QRectF(tape_x + 20, y_pos - 10, tape_width - 40, 20)
                            self.draw_text(
                                painter, text_rect,
                                Qt.AlignmentFlag.AlignCenter,
                                f"{int(tick_alt):05d}",
                                glow=False
                            )
                        else:
                            # Minor ticks
                            painter.setPen(self.hud_color)
                            painter.drawLine(tick_line)
            else:
                # Fall back to original drawing
                painter.setPen(self.hud_color)

                # Draw altitude box
                box_height = 30
                box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)
                painter.drawRect(box_rect)

                # Draw current altitude
                text_point = QPointF(tape_x, tape_y + 5)
                painter.drawText(text_point, f"{int(self.altitude):05d}")

                # Draw altitude ticks
                tick_spacing = box_height * 0.8
                for i in range(-5, 6):
                    tick_alt = self.altitude + (i * 100)
                    y_pos = tape_y + (i * tick_spacing)

                    if i != 0:  # Don't draw over the main altitude
                        tick_line = QLineF(
                            QPointF(tape_x + tape_width - 20, y_pos),
                            QPointF(tape_x + tape_width - 10, y_pos)
                        )
                        painter.drawLine(tick_line)
                        if i % 2 == 0:
                            text_point = QPointF(tape_x + 20, y_pos + 5)
                            painter.drawText(text_point, f"{int(tick_alt):05d}")

        except Exception as e:
            logger.error(f"Error drawing altitude tape: {str(e)}")
            raise

    def draw_airspeed_tape(self, painter: QPainter):
        """Draw scrolling airspeed tape with enhanced visuals"""
        try:
            # Calculate positions based on window size
            tape_width = min(self.width() / 8, 70)
            tape_x = 20
            tape_y = self.height() / 2

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            if use_gradients:
                # Draw airspeed box with enhanced visuals
                box_height = 30
                box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)

                # Draw box with gradient background
                self.draw_rect(
                    painter, box_rect,
                    fill=True,
                    fill_color=QColor(0, 0, 0, 180),
                    corner_radius=corner_radius
                )

                # Draw current airspeed with glow effect
                text_rect = QRectF(tape_x, tape_y - 10, tape_width - 20, 20)
                self.draw_text(
                    painter, text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{int(self.airspeed):03d}",
                    glow=True
                )

                # Draw mach number (aircraft specific) - repositioned to avoid overlap
                mach_rect = QRectF(tape_x, tape_y + box_height/2 + 5, tape_width - 10, 20)
                painter.setPen(self.hud_color)
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
                    painter.setBrush(self.target_color)
                    painter.drawPath(target_path)

                    # Draw small text with target value
                    text_rect = QRectF(tape_x, target_y - 8, tape_width - 20, 16)
                    painter.setPen(self.target_color)
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
                            self.draw_line(
                                painter, tick_line.p1(), tick_line.p2(),
                                width=1.5,
                                glow=False
                            )

                            # Draw speed value
                            text_rect = QRectF(tape_x + 10, y_pos - 10, tape_width - 20, 20)
                            self.draw_text(
                                painter, text_rect,
                                Qt.AlignmentFlag.AlignCenter,
                                f"{int(tick_speed):03d}",
                                glow=False
                            )
                        else:
                            # Minor ticks
                            painter.setPen(self.hud_color)
                            painter.drawLine(tick_line)
            else:
                # Fall back to original drawing
                painter.setPen(self.hud_color)

                # Draw airspeed box
                box_height = 30
                box_rect = QRectF(tape_x - 10, tape_y - box_height/2, tape_width, box_height)
                painter.drawRect(box_rect)

                # Draw current airspeed
                text_point = QPointF(tape_x, tape_y + 5)
                painter.drawText(text_point, f"{int(self.airspeed):03d}")

                # Draw mach number (aircraft specific) - repositioned to avoid overlap
                mach_point = QPointF(tape_x, tape_y + box_height + 15)
                painter.drawText(mach_point, f"M{self.mach:.3f}")

                # Draw speed ticks
                tick_spacing = box_height * 0.8
                for i in range(-5, 6):
                    tick_speed = self.airspeed + (i * 10)
                    y_pos = tape_y + (i * tick_spacing)

                    if i != 0:  # Don't draw over the main speed
                        tick_line = QLineF(
                            QPointF(tape_x - 10, y_pos),
                            QPointF(tape_x, y_pos)
                        )
                        painter.drawLine(tick_line)
                        if i % 2 == 0:
                            text_point = QPointF(tape_x + 10, y_pos + 5)
                            painter.drawText(text_point, f"{int(tick_speed):03d}")

        except Exception as e:
            logger.error(f"Error drawing airspeed tape: {str(e)}")
            raise

    def draw_heading_indicator(self, painter: QPainter):
        """Draw heading indicator with enhanced visuals"""
        try:
            # Calculate positions based on window size
            center_x = self.width() / 2
            heading_y = self.height() / 10
            box_width = min(self.width() / 16, 50)
            box_height = 30

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            if use_gradients:
                # Draw heading box with enhanced visuals
                box_rect = QRectF(
                    center_x - box_width/2,
                    heading_y - box_height/2,
                    box_width,
                    box_height
                )

                # Draw box with gradient background
                self.draw_rect(
                    painter, box_rect,
                    fill=True,
                    fill_color=QColor(0, 0, 0, 180),
                    corner_radius=corner_radius
                )

                # Draw current heading with glow effect
                text_rect = QRectF(
                    center_x - box_width/2,
                    heading_y - box_height/2,
                    box_width,
                    box_height
                )
                self.draw_text(
                    painter, text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{int(self.heading):03d}°",
                    glow=True
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
                            self.draw_line(
                                painter, tick_line.p1(), tick_line.p2(),
                                width=1.5,
                                glow=False
                            )

                            # Draw heading value
                            text_rect = QRectF(x_pos - 15, heading_y - box_height - 15, 30, 15)
                            self.draw_text(
                                painter, text_rect,
                                Qt.AlignmentFlag.AlignCenter,
                                f"{int(tick_heading):03d}",
                                glow=False
                            )
                        else:
                            # Minor ticks
                            painter.setPen(self.hud_color)
                            painter.drawLine(tick_line)

                # Draw additional compass arc for more futuristic look
                arc_radius = box_width * 3
                arc_rect = QRectF(
                    center_x - arc_radius,
                    heading_y - arc_radius,
                    arc_radius * 2,
                    arc_radius * 2
                )

                # Draw partial arc
                painter.setPen(QPen(self.hud_color, 1.0))
                painter.drawArc(arc_rect, 30 * 16, 120 * 16)  # Qt uses 1/16th of a degree
            else:
                # Fall back to original drawing
                painter.setPen(self.hud_color)

                # Draw heading box
                box_rect = QRectF(
                    center_x - box_width/2,
                    heading_y - box_height/2,
                    box_width,
                    box_height
                )
                painter.drawRect(box_rect)

                # Draw current heading
                text_point = QPointF(center_x - box_width/2 + 5, heading_y + 5)
                painter.drawText(text_point, f"{int(self.heading):03d}°")

                # Draw compass ticks
                tick_spacing = box_width * 1.2
                for i in range(-3, 4):
                    tick_heading = (self.heading + (i * 10)) % 360
                    x_pos = center_x + (i * tick_spacing)

                    if i != 0:  # Don't draw over the main heading
                        tick_line = QLineF(
                            QPointF(x_pos, heading_y - box_height/2),
                            QPointF(x_pos, heading_y - box_height/4)
                        )
                        painter.drawLine(tick_line)
                        if i % 2 == 0:
                            text_point = QPointF(x_pos - 10, heading_y - box_height)
                            painter.drawText(text_point, f"{int(tick_heading):03d}")

        except Exception as e:
            logger.error(f"Error drawing heading indicator: {str(e)}")
            raise

    def draw_flight_mode_indicator(self, painter: QPainter):
        """Draw the current FMS mode ()"""
        try:
            # Calculate positions based on window size
            mode_x = self.width() / 2
            mode_y = self.height() - 40
            box_width = min(self.width() / 6, 120)
            box_height = 30

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            # Set color based on mode
            if self.flight_mode == "COMBAT":
                mode_color = self.critical_color
                glow = True
            elif self.flight_mode == "STEALTH":
                mode_color = QColor(100, 100, 255)  # Stealth blue
                glow = True
            elif self.flight_mode == "EMERGENCY":
                mode_color = self.warning_color
                glow = True
                # Make it blink in emergency mode
                if int(time.time() * 2) % 2 == 0:
                    mode_color = self.critical_color
            else:
                mode_color = self.hud_color
                glow = False

            if use_gradients:
                # Draw mode box with enhanced visuals
                box_rect = QRectF(
                    mode_x - box_width/2,
                    mode_y - box_height/2,
                    box_width,
                    box_height
                )

                # Draw box with appropriate background
                self.draw_rect(
                    painter, box_rect,
                    fill=True,
                    fill_color=QColor(0, 0, 0, 180),
                    corner_radius=corner_radius
                )

                # Draw flight mode text with appropriate color/glow
                text_rect = QRectF(
                    mode_x - box_width/2,
                    mode_y - box_height/2,
                    box_width,
                    box_height
                )

                # Set font for mode display
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

                # Draw the mode text
                painter.setPen(mode_color)
                if glow:
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        self.flight_mode,
                        glow=True,
                        glow_color=mode_color
                    )
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.flight_mode)

                # Reset font
                painter.setFont(QFont("Arial", 8))
            else:
                # Fall back to simple drawing
                painter.setPen(mode_color)

                # Draw mode box
                box_rect = QRectF(
                    mode_x - box_width/2,
                    mode_y - box_height/2,
                    box_width,
                    box_height
                )
                painter.drawRect(box_rect)

                # Set font for mode display
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

                # Draw mode text
                text_point = QPointF(mode_x - 25, mode_y + 5)
                painter.drawText(text_point, self.flight_mode)

                # Reset font
                painter.setFont(QFont("Arial", 8))

        except Exception as e:
            logger.error(f"Error drawing flight mode indicator: {str(e)}")
            raise

    def draw_tactical_indicators(self, painter: QPainter):
        """Draw tactical indicators (G-force, AOA)"""
        try:
            # Calculate positions based on window size - moved to bottom of display
            left_margin = 20
            tactical_x = left_margin + 120  # Position on left side of display
            tactical_y_start = self.height() - 100  # Position at bottom of display
            tactical_spacing = 30
            tactical_width = 120

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Draw tactical indicators with enhanced visuals
            # 1. G-Force indicator
            g_force_y = tactical_y_start
            self._draw_tactical_value(
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
            self._draw_tactical_value(
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

            # Removed energy state indicator as per user feedback

        except Exception as e:
            logger.error(f"Error drawing tactical indicators: {str(e)}")
            raise

    def _draw_tactical_value(self, painter, label, value, x, y, width,
                           current_value, normal_threshold, warning_threshold, critical_threshold):
        """Helper to draw tactical indicator with thresholds"""
        # Determine color based on value
        if current_value > critical_threshold:
            color = self.critical_color
        elif current_value > warning_threshold:
            color = self.warning_color
        elif current_value > normal_threshold:
            color = self.energy_color  # Yellow for elevated but not warning
        else:
            color = self.hud_color  # Normal color

        # Draw label and value with clear background to prevent overlap
        bg_rect = QRectF(x - width - 5, y - 12, width + 10, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRect(bg_rect)

        # Draw label
        label_rect = QRectF(x - width, y - 7, width - 40, 15)
        painter.setPen(self.hud_color)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight, label)

        # Draw value
        value_rect = QRectF(x - 40, y - 7, 40, 15)
        painter.setPen(color)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignRight, value)

        # Reset brush
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def draw_envelope_warnings(self, painter: QPainter):
        """Draw flight envelope warnings and caution indications"""
        try:
            if not self.envelope_warnings:
                return  # No warnings to display

            # Calculate positions based on window size
            warning_x = self.width() / 2
            warning_y_start = 60
            warning_height = 30
            warning_spacing = 5

            # Draw each warning
            for i, warning in enumerate(self.envelope_warnings):
                warning_y = warning_y_start + i * (warning_height + warning_spacing)

                # Format warning message
                if warning == "BANK_ANGLE":
                    msg = "BANK ANGLE"
                elif warning == "PITCH_ANGLE":
                    msg = "PITCH ANGLE"
                elif warning == "ROLL_RATE":
                    msg = "ROLL RATE"
                elif warning == "PITCH_RATE":
                    msg = "PITCH RATE"
                elif warning == "YAW_RATE":
                    msg = "YAW RATE"
                else:
                    msg = warning.replace("_", " ")

                # Alternate warning color for visibility - blink on half-second intervals
                if int(time.time() * 2) % 2 == 0:
                    painter.setPen(self.critical_color)
                else:
                    painter.setPen(self.warning_color)

                # Set bold font for warnings
                painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))

                # Create a rectangle for text centering
                warning_rect = QRectF(
                    warning_x - 100,
                    warning_y - warning_height/2,
                    200,
                    warning_height
                )

                # Draw warning text
                painter.drawText(warning_rect, Qt.AlignmentFlag.AlignCenter, msg)

                # Reset font
                painter.setFont(QFont("Arial", 8))

        except Exception as e:
            logger.error(f"Error drawing envelope warnings: {str(e)}")
            raise
