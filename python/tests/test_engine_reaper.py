"""P2-4 / P3-7: orphan reaping and atomic staging of tmpfs dirs.

Dirs created by :mod:`fylite.engine` embed the creator PID, so a process
killed before ``atexit`` leaves identifiable leftovers that a later process can
reap — while never touching a concurrent *live* process's dirs.
"""
import os

from fylite.engine import ExecutionBody

reap_orphans = ExecutionBody.reap_orphans
stage_dir = ExecutionBody.stage_dir
_scratch_dir = ExecutionBody._scratch_dir


def test_reaps_dead_pid_dirs_only(tmp_path):
    base = str(tmp_path)
    dead = os.path.join(base, "native_run_2147480000_deadbeef")   # implausible PID
    live = os.path.join(base, f"native_run_{os.getpid()}_livexxxx")
    other = os.path.join(base, "unrelated_dir")
    for d in (dead, live, other):
        os.makedirs(d)

    n = reap_orphans(base, ("native_run_",))

    assert n == 1
    assert not os.path.exists(dead)        # dead PID -> reaped
    assert os.path.exists(live)            # our live PID -> kept
    assert os.path.exists(other)           # non-matching prefix -> untouched


def test_scratch_and_stage_names_embed_pid(tmp_path):
    d = _scratch_dir(str(tmp_path), "native_run_")
    try:
        assert d.name.startswith(f"native_run_{os.getpid()}_")
    finally:
        d.rmdir()

    src = tmp_path / "src"
    src.mkdir()
    (src / "a.bin").write_bytes(b"x" * 16)
    staged = stage_dir(src, prefix="native_stage_", env_var="_NOPE_")  # -> /dev/shm or None
    if staged is not None:                 # only when a tmpfs is present
        try:
            assert staged.name.startswith(f"native_stage_{os.getpid()}_")
            assert (staged / "a.bin").read_bytes() == b"x" * 16
        finally:
            import shutil
            shutil.rmtree(staged, ignore_errors=True)
