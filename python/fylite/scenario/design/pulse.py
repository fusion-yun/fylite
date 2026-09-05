"""线一 · 脉冲 —— feed-forward pulse design: a shape trajectory in, voltage waveforms out.

★★2026-09-05 (FYL-DESIGN-16 K-3, the fourth tool to sink).  This module used to
hold ``design_trajectory`` / ``verify_trajectory`` — the GSPulse-shaped whole-pulse
least-squares design, linearised on the finite-difference shape response of
``run.forward_equilibrium``.  That solver is the EFIT lineage removed under LICENSE
3.1, and its recorded answers do not ship either: every call raised
``KefitRunError`` (measured — the kernel repository's ``test_pulse.py`` errored at
collection on every machine).  A design nobody can run is not a design; both
functions and their private dynamics helpers are retired.

What the pulse line IS today is the design page's feed-forward chain — every
waypoint's currents designed by the linear isoflux start, the conductor circuit
assembled once, the per-channel voltages by the exact inverse of the circuit
integrator, and a free-boundary check at chosen waypoints — and that chain is
``case.rs::pulse_case`` (``code/pulse``), one recipe for the page and for Python.
:func:`feedforward` builds the PLAN and reads the RECORD back.

:func:`channel_limits` stays: the supply ratings folded into the design's units,
which ``fylite cases`` and the older gates still read (``code/breakdown`` folds the
same numbers inside the kernel).
"""
from __future__ import annotations

import numpy as np

from ...device import pf_channel_map

__all__ = ["feedforward", "channel_limits"]


def channel_limits(device) -> dict:
    """Per-channel supply limits, converted into the design's own units.

    ★It used to take a ``table_dir`` first and never read it: every number
    here comes from the device document and the frozen channel map.  A
    parameter that is threaded through three call sites and used by none
    says the deck is consulted when it is not.  ★★The retired trajectory
    design had lost the same parameter for the same reason — with the last
    Green-table read gone from the package, no entry point on this line has
    anything to do with a table directory.

    The design variable is a PER-TURN voltage on a BRSP channel, and the
    state is BRSP ampere-turns; the machine data is a TERMINAL voltage
    and a TERMINAL current per supply.  The bridge is the per-element
    turn count (``pf_active_circuits.element_turns``, cross-validated to
    0.07 % by the mlc benchmark) together with the E-14 channel weights:

        v_max_per_turn[c] = min_j ( V_supply[j] / N_j )
        i_max_aturn[c]    = min_j ( I_supply * N_j / w_cj )

    Taking the min over a channel's elements is the conservative reading
    for the two series pairs, whose two entries in the supply table
    disagree (PF7 560 V against PF9 280 V) -- the pair shares one supply
    and the table does not say which entry governs.  Marked [TBD]; a
    caller who knows better can override both vectors.
    """
    ps = device["power_supply"]
    turns = np.asarray(device["pf_active_circuits"]["element_turns"], float)
    vsup = np.asarray(ps["max_voltage_V"], float)
    isup = float(ps["current_limit_kA"]) * 1.0e3
    chans = pf_channel_map()
    v_max = np.empty(len(chans))
    i_max = np.empty(len(chans))
    for c, combo in enumerate(chans):
        v_max[c] = min(vsup[j] / turns[j] for j, _ in combo)
        i_max[c] = min(isup * turns[j] / w for j, w in combo)
    return {"v_max_per_turn": v_max, "i_max_aturn": i_max,
            "channels": chans, "note": "series-pair supply rating is [TBD]"}


#: ★★★2026-09-02：这里曾有一份 `bounded_lstsq` 的**纯 numpy 实现**，它自陈是
#: 「内核那份的重复，且是冻结的」（FYL-DESIGN-08 N-5），下面的 QP 一直调的是它。
#: 现已删除，调用点改走 `kernel.bounded_lstsq`。两条测量都记在这里，因为它们
#: 是当初冻结它、和现在删掉它的同一批依据：
#:
#:   * 良态问题上两者一致到 **1e-13**（本次复测 7.2e-13，60×24 随机箱约束），
#:     所以没有任何物理量把它们分开；
#:   * 击穿设计 `flux_target = 1.0` Wb 上，numpy 那条跑满 4000 次迭代上限、
#:     残差 **1.08e3**，而内核到 **6.7e-1** —— 三个数量级，而且**是静默的**：
#:     它返回的是一份「设计」，只是那不是个零点。`design.breakdown` 当初正是
#:     为此改走内核入口。
#:
#: ★**当初留下它的理由在本仓已不成立。** 那条理由是录音-oracle 体制：
#: `design_trajectory` 把电流喂给 `fylite.run.forward_equilibrium`，而那是按输入
#: 哈希回放的录音，1e-13 的电流差就是另一个键、于是查不到，三条 trajectory 判据
#: 会从「拿设计去对一次真解」变成**根本不跑**。而在这个仓里：`_oracle.py` 不在，
#: `run.forward_equilibrium` 直接抛「not available in this distribution」，那三条
#: 判据也不在本仓。**代价已经付过了，冻结的那份只剩下坏处。**


def feedforward(waypoints, *, verify=(), n_points: int = 24, x_weight: float = 0.0,
                nulls=None, control=None, i_max_aturn=None, profile=None,
                eta_coil_uohm_m: float | None = None, eta_vessel_uohm_m: float | None = None,
                limiter: str | None = None, device=None, **solve_kw) -> dict:
    """A feed-forward pulse — BY THE KERNEL (``code/pulse``).

    ``waypoints`` is a sequence of ``(t, ip, target)`` with ``target`` the Miller
    description (``r0``, ``z0``, ``a``, ``kappa``, ``delta_upper``, ``delta_lower``)
    as a mapping or a 6-tuple; ``ip <= 0`` means no plasma at that waypoint (the
    currents are held).  ``verify`` names waypoint indices to re-solve; ``nulls``
    is a list of ``(r, z)`` field nulls shared by every start (weighted by
    ``x_weight``), ``control`` a list of ``(r, z, w)`` isoflux control points.
    ``profile`` is ``{"beta0", "emp", "enp"}`` (analytic) or
    ``{"psin", "dpressure_dpsi", "f_df_dpsi"}`` (the delivered table) for the
    verify solves; ``solve_kw`` are ``relax`` · ``max_iter`` · ``tol`` · ``fb_gain``.

    Returns the record's arrays under the names its callers know: ``time``,
    ``currents`` (nt, n_ch) [A-turn], ``voltages`` (nt, n_ch) [V per turn],
    ``passive_currents`` (nt, n_v), ``resistance``, the per-waypoint design
    statistics and, per verified waypoint, the solve's shape and field.
    """
    from ...io import fydoc
    from . import _device
    known = {"relax", "max_iter", "tol", "fb_gain"}
    bad = set(solve_kw) - known
    if bad:
        raise TypeError(f"feedforward() got unexpected solver settings {sorted(bad)}; "
                        f"the kernel takes {sorted(known)}")
    keys = ("r0", "z0", "a", "kappa", "delta_upper", "delta_lower")
    t, ip, tg = [], [], []
    for w in waypoints:
        tk, ipk, target = w
        t.append(float(tk))
        ip.append(float(ipk))
        if isinstance(target, dict):
            tg.append([float(target.get(k, 0.0 if k in ("z0", "delta_upper", "delta_lower") else 1.0))
                       for k in keys])
        else:
            tg.append([float(v) for v in target])
    settings = {"n_points": float(n_points), "x_weight": float(x_weight)}
    settings.update({k: float(v) for k, v in solve_kw.items()})
    if eta_coil_uohm_m is not None:
        settings["eta_coil_uohm_m"] = float(eta_coil_uohm_m)
    if eta_vessel_uohm_m is not None:
        settings["eta_vessel_uohm_m"] = float(eta_vessel_uohm_m)
    if limiter is not None:
        settings["limiter"] = str(limiter)
    inputs = {"device": _device(device),
              "pulse": {"fylite:time": np.asarray(t, float), "fylite:ip": np.asarray(ip, float),
                        "fylite:target": np.asarray(tg, float).reshape(len(t), 6)}}
    if verify:
        inputs["pulse"]["fylite:verify"] = np.asarray(list(verify), float)
    discharge = {}
    if nulls:
        discharge["fylite:null_r"] = np.asarray([p[0] for p in nulls], float)
        discharge["fylite:null_z"] = np.asarray([p[1] for p in nulls], float)
    if control:
        discharge["fylite:control_r"] = np.asarray([c[0] for c in control], float)
        discharge["fylite:control_z"] = np.asarray([c[1] for c in control], float)
        discharge["fylite:control_w"] = np.asarray([c[2] if len(c) > 2 else 1.0 for c in control], float)
    if i_max_aturn is not None:
        discharge["fylite:i_max_aturn"] = np.atleast_1d(np.asarray(i_max_aturn, float))
    if discharge:
        inputs["discharge"] = discharge
    prof = dict(profile or {})
    if "psin" in prof:
        inputs["equilibrium"] = {"time_slice": [{"profiles_1d": {
            "fylite:psi_norm": np.asarray(prof["psin"], float),
            "dpressure_dpsi": np.asarray(prof["dpressure_dpsi"], float),
            "f_df_dpsi": np.asarray(prof["f_df_dpsi"], float)}}]}
    else:
        for k in ("beta0", "emp", "enp"):
            if k in prof:
                settings[k] = float(prof[k])
    rec = fydoc.complete("code/pulse", {"settings": settings, "inputs": inputs})
    arr = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    fact = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    n_ch = int(rec["dims"]["n"])
    checks = []
    idx = arr("check_index")
    for j in range(idx.size):
        checks.append({"k": int(idx[j]), "t": t[int(idx[j])], "ok": bool(arr("check_ok")[j]),
                       "shape": dict(zip(keys, (float(v) for v in arr("check_shape")[j]))),
                       "psi": arr("check_psi")[j],
                       **{k: float(arr("check_" + k)[j]) for k in
                          ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip", "residual", "iterations",
                           "converged", "settled", "bnd_kind", "xpt_r", "xpt_z", "fb_amp", "zc")}})
    return {"time": arr("time"), "currents": arr("aturns").reshape(len(t), n_ch),
            "voltages": arr("voltage").reshape(len(t), n_ch),
            "passive_currents": arr("passive_current").reshape(len(t), -1),
            "resistance": arr("resistance"), "n_channels": n_ch,
            "n_passive": int(fact("n_passive")),
            "design_psi_rms": arr("design_psi_rms"), "design_b_x": arr("design_b_x"),
            "design_at_bound": arr("design_at_bound").reshape(len(t), n_ch),
            "checks": checks, "notes": list(rec.get("notes", []))}
