# Emergency Battery: Provides power to critical flight control and
# navigation systems in the event of a failure of the main electrical systems.
# This battery is designed to ensure that key systems can operate long
# enough for the aircraft to land safely during an emergency.

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.powerManagement.batts.mainBatt import Battery

logger = get_logger()


class EmergencyBattery(Battery):
    """
    Emergency Battery: powers critical flight control and navigation
    systems if the main electrical system fails. Sized for endurance
    (how long it can sustain a small, fixed critical load) rather than
    peak current, unlike MainBattery.
    """

    # Typical emergency/standby battery: smaller capacity than the main
    # battery, dedicated to keeping essential flight instruments and FCS
    # alive during a main-bus failure.
    CRITICAL_LOAD_AMPS = 8.0

    def __init__(self, capacity_ah: float = 12.0, nominal_voltage: float = 24.0,
                 charge_pct: float = 100.0):
        super().__init__("Emergency Battery", capacity_ah, nominal_voltage, charge_pct)
        self.emergency_mode_active = False

    def activate_emergency_power(self):
        """Switch onto emergency battery power (main bus assumed failed)."""
        if not self.emergency_mode_active:
            self.emergency_mode_active = True
            logger.warning(f"[BATT] Emergency power ACTIVATED - "
                            f"{self.charge_pct:.1f}% charge remaining")

    def deactivate_emergency_power(self):
        """Main bus power restored; drop the emergency load."""
        if self.emergency_mode_active:
            self.emergency_mode_active = False
            self.load_amps = 0.0
            logger.info("[BATT] Emergency power deactivated - main bus restored")

    def sustain_critical_systems(self, dt_hours: float) -> bool:
        """
        Draw the fixed critical-systems load for one tick while in emergency
        mode. Returns False if the battery could not fully supply the load
        (i.e. is on the verge of depletion).
        """
        if not self.emergency_mode_active:
            return True
        supplied = self.discharge(self.CRITICAL_LOAD_AMPS, dt_hours)
        required = self.CRITICAL_LOAD_AMPS * dt_hours
        ok = supplied >= required * 0.999
        if not ok:
            logger.error("[BATT] Emergency battery cannot fully sustain critical "
                          f"systems - {self.charge_pct:.1f}% charge remaining")
        return ok

    def estimated_endurance_minutes(self) -> float:
        """How many more minutes the critical load can be sustained at the current charge."""
        if self.CRITICAL_LOAD_AMPS <= 0:
            return float('inf')
        remaining_ah = self._capacity_remaining_ah()
        return (remaining_ah / self.CRITICAL_LOAD_AMPS) * 60.0
