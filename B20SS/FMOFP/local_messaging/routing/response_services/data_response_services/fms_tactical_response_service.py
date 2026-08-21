"""
FMS Tactical response service for handling tactical data

Provides:
1. Async queue processing of tactical data
2. Integration with data handler for storage
3. Error handling and logging
4. Direct display notification without using MessageRoutingService
"""

import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.fms_tactical_data import create_fms_tactical_data_message
from FMOFP.Utils.common.message_format_adapter import get_message_format_adapter

logger = get_logger()

class FMSTacticalDataHandler:
    """Handles FMS tactical data storage and retrieval"""
    
    def __init__(self, fms_db):
        """Initialize with FMS database connection"""
        self.fms_db = fms_db
        
        # Ensure table exists
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            # Create tactical data table
            self.fms_db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS tactical_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    throttle_position REAL NOT NULL,
                    radar_cross_section REAL NOT NULL,
                    infrared_signature REAL NOT NULL,
                    ecm_status TEXT NOT NULL,
                    fuel_status REAL NOT NULL,
                    weapon_status TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
                """,
                query_type='execute'
            )
            logger.info("FMS tactical data table created/verified")
        except Exception as e:
            logger.error(f"Error creating tactical data tables: {e}")
            logger.error(traceback.format_exc())
    
    def store_tactical_data(self, tactical_data):
        """Store tactical data in the database"""
        try:
            # Extract values from tactical data
            request_id = getattr(tactical_data, 'request_id', str(time.time()))
            
            # Extract tactical values
            if hasattr(tactical_data, 'data') and isinstance(tactical_data.data, dict):
                # Format from message object
                mode = tactical_data.data.get('mode', 'NORMAL')
                status = tactical_data.data.get('status', 'READY')
                throttle_position = tactical_data.data.get('throttle_position', 0.0)
                radar_cross_section = tactical_data.data.get('radar_cross_section', 0.0)
                infrared_signature = tactical_data.data.get('infrared_signature', 0.0)
                ecm_status = tactical_data.data.get('ecm_status', 'INACTIVE')
                fuel_status = tactical_data.data.get('fuel_status', 100.0)
                weapon_status = tactical_data.data.get('weapon_status', 'SAFE')
            else:
                # Direct attributes
                mode = getattr(tactical_data, 'mode', 'NORMAL')
                status = getattr(tactical_data, 'status', 'READY')
                throttle_position = getattr(tactical_data, 'throttle_position', 0.0)
                radar_cross_section = getattr(tactical_data, 'radar_cross_section', 0.0)
                infrared_signature = getattr(tactical_data, 'infrared_signature', 0.0)
                ecm_status = getattr(tactical_data, 'ecm_status', 'INACTIVE')
                fuel_status = getattr(tactical_data, 'fuel_status', 100.0)
                weapon_status = getattr(tactical_data, 'weapon_status', 'SAFE')
            
            # Get timestamp
            timestamp = getattr(tactical_data, 'timestamp', time.time())
            
            # Insert into database
            self.fms_db.execute_query(
                """
                INSERT INTO tactical_data 
                (request_id, mode, status, throttle_position, radar_cross_section, 
                infrared_signature, ecm_status, fuel_status, weapon_status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, mode, status, throttle_position, radar_cross_section, 
                infrared_signature, ecm_status, fuel_status, weapon_status, timestamp),
                query_type='execute'
            )
            
            logger.info(f"Stored FMS tactical data: request_id={request_id}, mode={mode}, status={status}")
            return True
        except Exception as e:
            logger.error(f"Error storing tactical data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def get_latest_tactical_data(self):
        """Get the latest tactical data"""
        try:
            result = self.fms_db.execute_query(
                """
                SELECT * FROM tactical_data
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                query_type='select'
            )
            
            if result and len(result) > 0:
                # Get column names
                with self.fms_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(tactical_data)")
                    columns = [col[1] for col in cursor.fetchall()]
                
                # Convert row to dictionary
                row = result[0]
                data_dict = dict(zip(columns, row))
                
                # Create tactical data message
                tactical_data = create_fms_tactical_data_message(
                    mode=data_dict['mode'],
                    status=data_dict['status'],
                    throttle_position=data_dict['throttle_position'],
                    radar_cross_section=data_dict['radar_cross_section'],
                    infrared_signature=data_dict['infrared_signature'],
                    ecm_status=data_dict['ecm_status'],
                    fuel_status=data_dict['fuel_status'],
                    weapon_status=data_dict['weapon_status'],
                    timestamp=data_dict['timestamp']
                )
                
                # Add request ID
                tactical_data['request_id'] = data_dict['request_id']
                
                return tactical_data
            
            return None
        except Exception as e:
            logger.error(f"Error getting latest tactical data: {e}")
            logger.error(traceback.format_exc())
            return None

class FMSTacticalResponseService:
    """Handles FMS tactical data processing and storage"""
    _instance = None
    _initialized = False

    def __new__(cls, fms_db=None):
        if cls._instance is None:
            cls._instance = super(FMSTacticalResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, fms_db=None):
        """Initialize with FMS database connection"""
        if not self._initialized and fms_db is not None:
            self.data_handler = FMSTacticalDataHandler(fms_db)
            self._tactical_queue = None
            self._event_loop = None
            self._processing = False
            self._task = None
            
            # Get routing service for message handling
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.routing_service = get_message_routing_service()
            
            self._initialized = True
            logger.info("FMSTacticalResponseService initialized")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("FMSTacticalResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("FMSTacticalResponseService fully initialized")
            
        except Exception as e:
            logger.error(f"Error during FMSTacticalResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize FMSTacticalResponseService") from e

    async def start(self, event_loop=None) -> bool:
        """
        Start the FMS tactical response service
        
        Args:
            event_loop: Optional event loop to use for async operations
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                logger.info("FMS tactical service not initialized, initializing now...")
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
            self._tactical_queue = asyncio.Queue()  # Create queue with current event loop
            self._processing = True
            
            # Create and start the queue processing task
            logger.info("Creating queue processing task")
            self._task = self._event_loop.create_task(self._process_tactical_queue())
            self._task.add_done_callback(self._handle_task_done)
            
            logger.info("FMS tactical response service started")
            return True
        except Exception as e:
            logger.error(f"Error starting FMS tactical response service: {e}")
            traceback.print_exc()
            raise

    def _handle_task_done(self, task):
        """Handle completion of the processing task"""
        try:
            # Check if task failed with an exception
            if task.exception():
                logger.error(f"FMS tactical processing task failed: {task.exception()}")
                # Restart the task if processing should continue
                if self._processing:
                    logger.info("Restarting FMS tactical processing task")
                    self._task = self._event_loop.create_task(self._process_tactical_queue())
                    self._task.add_done_callback(self._handle_task_done)
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            traceback.print_exc()

    async def stop(self):
        """Stop the FMS tactical response service"""
        try:
            logger.info("Stopping FMS tactical response service")
            self._processing = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("FMS tactical response service stopped")
        except Exception as e:
            logger.error(f"Error stopping FMS tactical response service: {e}")
            traceback.print_exc()

    async def _process_tactical_queue(self):
        """Process tactical data queue with robust error handling"""
        logger.info("Starting FMS tactical queue processor")
        try:
            while self._processing:
                try:
                    logger.info("Waiting for FMS tactical data...")
                    tactical_data = await self._tactical_queue.get()
                    logger.info(f"Processing FMS tactical data: {tactical_data}")
                    try:
                        # Store data synchronously
                        success = self.data_handler.store_tactical_data(tactical_data)
                        if success:
                            logger.info(f"FMS tactical data processed and stored: {getattr(tactical_data, 'request_id', 'unknown')}")
                            # Only mark task done if storage was successful
                            self._tactical_queue.task_done()
                            
                            # Route to display system after storage
                            await self._route_to_display(tactical_data)
                        else:
                            logger.error(f"Failed to store FMS tactical data")
                            # Log failure details
                            logger.error(f"Failed data: {tactical_data}")
                            # Put the data back in queue for retry
                            await self._tactical_queue.put(tactical_data)
                    except Exception as store_error:
                        logger.error(f"Error storing FMS tactical data: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('fms_tactical_failures.log', 'a') as f:
                            f.write(f"Failed FMS Tactical Data: {tactical_data}\nError: {store_error}\n")
                        # Put the data back in queue for retry
                        await self._tactical_queue.put(tactical_data)
                except asyncio.CancelledError:
                    logger.info("FMS tactical queue processor cancelled")
                    break
                except Exception as e:
                    logger.error(f"FMS tactical queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Brief pause before retrying
        except Exception as e:
            logger.error(f"Fatal error in FMS tactical queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _route_to_display(self, tactical_data):
        """Route tactical data to display system"""
        try:
            # Get display message handler directly
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()
            
            if display_handler:
                # Create message for display system
                display_message = {
                    'data': tactical_data,
                    'request_id': getattr(tactical_data, 'request_id', str(time.time())),
                    'timestamp': getattr(tactical_data, 'timestamp', time.time()),
                    'message_type': 'fms_tacticalData',
                    'metadata': {
                        'data_type': 'tactical_data',
                        'source': 'flightManagementSystem',
                        'destination': 'display_system',
                        'command_type': 'tactical_data',
                        '_direct_from_fms_service': True
                    }
                }
                
                # Send via display handler's generic handler
                await display_handler.handle_generic_message(display_message)
                logger.info("Sent FMS tactical data to display system")
            else:
                logger.error("Could not get display message handler")
        except Exception as e:
            logger.error(f"Error routing to display: {e}")
            logger.error(traceback.format_exc())

    async def handle_tactical_data(self, message: Dict[str, Any]):
        """
        Handle FMS tactical data
        
        Args:
            message: Dictionary containing tactical data
        """
        try:
            # Check if this message has already been processed to prevent loops
            if message.get('metadata', {}).get('_processed_by_fms_tactical_service', False):
                logger.warning("Detected loop - message already processed by FMS tactical service")
                return

            # Add loop prevention flag
            if 'metadata' not in message:
                message['metadata'] = {}
            message['metadata']['_processed_by_fms_tactical_service'] = True
            
            # Log message
            logger.info("Handling FMS tactical data message")
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
                logger.warning("FMS tactical data missing request_id")
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
            if not self._tactical_queue:
                logger.info("Initializing queue for FMS tactical data")
                # Get current event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                # Start service with current loop
                await self.start(event_loop=loop)
            
            # Add to queue for processing
            await self._tactical_queue.put(data)
            
            # Send acknowledgment
            await self._send_acknowledgment(request_id, True, "FMS tactical data received")
            
        except Exception as e:
            logger.error(f"Error handling FMS tactical data: {e}")
            traceback.print_exc()
            if 'request_id' in locals():
                await self._send_acknowledgment(request_id, False, f"Error: {str(e)}")

    async def _send_acknowledgment(self, request_id: str, success: bool, message: str):
        """Send acknowledgment message"""
        try:
            ack_message = {
                'request_id': request_id,
                'command_type': 'tactical_data',
                'system_type': 'flightManagementSystem',
                'status': 'acknowledged' if success else 'failed',
                'timestamp': time.time(),
                'additional_info': {
                    'data_type': 'tactical_data',
                    'message_type': 'fms_tacticalDataResponse',
                    'status_message': message
                }
            }
            
            await self.routing_service.route_status_word(ack_message)
            logger.info(f"Sent acknowledgment for {request_id}: {ack_message['status']}")
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment: {e}")

# Singleton instance
_fms_tactical_response_service = None

def get_fms_tactical_response_service():
    """Get singleton instance of FMS Tactical Response Service"""
    global _fms_tactical_response_service
    if _fms_tactical_response_service is None:
        # Get FMS database from DBM
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        fms_db = db_manager.get_system_db('flightManagementSystem')
        
        # Create instance with FMS database
        _fms_tactical_response_service = FMSTacticalResponseService(fms_db)
    return _fms_tactical_response_service
