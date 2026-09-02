"""ExecutionBody.invoke — fork-per-call with full call-lifespan management.

The library is libc and the child closures are plain Python (fork passes them
unpickled), so every lifecycle behaviour is pinned down without a real solver:
scratch dirs are tracked and swept at close, release() detaches a dir meant to
outlive the session, a hung child is bounded by the timeout, and a Python-side
child error lands as a traceback in the captured run log (CallResult.tail).
"""
import ctypes.util
import shutil
import time
from pathlib import Path

import pytest

from fylite.engine import ExecutionBody

LIBC = ctypes.util.find_library("c") or "libc.so.6"


def test_call_runs_and_close_sweeps_scratch():
    s = ExecutionBody(lib_path=LIBC)
    r = s.invoke(lambda lib: 1)
    assert r.ok and Path(r.workdir).exists()   # left for the caller to consume
    s.close()
    assert not Path(r.workdir).exists()        # ...but never leaked in-process


def test_release_detaches_a_kept_dir_from_the_sweep():
    s = ExecutionBody(lib_path=LIBC)
    r = s.invoke(lambda lib: 1)
    s.release(r.workdir)                       # deliberate keep (keep_workdir)
    s.close()
    try:
        assert Path(r.workdir).exists()        # survived close; PID-tagged, so a
    finally:                                   # later process's reaper covers it
        shutil.rmtree(r.workdir, ignore_errors=True)


def test_call_is_timeout_bounded():
    s = ExecutionBody(lib_path=LIBC, timeout=0.3)
    try:
        with pytest.raises(TimeoutError):
            s.invoke(lambda lib: time.sleep(30) or 1)
    finally:
        s.close()


def test_timeout_kills_even_a_sigterm_ignoring_child(monkeypatch):
    # legacy codes sometimes trap/ignore SIGTERM; the timeout guarantee must
    # escalate to SIGKILL instead of hanging in an unbounded join.
    import signal

    monkeypatch.setattr("fylite.engine.ExecutionBody._TERM_GRACE", 0.3)

    def stubborn(lib):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
        return 1
    s = ExecutionBody(lib_path=LIBC, timeout=0.3)
    t0 = time.time()
    try:
        with pytest.raises(TimeoutError):
            s.invoke(stubborn)
        assert time.time() - t0 < 10        # bounded — no unbounded join
    finally:
        s.close()


def test_child_python_error_gets_traceback_in_log():
    s = ExecutionBody(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1 / 0)
        assert not r.ok and r.exitcode == 111
        assert "ZeroDivisionError" in r.tail()
    finally:
        s.close()


def test_call_without_a_library_is_a_loud_error():
    s = ExecutionBody()
    try:
        with pytest.raises(RuntimeError, match="lib_path"):
            s.invoke(lambda lib: 1)
    finally:
        s.close()
