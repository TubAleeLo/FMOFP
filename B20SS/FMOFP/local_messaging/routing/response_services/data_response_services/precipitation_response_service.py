"""
Precipitation response service for handling precipitation data

Provides:
1. Async queue processing of precipitation data
2. Integration with data handler for storage
3. Error handling and logging
4. Direct display notification without using MessageRoutingService
"""

import threading
import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData
from FMOFP.Utils.common.message_format_adapter import get_message_format_adapter
from ...handlers.precipitation_data_handler import PrecipitationDataHandler

logger = get_logger()

class PrecipitationResponseService:
    """Handles precipitation data processing and storage"""
    _instance = None
    _initialized = False

    _lock = threading.Lock()

    def __new__(cls, radar_db=None):
        # Double-checked locking to prevent a TOCTOU race where multiple
        # threads concurrently pass the `cls._instance is None` check
        # before either assignment lands, producing duplicate instances.
        # Same vulnerability class live-reproduced and fixed in
        # storage/DBM.py's DatabaseManager.__new__ this round.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PrecipitationResponseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, radar_db=None):
        """Initialize with radar database connection"""
        if not self._initialized and radar_db is not None:
            self.data_handler = PrecipitationDataHandler(radar_db)
            self._precipitation_queue = None
            self._event_loop = None
            self._processing = False
            self._task = None

            # Get routing service for message handling
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.routing_service = get_message_routing_service()

            self._initialized = True
            logger.info("PrecipitationResponseService initialized")

    async def initialize(self):
        """Complete async initialization of the service."""
        if self._initialized:
            logger.info("PrecipitationResponseService already initialized")
            return

        try:
            # Mark as initialized
            self._initialized = True
            logger.info("PrecipitationResponseService fully initialized")

        except Exception as e:
            logger.error(f"Error during PrecipitationResponseService initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to initialize PrecipitationResponseService") from e

    async def start(self, event_loop=None) -> bool:
        """
        Start the precipitation response service

        Args:
            event_loop: Optional event loop to use for async operations
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                logger.info("Precipitation service not initialized, initializing now...")
                await self.initialize()

            # Get current event loop if none provided
            if event_loop is None:
                try:
                    event_loop = asyncio.get_running_loop()
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Using existing event loop: {event_loop}")
                except RuntimeError:
                    event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(event_loop)
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Created new event loop: {event_loop}")

            self._event_loop = event_loop
            self._precipitation_queue = asyncio.Queue()  # Create queue with current event loop
            self._processing = True

            # Create and start the queue processing task
            logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Creating queue processing task")
            self._task = self._event_loop.create_task(self._process_precipitation_queue())
            self._task.add_done_callback(self._handle_task_done)

            # Log detailed information about the task
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Task created: {self._task}")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Task running: {not self._task.done()}")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Event loop running: {self._event_loop.is_running()}")

            logger.info("Precipitation response service started")
            return True
        except Exception as e:
            logger.error(f"Error starting precipitation response service: {e}")
            traceback.print_exc()
            raise

    def _handle_task_done(self, task):
        """Handle completion of the processing task"""
        try:
            # Check if task failed with an exception
            if task.exception():
                logger.error(f"Precipitation processing task failed: {task.exception()}")
                # Restart the task if processing should continue
                if self._processing:
                    logger.info("Restarting precipitation processing task")
                    self._task = self._event_loop.create_task(self._process_precipitation_queue())
                    self._task.add_done_callback(self._handle_task_done)
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            traceback.print_exc()

    async def stop(self):
        """Stop the precipitation response service"""
        try:
            logger.info("Stopping precipitation response service")
            self._processing = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Precipitation response service stopped")
        except Exception as e:
            logger.error(f"Error stopping precipitation response service: {e}")
            traceback.print_exc()

    async def _process_precipitation_queue(self):
        """Process precipitation data queue with robust error handling"""
        logger.info("Starting precipitation queue processor")
        try:
            while self._processing:
                try:
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Waiting for precipitation data...")
                    precipitation_data = await self._precipitation_queue.get()
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Processing precipitation data: {precipitation_data}")
                    try:
                        # Store data synchronously
                        success = self.data_handler.store_precipitation_data(precipitation_data)
                        if success:
                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation data processed and stored: {precipitation_data.request_id}")
                            # Only mark task done if storage was successful
                            self._precipitation_queue.task_done()
                        else:
                            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed to store precipitation data: {precipitation_data.request_id}")
                            # Log failure details
                            logger.error(f"Failed data: {precipitation_data}")
                            # Put the data back in queue for retry
                            await self._precipitation_queue.put(precipitation_data)
                    except Exception as store_error:
                        logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error storing precipitation data: {store_error}")
                        logger.error(traceback.format_exc())
                        # Add to failure log
                        with open('precipitation_failures.log', 'a') as f:
                            f.write(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed Precipitation Data: {precipitation_data}\nError: {store_error}\n")
                        # Put the data back in queue for retry
                        await self._precipitation_queue.put(precipitation_data)
                except asyncio.CancelledError:
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation queue processor cancelled")
                    break
                except Exception as e:
                    logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation queue processing error: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Brief pause before retrying
        except Exception as e:
            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Fatal error in precipitation queue processor: {e}")
            logger.error(traceback.format_exc())
            raise

    def _retrieve_precipitation_data_from_db(self, request_id: str) -> List[PrecipitationData]:
        """
        Retrieve precipitation data directly from database by request ID.
        This is called when processing precipitation data to verify it was stored.

        Args:
            request_id: The unique request ID to retrieve data for

        Returns:
            List of PrecipitationData objects, or empty list if no data found
        """
        try:
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Retrieving precipitation data from DB for request ID: {request_id}")

            # Verify data handler exists
            if not hasattr(self, 'data_handler') or self.data_handler is None:
                logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No data handler available for DB query")
                return []

            # Verify database connection
            if not hasattr(self.data_handler, 'radar_db') or self.data_handler.radar_db is None:
                logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No database connection available")
                return []

            radar_db = self.data_handler.radar_db

            # Verify table exists
            try:
                table_exists = radar_db.table_exists('precipitation_data')
                if not table_exists:
                    logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation data table does not exist in DB")
                    # Try to create the table using the handler
                    if hasattr(self, 'data_handler') and self.data_handler is not None:
                        logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Attempting to create table using handler")
                        if self.data_handler._init_database_table():
                            logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Successfully created precipitation_data table")
                            # Table should exist now, continue with query
                        else:
                            logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed to create precipitation_data table")
                            return []
                    else:
                        return []
            except Exception as e:
                logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error checking table existence: {e}")
                return []

            # Query database for data with this request ID - use more comprehensive query
            try:
                # First try exact match
                query = """
                        SELECT * FROM precipitation_data
                        WHERE request_id = ?
                        ORDER BY timestamp DESC
                        """

                results = radar_db.execute_query(
                    query,
                    (request_id,),
                    query_type='select',
                    manage_transaction=True
                )

                # If no exact match, try checking if this is a child request ID
                if not results or len(results) == 0:
                    logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No exact match for request_id {request_id}, trying parent/child pattern")

                    # Try as parent with child pattern
                    child_query = """
                            SELECT * FROM precipitation_data
                            WHERE request_id LIKE ?
                            ORDER BY timestamp DESC
                            """

                    results = radar_db.execute_query(
                        child_query,
                        (f"{request_id}_%",),
                        query_type='select',
                        manage_transaction=True
                    )

                    if results and len(results) > 0:
                        logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found {len(results)} child records for parent request_id {request_id}")

                if not results or len(results) == 0:
                    logger.warning(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No precipitation data found in DB for request ID {request_id}")
                    return []

                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Retrieved {len(results)} records from DB")

                # Get column names for mapping
                columns = []
                with radar_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(precipitation_data)")
                    columns = [col[1] for col in cursor.fetchall()]

                # Convert to PrecipitationData objects
                precipitation_data_list = []
                for row in results:
                    # Convert row to dictionary
                    row_dict = dict(zip(columns, row))

                    try:
                        # Create PrecipitationData object
                        precip_obj = PrecipitationData(
                            position=(row_dict['position_x'], row_dict['position_y']),
                            type=row_dict.get('precip_type', row_dict.get('type', 'rain')),
                            rate=float(row_dict['rate']),
                            intensity=float(row_dict['intensity']),
                            show_values=bool(int(row_dict.get('show_values', 0)))
                        )
                        precip_obj.request_id = row_dict['request_id']
                        precip_obj.timestamp = float(row_dict['timestamp'])

                        # Parse additional info if available
                        if 'additional_info' in row_dict and row_dict['additional_info']:
                            import json
                            try:
                                precip_obj.additional_info = json.loads(row_dict['additional_info'])
                            except json.JSONDecodeError:
                                precip_obj.additional_info = {}
                        else:
                            precip_obj.additional_info = {}

                        precipitation_data_list.append(precip_obj)

                    except Exception as e:
                        logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error converting DB row to PrecipitationData: {e}")
                        continue

                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Converted {len(precipitation_data_list)} DB rows to PrecipitationData objects")
                return precipitation_data_list

            except Exception as e:
                logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Database query error: {e}")
                logger.error(traceback.format_exc())
                return []

        except Exception as e:
            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error retrieving precipitation data from DB: {e}")
            logger.error(traceback.format_exc())
            return []

    async def get_weather_data_components(self, mode: str, current_precipitation: Optional[PrecipitationData] = None, should_request_from_radar: bool = True) -> Tuple[List[Any], List[Any], List[Any]]:
        """
        Retrieve all weather data components for the current radar mode

        Args:
            mode: Current radar mode (e.g., 'SURVEILLANCE')
            current_precipitation: Optional current precipitation data being processed

        Returns:
            tuple: (precipitation_data, vil_data, cell_data)
            Each component is a list of the respective data objects
        """
        try:
            # Get database connection
            if not hasattr(self, 'data_handler') or not self.data_handler:
                from FMOFP.storage.DBM import DatabaseManager
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')
                self.data_handler = PrecipitationDataHandler(radar_db)
                logger.info("[LOC_WX_DATA_COMPONENTS] Created new data_handler")
            else:
                radar_db = self.data_handler.radar_db
                logger.info("[LOC_WX_DATA_COMPONENTS] Using existing data_handler")

            # Pre-initialize result lists
            precip_data = []
            vil_data = []
            cell_data = []

            # First check if tables exist before attempting to query
            tables_exist = {
                'precipitation_data': False,
                'vil_data': False,
                'storm_cell_data': False
            }

            # Add high visibility logging for tracking precipitation table existence
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Checking tables: {tables_exist}")

            # Initialize variables for data freshness check
            precip_results = None
            data_is_fresh = False
            max_data_age = 10.0  # Consider data older than 10 seconds as stale
            current_time = time.time()

            # Verify which tables exist in the database
            for table in tables_exist.keys():
                try:
                    exists = radar_db.table_exists(table)
                    tables_exist[table] = exists
                    logger.info(f"[LOC_WX_DATA_COMPONENTS] Table {table} exists: {exists}")
                except Exception as e:
                    logger.warning(f"[LOC_WX_DATA_COMPONENTS] Error checking table {table}: {e}")

            # Check if we need to request from radar by fetching existing data first
            if tables_exist['precipitation_data']:
                try:
                    # Query precipitation data with timestamp for freshness check
                    # Calculate the staleness threshold timestamp
                    current_time = time.time()
                    staleness_threshold_time = current_time - max_data_age

                    # Query with staleness filter to only retrieve fresh data
                    precip_results = radar_db.execute_query(
                        """
                        SELECT * FROM precipitation_data
                        WHERE timestamp > ?
                        ORDER BY timestamp DESC
                        LIMIT 10
                        """,
                        (staleness_threshold_time,),
                        query_type='select'
                    )
                    logger.info(f"[LOC_WX_DATA_COMPONENTS] Retrieved {len(precip_results) if precip_results else 0} initial precipitation records")

                    # Check if we have data and if it's fresh enough
                    if precip_results and len(precip_results) > 0:
                        # Get column indexes
                        with radar_db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("PRAGMA table_info(precipitation_data)")
                            columns = [col[1] for col in cursor.fetchall()]

                        # Get timestamp index
                        timestamp_index = columns.index('timestamp')

                        # Check latest data age
                        latest_timestamp = float(precip_results[0][timestamp_index])
                        data_age = current_time - latest_timestamp
                        logger.info(f"[LOC_WX_DATA_COMPONENTS] Latest data age: {data_age:.2f} seconds")

                        # Determine if data is fresh enough
                        data_is_fresh = data_age < max_data_age
                        logger.info(f"[LOC_WX_DATA_COMPONENTS] Data is {'fresh' if data_is_fresh else 'stale'}")
                except Exception as e:
                    logger.warning(f"[LOC_WX_DATA_COMPONENTS] Error retrieving initial precipitation data: {e}")
                    precip_results = None
                    data_is_fresh = False

            # If should_request_from_radar is True and data is not fresh, send a request to the weather radar
            if should_request_from_radar and (not precip_results or not data_is_fresh):
                logger.info(f"[LOC_WX_DATA_COMPONENTS] Need to request fresh data from radar: data_exists={precip_results is not None}, data_is_fresh={data_is_fresh}")
                logger.info("[LOC_WX_DATA_COMPONENTS] No precipitation data in DB, sending request to weather radar")
                try:
                    # Get radar message handler
                    from FMOFP.local_messaging.routing.handlers.system_message_handlers.RadarMessageHandler import get_radar_message_handler
                    radar_handler = get_radar_message_handler()

                    if radar_handler:
                        # Import the request message type
                        from FMOFP.local_messaging.messageConfigurations.weather_radar_data import weather_radarPrecipitationRequest
                        import uuid

                        # Create request
                        precip_request = weather_radarPrecipitationRequest(
                            message_header="data_request",
                            sending_system="precipitation_response_service",
                            destination="weather_radar",
                            request_uuid=str(uuid.uuid4()),
                            scan_parameters={"mode": mode, "data_type": "precipitation"}
                        )

                        # Log that we're sending the request to radar
                        logger.info("[LOC_WX_DATA_COMPONENTS] Sending precipitation data request to weather radar")

                        # Send the request to weather radar
                        request_id = await radar_handler.send_request(
                            "weather_radar",  # Target system
                            "data",          # Command type
                            precip_request      # Send request object
                        )

                        logger.info(f"[LOC_WX_DATA_COMPONENTS] Precipitation data request sent to radar with ID: {request_id}")

                        # Add a delay to allow radar to respond
                        await asyncio.sleep(2.0)

                        # Try querying again after radar response
                        try:
                            precip_results = radar_db.execute_query(
                                """
                                SELECT * FROM precipitation_data
                                ORDER BY timestamp DESC
                                LIMIT 10
                                """,
                                (),
                                query_type='select'
                            )
                            logger.info(f"[LOC_WX_DATA_COMPONENTS] Retrieved {len(precip_results) if precip_results else 0} precipitation records after radar request")
                        except Exception as e:
                            logger.error(f"[LOC_WX_DATA_COMPONENTS] Error retrieving precipitation data after radar request: {e}")
                            precip_results = None
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error sending request to radar: {e}")
                    logger.error(traceback.format_exc())

            # If current_precipitation is provided, always include it in the results
            if current_precipitation:
                logger.info("[LOC_WX_DATA_COMPONENTS] Adding current precipitation data to results")
                precip_data.append(current_precipitation)

            # Fetch precipitation data if table exists
            if tables_exist['precipitation_data']:
                try:
                    precip_results = radar_db.execute_query(
                        """
                        SELECT * FROM precipitation_data
                        ORDER BY timestamp DESC
                        LIMIT 10
                        """,
                        (),
                        query_type='select'
                    )
                    logger.info(f"[LOC_WX_DATA_COMPONENTS] Retrieved {len(precip_results) if precip_results else 0} precipitation records")
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error retrieving precipitation data: {e}")
                    precip_results = None
            else:
                logger.warning("[LOC_WX_DATA_COMPONENTS] Precipitation data table does not exist, skipping query")
                precip_results = None

            # Format precipitation data
            if precip_results:
                try:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(precipitation_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    for row in precip_results:
                        try:
                            # Convert row to dictionary
                            precip_dict = dict(zip(columns, row))

                            # Create PrecipitationData object
                            from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData
                            precip_obj = PrecipitationData(
                                position=(precip_dict['position_x'], precip_dict['position_y']),
                                type=precip_dict.get('precip_type', precip_dict.get('type', 'rain')),
                                rate=float(precip_dict['rate']),
                                intensity=float(precip_dict['intensity']),
                                show_values=bool(int(precip_dict.get('show_values', 0)))
                            )
                            precip_obj.request_id = precip_dict['request_id']
                            precip_obj.timestamp = float(precip_dict['timestamp'])

                            # Only add if not already in list (avoid duplication with current_precipitation)
                            if current_precipitation and precip_obj.request_id == current_precipitation.request_id:
                                continue

                            # Add to list
                            precip_data.append(precip_obj)
                        except Exception as e:
                            logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing precipitation row: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing precipitation results: {e}")

            # Fetch VIL data if table exists
            if tables_exist['vil_data']:
                try:
                    # Calculate the staleness threshold timestamp for VIL data
                    current_time = time.time()
                    staleness_threshold_time = current_time - max_data_age

                    # Query with staleness filter to only retrieve fresh VIL data
                    vil_results = radar_db.execute_query(
                        """
                        SELECT * FROM vil_data
                        WHERE timestamp > ?
                        ORDER BY timestamp DESC
                        LIMIT 10
                        """,
                        (staleness_threshold_time,),
                        query_type='select'
                    )
                    logger.info(f"[LOC_WX_DATA_COMPONENTS] Retrieved {len(vil_results) if vil_results else 0} VIL records")
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error retrieving VIL data: {e}")
                    vil_results = None
            else:
                logger.error("[LOC_WX_DATA_COMPONENTS] VIL data table does not exist, skipping query")
                vil_results = None

            # Format VIL data
            if vil_results:
                try:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(vil_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    for row in vil_results:
                        try:
                            # Convert row to dictionary
                            vil_dict = dict(zip(columns, row))

                            # Create WeatherRadarVILData object
                            from FMOFP.local_messaging.messageConfigurations.weather_radar_data import WeatherRadarVILData
                            vil_obj = WeatherRadarVILData(
                                position=(vil_dict['position_x'], vil_dict['position_y']),
                                value=float(vil_dict['value']),
                                layer_count=int(vil_dict['layer_count']),
                                intensity=float(vil_dict['intensity']),
                                show_values=bool(int(vil_dict.get('show_values', 0)))
                            )
                            vil_obj.request_id = vil_dict['request_id']
                            vil_obj.timestamp = float(vil_dict['timestamp'])

                            # Add to list
                            vil_data.append(vil_obj)
                        except Exception as e:
                            logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing VIL row: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing VIL results: {e}")


            # Fetch storm cell data if table exists
            if tables_exist['storm_cell_data']:
                try:
                    # Calculate the staleness threshold timestamp for storm cell data
                    current_time = time.time()
                    staleness_threshold_time = current_time - max_data_age

                    # Query with staleness filter to only retrieve fresh storm cell data
                    cell_results = radar_db.execute_query(
                        """
                        SELECT * FROM storm_cell_data
                        WHERE timestamp > ?
                        ORDER BY timestamp DESC
                        LIMIT 10
                        """,
                        (staleness_threshold_time,),
                        query_type='select'
                    )
                    logger.info(f"[LOC_WX_DATA_COMPONENTS] Retrieved {len(cell_results) if cell_results else 0} storm cell records")
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error retrieving cell data: {e}")
                    cell_results = None
            else:
                logger.warning("[LOC_WX_DATA_COMPONENTS] Storm cell data table does not exist, skipping query")
                cell_results = None

            # Format cell data
            if cell_results:
                try:
                    # Get column names
                    columns = []
                    with radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(storm_cell_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    for row in cell_results:
                        try:
                            # Convert row to dictionary
                            cell_dict = dict(zip(columns, row))

                            # Create StormCellData object
                            from FMOFP.local_messaging.messageConfigurations.weather_radar_data import StormCellData
                            cell_obj = StormCellData(
                                x=float(cell_dict['position_x']),
                                y=float(cell_dict['position_y']),
                                intensity=float(cell_dict['intensity']),
                                show_values=bool(int(cell_dict.get('show_values', 0)))
                            )
                            cell_obj.request_id = cell_dict['request_id']
                            cell_obj.timestamp = float(cell_dict['timestamp'])

                            # Add to list
                            cell_data.append(cell_obj)
                        except Exception as e:
                            logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing cell row: {e}")
                            continue
                except Exception as e:
                    logger.error(f"[LOC_WX_DATA_COMPONENTS] Error processing cell results: {e}")
            else:
                # If no storm cell data in database
                logger.info("[LOC_WX_DATA_COMPONENTS] No storm cell data found in database")
                pass


            # Log final results
            logger.info(f"[LOC_WX_DATA_COMPONENTS] Returning data components:")
            logger.info(f"[LOC_WX_DATA_COMPONENTS] - Precipitation: {len(precip_data)} items")
            logger.info(f"[LOC_WX_DATA_COMPONENTS] - VIL: {len(vil_data)} items")
            logger.info(f"[LOC_WX_DATA_COMPONENTS] - Storm cells: {len(cell_data)} items")

            # Return all data components separately
            return precip_data, vil_data, cell_data

        except Exception as e:
            logger.error(f"[LOC_WX_DATA_COMPONENTS] Error retrieving weather data components: {e}")
            logger.error(traceback.format_exc())

            # In case of error, always ensure we return the current precipitation data if provided
            if current_precipitation:
                return [current_precipitation], [], []
            else:
                return [], [], []

    async def handle_precipitation_data(self, message: Dict[str, Any]):
        """
        Handle precipitation data from weather radar

        Args:
            message: Dictionary containing precipitation data
        """
        try:
            # Check if this message has already been processed to prevent loops
            if message.get('metadata', {}).get('_processed_by_precipitation_service', False):
                logger.warning("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected loop - message already processed by precipitation service")
                return

            # Add loop prevention flag
            if 'metadata' not in message:
                message['metadata'] = {}
            message['metadata']['_processed_by_precipitation_service'] = True

            # Log detailed message structure with exact test pattern
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Handling precipitation data message")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation response service handling data")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Message keys: {message.keys() if isinstance(message, dict) else 'N/A'}")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation Response Service initialization state: {self._initialized}")

            # Check current display mode from DisplayResponseService
            from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
            display_service = get_display_response_service()
            current_mode = None

            if display_service:
                try:
                    current_mode = await display_service.get_current_display_mode('radar_display')
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Current display mode: {current_mode}")
                except Exception as e:
                    logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error getting display mode: {e}")

            # Only process precipitation data if in SURVEILLANCE mode or mode is unknown (fallback for compatibility)
            if current_mode and current_mode.get('mode') != 'SURVEILLANCE':
                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Skipping precipitation data processing - display not in SURVEILLANCE mode (current: {current_mode.get('mode')})")

                # Send acknowledgment that we received but didn't process the data
                request_id = message.get('request_id')
                if request_id:
                    await self._send_acknowledgment(request_id, True,
                                             f"Precipitation data received but not processed - display in {current_mode.get('mode')} mode")
                return

            # If we reach here, either the mode is SURVEILLANCE or we couldn't determine the mode
            # In either case, we proceed with processing the precipitation data
            if current_mode:
                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Processing precipitation data in {current_mode.get('mode')} mode")
            else:
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Processing precipitation data (mode unknown)")

            # Use message format adapter to help extract fields
            message_adapter = get_message_format_adapter()
            normalized_message = message_adapter.normalize_message(message)
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Normalized message type: {normalized_message['message_type']}")

            # Extract required fields - but still use original message for strict compatibility
            request_id = message.get('request_id')
            if not request_id and isinstance(message, dict):
                # Try to find request_id in other common fields
                for field in ['requestId', 'request_uuid', 'id', 'uuid']:
                    if field in message:
                        request_id = message[field]
                        break

            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted request_id: {request_id}")
            if not request_id:
                logger.warning("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Precipitation data missing request_id")
                return

            # First check if this is a completion message with explicit completion data format
            if (isinstance(message.get('data'), dict) and
                message['data'].get('completion_message') == True and
                message['data'].get('status') == 'success'):
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected completion message with completion_message flag")
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Handling as completion message based on data content")
                await self._send_acknowledgment(request_id, True, "Completion message received")
                return True

            # If we get here, proceed with normal data extraction
            response = message.get('data')
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted response object: {response}")
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Response type: {type(response)}")

            # Check if response is a completion message
            if isinstance(response, dict) and response.get('completion_message') == True:
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected completion message with completion_message flag")
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Handling as completion message based on data content")
                await self._send_acknowledgment(request_id, True, "Completion message received")
                return True

            # Enhanced data extraction with multiple fallback mechanisms
            data = None

            # Check for precipitation data in precipitation_data field (alternative format)
            if not response and 'precipitation_data' in message:
                logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No data field found, checking precipitation_data field")
                response = message.get('precipitation_data')
                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted precipitation data from precipitation_data field: {response}")

            # Log the extracted data for debugging
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted precipitation data from response")

            # Try multiple approaches to extract valid precipitation data
            # Approach 1: Check if response is a list of data words or integers
            if isinstance(response, list):
                # Check if it's a list of integers - this is a special binary encoding format
                if len(response) > 0 and all(isinstance(word, int) for word in response):
                    logger.warning(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found encoded data format: {response}")

                    # Check if this is part of a block transfer
                    is_block_transfer = False
                    sequence_number = None
                    total_sequences = None
                    is_final = False

                    # Look for block transfer metadata in message
                    if 'metadata' in message and isinstance(message['metadata'], dict):
                        # Check for sequence information
                        if 'sequence_number' in message['metadata']:
                            is_block_transfer = True
                            sequence_number = message['metadata'].get('sequence_number', 1)
                            total_sequences = message['metadata'].get('total_sequences', 1)
                            is_final = message['metadata'].get('is_final', False)

                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected block transfer: sequence {sequence_number}/{total_sequences}, final={is_final}")

                    # Log the exact data being processed
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Processing encoded data with {len(response)} words: {response}")

                    # If this is a block transfer, use the block transfer manager
                    if is_block_transfer:
                        try:
                            # Import and get block transfer manager
                            from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
                            transfer_manager = get_block_transfer_manager()

                            # Register this block with the manager
                            transfer_complete = transfer_manager.register_block(
                                request_id, sequence_number, total_sequences, is_final, response
                            )

                            # If transfer is complete, process all data
                            if transfer_complete:
                                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Block transfer complete for request ID: {request_id}")

                                # Get assembled data
                                assembled_data = transfer_manager.get_assembled_data(request_id)

                                if assembled_data:
                                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Processing assembled data with {len(assembled_data)} words")

                                    # Process the assembled data
                                    success = self.data_handler.extract_and_store_binary_data(request_id, assembled_data)
                                else:
                                    logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed to get assembled data for complete transfer")
                                    success = False
                            else:
                                # Transfer not yet complete, acknowledge receipt
                                # Get status for logging
                                status = transfer_manager.get_transfer_status(request_id)
                                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Block transfer in progress: {status['received_blocks']}/{status['total_blocks']} blocks received ({status['percent_complete']:.1f}% complete)")

                                # Send acknowledgment for this block
                                await self._send_acknowledgment(
                                    request_id,
                                    True,
                                    f"Block {sequence_number}/{total_sequences} received and stored. Transfer {status['percent_complete']:.1f}% complete."
                                )
                                # Return early - we'll handle the complete data when the final block arrives
                                return
                        except Exception as e:
                            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error handling block transfer: {e}")
                            logger.error(traceback.format_exc())
                            await self._send_acknowledgment(
                                request_id,
                                False,
                                f"Error handling block transfer: {str(e)}"
                            )
                            return False
                    else:
                        # Not a block transfer, process with standard handler
                        try:
                            # Use the dedicated binary data handler
                            if not hasattr(self, 'data_handler') or self.data_handler is None:
                                logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] No data handler available for binary decoding")
                                return False

                            # Log statement to ensure data handler is properly initialized
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Data handler: {self.data_handler} for binary data processing")

                            # Process the binary data directly using the improved handler - ensure we have a valid response list
                            if not response or not isinstance(response, list):
                                logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Invalid response format: {type(response)}")
                                return False

                            # Force instantiate data handler if it's None, with error handling
                            if not self.data_handler:
                                from FMOFP.storage.DBM import DatabaseManager
                                logger.debug("[PRECIPITATION_FLOW_DEBUG] Re-initializing data_handler - was None")
                                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                                radar_db = db_manager.get_system_db('radar_management')
                                from FMOFP.local_messaging.routing.handlers.precipitation_data_handler import PrecipitationDataHandler
                                self.data_handler = PrecipitationDataHandler(radar_db)

                            # Process the binary data directly using the improved handler with detailed logging
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Extracting and storing binary data: {response}")
                            success = self.data_handler.extract_and_store_binary_data(request_id, response)
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Binary data extraction result: {success}")
                        except Exception as e:
                            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error processing binary data: {e}")
                            logger.error(traceback.format_exc())
                            return False

                        # Process result for successful extraction (either block transfer or direct)
                        if success:
                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Successfully extracted and stored binary data")

                            # Wait for database transaction to complete (avoid race condition)
                            await asyncio.sleep(0.2)

                            # Log DB retrieval attempt - changed level from error to info
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Attempting to verify data in database for request_id: {request_id}")

                            # Now we should get all the data points, not just a single record
                            # Use retry mechanism for database query
                            max_retries = 3
                            retry_delay = 0.2
                            precip_results = None

                            # First check for child records (individual precipitation points)
                            for retry_count in range(max_retries):
                                try:
                                    from FMOFP.storage.DBM import DatabaseManager
                                    db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                                    radar_db = db_manager.get_system_db('radar_management')

                                    # Look for child records using parent request ID pattern
                                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Querying for child records (attempt {retry_count+1})")
                                    child_results = radar_db.execute_query(
                                        """
                                        SELECT * FROM precipitation_data
                                        WHERE request_id LIKE ?
                                        ORDER BY timestamp DESC
                                        """,
                                        (f"{request_id}_%",),
                                        query_type='select',
                                        manage_transaction=True
                                    )

                                    if child_results and len(child_results) > 0:
                                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Successfully found {len(child_results)} child records")
                                        precip_results = child_results
                                        break
                                    else:
                                        # Fall back to looking for the parent record
                                        parent_results = radar_db.execute_query(
                                            """
                                            SELECT * FROM precipitation_data
                                            WHERE request_id = ?
                                            """,
                                            (request_id,),
                                            query_type='select',
                                            manage_transaction=True
                                        )

                                        if parent_results and len(parent_results) > 0:
                                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Found parent collection record")

                                            # Try to parse additional_info to get child records
                                            try:
                                                # Get column names
                                                with radar_db.get_connection() as conn:
                                                    cursor = conn.cursor()
                                                    cursor.execute("PRAGMA table_info(precipitation_data)")
                                                    columns = [col[1] for col in cursor.fetchall()]

                                                # Get additional_info from parent record
                                                row_dict = dict(zip(columns, parent_results[0]))
                                                if row_dict.get('additional_info'):
                                                    import json
                                                    additional_info = json.loads(row_dict['additional_info'])

                                                    # Check if this is a collection record with child IDs
                                                    if additional_info.get('is_collection_record') and additional_info.get('object_ids'):
                                                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Found collection record with {len(additional_info['object_ids'])} child objects")

                                                        # Query for all child records
                                                        child_ids = ', '.join([f"'{id}'" for id in additional_info['object_ids']])
                                                        query = f"""
                                                        SELECT * FROM precipitation_data
                                                        WHERE request_id IN ({child_ids})
                                                        """
                                                        child_results = radar_db.execute_query(query, (), query_type='select')

                                                        if child_results and len(child_results) > 0:
                                                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Retrieved {len(child_results)} child records from collection")
                                                            precip_results = child_results
                                                            break
                                            except Exception as parse_error:
                                                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Error parsing collection: {parse_error}")

                                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] No precipitation data found yet, retrying in {retry_delay}s")
                                        if retry_count < max_retries - 1:
                                            await asyncio.sleep(retry_delay)
                                            retry_delay *= 2  # Exponential backoff
                                except Exception as query_error:
                                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Query error on attempt {retry_count+1}: {query_error}")
                                    if retry_count < max_retries - 1:
                                        await asyncio.sleep(retry_delay)
                                        retry_delay *= 2  # Exponential backoff

                            if precip_results and len(precip_results) > 0:
                                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Successfully verified {len(precip_results)} precipitation records in DB for request ID {request_id}")

                                # Get column names
                                with radar_db.get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("PRAGMA table_info(precipitation_data)")
                                    columns = [col[1] for col in cursor.fetchall()]

                                # Convert first row to dictionary
                                precip_dict = dict(zip(columns, precip_results[0]))

                                # Create PrecipitationData object from DB record
                                data = PrecipitationData(
                                    position=(float(precip_dict.get('position_x', 0)), float(precip_dict.get('position_y', 0))),
                                    type=precip_dict.get('precip_type', precip_dict.get('type', 'rain')),
                                    rate=float(precip_dict.get('rate', 0.0)),
                                    intensity=float(precip_dict.get('intensity', 0.0)),
                                    show_values=bool(int(precip_dict.get('show_values', 1)))
                                )
                                data.request_id = request_id
                                data.timestamp = float(precip_dict.get('timestamp', time.time()))

                                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Created precipitation data from DB record: {data.__dict__}")
                                return data
                            else:
                                logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Verification failed: No precipitation data found in DB for request ID {request_id}")
                                return False
                        else:
                            logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed to extract and store binary data")
                            return False

                # Original handlers for string or object lists
                if len(response) == 2 and all(isinstance(word, str) for word in response):
                    try:
                        # Use PrecipitationData's from_data_words method if it exists
                        if hasattr(PrecipitationData, 'from_data_words'):
                            data = PrecipitationData.from_data_words(response)
                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Parsed precipitation data from words: {data.__dict__}")
                    except (ValueError, IndexError, AttributeError) as e:
                        logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Error parsing data words: {e}")
                        # Don't return yet, try other approaches
                elif len(response) > 0 and hasattr(response[0], 'position'):
                    # Process list of precipitation data objects directly
                    # Instead of just using the first item, return the entire list
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found list of {len(response)} precipitation data objects")
                    # Process all precipitation data objects
                    precip_data_list = []
                    for precip_item in response:
                        if hasattr(precip_item, 'position'):
                            precip_data_list.append(precip_item)

                    if precip_data_list:
                        # Store all precipitation data objects, not just the first one
                        for idx, precip_item in enumerate(precip_data_list):
                            # Create a new ID for each item to prevent conflicts
                            item_request_id = f"{request_id}_{idx+1}" if idx > 0 else request_id
                            precip_item.request_id = item_request_id
                            # Store each precipitation data object
                            await self._store_precipitation_data(precip_item)

                        # Return success, don't continue processing
                        await self._send_acknowledgment(request_id, True, f"Processed {len(precip_data_list)} precipitation data objects")
                        return True

                    # If no valid precipitation data objects were found, continue with first item for backward compatibility
                    data = response[0]
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Using first item from precipitation data list for compatibility")

            # Approach 2: Check if response has precipitation_data attribute
            if not data and hasattr(response, 'precipitation_data'):
                if isinstance(response.precipitation_data, list) and len(response.precipitation_data) > 0:
                    data = response.precipitation_data[0]
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted precipitation data from response.precipitation_data list")
                else:
                    data = response.precipitation_data
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Extracted precipitation data from response.precipitation_data attribute")

            # Approach 3: Check if response is a PrecipitationData object
            if not data and isinstance(response, PrecipitationData):
                data = response
                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Using response directly as PrecipitationData")

                # If we haven't found valid data at this point, check if this is a completion message
                if not data:
                    # Check for completion message pattern in various locations
                    is_completion_message = False

                    # Check in message type
                    if 'message_type' in message and 'completion' in str(message['message_type']).lower():
                        is_completion_message = True

                    # Check in command type
                    elif 'command_type' in message and 'completion' in str(message['command_type']).lower():
                        is_completion_message = True

                    # Check in data for completion indicator
                    elif isinstance(message.get('data'), dict) and message['data'].get('completion_message'):
                        is_completion_message = True

                    # Check in metadata for completion flag
                    elif message.get('metadata', {}).get('precipitation_completion'):
                        is_completion_message = True

                    # Check for data even in "completion" messages
                    data_in_message = False

                    # Look for top-level command_type inconsistency
                    command_type_mismatch = False
                    if isinstance(message, dict):
                        top_command_type = message.get('command_type', '')
                        metadata = message.get('metadata', {})
                        if isinstance(metadata, dict):
                            metadata_command_type = metadata.get('command_type', '')
                            if top_command_type == 'precipitation_data' and 'completion' in metadata_command_type.lower():
                                command_type_mismatch = True
                                logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected command_type mismatch: top='{top_command_type}', metadata='{metadata_command_type}'")

                    # Check if this is a completion message that actually contains completion data
                    # This handles the case where there's a command_type mismatch but the data is truly a completion message
                    is_actual_completion_data = False
                    if isinstance(message.get('data'), dict) and message['data'].get('completion_message'):
                        is_actual_completion_data = True
                        logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found actual completion data in message")

                # Check if there's actual data in the message itself
                if isinstance(message, dict):
                    # Check for complex data objects in various formats
                    if 'data' in message:
                        if isinstance(message['data'], list) and len(message['data']) > 0:
                            data_in_message = True
                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found data array in message['data'] with {len(message['data'])} items")
                        elif isinstance(message['data'], dict) and message['data'].get('position', None):
                            data_in_message = True
                            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found position data in message['data']")

                # Also check for nested precipitation objects
                if 'precipitation_data' in message and isinstance(message['precipitation_data'], list) and len(message['precipitation_data']) > 0:
                    data_in_message = True
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found precipitation_data array with {len(message['precipitation_data'])} items")

                # Also check the frame's "data" field that might contain precipitation objects
                elif 'frames' in message and isinstance(message['frames'], list) and len(message['frames']) > 2:
                    data_in_message = True
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found frames data in message with {len(message['frames'])} frames")

                # Check if message contains binary data that will be translated
                if 'metadata' in message and isinstance(message['metadata'], dict):
                    if message['metadata'].get('precip_data_available', False) or message['metadata'].get('precipitation_data', False):
                        data_in_message = True
                        logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Found precipitation data availability flags in metadata")

                # If top level command_type says precipitation_data, always treat as data regardless of metadata
                if isinstance(message, dict) and message.get('command_type') == 'precipitation_data':
                    command_type_override = True
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Top-level command_type is 'precipitation_data', overriding completion check")
                else:
                    command_type_override = False

                if (is_completion_message and not data_in_message and not command_type_override
                        and not command_type_mismatch):
                    # Standard completion message handling
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Received true precipitation completion message - not extracting data")
                    await self._send_acknowledgment(request_id, True, "Completion message received")
                    return True
                elif is_actual_completion_data:
                    # Handle messages that have actual completion data even if command types mismatch
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Detected completion data with command_type mismatch")
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Handling as completion message based on actual data content")
                    await self._send_acknowledgment(request_id, True, "Completion message received (despite command_type mismatch)")
                    return True
                elif (is_completion_message and (data_in_message or command_type_override
                      or command_type_mismatch)):
                    # This is a "completion" message that actually contains precipitation data or has command_type mismatch
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Received precipitation message containing data or command_type mismatch despite 'completion' flags")
                    logger.info("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Handling as normal precipitation data message instead")
                    # Continue processing as normal (fall through)
                else:
                    # Only log error for non-completion messages without data
                    logger.debug("[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Failed to extract valid precipitation data from message")
                    await self._send_acknowledgment(request_id, False, "Could not extract valid precipitation data")
                    return False

            # Initialize precip_data_list if it doesn't exist yet
            # This variable is only set if we already processed a list of precipitation objects
            if 'precip_data_list' not in locals():
                precip_data_list = []

            # Special handling for when response is a list of precipitation-like objects
            if isinstance(response, list) and len(response) > 0:
                # Check if these look like precipitation data objects
                if all(isinstance(item, dict) and 'position' in item and 'type' in item and 'rate' in item for item in response):
                    logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Processing list of {len(response)} precipitation data objects directly from message")
                    # Use the list directly
                    precip_data_list = response

                    # Store all objects
                    for idx, precip_item in enumerate(precip_data_list):
                        # Create a precipitation data object from dictionary
                        precip_obj = PrecipitationData(
                            position=precip_item['position'],
                            type=precip_item['type'],
                            rate=precip_item['rate'],
                            intensity=precip_item.get('intensity', 0.0),
                            show_values=precip_item.get('show_values', False)
                        )
                        precip_obj.request_id = f"{request_id}_{idx+1}" if idx > 0 else request_id
                        precip_obj.timestamp = time.time()

                        # Store each precipitation data object
                        await self._store_precipitation_data(precip_obj)

                    # Send acknowledgment and return
                    await self._send_acknowledgment(request_id, True, f"Processed {len(precip_data_list)} precipitation data objects directly")
                    return

            # This check needs to handle both scenarios: a single PrecipitationData object
            # or when we've already processed a list of precipitation objects above
            if (not data or not isinstance(data, PrecipitationData)) and not precip_data_list:
                # Only report an error if we haven't already processed the data as a list
                logger.debug(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Invalid data format or type")
                await self._send_acknowledgment(request_id, False, "Invalid data type")
                return

            # Validate data
            validation_errors = []
            if data.rate < 0 or data.rate > 100:  # 0-100 mm/hr range
                validation_errors.append("Invalid precipitation rate")
            if data.intensity < 0 or data.intensity > 1.0:  # 0-1 scale
                validation_errors.append("Invalid intensity value")
            if any(p > 255.0 for p in data.position):
                validation_errors.append("Position out of range")

            if validation_errors:
                error_msg = ", ".join(validation_errors)
                await self._send_acknowledgment(request_id, False, error_msg)
                return

            # Extract original request ID from message
            original_request_id = message.get('original_request_id', request_id)
            logger.info(f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] Using original request ID: {original_request_id}")

            # Create a new PrecipitationData object with validated fields
            precipitation_data = PrecipitationData(
                position=data.position,
                type=data.type,
                rate=data.rate,
                intensity=data.intensity,
                show_values=getattr(data, 'show_values', False)
            )
            precipitation_data.timestamp = message.get('timestamp', time.time())
            precipitation_data.request_id = original_request_id

            # Add metadata for tracking
            if not hasattr(precipitation_data, 'additional_info'):
                precipitation_data.additional_info = {}
            precipitation_data.additional_info['original_request_id'] = original_request_id

            # Get proper command word for display system
            from FMOFP.local_messaging.command_word_map import register_command_word
            display_command = register_command_word('displays', 0, 'radar_display', 'data', 'precipitation')
            precipitation_data.additional_info['command_word'] = display_command

            # Add any additional info
            if hasattr(data, 'additional_info'):
                precipitation_data.additional_info.update(data.additional_info)

            # Store data
            success = await self._store_precipitation_data(precipitation_data)

            # If storage was successful the bridge push inside
            # _store_precipitation_data() has already delivered the data to the
            # RadarDisplayDataCoordinator.  No further routing is needed here.
            # The previous code called display_handler.handle_precipitation_data()
            # at this point, which re-entered PrecipitationResponseService and
            # was silently killed by the loop-prevention decorator, leaving the
            # coordinator empty on the 1553B path.
            if success:
                logger.info(
                    f"[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW] "
                    f"Precipitation data stored and pushed to coordinator for {original_request_id}"
                )

            # Send acknowledgment based on storage result
            await self._send_acknowledgment(request_id, success,
                "Data stored successfully" if success else "Failed to store data")

        except Exception as e:
            logger.error(f"Error handling precipitation data: {e}")
            traceback.print_exc()
            if 'request_id' in locals():
                await self._send_acknowledgment(request_id, False, f"Error: {str(e)}")

    async def _store_precipitation_data(self, precipitation_data: PrecipitationData) -> bool:
        """Store precipitation data with robust error handling and verification"""
        try:
            # Log storage operation start
            logger.info(f"[PRECIP_STORE] Storing precipitation data with request_id: {precipitation_data.request_id}")
            logger.info(f"[PRECIP_STORE] Data details: position={precipitation_data.position}, type={precipitation_data.type}, rate={precipitation_data.rate}")

            # Ensure we have a valid data handler
            if not hasattr(self, 'data_handler') or self.data_handler is None:
                # Initialize data handler if needed
                from FMOFP.storage.DBM import DatabaseManager
                logger.info("[PRECIP_STORE] Creating new data handler")
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                radar_db = db_manager.get_system_db('radar_management')
                from FMOFP.local_messaging.routing.handlers.precipitation_data_handler import PrecipitationDataHandler
                self.data_handler = PrecipitationDataHandler(radar_db)

                # Verify initialization succeeded
                if not self.data_handler._initialized:
                    logger.error("[PRECIP_STORE] Failed to initialize data handler")
                    return False

                logger.info("[PRECIP_STORE] Data handler created and initialized")

            # Explicitly verify table exists before storage
            if not self.data_handler._verify_table_exists():
                logger.warning("[PRECIP_STORE] Precipitation table doesn't exist, creating it")
                if not self.data_handler._init_database_table():
                    logger.error("[PRECIP_STORE] Failed to create precipitation table")
                    return False
                logger.info("[PRECIP_STORE] Precipitation table created successfully")

            # Use ONLY direct storage with comprehensive verification
            # Store data directly through data handler (no queue)
            direct_store_result = self.data_handler.store_precipitation_data(precipitation_data)

            if not direct_store_result:
                logger.error(f"[PRECIP_STORE] Direct storage failed for request_id: {precipitation_data.request_id}")
                return False

            # Verify storage with explicit database query
            verify_data = await self._verify_precipitation_storage(precipitation_data.request_id)
            if not verify_data:
                logger.error(f"[PRECIP_STORE] Storage verification failed for request_id: {precipitation_data.request_id}")
                return False

            logger.info(f"[PRECIP_STORE] Precipitation data stored and verified successfully: {precipitation_data.request_id}")

            # Required test logging pattern
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] Storing data:")
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] - request_id: {precipitation_data.request_id}")
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] - position: {precipitation_data.position}")
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] - type: {precipitation_data.type}")
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] - rate: {precipitation_data.rate}")
            logger.info(f"[PRECIP_RSPNS_SERV_STORE] - timestamp: {precipitation_data.timestamp}")
            logger.debug(f"[PRECIP_RSPNS_SERV_STORE] Storing data with request_id: {precipitation_data.request_id}")

            # Push directly to the display coordinator via the bridge.
            # The original _forward_to_display_system() path went through
            # DisplayMessageHandler which re-enters the precipitation handling
            # chain and gets killed by loop-prevention decorators.
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_precipitation_data
                bridge_ok = push_precipitation_data([precipitation_data], precipitation_data.request_id)
                if bridge_ok:
                    logger.info(f"[PRECIP_STORE] Bridge: precipitation data pushed to display coordinator for request {precipitation_data.request_id}")
                else:
                    logger.warning(f"[PRECIP_STORE] Bridge push returned False for request {precipitation_data.request_id}")
            except Exception as _bridge_exc:
                logger.warning(f"[PRECIP_STORE] Bridge push failed (non-fatal): {_bridge_exc}")

            return True
        except Exception as e:
            logger.error(f"[PRECIP_STORE] Error storing precipitation data: {e}")
            logger.error(traceback.format_exc())
            return False

    async def _verify_precipitation_storage(self, request_id: str) -> bool:
        """
        Verify precipitation data was stored correctly in database

        Args:
            request_id: Request ID to verify

        Returns:
            bool: True if verification successful
        """
        try:
            if not hasattr(self, 'data_handler') or not self.data_handler or not hasattr(self.data_handler, 'radar_db'):
                logger.error("[PRECIP_VERIFY] No valid data handler for verification")
                return False

            # Get database connection
            radar_db = self.data_handler.radar_db

            # Perform verification query with retries
            max_retries = 3
            retry_delay = 0.1

            for retry in range(max_retries):
                try:
                    # First check for exact match
                    query = """
                        SELECT COUNT(*) FROM precipitation_data
                        WHERE request_id = ?
                    """

                    result = radar_db.execute_query(
                        query,
                        (request_id,),
                        query_type='select',
                        manage_transaction=True
                    )

                    if result and result[0][0] > 0:
                        logger.info(f"[PRECIP_VERIFY] Verified data in database: found {result[0][0]} records for request_id {request_id}")
                        return True

                    # If no exact match, check for child pattern
                    child_query = """
                        SELECT COUNT(*) FROM precipitation_data
                        WHERE request_id LIKE ?
                    """

                    child_result = radar_db.execute_query(
                        child_query,
                        (f"{request_id}_%",),
                        query_type='select',
                        manage_transaction=True
                    )

                    if child_result and child_result[0][0] > 0:
                        logger.info(f"[PRECIP_VERIFY] Verified data in database: found {child_result[0][0]} child records for parent request_id {request_id}")
                        return True

                    if retry < max_retries - 1:
                        logger.warning(f"[PRECIP_VERIFY] Verification attempt {retry+1} failed, retrying in {retry_delay}s")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff

                except Exception as query_error:
                    logger.error(f"[PRECIP_VERIFY] Database error on verification attempt {retry+1}: {query_error}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2

            logger.error(f"[PRECIP_VERIFY] All verification attempts failed for request_id {request_id}")
            return False

        except Exception as e:
            logger.error(f"[PRECIP_VERIFY] Error during verification: {e}")
            logger.error(traceback.format_exc())
            return False

    async def _forward_to_display_system(self, precipitation_data: PrecipitationData) -> None:
        """
        Forward precipitation data to display system WITHOUT querying DB or causing redundant storage

        Args:
            precipitation_data: Data to forward (single object that was already stored)
        """
        try:
            from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
            display_handler = get_display_message_handler()

            if not display_handler:
                logger.error("[PRECIP_FORWARD] Could not get display message handler")
                return

            # Get current radar mode
            current_mode_str = "SURVEILLANCE"
            if hasattr(precipitation_data, 'additional_info') and precipitation_data.additional_info.get('mode'):
                current_mode_str = precipitation_data.additional_info['mode']

            # Get command word for display system
            from FMOFP.local_messaging.command_word_map import register_command_word
            display_command = register_command_word('displays', 0, 'radar_display', 'data', 'precipitation')

            # Create forwarding message with ONLY the precipitation object(s)
            # NO database queries, NO extra data retrieval
            display_message = {
                'data': precipitation_data,
                'precipitation_data': [precipitation_data],  # Just include this object(s)
                'vil_data': [],  # Empty list to avoid DB query
                'cells': [],     # Empty list to avoid DB query
                'request_id': precipitation_data.request_id,
                'timestamp': time.time(),
                'message_type': 'weather_radarPrecipitationResponse',
                'metadata': {
                    'data_type': 'precipitation',
                    'source': 'weather_radar',
                    'destination': 'display_system',
                    'original_request_id': precipitation_data.request_id,
                    'precipitation_message': True,
                    '_direct_from_precipitation_service': True,
                    'command_type': 'precipitation_data',

                    # Prevent further storage attempts
                    '_already_stored': True,
                    '_processed_by_precipitation_service': True,
                    '_storage_timestamp': time.time(),

                    'weather_data': {
                        'precipitation': True,
                        'vil': False,
                        'cells': False
                    },
                    'is_mode_change': False
                }
            }

            # Add command word if available
            if hasattr(precipitation_data, 'additional_info') and precipitation_data.additional_info.get('command_word'):
                display_message['metadata']['command_word'] = precipitation_data.additional_info['command_word']
            else:
                display_message['metadata']['command_word'] = display_command

            # Forward to display handler with clear logs
            logger.info(f"[PRECIP_FORWARD] Sending SINGLE precipitation data object to display system")
            logger.info(f"[PRECIP_FORWARD] Object request_id: {precipitation_data.request_id}")
            await display_handler.handle_precipitation_data(display_message)
            logger.info(f"[PRECIP_FORWARD] Sent precipitation data to display system")

        except Exception as e:
            logger.error(f"[PRECIP_FORWARD] Error forwarding to display: {e}")
            logger.error(traceback.format_exc())

    async def _send_acknowledgment(self, request_id: str, success: bool, message: str):
        """Send acknowledgment message - DISABLED for precipitation messages to prevent cascading duplicates"""
        # Simply log the result, but DO NOT send any acknowledgments
        # This completely breaks the duplication chain by not creating any new status word messages

        logger.info(f"[PRECIP] Acknowledgment DISABLED for request {request_id}: {success}")

        # Log the result for debugging but don't generate a new message
        if success:
            logger.info(f"[PRECIP_STATUS] Successfully processed precipitation data: {request_id}")
        else:
            logger.error(f"[PRECIP_STATUS] Failed to process precipitation data: {request_id} - {message}")

    def get_queue_size(self) -> int:
        """Get current size of precipitation queue"""
        return self._precipitation_queue.qsize() if self._precipitation_queue else 0

    async def wait_for_empty_queue(self, timeout: Optional[float] = None):
        """
        Wait for precipitation queue to be empty

        Args:
            timeout: Optional timeout in seconds
        """
        try:
            if not self._precipitation_queue:
                logger.warning("Queue not initialized - service may not be started")
                return

            if not self._event_loop:
                logger.warning("Event loop not set - service may not be started")
                return

            # Ensure we're using the current event loop
            current_loop = asyncio.get_running_loop()
            if current_loop != self._event_loop:
                logger.warning("Current event loop differs from service loop - recreating queue")
                self._precipitation_queue = asyncio.Queue()
                self._event_loop = current_loop

            # Wait for queue to be empty with timeout
            try:
                await asyncio.wait_for(self._precipitation_queue.join(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for precipitation queue to empty after {timeout} seconds")
                # Check queue size to help diagnose issue
                logger.warning(f"Current queue size: {self._precipitation_queue.qsize()}")
                raise
        except Exception as e:
            logger.error(f"Error waiting for empty queue: {e}")
            raise


# Singleton accessor function to match the import in __init__.py
_precipitation_response_service = None

def get_precipitation_response_service() -> PrecipitationResponseService:
    """Get the singleton instance of PrecipitationResponseService"""
    global _precipitation_response_service
    if _precipitation_response_service is None:
        # Get radar database from DBM
        from FMOFP.storage.DBM import DatabaseManager
        db_manager = DatabaseManager('FMOFP/dbConfig.xml')
        radar_db = db_manager.get_system_db('radar_management')

        # Create instance with radar database
        _precipitation_response_service = PrecipitationResponseService(radar_db)

    return _precipitation_response_service
