# Messaging System Architecture

## Overview

The FMOFP messaging architecture consists of multiple interconnected subsystems that handle message creation, routing, and processing across system boundaries. This document explains how these systems interact, the message flow patterns, and best practices for maintaining system separation while ensuring reliable message delivery.

## Messaging Subsystems

### 1. Local Messaging System

**Location:** `FMOFP/Msg_handler/local_messaging/`

The local messaging system is responsible for:
- Internal message routing between FMOFP components
- Message creation for local communication
- Service-based handling of specific message types
- Event-driven communication patterns

Key components:
- `MessageRoutingService`: Central router for local messages
- `DisplayResponseService`: Handles display-related responses and commands
- `RadarResponseService`: Processes radar system responses and commands
- `PrecipitationResponseService`: Specialized handler for precipitation data

### 2. MIL-STD-1553B Hardware Messaging

**Location:** `FMOFP/Msg_handler/MIL_STD_1553B/`

This subsystem implements the military standard 1553B protocol for communication between avionics systems:
- Provides low-level data transfer between Remote Terminals (RT) and Bus Controller (BC)
- Handles command/status word formatting per MIL-STD-1553B specification
- Manages hardware-level communication through specialized data words

Key components:
- `mil_std_1553B.py`: Core protocol implementation
- `metadata_codec.py`: Encodes/decodes metadata fields
- `BC_words_decoder.py`: Processes Bus Controller words
- `RT_words_decoder.py`: Processes Remote Terminal words

### 3. Bus Controller System

**Location:** `FMOFP/Msg_handler/Bus_Controller/`

The Bus Controller manages MIL-STD-1553B bus operations:
- Controls message flow on the 1553B bus
- Schedules and prioritizes message transmission
- Handles message acknowledgments and status reporting

Key components:
- `BC.py`: Main Bus Controller implementation
- `BC_sender.py`: Handles message transmission from BC
- `BC_Listener.py`: Processes incoming messages to BC

### 4. Remote Terminal System

**Location:** `FMOFP/Msg_handler/Remote_Terminal/`

Remote Terminals represent individual subsystems on the 1553B bus:
- Receive and process commands from the Bus Controller
- Generate and send responses back to Bus Controller
- Implement system-specific functionality

Key components:
- `RT.py`: Main Remote Terminal implementation
- `RT_sender.py`: Handles message transmission from RT
- `RT_Listener.py`: Processes incoming messages to RT

### 5. Display Messenger

**Location:** `FMOFP/Msg_handler/local_messaging/DisplayMessageHandler.py`

Manages display-specific messaging:
- Handles visual data presentation
- Processes user interface commands
- Manages display state transitions

### 6. Radar Messenger

**Location:** `FMOFP/Systems/radarManagement/radar_messaging/`

Manages radar-specific messaging:
- Controls radar operation modes
- Processes sensor data
- Formats data for transmission

## Unified Routing Architecture

**Location:** `FMOFP/Msg_handler/routing/`

The unified routing architecture provides a consistent interface for message routing across all subsystems:

### Components

1. **UnifiedRouter** (`unified_router.py`):
   - Central routing component
   - Integrates validator, resolver, transformer, and dispatcher
   - Handles special case message routing

2. **System Integration** (`system_integration.py`):
   - Bridges unified routing with legacy components
   - Provides backward compatibility

3. **Special Case Handlers** (`routing/handlers/`):
   - `mode_change_handler.py`: Manages mode change messages
   - `precipitation_handler.py`: Handles precipitation data
   - `vil_handler.py`: Processes Vertically Integrated Liquid data

4. **Response Service Adapter** (`response_service_adapter.py`):
   - Provides standard interface to response services
   - Adapts between routing and service components

## Message Flow Patterns

### Standard Message Flow

1. Message originates from system (radar, display, etc.)
2. Message is formatted according to system's protocol
3. UnifiedRouter receives message through system_integration.route_message()
4. Router validates message format and resolves destination
5. If special case: routes to appropriate handler
6. If standard case: routes directly to destination
7. Destination system processes message and stores relevant data
8. Acknowledgments follow same path in reverse

### Mode Change Message Flow

```
1. Radar system initiates mode change
2. MIL-STD-1553B transports message to Bus Controller
3. Bus Controller routes through UnifiedRouter
4. ModeChangeHandler processes message:
   - Adds transaction ID and processing flags
   - Sends to RadarResponseService via ResponseServiceAdapter
   - Stores mode change in database
   - Creates status word acknowledgment
   - For completion messages: routes to DisplayResponseService
5. DisplayResponseService receives completion:
   - Verifies not already processed using transaction ID
   - Updates mode state in database
   - Forwards to DisplayMessageHandler for UI update
```

### Precipitation Data Flow

```
1. Radar system generates precipitation data
2. MIL-STD-1553B transports to Bus Controller
3. UnifiedRouter identifies precipitation message
4. PrecipitationHandler processes message:
   - Adds transaction ID and processing flags
   - Stores data via PrecipitationResponseService
   - Routes to DisplayMessageHandler for visualization
```

## Transaction Tracking and Loop Prevention

To prevent message loops and ensure each message is processed only once, we implement multiple safeguards:

### 1. Transaction IDs

Every message is assigned a unique transaction ID that follows it throughout its lifetime:

```python
# Generating transaction ID
transaction_id = str(uuid.uuid4())
message['metadata']['transaction_id'] = transaction_id
```

### 2. Processing Flags

Messages carry processing flags to indicate which components have already handled them:

```python
# Common processing flags
message['metadata']['_processed_by_mode_change_handler'] = True
message['metadata']['_processed_by_radar_response'] = True
message['metadata']['_processed_by_display_response'] = True
```

### 3. Component-Level Transaction Sets

Each component maintains a set of transactions it has already processed:

```python
# In ModeChangeHandler
if transaction_id in self._processed_transactions:
    logger.info(f"Skipping already processed transaction: {transaction_id}")
    return True
```

### 4. Cross-Component Verification

Components check if a message has been processed by other components:

```python
# In RadarResponseService
if metadata.get('_processed_by_mode_change_handler'):
    logger.info(f"Message already processed by ModeChangeHandler, skipping")
    return True
```

## Best Practices for Message Handling

1. **Always assign a transaction ID** to new messages:
   ```python
   if not transaction_id:
       transaction_id = str(uuid.uuid4())
   ```

2. **Check processing history** before handling a message:
   ```python
   if transaction_id in self._processed_transactions:
       return
   ```

3. **Mark messages as processed** after handling:
   ```python
   message['metadata']['_processed_by_component'] = True
   self._processed_transactions.add(transaction_id)
   ```

4. **Use a single routing path** for each message type:
   - Avoid creating duplicate paths for "reliability"
   - Standardize on ResponseServiceAdapter for service access
   - Let the UnifiedRouter handle special cases

5. **Respect system boundaries**:
   - Use proper channels for cross-system communication
   - Maintain clear separation between radar and display systems
   - Use the established message format for each system

## Common Message Formats

### Local Message Format

```python
{
    'command_type': 'mode_change',
    'request_id': 'unique-id',
    'timestamp': 1648245121.0,
    'data': {...},
    'metadata': {
        'transaction_id': 'uuid-string',
        'destination': 'display_system',
        '_processed_by_X': True
    },
    'additional_info': {...}
}
```

### MIL-STD-1553B Message Format

```python
MIL_STD_1553B_Message(
    rt_address=9,           # 5-bit Remote Terminal address 
    sub_address=1,          # 5-bit subaddress
    data=['010101...'],     # Array of 16-bit data words
    message_type='mode_change',
    command_type='mode_change_request'
)
```

## Troubleshooting Common Issues

### 1. Message Loops

**Symptoms:**
- Log shows the same message being processed multiple times
- System performance degrades over time
- Database shows duplicate entries

**Solutions:**
- Verify transaction ID generation and checking
- Ensure each component properly marks messages as processed
- Check that components verify processing flags from other components

### 2. Missing Messages

**Symptoms:**
- Expected updates don't appear in destination system
- Log shows message sent but not received

**Solutions:**
- Verify routing path is correct
- Check for transaction ID mismatches
- Ensure format conversion is correctly handling all fields

### 3. Transaction Conflicts

**Symptoms:**
- Database errors: "cannot start transaction within transaction"
- Incomplete data storage

**Solutions:**
- Use proper transaction management
- Let DBM handle transactions automatically 
- Avoid explicit BEGIN/COMMIT in service code
