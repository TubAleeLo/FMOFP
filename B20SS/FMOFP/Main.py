"""
Main Entry Point for Flight Management Operating Flight Program (FMOFP)

This module initializes and starts the FMOFP system, including all subsystems
and components. It sets up the event-driven communication system and manages
the overall program lifecycle.
"""

import os
import sys
import threading
import signal
import traceback
import asyncio

# ── Path/working-directory bootstrap (same as SystemStart.py) ────────────────
# `python FMOFP/Main.py` is the launch command documented by install.py and
# the README, but running this file directly puts only FMOFP/ on sys.path,
# so the `import FMOFP...` lines below raised ModuleNotFoundError — the
# documented entry point simply did not work (found August 2026 live-boot
# re-verification; SystemStart.py already had this bootstrap, Main.py never
# did). Mirror SystemStart.py: ensure both B20SS/ and B20SS/FMOFP/ are on
# sys.path, install the dual-path import alias shim, and normalise CWD to
# B20SS/ so the relative config paths ('FMOFP/dbConfig.xml', ...) resolve.
_HERE = os.path.dirname(os.path.abspath(__file__))          # …/B20SS/FMOFP
_ROOT = os.path.dirname(_HERE)                               # …/B20SS
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    from Utils.dual_path_compat import install as _install_dual_path_alias
    _install_dual_path_alias()
except ImportError:
    pass
if os.path.abspath(os.getcwd()) != os.path.abspath(_ROOT):
    os.chdir(_ROOT)
# ─────────────────────────────────────────────────────────────────────────────

import FMOFP.Utils.common.fetching as fetching
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.system_states import SystemState
from FMOFP.core.system_manager import get_system_manager
from FMOFP.core.event_driven_communication import get_event_bus
from FMOFP.local_messaging.routing.handlers.system_message_handlers.RadarMessageHandler import get_radar_message_handler
from PyQt6.QtCore import QTimer
from FMOFP.core.initializer import get_initializer

# Initialize SysLogger
logger = get_logger()
logger.debug("Main.py execution started - This is a test debug message")

class Flight_Management_Operating_Flight_Program:
    def __init__(self):
        logger.info(f"Flight_Management_Operating_Flight_Program __init__ called. Thread ID: {threading.get_ident()}")
        self.system_manager = get_system_manager()
        self.event_bus = get_event_bus()
        self.radar_message_handler = get_radar_message_handler()
        self._initialized = False
        self._started = False
        self.running = False
        self.shutdown_event = threading.Event()
        self._keep_running = True
        self._check_timer = None
        
        # Get existing instances from Initializer
        self._initializer = get_initializer()
        self._app = self._initializer.get_app()
        self._loop = self._initializer.get_loop()

    async def initialize(self):
        if self._initialized:
            # Silenced logging
            return

        logger.info(f"Initializing Flight Management Operating Flight Program. Thread ID: {threading.get_ident()}")
        logger.info("Initializing system components")
        try:
            # Initialize system asynchronously
            await self.system_manager.initialize_system()
            self._initialized = True
            logger.info(f"Flight Management Operating Flight Program initialized. Thread ID: {threading.get_ident()}")
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}. Thread ID: {threading.get_ident()}")
            await self.shutdown()

    def start(self):
        if not self._initialized:
            logger.error("Attempt to start uninitialized system. Please call initialize() first.")
            return

        if self._started:
            logger.warning("Flight Management Operating Flight Program already started. Ignoring repeated start attempt.")
            return

        logger.info(f"Flight_Management_Operating_Flight_Program start method called. Thread ID: {threading.get_ident()}")
        
        try:
            # Ensure we're in the main thread
            if threading.current_thread() is not threading.main_thread():
                raise RuntimeError("System must be started from the main thread")
            
            # Start the system manager
            self.system_manager.start_FM_system()
            
            # Set up check timer in main thread
            self._check_timer = QTimer()
            self._check_timer.setInterval(100)  # 100ms interval
            self._check_timer.timeout.connect(self._check_system_ready_slot)
            self._check_timer.start()
            
            # System is now running
            self.running = True
            self._started = True
            
        except Exception as e:
            logger.error(f"Error during system start: {str(e)}. Thread ID: {threading.get_ident()}")
            self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self.shutdown()))

    def _check_system_ready_slot(self):
        """Qt slot for checking system readiness"""
        try:
            if self.system_manager.is_system_ready():
                # Schedule state change in event loop thread
                self._loop.call_soon_threadsafe(
                    lambda: self.system_manager.state_manager.set_state(SystemState.NORMAL)
                )
                logger.info(f"System is in normal operation. Thread ID: {threading.get_ident()}")
                self._check_timer.stop()
        except Exception as e:
            logger.error(f"Error checking system readiness: {str(e)}")
            self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self.shutdown()))

    async def shutdown(self):
        if not self._started:
            logger.warning("Attempt to shut down a system that hasn't been started. Ignoring.")
            return

        # Flip _started to False immediately, before any of the real
        # shutdown work below (not at the end, as this previously did).
        # shutdown() is scheduled via loop.call_soon_threadsafe(lambda:
        # asyncio.create_task(fmofp.shutdown())) from the SIGINT/SIGTERM
        # signal handler in start_fmofp() below -- two signals arriving
        # close together (e.g. a duplicate SIGTERM, or SIGINT followed by
        # SIGTERM, both plausible from process managers/operators) each
        # schedule their own shutdown() task. The guard above only
        # protects against a *second* signal arriving after the *first*
        # shutdown() has fully finished; the previous code left
        # `self._started = False` until after `self.system_manager.stop()`,
        # `await asyncio.sleep(0.1)`, and `self.system_manager.
        # wait_for_shutdown()` had all already run, so a second shutdown()
        # task starting during that window would still see `_started ==
        # True`, pass the guard, and call `self.system_manager.stop()` a
        # second time on top of the first (live-reproduced with a stand-in
        # mirroring this exact guard/await structure: two overlapping
        # shutdown() calls both passed the guard and both invoked the
        # stop-work, confirmed via a call counter). Setting the flag here,
        # before the first await point, closes that window: a second
        # shutdown() task now sees `_started == False` immediately and
        # returns via the guard instead of re-running the stop sequence.
        self._started = False

        logger.info(f"Shutting down Flight Management Operating Flight Program. Thread ID: {threading.get_ident()}")
        self.running = False
        self._keep_running = False
        
        try:
            # Stop check timer
            if self._check_timer and self._check_timer.isActive():
                self._check_timer.stop()
            
            # Stop system components
            self.system_manager.stop()
            self.event_bus.stop()
            
            # Give components time to clean up
            await asyncio.sleep(0.1)
            
            self.system_manager.wait_for_shutdown()
            self.shutdown_event.set()
            # self._started was already set to False at the top of this
            # method (see comment there) -- not repeated here.
            self._initialized = False
            
            logger.info(f"Flight Management Operating Flight Program shut down. Thread ID: {threading.get_ident()}")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            raise

    def wait_for_shutdown(self):
        self.shutdown_event.wait()

def global_exception_handler(exctype, value, tb):
    logger.critical(f"Uncaught exception: {exctype.__name__}: {value}")

async def start_fmofp():
    sys.excepthook = global_exception_handler

    # Get existing instances from Initializer
    initializer = get_initializer()
    app = initializer.get_app()
    loop = initializer.get_loop()
    
    if not app or not loop:
        raise RuntimeError("Application or event loop not properly initialized")

    fmofp = Flight_Management_Operating_Flight_Program()
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig} to shutdown")
        loop.call_soon_threadsafe(lambda: asyncio.create_task(fmofp.shutdown()))

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize and start the system
        await fmofp.initialize()
        fmofp.start()
        
        # Wait for system to be ready
        while fmofp.running and not fmofp.system_manager.is_system_ready():
            await asyncio.sleep(0.1)
            
        # System is ready, let it run
        while fmofp.running:
            await asyncio.sleep(0.1)
            
    except Exception as e:
        logger.error(f"Error in FMOFP: {str(e)}")
        await fmofp.shutdown()
    finally:
        if fmofp.running:
            await fmofp.shutdown()

if __name__ == "__main__":
    
    logger.info(f"Main thread ID: {threading.get_ident()}")
    
    try:
        # Initialize the system through Initializer
        initializer = get_initializer()
        initializer.initialize()
        
        # Get the event loop from initializer
        loop = initializer.get_loop()
        
        # Run the main coroutine and Qt event loop together
        loop.create_task(start_fmofp())
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        # Let the initializer handle cleanup
        initializer.cleanup()
