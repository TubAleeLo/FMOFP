"""
Message Transformer

Transforms messages for each destination.
Ensures consistent message format and adds routing metadata.
"""

import copy
import time
import traceback
from typing import Dict, Any, List, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.routing_registry import get_routing_registry

logger = get_logger()

class MessageTransformer:
    def __init__(self, routing_registry=None):
        self.routing_registry = routing_registry or get_routing_registry()
        self.logger = get_logger()
        logger.info("MessageTransformer initialized")
        
    def transform_message(self, message: Union[Dict[str, Any], Any], destinations: List[str]) -> Dict[str, Union[Dict[str, Any], Any]]:
        """
        Transform a message for each destination.
        
        Args:
            message: The message to transform
            destinations: List of destination system IDs
            
        Returns:
            Dict[str, Union[Dict[str, Any], Any]]: Dictionary mapping destination to transformed message
        """
        try:
            transformed_messages = {}
            
            # Log original message critical fields
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
                    
            self.logger.info(f"[TRANSFORMER] Original message - request_id: {request_id}, command_name: {command_name}")
            
            for destination in destinations:
                # Create a deep copy of the message
                if isinstance(message, dict):
                    transformed = copy.deepcopy(message)
                    
                    # Ensure critical fields preservation in dictionary case
                    if 'command_name' in message and message['command_name']:
                        transformed['command_name'] = message['command_name']
                        self.logger.info(f"[TRANSFORMER] Preserved command_name in dict: {message['command_name']}")
                    
                    if 'request_id' in message and message['request_id']:
                        transformed['request_id'] = message['request_id']
                        self.logger.info(f"[TRANSFORMER] Preserved request_id in dict: {message['request_id']}")
                else:
                    # Convert object to dictionary
                    transformed = self._object_to_dict(message)
                    
                # Add routing metadata
                self._add_routing_metadata(transformed, destination)
                
                # Apply destination-specific transformations
                if destination == 'radar':
                    self._transform_for_radar(transformed)
                elif destination == 'display':
                    self._transform_for_display(transformed)
                
                # Verify critical fields are still present after transformation
                self.logger.info(f"[TRANSFORMER] After {destination} transformation - request_id: {transformed.get('request_id')}, command_name: {transformed.get('command_name')}")
                
                # Ensure metadata also contains critical fields
                if 'metadata' in transformed:
                    if transformed.get('command_name') and 'command_name' not in transformed['metadata']:
                        transformed['metadata']['command_name'] = transformed['command_name']
                    
                    if transformed.get('request_id') and 'request_id' not in transformed['metadata']:
                        transformed['metadata']['request_id'] = transformed['request_id']
                
                transformed_messages[destination] = transformed
                
            return transformed_messages
        except Exception as e:
            self.logger.error(f"Error transforming message: {e}")
            self.logger.error(traceback.format_exc())
            return {}
        
    def _object_to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        Convert an object to a dictionary.
        
        Args:
            obj: The object to convert
            
        Returns:
            Dict[str, Any]: Dictionary representation of the object
        """
        # Start with __dict__
        result = {}
        if hasattr(obj, '__dict__'):
            result = copy.deepcopy(obj.__dict__)
            
        # Add properties that might not be in __dict__
        for attr in dir(obj):
            if not attr.startswith('_') and not callable(getattr(obj, attr)) and attr not in result:
                result[attr] = getattr(obj, attr)
        
        # Log the current state of critical fields
        request_id = None
        command_name = None
        
        if hasattr(obj, 'request_id'):
            request_id = obj.request_id
        elif hasattr(obj, 'request_uuid'):
            request_id = obj.request_uuid
            
        if hasattr(obj, 'command_name'):
            command_name = obj.command_name
            
        self.logger.info(f"[TRANSFORMER] Object conversion - request_id: {request_id}, command_name: {command_name}")
            
        # Explicitly preserve critical fields
        if hasattr(obj, 'command_name') and obj.command_name:
            result['command_name'] = obj.command_name
            self.logger.info(f"[TRANSFORMER] Preserved command_name: {obj.command_name}")
            
        if hasattr(obj, 'request_id') and obj.request_id:
            result['request_id'] = obj.request_id
            self.logger.info(f"[TRANSFORMER] Preserved request_id: {obj.request_id}")
        
        if hasattr(obj, 'request_uuid') and obj.request_uuid:
            result['request_uuid'] = obj.request_uuid
            # Also set request_id for consistency if not already set
            if 'request_id' not in result:
                result['request_id'] = obj.request_uuid
                self.logger.info(f"[TRANSFORMER] Set request_id from request_uuid: {obj.request_uuid}")
                
        return result
        
    def _add_routing_metadata(self, message: Dict[str, Any], destination: str) -> None:
        """
        Add routing metadata to a message.
        
        Args:
            message: The message to add metadata to
            destination: The destination system ID
        """
        # Initialize metadata if not present
        if 'metadata' not in message:
            message['metadata'] = {}
            
        # Add routing information
        message['metadata']['routed_to'] = destination
        message['metadata']['routing_timestamp'] = time.time()
        
        # Add route history
        if 'route_history' not in message['metadata']:
            message['metadata']['route_history'] = []
            
        message['metadata']['route_history'].append({
            'destination': destination,
            'timestamp': time.time()
        })
        
    def _transform_for_radar(self, message: Dict[str, Any]) -> None:
        """
        Apply radar-specific transformations.
        
        Args:
            message: The message to transform
        """
        # Ensure RT address is set to radar
        message['rt_address'] = self.routing_registry.get_rt_address_by_system('radar')
        
        # Add radar-specific metadata
        if 'metadata' not in message:
            message['metadata'] = {}
            
        message['metadata']['system_type'] = 'radar'
        
        # Ensure command_type is set for special cases
        if 'message_type' in message:
            message_type = message['message_type']
            
            # Check if message_type is in special cases
            for case_id, case in self.routing_registry.special_cases.items():
                if message_type in case['message_types']:
                    if case_id == 'vil_data':
                        message['command_type'] = 'vilData'
                        message['command_name'] = 'radar_vilData'
                        break
                    elif case_id == 'precipitation_data':
                        message['command_type'] = 'precipitationData'
                        message['command_name'] = 'radar_precipitationData'
                        break
                    elif case_id == 'mode_change':
                        message['command_type'] = 'modeChange'
                        message['command_name'] = 'radar_modeChange'
                        break
        
    def _transform_for_display(self, message: Dict[str, Any]) -> None:
        """
        Apply display-specific transformations.
        
        Args:
            message: The message to transform
        """
        # Ensure RT address is set to display
        message['rt_address'] = self.routing_registry.get_rt_address_by_system('displays')
        
        # Add display-specific metadata
        if 'metadata' not in message:
            message['metadata'] = {}
            
        message['metadata']['system_type'] = 'display'
        
        # Ensure command_type is set for special cases
        if 'message_type' in message:
            message_type = message['message_type']
            
            # Check if message_type is in special cases
            for case_id, case in self.routing_registry.special_cases.items():
                if message_type in case['message_types']:
                    if case_id == 'vil_data':
                        message['command_type'] = 'vilData'
                        message['command_name'] = 'displays_vilData'
                        break
                    elif case_id == 'precipitation_data':
                        message['command_type'] = 'precipitationData'
                        message['command_name'] = 'displays_precipitationData'
                        break
                    elif case_id == 'mode_change':
                        message['command_type'] = 'modeChange'
                        message['command_name'] = 'displays_modeChange'
                        break

def get_message_transformer():
    """Get a new instance of MessageTransformer."""
    return MessageTransformer()
