"""
HVAC (Heating, Ventilation, and Air Conditioning)

Controls cockpit/cabin air temperature and airflow. Separate from
cooling.py, which manages the avionics electronics coolant loop rather
than crew-occupied spaces.
"""

from typing import Dict
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class HVACSystem:
    """Cockpit/cabin climate control: temperature setpoint and airflow."""

    MIN_TEMP_C = 10.0
    MAX_TEMP_C = 30.0
    MIN_AIRFLOW_PCT = 0.0
    MAX_AIRFLOW_PCT = 100.0

    # Degrees C the cabin moves toward setpoint per % airflow per hour,
    # a simplified first-order thermal response.
    RESPONSE_C_PER_PCT_PER_HOUR = 0.15

    def __init__(self, initial_temp_c: float = 22.0, ambient_temp_c: float = 15.0):
        self.cabin_temp_c = initial_temp_c
        self.ambient_temp_c = ambient_temp_c
        self.setpoint_c = initial_temp_c
        self.airflow_pct = 50.0
        self.powered = True

    def set_temperature(self, target_c: float):
        self.setpoint_c = max(self.MIN_TEMP_C, min(self.MAX_TEMP_C, target_c))
        logger.info(f"[HVAC] Setpoint changed to {self.setpoint_c:.1f}C")

    def set_airflow(self, pct: float):
        self.airflow_pct = max(self.MIN_AIRFLOW_PCT, min(self.MAX_AIRFLOW_PCT, pct))

    def power_off(self):
        self.powered = False
        logger.info("[HVAC] System powered off")

    def power_on(self):
        self.powered = True
        logger.info("[HVAC] System powered on")

    def update(self, dt_hours: float):
        """Advance cabin temperature toward setpoint by dt_hours."""
        if not self.powered or self.airflow_pct <= 0:
            # Passive drift toward ambient when the system isn't actively conditioning.
            drift = (self.ambient_temp_c - self.cabin_temp_c) * min(1.0, dt_hours * 2)
            self.cabin_temp_c += drift
            return

        error = self.setpoint_c - self.cabin_temp_c
        max_delta = self.airflow_pct * self.RESPONSE_C_PER_PCT_PER_HOUR * dt_hours
        delta = max(-max_delta, min(max_delta, error))
        self.cabin_temp_c += delta

    def get_status(self) -> Dict:
        return {
            'powered': self.powered,
            'cabin_temp_c': round(self.cabin_temp_c, 2),
            'setpoint_c': self.setpoint_c,
            'airflow_pct': round(self.airflow_pct, 1),
            'ambient_temp_c': self.ambient_temp_c,
            'at_setpoint': abs(self.cabin_temp_c - self.setpoint_c) < 0.5,
        }
