"""
Node-Based Primary Flight Display

Primary Flight Display (PFD) that uses display nodes for orientation data.
Subscribes to orientation nodes for flight data updates.

NOTE (production readiness re-analysis, August 2026): confirmed
unreachable in the live application -- pfd_display_factory.py's
create_display() only ever builds a HolographicPFD or the standard
PrimaryFlightDisplay, never this class, and nothing else in the codebase
constructs it either. Unlike FuturisticPFD/FuturisticMFD (see those
files' own notes), there's no explicit "removed" comment anywhere
pointing to a deliberate decision to retire this specific variant -- it
may simply be an alternative PFD implementation (built on the node-tree
system documented as operational in PLANNING.md Section 4.3) that was
never connected to the display factory. Left in place rather than
deleted or wired in, since neither action was requested; flagged here so
a future maintainer can make an informed call.
"""

from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics, QPainterPath, QLinearGradient
# NOTE (production readiness re-analysis, August 2026): QLinearGradient was
# missing from the import above despite being used in the sky/ground gradient
# rendering path -- found via `ruff check --select F821`. This class is
# already confirmed unreachable via the PFD display factory (see this file's
# module docstring above), so the bug has no live impact today, but fixed
# for correctness in case this class is ever wired in.
import math
import threading
import time
import asyncio
import traceback

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
from FMOFP.Systems.flightManagementSys.fmsControl import get_fms_control
from FMOFP.Interfaces.userInterface.displays.display_nodes.display_tree_manager import get_display_tree_manager
from FMOFP.Interfaces.userInterface.displays.display_nodes.orientation_node import OrientationNode
from FMOFP.Interfaces.userInterface.displays.behaviors.fms_orientation_behavior import get_fms_orientation_behavior

from .base_display import BaseDisplay, DisplayType

logger = get_logger()

class NodeBasedPFD(BaseDisplay):
    """Primary Flight Display that uses display nodes for orientation data"""
    
    def __init__(self):
        super().__init__(DisplayType.PFD)
        # Basic flight parameters (will be populated from nodes)
        self.altitude = 30000
        self.airspeed = 450
        self.heading = 45
        self.pitch = 0
        self.roll = 0
        
        # Extended flight parameters (will be populated from nodes)
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
        
        # Connect to display node tree
        self.tree_manager = get_display_tree_manager()
        
        # Get FMS orientation behavior and ensure it's initialized
        self.fms_behavior = get_fms_orientation_behavior()
        
        # Get FMS for additional data
        self.fms = get_flightManagementSystem()
        self.fms_control = get_fms_control()
        
        # Keep track of node subscriptions
        self.subscriptions = []
        
        # Thread synchronization
        self.lock = threading.Lock()
        
        # Main event loop for async node interactions
        self.loop = asyncio.new_event_loop()
        self.thread = None
        
        # Get orientation nodes (will be created by FMS behavior if they don't exist)
        self.orientation_root = None
        self.attitude_node = None
        self.position_node = None
        self.velocity_node = None
        self.tactical_node = None
        
        # Initialize event loop in separate thread
        self._start_event_loop()
        
        # Initialize node structure
        self._initialize_nodes()
        
        # Start the FMS behavior if it's not already running
        if not self.fms_behavior.is_running():
            logger.info("Starting FMS orientation behavior from PFD")
            self.fms_behavior.start()
        
        logger.info("Node-based PFD initialized successfully")
    
    def _start_event_loop(self):
        """Start asyncio event loop in a separate thread"""
        def run_event_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()
        logger.info("PFD asyncio event loop started")
    
    def _initialize_nodes(self):
        """Initialize connections to orientation nodes"""
        try:
            # Create a coroutine and run it in the event loop
            future = asyncio.run_coroutine_threadsafe(self._async_initialize_nodes(), self.loop)
            # Wait for the coroutine to complete
            future.result(timeout=5.0)
            logger.info("PFD successfully initialized orientation nodes")
        except Exception as e:
            logger.error(f"Error initializing PFD orientation nodes: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _async_initialize_nodes(self):
        """Async initialization of orientation nodes"""
        try:
            # Get orientation root node
            root = self.tree_manager.root
            self.orientation_root = root.get_child("flight_orientation")
            
            if not self.orientation_root:
                logger.warning("Orientation root node not found, behavior may not be initialized")
                return
            
            # Get individual nodes
            self.attitude_node = self.orientation_root.get_child("attitude")
            self.position_node = self.orientation_root.get_child("position")
            self.velocity_node = self.orientation_root.get_child("velocity")
            self.tactical_node = self.orientation_root.get_child("tactical")
            
            # Subscribe to node updates
            if self.attitude_node:
                self.attitude_node.add_subscriber(self.attitude_update)
                logger.info("Subscribed to attitude node updates")
            
            if self.position_node:
                self.position_node.add_subscriber(self.position_update)
                logger.info("Subscribed to position node updates")
            
            if self.velocity_node:
                self.velocity_node.add_subscriber(self.velocity_update)
                logger.info("Subscribed to velocity node updates")
            
            if self.tactical_node:
                self.tactical_node.add_subscriber(self.tactical_update)
                logger.info("Subscribed to tactical node updates")
            
            # Get initial values
            await self.update_from_nodes()
            
        except Exception as e:
            logger.error(f"Error in async node initialization: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def update_from_nodes(self):
        """Update all values from nodes"""
        try:
            # Update attitude values
            if self.attitude_node and isinstance(self.attitude_node.value, dict):
                with self.lock:
                    self.roll = self.attitude_node.value.get('roll', self.roll)
                    self.pitch = self.attitude_node.value.get('pitch', self.pitch)
            
            # Update position values
            if self.position_node and isinstance(self.position_node.value, dict):
                with self.lock:
                    self.heading = self.position_node.value.get('heading', self.heading)
                    self.altitude = self.position_node.value.get('altitude', self.altitude)
            
            # Update velocity values
            if self.velocity_node and isinstance(self.velocity_node.value, dict):
                with self.lock:
                    self.airspeed = self.velocity_node.value.get('airspeed', self.airspeed)
                    self.vertical_speed = self.velocity_node.value.get('vertical_speed', self.vertical_speed)
                    self.mach = self.velocity_node.value.get('mach', self.mach)
            
            # Update tactical values
            if self.tactical_node and isinstance(self.tactical_node.value, dict):
                with self.lock:
                    self.g_force = self.tactical_node.value.get('g_force', self.g_force)
                    self.aoa = self.tactical_node.value.get('aoa', self.aoa)
                    self.energy_state = self.tactical_node.value.get('energy_state', self.energy_state)
                    mode = self.tactical_node.value.get('mode', None)
                    if mode:
                        self.flight_mode = mode
            
            # Request repaint
            self.update()
            
        except Exception as e:
            logger.error(f"Error updating from nodes: {str(e)}")
            logger.error(traceback.format_exc())
    
    # Node subscriber methods (called by node updates)
    async def attitude_update(self, node_name, node_value):
        """Handle attitude node updates"""
        try:
            if isinstance(node_value, dict):
                with self.lock:
                    self.roll = node_value.get('roll', self.roll)
                    self.pitch = node_value.get('pitch', self.pitch)
                    # Request repaint
                    self.update()
                    logger.debug(f"PFD updated from attitude node: roll={self.roll}, pitch={self.pitch}")
        except Exception as e:
            logger.error(f"Error in attitude update: {str(e)}")
    
    async def position_update(self, node_name, node_value):
        """Handle position node updates"""
        try:
            if isinstance(node_value, dict):
                with self.lock:
                    self.heading = node_value.get('heading', self.heading)
                    self.altitude = node_value.get('altitude', self.altitude)
                    # Request repaint
                    self.update()
                    logger.debug(f"PFD updated from position node: altitude={self.altitude}, heading={self.heading}")
        except Exception as e:
            logger.error(f"Error in position update: {str(e)}")
    
    async def velocity_update(self, node_name, node_value):
        """Handle velocity node updates"""
        try:
            if isinstance(node_value, dict):
                with self.lock:
                    self.airspeed = node_value.get('airspeed', self.airspeed)
                    self.vertical_speed = node_value.get('vertical_speed', self.vertical_speed)
                    self.mach = node_value.get('mach', self.mach)
                    # Request repaint
                    self.update()
                    logger.debug(f"PFD updated from velocity node: airspeed={self.airspeed}, vs={self.vertical_speed}")
        except Exception as e:
            logger.error(f"Error in velocity update: {str(e)}")
    
    async def tactical_update(self, node_name, node_value):
        """Handle tactical node updates"""
        try:
            if isinstance(node_value, dict):
                with self.lock:
                    self.g_force = node_value.get('g_force', self.g_force)
                    self.aoa = node_value.get('aoa', self.aoa)
                    self.energy_state = node_value.get('energy_state', self.energy_state)
                    mode = node_value.get('mode', None)
                    if mode:
                        self.flight_mode = mode
                    # Request repaint
                    self.update()
                    logger.debug(f"PFD updated from tactical node: g={self.g_force}, aoa={self.aoa}")
        except Exception as e:
            logger.error(f"Error in tactical update: {str(e)}")
    
    def fallback_update_from_fms(self):
        """Fallback method to update from FMS directly if node updates aren't working"""
        try:
            if not self.fms:
                return
                
            # Get current flight data
            flight_data = self.fms.get_flight_data()
            
            with self.lock:
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
            
            # Request repaint
            self.update()
            logger.info("PFD updated from FMS fallback mechanism")
                
        except Exception as e:
            logger.error(f"Error in fallback FMS update: {str(e)}")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Unsubscribe from nodes
            if self.attitude_node:
                self.attitude_node.remove_subscriber(self.attitude_update)
            
            if self.position_node:
                self.position_node.remove_subscriber(self.position_update)
            
            if self.velocity_node:
                self.velocity_node.remove_subscriber(self.velocity_update)
            
            if self.tactical_node:
                self.tactical_node.remove_subscriber(self.tactical_update)
            
            # Stop event loop
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Join thread
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            
            logger.info("PFD resources cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up PFD: {str(e)}")
            
        # Call base cleanup
        super().cleanup()

    def paint_display(self, painter: QPainter):
        """Paint the Primary Flight Display"""
        try:
            # Draw main elements in order
            self.draw_attitude_indicator(painter)
            self.draw_altitude_tape(painter)
            self.draw_airspeed_tape(painter)
            self.draw_heading_indicator(painter)
            
            # Draw elements
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
        # Same implementation as the original PFD
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
        # Same implementation as the original PFD
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
        # Same implementation as the original PFD
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
                
                # Draw mach number (aircraft specific)
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
                
                # Draw mach number (aircraft specific)
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
        """Draw the current FMS mode"""
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
