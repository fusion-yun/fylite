"""K-15 — immutable iteration snapshots, staleness DAG, convergence panel."""
import pytest

from fylite import engine as v


def test_staleness_downstream_propagation():
    s = v.Staleness()
    added = s.invalidate("equilibrium")
    # a fresh equilibrium staleifies its whole downstream cone (the loop cycle)
    assert set(added) == set(v.STAGES)
    s.refresh("profiles")
    assert not s.is_stale("profiles")
    assert s.is_stale("bootstrap")
    # everything but the refreshed stage, in canonical stage order — derived from
    # STAGES rather than hand-copied, so adding a stage does not silently pass
    assert s.snapshot() == [x for x in v.STAGES if x != "profiles"]


def test_beam_stage_sits_between_the_equilibrium_and_the_constraint():
    """K-20: the beam deposition reads the equilibrium geometry and the kinetic
    profiles and feeds the current constraint, so it must be in the DAG — a new
    equilibrium has to make it stale."""
    s = v.Staleness()
    assert "beam" in v.STAGES
    assert "beam" in s.downstream("equilibrium")
    assert "beam" in s.downstream("profiles")
    assert "constraint" in s.downstream("beam")
    assert "beam" in s.invalidate("equilibrium")


def test_staleness_partial_invalidate_terminates():
    s = v.Staleness()
    added = s.invalidate("bootstrap")            # bootstrap -> constraint -> equilibrium -> ...
    # cycle must terminate, not loop forever
    assert "bootstrap" in added and "constraint" in added


def test_snapshot_is_write_once(tmp_path):
    d = v.snapshot(tmp_path, 0, inputs={"KZEROJ": [8]},
                   state={"q0": 0.7}, artifacts=None)
    assert (d / "inputs.json").is_file()
    assert (d / "state.json").is_file()
    with pytest.raises(v.SnapshotError):
        v.snapshot(tmp_path, 0, inputs={"x": 1})   # same index -> refuse


def test_snapshot_copies_artifacts_and_loads(tmp_path):
    g = tmp_path / "g137985.04000"
    g.write_text("PSI ...")
    v.snapshot(tmp_path / "arch", 3, inputs={"a": 1}, state={"q0": 0.78},
               artifacts=[g])
    assert v.list_snapshots(tmp_path / "arch") == [3]
    snap = v.load_snapshot(tmp_path / "arch", 3)
    assert snap["inputs"] == {"a": 1}
    assert snap["state"]["q0"] == 0.78
    assert "g137985.04000" in snap["artifacts"]


def test_convergence_panel():
    hist = [{"iter": 0, "q0": 0.70, "q95": 3.0, "constrained": False},
            {"iter": 1, "q0": 0.78, "q95": 3.05, "dq0": 0.08, "constrained": True},
            {"iter": 2, "q0": 0.781, "q95": 3.05, "dq0": 0.001,
             "constrained": True, "converged": True}]
    panel = v.convergence_panel(hist)
    assert panel["iter"] == [0, 1, 2]
    assert panel["q0"][-1] == 0.781
    assert panel["dq0"] == [None, 0.08, 0.001]
    assert panel["converged"] is True
    assert panel["n_iter"] == 2
