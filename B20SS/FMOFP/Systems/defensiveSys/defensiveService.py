"""
Defensive Systems Service

Implements the B20SS defensive suite:

  RWR (Radar Warning Receiver)
  - Ingests threat tracks from RadarDataFusion and AEWC radar
  - Classifies emissions by frequency band and threat level
  - Generates prioritised threat list for TSD and EICAS

  Countermeasures Dispenser
  - Chaff and flare inventory management
  - Manual and auto-release modes
  - Salvo sequencing with cooldown

  Electronic Warfare (EW)
  - Jamming state tracking
  - ECM/ECCM mode management

Singleton: get_defensive_service()
"""

import math
import random
import threading
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_defensive_service = None

# ── Threat classification ────────────────────────────────────────────────────

BAND_NAMES = {
    (0.5e9,  2e9):   "L",
    (2e9,    4e9):   "S",
    (4e9,    8e9):   "C",
    (8e9,   12e9):   "X",
    (12e9,  18e9):   "Ku",
    (18e9,  27e9):   "K",
    (27e9,  40e9):   "Ka",
}

THREAT_DB: Dict[str, Dict] = {
    "SA-10":   {"band": "X",  "pri": 1, "type": "SAM"},
    "SA-15":   {"band": "X",  "pri": 1, "type": "SAM"},
    "SA-6":    {"band": "Ku", "pri": 2, "type": "SAM"},
    "FIGHTER": {"band": "X",  "pri": 2, "type": "AIR"},
    "BOMBER":  {"band": "S",  "pri": 3, "type": "AIR"},
    "UNKNOWN": {"band": "?",  "pri": 4, "type": "UNK"},
}


def _classify_freq(freq_hz: float) -> str:
    for (lo, hi), name in BAND_NAMES.items():
        if lo <= freq_hz < hi:
            return name
    return "?"


@dataclass
class RWRContact:
    contact_id:  str
    bearing_deg: float
    range_nm:    float
    band:        str
    threat_type: str
    priority:    int          # 1 = highest
    hostile:     bool
    first_seen:  float = field(default_factory=time.time)
    last_seen:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "contact_id":  self.contact_id,
            "bearing_deg": round(self.bearing_deg, 1),
            "range_nm":    round(self.range_nm, 1),
            "band":        self.band,
            "threat_type": self.threat_type,
            "priority":    self.priority,
            "hostile":     self.hostile,
        }


# ── Main service ─────────────────────────────────────────────────────────────

class DefensiveService:

    CHAFF_MAX  = 60
    FLARE_MAX  = 30
    SALVO_SIZE = 2
    COOLDOWN_S = 3.0
    TRACK_TTL  = 10.0     # seconds before stale track is dropped

    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None
        self._db      = None
        self._init_db()

        # Countermeasures inventory
        self._chaff  = self.CHAFF_MAX
        self._flares = self.FLARE_MAX
        self._last_dispense = 0.0

        # RWR contacts  (id → RWRContact)
        self._contacts: Dict[str, RWRContact] = {}

        # EW state
        self._jamming_active = False
        self._ecm_mode       = "STANDBY"   # STANDBY / ACTIVE / PASSIVE

        # Simulated ESM sensor (passive)
        self._esm = None
        self._fusion = None
        self._load_sensors()

    # ------------------------------------------------------------------ init

    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('default')
            self._db.create_table('defensive_events', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'event':     'TEXT NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[DFS] Database initialised")
        except Exception as e:
            logger.warning(f"[DFS] DB init failed (non-fatal): {e}")

    def _load_sensors(self):
        try:
            from FMOFP.Systems.sensorManagement.passiveSensors.passiveSensors import PassiveSensorManager
            psm = PassiveSensorManager()
            psm.activate_sensor('electronic_support_measures')
            self._esm = psm
            logger.info("[DFS] ESM sensor attached")
        except Exception as e:
            logger.warning(f"[DFS] ESM unavailable: {e}")

        try:
            from FMOFP.Systems.radarManagement.radar_data_fusion import RadarDataFusion
            self._fusion = RadarDataFusion()
            logger.info("[DFS] RadarDataFusion attached")
        except Exception as e:
            logger.warning(f"[DFS] RadarDataFusion unavailable: {e}")

    # ------------------------------------------------------------------ RWR

    def _update_rwr(self):
        """Pull threat tracks from fusion layer and ESM; update contact table."""
        now = time.time()

        # From cross-radar fusion
        if self._fusion:
            try:
                for track in self._fusion.get_threat_tracks():
                    cid = f"FUS-{track.track_id}"
                    entry = THREAT_DB.get(track.classification, THREAT_DB["UNKNOWN"])
                    with self._lock:
                        self._contacts[cid] = RWRContact(
                            contact_id  = cid,
                            bearing_deg = track.bearing_deg(),
                            range_nm    = track.range_nm(),
                            band        = entry["band"],
                            threat_type = entry["type"],
                            priority    = entry["pri"],
                            hostile     = track.is_hostile(),
                            last_seen   = now,
                        )
            except Exception as e:
                logger.debug(f"[DFS] Fusion RWR update error: {e}")

        # From ESM sensor (simulated signal intercepts)
        if self._esm:
            try:
                signals = self._esm.get_sensor_data('electronic_support_measures') or []
                for sig in signals:
                    freq    = sig.get('frequency', 10e9)
                    bearing = sig.get('bearing', random.uniform(0, 360))
                    band    = _classify_freq(freq)
                    cid     = f"ESM-{band}-{int(bearing)}"
                    with self._lock:
                        if cid not in self._contacts:
                            self._contacts[cid] = RWRContact(
                                contact_id  = cid,
                                bearing_deg = bearing,
                                range_nm    = random.uniform(5, 60),
                                band        = band,
                                threat_type = "UNK",
                                priority    = 3,
                                hostile     = True,
                                last_seen   = now,
                            )
                        else:
                            self._contacts[cid].last_seen = now
            except Exception as e:
                logger.debug(f"[DFS] ESM update error: {e}")

        # Expire stale contacts
        with self._lock:
            stale = [k for k, v in self._contacts.items()
                     if now - v.last_seen > self.TRACK_TTL]
            for k in stale:
                del self._contacts[k]

    # ------------------------------------------------------------------ auto-dispense

    def _auto_dispense(self):
        """Auto-release flares if a high-priority IR threat exists."""
        now = time.time()
        with self._lock:
            high_pri = [c for c in self._contacts.values()
                        if c.priority == 1 and c.hostile]
            if high_pri and (now - self._last_dispense) > self.COOLDOWN_S:
                released = min(self.SALVO_SIZE, self._flares)
                if released > 0:
                    self._flares -= released
                    self._last_dispense = now
                    logger.warning(
                        f"[DFS] AUTO: {released} flare(s) released — "
                        f"{len(high_pri)} high-pri threat(s) detected. "
                        f"Remaining: {self._flares}"
                    )
                    self._log_event("auto_flare", {"released": released,
                                                   "threats": len(high_pri)})

    # ------------------------------------------------------------------ persist

    def _log_event(self, event: str, data: Dict):
        if self._db is None:
            return
        try:
            self._db.insert_into_table('defensive_events', {
                'timestamp': time.time(),
                'event':     event,
                'data':      json.dumps(data),
            })
        except Exception as e:
            logger.debug(f"[DFS] DB insert skipped: {e}")

    # ------------------------------------------------------------------ update loop

    def _update_loop(self):
        logger.info("[DFS] Defensive service loop started")
        while not self._running.is_set():
            try:
                self._update_rwr()
                self._auto_dispense()
            except Exception as e:
                logger.error(f"[DFS] Update error: {e}")
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

    # ------------------------------------------------------------------ public API

    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # newer subsystem singletons (see PowerManagementSystem.start(),
        # Systems/powerManagement/elec/powerManagementSystem.py) --
        # system_manager.py's start_FM_system() and
        # start_async_components()'s generic "start remaining components"
        # pass can both call a singleton's start() close enough together
        # to race an unguarded check-then-create. Reuses the existing
        # data lock since start() itself never touches any data this lock
        # guards, so there's no reentrancy risk.
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(
                target=self._update_loop, daemon=True, name="DEFENSIVE_Service")
            self._thread.start()
            logger.info("[DFS] Defensive service started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[DFS] Defensive service stopped")

    # Manual countermeasures
    def dispense_chaff(self, count: int = 1) -> int:
        with self._lock:
            released = min(count, self._chaff)
            self._chaff -= released
            if released:
                logger.info(f"[DFS] Manual: {released} chaff released. Remaining: {self._chaff}")
                self._log_event("manual_chaff", {"released": released})
            return released

    def dispense_flares(self, count: int = 1) -> int:
        with self._lock:
            now = time.time()
            if (now - self._last_dispense) < self.COOLDOWN_S:
                logger.warning("[DFS] Flare cooldown active")
                return 0
            released = min(count, self._flares)
            self._flares -= released
            self._last_dispense = now
            if released:
                logger.info(f"[DFS] Manual: {released} flare(s) released. Remaining: {self._flares}")
                self._log_event("manual_flare", {"released": released})
            return released

    def set_ecm_mode(self, mode: str):
        valid = ("STANDBY", "ACTIVE", "PASSIVE")
        if mode in valid:
            with self._lock:
                self._ecm_mode = mode
                self._jamming_active = (mode == "ACTIVE")
            logger.info(f"[DFS] ECM mode → {mode}")
            self._log_event("ecm_mode_change", {"mode": mode})

    def get_rwr_contacts(self) -> List[Dict]:
        with self._lock:
            return sorted(
                [c.to_dict() for c in self._contacts.values()],
                key=lambda x: x["priority"]
            )

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'chaff_remaining':  self._chaff,
                'flares_remaining': self._flares,
                'ecm_mode':         self._ecm_mode,
                'jamming_active':   self._jamming_active,
                'rwr_contacts':     [c.to_dict() for c in self._contacts.values()],
                'threat_count':     len(self._contacts),
            }

    def get_status(self) -> Dict[str, Any]:
        return {'running': self._thread is not None and self._thread.is_alive(),
                'healthy': True, **self.get_data()}


def get_defensive_service() -> DefensiveService:
    global _defensive_service
    if _defensive_service is None:
        _defensive_service = DefensiveService()
    return _defensive_service
