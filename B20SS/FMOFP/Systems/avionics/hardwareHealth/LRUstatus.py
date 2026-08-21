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
        # Forced-fault overrides (scenario engine / instructor station).
        # {lru_id: (HealthState, detail)} — while an entry exists, _poll_lru
        # reports the forced state for that LRU instead of the state derived
        # from the subsystem's live get_status(). This is the override hook
        # whose absence made scenario "system_failure" events log-only (see
        # scenarioEngine._inject_failure, August 2026 audit note).
        self._forced_faults: Dict[str, tuple] = {}

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

    # ── forced faults (scenario engine / instructor station) ─────────────────

    def resolve_lru_id(self, key: str) -> Optional[str]:
        """Resolve a scenario/instructor system identifier to a catalogued
        LRU id. Accepts (case-insensitive) an exact lru_id ("FCC-1"), an
        exact system_key ("flight_control_computer"), or a unique substring
        of the human-readable name ("flight control"). Returns None when
        nothing matches."""
        needle = (key or "").strip().lower()
        if not needle:
            return None
        with self._lock:
            for lru_id, lru in self._lrus.items():
                if needle == lru_id.lower() or needle == lru.system_key.lower():
                    return lru_id
            name_hits = [
                lru_id for lru_id, lru in self._lrus.items()
                if needle in lru.name.lower()
            ]
        return name_hits[0] if len(name_hits) == 1 else None

    def force_fault(self, key: str, state: HealthState = HealthState.FAULT,
                    detail: str = "", source: str = "scenario") -> str:
        """Force an LRU into a fault state until clear_forced_fault() is
        called. The override survives every poll cycle (_poll_lru applies it
        after live-status derivation), so unlike writing .health directly it
        is not silently overwritten a fraction of a second later.

        `key` is resolved via resolve_lru_id(); an unresolvable key creates a
        synthetic LRU entry (no accessor, so polling leaves it alone) — this
        keeps failure scenarios that name non-LRU systems ("engine_vibration",
        "fuel_transfer", ...) visible in get_all()/get_faults()/EICAS-facing
        aggregates instead of being dropped.

        Returns the lru_id the fault was applied to.
        """
        if not isinstance(state, HealthState):
            state = HealthState(str(state).upper())
        lru_id = self.resolve_lru_id(key)
        with self._lock:
            if lru_id is None:
                lru_id = str(key).strip().upper() or "UNKNOWN"
                if lru_id not in self._lrus:
                    self._lrus[lru_id] = LRU(
                        lru_id=lru_id,
                        name=f"{key} (scenario-declared)",
                        system_key=str(key),
                        accessor=None,
                    )
            lru = self._lrus[lru_id]
            detail_txt = detail or f"forced by {source}"
            self._forced_faults[lru_id] = (state, detail_txt)
            if lru.health != state:
                logger.warning(
                    f"[LRU] {lru_id} ({lru.name}): {lru.health.value} → "
                    f"{state.value} [FORCED: {detail_txt}]"
                )
            # Apply immediately as well, so the state is visible even when
            # the poll thread isn't running (monitor not started yet).
            lru.health       = state
            lru.fault_detail = f"FORCED: {detail_txt}"
            lru.last_checked = time.time()
        return lru_id

    def clear_forced_fault(self, key: Optional[str] = None) -> int:
        """Clear one forced fault (by the same identifiers force_fault
        accepts) or all of them (key=None). The next poll cycle rederives
        live health; cleared LRUs are reset to UNKNOWN immediately so stale
        FAULT states never linger when the monitor isn't polling. Returns the
        number of overrides cleared."""
        with self._lock:
            if key is None:
                targets = list(self._forced_faults)
            else:
                lru_id = None
                needle = key.strip().lower()
                for candidate in self._forced_faults:
                    lru = self._lrus.get(candidate)
                    if candidate.lower() == needle or (
                        lru and (needle == lru.system_key.lower()
                                 or needle in lru.name.lower())
                    ):
                        lru_id = candidate
                        break
                targets = [lru_id] if lru_id else []
            for lru_id in targets:
                self._forced_faults.pop(lru_id, None)
                lru = self._lrus.get(lru_id)
                if lru is not None:
                    if lru.accessor is None and lru.name.endswith("(scenario-declared)"):
                        # Synthetic entry created by force_fault for a
                        # non-catalogued system — remove it entirely so it
                        # doesn't linger as a permanent UNKNOWN and skew
                        # overall_health().
                        del self._lrus[lru_id]
                    else:
                        lru.health       = HealthState.UNKNOWN
                        lru.fault_detail = ""
                    logger.info(f"[LRU] {lru_id}: forced fault cleared")
            return len(targets)

    def get_forced_faults(self) -> Dict[str, Dict[str, str]]:
        """Snapshot of active forced faults: {lru_id: {state, detail}}."""
        with self._lock:
            return {
                lru_id: {"state": state.value, "detail": detail}
                for lru_id, (state, detail) in self._forced_faults.items()
            }

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
            # Forced-fault override (scenario engine / instructor station):
            # while active it wins over the live-derived state — this is the
            # hook whose absence previously made scenario "system_failure"
            # events log-only (any directly-set .health was overwritten on
            # the next poll tick).
            forced = self._forced_faults.get(lru.lru_id)
            if forced is not None:
                new_health = forced[0]
                fault      = f"FORCED: {forced[1]}"
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
