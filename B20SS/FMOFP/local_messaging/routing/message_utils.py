"""
Message Utilities

Utility functions for working with messages in the routing system.
Provides standardized message field preservation and conversion.
"""

import copy
from typing import Dict, Any, Union

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

def preserve_critical_fields(message: Union[Dict[str, Any], Any], 
                            ensure_metadata: bool = True) -> Dict[str, Any]:
    """
    Create a dictionary representation of a message with critical fields preserved.
    
    This utility function ensures that command_name and request_id fields are
    always preserved when converting messages between formats. It can be used
    by any component that needs to transform messages.
    
    Args:
        message: The message to process (can be a dict or an object)
        ensure_metadata: Whether to ensure metadata exists and contains critical fields
        
    Returns:
        Dict[str, Any]: Dictionary with preserved critical fields
    """
    # Start with a copy if it's already a dict
    if isinstance(message, dict):
        result = copy.deepcopy(message)
    else:
        # Convert object to dictionary
        result = {}
        if hasattr(message, '__dict__'):
            result = copy.deepcopy(message.__dict__)
            
        # Add properties that might not be in __dict__
        for attr in dir(message):
            if not attr.startswith('_') and not callable(getattr(message, attr)) and attr not in result:
                result[attr] = getattr(message, attr)
    
    # Extract critical fields
    request_id = None
    command_name = None
    
    if isinstance(message, dict):
        request_id = message.get('request_id')
        command_name = message.get('command_name')
    else:
        if hasattr(message, 'request_id'):
            request_id = message.request_id
        elif hasattr(message, 'request_uuid'):
            request_id = message.request_uuid
            
        if hasattr(message, 'command_name'):
            command_name = message.command_name
    
    # Explicitly preserve critical fields
    if command_name:
        result['command_name'] = command_name
        logger.info(f"[MSG_UTILS] Preserved command_name: {command_name}")
        
    if request_id:
        result['request_id'] = request_id
        logger.info(f"[MSG_UTILS] Preserved request_id: {request_id}")
    
    # Handle request_uuid conversion to request_id
    if not request_id and isinstance(message, dict) and 'request_uuid' in message:
        result['request_id'] = message['request_uuid']
        logger.info(f"[MSG_UTILS] Set request_id from request_uuid: {message['request_uuid']}")
    elif not request_id and hasattr(message, 'request_uuid') and message.request_uuid:
        result['request_id'] = message.request_uuid
        logger.info(f"[MSG_UTILS] Set request_id from request_uuid: {message.request_uuid}")
    
    # Ensure metadata exists and contains critical fields
    if ensure_metadata:
        if 'metadata' not in result:
            result['metadata'] = {}
            
        if command_name and 'command_name' not in result['metadata']:
            result['metadata']['command_name'] = command_name
            
        if request_id and 'request_id' not in result['metadata']:
            result['metadata']['request_id'] = request_id
    
    return result
