"""Test suite — RadarManagementSystem loop distinguishes shutdown from ill health.

Guards the August 2026 fix for the last error left in an otherwise clean
boot log: `RadarMain thread (ID: ...) detected unhealthy system`, logged at
ERROR on essentially every normal run.

Cause: `RadarManagementSystem._update_loop()` evaluated `is_healthy()`, which returns
`self.running and radar_health`. Once a shutdown cleared the `_running`
event, that call returned False for a perfectly healthy system, and the loop
reported the normal stop as a fault. Live-traced at ~107 ms after the
NORMAL -> SHUTTING_DOWN transition.

Fix: re-check `running` first and exit quietly; reserve the ERROR for a
radar that is genuinely unhealthy while the system is still meant to run.

Both directions are asserted here, because a fix that simply silenced the
message would be worse than the bug:
  1. Shutdown path  -> loop exits, NO error logged.
  2. Unhealthy path -> loop exits, error IS logged (still reports faults).
  3. Healthy path   -> loop keeps running.

Standalone-safe: run from B20SS/ as
`python -m FMOFP.Tests.test_radar_shutdown_health`.
"""
import os
import sys
import threading
import time

# Path setup — mirrors setup_env.py. radarControl's import chain uses
# bare-package imports (`from Utils...`), so B20SS/FMOFP must be on the path
# too, not just B20SS.
_B20SS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for _p in (_B20SS, os.path.join(_B20SS, 'FMOFP')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import FMOFP.Systems.radarManagement.radarControl as rc_mod
from FMOFP.Systems.radarManagement.radarControl import RadarManagementSystem

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


class _CapturedLogger:
    """Records error/info calls made by the loop under test."""

    def __init__(self, real):
        self._real = real
        self.errors = []
        self.infos = []

    def error(self, msg, *a, **k):
        self.errors.append(str(msg))

    def info(self, msg, *a, **k):
        self.infos.append(str(msg))

    def __getattr__(self, item):
        return getattr(self._real, item)


class _Stub:
    """Duck-typed stand-in exposing only what _update_loop touches, so the
    loop can be driven without booting radars, messaging, or Qt."""

    def __init__(self, healthy=True):
        self._running = threading.Event()
        self._running.set()
        self.radars = {}
        self._healthy = healthy

    @property
    def running(self):
        return self._running.is_set()

    def is_healthy(self):
        # Mirrors the real implementation's shape: running AND radar health.
        return self.running and self._healthy


def run_loop(stub, stop_after=None):
    """Drive the real _update_loop against a stub, optionally flipping a
    condition from another thread once the loop is under way."""
    captured = _CapturedLogger(rc_mod.logger)
    rc_mod.logger = captured
    try:
        if stop_after:
            threading.Timer(0.25, stop_after).start()
        worker = threading.Thread(
            target=RadarManagementSystem._update_loop, args=(stub,), daemon=True)
        worker.start()
        worker.join(timeout=15)
        return captured, worker
    finally:
        rc_mod.logger = captured._real


# ── 1. shutdown path: exits, logs no ERROR ───────────────────────────────────

# 1a. Flag cleared BETWEEN iterations — the `while self.running` guard at
# the top of the loop catches it. Always exited cleanly, even pre-fix.
stub = _Stub(healthy=True)
captured, worker = run_loop(stub, stop_after=lambda: stub._running.clear())

check("shutdown (between iterations): loop exited", not worker.is_alive())
check("shutdown (between iterations): no ERROR", not captured.errors,
      str(captured.errors))

# 1b. Flag cleared DURING an iteration — this is the real boot case (a
# shutdown lands while radar.update() work is in flight) and the one that
# produced the spurious ERROR: the loop is already past its `while` guard,
# so it reaches the health check with running already False. Made
# deterministic by clearing the flag from inside the radars iteration,
# rather than racing a timer against it.
class _ClearsDuringIteration(dict):
    def __init__(self, stub):
        super().__init__()
        self._stub = stub

    def values(self):
        self._stub._running.clear()
        return []


stub = _Stub(healthy=True)
stub.radars = _ClearsDuringIteration(stub)
captured, worker = run_loop(stub)

check("shutdown (mid-iteration): loop exited", not worker.is_alive())
unhealthy_errors = [e for e in captured.errors if "unhealthy" in e]
check("shutdown (mid-iteration): no 'detected unhealthy system' ERROR "
      "[THE REGRESSION]", not unhealthy_errors, str(unhealthy_errors))
check("shutdown (mid-iteration): no ERROR of any kind", not captured.errors,
      str(captured.errors))
check("shutdown (mid-iteration): reported the stop at INFO",
      any("shutting down" in m for m in captured.infos), str(captured.infos))

# ── 2. genuinely unhealthy: still reports the fault ──────────────────────────

# System is still meant to be running (_running set), but radar health fails.
stub = _Stub(healthy=True)


def _go_unhealthy():
    stub._healthy = False


captured, worker = run_loop(stub, stop_after=_go_unhealthy)

check("unhealthy: loop exited", not worker.is_alive())
check("unhealthy: ERROR still logged (fault reporting preserved)",
      any("unhealthy" in e for e in captured.errors), str(captured.errors))
check("unhealthy: _running cleared on fault", not stub.running)

# ── 3. healthy path: loop keeps running ──────────────────────────────────────

stub = _Stub(healthy=True)
captured = _CapturedLogger(rc_mod.logger)
rc_mod.logger = captured
try:
    worker = threading.Thread(
        target=RadarManagementSystem._update_loop, args=(stub,), daemon=True)
    worker.start()
    time.sleep(0.6)
    still_running = worker.is_alive()
    errors_while_healthy = list(captured.errors)
    stub._running.clear()          # ask it to stop
    worker.join(timeout=10)
finally:
    rc_mod.logger = captured._real

check("healthy: loop kept running while healthy", still_running)
check("healthy: no errors while healthy", not errors_while_healthy,
      str(errors_while_healthy))
check("healthy: exits promptly when asked to stop", not worker.is_alive())

# ── result ───────────────────────────────────────────────────────────────────

print(f"\nRadar shutdown-health tests: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
print("Radar shutdown health: all assertions passed")
