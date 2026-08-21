"""
LRU (Line Replaceable Unit) Status Monitor

Tracks the health state of every avionics LRU on the B20SS.  An LRU is any
field-replaceable avionics box: FCC, FMS, Nav computer, radar processor, etc.

Design:
  - LRUStatusMonitor polls each known LRU at a configurable rate
  - Each LRU has a HealthState (NOMINAL / DEGRADED / FAULT / OFFLINE)
  - Health state is derived from the system's own get_status() call and from
    the most recent BIT result for that LRU (from builtInTesting.BITResult)
  - The monitor exposes get_all() → dict keyed by LRU id for EICAS consumption
  - Thread-safe singleton: get_lru_monitor()

LRU catalogue is defined here and matches the systems started by SystemManager.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_lru_monitor = None


# ── Health state ──────────────────────────────────────────────────────────────

class HealthState(str, Enum):
    NOMINAL  = "NOMINAL"    # fully operational
    DEGRADED = "DEGRADED"   # operating with reduced capability
    FAULT    = "FAULT"      # non-operational fault detected
    OFFLINE  = "OFFLINE"    # not yet started or unreachable
    UNKNOWN  = "UNKNOWN"    # no status available yet


# ── LRU descriptor ────────────────────────────────────────────────────────────

@dataclass
class LRU:
    lru_id:      str               # e.g. "FCC-1"
    name:        str               # human-readable e.g. "Flight Control Computer"
    system_key:  str               # matches SystemManager component key
    accessor:    Optional[Callable] = field(default=None, repr=False)
                                   # callable → singleton; populated at runtime
    health:      HealthState       = HealthState.UNKNOWN
    last_status: Dict[str, Any]    = field(default_factory=dict)
    last_checked: float            = 0.0
    fault_detail: str              = ""
    bit_result:   Optional[str]    = None   # most recent BIT result string

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lru_id":       self.lru_id,
            "name":         self.name,
            "health":       self.health.value,
            "fault_detail": self.fault_detail,
            "bit_result":   self.bit_result,
            "last_checked": self.last_checked,
        }


# ── LRU catalogue ─────────────────────────────────────────────────────────────

def _build_catalogue() -> Dict[str, LRU]:
    """Define all known LRUs and their system accessor callables."""

    def _acc(import_path: str, func: str) -> Optional[Callable]:
        """Build a lazy accessor that imports and returns the singleton."""
        def _get():
            try:
                mod = __import__(import_path, fromlist=[func])
                return getattr(mod, func)()
            except Exception:
                return None
        return _get

    entries = [
        LRU("FCC-1",  "Flight Control Computer",
            "flight_control_computer",
            _acc("FMOFP.Systems.flightControlSys.flightControlComputer.flightControlComputer",
                 "get_flight_control_computer")),

        LRU("FMS-1",  "Flight Management System",
            "flightManagementSystem",
            _acc("FMOFP.Systems.flightManagementSys.flightManagementSystem",
                 "get_flightManagementSystem")),

        LRU("NAV-1",  "Navigation Service",
            "nav_service",
            _acc("FMOFP.Systems.nav.navService", "get_nav_service")),

        LRU("RDR-1",  "Radar Management",
            "radar_management",
            _acc("FMOFP.Systems.radarManagement.radarControl",
                 "get_radar_management_system")),

        LRU("ECU-1",  "Engine Control Unit",
            "engine_control_unit",
            _acc("FMOFP.Systems.engineManagement.ecu.engineControlUnit",
                 "get_engine_control_unit")),

        LRU("COMMS-1","Communications Service",
            "comms_service",
            _acc("FMOFP.Systems.comms.messaging_service", "get_comms_service")),

        LRU("MSN-1",  "Mission Planning Service",
            "mission_service",
            _acc("FMOFP.Systems.missionPlanning.missionService",
                 "get_mission_service")),

        LRU("DFS-1",  "Defensive Systems Service",
            "defensive_service",
            _acc("FMOFP.Systems.defensiveSys.defensiveService",
                 "get_defensive_service")),

        LRU("SNS-1",  "Sensor Service",
            "sensor_service",
            _acc("FMOFP.Systems.sensorManagement.sensorService",
                 "get_sensor_service")),

        LRU("GCAS-1", "Ground Collision Avoidance",
            "gcas",
            _acc("FMOFP.Systems.flightControlSys.groundCollisionAvoidanceSys"
                 ".groundCollisionAvoidanceSys", "get_gcas")),

        LRU("PERF-1", "Performance Monitor",
            "performance_monitor",
            _acc("FMOFP.Systems.flightControlSys.performaneMonitoring"
                 ".performaneMonitoring", "get_performance_monitor")),
    ]

    return {lru.lru_id: lru for lru in entries}


# ── Status derivation ─────────────────────────────────────────────────────────

def _derive_health(status: Dict[str, Any], lru: LRU) -> HealthState:
    """
    Derive a HealthState from a system's get_status() dict.

    Checks (in priority order):
      1. 'running' key — False → FAULT
      2. 'healthy' key — False → DEGRADED
      3. 'health' key — maps string value
      4. Most recent BIT result — FAIL → DEGRADED
      5. Default → NOMINAL
    """
    if not status:
        return HealthState.OFFLINE

    if status.get("running") is False:
        return HealthState.FAULT

    if status.get("healthy") is False:
        return HealthState.DEGRADED

    health_str = str(status.get("health", "")).upper()
    if health_str in ("FAULT", "ERROR", "FAILED"):
        return HealthState.FAULT
    if health_str in ("DEGRADED", "WARNING", "WARN"):
        return HealthState.DEGRADED
    if health_str in ("NOMINAL", "RUNNING", "NORMAL", "OK"):
        return HealthState.NOMINAL

    # Fall back to BIT result
    if lru.bit_result and "FAIL" in lru.bit_result:
        return HealthState.DEGRADED

    return HealthState.NOMINAL


# ── Monitor ───────────────────────────────────────────────────────────────────

class LRUStatusMonitor:
    """
    Polls all LRUs at POLL_HZ and maintains a current health snapshot.
    Thread-safe; designed to run as a daemon thread.
    """

    POLL_HZ = 1   # 1 Hz — LRU health changes slowly

    def __init__(self):
        self._lrus      = _build_catalogue()
        self._lock      = threading.Lock()
        self._stop_evt  = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="LRUStatusMonitor"
        )
        self._thread.start()
        logger.info("[LRU] Status monitor started")

    def stop(self):
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[LRU] Status monitor stopped")

    # ── public API ────────────────────────────────────────────────────────────

    def get_all(self) -> Dict[str, Dict]:
        """Return health snapshot for all LRUs."""
        with self._lock:
            return {lru_id: lru.to_dict() for lru_id, lru in self._lrus.items()}

    def get_lru(self, lru_id: str) -> Optional[Dict]:
        """Return health snapshot for a single LRU by id."""
        with self._lock:
            lru = self._lrus.get(lru_id)
            return lru.to_dict() if lru else None

    def get_faults(self) -> List[Dict]:
        """Return all LRUs currently in FAULT or DEGRADED state."""
        with self._lock:
            return [
                lru.to_dict() for lru in self._lrus.values()
                if lru.health in (HealthState.FAULT, HealthState.DEGRADED)
            ]

    def update_bit_result(self, lru_id: str, result_str: str):
        """
        Inject the latest BIT result string for an LRU.
        Called by builtInTesting after a BIT run.
        """
        with self._lock:
            if lru_id in self._lrus:
                self._lrus[lru_id].bit_result = result_str

    def overall_health(self) -> HealthState:
        """Aggregate health: worst state across all LRUs."""
        with self._lock:
            states = [lru.health for lru in self._lrus.values()]
        if HealthState.FAULT    in states: return HealthState.FAULT
        if HealthState.DEGRADED in states: return HealthState.DEGRADED
        if HealthState.OFFLINE  in states: return HealthState.DEGRADED
        if HealthState.UNKNOWN  in states: return HealthState.UNKNOWN
        return HealthState.NOMINAL

    def get_status(self) -> Dict[str, Any]:
        """SystemManager-compatible status dict."""
        return {
            "running":         self._thread is not None and self._thread.is_alive(),
            "healthy":         self.overall_health() != HealthState.FAULT,
            "overall_health":  self.overall_health().value,
            "lru_count":       len(self._lrus),
            "fault_count":     len(self.get_faults()),
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _poll_loop(self):
        interval = 1.0 / self.POLL_HZ
        while not self._stop_evt.is_set():
            try:
                self._poll_all()
            except Exception as exc:
                logger.error(f"[LRU] Poll error: {exc}")
            self._stop_evt.wait(interval)

    def _poll_all(self):
        for lru in self._lrus.values():
            self._poll_lru(lru)

    def _poll_lru(self, lru: LRU):
        if lru.accessor is None:
            return

        try:
            instance = lru.accessor()
            if instance is None:
                new_health = HealthState.OFFLINE
                status     = {}
                fault      = "system not started"
            elif hasattr(instance, "get_status"):
                status     = instance.get_status() or {}
                new_health = _derive_health(status, lru)
                fault      = status.get("fault_detail", "")
            else:
                # Instance exists but has no get_status — treat as nominal
                status     = {}
                new_health = HealthState.NOMINAL
                fault      = ""

        except Exception as exc:
            new_health = HealthState.UNKNOWN
            status     = {}
            fault      = str(exc)[:80]

        with self._lock:
            if lru.health != new_health:
                logger.info(
                    f"[LRU] {lru.lru_id} ({lru.name}): "
                    f"{lru.health.value} → {new_health.value}"
                    + (f" [{fault}]" if fault else "")
                )
            lru.health       = new_health
            lru.last_status  = status
            lru.last_checked = time.time()
            lru.fault_detail = fault


# ── Singleton ─────────────────────────────────────────────────────────────────

_monitor_lock = threading.Lock()


def get_lru_monitor() -> LRUStatusMonitor:
    global _lru_monitor
    with _monitor_lock:
        if _lru_monitor is None:
            _lru_monitor = LRUStatusMonitor()
    return _lru_monitor
