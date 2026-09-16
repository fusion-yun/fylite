"""The ITER reference separatrix as an inverse problem, run from THIS checkout (register record V-22).

★★2026-09-15 (/goal「完善磁平衡相关计算功能 … 前向后向」, second shape): B-21 posed the static inverse problem on EAST
against FreeGSNKE's inverse solve.  ITER has no reference side at all — the TEQ / TOSCA ITER equilibria are
pointer-only entries into an unset ``$ITER_SCENARIO_ROOT`` and FreeGSNKE carries no ITER machine — so this record is a
VERIFICATION: what is held is the design's own closure (the coils it asks for, the separatrix they produce, how far
that sits from the requested curve) and the settings the shape turned out to need.

★The card carries NO supply rating, so the anneal is unbounded.  ``max_abs_MAt`` is therefore held as a band, not
printed as a detail: without it a design may buy shape with current no coil set could carry (measured: the profile
exponent ``enp`` = 0.5 reaches kappa 1.834 — the closest to target of any variant — by asking for 37.5 MA.t and never
converging; given FOUR TIMES the round budget it does not converge either, its residual RISES from 0.12 to 0.32, so
that is instability, not a budget that was too small).

No card or no kernel library: the gate SKIPS by name.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READINGS = "inverse_shape_iter.json"
REPRO_REL, REPRO_ABS = 1e-6, 1e-9
UNHELD = ("notes", "seconds", "unbounded_because")

#: ★bands measured on this card (2026-09-15, three significant figures rounded up).  They are the design's own
#: closure, not an agreement with a second code: the target is the card's digitised reference separatrix, closed
#: through its X-point corner (it is open there by 322 mm), and the METIS wall is injected as the limiter.
V22_BAND = {"median_mm": 15.5, "p95_mm": 69.9, "max_mm": 124.0, "shape_error": 0.0308, "max_abs_MAt": 30.7}
#: ★`emp` = 2 is the last setting that still CONVERGES: emp 3 scores slightly better on shape_error (0.0269) but
#: exhausts its 600-round budget at residual 0.019, and `enp` 0.5 reaches the best kappa of all by asking for
#: 37.5 MA.t and never settling — at 2400 rounds (4x, 938 s) its residual RISES to 0.32, so the non-convergence is
#: the setting's, not the budget's.  The bands above are the converged design's.

#: what the shape needs, and what it cannot have: kappa stays ~4 % below the target at every setting that keeps the
#: currents physical; delta_lower likewise.  Held as a REading so that a future change is visible, not as a band.
V22_SHAPE_TARGET = {"r0": 6.2209, "a": 1.9819, "kappa": 1.8492, "delta_upper": 0.3456, "delta_lower": 0.5432, "z0": 0.3660}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def want() -> dict:
    p = ROOT / "docs" / "benchmark" / "readings" / READINGS
    if not p.is_file():
        pytest.skip(f"no {READINGS} recorded in docs/benchmark/readings (write it with `inverse-shape-iter --out`)")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def got(tmp_path_factory):
    try:
        return _tool().iter_shape(tmp_path_factory.mktemp("v22"))
    except Exception as e:  # noqa: BLE001 — a host without the card or the library skips by name
        if "device" in str(e).lower() or "library" in str(e).lower() or "discharge" in str(e):
            pytest.skip(f"no code/discharge / ITER card through the tree door here: {e}")
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


def test_v22_the_design_reproduces_its_recorded_readings(got, want):
    _walk(got["separatrix_vs_target"], want["separatrix_vs_target"], "separatrix_vs_target")
    _walk(got["currents"], want["currents"], "currents")
    _walk(got["design"]["facts"], want["design"]["facts"], "design/facts")


@pytest.mark.skipif(V22_BAND["median_mm"] is None, reason="bands are filled once the readings are registered")
def test_v22_the_designed_separatrix_stays_in_the_band(got):
    s = got["separatrix_vs_target"]
    assert s["median_mm"] <= V22_BAND["median_mm"], s
    assert s["p95_mm"] <= V22_BAND["p95_mm"], s
    assert s["max_mm"] <= V22_BAND["max_mm"], s
    assert got["design"]["facts"]["shape_error"] <= V22_BAND["shape_error"]


@pytest.mark.skipif(V22_BAND["max_abs_MAt"] is None, reason="bands are filled once the readings are registered")
def test_v22_the_design_does_not_buy_shape_with_current_the_machine_lacks(got):
    """★The card has no supply rating, so nothing in the door stops the anneal from asking for anything.

    This band is the stand-in: the recorded design's peak channel current, rounded up.  A future setting that
    improves the shape by exceeding it is not a better design — it is a design for a different machine."""
    assert got["currents"]["max_abs_MAt"] <= V22_BAND["max_abs_MAt"], got["currents"]["max_abs_MAt"]
    assert got["currents"]["limits_held"] is False


def test_v22_the_target_curve_is_recorded_with_its_defects(want):
    """★The ITER card's reference separatrix is a digitised METIS curve: 248 finite points, ~67 mm apart, and OPEN
    at the X-point by 322 mm.  The record closes it through the corner; if a later card ships a closed curve, this
    reading is stale and the closure should go."""
    inp = want["inputs"]
    assert inp["target_points"] == 248
    assert inp["target_open_gap_mm"] > 300.0
    assert inp["target_closed_through"] == [5.15, -3.40]
