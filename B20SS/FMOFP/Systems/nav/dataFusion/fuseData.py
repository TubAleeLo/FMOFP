"""
Navigation Data Fusion

Blends GPS position fixes with FMS dead-reckoning (DR) estimates using
a scalar Kalman filter — the simplest fusion approach that is still
statistically principled.

Architecture
------------
                  ┌───────────────┐
  GPS fix ──────► │               │
                  │  NavDataFusion │──► fused (lat, lon, alt, heading)
  FMS DR  ──────► │               │
                  └───────────────┘

The filter runs independently for each of the three position components
(latitude, longitude, altitude).  Heading is taken directly from the FMS
dead-reckoning because GPS does not provide heading.

Kalman Filter (per axis)
------------------------
  State    x   — estimated position (one axis)
  Predict  x_p = x + v·dt    (dead-reckoning step, v = axis rate)
           P_p = P + Q        (process noise accumulates between GPS fixes)
  Update   K   = P_p / (P_p + R)
           x   = x_p + K·(z - x_p)
           P   = (1 - K)·P_p

  Q — process noise variance: grows with time since last GPS fix
  R — GPS measurement noise variance (constant, ~9 m² ≈ 3 m 1-sigma)
"""

import math
import threading
import time
from typing import Dict, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Single-axis scalar Kalman filter
# ---------------------------------------------------------------------------

class _ScalarKalman:
    """One-dimensional constant-velocity Kalman filter."""

    def __init__(self, initial_value: float,
                 process_noise: float,
                 measurement_noise: float):
        self.x  = initial_value    # state estimate
        self.P  = 1.0              # error covariance
        self.Q  = process_noise    # process noise variance (per second)
        self.R  = measurement_noise

    def predict(self, dt: float, velocity: float = 0.0) -> None:
        """Dead-reckoning prediction step."""
        self.x += velocity * dt
        self.P += self.Q * dt      # uncertainty grows with time

    def update(self, measurement: float) -> None:
        """GPS measurement update step."""
        K     = self.P / (self.P + self.R)
        self.x = self.x + K * (measurement - self.x)
        self.P = (1.0 - K) * self.P


# ---------------------------------------------------------------------------
# NavDataFusion — public class used by FMS
# ---------------------------------------------------------------------------

class NavDataFusion:
    """
    Fuses GPS and FMS dead-reckoning into a single best-estimate position.

    Usage
    -----
    fusion = NavDataFusion()

    # Every FMS update cycle (20 Hz):
    fusion.predict(dt, lat_rate, lon_rate, alt_rate_fps)

    # When a GPS fix arrives (1 Hz):
    fusion.update_gps(lat_deg, lon_deg, alt_ft)

    # Read the fused estimate:
    lat, lon, alt, heading = fusion.get_fused_position()
    """

    # GPS measurement noise: ~5 m 1-sigma → variance in metres²
    # Converted to degrees²: 1° lat ≈ 111 000 m
    _GPS_R_LAT  = (5.0 / 111_000) ** 2    # degrees²
    _GPS_R_LON  = (5.0 / 111_000) ** 2    # degrees² (approximate)
    _GPS_R_ALT  = (10.0 / 0.3048) ** 2    # feet²  (10 m 1-sigma)

    # Process noise: expected DR error per second
    _Q_LAT  = (1.0 / 111_000) ** 2        # 1 m/s DR uncertainty
    _Q_LON  = (1.0 / 111_000) ** 2
    _Q_ALT  = (2.0 / 0.3048) ** 2         # 2 m/s altitude DR uncertainty

    def __init__(self):
        # Initial position: Lat 0, Lon 0, Alt 30 000 ft
        self._kf_lat = _ScalarKalman(0.0,    self._Q_LAT, self._GPS_R_LAT)
        self._kf_lon = _ScalarKalman(0.0,    self._Q_LON, self._GPS_R_LON)
        self._kf_alt = _ScalarKalman(30_000.0, self._Q_ALT, self._GPS_R_ALT)

        self._heading = 0.0            # degrees, straight from FMS DR
        self._last_gps_time: Optional[float] = None
        self._gps_fix_count = 0
        self._lock = threading.Lock()

    # ── Kalman prediction (called at FMS update rate, ~20 Hz) ──────────────

    def predict(self,
                dt: float,
                lat_rate_dps: float = 0.0,
                lon_rate_dps: float = 0.0,
                alt_rate_fps: float = 0.0,
                heading_deg: float  = 0.0) -> None:
        """
        Dead-reckoning prediction step.

        Args:
            dt              Time since last call (seconds).
            lat_rate_dps    Latitude rate (degrees/second).
            lon_rate_dps    Longitude rate (degrees/second).
            alt_rate_fps    Altitude rate (feet/second).
            heading_deg     Current heading from FMS DR (degrees).
        """
        with self._lock:
            self._kf_lat.predict(dt, lat_rate_dps)
            self._kf_lon.predict(dt, lon_rate_dps)
            self._kf_alt.predict(dt, alt_rate_fps)
            self._heading = heading_deg

    # ── GPS measurement update (called at GPS fix rate, ~1 Hz) ────────────

    def update_gps(self, lat_deg: float, lon_deg: float,
                   alt_ft: float) -> None:
        """
        GPS measurement update.

        Args:
            lat_deg   GPS latitude  (degrees WGS-84).
            lon_deg   GPS longitude (degrees WGS-84).
            alt_ft    GPS altitude  (feet above WGS-84 ellipsoid).
        """
        with self._lock:
            self._kf_lat.update(lat_deg)
            self._kf_lon.update(lon_deg)
            self._kf_alt.update(alt_ft)
            self._last_gps_time = time.time()
            self._gps_fix_count += 1
            logger.debug(
                f"[NAV_FUSION] GPS update #{self._gps_fix_count}: "
                f"lat={lat_deg:.5f}° lon={lon_deg:.5f}° alt={alt_ft:.0f}ft  "
                f"fused_alt={self._kf_alt.x:.0f}ft"
            )

    # ── Fused output ────────────────────────────────────────────────────────

    def get_fused_position(self) -> Tuple[float, float, float, float]:
        """
        Return (latitude_deg, longitude_deg, altitude_ft, heading_deg).

        These are the Kalman-fused best estimates and should be written
        into FMS navigation dict on every update cycle.
        """
        with self._lock:
            return (
                self._kf_lat.x,
                self._kf_lon.x,
                self._kf_alt.x,
                self._heading,
            )

    def get_gps_fix_count(self) -> int:
        """Number of GPS fixes incorporated so far."""
        with self._lock:
            return self._gps_fix_count

    def seconds_since_last_gps(self) -> Optional[float]:
        """Seconds elapsed since the most recent GPS fix, or None."""
        with self._lock:
            if self._last_gps_time is None:
                return None
            return time.time() - self._last_gps_time
