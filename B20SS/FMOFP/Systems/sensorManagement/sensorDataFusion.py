"""
Sensor Data Fusion

Fuses contacts from the active sensor suite (Radar, LIDAR) and passive sensor
suite (IR, ESM) into a unified SensorContact list.

Design:
  - ActiveSensorManager.scan() returns raw detection dicts
  - PassiveSensorManager.detect() returns raw signal/detection dicts
  - SensorDataFusion normalises both into SensorContact objects with a
    common schema, then de-duplicates contacts that appear in multiple sensors
    using a simple spatial proximity gate
  - The fused contact list is stored with a TTL so stale contacts expire

Consumed by:
  - SensorService._update() (replaces its direct active/passive calls)
  - DefensiveService._update_rwr() (supplements RadarDataFusion ESM data)

Singleton: get_sensor_data_fusion()
"""

import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_sensor_data_fusion = None


# ── Contact types ─────────────────────────────────────────────────────────────

class SensorSource(str, Enum):
    RADAR  = "RADAR"
    LIDAR  = "LIDAR"
    IR     = "IR"
    ESM    = "ESM"
    FUSED  = "FUSED"   # contact confirmed by 2+ sensors


class ContactClass(str, Enum):
    AIR     = "AIR"
    GROUND  = "GROUND"
    SURFACE = "SURFACE"
    EMITTER = "EMITTER"   # ESM-only — RF emitter, no kinematic data
    UNKNOWN = "UNKNOWN"


@dataclass
class SensorContact:
    contact_id:   str
    source:       SensorSource
    contact_class: ContactClass  = ContactClass.UNKNOWN

    # Kinematic (may be None for ESM-only contacts)
    range_m:      Optional[float] = None    # metres
    bearing_deg:  Optional[float] = None    # 0–360
    elevation_deg: Optional[float] = None  # +up / -down
    speed_ms:     Optional[float] = None

    # ESM-specific
    frequency_hz: Optional[float] = None
    signal_dbm:   Optional[float] = None
    band:         Optional[str]   = None

    # Meta
    confidence:   float = 1.0              # 0–1
    first_seen:   float = field(default_factory=time.time)
    last_seen:    float = field(default_factory=time.time)
    corroborated_by: List[str] = field(default_factory=list)  # other source names

    def to_dict(self) -> Dict:
        return {
            "contact_id":    self.contact_id,
            "source":        self.source.value,
            "class":         self.contact_class.value,
            "range_m":       round(self.range_m, 1)    if self.range_m    is not None else None,
            "bearing_deg":   round(self.bearing_deg, 1) if self.bearing_deg is not None else None,
            "elevation_deg": round(self.elevation_deg, 1) if self.elevation_deg is not None else None,
            "speed_ms":      round(self.speed_ms, 1)   if self.speed_ms   is not None else None,
            "frequency_hz":  self.frequency_hz,
            "signal_dbm":    self.signal_dbm,
            "band":          self.band,
            "confidence":    round(self.confidence, 2),
            "last_seen":     self.last_seen,
            "corroborated_by": self.corroborated_by,
        }


# ── Band classification (mirrors DefensiveService) ────────────────────────────

_BAND_MAP: List[Tuple[float, float, str]] = [
    (0.5e9,  2e9,  "L"),
    (2e9,    4e9,  "S"),
    (4e9,    8e9,  "C"),
    (8e9,   12e9,  "X"),
    (12e9,  18e9,  "Ku"),
    (18e9,  27e9,  "K"),
    (27e9,  40e9,  "Ka"),
]


def _classify_band(freq_hz: float) -> str:
    for lo, hi, name in _BAND_MAP:
        if lo <= freq_hz < hi:
            return name
    return "?"


# ── Proximity gate ────────────────────────────────────────────────────────────

_GATE_DEG = 5.0   # contacts within 5° bearing are considered the same target


def _bearing_delta(a: Optional[float], b: Optional[float]) -> float:
    if a is None or b is None:
        return 360.0
    delta = abs(a - b) % 360
    return min(delta, 360 - delta)


# ── Fusion engine ─────────────────────────────────────────────────────────────

class SensorDataFusion:
    """
    Ingests raw sensor reads from active and passive managers, normalises them
    into SensorContact objects, de-duplicates by bearing gate, and ages out
    stale contacts.
    """

    CONTACT_TTL_S = 8.0    # seconds before a contact is dropped
    POLL_HZ       = 5      # update rate in Hz

    def __init__(self):
        self._lock     = threading.Lock()
        self._contacts: Dict[str, SensorContact] = {}
        self._seq      = 0              # contact ID sequence counter

        self._active  = None   # lazy: ActiveSensorManager
        self._passive = None   # lazy: PassiveSensorManager

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _load_managers(self):
        # Previously rebuilt via object.__new__() + a hand-duplicated sensor
        # dict (same pattern fixed in sensorService.py -- see that file's
        # comment). Both managers instantiate cleanly through their normal
        # constructors; using those directly avoids drift from the real
        # sensor definitions in activeSensors.py/passiveSensors.py
        # (production readiness punch list, item 3 audit).
        if self._active is None:
            try:
                from FMOFP.Systems.sensorManagement.activeSensors.activeSensors import (
                    ActiveSensorManager,
                )
                mgr = ActiveSensorManager()
                for s in mgr.sensors.values():
                    s.activate()
                self._active = mgr
            except Exception as exc:
                logger.debug(f"[SDF] ActiveSensorManager unavailable: {exc}")

        if self._passive is None:
            try:
                from FMOFP.Systems.sensorManagement.passiveSensors.passiveSensors import (
                    PassiveSensorManager,
                )
                mgr = PassiveSensorManager()
                for s in mgr.sensors.values():
                    s.activate()
                self._passive = mgr
            except Exception as exc:
                logger.debug(f"[SDF] PassiveSensorManager unavailable: {exc}")

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self):
        """Ingest latest sensor reads, fuse, and expire stale contacts."""
        self._load_managers()
        self._ingest_active()
        self._ingest_passive()
        self._expire_stale()

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:04d}"

    def _ingest_active(self):
        if self._active is None:
            return

        for sensor_name, sensor in self._active.sensors.items():
            if not sensor.is_active:
                continue
            try:
                raw = sensor.scan()
            except Exception:
                continue
            if not raw:
                continue

            source = SensorSource.RADAR if "radar" in sensor_name else SensorSource.LIDAR

            for det in raw:
                bearing  = det.get("angle")
                range_m  = det.get("distance")
                speed_ms = det.get("speed", 0.0)
                elev     = det.get("elevation")

                # Classify by elevation
                if elev is not None:
                    cls = ContactClass.AIR if elev > 2 else ContactClass.GROUND
                else:
                    cls = ContactClass.UNKNOWN

                self._merge_or_add(SensorContact(
                    contact_id    = self._next_id(source.value[:3]),
                    source        = source,
                    contact_class = cls,
                    range_m       = range_m,
                    bearing_deg   = bearing,
                    elevation_deg = elev,
                    speed_ms      = speed_ms,
                    confidence    = sensor.accuracy,
                ))

    def _ingest_passive(self):
        if self._passive is None:
            return

        for sensor_name, sensor in self._passive.sensors.items():
            if not sensor.is_active:
                continue
            try:
                raw = sensor.detect()
            except Exception:
                continue
            if not raw:
                continue

            for det in raw:
                if "frequency" in det:
                    # ESM signal
                    freq  = det.get("frequency", 10e9)
                    band  = _classify_band(freq)
                    c = SensorContact(
                        contact_id    = self._next_id("ESM"),
                        source        = SensorSource.ESM,
                        contact_class = ContactClass.EMITTER,
                        bearing_deg   = det.get("bearing"),
                        frequency_hz  = freq,
                        signal_dbm    = det.get("signal_strength"),
                        band          = band,
                        confidence    = 0.7,
                    )
                else:
                    # IR detection
                    bearing = det.get("angle")
                    range_m = det.get("distance")
                    c = SensorContact(
                        contact_id    = self._next_id("IR"),
                        source        = SensorSource.IR,
                        contact_class = ContactClass.AIR,
                        range_m       = range_m,
                        bearing_deg   = bearing,
                        confidence    = 0.6,
                    )

                self._merge_or_add(c)

    def _merge_or_add(self, new: SensorContact):
        """Gate-merge new contact into existing table or add as new entry."""
        now = time.time()
        with self._lock:
            for existing in self._contacts.values():
                if _bearing_delta(existing.bearing_deg, new.bearing_deg) < _GATE_DEG:
                    # Same target — update and corroborate
                    existing.last_seen = now
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                    src_name = new.source.value
                    if src_name not in existing.corroborated_by:
                        existing.corroborated_by.append(src_name)
                    if len(existing.corroborated_by) >= 2:
                        existing.source = SensorSource.FUSED
                    # Update kinematics if the new reading has them and existing doesn't
                    if existing.range_m is None and new.range_m is not None:
                        existing.range_m = new.range_m
                    if existing.speed_ms is None and new.speed_ms is not None:
                        existing.speed_ms = new.speed_ms
                    if existing.frequency_hz is None and new.frequency_hz is not None:
                        existing.frequency_hz  = new.frequency_hz
                        existing.signal_dbm    = new.signal_dbm
                        existing.band          = new.band
                    return

            # No match — insert as new
            self._contacts[new.contact_id] = new

    def _expire_stale(self):
        now = time.time()
        with self._lock:
            stale = [cid for cid, c in self._contacts.items()
                     if now - c.last_seen > self.CONTACT_TTL_S]
            for cid in stale:
                del self._contacts[cid]

    # ── Public API ────────────────────────────────────────────────────────────

    def get_contacts(self) -> List[Dict]:
        """Return all current fused contacts as dicts."""
        with self._lock:
            return [c.to_dict() for c in self._contacts.values()]

    def get_contacts_by_source(self, source: SensorSource) -> List[Dict]:
        with self._lock:
            return [c.to_dict() for c in self._contacts.values()
                    if c.source == source]

    def get_contact_count(self) -> int:
        with self._lock:
            return len(self._contacts)

    def get_summary(self) -> Dict:
        with self._lock:
            counts: Dict[str, int] = {}
            for c in self._contacts.values():
                counts[c.contact_class.value] = counts.get(c.contact_class.value, 0) + 1
        return {
            "total":   sum(counts.values()),
            "by_class": counts,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_fusion_lock = threading.Lock()


def get_sensor_data_fusion() -> SensorDataFusion:
    global _sensor_data_fusion
    with _fusion_lock:
        if _sensor_data_fusion is None:
            _sensor_data_fusion = SensorDataFusion()
    return _sensor_data_fusion
