# 1. System Overview & Architecture

**Navigation:** [← Table of Contents](00_Title_and_TOC.md) | [Weather Radar System →](02_Weather_Radar_System.md)

---

## 1.1 Introduction to FMOFP

The Flight Management Operating Flight Program (FMOFP) is a comprehensive avionics system designed for advanced military aircraft operations. The system integrates multiple radar types, sophisticated display systems, and flight management capabilities through a robust MIL-STD-1553B communication architecture.

### Current Development Status

**IMPORTANT:** The FMOFP system is currently in active development (Version B20SS). While core functionality is operational, several features have known limitations:

- **Weather Radar:** ✅ **OPERATIONAL** radar processing, 🐛 **KNOWN ISSUES** with 1553B communication to displays
- **Other Radars:** ✅ **OPERATIONAL** radar processing, ✅ **OPERATIONAL** display integration (bridge connected)
- **Display Systems:** ✅ **OPERATIONAL** display rendering, ✅ **OPERATIONAL** live data integration
- **Flight Management:** ✅ **OPERATIONAL** core functionality

### Key System Capabilities

**Radar Systems:**
- **Weather Radar** - VIL analysis, precipitation detection, storm cell tracking
- **Targeting Radar** - Multi-target tracking and acquisition
- **Synthetic Aperture Radar (SAR)** - Ground mapping and imagery
- **Terrain Following Radar (TFR)** - Low-level flight operations
- **Airborne Early Warning and Control (AEWC)** - Surveillance operations

**Display Systems:**
- **Primary Flight Display (PFD)** - Real-time flight parameters and tactical indicators
- **Multi-Function Display (MFD)** - Radar integration and system monitoring
- **Holographic Display System** - Enhanced visual effects and 3D rendering

**Flight Management:**
- Real-time flight data integration with FMS
- Navigation and waypoint management
- Flight control system integration
- Tactical systems coordination

### System Integration Architecture

The FMOFP system operates through a layered integration model:

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │     PFD     │  │     MFD     │  │  Holographic HUD    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Radar Mgmt  │  │ Display Mgmt│  │   Flight Mgmt       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                 Communication Layer                         │
│              MIL-STD-1553B Protocol                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │Bus Controller│ │Remote Terms │  │  Message Routing    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Radar Data  │  │Display Data │  │   System Config     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 1.2 System Architecture Overview

### Component Architecture

The FMOFP system follows a modular, service-oriented architecture with clear separation of concerns:

#### Core System Manager ✅ **OPERATIONAL**
- Central coordination and component management
- System health monitoring and status reporting
- Component lifecycle management
- Thread and resource management

#### Radar Management System ✅ **OPERATIONAL**
**Radar Processing:** All radar types are fully operational for data processing
**Display Integration:** ✅ **OPERATIONAL** - All radars connected via radar-to-display bridge

**Operational Radar Systems:**
- Weather Radar (RT Address 9, Subaddress 1)
- TFR Radar (RT Address 9, Subaddress 2)
- SAR Radar (RT Address 9, Subaddress 3)
- Targeting Radar (RT Address 9, Subaddress 4)
- AEWC Radar (RT Address 9, Subaddress 5)

#### Display Management System ✅ **OPERATIONAL**
**Display Rendering:** All display types are fully operational
**Live Data Integration:** ✅ **OPERATIONAL** - All five radar systems push live data to the display coordinator

**Operational Display Systems:**
- Primary Flight Display (RT Address 11, Subaddress 11)
- Multi-Function Display (RT Address 11, Subaddress 12)
- Radar Display (RT Address 11, Subaddress 14)

#### Flight Management System ✅ **OPERATIONAL**
- Real-time flight data processing and integration
- Navigation and waypoint management
- Flight control system coordination
- Tactical systems management

### Database Architecture ✅ **OPERATIONAL**

The system uses a distributed database architecture with specialized databases for different subsystems:

**Database Configuration:**
- **Radar Data:** `radar_data.db` - All radar systems share common database
- **Display Data:** `display_data.db` - Display system data and configurations
- **Flight Management:** `fms_data.db` - Flight management and navigation data
- **Flight Control:** `flight_control_data.db` - Flight control system data
- **Navigation Data:** `navigation_data.db` - GPS and navigation systems
- **Communication Data:** `communication_data.db` - Radio, SatCom, and data link systems
- **System Configuration:** `default.db` - System-wide configuration and settings

**Performance Characteristics:**
- Maximum 20 total database workers across all systems
- Radar systems: High-performance configuration (200 queries/120s, 2000 batch inserts/3s)
- Display systems: Real-time configuration (200 queries/60s, 2000 batch inserts/3s)
- Flight systems: Critical-path configuration (200 queries/60s, 2000 batch inserts/3s)
- Default systems: Standard configuration (100 queries/60s, 1000 batch inserts/5s)

## 1.3 MIL-STD-1553B Communication Protocol

### Protocol Implementation ✅ **OPERATIONAL**

The FMOFP system implements a complete MIL-STD-1553B data bus architecture for reliable, deterministic communication between avionics subsystems.

**Key Features:**
- Dual redundant data bus capability
- Bus Controller (BC) and Remote Terminal (RT) implementation
- Command/response protocol with status word validation
- Block transfer capability for large data sets
- Built-in error detection and correction
- Transaction tracking and loop prevention

### Message Structure ✅ **OPERATIONAL**

All MIL-STD-1553B messages follow the standard 16-bit word format:

**Command Word Structure:**
```
Bit:  15 14 13 12 11 | 10 | 9  8  7  6  5 | 4  3  2  1  0
     [  RT Address  ] [T/R] [ Subaddress ] [ Word Count ]
```

**Status Word Structure:**
```
Bit:  15 14 13 12 11 | 10 | 9 | 8 | 7 6 5 | 4 | 3 | 2 | 1 | 0
     [  RT Address  ] [ME][IN][SR][Rsv'd][BC][BY][SS][DB][TF]
```

**Data Word Structure:**
```
Bit:  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
     [           Data (16 bits)                      ]
```

### Address Configuration ✅ **OPERATIONAL**

The system uses a standardized addressing scheme based on `rtAddressConfig.xml`:

**Primary RT Addresses:**
- **RT 0:** Unnamed System (Reserved)
- **RT 1:** Avionics Systems
- **RT 2:** Communications Systems
- **RT 3:** Engine Management
- **RT 4:** Environmental Control System
- **RT 5:** Flight Control System
- **RT 6:** Mission Planning
- **RT 7:** Navigation Systems
- **RT 8:** Power Management
- **RT 9:** Radar Systems ✅ **OPERATIONAL**
- **RT 10:** Sensor Management
- **RT 11:** Display Systems ✅ **OPERATIONAL**
- **RT 12:** Flight Management System ✅ **OPERATIONAL**

**Radar Subaddresses (RT 9):**
- **Subaddress 1:** Weather Radar ✅ **OPERATIONAL**
- **Subaddress 2:** TFR (Ground Mapping) Radar ✅ **OPERATIONAL**
- **Subaddress 3:** SAR (Air Mapping) Radar ✅ **OPERATIONAL**
- **Subaddress 4:** Targeting Radar ✅ **OPERATIONAL**
- **Subaddress 5:** AEWC (Collision Avoidance) Radar ✅ **OPERATIONAL**

**Display Subaddresses (RT 11):**
- **Subaddress 11:** Primary Flight Display ✅ **OPERATIONAL**
- **Subaddress 12:** Multi-Function Display ✅ **OPERATIONAL**
- **Subaddress 13:** EICAS (Engine Indicating) ✅ **OPERATIONAL**
- **Subaddress 14:** Radar Display ✅ **OPERATIONAL**
- **Subaddress 15:** Tactical Situation Display ✅ **OPERATIONAL**
- **Subaddress 16:** Stores Management System ✅ **OPERATIONAL**

### Communication Flow ✅ **OPERATIONAL**

**Message Routing Architecture:**
1. **Bus Controller (BC)** - Manages all bus communications
2. **Remote Terminals (RT)** - Individual subsystem endpoints
3. **Message Validation** - Ensures protocol compliance
4. **Transaction Tracking** - Prevents message loops
5. **Error Recovery** - Handles communication failures

**Current Communication Status:**
- **BC ↔ Radar Systems:** ✅ **OPERATIONAL**
- **BC ↔ Display Systems:** ✅ **OPERATIONAL**
- **BC ↔ Flight Management:** ✅ **OPERATIONAL**
- **Radar → Display Data Flow:** 🐛 **KNOWN ISSUES** (Weather radar only)
- **Cross-System Integration:** ✅ **OPERATIONAL** (cross-radar data fusion layer active)

## 1.4 System Requirements and Installation

### Hardware Requirements

**Minimum System Requirements:**
- **Processor:** Intel Core i7 or equivalent (64-bit)
- **Memory:** 16 GB RAM minimum
- **Storage:** 500 GB available space
- **Graphics:** DirectX 11 compatible graphics card
- **Network:** Ethernet adapter for system integration
- **Optional:** MIL-STD-1553B interface hardware for real hardware integration

**Recommended System Requirements:**
- **Processor:** Intel Core i9 or equivalent
- **Memory:** 32 GB RAM or higher
- **Storage:** 1 TB SSD storage
- **Graphics:** High-performance graphics card with 4GB+ VRAM
- **Display:** Dual monitor setup (1920x1080 minimum per display)
- **Network:** Gigabit Ethernet for optimal performance

### Software Requirements ✅ **OPERATIONAL**

**Operating System:**
- Windows 10 (64-bit) or later
- Windows Server 2019 or later (for server deployments)

**Required Software Components:**
- **Python 3.9 or later** ✅ **OPERATIONAL**
- **PyQt6 GUI framework** ✅ **OPERATIONAL**
- **NumPy** for numerical computations ✅ **OPERATIONAL**
- **SQLite** for database management ✅ **OPERATIONAL**

### Installation Procedure ✅ **OPERATIONAL**

A fully automated installer is provided. Run it once from the `B20SS/` directory:

```
python install.py
```

The installer performs all six steps automatically:

1. **Python version check** — requires Python 3.9+
2. **Directory structure verification** — confirms all required subdirectories are present
3. **Dependency installation** — installs PyQt6, NumPy, and qasync from bundled wheels or PyPI
4. **Configuration file validation** — parses and validates all four XML config files
5. **Database initialisation** — creates all SQLite databases from `schema.xml`
6. **Startup verification** — dry-runs the system to confirm all subsystems reach STANDBY

**Optional flags:**
```
python install.py --offline         # use only bundled wheels, no internet
python install.py --no-verify       # skip startup verification step
python install.py --force-reinstall # reinstall dependencies even if present
```

**Exit codes:** 0 = success, 1 = failure (reason printed to console).
   - Verify database tables are created correctly
   - Load initial configuration data
   - Confirm all system databases are accessible

5. **Verify Installation**
   ```
   python FMOFP/Main.py --verify
   ```
   - Check all components initialize correctly
   - Verify communication between subsystems
   - Confirm radar systems reach STANDBY mode
   - Test display system responsiveness

### Configuration Files ✅ **OPERATIONAL**

**Primary Configuration Files:**

**`dbConfig.xml`** - Database system configuration
- System database assignments
- Query rate limits and batch operations
- Connection pool settings
- Retry policies for database operations

**`rtAddressConfig.xml`** - MIL-STD-1553B addressing
- RT address assignments for all systems
- Subaddress mappings for subsystems
- System identification and naming

**`messageRateConfig.xml`** - Message timing configuration
- Message transmission rates
- Priority settings
- Timeout configurations

**`startupConfiguration.xml`** - System startup sequence
- Component initialization order
- Startup verification procedures
- Error handling during startup

## 1.5 Quick Start Guide

### System Startup ✅ **OPERATIONAL**

**1. Launch the FMOFP System**
```
cd FMOFP
python Main.py
```

**2. Monitor System Initialization**
- Watch startup logs for component initialization
- Verify all radar systems initialize to STANDBY mode
- Confirm display systems are responsive
- Check flight management system integration

**Expected Startup Sequence:**
```
[SYSTEM] Initializing FMOFP System Manager...
[DATABASE] Loading database configurations...
[1553B] Initializing MIL-STD-1553B communication...
[RADAR] Initializing radar management system...
[DISPLAY] Initializing display management system...
[FMS] Initializing flight management system...
[SYSTEM] All systems operational - Ready for operations
```

**3. Verify System Status**
- All radar systems should show STANDBY mode
- PFD should display current flight parameters
- MFD should be responsive to user input
- No critical errors in system logs

### Basic Operations ✅ **OPERATIONAL**

**Radar Mode Changes:**
1. Access radar control through system interface
2. Select desired radar system (Weather, Targeting, SAR, TFR, AEWC)
3. Choose target operational mode
4. Monitor mode change completion in logs
5. **Note:** Display integration limited to Weather radar

**Display Configuration:**
1. Access display settings through MFD interface
2. Select display theme (Standard or Holographic)
3. Adjust brightness and contrast settings
4. Configure display layout preferences
5. Test display responsiveness

**Flight Data Monitoring:**
1. Monitor PFD for real-time flight parameters
2. Check tactical indicators (G-Force, AOA, Energy State)
3. Review active warnings or cautions
4. Verify navigation data accuracy from FMS integration

### Known Limitations 🐛 **KNOWN ISSUES**

**Weather Radar Display Integration:**
- Weather radar data processing is fully operational
- VIL and precipitation data generation works correctly
- **Issue:** 1553B communication prevents data from reaching displays
- **Workaround:** Monitor radar status through system logs
- **Status:** Under active development

**Other Radar Display Integration:**
- All radar systems (Targeting, SAR, TFR, AEWC) process data correctly
- Radar mode changes and data generation are operational
- **Issue:** Data routing to display systems not yet implemented
- **Workaround:** Radar functionality available through direct system access
- **Status:** Planned for next development phase

**Display System Limitations:**
- Display rendering and user interface fully operational
- Theme management and visual effects working correctly
- **Issue:** Limited live data integration (FMS data works, radar data limited)
- **Workaround:** Use PFD for flight data, MFD for system status
- **Status:** Display integration under active development

### Emergency Procedures ⚠️ **IN DEVELOPMENT**

**System Failure Response:**
1. Check system health indicators in MFD
2. Review error logs for failure details:
   ```
   tail -f FMOFP/logs/DEBUG_*.log
   ```
3. Attempt component restart if safe to do so
4. Switch to backup systems if available
5. **Note:** Automated recovery procedures under development

**Communication Failure:**
1. Verify MIL-STD-1553B bus status
2. Check RT address configuration in logs
3. Restart communication subsystems:
   ```
   python FMOFP/MIL_STD_1553B/Messaging.py --restart
   ```
4. Monitor message flow recovery
5. **Note:** Enhanced diagnostics under development

### Performance Optimization ⚠️ **IN DEVELOPMENT**

**Current Performance Characteristics:**
- **Radar Processing:** Real-time operation at full capability
- **Display Updates:** 20Hz refresh rate for PFD, 10Hz for MFD
- **Database Operations:** Optimized for high-throughput radar data
- **Memory Usage:** Approximately 2-4 GB under normal operations
- **CPU Usage:** 30-50% on recommended hardware

**Optimization Guidelines:**
- Monitor database query rates in system logs
- Adjust message timing if communication delays occur
- Use holographic displays sparingly on lower-end hardware
- Close unused display windows to conserve resources

## 1.6 Visual System Architecture Guide

### System Architecture Visualization

[DIAGRAM PLACEHOLDER: High-level FMOFP system architecture diagram]
**Figure 1.1:** FMOFP System Architecture Overview
1. **User Interface Layer** - PFD, MFD, Holographic displays
2. **Application Layer** - Radar Management, Display Management, Flight Management
3. **Communication Layer** - MIL-STD-1553B Protocol implementation
4. **Data Layer** - Database systems and configuration management
5. **Hardware Interface Layer** - System hardware and external interfaces

### Component Interaction Flow

[DIAGRAM PLACEHOLDER: Component interaction sequence diagram]
**Figure 1.2:** System Component Interaction Flow
1. **System Manager** initiates component startup
2. **Database Manager** establishes data connections
3. **1553B Bus Controller** initializes communication
4. **Radar Systems** initialize to STANDBY mode
5. **Display Systems** establish FMS data connections
6. **Flight Management** begins real-time data processing

### MIL-STD-1553B Communication Architecture

[DIAGRAM PLACEHOLDER: 1553B communication architecture]
**Figure 1.3:** MIL-STD-1553B Communication Layout
1. **Bus Controller (BC)** - Central communication coordinator
2. **RT 9 - Radar Systems** - All radar system endpoints
3. **RT 11 - Display Systems** - All display system endpoints
4. **RT 12 - Flight Management** - FMS integration endpoint
5. **Data Bus** - Primary communication pathway
6. **Message Routing** - Protocol-compliant message flow

### Data Flow Visualization

[DIAGRAM PLACEHOLDER: System data flow diagram]
**Figure 1.4:** FMOFP Data Flow Architecture
1. **Flight Data Input** - Real-time flight parameters from FMS
2. **Radar Data Processing** - Multi-radar data generation
3. **Display Data Integration** - Data routing to display systems
4. **Database Storage** - Persistent data management
5. **System Health Monitoring** - Real-time status tracking

### Operational Mode Transitions

[DIAGRAM PLACEHOLDER: System mode transition diagram]
**Figure 1.5:** System Operational Mode Transitions
1. **STARTUP** - System initialization and component loading
2. **STANDBY** - Systems ready, minimal processing
3. **OPERATIONAL** - Full system operation with data processing
4. **MAINTENANCE** - System maintenance and diagnostic mode
5. **SHUTDOWN** - Controlled system shutdown sequence

### Interface Element Identification

[SCREENSHOT PLACEHOLDER: Main system interface with numbered callouts]
**Figure 1.6:** Main System Interface Elements
1. **System Status Panel** - Overall system health indicators
2. **Radar Control Section** - Access to all radar systems
3. **Display Management** - Display system controls and configuration
4. **Communication Monitor** - 1553B bus status and message flow
5. **Log Output Window** - Real-time system messages
6. **Configuration Access** - System settings and parameters
7. **Emergency Controls** - System shutdown and emergency procedures

### Step-by-Step System Startup Visualization

[SCREENSHOT PLACEHOLDER: System startup sequence screenshots]
**Figure 1.7:** Visual System Startup Guide
1. **Initial Launch** - Python console startup
2. **Component Loading** - System manager initialization
3. **Database Connection** - Database system establishment
4. **Communication Init** - 1553B protocol activation
5. **Radar Initialization** - All radar systems to STANDBY
6. **Display Activation** - Display systems become responsive
7. **System Ready** - Full operational capability achieved

---

**Navigation:** [← Table of Contents](00_Title_and_TOC.md) | [Weather Radar System →](02_Weather_Radar_System.md)

**Related Files:**
- → [Communication & Messaging](11_Communication_Messaging.md) - Detailed 1553B implementation
- → [Troubleshooting & Diagnostics](13_Troubleshooting_Diagnostics.md) - System problem resolution
- → [Technical Reference](14_Technical_Reference.md) - Configuration parameters and specifications

---

*File: 01_System_Overview.md*
*Last Updated: December 2024*
*Next Review: March 2025*
