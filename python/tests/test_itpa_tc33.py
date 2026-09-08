"""C-09：0-D 对 **ITPA TC-33** ITER 15 MA 参考算例（机构共识件，CC BY 4.0）。

★★这是本图里**最强的一条 C 路径**：参考不是某一次运行，而是 ITPA 输运与约束组的
参考算例（Zenodo `10.5281/zenodo.21391776`，JETTO 36.0.0 产出，五个 IDS），且**不受限**
——读者可以自己取回来复算。C-01 / C-02 的参考是受限件，这一条不是。

比什么、怎么摆平
----------------
本仓的 0-D 是**给定剖面**的功率平衡，参考侧是集成模拟的 H 模解。直接对比毫无意义，
所以先把两侧**能摆平的都摆平**，逐项取自参考件自身：几何（R₀ · a · κ · δ）· I_p ·
Z_eff · 外加热功率（EC 16.97 + NBI 32.25 MW）· 以及**体平均密度与电子温度**——
后两项由本门解出峰化指数 `pn` / `pt` 来达成（`brentq`，实测 ⟨n_e⟩ / ⟨T_e⟩ 逐位对上）。

摆平之后剩下的差，才是模型的差。

★★**燃料稀释是这里最大的一项，且默认值是错的**。实测：
`dtf=0.5`（把 n_D = n_T = 0.5 n_e 当作理所当然）给 P_fus **192.88 MW，+33.8 %**；
改用参考件**自己的组分**（分离面 n_D = n_T = 2.6e19 而 n_e = 5.72e19，即 0.4546）
给 **159.42 MW，+10.6 %**——**稀释一项吃掉 69 % 的差**。P_fus ∝ n_D n_T，所以
9 % 的燃料密度误差在功率上是 19 %。★这不是参考侧的口径问题，是「0.5 是个假设」。

余下的 +10.6 % 是**形状**：本仓的 `(1-ρ²)^p` 没有台基，而参考件有（T_e,ped 4.84 keV ·
n_e,ped 7.69e19）。体平均相同而形状不同，聚变功率就不同——⟨σv⟩ 对 T 是超线性的。
这一项**不该靠调峰化去抹平**：抹平了，本门就成了一次曲线拟合，而不是一次比较。

不可比的一项，说在明处
----------------------
`v_loop`：参考件记 −0.0546 V（COCOS 负号，且含 4.21 MA 自举 + 1.07 MA NBI 驱动 +
0.21 MA EC 驱动），本仓 0-D 的环电压是**纯欧姆**、不含非感应电流。两者不是同一个量，
本门**不判它**——判了就是拿一个不含自举的模型去对一个自举占 28 % 的解。

★没有参考件就跳过并点名（它在 fydoc 检出里，本仓不带）。
"""
from __future__ import annotations

import os
import pathlib

import numpy as np
import pytest

REF_DIRS = [
    pathlib.Path(os.environ.get("FYDOC_ORACLE", "/nonexistent")) / "cases/FYDOC-CASE-08-itpa-tc33/corpus",
    pathlib.Path.home() / "workspace/fydoc/cases/FYDOC-CASE-08-itpa-tc33/corpus",
]

#: 参考件自报的 415 s 全局量（`summary` IDS，逐项由 netCDF 读出）。
REF = {"ne0": 1.1571e20, "te0": 34.5569, "ti0": 26.1681,
       "ne_avg": 9.89809e19, "te_avg": 10.8408,
       "r0": 6.2, "a": 1.96771, "kappa": 1.8311, "du": 0.550684, "dl": 0.463029,
       "zeff": 1.39994, "ip_ka": 15000.0, "paux_mw": 16.9736 + 32.249,
       "p_fus_mw": 144.147,
       #: 分离面组分：n_D = n_T = 2.6e19 而 n_e = 5.71984e19
       "fuel_fraction": 2.6e19 / 5.71984e19}

#: 摆平之后仍有的差，取实测 +10.6 % 加一档余量。★带**不是**「够用就行」：
#: 它是一个给定剖面的 0-D 对集成模拟 H 模解的距离，写下来是为了让它变坏时看得见。
BAND = 0.13
#: 默认稀释（0.5）下的差，也钉住——它是本门最有价值的一句话。
BAND_NAIVE_MIN = 0.25


def _ref_dir():
    for d in REF_DIRS:
        if (d / "ITPA-TC33-415s.nc").is_file():
            return d
    return None


@pytest.fixture(scope="module")
def zerod():
    if _ref_dir() is None:
        pytest.skip("没有 ITPA TC-33 参考件（fydoc `cases/FYDOC-CASE-08-itpa-tc33/`）")
    from fylite.io import fydoc as door
    from fylite._paths import KERNEL_LIB
    if not KERNEL_LIB.exists():
        pytest.skip("没有内核（rust/build.sh）")

    def run(pn: float, pt: float, dtf: float) -> dict:
        s = {"ip": REF["ip_ka"], "r0": REF["r0"], "a": REF["a"], "kappa": REF["kappa"],
             "du": REF["du"], "dl": REF["dl"], "ne": REF["ne0"] / 1e19, "te": REF["te0"],
             "tite": REF["ti0"] / REF["te0"], "pn": pn, "pt": pt, "zeff": REF["zeff"],
             "dtf": dtf, "meff": 2.5, "paux": REF["paux_mw"],
             "t_ru": 1.0, "t_ft": 8.0, "t_end": 10.0, "t_on": 1.0, "t_off": 8.0,
             "slice": 100.0, "hfac": 1.0, "tau_law": 0.0, "w0": 1.0, "pfscale": 1.0,
             "phiavail": 0.0, "eqauto": 1.0}
        f = door.complete("code/zerod", {"settings": s, "inputs": {}})["fields"]
        sm, p1 = f["summary"], f["core_profiles"]["profiles_1d"]
        t = np.asarray(sm["time"]["data"], float)
        k = int(np.argmin(abs(t - 5.0)))          # 平顶中段
        ne = np.asarray(p1["electrons"]["density"]["data"], float).reshape(len(t), -1)[k]
        te = np.asarray(p1["electrons"]["temperature"]["data"], float).reshape(len(t), -1)[k]
        r = np.linspace(0.0, 1.0, ne.size)
        va = lambda y: float(np.trapezoid(y * r, r) / np.trapezoid(r, r))  # noqa: E731
        return {"ne_avg": va(ne), "te_avg": va(te) / 1e3,
                "p_fus": float(np.asarray(sm["fusion"]["power"]["value"]["data"], float)[k]) / 1e6}
    return run


@pytest.fixture(scope="module")
def matched(zerod):
    """把体平均摆平到参考件上，返回解出的峰化与两种稀释下的答案。"""
    from scipy.optimize import brentq
    pn = brentq(lambda p: zerod(p, 2.6, 0.5)["ne_avg"] - REF["ne_avg"], 0.01, 3.0, xtol=1e-4)
    pt = brentq(lambda p: zerod(pn, p, 0.5)["te_avg"] - REF["te_avg"], 0.5, 8.0, xtol=1e-4)
    return {"pn": pn, "pt": pt,
            "naive": zerod(pn, pt, 0.5),
            "ref_fuel": zerod(pn, pt, REF["fuel_fraction"])}


def test_the_volume_averages_really_are_matched(matched):
    """★先判摆平本身。摆不平而去比 P_fus，比的是两个不同的等离子体。"""
    got = matched["ref_fuel"]
    assert abs(got["ne_avg"] / REF["ne_avg"] - 1) < 1e-3, got["ne_avg"]
    assert abs(got["te_avg"] / REF["te_avg"] - 1) < 1e-3, got["te_avg"]


def test_the_fusion_power_lands_within_the_band_on_the_reference_composition(matched):
    dev = matched["ref_fuel"]["p_fus"] / REF["p_fus_mw"] - 1
    assert abs(dev) <= BAND, (
        f"P_fus {matched['ref_fuel']['p_fus']:.2f} MW vs 参考 {REF['p_fus_mw']} MW（{dev:+.1%}，带 {BAND:.0%}）")


def test_assuming_half_the_electrons_are_fuel_costs_a_third(matched):
    """★★本门最有价值的一句：`dtf=0.5` 不是中性的缺省，它是一个**假设**。

    参考件自己的组分是 0.4546（分离面 n_D = n_T = 2.6e19，n_e = 5.72e19）。
    P_fus ∝ n_D n_T，所以 9 % 的燃料密度差在功率上是 19 %。这一条钉住那个差**存在**
    且**大**——它变小的那天，要么是缺省改了，要么是参考件换了，两者都该有人看见。"""
    naive = matched["naive"]["p_fus"] / REF["p_fus_mw"] - 1
    ref = matched["ref_fuel"]["p_fus"] / REF["p_fus_mw"] - 1
    assert naive >= BAND_NAIVE_MIN, f"默认稀释下只差 {naive:+.1%}，与实测的 +33.8 % 不符"
    assert naive > ref, "默认稀释应当高估得更多"
