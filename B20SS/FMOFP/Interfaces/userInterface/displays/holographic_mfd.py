"""
Holographic Multi-Function Display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath, QFont, QPen, QBrush
from .holographic_display import HolographicDisplay
from .base_display import DisplayType
from .visual.enhanced_theme_manager import get_enhanced_theme_manager, EnhancedDisplayTheme
from .visual.enhanced_effects import get_enhanced_visual_effects
from .visual.holographic_settings_panel import HolographicSettingsPanel
from .radar.weather_radar_holographic_display import WeatherRadarHolographicDisplay
import math
import time
import random
from typing import Dict, List, Optional, Any, Tuple
from Utils.logger.sys_logger import get_logger
from FMOFP.manual_animation_timer import ManualAnimationTimer

logger = get_logger()

class HolographicMFD(HolographicDisplay):
    """Advanced holographic multi-function display with 3D visualization"""

    # NOTE (production readiness re-analysis, August 2026): added so
    # 'set_mfd_mode' events can cross from EventBus's background
    # "EventBus_Processor" thread to this widget's GUI thread safely -- see
    # the NOTE in __init__ below for the full explanation.
    _mode_event_received = pyqtSignal(object)

    def __init__(self, parent=None):
        """Initialize holographic multi-function display"""
        super().__init__(DisplayType.MFD, parent=parent)
        
        # Set theme to holographic
        self._theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)
        
        # Initialize display mode
        self.display_mode = "TACTICAL"  # Default mode
        self.available_modes = ["TACTICAL", "NAVIGATION", "SYSTEMS", "COMMUNICATIONS", "WEAPONS", "RADAR"]  # HOLOGRAPHIC DISPLAY BUTTONS
        
        # Add exclusive mode tracking to prevent display interference
        self._exclusive_mode_active = False
        
        # Initialize radar display
        self._radar_display = None
        self._radar_initialized = False
        
        # Initialize scan animation
        self.scan_angle = 0.0
        self.scan_speed = 45.0  # degrees per second
        
        # Initialize tactical data
        self.tactical_data = {
            "targets": [],
            "friendlies": [],
            "waypoints": [],
            "threats": [],
            "terrain_features": []
        }
        
        # Initialize 3D terrain data
        self.terrain_data = self._generate_sample_terrain_data(20, 20)
        
        # Initialize system status
        self.system_status = {
            "radar": "ACTIVE",
            "comms": "NOMINAL",
            "weapons": "SAFE",
            "navigation": "NOMINAL",
            "fuel": 85,
            "engine": "NOMINAL",
            "stealth": "INACTIVE"
        }
        
        # Generate sample targets for demo
        self._generate_sample_targets()
        
        # Create manual animation timer for scan line
        self._scan_timer = ManualAnimationTimer(update_interval=16)  # ~60 FPS
        self._scan_timer.add_animation("scan_line", self._update_scan_angle, speed=0.1)
        
        # Store initialization time for startup animation
        self._init_time = time.time()
        
        # Settings panel with holographic styling
        self._settings_panel = HolographicSettingsPanel()
        self._settings_panel.parent = self  # Set parent reference for context-aware settings
        
        # Ensure settings panel has the correct theme
        if hasattr(self._settings_panel, '_enhanced_theme_manager'):
            self._settings_panel._enhanced_theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)
            logger.info(f"Set settings panel theme to {EnhancedDisplayTheme.HOLOGRAPHIC.name}")
        
        # Setup settings panel with our callbacks
        self._setup_settings_panel()
        
        # Options button
        self.show_options_button = True
        self.options_button_rect = QRectF(0, 0, 30, 30)  # Will be positioned in paint_display
        
        # Register for MFD mode events
        # NOTE (production readiness re-analysis, August 2026): EventBus invokes
        # subscriber callbacks synchronously from its own dedicated
        # "EventBus_Processor" background thread (confirmed live-reachable:
        # system_manager.py starts the EventBus, and weather_radar_holographic_display.py
        # actively publishes 'set_mfd_mode'). _handle_mode_event() mutates
        # self.display_mode, can construct new child widgets via
        # _initialize_radar_display(), and calls self.update() -- all GUI-thread-
        # only operations; Qt does not support touching GUI objects from a non-GUI
        # thread. Subscribing self._mode_event_received.emit (a Qt signal) instead
        # of the handler directly means EventBus's background thread only ever
        # calls .emit(), and Qt's own cross-thread signal delivery (automatically
        # queued when the emitting thread differs from the receiving object's
        # thread) marshals the actual _handle_mode_event(event) call onto the GUI
        # thread where it's safe to touch widget state.
        try:
            from core.event_driven_communication import get_event_bus, Event
            self._event_bus = get_event_bus()
            self._mode_event_received.connect(self._handle_mode_event)
            # Stored as an attribute so cleanup() below can pass the exact
            # same callback object to event_bus.unsubscribe() later --
            # added (August 2026 re-analysis round, Round 11, EventBus
            # subscriber leak sweep) after confirming EventBus.subscribe()
            # had no unsubscribe() counterpart anywhere: MFDDisplayFactory's
            # clear_cache()/invalidate_cache() discard this instance and
            # create a new one, but without this the old instance's
            # subscription (and therefore the old instance itself, kept
            # alive forever by the callback reference the EventBus
            # subscribers list holds) was never released.
            self._mfd_mode_callback = self._mode_event_received.emit
            self._event_bus.subscribe('set_mfd_mode', self._mfd_mode_callback)
            logger.info("Registered for MFD mode events")
        except Exception as e:
            logger.error(f"Error registering for MFD mode events: {str(e)}")
            
    def _handle_mode_event(self, event):
        """Handle MFD mode change events from other components
        
        Args:
            event: Event object containing mode information
        """
        try:
            # Extract mode from event data
            if hasattr(event, 'data') and isinstance(event.data, dict):
                mode = event.data.get('mode')
                source = event.data.get('source', 'unknown')
                
                if mode and mode in self.available_modes:
                    # Switch to the requested mode
                    logger.info(f"Switching MFD mode to {mode} from source: {source}")
                    self.display_mode = mode
                    
                    # Initialize radar display if switching to RADAR mode
                    if mode == "RADAR" and not self._radar_initialized:
                        self._initialize_radar_display()
                    
                    # Request a repaint
                    self.update()
                else:
                    logger.warning(f"Received invalid MFD mode: {mode} from source: {source}")
            else:
                logger.warning(f"Received mode event with invalid data format: {event}")
                
        except Exception as e:
            logger.error(f"Error handling MFD mode event: {str(e)}")
        
        logger.info("Initialized holographic MFD")
        
    def _setup_settings_panel(self):
        """Set up settings panel with practical MFD settings"""
        # Set parent reference for context-aware settings
        self._settings_panel.parent = self
        
        # DISPLAY settings
        # Theme setting 
        self._settings_panel.add_setting(
            "theme", "Theme", "select", "holographic",
            options=[
                ("Classic", "classic"), 
                ("Modern", "modern"), 
                ("Night", "night"), 
                ("Holographic", "holographic")
            ],
            on_change=self._on_theme_changed
        )
        
        # Brightness setting
        self._settings_panel.add_setting(
            "brightness", "Brightness", "range", 0.8,
            min_value=0.2, max_value=1.0,
            on_change=self._on_brightness_changed
        )
        
        # Day/Night Mode
        self._settings_panel.add_setting(
            "day_night_mode", "Day/Night Mode", "toggle", True,
            on_change=self._on_day_night_changed
        )
        
        # Information Density
        self._settings_panel.add_setting(
            "information_density", "Info Density", "select", "Medium",
            options=[("Low", "low"), ("Medium", "medium"), ("High", "high")],
            on_change=self._on_density_changed
        )
        
        # TACTICAL MODE settings
        # Range Scale
        self._settings_panel.add_setting(
            "range_scale", "Range Scale", "select", "100",
            options=[("25 NM", "25"), ("50 NM", "50"), ("75 NM", "75"), ("100 NM", "100")],
            on_change=self._on_range_scale_changed
        )
        
        # Target Filtering
        self._settings_panel.add_setting(
            "target_filtering", "Target Filter", "select", "All",
            options=[("All", "all"), ("Hostile", "hostile"), ("Friendly", "friendly")],
            on_change=self._on_target_filtering_changed
        )
        
        # Threat Ring Display
        self._settings_panel.add_setting(
            "threat_ring_display", "Threat Rings", "toggle", True,
            on_change=self._on_threat_ring_display_changed
        )
        
        # NAVIGATION MODE settings
        # Map Orientation
        self._settings_panel.add_setting(
            "map_orientation", "Map Orientation", "select", "North Up",
            options=[("North Up", "north_up"), ("Track Up", "track_up")],
            on_change=self._on_map_orientation_changed
        )
        
        # Waypoint Display
        self._settings_panel.add_setting(
            "waypoint_display", "Waypoints", "select", "All",
            options=[("All", "all"), ("Route Only", "route"), ("None", "none")],
            on_change=self._on_waypoint_display_changed
        )
        
        # Terrain Display
        self._settings_panel.add_setting(
            "terrain_display", "Terrain", "toggle", True,
            on_change=self._on_terrain_display_changed
        )
        
        # SYSTEMS MODE settings
        self._settings_panel.add_setting(
            "system_status_detail", "Status Detail", "select", "Normal",
            options=[("Minimal", "minimal"), ("Normal", "normal"), ("Detailed", "detailed")],
            on_change=self._on_system_status_detail_changed
        )
        
        # COMMUNICATIONS MODE settings
        self._settings_panel.add_setting(
            "comm_channels", "Channel Display", "select", "Active",
            options=[("Active", "active"), ("All", "all"), ("Prioritized", "prioritized")],
            on_change=self._on_comm_channels_changed
        )
        
        # WEAPONS MODE settings
        self._settings_panel.add_setting(
            "targeting_mode", "Targeting Mode", "select", "Manual",
            options=[("Manual", "manual"), ("Assisted", "assisted"), ("Auto", "auto")],
            on_change=self._on_targeting_mode_changed
        )
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme change"""
        theme_map = {
            "classic": EnhancedDisplayTheme.CLASSIC,
            "modern": EnhancedDisplayTheme.MODERN,
            "night": EnhancedDisplayTheme.STEALTH,
            "holographic": EnhancedDisplayTheme.HOLOGRAPHIC
        }
        
        if theme_name in theme_map:
            self._theme_manager.set_theme(theme_map[theme_name])
            logger.info(f"Changed theme to {theme_name}")
    
    def _on_brightness_changed(self, value: float):
        """Handle brightness change"""
        # Store brightness value
        self.brightness = value
        # Apply brightness to display
        self._theme_manager.set_style_param("brightness", value)
        logger.info(f"Changed brightness to {value}")
        self.update()

    def _on_day_night_changed(self, is_day_mode: bool):
        """Handle day/night mode change"""
        # Apply appropriate theme based on day/night setting
        if is_day_mode:
            self._theme_manager.set_style_param("background_darkness", 0.2)
            self._theme_manager.set_style_param("text_brightness", 0.9)
        else:
            self._theme_manager.set_style_param("background_darkness", 0.8)
            self._theme_manager.set_style_param("text_brightness", 1.0)
        logger.info(f"Changed to {'day' if is_day_mode else 'night'} mode")
        self.update()
    
    def _on_density_changed(self, density: str):
        """Handle information density change"""
        # Update theme style parameter
        self._theme_manager.set_style_param("information_density", density)
        # Store density setting
        self.information_density = density
        logger.info(f"Changed information density to {density}")
        self.update()
    
    def _on_range_scale_changed(self, range_scale: str):
        """Handle range scale change"""
        # Update radar range
        self.radar_range = int(range_scale)
        logger.info(f"Changed radar range to {range_scale} NM")
        self.update()

    def _on_target_filtering_changed(self, filter_mode: str):
        """Handle target filtering change"""
        self.target_filter = filter_mode
        # Apply filtering to tactical display
        logger.info(f"Changed target filtering to {filter_mode}")
        self.update()
    
    def _on_threat_ring_display_changed(self, show_rings: bool):
        """Handle threat ring display change"""
        self.threat_ring_display = show_rings
        logger.info(f"Changed threat ring display to {show_rings}")
        self.update()
    
    def _on_map_orientation_changed(self, orientation: str):
        """Handle map orientation change"""
        self.map_orientation = orientation
        logger.info(f"Changed map orientation to {orientation}")
        self.update()
    
    def _on_waypoint_display_changed(self, display_mode: str):
        """Handle waypoint display change"""
        self.waypoint_display = display_mode
        logger.info(f"Changed waypoint display to {display_mode}")
        self.update()
        
        # Generate random waypoints based on display mode
        self.tactical_data["waypoints"] = []
        num_waypoints = 4 if display_mode == "all" else 2 if display_mode == "route" else 0
        
        for i in range(num_waypoints):
            # Random position (distance and angle)
            distance = random.uniform(30, 100)
            angle = 45 + i * 90  # Evenly spaced waypoints
            
            # Convert to x, y coordinates
            x = distance * math.cos(math.radians(angle))
            y = distance * math.sin(math.radians(angle))
            
            # Create waypoint
            waypoint = {
                "id": f"WP-{i+1}",
                "x": x,
                "y": y,
                "altitude": 25000,
                "type": "NAVIGATION"
            }
            
            self.tactical_data["waypoints"].append(waypoint)
    
    def _on_terrain_display_changed(self, show_terrain: bool):
        """Handle terrain display change"""
        self.show_terrain = show_terrain
        logger.info(f"Changed terrain display to {show_terrain}")
        self.update()
    
    def _on_system_status_detail_changed(self, detail_level: str):
        """Handle system status detail change"""
        self.system_status_detail = detail_level
        logger.info(f"Changed system status detail to {detail_level}")
        self.update()
    
    def _on_comm_channels_changed(self, channel_mode: str):
        """Handle communication channels display change"""
        self.comm_channels = channel_mode
        logger.info(f"Changed communication channels to {channel_mode}")
        self.update()
    
    def _on_targeting_mode_changed(self, mode: str):
        """Handle targeting mode change"""
        self.targeting_mode = mode
        logger.info(f"Changed targeting mode to {mode}")
        self.update()
    
    def _generate_sample_terrain_data(self, width: int, height: int) -> List[List[float]]:
        """Generate sample terrain data for 3D visualization"""
        # Create a 2D grid of terrain heights
        terrain = []
        for y in range(height):
            row = []
            for x in range(width):
                # Generate a height value between 0.0 and 1.0
                # Use perlin-like noise by combining sine waves of different frequencies
                base_height = 0.3
                
                # Add some random hills and valleys
                freq1 = 0.1
                freq2 = 0.05
                freq3 = 0.02
                
                height_value = base_height + \
                    0.2 * math.sin(x * freq1 * math.pi) * math.sin(y * freq1 * math.pi) + \
                    0.3 * math.sin(x * freq2 * math.pi + 0.5) * math.sin(y * freq2 * math.pi + 0.5) + \
                    0.1 * math.sin(x * freq3 * math.pi + 1.0) * math.sin(y * freq3 * math.pi + 1.0)
                
                # Add some random variation
                height_value += random.uniform(-0.05, 0.05)
                
                # Ensure height is between 0.0 and 1.0
                height_value = max(0.0, min(1.0, height_value))
                
                row.append(height_value)
            terrain.append(row)
        
        return terrain
    
    def _generate_sample_targets(self):
        """Generate sample targets and friendlies for tactical display"""
        # Clear existing data
        self.tactical_data["targets"] = []
        self.tactical_data["friendlies"] = []
        self.tactical_data["threats"] = []
        
        # Generate random targets
        for i in range(5):
            # Random position (distance and angle)
            distance = random.uniform(30, 90)
            angle = random.uniform(0, 360)
            
            # Convert to x, y coordinates
            x = distance * math.cos(math.radians(angle))
            y = distance * math.sin(math.radians(angle))
            
            # Random altitude
            altitude = random.uniform(15000, 35000)
            
            # Random speed
            speed = random.uniform(400, 800)
            
            # Random heading
            heading = random.uniform(0, 360)
            
            # Random threat level
            threat_level = random.randint(3, 9)
            
            # Create target
            target = {
                "id": f"TGT-{i+1:03d}",
                "x": x,
                "y": y,
                "altitude": altitude,
                "speed": speed,
                "heading": heading,
                "threat_level": threat_level,
                "type": random.choice(["FIGHTER", "BOMBER", "UAV", "MISSILE"])
            }
            
            self.tactical_data["targets"].append(target)
            
            # Add high threat targets to threat list
            if threat_level >= 7:
                self.tactical_data["threats"].append(target)
        
        # Generate random friendlies
        for i in range(3):
            # Random position (distance and angle)
            distance = random.uniform(20, 60)
            angle = random.uniform(0, 360)
            
            # Convert to x, y coordinates
            x = distance * math.cos(math.radians(angle))
            y = distance * math.sin(math.radians(angle))
            
            # Random altitude
            altitude = random.uniform(20000, 30000)
            
            # Random speed
            speed = random.uniform(400, 800)
            
            # Random heading
            heading = random.uniform(0, 360)
            
            # Create friendly
            friendly = {
                "id": f"FRD-{i+1:03d}",
                "x": x,
                "y": y,
                "altitude": altitude,
                "speed": speed,
                "heading": heading,
                "type": random.choice(["FIGHTER", "AWACS", "TANKER"])
            }
            
            self.tactical_data["friendlies"].append(friendly)
    
    def _update_scan_angle(self, animation_value: float):
        """Update scan angle based on animation value (0.0 to 1.0)"""
        # Convert animation value to angle (0-360 degrees)
        self.scan_angle = animation_value * 360.0
        # Request repaint
        self.update()
        
    def update_scan_angle(self, delta_time: float):
        """Update radar scan animation"""
        # Update scan angle
        self.scan_angle = (self.scan_angle + self.scan_speed * delta_time) % 360
    
    def _update_animations(self):
        """Override _update_animations to update scan angle"""
        # Call parent method first
        super()._update_animations()
        
        # Update scan angle based on elapsed time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self.update_scan_angle(delta_time)
    
    def _initialize_radar_display(self):
        """Initialize the weather radar holographic display"""
        if not self._radar_initialized:
            try:
                # Create the radar display if it doesn't exist
                if self._radar_display is None:
                    logger.info("Creating new WeatherRadarHolographicDisplay instance")
                    self._radar_display = WeatherRadarHolographicDisplay()
                    
                    # Make sure the radar display is visible and has the right size
                    if hasattr(self._radar_display, 'setVisible'):
                        self._radar_display.setVisible(True)
                    
                    # Apply the holographic theme to the radar display
                    if hasattr(self._radar_display, '_theme_manager'):
                        self._radar_display._theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)
                        logger.info("Applied holographic theme to radar display")
                    
                    logger.info("Successfully created weather radar holographic display")
                
                # Initialize the radar display with display data
                import asyncio
                logger.info("Starting radar display initialization task")
                init_task = asyncio.create_task(self._radar_display.initialize_display())
                
                # Mark as initialized to prevent repeated initialization attempts
                self._radar_initialized = True
                logger.info("Radar display initialization complete")
            except Exception as e:
                logger.error(f"Error initializing radar display: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                self._radar_initialized = False  # Mark as failed so we can retry
    
    # Helper method to ensure proper spacing between data points
    def _ensure_proper_spacing(self, data_points, min_distance=60):
        """Ensure proper spacing between data points to prevent overlapping"""
        if not data_points or len(data_points) <= 1:
            return
            
        # Sort data points by position for consistent processing
        data_points.sort(key=lambda p: (p['position'][0], p['position'][1]))
        
        # Adjust positions to ensure minimum distance
        for i in range(1, len(data_points)):
            current = data_points[i]
            previous = data_points[i-1]
            
            # Calculate current distance
            dx = current['position'][0] - previous['position'][0]
            dy = current['position'][1] - previous['position'][1]
            distance = math.sqrt(dx*dx + dy*dy)
            
            # If too close, adjust position
            if distance < min_distance:
                # Calculate unit vector for direction
                if distance > 0:
                    unit_x = dx / distance
                    unit_y = dy / distance
                else:
                    # If points are exactly on top of each other, use a default direction
                    unit_x = 1.0
                    unit_y = 0.0
                
                # Calculate new position
                new_x = previous['position'][0] + unit_x * min_distance
                new_y = previous['position'][1] + unit_y * min_distance
                
                # Update position
                current['position'] = (new_x, new_y)
    
    def _draw_radar_selection_button(self, painter, rect):
        """Draw a radar selection button at the top of the display"""
        # Save painter state
        painter.save()
        
        try:
            # Create button in top center
            button_width = 150
            button_height = 40
            button_x = (rect.width() - button_width) / 2 + rect.x()
            button_y = rect.y() + 5
            
            button_rect = QRectF(button_x, button_y, button_width, button_height)
            
            # Draw button background
            gradient = QLinearGradient(button_x, button_y, button_x, button_y + button_height)
            gradient.setColorAt(0, QColor(0, 80, 120, 200))
            gradient.setColorAt(1, QColor(0, 120, 180, 200))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(0, 200, 255), 2))
            
            # Draw button with angular corners
            path = QPainterPath()
            corner_size = 8
            
            path.moveTo(button_x + corner_size, button_y)
            path.lineTo(button_x + button_width - corner_size, button_y)
            path.lineTo(button_x + button_width, button_y + corner_size)
            path.lineTo(button_x + button_width, button_y + button_height - corner_size)
            path.lineTo(button_x + button_width - corner_size, button_y + button_height)
            path.lineTo(button_x + corner_size, button_y + button_height)
            path.lineTo(button_x, button_y + button_height - corner_size)
            path.lineTo(button_x, button_y + corner_size)
            path.closeSubpath()
            
            painter.drawPath(path)
            
            # Draw button text
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Arial", 10)
            font.setBold(True)
            painter.setFont(font)
            
            # Note the current radar type
            radar_type = "WEATHER"
            if hasattr(self._radar_display, '_current_radar_type'):
                radar_type = self._radar_display._current_radar_type
            
            painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, f"SELECT RADAR: {radar_type}")
            
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_radar_type_selector(self, painter, rect):
        """Draw radar type selector panel"""
        # Save painter state
        painter.save()
        
        try:
            # Create selector panel at the bottom of the display
            panel_width = rect.width() * 0.8
            panel_height = 30
            panel_x = rect.x() + (rect.width() - panel_width) / 2
            panel_y = rect.y() + rect.height() - panel_height - 10
            
            # Draw panel background
            panel_rect = QRectF(panel_x, panel_y, panel_width, panel_height)
            
            # Draw panel with angular frame
            self._visual_effects.draw_angular_frame(
                painter, 
                panel_rect,
                color=self._theme_manager.get_color("hud"),
                corner_style="angular",
                glow=True,
                depth=0.1
            )
            
            # Available radar types
            radar_types = ["WEATHER", "SAR", "TFR", "AEWC", "TARGETING"]
            
            # Calculate button width
            button_width = panel_width / len(radar_types)
            
            # Draw radar type buttons
            for i, radar_type in enumerate(radar_types):
                # Calculate button position
                button_x = panel_x + i * button_width
                
                # Create button rect
                button_rect = QRectF(button_x, panel_y, button_width, panel_height)
                
                # Determine if button is selected
                is_selected = False
                if hasattr(self._radar_display, '_current_radar_type'):
                    is_selected = self._radar_display._current_radar_type == radar_type
                elif i == 0:  # Select first button (WEATHER) by default
                    is_selected = True
                
                # Draw button
                if is_selected:
                    # Draw selected button with highlighting
                    highlight_color = self._theme_manager.get_color("data_primary")
                    self._visual_effects.draw_rect(
                        painter,
                        button_rect,
                        color=highlight_color,
                        fill=True,
                        fill_color=QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 80),
                        corner_radius=0.0,
                        glow=True,
                        depth=0.2
                    )
                
                # Draw button text
                text_rect = QRectF(button_x + 5, panel_y + 5, button_width - 10, panel_height - 10)
                
                text_color = "data_primary" if is_selected else "hud"
                self.draw_holographic_text(
                    painter,
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    radar_type,
                    depth=0.2,
                    color_name=text_color
                )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def _on_radar_mode_changed(self, mode):
        """Handle radar mode changes from the radar display"""
        logger.info(f"Radar mode changed to: {mode}")
        self.update()  # Request a repaint to show the new mode
    
    def paint_display(self, painter: QPainter):
        """Paint the Holographic Multi-Function Display"""
        try:
            # Enable antialiasing
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            # Draw holographic background
            self.draw_holographic_background(painter, QRectF(0, 0, self.width(), self.height()))
            
            # Draw content based on current mode
            if self.display_mode == "TACTICAL":
                self.draw_tactical_display(painter)
            elif self.display_mode == "NAVIGATION":
                self.draw_navigation_display(painter)
            elif self.display_mode == "SYSTEMS":
                self.draw_systems_display(painter)
            elif self.display_mode == "COMMUNICATIONS":
                self.draw_communications_display(painter)
            elif self.display_mode == "WEAPONS":
                self.draw_weapons_display(painter)
            elif self.display_mode == "RADAR":
                self.draw_radar_display(painter)
            
            # Draw mode selector
            self.draw_mode_selector(painter)
            
            # Draw holographic frame
            self.draw_holographic_frame(painter, QRectF(5, 5, self.width() - 10, self.height() - 10))
            
            # Draw options button if enabled
            if self.show_options_button:
                self._draw_options_button(painter, self.options_button_rect)
            
            # Draw settings panel if visible
            if self._settings_panel.visible:
                # Update settings panel animation
                self._settings_panel.update(0.016)  # ~60 FPS
                
                # Draw settings panel
                self._settings_panel.draw(painter, QRectF(0, 0, self.width(), self.height()))
            
            # Draw startup animation if needed
            self.draw_startup_animation(painter)
            
        except Exception as e:
            logger.error(f"Holographic MFD paint error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _draw_options_button(self, painter: QPainter, rect: QRectF):
        """Draw options button"""
        # Save painter state
        painter.save()
        
        try:
            # Position button in top-right corner
            button_size = 30
            rect = QRectF(
                self.width() - button_size - 10,
                10,
                button_size,
                button_size
            )
            self.options_button_rect = rect  # Update rect for mouse events
            
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
    
    def draw_tactical_display(self, painter: QPainter):
        """Draw tactical situation display with holographic effects"""
        # Calculate center and radius for tactical display
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) * 0.4
        
        # Draw radar grid
        self.draw_radar_grid(painter, QPointF(center_x, center_y), radius)
        
        # Draw range rings
        self.draw_range_rings(painter, QPointF(center_x, center_y), radius)
        
        # Draw scan line
        self.draw_scan_line(painter, QPointF(center_x, center_y), radius, self.scan_angle)
        
        # Filter targets based on settings
        filtered_targets = self.tactical_data["targets"]
        if hasattr(self, 'target_filter'):
            if self.target_filter == "hostile":
                filtered_targets = [t for t in filtered_targets if t["threat_level"] >= 5]
            elif self.target_filter == "friendly":
                filtered_targets = [t for t in filtered_targets if t["threat_level"] < 5]
        
        # Draw targets with filtering applied
        self.draw_filtered_targets(painter, QPointF(center_x, center_y), radius, filtered_targets)
        
        # Draw friendlies
        self.draw_friendlies(painter, QPointF(center_x, center_y), radius)
        
        # Draw waypoints
        self.draw_waypoints(painter, QPointF(center_x, center_y), radius)
        
        # Draw tactical data panel
        self.draw_tactical_data_panel(painter)
        
        # Draw threat indicators if enabled
        if not hasattr(self, 'threat_ring_display') or self.threat_ring_display:
            self.draw_threat_indicators(painter)
    
    def draw_radar_grid(self, painter: QPainter, center: QPointF, radius: float):
        """Draw radar grid with holographic effects"""
        # Draw hexagonal grid
        self._visual_effects.draw_hexagonal_grid(
            painter,
            center,
            radius,
            color=self._theme_manager.get_color("grid"),
            rings=5,
            glow=True,
            depth=0.1
        )
    
    def draw_range_rings(self, painter: QPainter, center: QPointF, radius: float):
        """Draw range rings with holographic effects"""
        # Draw concentric circles for range rings
        for i in range(1, 5):
            ring_radius = radius * i / 4
            
            # Create ellipse rect
            ring_rect = QRectF(
                center.x() - ring_radius,
                center.y() - ring_radius,
                ring_radius * 2,
                ring_radius * 2
            )
            
            # Draw ring with glow
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                ring_rect,
                color=self._theme_manager.get_color("grid"),
                fill=False,
                glow=i == 4,  # Only outer ring glows
                depth=0.1
            )
            
            # Draw range label
            range_value = i * 25  # 25, 50, 75, 100 NM
            label_x = center.x()
            label_y = center.y() - ring_radius
            
            label_rect = QRectF(
                label_x - 20,
                label_y - 10,
                40,
                20
            )
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                f"{range_value}",
                depth=0.1,
                color_name="grid"
            )
    
    def draw_scan_line(self, painter: QPainter, center: QPointF, radius: float, angle: float):
        """Draw radar scan line with holographic effects"""
        # Draw scan line
        self._visual_effects.draw_scan_line(
            painter,
            center,
            radius,
            angle,
            color=self._theme_manager.get_color("data_primary"),
            width=2.0,
            depth=0.2
        )
    
    def draw_targets(self, painter: QPainter, center: QPointF, radius: float):
        """Draw targets with holographic effects"""
        # Draw each target
        for target in self.tactical_data["targets"]:
            # Calculate position on radar
            target_x = center.x() + (target["x"] / 100.0) * radius
            target_y = center.y() + (target["y"] / 100.0) * radius
            
            # Determine color based on threat level
            if target["threat_level"] >= 8:
                color_name = "critical"
            elif target["threat_level"] >= 5:
                color_name = "warning"
            else:
                color_name = "data_tertiary"
            
            # Draw target symbol
            self.draw_target_symbol(
                painter,
                QPointF(target_x, target_y),
                target["heading"],
                target["type"],
                color_name,
                target["threat_level"] / 10.0
            )
            
            # Draw target label
            label_rect = QRectF(
                target_x + 10,
                target_y - 5,
                40,
                10
            )
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                target["id"],
                depth=0.2,
                color_name=color_name
            )
    
    def draw_filtered_targets(self, painter: QPainter, center: QPointF, radius: float, filtered_targets: List[Dict]):
        """Draw filtered targets with holographic effects"""
        # Draw each filtered target
        for target in filtered_targets:
            # Calculate position on radar
            target_x = center.x() + (target["x"] / 100.0) * radius
            target_y = center.y() + (target["y"] / 100.0) * radius
            
            # Determine color based on threat level
            if target["threat_level"] >= 8:
                color_name = "critical"
            elif target["threat_level"] >= 5:
                color_name = "warning"
            else:
                color_name = "data_tertiary"
            
            # Draw target symbol
            self.draw_target_symbol(
                painter,
                QPointF(target_x, target_y),
                target["heading"],
                target["type"],
                color_name,
                target["threat_level"] / 10.0
            )
            
            # Draw target label
            label_rect = QRectF(
                target_x + 10,
                target_y - 5,
                40,
                10
            )
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                target["id"],
                depth=0.2,
                color_name=color_name
            )
    
    def draw_target_symbol(self, painter: QPainter, position: QPointF, heading: float, 
                         target_type: str, color_name: str, threat_level: float):
        """Draw target symbol with holographic effects"""
        # Determine symbol size based on threat level
        size = 6 + threat_level * 4
        
        # Create symbol path
        symbol_path = QPainterPath()
        
        if target_type == "FIGHTER" or target_type == "UAV":
            # Triangle for fighters and UAVs
            symbol_path.moveTo(position.x(), position.y() - size)
            symbol_path.lineTo(position.x() - size, position.y() + size)
            symbol_path.lineTo(position.x() + size, position.y() + size)
            symbol_path.closeSubpath()
        elif target_type == "BOMBER":
            # Diamond for bombers
            symbol_path.moveTo(position.x(), position.y() - size)
            symbol_path.lineTo(position.x() + size, position.y())
            symbol_path.lineTo(position.x(), position.y() + size)
            symbol_path.lineTo(position.x() - size, position.y())
            symbol_path.closeSubpath()
        elif target_type == "MISSILE":
            # Circle for missiles
            symbol_path.addEllipse(position, size, size)
        
        # Save state
        painter.save()
        
        try:
            # Rotate symbol to match heading
            painter.translate(position.x(), position.y())
            painter.rotate(heading)
            painter.translate(-position.x(), -position.y())
            
            # Draw symbol with glow
            self._visual_effects.draw_enhanced_path(
                painter,
                symbol_path,
                color=self._theme_manager.get_color(color_name),
                fill=True,
                glow=threat_level > 0.5,
                depth=0.2
            )
            
        finally:
            # Restore state
            painter.restore()
    
    def draw_friendlies(self, painter: QPainter, center: QPointF, radius: float):
        """Draw friendly units with holographic effects"""
        # Draw each friendly
        for friendly in self.tactical_data["friendlies"]:
            # Calculate position on radar
            friendly_x = center.x() + (friendly["x"] / 100.0) * radius
            friendly_y = center.y() + (friendly["y"] / 100.0) * radius
            
            # Draw friendly symbol
            self.draw_friendly_symbol(
                painter,
                QPointF(friendly_x, friendly_y),
                friendly["heading"],
                friendly["type"]
            )
            
            # Draw friendly label
            label_rect = QRectF(
                friendly_x + 10,
                friendly_y - 5,
                40,
                10
            )
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                friendly["id"],
                depth=0.2,
                color_name="system_normal"
            )
    
    def draw_friendly_symbol(self, painter: QPainter, position: QPointF, heading: float, 
                           friendly_type: str):
        """Draw friendly symbol with holographic effects"""
        # Determine symbol size
        size = 8
        
        # Create symbol path
        symbol_path = QPainterPath()
        
        if friendly_type == "FIGHTER":
            # Square for fighters
            symbol_path.addRect(QRectF(
                position.x() - size/2,
                position.y() - size/2,
                size,
                size
            ))
        elif friendly_type == "AWACS":
            # Circle for AWACS
            symbol_path.addEllipse(position, size/2, size/2)
        elif friendly_type == "TANKER":
            # Cross for tankers
            symbol_path.moveTo(position.x() - size/2, position.y())
            symbol_path.lineTo(position.x() + size/2, position.y())
            symbol_path.moveTo(position.x(), position.y() - size/2)
            symbol_path.lineTo(position.x(), position.y() + size/2)
        
        # Save state
        painter.save()
        
        try:
            # Rotate symbol to match heading
            painter.translate(position.x(), position.y())
            painter.rotate(heading)
            painter.translate(-position.x(), -position.y())
            
            # Draw symbol with glow
            self._visual_effects.draw_enhanced_path(
                painter,
                symbol_path,
                color=self._theme_manager.get_color("system_normal"),
                fill=True,
                glow=True,
                depth=0.2
            )
            
        finally:
            # Restore state
            painter.restore()
    
    def draw_waypoints(self, painter: QPainter, center: QPointF, radius: float):
        """Draw waypoints with holographic effects"""
        # Draw each waypoint
        for i, waypoint in enumerate(self.tactical_data["waypoints"]):
            # Calculate position on radar
            waypoint_x = center.x() + (waypoint["x"] / 100.0) * radius
            waypoint_y = center.y() + (waypoint["y"] / 100.0) * radius
            
            # Draw waypoint symbol
            self.draw_waypoint_symbol(
                painter,
                QPointF(waypoint_x, waypoint_y),
                i + 1
            )
            
            # Draw waypoint label
            label_rect = QRectF(
                waypoint_x + 10,
                waypoint_y - 5,
                40,
                10
            )
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                waypoint["id"],
                depth=0.2,
                color_name="data_primary"
            )
            
            # Draw route line to next waypoint
            if i < len(self.tactical_data["waypoints"]) - 1:
                next_waypoint = self.tactical_data["waypoints"][i + 1]
                next_x = center.x() + (next_waypoint["x"] / 100.0) * radius
                next_y = center.y() + (next_waypoint["y"] / 100.0) * radius
                
                self._visual_effects.draw_enhanced_line(
                    painter,
                    QPointF(waypoint_x, waypoint_y),
                    QPointF(next_x, next_y),
                    color=self._theme_manager.get_color("data_primary"),
                    width=1.0,
                    glow=False,
                    depth=0.1
                )
    
    def draw_waypoint_symbol(self, painter: QPainter, position: QPointF, index: int):
        """Draw waypoint symbol with holographic effects"""
        # Determine symbol size
        size = 8
        
        # Create symbol path
        symbol_path = QPainterPath()
        symbol_path.addEllipse(position, size/2, size/2)
        
        # Draw symbol with glow
        self._visual_effects.draw_enhanced_path(
            painter,
            symbol_path,
            color=self._theme_manager.get_color("data_primary"),
            fill=False,
            glow=True,
            depth=0.2
        )
        
        # Draw waypoint index
        index_rect = QRectF(
            position.x() - size/2,
            position.y() - size/2,
            size,
            size
        )
        
        self.draw_holographic_text(
            painter,
            index_rect,
            Qt.AlignmentFlag.AlignCenter,
            str(index),
            depth=0.2,
            color_name="data_primary"
        )
    
    def draw_tactical_data_panel(self, painter: QPainter):
        """Draw tactical data panel with holographic effects"""
        # Calculate panel position and size
        panel_width = self.width() * 0.25
        panel_height = self.height() * 0.6
        panel_x = self.width() - panel_width - 10
        panel_y = (self.height() - panel_height) / 2
        
        # Draw panel background
        panel_rect = QRectF(panel_x, panel_y, panel_width, panel_height)
        
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(panel_x + 10, panel_y + 10, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "TACTICAL DATA",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw target information
        y_offset = panel_y + 40
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "TARGETS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw target list
        for i, target in enumerate(self.tactical_data["targets"]):
            if i >= 4:  # Limit to 4 targets
                break
                
            # Determine color based on threat level
            if target["threat_level"] >= 8:
                color_name = "critical"
            elif target["threat_level"] >= 5:
                color_name = "warning"
            else:
                color_name = "data_tertiary"
                
            # Draw target info
            target_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
            
            self.draw_holographic_text(
                painter,
                target_rect,
                Qt.AlignmentFlag.AlignLeft,
                f"{target['id']} - {target['type']} - TL:{target['threat_level']}",
                depth=0.15,
                color_name=color_name
            )
            
            y_offset += 20
        
        # Draw friendly information
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "FRIENDLIES:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw friendly list
        for i, friendly in enumerate(self.tactical_data["friendlies"]):
            if i >= 3:  # Limit to 3 friendlies
                break
                
            # Draw friendly info
            friendly_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
            
            self.draw_holographic_text(
                painter,
                friendly_rect,
                Qt.AlignmentFlag.AlignLeft,
                f"{friendly['id']} - {friendly['type']}",
                depth=0.15,
                color_name="system_normal"
            )
            
            y_offset += 20
        
        # Draw system status
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "SYSTEM STATUS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw radar status
        status_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignLeft,
            f"RADAR: {self.system_status['radar']}",
            depth=0.15,
            color_name="data_primary"
        )
        
        y_offset += 20
        
        # Draw weapons status
        status_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        # Determine color based on weapons status
        if self.system_status["weapons"] == "ARMED":
            weapons_color = "warning"
        elif self.system_status["weapons"] == "FIRING":
            weapons_color = "critical"
        else:
            weapons_color = "system_normal"
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignLeft,
            f"WEAPONS: {self.system_status['weapons']}",
            depth=0.15,
            color_name=weapons_color
        )
    
    def draw_threat_indicators(self, painter: QPainter):
        """Draw threat indicators with holographic effects"""
        # Get display dimensions
        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        
        # Calculate perimeter padding
        padding = 20
        indicator_size = 60  # Smaller size to avoid overlap
        
        # Draw each threat indicator
        for i, threat in enumerate(self.tactical_data["threats"]):
            # Calculate angle to threat
            threat_angle = math.degrees(math.atan2(threat["y"], threat["x"]))
            
            # Calculate position on perimeter based on threat angle
            # Add a small offset based on index to prevent exact overlaps
            display_angle = threat_angle + (i * 10) % 30 - 15  # Small offset based on index
            
            # Convert angle to radians for position calculation
            rad_angle = math.radians(display_angle)
            
            # Calculate position on perimeter
            # Use an elliptical path to account for non-square displays
            ellipse_a = (width / 2) - padding - indicator_size/2
            ellipse_b = (height / 2) - padding - indicator_size/2
            
            perimeter_x = center_x + ellipse_a * math.cos(rad_angle)
            perimeter_y = center_y + ellipse_b * math.sin(rad_angle)
            
            # Adjust for indicator size
            perimeter_x -= indicator_size / 2
            perimeter_y -= indicator_size / 2
            
            # Draw threat indicator
            self._visual_effects.draw_tactical_overlay(
                painter,
                QRectF(perimeter_x, perimeter_y, indicator_size, indicator_size),
                threat["threat_level"],
                threat_angle,  # Use actual threat angle for the indicator direction
                color=self._theme_manager.get_color("critical"),
                depth=0.3
            )
            
            # Draw threat direction line
            line_length = 20
            line_start_x = perimeter_x + indicator_size/2
            line_start_y = perimeter_y + indicator_size/2
            line_end_x = line_start_x + line_length * math.cos(rad_angle)
            line_end_y = line_start_y + line_length * math.sin(rad_angle)
            
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(line_start_x, line_start_y),
                QPointF(line_end_x, line_end_y),
                color=self._theme_manager.get_color("critical"),
                width=2.0,
                glow=True,
                depth=0.2
            )
            
            # Draw threat ID
            if i < len(self.tactical_data["threats"]):
                threat_id = threat["id"]
                threat_level = threat["threat_level"]
                
                # Position text near the indicator
                text_x = perimeter_x + indicator_size/2 - 20
                text_y = perimeter_y + indicator_size + 5
                
                text_rect = QRectF(text_x, text_y, 40, 15)
                
                self.draw_holographic_text(
                    painter,
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"TL:{threat_level}",
                    depth=0.2,
                    color_name="critical"
                )
    
    def draw_navigation_display(self, painter: QPainter):
        """Draw navigation display with holographic effects"""
        # Calculate center and size for 3D terrain display
        center_x = self.width() / 2
        center_y = self.height() / 2
        terrain_width = self.width() * 0.7
        terrain_height = self.height() * 0.6
        
        # Draw 3D terrain
        self.draw_3d_terrain(
            painter,
            QRectF(
                center_x - terrain_width/2,
                center_y - terrain_height/2,
                terrain_width,
                terrain_height
            )
        )
        
        # Draw navigation data panel
        self.draw_navigation_data_panel(painter)
    
    def draw_3d_terrain(self, painter: QPainter, rect: QRectF):
        """Draw 3D terrain with holographic effects"""
        # Draw terrain background
        self._visual_effects.draw_rect(
            painter,
            rect,
            color=self._theme_manager.get_color("hud"),
            fill=True,
            fill_color=QColor(0, 10, 20, 180),
            corner_radius=0.0,
            glow=False,
            depth=0.1
        )
        
        # Draw terrain grid
        grid_spacing_x = rect.width() / 10
        grid_spacing_y = rect.height() / 10
        
        for i in range(11):
            # Draw horizontal grid lines
            y = rect.y() + i * grid_spacing_y
            
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(rect.x(), y),
                QPointF(rect.x() + rect.width(), y),
                color=self._theme_manager.get_color("grid"),
                width=1.0,
                glow=False,
                depth=0.1
            )
            
            # Draw vertical grid lines
            x = rect.x() + i * grid_spacing_x
            
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(x, rect.y()),
                QPointF(x, rect.y() + rect.height()),
                color=self._theme_manager.get_color("grid"),
                width=1.0,
                glow=False,
                depth=0.1
            )
        
        # Draw terrain profile
        terrain_slice = []
        for i in range(len(self.terrain_data[0])):
            terrain_slice.append(self.terrain_data[len(self.terrain_data) // 2][i])
        
        self._visual_effects.draw_3d_terrain(
            painter,
            rect,
            terrain_slice,
            color=self._theme_manager.get_color("data_secondary"),
            style="modern",
            depth=0.2
        )
        
        # Draw waypoints on terrain
        for i, waypoint in enumerate(self.tactical_data["waypoints"]):
            # Calculate position on terrain
            waypoint_x = rect.x() + rect.width() * (0.1 + i * 0.2)
            waypoint_y = rect.y() + rect.height() * 0.5
            
            # Draw waypoint marker
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                QRectF(waypoint_x - 5, waypoint_y - 5, 10, 10),
                color=self._theme_manager.get_color("data_primary"),
                fill=True,
                glow=True,
                depth=0.3
            )
            
            # Draw waypoint label
            label_rect = QRectF(waypoint_x - 15, waypoint_y - 20, 30, 15)
            
            self.draw_holographic_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                waypoint["id"],
                depth=0.3,
                color_name="data_primary"
            )
    
    def draw_navigation_data_panel(self, painter: QPainter):
        """Draw navigation data panel with holographic effects"""
        # Calculate panel position and size
        panel_width = self.width() * 0.25
        panel_height = self.height() * 0.6
        panel_x = 10
        panel_y = (self.height() - panel_height) / 2
        
        # Draw panel background
        panel_rect = QRectF(panel_x, panel_y, panel_width, panel_height)
        
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(panel_x + 10, panel_y + 10, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "NAVIGATION DATA",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw waypoint information
        y_offset = panel_y + 40
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "WAYPOINTS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw waypoint list
        for i, waypoint in enumerate(self.tactical_data["waypoints"]):
            # Draw waypoint info
            waypoint_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
            
            self.draw_holographic_text(
                painter,
                waypoint_rect,
                Qt.AlignmentFlag.AlignLeft,
                f"{waypoint['id']} - ALT:{int(waypoint['altitude'])}",
                depth=0.15,
                color_name="data_primary"
            )
            
            y_offset += 20
        
        # Draw navigation system status
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "NAV SYSTEMS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw GPS status
        status_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignLeft,
            f"GPS: {self.system_status['navigation']}",
            depth=0.15,
            color_name="system_normal"
        )
        
        y_offset += 20
        
        # Draw INS status
        status_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignLeft,
            "INS: ALIGNED",
            depth=0.15,
            color_name="system_normal"
        )
    
    def draw_systems_display(self, painter: QPainter):
        """Draw systems status display with holographic effects"""
        # Calculate center and size for systems display
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Draw aircraft schematic
        self.draw_aircraft_schematic(painter, center_x, center_y)
        
        # Draw systems status panels
        self.draw_systems_status_panels(painter)
    
    def draw_aircraft_schematic(self, painter: QPainter, center_x: float, center_y: float):
        """Draw aircraft schematic with holographic effects"""
        # Calculate aircraft size
        aircraft_width = self.width() * 0.6
        aircraft_height = self.height() * 0.5
        
        # Draw aircraft outline
        aircraft_path = QPainterPath()
        
        # Nose
        aircraft_path.moveTo(center_x, center_y - aircraft_height / 2)
        
        # Left wing
        aircraft_path.lineTo(center_x - aircraft_width / 2, center_y)
        aircraft_path.lineTo(center_x - aircraft_width / 4, center_y)
        
        # Fuselage
        aircraft_path.lineTo(center_x - aircraft_width / 8, center_y + aircraft_height / 4)
        aircraft_path.lineTo(center_x + aircraft_width / 8, center_y + aircraft_height / 4)
        
        # Right wing
        aircraft_path.lineTo(center_x + aircraft_width / 4, center_y)
        aircraft_path.lineTo(center_x + aircraft_width / 2, center_y)
        
        # Back to nose
        aircraft_path.lineTo(center_x, center_y - aircraft_height / 2)
        
        # Draw aircraft outline with glow
        self._visual_effects.draw_enhanced_path(
            painter,
            aircraft_path,
            color=self._theme_manager.get_color("hud"),
            fill=False,
            glow=True,
            depth=0.2
        )
        
        # Draw system nodes
        self.draw_system_node(painter, center_x, center_y - aircraft_height / 4, "RADAR", self.system_status["radar"])
        self.draw_system_node(painter, center_x - aircraft_width / 4, center_y, "ENGINE", self.system_status["engine"])
        self.draw_system_node(painter, center_x + aircraft_width / 4, center_y, "FUEL", f"{self.system_status['fuel']}%")
        self.draw_system_node(painter, center_x, center_y + aircraft_height / 8, "COMMS", self.system_status["comms"])
    
    def draw_system_node(self, painter: QPainter, x: float, y: float, name: str, status: str):
        """Draw system node with holographic effects"""
        # Determine color based on status
        if "ACTIVE" in status or "NOMINAL" in status or status == "SAFE":
            color_name = "system_normal"
        elif "WARNING" in status or "DEGRADED" in status or "ARMED" in status:
            color_name = "warning"
        elif "CRITICAL" in status or "FAILURE" in status or "FIRING" in status:
            color_name = "critical"
        else:
            # Try to determine status from numeric value
            try:
                value = int(status.rstrip("%"))
                if value > 80:
                    color_name = "system_normal"
                elif value > 40:
                    color_name = "warning"
                else:
                    color_name = "critical"
            except Exception:
                color_name = "data_primary"
        
        # Draw node circle
        self._visual_effects.draw_enhanced_ellipse(
            painter,
            QRectF(x - 15, y - 15, 30, 30),
            color=self._theme_manager.get_color(color_name),
            fill=True,
            fill_color=QColor(0, 0, 0, 100),
            glow=True,
            depth=0.2
        )
        
        # Draw node name
        name_rect = QRectF(x - 25, y - 10, 50, 20)
        
        self.draw_holographic_text(
            painter,
            name_rect,
            Qt.AlignmentFlag.AlignCenter,
            name,
            depth=0.2,
            color_name=color_name
        )
        
        # Draw status below
        status_rect = QRectF(x - 30, y + 15, 60, 15)
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignCenter,
            status,
            depth=0.2,
            color_name=color_name
        )
    
    def draw_systems_status_panels(self, painter: QPainter):
        """Draw systems status panels with holographic effects"""
        # Calculate panel positions and sizes
        left_panel_width = self.width() * 0.2
        left_panel_height = self.height() * 0.7
        left_panel_x = 10
        left_panel_y = (self.height() - left_panel_height) / 2
        
        right_panel_width = self.width() * 0.2
        right_panel_height = self.height() * 0.7
        right_panel_x = self.width() - right_panel_width - 10
        right_panel_y = (self.height() - right_panel_height) / 2
        
        # Draw left panel (propulsion and power)
        self.draw_propulsion_panel(
            painter,
            QRectF(left_panel_x, left_panel_y, left_panel_width, left_panel_height)
        )
        
        # Draw right panel (avionics and weapons)
        self.draw_avionics_panel(
            painter,
            QRectF(right_panel_x, right_panel_y, right_panel_width, right_panel_height)
        )
    
    def draw_propulsion_panel(self, painter: QPainter, rect: QRectF):
        """Draw propulsion and power systems panel with holographic effects"""
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(rect.x() + 10, rect.y() + 10, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "PROPULSION & POWER",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw engine status
        y_offset = rect.y() + 40
        
        # Draw section title
        section_rect = QRectF(rect.x() + 10, y_offset, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "ENGINE:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw engine parameters
        params = [
            {"name": "THRUST", "value": "92%", "color": "system_normal"},
            {"name": "TEMP", "value": "820°C", "color": "system_normal"},
            {"name": "RPM", "value": "98%", "color": "system_normal"},
            {"name": "OIL PRESS", "value": "42 PSI", "color": "system_normal"}
        ]
        
        for param in params:
            # Draw parameter name
            name_rect = QRectF(rect.x() + 15, y_offset, rect.width() / 2 - 20, 15)
            
            self.draw_holographic_text(
                painter,
                name_rect,
                Qt.AlignmentFlag.AlignLeft,
                param["name"],
                depth=0.15,
                color_name="data_secondary"
            )
            
            # Draw parameter value
            value_rect = QRectF(rect.x() + rect.width() / 2, y_offset, rect.width() / 2 - 15, 15)
            
            self.draw_holographic_text(
                painter,
                value_rect,
                Qt.AlignmentFlag.AlignRight,
                param["value"],
                depth=0.15,
                color_name=param["color"]
            )
            
            y_offset += 20
        
        # Draw fuel status
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(rect.x() + 10, y_offset, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "FUEL:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw fuel parameters
        fuel_level = self.system_status["fuel"]
        fuel_color = "system_normal"
        
        if fuel_level < 20:
            fuel_color = "critical"
        elif fuel_level < 40:
            fuel_color = "warning"
        
        params = [
            {"name": "MAIN TANK", "value": f"{fuel_level}%", "color": fuel_color},
            {"name": "AUX TANK", "value": "65%", "color": "system_normal"},
            {"name": "FLOW RATE", "value": "850 LB/H", "color": "system_normal"},
            {"name": "ENDURANCE", "value": "2:45", "color": "system_normal"}
        ]
        
        for param in params:
            # Draw parameter name
            name_rect = QRectF(rect.x() + 15, y_offset, rect.width() / 2 - 20, 15)
            
            self.draw_holographic_text(
                painter,
                name_rect,
                Qt.AlignmentFlag.AlignLeft,
                param["name"],
                depth=0.15,
                color_name="data_secondary"
            )
            
            # Draw parameter value
            value_rect = QRectF(rect.x() + rect.width() / 2, y_offset, rect.width() / 2 - 15, 15)
            
            self.draw_holographic_text(
                painter,
                value_rect,
                Qt.AlignmentFlag.AlignRight,
                param["value"],
                depth=0.15,
                color_name=param["color"]
            )
            
            y_offset += 20
    
    def draw_avionics_panel(self, painter: QPainter, rect: QRectF):
        """Draw avionics and weapons systems panel with holographic effects"""
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(rect.x() + 10, rect.y() + 10, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "AVIONICS & WEAPONS",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw radar status
        y_offset = rect.y() + 40
        
        # Draw section title
        section_rect = QRectF(rect.x() + 10, y_offset, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "RADAR:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw radar parameters
        params = [
            {"name": "MODE", "value": "TACTICAL", "color": "data_primary"},
            {"name": "RANGE", "value": "100 NM", "color": "data_primary"},
            {"name": "TARGETS", "value": str(len(self.tactical_data["targets"])), "color": "data_primary"}
        ]
        
        for param in params:
            # Draw parameter name
            name_rect = QRectF(rect.x() + 15, y_offset, rect.width() / 2 - 20, 15)
            
            self.draw_holographic_text(
                painter,
                name_rect,
                Qt.AlignmentFlag.AlignLeft,
                param["name"],
                depth=0.15,
                color_name="data_secondary"
            )
            
            # Draw parameter value
            value_rect = QRectF(rect.x() + rect.width() / 2, y_offset, rect.width() / 2 - 15, 15)
            
            self.draw_holographic_text(
                painter,
                value_rect,
                Qt.AlignmentFlag.AlignRight,
                param["value"],
                depth=0.15,
                color_name=param["color"]
            )
            
            y_offset += 20
        
        # Draw weapons status
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(rect.x() + 10, y_offset, rect.width() - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "WEAPONS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Determine weapons status color
        weapons_status = self.system_status["weapons"]
        if weapons_status == "ARMED":
            weapons_color = "warning"
        elif weapons_status == "FIRING":
            weapons_color = "critical"
        else:
            weapons_color = "system_normal"
        
        # Draw weapons parameters
        params = [
            {"name": "STATUS", "value": weapons_status, "color": weapons_color},
            {"name": "AA MISSILES", "value": "4", "color": "data_primary"},
            {"name": "AG MISSILES", "value": "2", "color": "data_primary"},
            {"name": "CANNON", "value": "650 RDS", "color": "data_primary"}
        ]
        
        for param in params:
            # Draw parameter name
            name_rect = QRectF(rect.x() + 15, y_offset, rect.width() / 2 - 20, 15)
            
            self.draw_holographic_text(
                painter,
                name_rect,
                Qt.AlignmentFlag.AlignLeft,
                param["name"],
                depth=0.15,
                color_name="data_secondary"
            )
            
            # Draw parameter value
            value_rect = QRectF(rect.x() + rect.width() / 2, y_offset, rect.width() / 2 - 15, 15)
            
            self.draw_holographic_text(
                painter,
                value_rect,
                Qt.AlignmentFlag.AlignRight,
                param["value"],
                depth=0.15,
                color_name=param["color"]
            )
            
            y_offset += 20
    
    def draw_weapons_status_panel(self, painter: QPainter):
        """Draw weapons status panel with holographic effects"""
        # Calculate panel position and size
        panel_width = self.width() * 0.25
        panel_height = self.height() * 0.7
        panel_x = 10
        panel_y = (self.height() - panel_height) / 2
        
        # Draw panel background
        panel_rect = QRectF(panel_x, panel_y, panel_width, panel_height)
        
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(panel_x + 10, panel_y + 10, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "WEAPONS STATUS",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw weapons inventory
        y_offset = panel_y + 40
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "INVENTORY:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Draw weapons inventory
        weapons = [
            {"name": "AIM-120C", "count": "4", "type": "AA MISSILE"},
            {"name": "AIM-9X", "count": "2", "type": "AA MISSILE"},
            {"name": "AGM-65", "count": "2", "type": "AG MISSILE"},
            {"name": "GBU-31", "count": "2", "type": "BOMB"},
            {"name": "20MM", "count": "650", "type": "CANNON"}
        ]
        
        for weapon in weapons:
            # Draw weapon info
            weapon_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
            
            self.draw_holographic_text(
                painter,
                weapon_rect,
                Qt.AlignmentFlag.AlignLeft,
                f"{weapon['name']} x{weapon['count']}",
                depth=0.15,
                color_name="data_primary"
            )
            
            y_offset += 20
        
        # Draw weapons status
        y_offset += 10
        
        # Draw section title
        section_rect = QRectF(panel_x + 10, y_offset, panel_width - 20, 20)
        
        self.draw_holographic_text(
            painter,
            section_rect,
            Qt.AlignmentFlag.AlignLeft,
            "STATUS:",
            depth=0.15,
            color_name="hud"
        )
        
        y_offset += 25
        
        # Determine weapons status color
        weapons_status = self.system_status["weapons"]
        if weapons_status == "ARMED":
            weapons_color = "warning"
        elif weapons_status == "FIRING":
            weapons_color = "critical"
        else:
            weapons_color = "system_normal"
        
        # Draw weapons status
        status_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        self.draw_holographic_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignLeft,
            f"MASTER ARM: {weapons_status}",
            depth=0.15,
            color_name=weapons_color
        )
        
        y_offset += 20
        
        # Draw selected weapon
        selected_rect = QRectF(panel_x + 15, y_offset, panel_width - 30, 15)
        
        self.draw_holographic_text(
            painter,
            selected_rect,
            Qt.AlignmentFlag.AlignLeft,
            "SELECTED: AIM-120C",
            depth=0.15,
            color_name="data_primary"
        )
    def draw_communications_display(self, painter: QPainter):
        """Draw communications display with holographic effects"""
        # Calculate center and size for communications display
        center_x = self.width() / 2
        center_y = self.height() / 2
        panel_width = self.width() * 0.7
        panel_height = self.height() * 0.6
        
        # Draw main communications panel
        main_panel_rect = QRectF(
            center_x - panel_width/2,
            center_y - panel_height/2,
            panel_width,
            panel_height
        )
        
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            main_panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(
            main_panel_rect.x() + 10,
            main_panel_rect.y() + 10,
            main_panel_rect.width() - 20,
            30
        )
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "COMMUNICATIONS SYSTEMS",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw communications channels
        self.draw_comm_channels(painter, main_panel_rect)
        
        # Draw status panel
        status_panel_rect = QRectF(
            main_panel_rect.x() + main_panel_rect.width() + 10,
            main_panel_rect.y(),
            self.width() - main_panel_rect.x() - main_panel_rect.width() - 20,
            main_panel_rect.height()
        )
        
        self.draw_comm_status_panel(painter, status_panel_rect)
    
    def draw_comm_channels(self, painter: QPainter, panel_rect: QRectF):
        """Draw communications channels with holographic effects"""
        # Calculate channel list area
        channels_rect = QRectF(
            panel_rect.x() + 20,
            panel_rect.y() + 50,
            panel_rect.width() - 40,
            panel_rect.height() - 70
        )
        
        # Draw channels header
        header_rect = QRectF(
            channels_rect.x(),
            channels_rect.y(),
            channels_rect.width(),
            30
        )
        
        # Draw header columns
        col_width = channels_rect.width() / 4
        
        # Channel column
        channel_header_rect = QRectF(
            channels_rect.x(),
            header_rect.y(),
            col_width,
            header_rect.height()
        )
        
        self.draw_holographic_text(
            painter,
            channel_header_rect,
            Qt.AlignmentFlag.AlignCenter,
            "CHANNEL",
            depth=0.15,
            color_name="data_secondary"
        )
        
        # Frequency column
        freq_header_rect = QRectF(
            channels_rect.x() + col_width,
            header_rect.y(),
            col_width,
            header_rect.height()
        )
        
        self.draw_holographic_text(
            painter,
            freq_header_rect,
            Qt.AlignmentFlag.AlignCenter,
            "FREQUENCY",
            depth=0.15,
            color_name="data_secondary"
        )
        
        # Mode column
        mode_header_rect = QRectF(
            channels_rect.x() + col_width * 2,
            header_rect.y(),
            col_width,
            header_rect.height()
        )
        
        self.draw_holographic_text(
            painter,
            mode_header_rect,
            Qt.AlignmentFlag.AlignCenter,
            "MODE",
            depth=0.15,
            color_name="data_secondary"
        )
        
        # Status column
        status_header_rect = QRectF(
            channels_rect.x() + col_width * 3,
            header_rect.y(),
            col_width,
            header_rect.height()
        )
        
        self.draw_holographic_text(
            painter,
            status_header_rect,
            Qt.AlignmentFlag.AlignCenter,
            "STATUS",
            depth=0.15,
            color_name="data_secondary"
        )
        
        # Draw channel rows
        channels = [
            {"name": "UHF 1", "freq": "243.000", "mode": "AM", "status": "ACTIVE"},
            {"name": "VHF 1", "freq": "121.500", "mode": "AM", "status": "STANDBY"},
            {"name": "UHF 2", "freq": "311.000", "mode": "FM", "status": "STANDBY"},
            {"name": "SATCOM", "freq": "SECURE", "mode": "DATA", "status": "ACTIVE"},
            {"name": "DATALINK", "freq": "SECURE", "mode": "DATA", "status": "ACTIVE"},
            {"name": "GUARD", "freq": "243.000", "mode": "AM", "status": "MONITOR"}
        ]
        
        row_height = 30
        
        for i, channel in enumerate(channels):
            row_y = header_rect.y() + header_rect.height() + i * row_height
            
            # Highlight active channel
            if channel["status"] == "ACTIVE":
                row_rect = QRectF(
                    channels_rect.x(),
                    row_y,
                    channels_rect.width(),
                    row_height
                )
                
                self._visual_effects.draw_rect(
                    painter,
                    row_rect,
                    color=self._theme_manager.get_color("data_primary"),
                    fill=True,
                    fill_color=QColor(0, 50, 100, 80),
                    corner_radius=0.0,
                    glow=False,
                    depth=0.1
                )
            
            # Channel column
            channel_rect = QRectF(
                channels_rect.x(),
                row_y,
                col_width,
                row_height
            )
            
            self.draw_holographic_text(
                painter,
                channel_rect,
                Qt.AlignmentFlag.AlignCenter,
                channel["name"],
                depth=0.15,
                color_name="data_primary"
            )
            
            # Frequency column
            freq_rect = QRectF(
                channels_rect.x() + col_width,
                row_y,
                col_width,
                row_height
            )
            
            self.draw_holographic_text(
                painter,
                freq_rect,
                Qt.AlignmentFlag.AlignCenter,
                channel["freq"],
                depth=0.15,
                color_name="data_primary"
            )
            
            # Mode column
            mode_rect = QRectF(
                channels_rect.x() + col_width * 2,
                row_y,
                col_width,
                row_height
            )
            
            self.draw_holographic_text(
                painter,
                mode_rect,
                Qt.AlignmentFlag.AlignCenter,
                channel["mode"],
                depth=0.15,
                color_name="data_primary"
            )
            
            # Status column
            status_rect = QRectF(
                channels_rect.x() + col_width * 3,
                row_y,
                col_width,
                row_height
            )
            
            # Determine status color
            if channel["status"] == "ACTIVE":
                status_color = "system_normal"
            elif channel["status"] == "STANDBY":
                status_color = "data_secondary"
            elif channel["status"] == "MONITOR":
                status_color = "data_tertiary"
            else:
                status_color = "warning"
            
            self.draw_holographic_text(
                painter,
                status_rect,
                Qt.AlignmentFlag.AlignCenter,
                channel["status"],
                depth=0.15,
                color_name=status_color
            )
    
    def draw_comm_status_panel(self, painter: QPainter, panel_rect: QRectF):
        """Draw communications status panel with holographic effects"""
        # Draw panel with angular frame
        self._visual_effects.draw_angular_frame(
            painter,
            panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Draw panel title
        title_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 10,
            panel_rect.width() - 20,
            30
        )
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            "COMM STATUS",
            depth=0.2,
            color_name="hud"
        )
        
        # Draw status items
        y_offset = panel_rect.y() + 50
        
        status_items = [
            {"name": "RADIO 1", "status": "NOMINAL", "color": "system_normal"},
            {"name": "RADIO 2", "status": "NOMINAL", "color": "system_normal"},
            {"name": "DATALINK", "status": "CONNECTED", "color": "system_normal"},
            {"name": "ENCRYPTION", "status": "ACTIVE", "color": "system_normal"},
            {"name": "SATCOM", "status": "CONNECTED", "color": "system_normal"},
            {"name": "IFF", "status": "MODE 4", "color": "system_normal"}
        ]
        
        for item in status_items:
            # Draw item name
            name_rect = QRectF(
                panel_rect.x() + 15,
                y_offset,
                panel_rect.width() / 2 - 20,
                20
            )
            
            self.draw_holographic_text(
                painter,
                name_rect,
                Qt.AlignmentFlag.AlignLeft,
                item["name"],
                depth=0.15,
                color_name="data_secondary"
            )
            
            # Draw item status
            status_rect = QRectF(
                panel_rect.x() + panel_rect.width() / 2,
                y_offset,
                panel_rect.width() / 2 - 15,
                20
            )
            
            self.draw_holographic_text(
                painter,
                status_rect,
                Qt.AlignmentFlag.AlignRight,
                item["status"],
                depth=0.15,
                color_name=item["color"]
            )
            
            y_offset += 25
        
        # Draw message indicator
        message_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + panel_rect.height() - 80,
            panel_rect.width() - 20,
            30
        )
        
        self.draw_holographic_text(
            painter,
            message_rect,
            Qt.AlignmentFlag.AlignCenter,
            "MESSAGES: 2 NEW",
            depth=0.15,
            color_name="warning"
        )
        
        # Draw signal strength indicator
        signal_label_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + panel_rect.height() - 40,
            panel_rect.width() / 2 - 15,
            30
        )
        
        self.draw_holographic_text(
            painter,
            signal_label_rect,
            Qt.AlignmentFlag.AlignLeft,
            "SIGNAL:",
            depth=0.15,
            color_name="data_secondary"
        )
        
        # Draw signal strength bar
        signal_bar_rect = QRectF(
            panel_rect.x() + panel_rect.width() / 2,
            panel_rect.y() + panel_rect.height() - 35,
            panel_rect.width() / 2 - 20,
            20
        )
        
        # Draw signal strength (80%)
        signal_strength = 0.8
        
        self.draw_holographic_bar(
            painter,
            signal_bar_rect,
            signal_strength,
            0.0,
            1.0,
            vertical=False,
            color_name="system_normal",
            depth=0.15
        )
    
    def draw_radar_display(self, painter: QPainter):
        """Draw weather radar display with holographic effects"""
        # Initialize radar display if needed
        if not self._radar_initialized:
            self._initialize_radar_display()
        
        # Set exclusive mode flag when drawing radar
        self._exclusive_mode_active = True
        
        # Clear ALL tactical data to prevent it from showing through
        self.tactical_data = {
            "targets": [],
            "friendlies": [],
            "waypoints": [],
            "threats": [],
            "terrain_features": []
        }
        
        # Draw radar display
        if self._radar_display:
            # Save painter state
            painter.save()
            
            try:
                # Set up the radar display area margins
                # to ensure it covers any underlying display elements
                radar_rect = QRectF(
                    10, 
                    10, 
                    self.width() - 20, 
                    self.height() - 60 
                )
                
                # Draw radar frame
                self._visual_effects.draw_angular_frame(
                    painter,
                    radar_rect,
                    color=self._theme_manager.get_color("hud"),
                    corner_style="angular",
                    glow=True,
                    depth=0.1
                )
                
                # Draw radar title 
                title_rect = QRectF(
                    radar_rect.x() + 10,
                    radar_rect.y() + 10,
                    radar_rect.width() - 20,
                    30
                )
                
                self.draw_holographic_text(
                    painter,
                    title_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "WEATHER RADAR",
                    depth=0.2,
                    color_name="hud"
                )
                
                # Draw the radar selection button in the top of the display
                self._draw_radar_selection_button(painter, radar_rect)
                
                # Reset the radar display's internal data structures
                # This is critical to prevent overlapping elements
                if hasattr(self._radar_display, '_precipitation_data'):
                    self._radar_display._precipitation_data = []
                if hasattr(self._radar_display, '_vil_data'):
                    self._radar_display._vil_data = []
                if hasattr(self._radar_display, '_cell_data'):
                    self._radar_display._cell_data = []
                if hasattr(self._radar_display, '_weather_particles'):
                    self._radar_display._weather_particles = {'precipitation': {}, 'vil': {}}
                if hasattr(self._radar_display, '_tactical_data'):
                    self._radar_display._tactical_data = {'targets': [], 'friendlies': [], 'threats': []}
                
                # Allow the radar display to paint directly on our graphics context
                # Optimize margins to make better use of available space
                # Leave room for the radar title at top (60px) and mode selector at bottom (40px)
                adjusted_rect = radar_rect.adjusted(20, 60, -20, -40)
                
                # Save painter state for radar display
                painter.save()
                painter.translate(adjusted_rect.x(), adjusted_rect.y())
                
                # Use a more aggressive scale factor to utilize more of the display area
                # This will create less white space and make better use of the available area
                scale_factor = min(
                    adjusted_rect.width() / 800.0,  # Better scale for width
                    adjusted_rect.height() / 600.0  # Better scale for height
                ) * 0.95  # Increase scale to fill more space
                
                # Scale the painter to ensure proper fitting
                painter.scale(scale_factor, scale_factor)
                
                # Create a custom paint method with proper dimensions
                def custom_paint_radar(radar_display, painter, rect_width, rect_height):
                    """Custom paint method with explicit dimensions provided to radar display"""
                    # Store original attributes
                    original_attrs = {}
                    for attr in ['_width', '_height', 'width', 'height', 'sweep_angle', 
                                 '_weather_rotation', '_weather_pulse_factor']:
                        if hasattr(radar_display, attr):
                            original_attrs[attr] = getattr(radar_display, attr)
                    
                    # Set explicit dimensions scaled for the container
                    adjusted_width = rect_width / scale_factor
                    adjusted_height = rect_height / scale_factor
                    
                    # Set methods and properties
                    radar_display.width = lambda: adjusted_width
                    radar_display.height = lambda: adjusted_height
                    if hasattr(radar_display, '_width'):
                        radar_display._width = adjusted_width
                    if hasattr(radar_display, '_height'):
                        radar_display._height = adjusted_height
                    
                    try:
                        # Call the paint_display method
                        if hasattr(radar_display, 'paint_display'):
                            radar_display.paint_display(painter)
                        else:
                            raise AttributeError("paint_display method not found")
                    finally:
                        # Restore original attributes
                        for attr, value in original_attrs.items():
                            if callable(value):  # For methods like width(), height()
                                setattr(radar_display, attr, value)
                            else:  # For direct attributes like _width, _height
                                if hasattr(radar_display, attr):
                                    setattr(radar_display, attr, value)
                
                # Let the radar display paint itself with proper dimensions
                try:
                    # Use our custom paint function with proper dimensions
                    custom_paint_radar(
                        self._radar_display, 
                        painter, 
                        adjusted_rect.width(), 
                        adjusted_rect.height()
                    )
                    
                    #logger.info(f"Rendered radar display with dimensions {adjusted_rect.width()}x{adjusted_rect.height()}")
                        
                except Exception as e:
                    logger.error(f"Error rendering radar display: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # Draw error message
                    font = QFont('Arial', 10)
                    painter.setFont(font)
                    painter.setPen(QPen(Qt.GlobalColor.red))
                    painter.drawText(
                        QRectF(0, 0, adjusted_rect.width() / scale_factor, adjusted_rect.height() / scale_factor),
                        Qt.AlignmentFlag.AlignCenter,
                        f"Error: {str(e)}"
                    )
                
                # Restore painter state from radar display drawing
                painter.restore()
                
                # Log that we've rendered the radar display
                #logger.info(f"Rendered radar display with size {adjusted_rect.width()}x{adjusted_rect.height()}")
                
            finally:
                # Restore original painter state
                painter.restore()
        else:
            # Draw error message if radar display is not available
            error_rect = QRectF(
                self.width() * 0.2,
                self.height() * 0.4,
                self.width() * 0.6,
                self.height() * 0.2
            )
            
            self.draw_holographic_text(
                painter,
                error_rect,
                Qt.AlignmentFlag.AlignCenter,
                "WEATHER RADAR DISPLAY UNAVAILABLE",
                depth=0.2,
                color_name="warning"
            )
    
    def draw_weapons_display(self, painter: QPainter):
        """Draw weapons display with holographic effects"""
        # Calculate center and size for weapons display
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # Draw weapons status panel
        self.draw_weapons_status_panel(painter)
        
        # Draw targeting display
        self.draw_targeting_display(painter)
    
    def draw_targeting_display(self, painter: QPainter):
        """Draw targeting display with holographic effects"""
        # Calculate center and radius for targeting display
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) * 0.35
        
        # Draw targeting grid
        self._visual_effects.draw_targeting_grid(
            painter,
            QPointF(center_x, center_y),
            radius,
            color=self._theme_manager.get_color("grid"),
            glow=True,
            depth=0.2
        )
        
        # Draw targeting reticle
        self._visual_effects.draw_targeting_reticle(
            painter,
            QPointF(center_x, center_y),
            radius * 0.8,
            color=self._theme_manager.get_color("critical"),
            glow=True,
            depth=0.3
        )
        
        # Draw target information if a target is selected
        if self.tactical_data["targets"]:
            # Use the first target for demo
            target = self.tactical_data["targets"][0]
            
            # Draw target box
            target_rect = QRectF(
                center_x - radius * 0.2,
                center_y - radius * 0.2,
                radius * 0.4,
                radius * 0.4
            )
            
            self._visual_effects.draw_targeting_box(
                painter,
                target_rect,
                color=self._theme_manager.get_color("critical"),
                lock_status="LOCKED",
                glow=True,
                depth=0.3
            )
            
            # Draw target info panel
            info_panel_rect = QRectF(
                center_x + radius * 0.5,
                center_y - radius * 0.3,
                radius * 0.6,
                radius * 0.6
            )
            
            self._visual_effects.draw_angular_frame(
                painter,
                info_panel_rect,
                color=self._theme_manager.get_color("hud"),
                corner_style="angular",
                glow=True,
                depth=0.1
            )
            
            # Draw target info
            y_offset = info_panel_rect.y() + 10
            
            # Draw target ID
            id_rect = QRectF(
                info_panel_rect.x() + 10,
                y_offset,
                info_panel_rect.width() - 20,
                20
            )
            
            self.draw_holographic_text(
                painter,
                id_rect,
                Qt.AlignmentFlag.AlignCenter,
                target["id"],
                depth=0.2,
                color_name="critical"
            )
            
            y_offset += 25
            
            # Draw target parameters
            params = [
                {"name": "TYPE", "value": target["type"]},
                {"name": "RANGE", "value": f"{int(math.sqrt(target['x']**2 + target['y']**2))} NM"},
                {"name": "ALT", "value": f"{int(target['altitude'])} FT"},
                {"name": "SPEED", "value": f"{int(target['speed'])} KTS"}
            ]
            
            for param in params:
                # Draw parameter name
                name_rect = QRectF(
                    info_panel_rect.x() + 10,
                    y_offset,
                    info_panel_rect.width() / 2 - 15,
                    15
                )
                
                self.draw_holographic_text(
                    painter,
                    name_rect,
                    Qt.AlignmentFlag.AlignLeft,
                    param["name"],
                    depth=0.15,
                    color_name="data_secondary"
                )
                
                # Draw parameter value
                value_rect = QRectF(
                    info_panel_rect.x() + info_panel_rect.width() / 2,
                    y_offset,
                    info_panel_rect.width() / 2 - 10,
                    15
                )
                
                self.draw_holographic_text(
                    painter,
                    value_rect,
                    Qt.AlignmentFlag.AlignRight,
                    param["value"],
                    depth=0.15,
                    color_name="data_primary"
                )
                
                y_offset += 20
            
            # Draw weapon selection
            y_offset += 10
            
            weapon_rect = QRectF(
                info_panel_rect.x() + 10,
                y_offset,
                info_panel_rect.width() - 20,
                20
            )
            
            self.draw_holographic_text(
                painter,
                weapon_rect,
                Qt.AlignmentFlag.AlignCenter,
                "WEAPON: AIM-120C",
                depth=0.2,
                color_name="warning"
            )
    
    def draw_mode_selector(self, painter: QPainter):
        """Draw mode selector with holographic effects"""
        # Calculate mode selector position and size
        selector_width = self.width() * 0.8
        selector_height = 30
        selector_x = (self.width() - selector_width) / 2
        selector_y = self.height() - selector_height - 10
        
        # Draw selector background
        selector_rect = QRectF(selector_x, selector_y, selector_width, selector_height)
        
        self._visual_effects.draw_angular_frame(
            painter,
            selector_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True,
            depth=0.1
        )
        
        # Calculate button width
        button_width = selector_width / len(self.available_modes)
        
        # Draw mode buttons
        for i, mode in enumerate(self.available_modes):
            # Calculate button position
            button_x = selector_x + i * button_width
            
            # Create button rect
            button_rect = QRectF(button_x, selector_y, button_width, selector_height)
            
            # Determine if button is selected
            is_selected = mode == self.display_mode
            
            # Draw button
            if is_selected:
                # Draw selected button
                self._visual_effects.draw_angular_frame(
                    painter,
                    button_rect,
                    color=self._theme_manager.get_color("data_primary"),
                    corner_style="angular",
                    glow=True,
                    depth=0.2
                )
            
            # Draw button text
            text_rect = QRectF(button_x + 5, selector_y + 5, button_width - 10, selector_height - 10)
            
            self.draw_holographic_text(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignCenter,
                mode,
                depth=0.2,
                color_name="data_primary" if is_selected else "hud"
            )
    
    def draw_holographic_bar(self, painter: QPainter, rect: QRectF, value: float, min_value: float, max_value: float, 
                           vertical: bool = False, color_name: str = "data_primary", depth: float = 0.2):
        """Draw a holographic progress bar with glowing effect
        
        Args:
            painter: QPainter instance
            rect: Rectangle to draw the bar in
            value: Current value of the bar
            min_value: Minimum value of the bar
            max_value: Maximum value of the bar
            vertical: Whether the bar is vertical (True) or horizontal (False)
            color_name: Name of the color to use from theme
            depth: Depth effect (0.0 to 1.0)
        """
        # Save painter state
        painter.save()
        
        try:
            # Calculate normalized value (0.0 to 1.0)
            normalized_value = (value - min_value) / (max_value - min_value)
            normalized_value = max(0.0, min(1.0, normalized_value))  # Clamp to 0.0-1.0
            
            # Get color from theme
            color = self._theme_manager.get_color(color_name)
            
            # Draw background
            background_color = QColor(color)
            background_color.setAlpha(40)  # Semi-transparent
            painter.fillRect(rect, background_color)
            
            # Draw border
            self._visual_effects.draw_rect(
                painter,
                rect,
                color=color,
                fill=False,
                corner_radius=0.0,
                glow=True,
                depth=depth
            )
            
            # Calculate fill rectangle based on value and orientation
            if vertical:
                # For vertical bars, fill from bottom to top
                fill_height = rect.height() * normalized_value
                fill_rect = QRectF(
                    rect.x(),
                    rect.y() + rect.height() - fill_height,
                    rect.width(),
                    fill_height
                )
            else:
                # For horizontal bars, fill from left to right
                fill_width = rect.width() * normalized_value
                fill_rect = QRectF(
                    rect.x(),
                    rect.y(),
                    fill_width,
                    rect.height()
                )
            
            # Draw fill with glow effect
            fill_color = QColor(color)
            fill_color.setAlpha(180)  # More opaque than background
            
            # Create gradient for fill
            gradient = QLinearGradient(
                fill_rect.x(),
                fill_rect.y(),
                fill_rect.x() + (fill_rect.width() if not vertical else 0),
                fill_rect.y() + (fill_rect.height() if vertical else 0)
            )
            gradient.setColorAt(0.0, fill_color.lighter(120))
            gradient.setColorAt(1.0, fill_color)
            
            # Fill with gradient
            painter.fillRect(fill_rect, gradient)
            
            # Draw glow effect on the edge of the fill
            glow_pen = QPen(color)
            glow_pen.setWidth(2)
            painter.setPen(glow_pen)
            
            if vertical:
                # Draw horizontal line at the top of the fill
                painter.drawLine(
                    QPointF(fill_rect.x(), fill_rect.y()),
                    QPointF(fill_rect.x() + fill_rect.width(), fill_rect.y())
                )
            else:
                # Draw vertical line at the right edge of the fill
                painter.drawLine(
                    QPointF(fill_rect.x() + fill_rect.width(), fill_rect.y()),
                    QPointF(fill_rect.x() + fill_rect.width(), fill_rect.y() + fill_rect.height())
                )
            
            # Draw value text if there's enough space
            if (vertical and rect.width() >= 30) or (not vertical and rect.height() >= 15):
                # Format value as percentage
                value_text = f"{int(normalized_value * 100)}%"
                
                # Draw text
                text_rect = QRectF(rect)  # Use the entire bar area for text
                
                self.draw_holographic_text(
                    painter,
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    value_text,
                    depth=depth,
                    color_name=color_name
                )
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_startup_animation(self, painter: QPainter):
        """Draw startup animation with holographic effects"""
        # Check if startup animation is needed
        current_time = time.time()
        startup_duration = 2.0  # seconds
        
        # Get time since initialization
        time_since_init = current_time - self._init_time
        
        # If within startup duration, draw animation
        if time_since_init < startup_duration:
            # Calculate animation progress
            animation_progress = time_since_init / startup_duration
            
            # Draw startup overlay
            self._visual_effects.draw_startup_animation(
                painter,
                QRectF(0, 0, self.width(), self.height()),
                animation_progress,
                color=self._theme_manager.get_color("hud"),
                glow=True,
                depth=0.3
            )
            
            # Draw startup text
            text_rect = QRectF(
                self.width() * 0.2,
                self.height() * 0.45,
                self.width() * 0.6,
                self.height() * 0.1
            )
            
            self.draw_holographic_text(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignCenter,
                "INITIALIZING HOLOGRAPHIC MFD",
                depth=0.3,
                color_name="hud"
            )
            
            # Draw progress bar
            progress_rect = QRectF(
                self.width() * 0.3,
                self.height() * 0.55,
                self.width() * 0.4 * animation_progress,
                self.height() * 0.02
            )
            
            self._visual_effects.draw_rect(
                painter,
                progress_rect,
                color=self._theme_manager.get_color("data_primary"),
                fill=True,
                fill_color=self._theme_manager.get_color("data_primary"),
                corner_radius=0.0,
                glow=True,
                depth=0.2
            )
            
            # Request repaint to continue animation
            QTimer.singleShot(16, self.update)
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Convert event position to QPointF
        pos = QPointF(event.position())
        
        # Check if settings panel is visible and handle click
        if hasattr(self, '_settings_panel') and self._settings_panel.visible:
            if self._settings_panel.handle_click(pos):
                # Click was handled by settings panel
                self.update()
                return
        
        # Check if in RADAR mode and radar selection button was clicked
        if self.display_mode == "RADAR" and hasattr(self, '_radar_button_rect'):
            # Track the button rect created in _draw_radar_selection_button
            button_rect = getattr(self, '_radar_button_rect', None)
            
            if button_rect and button_rect.contains(pos):
                logger.info("Radar selection button clicked")
                if self._radar_display and hasattr(self._radar_display, '_radar_selection_menu'):
                    # Calculate menu position centered on button
                    menu_pos = QPointF(
                        button_rect.center().x() - 150,  # Center horizontally
                        button_rect.bottom() + 20        # Below the button
                    )
                    # Store original handle_click method
                    if not hasattr(self, '_original_handle_click'):
                        if hasattr(self._radar_display._radar_selection_menu, 'handle_click'):
                            self._original_handle_click = self._radar_display._radar_selection_menu.handle_click
                            
                            # Create a wrapper to capture the selection
                            def handle_click_wrapper(position):
                                result = self._original_handle_click(position)
                                if isinstance(result, str):
                                    # If result is a string, it's a radar ID to switch to
                                    self._handle_radar_selection(result)
                                return result
                            
                            # Replace handle_click method with our wrapper
                            self._radar_display._radar_selection_menu.handle_click = handle_click_wrapper
                            logger.info("Hooked up radar selection menu events")
                    
                    self._radar_display._radar_selection_menu.show(menu_pos)
                    logger.info(f"Showing radar selection menu at {menu_pos.x():.1f}, {menu_pos.y():.1f}")
                    self.update()
                    return
                else:
                    logger.error("Radar selection menu not available")
        
        # Check if options button was clicked
        if hasattr(self, 'options_button_rect') and self.options_button_rect.contains(pos):
            # Show settings panel
            self._settings_panel.show((self.width() / 2 - 150, self.height() / 2 - 200))
            self.update()
            return
        
        # Check if click is in mode selector area
        selector_width = self.width() * 0.8
        selector_height = 30
        selector_x = (self.width() - selector_width) / 2
        selector_y = self.height() - selector_height - 10
        
        selector_rect = QRectF(selector_x, selector_y, selector_width, selector_height)
        
        if selector_rect.contains(event.position().x(), event.position().y()):
            # Calculate which mode button was clicked
            button_width = selector_width / len(self.available_modes)
            button_index = int((event.position().x() - selector_x) / button_width)
            
            # Ensure index is valid
            if 0 <= button_index < len(self.available_modes):
                # Set new display mode
                self.display_mode = self.available_modes[button_index]
                logger.info(f"Changed display mode to {self.display_mode}")
                
                # Request repaint
                self.update()
                return
        
        # Call parent handler for other clicks
        super().mousePressEvent(event)
    
    def cleanup(self):
        """Clean up resources"""
        super().cleanup()

        # Unsubscribe from the EventBus 'set_mfd_mode' topic before this
        # instance is discarded -- see the NOTE where self._mfd_mode_callback
        # is assigned in __init__ for why this is needed.
        if hasattr(self, '_event_bus') and hasattr(self, '_mfd_mode_callback'):
            try:
                unsubscribed = self._event_bus.unsubscribe('set_mfd_mode', self._mfd_mode_callback)
                logger.info(f"Unsubscribed HolographicMFD instance from EventBus: {unsubscribed}")
            except Exception as e:
                logger.error(f"Error unsubscribing HolographicMFD from EventBus: {str(e)}")
        
        # Stop scan timer
        if self._scan_timer:
            self._scan_timer.stop()
            self._scan_timer = None
            logger.info("Stopped scan timer")
        
        # Clean up settings panel if needed
        if hasattr(self, '_settings_panel'):
            self._settings_panel.visible = False
