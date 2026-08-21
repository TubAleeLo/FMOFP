# Legal Information & Development Status

**Navigation:** [← Getting Started](00a_Getting_Started.md) | [Table of Contents](00_Title_and_TOC.md) | [System Overview →](01_System_Overview.md)

---

## Copyright Notice

**© 2024-2025 FMOFP Development Team**  
Flight Management Operating Flight Program (FMOFP)  
All rights reserved.

This software and documentation are proprietary and confidential. No part of this software or documentation may be reproduced, distributed, or transmitted in any form or by any means, including photocopying, recording, or other electronic or mechanical methods, without the prior written permission of the development team, except in the case of brief quotations embodied in critical reviews and certain other noncommercial uses permitted by copyright law.

---

## Development Status Disclaimer

### **IMPORTANT DEVELOPMENT NOTICE**

**This system is under active development (Version B20SS).**

**⚠️ CRITICAL DISCLAIMERS:**
- **NOT FOR OPERATIONAL FLIGHT USE** - This system is for development and training purposes only
- **FEATURES MAY CHANGE** - Operational capabilities and procedures may change between versions
- **DEVELOPMENT BUILD** - This is a development build with known limitations and issues

### Current Implementation Status

**Operational Systems ✅:**
- Core system architecture and management
- MIL-STD-1553B communication protocol
- Database management and storage
- Flight Management System (FMS) integration
- Primary Flight Display (PFD) with real-time flight data
- Multi-Function Display (MFD) system integration
- Holographic display system with advanced visual effects

**Systems with Known Issues 🐛:**
- *(None currently. The weather radar display-integration issue listed in
  earlier revisions was resolved in 1.2.0 — see File 02.)*

**Systems in Development ⚠️:**
- **Advanced Display Features** - Some display capabilities are partially implemented
- **Environmental Control System** - Readings are simulated placeholders rather than a modelled thermal system

**Planned Features ❌:**
- **Real MIL-STD-1553B Hardware Operation** - The software bus adapter layer
  provides the integration point; no vendor driver ships with the system, so
  operation against a physical interface card requires supplying one
- **Distributed Operation** - 1553B addressing is fixed to loopback ports,
  suitable for a single-host simulation only

---

## Usage Restrictions and Disclaimers

### Permitted Uses

**✅ AUTHORIZED USES:**
- **Development and Testing** - Software development and system testing
- **Training and Education** - Educational purposes and intern training
- **Research and Analysis** - System research and capability analysis
- **Documentation and Review** - Technical documentation and system review

### Liability Limitations

**DISCLAIMER OF WARRANTIES:**
This software is provided "AS IS" without warranty of any kind, either express or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, or non-infringement. The development team does not warrant that the software will meet your requirements or that the operation of the software will be uninterrupted or error-free.

**LIMITATION OF LIABILITY:**
In no event shall the development team be liable for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this software.

---

## Contact Information

### Development Team

**Primary Contact:**
- **Development Team Lead:** [Contact Information]
- **Technical Lead:** [Technical Contact]
- **Documentation Lead:** [Documentation Contact]

---

## Acknowledgments
- **Person 1
- **Person 2
- **Person 3
- **Person 4
- **Person 5
- **Person 6


### Third-Party Components

**Python Ecosystem:**
- **Python 3.12+** - Core programming language
- **PyQt6** - GUI framework for display systems
- **NumPy** - Numerical computing for radar processing
- **SQLite** - Database management system

### Standards and Protocols

**Military Standards:**
- **MIL-STD-1553B** - Digital time division command/response multiplex data bus
- **Military Avionics Standards** - Various military avionics specifications

### Development Tools

**Development Environment:**
- **Python Development Tools** - IDEs, debuggers, and testing frameworks
- **Database Tools** - Database design and management utilities
- **Documentation Tools** - Markdown processing and documentation generation

---

## Version History

### FMOFP 1.2.0 (Current)
**Release Date:** August 21, 2026
**Status:** Active Development Build — completion build

**Changes in this release:**
- **Weather radar → display integration resolved.** The 1553B delivery
  defect documented as a known issue through earlier revisions is fixed;
  verified live at 104 bridge deliveries and 104 matching display updates
  over a 50-second run.
- **Scenario `system_failure` events made functional** — they now force
  faults into the LRU health registry instead of only writing a log line.
- **MIL-STD-1553B bus adapter layer** added, providing the documented
  integration point for real interface hardware.
- **Cold-start database connection-pool exhaustion fixed**, along with the
  spurious shutdown health error and the debug-CLI dead test-menu entries.
- **Clean boot log** — a normal run now completes with zero ERROR lines from
  startup through graceful shutdown.

### FMOFP 1.1.0
**Release Date:** August 2026
**Status:** Superseded

- Post-audit build: 20 production-readiness audit rounds, the
  `SystemStateManager` boot-deadlock fix, the full-suite CI runner, and the
  subsystem wiring work.

### Version B20SS (Original)
**Release Date:** December 2024
**Status:** Superseded — retained for reference

**Major Features:**
- Complete system architecture implementation
- Operational radar processing for all radar types
- Functional display systems with FMS integration
- MIL-STD-1553B communication protocol
- Comprehensive documentation and user manual

**Known Limitations:**
- No vendor driver for real MIL-STD-1553B interface hardware
- Single-host operation only (fixed loopback 1553B addressing)
- Environmental Control System readings are simulated placeholders
- Some advanced display features remain partially implemented

**Next Release Goals:**
- Tenative

---

## Legal Compliance

### Export Control

**IMPORTANT:** This software may be subject to export control regulations. Users are responsible for ensuring compliance with all applicable export control laws and regulations.

### Intellectual Property

**Patents and Trademarks:**
- All proprietary algorithms and methods are protected by intellectual property rights
- Third-party trademarks and copyrights are acknowledged and respected
- Use of this software does not grant any rights to proprietary technologies

### Data Protection

**Privacy and Data Handling:**
- System logs may contain operational data
- Users are responsible for protecting sensitive information
- No personal data is collected by the system itself
- Operational data should be handled according to applicable security protocols

---

**Navigation:** [← Getting Started](00a_Getting_Started.md) | [Table of Contents](00_Title_and_TOC.md) | [System Overview →](01_System_Overview.md)

**Related Files:**
- → [Getting Started](00a_Getting_Started.md) - Quick start guide for new users
- → [System Overview](01_System_Overview.md) - Complete system architecture
- → [System Maintenance](13_System_Maintenance.md) - System administration and maintenance

---

*File: 00b_Legal_Information.md*  
*Last Updated: June 13 2025*
