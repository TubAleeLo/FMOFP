"""
Thrust Management System

Coordinates commanded thrust across the aircraft's engines: manual throttle
lever inputs, autothrottle (airspeed-hold) mode, and asymmetric-thrust
safety limiting. This sits above the per-engine simulation in
EngineControlUnit (engineManagement/ecu/engineControlUnit.py) -- ECU models
a single engine's internal parameters (N1/N2/EGT/fuel flow), while this
class is responsible for deciding what thrust % each named engine should be
commanded to.
"""

import threading
import time
from typing import Dict, Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Maximum allowed difference between any two engines' commanded thrust
# before it's flagged as a dangerous asymmetric-thrust condition.
MAX_SAFE_THRUST_ASYMMETRY_PCT = 25.0

_tms_instance = None


class ThrustManagementSystem:
    """Coordinates commanded thrust across one or more named engines."""

    def __init__(self):
        self._engine_thrust: Dict[str, float] = {}
        self.autothrottle_engaged = False
        self.target_airspeed_kts: Optional[float] = None
        self._at_last_error = 0.0
        self._at_integral = 0.0
        self._running = threading.Event()
        self._thread = None
        self._start_lock = threading.Lock()

    def register_engine(self, engine_name: str, initial_thrust_pct: float = 0.0):
        self._engine_thrust[engine_name] = max(0.0, min(100.0, initial_thrust_pct))
        logger.info(f"[TMS] Registered engine {engine_name} at {initial_thrust_pct:.1f}% thrust")

    def set_thrust(self, engine_name: str, pct: float) -> bool:
        """Manual throttle lever input for one engine. Returns False if unknown engine."""
        if engine_name not in self._engine_thrust:
            logger.warning(f"[TMS] set_thrust: unknown engine {engine_name}")
            return False
        self._engine_thrust[engine_name] = max(0.0, min(100.0, pct))
        return True

    def set_all_thrust(self, pct: float):
        """Symmetric thrust command across every registered engine."""
        for name in self._engine_thrust:
            self._engine_thrust[name] = max(0.0, min(100.0, pct))

    def get_thrust(self, engine_name: str) -> Optional[float]:
        return self._engine_thrust.get(engine_name)

    def get_all_thrust(self) -> Dict[str, float]:
        return dict(self._engine_thrust)

    # ------------------------------------------------------------------ autothrottle

    def engage_autothrottle(self, target_airspeed_kts: float):
        self.autothrottle_engaged = True
        self.target_airspeed_kts = target_airspeed_kts
        self._at_last_error = 0.0
        self._at_integral = 0.0
        logger.info(f"[TMS] Autothrottle engaged, target {target_airspeed_kts:.0f} kts")

    def disengage_autothrottle(self):
        if self.autothrottle_engaged:
            self.autothrottle_engaged = False
            self.target_airspeed_kts = None
            logger.info("[TMS] Autothrottle disengaged")

    def update_autothrottle(self, current_airspeed_kts: float, dt: float):
        """
        Simple PI controller adjusting symmetric thrust to hold
        target_airspeed_kts. No-op if autothrottle isn't engaged.
        """
        if not self.autothrottle_engaged or self.target_airspeed_kts is None or dt <= 0:
            return

        error = self.target_airspeed_kts - current_airspeed_kts
        self._at_integral = max(-50.0, min(50.0, self._at_integral + error * dt))
        kp, ki = 0.5, 0.05
        delta_pct = kp * error + ki * self._at_integral
        self._at_last_error = error

        current_avg = (sum(self._engine_thrust.values()) / len(self._engine_thrust)
                       if self._engine_thrust else 0.0)
        self.set_all_thrust(current_avg + delta_pct)

    # ------------------------------------------------------------------ safety

    def check_asymmetry(self) -> Optional[float]:
        """
        Returns the current max thrust asymmetry (percentage points) between
        any two engines, or None if fewer than 2 engines are registered.
        """
        if len(self._engine_thrust) < 2:
            return None
        values = list(self._engine_thrust.values())
        asymmetry = max(values) - min(values)
        if asymmetry > MAX_SAFE_THRUST_ASYMMETRY_PCT:
            logger.warning(f"[TMS] Asymmetric thrust condition: {asymmetry:.1f}pp "
                            f"(limit {MAX_SAFE_THRUST_ASYMMETRY_PCT}pp)")
        return asymmetry

    def get_status(self) -> Dict:
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'engines': self.get_all_thrust(),
            'autothrottle_engaged': self.autothrottle_engaged,
            'target_airspeed_kts': self.target_airspeed_kts,
            'asymmetry_pct': self.check_asymmetry(),
        }

    # ------------------------------------------------------------------ lifecycle

    def _update_loop(self):
        """
        Background driver: while autothrottle is engaged, periodically pull
        current airspeed from the FMS and feed it into update_autothrottle().
        When autothrottle isn't engaged, this loop just idles -- manual
        set_thrust()/set_all_thrust() calls take effect immediately and
        don't need a background loop to apply.
        """
        logger.info("[TMS] Update loop started")
        last = time.time()
        while not self._running.is_set():
            try:
                now = time.time()
                dt = now - last
                last = now
                if self.autothrottle_engaged:
                    from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
                    fms = get_flightManagementSystem()
                    airspeed_kts = fms.get_flight_data()['velocity'].get('airspeed', 0.0)
                    self.update_autothrottle(airspeed_kts, dt)
                self.check_asymmetry()
            except Exception as e:
                logger.error(f"[TMS] Update error: {e}")
                # NOTE (production readiness re-analysis, August 2026): this was
                # `time.sleep(5)`, which is NOT interruptible by stop() setting the
                # Event -- live-verified (via ThrustManagementSystem, same pattern)
                # that calling stop() while a thread is in this backoff sleep makes
                # stop()'s join(timeout=2) time out and return while the thread is
                # still alive, misleadingly logging "stopped" up to ~3s before the
                # thread actually exits. Event.wait(timeout) is interruptible by
                # .set(), so stop() now wakes this immediately instead of waiting
                # out the full backoff.
                self._running.wait(5)
                continue
            time.sleep(0.5)  # 2 Hz

    def start(self):
        # Guarded by a dedicated lock -- see PowerManagementSystem.start()'s
        # comment for the full TOCTOU race explanation confirmed live via
        # an extended boot test; same fix applied here.
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="TMS_Update")
            self._thread.start()
            logger.info("[TMS] Thrust Management System started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[TMS] Thrust Management System stopped")


def get_thrust_management_system() -> "ThrustManagementSystem":
    global _tms_instance
    if _tms_instance is None:
        _tms_instance = ThrustManagementSystem()
        # Twin-engine configuration, following the precedent already set by
        # FuelManagementSystem.setup_aircraft() (Engine 1 / Engine 2, the
        # only existing source of an engine-count decision for the B20SS
        # anywhere in this codebase).
        _tms_instance.register_engine("Engine 1", 0.0)
        _tms_instance.register_engine("Engine 2", 0.0)
    return _tms_instance
