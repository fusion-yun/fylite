"""Fixed-boundary equilibrium gates run from THIS checkout (register records V-19 · B-16).

★★2026-09-15 用户「补全 fixed-boundary 情景」: the kernel's ``code/fixed_boundary`` door makes fylite SOLVE the problem a
fixed-boundary code is handed — an outline held as psi = const, p'(psi_N) and FF'(psi_N) — so the benchmark no longer
reads a residual off someone else's map (``B-10`` → ``V-16``).  The side computations are ``tools/benchmark-fixed-boundary.py``.

* V-19 needs no data: the Solov'ev contour and its closed form are rebuilt here, fylite through the door every run, CHEASE
  rerun when a local build is present (``$CHEASE_EXE``), skipped by name otherwise.
* B-16 needs the fydoc case store (``$FYDOC_ORACLE``, FYDOC-CASE-23, experiment class): fylite's side is recomputed from
  KEFIT's g-file there and held against the recorded readings; CHEASE's side is the recorded, sha256-indexed archive.

No kernel library with ``code/fixed_boundary``: the gate SKIPS by name.

★2026-09-19 (VEQ phase 2, record ``eq-forward-veq-fixed-boundary``): the same door with ``method = veq`` — the parametric
MXH-Chebyshev solve (arXiv:2606.11821, kernel ``veq.rs``) resampled onto the grid method's rectangle.  Its gates run the
Solov'ev case at the tool's cheap and accurate resolutions against the closed form and against the grid method, and the
EAST case against CHEASE's archived NS = 80 map.  A library whose door does not know ``method = veq`` SKIPS them by name.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "corpus/benchmark/fixed_boundary_east137985.json"
ARCHIVE = "corpus/chease/chease_fixed_boundary_east137985.tar.gz"
REPRO_REL, REPRO_ABS = 1e-6, 1e-9

#: ★V-19's measured bands (2026-09-15, three significant figures rounded up; the register's rule)
V19_FYLITE_129 = {"node_error": 5.52e-05, "psin_rms": 1.09e-05, "psin_max": 1.06e-04, "axis_mm": 0.0261, "span_rel": 2.46e-06,
                  "ip_rel": 1.72e-05, "q0_rel": 3.27e-03, "gap_max_m": 4.13e-05}
#: second order: the 65² → 129² ratio of the node error was 8.3 (33² → 65²: 3.2)
V19_ORDER_RATIO = 3.0
V19_CHEASE_80 = {"psin_rms": 3.91e-06, "psin_max": 5.86e-05, "axis_mm": 1.75e-06, "span_rel": 1.99e-08, "ip_rel": 9.36e-10, "q0_rel": 3.56e-06}
#: ★B-16's measured band: fylite 129² against CHEASE NS = NT = 80 on KEFIT's psi_N = 0.995 surface of #137985 t4041_mag
B16_BAND = {"psin_rms": 4.92e-05, "psin_max": 2.66e-04, "axis_mm": 0.00468, "span_rel": 7.54e-04, "ip_rel": 9.68e-04,
            "q_rel_rms_01_09": 1.05e-03, "q_rel_max_01_09": 1.83e-03, "q95_rel": 1.86e-03}

#: ★VEQ's measured bands (2026-09-19, three significant figures rounded up).  ★Numbers that sit at the solve's round-off
#: (below ~1e-8: the node error, the axis, the flux span and q0 of the accurate tier) get a FLOOR instead — the Levenberg-
#: Marquardt path is not bit-reproducible across hosts, and a band at 5e-10 would only measure that.  psin_rms / psin_max
#: are read through a bicubic spline of the 129² resampled map (the tool's `compare`), so they carry the map's
#: interpolation error (2.2e-6 rms), not the solve's; the node error is the solve's.
V19_VEQ = {"cheap": {"node_error": 1.06e-06, "psin_rms": 2.18e-06, "psin_max": 3.99e-05, "axis_mm": 1.75e-05, "span_rel": 1.35e-09,
                     "ip_rel": 2.19e-08, "q0_rel": 2.03e-07},
           "accurate": {"node_error": 1e-08, "psin_rms": 2.17e-06, "psin_max": 4.00e-05, "axis_mm": 1e-06, "span_rel": 1e-09,
                        "ip_rel": 2.37e-08, "q0_rel": 1e-08}}
#: FR-EQ-001's own criterion (FYTOK-SRS-03: fixed-boundary Solov'ev deep interior < 5e-4), held on both tiers as well
FR_EQ_001 = 5e-4
#: grid 129² against veq (accurate) on the same rectangle: the grid method's own error
V19_VEQ_VS_GRID = {"psin_rms": 1.02e-05, "psin_max": 9.39e-05, "axis_mm": 0.0261, "ip_rel": 1.72e-05, "q0_rel": 1.98e-05,
                   "q_rel_rms_01_09": 2.30e-04}
#: ★B-16 with veq (accurate: l = m = 10, 40 x 40) against CHEASE NS = NT = 80 (the case store's archive)
B16_VEQ_BAND = {"psin_rms": 1.00e-04, "psin_max": 1.13e-03, "axis_mm": 0.347, "span_rel": 8.40e-04, "ip_rel": 8.43e-04,
                "q_rel_rms_01_09": 1.04e-03, "q_rel_max_01_09": 1.85e-03, "q95_rel": 2.32e-03}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_fixed_boundary", ROOT / "tools" / "benchmark-fixed-boundary.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    t = _tool()
    try:
        sol = t.Solovev()
        t.fylite_side(sol.problem(), 33)
    except Exception as e:  # noqa: BLE001 — a host without a kernel carrying the door skips by name
        pytest.skip(f"no code/fixed_boundary through the tree door here: {e}")
    return t


def _in(got: dict, band: dict, tag: str):
    for k, v in band.items():
        assert abs(got[k]) <= v, (tag, k, got[k], v)


def test_v19_fylite_recovers_the_solovev_map_inside_its_contour(tool):
    sol = tool.Solovev()
    prob, exact = sol.problem(), sol.side()
    s65, s129 = tool.fylite_side(prob, 65), tool.fylite_side(prob, 129)
    e65, e129 = tool.node_error(sol, s65), tool.node_error(sol, s129)
    got = dict(tool.compare(exact, s129, prob), node_error=e129, gap_max_m=s129["facts"]["gap_max"])
    assert s129["facts"]["converged"] == 1.0
    _in(got, V19_FYLITE_129, "V-19 fylite 129²")
    assert e65 / e129 > V19_ORDER_RATIO, (e65, e129)


def test_v19_chease_on_the_same_contour(tool, tmp_path):
    """The second code on the same problem: CHEASE rerun from the EXPEQ this checkout writes (sign and normalisation
    measured here, not assumed — a wrong sign of p' or TT' does not converge)."""
    if not tool.CHEASE.is_file():
        pytest.skip(f"CHEASE is not built here: {tool.CHEASE} (third_party/chease/BUILD_RUN_RECIPE_fyeq.md)")
    sol = tool.Solovev()
    prob = sol.problem()
    run = tool.chease_run(prob, tmp_path / "ns80", 80, "Solov'ev fixed boundary (V-19)")
    _in(tool.compare(sol.side(), tool.gfile_side(run["EQDSK_COCOS_02.OUT"]), prob), V19_CHEASE_80, "V-19 CHEASE NS 80")


@pytest.fixture(scope="module")
def case(tool) -> Path:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / READINGS).is_file():
        pytest.skip(f"no {READINGS} in the case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    return store / CASE


def _close(got: float, want: float) -> bool:
    return abs(got - want) <= max(REPRO_ABS, REPRO_REL * abs(want))


def test_b16_fylite_reproduces_its_readings_and_stays_in_the_band_against_chease(tool, case):
    import yaml
    want = json.loads((case / READINGS).read_text(encoding="utf-8"))
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    arch = (case / ARCHIVE).read_bytes()
    assert hashlib.sha256(arch).hexdigest() == sums[ARCHIVE.removeprefix("corpus/")] == want["chease_archive_sha256"]
    prob, gbytes = tool.east_problem(case)
    assert hashlib.sha256(gbytes).hexdigest() == want["inputs"]["g_sha256"]
    assert _close(prob["ip_inside"], want["inputs"]["ip_inside_A"])
    s129 = tool.fylite_side(prob, 129)
    for k, v in want["fylite"]["n129"]["facts"].items():
        assert _close(s129["facts"][k], v), ("fylite 129", k, s129["facts"][k], v)
    with tarfile.open(case / ARCHIVE, "r:gz") as tf:
        gb = tf.extractfile("chease_fixed_boundary_east137985/ns80/EQDSK_COCOS_02.OUT").read()
    got = tool.compare(tool.gfile_side(gb), s129, prob)
    for k, v in want["compare"]["fylite_129_vs_chease_80"].items():
        if isinstance(v, float):
            assert _close(got[k], v), ("vs CHEASE", k, got[k], v)
    _in(got, B16_BAND, "B-16")


def test_b16_kefit_context_is_a_reading(case):
    """KEFIT's free-boundary map inside the same surface is context, not the reference: both fixed-boundary codes sit the
    same 2.3 mm (axis) and 0.21 % (psi_N rms) from it — its own 65² discretisation, not either solver's error."""
    want = json.loads((case / READINGS).read_text(encoding="utf-8"))["compare"]
    fy, ch = want["fylite_129_vs_kefit"], want["chease_80_vs_kefit"]
    assert abs(fy["axis_mm"] - ch["axis_mm"]) < 0.05 and abs(fy["psin_rms"] - ch["psin_rms"]) < 1e-4


# ------------------------------------------------------------------------------------------------ method = veq


@pytest.fixture(scope="module")
def veq_tool(tool):
    sol = tool.Solovev()
    try:
        s = tool.fylite_side(sol.problem(), 33, "veq", tool.SOLOVEV_VEQ["cheap"])
    except Exception as e:  # noqa: BLE001 — a library whose door predates method = veq refuses it by name
        pytest.skip(f"this library's code/fixed_boundary has no method = veq: {e}")
    if s["facts"].get("method") != 1.0:
        pytest.skip("this library's code/fixed_boundary ignored method = veq")
    return tool


@pytest.mark.parametrize("tier", ["cheap", "accurate"])
def test_veq_recovers_the_solovev_map_inside_its_contour(veq_tool, tier):
    t = veq_tool
    sol = t.Solovev()
    prob, exact = sol.problem(), sol.side()
    s = t.fylite_side(prob, 129, "veq", t.SOLOVEV_VEQ[tier])
    f = s["facts"]
    assert f["method"] == 1.0 and f["converged"] == 1.0 and f["veq_admissible"] == 1.0 and f["veq_symmetric"] == 1.0
    got = dict(t.compare(exact, s, prob), node_error=t.node_error(sol, s))
    assert got["psin_rms"] < FR_EQ_001, got["psin_rms"]
    _in(got, V19_VEQ[tier], f"V-19 veq {tier}")


def test_veq_and_grid_agree_on_the_same_rectangle(veq_tool):
    t = veq_tool
    prob = t.Solovev().problem()
    g, v = t.fylite_side(prob, 129), t.fylite_side(prob, 129, "veq", t.SOLOVEV_VEQ["accurate"])
    assert g["grid"] == v["grid"]
    for k in ("rg", "zg", "fraction"):
        assert (g["nodes"][k] == v["nodes"][k]).all(), k
    _in(t.compare(g, v, prob), V19_VEQ_VS_GRID, "V-19 grid 129 vs veq")


def test_b16_veq_against_the_chease_archive(veq_tool):
    """The EAST case (KEFIT's psi_N = 0.995 surface of #137985 t4041_mag) with method = veq against CHEASE NS = NT = 80 from
    the case store's sha256-indexed archive.  ★Needs only the KEFIT tar and the CHEASE archive, not the B-16 readings."""
    import yaml
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    case = store / CASE if store is not None else None
    if case is None or not (case / ARCHIVE).is_file():
        pytest.skip(f"no {ARCHIVE} in the case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    t = veq_tool
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    arch = (case / ARCHIVE).read_bytes()
    assert hashlib.sha256(arch).hexdigest() == sums[ARCHIVE.removeprefix("corpus/")]
    prob, _ = t.east_problem(case)
    v = t.fylite_side(prob, 129, "veq", t.EAST_VEQ["accurate"])
    assert v["facts"]["converged"] == 1.0 and v["facts"]["veq_admissible"] == 1.0
    with tarfile.open(case / ARCHIVE, "r:gz") as tf:
        gb = tf.extractfile("chease_fixed_boundary_east137985/ns80/EQDSK_COCOS_02.OUT").read()
    _in(t.compare(t.gfile_side(gb), v, prob), B16_VEQ_BAND, "B-16 veq accurate vs CHEASE 80")
