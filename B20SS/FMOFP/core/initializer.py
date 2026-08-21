"""
Initializer singleton for managing shared system resources
"""
import os
import sys
import threading
import traceback
import asyncio
from PyQt6.QtWidgets import QApplication
from Utils.logger.sys_logger import get_logger
from Utils.common.system_state_manager import SystemStateManager
from Utils.common.system_states import SystemState
from qasync import QEventLoop

logger = get_logger()

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class Initializer(metaclass=SingletonMeta):
    def __init__(self):
        self.initialized = False
        self._app = None
        self._loop = None
        self._state_manager = None
        self._shutdown_started = False

    def initialize(self):
        if not self.initialized:
            try:
                # Log system information
                logger.info(f"Current working directory: {os.getcwd()}")
                logger.info(f"Main thread ID: {threading.get_ident()}")
                
                # Initialize Qt application (singleton)
                if not QApplication.instance():
                    self._app = QApplication(sys.argv)
                else:
                    self._app = QApplication.instance()
                
                # Create event loop that works with Qt (singleton)
                if not self._loop:
                    self._loop = QEventLoop(self._app)
                    asyncio.set_event_loop(self._loop)
                
                # Initialize SystemStateManager
                self._state_manager = SystemStateManager()
                self._state_manager.initialize()
                
                # Set up state transition handler
                self._state_manager.add_state_change_handler(self._handle_state_change)
                
                self.initialized = True
                logger.info("System initialization completed successfully.")
            except Exception as e:
                logger.error(f"Error during system initialization: {str(e)}")
                raise

    def _handle_state_change(self, old_state, new_state):
        """Handle system state transitions"""
        logger.info(f"System state transition: {old_state} -> {new_state}")
        
        if new_state == SystemState.SHUTDOWN:
            self._initiate_shutdown()
        elif new_state == SystemState.ERROR:
            self._handle_error_state()

    def _initiate_shutdown(self):
        """Initiate graceful shutdown sequence

        NOTE: This is invoked synchronously from _handle_state_change(), which
        is itself fired synchronously by state_manager.set_state(SHUTDOWN).
        That call happens from *inside* system_manager.stop_system(), which is
        running as part of the still-executing Flight_Management_Operating_Flight_Program.shutdown()
        asyncio task. That means this method's call stack is still nested inside
        an active task on the running event loop.

        Previously this method called self.cleanup() synchronously here, and
        cleanup() calls self._loop.run_until_complete(...) and self._loop.close()
        on that SAME loop. Calling run_until_complete() reentrantly while
        another task on the loop hasn't finished executing is illegal in
        asyncio and raised:
            RuntimeError: Cannot enter into task <...MessageRoutingService.stop()...>
            while another task <...Flight_Management_Operating_Flight_Program.shutdown()...>
            is being executed.
        followed by "Error during cleanup: Event loop stopped before Future
        completed." The loop was then left in an inconsistent state where
        run_forever() never actually returned, so the process kept running
        (Qt timers/animations kept firing) long after "All system components
        stopped" was logged.

        The fix: only schedule loop.stop() here (via call_soon_threadsafe,
        which is safe to call from any context). Do NOT call cleanup() here.
        Once the current task chain finishes unwinding and control returns to
        run_forever(), the scheduled stop() will actually take effect and
        run_forever() will return. SystemStart.py's own `finally:
        initializer.cleanup()` block then runs cleanup() safely, outside of
        any actively-executing task, where run_until_complete()/close() are
        legal.

        Watchdog: even with the fix above, live testing showed that
        confirmed-successful calls to loop.stop() (self._loop.is_running()
        correctly reports False immediately afterward, and Qt's
        QApplication.exit() is confirmed invoked by qasync's QEventLoop.stop())
        do not always cause the underlying QApplication.exec() call inside
        qasync's run_forever() to actually return - some UI widgets run their
        own free-running QTimers (e.g. weather radar animation, ~60fps) that
        keep Qt's native event loop pumping. By this point in shutdown, every
        thread and resource this codebase owns has already been stopped
        cleanly (verified via live SIGTERM testing: thread_manager reports
        zero "did not stop within timeout" errors and all system components
        report stopped within ~4 seconds of receiving the signal) - the only
        remaining thing keeping the process alive is Qt's own event pump. A
        bounded watchdog is the standard, safe way to guarantee the process
        actually exits: if we haven't returned from run_forever() a few
        seconds after every real component has already finished stopping,
        force-exit. This mirrors how orchestrators (systemd/k8s/docker) treat
        graceful shutdown themselves: try to exit cleanly, then hard-kill
        after a bounded grace period.
        """
        if self._shutdown_started:
            return
            
        self._shutdown_started = True
        logger.info("Initiating graceful shutdown sequence")
        
        try:
            # Stop the event loop if it's running. This is scheduled via
            # call_soon_threadsafe so it only takes effect once the current
            # task chain finishes and control returns to run_forever() -
            # cleanup() (run_until_complete/close) must NOT be called here,
            # see docstring above.
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)

            # Safety-net watchdog: force the process to exit if it hasn't
            # already done so shortly after shutdown was initiated. All
            # component/thread cleanup happens well within this window (see
            # docstring above); this only ever fires if something below the
            # asyncio layer (e.g. a Qt native event loop / timer) is keeping
            # the process alive after every real resource has been released.
            def _watchdog_force_exit():
                logger.warning(
                    "Shutdown watchdog: process did not exit naturally within "
                    "the grace period after all components stopped; forcing exit."
                )
                os._exit(0)

            watchdog = threading.Timer(5.0, _watchdog_force_exit)
            watchdog.daemon = True
            watchdog.start()
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")

    def _handle_error_state(self):
        """Handle transition to error state"""
        logger.error("System entered ERROR state")
        self._initiate_shutdown()

    def get_app(self):
        return self._app

    def get_loop(self):
        return self._loop

    def get_state_manager(self):
        return self._state_manager

    def cleanup(self):
        """Clean up resources"""
        if not self._shutdown_started:
            self._shutdown_started = True
            
        try:
            logger.info("Starting cleanup sequence")
            
            # Stop the event loop
            if self._loop and self._loop.is_running():
                self._loop.stop()
                
            # Close the event loop
            if self._loop and not self._loop.is_closed():
                # Run any pending callbacks
                pending = asyncio.all_tasks(self._loop)
                if pending:
                    logger.info(f"Cleaning up {len(pending)} pending tasks")
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                self._loop.close()
                logger.info("Event loop closed")
                
            # Clean up Qt application
            if self._app:
                self._app.quit()
                logger.info("Qt application quit")
                
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

# Singleton instance
_initializer = None

def get_initializer():
    global _initializer
    if _initializer is None:
        _initializer = Initializer()
    return _initializer
