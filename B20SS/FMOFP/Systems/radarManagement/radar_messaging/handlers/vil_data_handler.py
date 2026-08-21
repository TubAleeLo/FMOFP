"""
Handler for VIL (Vertically Integrated Liquid) data messages.

Implements standardized handling of VIL data according to the messaging consistency plan:
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
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    COMMAND_TYPE_VIL_DATA,
    is_vil_message,
    is_message_type,
    get_message_type
)
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.weather_data import (
    WeatherRadarVILData,
    WeatherRadarVILResponse
)
from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
    get_rt_address, 
    get_subaddress, 
    get_rt_subaddress_pair_for_radar,
    is_radar_subsystem,
    get_system_id_for_addressing
)

logger = get_logger()

# Using the radar-local WeatherRadarVILData from message_definitions.weather_data

class VILDataHandler(BaseMessageHandler):
    """Handler for VIL data messages"""
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
                logger.info("[VIL_DB] VIL data table exists")
            else:
                logger.error("[VIL_DB] VIL data table does not exist")
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
                'layer_count': 'INTEGER NOT NULL DEFAULT 1', # Number of layers used in calculation
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

    def _get_rt_subaddress_for_vil(self, system_name=None):
        """
        Get the RT address and subaddress for VIL data messages.
        
        Args:
            system_name: Optional system name, defaults to 'weather_radar'
            
        Returns:
            tuple: (rt_address, subaddress)
        """
        radar_system = system_name or 'weather_radar'
        
        # Use enhanced utility for proper subsystem handling
        rt_address, subaddress = get_rt_subaddress_pair_for_radar(radar_system, 'weather_radar')
        logger.debug(f"Using RT address {rt_address} and subaddress {subaddress} for VIL data")
        
        return rt_address, subaddress
        
    def _get_command_word(self, target_system='displays'):
        """
        Generate command word for VIL data using standard address utilities.
        
        Args:
            target_system: The target system ID, defaults to 'displays'
            
        Returns:
            str: The command word
        """
        from FMOFP.local_messaging.command_word_map import register_command_word
        
        # Use address utility functions instead of hardcoded values
        displays_rt = get_rt_address(target_system)
        radar_display_sa = get_subaddress('radar_display')
        
        return register_command_word(target_system, 0, 'radar_display', 'data', 'vil')
    
    def store_vil_data(self, vil_data: Union[WeatherRadarVILData, Dict]) -> bool:
        """
        Store VIL data with robust error handling
        
        Args:
            vil_data: WeatherRadarVILData object or dictionary to store
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            # Convert dictionary to WeatherRadarVILData if needed
            if isinstance(vil_data, dict):
                vil_data = WeatherRadarVILData.from_dict(vil_data)
            # Create a copy to avoid modifying the original
            elif isinstance(vil_data, WeatherRadarVILData):
                vil_data = WeatherRadarVILData(
                    data_uuid=vil_data.data_uuid,
                    grid_cells=vil_data.grid_cells,
                    scan_width=vil_data.scan_width,
                    scan_height=vil_data.scan_height,
                    message_header=vil_data.message_header,
                    sending_system=vil_data.sending_system,
                    destination=vil_data.destination,
                    request_id=vil_data.request_id,
                    response_uuid=vil_data.response_uuid
                )
                
            logger.info(f"[VIL_FLOW] Starting storage of VIL data with request_id: {vil_data.request_id}")
            
            # Ensure additional_info is a dictionary
            if not isinstance(vil_data.additional_info, dict):
                vil_data.additional_info = {}
            
            additional_info = vil_data.additional_info.copy()

            # Extract command word and add to additional_info
            command_word = additional_info.get('command_word')
            if not command_word:
                # Get command word using utility function
                command_word = self._get_command_word('displays')
                additional_info['command_word'] = command_word
                logger.info(f"[VIL_FLOW] Generated command word: {command_word}")
                
            # Add mode information if available
            if 'mode' not in additional_info:
                additional_info['mode'] = 'SURVEILLANCE'  # Default mode for VIL data
                
            # Add message type information from centralized constants
            if 'message_type' not in additional_info:
                additional_info['message_type'] = WEATHER_RADAR_VIL_RESPONSE

            data = {
                'request_id': vil_data.request_id,
                'timestamp': vil_data.timestamp,
                'position_x': vil_data.position[0],
                'position_y': vil_data.position[1],
                'value': vil_data.value,
                'layer_count': vil_data.layer_count,
                'intensity': vil_data.intensity,
                'show_values': 1 if vil_data.show_values else 0,
                'additional_info': json.dumps(additional_info)
            }

            # Log the data being stored
            logger.info("[VIL_STORE] Storing VIL data:")
            logger.info(f"[VIL_STORE] - request_id: {data['request_id']}")
            logger.info(f"[VIL_STORE] - position: ({data['position_x']}, {data['position_y']})")
            logger.info(f"[VIL_STORE] - value: {data['value']}")
            logger.info(f"[VIL_STORE] - intensity: {data['intensity']}")

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
                    logger.info("[VIL_STORE] VIL data stored and verified successfully")
                    return True
                else:
                    logger.error("[VIL_STORE] VIL data storage verification failed")
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
            # Create position tuple from x,y coordinates
            position = (float(row_dict['position_x']), float(row_dict['position_y']))
            
            # Parse additional_info
            try:
                additional_info = json.loads(row_dict['additional_info']) if row_dict['additional_info'] else {}
            except json.JSONDecodeError:
                additional_info = {}
            
            # Get value and intensity
            value = float(row_dict['value'])
            intensity = float(row_dict['intensity'])
            
            # Create single grid cell with the data
            grid_cells = [
                {
                    'position': position,
                    'value': value, 
                    'intensity': intensity,
                }
            ]
            
            # Create WeatherRadarVILData object using the radar-local message class
            vil_data = WeatherRadarVILData(
                data_uuid=str(row_dict['request_id']),
                grid_cells=grid_cells,
                scan_width=500.0,  # Default width
                scan_height=500.0, # Default height
                message_header="vil_data",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=str(row_dict['request_id'])
            )
            
            # Store additional metadata in the object
            vil_data.timestamp = float(row_dict['timestamp'])
            vil_data.layer_count = int(row_dict.get('layer_count', 1))
            vil_data.show_values = bool(int(row_dict.get('show_values', 0)))
            
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
            logger.info(f"[VIL_DB] Table exists check: {table_exists}")
            
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
            logger.info(f"[VIL_DB] Executing query: {query} with params: {params}")
            
            results = self.radar_db.execute_query(query, tuple(params), query_type='select')
            if not results:
                logger.info("[VIL_DB] No results found")
                return []
                
            logger.info(f"[VIL_DB] Found {len(results)} results")
            
            # Get column names
            columns = []
            with self.radar_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(vil_data)")
                columns = [col[1] for col in cursor.fetchall()]
            
            # Convert results to dictionaries
            raw_data = []
            for row in results:
                row_dict = dict(zip(columns, row))
                raw_data.append(row_dict)
            
            # Convert to WeatherRadarVILData objects
            vil_data_list = []
            for row_dict in raw_data:
                try:
                    vil_data = self._convert_to_vil_data(row_dict)
                    vil_data_list.append(vil_data)                    
                except Exception as e:
                    logger.error(f"Error converting row to WeatherRadarVILData: {e}")
                    logger.error(f"Row data: {row_dict}")
                    continue
            
            logger.info(f"[VIL_DB] Successfully converted {len(vil_data_list)} records to WeatherRadarVILData objects")
            return vil_data_list
            
        except Exception as e:
            logger.error(f"Error retrieving VIL data: {e}")
            traceback.print_exc()
            return []

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
            
    def validate_message(self, message):
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
            
            logger.info(f"[VIL_HANDLER] Message validated as a valid VIL message: {message_type}")
            return True
            
        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error validating VIL message: {e}")
            logger.error(traceback.format_exc())
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
            logger.warning(f"Invalid VIL message: {message}")
            return False
            
        try:
            # Pre-process the message
            processed_message = self.pre_process_message(message)
            
            # Extract message type and system information
            from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
            message_type = get_message_type(processed_message)
            
            # Extract system information
            system_name = 'weather_radar'  # Default
            if isinstance(processed_message, dict) and 'metadata' in processed_message:
                if isinstance(processed_message['metadata'], dict) and 'system_type' in processed_message['metadata']:
                    system_name = processed_message['metadata']['system_type']
            
            # Get the correct RT address and subaddress for this message
            rt_address, subaddress = self._get_rt_subaddress_for_vil(system_name)
            
            # Log addressing information
            logger.debug(f"VIL message for system {system_name} using RT={rt_address}, SA={subaddress}")
            
            if message_type.lower() == WEATHER_RADAR_VIL_REQUEST.lower():
                # Handle VIL data request
                logger.info("[VIL_HANDLER] Handling VIL data request")
                # Process the request logic here
                # This could involve retrieving data from the database or generating new data
                return True
                
            elif message_type.lower() == WEATHER_RADAR_VIL_RESPONSE.lower():
                # Handle VIL data response
                logger.info("[VIL_HANDLER] Handling VIL data response")
                # Process the response logic here
                # This could involve storing data or forwarding to other systems
                return True
            
            logger.warning(f"[VIL_HANDLER] Unsupported VIL message type: {message_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error handling VIL message: {e}")
            traceback.print_exc()
            return False

    def create_vil_response(self, vil_data_list: List[WeatherRadarVILData], request_id: str) -> WeatherRadarVILResponse:
        """
        Create a VIL response message from a list of VIL data objects
        
        Args:
            vil_data_list: List of WeatherRadarVILData objects
            request_id: Request ID to include in response
            
        Returns:
            WeatherRadarVILResponse object
        """
        try:
            # Combine all grid cells from all VIL data objects
            combined_grid_cells = []
            for vil_data in vil_data_list:
                combined_grid_cells.extend(vil_data.grid_cells)
                
            # Create response message
            response = WeatherRadarVILResponse(
                data_uuid=str(time.time()),
                grid_cells=combined_grid_cells,
                scan_width=500.0,  # Default width
                scan_height=500.0, # Default height
                message_header="vil_response",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=request_id,
                command_type=COMMAND_TYPE_VIL_DATA,
                command_name="WEATHER_RADAR_VIL"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating VIL response: {e}")
            traceback.print_exc()
            # Return a minimal response in case of error
            return WeatherRadarVILResponse(
                data_uuid=str(time.time()),
                grid_cells=[],
                scan_width=0.0,
                scan_height=0.0,
                message_header="error",
                sending_system="weather_radar",
                destination="radar_handler",
                request_id=request_id
            )
