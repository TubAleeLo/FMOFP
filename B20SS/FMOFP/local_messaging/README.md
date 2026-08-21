# FMOFP Messaging System

## Overview

This directory contains the messaging infrastructure for the Flight Management Operating Flight Program (FMOFP). The messaging system handles communication between various components, including radar systems, display systems, and hardware interfaces using MIL-STD-1553B protocol.

## Directory Structure

- **`Bus_Controller/`**: Bus Controller (BC) implementation for MIL-STD-1553B communication
- **`local_messaging/`**: Internal messaging between FMOFP components
- **`messageConfigurations/`**: Message type definitions and configuration
- **`MIL_STD_1553B/`**: Military standard 1553B protocol implementation
- **`Remote_Terminal/`**: Remote Terminal (RT) implementation for MIL-STD-1553B
- **`routing/`**: Unified routing architecture including special case handlers

## Key Components

### Unified Router

Located in `routing/unified_router.py`, the UnifiedRouter provides a centralized message routing system that integrates all messaging components:

```python
# Use the Unified Router for message routing to ensure proper deduplication
from FMOFP.Msg_handler.routing.system_integration import route_message

# Example usage
await route_message(message_dict)
```

### Special Case Handlers

Special message types are handled by dedicated handlers in `routing/handlers/`:

- `mode_change_handler.py`: Manages mode change messages
- `precipitation_handler.py`: Handles precipitation data
- `vil_handler.py`: Processes Vertically Integrated Liquid data

### Response Services

Response services in `local_messaging/` handle specific system responses:

- `DisplayResponseService.py`: Display system responses
- `RadarResponseService.py`: Radar system responses
- `precipitation/precipitation_response_service.py`: Specialized precipitation data handling

## Best Practices

### 1. Message Routing

Always use the Unified Router for message routing:

```python
# GOOD: Route through unified router
from FMOFP.Msg_handler.routing.system_integration import route_message
await route_message(message_dict)

# BAD: Direct service calls bypass proper routing
# await radar_response_service.handle_mode_change(message_dict)
```

### 2. Transaction Tracking

Always include transaction IDs in messages to prevent loops:

```python
# Generate transaction ID
import uuid
transaction_id = str(uuid.uuid4())

# Include in message metadata
if 'metadata' not in message:
    message['metadata'] = {}
message['metadata']['transaction_id'] = transaction_id

# Also include in additional_info for backward compatibility
if 'additional_info' not in message:
    message['additional_info'] = {}
message['additional_info']['transaction_id'] = transaction_id
```

### 3. Message Deduplication

Check if a message has already been processed before handling:

```python
# Check transaction ID
if transaction_id in self._processed_transactions:
    logger.info(f"Skipping already processed transaction: {transaction_id}")
    return True
    
# Check processing flags
if message.get('metadata', {}).get('_processed_by_my_component'):
    logger.info(f"Message already processed by this component")
    return True
```

### 4. Message Processing Flags

Mark messages as processed to prevent loops:

```python
# Add processing flag
message['metadata']['_processed_by_my_component'] = True

# Add to processed transactions
self._processed_transactions.add(transaction_id)
```

### 5. System Separation

Respect system boundaries by using the appropriate channels:

```python
# GOOD: Use ResponseServiceAdapter for consistent access
from FMOFP.Msg_handler.routing.response_service_adapter import get_response_service_adapter
response_service_adapter = get_response_service_adapter()
await response_service_adapter.handle_mode_change(message)

# BAD: Bypassing the adapter can create inconsistent state
# from FMOFP.Msg_handler.local_messaging.RadarResponseService import get_radar_response_service
# radar_service = get_radar_response_service()
# await radar_service.handle_mode_change_data(message)
```

## Message Flow Examples

### Mode Change Flow

```
1. Radar system → MIL-STD-1553B → Bus Controller
2. UnifiedRouter → ModeChangeHandler
3. ModeChangeHandler → RadarResponseService (via ResponseServiceAdapter)
4. RadarResponseService stores mode change and creates acknowledgment
5. For completion messages: ModeChangeHandler → DisplayResponseService
```

### Precipitation Data Flow

```
1. Radar system → MIL-STD-1553B → Bus Controller
2. UnifiedRouter → PrecipitationHandler
3. PrecipitationHandler → PrecipitationResponseService
4. PrecipitationResponseService → DisplayMessageHandler
```

## Common Issues and Solutions

### Message Loops

If messages are being processed multiple times:

1. Verify transaction ID generation and checking
2. Ensure processing flags are being set and checked
3. Avoid creating multiple paths for the same message type

### Database Errors

For "cannot start transaction within transaction" errors:

1. Let DBM handle transactions automatically
2. Avoid explicit BEGIN/COMMIT in service code
3. Use DBM's transaction state tracking

### Missing Messages

If messages aren't reaching their destination:

1. Verify routing path is correct
2. Check for transaction ID mismatches
3. Ensure format conversion is handling all fields correctly

## Further Documentation

For more detailed information on the messaging system, refer to these documents:

- [Messaging System Architecture](../docs/Messaging/messaging_system_architecture.md)
- [Complete Message Reference](../docs/Messaging/complete_message_reference.md)
