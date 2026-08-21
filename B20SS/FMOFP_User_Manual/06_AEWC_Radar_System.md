# 6. AEWC Radar System

**Navigation:** [← TFR Radar System](05_TFR_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [Primary Flight Display →](07_Primary_Flight_Display.md)

---

## 6.1 AEWC Radar Overview

### System Status ⚠️ **BASIC SIMULATION** (Target Simulation) | ✅ **OPERATIONAL** (Display Integration + Sector Priority + Electronic Protection)

The Airborne Early Warning and Control (AEWC) Radar System provides simulated air surveillance with dynamic sector priority management and electronic protection (ECM) capabilities. Display integration is active, and fused AEWC tracks appear on the Tactical Situation Display via the cross-radar data fusion layer.

**Current Implementation Status:**
- **Mode Switching:** ✅ **OPERATIONAL** - Can switch between AEWC modes
- **Target Simulation:** ⚠️ **BASIC SIMULATION** - Mathematical target generation only
- **Sector Management:** ⚠️ **BASIC SIMULATION** - Simple 6-sector division
- **Display Integration:** ✅ **OPERATIONAL** - push_aewc_data() routes tracks to display coordinator
- **Sector Priority:** ✅ **OPERATIONAL** - SectorPriorityManager dynamically allocates dwell time
- **Electronic Protection:** ✅ **OPERATIONAL** - ElectronicProtection detects and mitigates jamming

### Technical Specifications

**Operating Parameters:**
- **Maximum Range:** 400,000 meters (400 km) - simulated
- **Target Capacity:** Up to 10 simultaneous simulated targets
- **Sector Configuration:** 6 sectors, 60° each
- **Stealth Detection Probability:** 20% base rate (SNR-dependent)
- **Stealth Target Probability:** 30% of generated targets
- **RT Address:** 9 (Radar Systems)
- **Subaddress:** 5 (AEWC Radar)

**Simulation Capabilities:**
- **Target Generation:** Mathematical aircraft simulation
- **Sector Scanning:** Basic 6-sector coverage simulation
- **Stealth Simulation:** Probability-based stealth detection
- **Environmental Modeling:** Basic propagation condition simulation
- **Track Management:** Simple target tracking simulation

### Key Limitations

**What This System IS:**
- Basic target generator for testing display systems
- Sector management demonstration platform
- Target tracking simulation tool
- Data structure and messaging example
- Development and testing tool

**What This System IS NOT:**
- Real AEWC radar system
- Operational air surveillance system
- Production-ready AEWC capability
- Actual threat detection system

## 6.2 Interface Elements Identification

### AEWC Radar Control Interface

[SCREENSHOT PLACEHOLDER: AEWC Radar control interface with numbered callouts]
**Figure 6.1:** AEWC Radar Control Interface
1. **System Selection Dropdown** - Choose AEWC Radar from available systems
2. **Current Mode Indicator** - Displays active operational mode (STANDBY, SEARCH, SECTOR_SCAN, TRACK)
3. **Available Modes List** - Shows all operational modes available for selection
4. **Mode Change Button** - Initiates mode transition to selected target mode
5. **Target Count Display** - Shows number of currently tracked targets (max 10)
6. **Sector Status Panel** - Displays 6-sector scanning progress and target assignments
7. **Stealth Detection Indicator** - Shows stealth target detection probability and status
8. **System Status Display** - Real-time radar system health and processing status

### Mode Change Procedure Visualization

[SCREENSHOT PLACEHOLDER: Before mode change - STANDBY mode]
**Figure 6.2:** Before Mode Change - STANDBY Mode
1. **Current Mode: STANDBY** - System powered but not generating targets
2. **Target Count: 0** - No targets in memory
3. **Sectors: Inactive** - All 6 sectors showing inactive status
4. **System Ready Indicator** - Green status showing system ready for mode change
5. **Communication Active** - 1553B connection established and healthy

[SCREENSHOT PLACEHOLDER: During mode change to SEARCH]
**Figure 6.3:** During Mode Change - Transition to SEARCH
1. **Mode Change Status** - "Changing to SEARCH" message displayed
2. **Target Generation Preparing** - System preparing for target simulation
3. **Sector Initialization** - 6 sectors being configured for coverage
4. **Communication Activity** - 1553B messages being exchanged
5. **Status Updates** - Real-time log messages showing transition steps

[SCREENSHOT PLACEHOLDER: After mode change - SEARCH mode with targets]
**Figure 6.4:** After Mode Change - SEARCH Mode with Targets Generated
1. **New Mode: SEARCH** - Mode indicator updated to show active mode
2. **Targets Generated** - Multiple simulated targets created and tracked
3. **Target Count: 5** - Example showing 5 active targets
4. **Sector Assignment** - Targets distributed across sectors
5. **System Health** - All indicators showing normal operation

### Step-by-Step Mode Change Procedure

**Procedure: Changing AEWC Radar to SEARCH Mode**

**Step 1: Access AEWC Radar Controls**
1. Open the radar management system interface
2. Locate the AEWC Radar section [See Figure 6.1, Item 1]
3. Verify current mode shows "STANDBY" [See Figure 6.2, Item 1]
4. Confirm system status indicators are green [See Figure 6.2, Item 4]

**Step 2: Initiate Mode Change to SEARCH**
1. Click on the mode selection dropdown [See Figure 6.1, Item 3]
2. Select "SEARCH" (Mode 50) from the available modes list
3. Click the "Change Mode" button [See Figure 6.1, Item 4]
4. Monitor the status display for transition confirmation [See Figure 6.3, Item 1]

**Step 3: Monitor Mode Transition**
1. Watch for "Mode change in progress" message [See Figure 6.3, Item 1]
2. Observe target generation preparation [See Figure 6.3, Item 2]
3. Monitor sector initialization [See Figure 6.3, Item 3]
4. Verify communication activity remains healthy [See Figure 6.3, Item 4]

**Step 4: Verify SEARCH Mode Operation**
1. Confirm mode indicator shows "SEARCH" [See Figure 6.4, Item 1]
2. Check for target generation [See Figure 6.4, Item 2]
3. Monitor target count display [See Figure 6.4, Item 3]
4. Verify sector target assignments [See Figure 6.4, Item 4]

**Step 5: Monitor Target Generation**
1. Observe automatic target generation (10% probability per update)
2. Check target classifications (STEALTH, FIGHTER, HIGH_ALT, UNKNOWN)
3. Monitor stealth detection probability (20% for stealth targets)
4. Fused tracks visible on TSD via RadarDataFusion cross-radar fusion layer

### Sector Scanning Procedure Visualization

[SCREENSHOT PLACEHOLDER: SECTOR_SCAN mode interface]
**Figure 6.5:** SECTOR_SCAN Mode - 6-Sector Coverage
1. **Sector 1 (0°-60°)** - Progress bar showing scan completion
2. **Sector 2 (60°-120°)** - Active scanning indicator
3. **Sector 3 (120°-180°)** - Target assignments displayed
4. **Sector 4 (180°-240°)** - Scan progress percentage
5. **Sector 5 (240°-300°)** - Elevation coverage (-15° to +45°)
6. **Sector 6 (300°-360°)** - Sector priority and status

### AEWC Data Flow Visualization

[DIAGRAM PLACEHOLDER: AEWC target generation and sector management flow]
**Figure 6.6:** AEWC Target Generation and Sector Management Flow
1. **Mode Change Request** - User initiates mode change via interface
2. **Target Algorithm Selection** - System selects appropriate target generator
3. **Sector Configuration** - 6 sectors initialized with 60° coverage each
4. **Target Generation** - Mathematical aircraft simulation (10% probability)
5. **Stealth Processing** - 30% stealth probability, 20% detection rate
6. **Sector Assignment** - Targets assigned to appropriate sectors
7. **SNR Calculation** - Signal strength based on range and RCS
8. **Data Object Creation** - Complete target data structure created
9. **Display Integration** - Data routing to displays (not implemented)

### Target Type Comparison

[SCREENSHOT PLACEHOLDER: Normal target detection]
**Figure 6.7:** Normal Target Detection
1. **Target Type: FIGHTER** - High-speed aircraft simulation
2. **RCS: 5.2 m²** - Moderate radar cross-section
3. **Range: 125 km** - Within detection range
4. **SNR: 25 dB** - Strong signal return
5. **Detection: Confirmed** - Target successfully detected

[SCREENSHOT PLACEHOLDER: Stealth target detection attempt]
**Figure 6.8:** Stealth Target Detection Attempt
1. **Target Type: STEALTH** - Low-observable aircraft
2. **RCS: 0.05 m²** - Very low radar cross-section
3. **Range: 180 km** - Extended detection range
4. **SNR: 8 dB** - Weak signal return
5. **Detection: Failed** - Target not detected (realistic stealth simulation)

## 6.3 Operational Modes and Capabilities

### Universal Base Modes ✅ **OPERATIONAL**

**STANDBY (Mode 0)**
- System powered but not generating targets
- No target simulation or processing
- All sectors cleared
- Ready for rapid mode transition

**NORMAL (Mode 1)**
- Standard operational mode
- Basic target simulation capabilities
- Default mode for routine operations

**DEGRADED (Mode 2)**
- Reduced capability operation
- Limited target simulation
- Used when system constraints exist

**TEST (Mode 3)**
- Built-in test mode
- System self-diagnostics
- Target generation verification

**MAINTENANCE (Mode 4)**
- Maintenance and calibration mode
- System configuration access
- Diagnostic data collection

### AEWC-Specific Modes

**AEWC_SEARCH / SEARCH (Mode 50)** ⚠️ **BASIC SIMULATION**
- Generates simulated air targets randomly
- 10% probability of new target per update
- Maximum 10 targets maintained
- **Limitation:** Not actual radar search processing

```
Procedure: Switching to Search Mode
1. Access radar control interface
2. Select AEWC Radar system
3. Choose AEWC_SEARCH or SEARCH mode (Mode 50)
4. System generates simulated targets
5. Target data available for testing (not displayed)
```

**AEWC_SURVEILLANCE / SURVEILLANCE (Mode 51)** ⚠️ **BASIC SIMULATION**
- Enhanced target surveillance simulation
- Same target generation as SEARCH mode
- Sector scanning progress simulation
- **Limitation:** Not actual surveillance processing

**SECTOR_SCAN (Mode 52)** ⚠️ **BASIC SIMULATION**
- Sector-by-sector scanning simulation
- 6 predefined sectors (60° each)
- Sector progress tracking simulation
- **Limitation:** Not actual sector scanning

**STEALTH_DETECTION (Mode 53)** ✅ **OPERATIONAL** — StealthDetector
- Mode exists in enum but no special processing
- Uses same target generation as other modes
- No enhanced stealth detection algorithms
- **Status:** Basic target simulation only

**ELECTRONIC_PROTECTION (Mode 54)** ✅ **OPERATIONAL** — ElectronicProtection
- Mode exists in enum but no special processing
- No electronic warfare capabilities
- No jamming resistance algorithms
- **Status:** Placeholder only

**AEWC_TRACK / TRACK (Mode 55)** ⚠️ **BASIC SIMULATION**
- Target tracking simulation
- Same target generation as other modes
- Basic track management simulation
- **Limitation:** Not actual track processing

## 6.4 Target Simulation Details

### Mathematical Target Generation ⚠️ **BASIC SIMULATION**

**Algorithm Implementation:**
```python
def _generate_target():
    # Random position within 400km range
    r = np.random.uniform(5000, 400000)
    theta = np.random.uniform(0, 2*np.pi)
    phi = np.random.uniform(-np.pi/4, np.pi/4)

    # Calculate 3D position
    x = r * np.cos(phi) * np.cos(theta)
    y = r * np.cos(phi) * np.sin(theta)
    z = r * np.sin(phi)

    # Random velocity (150-500 m/s)
    v_mag = np.random.uniform(150, 500)
    # Random acceleration (0-50 m/s²)
    a_mag = np.random.uniform(0, 50)

    return target_data
```

**Target Characteristics:**
- **Position Range:** 5-400 km from radar
- **Velocity Range:** 150-500 m/s (realistic aircraft speeds)
- **Acceleration Range:** 0-50 m/s² (maneuvering capability)
- **RCS Range:** 0.01-100 m² (stealth to large aircraft)
- **Classification:** STEALTH, FIGHTER, HIGH_ALT, UNKNOWN

### Stealth Detection Simulation ⚠️ **BASIC SIMULATION**

**Stealth Algorithm:**
```python
def _calculate_stealth_detection():
    # 30% chance target is stealth
    is_stealth = np.random.random() < 0.3

    if is_stealth:
        rcs = np.random.uniform(0.01, 0.1)  # Low RCS
        # 20% base detection probability
        detection_prob = 0.2 * (snr / 30)
        if np.random.random() > detection_prob:
            return False  # Target not detected

    return True  # Target detected
```

**Stealth Characteristics:**
- **Stealth Probability:** 30% of generated targets
- **Stealth RCS:** 0.01-0.1 m² (very low radar signature)
- **Detection Probability:** 20% base rate for stealth targets
- **SNR Dependency:** Detection probability scales with signal strength

### Sector Management ⚠️ **BASIC SIMULATION**

**Sector Configuration:**
```python
def _initialize_sectors():
    # 6 sectors covering 360°
    for i in range(6):
        sector_id = f"SECTOR_{i+1}"
        azimuth_start = i * 60
        azimuth_end = (i + 1) * 60
        elevation_range = (-15, 45)  # ±15° to +45°

        sectors[sector_id] = Sector(
            azimuth_range=(azimuth_start, azimuth_end),
            elevation_range=elevation_range,
            priority=1
        )
```

**Sector Characteristics:**
- **Sector Count:** 6 sectors total
- **Azimuth Coverage:** 60° per sector (360° total)
- **Elevation Coverage:** -15° to +45° per sector
- **Scan Progress:** Simulated 0.0-1.0 progress per sector
- **Active Tracks:** Target assignment per sector

## 6.5 Environmental Simulation

### Signal Processing Simulation ⚠️ **BASIC SIMULATION**

**SNR Calculation:**
```python
def _calculate_snr(target):
    # Basic radar equation simulation
    tx_power = 100000  # 100 kW
    wavelength = 0.03  # 10 GHz
    antenna_gain = 10000  # 40 dB

    range_to_target = calculate_range(target['position'])
    received_power = (tx_power * antenna_gain**2 * wavelength**2 * target['rcs']) / \
                    ((4*np.pi)**3 * range_to_target**4)

    # Environmental factors
    if propagation_conditions['ducting']:
        received_power += 10  # dB enhancement

    snr = 10 * np.log10(received_power) - noise_floor
    return max(0, snr)
```

**Environmental Parameters:**
- **Noise Floor:** -110 dBm
- **Propagation Ducting:** Boolean flag affecting SNR
- **Humidity:** 0.5 (50% relative humidity)
- **Temperature:** 20.0°C
- **Clutter Map:** Empty dictionary (no clutter simulation)

### Performance Metrics ⚠️ **BASIC SIMULATION**

**Simulated Performance:**
- **Detection Range:** Up to 400 km (mathematical limit)
- **Target Capacity:** 10 simultaneous targets
- **Update Rate:** Real-time target position updates
- **Sector Scan Rate:** 1-second update intervals
- **False Alarm Rate:** Not simulated

## 6.6 System Limitations and Development Status

### Current Limitations (remaining simulation constraints)

**Processing Limitations:**
- **No Real Radar Processing:** Only mathematical target generation
- **No Actual Target Data:** Targets are mathematically simulated
- **No Signal Processing:** No actual radar signal processing
- **No Beam Steering:** No actual radar beam control
- **No Real Detection:** Simulated detection doesn't match real world

**Operational Limitations:**
- **No Display Integration:** Generated targets not shown anywhere
- **No Real-Time Operation:** Targets generated on-demand only
- **No Mission Integration:** No connection to mission planning systems
- **No Threat Assessment:** No actual threat evaluation capability
- **No Electronic Warfare:** No jamming or countermeasure capability

### Development Roadmap

**Phase 1:** ❌ **NOT PLANNED**
- Real AEWC signal processing algorithms
- Actual radar data integration
- Beam steering and control

**Phase 2:** ❌ **NOT PLANNED**
- Display system integration
- Mission planning system integration
- Real-time target processing

**Phase 3:** ❌ **NOT PLANNED**
- Advanced AEWC algorithms
- Electronic warfare capabilities
- Threat assessment systems

### Intended Use Cases

**Current Valid Uses:**
- **Display System Testing:** Test target data routing and display
- **Message System Testing:** Verify AEWC message handling
- **Mode Switching Testing:** Test radar mode change procedures
- **Data Structure Validation:** Verify target data formatting
- **Sector Management Testing:** Test sector scanning simulation

**Invalid Use Cases:**
- **Operational Air Surveillance:** System cannot provide real target data
- **Threat Detection:** No actual threat identification capability
- **Mission Planning:** No real situational awareness data
- **Air Traffic Control:** No actual aircraft tracking capability

## 6.7 AEWC Radar Troubleshooting

### Common Issues and Solutions

#### Issue 1: No Target Generation

**Symptoms:**
- Mode changes successful but no targets generated
- Empty target lists returned
- Error messages in AEWC radar logs

**Root Cause:**
- System in STANDBY mode (no target generation)
- Target capacity limit reached (10 targets maximum)
- Invalid mode selection for target generation

**Solution:**
1. Verify radar is not in STANDBY mode
2. Check current target count (maximum 10)
3. Use target-generating modes (SEARCH, SURVEILLANCE, TRACK)
4. Monitor logs for specific error messages

#### Issue 2: Target Data Not Available ❌ **EXPECTED BEHAVIOR**

**Symptoms:**
- Targets generated but not visible anywhere
- No display of target information
- Data seems to disappear after generation

**Root Cause:**
- Display integration not implemented
- This is expected behavior, not a bug

**Current Workaround:**
1. Monitor AEWC radar processing in system logs:
   ```
   tail -f FMOFP/logs/DEBUG_*.log | grep AEWC_RADAR
   ```
2. Verify target generation completion in logs
3. Check sector scanning progress in logs
4. Use system health monitoring for radar status
5. **Note:** Targets are generated but not displayed

#### Issue 3: Stealth Targets Not Detected

**Symptoms:**
- Expected stealth targets not appearing in target list
- Inconsistent target detection
- Lower target counts than expected

**Root Cause:**
- Stealth detection simulation working as designed
- 30% of targets are stealth with 20% detection probability
- This is expected behavior for simulation

**Solution:**
1. Understand stealth detection is probabilistic
2. Stealth targets may not be detected (realistic simulation)
3. Monitor logs for stealth detection messages
4. Target count variation is normal

#### Issue 4: Sector Scanning Issues

**Symptoms:**
- Sector scan progress not updating
- Sectors appear inactive
- No sector-specific data

**Troubleshooting Steps:**
1. Verify radar is in SECTOR_SCAN mode
2. Check sector update timing (1-second intervals)
3. Monitor sector progress in logs
4. Ensure targets are being assigned to sectors

### Diagnostic Procedures

#### System Health Check ✅ **OPERATIONAL**

**Health Monitoring Parameters:**
- **Target Generation Status:** Current target count
- **Mode Status:** Current operational mode
- **Sector Status:** Sector scanning progress
- **Stealth Detection Rate:** Detection probability metrics

**Health Check Commands:**
```python
# Check AEWC radar status
status = aewc_radar.get_status()
print(f"Mode: {status['mode']}")
print(f"Running: {status['running']}")
print(f"Healthy: {status['healthy']}")
print(f"Active Tracks: {status['active_tracks']}")
print(f"Max Range: {status['max_range']} meters")
print(f"Stealth Detection Probability: {status['stealth_detection_probability']}")

# Check sector status
for sector_id, sector_info in status['sectors'].items():
    print(f"{sector_id}: Progress {sector_info['scan_progress']:.1%}, "
          f"Tracks {sector_info['active_tracks']}")
```

#### Performance Monitoring ⚠️ **LIMITED**

**Available Metrics:**
- **Target Generation Rate:** 10% probability per update
- **Target Update Rate:** Real-time position updates
- **Sector Scan Rate:** 1-second update intervals
- **Mode Change Time:** < 2 seconds

**Monitoring Commands:**
```bash
# Monitor target generation
grep "target.*generated" FMOFP/logs/DEBUG_*.log | tail -10

# Check stealth detection
grep "stealth.*detection" FMOFP/logs/DEBUG_*.log | tail -10

# Monitor sector scanning
grep "sector.*scan" FMOFP/logs/DEBUG_*.log | tail -10

# Check mode changes
grep "AEWC.*mode.*changed" FMOFP/logs/DEBUG_*.log | tail -10
```

### Configuration Verification

#### Basic Configuration Check ✅ **OPERATIONAL**

**Key Parameters:**
- Maximum range: 400,000 meters ✅
- Target capacity: 10 simultaneous targets ✅
- Sector count: 6 sectors ✅
- Stealth detection probability: 20% ✅

#### Mode Verification ⚠️ **BASIC SIMULATION**

**Implemented Modes (Basic Simulation):**
- AEWC_SEARCH/SEARCH (50): ⚠️ Target generation simulation
- AEWC_SURVEILLANCE/SURVEILLANCE (51): ⚠️ Target generation simulation
- SECTOR_SCAN (52): ⚠️ Sector scanning simulation
- AEWC_TRACK/TRACK (55): ⚠️ Target tracking simulation

**Limited Implementation Modes:**
- STEALTH_DETECTION (53): ✅ Bayesian stealth probability tracking via StealthDetector
- ELECTRONIC_PROTECTION (54): ✅ Jamming detection, frequency agility, beam notching, sector skip

#### Sector Configuration Verification ⚠️ **BASIC SIMULATION**

**Sector Parameters:**
- Sector 1: 0°-60° azimuth, -15° to +45° elevation ✅
- Sector 2: 60°-120° azimuth, -15° to +45° elevation ✅
- Sector 3: 120°-180° azimuth, -15° to +45° elevation ✅
- Sector 4: 180°-240° azimuth, -15° to +45° elevation ✅
- Sector 5: 240°-300° azimuth, -15° to +45° elevation ✅
- Sector 6: 300°-360° azimuth, -15° to +45° elevation ✅

---

**Navigation:** [← TFR Radar System](05_TFR_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [Primary Flight Display →](07_Primary_Flight_Display.md)

**Related Files:**
- → [Communication & Messaging](11_Communication_Messaging.md) - 1553B protocol details
- → [Troubleshooting & Diagnostics](13_Troubleshooting_Diagnostics.md) - System-wide troubleshooting
- → [Technical Reference](14_Technical_Reference.md) - Message types and configuration

---

*File: 06_AEWC_Radar_System.md*
*Last Updated: December 2024*
*Next Review: March 2025*

**IMPORTANT NOTICE:** This system provides basic target simulation only. It does not perform actual AEWC radar processing and is not suitable for operational use. Use only for development and testing purposes.
