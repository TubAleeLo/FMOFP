"""Test suite — thread-restart guard and get_commands error containment.

Guards the two intermittent live-boot defects closed in the August 2026
completion pass:

  1. ThreadManager.start_thread() guarded only on is_alive(). A
     threading.Thread that has already RUN TO COMPLETION is not alive, but
     .start() on it still raises "RuntimeError: threads can only be started
     once" — which is exactly what produced the intermittent
     "Error starting thread 'UserCLI_Input'/'UserCLI_Processing'" errors on
     live boots (those threads exit early with no interactive stdin, and a
     later start attempt hit a dead-but-already-started Thread).

  2. UserCLI.get_commands() wrapped its entire while loop in one
     try/except, so a single unexpected exception ended the thread
     permanently — and since a Thread cannot be restarted, CLI input was
     gone for the rest of the session. Each iteration is now contained,
     with a consecutive-failure circuit breaker.

Standalone-safe: run from B20SS/ as
`python -m FMOFP.Tests.test_thread_and_cli_resilience`.
"""
import sys
import threading
import time

sys.path.insert(0, '.')

from FMOFP.Utils.common.thread_manager import ThreadManager, ThreadState

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


# ── 1. thread-restart guard ──────────────────────────────────────────────────

tm = ThreadManager()
tm.add_thread("resilience_probe", lambda: None)     # returns immediately
check("thread: registered", "resilience_probe" in tm.threads)

started = tm.start_thread("resilience_probe")
check("thread: first start succeeds", started is True)

# Let it run to completion — now not alive, but already started.
tm.threads["resilience_probe"].thread.join(timeout=5)
probe = tm.threads["resilience_probe"].thread
check("thread: has finished", not probe.is_alive())
check("thread: ident retained after death (the restart discriminator)",
      probe.ident is not None)

# Pre-fix this call reached .start() and raised RuntimeError, which the
# handler logged as "Error starting thread ...". It must now decline quietly.
errors = []
_orig_error = None
try:
    import FMOFP.Utils.common.thread_manager as tm_mod
    _orig_error = tm_mod.logger.error
    tm_mod.logger.error = lambda *a, **k: errors.append(a[0] if a else "")
    restarted = tm.start_thread("resilience_probe")
finally:
    if _orig_error is not None:
        tm_mod.logger.error = _orig_error

check("thread: restart returns False instead of raising", restarted is False)
check("thread: restart logs no ERROR", not errors, str(errors))
check("thread: state not corrupted to ERROR",
      tm.threads["resilience_probe"].state != ThreadState.ERROR,
      str(tm.threads["resilience_probe"].state))

# A never-started thread must still start normally (guard isn't over-broad).
tm.add_thread("resilience_probe2", lambda: time.sleep(0.2))
check("thread: unstarted thread still starts",
      tm.start_thread("resilience_probe2") is True)
tm.threads["resilience_probe2"].thread.join(timeout=5)


# ── 2. get_commands error containment ────────────────────────────────────────

# Drive the real method against a stub so the loop's failure behavior can be
# exercised without booting the CLI, its singletons, or its config.
from FMOFP.Utils.debug.userCLI import UserCLI


class _ExplodingStateManager:
    """cli_state_node is present, so the loop enters the branch that reads
    get_cli_state() — which always raises."""
    cli_state_node = object()

    def __init__(self):
        self.calls = 0

    def get_cli_state(self):
        self.calls += 1
        raise RuntimeError("simulated transient CLI state failure")


class _Stub:
    def __init__(self):
        self.stop_threads = False
        self.cli_enabled = True
        self._stdin_eof = False
        self.prompt_shown = False
        self.state_manager = _ExplodingStateManager()


stub = _Stub()
t0 = time.monotonic()
worker = threading.Thread(
    target=UserCLI.get_commands, args=(stub,), daemon=True)
worker.start()

# The breaker is 10 consecutive failures with a 0.5s pause between them, so
# it self-terminates in ~5s rather than spinning or hanging.
worker.join(timeout=30)
elapsed = time.monotonic() - t0

check("cli: loop survived repeated failures (retried, did not exit on #1)",
      stub.state_manager.calls >= 10,
      f"only {stub.state_manager.calls} attempts")
check("cli: circuit breaker terminated the loop", not worker.is_alive(),
      "thread still running")
check("cli: breaker disabled input rather than spinning",
      stub.cli_enabled is False)
check("cli: breaker paced its retries (did not hot-spin)", elapsed >= 4.0,
      f"{elapsed:.1f}s for 10 attempts")
check("cli: terminated promptly once tripped", elapsed < 20,
      f"{elapsed:.1f}s")

# A clean stub must exit immediately when asked to stop (no breaker involved).
class _QuietStateManager:
    cli_state_node = None


quiet = _Stub()
quiet.state_manager = _QuietStateManager()
quiet.stop_threads = True
t0 = time.monotonic()
UserCLI.get_commands(quiet)
check("cli: honors stop_threads immediately",
      time.monotonic() - t0 < 1.0)
check("cli: healthy path leaves input enabled", quiet.cli_enabled is True)

# ── result ───────────────────────────────────────────────────────────────────

print(f"\nThread/CLI resilience tests: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
print("Thread/CLI resilience: all assertions passed")
