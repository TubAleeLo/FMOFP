"""
Remote Terminal

Handles communication between the Bus Controller and Remote Terminal subsystems.
Using mirrored BC sending behavior for consistent communication.
"""
import threading
import traceback
import time
import asyncio
import copy
import FMOFP.Utils.common.fetching as fetching
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.RT_msg import RT_Message_Analyzer, RT_construct
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.RT_transfer_aggregator import get_rt_transfer_aggregator
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_sender, get_rt_listener
from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
from FMOFP.Utils.common.thread_manager import ThreadManager
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class Remote_Terminal:
    """
    Remote Terminal class that handles communication with the Bus Controller.
    Sending behavior mirrors BC for consistent communication patterns.
    """
    _instance = None
    _lock = threading.RLock()  # Class-level lock for thread safety
    _initialized = False
    _last_log_time = 0
    _log_interval = 10.0  # Log only every 10 seconds
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Remote_Terminal, cls).__new__(cls)
                logger.info("Remote_Terminal singleton instance created")
            return cls._instance
    
    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.listening = False
                self.stop_event = threading.Event()
                self.last_sent_status = None
                self.rt_listener = get_rt_listener()  # Use global instance
                logger.info(f"Remote_Terminal using RT_Listener instance: {id(self.rt_listener)}")
                self.rtma = RT_Message_Analyzer()  # Create analyzer once
                self._instance_lock = threading.Lock()
                self._block_transfer_lock = threading.RLock()
                self._block_transfer_state = {}  # For tracking block transfers
                self._event_loop = None  # Event loop for async processing
                self.rt_construct = RT_construct()  # Create RT_construct once
                self.pending_requests = {}  # Track pending requests by request_id
                self.message_lock = threading.Lock()  # Lock for thread-safe operations on processed_messages
                self.processed_messages = []  # Queue for processed messages
                self.__class__._initialized = True
                logger.info("Remote_Terminal initialized with global RT_Listener")
            else:
                # Only log occasionally to avoid spamming logs
                current_time = time.time()
                if (current_time - self.__class__._last_log_time) >= self.__class__._log_interval:
                    logger.info(f"Reusing existing Remote_Terminal instance with RT_Listener: {id(self.rt_listener)}")
                    self.__class__._last_log_time = current_time

    def send_message(self, message):
        """
        Send message to BC, mirroring BC's approach to sending messages.
        
        Args:
            message: The message to send, can be a status word, dict with frames, or MIL_STD_1553B_Message
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the RT_sender instance
            rts = get_rt_sender()
            
            # Standardized message formatting for all types
            if isinstance(message, dict):
                if 'status_word' in message:
                    # Already in proper format for RT_send_message, just ensure all fields are present
                    formatted_message = message.copy()
                    # Add timestamp if not present
                    if 'timestamp' not in formatted_message:
                        formatted_message['timestamp'] = time.time()
                    # Add frames for block transfer protocol if not present
                    if 'frames' not in formatted_message and 'status_word' in formatted_message:
                        formatted_message['frames'] = [formatted_message['status_word']]
                        
                    logger.info(f"RT sending formatted message: {formatted_message}")
                    return rts.RT_send_message(formatted_message)
                elif 'frames' in message:
                    # Already in proper format, just ensure metadata is present
                    logger.info(f"RT sending frames message: {message}")
                    return rts.RT_send_message(message)
                else:
                    logger.error(f"Invalid message format - missing frames or status_word: {message}")
                    return False
            elif isinstance(message, list):
                # Convert list of frames to proper format
                if all(isinstance(frame, str) for frame in message):
                    # Extract status word from first element
                    status_word = message[0] if message else None
                    if status_word and len(status_word) == 20 and status_word.startswith("100"):
                        formatted_message = {
                            'status_word': status_word,
                            'frames': message,
                            'timestamp': time.time()
                        }
                        logger.info(f"RT sending formatted status word with frames: {formatted_message}")
                        return rts.RT_send_message(formatted_message)
                    else:
                        logger.warning(f"Invalid status word in frame list: {status_word}")
                        return rts.RT_send_message(message)
                else:
                    logger.warning(f"Invalid frame list: {message}")
                    return rts.RT_send_message(message)
            elif isinstance(message, str) and message:
                # Check if this is a status word (20 bits with sync pattern 100)
                if len(message) == 20 and message.startswith("100"):
                    # Format properly for sending
                    formatted_message = {
                        'status_word': message,
                        'frames': [message],
                        'timestamp': time.time()
                    }
                    logger.info(f"RT sending formatted status word: {formatted_message}")
                    return rts.RT_send_message(formatted_message)
                else:
                    logger.warning(f"Invalid status word: {message}")
                    return rts.RT_send_message(message)
            elif isinstance(message, MIL_STD_1553B_Message):
                # Extract fields from MIL_STD_1553B_Message and format properly
                # First, check if it has a status_word field
                status_word = getattr(message, 'status_word', None)
                
                # If no status word, try to create one using RT_construct
                if not status_word:
                    # Generate a proper status word based on RT and subaddress
                    rt_address = getattr(message, 'rt_address', 9)  # Default to radar system if not specified
                    sub_address = getattr(message, 'sub_address', 1)  # Default to data subaddress if not specified
                    status_word = self.rt_construct.construct_status_word(rt_address, sub_address)
                    logger.info(f"Generated status word for RT={rt_address}, SA={sub_address}: {status_word}")
                
                # Create properly formatted message
                formatted_message = {
                    'status_word': status_word,
                    'frames': [status_word],  # Initialize with status word
                    'request_id': getattr(message, 'request_id', None),
                    'timestamp': time.time(),
                    'metadata': {
                        'message_type': getattr(message, 'message_type', None),
                        'command_type': getattr(message, 'command_type', None),
                        'command_name': getattr(message, 'command_name', None),
                        'rt_address': getattr(message, 'rt_address', None),
                        'sub_address': getattr(message, 'sub_address', None)
                    }
                }
                
                # Add data if available
                if hasattr(message, 'data') and message.data:
                    # Handle different data formats
                    data = message.data
                    
                    # If data is a string and looks like binary, convert to data words
                    if isinstance(data, str) and all(bit in '01' for bit in data):
                        # Chunk into 16-bit data words
                        data_words = []
                        for i in range(0, len(data), 16):
                            chunk = data[i:i+16].ljust(16, '0')
                            # Add sync and parity to make it a valid 20-bit word
                            data_word = '001' + chunk + self._calculate_parity('001' + chunk)
                            data_words.append(data_word)
                        
                        # Add data words to frames
                        formatted_message['frames'].extend(data_words)
                        logger.info(f"Added {len(data_words)} data words to message")
                    elif isinstance(data, (list, tuple)):
                        # Handle list of data elements
                        for item in data:
                            if isinstance(item, str) and len(item) == 20:
                                # Already a valid 20-bit word
                                formatted_message['frames'].append(item)
                            elif isinstance(item, (int, float)):
                                # Convert number to data word
                                data_word = self.rt_construct.construct_data_word(int(item))
                                formatted_message['frames'].append(data_word)
                            else:
                                logger.warning(f"Unsupported data format: {type(item)}")
                        logger.info(f"Added {len(data)} data items to message")
                    else:
                        # Add raw data to preserved metadata
                        formatted_message['data'] = data
                        logger.info(f"Added raw data to message metadata")
                
                # Check if this should use block transfer
                if len(formatted_message['frames']) > 33:  # Status word + 32 data words
                    logger.info(f"Message requires block transfer with {len(formatted_message['frames'])} frames")
                
                logger.info(f"RT sending formatted MIL_STD_1553B_Message: {formatted_message}")
                return rts.RT_send_message(formatted_message)
            else:
                logger.error(f"Unsupported message type: {type(message)}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            logger.error(traceback.format_exc())
            return False

    def _calculate_parity(self, bits):
        """Calculate odd parity bit for a binary string."""
        ones_count = bits.count('1')
        return '1' if ones_count % 2 == 0 else '0'

    async def process_frame(self, frame):
        """
        Process incoming frames, mirroring BC's frame processing approach.
        
        Args:
            frame: The frame to process, can be a dict with frames, or a list of frames
            
        Returns:
            bool: True if successfully processed, False otherwise
        """
        try:
            logger.info(f"[RT] Processing frame: {frame}")
            
            # Extract the actual frames from the dictionary if needed
            actual_frames = frame
            request_id = None
            metadata = None
            
            if isinstance(frame, dict):
                if 'frames' in frame:
                    actual_frames = frame['frames']
                    logger.info(f"[RT] Extracted frames from dictionary: {actual_frames}")
                request_id = frame.get('request_id')
                metadata = frame.get('metadata', {})
            
            # Check if this is a block transfer message
            is_block_transfer = False
            if isinstance(frame, dict):
                # Check both top-level and metadata for transfer indicators
                is_transfer_init = frame.get('is_transfer_init', False)
                is_transfer_data = frame.get('is_transfer_data', False)
                is_transfer_complete = frame.get('is_transfer_complete', False)
                
                if metadata:
                    is_transfer_init = is_transfer_init or metadata.get('is_transfer_init', False)
                    is_transfer_data = is_transfer_data or metadata.get('is_transfer_data', False)
                    is_transfer_complete = is_transfer_complete or metadata.get('is_transfer_complete', False)
                
                if is_transfer_init or is_transfer_data or is_transfer_complete:
                    is_block_transfer = True
                    logger.info(f"[RT] Detected block transfer message: init={is_transfer_init}, data={is_transfer_data}, complete={is_transfer_complete}")
                    
                    # Handle block transfer
                    if is_transfer_init:
                        self._handle_block_transfer_init(frame)
                        return True
                    elif is_transfer_data:
                        # Handle data part of block transfer
                        self._handle_block_transfer_data(frame)
                        return True
                    elif is_transfer_complete:
                        # Handle completion of block transfer
                        self._handle_block_transfer_complete(frame)
                        return True
            
            # Use RT_Message_Analyzer to process the frames
            command_word, data_words = self.rtma.route_inc_frame(actual_frames)
            
            if command_word:
                logger.info(f"[RT] Successfully processed command word: {command_word}")
                
                # Extract necessary fields from command word
                rt_address = command_word.get('rt_address')
                sub_address = command_word.get('subaddress_mode')
                mode = command_word.get('mode')
                mode_value = None
                
                # Check if mode_value is in data_words
                if data_words and len(data_words) > 0:
                    mode_value = data_words[0].get('data') if isinstance(data_words[0], dict) else data_words[0]
                    logger.info(f"[RT] Extracted mode_value: {mode_value}")
                
                # Check if mode_value is in metadata
                if metadata and 'mode_value' in metadata:
                    mode_value = metadata['mode_value']
                    logger.info(f"[RT] Found mode_value in metadata: {mode_value}")
                
                # Combine data from all data words if any
                data = data_words
                
                # Extract message_type and command_type
                message_type = command_word.get('message_type')
                command_type = command_word.get('command_type')
                command_name = command_word.get('command_name')
                
                # Add additional metadata if available
                if metadata:
                    if 'message_type' in metadata and metadata['message_type']:
                        message_type = metadata['message_type']
                    if 'command_type' in metadata and metadata['command_type']:
                        command_type = metadata['command_type']
                    if 'command_name' in metadata and metadata['command_name']:
                        command_name = metadata['command_name']
                    # Also check for mode information
                    if 'mode' in metadata and metadata['mode']:
                        mode = metadata['mode']
                    if 'mode_value' in metadata and metadata['mode_value'] is not None:
                        mode_value = metadata['mode_value']
                
                # Get the RT_transfer_aggregator for binary data handling
                rt_aggregator = get_rt_transfer_aggregator()
                
                # Prepare a message context to check for binary data
                message_context = {
                    'message_type': message_type,
                    'command_type': command_type,
                    'metadata': {}
                }
                
                # Check if this is a binary data message
                is_binary_data = rt_aggregator.is_binary_data_message(message_context)
                if is_binary_data:
                    logger.debug(f"[TRANSFER_DATA_DEBUG] RT detected binary data message: {message_type}/{command_type}")
                
                # Extract and convert data to a format MIL_STD_1553B_Message can handle
                processed_data = []
                if isinstance(data, list):
                    # Check for the special case of a single dict with a binary data array
                    if len(data) == 1 and isinstance(data[0], dict) and 'data' in data[0] and isinstance(data[0]['data'], list):
                        binary_data = data[0]['data']
                        if all(isinstance(item, int) for item in binary_data):
                            logger.debug(f"[TRANSFER_DATA_DEBUG] Found binary data array with {len(binary_data)} elements")
                            logger.debug(f"[TRANSFER_DATA_DEBUG] Sample: {binary_data[:5] if len(binary_data) >= 5 else binary_data}")
                            processed_data = binary_data  # Use the binary data array directly
                    else:
                        # Process each item in the data list
                        for item in data:
                            if isinstance(item, dict) and 'data' in item:
                                data_value = item['data']
                                # Check if this is a binary array
                                if isinstance(data_value, list) and all(isinstance(x, int) for x in data_value):
                                    logger.debug(f"[TRANSFER_DATA_DEBUG] Found nested binary data array with {len(data_value)} elements")
                                    processed_data = data_value  # Use binary array directly
                                    break
                                else:
                                    # Extract the data value from the dictionary
                                    processed_data.append(data_value)
                            elif isinstance(item, (int, float, str)):
                                # Keep primitive types as-is
                                processed_data.append(item)
                            else:
                                # Skip items that can't be converted
                                logger.warning(f"[RT] Skipping unconvertible data item: {type(item)}")
                elif isinstance(data, (int, float, str)):
                    processed_data = [data]
                else:
                    logger.warning(f"[RT] Using empty data list due to unconvertible data type: {type(data)}")
                    processed_data = []
                
                # If we have binary data, make sure it's preserved
                if is_binary_data and isinstance(processed_data, list) and len(processed_data) > 0:
                    logger.debug(f"[TRANSFER_DATA_DEBUG] RT ensuring binary data preservation: {len(processed_data)} elements")
                    # Add proper flags in the message metadata
                    if not metadata:
                        metadata = {}
                    metadata['binary_data_preserved'] = True
                    metadata['binary_data_length'] = len(processed_data)
                    if 'precipitation' in str(message_type).lower() or 'precipitation' in str(command_type).lower():
                        metadata['precipitation_message'] = True
                        metadata['data_type'] = 'precipitation'
                
                logger.info(f"[RT] Processed data for MIL_STD_1553B_Message: {len(processed_data)} items")
                
                # Create MIL_STD_1553B_Message with all available information
                message = MIL_STD_1553B_Message(
                    rt_address=rt_address,
                    sub_address=sub_address,
                    data=processed_data,
                    message_type=message_type,
                    command_type=command_type,
                    command_name=command_name
                )
                
                # Add request_id if available
                if request_id:
                    message.request_id = request_id
                
                # Add mode information if available
                if mode:
                    message.mode = mode
                if mode_value is not None:
                    message.mode_value = mode_value
                
                # Add any additional fields from metadata
                if metadata:
                    for key, value in metadata.items():
                        if key not in ['rt_address', 'sub_address', 'data', 'message_type', 'command_type', 'command_name', 'request_id', 'mode', 'mode_value']:
                            setattr(message, key, value)
                
                # Log all details of the created message
                logger.info(f"[RT] Created MIL_STD_1553B_Message with:")
                logger.info(f"[RT]   - rt_address: {message.rt_address}")
                logger.info(f"[RT]   - sub_address: {message.sub_address}")
                logger.info(f"[RT]   - message_type: {message.message_type}")
                logger.info(f"[RT]   - command_type: {message.command_type}")
                logger.info(f"[RT]   - command_name: {message.command_name}")
                logger.info(f"[RT]   - request_id: {getattr(message, 'request_id', None)}")
                logger.info(f"[RT]   - mode: {getattr(message, 'mode', None)}")
                logger.info(f"[RT]   - mode_value: {getattr(message, 'mode_value', None)}")
                
                # Add message to processed_messages queue
                with self.rt_listener.message_lock:
                    self.rt_listener.processed_messages.append(message)
                    logger.info(f"[RT] Added message to processed_messages queue: {str(message).replace('→', '->')}")
                    logger.info(f"[RT] Current processed_messages queue size: {len(self.rt_listener.processed_messages)}")
                
                return True
            else:
                logger.warning("[RT] Failed to process command word")
                return False
                
        except Exception as e:
            logger.error(f"[RT] Error processing frame: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _handle_block_transfer_init(self, frame):
        """
        Handle block transfer initialization messages.
        
        Args:
            frame: The frame containing block transfer initialization information
        """
        try:
            logger.info(f"[RT] Handling block transfer initialization: {frame}")
            
            # Extract necessary information
            request_id = frame.get('request_id')
            if not request_id:
                logger.error("[RT] Block transfer initialization missing request_id")
                return
            
            metadata = frame.get('metadata', {})
            frames = frame.get('frames', [])
            
            # Extract total_messages and total_frames from either top-level or metadata
            total_messages = frame.get('total_messages')
            total_frames = frame.get('total_frames')
            
            if metadata:
                if total_messages is None and 'total_messages' in metadata:
                    total_messages = metadata['total_messages']
                if total_frames is None and 'total_frames' in metadata:
                    total_frames = metadata['total_frames']
            
            # If still not found, try to extract from frames if available
            if (total_messages is None or total_frames is None) and len(frames) >= 3:
                # In a block transfer init message, frames[1] = total_messages, frames[2] = total_frames
                # These are binary words that need to be converted to integers
                if total_messages is None and frames[1]:
                    # Extract 16 data bits (bits 3-18) from the 20-bit word
                    data_bits = frames[1][3:19]
                    try:
                        total_messages = int(data_bits, 2)
                        logger.info(f"[RT] Extracted total_messages from frame: {total_messages}")
                    except ValueError:
                        logger.error(f"[RT] Invalid total_messages format: {data_bits}")
                
                if total_frames is None and frames[2]:
                    # Extract 16 data bits (bits 3-18) from the 20-bit word
                    data_bits = frames[2][3:19]
                    try:
                        total_frames = int(data_bits, 2)
                        logger.info(f"[RT] Extracted total_frames from frame: {total_frames}")
                    except ValueError:
                        logger.error(f"[RT] Invalid total_frames format: {data_bits}")
            
            if total_messages is None:
                logger.warning("[RT] Missing total_messages in block transfer initialization")
                total_messages = 1  # Default to 1 if not specified
            
            if total_frames is None:
                logger.warning("[RT] Missing total_frames in block transfer initialization")
                total_frames = 0  # Default to 0 if not specified
            
            # Get message_type and command_type
            message_type = metadata.get('message_type') if metadata else None
            command_type = metadata.get('command_type') if metadata else None
            command_name = metadata.get('command_name') if metadata else None
            
            # Initialize block transfer state
            with self._block_transfer_lock:
                self._block_transfer_state[request_id] = {
                    'total_messages': total_messages,
                    'total_frames': total_frames,
                    'received_messages': 0,
                    'received_frames': 0,
                    'data_buffer': [],
                    'timestamp': time.time(),
                    'message_type': message_type,
                    'command_type': command_type,
                    'command_name': command_name,
                    'metadata': metadata,
                    'complete': False
                }
                logger.info(f"[RT] Initialized block transfer state for request_id {request_id}")
            
            # Send acknowledgment to BC
            rt_address = frame.get('rt_address')
            if not rt_address and metadata:
                rt_address = metadata.get('rt_address')
            if not rt_address:
                rt_address = 9  # Default to radar system
            
            # Construct a status word for acknowledgment
            status_word = self.rt_construct.construct_status_word(rt_address)
            
            # Create acknowledgment message
            ack_message = {
                'status_word': status_word,
                'request_id': request_id,
                'timestamp': time.time(),
                'command_type': 'transfer_init_ack',
                'message_type': message_type,
                'command_name': command_name,
                'metadata': {
                    'is_transfer_init_ack': True,
                    'total_messages': total_messages,
                    'total_frames': total_frames
                }
            }
                
            # Send acknowledgment
            self.send_message(ack_message)
            logger.info(f"[RT] Sent acknowledgment for block transfer completion: {request_id}")
                
        except Exception as e:
            logger.error(f"[RT] Error handling block transfer completion: {str(e)}")
            logger.error(traceback.format_exc())

    def _process_complete_block_transfer(self, request_id):
        """
        Process a complete block transfer and create a message for it.
        
        Args:
            request_id: The request ID of the complete block transfer
        """
        try:
            logger.info(f"[RT] Processing complete block transfer for request_id {request_id}")
            
            with self._block_transfer_lock:
                if request_id not in self._block_transfer_state:
                    logger.error(f"[RT] No block transfer state found for request_id {request_id}")
                    return
                
                # Get the state
                state = self._block_transfer_state[request_id]
                
                # Extract data buffer and metadata
                data_buffer = state['data_buffer']
                message_type = state['message_type']
                command_type = state['command_type']
                command_name = state['command_name']
                metadata = state['metadata']
                
                # Convert data buffer to a proper format for MIL_STD_1553B_Message
                # For binary data words, extract the 16 data bits (bits 3-18)
                data = []
                for frame in data_buffer:
                    if isinstance(frame, str) and len(frame) == 20:
                        # Extract 16 data bits (bits 3-18) from the 20-bit word
                        data_bits = frame[3:19]
                        try:
                            data_value = int(data_bits, 2)
                            data.append(data_value)
                        except ValueError:
                            logger.error(f"[RT] Invalid data format in frame: {frame}")
                    else:
                        logger.warning(f"[RT] Invalid frame in data buffer: {frame}")
                
                logger.info(f"[RT] Extracted {len(data)} data values from block transfer")
                
                # Determine RT address and subaddress
                rt_address = None
                sub_address = None
                
                if metadata:
                    rt_address = metadata.get('rt_address')
                    sub_address = metadata.get('sub_address') or metadata.get('subaddress')
                
                if rt_address is None:
                    rt_address = 9  # Default to radar system
                if sub_address is None:
                    sub_address = 1  # Default to data subaddress
                
                # Create MIL_STD_1553B_Message
                message = MIL_STD_1553B_Message(
                    rt_address=rt_address,
                    sub_address=sub_address,
                    data=data,
                    message_type=message_type,
                    command_type=command_type,
                    command_name=command_name
                )
                
                # Add request_id
                message.request_id = request_id
                
                # Add block transfer information
                message.is_block_transfer = True
                message.block_transfer_complete = True
                
                # Add any additional metadata fields
                if metadata:
                    for key, value in metadata.items():
                        if key not in ['rt_address', 'sub_address', 'data', 'message_type', 'command_type', 'command_name', 'request_id']:
                            setattr(message, key, value)
                
                # Log the created message
                logger.info(f"[RT] Created message from complete block transfer:")
                logger.info(f"[RT]   - rt_address: {message.rt_address}")
                logger.info(f"[RT]   - sub_address: {message.sub_address}")
                logger.info(f"[RT]   - message_type: {message.message_type}")
                logger.info(f"[RT]   - command_type: {message.command_type}")
                logger.info(f"[RT]   - command_name: {message.command_name}")
                logger.info(f"[RT]   - request_id: {message.request_id}")
                logger.info(f"[RT]   - data length: {len(data)}")
                
                # Add message to processed_messages queue
                with self.rt_listener.message_lock:
                    self.rt_listener.processed_messages.append(message)
                    logger.info(f"[RT] Added block transfer message to processed_messages queue")
                    logger.info(f"[RT] Current processed_messages queue size: {len(self.rt_listener.processed_messages)}")
        except Exception as e:
            logger.error(f"[RT] Error processing complete block transfer: {str(e)}")
            logger.error(traceback.format_exc())

    def process_frames_loop(self):
        """Process frames according to MIL-STD-1553B protocol - mirror of BC's approach."""
        logger.info("Remote_Terminal.process_frames_loop: Starting frame processing loop")
        
        # Create event loop for async processing if not already created
        if self._event_loop is None:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            logger.info("Created new event loop for async processing")
        
        # Add logging throttling
        last_log_time = 0
        log_interval = 10.0  
        
        # Add message counters for monitoring
        message_count = 0
        processed_count = 0
        
        while self.listening and not self.stop_event.is_set():
            try:
                # Log status periodically
                current_time = time.time()
                should_log = (current_time - last_log_time) >= log_interval
                
                if should_log:
                    # Log queue status
                    with self.rt_listener.message_lock:
                        processed_queue_size = len(self.rt_listener.processed_messages)
                    data_received_size = len(self.rt_listener.data_received)
                    logger.info(f"Remote_Terminal.process_frames_loop: Status - processed_messages={processed_queue_size}, data_received={data_received_size}")
                    logger.info(f"Remote_Terminal.process_frames_loop: Messages processed: {message_count}, Successfully processed: {processed_count}")
                    last_log_time = current_time
                
                # Only process when actual BC command received
                if self.rt_listener.data_received and len(self.rt_listener.data_received) > 0:
                    frames = self.rt_listener.data_received.pop(0)
                    message_count += 1
                    
                    if isinstance(frames, (list, dict)):
                        logger.info(f"Remote_Terminal.process_frames_loop: Processing frames: {frames}")
                        try:
                            # Process frame using async method
                            result = self._event_loop.run_until_complete(self.process_frame(frames))
                            if result:
                                logger.info("Remote_Terminal.process_frames_loop: Frames processed successfully")
                                processed_count += 1
                            else:
                                logger.warning("Remote_Terminal.process_frames_loop: Frame processing returned False")
                                
                            with self.rt_listener.message_lock:
                                queue_size = len(self.rt_listener.processed_messages)
                            logger.info(f"Remote_Terminal.process_frames_loop: Current processed_messages queue size: {queue_size}")

                        except Exception as e:
                            logger.error(f"Remote_Terminal.process_frames_loop: Error processing frames: {e}")
                            logger.error(traceback.format_exc())
                    else:
                        logger.error(f"Remote_Terminal.process_frames_loop: Invalid frames format: {type(frames)}")
                
                # Cleanup block transfer state periodically
                self._cleanup_block_transfer_state()
                
                # Small sleep to prevent tight loop
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Remote_Terminal.process_frames_loop: Error in loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(0.1)  # Sleep longer on error
                
        logger.info("Remote_Terminal.process_frames_loop: Frame processing loop stopped")

    def _cleanup_block_transfer_state(self):
        """Clean up block transfer state to prevent memory leaks."""
        try:
            current_time = time.time()
            with self._block_transfer_lock:
                # Remove block transfer states older than 60 seconds
                expired_request_ids = []
                for request_id, state in self._block_transfer_state.items():
                    if current_time - state['timestamp'] > 60.0:
                        expired_request_ids.append(request_id)
                
                # Remove expired states
                for request_id in expired_request_ids:
                    logger.info(f"[RT] Removing expired block transfer state for request_id: {request_id}")
                    del self._block_transfer_state[request_id]
                
                if expired_request_ids:
                    logger.info(f"[RT] Removed {len(expired_request_ids)} expired block transfer states")
        except Exception as e:
            logger.error(f"[RT] Error cleaning up block transfer state: {e}")
            logger.error(traceback.format_exc())

    def start_listener(self):
        """Start RT listener, mirroring BC's start_listener method."""
        logger.info("Remote_Terminal.start_listener: Starting RT listener...")
        
        # Start RT_Listener socket thread
        thread_manager = ThreadManager()
        thread_manager.add_thread("RT Listening", target=self.rt_listener.start_listening)
        thread_manager.start_thread("RT Listening")
        
        # Start frame processing thread
        self.listening = True
        thread_manager.add_thread("RT Listener", target=self.process_frames_loop)
        thread_manager.start_thread("RT Listener")
        
        logger.info("Remote_Terminal.start_listener: All threads started")

    def stop_listener(self):
        """Stop RT listener, mirroring BC's stop_listener method."""
        logger.info("Remote_Terminal.stop_listener: Stopping listener...")
        self.stop_event.set()
        self.listening = False

        # This only stops the "RT Listener" thread (process_frames_loop,
        # gated on self.listening/self.stop_event above). It does NOT stop
        # the separate "RT Listening" thread, which runs self.rt_listener's
        # own start_listening() -- that object has its own independent
        # self.running flag, set via RT_Listener.stop_listening(), and
        # nothing was ever calling it (mirrors the identical gap found and
        # fixed in Bus_Controller.stop_listener() -- see BC.py). Confirmed
        # live this method itself was never called anywhere in the
        # codebase, so neither RT thread ever received a stop signal.
        if self.rt_listener is not None:
            self.rt_listener.stop_listening()

        # Close event loop if it exists
        if self._event_loop is not None:
            self._event_loop.close()
            self._event_loop = None
            logger.info("Closed event loop")
            
        logger.info("Remote_Terminal.stop_listener: Listener stopped")



    def _handle_block_transfer_data(self, frame):
        """
        Handle block transfer data messages.
        
        Args:
            frame: The frame containing block transfer data
        """
        try:
            logger.info(f"[RT] Handling block transfer data: {frame}")
            
            # Extract necessary information
            request_id = frame.get('request_id')
            if not request_id:
                logger.error("[RT] Block transfer data missing request_id")
                return
            
            metadata = frame.get('metadata', {})
            frames = frame.get('frames', [])
            
            # Extract sequence_number, total_sequences, and is_final
            sequence_number = frame.get('sequence_number')
            total_sequences = frame.get('total_sequences')
            is_final = frame.get('is_final', False)
            
            if metadata:
                if sequence_number is None and 'sequence_number' in metadata:
                    sequence_number = metadata['sequence_number']
                if total_sequences is None and 'total_sequences' in metadata:
                    total_sequences = metadata['total_sequences']
                if not is_final and 'is_final' in metadata:
                    is_final = metadata['is_final']
            
            # If still not found and frames are available, try to extract from frames
            if (sequence_number is None or total_sequences is None) and len(frames) >= 3:
                # In a block transfer data message, frames[1] = sequence_number, frames[2] = total_sequences
                if sequence_number is None and frames[1]:
                    # Extract 16 data bits (bits 3-18) from the 20-bit word
                    data_bits = frames[1][3:19]
                    try:
                        sequence_number = int(data_bits, 2)
                        logger.info(f"[RT] Extracted sequence_number from frame: {sequence_number}")
                    except ValueError:
                        logger.error(f"[RT] Invalid sequence_number format: {data_bits}")
                
                if total_sequences is None and frames[2]:
                    # Extract 16 data bits (bits 3-18) from the 20-bit word
                    data_bits = frames[2][3:19]
                    try:
                        total_sequences = int(data_bits, 2)
                        logger.info(f"[RT] Extracted total_sequences from frame: {total_sequences}")
                    except ValueError:
                        logger.error(f"[RT] Invalid total_sequences format: {data_bits}")
            
            if sequence_number is None:
                logger.warning("[RT] Missing sequence_number in block transfer data")
                sequence_number = 1  # Default to 1 if not specified
            
            if total_sequences is None:
                logger.warning("[RT] Missing total_sequences in block transfer data")
                total_sequences = 1  # Default to 1 if not specified
            
            # Check if we have a block transfer state for this request_id
            with self._block_transfer_lock:
                if request_id not in self._block_transfer_state:
                    logger.warning(f"[RT] No block transfer state found for request_id {request_id}")
                    # Create a new state with available information
                    self._block_transfer_state[request_id] = {
                        'total_messages': total_sequences,
                        'total_frames': 0,
                        'received_messages': 0,
                        'received_frames': 0,
                        'data_buffer': [],
                        'timestamp': time.time(),
                        'message_type': metadata.get('message_type') if metadata else None,
                        'command_type': metadata.get('command_type') if metadata else None,
                        'command_name': metadata.get('command_name') if metadata else None,
                        'metadata': metadata,
                        'complete': False
                    }
                    logger.info(f"[RT] Created new block transfer state for request_id {request_id}")
                
                # Get the state
                state = self._block_transfer_state[request_id]
                
                # Update state
                state['received_messages'] += 1
                state['timestamp'] = time.time()
                
                # Extract data from frames (skip the first 3 frames: status word, sequence_number, total_sequences)
                if len(frames) > 3:
                    data_frames = frames[3:]
                    state['data_buffer'].extend(data_frames)
                    state['received_frames'] += len(data_frames)
                    logger.info(f"[RT] Added {len(data_frames)} data frames to buffer for request_id {request_id}")
                
                # Check if this is the final message or if we've received all messages
                if is_final or state['received_messages'] >= state['total_messages']:
                    state['complete'] = True
                    logger.info(f"[RT] Block transfer complete for request_id {request_id}")
                    
                    # Create and process the complete message
                    self._process_complete_block_transfer(request_id)
                    
                    # Remove the state
                    del self._block_transfer_state[request_id]
                    logger.info(f"[RT] Removed block transfer state for request_id {request_id}")
                else:
                    # Send acknowledgment for this message
                    rt_address = frame.get('rt_address')
                    if not rt_address and metadata:
                        rt_address = metadata.get('rt_address')
                    if not rt_address:
                        rt_address = 9  # Default to radar system
                    
                    # Construct a status word for acknowledgment
                    status_word = self.rt_construct.construct_status_word(rt_address)
                    
                    # Create acknowledgment message
                    ack_message = {
                        'status_word': status_word,
                        'request_id': request_id,
                        'timestamp': time.time(),
                        'command_type': 'transfer_data_ack',
                        'message_type': state['message_type'],
                        'command_name': state['command_name'],
                        'metadata': {
                            'is_transfer_data_ack': True,
                            'sequence_number': sequence_number,
                            'total_sequences': total_sequences,
                            'received_messages': state['received_messages'],
                            'total_messages': state['total_messages']
                        }
                    }
                    
                    # Send acknowledgment
                    self.send_message(ack_message)
                    logger.info(f"[RT] Sent acknowledgment for block transfer data: {request_id}, sequence {sequence_number}/{total_sequences}")
                
        except Exception as e:
            logger.error(f"[RT] Error handling block transfer data: {str(e)}")
            logger.error(traceback.format_exc())

    def _handle_block_transfer_complete(self, frame):
        """
        Handle block transfer completion messages.
        
        Args:
            frame: The frame containing block transfer completion information
        """
        try:
            logger.info(f"[RT] Handling block transfer completion: {frame}")
            
            # Extract necessary information
            request_id = frame.get('request_id')
            if not request_id:
                logger.error("[RT] Block transfer completion missing request_id")
                return
            
            # Check if we have a block transfer state for this request_id
            with self._block_transfer_lock:
                if request_id not in self._block_transfer_state:
                    logger.warning(f"[RT] No block transfer state found for request_id {request_id}")
                    return
                
                # Get the state
                state = self._block_transfer_state[request_id]
                
                # Mark as complete
                state['complete'] = True
                logger.info(f"[RT] Marked block transfer as complete for request_id {request_id}")
                
                # Create and process the complete message
                self._process_complete_block_transfer(request_id)
                
                # Remove the state
                del self._block_transfer_state[request_id]
                logger.info(f"[RT] Removed block transfer state for request_id {request_id}")
                
                # Send acknowledgment
                metadata = frame.get('metadata', {})
                rt_address = frame.get('rt_address')
                if not rt_address and metadata:
                    rt_address = metadata.get('rt_address')
                if not rt_address:
                    rt_address = 9  # Default to radar system
                
                # Construct a status word for acknowledgment
                status_word = self.rt_construct.construct_status_word(rt_address)
                
                # Create acknowledgment message
                ack_message = {
                    'status_word': status_word,
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'command_type': 'transfer_complete_ack',
                    'message_type': state.get('message_type'),
                    'command_name': state.get('command_name'),
                    'metadata': {
                        'is_transfer_complete_ack': True,
                        'status': 'success'
                    }
                }
                
                # Send acknowledgment
                self.send_message(ack_message)
                logger.info(f"[RT] Sent acknowledgment for block transfer completion: {request_id}")
                
        except Exception as e:
            logger.error(f"[RT] Error handling block transfer completion: {str(e)}")
            logger.error(traceback.format_exc())


    def get_message(self, wait=False, timeout=None):
        """
        Get a processed message from the queue.
        Mirrors BC's get_message method for consistent behavior.
        
        Args:
            wait (bool): Whether to wait for a message if none is available
            timeout (float): Maximum time to wait for a message, in seconds
        
        Returns:
            MIL_STD_1553B_Message or None: The next processed message, or None if none is available
        """
        # time.monotonic(), not time.time(): this loop measures ELAPSED wait
        # time, and time.time() is the wall clock, which can jump backward
        # (NTP/GPS time correction, manual clock adjustment, VM live
        # migration). Live-reproduced (round 19) by monkeypatching time.time()
        # to simulate exactly that -- a 600s backward jump immediately after
        # start_time was captured -- and calling get_message(wait=True,
        # timeout=2): the call never returned within a 15s outer deadline,
        # because (time.time() - start_time) stayed negative forever, which
        # is never > timeout, so the "Timeout exceeded" branch can never be
        # reached. A caller expecting a bounded 2-second wait hangs
        # indefinitely instead. time.monotonic() is purpose-built for
        # duration/elapsed-time measurement and is immune to this class of
        # wall-clock adjustment (Python docs explicitly recommend it over
        # time.time() for this exact use case).
        start_time = time.monotonic()
        
        while True:
            with self.message_lock:
                if self.processed_messages:
                    message = self.processed_messages.pop(0)
                    logger.info(f"[RT] Returning message from queue: {message}")
                    return message
            
            if not wait:
                logger.info("[RT] No messages available and wait=False")
                return None
                
            # Check if timeout exceeded
            if timeout is not None and (time.monotonic() - start_time) > timeout:
                logger.info(f"[RT] Timeout ({timeout}s) exceeded waiting for message")
                return None
                
            # Sleep briefly to avoid tight loop
            time.sleep(0.01)

# Get global Remote_Terminal instance
def get_Remote_Terminal():
    """Get global Remote_Terminal instance."""
    return Remote_Terminal()
