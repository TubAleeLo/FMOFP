"""
Holographic radar display with advanced 3D visualization and tactical overlays
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont, QFontMetrics, QTransform
from typing import Dict, List, Optional, Tuple, Any
import math
import time
import random
from .futuristic_radar_display import FuturisticRadarDisplay
from ..visual.theme_manager import get_theme_manager, DisplayTheme
from ..visual.enhanced_theme_manager import get_enhanced_theme_manager, EnhancedDisplayTheme
from ..visual.effects import VisualEffects
from ..visual.animation_controller import AnimationController, TransitionGroup
from ..visual.holographic_settings_panel import HolographicSettingsPanel
from Utils.logger.sys_logger import get_logger
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
from FMOFP.manual_animation_timer import ManualAnimationTimer

logger = get_logger()

class HolographicRadarDisplay(FuturisticRadarDisplay):
    """Advanced holographic radar display with 3D visualization and tactical overlays"""

    def __init__(self):
        """Initialize holographic radar display"""
        super().__init__()

        # Initialize enhanced theme manager
        self._enhanced_theme_manager = get_enhanced_theme_manager()

        # Set theme to holographic in both theme managers
        self._theme_manager.set_theme(DisplayTheme.MODERN)  # Base theme manager for compatibility
        self._enhanced_theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)  # Enhanced theme for holographic effects
        self.update_colors_from_theme()

        # Enhanced display properties
        self.use_holographic_elements = True
        self.use_parallax_effects = True
        self.use_dynamic_focus = True
        self.use_tactical_overlays = True
        self.use_enhanced_targeting = True
        self.use_threat_prioritization = True
        self.use_predictive_tracking = True
        self.use_environmental_awareness = True

        # Target filtering properties
        self.target_filter = "all"  # Default to showing all targets
        self.show_threat_rings = True  # Default to showing threat rings

        # Replace standard settings panel with holographic version
        self._settings_panel = HolographicSettingsPanel()
        self._settings_panel.parent = self  # Set parent reference for context-aware settings

        # Ensure settings panel has the correct theme
        if hasattr(self._settings_panel, '_enhanced_theme_manager'):
            self._settings_panel._enhanced_theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)
            logger.info(f"Set settings panel theme to {EnhancedDisplayTheme.HOLOGRAPHIC.name}")

        # Setup settings panel with our callbacks
        self._setup_settings_panel()

        # Holographic display properties
        self.holo_rotation = 0.0  # Rotation angle for 3D effect
        self.holo_rotation_speed = 5.0  # Degrees per second
        self.holo_elevation = 30.0  # Elevation angle for 3D view
        self.holo_perspective = 0.3  # Perspective factor (0.0 to 1.0)
        self.holo_layer_separation = 0.1  # Separation between layers
        self.holo_layers = 3  # Number of layers in holographic display

        # Focus system
        self.focus_target = None  # Currently focused target
        self.focus_transition = 0.0  # Transition factor for focus effect
        self.focus_pulse = 0.0  # Pulse effect for focused elements

        # Tactical overlay
        self.tactical_zones = []  # Tactical zones (threat areas, etc.)
        self.tactical_routes = []  # Tactical routes (waypoints, etc.)
        self.tactical_annotations = []  # Tactical annotations (text, markers)

        # Threat tracking
        self.threat_analysis = {}  # Threat analysis data
        self.threat_predictions = []  # Predicted threat movements

        # Environmental data
        self.terrain_profile = []  # Terrain profile data
        self.weather_data = {}  # Weather data
        self.visibility_conditions = "CLEAR"  # Current visibility conditions

        # Animation properties
        self.layer_animation_offset = 0.0  # Animation offset for layer effects
        self.scan_line_position = 0.0  # Position of scanning line effect
        self.data_refresh_progress = 0.0  # Progress of data refresh animation

        # Manual animation timer as a fallback
        self._manual_animation_timer = ManualAnimationTimer(update_interval=50)  # 20 Hz

        # Initialize holographic elements
        self._init_holographic_elements()

    def update_colors_from_theme(self):
        """Update display colors from current theme"""
        # First update colors from base theme manager (parent class)
        super().update_colors_from_theme()

        # Then update colors from enhanced theme manager
        if hasattr(self, '_enhanced_theme_manager'):
            # Update holographic-specific colors
            logger.info("Updating colors from enhanced theme manager")

            # Make sure settings panel is also updated
            if hasattr(self, '_settings_panel') and self._settings_panel is not None:
                if hasattr(self._settings_panel, '_enhanced_theme_manager'):
                    self._settings_panel._enhanced_theme_manager.set_theme(self._enhanced_theme_manager.get_theme())
                    logger.info(f"Updated settings panel theme to {self._enhanced_theme_manager.get_theme().name}")

    def _setup_settings_panel(self):
        """Set up settings panel with holographic-specific settings and callbacks"""
        # We're not calling the parent method to avoid duplicate settings
        # Instead, we'll add only the settings we need

        # Add theme setting explicitly
        self._settings_panel.add_setting(
            "theme",
            "Theme",
            "select",
            "holographic",  # Default to holographic theme
            options=[
                ("Classic", "classic"),
                ("Modern", "modern"),
                ("Night", "night"),
                ("Holographic", "holographic")
            ],
            on_change=self._on_theme_changed
        )

        # Log that we added the theme setting with a callback
        logger.info(f"Added theme setting with callback: {self._on_theme_changed}")

        # Range scale setting
        self._settings_panel.add_setting(
            "range_scale",
            "Range Scale",
            "select",
            str(self.range_scale),
            options=[
                ("20 NM", "20"),
                ("40 NM", "40"),
                ("80 NM", "80"),
                ("160 NM", "160")
            ],
            on_change=self._on_range_scale_changed
        )

        # Grid type setting
        self._settings_panel.add_setting(
            "grid_type",
            "Grid Type",
            "select",
            "hexagonal",
            options=[
                ("Hexagonal", "hexagonal"),
                ("Circular", "circular"),
                ("Radial", "radial")
            ],
            on_change=self._on_grid_type_changed
        )

        # Glow effects setting
        self._settings_panel.add_setting(
            "use_glow",
            "Glow Effects",
            "toggle",
            True,
            on_change=self._on_glow_changed
        )

        # Animations setting
        self._settings_panel.add_setting(
            "use_animations",
            "Animations",
            "toggle",
            True,
            on_change=self._on_animations_changed
        )

        # Information density setting
        self._settings_panel.add_setting(
            "information_density",
            "Information Density",
            "select",
            "tactical",
            options=[
                ("Minimal", "minimal"),
                ("Standard", "standard"),
                ("Tactical", "tactical"),
                ("Maximum", "maximum")
            ],
            on_change=self._on_density_changed
        )

        # Target filtering with integrated threat rings
        self._settings_panel.add_setting(
            "target_filtering",
            "Target Filter",
            "select",
            "all",  # Use lowercase to match the implementation
            options=[
                ("All", "all"),
                ("Hostile Only", "hostile"),
                ("Friendly Only", "friendly"),
                ("No Threats", "none")
            ],
            on_change=self._on_target_filtering_changed
        )

        # Add holographic display properties
        self._settings_panel.add_setting(
            "holo_rotation_speed",
            "Rotation Speed",
            "range",
            self.holo_rotation_speed,
            min_value=0.0,
            max_value=10.0,
            on_change=self._on_rotation_speed_changed
        )

        self._settings_panel.add_setting(
            "holo_elevation",
            "Elevation Angle",
            "range",
            self.holo_elevation,
            min_value=0.0,
            max_value=60.0,
            on_change=self._on_elevation_changed
        )

        self._settings_panel.add_setting(
            "holo_perspective",
            "3D Perspective",
            "range",
            self.holo_perspective,
            min_value=0.0,
            max_value=1.0,
            on_change=self._on_perspective_changed
        )

        self._settings_panel.add_setting(
            "holo_layer_separation",
            "Layer Separation",
            "range",
            self.holo_layer_separation,
            min_value=0.0,
            max_value=0.5,
            on_change=self._on_layer_separation_changed
        )

        self._settings_panel.add_setting(
            "holo_layers",
            "Number of Layers",
            "select",
            self.holo_layers,
            options=[
                ("2 Layers", 2),
                ("3 Layers", 3),
                ("4 Layers", 4),
                ("5 Layers", 5)
            ],
            on_change=self._on_layers_changed
        )

        # Feature toggles
        self._settings_panel.add_setting(
            "use_parallax_effects",
            "Parallax Effects",
            "toggle",
            self.use_parallax_effects,
            on_change=self._on_parallax_effects_changed
        )

        self._settings_panel.add_setting(
            "use_dynamic_focus",
            "Dynamic Focus",
            "toggle",
            self.use_dynamic_focus,
            on_change=self._on_dynamic_focus_changed
        )

        self._settings_panel.add_setting(
            "use_tactical_overlays",
            "Tactical Overlays",
            "toggle",
            self.use_tactical_overlays,
            on_change=self._on_tactical_overlays_changed
        )

        self._settings_panel.add_setting(
            "use_enhanced_targeting",
            "Enhanced Targeting",
            "toggle",
            self.use_enhanced_targeting,
            on_change=self._on_enhanced_targeting_changed
        )

        self._settings_panel.add_setting(
            "use_threat_prioritization",
            "Threat Prioritization",
            "toggle",
            self.use_threat_prioritization,
            on_change=self._on_threat_prioritization_changed
        )

        self._settings_panel.add_setting(
            "use_predictive_tracking",
            "Predictive Tracking",
            "toggle",
            self.use_predictive_tracking,
            on_change=self._on_predictive_tracking_changed
        )

        self._settings_panel.add_setting(
            "use_environmental_awareness",
            "Environmental Awareness",
            "toggle",
            self.use_environmental_awareness,
            on_change=self._on_environmental_awareness_changed
        )

    # Callback methods for holographic settings
    def _on_grid_type_changed(self, grid_type: str):
        """Handle grid type change"""
        # Store the grid type locally instead of trying to modify theme
        self.grid_type = grid_type
        logger.info(f"Changed grid type to {grid_type}")
        # Request a repaint to show the change
        self.update()

    def _on_glow_changed(self, use_glow: bool):
        """Handle glow effects change"""
        # Store the glow setting locally instead of trying to modify theme
        self.use_glow = use_glow
        logger.info(f"Changed glow effects to {use_glow}")
        # Request a repaint to show the change
        self.update()

    def _on_animations_changed(self, use_animations: bool):
        """Handle animations change"""
        # Store the animations setting locally
        self.use_animations = use_animations
        logger.info(f"Changed animations to {use_animations}")

        # Start or stop animations based on setting
        if use_animations:
            if not self._animation_controller.is_running():
                self._animation_controller.start()
                self._start_animations()
                logger.info("Started animations")
        else:
            if self._animation_controller.is_running():
                self._animation_controller.cancel_all_animations()
                logger.info("Stopped animations")

        # Request a repaint to show the change
        self.update()

    def _on_density_changed(self, density: str):
        """Handle information density change"""
        # Store the information density locally instead of trying to modify theme
        self.information_density = density
        logger.info(f"Changed information density to {density}")
        # Request a repaint to show the change
        self.update()

    def _on_rotation_speed_changed(self, value):
        """Handle rotation speed change"""
        self.holo_rotation_speed = value
        logger.info(f"Changed rotation speed to {value}")
        # Restart animations with new speed
        self._restart_holo_rotation_animation()

    def _on_elevation_changed(self, value):
        """Handle elevation angle change"""
        self.holo_elevation = value
        logger.info(f"Changed elevation angle to {value}")
        self.update()  # Request repaint

    def _on_perspective_changed(self, value):
        """Handle perspective factor change"""
        self.holo_perspective = value
        logger.info(f"Changed perspective factor to {value}")
        self.update()  # Request repaint

    def _on_layer_separation_changed(self, value):
        """Handle layer separation change"""
        self.holo_layer_separation = value
        logger.info(f"Changed layer separation to {value}")
        self.update()  # Request repaint

    def _on_layers_changed(self, value):
        """Handle number of layers change"""
        self.holo_layers = value
        logger.info(f"Changed number of layers to {value}")
        self.update()  # Request repaint

    def _on_parallax_effects_changed(self, value):
        """Handle parallax effects toggle"""
        self.use_parallax_effects = value
        logger.info(f"Changed parallax effects to {value}")
        self.update()  # Request repaint

    def _on_dynamic_focus_changed(self, value):
        """Handle dynamic focus toggle"""
        self.use_dynamic_focus = value
        logger.info(f"Changed dynamic focus to {value}")
        self.update()  # Request repaint

    def _on_tactical_overlays_changed(self, value):
        """Handle tactical overlays toggle"""
        self.use_tactical_overlays = value
        logger.info(f"Changed tactical overlays to {value}")
        self.update()  # Request repaint

    def _on_enhanced_targeting_changed(self, value):
        """Handle enhanced targeting toggle"""
        self.use_enhanced_targeting = value
        logger.info(f"Changed enhanced targeting to {value}")
        self.update()  # Request repaint

    def _on_threat_prioritization_changed(self, value):
        """Handle threat prioritization toggle"""
        self.use_threat_prioritization = value
        logger.info(f"Changed threat prioritization to {value}")
        self.update()  # Request repaint

    def _on_predictive_tracking_changed(self, value):
        """Handle predictive tracking toggle"""
        self.use_predictive_tracking = value
        logger.info(f"Changed predictive tracking to {value}")
        self.update()  # Request repaint

    def _on_environmental_awareness_changed(self, value):
        """Handle environmental awareness toggle"""
        self.use_environmental_awareness = value
        logger.info(f"Changed environmental awareness to {value}")
        self.update()  # Request repaint

    def _on_range_scale_changed(self, value):
        """Handle range scale change"""
        # Convert value to integer (it comes as a string from the settings panel)
        try:
            new_range = int(value)
            # Update the range scale
            self.range_scale = new_range
            logger.info(f"Changed range scale to {new_range} NM")
            # Request a repaint to show the change
            self.update()
        except ValueError:
            logger.error(f"Invalid range scale value: {value}")

    def _on_theme_changed(self, theme_name: str):
        """Handle theme change by updating both base and enhanced theme managers"""
        logger.info(f"[HOLO_RADAR] Changing theme to {theme_name}")
        logger.info(f"[HOLO_RADAR] Current theme before change - Base: {self._theme_manager.get_theme().name}, Enhanced: {self._enhanced_theme_manager.get_theme().name}")

        # Map base theme name to base theme enum
        base_theme_map = {
            "classic": DisplayTheme.CLASSIC,
            "modern": DisplayTheme.MODERN,
            "night": DisplayTheme.NIGHT,
            "holographic": DisplayTheme.MODERN  # Map to MODERN as fallback for base theme
        }

        # Map base theme name to enhanced theme enum
        enhanced_theme_map = {
            "classic": EnhancedDisplayTheme.CLASSIC,
            "modern": EnhancedDisplayTheme.MODERN,
            "night": EnhancedDisplayTheme.STEALTH,
            "holographic": EnhancedDisplayTheme.HOLOGRAPHIC
        }

        # Update base theme manager
        if theme_name in base_theme_map:
            base_theme = base_theme_map[theme_name]
            self._theme_manager.set_theme(base_theme)
            logger.info(f"[HOLO_RADAR] Set base theme to {base_theme.name}")
        else:
            logger.error(f"[HOLO_RADAR] Unknown base theme name: {theme_name}")

        # Update enhanced theme manager
        if theme_name in enhanced_theme_map:
            enhanced_theme = enhanced_theme_map[theme_name]
            self._enhanced_theme_manager.set_theme(enhanced_theme)
            logger.info(f"[HOLO_RADAR] Set enhanced theme to {enhanced_theme.name}")
        else:
            logger.error(f"[HOLO_RADAR] Unknown enhanced theme name: {theme_name}")

        # Log current theme after change
        logger.info(f"[HOLO_RADAR] Current theme after change - Base: {self._theme_manager.get_theme().name}, Enhanced: {self._enhanced_theme_manager.get_theme().name}")

        # Update colors from both theme managers
        self.update_colors_from_theme()
        logger.info("[HOLO_RADAR] Updated colors from theme")

        # Update settings panel theme if available
        if hasattr(self, '_settings_panel') and self._settings_panel is not None:
            if hasattr(self._settings_panel, '_enhanced_theme_manager'):
                panel_theme = enhanced_theme_map.get(theme_name, EnhancedDisplayTheme.HOLOGRAPHIC)
                self._settings_panel._enhanced_theme_manager.set_theme(panel_theme)
                logger.info(f"[HOLO_RADAR] Updated settings panel theme to {panel_theme.name}")
            else:
                logger.warning("[HOLO_RADAR] Settings panel does not have _enhanced_theme_manager")
        else:
            logger.warning("[HOLO_RADAR] Settings panel not available")

        # Force a repaint
        logger.info("[HOLO_RADAR] Forcing repaint")
        self.update()

    def _on_target_filtering_changed(self, filter_mode: str):
        """Handle target filtering change with integrated threat rings"""
        # Store the filter mode
        self.target_filter = filter_mode

        # Update threat rings visibility based on filter mode
        # If "none" is selected, we'll hide threat rings completely
        self.show_threat_rings = filter_mode != "none"

        # If "friendly" is selected, we'll still show the display but hide enemy threats
        # This is handled in the _draw_tracked_objects method

        logger.info(f"Changed target filtering to {filter_mode}, threat rings: {self.show_threat_rings}")
        self.update()  # Request repaint

    def _init_holographic_elements(self):
        """Initialize holographic display elements"""
        # Generate sample tactical zones
        self._generate_sample_tactical_zones()

        # Generate sample tactical routes
        self._generate_sample_tactical_routes()

        # Generate sample terrain profile
        self.terrain_profile = self._generate_sample_terrain_data(48)

        # Generate sample weather data
        self.weather_data = {
            "precipitation": random.uniform(0.0, 0.5),
            "cloud_cover": random.uniform(0.2, 0.8),
            "wind_speed": random.uniform(5.0, 15.0),
            "wind_direction": random.uniform(0.0, 360.0),
            "turbulence": random.uniform(0.0, 0.3)
        }

        # Make sure animation controller is running
        if not self._animation_controller.is_running():
            self._animation_controller.start()
            logger.info("Started animation controller")

        # Set up animations with completion callbacks to ensure continuous animation
        self._start_animations()

        # Set up manual animations as a fallback
        self._setup_manual_animations()

        # Ensure settings panel is properly initialized
        self._ensure_settings_panel_ready()

    def _ensure_settings_panel_ready(self):
        """Ensure settings panel is properly initialized and ready for use"""
        # Make sure settings panel has all necessary settings
        if not hasattr(self, '_settings_panel') or self._settings_panel is None:
            logger.warning("Settings panel not initialized, creating new one")
            self._settings_panel = HolographicSettingsPanel()
            self._settings_panel.parent = self
            self._setup_settings_panel()

        # Ensure settings panel has the correct theme
        if hasattr(self._settings_panel, '_enhanced_theme_manager'):
            self._settings_panel._enhanced_theme_manager.set_theme(EnhancedDisplayTheme.HOLOGRAPHIC)

        # Ensure settings panel has the correct size
        if hasattr(self._settings_panel, 'width') and hasattr(self._settings_panel, 'height'):
            # Count total number of settings
            total_settings = len(self._settings_panel.options)

            # Calculate required height based on number of settings
            # Each setting takes about 40px height, plus 150px for header and padding
            required_height = total_settings * 40 + 150

            # Use fixed values instead of relying on width() and height() methods
            self._settings_panel.width = 400  # Fixed width for better visibility
            self._settings_panel.height = max(required_height, 450)  # Fixed height to fit all settings

            logger.info(f"Adjusted settings panel size to {self._settings_panel.width}x{self._settings_panel.height} for {total_settings} settings")

        # Log that settings panel is ready
        logger.info("Settings panel initialized and ready for use")

    def showEvent(self, event):
        """Handle show event to ensure settings panel is ready when display is shown"""
        super().showEvent(event)

        # Ensure settings panel is ready when display is shown
        self._ensure_settings_panel_ready()

        # Make sure options button is properly positioned
        self.options_button_rect = QRectF(
            self.width() - 50,  # Position in top-right corner
            10,
            40,
            40
        )

        # Log that display is shown and settings panel is ready
        logger.info("Holographic radar display shown, settings panel ready")

    def test_settings_panel(self):
        """Test method to verify settings panel functionality

        This method can be called from the console or a test script to verify
        that the settings panel is working correctly. It simulates clicking
        the options button and verifies that the settings panel is shown.

        Returns:
            bool: True if settings panel is working correctly, False otherwise
        """
        logger.info("Testing settings panel functionality")

        # Ensure settings panel is ready
        self._ensure_settings_panel_ready()

        # Verify that settings panel exists and is properly initialized
        if not hasattr(self, '_settings_panel') or self._settings_panel is None:
            logger.error("Settings panel does not exist")
            return False

        # Verify that settings panel has the correct theme
        if hasattr(self._settings_panel, '_enhanced_theme_manager'):
            theme = self._settings_panel._enhanced_theme_manager.get_theme()
            if theme != EnhancedDisplayTheme.HOLOGRAPHIC:
                logger.error(f"Settings panel has incorrect theme: {theme}")
                return False

        # Verify that settings panel has the correct settings
        required_settings = [
            "target_filtering",
            "holo_rotation_speed",
            "holo_elevation",
            "holo_perspective",
            "holo_layer_separation",
            "holo_layers"
        ]

        for setting_id in required_settings:
            found = False
            for option in self._settings_panel.options:
                if option.id == setting_id:
                    found = True
                    break

            if not found:
                logger.error(f"Settings panel missing required setting: {setting_id}")
                return False

        # Simulate clicking the options button
        logger.info("Simulating click on options button")
        self._settings_panel.show((self.width() / 2 - 150, self.height() / 2 - 200))

        # Verify that settings panel is visible
        if not self._settings_panel.visible:
            logger.error("Settings panel not visible after simulated click")
            return False

        # Hide settings panel
        self._settings_panel.hide()

        # Log success
        logger.info("Settings panel test completed successfully")
        return True

    def _setup_manual_animations(self):
        """Set up manual animations as a fallback"""
        logger.info("Setting up manual animations")

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

    def _start_animations(self):
        """Start all animations with proper completion callbacks"""
        logger.info("Starting all animations")

        # Cancel any existing animations first
        self._animation_controller.cancel_animation("holo_rotation")
        self._animation_controller.cancel_animation("scan_line")
        self._animation_controller.cancel_animation("layer_offset")

        # Create new animations with completion callbacks
        self._animation_controller.create_animation(
            "holo_rotation",
            0.0,
            360.0,
            360.0 / self.holo_rotation_speed,
            lambda value: self._set_holo_rotation(value),
            lambda: self._restart_holo_rotation_animation(),
            QEasingCurve.Type.Linear
        )

        self._animation_controller.create_animation(
            "scan_line",
            0.0,
            1.0,
            2.0,
            lambda value: self._set_scan_line_position(value),
            lambda: self._restart_scan_line_animation(),
            QEasingCurve.Type.Linear
        )

        self._animation_controller.create_animation(
            "layer_offset",
            0.0,
            1.0,
            5.0,
            lambda value: self._set_layer_animation_offset(value),
            lambda: self._restart_layer_offset_animation(),
            QEasingCurve.Type.Linear
        )

    def _restart_holo_rotation_animation(self):
        """Restart the holographic rotation animation to create continuous effect"""
        logger.info("Restarting holo_rotation animation")
        self._animation_controller.create_animation(
            "holo_rotation",
            0.0,
            360.0,
            360.0 / self.holo_rotation_speed,
            lambda value: self._set_holo_rotation(value),
            lambda: self._restart_holo_rotation_animation(),
            QEasingCurve.Type.Linear
        )

    def _restart_scan_line_animation(self):
        """Restart the scan line animation to create continuous radar sweep effect"""
        logger.info("Restarting scan_line animation")
        # Fix: Ensure the animation controller is running
        if not self._animation_controller.is_running():
            self._animation_controller.start()
            logger.warning("Animation controller was not running, restarted it")

        # Fix: Use a more reliable animation setup with proper error handling
        try:
            self._animation_controller.create_animation(
                "scan_line",
                0.0,
                1.0,
                2.0,
                lambda value: self._set_scan_line_position(value),
                lambda: self._restart_scan_line_animation(),
                QEasingCurve.Type.Linear
            )
            logger.info("Successfully created new scan_line animation")
        except Exception as e:
            logger.error(f"Failed to create scan_line animation: {str(e)}")
            # Fallback: Use manual animation timer
            if not self._manual_animation_timer.is_running():
                self._manual_animation_timer.start()
                logger.warning("Using manual animation timer as fallback")

    def _restart_layer_offset_animation(self):
        """Restart the layer offset animation to create continuous effect"""
        logger.info("Restarting layer_offset animation")
        self._animation_controller.create_animation(
            "layer_offset",
            0.0,
            1.0,
            5.0,
            lambda value: self._set_layer_animation_offset(value),
            lambda: self._restart_layer_offset_animation(),
            QEasingCurve.Type.Linear
        )

    def _set_holo_rotation(self, value):
        """Set holographic rotation angle"""
        self.holo_rotation = value
        # Request a repaint to show the change
        self.update()

    def _set_scan_line_position(self, value):
        """Set scan line position"""
        self.scan_line_position = value
        # Request a repaint to show the change
        self.update()

    def _set_layer_animation_offset(self, value):
        """Set layer animation offset"""
        self.layer_animation_offset = value
        # Request a repaint to show the change
        self.update()

    def _generate_sample_tactical_zones(self):
        """Generate sample tactical zones for display"""
        # Create a few tactical zones
        for i in range(3):
            # Random position
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(20, 35)

            x = distance * math.sin(angle)
            y = distance * math.cos(angle)

            # Random size
            radius = random.uniform(5, 15)

            # Random type
            zone_type = random.choice(["THREAT", "RESTRICTED", "CAUTION"])

            # Create zone
            zone = {
                "position": (x, y),
                "radius": radius,
                "type": zone_type,
                "intensity": random.uniform(0.3, 1.0)
            }

            self.tactical_zones.append(zone)

    def _generate_sample_tactical_routes(self):
        """Generate sample tactical routes for display"""
        # Create a few tactical routes
        for i in range(2):
            # Create waypoints
            waypoints = []

            # Starting point
            start_angle = random.uniform(0, 2 * math.pi)
            start_distance = random.uniform(10, 30)

            start_x = start_distance * math.sin(start_angle)
            start_y = start_distance * math.cos(start_angle)

            waypoints.append((start_x, start_y))

            # Add additional waypoints
            num_waypoints = random.randint(3, 6)

            for j in range(num_waypoints):
                # Random offset from previous point
                prev_x, prev_y = waypoints[-1]

                offset_angle = random.uniform(0, 2 * math.pi)
                offset_distance = random.uniform(5, 15)

                new_x = prev_x + offset_distance * math.sin(offset_angle)
                new_y = prev_y + offset_distance * math.cos(offset_angle)

                # Ensure within range
                distance = math.sqrt(new_x**2 + new_y**2)
                if distance > 40:
                    # Scale back
                    scale = 40 / distance
                    new_x *= scale
                    new_y *= scale

                waypoints.append((new_x, new_y))

            # Create route
            route = {
                "waypoints": waypoints,
                "type": "FLIGHT_PATH" if i == 0 else "PATROL_ROUTE",
                "active": random.choice([True, False])
            }

            self.tactical_routes.append(route)

    def draw_display(self, painter: QPainter, rect: QRectF, data: Dict = None):
        """Override draw_display to ensure options button is drawn with enhanced visibility"""
        # Call parent method to draw base display
        super().draw_display(painter, rect, data)

        # Draw an enhanced, more visible settings icon in the top-right corner
        self._draw_enhanced_options_button(painter, self.options_button_rect)

    def _draw_enhanced_options_button(self, painter: QPainter, rect: QRectF):
        """Draw an enhanced, more visible settings icon"""
        # Save painter state
        painter.save()

        try:
            # Draw button background with pulsing effect
            background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
            background_color.setAlpha(200)  # More opaque for better visibility
            painter.fillRect(rect, background_color)

            # Draw button frame with prominent glow
            self._visual_effects.draw_angular_frame(
                painter,
                rect,
                color=self._enhanced_theme_manager.get_color("data_primary"),  # Use more noticeable color
                corner_style="angular",
                glow=True
            )

            # Draw gear icon
            # Calculate center and radius
            center_x = rect.x() + rect.width() / 2
            center_y = rect.y() + rect.height() / 2
            radius = min(rect.width(), rect.height()) * 0.35  # Slightly larger

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
                color=self._enhanced_theme_manager.get_color("data_primary"),  # More noticeable color
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
                color=self._enhanced_theme_manager.get_color("data_primary"),
                fill=True,
                glow=True
            )

            # Draw gear teeth with more contrast
            num_teeth = 8
            for i in range(num_teeth):
                angle = 2 * math.pi * i / num_teeth

                # Calculate tooth position
                tooth_x = center_x + radius * 1.4 * math.cos(angle)
                tooth_y = center_y + radius * 1.4 * math.sin(angle)

                # Draw tooth line with increased width for visibility
                self._visual_effects.draw_enhanced_line(
                    painter,
                    QPointF(center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)),
                    QPointF(tooth_x, tooth_y),
                    color=self._enhanced_theme_manager.get_color("data_primary"),
                    width=2.0,  # Thicker line
                    glow=True
                )

            # Add "SETTINGS" label below the gear icon for clarity
            label_rect = QRectF(
                rect.x() - 10,  # Extend beyond button for text
                rect.bottom() + 2,
                rect.width() + 20,  # Wider for text
                15
            )

            self._visual_effects.draw_enhanced_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                "SETTINGS",
                glow=True,
                glow_color=self._enhanced_theme_manager.get_color("data_primary")
            )

        finally:
            # Restore painter state
            painter.restore()

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw holographic radar display with advanced effects"""
        # Get theme parameters
        use_holographic_elements = self._theme_manager.get_style_param("use_holographic_elements", True)

        if use_holographic_elements:
            # Draw holographic radar display
            self._draw_holographic_radar(painter, rect, data)
        else:
            # Fall back to standard futuristic display
            super().draw_radar_elements(painter, rect, data)

    def _draw_holographic_radar(self, painter: QPainter, rect: QRectF, data: Dict):
        """Draw holographic radar with 3D layered effect"""
        # Completely clear the display with proper composition mode
        # This ensures no artifacts from previous frames remain
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(rect, QColor(0, 0, 0, 255))
        painter.restore()

        # Save state for the rest of the drawing
        painter.save()

        try:
            # Calculate radar center and radius
            center_x = rect.width() * 0.5
            center_y = rect.height() * 0.5

            # Adjust for side panel if visible
            if self.side_panel_width > 0:
                center_x = (rect.width() - self.side_panel_width) * 0.5

            center = QPointF(center_x, center_y)
            radius = min(center_x, center_y) * 0.85

            # Draw layered background with proper composition mode
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self._visual_effects.draw_layered_background(
                painter,
                rect,
                base_color=self._enhanced_theme_manager.get_color("background"),
                grid_color=self._enhanced_theme_manager.get_color("grid"),
                grid_type=self._theme_manager.get_style_param("grid_type", "hexagonal")
            )

            # Create offscreen buffer for each layer to prevent transparency issues
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

                # Set composition mode for proper layer blending
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

                # Translate to center
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
                self._draw_radar_layer(
                    painter,
                    rect,
                    center,
                    radius,
                    data,
                    layer,
                    layer_z + layer_animation
                )

                painter.restore()

            # Reset composition mode for remaining elements
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Draw scan line effect
            self._draw_scan_line(painter, center, radius)

            # Draw tactical overlays
            if self.use_tactical_overlays:
                # RWR contacts from DefensiveService overlaid at depth layer 2
                try:
                    from FMOFP.Systems.defensiveSys.defensiveService import get_defensive_service
                    rwr = get_defensive_service().get_rwr_contacts()
                    if rwr:
                        cx2 = center.x()
                        cy2 = center.y()
                        r2  = min(cx2, cy2) * 0.85
                        rwr_color = QColor(255, 80, 80, 180)
                        for contact in rwr:
                            b = math.radians(contact.get("bearing_deg", 0) - 90)
                            rx = cx2 + r2 * math.cos(b)
                            ry = cy2 + r2 * math.sin(b)
                            painter.setPen(QPen(rwr_color, 2))
                            painter.setBrush(rwr_color)
                            painter.drawEllipse(QPointF(rx, ry), 5, 5)
                except Exception:
                    logger.debug("HolographicRadarDisplay: DefensiveService not yet running", exc_info=True)

            # Draw side panel if visible
            if self.side_panel_width > 0:
                self._draw_side_panel(painter, rect)

            # Draw mode indicator and status
            self._draw_mode_indicator(painter, rect)

            # Draw holographic frame
            self._draw_holographic_frame(painter, rect)

        finally:
            # Restore state
            painter.restore()

    def _draw_radar_layer(self, painter: QPainter, rect: QRectF, center: QPointF,
                        radius: float, data: Dict, layer: int, layer_z: float):
        """Draw elements for a specific holographic layer"""
        # Different elements on different layers
        if layer == 0:  # Bottom layer
            # Draw grid
            grid_type = self._theme_manager.get_style_param("grid_type", "hexagonal")

            if grid_type == "hexagonal":
                self._visual_effects.draw_hexagonal_grid(
                    painter,
                    center,
                    radius,
                    color=self._enhanced_theme_manager.get_color("grid"),
                    rings=4,
                    glow=True
                )
            else:
                # Draw traditional range rings
                self.draw_range_rings(painter, center, radius)

            # Draw terrain visualization if enabled
            if self.show_3d_terrain:
                self._draw_terrain_visualization(painter, rect)

        elif layer == 1:  # Middle layer
            # Draw tactical zones
            self._draw_tactical_zones(painter, center, radius)

            # Draw tactical routes
            self._draw_tactical_routes(painter, center, radius)

        elif layer == 2:  # Top layer
            # Draw tracked objects
            self._draw_tracked_objects(painter, center, radius, data)

            # Draw threat predictions if enabled
            if self.use_predictive_tracking:
                self._draw_threat_predictions(painter, center, radius)

            # Draw cardinal directions
            self._draw_cardinal_directions(painter, center, radius)

    def _draw_scan_line(self, painter: QPainter, center: QPointF, radius: float):
        """Draw animated scan line effect"""
        # Calculate scan angle
        scan_angle = self.scan_line_position * 360.0

        # Calculate scan endpoint
        scan_rad = math.radians(scan_angle)
        end_x = center.x() + radius * math.sin(scan_rad)
        end_y = center.y() - radius * math.cos(scan_rad)

        # Create scan color with pulse effect
        scan_color = QColor(self._enhanced_theme_manager.get_color("data_primary"))

        # Save painter state
        painter.save()

        # Use proper composition mode for the scan line
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Draw scan line with glow
        self._visual_effects.draw_enhanced_line(
            painter,
            center,
            QPointF(end_x, end_y),
            color=scan_color,
            width=2.0,
            glow=True
        )

        # Draw scan arc (fading trail)
        path = QPainterPath()
        path.moveTo(center)

        # Calculate arc angles
        start_angle = (scan_angle - 30) % 360
        if start_angle > scan_angle:
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
        arc_color = QColor(scan_color)
        arc_color.setAlpha(100)

        # Draw arc with semi-transparency
        painter.setBrush(QBrush(arc_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Restore painter state
        painter.restore()

    def _draw_tactical_zones(self, painter: QPainter, center: QPointF, radius: float):
        """Draw tactical zones (threat areas, restricted airspace, etc.)"""
        for zone in self.tactical_zones:
            # Get zone properties
            position = zone.get("position", (0, 0))
            zone_radius = zone.get("radius", 10)
            zone_type = zone.get("type", "THREAT")
            intensity = zone.get("intensity", 1.0)

            # Convert position to screen coordinates
            screen_pos = self.world_to_screen(position, center, radius, self.range_scale)

            # Calculate screen radius
            screen_radius = zone_radius * (radius / self.range_scale)

            # Determine color based on zone type
            if zone_type == "THREAT":
                color = self._enhanced_theme_manager.get_color("tactical_overlay")
            elif zone_type == "RESTRICTED":
                color = self._enhanced_theme_manager.get_color("warning")
            else:  # CAUTION
                color = self._enhanced_theme_manager.get_color("caution")

            # Apply intensity
            zone_color = QColor(color)
            zone_color.setAlpha(int(color.alpha() * intensity * 0.7))

            # Create zone rect
            zone_rect = QRectF(
                screen_pos.x() - screen_radius,
                screen_pos.y() - screen_radius,
                screen_radius * 2,
                screen_radius * 2
            )

            # Draw zone with fill and glow
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                zone_rect,
                color=color,
                fill=True,
                fill_color=zone_color,
                glow=True
            )

            # Draw zone label
            label_rect = QRectF(
                screen_pos.x() - screen_radius,
                screen_pos.y() - screen_radius - 20,
                screen_radius * 2,
                20
            )

            self._visual_effects.draw_enhanced_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                zone_type,
                glow=True,
                glow_color=color
            )

    def _draw_tactical_routes(self, painter: QPainter, center: QPointF, radius: float):
        """Draw tactical routes (waypoints, patrol routes, etc.)"""
        for route in self.tactical_routes:
            # Get route properties
            waypoints = route.get("waypoints", [])
            route_type = route.get("type", "FLIGHT_PATH")
            active = route.get("active", True)

            if not waypoints:
                continue

            # Determine color based on route type
            if route_type == "FLIGHT_PATH":
                color = self._enhanced_theme_manager.get_color("waypoint")
            else:  # PATROL_ROUTE
                color = self._enhanced_theme_manager.get_color("friendly")

            # Apply active/inactive state
            if not active:
                route_color = QColor(color)
                route_color.setAlpha(int(color.alpha() * 0.5))
            else:
                route_color = color

            # Create path for route
            path = QPainterPath()

            # Convert first waypoint to screen coordinates
            first_point = self.world_to_screen(waypoints[0], center, radius, self.range_scale)
            path.moveTo(first_point)

            # Add remaining waypoints
            for i in range(1, len(waypoints)):
                screen_point = self.world_to_screen(waypoints[i], center, radius, self.range_scale)
                path.lineTo(screen_point)

            # Draw route with glow
            self._visual_effects.draw_enhanced_path(
                painter,
                path,
                color=route_color,
                fill=False,
                glow=active
            )

            # Draw waypoint markers
            for waypoint in waypoints:
                screen_point = self.world_to_screen(waypoint, center, radius, self.range_scale)

                # Draw waypoint marker
                marker_size = 6
                marker_rect = QRectF(
                    screen_point.x() - marker_size / 2,
                    screen_point.y() - marker_size / 2,
                    marker_size,
                    marker_size
                )

                self._visual_effects.draw_enhanced_ellipse(
                    painter,
                    marker_rect,
                    color=route_color,
                    fill=True,
                    glow=active
                )

    def _get_tracked_objects(self) -> List[Dict]:
        """Get current tracked objects from RadarDataFusion; fall back to samples."""
        try:
            if not hasattr(self, "_fusion") or self._fusion is None:
                from FMOFP.Systems.radarManagement.radar_data_fusion import get_radar_data_fusion
                self._fusion = get_radar_data_fusion()
            tracks = self._fusion.get_fused_tracks()
            if tracks:
                result = []
                for t in tracks:
                    d = t.to_tsd_dict() if hasattr(t, "to_tsd_dict") else {}
                    result.append({
                        "type":         "enemy" if d.get("hostile") else
                                        "friendly" if d.get("identity") == "FRIENDLY" else "neutral",
                        "position":     (d.get("range_nm", 0) * math.cos(math.radians(d.get("bearing", 0))),
                                         d.get("range_nm", 0) * math.sin(math.radians(d.get("bearing", 0)))),
                        "velocity":     (d.get("vx", 0), d.get("vy", 0)),
                        "threat_level": min(10, max(0, int(d.get("range_nm", 50) / 5))),
                        "track_id":     getattr(t, "track_id", 0),
                    })
                return result
        except Exception as exc:
            logger.debug(f"[HoloRadar] Fusion unavailable, using sample data: {exc}")
            self._fusion = None
        return self._generate_sample_tracked_objects()

    def _draw_threat_predictions(self, painter: QPainter, center: QPointF, radius: float):
        """Draw predicted threat movements"""
        # Get tracked objects
        tracked_objects = self._get_tracked_objects()

        for obj in tracked_objects:
            # Only predict for enemy objects
            if obj.get("type") != "enemy":
                continue

            # Get object properties
            position = obj.get("position", (0, 0))
            velocity = obj.get("velocity", (0, 0))
            threat_level = obj.get("threat_level", 0)

            # Only predict for high threat objects
            if threat_level < 7:
                continue

            # Convert position to screen coordinates
            screen_pos = self.world_to_screen(position, center, radius, self.range_scale)

            # Calculate prediction points
            prediction_points = []

            # Add current position
            prediction_points.append(screen_pos)

            # Add future positions (30 second prediction in 5 second increments)
            for t in range(1, 7):
                # Calculate future position
                future_x = position[0] + velocity[0] * t * 5
                future_y = position[1] + velocity[1] * t * 5

                # Convert to screen coordinates
                future_screen_pos = self.world_to_screen((future_x, future_y), center, radius, self.range_scale)

                # Add to prediction points
                prediction_points.append(future_screen_pos)

            # Create path for prediction
            path = QPainterPath()
            path.moveTo(prediction_points[0])

            for i in range(1, len(prediction_points)):
                path.lineTo(prediction_points[i])

            # Draw prediction path with decreasing opacity
            prediction_color = QColor(self._enhanced_theme_manager.get_color("enemy"))
            prediction_color.setAlpha(int(prediction_color.alpha() * 0.5))

            # Use dashed line for prediction
            pen = QPen(prediction_color)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawPath(path)

            # Draw prediction points
            for i, point in enumerate(prediction_points[1:], 1):
                # Decreasing size and opacity for future points
                opacity = 1.0 - (i / len(prediction_points))
                size = 5 * opacity

                point_color = QColor(prediction_color)
                point_color.setAlpha(int(prediction_color.alpha() * opacity))

                point_rect = QRectF(
                    point.x() - size / 2,
                    point.y() - size / 2,
                    size,
                    size
                )

                painter.setBrush(QBrush(point_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(point_rect)

    def _draw_holographic_frame(self, painter: QPainter, rect: QRectF):
        """Draw holographic frame around display"""
        # Create frame rect
        frame_rect = rect.adjusted(5, 5, -5, -5)

        # Draw angular frame with glow
        self._visual_effects.draw_angular_frame(
            painter,
            frame_rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True
        )

        # Draw holographic elements in corners
        self._draw_corner_elements(painter, rect)

        # Draw navigation button
        self._draw_navigation_button(painter, rect)

    def _draw_corner_elements(self, painter: QPainter, rect: QRectF):
        """Draw holographic elements in corners of display"""
        # Calculate corner positions with increased margins to prevent overlap
        corner_size = 40
        margin = 30  # Increased from 25 to 30 for even more separation

        # Top-left corner
        tl_rect = QRectF(
            rect.x() + margin,
            rect.y() + margin,
            corner_size,
            corner_size
        )

        # Top-right corner
        tr_rect = QRectF(
            rect.right() - corner_size - margin,
            rect.y() + margin,
            corner_size,
            corner_size
        )

        # Bottom-left corner
        bl_rect = QRectF(
            rect.x() + margin,
            rect.bottom() - corner_size - margin,
            corner_size,
            corner_size
        )

        # Bottom-right corner
        br_rect = QRectF(
            rect.right() - corner_size - margin,
            rect.bottom() - corner_size - margin,
            corner_size,
            corner_size
        )

        # Save painter state
        painter.save()

        # Use proper composition mode for corner elements
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Draw corner elements
        self._draw_corner_element(painter, tl_rect, "TL")
        self._draw_corner_element(painter, tr_rect, "TR")
        self._draw_corner_element(painter, bl_rect, "BL")
        self._draw_corner_element(painter, br_rect, "BR")

        # Restore painter state
        painter.restore()

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
                # Draw environmental conditions
                self._draw_environmental_indicator(painter, rect)
            elif corner == "BR":
                # Draw tactical status
                self._draw_tactical_status(painter, rect)

        finally:
            # Restore state
            painter.restore()

    def _draw_system_status(self, painter: QPainter, rect: QRectF):
        """Draw system status indicator"""
        # Draw background
        background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
        painter.fillRect(rect, background_color)

        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._enhanced_theme_manager.get_color("hud"),
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
            glow_color=self._enhanced_theme_manager.get_color("system_normal")
        )

    def _draw_data_refresh_indicator(self, painter: QPainter, rect: QRectF):
        """Draw data refresh indicator"""
        # Draw background
        background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
        painter.fillRect(rect, background_color)

        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._enhanced_theme_manager.get_color("hud"),
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

        painter.fillRect(progress_fill_rect, self._enhanced_theme_manager.get_color("data_primary"))

        # Draw refresh text
        text_rect = rect.adjusted(5, 5, -5, -15)

        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            "DATA",
            glow=True,
            glow_color=self._enhanced_theme_manager.get_color("data_primary")
        )

    def _draw_environmental_indicator(self, painter: QPainter, rect: QRectF):
        """Draw environmental conditions indicator"""
        # Draw background
        background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
        painter.fillRect(rect, background_color)

        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )

        # Draw visibility text
        text_rect = rect.adjusted(5, 5, -5, -5)

        self._visual_effects.draw_enhanced_text(
            painter,
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            self.visibility_conditions,
            glow=True,
            glow_color=self._enhanced_theme_manager.get_color("data_secondary")
        )

    def _draw_tactical_status(self, painter: QPainter, rect: QRectF):
        """Draw tactical status indicator"""
        # Draw background
        background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
        painter.fillRect(rect, background_color)

        # Draw frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            corner_style="angular",
            glow=False
        )

        # Draw tactical status
        status_rect = rect.adjusted(5, 5, -5, -5)

        # Count threats
        threat_count = 0
        for obj in self._get_tracked_objects():
            if obj.get("type") == "enemy" and obj.get("threat_level", 0) > 5:
                threat_count += 1

        # Draw threat count
        self._visual_effects.draw_enhanced_text(
            painter,
            status_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"THR {threat_count}",
            glow=threat_count > 0,
            glow_color=self._enhanced_theme_manager.get_color("enemy") if threat_count > 0 else self._enhanced_theme_manager.get_color("hud")
        )

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

        # Check if options button was clicked
        if hasattr(self, 'options_button_rect') and self.options_button_rect.contains(pos):
            # Show settings panel with enhanced visibility
            logger.info("Options button clicked, showing settings panel")

            # Position the panel in the center of the display for better visibility
            # Calculate panel position to ensure it's centered and fully visible
            panel_width = self._settings_panel.width
            panel_height = self._settings_panel.height

            # Center horizontally
            panel_x = max(10, min(self.width() - panel_width - 10, self.width() / 2 - panel_width / 2))

            # Center vertically, but ensure it's not too close to the top or bottom
            panel_y = max(10, min(self.height() - panel_height - 10, self.height() / 2 - panel_height / 2))

            # Show the panel at the calculated position
            self._settings_panel.show((panel_x, panel_y))

            logger.info(f"Showing settings panel at ({panel_x}, {panel_y}) with size {panel_width}x{panel_height}")

            # Force immediate update to show the panel
            self.update()
            return

        # Check if navigation button was clicked
        if hasattr(self, 'navigation_button_rect'):
            # Create navigation button rect if not already defined
            if not hasattr(self, 'navigation_button_rect'):
                self.navigation_button_rect = QRectF(
                    self.width() - 100,  # Position to left of settings button
                    10,                  # Align with top
                    40,
                    40
                )

            # Check if navigation button was clicked
            if self.navigation_button_rect.contains(pos):
                logger.info("Navigation button clicked, returning to main display")

                # Emit signal to return to main display if available
                if hasattr(self, 'display_changed') and callable(getattr(self, 'display_changed', None)):
                    logger.info("Emitting display_changed signal")
                    self.display_changed.emit("main")
                else:
                    logger.warning("No display_changed signal available")

                    # Fallback: Try to notify parent directly
                    if hasattr(self, 'parent') and self.parent() is not None:
                        if hasattr(self.parent(), 'switch_to_main_display') and callable(getattr(self.parent(), 'switch_to_main_display', None)):
                            logger.info("Calling parent's switch_to_main_display method")
                            self.parent().switch_to_main_display()
                        else:
                            logger.warning("Parent does not have switch_to_main_display method")

                return

        # Call parent handler for other clicks
        super().mousePressEvent(event)

    def _draw_tracked_objects(self, painter: QPainter, center: QPointF, radius: float, data: Dict):
        """Draw tracked objects on radar with target filtering"""
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

        # Apply target filtering if set
        if hasattr(self, 'target_filter'):
            if self.target_filter == "hostile":
                # Show only enemy objects
                tracked_objects = [obj for obj in tracked_objects if obj.get("type") == "enemy"]
            elif self.target_filter == "friendly":
                # Show only friendly objects
                tracked_objects = [obj for obj in tracked_objects if obj.get("type") == "friendly"]
            elif self.target_filter == "none":
                # Don't show any threats
                tracked_objects = [obj for obj in tracked_objects if obj.get("type") != "enemy"]

        # Threat prioritization — highest threat_level renders last (topmost z-order)
        if getattr(self, "use_threat_prioritization", False):
            tracked_objects = sorted(
                tracked_objects,
                key=lambda o: o.get("threat_level", 0)
            )  # ascending: highest threat drawn on top

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
                    color = self._enhanced_theme_manager.get_color("friendly")
                elif obj_type == "enemy":
                    color = self._enhanced_theme_manager.get_color("enemy")
                else:
                    color = self._enhanced_theme_manager.get_color("neutral")

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
                # Only draw if show_threat_rings is not explicitly set to False
                if threat_level > 7 and obj_type == "enemy" and getattr(self, 'show_threat_rings', True):
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

    def _draw_navigation_button(self, painter: QPainter, rect: QRectF):
        """Draw navigation button to return to other displays"""
        # Create button rect - move to top-right corner for better visibility
        button_size = 40  # Increase from 30 to 40 for better visibility
        self.navigation_button_rect = QRectF(
            rect.right() - button_size - 60,  # Position to left of settings button
            rect.top() + 10,                  # Align with top
            button_size,
            button_size
        )

        # Draw button background
        background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
        painter.fillRect(self.navigation_button_rect, background_color)

        # Draw button frame with more prominent glow
        self._visual_effects.draw_angular_frame(
            painter,
            self.navigation_button_rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True
        )

        # Draw back arrow icon with larger size
        arrow_color = self._enhanced_theme_manager.get_color("hud")
        painter.setPen(QPen(arrow_color, 3.0))  # Increase line width from 2.0 to 3.0

        # Calculate arrow points
        center_x = self.navigation_button_rect.center().x()
        center_y = self.navigation_button_rect.center().y()
        arrow_size = button_size * 0.5  # Increase from 0.4 to 0.5

        # Draw arrow
        arrow_path = QPainterPath()
        arrow_path.moveTo(center_x + arrow_size/2, center_y - arrow_size/2)  # Top right
        arrow_path.lineTo(center_x - arrow_size/2, center_y)                 # Middle left
        arrow_path.lineTo(center_x + arrow_size/2, center_y + arrow_size/2)  # Bottom right

        # Draw arrow with glow
        self._visual_effects.draw_enhanced_path(
            painter,
            arrow_path,
            color=arrow_color,
            fill=False,
            glow=True
        )

        # Add "BACK" label below the navigation button for clarity
        label_rect = QRectF(
            self.navigation_button_rect.x() - 10,  # Extend beyond button for text
            self.navigation_button_rect.bottom() + 2,
            self.navigation_button_rect.width() + 20,  # Wider for text
            15
        )

        self._visual_effects.draw_enhanced_text(
            painter,
            label_rect,
            Qt.AlignmentFlag.AlignCenter,
            "BACK",
            glow=True,
            glow_color=self._enhanced_theme_manager.get_color("hud")
        )
