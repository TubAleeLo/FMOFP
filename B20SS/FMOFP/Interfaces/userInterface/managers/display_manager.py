from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import QTimer, QThread
from typing import Dict, Union
import time
import traceback
# Import display-local modules
from ..messaging.display_address_utils import (
    PFD_SUBADDRESS, MFD_SUBADDRESS, EICAS_SUBADDRESS,
    RADAR_DISPLAY_SUBADDRESS, TSD_SUBADDRESS, SMS_SUBADDRESS
)
from ..messaging.display_message_types import (
    WEATHER_RADAR_MODE_STANDBY
)
# Still need to import DisplayType and DisplayMode from base_display
# as they are enums used throughout the display system
from ..displays.base_display import DisplayType, DisplayMode
from ..displays.pfd_container import PFDContainer
from ..displays.mfd_container import MFDContainer
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Mapping between string IDs and DisplayType enums
# Use subaddress names from display_address_utils for consistency
DISPLAY_ID_MAP = {
    'pfd': DisplayType.PFD,  # Keep string keys for backward compatibility
    'mfd': DisplayType.MFD,
    'eicas': DisplayType.EICAS,
    'radar_display': DisplayType.RADAR,
    'tsd': DisplayType.TSD,
    'sms': DisplayType.SMS,
    'hud': DisplayType.HUD
}

# Mapping between subaddress constants and DisplayType enums
# This provides a more consistent way to map between subaddresses and display types
SUBADDRESS_DISPLAY_MAP = {
    PFD_SUBADDRESS: DisplayType.PFD,
    MFD_SUBADDRESS: DisplayType.MFD,
    EICAS_SUBADDRESS: DisplayType.EICAS,
    RADAR_DISPLAY_SUBADDRESS: DisplayType.RADAR,
    TSD_SUBADDRESS: DisplayType.TSD,
    SMS_SUBADDRESS: DisplayType.SMS
}

class DisplayManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DisplayManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not self.initialized:
            # Check if we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("DisplayManager must be created in the main thread")

            self.displays: Dict[Union[str, DisplayType], QWidget] = {}
            self.current_mode = DisplayMode.DAY
            self.initialized = True
            self._running = False
            self._update_timer = None
            logger.info("Display Manager initialized")

    async def initialize(self):
        """Initialize the display manager"""
        if hasattr(self, '_init_complete'):
            logger.debug("Display Manager already initialized")
            return

        try:
            logger.info("Display Manager: Starting initialization")

            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display initialization must be done in the main thread")

            # Create update timer in main thread
            self._update_timer = QTimer()
            self._update_timer.setInterval(16)  # ~60 FPS
            self._update_timer.timeout.connect(self._update_displays)

            # Initialize theme manager first to ensure display types are properly set
            from ..displays.visual.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()
            logger.info("Theme manager initialized")

            # Set default display types for each theme if not already set
            for theme_name in ["classic", "modern", "night"]:
                try:
                    # Convert string to enum
                    from ..displays.visual.theme_manager import DisplayTheme
                    theme_enum = getattr(DisplayTheme, theme_name.upper())

                    # Get theme data
                    theme_data = theme_manager._themes.get(theme_enum)
                    if theme_data and "display_types" not in theme_data:
                        # Set default display types - all themes use standard display type
                        theme_data["display_types"] = {
                            "pfd": "standard",
                            "mfd": "standard",
                            "radar": "standard",
                            "hud": "standard"
                        }
                        logger.info(f"Set default display types for theme: {theme_name}")
                except Exception as theme_error:
                    logger.error(f"Error setting display types for theme {theme_name}: {str(theme_error)}")
                    logger.error(traceback.format_exc())

            # Initialize display tree manager
            from ..displays.display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()
            if not tree_manager._initialized:
                logger.info("Initializing display tree manager")
                await tree_manager.initialize()
                if not tree_manager._initialized:
                    raise RuntimeError("Display tree manager failed to initialize")
                logger.info("Display tree manager initialization verified")

            # Initialize displays with async support
            logger.info("Setting up displays")
            await self.setup_displays()

            # Verify display initialization
            if not self.displays:
                raise RuntimeError("No displays were created during initialization")

            for display_id, display in self.displays.items():
                if isinstance(display_id, str):  # Only check string keys to avoid duplicates
                    if not display:
                        raise RuntimeError(f"Display {display_id} was not properly created")
                    if hasattr(display, 'tree') and not display.tree._initialized:
                        raise RuntimeError(f"Display {display_id} tree not properly initialized")
                    logger.info(f"Display {display_id} initialization verified")

            self._init_complete = True
            logger.info("Display Manager initialization complete and verified")
        except Exception as e:
            logger.error(f"Error initializing displays: {str(e)}")
            logger.error(traceback.format_exc())
            self._init_complete = False
            raise

    async def setup_displays(self):
        """Create and configure all display instances"""
        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display setup must be done in the main thread")

            # Initialize display tree first
            from ..displays.display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()
            if not tree_manager._initialized:
                logger.info("Initializing display tree manager")
                await tree_manager.initialize()
                logger.info("Display tree manager initialization complete")

            if not self.displays:
                # Create displays with both string and enum keys
                logger.debug("Creating Primary Flight Display Container")
                from ..displays.pfd_container import PFDContainer
                pfd = PFDContainer()
                self.displays['pfd'] = pfd
                self.displays[DisplayType.PFD] = pfd

                logger.debug("Creating Multi-Function Display Container")
                from ..displays.mfd_container import MFDContainer
                mfd = MFDContainer()
                self.displays['mfd'] = mfd
                self.displays[DisplayType.MFD] = mfd

                # Initialize weather radar display
                logger.debug("Creating Weather Radar Display")
                from ..displays.radar.weather_radar_widget import WeatherRadarWidget
                weather_radar = WeatherRadarWidget()
                self.displays['radar_display'] = weather_radar
                self.displays[DisplayType.RADAR] = weather_radar

                # Initialize EICAS
                logger.debug("Creating EICAS Display")
                from ..displays.eicas import EICASDisplay
                eicas = EICASDisplay()
                self.displays['eicas'] = eicas
                self.displays[DisplayType.EICAS] = eicas

                # Initialize Tactical Situation Display
                logger.debug("Creating Tactical Situation Display")
                from ..displays.tsd import TacticalSituationDisplay
                tsd = TacticalSituationDisplay()
                self.displays['tsd'] = tsd
                self.displays[DisplayType.TSD] = tsd

                # Initialize Stores Management System
                logger.debug("Creating Stores Management System Display")
                from ..displays.sms import StoresManagementDisplay
                sms = StoresManagementDisplay()
                self.displays['sms'] = sms
                self.displays[DisplayType.SMS] = sms

                # Initialize HUD container
                logger.debug("Creating Head-Up Display Container")
                from ..displays.hud_container import HUDContainer
                hud = HUDContainer()
                self.displays['hud'] = hud
                self.displays[DisplayType.HUD] = hud

                # Initialize containers
                logger.info("Initializing display containers")

                # Initialize PFD container
                logger.debug("Initializing PFD container")
                await pfd.initialize()

                # Initialize MFD container
                logger.debug("Initializing MFD container")
                await mfd.initialize()

                # Initialize HUD container
                logger.debug("Initializing HUD container")
                await hud.initialize()

                # Initialize weather radar display specifically
                logger.info("Initializing weather radar display")
                try:
                    # Initialize the weather radar display
                    await weather_radar.initialize_display()

                    # Set initial mode to STANDBY only after initialization
                    # Use constant from display_message_types for consistency
                    mode_data = {
                        'current_mode': WEATHER_RADAR_MODE_STANDBY,
                        'mode_enum': 'weather_radarMode',
                        'source_system': 'weather_radar',
                        'timestamp': time.time(),
                        'message_type': 'mode_change'  # Add message_type for consistent handling
                    }
                    await weather_radar.display._handle_mode_update('mode', mode_data)
                    logger.info("Weather radar display initialized and set to STANDBY")
                except Exception as e:
                    logger.error(f"Error initializing weather radar display: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise

        except Exception as e:
            logger.error(f"Error setting up displays: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def show_display(self, display_id: Union[str, DisplayType, str]):
        """Show a specific display

        Args:
            display_id: Can be a string ID, DisplayType enum, or subaddress constant
        """
        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display operations must be done in the main thread")

            # Convert string ID to enum if needed
            if isinstance(display_id, str):
                # First check if it's a subaddress
                if display_id in SUBADDRESS_DISPLAY_MAP:
                    display_type = SUBADDRESS_DISPLAY_MAP[display_id]
                else:
                    # Then check if it's a string ID
                    display_type = DISPLAY_ID_MAP.get(display_id)
                    if not display_type:
                        raise ValueError(f"Invalid display ID: {display_id}")
                display_id = display_type

            if display_id in self.displays:
                display = self.displays[display_id]
                if not display.isVisible():
                    display.show()
                    # Log in exact format required by test
                    logger.info(f"Display {display_id.name} shown")
                display.raise_()
                display.activateWindow()
            else:
                logger.warning(f"Display {display_id} not found in available displays")
        except Exception as e:
            logger.error(f"Error showing display {display_id}: {str(e)}")
            logger.error(traceback.format_exc())

    def set_mode(self, mode: DisplayMode):
        """Set display mode for all displays"""
        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display operations must be done in the main thread")

            self.current_mode = mode
            for display_id, display in self.displays.items():
                if isinstance(display_id, str):  # Only process string keys to avoid duplicates
                    display.set_mode(mode)
                    # Log in exact format required by test
                    logger.info(f"Display {DISPLAY_ID_MAP[display_id].name} mode changed to {mode.name}")
        except Exception as e:
            logger.error(f"Error setting display mode: {str(e)}")
            logger.error(traceback.format_exc())

    def _update_displays(self):
        """Update all displays"""
        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                return

            if not self._running:
                return

            # Only update displays with string keys to avoid duplicates
            for display_id, display in self.displays.items():
                if isinstance(display_id, str) and display.is_running() and display.isVisible():
                    display.update()
        except Exception as e:
            logger.error(f"Error updating displays: {str(e)}")
            logger.error(traceback.format_exc())

    async def start(self):
        """Start the display manager"""
        if self._running:
            logger.debug("Display manager already running")
            return

        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display operations must be done in the main thread")

            # Verify initialization is complete
            if not hasattr(self, '_init_complete') or not self._init_complete:
                raise RuntimeError("Display manager not properly initialized")

            logger.info("Starting display manager")

            # Verify display tree is initialized
            from ..displays.display_nodes.display_tree_manager import get_display_tree_manager
            tree_manager = get_display_tree_manager()
            if not tree_manager._initialized:
                raise RuntimeError("Display tree manager not initialized")
            logger.info("Display tree manager verified")

            # Start update timer
            if self._update_timer:
                self._update_timer.start()
                logger.info("Display update timer started")

            # Position and show displays
            screen = QApplication.primaryScreen().geometry()

            # Start PFD
            if 'pfd' in self.displays:
                pfd = self.displays['pfd']
                if not pfd:
                    raise RuntimeError("PFD display not properly created")
                # Position PFD on the left side
                pfd.move(screen.left() + 50, screen.top() + 50)
                await pfd.start()
                pfd.show()  # Explicitly show the display
                logger.info("Primary Flight Display: Started, positioned, and shown")

            # Start MFD
            if 'mfd' in self.displays:
                mfd = self.displays['mfd']
                if not mfd:
                    raise RuntimeError("MFD display not properly created")
                # Position MFD to the right of PFD
                mfd.move(screen.left() + 900, screen.top() + 50)
                await mfd.start()
                mfd.show()  # Explicitly show the display
                logger.info("Multi-Function Display: Started, positioned, and shown")

            # Start HUD but don't show it (not used in this configuration)
            if 'hud' in self.displays:
                hud = self.displays['hud']
                if not hud:
                    raise RuntimeError("HUD display not properly created")
                # Position HUD at the top center
                hud.move(screen.left() + 450, screen.top() + 10)
                await hud.start()
                # Don't show HUD as it's not needed
                logger.info("Head-Up Display: Started and positioned (not shown)")

            # Start EICAS — positioned below PFD, not shown by default
            if 'eicas' in self.displays:
                eicas = self.displays['eicas']
                eicas.move(screen.left() + 50, screen.top() + 700)
                eicas.start()
                logger.info("EICAS Display: Started and positioned (not shown by default)")

            # Start TSD — positioned beside EICAS, not shown by default
            if 'tsd' in self.displays:
                tsd = self.displays['tsd']
                tsd.move(screen.left() + 900, screen.top() + 700)
                tsd.start()
                logger.info("Tactical Situation Display: Started and positioned (not shown by default)")

            # Start SMS — positioned below TSD, not shown by default
            if 'sms' in self.displays:
                sms = self.displays['sms']
                sms.move(screen.left() + 1750, screen.top() + 700)
                sms.start()
                logger.info("Stores Management System Display: Started and positioned (not shown by default)")

            # Start Weather Radar Display but don't show it (integrated into MFD)
            if 'radar_display' in self.displays:
                radar = self.displays['radar_display']
                if not radar:
                    raise RuntimeError("Weather Radar display not properly created")
                if not radar.display.tree._initialized:
                    raise RuntimeError("Weather Radar display tree not initialized")
                # Position radar display to the right of MFD
                radar.move(screen.left() + 1700, screen.top() + 50)
                radar.start()
                # Don't show radar as a separate window
                logger.info("Weather Radar Display: Started and positioned (not shown)")

            # Verify all displays are running
            for display_id, display in self.displays.items():
                if isinstance(display_id, str):  # Only verify string keys to avoid duplicates
                    if not display.is_running():
                        raise RuntimeError(f"Display {display_id} failed to start")
                    logger.info(f"Display {display_id} running verified")

            self._running = True
            logger.info("Display manager started and verified successfully")

        except Exception as e:
            logger.error(f"Error starting display manager: {str(e)}")
            logger.error(traceback.format_exc())
            self._running = False
            raise

    def stop(self):
        """Stop the display manager"""
        try:
            # Ensure we're in the main thread
            if QThread.currentThread() is not QApplication.instance().thread():
                raise RuntimeError("Display operations must be done in the main thread")

            self._running = False

            # Stop update timer
            if self._update_timer and self._update_timer.isActive():
                self._update_timer.stop()

            # Stop and close all displays (using string keys to avoid duplicates)
            for display_id, display in [(k,v) for k,v in self.displays.items() if isinstance(k, str)]:
                try:
                    logger.debug(f"{display_id}: Stopping display")
                    display.stop()
                except Exception as e:
                    logger.error(f"Error stopping display {display_id}: {str(e)}")
                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error stopping display manager: {str(e)}")
            logger.error(traceback.format_exc())

# Singleton instance
_display_manager = None

def get_display_manager():
    global _display_manager
    if _display_manager is None:
        # Ensure we're in the main thread
        if QThread.currentThread() is not QApplication.instance().thread():
            raise RuntimeError("DisplayManager must be created in the main thread")
        _display_manager = DisplayManager()
    return _display_manager
