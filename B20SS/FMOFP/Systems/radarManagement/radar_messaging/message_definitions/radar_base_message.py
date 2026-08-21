"""
Radar Base Message

A base class for all radar messages to ensure consistent serialization and validation.
Provides a standardized interface for message handling within the radar subsystem,
maintaining proper system boundaries.
"""

from dataclasses import dataclass, field, asdict
import uuid
import time
import xml.etree.ElementTree as ET
from typing import Type, Dict, Any, Optional

# Import standard message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST,
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_STATUS_REQUEST,
    WEATHER_RADAR_STATUS_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    WEATHER_RADAR_PRECIPITATION_RESPONSE
)

@dataclass
class RadarBaseMessage:
    """
    Base class for all radar-specific messages.
    Provides consistent serialization, validation, and metadata handling.
    """
    ## Message header
    message_header: str = None

    # Message Identifiers
    timestamp: float = field(default_factory=time.time)
    message_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_uuid: str = None  # For backward compatibility, prefer request_id
    response_uuid: str = None
    priority: str = "normal"
    status: str = "pending"
    
    # Address fields
    destination: str = None
    sending_system: str = None
    source: str = None
    
    ## Message body
    # Message Attributes
    command_type: str = None
    command_subtype: str = None
    message_type: str = None
    command_name: str = None
    
    # Metadata for additional information
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """
        Initialize message after creation.
        Synchronizes fields, applies standard values, and ensures proper initialization.
        """
        # Ensure timestamp is set if not provided
        if self.timestamp is None:
            self.timestamp = time.time()
            
        # Ensure request_id is synced with request_uuid for compatibility
        if self.request_uuid and not self.request_id:
            self.request_id = self.request_uuid
        elif self.request_id and not self.request_uuid:
            self.request_uuid = self.request_id
            
        # Set default priority if not provided
        if not self.priority:
            self.priority = "normal"
            
        # Set default status if not provided
        if not self.status:
            self.status = "pending"
            
        # Create metadata if it doesn't exist
        if not self.metadata:
            self.metadata = {}
            
        # Ensure critical fields are in metadata
        self._ensure_critical_fields_in_metadata()
    
    def _ensure_critical_fields_in_metadata(self):
        """Ensure critical fields are included in metadata for preservation."""
        # Add command_name to metadata if it exists
        if self.command_name:
            self.metadata['command_name'] = self.command_name
            
        # Add UUID fields to metadata
        if self.message_uuid:
            self.metadata['message_uuid'] = self.message_uuid
        if self.request_id:
            self.metadata['request_id'] = self.request_id
        if self.request_uuid:
            self.metadata['request_uuid'] = self.request_uuid
        if self.response_uuid:
            self.metadata['response_uuid'] = self.response_uuid
            
        # Add message_type to metadata
        if self.message_type:
            self.metadata['message_type'] = self.message_type
            
        # Add command_type to metadata
        if self.command_type:
            self.metadata['command_type'] = self.command_type

    def validate(self):
        """Validate required message fields"""
        missing_fields = []
        if not self.message_header:
            missing_fields.append("message_header")
        if not self.message_type:
            missing_fields.append("message_type")
        if not self.sending_system:
            missing_fields.append("sending_system")
        if not self.destination:
            missing_fields.append("destination")
            
        # Only validate command_name if it's set
        if self.command_name is not None and not self.command_name:
            missing_fields.append("command_name")
            
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        # If using standard message types, validate they are defined in constants
        if self.message_type and self.message_type.startswith('WEATHER_RADAR_'):
            # Check against constants
            from FMOFP.Systems.radarManagement.radar_messaging.message_types import get_message_type
            valid_type = get_message_type(self.message_type)
            if not valid_type:
                raise ValueError(f"Invalid weather radar message type: {self.message_type}")

    def to_dict(self):
        """
        Convert the message to a dictionary that includes all fields and metadata.
        Ensures critical fields are preserved in both top-level and metadata.
        """
        # Get base dictionary from dataclass
        result = asdict(self)
        
        # Create metadata if it doesn't exist
        if 'metadata' not in result or not result['metadata']:
            result['metadata'] = {}
        
        # Ensure critical fields are in metadata
        # Command name preservation
        if self.command_name:
            result['metadata']['command_name'] = self.command_name
            
        # UUID field preservation
        if self.message_uuid:
            result['metadata']['message_uuid'] = self.message_uuid
        if self.request_id:
            result['metadata']['request_id'] = self.request_id
        if self.request_uuid:
            result['metadata']['request_uuid'] = self.request_uuid
        if self.response_uuid:
            result['metadata']['response_uuid'] = self.response_uuid
                
        # Message type preservation
        if self.message_type:
            result['metadata']['message_type'] = self.message_type
            
        # Command type preservation
        if self.command_type:
            result['metadata']['command_type'] = self.command_type
            
        return result

    def from_dict(self, data):
        """Update message attributes from a dictionary."""
        for field_name, value in data.items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)

    def to_mil_std_message(self):
        """Convert to MIL_STD_1553B_Message for transmission."""
        from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
        from FMOFP.Systems.radarManagement.radar_messaging.address_utils import (
            get_rt_address,
            get_subaddress,
            get_rt_subaddress_pair_for_radar
        )
        
        # Get RT/SA addresses based on message type
        rt_address = None
        sub_address = None
        
        # Try to determine system type from message attributes
        system_type = self.sending_system
        if 'weather' in str(self.message_type).lower():
            system_type = 'weather_radar'
        elif 'tfr' in str(self.message_type).lower():
            system_type = 'tfr_radar'
        elif 'sar' in str(self.message_type).lower():
            system_type = 'sar_radar'
        elif 'targeting' in str(self.message_type).lower():
            system_type = 'targeting_radar'
        elif 'aewc' in str(self.message_type).lower():
            system_type = 'aewc_radar'
            
        # Use address utilities to get RT/SA pair
        try:
            rt_address, sub_address = get_rt_subaddress_pair_for_radar(system_type, 'weather_radar')
        except Exception:
            # Fallback to defaults if lookup fails
            rt_address = 9  # Default radar address
            sub_address = 1  # Default data subaddress
        
        # Convert message to dictionary
        msg_dict = self.to_dict()
        
        # Create MIL_STD_1553B_Message
        mil_std_msg = MIL_STD_1553B_Message(
            rt_address=rt_address,
            sub_address=sub_address,
            data=msg_dict.get('data', [])
        )
        
        # Copy all metadata fields to MIL_STD_1553B_Message
        for key, value in msg_dict.items():
            if key not in ['rt_address', 'sub_address', 'data']:
                setattr(mil_std_msg, key, value)
                
        return mil_std_msg

# Registry for message types
MESSAGE_REGISTRY: Dict[str, Type[RadarBaseMessage]] = {}

def register_message_type(message_type: str, message_class: Type[RadarBaseMessage]):
    """Register a message type for factory creation."""
    MESSAGE_REGISTRY[message_type] = message_class

def create_message(message_type: str, **kwargs) -> RadarBaseMessage:
    """Create a message of the specified type with the given parameters."""
    if message_type not in MESSAGE_REGISTRY:
        raise ValueError(f"Message type {message_type} is not registered.")
    return MESSAGE_REGISTRY[message_type](message_type=message_type, **kwargs)
