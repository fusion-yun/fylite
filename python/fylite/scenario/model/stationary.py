"""自洽稳态外环 —— the stationary plasma loop (T-C14).

★★**这一层不是新机制，它是已经在跑的那个皮卡。**  The flux match (T-C13)
already freezes the burn at each iteration boundary and lags the pedestal by
one, for a reason that was measured rather than assumed: with the alpha power
live inside the Newton Jacobian one probe lifts every radius of a channel
together, the core temperature rises, the alpha power rises, and *the target
chases its own answer*.  What this module adds is only that the same Picard
wraps three more things — the steady current, the sawtooth, and the
equilibrium.

The order is upstream's own (FUSE's ``ActorStationaryPlasma``):

    源 → 台基 → 输运 → 电流 → 锯齿 → 平衡
    sources -> pedestal -> transport -> current -> sawteeth -> equilibrium

and so is the convergence test — **the relative change of the pressure and of
the current profile between rounds**, 5 % by default
(``convergence_error = 5E-2``, ``max_iterations = 5``).

★★**What is here and what is deliberately not.**  The six steps are the
caller's, passed in as callables: this package has a flux match
(:func:`fylite.kernel.flux_match`), an EPED1-NN (:func:`fylite.kernel.eped1nn`),
a sawtooth (the kernel's ``sawtooth_crash``, an oracle-only export since T-4 第六刀) and a free-boundary solve
(:func:`fylite.kernel.gs_free_solve`), but *which* of them a given run uses,
and on what geometry, is a scenario decision and not a loop decision.  What
the loop owns — and what a second host can therefore be held against — is the
**order**, the **convergence rule**, and the **steady-current step** itself.

★The browser (``app/assets/worker.js``) runs the same loop.  The session file
it writes carries ``fylite:stationary/fylite:steady_current`` — every array
:func:`steady_current` was handed and the ψ that came out — precisely so the
two hosts can be held against each other (T-C14〔五〕);
``app/tests/validate-stationary.mjs`` 〔己〕 does exactly that.
"""

from __future__ import annotations

import math

import numpy as np

from ... import fyo
from . import assembly

__all__ = ["relative_change", "steady_current", "StationaryRound",
           "stationary_rounds"]


def relative_change(new, old) -> float:
    r"""The loop's own convergence measure: ``max|a-b| / max|b|``.

    ★An **L∞** measure and not an L2 one, and that is upstream's choice
    carried over: a pressure profile that has settled everywhere except at
    one radius has *not* settled, and an RMS would let that one radius hide
    under sixty that did.

    ★The denominator is ``max|b|`` — the previous round's own scale — rather
    than a per-point ratio, because a per-point ratio is dominated by the
    edge, where both profiles are near zero and the ratio is noise.

    Returns 0.0 when the previous round is identically zero: there is no
    scale to be relative to, and a NaN here would silently disable half the
    convergence test.
    """
    a = np.asarray(new, float)
    b = np.asarray(old, float)
    if a.shape != b.shape:
        raise ValueError(
            f"relative_change: two rounds on different ladders ({a.shape} vs "
            f"{b.shape}) — relabel one onto the other first; a change "
            "measured across a moving grid is mostly the grid")
    den = float(np.max(np.abs(b))) if b.size else 0.0
    if not (den > 0):
        return 0.0
    return float(np.max(np.abs(a - b))) / den


def steady_current(
    rho,
    *,
    vprime,
    gm3,
    gm2,
    fpol,
    b0: float,
    te,
    ti,
    ne,
    psi,
    sigma_par,
    j_ni,
    dt: float = math.inf,
    edge_psi: float | None = None,
    edge_psi_rate: float = 0.0,
    tol_steady: float = 1e-9,
    n_coupling: int = 2,
    tol: float = 1e-10,
    max_inner: int = 60,
) -> dict:
    r"""步 4 — the ψ channel driven to its stationary state, and nothing else.

    The heat and density channels are **off**: the flux match has just solved
    the temperatures, and a steady heat solve on top would be a second answer
    to the question the Newton machine answered.

    ★★``dt`` DEFAULTS TO INFINITY AND THAT IS NOT THE FLAT TOP.  At
    ``dt = inf`` the time derivative is gone, so the Ohmic term ``sigma E``
    — which IS ``-dpsi/dt`` — is identically zero and what comes out carries
    only the non-inductive current, whatever ``edge_psi_rate`` says (pinned
    in ``test_stationary.py``: exactly linear in ``j_ni``, unchanged to
    1e-12 by a decade of ``sigma_par``, by the boundary flux, and by a
    -5 Wb/s boundary rate).  A tokamak holding a flat top is **stationary,
    not steady**: ``dpsi/dt = V_loop`` uniform, flux being consumed.  Pass a
    long FINITE ``dt`` with a boundary rate for that state — ``1e5`` and
    ``1e7`` give the same profile to 1e-5 on a ladder whose tau_R is ~5 s,
    and the enclosed current is affine in the rate to five digits.

    ★``sigma_par`` and ``j_ni`` are handed in **frozen** rather than
    recomputed.  That is the same Picard the rest of this loop runs on, and
    it is also what makes the cross-host claim a claim about *one solve*:
    ``同一个解`` and ``同一条闭包`` are two different assertions, and this
    function makes the first.

    ★``ne`` is passed because :func:`~fylite.scenario.model.assembly.solve_core`
    wants a density beside the temperatures; **it does not enter this march**
    — measured, not assumed: marching the same ψ with ``n_e`` and with
    ``n_e/2`` gives ``max|Δψ| = 0`` exactly, because with the heat and
    density channels off no equation in the system contains it.

    ``edge_psi_rate`` [Wb/s] is the boundary loop voltage: with it at zero
    the steady state carries only the non-inductive current, which is why
    the I_p that comes out is a **result** and not the requested one.  Closing
    that gap is the I_p controller's job (T-C16), not this function's.

    Returns ``{psi, q, psi_repaired, i_p}`` — ``i_p`` from
    :func:`fylite.fyo.enclosed_plasma_current`, which reads ψ in **Wb/rad**
    while this channel's ψ is **full-turn Wb** (COCOS 17), so the conversion
    happens here rather than in either caller's head.
    """
    rho = np.asarray(rho, float)
    out = assembly.solve_core(
        rho,
        vprime=vprime, gm3=gm3, gm2=gm2, fpol=fpol, b0=b0,
        ne=np.asarray(ne, float),
        te=np.asarray(te, float), ti=np.asarray(ti, float),
        heat=False,
        current=lambda state: (np.asarray(sigma_par, float),
                               np.asarray(j_ni, float)),
        psi=np.asarray(psi, float),
        dt=float(dt), max_outer=1,
        tol_steady=tol_steady, n_coupling=n_coupling,
        edge_psi=(float(np.asarray(psi, float)[-1]) if edge_psi is None
                  else float(edge_psi)),
        edge_psi_rate=float(edge_psi_rate),
        tol=tol, max_inner=max_inner)
    psi_out = np.asarray(out["psi"], float)
    #: ★★RE-ANCHORED TO THE EDGE IT CAME IN ON.  With a loop voltage and a
    #: long step the stationary state has consumed ``V_loop * dt`` of flux,
    #: so ``psi`` comes back offset by thousands of Wb — while every quantity
    #: anyone reads off it (``q``, the enclosed current) depends only on
    #: ``dpsi/drho``.  The shift is a GAUGE choice and it is stated here
    #: rather than left to each caller, because the browser makes the same
    #: one and「两个宿主同一个解」has to be a claim about one gauge.
    psi_in = np.asarray(psi, float)
    if psi_out.size and psi_in.size:
        psi_out = psi_out + (float(psi_in[-1]) - float(psi_out[-1]))
    ip = fyo.enclosed_plasma_current(rho, vprime, gm2,
                                     psi_out / (2.0 * math.pi))
    return {"psi": psi_out, "q": np.asarray(out["q"], float),
            "psi_repaired": out.get("psi_repaired"),
            "i_p": float(ip[-1])}


class StationaryRound(dict):
    """One round's record — a plain dict, with the browser's own key names.

    ★The keys match ``fylite:stationary/fylite:rounds`` in the session file
    one for one, so a round from either host reads the same and a gate can
    compare them without a translation table in between.
    """


def stationary_rounds(
    *,
    transport,
    pressure,
    current=None,
    sawtooth=None,
    equilibrium=None,
    q_of=None,
    max_rounds: int = 1,
    tolerance: float = 5e-2,
) -> dict:
    r"""The loop itself: six steps a round, until two rounds agree.

    Every step is a callable the caller supplies, and every one of them may
    return a *reason* instead of doing its work — the loop stops and says
    which, rather than reporting a round that did nothing:

    ``transport()``
        源 → 台基 → 输运, i.e. the flux match with the burn frozen and the
        pedestal lagged.  Returns ``{"converged": bool, **record}``.  A round
        whose match did not converge **ends the loop**: alternating onto a
        state the inner solve never reached would be iterating a quantity
        nobody solved for.
    ``pressure()``
        the profile the convergence test is taken on (Pa on the ladder).
    ``current()``
        步 4, normally :func:`steady_current`; ``None`` skips it.
    ``sawtooth()``
        步 5, on the q the current step produced.
    ``equilibrium()``
        步 6.  Returns ``{"skipped": why}`` for a geometry with no boundary
        to re-solve (a g-file's metric came from a file), ``{"failed": why}``
        when the solve itself failed, and otherwise its own record.
        ★When it moves the ladder it is the CALLER's job to relabel the
        profiles — and to relabel the previous round's pressure and q too,
        or ``Δp`` would be mostly the grid moving.
    ``q_of()``
        the current profile the second half of the test is taken on.

    ★★**The first round never counts as converged, however small its
    numbers.**  It has no previous round to differ from — the profiles it is
    compared against came from the starting guess, not from a solved round —
    and a loop that reported convergence there would be reporting that its
    initial guess had not changed much.

    Returns ``{rounds, converged, why, tolerance, max_rounds}``: ``why`` is
    ``""`` when the loop simply ran out of rounds, which is a **different**
    statement from ``"match"`` (the inner solve stalled) and is kept apart
    from it for that reason.
    """
    rounds: list[StationaryRound] = []
    converged = False
    why = ""
    p_prev = None
    q_prev = None
    for rnd in range(max(1, int(max_rounds))):
        p_prev = np.asarray(pressure(), float) if p_prev is None else p_prev
        if q_prev is None and q_of is not None:
            q_prev = np.asarray(q_of(), float)
        rec = StationaryRound(round=rnd + 1)
        tr = transport()
        rec.update(tr or {})
        if not (tr and tr.get("converged")):
            why = "match"
            rounds.append(rec)
            break
        if max_rounds <= 1:
            converged = True
            rounds.append(rec)
            break
        if current is not None:
            cur = current()
            if cur is None or cur.get("failed"):
                why = (cur or {}).get("failed") or "current"
                rounds.append(rec)
                break
            rec.update(cur)
        #: ★步 5 rides with 步 4: the current round and the crash that
        #: follows it are ONE round.  (In the browser this is literally a
        #: flag that has to span both calls, and restoring it one line early
        #: made the sawtooth refuse every round — the gate caught it.)
        if sawtooth is not None:
            rec["sawtooth"] = sawtooth()
        if equilibrium is not None:
            eq = equilibrium() or {}
            if eq.get("failed"):
                why = eq["failed"]
                rounds.append(rec)
                break
            rec["equilibrium"] = None if eq.get("skipped") else eq
            rec["equilibrium_skipped"] = eq.get("skipped")
        p_now = np.asarray(pressure(), float)
        d_p = relative_change(p_now, p_prev)
        d_q = (relative_change(np.asarray(q_of(), float), q_prev)
               if q_of is not None and q_prev is not None else float("nan"))
        rec["d_pressure"] = d_p
        rec["d_q"] = d_q
        rounds.append(rec)
        p_prev = p_now
        if q_of is not None:
            q_prev = np.asarray(q_of(), float)
        first = rnd == 0
        if not first and d_p < tolerance and (math.isnan(d_q)
                                              or d_q < tolerance):
            converged = True
            break
    return {"rounds": rounds, "converged": converged, "why": why,
            "tolerance": float(tolerance), "max_rounds": int(max_rounds),
            "equilibrium_rounds": sum(1 for r in rounds
                                      if r.get("equilibrium"))}
