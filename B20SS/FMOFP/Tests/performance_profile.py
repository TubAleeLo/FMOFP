#!/usr/bin/env python3
"""
FMOFP Performance Profiler
===========================
Measures render times for each display at target refresh rates.

Targets (from PLANNING.md / architecture spec):
  PFD              60 Hz   <40% CPU   <16.7 ms per frame
  MFD              60 Hz   <40% CPU   <16.7 ms per frame
  EICAS            10 Hz   <15% CPU   <100 ms per frame
  TSD              20 Hz   <30% CPU   <50  ms per frame
  WeatherRadar     20 Hz   <40% CPU   <50  ms per frame
  HolographicPFD   60 Hz   <40% CPU   <16.7 ms per frame
  HolographicMFD   10 Hz   <40% CPU   <100 ms per frame

Usage:
  cd B20SS
  python FMOFP/Tests/performance_profile.py
  python FMOFP/Tests/performance_profile.py --frames 500
  python FMOFP/Tests/performance_profile.py --display eicas
  python FMOFP/Tests/performance_profile.py --cprofile --display weather_radar
"""

import argparse
import cProfile
import io
import os
import pstats
import statistics
import sys
import time

# Qt must run offscreen; set before any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure both B20SS/ and B20SS/FMOFP/ are on the path
_HERE = os.path.dirname(os.path.abspath(__file__))
_B20SS = os.path.abspath(os.path.join(_HERE, "..", ".."))
_FMOFP = os.path.join(_B20SS, "FMOFP")
for _p in (_B20SS, _FMOFP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QPixmap

_APP = QApplication.instance() or QApplication(sys.argv)


# ── Targets ───────────────────────────────────────────────────────────────────

TARGETS = {
    # name: (target_hz, budget_ms, cpu_warn_pct)
    "pfd":           (60,  16.7, 40),
    "mfd":           (60,  16.7, 40),
    "eicas":         (10, 100.0, 15),
    "tsd":           (20,  50.0, 30),
    "weather_radar": (20,  50.0, 40),
    "holo_pfd":      (60,  16.7, 40),
    "holo_mfd":      (10, 100.0, 40),
}


# ── Factories ─────────────────────────────────────────────────────────────────

def _make_pfd():
    from FMOFP.Interfaces.userInterface.displays.pfd import PrimaryFlightDisplay
    w = PrimaryFlightDisplay(); w.resize(800, 600); return w

def _make_mfd():
    from FMOFP.Interfaces.userInterface.displays.mfd import MultiFunctionDisplay
    w = MultiFunctionDisplay(); w.resize(800, 600); return w

def _make_eicas():
    from FMOFP.Interfaces.userInterface.displays.eicas import EICASDisplay
    w = EICASDisplay(); w.resize(800, 600); return w

def _make_tsd():
    from FMOFP.Interfaces.userInterface.displays.tsd import TacticalSituationDisplay
    w = TacticalSituationDisplay(); w.resize(800, 600); return w

def _make_weather_radar():
    from FMOFP.Interfaces.userInterface.displays.radar.weather_radar_display import WeatherRadarDisplay
    return WeatherRadarDisplay()

def _make_holo_pfd():
    from FMOFP.Interfaces.userInterface.displays.holographic_pfd import HolographicPFD
    w = HolographicPFD(); w.resize(800, 600); return w

def _make_holo_mfd():
    from FMOFP.Interfaces.userInterface.displays.holographic_mfd import HolographicMFD
    w = HolographicMFD(); w.resize(800, 600); return w

FACTORIES = {
    "pfd":           _make_pfd,
    "mfd":           _make_mfd,
    "eicas":         _make_eicas,
    "tsd":           _make_tsd,
    "weather_radar": _make_weather_radar,
    "holo_pfd":      _make_holo_pfd,
    "holo_mfd":      _make_holo_mfd,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paint_frame(widget, w=800, h=600):
    """Render one frame to an off-screen pixmap and return elapsed ms."""
    from PyQt6.QtCore import QRectF
    px = QPixmap(w, h)
    px.fill()
    p = QPainter(px)
    rect = QRectF(0, 0, w, h)
    t0 = time.perf_counter()
    try:
        if hasattr(widget, "paint_display"):
            widget.paint_display(p)
        elif hasattr(widget, "draw_radar_elements"):
            widget.draw_radar_elements(p, rect, {})
        else:
            raise AttributeError(f"{type(widget).__name__} has no paint_display or draw_radar_elements")
    finally:
        p.end()
    return (time.perf_counter() - t0) * 1000.0


def _warmup(widget, n=5):
    for _ in range(n):
        try:
            _paint_frame(widget)
        except Exception:
            pass


# ── cProfile helper ───────────────────────────────────────────────────────────

def _cprofile_display(name, n_frames=50):
    """Run n_frames under cProfile and print the top 20 hotspots."""
    try:
        widget = FACTORIES[name]()
    except Exception as e:
        print(f"  Could not instantiate {name}: {e}")
        return
    _warmup(widget)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(n_frames):
        try:
            _paint_frame(widget)
        except Exception:
            pass
    pr.disable()
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    ps.print_stats(20)
    print(f"\n  cProfile — {name.upper()} — top 20 cumulative ({n_frames} frames):")
    lines = buf.getvalue().splitlines()
    # Skip boilerplate header (first 5 lines), print the rest
    for line in lines[5:]:
        print(f"    {line}")


# ── Profiler ──────────────────────────────────────────────────────────────────

def profile_display(name, n_frames):
    target_hz, budget_ms, _ = TARGETS[name]
    print(f"\n{'─'*60}")
    print(f"  {name.upper()}  —  target {target_hz} Hz  ({budget_ms:.1f} ms budget)")
    print(f"{'─'*60}")

    try:
        widget = FACTORIES[name]()
    except Exception as e:
        print(f"  ✗  Could not instantiate {name}: {e}")
        return {"name": name, "error": str(e)}

    _warmup(widget)
    times_ms = []
    errors = 0

    for i in range(n_frames):
        try:
            times_ms.append(_paint_frame(widget))
        except Exception as exc:
            errors += 1
            if errors <= 3:
                print(f"  ✗  Frame {i} error: {exc}")

    if not times_ms:
        print("  ✗  No frames rendered successfully")
        return {"name": name, "error": "no frames rendered"}

    mean_ms   = statistics.mean(times_ms)
    median_ms = statistics.median(times_ms)
    p95_ms    = sorted(times_ms)[int(len(times_ms) * 0.95)]
    p99_ms    = sorted(times_ms)[int(len(times_ms) * 0.99)]
    max_ms    = max(times_ms)
    stdev_ms  = statistics.stdev(times_ms) if len(times_ms) > 1 else 0.0
    eff_hz    = 1000.0 / mean_ms if mean_ms > 0 else 0.0
    pct_over  = 100.0 * sum(1 for t in times_ms if t > budget_ms) / len(times_ms)
    passing   = mean_ms <= budget_ms

    sym = "✓" if passing else "✗"
    print(f"  Frames rendered   : {len(times_ms)} / {n_frames}  (errors: {errors})")
    print(f"  Mean              : {mean_ms:7.2f} ms   (budget {budget_ms:.1f} ms)  {sym}")
    print(f"  Median            : {median_ms:7.2f} ms")
    print(f"  P95               : {p95_ms:7.2f} ms")
    print(f"  P99               : {p99_ms:7.2f} ms")
    print(f"  Max               : {max_ms:7.2f} ms")
    print(f"  Std dev           : {stdev_ms:7.2f} ms")
    print(f"  Effective rate    : {eff_hz:7.1f} Hz   (target {target_hz} Hz)")
    print(f"  Frames over budget: {pct_over:.1f}%")

    if not passing:
        print(f"\n  ⚠  Mean is {mean_ms/budget_ms:.1f}× the {budget_ms:.1f} ms budget.")

    return {
        "name": name, "n_frames": len(times_ms), "errors": errors,
        "mean_ms": round(mean_ms, 3), "median_ms": round(median_ms, 3),
        "p95_ms": round(p95_ms, 3), "p99_ms": round(p99_ms, 3),
        "max_ms": round(max_ms, 3), "stdev_ms": round(stdev_ms, 3),
        "eff_hz": round(eff_hz, 1), "target_hz": target_hz,
        "budget_ms": budget_ms, "pct_over": round(pct_over, 1),
        "pass": passing,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FMOFP display performance profiler")
    parser.add_argument("--frames",         type=int, default=200)
    parser.add_argument("--display",        choices=list(FACTORIES.keys()))
    parser.add_argument("--json",           action="store_true")
    parser.add_argument("--cprofile",       action="store_true",
                        help="Run cProfile on each display after timing")
    parser.add_argument("--cprofile-frames", type=int, default=50,
                        dest="cprofile_frames")
    args = parser.parse_args()

    displays = [args.display] if args.display else list(TARGETS.keys())

    print("=" * 60)
    print("  FMOFP Performance Profiler")
    print(f"  Frames per display : {args.frames}")
    print(f"  Displays           : {', '.join(d.upper() for d in displays)}")
    print("=" * 60)

    results = []
    for name in displays:
        r = profile_display(name, args.frames)
        results.append(r)
        if args.cprofile and "error" not in r:
            _cprofile_display(name, args.cprofile_frames)

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Display':<14}  {'Mean ms':>8}  {'Budget ms':>10}  {'Eff Hz':>7}  {'%>budget':>8}  Status")
    print(f"  {'─'*14}  {'─'*8}  {'─'*10}  {'─'*7}  {'─'*8}  {'─'*6}")
    all_pass = True
    for r in results:
        if "error" in r:
            print(f"  {r['name'].upper():<14}  {'ERROR':>8}  {'':>10}  {'':>7}  {'':>8}  FAIL")
            all_pass = False
        else:
            sym = "PASS" if r["pass"] else "FAIL"
            if not r["pass"]:
                all_pass = False
            print(f"  {r['name'].upper():<14}  {r['mean_ms']:>8.2f}  "
                  f"{r['budget_ms']:>10.1f}  {r['eff_hz']:>7.1f}  "
                  f"{r['pct_over']:>7.1f}%  {sym}")

    print(f"\n  Overall: {'✓ ALL PASS' if all_pass else '✗ FAILURES DETECTED'}")
    print("=" * 60)

    if args.json:
        import json
        print(json.dumps(results, indent=2))

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
