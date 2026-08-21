import sys
import random
import math
import time
import threading
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class TargetStatus:
    DESIGNATED  = 'DESIGNATED'
    ACQUIRED    = 'ACQUIRED'
    TRACKING    = 'TRACKING'
    ENGAGED     = 'ENGAGED'
    BDA_PENDING = 'BDA_PENDING'
    DESTROYED   = 'DESTROYED'
    LOST        = 'LOST'


class Target:
    def __init__(self, id, type, position, priority):
        self.id            = id
        self.type          = type
        self.position      = position
        self.priority      = priority
        self.status        = TargetStatus.DESIGNATED
        self.track_quality = 0.0
        self.weapon_system = None
        self.last_updated  = time.time()
        self.first_seen    = time.time()
        self.speed_kts     = 0.0
        self.heading_deg   = 0.0

    def to_dict(self):
        return {
            'id':            self.id,
            'type':          self.type,
            'position':      self.position,
            'priority':      self.priority,
            'status':        self.status,
            'track_quality': round(self.track_quality, 2),
            'weapon_system': self.weapon_system,
            'speed_kts':     self.speed_kts,
            'heading_deg':   self.heading_deg,
            'name':          str(self.id),
            'lat':           self.position[0] if self.position else 0,
            'lon':           self.position[1] if self.position else 0,
            'alt_ft':        self.position[2] if self.position and len(self.position) > 2 else 0,
        }


class Targeting:
    _TRACK_DECAY_S = 30.0

    def __init__(self):
        self._lock = threading.Lock()
        self.targets: dict = {}
        self.engaged_targets: dict = {}

    def add_target(self, target):
        with self._lock:
            self.targets[target.id] = target
        logger.info(f"[TARGETING] Added target {target.id} ({target.type})")

    def remove_target(self, target_id):
        with self._lock:
            if target_id in self.targets:
                del self.targets[target_id]
                self.engaged_targets.pop(target_id, None)
                logger.info(f"[TARGETING] Removed target {target_id}")
                return True
        logger.warning(f"[TARGETING] Target {target_id} not found")
        return False

    def prioritize_targets(self):
        with self._lock:
            return sorted(self.targets.values(), key=lambda t: t.priority, reverse=True)

    def acquire_target(self, target_id):
        """Alias for acquire() — maintains backward compat."""
        return self.acquire(target_id)

    def acquire(self, target_id) -> bool:
        with self._lock:
            t = self.targets.get(target_id)
            if t and t.status == TargetStatus.DESIGNATED:
                t.status        = TargetStatus.ACQUIRED
                t.track_quality = 0.5
                t.last_updated  = time.time()
                logger.info(f"[TARGETING] Acquired {target_id}")
                return True
        logger.warning(f"[TARGETING] Cannot acquire {target_id}")
        return False

    def track_target(self, target_id):
        with self._lock:
            t = self.targets.get(target_id)
            if t:
                t.position = (
                    t.position[0] + random.uniform(-0.001, 0.001),
                    t.position[1] + random.uniform(-0.001, 0.001),
                    t.position[2] + random.uniform(-10, 10),
                )
                return t.position
        logger.warning(f"[TARGETING] Target {target_id} not found")
        return None

    def engage_target(self, target_id, weapon_system):
        with self._lock:
            t = self.targets.get(target_id)
            if t and t.status in (TargetStatus.ACQUIRED, TargetStatus.TRACKING):
                t.status        = TargetStatus.ENGAGED
                t.weapon_system = weapon_system
                self.engaged_targets[target_id] = weapon_system
                logger.info(f"[TARGETING] Engaged {target_id} with {weapon_system}")
                return True
        logger.warning(f"[TARGETING] Cannot engage {target_id}")
        return False

    def disengage_target(self, target_id):
        with self._lock:
            t = self.targets.get(target_id)
            if t and target_id in self.engaged_targets:
                t.status        = TargetStatus.TRACKING
                t.weapon_system = None
                del self.engaged_targets[target_id]
                logger.info(f"[TARGETING] Disengaged {target_id}")
                return True
        logger.warning(f"[TARGETING] {target_id} was not engaged")
        return False

    def mark_bda_pending(self, target_id: str) -> bool:
        with self._lock:
            t = self.targets.get(target_id)
            if t and t.status == TargetStatus.ENGAGED:
                t.status = TargetStatus.BDA_PENDING
                return True
        return False

    def assess_damage(self, target_id: str, destroyed: bool) -> bool:
        with self._lock:
            t = self.targets.get(target_id)
            if t and t.status == TargetStatus.BDA_PENDING:
                t.status = TargetStatus.DESTROYED if destroyed else TargetStatus.ACQUIRED
                logger.info(f"[TARGETING] BDA {target_id}: {'DESTROYED' if destroyed else 'SURVIVED'}")
                return True
        return False

    def update_from_radar(self, target_id: str, lat: float, lon: float,
                          alt_ft: float, speed_kts: float = 0.0,
                          heading_deg: float = 0.0,
                          track_quality: float = 0.8) -> bool:
        with self._lock:
            t = self.targets.get(target_id)
            if t is None:
                return False
            t.position      = (lat, lon, alt_ft)
            t.speed_kts     = speed_kts
            t.heading_deg   = heading_deg
            t.track_quality = min(1.0, track_quality)
            t.last_updated  = time.time()
            if t.status == TargetStatus.DESIGNATED:
                t.status = TargetStatus.ACQUIRED
            elif t.status == TargetStatus.ACQUIRED:
                t.status = TargetStatus.TRACKING
        return True

    def simulate_tick(self) -> None:
        """Decay stale track quality. Called once per update cycle."""
        now = time.time()
        with self._lock:
            for t in self.targets.values():
                stale = now - t.last_updated
                if stale > 0:
                    t.track_quality = max(0.0,
                        t.track_quality - (stale / self._TRACK_DECAY_S) * 0.05)
                    if (t.track_quality < 0.1
                            and t.status == TargetStatus.TRACKING):
                        t.status = TargetStatus.LOST
                        logger.warning(f"[TARGETING] Track lost: {t.id}")

    def get_target_status(self, target_id):
        with self._lock:
            t = self.targets.get(target_id)
            return t.to_dict() if t else None

    def get_all(self):
        with self._lock:
            return [t.to_dict() for t in self.targets.values()]

    def get_prioritised(self):
        """Return active (non-destroyed/lost) targets sorted by priority then track quality."""
        with self._lock:
            active = [t for t in self.targets.values()
                      if t.status not in (TargetStatus.DESTROYED, TargetStatus.LOST)]
            return [t.to_dict() for t in sorted(
                active, key=lambda t: (t.priority, -t.track_quality))]

    def get_engaged(self):
        with self._lock:
            return [t.to_dict() for t in self.targets.values()
                    if t.status == TargetStatus.ENGAGED]

    def summary(self):
        with self._lock:
            counts: dict = {}
            for t in self.targets.values():
                counts[t.status] = counts.get(t.status, 0) + 1
        return counts

    def handle_message(self, message):
        msg_type = message.get("type")
        if msg_type == "add_target":
            target = Target(**message.get("target_data"))
            self.add_target(target)
        elif msg_type == "remove_target":
            return self.remove_target(message.get("target_id"))
        elif msg_type == "acquire_target":
            return self.acquire(message.get("target_id"))
        elif msg_type == "track_target":
            return self.track_target(message.get("target_id"))
        elif msg_type == "engage_target":
            return self.engage_target(message.get("target_id"), message.get("weapon_system"))
        elif msg_type == "disengage_target":
            return self.disengage_target(message.get("target_id"))
        elif msg_type == "get_target_status":
            return self.get_target_status(message.get("target_id"))

    def _dict_to_xml(self, tag, d):
        elem = ET.Element(tag)
        for key, val in d.items():
            child = ET.Element(key)
            child.text = str(val)
            elem.append(child)
        return ET.tostring(elem, encoding='unicode')

    def _xml_to_dict(self, xml_string):
        root = ET.fromstring(xml_string)
        return {child.tag: child.text for child in root}


# Example usage
if __name__ == "__main__":
    targeting = Targeting()
    target = Target("T001", "Ground", (34.0522, -118.2437, 0), 5)
    targeting.add_target(target)
    targeting.acquire("T001")
    logger.info(targeting.get_target_status("T001"))
