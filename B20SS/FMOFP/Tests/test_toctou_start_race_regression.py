"""
Regression test: TOCTOU race in subsystem singleton start() methods

This session found a systemic, pre-existing race across every Phase 2/3
subsystem singleton's start() method: the original pattern was an
unguarded "if self._thread is None or not self._thread.is_alive():
create-and-start" check-then-create sequence. system_manager.py calls
x.start() directly during boot AND separately, its generic "start
remaining components" pass also calls component.start() on the same
instance -- both paths can call a given singleton's start() close enough
together to race the unguarded check, letting two independent background
threads for the same instance come up simultaneously. Proven live at the
time via FlightDataMonitoring's collect_data() log volume running at ~2x
the single-thread expectation.

Fixed in 19 files (commits 0ec68ba, b7d3779, 0c33928, b2a4761) by wrapping
each start()'s check-then-create sequence in a lock. This test guards
against that fix regressing: it hammers start() concurrently from many
threads on each of a representative sample of the fixed singletons (the 8
built out this session, plus NavService representing the 9 pre-existing
subsystems that got the identical fix) and asserts that, no matter how
many overlapping start() calls occur, only ONE background thread with the
singleton's expected thread name ever exists in the process.

This intentionally checks threading.enumerate() rather than just
get_status()['running'] -- get_status() only proves *a* thread is alive,
not that a second one wasn't also silently spun up and left running
unsupervised (which is exactly what the original bug did).
"""

import sys
import os
import time
import threading

# Path setup — mirrors setup_env.py
_B20SS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for _p in (_B20SS, os.path.join(_B20SS, 'FMOFP')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()


# ─────────────────────────────────────────────────────── test framework ──

class _Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self._failures = []

    def check(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            self.passed += 1
            print(f"  ✓  {name}")
        else:
            self.failed += 1
            msg = f"  ✗  {name}" + (f"  [{detail}]" if detail else "")
            print(msg)
            self._failures.append(msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n  {self.passed}/{total} passed")
        if self._failures:
            print("\n  Failures:")
            for f in self._failures:
                print(f"    {f}")
        return self.failed == 0


N_CONCURRENT_CALLERS = 12


def _hammer_start(instance, thread_name: str, r: _Results, label: str) -> None:
    """
    Calls instance.start() from N_CONCURRENT_CALLERS threads simultaneously
    (synchronized with a Barrier to maximize actual overlap -- the whole
    point of a TOCTOU race is that the calls have to genuinely interleave,
    not just happen one after another), then asserts exactly one live
    thread named `thread_name` exists anywhere in the process.
    """
    barrier = threading.Barrier(N_CONCURRENT_CALLERS)

    def _caller():
        barrier.wait()  # release all callers at (as close to) the same instant
        instance.start()

    callers = [threading.Thread(target=_caller) for _ in range(N_CONCURRENT_CALLERS)]
    for c in callers:
        c.start()
    for c in callers:
        c.join(timeout=5)

    time.sleep(0.3)  # let any (bugged) second thread's startup log line land

    matching = [t for t in threading.enumerate() if t.name == thread_name]
    r.check(f"{label}: exactly one live '{thread_name}' thread after "
            f"{N_CONCURRENT_CALLERS} concurrent start() calls",
            len(matching) == 1, f"found {len(matching)}: {matching}")
    r.check(f"{label}: get_status()['running'] is True after the concurrent start() storm",
            instance.get_status().get('running') is True)

    instance.stop()
    time.sleep(0.3)


# ──────────────────────────── individual regression tests ─────────────────

def test_race_thrust_management(r: _Results) -> None:
    print("\n  ── Race regression: ThrustManagementSystem ──")
    from FMOFP.Systems.engineManagement.thrustManagement.thrustManagement import ThrustManagementSystem
    tms = ThrustManagementSystem()
    tms.register_engine("Engine 1", 0.0)
    tms.register_engine("Engine 2", 0.0)
    _hammer_start(tms, "TMS_Update", r, "ThrustManagementSystem")


def test_race_hydraulics(r: _Results) -> None:
    print("\n  ── Race regression: HydraulicSystemController ──")
    from FMOFP.Systems.hydraulics.hydrControl import HydraulicSystemController
    hydr = HydraulicSystemController()
    _hammer_start(hydr, "Hydraulics_Update", r, "HydraulicSystemController")


def test_race_airframe(r: _Results) -> None:
    print("\n  ── Race regression: AirframeSystemManager ──")
    from FMOFP.Systems.airframeSystemManagement.airframeControl import AirframeSystemManager
    airframe = AirframeSystemManager()
    _hammer_start(airframe, "Airframe_Update", r, "AirframeSystemManager")


def test_race_ecs(r: _Results) -> None:
    print("\n  ── Race regression: ECSControl ──")
    from FMOFP.Systems.enviornmentalControlSystem.ecsControl import ECSControl
    ecs = ECSControl()
    _hammer_start(ecs, "ECS_Update", r, "ECSControl")


def test_race_fm_fitness(r: _Results) -> None:
    print("\n  ── Race regression: FlightManagementFitness ──")
    from FMOFP.Systems.fmFitness.fmStatus import FlightManagementFitness
    fitness = FlightManagementFitness()
    _hammer_start(fitness, "FMFitness_Update", r, "FlightManagementFitness")


def test_race_fdm(r: _Results) -> None:
    print("\n  ── Race regression: FlightDataMonitoring ──")
    # This is the exact class the original bug was proven concretely on
    # (collect_data() log volume running at ~2x the single-thread rate).
    from FMOFP.Systems.flightDataMonitoring.fdmControl import FlightDataMonitoring
    fdm = FlightDataMonitoring()
    _hammer_start(fdm, "FDM_Record", r, "FlightDataMonitoring")


def test_race_power_management(r: _Results) -> None:
    print("\n  ── Race regression: PowerManagementSystem ──")
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    _hammer_start(pms, "PMS_Update", r, "PowerManagementSystem")


def test_race_fuel_management(r: _Results) -> None:
    print("\n  ── Race regression: FuelManagementSystem ──")
    # Only one FuelManagementSystem() construction in this whole file (a
    # single instance, start() hammered concurrently afterward) -- keeps
    # this well under the 'default' system database's 10-per-60s 'create'
    # query rate limit that FuelSystem.__init__() consumes 3 of per
    # instantiation (see test_power_fuel_thrust.py's test_fms_group for
    # the full explanation of that constraint).
    from FMOFP.Systems.engineManagement.fuelManagement.fuelControl import FuelManagementSystem
    fms = FuelManagementSystem()
    fms.setup_aircraft()
    _hammer_start(fms, "FMS_Update", r, "FuelManagementSystem")


def test_race_nav_service(r: _Results) -> None:
    print("\n  ── Race regression: NavService (representative of the 9 pre-existing subsystems) ──")
    # NavService is the one class in the "9 pre-existing subsystems" group
    # (commit 0c33928) that had no existing data lock to reuse and was
    # given a brand-new dedicated self._start_lock -- a slightly different
    # code path from the other 8 in this file (which reused an existing
    # lock), worth covering directly rather than assuming it behaves
    # identically.
    from FMOFP.Systems.nav.navService import get_nav_service
    nav = get_nav_service()
    _hammer_start(nav, "NAV_Service", r, "NavService")


# ──────────────────────────────────────────────────────────────── runner ──

def run_all() -> bool:
    r = _Results()
    tests = [
        test_race_thrust_management,
        test_race_hydraulics,
        test_race_airframe,
        test_race_ecs,
        test_race_fm_fitness,
        test_race_fdm,
        test_race_power_management,
        test_race_fuel_management,
        test_race_nav_service,
    ]

    for test_fn in tests:
        try:
            test_fn(r)
        except Exception as exc:
            import traceback as _tb
            r.failed += 1
            print(f"  ✗  {test_fn.__name__} raised: {exc}")
            _tb.print_exc()

    print("\n" + "=" * 60)
    passed = r.summary()
    print("=" * 60)
    return passed


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
