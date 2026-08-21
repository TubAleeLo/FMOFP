"""
AEWC Processor — Airborne Early Warning and Control Radar

Implements two capability modules from PLANNING.md §2.1 / §3.4:

  SectorPriorityManager   — dynamically prioritises coverage sectors based
                             on track density, threat level, and mission phase.

  ElectronicProtection    — detects and mitigates RF jamming / interference.

Both processors are called from the AEWC radar on each update cycle.

Sector Prioritisation
---------------------
Each of the six AEWC sectors is assigned a priority score:

  score = track_density_weight × n_tracks
        + threat_weight        × n_hostile_tracks
        + dwell_penalty        × time_since_last_scan

Higher-priority sectors receive proportionally more dwell time.

Electronic Protection
---------------------
Jamming is detected by monitoring receiver noise power in each sector.
If the apparent noise floor exceeds the expected thermal noise by more than
ECM_THRESHOLD_DB, that sector is flagged as jammed.

Mitigation actions (in order of aggression):
  1. Frequency agility — move to a notch frequency.
  2. Beam notching — null the jammer direction.
  3. Power increase — raise transmit power to overcome jamming.
  4. Sector skip — temporarily abandon the jammed sector.
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ─────────────────────────────────── SectorPriorityManager ───────────────

@dataclass
class SectorStatus:
    sector_id:          str
    priority_score:     float
    n_tracks:           int
    n_hostile:          int
    dwell_fraction:     float   # 0-1 share of radar time
    last_scan_time:     float
    jammed:             bool = False


class SectorPriorityManager:
    """
    Dynamic sector priority scheduler for AEWC coverage.

    On each scheduling epoch the manager:
      1. Collects current track counts per sector from the AEWC radar.
      2. Scores each sector.
      3. Normalises scores to fractional dwell allocations.
      4. Returns the ordered scan sequence for this epoch.
    """

    # Scoring weights
    W_DENSITY    = 1.0    # weight for total track count in sector
    W_THREAT     = 3.0    # weight for hostile tracks (higher priority)
    W_DWELL_AGE  = 0.5    # weight for time-since-last-scan (prevents starvation)
    MIN_DWELL    = 0.05   # every sector gets at least 5 % of dwell time

    def __init__(self, sector_ids: List[str]):
        self._statuses: Dict[str, SectorStatus] = {
            sid: SectorStatus(
                sector_id      = sid,
                priority_score = 1.0,
                n_tracks       = 0,
                n_hostile      = 0,
                dwell_fraction = 1.0 / max(len(sector_ids), 1),
                last_scan_time = time.time(),
            )
            for sid in sector_ids
        }

    def update(self, sector_track_counts: Dict[str, int],
               sector_hostile_counts: Dict[str, int],
               jammed_sectors: set) -> List[str]:
        """
        Recompute sector priorities and return the ordered scan sequence.

        Args:
            sector_track_counts  : {sector_id: total track count}
            sector_hostile_counts: {sector_id: hostile track count}
            jammed_sectors       : set of sector_ids currently jammed

        Returns:
            Ordered list of sector_ids (highest priority first).
        """
        now = time.time()
        raw_scores: Dict[str, float] = {}

        for sid, status in self._statuses.items():
            n_tracks  = sector_track_counts.get(sid, 0)
            n_hostile = sector_hostile_counts.get(sid, 0)
            age       = now - status.last_scan_time

            score = (self.W_DENSITY   * n_tracks +
                     self.W_THREAT    * n_hostile +
                     self.W_DWELL_AGE * age)

            # Jammed sectors get a boost so we monitor them more closely
            if sid in jammed_sectors:
                score += 2.0

            raw_scores[sid]  = score
            status.n_tracks  = n_tracks
            status.n_hostile = n_hostile
            status.jammed    = sid in jammed_sectors

        total = sum(raw_scores.values()) or 1.0
        for sid in self._statuses:
            frac = max(self.MIN_DWELL, raw_scores[sid] / total)
            self._statuses[sid].priority_score  = raw_scores[sid]
            self._statuses[sid].dwell_fraction  = frac

        ordered = sorted(self._statuses.keys(),
                         key=lambda s: -self._statuses[s].priority_score)
        logger.debug(f"[AEWC_PROC] Sector order: {ordered}")
        return ordered

    def mark_scanned(self, sector_id: str) -> None:
        """Mark a sector as just scanned (resets dwell age)."""
        if sector_id in self._statuses:
            self._statuses[sector_id].last_scan_time = time.time()

    def get_dwell_allocation(self) -> Dict[str, float]:
        return {sid: s.dwell_fraction for sid, s in self._statuses.items()}

    def get_status(self, sector_id: str) -> Optional[SectorStatus]:
        return self._statuses.get(sector_id)


# ─────────────────────────────────── ElectronicProtection ────────────────

@dataclass
class JammerContact:
    sector_id:          str
    estimated_bearing:  float    # degrees (best estimate)
    jam_type:           str      # "CONTINUOUS" | "SPOT" | "SWEEP" | "DECEPTIVE"
    severity:           float    # 0-1
    mitigation_active:  str      # "NONE" | "FREQ_AGILITY" | "BEAM_NOTCH" | "POWER" | "SKIP"
    first_detected:     float
    last_seen:          float = field(default_factory=time.time)


class ElectronicProtection:
    """
    Detects and mitigates RF jamming in the AEWC sensor.

    Jamming detection
    -----------------
    The noise floor in each sector is compared against the theoretical
    thermal noise.  A noise exceedance > ECM_THRESHOLD_DB is treated as
    active jamming.

    Mitigation hierarchy
    --------------------
    MILD   (severity < 0.4) → Frequency agility
    MEDIUM (severity < 0.7) → Beam notching + frequency agility
    SEVERE (severity ≥ 0.7) → Power increase + notching
    CRITICAL               → Sector skip (last resort)
    """

    ECM_THRESHOLD_DB   = 6.0    # dB above noise floor → jamming
    THERMAL_NOISE_DBM  = -110   # dBm expected noise floor
    JAMMER_TTL_S       = 15.0   # seconds before a lost jammer is dropped

    def __init__(self):
        self._jammers: Dict[str, JammerContact] = {}   # sector_id → contact
        self._freq_offset: float = 0.0                 # current frequency offset (MHz)

    def assess_sector(self, sector_id: str,
                      apparent_noise_dbm: float) -> Optional[JammerContact]:
        """
        Assess a sector for jamming and update mitigation state.

        Args:
            sector_id         : sector identifier
            apparent_noise_dbm: measured noise power (dBm)

        Returns:
            JammerContact if jamming detected, else None
        """
        try:
            exceedance = apparent_noise_dbm - self.THERMAL_NOISE_DBM
            now = time.time()

            if exceedance < self.ECM_THRESHOLD_DB:
                # No jamming — clear any existing contact for this sector
                if sector_id in self._jammers:
                    del self._jammers[sector_id]
                return None

            severity = min(1.0, exceedance / 40.0)   # normalise 6–46 dB → 0-1

            # Determine jammer type from noise characteristics (simplified)
            if exceedance > 30:
                jam_type = "CONTINUOUS"
            elif exceedance > 20:
                jam_type = "SPOT"
            elif exceedance > 10:
                jam_type = "SWEEP"
            else:
                jam_type = "DECEPTIVE"

            # Bearing estimate (random in sector — would be AOA-derived in hardware)
            bearing = random.uniform(0, 360)

            mitigation = self._select_mitigation(severity, sector_id)
            self._apply_mitigation(mitigation, sector_id)

            if sector_id in self._jammers:
                contact = self._jammers[sector_id]
                contact.severity          = severity
                contact.jam_type          = jam_type
                contact.mitigation_active = mitigation
                contact.last_seen         = now
            else:
                contact = JammerContact(
                    sector_id         = sector_id,
                    estimated_bearing = bearing,
                    jam_type          = jam_type,
                    severity          = severity,
                    mitigation_active = mitigation,
                    first_detected    = now,
                )
                self._jammers[sector_id] = contact
                logger.warning(
                    f"[ECM] Jamming detected in {sector_id}: "
                    f"{jam_type} severity={severity:.2f}  "
                    f"mitigation={mitigation}"
                )

            return contact

        except Exception as exc:
            logger.error(f"[ECM] Assessment error in {sector_id}: {exc}")
            return None

    def _select_mitigation(self, severity: float, sector_id: str) -> str:
        if severity < 0.4:
            return "FREQ_AGILITY"
        elif severity < 0.7:
            return "BEAM_NOTCH"
        elif severity < 0.9:
            return "POWER"
        else:
            return "SKIP"

    def _apply_mitigation(self, mitigation: str, sector_id: str) -> None:
        """Apply the selected mitigation (simulated effects)."""
        if mitigation == "FREQ_AGILITY":
            self._freq_offset = random.uniform(5, 50)   # hop ±50 MHz
            logger.debug(f"[ECM] Frequency agility: +{self._freq_offset:.0f} MHz")
        elif mitigation == "BEAM_NOTCH":
            logger.debug(f"[ECM] Beam notch applied to {sector_id}")
        elif mitigation == "POWER":
            logger.debug(f"[ECM] Transmit power increased for {sector_id}")
        elif mitigation == "SKIP":
            logger.warning(f"[ECM] Sector {sector_id} skipped due to severe jamming")

    def cleanup_stale(self) -> None:
        """Remove jammer contacts that have not been seen recently."""
        now = time.time()
        stale = [sid for sid, j in self._jammers.items()
                 if now - j.last_seen > self.JAMMER_TTL_S]
        for sid in stale:
            del self._jammers[sid]

    def get_active_jammers(self) -> List[JammerContact]:
        return list(self._jammers.values())

    def is_sector_jammed(self, sector_id: str) -> bool:
        return sector_id in self._jammers

    def get_jammed_sectors(self) -> set:
        return set(self._jammers.keys())

    @property
    def freq_offset_mhz(self) -> float:
        return self._freq_offset
