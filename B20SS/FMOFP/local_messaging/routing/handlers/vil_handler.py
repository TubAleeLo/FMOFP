
"""
VIL Handler

Handles VIL data messages using ResponseServiceAdapter.
Implementation aligns with the precipitation data handler approach.
"""

import traceback
import time
import json
from typing import Dict, Any, Union, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.response_service_adapter import get_response_service_adapter
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import WeatherRadarVILData

logger = get_logger()

class VILHandler:
    """Handler for VIL data messages."""
    
    def __init__(self, response_service_adapter=None):
        self.response_service_adapter = response_service_adapter or get_response_service_adapter()
        self.logger = get_logger()
        logger.info("VILHandler initialized")
        
    def _get_command_word(self, target_system='displays'):
        """
        Generate command word for VIL data using standard address utilities.
        
        Args:
            target_system: The target system ID, defaults to 'displays'
            
        Returns:
            str: The command word
        """
        from FMOFP.local_messaging.command_word_map import register_command_word
        from FMOFP.MIL_STD_1553B.address_utils import get_rt_address, get_subaddress
        
        # Use address utility functions instead of hardcoded values
        displays_rt = get_rt_address(target_system)
        radar_display_sa = get_subaddress('radar_display')
        
        return register_command_word(target_system, 0, 'radar_display', 'data', 'vil')
        
    from FMOFP.Utils.message_loop_prevention.decorators import prevent_message_loops_async
    
    @prevent_message_loops_async(service_name="vil_handler")
    async def handle_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Handle VIL data message.

        Args:
            message: The message to handle

        Returns:
            bool: True if the message was handled successfully, False otherwise
        """
        try:
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Add loop prevention flag
            if 'metadata' not in message_dict:
                message_dict['metadata'] = {}
            message_dict['metadata']['_processed_by_vil_handler'] = True
            
            # Check if this is a completion message
            is_completion = False
            if 'message_type' in message_dict and 'Completion' in message_dict['message_type']:
                is_completion = True
            elif 'command_name' in message_dict and 'COMPLETION' in message_dict['command_name']:
                is_completion = True
                
            # Log message handling
            logger.info(f"[VIL_HANDLER] Handling VIL {'completion' if is_completion else 'data'} message")
            
            # Process through response service adapter
            result = await self.response_service_adapter.handle_vil_data(message_dict)
            
            # For completion messages, we don't need to route to display
            if is_completion:
                logger.info(f"[VIL_HANDLER] Successfully handled VIL completion message")
                return result
                
            # Create command data for display
            command_data = {
                'command_type': 'vil_data',
                'display_type': 'radar_display',
                'request_id': message_dict.get('request_id'),
                'timestamp': message_dict.get('timestamp'),
                'command_name': message_dict.get('command_name'),  # Preserve command_name
                'message_type': 'weather_radarVILResponse',  # Use schema-defined message type
                'vil_data': message_dict.get('vil_data'),  # Directly pass vil_data field
                'data': message_dict.get('data'),  # Also pass data field for flexibility
                'additional_info': {
                    'vil_data': message_dict.get('vil_data'),
                    'original_request_id': message_dict.get('request_id'),
                    'command_name': message_dict.get('command_name'),  # Also store in additional_info for redundancy
                    'message_type': 'weather_radarVILResponse',  # Ensure consistent message type
                    '_processed_by_vil_handler': True  # Loop prevention flag
                }
            }
            
            # Include metadata to ensure consistency with proper headers
            if 'metadata' in message_dict:
                command_data['metadata'] = message_dict['metadata']
                command_data['metadata']['_processed_by_vil_handler'] = True
                command_data['metadata']['vil_message'] = True
                command_data['metadata']['vil_data_available'] = True
                
            # Display message handling - mirrors the precipitation handler pattern
            await self.response_service_adapter.handle_display_command(command_data)
            
            logger.info(f"[VIL_HANDLER] Successfully handled VIL data message")
            return result
        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error handling VIL data: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _extract_vil_data(self, message_dict: Dict[str, Any]) -> List[WeatherRadarVILData]:
        """
        Extract VIL data from message dictionary with multiple fallback approaches.
        
        Args:
            message_dict: Message dictionary
            
        Returns:
            List of WeatherRadarVILData objects
        """
        try:
            vil_data_list = []
            
            # Check for VIL data in different formats
            if 'vil_data' in message_dict and message_dict['vil_data']:
                # Direct vil_data field (list or single object)
                data = message_dict['vil_data']
                if isinstance(data, list):
                    vil_data_list.extend(data)
                else:
                    vil_data_list.append(data)
                logger.info(f"[VIL_HANDLER] Found VIL data in vil_data field: {len(vil_data_list)} items")
                
            elif 'data' in message_dict:
                # Data field could contain VIL data
                data = message_dict['data']
                
                # Check if data is WeatherRadarVILData object or list
                if isinstance(data, list):
                    # Filter list for WeatherRadarVILData objects
                    for item in data:
                        if hasattr(item, 'position') and hasattr(item, 'value'):
                            vil_data_list.append(item)
                elif hasattr(data, 'position') and hasattr(data, 'value'):
                    # Single WeatherRadarVILData object
                    vil_data_list.append(data)
                
                logger.info(f"[VIL_HANDLER] Found VIL data in data field: {len(vil_data_list)} items")

            # Ensure all VIL data has correct timestamps and request_ids
            for item in vil_data_list:
                if not hasattr(item, 'timestamp') or not item.timestamp:
                    item.timestamp = message_dict.get('timestamp', time.time())
                if not hasattr(item, 'request_id') or not item.request_id:
                    item.request_id = message_dict.get('request_id', str(time.time()))
                
                # Add additional info if not present
                if not hasattr(item, 'additional_info') or not item.additional_info:
                    item.additional_info = {}
                
                # Add command word if not present
                if 'command_word' not in item.additional_info:
                    item.additional_info['command_word'] = self._get_command_word()
            
            return vil_data_list
            
        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error extracting VIL data: {e}")
            logger.error(traceback.format_exc())
            return []
    
    def _create_display_message(self, vil_data_list: List[WeatherRadarVILData], message_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a display message for VIL data similar to precipitation handler.
        
        Args:
            vil_data_list: List of WeatherRadarVILData objects
            message_dict: Original message dictionary
            
        Returns:
            Display message dictionary
        """
        try:
            # Get request ID from first VIL data item or message
            request_id = vil_data_list[0].request_id if vil_data_list else message_dict.get('request_id', str(time.time()))
            
            # Get current mode from message
            mode_str = message_dict.get('mode', 'SURVEILLANCE')
            
            # Format data for display with all required fields and correct nesting
            display_message = {
                'data': vil_data_list,
                'vil_data': vil_data_list,  # Include directly for display system
                'request_id': request_id,
                'timestamp': time.time(),
                'message_type': 'display_vil_data',  # Use schema-defined message type
                'command_type': 'vil_data',
                'command_name': 'DISPLAY_VIL_DATA',
                'display_type': 'radar_display',  # Add display type
                'status': 'acknowledged',
                'metadata': {
                    'data_type': 'vil',
                    'source': 'weather_radar',
                    'destination': 'display_system',
                    'original_request_id': request_id,
                    'vil_message': True,
                    'vil_data_available': True,  # Explicitly mark data as available
                    'command_type': 'vil_data',
                    'command_name': 'DISPLAY_VIL_DATA',
                    'command_word': self._get_command_word(),
                    'message_type': 'display_vil_data',  # Consistent message type
                    'mode': mode_str,  # Add mode information
                    'weather_data': {
                        'vil': True
                    }
                },
                'additional_info': {
                    'data_type': 'vil',
                    'mode': mode_str,
                    'message_type': 'display_vil_data',
                    'command_name': 'DISPLAY_VIL_DATA',
                    'vil_data_available': True,
                    'show_vil': True,  # Explicitly request showing VIL
                    'weather_data': {
                        'mode': mode_str,
                        'vil_data': [
                            {
                                'position': item.position,
                                'value': item.value,
                                'layer_count': item.layer_count,
                                'intensity': item.intensity,
                                'show_values': item.show_values if hasattr(item, 'show_values') else True
                            } for item in vil_data_list
                        ]
                    },
                    'command_word': self._get_command_word(),
                    'original_request_id': request_id
                }
            }
            
            logger.info(f"[VIL_HANDLER] Created enhanced display message with {len(vil_data_list)} VIL data items")
            return display_message
            
        except Exception as e:
            logger.error(f"[VIL_HANDLER] Error creating display message: {e}")
            logger.error(traceback.format_exc())
            
            # Return a minimal message in case of error
            return {
                'data': vil_data_list,
                'request_id': message_dict.get('request_id', str(time.time())),
                'message_type': 'display_vil_data',
                'command_type': 'vil_data',
                'command_name': 'DISPLAY_VIL_DATA'
            }

# Singleton instance
_vil_handler = None

def get_vil_handler():
    """Get the singleton instance of VILHandler."""
    global _vil_handler
    if _vil_handler is None:
        _vil_handler = VILHandler()
    return _vil_handler
