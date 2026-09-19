"""The static inverse problem, run from THIS checkout, against FreeGSNKE's recorded inverse solve (register record B-21).

★★2026-09-15 (/goal「完善磁平衡相关计算功能 … 前向后向」): one problem to two codes — KEFIT's separatrix outline at
4.041 s as the target, its X-points as nulls, its p'/FF' and Ip, the same EAST card.  fylite designs with
``code/discharge`` (annealed ridge fit, coil limits held, a free-boundary solve each pass); FreeGSNKE's side is the
recorded inverse solve in the case store (isoflux on 24 points of that curve plus null points, Newton).

Held here: the recomputed readings against the recorded ones, the achieved boundary's measured band, and — because the
two designs' CURRENTS differ far more than their boundaries — the null-space reading: all three current sets
(KEFIT's own, FreeGSNKE's, fylite's) forward-solved on the same profiles give separatrices within a few millimetres.

No store, no card, or no kernel library: the gate SKIPS by name.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "corpus/benchmark/inverse_shape_east137985.json"
REPRO_REL, REPRO_ABS = 1e-6, 1e-9
UNHELD = ("notes", "seconds", "environment")

#: ★measured bands (2026-09-15, three significant figures rounded up).  The boundary band is on the FAIR WINDOW
#: (X-point corners excluded, and the band the target curve does not cover — KEFIT's outline stops at Z = +0.658
#: while its upper X-point is at +0.767).  `psin_rms` is each design's forward solve on KEFIT's own map.
#: ★★2026-09-19 re-measured (FR-EQ-001, user ruling: the edge rule is the doors' default).  The old band sat on the node
#: rule, whose design and forward solves leaned on 10 kA of fictitious vertical current; on the edge rule the design holds
#: the column where its last solve left it (the anchor), reads its residual on the coils' own field so the coils take
#: the pairs' job over, and is RELEASED at the end — its currents forward-solved with no anchor.  `fylite_boundary_*`
#: is the anchored design's separatrix; `release_gap_rms_m` what its currents hold by themselves.
B21_BAND = {"fylite_boundary_median_mm": 3.07, "fylite_boundary_p95_mm": 6.48, "fylite_boundary_max_mm": 13.3, "fylite_psin_rms": 0.029, "null_space_psin_spread": 0.0105, "null_space_boundary_median_spread_mm": 2.06, "release_gap_rms_m": 0.0139}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
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
def got(case, tmp_path_factory):
    try:
        return _tool().inverse_shape(case, tmp_path_factory.mktemp("b21"))
    except Exception as e:  # noqa: BLE001 — a host without the card or the library skips by name
        if "device" in str(e).lower() or "library" in str(e).lower() or "discharge" in str(e):
            pytest.skip(f"no code/discharge / EAST card through the tree door here: {e}")
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


def test_b21_the_design_reproduces_its_recorded_readings(got, want):
    _walk(got["currents"], want["currents"], "currents")
    _walk(got["boundary_vs_target"], want["boundary_vs_target"], "boundary_vs_target")
    _walk(got["null_space"], want["null_space"], "null_space")


def test_b21_the_designed_boundary_stays_in_the_band(got):
    b = got["boundary_vs_target"]["fylite"]
    assert b["median_mm"] <= B21_BAND["fylite_boundary_median_mm"], b
    assert b["p95_mm"] <= B21_BAND["fylite_boundary_p95_mm"], b
    assert b["max_mm"] <= B21_BAND["fylite_boundary_max_mm"], b
    assert got["design"]["facts"]["n_at_coil_limit"] == 0.0


def test_b21_the_released_design_holds_itself(got):
    """★★FR-EQ-001: the design's currents, released from the anchor, converge to an equilibrium the COILS hold — the
    virtual pair ends at tens of amperes (under 1e-3 Ip), not the 165 kA a design read on the total field leaned on."""
    r = got["design"]["release"]
    ip = got["inputs"]["ip_A"]
    assert r["release_converged"] == 1.0 and r["release_residual"] <= 1e-9, r
    assert abs(r["release_fb_amp"]) < 1e-3 * ip, r
    assert r["release_gap_rms"] <= B21_BAND["release_gap_rms_m"], r


def test_b21_the_currents_differ_far_more_than_the_equilibria(got):
    """★The finding this record exists for: a shape constrains the coil currents only up to the design's null space.

    fylite's design and FreeGSNKE's differ by tens of kA.t per channel, yet forward-solved on the same profiles (edge
    rule, each converging with tens of amperes in the pair) the separatrices of all three — and KEFIT's own — lie
    within a few millimetres of the same target.  If the current
    difference ever collapses to the noise, this record's reading is stale."""
    c = got["currents"]
    assert c["fylite_vs_freegsnke_rms_kAt"] > 5.0, c
    ns = got["null_space"]
    psin = [ns[k]["compare"]["psin_rms_inside"] for k in ("kefit", "freegsnke", "fylite")]
    axis_r = [ns[k]["compare"]["dR_axis_mm"] for k in ("kefit", "freegsnke", "fylite")]
    axis_z = [ns[k]["compare"]["dZ_axis_mm"] for k in ("kefit", "freegsnke", "fylite")]
    assert max(psin) - min(psin) <= B21_BAND["null_space_psin_spread"], psin
    #: ★2026-09-19: the SEPARATRICES agree (median distance to the target within ~2 mm of one another); the AXES do not —
    #: the released fylite design's column sits ~19 mm below the others'.  The shape pins the boundary, not where the
    #: vertically unstable column balances inside it; the axis spread is reported (the record), not banded.
    bmed = [ns[k]["compare"]["boundary_median_mm"] for k in ("kefit", "freegsnke", "fylite")]
    assert max(bmed) - min(bmed) <= B21_BAND["null_space_boundary_median_spread_mm"], bmed
    assert all(ns[k]["converged"] == 1.0 for k in ("kefit", "freegsnke", "fylite")), ns
    assert ns["fylite"]["compare"]["psin_rms_inside"] <= B21_BAND["fylite_psin_rms"]
    assert c["fylite_vs_kefit_rms_kAt"] > c["freegsnke_vs_kefit_rms_kAt"]
    del axis_r, axis_z


def test_b21_the_target_curve_limits_are_recorded(want):
    """★The target is KEFIT's own outline: 69 points, median segment ~49 mm, and it stops 134 mm short of the upper
    X-point.  The fair window exists because of that; the all-points reading is kept beside it as the caveat."""
    inp = want["inputs"]
    assert inp["target_points"] == 69
    assert inp["target_segment_median_mm"] > 40.0
    assert want["boundary_vs_target_all_points"]["freegsnke"]["max_mm"] > 3 * want["boundary_vs_target"]["freegsnke"]["max_mm"] / 2
