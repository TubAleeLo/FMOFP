"""
Radar Enumerations for Predefined Message System

This file used to define its own, independent set of radar mode enums
with a completely different numbering scheme from the canonical
definitions in Systems/radarManagement/radar_enums.py -- e.g. this
module's targeting_radarMode.SEARCH was 2, while the canonical
targeting_radarMode.SEARCH (what targeting_radar.py itself validates
against and what RadarMessageHandler.py decodes incoming messages with)
is 40. Because Interfaces/predefinedMessages/*_messages.py sends the
raw integer .value of these enums over the message bus (see e.g.
targeting_radar_messages.py::set_targeting_radar_mode, which passes the
enum instance into radar_handler.send_request(...)), a caller using
this module's old numbering to request SEARCH mode (value=2) would have
had the receiving radar interpret raw value 2 as DEGRADED under the
canonical numbering -- a silent, wrong-mode bug, not merely a comparison
mismatch. Confirmed live (August 2026 audit) that radar_handler here
resolves to the real, live system_manager.components['radar_message_handler']
when running against a booted system, so this was a genuinely reachable
bug for any caller of this predefinedMessages API, not just a
theoretical one.

Fixed by re-exporting the single canonical definitions from
Systems/radarManagement/radar_enums.py instead of redefining them with
different values. The only member name used here that the canonical
enums didn't already have was TRACKING (this module's alias for
TRACK/TRACKING mode on targeting_radarMode and aewc_radarMode) -- added
as an additional alias to the canonical enums rather than dropped, so
existing call sites (targeting_radar_messages.py, aewc_radar_messages.py,
usage_example.py) keep working unchanged.
"""

from FMOFP.Systems.radarManagement.radar_enums import (
    RadarMode,
    weather_radarMode,
    targeting_radarMode,
    sar_radarMode,
    aewc_radarMode,
    tfr_radarMode,
)

__all__ = [
    "RadarMode",
    "weather_radarMode",
    "targeting_radarMode",
    "sar_radarMode",
    "aewc_radarMode",
    "tfr_radarMode",
]
