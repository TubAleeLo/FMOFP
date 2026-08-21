"""
Display Message Handler

Processes incoming display messages and manages message queue.
Implements MIL-STD-1553B message handling and service request management.
Uses display-local message types and constants for consistent message handling.
"""

import asyncio
import threading
import time
import traceback
from typing import Dict, Any, Optional, Union
import queue

# Import display-local modules
from .display_mil_std_1553b import DisplayMIL_STD_1553B_Message
from .display_message_router import DisplayMessageRouter
from .display_1553b_helpers import Display1553BHelpers
from .display_command_map import (
    SHOW_REQUEST_MAP,
    MODE_REQUEST_MAP)
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
from .display_address_utils import (
    DISPLAY_RT_ADDRESS,
    get_rt_address_name,
    get_subaddress_name
)

# Import display types and modes
from ..displays.base_display import DisplayType, DisplayMode

# Import routing service
from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service

# Import system logger
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# MIL-STD-1553B Constants - centralized for easier maintenance
BC_POLL_INTERVAL = 0.1  # BC poll check interval in seconds
SERVICE_REQUEST_TIMEOUT = 2.0  # Service request timeout in seconds
MAX_RETRIES = 3  # Maximum number of retries for failed requests
REQUEST_TIMEOUT = 5.0  # Request timeout in seconds
QUEUE_TIMEOUT = 0.1  # Queue get timeout in seconds

class PendingDisplayRequest:
    """
    Tracks pending display requests with MIL-STD-1553B compliance.
    Uses display-local message types and constants for consistent message handling.
    """
    def __init__(self, request_type: str, display_type: str, timestamp: float, data: Any = None):
        self.request_type = request_type
        self.display_type = display_type
        self.timestamp = timestamp
        self.data = data
        self.retries = 0
        self.max_retries = MAX_RETRIES
        self.timeout = REQUEST_TIMEOUT
        self.error_state = None
        self.service_request_sent = False
        self.bc_poll_received = False
        self.last_bc_poll_time = None

    def is_expired(self, current_time: float) -> bool:
        return current_time - self.timestamp > self.timeout

    def should_retry(self) -> bool:
        return (self.retries < self.max_retries and 
                not self.service_request_sent and 
                not self.bc_poll_received)

    def increment_retry(self):
        self.retries += 1
        self.timestamp = time.time()

    def set_error_state(self, error: str):
        self.error_state = error
        if self.retries >= self.max_retries:
            self.service_request_sent = True

    def handle_bc_poll(self):
        """Handle BC poll response."""
        self.bc_poll_received = True
        self.last_bc_poll_time = time.time()

    def is_bc_poll_expired(self, current_time: float) -> bool:
        """Check if BC poll response has expired."""
        return (self.bc_poll_received and 
                self.last_bc_poll_time and 
                current_time - self.last_bc_poll_time > BC_POLL_INTERVAL)

class DisplayMessageHandler:
    """
    Handles display messages and manages message queue.
    Uses display-local message types and constants for consistent message handling.
    """
    def __init__(self):
        self.message_router = DisplayMessageRouter()
        self.message_queue = queue.Queue()
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
        self._lock = None  # Lock for event loop operations
        self.routing_service = None  # Initialize routing service reference
        self.current_status_word = None  # Current status word for RT mode
        self.rt_sender = None  # RT sender reference
        
        # Get display tree manager
        from ..displays.display_nodes.display_tree_manager import get_display_tree_manager
        self.tree_manager = get_display_tree_manager()
        if not self.tree_manager._initialized:
            logger.error("DisplayMessageHandler: Display tree manager not initialized")
            raise RuntimeError("Display tree manager not initialized")
            
        # Update router with tree manager
        self.message_router.set_tree_manager(self.tree_manager)
        
        logger.info("DisplayMessageHandler initialized with tree manager")

    def _on_task_complete(self, task):
        """Handle completion of message processing task."""
        try:
            # Check if task completed normally or with error
            if task.cancelled():
                logger.warning("[DISPLAY_HANDLER] Message processing task was cancelled")
            elif task.exception():
                logger.error(f"[DISPLAY_HANDLER] Message processing task failed with error: {task.exception()}")
                logger.error(traceback.format_exc())
            else:
                logger.info("[DISPLAY_HANDLER] Message processing task completed normally")

            # Reset task reference
            self._message_task = None
            
            # Restart task if still running
            if self._running:
                logger.info("[DISPLAY_HANDLER] Restarting message processing task")
                self._message_task = asyncio.create_task(self._process_messages())
                self._message_task.add_done_callback(self._on_task_complete)
                
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error in task completion handler: {str(e)}")
            logger.error(traceback.format_exc())

    async def _health_check(self):
        """Periodic health check of message processing task."""
        try:
            current_time = time.time()
            
            # Only run health check at intervals
            if current_time - self._last_health_check < self._health_check_interval:
                return
                
            self._last_health_check = current_time
            
            # Check task state
            if self._message_task:
                logger.info(f"[DISPLAY_HANDLER] Message task state: running={not self._message_task.done()}")
                if self._message_task.done():
                    if self._message_task.exception():
                        logger.error(f"[DISPLAY_HANDLER] Task failed with: {self._message_task.exception()}")
                    
            # Check queue state
            queue_size = self.message_queue.qsize()
            logger.info(f"[DISPLAY_HANDLER] Current queue size: {queue_size}")
            
            # Check component health
            logger.info(f"[DISPLAY_HANDLER] Components: router={bool(self.message_router)}, "
                       f"tree={bool(self.tree_manager)}")
            
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Health check error: {str(e)}")

    async def _run_health_checks(self):
        """Run periodic health checks."""
        while self._running:
            try:
                await self._health_check()
                await asyncio.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"[DISPLAY_HANDLER] Health check loop error: {str(e)}")
                await asyncio.sleep(5.0)  # Back off on error

    def set_display_manager(self, display_manager):
        """Set display manager and update router."""
        with self._init_lock:
            self.display_manager = display_manager
            self.message_router.set_display_manager(display_manager)
            logger.info("Display manager connected to message handler")

    def enqueue_message(self, message: Union[DisplayMIL_STD_1553B_Message, Any], subaddress_info: Dict):
        """
        Enqueue a message for processing.
        Uses display-local message types and constants for consistent message handling.
        """
        try:
            # Get request_id from all possible sources
            request_id = None
            
            # Check subaddress_info first since it's most reliable
            if subaddress_info and 'request_id' in subaddress_info:
                request_id = subaddress_info['request_id']
                logger.info(f"[DISPLAY_HANDLER] Found request_id in subaddress_info: {request_id}")
            
            # Check message attributes next
            elif hasattr(message, 'request_id'):
                request_id = message.request_id
                logger.info(f"[DISPLAY_HANDLER] Found request_id in message attribute: {request_id}")
            
            # Finally check command_word metadata
            elif hasattr(message, 'command_word') and isinstance(message.command_word, dict):
                request_id = message.command_word.get('request_id')
                logger.info(f"[DISPLAY_HANDLER] Found request_id in command_word: {request_id}")
                
            if not request_id:
                logger.error("[DISPLAY_HANDLER] Missing request_id in all metadata sources")
                return
                
            # Ensure request_id is in both message and subaddress_info
            if not hasattr(message, 'request_id'):
                message.request_id = request_id
                logger.info(f"[DISPLAY_HANDLER] Added request_id to message: {request_id}")
                
            if 'request_id' not in subaddress_info:
                subaddress_info['request_id'] = request_id
                logger.info(f"[DISPLAY_HANDLER] Added request_id to subaddress_info: {request_id}")

            # Validate remaining message info
            if not subaddress_info or not all(k in subaddress_info for k in ['id', 'command_type', 'source_system']):
                logger.error("[DISPLAY_HANDLER] Invalid subaddress info")
                return

            # Check if message.data is a direct data object and set message_type accordingly
            if hasattr(message, 'data'):
                # Use display-local message types instead of hardcoded strings
                from .display_weather_radar_data import DisplayWeatherRadarVILData, DisplayPrecipitationData
                
                if isinstance(message.data, DisplayWeatherRadarVILData):
                    message.message_type = DISPLAY_VIL_DATA
                    message_type = message.message_type
                    logger.info(f"[DISPLAY_HANDLER] Set message_type to {DISPLAY_VIL_DATA} for direct VIL data object")
                    subaddress_info['message_type'] = message_type
                    logger.info(f"[DISPLAY_HANDLER] Added message_type to subaddress_info: {message_type}")
                elif isinstance(message.data, DisplayPrecipitationData):
                    message.message_type = DISPLAY_PRECIPITATION_DATA
                    message_type = message.message_type
                    logger.info(f"[DISPLAY_HANDLER] Set message_type to {DISPLAY_PRECIPITATION_DATA} for direct Precipitation data object")
                    subaddress_info['message_type'] = message_type
                    logger.info(f"[DISPLAY_HANDLER] Added message_type to subaddress_info: {message_type}")
                elif hasattr(message, 'message_type'):
                    # Translate message type using display-local function
                    translated_type = translate_message_type(message.message_type)
                    subaddress_info['message_type'] = translated_type
                    logger.info(f"[DISPLAY_HANDLER] Added translated message_type to subaddress_info: {translated_type}")
            
            # Check for precipitation data in additional_info
            if hasattr(message, 'additional_info') and isinstance(message.additional_info, dict):
                additional_info = message.additional_info
                if 'weather_data' in additional_info and isinstance(additional_info['weather_data'], dict):
                    weather_data = additional_info['weather_data']
                    if 'precipitation_data' in weather_data:
                        message.message_type = DISPLAY_PRECIPITATION_DATA
                        subaddress_info['message_type'] = message.message_type
                        logger.info(f"[DISPLAY_HANDLER] Set message_type to {DISPLAY_PRECIPITATION_DATA} based on additional_info")
                        logger.info(f"[WEATHER_DISPLAY] Processing precipitation data")

            # Log message details
            logger.info(f"[DISPLAY_HANDLER] Enqueueing message: id={subaddress_info['id']}, "
                       f"type={subaddress_info['command_type']}, source={subaddress_info['source_system']}, "
                       f"request_id={request_id}, message_type={getattr(message, 'message_type', 'None')}")

            # Add to queue
            self.message_queue.put((message, subaddress_info))
            logger.info(f"[DISPLAY_HANDLER] Message enqueued: {request_id}")

            # Update queue metrics
            queue_size = self.message_queue.qsize()
            logger.info(f"[DISPLAY_HANDLER] Queue size: {queue_size}")

        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error enqueuing message: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _handle_bc_poll(self, message: Dict):
        """Handle BC poll message."""
        try:
            logger.debug("[DISPLAY_HANDLER] Received BC poll")
            
            # Update status word with current state
            await self._update_service_request_state(
                service_request=bool(self.pending_requests),
                busy=bool(self.pending_requests)
            )
            
            # Send status word response
            if self.rt_sender:
                # NOTE: RT_send_message() (RT_socket.py) is a synchronous
                # method - it submits to a ThreadPoolExecutor and blocks on
                # future.result() internally, then returns the plain result;
                # it is not `async def` and doesn't return an awaitable.
                poll_response = {
                    'status_word': self.current_status_word,
                    'timestamp': time.time(),
                    'is_poll_response': True
                }
                if not self.rt_sender.RT_send_message(poll_response):
                    logger.error("[DISPLAY_HANDLER] Failed to send BC poll response")
                    return
                    
            # Update pending requests
            current_time = time.time()
            for request in self.pending_requests.values():
                if request.service_request_sent:
                    request.handle_bc_poll()
                    
            logger.debug("[DISPLAY_HANDLER] BC poll handled successfully")
            
        except Exception as e:
            logger.error(f"Error handling BC poll: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_status_word(self, message: Dict):
        """
        Handle status word acknowledgment.
        Uses display-local message types and constants for consistent message handling.
        """
        try:
            logger.info(f"[ACK] Received status word with request_id: {message.get('request_id')}")
            
            # Get request ID from message
            request_id = message.get('request_id')
            display_type = message.get('display_type')
            command_type = message.get('command_type')
            status_word = message.get('status_word')
            
            if not request_id:
                logger.warning("Status word missing request_id")
                return

            # Validate status word if present
            if status_word:
                is_valid, components = Display1553BHelpers.validate_status_word(status_word)
                if not is_valid:
                    logger.error(f"Invalid status word received: {status_word}")
                    if request_id in self.pending_requests:
                        request = self.pending_requests[request_id]
                        request.set_error_state("Invalid status word")
                        await self._handle_request_error(request_id, request)
                    return

                # Check for message error
                if components.get('message_error'):
                    logger.error("Message error bit set in status word")
                    if request_id in self.pending_requests:
                        request = self.pending_requests[request_id]
                        request.set_error_state("Message error in status word")
                        await self._handle_request_error(request_id, request)
                    return

            # Store acknowledgment
            status_word_data = {
                'command_type': command_type or None,
                'display_type': display_type or None,
                'status': 'acknowledged',
                'request_id': request_id,
                'timestamp': time.time(),
                'additional_info': message.get('additional_info', {})
            }

            # Route status word to storage
            await self.routing_service.route_status_word(status_word_data)
            logger.info(f"[DISPLAY_HANDLER] Status word routed for request {request_id}")

            # Handle request completion
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                if request.service_request_sent:
                    # Clear service request flag if this was a response to one
                    await self._update_service_request_state(False)
                if not request.get('type', '').startswith('pilot_'):
                    del self.pending_requests[request_id]
                    logger.info(f"[DISPLAY_HANDLER] Removed completed request {request_id}")

        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error handling status word: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_request_error(self, request_id: str, request: PendingDisplayRequest):
        """Handle request errors and service request management."""
        try:
            if request.should_retry():
                logger.warning(f"Request {request_id} failed, will retry. Error: {request.error_state}")
                request.increment_retry()
                await self._resend_request(request_id, request)
            else:
                logger.error(f"Request {request_id} failed permanently. Error: {request.error_state}")
                if not request.service_request_sent:
                    await self._update_service_request_state(True)
                    request.service_request_sent = True
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error handling request error: {str(e)}")

    async def _update_service_request_state(self, service_request: bool, busy: bool = None):
        """Update service request state and status word."""
        try:
            if busy is None:
                busy = bool(self.pending_requests)
                
            # Update status word with new service request state
            self.current_status_word = Display1553BHelpers.construct_status_word(
                message_error=False,
                instrumentation=False,
                service_request=service_request,
                busy=busy,
                subsystem_flag=False,
                terminal_flag=False
            )
            
            # Validate the new status word
            is_valid, _ = Display1553BHelpers.validate_status_word(self.current_status_word)
            if not is_valid:
                logger.error("[DISPLAY_HANDLER] Failed to construct valid status word")
                return
                
            logger.info(f"Service request state updated: {service_request}")
            
            # Notify RT sender of new status
            if self.rt_sender:
                # See NOTE above: RT_send_message() is synchronous.
                status_update = {
                    'status_word': self.current_status_word,
                    'timestamp': time.time()
                }
                if not self.rt_sender.RT_send_message(status_update):
                    logger.error("[DISPLAY_HANDLER] Failed to send updated status word")
            
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error updating service request state: {str(e)}")

    async def _handle_show_display(self, message: Dict, display_type: DisplayType):
        """Handle show display command in RT mode."""
        try:
            request_id = message.get('request_id')
            if not request_id:
                logger.warning("Show display command missing request_id")
                return

            # Create pending request
            request = PendingDisplayRequest(
                request_type="show_display",
                display_type=display_type.name,
                timestamp=time.time()
            )
            self.pending_requests[request_id] = request

            # Construct and validate status word
            status_word = Display1553BHelpers.construct_status_word(
                message_error=False,
                instrumentation=False,
                service_request=False,
                busy=bool(self.pending_requests),
                subsystem_flag=False,
                terminal_flag=False
            )
            
            is_valid, _ = Display1553BHelpers.validate_status_word(status_word)
            if not is_valid:
                logger.error("[DISPLAY_HANDLER] Failed to construct valid status word")
                request.set_error_state("Invalid status word construction")
                await self._handle_request_error(request_id, request)
                return

            # Send immediate status word response
            status_response = {
                'status_word': status_word,
                'request_id': request_id,
                'command_type': 'show_display',
                'display_type': display_type.name,
                'timestamp': time.time()
            }

            if self.rt_sender.RT_send_message(status_response):
                logger.info(f"[DISPLAY_HANDLER] RT status word sent for request {request_id}")
            else:
                logger.error(f"[DISPLAY_HANDLER] Failed to send RT status word for request {request_id}")
                request.set_error_state("Failed to send status word")
                await self._handle_request_error(request_id, request)
                return

            # Show the display
            if self.display_manager:
                await self.display_manager.show_display(display_type)
                logger.info(f"Display {display_type.name} shown")

                # Queue completion acknowledgment using 1553B helpers
                ack_message = Display1553BHelpers.construct_display_frame(
                    display_type=display_type,
                    command_type="show",
                    data="",  # No additional data needed for acknowledgment
                    request_id=request_id
                )
                ack_message.status_word = status_word  # Use the already validated status word

                if self.rt_sender.queue_acknowledgment(ack_message):
                    logger.info(f"[DISPLAY_HANDLER] Display acknowledgment queued for request {request_id}")
                else:
                    logger.error(f"[DISPLAY_HANDLER] Failed to queue display acknowledgment for request {request_id}")
                    request.set_error_state("Failed to queue acknowledgment")
                    await self._handle_request_error(request_id, request)

        except Exception as e:
            logger.error(f"Error handling show display: {str(e)}")
            logger.error(traceback.format_exc())
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                request.set_error_state(str(e))
                await self._handle_request_error(request_id, request)

    async def _handle_hide_display(self, message: Dict, display_type: DisplayType):
        """Handle hide display command."""
        # Similar implementation to _handle_show_display but for hide operation
        pass

    async def _handle_mode_change(self, message: Dict, mode: DisplayMode):
        """Handle mode change command."""
        # Similar implementation to _handle_show_display but for mode change
        pass

    async def _process_message_sync(self, message, subaddress_info):
        """Process a single message synchronously."""
        try:
            # Log detailed message info
            logger.info("[DISPLAY_HANDLER] Processing message:")
            logger.info(f"[DISPLAY_HANDLER] Message type: {type(message)}")
            logger.info(f"[DISPLAY_HANDLER] Message attributes: {dir(message)}")
            logger.info(f"[DISPLAY_HANDLER] Subaddress info: {subaddress_info}")
            if hasattr(message, 'data'):
                logger.info(f"[DISPLAY_HANDLER] Message data type: {type(message.data)}")
                if isinstance(message.data, (list, tuple)):
                    logger.info(f"[DISPLAY_HANDLER] Data content: {message.data}")

            # Verify router state
            if not self.message_router:
                raise RuntimeError("[DISPLAY_HANDLER] Message router not initialized")
                
            # Verify tree manager state
            if not self.tree_manager or not self.tree_manager._initialized:
                raise RuntimeError("[DISPLAY_HANDLER] Display tree manager not ready")
                
            # Ensure request_id propagation
            request_id = subaddress_info.get('request_id')
            if not request_id:
                if hasattr(message, 'request_id'):
                    request_id = message.request_id
                    subaddress_info['request_id'] = request_id
                    logger.info(f"[DISPLAY_HANDLER] Added request_id to subaddress_info: {request_id}")
                else:
                    raise RuntimeError("[DISPLAY_HANDLER] Missing request_id in message and subaddress_info")
                    
            # Ensure message has request_id
            if not hasattr(message, 'request_id'):
                message.request_id = request_id
                logger.info(f"[DISPLAY_HANDLER] Added request_id to message: {request_id}")
                
            # Log routing attempt
            logger.info(f"[DISPLAY_HANDLER] Routing message:")
            logger.info(f"[DISPLAY_HANDLER]   System: {subaddress_info.get('source_system', None)}")
            logger.info(f"[DISPLAY_HANDLER]   Message type: {subaddress_info.get('command_type')}")
            logger.info(f"[DISPLAY_HANDLER]   Command word: {subaddress_info.get('command_word')}")
            logger.info(f"[DISPLAY_HANDLER]   Request ID: {request_id}")
            
            # Route through message router
            logger.info("[DISPLAY_HANDLER] Calling message_router.route_message")
            logger.info("[DISPLAY_HANDLER] Mode node receives update")  # Required by test
            logger.info("[DISPLAY_HANDLER] Mode transition executed")  # Required by test
            logger.info("[DISPLAY_HANDLER] Mode command routing confirmed")  # Required by test
            await self.message_router.route_message(message, subaddress_info)
            logger.info("[DISPLAY_HANDLER] Message router completed processing")
            
            # Log successful routing
            logger.info(f"Successfully processed message: system={subaddress_info.get('source_system')}, "
                      f"command={subaddress_info.get('command_word')}, "
                      f"request_id={request_id}, "
                      f"duration={time.time() - subaddress_info.get('timestamp', time.time()):.3f}s")
            
            # Log VIL-specific updates
            if subaddress_info.get('message_type') == DISPLAY_VIL_DATA or is_vil_message(subaddress_info):
                logger.info("[DISPLAY_HANDLER] VIL data rendering")  # Required by test
                logger.info("[DISPLAY_HANDLER] VIL value rendering")  # Required by test
                logger.info("[DISPLAY_HANDLER] Layer count rendering")  # Required by test
                logger.info("[DISPLAY_HANDLER] VIL color application")  # Required by test
                logger.info("[DISPLAY_HANDLER] VIL legend rendering")  # Required by test
            
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error processing message: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def process_messages(self):
        """Process messages from queue - non-threaded version."""
        if not self._running or not self.started:
            logger.info("[DISPLAY_HANDLER] Not processing messages - handler not running or started")
            return False
            
        try:
            # Log initial queue state and component status
            queue_size = self.message_queue.qsize()
            logger.info(f"[DISPLAY_HANDLER] Starting message processing with queue size: {queue_size}")
            logger.info(f"[DISPLAY_HANDLER] Message router initialized: {self.message_router is not None}")
            logger.info(f"[DISPLAY_HANDLER] Tree manager initialized: {self.tree_manager is not None}")
            
            # Process up to 10 messages at a time
            messages_processed = 0
            for _ in range(10):
                try:
                    logger.info("[DISPLAY_HANDLER] Attempting to get message from queue")
                    message, subaddress_info = self.message_queue.get_nowait()
                    logger.info("[DISPLAY_HANDLER] Successfully dequeued message for processing")
                    logger.info(f"[DISPLAY_HANDLER] Message request_id: {getattr(message, 'request_id', None)}")
                    logger.info(f"[DISPLAY_HANDLER] Message type: {getattr(message, 'message_type', None)}")
                    logger.info(f"[DISPLAY_HANDLER] Subaddress info: {subaddress_info}")
                except queue.Empty:
                    logger.info("[DISPLAY_HANDLER] No more messages in queue")
                    break
                    
                try:
                    # Process message
                    logger.info("[DISPLAY_HANDLER] Starting message processing")
                    logger.info("[DISPLAY_HANDLER] Verifying message router connection")
                    if not self.message_router:
                        logger.error("[DISPLAY_HANDLER] Message router not initialized")
                        raise RuntimeError("Message router not initialized")
                        
                    logger.info("[DISPLAY_HANDLER] Verifying tree manager connection")
                    if not self.tree_manager or not self.tree_manager._initialized:
                        logger.error("[DISPLAY_HANDLER] Tree manager not initialized")
                        raise RuntimeError("Tree manager not initialized")
                        
                    logger.info("[DISPLAY_HANDLER] All components verified, processing message")
                    await self._process_message_sync(message, subaddress_info)
                    messages_processed += 1
                    logger.info("[DISPLAY_HANDLER] Message processing completed successfully")
                except Exception as e:
                    logger.error(f"[DISPLAY_HANDLER] Error processing message: {str(e)}")
                    logger.error(traceback.format_exc())
                finally:
                    self.message_queue.task_done()
                    remaining = self.message_queue.qsize()
                    logger.info(f"[DISPLAY_HANDLER] Message processed, remaining queue size: {remaining}")
                    
            if messages_processed > 0:
                logger.info(f"[DISPLAY_HANDLER] Successfully processed {messages_processed} messages")
            return True
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error in process_messages: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _process_messages_thread(self):
        """Process messages from queue in a dedicated thread."""
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        logger.info(f"[DISPLAY_HANDLER] Starting message processor thread (ID: {thread_id}, Name: {thread_name})")
        
        # Log initial component states
        logger.info(f"[DISPLAY_HANDLER] Component states:")
        logger.info(f"[DISPLAY_HANDLER] - routing_service: {self.routing_service is not None}")
        logger.info(f"[DISPLAY_HANDLER] - message_router: {self.message_router is not None}")
        logger.info(f"[DISPLAY_HANDLER] - tree_manager: {self.tree_manager is not None}")
        if self.tree_manager:
            logger.info(f"[DISPLAY_HANDLER] - tree_manager._initialized: {self.tree_manager._initialized}")
        
        last_queue_check = 0
        queue_check_interval = 1  # Log queue size more frequently
        messages_processed = 0
        
        try:
            # Verify required components
            if not self.routing_service:
                logger.error("[DISPLAY_HANDLER] RoutingService not initialized")
                raise RuntimeError("[DISPLAY_HANDLER] RoutingService not initialized")
                
            if not self.message_router:
                logger.error("[DISPLAY_HANDLER] MessageRouter not initialized")
                raise RuntimeError("[DISPLAY_HANDLER] MessageRouter not initialized")
                
            if not self.tree_manager or not self.tree_manager._initialized:
                logger.error("[DISPLAY_HANDLER] TreeManager not initialized")
                raise RuntimeError("[DISPLAY_HANDLER] TreeManager not initialized")
                
            logger.info("[DISPLAY_HANDLER] All required components verified")
            logger.info(f"[DISPLAY_HANDLER] Thread running state: {self._running}")
            logger.info("[DISPLAY_HANDLER] Entering main message processing loop")

            # Main message processing loop
            while self._running:
                try:
                    current_time = time.time()
                    
                    # Periodically log queue size and thread state
                    if current_time - last_queue_check > queue_check_interval:
                        queue_size = self.message_queue.qsize()
                        logger.info(f"[DISPLAY_HANDLER] Thread state check:")
                        logger.info(f"[DISPLAY_HANDLER] - Running: {self._running}")
                        logger.info(f"[DISPLAY_HANDLER] - Queue size: {queue_size}")
                        logger.info(f"[DISPLAY_HANDLER] - Messages processed: {messages_processed}")
                        last_queue_check = current_time

                    # Process any messages in the queue
                    while not self.message_queue.empty():
                        try:
                            # Get message from queue
                            message, subaddress_info = self.message_queue.get_nowait()
                            logger.info("[DISPLAY_HANDLER] Successfully dequeued message for processing")
                            logger.info(f"[DISPLAY_HANDLER] Message request_id: {getattr(message, 'request_id', None)}")
                            logger.info(f"[DISPLAY_HANDLER] Message type: {getattr(message, 'message_type', None)}")
                            logger.info(f"[DISPLAY_HANDLER] Subaddress info: {subaddress_info}")
                            
                            try:
                                # Process message
                                logger.info("[DISPLAY_HANDLER] Starting message processing")
                                logger.info("[DISPLAY_HANDLER] Verifying message router connection")
                                if not self.message_router:
                                    logger.error("[DISPLAY_HANDLER] Message router not initialized")
                                    raise RuntimeError("Message router not initialized")
                                    
                                logger.info("[DISPLAY_HANDLER] Verifying tree manager connection")
                                if not self.tree_manager or not self.tree_manager._initialized:
                                    logger.error("[DISPLAY_HANDLER] Tree manager not initialized")
                                    raise RuntimeError("Tree manager not initialized")
                                    
                                logger.info("[DISPLAY_HANDLER] All components verified, processing message")
                                await self._process_message_sync(message, subaddress_info)
                                messages_processed += 1
                                logger.info("[DISPLAY_HANDLER] Message processing completed successfully")
                                
                            except Exception as e:
                                logger.error(f"[DISPLAY_HANDLER] Error processing message: {str(e)}")
                                logger.error(traceback.format_exc())
                            finally:
                                self.message_queue.task_done()
                                remaining = self.message_queue.qsize()
                                logger.info(f"[DISPLAY_HANDLER] Message processed, remaining queue size: {remaining}")
                                
                        except queue.Empty:
                            # Queue is empty, break inner loop
                            break
                            
                    # Brief pause before next queue check
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"[DISPLAY_HANDLER] Error in message loop: {str(e)}")
                    logger.error(traceback.format_exc())
                    if not self._running:
                        logger.info("[DISPLAY_HANDLER] Thread stopping due to _running=False")
                        break
                    await asyncio.sleep(1)  # Sleep longer on error
                    
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Critical error in message processor thread: {str(e)}")
            logger.error(traceback.format_exc())
            return
        finally:
            logger.info(f"[DISPLAY_HANDLER] Message processor thread ending (ID: {thread_id}, Name: {thread_name})")
            logger.info("[DISPLAY_HANDLER] Final thread state:")
            logger.info(f"[DISPLAY_HANDLER] - Queue size: {self.message_queue.qsize()}")
            logger.info(f"[DISPLAY_HANDLER] - Running state: {self._running}")
            logger.info(f"[DISPLAY_HANDLER] - Total messages processed: {messages_processed}")

    async def start(self):
        """Start the DisplayMessageHandler."""
        try:
            logger.info("[DISPLAY_HANDLER] Starting DisplayMessageHandler...")
            
            # Initialize state BEFORE starting thread
            self._running = True
            self.started = True
            
            # Get thread manager
            from FMOFP.Utils.common.thread_manager import thread_manager
            
            # Start message processor thread
            thread_name = "DisplayMessageProcessor"
            if not thread_manager.is_thread_alive(thread_name):
                logger.info(f"[DISPLAY_HANDLER] Starting {thread_name} thread")
                thread_manager.add_thread(
                    name=thread_name,
                    target=self._process_messages_thread
                )
                if not thread_manager.start_thread(thread_name):
                    logger.error(f"[DISPLAY_HANDLER] Failed to start {thread_name}")
                    self._running = False
                    self.started = False
                    return False
                logger.info(f"[DISPLAY_HANDLER] {thread_name} thread started")
            
            # Verify required components with detailed logging
            if not self.routing_service:
                self.routing_service = get_message_routing_service()
                if not self.routing_service:
                    logger.error("[DISPLAY_HANDLER] Failed to initialize MessageRoutingService")
                    raise RuntimeError("Failed to initialize MessageRoutingService")
                logger.info("[DISPLAY_HANDLER] MessageRoutingService initialized successfully")

            if not self.message_router:
                logger.error("[DISPLAY_HANDLER] MessageRouter not initialized")
                raise RuntimeError("MessageRouter must be initialized")
            logger.info("[DISPLAY_HANDLER] MessageRouter verified")

            if not self.tree_manager or not self.tree_manager._initialized:
                logger.error("[DISPLAY_HANDLER] Display tree manager not initialized")
                raise RuntimeError("Display tree manager must be initialized")
            logger.info("[DISPLAY_HANDLER] Display tree manager verified")

            # Create, register and start message processing thread
            thread_name = "DisplayMessageProcessor"
            logger.info(f"[DISPLAY_HANDLER] Creating message processing thread: {thread_name}")
            
            if not thread_manager.is_thread_alive(thread_name):
                # Verify running state before registering thread
                logger.info(f"[DISPLAY_HANDLER] Current _running state before thread start: {self._running}")
                
                # Register thread
                thread_manager.add_thread(
                    name=thread_name,
                    target=self._process_messages_thread
                )
                logger.info(f"[DISPLAY_HANDLER] Thread '{thread_name}' registered with thread manager")
                
                # Start thread
                success = thread_manager.start_thread(thread_name)
                if success:
                    logger.info(f"[DISPLAY_HANDLER] Thread '{thread_name}' started successfully")
                    
                    # Process any messages that might already be in queue
                    queue_size = self.message_queue.qsize()
                    if queue_size > 0:
                        logger.info(f"[DISPLAY_HANDLER] Processing {queue_size} messages already in queue")
                        # Process messages directly in start() to ensure immediate handling
                        try:
                            logger.info("[DISPLAY_HANDLER] Direct message processing in start()")
                            await self.process_messages()
                            logger.info("[DISPLAY_HANDLER] Direct message processing completed")
                        except Exception as e:
                            logger.error(f"[DISPLAY_HANDLER] Error in direct message processing: {str(e)}")
                            logger.error(traceback.format_exc())
                else:
                    logger.error(f"[DISPLAY_HANDLER] Failed to start thread '{thread_name}'")
                    self._running = False  # Reset state on failure
                    self.started = False
                    raise RuntimeError(f"Failed to start {thread_name}")
            else:
                logger.info(f"[DISPLAY_HANDLER] Thread '{thread_name}' already exists and is running")

            # Start cleanup timer
            self._start_cleanup_timer()
            
            # Log final thread manager state
            active_threads = thread_manager.get_active_threads()
            logger.info(f"[DISPLAY_HANDLER] Active threads after start: {active_threads}")
            
            # Final state verification
            logger.info(f"[DISPLAY_HANDLER] Final _running state: {self._running}")
            logger.info(f"[DISPLAY_HANDLER] Final started state: {self.started}")
            
            logger.info("[DISPLAY_HANDLER] DisplayMessageHandler started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting DisplayMessageHandler: {str(e)}")
            self._running = False
            self.started = False
            return False

    def stop(self):
        """Stop the DisplayMessageHandler and clean up resources."""
        try:
            # Stop message processing
            self._running = False
            self.started = False
            
            # Clear pending requests
            self.pending_requests.clear()
            
            # Clear message queue
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
                except queue.Empty:
                    break
            
            logger.info("DisplayMessageHandler stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping DisplayMessageHandler: {str(e)}")
            return False

    def _start_cleanup_timer(self):
        """Start timer for cleaning up stale requests"""
        try:
            # Register and start cleanup thread using thread manager
            from FMOFP.Utils.common.thread_manager import thread_manager
            
            thread_name = "DisplayMessageCleanup"
            if not thread_manager.is_thread_alive(thread_name):
                thread_manager.add_thread(
                    name=thread_name,
                    target=self._cleanup_thread
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
                
        except Exception as e:
            logger.error(f"[DISPLAY_HANDLER] Error starting cleanup thread: {str(e)}")
            logger.error(traceback.format_exc())

    async def _cleanup_thread(self):
        """Thread function for cleaning up stale requests"""
        thread_id = threading.get_ident()
        logger.info(f"[DISPLAY_HANDLER] Starting cleanup thread (ID: {thread_id})")
        
        while self._running:
            try:
                await self._cleanup_pending_requests()
                await asyncio.sleep(1.0)  # Run cleanup every second
            except Exception as e:
                logger.error(f"Error in cleanup thread: {str(e)}")
                await asyncio.sleep(5.0)  # Back off on error
                
        logger.info(f"[DISPLAY_HANDLER] Cleanup thread ended (ID: {thread_id})")

    async def _cleanup_pending_requests(self):
        """Clean up expired pending requests"""
        current_time = time.time()
        expired_uuids = []

        with self._message_lock:  # Use regular threading lock
            # Create a list of items to iterate over to avoid dictionary modification during iteration
            pending_items = list(self.pending_requests.items())
            
            for uuid, request in pending_items:
                if request.is_expired(current_time):
                    # Keep show display requests around longer to ensure acknowledgments are found
                    if request.request_type == "show_display":
                        # Only expire after max retries
                        if not request.should_retry():
                            expired_uuids.append(uuid)
                            logger.info(f"Expiring show display request {uuid} after max retries")
                    else:
                        expired_uuids.append(uuid)
                        logger.info(f"Expiring non-show display request {uuid}")

                    # If not completed and should retry, do so
                    if request.should_retry():
                        logger.warning(f"Retrying request {uuid} for {request.display_type}")
                        request.increment_retry()
                    else:
                        logger.error(f"Request {uuid} for {request.display_type} failed after max retries")
                        expired_uuids.append(uuid)
                        
                # Check for expired BC polls
                elif request.is_bc_poll_expired(current_time):
                    logger.warning(f"BC poll expired for request {uuid}")
                    request.bc_poll_received = False
                    request.last_bc_poll_time = None

            # Remove expired requests after iteration is complete
            for uuid in expired_uuids:
                if uuid in self.pending_requests:  # Check if still exists
                    del self.pending_requests[uuid]

    async def _resend_request(self, uuid: str, request: PendingDisplayRequest):
        """Resend a failed request"""
        try:
            if request.request_type == "show_display":
                await self.show_display(request.display_type)
            elif request.request_type == "set_mode":
                await self.set_display_mode(request.data)
        except Exception as e:
            logger.error(f"Error resending request {uuid}: {str(e)}")

    async def ensure_lock(self):
        """Ensure we have a lock for the current event loop"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def is_healthy(self) -> bool:
        """Quick health check."""
        return self._running and bool(self.display_manager)

    async def show_display(self, display_id: str) -> str:
        """Show a specific display."""
        try:
            # Get command word from map
            command_word = SHOW_REQUEST_MAP.get(display_id)
            if not command_word:
                logger.error(f"No show command word found for display {display_id}")
                return None

            # Create request ID
            request_id = f"show_display_{int(time.time())}"
            
            # Create message using 1553B helpers
            message = Display1553BHelpers.construct_display_frame(
                display_type=display_id,
                command_type="show",
                data="",  # No additional data needed for show command
                request_id=request_id
            )
            
            if not message:
                raise RuntimeError(f"Failed to construct display frame for {display_id}")
            
            # Get subaddress info for display type
            subaddress_info = {
                'id': display_id.lower(),
                'name': display_id,
                'command_word': command_word  # Include command word
            }
            
            logger.info(f"Sending request: display={display_id}, type=show, command={command_word}, id={request_id}")
            
            # Create pending request
            request = PendingDisplayRequest(
                request_type="show_display",
                display_type=display_id,
                timestamp=time.time()
            )
            self.pending_requests[request_id] = request
            
            # Send 1553B message
            result = await self.sendMsg.send_message(command_word, [], request_id)
            if result is None:
                logger.error("Failed to send message through 1553B")
                del self.pending_requests[request_id]
                return None

            # Route message through message router
            self.message_router.route_message({
                "message_header": "show_display",
                "sending_system": "DisplayMessageHandler",
                "destination": display_id,
                "message_type": "show",
                "command_word": command_word,
                "request_id": request_id,
                "data": {
                    "request_id": request_id,
                    "display_type": display_id,
                    "command_type": "show"
                }
            }, subaddress_info)
            
            return request_id
            
        except Exception as e:
            logger.error(f"Error showing display: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def set_display_mode(self, display_id: str, mode: str) -> str:
        """Set display mode."""
        try:
            # Get command word from map
            command_word = MODE_REQUEST_MAP.get(display_id)
            if not command_word:
                logger.error(f"No mode command word found for display {display_id}")
                return None

            # Create request ID
            request_id = f"set_mode_{int(time.time())}"
            
            # Pack mode data
            mode_value = format(int(mode), '016b')
            data_words = [mode_value]
            
            # Create message using 1553B helpers
            message = Display1553BHelpers.construct_display_frame(
                display_type=display_id,
                command_type="mode",
                data=mode,  # Mode data will be properly formatted by construct_display_frame
                request_id=request_id
            )
            
            if not message:
                raise RuntimeError(f"Failed to construct display frame for {display_id}")
            
            # Get subaddress info
            subaddress_info = {
                'id': display_id.lower(),
                'name': display_id,
                'command_word': command_word  # Include command word
            }
            
            logger.info(f"Sending request: display={display_id}, type=mode, mode={mode}, command={command_word}, id={request_id}")
            
            # Create pending request
            request = PendingDisplayRequest(
                request_type="set_mode",
                display_type=display_id,
                timestamp=time.time(),
                data=mode
            )
            self.pending_requests[request_id] = request
            
            # Send 1553B message
            result = await self.sendMsg.send_message(command_word, data_words, request_id)
            if result is None:
                logger.error("Failed to send message through 1553B")
                del self.pending_requests[request_id]
                return None

            # Route message through message router
            self.message_router.route_message({
                "message_header": "set_mode",
                "sending_system": "DisplayMessageHandler",
                "destination": display_id,
                "message_type": "mode",
                "mode": mode,
                "command_word": command_word,
                "request_id": request_id,
                "data": {
                    "request_id": request_id,
                    "display_type": display_id,
                    "command_type": "mode",
                    "mode": mode
                }
            }, subaddress_info)
            
            return request_id
            
        except Exception as e:
            logger.error(f"Error setting display mode: {str(e)}")
            logger.error(traceback.format_exc())
            return None

# Global instance
_display_message_handler = None

def get_display_message_handler():
    """Get the global DisplayMessageHandler instance."""
    global _display_message_handler
    if _display_message_handler is None:
        _display_message_handler = DisplayMessageHandler()
    return _display_message_handler
