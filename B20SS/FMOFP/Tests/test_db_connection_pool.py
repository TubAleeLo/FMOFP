"""Test suite — DBM connection-pool contention regression.

Guards the August 2026 fix for the cold-start
"[DBM] Timeout waiting for available connection" errors (PLANNING.md open
item, now closed). The defect was an ACQUISITION-ORDER bug in
ConnectionPool.get_connection(): it blocked the full timeout waiting for a
returned connection BEFORE considering growing the pool toward
max_connections, so a burst of concurrent callers stalled `timeout` seconds
each while capacity sat unused, then raised once the pool finally saturated.

Covered here:
  1. Grow-before-block: with an empty pool and capacity available, an
     acquire returns immediately (not after `timeout` seconds).
  2. Concurrent burst within capacity: N callers, N <= max, all succeed
     promptly and connection_count never exceeds max.
  3. Genuine saturation still raises ConnectionPoolTimeout (with a short
     timeout so the suite stays fast) — the error is preserved for the case
     it was actually meant to report.
  4. Saturation recovers: once connections are returned, waiters proceed.
  5. connection_count does not leak when create_connection() fails — the
     original code incremented before creating, permanently shrinking
     capacity after a failed open.
  6. return_connection() does not double-decrement connection_count when a
     dead connection is replaced.
  7. Hammer test: 40 threads x repeated acquire/return against a small pool
     completes with zero spurious timeouts and an intact final count.

Standalone-safe: run from B20SS/ as
`python -m FMOFP.Tests.test_db_connection_pool`.
"""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, '.')

from FMOFP.storage.DBM import ConnectionPool, ConnectionPoolTimeout

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


_tmpdir = tempfile.mkdtemp(prefix="fmofp_pool_test_")
DB = os.path.join(_tmpdir, "pool_test.db")


def new_pool(min_c=2, max_c=5, timeout=None):
    pool = ConnectionPool(DB, min_connections=min_c, max_connections=max_c,
                          acquire_timeout=timeout)
    pool.initialize()
    return pool


# ── 1. grow-before-block ─────────────────────────────────────────────────────

# min=2/max=5, acquire_timeout deliberately large: if the implementation
# blocks before growing, this test takes >= 5s per acquire and the elapsed
# assertion fails. Pre-fix this is exactly what happened.
pool = new_pool(min_c=2, max_c=5, timeout=5)
held = [pool.get_connection() for _ in range(2)]      # drain the initial pool
start = time.monotonic()
third = pool.get_connection()                          # must GROW, not wait
elapsed = time.monotonic() - start
check("grow-before-block: acquire past min returns promptly",
      elapsed < 1.0, f"took {elapsed:.2f}s (pre-fix: ~5s)")
check("grow-before-block: pool grew", pool.connection_count == 3,
      str(pool.connection_count))
for c in held + [third]:
    pool.return_connection(c)
pool.close_all()

# ── 2. concurrent burst within capacity ──────────────────────────────────────

pool = new_pool(min_c=2, max_c=8, timeout=5)
results = []
res_lock = threading.Lock()
barrier = threading.Barrier(8)


def burst_worker():
    barrier.wait()
    t0 = time.monotonic()
    try:
        conn = pool.get_connection()
        dt = time.monotonic() - t0
        time.sleep(0.05)
        pool.return_connection(conn)
        with res_lock:
            results.append(("ok", dt))
    except Exception as e:
        with res_lock:
            results.append(("err", str(e)))


threads = [threading.Thread(target=burst_worker) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=30)

oks = [r for r in results if r[0] == "ok"]
check("burst: all 8 concurrent acquires succeeded", len(oks) == 8,
      str(results))
slowest = max((r[1] for r in oks), default=99)
check("burst: none stalled on the acquire timeout", slowest < 1.0,
      f"slowest {slowest:.2f}s")
check("burst: connection_count never exceeded max",
      pool.connection_count <= 8, str(pool.connection_count))
pool.close_all()

# ── 3. genuine saturation still raises ───────────────────────────────────────

pool = new_pool(min_c=1, max_c=2, timeout=0.3)
saturating = [pool.get_connection(), pool.get_connection()]
start = time.monotonic()
try:
    pool.get_connection()
    check("saturation: raises when truly at capacity", False, "no exception")
except ConnectionPoolTimeout as e:
    waited = time.monotonic() - start
    check("saturation: raises ConnectionPoolTimeout at capacity", True)
    check("saturation: waited for the configured timeout first",
          waited >= 0.25, f"{waited:.2f}s")
    check("saturation: message names the database", DB in str(e), str(e))
except Exception as e:
    check("saturation: raises ConnectionPoolTimeout at capacity", False,
          f"got {type(e).__name__}: {e}")

# ── 4. saturation recovers once a connection comes back ──────────────────────

def _return_soon():
    time.sleep(0.1)
    pool.return_connection(saturating.pop())


threading.Thread(target=_return_soon, daemon=True).start()
try:
    conn = pool.get_connection(timeout=5)
    check("saturation: waiter proceeds after a return", True)
    pool.return_connection(conn)
except Exception as e:
    check("saturation: waiter proceeds after a return", False, str(e))
for c in saturating:
    pool.return_connection(c)
pool.close_all()

# ── 5. no count leak when create_connection fails ────────────────────────────

pool = new_pool(min_c=1, max_c=4, timeout=0.3)
held = [pool.get_connection()]
count_before = pool.connection_count
original_create = pool.create_connection


def failing_create():
    raise RuntimeError("simulated: unable to open database file")


pool.create_connection = failing_create
for _ in range(3):
    try:
        pool.get_connection()
    except Exception:
        pass
pool.create_connection = original_create
check("failure: connection_count not leaked by failed creates",
      pool.connection_count == count_before,
      f"{pool.connection_count} vs {count_before}")
# capacity is still usable afterwards
try:
    conn = pool.get_connection()
    check("failure: pool still usable after failed creates", True)
    pool.return_connection(conn)
except Exception as e:
    check("failure: pool still usable after failed creates", False, str(e))
for c in held:
    pool.return_connection(c)
pool.close_all()

# ── 6. dead-connection replacement accounting ────────────────────────────────

pool = new_pool(min_c=2, max_c=4, timeout=1)
conn = pool.get_connection()
count_before = pool.connection_count
conn.close()                       # make it invalid before returning it
pool.return_connection(conn)
check("dead-conn: count unchanged after replace-on-return",
      pool.connection_count == count_before,
      f"{pool.connection_count} vs {count_before}")
check("dead-conn: replacement is usable",
      pool.is_connection_valid(pool.get_connection()))
pool.close_all()

# ── 7. hammer ────────────────────────────────────────────────────────────────

pool = new_pool(min_c=2, max_c=6, timeout=10)
errors = []
err_lock = threading.Lock()


def hammer():
    for _ in range(15):
        try:
            c = pool.get_connection()
            c.execute("SELECT 1")
            pool.return_connection(c)
        except Exception as e:
            with err_lock:
                errors.append(str(e))


threads = [threading.Thread(target=hammer) for _ in range(40)]
t0 = time.monotonic()
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=60)
hammer_elapsed = time.monotonic() - t0

check("hammer: 40 threads x 15 ops, zero errors", not errors,
      f"{len(errors)} errors, first: {errors[0] if errors else ''}")
check("hammer: completed without timeout stalls", hammer_elapsed < 30,
      f"{hammer_elapsed:.1f}s")
check("hammer: connection_count within bounds",
      0 < pool.connection_count <= 6, str(pool.connection_count))
pool.close_all()

# ── cleanup ──────────────────────────────────────────────────────────────────

for fname in os.listdir(_tmpdir):
    try:
        os.remove(os.path.join(_tmpdir, fname))
    except OSError:
        pass
try:
    os.rmdir(_tmpdir)
except OSError:
    pass

print(f"\nDB connection pool tests: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
print("DB connection pool: all assertions passed")
