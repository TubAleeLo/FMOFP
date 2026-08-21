"""
TFR Processor — Terrain Following Radar

Implements two capability modules from PLANNING.md §2.1 / §3.5:

  PathOptimiser     — generates a safe flight path through the terrain
                      profile by minimising exposure while maintaining
                      the aircraft's minimum clearance altitude.

  ClearanceManager  — continuously monitors terrain clearance and escalates
                      warnings through LOW / CAUTION / PULL_UP levels.

Both processors are called by the TFR radar on each terrain profile update.

Path Optimisation
-----------------
Given the ordered elevation profile [(distance_m, height_m), …] the
optimiser computes a safe altitude command sequence using a simple
look-ahead algorithm:

  1. Slide a look-ahead window forward (defaulting to 5 nm / ~9 km).
  2. In each window find the maximum terrain height.
  3. Required altitude = max_height + CLEARANCE_M.
  4. Rate-limit altitude commands so the aircraft can actually achieve them.
  5. Return the command sequence as a list of (distance_m, alt_m) waypoints.

Clearance Management
--------------------
The clearance manager classifies each terrain profile point against the
aircraft's current barometric altitude and assigns a warning level:

  CLEAR      → clearance ≥ CLEAR_M
  LOW        → clearance ≥ LOW_M but < CLEAR_M
  CAUTION    → clearance ≥ CAUTION_M but < LOW_M
  PULL_UP    → clearance < CAUTION_M  (immediate action required)
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ──────────────────────────────────────────────── constants ────────────────

# Clearance thresholds (metres AGL)
CLEAR_M      = 600     # comfortable — no advisory
LOW_M        = 300     # low advisory
CAUTION_M    = 150     # caution advisory
PULL_UP_M    = 60      # PULL UP (immediate)

# Path optimiser constants
MIN_CLEARANCE_M  = 300     # minimum commanded clearance above terrain
LOOKAHEAD_M      = 9260    # look-ahead distance (≈ 5 nm)
MAX_ALT_RATE_MPS = 25      # max climb rate used in command smoothing (m/s)
_FT_PER_M        = 3.28084


# ──────────────────────────────────────────── ClearanceManager ─────────────

@dataclass
class ClearanceWarning:
    """A clearance advisory for a specific terrain profile point."""
    distance_m:   float
    terrain_m:    float
    clearance_m:  float
    level:        str      # "CLEAR" | "LOW" | "CAUTION" | "PULL_UP"
    timestamp:    float = field(default_factory=time.time)

    @property
    def is_actionable(self) -> bool:
        return self.level in ("CAUTION", "PULL_UP")

    @property
    def is_critical(self) -> bool:
        return self.level == "PULL_UP"


class ClearanceManager:
    """
    Continuous terrain clearance monitor.

    Tracks the minimum clearance seen since last reset and upgrades
    the master warning level on each profile update.
    """

    def __init__(self):
        self._master_level = "CLEAR"
        self._last_warnings: List[ClearanceWarning] = []
        self._min_clearance_m = float("inf")

    def assess_profile(self,
                       terrain_profile: List[Tuple[float, float]],
                       aircraft_alt_m: float) -> List[ClearanceWarning]:
        """
        Assess the terrain profile against the aircraft's current altitude.

        Args:
            terrain_profile : [(distance_m, terrain_height_m), …]
            aircraft_alt_m  : current barometric altitude in metres MSL

        Returns:
            List of ClearanceWarning objects, critical first.
        """
        warnings: List[ClearanceWarning] = []
        min_cl = float("inf")

        for distance_m, terrain_m in terrain_profile:
            clearance = aircraft_alt_m - terrain_m
            min_cl    = min(min_cl, clearance)

            if clearance >= CLEAR_M:
                level = "CLEAR"
            elif clearance >= LOW_M:
                level = "LOW"
            elif clearance >= CAUTION_M:
                level = "CAUTION"
            else:
                level = "PULL_UP"

            if level != "CLEAR":
                warnings.append(ClearanceWarning(
                    distance_m  = distance_m,
                    terrain_m   = terrain_m,
                    clearance_m = clearance,
                    level       = level,
                ))

        # Upgrade master warning level
        order = {"CLEAR": 0, "LOW": 1, "CAUTION": 2, "PULL_UP": 3}
        if warnings:
            worst = max(warnings, key=lambda w: order.get(w.level, 0))
            if order.get(worst.level, 0) > order.get(self._master_level, 0):
                self._master_level = worst.level
                logger.warning(
                    f"[TFR_PROC] Clearance master level: {self._master_level}  "
                    f"min_clearance={min_cl:.0f} m "
                    f"({min_cl * _FT_PER_M:.0f} ft)"
                )

        self._min_clearance_m  = min_cl if min_cl < float("inf") else 0.0
        self._last_warnings    = warnings
        # Decay master level toward CLEAR over time (auto-recovery)
        if not warnings:
            self._master_level = "CLEAR"

        warnings.sort(key=lambda w: -order.get(w.level, 0))
        return warnings

    @property
    def master_level(self) -> str:
        return self._master_level

    @property
    def min_clearance_m(self) -> float:
        return self._min_clearance_m

    @property
    def min_clearance_ft(self) -> float:
        return self._min_clearance_m * _FT_PER_M

    def get_last_warnings(self) -> List[ClearanceWarning]:
        return list(self._last_warnings)

    def reset(self) -> None:
        self._master_level   = "CLEAR"
        self._last_warnings  = []
        self._min_clearance_m = float("inf")


# ──────────────────────────────────────────────── PathOptimiser ────────────

@dataclass
class AltitudeCommand:
    """A commanded altitude at a given forward distance."""
    distance_m:  float
    altitude_m:  float    # target barometric altitude (MSL)
    reason:      str      # "TERRAIN_AVOIDANCE" | "OBSTACLE" | "CLEARANCE"

    @property
    def altitude_ft(self) -> float:
        return self.altitude_m * _FT_PER_M


class PathOptimiser:
    """
    Generates a smooth, minimum-exposure flight path through the terrain.

    The optimiser works on the ordered elevation profile produced by the
    TFR radar and returns a sequence of altitude commands that keep the
    aircraft above MIN_CLEARANCE_M at all points within the look-ahead
    window.

    The path is rate-limited: transitions between successive command
    altitudes are constrained to MAX_ALT_RATE_MPS to ensure the aircraft
    can physically follow the profile at its current speed.
    """

    def __init__(self, aircraft_speed_ms: float = 250.0):
        self.aircraft_speed_ms = aircraft_speed_ms   # m/s (≈ 486 knots)
        self._last_commands: List[AltitudeCommand] = []

    def compute_path(self,
                     terrain_profile: List[Tuple[float, float]],
                     current_alt_m: float,
                     lookahead_m: float = LOOKAHEAD_M) -> List[AltitudeCommand]:
        """
        Compute safe altitude commands for the terrain profile.

        Args:
            terrain_profile : [(distance_m, terrain_height_m), …] ordered by distance
            current_alt_m   : aircraft's current barometric altitude (metres MSL)
            lookahead_m     : look-ahead window length (metres)

        Returns:
            List of AltitudeCommand sorted by distance.
        """
        if not terrain_profile:
            return []

        try:
            # Filter to look-ahead window
            window = [(d, h) for d, h in terrain_profile if d <= lookahead_m]
            if not window:
                window = terrain_profile[:20]   # fallback: take first 20 points

            # Sliding window: compute required altitude at each step
            window_size_pts = max(5, len(window) // 10)
            commands: List[AltitudeCommand] = []
            prev_alt = current_alt_m

            for i, (dist, _) in enumerate(window):
                # Look ahead from this point
                ahead_end = min(len(window), i + window_size_pts)
                ahead_heights = [h for _, h in window[i:ahead_end]]
                max_terrain = max(ahead_heights) if ahead_heights else 0.0

                required_alt = max_terrain + MIN_CLEARANCE_M

                # Rate limiting: can we reach required_alt from prev_alt?
                time_available_s = (
                    dist / max(self.aircraft_speed_ms, 1.0)
                )
                max_delta = MAX_ALT_RATE_MPS * time_available_s
                commanded = max(prev_alt - max_delta,
                                min(prev_alt + max_delta, required_alt))

                # Only emit a new command if there's a meaningful change
                if (not commands or
                        abs(commanded - commands[-1].altitude_m) > 20.0):
                    commands.append(AltitudeCommand(
                        distance_m = dist,
                        altitude_m = commanded,
                        reason     = "TERRAIN_AVOIDANCE",
                    ))
                    prev_alt = commanded

            # Final point: ensure we clear the highest terrain in the window
            max_in_window = max(h for _, h in window)
            clearance_alt = max_in_window + MIN_CLEARANCE_M
            if not commands or commands[-1].altitude_m < clearance_alt:
                commands.append(AltitudeCommand(
                    distance_m = window[-1][0],
                    altitude_m = clearance_alt,
                    reason     = "CLEARANCE",
                ))

            self._last_commands = commands
            logger.debug(
                f"[TFR_PROC] Path: {len(commands)} waypoints, "
                f"min_alt={min(c.altitude_m for c in commands):.0f} m, "
                f"max_alt={max(c.altitude_m for c in commands):.0f} m"
            )
            return commands

        except Exception as exc:
            logger.error(f"[TFR_PROC] Path optimisation error: {exc}")
            return []

    def get_last_commands(self) -> List[AltitudeCommand]:
        return list(self._last_commands)

    def update_speed(self, speed_ms: float) -> None:
        self.aircraft_speed_ms = max(50.0, speed_ms)
