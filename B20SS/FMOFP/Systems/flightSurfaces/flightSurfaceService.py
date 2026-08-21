"""
Flight Surfaces Service

Simulates all B20SS aerodynamic control surfaces:

  Primary:   ailerons, elevators, rudder
  Secondary: flaps (0/5/15/30°), leading-edge slats, speed brakes
  Adaptive:  control surface trim (pitch, roll, yaw)

Receives commands from FlightControlComputer and feeds
feedback into FMS attitude data.

Singleton: get_flight_surface_service()
"""

import math
import random
import threading
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_flight_surface_service = None

# Valid flap settings (degrees)
FLAP_DETENTS = (0, 5, 15, 30)


@dataclass
class Surface:
    """One control surface."""
    name:         str
    position:     float = 0.0    # degrees, positive = trailing-edge down / right
    cmd:          float = 0.0    # commanded position
    rate_deg_s:   float = 30.0   # slew rate
    limit_lo:     float = -30.0
    limit_hi:     float =  30.0
    healthy:      bool  = True

    def step(self, dt: float):
        """Move toward cmd at rate_deg_s."""
        error = self.cmd - self.position
        delta = math.copysign(min(abs(error), self.rate_deg_s * dt), error)
        self.position = max(self.limit_lo, min(self.limit_hi, self.position + delta))


class FlightSurfaceService:

    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None
        self._db      = None
        self._init_db()

        # Primary surfaces
        self.aileron_l  = Surface("aileron_l",  rate_deg_s=60, limit_lo=-25, limit_hi=25)
        self.aileron_r  = Surface("aileron_r",  rate_deg_s=60, limit_lo=-25, limit_hi=25)
        self.elevator_l = Surface("elevator_l", rate_deg_s=50, limit_lo=-30, limit_hi=30)
        self.elevator_r = Surface("elevator_r", rate_deg_s=50, limit_lo=-30, limit_hi=30)
        self.rudder     = Surface("rudder",     rate_deg_s=40, limit_lo=-30, limit_hi=30)

        # Secondary surfaces
        self.flap_l     = Surface("flap_l",     rate_deg_s=5,  limit_lo=0,   limit_hi=30)
        self.flap_r     = Surface("flap_r",     rate_deg_s=5,  limit_lo=0,   limit_hi=30)
        self.slat_l     = Surface("slat_l",     rate_deg_s=5,  limit_lo=0,   limit_hi=20)
        self.slat_r     = Surface("slat_r",     rate_deg_s=5,  limit_lo=0,   limit_hi=20)
        self.speedbrake = Surface("speedbrake", rate_deg_s=30, limit_lo=0,   limit_hi=60)

        # Trim
        self._trim = {'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0}

        # Commanded flap setting
        self._flap_cmd = 0

        self._all: list[Surface] = [
            self.aileron_l, self.aileron_r,
            self.elevator_l, self.elevator_r,
            self.rudder,
            self.flap_l, self.flap_r,
            self.slat_l, self.slat_r,
            self.speedbrake,
        ]

    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('flight_control_computer')
            self._db.create_table('surface_data', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[FSS] Database initialised")
        except Exception as e:
            logger.warning(f"[FSS] DB init failed (non-fatal): {e}")

    # ------------------------------------------------------------------ FCC sync

    def _sync_from_fcc(self):
        """Pull FCC attitude data and derive surface commands."""
        try:
            from FMOFP.Systems.flightControlSys.flightControlComputer.flightControlComputer import get_flight_control_computer
            fcc = get_flight_control_computer()
            data = fcc.get_data()
            if not data:
                return

            roll  = data.get('roll',  0.0)
            pitch = data.get('pitch', 0.0)
            aoa   = data.get('angle_of_attack', 0.0)

            with self._lock:
                # Aileron follows roll demand (simplified fly-by-wire)
                aileron_cmd = max(-25, min(25, -roll * 0.5))
                self.aileron_l.cmd = -aileron_cmd
                self.aileron_r.cmd =  aileron_cmd

                # Elevator follows pitch demand
                elev_cmd = max(-30, min(30, -pitch * 0.8))
                self.elevator_l.cmd = elev_cmd
                self.elevator_r.cmd = elev_cmd

                # Auto-slat: extend when AOA > 8°
                slat_cmd = 20.0 if aoa > 8.0 else 0.0
                self.slat_l.cmd = slat_cmd
                self.slat_r.cmd = slat_cmd

        except Exception as e:
            logger.debug(f"[FSS] FCC sync error: {e}")

    def _step_all(self, dt: float):
        with self._lock:
            for surface in self._all:
                surface.step(dt)

    def _persist(self):
        if self._db is None:
            return
        try:
            self._db.insert_into_table('surface_data', {
                'timestamp': time.time(),
                'data':      json.dumps(self._snapshot()),
            })
        except Exception as e:
            logger.debug(f"[FSS] DB insert skipped: {e}")

    def _snapshot(self) -> Dict:
        return {s.name: round(s.position, 2) for s in self._all}

    def _update_loop(self):
        logger.info("[FSS] Flight surface service loop started")
        last = time.time()
        while not self._running.is_set():
            now = time.time()
            dt  = now - last
            last = now
            try:
                self._sync_from_fcc()
                self._step_all(dt)
                self._persist()
            except Exception as e:
                logger.error(f"[FSS] Update error: {e}")
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
            time.sleep(0.02)  # 50 Hz — fast enough for smooth surface motion

    # ------------------------------------------------------------------ public API

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
                target=self._update_loop, daemon=True, name="FSS_Update")
            self._thread.start()
            logger.info("[FSS] Flight surface service started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[FSS] Flight surface service stopped")

    def set_flaps(self, detent: int):
        """Set flaps to nearest valid detent (0 / 5 / 15 / 30)."""
        nearest = min(FLAP_DETENTS, key=lambda d: abs(d - detent))
        with self._lock:
            self._flap_cmd = nearest
            self.flap_l.cmd = float(nearest)
            self.flap_r.cmd = float(nearest)
        logger.info(f"[FSS] Flaps commanded to {nearest}°")

    def set_speedbrake(self, pct: float):
        """Extend speed brake 0–100%."""
        cmd = max(0, min(60, pct * 0.6))
        with self._lock:
            self.speedbrake.cmd = cmd

    def set_rudder(self, deg: float):
        with self._lock:
            self.rudder.cmd = max(-30, min(30, deg))

    def set_trim(self, axis: str, deg: float):
        if axis in self._trim:
            with self._lock:
                self._trim[axis] = max(-10, min(10, deg))

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'surfaces':  self._snapshot(),
                'flap_cmd':  self._flap_cmd,
                'trim':      dict(self._trim),
                'healthy':   all(s.healthy for s in self._all),
            }

    def get_status(self) -> Dict[str, Any]:
        return {'running': self._thread is not None and self._thread.is_alive(),
                **self.get_data()}


def get_flight_surface_service() -> FlightSurfaceService:
    global _flight_surface_service
    if _flight_surface_service is None:
        _flight_surface_service = FlightSurfaceService()
    return _flight_surface_service
