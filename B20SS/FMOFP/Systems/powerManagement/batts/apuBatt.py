# Auxiliary Power Unit (APU) Battery: The APU is used to start the
# main engines and provide power for onboard systems when the main
# engines are not running, especially on the ground. The APU
# battery helps in starting the APU and can be used when
# the main battery is not available.

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.powerManagement.batts.mainBatt import Battery

logger = get_logger()


class APUBattery(Battery):
    """
    APU Battery: dedicated to starting the Auxiliary Power Unit, and usable
    as a fallback when the main battery is unavailable/depleted.
    """

    APU_START_AMPS = 150.0
    APU_START_DURATION_HOURS = 8.0 / 3600.0  # ~8 second APU light-off

    def __init__(self, capacity_ah: float = 15.0, nominal_voltage: float = 24.0,
                 charge_pct: float = 100.0):
        super().__init__("APU Battery", capacity_ah, nominal_voltage, charge_pct)
        self.apu_running = False

    def start_apu(self) -> bool:
        """Attempt to start the APU. Returns True on a successful light-off."""
        if self.apu_running:
            logger.info("[BATT] APU already running")
            return True
        if self.charge_pct < 15.0:
            logger.warning(f"[BATT] APU battery too low ({self.charge_pct:.1f}%) to start APU")
            return False
        supplied = self.discharge(self.APU_START_AMPS, self.APU_START_DURATION_HOURS)
        required = self.APU_START_AMPS * self.APU_START_DURATION_HOURS
        self.apu_running = supplied >= required * 0.999
        logger.info(f"[BATT] APU start: {'OK' if self.apu_running else 'FAILED'} "
                    f"(charge now {self.charge_pct:.1f}%)")
        return self.apu_running

    def stop_apu(self):
        if self.apu_running:
            self.apu_running = False
            logger.info("[BATT] APU shut down")

    def assist_main_battery_start(self, engine_name: str, requested_amps: float,
                                   dt_hours: float) -> float:
        """
        Supply supplementary current to help start an engine when the main
        battery alone is insufficient. Returns the amp-hours actually
        contributed by this battery.
        """
        supplied = self.discharge(requested_amps, dt_hours)
        if supplied > 0:
            logger.info(f"[BATT] APU battery assisting start of {engine_name}: "
                        f"{supplied:.2f}Ah contributed")
        return supplied
