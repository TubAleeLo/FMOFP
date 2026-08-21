"""CI boot smoke test — proves the application's real entry path can start.

Motivation (August 2026): commit 8f37be6 introduced a self-deadlock in
SystemStateManager.__new__/_initialize (non-reentrant class _lock re-acquired
while already held), which made `import FMOFP.core.system_manager` — and
therefore Main.py — hang forever on first construction. CI stayed green for
eight days because no CI test exercised the boot path. This test exists so
that class of regression ("green CI, unlaunchable app") can never pass CI
again.

Design: each check runs in a SUBPROCESS with a hard timeout, because the
failure mode being guarded against is an infinite hang, not an exception.
The child uses os._exit(0) after success so lingering non-daemon background
threads spawned at import time cannot keep it alive.

Run from B20SS/:  python FMOFP/Tests/ci_test_boot_smoke.py
"""
import os
import subprocess
import sys

TIMEOUT_S = 120  # generous: CI runners are slow; a deadlock hangs forever anyway

CHECKS = [
    (
        "SystemStateManager constructs without deadlock",
        "from FMOFP.Utils.common.system_state_manager import SystemStateManager\n"
        "s1 = SystemStateManager(); s2 = SystemStateManager()\n"
        "assert s1 is s2, 'singleton violated'\n"
        "import os; print('OK'); os._exit(0)\n",
    ),
    (
        "core.system_manager imports (module-level SystemManager() boot object)",
        "import FMOFP.core.system_manager as sm\n"
        "assert sm.get_system_manager() is not None\n"
        "import os; print('OK'); os._exit(0)\n",
    ),
    (
        # Guards the display-node lock-held-notify deadlock class (August
        # 2026): VisualNode.update()/ModeNode.update() awaited
        # _notify_subscribers() while holding the node's non-reentrant
        # threading.Lock, which _notify_subscribers() re-acquires — hanging
        # initialize_system() forever on the first display-tree update of
        # boot, even though importing system_manager succeeded (which is
        # why the import check above could not catch it).
        "VisualNode/ModeNode.update(notify=True) completes without deadlock",
        "import asyncio, os\n"
        "from FMOFP.Interfaces.userInterface.displays.display_nodes.visual_node import VisualNode\n"
        "from FMOFP.Interfaces.userInterface.displays.display_nodes.mode_node import ModeNode\n"
        "async def main():\n"
        "    seen = []\n"
        "    async def sub(name, value): seen.append(name)\n"
        "    vn = VisualNode('smoke_visual')\n"
        "    vn.add_subscriber(sub)\n"
        "    await asyncio.wait_for(vn.update({'elements': []}, notify=True), 30)\n"
        "    mn = ModeNode('smoke_mode')\n"
        "    mn.add_subscriber(sub)\n"
        "    await asyncio.wait_for(mn.update('STANDBY', notify=True), 30)\n"
        "    assert len(seen) == 2, f'subscribers not notified: {seen}'\n"
        "asyncio.run(main())\n"
        "print('OK'); os._exit(0)\n",
    ),
    (
        # Full end-to-end boot: initialize → start → an operational system
        # state, i.e. what SystemStart.py/Main.py actually do. This is the
        # check that fails if ANY future regression stalls the boot chain,
        # whatever its mechanism (it caught the operation_tracker
        # lock-across-callback event-loop freeze that the three targeted
        # checks above could not see). RUNNING is transient — the system
        # settles into NORMAL within ~1s — so both count as success.
        "full boot reaches an operational SystemState",
        # Mirrors SystemStart.py's bootstrap exactly, INCLUDING the
        # dual-path import shim: without it, FMOFP.Utils.* and Utils.*
        # resolve to two separate module objects, so this check would poll
        # a different SystemStateManager singleton than the one the boot
        # path updates and never see RUNNING.
        "import sys, os\n"
        "sys.path.insert(0, os.path.join(os.getcwd(), 'FMOFP'))\n"
        "from Utils.dual_path_compat import install as _i; _i()\n"
        "import asyncio\n"
        "from FMOFP.core.initializer import get_initializer\n"
        "from FMOFP.Utils.common.system_states import SystemState\n"
        "from FMOFP.Utils.common.system_state_manager import get_system_state_manager\n"
        "init = get_initializer(); init.initialize()\n"
        "loop = init.get_loop()\n"
        "from Main import start_fmofp\n"
        "async def watch():\n"
        "    sm = get_system_state_manager()\n"
        "    for _ in range(600):\n"
        "        await asyncio.sleep(0.1)\n"
        "        try:\n"
        "            state = sm.get_state()\n"
        "        except ValueError:\n"
        "            continue  # state node not created yet\n"
        "        if state in (SystemState.RUNNING, SystemState.NORMAL):\n"
        "            print('OK'); os._exit(0)\n"
        "    print('never reached an operational state'); os._exit(5)\n"
        # Keep strong references to both tasks: asyncio holds only weak
        # refs, and an unreferenced pending task can be garbage-collected
        # mid-flight (observed live here — the watcher silently vanished).
        "_t1 = loop.create_task(start_fmofp())\n"
        "_t2 = loop.create_task(watch())\n"
        "loop.run_forever()\n",
    ),
]


def run_check(name: str, code: str) -> bool:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    cwd = os.getcwd()
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (cwd, os.path.join(cwd, "FMOFP"), env.get("PYTHONPATH", "")) if p
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            timeout=TIMEOUT_S,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        print(f"  ✗  {name}: TIMED OUT after {TIMEOUT_S}s (deadlock/hang on boot path)")
        return False
    if proc.returncode != 0:
        print(f"  ✗  {name}: exit code {proc.returncode}")
        tail = "\n".join((proc.stderr or proc.stdout or "").splitlines()[-15:])
        print(tail)
        return False
    print(f"  ✓  {name}")
    return True


def main() -> int:
    print("Boot smoke test (each check subprocess-isolated, "
          f"{TIMEOUT_S}s watchdog):")
    failures = [name for name, code in CHECKS if not run_check(name, code)]
    if failures:
        print(f"Boot smoke test FAILED: {len(failures)}/{len(CHECKS)} checks failed")
        return 1
    print("Boot smoke test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
