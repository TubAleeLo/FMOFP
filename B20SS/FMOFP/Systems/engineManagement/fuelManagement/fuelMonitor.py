"""
Fuel Monitor

Watches tank quantities over time for a FuelSystem (fuelControl.py):
tracks consumption rate, raises low-fuel / critical-fuel alerts, and
detects unexpected fuel loss (a level dropping faster than engine
consumption alone can explain -- a simple leak-detection heuristic).
"""

from typing import Dict, List, Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

LOW_FUEL_PCT = 20.0
CRITICAL_FUEL_PCT = 10.0

# If a tank's level drops by more than this fraction of its capacity in a
# single tick beyond what the known engine fuel-consumption rate accounts
# for, flag it as a possible leak.
LEAK_UNEXPLAINED_DROP_FRACTION = 0.02


class FuelMonitor:
    """Consumption tracking and alerting for a FuelSystem's tanks."""

    def __init__(self, fuel_system):
        """
        Args:
            fuel_system: a Systems.engineManagement.fuelManagement.fuelControl.FuelSystem
                instance to monitor.
        """
        self.fuel_system = fuel_system
        self._last_levels: Dict[str, float] = {}
        self._consumption_rate_kg_per_s: Dict[str, float] = {}
        self._alerts: List[Dict] = []

    def _tank_capacity(self, tank_name: str) -> Optional[float]:
        tank = self.fuel_system.tanks.get(tank_name)
        return tank.capacity if tank else None

    def poll(self, dt_seconds: float):
        """Sample current tank levels and update consumption rates / alerts."""
        if dt_seconds <= 0:
            return
        status = self.fuel_system.get_fuel_status()
        for tank_name, level in status.items():
            capacity = self._tank_capacity(tank_name)
            last = self._last_levels.get(tank_name)
            if last is not None:
                drop = last - level
                rate = drop / dt_seconds
                self._consumption_rate_kg_per_s[tank_name] = max(0.0, rate)

                # Leak heuristic: compare actual drop to what the tank's
                # connected engines' known fuel_consumption_rate would predict.
                expected_drop = self._expected_consumption(tank_name, dt_seconds)
                if capacity and drop > expected_drop + capacity * LEAK_UNEXPLAINED_DROP_FRACTION:
                    self._raise_alert(tank_name, 'LEAK_SUSPECTED',
                                       f"Unexplained fuel loss in {tank_name}: "
                                       f"{drop:.1f}kg drop, expected ~{expected_drop:.1f}kg")

            self._last_levels[tank_name] = level

            if capacity:
                pct = (level / capacity) * 100.0
                if pct <= CRITICAL_FUEL_PCT:
                    self._raise_alert(tank_name, 'CRITICAL_FUEL', f"{tank_name} at {pct:.1f}% - CRITICAL")
                elif pct <= LOW_FUEL_PCT:
                    self._raise_alert(tank_name, 'LOW_FUEL', f"{tank_name} at {pct:.1f}%")

    def _expected_consumption(self, tank_name: str, dt_seconds: float) -> float:
        expected = 0.0
        for engine_name in self.fuel_system.fuel_lines.get(tank_name, []):
            engine = self.fuel_system.engines.get(engine_name)
            if engine:
                expected += engine.fuel_consumption_rate * dt_seconds
        return expected

    def _raise_alert(self, tank_name: str, alert_type: str, message: str):
        alert = {'tank': tank_name, 'type': alert_type, 'message': message}
        self._alerts.append(alert)
        log_fn = logger.error if alert_type in ('CRITICAL_FUEL', 'LEAK_SUSPECTED') else logger.warning
        log_fn(f"[FUEL_MON] {message}")

    def get_consumption_rates(self) -> Dict[str, float]:
        """kg/s consumption rate per tank, based on the most recent poll()."""
        return dict(self._consumption_rate_kg_per_s)

    def get_alerts(self, clear: bool = False) -> List[Dict]:
        alerts = list(self._alerts)
        if clear:
            self._alerts.clear()
        return alerts

    def get_status(self) -> Dict:
        return {
            'levels': dict(self._last_levels),
            'consumption_rates_kg_per_s': self.get_consumption_rates(),
            'active_alerts': len(self._alerts),
        }
