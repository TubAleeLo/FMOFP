"""
Tactical Situation Display (TSD)

Shows the aircraft's current tactical state on a single-screen summary:

  ┌────────────────────────────────────────────────────┐
  │  Title bar                                         │
  ├──────────────────┬─────────────────────────────────┤
  │  Situation map   │  Energy / performance metrics   │
  │  (bearing ring + │  G-force arc                    │
  │   threat vectors)│  AoA indicator                  │
  │                  │  Energy state bar                │
  │                  │  Specific excess power           │
  ├──────────────────┴─────────────────────────────────┤
  │  Tactical systems status strip                     │
  │  (mode · countermeasures · targeting · weapons     │
  │   stealth · RCS · IR sig · ECM · fuel · throttle) │
  └────────────────────────────────────────────────────┘

Data source: FMS (get_flight_data) + fmsControl (get_tactical_status).
Polls at 10 Hz.
"""

import math
import threading
import time
import traceback
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from .base_display import BaseDisplay, DisplayType
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ─────────────────────────────────────────────────────────── colours ──
_GREEN  = QColor(0,   255, 120)
_AMBER  = QColor(255, 200,   0)
_RED    = QColor(255,  60,  60)
_CYAN   = QColor(0,   220, 255)
_WHITE  = QColor(240, 240, 240)
_DIM    = QColor(100, 100, 100)
_BG     = QColor(10,   12,  16)
_PANEL  = QColor(18,   22,  28)
_RING   = QColor(40,   60,  40)

# Flight mode colours
_MODE_COLOURS = {
    "NORMAL":    _GREEN,
    "COMBAT":    _RED,
    "STEALTH":   _CYAN,
    "TRAINING":  _AMBER,
    "EMERGENCY": QColor(255, 100, 0),
}


class TacticalSituationDisplay(BaseDisplay):
    """
    Tactical Situation Display widget.

    Pulls all data from FMS + fmsControl at 10 Hz.  When neither is
    available (e.g. during early start-up), the display shows a
    NO DATA state rather than crashing.
    """

    def __init__(self, parent=None):
        super().__init__(DisplayType.TSD, parent=parent)

        # ── cached state ───────────────────────────────────────────────────
        self._mode      = "NORMAL"
        self._heading   = 0.0
        self._airspeed  = 0.0
        self._altitude  = 0.0
        self._g_force   = 1.0
        self._aoa       = 0.0
        self._energy    = 50.0      # 0-100
        self._sep       = 0.0       # specific excess power (m/s)
        self._throttle  = 50.0      # 0-100 %
        self._waypoints: List[Dict] = []

        # Tactical systems
        self._tac: Dict = {
            "countermeasures": "STANDBY",
            "targeting":       "STANDBY",
            "weapons":         "SAFE",
            "stealth_mode":    "OFF",
        }
        self._warnings: List[str] = []

        # Envelope / energy metrics
        self._max_turn_sustained  = 0.0   # deg/s
        self._max_turn_instant    = 0.0   # deg/s
        self._max_climb_fpm       = 0.0

        # Threat vectors (simulated — position relative to own ship, nm)
        self._threats: List[Dict] = []
        self._track_history: Dict[str, List] = {}  # contact_id -> [(x,y)...]
        self._rwr_contacts: List[Dict] = []        # from DefensiveService

        # ── FMS handles ────────────────────────────────────────────────────
        self._fms         = None
        self._fms_control = None
        self._fusion      = None   # RadarDataFusion singleton (lazy)
        self._mission     = None   # MissionService singleton (lazy)
        self._lock        = threading.Lock()

        # ── poll timer (10 Hz) ────────────────────────────────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_data)
        self._poll_timer.start()

        logger.info("[TSD] Display initialised")

    # ───────────────────────────────────────────────── data layer ──────────

    def _lazy_fms(self):
        if self._fms is None:
            try:
                from FMOFP.Systems.flightManagementSys.flightManagementSystem import (
                    get_flightManagementSystem,
                )
                from FMOFP.Systems.flightManagementSys.fmsControl import (
                    get_fms_control,
                )
                self._fms = get_flightManagementSystem()
                self._fms_control = get_fms_control()
            except Exception as exc:
                logger.debug(f"[TSD] FMS not ready: {exc}")

        if self._fusion is None:
            try:
                from FMOFP.Systems.radarManagement.radar_data_fusion import (
                    get_radar_data_fusion,
                )
                self._fusion = get_radar_data_fusion()
            except Exception as exc:
                logger.debug(f"[TSD] Fusion not ready: {exc}")

        if self._mission is None:
            try:
                from FMOFP.Systems.missionPlanning.missionService import get_mission_service
                self._mission = get_mission_service()
            except Exception as exc:
                logger.debug(f"[TSD] MissionService not ready: {exc}")

    def _poll_data(self):
        """Pull live data from FMS and update the cached state."""
        try:
            self._lazy_fms()
            if not self._fms:
                return

            fd = self._fms.get_flight_data()
            ts: Optional[Dict] = None
            if self._fms_control:
                try:
                    ts = self._fms_control.get_tactical_status()
                except Exception:
                    logger.debug("TSD: FMS tactical status unavailable", exc_info=True)

            with self._lock:
                nav = fd.get("navigation", {})
                vel = fd.get("velocity",   {})
                tac = fd.get("tactical",   {})
                sta = fd.get("status",     {})

                self._heading  = nav.get("heading",  self._heading)
                self._altitude = nav.get("altitude", self._altitude)
                self._airspeed = vel.get("airspeed", self._airspeed)
                self._g_force  = tac.get("g_force",  self._g_force)
                self._aoa      = tac.get("aoa",      self._aoa)
                self._energy   = tac.get("energy_state", self._energy)
                self._mode     = sta.get("mode",     self._mode)

                # Waypoints: prefer MissionService tactical route over raw FMS nav
                if self._mission is not None:
                    try:
                        route_nav = self._mission.get_nav_data()
                        self._waypoints = route_nav.get("route", [])
                    except Exception:
                        self._waypoints = nav.get("waypoints", [])
                else:
                    self._waypoints = nav.get("waypoints", [])

                if ts:
                    self._tac      = ts.get("tactical_systems",   self._tac)
                    self._warnings = ts.get("envelope_warnings",  self._warnings)
                    em = ts.get("energy_metrics", {})
                    self._sep               = em.get("specific_excess_power", 0.0)
                    self._max_turn_sustained = em.get("max_sustained_turn_rate", 0.0)
                    self._max_turn_instant   = em.get("max_instantaneous_turn_rate", 0.0)
                    self._max_climb_fpm      = em.get("max_climb_rate_fpm", 0.0)
                    prof = ts.get("profile_limits", {})
                    self._throttle = prof.get("engine_power", 0.7) * 100

                # Pull real fused tracks; fall back to simulation
                # if fusion not yet running.
                self._threats = self._get_fused_threats()

                # Merge OOB unit positions from MissionService into threat layer.
                # Enemy units appear as hostile contacts; friendly as non-hostile.
                if self._mission is not None:
                    try:
                        own_lat = nav.get("latitude",  35.4147)
                        own_lon = nav.get("longitude", -97.3866)
                        own_hdg = self._heading
                        oob_contacts = self._oob_to_threat_vectors(
                            self._mission.get_oob(), own_lat, own_lon, own_hdg)
                        # Append OOB contacts; fused radar tracks take precedence
                        self._threats = self._threats + oob_contacts
                    except Exception as exc:
                        logger.debug(f"[TSD] OOB merge error: {exc}")

                # RWR contacts from DefensiveService
                try:
                    from FMOFP.Systems.defensiveSys.defensiveService import get_defensive_service
                    self._rwr_contacts = get_defensive_service().get_rwr_contacts()
                except Exception:
                    logger.debug("TSD: DefensiveService not yet running", exc_info=True)

            self._safe_update()

        except Exception as exc:
            logger.error(f"[TSD] Poll error: {exc}")
            logger.error(traceback.format_exc())

    def _get_fused_threats(self) -> List[Dict]:
        """
        Return threat-vector dicts from the cross-radar fusion layer.
        Each dict has the keys _draw_map() expects:
            bearing (deg true), range_nm, type (str), hostile (bool)

        Falls back to _simulate_threats() when fusion is unavailable
        or has not yet produced any tracks.
        """
        try:
            if self._fusion is not None:
                tracks = self._fusion.get_fused_tracks()
                if tracks:
                    return [t.to_tsd_dict() for t in tracks]
        except Exception as exc:
            logger.debug(f"[TSD] Fusion read error: {exc}")
        return self._simulate_threats()

    def _simulate_threats(self) -> List[Dict]:
        """Return a small set of simulated threat vectors (relative nm, bearing)."""
        t = time.time()
        return [
            {"bearing": (self._heading + 45 + 10 * math.sin(t * 0.2)) % 360,
             "range_nm": 18 - 5 * abs(math.sin(t * 0.1)),
             "type": "FIGHTER", "hostile": True},
            {"bearing": (self._heading + 210 + 8 * math.sin(t * 0.15 + 1)) % 360,
             "range_nm": 32 + 4 * math.sin(t * 0.08),
             "type": "SAM", "hostile": True},
        ]

    def _oob_to_threat_vectors(
        self, oob_data: dict, own_lat: float, own_lon: float, own_hdg: float
    ) -> List[Dict]:
        """
        Convert OOB unit positions into TSD threat-vector dicts.

        Each returned dict contains:
            bearing  — degrees true from own ship
            range_nm — nautical miles from own ship
            type     — unit type string (e.g. 'SAM_SITE', 'FIGHTER')
            hostile  — True for ENEMY units
            identity — 'FRIENDLY' | 'ENEMY' | 'NEUTRAL' | 'UNKNOWN'
        """
        import math as _math
        contacts = []
        NM_PER_DEG_LAT = 60.0

        for affil_key in ("enemy", "friendly", "neutral"):
            units = oob_data.get(affil_key, [])
            hostile = affil_key == "enemy"
            identity = affil_key.upper()

            for unit in units:
                pos = unit.get("position")
                if not pos or len(pos) < 2:
                    continue
                u_lat, u_lon = float(pos[0]), float(pos[1])

                dlat = (u_lat - own_lat) * NM_PER_DEG_LAT
                dlon = (u_lon - own_lon) * NM_PER_DEG_LAT * _math.cos(_math.radians(own_lat))
                range_nm = _math.sqrt(dlat ** 2 + dlon ** 2)

                # Only show units within 120 nm
                if range_nm > 120:
                    continue

                bearing_true = (_math.degrees(_math.atan2(dlon, dlat)) + 360) % 360
                status = unit.get("status", "OPERATIONAL")

                contacts.append({
                    "bearing":  round(bearing_true, 1),
                    "range_nm": round(range_nm, 1),
                    "type":     unit.get("type", "UNIT"),
                    "hostile":  hostile,
                    "identity": identity,
                    "status":   status,
                    "name":     unit.get("id", ""),
                })
        return contacts

    # ───────────────────────────────────────────────── paint ───────────────

    def paint_display(self, painter: QPainter):
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.save()

            w = float(self.width())
            h = float(self.height())

            title_h  = h * 0.07
            body_h   = h * 0.75
            strip_h  = h - title_h - body_h

            map_w    = w * 0.50
            metrics_w = w - map_w

            # Regions
            title_r   = QRectF(0,      0,          w,         title_h)
            map_r     = QRectF(0,      title_h,    map_w,     body_h)
            metrics_r = QRectF(map_w,  title_h,    metrics_w, body_h)
            strip_r   = QRectF(0,      title_h + body_h, w,  strip_h)

            with self._lock:
                self._draw_title(painter, title_r)
                self._draw_map(painter, map_r)
                self._draw_metrics(painter, metrics_r)
                self._draw_strip(painter, strip_r)

            painter.restore()
        except Exception as exc:
            logger.error(f"[TSD] Paint error: {exc}")
            logger.error(traceback.format_exc())
            raise

    # ── title bar ────────────────────────────────────────────────────────────

    def _draw_title(self, painter: QPainter, r: QRectF):
        mode_col = _MODE_COLOURS.get(self._mode, _WHITE)
        painter.fillRect(r, QColor(20, 20, 30))

        f = QFont("Monospace", 11, QFont.Weight.Bold)
        painter.setFont(f)
        painter.setPen(QPen(mode_col))
        painter.drawText(
            r, Qt.AlignmentFlag.AlignCenter,
            f"TSD — TACTICAL SITUATION        MODE: {self._mode}"
        )
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left()), int(r.bottom()),
                         int(r.right()), int(r.bottom()))

    # ── situation map ────────────────────────────────────────────────────────

    def _draw_map(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, _BG)
        painter.setPen(QPen(_DIM, 1))
        painter.drawRect(r)

        cx = r.left() + r.width()  / 2
        cy = r.top()  + r.height() / 2
        rad = min(r.width(), r.height()) / 2 - 14

        # Bearing ring
        painter.setPen(QPen(_RING, 1))
        for ring_frac in [0.33, 0.67, 1.0]:
            rr = rad * ring_frac
            painter.drawEllipse(
                QPointF(cx, cy), rr, rr
            )

        # Range labels (NM) — max range = 50 nm
        max_nm = 50.0
        f_sm = QFont("Monospace", 7)
        painter.setFont(f_sm)
        painter.setPen(QPen(_DIM))
        for frac, label in [(0.33, "17"), (0.67, "33"), (1.0, "50")]:
            label_r = QRectF(cx + rad * frac - 12, cy - 10, 24, 12)
            painter.drawText(label_r, Qt.AlignmentFlag.AlignCenter, label)

        # Cardinal tick marks
        painter.setPen(QPen(_DIM, 1))
        for deg, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
            rad_ang = math.radians(deg - 90)
            ox = cx + (rad + 2) * math.cos(rad_ang)
            oy = cy + (rad + 2) * math.sin(rad_ang)
            ix = cx + (rad - 6) * math.cos(rad_ang)
            iy = cy + (rad - 6) * math.sin(rad_ang)
            painter.drawLine(QPointF(ix, iy), QPointF(ox, oy))
            lx = cx + (rad + 10) * math.cos(rad_ang)
            ly = cy + (rad + 10) * math.sin(rad_ang)
            lbl_r = QRectF(lx - 8, ly - 7, 16, 14)
            painter.setFont(f_sm)
            painter.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter, label)

        # Own-ship symbol (triangle pointing up — rotated by heading)
        own_size = 10.0
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._heading)
        path = QPainterPath()
        path.moveTo(0, -own_size)
        path.lineTo(-own_size * 0.6, own_size * 0.7)
        path.lineTo(own_size * 0.6, own_size * 0.7)
        path.closeSubpath()
        painter.setPen(QPen(_GREEN, 1))
        painter.setBrush(_GREEN)
        painter.drawPath(path)
        painter.restore()

        # Waypoints
        if self._waypoints:
            active_wp = None
            for wp in self._waypoints[:8]:
                # Project using lat/lon delta; for simulator we use a simple
                # placeholder offset based on waypoint index
                idx = wp.get("id", 0)
                angle_rad = math.radians(self._heading + 30 * idx)
                dist_nm = min(max_nm * 0.9, 5 + idx * 8)
                wx = cx + (dist_nm / max_nm) * rad * math.cos(angle_rad - math.pi / 2)
                wy = cy + (dist_nm / max_nm) * rad * math.sin(angle_rad - math.pi / 2)
                painter.setPen(QPen(_CYAN, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(wx - 4, wy - 4, 8, 8))
                # Label
                f_wp = QFont("Monospace", 6)
                painter.setFont(f_wp)
                painter.setPen(QPen(_CYAN))
                painter.drawText(QRectF(wx + 5, wy - 6, 40, 12),
                                 Qt.AlignmentFlag.AlignLeft,
                                 wp.get("name", f"WP{idx}"))

        # Threat contacts — threat rings, track history, IFF symbology, velocity vectors
        f_t = QFont("Monospace", 6)
        _THREAT_RING = QColor(180, 40, 40, 60)

        for thr in self._threats:
            b   = math.radians(thr.get("bearing", 0) - 90)
            d   = thr.get("range_nm", 0)
            tx  = cx + (d / max_nm) * rad * math.cos(b)
            ty  = cy + (d / max_nm) * rad * math.sin(b)
            col = _RED if thr.get("hostile") else _AMBER
            tid = thr.get("type", "UNK")
            is_hostile = thr.get("hostile", False)

            # Track history trail
            ckey = f"{tid}_{int(thr.get('bearing', 0))}"
            if ckey not in self._track_history:
                self._track_history[ckey] = []
            hist = self._track_history[ckey]
            hist.append((tx, ty))
            if len(hist) > 20:
                hist.pop(0)
            if len(hist) > 1:
                for hi in range(1, len(hist)):
                    tc = QColor(col)
                    tc.setAlpha(int(80 * hi / len(hist)))
                    painter.setPen(QPen(tc, 1, Qt.PenStyle.DotLine))
                    painter.drawLine(QPointF(*hist[hi-1]), QPointF(*hist[hi]))

            # Threat ring for SAM/MISSILE (10 nm)
            if is_hostile and tid in ("SAM", "MISSILE"):
                ring_r = (10.0 / max_nm) * rad
                painter.setPen(QPen(_THREAT_RING, 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(tx, ty), ring_r, ring_r)

            # IFF symbology
            painter.setPen(QPen(col, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            sz = 6.0
            if is_hostile:
                # X = hostile
                painter.drawLine(QPointF(tx - sz, ty - sz), QPointF(tx + sz, ty + sz))
                painter.drawLine(QPointF(tx + sz, ty - sz), QPointF(tx - sz, ty + sz))
            elif thr.get("identity", "UNKNOWN") == "FRIENDLY":
                # Circle = friendly
                painter.drawEllipse(QPointF(tx, ty), sz, sz)
            else:
                # Diamond = unknown
                pts = [QPointF(tx, ty-sz), QPointF(tx+sz, ty),
                       QPointF(tx, ty+sz), QPointF(tx-sz, ty), QPointF(tx, ty-sz)]
                for pi in range(len(pts)-1):
                    painter.drawLine(pts[pi], pts[pi+1])

            # Velocity vector
            vx = thr.get("vx", 0)
            vy = thr.get("vy", 0)
            if abs(vx) > 0.1 or abs(vy) > 0.1:
                spd = math.sqrt(vx*vx + vy*vy)
                vang = math.atan2(vy, vx)
                vec_len = min(spd / max_nm * rad * 3, 20)
                vex = tx + vec_len * math.cos(vang)
                vey = ty + vec_len * math.sin(vang)
                painter.setPen(QPen(col, 1))
                painter.drawLine(QPointF(tx, ty), QPointF(vex, vey))
                for da in (0.4, -0.4):
                    painter.drawLine(QPointF(vex, vey),
                        QPointF(vex - 5*math.cos(vang+da), vey - 5*math.sin(vang+da)))

            # Label
            painter.setFont(f_t)
            painter.setPen(QPen(col))
            painter.drawText(QRectF(tx + 8, ty - 6, 50, 12),
                             Qt.AlignmentFlag.AlignLeft, f"{tid} {d:.0f}nm")

        # RWR contacts from DefensiveService (bearing-only, on ring edge)
        for rwr in self._rwr_contacts:
            b  = math.radians(rwr.get("bearing_deg", 0) - 90)
            rx = cx + rad * math.cos(b)
            ry = cy + rad * math.sin(b)
            painter.setPen(QPen(_RED, 2))
            painter.setBrush(_RED)
            painter.drawEllipse(QPointF(rx, ry), 4, 4)
            painter.setFont(QFont("Monospace", 6))
            painter.setPen(QPen(_RED))
            painter.drawText(QRectF(rx + 5, ry - 5, 20, 10),
                             Qt.AlignmentFlag.AlignLeft, rwr.get("band", "?"))

        # Heading readout
        f_hdg = QFont("Monospace", 9, QFont.Weight.Bold)
        painter.setFont(f_hdg)
        painter.setPen(QPen(_WHITE))
        hdg_r = QRectF(r.left() + 4, r.bottom() - 20, 80, 18)
        painter.drawText(hdg_r, Qt.AlignmentFlag.AlignVCenter,
                         f"HDG {self._heading:05.1f}°")

    # ── metrics panel ────────────────────────────────────────────────────────

    def _draw_metrics(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, _PANEL)
        painter.setPen(QPen(_DIM, 1))
        painter.drawRect(r)

        f_lbl = QFont("Monospace", 8)
        f_val = QFont("Monospace", 10, QFont.Weight.Bold)

        # ── G-force arc ────────────────────────────────────────────────────
        arc_cx = r.left() + r.width() / 2
        arc_cy = r.top() + r.height() * 0.22
        arc_r  = min(r.width(), r.height()) * 0.18

        # Background arc (0 – 9 G)
        painter.setPen(QPen(_DIM, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        arc_rect = QRectF(arc_cx - arc_r, arc_cy - arc_r,
                          arc_r * 2, arc_r * 2)
        painter.drawArc(arc_rect, 210 * 16, -240 * 16)   # 210° to -30°

        # G ticks (0, 3, 6, 9)
        painter.setFont(f_lbl)
        for g_val, label in [(0, "0"), (3, "3"), (6, "6"), (9, "9")]:
            ang = math.radians(210 - (g_val / 9) * 240)
            tx  = arc_cx + arc_r * 1.2 * math.cos(ang)
            ty  = arc_cy - arc_r * 1.2 * math.sin(ang)
            painter.setPen(QPen(_DIM))
            painter.drawText(QRectF(tx - 8, ty - 7, 16, 14),
                             Qt.AlignmentFlag.AlignCenter, label)

        # G needle
        g_clamped = max(0.0, min(9.0, self._g_force))
        g_ang = math.radians(210 - (g_clamped / 9) * 240)
        needle_end = QPointF(
            arc_cx + arc_r * math.cos(g_ang),
            arc_cy - arc_r * math.sin(g_ang),
        )
        g_col = (_RED   if self._g_force > 8.0 else
                 _AMBER if self._g_force > 6.0 else _GREEN)
        painter.setPen(QPen(g_col, 2))
        painter.drawLine(QPointF(arc_cx, arc_cy), needle_end)

        # G readout
        painter.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        painter.setPen(QPen(g_col))
        g_r = QRectF(arc_cx - 25, arc_cy - 10, 50, 20)
        painter.drawText(g_r, Qt.AlignmentFlag.AlignCenter,
                         f"{self._g_force:.1f}G")

        # ── metric rows ────────────────────────────────────────────────────
        row_y = r.top() + r.height() * 0.46
        row_h = (r.bottom() - row_y - 8) / 6

        def row(label, value, col):
            nonlocal row_y
            l_r = QRectF(r.left() + 8,  row_y, r.width() * 0.56, row_h)
            v_r = QRectF(r.left() + r.width() * 0.58, row_y,
                         r.width() * 0.40, row_h)
            painter.setFont(f_lbl)
            painter.setPen(QPen(_DIM))
            painter.drawText(l_r, Qt.AlignmentFlag.AlignVCenter, label)
            painter.setFont(f_val)
            painter.setPen(QPen(col))
            painter.drawText(v_r, Qt.AlignmentFlag.AlignVCenter |
                             Qt.AlignmentFlag.AlignRight, value)
            row_y += row_h

        # AoA
        aoa_col = (_RED   if abs(self._aoa) > 20 else
                   _AMBER if abs(self._aoa) > 14 else _GREEN)
        row("AoA", f"{self._aoa:+5.1f}°", aoa_col)

        # Energy state bar
        row("ENERGY", f"{self._energy:5.1f}%",
            _RED if self._energy < 20 else _AMBER if self._energy < 40 else _GREEN)

        # SEP
        sep_col = _AMBER if self._sep < 0 else _GREEN
        row("SEP", f"{self._sep:+5.0f} m/s", sep_col)

        # Turn rates
        row("TURN SUS", f"{self._max_turn_sustained:5.1f}°/s", _CYAN)
        row("TURN INS", f"{self._max_turn_instant:5.1f}°/s",   _CYAN)
        row("CLB MAX",  f"{self._max_climb_fpm:6.0f} fpm",     _GREEN)

        # ── envelope warnings ─────────────────────────────────────────────
        if self._warnings:
            warn_y = r.bottom() - len(self._warnings) * 13 - 4
            painter.setFont(QFont("Monospace", 7, QFont.Weight.Bold))
            painter.setPen(QPen(_AMBER))
            for w in self._warnings[-3:]:   # max 3
                wr = QRectF(r.left() + 4, warn_y, r.width() - 8, 13)
                painter.drawText(wr, Qt.AlignmentFlag.AlignVCenter,
                                 f"⚠ {w}")
                warn_y += 13

    # ── tactical systems strip ───────────────────────────────────────────────

    def _draw_strip(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, QColor(14, 16, 22))
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left()), int(r.top()),
                         int(r.right()), int(r.top()))

        # Build display items
        systems = {
            "CNTM":  self._tac.get("countermeasures", "STANDBY"),
            "TGT":   self._tac.get("targeting",       "STANDBY"),
            "WPN":   self._tac.get("weapons",         "SAFE"),
            "STLTH": self._tac.get("stealth_mode",    "OFF"),
        }
        extra = {
            "THROT": f"{self._throttle:4.0f}%",
            "IAS":   f"{self._airspeed:5.0f}kt",
            "ALT":   f"{self._altitude:6.0f}ft",
        }

        all_items = [(k, v, self._sys_colour(k, v))
                     for k, v in systems.items()]
        all_items += [(k, v, _GREEN) for k, v in extra.items()]

        cell_w = r.width() / len(all_items)
        f_lbl  = QFont("Monospace", 7)
        f_val  = QFont("Monospace", 8, QFont.Weight.Bold)

        for i, (label, value, col) in enumerate(all_items):
            cx = r.left() + i * cell_w
            lbl_r = QRectF(cx + 2, r.top() + 2,  cell_w - 4, r.height() * 0.45)
            val_r = QRectF(cx + 2, r.top() + r.height() * 0.48,
                           cell_w - 4, r.height() * 0.50)
            painter.setFont(f_lbl)
            painter.setPen(QPen(_DIM))
            painter.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter, label)
            painter.setFont(f_val)
            painter.setPen(QPen(col))
            painter.drawText(val_r, Qt.AlignmentFlag.AlignCenter, value)

            # Vertical divider
            if i > 0:
                painter.setPen(QPen(_DIM, 1))
                painter.drawLine(int(cx), int(r.top()),
                                 int(cx), int(r.bottom()))

    @staticmethod
    def _sys_colour(system: str, state: str) -> QColor:
        """Map a tactical system state to a colour."""
        danger = {"ARMED", "ACTIVE", "ON", "FAILED"}
        ready  = {"READY", "PASSIVE", "SAFE", "STANDBY"}
        if state in danger:
            return _RED if system == "WPN" else _AMBER
        if state in ready:
            return _GREEN
        return _WHITE

    # ────────────────────────────────────────────── lifecycle ──────────────

    def stop(self):
        self._poll_timer.stop()
        super().stop()

    def cleanup(self):
        self._poll_timer.stop()
