"""
MIL-STD-1553B Bus Adapter Layer

Closes PLANNING.md Next Steps item 12 ("Hardware interface — optional real
MIL-STD-1553B hardware adapter integration") to the extent possible without
physical hardware: this module is the single, documented integration point
where a real 1553B interface card (Alta, DDC, Abaco/GE, AIM, ...) plugs into
FMOFP. Everything above this layer — BC_sender, RT_sender, the block-transfer
protocol, message construction — is transport-agnostic and does not change
when the transport does.

Design
------
A BusAdapter moves an already-encoded payload (the JSON-serialized frame
message the senders build today) from one bus participant to the other. Three
implementations ship:

  * SocketBusAdapter   — the default. Reproduces the original behavior of
                         BC_socket/RT_socket exactly: one short-lived TCP
                         connection to the peer's loopback listener per
                         transmit (BC → localhost:5001 where RT_Listener
                         listens; RT → localhost:5000 where BC_Listener
                         listens). The receive side remains the existing
                         BC_Listener/RT_Listener threads, untouched.

  * LoopbackBusAdapter — in-process test double. Transmits are delivered
                         synchronously to the peer role's receive callback
                         (or queued if none is registered). No sockets. Used
                         by Tests/test_bus_adapter.py.

  * HardwareBusAdapter — the real-hardware integration template. It holds no
                         vendor code (none can be written or verified without
                         a physical card on a physical bus); instead it
                         delegates to a driver object registered at runtime
                         via register_hardware_driver(), and fails with an
                         instructive error when none is registered. The
                         driver contract is documented on the class.

Selection is per role ('bc' / 'rt') via busAdapterConfig.xml next to the
other FMOFP config XMLs; when the file is absent or unparseable the socket
adapter with its historical defaults is used, so a stock checkout behaves
byte-for-byte as before this layer existed.

Public API
----------
  get_bus_adapter(role)             -> BusAdapter singleton for 'bc' or 'rt'
  register_hardware_driver(role, d) -> install a vendor driver object
  reset_bus_adapters()              -> drop cached adapters (tests only)
"""

import os
import socket
import threading
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Dict, Optional
from xml.etree import ElementTree as ET

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Historical transport constants, unchanged since the initial commit:
# BC_Listener accepts on 5000, RT_Listener accepts on 5001, both loopback-only
# (see BC_socket.py setup_socket() for why binding wider was rejected).
_ROLE_DEFAULTS = {
    "bc": {"peer_host": "localhost", "peer_port": 5001},  # BC transmits to RT
    "rt": {"peer_host": "localhost", "peer_port": 5000},  # RT transmits to BC
}

_VALID_ROLES = tuple(_ROLE_DEFAULTS)

_CONFIG_BASENAME = "busAdapterConfig.xml"


# ── Interface ─────────────────────────────────────────────────────────────────

class BusAdapter(ABC):
    """Transport abstraction for one bus participant (BC or RT)."""

    #: adapter-type string, set by subclasses ("socket", "loopback", "hardware")
    adapter_type: str = "abstract"

    def __init__(self, role: str):
        if role not in _VALID_ROLES:
            raise ValueError(f"Bus adapter role must be one of {_VALID_ROLES}, got {role!r}")
        self.role = role
        self._receive_callback: Optional[Callable[[bytes], None]] = None

    # -- lifecycle ------------------------------------------------------------

    def open(self) -> None:
        """Acquire transport resources. Socket adapter needs none (it connects
        per transmit); hardware adapters open the device here."""

    def close(self) -> None:
        """Release transport resources."""

    # -- data path ------------------------------------------------------------

    @abstractmethod
    def transmit(self, payload: bytes) -> bool:
        """Deliver one encoded message to the peer. Returns True on success.
        Must not raise for ordinary delivery failures — log and return False,
        matching the original inline socket code's contract."""

    def set_receive_callback(self, callback: Optional[Callable[[bytes], None]]) -> None:
        """Register a callable invoked with each payload received from the
        peer. The socket adapter does not use this (BC_Listener/RT_Listener
        remain the receive path); loopback and hardware adapters do."""
        self._receive_callback = callback

    # -- introspection --------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return {"role": self.role, "type": self.adapter_type}


# ── Socket (default) ──────────────────────────────────────────────────────────

class SocketBusAdapter(BusAdapter):
    """The original FMOFP transport: one short-lived TCP connection to the
    peer's loopback listener per transmit. Behavior (connect → sendall →
    close; ConnectionRefusedError and generic errors logged, False returned)
    is copied verbatim from the blocks it replaced in BC_socket.py /
    RT_socket.py so this refactor is behavior-neutral."""

    adapter_type = "socket"

    def __init__(self, role: str, peer_host: Optional[str] = None,
                 peer_port: Optional[int] = None):
        super().__init__(role)
        defaults = _ROLE_DEFAULTS[role]
        self.peer_host = peer_host or defaults["peer_host"]
        self.peer_port = int(peer_port or defaults["peer_port"])

    def transmit(self, payload: bytes) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                logger.info(
                    f"{self.role.upper()} bus adapter connecting to "
                    f"{self.peer_host}:{self.peer_port}"
                )
                sock.connect((self.peer_host, self.peer_port))
                sock.sendall(payload)
                return True
        except ConnectionRefusedError:
            logger.error(f"Connection refused to {self.peer_host}:{self.peer_port}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    def describe(self) -> Dict[str, Any]:
        d = super().describe()
        d.update({"peer_host": self.peer_host, "peer_port": self.peer_port})
        return d


# ── Loopback (tests) ──────────────────────────────────────────────────────────

class LoopbackBusAdapter(BusAdapter):
    """In-process transport: a transmit on one role is delivered synchronously
    to the other role's receive callback, or queued on the peer until one is
    registered. Lets the adapter plumbing be tested with no sockets and no
    listener threads."""

    adapter_type = "loopback"

    _peers: Dict[str, "LoopbackBusAdapter"] = {}
    _peers_lock = threading.Lock()

    def __init__(self, role: str):
        super().__init__(role)
        self.received: deque = deque(maxlen=256)  # payloads delivered to this role
        with LoopbackBusAdapter._peers_lock:
            LoopbackBusAdapter._peers[role] = self

    def transmit(self, payload: bytes) -> bool:
        peer_role = "rt" if self.role == "bc" else "bc"
        with LoopbackBusAdapter._peers_lock:
            peer = LoopbackBusAdapter._peers.get(peer_role)
        if peer is None:
            logger.warning(
                f"[BUS_ADAPTER] Loopback transmit from {self.role} dropped: "
                f"no {peer_role} loopback adapter exists"
            )
            return False
        peer.received.append(payload)
        if peer._receive_callback is not None:
            try:
                peer._receive_callback(payload)
            except Exception as e:
                logger.error(f"[BUS_ADAPTER] Loopback receive callback error: {e}")
                return False
        return True


# ── Hardware (integration template) ───────────────────────────────────────────

class HardwareBusAdapter(BusAdapter):
    """Integration point for a physical MIL-STD-1553B interface card.

    No vendor code ships here — it cannot be written or verified without a
    physical card on a physical bus (PLANNING.md item 12 is *optional* for
    exactly that reason). Instead, a deployment with real hardware implements
    a small driver object and registers it:

        from FMOFP.MIL_STD_1553B.bus_adapter import register_hardware_driver

        class AltaDriver:                     # example — any vendor SDK
            def open(self):    ...            # open card / channel
            def close(self):   ...            # release card
            def transmit(self, payload: bytes) -> bool:
                ...                           # put words on the wire
            def set_receive_callback(self, cb):   # optional
                ...                           # deliver received words to cb

        register_hardware_driver('bc', AltaDriver())

    then selects type="hardware" in busAdapterConfig.xml. The driver decides
    how FMOFP's JSON frame payloads map onto its card's word API — typically
    by decoding the 20-bit frame strings the senders already produce (sync
    bits + 16 data/command bits + parity, see BC_msg.BC_construct).

    Until a driver is registered, every operation fails with an instructive
    error rather than pretending hardware exists.
    """

    adapter_type = "hardware"

    def __init__(self, role: str):
        super().__init__(role)
        self._driver: Optional[Any] = None

    def _require_driver(self) -> Any:
        if self._driver is None:
            raise NotImplementedError(
                f"No MIL-STD-1553B hardware driver registered for role "
                f"'{self.role}'. Real-bus operation requires a physical "
                f"interface card and a vendor driver object — see "
                f"HardwareBusAdapter's docstring and call "
                f"register_hardware_driver('{self.role}', driver) before "
                f"selecting type=\"hardware\" in {_CONFIG_BASENAME}."
            )
        return self._driver

    def register_driver(self, driver: Any) -> None:
        for required in ("open", "close", "transmit"):
            if not callable(getattr(driver, required, None)):
                raise TypeError(
                    f"Hardware driver for role '{self.role}' must provide a "
                    f"callable .{required}() — got {type(driver).__name__}"
                )
        self._driver = driver
        if self._receive_callback is not None and callable(
            getattr(driver, "set_receive_callback", None)
        ):
            driver.set_receive_callback(self._receive_callback)
        logger.info(
            f"[BUS_ADAPTER] Hardware driver {type(driver).__name__} "
            f"registered for role '{self.role}'"
        )

    def open(self) -> None:
        self._require_driver().open()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    def transmit(self, payload: bytes) -> bool:
        try:
            return bool(self._require_driver().transmit(payload))
        except NotImplementedError:
            raise
        except Exception as e:
            logger.error(f"[BUS_ADAPTER] Hardware transmit error: {e}")
            return False

    def set_receive_callback(self, callback) -> None:
        super().set_receive_callback(callback)
        if self._driver is not None and callable(
            getattr(self._driver, "set_receive_callback", None)
        ):
            self._driver.set_receive_callback(callback)


# ── Configuration + factory ───────────────────────────────────────────────────

_adapters: Dict[str, BusAdapter] = {}
_adapters_lock = threading.Lock()

_ADAPTER_CLASSES = {
    "socket": SocketBusAdapter,
    "loopback": LoopbackBusAdapter,
    "hardware": HardwareBusAdapter,
}


def _config_path() -> str:
    # Same resolution scheme as the other FMOFP config XMLs (they live in the
    # FMOFP package directory, resolved relative to this source tree).
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        _CONFIG_BASENAME)


def _load_config() -> Dict[str, Dict[str, Any]]:
    """Parse busAdapterConfig.xml → {role: {type, peer_host?, peer_port?}}.
    Missing file or any parse problem degrades to the socket default so a
    stock checkout never changes behavior because of this layer."""
    path = os.path.normpath(_config_path())
    config: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(path):
        return config
    try:
        root = ET.parse(path).getroot()
        for elem in root.findall(".//adapter"):
            role = (elem.get("role") or "").strip().lower()
            if role not in _VALID_ROLES:
                logger.warning(f"[BUS_ADAPTER] Ignoring adapter config with role={role!r}")
                continue
            entry: Dict[str, Any] = {
                "type": (elem.get("type") or "socket").strip().lower()
            }
            if elem.get("peer_host"):
                entry["peer_host"] = elem.get("peer_host").strip()
            if elem.get("peer_port"):
                entry["peer_port"] = int(elem.get("peer_port"))
            config[role] = entry
    except Exception as e:
        logger.error(
            f"[BUS_ADAPTER] Failed to parse {path} ({e}) — "
            f"falling back to socket adapters"
        )
        return {}
    return config


def get_bus_adapter(role: str) -> BusAdapter:
    """Return the process-wide adapter for 'bc' or 'rt', creating it from
    busAdapterConfig.xml (default: socket with historical host/port) on first
    use."""
    if role not in _VALID_ROLES:
        raise ValueError(f"Bus adapter role must be one of {_VALID_ROLES}, got {role!r}")
    with _adapters_lock:
        adapter = _adapters.get(role)
        if adapter is None:
            entry = _load_config().get(role, {})
            adapter_type = entry.get("type", "socket")
            cls = _ADAPTER_CLASSES.get(adapter_type)
            if cls is None:
                logger.warning(
                    f"[BUS_ADAPTER] Unknown adapter type {adapter_type!r} for "
                    f"role '{role}' — using socket"
                )
                cls = SocketBusAdapter
            if cls is SocketBusAdapter:
                adapter = SocketBusAdapter(
                    role,
                    peer_host=entry.get("peer_host"),
                    peer_port=entry.get("peer_port"),
                )
            else:
                adapter = cls(role)
            _adapters[role] = adapter
            logger.info(f"[BUS_ADAPTER] Created {adapter.describe()} for role '{role}'")
        return adapter


def register_hardware_driver(role: str, driver: Any) -> None:
    """Install a vendor driver on the (hardware) adapter for `role`. See
    HardwareBusAdapter's docstring for the driver contract."""
    adapter = get_bus_adapter(role)
    if not isinstance(adapter, HardwareBusAdapter):
        raise RuntimeError(
            f"Adapter for role '{role}' is type '{adapter.adapter_type}', not "
            f"'hardware' — set type=\"hardware\" for it in {_CONFIG_BASENAME} "
            f"before registering a driver."
        )
    adapter.register_driver(driver)


def reset_bus_adapters() -> None:
    """Drop all cached adapters (and loopback pairings). Test use only."""
    with _adapters_lock:
        for adapter in _adapters.values():
            try:
                adapter.close()
            except Exception:
                pass
        _adapters.clear()
    with LoopbackBusAdapter._peers_lock:
        LoopbackBusAdapter._peers.clear()
