"""
AsyncThreadWrapper

Provides a wrapper class that bridges asyncio tasks and thread visibility by running
asyncio event loops in dedicated threads that are properly registered with the thread manager.
"""

import asyncio
import threading
import traceback
from typing import Optional, Callable, Coroutine
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.thread_manager import thread_manager

logger = get_logger()

class AsyncThreadWrapper:
    """
    Wraps asyncio coroutines in a properly managed thread that is visible in the thread manager
    and system call stack.
    """
    def __init__(self, name: str, target: Callable[..., Coroutine], *args, **kwargs):
        self.name = name
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        self._started = threading.Event()
        self._error: Optional[Exception] = None
        
        # Register with thread manager
        thread_manager.register_startup_thread(self.name)
        logger.info(f"AsyncThreadWrapper: Registered thread '{self.name}' with thread manager")

    def _run_loop(self):
        """
        Thread target that sets up and runs the asyncio event loop.
        Ensures proper thread naming and state management.
        """
        try:
            # Set thread name for visibility
            threading.current_thread().name = self.name
            logger.info(f"AsyncThreadWrapper: Starting thread '{self.name}'. Thread ID: {threading.get_ident()}")

            # Create and set event loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Create and run the main coroutine
            main_task = self.loop.create_task(self._run_target())
            self.running = True
            self._started.set()
            
            # Run the event loop
            self.loop.run_until_complete(main_task)
            
        except Exception as e:
            self._error = e
            logger.error(f"AsyncThreadWrapper: Error in thread '{self.name}': {str(e)}")
        finally:
            self.running = False
            if self.loop and not self.loop.is_closed():
                self.loop.close()
            logger.info(f"AsyncThreadWrapper: Thread '{self.name}' ended")

    async def _run_target(self):
        """
        Runs the target coroutine and handles cleanup.
        """
        try:
            logger.info(f"AsyncThreadWrapper: Running target in thread '{self.name}'")
            await self.target(*self.args, **self.kwargs)
        except asyncio.CancelledError:
            logger.info(f"AsyncThreadWrapper: Target in thread '{self.name}' cancelled")
        except Exception as e:
            logger.error(f"AsyncThreadWrapper: Error running target in thread '{self.name}': {str(e)}")
            raise

    def start(self):
        """
        Starts the wrapped coroutine in a new thread.
        Returns immediately, use wait_until_started() to wait for thread to be ready.
        """
        if self.thread and self.thread.is_alive():
            
            return False

        try:
            self.thread = threading.Thread(target=self._run_loop)
            thread_manager.add_thread(self.name, target=self._run_loop)
            success = thread_manager.start_thread(self.name)
            
            if success:
                logger.info(f"AsyncThreadWrapper: Successfully started thread '{self.name}'")
                return True
            else:
                logger.error(f"AsyncThreadWrapper: Failed to start thread '{self.name}'")
                return False
                
        except Exception as e:
            logger.error(f"AsyncThreadWrapper: Error starting thread '{self.name}': {str(e)}")
            return False

    def wait_until_started(self, timeout: Optional[float] = None) -> bool:
        """
        Waits until the thread and event loop are ready.
        Returns True if started successfully, False if timeout or error occurred.
        """
        if self._started.wait(timeout):
            if self._error:
                logger.error(f"AsyncThreadWrapper: Thread '{self.name}' failed to start: {str(self._error)}")
                return False
            return True
        logger.error(f"AsyncThreadWrapper: Timeout waiting for thread '{self.name}' to start")
        return False

    async def stop(self):
        """
        Stops the event loop and thread.
        Should be called from another thread/coroutine.
        """
        logger.info(f"AsyncThreadWrapper: Stopping thread '{self.name}'")
        self.running = False
        
        if self.loop and not self.loop.is_closed():
            try:
                # Cancel all running tasks
                for task in asyncio.all_tasks(self.loop):
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                self.loop.stop()
                self.loop.close()
            except Exception as e:
                logger.error(f"AsyncThreadWrapper: Error stopping event loop in thread '{self.name}': {str(e)}")

        if self.thread and self.thread.is_alive():
            self.thread.join()
            logger.info(f"AsyncThreadWrapper: Thread '{self.name}' stopped")

    def is_alive(self) -> bool:
        """
        Checks if the thread is alive and running.
        """
        return bool(self.thread and self.thread.is_alive() and self.running)

    def get_error(self) -> Optional[Exception]:
        """
        Returns any error that occurred in the thread.
        """
        return self._error
