"""
VIL (Vertically Integrated Liquid) data processor for weather radar display.
Handles various formats of VIL data.
"""
import time
import traceback
from typing import Any, Dict, List, Optional

from Utils.logger.sys_logger import get_logger

logger = get_logger()

class VILDataProcessor:
    """Process VIL data for weather radar display."""
    
    def __init__(self, data_coordinator, settings_manager, log_throttler, vil_data_timestamp):
        """
        Initialize VIL data processor.
        
        Args:
            data_coordinator: The radar display data coordinator instance
            settings_manager: The visual settings manager instance
            log_throttler: The log throttler instance for rate-limited logging
            vil_data_timestamp: Reference to the timestamp dictionary for VIL data persistence
        """
        self._data_coordinator = data_coordinator
        self._settings_manager = settings_manager
        self._log_throttler = log_throttler
        self._vil_data_timestamp = vil_data_timestamp
        
    async def process_data(self, data: Any, node_name: str) -> List[Dict[str, Any]]:
        """
        Process VIL data from various formats.
        
        CRITICAL: Only passes through data as received - makes no modifications.
        
        Args:
            data: Data to process
            node_name: Source node name
            
        Returns:
            The processed VIL data, or empty list if no valid data found
        """
        logger.warning(f"[VIL_PROCESSOR] Processing data of type: {type(data).__name__}")
        
        # Ensure visual elements are set to show VIL data in surveillance mode
        await self._settings_manager.update_settings_async({
            'show_vil': True,
            'show_vil_legend': True,
            'show_vil_values': True
        }, apply_to_node=False)
        
        # Extract request_id from the data if available - NEVER generate one
        request_id = None
        if isinstance(data, dict) and 'request_id' in data:
            request_id = data['request_id']
        elif hasattr(data, 'request_id'):
            request_id = data.request_id
            
        # CASE 1: Direct list of VIL dictionaries (most common case)
        if isinstance(data, list) and len(data) > 0:
            if all(isinstance(item, dict) for item in data):
                logger.warning(f"[VIL_PROCESSOR] Found direct list of {len(data)} VIL data points")
                
                # Store the data EXACTLY as received - no modifications
                try:
                    if not request_id:
                        # If we can't find a request_id, attempt to extract from the first item
                        if len(data) > 0 and isinstance(data[0], dict) and 'request_id' in data[0]:
                            request_id = data[0]['request_id']
                            logger.warning(f"[VIL_PROCESSOR] Using request_id from first item: {request_id}")
                    
                    if not request_id:
                        logger.error("[VIL_PROCESSOR] Cannot store VIL data: No request_id available")
                        return []
                        
                    # Use the coordinator to store the data
                    stored_count = self._data_coordinator.store_data('vil', data, request_id)
                    logger.warning(f"[VIL_PROCESSOR] Stored {stored_count} VIL data points")
                    
                    # Get stored data from coordinator
                    stored_data = self._data_coordinator.get_data('vil', use_backup=False)
                    logger.warning(f"[VIL_PROCESSOR] Retrieved {len(stored_data)} VIL data points")
                    
                    # Store current timestamp for persistence
                    current_time = time.time()
                    for item in data:
                        if 'id' in item:
                            self._vil_data_timestamp[item['id']] = current_time
                    
                    return stored_data
                except Exception as e:
                    logger.error(f"[VIL_PROCESSOR] Error storing VIL data: {str(e)}")
                    logger.error(traceback.format_exc())
                    return []
        
        # CASE 2: Data with 'data' attribute containing VIL list
        if hasattr(data, 'data') and isinstance(data.data, list) and len(data.data) > 0:
            logger.warning(f"[VIL_PROCESSOR] Found list of {len(data.data)} VIL points in data.data")
            # Process the extracted data
            return await self.process_data(data.data, node_name)
            
        # CASE 3: Dictionary with additional_info.weather_data.vil_data
        if isinstance(data, dict) and 'additional_info' in data:
            additional_info = data['additional_info']
            
            if isinstance(additional_info, dict) and 'weather_data' in additional_info:
                weather_data = additional_info['weather_data']
                
                if isinstance(weather_data, dict) and 'vil_data' in weather_data and isinstance(weather_data['vil_data'], list):
                    vil_data = weather_data['vil_data']
                    logger.warning(f"[VIL_PROCESSOR] Found {len(vil_data)} VIL points in weather_data")
                    # Process the extracted data
                    return await self.process_data(vil_data, node_name)
                    
        # CASE 4: Object with additional_info attribute
        if hasattr(data, 'additional_info') and data.additional_info is not None:
            if hasattr(data.additional_info, 'weather_data') and hasattr(data.additional_info.weather_data, 'vil_data'):
                vil_data = data.additional_info.weather_data.vil_data
                if isinstance(vil_data, list):
                    logger.warning(f"[VIL_PROCESSOR] Found {len(vil_data)} VIL points in additional_info.weather_data")
                    # Process the extracted data
                    return await self.process_data(vil_data, node_name)
                    
        # CASE 5: Dictionary with command_type.vil_data
        if isinstance(data, dict) and 'command_type' in data:
            command_type = data['command_type']
            if isinstance(command_type, dict) and command_type.get('type') == 'vil':
                if 'data' in data and isinstance(data['data'], list):
                    vil_data = data['data']
                    logger.warning(f"[VIL_PROCESSOR] Found {len(vil_data)} VIL points in command_type data")
                    # Process the extracted data
                    return await self.process_data(vil_data, node_name)
        
        # No valid VIL data found
        logger.error("[VIL_PROCESSOR] No VIL data found in any recognized format")
        return []
