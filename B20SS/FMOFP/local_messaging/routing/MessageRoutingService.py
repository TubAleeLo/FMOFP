"""
Message Routing Service

Routes messages between components:
1. Routes command acknowledgments to storage
2. Routes data words to appropriate storage
3. Handles message routing and persistence
"""

import asyncio
import sys
import time
import uuid
import traceback
from typing import Dict, Any, Optional, List, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
# Import only the dataclasses to avoid circular dependency

logger = get_logger()

class MessageRoutingService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageRoutingService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Initialize services as None - they will be set later
            self.radar_response_service = None
            self.display_response_service = None
            self._vil_service = None  # Initialize VIL service reference
            self._comms_service = None    # CommsService reference
            self._mission_service = None  # MissionService reference

            # Initialize unified router
            from FMOFP.local_messaging.routing.unified_router import get_unified_router
            self.unified_router = get_unified_router()

            # Initialize routing registry
            from FMOFP.local_messaging.routing.routing_registry import get_routing_registry
            self.routing_registry = get_routing_registry()

            # Load routing configuration
            try:
                self.routing_registry.load_from_xml(
                    'FMOFP/local_messaging/messageConfigurations/address_book.xml',
                    'FMOFP/local_messaging/messageConfigurations/command_registry.xml'
                )
                logger.info("Routing registry loaded successfully")
            except Exception as e:
                logger.error(f"Error loading routing registry: {e}")
                logger.error(traceback.format_exc())

            self._initialized = True
            logger.info("MessageRoutingService initialized with Unified Router")
            logger.info(f"Unified Router instance ID: {id(self.unified_router)}")

    def set_display_response_service(self, service):
        """Set the display response service after initialization"""
        self.display_response_service = service
        # Set routing service in display response service
        if service is not None:
            service.set_routing_service(self)
            logger.info("Display response service set")
        else:
            logger.warning("Attempted to set null display_response_service")

    def set_radar_response_service(self, service):
        """Set the radar response service after initialization"""
        if service is not None:
            self.radar_response_service = service
            logger.info("Radar response service set")
        else:
            logger.warning("Attempted to set null radar_response_service")

    def set_comms_service(self, service) -> None:
        """Register CommsService so route_comms_message can use it directly."""
        self._comms_service = service
        logger.info("CommsService registered with MessageRoutingService")

    def set_mission_service(self, service) -> None:
        """Register MissionService so route_mission_message can use it directly."""
        self._mission_service = service
        logger.info("MissionService registered with MessageRoutingService")

    async def stop(self):
        """Stop the message routing service."""
        logger.info("Stopping message routing service")
        # Clear references to other services
        if self.radar_response_service:
            await self.radar_response_service.stop()
            self.radar_response_service = None
        if self.display_response_service:
            await self.display_response_service.stop()
            self.display_response_service = None
        self._initialized = False
        logger.info("Message routing service stopped")

    async def route_status_word(self, message: Dict[str, Any]):
        """Route status word (command acknowledgment) to storage using UnifiedRouter"""
        try:
            # Log routing attempt
            logger.info(f"[ACK] Routing status word with request_id: {message.get('request_id')} via UnifiedRouter")

            # Add message type if not present
            if 'message_type' not in message:
                message['message_type'] = 'radar_statusWord'

            # Add command type if not present
            if 'command_type' not in message:
                message['command_type'] = 'status_word'

            # Route through UnifiedRouter
            from FMOFP.local_messaging.routing.system_integration import route_message
            result = route_message(message)

            if result:
                logger.info(f"[ACK] Successfully routed status word with request_id: {message.get('request_id')}")
            else:
                logger.error(f"[ACK] Failed to route status word with request_id: {message.get('request_id')}")

            return result
        except Exception as e:
            logger.error(f"Error routing status word: {e}")
            logger.error(traceback.format_exc())
            return False

    async def route_status_word_async(self, message: Dict[str, Any]):
        """Route status word (command acknowledgment) to storage (async version)"""
        try:
            # Extract request_id if present
            request_id = message.get('request_id')
            if not request_id:
                logger.warning("Status word missing request_id")
                return

            # Preserve all original message fields and add defaults for required fields
            status_word_message = {
                'command_type': message.get('command_type', None),
                'radar_type': message.get('radar_type', None),
                'status': message.get('status', 'acknowledged'),
                'request_id': request_id,
                'timestamp': message.get('timestamp', time.time()),
                'additional_info': message.get('additional_info')
                }

            # Add any other fields from original message
            for key, value in message.items():
                if key not in status_word_message:
                    status_word_message[key] = value

            # Store acknowledgment with complete message
            # Force immediate processing in test environment
            if 'test' in sys.modules:
                logger.info("Test environment detected - forcing immediate storage")
                await self.radar_response_service.handle_status_word_async(status_word_message)
                # Add delay to ensure storage completes
                await asyncio.sleep(0.5)
            else:
                # Normal operation
                await self.radar_response_service.handle_status_word_async(status_word_message)

            logger.info(f"Routed status word with request_id: {request_id}")
        except Exception as e:
            logger.error(f"Error routing status word: {e}")
            raise

    async def route_event(self, event_data: Dict[str, Any]):
        """Route event data to appropriate handlers.

        Args:
            event_data: Dictionary containing event data
        """
        try:
            # Get display message handler
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            if not display_handler:
                logger.error("[ROUTE_EVENT] Could not get display message handler")
                raise Exception("Display message handler not found")

            ## Handle display mode changed events

            ## Extract event type
            event_type = event_data.get('event_type')
            if not event_type:
                logger.warning("Event missing event_type")
                return
            logger.info(f"[ROUTE_EVENT] Routing event: {event_type}")

            # NOTE (production readiness re-analysis, August 2026): `mode` and
            # `display_type` were referenced below (mode_map[mode],
            # display_type=display_type in the send_request() call, etc.)
            # without ever being extracted from event_data -- found via
            # `ruff check --select F821` (undefined-name). Confirmed via the
            # only real caller, DisplayResponseService.py's mode-change-event
            # publication, that event_data always carries both keys
            # ('display_type', 'mode', plus 'mode_value'/'source_system'/etc.)
            # -- this reads as a straightforward missing-extraction bug, not a
            # design gap. Every call to route_event() before this fix hit
            # `if display_handler and mode:` immediately, raised
            # NameError('mode' is not defined), and was silently caught by
            # this method's own `except Exception as handler_error:` below,
            # meaning the entire "route a display mode change through the
            # display message handler" path -- this method's actual purpose
            # for mode-change events -- had never once succeeded.
            mode = event_data.get('mode')
            display_type = event_data.get('display_type')

            # Only send a new mode change request for non-completion messages
            # This prevents the loop where completion messages trigger new requests
            try:
                # Get display message handler
                from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
                display_handler = get_display_message_handler()

                if display_handler and mode:
                    # Import radar display modes
                    from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode

                    # Map the mode string to RadarDisplayMode enum
                    mode_map = {
                        'STANDBY': RadarDisplayMode.STANDBY,
                        'SURVEILLANCE': RadarDisplayMode.SURVEILLANCE,
                        'MAPPING': RadarDisplayMode.MAPPING,
                        'TURBULENCE': RadarDisplayMode.TURBULENCE,
                        'WINDSHEAR': RadarDisplayMode.WINDSHEAR
                    }

                    # Get the display mode - use the actual mode from the event
                    # If mode is not in the map, log an error but continue with the original mode string
                    if mode in mode_map:
                        display_mode = mode_map[mode]
                        logger.warning(f"[DISPLAY_MODE] Mapped mode {mode} to {display_mode.name}")

                        # Create enhanced command data with explicit flags to prevent loops
                        enhanced_command_data = {
                            'mode': display_mode.name,
                            'force_update': True,
                            'update_visual': True,
                            '_processed_by_display_response': True,  # Mark as processed
                            '_prevent_rerouting': True,  # Add explicit flag to prevent re-routing
                            'transaction_id': str(uuid.uuid4())  # Add unique transaction ID
                        }

                        # Send mode change through proper channel
                        logger.warning(f"[DISPLAY_MODE] Setting display mode to {display_mode.name} for {display_type}")
                        await display_handler.send_request(
                            display_type=display_type,
                            command_type='mode_change',
                            command_data=enhanced_command_data
                        )
                        logger.warning(f"[DISPLAY_MODE] Sent mode change through display message handler")
                    else:
                        logger.error(f"[DISPLAY_MODE] Unknown mode: {mode}, cannot map to RadarDisplayMode")
            except Exception as handler_error:
                logger.error(f"[DISPLAY_MODE] Error updating through display handler: {str(handler_error)}")
                logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"[ROUTE_EVENT] Error routing event: {e}")
            logger.error(traceback.format_exc())

    async def route_mode_change(self, message: Dict[str, Any]):
        """Route mode change data to storage using UnifiedRouter"""
        try:
            # Extract request_id for logging
            request_id = message.get('request_id')
            if not request_id:
                raise ValueError("[MSG_ROUTE_MODE_CHANGE] message missing request_id")

            # Log routing attempt
            logger.info(f"[MSG_ROUTE_MODE_CHANGE] Routing mode change with request_id: {request_id} via UnifiedRouter")

            # Add message_type if not present
            if 'message_type' not in message:
                radar_type = message.get('radar_type', 'weather_radar')
                message['message_type'] = f"{radar_type}_modeChangeRequest"

            # Make sure command_type is set
            if 'command_type' not in message:
                message['command_type'] = 'mode_change'

            # Route through UnifiedRouter
            from FMOFP.local_messaging.routing.system_integration import route_message
            result = route_message(message)

            if result:
                logger.info(f"[MSG_ROUTE_MODE_CHANGE] Successfully routed mode change with request_id: {request_id}")
            else:
                logger.error(f"[MSG_ROUTE_MODE_CHANGE] Failed to route mode change with request_id: {request_id}")

            return result
        except Exception as e:
            logger.error(f"[MSG_ROUTE_MODE_CHANGE] Error routing mode change: {e}")
            logger.error(traceback.format_exc())
            return False

    async def get_mode_changes(self, radar_type: Optional[str] = None,
                             start_time: Optional[float] = None,
                             end_time: Optional[float] = None) -> List[Tuple]:
        """Get mode changes from storage with optional filtering"""
        try:
            # Get mode changes through response service
            mode_changes = self.radar_response_service.get_mode_changes(
                radar_type=radar_type,
                start_time=start_time,
                end_time=end_time
            )
            logger.info(f"Retrieved {len(mode_changes)} mode changes for {radar_type}")
            return mode_changes
        except Exception as e:
            logger.error(f"Error getting mode changes: {e}")
            return []

    async def get_command_acknowledgments(self, radar_type: Optional[str] = None,
                                        start_time: Optional[float] = None,
                                        end_time: Optional[float] = None) -> List[Tuple]:
        """Get command acknowledgments from storage with optional filtering"""
        try:
            # Get acknowledgments through response service
            acknowledgments = self.radar_response_service.get_command_acknowledgments(
                radar_type=radar_type,
                start_time=start_time,
                end_time=end_time
            )
            logger.info(f"Retrieved {len(acknowledgments)} acknowledgments for {radar_type}")
            return acknowledgments
        except Exception as e:
            logger.error(f"Error getting command acknowledgments: {e}")
            return []

    async def _ensure_vil_service(self):
        """Ensure VIL service is available, creating it if necessary"""
        if not self._vil_service:
            # Try to get it from the system manager
            from FMOFP.core.system_manager import get_system_manager
            system_manager = get_system_manager()
            self._vil_service = system_manager.get_component('vil_response_service')

            if not self._vil_service:
                logger.warning("[VIL_FLOW] VIL Response Service not found in system manager - creating fallback instance")
                # Create a new VIL Response Service instance
                from FMOFP.local_messaging.routing.response_services.data_response_services.vil_response_service import VILResponseService
                from FMOFP.storage.DBM import DatabaseManager

                # Get radar database
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')

                # Create VIL service
                self._vil_service = VILResponseService(radar_db)

                # Start the service
                event_loop = asyncio.get_event_loop()
                await self._vil_service.start(event_loop=event_loop)

                # Register with system manager
                system_manager.register_component('vil_response_service', self._vil_service)
                logger.info("[VIL_FLOW] Created and registered new VIL Response Service instance")
            else:
                logger.info("[VIL_FLOW] Retrieved VIL Response Service from system manager")

        return self._vil_service

    # New helper method for precipitation service
    async def _ensure_precipitation_service(self):
        """Ensure Precipitation service is available, creating it if necessary"""
        # Try to get it from the system manager
        from FMOFP.core.system_manager import get_system_manager
        system_manager = get_system_manager()
        precip_service = system_manager.get_component('precipitation_response_service')

        if not precip_service:
            logger.warning("[LOC_MSG_RT_SERV_PRECIP_FLOW] Precipitation Response Service not found in system manager - creating fallback instance")
            # Create a new Precipitation Response Service instance
            from FMOFP.local_messaging.routing.response_services.data_response_services.precipitation_response_service import get_precipitation_response_service
            from FMOFP.storage.DBM import DatabaseManager

            # Get the service using the singleton
            precip_service = get_precipitation_response_service()

            # Start the service
            event_loop = asyncio.get_event_loop()
            await precip_service.start(event_loop=event_loop)

            # Register with system manager
            system_manager.register_component('precipitation_response_service', precip_service)
            logger.info("[LOC_MSG_RT_SERV_PRECIP_FLOW] Created and registered new Precipitation Response Service instance")
        else:
            logger.info("[LOC_MSG_RT_SERV_PRECIP_FLOW] Retrieved Precipitation Response Service from system manager")

        return precip_service

    async def route_vil_data(self, message: Dict[str, Any]):
        """Route VIL data using UnifiedRouter"""
        try:
            # Extract request_id for logging
            request_id = message.get('request_id')
            if not request_id:
                raise ValueError("[LOC_MSG_RT_SERV_PRECIP_FLOW] Mode change message missing request_id")

            # Log routing attempt
            logger.info(f"[VIL_FLOW] Routing VIL data with request_id: {request_id} via UnifiedRouter")

            # Add message_type if not present
            if 'message_type' not in message:
                message['message_type'] = 'weather_radarVILResponse'

            # Make sure command_type is set
            if 'command_type' not in message:
                message['command_type'] = 'vil_data'

            # Route through UnifiedRouter
            from FMOFP.local_messaging.routing.system_integration import route_message
            result = route_message(message)

            if result:
                logger.info(f"[VIL_FLOW] Successfully routed VIL data with request_id: {request_id}")
            else:
                logger.warning(f"[VIL_FLOW] Failed to route VIL data with request_id: {request_id}")

            return result
        except Exception as e:
            logger.error(f"Error routing VIL data: {e}")
            logger.error(traceback.format_exc())
            return False


    async def route_precipitation_data(self, message: Dict[str, Any]):
        """
        Route precipitation data to display system.

        This method handles converting various formats of precipitation data into
        proper PrecipitationData objects, taking into account serialization/deserialization
        that may have occurred during message transmission.

        Args:
            message: Dictionary containing precipitation data and metadata

        Raises:
            ValueError: If no valid precipitation data could be extracted
        """
        try:
            # LOOP PREVENTION: Check if message has already been processed
            if message.get('metadata', {}).get('_processed_by_routing_service', False):
                logger.warning("[PRECIPITATION_FLOW] Detected routing loop - message already processed by routing service")
                return

            # Extract request_id if present
            request_id = message.get('request_id')
            if not request_id:
                raise ValueError("[PRECIPITATION_FLOW] Precipitation data missing request_id")


            # Extract original precipitation data with enhanced checking
            precipitation_data = None

            # Try different locations where precipitation data might be stored
            for key in ['precipitation_data', 'data', 'precipitation']:
                if key in message and message[key] is not None:
                    precipitation_data = message[key]
                    logger.info(f"[PRECIPITATION_FLOW] Found precipitation data in '{key}' field")
                    break

            # Check for nested data structures
            if precipitation_data is None and 'metadata' in message and isinstance(message['metadata'], dict):
                metadata = message['metadata']
                for key in ['precipitation_data', 'data', 'precipitation', 'weather_data']:
                    if key in metadata and metadata[key] is not None:
                        if key == 'weather_data' and isinstance(metadata[key], dict):
                            # Check inside weather_data
                            for wkey in ['precipitation_data', 'precipitation']:
                                if wkey in metadata[key] and metadata[key][wkey] is not None:
                                    precipitation_data = metadata[key][wkey]
                                    logger.info(f"[PRECIPITATION_FLOW] Found precipitation data in metadata.weather_data.{wkey}")
                                    break
                        else:
                            precipitation_data = metadata[key]
                            logger.info(f"[PRECIPITATION_FLOW] Found precipitation data in metadata.{key}")
                            break

            if precipitation_data is None:
                logger.error("[PRECIPITATION_FLOW] No precipitation data found in message")
                # Log the complete message structure without sensitive data
                logger.debug(f"[PRECIPITATION_FLOW] Message keys: {list(message.keys())}")
                if 'metadata' in message and isinstance(message['metadata'], dict):
                    logger.debug(f"[PRECIPITATION_FLOW] Metadata keys: {list(message['metadata'].keys())}")
                raise ValueError("No precipitation data found in message")

            # Import here to avoid circular imports
            from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData

            # Log detailed message for debugging
            logger.info(f"[PRECIPITATION_FLOW] Routing precipitation data to display system")
            logger.info(f"[PRECIPITATION_FLOW] Precipitation data type: {type(precipitation_data)}")

            # Enhanced data conversion with better null handling
            def extract_position(data_point):
                """Extract position from various formats."""
                if isinstance(data_point, dict):
                    # Try to get position tuple directly
                    position = data_point.get('position')
                    if position is not None:
                        # Return tuple as is
                        return position

                    # Try to get x, y coordinates
                    x = data_point.get('x', data_point.get('position_x'))
                    y = data_point.get('y', data_point.get('position_y'))

                    if x is not None and y is not None:
                        return (float(x), float(y))

                    # Try to get x_position, y_position
                    x = data_point.get('x_position')
                    y = data_point.get('y_position')

                    if x is not None and y is not None:
                        return (float(x), float(y))

                    # Default to (0.0, 0.0) if no position found
                    return (0.0, 0.0)
                elif hasattr(data_point, 'position'):
                    return data_point.position
                elif hasattr(data_point, 'x') and hasattr(data_point, 'y'):
                    return (float(data_point.x), float(data_point.y))
                elif hasattr(data_point, 'position_x') and hasattr(data_point, 'position_y'):
                    return (float(data_point.position_x), float(data_point.position_y))
                else:
                    return (0.0, 0.0)

            # Create proper precipitation data objects
            precipitation_data_objects = []

            # Handle list of data points
            if isinstance(precipitation_data, list):
                for data_point in precipitation_data:
                    try:
                        # Skip None values in the list
                        if data_point is None:
                            continue

                        # Handle dictionary format (most common after serialization)
                        if isinstance(data_point, dict):
                            # Extract position from dictionary with fallback to defaults
                            position = extract_position(data_point)

                            # Extract other properties with fallbacks
                            precip_type = data_point.get('type', 'unknown')
                            # Handle string vs list format for rate
                            rate = data_point.get('rate', 20.0)
                            if isinstance(rate, list) and len(rate) > 0:
                                rate = rate[0]
                            # Handle string vs float for intensity
                            intensity = data_point.get('intensity', 0.5)
                            if isinstance(intensity, str):
                                try:
                                    intensity = float(intensity)
                                except (ValueError, TypeError):
                                    intensity = 0.5

                            show_values = bool(data_point.get('show_values', True))

                            # Create PrecipitationData object with extracted values
                            precip_obj = PrecipitationData(
                                position=position,
                                type=precip_type,
                                rate=float(rate),
                                intensity=float(intensity),
                                show_values=show_values
                            )

                            # Add request_id and timestamp
                            precip_obj.request_id = request_id
                            precip_obj.timestamp = message.get('timestamp', time.time())

                            # Add any additional info
                            if 'additional_info' not in precip_obj.additional_info and 'additional_info' in data_point:
                                precip_obj.additional_info = data_point.get('additional_info', {})

                            precipitation_data_objects.append(precip_obj)

                        # Handle objects with attributes (may be original PrecipitationData objects)
                        elif hasattr(data_point, 'position') or (hasattr(data_point, 'x') and hasattr(data_point, 'y')):
                            # This might be a PrecipitationData object already
                            if isinstance(data_point, PrecipitationData):
                                # Update request_id and timestamp
                                data_point.request_id = request_id
                                data_point.timestamp = message.get('timestamp', time.time())
                                precipitation_data_objects.append(data_point)
                            else:
                                # Create a new PrecipitationData from the object
                                position = extract_position(data_point)

                                # Extract other properties
                                precip_type = getattr(data_point, 'type', 'unknown')
                                rate = getattr(data_point, 'rate', 20.0)
                                intensity = getattr(data_point, 'intensity', 0.5)
                                show_values = bool(getattr(data_point, 'show_values', True))

                                precip_obj = PrecipitationData(
                                    position=position,
                                    type=precip_type,
                                    rate=float(rate),
                                    intensity=float(intensity),
                                    show_values=show_values
                                )

                                # Add request_id and timestamp
                                precip_obj.request_id = request_id
                                precip_obj.timestamp = message.get('timestamp', time.time())

                                # Add any additional info
                                if hasattr(data_point, 'additional_info'):
                                    precip_obj.additional_info = getattr(data_point, 'additional_info', {})

                                precipitation_data_objects.append(precip_obj)
                        else:
                            # Try to convert other formats - last resort
                            logger.warning(f"[PRECIPITATION_FLOW] Unrecognized data point format: {type(data_point)}")

                            # Try to convert to string and extract key information
                            data_str = str(data_point)
                            if 'position' in data_str or 'type' in data_str:
                                logger.info(f"[PRECIPITATION_FLOW] Attempting to parse data from string representation")

                                # Create a default precipitation object and continue
                                precip_obj = PrecipitationData(
                                    position=(0.0, 0.0),
                                    type='unknown',
                                    rate=20.0,
                                    intensity=0.5,
                                    show_values=True
                                )

                                precip_obj.request_id = request_id
                                precip_obj.timestamp = message.get('timestamp', time.time())
                                precipitation_data_objects.append(precip_obj)
                    except Exception as data_point_error:
                        # Log the error but continue with other data points
                        logger.error(f"[PRECIPITATION_FLOW] Error processing data point: {data_point_error}")
                        logger.error(traceback.format_exc())
                        # Continue to the next data point
                        continue

            # Handle single data point (object or dictionary)
            elif precipitation_data is not None:
                try:
                    # Handle dictionary format
                    if isinstance(precipitation_data, dict):
                        # Extract position
                        position = extract_position(precipitation_data)

                        # Extract other properties with fallbacks
                        precip_type = precipitation_data.get('type', 'unknown')
                        rate = precipitation_data.get('rate', 20.0)
                        if isinstance(rate, str):
                            try:
                                rate = float(rate)
                            except (ValueError, TypeError):
                                rate = 20.0

                        intensity = precipitation_data.get('intensity', 0.5)
                        if isinstance(intensity, str):
                            try:
                                intensity = float(intensity)
                            except (ValueError, TypeError):
                                intensity = 0.5

                        show_values = bool(precipitation_data.get('show_values', True))

                        # Create PrecipitationData object
                        precip_obj = PrecipitationData(
                            position=position,
                            type=precip_type,
                            rate=float(rate),
                            intensity=float(intensity),
                            show_values=show_values
                        )

                        precip_obj.request_id = request_id
                        precip_obj.timestamp = message.get('timestamp', time.time())

                        # Add any additional info
                        if 'additional_info' in precipitation_data:
                            precip_obj.additional_info = precipitation_data.get('additional_info', {})

                        precipitation_data_objects.append(precip_obj)

                    # Handle object format (may be original PrecipitationData object)
                    elif hasattr(precipitation_data, 'position') or (hasattr(precipitation_data, 'x') and hasattr(precipitation_data, 'y')):
                        # This might be a PrecipitationData object already
                        if isinstance(precipitation_data, PrecipitationData):
                            # Update request_id and timestamp
                            precipitation_data.request_id = request_id
                            precipitation_data.timestamp = message.get('timestamp', time.time())
                            precipitation_data_objects.append(precipitation_data)
                        else:
                            # Create a new PrecipitationData from the object
                            position = extract_position(precipitation_data)

                            # Extract other properties
                            precip_type = getattr(precipitation_data, 'type', 'unknown')
                            rate = getattr(precipitation_data, 'rate', 20.0)
                            intensity = getattr(precipitation_data, 'intensity', 0.5)
                            show_values = bool(getattr(precipitation_data, 'show_values', True))

                            precip_obj = PrecipitationData(
                                position=position,
                                type=precip_type,
                                rate=float(rate),
                                intensity=float(intensity),
                                show_values=show_values
                            )

                            precip_obj.request_id = request_id
                            precip_obj.timestamp = message.get('timestamp', time.time())

                            # Add any additional info
                            if hasattr(precipitation_data, 'additional_info'):
                                precip_obj.additional_info = getattr(precipitation_data, 'additional_info', {})

                            precipitation_data_objects.append(precip_obj)
                    else:
                        # Try to parse from string representation - last resort
                        logger.warning(f"[PRECIPITATION_FLOW] Unrecognized precipitation data format: {type(precipitation_data)}")

                        # Create a default precipitation object as fallback
                        precip_obj = PrecipitationData(
                            position=(0.0, 0.0),
                            type='unknown',
                            rate=20.0,
                            intensity=0.5,
                            show_values=True
                        )

                        precip_obj.request_id = request_id
                        precip_obj.timestamp = message.get('timestamp', time.time())
                        precipitation_data_objects.append(precip_obj)
                except Exception as single_data_error:
                    # Log the error
                    logger.error(f"[PRECIPITATION_FLOW] Error processing single precipitation data: {single_data_error}")
                    logger.error(traceback.format_exc())
                    # Continue with the rest of the method

            # Create at least one default data point if none were successfully created
            if not precipitation_data_objects:
                logger.warning("[PRECIPITATION_FLOW] No valid precipitation data objects could be created - using default")

                # Create a default precipitation object to ensure display is updated
                precip_obj = PrecipitationData(
                    position=(0.0, 0.0),
                    type='unknown',
                    rate=0.0,
                    intensity=0.0,
                    show_values=False
                )

                precip_obj.request_id = request_id
                precip_obj.timestamp = message.get('timestamp', time.time())
                precip_obj.additional_info = {'fallback_data': True}
                precipitation_data_objects.append(precip_obj)

                logger.info("[PRECIPITATION_FLOW] Created default precipitation data object as fallback")

            # Log the result of conversion
            logger.info(f"[PRECIPITATION_FLOW] Successfully created {len(precipitation_data_objects)} precipitation data objects")

            # Prepare message for display system with enhanced metadata
            precip_message = {
                'data': precipitation_data_objects[0] if precipitation_data_objects else None,
                'precipitation_data': precipitation_data_objects,  # Include full list for batch processing
                'request_id': request_id,
                'timestamp': message.get('timestamp', time.time()),
                'mode': message.get('mode', 'SURVEILLANCE'),
                'message_type': 'weather_radarPrecipitationResponse',  # Ensure correct message type
                'metadata': {
                    'data_type': 'precipitation',
                    'source': 'weather_radar',
                    'destination': 'display_system',
                    'original_request_id': request_id,
                    'precipitation_message': True,
                    '_processed_by_routing_service': True  # LOOP PREVENTION FLAG
                }
            }

            # Preserve any metadata from the original message
            if 'metadata' in message and isinstance(message['metadata'], dict):
                # Merge metadata with our new metadata, keeping our keys for critical fields
                for key, value in message['metadata'].items():
                    if key not in precip_message['metadata']:
                        precip_message['metadata'][key] = value

            # Get display message handler
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()

            if not display_handler:
                logger.error("[PRECIPITATION_FLOW] Could not get display message handler")
                raise ValueError("Could not get display message handler")

            # Send precipitation data to display system
            await display_handler.handle_precipitation_data(precip_message)

            logger.info(f"[PRECIPITATION_FLOW] Successfully routed precipitation data to display system with request_id: {request_id}")
        except Exception as e:
            logger.warning(f"[PRECIPITATION_FLOW] Error routing precipitation data: {e}")
            logger.error(traceback.format_exc())
            raise


    async def route_comms_message(self, message: Dict[str, Any]) -> None:
        """
        Route a COMMS_* message directly to CommsService.

        Supported message_types (from message_types.py):
            comms_radioFreqSet, comms_radioModeSet,
            comms_satcomAcquire, comms_datalinkModeSet,
            comms_transmitRadio, comms_sendSatcom, comms_sendDatalink,
            comms_statusRequest
        """
        try:
            if self._comms_service is None:
                from FMOFP.Systems.comms.messaging_service import get_comms_service
                self._comms_service = get_comms_service()

            msg_type = message.get('message_type', '')
            params   = message.get('params', message.get('data', {}))

            if msg_type in ('comms_radioFreqSet', 'COMMS_RADIO_FREQ_SET'):
                freq = params.get('frequency') if isinstance(params, dict) else None
                if freq is not None:
                    self._comms_service.set_radio_frequency(float(freq))

            elif msg_type in ('comms_radioModeSet', 'COMMS_RADIO_MODE_SET'):
                mode = params.get('mode') if isinstance(params, dict) else None
                if mode:
                    self._comms_service.set_radio_mode(str(mode))

            elif msg_type in ('comms_satcomAcquire', 'COMMS_SATCOM_ACQUIRE'):
                self._comms_service.acquire_satellite()

            elif msg_type in ('comms_datalinkModeSet', 'COMMS_DATALINK_MODE_SET'):
                mode = params.get('mode') if isinstance(params, dict) else None
                if mode:
                    self._comms_service.set_datalink_mode(str(mode))

            elif msg_type in ('comms_transmitRadio', 'COMMS_TRANSMIT_RADIO'):
                text = params.get('message', '') if isinstance(params, dict) else str(params)
                self._comms_service.transmit_radio(text)

            elif msg_type in ('comms_sendSatcom', 'COMMS_SEND_SATCOM'):
                text = params.get('message', '') if isinstance(params, dict) else str(params)
                self._comms_service.send_satcom(text)

            elif msg_type in ('comms_sendDatalink', 'COMMS_SEND_DATALINK'):
                text     = params.get('message', '') if isinstance(params, dict) else str(params)
                priority = params.get('priority', 2) if isinstance(params, dict) else 2
                self._comms_service.send_datalink(text, int(priority))

            elif msg_type in ('comms_statusRequest', 'COMMS_STATUS_REQUEST'):
                # Status requests are answered by the display layer reading CommsService directly
                pass

            logger.info(f"[ROUTE_COMMS] Handled {msg_type}")

        except Exception as e:
            logger.error(f"[ROUTE_COMMS] Error routing comms message: {e}")
            logger.error(traceback.format_exc())

    async def route_mission_message(self, message: Dict[str, Any]) -> None:
        """
        Route a MISSION_* message directly to MissionService.

        Supported message_types (from message_types.py):
            mission_phaseSet, mission_phaseAdvance,
            mission_waypointAdd, mission_waypointRemove,
            mission_targetDesignate, mission_targetEngage,
            mission_targetBDA, mission_targetUpdate,
            mission_unitAdd, mission_unitUpdate,
            mission_objectivesSet, mission_roeSet,
            mission_intelUpdate, mission_routeOptimise,
            mission_statusRequest
        """
        try:
            if self._mission_service is None:
                from FMOFP.Systems.missionPlanning.missionService import get_mission_service
                self._mission_service = get_mission_service()

            msg_type = message.get('message_type', '')
            params   = message.get('params', message.get('data', {}))
            if not isinstance(params, dict):
                params = {}

            if msg_type in ('mission_phaseSet', 'MISSION_PHASE_SET'):
                phase = params.get('phase', '')
                if phase:
                    self._mission_service.set_phase(str(phase))

            elif msg_type in ('mission_phaseAdvance', 'MISSION_PHASE_ADVANCE'):
                self._mission_service.advance_phase()

            elif msg_type in ('mission_waypointAdd', 'MISSION_WAYPOINT_ADD'):
                self._mission_service.add_waypoint(
                    name   = params.get('name', 'WP'),
                    lat    = float(params.get('lat', 0)),
                    lon    = float(params.get('lon', 0)),
                    alt_ft = float(params.get('alt_ft', 0)),
                    wp_type = params.get('wp_type', 'NAV'),
                )

            elif msg_type in ('mission_waypointRemove', 'MISSION_WAYPOINT_REMOVE'):
                wp_id = params.get('wp_id')
                if wp_id is not None:
                    self._mission_service._ctrl.route.remove_waypoint(int(wp_id))

            elif msg_type in ('mission_targetDesignate', 'MISSION_TARGET_DESIGNATE'):
                self._mission_service.designate_target(
                    name        = params.get('name', 'TGT'),
                    lat         = float(params.get('lat', 0)),
                    lon         = float(params.get('lon', 0)),
                    alt_ft      = float(params.get('alt_ft', 0)),
                    priority    = int(params.get('priority', 3)),
                    target_type = params.get('target_type', 'POINT'),
                )

            elif msg_type in ('mission_targetEngage', 'MISSION_TARGET_ENGAGE'):
                target_id = params.get('target_id', '')
                weapon    = params.get('weapon', 'UNSPECIFIED')
                if target_id:
                    self._mission_service.engage_target(target_id, weapon)

            elif msg_type in ('mission_targetBDA', 'MISSION_TARGET_BDA'):
                target_id = params.get('target_id', '')
                destroyed = bool(params.get('destroyed', False))
                if target_id:
                    self._mission_service._ctrl.targeting.mark_bda_pending(target_id)
                    self._mission_service._ctrl.targeting.assess_damage(target_id, destroyed)

            elif msg_type in ('mission_targetUpdate', 'MISSION_TARGET_UPDATE'):
                target_id = params.get('target_id', '')
                if target_id:
                    self._mission_service.radar_target_update(
                        target_id    = target_id,
                        lat          = float(params.get('lat', 0)),
                        lon          = float(params.get('lon', 0)),
                        alt_ft       = float(params.get('alt_ft', 0)),
                        speed        = float(params.get('speed_kts', 0)),
                        heading      = float(params.get('heading_deg', 0)),
                        quality      = float(params.get('track_quality', 0.8)),
                    )

            elif msg_type in ('mission_unitAdd', 'MISSION_UNIT_ADD'):
                unit_data = params.get('unit_data', params)
                self._mission_service.add_unit(unit_data)

            elif msg_type in ('mission_unitUpdate', 'MISSION_UNIT_UPDATE'):
                unit_id = params.get('unit_id', '')
                if unit_id:
                    pos = params.get('position')
                    if pos and len(pos) >= 2:
                        self._mission_service._ctrl.update_unit_position(
                            unit_id, float(pos[0]), float(pos[1]),
                            float(pos[2]) if len(pos) > 2 else 0.0)
                    status = params.get('status')
                    if status:
                        self._mission_service._ctrl.oob.update_status(unit_id, status)

            elif msg_type in ('mission_objectivesSet', 'MISSION_OBJECTIVES_SET'):
                self._mission_service.set_objectives(params.get('objectives', []))

            elif msg_type in ('mission_roeSet', 'MISSION_ROE_SET'):
                self._mission_service.set_roe(params.get('rules', []))

            elif msg_type in ('mission_intelUpdate', 'MISSION_INTEL_UPDATE'):
                self._mission_service.update_intelligence(params.get('data', params))

            elif msg_type in ('mission_routeOptimise', 'MISSION_ROUTE_OPTIMISE'):
                self._mission_service.optimise_route()

            elif msg_type in ('mission_statusRequest', 'MISSION_STATUS_REQUEST'):
                # Display reads MissionService.get_data() directly; no action needed here
                pass

            logger.info(f"[ROUTE_MISSION] Handled {msg_type}")

        except Exception as e:
            logger.error(f"[ROUTE_MISSION] Error routing mission message: {e}")
            logger.error(traceback.format_exc())

    async def route_display_command(self, message: Dict[str, Any]):
        """Route display command to storage"""
        try:
            # Extract request_id if present
            request_id = message.get('request_id')
            if not request_id:
                logger.warning("Display command missing request_id")
                return

            # Prepare complete display command data
            display_command_data = {
                'command_type': message.get('command_type', None),
                'display_type': message.get('display_type', None),
                'status': message.get('status', 'acknowledged'),
                'request_id': request_id,
                'timestamp': message.get('timestamp', time.time()),
                'additional_info': message.get('additional_info', {})
            }

            # Log the data being sent
            logger.info(f"Sending display command data to storage: {display_command_data}")

            # Store display command with complete data
            await self.display_response_service.handle_display_command(display_command_data)

            logger.info(f"Routed display command with request_id: {request_id}")
        except Exception as e:
            logger.error(f"Error routing display command: {e}")
            raise

    async def route_message(self, message: MIL_STD_1553B_Message):
        """Route a message using the Unified Router exclusively.

        Args:
            message: The MIL-STD-1553B message to route

        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Check for loop prevention flags
            metadata = {}

            # Check if message is a dict with metadata
            if isinstance(message, dict) and 'metadata' in message:
                metadata = message['metadata']
            # Check if message has metadata attribute
            elif hasattr(message, 'metadata') and message.metadata:
                metadata = message.metadata

            # Initialize routed messages set if it doesn't exist
            if not hasattr(self, '_routed_messages'):
                self._routed_messages = set()

            # Extract message ID from the message
            request_id = None
            if isinstance(message, dict):
                request_id = message.get('request_id')
            elif hasattr(message, 'request_id'):
                request_id = message.request_id

            transaction_id = None
            if isinstance(metadata, dict):
                transaction_id = metadata.get('transaction_id')

            # Create a unique message identifier
            message_id = None
            if request_id:
                command_type = None
                if isinstance(message, dict):
                    command_type = message.get('command_type')
                elif hasattr(message, 'command_type'):
                    command_type = message.command_type

                if command_type:
                    message_id = f"{request_id}_{command_type}"
                else:
                    message_id = request_id

            # If we have a transaction_id, use it as part of the message identifier
            if transaction_id:
                if message_id:
                    message_id = f"{message_id}_{transaction_id}"
                else:
                    message_id = transaction_id

            # Check if this message has already been processed
            if message_id and message_id in self._routed_messages:
                logger.warning(f"[ROUTE] BREAKING LOOP - Message with ID {message_id} already routed")
                return True

            # Check if this message is marked as already processed
            if isinstance(metadata, dict):
                if metadata.get('_processed_by_routing_service'):
                    logger.warning(f"[ROUTE] BREAKING LOOP - Message already processed by routing service")
                    return True
                if metadata.get('_prevent_rerouting'):
                    logger.warning(f"[ROUTE] BREAKING LOOP - Message has _prevent_rerouting flag")
                    return True
                if metadata.get('final_delivery_to_display'):
                    logger.warning(f"[ROUTE] BREAKING LOOP - Message marked as final delivery")
                    return True

                # Mark message as processed by routing service
                metadata['_processed_by_routing_service'] = True

            # For dict messages, add the flag to metadata
            if isinstance(message, dict):
                if 'metadata' not in message:
                    message['metadata'] = {}
                message['metadata']['_processed_by_routing_service'] = True

            # Add to routed messages set if we have an ID
            if message_id:
                self._routed_messages.add(message_id)
                # Limit set size to prevent memory leaks
                if len(self._routed_messages) > 1000:
                    # Remove oldest entries (this is approximation as sets don't maintain order)
                    while len(self._routed_messages) > 800:
                        self._routed_messages.pop()

            # Log message details for debugging
            logger.info(f"[ROUTE] Routing message:")
            logger.info(f"[ROUTE]   Message ID: {message_id}")
            logger.info(f"[ROUTE]   System: {getattr(message, 'destination', None)}")
            logger.info(f"[ROUTE]   Message type: {getattr(message, 'message_type', None)}")
            logger.info(f"[ROUTE]   Command word: {getattr(message, 'command_word', None)}")
            logger.info(f"[ROUTE]   Request ID: {request_id}")

            # Use the Unified Router exclusively for message routing
            from FMOFP.local_messaging.routing.system_integration import route_message

            # Detect COMMS messages and handle directly
            raw_type = None
            if isinstance(message, dict):
                raw_type = message.get('message_type') or message.get('command_type', '')
            elif hasattr(message, 'message_type'):
                raw_type = message.message_type or getattr(message, 'command_type', '')
            raw_type = str(raw_type or '').lower()

            if 'comms_' in raw_type or raw_type.startswith('comms'):
                msg_dict = message if isinstance(message, dict) else vars(message)
                await self.route_comms_message(msg_dict)
                return True

            if 'mission_' in raw_type or raw_type.startswith('mission'):
                msg_dict = message if isinstance(message, dict) else vars(message)
                await self.route_mission_message(msg_dict)
                return True

            # Route the message using the unified router through the system_integration interface
            result = route_message(message)

            if result:
                logger.info("[ROUTE] Message successfully routed using Unified Router")
            else:
                logger.error("[ROUTE] Unified Router failed to route message")
                logger.error("[ROUTE] Message will not be processed - NO FALLBACK TO LEGACY ROUTING")
                # Do not fall back to legacy routing if unified router fails

            return result

        except Exception as e:
            logger.error(f"Error routing message: {str(e)}")
            logger.error(traceback.format_exc())
            # Even in case of exception, do not fall back to legacy routing
            return False

def get_message_routing_service() -> MessageRoutingService:
    """Get the singleton instance of MessageRoutingService"""
    return MessageRoutingService()
