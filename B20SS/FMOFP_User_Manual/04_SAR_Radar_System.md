# 4. SAR Radar System

**Navigation:** [← Targeting Radar System](03_Targeting_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [TFR Radar System →](05_TFR_Radar_System.md)

---

## 4.1 SAR Radar Overview

### System Status ⚠️ **BASIC SIMULATION** (Pattern Generation) | ✅ **OPERATIONAL** (Display Integration + Change Detection)

The Synthetic Aperture Radar (SAR) System provides basic simulated imaging capabilities for development and testing purposes. The system generates simple pattern-based imagery and routes it to the display coordinator via `push_sar_data()`. CFAR log-ratio change detection (`sar_processor.py`) identifies differences between successive imagery frames.

**Current Implementation Status:**
- **Mode Switching:** ✅ **OPERATIONAL** - Can switch between SAR modes
- **Pattern Generation:** ⚠️ **BASIC SIMULATION** - Simple simulated patterns only
- **Image Data Structure:** ✅ **OPERATIONAL** - Proper data formatting and geo-referencing
- **Display Integration:** ✅ **OPERATIONAL** - push_sar_data() routes imagery to display coordinator
- **Change Detection:** ✅ **OPERATIONAL** - CFAR log-ratio change detection (sar_processor.py)

### Technical Specifications

**Operating Parameters:**
- **Image Dimensions:** 1024 × 1024 pixels
- **Resolution:** 1.0 meters per pixel (simulated)
- **Coverage Area:** 10 km × 10 km (simulated)
- **Geo-Reference Coverage:** ±5000 meters from center point
- **RT Address:** 9 (Radar Systems)
- **Subaddress:** 2 (SAR Radar)

**Simulation Capabilities:**
- **Data Format:** 8-bit grayscale imagery (numpy.uint8)
- **Geo-Referencing:** Corner point coordinate system
- **Noise Simulation:** Gaussian noise overlay (mean=0, σ=10)
- **Mode-Specific Patterns:** Different patterns per imaging mode
- **Metadata Integration:** Complete geo-spatial reference data

### Key Limitations

**What This System IS:**
- Basic pattern generator for testing display systems
- Mode switching demonstration platform
- Data structure and messaging example
- Development and testing tool

**What This System IS NOT:**
- Real SAR processing system
- Operational imaging radar
- Production-ready SAR capability
- Actual terrain mapping system

## 4.2 Interface Elements Identification

### SAR Radar Control Interface

[SCREENSHOT PLACEHOLDER: SAR Radar control interface with numbered callouts]
**Figure 4.1:** SAR Radar Control Interface
1. **System Selection Dropdown** - Choose SAR Radar from available systems
2. **Current Mode Indicator** - Displays active operational mode (STANDBY, STRIPMAP, SPOTLIGHT, SCANSAR)
3. **Available Modes List** - Shows all operational modes available for selection
4. **Mode Change Button** - Initiates mode transition to selected target mode
5. **Pattern Generation Status** - Shows when pattern generation is active
6. **Image Data Indicator** - Displays when image data has been generated
7. **System Status Display** - Real-time radar system health and processing status
8. **Configuration Access** - Pattern generation parameters and settings

### Mode Change Procedure Visualization

[SCREENSHOT PLACEHOLDER: Before mode change - STANDBY mode]
**Figure 4.2:** Before Mode Change - STANDBY Mode
1. **Current Mode: STANDBY** - System powered but not generating patterns
2. **Pattern Status: Inactive** - No pattern generation occurring
3. **System Ready Indicator** - Green status showing system ready for mode change
4. **Available Modes** - STRIPMAP, SPOTLIGHT, SCANSAR modes available
5. **Communication Active** - 1553B connection established and healthy

[SCREENSHOT PLACEHOLDER: During mode change to STRIPMAP]
**Figure 4.3:** During Mode Change - Transition to STRIPMAP
1. **Mode Change Status** - "Changing to STRIPMAP" message displayed
2. **Pattern Generation Preparing** - System preparing for pattern generation
3. **System Processing** - Radar system reconfiguring for STRIPMAP mode
4. **Communication Activity** - 1553B messages being exchanged
5. **Status Updates** - Real-time log messages showing transition steps

[SCREENSHOT PLACEHOLDER: After mode change - STRIPMAP mode with pattern generated]
**Figure 4.4:** After Mode Change - STRIPMAP Mode with Pattern Generated
1. **New Mode: STRIPMAP** - Mode indicator updated to show active mode
2. **Pattern Generated** - Linear pattern simulation completed
3. **Image Data Available** - 1024x1024 image data created
4. **System Health** - All indicators showing normal operation
5. **Known Limitation Note** - Reminder that this is basic simulation only

### Step-by-Step Mode Change Procedure

**Procedure: Changing SAR Radar to STRIPMAP Mode**

**Step 1: Access SAR Radar Controls**
1. Open the radar management system interface
2. Locate the SAR Radar section [See Figure 4.1, Item 1]
3. Verify current mode shows "STANDBY" [See Figure 4.2, Item 1]
4. Confirm system status indicators are green [See Figure 4.2, Item 3]

**Step 2: Initiate Mode Change to STRIPMAP**
1. Click on the mode selection dropdown [See Figure 4.1, Item 3]
2. Select "STRIPMAP" (Mode 30) from the available modes list
3. Click the "Change Mode" button [See Figure 4.1, Item 4]
4. Monitor the status display for transition confirmation [See Figure 4.3, Item 1]

**Step 3: Monitor Mode Transition**
1. Watch for "Mode change in progress" message [See Figure 4.3, Item 1]
2. Observe pattern generation preparation [See Figure 4.3, Item 2]
3. Monitor log output for detailed transition steps
4. Verify communication activity remains healthy [See Figure 4.3, Item 4]

**Step 4: Verify STRIPMAP Mode Operation**
1. Confirm mode indicator shows "STRIPMAP" [See Figure 4.4, Item 1]
2. Check for pattern generation completion [See Figure 4.4, Item 2]
3. Verify image data has been created [See Figure 4.4, Item 3]
4. Monitor system health indicators [See Figure 4.4, Item 4]

**Step 5: Understand System Limitations**
1. Note that this is basic pattern simulation only [See Figure 4.4, Item 5]
2. Understand that no real SAR processing occurs
3. Display integration active — imagery routed to MFD via bridge
4. Use log monitoring to verify pattern generation

### SAR Pattern Generation Visualization

[DIAGRAM PLACEHOLDER: SAR pattern generation flow]
**Figure 4.5:** SAR Pattern Generation Flow
1. **Mode Change Request** - User initiates mode change via interface
2. **Pattern Algorithm Selection** - System selects appropriate pattern generator
3. **Image Buffer Creation** - 1024x1024 pixel array allocated
4. **Pattern Generation** - Mode-specific pattern created (lines, circles, bands)
5. **Noise Addition** - Gaussian noise overlay applied
6. **Geo-Referencing** - Corner points and metadata added
7. **Data Object Creation** - Complete SAR image data structure created
8. **Display Integration** - ✅ Active — imagery routed via radar-to-display bridge

### Pattern Type Comparison

[SCREENSHOT PLACEHOLDER: STRIPMAP pattern example]
**Figure 4.6:** STRIPMAP Pattern Example
1. **Vertical Lines** - 5 random vertical lines across image
2. **Line Width** - 10 pixels wide (10 meters at 1m resolution)
3. **Line Intensity** - 200/255 grayscale value
4. **Background** - Zero intensity with Gaussian noise
5. **Coverage** - 10km x 10km simulated area

[SCREENSHOT PLACEHOLDER: SPOTLIGHT pattern example]
**Figure 4.7:** SPOTLIGHT Pattern Example
1. **Circular Area** - Single circle centered in image
2. **Circle Radius** - 256 pixels (2.56 km at 1m resolution)
3. **Circle Intensity** - 200/255 grayscale value
4. **Background** - Zero intensity with Gaussian noise
5. **Focus Area** - Simulated high-resolution spotlight area

[SCREENSHOT PLACEHOLDER: SCANSAR pattern example]
**Figure 4.8:** SCANSAR Pattern Example
1. **Horizontal Bands** - 3 distinct swaths across image
2. **Band Height** - ~341 pixels each (3.3 km)
3. **Random Patterns** - Different intensity per swath (100-200)
4. **Swath Separation** - Clear boundaries between bands
5. **Wide Coverage** - Simulated wide-area mapping

## 4.3 Operational Modes and Capabilities

### Universal Base Modes ✅ **OPERATIONAL**

**STANDBY (Mode 0)**
- System powered but not generating patterns
- No image generation or processing
- Minimal power consumption
- Ready for rapid mode transition

**NORMAL (Mode 1)**
- Standard operational mode
- Basic pattern generation capabilities
- Default mode for routine operations

**DEGRADED (Mode 2)**
- Reduced capability operation
- Limited pattern generation
- Used when system constraints exist

**TEST (Mode 3)**
- Built-in test mode
- System self-diagnostics
- Pattern generation verification

**MAINTENANCE (Mode 4)**
- Maintenance and calibration mode
- System configuration access
- Diagnostic data collection

### SAR-Specific Modes

**STRIPMAP (Mode 30)** ⚠️ **BASIC SIMULATION**
- Generates simple linear pattern features
- 5 random vertical lines across image
- Line width: 10 pixels, intensity: 200/255
- **Limitation:** Not actual stripmap SAR processing

```
Procedure: Switching to Stripmap Mode
1. Access radar control interface
2. Select SAR Radar system
3. Choose STRIPMAP mode (Mode 30)
4. System generates linear pattern simulation
5. Pattern available for testing (not displayed)
```

**SPOTLIGHT (Mode 31)** ⚠️ **BASIC SIMULATION**
- Generates simple circular pattern
- Circle centered at image center (512, 512)
- Radius: 256 pixels, intensity: 200/255
- **Limitation:** Not actual spotlight SAR processing

**SCANSAR (Mode 32)** ⚠️ **BASIC SIMULATION**
- Generates 3 horizontal bands with random patterns
- Each band: ~341 pixels high
- Random intensity 100-200 per band
- **Limitation:** Not actual ScanSAR processing

**INTERFEROMETRIC (Mode 33)** ❌ **NOT IMPLEMENTED** (planned)
- Mode exists in enum but no processing
- Returns empty image data
- No elevation mapping capability
- **Status:** Placeholder only

**DOPPLER_BEAM (Mode 34)** ❌ **NOT IMPLEMENTED** (planned)
- Mode exists in enum but no processing
- Returns empty image data
- No moving target indication
- **Status:** Placeholder only

## 4.4 Pattern Generation Details

### Stripmap Pattern Generation ⚠️ **BASIC SIMULATION**

**Algorithm Implementation:**
```python
def _generate_stripmap_pattern():
    image = np.zeros((1024, 1024), dtype=np.uint8)
    # Generate 5 random vertical lines
    for i in range(5):
        x = np.random.randint(0, 1024)
        image[:, x:x+10] = 200  # 10-pixel wide lines
    # Add Gaussian noise
    noise = np.random.normal(0, 10, image.shape)
    return np.clip(image + noise, 0, 255).astype(np.uint8)
```

**Pattern Characteristics:**
- **Feature Type:** Vertical lines (simulating linear infrastructure)
- **Feature Count:** 5 random lines per image
- **Feature Width:** 10 pixels (10 meters at 1m resolution)
- **Feature Intensity:** 200/255 grayscale
- **Background:** Zero intensity with noise

### Spotlight Pattern Generation ⚠️ **BASIC SIMULATION**

**Algorithm Implementation:**
```python
def _generate_spotlight_pattern():
    image = np.zeros((1024, 1024), dtype=np.uint8)
    center_x, center_y = 512, 512
    radius = 256
    # Create circular mask
    y, x = np.ogrid[-center_y:1024-center_y, -center_x:1024-center_x]
    mask = x*x + y*y <= radius*radius
    image[mask] = 200
    # Add Gaussian noise
    noise = np.random.normal(0, 10, image.shape)
    return np.clip(image + noise, 0, 255).astype(np.uint8)
```

**Pattern Characteristics:**
- **Feature Type:** Circular area (simulating focused target area)
- **Center Point:** Image center (512, 512)
- **Radius:** 256 pixels (2 kilometers at 1m resolution)
- **Feature Intensity:** 200/255 grayscale
- **Background:** Zero intensity with noise

### ScanSAR Pattern Generation ⚠️ **BASIC SIMULATION**

**Algorithm Implementation:**
```python
def _generate_scansar_pattern():
    image = np.zeros((1024, 1024), dtype=np.uint8)
    # Create 3 horizontal swaths
    for i in range(3):
        start_y = i * 341
        end_y = (i + 1) * 341
        # Random pattern per swath
        swath_pattern = np.random.randint(100, 200, (end_y-start_y, 1024))
        image[start_y:end_y, :] = swath_pattern
    # Add Gaussian noise
    noise = np.random.normal(0, 10, image.shape)
    return np.clip(image + noise, 0, 255).astype(np.uint8)
```

**Pattern Characteristics:**
- **Swath Count:** 3 horizontal bands
- **Swath Height:** ~341 pixels each (3.3 km)
- **Pattern Type:** Random intensity per swath
- **Intensity Range:** 100-200 grayscale per swath
- **Background:** Swath-based random patterns

## 4.5 Data Structure and Geo-Referencing

### Image Data Structure ✅ **OPERATIONAL**

**Data Format:**
```python
SAR Image Data Structure:
{
    'image_data': numpy.ndarray(1024, 1024, dtype=uint8),
    'resolution': 1.0,  # meters per pixel
    'geo_reference': {
        'corner_points': [(-5000, -5000), (-5000, 5000),
                          (5000, 5000), (5000, -5000)],
        'image_width': 1024,
        'image_height': 1024
    },
    'timestamp': float,  # Image generation time
    'mode': str  # Current SAR mode
}
```

**Geo-Referencing System ✅ OPERATIONAL:**
- **Coordinate System:** Local Cartesian coordinates
- **Origin:** Image center corresponds to (0, 0)
- **Coverage:** ±5000 meters from center
- **Corner Points:** Four-point geo-reference system
- **Pixel Mapping:** Direct 1:1 meter-to-pixel mapping

### Message Integration ✅ **OPERATIONAL**

**Message Flow:**
1. **Mode Change Request:** Received and processed
2. **Pattern Generation:** Mode-specific pattern created
3. **Data Packaging:** Image data formatted with metadata
4. **Message Creation:** SAR imagery message object created
5. **Completion Notification:** Mode change completion sent
6. **Data Transmission:** ✅ **OPERATIONAL** — push_sar_data() to display coordinator

## 4.6 System Limitations and Development Status

### Current Limitations

**Processing Limitations:**
- **No Real SAR Processing:** Only basic pattern generation
- **No Actual Radar Data:** Patterns are mathematically generated
- **No Range Processing:** No actual radar signal processing
- **No Azimuth Processing:** No synthetic aperture formation
- **No Focusing Algorithms:** No SAR image focusing

**Operational Limitations:**
- **Display Integration:** ✅ Imagery routed via `push_sar_data()` to display coordinator
- **No Real-Time Operation:** Patterns generated on-demand only
- **No Terrain Interaction:** Patterns don't reflect actual terrain
- **No Mission Planning:** No integration with flight planning systems

### Development Roadmap

**Phase 1:** ❌ **NOT PLANNED**
- Real SAR signal processing algorithms
- Actual radar data integration
- Range and azimuth processing

**Phase 2:** ❌ **NOT PLANNED**
- Display system integration
- Real-time processing capability
- Terrain database integration

**Phase 3:** ❌ **NOT PLANNED**
- Advanced SAR modes (interferometry, polarimetry)
- Automatic target recognition
- Change detection algorithms

### Intended Use Cases

**Current Valid Uses:**
- **Display System Testing:** Test image data routing and display
- **Message System Testing:** Verify SAR message handling
- **Mode Switching Testing:** Test radar mode change procedures
- **Data Structure Validation:** Verify geo-referencing and metadata

**Invalid Use Cases:**
- **Operational SAR Imaging:** System cannot provide real SAR images
- **Navigation:** Patterns do not represent actual terrain
- **Intelligence Gathering:** No real reconnaissance capability
- **Mission Planning:** No actual ground truth data

## 4.7 SAR Radar Troubleshooting

### Common Issues and Solutions

#### Issue 1: No Pattern Generation

**Symptoms:**
- Mode changes successful but no image data generated
- Empty or zero-filled image arrays returned
- Error messages in SAR radar logs

**Root Cause:**
- System in STANDBY mode (no pattern generation)
- Invalid mode selection (INTERFEROMETRIC or DOPPLER_BEAM)
- Memory allocation failures

**Solution:**
1. Verify radar is not in STANDBY mode
2. Use only implemented modes (STRIPMAP, SPOTLIGHT, SCANSAR)
3. Check system memory availability
4. Monitor logs for specific error messages

#### Issue 2: Pattern Data Not Available ❌ **EXPECTED BEHAVIOR**

**Symptoms:**
- Patterns generated but not visible anywhere
- No display of SAR imagery
- Data seems to disappear after generation

**Root Cause:**
- Display integration: ✅ operational via bridge
- This is expected behavior, not a bug

**Current Workaround:**
1. Monitor SAR radar processing in system logs:
   ```
   tail -f FMOFP/logs/DEBUG_*.log | grep SAR_RADAR
   ```
2. Verify pattern generation completion in logs
3. Use system health monitoring for radar status
4. **Note:** Patterns are generated but not displayed

#### Issue 3: Incorrect Pattern Types

**Symptoms:**
- Expected pattern doesn't match mode
- Random or unexpected pattern generation
- Inconsistent pattern characteristics

**Troubleshooting Steps:**
1. Verify correct mode selection
2. Check mode change completion in logs
3. Ensure mode is not INTERFEROMETRIC or DOPPLER_BEAM
4. Restart system if mode switching appears stuck

### Diagnostic Procedures

#### System Health Check ✅ **OPERATIONAL**

**Health Monitoring Parameters:**
- **Pattern Generation Status:** Current processing state
- **Mode Status:** Current operational mode
- **Memory Usage:** Image buffer utilization
- **Processing Performance:** Generation time metrics

**Health Check Commands:**
```python
# Check SAR radar status
status = sar_radar.get_status()
print(f"Mode: {status['mode']}")
print(f"Running: {status['running']}")
print(f"Healthy: {status['healthy']}")
print(f"Image Dimensions: {status['image_dimensions']}")
print(f"Resolution: {status['resolution']} m/pixel")
```

#### Performance Monitoring ⚠️ **LIMITED**

**Available Metrics:**
- **Pattern Generation Time:** Typically < 0.1 seconds
- **Mode Change Time:** < 2 seconds
- **Memory Utilization:** Basic monitoring only
- **Error Rate:** Basic error counting

**Monitoring Commands:**
```bash
# Monitor pattern generation
grep "imagery.*generated" FMOFP/logs/DEBUG_*.log | tail -10

# Check mode changes
grep "SAR.*mode.*changed" FMOFP/logs/DEBUG_*.log | tail -10
```

### Configuration Verification

#### Basic Configuration Check ✅ **OPERATIONAL**

**Key Parameters:**
- Image dimensions: 1024×1024 pixels ✅
- Resolution: 1.0 meters per pixel ✅
- Coverage area: ±5000 meters ✅
- Corner points: [(-5000,-5000), (-5000,5000), (5000,5000), (5000,-5000)] ✅

#### Mode Verification ✅ **OPERATIONAL**

**Implemented Modes:**
- STRIPMAP (30): ✅ Pattern generation works
- SPOTLIGHT (31): ✅ Pattern generation works
- SCANSAR (32): ✅ Pattern generation works

**Non-Implemented Modes:**
- INTERFEROMETRIC (33): ❌ Returns empty data
- DOPPLER_BEAM (34): ❌ Returns empty data

---

**Navigation:** [← Targeting Radar System](03_Targeting_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [TFR Radar System →](05_TFR_Radar_System.md)

**Related Files:**
- → [Communication & Messaging](11_Communication_Messaging.md) - 1553B protocol details
- → [Troubleshooting & Diagnostics](13_Troubleshooting_Diagnostics.md) - System-wide troubleshooting
- → [Technical Reference](14_Technical_Reference.md) - Message types and configuration

---

*File: 04_SAR_Radar_System.md*
*Last Updated: December 2024*
*Next Review: March 2025*

**IMPORTANT NOTICE:** This system provides basic pattern simulation only. It does not perform actual SAR processing and is not suitable for operational use. Use only for development and testing purposes.
