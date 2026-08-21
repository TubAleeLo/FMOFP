"""
SAR Processor — Synthetic Aperture Radar

Implements change detection between successive SAR imagery frames.

PLANNING.md §2.1 lists `change_detection.py` under sar_capabilities.
This processor provides that capability as a single class that the SAR
radar calls on each new imagery frame.

Algorithm (Constant False Alarm Rate change detection)
------------------------------------------------------
  1. Store the previous frame (reference image).
  2. Compute the log-ratio image: L = log(I_new) − log(I_ref).
  3. Threshold |L| at a CFAR level derived from the local mean + k·σ.
  4. Morphologically clean the binary change mask (remove isolated pixels).
  5. Label connected components as individual change regions.
  6. Report each region as a ChangeEvent.

The log-ratio is used rather than simple subtraction because SAR imagery
has multiplicative (speckle) noise whose statistics are better handled
in the log domain.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
try:
    from scipy import ndimage
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    ndimage = None  # type: ignore[assignment]
    _SCIPY_AVAILABLE = False

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


@dataclass
class ChangeEvent:
    """A detected change region between two SAR frames."""
    event_id:       int
    centroid_px:    Tuple[int, int]       # (row, col) in image pixels
    area_px:        int                   # number of changed pixels
    log_ratio_mean: float                 # mean log-ratio (magnitude of change)
    change_type:    str                   # "ADDITION" | "REMOVAL" | "CHANGE"
    confidence:     float                 # 0-1
    timestamp:      float = field(default_factory=time.time)

    @property
    def is_significant(self) -> bool:
        return self.area_px > 50 and self.confidence > 0.6


class ChangeDetector:
    """
    Frame-differencing change detector for SAR imagery.

    Usage
    -----
    detector = ChangeDetector()
    events = detector.process(new_image)   # first call stores reference
    events = detector.process(next_image)  # subsequent calls detect change
    """

    # CFAR parameters
    CFAR_K          = 3.0    # threshold = mean + k·std in local window
    CFAR_WINDOW     = 11     # local statistics window size (pixels)
    MIN_AREA_PX     = 10     # smallest reportable change region
    LOG_FLOOR       = 1.0    # floor value before log (avoid log(0))
    MAX_EVENTS      = 32     # cap reported events per frame

    def __init__(self):
        self._reference: Optional[np.ndarray] = None
        self._next_id = 1

    def process(self, image: np.ndarray) -> List[ChangeEvent]:
        """
        Detect changes between `image` and the stored reference frame.

        On the first call the image is stored as the reference and an
        empty list is returned.

        Args:
            image : 2-D uint8 array (H × W), SAR backscatter intensity

        Returns:
            List of ChangeEvent objects
        """
        try:
            if image is None or image.size == 0:
                return []

            img = image.astype(float)

            if self._reference is None:
                self._reference = img.copy()
                logger.debug("[SAR_PROC] Reference frame stored")
                return []

            # Align sizes (take minimum)
            min_h = min(img.shape[0], self._reference.shape[0])
            min_w = min(img.shape[1], self._reference.shape[1])
            ref = self._reference[:min_h, :min_w]
            cur = img[:min_h, :min_w]

            # Log-ratio image (floor avoids log(0))
            log_ratio = np.log(np.maximum(cur, self.LOG_FLOOR)) - \
                        np.log(np.maximum(ref, self.LOG_FLOOR))
            log_abs   = np.abs(log_ratio)

            if not _SCIPY_AVAILABLE or ndimage is None:
                logger.warning("[SAR_PROC] scipy unavailable; change detection skipped")
                return []
            local_mean = ndimage.uniform_filter(log_abs, size=self.CFAR_WINDOW)
            local_sq   = ndimage.uniform_filter(log_abs**2, size=self.CFAR_WINDOW)
            local_std  = np.sqrt(np.maximum(0, local_sq - local_mean**2))
            threshold  = local_mean + self.CFAR_K * local_std

            # Binary change mask
            change_mask = log_abs > threshold

            # Morphological cleaning: remove isolated pixels
            change_mask = ndimage.binary_opening(change_mask, iterations=1)
            change_mask = ndimage.binary_closing(change_mask, iterations=1)

            # Label connected components
            labeled, n_components = ndimage.label(change_mask)

            events: List[ChangeEvent] = []
            for label_id in range(1, min(n_components + 1,
                                         self.MAX_EVENTS + 1)):
                region_mask = labeled == label_id
                area = int(np.sum(region_mask))
                if area < self.MIN_AREA_PX:
                    continue

                # Centroid
                coords = np.argwhere(region_mask)
                # Explicit 2-tuple to satisfy Tuple[int, int]
                centroid: Tuple[int, int] = (
                    int(coords[:, 0].mean()),
                    int(coords[:, 1].mean()),
                )

                # Mean log-ratio in region
                lr_mean = float(np.mean(log_ratio[region_mask]))
                lr_abs  = abs(lr_mean)

                # Change type: positive log-ratio → new bright target (addition)
                if lr_mean > 0.3:
                    change_type = "ADDITION"
                elif lr_mean < -0.3:
                    change_type = "REMOVAL"
                else:
                    change_type = "CHANGE"

                # Confidence: larger area and higher ratio → more confident
                confidence = min(0.95, 0.5 + lr_abs * 0.3 +
                                       math.log10(max(area, 1)) * 0.05)

                events.append(ChangeEvent(
                    event_id      = self._next_id,
                    centroid_px   = centroid,
                    area_px       = area,
                    log_ratio_mean = lr_mean,
                    change_type   = change_type,
                    confidence    = confidence,
                ))
                self._next_id += 1

            # Update reference
            self._reference = img.copy()

            sig = [e for e in events if e.is_significant]
            if sig:
                logger.info(
                    f"[SAR_PROC] {len(sig)} significant change(s) detected "
                    f"({len(events)} total regions)"
                )
            return events

        except Exception as exc:
            logger.error(f"[SAR_PROC] Change detection error: {exc}")
            return []

    def reset_reference(self) -> None:
        """Force a reference frame reset (call on mode change)."""
        self._reference = None

    @property
    def has_reference(self) -> bool:
        return self._reference is not None
