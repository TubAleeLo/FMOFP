"""
Engine Control Unit (ECU)

Simulates a turbofan engine for the B20SS:
  - Thrust, N1/N2 RPM, EGT, fuel flow, oil pressure/temp, vibration
  - Persists via current DBM API (flight_control_computer db)
  - Publishes get_data() for EICAS and FMS consumers
  - Singleton: get_engine_control_unit()
"""

import random
import math
import time
import threading
import json
from typing import Dict, Any

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_ecu_instance = None


class EngineControlUnit:
    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None

        # Engine state
        self.thrust_pct     = 70.0    # 0-100 %
        self.n1_pct         = 78.5    # fan speed %
        self.n2_pct         = 84.2    # core speed %
        self.egt_c          = 665.0   # exhaust gas temp °C
        self.ff_kgh         = 2400.0  # fuel flow kg/h
        self.oil_psi        = 60.0
        self.oil_temp_c     = 92.0
        self.vibration      = 0.3
        self.compressor_eff = 88.0    # %

        self._ecu_data: Dict[str, Any] = {}
        self._db = None
        self._init_db()

    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('flight_control_computer')
            self._db.create_table('ecu_data', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[ECU] Database initialised")
        except Exception as e:
            logger.warning(f"[ECU] DB init failed (non-fatal): {e}")

    def _adjust(self):
        t = time.time()
        with self._lock:
            self.thrust_pct     = max(0, min(100, self.thrust_pct + random.uniform(-0.5, 0.5)))
            self.n1_pct         = 0.80 * self.thrust_pct + 18 + random.gauss(0, 0.1)
            self.n2_pct         = 0.75 * self.thrust_pct + 22 + random.gauss(0, 0.1)
            self.egt_c          = 350 + self.thrust_pct * 4.5 + random.gauss(0, 1)
            self.ff_kgh         = self.thrust_pct * 42 + random.gauss(0, 5)
            self.oil_psi        = 60 + 4 * math.sin(t * 0.1) + random.gauss(0, 0.2)
            self.oil_temp_c     = 92 + 8 * math.sin(t * 0.05 + 1) + random.gauss(0, 0.1)
            self.vibration      = 0.2 + 0.15 * abs(math.sin(t * 0.3)) + random.gauss(0, 0.01)
            self.compressor_eff = max(75, min(98, self.compressor_eff + random.uniform(-0.1, 0.1)))

    def _snapshot(self):
        with self._lock:
            self._ecu_data = {
                'thrust_pct':     round(self.thrust_pct, 2),
                'n1_pct':         round(self.n1_pct, 2),
                'n2_pct':         round(self.n2_pct, 2),
                'egt_c':          round(self.egt_c, 1),
                'ff_kgh':         round(self.ff_kgh, 1),
                'oil_psi':        round(self.oil_psi, 2),
                'oil_temp_c':     round(self.oil_temp_c, 2),
                'vibration':      round(self.vibration, 3),
                'compressor_eff': round(self.compressor_eff, 2),
                'timestamp':      time.time(),
            }

    def _persist(self):
        if self._db is None:
            return
        try:
            self._db.insert_into_table('ecu_data', {
                'timestamp': self._ecu_data['timestamp'],
                'data':      json.dumps(self._ecu_data),
            })
        except Exception as e:
            logger.debug(f"[ECU] DB insert skipped: {e}")

    def _update_loop(self):
        logger.info("[ECU] Update loop started")
        while not self._running.is_set():
            try:
                self._adjust()
                self._snapshot()
                self._persist()
            except Exception as e:
                logger.error(f"[ECU] Update error: {e}")
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
            time.sleep(0.5)   # 2 Hz

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
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="ECU_Update")
            self._thread.start()
            logger.info("[ECU] Engine Control Unit started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[ECU] Engine Control Unit stopped")

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._ecu_data)

    def get_status(self) -> Dict[str, Any]:
        return {'running': self._thread is not None and self._thread.is_alive(),
                'healthy': True, **self.get_data()}

    def set_thrust(self, pct: float):
        with self._lock:
            self.thrust_pct = max(0, min(100, float(pct)))


def get_engine_control_unit() -> EngineControlUnit:
    global _ecu_instance
    if _ecu_instance is None:
        _ecu_instance = EngineControlUnit()
    return _ecu_instance
