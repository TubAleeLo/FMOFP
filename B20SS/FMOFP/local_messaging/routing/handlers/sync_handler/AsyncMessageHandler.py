"""
Async Message Handler for Flight Management Operating Flight Program
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import asyncio
import queue
import socket
import threading
import traceback
import time
import uuid
from typing import Dict, Callable, List, Tuple, Optional
from FMOFP.MIL_STD_1553B.Messaging import send1553Msg
from FMOFP.local_messaging.command_word_map import validate_command_word
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class HandlerState:
    """Enumeration of AsyncMessageHandler states."""
    STOPPED = 0      # Not running, not processing messages
    STARTING = 1     # In the process of starting up
    RUNNING = 2      # Fully operational
    STOPPING = 3     # In the process of shutting down
    DEGRADED = 4     # Running but with reduced capacity
    
    @staticmethod
    def to_string(state: int) -> str:
        """Convert state integer to string representation."""
        states = {
            0: "STOPPED",
            1: "STARTING",
            2: "RUNNING",
            3: "STOPPING",
            4: "DEGRADED"
        }
        return states.get(state, f"UNKNOWN({state})")

class MessagePriority:
    """Priority levels for message processing."""
    HIGH = 0    # Critical system messages (mode changes, alerts)
    NORMAL = 1  # Standard operational messages
    LOW = 2     # Background or non-time-sensitive messages
    
    @staticmethod
    def get_priority(message: Dict) -> int:
        """Determine message priority based on content."""
        # Mode change messages get high priority
        if message.get('command_type') == 'mode_change' or message.get('message_type', '').endswith('ModeChangeRequest'):
            return MessagePriority.HIGH
            
        # Mode change completion messages get high priority
        if message.get('command_type') == 'mode_change_completion' or message.get('message_type', '').endswith('ModeChangeCompletion'):
            return MessagePriority.HIGH
            
        # Messages with 'alert' or 'warning' in type get high priority
        if any(urgent in str(message.get('message_type', '')).lower() for urgent in ['alert', 'warning', 'emergency']):
            return MessagePriority.HIGH
            
        # Default to normal priority
        return MessagePriority.NORMAL

class MessageBufferManager:
    """Thread-safe buffer for messages when handler is not ready."""
    
    def __init__(self):
        self._buffer = {
            MessagePriority.HIGH: [],
            MessagePriority.NORMAL: [],
            MessagePriority.LOW: []
        }
        self._lock = threading.Lock()
        self._size = 0
        self._last_flush_time = 0
        self._flush_interval = 5.0  # seconds
        
    def add_message(self, system_name: str, message: Dict, priority: int = None):
        """Add a message to the buffer with priority."""
        if priority is None:
            priority = MessagePriority.get_priority(message)

            # NOTE (production readiness re-analysis, August 2026): `request_id`
            # was referenced here without ever being extracted from `message`
            # -- found via `ruff check --select F821` (undefined-name). Every
            # call to add_message() with priority=None (the default) hit this
            # NameError immediately, before the buffer append below could ever
            # run, so this priority-buffering path had never actually worked.
            # Fixed to match the extraction convention used everywhere else in
            # this file (e.g. `request_id = message.get('request_id')` at the
            # two call sites in process_message()/process_message_sync()).
            request_id = message.get('request_id')
            if not request_id:
                raise ValueError("[ASYNC][BUFFER] No request_id found in message")
        with self._lock:
            self._buffer[priority].append((system_name, message))
            self._size += 1
            logger.debug(f"[BUFFER] Added message {message['message_id']} for {system_name} with priority {priority}")
            
    def get_all_messages(self) -> List[Tuple[str, Dict, int]]:
        """Get all buffered messages in priority order."""
        with self._lock:
            result = []
            # Get messages in priority order
            for priority in sorted(self._buffer.keys()):
                for system_name, message in self._buffer[priority]:
                    result.append((system_name, message, priority))
            
            # Clear buffer
            self._buffer = {
                MessagePriority.HIGH: [],
                MessagePriority.NORMAL: [],
                MessagePriority.LOW: []
            }
            old_size = self._size
            self._size = 0
            self._last_flush_time = time.time()
            
            if old_size > 0:
                logger.info(f"[BUFFER] Flushed {old_size} messages from buffer")
            return result
            
    def size(self) -> int:
        """Get the total size of the buffer."""
        with self._lock:
            return self._size
            
    def should_flush(self) -> bool:
        """Check if buffer should be flushed based on time or size."""
        current_time = time.time()
        with self._lock:
            # Don't flush if empty
            if self._size == 0:
                return False
                
            # Flush if buffer has been holding messages for too long
            if current_time - self._last_flush_time > self._flush_interval:
                return True
                
            # Flush if buffer is getting too large
            if self._size > 100:  # Arbitrary threshold
                return True
                
        return False

class PriorityQueue:
    """Thread-safe priority queue with retry tracking."""
    def __init__(self):
        self._queues = {
            MessagePriority.HIGH: queue.Queue(),
            MessagePriority.NORMAL: queue.Queue(),
            MessagePriority.LOW: queue.Queue()
        }
        self._retry_tracking = {}  # message_id -> (retry_count, last_attempt_time)
        self._lock = threading.Lock()
        self._size = 0
        
    def put(self, item: Tuple):
        """Put an item in the queue with priority.
        
        Handles both 2-value tuples (system_name, message) and 3-value tuples (system_name, message, priority).
        For 2-value tuples, priority is determined from the message content.
        """
        # Handle both 2-value and 3-value tuples
        if len(item) == 3:
            system_name, message, priority = item
            logger.info(f"[ASYNC][PRIORITY_Q] Received 3-value tuple with explicit priority {priority}")
        elif len(item) == 2:
            system_name, message = item
            # Determine priority from message content
            priority = MessagePriority.get_priority(message)
            logger.info(f"[ASYNC][PRIORITY_Q] Received 2-value tuple, determined priority {priority}")
        else:
            logger.error(f"[ASYNC][PRIORITY_Q] Invalid item format: expected 2 or 3 values, got {len(item)}")
            raise ValueError(f"[ASYNC][PRIORITY_Q] Invalid item format: expected 2 or 3 values, got {len(item)}")
        

            
        message_id = message['message_id']
        
        with self._lock:
            # Initialize retry tracking if new message
            if message_id not in self._retry_tracking:
                self._retry_tracking[message_id] = (0, time.time())
                
            # Add to appropriate queue
            self._queues[priority].put((system_name, message))
            self._size += 1
            logger.debug(f"[ASYNC][PRIORITY_Q] Added message {message_id} for {system_name} with priority {priority}")
            
    def get(self, timeout: Optional[float] = None) -> Optional[Tuple[str, Dict]]:
        """Get the highest priority item from the queue or None if timeout occurs."""
        start_time = time.time()
        
        while True:
            # Try to get from each queue in priority order
            for priority in sorted(self._queues.keys()):
                if priority is None:
                    continue
                
                # Check if the queue has items before attempting to get
                # This avoids raising queue.Empty exception
                if not self._queues[priority].empty():
                    item = self._queues[priority].get(block=False)
                    with self._lock:
                        self._size -= 1
                    return item
                # If this priority queue is empty, continue to next priority

            # If we get here, all queues are empty
            if timeout is None:
                # No timeout, just wait a bit and try again
                time.sleep(0.01)
            else:
                # With timeout, check if we should keep waiting
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    # Instead of raising an exception, return None quietly
                    # Don't log timeout as it causes excessive log spam
                    return None  # Caller must check for None
                time.sleep(min(0.01, remaining))
                
    def get_nowait(self) -> Optional[Tuple[str, Dict]]:
        """Get an item without blocking or None if queue is empty."""
        # Check if any queue has items
        for priority in sorted(self._queues.keys()):
            if priority is None:
                continue
                
            # Check if the queue has items before attempting to get
            if not self._queues[priority].empty():
                try:
                    item = self._queues[priority].get(block=False)
                    with self._lock:
                        self._size -= 1
                    return item
                except queue.Empty:
                    # This shouldn't happen since we checked, but handle it anyway
                    continue
                    
        # All queues are empty
        return None
        
    def task_done(self, message_id: str = None, success: bool = True):
        """Mark a task as done and clean up retry tracking."""
        with self._lock:
            if message_id and message_id in self._retry_tracking:
                if success:
                    # Remove from retry tracking on success
                    del self._retry_tracking[message_id]
                else:
                    # Update retry count on failure
                    retry_count, _ = self._retry_tracking[message_id]
                    self._retry_tracking[message_id] = (retry_count + 1, time.time())
            elif message_id is None:
                logger.error("[ASYNC][PRIORITY_Q]  task_done called without message_id")
                    
    def empty(self) -> bool:
        """Check if all queues are empty."""
        return self.qsize() == 0
        
    def qsize(self) -> int:
        """Get the total size of all queues."""
        with self._lock:
            return self._size
            
    def get_retry_candidates(self, max_retries: int = 3, retry_delay: float = 5.0) -> List[str]:
        """Get message IDs that should be retried based on retry policy."""
        candidates = []
        current_time = time.time()
        
        with self._lock:
            for message_id, (retry_count, last_attempt) in list(self._retry_tracking.items()):
                # Check if we've exceeded max retries
                if retry_count >= max_retries:
                    # Remove from tracking
                    del self._retry_tracking[message_id]
                    continue
                    
                # Check if enough time has passed for retry
                if current_time - last_attempt >= retry_delay:
                    candidates.append(message_id)
                    
        return candidates

class PeriodicTask:
    def __init__(self, func: Callable, interval: float):
        self.func = func
        self.interval = interval
        self.last_run = 0
        self.error_count = 0
        self.max_errors = 3

    def should_run(self, current_time: float) -> bool:
        return current_time - self.last_run >= self.interval

    def run(self, current_time: float) -> bool:
        try:
            self.func()
            self.last_run = current_time
            self.error_count = 0  # Reset error count on successful run
            return True
        except Exception as e:
            logger.error(f"Error in periodic task: {str(e)}")
            self.error_count += 1
            return False

    def should_disable(self) -> bool:
        return self.error_count >= self.max_errors

class SystemHandler:
    def __init__(self, system_name: str):
        self.system_name = system_name
        self.message_handlers: Dict[str, Callable] = {}
        self.periodic_tasks: List[PeriodicTask] = []
        self.active = True
        self._state_lock = threading.Lock()
        self._last_active_time = time.time()
        self._handler_states = {}  # Track handler states
        self._task_states = {}     # Track task states
        logger.info(f"SystemHandler created for {system_name}")

    def register_handler(self, command_word: str, handler: Callable):
        """Register message handler with state tracking."""
        try:
            with self._state_lock:
                # Check if handler for this command word is already registered
                if command_word in self.message_handlers:
                    # Silent skip if already registered
                    return
                    
                # If not already registered, proceed with registration
                self.message_handlers[command_word] = handler
                self._handler_states[command_word] = {
                    'registered_time': time.time(),
                    'last_used': None,
                    'error_count': 0,
                    'success_count': 0
                }
                logger.debug(f"[Async] Registered handler for command word {command_word} in {self.system_name}")
        except Exception as e:
            logger.error(f"[Async] Error registering handler for {command_word}: {str(e)}")
            raise

    def add_periodic_task(self, func: Callable, interval: float):
        """Add periodic task with state tracking."""
        try:
            with self._state_lock:
                task = PeriodicTask(func, interval)
                self.periodic_tasks.append(task)
                task_id = id(task)
                self._task_states[task_id] = {
                    'added_time': time.time(),
                    'last_run': None,
                    'run_count': 0,
                    'error_count': 0
                }
                logger.debug(f"[Async] Added periodic task with interval {interval}s to {self.system_name}")
        except Exception as e:
            logger.error(f"[Async] Error adding periodic task: {str(e)}")
            raise

    def update_handler_state(self, command_word: str, success: bool):
        """Update handler state after message processing."""
        try:
            with self._state_lock:
                if command_word in self._handler_states:
                    state = self._handler_states[command_word]
                    state['last_used'] = time.time()
                    if success:
                        state['success_count'] += 1
                    else:
                        state['error_count'] += 1
        except Exception as e:
            logger.error(f"[Async] Error updating handler state: {str(e)}")

    def update_task_state(self, task: PeriodicTask, success: bool):
        """Update task state after execution."""
        try:
            with self._state_lock:
                task_id = id(task)
                if task_id in self._task_states:
                    state = self._task_states[task_id]
                    state['last_run'] = time.time()
                    state['run_count'] += 1
                    if not success:
                        state['error_count'] += 1
        except Exception as e:
            logger.error(f"Error updating task state: {str(e)}")

    def get_system_state(self) -> Dict:
        """Get complete system state."""
        with self._state_lock:
            return {
                'system_name': self.system_name,
                'active': self.active,
                'last_active_time': self._last_active_time,
                'handler_states': self._handler_states.copy(),
                'task_states': self._task_states.copy(),
                'handler_count': len(self.message_handlers),
                'task_count': len(self.periodic_tasks)
            }

    def set_active(self, active: bool):
        """Safely update system active state."""
        with self._state_lock:
            old_state = self.active
            self.active = active
            self._last_active_time = time.time()
            logger.info(f"System {self.system_name} state changed: {old_state} -> {active}")

class AsyncMessageHandler:
    # Constants for retry and timeout handling
    MAX_RETRIES = 3
    RETRY_DELAY = 5.0  # seconds
    MESSAGE_TIMEOUT = 30.0  # seconds
    
    def __init__(self, num_workers: int = 4):
        # Add instance ID for tracking
        self._instance_id = id(self)
        
        # Replace simple queue with priority queue
        self.message_queue = PriorityQueue()
        
        # Add state management
        self._state = HandlerState.STOPPED
        self._state_lock = threading.Lock()
        self._state_transitions = []
        
        # Legacy state flags (for backward compatibility)
        self.workers = []
        self.running = False
        self.send_1553_msg = send1553Msg()
        self.num_workers = num_workers
        self.systems: Dict[str, SystemHandler] = {}
        self.periodic_task_thread = None
        self.executor = None
        self.started = False
        self.lock = threading.Lock()
        self._last_health_check = 0
        self._health_check_interval = 5.0  # seconds
        self._worker_ready_events = []  # Track worker readiness
        self._event_loop = asyncio.new_event_loop()  # Initialize event loop
        asyncio.set_event_loop(self._event_loop)  # Set as current event loop
        self.radar_db = None  # Will be set after initialization
        self._db_initialized = threading.Event()  # Track database initialization
        
        # Replace simple buffer list with buffer manager
        self._message_buffer = MessageBufferManager()
        
        # Add message tracking for timeouts and retries
        self._message_tracking = {}  # message_id -> (timestamp, system_name, priority, retry_count, message)
        self._pending_transactions = {}  # transaction_id -> (message_ids, completion_status)
        self._transaction_lock = threading.Lock()
        
        # Add watchdog thread for timeout handling
        self._watchdog_thread = None
        
        # Per-thread event loop tracking
        self._thread_loops = {}  # thread_id -> event_loop
        self._thread_loops_lock = threading.Lock()
        
        logger.info(f"[Async] AsyncMessageHandler instance {self._instance_id} initialized with {num_workers} workers")
    
    def _get_or_create_event_loop(self):
        """Get current thread's event loop or create a new one."""
        thread_id = threading.get_ident()
        
        with self._thread_loops_lock:
            # Check if we already have a loop for this thread
            if thread_id in self._thread_loops:
                loop = self._thread_loops[thread_id]
                # Verify the loop is still running
                if loop.is_running() or not loop.is_closed():
                    return loop
            
            # Create a new loop if needed
            try:
                # Try to get the current event loop
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Store the loop for this thread
            self._thread_loops[thread_id] = loop
            logger.info(f"[Async] Created new event loop for thread {thread_id}")
            return loop

    def set_radar_db(self, db):
        """Set the radar database and signal initialization"""
        self.radar_db = db
        self._db_initialized.set()
        logger.info("[Async] Radar database initialized")

    def register_system(self, system_name: str) -> SystemHandler:
        """Register a new system or return existing one."""
        with self.lock:
            if system_name not in self.systems:
                logger.info(f"[Async] Creating new SystemHandler for {system_name}")
                system = SystemHandler(system_name)
                self.systems[system_name] = system
                logger.info(f"[Async] Registered new system: {system_name}")
            else:
                system = self.systems[system_name]
                if not system.active:
                    logger.info(f"[Async] Reactivating system: {system_name}")
                    system.active = True
                
            return self.systems[system_name]

    def check_threads(self) -> Tuple[List[bool], bool]:
        """Check thread status and recover dead workers if needed."""
        with self.lock:
            # Check worker threads
            worker_statuses = []
            dead_workers = []
            for i, worker in enumerate(self.workers):
                is_alive = worker.is_alive()
                worker_statuses.append(is_alive)
                if not is_alive:
                    dead_workers.append(i)

            # Attempt recovery of dead workers
            if dead_workers:
                logger.warning(f"[Async] Found dead workers: {dead_workers}")
                self._recover_workers(dead_workers)

            # Check periodic task thread
            periodic_task_status = self.periodic_task_thread.is_alive() if self.periodic_task_thread else False
            if not periodic_task_status and self.running:
                logger.warning("[Async] Periodic task thread dead, attempting recovery")
                self._recover_periodic_task()
                
            # Check watchdog thread
            watchdog_status = self._watchdog_thread.is_alive() if self._watchdog_thread else False
            if not watchdog_status and self.running:
                logger.warning("[Async] Watchdog thread dead, attempting recovery")
                self._start_watchdog()

            return worker_statuses, periodic_task_status

    def _recover_workers(self, dead_indices: List[int]):
        """Recover dead worker threads."""
        try:
            logger.info(f"[Async] Attempting to recover workers: {dead_indices}")
            for i in dead_indices:
                # Remove dead worker
                if i < len(self.workers):
                    dead_worker = self.workers[i]
                    self.workers[i] = None  # Mark for replacement

                    # Create new worker
                    ready_event = threading.Event()
                    worker = threading.Thread(
                        target=self._process_messages,
                        name=f"[Async] AsyncMessageHandler_Worker_{i}_recovered",
                        args=(ready_event,),
                        daemon=False
                    )

                    # Start new worker
                    worker.start()
                    if not worker.is_alive():
                        logger.error(f"[Async] Failed to start recovered worker {i}")
                        continue

                    # Replace dead worker
                    self.workers[i] = worker
                    self._worker_ready_events[i] = ready_event

                    # Wait for worker to be ready
                    if not ready_event.wait(timeout=5.0):
                        logger.error(f"[Async] Recovered worker {i} failed to initialize")
                        continue

                    logger.info(f"[Async] Successfully recovered worker {i}")

            # Clean up any remaining dead workers
            self.workers = [w for w in self.workers if w is not None and w.is_alive()]
            self._worker_ready_events = self._worker_ready_events[:len(self.workers)]

        except Exception as e:
            logger.error(f"Error recovering workers: {e}")
            logger.error(traceback.format_exc())

    def _recover_periodic_task(self):
        """Recover periodic task thread."""
        try:
            logger.info("[Async] Attempting to recover periodic task thread")
            
            # Stop old thread if it exists
            if self.periodic_task_thread:
                self.periodic_task_thread.join(timeout=1.0)
            
            # Create and start new thread
            self.periodic_task_thread = threading.Thread(
                target=self._run_periodic_tasks,
                name="[Async] AsyncMessageHandler_PeriodicTasks_recovered",
                daemon=False  # Use non-daemon thread to prevent unexpected termination
            )
            self.periodic_task_thread.start()
            
            if not self.periodic_task_thread.is_alive():
                logger.error("[Async] Failed to recover periodic task thread")
                return False
                
            logger.info("[Async] Successfully recovered periodic task thread")
            return True
            
        except Exception as e:
            logger.error(f"[Async] Error recovering periodic task thread: {e}")
            logger.error(traceback.format_exc())
            return False

    def _set_state(self, new_state: int):
        """Safely set handler state with validation and recovery."""
        with self._state_lock:
            old_state = self._state
            
            # Store the last error for reference in state transitions
            last_error = getattr(self, '_last_error', None)
            
            # Define valid state transitions
            valid_transitions = {
                HandlerState.STOPPED: [HandlerState.STARTING],  # From STOPPED can only go to STARTING
                HandlerState.STARTING: [HandlerState.RUNNING, HandlerState.DEGRADED, HandlerState.STOPPED],  # STARTING can go to RUNNING, DEGRADED, or back to STOPPED on error
                HandlerState.RUNNING: [HandlerState.DEGRADED, HandlerState.STOPPING],  # RUNNING can go to DEGRADED or STOPPING
                HandlerState.DEGRADED: [HandlerState.RUNNING, HandlerState.STOPPING],  # DEGRADED can recover to RUNNING or go to STOPPING
                HandlerState.STOPPING: [HandlerState.STOPPED]   # STOPPING can only go to STOPPED
            }
            
            # Check if transition is valid
            if new_state not in valid_transitions.get(old_state, []):
                # Special case: Allow forced transition to STOPPING from any state
                if new_state == HandlerState.STOPPING:
                    logger.warning(f"[Async] Forcing transition from {HandlerState.to_string(old_state)} to STOPPING")
                # Special case: Allow forced transition to STOPPED from STARTING if startup failed
                elif old_state == HandlerState.STARTING and new_state == HandlerState.STOPPED:
                    logger.warning(f"[Async] Startup failed, forcing transition to STOPPED")
                # Special case: Prevent RUNNING -> STOPPED transition due to validation failures or connection errors
                elif old_state == HandlerState.RUNNING and new_state == HandlerState.STOPPED:
                    # Check if this is due to a validation failure
                    if hasattr(self, '_last_validation_error') and self._last_validation_error:
                        logger.warning(f"[Async] Preventing transition to STOPPED due to validation failure: {self._last_validation_error}")
                        # Set to DEGRADED instead
                        new_state = HandlerState.DEGRADED
                        logger.info(f"[Async] Redirecting to DEGRADED state instead")
                        # Reset the validation error flag
                        self._last_validation_error = None
                    # Check if this is due to a connection error
                    elif hasattr(self, '_last_error_type') and self._last_error_type == 'connection':
                        logger.warning(f"[Async] Preventing transition to STOPPED due to connection error: {getattr(self, '_last_error', None)}")
                        # Set to DEGRADED instead for connection errors
                        new_state = HandlerState.DEGRADED
                        logger.info(f"[Async] Redirecting to DEGRADED state instead for connection error")
                    else:
                        # Check worker health before allowing direct RUNNING -> STOPPED transition
                        worker_status = [w.is_alive() for w in self.workers]
                        active_workers = sum(1 for w in worker_status if w)
                        pending_messages = not self.message_queue.empty() or self._message_buffer.size() > 0
                        
                        if active_workers > 0 and pending_messages:
                            logger.warning(f"[Async] Preventing direct transition from {HandlerState.to_string(old_state)} to {HandlerState.to_string(new_state)} with {active_workers} active workers and pending messages")
                            # Force transition to STOPPING instead
                            new_state = HandlerState.STOPPING
                            logger.info(f"[Async] Redirecting to STOPPING state instead")
                else:
                    logger.warning(f"[Async] Invalid state transition from {HandlerState.to_string(old_state)} to {HandlerState.to_string(new_state)}")
                    # Log but allow transition to proceed - better to have an invalid transition than to block operation
            
            # Update state
            self._state = new_state
            
            # Update legacy state flags for backward compatibility
            if new_state == HandlerState.RUNNING:
                self.started = True
                self.running = True
            elif new_state == HandlerState.STARTING:
                self.started = True
                self.running = False
            elif new_state == HandlerState.STOPPING:
                self.started = True
                self.running = False
            elif new_state == HandlerState.STOPPED:
                self.started = False
                self.running = False
            elif new_state == HandlerState.DEGRADED:
                self.started = True
                self.running = True
            
            # Record transition
            transition_time = time.time()
            self._state_transitions.append((old_state, new_state, transition_time))
            logger.info(f"[Async] AsyncMessageHandler state transition: {HandlerState.to_string(old_state)} -> {HandlerState.to_string(new_state)} at {time.strftime('%H:%M:%S', time.localtime(transition_time))}")
            
            # State-specific actions
            if new_state == HandlerState.RUNNING:
                # Check and recover worker threads
                if old_state in [HandlerState.STOPPED, HandlerState.STARTING]:
                    # Full recovery needed
                    worker_status = [w.is_alive() for w in self.workers]
                    dead_workers = [i for i, alive in enumerate(worker_status) if not alive]
                    if dead_workers:
                        self._recover_workers(dead_workers)
                    if not self.periodic_task_thread or not self.periodic_task_thread.is_alive():
                        self._recover_periodic_task()
                    if not self._watchdog_thread or not self._watchdog_thread.is_alive():
                        self._start_watchdog()
                        
                # Check for degraded state
                if not all(w.is_alive() for w in self.workers):
                    # Some workers are dead, set to degraded
                    self._state = HandlerState.DEGRADED
                    logger.warning("[Async] Not all workers are alive, setting state to DEGRADED")
                    self._state_transitions.append((new_state, HandlerState.DEGRADED, time.time()))
                    
            elif new_state == HandlerState.STOPPING:
                # Flush any buffered messages with high priority
                buffer_size = self._message_buffer.size()
                if buffer_size > 0:
                    logger.info(f"[Async] Flushing {buffer_size} buffered messages before stopping")
                    self._flush_buffer_to_queue()
                    
            elif new_state == HandlerState.STOPPED:
                # Clean up any resources if needed
                pass
                
            elif new_state == HandlerState.DEGRADED:
                # Try to recover if possible
                logger.warning("[Async] Handler in DEGRADED state, attempting recovery")
                worker_status = [w.is_alive() for w in self.workers]
                dead_workers = [i for i, alive in enumerate(worker_status) if not alive]
                if dead_workers:
                    self._recover_workers(dead_workers)
            
            return True
            
    def _set_legacy_state(self, started: bool, running: bool):
        """Legacy method for backward compatibility."""
        if started and running:
            return self._set_state(HandlerState.RUNNING)
        elif started and not running:
            return self._set_state(HandlerState.STOPPING)
        else:
            return self._set_state(HandlerState.STOPPED)

    def _start_watchdog(self):
        """Start or restart the watchdog thread."""
        try:
            logger.info("[Async] Starting watchdog thread")
            
            # Stop old thread if it exists
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                logger.info("[Async] Stopping existing watchdog thread")
                # We can't really stop it, but we can let it die naturally
                
            # Create and start new thread
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                name="[Async] AsyncMessageHandler_Watchdog",
                daemon=False
            )
            self._watchdog_thread.start()
            
            if not self._watchdog_thread.is_alive():
                logger.error("[Async] Failed to start watchdog thread")
                return False
                
            logger.info("[Async] Successfully started watchdog thread")
            return True
            
        except Exception as e:
            logger.error(f"[Async] Error starting watchdog thread: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def _watchdog_loop(self):
        """Watchdog loop to check for timed out messages, retry failed messages, and monitor handler state."""
        try:
            logger.info("[Async] Watchdog thread started")
            
            # Track last state check time
            last_state_check = time.time()
            state_check_interval = 10.0  # Check state every 10 seconds
            
            while self.running:
                try:
                    current_time = time.time()
                    
                    # Check handler state periodically
                    if current_time - last_state_check > state_check_interval:
                        with self._state_lock:
                            current_state = self._state
                            
                            # If we're in DEGRADED state, attempt recovery
                            if current_state == HandlerState.DEGRADED:
                                logger.info("[Async] Watchdog detected DEGRADED state, attempting recovery")
                                
                                # Check worker threads
                                worker_status = [w.is_alive() for w in self.workers]
                                dead_workers = [i for i, alive in enumerate(worker_status) if not alive]
                                
                                if dead_workers:
                                    logger.info(f"[Async] Watchdog attempting to recover {len(dead_workers)} dead workers")
                                    self._recover_workers(dead_workers)
                                    
                                    # Check if recovery was successful
                                    if all(w.is_alive() for w in self.workers):
                                        logger.info("[Async] Watchdog successfully recovered all workers, transitioning to RUNNING state")
                                        self._set_state(HandlerState.RUNNING)
                                
                            # Check if buffer should be flushed
                            if self._message_buffer.should_flush() and current_state in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                                logger.info("[Async] Watchdog detected buffered messages, flushing to queue")
                                self._flush_buffer_to_queue()
                                
                        last_state_check = current_time
                    
                    # Check for timed out messages
                    with self._transaction_lock:
                        timed_out_messages = []
                        for message_id, (timestamp, system_name, priority, retry_count, message) in list(self._message_tracking.items()):
                            if current_time - timestamp > self.MESSAGE_TIMEOUT:
                                timed_out_messages.append((message_id, system_name, priority, retry_count, message))
                                
                        # Handle timed out messages
                        for message_id, system_name, priority, retry_count, message in timed_out_messages:
                            logger.warning(f"[Async] Message {message_id} for {system_name} timed out after {self.MESSAGE_TIMEOUT}s")
                            
                            # Check if we should retry based on priority and state
                            should_retry = (
                                priority == MessagePriority.HIGH or  # Always retry high priority messages
                                (self._state in [HandlerState.RUNNING, HandlerState.DEGRADED] and  # Only retry normal/low priority in good states
                                 priority == MessagePriority.NORMAL)
                            )
                            
                            if should_retry and retry_count < self.MAX_RETRIES:
                                logger.info(f"[Async] Retrying timed out message {message_id} (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                                
                                # Update retry count in tracking
                                self._message_tracking[message_id] = (current_time, system_name, priority, retry_count + 1, message)
                                
                                # Requeue the message with original content but updated retry count
                                try:
                                    # Validate message before requeuing
                                    if self._validate_message(system_name, message):
                                        # Add to queue with high priority to ensure it gets processed quickly
                                        self.message_queue.put((system_name, message, MessagePriority.HIGH))
                                        logger.info(f"[Async] Requeued message {message_id} for {system_name}")
                                    else:
                                        logger.warning(f"[Async] Failed to requeue invalid message {message_id} for {system_name}")
                                        # Remove from tracking since we can't requeue it
                                        del self._message_tracking[message_id]
                                except Exception as e:
                                    logger.error(f"[Async] Error requeuing message {message_id}: {e}")
                                    # Keep in tracking for potential future retry
                            else:
                                # Remove from tracking
                                if message_id in self._message_tracking:
                                    del self._message_tracking[message_id]
                                    logger.warning(f"[Async] Giving up on message {message_id} after {retry_count} attempts")
                                
                    # Check for messages that need to be retried from the queue's retry tracking
                    retry_candidates = self.message_queue.get_retry_candidates(
                        max_retries=self.MAX_RETRIES,
                        retry_delay=self.RETRY_DELAY
                    )
                    
                    if retry_candidates:
                        logger.info(f"[Async] Found {len(retry_candidates)} messages to retry from queue tracking")
                        
                        # Process each retry candidate
                        for message_id in retry_candidates:
                            # Check if we have the message in our tracking
                            with self._transaction_lock:
                                if message_id in self._message_tracking:
                                    timestamp, system_name, priority, retry_count, message = self._message_tracking[message_id]
                                    
                                    # Update retry count
                                    self._message_tracking[message_id] = (current_time, system_name, priority, retry_count + 1, message)
                                    
                                    # Requeue the message
                                    try:
                                        # Validate message before requeuing
                                        if self._validate_message(system_name, message):
                                            # Add to queue with high priority to ensure it gets processed quickly
                                            self.message_queue.put((system_name, message, MessagePriority.HIGH))
                                            logger.info(f"[Async] Requeued message {message_id} for {system_name} from queue tracking")
                                        else:
                                            logger.warning(f"[Async] Failed to requeue invalid message {message_id} for {system_name}")
                                            # Remove from tracking since we can't requeue it
                                            del self._message_tracking[message_id]
                                    except Exception as e:
                                        logger.error(f"[Async] Error requeuing message {message_id} from queue tracking: {e}")
                        
                    # Sleep to avoid high CPU usage
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"[Async] Error in watchdog loop: {e}")
                    logger.error(traceback.format_exc())
                    time.sleep(0.1)  # Longer sleep on error
                    
        except Exception as e:
            logger.error(f"[Async] Fatal error in watchdog thread: {e}")
            logger.error(traceback.format_exc())
            
            # Try to recover by setting state to DEGRADED
            try:
                with self._state_lock:
                    if self._state == HandlerState.RUNNING:
                        logger.warning("[Async] Watchdog thread died, setting state to DEGRADED")
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
            except Exception:
                logger.debug("[Async] Watchdog: failed to update handler state", exc_info=True)

    def start(self):
        with self.lock:
            # Log initial state
            logger.info(f"[Async] Starting AsyncMessageHandler. Current state: started={self.started}, running={self.running}, state={HandlerState.to_string(self._state)}")
            
            # Handle inconsistent state
            if self.started and self._state == HandlerState.STOPPED:
                logger.warning("[Async] AsyncMessageHandler in inconsistent state (STOPPED but started=True). Forcing transition to STARTING.")
                self._set_state(HandlerState.STARTING)
                
            # If already started but not running, ensure proper state transition
            elif self.started and not self.running:
                logger.warning("[Async] AsyncMessageHandler started but not running. Ensuring proper state transition.")
                self._set_state(HandlerState.STARTING)
                
            elif self.started and self.running:
                logger.info("[Async] AsyncMessageHandler is already started and running")
                return

            try:
                # Initialize ThreadPoolExecutor
                self.executor = ThreadPoolExecutor(max_workers=self.num_workers)
                logger.debug("[Async] ThreadPoolExecutor initialized")

                # Set state with logging
                self._set_state(HandlerState.STARTING)

                # _set_state(STARTING) sets self.running = False (see the
                # HandlerState.STARTING branch in _set_state). But every
                # worker thread (_process_messages) and the periodic task
                # thread (_run_periodic_tasks) gate their entire run loop on
                # `while self.running:`, and both are started below, before
                # _set_state(HandlerState.RUNNING) runs at the end of this
                # method. So each thread's very first loop check sees
                # self.running == False and returns immediately -- confirmed
                # live: the periodic task thread logs "Periodic task runner
                # started" and then exits before start() finishes checking
                # is_alive(), producing "Error starting AsyncMessageHandler:
                # Failed to start periodic task thread" on every boot.
                # Worker threads have the same bug but usually win the race
                # since they do more setup work (creating an asyncio event
                # loop, signalling their ready_event) before reaching their
                # while check -- they are just as likely to die right after.
                # self.running is the low-level "keep the thread's loop
                # alive" switch; the loop bodies already separately check
                # self._state for RUNNING/DEGRADED before doing real work
                # and just idle-sleep otherwise (see _process_messages), so
                # it's safe to flip this on now, before any thread that
                # depends on it is created (production readiness deep dive,
                # found via live full-system-boot testing).
                self.running = True
                
                # Start worker threads
                logger.info("[Async] Starting worker threads...")
                for i in range(self.num_workers):
                    ready_event = threading.Event()
                    self._worker_ready_events.append(ready_event)
                    
                    worker = threading.Thread(
                        target=self._process_messages,
                        name=f"AsyncMessageHandler_Worker_{i}",
                        args=(ready_event,),
                        daemon=False  # Use non-daemon thread to prevent unexpected termination
                    )
                    self.workers.append(worker)  # Add to list before starting
                    worker.start()
                    
                    # Verify thread started
                    if not worker.is_alive():
                        self._set_state(HandlerState.STOPPED)
                        raise RuntimeError(f"Failed to start worker thread {i}")
                    logger.info(f"[Async] Started worker thread {i}")
                
                # Wait for all workers to be ready
                for i, event in enumerate(self._worker_ready_events):
                    if not event.wait(timeout=5.0):  # 5 second timeout
                        self._set_state(HandlerState.STOPPED)
                        raise RuntimeError(f"Worker thread {i} failed to initialize")

                # Start periodic task thread
                logger.info("[Async] Starting periodic task thread...")
                self.periodic_task_thread = threading.Thread(
                    target=self._run_periodic_tasks,
                    name="AsyncMessageHandler_PeriodicTasks",
                    daemon=False  # Use non-daemon thread to prevent unexpected termination
                )
                self.periodic_task_thread.start()
                
                # Verify periodic task thread
                if not self.periodic_task_thread.is_alive():
                    self._set_state(HandlerState.STOPPED)
                    raise RuntimeError("Failed to start periodic task thread")
                    
                # Set state to RUNNING after all threads are started
                self._set_state(HandlerState.RUNNING)
                
                logger.info("[Async] Started periodic task thread")
                
                # Start watchdog thread
                self._start_watchdog()
                
                logger.info(f"[Async] Started {self.num_workers} worker threads")
                
                # Process any buffered messages
                buffer_size = self._message_buffer.size()
                if buffer_size > 0:
                    logger.info(f"[Async] Processing {buffer_size} buffered messages")
                    
                    # Get all buffered messages in priority order
                    buffered_messages = self._message_buffer.get_all_messages()
                    
                    # Process each buffered message
                    for system_name, message, priority in buffered_messages:
                        try:
                            logger.info(f"[Async] Processing buffered message for {system_name} with priority {priority}")
                            self.add_message(system_name, message)
                        except Exception as e:
                            logger.error(f"[Async] Error processing buffered message: {e}")
                            logger.error(traceback.format_exc())
                    
                    logger.info(f"[Async] Finished processing buffered messages")
            except Exception as e:
                logger.error(f"[Async] Error starting AsyncMessageHandler: {str(e)}")
                self.stop()
                raise

    def stop(self):
        with self.lock:
            if not self.started:
                logger.warning("[Async] AsyncMessageHandler is not running")
                return

            try:
                logger.info("[Async] Stopping AsyncMessageHandler")
                
                # First set state to STOPPING
                self._set_state(HandlerState.STOPPING)
                
                # Process any remaining messages synchronously
                while not self.message_queue.empty():
                    try:
                        system_name, message = self.message_queue.get_nowait()
                        # Process message synchronously
                        if system_name in self.systems:
                            command_word = message.get('command_word')
                            if command_word:
                                handler = self.systems[system_name].message_handlers.get(command_word)
                                if handler:
                                    try:
                                        if asyncio.iscoroutinefunction(handler):
                                            loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(loop)
                                            loop.run_until_complete(handler(message))
                                            loop.close()
                                        else:
                                            handler(message)
                                    except Exception as e:
                                        logger.error(f"Error in final message handler: {str(e)}")
                    except queue.Empty:
                        break
                    except Exception as e:
                        logger.error(f"[Async] Error processing final message: {str(e)}")
                
                # Keep in STOPPING state while cleaning up threads
                self._set_state(HandlerState.STOPPING)
                
                # Stop worker threads
                for worker in self.workers:
                    worker.join(timeout=2.0)
                self.workers.clear()
                self._worker_ready_events.clear()
                
                # Stop periodic task thread
                if self.periodic_task_thread:
                    self.periodic_task_thread.join(timeout=2.0)
                    self.periodic_task_thread = None
                    
                # Stop watchdog thread
                if self._watchdog_thread:
                    self._watchdog_thread.join(timeout=2.0)
                    self._watchdog_thread = None
                
                # Shutdown executor
                if self.executor:
                    self.executor.shutdown(wait=True)
                    self.executor = None
                
                # Finally set state to STOPPED after cleanup
                self._set_state(HandlerState.STOPPED)
                
                logger.info("[Async] AsyncMessageHandler stopped successfully")
                logger.info("[Async] State transition history:")
                for old, new, timestamp in self._state_transitions[-5:]:  # Show last 5 transitions
                    logger.info(f"[Async]   {time.strftime('%H:%M:%S', time.localtime(timestamp))}: {old} -> {new}")
            except Exception as e:
                logger.error(f"[Async] Error stopping AsyncMessageHandler: {str(e)}")
                # Ensure we set state to STOPPED even on error
                self._set_state(HandlerState.STOPPED)
                raise

    def add_message(self, system_name: str, message: Dict):
        """Add a message to the processing queue (synchronous version)."""
        try:
            # Log detailed state at message addition attempt
            logger.info(f"[ASYNC_MSG] Attempting to add message for {system_name}")
            with self._state_lock:
                current_state = self._state
                logger.info(f"[ASYNC_MSG] AsyncMessageHandler instance {self._instance_id} state: {HandlerState.to_string(current_state)}")
                logger.info(f"[ASYNC_MSG] Message queue size: {self.message_queue.qsize()}")
                logger.info(f"[ASYNC_MSG] Active workers: {sum(1 for w in self.workers if w.is_alive())}/{len(self.workers)}")

                # Buffer messages if handler is not in RUNNING or DEGRADED state
                if self._state not in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                    logger.warning(f"[ASYNC_MSG] AsyncMessageHandler instance {self._instance_id} in {HandlerState.to_string(self._state)} state. Buffering message for {system_name}")
                    
                    # Determine message priority - high priority for messages during STOPPING state
                    if self._state == HandlerState.STOPPING:
                        priority = MessagePriority.HIGH  # Prioritize messages during shutdown
                    else:
                        priority = MessagePriority.get_priority(message)
                    
                    # Add to buffer manager
                    self._message_buffer.add_message(system_name, message, priority)
                    logger.info(f"[ASYNC_MSG] Message buffered. Buffer size: {self._message_buffer.size()}")
                    
                    # Always try to restart if in STOPPED state
                    if self._state == HandlerState.STOPPED:
                        logger.warning("[ASYNC_MSG] AsyncMessageHandler in STOPPED state. Attempting to restart...")
                        try:
                            # Start in a separate thread to avoid blocking
                            restart_thread = threading.Thread(
                                target=self.start,
                                name="AsyncMessageHandler_Restart",
                                daemon=False  # Use non-daemon thread to prevent unexpected termination
                            )
                            restart_thread.start()
                            
                            # Wait briefly for restart to begin
                            restart_thread.join(timeout=0.5)
                            
                            logger.info("[ASYNC_MSG] AsyncMessageHandler restart initiated")
                            
                            # Wait for state to change from STOPPED
                            for _ in range(10):  # Try for 1 second
                                if self._state != HandlerState.STOPPED:
                                    logger.info(f"[ASYNC_MSG] AsyncMessageHandler state changed to {HandlerState.to_string(self._state)}")
                                    break
                                time.sleep(0.1)
                            else:
                                logger.warning("[ASYNC_MSG] AsyncMessageHandler failed to change state from STOPPED within timeout")
                        except Exception as e:
                            logger.error(f"[ASYNC_MSG] Failed to restart AsyncMessageHandler: {e}")
                            logger.error(traceback.format_exc())
                    elif self._state == HandlerState.STARTING:
                        logger.info("[ASYNC_MSG] Handler is starting, message will be processed when ready")
                    elif self._state == HandlerState.STOPPING:
                        logger.warning("[ASYNC_MSG] Handler is stopping, message may be delayed")
                    
                    return

            # Determine message priority
            priority = MessagePriority.get_priority(message)
            
            # NOTE: message_id was previously accessed directly via
            # message['message_id'], but every real call site in the
            # codebase (send_radar_message() in weather_radar_messages.py,
            # and all 11 call sites in RadarMessageHandler.py for TFR/SAR/
            # targeting/AEWC/weather-shear/weather-turbulence updates) builds
            # its message dict without one. Confirmed live: this raised
            # "KeyError: 'message_id'" every time add_message() was called
            # while the handler was RUNNING (the normal operating state) -
            # the early-return buffering path when the handler isn't
            # RUNNING/DEGRADED masked this during typical passive testing,
            # since that path returns before reaching this line. message_id
            # is only used internally here for timeout/retry bookkeeping
            # (_message_tracking), not as something callers need to supply
            # semantically, so generate one when missing rather than
            # requiring every call site to be updated.
            if 'message_id' not in message:
                message['message_id'] = str(uuid.uuid4())
            message_id = message['message_id']
            
            # Track message for timeout and retry (including full message for retry)
            with self._transaction_lock:
                self._message_tracking[message_id] = (time.time(), system_name, priority, 0, message.copy())

            # Validate message before adding to queue
            try:
                if not self._validate_message(system_name, message):
                    logger.error(f"[ASYNC_MSG] Message validation failed for system {system_name}")
                    logger.error(f"[ASYNC_MSG] Message content: {message}")
                    # Store validation error for state management
                    self._last_validation_error = f"Validation failed for {system_name} message: {message.get('message_id', None)}"
                    return
            except Exception as validation_error:
                # Store validation error for state management
                error_msg = str(validation_error)
                logger.error(f"[ASYNC_MSG] Validation exception: {error_msg}")
                self._last_validation_error = f"Validation exception: {error_msg}"
                return

            # Add to queue if validation passes
            self.message_queue.put((system_name, message, priority))
            logger.info(f"[ASYNC_MSG] Successfully added message for system {system_name} with priority {priority}")
            logger.debug(f"[ASYNC_MSG] New queue size: {self.message_queue.qsize()}")
        except Exception as e:
            logger.error(f"[ASYNC_MSG] Error adding message: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _flush_buffer_to_queue(self):
        """Flush buffered messages to the queue."""
        try:
            # Check state before flushing
            with self._state_lock:
                current_state = self._state
                if current_state not in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                    logger.warning(f"[Async] Cannot flush buffer in {HandlerState.to_string(current_state)} state")
                    
                    # If in STOPPED state, try to restart
                    if current_state == HandlerState.STOPPED:
                        logger.warning("[Async] AsyncMessageHandler in STOPPED state. Attempting to restart before flushing...")
                        try:
                            # Set state to STARTING
                            self._set_state(HandlerState.STARTING)
                            
                            # Start in a separate thread to avoid blocking
                            restart_thread = threading.Thread(
                                target=self.start,
                                name="AsyncMessageHandler_Restart_Flush",
                                daemon=False  # Use non-daemon thread to prevent unexpected termination
                            )
                            restart_thread.start()
                            
                            # Wait briefly for restart to begin
                            restart_thread.join(timeout=0.5)
                            
                            logger.info("[Async] AsyncMessageHandler restart initiated before flushing")
                            
                            # Wait for state to change to RUNNING or DEGRADED
                            for _ in range(20):  # Try for 2 seconds
                                if self._state in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                                    logger.info(f"[Async] AsyncMessageHandler state changed to {HandlerState.to_string(self._state)}")
                                    break
                                time.sleep(0.1)
                            else:
                                logger.warning("[Async] AsyncMessageHandler failed to reach RUNNING or DEGRADED state within timeout")
                                return  # Don't flush if we couldn't restart
                        except Exception as e:
                            logger.error(f"[Async] Failed to restart AsyncMessageHandler before flushing: {e}")
                            logger.error(traceback.format_exc())
                            return  # Don't flush if restart failed
                    else:
                        return  # Don't flush in other states
            
            # Get all buffered messages
            buffered_messages = self._message_buffer.get_all_messages()
            
            if not buffered_messages:
                return
                
            logger.info(f"[Async] Flushing {len(buffered_messages)} buffered messages to queue")
            
            # Add each message to the queue
            for system_name, message, priority in buffered_messages:
                try:
                    # Validate message before adding to queue
                    if self._validate_message(system_name, message):
                        # Add to queue
                        self.message_queue.put((system_name, message, priority))
                        logger.debug(f"[Async] Flushed buffered message {message.get('message_id')} to queue")
                    else:
                        logger.warning(f"[Async] Discarding invalid buffered message for {system_name}")
                except Exception as e:
                    logger.error(f"[Async] Error flushing buffered message: {str(e)}")
                    
            logger.info(f"[Async] Finished flushing buffered messages")
            
        except Exception as e:
            logger.error(f"[Async] Error in buffer flush: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _validate_message(self, system_name: str, message: Dict) -> bool:
        """Validate message before processing."""
        try:
            # Handling for status words
            if 'status_word' in message or message.get('message_type') == 'status_word' or (
                isinstance(message.get('command_word'), str) and 
                message.get('command_word').startswith('100')):  # Status words start with 100
                
                # Extract RT address to determine system
                rt_address = message.get('rt_address')
                
                # For display system status words (RT address 11)
                if rt_address == 11 and system_name == 'display':
                    logger.info(f"[Async] Processing display system status word message: {message.get('message_id', None)}")
                    return True  # Skip command word validation for display status words
                
                # For radar system status words (RT address 9)
                elif rt_address == 9 and system_name == 'radar':
                    logger.info(f"[Async] Processing radar system status word message: {message.get('message_id', None)}")
                    return True  # Skip command word validation for radar status words
                
                # Misrouted status word
                elif rt_address == 11 and system_name == 'radar':
                    logger.warning(f"[Async] Display status word (RT=11) incorrectly routed to radar system")
                    return False
                elif rt_address == 9 and system_name == 'display':
                    logger.warning(f"[Async] Radar status word (RT=9) incorrectly routed to display system")
                    return False

            # Check if we have a database connection - only for radar systems
            # Skip database check for display systems and other non-radar systems
            if system_name == 'radar' and (not hasattr(self, 'radar_db') or self.radar_db is None):
                # Instead of failing, try to get the radar_db from the system manager
                try:
                    from FMOFP.storage.DBM import DatabaseManager
                    from FMOFP.core.system_manager import get_system_manager
                    
                    # Get the system manager
                    system_manager = get_system_manager()
                    
                    # Get the database manager
                    db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                    
                    # Get the radar database
                    radar_db = db_manager.get_system_db('radar_management')
                    
                    # Set the radar_db on this instance
                    self.radar_db = radar_db
                    
                    # Signal that the database is initialized
                    if hasattr(self, '_db_initialized'):
                        self._db_initialized.set()
                    
                    logger.info("[Async] Successfully initialized radar_db from system manager")
                except Exception as e:
                    logger.error(f"[Async] Failed to get radar_db from system manager: {e}")
                    logger.error("[Async] No radar database connection available - cannot process radar messages")
                    return False
                
            # For display systems, we don't need to check radar_db
            # This allows display messages to be processed even if radar_db is not set

            # Check command word exists
            command_word = message.get('command_word')
            if not command_word:
                logger.error(f"[Async] Message missing command word for system {system_name}")
                return False

            # Auto-register system if it doesn't exist
            if system_name not in self.systems:
                logger.info(f"[Async] Auto-registering system: {system_name}")
                self.register_system(system_name)

            # Get system after potential registration
            system = self.systems[system_name]
            if not system.active:
                logger.warning(f"[Async] System {system_name} is inactive")
                return False

            # Validate command word format
            try:
                validate_command_word(command_word)
            except ValueError as e:
                logger.error(f"[Async] Invalid command word format: {e}")
                return False

            return True
        except Exception as e:
            logger.error(f"[Async] Error validating message: {e}")
            return False


    def _process_messages(self, ready_event: threading.Event):
        """Process messages from the queue with state awareness."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            thread_name = threading.current_thread().name
            thread_id = threading.get_ident()
            logger.info(f"[Async] Message processor starting: {thread_name} (thread ID: {thread_id})")
            logger.info(f"[Async] Thread state: alive={threading.current_thread().is_alive()}")
            
            # Track worker state
            worker_state = {
                'processed_count': 0,
                'error_count': 0,
                'last_message_time': None,
                'last_error_time': None,
                'consecutive_errors': 0,
                'connection_errors': 0  # Track connection-specific errors
            }
            
            # Set max consecutive errors before backing off
            max_consecutive_errors = 3
            error_backoff_time = 1.0  # seconds
            
            ready_event.set()  # Signal thread is ready
            logger.info(f"[Async] Ready event set for {thread_name}")
            
            while self.running:
                try:
                    # Check handler state
                    with self._state_lock:
                        current_state = self._state
                        
                    # Check if buffer should be flushed regardless of state
                    if self._message_buffer.should_flush():
                        logger.info("[Async] Buffer needs flushing, processing now")
                        self._flush_buffer_to_queue()
                        
                    # Only process messages if in RUNNING or DEGRADED state
                    if current_state not in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                        # If stopping, try to process high priority messages only
                        if current_state == HandlerState.STOPPING:
                            try:
                                # Try to get a high priority message with a short timeout
                                system_name, message = self._get_high_priority_message(timeout=0.1)
                                logger.info(f"[Async] Processing high priority message during STOPPING state")
                                # Process the high priority message
                                self._process_single_message(system_name, message, loop, worker_state)
                            except queue.Empty:
                                # No high priority messages, sleep briefly
                                time.sleep(0.1)
                        else:
                            # If in STOPPED state but we have buffered messages, try to transition to RUNNING
                            if current_state == HandlerState.STOPPED and self._message_buffer.size() > 0:
                                logger.warning("[Async] In STOPPED state with buffered messages, attempting recovery")
                                with self._state_lock:
                                    self._set_state(HandlerState.STARTING)
                                    self._set_state(HandlerState.RUNNING)
                            # In other states, just sleep
                            time.sleep(0.5)
                            continue
                    
                    # Check if buffer should be flushed
                    if self._message_buffer.should_flush():
                        self._flush_buffer_to_queue()
                    
                    # Back off if we've had too many consecutive errors
                    if worker_state['consecutive_errors'] >= max_consecutive_errors:
                        logger.warning(f"[Async] Worker {thread_name} backing off after {worker_state['consecutive_errors']} consecutive errors")
                        time.sleep(error_backoff_time)
                        # Increase backoff time for next error, up to a maximum
                        error_backoff_time = min(error_backoff_time * 2, 10.0)
                    else:
                        # Reset backoff time if we're not in error state
                        error_backoff_time = 1.0
                    
                    try:
                        # Use timeout to prevent thread from blocking forever
                        item = self.message_queue.get(timeout=1.0)
                        
                        # Check if we got None from the timeout
                        if item is None:
                            # This is normal for timeout, just continue to next iteration
                            # No need to log this as it creates log spam during normal operation
                            continue
                            
                        # Handle different item formats
                        if isinstance(item, tuple) and len(item) >= 2:
                            # If item is a tuple with at least 2 elements, unpack it
                            system_name, message = item[0], item[1]
                            logger.info(f"[Async] Processing tuple message for system: {system_name}")
                        elif isinstance(item, str):
                            # If item is a string, it's likely a system name without a message
                            logger.error(f"[Async] Received system name without message: {item}")
                            continue
                        else:
                            # For any other format, log an error and continue
                            logger.error(f"[Async] Invalid item format from queue: {type(item).__name__}")
                            continue
                        
                        # Process the message with the extracted system_name and message
                        # Pass system_name and message as separate arguments, not as a tuple
                        self._process_single_message(system_name, message, loop, worker_state)
                        
                    except queue.Empty:
                        # Queue is empty, just continue waiting
                        continue
                except Exception as e:
                    logger.error(f"[Async] Error in message processing loop: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Update error stats
                    worker_state['error_count'] += 1
                    worker_state['last_error_time'] = time.time()
                    worker_state['consecutive_errors'] += 1
                    
                    # Don't exit the loop on error, but sleep briefly
                    time.sleep(0.5)
                    continue
        # Add specific handling for connection-related errors
        except (socket.error, ConnectionError, BrokenPipeError) as conn_err:
            logger.warning(f"[Async] Connection error in worker thread {thread_name}: {str(conn_err)}")
            logger.warning(traceback.format_exc())
            ready_event.set()  # Ensure event is set even on error
            
            # Don't die - implement circuit breaker pattern
            try:
                # Log the error but continue processing
                logger.warning(f"[Async] Worker thread encountered connection error, implementing circuit breaker")
                
                # Store connection error type for state management
                with self._state_lock:
                    self._last_error_type = 'connection'
                    self._last_error = str(conn_err)
                
                # Sleep briefly to prevent tight error loops
                time.sleep(1.0)
                
                # Instead of dying, restart the processing loop
                logger.info(f"[Async] Worker thread {thread_name} restarting after connection error")
                
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Reset worker state but preserve error counts
                worker_state['connection_errors'] += 1
                worker_state['last_error_time'] = time.time()
                
                # Continue processing instead of dying
                # This prevents cascading failures
                return self._process_messages(ready_event)  # Restart the processing function
                
            except Exception as circuit_breaker_error:
                # Only if the circuit breaker itself fails, then degrade
                logger.error(f"[Async] Circuit breaker failed: {circuit_breaker_error}")
                with self._state_lock:
                    if self._state == HandlerState.RUNNING:
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
        except Exception as e:
            logger.error(f"[Async] Fatal error in message processor: {str(e)}")
            logger.error(traceback.format_exc())
            ready_event.set()  # Ensure event is set even on error
            
            # Try to update handler state
            try:
                with self._state_lock:
                    self._last_error_type = 'general'
                    self._last_error = str(e)
                    if self._state == HandlerState.RUNNING:
                        logger.warning(f"[Async] Worker thread {thread_name} died, setting state to DEGRADED")
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
            except Exception:
                logger.debug("[Async] Worker: failed to update handler state", exc_info=True)
        finally:
            try:
                loop.close()
            except Exception as e:
                logger.error(f"[Async] Error closing event loop: {str(e)}")
                
    def _get_high_priority_message(self, timeout: float = 0.1) -> Optional[Tuple[str, Dict]]:
        """Get only high priority messages from the queue or None if empty."""
        # Check if high priority queue has items before attempting to get
        # This avoids raising queue.Empty exception
        if not self.message_queue._queues[MessagePriority.HIGH].empty():
            try:
                item = self.message_queue._queues[MessagePriority.HIGH].get(block=False)
                with self.message_queue._lock:
                    self.message_queue._size -= 1
                return item
            except queue.Empty:
                # This shouldn't happen since we checked, but handle it anyway
                pass
                
        # Return None if no messages or error occurred
        return None
            
    def _process_single_message(self, system_name, message, loop: asyncio.AbstractEventLoop, worker_state: Dict):
        """Process a single message with error handling and state tracking."""
        
        # Log the system name for debugging
        logger.info(f"[Async] Processing message for system: {system_name}")
        
        # Validate input parameters
        if system_name is None or not isinstance(system_name, str):
            logger.error(f"[Async] Invalid system_name: {system_name}")
            return
            
        # Validate message is a dictionary
        if not isinstance(message, dict):
            logger.error(f"[Async] Invalid message format: expected dict, got {type(message).__name__}")
            return
            
        # Extract message_id for task completion
        message_id = message.get('message_id')
        if not message_id:
            logger.warning(f"[Async] Message without message_id: {message}")
            message_id = "unknown"  # Use a default ID if none is provided
        
        # Get message priority
        priority = MessagePriority.get_priority(message)
        
        # Update worker state
        worker_state['last_message_time'] = time.time()
        
        try:
            # Run message handling in the event loop
            loop.run_until_complete(self._handle_message_async(system_name, message))
            
            # Mark task as done with message_id and success=True
            self.message_queue.task_done(message_id, success=True)
            
            # Update worker state on success
            worker_state['processed_count'] += 1
            worker_state['consecutive_errors'] = 0  # Reset consecutive errors
            
            # Remove from message tracking
            with self._transaction_lock:
                if message_id in self._message_tracking:
                    del self._message_tracking[message_id]
                    
        except Exception as e:
            # Mark task as failed if there's an error
            self.message_queue.task_done(message_id, success=False)
            
            # Update worker state on error
            worker_state['error_count'] += 1
            worker_state['last_error_time'] = time.time()
            worker_state['consecutive_errors'] += 1
            
            # Log error with priority level
            if priority == MessagePriority.HIGH:
                logger.error(f"[Async] Error processing HIGH PRIORITY message {message_id}: {str(e)}")
            else:
                logger.error(f"[Async] Error processing message {message_id}: {str(e)}")
                
            logger.error(traceback.format_exc())
            
            # Update message tracking for retry
            with self._transaction_lock:
                if message_id in self._message_tracking:
                    timestamp, sys_name, pri, retry_count, orig_message = self._message_tracking[message_id]
                    self._message_tracking[message_id] = (time.time(), sys_name, pri, retry_count + 1, orig_message)

    async def _handle_message_async(self, system_name: str, message: Dict):
        """Async wrapper for message handling with state tracking."""
        try:
            # Validate message has required fields
            if 'command_word' not in message:
                logger.error(f"[Async] Message missing command_word for system {system_name}")
                return
                
            command_word = message['command_word']
            data = message.get('data')
            request_id = message.get('request_id')
            message_type = message.get('message_type')
            
            # Ensure system exists
            if system_name not in self.systems:
                logger.info(f"[Async] Auto-registering system: {system_name}")
                self.register_system(system_name)
                
            system = self.systems[system_name]
            
            # Validate command word format
            try:
                validated_command = validate_command_word(command_word)
            except ValueError as e:
                logger.error(f"[Async] Invalid command word format: {e}")
                return
            
            # Log message routing
            logger.info(f"[Async] Routing message:")
            logger.info(f"[Async]   System: {system_name}")
            logger.info(f"[Async]   Message type: {message_type}")
            logger.info(f"[Async]   Command word: {validated_command}")
            logger.info(f"[Async]   Request ID: {request_id}")
            
            handler = system.message_handlers.get(validated_command)
            if not handler:
                # Try message type as fallback
                handler = system.message_handlers.get(message_type)
                if handler:
                    logger.info(f"[Async] Found handler by message type: {message_type}")
            if handler:
                try:
                    # Track message start
                    start_time = time.time()
                    
                    # Execute handler
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(data)
                    else:
                        result = handler(data)
                    
                    # Update handler state on success
                    system.update_handler_state(validated_command, success=True)
                    
                    # Log success with timing
                    logger.info(f"[Async] Successfully processed message: system={system_name}, command={validated_command}, request_id={request_id}, duration={time.time() - start_time:.3f}s")
                    
                    return result
                    
                except Exception as e:
                    # Update handler state on failure
                    system.update_handler_state(validated_command, success=False)
                    logger.error(f"[Async] Handler error for command {validated_command}: {str(e)}")
                    raise
            else:
                logger.warning(f"[Async] Unknown command word: {validated_command} for system {system_name}")
                
        except Exception as e:
            logger.error(f"[Async] Error handling message: {str(e)}")
            # Don't update handler state here as it's a system-level error

    def _handle_message(self, system_name: str, message: Dict):
        """Handle incoming messages with proper async support and state tracking."""
        try:
            # Validate message format before accessing keys
            if not isinstance(message, dict):
                logger.error(f"[Async] Invalid message format: expected dict, got {type(message).__name__}")
                # Update handler state to DEGRADED instead of letting it crash
                with self._state_lock:
                    if self._state == HandlerState.RUNNING:
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
                        logger.warning("[Async] Transitioning to DEGRADED state due to invalid message format")
                return
                
            # Validate command_word exists
            if 'command_word' not in message:
                logger.error(f"[Async] Message missing command_word for system {system_name}")
                # Update handler state to DEGRADED instead of letting it crash
                with self._state_lock:
                    if self._state == HandlerState.RUNNING:
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
                        logger.warning("[Async] Transitioning to DEGRADED state due to missing command_word")
                return
                
            command_word = message['command_word']  # Now safely validated
            data = message.get('data')
            request_id = message.get('request_id')
            
            # Validate system exists
            if system_name not in self.systems:
                logger.error(f"[Async] System {system_name} not found")
                # Auto-register system if it doesn't exist
                logger.info(f"[Async] Auto-registering system: {system_name}")
                self.register_system(system_name)
            
            system = self.systems[system_name]  # Now safely validated
            
            # Validate command_word format
            try:
                validated_command = validate_command_word(command_word)
            except ValueError as e:
                logger.error(f"[Async] Invalid command word format: {e}")
                # Update handler state to DEGRADED instead of letting it crash
                with self._state_lock:
                    if self._state == HandlerState.RUNNING:
                        self._state = HandlerState.DEGRADED
                        self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
                        logger.warning("[Async] Transitioning to DEGRADED state due to invalid command word")
                return
            
            handler = system.message_handlers.get(validated_command)
            if handler:
                try:
                    # Track message start
                    start_time = time.time()
                    
                    # Execute handler
                    if asyncio.iscoroutinefunction(handler):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        future = asyncio.run_coroutine_threadsafe(
                            handler(data),
                            loop
                        )
                        result = future.result(timeout=5.0)  # 5 second timeout for handlers
                        
                        # Update handler state on success
                        system.update_handler_state(validated_command, success=True)
                        
                        # Log success with timing
                        logger.info(f"[Async] Successfully processed message: system={system_name}, command={validated_command}, request_id={request_id}, duration={time.time() - start_time:.3f}s")
                        
                        return result
                        
                    else:
                        result = handler(data)
                        
                        # Update handler state on success
                        system.update_handler_state(validated_command, success=True)
                        
                        # Log success with timing
                        logger.info(f"[Async] Successfully processed message: system={system_name}, command={validated_command}, request_id={request_id}, duration={time.time() - start_time:.3f}s")
                        
                        return result
                        
                except TimeoutError:
                    # Update handler state on timeout
                    system.update_handler_state(validated_command, success=False)
                    logger.error(f"[Async] Handler timeout for command {validated_command} in system {system_name}")
                    raise
                    
                except Exception as e:
                    # Update handler state on failure
                    system.update_handler_state(validated_command, success=False)
                    logger.error(f"[Async] Handler error for command {validated_command}: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
                    
            else:
                logger.warning(f"[Async] Unknown command word: {validated_command} for system {system_name}")

        except Exception as e:
            logger.error(f"[Async] Error handling message: {str(e)}")
            logger.error(traceback.format_exc())
            # Update handler state to DEGRADED instead of letting it crash
            with self._state_lock:
                if self._state == HandlerState.RUNNING:
                    self._state = HandlerState.DEGRADED
                    self._state_transitions.append((HandlerState.RUNNING, HandlerState.DEGRADED, time.time()))
                    logger.warning("[Async] Transitioning to DEGRADED state due to message handling error")

    def send_message(self, system_name: str, command_word: str, data: Dict):
        try:
            if not isinstance(command_word, str) or len(command_word) != 16 or not set(command_word) <= {'0', '1'}:
                raise ValueError(f"Invalid command word format: {command_word}")

            command_word_int = int(command_word, 2)
            self.send_1553_msg.send_message(command_word_int, data)
            logger.debug(f"[Async] Sent 1553 message: {system_name}, {command_word} ({command_word_int})")
        except Exception as e:
            logger.error(f"[Async] Error sending message for {system_name}: {str(e)}")
            raise

    async def send_request(self, system_name: str, command_word: str, data: Dict, timeout: float = 5.0) -> str:
        """Send a request and return a request ID for tracking the response."""
        try:
            # Add debug logging for data type and fields
            logger.info(f"[Async] send_request called with system_name={system_name}, command_word={command_word}")
            logger.info(f"[Async] Data type: {type(data).__name__}")
            logger.info(f"[Async] Data has fields: {[f for f in dir(data) if not f.startswith('_') and not callable(getattr(data, f))]}")
            logger.info(f"[Async] Data repr: {repr(data)}")
            
            request_id = f"{system_name}_{command_word}_{int(time.time() * 1000)}"
            message = {
                'command_word': command_word,
                'data': data,
                'request_id': request_id,
                'timestamp': time.time()
            }
            
            # Extract metadata fields directly into the message
            metadata_fields = [
                'message_header', 'message_type', 'command_name', 
                'sending_system', 'destination', 'additional_info'
            ]
            
            for field in metadata_fields:
                if hasattr(data, field) and getattr(data, field) is not None:
                    message[field] = getattr(data, field)
                    logger.info(f"[Async] Extracted metadata field {field}: {getattr(data, field)}")

                    
            
            
            # Add command_type based on command_name if available
            if hasattr(data, 'command_name') and getattr(data, 'command_name'):
                message['command_type'] = 'command'
                logger.info(f"[Async] Set command_type to 'command' based on command_name")
            
            # Log the extracted metadata
            logger.info(f"[Async] Extracted metadata from BaseMessage: {', '.join(f'{k}={message[k]}' for k in message if k not in ['command_word', 'data', 'request_id', 'timestamp'])}")
        
            self.add_message(system_name, message)
            logger.debug(f"[Async] Sent request: {system_name}, {command_word}, request_id={request_id}")
            return request_id
        except Exception as e:
            logger.error(f"[Async] Error sending request for {system_name}: {str(e)}")
            raise

    def _run_periodic_tasks(self):
        logger.debug("[Async] Periodic task runner started")
        while self.running:
            try:
                current_time = time.time()
                # Locked snapshot (added August 2026 re-analysis round,
                # Round 15, message routing table staleness sweep):
                # register_system() inserts new keys into self.systems
                # under self.lock whenever a not-yet-seen system name is
                # first encountered (reactive, not just at boot -- e.g.
                # RadarMessageHandler/FMSMessageHandler/DisplayMessageHandler/
                # FCSMessageHandler all call it lazily), while this loop
                # previously iterated `self.systems.values()` directly with
                # no lock at all. Live-reproduced (same bug class as the
                # DisplayNode and RadarDisplayDataCoordinator dict races
                # fixed earlier this session): a concurrent register_system()
                # call while this loop was mid-iteration raised "RuntimeError:
                # dictionary changed size during iteration" on the first
                # trial of a 2-thread stress test. Taking a snapshot under
                # the lock and iterating the snapshot (not the live dict)
                # closes this without holding self.lock for the whole
                # per-cycle task-processing duration, which could otherwise
                # add unnecessary contention against other threads calling
                # register_system().
                with self.lock:
                    systems_snapshot = list(self.systems.values())
                for system in systems_snapshot:
                    if not system.active:
                        continue
                        
                    tasks = system.periodic_tasks.copy()
                    for task in tasks:
                        if task.should_disable():
                            system.periodic_tasks.remove(task)
                            logger.warning(f"[Async] Disabled failing periodic task in {system.system_name}")
                            continue
                            
                        if task.should_run(current_time):
                            try:
                                if not task.run(current_time):
                                    logger.warning(f"[Async] Periodic task failed in {system.system_name}")
                            except Exception as e:
                                logger.error(f"[Async] Error in periodic task: {str(e)}")
                                
                time.sleep(0.1)  # Prevent excessive CPU usage
                
            except Exception as e:
                logger.error(f"[Async] Error in periodic task runner: {str(e)}")
                time.sleep(1.0)  # Longer sleep on error

    def check_health(self) -> bool:
        """Comprehensive health check of the AsyncMessageHandler"""
        try:
            current_time = time.time()
            if current_time - self._last_health_check < self._health_check_interval:
                return self._state in [HandlerState.RUNNING, HandlerState.DEGRADED]  # Return last known state if checked recently
                
            with self.lock:
                # Check basic state
                if self._state not in [HandlerState.RUNNING, HandlerState.DEGRADED]:
                    return False
                
                # Check worker threads
                if not all(worker.is_alive() for worker in self.workers):
                    return False
                
                # Check periodic task thread
                if not self.periodic_task_thread or not self.periodic_task_thread.is_alive():
                    return False
                
                # Check executor
                if not self.executor or self.executor._shutdown:
                    return False
                
                # Check systems
                if not any(system.active for system in self.systems.values()):
                    return False
                
                self._last_health_check = current_time
                return True
                
        except Exception as e:
            logger.error(f"[Async] Error in health check: {str(e)}")
            return False

    def is_healthy(self) -> bool:
        """Quick health check with detailed logging"""
        try:
            current_time = time.time()
            if current_time - self._last_health_check < self._health_check_interval:
                return self._state in [HandlerState.RUNNING, HandlerState.DEGRADED]
                
            with self.lock:
                # Check basic state
                if self._state == HandlerState.STOPPED:
                    logger.error(f"[Async] AsyncMessageHandler in {HandlerState.to_string(self._state)} state")
                    return False
                    
                if self._state == HandlerState.STOPPING:
                    logger.error(f"[Async] AsyncMessageHandler in {HandlerState.to_string(self._state)} state")
                    return False
                    
                if self._state == HandlerState.STARTING:
                    logger.error(f"[Async] AsyncMessageHandler in {HandlerState.to_string(self._state)} state")
                    return False
                
                # Check worker threads
                dead_workers = [i for i, worker in enumerate(self.workers) if not worker.is_alive()]
                if dead_workers:
                    logger.error(f"[Async] Worker threads not alive: {dead_workers}")
                    return False
                
                # Check periodic task thread
                if not self.periodic_task_thread:
                    logger.error("[Async] Periodic task thread not initialized")
                    return False
                    
                if not self.periodic_task_thread.is_alive():
                    logger.error("[Async] Periodic task thread not alive")
                    return False
                
                # Check executor
                if not self.executor:
                    logger.error("[Async] ThreadPoolExecutor not initialized")
                    return False
                    
                if self.executor._shutdown:
                    logger.error("[Async] ThreadPoolExecutor is shutdown")
                    return False
                
                # Check systems
                if not self.systems:
                    logger.error("[Async] No systems registered")
                    return False
                    
                active_systems = [name for name, sys in self.systems.items() if sys.active]
                if not active_systems:
                    logger.error("[Async] No active systems found. Systems: " + 
                               ", ".join(f"{name}({'active' if sys.active else 'inactive'})"
                                       for name, sys in self.systems.items()))
                    return False
                
                self._last_health_check = current_time
                return True
                
        except Exception as e:
            logger.error(f"[Async] Error in health check: {str(e)}")
            return False

# Global instance with thread-safe initialization
_async_message_handler = None
_handler_lock = threading.Lock()

def get_Async_message_handler():
    """
    Get the global AsyncMessageHandler instance.
    
    Returns:
        AsyncMessageHandler: The singleton instance of AsyncMessageHandler
    """
    global _async_message_handler
    
    # Always acquire the lock to prevent race conditions
    with _handler_lock:
        # Check if instance exists
        if _async_message_handler is None:
            logger.info("[Async] Creating new global AsyncMessageHandler instance")
            _async_message_handler = AsyncMessageHandler()
            # Log the instance ID for tracking
            logger.info(f"[Async] Created AsyncMessageHandler instance: {id(_async_message_handler)}")
        else:
            # Check if the instance is in a valid state
            if hasattr(_async_message_handler, '_state'):
                state = _async_message_handler._state
                # If the instance is in STOPPED state, try to restart it
                if state == HandlerState.STOPPED:
                    logger.warning(f"[Async] AsyncMessageHandler instance {id(_async_message_handler)} is in STOPPED state. Attempting to restart...")
                    try:
                        # Start in a separate thread to avoid blocking
                        restart_thread = threading.Thread(
                            target=_async_message_handler.start,
                            name="AsyncMessageHandler_Restart",
                            daemon=False
                        )
                        restart_thread.start()
                        
                        # Wait briefly for restart to begin
                        restart_thread.join(timeout=0.5)
                        
                        logger.info("[Async] AsyncMessageHandler restart initiated")
                    except Exception as e:
                        logger.error(f"[Async] Failed to restart AsyncMessageHandler: {e}")
                        logger.error(traceback.format_exc())
    
    return _async_message_handler

def get_SystemHandler(system_name: str):
    return SystemHandler(system_name)
