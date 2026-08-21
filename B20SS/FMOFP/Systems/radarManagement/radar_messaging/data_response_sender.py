"""
Data Response Sender

Handles sending data responses by converting MIL_STD_1553B_Message objects or dictionaries to the dictionary format
expected by RT_sender.

Uses enhanced address utilities to ensure consistent addressing for radar subsystems according to MIL-STD-1553B protocol.
"""

import threading
import time
import uuid
import traceback
import math

from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
    get_rt_address,
    get_subaddress,
    get_rt_subaddress_pair_for_radar,
    is_radar_subsystem,
    get_system_id_for_addressing
)

logger = get_logger()

class DataResponseSender:
    """Handles sending data responses by converting MIL_STD_1553B_Message objects or dictionaries to the format expected by RT_sender."""

    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DataResponseSender, cls).__new__(cls)
                logger.info(f"Creating new DataResponseSender instance: {id(cls._instance)}")
            else:
                logger.info(f"Returning existing DataResponseSender instance: {id(cls._instance)}")
            return cls._instance

    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                # Initialize RT_sender
                from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_sender
                self.rt_sender = get_rt_sender()
                logger.info(f"DataResponseSender initialized with RT_sender: {id(self.rt_sender)}")
                self.__class__._initialized = True

    def send_data_response(self, message, **kwargs) -> bool:
        """
        Convert message to dictionary format expected by RT_sender and send it.
        Enhanced to properly handle all data types, particularly complex objects.

        Args:
            message: The MIL_STD_1553B_Message object or dictionary to send
            **kwargs: Additional parameters that may override message attributes

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Log the original message for debugging
            logger.info(f"[DATA_SENDER] Sending data response: {message}")

            # Extract system name and determine proper RT/SA pair
            system_name = None

            # Try to determine system name from the message or kwargs
            if isinstance(message, dict):
                # Look for system_name or system_type in message dictionary
                system_name = message.get('system_name', message.get('system_type'))
                # Check in metadata
                if not system_name and 'metadata' in message and isinstance(message['metadata'], dict):
                    system_name = message['metadata'].get('system_name', message['metadata'].get('system_type'))
            else:
                # Look for system_name or system_type in object attributes
                if hasattr(message, 'system_name'):
                    system_name = message.system_name
                elif hasattr(message, 'system_type'):
                    system_name = message.system_type
                # Check in metadata
                elif hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                    system_name = message.metadata.get('system_name', message.metadata.get('system_type'))

            # Get from kwargs if not found in message
            if not system_name:
                system_name = kwargs.get('system_name', kwargs.get('system_type', 'weather_radar'))

            logger.info(f"[DATA_SENDER] Determined system name: {system_name}")

            # Use enhanced address utilities to get proper RT/SA pair
            try:
                rt_address, sub_address = get_rt_subaddress_pair_for_radar(system_name, 'weather_radar')
                logger.info(f"[DATA_SENDER] Using address utilities: RT={rt_address}, SA={sub_address} for system {system_name}")
            except Exception as e:
                logger.warning(f"[DATA_SENDER] Error using address utilities: {e}")
                # Try to get addresses from the message as fallback
                if isinstance(message, dict):
                    # Extract fields from dictionary
                    # Check for both 'rt_address' and 'rtAddress' keys
                    rt_address = message.get('rt_address', message.get('rtAddress', kwargs.get('rt_address', 9)))
                    # Check for both 'sub_address' and 'subAddress' keys
                    sub_address = message.get('sub_address', message.get('subAddress', kwargs.get('sub_address', 1)))
                else:
                    # Extract fields from object attributes
                    rt_address = getattr(message, 'rt_address', kwargs.get('rt_address', 9))
                    sub_address = getattr(message, 'sub_address', kwargs.get('sub_address', 1))
                logger.info(f"[DATA_SENDER] Fallback addresses: RT={rt_address}, SA={sub_address}")

            # Log the extracted values for debugging
            logger.info(f"[DATA_SENDER] Using RT address: {rt_address}, subaddress: {sub_address}")

            # Extract other message attributes
            if isinstance(message, dict):
                logger.info(f"[DATA_SENDER] Original message keys: {list(message.keys())}")
                message_type = message.get('message_type', kwargs.get('message_type'))
                command_type = message.get('command_type', kwargs.get('command_type'))
                command_name = message.get('command_name', kwargs.get('command_name'))
                request_id = message.get('request_id', kwargs.get('request_id'))
                data = message.get('data')

                # ENHANCEMENT: Check for precipitation_data or specific data fields
                if data is None and 'precipitation_data' in message:
                    data = message['precipitation_data']
                    logger.info(f"[DATA_SENDER] Found precipitation_data field: {data}")
            else:
                # Extract fields from object attributes
                message_type = getattr(message, 'message_type', kwargs.get('message_type'))
                command_type = getattr(message, 'command_type', kwargs.get('command_type'))
                command_name = getattr(message, 'command_name', kwargs.get('command_name'))
                request_id = getattr(message, 'request_id', kwargs.get('request_id'))

                # ENHANCEMENT: Better data extraction for complex objects
                data = None
                # Try various attribute names for object data
                for attr_name in ['data', 'precipitation_data', 'vil_data']:
                    if hasattr(message, attr_name):
                        data = getattr(message, attr_name)
                        logger.info(f"[DATA_SENDER] Found data in {attr_name} attribute")
                        break

            if not request_id:
                raise ValueError("[DATA_RSPS_SENDER] No request ID found in message or kwargs")

            # Create status word
            status_word = self._create_status_word(rt_address)
            logger.info(f"[DATA_SENDER] Created status word: {status_word}")

            # Create dictionary format
            message_dict = {
                'status_word': status_word,
                'request_id': request_id,
                'timestamp': time.time(),
                'command_type': command_type,
                'message_type': message_type,
                'command_name': command_name,
                'rt_address': rt_address,
                'sub_address': sub_address
            }

            # ENHANCEMENT: Proper data handling for complex objects
            # Check for complex data type that needs special handling
            if data is not None:
                # Log detailed data characteristics
                logger.info(f"[DATA_SENDER] Processing data of type {type(data)}")

                # Handle list of precipitation or VIL data objects
                if isinstance(data, list) and data and hasattr(data[0], 'position'):
                    logger.info(f"[DATA_SENDER] Detected complex data objects: {len(data)} items")

                    # Convert complex objects to binary format for 1553B
                    encoded_data = self._encode_complex_objects(data)
                    message_dict['data'] = encoded_data

                    # Set block transfer flag if needed
                    if len(encoded_data) > 30:  # MIL-STD-1553B word limit per message
                        if 'metadata' not in message_dict:
                            message_dict['metadata'] = {}

                        # Add block transfer metadata
                        total_blocks = (len(encoded_data) + 29) // 30
                        message_dict['metadata']['is_block_transfer'] = True
                        message_dict['metadata']['total_sequences'] = total_blocks
                        message_dict['metadata']['sequence_number'] = 1  # Initial block
                        message_dict['metadata']['is_final'] = (total_blocks == 1)

                        logger.info(f"[DATA_SENDER] Data requires {total_blocks} blocks for transfer")
                else:
                    # Standard data assignment for primitive types
                    message_dict['data'] = data

            # Add or update metadata
            if 'metadata' not in message_dict:
                message_dict['metadata'] = {}

            # Use centralized constants for message types
            from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
                WEATHER_RADAR_DATA,
                WEATHER_RADAR_VIL_RESPONSE,
                WEATHER_RADAR_PRECIPITATION_RESPONSE,
                get_message_type
            )

            # Update specific fields while preserving existing metadata
            message_dict['metadata'].update({
                'message_type': message_type,
                'command_type': command_type,
                'command_name': command_name,
                'source_system': system_name,
                'destination': 'display_system',
                'request_id': request_id
            })

            # ENHANCEMENT: Preserve critical metadata for precipitation and VIL
            if message_type and 'precipitation' in message_type.lower():
                message_dict['metadata']['precipitation_message'] = True
                message_dict['metadata']['data_type'] = 'precipitation'
                logger.info(f"[DATA_SENDER] Added precipitation metadata flags")
            elif message_type and 'vil' in message_type.lower():
                message_dict['metadata']['vil_message'] = True
                message_dict['metadata']['data_type'] = 'vil'
                logger.info(f"[DATA_SENDER] Added VIL metadata flags")

            # Remove None values
            message_dict = {k: v for k, v in message_dict.items() if v is not None}

            # Log the converted message
            logger.info(f"[DATA_SENDER] Converted message to dictionary format: {message_dict}")

            # Send via RT_sender
            result = self.rt_sender.RT_send_message(message_dict)

            if result:
                logger.info(f"[DATA_SENDER] Successfully sent data response with request ID: {request_id}")
            else:
                logger.error(f"[DATA_SENDER] Failed to send data response with request ID: {request_id}")

            return result

        except Exception as e:
            logger.error(f"[DATA_SENDER] Error sending data response: {e}")
            logger.error(traceback.format_exc())
            return False

    def _encode_complex_objects(self, objects_list):
        """
        Convert complex data objects (precipitation, VIL) to binary format for 1553B transmission.
        Enhanced version that preserves precision for small rate and intensity values.

        ENCODING SCHEME:
        ---------------
        1. Message Format:
           - Word 1: Number of objects (N)
           - Word 2: Scaling factors metadata
             * High byte (8 bits): Rate scale code = log2(RATE_SCALE) * 16
             * Low byte (8 bits): Intensity scale code = log2(INTENSITY_SCALE) * 16
           - Words 3 to 2N+2: Object data (2 words per object)
             * Word 1: Position (16 bits)
               - High byte (8 bits): X coordinate offset by +128
               - Low byte (8 bits): Y coordinate offset by +128
             * Word 2: Attributes (16 bits)
               - Bits 15-12 (4 bits): Type code (0=rain, 1=snow, 2=sleet, 3=hail, 4=mixed)
               - Bits 11-6 (6 bits): Rate code = min(63, int(rate * RATE_SCALE))
               - Bits 5-0 (6 bits): Intensity code = min(63, int(intensity * INTENSITY_SCALE))

        2. Encoding Process:
           - Position: Add 128 to both X and Y coordinates to center around middle of byte range
           - Rate: Scale by 100.0 (RATE_SCALE) to convert small decimals to integers (e.g., 0.31 → 31)
           - Intensity: Scale by 5000.0 (INTENSITY_SCALE) to convert tiny decimals to integers (e.g., 0.00628 → 31.4)
           - All values are capped to fit within their bit allocations

        3. Decoding Process:
           - Positions: Subtract 128 from encoded X,Y to recover original coordinates
           - Rate: Divide encoded rate by RATE_SCALE (code * 100.0 / rate_scale)
           - Intensity: Divide encoded intensity by INTENSITY_SCALE (code * 100.0 / intensity_scale)

        Args:
            objects_list: List of data objects with position, type, etc.

        Returns:
            list: List of integers (16-bit words) representing serialized data
        """
        encoded_data = []

        # Scaling factors for 6-bit fields (0-63):
        #   RATE_SCALE=2      → range 0–31.5 mm/hr, resolution 0.5 mm/hr
        #   INTENSITY_SCALE=63 → range 0–1.0, resolution 1/63 ≈ 0.016
        # These constants must match precipitation_data_handler.extract_and_store_binary_data.
        RATE_SCALE = 2.0
        INTENSITY_SCALE = 63.0

        # Word 0: number of objects
        encoded_data.append(len(objects_list))

        # Word 1: scale metadata so the decoder can recover the exact constants.
        # Encoded as log2(scale) × 16 to fit in one byte each.
        rate_scale_code      = min(255, int(math.log2(RATE_SCALE) * 16)) if RATE_SCALE > 0 else 0
        intensity_scale_code = min(255, int(math.log2(INTENSITY_SCALE) * 16))
        scale_word = (rate_scale_code << 8) | intensity_scale_code
        encoded_data.append(scale_word)

        logger.debug(f"[DATA_SENDER] Encoding {len(objects_list)} objects — "
                     f"RATE_SCALE={RATE_SCALE}, INTENSITY_SCALE={INTENSITY_SCALE}")

        # Track encoded objects
        encoded_count = 0

        for obj in objects_list:
            try:
                # Position word (8 bits X, 8 bits Y) — common to both VIL and precipitation
                x, y = map(float, obj.position)

                # Center around 128 to utilise the full 0-255 byte range.
                # Decoder must subtract 128 to recover original coordinates.
                x_int = max(0, min(255, int(x + 128)))
                y_int = max(0, min(255, int(y + 128)))
                pos_word = (x_int << 8) | y_int
                encoded_data.append(pos_word)

                logger.debug(f"[DATA_SENDER] Position: original=({x}, {y}), encoded=({x_int},{y_int}), word=0x{pos_word:04x}")

                # Detect object type: VIL objects have .value/.layer_count;
                # precipitation objects have .type/.rate.
                is_vil = hasattr(obj, 'value') and hasattr(obj, 'layer_count') and not hasattr(obj, 'type')

                if is_vil:
                    # VIL attribute word layout — matches WeatherRadarVILData.to_data_words():
                    #   Bits 15-9  (7 bits): value_code  = min(127, round(value * 2))
                    #   Bits  8-5  (4 bits): layer_code  = min(15, layer_count)
                    #   Bits  4-1  (4 bits): intensity_code = min(15, round(intensity * 15))
                    #   Bit   0    (1 bit) : show_bit
                    value_code     = max(0, min(127, round(getattr(obj, 'value', 0.0) * 2)))
                    layer_code     = max(0, min(15,  int(getattr(obj, 'layer_count', 0))))
                    intensity_code = max(0, min(15,  round(getattr(obj, 'intensity', 0.0) * 15)))
                    show_bit       = 1 if getattr(obj, 'show_values', True) else 0
                    attr_word = (value_code << 9) | (layer_code << 5) | (intensity_code << 1) | show_bit

                    logger.debug(f"[DATA_SENDER] VIL encoding: value={obj.value}→{value_code}, "
                                 f"layers={obj.layer_count}→{layer_code}, "
                                 f"intensity={obj.intensity:.3f}→{intensity_code}, "
                                 f"show={show_bit}, attr_word=0x{attr_word:04x}")
                else:
                    # Precipitation attribute word layout (16 bits):
                    #   Bits 15-12 (4 bits): type_code
                    #   Bits 11-6  (6 bits): rate_code  = min(63, int(rate * RATE_SCALE))
                    #   Bits  5-0  (6 bits): intensity_code = min(63, int(intensity * INTENSITY_SCALE))
                    type_map   = {'rain': 0, 'snow': 1, 'sleet': 2, 'hail': 3, 'mixed': 4}
                    type_code  = type_map.get(getattr(obj, 'type', 'rain'), 0)
                    rate       = getattr(obj, 'rate', 0.0)
                    rate_code  = max(0, min(63, int(rate * RATE_SCALE)))
                    intensity  = getattr(obj, 'intensity', 0.5)
                    intensity_code = max(0, min(63, int(intensity * INTENSITY_SCALE)))
                    attr_word  = (type_code << 12) | (rate_code << 6) | intensity_code

                    logger.debug(f"[DATA_SENDER] Precipitation encoding: type={type_code}, "
                                 f"rate={rate}→{rate_code}, intensity={intensity:.4f}→{intensity_code}, "
                                 f"attr_word=0x{attr_word:04x}")

                encoded_data.append(attr_word)
                encoded_count += 1

            except Exception as e:
                logger.error(f"[DATA_SENDER] Error encoding object: {e}")
                # Continue with next object

        logger.info(f"[DATA_SENDER] Successfully encoded {encoded_count}/{len(objects_list)} objects")
        logger.info(f"[DATA_SENDER] Total encoded data size: {len(encoded_data)} words")

        return encoded_data

    def _create_status_word(self, rt_address) -> str:
        """
        Create a valid status word for the given RT address.

        Args:
            rt_address: The RT address (e.g., 9 for weather radar)

        Returns:
            str: A 20-bit binary string representing the status word with odd parity
        """
        # Format: sync bits (3) + RT address (5) + message bit (1) + reserved bits (3) + subaddress (5) + word count (2) + parity (1)
        sync_bits = '100'  # Standard sync bits for status word
        rt_address_bits = format(rt_address, '05b')  # 5-bit RT address
        message_bit = '0'  # No message
        reserved_bits = '000'  # Reserved bits
        subaddress_bits = '00000'  # No subaddress
        word_count_bits = '00'  # No data words (reduced to 2 bits to make room for parity)

        # Create status word without parity bit (19 bits)
        status_word_without_parity = sync_bits + rt_address_bits + message_bit + reserved_bits + subaddress_bits + word_count_bits

        # Count number of 1s in the status word
        ones_count = status_word_without_parity.count('1')

        # Calculate parity bit to ensure odd parity (total number of 1s including parity bit should be odd)
        parity_bit = '1' if ones_count % 2 == 0 else '0'

        # Add parity bit to status word to create a 20-bit word
        status_word = status_word_without_parity + parity_bit

        logger.info(f"[DATA_SENDER] Created status word with parity: {status_word}, ones count: {ones_count}, parity bit: {parity_bit}")

        return status_word

    def send_precipitation_data(self, message, **kwargs) -> bool:
        """
        Send precipitation data response with proper object preservation.

        Args:
            message: The MIL_STD_1553B_Message object or dictionary to send
            **kwargs: Additional parameters that may override message attributes

        Returns:
            bool: True if successful, False otherwise
        """
        # Use centralized message type constants
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
            WEATHER_RADAR_PRECIPITATION_RESPONSE,
            COMMAND_TYPE_PRECIPITATION_DATA,
            is_message_type
        )

        # Set default values for precipitation data using constants
        kwargs.setdefault('message_type', WEATHER_RADAR_PRECIPITATION_RESPONSE)
        kwargs.setdefault('command_type', COMMAND_TYPE_PRECIPITATION_DATA)

        # ENHANCEMENT: Extract and preserve precipitation data objects
        precipitation_data = None

        # Check various locations where data might be stored
        if isinstance(message, dict):
            if 'data' in message:
                precipitation_data = message['data']
                logger.info(f"[DATA_SENDER] Found precipitation data in 'data' field: {len(precipitation_data) if isinstance(precipitation_data, list) else 'scalar'}")
            elif 'precipitation_data' in message:
                precipitation_data = message['precipitation_data']
                logger.info(f"[DATA_SENDER] Found precipitation data in 'precipitation_data' field: {len(precipitation_data) if isinstance(precipitation_data, list) else 'scalar'}")
        elif hasattr(message, 'precipitation_data'):
            precipitation_data = message.precipitation_data
            logger.info(f"[DATA_SENDER] Found precipitation data in precipitation_data attribute: {len(precipitation_data) if isinstance(precipitation_data, list) else 'scalar'}")
        elif hasattr(message, 'data'):
            precipitation_data = message.data
            logger.info(f"[DATA_SENDER] Found precipitation data in data attribute: {len(precipitation_data) if isinstance(precipitation_data, list) else 'scalar'}")

        # Ensure we have data to work with
        if precipitation_data is None:
            logger.warning(f"[DATA_SENDER] No precipitation data found in message, falling back to standard behavior")
        else:
            logger.info(f"[DATA_SENDER] Successfully extracted precipitation data for transmission")

        # Create a copy of the message to avoid modifying the original
        if isinstance(message, dict):
            message_copy = message.copy()

            # Ensure the data is explicitly attached before sending
            if precipitation_data is not None:
                message_copy['data'] = precipitation_data
                logger.info(f"[DATA_SENDER] Attached precipitation data to message copy")

            # Add additional metadata for precipitation data
            if 'metadata' not in message_copy:
                message_copy['metadata'] = {}

            message_copy['metadata']['precipitation_message'] = True
            message_copy['metadata']['data_type'] = 'precipitation'
            message_copy['metadata']['final_delivery_to_display'] = True
            message_copy['metadata']['destination'] = 'display_system'

            if 'command_name' in message_copy:
                message_copy['metadata']['command_name'] = message_copy['command_name']
            if 'request_id' in message_copy:
                message_copy['metadata']['request_id'] = message_copy['request_id']

            logger.info(f"[DATA_SENDER] Sending precipitation data response with enhanced metadata and preserved data objects")
            return self.send_data_response(message_copy, **kwargs)
        else:
            # Handle object-style message
            logger.info(f"[DATA_SENDER] Sending precipitation data response with object-style message")
            # Add explicit data passing to kwargs to ensure it's included
            if precipitation_data is not None:
                kwargs['data'] = precipitation_data
            return self.send_data_response(message, **kwargs)

    def send_vil_data(self, message, **kwargs) -> bool:
        """
        Send VIL data response.

        Args:
            message: The MIL_STD_1553B_Message object or dictionary to send
            **kwargs: Additional parameters that may override message attributes

        Returns:
            bool: True if successful, False otherwise
        """
        # Use centralized message type constants
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
            WEATHER_RADAR_VIL_RESPONSE,
            COMMAND_TYPE_VIL_DATA,
            is_message_type
        )

        # Set default values for VIL data using constants
        kwargs.setdefault('message_type', WEATHER_RADAR_VIL_RESPONSE)
        kwargs.setdefault('command_type', COMMAND_TYPE_VIL_DATA)

        # Add additional metadata for VIL data
        if isinstance(message, dict) and 'metadata' not in message:
            message['metadata'] = {}
        if isinstance(message, dict) and 'metadata' in message:
            message['metadata']['vil_message'] = True
            message['metadata']['data_type'] = 'vil'
            message['metadata']['final_delivery_to_display'] = True
            message['metadata']['destination'] = 'display_system'
            if 'command_name' in message:
                message['metadata']['command_name'] = message['command_name']
            if 'request_id' in message:
                message['metadata']['request_id'] = message['request_id']

        logger.info(f"[DATA_SENDER] Sending VIL data response with enhanced metadata")
        return self.send_data_response(message, **kwargs)

# Global instance
_data_response_sender = None
_sender_lock = threading.Lock()

def get_data_response_sender() -> DataResponseSender:
    """Get the global DataResponseSender instance."""
    global _data_response_sender
    with _sender_lock:
        if _data_response_sender is None:
            _data_response_sender = DataResponseSender()
            logger.info("Created global DataResponseSender instance")
        return _data_response_sender
