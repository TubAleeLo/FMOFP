"""
Radar Display Data Coordinator

Manages persistent storage of radar data for display purposes.
Ensures data is available between processing and drawing cycles.
"""
import time
import copy
import threading
import traceback
import uuid
from typing import Dict, List, Any, Optional

# Import display-local message types and helper functions
from ...messaging.display_message_types import (
    DISPLAY_VIL_DATA,
    DISPLAY_PRECIPITATION_DATA,
    DISPLAY_STORM_CELL_DATA,
    is_vil_message,
    is_precipitation_message
)

from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Define data type constants
DATA_TYPE_PRECIPITATION = "precipitation"
DATA_TYPE_VIL = "vil"
DATA_TYPE_CELLS = "cells"

class RadarDisplayDataCoordinator:
    """
    Manages persistent storage of radar data for display purposes.

    This coordinator ensures data is available between processing and drawing cycles,
    providing backup and recovery mechanisms for all radar data types.
    """

    def __init__(self):
        """Initialize the data coordinator with storage for common radar data types."""
        # Lock guarding self._data_store (added August 2026 re-analysis
        # round, Round 14, radar data TTL/expiration sweep). Reentrant
        # (RLock, not Lock) because store_data() periodically calls
        # self.cleanup_expired() on the same thread -- a plain Lock would
        # deadlock the calling thread on that self-call.
        self._lock = threading.RLock()
        # Main storage dictionary with data type as key
        self._data_store = {
            DATA_TYPE_PRECIPITATION: {'current': [], 'backup': [], 'ttl': 5.0},  # Time-to-live in seconds
            DATA_TYPE_VIL: {'current': [], 'backup': [], 'ttl': 5.0},
            DATA_TYPE_CELLS: {'current': [], 'backup': [], 'ttl': 5.0}
        }
        self._last_coordinator_check_log_time = 0
        self._timestamps = {}  # Track timestamps by data_id
        self._last_cleanup = time.time()
        self._cleanup_interval = 5.0

        # Counters for throttled logging
        self._log_throttle_interval = 10.0  # Log every 10 seconds
        self._data_access_counts = {
            DATA_TYPE_VIL: {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0},
            DATA_TYPE_PRECIPITATION: {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0},
            DATA_TYPE_CELLS: {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0}
        }

        # Initialize data logging collections for all data types
        self._storage_log_collections = {}
        self._retrieval_stats = {}

        # Setup log collections for each data type
        for data_type in self._data_store.keys():
            self._storage_log_collections[data_type] = {
                'last_log_time': 0,
                'log_interval': 10.0,  # Log every 10 seconds
                'stored_items': [],
                'total_stored': 0
            }

            self._retrieval_stats[data_type] = {
                'last_log_time': 0,
                'log_interval': 10.0,  # Log every 10 seconds
                'retrieve_count': 0,
                'empty_count': 0,
                'backup_used_count': 0,
                'total_items_returned': 0,
                'sample_item': None
            }

        logger.info("[RADAR_DATA_COORD] Initialized with storage for precipitation, vil, and cells data")

    def store_data(self, data_type: str, data_items: List[Any], request_id: str) -> int:
        """
        Store data items with timestamps.

        Args:
            data_type: Type of data (e.g., 'vil', 'precipitation', 'cells')
            data_items: List of data items to store
            request_id: Required request ID for tracking

        Returns:
            Number of items stored
        """
        # Validate request_id is provided and valid
        if not request_id:
            logger.error(f"[RADAR_DATA_COORD] Cannot store {data_type} data: request_id is required")
            raise ValueError("[RADAR_DATA_COORD] request_id is required")



        # Initialize counters for this data type if not already present
        if data_type not in self._data_access_counts:
            self._data_access_counts[data_type] = {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0}

        # Increment store counter
        self._data_access_counts[data_type]['store'] += 1

        if not data_items:
            logger.error(f"[RADAR_DATA_COORD] No {data_type} data items to store")
            raise ValueError(f"[RADAR_DATA_COORD] No {data_type} data items to store")


        # Locked (added Round 14, radar data TTL/expiration sweep):
        # inserting a brand-new key into self._data_store here used to
        # race with cleanup_expired()'s `for data_type, store in
        # self._data_store.items():` running on a different thread (e.g.
        # a message-handling worker thread calling store_data() for the
        # first time for a given radar type -- "targeting"/"sar"/"tfr"/
        # "aewc"/"windshear"/"turbulence" aren't pre-populated in
        # __init__ -- while the Qt GUI thread's paintEvent() is mid-way
        # through cleanup_expired()). Live-reproduced: "RuntimeError:
        # dictionary changed size during iteration" with a 2-thread
        # stress test (one thread calling store_data() with novel data
        # types, one calling cleanup_expired() in a loop).
        with self._lock:
            if data_type not in self._data_store:
                logger.info(f"[RADAR_DATA_COORD] Creating new storage for {data_type}")
                self._data_store[data_type] = {'current': [], 'backup': [], 'ttl': 30.0}
                # Initialise per-type logging collections for new data types
                self._storage_log_collections[data_type] = {
                    'last_log_time': 0, 'log_interval': 10.0,
                    'stored_items': [], 'total_stored': 0
                }
                self._retrieval_stats[data_type] = {
                    'last_log_time': 0, 'log_interval': 10.0,
                    'retrieve_count': 0, 'empty_count': 0,
                    'total_items_returned': 0, 'backup_used_count': 0,
                    'sample_item': None
                }


        # We have data and the request_id is valid, add id to each item and store
        for i, item in enumerate(data_items):
            # Skip if item already has an ID
            if (isinstance(item, dict) and 'id' in item) or (hasattr(item, 'id') and item.id):
                continue

            # Add request_id as the id for this item
            if isinstance(item, dict):
                item['id'] = f"{request_id}_{i}"
                logger.warning(f"[RADAR_DATA_COORD] Added ID to {data_type} item #{i}: {item['id']}")
            elif hasattr(item, '__dict__'):
                setattr(item, 'id', f"{request_id}_{i}")
                logger.warning(f"[RADAR_DATA_COORD] Added ID to {data_type} object #{i}: {getattr(item, 'id')}")


    # Note: cannot add attribute to simple types like int, float, etc.

        # PRE-VALIDATION: Check for ID field before processing
        missing_id_count = 0
        invalid_id_count = 0

        for i, item in enumerate(data_items):
            # Extract ID with multiple approach paths
            item_id = None

            if isinstance(item, dict) and 'id' in item:
                item_id = item['id']
            elif hasattr(item, 'id'):
                item_id = item.id

            # ID validation with detailed error reporting
            if not item_id:
                missing_id_count += 1
                logger.error(f"[RADAR_DATA_COORD] Missing ID in {data_type} item #{i}")
                if isinstance(item, dict):
                    logger.error(f"[RADAR_DATA_COORD] Item keys: {list(item.keys())}")
                elif hasattr(item, '__dict__'):
                    logger.error(f"[RADAR_DATA_COORD] Item attributes: {list(vars(item).keys())}")
            elif item_id == 'unknown':
                invalid_id_count += 1
                logger.error(f"[RADAR_DATA_COORD] Invalid 'unknown' ID in {data_type} item #{i}")

        # Abort if any items are missing ID
        if missing_id_count > 0 or invalid_id_count > 0:
            logger.error(f"[RADAR_DATA_COORD] Cannot store {data_type} data: {missing_id_count} items missing ID, {invalid_id_count} with 'unknown' ID")
            logger.error(f"[RADAR_DATA_COORD] Items must have valid IDs set upstream before reaching the coordinator")
            raise ValueError(f"[RADAR_DATA_COORD] {missing_id_count} items missing ID, {invalid_id_count} with 'unknown' ID")

        # Process and store each data item - add extra debugging for problematic data types
        logger.debug(f"[RADAR_DATA_COORD] Processing {len(data_items)} items for data_type: {data_type}")
        processed_items = self._process_items(data_items, data_type)
        logger.debug(f"[RADAR_DATA_COORD] Processed {len(processed_items)} items for {data_type}")

        # Update both current and backup stores
        try:
            # Locked (Round 14): also closes a narrower lost-update race
            # against cleanup_expired()'s per-type filter-and-reassign --
            # without this, a store_data() write here could be silently
            # clobbered by a concurrent cleanup_expired() that read the
            # prior (now-stale) list before this write landed.
            with self._lock:
                self._data_store[data_type]['current'] = processed_items
                self._data_store[data_type]['backup'] = copy.deepcopy(processed_items)
            logger.debug(f"[RADAR_DATA_COORD] Successfully stored {len(processed_items)} {data_type} items in both stores")
        except Exception as e:
            logger.error(f"[RADAR_DATA_COORD] Error storing {data_type} data: {str(e)}")
            logger.error(traceback.format_exc())

        # Also backup the timestamps for these items
        backup_timestamps = {}
        for item in processed_items:
            item_id = item.get('id')
            if item_id and item_id in self._timestamps:
                backup_timestamps[item_id] = self._timestamps[item_id]

        # Store backup timestamps in the data store
        if 'backup_timestamps' not in self._data_store[data_type]:
            self._data_store[data_type]['backup_timestamps'] = {}
        self._data_store[data_type]['backup_timestamps'] = backup_timestamps

        # Store collected information about data for throttled logging for all data types
        # Add these items to the collection for this data type
        for item in processed_items:
            # Only store essential info to avoid oversized logs
            simple_item = {
                'position': item.get('position', (0.0, 0.0)),
                'id': item.get('id', 'unknown')
            }

            # Add type-specific properties
            if data_type == DATA_TYPE_PRECIPITATION:
                simple_item['type'] = item.get('type', 'unknown')
                simple_item['rate'] = item.get('rate', 0.0)
            elif data_type == DATA_TYPE_VIL:
                simple_item['value'] = item.get('value', 0.0)
                simple_item['intensity'] = item.get('intensity', 0.0)
            elif data_type == DATA_TYPE_CELLS:
                simple_item['intensity'] = item.get('intensity', 0.0)

            self._storage_log_collections[data_type]['stored_items'].append(simple_item)


        # Warn about suspicious items but do not raise — _process_items already filters
        # (0,0) positions and 'unknown' IDs; raising here would silently drop valid batches.
        for _chk_item in processed_items:
            if _chk_item.get('position') == (0.0, 0.0) or _chk_item.get('id') == 'unknown':
                logger.warning(
                    f"[RADAR_DATA_COORD] Suspicious item survived processing: "
                    f"position={_chk_item.get('position')}, id={_chk_item.get('id')}"
                )

        self._storage_log_collections[data_type]['total_stored'] += len(processed_items)

        # Check if it's time to log the collected data
        current_time = time.time()
        if current_time - self._storage_log_collections[data_type]['last_log_time'] >= self._storage_log_collections[data_type]['log_interval']:
            logger.info(f"[RADAR_DATA_COORD] {data_type.upper()} STORAGE SUMMARY:")
            logger.debug(f"  - Total stored since last log: {self._storage_log_collections[data_type]['total_stored']}")
            logger.debug(f"  - Current collection has {len(self._storage_log_collections[data_type]['stored_items'])} items")

            # Log a sample of the collection (up to 5 items)
            sample_size = min(5, len(self._storage_log_collections[data_type]['stored_items']))
            if sample_size > 0:
                logger.debug(f"  - Sample of {sample_size} stored items:")
                for i in range(sample_size):
                    logger.debug(f"    Item {i}: {self._storage_log_collections[data_type]['stored_items'][i]}")

            # Reset collection after logging
            self._storage_log_collections[data_type]['stored_items'] = []
            self._storage_log_collections[data_type]['total_stored'] = 0
            self._storage_log_collections[data_type]['last_log_time'] = current_time

        # Always log storage operations as they're important
        logger.info(f"[RADAR_DATA_COORD] Stored {len(processed_items)} {data_type} data points (request_id: {request_id})")

        # Perform cleanup if needed
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_expired()
            self._last_cleanup = current_time

        return len(processed_items)

    def get_data(self, data_type: str, use_backup: bool = True) -> List[Dict[str, Any]]:
        """
        Get data, optionally from backup if primary is empty.

        Args:
            data_type: Type of data to retrieve
            use_backup: Whether to use backup data if current is empty

        Returns:
            List of data items
        """
        # Initialize counters for this data type if not already present
        if data_type not in self._data_access_counts:
            self._data_access_counts[data_type] = {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0}

        # Increment get counter
        self._data_access_counts[data_type]['get'] += 1

        if data_type not in self._data_store:
            # Only log this error without throttling as it's a serious issue
            logger.warning(f"[RADAR_DATA_COORD] No storage found for {data_type}")
            return []

        current_time = time.time()
        should_log = current_time - self._last_coordinator_check_log_time >= self._log_throttle_interval

        # Get current data
        data = self._data_store[data_type]['current']

        # If current data is empty but we have backup and use_backup is True, use backup
        if (not data or len(data) == 0) and use_backup:
            backup_data = self._data_store[data_type]['backup']

            if backup_data and len(backup_data) > 0:
                # Add enhanced expiration check for backup data
                current_time = time.time()
                ttl = self._data_store[data_type]['ttl']
                fresh_backup = []

                # Check if we have backup timestamps
                backup_timestamps = self._data_store[data_type].get('backup_timestamps', {})

                for item in backup_data:
                    item_id = item.get('id')
                    if item_id in backup_timestamps:
                        item_age = current_time - backup_timestamps[item_id]
                        if item_age < ttl:
                            fresh_backup.append(item)
                    elif item_id in self._timestamps:
                        # Fall back to primary timestamps if backup doesn't have it
                        item_age = current_time - self._timestamps[item_id]
                        if item_age < ttl:
                            fresh_backup.append(item)
                    else:
                        # Add items with no timestamp (should be rare)
                        # Give them a new timestamp
                        self._timestamps[item_id] = current_time
                        fresh_backup.append(item)

                # Only use backup if we have fresh items
                if fresh_backup:
                    # Increment backup used counter
                    self._data_access_counts[data_type]['backup_used'] += 1

                    # Log specifics about expired vs fresh backup items
                    expired_count = len(backup_data) - len(fresh_backup)

                    if expired_count > 0:
                        logger.warning(f"[RADAR_DATA_COORD] Filtered out {expired_count} expired {data_type} items from backup")

                    logger.warning(f"[RADAR_DATA_COORD] Restored {len(fresh_backup)} {data_type} data points from backup")

                    # Update current with fresh backup data only
                    self._data_store[data_type]['current'] = copy.deepcopy(fresh_backup)
                    data = self._data_store[data_type]['current']
                else:
                    logger.warning(f"[RADAR_DATA_COORD] All {len(backup_data)} backup {data_type} items were expired, not using backup")

        # Throttled logging for all data type retrievals
        # Update retrieval stats for this data type
        self._retrieval_stats[data_type]['retrieve_count'] += 1
        if not data or len(data) == 0:
            self._retrieval_stats[data_type]['empty_count'] += 1
        else:
            self._retrieval_stats[data_type]['total_items_returned'] += len(data)
            # Store a sample item from this batch
            if len(data) > 0 and not self._retrieval_stats[data_type]['sample_item']:
                # Only store essential info to avoid oversized logs
                item = data[0]
                sample_item = {
                    'position': item.get('position', (0.0, 0.0)),
                    'id': item.get('id', 'unknown')
                }

                # Add type-specific properties
                if data_type == DATA_TYPE_PRECIPITATION:
                    sample_item['type'] = item.get('type', 'unknown')
                    sample_item['rate'] = item.get('rate', 0.0)
                elif data_type == DATA_TYPE_VIL:
                    sample_item['value'] = item.get('value', 0.0)
                    sample_item['intensity'] = item.get('intensity', 0.0)
                elif data_type == DATA_TYPE_CELLS:
                    sample_item['intensity'] = item.get('intensity', 0.0)

                self._retrieval_stats[data_type]['sample_item'] = sample_item

        # Check if backup was used
        if (not data or len(data) == 0) and use_backup:
            backup_data = self._data_store[data_type]['backup']
            if backup_data and len(backup_data) > 0:
                self._retrieval_stats[data_type]['backup_used_count'] += 1

        # Log stats periodically
        current_time = time.time()
        if current_time - self._retrieval_stats[data_type]['last_log_time'] >= self._retrieval_stats[data_type]['log_interval']:
            logger.debug(f"[RADAR_DATA_COORD] {data_type.upper()} RETRIEVAL SUMMARY:")
            logger.debug(f"  - Retrieval attempts: {self._retrieval_stats[data_type]['retrieve_count']}")
            logger.debug(f"  - Empty results: {self._retrieval_stats[data_type]['empty_count']}")
            logger.debug(f"  - Backup used: {self._retrieval_stats[data_type]['backup_used_count']}")
            logger.debug(f"  - Total items returned: {self._retrieval_stats[data_type]['total_items_returned']}")

            if self._retrieval_stats[data_type]['sample_item']:
                logger.debug(f"  - Sample item: {self._retrieval_stats[data_type]['sample_item']}")

            # Check current and backup data for this logging cycle
            logger.debug(f"  - Current data size: {len(self._data_store[data_type]['current'])}")
            logger.debug(f"  - Backup data size: {len(self._data_store[data_type]['backup'])}")
            logger.debug(f"  - Current use_backup setting: {use_backup}")

            # Reset stats
            self._retrieval_stats[data_type] = {
                'last_log_time': current_time,
                'log_interval': 10.0,
                'retrieve_count': 0,
                'empty_count': 0,
                'backup_used_count': 0,
                'total_items_returned': 0,
                'sample_item': None
            }

        # Track empty data access
        if not data or len(data) == 0:
            self._data_access_counts[data_type]['empty'] += 1

        # Throttled logging
        if should_log:
            # Log accumulated stats since last log
            logger.info(f"[RADAR_DATA_COORD] {data_type} stats: get={self._data_access_counts[data_type]['get']}, " +
                       f"store={self._data_access_counts[data_type]['store']}, " +
                       f"empty={self._data_access_counts[data_type]['empty']}, " +
                       f"backup_used={self._data_access_counts[data_type]['backup_used']}")

            if data and len(data) > 0:
                logger.info(f"[RADAR_DATA_COORD] Retrieved {len(data)} {data_type} data points")
            else:
                logger.info(f"[RADAR_DATA_COORD] No {data_type} data available")

            # Reset counters after logging
            self._data_access_counts[data_type] = {'get': 0, 'store': 0, 'empty': 0, 'backup_used': 0}
            self._last_coordinator_check_log_time = current_time

        return data

    def _process_items(self, items: List[Any], data_type: str) -> List[Dict[str, Any]]:
        """
        Process items for storage, ensuring proper format.

        Args:
            items: List of data items to process
            data_type: Type of data being processed

        Returns:
            List of processed items in dictionary format with valid positions
        """
        current_time = time.time()
        processed_items = []
        filtered_count = 0

        # Enhanced logging for processing operation
        logger.debug(f"[RADAR_DATA_COORD] Processing {len(items)} {data_type} items with enhanced validation")

        for item in items:
            # Handle binary string data specially - with improved detection
            if isinstance(item, str) and (
                all(c in '01' for c in item.replace(' ', '')) or  # Original check
                (len(item) >= 16 and all(c in '01' for c in item)) or  # Standard binary format
                (item.startswith('0') and '1' in item)  # Most common binary format in MIL-STD-1553B
            ):
                logger.warning(f"[RADAR_DATA_COORD] Detected binary string: {item}")

                # Parse the binary string into coordinates and properties
                try:
                    # Clean the binary string - keep only 0 and 1
                    clean_binary = ''.join(c for c in item if c in '01')

                    # Log the cleaned binary string for debugging
                    logger.warning(f"[RADAR_DATA_COORD] Cleaned binary: {clean_binary}")

                    # Ensure minimum length for position data
                    if len(clean_binary) < 16:
                        # If binary string is too short, pad it with zeros to reach minimum length
                        clean_binary = clean_binary.zfill(16)
                        logger.warning(f"[RADAR_DATA_COORD] Padded binary string to minimum length: {clean_binary}")

                    # Extract position data - first 16 bits (8 for X, 8 for Y)
                    x_bits = clean_binary[:8]
                    y_bits = clean_binary[8:16]

                    # Convert to int and apply offset based on protocol (matching transfer aggregator)
                    x_coord = int(x_bits, 2) - 128.0
                    y_coord = int(y_bits, 2) - 128.0

                    # Log the parsed coordinates
                    logger.warning(f"[RADAR_DATA_COORD] Extracted coordinates: ({x_coord}, {y_coord})")

                    # Create the item dictionary with proper format
                    item_dict = {
                        'position': (x_coord, y_coord),
                        'id': f"{data_type}_{str(uuid.uuid4())[:8]}"
                    }

                    # Set default values that will be overridden if available in binary
                    item_dict['type'] = 'rain'  # Default type
                    item_dict['precip_type'] = 'rain'  # Default type (duplicate field)
                    item_dict['rate'] = 0.5  # Default rate
                    item_dict['intensity'] = 0.5  # Default intensity
                    item_dict['show_values'] = True  # Default to showing values

                    # Extract precipitation type, rate, and other fields if enough data
                    if data_type == DATA_TYPE_PRECIPITATION and len(clean_binary) >= 26:
                        type_bits = clean_binary[16:20]
                        rate_bits = clean_binary[20:26]

                        # Map type value to precipitation type
                        type_value = int(type_bits, 2)
                        precip_types = ['rain', 'snow', 'sleet', 'hail']
                        if type_value < len(precip_types):
                            item_dict['type'] = precip_types[type_value]
                            item_dict['precip_type'] = precip_types[type_value]
                            logger.warning(f"[RADAR_DATA_COORD] Extracted type: {item_dict['type']} (value: {type_value})")

                        # Extract rate with proper scaling factor (matching transfer aggregator)
                        rate_value = int(rate_bits, 2) * 0.01  # Scale factor from logs
                        item_dict['rate'] = rate_value
                        logger.warning(f"[RADAR_DATA_COORD] Extracted rate: {rate_value} (bits: {rate_bits})")

                    # Extract intensity if available
                    if len(clean_binary) >= 32:
                        intensity_bits = clean_binary[26:32]
                        # Use the correct scaling factor from the logs (1/5000.0 according to transfer aggregator)
                        intensity_value = int(intensity_bits, 2) * 0.0002
                        item_dict['intensity'] = min(intensity_value, 1.0)  # Cap at 1.0
                        logger.warning(f"[RADAR_DATA_COORD] Extracted intensity: {intensity_value} (bits: {intensity_bits})")

                    # Add to processed items - even with 0,0 coordinates (removed position filter)
                    logger.warning(f"[RADAR_DATA_COORD] Created precipitation object from binary: {item_dict}")
                    processed_items.append(item_dict)

                except Exception as e:
                    logger.error(f"[RADAR_DATA_COORD] Error processing binary string: {str(e)}")
                    logger.error(traceback.format_exc())

                # Continue to next item - we've processed this binary string or logged the error
                continue

            # Standard object processing for non-string items
            if not isinstance(item, dict) and hasattr(item, '__dict__'):
                item_dict = dict(vars(item))  # copy to prevent upstream mutation
            else:
                item_dict = item if isinstance(item, dict) else {}

            # ENHANCED POSITION EXTRACTION: Multiple levels of validation
            position = None
            position_source = "unknown"

            try:
                # Try to get position from dict first
                if isinstance(item, dict) and 'position' in item:
                    position = item['position']
                    position_source = "dict_key"
                # Then try object attribute
                elif hasattr(item, 'position'):
                    position = item.position
                    position_source = "object_attribute"
                # Look for alternative coordinates if position isn't found
                elif isinstance(item, dict) and all(k in item for k in ['x', 'y']):
                    position = (item['x'], item['y'])
                    position_source = "xy_coordinates"
                elif hasattr(item, 'x') and hasattr(item, 'y'):
                    position = (item.x, item.y)
                    position_source = "xy_attributes"

                # Log the position source and value
                logger.info(f"[RADAR_DATA_COORD] Position source: {position_source}, value: {position}")
            except Exception as e:
                logger.error(f"[RADAR_DATA_COORD] Error extracting position: {str(e)}")
                position = None

            # ENHANCED POSITION VALIDATION: Convert to proper tuple
            try:
                if position is not None:
                    if hasattr(position, 'tolist'):  # numpy array
                        item_dict['position'] = tuple(position.tolist())
                        logger.info(f"[RADAR_DATA_COORD] Converted numpy array to tuple: {item_dict['position']}")
                    elif isinstance(position, (list, tuple)) and len(position) >= 2:
                        item_dict['position'] = tuple(position)
                        logger.info(f"[RADAR_DATA_COORD] Used tuple/list position: {item_dict['position']}")
                    else:
                        logger.warning(f"[RADAR_DATA_COORD] Invalid position format: {position}, using default")
                        item_dict['position'] = (0.0, 0.0)  # Default position
                else:
                    logger.warning(f"[RADAR_DATA_COORD] No position found, using default")
                    item_dict['position'] = (0.0, 0.0)  # Default position
            except Exception as e:
                logger.error(f"[RADAR_DATA_COORD] Error validating position: {str(e)}")
                item_dict['position'] = (0.0, 0.0)  # Default position on exception

            # Convert numpy values to Python native types
            for key in ['value', 'intensity', 'layer_count']:
                if key in item_dict and hasattr(item_dict[key], 'item'):
                    item_dict[key] = item_dict[key].item()
                elif hasattr(item, key):
                    val = getattr(item, key)
                    if hasattr(val, 'item'):  # numpy scalar
                        item_dict[key] = val.item()
                    else:
                        item_dict[key] = val

            # Ensure show_values is a boolean
            if 'show_values' in item_dict and hasattr(item_dict['show_values'], 'item'):
                item_dict['show_values'] = bool(item_dict['show_values'].item())
            elif hasattr(item, 'show_values'):
                show_val = item.show_values
                if hasattr(show_val, 'item'):  # numpy boolean
                    item_dict['show_values'] = bool(show_val.item())
                else:
                    item_dict['show_values'] = bool(show_val)
            else:
                item_dict['show_values'] = True  # Default to showing values

            # Ensure required fields have default values if missing
            if data_type == DATA_TYPE_VIL or is_vil_message(item_dict):
                if 'value' not in item_dict:
                    item_dict['value'] = 10.0  # Default value
                if 'intensity' not in item_dict:
                    item_dict['intensity'] = 0.5  # Default intensity
                if 'layer_count' not in item_dict:
                    item_dict['layer_count'] = 1  # Default layer count
            elif data_type == DATA_TYPE_PRECIPITATION or is_precipitation_message(item_dict):
                # ENHANCED FIELD MAPPING: Ensure both 'type' and 'precip_type' fields always exist
                # and contain the same value to fix display rendering issues

                # Determine the actual precipitation type from either field
                precip_type_value = None
                if 'precip_type' in item_dict:
                    precip_type_value = item_dict['precip_type']
                    logger.info(f"[RADAR_DATA_COORD] Found precip_type field with value: {precip_type_value}")
                elif 'type' in item_dict:
                    precip_type_value = item_dict['type']
                    logger.info(f"[RADAR_DATA_COORD] Found type field with value: {precip_type_value}")
                else:
                    precip_type_value = 'rain'  # Default if neither field exists
                    logger.warning(f"[RADAR_DATA_COORD] No type field found, using default: {precip_type_value}")

                # Set both fields to the same value to ensure consistency
                item_dict['type'] = precip_type_value
                item_dict['precip_type'] = precip_type_value

                # Handle numeric values with minimal defaults - only if it's actually precipitation data
                if isinstance(item, (int, float)) and data_type == DATA_TYPE_PRECIPITATION:
                    # Only use the actual information we have - the rate value
                    # Don't add position defaults - this signals we don't have valid coordinates
                    # and the item should be filtered out later
                    item_dict = {
                        'rate': float(item),
                        'id': f"precipitation_{str(uuid.uuid4())[:8]}"
                    }
                    logger.warning(f"[RADAR_DATA_COORD] Extracted rate {item_dict['rate']} from numeric value")

                # Log the field mapping for debugging
                logger.info(f"[RADAR_DATA_COORD] Synchronized precipitation type fields: type={item_dict['type']}, precip_type={item_dict['precip_type']}")

                # NOTE: previously flagged with "check if this is necessary
                # or if this is cheating". Investigated: PrecipitationAnalyzer
                # (radar_messaging/precipitation_analysis.py) computes a real
                # Marshall-Palmer rate and a real intensity for every point it
                # successfully analyzes, so under normal operation these two
                # fields are already present by the time an item reaches here
                # and this fallback doesn't fire. It previously fired far more
                # than intended because of a real bug: weather_radar.py was
                # passing a 3D reflectivity array into PrecipitationAnalyzer
                # (which requires 2D), causing analysis to fail and return no
                # points at all - fixed separately (see weather_radar.py
                # _process_mapping_data). With that fixed, this remains as
                # what it always should have been: a display-layer safety net
                # for genuinely incomplete/degraded upstream data, not a
                # substitute for real analysis. Keeping it - a display item
                # missing rate/intensity should still render rather than be
                # dropped or crash the paint path.
                if 'rate' not in item_dict:
                    item_dict['rate'] = 20.0  # Default rate in mm/hr
                if 'intensity' not in item_dict:
                    item_dict['intensity'] = 0.5  # Default intensity

                # Ensure all precipitation data points have the required fields
                # This ensures consistency in the display rendering
                required_fields = ['position', 'type', 'precip_type', 'rate', 'intensity', 'show_values']
                for field in required_fields:
                    if field not in item_dict:
                        if field == 'position':
                            item_dict[field] = (0.0, 0.0)
                        elif field in ['type', 'precip_type']:
                            item_dict[field] = 'rain'
                        elif field == 'rate':
                            item_dict[field] = 20.0
                        elif field == 'intensity':
                            item_dict[field] = 0.7
                        elif field == 'show_values':
                            item_dict[field] = True
                        logger.warning(f"[RADAR_DATA_COORD] Added missing required field {field} to precipitation data")

            # Ensure position is never None at this point
            if 'position' not in item_dict or item_dict['position'] is None:
                logger.error(f"[RADAR_DATA_COORD] Position still None or missing after processing, setting default")
                item_dict['position'] = (0.0, 0.0)  # Default position as fallback

            # Validate tuple format - ensure it can be unpacked as x,y
            try:
                if not isinstance(item_dict['position'], tuple) or len(item_dict['position']) < 2:
                    logger.error(f"[RADAR_DATA_COORD] Position not a valid tuple: {item_dict['position']}, fixing")
                    # Try to convert to tuple if possible
                    if isinstance(item_dict['position'], list) and len(item_dict['position']) >= 2:
                        item_dict['position'] = tuple(item_dict['position'])
                    else:
                        item_dict['position'] = (0.0, 0.0)  # Default position
            except Exception as e:
                logger.error(f"[RADAR_DATA_COORD] Error validating position tuple: {str(e)}")
                item_dict['position'] = (0.0, 0.0)  # Default position

            # Add to processed items
            processed_items.append(item_dict)

        # FINAL VALIDATION PASS: Ensure all items have valid positions
        for i, item_dict in enumerate(processed_items):
            try:
                # Check position exists and is properly formatted
                if 'position' not in item_dict or item_dict['position'] is None:
                    logger.error(f"[RADAR_DATA_COORD] FINAL CHECK: Item {i} missing position, fixing")
                    item_dict['position'] = (0.0, 0.0)

                # Validate position can be unpacked as x,y
                if not isinstance(item_dict['position'], tuple) or len(item_dict['position']) < 2:
                    logger.error(f"[RADAR_DATA_COORD] FINAL CHECK: Item {i} has invalid position {item_dict['position']}, will be filtered out")
                    # Mark for removal instead of setting default position
                    processed_items[i] = None
                    filtered_count += 1
                    continue

                # Final sanity test - try to unpack the position and check for zeros
                x, y = item_dict['position']
                # Filter out (0.0, 0.0) positions as requested
                if x == 0.0 and y == 0.0:
                    logger.warning(f"[RADAR_DATA_COORD] FINAL CHECK: Item {i} has (0.0, 0.0) position, filtering out")
                    processed_items[i] = None
                    filtered_count += 1
                    continue

                logger.info(f"[RADAR_DATA_COORD] Position check passed for item {i}: ({x}, {y})")
            except Exception as e:
                logger.error(f"[RADAR_DATA_COORD] FINAL CHECK: Error unpacking position for item {i}: {str(e)}")
                processed_items[i] = None  # Mark for removal instead of setting default
                filtered_count += 1

        # Remove all items marked as None (filtered out)
        processed_items = [item for item in processed_items if item is not None]

        logger.debug(f"[RADAR_DATA_COORD] Finished processing: {len(processed_items)} valid items retained, {filtered_count} filtered out")
        return processed_items

    def cleanup_expired(self) -> None:
        """Remove expired data based on TTL."""
        with self._lock:  # Round 14 fix, see store_data() for the reproduced-crash writeup
            current_time = time.time()
            expired_count = 0

            # Track if we have any data to clean up
            has_data = False
            for data_type, store in self._data_store.items():
                if len(store['current']) > 0:
                    has_data = True
                    break

            # Skip all processing if no data to clean up
            if not has_data:
                return

            # Track if we should log this cleanup cycle
            # Only log every 10 seconds to reduce spam
            should_log_cycle = False
            if not hasattr(self, '_last_cleanup_log_time'):
                self._last_cleanup_log_time = 0

            if current_time - self._last_cleanup_log_time >= 10.0:
                should_log_cycle = True
                self._last_cleanup_log_time = current_time

            for data_type, store in self._data_store.items():
                ttl = store['ttl']
                current_data = store['current']

                # Skip if no data for this type
                if not current_data:
                    continue

                # Filter out expired items
                valid_items = []
                expired_items_for_type = 0

                for item in current_data:
                    # Ensure item has an ID
                    item_id = item.get('id')
                    if not item_id:

                        raise ValueError("[RADAR_DATA_COORD] Item missing ID, cannot process")
                    # Now check if we have a timestamp for this ID
                    if item_id in self._timestamps:
                        item_age = current_time - self._timestamps[item_id]
                        if item_age < ttl:
                            valid_items.append(item)
                        else:
                            expired_count += 1
                            expired_items_for_type += 1
                            # Remove timestamp entry
                            del self._timestamps[item_id]
                    else:
                        # Add a timestamp for this ID with full TTL
                        self._timestamps[item_id] = current_time  # Set to expire after full TTL
                        valid_items.append(item)
                        if should_log_cycle:
                            logger.debug(f"[RADAR_DATA_COORD] Added missing timestamp for {data_type} item")

                # Update current data with valid items
                store['current'] = valid_items

                # Only log if we actually removed items and should log this cycle
                if expired_items_for_type > 0 and should_log_cycle:
                    logger.info(f"[RADAR_DATA_COORD] Cleanup: {data_type} has {len(valid_items)} items (-{expired_items_for_type})")

            # Only log cleanup results if we actually removed something
            if expired_count > 0:
                logger.info(f"[RADAR_DATA_COORD] Cleanup complete: removed {expired_count} expired data points")

    def reset_data(self, data_type: str = None) -> None:
        """
        Reset data for a specific type or all types if none specified.

        Args:
            data_type: Type of data to reset, or None to reset all
        """
        try:
            # Locked (Round 14, radar data TTL/expiration sweep): the
            # `for type_name in self._data_store.keys():` iteration below
            # has the same concurrent-new-key-insertion crash risk as
            # cleanup_expired() -- see store_data() for the live-reproduced
            # writeup. reset_data() is reachable from the GUI thread via
            # WeatherRadarWidget's reset path while a worker thread could
            # be mid-store_data() for a not-yet-seen data type.
            with self._lock:
                if data_type is None:
                    # Reset all data types
                    logger.warning("[RADAR_DATA_COORD] Resetting all data types")
                    for type_name in self._data_store.keys():
                        self._data_store[type_name]['current'] = []
                        self._data_store[type_name]['backup'] = []
                        logger.warning(f"[RADAR_DATA_COORD] Reset {type_name} data")

                    # Clear all timestamps
                    timestamp_count = len(self._timestamps)
                    self._timestamps.clear()
                    logger.warning(f"[RADAR_DATA_COORD] Cleared {timestamp_count} timestamps")
                else:
                    # Reset specific data type
                    if data_type in self._data_store:
                        self._data_store[data_type]['current'] = []
                        self._data_store[data_type]['backup'] = []
                        logger.warning(f"[RADAR_DATA_COORD] Reset {data_type} data")

                        # Clear timestamps for this data type
                        # This is more complex as timestamps are stored by ID, not type
                        # So we need to identify IDs that belong to this type
                        to_remove = []
                        for item_id in self._timestamps:
                            if item_id.startswith(f"{data_type}_"):
                                to_remove.append(item_id)

                        # Remove identified timestamps
                        for item_id in to_remove:
                            del self._timestamps[item_id]

                        logger.warning(f"[RADAR_DATA_COORD] Cleared {len(to_remove)} timestamps for {data_type}")
                    else:
                        logger.warning(f"[RADAR_DATA_COORD] No storage found for {data_type} during reset")
        except Exception as e:
            logger.error(f"[RADAR_DATA_COORD] Error resetting data: {str(e)}")
            logger.error(traceback.format_exc())

# Global instance
_radar_display_data_coordinator = None

def get_radar_display_data_coordinator():
    """Get the global RadarDisplayDataCoordinator instance."""
    global _radar_display_data_coordinator
    if _radar_display_data_coordinator is None:
        _radar_display_data_coordinator = RadarDisplayDataCoordinator()
    return _radar_display_data_coordinator
