"""后验协方差与 sigma 带的门（register record `eq-reconstruct-posterior-bands`· `NR-EQ-003`）。

★判据只有一句「后验 / sigma 带随 fit 报告出」。**报出来不难，报得对才难**，所以这里守两件：
带随测量 sigma **精确线性**地走，以及协方差是一个合法的协方差（对称、半正定）。
★蒙特卡洛那道锚（照它说的噪声反复拟合，系数真按它散开）在内核仓。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
RECORDED = ROOT / "docs/benchmark/readings/uncertainty_east137985.json"


def _tool():
    spec = importlib.util.spec_from_file_location(
        "benchmark_uncertainty", ROOT / "tools" / "benchmark-uncertainty.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def got() -> dict:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / "case.yaml").is_file():
        pytest.skip(f"no {CASE} in the case store")
    try:
        from fylite import device
        device.document(shot=137985, measurement_chain="east")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no EAST device card / runtime library here: {e}")
    return _tool().readings(store / CASE)


def test_the_bands_scale_exactly_with_the_measurement_sigma(got):
    """★★测量 sigma 整体乘 k，后验 sigma 也该乘 k —— 线性拟合的**精确**性质。

    ★★**这一格是这条记录的要害**：一条不随输入 sigma 动的带不是不确定度，是装饰。
    而它恰恰最容易看起来是对的——量它的人若没真改到输入，得到的正是完美的不变性。
    """
    for k, r in got["scaling"]["pprime_sigma_ratio"].items():
        assert r == pytest.approx(float(k), rel=1e-9), (k, r)
    for k, v in got["scaling"]["coef_sigma_ratio"].items():
        for c in v:
            assert c == pytest.approx(float(k), rel=1e-9), (k, v)


def test_the_covariance_is_a_covariance(got):
    """★对称且半正定——截断 SVD 之后仍必须是一个合法的协方差。"""
    for k, r in got["runs"].items():
        tr = sum(s * s for s in r["coef_sigma"])
        assert r["cov_is_symmetric"] < 1e-9 * max(tr, 1.0), (k, r["cov_is_symmetric"])
        assert r["cov_min_eigenvalue"] > -1e-9 * max(tr, 1.0), (k, r["cov_min_eigenvalue"])


def test_the_band_is_reported_wide_enough_to_be_honest(got):
    """★带要真有宽度：纯磁测量拟合 p' 时，1 sigma 带与 p' 本身同量级。

    ★这不是一个精度指标，是一条**诚实性**检查——一个把带算成零的实现同样能过
    上面两格（零乘 k 还是零），而它等于没有报不确定度。
    """
    b = got["runs"]["1.0"]
    assert b["pprime_sigma_max"] > 0.0 and b["ffprim_sigma_max"] > 0.0, b
    assert b["pprime_band_over_value_median"] > 0.05, b


def test_the_recorded_readings_are_what_this_checkout_computes(got):
    want = json.loads(RECORDED.read_text(encoding="utf-8"))
    for k in want["runs"]:
        assert got["runs"][k]["pprime_sigma_max"] == pytest.approx(
            want["runs"][k]["pprime_sigma_max"], rel=1e-9), k
