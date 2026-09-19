"""线圈受力与导体表面场的门（register record `mhd-vertical-coil-forces-analytic` · `FR-EQ-014`）。

★★判据的三条解析锚（单环自感环向力 · 双环互感力 dM/dz · 环心场 mu0 I / 2R）是**内核仓**的
Rust 单测：它们不需要装置卡，也不该等一张卡。这里守的是另一件事——**那些性质在一台真机器上
仍然成立吗**，以及这一支自己的两条读数（环向项与净径向力的分家、表面场的离散敏感）。

★没有案例库、没有装置卡、没有运行库：按名跳过，与本册其余需要机器数据的门同一条政策。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
RECORDED = ROOT / "docs/benchmark/readings/coil_forces_east137985.json"

#: 牛顿第三定律不是收敛判据 —— 门卡在机器精度上，不卡一个工程容差
CANCEL_TOL = 1.0e-11


def _tool():
    spec = importlib.util.spec_from_file_location(
        "benchmark_coil_forces", ROOT / "tools" / "benchmark-coil-forces.py")
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
    except Exception as e:  # noqa: BLE001 — 没有卡或运行库就按名跳过
        pytest.skip(f"no EAST device card / runtime library here: {e}")
    return store / CASE


@pytest.fixture(scope="module")
def got(case) -> dict:
    return _tool().readings(case)


def test_the_vertical_forces_cancel_over_the_whole_set(got):
    """★牛顿第三定律：没有等离子体的一组导体，竖直力必须逐对抵消。

    ★★**这是这一支里最便宜、也最能抓住符号错的一条**，而且它在每一个细丝档上
    都该成立 —— 抵消来自 `dM/dz` 的反对称性，与离散多细无关。
    """
    for nu, s in got["filament_sweep"].items():
        rel = s["f_z_net_over_absmax"]
        assert abs(rel) < CANCEL_TOL, (nu, s)


def test_the_hoop_term_is_outward_on_every_energised_conductor(got):
    """★环向项按 I^2 走，永远向外 —— 每一件通电导体都不例外。"""
    assert got["at_nu_8"]["hoop_outward_everywhere"] is True
    for nu, s in got["filament_sweep"].items():
        assert s["hoop_outward_count"] == s["energised_count"], (nu, s)


def test_a_weakly_energised_outer_coil_is_pulled_inward_by_the_stack(got):
    """★★环向项与**净**径向力是两件事，而这台机器上它们连符号都不同。

    弱励磁的外侧线圈（R = 3.27 m，0.02 MA·t）自身环向项只有 ~0.001 MN，而内侧那摞
    的互吸大它约五倍，于是**净**径向力向内。★这条守的是「两者分开报」这件事本身：
    若哪天只剩净值，读者会把这读成缺陷 —— 而它是物理。
    """
    inward = got["at_nu_8"]["net_f_r_inward"]
    assert inward, "这台卡上本该有净径向力向内的弱励磁外侧线圈"
    for e in inward:
        assert e["f_r_hoop_MN"] > 0.0, e          # 它自己的环向项仍向外
        assert e["f_r_MN"] < 0.0, e               # 净值向内
        assert abs(e["f_r_hoop_MN"]) < abs(e["f_r_MN"]), e   # 被互吸压过


def test_the_surface_field_now_converges_with_the_filament_count(got):
    """★★表面场**收敛了**（2026-09-19）：导体自己的场改为面积分（极坐标 Gauss 求积，内核 `surface_field_converged`），
    不再是半个网格外的细丝采样。4 / 8 / 16 档的峰值散布从 7.1 % 降到 4e-4——剩下的是**其他**线圈的细丝离散，
    它们离得远、收敛得快。★旧的细丝采样值低 7–10 %：半格外取样取不到导体表面的峰。"""
    bs = got["convergence"]["b_surface_max_T"]
    assert got["convergence"]["b_surface_spread_rel"] < 1e-3, bs
    assert any("converged area integral" in n for n in got["at_nu_8"]["notes"]), got["at_nu_8"]["notes"]


def test_the_recorded_readings_are_what_this_checkout_computes(got):
    """★记录引的那份读数与本检出现算的一致 —— 记录里的数不会悄悄过期。"""
    want = json.loads(RECORDED.read_text(encoding="utf-8"))
    for nu in want["filament_sweep"]:
        for k in ("f_z_absmax_N", "f_r_absmax_N", "b_surface_max_T"):
            assert got["filament_sweep"][nu][k] == pytest.approx(
                want["filament_sweep"][nu][k], rel=1e-9), (nu, k)
    assert np.isclose(got["at_nu_8"]["b_surface_T"]["max"],
                      want["at_nu_8"]["b_surface_T"]["max"], rtol=1e-9)
