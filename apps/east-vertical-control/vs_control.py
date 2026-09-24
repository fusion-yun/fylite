#!/usr/bin/env python3
"""EAST 竖直不稳定性与竖直位置控制 —— 被控对象来自内核，控制器与闭环仿真在这里。

一次 ``run``：

1. **被控对象（内核）**：``code/vstab`` 在 EAST 装置卡与一份平衡上给出刚性位移模型的电路矩阵——
   互感 M、电阻 R、耦合梯度 G = ∂M/∂Z、外场刚度 k、理想阈值 k_ideal、位移行 C_ξ。
   取 ``circuit: full`` 让 IC 快控线圈进入回路，再把 PF 通道删掉（PF 由电源保持电流，
   对小信号动态没有贡献），留下「被动结构 + IC」；秩一修正 M* = M − (I_p²/k) G Gᵀ 由
   :func:`fylite.scenario.control.lti.linear_model` 做。
2. **控制器（本示例）**：IC1 / IC2 反对称供电 ``v_IC1 = +v、v_IC2 = −v``；PD 律
   ``u = −K_p ξ − K_d ξ̇``（微分经一阶滤波 τ_d），执行器一阶滞后 τ_a（``v̇ = (u − v)/τ_a``）。
3. **扫描与仿真（本示例，纯线性代数）**：闭环极点随 (K_p, K_d, τ_a) 的分布、可稳定的执行器
   滞后上限、竖直位移扰动（VDE 起始）的开环 / 闭环时间响应。
4. **壁的影响（内核）**：同一扇门按 ``vessel_scale``（壁到磁轴的距离）与 ``eta_scale``（壁电阻率）
   各扫一次开环增长率与判读档位。

输出一份结果 JSON，``vs_control.html`` 读它作图。见 README。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

APP = "east-vertical-control"
VERSION = "1"
#: 与入册基准 `mhd-vertical-freegsnke-east137985` 同一套离散（`tools/benchmark-wall-vstab.py` 的 VS_DISC）
DISC = {"coarsen": 1.0, "nu": 8.0, "nv": 8.0}
PASSIVE = "inner_shell,outer_shell,passive_plates"
GROUPS = ("inner_shell", "outer_shell", "passive_plates")
REGIMES = {0: "stable", 1: "resistive-wall", 2: "ideal-unstable"}

_FNUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?")


# --------------------------------------------------------------------------- #
# 输入
# --------------------------------------------------------------------------- #
def read_ccbrsp(path) -> list[float]:
    """A-EQDSK 里 EFIT 拟合的外加线圈电流 ``ccbrsp``（BRSP 次序，安匝）。

    找「nsilop magpri nfcoil nesum」那一行（四个整数），其后 nsilop + magpri 个数是环与探针，
    再 nfcoil 个是线圈——与 ``apps/east-free-boundary-evolution`` 的读法同一条规则。
    （``fylite.io.geqdsk.read_afile`` 读不了这一炮的表头，故自带。）
    """
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    for j, ln in enumerate(lines):
        w = ln.split()
        if len(w) == 4 and all(re.fullmatch(r"\d+", x) for x in w):
            nsilop, magpri, nfcoil = int(w[0]), int(w[1]), int(w[2])
            rest = [float(x.replace("D", "E").replace("d", "e")) for x in _FNUM.findall("\n".join(lines[j + 1:]))]
            return rest[nsilop + magpri:nsilop + magpri + nfcoil]
    raise ValueError(f"{path}: 找不到「nsilop magpri nfcoil nesum」那一行，读不出 ccbrsp")


def load_inputs(data_dir: Path, shot: int, gname: str | None, aname: str | None):
    from fylite import device, fyo
    from fylite.io import geqdsk
    gpath = data_dir / gname if gname else next(iter(sorted(data_dir.glob(f"g{shot}.*"))), None)
    apath = data_dir / aname if aname else next(iter(sorted(data_dir.glob(f"a{shot}.*"))), None)
    if gpath is None or not gpath.is_file():
        raise SystemExit(f"{data_dir} 里没有 g{shot}.* —— 用 --gfile 指定")
    if apath is None or not apath.is_file():
        raise SystemExit(f"{data_dir} 里没有 a{shot}.* —— 用 --afile 指定（要它的 ccbrsp 作 PF 通道安匝）")
    dev = device.document(shot=shot, measurement_chain="east")
    g = geqdsk.read_geqdsk(str(gpath))
    at = np.asarray(read_ccbrsp(apath), float)[:12]
    if at.size != 12:
        raise SystemExit(f"{apath}: ccbrsp 只有 {at.size} 个数，要 12 个 PF 通道")
    return dev, g, fyo.as_equilibrium(g), at, gpath, apath


# --------------------------------------------------------------------------- #
# 内核：被控对象
# --------------------------------------------------------------------------- #
def vstab(dev, eq, at, **settings) -> dict:
    """一次 ``code/vstab``：返回 facts · fields · dims · notes（都是门给的）。"""
    from fylite.io import fydoc
    rec = fydoc.complete("code/vstab", {"settings": {**DISC, **settings}, "inputs": {
        "device": dev, "equilibrium": eq, "discharge": {"fylite:channel_aturns": np.asarray(at, float)}}})
    return {"facts": {k: float(v["value"]) for k, v in rec["facts"].items()},
            "fields": rec["fields"], "dims": rec["dims"], "notes": list(rec.get("notes") or [])}


def plant(dev, eq, at, *, eta_ic: float | None, log=print) -> dict:
    """被动结构 + IC 的刚性竖直对象（PF 电流保持），以及一条接线判据。

    判据：同一份 ``circuit: full`` 矩阵再删掉 IC、只留被动结构，必须落回
    ``circuit: passive`` 那扇门自己给的 γ——不相等就是成员次序或删法错了。
    """
    from fylite.scenario.control import lti
    s = {"circuit": "full", "passive": PASSIVE, "ic": 1.0}
    if eta_ic is not None:
        s["eta_coil"] = float(eta_ic)
    t0 = time.time()
    full = vstab(dev, eq, at, **s)
    log(f"[plant] code/vstab full+IC  {time.time() - t0:.1f} s")
    f, F = full["facts"], full["fields"]
    n = int(full["dims"]["n"])
    arr = lambda k: np.asarray(F[k]["data"], float)  # noqa: E731
    M, R, G, c_xi = arr("m").reshape(n, n), arr("r"), arr("g"), arr("c_xi")
    ip, k, n_ch, n_ic = f["ip"], f["k"], int(f["n_channels"]), int(f["n_fast_coils"])
    n_pas = n - n_ch - n_ic
    if n_ic != 2:
        raise SystemExit(f"门只给出 {n_ic} 路快控线圈（要 IC1、IC2 两路）：装置卡里 function = b_field_fb 的线圈不对")
    #: 成员次序（case.rs::vstab_case）：PF 通道 · 被动 · 快控线圈
    P = np.arange(n_ch, n_ch + n_pas)
    keep = np.arange(n_ch, n)
    t0 = time.time()
    door_passive = vstab(dev, eq, at, circuit="passive", passive=PASSIVE, ic=0.0)
    log(f"[plant] code/vstab passive  {time.time() - t0:.1f} s")
    m_p = lti.linear_model(M[np.ix_(P, P)], R[P], plasma_response="rigid", ip=ip, G=G[P], k=k)
    g_door = door_passive["facts"]["gamma"]
    check = {"gamma_reduced": m_p.gamma, "gamma_door_passive": g_door,
             "rel_diff": abs(m_p.gamma / g_door - 1.0) if g_door else float("nan")}
    if not check["rel_diff"] < 1e-6:
        raise SystemExit(f"接线判据不成立：删掉 PF 与 IC 后 γ = {m_p.gamma:.6g}，门的 passive 档给 {g_door:.6g}")
    B_act = np.zeros((len(keep), 2))
    B_act[-2:, :] = np.eye(2)
    m = lti.linear_model(M[np.ix_(keep, keep)], R[keep], plasma_response="rigid", ip=ip, G=G[keep], k=k, B_act=B_act)
    c = c_xi[keep]
    #: ★c_xi 只依赖 G 与 k（ξ = −(I_p/k) Gᵀ I），截取是精确的；这里对一遍
    c_rebuilt = -(ip / k) * G[keep]
    if not np.allclose(c, c_rebuilt, rtol=1e-9, atol=0.0):
        raise SystemExit("门的 c_xi 与 −(I_p/k)·G 对不上：位移行的约定变了")
    return {"A": m.A, "B": m.B, "c": c, "gamma": m.gamma, "ip": ip, "k": k, "k_ideal": f["k_ideal"],
            "margin": f["margin"], "regime_code": int(f["regime_code"]), "n_passive": n_pas, "n_ic": n_ic,
            "R_ic": R[-2:].tolist(), "check": check,
            "door_passive": {k2: door_passive["facts"][k2] for k2 in ("gamma", "k", "k_ideal", "margin", "regime_code")},
            "door_full": {k2: f[k2] for k2 in ("gamma", "k", "k_ideal", "margin", "regime_code")},
            "notes": full["notes"] + [n2 for n2 in door_passive["notes"] if n2 not in full["notes"]],
            "plasma_filaments": {"r": arr("filament_r").tolist(), "z": arr("filament_z").tolist(),
                                 "current": arr("filament_current").tolist()},
            "eta_ic": eta_ic}


# --------------------------------------------------------------------------- #
# 控制器与闭环（本示例；只做线性代数）
# --------------------------------------------------------------------------- #
#: 状态 x = [I (n) · d（微分滤波）· z（Padé 时延，n_p）· v（执行器输出）]
#:
#:     İ = A I + b v,              ξ = cᵀ I
#:     ḋ = (ξ − d)/τ_d,            ξ̇_f = (ξ − d)/τ_d
#:     u = −K_p ξ − K_d ξ̇_f          （控制律，代数）
#:     ż = A_p z + B_p u,  w = C_p z + D_p u     （回路时延 e^{−sT} 的 Padé [n/n]）
#:     v̇ = (w − v)/τ_a              （电源一阶滞后）
PADE_ORDER = 4


def pade(T: float, n: int = PADE_ORDER):
    """e^{−sT} 的 Padé [n/n] 状态空间 (A_p, B_p, C_p, D_p)；T = 0 返回 None（直通）。"""
    if T <= 0.0:
        return None
    c = [math.factorial(2 * n - k) * math.factorial(n) / (math.factorial(2 * n) * math.factorial(k) * math.factorial(n - k))
         for k in range(n + 1)]
    den = [c[k] * T ** k for k in range(n + 1)]                  #: s^k 的系数（升幂）
    num = [((-1) ** k) * c[k] * T ** k for k in range(n + 1)]
    lead = den[n]
    den = [x / lead for x in den]
    num = [x / lead for x in num]
    Dp = num[n]                                                 #: 双正则：直通项 = (−1)^n
    r = [num[k] - Dp * den[k] for k in range(n)]                #: 严格正则部分的分子（升幂）
    Ap = np.zeros((n, n))
    Ap[:-1, 1:] = np.eye(n - 1)
    Ap[-1, :] = [-den[k] for k in range(n)]
    Bp = np.zeros(n); Bp[-1] = 1.0
    Cp = np.asarray(r, float)
    return Ap, Bp, Cp, float(Dp)


def closed_loop(pl: dict, b: np.ndarray, kp: float, kd: float, *, tau_a: float, tau_d: float,
                delay: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """闭环矩阵，以及 ξ 与 u 两行输出（x ↦ ξ、x ↦ u）。"""
    A, c = pl["A"], pl["c"]
    n = A.shape[0]
    P = pade(delay)
    npd = 0 if P is None else P[0].shape[0]
    N = n + 1 + npd + 1
    iD, iZ, iV = n, n + 1, n + 1 + npd
    #: u 的行：u = −K_p ξ − K_d (ξ − d)/τ_d
    row_u = np.zeros(N)
    row_u[:n] = -kp * c - (kd / tau_d) * c
    row_u[iD] = kd / tau_d
    row_xi = np.zeros(N); row_xi[:n] = c
    Acl = np.zeros((N, N))
    Acl[:n, :n] = A
    Acl[:n, iV] = b
    Acl[iD, :n] = c / tau_d
    Acl[iD, iD] = -1.0 / tau_d
    if P is None:
        w_row = row_u
    else:
        Ap, Bp, Cp, Dp = P
        Acl[iZ:iZ + npd, iZ:iZ + npd] = Ap
        Acl[iZ:iZ + npd, :] += np.outer(Bp, row_u)
        w_row = Dp * row_u
        w_row = w_row.copy(); w_row[iZ:iZ + npd] += Cp
    Acl[iV, :] += w_row / tau_a
    Acl[iV, iV] += -1.0 / tau_a
    return Acl, row_xi, row_u


def initial_state(pl: dict, N: int, xi0: float) -> np.ndarray:
    """开环不稳定模的形状、ξ(0) = ξ0；滤波器取 ξ0（不给初始微分冲击），时延与执行器从 0 起。"""
    n = pl["A"].shape[0]
    x = np.zeros(N)
    x[:n] = unstable_mode(pl) * xi0
    x[n] = xi0
    return x


def modal_response(Acl, rows, x0, t):
    """y_r(t) = Re Σ_i (r V)_i (V⁻¹ x0)_i e^{λ_i t}：一次特征分解给出全部输出与全部时刻。"""
    w, V = np.linalg.eig(Acl)
    a = np.linalg.solve(V, x0.astype(complex))
    E = np.exp(np.outer(w, t))                                 #: (N, nt)
    return w, [np.real((r @ V * a) @ E) for r in rows]


def march(Acl, rows, x0, t):
    """等步长 t 上的精确离散推进：x_{k+1} = e^{A Δt} x_k，返回各输出行。"""
    Phi = expm(Acl * (t[1] - t[0]))
    x = x0.copy()
    ys = [np.empty(len(t)) for _ in rows]
    for kk in range(len(t)):
        for y, r in zip(ys, rows):
            y[kk] = r @ x
        x = Phi @ x
    return ys


def settle_time(t, y, y0, tol=0.02) -> float:
    """|y| 最后一次超过 tol·|y0| 的时刻；到窗口末都没落下来就是窗口长度。"""
    over = np.nonzero(np.abs(y) > tol * abs(y0))[0]
    if over.size == 0:
        return 0.0
    k = int(over[-1])
    return float(t[min(k + 1, len(t) - 1)])


def max_re(A: np.ndarray) -> float:
    return float(np.max(np.linalg.eigvals(A).real))


def orientation(pl: dict, *, tau_a: float, tau_d: float) -> tuple[np.ndarray, float]:
    """反对称对 b = B[:, IC1] − B[:, IC2] 的极性：取使 K_p > 0 为恢复力的那一侧。

    两种极性下各找 P 律（K_d = 0、无时延）能把最大实部压到 0 以下的最小 K_p，有解的那一侧即是。
    """
    b0 = pl["B"][:, 0] - pl["B"][:, 1]
    best = None
    for sgn in (+1.0, -1.0):
        kp = kp_min(pl, sgn * b0, tau_a=tau_a, tau_d=tau_d)
        if kp is not None and (best is None or kp < best[1]):
            best = (sgn, kp)
    if best is None:
        raise SystemExit("两种极性下 P 律都压不住这个模——IC 对竖直模没有控制力（几何或接线不对）")
    return best[0] * b0, best[1]


def kp_min(pl: dict, b: np.ndarray, *, tau_a: float, tau_d: float, lo=1e-3, hi=1e12) -> float | None:
    """P 律下使闭环最大实部 < 0 的最小 K_p [V/m]（对数二分）；找不到返回 None。"""
    f = lambda kp: max_re(closed_loop(pl, b, kp, 0.0, tau_a=tau_a, tau_d=tau_d)[0])  # noqa: E731
    grid = np.logspace(math.log10(lo), math.log10(hi), 49)
    vals = [f(x) for x in grid]
    idx = next((i for i, v in enumerate(vals) if v < 0.0), None)
    if idx is None:
        return None
    if idx == 0:
        return float(grid[0])
    a, z = math.log10(grid[idx - 1]), math.log10(grid[idx])
    for _ in range(40):
        m = 0.5 * (a + z)
        (z, a) = (m, a) if f(10 ** m) < 0.0 else (z, m)
    return float(10 ** z)


def gain_map(pl, b, kp_ref, gamma, *, delay, tau_a, tau_d, xi0, t_end, n_grid) -> dict:
    """(K_p, K_d) 网格：闭环最大实部、ξ 的 2 % 沉降时间、峰值电压 |u|。

    K_p 围绕 P 律下限取对数，K_d 以 K_p,min/γ 为尺。★「最大实部」判稳定，但**不拿它挑增益**：
    被动板的慢 L/R 模 IC 控制不到，它在稳定区里一直占着最大实部（一块平台）；挑增益看的是
    ξ 本身沉降多快、要多大电压。
    """
    kps = np.logspace(math.log10(kp_ref * 0.3), math.log10(kp_ref * 300.0), n_grid)
    kd_ref = kp_ref / max(gamma, 1e-9)
    kds = np.concatenate([[0.0], np.logspace(math.log10(kd_ref * 1e-4), math.log10(kd_ref * 10.0), n_grid - 1)])
    t = np.linspace(0.0, t_end, 400)
    mre = np.empty((n_grid, n_grid)); ts = np.full((n_grid, n_grid), np.nan); up = np.full((n_grid, n_grid), np.nan)
    for i, kd in enumerate(kds):
        for j, kp in enumerate(kps):
            Acl, rx, ru = closed_loop(pl, b, kp, kd, tau_a=tau_a, tau_d=tau_d, delay=delay)
            mre[i, j] = max_re(Acl)
            if mre[i, j] < 0.0:
                #: ★逐步推进而不是模态叠加：τ_a、τ_d 与 Padé 的极点挤在一起时特征向量矩阵近乎亏损
                #: （合成对象上 cond(V) ≈ 8e11），模态叠加会丢精度；e^{A dt} 不受这个影响
                xi, u = march(Acl, (rx, ru), initial_state(pl, Acl.shape[0], xi0), t)
                ts[i, j] = settle_time(t, xi, xi0)
                up[i, j] = float(np.max(np.abs(u)))
    stable = mre < 0.0
    best = None
    if stable.any():
        k = np.nanargmin(np.where(stable, ts, np.nan))
        i, j = np.unravel_index(k, ts.shape)
        #: ★最快点落在网格边上，说明「再加增益还会更快」——没有电压限幅时这张网格的最快点
        #: 只是网格的边，不是一个最优；如实标出来
        best = {"kp": float(kps[j]), "kd": float(kds[i]), "max_re": float(mre[i, j]),
                "settle_s": float(ts[i, j]), "u_peak_V": float(up[i, j]),
                "on_edge": bool(j in (0, n_grid - 1) or i == n_grid - 1)}
    nan2none = lambda a: [[None if not np.isfinite(v) else float(v) for v in row] for row in a]  # noqa: E731
    return {"delay": delay, "tau_a": tau_a, "kp": kps.tolist(), "kd": kds.tolist(),
            "max_re": mre.tolist(), "settle_s": nan2none(ts), "u_peak_V": nan2none(up),
            "best": best, "stable_fraction": float(np.mean(stable))}


def delay_sweep(pl, b, kp_ref, gamma, *, delays, tau_a, tau_d, xi0, t_end, n_grid) -> dict:
    """每个回路时延下网格上能否稳定、最快能多快；过零处插出可稳定的时延上限 T_crit。"""
    rows = []
    for T in delays:
        gm = gain_map(pl, b, kp_ref, gamma, delay=T, tau_a=tau_a, tau_d=tau_d, xi0=xi0, t_end=t_end, n_grid=n_grid)
        best_re = float(np.min(np.asarray(gm["max_re"])))
        rows.append({"delay": T, "best_max_re": best_re, "stable_fraction": gm["stable_fraction"],
                     "best": gm["best"]})
    crit = None
    for a_, z_ in zip(rows, rows[1:]):
        if a_["best_max_re"] < 0.0 <= z_["best_max_re"]:
            la, lz = math.log10(max(a_["delay"], 1e-12)), math.log10(z_["delay"])
            crit = 10 ** (la + (0.0 - a_["best_max_re"]) * (lz - la) / (z_["best_max_re"] - a_["best_max_re"]))
            break
    return {"rows": rows, "delay_crit": crit, "gamma_delay_crit": (gamma * crit) if crit else None}


def expm(A: np.ndarray) -> np.ndarray:
    """矩阵指数：缩放与平方 + (6,6) Padé。"""
    nrm = np.linalg.norm(A, 1)
    s = max(0, int(math.ceil(math.log2(nrm))) + 1) if nrm > 0.5 else 0
    X = A / (2 ** s)
    c = [1.0]
    for kk in range(1, 7):
        c.append(c[-1] * (7 - kk) / (kk * (13 - kk)))
    I = np.eye(A.shape[0])
    N, D, P = I.copy(), I.copy(), I.copy()
    for kk in range(1, 7):
        P = P @ X
        N = N + c[kk] * P
        D = D + ((-1) ** kk) * c[kk] * P
    E = np.linalg.solve(D, N)
    for _ in range(s):
        E = E @ E
    return E


def unstable_mode(pl: dict) -> np.ndarray:
    """开环不稳定模（A 的最大实部本征向量），归一到 ξ = cᵀ x = 1 m。"""
    w, V = np.linalg.eig(pl["A"])
    i = int(np.argmax(w.real))
    v = np.real(V[:, i])
    return v / float(pl["c"] @ v)


def simulate(pl, b, *, kp, kd, tau_a, tau_d, delay, xi0, t_end, dt, frames, closed=True) -> dict:
    """精确离散 x_{k+1} = e^{A dt} x_k 推进；开环档只有电路状态。"""
    n = pl["A"].shape[0]
    if closed:
        Acl, rx, ru = closed_loop(pl, b, kp, kd, tau_a=tau_a, tau_d=tau_d, delay=delay)
        x = initial_state(pl, Acl.shape[0], xi0)
        iV = Acl.shape[0] - 1
    else:
        Acl = pl["A"]; rx = np.concatenate([pl["c"]]); ru = np.zeros(n); iV = None
        x = unstable_mode(pl) * xi0
    Phi = expm(Acl * dt)
    nt = int(round(t_end / dt))
    every = max(1, nt // 600)
    fevery = max(1, nt // frames)
    rec = {k: [] for k in ("t", "xi", "u", "v", "i_ic1", "i_ic2", "i_wall_sum")}
    fr_t, fr_I = [], []
    pas = slice(0, pl["n_passive"])
    for step in range(nt + 1):
        if step % every == 0:
            I = x[:n]
            rec["t"].append(step * dt); rec["xi"].append(float(rx @ x)); rec["u"].append(float(ru @ x))
            rec["v"].append(float(x[iV]) if iV is not None else 0.0)
            rec["i_ic1"].append(float(I[-2])); rec["i_ic2"].append(float(I[-1]))
            rec["i_wall_sum"].append(float(np.sum(I[pas])))
        if step % fevery == 0:
            fr_t.append(step * dt); fr_I.append([float(q) for q in x[:n][pas]])
        if step < nt:
            x = Phi @ x
            if not np.all(np.isfinite(x)) or abs(float(rx @ x)) > 1e3:
                break
    return {"closed": closed, "kp": kp, "kd": kd, "tau_a": tau_a, "tau_d": tau_d, "delay": delay, "xi0": xi0,
            **rec, "frames": {"t": fr_t, "i_passive": fr_I}, "poles": _poles(Acl)}


def _poles(A: np.ndarray, keep: int = 16) -> list:
    w = np.linalg.eigvals(A)
    w = w[np.argsort(-w.real)][:keep]
    return [[float(q.real), float(q.imag)] for q in w]


# --------------------------------------------------------------------------- #
# 壁扫描（内核）
# --------------------------------------------------------------------------- #
def wall_scan(dev, eq, at, *, vessel, eta, log=print) -> dict:
    out = {"vessel_scale": [], "eta_scale": []}
    for key, vals in (("vessel_scale", vessel), ("eta_scale", eta)):
        for v in vals:
            t0 = time.time()
            try:
                r = vstab(dev, eq, at, circuit="passive", passive=PASSIVE, ic=0.0, **{key: float(v)})
                f = r["facts"]
                row = {key: v, "gamma": f["gamma"], "regime": REGIMES.get(int(f["regime_code"]), "?"),
                       "margin": f["margin"], "k": f["k"], "k_ideal": f["k_ideal"]}
            except Exception as ex:  # noqa: BLE001 —— 门按名拒绝也是一个读数（壁太远时 M 不再正定）
                row = {key: v, "refused": f"{type(ex).__name__}: {str(ex)[:200]}"}
            log(f"[scan] {key} = {v}: {row.get('gamma', row.get('refused'))}  ({time.time() - t0:.0f} s)")
            out[key].append(row)
    return out


# --------------------------------------------------------------------------- #
# 几何（画截面用；全部取装置文档与 g-file，不补任何尺寸）
# --------------------------------------------------------------------------- #
def geometry(dev, g, n_passive: int) -> dict:
    from fylite import device
    elems, eta, groups = device.passive_set(dev, groups=GROUPS)
    if len(elems) != n_passive:
        raise SystemExit(f"装置模块给 {len(elems)} 件被动元件，门给 {n_passive} 件——次序对不上就不能着色")
    coils = []
    for c in (dev.get("pf_active") or {}).get("coil") or []:
        els = []
        for e in c.get("element") or []:
            rect = (e.get("geometry") or {}).get("rectangle") or {}
            if rect:
                els.append({"r": float(rect["r"]), "z": float(rect["z"]), "w": float(rect["width"]),
                            "h": float(rect["height"]), "a1": float(e.get("fylite:a1", 0.0)),
                            "a2": float(e.get("fylite:a2", 90.0))})
        coils.append({"name": str(c.get("name")), "fast": bool(device.is_fast_coil(c)), "elements": els})
    lim = device.limiter_unit(dev)
    outline = lim.get("outline") or {}
    grp = []
    for name in GROUPS:
        sl = groups.get(name)
        if sl is not None:
            grp.append({"name": name, "start": int(sl.start), "stop": int(sl.stop)})
    nw, nh = int(g["nw"]), int(g["nh"])
    rr = [g["rleft"] + g["rdim"] * i / (nw - 1) for i in range(nw)]
    zz = [g["zmid"] - 0.5 * g["zdim"] + g["zdim"] * j / (nh - 1) for j in range(nh)]
    psi = np.asarray(g["psirz"], float).reshape(nh, nw)
    span = float(g["sibry"] - g["simag"]) or 1.0
    psin = (psi - g["simag"]) / span
    st = max(1, nw // 65)
    return {"passive": [{"r": e.r, "z": e.z, "w": e.w, "h": e.h, "a1": e.a, "a2": e.a2} for e in elems],
            "passive_groups": grp, "passive_eta_uohm_m": [float(x) for x in eta],
            "coils": coils,
            "limiter": {"r": list(map(float, outline.get("r", []))), "z": list(map(float, outline.get("z", [])))},
            "boundary": {"r": list(map(float, g.get("rbbbs", []))), "z": list(map(float, g.get("zbbbs", [])))},
            "axis": {"r": float(g["rmaxis"]), "z": float(g["zmaxis"])},
            "psi_norm": {"r": rr[::st], "z": zz[::st], "data": psin[::st, ::st].tolist()}}


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #
def _floats(s: str) -> list[float]:
    return [float(x) for x in s.split(",") if x.strip()]


def cmd_run(a) -> int:
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    t_all = time.time()
    dev, g, eq, at, gpath, apath = load_inputs(Path(a.data_dir), a.shot, a.gfile, a.afile)
    pl = plant(dev, eq, at, eta_ic=a.eta_ic, log=log)
    gamma = pl["gamma"]
    log(f"[plant] 被动 {pl['n_passive']} + IC {pl['n_ic']}（PF 保持）: γ = {gamma:.5g} /s  1/γ = {1 / gamma * 1e3:.4g} ms  "
        f"（判据：删 IC 后 {pl['check']['gamma_reduced']:.6g} 对门 {pl['check']['gamma_door_passive']:.6g}）")
    b, kp0 = orientation(pl, tau_a=a.tau_a, tau_d=a.tau_d)
    log(f"[ctrl] P 律下限 K_p,min = {kp0:.4g} V/m（无时延）")
    common = dict(tau_a=a.tau_a, tau_d=a.tau_d, xi0=a.xi0, t_end=a.t_end)
    #: 时延取成 1/γ 的倍数：可不可控由 γT 决定，不由 T 的绝对值决定
    delays = [x / gamma for x in _floats(a.delays_gamma)]
    maps = []
    for T in delays:
        t0 = time.time()
        gm = gain_map(pl, b, kp0, gamma, delay=T, n_grid=a.grid, **common)
        maps.append(gm)
        bb = gm["best"]
        log(f"[ctrl] 增益图 T = {T * 1e3:.4g} ms（γT = {gamma * T:.3g}）: 可稳比例 {gm['stable_fraction']:.2f}  "
            + (f"最快沉降 {bb['settle_s'] * 1e3:.3g} ms @ K_p {bb['kp']:.3g} · K_d {bb['kd']:.3g}，峰值 {bb['u_peak_V']:.3g} V"
               if bb else "无稳定点") + f"  ({time.time() - t0:.0f} s)")
    sweep_d = [x / gamma for x in np.logspace(math.log10(a.gT_lo), math.log10(a.gT_hi), a.gT_n)]
    t0 = time.time()
    dsw = delay_sweep(pl, b, kp0, gamma, delays=sweep_d, n_grid=max(11, a.grid // 2), **common)
    log(f"[ctrl] 可稳定的回路时延上限 T_crit = {dsw['delay_crit']}  γ·T_crit = {dsw['gamma_delay_crit']}  "
        f"({time.time() - t0:.0f} s)")
    nominal = maps[0]["best"]
    sim_kw = dict(tau_a=a.tau_a, tau_d=a.tau_d, xi0=a.xi0, t_end=a.t_end, dt=a.dt, frames=a.frames)
    cases = [("open", "开环（不控）", dict(closed=False, kp=0.0, kd=0.0, delay=0.0))]
    if nominal:
        law = "P" if nominal["kd"] == 0.0 else "PD"
        cases.append(("pd_best", f"{law}（网格上沉降最快）", dict(closed=True, kp=nominal["kp"], kd=nominal["kd"], delay=delays[0])))
    cases.append(("p_only", "只有 P（3 × 下限）", dict(closed=True, kp=3.0 * kp0, kd=0.0, delay=delays[0])))
    if dsw["delay_crit"] and nominal:
        T_bad = 1.5 * dsw["delay_crit"]
        cases.append(("too_slow", f"回路时延 1.5 × 上限（γT = {gamma * T_bad:.2f}）",
                      dict(closed=True, kp=nominal["kp"], kd=nominal["kd"], delay=T_bad)))
    sims = []
    for key, label, kw in cases:
        s_ = simulate(pl, b, **sim_kw, **kw)
        s_.update({"key": key, "label": label})
        sims.append(s_)
        log(f"[sim] {label}: ξ(end) = {s_['xi'][-1]:.3g} m  max|u| = {max(abs(q) for q in s_['u']):.3g} V")
    scan = None
    if not a.no_scan:
        scan = wall_scan(dev, eq, at, vessel=_floats(a.vessel_scales), eta=_floats(a.eta_scales), log=log)
    mode = unstable_mode(pl)
    geo = geometry(dev, g, pl["n_passive"])
    out = {
        "@type": "fylite:EastVerticalControl", "app": APP, "version": VERSION,
        "shot": a.shot, "inputs": {"gfile": gpath.name, "afile": apath.name, "ccbrsp_aturns": at.tolist()},
        "plant": {"gamma": gamma, "growth_time_s": 1.0 / gamma if gamma > 0 else None,
                  "ip": pl["ip"], "k": pl["k"], "k_ideal": pl["k_ideal"], "margin": pl["margin"],
                  "regime": REGIMES.get(pl["regime_code"], "?"), "n_passive": pl["n_passive"], "n_ic": pl["n_ic"],
                  "r_ic_ohm": pl["R_ic"], "eta_ic_uohm_m": pl["eta_ic"],
                  "door_passive": pl["door_passive"], "door_full": pl["door_full"], "check": pl["check"],
                  "notes": pl["notes"],
                  "open_loop_poles": _poles(pl["A"]),
                  "mode": {"xi_m": 1.0, "i_passive_A_per_m": mode[:pl["n_passive"]].tolist(),
                           "i_ic_A_per_m": mode[pl["n_passive"]:].tolist()},
                  "plasma_filaments": pl["plasma_filaments"]},
        "controller": {"law": "u = −K_p ξ − K_d ξ̇_f ；v_IC1 = +v、v_IC2 = −v",
                       "loop": "ξ → [PD] → u → [时延 e^{−sT}（Padé %d 阶）] → [电源 1/(τ_a s + 1)] → v → IC" % PADE_ORDER,
                       "tau_a": a.tau_a, "tau_d": a.tau_d, "pade_order": PADE_ORDER,
                       "kp_min_P": kp0, "gain_maps": maps, "delay_sweep": dsw},
        "simulations": sims, "wall_scan": scan, "geometry": geo,
        "options": {k2: v for k2, v in vars(a).items() if k2 != "func"},
        "provenance": {
            "kernel": "code/vstab —— M、R、G、k、k_ideal、c_ξ、开环增长率、判读档位、壁扫描",
            "app": "删 PF（电流保持）、IC 反对称供电、PD + 时延 + 电源滞后、闭环极点与模态响应、时间仿真",
            "caveats": ["无质量刚性位移模型：只描述 n = 0 竖直模的小信号线性行为；大位移、形变、触壁之后都不在其中",
                        "控制器与执行器参数（K_p、K_d、τ_a、τ_d、T）是本示例的设定，不是 EAST PCS 的实际值",
                        "没有电源电压 / 电流限幅与测量噪声",
                        "ξ 取刚性模型的真值（状态反馈），不是磁测量估计"]},
        "wall_s": time.time() - t_all,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(finite(out), ensure_ascii=False, allow_nan=False, default=_json_default))
    log(f"写出 {a.out}（{Path(a.out).stat().st_size / 1e6:.2f} MB，{out['wall_s']:.0f} s）")
    return 0


def finite(o):
    """非有限的数一律写成 null：理想不稳档的 γ = +∞ 不是一个数，而严格 JSON 里也没有 Infinity。

    ★档位另有字段（``regime``）说明它是理想不稳——null 本身不承载含义，读的人去看档位。
    """
    if isinstance(o, dict):
        return {k: finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [finite(v) for v in o]
    if isinstance(o, np.ndarray):
        return finite(o.tolist())
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    return o


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vs_control.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="被控对象（内核）→ 控制器分析与闭环仿真 → 结果 JSON")
    r.add_argument("data_dir", help="EAST 数据目录（含 g<shot>.* 与 a<shot>.*）")
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--shot", type=int, default=115672)
    r.add_argument("--gfile"); r.add_argument("--afile")
    r.add_argument("--eta-ic", type=float, default=None,
                   help="IC 线圈电阻率 [μΩ·m]；缺省取装置卡里 IC 自己的 resistance")
    r.add_argument("--tau-a", type=float, default=1e-3, help="电源一阶滞后 τ_a [s]")
    r.add_argument("--tau-d", type=float, default=1e-3, help="微分滤波时间常数 τ_d [s]")
    r.add_argument("--delays-gamma", default="0,0.1,0.3,0.6",
                   help="画增益图的回路时延，以 1/γ 为单位（γT），逗号分隔；第一个是名义值")
    r.add_argument("--gT-lo", type=float, default=0.02); r.add_argument("--gT-hi", type=float, default=3.0)
    r.add_argument("--gT-n", type=int, default=15, help="时延扫描的点数（γT 对数均布）")
    r.add_argument("--grid", type=int, default=31, help="增益图每边的点数")
    r.add_argument("--xi0", type=float, default=0.01, help="初始竖直位移 [m]")
    r.add_argument("--t-end", type=float, default=0.4); r.add_argument("--dt", type=float, default=5e-5)
    r.add_argument("--frames", type=int, default=120, help="截面动画的帧数")
    r.add_argument("--no-scan", action="store_true", help="跳过壁扫描（每点一次 code/vstab）")
    r.add_argument("--vessel-scales", default="0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5")
    r.add_argument("--eta-scales", default="0.25,0.5,1,2,4")
    r.set_defaults(func=cmd_run)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
