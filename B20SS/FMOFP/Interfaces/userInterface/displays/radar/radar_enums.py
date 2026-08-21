"""
Radar Enums for Display System

This file used to be an independent, hand-maintained copy of
Systems/radarManagement/radar_enums.py ("This file is a local copy of
radar_enums.py in the Radar system", per the old docstring). That
duplication had drifted: aewc_radarMode here was missing the
AEWC_TRACK/TRACK member that the canonical Systems-layer enum has, and
every member here was a genuinely separate class object from the
Systems-layer one, so isinstance() checks and equality comparisons
between an enum value obtained via this module and one obtained via
Systems.radarManagement.radar_enums would silently fail even when the
member "looked" the same (e.g. targeting_radarMode.SEARCH from this
module is not the targeting_radarMode.SEARCH radar objects actually
validate against in Systems/radarManagement/targeting/targeting_radar.py
etc.).

Fixed (August 2026 audit) by re-exporting the single canonical
definitions from Systems/radarManagement/radar_enums.py instead of
redefining them. Existing `from .radar_enums import weather_radarMode`
(or `from ..radar_enums import ...`) call sites throughout the display
layer keep working unchanged -- they now get the real, canonical enum
classes instead of a drifted local copy.
"""

from FMOFP.Systems.radarManagement.radar_enums import (
    RadarMode,
    MissionPhase,
    weather_radarMode,
    targeting_radarMode,
    sar_radarMode,
    aewc_radarMode,
    tfr_radarMode,
)

__all__ = [
    "RadarMode",
    "MissionPhase",
    "weather_radarMode",
    "targeting_radarMode",
    "sar_radarMode",
    "aewc_radarMode",
    "tfr_radarMode",
]
