"""
Communications Messaging Service

Unified manager for all comms subsystems (radio, satcom, data link).
Starts each subsystem's update loop and exposes get_data() for the MFD
comms page and EICAS.

Singleton: get_comms_service()
"""

import threading
import time
import random
import json
from typing import Dict, Any

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_comms_service = None


class CommsService:
    """Lightweight wrapper that owns radio, satcom, and data-link state."""

    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None
        self._db      = None
        self._init_db()

        # Radio state
        self._radio = {
            'frequency':      118.0,   # MHz
            'mode':           'AM',
            'volume':         50,
            'squelch':        3,
            'signal_strength': 0.0,
            'active':         False,
        }

        # SatCom state
        self._satcom = {
            'connection_status': 'disconnected',
            'signal_strength':   0.0,
            'data_rate_kbps':    0.0,
            'latency_ms':        0.0,
            'satellite_id':      None,
        }

        # Data link state
        self._datalink = {
            'link_status':       'inactive',
            'mode':              'LOS',
            'channel':           1,
            'packets_sent':      0,
            'packets_received':  0,
            'error_rate':        0.0,
        }

    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('radio')
            self._db.create_table('comms_data', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'subsystem': 'TEXT NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[COMMS] Database initialised")
        except Exception as e:
            logger.warning(f"[COMMS] DB init failed (non-fatal): {e}")

    # ------------------------------------------------------------------ simulation

    def _simulate(self):
        with self._lock:
            # Radio
            self._radio['signal_strength'] = max(0, min(100,
                self._radio['signal_strength'] + random.uniform(-3, 3)))
            self._radio['active'] = self._radio['signal_strength'] > 20

            # SatCom
            if self._satcom['connection_status'] == 'connected':
                self._satcom['signal_strength'] = max(0, min(100,
                    self._satcom['signal_strength'] + random.uniform(-1, 1)))
                self._satcom['data_rate_kbps'] = max(0,
                    self._satcom['data_rate_kbps'] + random.uniform(-5, 5))
                self._satcom['latency_ms'] = max(200,
                    self._satcom['latency_ms'] + random.uniform(-10, 10))
            else:
                if random.random() < 0.01:
                    self._satcom['connection_status'] = 'connected'
                    self._satcom['signal_strength']   = random.uniform(40, 80)
                    self._satcom['data_rate_kbps']    = random.uniform(50, 200)
                    self._satcom['latency_ms']        = random.uniform(200, 600)
                    self._satcom['satellite_id']      = random.randint(1, 12)
                elif self._satcom['connection_status'] == 'acquiring':
                    if random.random() < 0.05:   # 5% per tick while acquiring
                        self._satcom['connection_status'] = 'connected'
                        self._satcom['signal_strength']   = random.uniform(40, 80)
                        self._satcom['data_rate_kbps']    = random.uniform(50, 200)
                        self._satcom['latency_ms']        = random.uniform(200, 600)
                        self._satcom['satellite_id']      = random.randint(1, 12)
                        logger.info("[COMMS] Satellite acquired")

            # Data link
            if self._satcom['connection_status'] == 'connected':
                self._datalink['link_status'] = 'active'
                self._datalink['packets_sent']     += random.randint(0, 2)
                self._datalink['packets_received'] += random.randint(0, 2)
                self._datalink['error_rate'] = max(0,
                    self._datalink['error_rate'] + random.uniform(-0.1, 0.1))
            else:
                self._datalink['link_status'] = 'inactive'

    def _persist(self):
        if self._db is None:
            return
        try:
            ts = time.time()
            for subsystem, data in [('radio',   self._radio),
                                    ('satcom',  self._satcom),
                                    ('datalink', self._datalink)]:
                self._db.insert_into_table('comms_data', {
                    'timestamp': ts,
                    'subsystem': subsystem,
                    'data':      json.dumps(data),
                })
        except Exception as e:
            logger.debug(f"[COMMS] DB insert skipped: {e}")

    def _update_loop(self):
        logger.info("[COMMS] Update loop started")
        while not self._running.is_set():
            try:
                self._simulate()
                self._persist()
            except Exception as e:
                logger.error(f"[COMMS] Update error: {e}")
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
            time.sleep(1.0)   # 1 Hz

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
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="COMMS_Update")
            self._thread.start()
            logger.info("[COMMS] Communications service started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[COMMS] Communications service stopped")

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'radio':    dict(self._radio),
                'satcom':   dict(self._satcom),
                'datalink': dict(self._datalink),
            }

    def get_status(self) -> Dict[str, Any]:
        d = self.get_data()
        return {'running': self._thread is not None and self._thread.is_alive(),
                'healthy': True, **d}

    # Manual controls
    def set_radio_frequency(self, freq: float):
        with self._lock:
            self._radio['frequency'] = round(float(freq), 3)

    def set_radio_mode(self, mode: str):
        with self._lock:
            if mode in ('AM', 'FM', 'USB', 'LSB'):
                self._radio['mode'] = mode

    def set_radio_volume(self, volume: int) -> None:
        with self._lock:
            self._radio['volume'] = max(0, min(100, int(volume)))

    def set_radio_squelch(self, squelch: int) -> None:
        with self._lock:
            self._radio['squelch'] = max(0, min(9, int(squelch)))

    def transmit_radio(self, message: str) -> bool:
        with self._lock:
            active = self._radio.get('active', False)
        if active:
            logger.info(f"[COMMS] Radio TX: {message[:80]}")
            return True
        logger.warning("[COMMS] Radio TX failed: no signal")
        return False

    def acquire_satellite(self) -> None:
        """Trigger a satellite acquisition attempt (sets status to 'acquiring')."""
        with self._lock:
            if self._satcom['connection_status'] != 'connected':
                self._satcom['connection_status'] = 'acquiring'
                logger.info("[COMMS] Satellite acquisition triggered")

    def send_satcom(self, message: str) -> bool:
        with self._lock:
            connected = self._satcom['connection_status'] == 'connected'
        if connected:
            logger.info(f"[COMMS] SatCom TX: {message[:80]}")
            return True
        logger.warning("[COMMS] SatCom TX failed: not connected")
        return False

    def set_datalink_mode(self, mode: str) -> None:
        if mode in ('LOS', 'BLOS'):
            with self._lock:
                self._datalink['mode'] = mode
            logger.info(f"[COMMS] DataLink mode → {mode}")

    def set_datalink_channel(self, channel: int) -> None:
        with self._lock:
            self._datalink['channel'] = max(1, min(20, int(channel)))

    def send_datalink(self, message: str, priority: int = 2) -> bool:
        with self._lock:
            active = self._datalink.get('link_status') == 'active'
        if active:
            with self._lock:
                self._datalink['packets_sent'] += 1
            logger.info(f"[COMMS] DataLink TX (pri={priority}): {message[:80]}")
            return True
        logger.warning("[COMMS] DataLink TX failed: link inactive")
        return False


def get_comms_service() -> CommsService:
    global _comms_service
    if _comms_service is None:
        _comms_service = CommsService()
    return _comms_service
