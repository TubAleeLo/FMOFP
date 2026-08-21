"""
Handler for precipitation data messages.

Implements standardized handling of precipitation data according to the messaging consistency plan:
- Uses centralized message type constants
- Uses address utilities for RT/SA addressing
- Implements consistent database storage and retrieval
- Follows standard message handling patterns
"""

import threading
import json
import traceback
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_messaging.base_message_handler import BaseMessageHandler
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    COMMAND_TYPE_PRECIPITATION_DATA,
    COMMAND_TYPE_PRECIPITATION_COMPLETION,
    is_precipitation_message,
    is_message_type,
    get_message_type
)
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.weather_data import (
    PrecipitationData,
    WeatherRadarPrecipitationResponse
)
from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
    get_rt_address,
    get_subaddress,
    get_rt_subaddress_pair_for_radar,
    is_radar_subsystem,
    get_system_id_for_addressing
)

logger = get_logger()

# Using the radar-local PrecipitationData from message_definitions.weather_data

class PrecipitationDataHandler(BaseMessageHandler):
    """Handler for precipitation data messages"""
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
                logger.info("[PRECIP_DB] Precipitation data table exists")
            else:
                logger.error("[PRECIP_DB] Precipitation data table does not exist")
            return exists

        except Exception as e:
            logger.error(f"[PRECIP_DB] Error verifying table: {e}")
            traceback.print_exc()
            return False

    def _init_database_table(self) -> bool:
        """Initialize precipitation data table using DatabaseManager"""
        try:
            logger.info("[PRECIP_DB] Checking precipitation data table")

            # First check if table already exists
            if self.radar_db.table_exists('precipitation_data'):
                logger.info("[PRECIP_DB] Precipitation data table already exists")
                return True

            logger.info("[PRECIP_DB] Initializing precipitation data table")

            # Create table using DBM's transaction management
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

            # Create indices for commonly queried fields
            logger.info("[PRECIP_DB] Creating indices")
            indices = [
                ('precip_timestamp_idx', 'timestamp'),
                ('precip_rate_idx', 'rate'),
                ('precip_type_idx', 'type'),
                ('precip_request_id_idx', 'request_id')
            ]

            for idx_name, column in indices:
                query = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "precipitation_data" ("{column}")'
                self.radar_db.execute_query(query, query_type='create')

            logger.info("[PRECIP_DB] Precipitation data table and indices initialized successfully")
            return True

        except Exception as e:
            logger.error(f"[PRECIP_DB] Critical error initializing precipitation table: {e}")
            logger.error(traceback.format_exc())
            return False

    def _get_rt_subaddress_for_precipitation(self, system_name=None):
        """
        Get the RT address and subaddress for precipitation data messages.

        Args:
            system_name: Optional system name, defaults to 'weather_radar'

        Returns:
            tuple: (rt_address, subaddress)
        """
        radar_system = system_name or 'weather_radar'

        # Use enhanced utility for proper subsystem handling
        rt_address, subaddress = get_rt_subaddress_pair_for_radar(radar_system, 'weather_radar')
        logger.debug(f"Using RT address {rt_address} and subaddress {subaddress} for precipitation data")

        return rt_address, subaddress

    def _get_command_word(self, target_system='displays'):
        """
        Generate command word for precipitation data using standard address utilities.

        Args:
            target_system: The target system ID, defaults to 'displays'

        Returns:
            str: The command word
        """
        from FMOFP.local_messaging.command_word_map import register_command_word

        # Use address utility functions instead of hardcoded values
        displays_rt = get_rt_address(target_system)
        radar_display_sa = get_subaddress('radar_display')

        return register_command_word(target_system, 0, 'radar_display', 'data', 'precipitation')

    def store_precipitation_data(self, precip_data: Union[PrecipitationData, Dict]) -> bool:
        """
        Store precipitation data with robust error handling

        Args:
            precip_data: PrecipitationData object or dictionary to store

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            # Convert dictionary to PrecipitationData if needed
            if isinstance(precip_data, dict):
                precip_data = PrecipitationData.from_dict(precip_data)
            # Create a copy to avoid modifying the original
            elif isinstance(precip_data, PrecipitationData):
                precip_data = PrecipitationData(
                    data_uuid=precip_data.data_uuid,
                    grid_cells=precip_data.grid_cells,
                    scan_width=precip_data.scan_width,
                    scan_height=precip_data.scan_height,
                    message_header=precip_data.message_header,
                    sending_system=precip_data.sending_system,
                    destination=precip_data.destination,
                    request_id=precip_data.request_id,
                    response_uuid=precip_data.response_uuid
                )

            logger.info(f"[PRECIP_FLOW] Starting storage of precipitation data with request_id: {precip_data.request_id}")

            # Ensure additional_info is a dictionary
            if not isinstance(precip_data.additional_info, dict):
                precip_data.additional_info = {}

            additional_info = precip_data.additional_info.copy()

            # Extract command word and add to additional_info
            command_word = additional_info.get('command_word')
            if not command_word:
                # Get command word using utility function
                command_word = self._get_command_word('displays')
                additional_info['command_word'] = command_word
                logger.info(f"[PRECIP_FLOW] Generated command word: {command_word}")

            # Add mode information if available
            if 'mode' not in additional_info:
                additional_info['mode'] = 'SURVEILLANCE'  # Default mode for precipitation data

            # Add message type information from centralized constants
            if 'message_type' not in additional_info:
                additional_info['message_type'] = WEATHER_RADAR_PRECIPITATION_RESPONSE

            # Check if we're dealing with a PrecipitationData object with expected attributes
            if hasattr(precip_data, 'position') and isinstance(precip_data.position, tuple):
                # Standard data format
                data = {
                    'request_id': precip_data.request_id,
                    'timestamp': precip_data.timestamp,
                    'position_x': precip_data.position[0],
                    'position_y': precip_data.position[1],
                    # Ensure consistent field naming - handle both 'type' and 'precip_type' attributes
                    'type': getattr(precip_data, 'type', getattr(precip_data, 'precip_type', 'rain')),
                    'rate': precip_data.rate,
                    'intensity': precip_data.intensity,
                    'show_values': 1 if getattr(precip_data, 'show_values', False) else 0,
                    'additional_info': json.dumps(additional_info)
                }
            else:
                # Handle alternative format (like from BC_transfer_aggregator)
                logger.info(f"[PRECIP_STORE] Handling alternative format precipitation data")
                # Log the available attributes to help debug
                if isinstance(precip_data, dict):
                    logger.info(f"[PRECIP_STORE] Available dict keys: {precip_data.keys()}")
                else:
                    logger.info(f"[PRECIP_STORE] Available attributes: {dir(precip_data)}")

                # Extract data using flexible approach
                position = getattr(precip_data, 'position', (0, 0))
                if isinstance(position, dict) and 'x' in position and 'y' in position:
                    position = (position['x'], position['y'])

                data = {
                    'request_id': getattr(precip_data, 'request_id', str(time.time())),
                    'timestamp': getattr(precip_data, 'timestamp', time.time()),
                    'position_x': position[0] if isinstance(position, tuple) else 0,
                    'position_y': position[1] if isinstance(position, tuple) else 0,
                    'type': getattr(precip_data, 'type', 'rain'),
                    'rate': getattr(precip_data, 'rate', 0.0),
                    'intensity': getattr(precip_data, 'intensity', 0.0),
                    'show_values': 1 if getattr(precip_data, 'show_values', False) else 0,
                    'additional_info': json.dumps(additional_info)
                }

            # Log the data being stored
            logger.info("[PRECIP_STORE] Storing precipitation data:")
            logger.info(f"[PRECIP_STORE] - request_id: {data['request_id']}")
            logger.info(f"[PRECIP_STORE] - position: ({data['position_x']}, {data['position_y']})")
            logger.info(f"[PRECIP_STORE] - type: {data['type']}")
            logger.info(f"[PRECIP_STORE] - rate: {data['rate']}")
            logger.info(f"[PRECIP_STORE] - intensity: {data['intensity']}")

            try:
                # First check if table exists, create if not
                if not self._verify_table_exists():
                    logger.error("[PRECIP_STORE] Precipitation data table does not exist - creating it")
                    if not self._init_database_table():
                        logger.error("[PRECIP_STORE] Failed to create precipitation data table")
                        return False

                # Log more detailed information about database operation
                logger.debug(f"[PRECIP_FLOW_DEBUG] Storing precipitation data with request_id: {data['request_id']}")
                logger.debug(f"[PRECIP_FLOW_DEBUG] Position: ({data['position_x']}, {data['position_y']})")
                logger.debug(f"[PRECIP_FLOW_DEBUG] Type: {data['type']}, Rate: {data['rate']}, Intensity: {data['intensity']}")

                # Check if record with same request_id already exists
                check_query = 'SELECT COUNT(*) FROM "precipitation_data" WHERE "request_id" = ?'
                check_result = self.radar_db.execute_query(check_query, (data['request_id'],), query_type='select')

                if check_result and check_result[0][0] > 0:
                    logger.warning(f"[PRECIP_STORE] Record with request_id {data['request_id']} already exists - updating")

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
                    logger.debug("[PRECIP_FLOW_DEBUG] Precipitation data stored and verified successfully")
                    # Show sample of stored data
                    sample_query = 'SELECT * FROM "precipitation_data" WHERE "request_id" = ? LIMIT 1'
                    sample_result = self.radar_db.execute_query(sample_query, (data['request_id'],), query_type='select')
                    if sample_result:
                        logger.debug(f"[PRECIP_FLOW_DEBUG] Sample of stored data: {sample_result[0]}")
                    return True
                else:
                    logger.debug("[PRECIP_FLOW_DEBUG] Precipitation data storage verification failed")
                    return False

            except Exception as e:
                logger.error(f"[PRECIP_STORE] Error during storage: {e}")
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
            # Create position tuple from x,y coordinates
            position = (float(row_dict['position_x']), float(row_dict['position_y']))

            # Parse additional_info
            try:
                additional_info = json.loads(row_dict['additional_info']) if row_dict['additional_info'] else {}
            except json.JSONDecodeError:
                additional_info = {}

            # Get precipitation info
            precip_type = str(row_dict['type'])
            rate = float(row_dict['rate'])
            intensity = float(row_dict['intensity'])

            # Create a grid cell with the precipitation data
            grid_cells = [
                {
                    'position': position,
                    'type': precip_type,
                    'rate': rate,
                    'intensity': intensity
                }
            ]

            # Create PrecipitationData object using the radar-local message class
            precip_data = PrecipitationData(
                data_uuid=str(row_dict['request_id']),
                grid_cells=grid_cells,
                scan_width=500.0,  # Default width
                scan_height=500.0, # Default height
                message_header="precipitation_data",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=str(row_dict['request_id'])
            )

            # Store additional metadata
            precip_data.timestamp = float(row_dict['timestamp'])
            precip_data.show_values = bool(int(row_dict.get('show_values', 0)))

            return precip_data

        except Exception as e:
            logger.error(f"Error converting row to WeatherRadarPrecipitationData: {e}")
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
            min_rate: Optional minimum precipitation rate filter
            max_rate: Optional maximum precipitation rate filter

        Returns:
            List of WeatherRadarPrecipitationData objects matching the filters
        """
        try:
            # Log table verification
            table_exists = self._verify_table_exists()
            logger.info(f"[PRECIP_DB] Table exists check: {table_exists}")

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
            logger.info(f"[PRECIP_DB] Executing query: {query} with params: {params}")

            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            if not results:
                logger.info("[PRECIP_DB] No results found")
                return []

            logger.info(f"[PRECIP_DB] Found {len(results)} results")

            # Get column names
            columns = []
            with self.radar_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(precipitation_data)")
                columns = [col[1] for col in cursor.fetchall()]

            # Convert results to dictionaries
            raw_data = []
            for row in results:
                row_dict = dict(zip(columns, row))
                raw_data.append(row_dict)

            # Convert to WeatherRadarPrecipitationData objects
            precip_data_list = []
            for row_dict in raw_data:
                try:
                    precip_data = self._convert_to_precipitation_data(row_dict)
                    precip_data_list.append(precip_data)
                except Exception as e:
                    logger.error(f"Error converting row to WeatherRadarPrecipitationData: {e}")
                    logger.error(f"Row data: {row_dict}")
                    continue

            logger.info(f"[PRECIP_DB] Successfully converted {len(precip_data_list)} records to WeatherRadarPrecipitationData objects")
            return precip_data_list

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

    def validate_message(self, message):
        """
        Validate if the message is a valid precipitation message.
        Enhanced to handle both object format and string data format.

        Args:
            message: The message to validate

        Returns:
            bool: True if message is valid, False otherwise
        """
        try:
            # debugging for message structure
            logger.info(f"[PRECIP_HANDLER] Validating message: {type(message)}")
            if isinstance(message, dict):
                logger.info(f"[PRECIP_HANDLER] Message keys: {list(message.keys())}")

                # Check for string format data from BC/RT transfer
                if 'data' in message and isinstance(message['data'], str):
                    logger.info(f"[PRECIP_HANDLER] Message has string data of length: {len(message['data'])}")
                    # String data from BC/RT transfer is valid for precipitation messages
                    return True

            # Check if the message has a message_type that we can handle
            message_type = get_message_type(message)
            if not message_type:
                # Enhanced check for precipitation indicators without explicit message_type
                if isinstance(message, dict):
                    metadata = message.get('metadata', {})
                    if metadata and isinstance(metadata, dict):
                        if metadata.get('precipitation_message') or metadata.get('data_type') == 'precipitation':
                            logger.info(f"[PRECIP_HANDLER] Detected precipitation message from metadata flags")
                            return True

                logger.warning(f"[PRECIP_HANDLER] Message has no message_type: {message}")
                return False

            # Check if the message type is one we can handle
            if not is_message_type(message, WEATHER_RADAR_PRECIPITATION_REQUEST) and not is_message_type(message, WEATHER_RADAR_PRECIPITATION_RESPONSE):
                # Use more flexible check with is_precipitation_message if specific type check fails
                if not is_precipitation_message(message):
                    logger.warning(f"[PRECIP_HANDLER] Message type {message_type} is not a precipitation message")
                    return False

            # For response messages, check for required attributes
            if is_message_type(message, WEATHER_RADAR_PRECIPITATION_RESPONSE):
                # check - data can be in various formats
                if isinstance(message, dict):
                    if 'data' not in message:
                        if 'frames' in message and isinstance(message['frames'], list) and len(message['frames']) > 4:
                            # Message has frames which will be processed by transfer aggregator
                            logger.info(f"[PRECIP_HANDLER] Precipitation message has frames instead of data")
                            return True
                        else:
                            logger.warning(f"[PRECIP_HANDLER] Precipitation response missing data attribute and no frames")
                            return False

            logger.info(f"[PRECIP_HANDLER] Message validated as a valid precipitation message: {message_type}")
            return True

        except Exception as e:
            logger.error(f"[PRECIP_HANDLER] Error validating precipitation message: {e}")
            logger.error(traceback.format_exc())
            return False

    def handle_message(self, message):
        """
        Handle a precipitation data message.
        Implementation of the abstract method from BaseMessageHandler.
        Enhanced to handle both object format and string data format.

        Args:
            message: The message to handle

        Returns:
            bool: True if message was handled successfully, False otherwise
        """
        # First check - log current state for debugging
        logger.info(f"[PRECIP_HANDLER] Handling message: {type(message)}")
        if isinstance(message, dict):
            # Log message structure for diagnosis
            msg_keys = list(message.keys())
            logger.info(f"[PRECIP_HANDLER] Message keys: {msg_keys}")

            # If message has metadata, check for specific indicators
            if 'metadata' in message and isinstance(message['metadata'], dict):
                metadata_keys = list(message['metadata'].keys())
                logger.info(f"[PRECIP_HANDLER] Metadata keys: {metadata_keys}")

                # Extract critical metadata flags for logging
                precip_flag = message['metadata'].get('precipitation_message', False)
                data_type = message['metadata'].get('data_type', 'unknown')
                logger.info(f"[PRECIP_HANDLER] Precipitation flag: {precip_flag}, Data type: {data_type}")

            # Check for data format and log
            if 'data' in message:
                data_type = type(message['data'])
                data_len = len(message['data']) if hasattr(message['data'], '__len__') else 'N/A'
                logger.info(f"[PRECIP_HANDLER] Data type: {data_type}, length: {data_len}")

                # Try to log first data item for diagnosis
                if isinstance(message['data'], list) and len(message['data']) > 0:
                    first_item = message['data'][0]
                    logger.info(f"[PRECIP_HANDLER] First data item type: {type(first_item)}")
                    if isinstance(first_item, dict) and 'position' in first_item:
                        logger.info(f"[PRECIP_HANDLER] First data item has position: {first_item['position']}")

        # Standard validation
        if not self.validate_message(message):
            logger.warning(f"[PRECIP_HANDLER] Invalid precipitation message: {message}")
            return False

        try:
            # Pre-process the message
            processed_message = self.pre_process_message(message)

            # Extract message type using helper function
            from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
            message_type = get_message_type(processed_message)

            # Check for BC/RT string data format
            if isinstance(processed_message, dict) and 'data' in processed_message:
                data = processed_message['data']
                if isinstance(data, str):
                    logger.info(f"[PRECIP_HANDLER] Converting string data to precipitation objects")
                    # Handle string data format from BC/RT transfer
                    try:
                        # Try to convert string data to precipitation objects
                        # Use precipitation_data_generator to reconstruct objects
                        from FMOFP.Systems.radarManagement.weather.precipitation_data_generator_sync import PrecipitationDataGenerator
                        generator = PrecipitationDataGenerator({})

                        # Use empty objects list as fallback
                        precip_objects = []

                        # Try to parse the string data
                        try:
                            import json
                            parsed_data = json.loads(data)
                            if isinstance(parsed_data, list) and len(parsed_data) > 0:
                                logger.info(f"[PRECIP_HANDLER] Successfully parsed string data into {len(parsed_data)} objects")
                                precip_objects = parsed_data
                        except Exception:
                            logger.error(f"[PRECIP_HANDLER] Failed to parse string data, using empty list")

                        # Get request ID
                        request_id = processed_message.get('request_id', str(time.time()))

                        # Create a response with the precipitation objects
                        mode = processed_message.get('metadata', {}).get('mode', 'SURVEILLANCE')
                        response = generator.create_precipitation_response(precip_objects, request_id, mode)

                        # Store in database
                        for obj in precip_objects:
                            self.store_precipitation_data(obj)

                        logger.info(f"[PRECIP_HANDLER] Stored {len(precip_objects)} precipitation objects")
                        return True
                    except Exception as e:
                        logger.error(f"[PRECIP_HANDLER] Error processing string data: {e}")
                        logger.error(traceback.format_exc())
                        return False

            # Regular processing for standard message types
            if message_type and message_type.lower() == WEATHER_RADAR_PRECIPITATION_REQUEST.lower():
                # Handle data request
                logger.info("[PRECIP_HANDLER] Handling precipitation data request")
                # Process the request logic here
                # This could involve retrieving data from the database or generating new data
                return True

            elif message_type and message_type.lower() == WEATHER_RADAR_PRECIPITATION_RESPONSE.lower():
                # Handle data response
                logger.info("[PRECIP_HANDLER] Handling precipitation data response")

                # Get message information
                request_id = getattr(processed_message, 'request_id',
                                   processed_message.get('request_id', str(time.time())))

                # Ensure additional_info is properly set
                if hasattr(processed_message, 'additional_info') and isinstance(processed_message.additional_info, dict):
                    additional_info = processed_message.additional_info.copy()
                elif isinstance(processed_message, dict) and 'metadata' in processed_message:
                    additional_info = processed_message['metadata'].copy()
                else:
                    additional_info = {}

                # Extract command word and add to additional_info
                command_word = additional_info.get('command_word')
                if not command_word:
                    # Get command word using address utils
                    command_word = self._get_command_word()
                    additional_info['command_word'] = command_word
                    logger.info(f"[PRECIP_HANDLER] Generated command word: {command_word}")

                # Add message type information if missing
                if 'message_type' not in additional_info:
                    additional_info['message_type'] = WEATHER_RADAR_PRECIPITATION_RESPONSE

                # Check if we have precipitation data objects in the message
                if isinstance(processed_message, dict) and 'data' in processed_message:
                    data = processed_message['data']
                    if isinstance(data, list) and len(data) > 0:
                        for obj in data:
                            if isinstance(obj, dict) and 'position' in obj:
                                # Store precipitation data object
                                logger.info(f"[PRECIP_HANDLER] Storing precipitation data object: {obj}")
                                self.store_precipitation_data(obj)

                return True
            else:
                # For messages without a standard type, check if it has precipitation data
                if isinstance(processed_message, dict):
                    metadata = processed_message.get('metadata', {})
                    if metadata.get('precipitation_message') or metadata.get('data_type') == 'precipitation':
                        logger.info(f"[PRECIP_HANDLER] Processing non-standard precipitation message")

                        # Extract precipitation data if available
                        if 'data' in processed_message:
                            data = processed_message['data']
                            if isinstance(data, list) and len(data) > 0:
                                for obj in data:
                                    if isinstance(obj, dict) and 'position' in obj:
                                        # Store precipitation data object
                                        logger.info(f"[PRECIP_HANDLER] Storing precipitation data object: {obj}")
                                        self.store_precipitation_data(obj)
                                return True

                logger.warning(f"[PRECIP_HANDLER] Unsupported precipitation message type: {message_type}")
                return False

        except Exception as e:
            logger.error(f"Error handling precipitation message: {e}")
            traceback.print_exc()
            return False

    def create_precipitation_response(self, precip_data_list: List[PrecipitationData], request_id: str) -> WeatherRadarPrecipitationResponse:
        """
        Create a precipitation response message from a list of precipitation data objects

        Args:
            precip_data_list: List of PrecipitationData objects
            request_id: Request ID to include in response

        Returns:
            WeatherRadarPrecipitationResponse object
        """
        try:
            # Combine all grid cells from all precipitation data objects
            combined_grid_cells = []
            for precip_data in precip_data_list:
                combined_grid_cells.extend(precip_data.grid_cells)

            # Create response message
            response = WeatherRadarPrecipitationResponse(
                data_uuid=str(time.time()),
                grid_cells=combined_grid_cells,
                scan_width=500.0,  # Default width
                scan_height=500.0, # Default height
                message_header="precipitation_response",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=request_id,
                command_type=COMMAND_TYPE_PRECIPITATION_DATA,
                command_name="WEATHER_RADAR_PRECIPITATION"
            )

            return response

        except Exception as e:
            logger.error(f"Error creating precipitation response: {e}")
            traceback.print_exc()
            # Return a minimal response in case of error
            return WeatherRadarPrecipitationResponse(
                data_uuid=str(time.time()),
                grid_cells=[],
                scan_width=0.0,
                scan_height=0.0,
                message_header="error",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=request_id
            )
