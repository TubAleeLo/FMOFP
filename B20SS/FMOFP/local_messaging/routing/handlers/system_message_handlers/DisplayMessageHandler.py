"""
Display Message Handler for Local Messaging

Handles local message creation and routing for display system commands.
Similar to RadarMessageHandler but adapted for display operations.
"""

import asyncio
import threading
import traceback
import time
import json
import uuid as uuid_lib
from typing import Optional, Dict, Any, Union, List
from ..sync_handler.AsyncMessageHandler import AsyncMessageHandler
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
from FMOFP.MIL_STD_1553B.Messaging import send1553Msg
from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
from FMOFP.local_messaging.routing.response_services.data_response_services.vil_response_service import VILResponseService
from FMOFP.local_messaging.routing.response_services.data_response_services.echo_top_response_service import EchoTopResponseService
from FMOFP.Utils.logger.sys_logger import get_logger
# Import centralized message type definitions
from FMOFP.local_messaging.message_types import (
    WEATHER_RADAR_VIL_REQUEST, WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST, WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_ECHO_TOP_REQUEST, WEATHER_RADAR_ECHO_TOP_RESPONSE,
    WEATHER_RADAR_MODE_CHANGE_REQUEST, WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    DISPLAY_MODE_REQUEST, DISPLAY_MODE_RESPONSE,
    DISPLAY_DATA_REQUEST, DISPLAY_DATA_RESPONSE,
    is_vil_message, is_precipitation_message, is_mode_change_message
)

logger = get_logger()

class DisplayMessageHandler:
    # Constants for message types
    SHOW_COMMAND = 0x01
    MODE_COMMAND = 0x02
    DATA_COMMAND = 0x03

    def __init__(self):
        """Initialize display message handler."""
        self.async_handler = None
        self._initialized = False
        self.routing_service = None

        # Add tracking for processed message IDs
        self._processed_request_ids = set()
        self._processed_request_ids_lock = threading.Lock()

        # Get display response service
        from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
        self.response_service = get_display_response_service()

        # Initialize message routing service
        self.routing_service = get_message_routing_service()

        # Initialize data response services with database connection
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        radar_db = db_manager.get_system_db('radar_management')

        # Initialize VIL Response Service
        self.vil_response_service = VILResponseService(radar_db)
        logger.info(f"DisplayMessageHandler initialized with VIL Response Service, initialized state: {getattr(self.vil_response_service, '_initialized', False)}")

        # Initialize Echo Top Response Service
        self.echo_top_response_service = EchoTopResponseService(radar_db)
        logger.info(f"DisplayMessageHandler initialized with Echo Top Response Service, initialized state: {getattr(self.echo_top_response_service, '_initialized', False)}")

        # Initialize other components
        self.system_handler = None  # Will be set during async handler setup
        self.response_handlers = {}
        self.started = False
        self._thread = None
        self._processing_task = None
        self._init_lock = threading.Lock()
        self._message_lock = threading.Lock()
        self.SYSTEM_NAME = "displays"  # Centralize system name
        self.routing_service = get_message_routing_service()
        self.bc_construct = BC_construct()
        self.sendMsg = send1553Msg()  # Add send1553Msg instance
        self.pending_requests = {}  # Track pending requests

        # Add radar mode state tracking
        self._radar_mode = None  # Current radar mode
        self._radar_mode_enum = None  # Enum type for current mode
        self._previous_radar_mode = None  # Previous radar mode

    def check_health(self) -> bool:
        """Check component health status."""
        try:
            # Check if running
            if not self.started:
                return False

            # Check async handler health
            if not self.async_handler or not self.async_handler.check_health():
                return False

            # Check routing service
            if not self.routing_service:
                return False

            # Check response service
            if not self.response_service:
                return False

            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    def start(self):
        """Start the DisplayMessageHandler and initialize its components."""
        try:
            if not self.async_handler:
                raise RuntimeError("AsyncMessageHandler must be set before starting")

            # Don't try to start async handler - system manager handles that
            if not self.async_handler.started:
                logger.warning("AsyncMessageHandler not started - waiting for system manager")
                return

            # Verify routing service is set
            if not self.routing_service:
                raise RuntimeError("MessageRoutingService must be set before starting")

            # Verify response service is set
            if not self.response_service:
                raise RuntimeError("DisplayResponseService must be set before starting")

            self.started = True
            logger.info("DisplayMessageHandler started successfully")
        except Exception as e:
            logger.error(f"Error starting DisplayMessageHandler: {str(e)}")
            raise

    def set_async_handler(self, async_handler: AsyncMessageHandler):
        """Set the async handler and register message handlers."""
        if not async_handler:
            raise ValueError("async_handler cannot be None")

        with self._init_lock:
            try:
                # Log current state
                logger.info(f"Setting async handler. Current state: async_handler={self.async_handler is not None}, started={self.started}")

                # If we already have this handler and it's healthy, just return
                if self.async_handler == async_handler:
                    if self.async_handler.is_healthy():
                        logger.info("AsyncMessageHandler already set and healthy")
                        return
                    else:
                        logger.warning("Existing AsyncMessageHandler unhealthy, will reset")

                # Verify new handler is running
                logger.info(f"New async handler state: started={async_handler.started}, running={async_handler.running}")
                if not async_handler.started or not async_handler.running:
                    logger.error("AsyncMessageHandler must be started and running")
                    raise RuntimeError("AsyncMessageHandler not ready")

                # Store reference and register system
                self.async_handler = async_handler

                # Register our system and get handler
                self.system_handler = self.async_handler.register_system(self.SYSTEM_NAME)
                if not self.system_handler:
                    raise RuntimeError("Failed to register system with AsyncMessageHandler")

                # Ensure system is marked as active
                self.system_handler.active = True

                # Register message handlers
                self._register_message_handlers()

                # Start if not already started
                if not self.started:
                    self.start()

                # Verify health
                if not self.async_handler.is_healthy():
                    logger.error("AsyncMessageHandler failed health check after setup")
                    raise RuntimeError("AsyncMessageHandler not healthy after setup")

                logger.info("AsyncMessageHandler set and handlers registered successfully")

            except Exception as e:
                logger.error(f"Error setting up AsyncMessageHandler: {str(e)}")
                raise

    def _register_message_handlers(self):
        """Register message handlers with the system handler."""
        if not self.system_handler:
            raise RuntimeError("SystemHandler not set")

        # Import display command maps
        from FMOFP.local_messaging.display_command_map import (
            DISPLAY_TYPES, SHOW_REQUEST_MAP, MODE_REQUEST_MAP, DATA_REQUEST_MAP, STATUS_REQUEST_MAP
        )

        # Register FMS message handlers
        logger.info("[LOCAL_DISPLAYMESSAGEHANDLER] Registering FMS handlers")

        # Register for FMS message types
        fms_msg_types = [
            "fms_flightData",        # Flight data (attitude, velocity, etc.)
            "fms_attitudeUpdateRequest",  # Attitude update requests
            "fms_navigationUpdateRequest", # Navigation updates
            "fms_statusResponse",    # Status responses
            "fms_commandResponse"    # Command responses
        ]

        for msg_type in fms_msg_types:
            self.system_handler.register_handler(
                msg_type,
                lambda msg: asyncio.create_task(self._handle_fms_message(msg))
            )
            logger.info(f"[DISPLAY] Registered handler for FMS message type: {msg_type}")

        # Register weather radar handlers
        logger.info("[LOCAL_DISPLAYMESSAGEHANDLER] Registering weather radar handlers")

        # Helper to check if message is for display system
        def is_display_message(message: Union[Dict, MIL_STD_1553B_Message]) -> bool:
            # Get display system RT address from address_utils
            from FMOFP.local_messaging.address_utils import get_rt_address
            display_rt = get_rt_address('displays')

            if isinstance(message, MIL_STD_1553B_Message):
                return message.rt_address == display_rt
            elif isinstance(message, dict):
                rt_addr = message.get('rt_address')
                return rt_addr == display_rt if rt_addr is not None else False
            return False

        # Register for all weather radar message types with RT address check
        weather_msg_types = [
            "weather_radar_display",           # Display updates
            "weather_radarCommand",            # Commands
            "weather_radarResponse",           # Responses
            "weather_radarModeChange",         # Mode changes
            "weather_radarModeUpdate",         # Mode updates
            "weather_radarModeRequest",        # Mode requests
            "display_mode_request",            # Display mode requests
            "radarPrecipitationCompletion",    # Precipitation completion messages
            "weather_radarPrecipitationResponse" # Precipitation data responses
        ]

        for msg_type in weather_msg_types:
            self.system_handler.register_handler(
                msg_type,
                lambda msg: asyncio.create_task(self._handle_weather_display(msg)) if is_display_message(msg) else None
            )
            # logged in the loop above
            # logger.info(f"[DISPLAY] Registered handler for message type: {msg_type}")

        # Register for both radar and display mode commands
        mode_commands = [
            format(int('0x2005', 16), '016b'),  # weather_radarModeChangeRequest
            format(int('0x7003', 16), '016b')   # display_mode_request
        ]

        for command_word in mode_commands:
            self.system_handler.register_handler(
                command_word,
                lambda msg: asyncio.create_task(self._handle_weather_display(msg))
            )
            # logged in the loop above
            # logger.info(f"[DISPLAY] Registered handler for mode command: {command_word}")

        # Register handlers for each display type
        for display_id in DISPLAY_TYPES:
            # Show display commands
            show_request = SHOW_REQUEST_MAP[display_id]
            show_response = show_request.replace('REQUEST', 'RESPONSE')
            self.system_handler.register_handler(
                show_request,
                lambda msg, d=display_id: asyncio.create_task(self._handle_show_display(msg, d))
            )
            self.system_handler.register_handler(
                show_response,
                lambda msg, d=display_id: asyncio.create_task(self._handle_show_display(msg, d))
            )

            # Mode change commands
            mode_request = MODE_REQUEST_MAP[display_id]
            mode_response = mode_request.replace('REQUEST', 'RESPONSE')
            self.system_handler.register_handler(
                mode_request,
                lambda msg, d=display_id: asyncio.create_task(self._handle_set_mode(msg, d))
            )
            self.system_handler.register_handler(
                mode_response,
                lambda msg, d=display_id: asyncio.create_task(self._handle_set_mode(msg, d))
            )

            # Data commands
            data_request = DATA_REQUEST_MAP[display_id]
            data_response = data_request.replace('REQUEST', 'RESPONSE')
            self.system_handler.register_handler(
                data_request,
                lambda msg, d=display_id: asyncio.create_task(self._handle_data_request(msg, d))
            )
            self.system_handler.register_handler(
                data_response,
                lambda msg, d=display_id: asyncio.create_task(self._handle_data_request(msg, d))
            )

            # Status commands
            status_request = STATUS_REQUEST_MAP[display_id]
            status_response = status_request.replace('REQUEST', 'RESPONSE')
            self.system_handler.register_handler(
                status_request,
                lambda msg, d=display_id: asyncio.create_task(self._handle_status_word(msg))
            )
            self.system_handler.register_handler(
                status_response,
                lambda msg, d=display_id: asyncio.create_task(self._handle_status_word(msg))
            )
            logger.info(f"[DISPLAY] Registered handler for status command: {status_request}")

        # Register handler for display status word acknowledgments
        # Only handle messages with RT address 11 (01011) and display subaddresses
        def is_display_status_word(message: Dict) -> bool:
            # Extract RT address from status word
            if 'status_word' in message:
                status_word = message['status_word']
                if len(status_word) >= 8:  # Need at least sync + RT address
                    rt_addr = status_word[3:8]  # RT address is bits 4-8

                    # Get display system RT address from address_utils
                    from FMOFP.local_messaging.address_utils import get_rt_address
                    try:
                        displays_rt = get_rt_address('displays')
                        displays_rt_bin = format(displays_rt, '05b')  # Convert to 5-bit binary string
                        return rt_addr == displays_rt_bin  # Compare binary strings
                    except Exception as e:
                        logger.error(f"[DISPLAY] Error getting displays RT address: {e}")
                        traceback.print_exc()
            return False

        # Register handler with RT address check
        self.system_handler.register_handler(
            "status_word",
            lambda msg: asyncio.create_task(self._handle_status_word(msg)) if is_display_status_word(msg) else None
        )



    async def _handle_data_request(self, message: Union[Dict, str], display_id: str):
        """Handle data request command."""
        try:
            # Import display types mapping
            from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

            # Get display type from ID
            display_type = DISPLAY_TYPES[display_id].name

            # Extract request_id and data_type from message
            if isinstance(message, dict):
                request_id = message.get('request_id')
                data_type = message.get('data', {}).get('type')

                # Also check message.data for request_id if not found at top level
                if not request_id and isinstance(message.get('data'), dict):
                    request_id = message['data'].get('request_id')
            else:
                # For string messages, parse command type from message
                data_type = message
                # String messages must have request_id passed separately
                request_id = None

            # Validate required fields
            if not display_type:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Data request missing display type")
                return

            if not data_type:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Data request missing data type")
                return

            if not request_id:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Data request missing request ID")
                return

            # Route command to storage
            command_data = {
                'command_type': 'data_request',
                'display_type': display_type,
                'data_type': data_type,
                'request_id': request_id,  # Now properly propagated
                'timestamp': time.time(),
                'status': 'acknowledged'
            }

            logger.info(f"Processing data request: type={data_type}, request_id={request_id}")

            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Data request processed for {display_type} - {data_type}")

        except Exception as e:
            logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error handling data request: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_data_subscription(self, message: Optional[Dict]):
        """Handle data subscription command."""
        try:
            display_type = message.get('display') if message else None
            request_id = message.get('request_id') if message else None
            data = message.get('data', {}) if message else {}
            data_type = data.get('type')
            subscribe = data.get('subscribe', True)

            if not all([display_type, data_type]):
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Data subscription missing required fields")
                return

            # Route command to storage
            command_data = {
                'command_type': 'data_subscription',
                'display_type': display_type,
                'data_type': data_type,
                'subscribe': subscribe,
                'request_id': request_id,
                'timestamp': time.time(),
                'status': 'acknowledged'
            }

            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            action = "Subscription" if subscribe else "Unsubscription"
            logger.info(f"Data {action.lower()} processed for {display_type} - {data_type}")

        except Exception as e:
            logger.error(f"Error handling data subscription: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_show_display(self, message: Optional[Dict], display_id: str):
        """Handle show display command."""
        try:
            # Import display types mapping
            from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

            # Get display type from ID
            display_type = DISPLAY_TYPES[display_id].name
            request_id = message.get('request_id') if message else None

            if not display_type:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Show display command missing display type")
                return

            # Route command to storage
            command_data = {
                'command_type': 'show_display',
                'display_type': display_type,
                'request_id': request_id,
                'timestamp': time.time(),
                'status': 'acknowledged'
            }

            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Show display command processed for {display_type}")

        except Exception as e:
            logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error handling show display command: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_set_mode(self, message: Optional[Dict], display_id: str):
        """Handle set display mode command."""
        try:
            # Import display types mapping
            from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

            # Get display type from ID
            display_type = DISPLAY_TYPES[display_id].name

            # Handle both dict and string message formats
            if isinstance(message, dict):
                mode_value = message.get('data')
                request_id = message.get('request_id')
            else:
                # For string messages, use message as mode value
                mode_value = message
                request_id = None

            if mode_value is None:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Set mode command missing mode value")
                return

            try:
                # If mode_value is already a RadarDisplayMode enum value, use it directly
                if isinstance(mode_value, int) and 0 <= mode_value < len(RadarDisplayMode):
                    mode = RadarDisplayMode(mode_value)
                else:
                    # Otherwise try to get enum by name
                    mode = RadarDisplayMode[str(mode_value)]
            except ValueError:
                logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid mode value: {mode_value}")
                return

            # Route command to storage
            command_data = {
                'command_type': 'set_mode',
                'mode': mode.name,
                'request_id': request_id,
                'timestamp': time.time(),
                'status': 'acknowledged'
            }

            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Set mode command processed: {mode.name}")

        except Exception as e:
            logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error handling set mode command: {str(e)}")
            logger.error(traceback.format_exc())

    async def _handle_status_word(self, message: Optional[Dict]):
        """Handle status word acknowledgment."""
        try:
            request_id = message.get('request_id') if message else None
            command_type = message.get('command_type') if message else None

            if not request_id:
                logger.error("[LOCAL_DISPLAYMESSAGEHANDLER] Status word missing request ID")
                return

            # Route status word to storage
            status_data = {
                'command_type': command_type,
                'request_id': request_id,
                'timestamp': time.time(),
                'status': 'acknowledged'
            }

            await self.routing_service.route_status_word(status_data)
            logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Status word routed for request {request_id}")

        except Exception as e:
            logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error handling status word: {str(e)}")
            logger.error(traceback.format_exc())


        #### Might be a problem with this method ###
    async def send_request(self, display_type: str, command_type: str, command_data: Any = None) -> Optional[str]:
        """Send a display command request."""
        try:
            # Import command word helper
            from FMOFP.local_messaging.display_command_map import (
                DISPLAY_TYPES, get_display_command_word
            )

            # Convert display type to lowercase ID
            display_id = display_type.lower()
            if display_id not in DISPLAY_TYPES:
                logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid display type: {display_type}")
                return None

            # Get proper command word
            try:
                command_word = get_display_command_word(display_id, command_type)
            except ValueError as e:
                logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error getting command word: {e}")
                return None

            # Create request data
            request_data = {
                'display': display_type,
                'type': command_type,
                'data': command_data
            }

            # Generate request_id
            request_id = str(uuid_lib.uuid4())
            logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Sending request: display={display_type}, type={command_type}, command={command_word}, id={request_id}")

            # Store pending request
            self.pending_requests[request_id] = {
                'request_type': command_type,
                'display_type': display_type,
                'timestamp': time.time(),
                'data': command_data
            }

            # NOTE (production readiness re-analysis, August 2026): this class has
            # no response-handling path that ever reads or removes an entry from
            # self.pending_requests on success -- the only other reference to it
            # anywhere in this 2700+ line file is the del a few lines below on the
            # *send failure* branch. This class also has a separate, apparently
            # unfinished response_handlers/register_response_handler()/
            # handle_response() mechanism (a few hundred lines below), but that is
            # ALSO dead: grepping the whole codebase found zero callers of
            # register_response_handler() or handle_response() -- neither dict-
            # based mechanism actually correlates a response back to a sent
            # request in this class today. pending_requests was therefore
            # effectively write-only on the success path: every successful
            # send_request() call left a permanent entry here for the life of the
            # process, an unbounded-growth leak confirmed by grepping this entire
            # file for every reference to pending_requests. Rather than fabricate
            # a full TTL/response-handling mechanism that doesn't otherwise exist
            # in this class, applied the same bounded-cap-and-trim pattern already
            # used successfully a few hundred lines below for
            # self._processed_request_ids in this same file, to stop the
            # unbounded growth without changing any other behavior.
            if len(self.pending_requests) > 1000:
                oldest_first = sorted(self.pending_requests.items(), key=lambda kv: kv[1].get('timestamp', 0))
                self.pending_requests = dict(oldest_first[-500:])

            # Send 1553B message
            data_words = []
            if command_type == 'show':
                # Show command: 0x01 in lower byte
                data_word = self.SHOW_COMMAND
                data_words = [format(data_word, '016b')]
            elif (command_type == 'mode' or command_type == 'mode_change') and command_data is not None:
                # Get mode value from RadarDisplayMode enum or command_data
                try:
                    # Initialize mode_value
                    mode_value = None

                    # Case 1: command_data is a RadarDisplayMode enum directly
                    if isinstance(command_data, RadarDisplayMode):
                        mode_value = command_data.value
                        logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Using direct RadarDisplayMode enum value: {mode_value}")
                    # Case 2: command_data is a dict with 'mode' key
                    elif isinstance(command_data, dict) and 'mode' in command_data:
                        mode_name = command_data['mode']
                        mode_enum = RadarDisplayMode[mode_name]
                        mode_value = mode_enum.value
                        logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Extracted mode {mode_name} (value: {mode_value}) from command_data dict")
                    # Case 3: command_data is a string (mode name)
                    elif isinstance(command_data, str):
                        mode_enum = RadarDisplayMode[command_data]
                        mode_value = mode_enum.value
                        logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Extracted mode value {mode_value} from string: {command_data}")
                    # Case 4: command_data is an integer (direct mode value)
                    elif isinstance(command_data, int):
                        mode_value = command_data
                        logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Using direct integer mode value: {mode_value}")
                    else:
                        logger.error(f"Unsupported command_data type: {type(command_data)}")
                        return None

                    # Validate mode_value
                    if mode_value is None:
                        logger.error(f"Failed to extract mode value from command_data: {command_data}")
                        return None

                except (KeyError, ValueError) as e:
                    logger.error(f"Invalid mode value: {command_data}, error: {e}")
                    return None

                # Mode value in upper byte, MODE_COMMAND (0x02) in lower byte
                data_word = (mode_value << 8) | self.MODE_COMMAND
                data_words = [format(data_word, '016b')]
                logger.info(f"[LOCAL_DISPLAYMESSAGEHANDLER] Created data word for mode {mode_value}: {data_words[0]}")
            elif command_type == 'data':
                # For data requests, include request_id in command data
                if isinstance(command_data, dict):
                    command_data['request_id'] = request_id
                else:
                    command_data = {'type': command_data, 'request_id': request_id}
                # Data command: 0x03 in lower byte
                data_word = self.DATA_COMMAND
                data_words = [format(data_word, '016b')]

            # Create metadata for the message
            metadata = {
                'message_header': command_type,
                'message_type': f'display_{command_type}',
                'command_type': command_type,
                'command_name': f'DISPLAY_{command_type.upper()}',
                'sending_system': 'DisplayMessageHandler',
                'destination': display_type,
                'request_id': request_id
            }

            # If command_data is a dict, add any additional metadata
            if isinstance(command_data, dict):
                # Add mode information if available
                if 'mode' in command_data:
                    metadata['mode'] = command_data['mode']

                # Add any other relevant fields
                for key in ['force_update', 'update_visual']:
                    if key in command_data:
                        metadata[key] = command_data[key]

            # Send through BC with metadata
            result = await self.sendMsg.send_message(command_word, data_words, request_id, metadata)
            if result is None:
                logger.error("Failed to send message through 1553B")
                del self.pending_requests[request_id]  # Clean up pending request
                return None

            return request_id

        except Exception as e:
            logger.error(f"Error sending display request: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def show_display(self, display_type: str) -> Optional[str]:
        """
        Send request to show a specific display.

        Args:
            display_type: Display identifier (e.g., 'pfd', 'mfd'). Required.

        Returns:
            Request ID if successful, None otherwise

        Raises:
            ValueError: If display_type is not provided or invalid
        """
        if not display_type:
            raise ValueError("display_type is required")

        # Import display types mapping
        from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

        # Convert to lowercase for comparison
        display_id = display_type.lower()
        if display_id not in DISPLAY_TYPES:
            raise ValueError(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid display type: {display_type}")

        # Log the show request
        logger.info(f"Showing display {display_type}")

        return await self.send_request(
            display_type=display_id,  # Use lowercase ID for consistency
            command_type='show',
            command_data=None
        )

    async def set_display_mode(self, mode: RadarDisplayMode, display_type: str = None) -> Optional[str]:
        """
        Send request to set display mode for a specific display.

        Args:
            mode: RadarDisplayMode enum value
            display_type: Display identifier (e.g., 'pfd', 'mfd'). Required.

        Returns:
            Request ID if successful, None otherwise

        Raises:
            ValueError: If display_type is not provided or invalid
        """
        if not display_type:
            raise ValueError("display_type is required")

        # Import display types mapping
        from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

        # Convert to lowercase for comparison
        display_id = display_type.lower()
        if display_id not in DISPLAY_TYPES:
            raise ValueError(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid display type: {display_type}")

        # Log the mode change request with enhanced visibility
        logger.warning(f"[LOCAL_DISPLAYMESSAGEHANDLER] Setting {display_type} mode to {mode.name}")

        # Store the mode change in the display response service
        try:
            # Get display response service
            from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
            response_service = get_display_response_service()

            # Create mode change command data with explicit force_update flag
            command_data = {
                'command_type': 'mode_change',
                'display_type': display_type,
                'status': 'acknowledged',
                'request_id': str(uuid_lib.uuid4()),
                'timestamp': time.time(),
                'additional_info': {
                    'source_system': 'weather_radar',
                    'mode': mode.name,
                    'mode_value': mode.value,
                    'update_display_tree': True,  # Signal that display tree should be updated
                    'force_update': True,         # Force update regardless of current state
                    'weather_data': {
                        'mode': mode.name,
                        'mode_value': mode.value,
                        'cells': [],
                        'precipitation': [],
                        'vil_data': [],           # Will be populated by DisplayResponseService
                        'visual_elements': {      # Add explicit visual elements
                            'show_vil': True,
                            'show_vil_legend': True,
                            'show_vil_values': True,
                            'opacity': 1.0,
                            'show_scan_line': mode.name == 'SURVEILLANCE',
                            'show_intensity_scale': mode.name == 'SURVEILLANCE',
                            'show_terrain_scale': mode.name == 'MAPPING'
                        }
                    }
                }
            }

            # Store the command in the response service
            await response_service.handle_display_command(command_data, from_display_handler=True)
            logger.warning(f"[LOCAL_DISPLAYMESSAGEHANDLER] Stored mode change command: {mode.name}")

        except Exception as e:
            logger.error(f"[LOCAL_DISPLAYMESSAGEHANDLER] Error storing mode change: {str(e)}")
            logger.error(traceback.format_exc())

        # Send the request through the normal channel as well
        # Create enhanced command data with explicit update flags
        enhanced_command_data = {
            'mode': mode.name,
            'force_update': True,  # Add explicit flag to force update
            'update_visual': True  # Add explicit flag to update visual elements
        }

        request_id = await self.send_request(
            display_type=display_id,  # Use lowercase ID for consistency
            command_type='mode_change',  # Use explicit mode_change type
            command_data=enhanced_command_data  # Send enhanced command data
        )

        logger.warning(f"[LOCAL_DISPLAYMESSAGEHANDLER] Mode change request sent with ID: {request_id}")
        return request_id

    async def request_data(self, display_type: str, data_type: str) -> Optional[str]:
        """
        Send request for display data.

        Args:
            display_type: Display identifier (e.g., 'pfd', 'mfd'). Required.
            data_type: Type of data to request (e.g., 'navigation', 'tactical'). Required.

        Returns:
            Request ID if successful, None otherwise

        Raises:
            ValueError: If display_type is not provided or invalid
        """
        if not display_type:
            raise ValueError("display_type is required")

        if not data_type:
            raise ValueError("data_type is required")

        # Import display types mapping
        from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

        # Convert to lowercase for comparison
        display_id = display_type.lower()
        if display_id not in DISPLAY_TYPES:
            raise ValueError(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid display type: {display_type}")

        # Log the data request
        logger.info(f"Requesting {data_type} data from {display_type}")

        return await self.send_request(
            display_type=display_id,  # Use lowercase ID for consistency
            command_type='data',
            command_data={'type': data_type}
        )

    async def subscribe_to_data(self, display_type: str, data_type: str, subscribe: bool = True) -> Optional[str]:
        """
        Subscribe or unsubscribe to display data updates.

        Args:
            display_type: Display identifier (e.g., 'pfd', 'mfd'). Required.
            data_type: Type of data to subscribe to (e.g., 'navigation', 'tactical'). Required.
            subscribe: True to subscribe, False to unsubscribe. Defaults to True.

        Returns:
            Request ID if successful, None otherwise

        Raises:
            ValueError: If display_type or data_type is not provided or invalid
        """
        if not display_type:
            raise ValueError("display_type is required")

        if not data_type:
            raise ValueError("data_type is required")

        # Import display types mapping
        from FMOFP.local_messaging.display_command_map import DISPLAY_TYPES

        # Convert to lowercase for comparison
        display_id = display_type.lower()
        if display_id not in DISPLAY_TYPES:
            raise ValueError(f"[LOCAL_DISPLAYMESSAGEHANDLER] Invalid display type: {display_type}")

        # Log the subscription request
        action = "Subscribing to" if subscribe else "Unsubscribing from"
        logger.info(f"{action} {data_type} data from {display_type}")

        return await self.send_request(
            display_type=display_id,  # Use lowercase ID for consistency
            command_type='data_subscription',
            command_data={
                'type': data_type,
                'subscribe': subscribe
            }
        )

    def register_response_handler(self, request_id: str, handler):
        """Register a handler for response messages."""
        self.response_handlers[request_id] = handler
        logger.debug(f"Registered response handler for request {request_id}")

    async def handle_response(self, message: MIL_STD_1553B_Message, request_id: str):
        """Handle response messages."""
        try:
            if request_id in self.response_handlers:
                handler = self.response_handlers[request_id]
                await handler(message)
                logger.debug(f"Response handled for request {request_id}")
            else:
                logger.warning(f"No handler found for request {request_id}")

        except Exception as e:
            logger.error(f"Error handling display response: {str(e)}")
            logger.error(traceback.format_exc())

    def is_healthy(self) -> bool:
        """Check if handler is healthy."""
        try:
            with self._init_lock:
                if not self.started:
                    return False

                if not self.async_handler or not self.async_handler.is_healthy():
                    return False

                if not self.system_handler:
                    return False

                if not self.routing_service:
                    return False

                if not self.response_service:
                    return False

                return True

        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            return False

    async def handle_vil_data(self, message: Dict[str, Any]):
        """Handle VIL (Vertically Integrated Liquid) data message for display system.

        Args:
            message: Dictionary containing VIL data and metadata

        This method routes VIL data to the appropriate display components,
        ensuring it's properly processed and visualized.
        """
        try:
            # COMPREHENSIVE DATA FLOW LOGGING
            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== START VIL DATA HANDLING ======")
            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] DisplayMessageHandler.handle_vil_data called")
            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message type: {type(message)}")

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # CHECK IF MESSAGE ALREADY PROCESSED - EARLY CHECK
            if self._has_processed_request_id(request_id):
                logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Skipping already processed message: {request_id}")
                return

            # MARK THIS MESSAGE AS PROCESSED - EARLY MARKING
            self._mark_request_id_processed(request_id)

            # Log message structure
            if isinstance(message, dict):
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message keys: {list(message.keys())}")
                if 'data' in message:
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data type: {type(message['data'])}")
                    if isinstance(message['data'], dict):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data keys: {list(message['data'].keys())}")
                    elif isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data is list of length: {len(message['data'])}")
                        if message['data'] and len(message['data']) > 0:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item type: {type(message['data'][0])}")
                            if isinstance(message['data'][0], dict):
                                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item keys: {list(message['data'][0].keys())}")
                    else:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data value: {message['data']}")

            # Check for VIL data in various formats
            vil_data = None

            # Check for VIL in message dict
            if isinstance(message, dict):
                if 'vil_data' in message:
                    vil_data = message['vil_data']
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found VIL data in message['vil_data']")
                elif 'data' in message:
                    # Data could contain VIL
                    if isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential VIL data in message['data'] list")
                        vil_data = message['data']
                    elif isinstance(message['data'], (int, str)):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential raw value in message['data']: {message['data']}")
                    elif isinstance(message['data'], dict) and ('vil_data' in message['data'] or 'vil' in message['data']):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found VIL data in message['data'] dictionary")
                        vil_data = message['data'].get('vil_data', message['data'].get('vil'))
                elif 'additional_info' in message and isinstance(message['additional_info'], dict):
                    # Check in additional_info
                    if 'weather_data' in message['additional_info'] and isinstance(message['additional_info']['weather_data'], dict):
                        weather_data = message['additional_info']['weather_data']
                        if 'vil_data' in weather_data or 'vil' in weather_data:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found VIL data in message['additional_info']['weather_data']")
                            vil_data = weather_data.get('vil_data', weather_data.get('vil'))

            # Log what we found
            if vil_data is not None:
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] VIL data type: {type(vil_data)}")
                if isinstance(vil_data, list):
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] VIL data length: {len(vil_data)}")
                    if vil_data and len(vil_data) > 0:
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First VIL item: {vil_data[0]}")
            else:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No VIL data found in message")

            # Log the receipt of VIL data
            logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] DisplayMessageHandler received VIL data")

            # DIRECT DISPLAY PROCESSING - Skip sending to VIL service
            # No need to forward to VIL service since this data should
            # already have been processed there before reaching DisplayMessageHandler

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # Log direct processing
            logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Directly processing VIL data for display")
            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Direct display processing - bypassing VILResponseService")

            # Fetch VIL data from the database
            try:
                # Use the database manager to get VIL data
                from FMOFP.storage.DBM import DatabaseManager
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')

                # Query for VIL data
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Fetching VIL data from database")
                vil_db_data = radar_db.execute_query(
                    """
                    SELECT * FROM vil_data
                    ORDER BY timestamp DESC
                    LIMIT 10
                    """,
                    (),
                    query_type='select'
                )

                if vil_db_data and len(vil_db_data) > 0:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(vil_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    # Convert rows to dictionaries
                    vil_dict_list = []
                    for row in vil_db_data:
                        vil_dict_list.append(dict(zip(columns, row)))

                    # Format VIL data for display
                    formatted_vil_data = []
                    for vil in vil_dict_list:
                        formatted_vil_data.append({
                            'position': (vil['position_x'], vil['position_y']),
                            'value': vil['value'],
                            'layer_count': vil['layer_count'],
                            'intensity': vil['intensity'],
                            'show_values': bool(vil['show_values'])
                        })

                    # Use the database data instead of the message data
                    vil_data = formatted_vil_data
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Retrieved {len(vil_data)} VIL data points from database")

                    # Log the first item for verification
                    if len(vil_data) > 0:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] First VIL item from DB: {vil_data[0]}")
                else:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No VIL data found in database")
            except Exception as db_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Error fetching VIL data from database: {db_error}")
                logger.error(traceback.format_exc())

            # Create display command for storage/tracking
            try:
                # Store in response service for tracking
                display_command = {
                    'command_type': 'vil_data',
                    'display_type': 'radar_display',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'vil',
                        'message_type': WEATHER_RADAR_VIL_RESPONSE,
                        'vil_data': vil_data,
                        'directly_processed': True
                    }
                }

                # Add any metadata from the original message
                if isinstance(message, dict) and 'metadata' in message:
                    display_command['metadata'] = message.get('metadata', {})

                # Store in response service
                await self.response_service.handle_display_command(display_command, from_display_handler=True)
                logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Successfully stored VIL display command")

                # CREATE AND SEND A MIL-STD-1553B MESSAGE TO THE DISPLAY HARDWARE
                try:
                    import json
                    from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message

                    # Create a properly formatted MIL-STD-1553B message with binary data
                    # MIL-STD-1553B Protocol requires binary data (not JSON strings)

                    # Create a simple command word - using 0x05 as the VIL data command code
                    VIL_COMMAND = 0x05
                    data_word = format(VIL_COMMAND, '016b')  # Format as 16-bit binary string

                    logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Creating binary MIL-STD-1553B message with data: {data_word}")

                    # Get proper RT address from configuration
                    from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
                    display_rt_address = get_rt_address("displays")
                    weather_radar_sa = get_subaddress("weather_radar")

                    # Create MIL-STD-1553B message for display system
                    display_message = MIL_STD_1553B_Message(
                        rt_address=display_rt_address,
                        sub_address=weather_radar_sa,
                        data=data_word   # Binary data word
                    )

                    # Set command_type and message_type on the message
                    display_message.command_type = 'vil_data'
                    display_message.message_type = 'display_vil_data'
                    display_message.request_id = request_id

                    # Add VIL data as metadata - this won't be sent in the binary message
                    # but will be used by display system later when it looks up the data
                    display_message.vil_data = vil_data

                    # FORMAT FOR HARDWARE DISPLAY: Binary 16-bit word (NOT JSON)
                    # Command word structure: SSSAAAAAZBBBBBCCCCCP (S=sync, A=RT address, Z = transmit/receive B=subaddress C=count/mode, P=parity)

                    # Get proper RT address from configuration
                    from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_address, get_subaddress
                    # Get display command word from command registry
                    from FMOFP.local_messaging.display_command_map import get_display_command_word

                    # Get command word using registry lookup for radar_display with data command type
                    # VIL data uses the standard 'data' command type
                    command_word = get_display_command_word('radar_display', 'data')
                    sub_address = get_subaddress("weather_radar")  # Should return 14
                    display_rt_address = get_rt_address("displays")  # Should return 11

                    # Log the command for tracking
                    logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Using 'data' command type for VIL data with command word: {command_word}")

                    # Create proper binary format data word for VIL command
                    VIL_COMMAND = 0x03  # Use data command code (3) instead of status (5)
                    data_word = format(VIL_COMMAND, '016b')  # Create binary 16-bit word

                    # Send through sendMsg with explicit command word
                    # Include 'command_name' in metadata for MIL_STD_1553B or it will be rejected
                    metadata = {
                        'message_type': 'display_vil_data',
                        'command_type': 'vil_data',
                        'command_name': 'DISPLAY_VIL_DATA',  # REQUIRED by Messaging.py
                        'request_id': request_id,
                        'vil_data_available': True,
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler',
                        'vil_message': True  # Flag for displayMessenger.py detection
                    }


                    # Create formatted display data in the same structure as _handle_weather_display
                    formatted_display_data = {
                        'command_type': 'vil_data',  # Use specific type
                        'display_type': 'radar_display',
                        'data': {
                            'weather': {
                                'precipitation': [],
                                'vil_data': vil_data,
                                'cells': []
                            },
                            'visual': {
                                'overlay': 'weather',
                                'show_status': True,
                                'show_legend': True,
                                'show_values': True,
                                'opacity': 1.0,
                                'show_intensity_scale': True,
                                'show_scan_line': True,
                                'show_vil': True,
                                'show_vil_legend': True,
                                'show_vil_values': True
                            }
                        },
                        'message_type': 'weather_radarVILResponse',  # Use registered message type
                        'metadata': metadata
                    }


                    result = await self.sendMsg.send_message(command_word, [data_word], request_id, formatted_display_data)

                    logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Send message result: {result}")
                    logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Sent VIL data to display system via MIL-STD-1553B message")
                except Exception as send_error:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Error sending MIL-STD-1553B message: {send_error}")
                    logger.error(traceback.format_exc())

            except Exception as service_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Error storing display command: {service_error}")
                logger.error(traceback.format_exc())

            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== END VIL DATA HANDLING ======")

            # Send success acknowledgment
            request_id = message.get('request_id')
            if request_id:
                # Create a success acknowledgment
                ack_message = {
                    'request_id': request_id,
                    'command_type': 'vil_data',
                    'radar_type': 'weather_radar',
                    'status': 'acknowledged',
                    'timestamp': time.time(),
                    'additional_info': {
                        'data_type': 'vil',
                        'message_type': WEATHER_RADAR_VIL_RESPONSE,
                        'status_message': "Data processed successfully"
                    }
                }

                # Try to send acknowledgment
                routing_service = get_message_routing_service()
                await routing_service.route_status_word(ack_message)
                logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Sent success acknowledgment for {request_id}")

            logger.info(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Completed VIL data handling")

        except Exception as e:
            logger.debug(f"[LOCAL_DISP_MSG_HDR_VIL_FLOW] Error handling VIL data: {e}")
            logger.error(traceback.format_exc())

    def _convert_binary_precipitation_data(self, binary_data: str, request_id: str) -> List[Dict[str, Any]]:
        """Convert binary precipitation data to proper object format.

        Args:
            binary_data: Binary string representation of precipitation data
            request_id: Request ID for tracking

        Returns:
            List of properly formatted precipitation data objects
        """
        try:
            logger.debug(f"[PRECIP_CONVERTER] Converting binary precipitation data: {binary_data[:30]}{'...' if len(binary_data) > 30 else ''}")

            # Format validation
            if not binary_data or not isinstance(binary_data, str):
                logger.debug(f"[PRECIP_CONVERTER] Invalid binary data: {binary_data}")
                return []

            # ENHANCED HANDLING FOR FRAME-BASED BINARY DATA
            # Check if this is a transfer aggregator frame
            result_objects = []
            if binary_data.startswith('001') or binary_data.startswith('100'):
                # This appears to be a MIL-STD-1553B frame
                # Need to decode using frame swap logic seen in the logs
                logger.debug(f"[PRECIP_CONVERTER] Detected MIL-STD-1553B frame format")

                # Split the binary data into 20-bit frames if not already done
                frames = []
                if len(binary_data) >= 20:
                    # Split into 20-bit frames
                    for i in range(0, len(binary_data), 20):
                        if i + 20 <= len(binary_data):
                            frames.append(binary_data[i:i+20])

                logger.debug(f"[PRECIP_CONVERTER] Extracted {len(frames)} frames")

                # Process frames in pairs (command/data frames)
                for i in range(0, len(frames), 2):
                    if i + 1 < len(frames):
                        # We need to swap the frames based on the transfer aggregator logs
                        position_frame = frames[i]
                        attribute_frame = frames[i+1]

                        # Extract the data words (bits 4-19)
                        position_bits = position_frame[3:19] if len(position_frame) >= 19 else ''
                        attribute_bits = attribute_frame[3:19] if len(attribute_frame) >= 19 else ''

                        if len(position_bits) >= 16 and len(attribute_bits) >= 16:
                            # Log frame analysis
                            logger.debug(f"[PRECIP_CONVERTER] Frame pair {i//2}:")
                            logger.debug(f"[PRECIP_CONVERTER] - Position frame: {position_frame}")
                            logger.debug(f"[PRECIP_CONVERTER] - Attribute frame: {attribute_frame}")
                            logger.debug(f"[PRECIP_CONVERTER] - Position bits: {position_bits}")
                            logger.debug(f"[PRECIP_CONVERTER] - Attribute bits: {attribute_bits}")

                            # Swap the data based on the CORRECTED position/attribute logic in logs
                            corrected_position_bits = attribute_bits  # Use attribute frame for position
                            corrected_attribute_bits = position_bits  # Use position frame for attributes

                            # Convert binary position to coordinates
                            position_value = int(corrected_position_bits, 2)
                            x_coord = (position_value >> 8) & 0xFF  # Extract upper byte
                            y_coord = position_value & 0xFF        # Extract lower byte

                            # Adjust coordinates to match transfer aggregator decoding
                            x_adjusted = x_coord - 128.0
                            y_adjusted = y_coord - 128.0

                            # Extract attribute data
                            attribute_value = int(corrected_attribute_bits, 2)

                            # Extract attribute data with proper bit positions
                            type_bits = (attribute_value >> 12) & 0xF     # Top 4 bits
                            rate_bits = (attribute_value >> 6) & 0x3F     # Middle 6 bits
                            intensity_bits = attribute_value & 0x3F       # Bottom 6 bits

                            # Map type value to precipitation type (same as transfer aggregator)
                            type_map = {0: 'rain', 1: 'snow', 2: 'sleet', 3: 'hail', 4: 'mixed'}
                            precip_type = type_map.get(type_bits, 'rain')

                            # Scale values exactly like transfer aggregator
                            rate = rate_bits * 0.01  # Match transfer aggregator scale factor
                            intensity = intensity_bits * 0.0002  # Match transfer aggregator scale factor

                            # Create precipitation data object
                            formatted_data = {
                                'position': (x_adjusted, y_adjusted),
                                'type': precip_type,
                                'precip_type': precip_type,  # Add both fields for compatibility
                                'rate': rate,
                                'intensity': intensity,
                                'show_values': False,  # Match transfer aggregator
                                'id': f"{request_id}_{i//2}",  # Generate unique ID for each object
                                'request_id': request_id,
                                'timestamp': time.time()
                            }

                            # Log the decoded object
                            logger.debug(f"[PRECIP_CONVERTER] Decoded object {i//2}:")
                            logger.debug(f"[PRECIP_CONVERTER] - Position: {formatted_data['position']}")
                            logger.debug(f"[PRECIP_CONVERTER] - Type: {formatted_data['type']}")
                            logger.debug(f"[PRECIP_CONVERTER] - Rate: {formatted_data['rate']}")
                            logger.debug(f"[PRECIP_CONVERTER] - Intensity: {formatted_data['intensity']}")

                            # Add to result list
                            result_objects.append(formatted_data)

                # If we successfully decoded objects, return them
                if result_objects:
                    logger.debug(f"[PRECIP_CONVERTER] Successfully decoded {len(result_objects)} objects from frames")
                    return result_objects

            # STANDARD BINARY STRING HANDLING (FALLBACK)
            # Ensure we have a proper binary string by cleaning it first
            clean_binary = ''.join(c for c in binary_data if c in '01')
            if len(clean_binary) < 16:  # Minimum required bits
                logger.debug(f"[PRECIP_CONVERTER] Binary data too short after cleaning: {clean_binary}")
                return []

            # Create a default precipitation data object since we may not be able to extract
            # all parameters correctly from the binary string
            formatted_data = {
                'position': (0.0, 0.0),  # Default position
                'type': 'rain',          # Default type
                'precip_type': 'rain',   # Default type (duplicate field for compatibility)
                'rate': 0.5,             # Default rate
                'intensity': 0.7,        # Default intensity
                'show_values': True,     # Show values by default
                'id': f"{request_id}_0", # Generate unique ID
                'request_id': request_id,
                'timestamp': time.time()
            }

            # Try to extract position data
            try:
                # Extract X and Y positions
                # The format based on logs seems to be: first 16 bits are position (8 bits X, 8 bits Y)
                if len(clean_binary) >= 16:
                    x_bits = clean_binary[:8]
                    y_bits = clean_binary[8:16]

                    # Convert to integers and then scale appropriately
                    x_coord = int(x_bits, 2)
                    y_coord = int(y_bits, 2)

                    # Scale coordinates based on format seen in transfer aggregator
                    # (Values seem to be scaled coordinates)
                    formatted_data['position'] = (x_coord - 128.0, y_coord - 128.0)
                    logger.debug(f"[PRECIP_CONVERTER] Extracted position: {formatted_data['position']}")
            except Exception as pos_error:
                logger.debug(f"[PRECIP_CONVERTER] Error extracting position: {pos_error}")

            # Try to extract precipitation type and rate
            try:
                # If we have enough bits, extract type (4 bits) and rate (6 bits)
                if len(clean_binary) >= 26:
                    type_bits = clean_binary[16:20]
                    rate_bits = clean_binary[20:26]

                    # Convert to values
                    type_value = int(type_bits, 2)
                    rate_value = int(rate_bits, 2)

                    # Map type value to precipitation type
                    precip_types = ['rain', 'snow', 'sleet', 'hail']
                    precip_type = precip_types[min(type_value, len(precip_types)-1)]

                    # Scale rate (typically 0.01 factor as seen in transfer aggregator logs)
                    rate = rate_value * 0.01

                    formatted_data['type'] = precip_type
                    formatted_data['precip_type'] = precip_type  # Add both fields for compatibility
                    formatted_data['rate'] = rate
                    logger.debug(f"[PRECIP_CONVERTER] Extracted type: {precip_type}, rate: {rate}")
            except Exception as type_error:
                logger.debug(f"[PRECIP_CONVERTER] Error extracting type/rate: {type_error}")

            # Try to extract intensity
            try:
                # If we have enough bits, extract intensity (6 bits)
                if len(clean_binary) >= 32:
                    intensity_bits = clean_binary[26:32]
                    intensity_value = int(intensity_bits, 2)

                    # Scale intensity (typically 0.0002 factor as seen in transfer aggregator)
                    intensity = intensity_value * 0.0002
                    formatted_data['intensity'] = min(intensity, 1.0)  # Cap at 1.0
                    logger.debug(f"[PRECIP_CONVERTER] Extracted intensity: {intensity}")
            except Exception as int_error:
                logger.debug(f"[PRECIP_CONVERTER] Error extracting intensity: {int_error}")

            # Always ensure we return a list with at least one item
            logger.debug(f"[PRECIP_CONVERTER] Standard conversion complete. Formatted data: {formatted_data}")
            return [formatted_data]

        except Exception as e:
            logger.debug(f"[PRECIP_CONVERTER] Error converting binary precipitation data: {e}")
            logger.error(traceback.format_exc())
            return []  # Return empty list on error

    def _has_processed_request_id(self, request_id):
        """Check if a request ID or its base version has already been processed."""
        if not request_id:
            return False

        # Extract base request ID (without numeric suffix)
        base_request_id = request_id.split('_')[0] if '_' in request_id else request_id

        with self._processed_request_ids_lock:
            # Check if we've already processed this exact ID or its base form
            return (request_id in self._processed_request_ids or
                    base_request_id in self._processed_request_ids)

    def _mark_request_id_processed(self, request_id):
        """Mark a request ID as processed."""
        if not request_id:
            return

        # Extract base request ID (without numeric suffix)
        base_request_id = request_id.split('_')[0] if '_' in request_id else request_id

        with self._processed_request_ids_lock:
            # Store the base ID instead of variants with suffixes
            self._processed_request_ids.add(base_request_id)

            # Limit set size to prevent memory issues
            if len(self._processed_request_ids) > 10000:
                # Keep only the 5000 most recently added IDs
                self._processed_request_ids = set(list(self._processed_request_ids)[-5000:])

    async def handle_precipitation_data(self, message: Dict[str, Any]):
        """Handle precipitation data message for display system.

        Args:
            message: Dictionary containing precipitation data and metadata

        This method routes precipitation data to the appropriate display components,
        ensuring it's properly processed and visualized.
        """
        try:
            # COMPREHENSIVE DATA FLOW LOGGING
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== START PRECIPITATION DATA HANDLING ======")
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] DisplayMessageHandler.handle_precipitation_data called")
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message type: {type(message)}")

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # CHECK IF MESSAGE ALREADY PROCESSED - EARLY CHECK
            if self._has_processed_request_id(request_id):
                logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Skipping already processed message: {request_id}")
                return

            # MARK THIS MESSAGE AS PROCESSED - EARLY MARKING
            self._mark_request_id_processed(request_id)

            # Log message structure
            if isinstance(message, dict):
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message keys: {list(message.keys())}")
                if 'data' in message:
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data type: {type(message['data'])}")
                    if isinstance(message['data'], dict):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data keys: {list(message['data'].keys())}")
                    elif isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data is list of length: {len(message['data'])}")
                        if message['data'] and len(message['data']) > 0:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item type: {type(message['data'][0])}")
                            if isinstance(message['data'][0], dict):
                                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item keys: {list(message['data'][0].keys())}")
                    else:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data value: {message['data']}")

            # precipitation data extraction
            precip_data = None

            # Check for precipitation in message dict
            if isinstance(message, dict):
                if 'precipitation' in message:
                    precip_data = message['precipitation']
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found precipitation data in message['precipitation'] with {len(precip_data) if isinstance(precip_data, list) else 'N/A'} items")
                elif 'precipitation_data' in message:
                    precip_data = message['precipitation_data']
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found precipitation data in message['precipitation_data']")
                elif 'data' in message:
                    # Data could contain precipitation
                    if isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential precipitation data in message['data'] list")
                        precip_data = message['data']
                    elif isinstance(message['data'], (int, str)):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential raw value in message['data']: {message['data']}")
                        # save raw data value for later conversion
                        precip_data = message['data']
                    elif isinstance(message['data'], dict) and ('precipitation' in message['data'] or 'precipitation_data' in message['data']):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found precipitation data in message['data'] dictionary")
                        precip_data = message['data'].get('precipitation', message['data'].get('precipitation_data'))
                elif 'additional_info' in message and isinstance(message['additional_info'], dict):
                    # Check in additional_info
                    if 'weather_data' in message['additional_info'] and isinstance(message['additional_info']['weather_data'], dict):
                        weather_data = message['additional_info']['weather_data']
                        if 'precipitation' in weather_data or 'precipitation_data' in weather_data:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found precipitation data in message['additional_info']['weather_data']")
                            precip_data = weather_data.get('precipitation', weather_data.get('precipitation_data'))

            # Log what we found
            if precip_data is not None:
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Precipitation data type: {type(precip_data)}")
                if isinstance(precip_data, list):
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Precipitation data length: {len(precip_data)}")
                    if precip_data and len(precip_data) > 0:
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First precipitation item: {precip_data[0]}")
                elif isinstance(precip_data, str):
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found string precipitation data: {precip_data}")
            else:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No precipitation data found in message")

            # Log the receipt of precipitation data
            logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] DisplayMessageHandler received precipitation data")

            # DIRECT DISPLAY PROCESSING - Skip sending to precipitation service
            # No need to forward to precipitation service since this data should
            # already have been processed there before reaching DisplayMessageHandler

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

                # Log direct processing with high visibility for debugging
                logger.debug(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Directly processing precipitation data for display")
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Direct display processing - bypassing PrecipitationResponseService")

            # Fetch precipitation data from the database
            try:
                # Use the database manager to get precipitation data
                from FMOFP.storage.DBM import DatabaseManager
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')

                # Query for precipitation data
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Fetching precipitation data from database")
                precip_db_data = radar_db.execute_query(
                    """
                    SELECT * FROM precipitation_data
                    ORDER BY timestamp DESC
                    LIMIT 10
                    """,
                    (),
                    query_type='select'
                )

                if precip_db_data and len(precip_db_data) > 0:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(precipitation_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    # Convert rows to dictionaries
                    precip_dict_list = []
                    for row in precip_db_data:
                        precip_dict_list.append(dict(zip(columns, row)))

                    # Format precipitation data for display
                    formatted_precip_data = []
                    for precip in precip_dict_list:
                        formatted_precip_data.append({
                            'position': (precip['position_x'], precip['position_y']),
                            'type': precip['type'],
                            'rate': precip['rate'],
                            'intensity': precip['intensity'],
                            'show_values': bool(precip['show_values'])
                        })

                    # Use the database data instead of the message data
                    precip_data = formatted_precip_data
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Retrieved {len(precip_data)} precipitation data points from database")

                    # Log the first item for verification
                    if len(precip_data) > 0:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] First precipitation item from DB: {precip_data[0]}")
                else:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No precipitation data found in database")
            except Exception as db_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Error fetching precipitation data from database: {db_error}")
                logger.error(traceback.format_exc())

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # Properly handle string precipitation data
            # Convert binary string to precipitation data objects if needed
            if isinstance(precip_data, str):
                logger.warning(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Detected string precipitation data, converting to proper format")
                # Use our new conversion method to transform binary string to precipitation objects
                precip_data = self._convert_binary_precipitation_data(precip_data, request_id)
                logger.warning(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Converted string data to {len(precip_data)} precipitation objects")

            # Create display command for storage/tracking
            try:
                # Store in response service for tracking
                display_command = {
                    'command_type': 'precipitation_data',
                    'display_type': 'radar_display',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'precipitation',
                        'message_type': WEATHER_RADAR_PRECIPITATION_RESPONSE,
                        'precipitation_data': precip_data,
                        'directly_processed': True
                    }
                }

                # Add any metadata from the original message
                if isinstance(message, dict) and 'metadata' in message:
                    display_command['metadata'] = message.get('metadata', {})

                # Store in response service
                await self.response_service.handle_display_command(display_command, from_display_handler=True)
                logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Successfully stored precipitation display command")

                # CREATE AND SEND A MIL-STD-1553B MESSAGE TO THE DISPLAY HARDWARE
                try:
                    import json
                    from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message

                    # Get proper RT address from configuration
                    from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
                    from FMOFP.local_messaging.display_command_map import get_display_command_word
                    from FMOFP.local_messaging.command_word_map import WEATHER_DATA_REQUEST_MAP

                    # Use the specific precipitation command word instead of generic data command
                    if 'precipitation' in WEATHER_DATA_REQUEST_MAP:
                        command_word = WEATHER_DATA_REQUEST_MAP['precipitation']
                        logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIP_FLOW] Using specific precipitation command word: {command_word}")
                    else:
                        # Fallback to generic command word if specific not found
                        command_word = get_display_command_word('radar_display', 'data')
                        logger.warning(f"[LOCAL_DISP_MSG_HDR_PRECIP_FLOW] Precipitation command word not found, using generic: {command_word}")

                    # Create a binary-encoded representation of precipitation data
                    logger.debug(f"[PRECIPITATION_DEBUG] Encoding {len(precip_data) if precip_data else 0} precipitation objects for transmission")

                    # First word is object count
                    binary_data = [len(precip_data) if precip_data else 0]

                    # Add two words for each precipitation object
                    if precip_data and len(precip_data) > 0:
                        for i, precip_obj in enumerate(precip_data):
                            # Extract coordinates from position tuple
                            try:
                                position = precip_obj['position'] if isinstance(precip_obj, dict) else precip_obj.position
                                if not position or len(position) < 2:
                                    logger.debug(f"[PRECIPITATION_DEBUG] Invalid position in object {i}: {position}")
                                    continue

                                x, y = position

                                # Encode coordinates as bytes (adding 128 to handle negative values)
                                x_encoded = int(x + 128) & 0xFF
                                y_encoded = int(y + 128) & 0xFF

                                # Position word: x in high byte, y in low byte
                                position_word = (x_encoded << 8) | y_encoded

                                # Determine precipitation type code
                                precip_type = precip_obj['type'] if isinstance(precip_obj, dict) else precip_obj.type
                                type_code = 0  # Default rain
                                if precip_type == 'snow':
                                    type_code = 1
                                elif precip_type == 'sleet':
                                    type_code = 2
                                elif precip_type == 'hail':
                                    type_code = 3

                                # Get rate and intensity values
                                rate = precip_obj['rate'] if isinstance(precip_obj, dict) else precip_obj.rate
                                intensity = precip_obj['intensity'] if isinstance(precip_obj, dict) else precip_obj.intensity

                                # Scale precipitation rate and intensity to integers
                                rate_value = min(63, int(rate * 100))
                                intensity_value = min(63, int(intensity * 5000))

                                # Encode attributes word:
                                # Bits 15-12 (4 bits): Type code
                                # Bits 11-6 (6 bits): Rate
                                # Bits 5-0 (6 bits): Intensity
                                attribute_word = (type_code << 12) | (rate_value << 6) | intensity_value

                                # Add to binary data array
                                binary_data.append(position_word)
                                binary_data.append(attribute_word)

                                # Log the encoded data for debugging
                                logger.debug(f"[PRECIPITATION_DEBUG] Object {i}: position=({x},{y}), encoded_position=0x{position_word:04X}, " +
                                            f"type={precip_type}({type_code}), rate={rate}({rate_value}), intensity={intensity}({intensity_value}), " +
                                            f"attr_word=0x{attribute_word:04X}")
                            except Exception as encode_error:
                                logger.debug(f"[PRECIPITATION_DEBUG] Error encoding object {i}: {encode_error}")
                                logger.error(traceback.format_exc())

                    # Log the binary data for debugging
                    logger.debug(f"[PRECIPITATION_DEBUG] Binary data: {binary_data}")
                    logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Created binary data with {len(binary_data)} words for {binary_data[0]} precipitation objects")

                    # Add metadata for binary encoding
                    metadata = {
                        'message_type': 'weather_radarPrecipitationResponse',
                        'command_type': 'precipitation_data',
                        'command_name': 'DISPLAY_PRECIPITATION_DATA',
                        'data': binary_data,  # Send the binary data directly
                        'request_id': request_id,
                        'binary_encoded': True,
                        'precip_data_available': True,
                        'precipitation_message': True,
                        'is_transfer_data': True,  # Signal this contains binary-encoded data
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler'
                    }

                    # Log what we're actually sending
                    logger.debug(f"[PRECIPITATION_DEBUG] Sending command word: {command_word} with {len(binary_data)} binary words")

                    # Send the binary data directly in the message the metadata
                    result = await self.sendMsg.send_message(command_word, binary_data, request_id, metadata)

                    logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Send message result: {result}")
                    logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Sent precipitation data to display system via MIL-STD-1553B message")
                except Exception as send_error:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Error sending MIL-STD-1553B message: {send_error}")
                    logger.error(traceback.format_exc())

            except Exception as service_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Error storing display command: {service_error}")
                logger.error(traceback.format_exc())

            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== END PRECIPITATION DATA HANDLING ======")

            # Send success acknowledgment
            request_id = message.get('request_id')
            if request_id:
                # Create a success acknowledgment
                ack_message = {
                    'request_id': request_id,
                    'command_type': 'precipitation_data',
                    'radar_type': 'weather_radar',
                    'status': 'acknowledged',
                    'timestamp': time.time(),
                    'additional_info': {
                        'data_type': 'precipitation',
                        'message_type': WEATHER_RADAR_PRECIPITATION_RESPONSE,
                        'status_message': "Data processed successfully"
                    }
                }

                # Try to send acknowledgment
                routing_service = get_message_routing_service()
                await routing_service.route_status_word(ack_message)
                logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Sent success acknowledgment for {request_id}")

            logger.info(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Completed precipitation data handling")

        except Exception as e:
            logger.debug(f"[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW] Error handling precipitation data: {e}")
            logger.error(traceback.format_exc())

    async def _handle_weather_display(self, message: Dict):
        """Handle weather radar display updates"""
        try:
            # Log incoming message
            logger.info("[DISPLAY_MSG] Received weather display message")

            # Extract message properties
            message_type = message.get('message_type', '')
            original_command_type = message.get('command_type')

            # Extract message components
            metadata = message.get('metadata', {})
            additional_info = message.get('additional_info', {})
            weather_data = additional_info.get('weather_data', {})

            # Get mode state from metadata or additional_info
            mode_state = metadata.get('mode_state') or additional_info.get('mode_state')

            # detection for specialized data types
            command_type = original_command_type

            # Determine specific command type based on message content and message_type
            if message_type:
                logger.info(f"[DISPLAY_MSG] Analyzing message_type: {message_type}")

                # Check for VIL data in message_type
                if 'vil' in message_type.lower():
                    command_type = 'vil_data'
                    logger.info(f"[DISPLAY_MSG] Detected VIL data message from message_type: {message_type}")
                # Check for precipitation data in message_type
                elif 'precipitation' in message_type.lower():
                    command_type = 'precipitation_data'
                    logger.error(f"[DISPLAY_MSG] Detected precipitation data message from message_type: {message_type}")

                    # If we have weather_data field, extract precipitation data from there
                    if additional_info and 'weather_data' in additional_info:
                        if 'precipitation' in additional_info['weather_data']:
                            precip_data = additional_info['weather_data']['precipitation']
                            logger.error(f"[DISPLAY_MSG] Extracted precipitation data from weather_data: {len(precip_data) if isinstance(precip_data, list) else 'N/A'} items")

            # If command_type is still not determined, check message content
            if not command_type:
                if mode_state:
                    command_type = 'mode_change'
                elif weather_data and weather_data.get('vil_data'):
                    command_type = 'vil_data'
                    logger.info(f"[DISPLAY_MSG] Detected VIL data from weather_data content")
                elif weather_data and weather_data.get('precipitation'):
                    command_type = 'precipitation_data'
                    logger.info(f"[DISPLAY_MSG] Detected precipitation data from weather_data content")
                elif weather_data and weather_data.get('cells'):
                    command_type = 'cell_data_update'
                else:
                    command_type = 'display_update'

            logger.info(f"[DISPLAY_MSG] Processing {command_type} command (original: {original_command_type})")

            # For VIL data, use specialized routing
            if command_type == 'vil_data' or message_type == 'weather_radarVILResponse':
                # Add debug logging to identify exact message structure
                logger.info(f"[VIL_DEBUG] Processing message of type: {message_type}")
                logger.info(f"[VIL_DEBUG] Message attributes: {dir(message) if hasattr(message, '__dir__') else 'No attributes'}")
                logger.info(f"[VIL_DEBUG] Message dict content: {message if isinstance(message, dict) else 'Not a dict'}")

                # Extract VIL data with improved logic
                vil_data = []

                # Try multiple extraction methods
                if hasattr(message, 'vil_data'):
                    # Case 1: Direct attribute
                    logger.info("[VIL_DEBUG] Found 'vil_data' attribute")
                    vil_data = message.vil_data
                elif isinstance(message, dict) and 'vil_data' in message:
                    # Case 2: Dictionary key
                    logger.info("[VIL_DEBUG] Found 'vil_data' in dict keys")
                    vil_data = message['vil_data']
                elif hasattr(message, 'data') and hasattr(message.data, 'vil_data'):
                    # Case 3: Nested attribute
                    logger.info("[VIL_DEBUG] Found 'vil_data' in nested data attribute")
                    vil_data = message.data.vil_data
                elif isinstance(message, dict) and 'data' in message and isinstance(message['data'], dict) and 'vil_data' in message['data']:
                    # Case 4: Nested dictionary
                    logger.info("[VIL_DEBUG] Found 'vil_data' in nested data dict")
                    vil_data = message['data']['vil_data']
                elif weather_data and 'vil_data' in weather_data:
                    # Case 5: From weather_data (existing code)
                    logger.info("[VIL_DEBUG] Found 'vil_data' in weather_data")
                    vil_data = weather_data.get('vil_data')


                # Now route VIL data to VIL Response Service
                if vil_data:
                    # Log detailed info about the extracted data
                    logger.info(f"[VIL_DEBUG] Extracted VIL data count: {len(vil_data) if isinstance(vil_data, list) else 'Not a list'}")
                    logger.info(f"[VIL_DEBUG] VIL data type: {type(vil_data)}")

                    # Route VIL data through VIL Response Service
                    try:
                        # Import WeatherRadarVILData class
                        from FMOFP.local_messaging.messageConfigurations.weather_radar_data import WeatherRadarVILData

                        # Create proper VIL data objects
                        vil_data_objects = []
                        if isinstance(vil_data, list):
                            for data_point in vil_data:
                                if isinstance(data_point, dict):
                                    vil_obj = WeatherRadarVILData(
                                        position=data_point.get('position', (0.0, 0.0)),
                                        value=data_point.get('value', 0.0),
                                        layer_count=data_point.get('layer_count', 0),
                                        intensity=data_point.get('intensity', 0.0),
                                        show_values=data_point.get('show_values', False)
                                    )
                                    vil_obj.request_id = message.get('request_id', str(time.time())) if isinstance(message, dict) else (message.request_id if hasattr(message, 'request_id') else str(time.time()))
                                    vil_obj.timestamp = message.get('timestamp', time.time()) if isinstance(message, dict) else (message.timestamp if hasattr(message, 'timestamp') else time.time())
                                    vil_data_objects.append(vil_obj)
                                elif hasattr(data_point, 'position'):
                                    # Already a VIL data object
                                    vil_data_objects.append(data_point)
                        elif isinstance(vil_data, dict):
                            vil_obj = WeatherRadarVILData(
                                position=vil_data.get('position', (0.0, 0.0)),
                                value=vil_data.get('value', 0.0),
                                layer_count=vil_data.get('layer_count', 0),
                                intensity=vil_data.get('intensity', 0.0),
                                show_values=vil_data.get('show_values', False)
                            )
                            vil_obj.request_id = message.get('request_id', str(time.time())) if isinstance(message, dict) else (message.request_id if hasattr(message, 'request_id') else str(time.time()))
                            vil_obj.timestamp = message.get('timestamp', time.time()) if isinstance(message, dict) else (message.timestamp if hasattr(message, 'timestamp') else time.time())
                            vil_data_objects.append(vil_obj)
                        elif not isinstance(vil_data, list):
                            # If we have a single object that's not a dict, try to use it directly
                            vil_data_objects = [vil_data]

                        # Verify VIL Response Service initialization
                        if not hasattr(self, 'vil_response_service') or not self.vil_response_service or not getattr(self.vil_response_service, '_initialized', False):
                            logger.warning("[DISPLAY_MSG] VIL Response Service not properly initialized, reinitializing...")
                            from FMOFP.storage.DBM import DatabaseManager
                            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                            radar_db = db_manager.get_system_db('radar_management')
                            self.vil_response_service = VILResponseService(radar_db)
                            logger.info(f"[DISPLAY_MSG] Reinitialized VIL Response Service, state: {getattr(self.vil_response_service, '_initialized', False)}")

                        # Create a list of VIL data objects if needed
                        vil_data_list = vil_data_objects if isinstance(vil_data_objects, list) else [vil_data_objects]

                        # Log what we're about to send to the VIL Response Service
                        logger.info(f"[VIL_FLOW] Handling VIL data message")
                        logger.info(f"[VIL_FLOW] Extracted VIL data from response")
                        logger.info(f"[VIL_FLOW] Preparing to route {len(vil_data_list)} VIL data objects to VIL Response Service")

                        # Prepare message for VIL Response Service with ALL required fields
                        request_id = message.get('request_id', str(time.time())) if isinstance(message, dict) else (message.request_id if hasattr(message, 'request_id') else str(time.time()))
                        vil_message = {
                            'data': vil_data_list[0] if vil_data_list else None,
                            'vil_data': vil_data_list,  # Add the full list as well
                            'request_id': request_id,
                            'timestamp': message.get('timestamp', time.time()) if isinstance(message, dict) else (message.timestamp if hasattr(message, 'timestamp') else time.time()),
                            'mode': mode_state.get('current_mode', 'SURVEILLANCE') if mode_state else 'SURVEILLANCE',
                            'message_type': message_type
                        }

                        # Send to VIL Response Service
                        asyncio.create_task(self.vil_response_service.handle_vil_data(vil_message))

                        # Create command data for response tracking
                        command_data = {
                            'command_type': 'vil_data',
                            'display_type': 'radar_display',
                            'request_id': request_id,
                            'timestamp': time.time(),
                            'status': 'acknowledged',
                            'additional_info': {
                                'source_system': 'weather_radar',
                                'data_type': 'vil',
                                'message_type': message_type,
                                'weather_data': {
                                    'vil_data': vil_data_list
                                }
                            }
                        }

                        # Store command in response service
                        await self.response_service.handle_display_command(command_data, from_display_handler=True)
                        logger.info(f"[VIL_FLOW] Routed VIL data to display system")
                        logger.info(f"[VIL_FLOW] Processed VIL data message through VIL Response Service")
                        return
                    except Exception as e:
                        logger.error(f"[DISPLAY_MSG] Error routing VIL data to VIL Response Service: {e}")
                        logger.error(traceback.format_exc())

                        # Fall back to direct routing if VIL Response Service fails
                        vil_message = {
                            'vil_data': vil_data,
                            'request_id': message.get('request_id', str(time.time())) if isinstance(message, dict) else (message.request_id if hasattr(message, 'request_id') else str(time.time())),
                            'timestamp': message.get('timestamp', time.time()) if isinstance(message, dict) else (message.timestamp if hasattr(message, 'timestamp') else time.time()),
                            'mode': mode_state.get('current_mode', 'SURVEILLANCE') if mode_state else 'SURVEILLANCE'
                        }

                        # Route VIL data directly as fallback
                        logger.info(f"[DISPLAY_MSG] Falling back to direct routing: {vil_message}")
                        await self.routing_service.route_vil_data(vil_message)

                        # Store command in response service
                        await self.response_service.handle_display_command(command_data, from_display_handler=True)
                        logger.info(f"[DISPLAY_MSG] Processed VIL data message via fallback")
                        return

            # For precipitation data, use specialized routing
            elif command_type == 'precipitation_data':
                # Extract precipitation data
                precip_data = []
                if hasattr(message, 'precipitation'):
                    precip_data = message.precipitation
                elif weather_data and weather_data.get('precipitation'):
                    precip_data = weather_data.get('precipitation')

                if precip_data:
                    # Create command data for response tracking
                    command_data = {
                        'command_type': 'precipitation_data',
                        'display_type': 'radar_display',
                        'request_id': message.get('request_id'),
                        'timestamp': time.time(),
                        'status': 'acknowledged',
                        'additional_info': {
                            'source_system': 'weather_radar',
                            'data_type': 'precipitation',
                            'weather_data': {
                                'precipitation': precip_data
                            }
                        }
                    }

                    # Store command in response service
                    await self.response_service.handle_display_command(command_data, from_display_handler=True)
                    logger.info(f"[DISPLAY_MSG] Processed precipitation data message")
                    return

            # Only update mode for mode change commands
            # For other command types, get current mode but don't change it
            if command_type == 'mode_change' or command_type == 'mode_change_completion' or 'mode_change' in str(command_type).lower():
                # For mode change commands, extract mode from the message
                current_mode = mode_state.get('current_mode', 'SURVEILLANCE') if mode_state else 'SURVEILLANCE'
                logger.debug(f"[DISPLAY_MSG] Processing mode change to {current_mode}")
            else:
                # For data messages, get current mode from DisplayResponseService
                try:
                    # Get display response service
                    from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
                    display_service = get_display_response_service()
                    current_mode_info = None

                    # Try to get current mode from service
                    if display_service:
                        try:
                            current_mode_info = await display_service.get_current_display_mode('weather_radar')
                        except Exception as e:
                            logger.error(f"[DISPLAY_MSG] Error getting current mode: {e}")

                    # Use current mode or fallback to SURVEILLANCE
                    current_mode = current_mode_info.get('mode', 'SURVEILLANCE') if current_mode_info else 'SURVEILLANCE'
                    logger.info(f"[DISPLAY_MSG] Using existing mode {current_mode} for {command_type} message")
                except Exception as e:
                    logger.error(f"[DISPLAY_MSG] Error retrieving current mode: {e}")
                    current_mode = 'SURVEILLANCE'  # Fallback to SURVEILLANCE
            display_data = {
                'command_type': command_type,
                'display_type': 'weather_radar',
                'data': {
                    'mode': {
                        'current_mode': current_mode,
                        'mode_value': mode_state.get('mode_value') if mode_state else None,
                        'source_system': 'weather_radar',
                        'timestamp': time.time()
                    },
                    'visual': {
                        'overlay': current_mode.lower(),
                        'show_status': True,
                        'show_legend': current_mode != 'STANDBY',
                        'show_values': current_mode != 'STANDBY',
                        'opacity': 0.8 if current_mode == 'MAPPING' else 1.0,
                        'show_terrain_scale': current_mode == 'MAPPING',
                        'show_intensity_scale': current_mode == 'SURVEILLANCE',
                        'show_scan_line': current_mode == 'SURVEILLANCE'
                    },
                    'weather': {
                        'vil_data': [
                            {
                                'position': vil.get('position', (0, 0)),
                                'value': vil.get('value', 0),
                                'layer_count': vil.get('layer_count', 0),
                                'intensity': vil.get('intensity', 0),
                                'show_values': vil.get('show_values', True)
                            } for vil in weather_data.get('vil_data', [])
                        ],
                        'precipitation': [
                            {
                                'position': precip.get('position', (0, 0)),
                                'type': precip.get('type', None),
                                'rate': precip.get('rate', 0),
                                'intensity': precip.get('intensity', 0),
                                'show_values': precip.get('show_values', True)
                            } for precip in weather_data.get('precipitation', [])
                        ],
                        'cells': [
                            {
                                'position': cell.get('position', (0, 0)),
                                'intensity': cell.get('intensity', 0),
                                'show_values': cell.get('show_values', True)
                            } for cell in weather_data.get('cells', [])
                        ]
                    }
                }
            }

            # Get proper RT address from configuration
            from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
            display_rt_address = get_rt_address("displays")
            weather_radar_sa = get_subaddress("weather_radar")

            # Create MIL-STD-1553B message for display system
            display_message = MIL_STD_1553B_Message(
                rt_address=display_rt_address,
                sub_address=weather_radar_sa,
                data=json.dumps(display_data)
            )

            # Set command_type and message_type on the message
            display_message.command_type = command_type
            display_message.message_type = message_type or f"display_{command_type}"
            display_message.request_id = message.get('request_id')

            # Send through message routing service
            await self.routing_service.route_message(display_message)
            logger.info(f"[DISPLAY_MSG] Sent {command_type} to display system")

            # Create command data for response tracking
            command_data = {
                'command_type': command_type,
                'display_type': 'radar_display',
                'request_id': message.get('request_id'),
                'timestamp': time.time(),
                'status': 'acknowledged',
                'additional_info': {
                    'source_system': 'weather_radar',
                    'mode_state': {
                        'current_mode': current_mode,
                        'source_system': 'weather_radar'
                    },
                    'weather_data': {
                        'vil_data': weather_data.get('vil_data', []),
                        'precipitation': weather_data.get('precipitation', []),
                        'cells': weather_data.get('cells', [])
                    }
                }
            }

            # Store command in response service
            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            logger.info(f"[DISPLAY_MSG] Processed weather radar {command_type}")

        except Exception as e:
            logger.error(f"[DISPLAY_MSG] Error handling weather display: {str(e)}")
            logger.error(traceback.format_exc())

    async def handle_echo_top_data(self, message: Dict[str, Any]):
        """Handle Echo Top (Cloud Top Height) data message for display system.

        Args:
            message: Dictionary containing echo top data and metadata

        This method routes echo top data to the appropriate display components,
        ensuring it's properly processed and visualized.
        """
        try:
            # COMPREHENSIVE DATA FLOW LOGGING
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== START ECHO TOP DATA HANDLING ======")
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] DisplayMessageHandler.handle_echo_top_data called")
            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message type: {type(message)}")

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # CHECK IF MESSAGE ALREADY PROCESSED - EARLY CHECK
            if self._has_processed_request_id(request_id):
                logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Skipping already processed message: {request_id}")
                return

            # MARK THIS MESSAGE AS PROCESSED - EARLY MARKING
            self._mark_request_id_processed(request_id)

            # Log message structure
            if isinstance(message, dict):
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message keys: {list(message.keys())}")
                if 'data' in message:
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data type: {type(message['data'])}")
                    if isinstance(message['data'], dict):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data keys: {list(message['data'].keys())}")
                    elif isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data is list of length: {len(message['data'])}")
                        if message['data'] and len(message['data']) > 0:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item type: {type(message['data'][0])}")
                            if isinstance(message['data'][0], dict):
                                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First data item keys: {list(message['data'][0].keys())}")
                    else:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Message data value: {message['data']}")

            # Check for Echo Top data in various formats
            echo_top_data = None

            # Check for Echo Top in message dict
            if isinstance(message, dict):
                if 'echo_top_data' in message:
                    echo_top_data = message['echo_top_data']
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found echo top data in message['echo_top_data']")
                elif 'data' in message:
                    # Data could contain Echo Top
                    if isinstance(message['data'], list):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential echo top data in message['data'] list")
                        echo_top_data = message['data']
                    elif isinstance(message['data'], (int, str)):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found potential raw value in message['data']: {message['data']}")
                    elif isinstance(message['data'], dict) and ('echo_top_data' in message['data'] or 'echo_top' in message['data']):
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found echo top data in message['data'] dictionary")
                        echo_top_data = message['data'].get('echo_top_data', message['data'].get('echo_top'))
                elif 'additional_info' in message and isinstance(message['additional_info'], dict):
                    # Check in additional_info
                    if 'weather_data' in message['additional_info'] and isinstance(message['additional_info']['weather_data'], dict):
                        weather_data = message['additional_info']['weather_data']
                        if 'echo_top_data' in weather_data or 'echo_top' in weather_data:
                            logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Found echo top data in message['additional_info']['weather_data']")
                            echo_top_data = weather_data.get('echo_top_data', weather_data.get('echo_top'))

            # Log what we found
            if echo_top_data is not None:
                logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Echo top data type: {type(echo_top_data)}")
                if isinstance(echo_top_data, list):
                    logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] Echo top data length: {len(echo_top_data)}")
                    if echo_top_data and len(echo_top_data) > 0:
                        logger.info(f"[LOCAL_DISP_MSG_HDR_TRACKING] First echo top item: {echo_top_data[0]}")
            else:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No echo top data found in message")

            # Log the receipt of echo top data
            logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] DisplayMessageHandler received echo top data")

            # Extract request_id for acknowledgment/tracking
            request_id = message.get('request_id')
            if not request_id:
                request_id = str(time.time())  # Generate one if not present
                message['request_id'] = request_id

            # Log direct processing
            logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Directly processing echo top data for display")
            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Direct display processing - bypassing EchoTopResponseService")

            # Fetch echo top data from the database
            try:
                # Use the database manager to get echo top data
                from FMOFP.storage.DBM import DatabaseManager
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')

                # Query for echo top data
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Fetching echo top data from database")
                echo_top_db_data = radar_db.execute_query(
                    """
                    SELECT * FROM echo_top_data
                    ORDER BY timestamp DESC
                    LIMIT 10
                    """,
                    (),
                    query_type='select'
                )

                if echo_top_db_data and len(echo_top_db_data) > 0:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(echo_top_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    # Convert rows to dictionaries
                    echo_top_dict_list = []
                    for row in echo_top_db_data:
                        echo_top_dict_list.append(dict(zip(columns, row)))

                    # Format echo top data for display
                    formatted_echo_top_data = []
                    for echo_top in echo_top_dict_list:
                        formatted_echo_top_data.append({
                            'position': (echo_top['position_x'], echo_top['position_y']),
                            'height': echo_top['height'],
                            'intensity': echo_top['intensity'],
                            'show_values': bool(echo_top['show_values'])
                        })

                    # Use the database data instead of the message data
                    echo_top_data = formatted_echo_top_data
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Retrieved {len(echo_top_data)} echo top data points from database")

                    # Log the first item for verification
                    if len(echo_top_data) > 0:
                        logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] First echo top item from DB: {echo_top_data[0]}")
                else:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] No echo top data found in database")
            except Exception as db_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] Error fetching echo top data from database: {db_error}")
                logger.error(traceback.format_exc())

            # Create display command for storage/tracking
            try:
                # Store in response service for tracking
                display_command = {
                    'command_type': 'echo_top_data',
                    'display_type': 'radar_display',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'echo_top',
                        'message_type': WEATHER_RADAR_ECHO_TOP_RESPONSE,
                        'echo_top_data': echo_top_data,
                        'directly_processed': True
                    }
                }

                # Add any metadata from the original message
                if isinstance(message, dict) and 'metadata' in message:
                    display_command['metadata'] = message.get('metadata', {})

                # Store in response service
                await self.response_service.handle_display_command(display_command, from_display_handler=True)
                logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Successfully stored echo top display command")

                # CREATE AND SEND A MIL-STD-1553B MESSAGE TO THE DISPLAY HARDWARE
                try:
                    import json
                    from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message

                    # Create a properly formatted MIL-STD-1553B message with binary data
                    # MIL-STD-1553B Protocol requires binary data (not JSON strings)

                    # Create a simple command word - using 0x06 as the echo top data command code
                    ECHO_TOP_COMMAND = 0x06
                    data_word = format(ECHO_TOP_COMMAND, '016b')  # Format as 16-bit binary string

                    logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Creating binary MIL-STD-1553B message with data: {data_word}")

                    # Get proper RT address from configuration
                    from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
                    display_rt_address = get_rt_address("displays")
                    weather_radar_sa = get_subaddress("weather_radar")

                    # Create MIL-STD-1553B message for display system
                    display_message = MIL_STD_1553B_Message(
                        rt_address=display_rt_address,
                        sub_address=weather_radar_sa,
                        data=data_word   # Binary data word
                    )

                    # Set command_type and message_type on the message
                    display_message.command_type = 'echo_top_data'
                    display_message.message_type = 'display_echo_top_data'
                    display_message.request_id = request_id

                    # Add echo top data as metadata - this won't be sent in the binary message
                    # but will be used by display system later when it looks up the data
                    display_message.echo_top_data = echo_top_data

                    # FORMAT FOR HARDWARE DISPLAY: Binary 16-bit word (NOT JSON)
                    # Command word structure: SSSAAAAAZBBBBBCCCCCP (S=sync, A=RT address, Z = transmit/receive B=subaddress C=count/mode, P=parity)

                    # Get proper RT address from configuration
                    from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_address, get_subaddress
                    # Get display command word from command registry
                    from FMOFP.local_messaging.display_command_map import get_display_command_word

                    # Get command word using registry lookup for radar_display with data command type
                    # VIL data uses the standard 'data' command type
                    command_word = get_display_command_word('radar_display', 'data')
                    sub_address = get_subaddress("weather_radar")  # Should return 14
                    display_rt_address = get_rt_address("displays")  # Should return 11

                    # Log the command for tracking
                    logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Using 'data' command type for echo top data with command word: {command_word}")

                    # Create proper binary format data word for echo top command
                    ECHO_TOP_COMMAND = 0x03  # Use data command code (3) instead of status (6)
                    data_word = format(ECHO_TOP_COMMAND, '016b')  # Create binary 16-bit word

                    # Send through sendMsg with explicit command word
                    # Include 'command_name' in metadata for MIL_STD_1553B or it will be rejected
                    metadata = {
                        'message_type': 'display_echo_top_data',
                        'command_type': 'echo_top_data',
                        'command_name': 'DISPLAY_ECHO_TOP_DATA',  # REQUIRED by Messaging.py
                        'request_id': request_id,
                        'echo_top_data_available': True,
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler',
                        'echo_top_message': True  # Flag for displayMessenger.py detection
                    }

                    # Create formatted display data in the same structure as _handle_weather_display
                    formatted_display_data = {
                        'command_type': 'data',  # Changed to standard 'data' command type
                        'display_type': 'radar_display',
                        'data': {
                            'weather': {
                                'precipitation': [],
                                'vil_data': [],
                                'echo_top_data': echo_top_data,
                                'cells': []
                            },
                            'visual': {
                                'overlay': 'weather',
                                'show_status': True,
                                'show_legend': True,
                                'show_values': True,
                                'opacity': 1.0,
                                'show_intensity_scale': True,
                                'show_scan_line': True,
                                'show_echo_top': True,
                                'show_echo_top_legend': True,
                                'show_echo_top_values': True
                            }
                        },
                        'message_type': 'display_data',  # Added standard message type
                        'metadata': metadata
                    }

                    result = await self.sendMsg.send_message(command_word, [data_word], request_id, formatted_display_data)

                    logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Send message result: {result}")
                    logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Sent echo top data to display system via MIL-STD-1553B message")
                except Exception as send_error:
                    logger.debug(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Error sending MIL-STD-1553B message: {send_error}")
                    logger.error(traceback.format_exc())

            except Exception as service_error:
                logger.debug(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Error storing display command: {service_error}")
                logger.error(traceback.format_exc())

            logger.debug(f"[LOCAL_DISP_MSG_HDR_TRACKING] ====== END ECHO TOP DATA HANDLING ======")

            # Send success acknowledgment
            request_id = message.get('request_id')
            if request_id:
                # Create a success acknowledgment
                ack_message = {
                    'request_id': request_id,
                    'command_type': 'echo_top_data',
                    'radar_type': 'weather_radar',
                    'status': 'acknowledged',
                    'timestamp': time.time(),
                    'additional_info': {
                        'data_type': 'echo_top',
                        'message_type': WEATHER_RADAR_ECHO_TOP_RESPONSE,
                        'status_message': "Data processed successfully"
                    }
                }

                # Try to send acknowledgment
                routing_service = get_message_routing_service()
                await routing_service.route_status_word(ack_message)
                logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Sent success acknowledgment for {request_id}")

            logger.info(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Completed echo top data handling")

        except Exception as e:
            logger.debug(f"[LOCAL_DISP_MSG_HDR_ECHO_TOP_FLOW] Error handling echo top data: {e}")
            logger.error(traceback.format_exc())

    async def _handle_fms_message(self, message: Dict):
        """Handle Flight Management System (FMS) messages.

        This method processes messages from the FMS system and updates
        appropriate displays with flight data, attitude information,
        and navigation updates.

        Args:
            message: The FMS message containing flight data
        """
        try:
            # Log incoming message
            logger.info("[DISPLAY_MSG_FMS] Received FMS message")

            # Extract message properties
            message_type = message.get('message_type', '')

            # Get display type based on message content
            # Default to PFD (Primary Flight Display) for most FMS data
            display_type = 'pfd'

            # Extract request ID for tracking
            request_id = message.get('request_id', str(time.time()))

            # Different processing based on message type
            if message_type == 'fms_flightData':
                # Extract flight data components
                attitude = message.get('attitude', {})
                velocity = message.get('velocity', {})
                navigation = message.get('navigation', {})
                tactical = message.get('tactical', {})

                # Format data for PFD display
                pfd_data = {
                    'command_type': 'fms_data',
                    'display_type': 'pfd',
                    'data': {
                        'attitude': {
                            'roll': attitude.get('roll', 0),
                            'pitch': attitude.get('pitch', 0),
                            'yaw': attitude.get('yaw', 0),
                            'heading': navigation.get('heading', 0)
                        },
                        'velocity': {
                            'airspeed': velocity.get('airspeed', 0),
                            'vertical_speed': velocity.get('vertical_speed', 0),
                            'ground_speed': velocity.get('ground_speed', 0)
                        },
                        'navigation': {
                            'altitude': navigation.get('altitude', 0),
                            'heading': navigation.get('heading', 0),
                            'latitude': navigation.get('latitude', 0),
                            'longitude': navigation.get('longitude', 0)
                        },
                        'tactical': tactical
                    }
                }

                # Create display command for PFD
                command_data = {
                    'command_type': 'fms_data',
                    'display_type': 'pfd',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'flight_data',
                        'message_type': message_type,
                        'source_system': 'flightManagementSystem'
                    }
                }

                # Store in response service for tracking
                await self.response_service.handle_display_command(command_data, from_display_handler=True)
                logger.info("[DISPLAY_MSG_FMS] Processed FMS flight data for PFD")

                # Create MIL-STD-1553B message for PFD display system
                try:
                    import json
                    from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message

                    # Get proper RT address from configuration
                    from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_address, get_subaddress
                    # Get display command word from command registry
                    from FMOFP.local_messaging.display_command_map import get_display_command_word

                    # Get command word for PFD with data command type
                    command_word = get_display_command_word('pfd', 'data')
                    data_word = format(0x03, '016b')  # Use data command code (3)

                    # Metadata for message
                    metadata = {
                        'message_type': 'display_fms_data',
                        'command_type': 'fms_data',
                        'command_name': 'DISPLAY_FMS_DATA',
                        'request_id': request_id,
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler',
                        'fms_message': True
                    }

                    # Send formatted data to PFD
                    await self.sendMsg.send_message(command_word, [data_word], request_id, pfd_data)
                    logger.info("[DISPLAY_MSG_FMS] Sent flight data to PFD display via MIL-STD-1553B")

                except Exception as send_error:
                    logger.error(f"[DISPLAY_MSG_FMS] Error sending to PFD: {send_error}")
                    logger.error(traceback.format_exc())

            elif message_type == 'fms_attitudeUpdateRequest' or message_type == 'fms_attitudeUpdateResponse':
                # Extract attitude parameters
                parameters = message.get('parameters', {})

                # Format attitude data for PFD
                attitude_data = {
                    'command_type': 'attitude_update',
                    'display_type': 'pfd',
                    'data': {
                        'attitude': {
                            'roll': parameters.get('roll', 0),
                            'pitch': parameters.get('pitch', 0),
                            'yaw': parameters.get('yaw', 0)
                        }
                    }
                }

                # Create display command for PFD
                command_data = {
                    'command_type': 'attitude_update',
                    'display_type': 'pfd',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'attitude',
                        'message_type': message_type,
                        'source_system': 'flightManagementSystem'
                    }
                }

                # Store in response service for tracking
                await self.response_service.handle_display_command(command_data, from_display_handler=True)
                logger.info("[DISPLAY_MSG_FMS] Processed FMS attitude update for PFD")

                # Create MIL-STD-1553B message for PFD display
                try:
                    from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
                    from FMOFP.local_messaging.display_command_map import get_display_command_word

                    # Get command word for PFD with data command type
                    command_word = get_display_command_word('pfd', 'data')
                    data_word = format(0x03, '016b')  # Use data command code (3)

                    # Metadata for message
                    metadata = {
                        'message_type': 'display_attitude_update',
                        'command_type': 'attitude_update',
                        'command_name': 'DISPLAY_ATTITUDE_UPDATE',
                        'request_id': request_id,
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler',
                        'fms_message': True
                    }

                    # Send formatted data to PFD
                    await self.sendMsg.send_message(command_word, [data_word], request_id, attitude_data)
                    logger.info("[DISPLAY_MSG_FMS] Sent attitude update to PFD display via MIL-STD-1553B")

                except Exception as send_error:
                    logger.error(f"[DISPLAY_MSG_FMS] Error sending to PFD: {send_error}")
                    logger.error(traceback.format_exc())

            elif message_type == 'fms_navigationUpdateRequest' or message_type == 'fms_navigationUpdateResponse':
                # Extract navigation parameters
                parameters = message.get('parameters', {})

                # Format navigation data for navigation display (could be MFD or PFD)
                nav_data = {
                    'command_type': 'navigation_update',
                    'display_type': 'mfd',  # Use MFD for nav data
                    'data': {
                        'navigation': {
                            'altitude': parameters.get('altitude', 0),
                            'heading': parameters.get('heading', 0),
                            'latitude': parameters.get('latitude', 0),
                            'longitude': parameters.get('longitude', 0),
                            'course': parameters.get('course', 0),
                            'waypoints': parameters.get('waypoints', [])
                        }
                    }
                }

                # Create display command for MFD
                command_data = {
                    'command_type': 'navigation_update',
                    'display_type': 'mfd',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'status': 'acknowledged',
                    'additional_info': {
                        'data_type': 'navigation',
                        'message_type': message_type,
                        'source_system': 'flightManagementSystem'
                    }
                }

                # Store in response service for tracking
                await self.response_service.handle_display_command(command_data, from_display_handler=True)
                logger.info("[DISPLAY_MSG_FMS] Processed FMS navigation update for MFD")

                # Create MIL-STD-1553B message for MFD display
                try:
                    from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
                    from FMOFP.local_messaging.display_command_map import get_display_command_word

                    # Get command word for MFD with data command type
                    command_word = get_display_command_word('mfd', 'data')
                    data_word = format(0x03, '016b')  # Use data command code (3)

                    # Metadata for message
                    metadata = {
                        'message_type': 'display_navigation_update',
                        'command_type': 'navigation_update',
                        'command_name': 'DISPLAY_NAVIGATION_UPDATE',
                        'request_id': request_id,
                        'destination': 'displays',
                        'sending_system': 'DisplayMessageHandler',
                        'fms_message': True
                    }

                    # Send formatted data to MFD
                    await self.sendMsg.send_message(command_word, [data_word], request_id, nav_data)
                    logger.info("[DISPLAY_MSG_FMS] Sent navigation update to MFD display via MIL-STD-1553B")

                except Exception as send_error:
                    logger.error(f"[DISPLAY_MSG_FMS] Error sending to MFD: {send_error}")
                    logger.error(traceback.format_exc())

            else:
                # For other message types, just log
                logger.info(f"[DISPLAY_MSG_FMS] Received {message_type} message, no specific handler")

        except Exception as e:
            logger.error(f"[DISPLAY_MSG_FMS] Error handling FMS message: {str(e)}")
            logger.error(traceback.format_exc())

    def stop(self):
        """Stop the message handler."""
        try:
            self.started = False

            # Cancel processing task
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    self._processing_task.result()
                except asyncio.CancelledError:
                    pass
                self._processing_task = None

            # Don't stop async handler - let system manager handle that
            logger.info("DisplayMessageHandler stopped")
        except Exception as e:
            logger.error(f"Error stopping DisplayMessageHandler: {str(e)}")
            logger.error(traceback.format_exc())

# Global instance
_display_message_handler = None

def get_display_message_handler():
    """Get the global DisplayMessageHandler instance."""
    global _display_message_handler
    if _display_message_handler is None:
        _display_message_handler = DisplayMessageHandler()
    return _display_message_handler
