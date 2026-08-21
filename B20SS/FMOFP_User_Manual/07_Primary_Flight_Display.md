# 7. Primary Flight Display (PFD)

**Navigation:** [← AEWC Radar System](06_AEWC_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [Multi-Function Display →](08_Multi_Function_Display.md)

---

## 7.1 PFD Overview

### System Status ✅ **OPERATIONAL** (Advanced Flight Display System)

The Primary Flight Display (PFD) provides comprehensive flight information in a sophisticated glass cockpit format with real-time integration to the Flight Management System (FMS). The PFD features advanced visual effects, multiple display themes, and tactical flight envelope monitoring capabilities.

**Current Operational Status:**
- **Flight Data Integration:** ✅ **OPERATIONAL** - Real-time FMS data at 20Hz update rate
- **Attitude Display:** ✅ **OPERATIONAL** - Artificial horizon with enhanced pitch ladder
- **Flight Instruments:** ✅ **OPERATIONAL** - Altitude, airspeed, heading tapes and indicators
- **Tactical Indicators:** ✅ **OPERATIONAL** - G-force, AOA, envelope warnings
- **Visual Effects:** ✅ **OPERATIONAL** - Enhanced themes with gradients and glow effects
- **Mode Indicators:** ✅ **OPERATIONAL** - Flight mode display with color coding

### Technical Specifications

**Display Parameters:**
- **Update Rate:** 20 Hz (50ms refresh interval)
- **Data Source:** Flight Management System (FMS)
- **Display Types:** Standard, Holographic variants available
- **Theme Support:** Classic, Modern, Night themes
- **Resolution:** Adaptive to display size
- **Rendering:** PyQt6 with hardware acceleration

**Flight Data Integration:**
- **Attitude Data:** Roll, pitch from FMS attitude system
- **Velocity Data:** Airspeed, vertical speed, Mach number
- **Navigation Data:** Heading, altitude from navigation system
- **Tactical Data:** G-force, angle of attack, energy state
- **Status Data:** Flight mode, warnings, envelope limits

### Key Capabilities

**Primary Flight Instruments:**
- Real-time attitude indicator with artificial horizon
- Scrolling altitude tape with target altitude indication
- Scrolling airspeed tape with Mach number display
- Heading indicator with compass rose
- Vertical speed indicator with climb/descent arrows

**Advanced Features:**
- ✅ **OPERATIONAL:** Enhanced visual effects with gradients and glow
- ✅ **OPERATIONAL:** Flight envelope warnings with blinking alerts
- ✅ **OPERATIONAL:** Tactical indicators (G-force, AOA) with threshold warnings
- ✅ **OPERATIONAL:** Flight mode indicators with emergency mode blinking
- ✅ **OPERATIONAL:** Target value indicators for autopilot integration

## 7.2 Display Element Identification

### Primary Flight Display Layout

[SCREENSHOT PLACEHOLDER: PFD main display with numbered callouts]
**Figure 7.1:** Primary Flight Display - Main Elements
1. **Attitude Indicator** - Artificial horizon with pitch ladder (center)
2. **Airspeed Tape** - Scrolling airspeed display (left side)
3. **Altitude Tape** - Scrolling altitude display (right side)
4. **Heading Indicator** - Compass display (top center)
5. **Flight Mode Indicator** - Current flight mode (bottom center)
6. **G-Force Indicator** - Tactical G-force display (bottom left)
7. **AOA Indicator** - Angle of attack display (bottom left)
8. **Envelope Warnings** - Critical flight envelope alerts (top center)

### Display Theme Comparison

[SCREENSHOT PLACEHOLDER: Classic theme PFD]
**Figure 7.2:** Classic Theme Display
1. **Standard Elements** - Basic rectangular display elements
2. **Basic Colors** - Standard HUD color scheme
3. **Simple Lines** - Basic line rendering without effects
4. **Traditional Layout** - Classic glass cockpit appearance
5. **High Contrast** - Clear visibility in all conditions

[SCREENSHOT PLACEHOLDER: Modern theme PFD]
**Figure 7.3:** Modern Theme Display
1. **Enhanced Elements** - Gradient effects and rounded corners
2. **Glow Effects** - Enhanced text and element rendering
3. **Advanced Graphics** - Sophisticated visual effects
4. **Depth Perception** - 3D-style visual enhancements
5. **Modern Styling** - Contemporary glass cockpit appearance

### Display Configuration Procedure

**Procedure: Changing Display Theme**

**Step 1: Access Display Settings**
1. Right-click on the PFD display area
2. Select "Display Configuration" from context menu
3. Choose "Theme Settings" option
4. Review available theme options

**Step 2: Select Theme**
1. Choose from available themes [See Figures 7.2-7.3]:
   - **Classic Theme** - Traditional glass cockpit appearance
   - **Modern Theme** - Enhanced visual effects and gradients
   - **Night Theme** - Optimized for low-light operations
2. Preview changes in real-time
3. Apply new theme settings

**Step 3: Verify Changes**
1. Check visual effects activation
2. Confirm all elements display correctly
3. Test display responsiveness
4. Verify readability in current lighting conditions

### Flight Data Integration Visualization

[DIAGRAM PLACEHOLDER: PFD data flow from FMS]
**Figure 7.4:** PFD Data Integration Flow
1. **FMS Flight Data** - Real-time flight parameters at 20Hz
2. **Attitude System** - Roll and pitch data for artificial horizon
3. **Velocity System** - Airspeed, vertical speed, Mach number
4. **Navigation System** - Heading and altitude information
5. **Tactical System** - G-force, AOA, envelope monitoring
6. **Status System** - Flight mode and warning information
7. **PFD Rendering** - Real-time display update and visual effects

### Step-by-Step Display Operations

**Procedure: Understanding PFD Elements**

**Step 1: Attitude Indicator Reading**
1. Locate the artificial horizon in center of display [See Figure 7.1, Item 1]
2. Observe blue sky (above) and brown ground (below) sections
3. Note aircraft symbol (fixed) and horizon line (moving)
4. Read pitch ladder markings for precise pitch angle
5. Observe roll indication from horizon line angle

**Step 2: Airspeed and Altitude Monitoring**
1. Check current airspeed in left tape [See Figure 7.1, Item 2]
2. Note Mach number display below airspeed
3. Monitor altitude in right tape [See Figure 7.1, Item 3]
4. Observe vertical speed arrow (green=climb, orange=descent)
5. Check for target altitude/airspeed indicators (green triangles)

**Step 3: Navigation Information**
1. Read current heading from top indicator [See Figure 7.1, Item 4]
2. Note compass tick marks and cardinal directions
3. Observe heading changes during turns
4. Check for navigation accuracy

**Step 4: Tactical Information Monitoring**
1. Monitor G-force reading [See Figure 7.1, Item 6]
2. Check AOA (Angle of Attack) value [See Figure 7.1, Item 7]
3. Watch for color changes indicating threshold warnings:
   - **Green/Cyan** - Normal operations
   - **Yellow** - Elevated values
   - **Orange** - Warning levels
   - **Red** - Critical levels

**Step 5: Flight Mode and Warning Awareness**
1. Check current flight mode [See Figure 7.1, Item 5]
2. Note mode-specific color coding:
   - **NORMAL** - Standard HUD color
   - **COMBAT** - Critical red with glow
   - **STEALTH** - Stealth blue with glow
   - **EMERGENCY** - Blinking orange/red
3. Monitor for envelope warnings [See Figure 7.1, Item 8]
4. Respond to any blinking critical alerts

## 7.3 Attitude Indicator and Pitch Ladder

### Overview ✅ **OPERATIONAL**

The attitude indicator provides real-time aircraft orientation information with a sophisticated artificial horizon display, enhanced pitch ladder, and advanced visual effects.

**Attitude Display Features:**
- Real-time roll and pitch from FMS attitude system
- Artificial horizon with sky/ground color differentiation
- Enhanced pitch ladder with 5-degree increments
- Perspective grid lines for depth perception
- Gradient sky and ground effects

### Attitude Indicator Components ✅ **OPERATIONAL**

**Artificial Horizon:**
```
Sky Section:
- Gradient blue coloring (lighter at horizon)
- Upper sky darkening for realism
- Enhanced with glow effects in modern themes

Ground Section:
- Gradient brown coloring (darker at bottom)
- Realistic ground texture representation
- Enhanced depth effects
```

**Pitch Ladder System:**
- **Major Lines (±10°, ±20°):** Enhanced with glow effects, wider display
- **Minor Lines (±5°, ±15°):** Standard width, clear visibility
- **Pitch Values:** Displayed on both sides of ladder
- **Range:** ±20 degrees visible range
- **Spacing:** 4 pixels per degree (adaptive to display size)

### Enhanced Visual Effects ✅ **OPERATIONAL**

**Gradient Effects (Modern/Night Themes):**
- Sky gradient from darker blue (top) to lighter blue (horizon)
- Ground gradient from standard brown (horizon) to darker brown (bottom)
- Horizon line with glow effect for enhanced visibility
- Perspective grid lines for 3D depth perception

**Pitch Ladder Enhancements:**
- Major pitch lines with glow effects
- Enhanced text rendering with anti-aliasing
- Depth-based color variations
- Smooth animation during attitude changes

### Attitude Data Processing ✅ **OPERATIONAL**

**Real-Time Updates:**
```
Data Flow:
1. FMS Attitude System → Flight Data
2. PFD Update Timer (20Hz) → Data Retrieval
3. Attitude Processing → Roll/Pitch Extraction
4. Display Rendering → Visual Update
```

**Attitude Parameters:**
- **Roll Range:** ±180 degrees (full range)
- **Pitch Range:** ±90 degrees (displayed ±20 degrees)
- **Update Rate:** 20 Hz from FMS
- **Accuracy:** High precision from FMS integration
- **Smoothing:** Real-time with no artificial lag

## 7.4 Altitude and Airspeed Tapes

### Overview ✅ **OPERATIONAL**

The PFD features scrolling altitude and airspeed tapes that provide precise flight parameter information with target indicators, enhanced visual effects, and real-time FMS integration.

### Altitude Tape System ✅ **OPERATIONAL**

**Tape Configuration:**
- **Position:** Right side of display
- **Current Altitude:** Highlighted in center box with enhanced background
- **Scale:** 100-foot increments with major ticks every 200 feet
- **Range:** ±500 feet visible range
- **Format:** 5-digit display (e.g., "30000")

**Enhanced Features:**
- **Target Altitude Indicator:** Green triangle pointing to target altitude
- **Vertical Speed Arrow:** Color-coded climb (green) / descent (orange) indicator
- **Gradient Background:** Enhanced box with rounded corners (modern themes)
- **Glow Effects:** Current altitude with glow text rendering

**Vertical Speed Integration:**
```
Vertical Speed Display:
- Threshold: >50 fpm for display activation
- Range: ±2000 fpm normalized display
- Colors: Green (climb), Orange (descent)
- Position: Left of altitude tape
- Format: Absolute value display
```

### Airspeed Tape System ✅ **OPERATIONAL**

**Tape Configuration:**
- **Position:** Left side of display
- **Current Airspeed:** Highlighted in center box with enhanced background
- **Scale:** 10-knot increments with major ticks every 20 knots
- **Range:** ±50 knots visible range
- **Format:** 3-digit display (e.g., "450")

**Enhanced Features:**
- **Mach Number Display:** Below airspeed box (format: "M0.750")
- **Target Airspeed Indicator:** Green triangle pointing to target airspeed
- **Gradient Background:** Enhanced box with rounded corners (modern themes)
- **Glow Effects:** Current airspeed with glow text rendering

**Airspeed Data Integration:**
```
Data Sources:
- Airspeed: FMS velocity system (knots)
- Mach Number: FMS velocity system (3 decimal places)
- Target Airspeed: FMS control system
- Vertical Speed: FMS velocity system (fpm)
```

### Tape Visual Enhancements ✅ **OPERATIONAL**

**Modern Theme Effects:**
- Gradient backgrounds for current value boxes
- Glow effects for current values
- Enhanced tick mark rendering
- Target indicators with smooth animation
- Rounded corner styling

**Classic Theme Fallback:**
- Standard rectangular boxes
- Basic line rendering
- Standard text display
- Full functionality maintained

## 7.5 Heading Indicator

### Overview ✅ **OPERATIONAL**

The heading indicator provides precise aircraft heading information with an enhanced compass display, cardinal point markers, and advanced visual effects.

### Heading Display System ✅ **OPERATIONAL**

**Indicator Configuration:**
- **Position:** Top center of display
- **Current Heading:** Highlighted in center box
- **Scale:** 10-degree increments with major ticks every 20 degrees
- **Range:** ±30 degrees visible range
- **Format:** 3-digit display with degree symbol (e.g., "045°")

**Enhanced Features:**
- **Compass Ticks:** Major and minor tick marks with enhanced rendering
- **Cardinal Points:** N, E, S, W labels with glow effects
- **Gradient Background:** Enhanced box with rounded corners (modern themes)
- **Compass Arc:** Partial arc display for futuristic appearance

### Compass Rose Integration ✅ **OPERATIONAL**

**Visual Elements:**
```
Compass Components:
- Center Box: Current heading with enhanced background
- Tick Marks: 10° (minor) and 20° (major) increments
- Cardinal Labels: N, E, S, W positioned at 1.2x radius
- Compass Arc: 120-degree arc for enhanced visual appeal
```

**Enhanced Visual Effects:**
- **Glow Text:** Current heading with glow rendering
- **Enhanced Ticks:** Major ticks with glow effects
- **Cardinal Points:** Enhanced text with glow effects
- **Compass Arc:** Partial arc with enhanced line rendering

### Heading Data Processing ✅ **OPERATIONAL**

**Real-Time Updates:**
```
Data Flow:
1. FMS Navigation System → Heading Data
2. PFD Update Timer (20Hz) → Data Retrieval
3. Heading Processing → Degree Conversion
4. Display Rendering → Visual Update
```

**Heading Parameters:**
- **Range:** 0-359 degrees
- **Accuracy:** 1-degree precision
- **Update Rate:** 20 Hz from FMS
- **Format:** True heading (magnetic variation applied)

## 7.6 Flight Mode Indicators

### Overview ✅ **OPERATIONAL**

The flight mode indicator displays the current FMS operational mode with color-coded status indication, emergency mode blinking, and enhanced visual effects for critical mode awareness.

### Mode Display System ✅ **OPERATIONAL**

**Indicator Configuration:**
- **Position:** Bottom center of display
- **Mode Display:** Current FMS mode in highlighted box
- **Color Coding:** Mode-specific colors for immediate recognition
- **Enhanced Effects:** Glow effects for critical modes
- **Emergency Blinking:** 2Hz blink rate for emergency modes

**Supported Flight Modes:**
```
Mode Types and Colors:
- NORMAL: Standard HUD color (green/cyan)
- COMBAT: Critical red with glow effects
- STEALTH: Stealth blue with glow effects
- EMERGENCY: Warning orange with critical red blinking
- DEGRADED: Standard HUD color
- MAINTENANCE: Standard HUD color
```

### Mode Color Coding ✅ **OPERATIONAL**

**Color Scheme:**
- **NORMAL Mode:** Standard HUD color (operational)
- **COMBAT Mode:** Critical red with glow effects (high alert)
- **STEALTH Mode:** Stealth blue with glow effects (special operations)
- **EMERGENCY Mode:** Alternating orange/red with 2Hz blink (critical alert)
- **Other Modes:** Standard HUD color (normal operations)

**Visual Enhancement:**
- **Gradient Background:** Enhanced box with rounded corners
- **Glow Effects:** Critical modes with glow text rendering
- **Bold Font:** 10-point Arial Bold for visibility
- **Emergency Blinking:** Time-based color alternation

### Mode Integration ✅ **OPERATIONAL**

**FMS Integration:**
```
Data Flow:
1. FMS Status System → Mode Data
2. PFD Update Timer (20Hz) → Mode Retrieval
3. Mode Processing → Color Assignment
4. Display Rendering → Enhanced Visual Update
```

**Mode Parameters:**
- **Source:** FMS status system
- **Update Rate:** 20 Hz real-time
- **Display Format:** Text string (e.g., "COMBAT")
- **Color Assignment:** Dynamic based on mode type

## 7.7 Tactical Indicators (G-Force, AOA)

### Overview ✅ **OPERATIONAL**

The tactical indicators provide critical flight envelope information including G-force and angle of attack (AOA) with threshold-based color warnings and enhanced visual effects for pilot awareness.

### G-Force Indicator ✅ **OPERATIONAL**

**Display Configuration:**
- **Position:** Bottom left area of display
- **Format:** "G-FORCE: X.X" with 1 decimal place precision
- **Color Coding:** Threshold-based warning system
- **Background:** Clear background to prevent overlap
- **Update Rate:** 20 Hz from FMS tactical system

**G-Force Thresholds:**
```
Threshold System:
- Normal (≤2.0G): Standard HUD color
- Elevated (2.1-6.0G): Yellow warning color
- Warning (6.1-8.0G): Orange warning color
- Critical (>8.0G): Red critical color
```

**G-Force Data Integration:**
```
Data Source: FMS Tactical System
- Range: 0.0 - 15.0+ G
- Precision: 0.1 G increments
- Update Rate: 20 Hz real-time
- Calculation: Total G-force magnitude
```

### Angle of Attack (AOA) Indicator ✅ **OPERATIONAL**

**Display Configuration:**
- **Position:** Below G-force indicator
- **Format:** "AOA: XX.X°" with 1 decimal place precision
- **Color Coding:** Threshold-based warning system
- **Background:** Clear background to prevent overlap
- **Update Rate:** 20 Hz from FMS tactical system

**AOA Thresholds:**
```
Threshold System:
- Normal (≤10.0°): Standard HUD color
- Elevated (10.1-18.0°): Yellow warning color
- Warning (18.1-22.0°): Orange warning color
- Critical (>22.0°): Red critical color
```

**AOA Data Integration:**
```
Data Source: FMS Tactical System
- Range: -30.0° to +45.0°
- Precision: 0.1° increments
- Update Rate: 20 Hz real-time
- Type: Angle of attack in degrees
```

### Tactical Display Enhancement ✅ **OPERATIONAL**

**Visual Features:**
- **Clear Backgrounds:** Semi-transparent black backgrounds prevent text overlap
- **Color-Coded Values:** Threshold-based color system for immediate recognition
- **Compact Layout:** Efficient use of display space
- **Real-Time Updates:** Smooth value transitions

**Threshold Warning System:**
```
Warning Logic:
1. Continuous monitoring of tactical values
2. Real-time threshold comparison
3. Dynamic color assignment
4. Immediate visual feedback
```

## 7.8 Envelope Warnings

### Overview ✅ **OPERATIONAL**

The envelope warning system provides critical flight envelope limit alerts with blinking visual indicators, color-coded warnings, and real-time monitoring of flight parameters to ensure safe aircraft operation.

### Warning System ✅ **OPERATIONAL**

**Warning Display:**
- **Position:** Upper center area of display
- **Format:** Bold text with blinking effects
- **Blink Rate:** 2 Hz (0.5-second intervals)
- **Color Alternation:** Critical red and warning orange
- **Font:** 12-point Arial Bold for maximum visibility

**Supported Warning Types:**
```
Envelope Warnings:
- BANK_ANGLE: Excessive bank angle detected
- PITCH_ANGLE: Excessive pitch angle detected
- ROLL_RATE: Excessive roll rate detected
- PITCH_RATE: Excessive pitch rate detected
- YAW_RATE: Excessive yaw rate detected
```

### Warning Visual Effects ✅ **OPERATIONAL**

**Blinking System:**
- **Timing:** 2 Hz alternation (500ms intervals)
- **Colors:** Critical red ↔ Warning orange
- **Text Format:** Uppercase with underscores converted to spaces
- **Positioning:** Centered with 30-pixel spacing between warnings

**Warning Priority:**
- All active warnings displayed simultaneously
- Vertical stacking with consistent spacing
- Bold font for maximum visibility
- Time-based color alternation for attention

### Envelope Monitoring Integration ✅ **OPERATIONAL**

**Data Sources:**
```
FMS Control System:
- Tactical Status → Envelope Warnings
- Profile Limits → Maximum Values
- Real-Time Monitoring → Warning Generation
```

**Warning Parameters:**
- **Source:** FMS tactical status system
- **Update Rate:** 20 Hz real-time monitoring
- **Warning Logic:** Threshold-based limit detection
- **Display Logic:** Immediate visual alert activation

**Warning Lifecycle:**
```
Warning Process:
1. FMS monitors flight parameters
2. Threshold exceedance detection
3. Warning list generation
4. PFD warning display activation
5. Continuous blinking until condition clears
```

## 7.9 PFD Configuration and Troubleshooting

### Display Configuration ✅ **OPERATIONAL**

**Theme Selection:**
- **Classic Theme:** Standard display with basic visual effects
- **Modern Theme:** Enhanced gradients, glow effects, rounded corners
- **Night Theme:** Optimized for low-light operations

**Display Type Options:**
- **Standard PFD:** Traditional glass cockpit layout
- **Holographic PFD:** Advanced 3D effects with depth rendering

### Configuration Parameters

**Update Settings:**
```
Timer Configuration:
- Update Rate: 50ms (20 Hz)
- Data Source: Flight Management System
- Thread Safety: Mutex-protected data access
- Error Handling: Graceful degradation on FMS disconnect
```

**Visual Settings:**
```
Theme Parameters:
- use_gradients: Enable/disable gradient effects
- corner_radius: Rounded corner radius (0.0 = square)
- glow_effects: Enable/disable glow rendering
- enhanced_text: Enable/disable enhanced text rendering
```

### Common Issues and Solutions

#### Issue 1: PFD Not Updating

**Symptoms:**
- Static display values
- No real-time updates
- Frozen attitude indicator

**Troubleshooting Steps:**
1. Verify FMS connection status
2. Check update timer operation:
   ```python
   # Check if update timer is running
   if self.update_timer and self.update_timer.isActive():
       print("Timer active")
   ```
3. Verify FMS data availability
4. Restart PFD display if necessary

#### Issue 2: Visual Effects Not Working

**Symptoms:**
- No gradient effects
- Missing glow effects
- Standard appearance only

**Solution:**
1. Check theme configuration:
   ```python
   # Verify theme manager settings
   use_gradients = self._theme_manager.get_style_param("use_gradients", False)
   ```
2. Ensure modern or night theme is selected
3. Verify graphics hardware acceleration

#### Issue 3: Attitude Indicator Errors

**Symptoms:**
- Incorrect horizon display
- Pitch ladder misalignment
- Roll indication errors

**Troubleshooting Steps:**
1. Verify FMS attitude data:
   ```python
   # Check attitude data availability
   flight_data = self.fms.get_flight_data()
   attitude = flight_data.get('attitude', {})
   ```
2. Check coordinate system alignment
3. Verify pitch ladder calculation parameters

### Performance Optimization

**Rendering Performance:**
- Enable hardware acceleration when available
- Use efficient painting techniques
- Minimize unnecessary redraws
- Optimize gradient and glow effect rendering

**Memory Management:**
- Proper cleanup of resources
- Timer management
- Thread-safe data access
- Efficient data structure usage

### Diagnostic Procedures

**System Health Check:**
```python
# PFD health verification
def check_pfd_health():
    # Verify FMS connection
    if not self.fms:
        return "FMS not connected"
    
    # Check update timer
    if not self.update_timer or not self.update_timer.isActive():
        return "Update timer not active"
    
    # Verify data flow
    flight_data = self.fms.get_flight_data()
    if not flight_data:
        return "No flight data available"
    
    return "PFD healthy"
```

**Performance Monitoring:**
```python
# Monitor update performance
def monitor_update_performance():
    start_time = time.time()
    self.update_flight_data()
    update_time = time.time() - start_time
    
    if update_time > 0.05:  # 50ms threshold
        logger.warning(f"Slow PFD update: {update_time:.3f}s")
```

---

**Navigation:** [← AEWC Radar System](06_AEWC_Radar_System.md) | [Table of Contents](00_Title_and_TOC.md) | [Multi-Function Display →](08_Multi_Function_Display.md)

**Related Files:**
- → [Multi-Function Display](08_Multi_Function_Display.md) - MFD system integration
- → [Holographic Display System](09_Holographic_Display_System.md) - Advanced display effects
- → [Flight Management Integration](10_Flight_Management_Integration.md) - FMS data sources

---

*File: 07_Primary_Flight_Display.md*  
*Last Updated: December 2024*  
*Next Review: March 2025*
