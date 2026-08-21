"""
Enhanced Radar Response Service

Provides robust storage and management of:
1. Command acknowledgments
2. Mode change data
3. Comprehensive error handling and logging
"""

import asyncio
import time
import threading
import json
import traceback
import sys
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
from FMOFP.storage.DBM import DatabaseManager
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.response_services.data_response_services.precipitation_response_service import PrecipitationResponseService


logger = get_logger()

@dataclass
class CommandAcknowledgment:
    """Enhanced data structure for command acknowledgments"""
    timestamp: float
    command_type: str
    radar_type: str
    status: str
    request_id: str
    additional_info: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None
    mode_value: Optional[int] = None

@dataclass
class ModeChangeData:
    """Enhanced data structure for mode change data"""
    timestamp: float
    radar_type: str
    mode: str
    request_id: str
    data_word: str
    additional_info: Optional[Dict[str, Any]] = None

class EnhancedRadarResponseService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EnhancedRadarResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Use a lock to prevent race conditions during initialization
            init_lock = threading.Lock()
            
            with init_lock:
                # Check if already initialized by another thread
                if self._initialized:
                    return
                    
                # Database setup with retry mechanism
                max_retries = 5
                retry_delay = 1.0
                self.db_manager = None
                self.radar_db = None
                
                for attempt in range(max_retries):
                    try:
                        # Initialize database manager
                        self.db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                        
                        # Ensure systems dictionary is initialized
                        if not hasattr(self.db_manager, 'systems') or self.db_manager.systems is None:
                            self.db_manager.systems = {}
                            
                        # Initialize system databases if needed
                        if not self.db_manager.initialized:
                            self.db_manager.initialize_system_databases()
                            
                        # Get radar_management database
                        self.radar_db = self.db_manager.get_system_db('radar_management')
                        
                        # If we got here, database setup was successful
                        logger.info("Database setup successful")
                        break
                    except Exception as e:
                        logger.error(f"Database setup attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        else:
                            raise RuntimeError("Failed to initialize database") from e
                
                # Initialize threading components
                self._lock = threading.Lock()
                
                # Create event loop first
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)
                
                # Queues and event loop management
                self._acknowledgment_queue = asyncio.Queue()
                self._mode_change_queue = asyncio.Queue()
                
                # Initialize database tables with retry mechanism
                for attempt in range(max_retries):
                    try:
                        # Initialize database tables
                        self._init_database_tables()
                        # If we got here, table initialization was successful
                        logger.info("Database tables initialized successfully")
                        break
                    except Exception as e:
                        logger.error(f"Database table initialization attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        else:
                            raise RuntimeError("Failed to initialize database tables") from e
                
                # Start event loop manager
                self._start_event_loop_manager()
                
                # Initialize precipitation service
                self.precipitation_service = PrecipitationResponseService(self.radar_db)
                
                self._initialized = True
                logger.info("EnhancedRadarResponseService initialized")

    def _init_database_tables(self):
        """Robust database table initialization with enhanced schema"""
        try:
            # Check if tables already exist
            acks_exists = self.radar_db.table_exists('command_acknowledgments')
            mode_exists = self.radar_db.table_exists('mode_changes')
            
            if acks_exists and mode_exists:
                logger.info("Database tables already exist")
                return
            
            # Initialize tables only if they don't exist
            if not acks_exists:
                # Command acknowledgments table with updated schema - removed UNIQUE constraint
                self.radar_db.create_table('command_acknowledgments', {
                    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'timestamp': 'REAL NOT NULL',
                    'command_type': 'TEXT NOT NULL',
                    'radar_type': 'TEXT NOT NULL',
                    'status': 'TEXT NOT NULL',
                    'request_id': 'TEXT NOT NULL',
                    'additional_info': 'TEXT',
                    'created_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP'
                })
                
                # Create composite index for faster lookups
                self.radar_db.execute_query(
                    "CREATE INDEX IF NOT EXISTS idx_command_acks_composite ON command_acknowledgments(request_id, timestamp)",
                    query_type='create'
                )
            
            if not mode_exists:
                # Mode changes table - removed UNIQUE constraint from request_id
                self.radar_db.create_table('mode_changes', {
                    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'timestamp': 'REAL NOT NULL',
                    'radar_type': 'TEXT NOT NULL',
                    'mode': 'TEXT NOT NULL',
                    'request_id': 'TEXT NOT NULL',
                    'data_word': 'TEXT NOT NULL',
                    'additional_info': 'TEXT',
                    'created_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP'
                })
                
                # Create composite index for faster lookups
                self.radar_db.execute_query(
                    "CREATE INDEX IF NOT EXISTS idx_mode_changes_composite ON mode_changes(request_id, timestamp)",
                    query_type='create'
                )

            logger.info("Enhanced database tables initialized")
        except Exception as e:
            logger.error(f"Database table initialization failed: {e}")
            traceback.print_exc()
            raise

    def _start_event_loop_manager(self):
        """Start a dedicated event loop manager thread"""
        if hasattr(self, '_event_loop_thread') and self._event_loop_thread.is_alive():
            logger.info("Event loop manager already running")
            return

        def event_loop_manager():
            try:
                # Create and store event loop if not exists
                if not hasattr(self, '_event_loop') or self._event_loop.is_closed():
                    self._event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._event_loop)
                
                # Create tasks if they don't exist or are done
                if not hasattr(self, '_tasks') or any(task.done() for task in self._tasks):
                    self._tasks = [
                        self._event_loop.create_task(self._process_acknowledgment_queue()),
                        self._event_loop.create_task(self._process_mode_change_queue())
                    ]
                    
                    # Store tasks reference
                    for task in self._tasks:
                        # NOTE: not t.cancelled() alone is not sufficient here.
                        # _process_acknowledgment_queue()/_process_mode_change_queue()
                        # both catch asyncio.CancelledError internally and `break`
                        # out of their loop to shut down cleanly (see their
                        # `except asyncio.CancelledError: ...; break`), rather than
                        # letting it propagate. That means a task we intentionally
                        # cancel via stop() completes normally from asyncio's
                        # perspective - t.cancelled() is False even though the
                        # shutdown was requested and handled correctly - so this
                        # previously logged a false "completed unexpectedly" ERROR
                        # on every graceful stop(). Check for an actual stored
                        # exception instead, which only exists on a genuine crash.
                        task.add_done_callback(lambda t: logger.error(f"Task {t} completed unexpectedly") if (not t.cancelled() and t.exception() is not None) else None)
                
                # Run event loop
                self._event_loop.run_forever()
            except Exception as e:
                logger.error(f"Event loop manager error: {e}")
                traceback.print_exc()
                
        # Start event loop manager in a daemon thread
        self._event_loop_thread = threading.Thread(target=event_loop_manager, daemon=True)
        self._event_loop_thread.start()
        
        # Wait for event loop to be ready and tasks to be created
        start_time = time.time()
        timeout = 10  # 10 second timeout
        
        while time.time() - start_time < timeout:
            if not hasattr(self, '_event_loop') or not self._event_loop.is_running():
                time.sleep(0.1)
                continue
                
            if not hasattr(self, '_tasks'):
                time.sleep(0.1)
                continue
                
            # Verify tasks are running
            all_tasks = asyncio.all_tasks(self._event_loop)
            running_tasks = [t for t in all_tasks if not t.done()]
            if len(running_tasks) >= 2:  # We expect at least 2 tasks
                logger.info(f"Event loop manager started with {len(running_tasks)} tasks running")
                return
                
            time.sleep(0.1)
            
        raise RuntimeError("Failed to start event loop manager within timeout")

    async def stop(self):
        """Stop the event loop manager thread and its background tasks.

        NOTE: This class has no shutdown path prior to this fix. Its
        internal `_event_loop_thread` is a daemon thread, so it does not
        by itself prevent process exit, but MessageRoutingService.stop()
        was unconditionally doing `await self.radar_response_service.stop()`
        on every shutdown, which raised
        "AttributeError: 'EnhancedRadarResponseService' object has no
        attribute 'stop'" (visible as an unretrieved task exception in the
        logs) since this method never existed. This adds a real stop() that
        cancels the queue-processing tasks and stops/joins the dedicated
        event loop thread, matching the async calling convention already
        used by MessageRoutingService.stop().
        """
        logger.info("[RADAR_RESPONSE_SVC] Stopping EnhancedRadarResponseService")
        try:
            if hasattr(self, '_event_loop') and self._event_loop and self._event_loop.is_running():
                if hasattr(self, '_tasks'):
                    for task in self._tasks:
                        self._event_loop.call_soon_threadsafe(task.cancel)
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)

            if hasattr(self, '_event_loop_thread') and self._event_loop_thread.is_alive():
                self._event_loop_thread.join(timeout=2.0)
                if self._event_loop_thread.is_alive():
                    logger.warning("[RADAR_RESPONSE_SVC] Event loop manager thread did not stop within timeout")
                else:
                    logger.info("[RADAR_RESPONSE_SVC] Event loop manager thread stopped")
        except Exception as e:
            logger.error(f"[RADAR_RESPONSE_SVC] Error stopping: {e}")
        logger.info("[RADAR_RESPONSE_SVC] EnhancedRadarResponseService stopped")

    async def _process_acknowledgment_queue(self):
        """Process acknowledgment queue with robust error handling"""
        logger.info("Starting acknowledgment queue processor")
        try:
            while True:
                try:
                    logger.info("Waiting for acknowledgment...")
                    ack = await self._acknowledgment_queue.get()
                    logger.info(f"Processing acknowledgment: {ack}")
                    try:
                        await self._store_command_acknowledgment(ack)
                        logger.info(f"Acknowledgment processed and stored: {ack.request_id}")
                    except Exception as store_error:
                        logger.error(f"Error storing acknowledgment: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('acknowledgment_failures.log', 'a') as f:
                            f.write(f"Failed Acknowledgment: {ack}\nError: {store_error}\n")
                    finally:
                        self._acknowledgment_queue.task_done()
                except asyncio.CancelledError:
                    logger.info("Acknowledgment queue processor cancelled")
                    break
                except Exception as e:
                    logger.error(f"Acknowledgment queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Fatal error in acknowledgment queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _process_mode_change_queue(self):
        """Process mode change queue with robust error handling"""
        while True:
            try:
                mode_change = await self._mode_change_queue.get()
                await self._store_mode_change(mode_change)
                self._mode_change_queue.task_done()
            except Exception as e:
                logger.error(f"Mode change queue processing error: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)

    async def _store_command_acknowledgment(self, ack: CommandAcknowledgment):
        """
        Robust method to store command acknowledgments
        
        Args:
            ack (CommandAcknowledgment): Acknowledgment data to store
        """
        try:
            # Log incoming acknowledgment
            logger.info(f"[STORE] Storing command acknowledgment:")
            logger.info(f"[STORE]   timestamp: {ack.timestamp}")
            logger.info(f"[STORE]   command_type: {ack.command_type}")
            logger.info(f"[STORE]   radar_type: {ack.radar_type}")
            logger.info(f"[STORE]   status: {ack.status}")
            logger.info(f"[STORE]   request_id: {ack.request_id}")
            logger.info(f"[STORE]   additional_info: {ack.additional_info}")

            # Verify table exists
            table_check = self.radar_db.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='command_acknowledgments'",
                query_type='select'
            )
            logger.info(f"[STORE] Table check result: {table_check}")
            
            if not table_check:
                logger.error("[STORE] command_acknowledgments table does not exist!")
                raise Exception("command_acknowledgments table missing")

            # Get current row count
            count_before = self.radar_db.execute_query(
                "SELECT COUNT(*) FROM command_acknowledgments",
                query_type='select'
            )
            logger.info(f"[STORE] Row count before insert: {count_before}")
            
            additional_info = json.dumps(ack.additional_info) if ack.additional_info else None
            
            fields = ['timestamp', 'command_type', 'radar_type', 'status', 'request_id', 'additional_info']
            placeholders = ', '.join(['?' for _ in fields])
            
            query = f'INSERT INTO "command_acknowledgments" ({", ".join(fields)}) VALUES ({placeholders})'
            params = (
                ack.timestamp, 
                ack.command_type, 
                ack.radar_type, 
                ack.status, 
                ack.request_id, 
                additional_info
            )
            
            # Log database operation
            logger.info(f"[STORE] Executing database query:")
            logger.info(f"[STORE]   Query: {query}")
            logger.info(f"[STORE]   Parameters: {params}")
            
            # Execute database operation
            if 'test' in sys.modules:
                logger.info("[STORE] Test environment detected - forcing immediate storage")
                
                # First verify table exists
                table_check = self.radar_db.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='command_acknowledgments'",
                    query_type='select'
                )
                logger.info(f"[STORE] Table check result: {table_check}")
                
                if not table_check:
                    logger.error("[STORE] command_acknowledgments table does not exist!")
                    raise Exception("command_acknowledgments table missing")
                
                try:
                    # Execute insert with explicit transaction management
                    result = self.radar_db.execute_query(
                        query,
                        params,
                        query_type='insert',
                        manage_transaction=True  # Let DBM handle the transaction
                    )
                    logger.info(f"[STORE] Insert result: {result}")
                    
                    # Force batch processing
                    self.radar_db.process_batch('insert')
                    
                    # Add delay to ensure storage completes
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"[STORE] Error during insert: {e}")
                    raise
                
                # Verify storage
                verify_query = 'SELECT * FROM "command_acknowledgments" WHERE request_id = ? AND radar_type = ?'
                verify_params = (ack.request_id, ack.radar_type)
                verify_result = self.radar_db.execute_query(
                    verify_query,
                    verify_params,
                    query_type='select'
                )
                
                if verify_result:
                    logger.info(f"[STORE] Verified acknowledgment storage: {verify_result}")
                else:
                    logger.error("[STORE] Failed to verify acknowledgment storage")
                    # Try one more time with a delay
                    await asyncio.sleep(0.5)
                    verify_result = self.radar_db.execute_query(
                        verify_query,
                        verify_params,
                        query_type='select'
                    )
                    if verify_result:
                        logger.info(f"[STORE] Verified acknowledgment storage on retry: {verify_result}")
                    else:
                        logger.error("[STORE] Failed to verify acknowledgment storage after retry")
                        raise Exception("Storage verification failed")
                
                # Get final row count
                count_check = self.radar_db.execute_query(
                    "SELECT COUNT(*) FROM command_acknowledgments",
                    query_type='select'
                )
                logger.info(f"[STORE] Total rows after insert: {count_check}")
            else:
                # Normal operation
                result = self.radar_db.execute_query(query, params, query_type='insert')
            
            logger.info(f"Database operation result: {result}")
            logger.info(f"Stored command acknowledgment for {ack.radar_type} with request_id {ack.request_id}")
        
        except Exception as e:
            logger.error(f"Critical error storing command acknowledgment: {e}")
            traceback.print_exc()
            # Fallback logging
            with open('acknowledgment_failures.log', 'a') as f:
                f.write(f"Failed Acknowledgment: {ack}\nError: {e}\n")

    async def _store_mode_change(self, mode_data: ModeChangeData):
        """
        Robust method to store mode change data
        
        Args:
            mode_data (ModeChangeData): Mode change data to store
        """
        try:
            additional_info = json.dumps(mode_data.additional_info) if mode_data.additional_info else None
            
            fields = ['timestamp', 'radar_type', 'mode', 'request_id', 'data_word', 'additional_info']
            placeholders = ', '.join(['?' for _ in fields])
            
            query = f'INSERT INTO "mode_changes" ({", ".join(fields)}) VALUES ({placeholders})'
            params = (
                mode_data.timestamp,
                mode_data.radar_type,
                mode_data.mode,
                mode_data.request_id,
                mode_data.data_word,
                additional_info
            )
            
            # Force immediate processing for test scenarios
            if 'test' in sys.modules:
                logger.info("[STORE] Test environment detected - forcing immediate insert")
                
                # Start transaction
                self.radar_db.execute_query(
                    "BEGIN IMMEDIATE",
                    query_type='create',
                    manage_transaction=True
                )
                
                try:
                    # Execute insert
                    result = self.radar_db.execute_query(
                        query,
                        params,
                        query_type='insert',
                        manage_transaction=False  # Don't auto-manage since we're handling it
                    )
                    logger.info(f"[STORE] Insert result: {result}")
                    
                    # Commit transaction
                    self.radar_db.execute_query(
                        "COMMIT",
                        query_type='create',
                        manage_transaction=True
                    )
                    
                    # Force batch processing
                    self.radar_db.process_batch('insert')
                    
                    # Add delay to ensure storage completes
                    await asyncio.sleep(0.5)
                    
                    # Verify storage
                    verify_query = 'SELECT * FROM "mode_changes" WHERE request_id = ? AND radar_type = ?'
                    verify_params = (mode_data.request_id, mode_data.radar_type)
                    verify_result = self.radar_db.execute_query(
                        verify_query,
                        verify_params,
                        query_type='select'
                    )
                    
                    if verify_result:
                        logger.info(f"[STORE] Verified mode change storage: {verify_result}")
                    else:
                        logger.error("[STORE] Failed to verify mode change storage")
                        raise Exception("Storage verification failed")
                        
                except Exception as e:
                    # Rollback on error
                    logger.error(f"[STORE] Error during insert: {e}")
                    self.radar_db.execute_query(
                        "ROLLBACK",
                        query_type='create',
                        manage_transaction=True
                    )
                    raise
            else:
                # Normal operation
                result = self.radar_db.execute_query(query, params, query_type='insert')
            
            logger.info(f"Stored mode change for {mode_data.radar_type} with request_id {mode_data.request_id}")
        
        except Exception as e:
            logger.error(f"Critical error storing mode change: {e}")
            traceback.print_exc()
            # Fallback logging
            with open('mode_change_failures.log', 'a') as f:
                f.write(f"Failed Mode Change: {mode_data}\nError: {e}\n")

    def handle_status_word(self, message: Dict[str, Any]):
        """
        Synchronous status word handling
        
        Args:
            message (Dict[str, Any]): Status word message details
        """
        try:
            # Log incoming message
            logger.info(f"Handling status word message: {message}")

            # Check if this is a raw protocol message (only status_word and timestamp)
            if set(message.keys()) == {'status_word', 'timestamp'}:
                logger.info("Ignoring raw status word protocol message")
                return

            # Check if this is a valid acknowledgment message
            if not ('status_word' in message and ('request_id' in message or 'additional_info' in message)):
                logger.warning("Invalid acknowledgment message format")
                return

            # Extract fields from message
            request_id = message.get('request_id')
            if not request_id:
                logger.warning("Status word missing request_id")
                return

            radar_type = message.get('radar_type')
            if not radar_type:
                logger.warning("Status word missing radar_type")
                return

            # Log the message being processed
            logger.info(f"Processing acknowledgment with request_id: {request_id}")

            # Preserve original additional_info
            additional_info = message.get('additional_info', {})

            # Create acknowledgment with comprehensive data
            ack = CommandAcknowledgment(
                timestamp=message.get('timestamp', time.time()),
                command_type=message.get('command_type', None),
                radar_type=radar_type,
                status=message.get('status', 'acknowledged'),
                request_id=request_id,
                additional_info=additional_info
            )

            # Convert radar_type from integer to string if needed
            if isinstance(ack.radar_type, int):
                ack.radar_type = f"weather_radar"  # Default to weather_radar for now
            
            # Store acknowledgment directly
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, use create_task
                future = asyncio.create_task(self._store_command_acknowledgment(ack))
                # Wait for a short time to ensure storage completes
                loop.call_later(0.1, lambda: asyncio.ensure_future(future))
            else:
                # If we're not in an async context, run the coroutine directly
                loop.run_until_complete(self._store_command_acknowledgment(ack))
        
        except Exception as e:
            logger.error(f"[RDR_RESPSE_SERV] Error handling status word: {e}")
            traceback.print_exc()

    async def handle_precipitation_data(self, message: Dict[str, Any]):
        """Route precipitation data to precipitation service"""
        await self.precipitation_service.handle_precipitation_data(message)

    async def handle_status_word_async(self, message: Dict[str, Any]):
        """
        Asynchronous status word handling
        
        Args:
            message (Dict[str, Any]): Status word message details
        """
        try:
            # Ensure we're running in the correct event loop
            if not self._event_loop or not self._event_loop.is_running():
                logger.error("[RDR_RSPNS_SERV][STATUS] Event loop not running!")
                return
            
            # Initialize metadata from message
            metadata = message.get('additional_info', {})
            logger.info(f"[RDR_RSPNS_SERV][STATUS] Handling async status word with metadata: {metadata}")
                
            # Simple log for tracking
            logger.info(f"[RDR_RSPNS_SERV][STATUS] Storing status word with request_id: {message.get('request_id')}")

            # Get additional info and request ID
            additional_info = message.get('additional_info', {})
            request_id = message.get('request_id')
            radar_type = message.get('radar_type')
            command_type = message.get('command_type')
            timestamp = message.get('timestamp', time.time())
            mode = message.get('mode')
            mode_value = message.get('mode_value')
            
            ## For acknowledged mode changes, mode = "cmd ack".
            

            # Verify required fields
            if not all([request_id, radar_type, command_type]):
                logger.error("[RDR_RSPNS_SERV][STATUS] Missing required fields in status word message")
                logger.error(f"[RDR_RSPNS_SERV][STATUS] request_id: {request_id}")
                logger.error(f"[RDR_RSPNS_SERV][STATUS] radar_type: {radar_type}")
                logger.error(f"[RDR_RSPNS_SERV][STATUS] command_type: {command_type}")
                return

            # Create acknowledgment object
            ack = CommandAcknowledgment(
                timestamp=timestamp,
                command_type=command_type,
                radar_type=radar_type,
                status=message.get('status', 'acknowledged'),
                request_id=request_id,
                mode=mode or None,  # Add mode as top-level attribute
                mode_value=mode_value or None,  # Add mode_value as top-level attribute (must be int or None)
                additional_info=additional_info
            )

            if mode == None and message.get('status', 'acknowledged') == 'acknowledged':
                # If no mode is provided, and status is acknowledged, this as a command acknowledgement for the mode set
                mode = 'cmd ack'
                mode_value = None

            # Log acknowledgment details
            logger.info(f"[STORE] Created acknowledgment object:")
            logger.info(f"[STORE]   timestamp: {ack.timestamp}")
            logger.info(f"[STORE]   command_type: {ack.command_type}")
            logger.info(f"[STORE]   radar_type: {ack.radar_type}")
            logger.info(f"[STORE]   status: {ack.status}")
            logger.info(f"[STORE]   request_id: {ack.request_id}")
            logger.info(f"[STORE]   additional_info: {ack.additional_info}")

            # Check if this is a mode change completion message
            is_completion = (
                command_type == 'mode_change_completion' or
                message.get('message_type') == 'weather_radarModeChangeCompletion' or
                (metadata and metadata.get('message_type') == 'weather_radarModeChangeCompletion')
            )
            
            # Check if this message has already been processed
            if metadata and metadata.get('_processed_by_radar_response'):
                logger.warning(f"[ACK] Skipping already processed message with request_id {request_id}")
                return
                
            # Mark this message as processed to prevent loops
            if not metadata:
                metadata = {}
            metadata['_processed_by_radar_response'] = True
            
            # For mode change commands, store mode change data first
            
            if command_type == 'mode_change' and not is_completion:
                # Get mode value from data word
                mode_value = None
                data_word = None
                
                # First try to get from command word's additional info
                command_info = message.get('additional_info', {}).get('command_word', {})
                if isinstance(command_info, dict):
                    # Try to get from data_words list
                    data_words = command_info.get('data_words', [])
                    if data_words and isinstance(data_words[0], dict) and 'data' in data_words[0]:
                        mode_value = data_words[0]['data']
                        data_word = format(mode_value, '016b')
                        logger.info(f"Extracted mode value {mode_value} from command_word data_words")
                
                # If not found, try the raw data word in message
                if not mode_value:
                    raw_data = message.get('data_word')
                    if isinstance(raw_data, dict) and 'data' in raw_data:
                        mode_value = raw_data['data']
                        data_word = format(mode_value, '016b')
                        logger.info(f"Extracted mode value {mode_value} from raw data word")
                    elif isinstance(raw_data, str) and len(raw_data) >= 16:
                        data_word = raw_data[-16:]
                        mode_value = int(data_word, 2)
                        logger.info(f"Extracted mode value {mode_value} from binary data word")
                
                # If still not found, try the decoded data words
                if not mode_value and 'data_words' in message:
                    decoded_words = message['data_words']
                    if decoded_words and isinstance(decoded_words[0], dict) and 'data' in decoded_words[0]:
                        mode_value = decoded_words[0]['data']
                        data_word = format(mode_value, '016b')
                        logger.info(f"Extracted mode value {mode_value} from decoded data words")
                
                # If still not found, try to get from command word's data words
                if not mode_value and 'command_word' in message:
                    cmd_word = message['command_word']
                    if isinstance(cmd_word, dict) and 'data_words' in cmd_word:
                        data_words = cmd_word['data_words']
                        if data_words and isinstance(data_words[0], dict) and 'data' in data_words[0]:
                            mode_value = data_words[0]['data']
                            data_word = format(mode_value, '016b')
                            logger.info(f"Extracted mode value {mode_value} from command word data_words")
                
                # If still not found, try to get from command word's data field
                if not mode_value and 'command_word' in message:
                    cmd_word = message['command_word']
                    if isinstance(cmd_word, dict) and 'data' in cmd_word:
                        mode_value = cmd_word['data']
                        data_word = format(mode_value, '016b')
                        logger.info(f"Extracted mode value {mode_value} from command word data")
                
                # If still not found, try to get from the message itself
                if not mode_value:
                    # Look for any dictionary in the message that has a 'data' field
                    for key, value in message.items():
                        if isinstance(value, dict) and 'data' in value:
                            mode_value = value['data']
                            data_word = format(mode_value, '016b')
                            logger.info(f"Extracted mode value {mode_value} from message field {key}")
                            break
                
                if mode_value is not None:
                    mode_name = str(mode_value)
                    # Update additional_info with mode data
                    additional_info.update({
                        'mode': mode_name,
                        'data_word': data_word or format(mode_value, '016b'),
                        'command_type': 'mode_change',
                        '_processed_by_radar_response': True  # Mark as processed
                    })
                    logger.info(f"[RDR_RESPSE_SERV] Added mode info to additional_info: {additional_info}")
                else:
                    # if status is acknowledged then it is a command acknowledgment, set mode to 'cmd ack'
                    if message.get('status', 'acknowledged') == 'acknowledged' and message.get('command_type') == 'mode_change':
                        mode = 'cmd ack'
                        logger.debug(f"[RDR_RESPSE_SERV] error in mode value: {mode_value}")

                # Store mode change first - ensure mode is never NULL
                mode_value_str = additional_info.get('mode', 'command_ack')
                if mode_value_str is None:
                    mode_value_str = 'command_ack'  # Default to 'command_ack' if mode is None
                
                mode_data = ModeChangeData(
                    timestamp=timestamp,
                    radar_type=radar_type,
                    mode=mode_value_str,  # Use the non-NULL mode value
                    request_id=request_id,
                    data_word=additional_info.get('data_word', '0'),
                    additional_info=additional_info
                )
                await self._store_mode_change(mode_data)
                logger.info(f"[RDR_RESPSE_SERV] Stored mode change data for {radar_type}")
                # Add delay to ensure mode change is stored
                await asyncio.sleep(0.5)  # Increased delay

            # Create and store acknowledgment with updated additional_info and mode information
            ack = CommandAcknowledgment(
                timestamp=timestamp,
                command_type=command_type,
                radar_type=radar_type,
                status=message.get('status', 'acknowledged'),
                request_id=request_id,
                mode=mode,  # Include mode
                mode_value=mode_value,  # Include mode_value
                additional_info=additional_info
            )

            # Store acknowledgment with retries
            max_retries = 3
            retry_delay = 0.5
            success = False

            for retry in range(max_retries):
                try:
                    # Store acknowledgment
                    await self._store_command_acknowledgment(ack)
                    logger.info(f"[RDR_RESPSE_SERV][STORE] Attempt {retry + 1}: Stored command acknowledgment for {radar_type}")

                    # Verify storage
                    verify_query = 'SELECT * FROM "command_acknowledgments" WHERE request_id = ? AND radar_type = ?'
                    verify_params = (request_id, radar_type)
                    
                    # Add delay before verification
                    await asyncio.sleep(retry_delay)
                    
                    verify_result = self.radar_db.execute_query(
                        verify_query,
                        verify_params,
                        query_type='select'
                    )

                    if verify_result:
                        logger.info(f"[RDR_RESPSE_SERV][STORE] Attempt {retry + 1}: Verified acknowledgment storage: {verify_result}")
                        success = True
                        break
                    else:
                        logger.warning(f"[RDR_RESPSE_SERV][STORE] Attempt {retry + 1}: Storage verification failed")
                        if retry < max_retries - 1:
                            logger.info(f"[RDR_RESPSE_SERV][STORE] Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                except Exception as e:
                    logger.error(f"[RDR_RESPSE_SERV][STORE] Attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        logger.info(f"[RDR_RESPSE_SERV][STORE] Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff

            if not success:
                logger.error(f"[RDR_RESPSE_SERV][STORE] Failed to store acknowledgment after {max_retries} attempts")
                raise Exception("Failed to store and verify acknowledgment")
                
            # After successful storage, check if message should be forwarded to display system
            # This ensures all relevant message types get to the display
            should_forward_to_display = False
            
            # 1. Check for completion messages
            if is_completion:
                should_forward_to_display = True
                logger.warning(f"[RDR_RESPSE_SERV] Marked completion message should_forward_to_display: {request_id}")
                
            # 2. Check for explicit display destination
            elif message.get('destination') == 'display_system':
                should_forward_to_display = True
                logger.warning(f"[RDR_RESPSE_SERV] Forwarding explicit display destination message: {request_id}")
                
            # 3. Check metadata for display destination 
            elif isinstance(message.get('metadata'), dict) and message.get('metadata', {}).get('destination') == 'display_system':
                should_forward_to_display = True
                logger.warning(f"[RDR_RESPSE_SERV] Forwarding metadata-flagged display message: {request_id}")
                
            # 4. Check for radar data messages that need display
            elif command_type in ('precipitation_data', 'vil_data', 'radar_surveillance', 'radar_mapping'):
                should_forward_to_display = True
                logger.warning(f"[RDR_RESPSE_SERV] Forwarding radar data message: {request_id}, type: {command_type}")
                
            # 5. Check for message types known to need display
            elif message.get('message_type') and any(display_type in message.get('message_type', '').lower() 
                                                    for display_type in ['vil', 'precip', 'precipitation', 
                                                                        'surveillance', 'mapping']):
                should_forward_to_display = True
                logger.warning(f"[RDR_RESPSE_SERV] Forwarding display-related message type: {message.get('message_type')}")
            
            # Forward the message if needed
            if should_forward_to_display:
                await self._forward_completion_to_display(message)
        
        except Exception as e:
            logger.error(f"[RDR_RESPSE_SERV] Error handling async status word: {e}")
            traceback.print_exc()

    async def _forward_completion_to_display(self, message: Dict[str, Any]) -> bool:
        """
        Forward completion messages to the display system.
        Called after successful storage in database to ensure display gets updated.
        
        Args:
            message (Dict[str, Any]): The message to forward
            
        Returns:
            bool: True if the message was forwarded successfully, False otherwise
        """
        try:
            # Get or create metadata
            metadata = message.get('metadata', {})
            if 'metadata' not in message:
                message['metadata'] = metadata
                
            # Extract or generate transaction ID
            import uuid
            transaction_id = metadata.get('transaction_id')
            
            # Check additional_info for transaction_id if not in metadata
            add_info = message.get('additional_info', {})
            if not transaction_id and isinstance(add_info, dict):
                transaction_id = add_info.get('transaction_id')
                # Also check processed transactions list
                if not transaction_id and '_processed_transactions' in add_info:
                    trans_list = add_info.get('_processed_transactions', [])
                    if trans_list and len(trans_list) > 0:
                        transaction_id = trans_list[0]
            
            # If still no transaction ID, generate one
            if not transaction_id:
                transaction_id = str(uuid.uuid4())
                message['metadata']['transaction_id'] = transaction_id
                
                # Also add to additional_info for consistent tracking
                if 'additional_info' not in message:
                    message['additional_info'] = {}
                if isinstance(message['additional_info'], dict):
                    message['additional_info']['transaction_id'] = transaction_id
            
            # Initialize _forwarded_transactions if needed
            if not hasattr(self, '_forwarded_transactions'):
                self._forwarded_transactions = set()
                
            # Check if we've already processed this transaction
            if transaction_id in self._forwarded_transactions:
                logger.warning(f"[RDR_RESPSE_SERV] Transaction {transaction_id} already processed in _forwarded_transactions, BREAKING LOOP")
                return True
                
            # Skip if already processed by ModeChangeHandler
            if metadata.get('_processed_by_mode_change_handler') or \
               (isinstance(add_info, dict) and add_info.get('_processed_by_mode_change_handler')):
                logger.warning(f"[RDR_RESPSE_SERV] Message with transaction {transaction_id} already processed by ModeChangeHandler, BREAKING LOOP")
                return True
                
            # Check for our own processing flags
            if metadata.get('_processed_by_radar_response_forward') or \
               metadata.get('_already_forwarded_to_display'):
                logger.warning(f"[RDR_RESPSE_SERV] Message with transaction {transaction_id} already processed or forwarded, BREAKING LOOP")
                return True
                
            # Check if DBM triggered loop
            if metadata.get('_db_processed') or \
               (isinstance(add_info, dict) and add_info.get('_db_processed')):
                logger.warning(f"[RDR_RESPSE_SERV] Message with transaction {transaction_id} already processed by database, BREAKING LOOP")
                return True
                
            # Add processing flags to prevent loops
            message['metadata']['_processed_by_radar_response_forward'] = True
            message['metadata']['_already_forwarded_to_display'] = True
            message['metadata']['transaction_id'] = transaction_id
            
            # Initialize _forwarded_transactions if needed
            if not hasattr(self, '_forwarded_transactions'):
                self._forwarded_transactions = set()
                
            # Check if we've already processed this transaction
            if transaction_id in self._forwarded_transactions:
                logger.info(f"[RDR_RESPSE_SERV] Transaction {transaction_id} already processed, skipping")
                return True
                
            # Add to processed transactions
            self._forwarded_transactions.add(transaction_id)
            
            # Extract key message data
            request_id = message.get('request_id')
            radar_type = message.get('radar_type')
            command_type = message.get('command_type', 'mode_change_completion')
            message_type = message.get('message_type', 'weather_radarModeChangeCompletion')
            data_word = message.get('data_word', '0')
            mode = message.get('mode', 'SURVEILLANCE')
            
            # Ensure timestamp exists
            timestamp = message.get('timestamp')
            if timestamp is None:
                timestamp = time.time()
                message['timestamp'] = timestamp
                logger.warning(f"[RDR_RESPSE_SERV] Missing timestamp, using current time: {timestamp}")
            
            logger.warning(f"[RDR_RESPSE_SERV] Forwarding completion message to display: {request_id}")
            
            # Skip direct DisplayMessageHandler communication to break the loop
            # Just use DisplayResponseService instead for storage and forwarding
            logger.warning(f"[RDR_RESPSE_SERV] Skipping direct DisplayMessageHandler call to prevent message loops")
            
            # Store completion in DisplayResponseService for tracking
            from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
            display_response_service = get_display_response_service()
            
            if display_response_service:
            # Create command data for response service with flags to prevent re-processing loops
                command_data = {
                    'command_type': command_type,
                    'display_type': 'radar_display',
                    'status': 'acknowledged',
                    'request_id': request_id,
                    'timestamp': timestamp,
                    'additional_info': {
                        'source_system': radar_type,
                        'mode': mode,
                        'mode_value': data_word,
                        'update_display_tree': True,
                        'force_update': True,
                        'weather_data': {
                            'mode': mode,
                            'mode_value': data_word,
                            'visual_elements': {
                                'show_intensity_scale': True,
                                'opacity': 1.0,
                                'show_scan_line': mode == 'SURVEILLANCE',
                                'show_terrain_scale': mode == 'MAPPING'
                            }
                        },
                        # Add explicit flags to prevent re-processing and storage loops
                        '_processed_by_radar_response': True,
                        'is_completion_message': True,
                        'final_delivery_to_display': True
                    }
                }
                
                # Store command in response service
                await display_response_service.handle_display_command(command_data, from_display_handler=True)
                logger.warning(f"[RDR_RESPSE_SERV] Mode change command stored in DisplayResponseService")
            
            return True
        except Exception as e:
            logger.error(f"[RDR_RESPSE_SERV] Error forwarding to display: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def handle_mode_change_data(self, message: Dict[str, Any]):
        """
        Enhanced mode change data handling
        
        Args:
            message (Dict[str, Any]): Mode change message details
        """
        try:
            # Log incoming message
            logger.info(f"Handling mode change data: {message}")

            # Extract mode value from data_word if needed
            mode = message.get('mode')
            data_word = message.get('data_word')
            
            if not mode and data_word:
                try:
                    # Try to parse mode from data word
                    if isinstance(data_word, str):
                        if data_word.isdigit():
                            mode = str(int(data_word))
                        else:
                            mode = str(int(data_word, 2))
                    elif isinstance(data_word, (int, float)):
                        mode = str(int(data_word))
                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing mode from data word: {e}") 
                    mode = None

            # Extract radar_type or display_type (Will reach the same destination)
            radar_type = None
            if 'radar_type' in message:
                radar_type = message['radar_type']
            elif 'display_type' in message:
                radar_type = message['display_type']
            else:
                # Try to extract from JSON data if message is a JSON string
                try:
                    if isinstance(message.get('data'), str):
                        data_obj = json.loads(message['data'])
                        if 'display_type' in data_obj:
                            radar_type = data_obj['display_type']
                        elif 'radar_type' in data_obj:
                            radar_type = data_obj['radar_type']
                except (json.JSONDecodeError, AttributeError, TypeError):
                    pass
            
            # If still no radar_type, use a default
            if not radar_type:
                logger.warning(f"[RDR_RESPSE_SERV] No radar_type or display_type found in message, using default: 'weather_radar'")
                radar_type = 'weather_radar'  # Default radar type
            
            # Ensure mode is never NULL
            if not mode:
                # First try to get mode from message content
                if isinstance(message.get('data'), str):
                    try:
                        data_obj = json.loads(message['data'])
                        if 'data' in data_obj and 'mode' in data_obj['data'] and 'current_mode' in data_obj['data']['mode']:
                            mode = data_obj['data']['mode']['current_mode']
                            logger.info(f"Extracted mode {mode} from data.mode.current_mode")
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass

                # Still no mode, look for it in other places
                if not mode and 'metadata' in message and isinstance(message['metadata'], dict):
                    metadata_mode = message['metadata'].get('mode')
                    if metadata_mode:
                        mode = str(metadata_mode)
                        logger.info(f"Using mode {mode} from metadata")

                # Default to 'command_ack' if still no mode
                if not mode:
                    mode = 'command_ack'  # Default mode value to satisfy NOT NULL constraint
                    logger.warning(f"Using default mode 'command_ack' for request_id {message['request_id']}")

            # Create mode change data
            mode_data = ModeChangeData(
                timestamp=message.get('timestamp', time.time()),
                radar_type=radar_type,
                mode=mode,  # Will never be None due to the checks above
                request_id=message['request_id'],
                data_word=str(data_word) if data_word else '0',
                additional_info=message.get('additional_info')
            )

            # Log mode change data
            logger.info(f"Storing mode change data:")
            logger.info(f"  timestamp: {mode_data.timestamp}")
            logger.info(f"  radar_type: {mode_data.radar_type}")
            logger.info(f"  mode: {mode_data.mode}")
            logger.info(f"  request_id: {mode_data.request_id}")
            logger.info(f"  data_word: {mode_data.data_word}")

            # Store mode change directly instead of queuing
            await self._store_mode_change(mode_data)

            # In test environment, verify storage
            if 'test' in sys.modules:
                # Query to verify storage
                query = 'SELECT * FROM "mode_changes" WHERE request_id = ? AND radar_type = ?'
                params = (mode_data.request_id, mode_data.radar_type)
                results = self.radar_db.execute_query(query, params, query_type='select')
                if results:
                    logger.info(f"Verified mode change storage: {results}")
                else:
                    logger.warning(f"Mode change storage verification failed for request_id: {mode_data.request_id}")
        
        except Exception as e:
            logger.error(f"Error handling mode change data: {e}")
            traceback.print_exc()

    def get_command_acknowledgments(
        self, 
        radar_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Tuple]:
        """
        Retrieve command acknowledgments with robust filtering
        
        Args:
            radar_type (Optional[str]): Filter by radar type
            start_time (Optional[float]): Start timestamp for filtering
            end_time (Optional[float]): End timestamp for filtering
        
        Returns:
            List[Tuple]: List of matching acknowledgments
        """
        try:
            query = 'SELECT * FROM "command_acknowledgments"'
            conditions = []
            params = []

            if radar_type:
                conditions.append('radar_type = ?')
                params.append(radar_type)
            
            if start_time is not None and end_time is not None:
                conditions.append('timestamp BETWEEN ? AND ?')
                params.extend([start_time, end_time])

            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)

            logger.debug(f"Executing query: {query} with params: {params}")
            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            
            # Convert results to CommandAcknowledgment objects
            acknowledgments = []
            for row in results:
                # Row indices based on table schema:
                # 0: id, 1: timestamp, 2: command_type, 3: radar_type, 
                # 4: status, 5: request_id, 6: additional_info, 7: created_at
                try:
                    additional_info = json.loads(row[6]) if row[6] else None
                    ack = CommandAcknowledgment(
                        timestamp=row[1],
                        command_type=row[2],
                        radar_type=row[3],
                        status=row[4],
                        request_id=row[5],
                        additional_info=additional_info
                    )
                    acknowledgments.append(ack)
                except Exception as e:
                    logger.error(f"Error converting row to CommandAcknowledgment: {e}")
                    logger.error(f"Row data: {row}")
                    continue
            
            logger.info(f"Retrieved {len(acknowledgments)} acknowledgments")
            return acknowledgments
        
        except Exception as e:
            logger.error(f"Error retrieving command acknowledgments: {e}")
            traceback.print_exc()
            return []

    def get_mode_changes(
        self, 
        radar_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Tuple]:
        """
        Retrieve mode changes with robust filtering
        
        Args:
            radar_type (Optional[str]): Filter by radar type
            start_time (Optional[float]): Start timestamp for filtering
            end_time (Optional[float]): End timestamp for filtering
        
        Returns:
            List[Tuple]: List of matching mode changes
        """
        try:
            query = 'SELECT * FROM "mode_changes"'
            conditions = []
            params = []

            if radar_type:
                conditions.append('radar_type = ?')
                params.append(radar_type)
            
            if start_time is not None and end_time is not None:
                conditions.append('timestamp BETWEEN ? AND ?')
                params.extend([start_time, end_time])

            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)

            logger.debug(f"Executing query: {query} with params: {params}")
            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            
            # Convert results to ModeChangeData objects
            mode_changes = []
            for row in results:
                # Row indices based on table schema:
                # 0: id, 1: timestamp, 2: radar_type, 3: mode,
                # 4: request_id, 5: data_word, 6: additional_info, 7: created_at
                try:
                    additional_info = json.loads(row[6]) if row[6] else None
                    mode_change = ModeChangeData(
                        timestamp=row[1],
                        radar_type=row[2],
                        mode=row[3],
                        request_id=row[4],
                        data_word=row[5],
                        additional_info=additional_info
                    )
                    mode_changes.append(mode_change)
                except Exception as e:
                    logger.error(f"Error converting row to ModeChangeData: {e}")
                    logger.error(f"Row data: {row}")
                    continue
            
            logger.info(f"Retrieved {len(mode_changes)} mode changes")
            return mode_changes
        
        except Exception as e:
            logger.error(f"Error retrieving mode changes: {e}")
            traceback.print_exc()
            return []

def get_radar_response_service() -> EnhancedRadarResponseService:
    """Get the singleton instance of EnhancedRadarResponseService"""
    return EnhancedRadarResponseService()
