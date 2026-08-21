"""
Message Transformations

Defines message transformation mappings and utility functions.
Used to transform messages between different systems in the FMOFP.
"""

from typing import Dict, Any
import copy

# Message transformation mappings
# Maps source message types to destination-specific transformations
MESSAGE_TRANSFORMATIONS = {
    # Mode change completion messages
    'weather_radarModeChangeCompletion': {
        'display': {
            'command_type': 'mode_change',
            'display_type': 'weather_radar',
            'fields': {
                'metadata.mode': 'mode',
                'metadata.mode_value': 'mode_value',
                'metadata.new_mode': 'mode',
                'metadata.old_mode': 'old_mode',
                'metadata.request_id': 'request_id',
                'metadata.source_system': 'radar_type',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'is_completion_message': True
            }
        }
    },
    'mode_change_completion': {
        'display': {
            'command_type': 'mode_change',
            'display_type': 'weather_radar',
            'fields': {
                'metadata.mode': 'mode',
                'metadata.mode_value': 'mode_value',
                'metadata.new_mode': 'mode',
                'metadata.old_mode': 'old_mode',
                'metadata.request_id': 'request_id',
                'metadata.source_system': 'radar_type',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'is_completion_message': True
            }
        }
    },
    
    # Regular mode change messages
    'weather_radarModeChangeRequest': {
        'display': {
            'command_type': 'mode_change',
            'display_type': 'radar_display',
            'fields': {
                'metadata.mode': 'mode',
                'metadata.mode_value': 'mode_value',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True
            }
        }
    },
    'mode_change': {
        'display': {
            'command_type': 'mode_change',
            'display_type': 'radar_display',
            'fields': {
                'metadata.mode': 'mode',
                'metadata.mode_value': 'mode_value',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True
            }
        }
    },
    
    # VIL data messages
    'weather_radarVILResponse': {
        'display': {
            'command_type': 'vil_data',
            'display_type': 'radar_display',
            'fields': {
                'metadata.vil_data': 'vil_data',
                'data.vil_data': 'vil_data',
                'vil_data': 'vil_data',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'type': 'vil_data'
            }
        }
    },
    'vil_data': {
        'display': {
            'command_type': 'vil_data',
            'display_type': 'radar_display',
            'fields': {
                'metadata.vil_data': 'vil_data',
                'data.vil_data': 'vil_data',
                'vil_data': 'vil_data',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'type': 'vil_data'
            }
        }
    },
    
    # Precipitation data messages
    'weather_radarPrecipitationResponse': {
        'display': {
            'command_type': 'precipitation_data',
            'display_type': 'radar_display',
            'fields': {
                'metadata.precipitation': 'precipitation',
                'data.precipitation': 'precipitation',
                'precipitation': 'precipitation',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'type': 'precipitation_data'
            }
        }
    },
    'precipitation_data': {
        'display': {
            'command_type': 'precipitation_data',
            'display_type': 'radar_display',
            'fields': {
                'metadata.precipitation': 'precipitation',
                'data.precipitation': 'precipitation',
                'precipitation': 'precipitation',
                'metadata.request_id': 'request_id',
                'request_id': 'request_id'
            },
            'add_fields': {
                'force_update': True,
                'update_visual': True,
                'type': 'precipitation_data'
            }
        }
    }
}

def get_nested_value(obj: Dict[str, Any], path: str) -> Any:
    """
    Get a nested value from a dictionary using a dot-separated path.
    
    Args:
        obj: The dictionary to extract the value from
        path: The dot-separated path to the value (e.g., 'metadata.mode')
        
    Returns:
        The value at the specified path, or None if not found
    """
    if not obj or not path:
        return None
        
    parts = path.split('.')
    current = obj
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
            
    return current

def transform_message(message: Dict[str, Any], source_type: str, destination: str) -> Dict[str, Any]:
    """
    Transform a message based on predefined mappings.
    
    Args:
        message: The message to transform
        source_type: The source message type
        destination: The destination system
        
    Returns:
        The transformed message
    """
    # Create a deep copy of the message to avoid modifying the original
    result = copy.deepcopy(message)
    
    # Check if we have a transformation for this message type and destination
    if source_type not in MESSAGE_TRANSFORMATIONS:
        return result  # No transformation needed
        
    if destination not in MESSAGE_TRANSFORMATIONS[source_type]:
        return result  # No transformation for this destination
        
    # Get transformation rules
    rules = MESSAGE_TRANSFORMATIONS[source_type][destination]
    
    # Apply basic field mappings
    for dest_field, value in rules.items():
        if dest_field not in ('fields', 'add_fields'):
            result[dest_field] = value
            
    # Apply field mappings (source -> destination)
    if 'fields' in rules:
        for src_path, dest_field in rules['fields'].items():
            # Extract value from source path (e.g., metadata.mode)
            value = get_nested_value(message, src_path)
            if value is not None:
                result[dest_field] = value
                
    # Add additional fields
    if 'add_fields' in rules:
        for field, value in rules['add_fields'].items():
            result[field] = value
            
    return result

def get_message_type(message: Dict[str, Any]) -> str:
    """
    Get the message type from a message.
    
    Args:
        message: The message to get the type from
        
    Returns:
        The message type, or None if not found
    """
    # Check direct message_type field
    if 'message_type' in message:
        message_type = message['message_type']
        # Special case for weather radar mode change completion
        if message_type == 'weather_radarModeChangeCompletion':
            return 'mode_change_completion'
        return message_type
        
    # Check command_type field
    if 'command_type' in message:
        command_type = message['command_type']
        # Map command_type to message_type if needed
        if command_type == 'mode_change_completion':
            return 'mode_change_completion'
        return command_type
        
    # Check metadata
    if 'metadata' in message and isinstance(message['metadata'], dict):
        metadata = message['metadata']
        if 'message_type' in metadata:
            message_type = metadata['message_type']
            # Special case for weather radar mode change completion
            if message_type == 'weather_radarModeChangeCompletion':
                return 'mode_change_completion'
            return message_type
        if 'command_type' in metadata:
            command_type = metadata['command_type']
            # Map command_type to message_type if needed
            if command_type == 'mode_change_completion':
                return 'mode_change_completion'
            return command_type
            
    # Check command_name as fallback
    if 'command_name' in message:
        command_name = message['command_name']
        if 'mode_change_completion' in command_name.lower():
            return 'mode_change_completion'
        elif 'mode_change' in command_name.lower():
            return 'mode_change'
        elif 'vil' in command_name.lower():
            return 'vil_data'
        elif 'precipitation' in command_name.lower():
            return 'precipitation_data'
            
    return None
