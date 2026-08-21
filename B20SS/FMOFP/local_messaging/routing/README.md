# Unified Routing System

The Unified Routing System provides a centralized, consistent approach to message routing throughout the FMOFP system. It ensures that messages are properly validated, routed, transformed, and dispatched to the appropriate destinations.

## Components

### Routing Registry

The Routing Registry is the single source of truth for routing information in the FMOFP system. It loads system addresses, subaddresses, command types, and message types from XML files.

- **File**: `routing_registry.py`
- **Key Functions**:
  - `load_from_xml()`: Loads routing information from XML files
  - `get_system_by_rt_address()`: Gets system ID by RT address
  - `get_rt_address_by_system()`: Gets RT address by system ID
  - `get_subaddress()`: Gets subaddress value by system ID and subaddress ID
  - `get_command_value()`: Gets command value by system ID and command type
  - `get_message_type_info()`: Gets message type information
  - `get_special_case()`: Gets special case routing rule by message type
  - `is_special_case()`: Checks if a message is a special case

### Message Validator

The Message Validator validates message format and content against the Routing Registry. It checks RT addresses, subaddresses, and message types.

- **File**: `message_validator.py`
- **Key Functions**:
  - `validate_message()`: Validates a message against the routing registry
  - `_check_message_type()`: Checks if message is a valid type
  - `_check_required_fields()`: Checks if message has all required fields
  - `_validate_rt_address()`: Validates RT address against routing registry
  - `_validate_subaddress()`: Validates subaddress against routing registry

### Route Resolver

The Route Resolver determines message destinations based on routing rules. It handles special cases like VIL data, precipitation data, and mode changes.

- **File**: `route_resolver.py`
- **Key Functions**:
  - `resolve_routes()`: Resolves routes for a message
  - `_resolve_special_cases()`: Resolves routes for special cases
  - `_resolve_by_rt_address()`: Resolves routes based on RT address
  - `_resolve_by_content()`: Resolves routes based on message content

### Message Transformer

The Message Transformer transforms messages for each destination. It ensures consistent message format and adds routing metadata.

- **File**: `message_transformer.py`
- **Key Functions**:
  - `transform_message()`: Transforms a message for each destination
  - `_object_to_dict()`: Converts an object to a dictionary
  - `_add_routing_metadata()`: Adds routing metadata to a message
  - `_transform_for_radar()`: Applies radar-specific transformations
  - `_transform_for_display()`: Applies display-specific transformations

### Message Dispatcher

The Message Dispatcher dispatches messages to system queues. It handles message priorities and delivery confirmation.

- **File**: `message_dispatcher.py`
- **Key Functions**:
  - `dispatch_message()`: Dispatches a message to a system queue
  - `_get_message_priority()`: Gets message priority

### Unified Router

The Unified Router integrates the validator, resolver, transformer, and dispatcher components. It is the main entry point for the routing system.

- **File**: `unified_router.py`
- **Key Functions**:
  - `route_message()`: Routes a message to the appropriate destinations
  - `_check_special_case()`: Checks if a message is a special case

### Special Case Handlers

Special case handlers handle specific message types that require special routing logic.

- **Files**: `handlers/vil_handler.py`, `handlers/precipitation_handler.py`, `handlers/mode_change_handler.py`
- **Key Functions**:
  - `handle_message()`: Handles a special case message
  - `_extract_*_data()`: Extracts data from a message
  - `_create_*_message()`: Creates a message for a specific destination

### System Integration

The System Integration module integrates the Unified Router with the system manager.

- **File**: `system_integration.py`
- **Key Functions**:
  - `register_with_system_manager()`: Registers the Unified Router with the system manager
  - `initialize_routing_system()`: Initializes the routing system
  - `route_message()`: Routes a message using the Unified Router

## Configuration Files

### Address Book

The Address Book defines system addresses and subaddresses.

- **File**: `messageConfigurations/address_book.xml`

### Command Registry

The Command Registry defines command types and message types.

- **File**: `messageConfigurations/command_registry.xml`

## Usage

To use the Unified Router, you can either:

1. Use the `route_message()` function from the `system_integration` module:

```python
from FMOFP.Msg_handler.routing import route_message

# Route a message
success = route_message(message)
```

2. Get the Unified Router instance and call its `route_message()` method:

```python
from FMOFP.Msg_handler.routing import get_unified_router

# Get the Unified Router
router = get_unified_router()

# Route a message
success = router.route_message(message)
```

## Special Cases

The Unified Router handles the following special cases:

1. **VIL Data**: Messages containing Vertically Integrated Liquid data are routed to both radar and display systems.
2. **Precipitation Data**: Messages containing precipitation data are routed to both radar and display systems.
3. **Mode Changes**: Mode change messages are routed between radar and display systems.

## Message Type and Command Name Matching

The Unified Router uses exact message type and command name matching to determine message destinations. This ensures that messages are routed correctly and consistently throughout the system.

### Radar Message Types

The following radar message types are recognized:

- `weather_radarModeChangeRequest` 
- `weather_radarModeChangeResponse`
- `tfr_radarModeChangeRequest`
- `tfr_radarModeChangeResponse`
- `sar_radarModeChangeRequest`
- `sar_radarModeChangeResponse`
- `targeting_radarModeChangeRequest`
- `targeting_radarModeChangeResponse`
- `aewc_radarModeChangeRequest`
- `aewc_radarModeChangeResponse`
- `weather_radarStatusRequest`
- `weather_radarStatusResponse`
- `tfr_radarStatusRequest`
- `tfr_radarStatusResponse`
- `sar_radarStatusRequest`
- `sar_radarStatusResponse`
- `targeting_radarStatusRequest`
- `targeting_radarStatusResponse`
- `weather_radarVILResponse`
- `weather_radarPrecipitationResponse`

### Radar Command Names

The following radar command names are recognized:

- `radar_modeChange`
- `weather_radar_modeChange`
- `tfr_radar_modeChange`
- `sar_radar_modeChange`
- `targeting_radar_modeChange`
- `aewc_radar_modeChange`
- `radar_status`
- `weather_radar_status`
- `tfr_radar_status`
- `sar_radar_status`
- `targeting_radar_status`
- `aewc_radar_status`
- `radar_vilData`
- `radar_precipitationData`

### Display Message Types

The following display message types are recognized:

- `display_mode_request`
- `display_mode_response`
- `display_status_request`
- `display_status_response`
- `display_data_request`
- `display_data_response`
- `mode_change`
- `mode_change_completion`

### Display Command Names

The following display command names are recognized:

- `displays_modeChange`
- `displays_status`
- `displays_vilData`
- `displays_precipitationData`

### VIL Message Types

The following VIL message types are recognized:

- `weather_radarVILResponse`
- `weather_radarVILRequest`
- `vil_data`

### VIL Command Names

The following VIL command names are recognized:

- `radar_vilData`
- `displays_vilData`

## System Boundaries

The Unified Router respects system boundaries by:

1. Using the system manager to get the message queue manager
2. Providing a fallback to AsyncMessageHandler if needed
3. Not directly importing from Remote Terminal components
