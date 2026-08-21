"""
Route Management

Manages the aircraft's tactical route: waypoints, ordering, progress
tracking, ETE computation, and threat-aware deviation.

Consumed by MissionService/_ctrl and MFD route-display page.
All methods are thread-safe.
"""

import math
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()


class WaypointType(str, Enum):
    IP   = 'IP'     # Initial Point
    TGT  = 'TGT'    # Target
    EGR  = 'EGR'    # Egress
    ALT  = 'ALT'    # Alternate
    NAV  = 'NAV'    # Navigation
    REF  = 'REF'    # Refuel
    HOME = 'HOME'   # Recovery airfield


@dataclass
class Waypoint:
    id:        int
    name:      str
    lat:       float
    lon:       float
    alt_ft:    float
    wp_type:   WaypointType = WaypointType.NAV
    speed_kts: Optional[float] = None
    fly_over:  bool  = True
    ete_min:   Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id':        self.id,
            'name':      self.name,
            'lat':       self.lat,
            'lon':       self.lon,
            'alt_ft':    self.alt_ft,
            'type':      self.wp_type.value,
            'speed_kts': self.speed_kts,
            'fly_over':  self.fly_over,
            'ete_min':   self.ete_min,
        }


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    R_NM = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R_NM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class RouteManager:
    """
    Tactical route manager: ordered waypoints, ETE, auto-advance,
    threat deviation, and tactical insertion.
    """

    _REACHED_NM = 0.5   # waypoint reached when within this radius

    def __init__(self):
        self._lock        = threading.Lock()
        self._waypoints:  List[Waypoint]           = []
        self._active_idx: int                      = 0
        self._pos:        Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._gs_kts:     float                    = 450.0
        self._next_id:    int                      = 1
        logger.debug("[ROUTE] RouteManager initialised")

    # ------------------------------------------------------------------ CRUD

    def add_waypoint(self, name: str, lat: float, lon: float, alt_ft: float,
                     wp_type: WaypointType = WaypointType.NAV,
                     speed_kts: Optional[float] = None,
                     fly_over: bool = True,
                     index: Optional[int] = None) -> Waypoint:
        wp = Waypoint(id=self._next_id, name=name, lat=lat, lon=lon,
                      alt_ft=alt_ft, wp_type=wp_type,
                      speed_kts=speed_kts, fly_over=fly_over)
        with self._lock:
            self._next_id += 1
            if index is None:
                self._waypoints.append(wp)
            else:
                self._waypoints.insert(index, wp)
            self._compute_etes_locked()
        logger.info(f"[ROUTE] WP {wp.id} '{name}' ({wp_type.value}) added")
        return wp

    def remove_waypoint(self, wp_id: int) -> bool:
        with self._lock:
            before = len(self._waypoints)
            self._waypoints = [w for w in self._waypoints if w.id != wp_id]
            removed = len(self._waypoints) < before
            if removed:
                self._active_idx = max(0, min(self._active_idx,
                                              len(self._waypoints) - 1))
                self._compute_etes_locked()
        if removed:
            logger.info(f"[ROUTE] WP {wp_id} removed")
        return removed

    def clear_route(self) -> None:
        with self._lock:
            self._waypoints.clear()
            self._active_idx = 0
        logger.info("[ROUTE] Route cleared")

    # ------------------------------------------------------------------ Progress

    def update_position(self, lat: float, lon: float, alt_ft: float,
                        groundspeed_kts: float = 450.0) -> None:
        with self._lock:
            self._pos   = (lat, lon, alt_ft)
            self._gs_kts = max(1.0, groundspeed_kts)
            if self._active_idx < len(self._waypoints):
                wp = self._waypoints[self._active_idx]
                dist = _haversine_nm(lat, lon, wp.lat, wp.lon)
                if dist < self._REACHED_NM:
                    logger.info(f"[ROUTE] Reached WP {wp.id} '{wp.name}'")
                    self._active_idx = min(self._active_idx + 1,
                                          len(self._waypoints))
            self._compute_etes_locked()

    def _compute_etes_locked(self) -> None:
        if not self._waypoints:
            return
        lat, lon, _ = self._pos
        gs = self._gs_kts
        cumulative = 0.0
        for i, wp in enumerate(self._waypoints):
            if i < self._active_idx:
                wp.ete_min = None
                continue
            if i == self._active_idx:
                dist = _haversine_nm(lat, lon, wp.lat, wp.lon)
            else:
                prev = self._waypoints[i - 1]
                dist = _haversine_nm(prev.lat, prev.lon, wp.lat, wp.lon)
            cumulative += dist
            wp.ete_min = round((cumulative / gs) * 60, 1) if gs > 0 else None

    # ------------------------------------------------------------------ Optimisation

    def insert_target(self, name: str, lat: float, lon: float,
                      alt_ft: float) -> Waypoint:
        """Insert a TGT waypoint near the nearest forward waypoint."""
        with self._lock:
            if not self._waypoints:
                return self.add_waypoint(name, lat, lon, alt_ft, WaypointType.TGT)
            best_idx  = len(self._waypoints)
            best_dist = float('inf')
            for i in range(self._active_idx, len(self._waypoints)):
                d = _haversine_nm(self._waypoints[i].lat,
                                   self._waypoints[i].lon, lat, lon)
                if d < best_dist:
                    best_dist, best_idx = d, i
        return self.add_waypoint(name, lat, lon, alt_ft,
                                 WaypointType.TGT, index=best_idx)

    def deviate_from_threat(self, threat_lat: float, threat_lon: float,
                            threat_radius_nm: float = 20.0) -> int:
        """Push waypoints inside threat_radius_nm radially outward. Returns count adjusted."""
        adjusted = 0
        with self._lock:
            for wp in self._waypoints:
                dist = _haversine_nm(wp.lat, wp.lon, threat_lat, threat_lon)
                if 0 < dist < threat_radius_nm:
                    factor = (threat_radius_nm - dist) / dist * 1.1
                    wp.lat += (wp.lat - threat_lat) * factor
                    wp.lon += (wp.lon - threat_lon) * factor
                    adjusted += 1
            if adjusted:
                self._compute_etes_locked()
        if adjusted:
            logger.info(f"[ROUTE] Deviated {adjusted} waypoints around "
                        f"threat at ({threat_lat:.4f},{threat_lon:.4f})")
        return adjusted

    # ------------------------------------------------------------------ Data API

    def get_nav_data(self) -> Dict[str, Any]:
        with self._lock:
            active = None
            dist_nm = None
            bearing = None
            if self._active_idx < len(self._waypoints):
                wp = self._waypoints[self._active_idx]
                active  = wp.to_dict()
                lat, lon, _ = self._pos
                dist_nm = round(_haversine_nm(lat, lon, wp.lat, wp.lon), 1)
                dy = wp.lat - lat
                dx = (wp.lon - lon) * math.cos(math.radians(lat))
                bearing = round((math.degrees(math.atan2(dx, dy)) + 360) % 360, 1)
            return {
                'route':                   [w.to_dict() for w in self._waypoints],
                'active_index':            self._active_idx,
                'active_waypoint':         active,
                'distance_to_next_nm':     dist_nm,
                'bearing_to_next_deg':     bearing,
                'waypoints_remaining':     max(0, len(self._waypoints) - self._active_idx),
            }

    def get_full_route(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [w.to_dict() for w in self._waypoints]
