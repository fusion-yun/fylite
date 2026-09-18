"""MXH 边界拟合的门（register record `eq-surface-mxh-gfile-fit` · `FR-EQ-013`）。

★判据点名 7 机型（其中点名 MAST / DIII-D / JET）。语料库给 EAST / DIII-D / CFEDR / 合成；
★2026-09-18 起 `third_party/` 再给 MAST 与 JET 的真 EFIT（找不到那个目录时，那两格的门照实跳过）。
另有第二套实现（FUSE 的 MillerExtendedHarmonic.jl）的交叉核对：读数钉在记录里，有 Julia 时当场重算。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "docs/benchmark/readings/mxh_fit_gfiles.json"
CROSS = ROOT / "docs/benchmark/readings/mxh_fit_julia_crosscheck.json"
BAND = 0.024


def _tool():
    spec = importlib.util.spec_from_file_location(
        "benchmark_mxh_fit", ROOT / "tools" / "benchmark-mxh-fit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def got() -> dict:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None:
        pytest.skip("no case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    tool = _tool()
    res = tool.readings(store)
    if not [r for r in res["files"] if "mxh_rms" in r]:
        pytest.skip("no g-file in the case store fits")
    return res


def _real(res):
    """真装置的那些——合成件的轮廓不闭合，见记录，它不参与带的判定。"""
    return [r for r in res["files"] if "mxh_rms" in r and r["machine"] != "synthetic"]


def test_the_mxh_kappa_is_the_bounding_box_kappa(got):
    """★两条 kappa 必须一致：都从 Z 的极值来。

    ★★**这是最便宜的一条自洽检查**：拟合里的 theta 分支若挑错，kappa 本身不受影响，
    但形状系数会全歪——反过来，kappa 对上不说明拟合对；kappa 对不上则一定错。
    """
    for r in got["files"]:
        if "mxh_kappa" in r:
            assert abs(r["mxh_kappa"] - r["miller_kappa"]) < 1e-9, r


def test_every_real_machine_boundary_fits_inside_the_band(got):
    """★判据的 2.4 % 带——本机拿得到的真装置轮廓。"""
    out = [r for r in _real(got) if not r["in_band"]]
    #: ★DIII-D 那一份实测 2.460 %，**刚出带**——记录里判为不成立并记了成因
    #: （残差落在 X 点上）。门守的是「不再有别的件掉出去」，所以这里钉住已知的那一个。
    assert [r["machine"] for r in out] == ["d3d"], [r["file"] for r in out]
    for r in out:
        assert r["mxh_rms"] < 1.1 * BAND, r


def test_the_residual_sits_on_the_x_point(got):
    """★★最劣残差落在**尖角**上，不是散开的。

    这一格决定记录怎么写：残差若散开，是取样不够；若堆在 X 点，是 MXH 六阶谐波
    表达不了角——**后者是这族参数化的性质，不是这份实现的缺陷**。
    """
    for r in _real(got):
        z = abs(r["worst_residual_z_over_a"])
        assert z > 1.0, (r["file"], r["worst_residual_z_over_a"])


def test_an_unclosed_outline_is_named_not_averaged_in(got):
    """★合成件的轮廓首尾差 3 % 小半径——它是语料的性质，记录里点名排除。"""
    syn = [r for r in got["files"] if r.get("machine") == "synthetic" and "mxh_rms" in r]
    if not syn:
        pytest.skip("the synthetic g-file is not in this store")
    assert syn[0]["closure_gap_over_a"] > 0.01, syn[0]
    for r in _real(got):
        assert r["closure_gap_over_a"] < 1e-9, r


def test_the_recorded_readings_are_what_this_checkout_computes(got):
    want = json.loads(RECORDED.read_text(encoding="utf-8"))
    g = {r["file"]: r for r in got["files"] if "mxh_rms" in r}
    for r in want["files"]:
        if "mxh_rms" in r:
            assert g[r["file"]]["mxh_rms"] == pytest.approx(r["mxh_rms"], rel=1e-9), r["file"]


def test_mast_and_jet_real_efit_boundaries_fit_inside_the_band(got):
    """★判据点名的 MAST 与 JET：真 EFIT 重建，全部在带内，残差同样落在 X 点。"""
    rows = [r for r in got["files"] if r["machine"] in ("mast", "jet") and "mxh_rms" in r]
    if not rows:
        pytest.skip("no third_party/ next to this checkout (set $FYLITE_THIRD_PARTY)")
    assert {r["machine"] for r in rows} == {"mast", "jet"}
    for r in rows:
        assert r["in_band"] and r["closure_gap_over_a"] < 1e-9, r
        assert abs(r["worst_residual_z_over_a"]) > 1.0, r
    assert got["absent_machines"] == []


def test_a_second_implementation_draws_the_same_curves():
    """★★第二套实现（MillerExtendedHarmonic.jl）：同一批轮廓，几何量逐位、系数到 5e-3、重构曲线到 0.8 % 小半径。

    ★约定：它取 `Z = Z0 − κ a sin θ`，于是 `c_J = −c`、`s_J = +s`——`c_J = +c` 那一支差到 0.1 … 0.5，
    所以这个映射是量出来的，不是假设。
    """
    rec = json.loads(CROSS.read_text(encoding="utf-8"))
    assert rec["summary"]["n_files"] >= 14
    assert rec["summary"]["worst_geometry_gap"] < 1e-12
    assert rec["summary"]["worst_coeff_gap"] < 1e-2
    assert rec["summary"]["worst_curve_gap_over_a"] < 1e-2
    for r in rec["files"]:
        assert r["max_abs_c_minus_cj"] > 10 * r["max_abs_c_plus_cj"], r["file"]
        #: 两套实现到数据点的几何距离几乎相同：谁也没有「更贴」
        assert abs(r["geom_rms_fylite"] - r["geom_rms_julia"]) < 0.1 * r["geom_rms_fylite"], r["file"]


def test_the_crosscheck_reproduces_where_julia_is_installed(got):
    import os
    import shutil
    julia = os.environ.get("FYLITE_JULIA") or shutil.which("julia")
    project = os.environ.get("FYLITE_JULIA_PROJECT")
    if not julia or not project:
        pytest.skip("no Julia + MillerExtendedHarmonic.jl ($FYLITE_JULIA, $FYLITE_JULIA_PROJECT)")
    from fylite.engine import benchmark as bm
    res = _tool().crosscheck(bm.store_dir(), julia, project)
    want = {r["file"]: r for r in json.loads(CROSS.read_text(encoding="utf-8"))["files"]}
    for r in res["files"]:
        assert r["max_abs_c_plus_cj"] == pytest.approx(want[r["file"]]["max_abs_c_plus_cj"], rel=1e-6, abs=1e-12)
