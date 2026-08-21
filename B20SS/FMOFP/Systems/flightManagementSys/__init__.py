"""
Flight Management System Package

Provides aircraft flight management capabilities:
- Attitude control and monitoring (roll, pitch, yaw)
- Navigation systems integration
- Flight data management
- Tactical operations support
"""

# Import the main FMS components for easier access
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
from FMOFP.Systems.flightManagementSys.fmsControl import get_fms_control
from FMOFP.Systems.flightManagementSys.fmsMessenger import get_fms_messenger

__all__ = [
    'get_flightManagementSystem',
    'get_fms_control',
    'get_fms_messenger'
]
