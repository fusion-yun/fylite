"""Equilibrium benchmark gates run from THIS checkout, against KEFIT (register records B-14 · V-18 · B-15).

★★2026-09-15 用户裁定：废弃 libefit 对标，直接对标 KEFIT；平衡 benchmark 在本仓补全、不动内核仓。
Each gate recomputes fylite's side through the tree door (``tools/benchmark-equilibrium.py``) from inputs that live in the
fydoc case store (``$FYDOC_ORACLE``, FYDOC-CASE-23, experiment class — pointers only in the public register) and holds it
against (1) the readings recorded there, to the solver's own reproducibility, and (2) the register's measured band.
KEFIT's side is never rerun here: its answers are the recorded, sha256-indexed archive.

No store, no device card or no kernel library: the gate SKIPS by name — the same policy as every other gate that needs
machine data.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "corpus/benchmark/forward_kefit_east137985.json"
TWIN = "corpus/benchmark/twin_east137985.json"
#: reproducibility of a recomputed reading against the recorded one (same inputs, same library)
REPRO_REL, REPRO_ABS = 1e-6, 1e-9

#: ★B-14's measured band — the worst over the three magnetics-only slices (t4041 / t4944 / t5976 `_mag`), three
#: significant figures rounded up (register rule, 2026-09-14).  The POINT-profile slice is a finding, not in the band.
B14_MAG = ("t4041_mag", "t4944_mag", "t5976_mag")
B14_BAND = {"axis_mm": 4.87, "span_abs": 0.00264, "psin_rms": 0.00737, "psin_max": 0.0181, "boundary_median_mm": 3.43, "boundary_max_mm": 15.5, "xpoint_mm": 6.51}


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def case() -> Path:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / "case.yaml").is_file():
        pytest.skip(f"no {CASE} in the case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    try:
        from fylite import device
        device.document(shot=137985, measurement_chain="east")
    except Exception as e:  # noqa: BLE001 — a host without the card or the runtime library skips by name
        pytest.skip(f"no EAST device card / runtime library here: {e}")
    return store / CASE


def _close(got: float, want: float) -> bool:
    return abs(got - want) <= max(REPRO_ABS, REPRO_REL * abs(want))


def test_b14_the_forward_solve_reproduces_its_recorded_readings(case, tmp_path):
    want = json.loads((case / READINGS).read_text(encoding="utf-8"))
    got = _tool().forward_kefit(case, tmp_path)
    assert got["archive_sha256"] == want["archive_sha256"], "the KEFIT archive the readings were taken on has changed"
    for name, w in want["cases"].items():
        g = got["cases"][name]
        assert g["inputs"]["g_sha256"] == w["inputs"]["g_sha256"] and g["inputs"]["a_sha256"] == w["inputs"]["a_sha256"], name
        for k, v in w["compare"].items():
            if isinstance(v, float):
                assert _close(g["compare"][k], v), (name, k, g["compare"][k], v)


def test_b14_the_forward_solve_stays_in_the_band_on_kefits_magnetics_answers(case):
    rec = json.loads((case / READINGS).read_text(encoding="utf-8"))["cases"]
    for name in B14_MAG:
        c = rec[name]["compare"]
        assert math.hypot(c["dR_axis_mm"], c["dZ_axis_mm"]) <= B14_BAND["axis_mm"], name
        assert abs(c["span_rel"]) <= B14_BAND["span_abs"], name
        assert c["psin_rms_inside"] <= B14_BAND["psin_rms"] and c["psin_max_inside"] <= B14_BAND["psin_max"], name
        assert c["boundary_median_mm"] <= B14_BAND["boundary_median_mm"], name
        assert c["boundary_max_mm"] <= B14_BAND["boundary_max_mm"], name
        assert c["xpoint_dist_mm"] <= B14_BAND["xpoint_mm"], name
        assert abs(c["ip_rel"]) < 1e-9, name          #: Ip is an equality in both codes


def test_b14_the_point_profile_slice_is_recorded_outside_the_band(case):
    """★A finding held as one: KEFIT's POINT-constrained profile at 5.976 s is not reproduced to the magnetics band,
    and fylite's forward solve does not settle on it in 600 iterations.  If this starts passing the band, the record's
    finding is stale — say so rather than let it drift."""
    c = json.loads((case / READINGS).read_text(encoding="utf-8"))["cases"]["t5976_primary"]
    assert c["compare"]["psin_rms_inside"] > B14_BAND["psin_rms"]
    assert c["fylite"]["settled"] == 0.0


#: ★V-18 / B-15's measured band — the one twin (4.041 s coil currents, analytic family e_mp = e_np = 1), three significant
#: figures rounded up.  V-18 is fylite recovering its own forward truth; B-15 is KEFIT on the same synthetic measurements.
#: ★★2026-09-17 `q0_abs` 6.1e-4 → 1.2e-3，**这一格是放宽的，理由必须写在这里**：内核把 q0 从
#: 「最内两面外推」改成「轴上解析极限」（内核仓 d13376b）之后，孪生的真值与重构**不再共享
#: 同一个偏置**——旧算法下那层共同偏置在相减时抵消，把这条差压到 6.1e-4；抵消没了，露出的
#: 是两者的真差 1.19e-3。★**所以这不是变差，是此前那个数被一层抵消美化过**，与本记录
#: 一直写着的「孪生有主场优势」是同一件事的又一次现形。其余各格一位未动。
V18_BAND = {"q0_abs": 0.0012, "q95_abs": 0.00128, "axis_mm": 1.18, "span_abs": 0.000176, "psin_rms": 0.00234, "psin_max": 0.00429, "boundary_median_mm": 0.657, "boundary_max_mm": 1.65, "xpoint_mm": 0.784, "ip_abs": 9.5e-11}
#: ★★2026-09-17 `q0_abs` 4.87e-2 → 5.03e-2，理由与 V18 那格是同一件事的另一面：
#: **KEFIT 自己一个数都没动，是我们的真值挪了**——内核把 q0 改成轴上解析极限之后，
#: 孪生真值的 q0 从 1.36971 到 1.37201。于是 KEFIT 与真值的距离按**更准的真值**重新量出来，
#: 变大了。★**带放宽不是迁就 KEFIT，是承认此前那个数是拿一个偏了的真值量出来的。**
B15_BAND = {"q0_abs": 0.0503, "q95_abs": 0.0107, "axis_mm": 1.33, "span_abs": 0.00853, "psin_rms": 0.00681, "psin_max": 0.0132, "boundary_median_mm": 1.57, "boundary_max_mm": 4.17, "xpoint_mm": 2.19, "ip_abs": 0.00248}


@pytest.fixture(scope="module")
def twin_run(case, tmp_path_factory):
    out = tmp_path_factory.mktemp("twin")
    return _tool().twin(case, out, None, None)


def _in_band(side: dict, band: dict, tag: str):
    c = side["compare"]
    assert abs(side["q0_rel"]) <= band["q0_abs"] and abs(side["q95_rel"]) <= band["q95_abs"], (tag, side["q0_rel"], side["q95_rel"])
    assert math.hypot(c["dR_axis_mm"], c["dZ_axis_mm"]) <= band["axis_mm"], tag
    assert abs(c["span_rel"]) <= band["span_abs"] and abs(c["ip_rel"]) <= band["ip_abs"], tag
    assert c["psin_rms_inside"] <= band["psin_rms"] and c["psin_max_inside"] <= band["psin_max"], tag
    assert c["boundary_median_mm"] <= band["boundary_median_mm"] and c["boundary_max_mm"] <= band["boundary_max_mm"], tag
    assert c["xpoint_dist_mm"] <= band["xpoint_mm"], tag


def test_v18_fylite_recovers_the_twin_truth_and_reproduces_its_readings(case, twin_run):
    want = json.loads((case / TWIN).read_text(encoding="utf-8"))
    got = twin_run
    for k, v in want["truth"]["facts"].items():
        assert _close(got["truth"]["facts"][k], v), ("truth", k)
    assert got["fylite"]["zc_anchor_m"] == want["fylite"]["zc_anchor_m"]
    for k, v in want["fylite"]["compare"].items():
        if isinstance(v, float):
            assert _close(got["fylite"]["compare"][k], v), ("fylite", k, got["fylite"]["compare"][k], v)
    _in_band(got["fylite"], V18_BAND, "V-18")


def test_b15_kefit_on_the_twin_measurements_stays_in_its_band(case, twin_run):
    """KEFIT's answer is the recorded run (archive, sha256-indexed); only the comparison is recomputed, against the truth
    this checkout rebuilds — so a change in fylite's forward solve shows up here too."""
    import tarfile
    tool = _tool()
    want = json.loads((case / TWIN).read_text(encoding="utf-8"))["kefit"]
    with tarfile.open(case / "corpus/kefit/kefit_twin_east137985.tar.gz", "r:gz") as tf:
        name = next(m.name for m in tf.getmembers() if "/g137985." in m.name)
        gbytes = tf.extractfile(name).read()
    from fylite.io import geqdsk
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "g").write_bytes(gbytes)
        ref = tool.kefit_map(geqdsk.read_geqdsk(Path(d) / "g"))
    truth, _meas, _dev, _raw = tool.twin_truth(case)
    cmpd = tool.compare_maps(truth["map"], ref)
    for k, v in want["compare"].items():
        if isinstance(v, float):
            assert _close(cmpd[k], v), ("kefit", k, cmpd[k], v)
    _in_band(want, B15_BAND, "B-15")


#: ★B-12 (EAST #137985 on raw-tree inputs, fylite and KEFIT on the same numbers) is a two-code reading that is NOT judged:
#: there is no band.  What its gate pins is that the readings and the three archives they were taken from are the ones
#: the case registered — sha256 against `case.yaml` — and that the block still says what the register record says.
B12_ARCHIVES = ("raw/raw_slices_east137985.json", "kefit/kefit_raw_east137985.tar.gz", "fylite/fylite_raw_east137985.tar.gz",
                "benchmark/comparison_readings_east137985.fyo.jsonld")
B12_REJECTED = ["HBPH1T", "HBPH2T", "HBPH3T", "HBPD8T", "HBPD10T", "HBPH1N", "HBPD10N"]


def test_b12_the_raw_tree_readings_are_the_registered_ones(case):
    import hashlib
    import yaml
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    for rel in B12_ARCHIVES:
        assert hashlib.sha256((case / "corpus" / rel).read_bytes()).hexdigest() == sums[rel], rel
    doc = json.loads((case / "corpus/benchmark/comparison_readings_east137985.fyo.jsonld").read_text(encoding="utf-8"))
    block = next(t for t in doc["fylite:tiers"] if t.get("@id") == "#R-raw-trees")
    rej = block["fylite:variants"]["rejected"]
    assert rej["rejected_probes"] == B12_REJECTED
    for key in ("4.041", "4.944", "5.976"):
        s = rej["slices"][key]
        assert s["fylite_M"]["converged"] is True, key
        assert (s["kefit"]["mag"] or {}).get("problems") == [], key
    assert all(block["fylite:variants"]["all_probes"]["slices"][k]["fylite_M"]["chi2"] > 1000 for k in ("4.041", "4.944", "5.976"))
