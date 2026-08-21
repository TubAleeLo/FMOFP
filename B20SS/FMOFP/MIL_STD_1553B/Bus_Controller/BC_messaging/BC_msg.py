"""
Bus Controller Message Handling

Handles construction and deconstruction of MIL-STD-1553B messages.
"""

import json
import traceback
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_encode_decode.BC_words_encoder import BCWordsEncoder
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_encode_decode.BC_words_decoder import BC_decoders
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class BC_construct:
    # Sync patterns according to MIL-STD-1553B
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern (same as command)

    def __init__(self):
        self.bce = BCWordsEncoder()

    def calculate_parity(self, word):
        """
        Calculate odd parity bit for a binary word according to MIL-STD-1553B.
        Returns '1' or '0' to make the total number of 1s odd.
        """
        ones_count = word.count('1')
        return '1' if ones_count % 2 == 0 else '0'

    def construct_command_word(self, RT_address, t_or_r, sub_add_or_mode_code, data_word_count):
        """
        Construct a command word according to MIL-STD-1553B specification.
        Command word format:
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - T/R bit (1 bit)
        - Subaddress/Mode (5 bits)
        - Word Count/Mode Code (5 bits)
        - Parity (1 bit)
        """
        logger.debug('Start constructing command word with RT_address: %s, t_or_r: %s, sub_add_or_mode_code: %s, data_word_count: %s', RT_address, t_or_r, sub_add_or_mode_code, data_word_count)

        try:
            # Convert inputs to binary strings and validate
            RT_address_bin = format(int(RT_address), '05b')
            t_or_r_bin = '0' if t_or_r == 0 else '1'
            sub_add_bin = format(int(sub_add_or_mode_code), '05b')
            data_count_bin = format(int(data_word_count), '05b')

            # Check lengths
            if not (len(RT_address_bin) == 5 and len(t_or_r_bin) == 1 and
                    len(sub_add_bin) == 5 and len(data_count_bin) == 5):
                logger.error('Invalid bit lengths in command word components')
                return None

            # Construct 16-bit word without sync and parity
            word_16bit = RT_address_bin + t_or_r_bin + sub_add_bin + data_count_bin

            # Add sync pattern
            word_with_sync = self.COMMAND_SYNC + word_16bit

            # Add parity bit
            parity = self.calculate_parity(word_with_sync)
            command_word = word_with_sync + parity

            # Validate final length
            if len(command_word) != 20:
                logger.error(f"Invalid command word length: {len(command_word)} bits")
                return None

            logger.debug('Finished constructing command word: %s', command_word)
            return command_word

        except Exception as e:
            logger.error(f"Error constructing command word: {str(e)}")
            return None

    def construct_data_word(self, data):
        """
        Construct a data word according to MIL-STD-1553B specification.
        Data word format:
        - Sync (3 bits): 001
        - Data (16 bits)
        - Parity (1 bit)
        """
        logger.debug('Start constructing data word with data: %s', data)

        try:
            # Convert data to 16-bit binary
            if isinstance(data, int):
                # Integer data - format as 16-bit binary
                if data < 0 or data > 65535:  # 2^16 - 1
                    logger.error(f'Data value {data} out of range for 16-bit word')
                    return None
                data_bin = format(data, '016b')
            elif isinstance(data, str):
                # String data - check if it's already binary
                if all(bit in '01' for bit in data):
                    # Binary string - validate length
                    if len(data) != 16:
                        logger.error(f'Binary data must be exactly 16 bits, got {len(data)} bits')
                        return None
                    data_bin = data
                else:
                    # Not a binary string - try to convert to int
                    try:
                        int_val = int(data)
                        if int_val < 0 or int_val > 65535:
                            logger.error(f'Data value {int_val} out of range for 16-bit word')
                            return None
                        data_bin = format(int_val, '016b')
                    except ValueError:
                        logger.error(f'Cannot convert data "{data}" to 16-bit binary')
                        return None
            else:
                logger.error(f'Unsupported data type: {type(data)}')
                return None

            # Validate data length
            if len(data_bin) != 16:
                logger.error(f'Invalid data word length: {len(data_bin)} bits')
                return None

            # Add sync pattern
            word_with_sync = self.DATA_SYNC + data_bin

            # Calculate parity bit (odd parity)
            ones_count = word_with_sync.count('1')
            parity = '1' if ones_count % 2 == 0 else '0'

            # Add parity bit
            data_word = word_with_sync + parity

            # Validate final length
            if len(data_word) != 20:
                logger.error(f"Invalid data word length: {len(data_word)} bits")
                return None

            # Log parity calculation for debugging
            logger.debug(f"Data word parity calculation: ones_count={ones_count}, parity={parity}")
            logger.debug('Finished constructing data word: {data_word}')
            return data_word

        except Exception as e:
            logger.error(f"Error constructing data word: {str(e)}")
            return None

    def construct_communication_frame(self, RT_address, t_or_r, sub_add_or_mode_code, data_word_count, message, metadata=None):
        """
        Construct a complete communication frame according to MIL-STD-1553B specification.
        Frame format:
        - Command word (20 bits)
        - Metadata words (if metadata is provided)
        - Data words (20 bits each, if any)

        Args:
            RT_address: Remote Terminal address
            t_or_r: Transmit/Receive flag
            sub_add_or_mode_code: Subaddress or mode code
            data_word_count: Number of data words
            message: Data to send
            metadata: Optional metadata dictionary to encode into data words
        """
        logger.info('Start constructing communication frame with RT_address: %s, t_or_r: %s, sub_add_or_mode_code: %s, data_word_count: %s, message: %s',
                    RT_address, t_or_r, sub_add_or_mode_code, data_word_count, message)

        try:
            # Convert data_word_count to int if it's a binary string
            if isinstance(data_word_count, str):
                data_word_count = int(data_word_count, 2)

            # For empty messages with no metadata, always use data_word_count=0
            if (message is None or message == '' or (isinstance(message, list) and not message)) and not metadata:
                command_word = self.construct_command_word(RT_address, t_or_r, sub_add_or_mode_code, 0)
                if command_word:
                    logger.info(f'Constructed command frame for empty message: {command_word}')
                    return [command_word]
                else:
                    logger.error('Failed to construct command word')
                    return []

            # Convert message to list if it's not already
            message_list = message if isinstance(message, list) else ([message] if message else [])

            # Encode metadata if provided
            metadata_words = []
            if metadata:
                try:
                    # Import metadata codec
                    from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec

                    # Encode metadata into data words
                    metadata_words = MetadataCodec.encode_metadata(metadata)
                    logger.info(f'Encoded metadata into {len(metadata_words)} data words')
                except Exception as e:
                    logger.error(f'Error encoding metadata: {e}')
                    # Continue without metadata if encoding fails

            # Combine metadata words and message data words
            all_data_words = metadata_words + message_list

            # Update data word count to include metadata
            actual_data_word_count = len(all_data_words)

            # Validate against MIL-STD-1553B limit of 32 data words
            if actual_data_word_count > 32:
                logger.warning(f'Data word count exceeds MIL-STD-1553B limit: {actual_data_word_count} > 32')
                # BC_msg builds a *single* 1553B message frame capped at 32
                # words.  Oversized payloads from the FMS arrive here already
                # split into ≤32-word blocks by FMSMessenger._send_as_block_transfer,
                # so this path should only be reached for naturally small messages.
                # Truncate to 32 words as the MIL-STD-1553B frame limit requires.
                raise Exception("[BC_MSG] Data word count exceeds MIL-STD-1553B limit")

            # Construct command word with actual data word count
            command_word = self.construct_command_word(RT_address, t_or_r, sub_add_or_mode_code, actual_data_word_count)
            if not command_word:
                logger.error('Failed to construct command word')
                return []

            # Construct data words
            data_words = []
            for data in all_data_words:
                data_word = self.construct_data_word(data)
                if not data_word:
                    logger.error(f'Failed to construct data word for: {data}')
                    return []
                data_words.append(data_word)

            # Combine command word and data words
            frame = [command_word] + data_words

            logger.info('Finished constructing communication frame: command word + %d data words', len(data_words))
            return frame

        except Exception as e:
            logger.error(f"Error constructing communication frame: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def validate_frame(self, frame):
        """
        Validate a complete communication frame.

        Args:
            frame: List of 20-bit words

        Returns:
            bool: True if frame is valid, False otherwise
        """
        try:
            if not frame:
                return False

            # Check each word is 20 bits
            for word in frame:
                if len(word) != 20:
                    logger.error(f"Invalid word length: {len(word)} bits")
                    return False

            # Validate command word (first word)
            if not frame[0].startswith(self.COMMAND_SYNC):
                logger.error("Invalid command word sync bits")
                return False

            # Validate data words if present
            for word in frame[1:]:
                if not word.startswith(self.DATA_SYNC):
                    logger.error("Invalid data word sync bits")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating frame: {str(e)}")
            return False

    def validate_status_word(self, status_word):
        """
        Validate a status word according to MIL-STD-1553B specification.

        Args:
            status_word: 20-bit status word string

        Returns:
            bool: True if status word is valid, False otherwise
        """
        try:
            # Clean status word string
            status_word = ''.join(filter(lambda x: x in ['0', '1'], str(status_word)))

            if not status_word or len(status_word) != 20:
                logger.error(f"Invalid status word length: {len(status_word)} bits")
                return False

            # Check sync pattern
            if not status_word.startswith(self.STATUS_SYNC):
                logger.error(f"Invalid status word sync pattern: {status_word[:3]}")
                return False

            # Check parity
            if self.calculate_parity(status_word[:-1]) != status_word[-1]:
                logger.error(f"Invalid status word parity: expected {self.calculate_parity(status_word[:-1])}, got {status_word[-1]}")
                return False

            logger.info(f"Valid status word received: {status_word}")
            return True

        except Exception as e:
            logger.error(f"Error validating status word: {str(e)}")
            return False

class BC_deconstruct:
    # Status word sync pattern according to MIL-STD-1553B
    STATUS_SYNC = "100"

    def __init__(self):
        self.bcd = BC_decoders()

    def _create_default_status_word(self, status_frame):
        """
        Create a default status word from available metadata when direct extraction fails.

        Args:
            status_frame: The original status frame dictionary

        Returns:
            dict: A minimal status word dictionary with available information
        """
        # Create a basic frame with minimal required fields
        default_status = {
            'sync': self.STATUS_SYNC,
            'rt_address': None,
            'parity': 0
        }

        # Try to extract RT address from metadata
        if 'metadata' in status_frame and isinstance(status_frame['metadata'], dict):
            if 'rt_address' in status_frame['metadata']:
                default_status['rt_address'] = status_frame['metadata']['rt_address']
                logger.info(f'[BC_MSG] Extracted RT address from metadata: {default_status["rt_address"]}')

        # Try to get rt_address from top level if not found in metadata
        if default_status['rt_address'] is None and 'rt_address' in status_frame:
            default_status['rt_address'] = status_frame['rt_address']
            logger.info(f'[BC_MSG] Extracted RT address from top level: {default_status["rt_address"]}')

        # Add request_id if available
        if 'request_id' in status_frame:
            default_status['request_id'] = status_frame['request_id']
            logger.info(f'[BC_MSG] Preserved request_id in default status word: {status_frame["request_id"]}')

        logger.info(f'[BC_MSG] Created default status word with RT address: {default_status["rt_address"]}')
        return default_status

    def deconstruct_status_word(self, status_frame, request_id=None):
        """
        Deconstruct a status word according to MIL-STD-1553B specification.
        Status word format:
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - Message Error (1 bit)
        - Instrumentation (1 bit)
        - Service Request (1 bit)
        - Reserved (3 bits)
        - Broadcast Command (1 bit)
        - Busy (1 bit)
        - Subsystem Flag (1 bit)
        - Dynamic Bus Control (1 bit)
        - Terminal Flag (1 bit)
        - Parity (1 bit)
        """
        try:
            # First handle dictionary input (from block transfer protocol)
            if isinstance(status_frame, dict):
                logger.info('[BC_MSG] Received dictionary for status_frame, extracting status_word field')

                # For complex dictionaries with frame arrays (block transfer)
                if 'frames' in status_frame and isinstance(status_frame['frames'], list) and len(status_frame['frames']) > 0:
                    frames = status_frame['frames']
                    logger.info(f'[BC_MSG] Found frames array with {len(frames)} frames')

                    # Look for a valid status word (starts with STATUS_SYNC)
                    valid_status_frame = None

                    # First check the first frame as it's most likely to be the status word
                    if len(frames) > 0 and isinstance(frames[0], str):
                        first_frame = frames[0]
                        # Check if it starts with the status word sync pattern
                        if first_frame.startswith(self.STATUS_SYNC):
                            valid_status_frame = first_frame
                            logger.info(f'[BC_MSG] Found valid status word as first frame: {valid_status_frame}')

                    # If first frame wasn't valid, scan all frames for a valid status word
                    if valid_status_frame is None:
                        for i, frame in enumerate(frames):
                            if isinstance(frame, str) and frame.startswith(self.STATUS_SYNC):
                                valid_status_frame = frame
                                logger.info(f'[BC_MSG] Found valid status word at position {i}: {valid_status_frame}')
                                break

                    # If we found a valid status word frame, use it
                    if valid_status_frame is not None:
                        status_frame = valid_status_frame
                    else:
                        logger.warning(f'[BC_MSG] No valid status word found in frames array of length {len(frames)}')
                        # Create a default status word with available information
                        default_status = self._create_default_status_word(status_frame)
                        return default_status

                # Simple dictionary with status_word field
                elif 'status_word' in status_frame:
                    logger.info(f'[BC_MSG] Extracted status_word from dictionary: {status_frame["status_word"]}')
                    status_frame = status_frame['status_word']
                else:
                    logger.error('[BC_MSG] Could not extract status_word from dictionary')
                    # Create default status word
                    default_status = self._create_default_status_word(status_frame)
                    return default_status

            # Handle potentially concatenated frames in string format
            if isinstance(status_frame, str) and len(status_frame) > 20:
                logger.warning(f'[BC_MSG] Received oversized status_frame: {len(status_frame)} bits')

                # Check if it's a string representation of a dictionary or list
                if (status_frame.startswith('{') and status_frame.endswith('}')) or \
                   (status_frame.startswith('[') and status_frame.endswith(']')):
                    logger.info('[BC_MSG] Detected string representation of complex data structure')
                    try:
                        # Try to parse it using json.loads
                        parsed_data = json.loads(status_frame)

                        # Recursively call this method with the parsed data
                        return self.deconstruct_status_word(parsed_data, request_id)
                    except (ValueError, SyntaxError) as e:
                        logger.error(f'[BC_MSG] Failed to parse string as data structure: {e}')
                        # Continue with normal processing

                # Try to find a valid status word within the concatenated string
                # Look for the sync pattern at the beginning
                if status_frame.startswith(self.STATUS_SYNC):
                    logger.info('[BC_MSG] Using first 20 bits as status word')
                    status_frame = status_frame[:20]
                else:
                    # Scan for sync pattern in the string
                    for i in range(len(status_frame) - 20 + 1):
                        if status_frame[i:i+3] == self.STATUS_SYNC:
                            candidate = status_frame[i:i+20]
                            logger.info(f'[BC_MSG] Found potential status word at position {i}: {candidate}')
                            status_frame = candidate
                            break

            # Strip out any character that is not a 1 or 0
            cleaned_status_frame = ''.join(filter(lambda x: x in ['0', '1'], str(status_frame)))

            if not all(bit in ['0', '1'] for bit in cleaned_status_frame):
                logger.error('Invalid content in status_frame after cleaning: %s', cleaned_status_frame)
                return None

            # Check frame length
            if len(cleaned_status_frame) != 20:
                logger.error('Invalid status_frame length after cleaning: %s', len(cleaned_status_frame))

                # Handle multiple concatenated 20-bit frames (for block transfers that might get concatenated)
                if len(cleaned_status_frame) > 20 and len(cleaned_status_frame) % 20 == 0:
                    logger.warning(f'[BC_MSG] Detected {len(cleaned_status_frame) // 20} concatenated frames, using first frame')
                    cleaned_status_frame = cleaned_status_frame[:20]
                else:
                    # Cannot process this status_frame
                    raise Exception("Invalid status_frame length")

            logger.info('Start deconstructing status word with cleaned_status_frame: %s', cleaned_status_frame)
            status_word = self.bcd.decode_status_word(cleaned_status_frame)

            # Add request_id to status word if provided
            if request_id:
                status_word['request_id'] = request_id

            logger.info('Bus Controller: Finished deconstructing status word. Status word: %s', status_word)
            return status_word
        except Exception as error:
            logger.error('Exception while deconstructing status word: %s', str(error))
            raise

    def deconstruct_data_word(self, data_frame):
        """
        Deconstruct a data word according to MIL-STD-1553B specification.
        Data word format:
        - Sync (3 bits): 001
        - Data (16 bits)
        - Parity (1 bit)
        """
        try:
            logger.debug('Start deconstructing data word with data_frame: %s', data_frame)
            # Ensure the correct argument is passed to decode_data_word
            data_word = self.bcd.decode_data_word(data_frame)
            logger.debug('Finished deconstructing data word. Data word: %s', data_word)
            return data_word
        except Exception as error:
            logger.error('Exception while deconstructing data word: %s', str(error))
            return None

    def route_inc_frame(self, received_frame, request_id=None):
        """Route incoming frame to appropriate handler based on sync bits."""
        try:
            if received_frame[0:3] == "100":  # Status word
                status_word = self.deconstruct_status_word(received_frame, request_id)
                if status_word:
                    # For status words, return radar system and status_word command type
                    return "radar", "status_word", status_word
            elif received_frame[0:3] == "001":  # Data word
                data_word = self.deconstruct_data_word(received_frame)
                if data_word:
                    # For data words, return radar system and data command type
                    return "radar", "data_word", data_word
            else:
                raise Exception("Invalid incoming frame")

            logger.error("Failed to route frame: %s", received_frame)
            return None, None, None

        except Exception as error:
            logger.error('Exception while routing incoming frame: %s', str(error))
            return None, None, None
