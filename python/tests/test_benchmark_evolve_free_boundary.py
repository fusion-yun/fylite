"""Free-boundary evolution coupled to the PF circuits and the passive structure, run from THIS checkout (register record V-21).

★★2026-09-15 (/goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」): ``code/evolve_free_boundary`` is marched
through the tree door every run on the EAST card and KEFIT's t4041_mag answer by ``tools/benchmark-evolve-free-boundary.py``.
There is no second code: what is held are identities the march must keep (a shell mode decays on ``code/wall``'s own time
constant; a perfect conductor keeps its linked flux while the plasma current ramps; a current-driven march handed a
voltage march's channel currents gives back its shell currents), the recomputed readings against the recorded ones
(the solver's reproducibility), and — as a reading, not a band — ``code/forward`` on the B-14 slices with the node rule
and with ``edge_fraction``.

No store, no card, or a kernel without ``code/evolve_free_boundary`` (point ``$FYLITE_KERNEL_LIB`` at a current build):
the gate SKIPS by name.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "corpus/benchmark/evolve_free_boundary_east137985.json"
REPRO_REL, REPRO_ABS = 1e-6, 1e-9
#: what differs run to run by construction, not by physics
UNHELD = ("notes", "seconds", "environment")

#: ★bands (2026-09-15): the two identities are exact up to roundoff (the recorded values are ~1e-15 / ~1e-13, the bands a
#: thousand times that); the loop equation is solved to the free-boundary solve's own tolerance (1e-9); the drive
#: reproduction is the measured value rounded up (three significant figures)
V21_BAND = {"wall_decay_rel": 1e-12, "flux_drift_over_moved": 1e-10, "circuit_residual": 1e-9, "shell_rel_max": 4.51e-09}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_evolve_free_boundary", ROOT / "tools" / "benchmark-evolve-free-boundary.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def case() -> Path:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / READINGS).is_file():
        pytest.skip(f"no {READINGS} in the case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    return store / CASE


@pytest.fixture(scope="module")
def want(case) -> dict:
    return json.loads((case / READINGS).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def got(case):
    try:
        return _tool().readings(case)
    except Exception as e:  # noqa: BLE001 — a host without the card or a kernel carrying the door skips by name
        if "evolve_free_boundary" in str(e) or "device" in str(e).lower() or "library" in str(e).lower():
            pytest.skip(f"no code/evolve_free_boundary / EAST card through the tree door here: {e}")
        raise


def _close(g: float, w: float) -> bool:
    return abs(g - w) <= max(REPRO_ABS, REPRO_REL * abs(w))


def _walk(g, w, path=""):
    if isinstance(w, dict):
        for k, v in w.items():
            if k not in UNHELD:
                _walk(g[k], v, f"{path}/{k}")
    elif isinstance(w, list):
        assert len(g) == len(w), (path, len(g), len(w))
        for i, v in enumerate(w):
            _walk(g[i], v, f"{path}[{i}]")
    elif isinstance(w, float):
        assert _close(g, w), (path, g, w)
    else:
        assert g == w, (path, g, w)


def test_the_readings_are_the_registered_ones(case):
    import yaml
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    assert hashlib.sha256((case / READINGS).read_bytes()).hexdigest() == sums[READINGS.removeprefix("corpus/")]


def test_v21_a_shell_mode_decays_on_the_wall_time(got, want):
    _walk(got["wall_decay"], want["wall_decay"], "wall_decay")
    assert got["wall_decay"]["max_rel_deviation"] <= V21_BAND["wall_decay_rel"]


def test_v21_a_perfect_conductor_keeps_its_flux_while_the_plasma_ramps(got, want):
    _walk(got["flux_freezing"], want["flux_freezing"], "flux_freezing")
    f = got["flux_freezing"]
    assert f["drift_over_moved"] <= V21_BAND["flux_drift_over_moved"]
    assert f["facts"]["max_circuit_residual"] <= V21_BAND["circuit_residual"]
    #: every coupled step a converged equilibrium of the currents alone (the start is `code/forward`'s kind of solve)
    assert all(s == 2.0 for s in f["gs_state"][1:]) and f["facts"]["fb_held"] == 0.0


def test_v21_current_drive_reproduces_the_voltage_march(got, want):
    _walk(got["drive_reproduction"], want["drive_reproduction"], "drive_reproduction")
    d = got["drive_reproduction"]
    assert d["shell_rel_max"] <= V21_BAND["shell_rel_max"]
    for tag in ("voltage", "current"):
        assert d[tag]["facts"]["max_circuit_residual"] <= V21_BAND["circuit_residual"], tag
        assert all(s == 2.0 for s in d[tag]["gs_state"]), tag


def test_v21_the_forward_edge_rule_is_a_reading_not_a_band(got, want):
    """★A finding held as one: on the magnetics-only B-14 slices the node rule stops `settled` with the virtual pair
    carrying ~10 kA, the edge rule converges with it trimmed to tens of amperes — and sits further from KEFIT's axis.
    B-14's node readings are an equilibrium held by the pair.  If the edge rule stops converging, or the node rule
    starts to, this is stale."""
    _walk(got["forward_edge"], want["forward_edge"], "forward_edge")
    for name, v in got["forward_edge"].items():
        if not name.endswith("_mag"):
            continue
        assert v["node"]["settled"] == 1.0 and abs(v["node"]["fb_amp"]) > 5e3, name
        assert v["edge"]["converged"] == 1.0 and abs(v["edge"]["fb_amp"]) < 1e3, name
