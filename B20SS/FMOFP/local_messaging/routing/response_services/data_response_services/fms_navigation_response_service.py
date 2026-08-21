"""
FMS Navigation response service for handling navigation data

Provides:
1. Async queue processing of navigation data
2. Integration with data handler for storage
3. Error handling and logging
4. Direct display notification without using MessageRoutingService
"""

import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.fms_navigation_data import create_fms_navigation_data_message
from FMOFP.Utils.common.message_format_adapter import get_message_format_adapter

logger = get_logger()

class FMSNavigationDataHandler:
    """Handles FMS navigation data storage and retrieval"""
    
    def __init__(self, fms_db):
        """Initialize with FMS database connection"""
        self.fms_db = fms_db
        
        # Ensure table exists
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            # Create navigation data table
            self.fms_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS navigation_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL NOT NULL,
                    heading REAL NOT NULL,
                    track REAL NOT NULL,
                    navigation_mode TEXT NOT NULL,
                    waypoint TEXT,
                    timestamp REAL NOT NULL
                )
                """,
                query_type='execute'
            )
            logger.info("FMS navigation data table created/verified")
        except Exception as e:
            logger.error(f"Error creating navigation data tables: {e}")
            logger.error(traceback.format_exc())
    
    def store_navigation_data(self, navigation_data):
        """Store navigation data in the database"""
        try:
            # Extract values from navigation data
            request_id = getattr(navigation_data, 'request_id', str(time.time()))
            
            # Extract navigation values
            if hasattr(navigation_data, 'data') and isinstance(navigation_data.data, dict):
                # Format from message object
                latitude = navigation_data.data.get('latitude', 0.0)
                longitude = navigation_data.data.get('longitude', 0.0)
                altitude = navigation_data.data.get('altitude', 0.0)
                heading = navigation_data.data.get('heading', 0.0)
                track = navigation_data.data.get('track', 0.0)
                navigation_mode = navigation_data.data.get('navigation_mode', 'MANUAL')
                waypoint = navigation_data.data.get('waypoint', '')
            else:
                # Direct attributes
                latitude = getattr(navigation_data, 'latitude', 0.0)
                longitude = getattr(navigation_data, 'longitude', 0.0)
                altitude = getattr(navigation_data, 'altitude', 0.0)
                heading = getattr(navigation_data, 'heading', 0.0)
                track = getattr(navigation_data, 'track', 0.0)
                navigation_mode = getattr(navigation_data, 'navigation_mode', 'MANUAL')
                waypoint = getattr(navigation_data, 'waypoint', '')
            
            # Get timestamp
            timestamp = getattr(navigation_data, 'timestamp', time.time())
            
            # Insert into database
            self.fms_db.execute_query(
                """
                INSERT INTO navigation_data 
                (request_id, latitude, longitude, altitude, heading, track, navigation_mode, waypoint, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, latitude, longitude, altitude, heading, track, navigation_mode, waypoint, timestamp),
                query_type='execute'
            )
            
            logger.info(f"Stored FMS navigation data: request_id={request_id}, lat={latitude}, lon={longitude}, alt={altitude}")
            return True
        except Exception as e:
            logger.error(f"Error storing navigation data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def get_latest_navigation_data(self):
        """Get the latest navigation data"""
        try:
            result = self.fms_db.execute_query(
                """
                SELECT * FROM navigation_data
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                query_type='select'
            )
            
            if result and len(result) > 0:
                # Get column names
                with self.fms_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(navigation_data)")
                    columns = [col[1] for col in cursor.fetchall()]
                
                # Convert row to dictionary
                row = result[0]
                data_dict = dict(zip(columns, row))
                
                # Create navigation data message
                navigation_data = create_fms_navigation_data_message(
                    latitude=data_dict['latitude'],
                    longitude=data_dict['longitude'],
                    altitude=data_dict['altitude'],
                    heading=data_dict['heading'],
                    track=data_dict['track'],
                    navigation_mode=data_dict['navigation_mode'],
                    waypoint=data_dict['waypoint'],
                    timestamp=data_dict['timestamp']
                )
                
                # Add request ID
                navigation_data['request_id'] = data_dict['request_id']
                
                return navigation_data
            
            return None
        except Exception as e:
            logger.error(f"Error getting latest navigation data: {e}")
            logger.error(traceback.format_exc())
            return None

class FMSNavigationResponseService:
    """Handles FMS navigation data processing and storage"""
    _instance = None
    _initialized = False

    def __new__(cls, fms_db=None):
        if cls._instance is None:
            cls._instance = super(FMSNavigationResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, fms_db=None):
        """Initialize with FMS database connection"""
        if not self._initialized and fms_db is not None:
            self.data_handler = FMSNavigationDataHandler(fms_db)
            self._navigation_queue = None
            self._event_loop = None
            self._processing = False
            self._task = None
            
            # Get routing service for message handling
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.routing_service = get_message_routing_service()
            
            self._initialized = True
            logger.info("FMSNavigationResponseService initialized")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("FMSNavigationResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("FMSNavigationResponseService fully initialized")
            
        except Exception as e:
            logger.error(f"Error during FMSNavigationResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize FMSNavigationResponseService") from e

    async def start(self, event_loop=None) -> bool:
        """
        Start the FMS navigation response service
        
        Args:
            event_loop: Optional event loop to use for async operations
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                logger.info("FMS navigation service not initialized, initializing now...")
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
            self._navigation_queue = asyncio.Queue()  # Create queue with current event loop
            self._processing = True
            
            # Create and start the queue processing task
            logger.info("Creating queue processing task")
            self._task = self._event_loop.create_task(self._process_navigation_queue())
            self._task.add_done_callback(self._handle_task_done)
            
            logger.info("FMS navigation response service started")
            return True
        except Exception as e:
            logger.error(f"Error starting FMS navigation response service: {e}")
            traceback.print_exc()
            raise

    def _handle_task_done(self, task):
        """Handle completion of the processing task"""
        try:
            # Check if task failed with an exception
            if task.exception():
                logger.error(f"FMS navigation processing task failed: {task.exception()}")
                # Restart the task if processing should continue
                if self._processing:
                    logger.info("Restarting FMS navigation processing task")
                    self._task = self._event_loop.create_task(self._process_navigation_queue())
                    self._task.add_done_callback(self._handle_task_done)
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            traceback.print_exc()

    async def stop(self):
        """Stop the FMS navigation response service"""
        try:
            logger.info("Stopping FMS navigation response service")
            self._processing = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("FMS navigation response service stopped")
        except Exception as e:
            logger.error(f"Error stopping FMS navigation response service: {e}")
            traceback.print_exc()

    async def _process_navigation_queue(self):
        """Process navigation data queue with robust error handling"""
        logger.info("Starting FMS navigation queue processor")
        try:
            while self._processing:
                try:
                    logger.info("Waiting for FMS navigation data...")
                    navigation_data = await self._navigation_queue.get()
                    logger.info(f"Processing FMS navigation data: {navigation_data}")
                    try:
                        # Store data synchronously
                        success = self.data_handler.store_navigation_data(navigation_data)
                        if success:
                            logger.info(f"FMS navigation data processed and stored: {getattr(navigation_data, 'request_id', 'unknown')}")
                            # Only mark task done if storage was successful
                            self._navigation_queue.task_done()
                            
                            # Route to display system after storage
                            await self._route_to_display(navigation_data)
                        else:
                            logger.error(f"Failed to store FMS navigation data")
                            # Log failure details
                            logger.error(f"Failed data: {navigation_data}")
                            # Put the data back in queue for retry
                            await self._navigation_queue.put(navigation_data)
                    except Exception as store_error:
                        logger.error(f"Error storing FMS navigation data: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('fms_navigation_failures.log', 'a') as f:
                            f.write(f"Failed FMS Navigation Data: {navigation_data}\nError: {store_error}\n")
                        # Put the data back in queue for retry
                        await self._navigation_queue.put(navigation_data)
                except asyncio.CancelledError:
                    logger.info("FMS navigation queue processor cancelled")
                    break
                except Exception as e:
                    logger.error(f"FMS navigation queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Brief pause before retrying
        except Exception as e:
            logger.error(f"Fatal error in FMS navigation queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _route_to_display(self, navigation_data):
        """Route navigation data to display system"""
        try:
            # Get display message handler directly
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            
            if display_handler:
                # Create message for display system
                display_message = {
                    'data': navigation_data,
                    'request_id': getattr(navigation_data, 'request_id', str(time.time())),
                    'timestamp': getattr(navigation_data, 'timestamp', time.time()),
                    'message_type': 'fms_navigationData',
                    'metadata': {
                        'data_type': 'navigation_data',
                        'source': 'flightManagementSystem',
                        'destination': 'display_system',
                        'command_type': 'navigation_data',
                        '_direct_from_fms_service': True
                    }
                }
                
                # Send via display handler's generic handler
                await display_handler.handle_generic_message(display_message)
                logger.info("Sent FMS navigation data to display system")
            else:
                logger.error("Could not get display message handler")
        except Exception as e:
            logger.error(f"Error routing to display: {e}")
            logger.error(traceback.format_exc())

    async def handle_navigation_data(self, message: Dict[str, Any]):
        """
        Handle FMS navigation data
        
        Args:
            message: Dictionary containing navigation data
        """
        try:
            # Check if this message has already been processed to prevent loops
            if message.get('metadata', {}).get('_processed_by_fms_navigation_service', False):
                logger.warning("Detected loop - message already processed by FMS navigation service")
                return

            # Add loop prevention flag
            if 'metadata' not in message:
                message['metadata'] = {}
            message['metadata']['_processed_by_fms_navigation_service'] = True
            
            # Log message
            logger.info("Handling FMS navigation data message")
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
                logger.warning("FMS navigation data missing request_id")
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
            if not self._navigation_queue:
                logger.info("Initializing queue for FMS navigation data")
                # Get current event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                # Start service with current loop
                await self.start(event_loop=loop)
            
            # Add to queue for processing
            await self._navigation_queue.put(data)
            
            # Send acknowledgment
            await self._send_acknowledgment(request_id, True, "FMS navigation data received")
            
        except Exception as e:
            logger.error(f"Error handling FMS navigation data: {e}")
            traceback.print_exc()
            if 'request_id' in locals():
                await self._send_acknowledgment(request_id, False, f"Error: {str(e)}")

    async def _send_acknowledgment(self, request_id: str, success: bool, message: str):
        """Send acknowledgment message"""
        try:
            ack_message = {
                'request_id': request_id,
                'command_type': 'navigation_data',
                'system_type': 'flightManagementSystem',
                'status': 'acknowledged' if success else 'failed',
                'timestamp': time.time(),
                'additional_info': {
                    'data_type': 'navigation_data',
                    'message_type': 'fms_navigationDataResponse',
                    'status_message': message
                }
            }
            
            await self.routing_service.route_status_word(ack_message)
            logger.info(f"Sent acknowledgment for {request_id}: {ack_message['status']}")
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment: {e}")

# Singleton instance
_fms_navigation_response_service = None

def get_fms_navigation_response_service():
    """Get singleton instance of FMS Navigation Response Service"""
    global _fms_navigation_response_service
    if _fms_navigation_response_service is None:
        # Get FMS database from DBM
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        fms_db = db_manager.get_system_db('flightManagementSystem')
        
        # Create instance with FMS database
        _fms_navigation_response_service = FMSNavigationResponseService(fms_db)
    return _fms_navigation_response_service
