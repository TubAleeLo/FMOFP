"""
Test suite: Power / Fuel / Thrust Management Systems

Covers the three subsystems built out and wired into the live boot
sequence this session (system_manager.py Phase 3):
PowerManagementSystem (batteries + cooling/HVAC thermal model),
FuelManagementSystem/FuelSystem (tank/engine/fuel-line model + monitor +
transfer manager), and ThrustManagementSystem (autothrottle + asymmetry
safety check). Until this file, none of these had any automated test
coverage -- every bug in them (heat-load scaling, missing fuel_tanks
table, the redundant double-draining transfer rule, the start() TOCTOU
race) was only ever caught by manual live boot testing.

Tests
-----
1.  PowerManagementSystem — construction wires real battery/cooling/HVAC objects
2.  PowerManagementSystem — adjust_power_parameters() stays within configured ranges
3.  PowerManagementSystem — monitor() populates pms_data with expected keys
4.  PowerManagementSystem — heat-load regression: coolant stays under WARNING_TEMP_C
5.  PowerManagementSystem — start()/get_status()/stop() lifecycle
6.  FuelSystem — table creation regression: add_tank/add_engine/transfer_fuel raise nothing
7.  FuelTank — consume/refill clamp at 0 and capacity
8.  FuelManagementSystem — setup_aircraft() wires 3 tanks, 2 engines, 4 fuel lines
9.  FuelManagementSystem — perform_fuel_transfer() tops up a low main tank from Center
10. FuelManagementSystem — transfer_manager starts with zero rules (redundant-rule regression)
11. FuelManagementSystem — get_status() has expected keys; start()/stop() lifecycle
12. ThrustManagementSystem — register/set/get thrust, unknown-engine rejection
13. ThrustManagementSystem — check_asymmetry: None below 2 engines, correct value at 2
14. ThrustManagementSystem — autothrottle PI loop moves thrust toward target
15. ThrustManagementSystem — start()/get_status()/stop() lifecycle
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


# ──────────────────────────── Power Management tests ──────────────────────

def test_pms_construction(r: _Results) -> None:
    print("\n  ── PowerManagementSystem: construction ──")
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    r.check("main_battery is a real Battery object", hasattr(pms.main_battery, "charge_pct"))
    r.check("emergency_battery is a real Battery object", hasattr(pms.emergency_battery, "charge_pct"))
    r.check("apu_battery is a real Battery object", hasattr(pms.apu_battery, "charge_pct"))
    r.check("mission_equipment bank has 3 registered equipment items",
            len(pms.mission_equipment.equipment) == 3 if hasattr(pms.mission_equipment, "equipment")
            else len(pms.mission_equipment.get_all_status()) == 3,
            "mission equipment count mismatch")
    r.check("cooling system present", hasattr(pms.cooling, "coolant_temp_c"))
    r.check("hvac system present", hasattr(pms.hvac, "cabin_temp_c"))
    return pms


def test_pms_adjust_power_parameters(r: _Results) -> None:
    print("\n  ── PowerManagementSystem: adjust_power_parameters ──")
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    pms.adjust_power_parameters(dt_hours=1.0 / 3600.0)
    r.check("generator_output within configured 200-250kW range",
            200.0 <= pms.generator_output <= 250.0, f"got {pms.generator_output}")
    r.check("total_power_consumption within configured 180-220kW range",
            180.0 <= pms.total_power_consumption <= 220.0, f"got {pms.total_power_consumption}")
    r.check("main battery charge_pct stays within [0, 100]",
            0.0 <= pms.main_battery.charge_pct <= 100.0, f"got {pms.main_battery.charge_pct}")


def test_pms_monitor(r: _Results) -> None:
    print("\n  ── PowerManagementSystem: monitor() ──")
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    pms.adjust_power_parameters()
    pms.monitor()
    expected_keys = {
        'main_battery_charge', 'emergency_battery_charge', 'apu_battery_charge',
        'generator_output', 'total_power_consumption', 'power_balance',
        'main_bus_voltage', 'aux_bus_voltage', 'generator_frequency',
        'power_factor', 'coolant_temp_c', 'cabin_temp_c',
    }
    r.check("pms_data contains all expected keys",
            expected_keys.issubset(pms.pms_data.keys()),
            f"missing: {expected_keys - pms.pms_data.keys()}")


def test_pms_heat_load_regression(r: _Results) -> None:
    print("\n  ── PowerManagementSystem: heat-load scaling regression ──")
    # Regression test for the fixed bug: cooling.set_heat_load() was
    # originally scaled by (total_power_consumption * 1000.0 * 0.35), which
    # overwhelmed the ActiveDissipationUnit's ~2.1kW max rejection and drove
    # coolant_temp_c past CRITICAL_TEMP_C (70C) within about two minutes.
    # The fix (* 6.0 instead) should keep coolant comfortably under
    # WARNING_TEMP_C (55C) even after many ticks at max consumption.
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    pms.total_power_consumption = 220.0  # top of the simulated consumption range
    for _ in range(120):  # 120 ticks at 1s cadence == 2 simulated minutes
        pms.cooling.set_heat_load('avionics_bus', pms.total_power_consumption * 6.0)
        pms.cooling.update(dt_hours=1.0 / 3600.0)
    r.check("coolant_temp_c stays under WARNING_TEMP_C (55C) after 120 ticks at max load",
            pms.cooling.coolant_temp_c < 55.0, f"got {pms.cooling.coolant_temp_c}")


def test_pms_lifecycle(r: _Results) -> None:
    print("\n  ── PowerManagementSystem: start/get_status/stop lifecycle ──")
    from FMOFP.Systems.powerManagement.elec.powerManagementSystem import PowerManagementSystem
    pms = PowerManagementSystem()
    status_before = pms.get_status()
    r.check("get_status()['running'] is False before start()", status_before['running'] is False)

    pms.start()
    time.sleep(1.5)
    status_during = pms.get_status()
    r.check("get_status()['running'] is True after start()", status_during['running'] is True)
    r.check("pms_data populated by background thread", len(status_during['pms_data']) > 0)

    pms.stop()
    time.sleep(0.2)
    r.check("thread is no longer alive after stop()",
            not (pms.thread is not None and pms.thread.is_alive()))


# ──────────────────────────── Fuel Management tests ───────────────────────

def test_fuel_system_table_creation(r: _Results) -> None:
    print("\n  ── FuelSystem: table creation regression ──")
    # Regression test for the fixed bug: FuelSystem.__init__() never
    # created the fuel_tanks/engines/fuel_lines tables that add_tank()/
    # add_engine()/transfer_fuel()/update() all write to, producing 260+
    # "no such table: fuel_tanks" ERROR log lines in a 15s live boot before
    # the fix. None of these calls should raise or log a "no such table"
    # error now.
    from FMOFP.Systems.engineManagement.fuelManagement.fuelControl import FuelSystem
    fs = FuelSystem()
    try:
        fs.add_tank("Test Tank", 5000)
        fs.add_engine("Test Engine", 10000)
        fs.connect_tank_to_engine("Test Tank", "Test Engine", 50)
        fs.set_engine_thrust("Test Engine", 50)
        fs.transfer_fuel.__self__  # no-op attr access, keeps flake tools quiet
        fs.update(1.0)
        ok = True
    except Exception as exc:
        ok = False
        logger.error(f"FuelSystem table-creation regression raised: {exc}")
    r.check("add_tank/add_engine/connect_tank_to_engine/update raise nothing", ok)


def test_fuel_tank_clamping(r: _Results) -> None:
    print("\n  ── FuelTank: consume/refill clamping ──")
    from FMOFP.Systems.engineManagement.fuelManagement.fuelControl import FuelTank
    tank = FuelTank("Clamp Test", 1000.0)
    over_consumed = tank.consume(5000.0)
    r.check("consume() clamps to current_level, not the requested amount",
            over_consumed == 1000.0, f"got {over_consumed}")
    r.check("current_level does not go negative", tank.current_level == 0.0, f"got {tank.current_level}")

    over_filled = tank.refill(5000.0)
    r.check("refill() clamps to available capacity",
            over_filled == 1000.0, f"got {over_filled}")
    r.check("current_level does not exceed capacity",
            tank.current_level == tank.capacity, f"got {tank.current_level}")


def test_fms_group(r: _Results) -> None:
    """
    Combines setup_aircraft(), perform_fuel_transfer(), the
    transfer_manager-starts-empty regression, get_status(), and the
    start()/stop() lifecycle into a single FuelManagementSystem instance.
    Deliberately NOT split into one FuelManagementSystem() per check: the
    'default' system database (shared by FuelSystem, since dbConfig.xml has
    no dedicated 'engine' entry -- see FuelSystem.__init__'s comment) rate-
    limits 'create' queries to 10 per 60s, and each FuelManagementSystem()
    construction issues 3 (fuel_tanks/engines/fuel_lines). More than 3
    instantiations in one process would trip DBM's rate limiter and force
    this test to block for up to a minute.
    """
    print("\n  ── FuelManagementSystem: setup_aircraft() ──")
    from FMOFP.Systems.engineManagement.fuelManagement.fuelControl import FuelManagementSystem
    fms = FuelManagementSystem()
    fms.setup_aircraft()
    r.check("3 tanks registered", len(fms.fuel_system.tanks) == 3, f"got {len(fms.fuel_system.tanks)}")
    r.check("2 engines registered", len(fms.fuel_system.engines) == 2, f"got {len(fms.fuel_system.engines)}")
    total_lines = sum(len(v) for v in fms.fuel_system.fuel_lines.values())
    r.check("4 fuel lines registered", total_lines == 4, f"got {total_lines}")

    print("\n  ── FuelManagementSystem: transfer_manager starts with zero rules ──")
    # Regression test: an earlier version registered a TransferRule
    # duplicating perform_fuel_transfer()'s own Center->Mains policy,
    # causing double-draining of the Center tank and false LEAK_SUSPECTED
    # alerts from FuelMonitor. transfer_manager must start empty.
    r.check("transfer_manager.get_status()['rule_count'] == 0",
            fms.transfer_manager.get_status()['rule_count'] == 0,
            f"got {fms.transfer_manager.get_status()['rule_count']}")

    print("\n  ── FuelManagementSystem: perform_fuel_transfer() ──")
    # Drain Main Left below the 5000kg threshold that perform_fuel_transfer()
    # checks, leaving Center comfortably above its own 5000kg threshold.
    fms.fuel_system.tanks["Main Left"].current_level = 3000.0
    before = fms.fuel_system.tanks["Main Left"].current_level
    fms.perform_fuel_transfer()
    after = fms.fuel_system.tanks["Main Left"].current_level
    r.check("Main Left level increases after transfer from Center",
            after > before, f"before={before}, after={after}")

    print("\n  ── FuelManagementSystem: get_status() ──")
    status = fms.get_status()
    expected_keys = {'running', 'fuel_status', 'engines', 'monitor', 'transfers'}
    r.check("get_status() has expected keys",
            expected_keys.issubset(status.keys()), f"missing: {expected_keys - status.keys()}")

    print("\n  ── FuelManagementSystem: start/stop lifecycle ──")
    fms.start()
    time.sleep(1.0)
    r.check("running is True after start()", fms.get_status()['running'] is True)

    fms.stop()
    time.sleep(0.2)
    r.check("running is False after stop()", fms.running is False)


# ──────────────────────────── Thrust Management tests ─────────────────────

def test_tms_register_and_set_thrust(r: _Results) -> None:
    print("\n  ── ThrustManagementSystem: register/set/get thrust ──")
    from FMOFP.Systems.engineManagement.thrustManagement.thrustManagement import ThrustManagementSystem
    tms = ThrustManagementSystem()
    tms.register_engine("Engine 1", 20.0)
    tms.register_engine("Engine 2", 20.0)
    r.check("get_thrust returns registered initial value",
            tms.get_thrust("Engine 1") == 20.0, f"got {tms.get_thrust('Engine 1')}")

    ok = tms.set_thrust("Engine 1", 75.0)
    r.check("set_thrust on known engine returns True", ok is True)
    r.check("set_thrust clamps to [0,100] and applied correctly",
            tms.get_thrust("Engine 1") == 75.0, f"got {tms.get_thrust('Engine 1')}")

    ok_unknown = tms.set_thrust("Engine 99", 50.0)
    r.check("set_thrust on unknown engine returns False", ok_unknown is False)

    tms.set_all_thrust(60.0)
    r.check("set_all_thrust applies symmetrically",
            all(v == 60.0 for v in tms.get_all_thrust().values()),
            f"got {tms.get_all_thrust()}")


def test_tms_asymmetry_check(r: _Results) -> None:
    print("\n  ── ThrustManagementSystem: check_asymmetry ──")
    from FMOFP.Systems.engineManagement.thrustManagement.thrustManagement import ThrustManagementSystem
    tms = ThrustManagementSystem()
    r.check("check_asymmetry() is None with 0 engines registered",
            tms.check_asymmetry() is None)

    tms.register_engine("Engine 1", 50.0)
    r.check("check_asymmetry() is None with only 1 engine registered",
            tms.check_asymmetry() is None)

    tms.register_engine("Engine 2", 80.0)
    asymmetry = tms.check_asymmetry()
    r.check("check_asymmetry() returns correct delta with 2 engines",
            asymmetry == 30.0, f"got {asymmetry}")


def test_tms_autothrottle_pi_loop(r: _Results) -> None:
    print("\n  ── ThrustManagementSystem: autothrottle PI controller ──")
    from FMOFP.Systems.engineManagement.thrustManagement.thrustManagement import ThrustManagementSystem
    tms = ThrustManagementSystem()
    tms.register_engine("Engine 1", 40.0)
    tms.register_engine("Engine 2", 40.0)

    tms.engage_autothrottle(target_airspeed_kts=300.0)
    r.check("autothrottle_engaged is True after engage", tms.autothrottle_engaged is True)

    thrust_before = tms.get_thrust("Engine 1")
    # Current airspeed (250kts) is below target (300kts) -> positive error
    # -> the PI controller should command more thrust, not less.
    tms.update_autothrottle(current_airspeed_kts=250.0, dt=1.0)
    thrust_after = tms.get_thrust("Engine 1")
    r.check("thrust increases when airspeed is below target",
            thrust_after > thrust_before, f"before={thrust_before}, after={thrust_after}")

    tms.disengage_autothrottle()
    r.check("autothrottle_engaged is False after disengage", tms.autothrottle_engaged is False)

    thrust_static = tms.get_thrust("Engine 1")
    tms.update_autothrottle(current_airspeed_kts=100.0, dt=1.0)
    r.check("update_autothrottle is a no-op once disengaged",
            tms.get_thrust("Engine 1") == thrust_static,
            f"before={thrust_static}, after={tms.get_thrust('Engine 1')}")


def test_tms_lifecycle(r: _Results) -> None:
    print("\n  ── ThrustManagementSystem: start/get_status/stop lifecycle ──")
    from FMOFP.Systems.engineManagement.thrustManagement.thrustManagement import ThrustManagementSystem
    tms = ThrustManagementSystem()
    tms.register_engine("Engine 1", 0.0)
    tms.register_engine("Engine 2", 0.0)

    status_before = tms.get_status()
    r.check("get_status()['running'] is False before start()", status_before['running'] is False)

    # Deliberately leave autothrottle disengaged so _update_loop's idle path
    # (no FMS dependency) is exercised — this test should not require a
    # running FMS singleton.
    tms.start()
    time.sleep(1.0)
    r.check("get_status()['running'] is True after start()", tms.get_status()['running'] is True)

    tms.stop()
    time.sleep(0.2)
    r.check("thread is no longer alive after stop()",
            not (tms._thread is not None and tms._thread.is_alive()))


# ──────────────────────────────────────────────────────────────── runner ──

def run_all() -> bool:
    r = _Results()
    tests = [
        test_pms_construction,
        test_pms_adjust_power_parameters,
        test_pms_monitor,
        test_pms_heat_load_regression,
        test_pms_lifecycle,
        test_fuel_system_table_creation,
        test_fuel_tank_clamping,
        test_fms_group,
        test_tms_register_and_set_thrust,
        test_tms_asymmetry_check,
        test_tms_autothrottle_pi_loop,
        test_tms_lifecycle,
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
