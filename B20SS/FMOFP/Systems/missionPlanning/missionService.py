"""
Mission Planning Service

Wraps MissionPlanningSystem, RouteManagement, OrderOfBattle, and Targeting
into a single service that:
  - Starts the mission data update loop
  - Persists state via current DBM API
  - Exposes get_data() for MFD mission page and TSD
  - Singleton: get_mission_service()
"""

import threading
import time
import json
from typing import Dict, Any, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_mission_service = None


class MissionService:
    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None
        self._db      = None
        self._init_db()

        # Mission state
        self._phase      = 'PLANNING'
        self._waypoints: List[Dict] = []
        self._targets:   List[Dict] = []
        self._threats:   List[Dict] = []
        self._current_position = {'lat': 35.4147, 'lon': -97.3866, 'alt_ft': 1290.6}
        self._active_waypoint_idx = 0

        # Import and initialise MissionPlanningSystem if available
        self._mps = None
        try:
            from FMOFP.Systems.missionPlanning.missionControl import MissionPlanningSystem
            self._mps = MissionPlanningSystem()
            logger.info("[MISSION] MissionPlanningSystem attached")
        except Exception as e:
            logger.warning(f"[MISSION] MissionPlanningSystem unavailable: {e}")

        # Full mission coordinator (exposes route, targeting, oob)
        self._ctrl = None
        try:
            from FMOFP.Systems.missionPlanning.missionControl import MissionControl
            self._ctrl = MissionControl()
            logger.info("[MISSION] MissionControl attached")
        except Exception as e:
            logger.warning(f"[MISSION] MissionControl unavailable: {e}")

    def _init_db(self):
        try:
            from FMOFP.storage.DBM import DatabaseManager
            db_manager = DatabaseManager('FMOFP/dbConfig.xml')
            self._db = db_manager.get_system_db('mission_management_system')
            self._db.create_table('mission_data', {
                'id':        'INTEGER PRIMARY KEY AUTOINCREMENT',
                'timestamp': 'REAL NOT NULL',
                'phase':     'TEXT NOT NULL',
                'data':      'TEXT NOT NULL',
            })
            logger.info("[MISSION] Database initialised")
        except Exception as e:
            logger.warning(f"[MISSION] DB init failed (non-fatal): {e}")

    def _update(self):
        """Sync position from FMS and tick MissionControl if available."""
        try:
            from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
            fms = get_flightManagementSystem()
            fd  = fms.get_flight_data()
            nav = fd.get('navigation', {})
            vel = fd.get('velocity', {})
            # NOTE: FMS.get_flight_data() always returns a fully-populated
            # 'navigation' dict, even before FMS has produced any real fix
            # (all zeros: {'latitude': 0, 'longitude': 0, 'altitude': 0, ...}).
            # `if nav:` alone is therefore always True once FMS exists, so this
            # used to unconditionally clobber the sensible startup default
            # (self._current_position, set in __init__) with (0, 0, 0) the
            # moment this loop's very first tick ran - which, depending on
            # exactly how far FMS's GPS thread had gotten by that point,
            # could transiently show "null island" on the mission/TSD display
            # right after boot instead of the aircraft's actual position.
            # Only sync once FMS has reported a non-placeholder fix.
            has_real_fix = nav and (nav.get('latitude', 0) != 0 or nav.get('longitude', 0) != 0)
            if has_real_fix:
                with self._lock:
                    self._current_position = {
                        'lat':    nav.get('latitude',  self._current_position['lat']),
                        'lon':    nav.get('longitude', self._current_position['lon']),
                        'alt_ft': nav.get('altitude',  self._current_position['alt_ft']),
                    }
                if self._mps:
                    self._mps.update_current_position(
                        self._current_position['lat'],
                        self._current_position['lon'],
                        self._current_position['alt_ft'],
                    )
                if self._ctrl:
                    gs = vel.get('groundspeed', 450.0)
                    self._ctrl.tick(
                        self._current_position['lat'],
                        self._current_position['lon'],
                        self._current_position['alt_ft'],
                        gs,
                    )
        except Exception:
            logger.debug("MissionService: FMS not yet ready, skipping position update", exc_info=True)

    def _persist(self):
        if self._db is None:
            return
        try:
            with self._lock:
                snapshot = {
                    'position':  self._current_position,
                    'waypoints': self._waypoints,
                    'targets':   self._targets,
                    'threats':   self._threats,
                }
            self._db.insert_into_table('mission_data', {
                'timestamp': time.time(),
                'phase':     self._phase,
                'data':      json.dumps(snapshot),
            })
        except Exception as e:
            logger.debug(f"[MISSION] DB insert skipped: {e}")

    def _update_loop(self):
        logger.info("[MISSION] Update loop started")
        while not self._running.is_set():
            try:
                self._update()
                self._persist()
            except Exception as e:
                logger.error(f"[MISSION] Update error: {e}")
                # NOTE (production readiness re-analysis, August 2026): this was
                # `time.sleep(5)`, which is NOT interruptible by stop() setting the
                # Event -- live-verified (via ThrustManagementSystem, same pattern)
                # that calling stop() while a thread is in this backoff sleep makes
                # stop()'s join(timeout=2) time out and return while the thread is
                # still alive, misleadingly logging "stopped" up to ~3s before the
                # thread actually exits. Event.wait(timeout) is interruptible by
                # .set(), so stop() now wakes this immediately instead of waiting
                # out the full backoff.
                self._running.wait(5)
                continue
            time.sleep(1.0)

    # ------------------------------------------------------------------ public API

    def start(self):
        # Guarded against the same TOCTOU race documented and fixed on the
        # newer subsystem singletons -- see PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py). Reuses
        # the existing data lock; start() never touches the data it
        # guards, so no reentrancy risk.
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self._update_loop, daemon=True, name="MISSION_Update")
            self._thread.start()
            logger.info("[MISSION] Mission service started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[MISSION] Mission service stopped")

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            base = {
                'phase':            self._phase,
                'current_position': dict(self._current_position),
                'waypoints':        list(self._waypoints),
                'targets':          list(self._targets),
                'threats':          list(self._threats),
                'active_waypoint':  self._active_waypoint_idx,
            }
        # Merge richer ctrl snapshot when available
        if self._ctrl:
            try:
                snap = self._ctrl.get_snapshot()
                base['phase']   = snap.get('phase', base['phase'])
                base['route']   = snap.get('route',  {})
                base['targets'] = snap.get('targets', base['targets'])
                base['engaged'] = snap.get('engaged', [])
                base['oob_summary'] = snap.get('oob_summary', {})
            except Exception:
                logger.warning("MissionService: error merging snapshot into status dict", exc_info=True)
        return base

    def get_status(self) -> Dict[str, Any]:
        return {'running': self._thread is not None and self._thread.is_alive(),
                'healthy': True, **self.get_data()}

    def set_phase(self, phase: str):
        valid = ('PLANNING', 'INGRESS', 'OBJECTIVE', 'EGRESS', 'COMPLETE')
        if phase.upper() in valid:
            with self._lock:
                self._phase = phase.upper()
            if self._ctrl:
                self._ctrl.set_phase(phase)
            logger.info(f"[MISSION] Phase → {phase.upper()}")

    def advance_phase(self) -> str:
        if self._ctrl:
            new_phase = self._ctrl.advance_phase()
            with self._lock:
                self._phase = new_phase
            return new_phase
        order = ['PLANNING', 'INGRESS', 'OBJECTIVE', 'EGRESS', 'COMPLETE']
        with self._lock:
            try:
                idx = order.index(self._phase)
            except ValueError:
                idx = 0
            self._phase = order[min(idx + 1, len(order) - 1)]
            return self._phase

    # This used to be shadowed by an earlier add_waypoint(lat, lon, alt_ft,
    # name='') defined above set_phase() -- Python silently kept only this
    # later definition, making the other dead code with an incompatible
    # positional argument order. Removed the dead one (production readiness
    # punch list, item 3 audit); all current callers already use keyword
    # args matching this signature, so behavior is unchanged.
    def add_waypoint(self, name: str = '', lat: float = 0.0,
                     lon: float = 0.0, alt_ft: float = 0.0,
                     wp_type: str = 'NAV') -> Dict[str, Any]:
        with self._lock:
            wp = {'id': len(self._waypoints), 'lat': lat, 'lon': lon,
                  'alt_ft': alt_ft, 'name': name, 'type': wp_type}
            self._waypoints.append(wp)
        if self._mps:
            self._mps.add_waypoint(lat, lon, alt_ft)
        if self._ctrl:
            from FMOFP.Systems.missionPlanning.routeManagement.handleRoute import WaypointType
            wt = WaypointType[wp_type.upper()] if wp_type.upper() in WaypointType.__members__ else WaypointType.NAV
            self._ctrl.route.add_waypoint(name, lat, lon, alt_ft, wt)
        return wp

    def get_route(self) -> List[Dict]:
        if self._ctrl:
            return self._ctrl.route.get_full_route()
        with self._lock:
            return list(self._waypoints)

    def get_nav_data(self) -> Dict[str, Any]:
        if self._ctrl:
            return self._ctrl.route.get_nav_data()
        with self._lock:
            return {'route': list(self._waypoints), 'active_index': self._active_waypoint_idx}

    def designate_target(self, name: str = 'TGT', lat: float = 0.0,
                         lon: float = 0.0, alt_ft: float = 0.0,
                         priority: int = 3, target_type: str = 'POINT') -> Dict[str, Any]:
        if self._ctrl:
            from FMOFP.Systems.missionPlanning.targeting.targeting import Target, TargetStatus
            t_id = f"T{len(self._ctrl.targeting.targets) + 1:04d}"
            tgt  = Target(t_id, target_type, (lat, lon, alt_ft), priority)
            tgt.status = TargetStatus.DESIGNATED
            self._ctrl.targeting.add_target(tgt)
            # Insert TGT waypoint
            self._ctrl.route.insert_target(f"TGT-{t_id}", lat, lon, alt_ft)
            with self._lock:
                self._targets.append(tgt.to_dict())
            return tgt.to_dict()
        # Fallback
        with self._lock:
            entry = {'id': f"T{len(self._targets)+1:04d}", 'name': name,
                     'lat': lat, 'lon': lon, 'alt_ft': alt_ft,
                     'priority': priority, 'status': 'DESIGNATED', 'type': target_type}
            self._targets.append(entry)
        return entry

    def engage_target(self, target_id: str, weapon: str) -> bool:
        if self._ctrl:
            return self._ctrl.targeting.engage_target(target_id, weapon)
        return False

    def radar_target_update(self, target_id: str, lat: float, lon: float,
                            alt_ft: float, speed: float = 0.0,
                            heading: float = 0.0,
                            quality: float = 0.8) -> bool:
        if self._ctrl:
            return self._ctrl.targeting.update_from_radar(
                target_id, lat, lon, alt_ft, speed, heading, quality)
        return False

    def get_targets(self) -> List[Dict]:
        if self._ctrl:
            return self._ctrl.targeting.get_prioritised()
        with self._lock:
            return list(self._targets)

    def add_unit(self, data: Dict) -> Optional[Dict]:
        if self._ctrl:
            from FMOFP.Systems.missionPlanning.orderOfBattle.orderOfBattle import Unit
            try:
                pos = data.get('position', (0, 0, 0))
                unit = Unit(
                    id=data.get('id', 'U?'),
                    type=data.get('type', 'UNKNOWN'),
                    affiliation=data.get('affiliation', 'UNKNOWN'),
                    position=tuple(pos) if not isinstance(pos, tuple) else pos,
                    capabilities=data.get('capabilities', []),
                    threat_level=int(data.get('threat_level', 0)),
                )
                self._ctrl.oob.add_unit(unit)
                return unit.to_dict()
            except Exception as e:
                logger.error(f"[MISSION] add_unit error: {e}")
        return None

    def get_oob(self) -> Dict[str, Any]:
        if self._ctrl:
            return {
                'summary':  self._ctrl.oob.summary(),
                'friendly': self._ctrl.oob.get_by_affiliation('friendly'),
                'enemy':    self._ctrl.oob.get_by_affiliation('enemy'),
                'neutral':  self._ctrl.oob.get_by_affiliation('neutral'),
            }
        return {'summary': {}, 'friendly': [], 'enemy': [], 'neutral': []}

    def get_threats(self, min_level: int = 1) -> List[Dict]:
        if self._ctrl:
            return self._ctrl.oob.get_threats(min_level)
        return []

    def set_objectives(self, objectives: List[str]) -> None:
        if self._ctrl:
            self._ctrl.set_objectives(objectives)

    def set_roe(self, rules: List[str]) -> None:
        if self._ctrl:
            self._ctrl.set_roe(rules)

    def update_intelligence(self, data: Dict) -> None:
        if self._ctrl:
            self._ctrl.update_intelligence(data)

    def optimise_route(self) -> int:
        if self._ctrl:
            return self._ctrl.optimise_route_for_threats()
        return 0

    # A duplicate, simpler add_target() used to exist above set_phase() that
    # only appended to self._targets without touching self._ctrl/designate_target
    # -- unreachable dead code, since this later definition (same signature)
    # was the one Python actually kept. Removed the dead one (production
    # readiness punch list, item 3 audit).
    def add_target(self, lat: float, lon: float, priority: int = 1, name: str = ''):
        """Legacy API — delegates to designate_target."""
        return self.designate_target(name=name, lat=lat, lon=lon, priority=priority)


def get_mission_service() -> 'MissionService':
    global _mission_service
    if _mission_service is None:
        _mission_service = MissionService()
    return _mission_service
