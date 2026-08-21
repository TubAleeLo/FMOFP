"""
Cross-Radar Data Fusion Layer
===============================
Correlates air tracks from multiple sensor sources (Targeting Radar, AEWC)
into a single, authoritative Fused Track Table.

Architecture
------------
                ┌──────────────────┐
                │  targeting_radar  │──► current_targets {id: track_dict}
                └──────────────────┘       │
                                           ▼
                ┌──────────────────┐   RadarDataFusion._update()
                │   aewc_radar     │──► correlate → merge → FusedTrack table
                └──────────────────┘       │
                                           ▼
                                    get_fused_tracks()
                                           │
                                 ┌─────────┴─────────┐
                                 ▼                   ▼
                            TSD display       (future) SMS, MFD

Coordinate system
-----------------
All radars use Cartesian ENU (East-North-Up) metres relative to the own
aircraft as the common frame.  Bearing and range conversions for display
are done at read time, not in the fusion layer.

Correlation gate
----------------
Two reports from different sensors are treated as the same contact when
their 3-D Euclidean separation is ≤ GATE_M (500 m by default).

Track confidence
----------------
  - Single-sensor track   → confidence = sensor weight (0.7 or 0.8)
  - Correlated dual-sensor → confidence = 1 − (1−w₁)(1−w₂)  (probability union)

Threat assessment
-----------------
  HOSTILE  ← classification contains "HOSTILE" or identity is known adversary
  UNKNOWN  ← default
  FRIENDLY ← classification/identity explicitly friendly

Lifecycle
---------
Tracks age out after TRACK_TTL_S seconds without a new report.
The fusion runs at UPDATE_HZ on a daemon thread started by start() /
stopped by stop().  It is safe to call get_fused_tracks() from any thread.
"""

import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ── tuneable constants ────────────────────────────────────────────────────────

GATE_M          = 500.0   # correlation gate radius (metres)
TRACK_TTL_S     = 30.0    # seconds before an unseen track is dropped
UPDATE_HZ       = 2.0     # fusion update rate

# Sensor confidence weights
_W_TARGETING    = 0.80    # Targeting radar: high-accuracy, short-range
_W_AEWC         = 0.70    # AEWC: wide-area but lower precision

_METRES_PER_NM  = 1852.0

# ── data structures ───────────────────────────────────────────────────────────

@dataclass
class FusedTrack:
    """
    A single fused air track — the output of the fusion layer.

    position_m  : (x, y, z) metres, ENU relative to own ship
    velocity_ms : (vx, vy, vz) m/s
    confidence  : 0-1, fused detection probability
    classification : e.g. "FIGHTER", "UNKNOWN", "FRIENDLY"
    identity    : IFF / squawk code string or "UNKNOWN"
    threat      : "HOSTILE" | "UNKNOWN" | "FRIENDLY"
    sources     : list of sensor names that contributed
    last_seen   : Unix timestamp of last contributing report
    track_id    : stable UUID string for this fused contact
    """
    track_id:       str
    position_m:     Tuple[float, float, float]
    velocity_ms:    Tuple[float, float, float]
    confidence:     float
    classification: str
    identity:       str
    threat:         str
    sources:        List[str]
    last_seen:      float

    # ── convenience properties ─────────────────────────────────────────────

    @property
    def range_m(self) -> float:
        x, y, z = self.position_m
        return math.sqrt(x*x + y*y + z*z)

    @property
    def range_nm(self) -> float:
        return self.range_m / _METRES_PER_NM

    @property
    def bearing_deg(self) -> float:
        """
        Bearing from own ship to track in degrees true (0° = North / +Y axis).
        Uses ENU convention: East = +X, North = +Y.
        """
        x, y, _ = self.position_m
        return math.degrees(math.atan2(x, y)) % 360

    @property
    def altitude_ft(self) -> float:
        return self.position_m[2] / 0.3048

    def is_hostile(self) -> bool:
        return self.threat == "HOSTILE"

    def to_tsd_dict(self) -> Dict:
        """Convert to the dict format expected by the TSD threat display."""
        return {
            "bearing":   self.bearing_deg,
            "range_nm":  self.range_nm,
            "type":      self.classification,
            "hostile":   self.is_hostile(),
            "confidence": self.confidence,
            "sources":   list(self.sources),
            "track_id":  self.track_id,
            "identity":  self.identity,
        }


# ── fusion engine ─────────────────────────────────────────────────────────────

class RadarDataFusion:
    """
    Singleton cross-radar data fusion engine.

    Pulls live track data from the radar management system's radar instances,
    correlates them across sensors, and maintains a Fused Track Table.

    Usage
    -----
    fusion = get_radar_data_fusion()
    fusion.start()                         # begin update thread

    tracks = fusion.get_fused_tracks()     # thread-safe read

    fusion.stop()
    """

    _instance: Optional["RadarDataFusion"] = None
    _lock_class = threading.Lock()

    def __new__(cls) -> "RadarDataFusion":
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._fused_tracks: Dict[str, FusedTrack] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._radar_ctrl = None
        self._initialized = True
        logger.info("[FUSION] RadarDataFusion initialised")

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the fusion update thread (daemon, safe to call repeatedly)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="RadarDataFusion",
            daemon=True,
        )
        self._thread.start()
        logger.info("[FUSION] Update thread started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("[FUSION] Stopped")

    # ── public query interface ────────────────────────────────────────────────

    def get_fused_tracks(self) -> List[FusedTrack]:
        """Return a snapshot of the current fused track table (thread-safe)."""
        with self._lock:
            return list(self._fused_tracks.values())

    def get_threat_tracks(self) -> List[FusedTrack]:
        """Return only tracks assessed as HOSTILE."""
        with self._lock:
            return [t for t in self._fused_tracks.values()
                    if t.threat == "HOSTILE"]

    def get_track_count(self) -> int:
        with self._lock:
            return len(self._fused_tracks)

    # ── update loop ───────────────────────────────────────────────────────────

    def _run(self) -> None:
        logger.info("[FUSION] Update loop running")
        interval = 1.0 / UPDATE_HZ
        while not self._stop_event.is_set():
            try:
                self._update()
            except Exception as exc:
                logger.error(f"[FUSION] Update error: {exc}")
            self._stop_event.wait(interval)
        logger.info("[FUSION] Update loop exited")

    def _update(self) -> None:
        """
        Single fusion epoch:
          1. Collect raw reports from all sensor sources.
          2. Correlate across sensors (nearest-neighbour within gate).
          3. Merge correlated reports into fused tracks.
          4. Age out stale tracks.
          5. Write results to the fused track table.
        """
        reports = self._collect_reports()
        new_table = self._correlate_and_merge(reports)
        self._age_out(new_table)
        with self._lock:
            self._fused_tracks = new_table

    # ── report collection ─────────────────────────────────────────────────────

    def _lazy_radar_ctrl(self):
        """Lazy-load the radar management system to avoid circular imports."""
        if self._radar_ctrl is None:
            try:
                from FMOFP.Systems.radarManagement.radarControl import (
                    get_radar_management_system,
                )
                self._radar_ctrl = get_radar_management_system()
            except Exception as exc:
                logger.debug(f"[FUSION] Radar ctrl not ready: {exc}")
        return self._radar_ctrl

    def _collect_reports(self) -> List[Dict]:
        """
        Pull raw track dicts from each active radar and tag them with
        sensor name and weight.

        Returns a flat list of report dicts, each guaranteed to have:
            position  : (x, y, z) metres
            velocity  : (vx, vy, vz) m/s
            sensor    : str
            weight    : float (sensor confidence)
            classification : str
            identity  : str
        """
        ctrl = self._lazy_radar_ctrl()
        if ctrl is None:
            return []

        reports: List[Dict] = []

        radars = getattr(ctrl, "radars", {})
        for radar_name, radar in radars.items():
            targets = getattr(radar, "current_targets", {})
            if not targets:
                continue

            if "targeting" in radar_name:
                weight = _W_TARGETING
            elif "aewc" in radar_name:
                weight = _W_AEWC
            else:
                continue   # weather, SAR, TFR don't produce air tracks

            for track_id, tdata in targets.items():
                if not isinstance(tdata, dict):
                    continue
                pos = tdata.get("position") or (0.0, 0.0, 0.0)
                vel = tdata.get("velocity") or (0.0, 0.0, 0.0)
                if len(pos) < 3:
                    pos = (*pos, 0.0)
                if len(vel) < 3:
                    vel = (*vel, 0.0)

                reports.append({
                    "position":       tuple(float(v) for v in pos[:3]),
                    "velocity":       tuple(float(v) for v in vel[:3]),
                    "classification": str(tdata.get("classification", "UNKNOWN")),
                    "identity":       str(tdata.get("identity", "UNKNOWN")),
                    "rcs":            float(tdata.get("rcs", 5.0)),
                    "is_stealth":     bool(tdata.get("is_stealth", False)),
                    "sensor":         radar_name,
                    "weight":         weight,
                    "source_id":      str(track_id),
                    "timestamp":      float(tdata.get("last_update", time.time())),
                })

        return reports

    # ── correlation and merging ───────────────────────────────────────────────

    @staticmethod
    def _distance_m(pos_a: Tuple, pos_b: Tuple) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos_a[:3], pos_b[:3])))

    def _correlate_and_merge(
        self, reports: List[Dict]
    ) -> Dict[str, FusedTrack]:
        """
        Greedy nearest-neighbour correlation within GATE_M.

        Algorithm:
          - Sort reports by sensor weight (highest first) so high-quality
            sensors anchor the clusters.
          - For each unassigned report, find the nearest existing cluster
            centroid within GATE_M.  If found, merge; otherwise start a
            new cluster.
          - After clustering, carry over stable track_ids from the previous
            epoch's fused table (positional nearest-neighbour within GATE_M).
        """
        if not reports:
            return {}

        # Clusters: list of lists of report dicts
        clusters: List[List[Dict]] = []

        for report in sorted(reports, key=lambda r: -r["weight"]):
            assigned = False
            best_cluster = None
            best_dist = float("inf")
            for cluster in clusters:
                centroid = _centroid([r["position"] for r in cluster])
                d = self._distance_m(report["position"], centroid)
                if d < GATE_M and d < best_dist:
                    best_dist = d
                    best_cluster = cluster
            if best_cluster is not None:
                best_cluster.append(report)
            else:
                clusters.append([report])

        # Convert clusters to FusedTrack objects
        now = time.time()
        new_table: Dict[str, FusedTrack] = {}

        for cluster in clusters:
            track = self._merge_cluster(cluster, now)
            new_table[track.track_id] = track

        # Carry over stable track IDs from previous epoch
        with self._lock:
            old_table = self._fused_tracks.copy()

        self._reassign_ids(new_table, old_table)
        return new_table

    def _merge_cluster(self, cluster: List[Dict], timestamp: float) -> FusedTrack:
        """
        Merge a list of correlated reports into a single FusedTrack.

        Position  : weighted average (by sensor weight)
        Velocity  : weighted average
        Confidence: 1 − ∏(1 − wᵢ)  (probability union)
        Classification / identity: highest-weight sensor's value
        Threat    : derived from merged classification/identity
        """
        total_w = sum(r["weight"] for r in cluster)

        # Weighted position average
        pos = tuple(
            sum(r["position"][i] * r["weight"] for r in cluster) / total_w
            for i in range(3)
        )
        vel = tuple(
            sum(r["velocity"][i] * r["weight"] for r in cluster) / total_w
            for i in range(3)
        )

        # Confidence: probability union across independent sensors
        confidence = 1.0 - math.prod(1.0 - r["weight"] for r in cluster)
        confidence = min(1.0, confidence)

        # Classification and identity from highest-weight report
        anchor = max(cluster, key=lambda r: r["weight"])
        classification = anchor["classification"]
        identity       = anchor["identity"]

        # Threat assessment
        threat = self._assess_threat(classification, identity, cluster)

        sources = list({r["sensor"] for r in cluster})

        return FusedTrack(
            track_id       = str(uuid.uuid4()),   # provisional; reassigned below
            position_m     = pos,                  # type: ignore[arg-type]
            velocity_ms    = vel,                  # type: ignore[arg-type]
            confidence     = confidence,
            classification = classification,
            identity       = identity,
            threat         = threat,
            sources        = sources,
            last_seen      = timestamp,
        )

    @staticmethod
    def _assess_threat(classification: str, identity: str,
                       cluster: List[Dict]) -> str:
        """
        Simple threat assessment rule set.

        HOSTILE  — classification or identity explicitly hostile, or
                   RCS is consistent with a fighter (small) and confidence high
        FRIENDLY — explicitly friendly IFF
        UNKNOWN  — everything else
        """
        cls_upper = classification.upper()
        id_upper  = identity.upper()

        hostile_keywords = {"HOSTILE", "ENEMY", "BANDIT", "BOGEY"}
        friendly_keywords = {"FRIENDLY", "ALLY", "BLUE", "FRIENDLY_FORCE"}

        if any(k in cls_upper or k in id_upper for k in hostile_keywords):
            return "HOSTILE"
        if any(k in cls_upper or k in id_upper for k in friendly_keywords):
            return "FRIENDLY"
        # Heuristic: high-confidence, high-speed, small RCS → treat as hostile
        avg_rcs = sum(r.get("rcs", 5.0) for r in cluster) / len(cluster)
        speed   = math.sqrt(sum(v**2 for v in cluster[0]["velocity"]))
        if avg_rcs < 3.0 and speed > 200:
            return "HOSTILE"
        return "UNKNOWN"

    # ── track ID continuity ───────────────────────────────────────────────────

    def _reassign_ids(
        self,
        new_table:  Dict[str, FusedTrack],
        old_table:  Dict[str, FusedTrack],
    ) -> None:
        """
        Re-use stable track IDs from the previous epoch by nearest-neighbour
        matching within GATE_M.  New contacts that don't match any old track
        keep their provisional UUID.
        """
        used_old_ids: set = set()

        for new_id, new_track in new_table.items():
            best_old_id   = None
            best_dist     = float("inf")
            for old_id, old_track in old_table.items():
                if old_id in used_old_ids:
                    continue
                d = self._distance_m(new_track.position_m, old_track.position_m)
                if d < GATE_M and d < best_dist:
                    best_dist   = d
                    best_old_id = old_id

            if best_old_id is not None:
                # Overwrite the provisional UUID with the stable old ID
                stable_track = FusedTrack(
                    track_id       = best_old_id,
                    position_m     = new_track.position_m,
                    velocity_ms    = new_track.velocity_ms,
                    confidence     = new_track.confidence,
                    classification = new_track.classification,
                    identity       = new_track.identity,
                    threat         = new_track.threat,
                    sources        = new_track.sources,
                    last_seen      = new_track.last_seen,
                )
                new_table[new_id] = stable_track
                used_old_ids.add(best_old_id)

    # ── ageing ────────────────────────────────────────────────────────────────

    def _age_out(self, table: Dict[str, FusedTrack]) -> None:
        """Remove tracks not refreshed within TRACK_TTL_S."""
        now  = time.time()
        stale = [tid for tid, t in table.items()
                 if now - t.last_seen > TRACK_TTL_S]
        for tid in stale:
            del table[tid]
            logger.debug(f"[FUSION] Track {tid[:8]} aged out")


# ── helpers ───────────────────────────────────────────────────────────────────

def _centroid(positions: List[Tuple]) -> Tuple:
    n = len(positions)
    return tuple(sum(p[i] for p in positions) / n for i in range(3))


# ── singleton accessor ────────────────────────────────────────────────────────

_fusion_instance: Optional[RadarDataFusion] = None

def get_radar_data_fusion() -> RadarDataFusion:
    """Return the singleton RadarDataFusion instance."""
    global _fusion_instance
    if _fusion_instance is None:
        _fusion_instance = RadarDataFusion()
    return _fusion_instance
