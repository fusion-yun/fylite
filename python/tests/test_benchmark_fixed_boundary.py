"""Fixed-boundary equilibrium gates run from THIS checkout (register records V-19 · B-16).

★★2026-09-15 用户「补全 fixed-boundary 情景」: the kernel's ``code/fixed_boundary`` door makes fylite SOLVE the problem a
fixed-boundary code is handed — an outline held as psi = const, p'(psi_N) and FF'(psi_N) — so the benchmark no longer
reads a residual off someone else's map (``B-10`` → ``V-16``).  The side computations are ``tools/benchmark-fixed-boundary.py``.

* V-19 needs no data: the Solov'ev contour and its closed form are rebuilt here, fylite through the door every run, CHEASE
  rerun when a local build is present (``$CHEASE_EXE``), skipped by name otherwise.
* B-16 needs the fydoc case store (``$FYDOC_ORACLE``, FYDOC-CASE-23, experiment class): fylite's side is recomputed from
  KEFIT's g-file there and held against the recorded readings; CHEASE's side is the recorded, sha256-indexed archive.

No kernel library with ``code/fixed_boundary``: the gate SKIPS by name.
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
