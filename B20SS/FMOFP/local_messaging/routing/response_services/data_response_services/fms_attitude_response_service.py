"""
FMS Attitude response service for handling attitude data

Provides:
1. Async queue processing of attitude data
2. Integration with data handler for storage
3. Error handling and logging
4. Direct display notification without using MessageRoutingService
"""

import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.fms_attitude_data import create_fms_attitude_data_message
from FMOFP.Utils.common.message_format_adapter import get_message_format_adapter
# Import message loop prevention middleware
from FMOFP.Utils.message_loop_prevention.middleware import get_loop_prevention_middleware

logger = get_logger()

class FMSAttitudeDataHandler:
    """Handles FMS attitude data storage and retrieval"""
    
    def __init__(self, fms_db):
        """Initialize with FMS database connection"""
        self.fms_db = fms_db
        
        # Ensure table exists
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            # Create attitude data table
            self.fms_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS attitude_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    roll REAL NOT NULL,
                    pitch REAL NOT NULL,
                    yaw REAL NOT NULL,
                    roll_rate REAL NOT NULL,
                    pitch_rate REAL NOT NULL,
                    yaw_rate REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
                """,
                query_type='execute'
            )
            logger.info("FMS attitude data table created/verified")
        except Exception as e:
            logger.error(f"Error creating attitude data tables: {e}")
            logger.error(traceback.format_exc())
    
    def store_attitude_data(self, attitude_data):
        """Store attitude data in the database"""
        try:
            # Extract values from attitude data
            request_id = getattr(attitude_data, 'request_id', str(time.time()))
            
            # Extract attitude values
            if hasattr(attitude_data, 'data') and isinstance(attitude_data.data, dict):
                # Format from message object
                roll = attitude_data.data.get('roll', 0.0)
                pitch = attitude_data.data.get('pitch', 0.0)
                yaw = attitude_data.data.get('yaw', 0.0)
                roll_rate = attitude_data.data.get('roll_rate', 0.0)
                pitch_rate = attitude_data.data.get('pitch_rate', 0.0)
                yaw_rate = attitude_data.data.get('yaw_rate', 0.0)
            else:
                # Direct attributes
                roll = getattr(attitude_data, 'roll', 0.0)
                pitch = getattr(attitude_data, 'pitch', 0.0)
                yaw = getattr(attitude_data, 'yaw', 0.0)
                roll_rate = getattr(attitude_data, 'roll_rate', 0.0)
                pitch_rate = getattr(attitude_data, 'pitch_rate', 0.0)
                yaw_rate = getattr(attitude_data, 'yaw_rate', 0.0)
            
            # Get timestamp
            timestamp = getattr(attitude_data, 'timestamp', time.time())
            
            # Insert into database
            self.fms_db.execute_query(
                """
                INSERT INTO attitude_data 
                (request_id, roll, pitch, yaw, roll_rate, pitch_rate, yaw_rate, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, roll, pitch, yaw, roll_rate, pitch_rate, yaw_rate, timestamp),
                query_type='execute'
            )
            
            logger.info(f"Stored FMS attitude data: request_id={request_id}, roll={roll}, pitch={pitch}, yaw={yaw}")
            return True
        except Exception as e:
            logger.error(f"Error storing attitude data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def get_latest_attitude_data(self):
        """Get the latest attitude data"""
        try:
            result = self.fms_db.execute_query(
                """
                SELECT * FROM attitude_data
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                query_type='select'
            )
            
            if result and len(result) > 0:
                # Get column names
                with self.fms_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(attitude_data)")
                    columns = [col[1] for col in cursor.fetchall()]
                
                # Convert row to dictionary
                row = result[0]
                data_dict = dict(zip(columns, row))
                
                # Create attitude data message
                attitude_data = create_fms_attitude_data_message(
                    roll=data_dict['roll'],
                    pitch=data_dict['pitch'],
                    yaw=data_dict['yaw'],
                    roll_rate=data_dict['roll_rate'],
                    pitch_rate=data_dict['pitch_rate'],
                    yaw_rate=data_dict['yaw_rate'],
                    timestamp=data_dict['timestamp']
                )
                
                # Add request ID
                attitude_data['request_id'] = data_dict['request_id']
                
                return attitude_data
            
            return None
        except Exception as e:
            logger.error(f"Error getting latest attitude data: {e}")
            logger.error(traceback.format_exc())
            return None

class FMSAttitudeResponseService:
    """Handles FMS attitude data processing and storage"""
    _instance = None
    _initialized = False

    def __new__(cls, fms_db=None):
        if cls._instance is None:
            cls._instance = super(FMSAttitudeResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, fms_db=None):
        """Initialize with FMS database connection"""
        if not self._initialized and fms_db is not None:
            self.data_handler = FMSAttitudeDataHandler(fms_db)
            self._attitude_queue = None
            self._event_loop = None
            self._processing = False
            self._task = None
            
            # Get routing service for message handling
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.routing_service = get_message_routing_service()
            
            # Initialize loop prevention middleware
            try:
                self.loop_prevention = get_loop_prevention_middleware()
                logger.info("FMS Attitude Response Service integrated with loop prevention middleware")
            except Exception as e:
                logger.error(f"Failed to initialize loop prevention middleware: {e}")
                self.loop_prevention = None
            
            self._initialized = True
            logger.info("FMSAttitudeResponseService initialized")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("FMSAttitudeResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("FMSAttitudeResponseService fully initialized")
            
        except Exception as e:
            logger.error(f"Error during FMSAttitudeResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize FMSAttitudeResponseService") from e

    async def start(self, event_loop=None) -> bool:
        """
        Start the FMS attitude response service
        
        Args:
            event_loop: Optional event loop to use for async operations
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                logger.info("FMS attitude service not initialized, initializing now...")
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
            self._attitude_queue = asyncio.Queue()  # Create queue with current event loop
            self._processing = True
            
            # Create and start the queue processing task
            logger.info("Creating queue processing task")
            self._task = self._event_loop.create_task(self._process_attitude_queue())
            self._task.add_done_callback(self._handle_task_done)
            
            logger.info("FMS attitude response service started")
            return True
        except Exception as e:
            logger.error(f"Error starting FMS attitude response service: {e}")
            traceback.print_exc()
            raise

    def _handle_task_done(self, task):
        """Handle completion of the processing task"""
        try:
            # Check if task failed with an exception
            if task.exception():
                logger.error(f"FMS attitude processing task failed: {task.exception()}")
                # Restart the task if processing should continue
                if self._processing:
                    logger.info("Restarting FMS attitude processing task")
                    self._task = self._event_loop.create_task(self._process_attitude_queue())
                    self._task.add_done_callback(self._handle_task_done)
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            traceback.print_exc()

    async def stop(self):
        """Stop the FMS attitude response service"""
        try:
            logger.info("Stopping FMS attitude response service")
            self._processing = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("FMS attitude response service stopped")
        except Exception as e:
            logger.error(f"Error stopping FMS attitude response service: {e}")
            traceback.print_exc()

    async def _process_attitude_queue(self):
        """Process attitude data queue with robust error handling"""
        logger.info("Starting FMS attitude queue processor")
        try:
            while self._processing:
                try:
                    logger.info("Waiting for FMS attitude data...")
                    attitude_data = await self._attitude_queue.get()
                    logger.info(f"Processing FMS attitude data: {attitude_data}")
                    try:
                        # Store data synchronously
                        success = self.data_handler.store_attitude_data(attitude_data)
                        if success:
                            logger.info(f"FMS attitude data processed and stored: {getattr(attitude_data, 'request_id', 'unknown')}")
                            # Only mark task done if storage was successful
                            self._attitude_queue.task_done()
                            
                            # Route to display system after storage
                            await self._route_to_display(attitude_data)
                        else:
                            logger.error(f"Failed to store FMS attitude data")
                            # Log failure details
                            logger.error(f"Failed data: {attitude_data}")
                            # Put the data back in queue for retry
                            await self._attitude_queue.put(attitude_data)
                    except Exception as store_error:
                        logger.error(f"Error storing FMS attitude data: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('fms_attitude_failures.log', 'a') as f:
                            f.write(f"Failed FMS Attitude Data: {attitude_data}\nError: {store_error}\n")
                        # Put the data back in queue for retry
                        await self._attitude_queue.put(attitude_data)
                except asyncio.CancelledError:
                    logger.info("FMS attitude queue processor cancelled")
                    break
                except Exception as e:
                    logger.error(f"FMS attitude queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Brief pause before retrying
        except Exception as e:
            logger.error(f"Fatal error in FMS attitude queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _route_to_display(self, attitude_data):
        """Route attitude data to display system"""
        try:
            # Get display message handler directly
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            
            if display_handler:
                # Create message for display system
                display_message = {
                    'data': attitude_data,
                    'request_id': getattr(attitude_data, 'request_id', str(time.time())),
                    'timestamp': getattr(attitude_data, 'timestamp', time.time()),
                    'message_type': 'fms_attitudeData',
                    'metadata': {
                        'data_type': 'attitude_data',
                        'source': 'flightManagementSystem',
                        'destination': 'display_system',
                        'command_type': 'attitude_data',
                        '_direct_from_fms_service': True
                    }
                }
                
                # Send via display handler's generic handler
                await display_handler.handle_generic_message(display_message)
                logger.info("Sent FMS attitude data to display system")
            else:
                logger.error("Could not get display message handler")
        except Exception as e:
            logger.error(f"Error routing to display: {e}")
            logger.error(traceback.format_exc())

    async def handle_attitude_data(self, message: Dict[str, Any]):
        """
        Handle FMS attitude data
        
        Args:
            message: Dictionary containing attitude data
        """
        try:
            # Use loop prevention middleware if available
            if self.loop_prevention:
                should_process, enhanced_message = self.loop_prevention.process_message(message, "fms_attitude_service")
                if not should_process:
                    logger.warning("Breaking loop - FMS attitude message already processed by middleware")
                    return
                # Use the enhanced message with loop prevention metadata
                message = enhanced_message
            else:
                # Fallback to manual loop prevention if middleware not available
                if message.get('metadata', {}).get('_processed_by_fms_attitude_service', False):
                    logger.warning("Detected loop - message already processed by FMS attitude service")
                    return

                # Add legacy loop prevention flag
                if 'metadata' not in message:
                    message['metadata'] = {}
                message['metadata']['_processed_by_fms_attitude_service'] = True
            
            # Log message
            logger.info("Handling FMS attitude data message")
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
                logger.warning("FMS attitude data missing request_id")
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
            if not self._attitude_queue:
                logger.info("Initializing queue for FMS attitude data")
                # Get current event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                # Start service with current loop
                await self.start(event_loop=loop)
            
            # Add to queue for processing
            await self._attitude_queue.put(data)
            
            # Send acknowledgment
            await self._send_acknowledgment(request_id, True, "FMS attitude data received")
            
        except Exception as e:
            logger.error(f"Error handling FMS attitude data: {e}")
            traceback.print_exc()
            if 'request_id' in locals():
                await self._send_acknowledgment(request_id, False, f"Error: {str(e)}")

    async def _send_acknowledgment(self, request_id: str, success: bool, message: str):
        """Send acknowledgment message"""
        try:
            ack_message = {
                'request_id': request_id,
                'command_type': 'attitude_data',
                'system_type': 'flightManagementSystem',
                'status': 'acknowledged' if success else 'failed',
                'timestamp': time.time(),
                'additional_info': {
                    'data_type': 'attitude_data',
                    'message_type': 'fms_attitudeDataResponse',
                    'status_message': message
                }
            }
            
            await self.routing_service.route_status_word(ack_message)
            logger.info(f"Sent acknowledgment for {request_id}: {ack_message['status']}")
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment: {e}")

# Singleton instance
_fms_attitude_response_service = None

def get_fms_attitude_response_service():
    """Get singleton instance of FMS Attitude Response Service"""
    global _fms_attitude_response_service
    if _fms_attitude_response_service is None:
        # Get FMS database from DBM
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        fms_db = db_manager.get_system_db('flightManagementSystem')
        
        # Create instance with FMS database
        _fms_attitude_response_service = FMSAttitudeResponseService(fms_db)
    return _fms_attitude_response_service
