"""
Fuel Transfer Manager

Automated inter-tank fuel transfer/balancing on top of a FuelSystem
(fuelControl.py). FuelSystem.transfer_fuel() performs a single one-shot
transfer; this class decides *when* and *how much* to transfer based on
configurable balancing rules (e.g. keep the main tanks fed from a center
tank, or equalize main tanks against each other for lateral CG balance).
"""

from typing import Dict, List, Optional, Tuple
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class TransferRule:
    """
    One balancing rule: when `source_tank`'s level exceeds `min_source_pct`
    of its capacity, top up any tank in `feed_tanks` that is below
    `feed_below_pct` of its own capacity, transferring `rate_kg_per_s`.
    """

    def __init__(self, source_tank: str, feed_tanks: List[str],
                 feed_below_pct: float = 80.0, min_source_pct: float = 20.0,
                 rate_kg_per_s: float = 5.0):
        self.source_tank = source_tank
        self.feed_tanks = feed_tanks
        self.feed_below_pct = feed_below_pct
        self.min_source_pct = min_source_pct
        self.rate_kg_per_s = rate_kg_per_s


class FuelTransferManager:
    """Applies a set of TransferRules to a FuelSystem on each tick."""

    def __init__(self, fuel_system):
        """
        Args:
            fuel_system: a Systems.engineManagement.fuelManagement.fuelControl.FuelSystem
                instance to balance.
        """
        self.fuel_system = fuel_system
        self._rules: List[TransferRule] = []
        self._transfer_log: List[Dict] = []

    def add_rule(self, rule: TransferRule):
        self._rules.append(rule)
        logger.info(f"[FUEL_XFER] Rule added: {rule.source_tank} -> {rule.feed_tanks}")

    def _pct_full(self, tank_name: str) -> Optional[float]:
        tank = self.fuel_system.tanks.get(tank_name)
        if not tank or tank.capacity <= 0:
            return None
        return (tank.current_level / tank.capacity) * 100.0

    def update(self, dt_seconds: float):
        """Evaluate all rules and perform any transfers they trigger."""
        if dt_seconds <= 0:
            return
        for rule in self._rules:
            source_pct = self._pct_full(rule.source_tank)
            if source_pct is None or source_pct < rule.min_source_pct:
                continue
            for feed_tank in rule.feed_tanks:
                feed_pct = self._pct_full(feed_tank)
                if feed_pct is None or feed_pct >= rule.feed_below_pct:
                    continue
                amount = rule.rate_kg_per_s * dt_seconds
                self.fuel_system.transfer_fuel(rule.source_tank, feed_tank, amount)
                self._transfer_log.append({
                    'from': rule.source_tank, 'to': feed_tank, 'amount_kg': amount,
                })

    def balance_lateral(self, tank_a: str, tank_b: str, tolerance_pct: float = 2.0,
                         rate_kg_per_s: float = 5.0, dt_seconds: float = 1.0):
        """
        One-shot lateral balancing between two symmetric tanks (e.g. Main
        Left / Main Right) -- transfers from whichever is fuller toward
        whichever is emptier if the imbalance exceeds tolerance_pct.
        """
        pct_a = self._pct_full(tank_a)
        pct_b = self._pct_full(tank_b)
        if pct_a is None or pct_b is None:
            return
        imbalance = pct_a - pct_b
        if abs(imbalance) <= tolerance_pct:
            return
        amount = rate_kg_per_s * dt_seconds
        if imbalance > 0:
            self.fuel_system.transfer_fuel(tank_a, tank_b, amount)
        else:
            self.fuel_system.transfer_fuel(tank_b, tank_a, amount)
        logger.info(f"[FUEL_XFER] Lateral balance {tank_a}<->{tank_b}: "
                    f"imbalance was {imbalance:.1f}pp")

    def get_transfer_log(self) -> List[Dict]:
        return list(self._transfer_log)

    def get_status(self) -> Dict:
        return {
            'rule_count': len(self._rules),
            'transfers_performed': len(self._transfer_log),
        }
