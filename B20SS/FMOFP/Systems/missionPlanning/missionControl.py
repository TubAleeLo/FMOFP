import math
import random
from enum import Enum
import threading
import time
from typing import List, Tuple, Dict
from typing import Union
import Utils.common.fetching as fetching
from FMOFP.storage.DBM import DatabaseManager
from FMOFP.MIL_STD_1553B.Messaging import ScheduleMessage
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class MissionPhase(Enum):
    PLANNING  = 1
    INGRESS   = 2
    OBJECTIVE = 3
    EGRESS    = 4
    COMPLETE  = 5

class Waypoint:
    def __init__(self, id: int, lat: float, lon: float, alt: float):
        self.id  = id
        self.lat = lat
        self.lon = lon
        self.alt = alt

class Target:
    def __init__(self, id: int, lat: float, lon: float, priority: int):
        self.id       = id
        self.lat      = lat
        self.lon      = lon
        self.priority = priority
        self.status   = "Pending"

class Threat:
    def __init__(self, id: int, lat: float, lon: float, threat_level: int):
        self.id           = id
        self.lat          = lat
        self.lon          = lon
        self.threat_level = threat_level

class MissionPlanningSystem:
    def __init__(self):
        self.phase            = MissionPhase.PLANNING
        self.waypoints:  List[Waypoint]      = []
        self.targets:    Dict[int, Target]   = {}
        self.threats:    Dict[int, Threat]   = {}
        self.current_position = (35.414750000000004, -97.3866388888889, 1290.6)
        # RLock, not Lock (added August 2026 re-analysis round, Round
        # 16, scenario/mission-planning state-machine race sweep):
        # optimize_route() calls self.assess_threats() internally on
        # the same thread, so a plain Lock would deadlock that self-call
        # once assess_threats() itself became lock-guarded below.
        self.lock             = threading.RLock()
        self.aircraft_speed   = 500  # km/h

        # DB is optional — failures are non-fatal
        self._db = None
        try:
            self._db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('mission_management_system')
        except Exception as e:
            logger.warning(f"[MPS] DB unavailable (non-fatal): {e}")

        try:
            from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
            self.message_handler = _MessageHandlerShim(get_message_routing_service())
        except Exception:
            self.message_handler = _MessageHandlerShim(None)

    def set_phase(self, phase: MissionPhase):
        with self.lock:
            self.phase = phase
            self._send_phase_update()

    def _send_phase_update(self):
        try:
            message = {'type': 'mission_phase_update', 'phase': self.phase.value}
            self.message_handler.send_mission_data(message)
        except Exception as e:
            logger.debug(f"[MPS] Phase update send failed: {e}")

    def add_waypoint(self, lat: float, lon: float, alt: float):
        with self.lock:
            wp_id   = len(self.waypoints) + 1
            waypoint = Waypoint(wp_id, lat, lon, alt)
            self.waypoints.append(waypoint)
            logger.info(f"[MPS] Added waypoint {wp_id}")

    def add_target(self, lat: float, lon: float, priority: int):
        with self.lock:
            t_id   = len(self.targets) + 1
            target = Target(t_id, lat, lon, priority)
            self.targets[t_id] = target
            logger.info(f"[MPS] Added target {t_id}")

    def add_threat(self, lat: float, lon: float, threat_level: int):
        with self.lock:
            th_id  = len(self.threats) + 1
            threat = Threat(th_id, lat, lon, threat_level)
            self.threats[th_id] = threat
            logger.info(f"[MPS] Added threat {th_id}")

    def update_current_position(self, lat: float, lon: float, alt: float):
        with self.lock:
            self.current_position = (lat, lon, alt)

    def get_next_waypoint(self) -> Waypoint:
        # Locked (Round 16): this previously read self.waypoints with no
        # lock at all, while add_waypoint() mutates it under self.lock --
        # reachable from a different thread in practice, since
        # MissionControl.tick() (called every cycle from missionService.py's
        # daemon MISSION_Update thread) calls this, while add_waypoint()
        # can be triggered reactively from an AsyncMessageHandler worker
        # thread processing an incoming add-waypoint message.
        with self.lock:
            if not self.waypoints:
                return None
            return min(self.waypoints, key=lambda w: self._calculate_distance(w))

    def _calculate_distance(self, point: Union[Waypoint, Target, Threat]) -> float:
        lat1, lon1, _ = self.current_position
        return math.sqrt((point.lat - lat1) ** 2 + (point.lon - lon1) ** 2)

    def calculate_eta(self, waypoint: Waypoint) -> float:
        return self._calculate_distance(waypoint) / self.aircraft_speed

    def update_target_status(self, target_id: int, status: str):
        with self.lock:
            if target_id in self.targets:
                self.targets[target_id].status = status
                logger.info(f"[MPS] Target {target_id} → {status}")

    def assess_threats(self):
        # Locked (Round 16): self.threats is mutated under self.lock
        # elsewhere; this iteration previously wasn't.
        with self.lock:
            assessment = {}
            for threat_id, threat in self.threats.items():
                dist = self._calculate_distance(threat)
                assessment[threat_id] = {
                    'distance':     dist,
                    'threat_level': threat.threat_level,
                    'risk_factor':  threat.threat_level / max(dist, 0.001),
                }
            return assessment

    def optimize_route(self):
        # Locked (Round 16, scenario/mission-planning state-machine race
        # sweep): previously ran with no lock at all, while add_waypoint()
        # mutates self.waypoints under self.lock from a different thread
        # in live operation (add_waypoint() reachable from an
        # AsyncMessageHandler worker thread; optimize_route()/
        # get_next_waypoint() reachable from missionService.py's daemon
        # MISSION_Update thread via MissionControl.tick()). Live-reproduced:
        # self.waypoints.sort() while a concurrent add_waypoint() was
        # appending to the same list raised "ValueError: list modified
        # during sort" on the first trial of a 2-thread stress test. Now
        # safe to call self.assess_threats() from within this lock because
        # self.lock is an RLock (see __init__).
        with self.lock:
            self.waypoints.sort(key=lambda w: self._calculate_distance(w))
            for t_id, target in sorted(self.targets.items(),
                                        key=lambda x: x[1].priority, reverse=True):
                insert_idx = next(
                    (i for i, w in enumerate(self.waypoints)
                     if self._calculate_distance(w) > self._calculate_distance(target)),
                    len(self.waypoints))
                self.waypoints.insert(insert_idx,
                    Waypoint(target.id, target.lat, target.lon, self.current_position[2]))
            threat_assessment = self.assess_threats()
            for i, wp in enumerate(self.waypoints):
                for th_id, assessment in threat_assessment.items():
                    if assessment['risk_factor'] > 0.5:
                        wp.lat += (wp.lat - self.threats[th_id].lat) * 0.1
                        wp.lon += (wp.lon - self.threats[th_id].lon) * 0.1
            logger.info("[MPS] Route optimised")

    def send_mission_update(self):
        try:
            nwp = self.get_next_waypoint()
            if nwp:
                message = {
                    'type': 'mission_update', 'phase': self.phase.value,
                    'next_waypoint': {'id': nwp.id, 'lat': nwp.lat,
                                      'lon': nwp.lon, 'alt': nwp.alt},
                    'eta': self.calculate_eta(nwp),
                }
                self.message_handler.send_mission_data(message)
        except Exception as e:
            logger.debug(f"[MPS] Mission update send failed: {e}")


class _MessageHandlerShim:
    """Thin shim so MissionPlanningSystem.message_handler calls don't crash."""
    def __init__(self, routing_service):
        self._rs = routing_service

    def send_mission_data(self, message):
        pass   # no-op — routing happens through MissionService / MissionMessageHandler


# ── MissionControl ────────────────────────────────────────────────────────────
# New coordinator class that owns RouteManager, TargetingSystem, OrderOfBattle,
# and MissionData. Used by MissionService._ctrl.

class MissionControl:
    """
    Top-level mission planning coordinator.
    Owns: route (RouteManager), targeting (Targeting), oob (OrderOfBattle).
    MissionService exposes its API; MissionMessageHandler reaches through _ctrl.
    """

    def __init__(self):
        from FMOFP.Systems.missionPlanning.routeManagement.handleRoute import RouteManager
        from FMOFP.Systems.missionPlanning.targeting.targeting import Targeting
        from FMOFP.Systems.missionPlanning.orderOfBattle.orderOfBattle import OrderOfBattle

        self._lock    = threading.Lock()
        self.route    = RouteManager()
        self.targeting = Targeting()
        self.oob       = OrderOfBattle()

        self._phase        = 'PLANNING'
        self._objectives:  List[str] = []
        self._roe:         List[str] = []
        self._intelligence: dict     = {}

        logger.info("[MISSION_CTRL] MissionControl initialised")

    # ── Phase ──────────────────────────────────────────────────────────────────

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    def set_phase(self, phase: str) -> None:
        valid = ('PLANNING', 'INGRESS', 'OBJECTIVE', 'EGRESS', 'COMPLETE')
        phase_up = phase.upper()
        if phase_up in valid:
            with self._lock:
                self._phase = phase_up
            logger.info(f"[MISSION_CTRL] Phase → {phase_up}")

    def advance_phase(self) -> str:
        order = ['PLANNING', 'INGRESS', 'OBJECTIVE', 'EGRESS', 'COMPLETE']
        with self._lock:
            try:
                idx = order.index(self._phase)
            except ValueError:
                idx = 0
            if idx < len(order) - 1:
                self._phase = order[idx + 1]
            new_phase = self._phase
        logger.info(f"[MISSION_CTRL] Phase advanced → {new_phase}")
        return new_phase

    # ── Per-tick ──────────────────────────────────────────────────────────────

    def tick(self, lat: float, lon: float, alt_ft: float,
             groundspeed_kts: float = 450.0) -> None:
        self.route.update_position(lat, lon, alt_ft, groundspeed_kts)
        self.targeting.simulate_tick()

    # ── Route delegation ──────────────────────────────────────────────────────

    def update_unit_position(self, unit_id: str, lat: float, lon: float,
                              alt_ft: float) -> bool:
        return self.oob.update_unit_position(unit_id, (lat, lon, alt_ft))

    def optimise_route_for_threats(self) -> int:
        threats = self.oob.get_threats(min_level=2)
        adjusted = 0
        for t in threats:
            pos = t.get('position', (0, 0, 0))
            adjusted += self.route.deviate_from_threat(pos[0], pos[1])
        return adjusted

    # ── Mission data ──────────────────────────────────────────────────────────

    def set_objectives(self, objectives: List[str]) -> None:
        with self._lock:
            self._objectives = list(objectives)

    def set_roe(self, rules: List[str]) -> None:
        with self._lock:
            self._roe = list(rules)

    def update_intelligence(self, data: dict) -> None:
        with self._lock:
            self._intelligence.update(data)

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        # NOTE (Round 18 investigation): self.phase here is
        # MissionControl's own @property (returns self._phase, always a
        # plain str like 'PLANNING') -- NOT the same self.phase as the
        # separate MissionPlanningSystem class below, which holds a
        # MissionPhase Enum. Already JSON-safe as written; no change
        # needed here. (See MissionPlanningSystem._send_phase_update()
        # elsewhere in this file for the actual Enum-to-.value case that
        # class already handles correctly.)
        return {
            'phase':       self.phase,
            'route':       self.route.get_nav_data(),
            'oob_summary': self.oob.summary(),
            'targets':     self.targeting.get_prioritised(),
            'engaged':     self.targeting.get_engaged(),
        }


# Example usage
if __name__ == "__main__":
    mps = MissionPlanningSystem()
    mps.add_waypoint(35.4148, -97.3867, 1300)
    mps.add_threat(35.4149, -97.3868, 2)
    mps.optimize_route()
    print(mps.get_next_waypoint())
