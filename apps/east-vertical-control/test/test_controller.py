"""控制器那一半的门：全用合成对象，不要内核、不要数据。

被控对象来自内核（`code/vstab`），它的门在内核仓与本仓基准册里；这里只守本示例自己加的
东西——Padé 时延、闭环矩阵的拼法、模态响应、矩阵指数、P 律下限与时延上限。每一条都对一个
闭式解或另一种算法。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vs_control", HERE / "vs_control.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)


def scalar_plant(gamma: float, b: float = 1.0) -> dict:
    """一阶不稳定对象 ẋ = γ x + b v、ξ = x——竖直模的最小模型。"""
    return {"A": np.array([[gamma]]), "B": np.array([[b, 0.0]]), "c": np.array([1.0]), "n_passive": 0}


def test_pade_matches_the_delay_on_the_imaginary_axis():
    """[4/4] Padé 在 ωT ≤ 3 以内与 e^{−iωT} 相差不到 1e-3（模为 1、相位对上）。"""
    T = 0.02
    Ap, Bp, Cp, Dp = vs.pade(T, 4)
    for wT in (0.1, 0.5, 1.0, 2.0, 3.0):
        s = 1j * wT / T
        G = Cp @ np.linalg.solve(s * np.eye(4) - Ap, Bp) + Dp
        assert abs(G - np.exp(-s * T)) < 1e-3, (wT, G, np.exp(-s * T))


def test_pade_has_unit_dc_gain_and_is_allpass():
    Ap, Bp, Cp, Dp = vs.pade(0.05, 4)
    assert abs((Cp @ np.linalg.solve(-Ap, Bp)) + Dp - 1.0) < 1e-12
    assert np.all(np.linalg.eigvals(Ap).real < 0.0)
    assert vs.pade(0.0) is None


def test_expm_agrees_with_the_eigen_decomposition():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(6, 6)) * 3.0
    w, V = np.linalg.eig(A)
    ref = np.real(V @ np.diag(np.exp(w)) @ np.linalg.inv(V))
    assert np.allclose(vs.expm(A), ref, rtol=1e-9, atol=1e-9)


def test_p_control_moves_the_pole_to_gamma_minus_k():
    """无时延、执行器与微分滤波都极快时，P 律的闭环主极点就是 γ − b K_p。"""
    pl = scalar_plant(gamma=10.0, b=2.0)
    b = pl["B"][:, 0]
    Acl, _, _ = vs.closed_loop(pl, b, kp=15.0, kd=0.0, tau_a=1e-7, tau_d=1e-7, delay=0.0)
    w = np.linalg.eigvals(Acl)
    main = w[np.argmin(np.abs(w - (10.0 - 2.0 * 15.0)))]
    assert abs(main.real - (10.0 - 30.0)) < 1e-3, w


def test_the_p_law_threshold_is_gamma_over_b():
    """P 律下限 K_p,min = γ / b。"""
    pl = scalar_plant(gamma=10.0, b=2.0)
    kp = vs.kp_min(pl, pl["B"][:, 0], tau_a=1e-7, tau_d=1e-7)
    assert kp == pytest.approx(5.0, rel=1e-4)


def test_orientation_picks_the_restoring_polarity():
    """反对称对的两路反号：只有一种极性让 K_p > 0 是恢复力。"""
    pl = {"A": np.array([[10.0]]), "B": np.array([[-1.0, 1.0]]), "c": np.array([1.0]), "n_passive": 0}
    b, kp = vs.orientation(pl, tau_a=1e-7, tau_d=1e-7)
    assert b[0] > 0.0 and kp == pytest.approx(5.0, rel=1e-4)


@pytest.mark.parametrize("gT,stabilisable", [(0.5, True), (0.8, True), (1.3, False), (2.0, False)])
def test_a_p_law_can_hold_the_mode_only_while_gamma_t_is_below_one(gT, stabilisable):
    """经典结论：ẋ = γ x − K x(t − T) 存在稳定的 K 当且仅当 γT < 1。

    ★这正是「执行器必须快于 1/γ」的定量说法；用 Padé [4/4] 近似时延，所以只在离 1 够远的地方判。
    """
    gamma = 10.0
    pl = scalar_plant(gamma)
    b = pl["B"][:, 0]
    T = gT / gamma
    ok = any(vs.max_re(vs.closed_loop(pl, b, kp, 0.0, tau_a=1e-7, tau_d=1e-7, delay=T)[0]) < 0.0
             for kp in np.linspace(1.0001 * gamma, 6.0 * gamma, 400))
    assert ok is stabilisable


def test_the_modal_response_equals_the_time_march():
    """ξ(t) 的模态叠加与 e^{A dt} 逐步推进对上——到**条件数允许的**精度。

    ★这里特征向量矩阵的 cond(V) ≈ 8e11（τ_a、τ_d 与 Padé 的极点挤在一起，接近亏损），模态叠加
    因此只到 ~1e-5 的相对精度。这正是增益图改用逐步推进（``march``）的原因；本条留作两种算法的
    交叉核对，容差按条件数给。
    """
    pl = {"A": np.array([[8.0, 2.0], [0.5, -40.0]]), "B": np.array([[1.0, 0.0], [0.3, 0.0]]),
          "c": np.array([1.0, 0.2]), "n_passive": 1}
    b = pl["B"][:, 0]
    Acl, rx, ru = vs.closed_loop(pl, b, kp=30.0, kd=0.5, tau_a=1e-3, tau_d=1e-3, delay=0.01)
    x0 = vs.initial_state(pl, Acl.shape[0], 0.01)
    t = np.linspace(0.0, 0.2, 201)
    _, (xi_modal, u_modal) = vs.modal_response(Acl, (rx, ru), x0, t)
    Phi, x = vs.expm(Acl * (t[1] - t[0])), x0.copy()
    xi_march = []
    for _ in t:
        xi_march.append(rx @ x); x = Phi @ x
    assert np.max(np.abs(xi_modal - np.asarray(xi_march))) < 1e-4 * np.max(np.abs(xi_march))
    xi_m2, _ = vs.march(Acl, (rx, ru), x0, t)
    assert np.allclose(xi_m2, xi_march, rtol=1e-12, atol=0.0)


def test_settle_time_reads_the_last_excursion():
    t = np.linspace(0.0, 1.0, 101)
    y = np.exp(-10.0 * t)
    assert vs.settle_time(t, y, 1.0, tol=0.02) == pytest.approx(math.log(50.0) / 10.0, abs=0.011)
    assert vs.settle_time(t, np.ones_like(t), 1.0) == pytest.approx(1.0)


def test_read_ccbrsp_finds_the_coil_block(tmp_path):
    """a-file 的线圈段：「nsilop magpri nfcoil nesum」之后先跳过环与探针。"""
    f = tmp_path / "a1.00100"
    f.write_text(" 23-Jan-2026  01/01/99\n 1 1\n*  100.000  1  2  3  4\n 1.0 2.0\n 2 3 4 0\n"
                 " 1.0E+00 2.0E+00 3.0E+00 4.0E+00 5.0E+00\n 6.0E+00 7.0E+00 8.0E+00 9.9E+00\n")
    assert vs.read_ccbrsp(f) == [6.0, 7.0, 8.0, 9.9]
