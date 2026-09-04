"""闸子：物理校验册（`fylite.engine.physics`）量的是物理，不是措辞。

★★判据是**解析构造**，不是录音：本文件里的平衡是一族 Grad–Shafranov 的精确解
（ψ = aR⁴ + bR²Z² + cZ² + dR² + e ⟹ Δ*ψ = (8a+2b)R² + 2c，取 p′、ff′ 为常数即可
逐项配平），所以「残差应当为零」这句话在这里是可证的，而不是「上次跑出来是这样」。
每条检查都成对判：**精确解要过，动过手脚的要不过** —— 只判前者的闸子会让一条
永远返回 `pass` 的检查活下来。

★不需要内核：本册子读的是**已经产出的 fyo 文档**，所以这份闸子在没有
`libfylite_kernel.so` 的检出里照跑。
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from fylite import fyo
from fylite.engine import physics as ph

MU0 = 4e-7 * math.pi
E = 1.602176634e-19


# --------------------------------------------------------------------------- #
# 一个精确解，和它的文档
# --------------------------------------------------------------------------- #
#: Δ*ψ = (8a + 2b) R² + 2c，与 GS 的 −μ₀R²p′ − ff′ 逐项配平：
#: 8a + 2b = −μ₀ p′，2c = −ff′
P_PRIME = -2.0e4          # dp/dψ [Pa/Wb]
FF_PRIME = -0.5           # f df/dψ [T²m²/Wb]
_A = 0.002
_B = 0.5 * (-MU0 * P_PRIME - 8 * _A)
_C = -0.5 * FF_PRIME
_D = -0.02
_E = 0.1


def psi_exact(R, Z):
    return _A * R ** 4 + _B * R ** 2 * Z ** 2 + _C * Z ** 2 + _D * R ** 2 + _E


def equilibrium_doc(*, perturb: float = 0.0, n: int = 65) -> dict:
    """一份 `fyo:equilibrium`：二维 ψ 是上面的精确解，源函数是配平它的那一对。"""
    gr = np.linspace(2.0, 4.0, n)
    gz = np.linspace(-1.0, 1.0, n)
    RR, ZZ = np.meshgrid(gr, gz, indexing="ij")          # psi_2d 是 [R, Z]
    psi2d = psi_exact(RR, ZZ)
    if perturb:
        psi2d = psi2d + perturb * float(np.ptp(psi2d)) * np.sin(6 * RR) * np.cos(6 * ZZ)
    #: 边界：椭圆，整条在网格内（精确解处处满足 GS，所以取哪条闭曲线都成立）
    th = np.linspace(0.0, 2 * np.pi, 129)
    br, bz = 3.0 + 0.7 * np.cos(th), 0.75 * np.sin(th)
    psi_axis = float(psi_exact(3.0, 0.0))
    psi_bnd = float(psi_exact(3.7, 0.0))
    psi1d = np.linspace(psi_axis, psi_bnd, 33)

    doc = {"@context": {}, "@id": "test/equilibrium", "@type": "fyo:equilibrium"}
    fyo.put(doc, "EQUILIBRIUM", "grid_r", gr.tolist())
    fyo.put(doc, "EQUILIBRIUM", "grid_z", gz.tolist())
    fyo.put(doc, "EQUILIBRIUM", "psi_2d", psi2d.tolist())
    fyo.put(doc, "EQUILIBRIUM", "psi_1d", psi1d.tolist())
    fyo.put(doc, "EQUILIBRIUM", "dpressure_dpsi", [P_PRIME] * psi1d.size)
    fyo.put(doc, "EQUILIBRIUM", "f_df_dpsi", [FF_PRIME] * psi1d.size)
    fyo.put(doc, "EQUILIBRIUM", "psi_axis", psi_axis)
    fyo.put(doc, "EQUILIBRIUM", "psi_boundary", psi_bnd)
    fyo.put(doc, "EQUILIBRIUM", "boundary_r", br.tolist())
    fyo.put(doc, "EQUILIBRIUM", "boundary_z", bz.tolist())
    fyo.put(doc, "EQUILIBRIUM", "b0", 5.0)
    fyo.put(doc, "EQUILIBRIUM", "r0", 3.0)
    fyo.put(doc, "EQUILIBRIUM", "ip", 1.2e6)
    #: 梯子：体积与压强，同一条 ψ_norm 上
    psin = np.linspace(0.0, 1.0, 33)
    volume = 30.0 * psin ** 1.5 + 1e-3
    fyo.put(doc, "LADDER", "psin", psin.tolist())
    fyo.put(doc, "LADDER", "volume", volume.tolist())
    fyo.put(doc, "LADDER", "vprime", (45.0 * np.sqrt(psin) + 1e-3).tolist())
    return doc


def profiles_doc(*, psin=None, ne0=8e19, te0=9e3, ti0=8e3) -> dict:
    psin = np.linspace(0.0, 1.0, 33) if psin is None else np.asarray(psin, float)
    ne = ne0 * (1 - 0.8 * psin)
    te = te0 * (1 - 0.9 * psin) + 50.0
    ti = ti0 * (1 - 0.9 * psin) + 50.0
    doc = {"@context": {}, "@id": "test/core_profiles", "@type": "fyo:core_profiles"}
    fyo.put(doc, "CORE_PROFILES", "psin", psin.tolist())
    fyo.put(doc, "CORE_PROFILES", "rho_norm", np.sqrt(psin).tolist())
    fyo.put(doc, "CORE_PROFILES", "ne", ne.tolist())
    fyo.put(doc, "CORE_PROFILES", "ni", ne.tolist())
    fyo.put(doc, "CORE_PROFILES", "te", te.tolist())
    fyo.put(doc, "CORE_PROFILES", "ti", ti.tolist())
    fyo.put(doc, "CORE_PROFILES", "q", (1.1 + 3.0 * psin).tolist())
    return doc


def bundle(*, perturb: float = 0.0, with_pressure: bool = True, pressure_scale: float = 1.0):
    """平衡 + 剖面，压强按动理压强填（口径一致，`pressure-consistency` 应当过）。"""
    eq = equilibrium_doc(perturb=perturb)
    cp = profiles_doc()
    if with_pressure:
        psin = np.asarray(fyo.get(cp, "CORE_PROFILES", "psin"), float)
        ne = np.asarray(fyo.get(cp, "CORE_PROFILES", "ne"), float)
        te = np.asarray(fyo.get(cp, "CORE_PROFILES", "te"), float)
        ti = np.asarray(fyo.get(cp, "CORE_PROFILES", "ti"), float)
        p = pressure_scale * E * (ne * te + ne * ti)
        assert np.allclose(psin, np.asarray(fyo.get(eq, "LADDER", "psin"), float))
        fyo.put(eq, "EQUILIBRIUM", "pressure", p.tolist())
    return {"equilibrium": eq, "core_profiles": cp}


def summary_doc(**over) -> dict:
    """一份自洽的 `fyo:summary`：W/τ_E + dW/dt = P_ohm + P_aux + P_alpha − P_rad。"""
    t = np.linspace(0.0, 4.0, 9)
    w = 1.5e8 + 0.0 * t
    p_ohm, p_aux, p_alpha, p_rad = 1e6 + 0 * t, 3.0e7 + 0 * t, 5.0e6 + 0 * t, 4.0e6 + 0 * t
    dw = 0.0 * t
    p_heat = p_ohm + p_aux + p_alpha - p_rad
    tau = w / (p_heat - dw)
    doc = {"@context": {}, "@id": "test/summary", "@type": "fyo:summary"}
    put = {"time": t, "w_th": w, "dw_dt": dw, "tau_e": tau, "p_ohm": p_ohm, "p_aux": p_aux,
           "p_alpha": p_alpha, "p_rad": p_rad, "ip": 1.2e6 + 0 * t,
           "q_axis": 1.1 + 0 * t, "q95": 4.1 + 0 * t, "beta_n": 1.8 + 0 * t,
           "steady_change": 0.002 + 0 * t}
    put.update({k: np.asarray(v, float) if np.ndim(v) else v * np.ones_like(t)
                for k, v in over.items()})
    for k, v in put.items():
        fyo.put(doc, "SUMMARY", k, np.asarray(v, float).tolist())
    return doc


# --------------------------------------------------------------------------- #
# 定律
# --------------------------------------------------------------------------- #
def test_the_exact_solution_satisfies_grad_shafranov_and_a_perturbed_one_does_not():
    ok = ph.evaluate(bundle(), only=["grad-shafranov"])[0]
    assert ok["state"] == ph.PASS, ok
    #: 精确解的残差只剩差分截断误差 —— 与 h² 同量级，远在带内
    assert ok["measured"] < 5e-3, ok["detail"]
    assert ok["extra"]["points"] > 200

    bad = ph.evaluate(bundle(perturb=0.02), only=["grad-shafranov"])[0]
    assert bad["state"] == ph.FAIL, bad
    assert bad["measured"] > 10 * ok["measured"]


def test_a_flipped_sign_convention_is_a_caveat_not_a_false_failure():
    b = bundle()
    eq = b["equilibrium"]
    #: 另一套 COCOS：源函数整体反号 —— 残差落在另一支上
    fyo.put(eq, "EQUILIBRIUM", "dpressure_dpsi", [-P_PRIME] * 33)
    fyo.put(eq, "EQUILIBRIUM", "f_df_dpsi", [-FF_PRIME] * 33)
    r = ph.evaluate(b, only=["grad-shafranov"])[0]
    assert r["state"] == ph.PASS
    assert any("COCOS" in c for c in r["caveat"]), r


def test_missing_two_dimensional_psi_is_unevaluated_by_name_not_a_pass():
    b = bundle()
    del b["equilibrium"]["time_slice"][0]["profiles_2d"]
    r = ph.evaluate(b, only=["grad-shafranov"])[0]
    assert r["state"] == ph.UNEVALUATED
    assert r["missing"], r
    assert "评不了" in r["detail"]


def test_negative_temperature_and_density_fail_and_nan_is_caught():
    b = bundle()
    good = {r["check"]: r for r in ph.evaluate(b, only=["positive-temperature",
                                                        "positive-density", "finite"])}
    assert {v["state"] for v in good.values()} == {ph.PASS}

    cold = bundle()
    te = list(fyo.get(cold["core_profiles"], "CORE_PROFILES", "te"))
    te[-1] = -3.0
    fyo.put(cold["core_profiles"], "CORE_PROFILES", "te", te)
    r = ph.evaluate(cold, only=["positive-temperature"])[0]
    assert r["state"] == ph.FAIL and r["measured"] == -3.0

    nan = bundle()
    ne = list(fyo.get(nan["core_profiles"], "CORE_PROFILES", "ne"))
    ne[3] = float("nan")
    fyo.put(nan["core_profiles"], "CORE_PROFILES", "ne", ne)
    r = ph.evaluate(nan, only=["finite"])[0]
    assert r["state"] == ph.FAIL and r["measured"] == 1.0
    assert "core_profiles" in r["detail"]


# --------------------------------------------------------------------------- #
# 定义
# --------------------------------------------------------------------------- #
def test_psi_endpoints_and_grid_monotonicity_are_definitions():
    rs = {r["check"]: r for r in ph.evaluate(bundle(), only=["psi-endpoints", "grid-monotone",
                                                             "volume-monotone", "boundary-closed"])}
    assert {r["state"] for r in rs.values()} == {ph.PASS}, rs

    off = bundle()
    fyo.put(off["equilibrium"], "EQUILIBRIUM", "psi_axis",
            fyo.get(off["equilibrium"], "EQUILIBRIUM", "psi_axis") + 0.05)
    assert ph.evaluate(off, only=["psi-endpoints"])[0]["state"] == ph.FAIL

    back = bundle()
    x = list(fyo.get(back["core_profiles"], "CORE_PROFILES", "rho_norm"))
    x[5], x[6] = x[6], x[5]
    fyo.put(back["core_profiles"], "CORE_PROFILES", "rho_norm", x)
    r = ph.evaluate(back, only=["grid-monotone"])[0]
    assert r["state"] == ph.FAIL and "rho_norm" in r["detail"]


def test_an_open_boundary_and_one_outside_the_limiter_are_caught():
    b = bundle()
    eq = b["equilibrium"]
    fyo.put(eq, "EQUILIBRIUM", "limiter_r", [2.1, 3.9, 3.9, 2.1, 2.1])
    fyo.put(eq, "EQUILIBRIUM", "limiter_z", [-0.9, -0.9, 0.9, 0.9, -0.9])
    assert ph.evaluate(b, only=["boundary-closed"])[0]["state"] == ph.PASS

    tight = bundle()
    fyo.put(tight["equilibrium"], "EQUILIBRIUM", "limiter_r", [2.6, 3.2, 3.2, 2.6, 2.6])
    fyo.put(tight["equilibrium"], "EQUILIBRIUM", "limiter_z", [-0.4, -0.4, 0.4, 0.4, -0.4])
    r = ph.evaluate(tight, only=["boundary-closed"])[0]
    assert r["state"] == ph.FAIL and "越出限制器" in r["detail"]

    #: 边界正落在限制器上（外接矩形）不是越界 —— 射线法对这种点是随机的，
    #: 所以判据是「越出多于 tol × 小半径」
    flush = bundle()
    br = np.asarray(fyo.get(flush["equilibrium"], "EQUILIBRIUM", "boundary_r"), float)
    bz = np.asarray(fyo.get(flush["equilibrium"], "EQUILIBRIUM", "boundary_z"), float)
    fyo.put(flush["equilibrium"], "EQUILIBRIUM", "limiter_r",
            [br.min(), br.max(), br.max(), br.min(), br.min()])
    fyo.put(flush["equilibrium"], "EQUILIBRIUM", "limiter_z",
            [bz.min(), bz.min(), bz.max(), bz.max(), bz.min()])
    assert ph.evaluate(flush, only=["boundary-closed"])[0]["state"] == ph.PASS

    open_ = bundle()
    brl = list(fyo.get(open_["equilibrium"], "EQUILIBRIUM", "boundary_r"))
    brl[-1] = brl[0] + 0.5
    fyo.put(open_["equilibrium"], "EQUILIBRIUM", "boundary_r", brl)
    r = ph.evaluate(open_, only=["boundary-closed"])[0]
    assert r["state"] == ph.FAIL and r["measured"] > 10, r
    #: 闭合按**采样步**量：首末差一个采样步之内的等值线是闭合的
    #: （g-file 重不重复首点是写文件那边的习惯）
    sparse = bundle()
    br2 = list(fyo.get(sparse["equilibrium"], "EQUILIBRIUM", "boundary_r"))
    bz2 = list(fyo.get(sparse["equilibrium"], "EQUILIBRIUM", "boundary_z"))
    fyo.put(sparse["equilibrium"], "EQUILIBRIUM", "boundary_r", br2[:-1])
    fyo.put(sparse["equilibrium"], "EQUILIBRIUM", "boundary_z", bz2[:-1])
    assert ph.evaluate(sparse, only=["boundary-closed"])[0]["state"] == ph.PASS


def test_pressure_consistency_measures_the_kinetic_pressure_gap():
    same = ph.evaluate(bundle(), only=["pressure-consistency"])[0]
    assert same["state"] == ph.PASS and same["measured"] < 1e-12

    off = ph.evaluate(bundle(pressure_scale=1.4), only=["pressure-consistency"])[0]
    assert off["state"] == ph.FAIL
    assert 0.28 < off["measured"] < 0.30, off


def test_energy_balance_reads_the_stated_convention():
    b = bundle()
    b["summary"] = summary_doc()
    r = ph.evaluate(b, only=["energy-balance"])[0]
    assert r["state"] == ph.PASS and r["measured"] < 1e-12
    assert any("P_heat = p_ohm p_aux p_alpha -p_rad" in c for c in r["caveat"]), r

    #: τ_E 少记了两成 —— 定义式立刻不成立
    bad = bundle()
    s = summary_doc()
    tau = np.asarray(fyo.get(s, "SUMMARY", "tau_e"), float) * 0.8
    fyo.put(s, "SUMMARY", "tau_e", tau.tolist())
    bad["summary"] = s
    r2 = ph.evaluate(bad, only=["energy-balance"])[0]
    assert r2["state"] == ph.FAIL and 0.2 < r2["measured"] < 0.3

    #: 口径可由算例声明：只算欧姆 + 辅助时，同一份记录的残差另算
    r3 = ph.evaluate(b, only=["energy-balance"],
                     options={"energy-balance": {"p_heat_terms": ["p_ohm", "p_aux"]}})[0]
    assert r3["measured"] > 0.01
    assert any("p_ohm p_aux" in c for c in r3["caveat"])


def test_greenwald_and_beta_definitions_are_recomputed_not_trusted():
    b = bundle()
    eq, cp = b["equilibrium"], b["core_profiles"]
    ne = np.asarray(fyo.get(cp, "CORE_PROFILES", "ne"), float)
    vol = np.asarray(fyo.get(eq, "LADDER", "volume"), float)
    n_bar = float(np.trapezoid(ne, vol) / (vol[-1] - vol[0])) if hasattr(np, "trapezoid") \
        else float(np.trapz(ne, vol) / (vol[-1] - vol[0]))
    a = 0.7
    n_g = (1.2 / (math.pi * a ** 2)) * 1e20
    p = np.asarray(fyo.get(eq, "EQUILIBRIUM", "pressure"), float)
    p_avg = float(np.trapezoid(p, vol) / (vol[-1] - vol[0])) if hasattr(np, "trapezoid") \
        else float(np.trapz(p, vol) / (vol[-1] - vol[0]))
    beta_n = 2 * MU0 * p_avg / 5.0 ** 2 * 100.0 * a * 5.0 / 1.2

    b["summary"] = summary_doc(greenwald=n_bar / n_g, beta_n=beta_n)
    rs = {r["check"]: r for r in ph.evaluate(
        b, only=["greenwald-definition", "beta-normalized-definition"])}
    assert rs["greenwald-definition"]["state"] == ph.PASS, rs["greenwald-definition"]
    assert rs["beta-normalized-definition"]["state"] == ph.PASS, rs["beta-normalized-definition"]

    b2 = bundle()
    b2["summary"] = summary_doc(greenwald=2.5 * n_bar / n_g, beta_n=beta_n)
    r = ph.evaluate(b2, only=["greenwald-definition"])[0]
    assert r["state"] == ph.FAIL and r["measured"] > 0.5


# --------------------------------------------------------------------------- #
# 期望
# --------------------------------------------------------------------------- #
def test_declared_bounds_and_steady_state_are_the_cases_to_declare():
    b = bundle()
    b["summary"] = summary_doc()
    silent = ph.evaluate(b, only=["declared-bounds", "steady-state"])
    assert {r["state"] for r in silent} == {ph.UNEVALUATED}, silent
    assert "没有声明" in silent[0]["detail"]

    opts = {"declared-bounds": {"bounds": [{"quantity": "SUMMARY/beta_n", "max": 4.0},
                                           {"quantity": "SUMMARY/q95", "min": 3.0},
                                           {"quantity": "SUMMARY/nope", "max": 1.0}]},
            "steady-state": {"tolerance": 0.01}}
    rs = {r["check"]: r for r in ph.evaluate(b, only=["declared-bounds", "steady-state"],
                                             options=opts)}
    assert rs["declared-bounds"]["state"] == ph.PASS
    assert rs["declared-bounds"]["missing"] == ["SUMMARY/nope"]
    assert rs["steady-state"]["state"] == ph.PASS

    opts["declared-bounds"]["bounds"][0]["max"] = 1.0
    r = ph.evaluate(b, only=["declared-bounds"], options=opts)[0]
    assert r["state"] == ph.FAIL and "越界" in r["detail"]


def test_reversed_shear_is_conditional_not_a_failure():
    b = bundle()
    b["summary"] = summary_doc(q_axis=4.5, q95=3.0)
    r = ph.evaluate(b, only=["q-order"])[0]
    assert r["state"] == ph.CONDITIONAL and "反剪切" in r["detail"]


# --------------------------------------------------------------------------- #
# 册子本身
# --------------------------------------------------------------------------- #
def test_every_check_declares_what_it_reads_and_what_it_assumes():
    for cid, c in ph.CHECKS.items():
        assert c.kind in ("law", "definition", "expectation"), cid
        assert c.basis in ("machine_precision", "measured_band", "reference_stated"), cid
        assert c.formula and c.title, cid
        assert callable(c.fn), cid
        #: 期望类不带默认容差 —— 判据得由算例声明，否则「过」是无意义的
        if c.kind == "expectation":
            assert c.tolerance is None, cid
        for block, slot in c.reads:
            assert slot in fyo.TABLES[block]["slots"], f"{cid} reads {block}/{slot}"
    #: 缺省跑的就是定律与定义
    assert set(ph.DEFAULT_CHECKS) == set(ph.check_ids("law")) | set(ph.check_ids("definition"))


def test_an_empty_bundle_is_all_unevaluated_and_names_what_is_missing():
    rs = ph.evaluate({}, only=list(ph.CHECKS))
    assert {r["state"] for r in rs} == {ph.UNEVALUATED}
    s = ph.summarize(rs)
    assert s["overall"] == ph.UNEVALUATED and s["evaluated"] == 0
    assert all(r.get("missing") or r["detail"] for r in rs)


def test_plan_says_in_advance_which_checks_this_product_can_answer():
    rows = {r["check"]: r for r in ph.plan(bundle())}
    assert rows["grad-shafranov"]["evaluable"] is True
    assert rows["energy-balance"]["evaluable"] is False
    assert "SUMMARY/w_th" in rows["energy-balance"]["missing"]


def test_summarize_is_worst_first_and_counts_every_state():
    rs = [{"state": ph.PASS}, {"state": ph.CONDITIONAL}, {"state": ph.UNEVALUATED}]
    s = ph.summarize(rs)
    assert s == {"overall": ph.CONDITIONAL,
                 "counts": {ph.PASS: 1, ph.CONDITIONAL: 1, ph.FAIL: 0, ph.UNEVALUATED: 1},
                 "evaluated": 2, "total": 3}
    assert ph.summarize([{"state": ph.FAIL}, {"state": ph.PASS}])["overall"] == ph.FAIL


def test_a_check_that_raises_is_one_row_not_a_dead_batch():
    boom = ph.Check("boom", "law", "t", "f", (), 0.0, "machine_precision", (),
                    lambda r, o: (_ for _ in ()).throw(ValueError("nope")))
    ph.CHECKS["boom"] = boom
    try:
        rs = ph.evaluate(bundle(), only=["boom", "finite"])
    finally:
        del ph.CHECKS["boom"]
    assert rs[0]["state"] == ph.UNEVALUATED and "ValueError" in rs[0]["detail"]
    assert rs[1]["state"] == ph.PASS
