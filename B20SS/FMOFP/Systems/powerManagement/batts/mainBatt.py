# Main Aircraft Battery: This battery provides power for starting the engines and also
# serves as a backup power source for essential aircraft systems when engines are not
# running. It is typically a high-capacity battery capable of handling large loads.

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class Battery:
    """
    Shared base for the aircraft's battery models (main, emergency, APU,
    mission equipment). Tracks charge as a percentage of rated amp-hour
    capacity and exposes simple charge/discharge simulation, matching the
    level of detail already used by other component-level classes in this
    codebase (e.g. FuelTank in engineManagement/fuelManagement/fuelControl.py).
    """

    def __init__(self, name: str, capacity_ah: float, nominal_voltage: float,
                 charge_pct: float = 100.0):
        self.name = name
        self.capacity_ah = capacity_ah
        self.nominal_voltage = nominal_voltage
        self.charge_pct = max(0.0, min(100.0, charge_pct))
        self.load_amps = 0.0
        self.online = True

    def _capacity_remaining_ah(self) -> float:
        return self.capacity_ah * (self.charge_pct / 100.0)

    def discharge(self, amps: float, dt_hours: float) -> float:
        """
        Draw `amps` for `dt_hours` hours. Returns the amp-hours actually
        supplied (may be less than requested if the battery runs out).
        """
        if not self.online or amps <= 0 or dt_hours <= 0:
            return 0.0
        requested_ah = amps * dt_hours
        available_ah = self._capacity_remaining_ah()
        supplied_ah = min(requested_ah, available_ah)
        self.charge_pct = max(0.0, self.charge_pct - (supplied_ah / self.capacity_ah) * 100.0)
        self.load_amps = amps if supplied_ah >= requested_ah else 0.0
        if supplied_ah < requested_ah:
            logger.warning(f"[BATT] {self.name} depleted mid-draw: "
                            f"requested {requested_ah:.2f}Ah, supplied {supplied_ah:.2f}Ah")
        return supplied_ah

    def charge(self, amps: float, dt_hours: float) -> float:
        """
        Charge the battery at `amps` for `dt_hours` hours. Returns the
        amp-hours actually accepted (capped at full capacity).
        """
        if amps <= 0 or dt_hours <= 0:
            return 0.0
        offered_ah = amps * dt_hours
        headroom_ah = self.capacity_ah - self._capacity_remaining_ah()
        accepted_ah = min(offered_ah, headroom_ah)
        self.charge_pct = min(100.0, self.charge_pct + (accepted_ah / self.capacity_ah) * 100.0)
        return accepted_ah

    def is_depleted(self) -> bool:
        return self.charge_pct <= 0.0

    def get_status(self):
        return {
            'name': self.name,
            'charge_pct': round(self.charge_pct, 2),
            'load_amps': round(self.load_amps, 2),
            'capacity_ah': self.capacity_ah,
            'nominal_voltage': self.nominal_voltage,
            'online': self.online,
        }


class MainBattery(Battery):
    """
    Main Aircraft Battery: provides power for starting the engines and also
    serves as a backup power source for essential aircraft systems when
    engines are not running. High-capacity, handles large loads.
    """

    # Typical large-format aircraft main battery: ~40Ah at 24V, engine start
    # draws a large momentary current for a short duration.
    ENGINE_START_AMPS = 300.0
    ENGINE_START_DURATION_HOURS = 5.0 / 3600.0  # ~5 second start cycle

    def __init__(self, capacity_ah: float = 40.0, nominal_voltage: float = 24.0,
                 charge_pct: float = 100.0):
        super().__init__("Main Battery", capacity_ah, nominal_voltage, charge_pct)

    def start_engine(self, engine_name: str) -> bool:
        """
        Attempt to start an engine off battery power alone. Returns True if
        there was enough charge to complete the start sequence.
        """
        if self.charge_pct < 20.0:
            logger.warning(f"[BATT] Main battery too low ({self.charge_pct:.1f}%) "
                            f"to start {engine_name}")
            return False
        supplied = self.discharge(self.ENGINE_START_AMPS, self.ENGINE_START_DURATION_HOURS)
        required = self.ENGINE_START_AMPS * self.ENGINE_START_DURATION_HOURS
        success = supplied >= required * 0.999
        logger.info(f"[BATT] Main battery engine start for {engine_name}: "
                    f"{'OK' if success else 'FAILED'} (charge now {self.charge_pct:.1f}%)")
        return success

    def supply_essential_loads(self, amps: float, dt_hours: float) -> float:
        """Backup power path when engine-driven generators are unavailable."""
        return self.discharge(amps, dt_hours)
