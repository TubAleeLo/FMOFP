# Display System Architecture

## Complete Interface Files Structure

### 1. Scenario Files
- **FMOFP/Interfaces/scenarios/failureScenario.xml**: Failure scenario configuration
  - Defines system failure scenarios
  - Specifies failure conditions
  - Configures failure responses

- **FMOFP/Interfaces/scenarios/trainingScenario.xml**: Training scenario configuration
  - Defines training scenarios
  - Specifies training conditions
  - Configures training responses

### 2. Configuration Files
- **FMOFP/Interfaces/userInterface/controlPanel.xml**: Control panel layout configuration
  - Defines UI control elements
  - Specifies control panel structure
  - Configures user interactions

- **FMOFP/Interfaces/userInterface/hudLayout.xml**: HUD layout configuration
  - Defines heads-up display elements
  - Specifies display positions
  - Configures visual elements

### 2. Base Display Files
- **FMOFP/Interfaces/userInterface/displays/base_display.py**: Base display class
  - Defines DisplayType enum
  - Implements DisplayMode class
  - Provides BaseDisplay functionality

- **FMOFP/Interfaces/userInterface/displays/displays.py**: Display system manager
  - Coordinates display initialization
  - Manages display lifecycle
  - Handles display updates

- **FMOFP/Interfaces/userInterface/displays/mfd.py**: Multi-Function Display
  - Implements RadarData handling
  - Defines RadarType enums
  - Manages MultiFunctionDisplay

- **FMOFP/Interfaces/userInterface/displays/pfd.py**: Primary Flight Display
  - Implements PrimaryFlightDisplay
  - Handles flight data visualization
  - Manages flight instruments

### 3. Display Node System

#### Core Node Components
- **FMOFP/Interfaces/userInterface/displays/display_nodes/display_node_base.py**: Base node
  - Implements NodeMetadata for state tracking
  - Provides DisplayNode base class
  - Manages parent-child relationships
  - Handles subscriber notifications

#### Tree Management
- **FMOFP/Interfaces/userInterface/displays/display_nodes/display_tree_manager.py**: Tree manager
  - Implements FallbackMode for error handling
  - Manages complete display state tree
  - Handles radar branch initialization
  - Coordinates state updates across nodes
  - Key Features:
    * Dynamic radar enum loading
    * Branch-specific initialization
    * Mode-based visual updates
    * Data state management
    * State recovery mechanisms

#### Mode Management
- **FMOFP/Interfaces/userInterface/displays/display_nodes/mode_node.py**: Mode handling
  - Implements ModeNode for mode state management
  - Core Features:
    * Mode State Tracking:
      - Current and previous mode storage
      - Transition timestamp tracking
      - Mode history with timestamps (last 10 changes)
      - Time-in-mode calculations
    * Mode Validation:
      - Dynamic enum loading and validation
      - Mode value and name consistency checks
      - Fallback handling for invalid modes
      - Source system-based enum resolution
    * State Management:
      - Thread-safe state updates
      - Subscriber notifications
      - Error tracking and recovery
      - Complete state serialization
    * Mode Types:
      - STANDBY: Basic status display
      - SURVEILLANCE: Full radar operation
      - MAPPING: Terrain visualization
      - Custom modes per radar type
    * Error Handling:
      - Validation failure recovery
      - Fallback mode support
      - Error state tracking
      - Detailed error logging

#### Visual Management
- **FMOFP/Interfaces/userInterface/displays/display_nodes/visual_node.py**: Visual elements
  - Implements VisualNode for display elements
  - Manages visual states and properties
  - Controls element visibility:
    * Overlays (standby, surveillance, mapping)
    * Status indicators
    * Legends and scales
    * VIL data visualization
  - Handles opacity and rendering settings

### 4. Display Management

#### Manager Components
- **FMOFP/Interfaces/userInterface/managers/display_manager.py**: Display manager
  - Core Features:
    * Display Lifecycle:
      - Singleton instance management
      - Display initialization and setup
      - Display state coordination
      - Display updates and refresh
    * Mode Management:
      - Display mode setting
      - Mode transition handling
      - Mode state validation
      - Mode-specific display updates
    * Display Control:
      - Show/hide display management
      - Display update scheduling
      - Display state synchronization
      - Thread-safe operations
    * System Integration:
      - Start/stop functionality
      - Health monitoring
      - Resource management
      - Error handling

### 5. Radar Display System

#### Core Components
- **FMOFP/Interfaces/userInterface/displays/radar/base_radar_display.py**: Base radar
  - Implements BaseRadarDisplay
  - Provides common functionality
  - Handles coordinate transforms

- **FMOFP/Interfaces/userInterface/displays/radar/mode_handlers.py**: Mode handling
  - Implements radar mode handlers
  - Manages mode-specific behavior
  - Coordinates mode updates

- **FMOFP/Interfaces/userInterface/displays/radar/radar_display_factory.py**: Display factory
  - Creates radar displays
  - Manages display configuration
  - Handles initialization

#### Radar Type Implementations
- **FMOFP/Interfaces/userInterface/displays/radar/aewc_radar_display.py**: AEWC radar
  - Implements AEWCRadarDisplay
  - Handles surveillance modes
  - Manages track data

- **FMOFP/Interfaces/userInterface/displays/radar/sar_radar_display.py**: SAR radar
  - Implements SARRadarDisplay
  - Handles mapping modes
  - Processes imagery

- **FMOFP/Interfaces/userInterface/displays/radar/targeting_radar_display.py**: Targeting
  - Implements TargetingRadarDisplay
  - Handles target tracking
  - Manages targeting modes

- **FMOFP/Interfaces/userInterface/displays/radar/tfr_radar_display.py**: TFR radar
  - Implements TFRRadarDisplay
  - Handles terrain following
  - Processes terrain data

- **FMOFP/Interfaces/userInterface/displays/radar/weather_radar_display.py**: Weather radar
  - Implements WeatherRadarDisplay
  - Handles weather visualization
  - Manages weather data

- **FMOFP/Interfaces/userInterface/displays/radar/weather_radar_widget.py**: Weather widget
  - Implements Qt widget adapter
  - Handles paint events
  - Manages window properties

#### Mode Handlers
- **FMOFP/Interfaces/userInterface/displays/radar/tfr_mode_handler.py**: TFR modes
  - Implements TFRModeHandler
  - Manages terrain modes
  - Handles mode transitions

### 5. Radar Data Handling

#### Base Components
- **FMOFP/Interfaces/userInterface/displays/radar/radar_data_handler/base_radar_data_handler.py**: Base handler
  - Implements RadarEvent
  - Provides BaseRadarDataHandler
  - Manages data processing

- **FMOFP/Interfaces/userInterface/displays/radar/radar_data_handler/base_radar_display.py**: Display base
  - Extends BaseRadarDisplay
  - Handles display updates
  - Manages state caching

- **FMOFP/Interfaces/userInterface/displays/radar/radar_data_handler/weather_radar_display.py**: Weather data
  - Implements weather data handling
  - Processes weather information
  - Updates display state

### 6. Event System

#### Event Management
- **FMOFP/Interfaces/userInterface/displays/radar/radar_event_system/radar_event_manager.py**: Event manager
  - Implements RadarEventManager
  - Handles event routing
  - Manages subscriptions

- **FMOFP/Interfaces/userInterface/displays/radar/radar_event_system/radar_topic_registry.py**: Topic registry
  - Defines radar topics
  - Validates topic structure
  - Manages descriptions

- **FMOFP/Interfaces/userInterface/displays/radar/radar_event_system/display_cache.py**: Display cache
  - Implements DisplayCache
  - Manages state caching
  - Handles updates

### 7. Display Hierarchy
```
DisplayTreeManager
├── WeatherRadar
│   ├── ModeNode
│   ├── VisualNode
│   └── DataNode
│       ├── Precipitation
│       ├── VIL
│       └── Cells
├── TargetingRadar
│   ├── ModeNode
│   ├── VisualNode
│   └── DataNode
│       ├── Tracks
│       └── Targets
├── SARRadar
│   ├── ModeNode
│   ├── VisualNode
│   └── DataNode
│       ├── Imagery
│       └── Maps
├── TFRRadar
│   ├── ModeNode
│   ├── VisualNode
│   └── DataNode
│       ├── Terrain
│       └── Obstacles
└── AEWCRadar
    ├── ModeNode
    ├── VisualNode
    └── DataNode
        ├── Surveillance
        └── Tracks
```

### 8. Messaging System

#### Core Components
- **FMOFP/Interfaces/userInterface/messaging/displayMessenger.py**: Display messenger
  - Implements DisplayMessenger singleton
  - Handles 1553B message routing and processing
  - Manages display addressing and subaddressing
  - Coordinates with RT_Listener for message reception

- **FMOFP/Interfaces/userInterface/messaging/display_1553b_helpers.py**: 1553B helpers
  - Implements Display1553BHelpers for message handling
  - Provides message validation and parsing
  - Handles command word construction
  - Manages status word generation

- **FMOFP/Interfaces/userInterface/messaging/display_command_map.py**: Command mapping
  - Maps display commands to handlers
  - Validates command names and formats
  - Manages command registry and lookup
  - Handles command word extraction

- **FMOFP/Interfaces/userInterface/messaging/display_message_handler.py**: Message handler
  - Implements PendingDisplayRequest tracking
  - Handles message processing and routing
  - Manages request states and retries
  - Coordinates with async handler

- **FMOFP/Interfaces/userInterface/messaging/display_message_router.py**: Message router
  - Implements DisplayMessageRouter
  - Routes messages between components
  - Manages message flow and delivery
  - Handles message type resolution

- **FMOFP/Interfaces/userInterface/messaging/message_generator.py**: Message generator
  - Generates formatted display messages
  - Creates command and response messages
  - Handles message template loading
  - Validates message structures

#### Message Templates
- **FMOFP/Interfaces/userInterface/messaging/message_templates/display_acknowledgment.xml**: Acknowledgment template
  - Defines acknowledgment message format
  - Specifies required and optional fields
  - Configures acknowledgment types
  - Maps to 1553B message structure

- **FMOFP/Interfaces/userInterface/messaging/message_templates/display_command.xml**: Command template
  - Defines command message format
  - Specifies command parameters
  - Configures command types
  - Maps to 1553B command words

### 9. Message Flow

#### 1. Command Processing Flow (1553B)
```
1. Command Generation:
   - RadarMessageHandler creates mode change request
   - Generates command word (0100100001000101)  <- May vary based on subsystem address, t/r bit, data words
   - Constructs data word (0000000000000010)    <- will very based on data sent
   - Assigns unique request ID
   - Stores pending request

2. BC to RT Transmission:
   - BC_sender formats 1553B frames:
     * Command frame: 10001001000010001011    
     * Data frame: 00100000000000000101       
   - Transmits to RT (address 01001)
   - Verifies transmission success

3. RT Processing:
   - RT_Listener validates sync bits and frames
   - Decodes command word components:
     * RT address: 9
     * T/R bit: 0
     * Subaddress: 2
     * Word count: 5
   - Processes mode change (SURVEILLANCE)
   - Stores mode change in database
   - Generates status word (10001001000000000011)

4. Status Word Response:
   - RT sends status word to BC
   - BC_Listener verifies acknowledgment
   - Updates request status
   - Stores mode change confirmation
```

#### 2. Display System Flow
```
1. Message Reception (DisplayMessenger):
   - Receives MIL-STD-1553B message from RT_Listener
   - Validates message format and integrity
   - Extracts display-relevant information:
     * RT address and subaddress
     * Message type and data
     * Command parameters

2. Message Routing (DisplayMessageRouter):
   - Receives messages from DisplayMessenger
   - Extracts display information:
     * Display ID and name from subaddress
     * Display type validation
     * Message format verification
   - Routes to display messenger handler:
     * Validates messenger connection
     * Passes message with display type
     * Handles routing errors
   - Coordinates with display manager:
     * Maintains manager reference
     * Ensures proper message flow
     * Manages display state updates

2.5 ?GAP?
   - display message handler isn't included here?
   - if it coordinates with display manager, how does that get to the displaytreemanager?  is this a gap?
   - please complete a function trace to verify this and any further gaps

3. Display Tree Update (DisplayTreeManager):
   - Receives validated mode change request
   - Updates radar branch state:
     * Mode node: SURVEILLANCE
     * Visual node: overlay configuration
     * Data node: weather data settings
   - Manages node relationships and dependencies
   - Coordinates state propagation

3. Visual Processing (VisualNode):
   - Configures display elements based on mode:
     * Sets overlay to 'surveillance'
     * Enables scan line display
     * Shows intensity scale
     * Configures VIL visualization
   - Updates opacity and rendering settings
   - Manages element visibility states

4. Widget Rendering (WeatherRadarWidget):
   - Receives state updates from tree
   - Processes visual configuration
   - Handles Qt paint events
   - Renders final display output:
     * Weather data visualization
     * Mode-specific overlays
     * Status indicators
     * Scales and legends
```

#### 3. Data Flow
```
1. Mode Changes:
   - Command initiates mode change
   - Mode state updated in tree
   - Visual elements reconfigured
   - Display refreshed

2. Weather Data:
   - VIL data processed
   - Precipitation data updated
   - Cell data managed
   - Display elements redrawn

3. Status Updates:
   - System status monitored
   - Error states handled
   - Display state validated
   - Visual feedback provided
```

## State Management

### 1. Mode State
- Tracks current and previous modes
- Manages mode transitions
- Maintains mode history
- Validates mode changes

### 2. Visual State
- Controls overlay visibility
- Manages display elements
- Handles opacity settings
- Controls scale visibility

### 3. Data State
- Stores VIL data
- Manages precipitation data
- Tracks cell information
- Handles data updates

## Testing Requirements

1. Verify message flow through each component
2. Test mode change propagation
3. Validate display updates
4. Check data processing
5. Test error handling
6. Verify state consistency






INSTRUCTIONS:
Verify agaisnt project_structure.txt that you've included every file from /interfaces
Next, go back through the files and compare what you've written about them, ensure you've properly Identified their purpose, inclusions, and any other relevant information
Then write all that into the document (may do in steps if needed)
