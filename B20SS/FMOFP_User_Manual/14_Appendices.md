# 14. Appendices

**Navigation:** [← System Maintenance](13_System_Maintenance.md) | [Table of Contents](00_Title_and_TOC.md)

---

## Appendix A: Technical Specifications

### A.1 System Requirements

#### A.1.1 Hardware Requirements

**Minimum System Requirements:**
- **Processor:** Intel Core i5-8400 or AMD Ryzen 5 2600 (6 cores, 2.8 GHz)
- **Memory:** 16 GB RAM
- **Storage:** 500 GB SSD with 100 GB free space
- **Graphics:** DirectX 11 compatible with 2 GB VRAM
- **Network:** Gigabit Ethernet adapter
- **Display:** 1920x1080 minimum resolution

**Recommended System Requirements:**
- **Processor:** Intel Core i7-10700K or AMD Ryzen 7 3700X (8 cores, 3.6 GHz)
- **Memory:** 32 GB RAM
- **Storage:** 1 TB NVMe SSD with 200 GB free space
- **Graphics:** DirectX 12 compatible with 8 GB VRAM
- **Network:** Dual Gigabit Ethernet adapters
- **Display:** Dual 2560x1440 or single 4K display

#### A.1.2 Software Requirements

**Operating System:**
- **Primary:** Windows 10 Professional (64-bit) or later
- **Alternative:** Windows Server 2019 or later
- **Linux:** Ubuntu 20.04 LTS or CentOS 8 (experimental support)

**Runtime Dependencies:**
- **Python:** 3.9 or later with asyncio support
- **PyQt6:** 6.8.1 or later for GUI components
- **XML Parser:** Built-in xml.etree.ElementTree
- **Threading:** Python threading and asyncio libraries
- **Logging:** Python logging framework

### A.2 Network Configuration

#### A.2.1 MIL-STD-1553B Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    MIL-STD-1553B Bus                        │
├─────────────────────────────────────────────────────────────┤
│  Bus Controller (BC) - RT Address 0                         │
│  ├─ Avionics System - RT Address 1                          │
│  ├─ Communications - RT Address 2                           │
│  ├─ Engine Management - RT Address 3                        │
│  ├─ Environmental Control - RT Address 4                    │
│  ├─ Flight Control System - RT Address 5                    │
│  ├─ Mission Planning - RT Address 6                         │
│  ├─ Navigation System - RT Address 7                        │
│  ├─ Power Management - RT Address 8                         │
│  ├─ Radar Management - RT Address 9                         │
│  ├─ Sensor Management - RT Address 10                       │
│  └─ Display System - RT Address 11                          │
└─────────────────────────────────────────────────────────────┘
```

#### A.2.2 Port Configuration

**Default Port Assignments:**
- **Bus Controller Listener:** Port 12345
- **Remote Terminal Sender:** Port 12346
- **Display System:** Port 8080 (HTTP)
- **Diagnostic Interface:** Port 9090
- **Database Connections:** Port 5432 (PostgreSQL)

---

## Appendix B: Message Reference

### B.1 MIL-STD-1553B Message Format

#### B.1.1 Command Word Structure (20 bits)

```
Bit Position: 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
             [Sync Pattern] [RT Address] [T/R] [Subaddress] [Word Count] [P]
             [  1  0  0   ] [  5 bits  ] [ 1 ] [  5 bits  ] [  5 bits  ] [1]
```

**Field Descriptions:**
- **Sync Pattern (3 bits):** Always "100" for command/status words
- **RT Address (5 bits):** Remote Terminal address (0-31)
- **T/R Bit (1 bit):** 0 = BC to RT, 1 = RT to BC
- **Subaddress (5 bits):** Subaddress or mode code (0-31)
- **Word Count (5 bits):** Number of data words (0-32)
- **Parity (1 bit):** Odd parity bit

#### B.1.2 Data Word Structure (20 bits)

```
Bit Position: 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
             [Sync Pattern] [        Data Field        ] [P]
             [  0  0  1   ] [       16 bits           ] [1]
```

**Field Descriptions:**
- **Sync Pattern (3 bits):** Always "001" for data words
- **Data Field (16 bits):** Actual data payload
- **Parity (1 bit):** Odd parity bit

### B.2 Message Type Constants

#### B.2.1 Radar Message Types

```python
# Weather Radar Messages
WEATHER_RADAR_MODE_CHANGE_REQUEST = "weatherRadarModeChangeRequest"
WEATHER_RADAR_MODE_CHANGE_RESPONSE = "weatherRadarModeChangeResponse"
WEATHER_RADAR_PRECIPITATION_DATA = "weatherRadarPrecipitationData"
WEATHER_RADAR_VIL_DATA = "weatherRadarVILData"

# TFR Radar Messages
TFR_RADAR_MODE_CHANGE_REQUEST = "tfrRadarModeChangeRequest"
TFR_RADAR_ELEVATION_DATA = "tfrRadarElevationData"

# SAR Radar Messages
SAR_RADAR_MODE_CHANGE_REQUEST = "sarRadarModeChangeRequest"
SAR_RADAR_IMAGERY_DATA = "sarRadarImageryData"

# Targeting Radar Messages
TARGETING_RADAR_MODE_CHANGE_REQUEST = "targetingRadarModeChangeRequest"
TARGETING_RADAR_TRACK_DATA = "targetingRadarTrackData"

# AEWC Radar Messages
AEWC_RADAR_MODE_CHANGE_REQUEST = "aewcRadarModeChangeRequest"
AEWC_RADAR_SECTOR_SCAN = "aewcRadarSectorScan"
```

#### B.2.2 FMS Message Types

```python
# Flight Management System Messages
FMS_MODE_CHANGE_REQUEST = "fmsModeChangeRequest"
FMS_MODE_CHANGE_RESPONSE = "fmsModeChangeResponse"
FMS_NAVIGATION_UPDATE = "fmsNavigationUpdate"
FMS_ATTITUDE_UPDATE = "fmsAttitudeUpdate"
FMS_MANEUVER_REQUEST = "fmsManeuverRequest"

# Flight Control System Messages
FCS_CONTROL_SURFACE_CHANGE = "fcsControlSurfaceChange"
FCS_FLIGHT_MODE_CHANGE = "fcsFlightModeChange"
FCS_AUTOPILOT_COMMAND = "fcsAutopilotCommand"
```

### B.3 RT Address Mapping

#### B.3.1 System Address Assignments

| RT Address | System Name | Primary Function |
|------------|-------------|------------------|
| 0 | Bus Controller | Central message coordination |
| 1 | Avionics System | Core avionics management |
| 2 | Communications | Radio and data link systems |
| 3 | Engine Management | Engine control and monitoring |
| 4 | Environmental Control | Life support and climate |
| 5 | Flight Control System | Control surfaces and autopilot |
| 6 | Mission Planning | Mission management and planning |
| 7 | Navigation System | GPS and inertial navigation |
| 8 | Power Management | Electrical power distribution |
| 9 | Radar Management | Multi-radar coordination |
| 10 | Sensor Management | Sensor fusion and management |
| 11 | Display System | Cockpit displays and HUD |

#### B.3.2 Subaddress Assignments

**Radar Management (RT Address 9):**
- Subaddress 1: Weather Radar
- Subaddress 2: TFR Radar
- Subaddress 3: SAR Radar
- Subaddress 4: Targeting Radar
- Subaddress 5: AEWC Radar

**Display System (RT Address 11):**
- Subaddress 11: Primary Flight Display (PFD)
- Subaddress 12: Multi-Function Display (MFD)
- Subaddress 13: Engine Indication and Crew Alerting System (EICAS)
- Subaddress 14: Radar Display
- Subaddress 15: Tactical Situation Display (TSD)
- Subaddress 16: Stores Management System (SMS)

---

## Appendix C: Configuration Files

### C.1 System Configuration

#### C.1.1 startupConfiguration.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <logging>
        <commandInterface>true</commandInterface>
        <logging_enabled>true</logging_enabled>
        <debugging>true</debugging>
        <level>debug</level>
        <console_output>true</console_output>
    </logging>
    
    <database>
        <host>localhost</host>
        <port>5432</port>
        <name>fmofp_db</name>
        <user>fmofp_user</user>
        <timeout>30</timeout>
    </database>
    
    <network>
        <bc_port>12345</bc_port>
        <rt_port>12346</rt_port>
        <display_port>8080</display_port>
        <diagnostic_port>9090</diagnostic_port>
    </network>
    
    <performance>
        <thread_pool_size>10</thread_pool_size>
        <message_queue_size>1000</message_queue_size>
        <health_check_interval>5</health_check_interval>
        <display_refresh_rate>60</display_refresh_rate>
    </performance>
</configuration>
```

#### C.1.2 dbConfig.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<database_configuration>
    <systems>
        <system name="radar_management">
            <database>radar_data_db</database>
            <tables>
                <table name="weather_radar_data">weather_radar_table</table>
                <table name="tfr_radar_data">tfr_radar_table</table>
                <table name="sar_radar_data">sar_radar_table</table>
                <table name="targeting_radar_data">targeting_radar_table</table>
                <table name="aewc_radar_data">aewc_radar_table</table>
            </tables>
        </system>
        
        <system name="display_system">
            <database>display_data_db</database>
            <tables>
                <table name="pfd_data">pfd_table</table>
                <table name="mfd_data">mfd_table</table>
                <table name="hud_data">hud_table</table>
                <table name="radar_display_data">radar_display_table</table>
            </tables>
        </system>
        
        <system name="flight_management">
            <database>fms_data_db</database>
            <tables>
                <table name="navigation_data">navigation_table</table>
                <table name="attitude_data">attitude_table</table>
                <table name="flight_plan_data">flight_plan_table</table>
            </tables>
        </system>
    </systems>
</database_configuration>
```

### C.2 Message Configuration

#### C.2.1 messageRateConfig.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<message_rate_configuration>
    <rates>
        <rate message_type="weatherRadarModeChangeRequest" rate_hz="1.0"/>
        <rate message_type="weatherRadarPrecipitationData" rate_hz="10.0"/>
        <rate message_type="weatherRadarVILData" rate_hz="5.0"/>
        <rate message_type="fmsNavigationUpdate" rate_hz="20.0"/>
        <rate message_type="fmsAttitudeUpdate" rate_hz="50.0"/>
        <rate message_type="displayUpdate" rate_hz="60.0"/>
    </rates>
</message_rate_configuration>
```

#### C.2.2 rtAddressConfig.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rt_address_configuration>
    <remote_terminals>
        <rt address="1" name="avionics_system" enabled="true"/>
        <rt address="2" name="communications" enabled="true"/>
        <rt address="3" name="engine_management" enabled="true"/>
        <rt address="4" name="environmental_control" enabled="true"/>
        <rt address="5" name="flight_control_system" enabled="true"/>
        <rt address="6" name="mission_planning" enabled="true"/>
        <rt address="7" name="navigation_system" enabled="true"/>
        <rt address="8" name="power_management" enabled="true"/>
        <rt address="9" name="radar_management" enabled="true"/>
        <rt address="10" name="sensor_management" enabled="true"/>
        <rt address="11" name="display_system" enabled="true"/>
    </remote_terminals>
</rt_address_configuration>
```

---

## Appendix D: Error Codes and Troubleshooting

### D.1 System Error Codes

#### D.1.1 Initialization Errors (1000-1999)

| Error Code | Description | Resolution |
|------------|-------------|------------|
| 1001 | Component initialization failure | Check component dependencies and configuration |
| 1002 | Database connection failure | Verify database configuration and connectivity |
| 1003 | Thread manager initialization failure | Check thread pool configuration and resources |
| 1004 | Display system initialization failure | Verify graphics drivers and display configuration |
| 1005 | Message queue initialization failure | Check memory allocation and queue configuration |

#### D.1.2 Communication Errors (2000-2999)

| Error Code | Description | Resolution |
|------------|-------------|------------|
| 2001 | MIL-STD-1553B protocol violation | Check message format and timing |
| 2002 | RT address conflict | Verify RT address configuration |
| 2003 | Message timeout | Check network connectivity and system load |
| 2004 | Invalid message format | Validate message structure and encoding |
| 2005 | Block transfer failure | Check data integrity and sequence numbers |

#### D.1.3 Radar System Errors (3000-3999)

| Error Code | Description | Resolution |
|------------|-------------|------------|
| 3001 | Weather radar mode change failure | Check radar system status and configuration |
| 3002 | Precipitation data processing error | Verify data format and processing pipeline |
| 3003 | VIL data calculation error | Check input data and calculation parameters |
| 3004 | Radar display update failure | Verify display system connectivity |
| 3005 | Multi-radar coordination error | Check radar management system status |

#### D.1.4 Display System Errors (4000-4999)

| Error Code | Description | Resolution |
|------------|-------------|------------|
| 4001 | PFD rendering failure | Check graphics drivers and display hardware |
| 4002 | MFD update timeout | Verify display manager and data sources |
| 4003 | HUD projection error | Check HUD hardware and calibration |
| 4004 | Display container initialization failure | Verify Qt framework and display configuration |
| 4005 | Holographic display error | Check holographic display hardware and drivers |

### D.2 Common Issues and Solutions

#### D.2.1 Performance Issues

**Symptom:** System running slowly or unresponsively
**Possible Causes:**
- High CPU or memory usage
- Thread contention or deadlocks
- Database performance issues
- Network latency or congestion

**Resolution Steps:**
1. Check system resource utilization
2. Review thread manager status and performance metrics
3. Analyze database query performance
4. Verify network configuration and bandwidth
5. Optimize system configuration parameters

#### D.2.2 Display Issues

**Symptom:** Displays not updating or showing incorrect data
**Possible Causes:**
- Display manager not running
- Data source connectivity issues
- Graphics driver problems
- Display configuration errors

**Resolution Steps:**
1. Verify display manager status
2. Check data source connections
3. Update graphics drivers
4. Validate display configuration
5. Restart display system components

#### D.2.3 Communication Issues

**Symptom:** Messages not being delivered or processed
**Possible Causes:**
- MIL-STD-1553B protocol errors
- Network connectivity issues
- Message queue overflows
- RT address conflicts

**Resolution Steps:**
1. Check MIL-STD-1553B message format
2. Verify network connectivity
3. Monitor message queue status
4. Validate RT address configuration
5. Restart communication components

---

## Appendix E: Performance Benchmarks

### E.1 System Performance Metrics

#### E.1.1 Message Processing Performance

| Message Type | Processing Time (ms) | Throughput (msg/sec) | Memory Usage (MB) |
|--------------|---------------------|---------------------|-------------------|
| Weather Radar Mode Change | 5.2 | 192 | 2.1 |
| Precipitation Data | 12.8 | 78 | 8.5 |
| VIL Data | 8.4 | 119 | 5.2 |
| FMS Navigation Update | 3.1 | 323 | 1.8 |
| Display Update | 1.6 | 625 | 3.2 |

#### E.1.2 Display System Performance

| Display Type | Refresh Rate (FPS) | Render Time (ms) | GPU Usage (%) |
|--------------|-------------------|------------------|---------------|
| Primary Flight Display | 60 | 16.7 | 25 |
| Multi-Function Display | 60 | 16.7 | 35 |
| HUD Display | 60 | 16.7 | 20 |
| Radar Display | 30 | 33.3 | 45 |
| Holographic Display | 90 | 11.1 | 60 |

#### E.1.3 Thread Performance

| Thread Name | CPU Usage (%) | Memory Usage (MB) | Average Runtime (s) |
|-------------|---------------|-------------------|-------------------|
| Main Loop | 5.2 | 12.8 | N/A (continuous) |
| BC Listener | 8.1 | 15.2 | N/A (continuous) |
| RT Listener | 6.4 | 13.6 | N/A (continuous) |
| Async Message Handler | 12.3 | 28.4 | N/A (continuous) |
| Display Manager | 15.8 | 45.2 | N/A (continuous) |
| Radar Management | 18.6 | 32.1 | N/A (continuous) |

### E.2 Scalability Metrics

#### E.2.1 Concurrent User Support

| Concurrent Users | Response Time (ms) | CPU Usage (%) | Memory Usage (GB) |
|------------------|-------------------|---------------|-------------------|
| 1 | 45 | 25 | 2.1 |
| 5 | 52 | 35 | 2.8 |
| 10 | 68 | 48 | 3.9 |
| 20 | 89 | 65 | 5.2 |
| 50 | 156 | 85 | 8.7 |

#### E.2.2 Data Volume Handling

| Data Volume | Processing Time (s) | Memory Peak (GB) | Success Rate (%) |
|-------------|-------------------|------------------|------------------|
| 1 MB | 0.12 | 0.5 | 100 |
| 10 MB | 1.24 | 1.2 | 100 |
| 100 MB | 12.8 | 3.8 | 99.8 |
| 1 GB | 128.5 | 12.4 | 99.2 |
| 10 GB | 1285.2 | 45.6 | 97.8 |

---

## Appendix F: Glossary

### F.1 Technical Terms

**AEWC** - Airborne Early Warning and Control  
**BC** - Bus Controller (MIL-STD-1553B)  
**CLI** - Command Line Interface  
**EICAS** - Engine Indication and Crew Alerting System  
**FCS** - Flight Control System  
**FMS** - Flight Management System  
**FMOFP** - Flight Management Operating Flight Program  
**HUD** - Head-Up Display  
**MFD** - Multi-Function Display  
**MIL-STD-1553B** - Military Standard 1553B data bus  
**PFD** - Primary Flight Display  
**RT** - Remote Terminal (MIL-STD-1553B)  
**SAR** - Synthetic Aperture Radar  
**TFR** - Terrain Following Radar  
**TSD** - Tactical Situation Display  
**VIL** - Vertically Integrated Liquid  

### F.2 System Components

**Async Message Handler** - Asynchronous message processing component  
**Block Transfer** - Large data transfer mechanism exceeding 32-word limit  
**Bus Controller** - Central MIL-STD-1553B message coordinator  
**Display Manager** - Cockpit display coordination system  
**Message Queue Manager** - Message buffering and routing system  
**Radar Management System** - Multi-radar coordination and control  
**Remote Terminal** - MIL-STD-1553B endpoint device  
**System Manager** - Central system coordination and lifecycle management  
**Thread Manager** - Thread lifecycle and performance management  
**Unified Router** - System-wide message routing and distribution  

### F.3 Operational Terms

**Command Word** - MIL-STD-1553B control message format  
**Data Word** - MIL-STD-1553B data payload format  
**Health Check** - Automated component status verification  
**Mode Change** - System operational state transition  
**Precipitation Data** - Weather radar precipitation information  
**Request ID** - Unique message correlation identifier  
**Status Word** - MIL-STD-1553B response message format  
**Subaddress** - MIL-STD-1553B subsystem identifier  
**System State** - Overall system operational status  
**Test Suite** - Comprehensive system validation procedures  

---

## Appendix G: References and Standards

### G.1 Military Standards

- **MIL-STD-1553B** - Digital Time Division Command/Response Multiplex Data Bus
- **MIL-STD-461** - Requirements for the Control of Electromagnetic Interference Characteristics of Subsystems and Equipment
- **MIL-STD-810** - Environmental Engineering Considerations and Laboratory Tests
- **DO-178C** - Software Considerations in Airborne Systems and Equipment Certification
- **DO-254** - Design Assurance Guidance for Airborne Electronic Hardware

### G.2 Industry Standards

- **ARINC 429** - Digital Information Transfer System (DITS) for Aircraft
- **ARINC 661** - Cockpit Display System Interfaces to User Systems
- **IEEE 802.3** - Ethernet Standard for Local Area Networks
- **ISO 9001** - Quality Management Systems Requirements
- **RTCA DO-160** - Environmental Conditions and Test Procedures for Airborne Equipment

### G.3 Software Standards

- **Python 3.9+** - Programming language specification
- **PyQt6** - Cross-platform GUI toolkit
- **XML 1.0** - Extensible Markup Language specification
- **JSON** - JavaScript Object Notation data interchange format
- **SQL** - Structured Query Language for database operations

### G.4 Documentation References

- **FMOFP System Architecture Document** - Internal system design specification
- **MIL-STD-1553B Implementation Guide** - Protocol implementation details
- **Radar System Integration Manual** - Multi-radar coordination procedures
- **Display System Configuration Guide** - Cockpit display setup and operation
- **Maintenance and Troubleshooting Manual** - System maintenance procedures

---

**Navigation:** [← System Maintenance](13_System_Maintenance.md) | [Table of Contents](00_Title_and_TOC.md)

---

*File: 14_Appendices.md*  
*Last Updated: December 2024*  
*Next Review: As system implementations are updated*

**END OF MANUAL**
