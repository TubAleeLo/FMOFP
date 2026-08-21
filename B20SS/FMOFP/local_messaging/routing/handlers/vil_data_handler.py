"""
VIL (Vertically Integrated Liquid) data storage and retrieval handler

Standardized implementation that conforms to the messaging consistency plan
by using centralized definitions and consistent patterns.
"""

import threading
import json
import traceback
import time
from typing import Dict, Optional, List
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import WeatherRadarVILData
from FMOFP.local_messaging.routing.handlers.base_message_handler import BaseMessageHandler
from FMOFP.local_messaging.message_types import (
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    get_message_type,
    is_message_type,
    is_vil_message
)

logger = get_logger()

class VILDataHandler(BaseMessageHandler):
    """Handles storage and retrieval of VIL data"""
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
                    cls._instance = super(VILDataHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, radar_db=None):
        """Initialize with radar database connection"""
        super().__init__()

        # Initialize message types that this handler can process
        self.message_types = [WEATHER_RADAR_VIL_REQUEST, WEATHER_RADAR_VIL_RESPONSE]

        if not self._initialized and radar_db is not None:
            if not radar_db:
                raise ValueError("radar_db cannot be None")

            logger.info("[VIL_DB] Initializing VILDataHandler")
            self.radar_db = radar_db

            # Initialize database with retries
            max_retries = 3
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    if self._init_database_table():
                        self._initialized = True
                        logger.info("[VIL_DB] Initialization successful")
                        break
                    else:
                        logger.error(f"[VIL_DB] Initialization attempt {attempt + 1}/{max_retries} failed")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                except Exception as e:
                    logger.error(f"[VIL_DB] Error during initialization attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                    else:
                        raise RuntimeError("Failed to initialize VIL database") from e

            if not self._initialized:
                raise RuntimeError("Failed to initialize VIL database after max retries")

    def _verify_table_exists(self) -> bool:
        """Verify that the vil_data table exists"""
        try:
            # Use SystemDatabase instance directly
            exists = self.radar_db.table_exists('vil_data')
            if exists:
                logger.debug("[VIL_DB] VIL data table exists")
            else:
                logger.warning("[VIL_DB] VIL data table does not exist")
            return exists

        except Exception as e:
            logger.error(f"[VIL_DB] Error verifying table: {e}")
            traceback.print_exc()
            return False

    def _init_database_table(self) -> bool:
        """Initialize VIL data table using DatabaseManager"""
        try:
            logger.info("[VIL_DB] Checking VIL data table")

            # First check if table already exists
            if self.radar_db.table_exists('vil_data'):
                logger.info("[VIL_DB] VIL data table already exists")
                return True

            logger.info("[VIL_DB] Initializing VIL data table")

            # Create table using DBM's transaction management
            self.radar_db.create_table('vil_data', {
                'request_id': 'TEXT NOT NULL',    # Required for message tracking
                'timestamp': 'REAL NOT NULL',     # Unix timestamp
                'position_x': 'REAL NOT NULL',    # X coordinate in nm
                'position_y': 'REAL NOT NULL',    # Y coordinate in nm
                'value': 'REAL NOT NULL',         # VIL value in kg/m²
                'layer_count': 'INTEGER NOT NULL', # Number of layers
                'intensity': 'REAL NOT NULL',     # 0-1 scale
                'show_values': 'INTEGER NOT NULL DEFAULT 0',  # Boolean as integer
                'additional_info': 'TEXT'         # JSON string for extra data
            })

            # Create indices for commonly queried fields
            logger.info("[VIL_DB] Creating indices")
            indices = [
                ('vil_timestamp_idx', 'timestamp'),
                ('vil_value_idx', 'value'),
                ('vil_request_id_idx', 'request_id')
            ]

            for idx_name, column in indices:
                query = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "vil_data" ("{column}")'
                self.radar_db.execute_query(query, query_type='create')

            logger.info("[VIL_DB] VIL data table and indices initialized successfully")
            return True

        except Exception as e:
            logger.error(f"[VIL_DB] Critical error initializing VIL table: {e}")
            logger.error(traceback.format_exc())
            return False

    def store_vil_data(self, vil_data: WeatherRadarVILData) -> bool:
        """
        Store VIL data with robust error handling

        Args:
            vil_data: WeatherRadarVILData object to store

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            logger.debug(f"[VIL_FLOW] Starting storage of VIL data with request_id: {getattr(vil_data, 'request_id', None)}")
            logger.debug(f"[VIL_FLOW] Input WeatherRadarVILData object: {vil_data.__dict__}")

            # Verify required fields are present and add defaults if missing
            required_fields = ['request_id', 'position', 'value', 'layer_count', 'intensity']
            for field in required_fields:
                if not hasattr(vil_data, field):
                    logger.warning(f"[VIL_STORE] Missing required field: {field} - adding default value")
                    if field == 'request_id':
                        setattr(vil_data, field, str(time.time()))
                    elif field == 'position':
                        setattr(vil_data, field, (0.0, 0.0))
                    elif field == 'value':
                        setattr(vil_data, field, 0.0)
                    elif field == 'layer_count':
                        setattr(vil_data, field, 1)
                    elif field == 'intensity':
                        setattr(vil_data, field, 0.0)

            # Prepare data for storage with timestamp validation
            try:
                # Get timestamp, using provided timestamp even if in future
                timestamp = getattr(vil_data, 'timestamp', None)
                if timestamp is None:
                    timestamp = time.time()
                    logger.debug("[VIL_STORE] No timestamp provided, using current time")
                    vil_data.timestamp = timestamp
                else:
                    logger.debug(f"[VIL_STORE] Using provided timestamp: {timestamp}")

                # Initialize or get additional_info
                if not hasattr(vil_data, 'additional_info'):
                    vil_data.additional_info = {}
                elif not isinstance(vil_data.additional_info, dict):
                    logger.warning("[VIL_STORE] additional_info is not a dictionary - creating new one")
                    vil_data.additional_info = {}

                additional_info = vil_data.additional_info.copy()

                # Extract command word and add to additional_info
                command_word = additional_info.get('command_word')
                if not command_word:
                    # Get command word from command_word_map using address_utils for consistent RT/SA addressing
                    from FMOFP.local_messaging.command_word_map import register_command_word
                    # Use display_system and radar_display from address_utils for consistent addressing
                    system_id = 'displays'  # Use consistent system identifier
                    subaddress_name = 'radar_display'  # Use consistent subaddress identifier
                    command_word = register_command_word(system_id, 0, subaddress_name, 'data', 'vil')
                    additional_info['command_word'] = command_word
                    logger.debug(f"[VIL_FLOW] Generated command word: {command_word} for system={system_id}, subaddress={subaddress_name}")

                # Add mode information if available
                if 'mode' not in additional_info:
                    additional_info['mode'] = 'SURVEILLANCE'  # Default mode for VIL data

                # Add message type information from centralized constants
                from FMOFP.local_messaging.message_types import WEATHER_RADAR_VIL_RESPONSE
                if 'message_type' not in additional_info:
                    additional_info['message_type'] = WEATHER_RADAR_VIL_RESPONSE

                # Ensure show_values is set
                if not hasattr(vil_data, 'show_values'):
                    vil_data.show_values = False

                data = {
                    'request_id': getattr(vil_data, 'request_id'),  # Required by schema
                    'timestamp': timestamp,
                    'position_x': vil_data.position[0],
                    'position_y': vil_data.position[1],
                    'value': vil_data.value,
                    'layer_count': vil_data.layer_count,
                    'intensity': vil_data.intensity,
                    'show_values': 1 if vil_data.show_values else 0,
                    'additional_info': json.dumps(additional_info)
                }

                # Log the data being stored
                logger.debug("[VIL_STORE] Storing data:")
                logger.debug(f"[VIL_STORE] - request_id: {data['request_id']}")
                logger.debug(f"[VIL_STORE] - timestamp: {data['timestamp']}")
                logger.debug(f"[VIL_STORE] - position: ({data['position_x']}, {data['position_y']})")
                logger.debug(f"[VIL_STORE] - value: {data['value']}")
                logger.debug(f"[VIL_STORE] - layer_count: {data['layer_count']}")
                logger.debug(f"[VIL_STORE] - intensity: {data['intensity']}")

            except AttributeError as e:
                logger.error(f"[VIL_STORE] Failed to prepare data - missing attribute: {e}")
                logger.error(traceback.format_exc())
                return False
            except Exception as e:
                logger.error(f"[VIL_STORE] Failed to prepare data: {e}")
                logger.error(traceback.format_exc())
                return False

            try:
                # First check if table exists, create if not
                if not self._verify_table_exists():
                    logger.warning("[VIL_STORE] VIL data table does not exist - creating it")
                    if not self._init_database_table():
                        logger.error("[VIL_STORE] Failed to create VIL data table")
                        return False

                # Check if record with same request_id already exists
                check_query = 'SELECT COUNT(*) FROM "vil_data" WHERE "request_id" = ?'
                check_result = self.radar_db.execute_query(check_query, (data['request_id'],), query_type='select')

                if check_result and check_result[0][0] > 0:
                    logger.warning(f"[VIL_STORE] Record with request_id {data['request_id']} already exists - updating")

                    # Build update query
                    update_parts = []
                    for key in data.keys():
                        if key != 'request_id':  # Don't update the primary key
                            update_parts.append(f'"{key}" = ?')

                    update_query = f'UPDATE "vil_data" SET {", ".join(update_parts)} WHERE "request_id" = ?'

                    # Prepare values (all fields except request_id, then request_id at the end)
                    update_values = [data[key] for key in data.keys() if key != 'request_id']
                    update_values.append(data['request_id'])

                    # Execute update
                    self.radar_db.execute_query(update_query, tuple(update_values), query_type='update', manage_transaction=True)
                else:
                    # Build insert query
                    fields = ', '.join([f'"{k}"' for k in data.keys()])
                    placeholders = ', '.join(['?' for _ in data])
                    query = f'INSERT INTO "vil_data" ({fields}) VALUES ({placeholders})'

                    # Execute insert with transaction management
                    self.radar_db.execute_query(query, tuple(data.values()), query_type='insert', manage_transaction=True)

                # Verify data was stored
                verify_query = 'SELECT COUNT(*) FROM "vil_data" WHERE "request_id" = ?'
                result = self.radar_db.execute_query(verify_query, (data['request_id'],), query_type='select')

                if result and result[0][0] > 0:
                    logger.info("[VIL_STORE] Data stored and verified successfully")
                    return True
                else:
                    logger.error("[VIL_STORE] Data storage verification failed")
                    return False

            except Exception as e:
                logger.error(f"[VIL_STORE] Error during storage: {e}")
                logger.error(traceback.format_exc())
                return False

        except Exception as e:
            logger.error(f"Error storing VIL data: {e}")
            logger.error(traceback.format_exc())
            return False

    def _convert_to_vil_data(self, row_dict: Dict) -> WeatherRadarVILData:
        """
        Convert a database row dictionary to a WeatherRadarVILData object

        Args:
            row_dict: Dictionary containing VIL data from database

        Returns:
            WeatherRadarVILData object initialized with the row data
        """
        try:
            # Log input validation
            logger.debug(f"[VIL_CONVERT] Input dict: {row_dict}")
            logger.debug(f"[VIL_CONVERT] Dict keys: {row_dict.keys()}")

            # Create position tuple from x,y coordinates
            logger.debug(f"[VIL_CONVERT] Creating position from x={row_dict['position_x']}, y={row_dict['position_y']}")
            position = (float(row_dict['position_x']), float(row_dict['position_y']))
            logger.debug(f"[VIL_CONVERT] Position tuple created: {position}")

            # Parse additional_info
            try:
                additional_info = json.loads(row_dict['additional_info']) if row_dict['additional_info'] else {}
            except json.JSONDecodeError:
                additional_info = {}
            logger.debug(f"[VIL_CONVERT] Parsed additional_info: {additional_info}")

            # Create WeatherRadarVILData object with only the required fields
            logger.debug(f"[VIL_CONVERT] Creating WeatherRadarVILData with position={position}")
            vil_data = WeatherRadarVILData(
                position=position,
                value=float(row_dict['value']),
                layer_count=int(row_dict['layer_count']),
                intensity=float(row_dict['intensity']),
                show_values=bool(int(row_dict['show_values']))
            )
            logger.debug(f"[VIL_CONVERT] Created object: {vil_data}")
            logger.debug(f"[VIL_CONVERT] Object type: {type(vil_data)}")

            # Set the fields that have default factories after creation
            vil_data.request_id = str(row_dict['request_id'])
            vil_data.timestamp = float(row_dict['timestamp'])
            vil_data.additional_info = additional_info

            # Verify object state
            logger.debug(f"[VIL_CONVERT] Final object state:")
            logger.debug(f"[VIL_CONVERT] - position: {vil_data.position}")
            logger.debug(f"[VIL_CONVERT] - value: {vil_data.value}")
            logger.debug(f"[VIL_CONVERT] - layer_count: {vil_data.layer_count}")
            logger.debug(f"[VIL_CONVERT] - intensity: {vil_data.intensity}")
            logger.debug(f"[VIL_CONVERT] - show_values: {vil_data.show_values}")

            return vil_data

        except Exception as e:
            logger.error(f"Error converting row to WeatherRadarVILData: {e}")
            logger.error(f"Row data: {row_dict}")
            raise

    def get_vil_data(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> List[WeatherRadarVILData]:
        """
        Retrieve VIL data with filtering

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            min_value: Optional minimum VIL value filter
            max_value: Optional maximum VIL value filter

        Returns:
            List of WeatherRadarVILData objects matching the filters
        """
        try:
            # Log table verification
            table_exists = self._verify_table_exists()
            logger.debug(f"[VIL_DB] Table exists check: {table_exists}")

            # Log the query parameters
            logger.debug("[VIL_DB] Query parameters:")
            logger.debug(f"[VIL_DB] - Time range: {start_time} to {end_time}")
            logger.debug(f"[VIL_DB] - Value range: {min_value} to {max_value}")

            # Build query based on filters
            query_parts = ['SELECT * FROM "vil_data"']
            params = []

            where_conditions = []
            if start_time is not None and end_time is not None:
                where_conditions.append('"timestamp" BETWEEN ? AND ?')
                params.extend([start_time, end_time])
            if min_value is not None and max_value is not None:
                where_conditions.append('"value" BETWEEN ? AND ?')
                params.extend([min_value, max_value])

            if where_conditions:
                query_parts.append('WHERE ' + ' AND '.join(where_conditions))

            query_parts.append('ORDER BY "timestamp" DESC')
            query = ' '.join(query_parts)

            # Execute query
            logger.debug(f"[VIL_DB] Executing query: {query}")
            logger.debug(f"[VIL_DB] With parameters: {params}")

            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            if not results:
                logger.debug("[VIL_DB] No results found")
                return []

            logger.debug(f"[VIL_DB] Found {len(results)} results")

            # Get column names
            columns = []
            with self.radar_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(vil_data)")
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

            # Convert to WeatherRadarVILData objects
            vil_data_list = []
            for i, row_dict in enumerate(raw_data):
                try:
                    logger.debug(f"[VIL_GET] Converting row {i}: {row_dict}")
                    logger.debug(f"[VIL_GET] Row type before conversion: {type(row_dict)}")

                    vil_data = self._convert_to_vil_data(row_dict)
                    logger.debug(f"[VIL_GET] Converted object: {vil_data}")
                    logger.debug(f"[VIL_GET] Converted type: {type(vil_data)}")
                    logger.debug(f"[VIL_GET] Position attribute: {getattr(vil_data, 'position', None)}")
                    vil_data_list.append(vil_data)

                except Exception as e:
                    logger.error(f"Error converting row to WeatherRadarVILData: {e}")
                    logger.error(f"Row data: {row_dict}")
                    continue

            logger.debug(f"Successfully converted {len(vil_data_list)} records to WeatherRadarVILData objects")
            return vil_data_list

        except Exception as e:
            logger.error(f"Error retrieving VIL data: {e}")
            traceback.print_exc()
            return []

    def store_vil_data_raw(self, request_id: str, position_x: float, position_y: float,
                          value: float, layer_count: int, intensity: float,
                          timestamp: float = None, show_values: bool = True) -> bool:
        """
        Store raw VIL data directly with provided field values
        This method is used by vil_response_service to store data decoded from binary format

        Args:
            request_id: Unique ID for tracking
            position_x: X coordinate
            position_y: Y coordinate
            value: VIL value in kg/m²
            layer_count: Number of VIL layers
            intensity: Intensity on 0-1 scale
            timestamp: Optional timestamp, defaults to current time
            show_values: Whether to show values in display

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            # Critical log for test verification
            logger.debug(f"[VIL_RAW_STORE] Direct storage of raw VIL data:")
            logger.debug(f"[VIL_RAW_STORE] - request_id: {request_id}")
            logger.debug(f"[VIL_RAW_STORE] - position: ({position_x}, {position_y})")
            logger.debug(f"[VIL_RAW_STORE] - value: {value}")
            logger.debug(f"[VIL_RAW_STORE] - layer_count: {layer_count}")
            logger.debug(f"[VIL_RAW_STORE] - intensity: {intensity}")

            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = time.time()

            # Initialize additional_info with important metadata
            additional_info = {
                'source': 'vil_response_service',
                'binary_decoded': True,
                'mode': 'SURVEILLANCE',  # Default mode for VIL data
                'data_type': 'vil'
            }

            # Add command word
            from FMOFP.local_messaging.command_word_map import register_command_word
            system_id = 'displays'
            subaddress_name = 'radar_display'
            command_word = register_command_word(system_id, 0, subaddress_name, 'data', 'vil')
            additional_info['command_word'] = command_word

            # Add message type
            from FMOFP.local_messaging.message_types import WEATHER_RADAR_VIL_RESPONSE
            additional_info['message_type'] = WEATHER_RADAR_VIL_RESPONSE

            # Ensure table exists
            if not self._verify_table_exists():
                logger.warning("[VIL_RAW_STORE] Table doesn't exist, creating it")
                if not self._init_database_table():
                    logger.error("[VIL_RAW_STORE] Failed to create table")
                    return False

            # Prepare data for storage
            data = {
                'request_id': request_id,
                'timestamp': timestamp,
                'position_x': position_x,
                'position_y': position_y,
                'value': value,
                'layer_count': layer_count,
                'intensity': intensity,
                'show_values': 1 if show_values else 0,
                'additional_info': json.dumps(additional_info)
            }

            # Log for test verification
            logger.debug(f"[VIL_FLOW_DEBUG] Storing raw VIL data: position=({position_x}, {position_y}), value={value}, layer_count={layer_count}, intensity={intensity}")

            # Check if record exists
            check_query = 'SELECT COUNT(*) FROM "vil_data" WHERE "request_id" = ?'
            check_result = self.radar_db.execute_query(check_query, (request_id,), query_type='select')

            if check_result and check_result[0][0] > 0:
                # Update existing record
                logger.warning(f"[VIL_RAW_STORE] Record exists, updating: {request_id}")

                # Build update query
                update_parts = []
                for key in data.keys():
                    if key != 'request_id':
                        update_parts.append(f'"{key}" = ?')

                update_query = f'UPDATE "vil_data" SET {", ".join(update_parts)} WHERE "request_id" = ?'

                # Prepare values
                update_values = [data[key] for key in data.keys() if key != 'request_id']
                update_values.append(data['request_id'])

                # Execute update
                self.radar_db.execute_query(update_query, tuple(update_values), query_type='update', manage_transaction=True)
            else:
                # Insert new record
                logger.debug(f"[VIL_RAW_STORE] Inserting new record: {request_id}")

                # Build insert query
                fields = ', '.join([f'"{k}"' for k in data.keys()])
                placeholders = ', '.join(['?' for _ in data])
                query = f'INSERT INTO "vil_data" ({fields}) VALUES ({placeholders})'

                # Execute insert
                self.radar_db.execute_query(query, tuple(data.values()), query_type='insert', manage_transaction=True)

            # Verify storage
            verify_query = 'SELECT COUNT(*) FROM "vil_data" WHERE "request_id" = ?'
            result = self.radar_db.execute_query(verify_query, (data['request_id'],), query_type='select')

            if result and result[0][0] > 0:
                logger.info(f"[VIL_RAW_STORE] Data stored successfully: {request_id}")
                return True
            else:
                logger.error(f"[VIL_RAW_STORE] Data storage verification failed: {request_id}")
                return False

        except Exception as e:
            logger.error(f"[VIL_RAW_STORE] Error storing raw VIL data: {e}")
            logger.error(traceback.format_exc())
            return False

    def clear_old_data(self, max_age_seconds: float = 3600) -> int:
        """
        Clear VIL data older than specified age

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
            result = self.radar_db.delete_from_table('vil_data', condition)

            logger.info(f"Cleared VIL data older than {max_age_seconds} seconds")
            return result

        except Exception as e:
            logger.error(f"Error clearing old VIL data: {e}")
            traceback.print_exc()
            return 0

    def validate_message(self, message) -> bool:
        """
        Validate if the message is a valid VIL message.

        Args:
            message: The message to validate

        Returns:
            bool: True if message is valid, False otherwise
        """
        try:
            # Check if the message has a message_type that we can handle
            message_type = get_message_type(message)
            if not message_type:
                logger.warning(f"[VIL_HANDLER] Message has no message_type: {message}")
                return False

            # Check if the message type is one we can handle
            if not is_message_type(message, WEATHER_RADAR_VIL_REQUEST) and not is_message_type(message, WEATHER_RADAR_VIL_RESPONSE):
                # Use more flexible check with is_vil_message if specific type check fails
                if not is_vil_message(message):
                    logger.warning(f"[VIL_HANDLER] Message type {message_type} is not a VIL message")
                    return False

            # For response messages, check for required attributes
            if is_message_type(message, WEATHER_RADAR_VIL_RESPONSE):
                # Simple check for data attribute
                if isinstance(message, dict) and 'data' not in message:
                    logger.warning(f"[VIL_HANDLER] VIL response missing data attribute")
                    return False

            logger.debug(f"[VIL_HANDLER] Message validated as a valid VIL message: {message_type}")
            return True

        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error validating VIL message: {e}")
            logger.error(traceback.format_exc())
            return False

    def extract_and_store_binary_data(self, request_id: str, binary_data: List[int]) -> bool:
        """
        Extract and store all VIL data objects from binary format.

        Binary layout produced by DataResponseSender._encode_complex_objects:
          Word 0        : object count  (N)
          Word 1        : scale metadata (unused for VIL — reserved for future use)
          Words 2..2N+1 : pairs of (pos_word, attr_word) per object

        Position decoding:
          x = ((pos_word >> 8) & 0xFF) - 128   # undo +128 encoding offset
          y = (pos_word & 0xFF) - 128

        VIL attribute word layout (16 bits):
          Bits 15-9  (7 bits): value_code  → value = value_code * 0.5  kg/m²
          Bits  8-5  (4 bits): layer_code  → layer_count = layer_code
          Bits  4-0  (5 bits): intensity_code → intensity = intensity_code / 31.0

        Args:
            request_id: Request ID for tracking
            binary_data: List of integers containing encoded data

        Returns:
            bool: True if at least one object was stored successfully
        """
        try:
            if not binary_data or len(binary_data) < 3:
                logger.warning(f"[VIL_BINARY] Binary data too short: {len(binary_data)} words")
                return False

            # Word 0: number of objects
            object_count = binary_data[0]
            if object_count == 0:
                logger.warning("[VIL_BINARY] Object count is zero — nothing to decode")
                return False

            # Word 1: scale metadata (reserved; skip)
            # Words 2+: object pairs
            expected_size = 2 + (object_count * 2)
            if len(binary_data) < expected_size:
                logger.warning(
                    f"[VIL_BINARY] Data too short: expected {expected_size} words "
                    f"for {object_count} objects, got {len(binary_data)}"
                )
                # Decode however many complete pairs we have
                object_count = (len(binary_data) - 2) // 2

            logger.debug(f"[VIL_BINARY] Decoding {object_count} VIL objects from binary data")

            stored_count = 0
            timestamp = time.time()

            for i in range(object_count):
                pos_index  = 2 + (i * 2)
                attr_index = pos_index + 1

                if attr_index >= len(binary_data):
                    break

                pos_word  = binary_data[pos_index]
                attr_word = binary_data[attr_index]

                # Decode position — undo the +128 offset applied at encode time
                x = float((pos_word >> 8) & 0xFF) - 128.0
                y = float(pos_word & 0xFF) - 128.0

                # Decode VIL attributes — mirrors WeatherRadarVILData.to_data_words() layout:
                #   Bits 15-9  (7 bits): value_code
                #   Bits  8-5  (4 bits): layer_code
                #   Bits  4-1  (4 bits): intensity_code
                #   Bit   0    (1 bit) : show_bit
                value_code     = (attr_word >> 9) & 0x7F   # 7 bits
                layer_code     = (attr_word >> 5) & 0x0F   # 4 bits
                intensity_code = (attr_word >> 1) & 0x0F   # 4 bits
                show_bit       = attr_word & 0x01           # 1 bit

                value       = value_code * 0.5              # kg/m² (0.5 kg/m² per bit)
                layer_count = layer_code
                intensity   = intensity_code / 15.0         # 0.0–1.0
                show_values = bool(show_bit)

                object_id = f"{request_id}_{i + 1}"

                logger.debug(
                    f"[VIL_BINARY] Object {i+1}/{object_count}: "
                    f"pos=({x:.1f},{y:.1f}) value={value:.1f} "
                    f"layers={layer_count} intensity={intensity:.3f}"
                )

                success = self.store_vil_data_raw(
                    request_id=object_id,
                    position_x=x,
                    position_y=y,
                    value=value,
                    layer_count=layer_count,
                    intensity=intensity,
                    timestamp=timestamp,
                    show_values=show_values
                )

                if success:
                    stored_count += 1
                else:
                    logger.warning(f"[VIL_BINARY] Failed to store object {i+1}")

            logger.debug(f"[VIL_BINARY] Stored {stored_count}/{object_count} VIL objects")
            return stored_count > 0

        except Exception as e:
            logger.error(f"[VIL_BINARY] Error extracting and storing binary data: {e}")
            logger.debug(traceback.format_exc())
            return False

    def handle_message(self, message):
        """
        Handle a VIL data message.
        Implementation of the abstract method from BaseMessageHandler.

        Args:
            message: The message to handle

        Returns:
            bool: True if message was handled successfully, False otherwise
        """
        if not self.validate_message(message):
            logger.warning(f"[VIL_HANDLER] Invalid VIL message: {message}")
            return False

        try:
            # Log that we're handling the message
            message_type = get_message_type(message)
            logger.debug(f"[VIL_HANDLER] Handling VIL message type: {message_type}")

            # Check message type to determine action
            if is_message_type(message, WEATHER_RADAR_VIL_REQUEST):
                # Handle data request
                logger.debug("[VIL_HANDLER] Handling VIL data request")
                # Extract request parameters
                start_time = None
                end_time = None
                min_value = None
                max_value = None

                # Extract parameters if they exist in the message
                if isinstance(message, dict):
                    start_time = message.get('start_time')
                    end_time = message.get('end_time')
                    min_value = message.get('min_value')
                    max_value = message.get('max_value')

                # Get data
                data = self.get_vil_data(
                    start_time=start_time,
                    end_time=end_time,
                    min_value=min_value,
                    max_value=max_value
                )

                logger.debug(f"[VIL_HANDLER] Retrieved {len(data)} VIL data records")
                return True

            elif is_message_type(message, WEATHER_RADAR_VIL_RESPONSE):
                # Handle data response
                logger.debug("[VIL_HANDLER] Handling VIL data response")

                # Convert message to WeatherRadarVILData if needed
                if not isinstance(message, WeatherRadarVILData):
                    # Create VIL data object
                    try:
                        # Check if message is a dictionary
                        if isinstance(message, dict):
                            position = message.get('position', (0.0, 0.0))
                            if isinstance(position, list):
                                position = tuple(position)

                            # Create vil data object from dictionary
                            vil_data = WeatherRadarVILData(
                                position=position,
                                value=float(message.get('value', 0.0)),
                                layer_count=int(message.get('layer_count', 1)),
                                intensity=float(message.get('intensity', 0.0)),
                                show_values=bool(message.get('show_values', False))
                            )

                            # Set additional fields
                            vil_data.request_id = message.get('request_id', str(time.time()))
                            vil_data.timestamp = float(message.get('timestamp', time.time()))
                            vil_data.additional_info = message.get('additional_info', {})

                            # Store the data
                            result = self.store_vil_data(vil_data)
                            return result
                        else:
                            # If it's not a dictionary, log an error
                            logger.error(f"[VIL_HANDLER] Expected a dictionary message, got {type(message)}")
                            return False
                    except Exception as e:
                        logger.error(f"[VIL_HANDLER] Error creating WeatherRadarVILData from message: {e}")
                        logger.error(traceback.format_exc())
                        return False
                else:
                    # Message is already a WeatherRadarVILData object
                    result = self.store_vil_data(message)
                    return result

            # If we got here, the message type is not specifically supported
            # But we should still try if it's a valid VIL message according to is_vil_message
            if is_vil_message(message):
                logger.debug(f"[VIL_HANDLER] Handling generic VIL message: {message_type}")
                # Try to determine if it's a request or response
                if 'request' in message_type.lower():
                    logger.debug("[VIL_HANDLER] Treating as VIL request")
                    # Handle as a request - similar approach to WEATHER_RADAR_VIL_REQUEST
                    data = self.get_vil_data()
                    logger.debug(f"[VIL_HANDLER] Retrieved {len(data)} VIL data records")
                    return True
                else:
                    logger.debug("[VIL_HANDLER] Treating as VIL response")
                    # Handle as a response - try to extract data and store it
                    # This is a simplified approach
                    if isinstance(message, dict):
                        position = message.get('position', (0.0, 0.0))
                        if isinstance(position, list):
                            position = tuple(position)

                        # Create vil data object with defaults
                        vil_data = WeatherRadarVILData(
                            position=position,
                            value=float(message.get('value', 0.0)),
                            layer_count=int(message.get('layer_count', 1)),
                            intensity=float(message.get('intensity', 0.0)),
                            show_values=bool(message.get('show_values', False))
                        )

                        # Set additional fields
                        vil_data.request_id = message.get('request_id', str(time.time()))
                        vil_data.timestamp = float(message.get('timestamp', time.time()))
                        vil_data.additional_info = message.get('additional_info', {})

                        # Store the data
                        result = self.store_vil_data(vil_data)
                        return result

            # If we still couldn't handle it, log a warning
            logger.warning(f"[VIL_HANDLER] Unsupported VIL message type: {message_type}")
            return False

        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error handling VIL message: {e}")
            logger.error(traceback.format_exc())
            return False
