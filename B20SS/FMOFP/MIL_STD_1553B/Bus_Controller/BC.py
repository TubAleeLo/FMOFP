"""
Bus Controller

Handles MIL-STD-1553B bus communication and message routing.
"""

import json
import threading
import time
import traceback
import asyncio
import FMOFP.Utils.common.fetching as fetching
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_deconstruct
from FMOFP.MIL_STD_1553B.Messaging import get_send_1553_msg
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_connect.BC_socket import BC_Listener
from FMOFP.Utils.common.thread_manager import ThreadManager
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
from FMOFP.local_messaging.command_word_map import ADDRESS_BOOK
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.response_services.system_response_services.RadarResponseService import get_radar_response_service
from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
from FMOFP.MIL_STD_1553B.Bus_Controller.bc_message_extractor import get_bc_message_extractor
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_transfer_aggregator import get_block_transfer_aggregator
from FMOFP.MIL_STD_1553B.message_structure_normalizer import get_message_structure_normalizer
from FMOFP.MIL_STD_1553B.Bus_Controller.radar_type_utils import determine_radar_type

logger = get_logger()

class Bus_Controller:
    def __init__(self):
        self.listening = False
        self.stop_event = threading.Event()
        self.last_sent_status = None
        self.is_listening = False
        self.bcd = BC_deconstruct()
        self.bc_construct = BC_construct()
        self._lock = threading.Lock()
        self.pending_requests = {}  # Track pending requests by request_id
        self._event_loop = None
        # Reference to the BC_Listener created inside start_listener(), so
        # stop_listener() can actually reach it and tell it to stop (see
        # stop_listener() below for why this matters).
        self._listener = None
        # Message extractor for guaranteed field preservation
        self.message_extractor = get_bc_message_extractor()
        logger.info("Bus Controller initialized with message extractor")
        from FMOFP.local_messaging.routing.system_integration import route_message
        self.route_message = route_message  # Import here to avoid circular import issues

    def _translate_precipitation_binary_data(self, binary_value: int) -> dict:
        """

        Translate binary precipitation data into structured format

        Args:
            binary_value: Integer containing encoded precipitation data

        Returns:
            dict: Structured precipitation data with position, type, rate, and intensity
        """
        try:
            # Log binary representation
            logger.info(f"[BC_PRECIP] Translating binary data: {binary_value} (0x{binary_value:04X}, {bin(binary_value)[2:].zfill(16)})")

            # Extract position coordinates (upper byte for X, lower byte for Y)
            x_coordinate = (binary_value >> 8) & 0xFF  # Extract upper byte
            y_coordinate = binary_value & 0xFF         # Extract lower byte

########### Comment from data_response_sender.py ###############    We need to decode from this method to get the precip values
# This decoding should happen later in the precipitation processing pipeline,
# after the data has finished processing in the BC and is ready to go to the local system.

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
####################################################################################


            # Adjust for shifted coordinates
            # Subtract 128 to convert from 0-255 range back to -128 to 127 range
            # This mirrors the RT encoding which adds 128 to handle negative values
            x_coordinate_adjusted = x_coordinate - 128
            y_coordinate_adjusted = y_coordinate - 128

            # Extract precipitation characteristics using the correct bit positions from PrecipitationData.to_data_words()
            # Format: [Type: 2 bits][Rate: 7 bits][Intensity: 6 bits][Show: 1 bit]
            type_code = (binary_value >> 14) & 0x3  # Extract bits 15-14 (2 bits for type)
            rate_val = (binary_value >> 7) & 0x7F   # Extract bits 13-7 (7 bits for rate)
            intensity_val = (binary_value >> 1) & 0x3F  # Extract bits 6-1 (6 bits for intensity)
            show_bit = binary_value & 0x1           # Extract bit 0 (1 bit for show_values)

            # Convert to actual values - proper scaling factor inverse
            rate = rate_val / 100.0  # Divide by RATE_SCALE (100.0)
            intensity = intensity_val / 5000.0  # Divide by INTENSITY_SCALE (5000.0)

            # Map type code to precipitation type
            type_map = {0: 'rain', 1: 'snow', 2: 'hail', 3: 'mixed'}
            precip_type = type_map.get(type_code, 'rain')

            # Ensure intensity is never zero (for visibility)
            if intensity < 0.1:
                intensity = 0.1

            # Log the decoded data with both raw and adjusted coordinates
            logger.info(f"[BC_PRECIP] Decoded precipitation data:")
            logger.info(f"[BC_PRECIP] - Position X: {x_coordinate} (adjusted: {x_coordinate_adjusted})")
            logger.info(f"[BC_PRECIP] - Position Y: {y_coordinate} (adjusted: {y_coordinate_adjusted})")
            logger.info(f"[BC_PRECIP] - Type code: {type_code} -> {precip_type}")
            logger.info(f"[BC_PRECIP] - Rate: raw={rate_val}, decoded={rate} mm/hr (using scaling factor 1/100.0)")
            logger.info(f"[BC_PRECIP] - Intensity: raw={intensity_val}, decoded={intensity} (using scaling factor 1/5000.0)")

            # Return structured data with adjusted coordinates
            return {
                'position': [float(x_coordinate_adjusted), float(y_coordinate_adjusted)],
                'type': precip_type,
                'rate': float(rate),
                'intensity': float(intensity),
                'show_values': True,
                'binary_source': binary_value
            }
        except Exception as e:
            logger.error(f"[BC_PRECIP] Error translating binary data: {e}")
            logger.error(traceback.format_exc())
            return {
                'position': [0.0, 0.0],
                'type': 'rain',
                'rate': 0.0,
                'intensity': 0.0,
                'show_values': True,
                'error': str(e),
                'binary_source': binary_value
            }

    # Async message processing has been removed to ensure all messages go through the Unified Router

    def _get_rt_address(self, system_name):
        """Get RT address from address book."""
        try:
            return ADDRESS_BOOK[system_name]['address']
        except KeyError:
            logger.error(f"No address found for system: {system_name}")
            raise

    def _get_subaddress(self, system_name, command_word):
        """Get subaddress from address book."""
        try:
            # Get subaddresses from address book
            subaddresses = ADDRESS_BOOK[system_name]['subaddresses']
            # First try direct matching with command_word
            for subaddress_name, subaddress in subaddresses.items():
                # Check for direct match or command_word containing subaddress_name
                if command_word == subaddress_name or subaddress_name.lower() in command_word.lower():
                    return subaddress
        except Exception as e:
            logger.error(f"Error getting subaddress: {e}")

    async def send_message(self, frames, request_id=None, metadata=None):
        """
        Send message frames to RT using MIL-STD-1553B messaging.

        Args:
            frames: List of frames to send
            request_id: Optional request ID for tracking
            metadata: Optional metadata dictionary to encode into data words
        """
        try:
            # Get the MIL-STD-1553B messaging instance
            msg_1553 = get_send_1553_msg()

            # Extract command and data frames.
            # `frames` is documented as "List of frames to send", but the
            # only guard here was for a bare string (since a str supports
            # __getitem__/slicing too, and without this it would get sliced
            # into individual characters instead of treated as one frame).
            # A single non-list/tuple object -- e.g. a MIL_STD_1553B_Message
            # instance, the natural single-message calling convention --
            # was never handled, so frames[0] raised TypeError: '...Message'
            # object is not subscriptable (confirmed live). Generalize the
            # guard to wrap any non-list/tuple argument as a single frame.
            if not isinstance(frames, (list, tuple)):
                frames = [frames]

            command = frames[0]
            data = frames[1:] if len(frames) > 1 else []

            # Send through MIL-STD-1553B compliant system with metadata
            return await msg_1553.send_message(command, data, request_id, metadata)

        except Exception as e:
            # NOTE: this previously logged "Error handling status word" and
            # built an error_info dict referencing frame, status_word_frame,
            # rt_address, and radar_type -- none of which are defined
            # anywhere in this method (send_message has no such locals).
            # That was copy-pasted from an unrelated status-word-handling
            # method and crashed with NameError the moment any real
            # exception here needed to be reported, masking the original
            # error entirely (confirmed live: the TypeError above was
            # immediately followed by "name 'frame' is not defined").
            # Replaced with diagnostics that only reference this method's
            # actual locals.
            logger.error(f"[BC] Error sending message: {e}")
            logger.error(traceback.format_exc())
            error_info = {
                "error": str(e),
                "timestamp": time.time(),
                "frames_type": type(frames).__name__,
                "request_id": request_id,
            }
            logger.error(f"send_message error details: {error_info}")
            raise

    async def process_frame(self, frame):
        """Process received frames with block transfer handling."""
        try:
            # Get the block transfer aggregator
            aggregator = get_block_transfer_aggregator()

            # Convert frame to proper format for transfer detection
            parsed_frame = frame
            if isinstance(frame, str) and (frame.startswith('{') and frame.endswith('}')):
                try:
                    # Try to parse as dictionary if it's a string representation
                    parsed_frame = json.loads(frame)
                    logger.info(f"[BC] Successfully parsed frame string as dictionary")
                except (ValueError, SyntaxError) as e:
                    # Continue with string processing if parsing fails
                    logger.warning(f"[BC] Failed to parse frame as dictionary: {e}")
                    pass

            # Track key identifiers for logging
            request_id = "unknown"
            if isinstance(parsed_frame, dict):
                request_id = parsed_frame.get('request_id', 'unknown')
                logger.info(f"[BC] Processing frame with request_id: {request_id}")

            # Check if this is a block transfer message
            # detection for already aggregated messages to prevent loops
            already_aggregated = False
            if isinstance(parsed_frame, dict):
                metadata = parsed_frame.get('metadata', {})
                if isinstance(metadata, dict) and metadata.get('aggregated_block_transfer') == True:
                    already_aggregated = True
                    logger.info(f"[BC] Detected already aggregated block transfer message, processing directly")

            if not already_aggregated and isinstance(parsed_frame, dict) and aggregator.is_transfer_message(parsed_frame):
                logger.info(f"[BC] Detected block transfer message with request_id: {request_id}")

                # Register with aggregator, which will accumulate messages until the transfer is complete
                result = aggregator.register_message(parsed_frame)

                if result is None:
                    # Transfer still in progress, DO NOT PROCESS FURTHER
                    logger.info(f"[BC] Block transfer in progress for request_id: {request_id}, halting further processing")
                    return

                # Transfer complete - process the aggregated message
                logger.info(f"[BC] Block transfer complete for request_id: {request_id}, processing aggregated message")

                # Apply message structure normalization to ensure all required fields are present
                normalizer = get_message_structure_normalizer()
                result = normalizer.normalize_message_structure(result)
                logger.info(f"[BC] Normalized message structure to ensure routing compliance")

                frame = result
                logger.info(f"[BC] Aggregated message type: {result.get('message_type')}, command_type: {result.get('command_type')}")

                # If the aggregated message contains data, log its size
                if 'data' in result and isinstance(result['data'], list):
                    logger.info(f"[BC] Aggregated message contains {len(result['data'])} data items")
                elif 'data' in result and isinstance(result['data'], dict) and result['data'].get('completion_message'):
                    logger.info(f"[BC] Aggregated message contains completion data")

                # Route aggregated message directly without frame splitting
                if isinstance(result, dict) and 'message_type' in result and 'command_type' in result:
                    logger.info(f"[BC] Routing complete aggregated message directly: {result.get('message_type')}/{result.get('command_type')}")

                    # Directly route the message
                    route_result = self.route_message(result)

                    # Log success/failure
                    if route_result:
                        logger.info(f"[BC] Successfully routed aggregated message with direct routing")
                    else:
                        logger.error(f"[BC] Failed to route aggregated message")

                    # Return here to prevent frame splitting and further processing
                    return

            # Continue with normal processing for non-aggregated messages
            frames = []
            if isinstance(frame, list):
                frames.extend(frame)
            else:
                frames.append(str(frame))

            # Process each frame
            for raw_frame in frames:
                try:
                    # Check for aggregated block transfer
                    if isinstance(raw_frame, dict) and raw_frame.get('metadata', {}).get('aggregated_block_transfer', False):
                        logger.info(f"[BC] Processing aggregated block transfer as status word")
                        await self._process_status_word(raw_frame)
                        continue

                    # Clean frame
                    cleaned_frame = self._clean_frame(raw_frame)
                    if not cleaned_frame:
                        continue

                    # Process status word
                    if cleaned_frame.startswith('100'):
                        # Pass the original raw_frame instead of just the cleaned binary string
                        # This ensures that metadata is preserved for proper routing
                        await self._process_status_word(raw_frame)
                        continue

                    # Process command/data word
                    self._process_command_data_word(cleaned_frame)

                except Exception as e:
                    logger.error(f"Error processing frame {raw_frame}: {e}")
                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error in process_frame: {e}")
            logger.error(traceback.format_exc())

    def _clean_frame(self, frame):
        """Clean and validate frame according to MIL-STD-1553B standard."""
        try:
            # Handle dictionary format
            if isinstance(frame, dict):
                # Check if this is a block transfer message with comprehensive flag detection
                is_block_transfer = False
                metadata = frame.get('metadata', {})
                # Check both top-level frame and metadata for all three transfer flags
                is_transfer_init = frame.get('is_transfer_init') or metadata.get('is_transfer_init')
                is_transfer_data = frame.get('is_transfer_data') or metadata.get('is_transfer_data')
                is_transfer_complete = frame.get('is_transfer_complete') or metadata.get('is_transfer_complete')

                # Check message type for precipitation or VIL data
                message_type = frame.get('message_type') or (metadata.get('message_type') if metadata else None)
                command_type = frame.get('command_type') or (metadata.get('command_type') if metadata else None)
                command_name = frame.get('command_name') or (metadata.get('command_name') if metadata else None)

                # Additional check for precipitation and VIL data which needs block transfer handling
                is_precipitation = False
                is_vil = False

                if message_type and isinstance(message_type, str):
                    is_precipitation = 'precipitation' in message_type.lower()
                    is_vil = 'vil' in message_type.lower()

                if command_type and isinstance(command_type, str) and not (is_precipitation or is_vil):
                    is_precipitation = 'precipitation' in command_type.lower() or 'precip' in command_type.lower()
                    is_vil = 'vil' in command_type.lower()

                if command_name and isinstance(command_name, str) and not (is_precipitation or is_vil):
                    is_precipitation = 'precipitation' in command_name.lower()
                    is_vil = 'vil' in command_name.lower()

                # If this is precipitation or VIL data, treat it as a block transfer
                if is_precipitation or is_vil:
                    is_block_transfer = True
                    data_type = "precipitation" if is_precipitation else "VIL"
                    logger.info(f"[BC] Detected {data_type} data message - treating as block transfer")

                if is_transfer_init or is_transfer_data or is_transfer_complete:
                    is_block_transfer = True
                    if is_transfer_init:
                        logger.info(f"[BC] Detected block transfer initialization message")
                    elif is_transfer_data:
                        logger.info(f"[BC] Detected block transfer data message")
                    elif is_transfer_complete:
                        logger.info(f"[BC] Detected block transfer completion message")

                if 'status_word' in frame:
                    # Extract status word from dictionary
                    frame_str = frame['status_word']
                    logger.info(f"[BC] Extracted status_word from dictionary: {frame_str}")
                    # Ensure it's a valid 20-bit word
                    if len(frame_str) != 20 or not all(bit in '01' for bit in frame_str):
                        logger.warning(f"[BC] Invalid status word format: {frame_str}")
                        return None
                    return self._process_single_frame(frame_str, is_block_transfer)
                elif 'frames' in frame and frame['frames']:
                    # For block transfer messages, return the first frame without validation
                    if is_block_transfer:
                        frame_str = frame['frames'][0]
                        logger.info(f"[BC] Extracted first frame from block transfer: {frame_str}")
                        # Ensure it's a valid 20-bit word
                        if len(frame_str) != 20 or not all(bit in '01' for bit in frame_str):
                            logger.warning(f"[BC] Invalid frame format in block transfer: {frame_str}")
                            return None
                        return self._process_single_frame(frame_str, is_block_transfer)
                    # For regular messages, extract first frame from frames list
                    else:
                        frame_str = frame['frames'][0]
                        logger.info(f"[BC] Extracted first frame from frames list: {frame_str}")
                        # Ensure it's a valid 20-bit word
                        if len(frame_str) != 20 or not all(bit in '01' for bit in frame_str):
                            logger.warning(f"[BC] Invalid frame format in frames list: {frame_str}")
                            return None
                        return self._process_single_frame(frame_str, is_block_transfer)
                else:
                    logger.error(f"[BC] Invalid frame dictionary format: {frame}")
                    return None
            else:
                # Convert to string and clean
                frame_str = str(frame)
                # Skip processing if it's not a valid frame
                if not frame_str or len(frame_str) < 20 or not any(bit in '01' for bit in frame_str):
                    logger.warning(f"[BC] Skipping invalid frame: {frame_str}")
                    return None
                return self._process_single_frame(frame_str, False)

        except Exception as e:
            logger.error(f"[BC] Error cleaning frame: {e}")
            logger.error(traceback.format_exc())
            return None

    def _process_single_frame(self, frame_str, is_block_transfer=False):
        """Process a single frame string to validate and clean it according to MIL-STD-1553B."""
        try:
            # Handle dictionary format with status_word
            if isinstance(frame_str, dict) and 'status_word' in frame_str:
                status_word = frame_str['status_word']
                if isinstance(status_word, str) and len(status_word) == 20 and all(bit in '01' for bit in status_word):
                    logger.info(f"[BC] Extracted status_word from dictionary: {status_word}")
                    return status_word
                else:
                    logger.error(f"[BC] Invalid status_word in dictionary: {status_word}")
                    return None

            # Enhanced dictionary representation detection and handling
            if isinstance(frame_str, str) and frame_str.startswith('{') and frame_str.endswith('}'):
                try:
                    # Try to parse as a dictionary using json.loads
                    parsed_dict = json.loads(frame_str)

                    # Check if it has a status_word field
                    if isinstance(parsed_dict, dict) and 'status_word' in parsed_dict:
                        status_word = parsed_dict['status_word']

                        # Validate the status word
                        if isinstance(status_word, str) and len(status_word) == 20 and all(bit in '01' for bit in status_word):
                            logger.info(f"[BC] Extracted status_word from parsed dictionary: {status_word}")
                            return status_word
                        else:
                            logger.error(f"[BC] Invalid status_word in parsed dictionary: {status_word}")
                            return None

                    # Check for frames field which may contain valid frames
                    elif isinstance(parsed_dict, dict) and 'frames' in parsed_dict and isinstance(parsed_dict['frames'], list):
                        frames = parsed_dict['frames']

                        # Extract valid 20-bit frames with proper sync patterns
                        valid_frames = []
                        for frame in frames:
                            if isinstance(frame, str) and len(frame) == 20:
                                # Verify sync pattern (must be '100' or '001')
                                if frame.startswith('100') or frame.startswith('001'):
                                    valid_frames.append(frame)
                                    logger.info(f"[BC] Found valid frame in frames list: {frame}")

                        # If we found valid frames, return the first one
                        if valid_frames:
                            logger.info(f"[BC] Extracted {len(valid_frames)} valid frames from parsed dictionary")
                            return valid_frames[0]
                        else:
                            logger.error(f"[BC] No valid frames found in parsed dictionary")
                            return None

                except (ValueError, SyntaxError) as e:
                    logger.error(f"[BC] Error parsing dictionary-like string: {e}")
                    # Before falling through to normal processing, try more robust parsing
                    try:
                        # Check for framing patterns in the string that might indicate valid frames
                        # Look for patterns like: 'frames': ['100...', '001...']
                        if "'frames': [" in frame_str or '"frames": [' in frame_str:
                            # Find all 20-bit patterns that look like frames
                            import re
                            # Match either '100' or '001' followed by exactly 17 binary digits
                            binary_patterns = re.findall(r"['\"]((100|001)[01]{17})['\"]", frame_str)

                            if binary_patterns:
                                # Extract just the binary strings (first group in each match)
                                valid_frames = [pattern[0] for pattern in binary_patterns]
                                logger.info(f"[BC] Found {len(valid_frames)} valid frames using regex pattern matching")
                                # Return the first valid frame
                                return valid_frames[0]
                    except Exception as regex_error:
                        logger.error(f"[BC] Enhanced regex parsing failed: {regex_error}")
                        # Continue to normal processing

                # If json.loads fails, try string parsing as a fallback
                try:
                    if 'status_word' in frame_str:
                        # Find the status_word field
                        start_idx = frame_str.find('status_word') + len('status_word')
                        # Find the colon after status_word
                        colon_idx = frame_str.find(':', start_idx)
                        if colon_idx != -1:
                            # Find the start of the status word value (skip whitespace)
                            value_start = colon_idx + 1
                            while value_start < len(frame_str) and frame_str[value_start].isspace():
                                value_start += 1

                            # Find the end of the status word value (comma or closing brace)
                            value_end = frame_str.find(',', value_start)
                            if value_end == -1:
                                value_end = frame_str.find('}', value_start)

                            if value_end != -1:
                                # Extract the status word value
                                status_word = frame_str[value_start:value_end].strip()

                                # Clean any quotes or whitespace
                                status_word = status_word.strip("'\"").strip()

                                # Validate the status word
                                if len(status_word) == 20 and all(bit in '01' for bit in status_word):
                                    logger.info(f"[BC] Extracted status_word from string dictionary using fallback method: {status_word}")
                                    return status_word
                                else:
                                    logger.error(f"[BC] Invalid status_word extracted from string using fallback method: {status_word}")
                except Exception as e:
                    logger.error(f"[BC] Error in fallback string parsing: {e}")
                    # Continue with normal processing

            # Enhanced handling for string frames
            if isinstance(frame_str, str):
                # Check if this might be a binary string with dictionary format
                # This prevents treating dictionary strings as binary data, which leads to odd bit lengths
                if '{' in frame_str or '}' in frame_str or "'" in frame_str or '"' in frame_str:
                    logger.info(f"[BC] Detected potential dictionary format in string, length: {len(frame_str)}")

                    # Try to extract any valid 20-bit frames from the string
                    # Look for patterns starting with sync bits ('100' or '001') followed by 17 more bits
                    import re
                    frame_matches = re.findall(r'((?:100|001)[01]{17})', frame_str)

                    if frame_matches:
                        valid_frames = []
                        for match in frame_matches:
                            if len(match) == 20 and (match.startswith('100') or match.startswith('001')):
                                valid_frames.append(match)

                        if valid_frames:
                            logger.info(f"[BC] Found {len(valid_frames)} valid frames in dictionary-like string")
                            return valid_frames[0]  # Return the first valid frame

                    # If we detect dictionary format but can't extract valid frames,
                    # this is likely an invalid representation that would cause odd bit lengths
                    if any(char in "{}[]\'\":" for char in frame_str):
                        logger.warning(f"[BC] Rejecting dictionary-like string with no valid frames: {frame_str[:30]}...")
                        return None

                # Standard binary processing for non-dictionary strings
                frame_str = frame_str.replace('[', '').replace(']', '').replace('\\', '')
                frame_str = frame_str.replace('b"', '').replace('"', '').replace("'", "")

                # Extract binary data
                cleaned = ''.join(filter(lambda x: x in ['0', '1'], frame_str))

                # MIL-STD-1553B strictly requires 20-bit words
                if len(cleaned) != 20:
                    # For block transfer messages, extract valid 20-bit frames if possible
                    if is_block_transfer and len(cleaned) > 20:
                        logger.warning(f"[BC] Block transfer frame with length {len(cleaned)} bits - extracting first 20 bits")
                        cleaned = cleaned[:20]
                    # Detect concatenated frames that are multiple of 20 bits
                    elif len(cleaned) > 20 and (len(cleaned) % 20 == 0 or abs(len(cleaned) % 20) <= 4):
                        logger.info(f"[BC] Detected potentially concatenated frames: {len(cleaned)} bits")

                        # Use BlockTransferManager to split the oversized frame
                        from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
                        transfer_manager = get_block_transfer_manager()

                        # Split the frame into valid 20-bit chunks
                        split_frames = transfer_manager._split_oversized_frames(cleaned)

                        if split_frames and len(split_frames) > 0:
                            logger.info(f"[BC] Successfully split {len(cleaned)}-bit frame into {len(split_frames)} valid frames")
                            # Return the first valid frame and log the rest for processing in subsequent calls
                            return split_frames[0]
                        else:
                            # If splitting failed, fall back to extracting just the first 20 bits
                            logger.error(f"[BC] Failed to split oversized frame")
                    else:
                        logger.error(f"[BC] Invalid frame length: {len(cleaned)} bits - MIL-STD-1553B requires 20 bits")
                        return None

                # Validate sync bits according to MIL-STD-1553B
                if not (cleaned.startswith('100') or cleaned.startswith('001')):
                    logger.error(f"[BC] Invalid sync bits: {cleaned[:3]} - must be '100' (command/status) or '001' (data)")
                    return None

                # Validate parity (odd parity) according to MIL-STD-1553B
                ones_count = cleaned[:-1].count('1')
                expected_parity = '1' if ones_count % 2 == 0 else '0'
                if cleaned[-1] != expected_parity:
                    logger.error(f"[BC] Parity check failed: expected {expected_parity}, got {cleaned[-1]}")
                    return None

                return cleaned
            else:
                logger.error(f"[BC] Invalid frame format: {type(frame_str)}")
                return None

        except Exception as e:
            logger.error(f"[BC] Error cleaning frame: {e}")
            logger.error(traceback.format_exc())
            return None

    async def _process_status_word(self, frame):
        """Process status word frame."""
        try:
            logger.info(f"[BC] Processing status word frame: {frame}")

            if isinstance(frame, dict) and 'timestamp' in frame:
                # Preserve the original timestamp
                original_timestamp = frame.get('timestamp')
                logger.info(f"[BC] Preserving original timestamp: {original_timestamp}")

            # Use message extractor to extract all fields
            extracted = self.message_extractor.extract_all_fields(frame)

            # Log the results including critical fields
            logger.info(f"[BC] Extracted fields: command_name={extracted.get('command_name')}, "
                       f"request_id={extracted.get('request_id')}, "
                       f"timestamp={extracted.get('timestamp')}, "
                       f"extraction_timestamp={extracted.get('extraction_timestamp')}")

            # Pull critical fields from extraction result
            status_word_frame = extracted.get('status_word') or extracted.get('binary_data')
            status_type = extracted.get('command_type')
            msg_type = extracted.get('message_type')
            cmd_name = extracted.get('command_name')
            metadata = extracted.get('metadata', {})
            request_id = extracted.get('request_id')
            rt_address = extracted.get('rt_address')
            radar_type = extracted.get('radar_type')
            destination = extracted.get('destination')
            source = extracted.get('source_system')
            mode = extracted.get('mode')
            mode_value = extracted.get('mode_value')

            # If rt_address is still none and we have a dictionary frame,
            # try to determine from destination or other fields
            if rt_address is None and isinstance(frame, dict):
                destination = frame.get('destination', None)
                if destination is not None:
                    # Map destination name to RT address based on address book
                    if destination == 'radar' or destination == 'radar_system':
                        rt_address = 9  # Radar system address
                        logger.info(f"[BC] Setting RT address to 9 based on destination: {destination}")
                    elif destination == 'display_system' or destination == 'displays':
                        rt_address = 11  # Display system address
                        logger.info(f"[BC] Setting RT address to 11 based on destination: {destination}")
                    elif destination == 'weather_radar':    # Heading to radar display in MFD (IF weather_radar is the SUBADDRESS, its going to the actual radar system)
                        rt_address = 11
                        radar_type = 'weather_radar'        # Also set the radar_type
                        logger.info(f"[BC] Setting RT address to 11 and radar_type to weather_radar")
                    elif destination == 'tfr_radar':        # Heading to radar display in MFD (IF tfr_radar is the SUBADDRESS, its going to the actual radar system)
                        rt_address = 11
                        radar_type = 'tfr_radar'
                        logger.info(f"[BC] Setting RT address to 11 and radar_type to tfr_radar")
                    elif destination == 'sar_radar':       # Heading to radar display in MFD (IF sar_radar is the SUBADDRESS, its going to the actual radar system)
                        rt_address = 11
                        radar_type = 'sar_radar'
                        logger.info(f"[BC] Setting RT address to 11 and radar_type to sar_radar")
                    elif destination == 'targeting_radar':  # Heading to radar display in MFD (IF targeting_radar is the SUBADDRESS, its going to the actual radar system)
                        rt_address = 11
                        radar_type = 'targeting_radar'
                        logger.info(f"[BC] Setting RT address to 11 and radar_type to targeting_radar")
                    elif destination == 'aewc_radar':       # Heading to radar display in MFD (IF aewc_radar is the SUBADDRESS, its going to the actual radar system)
                        rt_address = 11
                        radar_type = 'aewc_radar'
                        logger.info(f"[BC] Setting RT address to 11 and radar_type to aewc_radar")
                    else:
                        # Try to look up the destination in the ADDRESS_BOOK
                        try:
                            # This handles all other system types that may be in the address book
                            rt_address = ADDRESS_BOOK[destination]['address']
                            logger.info(f"[BC] Found RT address {rt_address} for destination {destination} in ADDRESS_BOOK")
                        except (KeyError, TypeError):
                            logger.error(f"[BC] Could not determine RT address for destination: {destination}")

                # if we have a dispaly system address but no radar_type, set it to display_system
                if rt_address == 11 and not radar_type:
                    radar_type = frame.get('destination', None)
                    logger.info(f"[BC] Setting radar_type to display_system for RT address 11")


                # If we have a radar system address but no radar_type, try to determine it from metadata or subaddress
                if rt_address == 9 and not radar_type:
                    # Check metadata for radar_type or system_type
                    metadata = frame.get('metadata', {})
                    if isinstance(metadata, dict):
                        radar_type = metadata.get('radar_type') or metadata.get('system_type')

                    # If still not found, get from subaddress if available
                    if not radar_type:
                        subaddress = frame.get('sub_address', None) or metadata.get('subaddress', None)
                        if subaddress:
                            # Map subaddress to radar_type
                            radar_map = {
                                1: 'weather_radar',
                                2: 'tfr_radar',
                                3: 'sar_radar',
                                4: 'targeting_radar',
                                5: 'aewc_radar'
                            }
                            radar_type = radar_map.get(subaddress)
                            if radar_type:
                                logger.info(f"[BC] Determined radar_type {radar_type} from subaddress {subaddress}")
                timestamp = frame.get('timestamp', time.time())
                command_type = frame.get('command_type', None)
                message_type = frame.get('message_type', None)
                command_name = frame.get('command_name', None)
                metadata = frame.get('metadata', {})

                logger.info(f"[BC] Structured message details:")
                logger.info(f"[BC]   - Status word: {status_word_frame}")
                logger.info(f"[BC]   - Request ID: {request_id}")
                logger.info(f"[BC]   - RT address: {rt_address}")
                logger.info(f"[BC]   - Command type: {command_type}")
                logger.info(f"[BC]   - Message type: {message_type}")
                logger.info(f"[BC]   - Command name: {command_name}")

                # Log metadata if available
                if metadata:
                    logger.info(f"[BC] Message metadata: {metadata}")

                    # Check for mode change completion
                    if command_type == 'mode_change_completion':
                        old_mode = metadata.get('old_mode')
                        new_mode = metadata.get('new_mode')
                        if old_mode and new_mode:
                            logger.info(f"[BC] Mode change completion: {old_mode} -> {new_mode}")
            else:
                # Check if frame is a string or a dictionary-like string
                if isinstance(frame, str):
                    # Check if it's a dictionary-like string
                    if frame.startswith('{') and frame.endswith('}'):
                        try:
                            # Try to parse as a dictionary
                            parsed_dict = json.loads(frame)
                            if isinstance(parsed_dict, dict) and 'status_word' in parsed_dict:
                                # Recursively call with the parsed dictionary
                                logger.info(f"[BC] Parsed dictionary-like string into dictionary. REPROCESSING...")
                                return await self._process_status_word(parsed_dict)
                        except (ValueError, SyntaxError) as e:
                            logger.error(f"[BC] Error parsing dictionary-like string: {e}")
                            # Continue with raw frame processing

                    # Raw frame processing for string
                    status_word_frame = frame
                    request_id = None
                    # Properly validate the frame before extracting RT address
                    if isinstance(frame, str) and len(frame) >= 8 and all(bit in '01' for bit in frame[:8]):
                        # Make sure we're dealing with a valid binary string before extracting RT address
                        rt_address = int(frame[3:8], 2)
                        logger.info(f"[BC] Extracted RT address from raw binary frame: {rt_address}")
                    else:
                        logger.warning(f"[BC] Could not extract RT address from invalid frame format")
                        rt_address = None
                    timestamp = time.time()
                    command_type = None
                    message_type = None
                    command_name = None
                    radar_type = None
                    metadata = {}

                    if frame is not None and hasattr(frame, 'command_type'):
                        command_type = frame.command_type
                    else:
                        logger.info(f"[BC] No command_type found in frame: {frame}")
                        pass

                    logger.info(f"[BC] Raw frame details:")
                    logger.info(f"[BC]   - Status word: {status_word_frame}")
                    logger.info(f"[BC]   - RT address (extracted): {rt_address}")
                else:
                    # Not a dictionary or string, can't process
                    logger.error(f"[BC] Unsupported frame type: {type(frame)}")
                    return

            # Decode status word
            status_word = self.bcd.deconstruct_status_word(status_word_frame)
            if not status_word:
                logger.error("[BC] Failed to decode status word")
                return

            logger.info(f"[BC] Decoded status word: {status_word}")

            # If no RT address provided, extract from status word if it's a valid binary string
            if rt_address is None and status_word_frame:
                if isinstance(status_word_frame, str) and len(status_word_frame) >= 8 and all(bit in '01' for bit in status_word_frame[:8]):
                    # Make sure we're dealing with a binary string before extracting RT address
                    rt_address = int(status_word_frame[3:8], 2)
                    logger.info(f"[BC] Extracted RT address from status word: {rt_address}")
                else:
                    logger.warning(f"[BC] Could not extract RT address from invalid status word format")
                    # Try to extract RT address from original frame if it's a dictionary
                    if isinstance(frame, dict):
                        rt_address = frame.get('rt_address')
                        if rt_address is not None:
                            logger.info(f"[BC] Using RT address {rt_address} from frame dictionary")

            # If no request_id, try to find matching request using enhanced search
            if not request_id:
                logger.info("[BC] No request_id provided, searching for matching request using enhanced criteria")
                current_time = time.time()

                # Log all available pending requests for debugging
                if self.pending_requests:
                    logger.info(f"[BC] Available pending requests: {list(self.pending_requests.keys())}")
                    for req_id, req in list(self.pending_requests.items()):
                        logger.info(f"[BC] Pending request {req_id}: rt_address={req.get('rt_address')}, subaddress={req.get('subaddress')}")
                else:
                    logger.info("[BC] No pending requests available")

                # First try exact RT address match
                matched_requests = []
                for req_id, req in list(self.pending_requests.items()):
                    # Skip expired requests but keep them for now
                    if current_time - req['timestamp'] > 5.0:
                        logger.info(f"[BC] Request {req_id} expired: {current_time - req['timestamp']} seconds")
                        continue

                    # Log request details for debugging
                    logger.info(f"[BC] Evaluating request {req_id} for RT={rt_address}")
                    logger.info(f"[BC]   Request RT address: {req.get('rt_address')}")

                    # Match criteria
                    match_score = 0
                    match_reasons = []

                    # RT address exact match (most important)
                    if req.get('rt_address') == rt_address:
                        match_score += 3
                        match_reasons.append(f"RT address match: {rt_address}")

                    # Add this request to candidates with score and reasons
                    if match_score > 0:
                        matched_requests.append((req_id, req, match_score, match_reasons))
                        logger.info(f"[BC] Request {req_id} matched with score {match_score}: {', '.join(match_reasons)}")

                # Sort by match score (highest first)
                matched_requests.sort(key=lambda x: x[2], reverse=True)

                # Use the highest scoring match if any
                if matched_requests:
                    best_match = matched_requests[0]
                    request_id = best_match[0]
                    command_type = best_match[1].get('command_word', None)
                    logger.info(f"[BC] Found best matching request: {request_id}, score: {best_match[2]}")
                    logger.info(f"[BC] Match reasons: {', '.join(best_match[3])}")
                    logger.info(f"[BC] command_type: {command_type}")
                else:
                    # Only now remove expired requests
                    for req_id, req in list(self.pending_requests.items()):
                        if current_time - req['timestamp'] > 5.0:
                            logger.info(f"[BC] Removing expired request: {req_id}")
                            del self.pending_requests[req_id]

            # Get request details
            request_details = self.pending_requests.get(request_id, {})
            subaddress_int = request_details.get('subaddress', 1)
            logger.info(f"[BC] Request details: subaddress={subaddress_int}")

            # Determine system type based on RT address from addressbook
            system_type = None
            if rt_address == 9:  # Radar system (RT address 9)
                # Use radar system helper to determine radar type
                system_type, radar_type = determine_radar_type(frame, subaddress_int)
                if not system_type:
                    return
                logger.info(f"[BC] Determined system type: {system_type} (radar)")

            elif rt_address == 11:  # Display system (RT address 11)
                display_map = {
                    11: 'pfd',
                    12: 'mfd',
                    13: 'eicas',
                    14: 'radar_display',
                    15: 'tsd',
                    16: 'sms'
                }
                system_type = display_map.get(subaddress_int, 'display_system')
                logger.info(f"[BC] Mapped RT address 11 to display system: {system_type}")

                # Set radar_type to display_system for backward compatibility
                radar_type = 'display_system'
            else:
                logger.warning(f"[BC] Unrecognized RT address: {rt_address}")
                return

            # Store acknowledgment with retry logic
            if system_type:
                max_retries = 5
                retry_delay = 1.0
                last_error = None

                for attempt in range(max_retries):
                    try:
                        # Get the appropriate response service based on RT address
                        if rt_address == 1:  # Avionics
                            # Avionics health/status is monitored passively;
                            # no dedicated response service — log and continue.
                            logger.info(f"[BC] Avionics (RT {rt_address}) acknowledgment received")
                            response_service = None
                        elif rt_address == 2:  # Communications
                            try:
                                from FMOFP.local_messaging.routing.response_services.system_response_services.CommsResponseService import get_comms_response_service
                                response_service = get_comms_response_service()
                                logger.info(f"[BC] Using CommsResponseService for RT {rt_address}")
                            except Exception as _e:
                                logger.warning(f"[BC] CommsResponseService unavailable ({_e}); skipping")
                                response_service = None
                        elif rt_address == 3:  # Engine management
                            try:
                                from FMOFP.local_messaging.routing.response_services.system_response_services.FMSResponseService import get_fms_response_service
                                response_service = get_fms_response_service()
                                logger.info(f"[BC] Using FMSResponseService for engine RT {rt_address}")
                            except Exception as _e:
                                logger.warning(f"[BC] FMSResponseService unavailable for engine ({_e}); skipping")
                                response_service = None
                        elif rt_address == 4:  # Environmental control system
                            logger.info(f"[BC] ECS (RT {rt_address}) acknowledgment received")
                            response_service = None
                        elif rt_address == 5:  # Flight control system
                            try:
                                from FMOFP.local_messaging.routing.response_services.system_response_services.FCSResponseService import get_fcs_response_service
                                response_service = get_fcs_response_service()
                                logger.info(f"[BC] Using FCSResponseService for RT {rt_address}")
                            except Exception as _e:
                                logger.warning(f"[BC] FCSResponseService unavailable ({_e}); skipping")
                                response_service = None
                        elif rt_address == 6:  # Mission planning
                            try:
                                from FMOFP.Systems.missionPlanning.missionService import get_mission_service
                                # Mission service does not expose a 1553B response-service
                                # interface yet; log the acknowledgment and continue.
                                logger.info(f"[BC] Mission planning (RT {rt_address}) acknowledgment received")
                                response_service = None
                            except Exception as _e:
                                logger.warning(f"[BC] MissionService unavailable ({_e}); skipping")
                                response_service = None
                        elif rt_address == 7:  # Navigation
                            try:
                                from FMOFP.local_messaging.routing.response_services.data_response_services.fms_navigation_response_service import get_fms_navigation_response_service
                                response_service = get_fms_navigation_response_service()
                                logger.info(f"[BC] Using FMSNavigationResponseService for RT {rt_address}")
                            except Exception as _e:
                                logger.warning(f"[BC] FMSNavigationResponseService unavailable ({_e}); skipping")
                                response_service = None
                        elif rt_address == 8:  # Power management
                            logger.info(f"[BC] Power management (RT {rt_address}) acknowledgment received")
                            response_service = None
                        elif rt_address == 9:  # Radar system
                            response_service = get_radar_response_service()
                            logger.info(f"[BC] Using RadarResponseService for RT address {rt_address}")
                        elif rt_address == 10:  # Sensor management
                            logger.info(f"[BC] Sensor management (RT {rt_address}) acknowledgment received")
                            response_service = None
                        elif rt_address == 11:  # Display system
                            response_service = get_display_response_service()
                            logger.info(f"[BC] Using DisplayResponseService for RT address {rt_address}")
                        elif rt_address == 12:  # Flight Management System
                            try:
                                from FMOFP.local_messaging.routing.response_services.system_response_services.FMSResponseService import get_fms_response_service
                                response_service = get_fms_response_service()
                                logger.info(f"[BC] Using FMSResponseService for RT {rt_address}")
                            except Exception as _e:
                                logger.warning(f"[BC] FMSResponseService unavailable ({_e}); skipping")
                                response_service = None
                        elif rt_address in (13, 14, 15, 16):
                            # Unassigned RT addresses — no system mapped in rtAddressConfig.xml
                            logger.warning(f"[BC] Unassigned RT address {rt_address} — ignoring")
                            return

                        ack_request_id = request_id
                        if not ack_request_id:
                            logger.error("[BC] No request_id found for acknowledgment")
                            return

                        logger.info(f"[BC] Storing acknowledgment for {radar_type} with request_id {ack_request_id}")

                        # Extract mode information from metadata if available
                        mode = None
                        mode_value = None

                        # Check if metadata contains mode information
                        if isinstance(metadata, dict):
                            mode = metadata.get('mode')
                            mode_value = metadata.get('mode_value')
                            logger.info(f"[BC] Found mode in metadata: {mode}")
                            logger.info(f"[BC] Found mode_value in metadata: {mode_value}")

                        # Create additional_info with mode information
                        additional_info = {
                            'rt_address': rt_address,
                            'subaddress': subaddress_int,
                            'status_word': status_word,
                            'status_frame': status_word_frame,
                            'attempt': attempt + 1,
                            'original_request_id': request_id
                        }

                        # Add mode information to additional_info if available
                        if mode:
                            additional_info['mode'] = mode
                        if mode_value:
                            additional_info['mode_value'] = mode_value


                        # Store acknowledgment with mode information
                        # Different handling based on service type
                        if response_service is None:
                            # Systems without a dedicated response service
                            # (avionics, ECS, power, sensor, mission, unassigned)
                            logger.info(f"[BC] No response service for RT {rt_address} — acknowledgment logged only")
                        elif rt_address == 9:  # Radar service
                            # RadarResponseService uses handle_status_word_async
                            await response_service.handle_status_word_async({
                                'timestamp': timestamp,
                                'command_type': command_type,
                                'radar_type': radar_type,
                                'status': 'acknowledged',
                                'request_id': ack_request_id,
                                'mode': mode,
                                'mode_value': mode_value,
                                'additional_info': additional_info
                            })
                        elif rt_address == 11:  # Display service
                            # DisplayResponseService uses handle_display_command
                            await response_service.handle_display_command({
                                'timestamp': timestamp,
                                'command_type': command_type,
                                'display_type': radar_type,
                                'status': 'acknowledged',
                                'request_id': ack_request_id,
                                'mode': mode,
                                'mode_value': mode_value,
                                'additional_info': additional_info
                            })


                        logger.info(f"[BC] Awaited stored acknowledgment for {radar_type} with request_id {ack_request_id} successfully")

                        # Use unified router instead of direct routing
                        # Use unified router instead of direct routing
                        # Convert status word binary string to integer for MIL_STD_1553B_Message compatibility
                        # Extract the 16 data bits (bits 3-18) and convert to integer
                        if status_word_frame and len(status_word_frame) >= 19:
                            # Skip the 3 sync bits and extract the 16 data bits
                            data_bits = status_word_frame[3:19]
                            try:
                                # Convert binary string to integer
                                data_int = int(data_bits, 2)
                                logger.info(f"[BC] Converted status word data bits '{data_bits}' to integer: {data_int}")
                            except ValueError:
                                # Fallback to a default value if conversion fails
                                logger.error(f"[BC] Failed to convert status word data bits to integer: {data_bits}")
                                data_int = 0
                        else:
                            logger.error(f"[BC] Invalid status word frame format: {status_word_frame}")
                            data_int = 0

                        # Ensure metadata is defined for error handling
                        if not 'metadata' in locals() or metadata is None:
                            metadata = {}

                        # Extract message_type, command_type, and command_name from the original message
                        # This is critical for proper routing of completion messages
                        original_message_type = message_type
                        original_command_type = command_type
                        original_command_name = command_name

                        # Check if this is a mode change completion message based on metadata
                        if isinstance(frame, dict) and 'metadata' in frame:
                            metadata_dict = frame['metadata']
                            if isinstance(metadata_dict, dict):
                                # Always prioritize metadata fields over default values
                                # Check for explicit message type in metadata
                                if 'message_type' in metadata_dict:
                                    original_message_type = metadata_dict['message_type']
                                    logger.info(f"[BC] Using message_type from metadata: {original_message_type}")

                                # Check for explicit command type in metadata
                                if 'command_type' in metadata_dict:
                                    original_command_type = metadata_dict['command_type']
                                    logger.info(f"[BC] Using command_type from metadata: {original_command_type}")

                                # Check for explicit command name in metadata
                                if 'command_name' in metadata_dict:
                                    original_command_name = metadata_dict['command_name']
                                    logger.info(f"[BC] Using command_name from metadata: {original_command_name}")

                                # Check for mode change completion indicators in metadata as a fallback
                                elif 'message_purpose' in metadata_dict and metadata_dict['message_purpose'] == 'mode_change_completion':
                                    logger.info(f"[BC] Detected mode change completion message from metadata")
                                    original_message_type = metadata_dict.get('message_type', 'weather_radarModeChangeCompletion')
                                    original_command_type = 'mode_change_completion'
                                    original_command_name = metadata_dict.get('command_name', 'WEATHER_RADAR_MODE_CHANGE_COMPLETION')

                        # First, handle message_type if missing
                        if original_message_type == None:
                            # Command Ack Status Word
                            original_message_type = 'status_word_acknowledgment'
                            logger.warning(f"[BC] Status Message type is unknown, using default: {original_message_type}")

                        # Next, handle command_type if missing
                        if original_command_type == None:
                            # Try to determine command_type from message_type
                            if 'precipitation' in original_message_type.lower() or 'precip' in original_message_type.lower():
                                original_command_type = 'precipitation_data'
                                logger.info(f"[BC] Inferred command_type 'precipitation_data' from message_type: {original_message_type}")
                            elif 'vil' in original_message_type.lower():
                                original_command_type = 'vil_data'
                                logger.info(f"[BC] Inferred command_type 'vil_data' from message_type: {original_message_type}")
                            else:
                                # Default to mode_change_completion for other status words
                                original_command_type = 'mode_change_completion'
                                logger.warning(f"[BC] Status Command type is unknown, using default: {original_command_type}")

                        # First try to use the cmd_name (command_name) from the original extraction
                        if cmd_name and (original_command_name == None or original_command_name == ''):
                            original_command_name = cmd_name
                            logger.info(f"[BC] Using extracted command_name: {original_command_name}")
                        # If still missing, determine command_name from message_type and command_type
                        elif original_command_name == None or original_command_name == '':
                            # Determine command_name with specific handling for each case
                            message_type_lower = original_message_type.lower() if original_message_type else ''
                            command_type_lower = original_command_type.lower() if original_command_type else ''

                            # Precipitation message detection - highest priority
                            if 'precipitation' in message_type_lower or 'precip' in message_type_lower or 'precipitation' in command_type_lower or 'precip' in command_type_lower:
                                original_command_name = 'DISPLAY_PRECIPITATION_DATA'
                                logger.info(f"[BC] Setting precipitation command_name: {original_command_name}")

                            # VIL message detection - second priority
                            elif 'vil' in message_type_lower or 'vertically' in message_type_lower or 'vil' in command_type_lower:
                                original_command_name = 'DISPLAY_VIL_DATA'
                                logger.info(f"[BC] Setting VIL command_name: {original_command_name}")

                            # Mode change detection - third priority
                            elif 'mode_change_completion' in command_type_lower:
                                original_command_name = 'WEATHER_RADAR_MODE_CHANGE_COMPLETION'
                                logger.info(f"[BC] Setting mode change completion command_name: {original_command_name}")
                            elif 'mode_change' in command_type_lower or 'mode' in command_type_lower:
                                original_command_name = 'WEATHER_RADAR_MODE_CHANGE'
                                logger.info(f"[BC] Setting mode change command_name: {original_command_name}")

                            # No special case detected - use a specific default based on the data itself
                            else:
                                # Extract command name from metadata if possible
                                if isinstance(metadata, dict) and metadata.get('command_name'):
                                    original_command_name = metadata['command_name']
                                    logger.info(f"[BC] Extracted command_name from metadata: {original_command_name}")
                                else:
                                    # Default command name as last resort
                                    if system_type:
                                        original_command_name = f"{system_type.upper()}_DATA"
                                    else:
                                        original_command_name = 'WEATHER_RADAR_DATA'
                                    logger.warning(f"[BC] Setting default command_name: {original_command_name}")

                        # Create a properly formatted message for the unified router
                        # For completion messages, ensure the destination is set correctly
                        destination = None
                        if isinstance(metadata, dict):
                            destination = metadata.get('destination')

                        # Default to display_system for completion messages
                        if not destination and original_command_type == 'mode_change_completion':
                            destination = 'display_system'
                            logger.info(f"[BC] Setting destination to display_system for mode_change_completion message")
                        elif not destination:
                            destination = 'display_system'  # Default fallback

                        # Check if this is precipitation data that needs translation
                        is_precipitation_data = (
                            'precipitation' in str(original_message_type).lower() or
                            'precip' in str(original_command_type).lower() or
                            original_command_name == 'DISPLAY_PRECIPITATION_DATA' or
                            'WEA THER_RADAR_PRECIPITATION_DATA' in str(original_command_name)
                        )

                        # Enhanced metadata construction with better field preservation
                        combined_metadata = {
                            'system_type': system_type,
                            'rt_address': rt_address,
                            'subaddress': subaddress_int,
                            'status_word': status_word,
                            'status_frame': status_word_frame,
                            'original_request_id': request_id,  # Preserve original request_id
                            'source': 'bus_controller',
                            'source_system': system_type,  # Add source_system for consistency
                            'timestamp': timestamp,
                            'message_type': original_message_type,
                            'command_type': original_command_type,
                            'command_name': original_command_name,  # Preserve command_name
                            'destination': destination,  # Add destination field to metadata
                            'radar_type': radar_type      # Add radar_type for completeness
                        }

                        # Create message with explicit preservation of critical fields
                        unified_message = {
                            'command_word': status_word_frame,
                            'status_word': status_word,
                            'timestamp': timestamp,
                            'request_id': request_id or ack_request_id,  # Use original request_id when available
                            'rt_address': rt_address,  # This is the source RT address
                            'sub_address': subaddress_int,  # Add sub_address as a top-level field
                            'radar_type': radar_type,  # Now properly set from destination or subaddress
                            'message_type': original_message_type,
                            'command_type': original_command_type,
                            'command_name': original_command_name,  # Set command_name with our enhanced logic
                            'destination': destination,  # Explicitly set destination
                            'source_rt_address': rt_address,  # Add source_rt_address to clarify this is the source
                            'source_system': system_type  # Add source_system field which is important for routing
                        }

                        # First check for block transfer flags
                        is_transfer_init = False
                        is_transfer_data = False
                        is_transfer_complete = False

                        # Check both frame and metadata for all three transfer flags
                        if isinstance(frame, dict):
                            is_transfer_init = frame.get('is_transfer_init', False) or (metadata and metadata.get('is_transfer_init', False))
                            is_transfer_data = frame.get('is_transfer_data', False) or (metadata and metadata.get('is_transfer_data', False))
                            is_transfer_complete = frame.get('is_transfer_complete', False) or (metadata and metadata.get('is_transfer_complete', False))

                        # Handle block transfer from RT
                        if is_transfer_init or is_transfer_data or is_transfer_complete:
                            logger.info(f"[BC] Handling block transfer from RT: init={is_transfer_init}, data={is_transfer_data}, complete={is_transfer_complete}")

                            # Get the block transfer manager
                            from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
                            transfer_manager = get_block_transfer_manager()

                            if is_transfer_init:
                                # Handle initialization of block transfer from RT
                                logger.info(f"[BC] Processing block transfer initialization from RT for request_id: {request_id}")

                                # Clear any existing transfer data for this request_id
                                transfer_manager.clear_transfer(request_id)

                                # Extract total sequences and other metadata if available
                                total_sequences = frame.get('total_sequences', 1)
                                if isinstance(metadata, dict):
                                    total_sequences = metadata.get('total_sequences', total_sequences)

                                logger.info(f"[BC] Block transfer initialization from RT: request_id={request_id}, total_sequences={total_sequences}")

                                # Return early - we'll handle the data when it arrives
                                return True

                            elif is_transfer_data:
                                # Extract required block transfer parameters
                                sequence_number = frame.get('sequence_number') or metadata.get('sequence_number', 1)
                                total_sequences = frame.get('total_sequences') or metadata.get('total_sequences', 1)
                                is_final = frame.get('is_final', False) or metadata.get('is_final', False)

                                # Extract data (ensure compatibility with RT's format)
                                data_array = frame.get('data', [])

                                # Register this block
                                logger.info(f"[BC] Registering block {sequence_number}/{total_sequences} for request_id: {request_id}")
                                transfer_complete = transfer_manager.register_block(
                                    request_id,
                                    sequence_number,
                                    total_sequences,
                                    is_final,
                                    data_array
                                )

                                # Always return early for in-progress transfers
                                # This prevents any routing of partial data and ensures only complete transfers are processed
                                if not transfer_complete:
                                    # For in-progress transfers, acknowledge receipt but don't route
                                    logger.info(f"[BC] Block transfer in progress from RT for request_id: {request_id}")

                                    # Get transfer status for logging - safely access status fields with defaults
                                    status = transfer_manager.get_transfer_status(request_id)

                                    # Safely log transfer status with null-safe access
                                    received_blocks = status.get('received_blocks', 0)
                                    total_blocks = status.get('total_blocks', 0)
                                    percent_complete = status.get('percent_complete', 0.0)

                                    logger.info(f"[BC] Transfer status: {received_blocks}/{total_blocks} blocks received ({percent_complete:.1f}% complete)")

                                        # Return early - we'll handle the complete data when the final block arrives or transfer is complete
                                    return True
                                else:
                                    # If we got here, the transfer is complete - process the full data
                                    assembled_data = transfer_manager.get_assembled_data(request_id)

                                    if assembled_data and len(assembled_data) > 0:
                                        logger.info(f"[BC] Processing complete block transfer from RT with {len(assembled_data)} data points")
                                        # Use the assembled data in place of the original data
                                        unified_message['data'] = assembled_data
                                        # Add block transfer info to metadata
                                        combined_metadata['block_transfer_complete'] = True
                                        combined_metadata['binary_data_length'] = len(assembled_data)
                                        logger.info(f"[BC] Successfully retrieved and assembled complete block transfer data")
                                    else:
                                        logger.error(f"[BC] Failed to get assembled data for block transfer from RT despite transfer being complete")
                                        # Use whatever data we have in frame
                                        unified_message['data'] = frame.get('data', [data_int])
                            elif is_transfer_complete:
                                logger.info(f"[BC] Block transfer complete message received for request_id: {request_id}")

                                # Process final data if available
                                if transfer_manager.is_transfer_complete(request_id):
                                    assembled_data = transfer_manager.get_assembled_data(request_id)
                                    if assembled_data:
                                        unified_message['data'] = assembled_data
                                        combined_metadata['block_transfer_complete'] = True
                                        combined_metadata['binary_data_length'] = len(assembled_data)
                                        logger.info(f"[BC] Successfully retrieved assembled data for completed transfer")
                                else:
                                    logger.warning(f"[BC] Received transfer complete but transfer is not complete in manager")

                        # Apply translation for precipitation data if not handled by block transfer
                        elif is_precipitation_data:
                            # Check if this is part of a block transfer
                            is_transfer_data = False
                            if isinstance(metadata, dict):
                                is_transfer_data = metadata.get('is_transfer_data', False)
                                sequence_number = metadata.get('sequence_number', 0)
                                total_sequences = metadata.get('total_sequences', 0)
                                is_final = metadata.get('is_final', False)

                            if is_transfer_data:
                                logger.info(f"[BC] Detected precipitation block transfer message: seq={sequence_number}/{total_sequences}, final={is_final}")

                                # Get the block transfer manager
                                from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
                                transfer_manager = get_block_transfer_manager()

                                # Register this block
                                transfer_complete = transfer_manager.register_block(
                                    request_id,
                                    sequence_number,
                                    total_sequences,
                                    is_final,
                                    frame.get('data', [])
                                )

                                # Always return early for in-progress transfers
                                # This prevents any routing of partial data and ensures only complete transfers are processed
                                if not transfer_complete:
                                    # For in-progress transfers, acknowledge receipt but don't route
                                    logger.info(f"[BC] Block transfer in progress from RT for request_id: {request_id}")

                                    # Get transfer status for logging
                                    status = transfer_manager.get_transfer_status(request_id)
                                    logger.info(f"[BC] Transfer status: {status['received_blocks']}/{status['total_blocks']} blocks received ({status['percent_complete']:.1f}% complete)")

                                    # Return early - we'll handle the complete data when the final block arrives or transfer is complete
                                    return True
                                elif transfer_complete:
                                    # If we got here, the transfer is complete - process the full data
                                    # Get the complete assembled data
                                    assembled_data = transfer_manager.get_assembled_data(request_id)

                                    if assembled_data and len(assembled_data) > 0:
                                        logger.info(f"[BC] Processing complete precipitation block transfer with {len(assembled_data)} data points")

                                        # The first word should be the count of objects
                                        if len(assembled_data) > 1:
                                            object_count = assembled_data[0]
                                            logger.info(f"[BC] Block transfer contains {object_count} precipitation objects")

                                            # Replace the single data point with the complete data array
                                            unified_message['data'] = assembled_data

                                            # Add block transfer info to metadata
                                            combined_metadata['block_transfer_complete'] = True
                                            combined_metadata['precipitation_objects'] = object_count
                                            combined_metadata['binary_data_length'] = len(assembled_data)
                                            combined_metadata['binary_translated'] = False  # Don't translate here, let precipitation handler do it

                                            logger.info(f"[BC] Routed complete precipitation block transfer data")
                                        else:
                                            logger.error(f"[BC] Invalid assembled data: {assembled_data}")
                                            # Fall back to single data point translation
                                            translated_data = self._translate_precipitation_binary_data(data_int)
                                            unified_message['data'] = translated_data
                                            combined_metadata['binary_translated'] = True
                                            combined_metadata['binary_source_value'] = data_int
                                    else:
                                        logger.error(f"[BC] Failed to get assembled data for block transfer")
                                        # Fall back to single data point translation
                                        translated_data = self._translate_precipitation_binary_data(data_int)
                                        unified_message['data'] = translated_data
                                        combined_metadata['binary_translated'] = True
                                        combined_metadata['binary_source_value'] = data_int
                                else:
                                    # If we got here, transfer_complete was not caught by either true/false check
                                    # however by other checks we must be a trasnfer that is not compelte yet
                                    # so we will only acknowledge receipt and then return early
                                    # For in-progress transfers, acknowledge receipt but don't route
                                    logger.info(f"[BC] Block transfer in progress for request ID: {request_id}")

                                    # Get transfer status for logging
                                    status = transfer_manager.get_transfer_status(request_id)
                                    logger.info(f"[BC] Transfer status: {status['received_blocks']}/{status['total_blocks']} blocks received ({status['percent_complete']:.1f}% complete)")

                                    # Return early - we'll handle the complete data when the final block arrives
                                    # This prevents partial data from being routed
                                    return True
                            # Check if this is a completion message which shouldn't be translated
                            elif 'completion' in original_command_type.lower() if original_command_type else False:
                                # Check if this "completion" message actually has precipitation data
                                # If it has data, it should be treated as a data message even if labeled as completion
                                if 'data' in frame and isinstance(frame['data'], list) and len(frame['data']) > 0:
                                    logger.info(f"[BC] Detected precipitation message with data despite 'completion' in command type")
                                    # Override the command type to ensure it's properly handled
                                    original_command_type = 'precipitation_data'
                                    unified_message['command_type'] = 'precipitation_data'
                                    unified_message['data'] = frame['data']
                                    # Don't mark as completion message
                                    combined_metadata['precipitation_data'] = True
                                    combined_metadata['binary_translated'] = False
                                    logger.info(f"[BC] Treating as precipitation_data message because actual data is present")
                                else:
                                    # For true completion messages with no data, don't decode as precipitation data
                                    logger.info(f"[BC] Detected true precipitation completion message - not translating status word")
                                    # Create a completion indicator instead of translating the status word
                                    unified_message['data'] = {'completion_message': True, 'status': 'success'}
                                    # Set metadata flags
                                    combined_metadata['precipitation_completion'] = True
                                    combined_metadata['binary_translated'] = False
                                    logger.info(f"[BC] Using completion indicator instead of translating status word")
                            elif isinstance(data_int, int):
                                # Not a block transfer, process single data point as before
                                logger.info(f"[BC] Detected precipitation binary data: {data_int}")
                                translated_data = self._translate_precipitation_binary_data(data_int)
                                unified_message['data'] = translated_data
                                combined_metadata['binary_translated'] = True
                                combined_metadata['binary_source_value'] = data_int
                                logger.info(f"[BC] Translated precipitation binary data before routing")
                        else:
                            # Use the original binary data for other message types
                            unified_message['data'] = [data_int]

                        # Log the important fields for verification
                        logger.info(f"[BC] Created unified_message with critical fields:")
                        logger.info(f"[BC]   - request_id: {unified_message['request_id']}")
                        logger.info(f"[BC]   - command_name: {unified_message['command_name']}")
                        logger.info(f"[BC]   - message_type: {unified_message['message_type']}")
                        logger.info(f"[BC]   - command_type: {unified_message['command_type']}")

                        # Special handling for precipitation messages
                        if original_command_name == 'DISPLAY_PRECIPITATION_DATA' or 'precipitation' in original_message_type.lower() or 'precip' in original_command_type.lower():
                            combined_metadata['precipitation_message'] = True
                            combined_metadata['precip_data_available'] = True
                            # Ensure the command_name is consistent in both places
                            original_command_name = 'DISPLAY_PRECIPITATION_DATA'
                            unified_message['command_name'] = original_command_name
                            combined_metadata['command_name'] = original_command_name

                            # Data-aware message classification that properly handles precipitation data
                            # First determine if this message actually contains precipitation data (not just a completion marker)
                            has_actual_data = False

                            if 'data' in unified_message:
                                data_content = unified_message['data']
                                # Check for list data - definitely precipitation data objects
                                if isinstance(data_content, list) and len(data_content) > 0:
                                    has_actual_data = True
                                    logger.info(f"[BC] Found {len(data_content)} precipitation data objects")
                                # Check for translated precipitation data objects
                                elif isinstance(data_content, dict) and not data_content.get('completion_message'):
                                    if 'position' in data_content or 'type' in data_content or 'rate' in data_content:
                                        has_actual_data = True
                                        logger.info(f"[BC] Found precipitation data object: {data_content.get('type', 'unknown')} at {data_content.get('position', 'unknown')}")
                                # Check for data in frame
                                elif isinstance(frame, dict) and 'data' in frame:
                                    frame_data = frame['data']
                                    if isinstance(frame_data, list) and len(frame_data) > 0:
                                        has_actual_data = True
                                        logger.info(f"[BC] Found {len(frame_data)} precipitation data objects in frame")

                                # Adjust command_type based on actual data presence (not just based on name)
                                if has_actual_data:
                                    logger.info(f"[BC] DATA-AWARE CLASSIFICATION: Message contains actual precipitation data")
                                    # Force correct command_type regardless of what it was
                                    if 'completion' in str(unified_message.get('command_type', '')).lower():
                                        logger.info(f"[BC] Correcting command_type from '{unified_message.get('command_type')}' to 'precipitation_data' because actual data is present")
                                    unified_message['command_type'] = 'precipitation_data'
                                    combined_metadata['command_type'] = 'precipitation_data'
                                else:
                                    # Only mark as completion if it's explicitly a completion message with no data
                                    if isinstance(unified_message.get('data'), dict) and unified_message['data'].get('completion_message'):
                                        logger.info(f"[BC] Verified completion message with no data")
                                        # Make sure command_type is consistent
                                        unified_message['command_type'] = 'precipitation_completion'
                                        combined_metadata['command_type'] = 'precipitation_completion'

                                # Also check and update metadata's nested command_type since that's where the issue is happening
                                if 'metadata' in unified_message and isinstance(unified_message['metadata'], dict):
                                    if 'command_type' in unified_message['metadata']:
                                        logger.info(f"[BC] CRITICAL: Also correcting metadata.command_type from '{unified_message['metadata']['command_type']}' to 'precipitation_data'")
                                        unified_message['metadata']['command_type'] = 'precipitation_data'

                            logger.info(f"[BC] Enhanced metadata for precipitation message")
                            logger.info(f"[BC] CRITICAL PRESERVATION: Precipitation message with command_name={original_command_name}, request_id={unified_message['request_id']}")

                        # Special handling for VIL messages
                        elif original_command_name == 'DISPLAY_VIL_DATA' or 'vil' in original_message_type.lower() or 'vil' in original_command_type.lower():
                            combined_metadata['vil_message'] = True
                            combined_metadata['vil_data_available'] = True
                            # Ensure the command_name is consistent in both places
                            original_command_name = 'DISPLAY_VIL_DATA'
                            unified_message['command_name'] = original_command_name
                            combined_metadata['command_name'] = original_command_name
                            logger.info(f"[BC] Enhanced metadata for VIL message")
                            logger.info(f"[BC] CRITICAL PRESERVATION: VIL message with command_name={original_command_name}, request_id={unified_message['request_id']}")

                        # Special handling for mode change messages
                        elif 'mode_change' in original_command_type.lower() or 'mode' in command_type_lower or 'mode' in original_message_type.lower():
                            logger.info(f"[BC] Enhanced handling for mode change message: mode={mode}, mode_value={mode_value}")
                            # Ensure mode fields are properly set in metadata and unified message
                            if mode:
                                combined_metadata['mode'] = mode
                                unified_message['mode'] = mode
                            if mode_value:
                                combined_metadata['mode_value'] = mode_value
                                unified_message['mode_value'] = mode_value

                        # Add user-provided metadata if available
                        if metadata:
                            # Be careful not to overwrite our critical fields with empty values
                            for key, value in metadata.items():
                                # Only update if the key doesn't exist or the new value is not empty
                                if key not in combined_metadata or (value is not None and value != ''):
                                    combined_metadata[key] = value

                        # Add the combined metadata to the unified message
                        unified_message['metadata'] = combined_metadata

                        # Double check that command_name and request_id are set in both places
                        # This ensures redundancy and resilience
                        if original_command_name:
                            unified_message['command_name'] = original_command_name
                            unified_message['metadata']['command_name'] = original_command_name

                        if request_id:
                            unified_message['request_id'] = request_id
                            unified_message['metadata']['request_id'] = request_id

                        logger.info(f"[BC] Routing message through unified router: {unified_message}")
                        logger.info(f"[BC] Message flow trace: BC_Listener -> Bus_Controller -> Unified Router")

                        # Route through the unified router
                        route_result = self.route_message(unified_message)
                        logger.info(f"[BC] Routed status word through unified router: result={route_result}")

                        # Log mode change completion message
                        if command_type == 'mode_change_completion':
                            logger.info(f"[BC] Mode change completion message routed to unified router")
                            if metadata:
                                old_mode = metadata.get('old_mode')
                                new_mode = metadata.get('new_mode')
                                if old_mode and new_mode:
                                    logger.info(f"[BC] Mode change: {old_mode} -> {new_mode}")

                        # Remove processed request
                        if request_id in self.pending_requests:
                            del self.pending_requests[request_id]
                            logger.info(f"[BC] Processed status word for RT {rt_address}, request {request_id}")

                        break  # Success

                    except Exception as e:
                        last_error = e
                        if attempt < max_retries - 1:
                            logger.warning(f"[BC] Storage attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(f"[BC] All storage attempts failed: {e}")
                            logger.error(traceback.format_exc())
                            raise last_error
            else:
                logger.warning(f"[BC] Could not determine radar type for RT address {rt_address}")

        except Exception as e:
            logger.error(f"Error processing status word: {e}")
            logger.error(traceback.format_exc())

    def _process_command_data_word(self, frame):
        """Process command or data word frame using the unified router."""
        try:
            system_name, command_word, data = self.bcd.route_inc_frame(frame)
            if system_name and command_word:
                # Get request ID, timestamp, command_type, message_type, command_name, and all metadata from frame
                request_id = frame.get('request_id', None)
                timestamp = frame.get('timestamp', None)
                command_type = frame.get('command_type', None)
                message_type = frame.get('message_type', None)
                command_name = frame.get('command_name', None)
                metadata = frame.get('metadata', {})

                # Check for precipitation-related commands
                if 'precipitation' in command_word.lower() or 'precip' in command_word.lower():
                    command_name = 'DISPLAY_PRECIPITATION_DATA'
                    logger.info(f"[BC] Command word processor detected precipitation command: {command_word}")
                # Check for VIL-related commands
                elif 'vil' in command_word.lower():
                    command_name = 'DISPLAY_VIL_DATA'
                    logger.info(f"[BC] Command word processor detected VIL command: {command_word}")
                # Check for mode-related commands
                elif 'mode' in command_word.lower():
                    command_name = f"{system_name.upper()}_MODE_CHANGE"
                    logger.info(f"[BC] Command word processor detected mode command: {command_word}")
                # Default case
                else:
                    command_name = f"{system_name.upper()}_{command_word.upper()}"
                    logger.info(f"[BC] Generated command_name: {command_name}")

                # Create enhanced metadata with critical fields
                message_metadata = {
                    'system_type': system_name,
                    'command_word': command_word,
                    'source': 'bus_controller',
                    'timestamp': time.time(),
                    'command_name': command_name,  # Include command_name in metadata
                    'request_id': request_id,      # Include request_id in metadata
                    'message_type': message_type,  # Include message_type in metadata
                    'command_type': command_word,  # Include command_type in metadata
                    'source_system': system_name   # Include source_system for consistency
                }

                # Add special flags for precipitation and VIL
                if command_name == 'DISPLAY_PRECIPITATION_DATA':
                    message_metadata['precipitation_message'] = True
                    message_metadata['precip_data_available'] = True
                elif command_name == 'DISPLAY_VIL_DATA':
                    message_metadata['vil_message'] = True
                    message_metadata['vil_data_available'] = True
                # Add mode information for mode change commands
                elif 'mode' in command_word.lower():
                    # Extract mode data if possible
                    try:
                        if isinstance(data, str) and len(data) >= 16:
                            # For binary strings, convert to integer
                            mode_value = int(data, 2)
                        elif isinstance(data, list) and len(data) > 0:
                            # For lists, use the first value
                            mode_value = data[0]
                        else:
                            mode_value = None

                        if mode_value is not None:
                            message_metadata['mode_value'] = mode_value
                            logger.info(f"[BC] Extracted mode_value: {mode_value}")
                    except Exception as mode_e:
                        logger.warning(f"[BC] Could not extract mode value: {mode_e}")

                # Create a properly formatted message for the unified router with enhanced fields
                unified_message = {
                    'command_word': command_word,
                    'data': data if isinstance(data, list) else [data],
                    'timestamp': time.time(),
                    'request_id': request_id,
                    'rt_address': self._get_rt_address(system_name) if hasattr(self, '_get_rt_address') else None,
                    'sub_address': self._get_subaddress(system_name, command_word) if hasattr(self, '_get_subaddress') else None,
                    'message_type': message_type,
                    'command_type': command_word,
                    'command_name': command_name,  # Include command_name at top level
                    'metadata': message_metadata
                }

                # Log critical fields for verification
                logger.info(f"[BC] Created command word unified_message with:")
                logger.info(f"[BC]   - request_id: {unified_message['request_id']}")
                logger.info(f"[BC]   - command_name: {unified_message['command_name']}")
                logger.info(f"[BC]   - message_type: {unified_message['message_type']}")

                # Route through the unified router with enhanced logging
                logger.info(f"[BC] Routing command word message through unified router...")
                route_result = self.route_message(unified_message)

                if route_result:
                    logger.info(f"[BC] Successfully routed command/data word through unified router:")
                    logger.info(f"[BC]   - system: {system_name}")
                    logger.info(f"[BC]   - command: {command_word}")
                    logger.info(f"[BC]   - command_name: {command_name}")
                    logger.info(f"[BC]   - request_id: {request_id}")
                else:
                    logger.error(f"[BC] Failed to route command/data word:")
                    logger.error(f"[BC]   - system: {system_name}")
                    logger.error(f"[BC]   - command: {command_word}")
                    logger.error(f"[BC]   - command_name: {command_name}")
                    logger.error(f"[BC]   - request_id: {request_id}")
                    raise Exception(f"Failed to route command/data word: system={system_name}, command={command_word}")
            else:
                logger.warning(f"[BC] Invalid frame: system_name={system_name}, command_word={command_word}")
        except Exception as e:
            logger.error(f"Error processing command/data word: {e}")
            logger.error(traceback.format_exc())

    def start_listener(self):
        """Start BC listener."""
        logger.info("Starting BC listening...")
        try:
            listener = BC_Listener()
            self._listener = listener
            thread_manager.add_thread("BC Listening", target=listener.start_listening)
            thread_manager.start_thread("BC Listening")
            self.listening = True
            logger.info(f"BC listener started. Listening: {self.listening}")

            # Create event loop for async processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            while self.listening and not self.stop_event.is_set():
                if listener.data_received:
                    try:
                        # Process frame but don't remove it yet
                        loop.run_until_complete(self.process_frame(listener.data_received[0]))
                        # Only remove after processing
                        listener.data_received.pop(0)
                    except Exception as e:
                        logger.error(f"Error processing received data: {e}")
                time.sleep(0.1)  # Prevent tight loop

        except Exception as e:
            logger.error(f"Error in start_listener: {e}")
            logger.error(traceback.format_exc())
            self.stop_listener()

    def stop_listener(self):
        """Stop BC listener."""
        logger.info("Stopping BC listener...")
        self.stop_event.set()
        self.listening = False
        # This only stops the "BC Listener" thread (the while loop right
        # above in start_listener()). It does NOT stop the separate
        # "BC Listening" thread, which runs the BC_Listener socket object's
        # own start_listening() -- that object has its own independent
        # self.running flag, set via BC_Listener.stop_listening(), and
        # nothing was ever calling it. Confirmed live: system_manager.py's
        # stop_system() never called Bus_Controller.stop_listener() at all
        # (this method had no callers anywhere in the codebase), so neither
        # thread ever received a stop signal -- "BC Listener" would run
        # forever, and even once that's fixed, "BC Listening" would still
        # hang separately without this. Both are now stopped together here.
        if self._listener is not None:
            self._listener.stop_listening()
        logger.info("BC listener stopped")

# Global instance of ThreadManager
thread_manager = ThreadManager()

def get_Bus_Controller():
    """Get global Bus Controller instance."""
    return Bus_Controller()
