"""
Qt widget adapter for weather radar display
"""
import time
import traceback
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import QRectF, Qt, QPointF, pyqtSignal
from .weather_radar_display import WeatherRadarDisplay
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Singleton instance with enhanced reset capability
_weather_radar_widget_instance = None
_reset_requested = False

def get_weather_radar_widget(force_reset=False):
    """Get or create the singleton instance of WeatherRadarWidget
    
    Args:
        force_reset: If True, force creation of a new instance even if one exists
    """
    global _weather_radar_widget_instance, _reset_requested
    
    # Check if reset was requested or forced
    if force_reset or _reset_requested:
        logger.warning("Reset requested for WeatherRadarWidget instance")
        
        # Clean up old instance if it exists
        if _weather_radar_widget_instance is not None:
            try:
                # Unsubscribe from the EventBus 'weather_radar_update' topic
                # before discarding this instance -- without this,
                # EventBus.subscribers['weather_radar_update'] keeps a
                # permanent reference to the old instance's callback,
                # which (a) keeps this whole widget alive forever (it can
                # never be garbage collected while EventBus, a
                # process-lifetime singleton, still references it) and
                # (b) keeps firing the old instance's callback on every
                # future 'weather_radar_update' publish alongside the new
                # instance's callback. Added (August 2026 re-analysis
                # round, Round 11, EventBus subscriber leak sweep).
                if hasattr(_weather_radar_widget_instance, 'event_bus') and \
                   hasattr(_weather_radar_widget_instance, '_weather_update_callback'):
                    unsubscribed = _weather_radar_widget_instance.event_bus.unsubscribe(
                        'weather_radar_update', _weather_radar_widget_instance._weather_update_callback
                    )
                    logger.warning(f"Unsubscribed old WeatherRadarWidget instance from EventBus: {unsubscribed}")

                # Clean up display tree subscribers
                if hasattr(_weather_radar_widget_instance, 'display') and _weather_radar_widget_instance.display:
                    display = _weather_radar_widget_instance.display
                    if hasattr(display, 'tree') and display.tree:
                        tree = display.tree
                        weather_node = tree.root.get_child("weather_radar")
                        if weather_node:
                            # Clean up subscribers on visual node
                            visual_node = weather_node.get_child("visual")
                            if visual_node and hasattr(visual_node, 'subscribers'):
                                logger.warning(f"Clearing {len(visual_node.subscribers)} subscribers from visual node")
                                visual_node.subscribers.clear()
                            
                            # Clean up subscribers on data nodes
                            data_node = weather_node.get_child("data")
                            if data_node:
                                for data_type in ["precipitation", "vil", "cells"]:
                                    type_node = data_node.get_child(data_type)
                                    if type_node and hasattr(type_node, 'subscribers'):
                                        logger.warning(f"Clearing {len(type_node.subscribers)} subscribers from {data_type} node")
                                        type_node.subscribers.clear()
                
                # Stop the widget if it's running
                if _weather_radar_widget_instance.is_running():
                    _weather_radar_widget_instance.stop()
                    logger.warning("Stopped existing WeatherRadarWidget instance")
                
                # Ensure display is properly cleaned up
                if hasattr(_weather_radar_widget_instance, 'display') and _weather_radar_widget_instance.display:
                    # Call cleanup method if it exists
                    if hasattr(_weather_radar_widget_instance.display, 'cleanup'):
                        _weather_radar_widget_instance.display.cleanup()
                        logger.warning("Cleaned up display resources")
                    
                    # Reset the display property
                    _weather_radar_widget_instance._display = None
                    logger.warning("Reset display property of WeatherRadarWidget instance")
                
                # Reset the radar display data coordinator
                try:
                    from .radar_display_data_coordinator import get_radar_display_data_coordinator
                    coordinator = get_radar_display_data_coordinator()
                    coordinator.reset_data()
                    logger.warning("Reset all data in radar display data coordinator during widget reset")
                except Exception as coord_error:
                    logger.error(f"Error resetting radar display data coordinator: {coord_error}")
                    logger.error(traceback.format_exc())
                
                # Force garbage collection to clean up references
                import gc
                gc.collect()
                
                logger.warning("Cleaned up old WeatherRadarWidget instance")
            except Exception as e:
                logger.error(f"Error cleaning up old WeatherRadarWidget instance: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Create new instance
        logger.warning("Creating new WeatherRadarWidget instance after reset")
        _weather_radar_widget_instance = WeatherRadarWidget()
        _reset_requested = False
        return _weather_radar_widget_instance
    
    # Normal singleton pattern
    if _weather_radar_widget_instance is None:
        logger.info("Creating new WeatherRadarWidget instance")
        _weather_radar_widget_instance = WeatherRadarWidget()
    
    return _weather_radar_widget_instance

def reset_weather_radar_widget(force_immediate=False):
    """
    Request a reset of the WeatherRadarWidget singleton instance
    
    Args:
        force_immediate: If True, reset immediately instead of waiting for next get call
    
    This function doesn't immediately reset the instance by default, but sets a flag
    that will cause the instance to be reset the next time get_weather_radar_widget is called.
    If force_immediate is True, it will reset immediately.
    """
    global _reset_requested, _weather_radar_widget_instance
    _reset_requested = True
    
    # Check current display type for logging
    from ..visual.theme_manager import get_theme_manager
    theme_manager = get_theme_manager()
    display_type = theme_manager.get_display_type("radar", "standard")
    logger.warning(f"Reset requested for WeatherRadarWidget instance (current display type: {display_type})")
    
    if force_immediate and _weather_radar_widget_instance is not None:
        try:
            # Clean up display tree subscribers
            if hasattr(_weather_radar_widget_instance, 'display') and _weather_radar_widget_instance.display:
                display = _weather_radar_widget_instance.display
                if hasattr(display, 'tree') and display.tree:
                    tree = display.tree
                    weather_node = tree.root.get_child("weather_radar")
                    if weather_node:
                        # Clean up subscribers on visual node
                        visual_node = weather_node.get_child("visual")
                        if visual_node and hasattr(visual_node, 'subscribers'):
                            logger.warning(f"Clearing {len(visual_node.subscribers)} subscribers from visual node")
                            visual_node.subscribers.clear()
                        
                        # Clean up subscribers on data nodes
                        data_node = weather_node.get_child("data")
                        if data_node:
                            for data_type in ["precipitation", "vil", "cells"]:
                                type_node = data_node.get_child(data_type)
                                if type_node and hasattr(type_node, 'subscribers'):
                                    logger.warning(f"Clearing {len(type_node.subscribers)} subscribers from {data_type} node")
                                    type_node.subscribers.clear()
            
            # Stop the widget if it's running
            if _weather_radar_widget_instance.is_running():
                _weather_radar_widget_instance.stop()
                logger.warning("Stopped existing WeatherRadarWidget instance")
            
            # Ensure display is properly cleaned up
            if hasattr(_weather_radar_widget_instance, 'display') and _weather_radar_widget_instance.display:
                # Call cleanup method if it exists
                if hasattr(_weather_radar_widget_instance.display, 'cleanup'):
                    _weather_radar_widget_instance.display.cleanup()
                    logger.warning("Cleaned up display resources during immediate reset")
                
                # Reset the display property
                _weather_radar_widget_instance._display = None
                logger.warning("Reset display property of WeatherRadarWidget instance")
            
            # Reset the radar display data coordinator
            try:
                from .radar_display_data_coordinator import get_radar_display_data_coordinator
                coordinator = get_radar_display_data_coordinator()
                coordinator.reset_data()
                logger.warning("Reset all data in radar display data coordinator during immediate widget reset")
            except Exception as coord_error:
                logger.error(f"Error resetting radar display data coordinator: {coord_error}")
                logger.error(traceback.format_exc())
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Set instance to None
            _weather_radar_widget_instance = None
            logger.warning("Immediately reset WeatherRadarWidget instance")
        except Exception as e:
            logger.error(f"Error during immediate reset of WeatherRadarWidget: {str(e)}")
            logger.error(traceback.format_exc())

class WeatherRadarWidget(QWidget):
    """Qt widget adapter for weather radar display"""

    # NOTE (production readiness re-analysis, August 2026): added so
    # 'weather_radar_update' events can cross from EventBus's background
    # "EventBus_Processor" thread to this widget's GUI thread safely -- see
    # the NOTE at the subscribe() call below for the full explanation.
    _update_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = False
        
        # Check theme settings for display type
        from ..visual.theme_manager import get_theme_manager
        theme_manager = get_theme_manager()
        display_type = theme_manager.get_display_type("radar", "standard")
        logger.info(f"[WEATHER_WIDGET] Creating display with type: {display_type}")
        
        # Create appropriate display based on display type
        if display_type == "holographic":
            from .weather_radar_holographic_display import WeatherRadarHolographicDisplay
            self._display = WeatherRadarHolographicDisplay()
            logger.info("[WEATHER_WIDGET] Created holographic weather radar display")
        else:
            self._display = WeatherRadarDisplay()
            logger.info("[WEATHER_WIDGET] Created standard weather radar display")
        
        # Store the current display type for change detection
        self._current_display_type = display_type
        
        # Subscribe to update events
        from core.event_driven_communication import get_event_bus
        self.event_bus = get_event_bus()
        # NOTE (production readiness re-analysis, August 2026): this used to be
        # `lambda _: self.update()`, called synchronously from EventBus's
        # dedicated "EventBus_Processor" background thread (confirmed live-
        # reachable: system_manager.py starts the EventBus, and 'weather_radar_update'
        # is actively published from display_message_router.py and both weather
        # radar display classes). QWidget.update() is a GUI method and Qt does not
        # support calling GUI methods from a non-GUI thread -- this is a
        # documented cross-thread-access hazard (undefined behavior / potential
        # crash depending on platform and Qt version), not something that merely
        # happened to work by chance. Tried QMetaObject.invokeMethod() with a
        # QueuedConnection first, but couldn't positively confirm live that its
        # string-based method lookup actually resolves update()'s overloads in
        # this PyQt6 build (its return value came back None in an isolated
        # cross-thread test, and Qt only reliably supports invokeMethod-by-name
        # for methods explicitly registered as slots). Switched to a pyqtSignal
        # instead -- a Qt signal emitted from a different thread than its
        # receiver is automatically delivered via a queued connection, which is
        # PyQt's own primary, best-documented mechanism for this exact case, and
        # was live-verified (via the identical pattern on HolographicMFD, see
        # holographic_mfd.py) to actually execute the connected slot on the GUI
        # thread rather than the emitting thread.
        self._update_requested.connect(self.update)
        # Stored as an attribute (not an inline anonymous lambda) so it can
        # be passed to event_bus.unsubscribe() later -- see the reset path
        # in get_weather_radar_widget() below, which discards and replaces
        # this instance. Without a stable reference to the exact callback
        # object, there is no way to ever remove this subscription: added
        # (August 2026 re-analysis round, Round 11, EventBus subscriber
        # leak sweep) after confirming EventBus.subscribe() had no
        # unsubscribe() counterpart anywhere, so every widget reset here
        # permanently leaked the old widget instance (kept alive forever
        # by this callback reference) and left its stale callback firing
        # on every subsequent 'weather_radar_update' publish alongside the
        # new instance's callback.
        self._weather_update_callback = lambda _: self._update_requested.emit()
        self.event_bus.subscribe('weather_radar_update', self._weather_update_callback)
        
        # Set window properties
        self.setWindowTitle("Weather Radar Display")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)
        self.setMaximumSize(800, 600)  # Fix the size
        
        # Set window flags for proper display
        self.setWindowFlags(
            Qt.WindowType.Window |              # Regular window
            Qt.WindowType.WindowStaysOnTopHint |  # Stay on top
            Qt.WindowType.CustomizeWindowHint |   # Custom window
            Qt.WindowType.WindowTitleHint        # Show title bar
        )
        
    def paintEvent(self, event):
        """Handle Qt paint event"""
        # Check if display type has changed
        self._check_display_type_change()
        
        # Wrapped in try/finally (added August 2026 re-analysis round,
        # Round 13, Qt exception-propagation sweep): this used to construct
        # `painter` with no exception handling at all, then call
        # self._display.draw_radar_elements(...) -- a deep call tree
        # (particle emission, texture compositing, cell/precip/VIL
        # rendering) whose outer try/except (weather_radar_display.py
        # ::draw_radar_elements()) deliberately logs and *re-raises* rather
        # than swallowing. An uncaught exception here previously reached
        # this widget's paintEvent with the QPainter never `.end()`'d.
        # Live-reproduced with a minimal widget mirroring this exact
        # shape: an exception raised mid-paintEvent before painter.end()
        # is caught by this app's sys.excepthook (Main.py's
        # global_exception_handler) and logged -- it does not crash the
        # process -- but the unclosed QPainter leaves the widget's Qt
        # backing store in a corrupted state ("QBackingStore::endPaint()
        # called with active painter") that persists into every
        # *subsequent* paint of the same widget, not just the one that
        # failed, plus a "QPaintDevice: Cannot destroy paint device that
        # is being painted" error at eventual widget teardown. Root cause:
        # Python's traceback object (retained by sys.excepthook's `tb`
        # parameter, and by the interpreter's own exception-handling
        # machinery) keeps the failed paintEvent's stack frame -- and
        # therefore its local `painter` variable -- alive well past the
        # point where CPython's normal refcounting would otherwise
        # destroy it and trigger QPainter's RAII-style implicit end() on
        # a clean, non-exceptional return. This mirrors the exact,
        # already-fixed pattern base_display.py's paintEvent() uses
        # (try/except/finally with painter.isActive() before
        # painter.end()), which Round 7 found "exemplary" -- this widget's
        # own paintEvent just never got the same treatment. Live-verified
        # the fix eliminates the QBackingStore warning and the sticky
        # cross-paint corruption in the minimal reproduction.
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            # Draw radar display
            self._display.draw_radar_elements(painter, QRectF(self.rect()), {})
        except Exception as e:
            logger.error(f"[WEATHER_WIDGET] Error in paintEvent: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            if painter.isActive():
                painter.end()
        
    def _check_display_type_change(self):
        """Check if display type has changed and update display if needed"""
        try:
            # Get current display type from theme manager
            from ..visual.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()
            current_type = theme_manager.get_display_type("radar", "standard")
            
            # Check if display type has changed
            if current_type != self._current_display_type:
                logger.warning(f"[WEATHER_WIDGET] Display type changed from {self._current_display_type} to {current_type}, updating display")
                
                # Verify current display type
                is_holographic = False
                if self._display is not None:
                    from .weather_radar_holographic_display import WeatherRadarHolographicDisplay
                    is_holographic = isinstance(self._display, WeatherRadarHolographicDisplay)
                    logger.info(f"[WEATHER_WIDGET] Current display is {'holographic' if is_holographic else 'standard'}")
                
                # Clean up old display if needed
                if self._display is not None:
                    # First unsubscribe from any display tree nodes
                    try:
                        if hasattr(self._display, 'tree') and self._display.tree:
                            tree = self._display.tree
                            weather_node = tree.root.get_child("weather_radar")
                            if weather_node:
                                # Clean up subscribers on visual node
                                visual_node = weather_node.get_child("visual")
                                if visual_node and hasattr(visual_node, 'subscribers'):
                                    logger.warning(f"[WEATHER_WIDGET] Clearing subscribers from visual node")
                                    visual_node.subscribers.clear()
                                
                                # Clean up subscribers on data nodes
                                data_node = weather_node.get_child("data")
                                if data_node:
                                    for data_type in ["precipitation", "vil", "cells"]:
                                        type_node = data_node.get_child(data_type)
                                        if type_node and hasattr(type_node, 'subscribers'):
                                            logger.warning(f"[WEATHER_WIDGET] Clearing subscribers from {data_type} node")
                                            type_node.subscribers.clear()
                    except Exception as e:
                        logger.error(f"[WEATHER_WIDGET] Error clearing subscribers: {str(e)}")
                
                    # Then call cleanup method if it exists
                    if hasattr(self._display, 'cleanup'):
                        try:
                            self._display.cleanup()
                            logger.info("[WEATHER_WIDGET] Cleaned up old display")
                        except Exception as e:
                            logger.error(f"[WEATHER_WIDGET] Error cleaning up old display: {str(e)}")
                    
                    # Force garbage collection to clean up references
                    import gc
                    gc.collect()
                    logger.info("[WEATHER_WIDGET] Forced garbage collection after display cleanup")
                
                # Create new display based on type
                old_display = self._display
                if current_type == "holographic":
                    from .weather_radar_holographic_display import WeatherRadarHolographicDisplay
                    self._display = WeatherRadarHolographicDisplay()
                    logger.info("[WEATHER_WIDGET] Created new holographic weather radar display")
                else:
                    self._display = WeatherRadarDisplay()
                    logger.info("[WEATHER_WIDGET] Created new standard weather radar display")
                
                # Verify the new display is different from the old one
                if self._display is old_display:
                    logger.error("[WEATHER_WIDGET] Failed to create new display instance")
                    # Force creation of a new instance
                    if current_type == "holographic":
                        from .weather_radar_holographic_display import WeatherRadarHolographicDisplay
                        self._display = WeatherRadarHolographicDisplay()
                    else:
                        self._display = WeatherRadarDisplay()
                    logger.info("[WEATHER_WIDGET] Forced creation of new display instance")
                
                # Update stored display type
                self._current_display_type = current_type
                
                # Initialize the new display synchronously to ensure it's ready
                if hasattr(self._display, 'initialize_display'):
                    try:
                        # Initialize synchronously to ensure completion
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Create a task and wait for it to complete
                            future = asyncio.create_task(self._display.initialize_display())
                            # We can't wait here directly as it would block the UI thread
                            # Instead, we'll log that initialization is in progress
                            logger.info("[WEATHER_WIDGET] Display initialization started asynchronously")
                        else:
                            # Run directly if no loop is running
                            loop.run_until_complete(self._display.initialize_display())
                            logger.info("[WEATHER_WIDGET] Display initialized synchronously")
                    except Exception as e:
                        logger.error(f"[WEATHER_WIDGET] Error initializing new display: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Schedule a repaint to show the new display.
                # Fixed (August 2026 re-analysis round, Round 12,
                # GUI-thread-blocking/repaint-reentrancy sweep): this used
                # to call self.repaint() immediately after self.update(),
                # from within _check_display_type_change(), which is itself
                # invoked from the very top of paintEvent() -- i.e. a
                # synchronous, forced repaint() call made *from inside an
                # already-executing paintEvent*. Live-reproduced: Qt detects
                # this as illegal reentrancy ("QWidget::repaint: Recursive
                # repaint detected"), which does not simply no-op -- it
                # still forces a second, nested paintEvent() call before the
                # first has returned, doubling the paint work for this one
                # logical update and depending on backing-store/paint-device
                # state at the moment of reentry to render correctly at all.
                # self.update() alone already achieves the intended "make
                # sure the new display gets painted" goal by scheduling a
                # normal, non-reentrant repaint on the next event-loop
                # iteration -- the same mechanism used everywhere else in
                # this codebase to request a repaint -- so the extra
                # self.repaint() call was both redundant and actively
                # unsafe. Live-verified the fix with a minimal QWidget
                # reproducing the exact update()+repaint() sequence:
                # removing repaint() eliminates the "Recursive repaint
                # detected" warning and the reentrant nested paintEvent()
                # call entirely.
                self.update()
                logger.info("[WEATHER_WIDGET] Scheduled repaint after display change")
        except Exception as e:
            logger.error(f"[WEATHER_WIDGET] Error checking display type change: {str(e)}")
            logger.error(traceback.format_exc())
        
    def mousePressEvent(self, event):
        """Handle mouse press events and pass to display for interactive elements.
        
        Args:
            event: QMouseEvent containing click information
        """
        try:
            # Convert to QPointF for more precise positioning
            pos = QPointF(event.position())
            
            # Pass to display's handler
            if self._display.handle_mouse_click(pos):
                # If the click was handled by the display, update the widget
                self.update()
                logger.info(f"[WEATHER_WIDGET] Mouse click handled at ({pos.x():.1f}, {pos.y():.1f})")
            else:
                # If not handled, call the parent class implementation
                super().mousePressEvent(event)
                
        except Exception as e:
            logger.error(f"[WEATHER_WIDGET] Error handling mouse press: {str(e)}")
            logger.error(traceback.format_exc())
            # Still call parent to ensure proper event handling
            super().mousePressEvent(event)
        
    def is_running(self):
        """Check if display is running"""
        return self._running
        
    def start(self):
        """Start the display"""
        self._running = True
        # Don't show the widget in its own window when using the legend generator
        # The display will be shown within the MFD instead
        # Position relative to other displays
        # screen = QApplication.primaryScreen().geometry()
        # self.move(screen.left() + 1750, screen.top() + 50)
        # self.show()
        
    def stop(self):
        """Stop the display"""
        self._running = False
        self.hide()
        
    async def initialize_display(self, show_window=True):
        """Initialize the display with proper sequence
        
        Args:
            show_window: Whether to show the widget window (True for standalone, False for embedded)
        """
        try:
            logger.info("[WEATHER_WIDGET] Starting display initialization")
            
            # Initialize the underlying display
            await self._display.initialize_display()
            
            # Verify initialization
            if not self._display.tree._initialized:
                logger.error("[WEATHER_WIDGET] Display tree not properly initialized")
                raise RuntimeError("Display tree initialization failed")
            
            # Set running state but NEVER show window
            self._running = True
            
            #   THIS make the weather radar display show up in its own window
            #   Commenting this out makes the weather radar display show up in the MFD only
            # Override show_window parameter - never show the window
            # if show_window:
            #     # Position relative to other displays
            #     screen = QApplication.primaryScreen().geometry()
            #     self.move(screen.left() + 1750, screen.top() + 50)
            #     self.show()
                
            logger.info("[WEATHER_WIDGET] Display initialization complete")
            
        except Exception as e:
            logger.error(f"[WEATHER_WIDGET] Error during initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
    async def set_mode(self, mode):
        """Set display mode with proper initialization check"""
        try:
            # Verify initialization
            if not self._display.tree._initialized:
                logger.error("[WEATHER_WIDGET] Cannot set mode - display not initialized")
                raise RuntimeError("Display not initialized")
                
            # Use proper mode update mechanism
            mode_data = {
                'current_mode': mode.name if hasattr(mode, 'name') else str(mode),
                'mode_enum': 'weather_radarMode',
                'source_system': 'weather_radar',
                'timestamp': time.time()
            }
            
            await self._display._handle_mode_update('mode', mode_data)
            self.update()
            logger.info(f"[WEATHER_WIDGET] Mode updated to {mode_data['current_mode']}")
            
        except Exception as e:
            logger.error(f"[WEATHER_WIDGET] Error setting mode: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
    @property
    def display(self):
        """Get the underlying radar display"""
        # Check if display type has changed before returning
        self._check_display_type_change()
        return self._display
