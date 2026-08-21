"""
Interface Display Message Handler

Processes incoming display messages and manages message queue.
Implements MIL-STD-1553B message handling and service request management.
This is the interface version that properly handles async operations.
Uses display-local message types and constants for consistent message handling.
"""

import asyncio
import threading
import traceback
from typing import Dict, Any, Optional, Union
import queue

# Import display-local modules
from .display_mil_std_1553b import DisplayMIL_STD_1553B_Message
from .display_message_router import DisplayMessageRouter
from .display_message_types import (
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    DISPLAY_VIL_DATA,
    DISPLAY_PRECIPITATION_DATA,
    DISPLAY_ECHO_TOP_DATA,
    translate_message_type,
    is_precipitation_message,
    is_vil_message
)

# Import routing service
from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Global instance
_interface_display_message_handler = None
_instance_lock = threading.Lock()

class InterfaceDisplayMessageHandler:
    """Interface version of DisplayMessageHandler with proper async support."""
    def __init__(self):
        """Initialize display message handler."""
        import uuid
        
        # Get display tree manager first to ensure it exists
        from ..displays.display_nodes.display_tree_manager import get_display_tree_manager
        self.tree_manager = get_display_tree_manager()
        if not self.tree_manager._initialized:
            logger.error("DisplayMessageHandler: Display tree manager not initialized")
            raise RuntimeError("Display tree manager not initialized")

        # Initialize core components
        self.message_router = DisplayMessageRouter()
        self.message_queue = queue.Queue()
        self._queue_id = id(self.message_queue)  # Track queue instance
        self._running = False
        self._init_lock = threading.Lock()
        self._message_lock = threading.Lock()
        self._message_task = None
        self.pending_requests = {}
        self.started = False
        self.request_rate_limit = 10  # requests per second
        self.last_request_time = 0
        self.SYSTEM_NAME = "displays"  # Centralize system name
        self._task_health_check_timer = None
        self._last_health_check = 0
        self._health_check_interval = 5.0  # seconds
        self._lock = threading.Lock()  # Lock for event loop operations
        self.routing_service = None  # Initialize routing service reference

        # Add thread state tracking
        self._processor_ready = threading.Event()
        self._processor_running = threading.Event()
        self._processor_thread = None
        
        # Initialize loop prevention middleware
        try:
            from FMOFP.Utils.message_loop_prevention.middleware import get_loop_prevention_middleware
            self.loop_prevention = get_loop_prevention_middleware()
            logger.info("[INTERFACE_DISP_HDLR] Initialized loop prevention middleware")
            
            # Register specific categories if possible
            if hasattr(self.loop_prevention, 'register_category'):
                categories = {
                    'vil': {'type': 'Weather Radar data', 'priority': 'high', 'max_processing': 1},
                    'precipitation': {'type': 'Weather Radar data', 'priority': 'high', 'max_processing': 1},
                    'display_data': {'type': 'Display data', 'priority': 'medium', 'max_processing': 2},
                    'mode_change': {'type': 'Control command', 'priority': 'highest', 'max_processing': 1}
                }
                
                for category, settings in categories.items():
                    try:
                        self.loop_prevention.register_category(
                            category,
                            category_type=settings['type'],
                            priority=settings['priority'],
                            max_simultaneous_processing=settings['max_processing']
                        )
                    except Exception as cat_err:
                        logger.warning(f"[INTERFACE_DISP_HDLR] Failed to register category {category}: {cat_err}")
                        
                logger.info("[INTERFACE_DISP_HDLR] Registered message categories with loop prevention middleware")
        except Exception as e:
            logger.error(f"[INTERFACE_DISP_HDLR] Failed to initialize loop prevention middleware: {e}")
            self.loop_prevention = None

        # Update router with tree manager
        self.message_router.set_tree_manager(self.tree_manager)
        
        # Initialize event loop
        self._event_loop = None
        self._loop_lock = threading.Lock()
        
        logger.info(f"DisplayMessageHandler initialized with tree manager (queue_id: {self._queue_id})")

    def _get_event_loop(self):
        """Get or create event loop for current thread."""
        with self._loop_lock:
            try:
                # Always create a new event loop for this thread to avoid the "no current event loop" error
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop
            except Exception as e:
                logger.error(f"[INTERFACE_DISP_HDLR] Error creating event loop: {str(e)}")
                # If creating an event loop fails for any reason, create one as a fallback
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop

    def _run_message_processor(self):
        """Run the message processor in a thread."""
        thread_id = threading.get_ident()
        logger.info(f"[INTERFACE_DISP_HDLR] _run_message_processor starting (Thread ID: {thread_id}, Queue ID: {self._queue_id})")
        
        # Signal thread is starting
        self._processor_ready.set()
        
        # Get event loop for this thread
        loop = self._get_event_loop()
        logger.info(f"[INTERFACE_DISP_HDLR] Using event loop: {loop}")
        
        try:
            # Store loop reference
            with self._loop_lock:
                self._event_loop = loop
            
            logger.info(f"[INTERFACE_DISP_HDLR] Running _process_messages_thread in event loop")
            
            # Signal thread is now running and processing messages
            self._processor_running.set()
            
            loop.run_until_complete(self._process_messages_thread())
            logger.info(f"[INTERFACE_DISP_HDLR] _process_messages_thread completed normally")
        except Exception as e:
            logger.error(f"[INTERFACE_DISP_HDLR] Error in _run_message_processor: {str(e)}")
            logger.error(traceback.format_exc())
            # Clear running flag on error
            self._processor_running.clear()
        finally:
            logger.info(f"[INTERFACE_DISP_HDLR] Closing event loop")
            with self._loop_lock:
                if self._event_loop == loop:
                    self._event_loop = None
            loop.close()
            # Clear both flags when exiting
            self._processor_ready.clear()
            self._processor_running.clear()
            logger.info(f"[INTERFACE_DISP_HDLR] _run_message_processor exiting (Thread ID: {thread_id})")

    async def _process_messages_thread(self):
        """Process messages from queue in a dedicated thread."""
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        logger.info(f"[INTERFACE_DISP_HDLR] Starting message processor thread (ID: {thread_id}, Name: {thread_name})")
        
        # Get event loop for this thread
        loop = self._get_event_loop()
        logger.info(f"[INTERFACE_DISP_HDLR] Using event loop: {loop}")
        
        try:
            logger.info(f"[INTERFACE_DISP_HDLR] Entering message processing loop with _running={self._running}")
            while self._running:
                try:
                    # Log start of processing cycle
                    # logger.info("[INTERFACE_DISP_HDLR] Starting message processing cycle")
                    
                    message = None
                    subaddress_info = None
                    
                    # First check queue size with lock
                    with self._message_lock:
                        queue_size = self.message_queue.qsize()
                        #logger.info(f"[INTERFACE_DISP_HDLR] Current queue size: {queue_size}")
                        
                        if queue_size > 0:
                            try:
                                # Get message within lock scope
                                message, subaddress_info = self.message_queue.get_nowait()
                                logger.info("[INTERFACE_DISP_HDLR] Message dequeued for processing")
                                logger.info(f"[INTERFACE_DISP_HDLR] Message {message}")
                                logger.info(f"[INTERFACE_DISP_HDLR] subaddress_info {subaddress_info}")
                                logger.info(f"[INTERFACE_DISP_HDLR] Message details - ID: {getattr(message, 'request_id', None)}")
                                logger.info("[INTERFACE_DISP_HDLR] Mode command routing confirmed")
                            except queue.Empty:
                                logger.warning("[INTERFACE_DISP_HDLR] Queue was empty despite size check")
                                continue
                    
                    # Process message outside lock scope if we got one
                    if message is not None:
                        try:
                            logger.info("[INTERFACE_DISP_HDLR] Starting message routing")
                            logger.info(f"[INTERFACE_DISP_HDLR] Message type: {type(message)}")
                            logger.info(f"[INTERFACE_DISP_HDLR] Subaddress info: {subaddress_info}")
                            
                            # Route the message
                            await self.message_router.route_message(message, subaddress_info)
                            logger.info("[INTERFACE_DISP_HDLR] Message routing completed successfully")
                            logger.info("[INTERFACE_DISP_HDLR] Mode command routing confirmed")
                            
                            # Mark task as done
                            self.message_queue.task_done()
                            logger.info("[INTERFACE_DISP_HDLR] Message task marked as done")
                            
                            # Verify queue state after processing
                            with self._message_lock:
                                new_size = self.message_queue.qsize()
                                logger.info(f"[INTERFACE_DISP_HDLR] Queue size after processing: {new_size}")
                                
                        except Exception as route_error:
                            logger.error(f"[INTERFACE_DISP_HDLR] Error routing message: {str(route_error)}")
                            logger.error(f"[INTERFACE_DISP_HDLR] Message routing failed with error: {traceback.format_exc()}")
                            # Don't re-raise, continue processing next message
                    
                    # Short sleep to avoid CPU spinning
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"[INTERFACE_DISP_HDLR] Critical error in message processing cycle: {str(e)}")
                    logger.error(f"[INTERFACE_DISP_HDLR] Full traceback: {traceback.format_exc()}")
                    await asyncio.sleep(1.0)  # Back off on error
                    
            logger.info(f"[INTERFACE_DISP_HDLR] Exiting message processing loop (_running={self._running})")
        except Exception as e:
            logger.error(f"[INTERFACE_DISP_HDLR] Critical error in message processor thread: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            logger.info(f"[INTERFACE_DISP_HDLR] Message processor thread ending (ID: {thread_id})")

    async def start(self):
        """Start the DisplayMessageHandler."""
        try:
            logger.info("[INTERFACE_DISP_HDLR] Starting DisplayMessageHandler...")
            
            # Initialize state BEFORE starting thread
            self._running = True
            self.started = True
            
            # Get thread manager
            from FMOFP.Utils.common.thread_manager import thread_manager
            
            # Start message processor thread
            thread_name = "DisplayMessageProcessor"  # Use registered startup thread name
            if not thread_manager.is_thread_alive(thread_name):
                logger.info(f"[INTERFACE_DISP_HDLR] Starting {thread_name} thread")
                
                # Clear flags before starting
                self._processor_ready.clear()
                self._processor_running.clear()
                
                # Use synchronous wrapper method directly
                thread_manager.add_thread(
                    name=thread_name,
                    target=self._run_message_processor
                )
                
                # Start the thread
                if not thread_manager.start_thread(thread_name):
                    logger.error(f"[INTERFACE_DISP_HDLR] Failed to start {thread_name}")
                    self._running = False
                    self.started = False
                    return False
                    
                logger.info(f"[INTERFACE_DISP_HDLR] {thread_name} thread started")
                
                # Wait for thread to be ready (timeout after 5 seconds)
                if not self._processor_ready.wait(timeout=5.0):
                    logger.error(f"[INTERFACE_DISP_HDLR] Thread {thread_name} failed to signal ready")
                    self._running = False
                    self.started = False
                    return False
                
                # Wait for thread to be running (timeout after 5 seconds)
                if not self._processor_running.wait(timeout=5.0):
                    logger.error(f"[INTERFACE_DISP_HDLR] Thread {thread_name} failed to signal running")
                    self._running = False
                    self.started = False
                    return False
                
                # Verify thread is running
                if not thread_manager.is_thread_alive(thread_name):
                    logger.error(f"[INTERFACE_DISP_HDLR] Thread {thread_name} failed to start properly")
                    self._running = False
                    self.started = False
                    return False
                
                logger.info(f"[INTERFACE_DISP_HDLR] {thread_name} thread is ready and running")
            
            # Verify required components with detailed logging
            if not self.routing_service:
                self.routing_service = get_message_routing_service()
                if not self.routing_service:
                    logger.error("[INTERFACE_DISP_HDLR] Failed to initialize MessageRoutingService")
                    raise RuntimeError("Failed to initialize MessageRoutingService")
                logger.info("[INTERFACE_DISP_HDLR] MessageRoutingService initialized successfully")

            if not self.message_router:
                logger.error("[INTERFACE_DISP_HDLR] MessageRouter not initialized")
                raise RuntimeError("MessageRouter must be initialized")
            logger.info("[INTERFACE_DISP_HDLR] MessageRouter verified")

            if not self.tree_manager or not self.tree_manager._initialized:
                logger.error("[INTERFACE_DISP_HDLR] Display tree manager not initialized")
                raise RuntimeError("Display tree manager must be initialized")
            logger.info("[INTERFACE_DISP_HDLR] Display tree manager verified")

            # Start cleanup timer with async wrapper
            wrapped_cleanup = AsyncThreadWrapper(self._cleanup_thread)
            thread_name = "DisplayMessageCleanup"
            if not thread_manager.is_thread_alive(thread_name):
                thread_manager.add_thread(
                    name=thread_name,
                    target=wrapped_cleanup
                )
                success = thread_manager.start_thread(thread_name)
                if success:
                    logger.info(f"Thread '{thread_name}' started successfully")
                else:
                    logger.warning(f"Failed to start thread '{thread_name}'")
            else:
                # Silenced logging
                # logger.debug(f"Thread '{thread_name}' is already running, skipping start")
                pass
            
            # Log final thread manager state
            active_threads = thread_manager.get_active_threads()
            logger.info(f"[INTERFACE_DISP_HDLR] Active threads after start: {active_threads}")
            
            # Final state verification
            logger.info(f"[INTERFACE_DISP_HDLR] Final _running state: {self._running}")
            logger.info(f"[INTERFACE_DISP_HDLR] Final started state: {self.started}")
            
            logger.info("[INTERFACE_DISP_HDLR] DisplayMessageHandler started successfully")
            return True
        except Exception as e:
            logger.error(f"[INTERFACE_DISP_HDLR] Error starting DisplayMessageHandler: {str(e)}")
            self._running = False
            self.started = False
            return False

    def stop(self):
        """Stop the InterfaceDisplayMessageHandler and its background threads.

        This class is a genuinely separate object from DisplayMessageHandler
        (display_message_handler.py) -- confusingly, both register threads
        named "DisplayMessageProcessor" and "DisplayMessageCleanup" via the
        shared thread_manager, but since this class's start() runs first
        (see system_manager.py), it wins that name registration and
        DisplayMessageHandler's own attempt at the same names is silently a
        no-op (ThreadManager.add_thread() treats an already-registered name
        as "nothing to do"). Before this fix, this class had no stop()
        method at all, and system_manager.py's shutdown path only called
        DisplayMessageHandler.stop() -- which cleared the wrong instance's
        self._running, leaving the threads actually driven by *this*
        object's self._running running until thread_manager's bounded join
        timeout gave up on them (confirmed live: "DisplayMessageProcessor"
        and "DisplayMessageCleanup" both hung for the full 2s timeout on
        every shutdown). Mirrors DisplayMessageHandler.stop()'s pattern.
        """
        logger.info("[INTERFACE_DISP_HDLR] Stopping InterfaceDisplayMessageHandler")
        self._running = False
        self.started = False
        self._processor_ready.clear()
        self._processor_running.clear()
        logger.info("[INTERFACE_DISP_HDLR] InterfaceDisplayMessageHandler stopped")

    async def _cleanup_thread(self):
        """Thread function for cleaning up stale requests"""
        thread_id = threading.get_ident()
        logger.info(f"[INTERFACE_DISP_HDLR] Starting cleanup thread (ID: {thread_id})")
        
        while self._running:
            try:
                await self._cleanup_pending_requests()
                await asyncio.sleep(1.0)  # Run cleanup every second
            except Exception as e:
                logger.error(f"Error in cleanup thread: {str(e)}")
                await asyncio.sleep(5.0)  # Back off on error
                
        logger.info(f"[INTERFACE_DISP_HDLR] Cleanup thread ended (ID: {thread_id})")

    async def _cleanup_pending_requests(self):
        """Clean up expired pending requests"""
        # Implementation remains the same as before
        pass

    def enqueue_message(self, message: Union[DisplayMIL_STD_1553B_Message, Any], subaddress_info: Dict):
        """
        Enqueue a message for processing.
        Uses display-local message types and constants for consistent message handling.
        """
        import uuid
        try:
            # First verify processor is running
            if not self._processor_running.is_set():
                logger.error("[INTERFACE_DISP_HDLR] Message processor not running, cannot enqueue message")
                return
                
            with self._message_lock:
                # Get request_id from all possible sources
                request_id = None
                
                # Check subaddress_info first since it's most reliable
                if subaddress_info and 'request_id' in subaddress_info:
                    request_id = subaddress_info['request_id']
                
                # Check message attributes next
                elif hasattr(message, 'request_id'):
                    request_id = message.request_id
                
                # Finally check command_word metadata
                elif hasattr(message, 'command_word') and isinstance(message.command_word, dict):
                    request_id = message.command_word.get('request_id')
                if not request_id:
                    
                    raise ValueError("[INTERFACE_DISP_HDLR] No request_id found in message or subaddress_info")
                # Ensure request_id is in both message and subaddress_info
                if not hasattr(message, 'request_id'):
                    message.request_id = request_id
                    
                if 'request_id' not in subaddress_info:
                    subaddress_info['request_id'] = request_id
                
                # LOOP PREVENTION: Check if message has already been processed
                if self.loop_prevention:
                    # Determine message category using display-local message types
                    category = 'display_data'  # Default category
                    
                    # Try to extract category from subaddress_info
                    if subaddress_info:
                        if 'message_type' in subaddress_info:
                            msg_type = subaddress_info['message_type']
                            
                            # Use helper functions from display_message_types
                            if is_vil_message({'message_type': msg_type}):
                                category = 'vil'
                            elif is_precipitation_message({'message_type': msg_type}):
                                category = 'precipitation'
                            elif msg_type == DISPLAY_COMMAND_TYPE_MODE_CHANGE or msg_type == DISPLAY_COMMAND_TYPE_MODE:
                                category = 'mode_change'
                                
                        # Check command_type as well
                        if 'command_type' in subaddress_info:
                            cmd_type = subaddress_info['command_type']
                            if cmd_type == DISPLAY_COMMAND_TYPE_MODE_CHANGE or cmd_type == DISPLAY_COMMAND_TYPE_MODE:
                                category = 'mode_change'
                                
                    # Try to get transaction ID from message metadata
                    transaction_id = None
                    if hasattr(message, 'metadata') and message.metadata:
                        if hasattr(message.metadata, 'transaction_id'):
                            transaction_id = message.metadata.transaction_id
                        elif isinstance(message.metadata, dict) and 'transaction_id' in message.metadata:
                            transaction_id = message.metadata['transaction_id']
                    
                    # Also check subaddress_info for transaction_id
                    if not transaction_id and 'metadata' in subaddress_info:
                        if isinstance(subaddress_info['metadata'], dict) and 'transaction_id' in subaddress_info['metadata']:
                            transaction_id = subaddress_info['metadata']['transaction_id']
                    
                    if not request_id:
                        
                        raise ValueError("[INTERFACE_DISP_HDLR] No request_id found in message or subaddress_info")
                    
                    # Process message through loop prevention middleware
                    should_process, enhanced_message = self.loop_prevention.process_message(
                        message,
                        f"interface_display_{category}"
                    )
                    
                    if not should_process:
                        logger.warning(f"[INTERFACE_DISP_HDLR] *** Breaking message loop: {category} message already processed: {transaction_id} ***")
                        return
                        
                    # Use enhanced message
                    if enhanced_message is not message:
                        message = enhanced_message
                        logger.info(f"[INTERFACE_DISP_HDLR] Using enhanced message with transaction ID: {transaction_id}")

                # Add to queue with detailed logging
                logger.info(f"[INTERFACE_DISP_HDLR] Enqueueing message to queue {self._queue_id}")
                logger.info(f"[INTERFACE_DISP_HDLR] Current queue size: {self.message_queue.qsize()}")
                self.message_queue.put((message, subaddress_info))
                logger.info(f"[INTERFACE_DISP_HDLR] Message enqueued: {request_id}")
                logger.info(f"[INTERFACE_DISP_HDLR] New queue size: {self.message_queue.qsize()}")
                
                # Verify message was actually enqueued
                new_size = self.message_queue.qsize()
                if new_size == 0:
                    logger.error("[INTERFACE_DISP_HDLR] Message failed to enqueue - queue is empty")
                    return

        except Exception as e:
            logger.error(f"[INTERFACE_DISP_HDLR] Error enqueuing message: {str(e)}")
            logger.error(traceback.format_exc())
            raise

def get_interface_display_message_handler():
    """Get the global InterfaceDisplayMessageHandler instance."""
    global _interface_display_message_handler
    with _instance_lock:
        if _interface_display_message_handler is None:
            _interface_display_message_handler = InterfaceDisplayMessageHandler()
        return _interface_display_message_handler

# Helper class for async thread wrapping
class AsyncThreadWrapper:
    """Wrapper class to run async methods in thread context."""
    def __init__(self, async_method):
        self.async_method = async_method
        
    def __call__(self, *args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.async_method(*args, **kwargs))
        finally:
            loop.close()
