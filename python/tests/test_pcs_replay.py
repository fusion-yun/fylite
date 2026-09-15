"""PCS 指令回放的分窗推进（台账 I-20 · I-21 / PCS-V16）：切窗、快照、暂停与恢复 ≡ 不中断。

工况取内核判据自己的 Miller 缺省（与 ``test_session`` 同）；回放是三个节点的合成小回放。
"""
from __future__ import annotations

import csv
import json

import pytest

from fylite.engine import pcs_replay as R
from fylite.engine import session as S

from test_session import _plan  # noqa: E402  (same Miller case as the session gates)


@pytest.fixture(scope="module", autouse=True)
def _kernel():
    try:
        from fylite import kernel
        kernel.require_data()
    except Exception as exc:  # the data-plane library is not loadable here
        pytest.skip(f"the runtime library is not loadable: {exc}")


NODES = [
    {"t": 0.0, "phase": "flat", "ip": 15e6, "ne_bar": 1.0e20, "p_ec": {"a": 0.0}, "p_ic": 0.0, "flags": []},
    {"t": 0.3, "phase": "flat", "ip": 15e6, "ne_bar": 1.0e20, "p_ec": {"a": 0.0}, "p_ic": 0.0, "flags": []},
    {"t": 1.0, "phase": "flat", "ip": 15e6, "ne_bar": 1.0e20, "p_ec": {"a": 0.0}, "p_ic": 0.0, "flags": []},
]


def _rows(path):
    return list(csv.DictReader(open(path)))


def test_windows_are_cut_at_every_replay_node():
    edges = R.window_edges(NODES, 0.0, 0.6, window=0.25, ramp_window=0.25)
    assert edges[0] == pytest.approx(0.0) and edges[-1] == pytest.approx(0.6)
    assert any(abs(e - 0.3) < 1e-9 for e in edges), edges
    assert all(abs(round(e / S.STEP_S) * S.STEP_S - e) < 1e-9 for e in edges)


def test_a_paused_replay_resumed_from_its_snapshot_writes_what_the_uninterrupted_one_writes(tmp_path):
    """PCS-V16: pause at a window edge, resume from the pause snapshot -> the same 10 ms rows, bit for bit."""
    whole = R.march_replay(_plan(), NODES, 0.0, 0.5, tmp_path / "whole.csv", window=0.1, ramp_window=0.1,
                           ec_sources=[None], log=lambda *_: None)
    assert whole["stopped"] is None and whole["t_end"] == pytest.approx(0.5)
    part = R.march_replay(_plan(), NODES, 0.0, 0.5, tmp_path / "part.csv", window=0.1, ramp_window=0.1,
                          ec_sources=[None], pause_at=0.2, log=lambda *_: None)
    assert part["stopped"] and part["t_end"] == pytest.approx(0.2)
    pause = next(n for n in part["retained"] if n.startswith("pause@"))
    rest = R.march_replay(_plan(), NODES, 0.0, 0.5, tmp_path / "part.csv", window=0.1, ramp_window=0.1,
                          ec_sources=[None], resume=tmp_path / "part.csv.snapshots" / pause, log=lambda *_: None)
    assert rest["stopped"] is None and rest["t_end"] == pytest.approx(0.5)
    a, b = _rows(tmp_path / "whole.csv"), _rows(tmp_path / "part.csv")
    assert len(a) == len(b) == 50
    for ra, rb in zip(a, b):
        assert (ra["t"], ra["te0"], ra["w_th"], ra["beta_n"]) == (rb["t"], rb["te0"], rb["w_th"], rb["beta_n"])


def test_a_fork_resumed_into_a_new_output_starts_its_own_files_and_keeps_its_setting(tmp_path):
    """I-21d through the driver: resume a pause snapshot with a changed setting into ANOTHER output — its CSVs get
    headers, its kept snapshots carry the forked case (not the one forked from) and the fuelling state."""
    part = R.march_replay(_plan(), NODES, 0.0, 0.4, tmp_path / "base.csv", window=0.1, ramp_window=0.1,
                          ec_sources=[None], pause_at=0.2, log=lambda *_: None)
    pause = tmp_path / "base.csv.snapshots" / next(n for n in part["retained"] if n.startswith("pause@"))
    assert "fuel_state" in json.loads(pause.read_text())
    fork = R.march_replay(_plan(), NODES, 0.0, 0.4, tmp_path / "fork.csv", window=0.1, ramp_window=0.1,
                          ec_sources=[None], resume=pause, settings={"dt_max": 0.05}, log=lambda *_: None)
    assert fork["stopped"] is None and fork["t_end"] == pytest.approx(0.4)
    rows = _rows(tmp_path / "fork.csv")
    assert len(rows) == 20 and float(rows[0]["t"]) == pytest.approx(0.21)
    assert _rows(str(tmp_path / "fork.csv") + ".windows.csv")[0]["t_from"]
    end = json.loads((tmp_path / "fork.csv.snapshots" / next(n for n in fork["retained"] if n.startswith("end@"))).read_text())
    case = json.loads((tmp_path / "fork.csv.snapshots" / end["plan_ref"]).read_text())
    assert case["settings"]["dt_max"] == 0.05 and "fuel_state" in end


def test_the_snapshot_before_a_node_is_kept_and_the_case_is_stored_once(tmp_path):
    out = tmp_path / "run.csv"
    summary = R.march_replay(_plan(), NODES, 0.0, 0.4, out, window=0.1, ramp_window=0.1, ec_sources=[None],
                             log=lambda *_: None)
    snaps = tmp_path / "run.csv.snapshots"
    assert any(n.startswith("before-node@0.30") for n in summary["retained"]), summary["retained"]
    assert len(list(snaps.glob("plan.*.json"))) == 1
    kept = json.loads((snaps / next(n for n in summary["retained"] if n.startswith("before-node@0.30"))).read_text())
    assert "plan" not in kept and kept["plan_ref"].startswith("plan.") and kept["format"] == S.SNAPSHOT_FORMAT
