# Message Loop Prevention System

This package provides a comprehensive solution for preventing message loops in the FMOFP system, particularly for VIL (Vertically Integrated Liquid) and precipitation data.

## Overview

The message loop prevention system is designed to detect and prevent infinite loops in message processing. It works by tracking messages as they flow through the system and preventing the same message from being processed multiple times.

## Components

The system consists of several components:

### Core Components

- **MessageIdentifier**: Generates unique identifiers for messages based on their content.
- **MessageRegistry**: Tracks which messages have been processed to detect loops.
- **MessageLoopPrevention**: Central service that coordinates the identification and tracking of messages.

### Integration Components

- **Decorators**: Provide easy integration with existing code through method decorators.
- **Middleware**: Allows integration with the routing pipeline.
- **Configuration**: Provides customization options for the system.

## Usage

### Basic Usage

To use the message loop prevention system, you can use the decorators to wrap your message handling methods:

```python
from FMOFP.Utils.message_loop_prevention import prevent_message_loops, prevent_message_loops_async

# For synchronous methods
@prevent_message_loops(service_name="my_service")
def handle_message(message):
    # Process message
    pass

# For asynchronous methods
@prevent_message_loops_async(service_name="my_service")
async def handle_message_async(message):
    # Process message asynchronously
    pass
```

### Middleware Integration

For more complex scenarios, you can use the middleware to integrate with the routing pipeline:

```python
from FMOFP.Utils.message_loop_prevention import get_loop_prevention_middleware

def route_message(message):
    # Get middleware
    middleware = get_loop_prevention_middleware()
    
    # Check for loops
    should_process, enhanced_message = middleware.process_message(message, "my_router")
    
    if not should_process:
        # Message is part of a loop, skip processing
        return False
        
    # Continue with normal routing using enhanced message
    # ...
```

### Configuration

The system can be configured using a JSON configuration file. You can specify the path to the configuration file using the `MESSAGE_LOOP_PREVENTION_CONFIG` environment variable:

```bash
export MESSAGE_LOOP_PREVENTION_CONFIG=/path/to/config.json
```

Alternatively, you can load the configuration programmatically:

```python
from FMOFP.Utils.message_loop_prevention import get_config

# Load configuration from file
config = get_config()
config.load_from_file("/path/to/config.json")

# Update configuration
config.update_config({
    "enabled": True,
    "services": {
        "my_service": {
            "enabled": True,
            "max_tracked_messages": 500
        }
    }
})
```

## Configuration Options

The configuration file supports the following options:

```json
{
  "enabled": true,
  "log_level": "warning",
  "max_tracked_messages": 1000,
  "expiration_time": 60.0,
  "services": {
    "service_name": {
      "enabled": true,
      "max_tracked_messages": 500,
      "expiration_time": 30.0
    }
  },
  "categories": {
    "category_name": {
      "enabled": true,
      "max_tracked_messages": 500,
      "expiration_time": 30.0
    }
  }
}
```

- **enabled**: Whether the message loop prevention system is enabled.
- **log_level**: The log level for the system.
- **max_tracked_messages**: The maximum number of messages to track.
- **expiration_time**: The time in seconds after which a message is no longer considered for loop detection.
- **services**: Service-specific configuration.
- **categories**: Category-specific configuration.

## Monitoring

The system provides statistics about message processing:

```python
from FMOFP.Utils.message_loop_prevention import get_loop_prevention_middleware

# Get middleware
middleware = get_loop_prevention_middleware()

# Get statistics
stats = middleware.get_stats()
print(f"Processed messages: {stats['messages_processed']}")
print(f"Prevented loops: {stats['loops_detected']}")
```

## Troubleshooting

If you encounter issues with the message loop prevention system, you can:

1. Check the logs for warnings and errors.
2. Disable the system temporarily to see if it's causing the issue.
3. Clear the registry to reset the system.

```python
from FMOFP.Utils.message_loop_prevention import get_loop_prevention_middleware

# Get middleware
middleware = get_loop_prevention_middleware()

# Disable middleware
middleware.disable()

# Clear registry
middleware.clear_registry()

# Reset statistics
middleware.reset_stats()
```

## Example: Preventing VIL Data Loops

The system is particularly useful for preventing loops in VIL data processing:

```python
from FMOFP.Utils.message_loop_prevention import prevent_message_loops_async

class VILHandler:
    @prevent_message_loops_async(service_name="vil_handler")
    async def handle_message(self, message):
        # Process VIL data
        # ...
```

This ensures that each VIL data message is processed only once, preventing infinite loops in the system.
