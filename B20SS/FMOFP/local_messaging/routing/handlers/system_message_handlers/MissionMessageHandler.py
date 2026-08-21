"""
Mission Planning Message Handler

Handles LOCAL MISSION_* messages on the 1553B bus / local messaging stack.
Bridges the message routing layer to MissionService (phase, route, targets, OOB).

Architecture note
-----------------
MissionService (RT address 6) owns four subsystems — MissionData, RouteManager,
TargetingSystem, OrderOfBattle — coordinated through MissionControl.
All inputs from the scenario engine, HOTAS, or display keypad arrive as
typed dict messages and are forwarded to the appropriate MissionService method.

The handler also accepts radar-sourced target updates (from RadarDataFusion /
targeting radar), so targeting stays current without requiring the display
layer to relay them.

Singleton: get_mission_message_handler()
"""

import asyncio
import threading
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.core.event_driven_communication import get_event_bus, Event
from FMOFP.local_messaging.message_types import (
    MISSION_STATUS_REQUEST,
    MISSION_STATUS_RESPONSE,
    MISSION_PHASE_SET,
    MISSION_PHASE_ADVANCE,
    MISSION_WAYPOINT_ADD,
    MISSION_WAYPOINT_REMOVE,
    MISSION_TARGET_DESIGNATE,
    MISSION_TARGET_ENGAGE,
    MISSION_TARGET_BDA,
    MISSION_TARGET_UPDATE,
    MISSION_UNIT_ADD,
    MISSION_UNIT_UPDATE,
    MISSION_ROUTE_OPTIMISE,
    MISSION_OBJECTIVES_SET,
    MISSION_ROE_SET,
    MISSION_INTEL_UPDATE,
    MISSION_DATA_UPDATE,
)

logger = get_logger()

_mission_message_handler = None


class PendingMissionRequest:
    """Track a pending mission request."""

    def __init__(self, request_id: str, command_type: str, timeout: float = 5.0):
        self.request_id   = request_id
        self.command_type = command_type
        self.timestamp    = time.time()
        self.timeout      = timeout
        self.retry_count  = 0
        self.max_retries  = 3
        self.response: Optional[Dict] = None
        self.error:    Optional[str]  = None
        self.completed = False

    def is_expired(self) -> bool:
        return time.time() > self.timestamp + self.timeout

    def should_retry(self) -> bool:
        return not self.completed and self.retry_count < self.max_retries

    def increment_retry(self) -> int:
        self.retry_count += 1
        return self.retry_count

    def set_response(self, response: Dict) -> None:
        self.response  = response
        self.completed = True

    def set_error(self, error: str) -> None:
        self.error     = error
        self.completed = True


class MissionMessageHandler:
    """
    Message handler for the Mission Planning System (RT address 6).

    Receives typed dict messages from the routing layer and dispatches
    them to MissionService.  Emits status/data-update events back onto
    the event bus so the MFD mission page and TSD can stay current.
    """

    RT_ADDRESS = 6   # From rtAddressConfig.xml

    def __init__(self):
        self._lock            = threading.Lock()
        self._event_bus       = get_event_bus()
        self._mission_service = None   # lazy
        self._pending: Dict[str, PendingMissionRequest] = {}
        logger.info("[MISSION_HANDLER] MissionMessageHandler initialised")

    def start(self) -> None:
        """Called by SystemManager during startup sequence. No background thread needed."""
        logger.info("[MISSION_HANDLER] MissionMessageHandler started")

    # ------------------------------------------------------------------
    # Lazy service access

    def _get_mission(self):
        if self._mission_service is None:
            try:
                from FMOFP.Systems.missionPlanning.missionService import get_mission_service
                self._mission_service = get_mission_service()
            except Exception as exc:
                logger.warning(f"[MISSION_HANDLER] MissionService not ready: {exc}")
        return self._mission_service

    # ------------------------------------------------------------------
    # Primary entry point

    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """
        Dispatch a MISSION_* message to the appropriate MissionService call.
        Returns a response dict for status requests; None otherwise.
        """
        request_id = message.get("request_id", str(uuid.uuid4()))
        msg_type   = message.get("message_type", "")
        params     = message.get("params", message.get("data", {}))
        if not isinstance(params, dict):
            params = {}

        logger.debug(f"[MISSION_HANDLER] {msg_type} (req={request_id})")

        try:
            ms = self._get_mission()
            if ms is None:
                self._queue_pending(request_id, msg_type)
                return None

            # ── Phase management ────────────────────────────────────

            if msg_type in (MISSION_STATUS_REQUEST, "mission_statusRequest"):
                return await self._handle_status_request(request_id)

            elif msg_type in (MISSION_PHASE_SET, "mission_phaseSet"):
                phase = params.get("phase", "")
                if phase:
                    ms.set_phase(str(phase))
                    logger.info(f"[MISSION_HANDLER] Phase → {phase}")

            elif msg_type in (MISSION_PHASE_ADVANCE, "mission_phaseAdvance"):
                new_phase = ms.advance_phase()
                logger.info(f"[MISSION_HANDLER] Phase advanced → {new_phase}")

            # ── Route / waypoints ────────────────────────────────────

            elif msg_type in (MISSION_WAYPOINT_ADD, "mission_waypointAdd"):
                wp = ms.add_waypoint(
                    name    = params.get("name", "WP"),
                    lat     = float(params.get("lat", 0)),
                    lon     = float(params.get("lon", 0)),
                    alt_ft  = float(params.get("alt_ft", 0)),
                    wp_type = params.get("wp_type", "NAV"),
                )
                logger.info(f"[MISSION_HANDLER] Waypoint added: {wp.get('name')}")

            elif msg_type in (MISSION_WAYPOINT_REMOVE, "mission_waypointRemove"):
                wp_id = params.get("wp_id")
                if wp_id is not None:
                    ms._ctrl.route.remove_waypoint(int(wp_id))
                    logger.info(f"[MISSION_HANDLER] Waypoint {wp_id} removed")

            elif msg_type in (MISSION_ROUTE_OPTIMISE, "mission_routeOptimise"):
                adjusted = ms.optimise_route()
                logger.info(f"[MISSION_HANDLER] Route optimised ({adjusted} waypoints adjusted)")

            # ── Target lifecycle ─────────────────────────────────────

            elif msg_type in (MISSION_TARGET_DESIGNATE, "mission_targetDesignate"):
                tgt = ms.designate_target(
                    name        = params.get("name", "TGT"),
                    lat         = float(params.get("lat", 0)),
                    lon         = float(params.get("lon", 0)),
                    alt_ft      = float(params.get("alt_ft", 0)),
                    priority    = int(params.get("priority", 3)),
                    target_type = params.get("target_type", "POINT"),
                )
                logger.info(f"[MISSION_HANDLER] Target designated: {tgt.get('id')} '{tgt.get('name')}'")
                await self._emit_data_update(ms)

            elif msg_type in (MISSION_TARGET_ENGAGE, "mission_targetEngage"):
                target_id = params.get("target_id", "")
                weapon    = params.get("weapon", "UNSPECIFIED")
                if target_id:
                    result = ms.engage_target(target_id, weapon)
                    logger.info(f"[MISSION_HANDLER] Engage {target_id} with {weapon}: {result}")
                    await self._emit_data_update(ms)

            elif msg_type in (MISSION_TARGET_BDA, "mission_targetBDA"):
                target_id = params.get("target_id", "")
                destroyed = bool(params.get("destroyed", False))
                if target_id:
                    ms._ctrl.targeting.mark_bda_pending(target_id)
                    ms._ctrl.targeting.assess_damage(target_id, destroyed)
                    logger.info(f"[MISSION_HANDLER] BDA {target_id}: {'DESTROYED' if destroyed else 'SURVIVED'}")
                    await self._emit_data_update(ms)

            elif msg_type in (MISSION_TARGET_UPDATE, "mission_targetUpdate"):
                # Radar-sourced position fix for an existing target
                target_id = params.get("target_id", "")
                if target_id:
                    ms.radar_target_update(
                        target_id    = target_id,
                        lat          = float(params.get("lat", 0)),
                        lon          = float(params.get("lon", 0)),
                        alt_ft       = float(params.get("alt_ft", 0)),
                        speed        = float(params.get("speed_kts", 0)),
                        heading      = float(params.get("heading_deg", 0)),
                        quality      = float(params.get("track_quality", 0.8)),
                    )

            # ── OOB management ───────────────────────────────────────

            elif msg_type in (MISSION_UNIT_ADD, "mission_unitAdd"):
                unit_data = params.get("unit_data", params)
                unit = ms.add_unit(unit_data)
                if unit:
                    logger.info(f"[MISSION_HANDLER] OOB unit added: {unit.get('id')}")

            elif msg_type in (MISSION_UNIT_UPDATE, "mission_unitUpdate"):
                unit_id = params.get("unit_id", "")
                if unit_id:
                    pos = params.get("position")
                    if pos and len(pos) >= 2:
                        ms._ctrl.update_unit_position(
                            unit_id,
                            float(pos[0]), float(pos[1]),
                            float(pos[2]) if len(pos) > 2 else 0.0,
                        )
                    status = params.get("status")
                    if status:
                        ms._ctrl.oob.update_status(unit_id, str(status))
                    heading = params.get("heading_deg")
                    speed   = params.get("speed_kts")
                    if heading is not None and speed is not None:
                        ms._ctrl.oob.update_heading_speed(unit_id, float(heading), float(speed))

            # ── Mission data ─────────────────────────────────────────

            elif msg_type in (MISSION_OBJECTIVES_SET, "mission_objectivesSet"):
                objs = params.get("objectives", [])
                ms.set_objectives(objs)
                logger.info(f"[MISSION_HANDLER] Objectives set ({len(objs)})")

            elif msg_type in (MISSION_ROE_SET, "mission_roeSet"):
                rules = params.get("rules", [])
                ms.set_roe(rules)
                logger.info(f"[MISSION_HANDLER] ROE set ({len(rules)} rules)")

            elif msg_type in (MISSION_INTEL_UPDATE, "mission_intelUpdate"):
                data = params.get("data", params)
                ms.update_intelligence(data)
                logger.info(f"[MISSION_HANDLER] Intelligence updated ({len(data)} entries)")

            else:
                logger.debug(f"[MISSION_HANDLER] Unhandled type: {msg_type}")

        except Exception as exc:
            logger.error(f"[MISSION_HANDLER] Error handling {msg_type}: {exc}")
            logger.error(traceback.format_exc())

        return None

    # ------------------------------------------------------------------
    # Status request / data update events

    async def _handle_status_request(self, request_id: str) -> Dict:
        ms = self._get_mission()
        try:
            data = ms.get_data() if ms else {}
        except Exception as exc:
            logger.warning(f"[MISSION_HANDLER] get_data() failed: {exc}")
            data = {}

        response = {
            "message_type": MISSION_STATUS_RESPONSE,
            "request_id":   request_id,
            "timestamp":    time.time(),
            "data":         data,
        }
        try:
            # See NOTE in CommsMessageHandler.py: EventBus has no emit(),
            # only synchronous publish(Event(...)).
            self._event_bus.publish(Event(topic="mission_status_response", data=response))
        except Exception as exc:
            logger.debug(f"[MISSION_HANDLER] Event bus emit failed: {exc}")
        return response

    async def _emit_data_update(self, ms) -> None:
        """Push a MISSION_DATA_UPDATE event so displays stay current."""
        try:
            data = ms.get_data()
            # See NOTE above: EventBus has no emit(), only synchronous
            # publish(Event(...)).
            self._event_bus.publish(Event(topic=MISSION_DATA_UPDATE, data={
                "message_type": MISSION_DATA_UPDATE,
                "timestamp":    time.time(),
                "data":         data,
            }))
        except Exception as exc:
            logger.debug(f"[MISSION_HANDLER] Data update emit failed: {exc}")

    # ------------------------------------------------------------------
    # Pending / retry

    def _queue_pending(self, request_id: str, command_type: str) -> None:
        with self._lock:
            self._pending[request_id] = PendingMissionRequest(request_id, command_type)

    def retry_pending(self) -> int:
        """Flush expired pending requests. Returns count cleared."""
        if not self._pending:
            return 0
        with self._lock:
            expired = [rid for rid, req in self._pending.items() if req.is_expired()]
            for rid in expired:
                del self._pending[rid]
                logger.warning(f"[MISSION_HANDLER] Request {rid} expired without retry")
        return len(expired)

    # ------------------------------------------------------------------
    # Health

    def get_status(self) -> Dict[str, Any]:
        ms = self._get_mission()
        return {
            "handler":        "MissionMessageHandler",
            "rt_address":     self.RT_ADDRESS,
            "mission_ready":  ms is not None,
            "pending_count":  len(self._pending),
        }


def get_mission_message_handler() -> MissionMessageHandler:
    global _mission_message_handler
    if _mission_message_handler is None:
        _mission_message_handler = MissionMessageHandler()
    return _mission_message_handler
