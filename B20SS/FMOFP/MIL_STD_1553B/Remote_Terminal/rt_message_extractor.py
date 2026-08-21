"""
Remote Terminal Message Extractor

Extends the Universal Message Extractor with RT-specific field extraction logic.
Specialized handling for MIL-STD-1553B message formats in the Remote Terminal context.
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
    logger = logging.getLogger('rt_message_extractor')

class RT_MessageExtractor(UniversalMessageExtractor):
    """
    Remote Terminal specific message extractor with specialized handling for RT messages.
    Enhances the base extractor with RT-specific field processing and validation.
    """
    
    def __init__(self, **kwargs):
        """Initialize RT-specific message extractor."""
        super().__init__(**kwargs)
        self.logger.info("RT_MessageExtractor initialized")
    
    def _process_critical_fields(self, result):
        """
        RT-specific processing for critical fields.
        
        Enhances the base processing with special handling for:
        - RT addressing
        - System type determination
        - RT-specific message types
        - UUID field preservation
        - Command name standardization
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with RT-specific processing applied
        """
        # First apply base processing
        result = super()._process_critical_fields(result)
        
        # Ensure UUID fields are preserved in metadata for resilient tracking
        self._ensure_uuid_fields_in_metadata(result)
        
        # RT-specific field handling
        # Handle subaddress for RT messages
        if 'sub_address' not in result and 'binary_data' in result:
            binary = result.get('binary_data')
            if isinstance(binary, str) and len(binary) >= 13:
                result['sub_address'] = int(binary[8:13], 2)
                self.logger.info(f"[RT_EXTRACTOR] Extracted subaddress: {result['sub_address']}")
        
        # Determine system type for RT messages
        if result.get('rt_address') and not result.get('source_system'):
            rt_address = result['rt_address']
            
            # Map RT addresses to system types
            rt_system_map = {
                1: 'avionics',
                2: 'communications',
                3: 'engine_management',
                4: 'environmental_control',
                5: 'flight_control',
                6: 'mission_planning',
                7: 'navigation',
                8: 'power_management',
                9: 'radar_management',
                10: 'sensor_management',
                11: 'display_system'
            }
            
            if rt_address in rt_system_map:
                result['source_system'] = rt_system_map[rt_address]
                self.logger.info(f"[RT_EXTRACTOR] Mapped RT {rt_address} to system: {result['source_system']}")
        
        # Handle specific radar types
        if result.get('source_system') == 'radar_management' and result.get('sub_address'):
            subaddress = result['sub_address']
            
            # Map subaddresses to radar types
            radar_map = {
                1: 'weather_radar',
                2: 'tfr_radar',
                3: 'sar_radar',
                4: 'targeting_radar',
                5: 'aewc_radar'
            }
            
            if subaddress in radar_map:
                result['radar_type'] = radar_map[subaddress]
                self.logger.info(f"[RT_EXTRACTOR] Determined radar_type: {result['radar_type']}")
                
        # Ensure command_name is properly set for RT messages
        if not result.get('command_name') and result.get('message_type'):
            message_type = result['message_type'].lower()
            
            # Define mappings for common message types
            if 'precipitation' in message_type or 'precip' in message_type:
                result['command_name'] = 'RADAR_PRECIPITATION_DATA'
            elif 'vil' in message_type:
                result['command_name'] = 'RADAR_VIL_DATA'
            elif 'mode' in message_type and 'change' in message_type:
                result['command_name'] = 'RADAR_MODE_CHANGE'
                
            # Add radar type prefix if available
            if result.get('radar_type') and result.get('command_name'):
                radar_type = result['radar_type'].upper()
                command_name = result['command_name']
                
                # Only add prefix if not already present
                if not command_name.startswith(radar_type):
                    result['command_name'] = f"{radar_type}_{command_name.split('_', 1)[1]}"
                    
        return result
        
    def _extract_from_binary(self, binary_message):
        """
        Enhanced RT-specific extraction from binary message.
        
        Extends base extraction with specialized handling for MIL-STD-1553B
        command words, status words, and data words in the RT context.
        
        Args:
            binary_message: Binary message string
            
        Returns:
            dict: Extracted fields with RT-specific enhancements
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
                    self.logger.info(f"[RT_EXTRACTOR] Extracted RT address: {result['rt_address']}")
                    
                    # Also set subaddress if possible from bits 9-13
                    if len(binary_message) >= 14:
                        result['sub_address'] = int(binary_message[9:14], 2)
                        self.logger.info(f"[RT_EXTRACTOR] Extracted subaddress: {result['sub_address']}")
                

        
        # RT-specific binary message handling
        if isinstance(binary_message, str) and binary_message.startswith('100'):  # Command or status word
            # For RT, we're primarily interested in command words
            if result.get('message_type') == 'command_word':
                # Check T/R bit (bit 8) - critical for RT operation
                if len(binary_message) >= 9:
                    tr_bit = binary_message[8:9]
                    result['is_transmit'] = (tr_bit == '1')
                    result['is_receive'] = (tr_bit == '0')
                    
                    if result['is_transmit']:
                        result['rt_action'] = 'transmit'
                        result['message_direction'] = 'rt_to_bc'
                    else:
                        result['rt_action'] = 'receive'
                        result['message_direction'] = 'bc_to_rt'
                
                # Extract subaddress (bits 9-13)
                if len(binary_message) >= 14:
                    result['sub_address'] = int(binary_message[9:14], 2)
                    
                    # Check for mode codes
                    if result['sub_address'] == 0 or result['sub_address'] == 31:
                        result['is_mode_code'] = True
                        
                        # Extract mode code (bits 14-18)
                        if len(binary_message) >= 19:
                            mode_code = int(binary_message[14:19], 2)
                            result['mode_code'] = mode_code
                            
                            # Interpret mode codes
                            mode_code_map = {
                                0: 'dynamic_bus_control',
                                1: 'synchronize',
                                2: 'transmit_status_word',
                                3: 'initiate_self_test',
                                4: 'transmitter_shutdown',
                                5: 'override_transmitter_shutdown',
                                6: 'inhibit_terminal_flag',
                                7: 'override_inhibit_terminal_flag',
                                8: 'reset_remote_terminal',
                                16: 'transmit_vector_word',
                                17: 'synchronize_with_data',
                                18: 'transmit_last_command',
                                19: 'transmit_bit_word',
                                20: 'selected_transmitter_shutdown',
                                21: 'override_selected_transmitter_shutdown'
                            }
                            
                            result['mode_code_name'] = mode_code_map.get(mode_code, f"unknown_mode_{mode_code}")
                            self.logger.info(f"[RT_EXTRACTOR] Identified mode code: {result['mode_code_name']}")
                    else:
                        # Regular data transfer command
                        result['is_mode_code'] = False
                        
                        # Extract word count (bits 14-18)
                        if len(binary_message) >= 19:
                            word_count = int(binary_message[14:19], 2)
                            # In 1553B, word count of 0 means 32 words
                            if word_count == 0:
                                word_count = 32
                            result['word_count'] = word_count
                            self.logger.info(f"[RT_EXTRACTOR] Data transfer command, word count: {word_count}")
            
            # For RT, status words are responses to BC
            elif result.get('message_type') == 'status_word':
                # Status words already have base processing
                # Add RT-specific flags for tracking response type
                if result.get('status_flags'):
                    flags = result['status_flags']
                    
                    # RT tracking of responses
                    result['is_rt_response'] = True
                    if result.get('status_message_error'):
                        result['response_type'] = 'error'
                    elif result.get('status_busy'):
                        result['response_type'] = 'busy'
                    elif result.get('status_service_request'):
                        result['response_type'] = 'service_request'
                    else:
                        result['response_type'] = 'normal'
        
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
            
        # List of UUID fields to check
        uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid', 'request_id']
        
        # Copy all UUID fields to metadata
        for field in uuid_fields:
            if field in result and result[field]:
                result['metadata'][field] = result[field]
                self.logger.debug(f"[RT_EXTRACTOR] Preserved {field} in metadata: {result[field]}")
        
        # Ensure command_name is also preserved in metadata
        if result.get('command_name'):
            result['metadata']['command_name'] = result['command_name']
            self.logger.debug(f"[RT_EXTRACTOR] Preserved command_name in metadata: {result['command_name']}")
            
        # Ensure message_type is preserved in metadata
        if result.get('message_type'):
            result['metadata']['message_type'] = result['message_type']
            
        # Special handling for request_id (legacy field)
        if result.get('request_id') and not result.get('request_uuid'):
            result['request_uuid'] = result['request_id']
            result['metadata']['request_uuid'] = result['request_id']
            self.logger.debug(f"[RT_EXTRACTOR] Set request_uuid from request_id: {result['request_id']}")
            
        return result

def get_rt_message_extractor():
    """Get a new instance of RT_MessageExtractor."""
    return RT_MessageExtractor()
