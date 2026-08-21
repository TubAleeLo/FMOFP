"""
Stores Management System (SMS)

Provides the crew with a complete picture of all external and internal stores,
weapon station status, armament modes, and aircraft signature state.

Layout (800 × 600):
┌─────────────────────────────────────────────────────────┐
│  Title bar  (Master Arm state · Release mode · Delivery)│
├────────────────────────────┬────────────────────────────┤
│  Station diagram           │  Station detail table      │
│  (aircraft planform +      │  (type · qty · status ·    │
│   pylon icons, colour-     │   weight per station)      │
│   coded by state)          │                            │
├────────────────────────────┴────────────────────────────┤
│  Signature management strip                             │
│  (RCS · IR · ECM · Stealth · Countermeasures)          │
└─────────────────────────────────────────────────────────┘

Data source: FMS tactical_status + get_flight_data(), polled at 5 Hz.
Station loadout is simulated (no live armament system is modelled yet).
"""

import math
import threading
import time
import traceback
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QBrush,
    QLinearGradient,
)

from .base_display import BaseDisplay, DisplayType
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ──────────────────────────────────────────────────── colour palette ──
_GREEN  = QColor(0,   220,  90)
_AMBER  = QColor(255, 200,   0)
_RED    = QColor(255,  60,  60)
_CYAN   = QColor(0,   210, 255)
_WHITE  = QColor(235, 235, 235)
_DIM    = QColor( 90,  90,  90)
_BG     = QColor( 10,  12,  16)
_PANEL  = QColor( 18,  22,  30)
_DARK   = QColor( 12,  14,  20)

# Station state colours
_STATE_COLOUR = {
    "SAFE":      _GREEN,
    "ARMED":     _RED,
    "READY":     _AMBER,
    "EXPENDED":  _DIM,
    "JETTISONED": QColor(120, 60, 0),
    "EMPTY":     _DIM,
    "FAULT":     QColor(255, 0, 200),
}

# Master Arm states
_MASTER_ARM_COLOUR = {
    "SAFE":  _GREEN,
    "ARMED": _RED,
    "TRAIN": _AMBER,
}


# ─────────────────────────────────────── weapon store definition ──────
class _Store:
    """A single store (weapon or fuel tank) on a station."""
    def __init__(self, name: str, weight_kg: float, qty: int,
                 state: str = "SAFE", store_type: str = "WEAPON"):
        self.name       = name
        self.weight_kg  = weight_kg
        self.qty        = qty
        self.state      = state      # SAFE / ARMED / READY / EXPENDED / EMPTY
        self.store_type = store_type # WEAPON / TANK / POD / DECOY


class _Station:
    """A single weapon station (pylon or bay)."""
    def __init__(self, station_id: int, label: str,
                 rel_x: float, rel_y: float,
                 store: Optional[_Store] = None,
                 internal: bool = False):
        self.station_id = station_id
        self.label      = label
        self.rel_x      = rel_x    # 0-1 in planform coordinate space
        self.rel_y      = rel_y    # 0-1 (0 = nose, 1 = tail)
        self.store      = store
        self.internal   = internal  # True for internal bay stations


def _build_default_loadout() -> List[_Station]:
    """
    Return a representative B-2-style loadout:
      - 2 internal weapon bays (left / right), each with 4 MK-82 positions
      - 2 wingtip decoy stations
      - 1 centreline ECM pod

    Station positions use normalised planform coordinates
    (0,0 = top-left of bounding box, 1,1 = bottom-right).
    """
    mk82  = _Store("MK-82",   227, 4, "SAFE",  "WEAPON")
    jdam  = _Store("JDAM",    910, 2, "ARMED", "WEAPON")
    glcm  = _Store("JASSM",  1021, 1, "SAFE",  "WEAPON")
    decoy = _Store("ALE-55",    8, 8, "READY", "DECOY")
    ecm   = _Store("AN/ALQ",  180, 1, "READY", "POD")

    return [
        # Internal left bay  (stations 1-4)
        _Station(1, "L-BAY1", 0.38, 0.40, _Store("MK-82", 227, 4, "ARMED", "WEAPON"), internal=True),
        _Station(2, "L-BAY2", 0.38, 0.50, _Store("JDAM",  910, 2, "SAFE",  "WEAPON"), internal=True),
        _Station(3, "L-BAY3", 0.38, 0.60, _Store("JASSM",1021, 1, "SAFE",  "WEAPON"), internal=True),
        _Station(4, "L-BAY4", 0.38, 0.70, _Store("MK-82", 227, 0, "EMPTY", "WEAPON"), internal=True),
        # Internal right bay (stations 5-8)
        _Station(5, "R-BAY1", 0.62, 0.40, _Store("MK-82", 227, 4, "ARMED", "WEAPON"), internal=True),
        _Station(6, "R-BAY2", 0.62, 0.50, _Store("JDAM",  910, 2, "SAFE",  "WEAPON"), internal=True),
        _Station(7, "R-BAY3", 0.62, 0.60, _Store("JASSM",1021, 1, "SAFE",  "WEAPON"), internal=True),
        _Station(8, "R-BAY4", 0.62, 0.70, _Store("MK-82", 227, 0, "EMPTY", "WEAPON"), internal=True),
        # Wingtip decoy launchers (stations 9-10)
        _Station(9,  "LWTIP", 0.12, 0.58, _Store("ALE-55", 8, 8, "READY", "DECOY")),
        _Station(10, "RWTIP", 0.88, 0.58, _Store("ALE-55", 8, 8, "READY", "DECOY")),
        # Centreline ECM pod (station 11)
        _Station(11, "ECM-C", 0.50, 0.55, _Store("AN/ALQ", 180, 1, "READY", "POD")),
    ]


class StoresManagementDisplay(BaseDisplay):
    """
    Stores Management System (SMS) display widget.

    Shows the aircraft planform with all weapon stations colour-coded by
    their current state, a detail table for each station, the master-arm
    and release mode status, and the aircraft signature strip.
    """

    # ── Master arm / release modes ────────────────────────────────────────
    _MASTER_ARM      = "SAFE"       # SAFE / ARMED / TRAIN
    _RELEASE_MODE    = "SINGLE"     # SINGLE / RIPPLE / SALVO
    _DELIVERY_MODE   = "AUTO"       # AUTO / MAN / CCIP / CCRP / DTOS
    _SELECTED_STA    = 1            # Currently selected station

    def __init__(self, parent=None):
        super().__init__(DisplayType.SMS, parent=parent)

        # Weapon stations
        self._stations: List[_Station] = _build_default_loadout()

        # Master arm state (driven by FMS tactical mode)
        self._master_arm    = self._MASTER_ARM
        self._release_mode  = self._RELEASE_MODE
        self._delivery_mode = self._DELIVERY_MODE
        self._selected_sta  = self._SELECTED_STA

        # Signature state (from FMS tactical response service)
        self._rcs    = 0.0      # m²  (0.001 stealth → 10+ conventional)
        self._ir_sig = 0.0      # 0-1 normalised
        self._ecm    = "INACTIVE"
        self._stealth= "OFF"
        self._cntm   = "STANDBY"
        self._flight_mode = "NORMAL"

        # FMS handles (lazy)
        self._fms         = None
        self._fms_control = None
        self._lock        = threading.Lock()

        # Poll timer (5 Hz — stores change rarely)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._poll_data)
        self._poll_timer.start()

        logger.info("[SMS] Display initialised")

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
                logger.debug(f"[SMS] FMS not ready: {exc}")

    def _poll_data(self):
        """Pull tactical/signature data from FMS."""
        try:
            self._lazy_fms()
            if not self._fms:
                return

            ts: Optional[Dict] = None
            if self._fms_control:
                try:
                    ts = self._fms_control.get_tactical_status()
                except Exception:
                    logger.debug("SMS: FMS tactical status unavailable", exc_info=True)

            with self._lock:
                if ts:
                    tac = ts.get("tactical_systems", {})
                    self._cntm    = tac.get("countermeasures", self._cntm)
                    self._stealth = tac.get("stealth_mode",    self._stealth)
                    weapons_state = tac.get("weapons",         "SAFE")
                    self._flight_mode = ts.get("mode", self._flight_mode)

                    # Derive master arm from FMS weapons state
                    if weapons_state == "ARMED":
                        self._master_arm = "ARMED"
                    elif weapons_state == "READY":
                        self._master_arm = "TRAIN"
                    else:
                        self._master_arm = "SAFE"

                    # Simulated signature values (would come from sensor suite)
                    t = time.time()
                    self._rcs    = (0.001 if self._stealth == "ON"
                                   else 12 + 2 * abs(math.sin(t * 0.05)))
                    self._ir_sig = (0.05 if self._stealth == "ON"
                                   else 0.6 + 0.1 * abs(math.sin(t * 0.07 + 1)))
                    self._ecm    = ("ACTIVE" if self._cntm == "ACTIVE"
                                   else "STANDBY" if self._cntm in ("READY", "PASSIVE")
                                   else "INACTIVE")

                    # Propagate armed state to armed stations if master arm active
                    for sta in self._stations:
                        if sta.store and sta.store.state == "ARMED":
                            if self._master_arm == "SAFE":
                                # Master safe overrides individual arm
                                pass   # display shows individual state dimmed

            self._safe_update()

        except Exception as exc:
            logger.error(f"[SMS] Poll error: {exc}")
            logger.error(traceback.format_exc())

    # ──────────────────────────────────────────── computed properties ──────

    def _total_weight_kg(self) -> float:
        return sum(
            (s.store.weight_kg * max(s.store.qty, 1))
            for s in self._stations
            if s.store and s.store.state not in ("EMPTY", "EXPENDED", "JETTISONED")
        )

    def _armed_count(self) -> int:
        return sum(
            1 for s in self._stations
            if s.store and s.store.state == "ARMED"
        )

    # ───────────────────────────────────────────────────── paint ───────────

    def paint_display(self, painter: QPainter):
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.save()

            w = float(self.width())
            h = float(self.height())

            title_h  = h * 0.09
            body_h   = h * 0.73
            strip_h  = h - title_h - body_h

            plan_w   = w * 0.48
            detail_w = w - plan_w

            title_r  = QRectF(0,       0,          w,        title_h)
            plan_r   = QRectF(0,       title_h,    plan_w,   body_h)
            detail_r = QRectF(plan_w,  title_h,    detail_w, body_h)
            strip_r  = QRectF(0,       title_h + body_h, w, strip_h)

            with self._lock:
                self._draw_title(painter, title_r)
                self._draw_planform(painter, plan_r)
                self._draw_detail(painter, detail_r)
                self._draw_signature_strip(painter, strip_r)

            painter.restore()
        except Exception as exc:
            logger.error(f"[SMS] Paint error: {exc}")
            logger.error(traceback.format_exc())
            raise

    # ── title / master arm bar ───────────────────────────────────────────

    def _draw_title(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, QColor(14, 16, 24))
        arm_col = _MASTER_ARM_COLOUR.get(self._master_arm, _WHITE)

        # Left: system label
        f_sm = QFont("Monospace", 9)
        f_lg = QFont("Monospace", 10, QFont.Weight.Bold)

        lbl_r = QRectF(r.left() + 8, r.top(), r.width() * 0.30, r.height())
        painter.setFont(f_sm)
        painter.setPen(QPen(_DIM))
        painter.drawText(lbl_r, Qt.AlignmentFlag.AlignVCenter,
                         "STORES MANAGEMENT SYSTEM")

        # Centre: master arm (prominent)
        arm_r = QRectF(r.left() + r.width() * 0.30, r.top(),
                       r.width() * 0.25, r.height())
        painter.setFont(f_lg)
        painter.setPen(QPen(arm_col))
        painter.drawText(arm_r, Qt.AlignmentFlag.AlignCenter,
                         f"MASTER ARM: {self._master_arm}")

        # Right: release / delivery mode + summary counts
        right_r = QRectF(r.left() + r.width() * 0.56, r.top(),
                         r.width() * 0.42, r.height())
        painter.setFont(f_sm)
        painter.setPen(QPen(_DIM))
        summary = (f"REL: {self._release_mode}   "
                   f"DLVRY: {self._delivery_mode}   "
                   f"ARMED: {self._armed_count()}   "
                   f"LOAD: {self._total_weight_kg():.0f}kg")
        painter.drawText(right_r, Qt.AlignmentFlag.AlignVCenter |
                         Qt.AlignmentFlag.AlignRight, summary)

        # Bottom separator
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left()), int(r.bottom()),
                         int(r.right()), int(r.bottom()))

    # ── aircraft planform diagram ────────────────────────────────────────

    def _draw_planform(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, _BG)
        painter.setPen(QPen(_DIM, 1))
        painter.drawRect(r)

        # Planform drawing area (inset)
        pad   = 16.0
        pr    = r.adjusted(pad, pad, -pad, -pad)

        # Draw a simplified B-2 flying-wing planform silhouette
        self._draw_aircraft_silhouette(painter, pr)

        # Draw station markers
        for sta in self._stations:
            px = pr.left() + sta.rel_x * pr.width()
            py = pr.top()  + sta.rel_y * pr.height()
            self._draw_station_icon(painter, sta, QPointF(px, py))

    def _draw_aircraft_silhouette(self, painter: QPainter, r: QRectF):
        """Draw a schematic flying-wing outline."""
        cx  = r.left() + r.width()  / 2
        # Main wing outline (simplified W-shape for a flying wing)
        pts = [
            QPointF(cx,              r.top()  + r.height() * 0.20),  # nose
            QPointF(r.right() - 4,   r.top()  + r.height() * 0.50),  # right tip
            QPointF(cx + r.width() * 0.30, r.top() + r.height() * 0.78),  # right trailing notch
            QPointF(cx,              r.top()  + r.height() * 0.88),  # centreline trailing
            QPointF(cx - r.width() * 0.30, r.top() + r.height() * 0.78),  # left trailing notch
            QPointF(r.left()  + 4,   r.top()  + r.height() * 0.50),  # left tip
        ]
        path = QPainterPath()
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        path.closeSubpath()

        painter.setPen(QPen(_DIM, 1))
        painter.setBrush(QBrush(QColor(25, 30, 40)))
        painter.drawPath(path)

        # Internal bay outlines (dashed rectangles inside fuselage)
        dash_pen = QPen(_DIM, 1, Qt.PenStyle.DashLine)
        painter.setPen(dash_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        bay_w = r.width() * 0.12
        bay_h = r.height() * 0.36
        bay_top = r.top() + r.height() * 0.38

        # Left bay
        painter.drawRect(QRectF(cx - bay_w * 2.0, bay_top, bay_w, bay_h))
        # Right bay
        painter.drawRect(QRectF(cx + bay_w * 1.0, bay_top, bay_w, bay_h))

        # Centreline label
        f = QFont("Monospace", 7)
        painter.setFont(f)
        painter.setPen(QPen(_DIM))
        painter.drawText(
            QRectF(cx - 20, r.top() + r.height() * 0.24, 40, 12),
            Qt.AlignmentFlag.AlignCenter, "NOSE"
        )

    def _draw_station_icon(self, painter: QPainter, sta: _Station,
                           centre: QPointF):
        """Draw a single weapon station icon on the planform."""
        if sta.store is None or sta.store.state == "EMPTY":
            col  = _DIM
            size = 6.0
        else:
            col  = _STATE_COLOUR.get(sta.store.state, _WHITE)
            size = 9.0 if sta.internal else 7.0

        # Glow outline for armed stations
        if sta.store and sta.store.state == "ARMED" and self._master_arm == "ARMED":
            glow_pen = QPen(QColor(255, 60, 60, 80), 6)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(centre, size + 3, size + 3)

        # Main circle
        painter.setPen(QPen(col, 1))
        painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 100)))
        painter.drawEllipse(centre, size, size)

        # Station number label
        f = QFont("Monospace", 6)
        painter.setFont(f)
        painter.setPen(QPen(col))
        lbl_r = QRectF(centre.x() - 12, centre.y() + size + 1, 24, 10)
        painter.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter,
                         str(sta.station_id))

        # Store type abbreviation inside circle (if store present)
        if sta.store and sta.store.state not in ("EMPTY",):
            abbr = sta.store.name[:3]
            painter.setPen(QPen(col))
            inner_r = QRectF(centre.x() - size, centre.y() - size,
                             size * 2, size * 2)
            painter.setFont(QFont("Monospace", 5))
            painter.drawText(inner_r, Qt.AlignmentFlag.AlignCenter, abbr)

    # ── station detail table ─────────────────────────────────────────────

    def _draw_detail(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, _PANEL)
        painter.setPen(QPen(_DIM, 1))
        painter.drawRect(r)

        f_hd  = QFont("Monospace", 7, QFont.Weight.Bold)
        f_row = QFont("Monospace", 7)

        # Column widths (proportions of r.width())
        col_w = [0.12, 0.22, 0.10, 0.25, 0.15, 0.16]  # STA / NAME / QTY / STATE / WGT / TYPE
        col_labels = ["STA", "STORE", "QTY", "STATUS", "KG", "TYPE"]

        row_h  = min(18.0, (r.height() - 24) / (len(self._stations) + 1))
        hdr_y  = r.top() + 6

        # Header row
        painter.setFont(f_hd)
        painter.setPen(QPen(_DIM))
        x = r.left() + 4
        for label, frac in zip(col_labels, col_w):
            cw = r.width() * frac
            painter.drawText(QRectF(x, hdr_y, cw - 2, row_h),
                             Qt.AlignmentFlag.AlignVCenter, label)
            x += cw

        # Separator line
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left() + 2), int(hdr_y + row_h - 1),
                         int(r.right() - 2), int(hdr_y + row_h - 1))

        # Data rows
        painter.setFont(f_row)
        y = hdr_y + row_h

        for sta in self._stations:
            if y + row_h > r.bottom() - 4:
                break

            st   = sta.store
            col  = (_DIM if st is None or st.state in ("EMPTY", "JETTISONED")
                    else _STATE_COLOUR.get(st.state if st else "EMPTY", _WHITE))

            # Highlight row if this is the selected station
            if sta.station_id == self._selected_sta:
                painter.fillRect(
                    QRectF(r.left() + 2, y, r.width() - 4, row_h),
                    QColor(40, 50, 60)
                )

            values = [
                str(sta.station_id),
                (st.name if st else "—"),
                (str(st.qty) if st and st.state not in ("EMPTY",) else "—"),
                (st.state if st else "EMPTY"),
                (f"{st.weight_kg * max(st.qty, 1):.0f}" if st and st.qty > 0 else "—"),
                (st.store_type if st else "—"),
            ]

            x = r.left() + 4
            painter.setPen(QPen(col))
            for val, frac in zip(values, col_w):
                cw = r.width() * frac
                painter.drawText(QRectF(x, y, cw - 2, row_h),
                                 Qt.AlignmentFlag.AlignVCenter, val)
                x += cw

            # Thin separator
            if sta != self._stations[-1]:
                painter.setPen(QPen(QColor(30, 35, 45), 1))
                painter.drawLine(int(r.left() + 2), int(y + row_h - 1),
                                 int(r.right() - 2), int(y + row_h - 1))

            y += row_h

        # Totals row at bottom
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left() + 2), int(r.bottom() - row_h - 4),
                         int(r.right() - 2), int(r.bottom() - row_h - 4))

        painter.setFont(f_hd)
        painter.setPen(QPen(_WHITE))
        tot_r = QRectF(r.left() + 4, r.bottom() - row_h - 2,
                       r.width() - 8, row_h)
        painter.drawText(tot_r, Qt.AlignmentFlag.AlignVCenter |
                         Qt.AlignmentFlag.AlignRight,
                         f"TOTAL LOAD:  {self._total_weight_kg():.0f} kg    "
                         f"ARMED: {self._armed_count()} stas")

    # ── signature management strip ───────────────────────────────────────

    def _draw_signature_strip(self, painter: QPainter, r: QRectF):
        painter.fillRect(r, _DARK)
        painter.setPen(QPen(_DIM, 1))
        painter.drawLine(int(r.left()), int(r.top()),
                         int(r.right()), int(r.top()))

        f_lbl = QFont("Monospace", 7)
        f_val = QFont("Monospace", 8, QFont.Weight.Bold)

        items = [
            ("RCS",   f"{self._rcs:.3f} m²",
             _GREEN if self._rcs < 0.1 else _AMBER if self._rcs < 2.0 else _RED),
            ("IR SIG", f"{self._ir_sig * 100:.0f}%",
             _GREEN if self._ir_sig < 0.15 else _AMBER if self._ir_sig < 0.5 else _RED),
            ("ECM",   self._ecm,
             _GREEN if self._ecm == "ACTIVE" else
             _AMBER if self._ecm == "STANDBY" else _DIM),
            ("STEALTH", self._stealth,
             _CYAN if self._stealth == "ON" else _DIM),
            ("CNTM", self._cntm,
             _GREEN if self._cntm in ("ACTIVE", "READY") else
             _AMBER if self._cntm == "PASSIVE" else _DIM),
            ("MODE",  self._flight_mode,
             _RED if self._flight_mode == "COMBAT" else
             _CYAN if self._flight_mode == "STEALTH" else _GREEN),
        ]

        cell_w = r.width() / len(items)

        for i, (label, value, col) in enumerate(items):
            cx = r.left() + i * cell_w
            lbl_r = QRectF(cx + 2, r.top() + 2,   cell_w - 4, r.height() * 0.45)
            val_r = QRectF(cx + 2, r.top() + r.height() * 0.50,
                           cell_w - 4, r.height() * 0.48)

            painter.setFont(f_lbl)
            painter.setPen(QPen(_DIM))
            painter.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter, label)

            painter.setFont(f_val)
            painter.setPen(QPen(col))
            painter.drawText(val_r, Qt.AlignmentFlag.AlignCenter, value)

            if i > 0:
                painter.setPen(QPen(_DIM, 1))
                painter.drawLine(int(cx), int(r.top()),
                                 int(cx), int(r.bottom()))

    # ────────────────────────────────────────────── lifecycle ──────────────

    def stop(self):
        self._poll_timer.stop()
        super().stop()

    def cleanup(self):
        self._poll_timer.stop()
