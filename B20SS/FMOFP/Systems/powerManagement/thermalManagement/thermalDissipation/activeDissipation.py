"""
Active Dissipation Unit

The heat-rejection device (fan-assisted heat exchanger / radiator) used by
the avionics cooling loop (see coolingSystems/cooling.py) to actively reject
absorbed heat to ambient air. "Active" as opposed to passive convection --
fan speed can be commanded up to increase heat rejection at the cost of
higher power draw and noise/vibration.
"""

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class ActiveDissipationUnit:
    """
    Fan-driven heat exchanger. Rejects heat from a coolant loop to ambient
    air at a rate proportional to fan speed and the coolant-to-ambient
    temperature differential.
    """

    # Heat rejected (Watts) per % fan speed per degree C of delta-T,
    # a simplified linear heat-exchanger model.
    REJECTION_COEFFICIENT_W_PER_PCT_PER_C = 0.6
    MAX_FAN_PCT = 100.0
    MIN_FAN_PCT = 10.0  # fan never fully stops while unit is active

    def __init__(self, name: str = "Active Dissipation Unit"):
        self.name = name
        self.fan_pct = self.MIN_FAN_PCT
        self.active = True
        self.last_rejected_watts = 0.0

    def set_fan_speed(self, pct: float):
        self.fan_pct = max(self.MIN_FAN_PCT if self.active else 0.0,
                            min(self.MAX_FAN_PCT, pct))

    def activate(self):
        self.active = True
        if self.fan_pct < self.MIN_FAN_PCT:
            self.fan_pct = self.MIN_FAN_PCT
        logger.info(f"[THERMAL] {self.name} activated")

    def deactivate(self):
        self.active = False
        self.fan_pct = 0.0
        self.last_rejected_watts = 0.0
        logger.info(f"[THERMAL] {self.name} deactivated")

    def reject_heat(self, coolant_temp_c: float, ambient_temp_c: float) -> float:
        """
        Compute and return the heat (Watts) rejected this tick, given the
        current coolant and ambient temperatures. Returns 0 if the unit is
        inactive or the coolant is already at/below ambient (nothing to
        reject).
        """
        if not self.active:
            self.last_rejected_watts = 0.0
            return 0.0
        delta_t = max(0.0, coolant_temp_c - ambient_temp_c)
        rejected = self.fan_pct * delta_t * self.REJECTION_COEFFICIENT_W_PER_PCT_PER_C
        self.last_rejected_watts = rejected
        return rejected

    def auto_control(self, coolant_temp_c: float, target_temp_c: float):
        """
        Simple proportional fan-speed controller: increase fan speed as
        coolant temperature rises above target.
        """
        if not self.active:
            return
        error = coolant_temp_c - target_temp_c
        if error <= 0:
            self.set_fan_speed(self.MIN_FAN_PCT)
        else:
            # 5C over target -> full fan speed
            self.set_fan_speed(self.MIN_FAN_PCT + (error / 5.0) * (self.MAX_FAN_PCT - self.MIN_FAN_PCT))

    def get_status(self):
        return {
            'name': self.name,
            'active': self.active,
            'fan_pct': round(self.fan_pct, 1),
            'last_rejected_watts': round(self.last_rejected_watts, 1),
        }
