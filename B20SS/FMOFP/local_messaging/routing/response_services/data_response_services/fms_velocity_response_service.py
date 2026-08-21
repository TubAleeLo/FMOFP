"""
FMS Velocity response service for handling velocity data

Provides:
1. Async queue processing of velocity data
2. Integration with data handler for storage
3. Error handling and logging
4. Direct display notification without using MessageRoutingService
"""

import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.fms_velocity_data import create_fms_velocity_data_message
from FMOFP.Utils.common.message_format_adapter import get_message_format_adapter
# Import message loop prevention middleware
from FMOFP.Utils.message_loop_prevention.middleware import get_loop_prevention_middleware

logger = get_logger()

class FMSVelocityDataHandler:
    """Handles FMS velocity data storage and retrieval"""
    
    def __init__(self, fms_db):
        """Initialize with FMS database connection"""
        self.fms_db = fms_db
        
        # Ensure table exists
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            # Create velocity data table
            self.fms_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS velocity_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    airspeed REAL NOT NULL,
                    groundspeed REAL NOT NULL,
                    vertical_speed REAL NOT NULL,
                    mach REAL NOT NULL,
                    angle_of_attack REAL NOT NULL,
                    g_force REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
                """,
                query_type='execute'
            )
            logger.info("FMS velocity data table created/verified")
        except Exception as e:
            logger.error(f"Error creating velocity data tables: {e}")
            logger.error(traceback.format_exc())
    
    def store_velocity_data(self, velocity_data):
        """Store velocity data in the database"""
        try:
            # Extract values from velocity data
            request_id = getattr(velocity_data, 'request_id', str(time.time()))
            
            # Extract velocity values
            if hasattr(velocity_data, 'data') and isinstance(velocity_data.data, dict):
                # Format from message object
                airspeed = velocity_data.data.get('airspeed', 0.0)
                groundspeed = velocity_data.data.get('groundspeed', 0.0)
                vertical_speed = velocity_data.data.get('vertical_speed', 0.0)
                mach = velocity_data.data.get('mach', 0.0)
                angle_of_attack = velocity_data.data.get('angle_of_attack', 0.0)
                g_force = velocity_data.data.get('g_force', 1.0)
            else:
                # Direct attributes
                airspeed = getattr(velocity_data, 'airspeed', 0.0)
                groundspeed = getattr(velocity_data, 'groundspeed', 0.0)
                vertical_speed = getattr(velocity_data, 'vertical_speed', 0.0)
                mach = getattr(velocity_data, 'mach', 0.0)
                angle_of_attack = getattr(velocity_data, 'angle_of_attack', 0.0)
                g_force = getattr(velocity_data, 'g_force', 1.0)
            
            # Get timestamp
            timestamp = getattr(velocity_data, 'timestamp', time.time())
            
            # Insert into database
            self.fms_db.execute_query(
                """
                INSERT INTO velocity_data 
                (request_id, airspeed, groundspeed, vertical_speed, mach, angle_of_attack, g_force, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, airspeed, groundspeed, vertical_speed, mach, angle_of_attack, g_force, timestamp),
                query_type='execute'
            )
            
            logger.info(f"Stored FMS velocity data: request_id={request_id}, airspeed={airspeed}, groundspeed={groundspeed}")
            return True
        except Exception as e:
            logger.error(f"Error storing velocity data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def get_latest_velocity_data(self):
        """Get the latest velocity data"""
        try:
            result = self.fms_db.execute_query(
                """
                SELECT * FROM velocity_data
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                query_type='select'
            )
            
            if result and len(result) > 0:
                # Get column names
                with self.fms_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(velocity_data)")
                    columns = [col[1] for col in cursor.fetchall()]
                
                # Convert row to dictionary
                row = result[0]
                data_dict = dict(zip(columns, row))
                
                # Create velocity data message
                velocity_data = create_fms_velocity_data_message(
                    airspeed=data_dict['airspeed'],
                    groundspeed=data_dict['groundspeed'],
                    vertical_speed=data_dict['vertical_speed'],
                    mach=data_dict['mach'],
                    angle_of_attack=data_dict['angle_of_attack'],
                    g_force=data_dict['g_force'],
                    timestamp=data_dict['timestamp']
                )
                
                # Add request ID
                velocity_data['request_id'] = data_dict['request_id']
                
                return velocity_data
            
            return None
        except Exception as e:
            logger.error(f"Error getting latest velocity data: {e}")
            logger.error(traceback.format_exc())
            return None

class FMSVelocityResponseService:
    """Handles FMS velocity data processing and storage"""
    _instance = None
    _initialized = False

    def __new__(cls, fms_db=None):
        if cls._instance is None:
            cls._instance = super(FMSVelocityResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, fms_db=None):
        """Initialize with FMS database connection"""
        if not self._initialized and fms_db is not None:
            self.data_handler = FMSVelocityDataHandler(fms_db)
            self._velocity_queue = None
            self._event_loop = None
            self._processing = False
            self._task = None
            
            # Get routing service for message handling
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.routing_service = get_message_routing_service()
            
            # Initialize loop prevention middleware
            try:
                self.loop_prevention = get_loop_prevention_middleware()
                logger.info("FMS Velocity Response Service integrated with loop prevention middleware")
            except Exception as e:
                logger.error(f"Failed to initialize loop prevention middleware: {e}")
                self.loop_prevention = None
            
            self._initialized = True
            logger.info("FMSVelocityResponseService initialized")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("FMSVelocityResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("FMSVelocityResponseService fully initialized")
            
        except Exception as e:
            logger.error(f"Error during FMSVelocityResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize FMSVelocityResponseService") from e

    async def start(self, event_loop=None) -> bool:
        """
        Start the FMS velocity response service
        
        Args:
            event_loop: Optional event loop to use for async operations
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                logger.info("FMS velocity service not initialized, initializing now...")
                await self.initialize()

            # Get current event loop if none provided
            if event_loop is None:
                try:
                    event_loop = asyncio.get_running_loop()
                    logger.info("Using existing event loop")
                except RuntimeError:
                    event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(event_loop)
                    logger.info("Created new event loop")

            self._event_loop = event_loop
            self._velocity_queue = asyncio.Queue()  # Create queue with current event loop
            self._processing = True
            
            # Create and start the queue processing task
            logger.info("Creating queue processing task")
            self._task = self._event_loop.create_task(self._process_velocity_queue())
            self._task.add_done_callback(self._handle_task_done)
            
            logger.info("FMS velocity response service started")
            return True
        except Exception as e:
            logger.error(f"Error starting FMS velocity response service: {e}")
            traceback.print_exc()
            raise

    def _handle_task_done(self, task):
        """Handle completion of the processing task"""
        try:
            # Check if task failed with an exception
            if task.exception():
                logger.error(f"FMS velocity processing task failed: {task.exception()}")
                # Restart the task if processing should continue
                if self._processing:
                    logger.info("Restarting FMS velocity processing task")
                    self._task = self._event_loop.create_task(self._process_velocity_queue())
                    self._task.add_done_callback(self._handle_task_done)
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            traceback.print_exc()

    async def stop(self):
        """Stop the FMS velocity response service"""
        try:
            logger.info("Stopping FMS velocity response service")
            self._processing = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("FMS velocity response service stopped")
        except Exception as e:
            logger.error(f"Error stopping FMS velocity response service: {e}")
            traceback.print_exc()

    async def _process_velocity_queue(self):
        """Process velocity data queue with robust error handling"""
        logger.info("Starting FMS velocity queue processor")
        try:
            while self._processing:
                try:
                    logger.info("Waiting for FMS velocity data...")
                    velocity_data = await self._velocity_queue.get()
                    logger.info(f"Processing FMS velocity data: {velocity_data}")
                    try:
                        # Store data synchronously
                        success = self.data_handler.store_velocity_data(velocity_data)
                        if success:
                            logger.info(f"FMS velocity data processed and stored: {getattr(velocity_data, 'request_id', 'unknown')}")
                            # Only mark task done if storage was successful
                            self._velocity_queue.task_done()
                            
                            # Route to display system after storage
                            await self._route_to_display(velocity_data)
                        else:
                            logger.error(f"Failed to store FMS velocity data")
                            # Log failure details
                            logger.error(f"Failed data: {velocity_data}")
                            # Put the data back in queue for retry
                            await self._velocity_queue.put(velocity_data)
                    except Exception as store_error:
                        logger.error(f"Error storing FMS velocity data: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('fms_velocity_failures.log', 'a') as f:
                            f.write(f"Failed FMS Velocity Data: {velocity_data}\nError: {store_error}\n")
                        # Put the data back in queue for retry
                        await self._velocity_queue.put(velocity_data)
                except asyncio.CancelledError:
                    logger.info("FMS velocity queue processor cancelled")
                    break
                except Exception as e:
                    logger.error(f"FMS velocity queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Brief pause before retrying
        except Exception as e:
            logger.error(f"Fatal error in FMS velocity queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _route_to_display(self, velocity_data):
        """Route velocity data to display system"""
        try:
            # Get display message handler directly
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            
            if display_handler:
                # Create message for display system
                display_message = {
                    'data': velocity_data,
                    'request_id': getattr(velocity_data, 'request_id', str(time.time())),
                    'timestamp': getattr(velocity_data, 'timestamp', time.time()),
                    'message_type': 'fms_velocityData',
                    'metadata': {
                        'data_type': 'velocity_data',
                        'source': 'flightManagementSystem',
                        'destination': 'display_system',
                        'command_type': 'velocity_data',
                        '_direct_from_fms_service': True
                    }
                }
                
                # Send via display handler's generic handler
                await display_handler.handle_generic_message(display_message)
                logger.info("Sent FMS velocity data to display system")
            else:
                logger.error("Could not get display message handler")
        except Exception as e:
            logger.error(f"Error routing to display: {e}")
            logger.error(traceback.format_exc())

    async def handle_velocity_data(self, message: Dict[str, Any]):
        """
        Handle FMS velocity data
        
        Args:
            message: Dictionary containing velocity data
        """
        try:
            # Use loop prevention middleware if available
            if self.loop_prevention:
                should_process, enhanced_message = self.loop_prevention.process_message(message, "fms_velocity_service")
                if not should_process:
                    logger.warning("Breaking loop - FMS velocity message already processed by middleware")
                    return
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
            else:
                # Fallback to manual loop prevention if middleware not available
                if message.get('metadata', {}).get('_processed_by_fms_velocity_service', False):
                    logger.warning("Detected loop - message already processed by FMS velocity service")
                    return

                # Add legacy loop prevention flag
                if 'metadata' not in message:
                    message['metadata'] = {}
                message['metadata']['_processed_by_fms_velocity_service'] = True
            
            # Log message
            logger.info("Handling FMS velocity data message")
            logger.info(f"Message keys: {message.keys() if isinstance(message, dict) else 'N/A'}")
            
            # Extract request ID from message
            request_id = message.get('request_id')
            if not request_id and isinstance(message, dict):
                # Try to find request_id in other common fields
                for field in ['requestId', 'request_uuid', 'id', 'uuid']:
                    if field in message:
                        request_id = message[field]
                        break
                        
            logger.info(f"Extracted request_id: {request_id}")
            if not request_id:
                logger.warning("FMS velocity data missing request_id")
                request_id = str(time.time())  # Generate one if missing
            
            # Use message format adapter to help extract fields
            message_adapter = get_message_format_adapter()
            normalized_message = message_adapter.normalize_message(message)
            logger.info(f"Normalized message type: {normalized_message['message_type']}")
            
            # Extract data from message
            data = message.get('data')
            if not data:
                logger.warning("No data field found in message")
                return
                
            # Ensure we have a queue
            if not self._velocity_queue:
                logger.info("Initializing queue for FMS velocity data")
                # Get current event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                # Start service with current loop
                await self.start(event_loop=loop)
            
            # Add to queue for processing
            await self._velocity_queue.put(data)
            
            # Send acknowledgment
            await self._send_acknowledgment(request_id, True, "FMS velocity data received")
            
        except Exception as e:
            logger.error(f"Error handling FMS velocity data: {e}")
            traceback.print_exc()
            if 'request_id' in locals():
                await self._send_acknowledgment(request_id, False, f"Error: {str(e)}")

    async def _send_acknowledgment(self, request_id: str, success: bool, message: str):
        """Send acknowledgment message"""
        try:
            ack_message = {
                'request_id': request_id,
                'command_type': 'velocity_data',
                'system_type': 'flightManagementSystem',
                'status': 'acknowledged' if success else 'failed',
                'timestamp': time.time(),
                'additional_info': {
                    'data_type': 'velocity_data',
                    'message_type': 'fms_velocityDataResponse',
                    'status_message': message
                }
            }
            
            await self.routing_service.route_status_word(ack_message)
            logger.info(f"Sent acknowledgment for {request_id}: {ack_message['status']}")
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment: {e}")

# Singleton instance
_fms_velocity_response_service = None

def get_fms_velocity_response_service():
    """Get singleton instance of FMS Velocity Response Service"""
    global _fms_velocity_response_service
    if _fms_velocity_response_service is None:
        # Get FMS database from DBM
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        fms_db = db_manager.get_system_db('flightManagementSystem')
        
        # Create instance with FMS database
        _fms_velocity_response_service = FMSVelocityResponseService(fms_db)
    return _fms_velocity_response_service
