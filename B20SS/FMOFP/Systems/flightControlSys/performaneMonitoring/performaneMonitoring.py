"""
Performance Monitoring System

Tracks flight envelope exceedances and engine performance:
  - G-force, AoA, bank angle, pitch rate exceedances
  - Engine TIT/EGT trend monitoring
  - Fuel efficiency (nm per kg)
  - Generates advisory alerts for EICAS

Singleton: get_performance_monitor()
"""

import time
import threading
from typing import Dict, Any, List
from dataclasses import dataclass, field

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_perf_monitor = None


@dataclass
class Exceedance:
    parameter: str
    value:     float
    limit:     float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {'parameter': self.parameter,
                'value': round(self.value, 2),
                'limit': self.limit,
                'ts': self.timestamp}


class PerformanceMonitor:

    # Envelope limits
    LIMITS = {
        'g_force':          9.0,
        'angle_of_attack':  25.0,
        'roll':             60.0,
        'pitch':            45.0,
        'vertical_speed':   6000,   # fpm
    }

    HISTORY_MAX = 200   # keep last N readings

    def __init__(self):
        self._lock         = threading.Lock()
        self._running      = threading.Event()
        self._thread       = None
        self._exceedances: List[Exceedance] = []
        self._history:     List[Dict]       = []
        self._fuel_eff_hist: List[float]    = []

    def _get_state(self) -> Dict:
        try:
            from FMOFP.Systems.flightControlSys.flightControlComputer.flightControlComputer import get_flight_control_computer
            return get_flight_control_computer().get_data()
        except Exception:
            return {}

    def _get_engine(self) -> Dict:
        try:
            from FMOFP.Systems.engineManagement.ecu.engineControlUnit import get_engine_control_unit
            return get_engine_control_unit().get_data()
        except Exception:
            return {}

    def _check_envelope(self, state: Dict):
        now = time.time()
        new_exc = []
        for param, limit in self.LIMITS.items():
            val = abs(state.get(param, 0))
            if val > limit:
                exc = Exceedance(param, val, limit, now)
                new_exc.append(exc)
                logger.warning(
                    f"[PERF] ENVELOPE EXCEEDANCE: {param}={val:.1f} (limit {limit})")

        with self._lock:
            self._exceedances = new_exc

    def _compute_fuel_efficiency(self, state: Dict, engine: Dict) -> float:
        """nm per kg — rough metric."""
        speed_kts = state.get('speed', 0)
        ff_kgh    = engine.get('ff_kgh', 1)
        if ff_kgh <= 0:
            return 0.0
        return round(speed_kts / (ff_kgh / 60), 3)   # nm per kg

    def _record_history(self, state: Dict, engine: Dict, eff: float):
        entry = {
            'ts':         time.time(),
            'altitude':   state.get('altitude', 0),
            'speed':      state.get('speed', 0),
            'g_force':    state.get('g_force', 1),
            'n1_pct':     engine.get('n1_pct', 0),
            'egt_c':      engine.get('egt_c', 0),
            'ff_kgh':     engine.get('ff_kgh', 0),
            'fuel_eff':   eff,
        }
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self.HISTORY_MAX:
                self._history.pop(0)
            self._fuel_eff_hist.append(eff)
            if len(self._fuel_eff_hist) > self.HISTORY_MAX:
                self._fuel_eff_hist.pop(0)

    def _update_loop(self):
        logger.info("[PERF] Performance monitor loop started")
        while not self._running.is_set():
            try:
                state  = self._get_state()
                engine = self._get_engine()
                if state:
                    self._check_envelope(state)
                    eff = self._compute_fuel_efficiency(state, engine)
                    self._record_history(state, engine, eff)
            except Exception as e:
                logger.error(f"[PERF] Update error: {e}")
            time.sleep(1.0)

    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # newer subsystem singletons -- see PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py). Reuses
        # the existing data lock; start() never touches the data it
        # guards, so no reentrancy risk.
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(
                target=self._update_loop, daemon=True, name="PERF_Monitor")
            self._thread.start()
            logger.info("[PERF] Performance monitor started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)

    def get_exceedances(self) -> List[Dict]:
        with self._lock:
            return [e.to_dict() for e in self._exceedances]

    def get_avg_fuel_efficiency(self) -> float:
        with self._lock:
            if not self._fuel_eff_hist:
                return 0.0
            return round(sum(self._fuel_eff_hist) / len(self._fuel_eff_hist), 3)

    def get_status(self) -> Dict[str, Any]:
        # NOTE (production readiness re-analysis, August 2026): 'history_len'
        # used to read len(self._history) directly here, unlike its two sibling
        # values above which both go through locked accessors (get_exceedances(),
        # get_avg_fuel_efficiency()) -- _record_history() mutates self._history
        # under self._lock (append + pop(0) every ~1s from the update loop), so
        # this was the one inconsistent unlocked read in an otherwise
        # consistently-locked class. len() on a list is GIL-atomic so this was
        # never a crash risk, just a momentary staleness/consistency gap versus
        # its neighbors; locked for consistency.
        with self._lock:
            history_len = len(self._history)
        return {
            'running':      self._thread is not None and self._thread.is_alive(),
            'exceedances':  self.get_exceedances(),
            'avg_fuel_eff': self.get_avg_fuel_efficiency(),
            'history_len':  history_len,
        }


def get_performance_monitor() -> PerformanceMonitor:
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor
