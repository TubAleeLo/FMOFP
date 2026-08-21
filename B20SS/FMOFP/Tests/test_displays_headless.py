"""
Test suite: EICAS / TSD / SMS display smoke tests (headless)

Each display is instantiated, its internal state is populated with
representative data, and paint_display() is called through a real
QPainter on an off-screen QPixmap.  The test passes if no exception
is raised and the pixmap is not null.

Qt is initialised in offscreen mode so no X server / compositor is needed.
"""

import os
import sys

# Force Qt to use the offscreen platform before ANY Qt library is loaded.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

_B20SS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for _p in (_B20SS, os.path.join(_B20SS, 'FMOFP')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# QApplication MUST exist before any QWidget subclass is instantiated.
# Create it here at module level, before any FMOFP imports that may
# trigger Qt widget construction during module initialisation.
from PyQt6.QtWidgets import QApplication as _QApp
_APP = _QApp.instance() or _QApp(sys.argv)

import time
import traceback

from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()


# ─────────────────────────────────────────────────────── framework ───────

class _Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self._failures = []

    def check(self, name, cond, detail=""):
        if cond:
            self.passed += 1
            print(f"  ✓  {name}")
        else:
            self.failed += 1
            msg = f"  ✗  {name}" + (f"  [{detail}]" if detail else "")
            print(msg)
            self._failures.append(msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n  {self.passed}/{total} passed")
        if self._failures:
            print("\n  Failures:")
            for f in self._failures:
                print(f"    {f}")
        return self.failed == 0


def _qt_app():
    """Return the QApplication singleton (created at module level)."""
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or _APP


def _paint_widget(widget) -> bool:
    """
    Call paint_display() via a real QPainter on a 800×600 QPixmap.
    Returns True if no exception was raised.
    """
    from PyQt6.QtGui import QPainter, QPixmap
    from PyQt6.QtCore import Qt

    # Stop background timers so they cannot fire during the sync paint call
    for attr in ("_poll_timer", "_update_timer"):
        timer = getattr(widget, attr, None)
        if timer is not None and hasattr(timer, "stop"):
            try:
                timer.stop()
            except Exception:
                pass

    pixmap = QPixmap(800, 600)
    pixmap.fill(Qt.GlobalColor.black)
    painter = QPainter(pixmap)
    try:
        widget._running = True
        widget.resize(800, 600)
        widget.paint_display(painter)
        return True
    except Exception as exc:
        print(f"    paint_display raised: {exc}")
        traceback.print_exc()
        return False
    finally:
        painter.end()


# ───────────────────────────── EICAS tests ───────────────────────────────

def test_eicas_instantiation(r: _Results) -> None:
    print("\n  ── EICAS: instantiation ──")
    _qt_app()
    try:
        from FMOFP.Interfaces.userInterface.displays.eicas import EICASDisplay
        disp = EICASDisplay()
        r.check("EICASDisplay instantiates without error", True)
        r.check("has _engine dict",  hasattr(disp, "_engine"))
        r.check("has _fuel dict",    hasattr(disp, "_fuel"))
        r.check("has _hydraulic dict", hasattr(disp, "_hydraulic"))
        r.check("has _electrical dict", hasattr(disp, "_electrical"))
        r.check("has _alerts list",  hasattr(disp, "_alerts"))
        disp.stop()
    except Exception as exc:
        r.check("EICASDisplay instantiates without error", False, str(exc))


def test_eicas_paint_normal(r: _Results) -> None:
    print("\n  ── EICAS: paint in normal state ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.eicas import EICASDisplay
    disp = EICASDisplay()
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds in normal state", ok)
    disp.stop()


def test_eicas_paint_warnings(r: _Results) -> None:
    print("\n  ── EICAS: paint with active warnings ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.eicas import EICASDisplay
    disp = EICASDisplay()
    # Force alert-generating conditions
    disp._engine["egt_c"]     = 850.0  # above WARNING threshold
    disp._engine["oil_psi"]   = 35.0   # below LOW threshold
    disp._fuel["total_kg"]    = 300.0  # below WARN threshold
    disp._hydraulic["sys_a_psi"] = 1800.0  # below WARN threshold
    disp._alerts = disp._compute_alerts(disp._engine["thrust_pct"])
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds with active warnings", ok)
    r.check("alerts list is non-empty", len(disp._alerts) > 0,
            f"got {len(disp._alerts)}")
    has_warn = any(a["severity"] == "WARNING" for a in disp._alerts)
    r.check("at least one WARNING alert generated", has_warn)
    disp.stop()


def test_eicas_compute_alerts(r: _Results) -> None:
    print("\n  ── EICAS: _compute_alerts logic ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.eicas import EICASDisplay
    disp = EICASDisplay()

    # All in-limits → no alerts
    disp._engine["egt_c"]   = 600.0
    disp._engine["oil_psi"] = 65.0
    disp._fuel["total_kg"]  = 5000.0
    alerts_ok = disp._compute_alerts(70.0)
    r.check("no alerts when all parameters in limits",
            len(alerts_ok) == 0, f"got {len(alerts_ok)}")

    # EGT above warning threshold
    disp._engine["egt_c"] = 820.0
    alerts_egt = disp._compute_alerts(70.0)
    r.check("EGT > 800 → WARNING alert",
            any(a["severity"] == "WARNING" and "EGT" in a["text"]
                for a in alerts_egt))
    disp.stop()


# ───────────────────────────── TSD tests ─────────────────────────────────

def test_tsd_instantiation(r: _Results) -> None:
    print("\n  ── TSD: instantiation ──")
    _qt_app()
    try:
        from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
        disp = TacticalSituationDisplay()
        r.check("TacticalSituationDisplay instantiates", True)
        r.check("has _threats list", hasattr(disp, "_threats"))
        r.check("has _heading",      hasattr(disp, "_heading"))
        r.check("has _g_force",      hasattr(disp, "_g_force"))
        disp.stop()
    except Exception as exc:
        r.check("TacticalSituationDisplay instantiates", False, str(exc))


def test_tsd_paint_normal(r: _Results) -> None:
    print("\n  ── TSD: paint in normal state ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
    disp = TacticalSituationDisplay()
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds in normal state", ok)
    disp.stop()


def test_tsd_paint_with_threats(r: _Results) -> None:
    print("\n  ── TSD: paint with threat contacts ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
    disp = TacticalSituationDisplay()
    disp._heading  = 180.0
    disp._airspeed = 420.0
    disp._altitude = 28000.0
    disp._g_force  = 3.5
    disp._threats  = [
        {"bearing": 45.0, "range_nm": 15.0, "type": "FIGHTER", "hostile": True},
        {"bearing": 270.0, "range_nm": 40.0, "type": "SAM",    "hostile": True},
        {"bearing": 120.0, "range_nm": 55.0, "type": "UNKNOWN","hostile": False},
    ]
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds with threat contacts", ok)
    disp.stop()


def test_tsd_simulate_threats_fallback(r: _Results) -> None:
    print("\n  ── TSD: _simulate_threats fallback ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
    disp = TacticalSituationDisplay()
    # With _fusion = None, _get_fused_threats falls back to _simulate_threats
    disp._fusion = None
    threats = disp._get_fused_threats()
    r.check("_get_fused_threats returns list",       isinstance(threats, list))
    r.check("fallback produces at least one threat", len(threats) > 0,
            f"got {len(threats)}")
    r.check("threat has bearing key",  all("bearing"  in t for t in threats))
    r.check("threat has range_nm key", all("range_nm" in t for t in threats))
    disp.stop()


def test_tsd_paint_combat_mode(r: _Results) -> None:
    print("\n  ── TSD: paint in COMBAT mode ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
    disp = TacticalSituationDisplay()
    disp._mode = "COMBAT"
    disp._g_force = 7.2
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds in COMBAT mode", ok)
    disp.stop()


# ───────────────────────────── SMS tests ─────────────────────────────────

def test_sms_instantiation(r: _Results) -> None:
    print("\n  ── SMS: instantiation ──")
    _qt_app()
    try:
        from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
        disp = StoresManagementDisplay()
        r.check("StoresManagementDisplay instantiates", True)
        r.check("has _stations list",    hasattr(disp, "_stations"))
        r.check("has _master_arm attr",  hasattr(disp, "_master_arm"))
        r.check("11 stations in loadout", len(disp._stations) == 11,
                f"got {len(disp._stations)}")
        disp.stop()
    except Exception as exc:
        r.check("StoresManagementDisplay instantiates", False, str(exc))


def test_sms_paint_safe(r: _Results) -> None:
    print("\n  ── SMS: paint with master arm SAFE ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
    disp = StoresManagementDisplay()
    disp._master_arm = "SAFE"
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds with master arm SAFE", ok)
    disp.stop()


def test_sms_paint_armed(r: _Results) -> None:
    print("\n  ── SMS: paint with master arm ARMED ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
    disp = StoresManagementDisplay()
    disp._master_arm = "ARMED"
    # Arm a few stations
    for sta in disp._stations[:3]:
        if sta.store:
            sta.store.state = "ARMED"
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds with master arm ARMED", ok)
    disp.stop()


def test_sms_total_weight(r: _Results) -> None:
    print("\n  ── SMS: total weight calculation ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
    disp = StoresManagementDisplay()
    weight = disp._total_weight_kg()
    r.check("total weight is positive", weight > 0, f"got {weight:.0f} kg")
    # Expend all stores
    for sta in disp._stations:
        if sta.store:
            sta.store.state = "EXPENDED"
    weight_after = disp._total_weight_kg()
    r.check("total weight is 0 after all expended",
            weight_after == 0.0, f"got {weight_after}")
    disp.stop()


def test_sms_armed_count(r: _Results) -> None:
    print("\n  ── SMS: armed station count ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
    # Fresh instance so state from previous tests does not leak
    disp = StoresManagementDisplay()
    # Reset all to SAFE first
    for sta in disp._stations:
        if sta.store:
            sta.store.state = "SAFE"
    # Arm exactly 2 stations
    armed = 0
    for sta in disp._stations:
        if sta.store and armed < 2:
            sta.store.state = "ARMED"
            armed += 1
    r.check("armed_count() returns 2", disp._armed_count() == 2,
            f"got {disp._armed_count()}")
    disp.stop()


def test_sms_signature_strip_paint(r: _Results) -> None:
    print("\n  ── SMS: stealth mode affects paint ──")
    _qt_app()
    from FMOFP.Interfaces.userInterface.displays.sms import StoresManagementDisplay
    disp = StoresManagementDisplay()
    disp._stealth = "ON"
    disp._rcs     = 0.001
    disp._ir_sig  = 0.05
    disp._ecm     = "ACTIVE"
    ok = _paint_widget(disp)
    r.check("paint_display() succeeds in stealth mode", ok)
    disp.stop()


# ──────────────────────────────────────────── runner ─────────────────────

def run_all() -> bool:
    print("=" * 60)
    print(" Display Headless Smoke Test Suite")
    print("=" * 60)

    r = _Results()

    tests = [
        # EICAS
        test_eicas_instantiation,
        test_eicas_paint_normal,
        test_eicas_paint_warnings,
        test_eicas_compute_alerts,
        # TSD
        test_tsd_instantiation,
        test_tsd_paint_normal,
        test_tsd_paint_with_threats,
        test_tsd_simulate_threats_fallback,
        test_tsd_paint_combat_mode,
        # SMS
        test_sms_instantiation,
        test_sms_paint_safe,
        test_sms_paint_armed,
        test_sms_total_weight,
        test_sms_armed_count,
        test_sms_signature_strip_paint,
    ]

    for test_fn in tests:
        try:
            test_fn(r)
        except Exception as exc:
            r.failed += 1
            print(f"  ✗  {test_fn.__name__} raised: {exc}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    passed = r.summary()
    print("=" * 60)
    return passed


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
