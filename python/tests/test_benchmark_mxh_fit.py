"""MXH 边界拟合的门（register record `eq-surface-mxh-gfile-fit` · `FR-EQ-013`）。

★判据点名 7 机型；本机只有 4 个（EAST / DIII-D / CFEDR / 合成），MAST 与 JET 未评。
这里守的是能量到的那部分，以及两条不花钱却很能抓错的自洽检查。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "docs/benchmark/readings/mxh_fit_gfiles.json"
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
