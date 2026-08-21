"""
Weather radar display implementation with node-based state management.
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QPainterPath, QPen, QFont, QRadialGradient
# Import rendering components using the function-based approach to avoid circular imports
from Interfaces.userInterface.displays.radar.rendering import get_animation_controller
from Interfaces.userInterface.displays.radar.rendering import get_spatial_grid, get_dirty_region_tracker
from typing import Dict, Any, Union
import math
import time
import uuid
import copy
import random
import traceback
from .base_radar_display import BaseRadarDisplay
from Systems.radarManagement.radar_enums import weather_radarMode
from Utils.logger.sys_logger import get_logger
from core.event_driven_communication import get_event_bus, Event
from .radar_display_data_coordinator import get_radar_display_data_coordinator
from ..log_throttler import get_log_throttler

logger = get_logger()

class WeatherRadarDisplay(BaseRadarDisplay):
    """Weather radar display with node-based state management"""

    def __init__(self):
        super().__init__()
        # Get global display tree manager and event bus
        from ..display_nodes.display_tree_manager import get_display_tree_manager
        self.tree = get_display_tree_manager()
        self.event_bus = get_event_bus()
        self._subscribers_setup = False

        # Get the data coordinator for persistent data storage
        self._data_coordinator = get_radar_display_data_coordinator()

        # Get log throttler to manage logging frequency
        self._log_throttler = get_log_throttler()

        # Initialize state with mode tracking
        self._current_mode = weather_radarMode.STANDBY
        self._previous_mode = None
        self._mode_transition_time = None

        # VIL data statistics for logging
        self._vil_data_stats = {
            'received_count': 0,
            'stored_count': 0,
            'drawn_count': 0,
            'last_stats_reset': 0,
            'stats_interval': 60.0  # Reset stats every 2 minutes (extended from 60s)
        }

        # Logging throttle intervals
        self._log_throttle_interval = 30.0      # Standard throttle interval (30 seconds)
        self._high_frequency_interval = 60.0    # For very frequent operations (1 minute)
        self._display_log_throttle_interval = 60.0  # For display-related logs (1 minute)

        # Message counters for aggregated statistics
        self._message_counts = {
            'precipitation': 0,
            'vil': 0,
            'cells': 0,
            'display_updates': 0
        }

        # Get the VisualSettingsManager for weather_radar
        from ..utils.visual_settings_manager import get_visual_settings_manager
        self._settings_manager = get_visual_settings_manager("weather_radar")

        # Initialize visual elements from the settings manager
        self._visual_elements = self._settings_manager.get_settings()

        # Initialize legend generator
        from .legend_generator import get_legend_generator
        self._legend_generator = get_legend_generator()

        # Initialize data storage
        self._precipitation_data = []
        self._vil_data = []
        self._cell_data = []

        # Add persistence timers for VIL data
        self._vil_persist_time = 2.5  # Reduced TTL - only keep VIL data visible for 2.5 seconds
        self._vil_data_timestamp = {}  # Track when each VIL point was received
        self._vil_data_backup = []     # Backup storage for VIL data

        # Initialize logging throttle variables to prevent errors
        self._last_logged_mode_name = ""
        self._last_logged_mode = None
        self._last_drawing_mode_time = time.time()
        self._last_mode_log_time = time.time()
        self._last_scan_line_log_time = time.time()
        self._last_surveillance_log_time = time.time()
        self._last_surveillance_overlay_log_time = time.time()
        self._last_terrain_scale_log_time = time.time()
        self._last_mapping_log_time = time.time()
        self._last_standby_log_time = time.time()
        self._last_precip_log_time = time.time()
        self._last_cell_log_time = time.time()
        self._last_complete_log_time = time.time()
        self._last_vil_drawing_check_log_time = time.time()
        self._last_vil_drawing_enabled_log_time = time.time()

        # Add a timer to periodically call cleanup_expired
        # This ensures data points are removed after their TTL expires
        # even when there are no display updates or new data
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        # Set timer interval to 5000 milliseconds (5 seconds)
        # This matches the TTL in the data coordinator (5.0 seconds)
        self._cleanup_timer.start(5000)  # Run cleanup every 5 seconds

        # Add an expire_after flag for precipitation data
        self._precipitation_expire_after = True  # Set to True to enable expiration

        # Add stats logging timer
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._log_stats)
        self._stats_timer.start(60000)  # Log stats every minute

        # Initialize advanced animation controller
        self._animation_controller = get_animation_controller()

        # Initialize spatial partitioning
        self._spatial_grid = get_spatial_grid()
        self._dirty_region_tracker = get_dirty_region_tracker()

        # Initialize particle system
        self._particles = {
            'precipitation': {},  # Dict of precipitation_id -> list of particles
            'vil': {},           # Dict of vil_id -> list of particles
            'cells': {}          # Dict of cell_id -> list of particles
        }
        self._last_particle_update = time.time()

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
            None: QColor(128, 128, 128, 128)  # Gray
        }
        self._vil_colors = {
            'HIGH': QColor(255, 0, 0, 128),       # Red for high VIL
            'MEDIUM': QColor(255, 165, 0, 128),   # Orange for medium VIL
            'LOW': QColor(255, 255, 0, 128),      # Yellow for low VIL
            'MINIMAL': QColor(0, 255, 0, 128)     # Green for minimal VIL
        }
        self._cell_size = 10  # pixels
        self._precip_size = 15  # pixels
        self._vil_size = 12  # pixels
        self.range_scale = 40  # nautical miles

        logger.info("[WEATHER_DISPLAY] Initialized with node tree and log throttling")

    def cleanup(self):
        """Stop this display's own QTimers.

        `_cleanup_timer` and `_stats_timer` are both unparented QTimer()
        instances started immediately in __init__ and never otherwise
        stopped anywhere in this file -- this class had no cleanup()
        method at all before this fix, so RadarDisplayFactory's
        `if hasattr(cached_display, 'cleanup'):` check silently skipped
        it entirely when evicting a cached standard (non-holographic)
        weather radar display on a display-type switch, relying solely
        on the factory's subsequent gc.collect() call to indirectly
        reclaim the widget+timer reference cycle. Does not touch
        `_animation_controller` (a shared singleton via get_animation_controller(),
        not owned exclusively by this instance) or `_spatial_grid`/
        `_dirty_region_tracker` (same shared-singleton pattern) -- only
        the two QTimers this instance actually owns and starts itself.
        """
        try:
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer:
                self._cleanup_timer.stop()
            if hasattr(self, '_stats_timer') and self._stats_timer:
                self._stats_timer.stop()
            logger.info("[WEATHER_DISPLAY] Stopped cleanup and stats timers")
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error stopping timers during cleanup: {str(e)}")

    def _log_stats(self):
        """Periodically log statistics about data processing and display operations."""
        try:
            # Check if we have any meaningful data to log
            if any(count > 0 for count in self._message_counts.values()):
                # Format the message stats
                message_stats = ", ".join([f"{k}: {v}" for k, v in self._message_counts.items() if v > 0])
                logger.info(f"[WEATHER_DISPLAY] STATS - Last minute: {message_stats}")

                # Get throttler stats
                throttler_stats = self._log_throttler.get_stats()
                if throttler_stats:
                    throttle_msg = ", ".join([f"{k}: {v}" for k, v in throttler_stats.items() if v > 0])
                    logger.info(f"[WEATHER_DISPLAY] THROTTLED - Events: {throttle_msg}")

                # Reset counters for next period
                self._message_counts = {k: 0 for k in self._message_counts}
                self._log_throttler.reset_all_stats()
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error logging stats: {str(e)}")

    async def initialize_display(self):
        """Initialize display and set up subscribers."""
        try:
            # Initialize tree if needed
            if not self.tree._initialized:
                await self.tree.initialize()

            # Ensure weather_radar node exists
            weather = self.tree.root.get_child("weather_radar")
            if not weather:
                # Create weather_radar node if it doesn't exist
                from ..display_nodes.display_node_base import DisplayNode
                weather = DisplayNode("weather_radar", parent=self.tree.root)
                self.tree.root.add_child(weather)
                logger.warning("[WEATHER_DISPLAY] Created missing weather_radar node")

            # Ensure required child nodes exist
            required_nodes = ["mode", "visual", "data"]
            for node_name in required_nodes:
                if not weather.get_child(node_name):
                    from ..display_nodes.display_node_base import DisplayNode
                    node = DisplayNode(node_name, parent=weather)
                    weather.add_child(node)
                    logger.warning(f"[WEATHER_DISPLAY] Created missing {node_name} node")

            # Ensure data child nodes exist
            data_node = weather.get_child("data")
            if data_node:
                for data_type in ["precipitation", "vil", "cells"]:
                    if not data_node.get_child(data_type):
                        from ..display_nodes.display_node_base import DisplayNode
                        node = DisplayNode(data_type, parent=data_node)
                        data_node.add_child(node)
                        logger.warning(f"[WEATHER_DISPLAY] Created missing data.{data_type} node")

            # Setup subscribers if not already done
            if not self._subscribers_setup:
                await self._setup_node_subscribers()
                self._subscribers_setup = True
                logger.debug("[WEATHER_DISPLAY] Subscribers setup complete")

            # Set initial visual elements for STANDBY mode
            weather = self.tree.root.get_child("weather_radar")
            if weather:
                visual_node = weather.get_child("visual")
                if visual_node:
                    visual_data = {
                        'overlay': 'standby',
                        'show_status': True,
                        'show_legend': False,  # Disable in standby
                        'show_values': False,  # Disable in standby
                        'opacity': 1.0,
                        'show_vil': False,     # Disable VIL in standby
                        'show_vil_legend': False,
                        'show_vil_values': False
                    }
                    await visual_node.update(visual_data)
                    logger.info("[WEATHER_DISPLAY] Set initial visual elements")
                else:
                    logger.error("[WEATHER_DISPLAY] Visual node not found during initialization")
            else:
                logger.error("[WEATHER_DISPLAY] Weather radar node not found during initialization")

            # Verify node structure and subscriptions
            await self._verify_node_structure()

            logger.info("[WEATHER_DISPLAY] Display initialization complete")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error initializing display: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _verify_node_structure(self):
        """Verify node structure and subscriptions."""
        try:
            logger.debug("[WEATHER_DISPLAY] Verifying node structure and subscriptions")

            # Get weather radar node
            weather = self.tree.root.get_child("weather_radar")
            if not weather:
                logger.error("[WEATHER_DISPLAY] Weather radar node not found during verification")
                return

            # Verify data node and its children
            data_node = weather.get_child("data")
            if not data_node:
                logger.error("[WEATHER_DISPLAY] Data node not found during verification")
                return

            # Verify data node children and their subscribers
            for data_type in ["precipitation", "vil", "cells"]:
                node = data_node.get_child(data_type)
                if not node:
                    logger.error(f"[WEATHER_DISPLAY] {data_type} node not found during verification")
                    continue

                # Check if this instance is subscribed
                is_subscribed = False
                for subscriber in node.subscribers:
                    if hasattr(subscriber, '__self__') and subscriber.__self__ is self:
                        is_subscribed = True
                        break

                if not is_subscribed:
                    logger.error(f"[WEATHER_DISPLAY] Not subscribed to {data_type} node")
                    # Force subscription
                    node.add_subscriber(self._handle_data_update)
                    logger.debug(f"[WEATHER_DISPLAY] Forced subscription to {data_type} node")
                else:
                    logger.debug(f"[WEATHER_DISPLAY] Verified subscription to {data_type} node")

            logger.debug("[WEATHER_DISPLAY] Node structure and subscription verification complete")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error verifying node structure: {str(e)}")
            logger.error(traceback.format_exc())

    async def _setup_node_subscribers(self):
        """Set up node subscribers for state updates."""
        try:
            # Get weather radar nodes
            weather = self.tree.root.get_child("weather_radar")
            if not weather:
                logger.error("[WEATHER_DISPLAY] Weather radar node not found")
                return

            # Subscribe to mode updates
            mode_node = weather.get_child("mode")
            if mode_node:
                # Track subscriber count before and after
                mode_subscribers_before = len(mode_node.subscribers)
                mode_node.add_subscriber(self._handle_mode_update)
                mode_subscribers_after = len(mode_node.subscribers)
                logger.debug(f"[WEATHER_DISPLAY] Subscribed to mode updates: before={mode_subscribers_before}, after={mode_subscribers_after}")
            else:
                logger.error("[WEATHER_DISPLAY] Mode node not found during subscription setup")

            # Subscribe to visual updates
            visual_node = weather.get_child("visual")
            if visual_node:
                # Track subscriber count before and after
                visual_subscribers_before = len(visual_node.subscribers)
                visual_node.add_subscriber(self._handle_visual_update)
                visual_subscribers_after = len(visual_node.subscribers)
                logger.debug(f"[WEATHER_DISPLAY] Subscribed to visual updates: before={visual_subscribers_before}, after={visual_subscribers_after}")
            else:
                logger.error("[WEATHER_DISPLAY] Visual node not found during subscription setup")

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
                        logger.warning(f"[WEATHER_DISPLAY] Created missing {data_type} node")

                    # Track subscriber count before and after
                    subscribers_before = len(node.subscribers)

                    # Ensure this instance isn't already subscribed
                    # This prevents duplicate subscriptions
                    already_subscribed = False
                    for subscriber in node.subscribers:
                        if subscriber.__self__ is self and subscriber.__func__ is self._handle_data_update.__func__:
                            already_subscribed = True
                            logger.debug(f"[WEATHER_DISPLAY] Already subscribed to {data_type} updates")
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

                    logger.debug(f"[WEATHER_DISPLAY] Subscribed to {data_type} updates: before={subscribers_before}, after={subscribers_after}")

                # Log overall subscription results
                logger.debug(f"[WEATHER_DISPLAY] Data subscription results: {subscription_results}")

                # Verify subscriptions were successful
                for data_type, result in subscription_results.items():
                    if not result.get("success", False):
                        logger.error(f"[WEATHER_DISPLAY] Failed to subscribe to {data_type} updates")
                        # Try one more time with a different approach
                        node = data_node.get_child(data_type)
                        if node:
                            node.subscribers.add(self._handle_data_update)
                            logger.debug(f"[WEATHER_DISPLAY] Forced subscription to {data_type} node")
            else:
                # Create data node if it doesn't exist
                from ..display_nodes.display_node_base import DisplayNode
                data_node = DisplayNode("data", parent=weather)
                weather.add_child(data_node)
                logger.warning("[WEATHER_DISPLAY] Created missing data node")

                # Recursively call this method to set up subscribers for the newly created node
                await self._setup_node_subscribers()

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error setting up subscribers: {str(e)}")
            logger.error(traceback.format_exc())

    def update(self):
        """Request a display update from the widget system"""
        try:
            #logger.debug("[WEATHER_DISPLAY] Display update requested")    #  need to throttle this log.
            # Call QWidget's update method if we're inheriting from it
            if hasattr(super(), 'update'):
                super().update()
            # Make sure we call repaint to force a visual refresh
            if hasattr(self, 'repaint'):
                self.repaint()

            # Count display updates
            self._message_counts['display_updates'] += 1
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error in update method: {str(e)}")
            logger.error(traceback.format_exc())

    def handle_mouse_click(self, pos: QPointF) -> bool:
        """Handle mouse click events for interactive elements.

        Args:
            pos: Click position in widget coordinates

        Returns:
            True if click was handled, False otherwise
        """
        try:
            # Check if click is handled by the collapsible legend panel
            if self._legend_generator.handle_click(pos):
                # Force a repaint to show animation
                self.update()
                if hasattr(self, 'repaint'):
                    self.repaint()
                logger.info(f"[WEATHER_DISPLAY] Legend panel click handled at {pos.x()}, {pos.y()}")
                return True

            # Add other clickable elements here if needed

            return False
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error handling mouse click: {str(e)}")
            logger.error(traceback.format_exc())
            return False

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
                logger.debug(f"[WEATHER_DISPLAY] Mode update received from {node_name}: {mode_data}")

            # Use the message adapter to normalize the mode data
            from .weather_radar_display_message_adapter import get_weather_radar_display_message_adapter
            adapter = get_weather_radar_display_message_adapter()
            normalized_mode = adapter.normalize_mode_message(mode_data)

            # Log the normalized mode data (throttled)
            should_log, _ = self._log_throttler.should_log("normalized_mode", 10.0)
            if should_log:
                logger.warning(f"[WEATHER_DISPLAY] Normalized mode data: {normalized_mode}")

            # Get the current mode from the normalized data
            current_mode = normalized_mode['current_mode']
            mode_value = normalized_mode['mode_value']
            source_system = normalized_mode['source_system']
            force_update = normalized_mode.get('force_update', False)

            if not current_mode:
                logger.error("[WEATHER_DISPLAY] Mode update missing current_mode")
                return

            # Convert to enum if needed
            try:
                # If it's already an enum instance, use it directly
                if isinstance(current_mode, weather_radarMode):
                    new_mode = current_mode
                else:
                    # Try to get the enum by name
                    new_mode = getattr(weather_radarMode, current_mode)

                # Throttled mode logging
                should_log, _ = self._log_throttler.should_log("found_mode", 10.0)
                if should_log:
                    logger.info(f"[WEATHER_DISPLAY] Found mode enum: {new_mode.name}")
            except AttributeError:
                # Handle fallback with more robust error handling
                logger.error(f"[WEATHER_DISPLAY] Mode enum lookup failed for {current_mode}")
                try:
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
                        logger.error(f"[WEATHER_DISPLAY] Invalid mode: {current_mode}")
                        return
                    logger.debug(f"[WEATHER_DISPLAY] Mapped mode to enum: {new_mode.name}")
                except Exception as e:
                    logger.error(f"[WEATHER_DISPLAY] Mode mapping failed: {str(e)}")
                    return

            # Check if mode is actually changing or force_update is set
            if self._current_mode != new_mode or force_update:
                # Force mode update - important state change, always log
                logger.debug(f"[WEATHER_DISPLAY] Forcing mode update to: {new_mode.name}")
                self._previous_mode = self._current_mode
                self._current_mode = new_mode
                self._mode_transition_time = time.time()

                # Use the VisualSettingsManager to apply mode-specific settings
                # Use the async version since we're in an async method
                await self._settings_manager.apply_mode_settings_async(new_mode.name)

                # Update local visual elements from the settings manager
                self._visual_elements = self._settings_manager.get_settings()

                # Log with throttling
                should_log, _ = self._log_throttler.should_log("applied_settings", 10.0)
                if should_log:
                    logger.info(f"[WEATHER_DISPLAY] Applied {new_mode.name} settings using VisualSettingsManager")

                # Force display update
                self.update()
                if hasattr(self, 'repaint'):
                    self.repaint()

                should_log, _ = self._log_throttler.should_log("forced_update", 10.0)
                if should_log:
                    logger.info("[WEATHER_DISPLAY] Forced display update")
            else:
                # Mode already set, throttled logging
                should_log, _ = self._log_throttler.should_log("mode_unchanged", 30.0)
                if should_log:
                    logger.debug(f"[WEATHER_DISPLAY] Mode already set to {new_mode.name}, no update needed")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error handling mode update: {str(e)}")
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
                logger.info(f"[WEATHER_DISPLAY] Visual update from {node_name}")

            # Enhanced logging for visual elements
            old_show_vil = self._visual_elements.get('show_vil', False)
            new_show_vil = visual_data.get('show_vil', False)

            # Update the settings manager
            await self._settings_manager.update_settings_async(visual_data, apply_to_node=False)

            # Store visual elements locally for backward compatibility
            self._visual_elements = self._settings_manager.get_settings()

            # Log changes to show_vil flag (only if changed)
            if old_show_vil != new_show_vil:
                logger.debug(f"[WEATHER_DISPLAY] show_vil flag changed: {old_show_vil} -> {new_show_vil}")

            # Ensure VIL is always visible in SURVEILLANCE mode
            if self._current_mode == weather_radarMode.SURVEILLANCE:
                if not self._visual_elements.get('show_vil', False):
                    # Update both local copy and settings manager
                    self._visual_elements['show_vil'] = True
                    self._visual_elements['show_vil_values'] = True
                    await self._settings_manager.update_settings_async({
                        'show_vil': True,
                        'show_vil_values': True
                    }, apply_to_node=False)
                    logger.debug("[WEATHER_DISPLAY] Forced show_vil=True in SURVEILLANCE mode")

            # Log final visual state (with throttling)
            should_log, _ = self._log_throttler.should_log("final_visual", 30.0)
            if should_log:
                logger.info("[WEATHER_DISPLAY] Applied visual settings")

            # Create and publish update event
            event = Event('weather_radar_update', {})
            self.event_bus.publish(event)

            should_log, _ = self._log_throttler.should_log("published_event", 30.0)
            if should_log:
                logger.info("[WEATHER_DISPLAY] Published visual update event")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error handling visual update: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_data_update(self, node_name: str, data: Any) -> None:
        """Handle data state updates.

        Args:
            node_name: Name of updated node
            data: New data state
        """
        try:
            # Initialize data processors if they don't exist
            if not hasattr(self, '_data_processors'):
                from .data_processors import PrecipitationDataProcessor, VILDataProcessor, CellDataProcessor
                self._data_processors = {
                    'precipitation': PrecipitationDataProcessor(
                        self._data_coordinator,
                        self._settings_manager,
                        self._log_throttler
                    ),
                    'vil': VILDataProcessor(
                        self._data_coordinator,
                        self._settings_manager,
                        self._log_throttler,
                        self._vil_data_timestamp
                    ),
                    'cells': CellDataProcessor(
                        self._data_coordinator,
                        self._settings_manager,
                        self._log_throttler
                    )
                }
                logger.debug("[WEATHER_DISPLAY] Initialized data processors")

            # Check if we should log detailed entry for this update
            should_log_entry, _ = self._log_throttler.should_log(f"data_update_entry_{node_name}", 30.0)
            if should_log_entry:
                logger.info(f"[WEATHER_DISPLAY] DATA UPDATE RECEIVED: node={node_name}, data_type={type(data)}")

            # Track message counts for statistics based on node name
            if "precipitation" in node_name:
                self._message_counts['precipitation'] += 1
            elif "vil" in node_name:
                self._message_counts['vil'] += 1
            elif "cells" in node_name:
                self._message_counts['cells'] += 1

            # Process data through appropriate processor
            processed_data = None

            if "precipitation" in node_name:
                processed_data = await self._data_processors['precipitation'].process_data(data, node_name)
                if processed_data:
                    self._precipitation_data = processed_data
                    logger.debug(f"[WEATHER_DISPLAY] Processed {len(processed_data)} precipitation data points")
                else:
                    logger.warning("[WEATHER_DISPLAY] No precipitation data processed")

            elif "vil" in node_name:
                processed_data = await self._data_processors['vil'].process_data(data, node_name)
                if processed_data:
                    self._vil_data = processed_data
                    logger.debug(f"[WEATHER_DISPLAY] Processed {len(processed_data)} VIL data points")
                else:
                    logger.warning("[WEATHER_DISPLAY] No VIL data processed")

            elif "cells" in node_name:
                processed_data = await self._data_processors['cells'].process_data(data, node_name)
                if processed_data:
                    self._cell_data = processed_data
                    logger.debug(f"[WEATHER_DISPLAY] Processed {len(processed_data)} cell data points")
                else:
                    logger.warning("[WEATHER_DISPLAY] No cell data processed")

            # Store data based on type
            if "precipitation" in node_name:
                # Only log on throttled intervals for precipitation data
                should_log, count = self._log_throttler.should_log("precip_processing", self._high_frequency_interval)
                if should_log:
                    if count > 1:
                        logger.info(f"[WEATHER_DISPLAY] Processing {count} precipitation data messages")
                    else:
                        logger.info(f"[WEATHER_DISPLAY] Processing precipitation data")

                # Ensure visual elements are set to show precipitation data
                # This ensures precipitation data is always visible regardless of visual state
                await self._settings_manager.update_settings_async({
                    'show_precipitation': True,
                    'show_precipitation_legend': True,
                    'show_precipitation_values': True
                }, apply_to_node=False)

                # Update local copy for backward compatibility
                self._visual_elements = self._settings_manager.get_settings()

                # Store current timestamp for data persistence
                current_time = time.time()

                # ENHANCED PRECIPITATION DATA EXTRACTION - Handle all possible formats
                precip_data_found = False
                extracted_precip_data = []  # Store extracted data here first

                # Format 1: Direct list of precipitation data points
                if isinstance(data, list) and len(data) > 0:     ### FORMAT 1 IS NOT USED
                    should_log, _ = self._log_throttler.should_log("precip_format1", self._log_throttle_interval)
                    if should_log:
                        logger.info(f"[WEATHER_DISPLAY] Found list of {len(data)} precipitation data points")
                    extracted_precip_data = data
                    precip_data_found = True

                # Format 2: Data object with 'data' attribute containing precipitation list
                elif hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:       ### THIS FORMAT IS USED
                    logger.debug(f"[WEATHER_DISPLAY] Extracting {len(data.data)} precipitation points from data.data")
                    extracted_precip_data = data.data
                    precip_data_found = True

                # Handle the case where data itself is an integer/binary
                elif isinstance(data, (int, str)):
                    # Direct integer or binary string
                    raise ValueError(f"[WEATHER_DISPLAY] Received integer/binary data directly: {data}")


                # Format 3: Dictionary with additional_info.weather_data.precipitation_data
                elif isinstance(data, dict) and 'additional_info' in data:
                    logger.debug("[WEATHER_DISPLAY] Found dictionary with additional_info")
                    additional_info = data['additional_info']

                    if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                        weather_data = additional_info['weather_data']
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data in additional_info dict: {weather_data}")

                        if isinstance(weather_data, dict) and 'precipitation_data' in weather_data and isinstance(weather_data['precipitation_data'], list):
                            precip_data_list = weather_data['precipitation_data']
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(precip_data_list)} precipitation points in weather_data dict")
                            extracted_precip_data = precip_data_list
                            precip_data_found = True

                # Format 4: Object with additional_info attribute containing weather_data
                elif hasattr(data, 'additional_info') and data.additional_info is not None:
                    logger.debug("[WEATHER_DISPLAY] Found object with additional_info attribute")

                    # Handle both dictionary and object attribute access
                    if isinstance(data.additional_info, dict) and 'weather_data' in data.additional_info:
                        weather_data = data.additional_info['weather_data']
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data in additional_info: {weather_data}")

                        if isinstance(weather_data, dict) and 'precipitation_data' in weather_data and isinstance(weather_data['precipitation_data'], list):
                            precip_data_list = weather_data['precipitation_data']
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(precip_data_list)} precipitation points in weather_data")
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

                        processed_precip_data.append(precip_dict)

                    # Store the processed data using the coordinator
                    try:
                        logger.debug(f"[WEATHER_DISPLAY] Storing {len(processed_precip_data)} precipitation data points")
                        stored_count = self._data_coordinator.store_data('precipitation', processed_precip_data, request_id)
                        logger.debug(f"[WEATHER_DISPLAY] Stored {stored_count} precipitation data points")

                        # Get the data back from the coordinator
                        self._precipitation_data = self._data_coordinator.get_data('precipitation', use_backup=False)
                        logger.debug(f"[WEATHER_DISPLAY] Retrieved {len(self._precipitation_data)} precipitation data points")
                    except Exception as e:
                        logger.error(f"[WEATHER_DISPLAY] Error storing precipitation data: {str(e)}")
                        logger.error(traceback.format_exc())

                        # Fallback to direct storage
                        self._precipitation_data = processed_precip_data
                        logger.debug(f"[WEATHER_DISPLAY] Fallback: Directly stored {len(processed_precip_data)} precipitation data points")
                else:
                    # If no precipitation data found,  don't store anything
                    logger.error("[WEATHER_DISPLAY] No precipitation data found, not storing anything")
                    return
                # Store current timestamp for data persistence
                current_time = time.time()

                # ENHANCED VIL DATA EXTRACTION - Handle all possible formats
                vil_data_found = False
                extracted_vil_data = []  # Store extracted data here first

                # Format 1: Direct list of VIL data points
                if isinstance(data, list) and len(data) > 0:
                    logger.debug(f"[WEATHER_DISPLAY] Found list of {len(data)} VIL data points")

                    # Add timestamp to each data point for persistence
                    processed_data = []
                    for vil_item in data:
                        # Generate unique ID if needed
                        if not hasattr(vil_item, 'id') and not isinstance(vil_item, dict):
                            vil_item.id = f"vil_{str(uuid.uuid4())[:8]}"
                        elif isinstance(vil_item, dict) and 'id' not in vil_item:
                            vil_item['id'] = f"vil_{str(uuid.uuid4())[:8]}"

                        # Get ID for timestamp tracking
                        vil_id = vil_item.id if hasattr(vil_item, 'id') else vil_item.get('id', f"vil_{str(uuid.uuid4())[:8]}")

                        # Update timestamp for this data point
                        self._vil_data_timestamp[vil_id] = current_time
                        processed_data.append(vil_item)

                    extracted_vil_data = processed_data
                    logger.debug(f"[WEATHER_DISPLAY] VIL data sample: {extracted_vil_data[0] if extracted_vil_data else 'empty'}")
                    vil_data_found = True

                # Format 2: Data object with 'data' attribute containing VIL list
                elif hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
                    logger.debug(f"[WEATHER_DISPLAY] Extracting {len(data.data)} VIL points from data.data")
                    extracted_vil_data = data.data
                    vil_data_found = True

                # Format 3: Command type format
                elif hasattr(data, 'command_type') and isinstance(data.command_type, dict) and data.command_type.get('type') == 'vil':
                    logger.debug("[WEATHER_DISPLAY] Found command_type VIL format")

                    # Special handling for this specific format
                    if hasattr(data, 'data') and isinstance(data.data, list):
                        logger.warning(f"[WEATHER_DISPLAY] Found {len(data.data)} VIL data points in command_type format")
                        extracted_vil_data = data.data
                    else:
                        logger.warning("[WEATHER_DISPLAY] Using single data item from command_type format")
                        extracted_vil_data = [data]
                    vil_data_found = True

                # Format 4: Dictionary with additional_info.weather_data.vil_data
                # This is the format we're seeing in the logs
                elif isinstance(data, dict) and 'additional_info' in data:
                    logger.debug("[WEATHER_DISPLAY] Found dictionary with additional_info")
                    additional_info = data['additional_info']

                    if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                        weather_data = additional_info['weather_data']
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data in additional_info dict: {weather_data}")

                        if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                            vil_data_list = weather_data['vil_data']
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(vil_data_list)} VIL points in weather_data dict")
                            # Store in extracted_vil_data instead of directly in self._vil_data
                            extracted_vil_data = vil_data_list
                            vil_data_found = True

                # Format 5: Object with additional_info attribute containing weather_data
                elif hasattr(data, 'additional_info') and data.additional_info is not None:
                    logger.debug("[WEATHER_DISPLAY] Found object with additional_info attribute")

                    # Handle both dictionary and object attribute access
                    if isinstance(data.additional_info, dict) and 'weather_data' in data.additional_info:
                        weather_data = data.additional_info['weather_data']
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data in additional_info: {weather_data}")

                        if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                            vil_data_list = weather_data['vil_data']
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(vil_data_list)} VIL points in weather_data")
                            extracted_vil_data = vil_data_list
                            vil_data_found = True
                    elif hasattr(data.additional_info, 'weather_data'):
                        weather_data = data.additional_info.weather_data
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data attribute in additional_info")

                        if hasattr(weather_data, 'vil_data') and isinstance(weather_data.vil_data, list):
                            vil_data_list = weather_data.vil_data
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(vil_data_list)} VIL points in weather_data attribute")
                            extracted_vil_data = vil_data_list
                            vil_data_found = True

                # Format 6: Object with weather_data attribute
                elif hasattr(data, 'weather_data') and data.weather_data is not None:
                    logger.debug("[WEATHER_DISPLAY] Found object with weather_data attribute")

                    if hasattr(data.weather_data, 'vil_data'):
                        logger.debug("[WEATHER_DISPLAY] Found weather_data.vil_data format")
                        extracted_vil_data = data.weather_data.vil_data
                        vil_data_found = True

                # Format 7: Dictionary with metadata.weather_data.vil_data
                elif isinstance(data, dict) and 'metadata' in data:
                    logger.debug("[WEATHER_DISPLAY] Found dictionary with metadata")
                    metadata = data['metadata']

                    if isinstance(metadata, dict) and 'weather_data' in metadata:
                        weather_data = metadata['weather_data']
                        logger.debug(f"[WEATHER_DISPLAY] Found weather_data in metadata dict: {weather_data}")

                        if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                            vil_data_list = weather_data['vil_data']
                            logger.warning(f"[WEATHER_DISPLAY] Found {len(vil_data_list)} VIL points in metadata.weather_data")

                            # Process each VIL data point to ensure it's in the right format
                            processed_vil_data = []
                            for vil_item in vil_data_list:
                                # Convert to dictionary if it's an object
                                if not isinstance(vil_item, dict) and hasattr(vil_item, '__dict__'):
                                    vil_dict = vars(vil_item)
                                else:
                                    vil_dict = vil_item if isinstance(vil_item, dict) else {}

                                # Ensure position is properly formatted
                                if hasattr(vil_item, 'position'):
                                    pos = vil_item.position
                                    # Convert numpy array to tuple
                                    if hasattr(pos, 'tolist'):
                                        pos = tuple(pos.tolist())
                                    vil_dict['position'] = pos

                                # Convert numpy values to Python native types
                                for key in ['value', 'intensity', 'layer_count']:
                                    if hasattr(vil_item, key):
                                        val = getattr(vil_item, key)
                                        if hasattr(val, 'item'):  # numpy scalar
                                            vil_dict[key] = val.item()
                                        else:
                                            vil_dict[key] = val

                                # Ensure show_values is a boolean
                                if hasattr(vil_item, 'show_values'):
                                    show_val = vil_item.show_values
                                    if hasattr(show_val, 'item'):  # numpy boolean
                                        vil_dict['show_values'] = bool(show_val.item())
                                    else:
                                        vil_dict['show_values'] = bool(show_val)

                                # Add ID if missing
                                if 'id' not in vil_dict:
                                    raise ValueError("[WEATHER_DISPLAY] Missing ID in VIL data point")

                                processed_vil_data.append(vil_dict)

                            extracted_vil_data = processed_vil_data
                            vil_data_found = True
                            logger.debug(f"[WEATHER_DISPLAY] Processed {len(processed_vil_data)} VIL data points from metadata")

                # Keep previous VIL data that hasn't expired yet
                if hasattr(self, '_vil_data') and self._vil_data:
                    # Check timestamps and keep unexpired data
                    for old_vil in list(self._vil_data):
                        # Extract ID from different types
                        if isinstance(old_vil, dict):
                            old_id = old_vil.get('id', None)
                        else:
                            old_id = getattr(old_vil, 'id', None)

                        if old_id and old_id in self._vil_data_timestamp:
                            # If data is still fresh, keep it
                            if current_time - self._vil_data_timestamp[old_id] < self._vil_persist_time:
                                logger.debug(f"[WEATHER_DISPLAY] Keeping persistent VIL data point: {old_id}")
                                # Already in self._vil_data, so we don't need to add it again

                # If we found VIL data, store it using the data coordinator
                if vil_data_found and extracted_vil_data:
                    # Add detailed logging for debugging
                    logger.error(f"[WEATHER_DISPLAY] VIL DATA FOUND: {len(extracted_vil_data)} items")
                    logger.error(f"[WEATHER_DISPLAY] First VIL item type: {type(extracted_vil_data[0])}")
                    logger.error(f"[WEATHER_DISPLAY] First VIL item content: {extracted_vil_data[0]}")

                    # Extract request_id from the data if available - with multiple fallback options
                    request_id = None

                    # Try to get request_id from various possible locations
                    if isinstance(data, dict):
                        if 'request_id' in data:
                            request_id = data['request_id']
                            logger.error(f"[WEATHER_DISPLAY] Found request_id in data dict: {request_id}")
                        elif 'additional_info' in data and isinstance(data['additional_info'], dict):
                            if 'request_id' in data['additional_info']:
                                request_id = data['additional_info']['request_id']
                                logger.error(f"[WEATHER_DISPLAY] Found request_id in additional_info dict: {request_id}")
                            elif 'original_request_id' in data['additional_info']:
                                request_id = data['additional_info']['original_request_id']
                                logger.error(f"[WEATHER_DISPLAY] Found original_request_id in additional_info dict: {request_id}")

                    # Try object attributes if dict approach failed
                    if not request_id and hasattr(data, 'request_id'):
                        request_id = data.request_id
                        logger.error(f"[WEATHER_DISPLAY] Found request_id attribute: {request_id}")
                    elif not request_id and hasattr(data, 'additional_info'):
                        if hasattr(data.additional_info, 'request_id'):
                            request_id = data.additional_info.request_id
                            logger.error(f"[WEATHER_DISPLAY] Found request_id in additional_info attribute: {request_id}")
                        elif hasattr(data.additional_info, 'original_request_id'):
                            request_id = data.additional_info.original_request_id
                            logger.error(f"[WEATHER_DISPLAY] Found original_request_id in additional_info attribute: {request_id}")

                    # Check the first VIL data item if we still don't have a request_id
                    if not request_id and extracted_vil_data and len(extracted_vil_data) > 0:
                        first_item = extracted_vil_data[0]
                        if isinstance(first_item, dict) and 'request_id' in first_item:
                            request_id = first_item['request_id']
                            logger.error(f"[WEATHER_DISPLAY] Found request_id in first VIL item dict: {request_id}")
                        elif hasattr(first_item, 'request_id'):
                            request_id = first_item.request_id
                            logger.error(f"[WEATHER_DISPLAY] Found request_id attribute in first VIL item: {request_id}")

                    # we don't do backup behaviors for IDs, we MUST find the one from the previous message.
                    logger.error(f"[WEATHER_DISPLAY] Final request_id: {request_id}")

                    # Ensure VIL data is in the correct format for storage
                    # The coordinator expects a list of dictionaries with specific fields
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

                        # Convert numpy position to tuple
                        if position is not None:
                            if hasattr(position, 'tolist'):  # numpy array
                                vil_dict['position'] = tuple(position.tolist())
                            elif isinstance(position, (list, tuple)) and len(position) >= 2:
                                vil_dict['position'] = tuple(position)
                            else:
                                vil_dict['position'] = (0.0, 0.0)  # Default position
                        else:
                            vil_dict['position'] = (0.0, 0.0)  # Default position

                        # Convert numpy values to Python native types
                        for key in ['value', 'intensity', 'layer_count']:
                            if key in vil_dict and hasattr(vil_dict[key], 'item'):
                                vil_dict[key] = vil_dict[key].item()
                            elif hasattr(vil_item, key):
                                val = getattr(vil_item, key)
                                if hasattr(val, 'item'):  # numpy scalar
                                    vil_dict[key] = val.item()
                                else:
                                    vil_dict[key] = val

                        # Ensure show_values is a boolean
                        if 'show_values' in vil_dict and hasattr(vil_dict['show_values'], 'item'):
                            vil_dict['show_values'] = bool(vil_dict['show_values'].item())
                        elif hasattr(vil_item, 'show_values'):
                            show_val = vil_item.show_values
                            if hasattr(show_val, 'item'):  # numpy boolean
                                vil_dict['show_values'] = bool(show_val.item())
                            else:
                                vil_dict['show_values'] = bool(show_val)
                        else:
                            vil_dict['show_values'] = True  # Default to showing values




                        processed_vil_data.append(vil_dict)

                    # Log the processed data
                    logger.error(f"[WEATHER_DISPLAY] Processed {len(processed_vil_data)} VIL data items for storage")
                    if processed_vil_data:
                        logger.error(f"[WEATHER_DISPLAY] First processed item: {processed_vil_data[0]}")

                    # Store the processed data using the coordinator
                    try:
                        logger.error(f"[WEATHER_DISPLAY] BEFORE STORE: _vil_data has {len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0} items")
                        logger.error(f"[WEATHER_DISPLAY] Calling store_data with {len(processed_vil_data)} items and request_id: {request_id}")

                        # Use the processed data instead of raw extracted data
                        stored_count = self._data_coordinator.store_data('vil', processed_vil_data, request_id)
                        logger.error(f"[WEATHER_DISPLAY] store_data returned count: {stored_count}")

                        # Get the processed data back from the coordinator with backup option
                        logger.debug("[WEATHER_DISPLAY] Calling get_data with use_backup=True")
                        self._vil_data = self._data_coordinator.get_data('vil', use_backup=True)

                        # Check if _vil_data is properly set
                        if self._vil_data is None:
                            logger.error("[WEATHER_DISPLAY] ERROR: _vil_data is None after get_data call")
                            self._vil_data = []

                        logger.debug(f"[WEATHER_DISPLAY] AFTER get_data: _vil_data has {len(self._vil_data)} items")

                        # Update stats
                        self._vil_data_stats['stored_count'] += stored_count

                        # Also store a local backup copy
                        self._vil_data_backup = copy.deepcopy(processed_vil_data)
                        logger.error(f"[WEATHER_DISPLAY] Created backup with {len(self._vil_data_backup)} items")

                        logger.debug(f"[WEATHER_DISPLAY] Stored {stored_count} VIL data points using data coordinator")
                        logger.debug(f"[WEATHER_DISPLAY] Retrieved {len(self._vil_data)} VIL data points after storage")

                        # Log the first item for debugging
                        if self._vil_data and len(self._vil_data) > 0:
                            logger.warning(f"[WEATHER_DISPLAY] First processed VIL item: {self._vil_data[0]}")
                        else:
                            logger.error("[WEATHER_DISPLAY] ERROR: _vil_data is empty after get_data call")
                            # If get_data returns empty, use our processed data directly
                            self._vil_data = processed_vil_data
                            logger.debug(f"[WEATHER_DISPLAY] Directly assigned {len(processed_vil_data)} processed VIL items to _vil_data")
                    except Exception as e:
                        logger.error(f"[WEATHER_DISPLAY] Error storing VIL data: {str(e)}")
                        logger.error(traceback.format_exc())

                        # Fallback to direct storage if coordinator fails
                        logger.error("[WEATHER_DISPLAY] Using fallback direct storage")
                        self._vil_data = processed_vil_data  # Use processed data instead of raw data
                        self._vil_data_backup = copy.deepcopy(processed_vil_data)
                        logger.debug(f"[WEATHER_DISPLAY] Fallback: Directly stored {len(processed_vil_data)} VIL data points")
                elif hasattr(self, '_vil_data_backup') and self._vil_data_backup:
                    # If we didn't find VIL data but have backup data, restore from backup
                    import copy
                    self._vil_data = copy.deepcopy(self._vil_data_backup)
                    logger.debug(f"[WEATHER_DISPLAY] Restored {len(self._vil_data_backup)} VIL data points from backup")

                # Log the final VIL data state
                vil_count = len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0
                logger.debug(f"[WEATHER_DISPLAY] FINAL VIL DATA STATE: {vil_count} items")

                # Log stats
                logger.debug(f"[WEATHER_DISPLAY] VIL STATS: received={self._vil_data_stats['received_count']}, stored={self._vil_data_stats['stored_count']}, drawn={self._vil_data_stats['drawn_count']}")
                if hasattr(self, '_vil_data') and self._vil_data and len(self._vil_data) > 0:
                    logger.warning(f"[WEATHER_DISPLAY] First VIL item: {self._vil_data[0]}")
                    logger.warning(f"[WEATHER_DISPLAY] VIL data with persistence enabled ({self._vil_persist_time} seconds)")
                else:
                    # Instead of raising an error, try to extract VIL data directly from the message
                    logger.warning("[WEATHER_DISPLAY] No VIL data available after processing - attempting direct extraction")

                    # Try to extract VIL data directly from the message
                    if isinstance(data, dict) and 'additional_info' in data and 'weather_data' in data['additional_info']:
                        weather_data = data['additional_info']['weather_data']
                        if 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                            import copy
                            self._vil_data = copy.deepcopy(weather_data['vil_data'])
                            self._vil_data_backup = copy.deepcopy(weather_data['vil_data'])
                            logger.warning(f"[WEATHER_DISPLAY] Directly extracted {len(self._vil_data)} VIL data points")

                    # Log the final VIL data state after direct extraction
                    logger.debug(f"[WEATHER_DISPLAY] FINAL VIL DATA STATE (after direct extraction): {len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0} items")


                logger.debug(f"[WEATHER_DISPLAY] Storing VIL data: {len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0} points")

            elif "cells" in node_name:
                logger.debug(f"[WEATHER_DISPLAY] Storing cells data")
                self._cell_data = data

            # Request display update - force repaint
            logger.debug("[WEATHER_DISPLAY] Forcing display update after data processing")
            self.update()
            if hasattr(self, 'repaint'):
                self.repaint()

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error handling data update: {str(e)}")
            logger.error(traceback.format_exc())

    def draw_radar_elements(self, painter: QPainter, rect: QRectF, data: Dict[str, Any]) -> None:
        """Draw weather radar specific elements.

        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            data: Radar data
        """
        try:
            current_time = time.time()
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3

            # Call cleanup_expired on each drawing cycle
            # This ensures data points are removed after their TTL expires
            # even if no new data is being received
            self._data_coordinator.cleanup_expired()

            self.draw_range_rings(painter, center, radius)

            # Get current mode
            mode = self._current_mode or weather_radarMode.STANDBY
            mode_name = mode.name if hasattr(mode, 'name') else 'STANDBY'

            # Throttled mode drawing log
            if (self._last_logged_mode_name != mode_name or
                current_time - self._last_drawing_mode_time >= 5.0):
                logger.debug(f"[WEATHER_DISPLAY] Drawing mode: {mode_name}")
                self._last_drawing_mode_time = current_time
                self._last_logged_mode_name = mode_name

            # Draw mode-specific elements based on visual settings
            if mode_name == 'SURVEILLANCE':
                # Draw surveillance elements
                if self._visual_elements.get('show_scan_line', False):
                    self._draw_scan_line(painter, center, radius)
                    if current_time - self._last_scan_line_log_time >= 5.0:
                        logger.info("[WEATHER_DISPLAY] Drawing scan line")
                        self._last_scan_line_log_time = current_time

                # Force show_precipitation to True in SURVEILLANCE mode
                if not self._visual_elements.get('show_precipitation', False):
                    # Update both the settings manager and local copy
                    # Use the synchronous version since we're in a synchronous method
                    self._settings_manager.update_settings({
                        'show_precipitation': True,
                        'show_precipitation_legend': True,
                        'show_precipitation_values': True
                    })

                    # Update local copy for backward compatibility
                    self._visual_elements = self._settings_manager.get_settings()
                    logger.debug("[WEATHER_DISPLAY] Forced show_precipitation=True in SURVEILLANCE mode")

                self._draw_weather_cells(painter, center, radius)
                self._draw_surveillance_overlay(painter, rect)
                if current_time - self._last_surveillance_log_time >= 5.0:
                    self._last_surveillance_log_time = current_time

            elif mode_name == 'MAPPING':
                # Draw mapping elements
                if self._visual_elements.get('show_terrain_scale', False):
                    self._draw_terrain_scale(painter, rect)
                    if current_time - self._last_terrain_scale_log_time >= 5.0:
                        logger.info("[WEATHER_DISPLAY] Drawing terrain elevation scale")
                        self._last_terrain_scale_log_time = current_time

                self._draw_mapping_overlay(painter, rect)
                if current_time - self._last_mapping_log_time >= 5.0:
                    logger.info("[WEATHER_DISPLAY] Drawing mapping overlay")
                    self._last_mapping_log_time = current_time

            else:  # STANDBY
                # Draw standby elements
                if self._visual_elements.get('show_status', False):
                    self._draw_standby_overlay(painter, rect)

            # Wind shear overlay — active in WINDSHEAR mode
            if mode_name == 'WINDSHEAR':
                self._draw_windshear_overlay(painter, center, radius)

            # Turbulence overlay — active in TURBULENCE mode
            if mode_name == 'TURBULENCE':
                self._draw_turbulence_overlay(painter, center, radius)

            # Draw mode indicator
            self._draw_mode_indicator(painter, rect)

            # Debug logging for VIL drawing - throttled to reduce log spam
            current_time = time.time()
            if not hasattr(self, '_last_vil_drawing_check_log_time'):
                self._last_vil_drawing_check_log_time = 0

            # Always count the VIL data points, even when logging is throttled
            vil_data_count = len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0
            show_vil = self._visual_elements.get('show_vil', False)
            mode_name = self._current_mode.name if hasattr(self._current_mode, 'name') else None

            # Update VIL stats if needed
            if current_time - self._vil_data_stats['last_stats_reset'] > self._vil_data_stats['stats_interval']:
                logger.debug(f"[WEATHER_DISPLAY] VIL STATS RESET - Previous interval: received={self._vil_data_stats['received_count']}, stored={self._vil_data_stats['stored_count']}, drawn={self._vil_data_stats['drawn_count']}")
                self._vil_data_stats['received_count'] = 0
                self._vil_data_stats['stored_count'] = 0
                self._vil_data_stats['drawn_count'] = 0
                self._vil_data_stats['last_stats_reset'] = current_time

            # Track if we have VIL data but it's not being shown
            if vil_data_count > 0 and not show_vil:
                logger.warning(f"[WEATHER_DISPLAY]{vil_data_count} VIL data points but show_vil is False in {mode_name} mode")
                # Force show_vil to True if we have data and are in SURVEILLANCE mode
                if self._current_mode == weather_radarMode.SURVEILLANCE:
                    # Update both the settings manager and local copy
                    # Use the synchronous version since we're in a synchronous method
                    self._settings_manager.update_settings({
                        'show_vil': True,
                        'show_vil_legend': True,
                        'show_vil_values': True
                    })

                    # Update local copy for backward compatibility
                    self._visual_elements = self._settings_manager.get_settings()
                    show_vil = True
                    logger.debug("[WEATHER_DISPLAY] Forced show_vil=True in SURVEILLANCE mode")

            # Log the VIL drawing check (throttled)
            if current_time - self._last_vil_drawing_check_log_time >= 2.0:
                logger.warning(f"[WEATHER_DISPLAY] VIL drawing check: show_vil={show_vil}, vil_data_count={vil_data_count}, mode={mode_name}")
                self._last_vil_drawing_check_log_time = current_time

            # VIL data is now handled by the legend manager
            # Just update stats for logging purposes
            if self._visual_elements.get('show_vil', False):
                # Increment received count for stats
                self._vil_data_stats['received_count'] += 1

                # Log VIL data stats (throttled)
                if not hasattr(self, '_last_vil_drawing_enabled_log_time'):
                    self._last_vil_drawing_enabled_log_time = 0

                if current_time - self._last_vil_drawing_enabled_log_time >= 5.0:
                    logger.warning(f"[WEATHER_DISPLAY] VIL data available: {len(self._vil_data)} points")
                    self._last_vil_drawing_enabled_log_time = current_time

            # Draw precipitation data if available
            if self._precipitation_data:
                for precip in self._precipitation_data:
                    self._draw_precipitation(painter, center, radius, precip)
                    if current_time - self._last_precip_log_time >= 5.0:
                        # Handle string type precip data properly in log message
                        if isinstance(precip, dict):
                            pos = precip.get('position', (0,0))
                            logger.info(f"[WEATHER_DISPLAY] Drawing precipitation at {pos}")
                        else:
                            logger.info(f"[WEATHER_DISPLAY] Drawing precipitation (non-dictionary data)")
                        self._last_precip_log_time = current_time

            # Draw cell data if available
            if self._cell_data:
                for cell in self._cell_data:
                    self._draw_storm_cell(painter, center, radius, cell)
                    if current_time - self._last_cell_log_time >= 5.0:
                        logger.info(f"[WEATHER_DISPLAY] Drawing weather cell")
                        self._last_cell_log_time = current_time

            # Log completion
            if current_time - self._last_complete_log_time >= 5.0:
                logger.info("[WEATHER_DISPLAY] Completed drawing radar elements")
                self._last_complete_log_time = current_time

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing radar elements: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _draw_surveillance_overlay(self, painter: QPainter, rect: QRectF) -> None:
        """Draw surveillance mode specific overlay elements."""
        try:
            current_time = time.time()
            if current_time - self._last_surveillance_overlay_log_time >= self._display_log_throttle_interval:
                logger.info("[WEATHER_DISPLAY] Drawing surveillance overlay")
                self._last_surveillance_overlay_log_time = current_time

            # Draw legends using enhanced legend manager with collapsible panel
            if self._visual_elements.get('show_legend'):
                # Use the enhanced draw_all_legends method with the collapsible panel
                # Pass the actual display dimensions to ensure correct positioning
                self._legend_generator.draw_all_legends(painter, rect)

                # Log the legend rendering with dimensions (throttled)
                current_time = time.time()
                if not hasattr(self, '_last_legend_dimensions_log_time'):
                    self._last_legend_dimensions_log_time = 0

                if current_time - self._last_legend_dimensions_log_time >= 5.0:
                    logger.warning(f"[WEATHER_DISPLAY] Drawing legends with dimensions: ({rect.width():.1f}, {rect.height():.1f})")
                    self._last_legend_dimensions_log_time = current_time

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing surveillance overlay: {str(e)}")
            raise

    def _draw_mapping_overlay(self, painter: QPainter, rect: QRectF) -> None:
        """Draw mapping mode specific overlay elements."""
        try:
            # Draw terrain elevation scale
            scale_width = 20
            scale_height = rect.height() * 0.8
            scale_rect = QRectF(
                rect.right() - scale_width - 10,
                rect.top() + (rect.height() - scale_height)/2,
                scale_width,
                scale_height
            )

            # Draw elevation gradient
            gradient = QLinearGradient(
                scale_rect.topLeft(),
                scale_rect.bottomLeft()
            )
            gradient.setColorAt(0.0, QColor(139, 69, 19))  # Brown
            gradient.setColorAt(0.5, QColor(34, 139, 34))  # Green
            gradient.setColorAt(1.0, QColor(0, 191, 255))  # Blue

            painter.fillRect(scale_rect, gradient)
            painter.setPen(self.hud_color)
            painter.drawRect(scale_rect)

            # Draw scale labels
            painter.drawText(
                QRectF(scale_rect.left() - 40, scale_rect.top() - 20, 40, 20),
                Qt.AlignmentFlag.AlignRight,
                "High"
            )
            painter.drawText(
                QRectF(scale_rect.left() - 40, scale_rect.bottom(), 40, 20),
                Qt.AlignmentFlag.AlignRight,
                "Low"
            )

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing mapping overlay: {str(e)}")
            raise

    def _draw_standby_overlay(self, painter: QPainter, rect: QRectF) -> None:
        """Draw standby mode specific overlay elements."""
        try:
            current_time = time.time()
            painter.setPen(self.warning_color)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "WEATHER RADAR STANDBY"
            )

            # Throttled logging
            if current_time - self._last_standby_log_time >= 5.0:
                logger.info("[WEATHER_DISPLAY] Drawing standby overlay")
                self._last_standby_log_time = current_time

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing standby overlay: {str(e)}")
            raise

    def _draw_scan_line(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Draw rotating scan line."""
        try:
            # Calculate scan line angle based on time
            angle = (time.time() * 60) % 360  # Complete rotation every 6 seconds

            # Draw scan line
            painter.setPen(self.hud_color)
            painter.drawLine(
                center,
                QPointF(
                    center.x() + radius * math.cos(math.radians(angle)),
                    center.y() + radius * math.sin(math.radians(angle))
                )
            )
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing scan line: {str(e)}")
            raise

    def _draw_intensity_scale(self, painter: QPainter, rect: QRectF) -> None:
        """Draw weather intensity scale."""
        try:
            # Draw scale on right side
            scale_width = 20
            scale_height = rect.height() * 0.6
            scale_rect = QRectF(
                rect.right() - scale_width - 10,
                rect.center().y() - scale_height/2,
                scale_width,
                scale_height
            )

            # Create gradient
            gradient = QLinearGradient(
                scale_rect.topLeft(),
                scale_rect.bottomLeft()
            )
            gradient.setColorAt(0.0, self._intensity_colors['SEVERE'])
            gradient.setColorAt(0.3, self._intensity_colors['MODERATE'])
            gradient.setColorAt(0.6, self._intensity_colors['LIGHT'])
            gradient.setColorAt(1.0, self._intensity_colors['VERY_LIGHT'])

            # Draw scale
            painter.fillRect(scale_rect, gradient)
            painter.setPen(self.hud_color)
            painter.drawRect(scale_rect)

            # Draw labels
            label_width = 60
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.top() - 20, label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Severe"
            )
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.center().y() - 10, label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Moderate"
            )
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.bottom(), label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Light"
            )
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing intensity scale: {str(e)}")
            raise

    def _draw_terrain_scale(self, painter: QPainter, rect: QRectF) -> None:
        """Draw terrain elevation scale."""
        try:
            # Draw scale on right side
            scale_width = 20
            scale_height = rect.height() * 0.6
            scale_rect = QRectF(
                rect.right() - scale_width - 10,
                rect.center().y() - scale_height/2,
                scale_width,
                scale_height
            )

            # Create gradient
            gradient = QLinearGradient(
                scale_rect.topLeft(),
                scale_rect.bottomLeft()
            )
            gradient.setColorAt(0.0, QColor(139, 69, 19))   # Brown (mountains)
            gradient.setColorAt(0.3, QColor(34, 139, 34))   # Green (hills)
            gradient.setColorAt(0.6, QColor(124, 252, 0))   # Light green (plains)
            gradient.setColorAt(1.0, QColor(0, 191, 255))   # Blue (sea level)

            # Draw scale
            painter.fillRect(scale_rect, gradient)
            painter.setPen(self.hud_color)
            painter.drawRect(scale_rect)

            # Draw labels
            label_width = 80
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.top() - 20, label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Mountains"
            )
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.center().y() - 10, label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Hills"
            )
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.bottom(), label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Sea Level"
            )
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing terrain scale: {str(e)}")
            raise

    def _draw_mode_indicator(self, painter: QPainter, rect: QRectF) -> None:
        """Draw current mode indicator."""
        try:
            # Get current mode text
            mode_text = self._current_mode.name if hasattr(self._current_mode, 'name') else None

            # Set color based on mode
            if self._current_mode == weather_radarMode.STANDBY:
                painter.setPen(self.warning_color)
            else:
                painter.setPen(self.hud_color)

            # Draw mode text
            mode_rect = QRectF(rect.left(), rect.top(), rect.width(), 30)
            painter.drawText(
                mode_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                f"Mode: {mode_text}"
            )

            # Draw transition indicator if in transition
            if self._mode_transition_time and time.time() - self._mode_transition_time < 2.0:
                if self._previous_mode:
                    transition_rect = QRectF(rect.left(), rect.top() + 30, rect.width(), 20)
                    painter.drawText(
                        transition_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        f"Transitioning from {self._previous_mode.name}"
                    )

            current_time = time.time()
            # Check if mode has changed or enough time has passed since last log
            if (self._last_logged_mode != self._current_mode or
                current_time - self._last_mode_log_time >= 5.0):
                logger.debug(f"[WEATHER_DISPLAY] Drawing mode indicator: {mode_text}")
                self._last_mode_log_time = current_time
                self._last_logged_mode = self._current_mode

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing mode indicator: {str(e)}")
            raise

    def _draw_vil_legend(self, painter: QPainter, rect: QRectF, scale_rect: QRectF) -> None:
        """Draw VIL legend using the enhanced legend generator."""
        try:
            # Use the non-async version to avoid await issues
            # Pass the specific legend type to ensure we get the VIL legend
            self._legend_generator.draw_legend(painter, rect, "vil")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing VIL legend: {str(e)}")
            raise

    def _draw_weather_cells(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Draw weather cells, precipitation and VIL data."""
        try:
            # Get fresh data for each type from the coordinator
            cells = self._data_coordinator.get_data('cells', use_backup=True)
            # Don't use backup for precipitation data to allow it to expire properly
            precip = self._data_coordinator.get_data('precipitation', use_backup=False)
            # Don't use backup for VIL data to allow it to expire properly
            vil = self._data_coordinator.get_data('vil', use_backup=False)

            # Update local references for backward compatibility
            self._cell_data = cells
            self._precipitation_data = precip
            self._vil_data = vil

            # Count data items for logging
            cell_count = len(cells)
            precip_count = len(precip)
            vil_count = len(vil)

            # Update the legend generator with current data status
            # This ensures the legend will show based on what's currently visible
            self._legend_generator.update_data_status('cells', cell_count)
            self._legend_generator.update_data_status('precipitation', precip_count)
            self._legend_generator.update_data_status('vil', vil_count)

            # Initialize counters if needed
            if not hasattr(self, '_weather_cells_counters'):
                self._weather_cells_counters = {
                    'render_count': 0,
                    'cell_total': 0,
                    'precip_total': 0,
                    'vil_total': 0
                }

            # Accumulate counts for aggregated reporting
            self._weather_cells_counters['render_count'] += 1
            self._weather_cells_counters['cell_total'] += cell_count
            self._weather_cells_counters['precip_total'] += precip_count
            self._weather_cells_counters['vil_total'] += vil_count

            # Periodically log aggregated stats
            current_time = time.time()
            if not hasattr(self, '_last_weather_cells_log_time'):
                self._last_weather_cells_log_time = 0

            # Always log on first execution and then throttle
            if self._last_weather_cells_log_time == 0 or current_time - self._last_weather_cells_log_time >= 5.0:
                if self._weather_cells_counters['render_count'] > 1:
                    # Report aggregated data
                    avg_cell = self._weather_cells_counters['cell_total'] / self._weather_cells_counters['render_count']
                    avg_precip = self._weather_cells_counters['precip_total'] / self._weather_cells_counters['render_count']
                    avg_vil = self._weather_cells_counters['vil_total'] / self._weather_cells_counters['render_count']

                    logger.info(f"[WEATHER_DISPLAY] Weather cell stats (last {self._weather_cells_counters['render_count']} renders): " +
                                f"cells={cell_count} now, avg={avg_cell:.1f}, " +
                                f"precip={precip_count} now, avg={avg_precip:.1f}, " +
                                f"vil={vil_count} now, avg={avg_vil:.1f}")
                else:
                    # Direct report on first execution
                    logger.info(f"[WEATHER_DISPLAY] Drawing weather cells: cells={cell_count}, precip={precip_count}, vil={vil_count}")

                # Log VIL data details if available
                if vil_count > 0:
                    first_vil = vil[0]
                    logger.info(f"[WEATHER_DISPLAY] First VIL item type: {type(first_vil).__name__}, content: {first_vil}")

                # Reset counters after logging
                self._weather_cells_counters = {
                    'render_count': 0,
                    'cell_total': 0,
                    'precip_total': 0,
                    'vil_total': 0
                }
                self._last_weather_cells_log_time = current_time

            # Draw storm cells
            for cell in cells:
                self._draw_storm_cell(painter, center, radius, cell)

            # Draw precipitation
            for precip_item in precip:
                self._draw_precipitation(painter, center, radius, precip_item)

            # Draw VIL data and accumulate stats
            drawn_vil_count = 0
            for vil_item in vil:
                self._draw_vil(painter, center, radius, vil_item)
                drawn_vil_count += 1

            # Accumulate stats for this frame
            self._vil_data_stats['drawn_count'] += drawn_vil_count

            # Initialize accumulated counts if they don't exist
            if not hasattr(self, '_accumulated_drawn_vil_count'):
                self._accumulated_drawn_vil_count = 0
                self._accumulated_total_vil_count = 0
                self._accumulated_frames = 0

            # Accumulate counts until logging
            self._accumulated_drawn_vil_count += drawn_vil_count
            self._accumulated_total_vil_count = vil_count  # Use the most recent count
            self._accumulated_frames += 1

            # Log VIL drawing stats and reset accumulation when throttle interval is reached
            if current_time - self._last_vil_drawing_enabled_log_time >= 5.0:
                avg_drawn = self._accumulated_drawn_vil_count / max(1, self._accumulated_frames)
                logger.warning(f"[WEATHER_DISPLAY] VIL drawing stats: drawn={self._accumulated_drawn_vil_count} (avg {avg_drawn:.1f}/frame over {self._accumulated_frames} frames), total={self._accumulated_total_vil_count}")

                # Reset accumulated counts
                self._accumulated_drawn_vil_count = 0
                self._accumulated_total_vil_count = 0
                self._accumulated_frames = 0
                self._last_vil_drawing_enabled_log_time = current_time

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing weather cells: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _draw_storm_cell(self, painter: QPainter, center: QPointF, radius: float, cell: Dict) -> None:
        """Draw individual storm cell using particle system for realistic appearance."""
        try:
            # Get cell position — supports both 'position':(x,y) tuple (bridge/push format)
            # and legacy flat 'x'/'y' keys
            if 'position' in cell:
                pos = cell['position']
                x = float(pos[0]) if pos else 0.0
                y = float(pos[1]) if pos and len(pos) > 1 else 0.0
            else:
                x = float(cell.get('x', 0))
                y = float(cell.get('y', 0))

            # Convert from nautical miles to screen coordinates
            screen_x = center.x() + (x / self.range_scale) * radius
            screen_y = center.y() - (y / self.range_scale) * radius

            intensity = cell.get('intensity', 0)
            rotation = cell.get('rotation', 0.0)  # Rotation speed in radians/sec

            # Set cell color based on intensity
            color = self._get_intensity_color(intensity)

            # Get or create unique ID — bridge uses 'cell_id', legacy uses 'id'
            cell_id = cell.get('cell_id', cell.get('id', f"cell_{str(uuid.uuid4())[:8]}"))

            # Calculate particle radius based on intensity
            particle_radius = 15 + intensity * 15

            # Check if we need to generate new particles for this cell
            if (cell_id not in self._particles.get('cells', {}) or
                len(self._particles.get('cells', {}).get(cell_id, [])) == 0):
                # Generate particles for this cell with spiral motion
                self._generate_cell_particles(
                    screen_x,
                    screen_y,
                    intensity,
                    color,
                    cell_id,
                    particle_radius,
                    rotation
                )

                # Log particle generation (throttled)
                should_log, _ = self._log_throttler.should_log("cell_particle_gen", 30.0)
                if should_log:
                    particle_count = len(self._particles.get('cells', {}).get(cell_id, []))
                    logger.info(f"[WEATHER_DISPLAY] Generated {particle_count} particles for storm cell at ({x},{y})")

            # Draw particles for this cell
            self._draw_particles(painter, 'cells')

            # Draw intensity value if enabled
            if cell.get('show_values', False):
                # Text background
                text_rect = QRectF(
                    screen_x - particle_radius/2,
                    screen_y + particle_radius/2,
                    particle_radius,
                    particle_radius/2
                )

                # Draw text background
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))  # Black semi-transparent
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(text_rect)

                # Draw text with high contrast
                painter.setPen(QColor(255, 255, 0))  # Bright yellow
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

                # Format the intensity string with proper decimal places
                intensity_str = f"{intensity:.1f}"

                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    intensity_str
                )

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing storm cell: {str(e)}")
            raise

    def _draw_windshear_overlay(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Draw wind-shear events pulled from the 'windshear' coordinator store.

        Severity colour coding:
            LOW      → yellow
            MODERATE → orange
            SEVERE   → red
        Microburst events get a bold ring + 'MB' label.
        """
        try:
            from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
                get_radar_display_data_coordinator,
            )
            coordinator = get_radar_display_data_coordinator()
            events = coordinator.get_data("windshear", use_backup=True)
            if not events:
                return

            SEVERITY_COLORS = {
                "LOW":      QColor(255, 255,   0, 180),
                "MODERATE": QColor(255, 165,   0, 200),
                "SEVERE":   QColor(255,  50,  50, 220),
            }

            for ev in events:
                pos = ev.get("position", (0.0, 0.0))
                if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                    continue
                # Convert nm offsets to display pixels
                scale = radius / 100.0  # assume 100 nm display range
                px = center.x() + float(pos[0]) * scale
                py = center.y() - float(pos[1]) * scale

                severity = str(ev.get("severity", "LOW")).upper()
                color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["LOW"])
                is_mb = bool(ev.get("is_microburst", False))
                shear_kts = float(ev.get("shear_knots", 0.0))

                # Outer ring — larger for microburst
                ring_r = 14 if is_mb else 9
                pen = QPen(color, 2 if is_mb else 1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(px, py), ring_r, ring_r)

                # Fill dot
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(px, py), 3, 3)

                # Label
                painter.setPen(QPen(color, 1))
                font = painter.font()
                font.setPointSize(7)
                font.setBold(is_mb)
                painter.setFont(font)
                label = f"MB\n{shear_kts:.0f}kt" if is_mb else f"{shear_kts:.0f}kt"
                painter.drawText(
                    int(px + ring_r + 2), int(py - 6),
                    60, 24,
                    int(Qt.AlignmentFlag.AlignLeft),
                    label,
                )

        except Exception as exc:
            logger.debug(f"[WEATHER_DISPLAY] _draw_windshear_overlay error: {exc}", exc_info=True)

    def _draw_turbulence_overlay(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Draw turbulence cells pulled from the 'turbulence' coordinator store.

        Category colour coding (FAA AC 120-88A):
            LIGHT    → light green
            MODERATE → yellow
            SEVERE   → orange
            EXTREME  → red
        Cell size scales with intensity (EDR proxy).
        """
        try:
            from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
                get_radar_display_data_coordinator,
            )
            coordinator = get_radar_display_data_coordinator()
            cells = coordinator.get_data("turbulence", use_backup=True)
            if not cells:
                return

            CATEGORY_COLORS = {
                "LIGHT":    QColor(100, 220, 100, 160),
                "MODERATE": QColor(255, 230,   0, 180),
                "SEVERE":   QColor(255, 140,   0, 200),
                "EXTREME":  QColor(255,  40,  40, 220),
            }

            for cell in cells:
                pos = cell.get("position", (0.0, 0.0))
                if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                    continue
                scale = radius / 100.0
                px = center.x() + float(pos[0]) * scale
                py = center.y() - float(pos[1]) * scale

                category = str(cell.get("category", "LIGHT")).upper()
                color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["LIGHT"])
                intensity = max(0.0, min(1.0, float(cell.get("intensity", 0.3))))
                cell_r = 6 + intensity * 12   # 6–18 px radius

                # Filled cell blob
                fill = QColor(color)
                fill.setAlpha(max(60, int(intensity * 180)))
                painter.setBrush(fill)
                painter.setPen(QPen(color, 1))
                painter.drawEllipse(QPointF(px, py), cell_r, cell_r)

                # Category label
                painter.setPen(QPen(color, 1))
                font = painter.font()
                font.setPointSize(7)
                font.setBold(category in ("SEVERE", "EXTREME"))
                painter.setFont(font)
                painter.drawText(
                    int(px + cell_r + 2), int(py - 6),
                    60, 20,
                    int(Qt.AlignmentFlag.AlignLeft),
                    category[:3],
                )

        except Exception as exc:
            logger.debug(f"[WEATHER_DISPLAY] _draw_turbulence_overlay error: {exc}", exc_info=True)

    def _draw_precipitation(self, painter: QPainter, center: QPointF, radius: float, precip: Dict) -> None:
        """Draw individual precipitation area using particle system for realistic appearance."""
        try:
            # Get the current time to calculate fade effect
            current_time = time.time()

            # Strict validation of precipitation data
            if precip is None:
                logger.error("[WEATHER_DISPLAY] CRITICAL: Received None precipitation data")
                return  # Reject invalid data

            # Log format for diagnostics
            logger.warning(f"[WEATHER_DISPLAY] Processing precipitation data type: {type(precip)}")

            # Extract precipitation data fields from the dictionary
            # This is the expected path for properly formatted data
            if not isinstance(precip, dict):
                logger.error(f"[WEATHER_DISPLAY] CRITICAL: Non-dictionary precipitation data: {type(precip)}")
                return  # Reject invalid data format

            # Verify required keys - log and return if missing critical data
            logger.warning(f"[WEATHER_DISPLAY] Dictionary keys: {precip.keys()}")
            if 'position' not in precip:
                logger.error("[WEATHER_DISPLAY] CRITICAL: Missing required 'position' field")
                return  # Reject data without position

            # Extract position with strong validation
            position = precip.get('position')

            # Check if position is None before proceeding
            if position is None:
                logger.error("[WEATHER_DISPLAY] CRITICAL: Position is None - preventing crash")
                return  # Skip drawing this precipitation data

            # Validate position format
            if not isinstance(position, (tuple, list)) or len(position) < 2:
                logger.error(f"[WEATHER_DISPLAY] CRITICAL: Invalid position format: {position}")
                return  # Reject invalid position data

            # Extract position coordinates safely
            try:
                x, y = position[0], position[1]
            except Exception as e:
                logger.error(f"[WEATHER_DISPLAY] CRITICAL: Error unpacking position {position}: {str(e)}")
                return  # Skip drawing this precipitation data
            logger.warning(f"[WEATHER_DISPLAY] Position coordinates: ({x}, {y})")

            # Extract remaining fields with proper validation
            precip_type = precip.get('type', precip.get('precip_type', 'unknown'))
            if precip_type == 'unknown':
                logger.warning("[WEATHER_DISPLAY] Warning: Precipitation type not specified")

            # Extract numeric values with validation
            try:
                intensity = float(precip.get('intensity', 0.7))
                rate = float(precip.get('rate', 20.0))
            except (TypeError, ValueError) as e:
                logger.error(f"[WEATHER_DISPLAY] CRITICAL: Invalid numeric values: {e}")
                return  # Reject invalid data

            # Extract display options
            show_values = bool(precip.get('show_values', True))

            # Convert from nautical miles to screen coordinates
            screen_x = center.x() + (x / self.range_scale) * radius
            screen_y = center.y() - (y / self.range_scale) * radius

            # Apply appropriate visualization
            base_color = self._precipitation_colors.get(precip_type, self._precipitation_colors[None])
            color = QColor(base_color)

            # Apply fade effect if ID and timestamp are available
            alpha_multiplier = 1.0
            if self._precipitation_expire_after and 'id' in precip and isinstance(precip['id'], str):
                item_id = precip['id']
                if item_id in self._data_coordinator._timestamps:
                    item_age = current_time - self._data_coordinator._timestamps[item_id]
                    ttl = self._data_coordinator._data_store['precipitation']['ttl']
                    # Start fading at 60% of TTL
                    fade_start = ttl * 0.6
                    if item_age > fade_start:
                        # Calculate fade factor
                        remaining_time = ttl - item_age
                        alpha_multiplier = max(0.0, min(1.0, remaining_time / (ttl - fade_start)))
                        logger.debug(f"[WEATHER_DISPLAY] Precipitation fading: age={item_age:.1f}s, multiplier={alpha_multiplier:.2f}")

            # Set final color with appropriate opacity
            color.setAlpha(int(255 * max(0.3, min(0.75, intensity)) * alpha_multiplier))

            # Ensure particle system is initialized
            if not hasattr(self, '_particles'):
                self._initialize_particle_system()

            # Get or create unique ID for this precipitation data point
            precip_id = precip.get('id', f"precip_{str(uuid.uuid4())[:8]}")

            # Calculate particle radius based on intensity and rate
            particle_radius = 25 + intensity * 15 + min(rate / 5, 10)

            # Check if we need to generate new particles for this precipitation point
            if (precip_id not in self._particles.get('precipitation', {}) or
                len(self._particles.get('precipitation', {}).get(precip_id, [])) == 0):
                # Generate particles for this precipitation point
                self._generate_particles(
                    screen_x,
                    screen_y,
                    intensity,
                    color,
                    'precipitation',
                    precip_id,
                    particle_radius
                )

                # Log particle generation (throttled)
                should_log, _ = self._log_throttler.should_log("precip_particle_gen", 30.0)
                if should_log:
                    particle_count = len(self._particles.get('precipitation', {}).get(precip_id, []))
                    logger.info(f"[WEATHER_DISPLAY] Generated {particle_count} particles for precipitation at ({x},{y})")

            # Draw particles for this precipitation point
            self._draw_particles(painter, 'precipitation')

            # Draw rate value if enabled
            if show_values:
                # Text background
                text_rect = QRectF(
                    screen_x - particle_radius/2,
                    screen_y + particle_radius/2,
                    particle_radius,
                    particle_radius/2
                )

                # Draw text background
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))  # Black semi-transparent
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(text_rect)

                # Draw text with high contrast
                painter.setPen(QColor(255, 255, 0))  # Bright yellow
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

                # Format the rate string with proper decimal places
                rate_str = f"{rate:.1f}mm/h"
                # Ensure we never display just ".0" (force decimal point display)
                if rate_str.endswith(".0mm/h"):
                    rate_str = f"{rate:g}mm/h"  # Use general format for whole numbers

                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    rate_str
                )

            # Log successful drawing (throttled)
            should_log, count = self._log_throttler.should_log("precip_drawing_success", self._high_frequency_interval)
            if should_log:
                logger.info(f"[WEATHER_DISPLAY] Precipitation at ({x},{y}) drawn successfully with particle system")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] CRITICAL: Error drawing precipitation: {str(e)}")
            logger.error(traceback.format_exc())
            # Log the exception but continue with other elements

    def _initialize_particle_system(self):
        """Initialize the particle system for radar visualization."""
        try:
            # Initialize particle storage if it doesn't exist
            if not hasattr(self, '_particles'):
                self._particles = {
                    'precipitation': {},  # Dict of precipitation_id -> list of particles
                    'vil': {}            # Dict of vil_id -> list of particles
                }

            # Use animation controller instead of direct timer
            # The animation controller will emit signals that we'll handle

            # Initialize last update time
            if not hasattr(self, '_last_particle_update'):
                self._last_particle_update = time.time()

            # Wind vector is now managed by the animation controller

            logger.info("[WEATHER_DISPLAY] Enhanced particle system initialized with animation controller")

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error initializing particle system: {str(e)}")
            logger.error(traceback.format_exc())

    def _handle_animation_update(self, animation_state):
        """
        Handle animation state updates from the animation controller.

        Args:
            animation_state: Dictionary with animation state
        """
        try:
            # Extract animation parameters
            wind_vector = animation_state.get('wind_vector', (0, 0))
            turbulence = animation_state.get('turbulence', 0.0)
            dt = animation_state.get('dt', 0.016)  # Default to 16ms
            phase_name = animation_state.get('phase_name', '')
            phase_progress = animation_state.get('phase_progress', 0.0)
            transition_progress = animation_state.get('transition_progress', 0.0)

            # Log animation state (throttled)
            should_log, _ = self._log_throttler.should_log("animation_update", 5.0)
            if should_log:
                logger.info(f"[WEATHER_DISPLAY] Animation update: phase={phase_name}, progress={phase_progress:.2f}")

            # Update particles based on animation state
            self._update_particles_with_animation(wind_vector, turbulence, dt, phase_name, phase_progress)

            # Request a display update
            self.update()

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error handling animation update: {str(e)}")
            logger.error(traceback.format_exc())

    def _update_particles_with_animation(self, wind_vector, turbulence, dt, phase_name, phase_progress):
        """
        Update particle positions based on animation state.

        Args:
            wind_vector: Tuple of (dx, dy) wind displacement
            turbulence: Turbulence factor
            dt: Time delta in seconds
            phase_name: Current animation phase name
            phase_progress: Progress through current phase (0.0-1.0)
        """
        try:
            # Extract wind displacement
            dx, dy = wind_vector

            # weather pattern movement
            precip_speed_factor = 0.20  # 20% of original speed

            # Update precipitation particles
            for precip_id, particles in list(self._particles['precipitation'].items()):
                for particle in particles:
                    # Update position based on wind - apply speed reduction factor
                    particle['x'] += dx * dt * precip_speed_factor
                    particle['y'] += dy * dt * precip_speed_factor

                    # Add turbulence if enabled - also reduce by factor to match movement
                    if turbulence > 0:
                        particle['x'] += random.uniform(-turbulence, turbulence) * precip_speed_factor
                        particle['y'] += random.uniform(-turbulence, turbulence) * precip_speed_factor

                    # Update lifetime - extend to match slower movement
                    # Make sure they stay visible longer since they move more slowly
                    particle['lifetime'] -= dt * 0.7  # Slightly slower lifetime reduction

                    # Apply phase-specific effects
                    if phase_name == 'intensify':
                        # Increase opacity during intensify phase
                        particle['opacity'] = min(1.0, particle['opacity'] * (1.0 + 0.1 * dt))
                    elif phase_name == 'dissipate':
                        # Decrease opacity during dissipate phase
                        particle['opacity'] = max(0.1, particle['opacity'] * (1.0 - 0.2 * dt))

                    # Mark particle region as dirty if using dirty regions
                    if self._use_dirty_regions:
                        size = particle['size']
                        self._dirty_region_tracker.mark_point_dirty(
                            particle['x'], particle['y'], size/2 + 5  # Add margin for motion
                        )

                    # Update spatial grid if using spatial partitioning
                    if self._use_spatial_partitioning:
                        # Was f"precip_{precip_id}_{id(particle)}" -- every other
                        # particle type (vil_, cells_) and _draw_particles()'s own
                        # visibility filter use the full data_type ("precipitation"
                        # here) as the id prefix, so this abbreviated "precip_"
                        # prefix never matched and every precipitation particle
                        # was silently invisible to spatial-grid queries. Was
                        # latent (query_visible() was never called from a working
                        # code path) until the _draw_particles() duplicate-method
                        # fix restored real culling (production readiness
                        # reanalysis).
                        particle_id = f"precipitation_{precip_id}_{id(particle)}"
                        self._spatial_grid.update(particle_id, particle)

                # Remove expired particles
                self._particles['precipitation'][precip_id] = [
                    p for p in particles if p['lifetime'] > 0
                ]

                # Remove empty particle lists
                if not self._particles['precipitation'][precip_id]:
                    del self._particles['precipitation'][precip_id]

            # Update VIL particles - align with precipitation movement
            for vil_id, particles in list(self._particles['vil'].items()):
                for particle in particles:
                    # Update position based on wind - match precipitation speed
                    particle['x'] += dx * dt * precip_speed_factor
                    particle['y'] += dy * dt * precip_speed_factor

                    # Add turbulence if enabled - also reduce by factor to match movement
                    if turbulence > 0:
                        particle['x'] += random.uniform(-turbulence, turbulence) * precip_speed_factor
                        particle['y'] += random.uniform(-turbulence, turbulence) * precip_speed_factor

                    # Update lifetime - extend to match slower movement
                    particle['lifetime'] -= dt * 2  # faster lifetime reduction

                    # Apply phase-specific effects
                    if phase_name == 'intensify':
                        # Increase opacity during intensify phase
                        particle['opacity'] = min(1.0, particle['opacity'] * (1.0 + 0.1 * dt))
                    elif phase_name == 'dissipate':
                        # Decrease opacity during dissipate phase
                        particle['opacity'] = max(0.1, particle['opacity'] * (1.0 - 0.2 * dt))

                    # Mark particle region as dirty if using dirty regions
                    if self._use_dirty_regions:
                        size = particle['size']
                        self._dirty_region_tracker.mark_point_dirty(
                            particle['x'], particle['y'], size/2 + 5  # Add margin for motion
                        )

                    # Update spatial grid if using spatial partitioning
                    if self._use_spatial_partitioning:
                        particle_id = f"vil_{vil_id}_{id(particle)}"
                        self._spatial_grid.update(particle_id, particle)

                # Remove expired particles
                self._particles['vil'][vil_id] = [
                    p for p in particles if p['lifetime'] > 0
                ]

                # Remove empty particle lists
                if not self._particles['vil'][vil_id]:
                    del self._particles['vil'][vil_id]

            # Update cell particles
            if 'cells' in self._particles:
                for cell_id, particles in list(self._particles['cells'].items()):
                    for particle in particles:
                        # Get spiral motion parameters
                        spiral_radius = particle.get('spiral_radius', 0.0)
                        spiral_speed = particle.get('spiral_speed', 0.0)
                        spiral_phase = particle.get('spiral_phase', 0.0)

                        # Update spiral phase
                        particle['spiral_phase'] = spiral_phase + spiral_speed * dt

                        # Calculate spiral motion offset
                        spiral_x = spiral_radius * math.cos(particle['spiral_phase'])
                        spiral_y = spiral_radius * math.sin(particle['spiral_phase'])

                        # Apply base velocity and spiral motion
                        particle['x'] += particle['velocity'][0] * dt + spiral_x * dt
                        particle['y'] += particle['velocity'][1] * dt + spiral_y * dt

                        # Add turbulence if enabled
                        if turbulence > 0:
                            particle['x'] += random.uniform(-turbulence, turbulence) * 0.5
                            particle['y'] += random.uniform(-turbulence, turbulence) * 0.5

                        # Update lifetime
                        particle['lifetime'] -= dt

                        # Apply phase-specific effects
                        if phase_name == 'intensify':
                            # Increase opacity during intensify phase
                            particle['opacity'] = min(1.0, particle['opacity'] * (1.0 + 0.1 * dt))
                        elif phase_name == 'dissipate':
                            # Decrease opacity during dissipate phase
                            particle['opacity'] = max(0.1, particle['opacity'] * (1.0 - 0.2 * dt))

                        # Mark particle region as dirty if using dirty regions
                        if self._use_dirty_regions:
                            size = particle['size']
                            self._dirty_region_tracker.mark_point_dirty(
                                particle['x'], particle['y'], size/2 + 5  # Add margin for motion
                            )

                        # Update spatial grid if using spatial partitioning
                        if self._use_spatial_partitioning:
                            # Was f"cell_{cell_id}_{id(particle)}" (singular) --
                            # self._particles['cells'] (plural) and the insertion
                            # side (line ~2505: f"cells_{cell_id}_...") both use
                            # "cells_", and _draw_particles()'s visibility filter
                            # is keyed on data_type ("cells"), so the singular
                            # prefix here never matched. Same latent bug as the
                            # precipitation "precip_" mismatch fixed above
                            # (production readiness reanalysis).
                            particle_id = f"cells_{cell_id}_{id(particle)}"
                            self._spatial_grid.update(particle_id, particle)

                    # Remove expired particles
                    self._particles['cells'][cell_id] = [
                        p for p in particles if p['lifetime'] > 0
                    ]

                    # Remove empty particle lists
                    if not self._particles['cells'][cell_id]:
                        del self._particles['cells'][cell_id]

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error updating particles with animation: {str(e)}")
            logger.error(traceback.format_exc())

    def _generate_cell_particles(self, center_x: float, center_y: float, intensity: float,
                               color: QColor, cell_id: str, radius: float = 30.0,
                               rotation: float = 0.0):
        """
        Generate particles for a storm cell with spiral motion for realistic visualization.

        Args:
            center_x: X coordinate of center point
            center_y: Y coordinate of center point
            intensity: Intensity value (0.0-1.0) affecting particle count and opacity
            color: Base color for particles
            cell_id: Unique ID for this cell
            radius: Maximum radius for particle distribution
            rotation: Rotation speed in radians/sec (positive = counterclockwise)
        """
        try:
            # Ensure particle system is initialized
            if not hasattr(self, '_particles'):
                self._initialize_particle_system()

            # Calculate number of particles based on intensity
            # More intense cells = more particles
            base_count = 80  # Minimum number of particles
            max_count = 300  # Maximum number of particles
            particle_count = int(base_count + intensity * (max_count - base_count))

            # Apply particle count factor from animation controller
            particle_count_factor = self._animation_controller.get_parameter('particle_count_factor')
            if particle_count_factor:
                particle_count = int(particle_count * particle_count_factor)

            # Create new particle list for this cell
            particles = []

            # Set rotation direction based on hemisphere (northern = counterclockwise)
            # If rotation is provided, use that instead
            if rotation == 0.0:
                # Default rotation if not specified
                rotation_speed = 0.5 + intensity * 1.5  # Radians per second
                # Randomly determine rotation direction (70% counterclockwise for northern hemisphere)
                if random.random() < 0.7:
                    rotation_speed *= -1  # Counterclockwise
            else:
                rotation_speed = rotation

            # Create spiral effect with multiple arms
            num_arms = 2 + int(intensity * 3)  # 2-5 spiral arms based on intensity

            # Generate particles with spiral distribution
            for i in range(particle_count):
                # Choose a random spiral arm
                arm = random.randint(0, num_arms - 1)

                # Random distance from center with bias toward outer regions
                # This creates a more realistic storm cell appearance with stronger activity at the edges
                distance_bias = random.betavariate(2.0, 1.5)  # Beta distribution for edge bias
                distance = distance_bias * radius * 0.9  # Keep within 90% of radius

                # Calculate spiral phase offset for this arm
                arm_offset = arm * (2 * math.pi / num_arms)

                # Random phase offset within this arm's sector
                phase_offset = random.uniform(0, 0.8 * math.pi / num_arms)

                # Calculate initial angle with spiral pattern
                # Logarithmic spiral: r = a*e^(b*theta)
                # We work backwards to find theta from r
                spiral_tightness = 0.1 + intensity * 0.2  # Tighter spirals for higher intensity
                angle = arm_offset + phase_offset
                if distance > 0:
                    # Add spiral component to angle
                    angle += math.log(distance / (0.1 * radius)) / spiral_tightness

                # Calculate position
                px = center_x + math.cos(angle) * distance
                py = center_y + math.sin(angle) * distance

                # Calculate spiral motion parameters
                # Particles closer to center rotate faster
                spiral_radius = 0.5 + (distance / radius) * 3.0  # Larger spiral radius at edges
                spiral_speed = rotation_speed * (0.8 + 0.4 * (1.0 - distance / radius))  # Faster near center
                spiral_phase = random.uniform(0, 2 * math.pi)  # Random starting phase

                # Calculate base velocity (outward from center for growing cells)
                # This creates the effect of the storm cell expanding
                velocity_magnitude = 0.5 + intensity * 1.5  # Pixels per second
                velocity_angle = angle  # Outward direction
                vx = math.cos(velocity_angle) * velocity_magnitude
                vy = math.sin(velocity_angle) * velocity_magnitude

                # Random size (larger particles for more overlap)
                # Size varies based on distance from center and intensity
                max_size = 3.0 + intensity * 3.0  # Up to 6.0 for high intensity
                min_size = 1.5 + intensity * 1.5  # At least 1.5
                size_factor = 0.8 + 0.4 * (distance / radius)  # Larger at edges
                size = random.uniform(min_size * size_factor, max_size * size_factor)

                # Get particle lifetime from animation controller
                base_lifetime = self._animation_controller.get_parameter('particle_lifetime') or 3.0
                lifetime = random.uniform(base_lifetime * 0.5, base_lifetime * 1.5)

                # Random opacity based on intensity and distance from center
                base_opacity = 0.3 + intensity * 0.7  # Higher intensity = higher base opacity
                distance_factor = 0.7 + 0.3 * (distance / radius)  # Slightly stronger at edges
                opacity = base_opacity * distance_factor * random.uniform(0.7, 1.0)

                # Create particle with spiral motion parameters
                particle = {
                    'x': px,
                    'y': py,
                    'size': size,
                    'opacity': opacity,
                    'lifetime': lifetime,
                    'velocity': (vx, vy),  # Base velocity vector
                    'spiral_radius': spiral_radius,  # Radius of spiral motion
                    'spiral_speed': spiral_speed,  # Angular speed of spiral
                    'spiral_phase': spiral_phase,  # Current phase of spiral
                    'original_x': center_x,  # Store original position for reference
                    'original_y': center_y,
                    'arm': arm  # Store arm for potential future use
                }

                particles.append(particle)

                # Add to spatial grid if using spatial partitioning
                if self._use_spatial_partitioning:
                    particle_id = f"cells_{cell_id}_{id(particle)}"
                    self._spatial_grid.insert(particle_id, particle)

                # Mark particle region as dirty if using dirty regions
                if self._use_dirty_regions:
                    self._dirty_region_tracker.mark_point_dirty(px, py, size/2)

            # Store particles
            self._particles['cells'][cell_id] = particles

            # Add frame to animation controller's temporal buffer
            if hasattr(self._animation_controller, 'add_frame'):
                frame_data = {
                    'data_type': 'cells',
                    'data_id': cell_id,
                    'center_x': center_x,
                    'center_y': center_y,
                    'intensity': intensity,
                    'radius': radius,
                    'rotation': rotation_speed,
                    'particle_count': len(particles)
                }
                self._animation_controller.add_frame(frame_data)

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error generating cell particles: {str(e)}")
            logger.error(traceback.format_exc())

    def _generate_particles(self, center_x: float, center_y: float, intensity: float,
                           color: QColor, data_type: str, data_id: str, radius: float = 30.0):
        """
        Generate particles around a center point for realistic radar visualization.

        Args:
            center_x: X coordinate of center point
            center_y: Y coordinate of center point
            intensity: Intensity value (0.0-1.0) affecting particle count and opacity
            color: Base color for particles
            data_type: 'precipitation' or 'vil'
            data_id: Unique ID for this data point
            radius: Maximum radius for particle distribution
        """
        try:
            # Ensure particle system is initialized
            if not hasattr(self, '_particles'):
                self._initialize_particle_system()

            # Calculate number of particles based on intensity
            # More intense weather = more particles
            # Significantly increased particle counts for more realistic cloud-like appearance
            base_count = 100  # Minimum number of particles (increased from 20)
            max_count = 400  # Maximum number of particles (increased from 100)
            particle_count = int(base_count + intensity * (max_count - base_count))

            # Apply particle count factor from animation controller
            particle_count_factor = self._animation_controller.get_parameter('particle_count_factor')
            if particle_count_factor:
                particle_count = int(particle_count * particle_count_factor)

            # Create new particle list for this data point
            particles = []

            # Create a cluster effect with multiple density centers
            # This creates more realistic cloud-like formations
            num_clusters = 3 + int(intensity * 5)  # More intense = more clusters
            cluster_centers = []

            # Create main cluster at center
            cluster_centers.append((center_x, center_y, 1.0))  # (x, y, strength)

            # Create satellite clusters
            for i in range(num_clusters - 1):
                # Random angle and distance from main center
                angle = random.uniform(0, 2 * math.pi)
                # Keep clusters within 70% of the radius
                distance = random.uniform(0, 0.7) * radius

                # Calculate cluster center
                cx = center_x + math.cos(angle) * distance
                cy = center_y + math.sin(angle) * distance

                # Strength decreases with distance from main center
                strength = 0.4 + (0.6 * (1.0 - distance / radius))

                cluster_centers.append((cx, cy, strength))

            # Generate particles with positions influenced by clusters
            for _ in range(particle_count):
                # Choose a random cluster with bias toward stronger clusters
                weights = [c[2] for c in cluster_centers]
                total_weight = sum(weights)
                normalized_weights = [w / total_weight for w in weights]

                # Weighted random selection of cluster
                r = random.random()
                cumulative = 0
                selected_cluster = 0
                for i, weight in enumerate(normalized_weights):
                    cumulative += weight
                    if r <= cumulative:
                        selected_cluster = i
                        break

                cluster_x, cluster_y, cluster_strength = cluster_centers[selected_cluster]

                # Random angle and distance from cluster center
                angle = random.uniform(0, 2 * math.pi)
                # Use normal distribution for more realistic clustering
                # Standard deviation is smaller for stronger clusters
                std_dev = (1.0 - cluster_strength) * radius * 0.5
                distance = abs(random.normalvariate(0, std_dev))

                # Calculate position
                px = cluster_x + math.cos(angle) * distance
                py = cluster_y + math.sin(angle) * distance

                # Calculate distance from main center for color/opacity adjustments
                dist_from_main = math.sqrt((px - center_x)**2 + (py - center_y)**2)
                normalized_dist = min(1.0, dist_from_main / radius)

                # Random size (larger particles for more overlap)
                # Size varies based on distance from center and intensity
                max_size = 4.0 + intensity * 4.0  # Up to 8.0 for high intensity
                min_size = 2.0 + intensity * 2.0  # At least 2.0
                size_factor = 1.0 - normalized_dist * 0.7  # Larger near center
                size = random.uniform(min_size * size_factor, max_size * size_factor)

                # Get particle lifetime from animation controller
                base_lifetime = self._animation_controller.get_parameter('particle_lifetime') or 4.0
                lifetime = random.uniform(base_lifetime * 0.5, base_lifetime * 1.5)

                # Random opacity based on intensity and distance from center
                # Particles near center are more opaque
                base_opacity = 0.4 + intensity * 0.6  # Higher intensity = higher base opacity
                distance_factor = 1.0 - normalized_dist * 0.8  # Less falloff for better blending
                opacity = base_opacity * distance_factor * random.uniform(0.6, 1.0)

                # Create particle
                particle = {
                    'x': px,
                    'y': py,
                    'size': size,
                    'opacity': opacity,
                    'lifetime': lifetime,
                    'original_x': center_x,  # Store original position for reference
                    'original_y': center_y,
                    'cluster': selected_cluster  # Store cluster for potential future use
                }

                particles.append(particle)

                # Add to spatial grid if using spatial partitioning
                if self._use_spatial_partitioning:
                    particle_id = f"{data_type}_{data_id}_{id(particle)}"
                    self._spatial_grid.insert(particle_id, particle)

                # Mark particle region as dirty if using dirty regions
                if self._use_dirty_regions:
                    self._dirty_region_tracker.mark_point_dirty(px, py, size/2)

            # Store particles
            self._particles[data_type][data_id] = particles

            # Add frame to animation controller's temporal buffer
            if hasattr(self._animation_controller, 'add_frame'):
                frame_data = {
                    'data_type': data_type,
                    'data_id': data_id,
                    'center_x': center_x,
                    'center_y': center_y,
                    'intensity': intensity,
                    'radius': radius,
                    'particle_count': len(particles)
                }
                self._animation_controller.add_frame(frame_data)

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error generating particles: {str(e)}")
            logger.error(traceback.format_exc())

    def _draw_particles(self, painter: QPainter, data_type: str):
        """
        Draw all particles of a specific type with enhanced blending for realistic cloud-like appearance.

        Args:
            painter: QPainter to render with
            data_type: 'precipitation' or 'vil'
        """
        try:
            # Skip if no particles
            if not hasattr(self, '_particles') or not self._particles.get(data_type):
                return

            # Enable antialiasing for smoother particles
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Set pen to none (particles are just filled circles)
            painter.setPen(Qt.PenStyle.NoPen)

            # Get viewport rect for culling
            viewport_rect = QRectF(0, 0, self.width(), self.height())

            # First pass: Sort particles by size (larger ones first for better layering)
            all_particles = []
            for data_id, particle_list in self._particles[data_type].items():
                for particle in particle_list:
                    # Add data_id to particle for color lookup
                    particle_copy = particle.copy()
                    particle_copy['data_id'] = data_id
                    all_particles.append(particle_copy)

            # Sort particles by size (descending) for better layering
            all_particles.sort(key=lambda p: p['size'], reverse=True)

            # This class used to have two _draw_particles() definitions -- Python
            # silently kept only the later one, which drew every particle with no
            # culling at all. The earlier, shadowed definition filtered particles
            # via the spatial grid and dirty-region tracker (both real,
            # continuously-maintained infrastructure -- see the .insert()/.update()
            # calls elsewhere in this class) but never actually drew anything, so
            # it couldn't just be restored as-is either. Folded the working
            # culling logic from the dead definition into this one, ahead of the
            # actual draw loop (production readiness reanalysis, duplicate-method
            # systemic scan).

            # Use spatial partitioning if enabled
            if self._use_spatial_partitioning:
                # Query visible particles
                visible_ids = self._spatial_grid.query_visible(viewport_rect)

                # Filter particles by visibility
                visible_particles = []
                for particle in all_particles:
                    particle_id = f"{data_type}_{particle['data_id']}_{id(particle)}"
                    if particle_id in visible_ids:
                        visible_particles.append(particle)

                all_particles = visible_particles

            # Use dirty region tracking if enabled
            if self._use_dirty_regions:
                # Filter particles by dirty regions
                dirty_particles = []
                for particle in all_particles:
                    x = particle['x']
                    y = particle['y']
                    size = particle['size']

                    # Create particle rect
                    particle_rect = QRectF(
                        x - size/2,
                        y - size/2,
                        size,
                        size
                    )

                    # Check if particle intersects with dirty regions
                    if self._dirty_region_tracker.is_dirty(particle_rect):
                        dirty_particles.append(particle)

                all_particles = dirty_particles

            # Draw all particles in sorted, culled order
            for particle in all_particles:
                # Get particle properties
                x = particle['x']
                y = particle['y']
                size = particle['size']
                opacity = particle['opacity']
                data_id = particle['data_id']

                # Get base color based on data type
                if data_type == 'precipitation':
                    # Use color from the original precipitation data if available
                    if data_id in self._data_coordinator._data_store.get('precipitation', {}).get('data', {}):
                        precip_data = self._data_coordinator._data_store['precipitation']['data'][data_id]
                        precip_type = precip_data.get('type', 'rain')
                        base_color = self._precipitation_colors.get(precip_type, self._precipitation_colors[None])
                    else:
                        # Default to blue for rain if data not found
                        base_color = self._precipitation_colors['rain']
                else:  # vil
                    # Use color based on VIL level if available
                    if data_id in self._data_coordinator._data_store.get('vil', {}).get('data', {}):
                        vil_data = self._data_coordinator._data_store['vil']['data'][data_id]
                        value = vil_data.get('value', 20.0)

                        # Determine VIL level based on value
                        vil_level = 'MINIMAL'
                        if value > 30:
                            vil_level = 'HIGH'
                        elif value > 20:
                            vil_level = 'MEDIUM'
                        elif value > 10:
                            vil_level = 'LOW'

                        base_color = self._vil_colors.get(vil_level, self._vil_colors['MINIMAL'])
                    else:
                        # Default to yellow for VIL if data not found
                        base_color = self._vil_colors['LOW']

                # Create color with proper opacity
                color = QColor(base_color)
                color.setAlpha(int(255 * opacity))

                # Use radial gradient for softer edges (more cloud-like)
                gradient = QRadialGradient(x, y, size/2)
                gradient.setColorAt(0, color)  # Full color at center

                # Create transparent edge for better blending
                edge_color = QColor(color)
                edge_color.setAlpha(0)  # Fully transparent at edge
                gradient.setColorAt(1, edge_color)

                # Set brush with gradient
                painter.setBrush(QBrush(gradient))

                # Draw particle as circle with gradient
                particle_rect = QRectF(
                    x - size/2,
                    y - size/2,
                    size,
                    size
                )
                painter.drawEllipse(particle_rect)

        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error drawing particles: {str(e)}")
            logger.error(traceback.format_exc())

    def _draw_vil(self, painter: QPainter, center: QPointF, radius: float, vil: Dict) -> None:
        """Draw individual VIL data point using particle system for realistic appearance."""
        try:
            # Get VIL data - handle different formats based on the source
            # We expect vil to be a dictionary at this point due to our preprocessing
            if not isinstance(vil, dict):
                should_log, _ = self._log_throttler.should_log("vil_unexpected_type", 30.0)
                if should_log:
                    logger.warning(f"[WEATHER_DISPLAY] Unexpected VIL data type: {type(vil)}")
                # Convert to dictionary if possible
                if hasattr(vil, '__dict__'):
                    vil_dict = vars(vil)
                else:
                    # Cannot extract position from this object -- skip rather
                    # than draw fake data at origin (an earlier version of this
                    # code did that, which was misleading)
                    should_log, _ = self._log_throttler.should_log("vil_unrecognised_type", 60.0)
                    if should_log:
                        logger.warning(
                            f"[WEATHER_DISPLAY] Unrecognised VIL object type {type(vil).__name__} "
                            f"with no __dict__ — skipping"
                        )
                    return
            else:
                vil_dict = vil

            # Extract position - should be a tuple of (x, y)
            pos = vil_dict.get('position', (0.0, 0.0))

            # Ensure position is a tuple of two values
            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                should_log, count = self._log_throttler.should_log("vil_invalid_position", 30.0)
                if should_log:
                    if count > 1:
                        logger.warning(f"[WEATHER_DISPLAY] {count} invalid VIL positions detected, using default (0,0)")
                    else:
                        logger.warning(f"[WEATHER_DISPLAY] Invalid position format: {pos}, using default (0,0)")
                x, y = 0.0, 0.0
            else:
                x, y = pos[0], pos[1]

            # Extract other values with defaults
            value = vil_dict.get('value', 20.0)  # kg/m²
            layer_count = vil_dict.get('layer_count', 1)
            intensity = vil_dict.get('intensity', 0.7)
            show_values = vil_dict.get('show_values', True)

            # Get current time for animation effects
            current_time = time.time()

            # Convert from nautical miles to screen coordinates
            screen_x = center.x() + (x / self.range_scale) * radius
            screen_y = center.y() - (y / self.range_scale) * radius

            # Determine VIL level based on value
            vil_level = 'MINIMAL'
            if value > 30:
                vil_level = 'HIGH'
            elif value > 20:
                vil_level = 'MEDIUM'
            elif value > 10:
                vil_level = 'LOW'

            # Get color based on VIL level
            color = self._vil_colors.get(vil_level, self._vil_colors['MINIMAL'])

            # Adjust opacity based on intensity
            adjusted_color = QColor(color)
            adjusted_color.setAlpha(int(255 * min(1.0, max(0.3, intensity))))

            # Get or create unique ID for this VIL data point
            vil_id = vil_dict.get('id', f"vil_{str(uuid.uuid4())[:8]}")

            # Calculate particle radius based on value and intensity
            particle_radius = 20 + (value / 5) + (intensity * 10)

            # Check if we need to generate new particles for this VIL point
            if (vil_id not in self._particles.get('vil', {}) or
                len(self._particles.get('vil', {}).get(vil_id, [])) == 0):
                # Generate particles for this VIL point
                self._generate_particles(
                    screen_x,
                    screen_y,
                    intensity,
                    adjusted_color,
                    'vil',
                    vil_id,
                    particle_radius
                )

                # Log particle generation (throttled)
                should_log, _ = self._log_throttler.should_log("vil_particle_gen", 30.0)
                if should_log:
                    particle_count = len(self._particles.get('vil', {}).get(vil_id, []))
                    logger.info(f"[WEATHER_DISPLAY] Generated {particle_count} particles for VIL at ({x},{y})")

            # Draw particles for this VIL point
            self._draw_particles(painter, 'vil')

            # Draw value if enabled
            if show_values and self._visual_elements.get('show_vil_values', False):
                # Text background
                text_rect = QRectF(
                    screen_x - particle_radius/2,
                    screen_y + particle_radius/2,
                    particle_radius,
                    particle_radius/2
                )

                # Draw text background
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))  # Black semi-transparent
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(text_rect)

                # Draw text with high contrast
                painter.setPen(QColor(255, 255, 0))  # Bright yellow
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

                # Format the value string with proper decimal places
                value_str = f"{value:.1f}"

                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    value_str
                )

        except Exception as e:
            # Enhanced error logging for VIL data drawing issues
            logger.error(f"[WEATHER_DISPLAY] Error drawing VIL data: {str(e)}")
            logger.error(traceback.format_exc())

            # Log additional diagnostic information about the VIL data
            if isinstance(vil, dict):
                logger.error(f"[WEATHER_DISPLAY] VIL data that failed: position={vil.get('position', 'missing')}, "
                            f"value={vil.get('value', 'missing')}, intensity={vil.get('intensity', 'missing')}")
            else:
                logger.error(f"[WEATHER_DISPLAY] Failed VIL data type: {type(vil)}")

            # Continue with other items rather than crashing the entire display
            # This ensures that some data can still be displayed even if one point fails

    def _get_intensity_color(self, intensity: float) -> QColor:
        """Get color based on intensity value."""
        try:
            if intensity > 0.8:
                return self._intensity_colors['SEVERE']
            elif intensity > 0.6:
                return self._intensity_colors['MODERATE']
            elif intensity > 0.3:
                return self._intensity_colors['LIGHT']
            else:
                return self._intensity_colors['VERY_LIGHT']
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error getting intensity color: {str(e)}")
            return QColor(128, 128, 128, 128)  # Default gray

    def _periodic_cleanup(self):
        """
        Periodically clean up expired VIL and cell data.
        This method is called by the QTimer every 5 seconds.
        """
        try:
            # Initialize counters if needed
            if not hasattr(self, '_cleanup_stats'):
                self._cleanup_stats = {
                    'run_count': 0,
                    'vil_cleaned': 0,
                    'cells_cleaned': 0,
                    'last_log_time': 0
                }

            # Get counts before cleanup to track removed items
            vil_count_before = len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0
            cells_count_before = len(self._cell_data) if hasattr(self, '_cell_data') and self._cell_data else 0
            precipitation_count_before = len(self._precipitation_data) if hasattr(self, '_precipitation_data') and self._precipitation_data else 0

            # Current time for timestamp checking
            current_time = time.time()

            # More aggressive cleanup of all particle systems
            # This ensures particles are cleaned up properly and prevents buildup

            # First clear particle storage systems for any data that's over half its TTL
            particles_cleaned = 0

            # Clean VIL particles
            for vil_id in list(self._particles.get('vil', {}).keys()):
                if vil_id not in self._vil_data_timestamp or current_time - self._vil_data_timestamp[vil_id] > (self._vil_persist_time / 2):
                    if vil_id in self._particles.get('vil', {}):
                        particles_cleaned += len(self._particles['vil'][vil_id])
                        del self._particles['vil'][vil_id]

            # Clean precipitation particles that are older or not referenced
            for precip_id in list(self._particles.get('precipitation', {}).keys()):
                # Check if this ID exists in current precipitation data
                still_valid = False
                for precip_item in self._precipitation_data:
                    if isinstance(precip_item, dict) and precip_item.get('id') == precip_id:
                        still_valid = True
                        break

                if not still_valid:
                    if precip_id in self._particles.get('precipitation', {}):
                        particles_cleaned += len(self._particles['precipitation'][precip_id])
                        del self._particles['precipitation'][precip_id]

            # Clean cell particles
            for cell_id in list(self._particles.get('cells', {}).keys()):
                # Check if this ID exists in current cell data
                still_valid = False
                for cell_item in self._cell_data:
                    if isinstance(cell_item, dict) and cell_item.get('id') == cell_id:
                        still_valid = True
                        break

                if not still_valid:
                    if cell_id in self._particles.get('cells', {}):
                        particles_cleaned += len(self._particles['cells'][cell_id])
                        del self._particles['cells'][cell_id]

            if particles_cleaned > 0:
                logger.warning(f"[WEATHER_DISPLAY] Removed {particles_cleaned} expired particles from memory")

            # ENHANCED CLEANUP: Clean expired VIL data from local timestamp storage
            expired_vil_ids = []
            for vil_id, timestamp in list(self._vil_data_timestamp.items()):
                if current_time - timestamp > self._vil_persist_time:
                    expired_vil_ids.append(vil_id)

            # Remove expired VIL IDs from timestamp storage
            for vil_id in expired_vil_ids:
                self._vil_data_timestamp.pop(vil_id, None)

            if expired_vil_ids:
                logger.warning(f"[WEATHER_DISPLAY] Removed {len(expired_vil_ids)} expired VIL timestamps")

                # Also remove these IDs from backup storage
                if hasattr(self, '_vil_data_backup'):
                    self._vil_data_backup = [item for item in self._vil_data_backup
                                           if item.get('id') not in expired_vil_ids]
                    logger.warning(f"[WEATHER_DISPLAY] Cleaned backup VIL data: {len(self._vil_data_backup)} items remain")

            # Force a direct removal of expired timestamps from coordinator data
            # This ensures data is removed promptly after TTL expires
            self._data_coordinator.cleanup_expired()

            # Explicitly refresh data after cleanup
            # This ensures we're working with up-to-date data that doesn't include expired items
            self._vil_data = self._data_coordinator.get_data('vil', use_backup=False)
            self._cell_data = self._data_coordinator.get_data('cells', use_backup=False)
            self._precipitation_data = self._data_coordinator.get_data('precipitation', use_backup=False)

            # Get counts after cleanup
            vil_count_after = len(self._vil_data) if hasattr(self, '_vil_data') and self._vil_data else 0
            cells_count_after = len(self._cell_data) if hasattr(self, '_cell_data') and self._cell_data else 0
            precipitation_count_after = len(self._precipitation_data) if hasattr(self, '_precipitation_data') and self._precipitation_data else 0

            vil_cleaned = max(0, vil_count_before - vil_count_after)
            cells_cleaned = max(0, cells_count_before - cells_count_after)
            precipitation_cleaned = max(0, precipitation_count_before - precipitation_count_after)

            # Update stats
            self._cleanup_stats['run_count'] += 1
            self._cleanup_stats['vil_cleaned'] += vil_cleaned
            self._cleanup_stats['cells_cleaned'] += cells_cleaned

            # Log statistics periodically (every minute)
            if not hasattr(self, '_last_cleanup_stats_time'):
                self._last_cleanup_stats_time = 0

            if current_time - self._last_cleanup_stats_time >= 60.0:
                # Only log if we've actually cleaned some items
                if self._cleanup_stats['vil_cleaned'] > 0 or self._cleanup_stats['cells_cleaned'] > 0 or precipitation_cleaned > 0:
                    logger.warning(f"[WEATHER_DISPLAY] Cleanup stats: {self._cleanup_stats['run_count']} runs, " +
                                f"removed {self._cleanup_stats['vil_cleaned']} VIL items, " +
                                f"{self._cleanup_stats['cells_cleaned']} cell items, " +
                                f"{precipitation_cleaned} precipitation items")
                else:
                    # Brief summary if no items were cleaned
                    logger.info(f"[WEATHER_DISPLAY] Ran {self._cleanup_stats['run_count']} cleanups with no expired items")

                # Reset stats
                self._cleanup_stats['run_count'] = 0
                self._cleanup_stats['vil_cleaned'] = 0
                self._cleanup_stats['cells_cleaned'] = 0
                self._last_cleanup_stats_time = current_time

            # Force a display update to reflect the cleaned up data
            self.update()
            if hasattr(self, 'repaint'):
                self.repaint()
        except Exception as e:
            logger.error(f"[WEATHER_DISPLAY] Error in periodic cleanup: {str(e)}")
            logger.error(traceback.format_exc())

    @property
    def legend_manager(self):
        """Get the legend manager instance.

        Returns:
            The legend manager instance used by this display
        """
        return self._legend_generator.legend_manager
