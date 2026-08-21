"""
Flight Control Computer (FCC)

Simulates the B20SS flight control computer:
  - Continuous flight parameter simulation (attitude, speed, heading)
  - Derives g-force, AOA, vertical speed, flap/gear state
  - Persists data via the current DBM API (flight_control_computer system db)
  - Publishes data through get_data() for FMS and display consumers
  - Singleton factory: get_flight_control_computer()
"""

import random
import time
import threading
import json
from typing import Dict, Any

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_flight_control_computer = None


class FlightControlComputer:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._thread = None

        # Core flight state
        self.altitude        = 10000.0   # feet
        self.speed           = 500.0     # knots
        self.heading         = 0.0       # degrees
        self.pitch           = 0.0       # degrees
        self.roll            = 0.0       # degrees
        self.vertical_speed  = 0.0       # feet/min
        self.angle_of_attack = 2.0       # degrees
        self.g_force         = 1.0
        self.flaps           = 0         # degrees
        self.landing_gear    = 'up'

        self._fcs_data: Dict[str, Any] = {}

        # DBM via current API
        self._db = None
        self._init_db()

    # ------------------------------------------------------------------
    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('flight_control_computer')
            self._db.create_table('fcs_data', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[FCC] Database initialised")
        except Exception as e:
            logger.warning(f"[FCC] DB init failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    def _adjust(self):
        """Random-walk all flight parameters within realistic envelopes."""
        with self._lock:
            self.altitude        += random.uniform(-50, 50)
            self.speed           += random.uniform(-5, 5)
            self.heading          = (self.heading + random.uniform(-1, 1)) % 360
            self.pitch           += random.uniform(-0.5, 0.5)
            self.roll            += random.uniform(-0.5, 0.5)
            self.vertical_speed   = random.uniform(-500, 500)
            self.angle_of_attack  = max(0, self.angle_of_attack + random.uniform(-0.2, 0.2))
            self.g_force          = max(0.5, min(9.0, self.g_force + random.uniform(-0.05, 0.05)))

            self.altitude         = max(0, min(60000, self.altitude))
            self.speed            = max(100, min(1000, self.speed))
            self.pitch            = max(-45, min(45, self.pitch))
            self.roll             = max(-60, min(60, self.roll))
            self.angle_of_attack  = min(25, self.angle_of_attack)

    def _snapshot(self):
        with self._lock:
            self._fcs_data = {
                'altitude':        round(self.altitude, 2),
                'speed':           round(self.speed, 2),
                'heading':         round(self.heading, 2),
                'pitch':           round(self.pitch, 2),
                'roll':            round(self.roll, 2),
                'vertical_speed':  round(self.vertical_speed, 2),
                'angle_of_attack': round(self.angle_of_attack, 2),
                'g_force':         round(self.g_force, 3),
                'flaps':           self.flaps,
                'landing_gear':    self.landing_gear,
                'timestamp':       time.time(),
            }

    def _persist(self):
        if self._db is None:
            return
        try:
            self._db.insert_into_table('fcs_data', {
                'timestamp': self._fcs_data['timestamp'],
                'data':      json.dumps(self._fcs_data),
            })
        except Exception as e:
            logger.debug(f"[FCC] DB insert skipped: {e}")

    def _update_loop(self):
        logger.info("[FCC] Update loop started")
        while not self._running.is_set():
            try:
                self._adjust()
                self._snapshot()
                self._persist()
            except Exception as e:
                logger.error(f"[FCC] Update error: {e}")
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
            time.sleep(0.1)   # 10 Hz

    # ------------------------------------------------------------------ public API
    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # other subsystem singletons -- see PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py). Reuses
        # the existing data lock; start() never touches the data it
        # guards, so no reentrancy risk.
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="FCC_Update")
            self._thread.start()
            logger.info("[FCC] Flight Control Computer started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[FCC] Flight Control Computer stopped")

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._fcs_data)

    def get_status(self) -> Dict[str, Any]:
        return {'running': self._thread is not None and self._thread.is_alive(),
                'healthy': True, **self.get_data()}

    # Manual overrides (used by CLI / tests)
    def set_altitude(self, v):
        with self._lock: self.altitude = float(v)
    def set_speed(self, v):
        with self._lock: self.speed = float(v)
    def set_heading(self, v):
        with self._lock: self.heading = float(v) % 360


def get_flight_control_computer() -> FlightControlComputer:
    global _flight_control_computer
    if _flight_control_computer is None:
        _flight_control_computer = FlightControlComputer()
    return _flight_control_computer
