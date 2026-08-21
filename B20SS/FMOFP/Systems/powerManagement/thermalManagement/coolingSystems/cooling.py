"""
Avionics Cooling System

Manages the liquid coolant loop that absorbs waste heat from avionics bays
and electronics (radar processors, ECU, mission computers) and rejects it
to ambient via an ActiveDissipationUnit (see thermalDissipation/activeDissipation.py).

This is separate from HVAC.py, which controls cabin/cockpit air, not the
avionics coolant loop.
"""

from typing import Dict
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.powerManagement.thermalManagement.thermalDissipation.activeDissipation import ActiveDissipationUnit

logger = get_logger()

# Simplified thermal mass model: degrees C the coolant loop heats up per
# net Watt (heat load minus heat rejected) accumulated over one hour,
# treated as a fixed lumped thermal capacitance for the whole loop.
COOLANT_THERMAL_MASS_C_PER_WH = 0.02

WARNING_TEMP_C = 55.0
CRITICAL_TEMP_C = 70.0


class CoolingSystem:
    """Avionics coolant loop: absorbs heat loads, rejects via dissipation unit."""

    def __init__(self, target_temp_c: float = 25.0, ambient_temp_c: float = 20.0):
        self.coolant_temp_c = ambient_temp_c
        self.ambient_temp_c = ambient_temp_c
        self.target_temp_c = target_temp_c
        self.dissipation_unit = ActiveDissipationUnit("Avionics Bay Heat Exchanger")
        self._heat_sources: Dict[str, float] = {}  # name -> Watts

    def set_heat_load(self, source_name: str, watts: float):
        """Register/update the heat output of a component feeding this loop."""
        self._heat_sources[source_name] = max(0.0, watts)

    def remove_heat_source(self, source_name: str):
        self._heat_sources.pop(source_name, None)

    def total_heat_load_watts(self) -> float:
        return sum(self._heat_sources.values())

    def update(self, dt_hours: float):
        """Advance the coolant loop's thermal state by dt_hours."""
        self.dissipation_unit.auto_control(self.coolant_temp_c, self.target_temp_c)
        rejected_watts = self.dissipation_unit.reject_heat(self.coolant_temp_c, self.ambient_temp_c)
        net_watts = self.total_heat_load_watts() - rejected_watts
        delta_c = net_watts * dt_hours * COOLANT_THERMAL_MASS_C_PER_WH
        self.coolant_temp_c = max(self.ambient_temp_c, self.coolant_temp_c + delta_c)

        if self.coolant_temp_c >= CRITICAL_TEMP_C:
            logger.error(f"[THERMAL] Coolant temperature CRITICAL: {self.coolant_temp_c:.1f}C")
        elif self.coolant_temp_c >= WARNING_TEMP_C:
            logger.warning(f"[THERMAL] Coolant temperature elevated: {self.coolant_temp_c:.1f}C")

    def get_status(self) -> Dict:
        return {
            'coolant_temp_c': round(self.coolant_temp_c, 2),
            'target_temp_c': self.target_temp_c,
            'ambient_temp_c': self.ambient_temp_c,
            'total_heat_load_watts': round(self.total_heat_load_watts(), 1),
            'heat_sources': dict(self._heat_sources),
            'dissipation_unit': self.dissipation_unit.get_status(),
            'status': ('CRITICAL' if self.coolant_temp_c >= CRITICAL_TEMP_C
                       else 'WARNING' if self.coolant_temp_c >= WARNING_TEMP_C
                       else 'OK'),
        }
