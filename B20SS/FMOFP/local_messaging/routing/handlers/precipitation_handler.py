"""
Precipitation Handler

Handles precipitation data messages using ResponseServiceAdapter.
"""

import traceback
import time
from typing import Dict, Any, Union, List

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.response_service_adapter import get_response_service_adapter
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData

logger = get_logger()

class PrecipitationHandler:
    """Handler for precipitation data messages."""

    def __init__(self, response_service_adapter=None):
        self.response_service_adapter = response_service_adapter or get_response_service_adapter()
        self.logger = get_logger()
        logger.info("PrecipitationHandler initialized")

    async def handle_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Handle precipitation data message.

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
            message_dict['metadata']['_processed_by_precipitation_handler'] = True

            # Check for binary data array that needs translation
            if 'data' in message_dict and isinstance(message_dict['data'], list):
                data_array = message_dict['data']
                # Check if this looks like binary data (list of integers)
                if len(data_array) >= 3 and all(isinstance(item, int) for item in data_array[:3]):
                    logger.info(f"[PRECIP_HANDLER] Detected binary data array with {len(data_array)} elements")

                    # Translate the binary data into precipitation data objects
                    precipitation_data_list = self._translate_binary_data(message_dict.get('request_id', ''), data_array)

                    if precipitation_data_list:
                        # Replace the binary data with the translated objects
                        logger.info(f"[PRECIP_HANDLER] Translated {len(precipitation_data_list)} precipitation objects from binary data")

                        # Instead of directly replacing message_dict['data'], create a properly formatted structure
                        message_dict['precipitation_data'] = precipitation_data_list

                        # Keep original data for reference if needed
                        message_dict['metadata']['original_binary_data_length'] = len(data_array)
                        message_dict['metadata']['binary_data_translated'] = True
                        message_dict['metadata']['precipitation_objects_count'] = len(precipitation_data_list)

                        # Log success
                        logger.info(f"[PRECIP_HANDLER] Successfully translated binary data to {len(precipitation_data_list)} precipitation objects")

            # Check if this is a completion message
            is_completion = False
            if 'message_type' in message_dict and 'Completion' in message_dict['message_type']:
                is_completion = True
            elif 'command_name' in message_dict and 'COMPLETION' in message_dict['command_name']:
                is_completion = True

            # Check if there's actual precipitation data regardless of completion status
            has_precipitation_data = False
            if 'precipitation_data' in message_dict and isinstance(message_dict['precipitation_data'], list) and len(message_dict['precipitation_data']) > 0:
                has_precipitation_data = True
                logger.info(f"[PRECIP_HANDLER] Found {len(message_dict['precipitation_data'])} precipitation objects in message")
            elif 'data' in message_dict and isinstance(message_dict['data'], list):
                if any(isinstance(item, PrecipitationData) for item in message_dict['data']):
                    has_precipitation_data = True
                    logger.info(f"[PRECIP_HANDLER] Found precipitation objects in data array")
                elif len(message_dict['data']) > 0 and all(isinstance(item, dict) for item in message_dict['data']):
                    # Check if this is a list of dicts with position attributes (likely precipitation data)
                    if any('position' in item for item in message_dict['data']):
                        has_precipitation_data = True
                        logger.info(f"[PRECIP_HANDLER] Found precipitation-like data in data array")

            # Log message handling
            if 'metadata' in message_dict and message_dict['metadata'].get('binary_data_translated'):
                logger.info(f"[PRECIP_HANDLER] Handling precipitation data message with translated binary data")
            else:
                logger.info(f"[PRECIP_HANDLER] Handling precipitation {'completion' if is_completion else 'data'} message")

            # Process through response service adapter
            result = await self.response_service_adapter.handle_precipitation_data(message_dict)

            # Only skip display routing for true completion messages with no precipitation data
            if is_completion and not has_precipitation_data:
                logger.info(f"[PRECIP_HANDLER] Successfully handled precipitation completion message (no data to display)")
                return result

            # Create command data for display
            command_data = {
                'command_type': 'precipitation_data',
                'display_type': 'radar_display',
                'request_id': message_dict.get('request_id'),
                'timestamp': message_dict.get('timestamp'),
                'command_name': message_dict.get('command_name'),  # Preserve command_name
                'additional_info': {
                    'precipitation_data': message_dict.get('precipitation_data'),
                    'original_request_id': message_dict.get('request_id'),
                    'command_name': message_dict.get('command_name'),  # Also store in additional_info for redundancy
                    '_processed_by_precipitation_handler': True  # Loop prevention flag
                }
            }

            # Display message handling
            await self.response_service_adapter.handle_display_command(command_data)

            logger.info(f"[PRECIP_HANDLER] Successfully handled precipitation data message")
            return result
        except Exception as e:
            logger.error(f"[PRECIP_HANDLER] Error handling precipitation data: {e}")
            logger.error(traceback.format_exc())
            return False

    def _translate_binary_data(self, request_id: str, binary_data: List[int]) -> List[PrecipitationData]:
        """
        Translate binary data array into PrecipitationData objects.

        Args:
            request_id: The request ID for tracking
            binary_data: List of integers containing encoded data

        Returns:
            List[PrecipitationData]: List of translated precipitation data objects
        """
        try:
            precipitation_objects = []

            # Validate input
            if not binary_data or len(binary_data) < 1:
                logger.error(f"[PRECIP_HANDLER] Invalid binary data: {binary_data}")
                return []

            # Word 0: object count
            # Word 1: scale metadata (written by DataResponseSender — skip when indexing objects)
            # Words 2+: pairs of (pos_word, attr_word) per object
            object_count = binary_data[0]
            logger.debug(f"[PRECIP_HANDLER] Detected {object_count} precipitation objects in binary data")

            # Validate: 2 header words + 2 words per object
            expected_size = 2 + (object_count * 2)
            if len(binary_data) < expected_size:
                logger.error(f"[PRECIP_HANDLER] Binary data too short: expected {expected_size}, got {len(binary_data)}")
                return []

            # Process each object (pair of words)
            for i in range(object_count):
                # Start at index 2 to skip both the count word and the scale metadata word
                pos_index = 2 + (i * 2)
                attr_index = pos_index + 1

                if pos_index >= len(binary_data) or attr_index >= len(binary_data):
                    logger.error(f"[PRECIP_HANDLER] Index out of range: pos_index={pos_index}, attr_index={attr_index}")
                    continue

                # Extract position and attributes data
                pos_word = binary_data[pos_index]
                attr_word = binary_data[attr_index]

                # Log the binary representation for debugging
                logger.debug(f"[PRECIP_HANDLER] Processing object {i+1}/{object_count}:")
                logger.debug(f"[PRECIP_HANDLER] - Position word: {pos_word} (0x{pos_word:04X})")
                logger.debug(f"[PRECIP_HANDLER] - Attribute word: {attr_word} (0x{attr_word:04X})")

                # Decode position coordinates
                x_coordinate = (pos_word >> 8) & 0xFF  # Extract upper byte
                y_coordinate = pos_word & 0xFF        # Extract lower byte

                # Adjust coordinates from 0-255 range to -128 to 127 range
                x_adjusted = float(x_coordinate - 128)
                y_adjusted = float(y_coordinate - 128)

                # Decode precipitation characteristics
                type_code = (attr_word >> 12) & 0xF     # Top 4 bits
                rate_code = (attr_word >> 6) & 0x3F     # Middle 6 bits
                intensity_code = attr_word & 0x3F       # Bottom 6 bits

                # Map type code to precipitation type
                type_map = {0: 'rain', 1: 'snow', 2: 'sleet', 3: 'hail', 4: 'mixed'}
                precip_type = type_map.get(type_code, 'rain')

                # Convert codes to actual values
                rate = float(rate_code) / 2.0        # Inverse of encoder RATE_SCALE=2: rate_code=round(rate*2)
                intensity = float(intensity_code) / 63.0  # Scale from 0-63 to 0.0-1.0

                # Ensure intensity is never zero (for visibility)
                if intensity < 0.1:
                    intensity = 0.1

                # Create unique object ID
                object_id = f"{request_id}_{i+1}"

                # Log the decoded data
                logger.debug(f"[PRECIP_HANDLER] Decoded values:")
                logger.debug(f"[PRECIP_HANDLER] - Position: ({x_adjusted}, {y_adjusted})")
                logger.debug(f"[PRECIP_HANDLER] - Type: {precip_type} (code {type_code})")
                logger.debug(f"[PRECIP_HANDLER] - Rate: {rate} mm/hr (code {rate_code})")
                logger.debug(f"[PRECIP_HANDLER] - Intensity: {intensity} (code {intensity_code})")

                # Create PrecipitationData object with the translated values
                precip_obj = PrecipitationData(
                    position=(x_adjusted, y_adjusted),
                    type=precip_type,
                    rate=rate,
                    intensity=intensity,
                    show_values=True  # Default to showing values
                )

                # Set additional fields
                precip_obj.request_id = object_id
                precip_obj.timestamp = time.time()

                # Add metadata
                if not hasattr(precip_obj, 'additional_info'):
                    precip_obj.additional_info = {}

                precip_obj.additional_info.update({
                    'binary_source': True,
                    'position_word': pos_word,
                    'attribute_word': attr_word,
                    'parent_request_id': request_id,
                    'object_index': i,
                    'total_objects': object_count
                })

                # Add to result list
                precipitation_objects.append(precip_obj)

            logger.info(f"[PRECIP_HANDLER] Successfully translated {len(precipitation_objects)} precipitation objects")
            return precipitation_objects

        except Exception as e:
            logger.error(f"[PRECIP_HANDLER] Error translating binary data: {e}")
            logger.error(traceback.format_exc())
            return []

# Singleton instance
_precipitation_handler = None

def get_precipitation_handler():
    """Get the singleton instance of PrecipitationHandler."""
    global _precipitation_handler
    if _precipitation_handler is None:
        _precipitation_handler = PrecipitationHandler()
    return _precipitation_handler
