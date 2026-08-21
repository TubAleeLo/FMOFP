# 10. Flight Management Integration

**Navigation:** [← Holographic Display System](09_Holographic_Display_System.md) | [Communication Messaging →](11_Communication_Messaging.md)

---

## 10.1 FMS Integration Overview

### System Status: ✅ **OPERATIONAL**

The Flight Management System (FMS) serves as the central integration hub for all aircraft systems, providing real-time flight data management, navigation control, and tactical systems coordination. The FMS integrates with the Flight Control System (FCS) to deliver comprehensive flight management capabilities for military operations.

**Key Integration Points:**
- **Flight Control System (FCS)** - Real-time attitude and control surface management
- **Navigation Systems** - GPS, INS, and TACAN integration
- **Display Systems** - Primary Flight Display and Multi-Function Display data feeds
- **Mission Planning** - Waypoint management and tactical coordination
- **Radar Systems** - Tactical data integration and threat assessment
- **Cross-Radar Data Fusion** - `RadarDataFusion` correlates Targeting and AEWC tracks across a 500 m gate; fused contacts feed the TSD display (cross-radar data fusion layer active)

### Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                Flight Management System (FMS)                 │
├───────────────────────────────────────────────────────────────┤
│  • Real-time Flight Data (20Hz)                               │
│  • Mode Management (NORMAL/COMBAT/STEALTH/TRAINING/EMERGENCY) │
│  • System Integration Hub                                     │
└─────────────────┬─────────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌────▼────┐    ┌───▼────┐
│  FCS  │    │   NAV   │    │ MISSION│
│ ✅ OP │    │ ✅ OP  │    │⚠️ BASIC│
└───────┘    └─────────┘    └────────┘
```

### System Specifications

| Parameter | Value | Status |
|-----------|-------|--------|
| **Update Rate** | 20Hz (50ms intervals) | ✅ Operational |
| **FCS Integration** | 50Hz (20ms intervals) | ✅ Operational |
| **Data Precision** | 16-bit integer encoding | ✅ Operational |
| **Mode Switching** | Real-time with completion tracking | ✅ Operational |
| **Message Protocol** | MIL-STD-1553B compliant | ✅ Operational |

---

## 10.2 Real-Time Flight Data Integration

### System Status: ✅ **OPERATIONAL**

The FMS provides comprehensive real-time flight data integration with verified 20Hz update rates and complete data synchronization across all aircraft systems.

### Flight Data Categories

#### 10.2.1 Attitude Data ✅ **OPERATIONAL**

**Source:** Flight Control System (FCS) with Attitude Calculator
**Update Rate:** 50Hz (20ms intervals)
**Precision:** 0.01 degree resolution

```python
# Verified Implementation Data Structure
attitude = {
    'roll': 0,         # Roll angle in degrees (-180 to +180)
    'pitch': 0,        # Pitch angle in degrees (-90 to +90)
    'yaw': 0,          # Yaw angle in degrees (0 to 360)
    'roll_rate': 0,    # Roll rate in degrees/second
    'pitch_rate': 0,   # Pitch rate in degrees/second
    'yaw_rate': 0,     # Yaw rate in degrees/second
}
```

**Integration Verification:**
- ✅ Real-time updates from FCS attitude calculator
- ✅ Envelope protection with mode-specific limits
- ✅ Automatic fallback to simulation if FCS unavailable
- ✅ Data transmission to Primary Flight Display confirmed

#### 10.2.2 Velocity Data ✅ **OPERATIONAL**

**Source:** FMS calculations with sensor fusion
**Update Rate:** 20Hz (50ms intervals)

```python
# Verified Implementation Data Structure
velocity = {
    'airspeed': 0,        # Aircraft airspeed in knots
    'ground_speed': 0,    # Ground speed in knots
    'vertical_speed': 0,  # Vertical speed in feet/minute
    'mach': 0,            # Mach number (altitude compensated)
}
```

**Calculation Methods:**
- **Airspeed:** Base 450 knots with realistic variations
- **Mach Number:** Altitude-compensated calculation (661.4788 * 0.98 factor)
- **Vertical Speed:** Sinusoidal simulation with ±100 fpm range
- **Ground Speed:** Derived from airspeed with wind compensation

#### 10.2.3 Navigation Data ✅ **OPERATIONAL**

**Source:** GPS System with INS backup
**Update Rate:** 20Hz (50ms intervals)
**Status:** GPS operational but with threading issues

```python
# Verified Implementation Data Structure
navigation = {
    'latitude': 0,        # Current latitude (decimal degrees)
    'longitude': 0,       # Current longitude (decimal degrees)
    'altitude': 0,        # Current altitude in feet MSL
    'heading': 0,         # Current heading in degrees
    'track': 0,           # Ground track in degrees
    'waypoints': [],      # List of waypoints
    'active_waypoint': 0, # Index of active waypoint
}
```

**Integration Status:**
- ✅ Basic position tracking operational
- ✅ GPS triangulation operational (WLS solver, Bowring's iterative WGS-84 conversion)
- ✅ Waypoint management functional
- ✅ Kalman filter fusion operational (NavDataFusion — predict/update at 20 Hz / 1 Hz GPS)

#### 10.2.4 Tactical Data ✅ **OPERATIONAL**

**Source:** FMS calculations with FCS integration
**Update Rate:** 20Hz (50ms intervals)

```python
# Verified Implementation Data Structure
tactical = {
    'g_force': 0,         # Current G-force (1.0 = normal gravity)
    'aoa': 0,             # Angle of attack in degrees
    'sideslip': 0,        # Sideslip angle in degrees
    'energy_state': 0,    # Aircraft energy state (0-100 scale)
    'mode': 'NORMAL',     # Flight mode
}
```

**Calculation Verification:**
- **G-Force:** Real-time calculation based on attitude rates (1.0-9.0g range)
- **AOA:** Derived from pitch angle and pitch rate
- **Energy State:** Kinetic + potential energy normalized to 0-100 scale
- **Mode Integration:** Synchronized with FCS mode changes

### Data Transmission Protocol

#### MIL-STD-1553B Encoding ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Data word encoding (16-bit integers)
data_words = [
    0x1000,                                    # FMS data identifier
    int(attitude['roll'] * 100) & 0xFFFF,     # Roll (scaled)
    int(attitude['pitch'] * 100) & 0xFFFF,    # Pitch (scaled)
    int(attitude['yaw'] * 100) & 0xFFFF,      # Yaw (scaled)
    int(velocity['airspeed']) & 0xFFFF,       # Airspeed
    int(velocity['vertical_speed']) & 0xFFFF, # Vertical speed
    int(navigation['altitude']) & 0xFFFF,     # Altitude
    int(navigation['heading'] * 10) & 0xFFFF, # Heading (scaled)
    int(tactical['g_force'] * 100) & 0xFFFF,  # G-force (scaled)
    int(tactical['aoa'] * 100) & 0xFFFF,      # AOA (scaled)
    int(tactical['energy_state']) & 0xFFFF,   # Energy state
    mode_int                                   # Mode as integer
]
```

**Protocol Compliance:**
- ✅ 16-bit data word format
- ✅ Header identification (0x1000 for FMS data)
- ✅ Scaling factors for precision preservation
- ✅ Mode encoding with integer mapping
- ✅ Maximum 32 data words per message (MIL-STD-1553B limit)
- ✅ Automatic data serialization and deserialization

#### Message Processing Architecture ✅ **OPERATIONAL**

**Verified Components:**
- **FMS Message Processor:** Dedicated message routing and processing
- **Completion Message Handler:** MIL-STD-1553B compliant completion notifications
- **FMS Messenger:** RT-based communication with queue management
- **Message Type Detection:** Centralized message type constants and detection

**Message Flow:**
```
RT_Listener → MessageQueueManager → FMSMessenger → FMSMessageProcessor → FMS/FCS
     ↓
Completion Messages ← FMSCompletionMessageHandler ← RT_Sender
```

---

## 10.3 Navigation and Waypoint Management

### System Status: ✅ **OPERATIONAL**

GPS threading is fixed. The GPS update loop runs on a daemon thread started by FMS.start(). NavDataFusion blends GPS fixes into a Kalman-filtered position estimate updated at the FMS rate.

### 10.3.1 GPS Integration ✅ **OPERATIONAL**

**Implementation Status:**
- ✅ 12-satellite constellation (3 orbital planes, 55° inclination)
- ✅ Weighted least-squares position fix with elevation-angle weighting
- ✅ Bowring's iterative WGS-84 ↔ ECEF conversion
- ✅ Daemon thread started correctly by FMS.start()

**Verified Capabilities:**
```python
# GPS System Implementation
class GPSSystem:
    def triangulate_position(self) -> Tuple[float, float, float]:
        # Requires minimum 4 satellites for 3D position
        # Implements least squares algorithm
        # Fallback to last known position if insufficient satellites
```

**Current Constraints:**
- Simulated satellite data only (no real GPS hardware)
- Constellation geometry is fixed (not propagated over time)

### 10.3.2 Waypoint Management ✅ **OPERATIONAL**

**Implementation Status:** Fully functional waypoint system

**Verified Features:**
```python
# Waypoint Management Implementation
def add_waypoint(self, name, latitude, longitude, altitude, waypoint_type="NORMAL"):
    waypoint = {
        'id': waypoint_id,
        'name': name,
        'latitude': latitude,
        'longitude': longitude,
        'altitude': altitude,
        'type': waypoint_type
    }
    self.navigation['waypoints'].append(waypoint)
```

**Operational Capabilities:**
- ✅ Dynamic waypoint addition and removal
- ✅ Active waypoint tracking
- ✅ Distance and bearing calculations
- ✅ Integration with mission planning system

### 10.3.3 Navigation Data Fusion ✅ **OPERATIONAL**

**Available Systems:**
- **GPS:** Fully operational with WLS position fix
- **NavDataFusion:** Scalar Kalman filter blending GPS and FMS dead-reckoning

**Data Fusion Status:**
- ✅ GPS measurement update at ~1 Hz
- ✅ Dead-reckoning prediction at FMS update rate (~20 Hz)
- ✅ Kalman gain K = P/(P+R) computed per axis (lat, lon, alt)

---

## 10.4 Flight Control System Integration

### System Status: ✅ **OPERATIONAL**

Complete integration between FMS and Flight Control System with real-time attitude control and envelope protection.

### 10.4.1 FCS Architecture ✅ **OPERATIONAL**

**Verified Implementation:**
```python
class FlightControlSystem:
    def __init__(self, name: str = "FCS", fms_control=None, fms_messenger=None):
        self.mode = FlightControlModes.NORMAL
        self.running = False
        self._update_interval = 0.02  # 50Hz update rate
        self.attitude_calculator = get_attitude_calculator()
```

**Integration Points:**
- ✅ Direct FMS reference for data sharing
- ✅ Shared messenger for MIL-STD-1553B communication
- ✅ Real-time attitude data synchronization
- ✅ Mode synchronization between FMS and FCS

### 10.4.2 Flight Control Modes ✅ **OPERATIONAL**

**Available Modes:**
```python
class FlightControlModes:
    NORMAL = "NORMAL"         # Standard flight control
    COMBAT = "COMBAT"         # Enhanced maneuverability
    PRECISION = "PRECISION"   # Precise control for landing/refueling
    AUTOPILOT = "AUTOPILOT"   # Automated flight control
    TERRAIN = "TERRAIN"       # Terrain following mode
    EMERGENCY = "EMERGENCY"   # Emergency control mode
```

**Mode-Specific Parameters:**
| Mode | Update Rate | Max Bank | Max Pitch | Max G-Force |
|------|-------------|----------|-----------|-------------|
| NORMAL | 50Hz | 30° | 20° | 2.5g |
| COMBAT | 100Hz | 80° | 60° | 9.0g |
| PRECISION | 50Hz | 45° | 30° | 5.0g |
| EMERGENCY | 50Hz | 90° | 85° | 9.5g |

### 10.4.3 Control Surface Management ✅ **OPERATIONAL**

**Verified Implementation:**
```python
# Control inputs with normalized values
control_inputs = {
    'aileron': 0,      # Roll control: -1.0 to 1.0
    'elevator': 0,     # Pitch control: -1.0 to 1.0
    'rudder': 0,       # Yaw control: -1.0 to 1.0
    'throttle': 0.5,   # Engine power: 0.0 to 1.0
}
```

**Control Response:**
- ✅ Real-time control surface position updates
- ✅ Attitude response simulation with proper dynamics
- ✅ Control input validation and limiting
- ✅ Emergency override capabilities

### 10.4.4 Envelope Protection ✅ **OPERATIONAL**

**FMS Control Module Integration:**
```python
# Flight envelope limits by mode
flight_profiles = {
    "NORMAL": {
        "max_bank_angle": 30,      # degrees
        "max_pitch_angle": 20,     # degrees
        "max_g_force": 2.5,        # g's
        "max_aoa": 15,             # degrees
        "turn_rate_limit": 3,      # degrees/second
    },
    "COMBAT": {
        "max_bank_angle": 80,      # degrees
        "max_pitch_angle": 60,     # degrees
        "max_g_force": 9.0,        # g's
        "max_aoa": 25,             # degrees
        "turn_rate_limit": 20,     # degrees/second
    }
}
```

**Protection Features:**
- ✅ Real-time envelope monitoring
- ✅ Automatic limit enforcement
- ✅ Warning generation for envelope violations
- ✅ Mode-specific limit adjustment

---

## 10.5 Tactical Systems Management

### System Status: ✅ **OPERATIONAL**

Comprehensive tactical systems integration with mode-dependent configuration and real-time status management.

### 10.5.1 Tactical Mode Management ✅ **OPERATIONAL**

**Mode-Dependent System Configuration:**
```python
def _update_tactical_systems(self, mode):
    if mode == "COMBAT":
        self.tactical_systems["countermeasures"] = "READY"
        self.tactical_systems["targeting"] = "ACTIVE"
        self.tactical_systems["weapons"] = "ARMED"
        self.tactical_systems["stealth_mode"] = "OFF"
    elif mode == "STEALTH":
        self.tactical_systems["countermeasures"] = "PASSIVE"
        self.tactical_systems["targeting"] = "PASSIVE"
        self.tactical_systems["weapons"] = "SAFE"
        self.tactical_systems["stealth_mode"] = "ON"
```

**Tactical System States:**
| Mode | Countermeasures | Targeting | Weapons | Stealth |
|------|----------------|-----------|---------|---------|
| NORMAL | STANDBY | STANDBY | SAFE | OFF |
| COMBAT | READY | ACTIVE | ARMED | OFF |
| STEALTH | PASSIVE | PASSIVE | SAFE | ON |
| EMERGENCY | ACTIVE | READY | READY | OFF |

### 10.5.2 Energy Maneuverability ✅ **OPERATIONAL**

**Real-Time Calculations:**
```python
def calculate_energy_maneuverability(self):
    # Specific excess power calculation
    specific_excess_power = speed_ms * (thrust_available - drag) / weight

    # Turn performance calculations
    max_sustained_turn_rate = math.degrees(g * math.sqrt(thrust_weight_ratio**2 - 1) / speed_ms)
    max_instantaneous_turn_rate = math.degrees(g * math.sqrt(g_force**2 - 1) / speed_ms)

    # Climb performance
    max_climb_rate_fpm = specific_excess_power * 196.85  # m/s to fpm
```

**Tactical Metrics:**
- ✅ Specific excess power calculation
- ✅ Sustained turn rate computation
- ✅ Instantaneous turn rate computation
- ✅ Maximum climb rate calculation
- ✅ Energy advantage assessment

### 10.5.3 Predefined Maneuvers ✅ **OPERATIONAL**

**Available Maneuvers:**
```python
# Verified tactical maneuvers
maneuvers = {
    "BREAK_RIGHT": "Hard right turn with max performance",
    "BREAK_LEFT": "Hard left turn with max performance",
    "DEFENSIVE_SPLIT_S": "Roll inverted, pull down into opposite direction",
    "MAXIMUM_CLIMB": "Maximum performance climb",
    "DIVE": "Rapid descent with configurable angle"
}
```

**Maneuver Execution:**
- ✅ Real-time attitude command generation
- ✅ Envelope-protected maneuver execution
- ✅ Mode-appropriate performance limits
- ⚠️ Advanced maneuvers (barrel roll) not implemented

---

## 10.6 Mission Planning Integration

### System Status: ✅ **OPERATIONAL**

The mission planning system is fully operational, providing end-to-end coverage from route management through targeting and order-of-battle tracking. All components are wired into `SystemManager` and connected to the MFD mission page.

### 10.6.1 Mission Planning System ✅ **OPERATIONAL**

**Architecture:**
```python
# MissionService → MissionControl → RouteManager + TargetingSystem + OrderOfBattle
from FMOFP.Systems.missionPlanning.missionService import get_mission_service
ms = get_mission_service()
data = ms.get_data()  # returns phase, route, targets, oob_summary
```

**Mission Phases:**
- PLANNING — Mission preparation and route planning
- INGRESS — Approach to target area
- OBJECTIVE — Target engagement phase
- EGRESS — Departure from target area
- COMPLETE — Mission completion

**Operational Features:**
- ✅ Waypoint management and optimization (RouteManager)
- ✅ Target prioritization and tracking (TargetingSystem)
- ✅ Threat assessment and avoidance
- ✅ Route optimization algorithms
- ✅ Order-of-Battle tracking (FRIENDLY / ENEMY / NEUTRAL)
- ✅ MFD mission page with ROUTE / TARGETS / OOB sub-tabs
- ✅ SystemManager integration (started at Phase 3)

### 10.6.2 Target and Threat Management ✅ **OPERATIONAL**

**Target Management:**
```python
class Target:
    def __init__(self, id, type, position, priority):
        self.id       = id
        self.type     = type
        self.position = position   # (lat, lon, alt_ft)
        self.priority = priority
        self.status   = TargetStatus.DESIGNATED
```

**Status lifecycle:** DESIGNATED → ACQUIRED → ENGAGED → DESTROYED

**Integration Status:**
- ✅ Target status tracking and updates
- ✅ Threat proximity monitoring
- ✅ Risk factor calculations
- ✅ Database persistence for mission data
- ✅ MFD TARGETS tab with colour-coded status display

### 10.6.3 Route Optimization ✅ **OPERATIONAL**

**Current Algorithm:**
- Distance-based waypoint sorting
- Priority-based target insertion
- Threat avoidance adjustments (lateral offset on high-risk areas)
- Nav data: distance to next waypoint (nm), bearing, active index

**MFD Integration:**
The ROUTE tab on the MFD mission page shows the full waypoint list with the active waypoint highlighted (► marker), next-waypoint distance and bearing, and altitude for each entry. Clicking the ROUTE / TARGETS / OOB tab buttons switches sub-pages without leaving the mission page.

---

## 10.7 FMS Troubleshooting

### Common Integration Issues

#### 10.7.1 FMS-FCS Communication Issues

**Symptoms:**
- Attitude data not updating on displays
- Control inputs not responding
- Mode changes not synchronizing

**Troubleshooting Steps:**
1. **Check FCS Integration:**
   ```python
   # Verify FCS is properly initialized
   if self.flight_control_system:
       logger.info("FCS available and running")
   else:
       logger.error("FCS not available - check initialization")
   ```

2. **Verify Messenger Connection:**
   ```python
   # Check messenger status
   if self.messenger:
       logger.info("FMS messenger connected")
   else:
       logger.error("FMS messenger not set")
   ```

3. **Monitor Update Rates:**
   - FMS should update at 20Hz (50ms intervals)
   - FCS should update at 50Hz (20ms intervals)
   - Check for timing issues or thread blocking

#### 10.7.2 Navigation System Issues

**GPS Integration Problems:**
- **Threading Issues:** GPS system starts thread in main execution instead of system manager
- **Satellite Data:** Limited to simulated satellites, no real hardware integration
- **Position Accuracy:** Basic triangulation may have accuracy limitations

**Resolution:**
1. Move GPS thread initialization to system manager
2. Implement proper satellite data feeds
3. Add Kalman filtering for improved accuracy

#### 10.7.3 Mission Planning Issues

**Threading Problems:**
- Mission management system starts threads incorrectly
- Update loops may conflict with system manager

**Resolution:**
1. Integrate with system manager for proper thread management
2. Implement proper shutdown procedures
3. Add thread synchronization mechanisms

### Performance Monitoring

#### 10.7.4 System Health Checks

**FMS Health Monitoring:**
```python
def check_health(self):
    if not self.thread or not self.thread.is_alive():
        self.status['health'] = 'OFFLINE'
        return False
    if self.status['errors']:
        self.status['health'] = 'DEGRADED'
        return False
    self.status['health'] = 'NOMINAL'
    return True
```

**Key Health Indicators:**
- ✅ Thread status and responsiveness
- ✅ Error count and severity
- ✅ Update rate consistency
- ✅ Memory usage and performance

#### 10.7.5 Data Validation

**Flight Data Validation:**
```python
# Attitude validation
self.attitude['roll'] = (self.attitude['roll'] + 180) % 360 - 180
self.attitude['pitch'] = max(-90, min(90, self.attitude['pitch']))
self.attitude['yaw'] = self.attitude['yaw'] % 360

# G-force validation
self.attitude['g_force'] = max(0.1, min(9.0, self.attitude['g_force']))
```

**Validation Checks:**
- ✅ Attitude angle range validation
- ✅ G-force limit enforcement
- ✅ Velocity range checking
- ✅ Navigation coordinate validation

---

## 10.8 Configuration and Maintenance

### System Configuration

#### 10.8.1 FMS Configuration Parameters

**Update Rates:**
```python
self.update_rate = 0.05  # 20Hz FMS update rate
self._update_interval = 0.02  # 50Hz FCS update rate (combat: 0.01 = 100Hz)
```

**Mode Configuration:**
```python
available_modes = ["NORMAL", "COMBAT", "STEALTH", "TRAINING", "EMERGENCY"]
```

**Flight Profile Limits:**
- Configurable per-mode envelope limits
- Real-time limit enforcement
- Warning threshold configuration

#### 10.8.2 Integration Settings

**FCS Integration:**
```python
# Set reference to FMS in the FCS
self.flight_control_system.fms_control = self

# Pass messenger to FCS
self.flight_control_system.set_messenger(messenger)
```

**Display Integration:**
- Automatic data feeds to Primary Flight Display
- Real-time update synchronization
- Error handling and fallback procedures

### Maintenance Procedures

#### 10.8.3 Regular Maintenance

**Daily Checks:**
1. Verify FMS-FCS communication status
2. Check attitude data accuracy and update rates
3. Validate navigation system integration
4. Monitor system health indicators

**Weekly Maintenance:**
1. Review system logs for errors or warnings
2. Validate flight envelope protection settings
3. Check mission planning system integration
4. Update navigation database if required

**Monthly Maintenance:**
1. Comprehensive system integration testing
2. Performance optimization review
3. Configuration backup and validation
4. Software update integration testing

---

**Navigation:** [← Holographic Display System](09_Holographic_Display_System.md) | [Communication Messaging →](11_Communication_Messaging.md)

---

*File: 10_Flight_Management_Integration.md*
*Last Updated: December 2024*
*Next Review: As system implementations are updated*
