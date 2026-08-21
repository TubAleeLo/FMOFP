"""
Universal Message Extractor

Provides a robust utility for extracting all fields from any message format
in the FMOFP system. Guarantees consistency of critical fields while
dynamically handling any additional fields present in messages.

This class extracts and normalizes message fields from various formats including:
- Dictionary messages
- Objects with attributes
- MIL-STD-1553B binary messages
- Sequences of messages
"""

import time
import uuid
import traceback
from typing import Dict, Any, List, Tuple, Union, Optional

# Import system logger
try:
    from FMOFP.Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger('universal_message_extractor')

class UniversalMessageExtractor:
    """
    Universal message extraction utility that works with any message format.
    Guarantees consistent field extraction regardless of input format.
    Dynamically handles any fields present in messages.
    """
    
    # Core fields that must be guaranteed in every message
    GUARANTEED_FIELDS = {
        # Core message identifiers
        'message_type': None,
        'command_type': None,
        'command_name': None,
        
        # UUID fields
        'message_uuid': None,
        'request_uuid': None,
        'query_uuid': None,
        'status_uuid': None,
        'command_uuid': None,
        
        # Addressing fields 
        'rt_address': None,
        'sub_address': None,
        'source_system': None,
        'source': None,
        'destination': None,
        
        # UUID addressing fields
        'sending_system_uuid': None,
        'destination_uuid': None,
        'source_uuid': None,
        
        # Data fields
        'data': None,
        'timestamp': None,
        'metadata': {}
    }
    
    # Field resolution strategies
    FIELD_RESOLUTION_STRATEGIES = {
        'KEEP_FIRST': 'keep_first',      # Keep first encountered value (default)
        'KEEP_LAST': 'keep_last',        # Keep last encountered value
        'RAISE_ERROR': 'raise_error',    # Raise error on conflict
        'MERGE': 'merge'                 # Attempt to merge values (for dicts/lists)
    }
    
    def __init__(self, 
                 field_resolution_strategy='raise_error',
                 include_original_message=True, 
                 max_nesting_level=5):
        """
        Initialize extractor with configuration options.
        
        Args:
            field_resolution_strategy: Strategy for resolving field conflicts
                - 'keep_first': Keep first encountered value
                - 'keep_last': Keep last encountered value
                - 'raise_error': Raise error on conflict (default)
                - 'merge': Try to merge values (for dicts/lists)
            include_original_message: Whether to include original message in result
            max_nesting_level: Maximum nesting level for dict/object extraction
        """
        self.field_resolution_strategy = field_resolution_strategy
        self.include_original_message = include_original_message
        self.max_nesting_level = max_nesting_level
        self.logger = self._get_logger()
    
    def _get_logger(self):
        """Get system logger."""
        try:
            from FMOFP.Utils.logger.sys_logger import get_logger
            return get_logger()
        except ImportError:
            import logging
            return logging.getLogger('message_extractor')
            
    def extract_all_fields(self, message, current_level=0):
        """
        Extract all available fields from any message type.
        Returns a complete dictionary with all possible fields.
        
        Args:
            message: Any message format (dict, object, binary, etc.)
            current_level: Current nesting level for recursion control
            
        Returns:
            dict: Complete normalized message with all fields
        """
        # Initialize result with guaranteed fields
        result = self.GUARANTEED_FIELDS.copy()
        
        # Add extraction timestamp
        import time
        result['extraction_timestamp'] = time.time()
        
        # Normalize string frames into dictionary format before processing
        # This prevents downstream code from trying to call .get() on strings
        if isinstance(message, str):
            # Analyze string to determine if it's a binary message
            if self._is_binary_message(message):
                # If it's a binary status/command word (starts with 100)
                if message.startswith('100'):
                    # Extract RT address for status words (bits 3-7)
                    rt_address = None
                    if len(message) >= 8:
                        rt_address = int(message[3:8], 2)
                    
                    message = {
                        'status_word': message,
                        'binary_data': message,
                        'raw_frame': message,
                        'message_type': 'status_word',
                        'rt_address': rt_address
                    }
                    self.logger.info(f"Normalized binary status word with RT address: {rt_address}")
                # If it's a binary data word (starts with 001)
                elif message.startswith('001'):
                    message = {
                        'data_word': message,
                        'binary_data': message,
                        'raw_frame': message,
                        'message_type': 'data_word'
                    }
                    self.logger.info(f"Normalized binary data word")
                else:
                    # Other binary format
                    message = {
                        'binary_data': message,
                        'raw_frame': message,
                        'message_type': 'binary_data'
                    }
            else:
                # Not a valid binary message, still wrap as dictionary
                message = {
                    'raw_data': message,
                    'raw_frame': message,
                    'message_type': 'raw_text'
                }
            

            
        # Apply extraction strategies based on now-normalized message type
        extracted_fields = {}
        
        try:
            if isinstance(message, dict):
                extracted_fields = self._extract_from_dict(message, current_level)
            elif hasattr(message, '__dict__'):
                extracted_fields = self._extract_from_object(message, current_level)
            elif isinstance(message, (list, tuple)) and len(message) > 0:
                extracted_fields = self._extract_from_sequence(message)
            else:
                # Should be rare now since we normalized strings above
                self.logger.warning(f"Unrecognized message format: {type(message)}")
                extracted_fields = {'data': message}
        except Exception as e:
            self.logger.error(f"Error in extraction: {str(e)}")
            extracted_fields = {'data': message, 'extraction_error': str(e)}
        
        # Merge extracted fields into result, using resolution strategy for conflicts
        result = self._merge_fields(result, extracted_fields)
        
        # Keep original message if requested
        if self.include_original_message:
            result['original_message'] = message
            
        # Special handling for critical fields
        result = self._process_critical_fields(result)
        

        
        # Consolidate metadata from various sources into a single metadata dict
        result = self._consolidate_metadata(result)
        
        return result

    def _is_binary_message(self, message):
        """Check if a string message is a binary MIL-STD-1553B message."""
        # Binary message is 20 chars of 0s and 1s
        return (len(message) >= 20 and 
                all(c in '01' for c in message[:20]))
    
    def _extract_from_dict(self, message_dict, current_level=0):
        """
        Extract fields from dictionary message format.
        Handles nested dictionaries up to max_nesting_level.
        """
        if current_level >= self.max_nesting_level:
            return {'data': message_dict}
            
        result = {}
        
        # Extract all direct fields
        for key, value in message_dict.items():
            # Handle nested dictionaries
            if isinstance(value, dict) and current_level < self.max_nesting_level:
                nested_fields = self._extract_from_dict(value, current_level + 1)
                # Flatten or preserve structure based on key
                if key in ('metadata', 'additional_info'):
                    # For known metadata fields, flatten
                    for nested_key, nested_value in nested_fields.items():
                        if nested_key not in result or result[nested_key] is None:
                            result[nested_key] = nested_value
                        else:
                            # Apply resolution strategy for conflicts
                            result[nested_key] = self._resolve_field_conflict(
                                nested_key, result[nested_key], nested_value)
                else:
                    # For regular field, keep structure
                    result[key] = nested_fields
            else:
                # Direct field
                result[key] = value
                
        return result
    
    def _extract_from_object(self, message_obj, current_level=0):
        """
        Extract fields from object with attributes.
        Handles nested objects up to max_nesting_level.
        """
        if current_level >= self.max_nesting_level:
            return {'data': message_obj}
            
        result = {}
        
        # Get all attributes except magic methods
        for attr_name in dir(message_obj):
            if attr_name.startswith('__') or callable(getattr(message_obj, attr_name)):
                continue
                
            try:
                value = getattr(message_obj, attr_name)
                
                # Handle nested objects
                if hasattr(value, '__dict__') and current_level < self.max_nesting_level:
                    nested_fields = self._extract_from_object(value, current_level + 1)
                    # Flatten or preserve structure based on attribute name
                    if attr_name in ('metadata', 'additional_info'):
                        # For known metadata fields, flatten
                        for nested_key, nested_value in nested_fields.items():
                            if nested_key not in result or result[nested_key] is None:
                                result[nested_key] = nested_value
                            else:
                                # Apply resolution strategy for conflicts
                                result[nested_key] = self._resolve_field_conflict(
                                    nested_key, result[nested_key], nested_value)
                    else:
                        # For regular field, keep structure
                        result[attr_name] = nested_fields
                else:
                    # Direct attribute
                    result[attr_name] = value
            except AttributeError:
                # Skip attributes that can't be accessed
                continue
                
        return result
    
    def _extract_from_binary(self, binary_message):
        """
        Extract fields from binary MIL-STD-1553B message.
        Uses MetadataCodec for decoding metadata.
        """
        result = {}
        
        # Basic parsing of MIL-STD-1553B binary message
        try:
            # Identify message type based on sync pattern
            if binary_message.startswith('100'):
                # Command or status word
                result['is_command_or_status_word'] = True
                
                # Extract RT address (bits 3-7)
                if len(binary_message) >= 8:
                    result['rt_address'] = int(binary_message[3:8], 2)
                
                # Check if it's a status word
                if 'status_word' in str(binary_message) or binary_message[8:9] == '1':
                    result['message_type'] = 'status_word'
                else:
                    result['message_type'] = 'command_word'
                    
                # Store full binary representation
                result['binary_data'] = binary_message
                
            elif binary_message.startswith('001'):
                # Data word
                result['is_data_word'] = True
                result['message_type'] = 'data_word'
                result['binary_data'] = binary_message
                
                # Extract data value (bits 3-18)
                if len(binary_message) >= 19:
                    result['data_value'] = int(binary_message[3:19], 2)
            
            # Try to use MetadataCodec if available
            try:
                from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec
                # Check if this might be metadata
                if binary_message.startswith('001') and len(binary_message) >= 16:
                    # Convert to list of binary strings if needed
                    data_words = [binary_message]
                    if isinstance(binary_message, str) and len(binary_message) > 20:
                        # Split into 20-bit words
                        data_words = [binary_message[i:i+20] for i in range(0, len(binary_message), 20)]
                    
                    # Try to decode metadata
                    decoded_metadata = MetadataCodec.decode_metadata(data_words)
                    if decoded_metadata:
                        self.logger.info(f"Decoded metadata from binary: {decoded_metadata}")
                        # Update result with decoded metadata
                        for key, value in decoded_metadata.items():
                            if key not in result or result[key] is None:
                                result[key] = value
                            else:
                                # Apply resolution strategy for conflicts
                                result[key] = self._resolve_field_conflict(
                                    key, result[key], value)
            except (ImportError, Exception) as e:
                self.logger.warning(f"MetadataCodec not available or error: {e}")
                
        except Exception as e:
            self.logger.error(f"Error extracting from binary: {e}")
            
        return result
    
    def _extract_from_sequence(self, message_sequence):
        """
        Extract fields from a sequence (list, tuple) of messages.
        Handles both homogeneous (same type) and heterogeneous sequences.
        """
        result = {}
        
        # Extract fields from the first item as primary
        if len(message_sequence) > 0:
            first_item = message_sequence[0]
            result = self.extract_all_fields(first_item)
            
            # Store full sequence as data
            result['data'] = message_sequence
            
            # Check if this might be a sequence of data words
            if (all(isinstance(item, str) for item in message_sequence) and 
                all(self._is_binary_message(item) for item in message_sequence if isinstance(item, str))):
                try:
                    # Try to use MetadataCodec if available
                    try:
                        from FMOFP.MIL_STD_1553B.metadata_codec import MetadataCodec
                        decoded_metadata = MetadataCodec.decode_metadata(message_sequence)
                        if decoded_metadata:
                            self.logger.info(f"Decoded metadata from binary sequence: {decoded_metadata}")
                            # Update result with decoded metadata
                            for key, value in decoded_metadata.items():
                                if key not in result or result[key] is None:
                                    result[key] = value
                                else:
                                    # Apply resolution strategy for conflicts
                                    result[key] = self._resolve_field_conflict(
                                        key, result[key], value)
                    except (ImportError, Exception) as e:
                        self.logger.warning(f"MetadataCodec not available or error: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing binary sequence: {e}")
        
        return result
    
    def _merge_fields(self, target, source):
        """
        Merge fields from source into target using configured resolution strategy.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
            
        Returns:
            dict: Merged dictionary
        """
        if not source:
            return target
            
        result = target.copy()
        
        for key, value in source.items():
            if key not in result or result[key] is None:
                # No conflict, just add the field
                result[key] = value
            elif result[key] == value:
                # Values match, no conflict
                continue
            else:
                # Values don't match, apply resolution strategy
                try:
                    result[key] = self._resolve_field_conflict(key, result[key], value)
                except ValueError as e:
                    # If error raised, log and keep target value
                    self.logger.warning(f"Field conflict not resolved: {e}")
                
        return result
    
    def _resolve_field_conflict(self, field_name, value1, value2):
        """
        Resolve conflict between two values for the same field.
        
        Args:
            field_name: Name of the field with conflict
            value1: First value
            value2: Second value
            
        Returns:
            Resolved value based on strategy
            
        Raises:
            ValueError: If resolution strategy is 'raise_error' and values differ
        """
        # If values are equal, no conflict
        if value1 == value2:
            return value1
            
        # Special handling for timestamp - always keep original message timestamp
        if field_name == 'timestamp':
            # Keep whichever timestamp appears to be from the original message
            # (assume the earlier timestamp is the original message timestamp)
            try:
                if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
                    return min(value1, value2)  # Keep the earlier timestamp
                elif value1 is None:
                    return value2
                elif value2 is None:
                    return value1
            except Exception as e:
                self.logger.warning(f"Error comparing timestamps: {e}, keeping first value")
                return value1
            
        # Apply resolution strategy
        if self.field_resolution_strategy == 'keep_first':
            return value1
        elif self.field_resolution_strategy == 'keep_last':
            return value2
        elif self.field_resolution_strategy == 'merge':
            # Try to merge values
            if isinstance(value1, dict) and isinstance(value2, dict):
                # For dictionaries, merge recursively
                merged = value1.copy()
                for k, v in value2.items():
                    if k not in merged:
                        merged[k] = v
                    elif merged[k] == v:
                        continue
                    else:
                        # Recursive merge for nested dictionaries
                        if isinstance(merged[k], dict) and isinstance(v, dict):
                            merged[k] = self._resolve_field_conflict(f"{field_name}.{k}", merged[k], v)
                        else:
                            # Cannot merge non-dict values, fall back to keep_first
                            pass
                return merged
            elif isinstance(value1, list) and isinstance(value2, list):
                # For lists, concatenate
                return value1 + [x for x in value2 if x not in value1]
            else:
                # Cannot merge, fall back to keep_first
                self.logger.warning(
                    f"Cannot merge values for field '{field_name}', keeping first value")
                return value1
        else:  # 'raise_error'
            error_msg = (f"Field conflict for '{field_name}': "
                        f"'{value1}' vs '{value2}'")
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _process_critical_fields(self, result):
        """
        Process critical fields to ensure they meet system requirements.
        Applies specialized handling for key fields like command_name and UUID fields.
        Uses message_definitions.py as the single source of truth.
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with processed critical fields
        """
        # Import message definitions
        try:
            from FMOFP.local_messaging.messageConfigurations.message_definitions import (
                MessageDefinitions, MessageHeaders
            )
            using_message_definitions = True
        except ImportError:
            using_message_definitions = False
            self.logger.warning("Could not import message_definitions, using fallback standardization")
        
        # Ensure command_name follows expected format
        if result.get('command_name'):
            # Convert to uppercase for consistency
            result['command_name'] = str(result['command_name']).upper()
            
            # Use message definitions if available
            if using_message_definitions:
                # Get standard command names from message definitions
                try:
                    standard_command_names = {cmd.value: cmd.value for cmd in MessageDefinitions.CommandNames}
                    
                    # Try to match standard command names
                    for standard_name in standard_command_names:
                        if standard_name in result['command_name']:
                            result['command_name'] = standard_name
                            self.logger.info(f"Standardized command_name to {standard_name}")
                            break
                except Exception as e:
                    self.logger.warning(f"Error using MessageDefinitions.CommandNames: {e}")
            else:
                # Fallback to hardcoded standard names
                standard_command_names = {
                    'WEATHER_RADAR_MODE_CHANGE': 'WEATHER_RADAR_MODE_CHANGE',
                    'DISPLAY_PRECIPITATION_DATA': 'DISPLAY_PRECIPITATION_DATA',
                    'DISPLAY_VIL_DATA': 'DISPLAY_VIL_DATA',
                    'RADAR_PRECIPITATION_DATA': 'RADAR_PRECIPITATION_DATA',
                    'WEATHER_RADAR_PRECIPITATION_DATA': 'WEATHER_RADAR_PRECIPITATION_DATA',
                    'WEATHER_RADAR_VIL_DATA': 'WEATHER_RADAR_VIL_DATA'
                }
                
                # Try to match standard command names
                for standard_name in standard_command_names:
                    if standard_name in result['command_name']:
                        result['command_name'] = standard_name
                        break
        
        # Process UUID fields according to message purpose
        self._process_uuid_fields(result)
        
        # Infer message_type from command_name if missing
        if not result.get('message_type') and result.get('command_name'):
            # Use message definitions if available
            if using_message_definitions:
                try:
                    # Build reverse mapping from command name to message type
                    cmd_to_msg_type = {}
                    for msg_type, cmd_name in MessageDefinitions.MESSAGE_TYPE_TO_COMMAND_NAME.items():
                        cmd_to_msg_type[cmd_name.value] = msg_type.value
                    
                    cmd_name = result['command_name']
                    if cmd_name in cmd_to_msg_type:
                        result['message_type'] = cmd_to_msg_type[cmd_name]
                        self.logger.info(f"Inferred message_type '{result['message_type']}' from command_name '{cmd_name}'")
                except Exception as e:
                    self.logger.warning(f"Error using MessageDefinitions.MESSAGE_TYPE_TO_COMMAND_NAME: {e}")
            
            # Fallback to simple pattern matching
            if not result.get('message_type'):
                cmd_name = result['command_name']
                if 'MODE_CHANGE' in cmd_name:
                    result['message_type'] = 'mode_change'
                elif 'PRECIPITATION' in cmd_name:
                    result['message_type'] = 'precipitation_data'
                elif 'VIL' in cmd_name:
                    result['message_type'] = 'vil_data'
                    
        # Infer command_type from message_type if missing
        if not result.get('command_type') and result.get('message_type'):
            msg_type = result['message_type'].lower()
            if 'mode_change' in msg_type:
                result['command_type'] = 'mode_change'
            elif 'precipitation' in msg_type:
                result['command_type'] = 'precipitation_data'
            elif 'vil' in msg_type:
                result['command_type'] = 'vil_data'
            elif 'echo' in msg_type:
                result['command_type'] = 'echo_top_data'
            # Use REQUEST vs RESPONSE patterns to determine more specific command_type
            elif 'request' in msg_type:
                result['command_type'] = 'data_request'
            elif 'response' in msg_type:
                result['command_type'] = 'data_response'
                
        return result
        
    def _process_uuid_fields(self, result):
        """
        Process and standardize UUID fields in the message.
        Ensures appropriate UUID fields are populated based on message purpose.
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with processed UUID fields
        """
        # Determine message purpose to set primary UUID field
        message_purpose = self._determine_message_purpose(result)
        
        # Based on purpose, ensure the appropriate UUID is populated
        if message_purpose == 'request':
            self._ensure_request_uuid(result)
        elif message_purpose == 'query':
            self._ensure_query_uuid(result)
        elif message_purpose == 'status':
            self._ensure_status_uuid(result)
        elif message_purpose == 'command':
            self._ensure_command_uuid(result)
        
        # Always ensure message_uuid is present
        if not result.get('message_uuid'):
            # Try to use an appropriate field based on purpose
            purpose_to_field = {
                'request': 'request_uuid',
                'query': 'query_uuid',
                'status': 'status_uuid',
                'command': 'command_uuid'
            }
            
            field_to_check = purpose_to_field.get(message_purpose)
            if field_to_check and result.get(field_to_check):
                result['message_uuid'] = result[field_to_check]
                self.logger.info(f"Set message_uuid from {field_to_check}: {result['message_uuid']}")

        
        # Ensure all UUIDs are strings
        uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid']
        for field in uuid_fields:
            if field in result and result[field] is not None:
                result[field] = str(result[field])
        
        return result
        
    def _determine_message_purpose(self, result):
        """Determine the purpose of the message (request, query, status, command)."""
        # Check message_type field
        if result.get('message_type'):
            msg_type = result['message_type'].lower()
            if 'request' in msg_type:
                return 'request'
            elif 'query' in msg_type:
                return 'query'
            elif 'status' in msg_type or 'response' in msg_type:
                return 'status'
            elif 'command' in msg_type or 'mode_change' in msg_type:
                return 'command'
            
        # Check command_type field as backup
        if result.get('command_type'):
            cmd_type = result['command_type'].lower()
            if 'request' in cmd_type:
                return 'request'
            elif 'query' in cmd_type:
                return 'query'
            elif 'status' in cmd_type or 'response' in cmd_type:
                return 'status'
            elif 'command' in cmd_type or 'mode_change' in cmd_type:
                return 'command'
        
        # Default to 'request' if cannot determine
        return 'request'
        
    def _ensure_request_uuid(self, result):
        """Ensure request_uuid is populated."""
        if not result.get('request_uuid'):
            # Try to use existing fields like request_id
            if result.get('request_id'):
                result['request_uuid'] = result['request_id']
                self.logger.info(f"Set request_uuid from request_id: {result['request_uuid']}")

        return result
        
    def _ensure_query_uuid(self, result):
        """Ensure query_uuid is populated."""
        if not result.get('query_uuid'):
            # Try to use existing fields like request_id or request_uuid
            if result.get('request_uuid'):
                result['query_uuid'] = result['request_uuid']
                self.logger.info(f"Set query_uuid from request_uuid: {result['query_uuid']}")
            elif result.get('request_id'):
                result['query_uuid'] = result['request_id']
                self.logger.info(f"Set query_uuid from request_id: {result['query_uuid']}")

        return result
        
    def _ensure_status_uuid(self, result):
        """Ensure status_uuid is populated."""
        if not result.get('status_uuid'):
            # Try to use existing fields as appropriate
            if result.get('request_uuid'):
                result['status_uuid'] = result['request_uuid']
                self.logger.info(f"Set status_uuid from request_uuid: {result['status_uuid']}")
            elif result.get('request_id'):
                result['status_uuid'] = result['request_id']
                self.logger.info(f"Set status_uuid from request_id: {result['status_uuid']}")

        return result
        
    def _ensure_command_uuid(self, result):
        """Ensure command_uuid is populated."""
        if not result.get('command_uuid'):
            # Try to use existing fields as appropriate
            if result.get('request_uuid'):
                result['command_uuid'] = result['request_uuid']
                self.logger.info(f"Set command_uuid from request_uuid: {result['command_uuid']}")
            elif result.get('request_id'):
                result['command_uuid'] = result['request_id']
                self.logger.info(f"Set command_uuid from request_id: {result['command_uuid']}")
        return result
    
    def _consolidate_metadata(self, result):
        """
        Consolidate metadata from various sources into a single metadata dictionary.
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with consolidated metadata
        """
        # Initialize metadata dictionary if not present
        if 'metadata' not in result or not result['metadata']:
            result['metadata'] = {}
            
        # Fields that should be copied to metadata for preservation
        # This ensures critical fields are available in both places
        preserve_fields = [
            'command_name', 'request_id', 'message_type', 'command_type',
            'rt_address', 'sub_address', 'source_system', 'destination'
        ]
        
        for field in preserve_fields:
            if field in result and result[field] is not None:
                result['metadata'][field] = result[field]
                
        # Check for additional_info and merge into metadata
        if 'additional_info' in result and isinstance(result['additional_info'], dict):
            for key, value in result['additional_info'].items():
                if key not in result['metadata'] or result['metadata'][key] is None:
                    result['metadata'][key] = value
                else:
                    # Apply resolution strategy for conflicts
                    try:
                        result['metadata'][key] = self._resolve_field_conflict(
                            key, result['metadata'][key], value)
                    except ValueError:
                        # If error raised, keep metadata value
                        pass
                        
        return result

def get_universal_message_extractor():
    """Get a new instance of the UniversalMessageExtractor."""
    return UniversalMessageExtractor()
