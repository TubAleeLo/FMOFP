"""
RT Message Analyzer - Handles RT message processing according to MIL-STD-1553B
"""
import time
import copy
import traceback
from .RT_encode_decode.RT_words_encoder import RTWordsEncoder
from .RT_encode_decode.RT_words_decoder import RTWordsDecoder
from .RT_encode_decode.Handle_mode_code import Mode_code
from ..RT_connect.RT_socket import get_rt_sender
from .RT_transfer_aggregator import get_rt_transfer_aggregator
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class RT_Message_Analyzer:
    # Sync patterns according to MIL-STD-1553B (matching BC_msg.py)
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern (same as command)
    
    # Command type constants
    SHOW_COMMAND = 0x01
    MODE_COMMAND = 0x02
    DATA_COMMAND = 0x03
    
    def _is_precipitation_message(self, metadata):
        """
        Determine if a message is a precipitation data message based on metadata.
        Ported directly from BC_transfer_aggregator for consistency.
        """
        # Check metadata dictionary
        if isinstance(metadata, dict):
            if 'precipitation_message' in metadata and metadata['precipitation_message']:
                logger.info("[RT_MSG] Identified precipitation message via precipitation_message flag")
                return True
            if 'data_type' in metadata and metadata['data_type'] == 'precipitation':
                logger.info("[RT_MSG] Identified precipitation message via data_type=precipitation")
                return True
            if 'message_type' in metadata and isinstance(metadata['message_type'], str) and 'precipitation' in metadata['message_type'].lower():
                logger.info("[RT_MSG] Identified precipitation message via message_type containing 'precipitation'")
                return True
                
        # Check for large frame count (typical for precipitation data)
        if 'frame_count' in metadata and metadata['frame_count'] > 15:
            logger.info(f"[RT_MSG] Message with {metadata['frame_count']} frames likely precipitation data")
            return True
            
        return False
    
    # Subaddress mapping
    SUBADDRESS_MAP = {
        1: 'show',    # 00001: Show commands
        2: 'mode',    # 00010: Mode commands
        3: 'data'     # 00011: Data commands
    }
    
    ## Hexadecimal memory table for mode code
    Mode_code_table = {   
        '00': 'MC0',    '01': 'MC1',    '02': 'MC2',    '03': 'MC3',
        '04': 'MC4',    '05': 'MC5',    '06': 'MC6',    '07': 'MC7',
        '08': 'MC8',    '09': 'MC9',    '0A': 'MC10',   '0B': 'MC11',
        '0C': 'MC12',   '0D': 'MC13',   '0E': 'MC14',   '0F': 'MC15',
        '10': 'MC16',   '11': 'MC17',   '12': 'MC18',   '13': 'MC19',
        '14': 'MC20',   '15': 'MC21',   '16': 'MC22',   '17': 'MC23',
        '18': 'MC24',   '19': 'MC25',   '1A': 'MC26',   '1B': 'MC27',
        '1C': 'MC28',   '1D': 'MC29',   '1E': 'MC30',   '1F': 'MC31'
    }
    
    def __init__(self):
        self.rt_sender = get_rt_sender()
        logger.info("RT_Message_Analyzer initialized")
    
    def route_inc_frame(self, frame):   ##  High -> command word / Low -> data word 
        logger.info(f"RT received frame: {frame}")
        self.rtd = RT_deconstruct()
        self.md = Mode_code()
        self.rt_construct = RT_construct()  # Add RT_construct instance for status word generation
        try:
            # Extract request_id and frames with enhanced metadata handling
            request_id = None
            frame_data = []
            metadata = {}
            
            logger.info("[RT_MSG] Starting frame processing")
            
            # Handle different frame formats
            if isinstance(frame, dict):
                request_id = frame.get('request_id')
                frames_list = frame.get('frames', [])
                if isinstance(frames_list, list):
                    frame_data = frames_list
                else:
                    frame_data = [frames_list]
                
                # Extract metadata directly from frame
                if 'metadata' in frame:
                    metadata = frame['metadata']
                    logger.info(f"[RT_MSG] Found metadata in frame: {metadata}")
                
                # Extract command_name directly from frame or metadata
                command_name = None
                if 'command_name' in frame:
                    command_name = frame['command_name']
                    logger.info(f"[RT_MSG] Found command_name in frame: {command_name}")
                elif metadata and 'command_name' in metadata:
                    command_name = metadata['command_name']
                    logger.info(f"[RT_MSG] Found command_name in metadata: {command_name}")
                
                # Add command_name to metadata if not already there
                if command_name and metadata and 'command_name' not in metadata:
                    metadata['command_name'] = command_name
                    logger.info(f"[RT_MSG] Added command_name to metadata: {command_name}")
                
                # Create metadata dictionary with any other fields
                additional_metadata = {k: v for k, v in frame.items() if k not in ['frames', 'request_id', 'metadata']}
                if additional_metadata:
                    metadata.update(additional_metadata)
                    logger.info(f"[RT_MSG] Added additional metadata from frame: {additional_metadata}")
                
                logger.info(f"[RT_MSG] Extracted request_id from dict: {request_id}, metadata: {metadata}")
                logger.info(f"[RT_MSG] Frame data: {frame_data}")
            elif isinstance(frame, list):
                frame_data = frame
                # Check if we have a request_id in a known position
                if len(frame) > 2 and isinstance(frame[2], str) and len(frame[2]) == 36:
                    request_id = frame[2]
                    frame_data = frame[:2]  # Only take command and data frames
                    logger.info(f"Extracted request_id from list position: {request_id}")
            else:
                # Handle single frame string case
                frame_data = [frame]

            # Ensure frame_data is a list and has at least one frame
            if not frame_data:
                logger.error(f"Invalid frame data format: {frame_data}")
                return None, None

            # Clean frames
            frame_data = [str(f).strip("[]'\"") for f in frame_data]
            logger.info(f"Cleaned frames: {frame_data}")

            # Split into command and data frames with metadata preservation
            commandFrame = frame_data[0]
            dataFrames = frame_data[1:] if len(frame_data) > 1 else []

            command_word = None
            data_words = []
            # Extract command_name directly from the original frame dictionary
            command_name = None
            if isinstance(frame, dict) and 'command_name' in frame:
                command_name = frame['command_name']
                logger.info(f"[RT_MSG] Extracted command_name directly from frame: {command_name}")
            
            # Create response_metadata with command_name explicitly included
            response_metadata = {
                'request_id': request_id,
                'timestamp': time.time(),
                'original_request_id': request_id,  # Preserve original request_id
                **metadata
            }
            
            # Force command_name into response_metadata
            if command_name:
                response_metadata['command_name'] = command_name
                logger.info(f"[RT_MSG] CRITICAL: Added command_name to response_metadata: {command_name}")
            
            logger.info(f"Processing with metadata: {response_metadata}")

            # Process command word with enhanced metadata
            if commandFrame.startswith(self.COMMAND_SYNC):
                logger.info(f"[RT_MSG] Processing command word: {commandFrame}")
                # Decode and verify command word
                command_word = self.rtd.deconstruct_command_word(commandFrame)
                if command_word:
                    logger.info(f"[RT_MSG] Valid command word decoded: {command_word}")
                    logger.info(f"[RT_MSG] RT address in command: {command_word.get('rt_address')}")
                    
                    # Check if data words contain metadata
                    extracted_metadata = {}
                    remaining_data_frames = dataFrames.copy() if dataFrames else []
                    
                    # Try to extract metadata from data words
                    if dataFrames:
                        try:
                            # Import metadata codec
                            from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec
                            
                            # Convert data frames to binary strings if needed
                            binary_data_frames = []
                            for frame in dataFrames:
                                if isinstance(frame, str) and len(frame) == 20 and frame.startswith(self.DATA_SYNC):
                                    # Extract just the data portion (bits 3-18)
                                    data_bits = frame[3:19]
                                    binary_data_frames.append(data_bits)
                                elif isinstance(frame, dict) and 'data' in frame:
                                    data_bits = format(frame['data'], '016b')
                                    binary_data_frames.append(data_bits)
                            
                            # Extract metadata words from binary data frames
                            metadata_words, remaining_words = MetadataCodec.extract_metadata_words(binary_data_frames)
                            
                            if metadata_words:
                                # Decode metadata from metadata words
                                extracted_metadata = MetadataCodec.decode_metadata(metadata_words)
                                logger.info(f"[RT_MSG] Extracted metadata from data words: {extracted_metadata}")
                                
                                # Update remaining data frames
                                if len(remaining_words) != len(binary_data_frames):
                                    logger.info(f"[RT_MSG] Metadata extraction removed {len(binary_data_frames) - len(remaining_words)} data words")
                                    
                                    # Reconstruct remaining data frames with sync and parity
                                    remaining_data_frames = []
                                    for i, word in enumerate(remaining_words):
                                        if i < len(dataFrames):
                                            # Use original frame structure but replace data bits
                                            original_frame = dataFrames[i]
                                            if isinstance(original_frame, str) and len(original_frame) == 20:
                                                # Get the sync pattern (first 3 bits)
                                                sync_pattern = original_frame[:3]
                                                
                                                # Combine sync pattern with the new data word
                                                frame_without_parity = sync_pattern + word
                                                
                                                # Calculate the correct parity bit for the new combined data
                                                # Odd parity: total number of 1s should be odd
                                                ones_count = frame_without_parity.count('1')
                                                parity_bit = '0' if ones_count % 2 == 1 else '1'
                                                
                                                # Create the new frame with correct parity
                                                new_frame = frame_without_parity + parity_bit
                                                
                                                # Verify the new frame has the correct length
                                                if len(new_frame) != 20:
                                                    logger.error(f"[RT_MSG] Reconstructed frame has invalid length: {len(new_frame)}")
                                                    continue
                                                    
                                                # Log the reconstruction
                                                logger.info(f"[RT_MSG] Reconstructed frame: {new_frame} (sync: {sync_pattern}, data: {word}, parity: {parity_bit})")
                                                
                                                remaining_data_frames.append(new_frame)
                                            else:
                                                # Create new data word dictionary
                                                remaining_data_frames.append({'data': int(word, 2)})
                        except Exception as e:
                            logger.error(f"[RT_MSG] Error extracting metadata: {e}")
                            # Continue without metadata if extraction fails
                    
                    # Get message type and command type from RT command map
                    from .RT_command_map import get_rt_message_type
                    message_type, command_type = get_rt_message_type(
                        command_word['rt_address'],
                        command_word['subaddress_mode'],
                        commandFrame,
                        extracted_metadata
                    )
                    logger.info(f"[RT_MSG] Mapped message type: {message_type}, command type: {command_type}")
                    
                    # Add frame count to metadata for precipitation detection
                    extracted_metadata['frame_count'] = len(dataFrames)
                    
                    # Check if this is actually precipitation data being misidentified as VIL completion
                    if message_type == "radarVILCompletion" and self._is_precipitation_message(extracted_metadata):
                        logger.info("[RT_MSG] Correcting misidentified precipitation data")
                        message_type = "weather_radarPrecipitationResponse"
                        command_type = "precipitation_data"
                        
                        # Add precipitation flags to extracted_metadata
                        extracted_metadata['precipitation_message'] = True
                        extracted_metadata['data_type'] = 'precipitation'
                    
                    # If metadata contains message_type or command_type, use those instead
                    if extracted_metadata:
                        if 'message_type' in extracted_metadata:
                            message_type = extracted_metadata['message_type']
                            logger.info(f"[RT_MSG] Using message_type from metadata: {message_type}")
                        
                        if 'command_type' in extracted_metadata:
                            command_type = extracted_metadata['command_type']
                            logger.info(f"[RT_MSG] Using command_type from metadata: {command_type}")
                        
                        if 'command_name' in extracted_metadata:
                            logger.info(f"[RT_MSG] Found command_name in metadata: {extracted_metadata['command_name']}")
                            response_metadata['command_name'] = extracted_metadata['command_name']
                    
                    # Add metadata to command word
                    command_word.update({
                        **response_metadata,
                        **extracted_metadata,  # Include extracted metadata
                        'command_type': command_type,
                        'message_type': message_type,
                        'original_message_type': extracted_metadata.get('original_message_type', message_type)
                    })
                    
                    # Check if this is a block transfer message
                    if 'is_transfer_init' in extracted_metadata and extracted_metadata['is_transfer_init']:
                        command_word['is_transfer_init'] = True
                        logger.info(f"[RT_MSG] Marked command word as block transfer initialization")
                    elif metadata and 'is_transfer_init' in metadata and metadata['is_transfer_init']:
                        command_word['is_transfer_init'] = True
                        logger.info(f"[RT_MSG] Marked command word as block transfer initialization from metadata")
                    
                    logger.info(f"[RT_MSG] Added metadata to command word: {command_word}")
                    
                    # Update dataFrames to only include remaining data frames
                    if remaining_data_frames and len(remaining_data_frames) != len(dataFrames):
                        dataFrames = remaining_data_frames
                        logger.info(f"[RT_MSG] Updated dataFrames to exclude metadata: {len(dataFrames)} frames remaining")
                    
                    # Extract word_count from command_word to know how many data words to expect
                    word_count = command_word.get('word_count_mode', 0)
                    logger.info(f"[RT_MSG] Command word indicates {word_count} data words should follow")
                    
                    # Ensure we only process the expected number of data words
                    if word_count > 0 and len(dataFrames) > word_count:
                        logger.info(f"[RT_MSG] Limiting data frames to word_count: {word_count}")
                        dataFrames = dataFrames[:word_count]                    
                    
                    
            else:
                logger.error("Failed to decode command word")

            # Process data words with metadata from command word
            # First check if this is a binary data message that needs special handling
            is_binary_data = False
            binary_data = []
            
            # Check if this might be a precipitation or binary data message
            if command_word and command_type and message_type:
                # Get the RT_transfer_aggregator instance
                rt_aggregator = get_rt_transfer_aggregator()
                
                # Create a temporary message with the command info 
                temp_message = {
                    'command_type': command_type,
                    'message_type': message_type,
                    'metadata': command_word.copy()
                }
                
                # Check if this message contains binary data
                if rt_aggregator.is_binary_data_message(temp_message):
                    logger.debug(f"[TRANSFER_DATA_DEBUG] Detected binary data message: {message_type}/{command_type}")
                    is_binary_data = True
            
            # Process data words, collecting binary data if needed
            for i, dataFrame in enumerate(dataFrames):
                if dataFrame.startswith(self.DATA_SYNC):
                    logger.info(f"[RT_msg] Data word [{i + 1}]: {dataFrame}")
                    data_word = self.rtd.deconstruct_data_word(dataFrame)
                    
                    # For binary data collection, add the raw data value
                    if is_binary_data and data_word and isinstance(data_word, dict) and 'data' in data_word:
                        binary_data.append(data_word['data'])
                        logger.debug(f"[TRANSFER_DATA_DEBUG] Collected binary data item {i}: {data_word['data']}")
                    
                    if data_word:
                        # Add command metadata to data word
                        if isinstance(data_word, dict):
                            data_word.update({
                                **response_metadata,
                                'command_type': command_word.get('command_type'),
                                'message_type': command_word.get('message_type'),
                                'command_name': command_word.get('command_name'),
                                'data_word_index': i,
                                'total_data_words': word_count if 'word_count_mode' in command_word else len(dataFrames)
                            })
                        else:
                            data_word = {
                                'data': data_word,
                                **response_metadata,
                                'command_type': command_word.get('command_type'),
                                'message_type': command_word.get('message_type'),
                                'command_name': command_word.get('command_name'),
                                'data_word_index': i,
                                'total_data_words': word_count if 'word_count_mode' in command_word else len(dataFrames)
                            }
                        logger.info(f"Valid data word decoded with command metadata: {data_word}")
                        data_words.append(data_word)
                    else:
                        logger.error(f"[RT_msg] Failed to decode data word: {dataFrame}")
                else:
                    logger.error(f"[RT_msg] Invalid data word sync pattern: {dataFrame[:3]}")
            
            # Handle binary data if collected
            if is_binary_data and binary_data:
                logger.debug(f"[TRANSFER_DATA_DEBUG] Collected total of {len(binary_data)} binary data items")
                logger.debug(f"[TRANSFER_DATA_DEBUG] Sample: {binary_data[:5] if len(binary_data) >= 5 else binary_data}")
                
                # If command_word exists, update it with the binary data
                if command_word:
                    command_word['binary_data_preserved'] = True
                    command_word['binary_data_length'] = len(binary_data)
                    
                    # Replace the data in data_words with a single entry containing the binary data array
                    # This will be added to the created MIL_STD_1553B_Message in Remote_Terminal.process_frame
                    if not data_words:
                        # Create a new data word if none exist
                        data_words = [{
                            'data': binary_data,
                            **response_metadata,
                            'command_type': command_word.get('command_type'),
                            'message_type': command_word.get('message_type'),
                            'command_name': command_word.get('command_name'),
                            'data_word_index': 0,
                            'total_data_words': 1,
                            'binary_data_preserved': True,
                            'binary_data_length': len(binary_data)
                        }]
                        logger.debug(f"[TRANSFER_DATA_DEBUG] Created new data word with binary data array")
                    else:
                        # Replace existing data words with a single entry
                        data_words = [{
                            'data': binary_data,
                            **response_metadata,
                            'command_type': command_word.get('command_type'),
                            'message_type': command_word.get('message_type'),
                            'command_name': command_word.get('command_name'),
                            'data_word_index': 0,
                            'total_data_words': 1,
                            'binary_data_preserved': True, 
                            'binary_data_length': len(binary_data)
                        }]
                        logger.debug(f"[TRANSFER_DATA_DEBUG] Replaced data words with binary data array")

            # Generate and send status word acknowledgment if command word was successfully processed
            if command_word and command_word.get('rt_address') is not None:
                # Get RT address from command word
                rt_address = command_word.get('rt_address')
                # Generate status word
                status_word = self.rt_construct.construct_status_word(rt_address)
                
                # Get request ID from command word or direct frame input
                request_id = command_word.get('request_id')
                if not request_id and isinstance(frame, dict):
                    request_id = frame.get('request_id')
                
                # Check if this is a precipitation data or binary data message
                is_precipitation = False
                if command_word.get('message_type') and 'precipitation' in command_word.get('message_type', '').lower():
                    is_precipitation = True
                elif command_word.get('command_type') and command_word.get('command_type') in ['precipitation_data', 'vil_data']:
                    is_precipitation = True
                elif self._is_precipitation_message(command_word):
                    is_precipitation = True
                
                # Send status word with all necessary metadata
                metadata = command_word.copy() if isinstance(command_word, dict) else {}
                self._send_status_word(status_word, request_id, rt_address, metadata)
                
                # Log the acknowledgment, especially important for precipitation data
                if is_precipitation:
                    logger.info(f"[RT_MSG] Acknowledged precipitation data command with status word, request_id: {request_id}")
                else:
                    logger.info(f"[RT_MSG] Acknowledged command with status word, request_id: {request_id}")
                
            return command_word, data_words
        except Exception as e:
            logger.error(f"[RT_msg] Error processing frame: {e}")
            # Even in case of error, try to send a basic status word acknowledgment if possible
            try:
                if isinstance(frame, dict) and frame.get('request_id'):
                    rt_address = 9  # Default RT address if we can't extract it
                    if isinstance(frame.get('frames'), list) and len(frame.get('frames')) > 0:
                        # Try to extract RT address from first frame
                        first_frame = frame.get('frames')[0]
                        if isinstance(first_frame, str) and len(first_frame) >= 8:
                            # Extract RT address bits from command word
                            rt_address_bits = first_frame[3:8]
                            if all(bit in '01' for bit in rt_address_bits):
                                rt_address = int(rt_address_bits, 2)
                    
                    # Generate basic status word
                    status_word = self.rt_construct.construct_status_word(rt_address)
                    self._send_status_word(status_word, frame.get('request_id'), rt_address)
                    logger.info(f"[RT_MSG] Sent error-recovery status word with request_id: {frame.get('request_id')}")
            except Exception as status_error:
                logger.error(f"[RT_MSG] Failed to send error-recovery status word: {status_error}")
            
            return None, None

    def _send_status_word(self, status_word, request_id=None, rt_address=None, metadata=None):
        """Send status word back to BC using RT_sender with enhanced metadata."""
        try:
            # Ensure status word is properly formatted
            if not isinstance(status_word, str):
                logger.error(f"[RT_msg] Invalid status word type: {type(status_word)}")
                return False
                
            if len(status_word) != 20:
                logger.error(f"[RT_msg] Invalid status word length: {len(status_word)}")
                return False
                
            if not status_word.startswith(self.STATUS_SYNC):
                logger.error(f"[RT_msg] Invalid status word sync pattern: {status_word[:3]}")
                return False
            
            # Extract RT address from status word if not provided
            if rt_address is None:
                rt_address = int(status_word[3:8], 2) if all(bit in '01' for bit in status_word[3:8]) else 9
            
            # Create enhanced message structure with all required fields BC_Listener expects
            message = {
                'status_word': status_word,  # Use consistent field name across all components
                'frames': [status_word],     # BC_Listener also looks for frames array
                'request_id': request_id,    # Critical for matching acknowledgments
                'rt_address': rt_address,
                'sub_address': metadata.get('sub_address', metadata.get('subaddress', 1)) if metadata else 1,
                'message_type': metadata.get('message_type', 'status_word'),
                'original_message_type': metadata.get('original_message_type', 'status_word'),
                'command_type': metadata.get('command_type', None) if metadata else None,
                'timestamp': time.time()
            }
            
            # Add critical transfer-specific fields if present in metadata
            transfer_fields = [
                'is_transfer_init', 'is_transfer_data', 'is_transfer_complete',
                'sequence_number', 'total_sequences', 'is_final'
            ]
            
            for field in transfer_fields:
                if metadata and field in metadata:
                    message[field] = metadata[field]
                    logger.info(f"[RT_MSG] Including {field}={metadata[field]} in status word response")
            
            # Check if this is a precipitation or binary data acknowledgment
            if metadata and ('precipitation_message' in metadata or 
                           (metadata.get('message_type') and 'precipitation' in metadata.get('message_type').lower()) or
                           metadata.get('command_type') == 'precipitation_data'):
                message['precipitation_message'] = True
                message['data_type'] = 'precipitation'
                logger.info(f"[RT_MSG] Marked status word as precipitation data acknowledgment")
            
            # Create a metadata field at the dictionary level
            message['metadata'] = {
                'message_type': message['message_type'],
                'command_type': message['command_type'],
                'rt_address': rt_address,
                'sub_address': message['sub_address'],
                'request_id': request_id
            }
            
            # Copy transfer fields to metadata dictionary
            for field in transfer_fields:
                if field in message:
                    message['metadata'][field] = message[field]
            
            # Send message with retry if needed
            max_retries = 3
            for retry in range(max_retries):
                logger.info(f"[RT_MSG] Sending status word acknowledgment (attempt {retry+1}/{max_retries}): {status_word}")
                if self.rt_sender.RT_send_message(message):
                    logger.info(f"[RT_MSG] Successfully sent status word acknowledgment with request_id: {request_id}")
                    return True
                else:
                    logger.warning(f"[RT_MSG] Status word send attempt {retry+1} failed, retrying...")
                    time.sleep(0.01)  # Brief delay before retry
                    
            logger.error(f"Failed to send status word after {max_retries} attempts: {message}")
            return False
        except Exception as e:
            logger.error(f"Error sending status word: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
class RT_construct:
    # Sync patterns according to MIL-STD-1553B (matching BC_msg.py)
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern (same as command)
    
    def __init__(self):
        self.rte = RTWordsEncoder()
        logger.info("RT_construct initialized")
        
    def calculate_parity(self, word):
        """Calculate odd parity bit for a binary word"""
        return '1' if word.count('1') % 2 == 0 else '0'
        
    def construct_data_word(self, data_word_frame):
        try:
            logger.info(f"Constructing data word from frame: {data_word_frame}")
            # RTWordsEncoder already adds sync pattern and parity
            data_word = self.rte.encode_data_word(data_word_frame)
            logger.info(f"Constructed data word: {data_word}")
            return data_word
        
        except Exception as error:
            logger.error(f"Error constructing data word: {str(error)}")
            return None

    def construct_status_word(self, RT_address):
        try:
            logger.info(f"Constructing status word for RT address: {RT_address}")
            # RTWordsEncoder already adds sync pattern and parity
            status_word = self.rte.encode_status_word(RT_address)
            logger.info(f"Constructed status word: {status_word}")
            return status_word

        except Exception as error:
            logger.error(f"Error constructing status word: {str(error)}")
            return None

class RT_deconstruct:
    # Sync patterns according to MIL-STD-1553B (matching BC_msg.py)
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern (same as command)
    
    def __init__(self):
        self.rtd = RTWordsDecoder()
        logger.info("RT_deconstruct initialized")
        
    def calculate_parity(self, word):
        """Calculate odd parity bit for a binary word"""
        return '1' if word.count('1') % 2 == 0 else '0'
        
    def deconstruct_data_word(self, inc_data_word_frame):
        try:
            logger.info(f"[RT] Deconstructing data word frame: {inc_data_word_frame}")
            
            # Verify sync pattern and length
            if not inc_data_word_frame.startswith(self.DATA_SYNC):
                logger.error("[RT] Invalid data word sync pattern")
                # Try to fix sync pattern
                fixed_frame = self.DATA_SYNC + inc_data_word_frame[3:]
                logger.info(f"[RT] Attempting to fix sync pattern: {fixed_frame}")
                inc_data_word_frame = fixed_frame
            
            # Ensure frame is 20 bits
            if len(inc_data_word_frame) != 20:
                logger.error(f"[RT] Invalid data word length: {len(inc_data_word_frame)}")
                raise Exception("[RT] Invalid Data Word Frame")

            
            # Check and fix parity if needed
            if self.calculate_parity(inc_data_word_frame[:-1]) != inc_data_word_frame[-1]:
                logger.warning(f"[RT] Invalid data word parity: {inc_data_word_frame}")
                # Fix parity
                correct_parity = self.calculate_parity(inc_data_word_frame[:-1])
                fixed_frame = inc_data_word_frame[:-1] + correct_parity
                logger.info(f"[RT] Fixed parity: {fixed_frame}")
                inc_data_word_frame = fixed_frame
            
            # Decode data word with fixed frame
            try:
                data_word = self.rtd.decode_data_word(inc_data_word_frame)
                if data_word is not None:
                    logger.info(f"[RT] Decoded data word: {data_word}")
                    return data_word
                else:
                    # If RTWordsDecoder fails, extract data bits manually
                    logger.warning("[RT] RTWordsDecoder failed, extracting data bits manually")
                    data_bits = inc_data_word_frame[3:19]
                    data_value = int(data_bits, 2)
                    manual_data_word = {
                        'sync': inc_data_word_frame[:3],
                        'data': data_value,
                        'parity': int(inc_data_word_frame[19])
                    }
                    logger.info(f"[RT] Manually extracted data word: {manual_data_word}")
                    return manual_data_word
            except Exception as decode_error:
                logger.error(f"[RT] Error in RTWordsDecoder: {str(decode_error)}")
                # Extract data bits manually as fallback
                data_bits = inc_data_word_frame[3:19]
                data_value = int(data_bits, 2)
                manual_data_word = {
                    'sync': inc_data_word_frame[:3],
                    'data': data_value,
                    'parity': int(inc_data_word_frame[19])
                }
                logger.info(f"[RT] Manually extracted data word: {manual_data_word}")
                return manual_data_word
                    
        except Exception as error:
            logger.error(f"[RT] Error deconstructing data word: {str(error)}")
            # Last resort fallback - try to extract data bits from whatever we have
            try:
                if isinstance(inc_data_word_frame, str) and len(inc_data_word_frame) >= 16:
                    # Extract middle 16 bits or as many as possible
                    start_idx = max(0, (len(inc_data_word_frame) - 16) // 2)
                    data_bits = inc_data_word_frame[start_idx:start_idx+16]
                    if len(data_bits) < 16:
                        data_bits = data_bits.ljust(16, '0')
                    data_value = int(data_bits, 2)
                    fallback_data_word = {
                        'data': data_value,
                        'sync': '001',  # Default sync
                        'parity': 0     # Default parity
                    }
                    logger.info(f"[RT] Created fallback data word: {fallback_data_word}")
                    return fallback_data_word
            except Exception as fallback_error:
                logger.error(f"[RT] Fallback extraction failed: {str(fallback_error)}")
            return None
    
    def deconstruct_command_word(self, frame):
        try:
            logger.info(f"[RT] Deconstructing command word frame: {frame}")
            
            # Verify sync pattern and length
            if not frame.startswith(self.COMMAND_SYNC):
                logger.error("[RT] Invalid command word sync pattern")
                raise Exception("[RT] Invalid Command Word Frame")
                
            if len(frame) != 20:
                logger.error("[RT] Invalid command word length")
                raise Exception("[RT] Invalid Command Word Frame")
                
            # Verify parity
            if self.calculate_parity(frame[:-1]) != frame[-1]:
                logger.error("[RT] Invalid command word parity")
                raise Exception("[RT] Invalid Command Word Frame")
            
            # Decode command word
            command_word = self.rtd.decode_command_word(frame)
            if command_word is not None:
                logger.info(f"[RT] Decoded command word: {command_word}")
                return command_word
            else:
                logger.error("[RT] Failed to decode command word")
                raise Exception("[RT] Invalid Command Word Frame")
            
        except Exception as error:
            logger.error(f"[RT] Error deconstructing command word: {str(error)}")
            return None
