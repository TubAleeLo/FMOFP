"""
Bus Controller Socket

Handles socket communication between Bus Controller and Remote Terminal.
"""

import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import atexit
import time
import select
import FMOFP.Utils.common.fetching as fetching
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.bus_adapter import get_bus_adapter

logger = get_logger()

class BC_sender:
    def __init__(self, max_workers=5):
        self.destination_ip = "localhost"
        self.destination_port = 5001
        # Transport is now behind the bus adapter layer (bus_adapter.py) so a
        # real 1553B hardware interface can be swapped in via
        # busAdapterConfig.xml without touching this class. The default
        # SocketBusAdapter reproduces the previous inline socket code exactly
        # (destination_ip/destination_port above are kept for backwards
        # compatibility of anything that reads them; the adapter owns the
        # live values).
        self._bus_adapter = get_bus_adapter('bc')
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.is_shutting_down = False
        self.shutdown_event = threading.Event()
        self.acknowledged_requests = {}  # Track acknowledged requests
        self.acknowledged_requests_lock = threading.Lock()  # Lock for thread safety
        atexit.register(self.shutdown)
        logger.info(f"BC_sender initialized with max_workers={max_workers}")

    def BC_send_message(self, message):
        if self.is_shutting_down or self.executor._shutdown:
            logger.warning("Cannot send message, BC_sender is shutting down")
            return False
            
        logger.info(f"BC_sender submitting message to executor: {message}")
        future = self.executor.submit(self._send_message, message)
        result = future.result()
        logger.info(f"BC_send_message result: {result}")
        return result

    def _send_message(self, message):
        if self.is_shutting_down:
            logger.warning("_send_message aborting early due to shutdown")
            return False

        # Check if this is a large message that needs to be split
        if isinstance(message, dict) and 'frames' in message and isinstance(message['frames'], list):
            # Check if frames exceed MIL-STD-1553B limit (32 data words per message)
            if len(message['frames']) > 33:  # Command word + 32 data words
                logger.info(f"BC_sender detected large message with {len(message['frames'])} frames, using block transfer protocol")
                return self._send_large_message(message)

        # Extract metadata for logging but don't send it directly
        metadata = None
        request_id = None
        if isinstance(message, dict):
            metadata = message.get('metadata')
            request_id = message.get('request_id')
            if metadata:
                logger.info(f"BC_sender found metadata in message: {metadata}")
                if 'message_type' in metadata:
                    logger.info(f"BC_sender found message_type in metadata: {metadata['message_type']}")

        # Prepare the message to send
        # For dict messages, we need to extract the frames and preserve metadata
        if isinstance(message, dict) and 'frames' in message:
            # Create a new dict with just the essential fields for transmission
            transmission_dict = {
                'frames': message['frames'],
                'request_id': request_id
            }
            
            # Only include metadata fields needed for message processing
            if metadata:
                # Create a simplified metadata dict with just the essential fields
                essential_metadata = {
                    'message_type': metadata.get('message_type', ''),
                    'command_type': metadata.get('command_type', ''),
                    'command_name': metadata.get('command_name', ''),
                    # Add mode and mode_value fields to preserve them across the BC-RT boundary
                    'mode': metadata.get('mode'),
                    'mode_value': metadata.get('mode_value'),
                    # Also preserve old_mode and new_mode for mode change completion messages
                    'old_mode': metadata.get('old_mode'),
                    'new_mode': metadata.get('new_mode')
                }
                
                # Log the mode information for debugging
                if 'mode' in metadata:
                    logger.info(f"[BC_SENDER] Including mode in metadata: {metadata['mode']}")
                if 'mode_value' in metadata:
                    logger.info(f"[BC_SENDER] Including mode_value in metadata: {metadata['mode_value']}")
                
                # Add request_id if available
                if request_id:
                    essential_metadata['request_id'] = request_id
                
                transmission_dict['metadata'] = essential_metadata
            
            msg = json.dumps(transmission_dict).encode()
            logger.info(f"BC_sender sending dict message with frames and essential metadata")
        else:
            # List or single frame format
            if not isinstance(message, list):
                message = [message]
            msg = json.dumps(message).encode()
            logger.info(f"BC_sender sending frame list: {message}")
            
        logger.info(f"BC_sender encoded message: {msg}")
        
        # Delegate the actual wire transfer to the configured bus adapter
        # (socket by default — identical connect/sendall/close semantics and
        # error handling to the inline code this replaced).
        if self._bus_adapter.transmit(msg):
            logger.info(f"Message sent successfully: {message}")
            return True
        return False

    def _send_large_message(self, message):
        """
        Send a large message using MIL-STD-1553B block transfer protocol.
        
        This method implements the standard MIL-STD-1553B approach for handling large data transfers
        by breaking the data into multiple messages with proper sequencing and metadata.
        
        Args:
            message: The message to send, typically a dict with 'frames', 'request_id', and 'metadata'
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"BC_sender sending large message using block transfer protocol")
            
            # Extract frames, request_id, and metadata from message
            if not isinstance(message, dict) or 'frames' not in message:
                logger.error("Invalid message format for large message transfer")
                return False
                
            frames = message['frames']
            request_id = message.get('request_id')
            metadata = message.get('metadata', {})
            
            # Use the block transfer aggregator to detect binary data
            from FMOFP.MIL_STD_1553B.Bus_Controller.BC_transfer_aggregator import get_block_transfer_aggregator
            block_transfer_aggregator = get_block_transfer_aggregator()
            
            # Use existing methods to detect binary data
            has_binary_data = block_transfer_aggregator.is_binary_data_message(message)
            binary_data = None
            
            precipitation_data = False
            vil_data = False
            
            if has_binary_data:
                # Extract binary data using the aggregator
                binary_data = block_transfer_aggregator.extract_binary_data(message)
                logger.info(f"BC_sender detected binary data using transfer aggregator: {len(binary_data) if binary_data else 0} elements")
                
                # Check for specific types
                precipitation_data = block_transfer_aggregator._is_precipitation_message(message)
                vil_data = block_transfer_aggregator._is_vil_message(message)
                
                if precipitation_data:
                    logger.info(f"BC_sender detected precipitation data")
                if vil_data:
                    logger.info(f"BC_sender detected VIL data")
            
            # Calculate number of messages needed (max 32 data words per message)
            max_frames_per_message = 32  # MIL-STD-1553B limit
            
            # First frame is always the command word
            command_word = frames[0]
            data_frames = frames[1:]
            
            # Calculate number of messages needed
            num_messages = (len(data_frames) + max_frames_per_message - 1) // max_frames_per_message
            
            logger.info(f"BC_sender breaking large message into {num_messages} messages")
            
            # Import the BC_construct class to create properly formatted MIL-STD-1553B words
            from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
            bc_construct = BC_construct()
            
            # Send initialization message (Mode Code 17: Synchronize)
            # This message contains metadata about the transfer
            # Create properly formatted 20-bit data words with sync bits and parity
            total_messages_word = bc_construct.construct_data_word(num_messages)
            total_frames_word = bc_construct.construct_data_word(len(data_frames))
            
            # Create initialization message with metadata flags ONLY (no binary data)
            init_message = {
                'frames': [
                    command_word,  # Original command word
                    total_messages_word,  # Total number of messages in the transfer (20-bit word)
                    total_frames_word  # Total number of data frames (20-bit word)
                ],
                'request_id': request_id,
                'metadata': {
                    'message_type': metadata.get('message_type', 'block_transfer_init'),
                    'command_type': 'transfer_init',
                    'is_transfer_init': True,
                    'total_messages': num_messages,
                    'total_frames': len(data_frames),
                    'has_binary_data': has_binary_data
                }
            }
            
            # Include flags ONLY for binary data types (no actual data in init message)
            if has_binary_data:
                # Only set flags in metadata, DON'T include actual binary data
                init_message['metadata']['binary_data_expected'] = True
                
                # For correct count encoding, include item count (not buffer length)
                if binary_data is not None:
                    item_count = len(binary_data)
                    init_message['metadata']['binary_data_length'] = item_count
                
                # Add appropriate type flags (keep these flags in the metadata)
                if precipitation_data:
                    init_message['metadata']['precipitation_message'] = True
                    init_message['metadata']['data_type'] = 'precipitation'
                    
                    # Set count of precipitation objects
                    if binary_data and isinstance(binary_data, list):
                        count = len(binary_data)
                        # Include count in a standardized location - ensure it's in the 4th position (index 3)
                        from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
                        count_construct = BC_construct()
                        
                        # Ensure count is limited to the expected range (0-15)
                        count = min(15, count)  # Limit to max 15 precipitation objects
                        
                        # Ensure count is formatted consistently for the RT to interpret properly
                        # Use only lower 4 bits (0-15 range) and place them in a consistent position
                        # Format as a proper 20-bit MIL-STD-1553 data word with sync bits
                        count_word = count_construct.construct_data_word(count)
                        
                        # Ensure we have exactly 3 frames before appending count word
                        # This guarantees the count word is always at index 3 where RT expects it
                        while len(init_message['frames']) < 3:
                            # Add padding frame if needed
                            padding_word = count_construct.construct_data_word(0)
                            init_message['frames'].append(padding_word)
                            
                        # Add count word to initialization frames at exactly position 3
                        init_message['frames'].append(count_word)
                        
                        logger.info(f"BC_sender included precipitation count: {count} objects")
                        # Also add to metadata for extra redundancy
                        init_message['metadata']['precipitation_count'] = count
                    
                    logger.info(f"BC_sender included precipitation type flags in init message")
                elif vil_data:
                    init_message['metadata']['vil_message'] = True
                    init_message['metadata']['data_type'] = 'vil'
                    
                    # Set count of VIL objects
                    if binary_data and isinstance(binary_data, list):
                        count = len(binary_data)
                        # Include count in a standardized location - ensure it's in the 4th position (index 3)
                        from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct
                        count_construct = BC_construct()
                        
                        # Ensure count is limited to the expected range (0-15)
                        count = min(15, count)  # Limit to max 15 VIL objects
                        
                        # Ensure count is formatted consistently for the RT to interpret properly
                        # Use only lower 4 bits (0-15 range) and place them in a consistent position
                        # Format as a proper 20-bit MIL-STD-1553 data word with sync bits
                        count_word = count_construct.construct_data_word(count)
                        
                        # Ensure we have exactly 3 frames before appending count word
                        # This guarantees the count word is always at index 3 where RT expects it
                        while len(init_message['frames']) < 3:
                            # Add padding frame if needed
                            padding_word = count_construct.construct_data_word(0)
                            init_message['frames'].append(padding_word)
                            
                        # Add count word to initialization frames at exactly position 3
                        init_message['frames'].append(count_word)
                        
                        logger.info(f"BC_sender included VIL count: {count} objects")
                        # Also add to metadata for extra redundancy
                        init_message['metadata']['vil_count'] = count
                        
                    logger.info(f"BC_sender included VIL type flags in init message")
            
            # Check if this request has already been acknowledged
            already_acknowledged = False
            with self.acknowledged_requests_lock:
                if request_id in self.acknowledged_requests:
                    # Check if the acknowledgment is recent (within the last 5 seconds)
                    if time.time() - self.acknowledged_requests[request_id] < 5.0:
                        already_acknowledged = True
                        logger.info(f"BC_sender found recent acknowledgment for request ID: {request_id}, skipping initialization message")
            
            if not already_acknowledged:
                # Send initialization message
                init_result = self._send_message(init_message)
                if not init_result:
                    logger.error("Failed to send initialization message")
                    return False
                    
                logger.info(f"BC_sender sent transfer initialization message with request ID: {request_id}")
                
                # Wait for status word acknowledgment from RT
                # Get the BC_Listener instance
                from FMOFP.MIL_STD_1553B.Bus_Controller.BC_connect.BC_socket import get_bc_listener
                bc_listener = get_bc_listener()
                
                # Wait up to 1 second for status word acknowledgment
                max_wait_time = 1.0  # seconds
                wait_interval = 0.1  # seconds
                wait_time = 0
                status_word_received = False
                
                while wait_time < max_wait_time and not status_word_received:
                    # Check if there's a status word in the data_received queue
                    if bc_listener.data_received:
                        for i, data in enumerate(bc_listener.data_received):
                            # Check if this is a status word response for our request
                            if isinstance(data, dict) and 'status_word' in data and data.get('request_id') == request_id:
                                logger.info(f"BC_sender received status word acknowledgment for request ID: {request_id}")
                                status_word_received = True
                                # Store the acknowledgment time
                                with self.acknowledged_requests_lock:
                                    self.acknowledged_requests[request_id] = time.time()
                                # Remove the status word from the queue
                                with bc_listener._lock:
                                    bc_listener.data_received.pop(i)
                                break
                    
                    if not status_word_received:
                        time.sleep(wait_interval)
                        wait_time += wait_interval
                
                if not status_word_received:
                    logger.warning(f"BC_sender did not receive status word acknowledgment for request ID: {request_id}")
                    # Continue anyway, as the RT might have received the message but the acknowledgment was lost
            
            # Send data messages
            success = True
            for i in range(num_messages):
                # Calculate start and end indices for this chunk
                start_idx = i * max_frames_per_message
                end_idx = min((i + 1) * max_frames_per_message, len(data_frames))
                
                # Extract data chunk
                chunk = data_frames[start_idx:end_idx]
                
                # Add sequence metadata to the beginning of the chunk
                # First, create properly formatted 20-bit data words for sequence metadata
                sequence_number_word = bc_construct.construct_data_word(i + 1)  # Sequence number (1-based)
                total_messages_word = bc_construct.construct_data_word(num_messages)  # Total number of messages
                
                # Add the properly formatted sequence metadata words to the chunk
                chunk_with_metadata = [sequence_number_word, total_messages_word] + chunk
                
                # Create data message with binary data preserved
                data_message = {
                    'frames': [command_word] + chunk_with_metadata,  # Command word + chunk with metadata
                    'request_id': request_id,
                    'metadata': {
                        'message_type': metadata.get('message_type'),
                        'command_type': metadata.get('command_type'),
                        'is_transfer_data': True,
                        'sequence_number': i + 1,
                        'total_sequences': num_messages,
                        'is_final': (i == num_messages - 1),
                        'has_binary_data': has_binary_data
                    }
                }
                
                # Include binary data in data messages using the transfer aggregator
                if binary_data is not None:
                    data_message['data'] = binary_data
                    data_message['metadata']['binary_data_preserved'] = True
                    data_message['metadata']['binary_data_length'] = len(binary_data)
                    
                    # Add appropriate type flags
                    if precipitation_data:
                        data_message['metadata']['precipitation_message'] = True
                        data_message['metadata']['data_type'] = 'precipitation'
                    elif vil_data:
                        data_message['metadata']['vil_message'] = True
                        data_message['metadata']['data_type'] = 'vil'
                    
                    logger.info(f"BC_sender included binary data with {len(binary_data)} elements in data message {i+1}/{num_messages}")
                
                # Send data message
                data_result = self._send_message(data_message)
                if not data_result:
                    logger.error(f"Failed to send data message {i+1}/{num_messages}")
                    success = False
                    break
                    
                logger.info(f"BC_sender sent data message {i+1}/{num_messages} with request ID: {request_id}")
                
                # Small delay between messages to prevent overwhelming the bus
                time.sleep(0.01)
            
            # Send completion message (Mode Code 16: Transmit Vector Word)
            # This message indicates the end of the transfer
            if success:
                # Create properly formatted 20-bit data words for completion message
                total_messages_word = bc_construct.construct_data_word(num_messages)
                status_code_word = bc_construct.construct_data_word(1)  # Status code (1 = success)
                
                # Create completion message with metadata flags but NO binary data
                completion_message = {
                    'frames': [
                        command_word,  # Original command word
                        total_messages_word,  # Total number of messages sent (20-bit word)
                        status_code_word  # Status code (1 = success) (20-bit word)
                    ],
                    'request_id': request_id,
                    'metadata': {
                        'message_type': metadata.get('message_type', 'block_transfer_complete'),
                        'command_type': 'transfer_complete',
                        'is_transfer_complete': True,
                        'total_messages': num_messages,
                        'status': 'success',
                        'has_binary_data': False  # Important: set to false for completion messages
                    }
                }
                
                # Add type flags WITHOUT including the actual binary data
                if precipitation_data:
                    completion_message['metadata']['precipitation_message'] = True
                    completion_message['metadata']['data_type'] = 'precipitation'
                    logger.info(f"BC_sender included precipitation type flags in completion message (without binary data)")
                elif vil_data:
                    completion_message['metadata']['vil_message'] = True
                    completion_message['metadata']['data_type'] = 'vil'
                    logger.info(f"BC_sender included VIL type flags in completion message (without binary data)")
                
                # Send completion message
                completion_result = self._send_message(completion_message)
                if not completion_result:
                    logger.error("Failed to send completion message")
                    success = False
                else:
                    logger.info(f"BC_sender sent transfer completion message with request ID: {request_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error sending large message: {str(e)}")
            return False

    def shutdown(self):
        logger.info("BC_sender initiating shutdown")
        self.is_shutting_down = True
        logger.info("BC_sender waiting for in-progress tasks to complete")
        self.executor.shutdown(wait=True)
        logger.info("BC_sender has been shut down.")
        self.shutdown_event.set()

    def wait_for_shutdown(self):
        logger.info("BC_sender waiting for shutdown to complete")
        self.shutdown_event.wait()
        logger.info("BC_sender shutdown complete")

    def check_health(self) -> bool:
        health_status = not self.is_shutting_down and not self.executor._shutdown
        logger.info(f"BC_sender health check: {'healthy' if health_status else 'unhealthy'}")
        return health_status

class BC_Listener:
    def __init__(self):
        self.data_received = list()
        self.running = False
        self.port = 5000
        self.health_check_interval = 5  # Seconds between health checks
        self.last_activity_time = time.time()
        self.socket_variable = None
        self._lock = threading.Lock()
        logger.info(f"BC_Listener initialized on port {self.port}")

    def setup_socket(self):
        try:
            self.socket_variable = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_variable.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            logger.info(f"BC_Listener binding to port {self.port}")
            # Bound to loopback only: BC and RT always connect to each
            # other via destination_ip = "localhost" (see BC_socket.py /
            # RT_socket.py __init__), so there is no legitimate cross-host
            # use case here. Binding to all interfaces on an unauthenticated,
            # unencrypted socket that parses received frames unnecessarily
            # exposed this to any host on the network (production readiness
            # punch list, item 2).
            self.socket_variable.bind(("127.0.0.1", self.port))
            self.socket_variable.listen(5)
            self.socket_variable.setblocking(False)
            logger.info(f"BC_Listener socket set up successfully on port {self.port}")
        except Exception as e:
            logger.error(f"Error setting up BC_Listener socket: {str(e)}")
            raise

    def start_listening(self):
        self.running = True
        logger.info(f"BC_Listener starting on port {self.port}")
        self.setup_socket()

        while self.running:
            try:
                readable, _, _ = select.select([self.socket_variable], [], [], 1.0)
                if readable:
                    connection, client_address = self.socket_variable.accept()
                    logger.info(f"BC_Listener accepted connection from {client_address}")
                    connection.setblocking(False)
                    try:
                        self.handle_connection(connection, client_address)
                    finally:
                        # Defense in depth: handle_connection() already
                        # closes `connection` itself on every normal and
                        # caught-exception exit path, but if something
                        # inside it ever raised a BaseException its own
                        # broad `except Exception` doesn't catch (e.g. a
                        # SystemExit/KeyboardInterrupt landing in this
                        # background thread -- exceedingly unlikely, but
                        # not impossible), this connection would otherwise
                        # never be explicitly closed, leaking the socket
                        # until Python's GC eventually reclaims it.
                        # close() on an already-closed socket is a
                        # documented no-op, so this is always safe.
                        try:
                            connection.close()
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error in BC_Listener main loop: {str(e)}")

        self.socket_variable.close()
        logger.info("BC_Listener stopped")

    def handle_connection(self, connection, client_address):
        """Handle incoming connection from BC."""
        logger.info(f"[BC_LISTENER] Handling connection from {client_address}")
        # Accumulator for TCP stream reassembly: a single logical JSON
        # message sent via one sendall() call on the sender side can
        # legitimately arrive split across multiple recv(1024) calls here
        # -- TCP is a byte stream, not message-oriented, and makes no
        # boundary guarantees between what one sendall() writes and what
        # one recv() returns. Live-reproduced: a 2133-byte message (a
        # realistic size for a full 32-data-word MIL-STD-1553B block
        # transfer chunk plus metadata) sent in a single sendall() arrived
        # across 3 separate recv(1024) calls here; each fragment
        # independently failed json.loads() and was silently dropped
        # (logged as "Failed to parse frame data" but the actual message
        # content was lost, not reassembled or retried). Accumulate raw
        # bytes across recv() calls and only proceed to the existing
        # processing logic below once the buffer holds a complete,
        # parseable JSON message; bounded by _MAX_RECV_BUFFER_BYTES as a
        # safety valve against a truly malformed/never-terminating stream.
        recv_buffer = b""
        _MAX_RECV_BUFFER_BYTES = 10 * 1024 * 1024  # 10 MB
        while self.running:
            try:
                readable, _, _ = select.select([connection], [], [], 1.0)
                if readable:
                    data = connection.recv(1024)
                    if data:
                        recv_buffer += data
                        if len(recv_buffer) > _MAX_RECV_BUFFER_BYTES:
                            logger.error(
                                f"[BC_LISTENER] Discarding {len(recv_buffer)} buffered bytes from "
                                f"{client_address}: exceeded {_MAX_RECV_BUFFER_BYTES} bytes without "
                                f"a parseable message"
                            )
                            recv_buffer = b""
                            continue
                        try:
                            decoded_data = recv_buffer.decode()
                        except UnicodeDecodeError:
                            # A multi-byte UTF-8 character can also
                            # legitimately be split across recv() calls --
                            # wait for more bytes rather than failing.
                            continue
                        # Trial-parse: if this looks like a JSON message
                        # but isn't complete/valid yet, wait for more data
                        # on the next recv() instead of discarding it. The
                        # non-JSON "single frame format" fallback further
                        # below is unaffected -- it never reaches here
                        # since it doesn't start with '{' or '['.
                        if decoded_data.startswith('{') or decoded_data.startswith('['):
                            try:
                                json.loads(decoded_data)
                            except (ValueError, SyntaxError):
                                continue
                        # Buffer now holds one complete message (or isn't
                        # JSON-prefixed at all) -- reset before the
                        # existing processing logic below, which re-parses
                        # decoded_data itself.
                        recv_buffer = b""
                        try:
                            logger.info(f"[BC_LISTENER] Received raw data from {client_address}: {data}")
                            logger.info(f"[BC_LISTENER] Decoded data: {decoded_data}")
                            
                            try:
                                # Parse the received data
                                if decoded_data.startswith('{'):
                                    # Dict format with request_id
                                    parsed_data = json.loads(decoded_data)
                                    
                                    # Log the parsed data for debugging
                                    logger.info(f"[BC_LISTENER] Parsed data: {parsed_data}")
                                    
                                    # Check for block transfer indicators
                                    if isinstance(parsed_data, dict):
                                        # Check for block transfer indicators in both top-level and metadata
                                        metadata = parsed_data.get('metadata', {})
                                        is_transfer_init = parsed_data.get('is_transfer_init', False) or (
                                            isinstance(metadata, dict) and metadata.get('is_transfer_init', False)
                                        )
                                        is_transfer_data = parsed_data.get('is_transfer_data', False) or (
                                            isinstance(metadata, dict) and metadata.get('is_transfer_data', False)
                                        )
                                        is_transfer_complete = parsed_data.get('is_transfer_complete', False) or (
                                            isinstance(metadata, dict) and metadata.get('is_transfer_complete', False)
                                        )
                                        
                                        if is_transfer_init or is_transfer_data or is_transfer_complete:
                                            # Log block transfer detection
                                            if is_transfer_init:
                                                logger.info(f"[BC_LISTENER] Detected block transfer initialization from RT")
                                            elif is_transfer_data:
                                                # Get sequence info if available
                                                sequence_number = parsed_data.get('sequence_number') or metadata.get('sequence_number', 0)
                                                total_sequences = parsed_data.get('total_sequences') or metadata.get('total_sequences', 0)
                                                logger.info(f"[BC_LISTENER] Detected block transfer data from RT: sequence {sequence_number}/{total_sequences}")
                                            elif is_transfer_complete:
                                                logger.info(f"[BC_LISTENER] Detected block transfer completion from RT")
                                    
                                    
                                    # Check if this is a status word acknowledgment
                                    if 'status_word' in parsed_data:
                                        # Extract the status word
                                        status_word = parsed_data['status_word']
                                        
                                        # Clean the status word to ensure it's only 0s and 1s
                                        status_word = ''.join(filter(lambda x: x in '01', status_word))
                                        
                                        # Validate status word format
                                        if len(status_word) != 20:
                                            logger.error(f"[BC_LISTENER] Invalid status word length after cleaning: {len(status_word)} bits")
                                            continue
                                            
                                        # Validate sync bits
                                        if not status_word.startswith('100'):
                                            logger.error(f"[BC_LISTENER] Invalid sync bits in status word: {status_word[:3]}")
                                            continue
                                            
                                        # Log the cleaned status word
                                        logger.info(f"[BC_LISTENER] Cleaned status word: {status_word}")
                                        logger.info(f"[BC_LISTENER] Status word details:")
                                        logger.info(f"[BC_LISTENER]   - Sync bits: {status_word[:3]}")
                                        logger.info(f"[BC_LISTENER]   - RT address: {status_word[3:8]}")
                                        logger.info(f"[BC_LISTENER]   - Message bit: {status_word[8:9]}")
                                        logger.info(f"[BC_LISTENER]   - Reserved bits: {status_word[9:12]}")
                                        logger.info(f"[BC_LISTENER]   - Subaddress: {status_word[12:17]}")
                                        logger.info(f"[BC_LISTENER]   - Word count: {status_word[17:]}")
                                            
                                        # Extract request_id and other essential fields
                                        request_id = parsed_data.get('request_id')
                                        command_type = parsed_data.get('command_type')
                                        message_type = parsed_data.get('message_type')
                                        command_name = parsed_data.get('command_name')
                                        
                                        # Log the message details
                                        logger.info(f"[BC_LISTENER] Message details:")
                                        logger.info(f"[BC_LISTENER]   - Request ID: {request_id}")
                                        logger.info(f"[BC_LISTENER]   - Command type: {command_type}")
                                        logger.info(f"[BC_LISTENER]   - Message type: {message_type}")
                                        logger.info(f"[BC_LISTENER]   - Command name: {command_name}")
                                        
                                        # Create enhanced status message with ALL transfer-related fields preserved
                                        status_message = {
                                            'status_word': status_word,
                                            'request_id': request_id,
                                            'timestamp': parsed_data.get('timestamp', time.time())
                                        }
                                        
                                        # Copy ALL block transfer flags and metadata
                                        transfer_fields = [
                                            'is_transfer_init', 'is_transfer_data', 'is_transfer_complete',
                                            'sequence_number', 'total_sequences', 'is_final', 'data'
                                        ]
                                        
                                        # Copy all transfer fields from both top-level and metadata
                                        for field in transfer_fields:
                                            # Check top level first, then metadata
                                            if field in parsed_data:
                                                status_message[field] = parsed_data[field]
                                                logger.info(f"[BC_LISTENER] Preserved {field} from top level: {parsed_data[field]}")
                                            elif 'metadata' in parsed_data and parsed_data['metadata'] and field in parsed_data['metadata']:
                                                status_message[field] = parsed_data['metadata'][field]
                                                logger.info(f"[BC_LISTENER] Preserved {field} from metadata: {parsed_data['metadata'][field]}")
                                        
                                        # Preserve additional fields to maintain consistency
                                        if 'command_type' in parsed_data:
                                            status_message['command_type'] = parsed_data['command_type']
                                        if 'message_type' in parsed_data:
                                            status_message['message_type'] = parsed_data['message_type']
                                        if 'command_name' in parsed_data:
                                            status_message['command_name'] = parsed_data['command_name']
                                        
                                        # Preserve entire metadata structure if available
                                        if 'metadata' in parsed_data and parsed_data['metadata']:
                                            status_message['metadata'] = parsed_data['metadata']
                                            logger.info(f"[BC_LISTENER] Including metadata: {parsed_data['metadata']}")
                                            
                                            # Log mode information for debugging
                                            if 'mode' in parsed_data['metadata']:
                                                logger.info(f"[BC_LISTENER] Found mode in metadata: {parsed_data['metadata']['mode']}")
                                            if 'mode_value' in parsed_data['metadata']:
                                                logger.info(f"[BC_LISTENER] Found mode_value in metadata: {parsed_data['metadata']['mode_value']}")
                                        
                                        # Ensure consistency between top-level and metadata fields
                                        # to prevent UniversalMessageExtractor conflicts
                                        if 'metadata' in status_message and status_message['metadata']:
                                            # List of fields that must be consistent
                                            critical_transfer_fields = [
                                                'sequence_number', 
                                                'total_sequences', 
                                                'is_final',
                                                'is_transfer_init',
                                                'is_transfer_data', 
                                                'is_transfer_complete'
                                            ]
                                            
                                            for field in critical_transfer_fields:
                                                # Synchronize top-level and metadata fields using metadata as authority
                                                if field in status_message['metadata']:
                                                    # Log the synchronization if values differ
                                                    if field in status_message and status_message[field] != status_message['metadata'][field]:
                                                        logger.info(f"[BC_LISTENER] Synchronizing {field} from metadata: " 
                                                                  f"{status_message[field]} → {status_message['metadata'][field]}")
                                                        
                                                    # Always use metadata value as authoritative
                                                    status_message[field] = status_message['metadata'][field]
                                                
                                                # If field only exists at top level, copy to metadata for consistency
                                                elif field in status_message:
                                                    logger.info(f"[BC_LISTENER] Copying {field} to metadata: {status_message[field]}")
                                                    status_message['metadata'][field] = status_message[field]
                                            
                                        # Now store the synchronized message
                                        with self._lock:
                                            self.data_received.append(status_message)
                                            
                                        # Log the status word acknowledgment
                                        logger.info(f"[BC_LISTENER] Stored status word acknowledgment with request_id: {request_id}")
                                        logger.info(f"[BC_LISTENER] Stored valid frame, total frames: {len(self.data_received)}")
                                        
                                        # Log message flow trace
                                        logger.info(f"[BC_LISTENER] Message flow trace: RT_sender -> BC_Listener -> Bus_Controller")
                                        
                                        # Log mode change event
                                        if command_type == 'mode_change_completion':
                                            logger.info(f"[BC_LISTENER] Mode change completion message received with request_id: {request_id}")
                                            if 'metadata' in parsed_data and parsed_data['metadata']:
                                                old_mode = parsed_data['metadata'].get('old_mode')
                                                new_mode = parsed_data['metadata'].get('new_mode')
                                                if old_mode and new_mode:
                                                    logger.info(f"[BC_LISTENER] Mode change: {old_mode} -> {new_mode}")
                                        
                                        continue
                                        
                                    frames = parsed_data.get('frames', [])
                                    request_id = parsed_data.get('request_id')
                                elif decoded_data.startswith('['):
                                    # List format (backwards compatibility)
                                    frames = json.loads(decoded_data)
                                    request_id = None
                                else:
                                    # Single frame format
                                    frames = [decoded_data]
                                    request_id = None
                                
                                # Validate frames
                                valid_frames = []
                                for frame in frames:
                                    if len(frame) != 20:
                                        logger.error(f"Invalid frame size: {len(frame)} bits")
                                        continue
                                        
                                    # Check sync pattern
                                    sync_bits = frame[:3]
                                    if sync_bits in ['100', '001']:
                                        valid_frames.append(frame)
                                        logger.info(f"Valid sync bits ({sync_bits}) found in word: {frame}")
                                    else:
                                        logger.warning(f"Invalid sync pattern: {sync_bits}")
                                
                                            # Store valid frames with request_id and command_name if available
                                if valid_frames:
                                    with self._lock:
                                        if request_id:
                                            # Create message with frames and request_id
                                            message = {
                                                'frames': valid_frames,
                                                'request_id': request_id
                                            }
                                            
                                            # Add metadata if available in parsed_data
                                            if isinstance(parsed_data, dict):
                                                # Add command_name if available
                                                if 'command_name' in parsed_data:
                                                    message['command_name'] = parsed_data['command_name']
                                                    logger.info(f"BC_Listener preserved command_name: {parsed_data['command_name']}")
                                                
                                                # Copy transfer flags from top level of parsed_data
                                                for flag in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']:
                                                    if flag in parsed_data:
                                                        message[flag] = parsed_data[flag]
                                                        logger.info(f"BC_Listener preserved top-level flag {flag}: {parsed_data[flag]}")
                                                
                                                # Add metadata if available
                                                if 'metadata' in parsed_data:
                                                    message['metadata'] = parsed_data['metadata']
                                                    logger.info(f"BC_Listener preserved metadata: {parsed_data['metadata']}")
                                                    
                                                    # Ensures consistent behavior even if only metadata contains the flags
                                                    if isinstance(parsed_data['metadata'], dict):
                                                        for flag in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']:
                                                            if flag in parsed_data['metadata'] and flag not in message:
                                                                message[flag] = parsed_data['metadata'][flag]
                                                                logger.info(f"BC_Listener copied metadata flag {flag} to top level: {parsed_data['metadata'][flag]}")
                                                
                                            self.data_received.append(message)
                                        else:
                                            self.data_received.append(valid_frames)
                                    logger.info(f"BC_Listener stored valid frame, total frames: {len(self.data_received)}")
                                
                            except (ValueError, SyntaxError) as e:
                                logger.error(f"Failed to parse frame data: {e}")
                                
                            self.last_activity_time = time.time()
                            
                        except UnicodeDecodeError as e:
                            logger.error(f"Failed to decode received data: {e}")
                            logger.info(f"Raw data (hex): {data.hex()}")
                    else:
                        logger.warning(f"Connection closed by {client_address}")
                        break
            except Exception as e:
                logger.error(f"Error handling connection from {client_address}: {str(e)}")
                break
        connection.close()
        logger.info(f"Connection closed with {client_address}")

    def stop_listening(self):
        logger.info("BC_Listener stopping...")
        self.running = False

    def health_monitor(self):
        while self.running:
            time.sleep(self.health_check_interval)
            current_time = time.time()
            idle_time = current_time - self.last_activity_time
            logger.info(f"BC_Listener health check - Idle time: {idle_time:.2f}s")
            if idle_time > 60:
                logger.warning("No activity detected in the last interval")
            else:
                logger.debug("Health check: BC_Listener is active")

    def is_healthy(self) -> bool:
        health_status = self.running and (time.time() - self.last_activity_time) < 60
        logger.info(f"BC_Listener health status: {'healthy' if health_status else 'unhealthy'}")
        return health_status
    
    def check_health(self) -> bool:
        health_status = self.running
        logger.info(f"BC_Listener running status: {'running' if health_status else 'stopped'}")
        return health_status

# Global instances
bc_sender = BC_sender()
bc_listener = BC_Listener()

def get_bc_sender():
    logger.info("Getting BC_sender instance")
    return bc_sender

def get_bc_listener():
    logger.info("Getting BC_Listener instance")
    return bc_listener
