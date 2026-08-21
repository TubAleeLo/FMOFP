"""
Flight Control System (FCS) Package

This package implements the Flight Control System as a subsystem of the Flight Management System.
It handles aircraft orientation control and provides data to the Primary Flight Display (PFD).
"""

from FMOFP.Systems.flightManagementSys.flightControlSys.flight_control_system import (
    FlightControlSystem,
    get_flight_control_system
)

__all__ = ['FlightControlSystem', 'get_flight_control_system']
