from dataclasses import dataclass, field, asdict
import uuid
import time
import xml.etree.ElementTree as ET
from typing import Type, Dict

_UNSET = object()  # sentinel distinguishing "field omitted" from "field explicitly passed as None"

@dataclass
class BaseMessage:
    ## Message header
    message_header: str = None

    # Message Identifiers
    timestamp: str = None                                                       # Timestamp of message creation (set at construction time, see __init__)
    message_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))        # GENERAL TRACKING ID for the message
    request_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))        # UUID for requests ONLY, used for tracking and correlation
    query_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))          # UUID for queries ONLY, used for tracking and correlation
    status_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))         # UUID for status messages ONLY, used for tracking and correlation
    command_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))        # UUID for command messages ONLY, used for tracking and correlation
    priority: str  = "normal"
    status: str  = "pending"
    
    # Address fields
    destination: str = None                                                     # Destination may be a system or service
    destination_uuid: str = None                                                # need create uuid's for systems in address book and registry, then use them here
    sending_system: str = None                                                  # Sending system may be a system or service
    sending_system_uuid: str = None                                             # need create uuid's for systems in address book and registry, then use them here
    source: str = None                                                          # Source may be a system, user, or a service
    source_uuid: str = None                                                     # need create uuid's for systems in address book and registry, then use them here
    
    ## Message body
    # Message Attributes
    command_type: str = None
    command_subtype: str = None
    message_type: str = None
    command_name: str = None

    def __init__(self, message_header=None, timestamp=_UNSET, message_uuid=_UNSET,
                 request_uuid=_UNSET, query_uuid=_UNSET, status_uuid=_UNSET, command_uuid=_UNSET,
                 priority="normal", status="pending", destination=None, destination_uuid=None,
                 sending_system=None, sending_system_uuid=None, source=None, source_uuid=None,
                 command_type=None, command_subtype=None, message_type=None, command_name=None,
                 **kwargs):
        """
        Hand-written __init__ (dataclass() will not generate one when the class
        body already defines __init__ explicitly).

        This exists instead of the plain dataclass-generated __init__ for two reasons,
        both discovered via live testing of real message subclasses:

        1. Many message subclasses across the codebase (e.g. tfr_radarElevationProfile,
           sar_radarImagery, fcs_controlSurfaceRequest and ~20 other files) call
           super().__init__(message_type=..., <domain_specific>_uuid=..., **kwargs) with
           an identifier keyword that isn't one of this class's five declared *_uuid
           fields (data_uuid, warning_uuid, config_uuid, alert_uuid, etc.). The plain
           dataclass __init__ has no **kwargs catch-all, so every one of those calls
           raised "TypeError: BaseMessage.__init__() got an unexpected keyword argument"
           the moment the message was actually constructed. Any unrecognized keyword is
           now stored as a plain instance attribute instead of raising.
        2. `timestamp` was previously a plain (non-factory) dataclass default
           (`time.time()`), which is evaluated exactly once at class-definition time -
           every message that didn't explicitly pass timestamp= silently got the
           process-start time instead of its actual creation time. It's now generated
           fresh per instance, matching the "Timestamp of message creation" intent.
        """
        self.message_header = message_header
        self.timestamp = time.time() if timestamp is _UNSET else timestamp
        self.message_uuid = str(uuid.uuid4()) if message_uuid is _UNSET else message_uuid
        self.request_uuid = str(uuid.uuid4()) if request_uuid is _UNSET else request_uuid
        self.query_uuid = str(uuid.uuid4()) if query_uuid is _UNSET else query_uuid
        self.status_uuid = str(uuid.uuid4()) if status_uuid is _UNSET else status_uuid
        self.command_uuid = str(uuid.uuid4()) if command_uuid is _UNSET else command_uuid
        self.priority = priority
        self.status = status
        self.destination = destination
        self.destination_uuid = destination_uuid
        self.sending_system = sending_system
        self.sending_system_uuid = sending_system_uuid
        self.source = source
        self.source_uuid = source_uuid
        self.command_type = command_type
        self.command_subtype = command_subtype
        self.message_type = message_type
        self.command_name = command_name

        # Preserve any additional caller-supplied identifiers/data (e.g. data_uuid,
        # warning_uuid, profile_data) as plain instance attributes. These are not
        # declared dataclass fields, so (matching pre-existing behavior of subclasses
        # that already set extra plain attributes like self.profile_data) they will
        # not appear in asdict()/to_dict() unless a subclass adds them explicitly.
        for _key, _value in kwargs.items():
            setattr(self, _key, _value)

        self.__post_init__()

    def __post_init__(self):
        """
        Initialize message after creation.
        Synchronizes UUID fields, applies standard header/status values,
        and ensures all fields are properly initialized.
        """
        # Ensure timestamp is set if not provided
        if self.timestamp is None:
            self.timestamp = time.time()
            
        # Determine message purpose from message_type or other fields
        message_purpose = self._determine_message_purpose()
        
        # Set default priority if not provided
        if not self.priority:
            self.priority = "normal"
            
        # Set default status if not provided
        if not self.status:
            self.status = "pending"
            
        # Apply UUID synchronization based on message purpose
        self._synchronize_uuid_fields(message_purpose)
        
        # Create metadata if it doesn't exist
        if not hasattr(self, 'metadata') or not self.metadata:
            self.metadata = {}
            
        # Ensure command_name and critical fields are in metadata
        self._ensure_critical_fields_in_metadata()
    
    def _determine_message_purpose(self):
        """Determine the purpose of this message (request, query, status, command)."""
        # Check message_type field
        if self.message_type:
            msg_type = self.message_type.lower()
            if 'request' in msg_type:
                return 'request'
            elif 'query' in msg_type:
                return 'query'
            elif 'status' in msg_type or 'response' in msg_type:
                return 'status'
            elif 'command' in msg_type or 'mode' in msg_type:
                return 'command'
            
        # Check command_type field as backup
        if hasattr(self, 'command_type') and self.command_type:
            cmd_type = self.command_type.lower()
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
        
    def _synchronize_uuid_fields(self, message_purpose):
        """
        Synchronize UUID fields based on message purpose.
        Ensures the appropriate UUID field is populated and message_uuid is synced.
        """
        # Always generate message_uuid if not set
        if not self.message_uuid:
            self.message_uuid = str(uuid.uuid4())
            
        # Handle request_uuid for request messages
        if message_purpose == 'request':
            if not self.request_uuid:
                self.request_uuid = str(uuid.uuid4())
                
        # Handle query_uuid for query messages
        elif message_purpose == 'query':
            if not self.query_uuid:
                self.query_uuid = str(uuid.uuid4())
                
        # Handle status_uuid for status/response messages
        elif message_purpose == 'status':
            if not self.status_uuid:
                self.status_uuid = str(uuid.uuid4())
                
        # Handle command_uuid for command messages
        elif message_purpose == 'command':
            if not self.command_uuid:
                self.command_uuid = str(uuid.uuid4())
    
    def _ensure_critical_fields_in_metadata(self):
        """Ensure critical fields are included in metadata for preservation."""
        # Create metadata dictionary if it doesn't exist
        if not hasattr(self, 'metadata') or not self.metadata:
            self.metadata = {}
            
        # Add command_name to metadata if it exists
        if self.command_name:
            self.metadata['command_name'] = self.command_name
            
        # Add UUID fields to metadata
        if self.message_uuid:
            self.metadata['message_uuid'] = self.message_uuid
        if self.request_uuid:
            self.metadata['request_uuid'] = self.request_uuid
        if self.query_uuid:
            self.metadata['query_uuid'] = self.query_uuid
        if self.status_uuid:
            self.metadata['status_uuid'] = self.status_uuid
        if self.command_uuid:
            self.metadata['command_uuid'] = self.command_uuid
            
        # Add message_type to metadata
        if self.message_type:
            self.metadata['message_type'] = self.message_type
            
        # Add command_type to metadata if it exists
        if hasattr(self, 'command_type') and self.command_type:
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
        # This maintains backwards compatibility
        if self.command_name is not None and not self.command_name:
            missing_fields.append("command_name")
            
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        # If command_name is set, validate it exists in registry
        if self.command_name:
            from FMOFP.local_messaging.command_word_map import validate_command_name
            if not validate_command_name(self.command_name):
                raise ValueError(f"Invalid command name: {self.command_name}")

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
        uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid']
        for field in uuid_fields:
            value = getattr(self, field, None)
            if value:
                result['metadata'][field] = value
                
        # Message type preservation
        if self.message_type:
            result['metadata']['message_type'] = self.message_type
            
        # Command type preservation
        if self.command_type:
            result['metadata']['command_type'] = self.command_type
            
        return result

    def from_dict(self, data):
        for field_name, value in data.items():
            setattr(self, field_name, value)

    def to_xml(self):
        root = ET.Element(self.__class__.__name__)
        for field_name, value in self.to_dict().items():
            child = ET.SubElement(root, field_name)
            child.text = str(value)
        return ET.tostring(root, encoding='unicode')

    def from_xml(self, xml_str):
        root = ET.fromstring(xml_str)
        data = {child.tag: child.text for child in root}
        self.from_dict(data)

# Registry for message types
MESSAGE_REGISTRY: Dict[str, Type[BaseMessage]] = {}

def register_message_type(message_type: str, message_class: Type[BaseMessage]):
    MESSAGE_REGISTRY[message_type] = message_class

def create_message(message_type: str, **kwargs) -> BaseMessage:
    if message_type not in MESSAGE_REGISTRY:
        raise ValueError(f"Message type {message_type} is not registered.")
    return MESSAGE_REGISTRY[message_type](message_type=message_type, **kwargs)
