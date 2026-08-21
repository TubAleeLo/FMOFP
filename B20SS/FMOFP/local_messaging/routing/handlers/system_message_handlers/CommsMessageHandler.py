"""
Communications Message Handler

Handles LOCAL COMMS_* messages on the 1553B bus / local messaging stack.
Bridges the message routing layer to CommsService (radio, satcom, data-link).

Architecture note
-----------------
This handler is the mirror of FMSMessageHandler for the Communications
system.  CommsService (RT address 2) owns three subsystems — Radio, SatCom,
and DataLink — and does NOT maintain its own 1553B messenger.  All pilot /
operator inputs arrive here as typed dict messages from the routing layer
and are forwarded synchronously to the appropriate CommsService method.

Singleton: get_comms_message_handler()
"""

import asyncio
import threading
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.core.event_driven_communication import get_event_bus, Event
from FMOFP.local_messaging.message_types import (
    COMMS_STATUS_REQUEST,
    COMMS_STATUS_RESPONSE,
    COMMS_RADIO_FREQ_SET,
    COMMS_RADIO_MODE_SET,
    COMMS_SATCOM_ACQUIRE,
    COMMS_DATALINK_MODE_SET,
    COMMS_TRANSMIT_RADIO,
    COMMS_SEND_SATCOM,
    COMMS_SEND_DATALINK,
    COMMS_DATA_UPDATE,
)

logger = get_logger()

_comms_message_handler = None


class PendingCommsRequest:
    """Track a pending request awaiting a CommsService response."""

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


class CommsMessageHandler:
    """
    Message handler for the Communications System (RT address 2).

    Receives typed dict messages from the routing layer and dispatches
    them to CommsService.  Emits status-response events back onto the
    event bus so displays can subscribe without polling.
    """

    RT_ADDRESS = 2   # From rtAddressConfig.xml

    def __init__(self):
        self._lock          = threading.Lock()
        self._event_bus     = get_event_bus()
        self._comms_service = None   # lazy — fetched on first use
        self._pending: Dict[str, PendingCommsRequest] = {}
        logger.info("[COMMS_HANDLER] CommsMessageHandler initialised")

    def start(self) -> None:
        """Called by SystemManager during startup sequence. No background thread needed."""
        logger.info("[COMMS_HANDLER] CommsMessageHandler started")

    # ------------------------------------------------------------------
    # Lazy service access

    def _get_comms(self):
        if self._comms_service is None:
            try:
                from FMOFP.Systems.comms.messaging_service import get_comms_service
                self._comms_service = get_comms_service()
            except Exception as exc:
                logger.warning(f"[COMMS_HANDLER] CommsService not ready: {exc}")
        return self._comms_service

    # ------------------------------------------------------------------
    # Primary entry point

    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """
        Dispatch a COMMS_* message to the appropriate CommsService call.
        Returns a response dict for status requests; None otherwise.
        """
        request_id = message.get("request_id", str(uuid.uuid4()))
        msg_type   = message.get("message_type", "")
        params     = message.get("params", message.get("data", {}))
        if not isinstance(params, dict):
            params = {}

        logger.debug(f"[COMMS_HANDLER] {msg_type} (req={request_id})")

        try:
            cs = self._get_comms()
            if cs is None:
                self._queue_pending(request_id, msg_type)
                return None

            if msg_type in (COMMS_STATUS_REQUEST, "comms_statusRequest"):
                return await self._handle_status_request(request_id)

            elif msg_type in (COMMS_RADIO_FREQ_SET, "comms_radioFreqSet"):
                freq = params.get("frequency")
                if freq is not None:
                    cs.set_radio_frequency(float(freq))
                    logger.info(f"[COMMS_HANDLER] Radio freq → {freq} MHz")

            elif msg_type in (COMMS_RADIO_MODE_SET, "comms_radioModeSet"):
                mode = params.get("mode")
                if mode:
                    cs.set_radio_mode(str(mode))
                    logger.info(f"[COMMS_HANDLER] Radio mode → {mode}")

            elif msg_type in (COMMS_SATCOM_ACQUIRE, "comms_satcomAcquire"):
                cs.acquire_satellite()
                logger.info("[COMMS_HANDLER] Satellite acquisition triggered")

            elif msg_type in (COMMS_DATALINK_MODE_SET, "comms_datalinkModeSet"):
                mode = params.get("mode")
                if mode:
                    cs.set_datalink_mode(str(mode))
                    logger.info(f"[COMMS_HANDLER] DataLink mode → {mode}")

            elif msg_type in (COMMS_TRANSMIT_RADIO, "comms_transmitRadio"):
                result = cs.transmit_radio(str(params.get("message", "")))
                logger.info(f"[COMMS_HANDLER] Radio TX: {result}")

            elif msg_type in (COMMS_SEND_SATCOM, "comms_sendSatcom"):
                result = cs.send_satcom(str(params.get("message", "")))
                logger.info(f"[COMMS_HANDLER] SatCom TX: {result}")

            elif msg_type in (COMMS_SEND_DATALINK, "comms_sendDatalink"):
                priority = int(params.get("priority", 2))
                result   = cs.send_datalink(str(params.get("message", "")), priority)
                logger.info(f"[COMMS_HANDLER] DataLink TX pri={priority}: {result}")

            else:
                logger.debug(f"[COMMS_HANDLER] Unhandled type: {msg_type}")

        except Exception as exc:
            logger.error(f"[COMMS_HANDLER] Error handling {msg_type}: {exc}")
            logger.error(traceback.format_exc())

        return None

    # ------------------------------------------------------------------
    # Status request / response

    async def _handle_status_request(self, request_id: str) -> Dict:
        cs = self._get_comms()
        try:
            status_data = cs.get_status() if cs else {}
        except Exception as exc:
            logger.warning(f"[COMMS_HANDLER] get_status() failed: {exc}")
            status_data = {}

        response = {
            "message_type": COMMS_STATUS_RESPONSE,
            "request_id":   request_id,
            "timestamp":    time.time(),
            "status":       status_data,
        }
        try:
            # NOTE: EventBus (event_driven_communication.py) has no emit()
            # method at all - only publish(Event(...)), which is also
            # synchronous, not awaitable. This previously raised
            # "AttributeError: 'EventBus' object has no attribute 'emit'"
            # every time, silently swallowed by this except block (logged
            # only at DEBUG level), meaning this status response event was
            # never actually published to any subscriber.
            self._event_bus.publish(Event(topic="comms_status_response", data=response))
        except Exception as exc:
            logger.debug(f"[COMMS_HANDLER] Event bus emit failed: {exc}")
        return response

    # ------------------------------------------------------------------
    # Pending / retry

    def _queue_pending(self, request_id: str, command_type: str) -> None:
        with self._lock:
            self._pending[request_id] = PendingCommsRequest(request_id, command_type)

    def retry_pending(self) -> int:
        """Flush expired pending requests. Returns count cleared."""
        if not self._pending:
            return 0
        with self._lock:
            expired = [rid for rid, req in self._pending.items() if req.is_expired()]
            for rid in expired:
                del self._pending[rid]
                logger.warning(f"[COMMS_HANDLER] Request {rid} expired without retry")
        return len(expired)

    # ------------------------------------------------------------------
    # Health

    def get_status(self) -> Dict[str, Any]:
        cs = self._get_comms()
        return {
            "handler":       "CommsMessageHandler",
            "rt_address":    self.RT_ADDRESS,
            "comms_ready":   cs is not None,
            "pending_count": len(self._pending),
        }


def get_comms_message_handler() -> CommsMessageHandler:
    global _comms_message_handler
    if _comms_message_handler is None:
        _comms_message_handler = CommsMessageHandler()
    return _comms_message_handler
