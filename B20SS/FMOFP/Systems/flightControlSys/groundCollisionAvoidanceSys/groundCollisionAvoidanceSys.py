"""
Ground Collision Avoidance System (GCAS)

Monitors flight parameters and TFR terrain clearance to generate
crew alerts when the aircraft approaches unsafe conditions:

  PULLUP      — severe immediate pull-up required   (severity 1 = WARNING)
  SINK RATE   — excessive descent rate              (severity 1 = WARNING)
  TERRAIN     — terrain proximity from TFR          (severity 1 = WARNING)
  ALT LOW     — altitude below safe floor           (severity 2 = CAUTION)

Data sources
  - FMS  : altitude (ft), vertical speed (fpm)
  - TFR  : terrain_clearance (ft) via TFR processor

Singleton: get_gcas()

Alert dict schema (consumed by EICAS and MFD):
    {
        'severity':  1 (WARNING) | 2 (CAUTION),
        'code':      str,   e.g. "PULLUP"
        'message':   str,   human-readable crew message
        'ts':        float  unix timestamp
    }
"""

import threading
import time
from typing import Any, Dict, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ── thresholds ────────────────────────────────────────────────────────────────

_VS_PULLUP_FPM  = -4000   # fpm — immediate pull-up
_VS_SINK_FPM    = -2000   # fpm — sink rate caution
_ALT_TERRAIN_FT = 500     # ft  — terrain proximity from TFR clearance
_ALT_LOW_FT     = 200     # ft  — low-altitude floor
_POLL_HZ        = 10


# ── GCAS ─────────────────────────────────────────────────────────────────────

class GCAS:
    """
    Ground Collision Avoidance System singleton.

    Polls FMS and TFR data at 10 Hz and maintains an active alert list.
    The list is rebuilt every cycle so stale alerts automatically clear.
    """

    def __init__(self):
        self._lock     = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._alerts: List[Dict[str, Any]] = []
        self._fms      = None   # lazy

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # newer subsystem singletons -- see PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py). Reuses
        # the existing data lock; start() never touches the data it
        # guards, so no reentrancy risk.
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_evt.clear()
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="GCAS"
            )
            self._thread.start()
            logger.info("[GCAS] Started at %d Hz", _POLL_HZ)

    def stop(self):
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[GCAS] Stopped")

    # ── public API ────────────────────────────────────────────────────────────

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Return current active GCAS alerts (thread-safe copy)."""
        with self._lock:
            return list(self._alerts)

    def get_data(self) -> Dict[str, Any]:
        """Extended status dict for EICAS avionics section."""
        alerts = self.get_alerts()
        return {
            "active_alerts": alerts,
            "alert_count":   len(alerts),
            "status": (
                "WARNING" if any(a["severity"] == 1 for a in alerts)
                else "CAUTION" if alerts
                else "ARMED"
            ),
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _lazy_fms(self):
        if self._fms is None:
            try:
                from FMOFP.Systems.flightManagementSys.flightManagementSystem import (
                    get_flightManagementSystem,
                )
                self._fms = get_flightManagementSystem()
            except Exception as exc:
                logger.debug(f"[GCAS] FMS not ready: {exc}")

    def _get_flight_state(self) -> Dict[str, float]:
        """Return {altitude_ft, vertical_speed_fpm} from FMS; safe defaults on failure."""
        self._lazy_fms()
        try:
            if self._fms:
                fd  = self._fms.get_flight_data()
                nav = fd.get("navigation", {})
                vel = fd.get("velocity",   {})
                return {
                    "altitude_ft":        float(nav.get("altitude",       30_000)),
                    "vertical_speed_fpm": float(vel.get("vertical_speed",      0)),
                }
        except Exception as exc:
            logger.debug(f"[GCAS] FMS read error: {exc}")
        return {"altitude_ft": 30_000.0, "vertical_speed_fpm": 0.0}

    def _get_tfr_clearance(self) -> Optional[float]:
        """Return TFR terrain clearance in feet, or None if unavailable."""
        try:
            from FMOFP.Systems.radarManagement.terrainFollowing.tfr_processor import (
                get_tfr_processor,
            )
            proc = get_tfr_processor()
            data = proc.get_data() if hasattr(proc, "get_data") else {}
            val = data.get("terrain_clearance_ft", data.get("clearance_ft"))
            return float(val) if val is not None else None
        except Exception:
            return None

    def _evaluate(
        self,
        state: Dict[str, float],
        tfr_clearance: Optional[float],
    ) -> List[Dict[str, Any]]:
        """Build the alert list from current sensor readings."""
        alerts = []
        now = time.time()
        alt = state["altitude_ft"]
        vs  = state["vertical_speed_fpm"]

        # PULLUP — extreme descent rate at low altitude
        if vs <= _VS_PULLUP_FPM and alt < 2_000:
            alerts.append({
                "severity": 1,
                "code":     "PULLUP",
                "message":  f"PULL UP  VS {vs:.0f} fpm",
                "ts":       now,
            })
        # SINK RATE — significant descent
        elif vs <= _VS_SINK_FPM:
            alerts.append({
                "severity": 1,
                "code":     "SINK RATE",
                "message":  f"SINK RATE  {vs:.0f} fpm",
                "ts":       now,
            })

        # TERRAIN — TFR clearance too low
        if tfr_clearance is not None and tfr_clearance < _ALT_TERRAIN_FT:
            alerts.append({
                "severity": 1,
                "code":     "TERRAIN",
                "message":  f"TERRAIN  {tfr_clearance:.0f} ft clearance",
                "ts":       now,
            })

        # ALT LOW — altitude below safe floor (non-TFR)
        if alt < _ALT_LOW_FT and not any(a["code"] == "TERRAIN" for a in alerts):
            alerts.append({
                "severity": 2,
                "code":     "ALT LOW",
                "message":  f"ALT LOW  {alt:.0f} ft",
                "ts":       now,
            })

        return alerts

    def _poll_loop(self):
        interval = 1.0 / _POLL_HZ
        while not self._stop_evt.is_set():
            try:
                state         = self._get_flight_state()
                tfr_clearance = self._get_tfr_clearance()
                new_alerts    = self._evaluate(state, tfr_clearance)
                with self._lock:
                    self._alerts = new_alerts
                if new_alerts:
                    codes = ", ".join(a["code"] for a in new_alerts)
                    logger.debug(f"[GCAS] Active: {codes}")
            except Exception as exc:
                logger.error(f"[GCAS] Poll error: {exc}")
            self._stop_evt.wait(interval)


# ── singleton accessor ────────────────────────────────────────────────────────

_gcas: Optional[GCAS] = None
_gcas_lock = threading.Lock()


def get_gcas() -> GCAS:
    global _gcas
    with _gcas_lock:
        if _gcas is None:
            _gcas = GCAS()
    return _gcas
