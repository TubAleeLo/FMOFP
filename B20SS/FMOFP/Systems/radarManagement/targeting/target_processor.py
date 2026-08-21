"""
Target Processor — Targeting Radar

Implements two capability modules planned in PLANNING.md §2.1:

  SignatureAnalyzer   — RCS-based target classification using Swerling
                        scintillation models and pattern matching.

  StealthDetector     — Enhanced sensitivity processing for low-observable
                        (stealth) targets using non-coherent integration.

Both are called from the targeting radar's track update loop; they enrich
each track dict in-place with additional fields.

Output fields added to each track dict
---------------------------------------
  rcs_model       : str  — "SWERLING_1" | "SWERLING_2" | "NON_FLUCTUATING"
  signature_class : str  — refined classification
  stealth_flag    : bool — True if low-observable characteristics detected
  stealth_prob    : float — 0-1 probability of stealth
  detection_confidence : float — overall detection confidence 0-1
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


# ───────────────────────────────────────────────── Swerling model tables ──

# RCS fluctuation models (simplified):
#   Swerling 1 — slow fluctuator, scan-to-scan (typical fighter aircraft)
#   Swerling 2 — fast fluctuator, pulse-to-pulse (chaff, some missiles)
#   Non-fluctuating — rigid body (calibration sphere, certain missiles)

_SWERLING_MODELS = {
    "FIGHTER":       "SWERLING_1",
    "BOMBER":        "SWERLING_1",
    "HIGH_ALT":      "SWERLING_2",
    "MISSILE":       "SWERLING_2",
    "HELICOPTER":    "SWERLING_1",
    "DRONE":         "SWERLING_2",
    "UNKNOWN":       "SWERLING_1",
}

# RCS reference values (m²) for common target types
_RCS_REFERENCE = {
    "FIGHTER":    2.0,
    "BOMBER":    40.0,
    "HIGH_ALT":  10.0,
    "MISSILE":    0.05,
    "HELICOPTER":  3.0,
    "DRONE":       0.01,
    "UNKNOWN":     5.0,
}

# RCS thresholds for stealth assessment
_STEALTH_RCS_THRESHOLD_M2 = 0.1   # below this → candidate stealth
_STEALTH_PROB_HIGH        = 0.85
_STEALTH_PROB_LOW         = 0.15


@dataclass
class SignatureReport:
    track_id:            int
    rcs_measured:        float     # m²
    rcs_model:           str
    signature_class:     str
    confidence:          float     # classification confidence 0-1
    stealth_flag:        bool
    stealth_probability: float
    timestamp:           float


class SignatureAnalyzer:
    """
    Analyses radar cross-section signatures to refine target classification.

    Process
    -------
    1. Apply Swerling model correction to the measured RCS (accounts for
       target scintillation — RCS varies between scan dwells).
    2. Compare corrected RCS against reference values for each target type.
    3. Choose the most likely type using a nearest-neighbour RCS match.
    4. Estimate classification confidence from the RCS spread.
    """

    def __init__(self):
        self._reports: Dict[int, SignatureReport] = {}

    def analyse(self, track_id: int, track: Dict) -> Dict:
        """
        Enrich a track dict with signature analysis results.

        Args:
            track_id : integer track identifier
            track    : track dict (modified in-place)

        Returns:
            Same track dict with added keys.
        """
        try:
            rcs_raw = float(track.get("rcs", 5.0))
            speed   = math.sqrt(sum(v**2 for v in track.get("velocity", (0,0,0))))
            alt_m   = track.get("position", (0, 0, 0))[2]

            # Swerling 1 correction: chi-squared with 2 degrees of freedom
            # (mean = 1; variance = 1 → moderate fluctuation)
            rcs_corrected = rcs_raw * random.expovariate(1.0)
            rcs_corrected = max(0.001, rcs_corrected)

            # Find closest RCS reference match
            best_type  = "UNKNOWN"
            best_delta = float("inf")
            for ttype, ref_rcs in _RCS_REFERENCE.items():
                delta = abs(math.log10(max(rcs_corrected, 0.001)) -
                            math.log10(max(ref_rcs, 0.001)))
                if delta < best_delta:
                    best_delta = delta
                    best_type  = ttype

            # Confidence: inversely proportional to log-RCS mismatch
            confidence = max(0.2, min(0.95, 1.0 - best_delta / 3.0))

            # Override with speed-based hints
            if speed > 500:
                best_type = "MISSILE"
            elif speed > 250 and alt_m > 5000:
                best_type = "FIGHTER"
            elif alt_m > 15000:
                best_type = "HIGH_ALT"

            model = _SWERLING_MODELS.get(best_type, "SWERLING_1")

            report = SignatureReport(
                track_id            = track_id,
                rcs_measured        = rcs_corrected,
                rcs_model           = model,
                signature_class     = best_type,
                confidence          = confidence,
                stealth_flag        = False,    # set by StealthDetector
                stealth_probability = 0.0,
                timestamp           = time.time(),
            )
            self._reports[track_id] = report

            # Enrich track dict
            track["rcs_model"]           = model
            track["signature_class"]     = best_type
            track["detection_confidence"]= confidence
            track["classification"]      = best_type

            return track

        except Exception as exc:
            logger.error(f"[SIG_ANALYSER] Error analysing track {track_id}: {exc}")
            return track

    def get_report(self, track_id: int) -> Optional[SignatureReport]:
        return self._reports.get(track_id)


class StealthDetector:
    """
    Enhanced detection processing for low-observable targets.

    A stealth aircraft has a very small RCS (< 0.1 m²) and may fly
    unusual trajectories.  This detector:

      1. Flags tracks with RCS below the stealth threshold.
      2. Applies a non-coherent integration boost (n-pulse integration
         gives ~√n SNR improvement) to increase detectability.
      3. Computes a stealth probability using Bayesian update across
         successive detections.

    The `is_stealth` flag already exists on AEWC tracks; this detector
    provides the equivalent logic for the targeting radar.
    """

    _PRIOR_STEALTH = 0.05       # a priori probability (5 % of all contacts)
    _MIN_PULSES    = 8          # pulses for non-coherent integration

    def __init__(self):
        self._stealth_probs: Dict[int, float] = {}   # track_id → P(stealth)
        self._hit_counts:    Dict[int, int]   = {}   # track_id → consecutive detections

    def assess(self, track_id: int, track: Dict,
               sig_report: Optional[SignatureReport] = None) -> Dict:
        """
        Assess a track for stealth characteristics and update the track dict.

        Args:
            track_id   : integer track identifier
            track      : track dict (modified in-place)
            sig_report : optional SignatureReport from SignatureAnalyzer

        Returns:
            Enriched track dict.
        """
        try:
            rcs = sig_report.rcs_measured if sig_report else float(track.get("rcs", 5.0))
            snr = float(track.get("snr", 15.0))

            # Non-coherent integration: SNR gain ≈ √n for n pulses
            n_pulses = max(self._MIN_PULSES,
                           self._hit_counts.get(track_id, 0) + 1)
            snr_integrated = snr + 10 * math.log10(math.sqrt(n_pulses))

            # Likelihood ratio: P(low RCS | stealth) / P(low RCS | non-stealth)
            if rcs < _STEALTH_RCS_THRESHOLD_M2:
                # RCS consistent with stealth → update toward P=1
                likelihood_ratio = 8.0
            elif rcs < 0.5:
                likelihood_ratio = 2.0
            else:
                # High RCS → unlikely stealth
                likelihood_ratio = 0.2

            # Bayesian update
            prior = self._stealth_probs.get(track_id, self._PRIOR_STEALTH)
            posterior = (prior * likelihood_ratio /
                         (prior * likelihood_ratio + (1 - prior)))
            posterior = max(0.01, min(0.99, posterior))

            self._stealth_probs[track_id] = posterior
            self._hit_counts[track_id]    = n_pulses

            is_stealth = posterior > 0.6 and rcs < _STEALTH_RCS_THRESHOLD_M2

            # Update track
            track["stealth_flag"]        = is_stealth
            track["stealth_prob"]        = round(posterior, 3)
            track["snr_integrated"]      = round(snr_integrated, 1)
            track["is_stealth"]          = is_stealth

            if is_stealth:
                logger.info(
                    f"[STEALTH_DETECT] Track {track_id}: "
                    f"P(stealth)={posterior:.2f}  RCS={rcs:.4f} m²"
                )

            # Feed back into signature report
            if sig_report:
                sig_report.stealth_flag        = is_stealth
                sig_report.stealth_probability = posterior

            return track

        except Exception as exc:
            logger.error(f"[STEALTH_DETECT] Error assessing track {track_id}: {exc}")
            return track

    def clear_track(self, track_id: int) -> None:
        """Remove a dropped track from internal state."""
        self._stealth_probs.pop(track_id, None)
        self._hit_counts.pop(track_id, None)


class TargetProcessor:
    """
    Composite processor bundling SignatureAnalyzer + StealthDetector.

    Called once per targeting radar update cycle for each active track.
    """

    def __init__(self):
        self.signature_analyzer = SignatureAnalyzer()
        self.stealth_detector   = StealthDetector()

    def process_tracks(self, targets: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        Process all active tracks and return the enriched dict.

        Args:
            targets : {track_id: track_dict} from targeting_radar.current_targets

        Returns:
            Same dict with signature / stealth fields added to each track.
        """
        for track_id, track in targets.items():
            try:
                self.signature_analyzer.analyse(track_id, track)
                sig_report = self.signature_analyzer.get_report(track_id)
                self.stealth_detector.assess(track_id, track, sig_report)
            except Exception as exc:
                logger.error(f"[TARGET_PROC] Error on track {track_id}: {exc}")

        # Clean up stale stealth state for tracks no longer present
        active_ids = set(targets.keys())
        for old_id in (set(self.stealth_detector._stealth_probs) - active_ids):
            self.stealth_detector.clear_track(old_id)

        return targets
