"""Aggregating test runner — runs every standalone-safe test suite with one
real exit code.

Why this exists (August 2026 production-readiness follow-up): the repo had 23
test files but CI executed only 7 of them as individually-maintained workflow
steps, and PLANNING.md had already flagged that several test entry points
discard run_tests()'s result (false-positive risk). This runner is the single
source of truth for "the test suite": it subprocess-isolates each suite,
enforces a per-suite watchdog timeout (a hang is a failure, not a stall —
see ci_test_boot_smoke.py for why that matters here), aggregates results,
and exits nonzero if ANY suite fails, times out, or crashes.

Run from B20SS/:  python FMOFP/Tests/run_all_tests.py

Suites deliberately NOT run here, with reasons:
  - CLI-harness-only tests (exit 1 by design when run standalone, printing
    "This test should be run via the user CLI 'test' command"):
      fms_system_test, flight_control_system_test, predefined_messages_test,
      combined_precipitation_vil_flow_test, weather_radar_surveillance_mode_test,
      radar_tests/{weather,targeting,sar,tfr,aewc}_radar_test
    These require the full live system booted behind the debug CLI. Making
    them standalone-runnable is tracked in PLANNING.md (Next Steps).
  - test_weather_radar_holographic_display: interactive GUI test — enters
    QApplication.exec() and never exits; visual inspection only.
  - performance_profile: a profiler, not a pass/fail test.
  - setup_env: an import helper, not a test.
"""
import os
import subprocess
import sys
import time

# (module path run with -m?, name, timeout seconds)
SUITES = [
    (True,  "FMOFP.Tests.ci_test_boot_smoke", 300),
    (True,  "FMOFP.Tests.test_bridge_and_coordinator", 300),
    (True,  "FMOFP.Tests.test_displays_headless", 300),
    (False, "FMOFP/Tests/ci_test_weather_radar.py", 300),
    (False, "FMOFP/Tests/ci_test_scenario_engine.py", 300),
    (True,  "FMOFP.Tests.test_power_fuel_thrust", 300),
    (True,  "FMOFP.Tests.test_hydr_airframe_ecs_fdm_fitness_swcm", 300),
    (True,  "FMOFP.Tests.test_toctou_start_race_regression", 600),
    (True,  "FMOFP.Tests.test_precipitation_data_transfer", 300),
    (True,  "FMOFP.Tests.test_install_script", 300),
]


def run_suite(as_module: bool, name: str, timeout_s: int):
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    cwd = os.getcwd()
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (cwd, env.get("PYTHONPATH", "")) if p
    )
    cmd = [sys.executable, "-m", name] if as_module else [sys.executable, name]
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, timeout=timeout_s, capture_output=True, text=True,
            env=env, cwd=cwd,
        )
        elapsed = time.monotonic() - start
        return proc.returncode, elapsed, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        out = exc.stdout or b""
        err = exc.stderr or b""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        return "TIMEOUT", elapsed, out, err


def main() -> int:
    print(f"Running {len(SUITES)} test suites "
          "(subprocess-isolated, per-suite watchdog)\n" + "=" * 60)
    failures = []
    for as_module, name, timeout_s in SUITES:
        rc, elapsed, out, err = run_suite(as_module, name, timeout_s)
        label = name.rsplit("/", 1)[-1]
        if label.endswith(".py"):
            label = label[:-3]
        else:
            label = label.rsplit(".", 1)[-1]
        if rc == 0:
            print(f"  ✓  {label:<45s} {elapsed:6.1f}s")
        else:
            status = "TIMED OUT" if rc == "TIMEOUT" else f"exit {rc}"
            print(f"  ✗  {label:<45s} {elapsed:6.1f}s  ({status})")
            failures.append((name, rc))
            tail = "\n".join((err or out).splitlines()[-20:])
            print("     ┌─ last output " + "─" * 40)
            for line in tail.splitlines():
                print("     │ " + line)
            print("     └" + "─" * 54)
    print("=" * 60)
    if failures:
        print(f"FAILED: {len(failures)}/{len(SUITES)} suites: "
              + ", ".join(n for n, _ in failures))
        return 1
    print(f"All {len(SUITES)} suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
