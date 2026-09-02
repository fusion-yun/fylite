"""P1-3: COW holder fault handling — the first solve runs *in the holder*.

A ``ExecutionBody.cow`` holder loads the library once and warms in-holder, then forks a
child per later solve.  These tests pin down the three failure behaviours without
any real solver: the "library" is libc and the warmup/slice callbacks are plain
Python (fork passes them unpickled), so we can inject hard aborts and soft
failures deterministically.

  (b) a holder death mid-solve is wrapped as a RuntimeError carrying the log tail
      — not a bare EOFError;
  (c) a soft warmup failure (flag 0) tears the holder down (fail-fast) instead of
      serving later slices on un-loaded state;
  (+) a later slice crash stays isolated — the holder survives and keeps serving.
"""
import ctypes.util
import os
import time

import pytest

from fylite.engine import ExecutionBody

LIBC = ctypes.util.find_library("c") or "libc.so.6"


def _mk(**cb):
    """A COW ExecutionBody over libc with the given warmup/slice callbacks."""
    return ExecutionBody.cow(LIBC, {}, **cb)


def test_soft_warmup_failure_is_surfaced_and_kills_the_holder():
    # warmup returns 0 (no result) -> that solve reports not-ok, AND the holder
    # exits so a retry fails loudly rather than running slices on un-loaded state.
    s = _mk(warmup=lambda lib, buf, req: 0, slice=lambda lib, buf, req: 1)
    try:
        assert not s.invoke(("x",)).ok                 # clean failure, flag 0
        with pytest.raises(RuntimeError, match="not running|died"):
            s.invoke(("y",))                           # holder gone -> loud error
    finally:
        s.close()


def test_hard_warmup_abort_is_wrapped_not_bare_eof():
    # warmup hard-exits (stands in for a Fortran STOP in the holder) -> solve
    # wraps the EOFError as a RuntimeError, not a bare EOFError.
    s = _mk(warmup=lambda lib, buf, req: os._exit(3),
            slice=lambda lib, buf, req: 1)
    try:
        with pytest.raises(RuntimeError, match="holder died|aborted"):
            s.invoke(("x",))
    finally:
        s.close()


def test_later_slice_crash_stays_isolated():
    # a good warmup, then a slice child that hard-exits: the holder survives (the
    # crash is absorbed by the fork child) and keeps serving subsequent solves.
    def sl(lib, buf, req):
        if req == ("bad",):
            os._exit(4)
        return 1
    s = _mk(warmup=lambda lib, buf, req: 1, slice=sl)
    try:
        assert s.invoke(("warm",)).ok                  # warm succeeds
        assert not s.invoke(("bad",)).ok               # slice child crashes
        assert s._holder.is_alive()                   # holder survived
        assert s.invoke(("good",)).ok                  # still serving
    finally:
        s.close()


def test_slice_timeout_kills_child_but_holder_survives():
    # P1-2: a hung forked slice is killed at the timeout and reported not-ok;
    # the holder + loaded tables survive and keep serving.
    def sl(lib, buf, req):
        if req == ("hang",):
            time.sleep(30)
        return 1
    s = ExecutionBody.cow(LIBC, {}, warmup=lambda lib, b, r: 1, slice=sl, timeout=0.5)
    try:
        assert s.warm(("warm",)).ok
        assert not s.invoke(("hang",)).ok              # killed at ~0.5 s -> not ok
        assert s._holder.is_alive()                   # holder untouched
        assert s.invoke(("ok",)).ok                    # still serving
    finally:
        s.close()


def test_failed_solve_keeps_its_log_tail():
    # the private rundir is removed when solve() returns, but the log tail must
    # survive in the CallResult — a failed solve with no diagnostics is useless.
    import os as _os

    def sl(lib, buf, req):
        _os.write(1, b"DIAGNOSTIC-FROM-SLICE\n")
        return 0                                  # fail after logging
    s = _mk(warmup=lambda lib, buf, req: 1, slice=sl)
    try:
        assert s.warm(("w",)).ok
        r = s.invoke(("x",))
        assert not r.ok
        assert "DIAGNOSTIC-FROM-SLICE" in r.tail()   # cached before removal
    finally:
        s.close()


def test_wedged_holder_raises_timeout(monkeypatch):
    # P1-2: if the HOLDER itself is wedged (warmup hangs in-holder, no child to
    # kill), the parent poll fires and terminates it with a TimeoutError.
    monkeypatch.setattr("fylite.engine.ExecutionBody._POLL_MARGIN", 0.5)

    def warm(lib, buf, req):
        time.sleep(30)                                # warmup hangs in the holder
        return 1
    s = ExecutionBody.cow(LIBC, {}, warmup=warm, slice=lambda lib, b, r: 1, timeout=0.3)
    try:
        with pytest.raises(TimeoutError, match="unresponsive"):
            s.invoke(("x",))                           # poll(~0.8 s) fires
    finally:
        s.close()
