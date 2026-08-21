"""
Bus Controller Message Extractor

Extends the Universal Message Extractor with BC-specific field extraction logic.
Specialized handling for MIL-STD-1553B message formats in the Bus Controller context.
"""

import sys
import os
import time
from typing import Dict, Any, List, Union, Optional

# Import the base class
from FMOFP.Utils.common.universal_message_extractor import UniversalMessageExtractor

# Import system logger
try:
    from FMOFP.Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger('bc_message_extractor')

class BC_MessageExtractor(UniversalMessageExtractor):
    """
    Bus Controller specific message extractor with specialized handling for BC messages.
    Enhances the base extractor with BC-specific field processing and validation.
    """
    
    def __init__(self, **kwargs):
        """Initialize BC-specific message extractor."""
        super().__init__(**kwargs)
        self.logger.info("BC_MessageExtractor initialized")
    
    def _process_critical_fields(self, result):
        """
        BC-specific processing for critical fields.
        
        Enhances the base processing with special handling for:
        - Status words
        - Command words
        - RT addressing
        - BC-specific message types
        - UUID field preservation
        - Command name standardization
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with BC-specific processing applied
        """
        # First apply base processing
        result = super()._process_critical_fields(result)
        
        # Ensure UUID fields are preserved in metadata for resilient tracking
        self._ensure_uuid_fields_in_metadata(result)
        
        # BC-specific field handling
        # For example, ensure status words are properly identified
        if (result.get('status_word') or
            (result.get('message_type') == 'status_word') or
            (isinstance(result.get('binary_data'), str) and result.get('binary_data', '').startswith('100'))):
            
            result['message_type'] = 'status_word'
            result['is_status_word'] = True
            
            # Extract RT address for status words if available
            if 'rt_address' not in result and 'binary_data' in result:
                binary = result['binary_data']
                if isinstance(binary, str) and len(binary) >= 8:
                    result['rt_address'] = int(binary[3:8], 2)
                    
            # If rt_address is present, try to determine radar_type
            if result.get('rt_address') == 9:  # Radar system
                radar_type = None
                
                # Check for subaddress to determine radar type
                if result.get('sub_address'):
                    subaddress = result['sub_address']
                    radar_map = {
                        1: 'weather_radar',
                        2: 'tfr_radar',
                        3: 'sar_radar',
                        4: 'targeting_radar',
                        5: 'aewc_radar'
                    }
                    radar_type = radar_map.get(subaddress)
                
                # If found, set radar_type
                if radar_type:
                    result['radar_type'] = radar_type
                    self.logger.info(f"[BC_EXTRACTOR] Determined radar_type: {radar_type}")
            
        # Ensure command_name and request_id are preserved in status word
            if not result.get('command_name') or not result.get('request_id'):
                # Try to infer from metadata and other fields
                if result.get('original_message'):
                    original = result['original_message']
                    
                    if isinstance(original, dict):
                        # Extract command_name from original message (top priority)
                        if not result.get('command_name') and 'command_name' in original:
                            result['command_name'] = original['command_name']
                            self.logger.info(f"[BC_EXTRACTOR] Extracted command_name from original message: {result['command_name']}")
                        
                        # Extract request_id from original message (top priority)
                        if not result.get('request_id') and 'request_id' in original:
                            result['request_id'] = original['request_id']
                            self.logger.info(f"[BC_EXTRACTOR] Extracted request_id from original message: {result['request_id']}")
                        
                        # Next try metadata
                        if (original.get('metadata') and isinstance(original['metadata'], dict)):
                            metadata = original['metadata']
                            
                            # Extract command_name from metadata
                            if not result.get('command_name') and 'command_name' in metadata:
                                result['command_name'] = metadata['command_name']
                                self.logger.info(f"[BC_EXTRACTOR] Extracted command_name from metadata: {result['command_name']}")
                            
                            # Extract request_id from metadata
                            if not result.get('request_id') and 'request_id' in metadata:
                                result['request_id'] = metadata['request_id']
                                self.logger.info(f"[BC_EXTRACTOR] Extracted request_id from metadata: {result['request_id']}")
                    
                    elif hasattr(original, 'command_name') or hasattr(original, 'request_id'):
                        # Handle object types that have direct attributes
                        if not result.get('command_name') and hasattr(original, 'command_name'):
                            result['command_name'] = original.command_name
                            self.logger.info(f"[BC_EXTRACTOR] Extracted command_name from object attribute: {result['command_name']}")
                        
                        if not result.get('request_id') and hasattr(original, 'request_id'):
                            result['request_id'] = original.request_id
                            self.logger.info(f"[BC_EXTRACTOR] Extracted request_id from object attribute: {result['request_id']}")
                        
                        # Check for metadata as an attribute
                        if hasattr(original, 'metadata') and original.metadata:
                            if not result.get('command_name') and hasattr(original.metadata, 'command_name'):
                                result['command_name'] = original.metadata.command_name
                                self.logger.info(f"[BC_EXTRACTOR] Extracted command_name from object metadata: {result['command_name']}")
                            
                            if not result.get('request_id') and hasattr(original.metadata, 'request_id'):
                                result['request_id'] = original.metadata.request_id
                                self.logger.info(f"[BC_EXTRACTOR] Extracted request_id from object metadata: {result['request_id']}")
        
        # Handle special case for precipitation data
        if ('precipitation' in str(result.get('message_type', '')).lower() or 
            'precip' in str(result.get('command_type', '')).lower() or
            (result.get('command_name') and 'PRECIPITATION' in result['command_name'])):
            
            # Standardize fields for precipitation data
            result['message_type'] = 'precipitation_data'
            result['command_type'] = 'precipitation_data'
            if not result.get('command_name'):
                result['command_name'] = 'WEATHER_RADAR_PRECIPITATION_DATA'
                
            # Flag for message routing
            result['is_precipitation_data'] = True
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['precipitation_data'] = True
                result['metadata']['data_type'] = 'precipitation'
                result['metadata']['command_name'] = result['command_name']
                
        # Handle special case for VIL data
        if ('vil' in str(result.get('message_type', '')).lower() or 
            'vil' in str(result.get('command_type', '')).lower() or
            (result.get('command_name') and 'VIL' in result['command_name'])):
            
            # Standardize fields for VIL data
            result['message_type'] = 'vil_data'
            result['command_type'] = 'vil_data'
            if not result.get('command_name'):
                result['command_name'] = 'WEATHER_RADAR_VIL_DATA'
                
            # Flag for message routing
            result['is_vil_data'] = True
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['vil_data'] = True
                result['metadata']['data_type'] = 'vil'
                result['metadata']['command_name'] = result['command_name']
                
        # Handle special case for mode change
        if ('mode' in str(result.get('message_type', '')).lower() or 
            'mode' in str(result.get('command_type', '')).lower() or
            (result.get('command_name') and 'MODE' in result['command_name'])):
            
            # Preserve completion status exactly as found
            original_message_type = str(result.get('message_type', '')).lower()
            
            # Better detection for completion messages
            is_completion = ('completion' in original_message_type or 
                             'complete' in original_message_type or
                             (result.get('command_name') and 'COMPLETION' in result.get('command_name', '')))
            
            # Standardize fields for mode change - preserve completion status
            if is_completion:
                # Preserve original message type if it exists and contains 'weather_radar'
                if 'weather_radar' in original_message_type and 'mode' in original_message_type:
                    # Keep the original case
                    if result.get('message_type'):
                        # Just ensure 'Completion' is correctly appended if needed
                        if 'completion' not in result['message_type'].lower():
                            result['message_type'] = result['message_type'] + 'Completion'
                    else:
                        # Default if no original exists
                        result['message_type'] = 'weather_radarModeChangeCompletion'
                else:
                    # Generic completion
                    result['message_type'] = 'mode_change_completion'
                
                # Always ensure command_type reflects completion
                result['command_type'] = 'mode_change_completion'
                
                # Ensure command name reflects completion
                if not result.get('command_name'):
                    result['command_name'] = 'WEATHER_RADAR_MODE_CHANGE_COMPLETION'
                elif 'COMPLETION' not in result['command_name']:
                    result['command_name'] = result['command_name'] + '_COMPLETION'
            else:
                # Regular mode change (not completion)
                if 'weather_radar' in original_message_type:
                    result['message_type'] = 'weather_radarModeChange'
                else:
                    result['message_type'] = 'mode_change'
                    
                result['command_type'] = 'mode_change'
                
                if not result.get('command_name'):
                    # Determine radar_type from result
                    radar_type = result.get('radar_type')
                    
                    # If no radar_type directly, try to determine from RT address and subaddress
                    if not radar_type and result.get('rt_address') == 9:  # Radar system
                        subaddress = result.get('sub_address')
                        if subaddress:
                            subaddress_map = {
                                1: 'weather_radar',
                                2: 'tfr_radar',
                                3: 'sar_radar',
                                4: 'targeting_radar', 
                                5: 'aewc_radar'
                            }
                            radar_type = subaddress_map.get(subaddress)
                            self.logger.info(f"[BC_EXTRACTOR] Determined radar_type '{radar_type}' from subaddress {subaddress}")
                    
                    # Only if we have a radar_type, generate the command name
                    if radar_type:
                        from FMOFP.MIL_STD_1553B.Bus_Controller.radar_type_utils import get_radar_command_name
                        result['command_name'] = get_radar_command_name(radar_type, 'mode_change', is_completion=False)
                        self.logger.info(f"[BC_EXTRACTOR] Generated command_name: {result['command_name']} for radar_type: {radar_type}")
                
            # Flag for message routing
            result['is_mode_change'] = True
            if is_completion:
                result['is_completion'] = True
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['mode_change'] = True
                result['metadata']['data_type'] = 'mode'
                result['metadata']['command_name'] = result['command_name']
                result['metadata']['is_completion'] = is_completion
                
        return result
        
    def _extract_from_binary(self, binary_message):
        """
        Enhanced BC-specific extraction from binary message.
        
        Extends base extraction with specialized handling for MIL-STD-1553B
        command words, status words, and data words in the BC context.
        
        Args:
            binary_message: Binary message string
            
        Returns:
            dict: Extracted fields with BC-specific enhancements
        """
        # First get base extraction
        result = super()._extract_from_binary(binary_message)
        
        # Ensure binary string is properly processed even if it comes directly
        if isinstance(binary_message, str) and self._is_binary_message(binary_message):
            # Handle status/command word (always need RT address)
            if binary_message.startswith('100'):
                # Always extract RT address (bits 3-7) for any status/command word
                if len(binary_message) >= 8:
                    result['rt_address'] = int(binary_message[3:8], 2)
                    self.logger.info(f"[BC_EXTRACTOR] Extracted RT address: {result['rt_address']}")
        
        # BC-specific binary message handling
        if isinstance(binary_message, str) and binary_message.startswith('100'):  # Command or status word
            # Enhanced extraction for status word
            if result.get('message_type') == 'status_word':
                # Extract status flags from bits 8-15
                if len(binary_message) >= 16:
                    flags_bits = binary_message[8:16]
                    result['status_flags'] = int(flags_bits, 2)
                    
                    # Also set a request_id if not present
                    if not result.get('request_id'):
                        import uuid
                        result['request_id'] = f"auto_status_{result.get('rt_address')}_{uuid.uuid4().hex[:8]}"
                    
                    # Decode individual status flags
                    result['status_message_error'] = (flags_bits[0] == '1')
                    result['status_instrumentation'] = (flags_bits[1] == '1')
                    result['status_service_request'] = (flags_bits[2] == '1')
                    result['status_broadcast_received'] = (flags_bits[3] == '1')
                    result['status_busy'] = (flags_bits[4] == '1')
                    result['status_subsystem_flag'] = (flags_bits[5] == '1')
                    result['status_dynamic_bus_control'] = (flags_bits[6] == '1')
                    result['status_terminal_flag'] = (flags_bits[7] == '1')
                    
                    # Determine status word interpretation
                    if result['status_message_error']:
                        result['status_interpretation'] = 'message_error'
                    elif result['status_service_request']:
                        result['status_interpretation'] = 'service_request'
                    elif result['status_busy']:
                        result['status_interpretation'] = 'busy'
                    else:
                        result['status_interpretation'] = 'normal'
                        
                    self.logger.info(f"[BC_EXTRACTOR] Decoded status flags: {flags_bits}")
            
            # Enhanced extraction for command word
            elif result.get('message_type') == 'command_word':
                # Extract T/R bit (bit 8)
                if len(binary_message) >= 9:
                    result['transmit_receive_bit'] = binary_message[8:9]
                    result['is_transmit'] = (result['transmit_receive_bit'] == '1')
                    result['is_receive'] = (result['transmit_receive_bit'] == '0')
                
                # Extract subaddress/mode (bits 9-13)
                if len(binary_message) >= 14:
                    result['sub_address'] = int(binary_message[9:14], 2)
                    
                    # Check if this is a mode code
                    if result['sub_address'] == 0 or result['sub_address'] == 31:
                        result['is_mode_code'] = True
                        
                        # Extract mode code (bits 14-18)
                        if len(binary_message) >= 19:
                            result['mode_code'] = int(binary_message[14:19], 2)
                    else:
                        result['is_mode_code'] = False
                        
                        # Extract word count (bits 14-18)
                        if len(binary_message) >= 19:
                            # Handle special case where 0 means 32
                            word_count = int(binary_message[14:19], 2)
                            if word_count == 0:
                                word_count = 32
                            result['word_count'] = word_count
                
        # Try to determine message type for all BC messages
        if not result.get('message_type'):
            # Default for BC if unclear
            result['message_type'] = 'mil_std_1553b_message'
            
        return result
        
    def _ensure_uuid_fields_in_metadata(self, result):
        """
        Ensure all UUID fields are properly preserved in metadata.
        
        This is critical for tracking message flows across the system,
        especially in the MIL-STD-1553B context where messages can be
        transformed multiple times.
        
        Args:
            result: Result dictionary with fields to process
            
        Returns:
            dict: Result with UUID fields ensured in metadata
        """
        # Initialize metadata if not present
        if 'metadata' not in result or not result['metadata']:
            result['metadata'] = {}
            
        # List of critical fields to preserve bidirectionally
        critical_fields = [
            # UUID fields
            'message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid', 'request_id',
            # Command identification fields
            'command_name', 'message_type', 'command_type',
            # Routing fields
            'destination', 'source_system', 'rt_address', 'sub_address'
        ]
        
        # Copy all critical fields to metadata (bidirectional preservation)
        for field in critical_fields:
            # Copy from top-level to metadata
            if field in result and result[field] is not None:
                result['metadata'][field] = result[field]
                self.logger.debug(f"[BC_EXTRACTOR] Preserved {field} in metadata: {result[field]}")
            
            # Copy from metadata to top-level if missing at top level
            elif field in result.get('metadata', {}) and result['metadata'][field] is not None:
                if field not in result or result[field] is None:
                    result[field] = result['metadata'][field]
                    self.logger.debug(f"[BC_EXTRACTOR] Promoted {field} from metadata to top level: {result[field]}")
        
        # Special handling for request_id (legacy field)
        if result.get('request_id') and not result.get('request_uuid'):
            result['request_uuid'] = result['request_id']
            result['metadata']['request_uuid'] = result['request_id']
            self.logger.debug(f"[BC_EXTRACTOR] Set request_uuid from request_id: {result['request_id']}")
            
        # Log the final state of critical fields
        self.logger.info(f"[BC_EXTRACTOR] Final request_id: {result.get('request_id')}")
        self.logger.info(f"[BC_EXTRACTOR] Final command_name: {result.get('command_name')}")
            
        return result
    
    def extract_all_fields(self, message, current_level=0):
        """
        Enhanced field extraction for BC messages.
        
        Adds special handling for status word extraction in BC context.
        
        Args:
            message: Any message format
            current_level: Current nesting level
            
        Returns:
            dict: Complete extracted fields with BC-specific enhancements
        """
        # Store the original message for critical field recovery
        original_message = message
        
        # Specialized handling for status words - common BC message type
        if isinstance(message, dict) and 'status_word' in message:
            # Enhanced status word handling for BC
            result = super().extract_all_fields(message, current_level)
            
            # Store the original message for field recovery
            result['original_message'] = original_message
            
            # Make sure command_name and request_id are preserved at all costs
            if 'command_name' in message:
                result['command_name'] = message['command_name']
                self.logger.info(f"[BC_EXTRACTOR] Preserved critical command_name in status word: {result['command_name']}")
            
            if 'request_id' in message:
                result['request_id'] = message['request_id']
                self.logger.info(f"[BC_EXTRACTOR] Preserved critical request_id in status word: {result['request_id']}")
            
            # Check metadata as well
            if isinstance(message.get('metadata'), dict):
                if not result.get('command_name') and message['metadata'].get('command_name'):
                    result['command_name'] = message['metadata']['command_name']
                    self.logger.info(f"[BC_EXTRACTOR] Extracted command_name from metadata: {result['command_name']}")
                
                if not result.get('request_id') and message['metadata'].get('request_id'):
                    result['request_id'] = message['metadata']['request_id']
                    self.logger.info(f"[BC_EXTRACTOR] Extracted request_id from metadata: {result['request_id']}")
                
            # Flag as status word
            result['is_status_word'] = True
            result['message_type'] = 'status_word'
            
            # Ensure critical fields are in metadata
            self._ensure_uuid_fields_in_metadata(result)
            
            return result
        
        # For all other messages
        result = super().extract_all_fields(message, current_level)
        
        # Store the original message for field recovery
        result['original_message'] = original_message
        
        # Ensure critical fields are properly preserved
        if isinstance(message, dict):
            # Direct field extraction
            for field in ['command_name', 'request_id', 'message_type', 'command_type']:
                if field in message and message[field] is not None:
                    result[field] = message[field]
                    self.logger.debug(f"[BC_EXTRACTOR] Preserved {field} from dict: {result[field]}")
        elif hasattr(message, 'command_name') or hasattr(message, 'request_id'):
            # Object attribute extraction
            for field in ['command_name', 'request_id', 'message_type', 'command_type']:
                if hasattr(message, field) and getattr(message, field) is not None:
                    result[field] = getattr(message, field)
                    self.logger.debug(f"[BC_EXTRACTOR] Preserved {field} from object: {result[field]}")
        
        # Ensure critical fields are in metadata
        self._ensure_uuid_fields_in_metadata(result)
        
        return result
        
def get_bc_message_extractor():
    """Get a new instance of BC_MessageExtractor."""
    return BC_MessageExtractor()
