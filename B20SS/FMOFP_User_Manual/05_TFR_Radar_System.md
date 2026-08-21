# 5. TFR Radar System

**Navigation:** [← SAR Radar System](04_SAR_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [AEWC Radar System →](06_AEWC_Radar_System.md)

---

## 5.1 TFR Radar Overview

### System Status ⚠️ **BASIC SIMULATION** (Terrain Simulation) | ✅ **OPERATIONAL** (Display Integration + PathOptimiser + ClearanceManager)

The Terrain Following Radar (TFR) System provides basic simulated terrain profiling capabilities for development and testing purposes. The system generates mathematical terrain simulations and routes them to the display coordinator via `push_tfr_data()`. `PathOptimiser` computes safe altitude command sequences and `ClearanceManager` provides CLEAR / LOW / CAUTION / PULL_UP terrain clearance warnings.

**Current Implementation Status:**
- **Mode Switching:** ✅ **OPERATIONAL** - Can switch between TFR modes
- **Terrain Simulation:** ⚠️ **BASIC SIMULATION** - Mathematical terrain generation only
- **Warning System:** ⚠️ **BASIC SIMULATION** - Simple threshold-based warnings
- **Display Integration:** ✅ **OPERATIONAL** - push_tfr_data() routes terrain data to display coordinator
- **Path Optimisation:** ✅ **OPERATIONAL** - PathOptimiser generates safe altitude command sequence
- **Clearance Management:** ✅ **OPERATIONAL** - ClearanceManager monitors terrain clearance (CLEAR/LOW/CAUTION/PULL_UP)

### Technical Specifications

**Operating Parameters:**
- **Scan Range:** 10,000 meters (simulated)
- **Scan Width:** 2,000 meters (simulated)
- **Elevation Points:** 100 data points per profile
- **Warning Interval:** 1.0 seconds
- **RT Address:** 9 (Radar Systems)
- **Subaddress:** 3 (TFR Radar)

**Simulation Capabilities:**
- **Terrain Model:** Mathematical sine wave terrain generation
- **Warning Types:** High terrain and steep terrain detection
- **Data Format:** Distance-elevation coordinate pairs
- **Profile Generation:** Real-time mathematical calculation
- **Metadata Integration:** Complete terrain profile data structure

### Key Limitations

**What This System IS:**
- Mathematical terrain profile generator for testing
- Basic warning threshold demonstration
- Mode switching demonstration platform
- Data structure and messaging example
- Development and testing tool

**What This System IS NOT:**
- Real terrain following radar system
- Operational terrain avoidance system
- Production-ready TFR capability
- Actual obstacle detection system

## 5.2 Interface Elements Identification

### TFR Radar Control Interface

[SCREENSHOT PLACEHOLDER: TFR Radar control interface with numbered callouts]
**Figure 5.1:** TFR Radar Control Interface
1. **System Selection Dropdown** - Choose TFR Radar from available systems
2. **Current Mode Indicator** - Displays active operational mode (STANDBY, SEARCH, TRACK, TERRAIN_FOLLOWING)
3. **Available Modes List** - Shows all operational modes available for selection
4. **Mode Change Button** - Initiates mode transition to selected target mode
5. **Terrain Profile Status** - Shows when terrain data generation is active
6. **Warning Indicator** - Displays terrain warnings (HIGH_TERRAIN, STEEP_TERRAIN)
7. **System Status Display** - Real-time radar system health and processing status
8. **Configuration Access** - Terrain simulation parameters and settings

### Mode Change Procedure Visualization

[SCREENSHOT PLACEHOLDER: Before mode change - STANDBY mode]
**Figure 5.2:** Before Mode Change - STANDBY Mode
1. **Current Mode: STANDBY** - System powered but not generating terrain data
2. **Terrain Status: Inactive** - No terrain simulation occurring
3. **System Ready Indicator** - Green status showing system ready for mode change
4. **Available Modes** - SEARCH, TRACK, TERRAIN_FOLLOWING modes available
5. **Communication Active** - 1553B connection established and healthy

[SCREENSHOT PLACEHOLDER: During mode change to SEARCH]
**Figure 5.3:** During Mode Change - Transition to SEARCH
1. **Mode Change Status** - "Changing to SEARCH" message displayed
2. **Terrain Generation Preparing** - System preparing for terrain simulation
3. **System Processing** - Radar system reconfiguring for SEARCH mode
4. **Communication Activity** - 1553B messages being exchanged
5. **Status Updates** - Real-time log messages showing transition steps

[SCREENSHOT PLACEHOLDER: After mode change - SEARCH mode with terrain generated]
**Figure 5.4:** After Mode Change - SEARCH Mode with Terrain Generated
1. **New Mode: SEARCH** - Mode indicator updated to show active mode
2. **Terrain Generated** - Mathematical terrain simulation completed
3. **Profile Data Available** - 100 distance-elevation data points created
4. **Warning System Active** - Terrain warnings being evaluated
5. **System Health** - All indicators showing normal operation

### Step-by-Step Mode Change Procedure

**Procedure: Changing TFR Radar to SEARCH Mode**

**Step 1: Access TFR Radar Controls**
1. Open the radar management system interface
2. Locate the TFR Radar section [See Figure 5.1, Item 1]
3. Verify current mode shows "STANDBY" [See Figure 5.2, Item 1]
4. Confirm system status indicators are green [See Figure 5.2, Item 3]

**Step 2: Initiate Mode Change to SEARCH**
1. Click on the mode selection dropdown [See Figure 5.1, Item 3]
2. Select "SEARCH" (Mode 20) from the available modes list
3. Click the "Change Mode" button [See Figure 5.1, Item 4]
4. Monitor the status display for transition confirmation [See Figure 5.3, Item 1]

**Step 3: Monitor Mode Transition**
1. Watch for "Mode change in progress" message [See Figure 5.3, Item 1]
2. Observe terrain generation preparation [See Figure 5.3, Item 2]
3. Monitor log output for detailed transition steps
4. Verify communication activity remains healthy [See Figure 5.3, Item 4]

**Step 4: Verify SEARCH Mode Operation**
1. Confirm mode indicator shows "SEARCH" [See Figure 5.4, Item 1]
2. Check for terrain generation completion [See Figure 5.4, Item 2]
3. Verify terrain profile data has been created [See Figure 5.4, Item 3]
4. Monitor warning system activation [See Figure 5.4, Item 4]

**Step 5: Understand System Limitations**
1. Note that this is mathematical terrain simulation only
2. Understand that no real radar processing occurs
3. Display integration active; ClearanceManager warnings visible in status
4. Use log monitoring to verify terrain generation and warnings

### Terrain Warning Procedure Visualization

[SCREENSHOT PLACEHOLDER: Terrain warning detection]
**Figure 5.5:** Terrain Warning Detection
1. **Warning Type: HIGH_TERRAIN** - Elevation > 1500 meters detected
2. **Warning Location** - Distance and elevation coordinates displayed
3. **Warning Indicator** - Visual alert in interface
4. **Warning Log** - Real-time warning messages in system logs
5. **Warning Timing** - 1-second minimum interval between warnings

### TFR Data Flow Visualization

[DIAGRAM PLACEHOLDER: TFR terrain generation flow]
**Figure 5.6:** TFR Terrain Generation Flow
1. **Mode Change Request** - User initiates mode change via interface
2. **Terrain Algorithm Selection** - System selects mathematical terrain model
3. **Profile Calculation** - 100 distance-elevation points calculated
4. **Sine Wave Generation** - Primary and secondary terrain variations
5. **Noise Addition** - Gaussian noise overlay for realism
6. **Warning Evaluation** - Terrain checked against warning thresholds
7. **Data Object Creation** - Complete terrain profile data structure created
8. **Display Integration** - ✅ Active — terrain data routed via radar-to-display bridge

### Terrain Profile Comparison

[SCREENSHOT PLACEHOLDER: SEARCH mode terrain profile]
**Figure 5.7:** SEARCH Mode Terrain Profile
1. **Distance Range** - 0-10,000 meters coverage
2. **Elevation Profile** - Mathematical sine wave terrain
3. **Data Points** - 100 distance-elevation coordinates
4. **Base Elevation** - 1000 meters baseline
5. **Terrain Variations** - Primary and secondary wave patterns

[SCREENSHOT PLACEHOLDER: TERRAIN_FOLLOWING mode profile]
**Figure 5.8:** TERRAIN_FOLLOWING Mode Profile
1. **Distance Range** - 0-5,000 meters (filtered for close terrain)
2. **Elevation Profile** - Same mathematical model, filtered range
3. **Data Points** - ~50 distance-elevation coordinates
4. **Scan Width** - 1000 meters (narrower than other modes)
5. **Focus Area** - Close-range terrain emphasis

## 5.3 Operational Modes and Capabilities

### Universal Base Modes ✅ **OPERATIONAL**

**STANDBY (Mode 0)**
- System powered but not generating terrain data
- No terrain simulation or processing
- Minimal power consumption
- Ready for rapid mode transition

**NORMAL (Mode 1)**
- Standard operational mode
- Basic terrain simulation capabilities
- Default mode for routine operations

**DEGRADED (Mode 2)**
- Reduced capability operation
- Limited terrain simulation
- Used when system constraints exist

**TEST (Mode 3)**
- Built-in test mode
- System self-diagnostics
- Terrain generation verification

**MAINTENANCE (Mode 4)**
- Maintenance and calibration mode
- System configuration access
- Diagnostic data collection

### TFR-Specific Modes

**TFR_SEARCH / SEARCH (Mode 20)** ⚠️ **BASIC SIMULATION**
- Generates basic terrain profile simulation
- Mathematical terrain model with sine waves
- Terrain data regenerated on mode entry
- **Limitation:** Not actual terrain radar scanning

```
Procedure: Switching to Search Mode
1. Access radar control interface
2. Select TFR Radar system
3. Choose TFR_SEARCH or SEARCH mode (Mode 20)
4. System generates mathematical terrain simulation
5. Terrain data available for testing (not displayed)
```

**TFR_TRACK / TRACK (Mode 21)** ⚠️ **BASIC SIMULATION**
- Enhanced terrain profile simulation
- Same mathematical model as SEARCH mode
- Terrain data regenerated on mode entry
- **Limitation:** Not actual terrain tracking

**TFR_ACTIVE / ACTIVE (Mode 22)** ⚠️ **BASIC SIMULATION**
- Active terrain simulation mode
- Uses same mathematical terrain generation
- No additional processing beyond other modes
- **Limitation:** Not actual active radar processing

**TERRAIN_FOLLOWING (Mode 23)** ⚠️ **BASIC SIMULATION**
- Specialized terrain following simulation
- Filtered terrain data (distance < 5000m only)
- Narrower scan width simulation (1000m vs 2000m)
- **Limitation:** Not actual terrain following capability

**OBSTACLE_AVOIDANCE (Mode 24)** ✅ **OPERATIONAL** — PathOptimiser handles obstacle avoidance
- Mode exists in enum but no special processing
- Uses same terrain generation as other modes
- No obstacle-specific algorithms
- **Status:** Basic terrain simulation only

**TFR_GROUND_MAPPING / GROUND_MAPPING (Mode 25)** ❌ **NOT IMPLEMENTED**
- Mode exists in enum but no special processing
- Uses same terrain generation as other modes
- No ground mapping algorithms
- **Status:** Basic terrain simulation only

## 5.4 Terrain Simulation Details

### Mathematical Terrain Generation ⚠️ **BASIC SIMULATION**

**Algorithm Implementation:**
```python
def _initialize_terrain_data():
    distances = np.linspace(0, 10000, 100)  # 0-10km, 100 points
    # Mathematical terrain model
    elevations = 1000 + 500 * np.sin(distances / 1000) + \
                200 * np.sin(distances / 300) + \
                np.random.normal(0, 50, 100)
    return list(zip(distances, elevations))
```

**Terrain Characteristics:**
- **Base Elevation:** 1000 meters
- **Primary Variation:** 500m amplitude, 1km wavelength sine wave
- **Secondary Variation:** 200m amplitude, 300m wavelength sine wave
- **Noise Component:** Gaussian noise, σ=50 meters
- **Distance Range:** 0-10,000 meters
- **Data Points:** 100 elevation samples

### Warning System ⚠️ **BASIC SIMULATION**

**Warning Algorithm:**
```python
def _check_terrain_warnings():
    warnings = []
    for distance, elevation in terrain_data:
        if elevation > 1500:  # High terrain threshold
            warnings.append({
                'type': 'HIGH_TERRAIN',
                'distance': distance,
                'elevation': elevation
            })
        elif abs(elevation - 1000) > 300:  # Steep terrain threshold
            warnings.append({
                'type': 'STEEP_TERRAIN',
                'distance': distance,
                'elevation': elevation
            })
    return warnings
```

**Warning Types:**
- **HIGH_TERRAIN:** Elevation > 1500 meters
- **STEEP_TERRAIN:** Deviation from base (1000m) > 300 meters
- **Warning Interval:** 1.0 second minimum between warnings
- **Warning Format:** Type, distance, elevation data

### Terrain Following Profile ⚠️ **BASIC SIMULATION**

**Specialized Processing for TERRAIN_FOLLOWING Mode:**
```python
def _send_terrain_following_profile():
    # Filter to closer terrain points only
    terrain_following_points = []
    for distance, elevation in terrain_data:
        if distance < 5000:  # Focus on closer terrain
            terrain_following_points.append((distance, elevation))

    # Use narrower scan width
    scan_width = self.scan_width / 2  # 1000m instead of 2000m
```

**Profile Characteristics:**
- **Range Limit:** 5000 meters (vs. 10000m for other modes)
- **Scan Width:** 1000 meters (vs. 2000m for other modes)
- **Data Points:** ~50 points (filtered from 100)
- **Purpose:** Simulated close-range terrain focus

## 5.5 Data Structure and Message Integration

### Terrain Data Structure ✅ **OPERATIONAL**

**Data Format:**
```python
TFR Terrain Data Structure:
{
    'profile_data': [(distance, elevation), ...],  # List of tuples
    'scan_width': float,  # Scan width in meters
    'scan_range': 10000,  # Maximum range in meters
    'elevation_points': 100,  # Number of data points
    'timestamp': float,  # Data generation time
    'mode': str  # Current TFR mode
}
```

**Terrain Profile Format:**
- **Distance:** 0-10,000 meters in 100-meter increments
- **Elevation:** Calculated elevation in meters above sea level
- **Coordinate System:** Local distance-elevation pairs
- **Data Type:** List of (distance, elevation) tuples
- **Update Method:** Regenerated on mode changes

### Message Integration ✅ **OPERATIONAL**

**Message Flow:**
1. **Mode Change Request:** Received and processed
2. **Terrain Regeneration:** New mathematical terrain calculated
3. **Data Packaging:** Terrain data formatted with metadata
4. **Message Creation:** TFR elevation profile message created
5. **Warning Check:** Terrain warnings evaluated and sent
6. **Completion Notification:** Mode change completion sent
7. **Data Transmission:** ✅ **OPERATIONAL** — push_tfr_data() to display coordinator

**Warning Message Flow:**
1. **Warning Evaluation:** Terrain checked against thresholds
2. **Warning Creation:** Warning messages generated for violations
3. **Warning Transmission:** Individual warning messages sent
4. **Warning Timing:** 1-second minimum interval between checks

## 5.6 System Limitations and Development Status

### Current Limitations

**Processing Limitations:**
- **No Real Radar Processing:** Only mathematical terrain generation
- **No Actual Terrain Data:** Terrain is mathematically simulated
- **No Range Processing:** No actual radar signal processing
- **No Beam Steering:** No actual radar beam control
- **No Ground Truth:** Simulated terrain doesn't match real world

**Operational Limitations:**
- **Display Integration:** ✅ Terrain data routed via `push_tfr_data()` to display coordinator
- **No Real-Time Operation:** Terrain generated on mode change only
- **No Aircraft Integration:** No connection to flight control systems
- **No Mission Planning:** No integration with navigation systems
- **No Obstacle Detection:** No actual obstacle avoidance capability

### Development Roadmap

**Phase 1:** ❌ **NOT PLANNED**
- Real TFR signal processing algorithms
- Actual radar data integration
- Beam steering and control

**Phase 2:** ❌ **NOT PLANNED**
- Display system integration
- Flight control system integration
- Real-time terrain processing

**Phase 3:** ❌ **NOT PLANNED**
- Advanced terrain following algorithms
- Automatic obstacle avoidance
- Terrain database integration

### Intended Use Cases

**Current Valid Uses:**
- **Display System Testing:** Test terrain data routing and display
- **Message System Testing:** Verify TFR message handling
- **Mode Switching Testing:** Test radar mode change procedures
- **Data Structure Validation:** Verify terrain profile formatting
- **Warning System Testing:** Test warning message generation

**Invalid Use Cases:**
- **Operational Terrain Following:** System cannot provide real terrain data
- **Navigation:** Simulated terrain doesn't represent actual terrain
- **Flight Safety:** No actual obstacle detection capability
- **Mission Planning:** No real terrain avoidance data

## 5.7 TFR Radar Troubleshooting

### Common Issues and Solutions

#### Issue 1: No Terrain Data Generation

**Symptoms:**
- Mode changes successful but no terrain data generated
- Empty terrain profile arrays returned
- Error messages in TFR radar logs

**Root Cause:**
- System in STANDBY mode (no terrain generation)
- Invalid mode selection for data requests
- Memory allocation failures

**Solution:**
1. Verify radar is not in STANDBY mode
2. Use operational modes (SEARCH, TRACK, TERRAIN_FOLLOWING)
3. Check system memory availability
4. Monitor logs for specific error messages

#### Issue 2: Terrain Data Not Available ❌ **EXPECTED BEHAVIOR**

**Symptoms:**
- Terrain data generated but not visible anywhere
- No display of terrain profiles
- Data seems to disappear after generation

**Root Cause:**
- Display integration: ✅ operational via bridge
- This is expected behavior, not a bug

**Current Workaround:**
1. Monitor TFR radar processing in system logs:
   ```
   tail -f FMOFP/logs/DEBUG_*.log | grep TFR_RADAR
   ```
2. Verify terrain generation completion in logs
3. Check for terrain warning messages
4. Use system health monitoring for radar status
5. **Note:** Terrain data is generated but not displayed

#### Issue 3: No Terrain Warnings Generated

**Symptoms:**
- Terrain data generated but no warnings
- Expected warnings for high or steep terrain not appearing
- Warning system appears inactive

**Troubleshooting Steps:**
1. Check warning interval timing (1-second minimum)
2. Verify terrain data contains elevations > 1500m or deviations > 300m
3. Monitor logs for warning generation messages
4. Ensure system is not in STANDBY mode

**Expected Warning Conditions:**
- **HIGH_TERRAIN:** Any elevation > 1500 meters
- **STEEP_TERRAIN:** Any elevation deviation from 1000m > 300 meters
- **Normal Terrain:** Base elevation ~1000m ± variations

#### Issue 4: Inconsistent Terrain Profiles

**Symptoms:**
- Different terrain profiles on each mode change
- Terrain data appears random or inconsistent
- Unexpected terrain characteristics

**Root Cause:**
- Terrain includes random noise component (σ=50m)
- Terrain regenerated on each mode change
- This is expected behavior for simulation

**Solution:**
1. Understand that terrain includes random component
2. Terrain regeneration is normal on mode changes
3. Base terrain pattern remains consistent (sine waves)
4. Random noise provides realistic variation

### Diagnostic Procedures

#### System Health Check ✅ **OPERATIONAL**

**Health Monitoring Parameters:**
- **Terrain Generation Status:** Current processing state
- **Mode Status:** Current operational mode
- **Warning System Status:** Warning generation activity
- **Data Point Count:** Number of terrain points generated

**Health Check Commands:**
```python
# Check TFR radar status
status = tfr_radar.get_status()
print(f"Mode: {status['mode']}")
print(f"Running: {status['running']}")
print(f"Healthy: {status['healthy']}")
print(f"Scan Range: {status['scan_range']} meters")
print(f"Scan Width: {status['scan_width']} meters")
```

#### Performance Monitoring ⚠️ **LIMITED**

**Available Metrics:**
- **Terrain Generation Time:** Typically < 0.1 seconds
- **Mode Change Time:** < 2 seconds
- **Warning Generation Rate:** Based on 1-second intervals
- **Error Rate:** Basic error counting

**Monitoring Commands:**
```bash
# Monitor terrain generation
grep "elevation profile.*sent" FMOFP/logs/DEBUG_*.log | tail -10

# Check terrain warnings
grep "terrain warning" FMOFP/logs/DEBUG_*.log | tail -10

# Monitor mode changes
grep "TFR.*mode.*changed" FMOFP/logs/DEBUG_*.log | tail -10
```

### Configuration Verification

#### Basic Configuration Check ✅ **OPERATIONAL**

**Key Parameters:**
- Scan range: 10,000 meters ✅
- Scan width: 2,000 meters ✅
- Elevation points: 100 data points ✅
- Warning interval: 1.0 seconds ✅

#### Mode Verification ⚠️ **BASIC SIMULATION**

**Implemented Modes (Basic Simulation):**
- TFR_SEARCH/SEARCH (20): ⚠️ Mathematical terrain generation
- TFR_TRACK/TRACK (21): ⚠️ Mathematical terrain generation
- TFR_ACTIVE/ACTIVE (22): ⚠️ Mathematical terrain generation
- TERRAIN_FOLLOWING (23): ⚠️ Filtered terrain generation

**Limited Implementation Modes:**
- OBSTACLE_AVOIDANCE (24): ✅ PathOptimiser + ClearanceManager (PULL_UP/CAUTION/LOW/CLEAR)
- TFR_GROUND_MAPPING/GROUND_MAPPING (25): ❌ Same as basic terrain generation

#### Warning System Verification ⚠️ **BASIC SIMULATION**

**Warning Thresholds:**
- High terrain: > 1500 meters elevation ✅
- Steep terrain: > 300 meters deviation from 1000m base ✅
- Warning interval: 1.0 second minimum ✅
- Warning types: HIGH_TERRAIN, STEEP_TERRAIN ✅

---

**Navigation:** [← SAR Radar System](04_SAR_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [AEWC Radar System →](06_AEWC_Radar_System.md)

**Related Files:**
- → [Communication & Messaging](11_Communication_Messaging.md) - 1553B protocol details
- → [Troubleshooting & Diagnostics](13_Troubleshooting_Diagnostics.md) - System-wide troubleshooting
- → [Technical Reference](14_Technical_Reference.md) - Message types and configuration

---

*File: 05_TFR_Radar_System.md*
*Last Updated: December 2024*
*Next Review: March 2025*

**IMPORTANT NOTICE:** This system provides basic terrain simulation only. It does not perform actual terrain following radar processing and is not suitable for operational use. Use only for development and testing purposes.
