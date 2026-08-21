"""
Display Response Service

Handles responses to display system messages.
Similar to RadarResponseService but adapted for display operations.
"""

import asyncio
import traceback
import time
import sys
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Tuple, Union
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.storage.DBM import DatabaseManager
@dataclass
class DisplayCommand:
    """Display command data for storage."""
    timestamp: float
    command_type: str
    display_type: str
    status: str
    request_id: str
    additional_info: Optional[Dict] = None

logger = get_logger()

class DisplayResponseService:
    # Maximum recursion depth for message processing to prevent infinite loops
    MAX_PROCESSING_DEPTH = 5
    # Maximum number of retries for message processing
    MAX_RETRIES = 3
    # Timeout for message processing in seconds
    MESSAGE_TIMEOUT = 10.0
    
    def __init__(self):
        """Initialize display response service."""
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._response_queue = asyncio.Queue()
        self._acknowledgment_queue = asyncio.Queue()
        self._running = False
        self._processor_task = None
        self._acknowledgment_processor = None
        self._initialized = False
        
        # Message processing tracking
        self._processing_depth = {}  # Track recursion depth by request_id
        self._processed_messages = set()  # Track already processed message IDs
        self._message_timestamps = {}  # Track when messages were first seen
        self._processing_locks = {}  # Locks to prevent concurrent processing of the same message
        
        # Initialize database connections
        self.db_manager = DatabaseManager(config_path='FMOFP/dbConfig.xml')
        self.display_db = self.db_manager.get_system_db('displays')
        self.radar_db = self.db_manager.get_system_db('radar_management')
        
        # Initialize routing service as None - will be set by MessageRoutingService
        self.routing_service = None
        
        # Create tables if they don't exist
        self._create_tables()
        
        # Start the timeout watchdog
        self._watchdog_task = None
        
        logger.info("DisplayResponseService basic initialization complete")

    def set_routing_service(self, routing_service):
        """Set the message routing service.
        
        Args:
            routing_service: The MessageRoutingService instance
        """
        self.routing_service = routing_service
        logger.info("Message routing service set in DisplayResponseService")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("DisplayResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("DisplayResponseService fully initialized")
            
        except Exception as e:
            logger.error(f"Error during DisplayResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize DisplayResponseService") from e

    def _create_tables(self):
        """Create necessary database tables."""
        try:
            # Create display commands table
            self.display_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS display_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    command_type TEXT NOT NULL,
                    display_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    additional_info TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                (),
                query_type='create'
            )
            
            # Create index on request_id and timestamp
            self.display_db.execute_query(
                """
                CREATE INDEX IF NOT EXISTS idx_display_commands_composite 
                ON display_commands(request_id, timestamp)
                """,
                (),
                query_type='create'
            )
            
            # Create display mode state table for more reliable mode tracking
            self.display_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS display_mode_state (
                    display_type TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    mode_value TEXT,
                    timestamp REAL NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                (),
                query_type='create'
            )
            
            logger.info("Display database tables initialized")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise

    async def start(self):
        """Start the response service."""
        if self._running:
            return

        # Ensure initialization is complete
        if not self._initialized:
            logger.info("Service not initialized, initializing now...")
            await self.initialize()

        self._running = True
        self._processor_task = asyncio.create_task(self._process_responses())
        self._acknowledgment_processor = asyncio.create_task(self._process_acknowledgments())
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("DisplayResponseService started")

    async def stop(self):
        """Stop the response service."""
        if not self._running:
            return

        self._running = False
        if self._processor_task:
            await self._processor_task
            self._processor_task = None
        if self._acknowledgment_processor:
            await self._acknowledgment_processor
            self._acknowledgment_processor = None
        if self._watchdog_task:
            await self._watchdog_task
            self._watchdog_task = None
            
        # Clear tracking data
        self._processing_depth.clear()
        self._processed_messages.clear()
        self._message_timestamps.clear()
        self._processing_locks.clear()
            
        logger.info("DisplayResponseService stopped")

    async def _process_responses(self):
        """Process responses from the queue."""
        while self._running:
            try:
                # Get next response from queue
                response, request_id = await self._response_queue.get()
                
                try:
                    await self.handle_response(response, request_id)
                except Exception as e:
                    logger.error(f"Error handling response: {str(e)}")
                    logger.error(traceback.format_exc())
                finally:
                    self._response_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in response processor: {str(e)}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)  # Prevent tight loop on error

    async def queue_response(self, message: MIL_STD_1553B_Message, request_id: str):
        """Queue a response for processing."""
        await self._response_queue.put((message, request_id))
        logger.debug(f"Response queued for request {request_id}")

    async def wait_for_response(self, request_id: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Wait for a response to a specific request."""
        try:
            # Create future for this request
            future = asyncio.Future()
            self.pending_requests[request_id] = future

            try:
                # Wait for response with timeout
                response = await asyncio.wait_for(future, timeout)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to request {request_id}")
                return None
            finally:
                # Clean up
                self.pending_requests.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error waiting for display response: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def handle_response(self, message: MIL_STD_1553B_Message, request_id: str):
        """Handle a response message."""
        try:
            if request_id not in self.pending_requests:
                logger.warning(f"No pending request found for {request_id}")
                return

            # Parse response data
            response_data = self._parse_response(message)
            
            # Complete the future
            future = self.pending_requests[request_id]
            if not future.done():
                future.set_result(response_data)
                logger.debug(f"Response handled for request {request_id}")

        except Exception as e:
            logger.error(f"Error handling display response: {str(e)}")
            logger.error(traceback.format_exc())

    def _parse_response(self, message: MIL_STD_1553B_Message) -> Dict[str, Any]:
        """Parse response message data."""
        try:
            # First byte indicates response type
            response_type = message.data[:8]
            response_data = message.data[8:]

            if response_type == "00000001":  # Display shown
                return {
                    'type': 'display_shown',
                    'success': True
                }
            elif response_type == "00000010":  # Mode set
                return {
                    'type': 'mode_set',
                    'success': True
                }
            elif response_type == "11111111":  # Error
                return {
                    'type': 'error',
                    'error': response_data
                }
            else:
                logger.warning(f"Unknown response type: {response_type}")
                return {
                    'type': None,
                    'data': message.data
                }

        except Exception as e:
            logger.error(f"Error parsing display response: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'type': 'error',
                'error': str(e)
            }

    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._running and self._processor_task and not self._processor_task.done()

    async def _process_acknowledgments(self):
        """Process display command acknowledgments from the queue."""
        while self._running:
            try:
                # Get next acknowledgment from queue
                ack = await self._acknowledgment_queue.get()
                
                try:
                    # Store acknowledgment
                    await self.handle_display_command(ack)
                except Exception as e:
                    logger.error(f"Error handling display command: {str(e)}")
                    logger.error(traceback.format_exc())
                finally:
                    self._acknowledgment_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in acknowledgment processor: {str(e)}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)

    async def _watchdog_loop(self):
        """Watchdog loop to check for timed out messages."""
        try:
            while self._running:
                current_time = time.time()
                timed_out_messages = []
                
                # Check for timed out messages
                for request_id, timestamp in list(self._message_timestamps.items()):
                    if current_time - timestamp > self.MESSAGE_TIMEOUT:
                        timed_out_messages.append(request_id)
                
                # Handle timed out messages
                for request_id in timed_out_messages:
                    logger.warning(f"[WATCHDOG] Message with request_id {request_id} timed out after {self.MESSAGE_TIMEOUT}s")
                    self._message_timestamps.pop(request_id, None)
                    self._processing_depth.pop(request_id, None)
                    self._processing_locks.pop(request_id, None)
                    
                    # Complete any pending futures for this request
                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result({
                                'type': 'timeout',
                                'error': f"Request timed out after {self.MESSAGE_TIMEOUT}s"
                            })
                
                # Sleep for a short time to avoid high CPU usage
                await asyncio.sleep(1.0)
                
        except asyncio.CancelledError:
            logger.info("[WATCHDOG] Watchdog task cancelled")
        except Exception as e:
            logger.error(f"[WATCHDOG] Error in watchdog loop: {str(e)}")
            logger.error(traceback.format_exc())

    async def handle_vil_data(self, message: Dict[str, Any]):
        """
        Handle VIL data from weather radar system to display.
        
        This method processes VIL data messages and formats them for display,
        then routes them to the display system through the  channels.
        
        Args:
            message: Dictionary containing VIL data and metadata
            
        Raises:
            ValueError: If no valid VIL data could be extracted
        """
        try:
            # LOOP PREVENTION: Check if message has already been processed
            if message.get('metadata', {}).get('_processed_by_display_response', False):
                logger.warning("[VIL_FLOW] Detected routing loop - message already processed by display response service")
                return
            
            # Extract request_id if present
            request_id = message.get('request_id')
            if not request_id:
                
                raise ValueError("[DISP_RESP_SERVICE] No request_id found in message")

            # Extract original VIL data with enhanced checking
            vil_data = None
            
            # Try different locations where VIL data might be stored
            for key in ['vil_data', 'data', 'vil']:
                if key in message and message[key] is not None:
                    vil_data = message[key]
                    logger.info(f"[VIL_FLOW] Found VIL data in '{key}' field")
                    break
                    
            # Check for nested data structures
            if vil_data is None and 'metadata' in message and isinstance(message['metadata'], dict):
                metadata = message['metadata']
                for key in ['vil_data', 'data', 'vil', 'weather_data']:
                    if key in metadata and metadata[key] is not None:
                        if key == 'weather_data' and isinstance(metadata[key], dict):
                            # Check inside weather_data
                            for wkey in ['vil_data', 'vil']:
                                if wkey in metadata[key] and metadata[key][wkey] is not None:
                                    vil_data = metadata[key][wkey]
                                    logger.info(f"[VIL_FLOW] Found VIL data in metadata.weather_data.{wkey}")
                                    break
                        else:
                            vil_data = metadata[key]
                            logger.info(f"[VIL_FLOW] Found VIL data in metadata.{key}")
                            break
            
            if vil_data is None:
                logger.warning("[VIL_FLOW] No VIL data found in message")
                # Log the complete message structure without sensitive data
                logger.error(f"[VIL_FLOW] Message keys: {list(message.keys())}")
                if 'metadata' in message and isinstance(message['metadata'], dict):
                    logger.error(f"[VIL_FLOW] Metadata keys: {list(message['metadata'].keys())}")
                raise ValueError("No VIL data found in message")
            
            # Import here to avoid circular imports
            from FMOFP.local_messaging.messageConfigurations.weather_radar_data import WeatherRadarVILData
            
            # Log detailed message for debugging
            logger.info(f"[VIL_FLOW] Routing VIL data to display system")
            logger.info(f"[VIL_FLOW] VIL data type: {type(vil_data)}")
            
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
            
            # Create  VIL data objects
            vil_data_objects = []
            
            # Handle list of data points
            if isinstance(vil_data, list):
                for data_point in vil_data:
                    try:
                        # Skip None values in the list
                        if data_point is None:
                            continue
                            
                        # Handle dictionary format (most common after serialization)
                        if isinstance(data_point, dict):
                            # Extract position from dictionary with fallback to defaults
                            position = extract_position(data_point)
                            
                            # Extract other properties with fallbacks
                            value = data_point.get('value', 20.0)
                            layer_count = data_point.get('layer_count', 1)
                            
                            # Handle string vs float for intensity    
                            intensity = data_point.get('intensity', 0.5)
                            if isinstance(intensity, str):
                                try:
                                    intensity = float(intensity)
                                except (ValueError, TypeError):
                                    intensity = 0.5
                            
                            show_values = bool(data_point.get('show_values', True))
                            
                            # Create WeatherRadarVILData object with extracted values
                            vil_obj = WeatherRadarVILData(
                                position=position,
                                value=float(value),
                                layer_count=int(layer_count),
                                intensity=float(intensity),
                                show_values=show_values
                            )
                            
                            # Add request_id and timestamp
                            vil_obj.request_id = request_id
                            vil_obj.timestamp = message.get('timestamp', time.time())
                            
                            # Add any additional info
                            if hasattr(vil_obj, 'additional_info') and 'additional_info' not in vil_obj.additional_info and 'additional_info' in data_point:
                                vil_obj.additional_info = data_point.get('additional_info', {})
                                
                            vil_data_objects.append(vil_obj)
                            
                        # Handle objects with attributes (may be original WeatherRadarVILData objects)
                        elif hasattr(data_point, 'position') or (hasattr(data_point, 'x') and hasattr(data_point, 'y')):
                            # This might be a WeatherRadarVILData object already
                            if isinstance(data_point, WeatherRadarVILData):
                                # Update request_id and timestamp
                                data_point.request_id = request_id
                                data_point.timestamp = message.get('timestamp', time.time())
                                vil_data_objects.append(data_point)
                            else:
                                # Create a new WeatherRadarVILData from the object
                                position = extract_position(data_point)
                                
                                # Extract other properties
                                value = getattr(data_point, 'value', 20.0)
                                layer_count = getattr(data_point, 'layer_count', 1)
                                intensity = getattr(data_point, 'intensity', 0.5)
                                show_values = bool(getattr(data_point, 'show_values', True))
                                
                                vil_obj = WeatherRadarVILData(
                                    position=position,
                                    value=float(value),
                                    layer_count=int(layer_count),
                                    intensity=float(intensity),
                                    show_values=show_values
                                )
                                
                                # Add request_id and timestamp
                                vil_obj.request_id = request_id
                                vil_obj.timestamp = message.get('timestamp', time.time())
                                
                                # Add any additional info
                                if hasattr(data_point, 'additional_info'):
                                    vil_obj.additional_info = getattr(data_point, 'additional_info', {})
                                    
                                vil_data_objects.append(vil_obj)
                        else:
                            # Try to convert other formats - last resort
                            logger.warning(f"[VIL_FLOW] Unrecognized data point format: {type(data_point)}")
                            
                            # Try to convert to string and extract key information
                            data_str = str(data_point)
                            if 'position' in data_str or 'value' in data_str:
                                logger.info(f"[VIL_FLOW] Attempting to parse data from string representation")
                                
                                # Create a default VIL object and continue
                                vil_obj = WeatherRadarVILData(
                                    position=(0.0, 0.0),
                                    value=20.0,
                                    layer_count=1,
                                    intensity=0.5,
                                    show_values=True
                                )
                                
                                vil_obj.request_id = request_id
                                vil_obj.timestamp = message.get('timestamp', time.time())
                                vil_data_objects.append(vil_obj)
                    except Exception as data_point_error:
                        # Log the error but continue with other data points
                        logger.error(f"[VIL_FLOW] Error processing data point: {data_point_error}")
                        logger.error(traceback.format_exc())
                        # Continue to the next data point
                        continue
            
            # Handle single data point (object or dictionary)
            elif vil_data is not None:
                try:
                    # Handle dictionary format
                    if isinstance(vil_data, dict):
                        # Extract position
                        position = extract_position(vil_data)
                        
                        # Extract other properties with fallbacks
                        value = vil_data.get('value', 20.0)
                        if isinstance(value, str):
                            try:
                                value = float(value)
                            except (ValueError, TypeError):
                                value = 20.0
                                
                        layer_count = vil_data.get('layer_count', 1)
                        if isinstance(layer_count, str):
                            try:
                                layer_count = int(layer_count)
                            except (ValueError, TypeError):
                                layer_count = 1
                                
                        intensity = vil_data.get('intensity', 0.5)
                        if isinstance(intensity, str):
                            try:
                                intensity = float(intensity)
                            except (ValueError, TypeError):
                                intensity = 0.5
                                
                        show_values = bool(vil_data.get('show_values', True))
                        
                        # Create WeatherRadarVILData object
                        vil_obj = WeatherRadarVILData(
                            position=position,
                            value=float(value),
                            layer_count=int(layer_count),
                            intensity=float(intensity),
                            show_values=show_values
                        )
                        
                        vil_obj.request_id = request_id
                        vil_obj.timestamp = message.get('timestamp', time.time())
                        
                        # Add any additional info
                        if hasattr(vil_obj, 'additional_info') and 'additional_info' in vil_data:
                            vil_obj.additional_info = vil_data.get('additional_info', {})
                            
                        vil_data_objects.append(vil_obj)
                        
                    # Handle object format (may be original WeatherRadarVILData object)    
                    elif hasattr(vil_data, 'position') or (hasattr(vil_data, 'x') and hasattr(vil_data, 'y')):
                        # This might be a WeatherRadarVILData object already
                        if isinstance(vil_data, WeatherRadarVILData):
                            # Update request_id and timestamp
                            vil_data.request_id = request_id
                            vil_data.timestamp = message.get('timestamp', time.time())
                            vil_data_objects.append(vil_data)
                        else:
                            # Create a new WeatherRadarVILData from the object
                            position = extract_position(vil_data)
                            
                            # Extract other properties
                            value = getattr(vil_data, 'value', 20.0)
                            layer_count = getattr(vil_data, 'layer_count', 1)
                            intensity = getattr(vil_data, 'intensity', 0.5)
                            show_values = bool(getattr(vil_data, 'show_values', True))
                            
                            vil_obj = WeatherRadarVILData(
                                position=position,
                                value=float(value),
                                layer_count=int(layer_count),
                                intensity=float(intensity),
                                show_values=show_values
                            )
                            
                            vil_obj.request_id = request_id
                            vil_obj.timestamp = message.get('timestamp', time.time())
                            
                            # Add any additional info
                            if hasattr(vil_data, 'additional_info'):
                                vil_obj.additional_info = getattr(vil_data, 'additional_info', {})
                                
                            vil_data_objects.append(vil_obj)
                    else:
                        # Try to parse from string representation - last resort
                        logger.warning(f"[VIL_FLOW] Unrecognized VIL data format: {type(vil_data)}")
                        
                        # Create a default VIL object as fallback
                        vil_obj = WeatherRadarVILData(
                            position=(0.0, 0.0),
                            value=20.0,
                            layer_count=1,
                            intensity=0.5,
                            show_values=True
                        )
                        
                        vil_obj.request_id = request_id
                        vil_obj.timestamp = message.get('timestamp', time.time())
                        vil_data_objects.append(vil_obj)
                except Exception as single_data_error:
                    # Log the error
                    logger.error(f"[VIL_FLOW] Error processing single VIL data: {single_data_error}")
                    logger.error(traceback.format_exc())
                    # Continue with the rest of the method
            
            # Create at least one default data point if none were successfully created
            if not vil_data_objects:
                logger.warning("[VIL_FLOW] No valid VIL data objects could be created - using default")
                
                # Create a default VIL object to ensure display is updated
                vil_obj = WeatherRadarVILData(
                    position=(0.0, 0.0),
                    value=20.0,
                    layer_count=1,
                    intensity=0.5,
                    show_values=True
                )
                
                vil_obj.request_id = request_id
                vil_obj.timestamp = message.get('timestamp', time.time())
                if hasattr(vil_obj, 'additional_info'):
                    vil_obj.additional_info = {'fallback_data': True}
                vil_data_objects.append(vil_obj)
                
                logger.info("[VIL_FLOW] Created default VIL data object as fallback")
            
            # Log the result of conversion
            logger.info(f"[VIL_FLOW] Successfully created {len(vil_data_objects)} VIL data objects")
            
            # Prepare message for display system with enhanced metadata
            vil_message = {
                'data': vil_data_objects[0] if vil_data_objects else None,
                'vil_data': vil_data_objects,  # Include full list for batch processing
                'request_id': request_id,
                'timestamp': message.get('timestamp', time.time()),
                'mode': message.get('mode', 'SURVEILLANCE'),
                'message_type': 'weather_radarVILResponse',  # Ensure correct message type
                'metadata': {
                    'data_type': 'vil',
                    'source': 'weather_radar',
                    'destination': 'display_system',
                    'original_request_id': request_id,
                    'vil_message': True,
                    '_processed_by_display_response': True  # LOOP PREVENTION FLAG
                }
            }
            
            # Preserve any metadata from the original message
            if 'metadata' in message and isinstance(message['metadata'], dict):
                # Merge metadata with our new metadata, keeping our keys for critical fields
                for key, value in message['metadata'].items():
                    if key not in vil_message['metadata']:
                        vil_message['metadata'][key] = value
            
            # Get display message handler
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            
            if not display_handler:
                logger.error("[VIL_FLOW] Could not get display message handler")
                raise ValueError("Could not get display message handler")
            
            # Send VIL data to display system
            await display_handler.handle_vil_data(vil_message)
            
            logger.info(f"[VIL_FLOW] Successfully routed VIL data to display system with request_id: {request_id}")
        except Exception as e:
            logger.error(f"[VIL_FLOW] Error routing VIL data: {e}")
            logger.error(traceback.format_exc())
            raise

    async def handle_display_command(self, command: Union[DisplayCommand, Dict], from_display_handler: bool = False):
        """Handle display command storage and processing.
        
        Args:
            command: Display command to process
            from_display_handler: Whether command came through DisplayMessageHandler
        """
        try:
            # Ensure initialization
            if not self._initialized:
                logger.info("Display service not initialized, initializing now...")
                await self.initialize()
                
            # Verify command format
            if not isinstance(command, (DisplayCommand, dict)):
                raise ValueError(f"Invalid command type: {type(command)}")

            # Get or generate request_id
            request_id = command.get('request_id', '') if isinstance(command, dict) else command.request_id

            # Get or create additional_info for timestamp and transaction tracking
            additional_info = command.get('additional_info', {}) if isinstance(command, dict) else command.additional_info or {}
            if isinstance(command, dict) and 'additional_info' not in command:
                command['additional_info'] = additional_info
            elif not isinstance(command, dict) and not command.additional_info:
                command.additional_info = additional_info
                
            # Get command type for tracking
            command_type = command.get('command_type') if isinstance(command, dict) else command.command_type
                
            # Extract existing transaction ID if present
            transaction_id = None
            metadata = {}
            
            # Check various locations for transaction_id
            if isinstance(command, dict) and 'transaction_id' in command:
                transaction_id = command['transaction_id']
                
            if not transaction_id and isinstance(command, dict) and 'metadata' in command:
                metadata = command['metadata']
                transaction_id = metadata.get('transaction_id')
                
            if not transaction_id and isinstance(additional_info, dict):
                # Direct transaction_id
                if 'transaction_id' in additional_info:
                    transaction_id = additional_info['transaction_id']
                # Check processed transactions list
                elif '_processed_transactions' in additional_info and additional_info['_processed_transactions']:
                    transaction_id = additional_info['_processed_transactions'][0]
                # Check metadata
                elif 'metadata' in additional_info and isinstance(additional_info['metadata'], dict):
                    transaction_id = additional_info['metadata'].get('transaction_id')
                    
            # Generate new transaction ID if none exists
            if not transaction_id:
                transaction_id = str(uuid.uuid4())
                # Add to appropriate location for consistent tracking
                if isinstance(command, dict):
                    command['transaction_id'] = transaction_id
                    if 'metadata' not in command:
                        command['metadata'] = {}
                    command['metadata']['transaction_id'] = transaction_id
                    command['additional_info']['transaction_id'] = transaction_id
                else:
                    if not command.additional_info:
                        command.additional_info = {}
                    command.additional_info['transaction_id'] = transaction_id
                
            # Initialize transaction tracking if needed
            if not hasattr(self, '_processed_transactions'):
                self._processed_transactions = set()
                
            # Initialize mode change transaction tracking if not exists
            if not hasattr(self, '_processed_mode_change_transactions'):
                self._processed_mode_change_transactions = set()
                
            # Check for transaction ID in processed list - if present, BREAK LOOP
            if transaction_id in self._processed_transactions:
                logger.warning(f"[DISPLAY_RESPONSE] BREAKING LOOP - Already processed transaction: {transaction_id}")
                return True

            # Add to processed transactions
            self._processed_transactions.add(transaction_id)
                
            # Check for message ID in processed messages - if present, BREAK LOOP
            message_id = f"{request_id}_{command_type}"
            if message_id in self._processed_messages:
                logger.warning(f"[DISPLAY_RESPONSE] BREAKING LOOP - Already processed message: {message_id}")
                return True
                
            # Add to processed messages
            self._processed_messages.add(message_id)
                
            # Check if already processed by ModeChangeHandler
            if isinstance(metadata, dict) and metadata.get('_processed_by_mode_change_handler'):
                # If from ModeChangeHandler but not a completion message, skip further DisplayResponseService processing
                if not metadata.get('is_completion_message') and command_type != 'mode_change_completion':
                    logger.warning(f"[DISPLAY_RESPONSE] Message {message_id} already processed by ModeChangeHandler, storing only")
                    # Store but don't reprocess
                    # Add tracking flag
                    if isinstance(command, dict):
                        command['additional_info']['_processed_by_display_response'] = True
                    else:
                        command.additional_info['_processed_by_display_response'] = True
                        
            # Check if already processed in additional_info
            if isinstance(additional_info, dict) and additional_info.get('_processed_by_mode_change_handler'):
                if not additional_info.get('is_completion_message') and command_type != 'mode_change_completion':
                    logger.warning(f"[DISPLAY_RESPONSE] Message {message_id} already processed by ModeChangeHandler (via additional_info), storing only")
                    # Store but don't reprocess 
                    # Add tracking flag
                    additional_info['_processed_by_display_response'] = True
                
            # Enhanced deduplication for precipitation data
            if (isinstance(command, dict) and command.get('command_type') == 'precipitation_data') or \
               (not isinstance(command, dict) and command.command_type == 'precipitation_data') or \
               (isinstance(command, dict) and command.get('additional_info') and command.get('additional_info').get('data_type') == 'precipitation') or \
               (not isinstance(command, dict) and command.additional_info and command.additional_info.get('data_type') == 'precipitation'):
                
                # Get additional_info
                additional_info = command.get('additional_info', {}) if isinstance(command, dict) else command.additional_info or {}
                
                # Check for transaction ID
                transaction_id = additional_info.get('transaction_id')
                if not transaction_id:
                    transaction_id = str(uuid.uuid4())
                    if isinstance(command, dict):
                        if 'additional_info' not in command:
                            command['additional_info'] = {}
                        command['additional_info']['transaction_id'] = transaction_id
                    else:
                        if not command.additional_info:
                            command.additional_info = {}
                        command.additional_info['transaction_id'] = transaction_id
                    
                # Check if we've already processed this transaction
                if not hasattr(self, '_processed_precipitation_transactions'):
                    self._processed_precipitation_transactions = set()
                    
                if transaction_id in self._processed_precipitation_transactions:
                    logger.warning(f"[DISPLAY_RESPONSE] Skipping already processed precipitation data with transaction_id {transaction_id}")
                    return
                    
                # Add this transaction to processed set
                self._processed_precipitation_transactions.add(transaction_id)
                
                # Add flag to prevent re-routing
                if isinstance(command, dict):
                    if 'additional_info' not in command:
                        command['additional_info'] = {}
                    command['additional_info']['_processed_by_display_response'] = True
                else:
                    if not command.additional_info:
                        command.additional_info = {}
                    command.additional_info['_processed_by_display_response'] = True
                
                logger.debug(f"[DISPLAY_RESPONSE] Processing precipitation data with transaction_id {transaction_id}")
                
            # Check processing depth to prevent infinite recursion
            current_depth = self._processing_depth.get(request_id, 0)
            if current_depth >= self.MAX_PROCESSING_DEPTH:
                logger.error(f"[DISPLAY_RESPONSE] Maximum processing depth reached for request_id {request_id}: {current_depth}")
                return
                
            # Increment processing depth
            self._processing_depth[request_id] = current_depth + 1
            
            # Record message timestamp for timeout tracking
            if request_id not in self._message_timestamps:
                self._message_timestamps[request_id] = time.time()
                
            # Acquire processing lock for this request_id
            if request_id not in self._processing_locks:
                self._processing_locks[request_id] = asyncio.Lock()
                
            # Process with lock to prevent concurrent processing
            async with self._processing_locks[request_id]:
                # Convert dict to DisplayCommand if needed
                if isinstance(command, dict):
                    # Map radar_display to weather_radar for consistency
                    display_type = command.get('display_type', None)
                    if display_type == 'radar_display':
                        display_type = 'weather_radar'
                        logger.info(f"[DISPLAY_RESPONSE] Mapped radar_display to {display_type}")
                    
                    command = DisplayCommand(
                        timestamp=command.get('timestamp', time.time()),
                        command_type=command.get('command_type', None),
                        display_type=display_type,
                        status=command.get('status', 'acknowledged'),
                        request_id=request_id,
                        additional_info=command.get('additional_info', {})
                    )
                elif command.display_type == 'radar_display':
                    # Also map display_type for DisplayCommand objects
                    command.display_type = 'weather_radar'
                    logger.info(f"[DISPLAY_RESPONSE] Mapped radar_display to weather_radar in DisplayCommand")
                
                # Generate a unique transaction ID for this command if not present
                if not command.additional_info:
                    command.additional_info = {}
                if 'transaction_id' not in command.additional_info:
                    command.additional_info['transaction_id'] = str(uuid.uuid4())
                    
                # Track message processing
                transaction_id = command.additional_info['transaction_id']
                
            # Special handling for mode change messages
            is_mode_change = command_type == 'mode_change' or command_type == 'mode_change_completion'
            
            if is_mode_change:
                # Check if we've already processed this mode change transaction
                if transaction_id in self._processed_mode_change_transactions:
                    logger.warning(f"[DISPLAY_RESPONSE] Skipping already processed mode change transaction: {transaction_id}")
                    return
                # Add to processed transactions set
                self._processed_mode_change_transactions.add(transaction_id)
                
                # Check if this is a mode change completion message
                is_completion_message = (
                    command_type == 'mode_change_completion' or
                    (isinstance(additional_info, dict) and additional_info.get('command_type') == 'mode_change_completion') or
                    (isinstance(additional_info, dict) and additional_info.get('command_name') == 'WEATHER_RADAR_MODE_CHANGE_COMPLETION') or
                    (isinstance(additional_info, dict) and additional_info.get('is_completion_message'))
                )
                
                # Ensure the transaction is tracked within the message itself
                if isinstance(command, dict):
                    if 'additional_info' not in command:
                        command['additional_info'] = {}
                    additional_info = command['additional_info']
                else:
                    if not command.additional_info:
                        command.additional_info = {}
                    additional_info = command.additional_info
                    
                # Add to processed_transactions list if not already there
                if '_processed_transactions' not in additional_info:
                    additional_info['_processed_transactions'] = []
                if transaction_id not in additional_info['_processed_transactions']:
                    additional_info['_processed_transactions'].append(transaction_id)
                
                # Check if this is a completion message
                if is_completion_message:
                    # Check if already processed by display response
                    if command.additional_info and command.additional_info.get('_processed_by_display_response'):
                        logger.warning(f"[DISPLAY_RESPONSE] Breaking loop: Detected already processed completion message {transaction_id}")
                        return True
                    
                    # Mark as processed to prevent re-processing
                    if not command.additional_info:
                        command.additional_info = {}
                    command.additional_info['_processed_by_display_response'] = True
                    
                    # Add skip flag to prevent further routing
                    command.additional_info['_skip_further_routing'] = True
                    
                    # Add transaction to processed list
                    if '_processed_transactions' not in command.additional_info:
                        command.additional_info['_processed_transactions'] = []
                    if transaction_id not in command.additional_info['_processed_transactions']:
                        command.additional_info['_processed_transactions'].append(transaction_id)
                    
                    # Get full radar type (e.g. "weather_radar")
                    radar_type = command.additional_info.get('source_system')
                    if radar_type:
                        logger.info(f"[DISPLAY_RESPONSE] Storing mode change completion from {radar_type}")
                        
                        # Get mode information - check multiple possible locations
                        mode = None
                        mode_value = None
                        
                        # Try to get mode from various locations in the message
                        if command.additional_info:
                            # Check direct mode field
                            if 'mode' in command.additional_info:
                                mode = command.additional_info.get('mode')
                            # Check new_mode field (from completion message)
                            elif 'new_mode' in command.additional_info:
                                mode = command.additional_info.get('new_mode')
                            # Check mode in nested structure
                            elif 'additional_info' in command.additional_info and isinstance(command.additional_info['additional_info'], dict):
                                mode = command.additional_info['additional_info'].get('mode')
                        
                        # If we still don't have a mode, try other fields
                        if not mode and hasattr(command, 'new_mode'):
                            mode = command.new_mode
                        
                        # Get mode value similarly
                        if command.additional_info:
                            if 'mode_value' in command.additional_info:
                                mode_value = command.additional_info.get('mode_value')
                            elif 'additional_info' in command.additional_info and isinstance(command.additional_info['additional_info'], dict):
                                mode_value = command.additional_info['additional_info'].get('mode_value')
                        
                        # Log the mode change completion with high visibility
                        logger.info(f"[DISPLAY_RESPONSE] Processing mode change COMPLETION to {mode} for {command.display_type}")
                        
                        # Mark this command as processed to prevent infinite loops
                        if not command.additional_info:
                            command.additional_info = {}
                        command.additional_info['_processed_by_display_response'] = True
                        command.additional_info['is_completion_message'] = True
                        
                        # Forward to display message handler to update display
                        # This maintains system separation by using messaging channels
                        from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
                        display_handler = get_display_message_handler()
                        
                        if display_handler and mode:
                            # Use radar mode converter utility for type handling, providing the radar type
                            from FMOFP.local_messaging.radar_mode_converter import get_radar_display_mode
                            
                            # Get the radar_type from command information for proper type-specific mapping
                            radar_type = command.additional_info.get('source_system', command.display_type)
                            
                            # Convert mode to RadarDisplayMode enum and mode name with radar_type for context
                            display_mode, mode_name = get_radar_display_mode(mode, radar_type)
                            
                            if display_mode:
                                # Safe handling of enum - get the name and store both
                                mode_display_name = display_mode.name if hasattr(display_mode, 'name') else str(display_mode)
                                logger.info(f"[DISPLAY_RESPONSE] Successfully converted mode {mode} to {mode_display_name} for {radar_type}")
                                
                                # Store only the string name for later use, not the enum itself
                                command.additional_info['display_mode'] = mode_display_name 
                                command.additional_info['mode_name'] = mode_display_name
                                
                                # Use the string name for mode update operations
                                mode = mode_display_name
                                # Create enhanced command data with explicit update flags
                                enhanced_command_data = {
                                    'mode': mode,
                                    'force_update': True,  # Add explicit flag to force update
                                    'update_visual': True,  # Add explicit flag to update visual elements
                                    'is_completion_message': True,  # Mark as completion message
                                    '_processed_by_display_response': True,  # Mark as processed
                                    'final_delivery_to_display': True
                                    }
                                # Send mode change through proper channel
                                logger.info(f"[DISPLAY_RESPONSE] Setting display mode to {display_mode.name} for {command.display_type} (from completion message)")
                                
                                # Send request directly instead of using set_display_mode to avoid the loop
                                await display_handler.send_request(
                                    display_type=command.display_type,
                                    command_type='mode_change',
                                    command_data=enhanced_command_data
                                )
                                
                                logger.debug(f"[DISPLAY_RESPONSE] Sent mode change request through proper channel (from completion message)")
                                
                            else:
                                logger.error(f"[DISPLAY_RESPONSE] Unknown mode: {mode}, cannot map to RadarDisplayMode for {radar_type}")

                # For regular mode changes (not completions), check if we should process them
                elif command.command_type == 'mode_change':
                    # Check if this is a status word acknowledgment (which we should not send to AsyncMessageHandler)
                    is_status_word = (
                        command.additional_info and 
                        (command.additional_info.get('status_word') or 
                        'status_word' in command.additional_info or
                        command.additional_info.get('message_type') == 'status_word' or
                        (isinstance(command.additional_info.get('command_word'), str) and 
                        command.additional_info.get('command_word').startswith('1000')))
                    )
                    
                    if is_status_word:
                        # This is just a status word acknowledgment, not a real mode change
                        logger.debug(f"[DISPLAY_RESPONSE] Processing status word acknowledgment directly")
                        # Store it but don't process it as a mode change or forward to AsyncMessageHandler
                        if not command.additional_info:
                            command.additional_info = {}
                        command.additional_info['_is_status_word'] = True
                        command.additional_info['_skip_async_handler'] = True
                    # Use transaction_id instead of simple flag to prevent infinite loops
                    else:
                        processed_transaction = command.additional_info.get('_processed_transactions', [])
                        if transaction_id in processed_transaction:
                            logger.debug(f"[DISPLAY_RESPONSE] Skipping already processed mode change command with transaction_id {transaction_id}")
                        else:
                            # Add this transaction to processed list
                            if '_processed_transactions' not in command.additional_info:
                                command.additional_info['_processed_transactions'] = []
                            command.additional_info['_processed_transactions'].append(transaction_id)
                        # Get full radar type (e.g. "weather_radar")
                        radar_type = command.additional_info.get('source_system')
                        if radar_type:
                            logger.info(f"[DISPLAY_RESPONSE] Storing mode change from {radar_type}")
                        
                        # Get mode information
                        mode = command.additional_info.get('mode')
                        mode_value = command.additional_info.get('mode_value')
                        
                        # Log the mode change with high visibility
                        logger.info(f"[DISPLAY_RESPONSE] Processing mode change to {mode} for {command.display_type}")
                        
                        # Mark this command as processed to prevent infinite loops
                        if not command.additional_info:
                            command.additional_info = {}
                        command.additional_info['_processed_by_display_response'] = True
                        
                        # Forward to display message handler to update display
                        # This maintains system separation by using  messaging channels
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
                                logger.info(f"[DISPLAY_RESPONSE] Mapped mode {mode} to {display_mode.name}")
                                
                                # Create enhanced command data with explicit update flags
                                enhanced_command_data = {
                                    'mode': display_mode.name,
                                    'force_update': True,  # Add explicit flag to force update
                                    'update_visual': True,  # Add explicit flag to update visual elements
                                    '_processed_by_display_response': True  # Mark as processed
                                }
                                
                                # Send mode change through proper channel
                                logger.debug(f"[DISPLAY_RESPONSE] Setting display mode to {display_mode.name} for {command.display_type}")
                                
                                # Send request directly instead of using set_display_mode to avoid the loop
                                await display_handler.send_request(
                                    display_type=command.display_type,
                                    command_type='mode_change',
                                    command_data=enhanced_command_data
                                )
                                
                                logger.warning(f"[DISPLAY_RESPONSE] Sent mode change request through proper channel")
                            else:
                                logger.error(f"[DISPLAY_RESPONSE] Unknown mode: {mode}, cannot map to RadarDisplayMode")
            

                    
                    # Add weather data structure, but leave empty.
                    if 'weather_data' not in command.additional_info:
                        command.additional_info['weather_data'] = {
                            'mode': command.additional_info.get('mode'),
                            'mode_value': command.additional_info.get('mode_value'),
                            'cells': [],
                            'precipitation': [],
                            'vil_data': []
                        }
                    
                    try:
                        # Store the mode in the global state for access by VIL processing
                        mode = command.additional_info.get('mode')
                        mode_value = command.additional_info.get('mode_value')
                        await self._update_display_mode_state(
                            display_type=command.display_type,
                            mode=mode,
                            mode_value=mode_value
                        )
                        
                        logger.info(f"[DISPLAY_RESPONSE] Updated global mode state to {mode}")
                        
                    except Exception as e:
                        logger.error(f"[DISPLAY_RESPONSE] Error updating mode state: {str(e)}")
                        logger.error(traceback.format_exc())
                        return False
            
                # Store complete visual elements for mode changes

                if not command.additional_info: 
                    command.additional_info = {}
                    command.additional_info['visual_elements'] = (command.additional_info.get('weather_data', {}).get('visual_elements', {}))
                
                    
                ########################################
                ### If we get here, its for displays ###
                ########################################
                
            # Ensure timestamp is never NULL - do this early for all messages
            if isinstance(command, dict):
                if 'timestamp' not in command or command['timestamp'] is None:
                    command['timestamp'] = time.time()
                    logger.warning(f"[DISPLAY_RESPONSE] Missing timestamp in dict, using current time: {command['timestamp']}")
            elif command.timestamp is None:
                command.timestamp = time.time()
                logger.warning(f"[DISPLAY_RESPONSE] Missing timestamp in object, using current time: {command.timestamp}")

            # Log pre-insert data for debugging
            if isinstance(command, dict):
                logger.info(f"[DISPLAY_RESPONSE] Inserting display command with timestamp: {command.get('timestamp')}")
                logger.info(f"[DISPLAY_RESPONSE] Command type: {command.get('command_type')}")
                logger.info(f"[DISPLAY_RESPONSE] Display type: {command.get('display_type')}")
                logger.info(f"[DISPLAY_RESPONSE] Request ID: {command.get('request_id')}")
            else:
                logger.info(f"[DISPLAY_RESPONSE] Inserting display command with timestamp: {command.timestamp}")
                logger.info(f"[DISPLAY_RESPONSE] Command type: {command.command_type}")
                logger.info(f"[DISPLAY_RESPONSE] Display type: {command.display_type}")
                logger.info(f"[DISPLAY_RESPONSE] Request ID: {command.request_id}")
            
            # Check if this is a message that has already been processed and should skip storage
            skip_storage = False
            
            # Check completion messages with _processed_by_display_response flag
            if command.additional_info and isinstance(command.additional_info, dict):
                # Check for explicit processing flags that indicate this message has been through the system already
                already_processed = (
                    command.additional_info.get('_processed_by_display_response') == True and
                    command.additional_info.get('is_completion_message') == True and
                    '_processed_transactions' in command.additional_info
                )
                
                # If message has already been processed and has transaction tracking, skip storage
                if already_processed:
                    transaction_id = command.additional_info.get('transaction_id')
                    logger.warning(f"[DISPLAY_RESPONSE] Detected already processed completion message " 
                                   f"with transaction_id {transaction_id} - SKIPPING STORAGE TO BREAK LOOP")
                    skip_storage = True
            
            
            # Do not store acknowledged display commands
            if command.status == 'acknowledged' or command.additional_info.get('status') == 'acknowledged' or skip_storage == True:
                logger.info(f"[DISPLAY_RESPONSE] Command status is acknowledged, skipping storage")
                skip_storage = True
            
            
            
            if not skip_storage:
            # Database storage removed to prevent message looping
                logger.info(f"[DISPLAY_RESPONSE] Database storage skipped to prevent message looping: {command}")
            
            # Handle mode change commands specially
            if command.command_type == 'mode_change' and command.additional_info:
                # Check if this is a completion message that's already been processed
                is_completion_message = (
                    command.additional_info.get('is_completion_message') or 
                    command.additional_info.get('command_type') == 'mode_change_completion' or
                    (isinstance(command.additional_info.get('message_type'), str) and 'completion' in command.additional_info.get('message_type').lower())
                )
                
                # Check if message has already been processed by the radar response system
                already_processed = (
                    command.additional_info.get('_processed_by_radar_response') or
                    command.additional_info.get('_processed_by_mode_change_handler') or
                    '_processed_transactions' in command.additional_info
                )

                
            
        except Exception as e:
            logger.error(f"[DISPLAY_RESPONSE] Error storing display command: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def send_display_message(self, display_data: Dict):
        """Send message directly to display system without routing.
        
        Args:
            display_data: Dictionary containing the display message data
        """
        try:
            # Get display message handler
            from ...handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            if not display_handler:
                logger.error("[DISPLAY_RESPONSE] Could not get display message handler")
                raise RuntimeError("Could not get display message handler")

            # Send request through display handler
            display_request_id = await display_handler.send_request(
                "radar_display",  # Target display
                display_data.get('command_type', 'data'),  # Command type from data or default to data
                display_data  # Pass the data
            )
            
            # Store command after successful send
            await self.handle_display_command(display_data, from_display_handler=True)
            logger.info(f"[DISPLAY_RESPONSE] Sent message to display system: {display_data}")
            
        except Exception as e:
            logger.error(f"Error sending display message: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_display_commands(self, display_type: Optional[str] = None,
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None) -> List[Tuple]:
        """Get display commands from storage with optional filtering."""
        try:
            # Build query
            query = "SELECT * FROM display_commands WHERE 1=1"
            params = []
            
            if display_type:
                query += " AND display_type = ?"
                params.append(display_type)
                
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
                
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
                
            query += " ORDER BY timestamp DESC"
            
            # Execute query
            results = self.display_db.execute_query(
                query,
                tuple(params),
                query_type='select'
            )
            
            logger.info(f"Retrieved {len(results)} display commands")
            return results
            
        except Exception as e:
            logger.error(f"Error getting display commands: {str(e)}")
            logger.error(traceback.format_exc())
            return []
            
    async def _update_display_mode_state(self, display_type: str, mode: str = None, mode_value: Any = None, is_completion: bool = False):
        """Update the global display mode state.
        
        Args:
            display_type: Type of display (e.g. 'radar_display')
            mode: Mode name (e.g. 'SURVEILLANCE')
            mode_value: Mode value or parameters
            is_completion: Whether this update is from a completion message
        """
        try:
            # Validate required inputs to prevent database errors
            if not display_type:
                logger.error("[DISPLAY_MODE] Missing display_type - cannot update mode state")
                return
                
            # Ensure mode is not NULL to prevent database constraint errors
            if not mode:
                # Get current mode as fallback if available
                current_mode_info = await self.get_current_display_mode(display_type)
                if current_mode_info and current_mode_info.get('mode'):
                    mode = current_mode_info.get('mode')
                    logger.warning(f"[DISPLAY_MODE] Using current mode '{mode}' as fallback since no mode was provided")
                else:
                    # Default to SURVEILLANCE as a last resort
                    mode = "SURVEILLANCE"
                    logger.warning(f"[DISPLAY_MODE] Using default mode '{mode}' since no mode was provided")
            
            # Ensure mode_value is not NULL to prevent database issues
            if mode_value is None:
                mode_value = ""
                logger.warning("[DISPLAY_MODE] Provided mode_value was None, using empty string as fallback")
                
            # Add more detailed logging to track mode changes
            logger.warning(f"[DISPLAY_MODE] Updating display mode state: {display_type} -> {mode} (is_completion={is_completion})")
            logger.warning(f"[DISPLAY_MODE] Previous mode state: {await self.get_current_display_mode(display_type)}")
            
            # For completion messages, always update the mode
            # For non-completion messages, only update if we don't have a current mode
            current_mode = await self.get_current_display_mode(display_type)
            
            # Check if we've already processed a mode change for this mode recently
            # This helps prevent looping by tracking the last processed mode
            if hasattr(self, '_last_processed_mode') and self._last_processed_mode == mode:
                logger.warning(f"[DISPLAY_MODE] Skipping duplicate mode change to {mode} - already processed recently")
                return  # Skip processing to break the loop
            
            # Store the current mode as the last processed mode
            if not hasattr(self, '_last_processed_mode'):
                self._last_processed_mode = None
            self._last_processed_mode = mode
            
            if is_completion or not current_mode:
                # Store the current mode in the database for persistence
                self.display_db.execute_query(
                    """
                    INSERT OR REPLACE INTO display_mode_state (
                        display_type, mode, mode_value, timestamp
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (display_type, mode, str(mode_value), time.time()),
                    query_type='insert'
                )
                
                logger.warning(f"[DISPLAY_MODE] Updated mode state in database: {mode}")
            else:
                logger.warning(f"[DISPLAY_MODE] Skipping mode update for non-completion message (current mode: {current_mode.get('mode')})")
                return  # Skip the rest of the processing for non-completion messages
            
            # Double-check database insertion was successful
            mode_check = await self.get_current_display_mode(display_type)
            if mode_check and mode_check.get('mode') == mode:
                logger.warning(f"[DISPLAY_MODE] Verified mode update was successful: {mode}")
            else:
                logger.error(f"[DISPLAY_MODE] Mode update verification failed. Expected {mode}, got {mode_check}")
            
            # Publish an event for the mode change if routing service is available
            if self.routing_service:
                event_data = {
                    'display_type': display_type,
                    'mode': mode,
                    'mode_value': mode_value,
                    'source_system': 'weather_radar',  # Default to weather_radar for now
                    'timestamp': time.time(),
                    # NOTE (production readiness re-analysis, August 2026): this was
                    # `uuid.uuid4` (the bound function itself) instead of `uuid.uuid4()`
                    # (an actual generated UUID) -- found while investigating a related
                    # bug in MessageRoutingService.route_event(), which is this dict's
                    # only consumer. Stored the function object as 'request_id' instead
                    # of a real identifier, e.g. any downstream str()/comparison/DB-
                    # insert against this field would have gotten
                    # "<built-in method uuid4 of module object at 0x...>" instead of a
                    # UUID string.
                    'request_id': str(uuid.uuid4()),  # Generate a request ID for tracking
                    'force_update': True,  # Force update regardless of current state
                    'update_visual': True,   # Explicitly request visual update
                    '_processed_by_display_response': True  # Mark as processed to prevent loops
                }
                
                # Log the event publication with enhanced visibility
                logger.warning(f"[DISPLAY_MODE] Publishing mode change event: {mode}")
                
                # Route the event through the message routing service
                await self.routing_service.route_event(event_data)
                logger.warning(f"[DISPLAY_MODE] Published mode change event successfully")
                
                # For completion messages, we don't need to send another mode change request
                # This is the key fix to prevent the looping issue
                if is_completion:
                    logger.warning(f"[DISPLAY_MODE] Skipping additional mode change request for completion message")
                    return

            logger.warning(f"[DISPLAY_MODE] Updated display mode state: {display_type} -> {mode}")
        except Exception as e:
            logger.error(f"Error updating display mode state: {str(e)}")
            logger.error(traceback.format_exc())
            
    async def get_current_display_mode(self, display_type: str) -> Optional[Dict[str, Any]]:
        """Get the current mode for a display type.
        
        Args:
            display_type: Type of display (e.g. 'radar_display')
            
        Returns:
            Dictionary with mode information or None if not found
        """
        try:
            result = self.display_db.execute_query(
                """
                SELECT mode, mode_value, timestamp 
                FROM display_mode_state 
                WHERE display_type = ?
                """,
                (display_type,),
                query_type='select'
            )
            
            if result and len(result) > 0:
                return {
                    'mode': result[0][0],
                    'mode_value': result[0][1],
                    'timestamp': result[0][2]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting current display mode: {str(e)}")
            logger.error(traceback.format_exc())
            return None


# Global instance
_display_response_service = None

def get_display_response_service():
    """Get the global DisplayResponseService instance."""
    global _display_response_service
    if _display_response_service is None:
        _display_response_service = DisplayResponseService()
    return _display_response_service
