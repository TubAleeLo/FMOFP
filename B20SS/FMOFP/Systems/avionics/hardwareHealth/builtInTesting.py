"""
Built-In Testing (BIT) — avionics hardware health layer

Implements the actual test execution logic for the B20SS avionics suite.
Works alongside bitControl.BuiltInTestController, which owns the XML-driven
test catalogue; this module provides the per-component probes that replace
the hardcoded "OK" stubs in bitControl.

Three test families:
  PowerOnSelfTest  — run once at startup; probes each LRU
  PeriodicBIT      — runs on a schedule (driven by bitControl interval config)
  InitiatedBIT     — on-demand crew-initiated test

Each test returns a BITResult so callers get a structured pass/fail record
rather than a plain string.

Consumed by:
  - bitControl.BuiltInTestController  (replaces its hardcoded "OK")
  - LRUstatus.LRUStatusMonitor        (feeds LRU health state)
  - EICAS display                     (via bitControl)
"""

import time
import threading
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ── Result types ─────────────────────────────────────────────────────────────

class BITStatus(str, Enum):
    PASS    = "PASS"
    FAIL    = "FAIL"
    ABORT   = "ABORT"     # test could not run (e.g. system offline)
    PENDING = "PENDING"


@dataclass
class BITResult:
    test_id:    str
    component:  str
    status:     BITStatus
    detail:     str        = ""
    duration_ms: float     = 0.0
    timestamp:  float      = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "test_id":     self.test_id,
            "component":   self.component,
            "status":      self.status.value,
            "detail":      self.detail,
            "duration_ms": round(self.duration_ms, 1),
            "timestamp":   self.timestamp,
        }

    def __str__(self) -> str:
        return f"{self.test_id}/{self.component}: {self.status.value}"


# ── Component probe helpers ───────────────────────────────────────────────────

def _probe_system(system_name: str, component: str) -> BITResult:
    """
    Probe a single component of a named system.

    For components that map to a live singleton (FCC, FMS, NavService, etc.)
    we call get_status() and inspect the result.  For anything without a
    live accessor we fall back to a simulated probe that always passes unless
    the random fault injection threshold is exceeded (1 % fault rate in sim).
    """
    t0 = time.perf_counter()
    status  = BITStatus.PASS
    detail  = "nominal"

    try:
        if system_name in ("flightControlComputer", "flightControlSys"):
            from FMOFP.Systems.flightControlSys.flightControlComputer.flightControlComputer import get_flight_control_computer
            st = get_flight_control_computer().get_status()
            if not st.get("running", True):
                status, detail = BITStatus.FAIL, "FCC not running"

        elif system_name in ("navigationSystem", "navService"):
            from FMOFP.Systems.nav.navService import get_nav_service
            st = get_nav_service().get_status()
            if not st.get("running", True):
                status, detail = BITStatus.FAIL, "NavService not running"

        elif system_name == "missionComputer":
            from FMOFP.Systems.missionPlanning.missionService import get_mission_service
            st = get_mission_service().get_status()
            if not st.get("running", True):
                status, detail = BITStatus.FAIL, "MissionService not running"

        elif system_name in ("datalink", "satcom", "radios"):
            from FMOFP.Systems.comms.messaging_service import get_comms_service
            st = get_comms_service().get_status()
            if not st.get("running", True):
                status, detail = BITStatus.FAIL, f"Comms ({system_name}) not running"

        elif system_name == "radarSystem":
            from FMOFP.Systems.radarManagement.radarControl import get_radar_management_system
            rms = get_radar_management_system()
            if not rms.running:
                status, detail = BITStatus.FAIL, "RadarManagement not running"

        else:
            # Simulated probe — 1 % fault injection rate for realism
            if random.random() < 0.01:
                status = BITStatus.FAIL
                detail = f"simulated fault in {component}"

    except Exception as exc:
        # System not yet started or import error — treat as ABORT not FAIL
        status = BITStatus.ABORT
        detail = str(exc)[:80]

    duration_ms = (time.perf_counter() - t0) * 1000
    return BITResult(
        test_id=f"BIT-{system_name.upper()[:8]}",
        component=component,
        status=status,
        detail=detail,
        duration_ms=duration_ms,
    )


# ── PowerOnSelfTest ───────────────────────────────────────────────────────────

class PowerOnSelfTest:
    """
    Runs the POST suite defined in bitsConfig.xml selfTests once at startup.
    Results are stored and available for EICAS display.
    """

    def __init__(self):
        self._results:  List[BITResult] = []
        self._complete: bool            = False
        self._lock = threading.Lock()

    def run(self, self_tests: List[Dict]) -> List[BITResult]:
        """
        Execute all self-tests from bitControl's parsed catalogue.

        Args:
            self_tests: list of dicts with keys id, description, system, components
        Returns:
            list of BITResult objects (one per component)
        """
        results: List[BITResult] = []
        logger.info(f"[BIT] POST starting — {len(self_tests)} test(s)")

        for test in self_tests:
            test_id    = test.get("id", "UNKNOWN")
            system     = test.get("system", "unknown")
            components = test.get("components", [])

            for comp in components:
                result = _probe_system(system, comp)
                result.test_id = test_id
                results.append(result)
                level = logger.debug if result.status == BITStatus.PASS else logger.warning
                level(f"[BIT] POST {test_id}/{comp}: {result.status.value} ({result.detail})")

        with self._lock:
            self._results  = results
            self._complete = True

        passed = sum(1 for r in results if r.status == BITStatus.PASS)
        failed = len(results) - passed
        logger.info(f"[BIT] POST complete — {passed} PASS, {failed} FAIL/ABORT")
        return results

    def get_results(self) -> List[BITResult]:
        with self._lock:
            return list(self._results)

    def is_complete(self) -> bool:
        with self._lock:
            return self._complete

    def summary_strings(self) -> List[str]:
        """Return EICAS-style strings matching the format EICAS already expects."""
        with self._lock:
            return [f"{r.test_id}: {r.status.value}" for r in self._results]


# ── PeriodicBIT ───────────────────────────────────────────────────────────────

class PeriodicBIT:
    """
    Runs BIT tests on the schedule defined in bitsConfig.xml periodicTests.
    Called by BuiltInTestController; results accumulated per test_id.
    """

    def __init__(self):
        self._results: Dict[str, List[BITResult]] = {}
        self._last_run: Dict[str, float]          = {}
        self._lock = threading.Lock()

    def run_due(self, periodic_tests: List[Dict]) -> List[BITResult]:
        """
        Run any periodic tests whose interval (minutes) has elapsed.

        Args:
            periodic_tests: list of dicts with id, systems, interval
        Returns:
            list of BITResult objects for tests that ran this cycle
        """
        now     = time.time()
        new_results: List[BITResult] = []

        for test in periodic_tests:
            test_id  = test.get("id", "UNKNOWN")
            systems  = test.get("systems", [])
            interval_s = test.get("interval", 90) * 60

            last = self._last_run.get(test_id, 0)
            if now - last < interval_s:
                continue

            logger.info(f"[BIT] Periodic {test_id} running")
            for system in systems:
                result = _probe_system(system, system)
                result.test_id = test_id
                new_results.append(result)

            with self._lock:
                self._results.setdefault(test_id, []).extend(new_results)
                self._last_run[test_id] = now

        return new_results

    def get_results(self, test_id: Optional[str] = None) -> List[BITResult]:
        with self._lock:
            if test_id:
                return list(self._results.get(test_id, []))
            all_results = []
            for v in self._results.values():
                all_results.extend(v)
            return all_results


# ── InitiatedBIT ──────────────────────────────────────────────────────────────

class InitiatedBIT:
    """
    On-demand crew-initiated BIT.  Runs all tests synchronously and returns
    a full result set.  Called from userCLI or MFD maintenance page.
    """

    def run_all(self, self_tests: List[Dict],
                periodic_tests: List[Dict],
                interface_tests: List[Dict]) -> List[BITResult]:
        """Run the complete BIT suite on demand."""
        results: List[BITResult] = []
        logger.info("[BIT] Initiated BIT — running full suite")

        # Self-tests
        post = PowerOnSelfTest()
        results.extend(post.run(self_tests))

        # Periodic tests (force-run regardless of interval)
        for test in periodic_tests:
            test_id = test.get("id", "UNKNOWN")
            for system in test.get("systems", []):
                result = _probe_system(system, system)
                result.test_id = test_id
                results.append(result)

        # Interface tests — probe both sides; pass only if both pass
        for test in interface_tests:
            test_id = test.get("id", "UNKNOWN")
            sys1    = test.get("system1", "unknown")
            sys2    = test.get("system2", "unknown")
            for sys_name in (sys1, sys2):
                result = _probe_system(sys_name, sys_name)
                result.test_id = test_id
                results.append(result)

        passed = sum(1 for r in results if r.status == BITStatus.PASS)
        logger.info(f"[BIT] Initiated BIT complete — {passed}/{len(results)} PASS")
        return results

    def run_single(self, system: str, component: str,
                   test_id: str = "IBT") -> BITResult:
        """Run a single component probe (useful for targeted maintenance checks)."""
        logger.info(f"[BIT] Single probe: {system}/{component}")
        result = _probe_system(system, component)
        result.test_id = test_id
        return result
