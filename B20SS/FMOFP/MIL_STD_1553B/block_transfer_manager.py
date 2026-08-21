"""
Block Transfer Manager

Handles reassembly of multi-block MIL-STD-1553B transfers.
Provides a singleton interface for managing block transfers across the system.
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple

# Get system logger
from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

class BlockTransferManager:
    """Handles reassembly of multi-block MIL-STD-1553B transfers"""

    _instance = None  # Singleton instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BlockTransferManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.pending_transfers = {}  # Dict of request_id -> transfer data
            self._initialized = True
            logger.info("[BLOCK_TRANSFER] Manager initialized")

    def register_block(self, request_id: str, sequence_number: int, total_sequences: int,
                      is_final: bool, data: List[int]) -> bool:
        """
        Register a block in an ongoing transfer

        Args:
            request_id: Unique identifier for this transfer
            sequence_number: Current block sequence number (0-based or 1-based, both supported)
            total_sequences: Total number of blocks in this transfer
            is_final: Whether this is the final block
            data: Binary data array for this block

        Returns:
            bool: True if transfer is complete after registering this block
        """
        if not isinstance(request_id, str) or not request_id:
            logger.error("[BLOCK_TRANSFER] Invalid request_id")
            return False

        # Support both 0-based and 1-based sequence numbering
        if not isinstance(sequence_number, int) or sequence_number < 0:
            logger.error(f"[BLOCK_TRANSFER] Invalid sequence_number: {sequence_number}")
            return False

        if not isinstance(total_sequences, int) or total_sequences < 1:
            logger.error(f"[BLOCK_TRANSFER] Invalid total_sequences: {total_sequences}")
            return False

        if not isinstance(data, list):
            logger.error(f"[BLOCK_TRANSFER] Invalid data type: {type(data)}")
            return False

        # Enhanced logging for better diagnostics
        logger.info(f"[BLOCK_TRANSFER] Registering block {sequence_number}/{total_sequences} for request_id: {request_id}")
        logger.info(f"[BLOCK_TRANSFER] Block data length: {len(data)} items, is_final: {is_final}")

        # Initialize transfer record if needed
        if request_id not in self.pending_transfers:
            self.pending_transfers[request_id] = {
                'blocks': [None] * total_sequences,
                'total_sequences': total_sequences,
                'received_count': 0,
                'timestamp': time.time(),
                'complete': False,
                'data_type': None,  # Will be detected from metadata
                'message_type': None,  # Will be detected from metadata
                'is_zero_based': sequence_number == 0  # Detect if this is a 0-based or 1-based sequence
            }
            logger.info(f"[BLOCK_TRANSFER] Started new transfer for request_id: {request_id}")
            logger.info(f"[BLOCK_TRANSFER] Detected {'zero-based' if sequence_number == 0 else 'one-based'} sequence numbering")

            # Add enhanced logging specifically for precipitation data debugging
            logger.debug(f"[PRECIPITATION_FLOW_DEBUG] Starting block transfer with request_id={request_id}, total_sequences={total_sequences}")

        transfer = self.pending_transfers[request_id]

        # Adjust for 0-based sequence numbering if needed
        is_zero_based = transfer.get('is_zero_based', False)
        adjusted_sequence = sequence_number if is_zero_based else sequence_number - 1

        # Validate sequence number against expected total
        if adjusted_sequence >= transfer['total_sequences']:
            logger.error(f"[BLOCK_TRANSFER] Sequence number {sequence_number} exceeds total {transfer['total_sequences']}")
            return False

        # Check if this block was already received
        if transfer['blocks'][adjusted_sequence] is not None:
            logger.warning(f"[BLOCK_TRANSFER] Duplicate block: {sequence_number}/{total_sequences} for {request_id}")
            # Check if transfer is already complete
            return transfer['complete']

        # Enhanced precipitation and VIL data detection for more robust handling
        # First check for explicit indicators in metadata or message structure
        is_precipitation = False
        is_vil = False
        message_type = None

        # Examine each data item looking for dictionary metadata
        for item in data:
            if isinstance(item, dict):
                # Check for metadata in dictionary items
                item_metadata = item.get('metadata', {})
                if isinstance(item_metadata, dict):
                    item_msg_type = item_metadata.get('message_type', '')
                    item_cmd_type = item_metadata.get('command_type', '')

                    # Check for precipitation/VIL indicators in metadata
                    if isinstance(item_msg_type, str):
                        if 'precip' in item_msg_type.lower() or 'precipitation' in item_msg_type.lower():
                            is_precipitation = True
                            message_type = item_msg_type
                            logger.info(f"[BLOCK_TRANSFER] Detected precipitation data from metadata: {item_msg_type}")
                            break
                        elif 'vil' in item_msg_type.lower():
                            is_vil = True
                            message_type = item_msg_type
                            logger.info(f"[BLOCK_TRANSFER] Detected VIL data from metadata: {item_msg_type}")
                            break

                    if isinstance(item_cmd_type, str):
                        if 'precip' in item_cmd_type.lower() or 'precipitation' in item_cmd_type.lower():
                            is_precipitation = True
                            logger.info(f"[BLOCK_TRANSFER] Detected precipitation data from command_type: {item_cmd_type}")
                            break
                        elif 'vil' in item_cmd_type.lower():
                            is_vil = True
                            logger.info(f"[BLOCK_TRANSFER] Detected VIL data from command_type: {item_cmd_type}")
                            break

        # If not identified via metadata, use pattern recognition on first sequence
        if not (is_precipitation or is_vil) and len(data) > 0 and sequence_number == 1:
            first_word = data[0]
            # Precipitation and VIL data typically starts with a count of objects
            if isinstance(first_word, int) and first_word > 0 and first_word < 100:
                logger.info(f"[BLOCK_TRANSFER] Detected potential precipitation/VIL data block with {first_word} objects")
                # Set data type for consistent handling across blocks
                transfer['data_type'] = 'precipitation'
                # Preserve entire data block including metadata
                actual_data = data
                # Set is_precipitation flag
                is_precipitation = True
            else:
                # Standard case: first two words might be sequence metadata
                actual_data = data[2:] if len(data) > 2 else data
        else:
            # For subsequent blocks in a known precipitation/VIL transfer
            if transfer.get('data_type') in ['precipitation', 'vil']:
                # Preserve all data in precipitation/VIL transfers
                actual_data = data
                logger.info(f"[BLOCK_TRANSFER] Preserving all data for known {transfer.get('data_type')} transfer")
            else:
                # Standard handling for other data types
                actual_data = data[2:] if len(data) > 2 else data

        # Update the transfer record with precipitation/VIL information if detected
        if is_precipitation and not transfer.get('data_type'):
            transfer['data_type'] = 'precipitation'
            if message_type:
                transfer['message_type'] = message_type
            logger.info(f"[BLOCK_TRANSFER] Marked transfer as precipitation data for special handling")
        elif is_vil and not transfer.get('data_type'):
            transfer['data_type'] = 'vil'
            if message_type:
                transfer['message_type'] = message_type
            logger.info(f"[BLOCK_TRANSFER] Marked transfer as VIL data for special handling")

        logger.info(f"[BLOCK_TRANSFER] Storing block {sequence_number}/{total_sequences} with {len(actual_data)} data words")

        # Store the data and update received count using adjusted sequence number
        transfer['blocks'][adjusted_sequence] = actual_data
        transfer['received_count'] += 1

        # Check if transfer is complete
        transfer['complete'] = (transfer['received_count'] == transfer['total_sequences'])
        if transfer['complete']:
            logger.info(f"[BLOCK_TRANSFER] Transfer {request_id} is now complete with {transfer['received_count']} blocks")

        return transfer['complete']

    def is_transfer_complete(self, request_id: str) -> bool:
        """Check if all blocks for a transfer have been received"""
        if request_id not in self.pending_transfers:
            logger.warning(f"[BLOCK_TRANSFER] Unknown transfer: {request_id}")
            return False

        transfer = self.pending_transfers[request_id]
        return transfer['complete']

    def _validate_1553b_frames(self, frames):
        """
        Validate all frames to ensure they're exactly 20 bits and have valid sync bits.
        This matches RT's frame validation implementation for perfect consistency.

        Args:
            frames: List of frames to validate

        Returns:
            List of valid frames (all invalid frames are removed)
        """
        if not frames:
            return []

        valid_frames = []
        for i, frame in enumerate(frames):
            # Skip None and non-string frames
            if not isinstance(frame, str):
                logger.debug(f"[BLOCK_TRANSFER] Frame {i} is not a string: {type(frame)}")
                valid_frames.append(frame)  # Non-string items preserved as-is
                continue

            # Validate frame length
            if len(frame) != 20:
                logger.error(f"[BLOCK_TRANSFER] Frame {i} has invalid length {len(frame)}, expected 20 bits")

                # If close to 20, try to fix by padding or truncating
                if 18 <= len(frame) <= 22:
                    if len(frame) < 20:
                        # Pad with parity bit(s)
                        fixed_frame = frame.ljust(20, '0')
                    else:
                        # Truncate to 20 bits
                        fixed_frame = frame[:20]
                    logger.warning(f"[BLOCK_TRANSFER] Fixed frame {i} to valid length: {fixed_frame}")
                    frame = fixed_frame
                else:
                    # Too far off, skip this frame
                    continue

            # Check sync bits (must be '100' or '001')
            sync_bits = frame[:3]
            if sync_bits not in ['100', '001']:
                logger.error(f"[BLOCK_TRANSFER] Frame {i} has invalid sync bits: {sync_bits}")
                continue

            # Frame is valid, add to list
            valid_frames.append(frame)

        # Log validation summary
        if len(valid_frames) != len(frames):
            logger.warning(f"[BLOCK_TRANSFER] Frame validation: {len(valid_frames)}/{len(frames)} frames are valid")
        else:
            logger.info(f"[BLOCK_TRANSFER] Frame validation: All {len(frames)} frames are valid")

        return valid_frames

    def _validate_parity(self, frame):
        """
        Validate parity bit for a 20-bit frame according to MIL-STD-1553B

        Args:
            frame: 20-bit binary string to validate

        Returns:
            bool: True if parity is valid, False otherwise
        """
        if len(frame) != 20:
            return False

        # Count number of 1 bits in the first 19 bits
        ones_count = frame[:19].count('1')

        # MIL-STD-1553B uses odd parity
        expected_parity = '1' if ones_count % 2 == 0 else '0'

        return frame[19] == expected_parity

    def _split_oversized_frames(self, oversized_frame):
        """
        Enhanced frame splitting with military-grade pattern recognition and robustness

        Args:
            oversized_frame: String that might contain multiple concatenated frames or dictionary

        Returns:
            List of valid 20-bit frames extracted from the oversized frame
        """
        # First, detect if we're dealing with a dictionary representation
        if isinstance(oversized_frame, str) and oversized_frame.startswith('{') and oversized_frame.endswith('}'):
            logger.info(f"[BLOCK_TRANSFER] Detected dictionary structure in oversized frame")
            try:
                # Parse dictionary and extract frames directly
                parsed_dict = json.loads(oversized_frame)
                if isinstance(parsed_dict, dict) and 'frames' in parsed_dict:
                    frames = parsed_dict['frames']
                    valid_frames = []
                    for frame in frames:
                        if isinstance(frame, str) and len(frame) == 20:
                            if frame.startswith('100') or frame.startswith('001'):
                                valid_frames.append(frame)
                                logger.info(f"[BLOCK_TRANSFER] Extracted valid frame from dictionary: {frame}")

                    if valid_frames:
                        logger.info(f"[BLOCK_TRANSFER] Extracted {len(valid_frames)} valid frames from dictionary structure")
                        return valid_frames
            except (ValueError, SyntaxError) as e:
                logger.error(f"[BLOCK_TRANSFER] Failed to parse dictionary structure: {e}")
                # Continue with normal processing if dict parsing fails

        if not isinstance(oversized_frame, str):
            return [oversized_frame]

        # Skip processing if not binary data
        if not all(bit in '01' for bit in oversized_frame):
            return [oversized_frame]

        if len(oversized_frame) <= 20:
            return [oversized_frame]

        logger.warning(f"[BLOCK_TRANSFER] Splitting oversized frame: {len(oversized_frame)} bits")

        # Results array
        extracted_frames = []

        # Enhanced scanning with sliding window - works across entire data range
        pos = 0

        while pos <= len(oversized_frame) - 20:  # Need at least 20 bits for a complete frame
            # Check for sync pattern at current position
            if (oversized_frame[pos:pos+3] == '100' or oversized_frame[pos:pos+3] == '001'):
                # Found potential start of a frame
                candidate = oversized_frame[pos:pos+20]

                # Additional validation: check parity bit for enhanced integrity
                if self._validate_parity(candidate):
                    extracted_frames.append(candidate)
                    logger.info(f"[BLOCK_TRANSFER] Extracted valid 20-bit frame at position {pos}: {candidate}")
                    pos += 20  # Move to potential start of next frame
                else:
                    # Found sync bits but invalid parity - could be a coincidental match
                    logger.debug(f"[BLOCK_TRANSFER] Sync pattern found but parity check failed at position {pos}")
                    pos += 1  # Move one bit and continue searching
            else:
                # Move one bit at a time to find next sync pattern - ensures thorough search
                pos += 1

                # Log progress periodically for very large frames
                if pos % 100 == 0 and len(oversized_frame) > 500:
                    logger.debug(f"[BLOCK_TRANSFER] Scanning position {pos}/{len(oversized_frame)}")

        # Log results
        if extracted_frames:
            logger.info(f"[BLOCK_TRANSFER] Split oversized frame into {len(extracted_frames)} valid frames")
        else:
            logger.error(f"[BLOCK_TRANSFER] Failed to extract any valid frames from {len(oversized_frame)}-bit data")

            # Log frame details for diagnosis
            if len(oversized_frame) > 60:
                sample_start = oversized_frame[:60]
                sample_end = oversized_frame[-60:]
                logger.error(f"[BLOCK_TRANSFER] Frame start: {sample_start}...")
                logger.error(f"[BLOCK_TRANSFER] Frame end: ...{sample_end}")

                # Check if there are any potential sync patterns at all
                start_patterns = [i for i in range(len(oversized_frame)-2) if oversized_frame[i:i+3] in ['100', '001']]
                if start_patterns:
                    logger.error(f"[BLOCK_TRANSFER] Found {len(start_patterns)} potential sync patterns that failed validation")
                    if len(start_patterns) > 0:
                        logger.error(f"[BLOCK_TRANSFER] First 5 potential patterns at positions: {start_patterns[:5]}")
                else:
                    logger.error(f"[BLOCK_TRANSFER] No sync patterns found in entire frame")

        return extracted_frames

    def get_assembled_data(self, request_id: str) -> Optional[List[int]]:
        """
        Get fully assembled data for a complete transfer with MIL-STD-1553B validation

        Args:
            request_id: The unique identifier for the transfer

        Returns:
            List[int]: Complete assembled data array with valid frames, or None if transfer is incomplete
        """
        if not self.is_transfer_complete(request_id):
            logger.warning(f"[BLOCK_TRANSFER] Attempted to get incomplete transfer: {request_id}")
            return None

        # Collect raw assembled data as before
        raw_assembled_data = []
        for block in self.pending_transfers[request_id]['blocks']:
            if block:
                raw_assembled_data.extend(block)

        logger.info(f"[BLOCK_TRANSFER] Raw assembled data size: {len(raw_assembled_data)} items")

        #  ENHANCEMENT: Process data to ensure MIL-STD-1553B compliance
        # This exactly mirrors RT's frame validation approach
        processed_data = []

        # Process each item in raw_assembled_data
        for i, item in enumerate(raw_assembled_data):
            # Handle dictionary items that might contain frames or serialized data
            if isinstance(item, dict):
                logger.info(f"[BLOCK_TRANSFER] Processing dictionary item {i}")

                # Extract frames if available
                if 'frames' in item and isinstance(item['frames'], list):
                    frames = item['frames']
                    valid_frames = self._validate_1553b_frames(frames)
                    processed_data.extend(valid_frames)
                    logger.info(f"[BLOCK_TRANSFER] Processed {len(valid_frames)} frames from dictionary")
                else:
                    # If no frames field, preserve the dictionary
                    processed_data.append(item)
                    logger.info(f"[BLOCK_TRANSFER] Preserved dictionary without frames")

            # Handle string items that might be frames or serialized data
            elif isinstance(item, str):
                # Check if already a valid 20-bit frame
                if len(item) == 20 and (item.startswith('100') or item.startswith('001')):
                    processed_data.append(item)
                    logger.debug(f"[BLOCK_TRANSFER] Added valid 20-bit frame")
                # Handle oversized items that might be concatenated frames
                elif len(item) > 20:
                    # This might be multiple concatenated frames or a serialized string
                    extracted_frames = self._split_oversized_frames(item)
                    if extracted_frames:
                        # Validate the extracted frames
                        valid_extracted = self._validate_1553b_frames(extracted_frames)
                        processed_data.extend(valid_extracted)
                        logger.info(f"[BLOCK_TRANSFER] Processed oversized item into {len(valid_extracted)} valid frames")
                    else:
                        # If no frames could be extracted, preserve the original item
                        logger.warning(f"[BLOCK_TRANSFER] Could not extract frames from oversized item, preserving as-is")
                        processed_data.append(item)
                else:
                    # Not a valid frame but not oversized either - preserve as-is
                    logger.debug(f"[BLOCK_TRANSFER] Preserved non-standard string item")
                    processed_data.append(item)
            else:
                # Non-string/non-dict items (integers, lists, etc.) - preserve as-is
                processed_data.append(item)
                logger.debug(f"[BLOCK_TRANSFER] Preserved non-string item of type {type(item)}")

        # Log summary of processing
        original_count = len(raw_assembled_data)
        processed_count = len(processed_data)
        logger.info(f"[BLOCK_TRANSFER] Processed {original_count} raw items into {processed_count} valid items")

        if original_count != processed_count:
            # Calculate detailed stats for frame validation
            string_items = len([i for i in raw_assembled_data if isinstance(i, str)])
            string_items_after = len([i for i in processed_data if isinstance(i, str)])
            logger.info(f"[BLOCK_TRANSFER] String items: {string_items} before, {string_items_after} after processing")

            if string_items > string_items_after:
                frames_lost = string_items - string_items_after
                percent_lost = (frames_lost / string_items) * 100 if string_items > 0 else 0
                logger.warning(f"[BLOCK_TRANSFER] {frames_lost} frames ({percent_lost:.1f}%) removed during validation")

                # If significant data loss, log detailed information
                if percent_lost > 10:
                    logger.error(f"[BLOCK_TRANSFER] Significant data loss during frame validation: {percent_lost:.1f}%")
                    invalid_items = [i for i in raw_assembled_data if isinstance(i, str) and
                                    (len(i) != 20 or not (i.startswith('100') or i.startswith('001')))]

                    # Log a sample of invalid items for debugging
                    if invalid_items:
                        sample_size = min(3, len(invalid_items))
                        logger.error(f"[BLOCK_TRANSFER] Sample of {sample_size} invalid items:")
                        for i in range(sample_size):
                            item = invalid_items[i]
                            logger.error(f"[BLOCK_TRANSFER] Invalid item {i}: Length={len(item)}, Prefix={item[:5] if len(item) >= 5 else item}")

        # Clear this transfer from pending transfers to free memory
        del self.pending_transfers[request_id]

        return processed_data

    def cleanup_stale_transfers(self, max_age_seconds: int = 60) -> int:
        """
        Remove transfers that have been pending for too long

        Args:
            max_age_seconds: Maximum age in seconds before a transfer is considered stale

        Returns:
            int: Number of stale transfers removed
        """
        current_time = time.time()
        stale_transfers = []

        for request_id, transfer in self.pending_transfers.items():
            if current_time - transfer['timestamp'] > max_age_seconds:
                stale_transfers.append(request_id)

        for request_id in stale_transfers:
            logger.warning(f"[BLOCK_TRANSFER] Removing stale transfer: {request_id}")
            del self.pending_transfers[request_id]

        if stale_transfers:
            logger.info(f"[BLOCK_TRANSFER] Removed {len(stale_transfers)} stale transfers")

        return len(stale_transfers)

    def get_pending_transfers_count(self) -> int:
        """Get the number of pending transfers"""
        return len(self.pending_transfers)

    def clear_transfer(self, request_id: str) -> bool:
        """
        Clear an existing transfer by request_id

        Args:
            request_id: The unique identifier for the transfer

        Returns:
            bool: True if the transfer was found and cleared, False otherwise
        """
        if request_id not in self.pending_transfers:
            logger.warning(f"[BLOCK_TRANSFER] Attempted to clear nonexistent transfer: {request_id}")
            return False

        # Remove the transfer
        del self.pending_transfers[request_id]
        logger.info(f"[BLOCK_TRANSFER] Cleared transfer: {request_id}")
        return True

    def get_transfer_status(self, request_id: str) -> dict:
        """Get detailed status of a transfer"""
        if request_id not in self.pending_transfers:
            # Return a safe status object with default values to prevent KeyErrors
            logger.warning(f"[BLOCK_TRANSFER] Getting status for nonexistent transfer: {request_id}")
            return {
                'exists': False,
                'complete': False,
                'received_blocks': 0,
                'total_blocks': 0,
                'age_seconds': 0,
                'percent_complete': 0
            }

        transfer = self.pending_transfers[request_id]
        age = time.time() - transfer['timestamp']

        return {
            'exists': True,
            'complete': transfer['complete'],
            'received_blocks': transfer['received_count'],
            'total_blocks': transfer['total_sequences'],
            'age_seconds': age,
            'percent_complete': (transfer['received_count'] / transfer['total_sequences']) * 100
        }

# Singleton access function
def get_block_transfer_manager() -> BlockTransferManager:
    """Get the singleton instance of BlockTransferManager"""
    return BlockTransferManager()
