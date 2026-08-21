"""
System startup entry point
"""
import sys
import os
import traceback

# ── Path bootstrap ────────────────────────────────────────────────────────────
# Ensure both B20SS/ and B20SS/FMOFP/ are on sys.path so that bare-package
# imports (Utils.*, storage.*, core.*) resolve correctly regardless of how
# this file is launched (debugger, CLI, venv, etc.).
_HERE = os.path.dirname(os.path.abspath(__file__))          # …/B20SS/FMOFP
_ROOT = os.path.dirname(_HERE)                               # …/B20SS
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Install the dual-path import alias shim as early as possible, before
# any other project-local import below. See Utils/dual_path_compat.py:
# without this, "import Utils.X" (bare) and "from FMOFP.Utils.X import Y"
# (absolute) -- both used in this very file -- would load the same
# source file as two separate module/class objects.
try:
    from Utils.dual_path_compat import install as _install_dual_path_alias
    _install_dual_path_alias()
except ImportError:
    pass

# ── Working-directory bootstrap ───────────────────────────────────────────────
# All relative config paths in this codebase (e.g. 'FMOFP/dbConfig.xml',
# 'FMOFP/local_messaging/...') are written relative to B20SS/.
# Normalise CWD to B20SS/ regardless of where the user launched from,
# so those paths resolve correctly whether SystemStart.py is run as:
#   cd B20SS      && py FMOFP/SystemStart.py   (CWD already correct)
#   cd B20SS/FMOFP && py SystemStart.py        (CWD was wrong — fixed here)
if os.path.abspath(os.getcwd()) != os.path.abspath(_ROOT):
    os.chdir(_ROOT)
# ─────────────────────────────────────────────────────────────────────────────
import Utils.common.fetching as fetching
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.system_states import SystemState
from FMOFP.core.system_manager import get_system_manager
from FMOFP.core.initializer import get_initializer

logger = get_logger()

async def main():
    try:
        # Initialize the system
        initializer = get_initializer()
        initializer.initialize()  # This must complete before proceeding

        # Verify initialization
        app = initializer.get_app()
        loop = initializer.get_loop()
        if not app or not loop:
            raise RuntimeError("Failed to initialize application or event loop")

        logger.info("Starting Flight Management Operating Flight Program")

        # Import here to avoid circular imports
        from Main import start_fmofp

        # Start FMOFP
        await start_fmofp()

    except Exception as e:
        logger.critical(f"Critical error in SystemStart: {str(e)}")

        # Try to get system manager and set error state
        try:
            system_manager = get_system_manager()
            system_manager.state_manager.set_state(SystemState.ERROR)
        except Exception as cleanup_error:
            logger.critical(f"Error during cleanup: {str(cleanup_error)}")

        sys.exit(1)

if __name__ == "__main__":
    # Import threading here to avoid circular imports
    import threading

    try:
        # Check if we're in the main thread
        if threading.current_thread() is not threading.main_thread():
            logger.critical("SystemStart.py must be run in the main thread")
            sys.exit(1)

        # Initialize system first
        initializer = get_initializer()
        initializer.initialize()

        # Get Qt application and event loop
        app = initializer.get_app()
        loop = initializer.get_loop()

        if not app or not loop:
            raise RuntimeError("Failed to initialize application or event loop")

        try:
            # Run the main coroutine
            loop.run_until_complete(main())

            # Start Qt event loop
            with loop:  # Ensure proper cleanup of event loop
                loop.run_forever()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            # Clean up
            initializer.cleanup()

    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)
