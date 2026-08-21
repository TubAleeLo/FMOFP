'''
Thread Manager

ThreadManager class is a utility class that manages threads. It provides methods to 
add, start, stop, and check the status of threads. It also provides methods to get the
list of active threads and the status of a specific thread.
'''

import threading
import time
from typing import Dict, Set, List, Optional, Any
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.operation_tracker import track_operation, is_operation_completed, mark_operation_completed

logger = get_logger()

class ThreadState:
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class ManagedThread:
    def __init__(self, name: str, thread: threading.Thread, target: Any):
        self.name = name
        self.thread = thread
        self.target = target
        self.state = ThreadState.CREATED
        self.start_time: Optional[float] = None
        self.stop_time: Optional[float] = None
        self.error: Optional[Exception] = None

    def set_state(self, state: str):
        self.state = state
        if state == ThreadState.RUNNING:
            self.start_time = time.time()
        elif state in [ThreadState.STOPPED, ThreadState.ERROR]:
            self.stop_time = time.time()

    def get_runtime(self) -> Optional[float]:
        if self.start_time:
            end_time = self.stop_time if self.stop_time else time.time()
            return end_time - self.start_time
        return None

class ThreadManager:
    def __init__(self):
        self.threads: Dict[str, ManagedThread] = {}
        self.lock = threading.Lock()
        self.startup_threads: Set[str] = set()

    def register_startup_thread(self, name: str):
        """Register a thread name as a startup thread."""
        with self.lock:
            self.startup_threads.add(name)
            logger.info(f"Registered startup thread: {name}")

    def add_thread(self, name: str, target: Any, args: tuple = None):
        """Add a new thread to the manager."""
        with self.lock:
            # Check if this thread has already been created using operation tracking
            if is_operation_completed('thread_creation', name):
                logger.debug(f"Thread '{name}' already registered")
                if name in self.threads:
                    logger.warning(f"Thread '{name}' already exists. State: {self.threads[name].state}")
                    return
                
            # daemon=True: several background threads registered through
            # this manager block on genuinely uninterruptible calls (e.g.
            # input() for the CLI, socket.accept() for the 1553B bus
            # listeners) that no cooperative "running" flag can cancel while
            # blocked. Without daemon=True, those non-daemon threads being
            # merely abandoned by stop_thread()'s timeout (see stop_thread's
            # docstring) still keeps the whole interpreter -- and therefore
            # the process -- alive indefinitely after the main thread has
            # otherwise finished shutting down, defeating the timeout's
            # purpose. daemon=True guarantees the process can always exit
            # once the main thread is done, even for threads that can never
            # be cleanly joined.
            thread = threading.Thread(
                name=name,
                target=self._wrap_target(name, target),
                args=args if args else (),
                daemon=True,
            )
            managed_thread = ManagedThread(name, thread, target)
            self.threads[name] = managed_thread
            logger.info(f"Thread '{name}' added to ThreadManager. State: {managed_thread.state}")
            
            # Mark this thread as created
            mark_operation_completed('thread_creation', name)

    def _wrap_target(self, name: str, target: Any):
        """Wrap the thread target to track state and handle errors."""
        def wrapped_target(*args, **kwargs):
            managed_thread = self.threads.get(name)
            if not managed_thread:
                logger.error(f"No managed thread found for '{name}'")
                return

            try:
                managed_thread.set_state(ThreadState.RUNNING)
                logger.info(f"Thread '{name}' entering RUNNING state")
                result = target(*args, **kwargs)
                managed_thread.set_state(ThreadState.STOPPED)
                logger.info(f"Thread '{name}' completed successfully")
                return result
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                managed_thread.error = e
                managed_thread.set_state(ThreadState.ERROR)
                logger.error(f"Thread '{name}' failed with error: {str(e)}")
                # Store the traceback in the managed thread for inspection
                managed_thread.error_trace = error_trace
                raise
        return wrapped_target

    def start_thread(self, name: str) -> bool:
        """Start a thread with comprehensive state tracking."""
        with self.lock:
            managed_thread = self.threads.get(name)
            if not managed_thread:
                if name in self.startup_threads:
                    logger.debug(f"Startup thread '{name}' does not exist yet.")
                else:
                    logger.warning(f"No thread with the name '{name}' exists.")
                return False

            if managed_thread.thread.is_alive():
                return False

            try:
                managed_thread.set_state(ThreadState.STARTING)
                managed_thread.thread.start()
                logger.info(
                    f"Thread '{name}' started. "
                    f"State: {managed_thread.state}, "
                    f"Thread ID: {managed_thread.thread.ident}"
                )
                return True
            except Exception as e:
                managed_thread.error = e
                managed_thread.set_state(ThreadState.ERROR)
                logger.error(f"Error starting thread '{name}': {str(e)}")
                return False

    def stop_thread(self, name: str, timeout: float = 2.0):
        """Stop a thread with proper state management.

        `timeout` bounds the join so a single misbehaving/slow-to-exit
        thread can't hang the entire shutdown sequence forever. Several real
        cases of exactly that were found live: threads with no stop signal
        at all (an asyncio loop's run_forever() with nothing ever calling
        loop.stop()), a non-reentrant lock double-acquired on the same
        thread, and background loops blocking in a single uninterruptible
        time.sleep() lasting minutes. Those specific root causes are fixed
        at their source (see PLANNING.md), but a bounded join here is kept
        as defense-in-depth: it guarantees shutdown always completes in
        bounded time even if some other thread has a latent version of the
        same problem, rather than requiring every current and future
        background thread in the codebase to be defect-free.
        """
        with self.lock:
            managed_thread = self.threads.get(name)
            if not managed_thread:
                if name in self.startup_threads:
                    logger.debug(f"Startup thread '{name}' does not exist.")
                else:
                    logger.warning(f"No thread with the name '{name}' exists.")
                return

            if managed_thread.thread.is_alive():
                managed_thread.set_state(ThreadState.STOPPING)
                managed_thread.thread.join(timeout=timeout)
                if managed_thread.thread.is_alive():
                    # Thread did not exit within the grace period. Log it
                    # loudly and move on instead of hanging the rest of
                    # shutdown. Threads created via add_thread() are daemon
                    # threads (see add_thread()), so the process can still
                    # exit even if this one never finishes on its own; this
                    # also lets every OTHER component finish its own
                    # cleanup (sockets, etc.) instead of never getting the
                    # chance to run at all.
                    managed_thread.set_state(ThreadState.ERROR)
                    logger.error(
                        f"Thread '{name}' did not stop within {timeout:.1f}s "
                        f"timeout; giving up waiting and continuing shutdown. "
                        f"This thread may still be running."
                    )
                    return
                managed_thread.set_state(ThreadState.STOPPED)
                runtime = managed_thread.get_runtime()
                if runtime is not None:
                    logger.info(f"Thread '{name}' stopped. Runtime: {runtime:.2f}s")
                else:
                    logger.info(f"Thread '{name}' stopped.")
            else:
                logger.debug(f"Thread '{name}' is not running")

    def start_all_threads(self):
        for name in list(self.threads.keys()):
            self.start_thread(name)

    def stop_all_threads(self):
        """Stop all threads with proper cleanup."""
        logger.info("Stopping all threads...")
        for name in list(self.threads.keys()):
            self.stop_thread(name)
        logger.info("All threads stopped")

    def is_thread_alive(self, name: str) -> bool:
        """Check if a thread is alive with detailed state information."""
        with self.lock:
            managed_thread = self.threads.get(name)
            if not managed_thread:
                if name in self.startup_threads:
                    logger.debug(f"Startup thread '{name}' does not exist yet.")
                else:
                    logger.warning(f"No thread with the name '{name}' exists.")
                return False
            
            is_alive = managed_thread.thread.is_alive()
            runtime = managed_thread.get_runtime()
            runtime_str = f"{runtime:.2f}s" if runtime is not None else "N/A"
            logger.debug(
                f"Thread '{name}' status - "
                f"Alive: {is_alive}, "
                f"State: {managed_thread.state}, "
                f"Runtime: {runtime_str}"
            )
            return is_alive

    def get_active_threads(self) -> List[str]:
        """Get list of active threads with state information."""
        with self.lock:
            active_threads = [
                name for name, managed_thread in self.threads.items()
                if managed_thread.thread.is_alive()
            ]
            logger.debug(f"Active threads: {active_threads}")
            return active_threads

    def get_thread_status(self, name: str) -> str:
        """Get detailed thread status information."""
        with self.lock:
            managed_thread = self.threads.get(name)
            if not managed_thread:
                return f"Thread '{name}' does not exist"

            status = []
            status.append(f"Thread '{name}':")
            status.append(f"State: {managed_thread.state}")
            status.append(f"Running: {managed_thread.thread.is_alive()}")
            if managed_thread.thread.ident:
                status.append(f"Thread ID: {managed_thread.thread.ident}")
            runtime = managed_thread.get_runtime()
            if runtime is not None:
                status.append(f"Runtime: {runtime:.2f}s")
            if managed_thread.error:
                status.append(f"Error: {str(managed_thread.error)}")
            
            status_str = " | ".join(status)
            logger.debug(f"Thread status: {status_str}")
            return status_str

    def get_all_thread_states(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive state information for all threads."""
        with self.lock:
            states = {}
            for name, managed_thread in self.threads.items():
                states[name] = {
                    'state': managed_thread.state,
                    'alive': managed_thread.thread.is_alive(),
                    'thread_id': managed_thread.thread.ident,
                    'runtime': managed_thread.get_runtime(),
                    'error': str(managed_thread.error) if managed_thread.error else None
                }
            logger.debug(f"All thread states: {states}")
            return states

# Global instance of ThreadManager
thread_manager = ThreadManager()

# Global instance
_registered_threads_instance = None

class registered_threads:
    """Class to manage registered threads for startup management."""
    
    def __init__(self):
        self.init_complete = False
        self.registered_threads = set()

    @staticmethod
    def get_instance():
        """Get the singleton instance of registered_threads."""
        global _registered_threads_instance
        if _registered_threads_instance is None:
            _registered_threads_instance = registered_threads()
        return _registered_threads_instance

    def register_thread(self, name: str):
        """Register a thread for startup management."""
        self.registered_threads.add(name)

    def get_registered_threads(self) -> Set[str]:
        """Get the set of registered threads."""
        return self.registered_threads

    def clear_registered_threads(self):
        """Clear the set of registered threads."""
        self.registered_threads.clear()
        
    @staticmethod
    def register_known_threads(caller=None):
        """Register known threads for startup management.
        This static method can be called directly from the class or with a caller parameter."""
        
        def _register_threads_impl():
            instance = registered_threads.get_instance()
            
            # Register known startup threads
            thread_manager.register_startup_thread("Main_Loop")
            thread_manager.register_startup_thread("Event_Bus")
            
            # 1553B messaging threads
            thread_manager.register_startup_thread("BC Listener")
            thread_manager.register_startup_thread("BC Listening")
            thread_manager.register_startup_thread("RT Listener")
            thread_manager.register_startup_thread("RT Listening")
            thread_manager.register_startup_thread("ScheduleMessage")

            # User CLI threads
            thread_manager.register_startup_thread("UserCLI_Control")
            thread_manager.register_startup_thread("UserCLI_Input")
            thread_manager.register_startup_thread("UserCLI_Processing")
            thread_manager.register_startup_thread("UserCLI_Output")
            thread_manager.register_startup_thread("user_cli")

            # Async method threads
            thread_manager.register_startup_thread("AsyncMessageHandler")
            thread_manager.register_startup_thread("async_message_handler")
            thread_manager.register_startup_thread("ScheduleMessage")

            # System specific messenger threads
            thread_manager.register_startup_thread("RadarMessenger")
            thread_manager.register_startup_thread("DisplayMessenger")
            thread_manager.register_startup_thread("DisplayMessageProcessor")

            # System specific threads
            thread_manager.register_startup_thread("RadarManagement")
            thread_manager.register_startup_thread("RadarMain")
            thread_manager.register_startup_thread("WeatherRadar")

            # Monitor threads
            thread_manager.register_startup_thread("HealthMonitor")
            thread_manager.register_startup_thread("DatabaseMonitor")

            instance.init_complete = True
            logger.info("Known threads registered successfully")
            return True
            
        # Track this operation to ensure it only happens once
        return track_operation('thread_registration', 'global', _register_threads_impl)
