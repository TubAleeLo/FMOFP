"""
Navigation Service

Owns GPS, INS, and NavDataFusion update loops:
  - GPS generates position fixes at ~1 Hz and feeds NavDataFusion
  - INS propagates attitude/position at 10 Hz and applies GPS corrections
  - Fused position is written back into the FMS navigation dict
  - Singleton: get_nav_service()
"""

import threading
import time
from typing import Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_nav_service = None


class NavService:
    def __init__(self):
        self._running  = threading.Event()
        self._thread   = None
        self._last_gps = 0.0
        self._start_lock = threading.Lock()

        # Lazy-import to avoid circular dependencies at module load
        self._gps     = None
        self._ins     = None
        self._fusion  = None
        self._fms     = None

    def _lazy_init(self):
        if self._gps is None:
            try:
                # Use the GPSSystem already owned and started by FMS.
                # Creating a second GPS instance would produce different positions.
                from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
                _fms_temp = get_flightManagementSystem()
                self._gps = _fms_temp.gps_system   # GPSSystem instance
                logger.info("[NAV] GPS attached via FMS gps_system")
            except Exception as e:
                logger.warning(f"[NAV] GPS unavailable: {e}")

        if self._ins is None:
            try:
                from FMOFP.Systems.nav.ins.inertialNavigationSystem import get_ins
                self._ins = get_ins()
                logger.info("[NAV] INS attached")
            except Exception as e:
                logger.warning(f"[NAV] INS unavailable: {e}")

        if self._fusion is None:
            try:
                from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
                self._fms = get_flightManagementSystem()
                self._fusion = self._fms.nav_fusion
                logger.info("[NAV] NavDataFusion attached via FMS")
            except Exception as e:
                logger.warning(f"[NAV] NavDataFusion unavailable: {e}")

    def _tick(self, dt: float):
        now = time.time()

        # GPS fix at ~1 Hz
        if self._gps and self._fusion and (now - self._last_gps >= 1.0):
            try:
                # get_position_wgs84() returns (lat_deg, lon_deg, alt_ft) or None
                fix = self._gps.get_position_wgs84()
                if fix:
                    lat, lon, alt_ft = fix   # already in feet
                    self._fusion.update_gps(lat, lon, alt_ft)
                    # Correct INS with GPS fix
                    if self._ins:
                        self._ins.correct(lat, lon, alt_ft)
                    self._last_gps = now
            except Exception as e:
                logger.debug(f"[NAV] GPS tick error: {e}")

        # INS propagation at every tick
        if self._ins:
            try:
                self._ins.update(dt)
            except Exception as e:
                logger.debug(f"[NAV] INS tick error: {e}")

        # Write fused position back into FMS
        if self._fusion and self._fms:
            try:
                lat, lon, alt_ft, heading = self._fusion.get_fused_position()
                ins_pos = self._ins.get_position() if self._ins else {}
                self._fms.update_navigation(
                    latitude=lat,
                    longitude=lon,
                    altitude=alt_ft,
                    heading=heading,
                    pitch=ins_pos.get('pitch', 0.0),
                    roll=ins_pos.get('roll', 0.0),
                )
            except Exception as e:
                logger.debug(f"[NAV] FMS navigation update error: {e}")

    def _update_loop(self):
        logger.info("[NAV] Navigation service loop started")
        self._lazy_init()
        last = time.time()
        while not self._running.is_set():
            now = time.time()
            dt  = now - last
            last = now
            try:
                self._tick(dt)
            except Exception as e:
                logger.error(f"[NAV] Loop error: {e}")
            time.sleep(0.1)   # 10 Hz INS update

    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # newer subsystem singletons -- see PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py).
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="NAV_Service")
            self._thread.start()
            logger.info("[NAV] Navigation service started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[NAV] Navigation service stopped")

    def get_status(self):
        return {
            'running':      self._thread is not None and self._thread.is_alive(),
            'gps_available': self._gps is not None and self._gps.is_fix_valid(),
            'ins_available': self._ins is not None,
            'fusion_active': self._fusion is not None,
        }


def get_nav_service() -> NavService:
    global _nav_service
    if _nav_service is None:
        _nav_service = NavService()
    return _nav_service
