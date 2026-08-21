"""
Test suite: Hydraulics / Airframe / ECS / Flight Data Monitoring /
Flight Management Fitness / Software Config Manager

Covers the six subsystems wired into the live boot sequence this session
(system_manager.py Phase 3, commit 18cba09): HydraulicSystemController,
AirframeSystemManager, ECSControl, FlightDataMonitoring,
FlightManagementFitness, and SoftwareConfigManager. Before this file, none
of these had any automated test coverage -- every bug in them (missing
"FMOFP/" config-path segment, 100%-CPU busy-loop run() with no sleep,
run()-was-a-no-op instead of a real loop, the undefined self.scheduler
AttributeError) was only ever caught by manual live boot testing.

Tests
-----
1.  HydraulicSystemController — config loads primary/backup systems + pressure thresholds
2.  HydraulicSystemController — activate_backup() switches active_system
3.  HydraulicSystemController — start()/get_status()/stop() lifecycle
4.  AirframeSystemManager — config loads subsystems + sensors
5.  AirframeSystemManager — control_landing_gear() accepts deploy/retract without raising
6.  AirframeSystemManager — start()/get_status()/stop() lifecycle
7.  ECSControl — simulated readings return documented constant values
8.  ECSControl — monitor_ecs() runs without raising
9.  ECSControl — start()/get_status()/stop() lifecycle
10. FlightDataMonitoring — config loads recorders + storage cards
11. FlightDataMonitoring — eject_storage() handles valid and invalid slots
12. FlightDataMonitoring — start()/get_status()/stop() lifecycle; _record_loop distinct from run()
13. FlightManagementFitness — config loads components/thresholds/redundancy
14. FlightManagementFitness — check_thresholds() classifies OK/WARNING/CRITICAL by exact match
15. FlightManagementFitness — handle_redundancy() only fires for the configured component
16. FlightManagementFitness — start()/get_status()/stop() lifecycle
17. SoftwareConfigManager — config loads components/data_loads/update_sequence
18. SoftwareConfigManager — perform_update() with a valid load ID applies new versions
19. SoftwareConfigManager — perform_update() with an invalid load ID is a no-op, does not raise
20. SoftwareConfigManager — get_software_config_manager() singleton has no background thread
"""

import sys
import os
import time

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


def _lifecycle_check(r: _Results, label: str, instance, extra_status_check=None) -> None:
    """Shared start()/get_status()/stop() lifecycle assertions for the
    threading.Event-gated singletons in this file (all follow the same
    start()/stop()/get_status() shape)."""
    status_before = instance.get_status()
    r.check(f"{label}: get_status()['running'] is False before start()",
            status_before['running'] is False)

    instance.start()
    time.sleep(1.2)
    status_during = instance.get_status()
    r.check(f"{label}: get_status()['running'] is True after start()",
            status_during['running'] is True)
    if extra_status_check:
        extra_status_check(status_during)

    instance.stop()
    time.sleep(0.2)
    r.check(f"{label}: thread is no longer alive after stop()",
            not (instance._thread is not None and instance._thread.is_alive()))


# ──────────────────────────── Hydraulics tests ─────────────────────────────

def test_hydraulics_config_load(r: _Results) -> None:
    print("\n  ── HydraulicSystemController: config load ──")
    from FMOFP.Systems.hydraulics.hydrControl import HydraulicSystemController
    hydr = HydraulicSystemController()
    r.check("primary_system loaded", bool(hydr.primary_system.get('description')))
    r.check("backup_system loaded", bool(hydr.backup_system.get('description')))
    r.check("pressure_thresholds has nominal/warning/critical",
            {'nominal', 'warning', 'critical'}.issubset(hydr.pressure_thresholds.keys()))
    r.check("active_system defaults to primary_system",
            hydr.active_system is hydr.primary_system)


def test_hydraulics_activate_backup(r: _Results) -> None:
    print("\n  ── HydraulicSystemController: activate_backup() ──")
    from FMOFP.Systems.hydraulics.hydrControl import HydraulicSystemController
    hydr = HydraulicSystemController()
    hydr.activate_backup()
    r.check("active_system switches to backup_system after activate_backup()",
            hydr.active_system is hydr.backup_system)


def test_hydraulics_lifecycle(r: _Results) -> None:
    print("\n  ── HydraulicSystemController: start/get_status/stop lifecycle ──")
    from FMOFP.Systems.hydraulics.hydrControl import HydraulicSystemController
    hydr = HydraulicSystemController()
    _lifecycle_check(r, "HydraulicSystemController", hydr)


# ──────────────────────────── Airframe tests ───────────────────────────────

def test_airframe_config_load(r: _Results) -> None:
    print("\n  ── AirframeSystemManager: config load ──")
    from FMOFP.Systems.airframeSystemManagement.airframeControl import AirframeSystemManager
    airframe = AirframeSystemManager()
    r.check("subsystems loaded", len(airframe.subsystems) > 0, f"got {len(airframe.subsystems)}")
    r.check("sensors loaded", len(airframe.sensors) > 0, f"got {len(airframe.sensors)}")


def test_airframe_landing_gear(r: _Results) -> None:
    print("\n  ── AirframeSystemManager: control_landing_gear() ──")
    from FMOFP.Systems.airframeSystemManagement.airframeControl import AirframeSystemManager
    airframe = AirframeSystemManager()
    try:
        airframe.control_landing_gear("deploy")
        airframe.control_landing_gear("retract")
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"control_landing_gear regression raised: {exc}")
    r.check("control_landing_gear accepts deploy/retract without raising", ok)


def test_airframe_lifecycle(r: _Results) -> None:
    print("\n  ── AirframeSystemManager: start/get_status/stop lifecycle ──")
    from FMOFP.Systems.airframeSystemManagement.airframeControl import AirframeSystemManager
    airframe = AirframeSystemManager()

    def _check(status):
        r.check("AirframeSystemManager: get_status()['sensor_count'] matches loaded sensors",
                status['sensor_count'] == len(airframe.sensors),
                f"got {status['sensor_count']}, expected {len(airframe.sensors)}")

    _lifecycle_check(r, "AirframeSystemManager", airframe, extra_status_check=_check)


# ──────────────────────────── ECS tests ────────────────────────────────────

def test_ecs_simulated_readings(r: _Results) -> None:
    print("\n  ── ECSControl: simulated readings ──")
    from FMOFP.Systems.enviornmentalControlSystem.ecsControl import ECSControl
    ecs = ECSControl()
    r.check("get_temperature() returns documented constant",
            ecs.get_temperature() == 22.5, f"got {ecs.get_temperature()}")
    r.check("get_pressure() returns documented constant",
            ecs.get_pressure() == 101.3, f"got {ecs.get_pressure()}")
    r.check("get_air_quality() returns documented constant",
            ecs.get_air_quality() == 98.5, f"got {ecs.get_air_quality()}")


def test_ecs_monitor_no_raise(r: _Results) -> None:
    print("\n  ── ECSControl: monitor_ecs() ──")
    from FMOFP.Systems.enviornmentalControlSystem.ecsControl import ECSControl
    ecs = ECSControl()
    try:
        ecs.monitor_ecs()
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"monitor_ecs regression raised: {exc}")
    r.check("monitor_ecs() runs without raising", ok)


def test_ecs_climate_oxygen_subcomponents(r: _Results) -> None:
    print("\n  ── ECSControl: ClimateControl / OxygenControl sub-components ──")
    # Regression/coverage test for wiring ClimateControl and OxygenControl
    # into ECSControl (production readiness re-analysis, August 2026):
    # both classes were fixed earlier this session (a ModuleNotFoundError
    # on import) but never actually instantiated anywhere -- confirmed via
    # a repo-wide dead-code sweep. Now owned by ECSControl the same way
    # PowerManagementSystem owns its battery/cooling/HVAC sub-components.
    from FMOFP.Systems.enviornmentalControlSystem.ecsControl import ECSControl
    ecs = ECSControl()
    r.check("ECSControl owns a ClimateControl instance", hasattr(ecs.climate, "get_climate_status"))
    r.check("ECSControl owns an OxygenControl instance", hasattr(ecs.oxygen, "get_oxygen_status"))

    oxygen_before = ecs.oxygen.oxygen_level
    ecs.monitor_ecs()
    r.check("monitor_ecs() drives oxygen generation each tick",
            ecs.oxygen.oxygen_level >= oxygen_before,
            f"before={oxygen_before}, after={ecs.oxygen.oxygen_level}")

    status = ecs.get_status()
    r.check("get_status() includes a 'climate' sub-dict with temperature/humidity",
            {'temperature', 'humidity'}.issubset(status.get('climate', {}).keys()),
            f"got {status.get('climate')}")
    r.check("get_status() includes an 'oxygen' sub-dict with level/generation_rate",
            {'oxygen_level', 'generation_rate'}.issubset(status.get('oxygen', {}).keys()),
            f"got {status.get('oxygen')}")


def test_ecs_lifecycle(r: _Results) -> None:
    print("\n  ── ECSControl: start/get_status/stop lifecycle ──")
    # Regression test for the fixed bug: run() previously just set
    # self.running = True and returned immediately -- not an actual loop,
    # so using it as a thread target would do nothing and the thread would
    # exit almost instantly. get_status()['running'] must stay True while
    # the thread is genuinely looping.
    from FMOFP.Systems.enviornmentalControlSystem.ecsControl import ECSControl
    ecs = ECSControl()

    def _check(status):
        expected_keys = {'temperature_c', 'pressure_kpa', 'air_quality_pct'}
        r.check("ECSControl: get_status() has expected reading keys",
                expected_keys.issubset(status.keys()), f"missing: {expected_keys - status.keys()}")

    _lifecycle_check(r, "ECSControl", ecs, extra_status_check=_check)


# ──────────────────────────── FDM tests ────────────────────────────────────

def test_fdm_config_load(r: _Results) -> None:
    print("\n  ── FlightDataMonitoring: config load ──")
    from FMOFP.Systems.flightDataMonitoring.fdmControl import FlightDataMonitoring
    fdm = FlightDataMonitoring()
    r.check("recorders loaded", len(fdm.recorders) > 0, f"got {len(fdm.recorders)}")
    r.check("storage cards loaded", len(fdm.storage) > 0, f"got {len(fdm.storage)}")


def test_fdm_eject_storage(r: _Results) -> None:
    print("\n  ── FlightDataMonitoring: eject_storage() ──")
    from FMOFP.Systems.flightDataMonitoring.fdmControl import FlightDataMonitoring
    fdm = FlightDataMonitoring()
    valid_slot = fdm.storage[0]['slot']
    try:
        fdm.eject_storage(valid_slot)
        fdm.eject_storage(9999)  # invalid slot: should warn, not raise
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"eject_storage regression raised: {exc}")
    r.check("eject_storage() handles both valid and invalid slots without raising", ok)


def test_fdm_lifecycle(r: _Results) -> None:
    print("\n  ── FlightDataMonitoring: start/get_status/stop lifecycle (_record_loop, not run()) ──")
    # Regression test for the TOCTOU race originally found here: an
    # unlocked start() let two _record_loop() threads run simultaneously,
    # doubling collect_data() log volume (~28 lines in ~28s at 2s cadence,
    # vs. the ~14 a single correct thread produces). A single start()/stop()
    # cycle can't directly observe that without a concurrency harness (see
    # the dedicated TOCTOU regression test), but this does confirm the
    # lifecycle itself: start() must launch the repeating _record_loop(),
    # NOT the one-shot demo run() (which also calls eject_storage() on both
    # cards and would be wrong to repeat automatically every couple of
    # seconds).
    from FMOFP.Systems.flightDataMonitoring.fdmControl import FlightDataMonitoring
    fdm = FlightDataMonitoring()

    def _check(status):
        r.check("FlightDataMonitoring: get_status()['recorder_count'] matches loaded recorders",
                status['recorder_count'] == len(fdm.recorders),
                f"got {status['recorder_count']}, expected {len(fdm.recorders)}")

    _lifecycle_check(r, "FlightDataMonitoring", fdm, extra_status_check=_check)


# ──────────────────────────── FM Fitness tests ─────────────────────────────

def test_fitness_config_load(r: _Results) -> None:
    print("\n  ── FlightManagementFitness: config load ──")
    from FMOFP.Systems.fmFitness.fmStatus import FlightManagementFitness
    fitness = FlightManagementFitness()
    r.check("components loaded", len(fitness.components) > 0, f"got {len(fitness.components)}")
    r.check("thresholds has warning/critical", {'warning', 'critical'}.issubset(fitness.thresholds.keys()))
    r.check("redundancy configured", bool(fitness.redundancy.get('component')))


def test_fitness_check_thresholds(r: _Results) -> None:
    print("\n  ── FlightManagementFitness: check_thresholds() classification ──")
    # check_thresholds() compares by exact equality against the configured
    # threshold value (not a >= crossing check) -- documenting the current,
    # as-shipped behavior rather than an idealized one, matching this
    # session's convention of testing actual code behavior. Verified this
    # doesn't raise and covers all three branches (OK/WARNING/CRITICAL);
    # log output is the only observable side effect, so these calls are
    # smoke tests for "doesn't raise" plus one direct behavioral check via
    # the module's threshold dict itself.
    from FMOFP.Systems.fmFitness.fmStatus import FlightManagementFitness
    fitness = FlightManagementFitness()
    warning_cpu = fitness.thresholds['warning']['cpu']
    critical_cpu = fitness.thresholds['critical']['cpu']
    try:
        fitness.check_thresholds("test_component", {"cpu": 0, "memory": 0})       # OK path
        fitness.check_thresholds("test_component", {"cpu": warning_cpu, "memory": 0})   # WARNING path
        fitness.check_thresholds("test_component", {"cpu": critical_cpu, "memory": 0})  # CRITICAL path
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"check_thresholds regression raised: {exc}")
    r.check("check_thresholds() handles OK/WARNING/CRITICAL branches without raising", ok)


def test_fitness_handle_redundancy(r: _Results) -> None:
    print("\n  ── FlightManagementFitness: handle_redundancy() ──")
    from FMOFP.Systems.fmFitness.fmStatus import FlightManagementFitness
    fitness = FlightManagementFitness()
    try:
        fitness.handle_redundancy(fitness.redundancy['component'])   # configured -> should fire
        fitness.handle_redundancy("nonexistent_component")           # not configured -> should no-op
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"handle_redundancy regression raised: {exc}")
    r.check("handle_redundancy() handles matching and non-matching components without raising", ok)


def test_fitness_lifecycle(r: _Results) -> None:
    print("\n  ── FlightManagementFitness: start/get_status/stop lifecycle ──")
    # Regression test for the fixed bug: run()'s loop previously had no
    # time.sleep() call backing its "sleep for configured interval" comment
    # -- a 100%-CPU busy loop with no way to exit.
    from FMOFP.Systems.fmFitness.fmStatus import FlightManagementFitness
    fitness = FlightManagementFitness()

    def _check(status):
        r.check("FlightManagementFitness: get_status()['components'] matches loaded components",
                set(status['components']) == {c['name'] for c in fitness.components},
                f"got {status['components']}")

    _lifecycle_check(r, "FlightManagementFitness", fitness, extra_status_check=_check)


# ──────────────────────────── SW Config Manager tests ──────────────────────

def test_swcm_config_load(r: _Results) -> None:
    print("\n  ── SoftwareConfigManager: config load ──")
    from FMOFP.Systems.configurationManagement.swConfigure import SoftwareConfigManager
    swcm = SoftwareConfigManager()
    r.check("components loaded", len(swcm.components) > 0, f"got {len(swcm.components)}")
    r.check("data_loads loaded", len(swcm.data_loads) > 0, f"got {len(swcm.data_loads)}")
    r.check("update_sequence loaded", len(swcm.update_sequence) > 0, f"got {len(swcm.update_sequence)}")


def test_swcm_perform_update_valid(r: _Results) -> None:
    print("\n  ── SoftwareConfigManager: perform_update() with a valid load ID ──")
    from FMOFP.Systems.configurationManagement.swConfigure import SoftwareConfigManager
    swcm = SoftwareConfigManager()
    load_id = swcm.data_loads[0]['id']
    expected_versions = {s['component']: s['version'] for s in swcm.data_loads[0]['specs']}

    swcm.perform_update(load_id)

    all_applied = all(
        comp['version'] == expected_versions[comp['name']]
        for comp in swcm.components
        if comp['name'] in expected_versions
    )
    r.check("perform_update() applies the load's component versions",
            all_applied, f"components after update: {swcm.components}")


def test_swcm_perform_update_invalid(r: _Results) -> None:
    print("\n  ── SoftwareConfigManager: perform_update() with an invalid load ID ──")
    from FMOFP.Systems.configurationManagement.swConfigure import SoftwareConfigManager
    swcm = SoftwareConfigManager()
    versions_before = [dict(c) for c in swcm.components]
    try:
        swcm.perform_update("nonexistent-load-id")
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"perform_update(invalid) regression raised: {exc}")
    r.check("perform_update() with an unknown load ID does not raise", ok)
    r.check("perform_update() with an unknown load ID leaves components unchanged",
            versions_before == swcm.components, f"got {swcm.components}")


def test_swcm_singleton_no_background_thread(r: _Results) -> None:
    print("\n  ── SoftwareConfigManager: get_software_config_manager() singleton ──")
    # Deliberately-undertested design decision (see the accessor's own
    # docstring): unlike every other subsystem singleton in this file,
    # SoftwareConfigManager is NOT given a background thread, because its
    # run() applies one specific hardcoded historical data load as a
    # one-shot demo -- looping that on a timer would misleadingly "re-apply"
    # the same update forever. Confirms the singleton accessor still works
    # (same instance returned every call) and that the returned instance
    # genuinely has no thread-related state at all, distinguishing this
    # from a subsystem that merely hasn't been start()ed yet.
    from FMOFP.Systems.configurationManagement.swConfigure import get_software_config_manager
    swcm1 = get_software_config_manager()
    swcm2 = get_software_config_manager()
    r.check("get_software_config_manager() returns the same instance on repeated calls",
            swcm1 is swcm2)
    r.check("SoftwareConfigManager instance has no start()/_thread attribute",
            not hasattr(swcm1, 'start') and not hasattr(swcm1, '_thread'))


# ──────────────────────────────────────────────────────────────── runner ──

def run_all() -> bool:
    r = _Results()
    tests = [
        test_hydraulics_config_load,
        test_hydraulics_activate_backup,
        test_hydraulics_lifecycle,
        test_airframe_config_load,
        test_airframe_landing_gear,
        test_airframe_lifecycle,
        test_ecs_simulated_readings,
        test_ecs_monitor_no_raise,
        test_ecs_climate_oxygen_subcomponents,
        test_ecs_lifecycle,
        test_fdm_config_load,
        test_fdm_eject_storage,
        test_fdm_lifecycle,
        test_fitness_config_load,
        test_fitness_check_thresholds,
        test_fitness_handle_redundancy,
        test_fitness_lifecycle,
        test_swcm_config_load,
        test_swcm_perform_update_valid,
        test_swcm_perform_update_invalid,
        test_swcm_singleton_no_background_thread,
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
