# 3. Targeting Radar System

**Navigation:** [← Weather Radar System](02_Weather_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [SAR Radar System →](04_SAR_Radar_System.md)

---

## 3.1 Targeting Radar Overview

### System Status ✅ **OPERATIONAL** (Radar Processing) | ✅ **OPERATIONAL** (Display Integration)

The Targeting Radar System provides comprehensive target detection, tracking, and engagement capabilities for tactical operations. The radar processing engine is fully operational, display integration is active via the radar-to-display bridge, and signature analysis with stealth detection is operational.

**Current Operational Status:**
- **Radar Processing:** ✅ **OPERATIONAL** - All target detection algorithms functional
- **Mode Switching:** ✅ **OPERATIONAL** - All operational modes available
- **Target Generation:** ✅ **OPERATIONAL** - Simulated target tracking and lock-on
- **Display Integration:** ✅ **OPERATIONAL** - Data routed via radar_to_display_bridge.push_targeting_data()
- **System Health:** ✅ **OPERATIONAL** - Health monitoring and status reporting

### Technical Specifications

**Operating Parameters:**
- **Maximum Range:** 100 kilometers (100,000 meters)
- **Target Capacity:** Up to 5 simultaneous targets
- **Update Rate:** Real-time target position updates
- **Lock Quality:** SNR-based lock assessment (0.0-1.0)
- **Target Generation Probability:** 10% per update cycle in SEARCH mode
- **RT Address:** 9 (Radar Systems)
- **Subaddress:** 4 (Targeting Radar)

**Target Detection Capabilities:**
- **Position Tracking:** 3D Cartesian coordinates (x, y, z)
- **Velocity Tracking:** 3D velocity vectors (vx, vy, vz)
- **Acceleration Tracking:** 3D acceleration vectors (ax, ay, az)
- **Target Classification:** Fighter, High-Altitude, Unknown
- **Signal Analysis:** SNR, RCS (Radar Cross Section)

### Key Capabilities

**Target Management:**
- Automatic target detection and acquisition
- Multi-target tracking with unique track IDs
- Target classification based on speed and altitude
- Lock-on capability for precision tracking
- Jamming detection and countermeasures

**Advanced Features:**
- ✅ **OPERATIONAL:** Real-time target position prediction
- ✅ **OPERATIONAL:** Signal-to-noise ratio analysis
- ✅ **OPERATIONAL:** Radar cross-section measurement
- ✅ **OPERATIONAL:** SignatureAnalyzer — Swerling RCS model classification with confidence scoring
- ✅ **OPERATIONAL:** StealthDetector — Bayesian P(stealth) tracking with non-coherent integration boost

## 3.2 Interface Elements Identification

### Targeting Radar Control Interface

[SCREENSHOT PLACEHOLDER: Targeting Radar control interface with numbered callouts]
**Figure 3.1:** Targeting Radar Control Interface
1. **System Selection Dropdown** - Choose Targeting Radar from available systems
2. **Current Mode Indicator** - Displays active operational mode (STANDBY, SEARCH, TRACK, LOCK)
3. **Available Modes List** - Shows all operational modes available for selection
4. **Mode Change Button** - Initiates mode transition to selected target mode
5. **Target List Display** - Shows currently tracked targets with Track IDs
6. **Lock Status Indicator** - Displays current lock status and quality
7. **System Status Display** - Real-time radar system health and processing status
8. **Communication Status** - 1553B message flow status to/from radar system

### Mode Change Procedure Visualization

[SCREENSHOT PLACEHOLDER: Before mode change - STANDBY mode]
**Figure 3.2:** Before Mode Change - STANDBY Mode
1. **Current Mode: STANDBY** - System powered but not scanning
2. **Target List: Empty** - No targets in memory
3. **System Ready Indicator** - Green status showing system ready for mode change
4. **Available Modes** - SEARCH, TRACK, LOCK modes available
5. **Communication Active** - 1553B connection established and healthy

[SCREENSHOT PLACEHOLDER: During mode change to SEARCH]
**Figure 3.3:** During Mode Change - Transition to SEARCH
1. **Mode Change Status** - "Changing to SEARCH" message displayed
2. **Target List Clearing** - Any existing targets being cleared
3. **System Processing** - Radar system reconfiguring for search mode
4. **Communication Activity** - 1553B messages being exchanged
5. **Status Updates** - Real-time log messages showing transition steps

[SCREENSHOT PLACEHOLDER: After mode change - SEARCH mode active with targets]
**Figure 3.4:** After Mode Change - SEARCH Mode with Target Detection
1. **New Mode: SEARCH** - Mode indicator updated to show active mode
2. **Target Detection Active** - System actively searching for targets
3. **Target List Populated** - Detected targets shown with Track IDs
4. **Target Information** - Position, velocity, classification displayed
5. **System Health** - All indicators showing normal operation

### Step-by-Step Mode Change Procedure

**Procedure: Changing Targeting Radar to SEARCH Mode**

**Step 1: Access Targeting Radar Controls**
1. Open the radar management system interface
2. Locate the Targeting Radar section [See Figure 3.1, Item 1]
3. Verify current mode shows "STANDBY" [See Figure 3.2, Item 1]
4. Confirm system status indicators are green [See Figure 3.2, Item 3]

**Step 2: Initiate Mode Change to SEARCH**
1. Click on the mode selection dropdown [See Figure 3.1, Item 3]
2. Select "SEARCH" (Mode 40) from the available modes list
3. Click the "Change Mode" button [See Figure 3.1, Item 4]
4. Monitor the status display for transition confirmation [See Figure 3.3, Item 1]

**Step 3: Monitor Mode Transition**
1. Watch for "Mode change in progress" message [See Figure 3.3, Item 1]
2. Observe target list clearing [See Figure 3.3, Item 2]
3. Monitor log output for detailed transition steps
4. Verify communication activity remains healthy [See Figure 3.3, Item 4]

**Step 4: Verify SEARCH Mode Operation**
1. Confirm mode indicator shows "SEARCH" [See Figure 3.4, Item 1]
2. Monitor target detection activity [See Figure 3.4, Item 2]
3. Watch for targets appearing in target list [See Figure 3.4, Item 3]
4. Verify target information is being generated [See Figure 3.4, Item 4]

**Step 5: Monitor Target Detection**
1. Observe automatic target generation (10% probability per update)
2. Check target classifications (FIGHTER, HIGH_ALT, UNKNOWN)
3. Monitor target positions and velocities
4. Fused tracks available on TSD via cross-radar data fusion layer

### Target Lock Procedure Visualization

[SCREENSHOT PLACEHOLDER: TRACK mode with target selected]
**Figure 3.5:** TRACK Mode - Target Selection for Lock
1. **Current Mode: TRACK** - Enhanced tracking mode active
2. **Target List** - Multiple targets available for selection
3. **Selected Target** - Target highlighted for lock attempt
4. **Target Details** - Position, velocity, SNR information displayed
5. **Lock Button** - Ready to initiate lock-on procedure

[SCREENSHOT PLACEHOLDER: Lock acquisition in progress]
**Figure 3.6:** Lock Acquisition in Progress
1. **Lock Status** - "Acquiring lock on Track ID X" message
2. **Signal Quality** - SNR and lock quality indicators
3. **Target Tracking** - Enhanced tracking algorithms active
4. **Lock Quality Meter** - Real-time lock quality assessment
5. **System Processing** - Lock algorithms running

[SCREENSHOT PLACEHOLDER: Successful target lock]
**Figure 3.7:** Successful Target Lock - LOCK Mode
1. **Mode: LOCK** - System in precision lock mode
2. **Locked Target** - Target ID and lock quality displayed
3. **Lock Quality: High** - Strong lock with good SNR
4. **Target Prediction** - Enhanced position prediction active
5. **Engagement Ready** - System ready for engagement operations

### Step-by-Step Target Lock Procedure

**Procedure: Locking onto a Target**

**Step 1: Ensure Targets are Available**
1. Verify radar is in SEARCH mode with detected targets
2. Check target list for available targets [See Figure 3.4, Item 3]
3. Note target Track IDs and signal quality
4. Select target with highest SNR for best lock probability

**Step 2: Switch to TRACK Mode**
1. Change mode from SEARCH to TRACK (Mode 41)
2. Verify mode change completion [See Figure 3.5, Item 1]
3. Confirm targets remain in tracking list [See Figure 3.5, Item 2]
4. Select target for lock attempt [See Figure 3.5, Item 3]

**Step 3: Initiate Lock Acquisition**
1. Select target from target list [See Figure 3.5, Item 3]
2. Click "Lock" button or initiate lock command [See Figure 3.5, Item 5]
3. Monitor lock acquisition progress [See Figure 3.6, Item 1]
4. Watch signal quality indicators [See Figure 3.6, Item 2]

**Step 4: Monitor Lock Quality**
1. Observe lock quality meter [See Figure 3.6, Item 4]
2. Verify SNR remains above threshold (>15 dB recommended)
3. Check for jamming detection alerts
4. Monitor lock stability over time

**Step 5: Verify Lock Success**
1. Confirm mode shows "LOCK" [See Figure 3.7, Item 1]
2. Check locked target information [See Figure 3.7, Item 2]
3. Verify high lock quality [See Figure 3.7, Item 3]
4. Monitor enhanced target prediction [See Figure 3.7, Item 4]

### Targeting Radar Data Flow Visualization

[DIAGRAM PLACEHOLDER: Targeting radar data processing flow]
**Figure 3.8:** Targeting Radar Data Processing Flow
1. **Mode Change Request** - User initiates mode change via interface
2. **Target Search** - Radar begins scanning for targets (SEARCH mode)
3. **Target Detection** - Automatic target generation and classification
4. **Target Tracking** - Position, velocity, acceleration calculations
5. **Lock Acquisition** - Enhanced tracking for selected target (LOCK mode)
6. **Data Object Creation** - Target data formatted for transmission
7. **1553B Message Preparation** - Data packaged according to protocol
8. **Display Integration** - Data routing to displays (under development)

## 3.3 Operational Modes and Capabilities

### Universal Base Modes ✅ **OPERATIONAL**

**STANDBY (Mode 0)**
- System powered but not actively scanning
- No target detection or tracking
- Minimal power consumption
- Ready for rapid mode transition
- All targets cleared from memory

**NORMAL (Mode 1)**
- Standard operational mode
- Basic target detection capabilities
- Balanced performance and power consumption
- Default mode for routine operations

**DEGRADED (Mode 2)**
- Reduced capability operation
- Limited range and target capacity
- Used when system constraints exist
- Maintains essential targeting functions

**TEST (Mode 3)**
- Built-in test mode
- System self-diagnostics
- Target simulation verification
- Performance validation

**MAINTENANCE (Mode 4)**
- Maintenance and calibration mode
- System configuration access
- Diagnostic data collection
- Service mode operations

### Targeting-Specific Modes ✅ **OPERATIONAL**

**TARGET_SEARCH / SEARCH (Mode 40)** ✅ **OPERATIONAL**
- Active target search and acquisition
- Automatic target detection within range
- Multiple target tracking capability
- Continuous volume scanning
- **Aliases:** Both TARGET_SEARCH and SEARCH refer to mode 40
- **Current Status:** ✅ Fully operational — tracks routed to display via bridge

```
Procedure: Switching to Search Mode
1. Access radar control interface
2. Select Targeting Radar system
3. Choose TARGET_SEARCH or SEARCH mode (Mode 40)
4. Monitor target acquisition in logs
5. Verify target detection in system status
```

**TARGET_TRACK / TRACK (Mode 41)** ✅ **OPERATIONAL**
- Dedicated target tracking mode
- Enhanced tracking accuracy
- Target prediction algorithms
- Lock-on preparation
- **Aliases:** Both TARGET_TRACK and TRACK refer to mode 41
- **Current Status:** ✅ Fully operational — tracks routed to display via bridge

**LOCK (Mode 42)** ✅ **OPERATIONAL**
- Precision target lock-on mode
- High-accuracy tracking
- Engagement-ready status
- Jamming resistance
- **Current Status:** ✅ Fully operational — locked target routed to display via bridge

**TERRAIN_AVOIDANCE (Mode 43)** ⚠️ **IN DEVELOPMENT**
- Ground clutter rejection
- Low-altitude target tracking
- Terrain masking compensation
- Enhanced surface target detection

## 3.4 Target Search and Acquisition

### Overview ✅ **OPERATIONAL** (Processing) | ✅ **OPERATIONAL** (Display — via radar-to-display bridge)

The target search and acquisition system automatically detects and classifies targets within the radar's coverage area, providing real-time tracking information for tactical decision-making.

**Search Parameters:**
- **Search Volume:** 360° azimuth, ±30° elevation
- **Range Coverage:** 1-100 kilometers
- **Detection Threshold:** Configurable SNR threshold
- **Target Capacity:** Maximum 5 simultaneous targets
- **Update Rate:** Real-time position updates

### Target Detection Algorithm ✅ **OPERATIONAL**

**Detection Process:**
1. **Volume Scanning:**
   - Continuous 360° azimuth coverage
   - Elevation scanning from -30° to +30°
   - Range gates from 1 km to maximum range
   - Doppler processing for moving targets

2. **Signal Processing:**
   - Clutter rejection algorithms
   - Moving target indication (MTI)
   - Constant false alarm rate (CFAR) processing
   - Signal-to-noise ratio calculation

3. **Target Validation:**
   - Minimum detection criteria
   - Track correlation algorithms
   - False alarm rejection
   - Target confirmation over multiple scans

### Target Generation and Simulation ✅ **OPERATIONAL**

**Simulated Target Characteristics:**
```python
Target Parameters:
- Position: Random within 1-100 km range
- Velocity: 100-300 m/s (realistic aircraft speeds)
- Acceleration: 0-30 m/s² (maneuvering capability)
- RCS: 1-10 m² (radar cross-section)
- SNR: 10-30 dB (signal quality)
```

**Target Classification Logic:**
- **FIGHTER:** Velocity > 250 m/s
- **HIGH_ALT:** Altitude > 10,000 meters
- **UNKNOWN:** Default classification for unidentified targets

**Target Lifecycle Management:**
- Automatic target generation in SEARCH mode
- Target position updates based on velocity and acceleration
- Target removal when out of range
- Track ID assignment and management

### Search Mode Operations ✅ **OPERATIONAL**

**Search Pattern:**
- Continuous volume search
- 10% probability of new target detection per update
- Maximum 5 targets maintained simultaneously
- Automatic track initiation for valid detections

**Target Tracking:**
```
Target Update Process:
1. Calculate new position based on velocity
2. Update velocity based on acceleration
3. Recalculate range and signal strength
4. Update target classification if needed
5. Remove targets beyond maximum range
```

**Performance Metrics:**
- **Detection Range:** Up to 100 km for typical targets
- **Position Accuracy:** ±10 meters at 50 km range
- **Velocity Accuracy:** ±5 m/s
- **Update Rate:** 10 Hz for active targets

## 3.5 Target Tracking and Lock-On

### Overview ✅ **OPERATIONAL** (Processing) | ✅ **OPERATIONAL** (Display — via radar-to-display bridge)

The target tracking system provides continuous monitoring of detected targets, calculating position, velocity, and acceleration vectors for tactical analysis and engagement preparation.

**Tracking Capabilities:**
- 3D position tracking with Cartesian coordinates
- Velocity vector calculation and prediction
- Acceleration monitoring for maneuvering targets
- Signal quality assessment and lock feasibility
- Target identity and classification management

### Tracking Algorithm ✅ **OPERATIONAL**

**Position Prediction:**
```
Kinematic Equations:
- New Position = Old Position + (Velocity × Time) + (0.5 × Acceleration × Time²)
- New Velocity = Old Velocity + (Acceleration × Time)
- Range = √(x² + y² + z²)
- Range Rate = (x×vx + y×vy + z×vz) / Range
```

**Angle Calculations:**
```
Spherical Coordinates:
- Azimuth = arctan2(y, x)
- Elevation = arctan2(z, √(x² + y²))
- Angular Rates calculated from position derivatives
```

**Signal Quality Assessment:**
```
SNR Model:
- Base SNR = 30 dB at 1 km reference
- SNR = 30 - 20 × log10(Range/1000)
- Lock Quality = min(1.0, SNR/30)
```

### Track Management ✅ **OPERATIONAL**

**Track Initialization:**
- Unique track ID assignment (sequential numbering)
- Initial position and velocity estimation
- Target classification assignment
- Signal quality baseline establishment

**Track Maintenance:**
- Continuous position and velocity updates
- Acceleration calculation from velocity changes
- Signal quality monitoring
- Range and angle calculations

**Track Termination:**
- Automatic removal when target exceeds maximum range
- Track loss due to insufficient signal quality
- Manual track deletion in maintenance mode

### Lock-On Capabilities ✅ **OPERATIONAL**

**Lock-On Process:**
1. **Target Selection:**
   - Must be in TRACK mode
   - Target must exist in current track list
   - Sufficient signal quality required

2. **Lock Acquisition:**
   - Enhanced tracking algorithms activated
   - Increased update rate for locked target
   - Lock quality assessment based on SNR

3. **Lock Maintenance:**
   - Continuous lock quality monitoring
   - Jamming detection algorithms
   - Automatic lock release if quality degrades

**Lock Quality Metrics:**
- **Lock Quality Range:** 0.0 (no lock) to 1.0 (perfect lock)
- **Minimum Lock Threshold:** 0.5 for stable lock
- **Jamming Detection:** 5% probability per update cycle
- **Lock Loss Conditions:** Target out of range or SNR too low

### Target Data Products ✅ **OPERATIONAL**

**Position Data:**
- **Cartesian Coordinates:** (x, y, z) in meters
- **Range:** Distance from radar in meters
- **Azimuth:** Horizontal angle in radians
- **Elevation:** Vertical angle in radians

**Kinematic Data:**
- **Velocity Vector:** (vx, vy, vz) in m/s
- **Range Rate:** Radial velocity component
- **Acceleration Vector:** (ax, ay, az) in m/s²
- **Angular Rates:** Azimuth and elevation rates

**Target Attributes:**
- **Track ID:** Unique identifier
- **Classification:** FIGHTER, HIGH_ALT, UNKNOWN
- **RCS:** Radar cross-section in m²
- **SNR:** Signal-to-noise ratio in dB
- **Last Update:** Timestamp of last data update

## 3.6 Multi-Target Management

### Overview ✅ **OPERATIONAL** (Processing) | ✅ **OPERATIONAL** (Display — via radar-to-display bridge)

The multi-target management system handles simultaneous tracking of multiple targets, providing comprehensive situational awareness for tactical operations.

**Multi-Target Capabilities:**
- Simultaneous tracking of up to 5 targets
- Unique track ID assignment and management
- Individual target state maintenance
- Prioritization and resource allocation
- Lock-on capability for selected targets

### Target Prioritization ✅ **OPERATIONAL**

**Priority Factors:**
- **Range:** Closer targets receive higher priority
- **Signal Quality:** Higher SNR targets prioritized
- **Threat Assessment:** Based on classification and behavior
- **Lock Status:** Locked targets maintain highest priority

**Resource Allocation:**
- Processing time distributed among active targets
- Lock-on limited to one target at a time
- Memory allocation for target state data
- Update rate optimization based on priority

### Track Correlation ✅ **OPERATIONAL**

**Track Association:**
- Position-based correlation between scans
- Velocity consistency checking
- Track prediction for missed detections
- False track elimination

**Track Splitting and Merging:**
- Detection of target separation
- Handling of formation flying targets
- Track continuity maintenance
- Identity preservation during maneuvers

### Multi-Target Data Flow ✅ **OPERATIONAL**

**Data Structure:**
```python
Target Dictionary Structure:
{
    track_id: {
        'position': (x, y, z),
        'velocity': (vx, vy, vz),
        'acceleration': (ax, ay, az),
        'classification': 'FIGHTER'|'HIGH_ALT'|'UNKNOWN',
        'identity': 'UNKNOWN',
        'rcs': float,  # Radar Cross Section
        'snr': float,  # Signal-to-Noise Ratio
        'last_update': timestamp
    }
}
```

**Update Process:**
1. **Target State Updates:** Position, velocity, acceleration
2. **Signal Quality Assessment:** SNR and RCS calculations
3. **Classification Updates:** Based on current behavior
4. **Range Validation:** Remove out-of-range targets
5. **Lock Quality Updates:** For locked targets

## 3.7 Target Classification

### Overview ✅ **OPERATIONAL** (SignatureAnalyzer + StealthDetector)

The target classification system analyzes target characteristics to determine target type and potential threat level. Basic classification is operational, with advanced algorithms under development.

**Current Classification Capabilities:**
- **Speed-Based Classification:** Fighter vs. transport aircraft
- **Altitude-Based Classification:** High-altitude vs. low-altitude targets
- **Default Classification:** Unknown targets

**Classification Categories:**
- **FIGHTER:** High-speed targets (>250 m/s)
- **HIGH_ALT:** High-altitude targets (>10,000 m)
- **UNKNOWN:** Default for unclassified targets

### Classification Features ✅ **OPERATIONAL**

**Advanced Classification (Planned):**
- Radar signature analysis
- Maneuvering pattern recognition
- Electronic signature identification
- Threat assessment algorithms

**Classification Parameters (Planned):**
- **Size Estimation:** Based on RCS analysis
- **Type Identification:** Aircraft, missile, UAV
- **Threat Level:** High, medium, low threat assessment
- **Confidence Level:** Classification reliability metric

### Development Roadmap

**Phase 1:** ✅ **OPERATIONAL** — SignatureAnalyzer (Swerling model, RCS classification)
- Enhanced speed and altitude classification
- Basic maneuvering pattern analysis
- Improved confidence metrics

**Phase 2:** ✅ **OPERATIONAL** — StealthDetector (Bayesian P(stealth), non-coherent integration)
- Radar signature database integration
- Advanced threat assessment algorithms
- Real-time classification updates

**Phase 3:** ✅ **OPERATIONAL** — TargetProcessor wired into track update loop
- Machine learning classification models
- Electronic warfare signature analysis
- Cooperative target identification

## 3.8 Targeting Radar Troubleshooting

### Common Issues and Solutions

#### Issue 1: Targeting Radar Data Display ✅ **RESOLVED**

**Symptoms:**
- Radar mode changes successfully
- System logs show target detection and tracking
- No targeting data appears on displays
- Target generation and tracking completes normally

**Resolution:**
- `push_targeting_data()` in `radar_to_display_bridge.py` routes track data directly to the `RadarDisplayDataCoordinator`
- `TargetProcessor` enriches each track with `SignatureAnalyzer` classification and `StealthDetector` P(stealth) before display
- Fused tracks from all sensors also appear on the TSD via `RadarDataFusion`

**Verification:**
```
tail -f FMOFP/logs/DEBUG_*.log | grep "BRIDGE\|push_targeting"
```

**Resolution Status:** ✅ Resolved — display integration operational

#### Issue 2: Target Lock Failures

**Symptoms:**
- Targets detected but lock-on fails
- Lock quality remains low
- Frequent lock loss events

**Troubleshooting Steps:**
1. Verify radar is in TRACK mode before attempting lock
2. Check target signal quality (SNR > 15 dB recommended)
3. Ensure target is within lock range
4. Monitor for jamming detection alerts

**Solution:**
```python
# Check lock prerequisites
if self.mode == targeting_radarMode.TRACK:
    if track_id in self.current_targets:
        target = self.current_targets[track_id]
        if target['snr'] > 15:
            # Attempt lock
            self.locked_track_id = track_id
```

#### Issue 3: Target Generation Issues

**Symptoms:**
- No targets appearing in SEARCH mode
- Inconsistent target generation
- Targets disappearing unexpectedly

**Troubleshooting Steps:**
1. Verify radar is in SEARCH mode
2. Check maximum target limit (5 targets)
3. Monitor target generation probability (10% per update)
4. Verify range limits (1-100 km)

### Diagnostic Procedures

#### System Health Check ✅ **OPERATIONAL**

**Health Monitoring Parameters:**
- **Target Count:** Number of active targets
- **Lock Status:** Current lock state and quality
- **Mode Status:** Current operational mode
- **Signal Quality:** Average SNR across targets

**Health Check Commands:**
```python
# Check targeting radar status
status = targeting_radar.get_status()
print(f"Mode: {status['mode']}")
print(f"Active Tracks: {status['active_tracks']}")
if 'locked_track' in status:
    print(f"Locked Track: {status['locked_track']}")
    print(f"Lock Quality: {status['lock_quality']:.2f}")
```

#### Performance Monitoring ✅ **OPERATIONAL**

**Key Performance Indicators:**
- **Target Update Rate:** Real-time updates for all targets
- **Lock Acquisition Time:** < 2 seconds for valid targets
- **Track Continuity:** > 95% track maintenance
- **False Alarm Rate:** < 5% of detections

**Performance Monitoring:**
```bash
# Monitor target tracking performance
grep "target.*updated" FMOFP/logs/DEBUG_*.log | tail -20

# Check lock performance
grep "Locked onto track" FMOFP/logs/DEBUG_*.log | tail -10
```

### Configuration Verification

#### Radar Configuration Check ✅ **OPERATIONAL**

**Key Parameters to Verify:**
- Maximum range: 100,000 meters
- Target capacity: 5 simultaneous targets
- Lock quality threshold: 0.5 minimum
- Update rate: Real-time processing

#### Address Configuration Check ✅ **OPERATIONAL**

**Verify Targeting Radar Addressing:**
- RT Address: 9 (Radar Systems)
- Subaddress: 4 (Targeting Radar)
- Message routing configuration
- Display system address mapping

### Emergency Procedures

#### Radar System Reset

**When to Use:**
- Persistent target tracking failures
- Lock system malfunction
- Unresponsive to mode changes

**Reset Procedure:**
1. Switch to STANDBY mode (clears all targets)
2. Verify target list is empty
3. Switch to desired operational mode
4. Monitor target acquisition
5. Test lock functionality if needed

#### Target Management Reset

**Clear All Targets:**
```python
# Emergency target clearing
self.current_targets.clear()
self.locked_track_id = None
self.lock_quality = 0.0
self.next_track_id = 1
```

**Reinitialize Tracking:**
1. Clear all existing targets
2. Reset track ID counter
3. Clear lock status
4. Return to SEARCH mode for new acquisitions

---

**Navigation:** [← Weather Radar System](02_Weather_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [SAR Radar System →](04_SAR_Radar_System.md)

**Related Files:**
- → [Communication & Messaging](11_Communication_Messaging.md) - 1553B protocol details
- → [Troubleshooting & Diagnostics](13_Troubleshooting_Diagnostics.md) - System-wide troubleshooting
- → [Technical Reference](14_Technical_Reference.md) - Message types and configuration

---

*File: 03_Targeting_Radar_System.md*
*Last Updated: December 2024*
*Next Review: March 2025*
