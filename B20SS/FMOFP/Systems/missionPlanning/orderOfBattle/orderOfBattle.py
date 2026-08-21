import sys
import math
import threading
import xml.etree.ElementTree as ET
import FMOFP.Utils.common.fetching as fetching
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class Unit:
    def __init__(self, id, type, affiliation, position, capabilities,
                 threat_level: int = 0, speed_kts: float = 0.0,
                 heading_deg: float = 0.0):
        self.id           = id
        self.type         = type
        self.affiliation  = affiliation   # 'Friendly' | 'Enemy' | 'Neutral'
        self.position     = position      # (lat, lon, alt_ft)
        self.capabilities = capabilities
        self.status       = "Operational"
        self.threat_level = threat_level  # 0-5
        self.speed_kts    = speed_kts
        self.heading_deg  = heading_deg

    def to_dict(self):
        return {
            'id':           self.id,
            'type':         self.type,
            'affiliation':  self.affiliation,
            'position':     self.position,
            'capabilities': self.capabilities,
            'status':       self.status,
            'threat_level': self.threat_level,
            'speed_kts':    self.speed_kts,
            'heading_deg':  self.heading_deg,
        }


class OrderOfBattle:
    def __init__(self):
        self._lock          = threading.Lock()
        self.friendly_forces: dict = {}
        self.enemy_forces:    dict = {}
        self.neutral_forces:  dict = {}

    def _all_forces(self):
        return [self.friendly_forces, self.enemy_forces, self.neutral_forces]

    def _find_unit(self, unit_id):
        for force in self._all_forces():
            if unit_id in force:
                return force[unit_id], force
        return None, None

    def add_unit(self, unit):
        af = (unit.affiliation or '').lower()
        with self._lock:
            if af in ('friendly', 'friend'):
                self.friendly_forces[unit.id] = unit
            elif af == 'enemy':
                self.enemy_forces[unit.id] = unit
            elif af == 'neutral':
                self.neutral_forces[unit.id] = unit
            else:
                logger.warning(f"[OOB] Unknown affiliation '{unit.affiliation}' for unit {unit.id}")
                self.neutral_forces[unit.id] = unit
        logger.info(f"[OOB] Added {unit.affiliation} unit {unit.id} ({unit.type})")

    def remove_unit(self, unit_id):
        with self._lock:
            for force in self._all_forces():
                if unit_id in force:
                    del force[unit_id]
                    logger.info(f"[OOB] Removed unit {unit_id}")
                    return True
        logger.warning(f"[OOB] Unit {unit_id} not found")
        return False

    def update_unit_position(self, unit_id, new_position):
        with self._lock:
            unit, _ = self._find_unit(unit_id)
            if unit:
                unit.position = new_position
                return True
        logger.warning(f"[OOB] Unit {unit_id} not found")
        return False

    def update_unit_status(self, unit_id, new_status):
        return self.update_status(unit_id, new_status)

    def update_status(self, unit_id: str, status: str) -> bool:
        with self._lock:
            unit, _ = self._find_unit(unit_id)
            if unit:
                unit.status = status
                logger.info(f"[OOB] {unit_id} status → {status}")
                return True
        logger.warning(f"[OOB] Unit {unit_id} not found")
        return False

    def update_heading_speed(self, unit_id: str, heading: float, speed: float) -> bool:
        with self._lock:
            unit, _ = self._find_unit(unit_id)
            if unit:
                unit.heading_deg = heading
                unit.speed_kts   = speed
                return True
        return False

    def get_unit_info(self, unit_id):
        with self._lock:
            unit, _ = self._find_unit(unit_id)
            return unit.to_dict() if unit else None

    def get_all_units(self):
        with self._lock:
            result = []
            for force in self._all_forces():
                result.extend(u.to_dict() for u in force.values())
            return result

    def get_by_affiliation(self, affiliation: str):
        af = affiliation.lower()
        with self._lock:
            if af in ('friendly', 'friend'):
                return [u.to_dict() for u in self.friendly_forces.values()]
            elif af == 'enemy':
                return [u.to_dict() for u in self.enemy_forces.values()]
            elif af == 'neutral':
                return [u.to_dict() for u in self.neutral_forces.values()]
        return []

    def get_threats(self, min_level: int = 1):
        """Return enemy units at or above min threat_level."""
        with self._lock:
            return [u.to_dict() for u in self.enemy_forces.values()
                    if u.threat_level >= min_level]

    def summary(self):
        with self._lock:
            return {
                'FRIENDLY': len(self.friendly_forces),
                'ENEMY':     len(self.enemy_forces),
                'NEUTRAL':   len(self.neutral_forces),
            }

    def get_forces_in_area(self, center, radius):
        """Return all units within Euclidean radius (degrees) of center (lat,lon,alt)."""
        forces = []
        with self._lock:
            for force in self._all_forces():
                for unit in force.values():
                    pos = unit.position
                    dist = math.sqrt(
                        (pos[0] - center[0]) ** 2 +
                        (pos[1] - center[1]) ** 2 +
                        (pos[2] - center[2]) ** 2 if len(pos) > 2 else 0
                    )
                    if dist <= radius:
                        forces.append(unit.to_dict())
        return forces

    def handle_message(self, message):
        msg_type = message.get("type")
        if msg_type == "add_unit":
            unit = Unit(**message.get("unit_data"))
            self.add_unit(unit)
        elif msg_type == "remove_unit":
            return self.remove_unit(message.get("unit_id"))
        elif msg_type == "update_unit_position":
            return self.update_unit_position(message.get("unit_id"), message.get("new_position"))
        elif msg_type == "update_unit_status":
            return self.update_status(message.get("unit_id"), message.get("new_status"))
        elif msg_type == "get_unit_info":
            return self.get_unit_info(message.get("unit_id"))
        elif msg_type == "get_forces_in_area":
            return self.get_forces_in_area(message.get("center"), message.get("radius"))

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
    oob = OrderOfBattle()
    f = Unit("F001", "Fighter", "Friendly", (34.0522, -118.2437, 10000), ["Air-to-Air"])
    e = Unit("E001", "SAM Site", "Enemy",   (34.0522, -118.2437, 0),     ["SAM"], threat_level=4)
    oob.add_unit(f)
    oob.add_unit(e)
    logger.info(oob.summary())
    logger.info(oob.get_threats(min_level=1))
