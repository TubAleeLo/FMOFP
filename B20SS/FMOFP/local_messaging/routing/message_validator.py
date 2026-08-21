"""
Message Validator

Validates message format and content against the Routing Registry.
Checks RT addresses, subaddresses, and message types.
"""

import traceback
from typing import Dict, Any, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.routing_registry import get_routing_registry

logger = get_logger()

class MessageValidator:
    def __init__(self, routing_registry=None):
        self.routing_registry = routing_registry or get_routing_registry()
        self.logger = get_logger()
        logger.info("MessageValidator initialized")
        
    def validate_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate a message against the routing registry.
        
        Args:
            message: The message to validate (dictionary or object)
            
        Returns:
            bool: True if the message is valid, False otherwise
        """
        try:
            # Check message type
            if not self._check_message_type(message):
                return False
                
            # Check required fields
            if not self._check_required_fields(message):
                return False
                
            # Validate RT address
            if not self._validate_rt_address(message):
                return False
                
            # Validate subaddress
            if not self._validate_subaddress(message):
                return False
                
            # Validate UUID fields
            if not self._validate_uuid_fields(message):
                # Only log warning, don't fail validation
                self.logger.warning("[MSG_VALIDATOR] UUID fields missing or invalid")
                # We continue despite UUID issues - this is a warning, not an error
                
            # Validate message_type if present
            if not self._validate_message_type_field(message):
                return False
                
            # Validate command_name if present
            if not self._validate_command_name_field(message):
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error validating message: {e}")
            self.logger.error(traceback.format_exc())
            return False
        
    def _check_message_type(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Check if message is a valid type.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a valid type, False otherwise
        """
        # Check if message is a dictionary
        if isinstance(message, dict):
            return True
            
        # Check if message is a MIL_STD_1553B_Message or similar object
        if hasattr(message, 'rt_address') and hasattr(message, 'sub_address'):
            return True
            
        self.logger.error(f"Invalid message type: {type(message)}")
        return False
        
    def _check_required_fields(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Check if message has all required fields.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message has all required fields, False otherwise
        """
        required_fields = ['rt_address', 'sub_address']
        
        for field in required_fields:
            if isinstance(message, dict):
                if field not in message:
                    self.logger.error(f"Missing required field: {field}")
                    return False
            else:
                if not hasattr(message, field):
                    self.logger.error(f"Missing required field: {field}")
                    return False
                    
        return True
        
    def _validate_rt_address(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate RT address against routing registry.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if the RT address is valid, False otherwise
        """
        # Get RT address
        rt_address = message['rt_address'] if isinstance(message, dict) else message.rt_address
        
        # Check if RT address is valid
        system_id = self.routing_registry.get_system_by_rt_address(rt_address)
        if not system_id:
            self.logger.error(f"Invalid RT address: {rt_address}")
            return False
            
        return True
        
    def _validate_subaddress(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate subaddress against routing registry.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if the subaddress is valid, False otherwise
        """
        # Get RT address and subaddress
        rt_address = message['rt_address'] if isinstance(message, dict) else message.rt_address
        sub_address = message['sub_address'] if isinstance(message, dict) else message.sub_address
        
        # Get system ID
        system_id = self.routing_registry.get_system_by_rt_address(rt_address)
        if not system_id:
            self.logger.error(f"Invalid RT address: {rt_address}")
            return False
            
        # Check if subaddress is valid for this system
        system = self.routing_registry.systems.get(system_id)
        if not system:
            self.logger.error(f"System not found: {system_id}")
            return False
            
        # Check if subaddress is in range
        valid_subaddresses = list(system['subaddresses'].values())
        if sub_address not in valid_subaddresses:
            # Special case: Mode code subaddress (31)
            if sub_address == 31:
                return True
                
            self.logger.error(f"Invalid subaddress {sub_address} for system {system_id}")
            return False
            
        return True

    def _validate_message_type_field(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate message_type field if present.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if the message_type is valid or not present, False otherwise
        """
        # Check if message_type is present
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        # If message_type is not present, it's valid
        if not message_type:
            return True
            
        # Check if message_type is in special cases
        for case_id, case in self.routing_registry.special_cases.items():
            if message_type in case['message_types']:
                return True
                
        # Check if message_type is in message_types
        if message_type in self.routing_registry.message_types:
            return True
            
        # ----- NEED TO IMPLEMENT
        # Check if message_type is in status_words
        # if message_type in self.routing_registry.status_words:
        #     return True
        
            
        # Log warning but don't fail validation
        self.logger.warning(f"[MSG_VALIDATOR] Unknown message_type: {message_type}")
        return True
        
    def _validate_uuid_fields(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate UUID fields are present and properly formed.
        
        Checks for message_uuid, request_uuid, and other tracking IDs.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if UUID fields are valid or not critical, False otherwise
        """
        # List of UUID fields to check
        uuid_fields = ['message_uuid', 'request_uuid', 'request_id']
        
        # Track which fields are present
        present_fields = []
        
        # Check each field
        for field in uuid_fields:
            field_value = None
            
            # Extract from dictionary or object
            if isinstance(message, dict):
                field_value = message.get(field)
                
                # Also check metadata if present
                if not field_value and 'metadata' in message and isinstance(message['metadata'], dict):
                    field_value = message['metadata'].get(field)
            elif hasattr(message, field):
                field_value = getattr(message, field)
                
                # Also check metadata if present
                if not field_value and hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                    field_value = message.metadata.get(field)
            
            # If field is present, add to tracking
            if field_value:
                present_fields.append(field)
                
                # Validate UUID format if string
                if isinstance(field_value, str) and len(field_value) < 8:
                    self.logger.warning(f"UUID field {field} has suspicious value: {field_value} (too short)")
        
        # Check critical command_name field
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
            
            # Also check metadata if present
            if not command_name and 'metadata' in message and isinstance(message['metadata'], dict):
                command_name = message['metadata'].get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = getattr(message, 'command_name')
            
            # Also check metadata if present
            if not command_name and hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                command_name = message.metadata.get('command_name')
                
        # Log results
        if len(present_fields) > 0:
            self.logger.debug(f"[MSG_VALIDATOR] Found UUID fields: {', '.join(present_fields)}")
            
            # We want at least one UUID field for proper message tracking
            return True
        else:
            self.logger.warning(f"[MSG_VALIDATOR] No UUID fields found in message")
            
            # If no UUID fields, but command_name is present, still consider partially valid
            if command_name:
                self.logger.info(f"[MSG_VALIDATOR] Found command_name: {command_name}, considering partially valid")
                return True
                
            return False
    
    def _validate_command_name_field(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Validate command_name field if present.
        
        Args:
            message: The message to validate
            
        Returns:
            bool: True if the command_name is valid or not present, False otherwise
        """
        # Check if command_name is present
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
            
            # Also check metadata if present 
            if not command_name and 'metadata' in message and isinstance(message['metadata'], dict):
                command_name = message['metadata'].get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = getattr(message, 'command_name')
            
            # Also check metadata if present
            if not command_name and hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                command_name = message.metadata.get('command_name')
            
        # If command_name is not present, it's valid
        if not command_name:
            return True
            
        # Check if command_name is in special cases
        for case_id, case in self.routing_registry.special_cases.items():
            if 'command_names' in case and command_name in case['command_names']:
                return True
                
        # Check if command_name is in message_types
        if command_name in self.routing_registry.message_types:
            return True
            
        # Log warning but don't fail validation
        self.logger.warning(f"Unknown command_name: {command_name}")
        return True


def get_message_validator():
    """Get a new instance of MessageValidator."""
    return MessageValidator()
