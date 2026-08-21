# Flight Management Operating Flight Program (FMOFP)
## User Manual

**Version 1.1**
**Document Date:** August 2026 (originally December 2024)
**System Version:** FMOFP 1.1.0 (B20SS) — see `FMOFP/__init__.py` `__version__`

---

**IMPORTANT NOTICE**
This manual documents an in-development system. Features marked with status indicators show current implementation state:

- ✅ **OPERATIONAL:** Fully functional and tested
- ⚠️ **IN DEVELOPMENT:** Partially implemented, may have limitations
- ❌ **NOT IMPLEMENTED:** Planned but not yet developed
- 🐛 **KNOWN ISSUES:** Functional but with documented problems

**WARNING:** This system is under active development. Operational capabilities and procedures may change between versions. Always verify system status before relying on documented features for critical operations.

---

## Document Organization

This manual is organized into 14 separate files for easy navigation and maintenance:

- **Files 00-01:** System overview and architecture
- **Files 02-06:** Individual radar system documentation
- **Files 07-09:** Display system documentation
- **Files 10-14:** Integration, procedures, and reference materials

Each file is designed to be self-contained while providing cross-references to related sections.

---

## Table of Contents

### **Section 1: System Foundation**
**File: 00_Title_and_TOC.md** ................................. *This File*
- Document organization and conventions
- Status indicators and warnings
- Complete table of contents

**File: 00a_Getting_Started.md** ................................ *Page 5*
- Quick Start Guide for New Interns
- Essential Interface Overview
- First-Time User Checklist
- Basic Operation Tutorial

**File: 00b_Legal_Information.md** .............................. *Page 7*
- Copyright Notice and Development Status
- Usage Restrictions and Disclaimers
- Contact Information
- Development Team Information

**File: 01_System_Overview.md** ................................. *Page 8*
- 1.1 Introduction to FMOFP
- 1.2 System Architecture Overview
- 1.3 MIL-STD-1553B Communication Protocol
- 1.4 System Requirements and Installation
- 1.5 Quick Start Guide
- 1.6 Visual System Architecture Guide

### **Section 2: Radar Systems**
**File: 02_Weather_Radar_System.md** ............................ *Page 28*
- 2.1 Weather Radar Overview ✅ **OPERATIONAL**
- 2.2 Interface Elements Identification
- 2.3 Operational Modes and Capabilities
- 2.4 VIL (Vertically Integrated Liquid) Analysis ✅ **OPERATIONAL**
- 2.5 Precipitation Detection and Analysis ✅ **OPERATIONAL**
- 2.6 Storm Cell Tracking ✅ **OPERATIONAL**
- 2.7 Step-by-Step Operational Procedures
- 2.8 Turbulence Detection ✅ **OPERATIONAL**
- 2.9 Wind Shear Detection ✅ **OPERATIONAL**
- 2.10 Weather Radar Troubleshooting

**File: 03_Targeting_Radar_System.md** .......................... *Page 53*
- 3.1 Targeting Radar Overview ✅ **OPERATIONAL**
- 3.2 Interface Elements Identification
- 3.3 TARGET_SEARCH/SEARCH Mode (40) ✅ **OPERATIONAL**
- 3.4 TARGET_TRACK/TRACK Mode (41) ✅ **OPERATIONAL**
- 3.5 LOCK Mode (42) ✅ **OPERATIONAL**
- 3.6 Multi-Target Management ✅ **OPERATIONAL**
- 3.7 Target Classification ✅ **OPERATIONAL** (SignatureAnalyzer + StealthDetector)
- 3.8 Step-by-Step Operational Procedures
- 3.9 Targeting Radar Troubleshooting

**File: 04_SAR_Radar_System.md** ................................ ✅ **COMPLETE**
- 4.1 SAR Radar Overview ⚠️ **BASIC SIMULATION** (Pattern Generation) | ✅ **OPERATIONAL** (Display Integration + Change Detection)
- 4.2 Interface Elements Identification
- 4.3 Stripmap Mode Operations ⚠️ **BASIC SIMULATION** - Simple linear pattern generation
- 4.4 Spotlight Mode Operations ⚠️ **BASIC SIMULATION** - Simple circular pattern generation
- 4.5 ScanSAR Mode Operations ⚠️ **BASIC SIMULATION** - Simple multi-swath pattern generation
- 4.6 Interferometric Mode ❌ **NOT IMPLEMENTED** - Placeholder only
- 4.7 Doppler Beam Mode ❌ **NOT IMPLEMENTED** - Placeholder only
- 4.8 Step-by-Step Operational Procedures
- 4.9 SAR Radar Troubleshooting

**File: 05_TFR_Radar_System.md** ................................ ✅ **COMPLETE**
- 5.1 TFR Radar Overview ⚠️ **BASIC SIMULATION** (Terrain Simulation) | ✅ **OPERATIONAL** (Display Integration + Path Optimiser + Clearance Manager)
- 5.2 Interface Elements Identification
- 5.3 TFR_SEARCH/SEARCH Mode (20) ⚠️ **BASIC SIMULATION** - Mathematical terrain generation
- 5.4 TFR_TRACK/TRACK Mode (21) ⚠️ **BASIC SIMULATION** - Mathematical terrain generation
- 5.5 TERRAIN_FOLLOWING Mode (23) ⚠️ **BASIC SIMULATION** - Filtered terrain simulation
- 5.6 OBSTACLE_AVOIDANCE Mode (24) ✅ **OPERATIONAL** - PathOptimiser + ClearanceManager
- 5.7 Step-by-Step Operational Procedures
- 5.8 TFR Radar Troubleshooting

**File: 06_AEWC_Radar_System.md** ............................... ✅ **COMPLETE**
- 6.1 AEWC Radar Overview ⚠️ **BASIC SIMULATION** (Target Simulation) | ✅ **OPERATIONAL** (Display Integration + Sector Priority + Electronic Protection)
- 6.2 Interface Elements Identification
- 6.3 AEWC_SEARCH/SEARCH Mode (50) ⚠️ **BASIC SIMULATION** - Mathematical target generation
- 6.4 SECTOR_SCAN Mode (52) ⚠️ **BASIC SIMULATION** - 6-sector scanning simulation
- 6.5 AEWC_TRACK/TRACK Mode (55) ⚠️ **BASIC SIMULATION** - Target tracking simulation
- 6.6 STEALTH_DETECTION Mode (53) ✅ **OPERATIONAL** - StealthDetector via TargetProcessor
- 6.7 ELECTRONIC_PROTECTION Mode (54) ✅ **OPERATIONAL** - ElectronicProtection (jamming detection + mitigation)
- 6.8 Step-by-Step Operational Procedures
- 6.9 AEWC Radar Troubleshooting

### **Section 3: Display Systems**
**File: 07_Primary_Flight_Display.md** .......................... *Page 104*
- 7.1 PFD Overview ✅ **OPERATIONAL**
- 7.2 Display Element Identification
- 7.3 Attitude Indicator and Pitch Ladder ✅ **OPERATIONAL**
- 7.4 Altitude and Airspeed Tapes ✅ **OPERATIONAL**
- 7.5 Heading Indicator ✅ **OPERATIONAL**
- 7.6 Flight Mode Indicators ✅ **OPERATIONAL**
- 7.7 Tactical Indicators (G-Force, AOA) ✅ **OPERATIONAL**
- 7.8 Envelope Warnings ✅ **OPERATIONAL**
- 7.9 Step-by-Step Display Operations
- 7.10 PFD Configuration and Troubleshooting

**File: 08_Multi_Function_Display.md** .......................... *Page 122*
- 8.1 MFD Overview ✅ **OPERATIONAL**
- 8.2 Display Element Identification
- 8.3 Radar Integration and Display ✅ **OPERATIONAL**
- 8.4 System Status Monitoring ✅ **OPERATIONAL**
- 8.5 Navigation Display ⚠️ **IN DEVELOPMENT**
- 8.6 Tactical Display ⚠️ **IN DEVELOPMENT**
- 8.7 Communications Display ❌ **NOT IMPLEMENTED**
- 8.8 Step-by-Step Display Operations
- 8.9 MFD Configuration and Troubleshooting

**File: 09_Holographic_Display_System.md** ...................... *Page 140*
- 9.1 Holographic Display Overview ✅ **OPERATIONAL**
- 9.2 Display Element Identification
- 9.3 Enhanced Visual Effects ✅ **OPERATIONAL**
- 9.4 3D Rendering Capabilities ✅ **OPERATIONAL**
- 9.5 Animation and Particle Effects ⚠️ **IN DEVELOPMENT**
- 9.6 Theme Management ✅ **OPERATIONAL**
- 9.7 Step-by-Step Display Operations
- 9.8 Holographic Display Configuration

### **Section 4: System Integration**
**File: 10_Flight_Management_Integration.md** ................... *Page 152*
- 10.1 FMS Integration Overview ✅ **OPERATIONAL**
- 10.2 Real-Time Flight Data Integration ✅ **OPERATIONAL**
- 10.3 Navigation and Waypoint Management ✅ **OPERATIONAL**
- 10.4 Flight Control System Integration ✅ **OPERATIONAL**
- 10.5 Tactical Systems Management ✅ **OPERATIONAL**
- 10.6 Mission Planning Integration ✅ **OPERATIONAL** (MFD ROUTE/TARGETS/OOB tabs, MissionService, RouteManager, TargetingSystem, OOB)
- 10.7 FMS Troubleshooting

**File: 11_Communication_Messaging.md** ......................... *Page 177*
- 11.1 MIL-STD-1553B Implementation ✅ **OPERATIONAL** (all 12 RT addresses wired)
- 11.2 Bus Controller Operations ✅ **OPERATIONAL**
- 11.3 Remote Terminal Operations ✅ **OPERATIONAL**
- 11.4 Message Routing and Validation ✅ **OPERATIONAL**
- 11.5 Transaction Tracking ✅ **OPERATIONAL**
- 11.6 Error Handling and Recovery ✅ **OPERATIONAL**
- 11.7 Message Flow Visualization
- 11.8 Step-by-Step Communication Procedures
- 11.9 Communication Troubleshooting

**Defensive Systems** ✅ **OPERATIONAL**
- RWR (Radar Warning Receiver) — bearing ring display on TSD + EICAS hostile track alerts
- CMDS (Countermeasures Dispenser) — chaff/flare inventory bars on EICAS defensive panel
- ECM (Electronic Countermeasures) — STANDBY/ACTIVE/PASSIVE mode indicator on EICAS
- DefensiveService polled at 10 Hz; hostile contacts drive EICAS CAUTION/WARNING alerts

**Sensor Management** ✅ **OPERATIONAL**
- SensorService (active/passive sensors + RadarDataFusion track count)
- EICAS sensor health display: FAULT → WARNING, DEGRADED → CAUTION
- Fused hostile track count drives EICAS FUSION HOSTILE TRACK alerts (CAUTION ≥1, WARNING ≥3)

**Scenario Engine** ✅ **OPERATIONAL**
- `Interfaces/scenarios/scenarioEngine.py` — XML-driven event injection at timed triggers
- Supported event types: radar_contact, threat_launch, weather_cell, waypoint, phase_change, system_failure, message
- Two included scenarios: `trainingScenario.xml` (16 events, ~10 min) and `failureScenario.xml` (16 events, cascading failures)
- Usage: `engine = get_scenario_engine(); engine.load('trainingScenario.xml'); engine.start()`

### **Section 5: Operations and Reference**
**File: 12_Operational_Procedures.md** .......................... ✅ **COMPLETE**
- 12.1 System Startup Procedures ✅ **OPERATIONAL**
- 12.2 Component Initialization Sequence ✅ **OPERATIONAL**
- 12.3 Predefined Message Operations ✅ **OPERATIONAL**
- 12.4 System State Management ✅ **OPERATIONAL**
- 12.5 Combined Operations Procedures ✅ **OPERATIONAL**
- 12.6 Error Handling and Recovery ✅ **OPERATIONAL**
- 12.7 Shutdown Procedures ✅ **OPERATIONAL**
- 12.8 Operational Troubleshooting ✅ **OPERATIONAL**
- 12.9 Configuration and Maintenance ✅ **OPERATIONAL**

**File: 13_System_Maintenance.md** .............................. ✅ **COMPLETE**
- 13.1 Maintenance Overview ✅ **OPERATIONAL**
- 13.2 Logging System ✅ **OPERATIONAL**
- 13.3 Thread Management ✅ **OPERATIONAL**
- 13.4 Diagnostic Tools ✅ **OPERATIONAL**
- 13.5 Performance Monitoring ✅ **OPERATIONAL**
- 13.6 Maintenance Procedures ✅ **OPERATIONAL**
- 13.7 Troubleshooting Guide ✅ **OPERATIONAL**
- 13.8 Configuration Management ✅ **OPERATIONAL**

**File: 14_Appendices.md** ...................................... ✅ **COMPLETE**
- Appendix A: Technical Specifications ✅ **OPERATIONAL**
- Appendix B: Message Reference ✅ **OPERATIONAL**
- Appendix C: Configuration Files ✅ **OPERATIONAL**
- Appendix D: Error Codes and Troubleshooting ✅ **OPERATIONAL**
- Appendix E: Performance Benchmarks ✅ **OPERATIONAL**
- Appendix F: Glossary ✅ **OPERATIONAL**
- Appendix G: References and Standards ✅ **OPERATIONAL**

---

## Document Conventions

### Status Indicators
Throughout this manual, features are marked with status indicators to show their current implementation state:

- ✅ **OPERATIONAL:** Feature is fully implemented, tested, and ready for operational use
- ⚠️ **IN DEVELOPMENT:** Feature is partially implemented and may have limitations or incomplete functionality
- ❌ **NOT IMPLEMENTED:** Feature is planned but not yet developed
- 🐛 **KNOWN ISSUES:** Feature is functional but has documented problems or limitations

### Warning Levels
**CAUTION:** Indicates procedures that could result in system damage if not followed correctly.

**WARNING:** Indicates procedures that could result in mission failure or safety hazards.

**CRITICAL:** Indicates procedures that could result in catastrophic failure or loss of aircraft.

### Cross-References
- **→ See Section X.X:** Reference to related information in the same file
- **→ See File XX:** Reference to information in another manual file
- **→ See Technical Reference:** Reference to detailed technical information

### Code Examples
```
Code examples and command syntax are shown in monospace font
```

### Procedural Steps
1. Numbered steps indicate required sequence
   a. Sub-steps provide additional detail
   b. Alternative procedures when applicable

• Bullet points indicate options or additional information

---

## How to Use This Manual

### For New Users
1. Start with **File 01_System_Overview.md** for system introduction
2. Review **File 12_Operational_Procedures.md** for basic operations
3. Focus on specific radar or display files as needed for your role

### For Experienced Users
- Use individual files as reference for specific systems
- Check status indicators for current feature availability
- Refer to **File 13_Troubleshooting_Diagnostics.md** for problem resolution

### For System Administrators
- Review **File 11_Communication_Messaging.md** for system architecture
- Use **File 14_Technical_Reference.md** for configuration details
- Monitor **File 13_Troubleshooting_Diagnostics.md** for system health

### For Developers
- Check development status indicators throughout all files
- Review **File 14_Technical_Reference.md** for API and message specifications
- Use **File 13_Troubleshooting_Diagnostics.md** for debugging procedures

---

## Assembly Instructions for Microsoft Word

To combine these files into a single Word document:

1. **Create New Document:** Start with a blank Word document
2. **Insert Files:** Use Insert → Text → Object → Text from File for each markdown file in order
3. **Apply Formatting:** Convert markdown formatting to Word styles
4. **Update Page Numbers:** Adjust page references in table of contents
5. **Generate TOC:** Use Word's automatic table of contents feature
6. **Cross-Reference Links:** Convert file references to internal bookmarks

**Note:** Each file includes navigation headers and footers to maintain context when used independently.

---

*Document Version: 1.0*
*Last Updated: December 2024*
*Next Review: March 2025*
