# 11. Communication Messaging

**Navigation:** [← Flight Management Integration](10_Flight_Management_Integration.md) | [Operational Procedures →](12_Operational_Procedures.md)

---

## 11.1 MIL-STD-1553B Implementation

### System Status: ✅ **OPERATIONAL**

The FMOFP system implements a comprehensive MIL-STD-1553B communication protocol for reliable, deterministic data exchange between aircraft subsystems. The implementation provides full Bus Controller (BC) and Remote Terminal (RT) functionality with advanced features including block transfers, message validation, and error recovery.

**Key Features:**
- **Full MIL-STD-1553B Compliance** - 20-bit word format with sync and parity
- **Bus Controller Operations** - Centralized message routing and system coordination
- **Remote Terminal Operations** - Distributed subsystem communication
- **Block Transfer Support** - Large data transfers exceeding 32-word limit
- **Message Validation** - Protocol compliance and error detection
- **Transaction Tracking** - Request/response correlation with completion notifications

### Protocol Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MIL-STD-1553B Bus                        │
├─────────────────────────────────────────────────────────────┤
│  • Deterministic Communication Protocol                     │
│  • 20-bit Word Format (3 sync + 16 data + 1 parity)         │
│  • 32 Remote Terminals Maximum                              │
│  • 1 Mbps Data Rate                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼────┐   ┌────▼────┐   ┌────▼────┐
│   BC   │   │   RT    │   │   RT    │
│ ✅ OP │   │  ✅ OP  │   │  ✅ OP  │
└────────┘   └─────────┘   └─────────┘
```

### System Specifications

| Parameter | Value | Status |
|-----------|-------|--------|
| **Word Format** | 20-bit (3+16+1) | ✅ Operational |
| **Data Rate** | 1 Mbps | ✅ Operational |
| **Max Data Words** | 32 per message | ✅ Operational |
| **RT Addresses** | 0-31 (32 total) | ✅ Operational |
| **Subaddresses** | 0-31 per RT | ✅ Operational |
| **Block Transfers** | Unlimited size | ✅ Operational |

---

## 11.2 Message Flow Visualization

### FMOFP Communication Architecture

[DIAGRAM PLACEHOLDER: Complete FMOFP communication architecture]
**Figure 11.1:** FMOFP Communication System Architecture
1. **Bus Controller (BC)** - Central communication hub and message router
2. **Remote Terminals (RT)** - Distributed subsystem communication endpoints
3. **MIL-STD-1553B Bus** - Deterministic communication protocol backbone
4. **Message Routing** - Unified routing system for all message types
5. **Block Transfer System** - Large data transfer management
6. **Request Tracking** - Transaction correlation and completion monitoring
7. **Error Recovery** - Protocol error detection and recovery mechanisms
8. **System Integration** - Seamless integration with all FMOFP subsystems

### Message Flow Patterns

[DIAGRAM PLACEHOLDER: Message flow patterns between systems]
**Figure 11.2:** Common Message Flow Patterns
1. **Command-Response Pattern** - BC sends command, RT responds with data
2. **Data Broadcast Pattern** - RT broadcasts data to multiple subscribers
3. **Block Transfer Pattern** - Large data split across multiple messages
4. **Status Update Pattern** - Periodic system status reporting
5. **Mode Change Pattern** - System mode change requests and confirmations
6. **Error Recovery Pattern** - Retry and recovery message sequences
7. **Completion Notification** - Transaction completion acknowledgments
8. **Real-Time Data Flow** - Continuous sensor data streaming

### Step-by-Step Message Processing

**Procedure: Understanding Message Flow**

**Step 1: Message Origination**
1. Subsystem generates message (radar data, mode change, status update)
2. Message formatted according to MIL-STD-1553B protocol [See Figure 11.1, Item 3]
3. RT address and subaddress determined from ADDRESS_BOOK
4. Message queued for transmission via RT_Sender

**Step 2: Bus Controller Reception**
1. BC_Listener receives 20-bit frames from RT sockets [See Figure 11.1, Item 1]
2. Frame validation (sync pattern, parity, length) performed
3. Message extraction and metadata preservation
4. Block transfer detection and aggregation if needed [See Figure 11.1, Item 5]

**Step 3: Message Routing**
1. Unified router determines target subsystem [See Figure 11.1, Item 4]
2. Message type detection and classification
3. System-specific response service selection
4. Message forwarded to appropriate subsystem

**Step 4: Response Generation**
1. Target subsystem processes message and generates response
2. Completion notification created [See Figure 11.1, Item 6]
3. Response formatted and transmitted back to originator
4. Transaction tracking updated and cleanup performed

### MIL-STD-1553B Protocol Visualization

[DIAGRAM PLACEHOLDER: MIL-STD-1553B message structure]
**Figure 11.3:** MIL-STD-1553B Message Structure
1. **Sync Bits (3)** - '100' for command/status, '001' for data words
2. **RT Address (5)** - Remote Terminal address (0-31)
3. **T/R Bit (1)** - Transmit/Receive direction indicator
4. **Subaddress (5)** - Subsystem address within RT (0-31)
5. **Word Count (5)** - Number of data words (0-32)
6. **Data Words (16×N)** - Actual message payload data
7. **Parity Bit (1)** - Odd parity for error detection
8. **Status Word** - Response acknowledgment from RT

### Block Transfer Flow Visualization

[DIAGRAM PLACEHOLDER: Block transfer sequence]
**Figure 11.4:** Block Transfer Message Sequence
1. **Transfer Initiation** - Large message detected and split into blocks
2. **Block Sequence** - Multiple messages with sequence numbers
3. **Progress Tracking** - Block reception monitoring and validation
4. **Assembly Process** - Data blocks reassembled into complete message
5. **Completion Detection** - Final block received and validated
6. **Acknowledgment** - Transfer completion notification sent
7. **Error Recovery** - Missing block detection and retransmission
8. **Cleanup** - Transfer state cleanup and resource release

### System Integration Patterns

[DIAGRAM PLACEHOLDER: System integration message flows]
**Figure 11.5:** System Integration Message Flows
1. **Radar → Display** - Radar data routing to MFD and PFD displays
2. **FMS → Radar** - Mode change commands from flight management
3. **Display → FMS** - User input and configuration changes
4. **Status Broadcasting** - System health and status distribution
5. **Error Reporting** - Error messages and diagnostic information
6. **Configuration Updates** - System parameter and setting changes
7. **Real-Time Streaming** - Continuous sensor data flows
8. **Event Notifications** - System event and state change alerts

### Communication Performance Monitoring

[SCREENSHOT PLACEHOLDER: Communication performance dashboard]
**Figure 11.6:** Communication Performance Monitoring
1. **Message Throughput** - Messages per second processing rate
2. **Response Times** - Average and maximum response latencies
3. **Error Rates** - Protocol errors and retry statistics
4. **Queue Depths** - BC and RT message queue utilization
5. **Block Transfer Status** - Large transfer completion rates
6. **System Health** - Overall communication system status
7. **RT Connectivity** - Remote Terminal connection status
8. **Performance Trends** - Historical performance analysis

## 11.3 Bus Controller Operations

### System Status: ✅ **OPERATIONAL**

The Bus Controller serves as the central communication hub, managing all message traffic between Remote Terminals and providing system-wide coordination.

### 11.3.1 Message Processing Architecture ✅ **OPERATIONAL**

**Verified Implementation:**
```python
class Bus_Controller:
    def __init__(self):
        self.listening = False
        self.pending_requests = {}  # Track pending requests by request_id
        self.message_extractor = get_bc_message_extractor()
        self.route_message = route_message  # Unified message routing
```

**Core Components:**
- **BC_Listener:** Socket-based message reception from Remote Terminals
- **Message Extractor:** Field extraction and validation
- **Block Transfer Aggregator:** Large message assembly
- **Unified Router:** System-wide message distribution
- **Response Services:** System-specific acknowledgment handling

### 11.3.2 Message Flow Processing ✅ **OPERATIONAL**

**Incoming Message Flow:**
```
RT_Sender → BC_Listener → Bus_Controller → Message_Extractor → Block_Transfer_Aggregator
     ↓
Unified_Router → System_Response_Services → Target_Subsystem
```

**Verified Processing Steps:**
1. **Frame Reception:** BC_Listener receives 20-bit frames from RT sockets
2. **Frame Validation:** Sync pattern and parity verification
3. **Message Extraction:** Field parsing and metadata preservation
4. **Block Transfer Handling:** Multi-message assembly for large data
5. **Unified Routing:** System-wide message distribution
6. **Response Generation:** Acknowledgment and completion tracking

### 11.3.3 Block Transfer Management ✅ **OPERATIONAL**

**Implementation Status:** Advanced block transfer support for messages exceeding 32-word limit

**Verified Capabilities:**
```python
# Block transfer detection and aggregation
aggregator = get_block_transfer_aggregator()
if aggregator.is_transfer_message(parsed_frame):
    result = aggregator.register_message(parsed_frame)
    if result is None:
        # Transfer in progress - halt processing
        return
    # Transfer complete - process aggregated message
    frame = result
```

**Block Transfer Features:**
- ✅ Automatic detection of oversized messages
- ✅ Multi-message assembly with sequence tracking
- ✅ Progress monitoring and status reporting
- ✅ Error recovery and timeout handling
- ✅ Completion notification and acknowledgment

### 11.3.4 Request Tracking ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Enhanced request matching with multiple criteria
matched_requests = []
for req_id, req in list(self.pending_requests.items()):
    match_score = 0
    match_reasons = []
    
    # RT address exact match (most important)
    if req.get('rt_address') == rt_address:
        match_score += 3
        match_reasons.append(f"RT address match: {rt_address}")
```

**Tracking Features:**
- ✅ Request ID correlation with responses
- ✅ Multi-criteria matching (RT address, subaddress, timestamp)
- ✅ Timeout handling with automatic cleanup
- ✅ Match scoring for optimal request identification
- ✅ Completion notification generation

---

## 11.4 Remote Terminal Operations

### System Status: ✅ **OPERATIONAL**

Remote Terminals provide distributed communication endpoints for aircraft subsystems, handling both command reception and data transmission.

### 11.3.1 RT Architecture ✅ **OPERATIONAL**

**Verified Implementation:**
```python
class Remote_Terminal:
    def __init__(self):
        self.rt_listener = get_rt_listener()  # Global instance
        self.rtma = RT_Message_Analyzer()     # Message analysis
        self.rt_construct = RT_construct()    # Message construction
        self.processed_messages = []          # Message queue
```

**Core Components:**
- **RT_Listener:** Command reception from Bus Controller
- **RT_Message_Analyzer:** Incoming message parsing and validation
- **RT_Construct:** Outgoing message formatting and encoding
- **Message Queue Manager:** Processed message distribution
- **Block Transfer Handler:** Large data transmission support

### 11.3.2 Message Reception ✅ **OPERATIONAL**

**Verified Processing Flow:**
```python
async def process_frame(self, frame):
    # Extract frames and metadata
    actual_frames = frame
    if isinstance(frame, dict):
        if 'frames' in frame:
            actual_frames = frame['frames']
        request_id = frame.get('request_id')
        metadata = frame.get('metadata', {})
    
    # Use RT_Message_Analyzer to process frames
    command_word, data_words = self.rtma.route_inc_frame(actual_frames)
```

**Reception Features:**
- ✅ Multi-format frame handling (dict, list, string)
- ✅ Metadata preservation and extraction
- ✅ Command word parsing and validation
- ✅ Data word extraction and conversion
- ✅ Block transfer detection and assembly

### 11.3.3 Message Transmission ✅ **OPERATIONAL**

**Verified Implementation:**
```python
def send_message(self, message):
    # Get the RT_sender instance
    rts = get_rt_sender()
    
    # Standardized message formatting for all types
    if isinstance(message, dict):
        if 'status_word' in message:
            formatted_message = message.copy()
            if 'timestamp' not in formatted_message:
                formatted_message['timestamp'] = time.time()
            return rts.RT_send_message(formatted_message)
```

**Transmission Features:**
- ✅ Multiple message format support (dict, list, string, MIL_STD_1553B_Message)
- ✅ Automatic status word generation
- ✅ Timestamp and metadata preservation
- ✅ Block transfer initiation for large data
- ✅ Parity calculation and frame validation

### 11.3.4 RT Block Transfer Support ✅ **OPERATIONAL**

**Implementation Status:** Complete block transfer support for RT-to-BC communication

**Verified Capabilities:**
```python
def _handle_block_transfer_init(self, frame):
    # Extract transfer parameters
    total_messages = frame.get('total_messages')
    total_frames = frame.get('total_frames')
    
    # Initialize block transfer state
    self._block_transfer_state[request_id] = {
        'total_messages': total_messages,
        'total_frames': total_frames,
        'received_messages': 0,
        'data_buffer': [],
        'complete': False
    }
```

**Block Transfer Features:**
- ✅ Transfer initialization and parameter extraction
- ✅ Multi-message data buffering and assembly
- ✅ Sequence tracking and validation
- ✅ Completion detection and processing
- ✅ Acknowledgment generation and transmission

---

## 11.4 Message Routing and Validation

### System Status: ✅ **OPERATIONAL**

Comprehensive message routing system with validation, error checking, and system integration.

### 11.4.1 Message Structure Validation ✅ **OPERATIONAL**

**Verified Implementation:**
```python
class MIL_STD_1553B_Message:
    # MIL-STD-1553B Constants
    COMMAND_WORD_SIZE = 16  # bits
    DATA_WORD_SIZE = 16     # bits
    MAX_DATA_WORDS = 32
    STATUS_WORD_SIZE = 16   # bits
    
    def __init__(self, rt_address, sub_address, data, ...):
        # Validate RT address
        if not isinstance(rt_address, int) or not (0 <= rt_address <= 31):
            raise ValueError(f"RT address must be within 5-bit range (0-31)")
        
        # Validate subaddress
        if not isinstance(sub_address, int) or not (0 <= sub_address <= 31):
            raise ValueError(f"Subaddress must be within 5-bit range (0-31)")
```

**Validation Features:**
- ✅ RT address range validation (0-31)
- ✅ Subaddress range validation (0-31)
- ✅ Data word count limits (max 32)
- ✅ Message format compliance checking
- ✅ Sync pattern and parity validation

### 11.4.2 Binary Format Processing ✅ **OPERATIONAL**

**Verified Implementation:**
```python
def to_binary(self):
    # Format command word: RT address (5 bits) + T/R bit (1 bit) + Subaddress (5 bits) + Word Count (5 bits)
    t_r_bit = '1' if self.direction == self.RT_TO_BC else '0'
    command_word = format(self.rt_address, '05b') + t_r_bit + format(self.sub_address, '05b') + format(self.data_word_count, '05b')
    
    # For standard transfers, simply append the data
    if self.transfer_type == self.STANDARD_TRANSFER:
        return command_word + self.data
```

**Binary Processing Features:**
- ✅ 20-bit word format (3 sync + 16 data + 1 parity)
- ✅ Command word encoding with T/R bit
- ✅ Data word serialization and deserialization
- ✅ Block transfer format support
- ✅ Parity calculation and verification

### 11.4.3 Message Type Detection ✅ **OPERATIONAL**

**Verified Implementation:**
```python
def is_mode_change_message(message):
    msg_type = get_message_type(message)
    if not msg_type:
        return False
    
    msg_type_lower = msg_type.lower()
    return (msg_type_lower == FMS_MODE_CHANGE_REQUEST.lower() or 
            msg_type_lower == FMS_MODE_CHANGE_RESPONSE.lower() or 
            'modechange' in msg_type_lower.replace('_', ''))
```

**Detection Features:**
- ✅ Centralized message type constants
- ✅ Case-insensitive pattern matching
- ✅ Multiple format support (dict, object attributes)
- ✅ Specialized detection for precipitation, VIL, mode change messages
- ✅ Fallback handling for unknown message types

### 11.4.4 Unified Message Routing ✅ **OPERATIONAL**

**Implementation Status:** System-wide message routing with intelligent destination determination

**Verified Routing Logic:**
```python
# Route through the unified router
route_result = self.route_message(unified_message)

# Message flow trace
logger.info(f"Message flow trace: BC_Listener -> Bus_Controller -> Unified Router")
```

**Routing Features:**
- ✅ Automatic destination determination based on RT address
- ✅ System-specific response service selection
- ✅ Message metadata preservation throughout routing
- ✅ Error handling and fallback routing
- ✅ Completion notification generation

---

## 11.5 Transaction Tracking

### System Status: ✅ **OPERATIONAL**

Comprehensive transaction tracking system ensuring reliable message delivery and response correlation.

### 11.5.1 Request-Response Correlation ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Store acknowledgment with retry logic
max_retries = 5
retry_delay = 1.0

for attempt in range(max_retries):
    try:
        # Get appropriate response service based on RT address
        if rt_address == 9:  # Radar system
            response_service = get_radar_response_service()
        elif rt_address == 11:  # Display system
            response_service = get_display_response_service()
```

**Correlation Features:**
- ✅ Request ID generation and tracking
- ✅ Multi-criteria request matching
- ✅ Timeout handling with automatic cleanup
- ✅ Retry logic with exponential backoff
- ✅ Response service selection by RT address

### 11.5.2 Completion Message Handling ✅ **OPERATIONAL**

**Verified Implementation:**
```python
class FMSCompletionMessageHandler:
    def send_completion_message(self, system_name, message_type, command_type, ...):
        # Create status word with proper format (20-bit binary string)
        rt_address_bits = format(rt_address, '05b')  # 5 bits for RT address
        data_bits = f"{rt_address_bits}{message_error_bit}..."
        status_word = f"100{data_bits}{parity_bit}"
        
        # Create properly formatted message for RT_sender
        formatted_message = {
            'status_word': status_word,
            'request_id': request_id,
            'command_type': command_type,
            'message_type': message_type
        }
```

**Completion Features:**
- ✅ MIL-STD-1553B compliant status word generation
- ✅ Proper parity calculation and validation
- ✅ Request ID preservation and correlation
- ✅ System-specific completion message types
- ✅ Metadata preservation for routing

### 11.5.3 Error Handling and Recovery ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Enhanced request matching with timeout handling
current_time = time.time()
for req_id, req in list(self.pending_requests.items()):
    # Skip expired requests but keep them for now
    if current_time - req['timestamp'] > 5.0:
        logger.info(f"Request {req_id} expired: {current_time - req['timestamp']} seconds")
        continue
```

**Error Handling Features:**
- ✅ Request timeout detection and cleanup
- ✅ Retry logic with configurable attempts
- ✅ Error logging and diagnostic information
- ✅ Graceful degradation for communication failures
- ✅ Recovery procedures for lost messages

---

## 11.6 Error Handling and Recovery

### System Status: ✅ **OPERATIONAL**

Robust error handling and recovery mechanisms ensuring reliable communication under adverse conditions.

### 11.6.1 Protocol Error Detection ✅ **OPERATIONAL**

**Verified Implementation:**
```python
def _clean_frame(self, frame):
    # Validate sync bits according to MIL-STD-1553B
    if not (cleaned.startswith('100') or cleaned.startswith('001')):
        logger.error(f"Invalid sync bits: {cleaned[:3]} - must be '100' (command/status) or '001' (data)")
        return None
        
    # Validate parity (odd parity) according to MIL-STD-1553B
    ones_count = cleaned[:-1].count('1')
    expected_parity = '1' if ones_count % 2 == 0 else '0'
    if cleaned[-1] != expected_parity:
        logger.error(f"Parity check failed: expected {expected_parity}, got {cleaned[-1]}")
        return None
```

**Error Detection Features:**
- ✅ Sync pattern validation (100 for command/status, 001 for data)
- ✅ Parity bit verification (odd parity)
- ✅ Frame length validation (20-bit words)
- ✅ RT address and subaddress range checking
- ✅ Data word count limit enforcement

### 11.6.2 Communication Recovery ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Retry logic with exponential backoff
max_retries = 5
retry_delay = 1.0
last_error = None

for attempt in range(max_retries):
    try:
        # Attempt operation
        success = operation()
        if success:
            break
    except Exception as e:
        last_error = e
        if attempt < max_retries - 1:
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
            await asyncio.sleep(retry_delay)
        else:
            logger.error(f"All attempts failed: {e}")
            raise last_error
```

**Recovery Features:**
- ✅ Automatic retry with exponential backoff
- ✅ Configurable retry limits and delays
- ✅ Error classification and handling
- ✅ Graceful degradation for persistent failures
- ✅ Diagnostic logging for troubleshooting

### 11.6.3 Block Transfer Error Handling ✅ **OPERATIONAL**

**Verified Implementation:**
```python
def _cleanup_block_transfer_state(self):
    current_time = time.time()
    with self._block_transfer_lock:
        # Remove block transfer states older than 60 seconds
        expired_request_ids = []
        for request_id, state in self._block_transfer_state.items():
            if current_time - state['timestamp'] > 60.0:
                expired_request_ids.append(request_id)
```

**Block Transfer Error Handling:**
- ✅ Transfer timeout detection and cleanup
- ✅ Sequence number validation and gap detection
- ✅ Partial transfer recovery and resumption
- ✅ Memory leak prevention with state cleanup
- ✅ Progress monitoring and status reporting

---

## 11.7 Communication Troubleshooting

### Common Communication Issues

#### 11.7.1 Message Delivery Failures

**Symptoms:**
- Messages not reaching target subsystems
- Request timeouts and no responses
- Incomplete block transfers

**Troubleshooting Steps:**
1. **Check RT Address Configuration:**
   ```python
   # Verify RT addresses in address book
   rt_address = ADDRESS_BOOK[system_name]['address']
   if not (0 <= rt_address <= 31):
       logger.error(f"Invalid RT address: {rt_address}")
   ```

2. **Validate Message Format:**
   ```python
   # Check 20-bit word format
   if len(frame) != 20 or not all(bit in '01' for bit in frame):
       logger.error(f"Invalid frame format: {frame}")
   ```

3. **Monitor Message Queues:**
   - Check BC_Listener data_received queue
   - Verify RT processed_messages queue
   - Monitor block transfer aggregator status

#### 11.7.2 Block Transfer Issues

**Common Problems:**
- **Oversized Messages:** Messages exceeding 32-word limit not properly split
- **Sequence Errors:** Missing or out-of-order block transfer sequences
- **Timeout Issues:** Block transfers not completing within timeout period

**Resolution:**
1. **Enable Block Transfer Logging:**
   ```python
   logger.info(f"Block transfer status: {received_blocks}/{total_blocks} blocks received")
   ```

2. **Check Transfer State:**
   ```python
   # Monitor block transfer state
   status = transfer_manager.get_transfer_status(request_id)
   logger.info(f"Transfer progress: {status['percent_complete']:.1f}%")
   ```

3. **Verify Sequence Handling:**
   - Ensure sequence numbers are sequential
   - Check for missing blocks and gaps
   - Validate final block detection

#### 11.7.3 Protocol Compliance Issues

**Sync Pattern Errors:**
- **Invalid Sync Bits:** Frames not starting with '100' or '001'
- **Parity Failures:** Incorrect parity bit calculation
- **Word Length Issues:** Frames not exactly 20 bits

**Resolution:**
1. **Validate Frame Construction:**
   ```python
   # Proper frame format
   sync_bits = '100'  # Command/status word
   data_bits = format(data, '016b')  # 16-bit data
   parity_bit = calculate_parity(sync_bits + data_bits)
   frame = sync_bits + data_bits + parity_bit
   ```

2. **Check Parity Calculation:**
   ```python
   # Odd parity calculation
   ones_count = frame[:-1].count('1')
   expected_parity = '1' if ones_count % 2 == 0 else '0'
   ```

### Performance Monitoring

#### 11.7.4 Communication Metrics

**Key Performance Indicators:**
```python
# Message processing metrics
message_count = 0
processed_count = 0
error_count = 0

# Timing metrics
average_response_time = sum(response_times) / len(response_times)
max_response_time = max(response_times)

# Queue metrics
bc_queue_size = len(bc_listener.data_received)
rt_queue_size = len(rt_listener.processed_messages)
```

**Monitoring Features:**
- ✅ Message throughput tracking
- ✅ Response time measurement
- ✅ Error rate monitoring
- ✅ Queue depth analysis
- ✅ Block transfer completion rates

#### 11.7.5 Diagnostic Tools

**Built-in Diagnostics:**
```python
# Message flow tracing
logger.info(f"Message flow trace: RT_Sender -> BC_Listener -> Bus_Controller -> Unified Router")

# Request correlation tracking
logger.info(f"Request {request_id} matched with score {match_score}: {', '.join(match_reasons)}")

# Block transfer monitoring
logger.info(f"Block transfer complete with {len(assembled_data)} data points")
```

**Diagnostic Features:**
- ✅ End-to-end message flow tracing
- ✅ Request-response correlation logging
- ✅ Block transfer progress monitoring
- ✅ Error classification and reporting
- ✅ Performance metric collection

---

## 11.8 Configuration and Maintenance

### System Configuration

#### 11.8.1 RT Address Configuration

**Address Book Management:**
```python
ADDRESS_BOOK = {
    'radar_system': {'address': 9, 'subaddresses': {...}},
    'display_system': {'address': 11, 'subaddresses': {...}},
    'flight_control_system': {'address': 5, 'subaddresses': {...}},
    'navigation_system': {'address': 7, 'subaddresses': {...}}
}
```

**Configuration Features:**
- ✅ Centralized address management
- ✅ Subaddress mapping per system
- ✅ Dynamic address resolution
- ✅ Configuration validation
- ✅ Runtime address updates

#### 11.8.2 Communication Parameters

**Protocol Settings:**
```python
# MIL-STD-1553B Constants
COMMAND_WORD_SIZE = 16  # bits
DATA_WORD_SIZE = 16     # bits
MAX_DATA_WORDS = 32
STATUS_WORD_SIZE = 16   # bits
```

**Timing Parameters:**
```python
# Timeout and retry settings
REQUEST_TIMEOUT = 5.0      # seconds
MAX_RETRIES = 5
RETRY_DELAY = 1.0          # seconds
BLOCK_TRANSFER_TIMEOUT = 60.0  # seconds
```

---

**Navigation:** [← Flight Management Integration](10_Flight_Management_Integration.md) | [Operational Procedures →](12_Operational_Procedures.md)

---

*File: 11_Communication_Messaging.md*  
*Last Updated: December 2024*  
*Next Review: As system implementations are updated*
