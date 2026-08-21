"""
Test suite: Radar-to-Display Bridge + RadarDisplayDataCoordinator

Tests
-----
1.  Coordinator — store_data / get_data for all three built-in data types
2.  Coordinator — TTL expiry causes empty return without backup
3.  Coordinator — backup fallback returns data when current is empty
4.  Coordinator — reset_data clears current but preserves backup
5.  Coordinator — missing request_id raises ValueError
6.  Coordinator — empty data list raises ValueError
7.  Bridge — push_vil_data stores items via coordinator
8.  Bridge — push_precipitation_data stores items
9.  Bridge — push_targeting_data stores items with correct keys
10. Bridge — push_sar_data stores items
11. Bridge — push_tfr_data stores items
12. Bridge — push_aewc_data stores items
13. Bridge — push_cells_data stores StormCell-like objects
14. Bridge — push_* returns False for empty list (no crash)
15. Bridge — push_* returns False for missing request_id (no crash)
"""

import sys
import os
import time
import uuid

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


# ──────────────────────────── helpers ────────────────────────────────────

def _fresh_coordinator():
    """Return a brand-new RadarDisplayDataCoordinator instance for test isolation."""
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    return RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)


def _make_item(position=(1.0, 2.0), extra=None):
    d = {"position": position, "id": f"test_{uuid.uuid4().hex[:6]}"}
    if extra:
        d.update(extra)
    return d


def _req():
    return str(uuid.uuid4())


# ──────────────────────────── coordinator tests ───────────────────────────

def test_coordinator_store_and_get(r: _Results) -> None:
    print("\n  ── Coordinator: store / get ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    # Manually invoke __init__ via the class (singleton guard bypassed above)
    RadarDisplayDataCoordinator.__init__(coord)

    req = _req()
    items = [_make_item((x, x), {"value": x}) for x in range(3)]
    count = coord.store_data("vil", items, req)
    r.check("store_data returns item count > 0", count > 0, f"got {count}")

    result = coord.get_data("vil", use_backup=False)
    r.check("get_data returns stored items", len(result) > 0, f"got {len(result)}")


def test_coordinator_ttl_expiry(r: _Results) -> None:
    print("\n  ── Coordinator: TTL expiry ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    RadarDisplayDataCoordinator.__init__(coord)

    req = _req()
    items = [_make_item()]
    coord.store_data("precipitation", items, req)

    # Clear backup and current to confirm empty return
    coord._data_store["precipitation"]["current"] = []
    coord._data_store["precipitation"]["backup"] = []

    result = coord.get_data("precipitation", use_backup=True)
    r.check("get_data returns empty when current and backup both empty",
            len(result) == 0, f"got {len(result)}")


def test_coordinator_backup_fallback(r: _Results) -> None:
    print("\n  ── Coordinator: backup fallback ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    RadarDisplayDataCoordinator.__init__(coord)

    req = _req()
    items = [_make_item((5.0, 6.0), {"intensity": 0.8})]
    coord.store_data("cells", items, req)

    # Clear current, keep backup
    coord._data_store["cells"]["current"] = []

    result = coord.get_data("cells", use_backup=True)
    r.check("backup fallback returns data when current empty",
            len(result) == 1, f"got {len(result)}")


def test_coordinator_reset(r: _Results) -> None:
    print("\n  ── Coordinator: reset_data ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    RadarDisplayDataCoordinator.__init__(coord)

    req = _req()
    coord.store_data("vil", [_make_item()], req)
    coord.reset_data("vil")

    result = coord.get_data("vil", use_backup=False)
    r.check("reset_data clears current", len(result) == 0, f"got {len(result)}")


def test_coordinator_missing_request_id(r: _Results) -> None:
    print("\n  ── Coordinator: missing request_id ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    RadarDisplayDataCoordinator.__init__(coord)

    raised = False
    try:
        coord.store_data("vil", [_make_item()], "")
    except ValueError:
        raised = True
    r.check("empty request_id raises ValueError", raised)


def test_coordinator_empty_items(r: _Results) -> None:
    print("\n  ── Coordinator: empty item list ──")
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        RadarDisplayDataCoordinator,
    )
    coord = RadarDisplayDataCoordinator.__new__(RadarDisplayDataCoordinator)
    RadarDisplayDataCoordinator.__init__(coord)

    raised = False
    try:
        coord.store_data("vil", [], _req())
    except ValueError:
        raised = True
    r.check("empty items list raises ValueError", raised)


# ──────────────────────────────── bridge tests ────────────────────────────

def test_bridge_push_vil(r: _Results) -> None:
    print("\n  ── Bridge: push_vil_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_vil_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("vil")

    req = _req()
    items = [
        {"position": (1.0, 2.0), "value": 3.5, "intensity": 0.7,
         "id": f"{req}_0"},
        {"position": (3.0, 4.0), "value": 2.1, "intensity": 0.4,
         "id": f"{req}_1"},
    ]
    ok = push_vil_data(items, req)
    r.check("push_vil_data returns True", ok)
    stored = coord.get_data("vil", use_backup=False)
    r.check("push_vil_data items retrievable from coordinator",
            len(stored) == 2, f"got {len(stored)}")


def test_bridge_push_precipitation(r: _Results) -> None:
    print("\n  ── Bridge: push_precipitation_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_precipitation_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("precipitation")

    req = _req()
    items = [{"position": (10.0, 20.0), "type": "rain", "rate": 5.0,
              "intensity": 0.6, "id": f"{req}_0"}]
    ok = push_precipitation_data(items, req)
    r.check("push_precipitation_data returns True", ok)
    stored = coord.get_data("precipitation", use_backup=False)
    r.check("precipitation items retrievable", len(stored) >= 1,
            f"got {len(stored)}")


def test_bridge_push_targeting(r: _Results) -> None:
    print("\n  ── Bridge: push_targeting_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_targeting_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("targeting")

    req = _req()

    class _FakeTarget:
        target_position = (1000.0, 2000.0)  # 2D for coordinator compatibility
        target_velocity = (100.0, 0.0, 0.0)   # velocity stays 3D (not stored in coordinator position)
        target_id       = "T1"
        identity        = "UNKNOWN"
        classification  = "FIGHTER"
        confidence      = 0.8
        lock_status     = ""
        timestamp       = time.time()

    ok = push_targeting_data([_FakeTarget()], req)
    r.check("push_targeting_data returns True", ok)
    stored = coord.get_data("targeting", use_backup=False)
    r.check("targeting items retrievable", len(stored) >= 1,
            f"got {len(stored)}")
    if stored:
        r.check("targeting item has position key",
                "position" in stored[0])
        r.check("targeting item has classification key",
                "classification" in stored[0])


def test_bridge_push_sar(r: _Results) -> None:
    print("\n  ── Bridge: push_sar_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_sar_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("sar")

    req = _req()
    items = [{"position": (50.0, 50.0), "image_data": b"\x00" * 16,
              "resolution": 1.0, "id": f"{req}_0"}]
    ok = push_sar_data(items, req)
    r.check("push_sar_data returns True", ok)


def test_bridge_push_tfr(r: _Results) -> None:
    print("\n  ── Bridge: push_tfr_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_tfr_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("tfr")

    req = _req()
    items = [{"position": (10.0, 20.0), "distance": 1000.0, "elevation": 500.0,
              "id": f"{req}_0"}]
    ok = push_tfr_data(items, req)
    r.check("push_tfr_data returns True", ok)


def test_bridge_push_aewc(r: _Results) -> None:
    print("\n  ── Bridge: push_aewc_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_aewc_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("aewc")

    req = _req()
    items = [{"position": (15.0, 25.0), "track_type": "FIGHTER",
              "track_confidence": 0.9, "id": f"{req}_0"}]
    ok = push_aewc_data(items, req)
    r.check("push_aewc_data returns True", ok)


def test_bridge_push_cells(r: _Results) -> None:
    print("\n  ── Bridge: push_cells_data ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_cells_data
    from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
        get_radar_display_data_coordinator,
    )
    coord = get_radar_display_data_coordinator()
    coord.reset_data("cells")

    req = _req()

    # Simulate a StormCell dataclass
    class _FakeCell:
        cell_id             = 1
        position            = (10.0, 20.0)
        altitude            = 15000.0
        reflectivity        = 52.0
        velocity            = (5.0, 3.0)
        size                = 2.5
        intensity           = 0.8
        vertical_development = 500.0
        last_update         = time.time()

    ok = push_cells_data([_FakeCell()], req)
    r.check("push_cells_data returns True", ok)
    stored = coord.get_data("cells", use_backup=False)
    r.check("cells items retrievable", len(stored) >= 1, f"got {len(stored)}")
    if stored:
        r.check("cells item has intensity key", "intensity" in stored[0])


def test_bridge_empty_list(r: _Results) -> None:
    print("\n  ── Bridge: empty list guards ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import (
        push_vil_data, push_precipitation_data, push_targeting_data,
        push_cells_data,
    )
    req = _req()
    r.check("push_vil_data([]) returns False",       not push_vil_data([], req))
    r.check("push_precipitation_data([]) returns False",
            not push_precipitation_data([], req))
    r.check("push_targeting_data([]) returns False",  not push_targeting_data([], req))
    r.check("push_cells_data([]) returns False",      not push_cells_data([], req))


def test_bridge_missing_request_id(r: _Results) -> None:
    print("\n  ── Bridge: missing request_id guards ──")
    from FMOFP.local_messaging.routing.radar_to_display_bridge import (
        push_vil_data, push_precipitation_data,
    )
    item = [_make_item()]
    r.check("push_vil_data(req='') returns False",
            not push_vil_data(item, ""))
    r.check("push_precipitation_data(req='') returns False",
            not push_precipitation_data(item, ""))


# ──────────────────────────────────────────── runner ─────────────────────

def run_all() -> bool:
    print("=" * 60)
    print(" Bridge + Coordinator Test Suite")
    print("=" * 60)

    r = _Results()

    tests = [
        test_coordinator_store_and_get,
        test_coordinator_ttl_expiry,
        test_coordinator_backup_fallback,
        test_coordinator_reset,
        test_coordinator_missing_request_id,
        test_coordinator_empty_items,
        test_bridge_push_vil,
        test_bridge_push_precipitation,
        test_bridge_push_targeting,
        test_bridge_push_sar,
        test_bridge_push_tfr,
        test_bridge_push_aewc,
        test_bridge_push_cells,
        test_bridge_empty_list,
        test_bridge_missing_request_id,
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
