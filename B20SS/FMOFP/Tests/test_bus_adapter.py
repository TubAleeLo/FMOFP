"""Test suite — MIL-STD-1553B bus adapter layer (bus_adapter.py).

Covers the transport abstraction added in the August 2026 completion pass
(PLANNING.md Next Steps item 12):
  1. Factory defaults: no config / stock config → SocketBusAdapter with the
     historical host/port values, cached per role.
  2. Socket adapter really transmits: payload arrives at a scratch TCP
     listener, byte-for-byte.
  3. Socket adapter failure contract: connection refused → False, no raise
     (the contract BC_sender/RT_sender rely on).
  4. Loopback adapter: bc→rt and rt→bc delivery, callback + queue paths.
  5. Hardware adapter: instructive NotImplementedError without a driver,
     driver-contract validation, delegation once a driver is registered.
  6. Sender integration: BC_sender/RT_sender construct against the adapter
     layer and route sends through it.

Standalone-safe: run from B20SS/ as `python -m FMOFP.Tests.test_bus_adapter`.
"""
import socket
import sys
import threading

sys.path.insert(0, '.')

from FMOFP.MIL_STD_1553B import bus_adapter as ba

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ── 1. factory defaults ───────────────────────────────────────────────────────

ba.reset_bus_adapters()
bc = ba.get_bus_adapter('bc')
rt = ba.get_bus_adapter('rt')
check("factory: bc default is socket adapter", isinstance(bc, ba.SocketBusAdapter))
check("factory: rt default is socket adapter", isinstance(rt, ba.SocketBusAdapter))
check("factory: bc historical peer port 5001", bc.describe().get("peer_port") == 5001,
      str(bc.describe()))
check("factory: rt historical peer port 5000", rt.describe().get("peer_port") == 5000,
      str(rt.describe()))
check("factory: per-role singleton", ba.get_bus_adapter('bc') is bc)
try:
    ba.get_bus_adapter('nonsense')
    check("factory: invalid role rejected", False)
except ValueError:
    check("factory: invalid role rejected", True)

# ── 2. socket adapter transmits for real ─────────────────────────────────────

received = []
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 0))
server.listen(1)
scratch_port = server.getsockname()[1]


def _accept_once():
    conn, _ = server.accept()
    chunks = []
    while True:
        data = conn.recv(4096)
        if not data:
            break
        chunks.append(data)
    received.append(b"".join(chunks))
    conn.close()


listener = threading.Thread(target=_accept_once, daemon=True)
listener.start()

probe = ba.SocketBusAdapter('bc', peer_host="127.0.0.1", peer_port=scratch_port)
payload = b'{"frames": ["10000000000000000001"], "request_id": "test-123"}'
ok = probe.transmit(payload)
listener.join(timeout=5)
server.close()
check("socket: transmit returns True", ok is True)
check("socket: payload arrives byte-for-byte",
      received and received[0] == payload, str(received))

# ── 3. socket adapter failure contract ───────────────────────────────────────

# A port with nothing listening: bind-then-close guarantees it's free.
tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tmp.bind(("127.0.0.1", 0))
dead_port = tmp.getsockname()[1]
tmp.close()
refused = ba.SocketBusAdapter('rt', peer_host="127.0.0.1", peer_port=dead_port)
check("socket: connection refused → False, no raise",
      refused.transmit(b"x") is False)

# ── 4. loopback adapter ──────────────────────────────────────────────────────

ba.reset_bus_adapters()
lb_bc = ba.LoopbackBusAdapter('bc')
lb_rt = ba.LoopbackBusAdapter('rt')

got = []
lb_rt.set_receive_callback(got.append)
check("loopback: bc→rt transmit returns True", lb_bc.transmit(b"hello-rt") is True)
check("loopback: rt callback received payload", got == [b"hello-rt"], str(got))
check("loopback: rt queue holds payload", list(lb_rt.received) == [b"hello-rt"])

check("loopback: rt→bc without callback still queues",
      lb_rt.transmit(b"hello-bc") is True and list(lb_bc.received) == [b"hello-bc"])

# ── 5. hardware adapter ──────────────────────────────────────────────────────

hw = ba.HardwareBusAdapter('bc')
try:
    hw.transmit(b"x")
    check("hardware: transmit without driver raises", False)
except NotImplementedError as e:
    check("hardware: transmit without driver raises", True)
    check("hardware: error names register_hardware_driver",
          "register_hardware_driver" in str(e), str(e))

try:
    hw.register_driver(object())
    check("hardware: driver contract validated", False)
except TypeError:
    check("hardware: driver contract validated", True)


class FakeDriver:
    def __init__(self):
        self.sent = []
        self.opened = False

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def transmit(self, payload):
        self.sent.append(payload)
        return True


drv = FakeDriver()
hw.register_driver(drv)
hw.open()
check("hardware: open delegates to driver", drv.opened is True)
check("hardware: transmit delegates to driver",
      hw.transmit(b"words-on-the-wire") is True and drv.sent == [b"words-on-the-wire"])
hw.close()
check("hardware: close delegates to driver", drv.opened is False)

# register_hardware_driver() guard: role's configured adapter is socket here
ba.reset_bus_adapters()
try:
    ba.register_hardware_driver('bc', FakeDriver())
    check("hardware: register on non-hardware role rejected", False)
except RuntimeError:
    check("hardware: register on non-hardware role rejected", True)

# ── 6. sender integration ────────────────────────────────────────────────────

ba.reset_bus_adapters()
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_connect.BC_socket import BC_sender
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import RT_sender

bc_sender = BC_sender(max_workers=1)
rt_sender = RT_sender(max_workers=1)
check("integration: BC_sender uses the bus adapter layer",
      isinstance(getattr(bc_sender, "_bus_adapter", None), ba.BusAdapter))
check("integration: RT_sender uses the bus adapter layer",
      isinstance(getattr(rt_sender, "_bus_adapter", None), ba.BusAdapter))

# Swap in loopbacks so a real send round-trips in-process with no listeners.
bc_sender._bus_adapter = ba.LoopbackBusAdapter('bc')
rt_lb = ba.LoopbackBusAdapter('rt')
frame = "1000000000000000000" + "1"  # 20-bit word, valid sync bits
ok = bc_sender.BC_send_message({'frames': [frame], 'request_id': 'adapter-test'})
check("integration: BC send through loopback succeeds", ok is True)
check("integration: payload delivered to rt side",
      len(rt_lb.received) == 1 and b'adapter-test' in rt_lb.received[0],
      str(list(rt_lb.received)))

bc_sender.executor.shutdown(wait=False)
rt_sender.executor.shutdown(wait=False)

# ── result ───────────────────────────────────────────────────────────────────

print(f"\nBus adapter tests: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
print("Bus adapter: all assertions passed")
