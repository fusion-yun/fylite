"""Conducting-wall and vertical-instability gates run from THIS checkout, against FreeGSNKE (register records B-17 · B-18).

★★2026-09-15 用户「补全导体壁，垂直不稳定性算例」: fylite's side is recomputed through the tree door every run —
``code/wall`` (the passive set as a circuit) and ``code/vstab`` (the rigid-plasma dispersion) on the EAST card — by
``tools/benchmark-wall-vstab.py``; FreeGSNKE's side is the recorded, sha256-indexed run in the fydoc case store
(``$FYDOC_ORACLE``, FYDOC-CASE-23, experiment class: KEFIT's equilibrium and coil currents drive it).  Held: the
recomputed readings against the recorded ones (the solver's own reproducibility), and the measured bands.

No store, no card, or a kernel without ``code/wall`` (the prebuilt runtime library predates it — point
``$FYLITE_KERNEL_LIB`` at a current build): the gate SKIPS by name.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "corpus/benchmark/wall_vstab_east137985.json"
REPRO_REL, REPRO_ABS = 1e-6, 1e-9

#: ★measured bands (2026-09-15, the worst over the four sets / two passive sets, three significant figures rounded up)
B17_BAND = {"tau1_rel": 0.000762, "M_diag_rel_median": 0.0148, "M_diag_rel_max": 0.0801, "M_offdiag_rel_p95": 0.00542,
            "M_frobenius_rel": 0.0166, "R_rel_absmax": 0.0112}
B18_BAND = {"gamma_rel": 0.00372, "k_rel": 0.003, "k_ideal_rel": 0.000711, "margin_abs": 0.00504}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_wall_vstab", ROOT / "tools" / "benchmark-wall-vstab.py")
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
def got(case):
    try:
        return _tool().readings(case)
    except Exception as e:  # noqa: BLE001 — a host without the card or a kernel carrying code/wall skips by name
        if "code/wall" in str(e) or "device" in str(e).lower() or "library" in str(e).lower():
            pytest.skip(f"no code/wall / EAST card through the tree door here: {e}")
        raise


def _close(g: float, w: float) -> bool:
    return abs(g - w) <= max(REPRO_ABS, REPRO_REL * abs(w))


def _walk(g, w, path=""):
    if isinstance(w, dict):
        for k, v in w.items():
            if k != "notes":
                _walk(g[k], v, f"{path}/{k}")
    elif isinstance(w, list):
        for i, v in enumerate(w):
            _walk(g[i], v, f"{path}[{i}]")
    elif isinstance(w, float):
        assert _close(g, w), (path, g, w)
    else:
        assert g == w, (path, g, w)


def test_the_freegsnke_run_is_the_registered_one(case):
    import yaml
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    tool = _tool()
    for rel in (tool.ARCHIVE, READINGS):
        assert hashlib.sha256((case / rel).read_bytes()).hexdigest() == sums[rel.removeprefix("corpus/")], rel


def test_b17_the_wall_modes_reproduce_and_stay_in_the_band_against_freegsnke(case, got):
    want = json.loads((case / READINGS).read_text(encoding="utf-8"))
    _walk(got["wall"], want["wall"], "wall")
    for sname, s in got["wall"]["sets"].items():
        assert abs(s["tau1_rel"]) <= B17_BAND["tau1_rel"], sname
        assert s["M"]["diag_rel_median"] <= B17_BAND["M_diag_rel_median"] and s["M"]["diag_rel_max"] <= B17_BAND["M_diag_rel_max"], sname
        assert s["M"]["offdiag_rel_p95"] <= B17_BAND["M_offdiag_rel_p95"] and s["M"]["frobenius_rel"] <= B17_BAND["M_frobenius_rel"], sname
        assert s["R_rel_absmax"] <= B17_BAND["R_rel_absmax"], sname


def test_b18_the_rigid_dispersion_reproduces_and_stays_in_the_band_against_freegsnke(case, got):
    want = json.loads((case / READINGS).read_text(encoding="utf-8"))
    _walk(got["vstab"], want["vstab"], "vstab")
    for sname, s in got["vstab"]["sets"].items():
        c = s["compare"]
        assert abs(c["gamma_rel"]) <= B18_BAND["gamma_rel"] and abs(c["k_rel"]) <= B18_BAND["k_rel"], sname
        assert abs(c["k_ideal_rel"]) <= B18_BAND["k_ideal_rel"] and abs(c["margin_abs"]) <= B18_BAND["margin_abs"], sname


def test_b18_the_deformable_growth_rate_is_a_reading_not_a_band(case):
    """★FreeGSNKE's deformable plasma is physics the rigid model does not carry: with all three passive sets its growth
    rate is 2.2x its own rigid one on this near-double-null equilibrium (the Jacobian's linearity was not checked
    independently).  If that ratio falls near 1, the record's finding is stale — say so rather than let it drift."""
    s = json.loads((case / READINGS).read_text(encoding="utf-8"))["vstab"]["sets"]
    assert s["all"]["readings"]["deformable_over_rigid_gamma"] > 1.5
    assert 0.8 < s["inner_shell"]["readings"]["deformable_over_rigid_gamma"] < 1.0
