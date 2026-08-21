"""Test suite — scenario system_failure events are functional (not log-only).

Covers the forced-fault override added in the August 2026 completion pass:
  1. LRUStatusMonitor.force_fault on a catalogued LRU is visible immediately
     in get_lru()/get_faults()/overall_health().
  2. The override survives a poll cycle (_poll_lru honors it) — the exact
     mechanism whose absence made scenario failures log-only.
  3. clear_forced_fault restores live-derived health on the next poll.
  4. Non-catalogued system names become scenario-declared entries and are
     fully removed again on clear.
  5. ScenarioEngine._inject_failure routes set/clear/clear_all actions and
     the state parameter into the monitor.
  6. failureScenario.xml's own system_failure events all inject successfully
     end-to-end through the real dispatch path.

Standalone-safe: run from B20SS/ as
`python -m FMOFP.Tests.test_scenario_failure_injection`.
"""
import sys

sys.path.insert(0, '.')

from FMOFP.Systems.avionics.hardwareHealth.LRUstatus import (
    LRUStatusMonitor, HealthState,
)
import FMOFP.Systems.avionics.hardwareHealth.LRUstatus as lru_mod
from FMOFP.Interfaces.scenarios.scenarioEngine import ScenarioEngine, ScenarioEvent

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


monitor = LRUStatusMonitor()   # not started — no poll thread, no boot needed

# ── 1. force_fault on a catalogued LRU, visible immediately ──────────────────

lru_id = monitor.force_fault("flight_control_computer",
                             detail="scenario test fault")
check("resolve: system_key → lru_id", lru_id == "FCC-1", lru_id)
snap = monitor.get_lru("FCC-1")
check("force: health is FAULT immediately", snap["health"] == "FAULT", str(snap))
check("force: fault_detail marked FORCED",
      snap["fault_detail"].startswith("FORCED:"), str(snap))
check("force: get_faults contains FCC-1",
      any(f["lru_id"] == "FCC-1" for f in monitor.get_faults()))
check("force: overall_health is FAULT",
      monitor.overall_health() == HealthState.FAULT)
check("force: listed in get_forced_faults",
      "FCC-1" in monitor.get_forced_faults())

# resolution by exact lru_id and by unique name substring
check("resolve: lru_id accepted", monitor.resolve_lru_id("fcc-1") == "FCC-1")
check("resolve: unique name substring", monitor.resolve_lru_id("navigation") == "NAV-1")
check("resolve: unknown returns None", monitor.resolve_lru_id("no_such_system") is None)

# ── 2. override survives a poll cycle ────────────────────────────────────────

# This is the regression the August 2026 audit documented: a directly-set
# .health was overwritten by the very next _poll_lru tick. Run the real poll
# and assert the forced state now persists through it.
monitor._poll_all()
snap = monitor.get_lru("FCC-1")
check("poll: forced FAULT survives _poll_all", snap["health"] == "FAULT", str(snap))
check("poll: forced detail survives _poll_all",
      snap["fault_detail"].startswith("FORCED:"), str(snap))

# DEGRADED override also honored by the poll path
monitor.force_fault("FCC-1", state=HealthState.DEGRADED, detail="partial authority")
monitor._poll_all()
check("poll: forced DEGRADED survives _poll_all",
      monitor.get_lru("FCC-1")["health"] == "DEGRADED")

# ── 3. clear restores live derivation ────────────────────────────────────────

cleared = monitor.clear_forced_fault("flight_control_computer")
check("clear: one override cleared", cleared == 1, str(cleared))
monitor._poll_all()
snap = monitor.get_lru("FCC-1")
check("clear: health rederived from live status (not DEGRADED)",
      snap["health"] != "DEGRADED", str(snap))
check("clear: no forced faults remain", monitor.get_forced_faults() == {})

# ── 4. non-catalogued systems become scenario-declared entries ───────────────

before_count = len(monitor.get_all())
syn_id = monitor.force_fault("engine_vibration", state=HealthState.DEGRADED,
                             detail="compressor stall suspected")
check("synthetic: entry created", syn_id in monitor.get_all(), syn_id)
check("synthetic: appears in get_faults",
      any(f["lru_id"] == syn_id for f in monitor.get_faults()))
monitor._poll_all()   # accessor is None → poll leaves it alone
check("synthetic: state survives poll",
      monitor.get_lru(syn_id)["health"] == "DEGRADED")
monitor.clear_forced_fault("engine_vibration")
check("synthetic: fully removed on clear",
      syn_id not in monitor.get_all() and len(monitor.get_all()) == before_count)

# ── 5. ScenarioEngine._inject_failure routes into the monitor ────────────────

# _inject_failure uses the module singleton — install our monitor there.
lru_mod._lru_monitor = monitor

engine = ScenarioEngine()
engine._inject_failure({'system': 'flight_control_computer',
                        'description': 'FCC partial authority'})
check("engine: set action forces FAULT",
      monitor.get_lru("FCC-1")["health"] == "FAULT")

engine._inject_failure({'system': 'radar_management', 'state': 'DEGRADED',
                        'description': 'antenna servo degraded'})
check("engine: state param honored (DEGRADED)",
      monitor.get_lru("RDR-1")["health"] == "DEGRADED")

engine._inject_failure({'system': 'flight_control_computer', 'action': 'clear'})
check("engine: clear action clears the fault",
      "FCC-1" not in monitor.get_forced_faults())

engine._inject_failure({'system': 'x', 'action': 'clear_all'})
check("engine: clear_all clears everything", monitor.get_forced_faults() == {})

# invalid state falls back to FAULT instead of crashing the dispatch thread
engine._inject_failure({'system': 'NAV-1', 'state': 'EXPLODED'})
check("engine: unknown state falls back to FAULT",
      monitor.get_lru("NAV-1")["health"] == "FAULT")
engine._inject_failure({'system': 'x', 'action': 'clear_all'})

# ── 6. failureScenario.xml end-to-end through the real dispatcher ────────────

engine2 = ScenarioEngine()
ok = engine2.load('failureScenario.xml')
check("xml: failureScenario.xml loads", ok)
failure_events = [e for e in engine2._events if e.event_type == 'system_failure']
check("xml: scenario declares system_failure events", len(failure_events) > 0,
      str(len(failure_events)))
for event in failure_events:
    engine2._dispatch(event)
forced = monitor.get_forced_faults()
check("xml: every system_failure event produced a forced fault",
      len(forced) == len(failure_events),
      f"{len(forced)} forced vs {len(failure_events)} events: {sorted(forced)}")
check("xml: overall_health reflects injected failures",
      monitor.overall_health() in (HealthState.FAULT, HealthState.DEGRADED))
monitor.clear_forced_fault(None)
check("xml: clear_forced_fault(None) clears all", monitor.get_forced_faults() == {})

# ── result ───────────────────────────────────────────────────────────────────

print(f"\nScenario failure-injection tests: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
print("Scenario failure injection: all assertions passed")
