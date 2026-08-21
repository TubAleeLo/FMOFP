"""
Weather Radar Processor

Implements two capability modules that were planned but missing:

  WindShearProcessor  — detects wind shear hazards from Doppler velocity
                        gradients and predicts microburst divergence.

  TurbulenceProcessor — maps atmospheric turbulence from radar spectrum
                        width data and identifies eddy-current signatures.

Both processors are designed to operate on the reflectivity array already
produced by ReflectivitySimulator (shape: azimuth × elevation × range).
They are called from weather_radar._update_radar_state() in WINDSHEAR and
TURBULENCE modes, which previously contained only `pass`.

Output
------
WindShearProcessor.process()  → List[WindShearEvent]
TurbulenceProcessor.process() → List[TurbulenceCell]
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ─────────────────────────────────────────────────────── data structures ──

@dataclass
class WindShearEvent:
    """A detected wind-shear or microburst hazard."""
    event_id:       int
    position_nm:    Tuple[float, float]   # (azimuth°, range nm)
    shear_knots:    float                 # velocity gradient (knots per nm)
    divergence:     float                 # +ve = outflow (microburst), -ve = convergence
    is_microburst:  bool
    severity:       str                   # "LOW" | "MODERATE" | "SEVERE"
    altitude_ft:    float
    timestamp:      float = field(default_factory=time.time)

    @property
    def severity_level(self) -> int:
        return {"LOW": 1, "MODERATE": 2, "SEVERE": 3}.get(self.severity, 0)


@dataclass
class TurbulenceCell:
    """A region of significant atmospheric turbulence."""
    cell_id:        int
    position_nm:    Tuple[float, float]   # (azimuth°, range nm)
    intensity:      float                 # 0-1 normalised EDR proxy
    category:       str                   # "LIGHT" | "MODERATE" | "SEVERE" | "EXTREME"
    spectrum_width: float                 # m/s (raw diagnostic)
    altitude_ft:    float
    timestamp:      float = field(default_factory=time.time)


# ────────────────────────────────────────────── WindShearProcessor ─────────

class WindShearProcessor:
    """
    Detects wind-shear events from Doppler velocity gradient analysis.

    Algorithm (simplified operational model)
    -----------------------------------------
    1.  Extract the lowest-elevation Doppler velocity field from the
        reflectivity array (proxy: azimuthal gradient of reflectivity).
    2.  Compute the radial velocity divergence in each range-azimuth cell
        using finite differences.
    3.  Flag cells where |shear| > SHEAR_THRESHOLD or where outflow
        divergence is large enough to indicate a microburst.
    4.  Cluster adjacent flagged cells and report one event per cluster.

    Parameters
    ----------
    shear_threshold_kts : velocity gradient threshold for reporting (knots/nm)
    microburst_threshold : divergence threshold for microburst flag
    min_dbz             : minimum reflectivity to consider (avoids clear-air noise)
    """

    SHEAR_THRESHOLD_KTS = 15.0   # FAA microburst advisory threshold
    MICROBURST_THRESHOLD = 0.08  # normalised divergence
    MIN_DBZ = 20.0               # weak echo threshold
    _NM_PER_KM = 0.539957

    def __init__(self):
        self._next_id = 1
        self._last_result: List[WindShearEvent] = []
        self._last_run = 0.0

    def process(self, reflectivity: np.ndarray,
                elevation_angles: Tuple,
                scan_range_km: float = 100.0) -> List[WindShearEvent]:
        """
        Process a reflectivity volume and return detected wind-shear events.

        Args:
            reflectivity:    3D array (azimuth × elevation × range), dBZ
            elevation_angles: sequence of elevation angles (degrees)
            scan_range_km:   maximum instrumented range in km

        Returns:
            List of WindShearEvent objects, sorted by severity (highest first)
        """
        try:
            az, el, rng = reflectivity.shape
            if az == 0 or rng == 0:
                return []

            # Use lowest elevation tilt as Doppler proxy
            lowest = reflectivity[:, 0, :]                     # (az, rng)

            # Azimuthal gradient as velocity-shear proxy (dBZ/az_step → knots/nm)
            # Finite difference along azimuth axis
            grad_az = np.gradient(lowest, axis=0)              # dBZ per az-bin

            # Convert to knots/nm: empirical scaling (reflectivity gradient
            # correlates with wind shear in convective environments)
            shear_field = np.abs(grad_az) * 0.8               # rough scaling → kts/nm

            # Divergence: forward minus backward along range axis
            grad_rng = np.gradient(lowest, axis=1)
            divergence = grad_rng / 20.0                      # normalised

            # Range and azimuth bin widths
            range_step_nm = (scan_range_km * self._NM_PER_KM) / max(rng - 1, 1)
            az_step_deg   = 360.0 / max(az, 1)

            events: List[WindShearEvent] = []
            reported_cells: set = set()

            for az_i in range(az):
                for rng_j in range(rng):
                    shear = float(shear_field[az_i, rng_j])
                    div   = float(divergence[az_i, rng_j])
                    dbz   = float(lowest[az_i, rng_j])

                    if dbz < self.MIN_DBZ:
                        continue
                    if shear < self.SHEAR_THRESHOLD_KTS:
                        continue

                    # Skip if a neighbouring cell already reported
                    cluster_key = (az_i // 5, rng_j // 5)
                    if cluster_key in reported_cells:
                        continue
                    reported_cells.add(cluster_key)

                    is_mb = div > self.MICROBURST_THRESHOLD
                    if shear > 30:
                        sev = "SEVERE"
                    elif shear > 20:
                        sev = "MODERATE"
                    else:
                        sev = "LOW"

                    # Estimate altitude from elevation angle and range
                    el0 = float(elevation_angles[0]) if elevation_angles else 0.5
                    range_m = (rng_j + 1) * (scan_range_km * 1000 / max(rng, 1))
                    alt_ft  = range_m * math.tan(math.radians(el0)) / 0.3048

                    events.append(WindShearEvent(
                        event_id    = self._next_id,
                        position_nm = (az_i * az_step_deg, rng_j * range_step_nm),
                        shear_knots = shear,
                        divergence  = div,
                        is_microburst = is_mb,
                        severity    = sev,
                        altitude_ft = max(0.0, alt_ft),
                    ))
                    self._next_id += 1

            events.sort(key=lambda e: -e.severity_level)
            self._last_result = events
            self._last_run = time.time()

            if events:
                mb_count = sum(1 for e in events if e.is_microburst)
                logger.info(
                    f"[WINDSHEAR] {len(events)} events detected "
                    f"({mb_count} microburst{'s' if mb_count != 1 else ''})"
                )
            return events

        except Exception as exc:
            logger.error(f"[WINDSHEAR] Processing error: {exc}")
            return []

    def get_last_result(self) -> List[WindShearEvent]:
        return list(self._last_result)

    def has_severe_event(self) -> bool:
        return any(e.severity == "SEVERE" for e in self._last_result)

    def has_microburst(self) -> bool:
        return any(e.is_microburst for e in self._last_result)


# ────────────────────────────────────────────── TurbulenceProcessor ────────

class TurbulenceProcessor:
    """
    Maps atmospheric turbulence from radar-derived spectrum-width proxy.

    Algorithm
    ---------
    Spectrum width (σᵥ) is the standard deviation of Doppler velocities
    within a resolution cell.  High σᵥ indicates turbulence.  In this
    simulation σᵥ is approximated from the spatial variance of the
    reflectivity field (areas of rapid dBZ fluctuation correlate with
    turbulent eddies).

    EDR (Eddy Dissipation Rate) proxy
    ----------------------------------
        EDR ∝ σᵥ^(2/3) / range^(1/3)

    Categories (FAA AC 120-88A)
        LIGHT    : EDR 0.1 – 0.2
        MODERATE : EDR 0.2 – 0.4
        SEVERE   : EDR 0.4 – 0.6
        EXTREME  : EDR > 0.6
    """

    MIN_DBZ          = 15.0   # even clear-air turbulence can appear at low reflectivity
    LIGHT_EDR        = 0.1
    MODERATE_EDR     = 0.2
    SEVERE_EDR       = 0.4
    EXTREME_EDR      = 0.6
    _NM_PER_KM       = 0.539957

    def __init__(self):
        self._next_id = 1
        self._last_result: List[TurbulenceCell] = []
        self._last_run = 0.0

    def process(self, reflectivity: np.ndarray,
                elevation_angles: Tuple,
                scan_range_km: float = 100.0) -> List[TurbulenceCell]:
        """
        Process reflectivity volume and return turbulence cells.

        Args:
            reflectivity:    3D array (azimuth × elevation × range), dBZ
            elevation_angles: sequence of elevation angles
            scan_range_km:   max instrumented range in km

        Returns:
            List of TurbulenceCell objects, strongest first
        """
        try:
            az, el, rng = reflectivity.shape
            if az == 0 or rng == 0:
                return []

            # Use lowest tilt for surface-layer turbulence
            field_2d = reflectivity[:, 0, :]

            # Spectrum-width proxy: local standard deviation in a 3×3 window
            from scipy.ndimage import uniform_filter
            local_mean = uniform_filter(field_2d.astype(float), size=3)
            local_sq   = uniform_filter(field_2d.astype(float)**2, size=3)
            variance   = np.maximum(0, local_sq - local_mean**2)
            sigma_v    = np.sqrt(variance)              # proxy for σᵥ (m/s equivalent)

            range_step_nm = (scan_range_km * self._NM_PER_KM) / max(rng - 1, 1)
            az_step_deg   = 360.0 / max(az, 1)

            cells: List[TurbulenceCell] = []
            reported: set = set()
            el0 = float(elevation_angles[0]) if elevation_angles else 0.5

            for az_i in range(az):
                for rng_j in range(rng):
                    sw   = float(sigma_v[az_i, rng_j])
                    dbz  = float(field_2d[az_i, rng_j])

                    if dbz < self.MIN_DBZ or sw < 1.0:
                        continue

                    # EDR proxy: scale sigma_v to rough EDR range
                    range_m = max(1, (rng_j + 1) * (scan_range_km * 1000 / max(rng, 1)))
                    edr = (sw ** (2.0/3.0)) / (range_m ** (1.0/3.0)) * 0.3

                    if edr < self.LIGHT_EDR:
                        continue

                    cluster_key = (az_i // 4, rng_j // 4)
                    if cluster_key in reported:
                        continue
                    reported.add(cluster_key)

                    if edr >= self.EXTREME_EDR:
                        category = "EXTREME"
                    elif edr >= self.SEVERE_EDR:
                        category = "SEVERE"
                    elif edr >= self.MODERATE_EDR:
                        category = "MODERATE"
                    else:
                        category = "LIGHT"

                    intensity = min(1.0, edr / self.EXTREME_EDR)
                    alt_ft    = max(0.0,
                                   range_m * math.tan(math.radians(el0)) / 0.3048)

                    cells.append(TurbulenceCell(
                        cell_id      = self._next_id,
                        position_nm  = (az_i * az_step_deg, rng_j * range_step_nm),
                        intensity    = intensity,
                        category     = category,
                        spectrum_width = sw,
                        altitude_ft  = alt_ft,
                    ))
                    self._next_id += 1

            cells.sort(key=lambda c: -c.intensity)
            self._last_result = cells
            self._last_run = time.time()

            if cells:
                severe = sum(1 for c in cells if c.category in ("SEVERE", "EXTREME"))
                logger.info(
                    f"[TURBULENCE] {len(cells)} cells mapped "
                    f"({severe} severe/extreme)"
                )
            return cells

        except Exception as exc:
            logger.error(f"[TURBULENCE] Processing error: {exc}")
            return []

    def get_last_result(self) -> List[TurbulenceCell]:
        return list(self._last_result)

    def max_category(self) -> str:
        if not self._last_result:
            return "NONE"
        order = {"NONE": 0, "LIGHT": 1, "MODERATE": 2,
                 "SEVERE": 3, "EXTREME": 4}
        return max(self._last_result, key=lambda c: order.get(c.category, 0)).category
