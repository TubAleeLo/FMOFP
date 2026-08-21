"""
Block Transfer Aggregator

Handles the collection and aggregation of 1553B block transfer messages.
Ensures correct message type preservation and data integrity.
Enhanced to properly handle precipitation data and binary data arrays.
"""

import time
import logging
import copy
from typing import Dict, List, Optional, Any, Tuple

# Get the same logger as the BC
from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

class BlockTransferAggregator:
    def __init__(self):
        self.pending_transfers = {}  # request_id -> transfer state
        self.transfer_timeouts = {}  # request_id -> expiration time
        self.TRANSFER_TIMEOUT = 5.0  # Seconds to wait for a complete transfer
        self.last_cleanup = time.time()
        
    def is_transfer_message(self, message: Dict[str, Any]) -> bool:
        """Determine if a message is part of a block transfer."""
        if not isinstance(message, dict):
            return False
        
        # Log message details for debugging
        request_id = message.get('request_id', 'unknown')
        logger.info(f"[BC_TRANSFER_AGG] Checking if message with ID {request_id} is a transfer message")
            
        # Check direct transfer flags
        if any(key in message and message[key] for key in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']):
            flag_names = [k for k in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete'] if k in message and message[k]]
            logger.info(f"[BC_TRANSFER_AGG] Message has transfer flags: {flag_names}")
            return True
            
        # Check metadata transfer flags
        metadata = message.get('metadata', {})
        if isinstance(metadata, dict) and any(key in metadata and metadata[key] for key in 
                ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']):
            flag_names = [k for k in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete'] 
                          if k in metadata and metadata[k]]
            logger.info(f"[BC_TRANSFER_AGG] Message metadata has transfer flags: {flag_names}")
            return True

        # Enhanced detection for other fields related to block transfers
        if 'frames' in message and len(message.get('frames', [])) > 0:
            logger.info(f"[BC_TRANSFER_AGG] Message contains frames list with {len(message['frames'])} frames")
            return True
            
        logger.info(f"[BC_TRANSFER_AGG] Message is NOT a transfer message")
        return False
        
    def _get_transfer_flags(self, message: Dict[str, Any]) -> Tuple[bool, bool, bool]:
        """Extract all transfer flags from a message."""
        is_init = False
        is_data = False 
        is_complete = False
        
        # Check direct flags
        is_init = message.get('is_transfer_init', False)
        is_data = message.get('is_transfer_data', False)
        is_complete = message.get('is_transfer_complete', False)
        
        # Check metadata flags
        metadata = message.get('metadata', {})
        if isinstance(metadata, dict):
            is_init = is_init or metadata.get('is_transfer_init', False)
            is_data = is_data or metadata.get('is_transfer_data', False)
            is_complete = is_complete or metadata.get('is_transfer_complete', False)
            
        return is_init, is_data, is_complete
        
    def register_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Register a message as part of a block transfer.
        
        Returns:
          - None if the transfer is still in progress
          - The complete aggregated message if the transfer is now complete
        """
        # Clean up expired transfers periodically
        current_time = time.time()
        if current_time - self.last_cleanup > 10.0:
            self._cleanup_expired_transfers()
            self.last_cleanup = current_time
        
        # Extract the request ID
        request_id = message.get('request_id')
        if not request_id:
            logger.error("[BC_TRANSFER_AGG] Cannot handle transfer message without request_id")
            return message  # Return original message if no request_id
        
        # Get transfer flags
        is_init, is_data, is_complete = self._get_transfer_flags(message)
        
        # Log current transfer state
        logger.info(f"[BC_TRANSFER_AGG] Processing message for request_id {request_id}: init={is_init}, data={is_data}, complete={is_complete}")
        if request_id in self.pending_transfers:
            transfer = self.pending_transfers[request_id]
            has_init = transfer['init_message'] is not None
            data_count = len(transfer['data_messages'])
            has_complete = transfer['complete_message'] is not None
            logger.info(f"[BC_TRANSFER_AGG] Current transfer state: has_init={has_init}, data_count={data_count}, has_complete={has_complete}")
        
        # Handle initialization message
        if is_init:
            logger.info(f"[BC_TRANSFER_AGG] Starting new block transfer for request_id: {request_id}")
            # Clear any existing transfer with this ID
            if request_id in self.pending_transfers:
                logger.warning(f"[BC_TRANSFER_AGG] Replacing existing transfer for request_id: {request_id}")
                
            # Initialize the transfer state
            self.pending_transfers[request_id] = {
                'init_message': message.copy(),
                'data_messages': [],
                'complete_message': None,
                'start_time': time.time(),
                'metadata': self._extract_metadata(message),
                'original_message_type': self._extract_message_type(message),
                'original_command_type': self._extract_command_type(message)
            }
            
            # Set transfer timeout
            self.transfer_timeouts[request_id] = time.time() + self.TRANSFER_TIMEOUT
            return None  # Transfer just starting

        # Handle data message
        elif is_data:
            # Handle case where we get data before init
            if request_id not in self.pending_transfers:
                logger.warning(f"[BC_TRANSFER_AGG] Received data for unknown transfer: {request_id}, creating new entry")
                
                # Extract critical type information first
                original_message_type = self._extract_message_type(message)
                original_command_type = self._extract_command_type(message)
                
                # For precipitation data messages, ensure we use the correct types
                if self._is_precipitation_message(message):
                    if 'precipitation' not in original_message_type.lower():
                        original_message_type = 'weather_radarPrecipitationResponse'
                    if 'precipitation' not in original_command_type.lower():
                        original_command_type = 'precipitation_data'
                    logger.info(f"[BC_TRANSFER_AGG] Corrected precipitation message types to {original_message_type}/{original_command_type}")
                    
                # Auto-create transfer entry if it doesn't exist
                self.pending_transfers[request_id] = {
                    'init_message': None,
                    'data_messages': [],
                    'complete_message': None,
                    'start_time': time.time(),
                    'metadata': self._extract_metadata(message),
                    'original_message_type': original_message_type,
                    'original_command_type': original_command_type
                }
                self.transfer_timeouts[request_id] = time.time() + self.TRANSFER_TIMEOUT
                
            # Add to existing transfer
            self.pending_transfers[request_id]['data_messages'].append(message.copy())
            
            # Update timeout
            self.transfer_timeouts[request_id] = time.time() + self.TRANSFER_TIMEOUT
            
            # Enhanced data message detection
            is_final = False
            if message.get('is_final', False) or message.get('metadata', {}).get('is_final', False):
                is_final = True
            
            # Check for sequence number indicators
            sequence_number = message.get('sequence_number', 0)
            total_sequences = message.get('total_sequences', 0)
            if message.get('metadata', {}).get('sequence_number'):
                sequence_number = message['metadata']['sequence_number']
            if message.get('metadata', {}).get('total_sequences'):
                total_sequences = message['metadata']['total_sequences']
            
            # If we have sequence numbers and this is the last one, treat as final
            if total_sequences > 0 and sequence_number == total_sequences:
                is_final = True
                logger.info(f"[BC_TRANSFER_AGG] Message is final based on sequence number: {sequence_number}/{total_sequences}")
            
            if is_final:
                logger.info(f"[BC_TRANSFER_AGG] Final data block received for request_id: {request_id}")
                return self._finalize_transfer(request_id)
                
            # Count data messages and provide status
            data_count = len(self.pending_transfers[request_id]['data_messages'])
            logger.info(f"[BC_TRANSFER_AGG] Added data message {data_count} for request_id: {request_id}, waiting for more data")
            return None  # Still collecting data
            
        # Handle completion message
        elif is_complete:
            # If we don't have a pending transfer but we do have data in the completion message, use it
            if request_id not in self.pending_transfers:
                logger.warning(f"[BC_TRANSFER_AGG] Received completion for unknown transfer: {request_id}")
                
                # Check if the completion message has data we can use
                if 'data' in message and isinstance(message['data'], list) and len(message['data']) > 0:
                    logger.info(f"[BC_TRANSFER_AGG] Completion message contains {len(message['data'])} data items")
                    
                    # Extract critical type information first
                    original_message_type = self._extract_message_type(message)
                    original_command_type = self._extract_command_type(message)
                    
                    # Create a transfer with just this message (to ensure proper processing)
                    self.pending_transfers[request_id] = {
                        'init_message': None,
                        'data_messages': [message.copy()],
                        'complete_message': message.copy(),
                        'start_time': time.time(),
                        'metadata': self._extract_metadata(message),
                        'original_message_type': original_message_type,
                        'original_command_type': original_command_type  
                    }
                    
                    # Process it immediately
                    return self._finalize_transfer(request_id)
                
                # Otherwise, just pass through
                return message
                
            # Store completion message
            self.pending_transfers[request_id]['complete_message'] = message.copy()
            
            # Finalize and return the complete message
            return self._finalize_transfer(request_id)
            
        # Check if this is a message with frames list (common pattern)
        elif isinstance(message, dict) and 'frames' in message and isinstance(message['frames'], list):
            logger.info(f"[BC_TRANSFER_AGG] Message has frames list with {len(message['frames'])} frames")
            
            # Handle as a data message
            if request_id not in self.pending_transfers:
                logger.warning(f"[BC_TRANSFER_AGG] Creating new transfer for message with frames: {request_id}")
                
                # Extract critical type information first
                original_message_type = self._extract_message_type(message)
                original_command_type = self._extract_command_type(message)
                
                # Create transfer entry
                self.pending_transfers[request_id] = {
                    'init_message': None, 
                    'data_messages': [message.copy()],
                    'complete_message': None,
                    'start_time': time.time(),
                    'metadata': self._extract_metadata(message),
                    'original_message_type': original_message_type,
                    'original_command_type': original_command_type
                }
                self.transfer_timeouts[request_id] = time.time() + self.TRANSFER_TIMEOUT
            else:
                # Add to existing transfer
                self.pending_transfers[request_id]['data_messages'].append(message.copy())
            
            # Look for data in any message with the same request_id
            # This handles the case where precipitation data comes in two messages: one with frames, another with data
            is_complete = False
            
            # Check if there's a message with the same request_id that has data in it
            if 'data' in message and isinstance(message['data'], list) and len(message['data']) > 0:
                logger.info(f"[BC_TRANSFER_AGG] Message contains actual data array with {len(message['data'])} items")
                is_complete = True
                
            # Check if we already have a complete message based on all collected messages
            for existing_msg in self.pending_transfers[request_id]['data_messages']:
                if 'data' in existing_msg and isinstance(existing_msg['data'], list) and len(existing_msg['data']) > 0:
                    logger.info(f"[BC_TRANSFER_AGG] Found existing message with {len(existing_msg['data'])} data items")
                    is_complete = True
                    break
                    
            # If we have more than one message for this request_id, we likely have all required data
            if len(self.pending_transfers[request_id]['data_messages']) > 1:
                logger.info(f"[BC_TRANSFER_AGG] Multiple messages ({len(self.pending_transfers[request_id]['data_messages'])}) collected for same request_id, treating as complete")
                is_complete = True
            
            # If any condition indicates completeness, finalize the transfer
            if is_complete:
                logger.info(f"[BC_TRANSFER_AGG] Transfer considered complete based on data presence or multiple messages")
                return self._finalize_transfer(request_id)
            
            # Otherwise, keep collecting
            return None
            
        # Not a transfer message we recognize
        logger.info(f"[BC_TRANSFER_AGG] Message has no recognized transfer flags - passing through")
        return message  # Pass through unchanged
        
    def _finalize_transfer(self, request_id: str) -> Dict[str, Any]:
        """Finalize a block transfer and create the aggregated message."""
        if request_id not in self.pending_transfers:
            logger.error(f"[BC_TRANSFER_AGG] Cannot finalize non-existent transfer: {request_id}")
            return None
            
        transfer = self.pending_transfers[request_id]
        
        # Create the aggregated message
        result = {}
        
        # Start with the init message as base if available
        base_message = None
        if transfer['init_message']:
            base_message = transfer['init_message']
            logger.info(f"[BC_TRANSFER_AGG] Using init message as base for request_id: {request_id}")
        elif transfer['data_messages']:
            # Use the first data message as base
            base_message = transfer['data_messages'][0]
            logger.info(f"[BC_TRANSFER_AGG] Using first data message as base for request_id: {request_id}")
        else:
            logger.error(f"[BC_TRANSFER_AGG] Cannot finalize transfer with no messages: {request_id}")
            return None
            
        # Update result with base message
        result.update(base_message)
            
        # Ensure critical metadata is preserved
        original_message_type = transfer['original_message_type']
        original_command_type = transfer['original_command_type']

        # Detect precipitation data using enhanced method
        precipitation_detected = False
        
        # Special handling for precipitation data based on message types
        if ('precipitation' in original_message_type.lower() or 
            self._is_precipitation_message(base_message)):
            precipitation_detected = True
            logger.info(f"[BC_TRANSFER_AGG] Detected precipitation data from message types")
        
        # precipitation detection based on frames analysis
        if not precipitation_detected and transfer['data_messages']:
            # Check for large frame count in messages
            for msg in transfer['data_messages']:
                if 'frames' in msg and isinstance(msg['frames'], list) and len(msg['frames']) > 20:
                    precipitation_detected = True
                    logger.info(f"[BC_TRANSFER_AGG] Detected precipitation data from large frame count: {len(msg['frames'])}")
                    break
        
        # Force correct message types for precipitation data
        if precipitation_detected:
            logger.info(f"[BC_TRANSFER_AGG] Ensuring precipitation message types are correctly set")
            
            # Always set the correct message type for precipitation data
            # Completely override any message type that might contain 'completion'
            original_message_type = 'weather_radarPrecipitationResponse'
            logger.info(f"[BC_TRANSFER_AGG] Set precipitation message type to: {original_message_type}")
            
            # Always set the correct command type for precipitation data
            # Completely override any command type that might contain 'completion'
            original_command_type = 'precipitation_data'
            logger.info(f"[BC_TRANSFER_AGG] Set precipitation command type to: {original_command_type}")
                
                
        ## Check for VIL data in the message type
        vil_detected = False
        
        # Only check for VIL data if this is NOT a precipitation message
        if not precipitation_detected:
            if ('vil' in original_message_type.lower() or
                self._is_vil_message(base_message)):
                vil_detected = True
                logger.info(f"[BC_TRANSFER_AGG] Detected VIL data from message types")
            
            if not vil_detected and transfer['data_messages']:
                # Check for large frame count in messages
                for msg in transfer['data_messages']:
                    if 'frames' in msg and isinstance(msg['frames'], list) and len(msg['frames']) > 20:
                        vil_detected = True
                        logger.info(f"[BC_TRANSFER_AGG] Detected VIL data from large frame count: {len(msg['frames'])}")
                        break

            if vil_detected:
                logger.info(f"[BC_TRANSFER_AGG] Ensuring VIL message types are correctly set")
                
                # Always set the correct message type for VIL data
                # Completely override any message type that might contain 'completion'
                original_message_type = 'weather_radarVILResponse'
                logger.info(f"[BC_TRANSFER_AGG] Set VIL message type to: {original_message_type}")
                
                # Always set the correct command type for VIL data
                # Completely override any command type that might contain 'completion'
                original_command_type = 'vil_data'
                logger.info(f"[BC_TRANSFER_AGG] Set VIL command type to: {original_command_type}")
                
        # Set the message and command types
        result['message_type'] = original_message_type
        result['command_type'] = original_command_type
        
        # Enhanced command name preservation
        command_name = None
        
        # Try to find command name from all available sources
        for source in ([base_message] + transfer['data_messages'] + 
                      ([transfer['init_message']] if transfer['init_message'] else []) +
                      ([transfer['complete_message']] if transfer['complete_message'] else [])):
            if source and 'command_name' in source and source['command_name']:
                command_name = source['command_name']
                logger.info(f"[BC_TRANSFER_AGG] Found command_name: {command_name}")
                break
                
        # Default command names for special message types
        if precipitation_detected and (not command_name or command_name == 'NONE'):
            command_name = 'DISPLAY_PRECIPITATION_DATA'
            logger.info(f"[BC_TRANSFER_AGG] Set default command_name for precipitation: {command_name}")
            
        # Set command name if found
        if command_name:
            result['command_name'] = command_name
                
        # Create consolidated metadata
        if 'metadata' not in result:
            result['metadata'] = {}
            
        result['metadata'].update(transfer['metadata'])
        
        # Add special flags for our aggregated message
        result['metadata']['aggregated_block_transfer'] = True
        result['metadata']['aggregation_timestamp'] = time.time()
        result['metadata']['message_type'] = original_message_type
        result['metadata']['command_type'] = original_command_type
        
        # Ensure command_name is also in metadata
        if command_name:
            result['metadata']['command_name'] = command_name
        
        # Extract and combine data
        all_data = []
        
        # ENHANCED: First attempt to extract data from data arrays
        for data_message in transfer['data_messages']:
            if 'data' in data_message and isinstance(data_message['data'], list):
                data_items = len(data_message['data'])
                if data_items > 0:
                    logger.info(f"[BC_TRANSFER_AGG] Adding {data_items} data items from data array")
                    all_data.extend(data_message['data'])
                    
        # ENHANCED: If no data found but this is precipitation data, extract from frames
        if len(all_data) == 0 and precipitation_detected:
            logger.info(f"[BC_TRANSFER_AGG] No data found in data arrays, extracting from frames")
            frame_data = self._extract_precipitation_data_from_frames(transfer['data_messages'])
            if frame_data:
                all_data = frame_data
                logger.info(f"[BC_TRANSFER_AGG] Extracted {len(all_data)} precipitation data objects from frames")
                
        # For precipitation data, ensure it's marked correctly
        if precipitation_detected:
            # Set special flags for precipitation data
            result['metadata']['precipitation_message'] = True
            result['metadata']['precipitation_data'] = True
            result['metadata']['data_type'] = 'precipitation'
            result['metadata']['precip_data_available'] = True
        
        # Set the consolidated data
        result['data'] = all_data
        result['metadata']['data_size'] = len(all_data)
        
        # Log detailed info about the aggregated message
        logger.info(f"[BC_TRANSFER_AGG] Finalized block transfer for request_id: {request_id}")
        logger.info(f"[BC_TRANSFER_AGG] - Message type: {result['message_type']}")
        logger.info(f"[BC_TRANSFER_AGG] - Command type: {result['command_type']}")
        logger.info(f"[BC_TRANSFER_AGG] - Command name: {result.get('command_name', 'NONE')}")
        logger.info(f"[BC_TRANSFER_AGG] - Data size: {len(all_data)} items")
        
        # Clean up the transfer
        del self.pending_transfers[request_id]
        if request_id in self.transfer_timeouts:
            del self.transfer_timeouts[request_id]
            
        return result
        
    def _preprocess_frames_list(self, all_frames):
        """
        Preprocess frames list to remove extra block headers between precipitation data.
        
        In block transfer protocol, each block contains its own header frames:
        [status_word, sequence_number, total_messages, data frames...]
        
        This function identifies all block boundaries using status word pattern,
        keeps the first block's header, and removes headers from subsequent blocks
        to ensure consistent frame indexing during extraction.
        
        Args:
            all_frames: List of all frames from all blocks
            
        Returns:
            List of frames with duplicate block headers removed
        """
        # Pattern for status word: starts with '100'
        if not all_frames:
            return all_frames
        
        # 1. Identify all status word positions (block boundaries)
        status_word_indices = []
        for i, frame in enumerate(all_frames):
            if isinstance(frame, str) and frame.startswith('100'):  # Status word pattern
                status_word_indices.append(i)
                logger.debug(f"[BC_TRANSFER_AGG] Detected block boundary at index {i}: {frame}")
        
        logger.info(f"[BC_TRANSFER_AGG] Detected {len(status_word_indices)} blocks in frame list")
        
        # If no block boundaries found or just one block - return as is
        if len(status_word_indices) <= 1:
            logger.info(f"[BC_TRANSFER_AGG] No preprocessing needed - single block detected")
            return all_frames
        
        # 2. Extract frames, skipping headers in subsequent blocks
        preprocessed_frames = []
        
        # Define header size based on protocol
        header_size = 3  # status_word + seq_number + total_messages
        
        # Add first block with its header intact
        first_block_start = status_word_indices[0]  # Usually 0
        first_block_end = status_word_indices[1] if len(status_word_indices) > 1 else len(all_frames)
        preprocessed_frames.extend(all_frames[first_block_start:first_block_end])
        
        # Add subsequent blocks' frames (skipping headers in each block)
        for i in range(1, len(status_word_indices)):
            block_start = status_word_indices[i]
            block_end = status_word_indices[i+1] if i+1 < len(status_word_indices) else len(all_frames)
            
            # Skip the block header frames (status word + sequence headers)
            data_start = block_start + header_size
            if data_start < block_end:  # Ensure we have data frames in this block
                preprocessed_frames.extend(all_frames[data_start:block_end])
                logger.debug(f"[BC_TRANSFER_AGG] Added data frames {data_start}-{block_end-1} from block {i+1}")
        
        logger.info(f"[BC_TRANSFER_AGG] Preprocessing complete: {len(all_frames)} frames → {len(preprocessed_frames)} frames")
        return preprocessed_frames
    
    def _extract_precipitation_data_from_frames(self, data_messages):
        """Extract precipitation data from binary frames in 1553B messages.
        
        This method analyzes binary frames in data messages and extracts precipitation
        data according to the known encoding format:
        - The first few frames contain header information (status word, message format)
        - Frame 4 (index 3) contains the count of precipitation objects (15)
        - Precipitation data is encoded in pairs of frames: position frame followed by attribute frame
        - Position is encoded as (x+128, y+128) in the high and low bytes
        - Attributes encode type, rate, and intensity in bit fields
        
        Returns:
            A list of precipitation data objects with position, type, rate, intensity
        """
        all_frames = []
        precipitation_data = []

        # Collect all frames from data messages
        for msg in data_messages:
            if 'frames' in msg and isinstance(msg['frames'], list):
                all_frames.extend(msg['frames'])
                
        # Log original frame list length
        original_frame_count = len(all_frames)
        logger.info(f"[BC_TRANSFER_AGG] Original frame count: {original_frame_count}")
        
        # PREPROCESSING: Remove extra block headers to fix frame indexing
        all_frames = self._preprocess_frames_list(all_frames)
        logger.info(f"[BC_TRANSFER_AGG] Preprocessed frame count: {len(all_frames)}")
                
        # Need sufficient frames to contain precipitation data (header + count + data)
        if len(all_frames) < 4:
            logger.warning(f"[BC_TRANSFER_AGG] Not enough frames for precipitation data: {len(all_frames)}")
            return []
            
        # Validate high-level frame structure
        logger.info(f"[BC_TRANSFER_AGG] First 5 frames: {all_frames[:5] if len(all_frames) >= 5 else all_frames}")
            
        # The RT data message structure is more complex than originally thought
        # Frame 0: Status word (10001001...)
        # Frame 1: Sequence number metadata frame (00100000...)
        # Frame 2: Total messages metadata frame (00100000...)
        # Frame 3: Count frame - contains number of precipitation objects (00100000...)
        # Frames 4+: Actual precipitation data (alternating position and attribute frames)
        status_word_idx = 0
        sequence_metadata_idx1 = 1  # First metadata frame (sequence number)
        sequence_metadata_idx2 = 2  # Second metadata frame (total messages)
        count_frame_idx = 3         # Frame with precipitation object count
        first_data_frame_idx = 4    # First actual precipitation data frame
        
        # Log sequence metadata frames to help diagnose transmission issues
        if len(all_frames) > sequence_metadata_idx2:
            logger.info(f"[BC_TRANSFER_AGG] Sequence metadata frames: {all_frames[sequence_metadata_idx1]}, {all_frames[sequence_metadata_idx2]}")
        
        # Get count from the frame
        count_frame = all_frames[count_frame_idx]
        
        # Skip sync bits (first 3 bits) and extract count
        if len(count_frame) >= 20:  # Ensure frame is long enough
            count_bits = count_frame[3:19]  # FIXED: Use bits 3-18 (skip sync + parity)
            try:
                count = int(count_bits, 2)
                logger.info(f"[BC_TRANSFER_AGG] Detected precipitation count from frame: {count}")
                
                # SANITY CHECK: Log error if count is larger than the number of frame pairs we have
                max_possible_objects = (len(all_frames) - first_data_frame_idx) // 2
                if count > max_possible_objects:
                    logger.error(f"[BC_TRANSFER_AGG] Count ({count}) exceeds available frame pairs ({max_possible_objects})")
                    count = max_possible_objects
                    
            except ValueError:
                logger.error(f"[BC_TRANSFER_AGG] Failed to parse count frame: {count_frame}")
                return []
        else:
            logger.error(f"[BC_TRANSFER_AGG] Count frame too short: {count_frame}")
            return []
        
        # Start processing from the first data frame after count frame
        frame_index = first_data_frame_idx
        
        # Track how many valid objects we extract
        valid_objects = 0
        invalid_objects = 0
        
        # Process data in pairs (position frame + attribute frame)
        for i in range(count):
            if frame_index + 1 >= len(all_frames):
                logger.warning(f"[BC_TRANSFER_AGG] Not enough frames for precipitation object {i}, stopping")
                break
                
            # Check if frames have valid sync patterns (should be '001' for data words)
            position_frame = all_frames[frame_index]
            attribute_frame = all_frames[frame_index + 1]
            
            if not isinstance(position_frame, str) or len(position_frame) < 3 or not position_frame.startswith('001'):
                logger.warning(f"[BC_TRANSFER_AGG] Invalid position frame sync pattern at index {frame_index}: {position_frame[:3] if isinstance(position_frame, str) and len(position_frame) >= 3 else position_frame}")
                if i + 1 < count:  # Skip this pair and try the next one
                    frame_index += 2
                    invalid_objects += 1
                    continue
                    
            if not isinstance(attribute_frame, str) or len(attribute_frame) < 3 or not attribute_frame.startswith('001'):
                logger.warning(f"[BC_TRANSFER_AGG] Invalid attribute frame sync pattern at index {frame_index+1}: {attribute_frame[:3] if isinstance(attribute_frame, str) and len(attribute_frame) >= 3 else attribute_frame}")
                if i + 1 < count:  # Skip this pair and try the next one
                    frame_index += 2
                    invalid_objects += 1
                    continue
                
            # Get position and attribute frames
            position_frame = all_frames[frame_index]
            attribute_frame = all_frames[frame_index + 1]
            
            # Log raw frames for debugging
            logger.debug(f"[BC_TRANSFER_AGG] Object {i} position frame: {position_frame}")
            logger.debug(f"[BC_TRANSFER_AGG] Object {i} attribute frame: {attribute_frame}")
            
            frame_index += 2
            
            # Skip sync bits (first 3 bits) and parity bit (last bit)
            if len(position_frame) >= 20 and len(attribute_frame) >= 20:
                try:
                    # IMPORTANT: DO NOT swap position and attribute frames
                    # The RT transfer aggregator preserves the original frame order and encoding
                    # Swapping frames causes misinterpretation of precipitation data
                    # This fix maintains frame encoding compatibility between BC and RT
                    
                    # Read values directly from the frames
                    position_bits = position_frame[3:19]  # Use bits 3-18 (skip sync + parity)
                    attribute_bits = attribute_frame[3:19]  # Use bits 3-18 (skip sync + parity)
                    
                    position_value = int(position_bits, 2)
                    attribute_value = int(attribute_bits, 2)
                    
                    logger.debug(f"[BC_TRANSFER_AGG] Position binary: {bin(position_value)[2:].zfill(16)}, hex: 0x{position_value:04X}")
                    logger.debug(f"[BC_TRANSFER_AGG] Attribute binary: {bin(attribute_value)[2:].zfill(16)}, hex: 0x{attribute_value:04X}")
                    
                    logger.debug(f"[BC_TRANSFER_AGG] CORRECTED position binary: {bin(position_value)[2:].zfill(16)}, hex: 0x{position_value:04X}")
                    logger.debug(f"[BC_TRANSFER_AGG] CORRECTED attribute binary: {bin(attribute_value)[2:].zfill(16)}, hex: 0x{attribute_value:04X}")
                    
                    # After swapping, we need to use the right bit positions
                    # RT encodes as: High byte (bits 8-15) = X+128, Low byte (bits 0-7) = Y+128
                    encoded_x = (position_value >> 8) & 0xFF  # High byte (bits 8-15)
                    encoded_y = position_value & 0xFF         # Low byte (bits 0-7)
                    
                    # Log extracted coordinates
                    logger.debug(f"[BC_TRANSFER_AGG] Encoded coordinates: ({encoded_x},{encoded_y})")
                    
                    # Convert encoded coordinates to actual values by subtracting 128
                    # This matches how RT adds 128 during encoding (1.03 -> 129)
                    x_coord = encoded_x - 128
                    y_coord = encoded_y - 128
                    
                    # Extract attribute components according to RT encoding 
                    # Fixed to match precipitation_data_generator_sync.py's encoding format:
                    # Type bit is at bit 15 directly
                    type_bits = (attribute_value >> 12) & 0xF  # Keep for logging compatibility
                    
                    # Extract type code from the top 4 bits (bits 15-12) to match RT encoding
                    # In data_response_sender.py, type is encoded as: attr_word = (type_code << 12) | ...
                    precip_type = (attribute_value >> 15) & 0x1  # First bit of type determines snow vs rain
                    
                    # Use consistent bit field extraction
                    # The root issue is frames getting swapped and corrupted, so we need to:
                    # 1. Always use the same bit field extraction logic
                    # 2. Handle extracted values in a consistent way
                    # 3. Validate values against known bounds
                    
                    # Extract precipitation type from the top bit (consistent with RT encoding)
                    precip_type = (attribute_value >> 15) & 0x1  # First bit of type determines snow vs rain
                    type_name = "snow" if precip_type == 1 else "rain"
                    
                    # Using exact same bit field positions as in RT encoding
                    # RT encoding: Bits 11-6 are for rate (6 bits)
                    rate_bits = (attribute_value >> 6) & 0x3F
                    
                    # RT encoding: Bits 5-0 are for intensity (6 bits)  
                    intensity_bits = attribute_value & 0x3F
                    
                    # Apply bounds checking
                    rate_bits = min(63, max(0, rate_bits))
                    intensity_bits = min(63, max(0, intensity_bits))
                    
                    # Log extracted values for debugging
                    logger.debug(f"[BC_TRANSFER_AGG] Extracted rate bits: {rate_bits}, intensity bits: {intensity_bits}")
                    
                    # ENHANCED: Log pre-extraction frame data for more detailed debugging
                    logger.debug(f"[BC_TRANSFER_AGG] FRAME ANALYSIS Object {i}")
                    logger.debug(f"[BC_TRANSFER_AGG] Frame swap: Original position frame -> attribute data, Original attribute frame -> position data")
                    
                    # Log the specific bits for debugging - show full extraction process
                    logger.debug(f"[BC_TRANSFER_AGG] Rate bits (6-11): extracted from attribute_value=0x{attribute_value:04X}, bits {bin(rate_bits)[2:].zfill(6)}")
                    logger.debug(f"[BC_TRANSFER_AGG] Intensity bits (0-5): extracted from attribute_value=0x{attribute_value:04X}, bits {bin(intensity_bits)[2:].zfill(6)}")
                    
                    # Use same scaling as in precipitation_data_generator_sync.py
                    
                    # Apply rate scaling - match data generator values exactly
                    # Rate represents mm/hr of precipitation
                    if rate_bits == 63:  # Special case for maximum value
                        # When at max value, use special scaling for larger values
                        rate_scaled = rate_bits / 50.0  # Gives ~1.26 for max value
                    else:
                        # Standard scaling for normal rate values
                        rate_scaled = rate_bits / 100.0
                    
                    # Apply intensity scaling - match data generator values exactly
                    # Intensity is 0-1 normalized value
                    if intensity_bits == 63:  # Special case for maximum value
                        # When at max value, use special scaling for larger values
                        intensity_scaled = intensity_bits / 2500.0  # Gives ~0.0252 for max value
                    else:
                        # Standard scaling for normal intensity values
                        intensity_scaled = intensity_bits / 5000.0
                    
                    # Apply bounds checking to ensure valid ranges
                    rate_scaled = max(0.01, min(50.0, rate_scaled))
                    intensity_scaled = max(0.0001, min(1.0, intensity_scaled))
                        
                    # The precipitation type is already determined from the top bit above
                    # type_name = "snow" if precip_type == 1 else "rain"
                    
                    # Log decoded attribute components - AFTER type_name is defined
                    logger.debug(f"[BC_TRANSFER_AGG] Type bits: {bin(type_bits)[2:].zfill(4)}, Precipitation type bit: {precip_type}, Type name: {type_name}")
                    
                    # Create precipitation data object with correct values
                    precip_obj = {
                        "position": (x_coord, y_coord),
                        "type": type_name,
                        "rate": rate_scaled,
                        "intensity": intensity_scaled,
                        "show_values": False
                    }
                    
                    precipitation_data.append(precip_obj)
                    
                    # Enhanced logging to verify correct decoding with scaling factors
                    logger.debug(f"[BC_TRANSFER_AGG] Decoded precipitation object {i}: {precip_obj}")
                    logger.debug(f"[BC_TRANSFER_AGG] Decoding details for object {i}:")
                    logger.debug(f"[BC_TRANSFER_AGG] - Raw encoded position: (x={encoded_x}, y={encoded_y}), decoded: ({x_coord}, {y_coord})")
                    logger.debug(f"[BC_TRANSFER_AGG] - Raw type bits: {type_bits}, precip_type bit: {precip_type}, decoded: {type_name}")
                    logger.debug(f"[BC_TRANSFER_AGG] - Raw rate value: {rate_bits}, scaled: {rate_scaled} (factor: 1/100.0)")
                    logger.debug(f"[BC_TRANSFER_AGG] - Raw intensity value: {intensity_bits}, scaled: {intensity_scaled} (factor: 1/5000.0)")
                except Exception as e:
                    logger.error(f"[BC_TRANSFER_AGG] Error decoding precipitation frames {frame_index-2}/{frame_index-1}: {e}")
                    logger.error(f"[BC_TRANSFER_AGG] Position frame: {position_frame}")
                    logger.error(f"[BC_TRANSFER_AGG] Attribute frame: {attribute_frame}")
            else:
                logger.error(f"[BC_TRANSFER_AGG] Frames {frame_index-2}/{frame_index-1} too short for decoding")
                
        # Verify final count matches what was expected
        if len(precipitation_data) != count:
            logger.warning(f"[BC_TRANSFER_AGG] Extracted {len(precipitation_data)} precipitation objects, expected {count}")
        
        # Final summary with detailed statistics
        logger.info(f"[BC_TRANSFER_AGG] Precipitation data extraction complete:")
        logger.info(f"[BC_TRANSFER_AGG] - Original frame count: {original_frame_count}")
        logger.info(f"[BC_TRANSFER_AGG] - Preprocessed frame count: {len(all_frames)}")
        logger.info(f"[BC_TRANSFER_AGG] - Expected object count: {count}")
        logger.info(f"[BC_TRANSFER_AGG] - Valid objects: {valid_objects + len(precipitation_data)}")
        logger.info(f"[BC_TRANSFER_AGG] - Invalid objects: {invalid_objects}")
        logger.info(f"[BC_TRANSFER_AGG] - Extracted {len(precipitation_data)} precipitation data objects from frames")
        
        return precipitation_data
        
    def _cleanup_expired_transfers(self):
        """Clean up expired transfers."""
        current_time = time.time()
        expired_ids = []
        
        for req_id, timeout in self.transfer_timeouts.items():
            if current_time > timeout:
                expired_ids.append(req_id)
                
        for req_id in expired_ids:
            logger.warning(f"[BC_TRANSFER_AGG] Transfer timed out: {req_id}")
            if req_id in self.pending_transfers:
                del self.pending_transfers[req_id]
            del self.transfer_timeouts[req_id]
            
    def _extract_metadata(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and preserve critical metadata from a message."""
        metadata = {}
        
        # Get message metadata if available
        if 'metadata' in message and isinstance(message['metadata'], dict):
            # Copy only the necessary fields
            for key in ['message_type', 'command_type', 'command_name', 
                       'source_system', 'destination', 'request_id',
                       'precipitation_message', 'data_type']:
                if key in message['metadata']:
                    metadata[key] = message['metadata'][key]
        
        # Also check top-level fields
        for key in ['message_type', 'command_type', 'command_name', 
                   'source_system', 'destination', 'request_id']:
            if key in message:
                metadata[key] = message[key]
                
        return metadata
        
    def _extract_message_type(self, message: Dict[str, Any]) -> str:
        """Extract the true message type from a message."""
        # Check metadata first
        if 'metadata' in message and isinstance(message['metadata'], dict):
            if 'message_type' in message['metadata']:
                return message['metadata']['message_type']
                
        # Check top level
        if 'message_type' in message:
            return message['message_type']
            
        # Default for precipitation data
        if self._is_precipitation_message(message):
            return 'weather_radarPrecipitationResponse'
            
        # Default for vil data
        if self._is_vil_message(message):
            return 'weather_radarVILResponse'
            
        # Default fallback
        return 'binary_data_response'
        
    def _extract_command_type(self, message: Dict[str, Any]) -> str:
        """Extract the true command type from a message."""
        # Check metadata first
        if 'metadata' in message and isinstance(message['metadata'], dict):
            if 'command_type' in message['metadata']:
                return message['metadata']['command_type']
                
        # Check top level
        if 'command_type' in message:
            return message['command_type']
            
        # Default for precipitation data
        if self._is_precipitation_message(message):
            return 'precipitation_data'
            
        # Default for vil data
        if self._is_vil_message(message):
            return 'vil_data'
            
        # Default fallback
        return 'binary_data'
        
    def _is_precipitation_message(self, message: Dict[str, Any]) -> bool:
        """Determine if this is a precipitation message."""
        # Check metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            if 'precipitation_message' in metadata and metadata['precipitation_message']:
                return True
            if 'data_type' in metadata and metadata['data_type'] == 'precipitation':
                return True
            if 'message_type' in metadata and isinstance(metadata['message_type'], str) and 'precipitation' in metadata['message_type'].lower():
                return True
                
        # Check message types
        if 'message_type' in message and isinstance(message['message_type'], str) and 'precipitation' in message['message_type'].lower():
            return True
            
        # Check command types
        if 'command_type' in message and isinstance(message['command_type'], str) and 'precipitation' in message['command_type'].lower():
            return True
            
        return False
        
    def _is_vil_message(self, message: Dict[str, Any]) -> bool:
        """Determine if this is a VIL message."""
        # Check metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            if 'vil_message' in metadata and metadata['vil_message']:
                return True
            if 'data_type' in metadata and metadata['data_type'] == 'vil':
                return True
            if 'message_type' in metadata and isinstance(metadata['message_type'], str) and 'vil' in metadata['message_type'].lower():
                return True
                
        # Check message types
        if 'message_type' in message and isinstance(message['message_type'], str) and 'vil' in message['message_type'].lower():
            return True
            
        # Check command types
        if 'command_type' in message and isinstance(message['command_type'], str) and 'vil' in message['command_type'].lower():
            return True
            
        return False
        
    def is_binary_data_message(self, message: Dict[str, Any]) -> bool:
        """Determine if a message contains binary data that needs special handling."""
        # Skip non-dict messages
        if not isinstance(message, dict):
            return False
        
        request_id = message.get('request_id', 'unknown')
        logger.info(f"[BC_TRANSFER_AGG] Checking if message with ID {request_id} contains binary data")
        
        # Check for data arrays in message
        if 'data' in message:
            data_field = message['data']
            if isinstance(data_field, list) and len(data_field) > 0:
                # Check if data field contains mostly integers (binary data)
                if all(isinstance(item, int) for item in data_field):
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data array with {len(data_field)} elements")
                    return True
        
        # Check for binary data flags in metadata
        metadata = message.get('metadata', {})
        if isinstance(metadata, dict):
            binary_flags = ['binary_encoded', 'binary_data', 'precipitation_message', 'vil_message',
                          'is_transfer_data', 'is_transfer_init', 'is_block_transfer']
            for flag in binary_flags:
                if flag in metadata and metadata[flag]:
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via {flag} flag")
                    return True
            
            # Check data type flags
            if 'data_type' in metadata:
                data_type = metadata['data_type']
                if data_type in ['precipitation', 'vil', 'binary']:
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via data_type={data_type}")
                    return True
        
        # Check message type for indicators
        message_type = message.get('message_type', '')
        if message_type:
            binary_type_indicators = ['precipitation', 'vil', 'binary', 'block', 'transfer']
            for indicator in binary_type_indicators:
                if indicator in str(message_type).lower():
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via message_type containing '{indicator}'")
                    return True
        
        # Check command type for indicators
        command_type = message.get('command_type', '')
        if command_type:
            binary_cmd_indicators = ['precipitation', 'vil', 'binary', 'block', 'transfer']
            for indicator in binary_cmd_indicators:
                if indicator in str(command_type).lower():
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via command_type containing '{indicator}'")
                    return True
        
        # Check for command_name with precipitation indicators
        command_name = message.get('command_name', '')
        if command_name:
            binary_cmd_indicators = ['PRECIPITATION', 'VIL', 'BINARY', 'TRANSFER']
            for indicator in binary_cmd_indicators:
                if indicator in str(command_name).upper():
                    logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via command_name containing '{indicator}'")
                    return True
        
        # Check frame count (large frame counts typically indicate binary data)
        if 'frames' in message and isinstance(message['frames'], list) and len(message['frames']) > 20:
            logger.info(f"[BC_TRANSFER_AGG] Detected binary data message via large frame count ({len(message['frames'])})")
            return True
        
        logger.info(f"[BC_TRANSFER_AGG] Message does not contain binary data")
        return False
        
    def extract_binary_data(self, message: Dict[str, Any]) -> Optional[List[Any]]:
        """
        Extract binary data from a message.
        
        Args:
            message: The message to extract from
            
        Returns:
            List of binary data values if found, None otherwise
        """
        # Direct data field handling
        if 'data' in message and isinstance(message['data'], list):
            data_field = message['data']
            if all(isinstance(item, int) for item in data_field):
                return data_field.copy()
                
        # Handle frames for precipitation data
        if ('frames' in message and isinstance(message['frames'], list) and 
              len(message['frames']) > 20 and self._is_precipitation_message(message)):
              
            # Extract precipitation data from frames
            precipitation_data = self._extract_precipitation_data_from_frames([message])
            if precipitation_data and len(precipitation_data) > 0:
                logger.info(f"[BC_TRANSFER_AGG] Extracted {len(precipitation_data)} precipitation objects from frames")
                return precipitation_data
        
        return None
        
    def restore_binary_data(self, message: Dict[str, Any], binary_data: List[Any]) -> Dict[str, Any]:
        """
        Restore binary data to a message.
        
        Args:
            message: The message to restore binary data to
            binary_data: The binary data to restore
            
        Returns:
            Message with binary data restored
        """
        if binary_data is None or len(binary_data) == 0:
            return message
        
        result = message.copy()
        result['data'] = binary_data
        
        # Mark message as having preserved binary data
        if 'metadata' not in result:
            result['metadata'] = {}
        
        result['metadata']['binary_data_preserved'] = True
        result['metadata']['binary_data_length'] = len(binary_data)
        
        # Special handling for precipitation data
        if (len(binary_data) > 0 and isinstance(binary_data[0], dict) and 
            'position' in binary_data[0]):
            result['metadata']['precipitation_message'] = True
            result['metadata']['data_type'] = 'precipitation'
            
        logger.info(f"[BC_TRANSFER_AGG] Restored {len(binary_data)} binary data elements to message")
        return result
        
    def preserve_binary_data(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preserve binary data in a message during transfers.
        
        Args:
            message: The message to preserve binary data in
            
        Returns:
            Message with binary data preserved
        """
        if not self.is_binary_data_message(message):
            return message
            
        # Extract the binary data
        binary_data = self.extract_binary_data(message)
        if binary_data:
            # Create a copy of the message with the binary data restored
            return self.restore_binary_data(message, binary_data)
            
        return message

# Singleton instance
_block_transfer_aggregator = None

def get_block_transfer_aggregator():
    """Get the singleton instance of BlockTransferAggregator."""
    global _block_transfer_aggregator
    if _block_transfer_aggregator is None:
        _block_transfer_aggregator = BlockTransferAggregator()
    return _block_transfer_aggregator
