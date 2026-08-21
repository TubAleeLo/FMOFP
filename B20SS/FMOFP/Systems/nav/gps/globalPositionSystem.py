"""
Global Position System (GPS)

Simulates a GPS receiver with:
  - Constellation of 12 satellites in realistic orbital geometry
  - Pseudorange calculation with clock bias and noise
  - Weighted least-squares position fix (ECEF → WGS-84)
  - Automatic satellite update loop running on its own daemon thread
  - Thread-safe position output consumed by NavDataFusion

The thread is started by flightManagementSystem.start() (not here in
__main__) as documented in the user manual and the comment that was
already present in the original file.
"""

import math
import threading
import time
from collections import deque
from typing import Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# WGS-84 constants
# ---------------------------------------------------------------------------
_WGS84_A   = 6_378_137.0          # semi-major axis (m)
_WGS84_B   = 6_356_752.314_245    # semi-minor axis (m)
_WGS84_E2  = 1 - (_WGS84_B / _WGS84_A) ** 2   # first eccentricity squared
_SPEED_OF_LIGHT = 299_792_458.0   # m/s

# ---------------------------------------------------------------------------
# Satellite
# ---------------------------------------------------------------------------

class Satellite:
    """A single GPS satellite with ECEF position and clock bias."""

    def __init__(self, sat_id: int,
                 position: Tuple[float, float, float],
                 clock_bias: float):
        self.id         = sat_id
        self.position   = position        # ECEF (x, y, z) metres
        self.clock_bias = clock_bias      # seconds


def _build_constellation() -> list:
    """
    Return 12 GPS satellites in 3 orbital planes (inclination 55°),
    planes separated by 120° RAAN, 4 slots per plane spaced 90° apart.
    Altitude: 20 200 km (orbit radius ≈ 26 560 km from Earth centre).

    The original flat-ring layout caused degenerate geometry (identical
    H-matrix rows) so the WLS solver was singular.  The correct approach
    uses a full 3-D rotation: perifocal → inclined → ECI.
    """
    ORBIT_RADIUS = 26_560_000.0         # metres
    INCLINATION  = math.radians(55.0)   # GPS constellation inclination
    sats = []
    sat_id = 1
    for plane in range(3):
        raan = math.radians(plane * 120)
        for slot in range(4):
            u = math.radians(slot * 90)    # argument of latitude
            # Position in orbital plane (perifocal)
            x_p =  ORBIT_RADIUS * math.cos(u)
            y_p =  ORBIT_RADIUS * math.sin(u)
            # Incline: rotate around x-axis by INCLINATION
            x_i = x_p
            y_i = y_p * math.cos(INCLINATION)
            z_i = y_p * math.sin(INCLINATION)
            # Apply RAAN: rotate around z-axis
            x = x_i * math.cos(raan) - y_i * math.sin(raan)
            y = x_i * math.sin(raan) + y_i * math.cos(raan)
            z = z_i
            clock_bias = (sat_id * 1.3e-9) % 1e-6
            sats.append(Satellite(sat_id, (x, y, z), clock_bias))
            sat_id += 1
    return sats


# ---------------------------------------------------------------------------
# GPS Receiver — pseudorange + WLS position fix
# ---------------------------------------------------------------------------

class GPSReceiver:
    """
    GPS receiver that:
      - Holds the satellite constellation
      - Computes noisy pseudoranges
      - Solves a weighted least-squares position fix each epoch
      - Converts ECEF → WGS-84 geodetic coordinates
    """

    def __init__(self):
        self._position_ecef: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._clock_bias: float = 0.0
        self._last_known_ecef: Optional[Tuple[float, float, float]] = None
        self._position_wgs84: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._lock = threading.Lock()
        # Simulated true position (ECEF) — updated as aircraft moves
        self._true_position_ecef: Tuple[float, float, float] = (
            # lat=0, lon=0, alt=30 000 ft ≈ 9 144 m above WGS-84 ellipsoid
            _WGS84_A + 9_144.0, 0.0, 0.0
        )
        self._measurement_noise_m = 3.0    # 1-sigma pseudorange noise (m)

    # ── public ──────────────────────────────────────────────────────────────

    def update_true_position(self, lat_deg: float, lon_deg: float,
                             alt_ft: float) -> None:
        """Accept a dead-reckoning position (for simulation purposes)."""
        alt_m = alt_ft * 0.3048
        lat   = math.radians(lat_deg)
        lon   = math.radians(lon_deg)
        N = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat) ** 2)
        x = (N + alt_m) * math.cos(lat) * math.cos(lon)
        y = (N + alt_m) * math.cos(lat) * math.sin(lon)
        z = (N * (1 - _WGS84_E2) + alt_m) * math.sin(lat)
        with self._lock:
            self._true_position_ecef = (x, y, z)

    def compute_fix(self, satellites: list) -> bool:
        """
        Compute a position fix from the visible satellite constellation.

        Uses iterative weighted least-squares (4+ satellites required).
        Returns True if a valid fix was obtained.
        """
        visible = [s for s in satellites if self._is_visible(s)]
        if len(visible) < 4:
            logger.debug(f"[GPS] Only {len(visible)} visible satellites — "
                         "using last known position")
            return False

        try:
            fix_ecef, clock_bias = self._wls_solve(visible)
            with self._lock:
                self._position_ecef   = fix_ecef
                self._clock_bias      = clock_bias
                self._last_known_ecef = fix_ecef
                self._position_wgs84  = self._ecef_to_wgs84(*fix_ecef)
            return True
        except Exception as exc:
            logger.warning(f"[GPS] WLS solver failed: {exc}")
            return False

    def get_position_wgs84(self) -> Tuple[float, float, float]:
        """Return (latitude_deg, longitude_deg, altitude_ft)."""
        with self._lock:
            return self._position_wgs84

    def get_position_ecef(self) -> Tuple[float, float, float]:
        with self._lock:
            return self._position_ecef

    # ── private ─────────────────────────────────────────────────────────────

    def _is_visible(self, sat: Satellite) -> bool:
        """Satellite is visible when elevation angle above horizon ≥ 5°."""
        rx, ry, rz = self._true_position_ecef
        sx, sy, sz = sat.position
        # Vector from receiver to satellite
        dx, dy, dz = sx - rx, sy - ry, sz - rz
        # Receiver unit normal (pointing away from Earth centre)
        r_mag = math.sqrt(rx**2 + ry**2 + rz**2)
        if r_mag == 0:
            return True
        nx, ny, nz = rx / r_mag, ry / r_mag, rz / r_mag
        d_mag = math.sqrt(dx**2 + dy**2 + dz**2)
        if d_mag == 0:
            return False
        cos_el = (dx * nx + dy * ny + dz * nz) / d_mag
        elevation_deg = math.degrees(math.asin(max(-1.0, min(1.0, cos_el))))
        return elevation_deg >= 5.0

    def _pseudorange(self, sat: Satellite) -> float:
        """Compute noisy pseudorange to a satellite."""
        import random
        rx, ry, rz = self._true_position_ecef
        sx, sy, sz = sat.position
        geometric = math.sqrt((sx - rx)**2 + (sy - ry)**2 + (sz - rz)**2)
        noise = random.gauss(0.0, self._measurement_noise_m)
        return (geometric
                + _SPEED_OF_LIGHT * (self._clock_bias - sat.clock_bias)
                + noise)

    def _wls_solve(self, sats: list,
                   max_iter: int = 8,
                   tol: float = 0.01) -> Tuple[Tuple[float, float, float], float]:
        """
        Iterative weighted least-squares position fix.

        State vector: [dx, dy, dz, d_clock_bias]
        Weights: elevation-angle dependent (sin²(el)) — downweights
        low-elevation satellites that suffer more multipath.
        """
        # Initialise with last known or Earth centre
        if self._last_known_ecef:
            x, y, z = self._last_known_ecef
        else:
            x, y, z = self._true_position_ecef  # bootstrap from sim truth
        cb = self._clock_bias * _SPEED_OF_LIGHT   # receiver clock bias in metres

        for _ in range(max_iter):
            H_rows, residuals, weights = [], [], []
            for sat in sats:
                sx, sy, sz = sat.position
                rng_est = math.sqrt((sx - x)**2 + (sy - y)**2 + (sz - z)**2)
                if rng_est == 0:
                    continue
                rng_obs = self._pseudorange(sat)
                residuals.append(rng_obs - rng_est - cb
                                 + _SPEED_OF_LIGHT * sat.clock_bias)
                # Partial derivatives (unit vector + clock column)
                H_rows.append([-(sx - x) / rng_est,
                                -(sy - y) / rng_est,
                                -(sz - z) / rng_est,
                                1.0])
                # Elevation-dependent weight
                r_mag = math.sqrt(x**2 + y**2 + z**2) or 1.0
                nx, ny, nz = x / r_mag, y / r_mag, z / r_mag
                d_mag = math.sqrt((sx-x)**2+(sy-y)**2+(sz-z)**2) or 1.0
                cos_el = ((sx-x)*nx + (sy-y)*ny + (sz-z)*nz) / d_mag
                el = math.asin(max(-1.0, min(1.0, cos_el)))
                weights.append(math.sin(el) ** 2 + 0.01)   # floor at 0.01

            n = len(H_rows)
            if n < 4:
                raise ValueError("Insufficient visible satellites in solver")

            # Build matrices manually (avoid numpy dependency)
            # Normal equations: (H^T W H) dx = H^T W r
            HtWH = [[0.0]*4 for _ in range(4)]
            HtWr = [0.0]*4
            for i in range(n):
                w = weights[i]
                h = H_rows[i]
                r = residuals[i]
                for row in range(4):
                    HtWr[row] += w * h[row] * r
                    for col in range(4):
                        HtWH[row][col] += w * h[row] * h[col]

            dx = _solve_4x4(HtWH, HtWr)
            x  += dx[0]
            y  += dx[1]
            z  += dx[2]
            cb += dx[3]

            if math.sqrt(dx[0]**2 + dx[1]**2 + dx[2]**2) < tol:
                break

        return (x, y, z), cb / _SPEED_OF_LIGHT

    @staticmethod
    def _ecef_to_wgs84(x: float, y: float,
                        z: float) -> Tuple[float, float, float]:
        """
        Convert ECEF (x, y, z) metres to WGS-84 geodetic
        (latitude_deg, longitude_deg, altitude_ft).

        Uses Bowring's iterative method.
        """
        lon = math.atan2(y, x)
        p   = math.sqrt(x**2 + y**2)
        lat = math.atan2(z, p * (1 - _WGS84_E2))   # initial estimate

        for _ in range(10):
            sin_lat = math.sin(lat)
            N   = _WGS84_A / math.sqrt(1 - _WGS84_E2 * sin_lat**2)
            lat = math.atan2(z + _WGS84_E2 * N * sin_lat, p)

        sin_lat = math.sin(lat)
        cos_lat = math.cos(lat)
        N_final = _WGS84_A / math.sqrt(1 - _WGS84_E2 * sin_lat**2)

        if abs(cos_lat) > 1e-10:
            alt_m = p / cos_lat - N_final
        else:
            alt_m = abs(z) / abs(sin_lat) - N_final * (1 - _WGS84_E2)

        return (math.degrees(lat), math.degrees(lon), alt_m / 0.3048)


# ---------------------------------------------------------------------------
# 4×4 linear solver (Gaussian elimination with partial pivoting)
# ---------------------------------------------------------------------------

def _solve_4x4(A: list, b: list) -> list:
    """Solve A·x = b for a 4×4 system. Modifies A and b in-place."""
    n = 4
    # Augment
    M = [A[r][:] + [b[r]] for r in range(n)]
    for col in range(n):
        # Partial pivot
        max_row = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[max_row] = M[max_row], M[col]
        pivot = M[col][col]
        if abs(pivot) < 1e-14:
            raise ValueError("Singular matrix in GPS solver")
        for row in range(col + 1, n):
            factor = M[row][col] / pivot
            for c in range(col, n + 1):
                M[row][c] -= factor * M[col][c]
    # Back substitution
    x = [0.0] * n
    for row in range(n - 1, -1, -1):
        x[row] = M[row][n]
        for c in range(row + 1, n):
            x[row] -= M[row][c] * x[c]
        x[row] /= M[row][row]
    return x


# ---------------------------------------------------------------------------
# GPS System — public interface used by FMS
# ---------------------------------------------------------------------------

class GPSSystem:
    """
    GPS system that runs on a daemon thread managed by the FMS.

    Lifecycle
    ---------
    Called from flightManagementSystem.start():
        gps_system.run()   # call in a thread (or call start_thread())

    Called from flightManagementSystem.stop():
        gps_system.stop()
    """

    UPDATE_INTERVAL_S = 1.0          # one position fix per second

    def __init__(self):
        self.receiver   = GPSReceiver()
        self.satellites = _build_constellation()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._fix_valid = False

    # ── thread management ───────────────────────────────────────────────────

    def start_thread(self) -> None:
        """Start the GPS update loop on a daemon thread (called by FMS)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self.run,
            name="GPS-update",
            daemon=True
        )
        self._thread.start()
        logger.info("[GPS] Update thread started")

    def stop(self) -> None:
        """Signal the update loop to exit and wait for the thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                logger.warning("[GPS] Thread did not stop cleanly")
            self._thread = None
        logger.info("[GPS] Stopped")

    def run(self) -> None:
        """
        Main GPS update loop.

        On every epoch:
          1. Propagate satellite positions (simplified: constellation is static)
          2. Compute a WLS position fix
          3. Store result for NavDataFusion to read
        """
        logger.info("[GPS] Update loop running")
        while not self._stop_event.is_set():
            try:
                ok = self.receiver.compute_fix(self.satellites)
                with self._lock:
                    self._fix_valid = ok
                if ok:
                    lat, lon, alt = self.receiver.get_position_wgs84()
                    logger.debug(f"[GPS] Fix: lat={lat:.4f}° lon={lon:.4f}° "
                                 f"alt={alt:.0f}ft")
            except Exception as exc:
                logger.error(f"[GPS] Epoch error: {exc}")
            self._stop_event.wait(self.UPDATE_INTERVAL_S)
        logger.info("[GPS] Update loop exited")

    # ── data interface ──────────────────────────────────────────────────────

    def update_true_position(self, lat_deg: float, lon_deg: float,
                             alt_ft: float) -> None:
        """
        Feed the simulation truth position so satellites can compute
        realistic pseudoranges.  Called each FMS update cycle.
        """
        self.receiver.update_true_position(lat_deg, lon_deg, alt_ft)

    def get_position_wgs84(self) -> Optional[Tuple[float, float, float]]:
        """
        Return the latest GPS fix as (lat_deg, lon_deg, alt_ft) or None
        if no valid fix is available yet.
        """
        with self._lock:
            if not self._fix_valid:
                return None
        return self.receiver.get_position_wgs84()

    def is_fix_valid(self) -> bool:
        with self._lock:
            return self._fix_valid

    # ── kept for backward compatibility ────────────────────────────────────

    def add_satellite(self, satellite: Satellite) -> None:
        self.satellites.append(satellite)

    def get_current_position(self) -> Tuple[float, float, float]:
        return self.receiver.get_position_ecef()
