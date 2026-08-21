"""
Precipitation data storage and retrieval handler
"""

import threading
import json
import traceback
import time
from typing import Dict, Optional, List
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData
from FMOFP.local_messaging.message_types import WEATHER_RADAR_PRECIPITATION_RESPONSE, WEATHER_RADAR_PRECIPITATION_REQUEST
from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress
from FMOFP.local_messaging.routing.handlers.base_message_handler import BaseMessageHandler

logger = get_logger()

class PrecipitationDataHandler(BaseMessageHandler):
    """Handles storage and retrieval of precipitation data"""
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
                    cls._instance = super(PrecipitationDataHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, radar_db=None):
        """Initialize with radar database connection"""
        super().__init__()
        # Initialize message types that this handler can process
        self.message_types = [WEATHER_RADAR_PRECIPITATION_REQUEST, WEATHER_RADAR_PRECIPITATION_RESPONSE]

        if not self._initialized and radar_db is not None:
            if not radar_db:
                raise ValueError("radar_db cannot be None")

            logger.info("[PRECIP_DB] Initializing PrecipitationDataHandler")
            self.radar_db = radar_db

            # Initialize database with retries
            max_retries = 3
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    if self._init_database_table():
                        self._initialized = True
                        logger.info("[PRECIP_DB] Initialization successful")
                        break
                    else:
                        logger.error(f"[PRECIP_DB] Initialization attempt {attempt + 1}/{max_retries} failed")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                except Exception as e:
                    logger.error(f"[PRECIP_DB] Error during initialization attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                    else:
                        raise RuntimeError("Failed to initialize precipitation database") from e

            if not self._initialized:
                raise RuntimeError("Failed to initialize precipitation database after max retries")

    def _verify_table_exists(self) -> bool:
        """Verify that the precipitation_data table exists"""
        try:
            # Use SystemDatabase instance directly
            exists = self.radar_db.table_exists('precipitation_data')
            if exists:
                logger.debug("[PRECIP_DB] Precipitation data table exists")
            else:
                logger.warning("[PRECIP_DB] Precipitation data table does not exist")
            return exists

        except Exception as e:
            logger.error(f"[PRECIP_DB] Error verifying table: {e}")
            traceback.print_exc()
            return False

    def _init_database_table(self) -> bool:
        """Initialize precipitation data table with strict validation and error checking"""
        try:
            logger.info("[PRECIP_DB] Initializing precipitation data table")

            # First check if table already exists
            table_exists = False
            try:
                table_exists = self.radar_db.table_exists('precipitation_data')
                logger.debug(f"[PRECIP_DB] Table exists check: {table_exists}")
            except Exception as check_error:
                logger.error(f"[PRECIP_DB] Error checking table existence: {check_error}")
                # Continue with table creation attempt even if check fails

            if table_exists:
                logger.info("[PRECIP_DB] Precipitation data table already exists")
                return True

            # Create table with comprehensive schema
            try:
                logger.info("[PRECIP_DB] Creating precipitation_data table")
                self.radar_db.create_table('precipitation_data', {
                    'request_id': 'TEXT NOT NULL',    # Required for message tracking
                    'timestamp': 'REAL NOT NULL',     # Unix timestamp
                    'position_x': 'REAL NOT NULL',    # X coordinate in nm
                    'position_y': 'REAL NOT NULL',    # Y coordinate in nm
                    'type': 'TEXT NOT NULL',          # Precipitation type (rain, snow, etc.)
                    'rate': 'REAL NOT NULL',          # Precipitation rate (mm/hr)
                    'intensity': 'REAL NOT NULL',     # 0-1 scale
                    'show_values': 'INTEGER NOT NULL DEFAULT 0',  # Boolean as integer
                    'additional_info': 'TEXT'         # JSON string for extra data
                })
            except Exception as create_error:
                logger.error(f"[PRECIP_DB] Error creating table: {create_error}")
                logger.error(traceback.format_exc())
                return False

            # Create indices with error handling
            try:
                logger.info("[PRECIP_DB] Creating indices")
                indices = [
                    ('precip_timestamp_idx', 'timestamp'),
                    ('precip_rate_idx', 'rate'),
                    ('precip_type_idx', 'type'),
                    ('precip_request_id_idx', 'request_id')
                ]

                for idx_name, column in indices:
                    try:
                        query = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "precipitation_data" ("{column}")'
                        self.radar_db.execute_query(query, query_type='create')
                    except Exception as idx_error:
                        logger.error(f"[PRECIP_DB] Error creating index {idx_name}: {idx_error}")
                        # Continue with other indices
            except Exception as idx_error:
                logger.error(f"[PRECIP_DB] Error in index creation: {idx_error}")
                # Continue since the table exists

            # Verify table was created
            try:
                table_exists = self.radar_db.table_exists('precipitation_data')
                if table_exists:
                    logger.info("[PRECIP_DB] Precipitation data table created and verified")
                    return True
                else:
                    logger.error("[PRECIP_DB] Table creation verification failed")
                    return False
            except Exception as verify_error:
                logger.error(f"[PRECIP_DB] Error verifying table creation: {verify_error}")
                return False

        except Exception as e:
            logger.error(f"[PRECIP_DB] Critical error initializing precipitation table: {e}")
            logger.error(traceback.format_exc())
            return False

    def store_precipitation_data(self, precipitation_data: PrecipitationData) -> bool:
        """
        Store precipitation data with robust error handling

        Args:
            precipitation_data: PrecipitationData object to store

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            logger.debug(f"[LOC_PRECIP_DATA_HDLR_PRECIP_FLOW] Starting storage of precipitation data with request_id: {getattr(precipitation_data, 'request_id', None)}")
            logger.debug(f"[LOC_PRECIP_DATA_HDLR_PRECIP_FLOW] Input PrecipitationData object: {precipitation_data.__dict__}")

            # Verify required fields are present and add defaults if missing
            required_fields = ['request_id', 'position', 'type', 'rate', 'intensity']
            for field in required_fields:
                if not hasattr(precipitation_data, field):
                    logger.warning(f"[PRECIP_DATA_HNDLR_STORE] Missing required field: {field} - adding default value")
                    if field == 'request_id':
                        setattr(precipitation_data, field, str(time.time()))
                    elif field == 'position':
                        setattr(precipitation_data, field, (0.0, 0.0))
                    elif field == 'type':
                        setattr(precipitation_data, field, 'rain')
                    elif field == 'rate':
                        setattr(precipitation_data, field, 0.0)
                    elif field == 'intensity':
                        setattr(precipitation_data, field, 0.0)

            # Prepare data for storage with timestamp validation
            try:
                # Get timestamp, using provided timestamp even if in future
                timestamp = getattr(precipitation_data, 'timestamp', None)
                if timestamp is None:
                    timestamp = time.time()
                    logger.debug("[PRECIP_DATA_HNDLR_STORE] No timestamp provided, using current time")
                    precipitation_data.timestamp = timestamp
                else:
                    logger.debug(f"[PRECIP_DATA_HNDLR_STORE] Using provided timestamp: {timestamp}")

                # Initialize or get additional_info
                if not hasattr(precipitation_data, 'additional_info'):
                    precipitation_data.additional_info = {}
                elif not isinstance(precipitation_data.additional_info, dict):
                    logger.warning("[PRECIP_DATA_HNDLR_STORE] additional_info is not a dictionary - creating new one")
                    precipitation_data.additional_info = {}

                additional_info = precipitation_data.additional_info.copy()

                # Extract command word and add to additional_info
                command_word = additional_info.get('command_word')
                if not command_word:
                    # Get command word from command_word_map using address_utils for consistent RT/SA addressing
                    from FMOFP.local_messaging.command_word_map import register_command_word
                    # Use display_system and radar_display from address_utils for consistent addressing
                    system_id = 'displays'  # Use consistent system identifier
                    subaddress_name = 'radar_display'  # Use consistent subaddress identifier
                    command_word = register_command_word(system_id, 0, subaddress_name, 'data', 'precipitation')
                    additional_info['command_word'] = command_word
                    logger.debug(f"[LOC_PRECIP_DATA_HDLR_PRECIP_FLOW] Generated command word: {command_word} for system={system_id}, subaddress={subaddress_name}")

                # Add mode information if available
                if 'mode' not in additional_info:
                    additional_info['mode'] = 'SURVEILLANCE'  # Default mode for precipitation data

                # Add message type information from centralized constants
                if 'message_type' not in additional_info:
                    # Use the centralized constant from message_types.py
                    from FMOFP.local_messaging.message_types import WEATHER_RADAR_PRECIPITATION_RESPONSE
                    additional_info['message_type'] = WEATHER_RADAR_PRECIPITATION_RESPONSE

                # Ensure show_values is set
                if not hasattr(precipitation_data, 'show_values'):
                    precipitation_data.show_values = False

                data = {
                    'request_id': getattr(precipitation_data, 'request_id'),  # Required by schema
                    'timestamp': timestamp,
                    'position_x': precipitation_data.position[0],
                    'position_y': precipitation_data.position[1],
                    'type': precipitation_data.type,
                    'rate': precipitation_data.rate,
                    'intensity': precipitation_data.intensity,
                    'show_values': 1 if precipitation_data.show_values else 0,
                    'additional_info': json.dumps(additional_info)
                }

                # Add critical debugging log for tracking
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Storing precipitation data: position=({precipitation_data.position[0]}, {precipitation_data.position[1]}), type={precipitation_data.type}, rate={precipitation_data.rate}, intensity={precipitation_data.intensity}")

                # Log the data being stored
                logger.debug("[PRECIP_DATA_HNDLR_STORE] Storing data:")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - request_id: {data['request_id']}")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - timestamp: {data['timestamp']}")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - position: ({data['position_x']}, {data['position_y']})")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - type: {data['type']}")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - rate: {data['rate']}")
                logger.debug(f"[PRECIP_DATA_HNDLR_STORE] - intensity: {data['intensity']}")

            except AttributeError as e:
                logger.error(f"[PRECIP_DATA_HNDLR_STORE] Failed to prepare data - missing attribute: {e}")
                logger.error(traceback.format_exc())
                return False

            try:
                # First check if table exists, create if not
                if not self._verify_table_exists():
                    logger.warning("[PRECIP_DATA_HNDLR_STORE] Precipitation data table does not exist - creating it")
                    if not self._init_database_table():
                        logger.error("[PRECIP_DATA_HNDLR_STORE] Failed to create precipitation data table")
                        return False

                # Check if record with same request_id already exists
                check_query = 'SELECT COUNT(*) FROM "precipitation_data" WHERE "request_id" = ?'
                check_result = self.radar_db.execute_query(check_query, (data['request_id'],), query_type='select')

                if check_result and check_result[0][0] > 0:
                    logger.warning(f"[PRECIP_DATA_HNDLR_STORE] Record with request_id {data['request_id']} already exists - updating")

                    # Build update query
                    update_parts = []
                    for key in data.keys():
                        if key != 'request_id':  # Don't update the primary key
                            update_parts.append(f'"{key}" = ?')

                    update_query = f'UPDATE "precipitation_data" SET {", ".join(update_parts)} WHERE "request_id" = ?'

                    # Prepare values (all fields except request_id, then request_id at the end)
                    update_values = [data[key] for key in data.keys() if key != 'request_id']
                    update_values.append(data['request_id'])

                    # Execute update
                    self.radar_db.execute_query(update_query, tuple(update_values), query_type='update', manage_transaction=True)
                else:
                    # Build insert query
                    fields = ', '.join([f'"{k}"' for k in data.keys()])
                    placeholders = ', '.join(['?' for _ in data])
                    query = f'INSERT INTO "precipitation_data" ({fields}) VALUES ({placeholders})'

                    # Execute insert with transaction management
                    self.radar_db.execute_query(query, tuple(data.values()), query_type='insert', manage_transaction=True)

                # Verify data was stored
                verify_query = 'SELECT COUNT(*) FROM "precipitation_data" WHERE "request_id" = ?'
                result = self.radar_db.execute_query(verify_query, (data['request_id'],), query_type='select')

                if result and result[0][0] > 0:
                    logger.info("[PRECIP_DATA_HNDLR_STORE] Data stored and verified successfully")
                    return True
                else:
                    logger.error("[PRECIP_DATA_HNDLR_STORE] Data storage verification failed")
                    return False

            except Exception as e:
                logger.error(f"[PRECIP_DATA_HNDLR_STORE] Error during storage: {e}")
                logger.error(traceback.format_exc())
                return False

        except Exception as e:
            logger.error(f"Error storing precipitation data: {e}")
            logger.error(traceback.format_exc())
            return False

    def _convert_to_precipitation_data(self, row_dict: Dict) -> PrecipitationData:
        """
        Convert a database row dictionary to a PrecipitationData object

        Args:
            row_dict: Dictionary containing precipitation data from database

        Returns:
            PrecipitationData object initialized with the row data
        """
        try:
            # Log input validation
            logger.debug(f"[PRECIP_CONVERT] Input dict: {row_dict}")
            logger.debug(f"[PRECIP_CONVERT] Dict keys: {row_dict.keys()}")

            # Create position tuple from x,y coordinates
            logger.debug(f"[PRECIP_CONVERT] Creating position from x={row_dict['position_x']}, y={row_dict['position_y']}")
            position = (float(row_dict['position_x']), float(row_dict['position_y']))
            logger.debug(f"[PRECIP_CONVERT] Position tuple created: {position}")

            # Parse additional_info
            try:
                additional_info = json.loads(row_dict['additional_info']) if row_dict['additional_info'] else {}
            except json.JSONDecodeError:
                additional_info = {}
            logger.debug(f"[PRECIP_CONVERT] Parsed additional_info: {additional_info}")

            # Create PrecipitationData object with only the required fields
            logger.debug(f"[PRECIP_CONVERT] Creating PrecipitationData with position={position}")
            precipitation_data = PrecipitationData(
                position=position,
                type=str(row_dict['type']),
                rate=float(row_dict['rate']),
                intensity=float(row_dict['intensity']),
                show_values=bool(int(row_dict['show_values']))
            )
            logger.debug(f"[PRECIP_CONVERT] Created object: {precipitation_data}")
            logger.debug(f"[PRECIP_CONVERT] Object type: {type(precipitation_data)}")

            # Set the fields that have default factories after creation
            precipitation_data.request_id = str(row_dict['request_id'])
            precipitation_data.timestamp = float(row_dict['timestamp'])
            precipitation_data.additional_info = additional_info

            # Verify object state
            logger.debug(f"[PRECIP_CONVERT] Final object state:")
            logger.debug(f"[PRECIP_CONVERT] - position: {precipitation_data.position}")
            logger.debug(f"[PRECIP_CONVERT] - type: {precipitation_data.type}")
            logger.debug(f"[PRECIP_CONVERT] - rate: {precipitation_data.rate}")
            logger.debug(f"[PRECIP_CONVERT] - intensity: {precipitation_data.intensity}")
            logger.debug(f"[PRECIP_CONVERT] - show_values: {precipitation_data.show_values}")

            return precipitation_data

        except Exception as e:
            logger.error(f"Error converting row to PrecipitationData: {e}")
            logger.error(f"Row data: {row_dict}")
            raise

    def get_precipitation_data(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        precip_type: Optional[str] = None,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None
    ) -> List[PrecipitationData]:
        """
        Retrieve precipitation data with filtering

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            precip_type: Optional precipitation type filter
            min_rate: Optional minimum rate filter
            max_rate: Optional maximum rate filter

        Returns:
            List of PrecipitationData objects matching the filters
        """
        try:
            # Log table verification
            table_exists = self._verify_table_exists()
            logger.debug(f"[PRECIP_DB] Table exists check: {table_exists}")

            # Log the query parameters
            logger.debug("[PRECIP_DB] Query parameters:")
            logger.debug(f"[PRECIP_DB] - Time range: {start_time} to {end_time}")
            logger.debug(f"[PRECIP_DB] - Type: {precip_type}")
            logger.debug(f"[PRECIP_DB] - Rate range: {min_rate} to {max_rate}")

            # Build query based on filters
            query_parts = ['SELECT * FROM "precipitation_data"']
            params = []

            where_conditions = []
            if start_time is not None and end_time is not None:
                where_conditions.append('"timestamp" BETWEEN ? AND ?')
                params.extend([start_time, end_time])
            if precip_type is not None:
                where_conditions.append('"type" = ?')
                params.append(precip_type)
            if min_rate is not None and max_rate is not None:
                where_conditions.append('"rate" BETWEEN ? AND ?')
                params.extend([min_rate, max_rate])

            if where_conditions:
                query_parts.append('WHERE ' + ' AND '.join(where_conditions))

            query_parts.append('ORDER BY "timestamp" DESC')
            query = ' '.join(query_parts)

            # Execute query
            logger.debug(f"[PRECIP_DB] Executing query: {query}")
            logger.debug(f"[PRECIP_DB] With parameters: {params}")

            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            if not results:
                logger.debug("[PRECIP_DB] No results found")
                return []

            logger.debug(f"[PRECIP_DB] Found {len(results)} results")

            # Get column names
            columns = []
            with self.radar_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(precipitation_data)")
                columns = [col[1] for col in cursor.fetchall()]

            # Convert results to dictionaries
            raw_data = []
            for row in results:
                try:
                    # Convert row to dictionary using column names
                    row_dict = dict(zip(columns, row))
                    raw_data.append(row_dict)
                except Exception as e:
                    logger.error(f"Error converting row to dictionary: {e}")
                    logger.error(f"Row data: {row}")
                    continue

            # Convert to PrecipitationData objects
            precipitation_data_list = []
            for i, row_dict in enumerate(raw_data):
                try:
                    logger.debug(f"[PRECIP_GET] Converting row {i}: {row_dict}")
                    logger.debug(f"[PRECIP_GET] Row type before conversion: {type(row_dict)}")

                    precipitation_data = self._convert_to_precipitation_data(row_dict)
                    logger.debug(f"[PRECIP_GET] Converted object: {precipitation_data}")
                    logger.debug(f"[PRECIP_GET] Converted type: {type(precipitation_data)}")
                    logger.debug(f"[PRECIP_GET] Position attribute: {getattr(precipitation_data, 'position', None)}")
                    precipitation_data_list.append(precipitation_data)

                except Exception as e:
                    logger.error(f"Error converting row to PrecipitationData: {e}")
                    logger.error(f"Row data: {row_dict}")
                    continue

            logger.debug(f"Successfully converted {len(precipitation_data_list)} records to PrecipitationData objects")
            return precipitation_data_list

        except Exception as e:
            logger.error(f"Error retrieving precipitation data: {e}")
            traceback.print_exc()
            return []

    def clear_old_data(self, max_age_seconds: float = 3600) -> int:
        """
        Clear precipitation data older than specified age

        Args:
            max_age_seconds: Maximum age of data to keep in seconds

        Returns:
            Number of records deleted
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - max_age_seconds

            # Use SystemDatabase instance directly
            condition = {'timestamp': {'<': cutoff_time}}
            result = self.radar_db.delete_from_table('precipitation_data', condition)

            logger.info(f"Cleared precipitation data older than {max_age_seconds} seconds")
            return result

        except Exception as e:
            logger.error(f"Error clearing old precipitation data: {e}")
            traceback.print_exc()
            return 0

    def store_precipitation_data_raw(self, request_id: str, position_x: float, position_y: float,
                              precip_type: str, rate: float, intensity: float,
                              timestamp: float = None, show_values: bool = True,
                              use_transaction: bool = True) -> bool:
        """
        Store raw precipitation data directly with provided field values
        This method is used by precipitation_response_service to store data decoded from binary format

        Args:
            request_id: Unique ID for tracking
            position_x: X coordinate
            position_y: Y coordinate
            precip_type: Type of precipitation (rain, snow, etc.)
            rate: Precipitation rate (mm/hr)
            intensity: Intensity on 0-1 scale
            timestamp: Optional timestamp, defaults to current time
            show_values: Whether to show values in display

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            # Critical log for test verification
            logger.debug(f"[PRECIP_RAW_STORE] Direct storage of raw precipitation data:")
            logger.debug(f"[PRECIP_RAW_STORE] - request_id: {request_id}")
            logger.debug(f"[PRECIP_RAW_STORE] - position: ({position_x}, {position_y})")
            logger.debug(f"[PRECIP_RAW_STORE] - type: {precip_type}")
            logger.debug(f"[PRECIP_RAW_STORE] - rate: {rate}")

            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = time.time()

            # Initialize additional_info with important metadata
            additional_info = {
                'source': 'precipitation_response_service',
                'binary_decoded': True,
                'mode': 'SURVEILLANCE',  # Default mode for precipitation data
                'data_type': 'precipitation'
            }

            # Add command word
            from FMOFP.local_messaging.command_word_map import register_command_word
            system_id = 'displays'
            subaddress_name = 'radar_display'
            command_word = register_command_word(system_id, 0, subaddress_name, 'data', 'precipitation')
            additional_info['command_word'] = command_word

            # Add message type
            from FMOFP.local_messaging.message_types import WEATHER_RADAR_PRECIPITATION_RESPONSE
            additional_info['message_type'] = WEATHER_RADAR_PRECIPITATION_RESPONSE

            # Ensure table exists
            if not self._verify_table_exists():
                logger.warning("[PRECIP_RAW_STORE] Table doesn't exist, creating it")
                if not self._init_database_table():
                    logger.error("[PRECIP_RAW_STORE] Failed to create table")
                    return False

            # Prepare data for storage
            data = {
                'request_id': request_id,
                'timestamp': timestamp,
                'position_x': position_x,
                'position_y': position_y,
                'type': precip_type,
                'rate': rate,
                'intensity': intensity,
                'show_values': 1 if show_values else 0,
                'additional_info': json.dumps(additional_info)
            }

            # Log for test verification
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Storing raw precipitation data: position=({position_x}, {position_y}), type={precip_type}, rate={rate}, intensity={intensity}")

            # Check if record exists
            check_query = 'SELECT COUNT(*) FROM "precipitation_data" WHERE "request_id" = ?'
            check_result = self.radar_db.execute_query(check_query, (request_id,), query_type='select')

            if check_result and check_result[0][0] > 0:
                # Update existing record
                logger.warning(f"[PRECIP_RAW_STORE] Record exists, updating: {request_id}")

                # Build update query
                update_parts = []
                for key in data.keys():
                    if key != 'request_id':
                        update_parts.append(f'"{key}" = ?')

                update_query = f'UPDATE "precipitation_data" SET {", ".join(update_parts)} WHERE "request_id" = ?'

                # Prepare values
                update_values = [data[key] for key in data.keys() if key != 'request_id']
                update_values.append(data['request_id'])

                # Execute update
                self.radar_db.execute_query(update_query, tuple(update_values), query_type='update', manage_transaction=True)
            else:
                # Insert new record
                logger.debug(f"[PRECIP_RAW_STORE] Inserting new record: {request_id}")

                # Build insert query
                fields = ', '.join([f'"{k}"' for k in data.keys()])
                placeholders = ', '.join(['?' for _ in data])
                query = f'INSERT INTO "precipitation_data" ({fields}) VALUES ({placeholders})'

                # Execute insert
                self.radar_db.execute_query(query, tuple(data.values()), query_type='insert', manage_transaction=True)

            # Verify storage
            verify_query = 'SELECT COUNT(*) FROM "precipitation_data" WHERE "request_id" = ?'
            result = self.radar_db.execute_query(verify_query, (data['request_id'],), query_type='select')

            if result and result[0][0] > 0:
                logger.info(f"[PRECIP_RAW_STORE] Data stored successfully: {request_id}")
                # Get the stored record and confirm details
                detail_query = 'SELECT * FROM "precipitation_data" WHERE "request_id" = ?'
                detail_result = self.radar_db.execute_query(detail_query, (data['request_id'],), query_type='select')

                if detail_result:
                    # Get column names
                    with self.radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(precipitation_data)")
                        columns = [col[1] for col in cursor.fetchall()]

                    # Convert to dictionary
                    row_dict = dict(zip(columns, detail_result[0]))
                    logger.info(f"[PRECIP_RAW_STORE] Stored record details: position=({row_dict['position_x']}, {row_dict['position_y']}), type={row_dict['type']}")

                return True
            else:
                logger.error(f"[PRECIP_RAW_STORE] Data storage verification failed: {request_id}")
                return False

        except Exception as e:
            logger.error(f"[PRECIP_RAW_STORE] Error storing raw precipitation data: {e}")
            logger.error(traceback.format_exc())
            return False

    def extract_and_store_binary_data(self, request_id: str, binary_data: List[int]) -> bool:
        """
        Directly extract and store precipitation data from binary format

        Args:
            request_id: Request ID for tracking
            binary_data: List of integers containing encoded data

        Returns:
            bool: True if extraction and storage successful
        """
        try:
            # Add detailed logging
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Processing binary data for request_id={request_id}")
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Binary data received: {binary_data}")

            # Validate the binary data
            if not binary_data or len(binary_data) < 1:
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Invalid binary data: {binary_data}")
                return False

            # Word 0: number of objects
            # Word 1: scale metadata (rate/intensity scale codes — read and apply below)
            # Words 2+: pairs of (pos_word, attr_word) per object
            object_count = binary_data[0]
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Object count from first word: {object_count}")

            # Decode scale factors from word 1 (written by DataResponseSender._encode_complex_objects)
            # High byte = rate_scale_code = int(log2(RATE_SCALE) * 16)
            # Low byte  = intensity_scale_code = int(log2(INTENSITY_SCALE) * 16)
            import math
            scale_word = binary_data[1] if len(binary_data) > 1 else 0
            rate_scale_code      = (scale_word >> 8) & 0xFF
            intensity_scale_code = scale_word & 0xFF
            # Use fixed constants that match DataResponseSender._encode_complex_objects.
            # The log2-encoded scale_word in the header cannot represent these values
            # exactly, so we hardcode them here. Both sides must stay in sync.
            #   RATE_SCALE=2      → rate_code = round(rate * 2),    max 31.5 mm/hr
            #   INTENSITY_SCALE=63 → intensity_code = round(int*63), range 0-1 exact
            RATE_SCALE      = 2.0
            INTENSITY_SCALE = 63.0
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Using fixed scale factors: RATE={RATE_SCALE}, INTENSITY={INTENSITY_SCALE}")

            # Validate array size: 2 header words + 2 words per object
            expected_size = 2 + (object_count * 2)
            if len(binary_data) < expected_size:
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Binary data size mismatch: expected {expected_size}, got {len(binary_data)}")
                # Decode however many complete pairs we have
                object_count = (len(binary_data) - 2) // 2

            # Check if database table exists
            if not self._verify_table_exists():
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Precipitation table doesn't exist - creating now")
                if not self._init_database_table():
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Failed to create precipitation table")
                    return False
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Successfully created precipitation table")

            # Verify database connection
            if not hasattr(self, 'radar_db') or self.radar_db is None:
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] No database connection available")
                from FMOFP.storage.DBM import DatabaseManager
                db_manager = DatabaseManager('FMOFP/dbConfig.xml')
                self.radar_db = db_manager.get_system_db('radar_management')
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Re-established database connection")

            # Process and store all precipitation data objects
            stored_objects = 0
            precipitation_objects = []

            # Use a database transaction to ensure all data is stored atomically
            with self.radar_db.get_connection() as conn:
                cursor = conn.cursor()
                transaction_started = False

                try:
                    # Start transaction
                    cursor.execute('BEGIN TRANSACTION')
                    transaction_started = True

                    # Process each object (pair of words).
                    # Objects start at index 2: word 0 = count, word 1 = scale metadata.
                    for i in range(object_count):
                        # Calculate indices for the position and attribute words
                        pos_index = 2 + (i * 2)          # Skip count word and scale word
                        attr_index = pos_index + 1        # Get attribute word

                        if pos_index >= len(binary_data) or attr_index >= len(binary_data):
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Index out of range: pos_index={pos_index}, attr_index={attr_index}")
                            continue

                        # Extract position and attributes data
                        pos_word = binary_data[pos_index]
                        attr_word = binary_data[attr_index]

                        # Log the binary representation for debugging
                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Object {i+1}/{object_count}: ")
                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] - Position word: {pos_word} (0x{pos_word:04X}, {bin(pos_word)[2:].zfill(16)})")
                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] - Attribute word: {attr_word} (0x{attr_word:04X}, {bin(attr_word)[2:].zfill(16)})")

                        # Decode position coordinates — undo the +128 offset applied at encode time
                        x_coordinate = (pos_word >> 8) & 0xFF  # Extract upper byte
                        y_coordinate = pos_word & 0xFF          # Extract lower byte
                        x = float(x_coordinate) - 128.0
                        y = float(y_coordinate) - 128.0

                        # Decode precipitation characteristics from attribute word
                        # Layout: [4 bits type][6 bits rate][6 bits intensity]
                        type_code      = (attr_word >> 12) & 0xF   # top 4 bits
                        rate_code      = (attr_word >> 6)  & 0x3F  # middle 6 bits
                        intensity_code = attr_word          & 0x3F  # bottom 6 bits

                        # Map type code to precipitation type
                        type_map = {0: 'rain', 1: 'snow', 2: 'sleet', 3: 'hail', 4: 'mixed'}
                        precip_type = type_map.get(type_code, 'rain')

                        # Convert codes back using the scale factors read from the header word.
                        # Encoder used: rate_code = int(rate * RATE_SCALE)
                        #               intensity_code = int(intensity * INTENSITY_SCALE)
                        # So the inverse is: rate = rate_code / RATE_SCALE
                        #                    intensity = intensity_code / INTENSITY_SCALE
                        rate      = float(rate_code)      / RATE_SCALE
                        intensity = float(intensity_code) / INTENSITY_SCALE

                        # Ensure intensity is never zero (for display visibility)
                        if intensity < 0.001:
                            intensity = 0.001

                        # Create the unique object ID for this precipitation data point
                        object_id = f"{request_id}_{i+1}"

                        # Prepare data for storage
                        timestamp = time.time()
                        show_values_int = 1  # True

                        # Create JSON for additional info
                        import json
                        additional_info = json.dumps({
                            'source': 'precipitation_response_service',
                            'binary_decoded': True,
                            'mode': 'SURVEILLANCE',
                            'data_type': 'precipitation',
                            'object_index': i,
                            'total_objects': object_count,
                            'original_position_word': pos_word,
                            'original_attributes_word': attr_word,
                            'parent_request_id': request_id
                        })

                        # Log the decoded data details
                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Decoded object {i+1}: x={x}, y={y}, type={precip_type}, rate={rate}, intensity={intensity}")

                        # Store this object in the database
                        cursor.execute(
                            '''INSERT INTO precipitation_data
                               (request_id, timestamp, position_x, position_y,
                                type, rate, intensity, show_values, additional_info)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (object_id, timestamp, x, y, precip_type, rate,
                             intensity, show_values_int, additional_info)
                        )

                        # Track this object for return
                        precipitation_objects.append({
                            'request_id': object_id,
                            'position': (x, y),
                            'type': precip_type,
                            'rate': rate,
                            'intensity': intensity
                        })

                        stored_objects += 1

                    # If we've made it here, commit the transaction
                    conn.commit()
                    transaction_started = False
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Successfully stored {stored_objects}/{object_count} precipitation objects")

                except Exception as db_error:
                    # Roll back transaction if it's started but not committed
                    if transaction_started:
                        try:
                            conn.rollback()
                        except Exception as rollback_error:
                            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Error rolling back transaction: {rollback_error}")

                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Database error: {db_error}")
                    logger.error(traceback.format_exc())
                    return False

            # Verify that objects were stored correctly
            verification_success = False
            try:
                # Query to count stored objects for this request
                count_query = "SELECT COUNT(*) FROM precipitation_data WHERE request_id LIKE ?"
                result = self.radar_db.execute_query(count_query, (f"{request_id}_%",), query_type='select')

                if result and result[0][0] > 0:
                    stored_count = result[0][0]
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Verification successful: {stored_count} objects found in database")
                    verification_success = True
                else:
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Verification failed: No objects found in database")
                    verification_success = False
            except Exception as verify_error:
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Verification error: {verify_error}")
                logger.error(traceback.format_exc())
                verification_success = False

            # Also create a link record in the main request table using the original request_id
            # This makes it possible to find all related objects by the original request ID
            try:
                link_record = {
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'position_x': 0.0,
                    'position_y': 0.0,
                    'type': 'collection',
                    'rate': 0.0,
                    'intensity': 0.0,
                    'show_values': 1,
                    'additional_info': json.dumps({
                        'is_collection_record': True,
                        'object_count': object_count,
                        'stored_count': stored_objects,
                        'binary_data_size': len(binary_data),
                        'object_ids': [p['request_id'] for p in precipitation_objects]
                    })
                }

                # Check if link record exists first
                check_query = "SELECT COUNT(*) FROM precipitation_data WHERE request_id = ?"
                result = self.radar_db.execute_query(check_query, (request_id,), query_type='select')
                if result and result[0][0] > 0:
                    # Update existing link record
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Updating existing link record: {request_id}")

                    # Use direct database connection for update
                    with self.radar_db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            '''UPDATE precipitation_data SET
                               timestamp = ?, additional_info = ?
                               WHERE request_id = ?''',
                            (link_record['timestamp'], link_record['additional_info'], request_id)
                        )
                        conn.commit()
                else:
                    # Insert new link record
                    self.radar_db.insert_into_table('precipitation_data', link_record)

                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Created link record with original request_id: {request_id}")

            except Exception as link_error:
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Error creating link record: {link_error}")
                # Don't fail the whole operation for this

            return verification_success

        except Exception as e:
            logger.error(f"[PRECIP_BINARY] Error extracting and storing binary data: {e}")
            logger.debug(traceback.format_exc())
            return False

    def handle_precipitation_completion(self, message: Dict) -> bool:
        """
        Handle precipitation completion messages that might contain binary data

        Args:
            message: Completion message dictionary

        Returns:
            bool: True if data was processed and stored successfully
        """
        try:
            request_id = message.get('request_id')
            if not request_id:
                logger.error("[PRECIP_COMPLETION] Missing request_id in completion message")
                return False

            # Check for data array in the message
            data = message.get('data')
            if not data or not isinstance(data, list):
                logger.error(f"[PRECIP_COMPLETION] No data array in completion message: {message.keys()}")
                return False

            # Check if this is a block transfer
            metadata = message.get('metadata', {})
            is_transfer_data = metadata.get('is_transfer_data', False)
            is_final = metadata.get('is_final', False)

            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Processing completion message with data length: {len(data)}")
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Transfer info: is_transfer_data={is_transfer_data}, is_final={is_final}")

            if is_transfer_data:
                # This is part of a block transfer
                from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
                transfer_manager = get_block_transfer_manager()

                # Get sequence information
                sequence_number = metadata.get('sequence_number', 1)
                total_sequences = metadata.get('total_sequences', 1)

                # Register this block
                transfer_complete = transfer_manager.register_block(
                    request_id,
                    sequence_number,
                    total_sequences,
                    is_final,
                    data
                )

                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Registered block {sequence_number}/{total_sequences}, transfer complete: {transfer_complete}")

                if transfer_complete:
                    # Get the assembled data
                    assembled_data = transfer_manager.get_assembled_data(request_id)

                    if assembled_data:
                        logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Processing assembled data with {len(assembled_data)} words")
                        return self.extract_and_store_binary_data(request_id, assembled_data)
                    else:
                        logger.debug("[PRECIPITATION_FLOW_DEBUG] Failed to get assembled data")
                        return False
                else:
                    # Transfer not complete yet, wait for more blocks
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Block transfer not complete yet: {sequence_number}/{total_sequences}")

                    # Get status for logging
                    status = transfer_manager.get_transfer_status(request_id)
                    logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Transfer status: {status['received_blocks']}/{status['total_blocks']} blocks received ({status['percent_complete']:.1f}% complete)")

                    # Return true since we've handled this block
                    return True
            else:
                # Not a block transfer, process the data directly
                logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Processing direct data array with {len(data)} words")
                return self.extract_and_store_binary_data(request_id, data)

        except Exception as e:
            logger.error(f"[PRECIP_COMPLETION] Error handling completion message: {e}")
            logger.error(traceback.format_exc())
            return False

    def handle_message(self, message):
        """
        Handle a precipitation data message.
        Implementation of the abstract method from BaseMessageHandler.

        Args:
            message: The message to handle

        Returns:
            bool: True if message was handled successfully, False otherwise
        """
        if not self.validate_message(message):
            logger.warning(f"Invalid precipitation message: {message}")
            return False

        try:
            # Pre-process the message
            processed_message = self.pre_process_message(message)

            # Check message type to determine action
            message_type = processed_message.get('message_type', '')
            command_type = processed_message.get('command_type', '')

            # Log detailed message info for debugging
            logger.info(f"[PRECIP_HANDLER] Handling message: type={message_type}, command={command_type}")

            # Check for precipitation completion message
            if message_type.lower() == 'radarprecipitationcompletion' or command_type.lower() in ['precipitation_completion', 'transfer_complete']:
                logger.info("[PRECIP_HANDLER] Detected precipitation completion message")
                return self.handle_precipitation_completion(processed_message)

            elif message_type.lower() == WEATHER_RADAR_PRECIPITATION_REQUEST.lower():
                # Handle data request
                logger.info("Handling precipitation data request")
                # Extract request parameters
                start_time = processed_message.get('start_time')
                end_time = processed_message.get('end_time')
                precip_type = processed_message.get('precipitation_type')
                min_rate = processed_message.get('min_rate')
                max_rate = processed_message.get('max_rate')

                # Get data
                data = self.get_precipitation_data(
                    start_time=start_time,
                    end_time=end_time,
                    precip_type=precip_type,
                    min_rate=min_rate,
                    max_rate=max_rate
                )

                logger.info(f"Retrieved {len(data)} precipitation data records")
                return True

            elif message_type.lower() == WEATHER_RADAR_PRECIPITATION_RESPONSE.lower():
                # Handle data response
                logger.info("Handling precipitation data response")

                # Check for binary data array
                if 'data' in processed_message and isinstance(processed_message['data'], list) and len(processed_message['data']) > 0:
                    # This might be binary data - check if all elements are integers
                    data_array = processed_message['data']
                    if all(isinstance(item, int) for item in data_array):
                        logger.info(f"[PRECIP_HANDLER] Detected binary data array with {len(data_array)} elements")
                        return self.extract_and_store_binary_data(processed_message.get('request_id'), data_array)

                # Convert message to PrecipitationData if needed
                if not isinstance(message, PrecipitationData):
                    # Create precipitation data object
                    try:
                        position = message.get('position', (0.0, 0.0))
                        if isinstance(position, list):
                            position = tuple(position)

                        precip_data = PrecipitationData(
                            position=position,
                            type=message.get('type', 'rain'),
                            rate=float(message.get('rate', 0.0)),
                            intensity=float(message.get('intensity', 0.0)),
                            show_values=bool(message.get('show_values', False))
                        )

                        # Set additional fields
                        precip_data.request_id = message.get('request_id', str(time.time()))
                        precip_data.timestamp = float(message.get('timestamp', time.time()))
                        precip_data.additional_info = message.get('additional_info', {})

                        # Store the data
                        result = self.store_precipitation_data(precip_data)
                        return result
                    except Exception as e:
                        logger.error(f"Error creating PrecipitationData from message: {e}")
                        return False
                else:
                    # Message is already a PrecipitationData object
                    result = self.store_precipitation_data(message)
                    return result

            logger.warning(f"Unsupported precipitation message type: {message_type}")
            return False

        except Exception as e:
            logger.error(f"Error handling precipitation message: {e}")
            traceback.print_exc()
            return False
