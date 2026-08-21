"""
Inertial Navigation System (INS)

Strap-down INS simulation:
  - Integrates simulated accelerometer + gyro outputs
  - Accumulates position drift over time (realistic INS behaviour)
  - Provides lat/lon/alt/heading/pitch/roll to NavDataFusion
  - Singleton factory: get_ins()
"""

import math
import time
import threading
import random
from typing import Dict, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_ins_instance = None

# Earth radius (m)
_EARTH_RADIUS_M = 6_371_000.0


class InertialNavigationSystem:
    """
    Simplified strap-down INS.

    Maintains attitude quaternion approximated as Euler angles (pitch, roll,
    heading) and integrates accelerometer readings to estimate position.
    Drift grows at ~0.5 nm/hr (typical ring-laser gyro quality).
    """

    DRIFT_RATE_M_PER_S = 0.000257    # 0.5 nm/hr in m/s

    def __init__(self,
                 init_lat: float = 35.4147,
                 init_lon: float = -97.3866,
                 init_alt_ft: float = 1290.6):
        self._lock = threading.Lock()

        # Position state (degrees / feet)
        self._lat    = init_lat
        self._lon    = init_lon
        self._alt_ft = init_alt_ft

        # Attitude state (degrees)
        self._heading = 0.0
        self._pitch   = 0.0
        self._roll    = 0.0

        # Velocity estimate (m/s)
        self._vn = 0.0   # north
        self._ve = 0.0   # east
        self._vd = 0.0   # down (positive = descending)

        # Accumulated drift error (m)
        self._drift_n = 0.0
        self._drift_e = 0.0

        self._last_update = time.time()
        self._healthy = True

    # ------------------------------------------------------------------ internal

    def _simulate_imu(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Return simulated (accel_x,y,z m/s², gyro_x,y,z deg/s)."""
        accel = (
            random.gauss(0.0, 0.02),
            random.gauss(9.81, 0.01),
            random.gauss(0.0, 0.02),
        )
        gyro = (
            random.gauss(0.0, 0.01),
            random.gauss(0.0, 0.01),
            random.gauss(0.0, 0.005),
        )
        return accel, gyro

    def update(self, dt: float) -> None:
        """Propagate INS state by dt seconds."""
        accel, gyro = self._simulate_imu()

        with self._lock:
            # Integrate attitude
            self._pitch   = max(-45, min(45, self._pitch   + gyro[0] * dt))
            self._roll    = max(-60, min(60, self._roll    + gyro[1] * dt))
            self._heading = (self._heading + gyro[2] * dt) % 360

            # Dead-reckoning position update
            self._vn += accel[0] * dt * 0.1
            self._ve += accel[2] * dt * 0.1
            self._vd += (accel[1] - 9.81) * dt * 0.05

            # Clamp velocity drift
            self._vn = max(-300, min(300, self._vn))
            self._ve = max(-300, min(300, self._ve))
            self._vd = max(-50,  min(50,  self._vd))

            # Update position via velocity
            dlat = (self._vn * dt) / _EARTH_RADIUS_M
            dlon = (self._ve * dt) / (_EARTH_RADIUS_M * math.cos(math.radians(self._lat)) + 1e-9)
            self._lat    += math.degrees(dlat)
            self._lon    += math.degrees(dlon)
            self._alt_ft -= self._vd * dt * 3.28084   # m → ft

            # Accumulate drift
            drift_step    = self.DRIFT_RATE_M_PER_S * dt
            self._drift_n += random.gauss(0, drift_step)
            self._drift_e += random.gauss(0, drift_step)

    # ------------------------------------------------------------------ public API

    def get_position(self) -> Dict[str, float]:
        """Return current INS position estimate (with drift applied)."""
        with self._lock:
            dlat = math.degrees(self._drift_n / _EARTH_RADIUS_M)
            dlon = math.degrees(self._drift_e / (
                _EARTH_RADIUS_M * math.cos(math.radians(self._lat)) + 1e-9))
            return {
                'lat':     self._lat + dlat,
                'lon':     self._lon + dlon,
                'alt_ft':  self._alt_ft,
                'heading': self._heading,
                'pitch':   self._pitch,
                'roll':    self._roll,
                'vn_ms':   self._vn,
                've_ms':   self._ve,
            }

    def correct(self, lat: float, lon: float, alt_ft: float) -> None:
        """Apply an external position correction (from GPS/Kalman)."""
        with self._lock:
            self._lat    = lat
            self._lon    = lon
            self._alt_ft = alt_ft
            # Reset drift after correction
            self._drift_n = 0.0
            self._drift_e = 0.0

    def is_healthy(self) -> bool:
        return self._healthy

    def get_status(self) -> Dict:
        pos = self.get_position()
        return {'healthy': self._healthy, **pos}


def get_ins() -> InertialNavigationSystem:
    global _ins_instance
    if _ins_instance is None:
        _ins_instance = InertialNavigationSystem()
    return _ins_instance
