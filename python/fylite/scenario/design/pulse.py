"""Feedforward pulse design: target shape trajectory -> voltage waveforms (E-10).

The design problem P1 does not answer.  P1 asks "given voltages, what happens";
this asks the inverse: **given a shape trajectory, what voltages produce
it** — and answers it for the whole pulse at once rather than time slice
by time slice.

Shape of the algorithm, after GSPulse (J. Wai / CFS, MIT; see the
FYD-PORT-01-FYLITE absorption chapter): an outer whole-pulse quadratic
program alternating with a per-time equilibrium update.  Two deliberate
differences here:

* the QP is solved as **plain least squares in pure numpy**.  The only
  constraint is the conductor dynamics, which is a linear equality — so
  substituting it out leaves an unconstrained problem, and fylite keeps
  its numpy-only dependency instead of pulling in a QP package;
* the linearization uses the **finite-difference shape response of the
  real solver** (:mod:`fylite.scenario.design.shape`, E-16), not an analytic perturbed
  GS.  Re-linearizing between outer iterations is what plays the role of
  GSPulse's Picard update.

Cost (all terms optional through weights):

    J = sum_k || W_e (obs_k - obs_ref_k) ||^2
      + lam_v || V ||^2 + lam_dv || dV/dt ||^2

subject to the implicit-Euler conductor dynamics driving obs_k through
the response matrix.

**Feasibility is reported, never silently truncated** (``feasible``,
``residual_m``): a design that cannot reach its targets must say so —
the shape-control counterpart of the lesson in the free-boundary
chapter, where a parameter existed, accepted values, and changed
nothing.
"""
from __future__ import annotations

import tempfile

import numpy as np

from ...device import (channel_matrices, conductor_set, passive_set,
                       pf_channel_map)

from ...io import geqdsk

from . import shape
from ...run import forward_equilibrium
from ... import kernel

__all__ = ["design_trajectory", "verify_trajectory", "channel_limits"]


def channel_limits(device) -> dict:
    """Per-channel supply limits, converted into the design's own units.

    ★It used to take a ``table_dir`` first and never read it: every number
    here comes from the device document and the frozen channel map.  A
    parameter that is threaded through three call sites and used by none
    says the deck is consulted when it is not.  ★★:func:`design_trajectory`
    has now lost the same parameter for the same reason — with the last
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


def _dynamics_maps(M, R, t, n_ch):
    """Linear maps x = x_free + L @ vec(V) for implicit-Euler dynamics.

    State is the full conductor vector (channels first, then passive);
    only the first ``n_ch`` rows are driven.  Returns the free response
    (zero voltage) and the sensitivity of every channel state to every
    voltage sample, as arrays (n_t, n) and (n_t, n, n_t, n_ch).
    """
    n = M.shape[0]
    dts = np.diff(np.asarray(t, float))
    steps = [np.linalg.solve(M / dt + np.diag(R), M / dt) for dt in dts]
    gains = [np.linalg.solve(M / dt + np.diag(R), np.eye(n)[:, :n_ch])
             for dt in dts]
    n_t = len(t)
    L = np.zeros((n_t, n, n_t, n_ch))
    for k in range(1, n_t):
        L[k] = np.einsum("ij,jab->iab", steps[k - 1], L[k - 1])
        L[k, :, k, :] += gains[k - 1]
    return L


def design_trajectory(measurements, time, targets: shape.ShapeTargets,
                      obs_ref, x0, *, device,
                      passive_groups=("inner_shell",), profile=None,
                      weights=None, lam_v: float = 1e-6, lam_dv: float = 1e-4,
                      n_outer: int = 2, tol_m: float = 5e-3,
                      limits: bool = False, v_max_per_turn=None,
                      i_max_aturn=None, out=None, **run_kw) -> dict:
    """Design per-turn channel voltages that track a shape trajectory.

    Args:
        time: (n_t,) design grid [s], strictly increasing.
        obs_ref: (n_t, n_obs) target observable trajectory [m]; NaN marks
            "don't care" entries, which drop out of the cost.
        x0: initial channel state [A-turn].
        weights: (n_obs,) per-observable weights; default 1 for every
            finite target.
        n_outer: re-linearization passes (the Picard-like outer loop).
        tol_m: feasibility threshold on the RMS tracking residual [m].
        limits: when True the supply VOLTAGE limits become HARD box
            constraints on the design (E-23), so an over-ambitious target
            comes back as tracking residual rather than as an
            unrealizable waveform.  Current limits cannot be a box on the
            design variable (they constrain the state), so they are
            checked and REPORTED per channel instead of silently ignored.
        v_max_per_turn / i_max_aturn: override the limits derived from
            ``device`` by :func:`channel_limits`.
    """
    t = np.asarray(time, float)
    ref = np.asarray(obs_ref, float)
    x0 = np.asarray(x0, float)
    n_t, n_obs = ref.shape
    n_ch = x0.size
    profile = dict(profile or {"betap0": 0.69})
    outdir = out or tempfile.mkdtemp(prefix="fylite_pulse_")

    eta_c = device["pf_active_circuits"]["resistivity_uohm_m"]
    cond = conductor_set()
    pas_el, pas_eta, _ = passive_set(device, passive_groups)
    #: ★the channel-space block assembly is `channel_matrices` with THIS
    #: passive set — it used to be spelled out again here in numpy, which
    #: is the same M and R a second time
    cm = channel_matrices(cond, eta_coil_uohm_m=eta_c,
                                   passive=(pas_el, pas_eta), nu=3, nv=3)
    M, R = cm["M"], cm["R"]
    n = M.shape[0]

    mask = np.isfinite(ref)
    w = np.ones(n_obs) if weights is None else np.asarray(weights, float)

    lim = channel_limits(device)
    L = _dynamics_maps(M, R, t, n_ch)          # (n_t, n, n_t, n_ch)
    V = np.zeros((n_t, n_ch))
    history, iters = [], []
    for _ in range(max(1, n_outer)):
        # linearize the shape map about the CURRENT design's mean state
        state = np.zeros((n_t, n))
        state[0, :n_ch] = x0
        for k in range(1, n_t):
            dt = t[k] - t[k - 1]
            state[k] = np.linalg.solve(M / dt + np.diag(R),
                                       M @ state[k - 1] / dt +
                                       np.concatenate([V[k], np.zeros(n - n_ch)]))
        x_lin = state[:, :n_ch].mean(axis=0)
        resp = shape.shape_response(measurements, x_lin, targets, profile=profile,
                                    out=outdir, **run_kw)
        J = resp["J"]                                   # (n_obs, n_ch)

        # free response (V = 0) and the sensitivity of obs to vec(V)
        free = np.zeros((n_t, n))
        free[0, :n_ch] = x0
        for k in range(1, n_t):
            dt = t[k] - t[k - 1]
            free[k] = np.linalg.solve(M / dt + np.diag(R), M @ free[k - 1] / dt)
        obs_free = resp["base"][None, :] + (free[:, :n_ch] - x_lin[None, :]) @ J.T
        S = np.einsum("oc,kcia->koia", J, L[:, :n_ch, :, :])   # (n_t,n_obs,n_t,n_ch)

        rows, rhs = [], []
        for k in range(n_t):
            for o in range(n_obs):
                if not mask[k, o]:
                    continue
                rows.append(w[o] * S[k, o].reshape(-1))
                rhs.append(w[o] * (ref[k, o] - obs_free[k, o]))
        A_track = np.asarray(rows)
        b_track = np.asarray(rhs)

        nv = n_t * n_ch
        A_eff = np.sqrt(lam_v) * np.eye(nv)
        D = np.zeros((max(n_t - 1, 1) * n_ch, nv))
        for k in range(n_t - 1):
            dt = t[k + 1] - t[k]
            D[k * n_ch:(k + 1) * n_ch, (k + 1) * n_ch:(k + 2) * n_ch] = np.eye(n_ch) / dt
            D[k * n_ch:(k + 1) * n_ch, k * n_ch:(k + 1) * n_ch] = -np.eye(n_ch) / dt
        A = np.vstack([A_track, A_eff, np.sqrt(lam_dv) * D])
        b = np.concatenate([b_track, np.zeros(nv), np.zeros(D.shape[0])])
        if limits:
            vmax = (np.asarray(v_max_per_turn, float) if v_max_per_turn is not None
                    else lim["v_max_per_turn"])
            vmax = np.broadcast_to(vmax, (n_ch,))
            hi = np.tile(vmax, n_t)
            sol, n_used = kernel.bounded_lstsq(A, b, -hi, hi)
            iters.append(n_used)
        else:
            sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        V = sol.reshape(n_t, n_ch)
        resid = float(np.sqrt(np.mean((A_track @ sol - b_track) ** 2)))
        history.append(resid)

    # final predicted state trajectory
    state = np.zeros((n_t, n))
    state[0, :n_ch] = x0
    for k in range(1, n_t):
        dt = t[k] - t[k - 1]
        state[k] = np.linalg.solve(M / dt + np.diag(R),
                                   M @ state[k - 1] / dt +
                                   np.concatenate([V[k], np.zeros(n - n_ch)]))
    imax = (np.asarray(i_max_aturn, float) if i_max_aturn is not None
            else lim["i_max_aturn"])
    vmax = (np.asarray(v_max_per_turn, float) if v_max_per_turn is not None
            else lim["v_max_per_turn"])
    v_peak = np.max(np.abs(V), axis=0)
    i_peak = np.max(np.abs(state[:, :n_ch]), axis=0)
    over_v = np.flatnonzero(v_peak > vmax * (1.0 + 1e-9))
    # Self-check before believing the current limits: the INITIAL state is a
    # real shot's currents, so any channel whose limit it already violates has
    # a wrong limit, not a violating design.  The element-to-turns
    # correspondence those limits rest on is exactly what ledger E-15 leaves
    # open, so such channels are reported as suspect and excluded from the
    # violation list rather than blamed on the trajectory.
    suspect = np.flatnonzero(np.abs(x0) > imax)
    ok_i = np.setdiff1d(np.arange(n_ch), suspect)
    over_i = ok_i[i_peak[ok_i] > imax[ok_i]]
    return {"time": t, "voltages": V, "currents": state[:, :n_ch],
            "passive_currents": state[:, n_ch:], "residual_m": history[-1],
            "residual_history": history, "feasible": history[-1] <= tol_m,
            "tol_m": tol_m, "labels": targets.labels(), "outdir": outdir,
            "n_channels": n_ch, "limits_enforced": bool(limits),
            "v_max_per_turn": vmax, "i_max_aturn": imax,
            "v_peak_per_turn": v_peak, "i_peak_aturn": i_peak,
            "channels_over_voltage": over_v.tolist(),
            "channels_over_current": over_i.tolist(),
            "channels_current_limit_suspect": suspect.tolist(),
            "current_limit_note": (
                "channels listed as suspect have limits the equilibrium's own "
                "currents already exceed -- the limit is wrong, not the "
                "design; see ledger E-15 (element-to-turns mapping)"),
            "within_limits": bool(over_v.size == 0 and over_i.size == 0),
            "bounded_iterations": iters}


def verify_trajectory(measurements, design, targets: shape.ShapeTargets, *,
                      profile=None, every: int = 1, out=None, **run_kw) -> dict:
    """Run the designed currents through the real solver and report the
    achieved observables — the check that the design is not a fiction of
    its own linearization."""
    profile = dict(profile or {"betap0": 0.69})
    outdir = out or design["outdir"]
    ks = range(0, len(design["time"]), every)
    got = []
    for k in ks:
        r = forward_equilibrium({**measurements,
                                 "brsp": list(design["currents"][k])},
                                out=outdir, **profile, **run_kw)
        got.append(shape.shape_observables(geqdsk.read_geqdsk(r["gfile"]), targets))
    return {"k": list(ks), "t": design["time"][list(ks)],
            "observables": np.asarray(got)}
