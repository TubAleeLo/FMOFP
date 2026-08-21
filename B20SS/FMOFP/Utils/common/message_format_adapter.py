"""
Message Format Adapter

Provides utilities for adapting various message formats to a standard internal format.
Enhances modularity and scalability by normalizing message structures.
"""

import time
from typing import Any, Dict, List

from Utils.logger.sys_logger import get_logger

logger = get_logger()

class MessageFormatAdapter:
    """
    Adapts various message formats to a standard internal format.
    
    This adapter allows the system to handle any message format by normalizing
    it to a consistent internal representation, enhancing modularity and scalability.
    """
    
    @staticmethod
    def normalize_message(message: Any) -> Dict[str, Any]:
        """
        Convert any message format to a standard internal dictionary using message definitions.
        
        Args:
            message: The message to normalize, can be any type
            
        Returns:
            Dict[str, Any]: A normalized message dictionary with standard fields
        """
        try:
            # Import message definitions if available
            try:
                from FMOFP.local_messaging.messageConfigurations.message_definitions import (
                    MessageDefinitions, MessageHeaders, MessagePriority, MessageStatus
                )
                using_message_definitions = True
            except ImportError:
                using_message_definitions = False
                logger.warning("Could not import message_definitions, using fallback normalization")
            
            # Initialize standard message structure with UUID fields
            normalized = {
                # Basic fields
                'message_header': None,
                'command_type': None,
                'command_name': None,
                'message_type': None,
                'data': None,
                'timestamp': time.time(),
                
                # UUID fields
                'message_uuid': None,
                'request_uuid': None,
                'query_uuid': None,
                'status_uuid': None,
                'command_uuid': None,
                
                # Address fields
                'sending_system': None,
                'destination': None,
                'source': None,
                'source_system': None,
                'rt_address': None,
                'sub_address': None,
                
                # Status fields
                'priority': "normal",
                'status': "pending",
                
                # Metadata container
                'metadata': {}
            }
            
            # Handle dictionary messages
            if isinstance(message, dict):
                # Copy all fields directly - don't lose any information
                for key, value in message.items():
                    normalized[key] = value
                
                # Extract metadata from various fields
                for meta_field in ['additional_info', 'metadata', 'info']:
                    if meta_field in message and isinstance(message[meta_field], dict):
                        normalized['metadata'].update(message[meta_field])
                
                # Handle special case for data field
                if 'data' not in message and 'payload' in message:
                    normalized['data'] = message['payload']
                
                # Special handling for UUID fields
                MessageFormatAdapter._ensure_uuid_fields(normalized, message)
                    
                # Handle special case for message_type field
                if not normalized.get('message_type'):
                    # Try known alternate field names
                    for type_field in ['messageType', 'type', 'msg_type']:
                        if type_field in message:
                            normalized['message_type'] = message[type_field]
                            break
                    
                    # Try to infer message type from other fields
                    if not normalized.get('message_type') and 'message_header' in message:
                        normalized['message_type'] = message['message_header']
                    
                    # If we have command_name but no message_type, try to infer it
                    if not normalized.get('message_type') and normalized.get('command_name'):
                        normalized['message_type'] = MessageFormatAdapter._infer_message_type_from_command_name(
                            normalized['command_name'], using_message_definitions)
                
            # Handle object messages with attributes
            else:
                # Extract standard fields from attributes
                for field in normalized.keys():
                    if hasattr(message, field):
                        normalized[field] = getattr(message, field)
                
                # Extract metadata from various attribute patterns
                for meta_field in ['additional_info', 'metadata', 'info']:
                    if hasattr(message, meta_field):
                        meta_value = getattr(message, meta_field)
                        if isinstance(meta_value, dict):
                            normalized['metadata'].update(meta_value)
                
                # Handle special case for data field
                if normalized['data'] is None and hasattr(message, 'payload'):
                    normalized['data'] = getattr(message, 'payload')
                
                # Handle special case for request_id field
                if normalized['request_id'] is None:
                    for id_field in ['requestId', 'request_uuid', 'id', 'uuid']:
                        if hasattr(message, id_field):
                            normalized['request_id'] = getattr(message, id_field)
                            break
                
                # Handle special case for message_type field
                if normalized['message_type'] is None:
                    for type_field in ['messageType', 'type', 'msg_type']:
                        if hasattr(message, type_field):
                            normalized['message_type'] = getattr(message, type_field)
                            break
                    
                    # Try to infer message type from other fields
                    if not normalized['message_type'] and hasattr(message, 'message_header'):
                        normalized['message_type'] = getattr(message, 'message_header')
                
                # Try to infer message type from class name
                if not normalized['message_type'] and hasattr(message, '__class__'):
                    class_name = message.__class__.__name__
                    normalized['message_type'] = class_name
            
            # Perform message type inference if still not determined
            if not normalized['message_type']:
                normalized['message_type'] = MessageFormatAdapter._infer_message_type(message)
            
            # Log the normalized message structure
            logger.debug(f"Normalized message: {normalized}")
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing message: {str(e)}")
            # Return a basic normalized message with error info
            return {
                'request_id': None,
                'data': message,
                'message_type': None,
                'command_type': None,
                'timestamp': time.time(),
                'metadata': {'error': f"Normalization failed: {str(e)}"}
            }
    
    @staticmethod
    def _ensure_uuid_fields(normalized, message):
        """
        Ensure all UUID fields are properly populated and synchronized.
        
        Args:
            normalized: The normalized message dict being built
            message: The original message being processed
            
        Returns:
            None (modifies normalized dict in place)
        """
        import uuid
        
        # Handle request_id to request_uuid mapping (legacy support)
        if not normalized.get('request_uuid') and normalized.get('request_id'):
            normalized['request_uuid'] = normalized['request_id']
            logger.debug(f"Set request_uuid from request_id: {normalized['request_uuid']}")
        
        # Try to extract UUID fields from known alternate field names
        uuid_field_alternates = {
            'message_uuid': ['message_id', 'messageid', 'msg_uuid', 'msg_id'],
            'request_uuid': ['request_id', 'requestid', 'req_uuid', 'req_id'],
            'query_uuid': ['query_id', 'queryid'],
            'status_uuid': ['status_id', 'statusid'],
            'command_uuid': ['command_id', 'commandid', 'cmd_uuid', 'cmd_id']
        }
        
        # Check if the field exists in the message under alternate names
        for uuid_field, alternates in uuid_field_alternates.items():
            if not normalized.get(uuid_field):
                for alt_name in alternates:
                    if isinstance(message, dict) and alt_name in message:
                        normalized[uuid_field] = message[alt_name]
                        logger.debug(f"Set {uuid_field} from {alt_name}: {normalized[uuid_field]}")
                        break
                    elif hasattr(message, alt_name):
                        normalized[uuid_field] = getattr(message, alt_name)
                        logger.debug(f"Set {uuid_field} from attribute {alt_name}: {normalized[uuid_field]}")
                        break
        
        # Determine message purpose to ensure correct UUID field is populated
        message_purpose = MessageFormatAdapter._determine_message_purpose(normalized)
        
        # Based on purpose, ensure the appropriate UUID is populated
        purpose_to_field = {
            'request': 'request_uuid',
            'query': 'query_uuid',
            'status': 'status_uuid',
            'command': 'command_uuid'
        }
        
        primary_uuid_field = purpose_to_field.get(message_purpose)


        # Always ensure message_uuid is present
        if not normalized.get('message_uuid'):
            # Use the primary UUID field if available
            if primary_uuid_field and normalized.get(primary_uuid_field):
                normalized['message_uuid'] = normalized[primary_uuid_field]
                logger.debug(f"Set message_uuid from {primary_uuid_field}: {normalized['message_uuid']}")
  
                
        # Ensure all UUID fields that are set are strings
        uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid']
        for field in uuid_fields:
            if field in normalized and normalized[field] is not None:
                normalized[field] = str(normalized[field])
                
        # Ensure all UUID fields are in metadata
        if 'metadata' not in normalized:
            normalized['metadata'] = {}
            
        for field in uuid_fields:
            if normalized.get(field):
                normalized['metadata'][field] = normalized[field]
    
    @staticmethod
    def _determine_message_purpose(normalized):
        """
        Determine the purpose of a message (request, query, status, command).
        
        Args:
            normalized: The normalized message dictionary
            
        Returns:
            str: The message purpose ('request', 'query', 'status', or 'command')
        """
        # Check message_type field
        if normalized.get('message_type'):
            msg_type = str(normalized['message_type']).lower()
            if 'request' in msg_type:
                return 'request'
            elif 'query' in msg_type:
                return 'query'
            elif 'status' in msg_type or 'response' in msg_type:
                return 'status'
            elif 'command' in msg_type or 'mode' in msg_type:
                return 'command'
            
        # Check command_type field as backup
        if normalized.get('command_type'):
            cmd_type = str(normalized['command_type']).lower()
            if 'request' in cmd_type:
                return 'request'
            elif 'query' in cmd_type:
                return 'query'
            elif 'status' in cmd_type or 'response' in cmd_type:
                return 'status'
            elif 'command' in cmd_type or 'mode' in cmd_type:
                return 'command'
                
        # Default to 'request' if cannot determine
        return 'request'
    
    @staticmethod
    def _infer_message_type_from_command_name(command_name, using_message_definitions=False):
        """
        Infer message type from command name.
        
        Args:
            command_name: The command name to analyze
            using_message_definitions: Whether message_definitions module is available
            
        Returns:
            str: Inferred message type
        """
        if not command_name:
            return None
            
        # Use message definitions if available
        if using_message_definitions:
            try:
                from FMOFP.local_messaging.messageConfigurations.message_definitions import (
                    MessageDefinitions
                )
                
                # Use reverse mapping from command name to message type
                cmd_to_msg_type = {}
                for msg_type, cmd_name in MessageDefinitions.MESSAGE_TYPE_TO_COMMAND_NAME.items():
                    cmd_to_msg_type[cmd_name.value] = msg_type.value
                
                if command_name in cmd_to_msg_type:
                    return cmd_to_msg_type[command_name]
            except Exception as e:
                logger.warning(f"Error using MessageDefinitions: {e}")
        
        # Fallback to pattern matching
        cmd_name = str(command_name).upper()
        
        # Handle weather radar related commands
        if 'WEATHER_RADAR_MODE_CHANGE' in cmd_name:
            return 'weather_radarModeChangeRequest'
        elif 'DISPLAY_PRECIPITATION_DATA' in cmd_name:
            return 'weather_radarPrecipitationRequest'
        elif 'DISPLAY_VIL_DATA' in cmd_name:
            return 'weather_radarVILRequest'
        elif 'DISPLAY_ECHO_TOP_DATA' in cmd_name:
            return 'weather_radarEchoTopRequest'
        elif 'WEATHER_RADAR_PRECIPITATION_DATA' in cmd_name:
            return 'weather_radarPrecipitationResponse'
        elif 'WEATHER_RADAR_VIL_DATA' in cmd_name:
            return 'weather_radarVILResponse'
        elif 'WEATHER_RADAR_ECHO_TOP_DATA' in cmd_name:
            return 'weather_radarEchoTopResponse'
            
        # Handle display related commands
        elif 'DISPLAY_SHOW' in cmd_name:
            return 'display_show_request'
        elif 'DISPLAY_MODE_CHANGE' in cmd_name:
            return 'display_mode_request'
        elif 'DISPLAY_DATA_REQUEST' in cmd_name:
            return 'display_data_request'
            
        # Generic pattern matching for requests/responses
        elif 'REQUEST' in cmd_name:
            return f"{cmd_name.lower()}_request"
        elif 'RESPONSE' in cmd_name:
            return f"{cmd_name.lower()}_response"
            
        return None
    
    @staticmethod
    def _infer_message_type(message: Any) -> str:
        """
        Infer message type from message content.
        
        Args:
            message: The message to analyze
            
        Returns:
            str: Inferred message type
        """
        # Check if it's a dictionary with specific keys
        if isinstance(message, dict):
            # Check for VIL data indicators
            if any(key.lower() in ['vil', 'vertically', 'liquid'] for key in message.keys()):
                return 'vil_data'
            
            # Check for precipitation data indicators
            if any(key.lower() in ['precip', 'precipitation', 'rain'] for key in message.keys()):
                return 'precipitation_data'
            
            # Check for mode change indicators
            if any(key.lower() in ['mode', 'surveillance', 'mapping', 'standby'] for key in message.keys()):
                return 'mode_change'
        
        # Check if it's an object with specific attributes
        else:
            # Get all attributes
            attrs = dir(message)
            
            # Check for VIL data indicators
            if any(attr.lower() in ['vil', 'vertically', 'liquid'] for attr in attrs):
                return 'vil_data'
            
            # Check for precipitation data indicators
            if any(attr.lower() in ['precip', 'precipitation', 'rain'] for attr in attrs):
                return 'precipitation_data'
            
            # Check for mode change indicators
            if any(attr.lower() in ['mode', 'surveillance', 'mapping', 'standby'] for attr in attrs):
                return 'mode_change'
            
            # Check class name
            if hasattr(message, '__class__'):
                class_name = message.__class__.__name__.lower()
                if 'vil' in class_name:
                    return 'vil_data'
                elif 'precip' in class_name:
                    return 'precipitation_data'
                elif 'mode' in class_name:
                    return 'mode_change'
        
        # Default to unknown if no pattern matched
        return None
    
    @staticmethod
    def extract_vil_data(message: Any) -> List[Any]:
        """
        Extract VIL data from any message format.
        
        Args:
            message: The message containing VIL data
            
        Returns:
            List[Any]: List of VIL data objects
        """
        normalized = MessageFormatAdapter.normalize_message(message)
        
        # Try to extract VIL data from normalized message
        vil_data = []
        
        # Check data field first
        if normalized['data'] is not None:
            data = normalized['data']
            
            # If data is already a list of VIL objects
            if isinstance(data, list):
                # Check if items have VIL-related attributes
                if len(data) > 0 and hasattr(data[0], 'value') and hasattr(data[0], 'position'):
                    return data
            
            # If data is a single VIL object
            elif hasattr(data, 'value') and hasattr(data, 'position'):
                return [data]
            
            # If data has a vil_data attribute
            elif hasattr(data, 'vil_data'):
                vil_data_attr = getattr(data, 'vil_data')
                if isinstance(vil_data_attr, list):
                    return vil_data_attr
                else:
                    return [vil_data_attr]
        
        # Check for vil_data field in original message
        if isinstance(message, dict) and 'vil_data' in message:
            vil_data_field = message['vil_data']
            if isinstance(vil_data_field, list):
                return vil_data_field
            else:
                return [vil_data_field]
        
        # Check for vil_data attribute in original message
        if hasattr(message, 'vil_data'):
            vil_data_attr = getattr(message, 'vil_data')
            if isinstance(vil_data_attr, list):
                return vil_data_attr
            else:
                return [vil_data_attr]
        
        # If no VIL data found, return empty list
        return vil_data
    
    @staticmethod
    def is_vil_request(message: Any) -> bool:
        """
        Determine if a message is a VIL data request.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a VIL data request, False otherwise
        """
        # Normalize the message
        normalized = MessageFormatAdapter.normalize_message(message)
        
        # Check message type - IMPORTANT: Exclude responses to prevent loops
        message_type = normalized['message_type']
        if message_type:
            message_type_str = str(message_type).lower()
            # Check if it contains VIL terms but is NOT a response
            if (any(term in message_type_str for term in ['vil', 'vertically', 'liquid']) and 
                'response' not in message_type_str):
                return True
            # Explicitly reject VIL responses
            elif 'vil' in message_type_str and 'response' in message_type_str:
                return False
        
        # Check command type and data type
        if normalized['command_type'] == 'data':
            # Check if data field contains VIL indicators
            data = normalized['data']
            if isinstance(data, dict) and any(key.lower() in ['vil', 'vertically', 'liquid'] for key in data.keys()):
                return True
            
            # Check if data has VIL-related attributes
            if hasattr(data, 'scan_parameters'):
                scan_params = getattr(data, 'scan_parameters')
                if isinstance(scan_params, dict) and 'data_type' in scan_params:
                    return scan_params['data_type'].lower() in ['vil', 'vertically', 'liquid']
        
        # Check metadata
        metadata = normalized['metadata']
        if metadata and any(key.lower() in ['vil', 'vertically', 'liquid'] for key in metadata.keys()):
            return True
        
        # Check class name if available
        if hasattr(message, '__class__'):
            class_name = message.__class__.__name__.lower()
            if 'vil' in class_name and 'request' in class_name:
                return True
        
        return False

def get_message_format_adapter():
    """Get the MessageFormatAdapter singleton instance."""
    return MessageFormatAdapter()
