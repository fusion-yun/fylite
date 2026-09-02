"""ExecutionBody P0-P2: run-trace provenance, 3-value disposition + interpret
hook, reentrant/exclusive resolution, and COW self-heal (restart + retries).

The "library" is libc and the closures are plain Python (fork passes them
unpickled), so every behaviour is pinned without a real solver.
"""
import ctypes.util
from pathlib import Path

import pytest

from fylite import engine
from fylite.engine import (
    DELIVER, RECLAIM, RETAIN, CallScope, ExecutionBody, PoisonedBodyError,
    RunTrace, _CallResult,
)

LIBC = ctypes.util.find_library("c") or "libc.so.6"


# --------------------------------------------------------------------------- #
# P0 — run trace carries environment identity + duration; deliver records it
# --------------------------------------------------------------------------- #
def test_invoke_trace_has_env_identity_and_duration():
    s = ExecutionBody(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1)
        assert r.ok
        tr = r.trace
        assert tr is not None and tr.disposition == RETAIN
        assert tr.duration_s is not None and tr.duration_s >= 0
        assert tr.environment_identity["mode"] == "fork"
        assert tr.environment_identity["library"] == LIBC
        assert "library_sha256" in tr.environment_identity
    finally:
        s.close()


def test_deliver_records_the_run_trace(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "g1.000").write_text("g")
    trace = RunTrace(RETAIN, str(wd / "log"),
                     environment_identity={"mode": "fork", "library": "libx"},
                     duration_s=1.23)
    result = {"gfile": str(wd / "g1.000"), "workdir": str(wd),
              "terror": 0.01, "converged": True, "run_trace": vars(trace)}
    out = engine.deliver(result, tmp_path / "d")
    assert out["manifest"]["trace"]["duration_s"] == 1.23
    assert out["manifest"]["trace"]["environment_identity"]["library"] == "libx"


def test_deliver_explicit_trace_arg_overrides(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "g1.000").write_text("g")
    result = {"gfile": str(wd / "g1.000"), "workdir": str(wd)}
    tr = RunTrace(DELIVER, "log", environment_identity={"mode": "cow"}, duration_s=2.0)
    out = engine.deliver(result, tmp_path / "d", trace=tr)
    assert out["manifest"]["trace"]["environment_identity"]["mode"] == "cow"


# --------------------------------------------------------------------------- #
# P1 — interpret (P-1) hook + three-value disposition
# --------------------------------------------------------------------------- #
def test_interpret_hook_resolves_the_request():
    class IntBody(ExecutionBody):
        def interpret_inputs(self, request):
            n = request
            return lambda lib: n           # a raw int -> the child closure

    s = IntBody(lib_path=LIBC)
    try:
        r = s.invoke(7)                    # 7 is not callable; interpret made it so
        assert r.ok and r.flag == 7
    finally:
        s.close()


def test_harvest_forces_retain_on_failure():
    s = ExecutionBody(lib_path=LIBC)
    call = CallScope(request=None, workdir=Path("/tmp"), disposition=RECLAIM)
    res = _CallResult(exitcode=111, flag=0, workdir="/tmp/x",
                      log="/tmp/x/log", duration_s=0.1)      # not ok
    s.harvest(call, res)
    assert call.disposition == RETAIN                        # kept for post-mortem
    assert res.trace.disposition == RETAIN
    s.close()


def test_harvest_keeps_reclaim_on_success():
    s = ExecutionBody(lib_path=LIBC)
    call = CallScope(None, Path("/tmp"), disposition=RECLAIM)
    res = _CallResult(0, 1, "/tmp/x", "/tmp/x/log", duration_s=0.1)   # ok
    s.harvest(call, res)
    assert call.disposition == RECLAIM
    s.close()


def test_deliver_on_success_promotes_disposition():
    class DeliverBody(ExecutionBody):
        deliver_on_success = True

    s = DeliverBody(lib_path=LIBC)
    call = CallScope(None, Path("/tmp"), disposition=RETAIN)
    res = _CallResult(0, 1, "/tmp/x", "/tmp/x/log", duration_s=0.1)
    s.harvest(call, res)
    assert call.disposition == DELIVER and res.trace.disposition == DELIVER
    assert call.deliver is True
    s.close()


# --------------------------------------------------------------------------- #
# P2a — exclusive vs reentrant resolution
# --------------------------------------------------------------------------- #
def test_is_exclusive_resolution():
    s1 = ExecutionBody(lib_path=LIBC)
    s2 = ExecutionBody(lib_path=LIBC, exclusive_environment=False)
    try:
        assert s1._is_exclusive is True                # class default
        assert s2._is_exclusive is False               # instance override
        s2._holder = object()                          # a COW holder forces exclusivity
        assert s2._is_exclusive is True
    finally:
        s2._holder = None
        s1.close()
        s2.close()


def test_exclusive_rejects_a_concurrent_call():
    s = ExecutionBody(lib_path=LIBC)
    s._call_guard.acquire()                            # simulate an in-flight call
    try:
        with pytest.raises(RuntimeError, match="single-in-flight"):
            s.invoke(lambda lib: 1)
    finally:
        s._call_guard.release()
        s.close()


def test_reentrant_body_ignores_the_guard():
    s = ExecutionBody(lib_path=LIBC, exclusive_environment=False)
    s._call_guard.acquire()                            # would block an exclusive body
    try:
        r = s.invoke(lambda lib: 1)                    # reentrant: runs anyway
        assert r.ok
    finally:
        s._call_guard.release()
        s.close()


# --------------------------------------------------------------------------- #
# P2b — COW self-heal: restart() + invoke(retries=)
# --------------------------------------------------------------------------- #
def test_restart_requires_a_cow_session():
    s = ExecutionBody(lib_path=LIBC)
    try:
        with pytest.raises(RuntimeError, match="COW"):
            s.restart()
    finally:
        s.close()


def test_restart_respawns_a_dead_holder():
    s = ExecutionBody.cow(LIBC, {}, warmup=lambda lib, b, r: 1,
                          slice=lambda lib, b, r: 1)
    try:
        assert s.warm(("w",)).ok
        old_pid = s._holder.pid
        s._end_process(s._holder)                      # simulate holder death
        s.poison("simulated death")
        assert not s.environment_ready()
        s.restart()
        assert s.environment_ready()
        assert s._holder.pid != old_pid
        assert s.warm(("w2",)).ok                       # serves again after re-warm
    finally:
        s.close()


def test_invoke_retries_until_success():
    class Flaky(ExecutionBody):
        attempts = 0

        def execute(self, call, timeout, cancel_token=None):
            type(self).attempts += 1
            ok = self.attempts >= 2
            return _CallResult(0 if ok else 111, 1 if ok else 0,
                               str(call.workdir), str(call.workdir / "log"))

    s = Flaky(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1, retries=2)
        assert r.ok and Flaky.attempts == 2
        assert s.stats()["retries"] == 1 and s.stats()["failures"] >= 1
        assert r.trace.attempts == 2                 # trace records the attempt count
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q0.1 — bounded concurrency for a reentrant body (no fork-storm)
# --------------------------------------------------------------------------- #
def test_max_concurrency_caps_reentrant():
    import asyncio
    import threading

    class Tracked(ExecutionBody):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.cur = 0
            self.peak = 0
            self.lock = threading.Lock()

        def execute(self, call, timeout, cancel_token=None):
            import time as _t
            with self.lock:
                self.cur += 1
                self.peak = max(self.peak, self.cur)
            _t.sleep(0.05)
            with self.lock:
                self.cur -= 1
            return _CallResult(0, 1, str(call.workdir), str(call.workdir / "log"))

    s = Tracked(lib_path=LIBC, exclusive_environment=False, max_concurrency=2)

    async def go():
        await asyncio.gather(*(s.ainvoke(lambda lib: 1) for _ in range(6)))

    try:
        asyncio.run(go())
        assert 1 <= s.peak <= 2                       # never more than the cap
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q0.2 — DELIVER enactment via the on_deliver hook
# --------------------------------------------------------------------------- #
def test_deliver_on_success_fires_on_deliver():
    delivered = []

    class DeliverBody(ExecutionBody):
        deliver_on_success = True

        def on_deliver(self, call):
            delivered.append(str(call.workdir))

    s = DeliverBody(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1)
        assert r.ok and r.trace.disposition == DELIVER
        assert delivered == [r.workdir]               # hook fired at P-6
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q0.3 — real cancellation (fork child killed; ainvoke cancel propagates)
# --------------------------------------------------------------------------- #
def test_cancel_token_cancels_a_forked_call():
    import threading
    import time as _t

    s = ExecutionBody(lib_path=LIBC, timeout=30)
    token = threading.Event()
    threading.Thread(target=lambda: (_t.sleep(0.2), token.set()), daemon=True).start()
    t0 = _t.time()
    try:
        with pytest.raises(engine.CallCancelled):
            s.invoke(lambda lib: _t.sleep(30) or 1, cancel_token=token)
        assert _t.time() - t0 < 5                     # killed promptly, not at timeout
        assert s.stats()["cancels"] == 1
    finally:
        s.close()


def test_ainvoke_cancel_kills_the_child():
    import asyncio
    import time as _t

    s = ExecutionBody(lib_path=LIBC, timeout=30)

    async def go():
        task = asyncio.ensure_future(s.ainvoke(lambda lib: _t.sleep(30) or 1))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(go())
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q1.4 — per-child resource limits
# --------------------------------------------------------------------------- #
def test_rlimits_applied_in_child():
    s = ExecutionBody(lib_path=LIBC, rlimits={"NOFILE": 64})

    def child(lib):
        import resource
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        return 1 if soft == 64 else 2

    try:
        r = s.invoke(child)
        assert r.ok and r.flag == 1                   # the child saw NOFILE soft == 64
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q1.5 — telemetry (counters + call_id + per-phase timings)
# --------------------------------------------------------------------------- #
def test_stats_counts_calls_and_failures():
    s = ExecutionBody(lib_path=LIBC)
    try:
        s.invoke(lambda lib: 1)                       # ok
        s.invoke(lambda lib: 0)                       # not ok (flag 0)
        st = s.stats()
        assert st["calls"] == 2 and st["failures"] == 1
    finally:
        s.close()


def test_trace_has_call_id_and_phase_timings():
    s = ExecutionBody(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1)
        assert r.trace.call_id and r.trace.attempts == 1
        # every phase the protocol declares is timed (names come from the
        # contract, not a hand-copied list — see test_protocol_conformance.py)
        assert {m for _, m, _ in engine.PROTOCOL["phases"] if m != "dispose"} \
            <= set(r.trace.phase_timings)
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Q2.6 — symmetric acquire() + backoff
# --------------------------------------------------------------------------- #
def test_acquire_reopens_a_closed_lib_body():
    s = ExecutionBody(lib_path=LIBC)
    s.close()
    assert s._env_state == "cold"
    try:
        s.acquire()
        assert s.environment_ready()
        assert s.invoke(lambda lib: 1).ok
    finally:
        s.close()


def test_acquire_refuses_a_poisoned_environment_and_restart_replaces_it():
    """D2 fail-fast: acquire() never launders a poisoned environment into a
    serviceable one — replacing it is restart()'s explicit job."""
    s = ExecutionBody.cow(LIBC, {}, warmup=lambda lib, b, r: 1,
                          slice=lambda lib, b, r: 1)
    try:
        assert s.warm(("w",)).ok
        s._end_process(s._holder)
        s.poison("x")
        assert not s.environment_ready()
        with pytest.raises(PoisonedBodyError, match="poisoned"):
            s.acquire()
        s.restart()                                   # explicit replacement
        assert s.environment_ready() and s.warm(("w2",)).ok
    finally:
        s.close()


def test_retry_backoff_sleeps_exponentially(monkeypatch):
    slept = []
    monkeypatch.setattr("fylite.engine.body.time.sleep", slept.append)

    class Fail(ExecutionBody):
        def execute(self, call, timeout, cancel_token=None):
            return _CallResult(111, 0, str(call.workdir), str(call.workdir / "log"))

    s = Fail(lib_path=LIBC)
    try:
        s.invoke(lambda lib: 1, retries=2, retry_backoff=0.5)
        assert slept == [0.5, 1.0]                     # 0.5*2^0, 0.5*2^1
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# P3 — awaitable ainvoke (off the event loop)
# --------------------------------------------------------------------------- #
def test_ainvoke_runs_and_traces():
    import asyncio

    s = ExecutionBody(lib_path=LIBC)
    try:
        r = asyncio.run(s.ainvoke(lambda lib: 1))
        assert r.ok and r.trace is not None
        assert r.trace.environment_identity["mode"] == "fork"
    finally:
        s.close()


def test_ainvoke_reentrant_runs_concurrently():
    import asyncio

    s = ExecutionBody(lib_path=LIBC, exclusive_environment=False)

    async def go():
        return await asyncio.gather(*(s.ainvoke(lambda lib: 1) for _ in range(4)))

    try:
        rs = asyncio.run(go())
        assert len(rs) == 4 and all(r.ok for r in rs)
    finally:
        s.close()
