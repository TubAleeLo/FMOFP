"""
Cell data processor for weather radar display.
Handles various formats of weather cell data.
"""
import time
import traceback
from typing import Any, Dict, List, Optional

from Utils.logger.sys_logger import get_logger

logger = get_logger()

class CellDataProcessor:
    """Process weather cell data for weather radar display."""

    def __init__(self, data_coordinator, settings_manager, log_throttler):
        """
        Initialize cell data processor.

        Args:
            data_coordinator: The radar display data coordinator instance
            settings_manager: The visual settings manager instance
            log_throttler: The log throttler instance for rate-limited logging
        """
        self._data_coordinator = data_coordinator
        self._settings_manager = settings_manager
        self._log_throttler = log_throttler

    async def process_data(self, data: Any, node_name: str) -> List[Dict[str, Any]]:
        """
        Process cell data from various formats.

        CRITICAL: Only passes through data as received - makes no modifications.

        Args:
            data: Data to process
            node_name: Source node name

        Returns:
            The processed cell data, or empty list if no valid data found
        """
        logger.debug(f"[CELL_PROCESSOR] Processing data of type: {type(data).__name__}")

        # Extract request_id from the data if available - NEVER generate one
        request_id = None
        if isinstance(data, dict) and 'request_id' in data:
            request_id = data['request_id']
        elif hasattr(data, 'request_id'):
            request_id = data.request_id

        # CASE 1: Direct list of cell dictionaries (most common case)
        if isinstance(data, list) and len(data) > 0:
            if all(isinstance(item, dict) for item in data):
                # Check for position or x/y coordinates
                position_check = all('position' in item or ('x' in item and 'y' in item) for item in data)
                if position_check:
                    logger.debug(f"[CELL_PROCESSOR] Found direct list of {len(data)} cell data points")

                    # Store the data EXACTLY as received - no modifications
                    try:
                        if not request_id:
                            # If we can't find a request_id, attempt to extract from the first item
                            if len(data) > 0 and isinstance(data[0], dict) and 'request_id' in data[0]:
                                request_id = data[0]['request_id']
                                logger.debug(f"[CELL_PROCESSOR] Using request_id from first item: {request_id}")

                        if not request_id:
                            logger.error("[CELL_PROCESSOR] Cannot store cell data: No request_id available")
                            return []

                        # Use the coordinator to store the data
                        stored_count = self._data_coordinator.store_data('cells', data, request_id)
                        logger.debug(f"[CELL_PROCESSOR] Stored {stored_count} cell data points")

                        # Get stored data from coordinator
                        stored_data = self._data_coordinator.get_data('cells', use_backup=False)
                        logger.debug(f"[CELL_PROCESSOR] Retrieved {len(stored_data)} cell data points")
                        return stored_data
                    except Exception as e:
                        logger.error(f"[CELL_PROCESSOR] Error storing cell data: {str(e)}")
                        logger.error(traceback.format_exc())
                        return []

        # CASE 2: Data with 'data' attribute containing cell list
        if hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
            logger.debug(f"[CELL_PROCESSOR] Found list of {len(data.data)} cell points in data.data")
            # Process the extracted data
            return await self.process_data(data.data, node_name)

        # CASE 3: Dictionary with additional_info.weather_data.cell_data
        if isinstance(data, dict) and 'additional_info' in data:
            additional_info = data['additional_info']

            if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                weather_data = additional_info['weather_data']

                if isinstance(weather_data, dict) and 'cell_data' in weather_data and isinstance(weather_data['cell_data'], list):
                    cell_data = weather_data['cell_data']
                    logger.debug(f"[CELL_PROCESSOR] Found {len(cell_data)} cell points in weather_data")
                    # Process the extracted data
                    return await self.process_data(cell_data, node_name)

        # CASE 4: Object with additional_info attribute
        if hasattr(data, 'additional_info') and data.additional_info is not None:
            if hasattr(data.additional_info, 'weather_data') and hasattr(data.additional_info.weather_data, 'cell_data'):
                cell_data = data.additional_info.weather_data.cell_data
                if isinstance(cell_data, list):
                    logger.debug(f"[CELL_PROCESSOR] Found {len(cell_data)} cell points in additional_info.weather_data")
                    # Process the extracted data
                    return await self.process_data(cell_data, node_name)

        # No valid cell data found
        logger.warning("[CELL_PROCESSOR] No cell data found in any recognized format")
        return []
