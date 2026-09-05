"""线三 · 物理建模 / 预测 (S-7) — zerod · transport · coupled · tglf.

Four tools that answer four different questions, and the boundaries between
them are the point:

* :func:`zerod` — prescribed profiles in, 0-D scalars out.  ``Q`` here is
  arithmetic on the user's own inputs, not a prediction.
* :func:`transport` — fixed geometry, one channel solved on a prescribed
  metric.  It predicts a temperature; it does not move the equilibrium.
* :func:`coupled` — equilibrium and transport alternating.  ★The feedback is
  on the pressure's AMPLITUDE, not its shape: the free-boundary solver takes
  a parameterised source (beta0, emp, enp) and has no entry for an arbitrary
  ``p(psi)``.  A loop that fed the shape back would be a stronger claim.
* :func:`tglf` — local linear stability and quasilinear fluxes.  ``gamma``
  is a growth rate, not a flux.

Every number comes from the kernel.  This module chooses the surfaces, the
waveforms and the alternation, and reports what stopped where.
"""
from __future__ import annotations

import numpy as np

from dataclasses import dataclass, field

from . import gyrofluid as _tglf
from ... import kernel as K
from .. import provenance

__all__ = ["zerod", "transport", "coupled", "tglf",
           "Phases", "Waveform", "Scenario", "evaluate"]


# --------------------------------------------------------------------------- #
# The prescribed 0-D discharge: its four phases, its waveforms, and the
# scenario that names them.
#
# ★This was `fylite/zerod.py`.  Everything it computed is the kernel's now —
# the Bosch-Hale reactivity, the prescribed shape, the volume integrals, the
# Spitzer-like resistivity, and (this batch) the trapezoid, the phase test,
# the actuator window and the start/end policy of the three centre
# waveforms.  What is left is a DESCRIPTION of a run plus the call that
# evaluates it, which is what a scenario line is for — so it lives here,
# beside the tool that publishes it, instead of in a module of its own whose
# name promised physics it no longer had.
# --------------------------------------------------------------------------- #
@dataclass
class Phases:
    """The four phase boundaries [s]."""
    t_breakdown: float = 0.0
    t_rampup_end: float = 1.0
    t_flattop_end: float = 8.0
    t_end: float = 10.0

    #: ★The four boundaries are DATA and everything computed from them is
    #: the kernel's.  They appear in the ramp rates, in the flux budget and
    #: in the label a slice is reported under, so a second spelling of the
    #: trapezoid is a second discharge wearing the same name — and there
    #: were two, one here and one in the browser page.
    @property
    def bounds(self) -> tuple:
        return (self.t_breakdown, self.t_rampup_end, self.t_flattop_end,
                self.t_end)


@dataclass
class Waveform:
    """A heating actuator: constant power between two times."""
    power_w: float = 0.0
    t_on: float = 0.0
    t_off: float = 1e9

    def at(self, t):
        #: the kernel's `actuator` rule, in one line of numpy: on between
        #: `t_on` and `t_off` inclusive, off elsewhere — the same closed
        #: interval `code/zerod` applies to its own `paux` setting
        t = np.asarray(t, float)
        return np.where((t >= self.t_on) & (t <= self.t_off), float(self.power_w), 0.0)


@dataclass
class Scenario:
    """A prescribed discharge.  Geometry defaults are EAST-like."""
    phases: Phases = field(default_factory=Phases)
    ip_flattop: float = 4.0e5          # A
    ne_flattop: float = 4.0e19         # m^-3, on-axis
    te_flattop: float = 3.0            # keV, on-axis
    ti_over_te: float = 0.9
    peaking_n: float = 1.0
    peaking_t: float = 1.5
    #: ★Both of these were implicit defaults buried in the physics functions
    #: (``profile``'s ``edge_frac``, ``loop_voltage_ohmic``'s ``li``).  The
    #: kernel takes ten scalars and takes them all explicitly, so carrying
    #: them here is what makes the scenario a complete statement of the run
    #: rather than a partial one topped up by two function defaults.
    edge_frac: float = 0.05
    li: float = 0.9
    r0: float = 1.85
    a: float = 0.45
    kappa: float = 1.8
    zeff: float = 1.8
    dt_fraction: float = 0.5
    #: The auxiliary heating actuators, one per SYSTEM.
    #:
    #: ★★``ic`` is here even though no kernel channel deposits it yet
    #: (`FEATURE.md` §3.4: ICRH / ECRH are the two systems this package has
    #: no deposition model for).  It is here BECAUSE of that: without the
    #: name, a discharge with 2 MW of ICRF had to declare it as ``nbi`` or
    #: ``lh`` to reach ``p_inj`` at all, and the 0-D total came out right
    #: while the attribution came out wrong — the one error a total cannot
    #: show.  A name with no model behind it is a gap that stays visible;
    #: a wrong name is a gap that hides.
    #:
    #: ★The 0-D layer sums all four: at this tier the energy balance takes
    #: the injected power and nothing else, so the split is bookkeeping, not
    #: physics.  What ``ic`` does NOT do is deposit — see
    #: `docs/note/icrh-ecrh-gap.md` for what would have to land
    #: first, and what it would be judged by.
    nbi: Waveform = field(default_factory=Waveform)
    ic: Waveform = field(default_factory=Waveform)
    ec: Waveform = field(default_factory=Waveform)
    lh: Waveform = field(default_factory=Waveform)


def _zerod_plan(scn: Scenario, t, n_rho: int, *, extra: dict | None = None) -> dict:
    """The plan for ``code/zerod``: the phase table and the flat-tops as
    settings (the kernel builds the three centre waveforms on the bound time
    base — the same trapezoids, the same 2 % / 1 % residuals), the actuators
    summed here and bound under ``summary/p_aux``."""
    ph = scn.phases
    p_inj = scn.nbi.at(t) + scn.ic.at(t) + scn.ec.at(t) + scn.lh.at(t)
    settings = {"t_bd": float(ph.t_breakdown), "t_ru": float(ph.t_rampup_end),
                "t_ft": float(ph.t_flattop_end), "t_end": float(ph.t_end),
                "ip": float(scn.ip_flattop) / 1e3, "ne": float(scn.ne_flattop) / 1e19,
                "te": float(scn.te_flattop), "n_rho": float(n_rho),
                "tite": float(scn.ti_over_te), "pn": float(scn.peaking_n),
                "pt": float(scn.peaking_t), "edge_frac": float(scn.edge_frac),
                "r0": float(scn.r0), "a": float(scn.a), "kappa": float(scn.kappa),
                "zeff": float(scn.zeff), "li": float(scn.li), "dtf": float(scn.dt_fraction)}
    settings.update(extra or {})
    return {"settings": settings,
            "inputs": {"summary": {"time": np.asarray(t, float),
                                   "heating_current_drive": {"power_additional": {"value": np.asarray(p_inj, float)}}}}}


def _read_evaluate(rec: dict, scn: Scenario, t, n_rho: int) -> dict:
    arr = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    sm = rec["fields"]["summary"]
    cp = rec["fields"]["core_profiles"]
    nt = t.size
    #: the SUMMARY rows end in `/value` (the DD's spelling): `fusion/power/value`
    p_alpha = np.asarray(sm["fusion"]["power"]["value"]["data"], float)
    p_neutron = np.asarray(sm["fusion"]["neutron_power_total"]["value"]["data"], float)
    codes = arr("phase")
    labels = [K.PHASE_NAMES[int(c)] if np.isfinite(c) and 0 <= int(c) < len(K.PHASE_NAMES) else "" for c in codes]
    return {"t": t, "rho": np.linspace(0.0, 1.0, n_rho),
            "ip": np.asarray(sm["global_quantities"]["ip"]["value"]["data"], float),
            "v_loop": np.asarray(sm["global_quantities"]["v_loop"]["value"]["data"], float),
            "p_fus": p_alpha + p_neutron, "p_alpha": p_alpha,
            "p_inj": np.asarray(sm["heating_current_drive"]["power_additional"]["value"]["data"], float),
            "q": np.asarray(sm["global_quantities"]["fusion_gain"]["value"]["data"], float),
            "ne": np.asarray(cp["profiles_1d"]["electrons"]["density"]["data"], float).reshape(nt, n_rho),
            "te": np.asarray(cp["profiles_1d"]["electrons"]["temperature"]["data"], float).reshape(nt, n_rho) / 1e3,
            "ti": np.asarray(cp["profiles_1d"]["t_i_average"]["data"], float).reshape(nt, n_rho) / 1e3,
            "phase": labels,
            "volume": float(rec["facts"]["volume"]["value"])}


def evaluate(scn: Scenario, time=None, n_rho: int = 41) -> dict:
    """Time traces + per-slice profiles for a prescribed scenario.

    Returns Ip, V_loop, P_fus, P_alpha, P_inj and Q on the time grid, the
    prescribed n_e / T_e / T_i profiles per slice, and the phase label of
    each slice.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the sixth tool to sink): ONE knock on the
    document door (``code/zerod``).  It used to be one flat kernel call
    preceded by three waveform calls and followed by a label call; the
    waveforms are the kernel's to build from the phase table now, and the
    labels come back with the record.  ``Q`` is NaN where nothing is
    injected — 0 would read as "no gain" rather than "undefined".
    """
    from ...io import fydoc
    ph = scn.phases
    t = (np.linspace(ph.t_breakdown, ph.t_end, 120) if time is None
         else np.asarray(time, float))
    rec = fydoc.complete("code/zerod", _zerod_plan(scn, t, n_rho))
    return _read_evaluate(rec, scn, t, n_rho)


def zerod(scn: Scenario | None = None, *, time=None, n_rho: int = 41,
          predict: bool = False, law: str = "ipb98y2",
          h_factor: float = 1.0, bt: float = 0.0, m_eff: float = 2.5,
          w0: float = 0.0, **overrides) -> dict:
    """A prescribed discharge, evaluated (default) or predicted.

    ``predict=False`` — the four phases, the waveforms and the profiles the
    user prescribed, with ``V_loop`` / ``P_fus`` / ``P_alpha`` / ``Q``
    following analytically.  ★``Q`` is not a prediction: the density and
    temperature it divides are inputs.

    ``predict=True`` — the energy balance ``dW/dt = P_heat - W/tau_E`` is
    SOLVED with the named confinement scaling, and the temperature is a
    result.  ★The two must not be read side by side unlabelled; nothing in
    the numbers distinguishes them, which is why the tier is recorded in the
    result and in its provenance — and why the kernel's record says
    ``predicted`` itself.
    """
    from ...io import fydoc
    if isinstance(overrides.get("phases"), dict):
        overrides["phases"] = Phases(**overrides["phases"])
    for act in ("nbi", "ic", "ec", "lh"):
        if isinstance(overrides.get(act), dict):
            overrides[act] = Waveform(**overrides[act])
    scn = Scenario(**overrides) if scn is None else scn
    ph = scn.phases
    t = (np.linspace(ph.t_breakdown, ph.t_end, 120) if time is None
         else np.asarray(time, float))
    extra = {}
    if predict:
        extra = {"predict": 1.0, "tau_law": law, "hfac": float(h_factor), "meff": float(m_eff),
                 "bt": float(bt), "w0": float(w0)}
    rec = fydoc.complete("code/zerod", _zerod_plan(scn, t, n_rho, extra=extra))
    out = _read_evaluate(rec, scn, t, n_rho)
    out["tier"] = "prescribed"
    if predict:
        arr = lambda k: np.asarray(rec["fields"]["prediction_" + k]["data"], float)  # noqa: E731
        out["prediction"] = {k: arr(k) for k in
                             ("w_th", "tau_e", "te0", "p_ohm", "p_alpha", "p_heat", "p_lh", "balance")}
        out["tier"] = "predicted"
        assert float(rec["facts"]["predicted"]["value"]) == 1.0
    out["provenance"] = provenance("zerod", tier=out["tier"],
                                   law=law if predict else None)
    return out


def transport(*, rho=None, n_rho: int = 41, vprime=None, source=None,
              metric=None, velocity=None, d_pc: float = 0.0,
              power: float = 4.0, width: float = 0.35,
              y_init=None, edge_value: float = 0.3, closure: str = "constant",
              chi0: float = 1.0, p1: float = 0.25, p2: float = 1.75,
              dt: float = float("inf"), theta: float = 1.0,
              steps: int = 1, relax: float = 1.0, relax_coeff: float = 1.0,
              tol: float = 1e-10, max_inner: int = 200, neo=None,
              chi_given=None, b0: float | None = None, ne_axis: float | None = None,
              ne_peaking: float = 0.0, a: float | None = None, rmaj: float | None = None,
              kappa: float = 1.0, delta: float = 0.0, q95: float | None = None) -> dict:
    """Fixed-geometry 1.5-D core transport: advance or solve one channel.

    ``dt = inf`` with ``steps = 1`` is the steady solve — the well-posed use
    of the prescribed closures.  ★The neoclassical closure is different in
    kind: Chang-Hinton's chi falls with temperature, so this operating point
    has no steady state the iteration can approach (measured: singular
    undamped, negative temperatures under-relaxed).  It is therefore
    ADVANCED in time with a finite ``dt`` and a bounded number of ``steps``,
    and a run that reaches the cap reports ``settled = False`` rather than
    handing back where it happened to be.

    The geometry is PRESCRIBED here — that is the reduced tier.  ``coupled``
    is the tool that takes it from a solved equilibrium.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the seventh tool to sink): the outer
    march — the steps, the settle rule, the history — is
    ``case.rs::transport_case`` (``code/transport``) now.  This function
    binds the grid, the geometry, the source, the start, the convection and
    a given diffusivity on the declared rows, names the closure, and reads
    the record back.  ★The neoclassical closure is on the door too (the
    same day): its per-surface blocks are built in the kernel from the bar's
    Miller shape (``a`` · ``rmaj`` · ``kappa`` · ``delta`` · ``q95``), the field
    ``b0`` and the density ``ne_axis`` (with ``ne_peaking``); a caller that
    still hands ``neo`` blocks is refused, because there is one builder now.
    """
    from ...io import fydoc
    if neo is not None:
        from ... import kernel as _K
        raise _K.KernelError("the per-surface neo blocks are the kernel's now (`code/transport`, closure "
                             "'neoclassical'): pass b0 / ne_axis / ne_peaking and the bar's Miller shape "
                             "(a · rmaj · kappa · delta · q95) instead of blocks")
    if closure == "neoclassical" and (b0 is None or ne_axis is None or rmaj is None or q95 is None):
        from ... import kernel as _K
        raise _K.KernelError("closure 'neoclassical' needs the field and the density the surfaces are built "
                             "on: b0 [T], ne_axis [m^-3] (with ne_peaking), and the Miller shape rmaj (R0/a), "
                             "q95, kappa, delta")
    if closure == "given" and chi_given is None:
        from ... import kernel as _K
        raise _K.KernelError("closure 'given' needs chi_given")
    x = np.linspace(0.0, 1.0, int(n_rho)) if rho is None else np.asarray(rho, float)
    n = x.size
    if n < 3:
        raise ValueError("the transport grid needs at least three points")
    vp = np.maximum(x, 1e-6) * 2.0 if vprime is None else np.asarray(vprime, float)
    #: the source and the start are the KERNEL's defaults when not given — the
    #: Gaussian `P exp(-(x/w)^2)` and `edge + 2 (1 - x^2)` through its own
    #: profile family — and come back on the record
    inputs = {"fylite:rho": x, "fylite:vprime": vp}
    if source is not None:
        inputs["fylite:source"] = np.asarray(source, float)
    if y_init is not None:
        y = np.asarray(y_init, float).copy()
        if y.ndim == 2:
            #: ★a time-series profile handed in as the start (a 0-D run's `te`, (nt, nr))
            #: means its LAST slice — the state that series ended at.  The flat
            #: operator used to read the first n values of the flattened array, i.e.
            #: the first slice, silently; the door refuses a wrong length, so the
            #: choice is made here, once, and said.
            y = y[-1].copy()
        if y.size != n:
            raise ValueError(f"y_init has {y.size} points, the grid {n}")
        inputs["fylite:y_init"] = y
    if metric is not None:
        inputs["fylite:metric"] = np.asarray(metric, float)
    if velocity is not None:
        inputs["fylite:velocity"] = np.asarray(velocity, float)
    if chi_given is not None:
        inputs["fylite:chi_given"] = np.asarray(chi_given, float)
    settings = {"closure": str(closure), "chi0": float(chi0), "p1": float(p1), "p2": float(p2),
                "power": float(power), "width": float(width),
                "edge": float(edge_value), "dpc": float(d_pc), "theta": float(theta),
                "steps": float(max(int(steps), 1)), "relax": float(relax),
                "relax_coeff": float(relax_coeff), "tol": float(tol), "max_inner": float(max_inner)}
    if np.isfinite(dt):
        settings["dt"] = float(dt)
    #: ★the neoclassical tier's surfaces (2026-09-05): the bar's Miller shape,
    #: the field and the density, built in the kernel from these — the page's
    #: `neoBlocks` and this face hand over the same seven numbers
    for key, val in (("b0", b0), ("ne_axis", ne_axis), ("nepeak", ne_peaking if closure == "neoclassical" else None),
                     ("amin", a), ("rmaj", rmaj), ("q95", q95)):
        if val is not None:
            settings[key] = float(val)
    if closure == "neoclassical":
        settings.update({"kappa": float(kappa), "delta": float(delta)})
    rec = fydoc.complete("code/transport", {"settings": settings, "inputs": {"transport": inputs}})
    f = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    arr = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    hist = [{"step": i + 1, "change": float(c), "inner_iterations": int(it), "converged": bool(cv),
             "residual": float(r), "axis": float(ax)}
            for i, (c, it, cv, r, ax) in enumerate(zip(arr("history_change"), arr("history_inner_iterations"),
                                                       arr("history_converged"), arr("history_residual"),
                                                       arr("history_axis")))]
    return {"rho": x, "y": arr("y"), "vprime": vp, "source": arr("source"),
            "steps": int(f("steps")), "settled": bool(f("settled")), "history": hist,
            "inner_iterations": int(f("inner_iterations")),
            "converged": bool(f("converged")), "residual": f("residual"),
            "provenance": provenance("transport", closure=closure,
                                     steady=not np.isfinite(dt))}


# --------------------------------------------------------------------------- #
# 1.5-D, time-marching (the browser's 含时演化 bar) — BY THE KERNEL
# --------------------------------------------------------------------------- #
def evolve(*, a: float, r0: float, b0: float,
           te_axis: float, ti_axis: float, ne_axis: float,
           edge_te: float, edge_ti: float, edge_ne: float,
           n_rho: int = 41, kappa: float = 1.0, delta: float = 0.0,
           q95: float = 3.0, peaking_t: float = 1.5,
           peaking_n: float = 0.5,
           chi0: float = 1.0, chi_ratio: float = 1.0, d_pc: float = 0.0,
           p_e: float = 0.0, p_i: float = 0.0,
           dep_centre: float = 0.0, dep_width: float = 0.3,
           dt: float = 2e-3, n_steps: int = 60, dt_target: float = 0.02,
           brem: bool = True, bulk: str = "D",
           impurity: str | None = None, imp_conc: float = 0.0,
           imp_z: float = 0.0,
           alpha: bool = False, dt_fraction: float = 0.5,
           zeff: float = 1.5,
           pedestal: bool = False, ip: float = 0.0,
           current: bool = False, ohmic: bool = False,
           bootstrap: bool = False, v_loop: float = 0.0,
           sawtooth: bool = False, saw_mix: float = 1.0,
           saw_period: float = 0.0,
           chi_e_profile=None, chi_i_profile=None,
           equilibrium=None, n_surfaces: int | None = None,
           edge_psin: float = 0.95, reference=None,
           i_cd: float = 0.0, cd_centre: float = 0.4,
           cd_width: float = 0.2,
           density: bool = False, d_over_chi: float = 0.5, pinch: float = 0.0,
           fuel: float = 0.0, fuel_centre: float = 1.0, fuel_width: float = 0.25,
           quasi: bool = False, d_over_chi_z: float | None = None,
           pinch_z: float | None = None, fuel_z: float = 0.0,
           momentum: bool = False, prandtl: float = 1.0,
           torque: float = 0.0, closure: str = "constant",
           wave: dict | None = None, ipctl: bool = False,
           ip_kp: float = 0.0, ip_ki: float = 0.0,
           nbi: dict | None = None, lh_antennas: dict | None = None,
           executors: dict | None = None, turb: dict | None = None,
           couple: dict | None = None, fm: dict | None = None) -> dict:
    """March the heat channel in time — BY THE KERNEL (``code/evolve``).

    ★2026-09-05 第十九刀: ``couple`` runs the DEVICE tier's equilibrium
    alternation — the page's coupled block.  The start is ``code/refit`` with
    ``fit: 0`` (one free-boundary solve on the device's coils at the channel
    currents, the ladder traced off it); then blocks of ``every`` steps of
    ``code/evolve`` on that ladder, and between blocks ``code/refit`` with
    ``fit: 1``: the transport pressure's shape fitted to the analytic current
    family (``evFitShape``), the pressure amplitude ``beta0`` moved by the ratio
    of the two beta_p (the march's against the previous equilibrium's own,
    under-relaxed by ``relax``), a new free solve, the ladder re-traced, the
    state remapped by psi_N, the flux rebuilt in the march's gauge and the old
    V' handed to the next block's first step (``vprime_old``).  This function
    keeps the CADENCE only.  ``couple = {every, aturns, ip, beta0, emp, enp,
    r0, relax, device, limiter, max_iter, gs_relax, gs_tol, fb_gain, n_theta}``
    (``aturns`` and ``ip`` required; ``r0`` the profile family's reference
    radius; ``device`` a device document, default the bundled one).  With
    ``couple`` the geometry arguments and ``equilibrium`` are not read: the
    ladder is the solve's, ``n_rho`` its node count, ``edge_psin`` its edge.
    The answer's ``rounds`` is one record per block (``block, steps, settled,
    beta0, fit, bp_target, bp_eq, bp_fix, free, refined, refine_why``),
    ``free_solves`` every solve's verdict (block 0 first).  ★第二十刀:
    ``fixed=True`` (with ``deg_p`` / ``deg_f``, default 3) adds the page's
    fixed-boundary refinement to each alternation — the plasma source replaced
    by p' and FF' as polynomials of the transport's own pressure on a sub-box
    whose border is the free solve's, held to its own zero test; a refinement
    that fails is REPORTED (``refine_why``) and the family's answer stands.  The
    turbulent closure is not combined with ``couple`` in this tool (the page
    combines them).

    ★2026-09-05 第二十一刀: ``closure="flux-match"`` does not march — it is the
    page's T-C13 tier, a root find for the gradient vector (a/L_Te, a/L_Ti at
    ``n_rad`` match radii) at which the model flux equals the power crossing
    each surface, by the kernel's own Newton machine.  TGLF lives in the
    extension, so the match is a conversation across two doors and this
    function keeps the cadence only: ``code/evolve`` with ``stage: start``
    hands back the state at x0, the extension's ``code/turbulence`` (at the
    match radii) gives chi there, ``stage: eval`` feeds the machine and asks
    for the next state, and so on until the machine is done and ``stage:
    finish`` writes the record.  ``fm = {n_rad, rho_min, iter, tol, dx,
    dx_max, n_ky, outer, o_tol, o_relax}`` (defaults 6 · 0.3 · 8 · 0.01 · 0.05
    · 1 · 8 · 1 · 0.02 · 1).  With ``outer > 1`` the stationary outer loop
    (T-C14) runs: after each match the current half (``code/steady_current``:
    the steady flux at the matched profiles with the loop voltage found by
    secant on the enclosed current, the sawtooth it may allow) and — with
    ``couple`` given — the equilibrium half (``code/refit``, the ladder
    re-traced and the state remapped), until the pressure and q move by less
    than ``o_tol`` between rounds.  The answer is the matched state with the
    match record (``match``), the rounds (``stationary``) and the closure at
    the matched state; there is no time axis (``t`` is empty).

    ★2026-09-05 第十八刀: ``closure="turbulent"`` marches on the neoclassical
    chi_i plus a TGLF-derived one.  TGLF lives in the EXTENSION library, so
    the extension's own door (``code/turbulence``, ``fylite_ext_fyo_tree``)
    evaluates the page's ``turbulentChi`` — the surface blocks from the ladder
    and the state, ``n_rad`` sampled radii, ``n_ky`` log-spaced ky, one
    quasilinear flux each, chi in gyro-Bohm units interpolated onto the
    ladder, relaxed by ``relax`` against the previous answer — and this
    function keeps the page's CADENCE only: the door on the initial state
    (``probe``), then blocks of ``every`` steps with the answer bound as
    ``chi_turb``, the door again on the state each block ended with.
    ``turb = {every, n_rad, n_ky, relax, sat_rule, width}`` (defaults 2 · 6 ·
    8 · 1 · 1 · 1.65).  The answer's ``chi_turb`` is the last evaluation,
    ``turb_evals`` how many there were; the traces are stitched across blocks.

    ★2026-09-05 第十七刀: the two executors run INSIDE the march.  ``nbi`` is
    the DD's ``nbi`` document (``{"unit": [...]}``, the shape ``model.nbi.deposit``
    takes) and ``lh_antennas`` the ``{"antenna": [...]}`` document; the kernel
    evaluates ``code/beam`` / ``code/wave`` ONCE on the initial state at the
    ladder's own psi_N, remaps the shell deposition onto the ladder
    conservatively (the page's T-M14 rule), and marches on it: with a beam the
    aux powers, the torque and the driven current are the beam's (``p_e`` ·
    ``p_i`` · ``torque`` · ``i_cd`` are inert), the fast-ion trace third rides on
    beta_N; the wave's electron deposition and current ride on top.  Both need
    the psi map, so the Miller tier refuses them by name — pass ``equilibrium``.
    ``executors`` are the two cases' own settings in one map (``beam_shells`` ·
    ``stopping_model`` · ``n_samples`` · ``n_width_r`` · ``n_width_z`` ·
    ``orbit_losses`` · ``impurity_form``; ``eta_cd`` · ``xi`` · ``upshift_min`` ·
    ``upshift_max`` · ``lh_shells`` · ``width_floor`` · ``cd_model``).  The answer
    carries ``p_aux`` / ``p_aux_beam`` / ``p_aux_lh`` per step, ``j_lh``, and the
    executors' whole records under ``beam`` / ``lh`` (``code/beam``'s and
    ``code/wave``'s own fields, ``p_outside_ladder`` beside them).

    ★2026-09-05 第十五刀: ``density=True`` marches the main-ion density beside
    the heat (a PRESCRIBED particle closure — ``D = d_over_chi * chi_e`` and a
    constant ``pinch`` [m/s] — with ``fuel`` [1/s] deposited on a Gaussian);
    ``quasi=True`` puts the named ``impurity`` INTO the quasi-neutrality: the
    main ion diluted by ``zeff`` (``ion_dilution``), the impurity a second ion
    channel with its own ``d_over_chi_z`` / ``pinch_z`` / ``fuel_z`` (defaults:
    the main ion's), and Z_eff a RESULT of the two species; ``momentum=True``
    advances the toroidal rotation beside the march (``chi_phi = prandtl *
    chi_i``, ``torque`` [N m] on the aux deposit, Dirichlet zero at the edge).
    ★第十六刀: ``closure="neoclassical"`` marches on Chang-Hinton's ion chi
    evaluated on the ladder's own surface rows (``chi_e = chi_i * chi_ratio``);
    ``wave={ramp, flat, end, start, end2, power, vloop, fuel, ip}`` multiplies
    the actuators by the kernel's trapezoid over the four phase times, per
    step; ``ipctl=True`` (with ``current=True``) closes a PI loop (``ip_kp``,
    ``ip_ki``) on the enclosed current's ratio to its own first reading and
    drives the loop voltage with it.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the ninth tool to sink).  This function
    used to be the ASSEMBLY around the one declared entry ``evolve_heat``: the
    Miller metric from four scalars through ``geo_surface``, or a traced ladder
    off an equilibrium document (``fyo.Ladder`` — |F|, |q|, the 2π gauge, the
    Miller rows in metres); the profile shapes; the reference start per channel
    (``useRef``); the given-chi pair; then ``K.scenario``.  Every one of those
    is ``case.rs::evolve`` now, spelled in SI beside the page's own units, and
    the kernel repository's ``test_evolve_code.py`` holds the door to the old
    recipe bit for bit.  What stays here is the PLAN and the argument contract.

    Scope is the entry's and is stated rather than implied — heat channel,
    constant closure, aux deposit, ADAS radiation (bulk + one prescribed
    impurity), D-T alpha in the prescribed tier, and (``pedestal=True``) the
    EPED1-NN pedestal driving the Dirichlet edge; ``current=True`` adds the
    poloidal-flux channel with its ohmic / bootstrap / driven-current drives
    and the sawtooth.  A discharge that wants the density channel, a beam, a
    wave or an evolving equilibrium is NOT this tool: those stay in the
    browser loop until their own batch sinks them, and `fylite cases --plan`
    names, per case, which one is missing.

    ``equilibrium`` (a document, a g-file path or dict) selects the TRACED
    tier: the metric is read off the flux map, ``a`` / ``r0`` / ``b0`` /
    ``kappa`` / ``delta`` / ``q95`` are not read at all, and the march can
    sawtooth because q is whatever the equilibrium has.  ``ip`` is PRESCRIBED
    and is read only by the pedestal (beta_N's denominator).

    ``te_axis`` / ``edge_te`` in eV, ``ne_axis`` in m^-3, ``p_e`` in W —
    SI in, SI out; the page's own keV / 1e19 / MW sliders are converted by
    whoever reads the page (`engine.cases`).
    """
    from ...io import fydoc
    from ... import fyo as _fyo

    #: the argument contract — the sentences a caller acts on, before the plan
    if sawtooth and not current:
        raise ValueError(
            "the sawtooth needs the current channel: its trigger is q(0) < 1 "
            "and q is a result only where current diffusion is solved — pass "
            "`current=True`, or drop the sawtooth")
    if (chi_e_profile is None) != (chi_i_profile is None):
        raise ValueError(
            "chi_e_profile and chi_i_profile come together or not at all: "
            "the given-profile closure replaces BOTH channels' diffusivity, "
            "and half a closure is a different model nobody named")
    if sawtooth and not (saw_mix > 0):
        raise ValueError(
            f"saw_mix must be positive (got {saw_mix!r}): the mixing radius "
            "is `saw_mix * r_1`, and there is no default for the same reason "
            "TGLF's `width` has none — it is the reader's model choice")
    if i_cd and not current:
        raise ValueError(
            f"a driven current of {i_cd:g} A needs the current channel: it "
            "is a non-inductive drive on the poloidal flux, and with "
            "`current=False` this entry does not solve for one")
    if (ohmic or bootstrap) and not current:
        drives = " and ".join(n for n, on in
                              (("ohmic", ohmic), ("bootstrap", bootstrap))
                              if on)
        raise ValueError(
            f"{drives} needs the current channel: both are drives on the "
            "poloidal flux, and with `current=False` this entry does not "
            "solve for one — pass `current=True`, or drop the drive")
    if pedestal and not (ip > 0):
        raise ValueError(
            "the EPED1-NN pedestal needs a plasma current: beta_N is "
            "normalised by a*B0/Ip, and this tier does not solve for Ip — "
            "pass the discharge's prescribed `ip`")
    if impurity and not (imp_z > 0):
        raise ValueError(
            f"impurity {impurity!r} needs its charge (imp_z): the "
            "bremsstrahlung term goes as Z^2, so a concentration without a "
            "charge radiates a plasma nobody asked for")
    if quasi and not impurity:
        raise ValueError(
            "quasi=True puts an impurity into the quasi-neutrality, so it "
            "needs one: pass `impurity=` (and its `imp_z`)")
    if closure not in ("constant", "neoclassical", "turbulent", "flux-match"):
        raise ValueError(
            f"closure {closure!r}: this tool marches on the constant, the "
            "neoclassical or the turbulent closure (the last through the "
            "extension's door between blocks), or solves the flux-match tier "
            "(closure='flux-match': a root find, not a march — see `fm`)")
    if closure == "flux-match":
        if density or momentum or current:
            raise ValueError(
                "the flux-match tier solves the heat channel alone: the density, "
                "momentum and current channels are the stationary outer loop's "
                "(fm={'outer': N}), not the match's")
        if wave:
            raise ValueError("the flux-match tier has no time axis: no actuator waveform")
    if couple is not None:
        for key in ("aturns", "ip"):
            if key not in couple:
                raise ValueError(
                    f"couple needs {key!r}: the alternation solves the free boundary "
                    "on the device's coils at the channel currents the run was "
                    "designed with, and normalises the current to ip")
        if closure == "turbulent":
            raise ValueError(
                "couple with the turbulent closure is not combined in this tool: "
                "run one or the other (the page combines them)")
    if ipctl and not current:
        raise ValueError(
            "ipctl=True needs the current channel: the loop drives the "
            "boundary flux rate and closes on the current read off psi")

    settings = {
        "geometry": "miller" if equilibrium is None else "gfile",
        "te_axis": float(te_axis), "ti_axis": float(ti_axis),
        "ne_axis": float(ne_axis), "edge_te": float(edge_te),
        "edge_ti": float(edge_ti), "edge_ne": float(edge_ne),
        "peaking_t": float(peaking_t), "peaking_n": float(peaking_n),
        "chi0": float(chi0), "chi_ratio": float(chi_ratio),
        "d_pc": float(d_pc), "p_e": float(p_e), "p_i": float(p_i),
        "dep_centre": float(dep_centre), "dep_width": float(dep_width),
        "dt": float(dt), "n_steps": float(max(1, int(n_steps))),
        "dt_target": float(dt_target), "brem": float(bool(brem)),
        "bulk": str(bulk), "impurity": str(impurity or ""),
        "imp_conc": float(imp_conc), "imp_z": float(imp_z),
        "alpha": float(bool(alpha)), "dt_fraction": float(dt_fraction),
        "zeff": float(zeff), "pedestal": float(bool(pedestal)),
        "ip_a": float(ip), "current": float(bool(current)),
        "ohmic": float(bool(ohmic)), "bootstrap": float(bool(bootstrap)),
        "v_loop": float(v_loop), "sawtooth": float(bool(sawtooth)),
        "saw_mix": float(saw_mix), "saw_period": float(saw_period),
        "i_cd_a": float(i_cd), "cd_centre": float(cd_centre),
        "cd_width": float(cd_width),
        "density": float(bool(density)), "d_over_chi": float(d_over_chi),
        "pinch": float(pinch), "fuel_rate": float(fuel),
        "fuel_centre": float(fuel_centre), "fuel_width": float(fuel_width),
        "quasi": float(bool(quasi)),
        "d_over_chi_z": float(d_over_chi if d_over_chi_z is None else d_over_chi_z),
        "pinch_z": float(pinch if pinch_z is None else pinch_z),
        "fuel_z_rate": float(fuel_z),
        "momentum": float(bool(momentum)), "prandtl": float(prandtl),
        "torque": float(torque),
        "closure": {"neoclassical": "2", "turbulent": "3", "flux-match": "4"}.get(closure, "0"),
        "wave": float(bool(wave)), "ipctl": float(bool(ipctl)),
        "ip_kp": float(ip_kp), "ip_ki": float(ip_ki),
        "beam": float(nbi is not None), "lh": float(lh_antennas is not None),
    }
    for k, v in (executors or {}).items():
        settings[k] = v if isinstance(v, str) else float(v)
    if wave:
        settings.update({"wave_ramp": float(wave["ramp"]), "wave_flat": float(wave["flat"]),
                         "wave_end": float(wave["end"]), "wave_start": float(wave.get("start", 0.0)),
                         "wave_end2": float(wave.get("end2", 0.0)),
                         "wave_power": float(bool(wave.get("power", True))),
                         "wave_vloop": float(bool(wave.get("vloop", False))),
                         "wave_fuel": float(bool(wave.get("fuel", False))),
                         "wave_ip": float(bool(wave.get("ip", False)))})
    inputs: dict = {}
    if couple is not None:
        #: the ladder tier's two shape scalars are what the page's sliders hand it
        #: (the ladder's own rows carry the traced shapes)
        settings.update({"geometry": "ladder", "edge_psin": float(edge_psin),
                         "n": float(max(5, int(n_rho))), "kappa": float(kappa), "delta": float(delta)})
    elif equilibrium is None:
        settings.update({"a": float(a), "r0": float(r0), "b0": float(b0),
                         "kappa": float(kappa), "delta": float(delta),
                         "q95": float(q95), "n": float(max(5, int(n_rho)))})
    else:
        settings["edge_psin"] = float(edge_psin)
        if n_surfaces is not None:
            settings["n_surfaces"] = float(n_surfaces)
        inputs["equilibrium"] = _fyo.as_equilibrium(equilibrium)
    if reference is not None:
        #: the table as the kernel reads it: its own radii, the channels it
        #: states (a blank cell is NaN and stays NaN — the kernel's rule fills
        #: that one point from the shape and names the channels it took)
        settings["reference"] = 1.0
        cp: dict = {"grid": {"rho_tor": np.asarray(reference["rho"], float)},
                    "electrons": {}}
        if "te" in reference:
            cp["electrons"]["temperature"] = np.asarray(reference["te"], float)
        if "ne" in reference:
            cp["electrons"]["density"] = np.asarray(reference["ne"], float)
        if "ti" in reference:
            cp["t_i_average"] = np.asarray(reference["ti"], float)
        inputs["core_profiles"] = {"profiles_1d": cp}
    if nbi is not None:
        inputs["nbi"] = nbi
    if lh_antennas is not None:
        inputs["lh_antennas"] = lh_antennas
    if chi_e_profile is not None:
        inputs["core_transport"] = {"model": [{"profiles_1d": {
            "electrons": {"energy": {"d": np.asarray(chi_e_profile, float)}},
            "total_ion_energy": {"d": np.asarray(chi_i_profile, float)}}}]}
    if closure == "flux-match":
        #: 第二十一刀 — a root find in stages, the extension's chi between them;
        #: its answer is a matched STATE, not a march, so it is shaped as one
        return _flux_match_answer(settings, inputs, fm or {}, couple=couple, quasi=quasi,
                                  geometry="device" if couple is not None else ("miller" if equilibrium is None else "ladder"))
    turb_evals, chi_turb, rounds, free_solves = 0, None, None, None
    if closure == "turbulent":
        rec, turb_evals, chi_turb = _turbulent_march(settings, inputs, turb or {},
                                                     momentum=momentum, quasi=quasi,
                                                     beam=nbi is not None, lh=lh_antennas is not None)
    elif couple is not None:
        rec, rounds, free_solves = _coupled_march(settings, inputs, couple, momentum=momentum, quasi=quasi,
                                                  wave_power=bool(wave) and bool(wave.get("power", True)))
    else:
        rec = fydoc.complete("code/evolve", {"settings": settings, "inputs": inputs})

    F = rec["fields"]
    arr = lambda k: np.asarray(F[k]["data"], float)  # noqa: E731
    fact = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    cp = F["core_profiles"]["profiles_1d"]
    lad = F["equilibrium"]["time_slice"]["profiles_1d"]
    sm = F["summary"]
    gq = sm["global_quantities"]
    steps = int(fact("steps"))
    geometry = "device" if couple is not None else ("miller" if equilibrium is None else "ladder")
    ref_used = tuple(k for k in ("te", "ti", "ne") if fact("ref_" + k) == 1.0)
    return {
        "rho": np.asarray(cp["grid"]["rho_tor"]["data"], float),
        "vprime": np.asarray(lad["dvolume_drho_tor"]["data"], float),
        "gm3": np.asarray(lad["gm3"]["data"], float), "geometry": geometry,
        "te": np.asarray(cp["electrons"]["temperature"]["data"], float),
        "ti": np.asarray(cp["t_i_average"]["data"], float),
        "ne": np.asarray(cp["electrons"]["density"]["data"], float),
        "te_init": arr("te_init"), "ti_init": arr("ti_init"),
        #: 第十五刀 — the composition and the two channels (None where off)
        "ni": np.asarray(cp["fylite:ion_density"]["data"], float),
        "zeff": np.asarray(cp["zeff"]["data"], float),
        "nz": (np.asarray(cp["fylite:impurity_density"]["data"], float)
               if quasi else None),
        "omega": (np.asarray(cp["rotation_frequency_tor_sonic"]["data"], float)
                  if momentum else None),
        "omega_axis": arr("omega_axis"),
        "dt_fraction_used": fact("dt_fraction_used"),
        "wave_k": arr("wave_k"), "v_loop_used": arr("v_loop_used"),
        "ip_psi": arr("ip_psi"), "chi_neo": arr("chi_neo"),
        "t": np.asarray(sm["time"]["data"], float),
        "te_axis": np.asarray(sm["local"]["magnetic_axis"]["t_e"]["value"]["data"], float),
        "ti_axis": np.asarray(sm["local"]["magnetic_axis"]["t_i_average"]["value"]["data"], float),
        "dt_used": arr("dt_used"),
        "p_rad": np.asarray(gq["power_radiated"]["value"]["data"], float),
        "p_alpha": np.asarray(sm["fusion"]["power"]["value"]["data"], float),
        "beta_n": np.asarray(gq["beta_tor_norm"]["value"]["data"], float),
        "t_ped": arr("t_ped"), "balance": arr("balance"),
        "balance_worst": fact("balance_worst"),
        "ped_extrapolation": fact("ped_extrap"),
        "steps": steps, "settled": bool(fact("settled")),
        "dt_capped": int(fact("dt_capped")),
        "psi": arr("psi"), "j_bs": arr("j_bs"),
        "p_ohm": np.asarray(gq["power_ohm"]["value"]["data"], float),
        "q": arr("q"),
        "saw_r1": arr("saw_r1"), "saw_mixed": arr("saw_mixed"),
        "saw_refused": arr("saw_refused"), "saw_count": int(fact("saw_count")),
        "j_cd": arr("j_cd"),
        #: 第十七刀 — the auxiliary power the march put in, by executor; the
        #: wave's current; the executors' whole records where they ran
        "p_aux": arr("p_aux"), "p_aux_beam": arr("p_aux_beam"),
        "p_aux_lh": arr("p_aux_lh"), "j_lh": arr("j_lh"),
        "beam": F.get("beam"), "lh": F.get("lh"),
        #: 第十八刀 — the turbulent tier's last evaluation and the count
        "chi_turb": chi_turb, "turb_evals": turb_evals,
        #: 第十九刀 — the alternation's record per block, and every free solve
        "rounds": rounds, "free_solves": free_solves,
        "notes": list(rec.get("notes", [])),
        "provenance": provenance("evolve", closure="constant",
                                 channels=("heat", "current") if current
                                          else ("heat",),
                                 sawtooth="mixing" if sawtooth else None,
                                 geometry=geometry,
                                 reference_channels=ref_used,
                                 driven_current=(float(i_cd) if i_cd
                                                 else None),
                                 executors=tuple(k for k, v in (("nbi", nbi), ("lh", lh_antennas))
                                                 if v is not None) or None,
                                 turbulence=("tglf (extension door, blocks of %d)" % int((turb or {}).get("every", 2))
                                             if closure == "turbulent" else None),
                                 coupled=("code/refit between blocks of %d (free solve, pressure amplitude by beta_p)"
                                          % int((couple or {}).get("every", 1)) if couple is not None else None),
                                 pedestal="eped1nn" if pedestal else None,
                                 loop="kernel (evolve_heat)"),
    }


_TURB_DEFAULTS = {"every": 2, "n_rad": 6, "n_ky": 8, "relax": 1.0, "sat_rule": 1, "width": 1.65}

#: the per-step traces `code/evolve` reports, stitched across blocks (each cut at
#: the block's own `steps`); everything else the last block states
_TRACES = (("summary", "time"), ("summary", "local", "magnetic_axis", "t_e", "value"),
           ("summary", "local", "magnetic_axis", "t_i_average", "value"), ("summary", "fusion", "power", "value"),
           ("summary", "global_quantities", "power_radiated", "value"), ("summary", "global_quantities", "power_line", "value"),
           ("summary", "global_quantities", "power_ohm", "value"), ("summary", "global_quantities", "beta_tor_norm", "value"),
           ("dt_used",), ("balance",), ("t_ped",), ("saw_r1",), ("saw_mixed",), ("saw_refused",), ("omega_axis",),
           ("wave_k",), ("v_loop_used",), ("ip_psi",), ("ip_want",), ("ip_err",), ("p_aux",), ("p_aux_beam",), ("p_aux_lh",))


def _turbulent_march(settings: dict, inputs: dict, turb: dict, *, momentum: bool, quasi: bool,
                     beam: bool, lh: bool):
    """The page's cadence around the extension's door — see :func:`evolve`."""
    from ...io import fydoc

    t = {**_TURB_DEFAULTS, **turb}
    every = max(1, int(t["every"]))
    n_steps = int(settings["n_steps"])
    probe = fydoc.complete("code/evolve", {"settings": {**settings, "probe": 1.0}, "inputs": inputs})
    lad = probe["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
    ladder = {k: np.asarray(lad[k]["data"], float) for k in
              ("rho_tor", "fylite:r_minor", "fylite:r_major", "fylite:shift", "q", "magnetic_shear",
               "elongation", "triangularity_upper")}
    a, b0 = float(probe["facts"]["a"]["value"]), float(probe["facts"]["b0"]["value"])

    def state_of(rec):
        cp = rec["fields"]["core_profiles"]["profiles_1d"]
        st = {"te": np.asarray(cp["electrons"]["temperature"]["data"], float),
              "ne": np.asarray(cp["electrons"]["density"]["data"], float),
              "ti": np.asarray(cp["t_i_average"]["data"], float),
              "ni": np.asarray(cp["fylite:ion_density"]["data"], float)}
        if momentum and "rotation_frequency_tor_sonic" in cp:
            st["omega"] = np.asarray(cp["rotation_frequency_tor_sonic"]["data"], float)
        if quasi and "fylite:impurity_density" in cp:
            st["nz"] = np.asarray(cp["fylite:impurity_density"]["data"], float)
        return st

    def door(st, prev):
        prof = {"grid": {"rho_tor": ladder["rho_tor"]},
                "electrons": {"temperature": st["te"], "density": st["ne"]},
                "t_i_average": st["ti"], "fylite:ion_density": st["ni"]}
        if "omega" in st:
            prof["rotation_frequency_tor_sonic"] = st["omega"]
        plan = {"settings": {"a": a, "b0": b0, "n_rad": float(t["n_rad"]), "n_ky": float(t["n_ky"]),
                             "sat_rule": float(t["sat_rule"]), "width": float(t["width"]), "relax": float(t["relax"])},
                "inputs": {"equilibrium": {"time_slice": {"profiles_1d": ladder}},
                           "core_profiles": {"profiles_1d": prof}}}
        if prev is not None:
            plan["inputs"]["evolve"] = {"fylite:chi_turb": prev}
        rec = fydoc.complete("code/turbulence", plan)
        return np.asarray(rec["fields"]["chi_turb"]["data"], float)

    arr = lambda rec, k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    chi = door(state_of(probe), None)
    evals, prev, blocks, left = 1, None, [], n_steps
    while left > 0:
        st_plan = dict(settings, n_steps=float(min(every, left)))
        inp = dict(inputs)
        if prev is not None:
            fc = prev["facts"]
            st_plan.update({"resume": 1.0, "state": 1.0, "t_start": fc["t_end"]["value"], "dt_start": fc["dt_next"]["value"],
                            "edge_te_in": fc["edge_te_out"]["value"], "edge_ti_in": fc["edge_ti_out"]["value"],
                            "capped_in": fc["dt_capped"]["value"], "saw_elapsed_in": fc["saw_elapsed_out"]["value"],
                            "dt_fraction_in": fc["dt_fraction_used"]["value"],
                            "ipctl_ratio0_in": fc["ipctl_ratio0_out"]["value"], "ipctl_integral_in": fc["ipctl_integral_out"]["value"],
                            "ipctl_calibrated_in": fc["ipctl_calibrated_out"]["value"]})
            st = state_of(prev)
            prof = {"grid": {"psi": arr(prev, "psi")},
                    "electrons": {"temperature": st["te"], "density": st["ne"]},
                    "t_i_average": st["ti"], "fylite:ion_density": st["ni"]}
            if "omega" in st:
                prof["rotation_frequency_tor_sonic"] = st["omega"]
            if "nz" in st:
                prof["fylite:impurity_density"] = st["nz"]
            inp["core_profiles"] = {"profiles_1d": prof}
            carried = {"fylite:psi_prev": arr(prev, "psi_prev_out"), "fylite:sigma_prev": arr(prev, "sigma_prev_out"),
                       "fylite:exch_prev": arr(prev, "exch_prev_out")}
            if beam:
                carried.update({f"fylite:{k}": arr(prev, k) for k in
                                ("beam_e", "beam_i", "beam_torque", "beam_j", "beam_p_par", "beam_p_perp")})
            if lh:
                carried.update({f"fylite:{k}": arr(prev, k) for k in ("lh_e", "lh_j")})
        else:
            carried = {}
        carried["fylite:chi_turb"] = chi
        inp["evolve"] = carried
        rec = fydoc.complete("code/evolve", {"settings": st_plan, "inputs": inp})
        blocks.append(rec)
        left -= int(rec["facts"]["steps"]["value"])
        prev = rec
        if float(rec["facts"]["settled"]["value"]) != 0.0 or left <= 0:
            break
        chi = door(state_of(rec), chi)
        evals += 1
    #: the stitched record: the last block's fields, the traces concatenated
    import copy as _copy
    out = _copy.deepcopy(blocks[-1])

    def node(rec, path):
        n = rec["fields"]
        for p in path:
            n = n[p]
        return n
    for path in _TRACES:
        try:
            parts = [np.asarray(node(b, path)["data"], float)[:int(b["facts"]["steps"]["value"])] for b in blocks]
        except KeyError:
            continue
        node(out, path)["data"] = np.concatenate(parts)
    out["facts"]["steps"]["value"] = float(sum(int(b["facts"]["steps"]["value"]) for b in blocks))
    out["facts"]["saw_count"]["value"] = float(sum(int(b["facts"]["saw_count"]["value"]) for b in blocks))
    out["facts"]["dt_capped"]["value"] = float(sum(int(b["facts"]["dt_capped"]["value"]) for b in blocks))
    out["facts"]["balance_worst"]["value"] = max(float(b["facts"]["balance_worst"]["value"]) for b in blocks)
    out["facts"]["ped_extrap"]["value"] = max(float(b["facts"]["ped_extrap"]["value"]) for b in blocks)
    out["notes"] = [s for b in blocks for s in b.get("notes", [])]
    return out, evals, chi


_COUPLE_DEFAULTS = {"every": 1, "beta0": 0.55, "emp": 1.0, "enp": 1.0, "relax": 0.5}

#: the ladder rows `code/refit` states and `code/evolve`'s ladder tier binds
_LADDER_ROWS = ("rho_tor", "dvolume_drho_tor", "gm3", "gm7", "gm2", "f", "q", "fylite:r_minor", "fylite:r_major",
                "fylite:r2_average", "magnetic_shear", "elongation", "triangularity_upper", "fylite:shift",
                "fylite:psi_norm", "psi")


def _coupled_march(settings: dict, inputs: dict, couple: dict, *, momentum: bool, quasi: bool,
                   wave_power: bool):
    """The page's block cadence around `code/refit` — see :func:`evolve` (第十九刀)."""
    from ...io import fydoc
    from ..design import _device

    c = {**_COUPLE_DEFAULTS, **couple}
    every = max(1, int(c["every"]))
    n_steps = int(settings["n_steps"])
    dev = _device(c.get("device"))
    aturns = np.asarray(c["aturns"], float)
    fixed = {"ip": float(c["ip"]), "emp": float(c["emp"]), "enp": float(c["enp"]),
             "relax": float(c["relax"]), "n": float(settings["n"]), "edge_psin": float(settings["edge_psin"]),
             "n_theta": float(c.get("n_theta", 121)),
             "deg_p": float(c.get("deg_p", 3)), "deg_f": float(c.get("deg_f", 3))}
    refine = bool(c.get("fixed"))
    if "r0" in c:
        fixed["r0"] = float(c["r0"])
    for key in ("max_iter", "gs_relax", "gs_tol", "fb_gain", "b0", "r0_tf"):
        if key in c:
            fixed[key] = float(c[key])
    if c.get("limiter"):
        fixed["limiter"] = str(c["limiter"])
    if "b0" not in fixed or "r0_tf" not in fixed or "r0" not in fixed:
        #: the vacuum field off the device document — the page's `tf: {r0, b0}`
        #: (`FyDevice.tf`), else the deck's `machine/r_centre` and the TF coil's
        #: `b_field_tor_vacuum_r` (B0 * R0) as `device.py` reads it
        tf = dev.get("tf") or {}
        mach = dev.get("machine") or {}
        r0_tf = tf.get("r0", mach.get("r_centre"))
        b0_tf = tf.get("b0")
        if b0_tf is None and (dev.get("tf") or {}).get("b_field_tor_vacuum_r") is not None and r0_tf:
            b0_tf = float(dev["tf"]["b_field_tor_vacuum_r"]) / float(r0_tf)
        if r0_tf is None or b0_tf is None:
            raise ValueError("couple needs the vacuum field: pass b0 and r0_tf, or a device document "
                             "with tf/{r0, b0} (or machine/r_centre and tf/b_field_tor_vacuum_r)")
        fixed.setdefault("b0", float(b0_tf))
        fixed.setdefault("r0_tf", float(r0_tf))
        fixed.setdefault("r0", float(r0_tf))
    arr = lambda rec, k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    fact = lambda rec, k: float(rec["facts"][k]["value"])  # noqa: E731

    def refit(beta0, fit, *, ladder=None, state=None, p_fast=None, eq_prev=None):
        st = dict(fixed, beta0=float(beta0), fit=float(fit), couple_fixed=float(bool(fit and refine)))
        inp = {"device": dev, "discharge": {"fylite:channel_aturns": aturns}}
        if fit:
            st["a"] = float(ladder["a"])
            inp["equilibrium"] = {"time_slice": {"profiles_1d": {
                "rho_tor": ladder["rho_tor"], "dvolume_drho_tor": ladder["dvolume_drho_tor"],
                "fylite:psi_norm": ladder["fylite:psi_norm"]}}}
            prof = {"electrons": {"temperature": state["te"], "density": state["ne"]},
                    "t_i_average": state["ti"], "fylite:ion_density": state["ni"]}
            if "omega" in state:
                prof["rotation_frequency_tor_sonic"] = state["omega"]
            if "nz" in state:
                prof["fylite:impurity_density"] = state["nz"]
            inp["core_profiles"] = {"profiles_1d": prof}
            if p_fast is not None:
                inp["evolve"] = {"fylite:p_fast_third": p_fast}
            if eq_prev is not None:
                #: the FREE solve's own p(psi_N), whichever equilibrium the march stood on
                inp["refit"] = {"fylite:eq_x": arr(eq_prev, "free_profile_x"), "fylite:eq_p": arr(eq_prev, "free_pres")}
        return fydoc.complete("code/refit", {"settings": st, "inputs": inp})

    def ladder_of(rec):
        lad = rec["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
        out = {k: np.asarray(lad[k]["data"], float) for k in _LADDER_ROWS}
        out["a"], out["r0"], out["b0"] = fact(rec, "a"), fact(rec, "r0"), fact(rec, "b0")
        return out

    def free_of(rec, block):
        return {"block": block, "converged": bool(fact(rec, "converged")), "settled": bool(fact(rec, "settled")),
                "residual": fact(rec, "residual"), "iterations": int(fact(rec, "iterations")),
                "max_iter": int(fact(rec, "max_iter")), "tol": fact(rec, "tol")}

    def state_of(rec):
        cp = rec["fields"]["core_profiles"]["profiles_1d"]
        st = {"te": np.asarray(cp["electrons"]["temperature"]["data"], float),
              "ne": np.asarray(cp["electrons"]["density"]["data"], float),
              "ti": np.asarray(cp["t_i_average"]["data"], float),
              "ni": np.asarray(cp["fylite:ion_density"]["data"], float)}
        if momentum and "rotation_frequency_tor_sonic" in cp:
            st["omega"] = np.asarray(cp["rotation_frequency_tor_sonic"]["data"], float)
        if quasi and "fylite:impurity_density" in cp:
            st["nz"] = np.asarray(cp["fylite:impurity_density"]["data"], float)
        return st

    beta0 = float(c["beta0"])
    eq = refit(beta0, 0)
    beta0 = fact(eq, "beta0")
    ladder = ladder_of(eq)
    free_solves = [free_of(eq, 0)]
    rounds, blocks = [], []
    prev, left, block = None, n_steps, 0
    while left > 0:
        block += 1
        st_plan = dict(settings, n_steps=float(min(every, left)),
                       a=ladder["a"], r0=ladder["r0"], b0=ladder["b0"])
        inp = dict(inputs)
        inp["equilibrium"] = {"time_slice": {"profiles_1d": {k: ladder[k] for k in _LADDER_ROWS}}}
        if prev is not None:
            fc = prev["facts"]
            st_plan.update({"resume": 1.0, "state": 1.0, "t_start": fc["t_end"]["value"], "dt_start": fc["dt_next"]["value"],
                            "edge_te_in": fc["edge_te_out"]["value"], "edge_ti_in": fc["edge_ti_out"]["value"],
                            "capped_in": fc["dt_capped"]["value"], "saw_elapsed_in": fc["saw_elapsed_out"]["value"],
                            "dt_fraction_in": fc["dt_fraction_used"]["value"],
                            "ipctl_ratio0_in": fc["ipctl_ratio0_out"]["value"], "ipctl_integral_in": fc["ipctl_integral_out"]["value"],
                            "ipctl_calibrated_in": fc["ipctl_calibrated_out"]["value"],
                            #: the first step after the alternation: the lagged pair dropped, the volume moved
                            "lag_reset": 1.0, "vprime_moved": 1.0})
            st = state_of(eq)
            prof = {"grid": {"psi": ladder["psi"]},
                    "electrons": {"temperature": st["te"], "density": st["ne"]},
                    "t_i_average": st["ti"], "fylite:ion_density": st["ni"]}
            if "omega" in st:
                prof["rotation_frequency_tor_sonic"] = st["omega"]
            if "nz" in st:
                prof["fylite:impurity_density"] = st["nz"]
            inp["core_profiles"] = {"profiles_1d": prof}
            n_new = ladder["rho_tor"].size
            ex = arr(prev, "exch_prev_out")
            ex_max = float(np.max(ex[np.isfinite(ex)])) if np.any(np.isfinite(ex)) else 0.0
            #: the exchange ceiling keeps the previous closure's fastest rate (the
            #: page reads its last closure unchanged across the alternation); the
            #: executors are evaluated afresh on the new psi map (no carried arrays)
            inp["evolve"] = {"fylite:psi_prev": np.zeros(n_new), "fylite:sigma_prev": np.zeros(n_new),
                             "fylite:exch_prev": np.full(n_new, ex_max), "fylite:vprime_old": arr(eq, "vprime_old")}
        rec = fydoc.complete("code/evolve", {"settings": st_plan, "inputs": inp})
        blocks.append(rec)
        took = int(rec["facts"]["steps"]["value"])
        left -= took
        settled = float(rec["facts"]["settled"]["value"]) != 0.0
        rounds.append({"block": block, "steps": n_steps - left, "settled": settled, "beta0": beta0,
                       "fit": None, "bp_target": float("nan"), "bp_eq": float("nan"), "bp_fix": float("nan"),
                       "free": None, "refined": None, "refine_why": None})
        prev = rec
        if settled or left <= 0:
            break
        #: the alternation on the state the block ended with
        st = state_of(rec)
        p_fast = None
        if "beam" in rec["fields"]:
            kp = float(arr(rec, "wave_k")[took - 1]) if wave_power else 1.0
            p_fast = (arr(rec, "beam_p_par") + 2.0 * arr(rec, "beam_p_perp")) / 3.0 * kp
        eq = refit(beta0, 1, ladder=ladder, state=st, p_fast=p_fast, eq_prev=eq)
        beta0 = fact(eq, "beta0")
        ladder = ladder_of(eq)
        free = free_of(eq, block)
        free_solves.append(free)
        fit = ({"emp": fact(eq, "fit_emp"), "enp": fact(eq, "fit_enp"), "rms": fact(eq, "fit_rms")}
               if fact(eq, "fit_found") else None)
        refined = None
        if refine and fact(eq, "fixed_ok"):
            refined = {k: fact(eq, f) for k, f in (("ip", "fixed_ip"), ("ip_target", "fixed_ip_target"),
                                                    ("res_p", "res_p"), ("res_f", "res_f"), ("deg_p", "deg_p"),
                                                    ("deg_f", "deg_f"), ("iterations", "fixed_iterations"),
                                                    ("residual", "fixed_residual"), ("zero_psi", "zero_psi"),
                                                    ("zero_ip_rel", "zero_ip_rel"), ("ff_shift", "fixed_ff_shift"))}
        why = None
        if refine and not fact(eq, "fixed_ok"):
            why = next((t[len("refine: "):] for t in eq.get("notes", []) if t.startswith("refine: ")), "the refinement failed")
        rounds[-1].update({"beta0": beta0, "fit": fit, "bp_target": fact(eq, "bp_target"),
                           "bp_eq": fact(eq, "bp_eq"), "bp_fix": fact(eq, "bp_fix"), "free": free,
                           "refined": refined, "refine_why": why})
    #: the stitched record: the last block's fields (on the last ladder), the traces concatenated
    import copy as _copy
    out = _copy.deepcopy(blocks[-1])

    def node(rec, path):
        n = rec["fields"]
        for p in path:
            n = n[p]
        return n
    for path in _TRACES:
        try:
            parts = [np.asarray(node(b, path)["data"], float)[:int(b["facts"]["steps"]["value"])] for b in blocks]
        except KeyError:
            continue
        node(out, path)["data"] = np.concatenate(parts)
    out["facts"]["steps"]["value"] = float(sum(int(b["facts"]["steps"]["value"]) for b in blocks))
    out["facts"]["saw_count"]["value"] = float(sum(int(b["facts"]["saw_count"]["value"]) for b in blocks))
    out["facts"]["dt_capped"]["value"] = float(sum(int(b["facts"]["dt_capped"]["value"]) for b in blocks))
    out["facts"]["balance_worst"]["value"] = max(float(b["facts"]["balance_worst"]["value"]) for b in blocks)
    out["facts"]["ped_extrap"]["value"] = max(float(b["facts"]["ped_extrap"]["value"]) for b in blocks)
    out["notes"] = [s for b in blocks for s in b.get("notes", [])]
    return out, rounds, free_solves


_FM_DEFAULTS = {"n_rad": 6, "rho_min": 0.3, "iter": 8, "tol": 0.01, "dx": 0.05, "dx_max": 1.0, "n_ky": 8,
                "outer": 1, "o_tol": 0.02, "o_relax": 1.0, "sat_rule": 1, "width": 1.65}

#: what the match carries between its stages, verbatim
_FM_CARRIED = ("fm_machine", "fm_x", "fm_w", "fm_scalars", "fm_alpha_e", "fm_alpha_i", "fm_alpha_total",
               "fm_hist_worst", "fm_hist_conv", "fm_hist_tped")


def _flux_match_once(settings: dict, inputs: dict, f: dict, state: dict | None, ladder_hint: dict | None):
    """One flux match: the stages of `code/evolve` with the extension's chi between them."""
    from ...io import fydoc

    arr = lambda rec, k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    fact = lambda rec, k: float(rec["facts"][k]["value"])  # noqa: E731
    base = dict(settings, closure="4", n_rad=float(f["n_rad"]), fm_rho_min=float(f["rho_min"]), fm_iter=float(f["iter"]),
                fm_tol=float(f["tol"]), fm_dx=float(f["dx"]), fm_dx_max=float(f["dx_max"]))
    inp = dict(inputs)
    if state is not None:
        base["state"] = 1.0
        prof = {"electrons": {"temperature": state["te"], "density": state["ne"]},
                "t_i_average": state["ti"], "fylite:ion_density": state["ni"]}
        if "psi" in state:
            prof["grid"] = {"psi": state["psi"]}
        inp["core_profiles"] = {"profiles_1d": prof}
    if ladder_hint is not None:
        inp["equilibrium"] = {"time_slice": {"profiles_1d": ladder_hint}}
    rec = fydoc.complete("code/evolve", {"settings": dict(base, stage="start"), "inputs": inp})
    lad = rec["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
    ladder = {k: np.asarray(lad[k]["data"], float) for k in
              ("rho_tor", "fylite:r_minor", "fylite:r_major", "fylite:shift", "q", "magnetic_shear",
               "elongation", "triangularity_upper")}
    a, b0 = fact(rec, "a"), fact(rec, "b0")
    radii = arr(rec, "fm_index")
    first = rec
    evals = 0

    def chi_at(rec):
        cp = rec["fields"]["core_profiles"]["profiles_1d"]
        prof = {"grid": {"rho_tor": ladder["rho_tor"]},
                "electrons": {"temperature": np.asarray(cp["electrons"]["temperature"]["data"], float),
                              "density": np.asarray(cp["electrons"]["density"]["data"], float)},
                "t_i_average": np.asarray(cp["t_i_average"]["data"], float),
                "fylite:ion_density": np.asarray(cp["fylite:ion_density"]["data"], float)}
        plan = {"settings": {"a": a, "b0": b0, "n_rad": float(f["n_rad"]), "n_ky": float(f["n_ky"]),
                             "sat_rule": float(f["sat_rule"]), "width": float(f["width"]), "relax": 1.0},
                "inputs": {"equilibrium": {"time_slice": {"profiles_1d": ladder}},
                           "core_profiles": {"profiles_1d": prof},
                           "turbulence": {"fylite:radii": radii}}}
        t = fydoc.complete("code/turbulence", plan)
        return np.asarray(t["fields"]["chi_turb"]["data"], float)

    guard = 0
    while True:
        carried = {f"fylite:{k}": arr(rec, k) for k in _FM_CARRIED}
        carried["fylite:chi_turb"] = chi_at(rec)
        evals += 1
        stage = "finish" if fact(rec, "fm_final") == 1.0 else "eval"
        plan_in = dict(inp, evolve=carried)
        rec = fydoc.complete("code/evolve", {"settings": dict(base, stage=stage), "inputs": plan_in})
        if fact(rec, "fm_phase") == 3.0:
            break
        guard += 1
        if guard > (2 + 4) * int(f["iter"]) + 80:
            raise RuntimeError("the flux match did not finish")
    return rec, first, evals


def _flux_match_answer(settings: dict, inputs: dict, fm: dict, *, couple: dict | None, quasi: bool, geometry: str) -> dict:
    """The flux-match tier's answer: the match, the stationary rounds, the matched state."""
    from ...io import fydoc

    f = {**_FM_DEFAULTS, **fm}
    outer = max(1, int(f["outer"]))
    arr = lambda rec, k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    fact = lambda rec, k: float(rec["facts"][k]["value"])  # noqa: E731
    settings = dict(settings)
    inputs = dict(inputs)
    #: the device tier: the start is `code/refit` with fit 0, the ladder its
    #: (第十九刀's rule, on this tier too)
    ladder_hint = None
    eq_prev = None
    beta0 = None
    dev = aturns = None
    if couple is not None:
        from ..design import _device
        c = {**_COUPLE_DEFAULTS, **couple}
        dev, aturns = _device(c.get("device")), np.asarray(c["aturns"], float)
        fixed = {"ip": float(c["ip"]), "emp": float(c["emp"]), "enp": float(c["enp"]), "relax": float(c["relax"]),
                 "n": float(settings["n"]), "edge_psin": float(settings["edge_psin"]), "n_theta": float(c.get("n_theta", 121))}
        for key in ("max_iter", "gs_relax", "gs_tol", "fb_gain", "b0", "r0", "r0_tf", "limiter"):
            if key in c:
                fixed[key] = c[key] if isinstance(c[key], str) else float(c[key])
        tf = dev.get("tf") or {}
        mach = dev.get("machine") or {}
        fixed.setdefault("r0_tf", float(tf.get("r0", mach.get("r_centre"))))
        fixed.setdefault("b0", float(tf.get("b0")))
        fixed.setdefault("r0", fixed["r0_tf"])
        beta0 = float(c["beta0"])
        eq_prev = fydoc.complete("code/refit", {"settings": dict(fixed, beta0=beta0, fit=0.0),
                                                "inputs": {"device": dev, "discharge": {"fylite:channel_aturns": aturns}}})
        beta0 = fact(eq_prev, "beta0")
        lad = eq_prev["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
        ladder_hint = {k: np.asarray(lad[k]["data"], float) for k in _LADDER_ROWS}
        settings.update({"a": fact(eq_prev, "a"), "r0": fact(eq_prev, "r0"), "b0": fact(eq_prev, "b0")})
    state = None
    rounds = []
    rec = first = None
    evals_total = 0
    converged_outer, why = False, None
    p_prev = q_prev = None
    ladder_rows = None
    for rnd in range(outer):
        rec, first, evals = _flux_match_once(settings, inputs, f, state, ladder_hint)
        evals_total += evals
        cp = rec["fields"]["core_profiles"]["profiles_1d"]
        state = {"te": np.asarray(cp["electrons"]["temperature"]["data"], float),
                 "ti": np.asarray(cp["t_i_average"]["data"], float),
                 "ne": np.asarray(cp["electrons"]["density"]["data"], float),
                 "ni": np.asarray(cp["fylite:ion_density"]["data"], float)}
        if "psi" in (state or {}):
            pass
        lad = rec["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
        ladder_rows = {k: np.asarray(v["data"], float) for k, v in lad.items() if isinstance(v, dict) and "data" in v}
        if not fact(rec, "fm_converged"):
            why = "match"
            break
        if outer <= 1:
            converged_outer = True
            break
        #: the current half, on the ladder the match sat on
        rho = ladder_rows["rho_tor"]
        need = ("dvolume_drho_tor", "gm3", "gm2", "f", "q", "fylite:r_minor", "fylite:r_major")
        if any(k not in ladder_rows for k in need):
            why = "current: the ladder carries no gm2 / f (the Miller tier has no flux to march)"
            break
        psi = state.get("psi")
        if psi is None:
            psi = ladder_rows.get("psi")
        if psi is None:
            why = "current: no initial flux on this ladder"
            break
        st_cur = {"a": settings["a"], "r0": settings["r0"], "b0": settings["b0"], "ip_a": float(settings.get("ip_a", 0.0)),
                  "zeff": settings.get("zeff", 1.5), "bootstrap": float(settings.get("bootstrap", 0.0)),
                  "quasi": float(quasi), "tol_steady": 1e-9, "n_coupling": 2.0,
                  "relax": float(f["o_relax"]), "first": float(rnd == 0), "sawtooth": float(settings.get("sawtooth", 0.0)),
                  "saw_mix": float(settings.get("saw_mix", 1.0)), "imp_z": float(settings.get("imp_z", 0.0))}
        cur_in = {"equilibrium": {"time_slice": {"profiles_1d": {k: ladder_rows[k] for k in ("rho_tor",) + need}}},
                  "core_profiles": {"profiles_1d": {"grid": {"psi": psi},
                                                    "electrons": {"temperature": state["te"], "density": state["ne"]},
                                                    "t_i_average": state["ti"], "fylite:ion_density": state["ni"]}}}
        if q_prev is not None:
            cur_in["evolve"] = {"fylite:q_prev": q_prev}
        cur = fydoc.complete("code/steady_current", {"settings": st_cur, "inputs": cur_in})
        cpc = cur["fields"]["core_profiles"]["profiles_1d"]
        state = {"te": np.asarray(cpc["electrons"]["temperature"]["data"], float),
                 "ti": np.asarray(cpc["t_i_average"]["data"], float),
                 "ne": np.asarray(cpc["electrons"]["density"]["data"], float),
                 "ni": np.asarray(cpc["fylite:ion_density"]["data"], float),
                 "psi": np.asarray(cpc["grid"]["psi"]["data"], float)}
        q_now = arr(cur, "q")
        p_now = (state["ne"] * state["te"] + state["ni"] * state["ti"]) * 1.602176634e-19
        eq_round = None
        if couple is not None:
            #: the equilibrium half: the alternation at this round's current
            ip_now = fact(cur, "ip")
            ip_use = ip_now if np.isfinite(ip_now) and abs(ip_now) > 0 else float(c["ip"])
            fixed_r = dict(fixed, ip=ip_use, beta0=beta0, fit=1.0, a=float(settings["a"]), fit_relax=float(f["o_relax"]),
                           emp=float(fact(eq_prev, "emp")), enp=float(fact(eq_prev, "enp")))
            eq = fydoc.complete("code/refit", {"settings": fixed_r, "inputs": {
                "device": dev, "discharge": {"fylite:channel_aturns": aturns},
                "equilibrium": {"time_slice": {"profiles_1d": {"rho_tor": rho, "dvolume_drho_tor": ladder_rows["dvolume_drho_tor"],
                                                               "fylite:psi_norm": ladder_rows["fylite:psi_norm"]}}},
                "core_profiles": {"profiles_1d": {"electrons": {"temperature": state["te"], "density": state["ne"]},
                                                  "t_i_average": state["ti"], "fylite:ion_density": state["ni"]}},
                "refit": {"fylite:eq_x": arr(eq_prev, "free_profile_x"), "fylite:eq_p": arr(eq_prev, "free_pres")}}})
            psin_old = ladder_rows["fylite:psi_norm"]
            lad2 = eq["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
            ladder_hint = {k: np.asarray(lad2[k]["data"], float) for k in _LADDER_ROWS}
            cp2 = eq["fields"]["core_profiles"]["profiles_1d"]
            state = {"te": np.asarray(cp2["electrons"]["temperature"]["data"], float),
                     "ti": np.asarray(cp2["t_i_average"]["data"], float),
                     "ne": np.asarray(cp2["electrons"]["density"]["data"], float),
                     "ni": np.asarray(cp2["fylite:ion_density"]["data"], float),
                     "psi": np.asarray(cp2["grid"]["psi"]["data"], float)}
            settings.update({"a": fact(eq, "a"), "r0": fact(eq, "r0"), "b0": fact(eq, "b0")})
            remap = lambda v: np.interp(ladder_hint["fylite:psi_norm"], psin_old, v)  # noqa: E731
            if p_prev is not None:
                p_prev = remap(p_prev)
            q_now = remap(q_now)
            p_now = remap(p_now)
            eq_round = {"a_old": float(fixed_r["a"]), "a_new": fact(eq, "a"), "beta0": fact(eq, "beta0"),
                        "bp_target": fact(eq, "bp_target"), "bp_eq": fact(eq, "bp_eq"), "ip_used": ip_use,
                        "free": {"converged": bool(fact(eq, "converged")), "residual": fact(eq, "residual"),
                                 "iterations": int(fact(eq, "iterations"))}}
            beta0 = fact(eq, "beta0")
            eq_prev = eq
        rel = lambda a2, b2: float(np.max(np.abs(a2 - b2)) / np.max(np.abs(b2))) if np.max(np.abs(b2)) > 0 else 0.0  # noqa: E731
        d_p = rel(p_now, p_prev) if p_prev is not None else float("nan")
        d_q = rel(q_now, q_prev) if q_prev is not None else float("nan")
        rounds.append({"round": rnd + 1, "d_pressure": d_p, "d_q": d_q, "q0": fact(cur, "q0"), "ip": fact(cur, "ip"),
                       "ip_requested": fact(cur, "ip_requested"), "v_loop": fact(cur, "v_loop"),
                       "v_loop_clamped": bool(fact(cur, "v_loop_clamped")),
                       "sawtooth": ({"r1": fact(cur, "saw_r1"), "r_mix": fact(cur, "saw_r_mix"), "refused": bool(fact(cur, "saw_refused"))}
                                    if fact(cur, "saw_r1") > 0 else None),
                       "match_iterations": int(fact(rec, "fm_iterations")), "match_worst": fact(rec, "fm_worst"),
                       "equilibrium": eq_round,
                       "equilibrium_skipped": None if couple is not None else "no free boundary on this tier"})
        p_prev, q_prev = p_now, q_now
        if rnd > 0 and d_p < f["o_tol"] and (np.isnan(d_q) or d_q < f["o_tol"]):
            converged_outer = True
            break
    F = rec["fields"]
    cp = F["core_profiles"]["profiles_1d"]
    match = {k: arr(rec, "fm_" + k) for k in ("radii", "rho_n", "psin", "index", "alte", "alti", "flux_e", "flux_i",
                                               "target_e", "target_i", "rel_e", "rel_i", "hist_worst", "hist_conv", "hist_tped")}
    match.update({"iterations": int(fact(rec, "fm_iterations")), "converged": bool(fact(rec, "fm_converged")),
                  "worst": fact(rec, "fm_worst"), "tol": float(f["tol"]), "evaluations": int(fact(rec, "fm_evals")),
                  "n_radii": int(fact(rec, "n_radii")), "burn_frozen": bool(fact(rec, "fm_burn_frozen")),
                  "burn_check": fact(rec, "fm_burn_check"), "weight_floor": fact(rec, "fm_weight_floor"),
                  "weight_ref": fact(rec, "fm_weight_ref")})
    return {
        "rho": np.asarray(cp["grid"]["rho_tor"]["data"], float),
        "te": np.asarray(cp["electrons"]["temperature"]["data"], float),
        "ti": np.asarray(cp["t_i_average"]["data"], float),
        "ne": np.asarray(cp["electrons"]["density"]["data"], float),
        "ni": np.asarray(cp["fylite:ion_density"]["data"], float),
        "psi": state.get("psi") if state else None,
        "chi_e": arr(rec, "chi_e"), "chi_i": arr(rec, "chi_i"), "chi_neo": arr(rec, "chi_neo"), "chi_turb": arr(rec, "chi_turb"),
        "zeff": arr(rec, "zeff"), "q_e": arr(rec, "q_e"), "q_i": arr(rec, "q_i"),
        "p_alpha": fact(rec, "p_alpha"), "p_rad": fact(rec, "p_rad"), "p_line": fact(rec, "p_line"), "p_aux": fact(rec, "p_aux"),
        "edge_te": fact(rec, "edge_te_out"), "edge_ti": fact(rec, "edge_ti_out"),
        "match": match,
        "stationary": ({"rounds": rounds, "converged": converged_outer, "why": why, "tolerance": float(f["o_tol"]),
                        "max_rounds": outer} if outer > 1 else None),
        "turb_evals": evals_total, "t": np.zeros(0), "steps": 0, "settled": bool(fact(rec, "fm_converged")),
        "geometry": geometry,
        "notes": list(rec.get("notes", [])),
        "provenance": provenance("evolve", closure="flux-match", channels=("heat",), geometry=geometry,
                                 match="Newton in gradient space (transport::FluxMatch), the burn Picard-frozen per iteration, the pedestal lagged one iteration",
                                 stationary=("%d rounds: match -> steady current -> %s" % (len(rounds), "equilibrium" if couple is not None else "no equilibrium half")
                                             if outer > 1 else None),
                                 loop="kernel (code/evolve stages + code/turbulence + code/steady_current)"),
    }


# --------------------------------------------------------------------------- #
# equilibrium <-> transport
# --------------------------------------------------------------------------- #
def coupled(*, aturns: list, ip: float, beta0: float = 0.55, emp: float = 1.0,
            enp: float = 1.0, r0: float = 1.85, n_outer: int = 5,
            n_rho: int = 41, n_theta: int = 121,
            power: float = 4.0, width: float = 0.35, chi0: float = 1.0,
            closure: str = "constant", edge_value: float = 0.3,
            t_ref: float = 2.0, relax: float = 0.5, tol: float = 1e-3,
            limiter: str | None = None, device=None, **solve_kw) -> dict:
    """Self-consistent alternation — BY THE KERNEL (``code/coupled``).

    Each outer round solves a free-boundary equilibrium from the channel
    currents, traces the metric ON THE FIELD IT JUST SOLVED, solves the
    temperature to steady on that metric, and moves ``beta0`` toward the
    volume-averaged temperature the transport solve produced.

    ★★The feedback is the pressure AMPLITUDE only.  The analytic profile
    takes ``(beta0, emp, enp)``; there is no entry for an arbitrary
    ``p(psi)``, so this loop can change how much pressure there is and not
    how it is distributed.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the tenth tool to sink): this was the
    last host-side assembly that solved a free boundary itself.  The loop —
    the solve, the trace, the steady step, the feedback — is
    ``case.rs::coupled_case`` now; the kernel repository's
    ``test_coupled_code.py`` holds the door to the old recipe bit for bit on
    the EAST reference discharge.  ``solve_kw`` are the solve's own
    ``max_iter`` · ``gs_relax`` · ``gs_tol`` · ``fb_gain``; ``limiter`` names
    a limiter unit of the device document (default: its first).

    ★What is between two outer rounds has not been solved.  ``history``
    therefore reports per round: the equilibrium's own iteration count and
    residual, the number of surfaces that traced, the transport solve's
    inner iterations, and the relative change in ``beta0`` — the quantities
    that say whether the loop settled or merely stopped.
    """
    from ...io import fydoc
    from ..design import _device
    known = {"max_iter", "gs_relax", "gs_tol", "fb_gain"}
    bad = set(solve_kw) - known
    if bad:
        raise TypeError(f"coupled() got unexpected solver settings {sorted(bad)}; "
                        f"the kernel takes {sorted(known)}")
    settings = {"ip": float(ip), "beta0": float(beta0), "emp": float(emp), "enp": float(enp),
                "r0": float(r0), "n_outer": float(max(1, int(n_outer))), "n_rho": float(n_rho),
                "n_theta": float(n_theta), "power": float(power), "width": float(width),
                "chi0": float(chi0), "closure": str(closure), "edge_value": float(edge_value),
                "t_ref": float(t_ref), "relax": float(relax), "tol": float(tol)}
    settings.update({k: float(v) for k, v in solve_kw.items()})
    if limiter is not None:
        settings["limiter"] = str(limiter)
    rec = fydoc.complete("code/coupled", {
        "settings": settings,
        "inputs": {"device": _device(device),
                   "discharge": {"fylite:channel_aturns": np.asarray(aturns, float)}}})
    F = rec["fields"]
    arr = lambda k: np.asarray(F[k]["data"], float)  # noqa: E731
    fact = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    cols = {k: arr("history_" + k) for k in ("it", "beta0", "change", "t_avg", "axis", "surfaces",
                                              "metric_change", "gs_iterations", "gs_residual",
                                              "inner_iterations", "converged")}
    history = [{"it": int(cols["it"][i]), "beta0": float(cols["beta0"][i]),
                "change": float(cols["change"][i]), "t_avg": float(cols["t_avg"][i]),
                "axis": float(cols["axis"][i]), "surfaces": int(cols["surfaces"][i]),
                "metric_change": float(cols["metric_change"][i]),
                "gs_iterations": int(cols["gs_iterations"][i]),
                "gs_residual": float(cols["gs_residual"][i]),
                "inner_iterations": int(cols["inner_iterations"][i]),
                "converged": bool(cols["converged"][i])}
               for i in range(cols["it"].size)]
    converged = bool(fact("converged"))
    return {"rho": np.asarray(F["core_profiles"]["profiles_1d"]["grid"]["rho_tor_norm"]["data"], float),
            "te": arr("te"),
            "vprime": np.asarray(F["equilibrium"]["time_slice"]["profiles_1d"]["dvolume_drho_tor"]["data"], float),
            "source": arr("source"), "beta0": fact("beta0"),
            "history": history, "converged": converged,
            "iterations": int(fact("iterations")),
            "notes": list(rec.get("notes", [])),
            "provenance": provenance("coupled", closure=closure,
                                     converged=converged,
                                     feedback="pressure amplitude only",
                                     metric="re-traced per outer iteration; "
                                            "each round solved to steady, so "
                                            "no time term and no dV'/dt "
                                            "here")}


# --------------------------------------------------------------------------- #
# local linear stability / quasilinear fluxes
# --------------------------------------------------------------------------- #
def tglf(inputs: dict, *, fluxes: bool = False, ky=None,
         sat_rule: int = 1, nmodes: int = 2) -> dict:
    """Local linear stability (default) or the quasilinear flux chain.

    ``inputs`` is the ``input.tglf`` name/value mapping.  With
    ``fluxes=False`` the answer is the eigenvalues at one ``ky``: ★gamma is
    a linear GROWTH RATE, not a transport flux — they are read at different
    places in an argument and a page that puts them in one column invites
    the wrong one.

    With ``fluxes=True`` the whole chain runs over a ky spectrum under
    ``sat_rule``.  ★The operating point is the CALLER's to state: this path
    does not bisect for the mode width, so ``WIDTH`` and the unit
    normalisations are required rather than invented — guessing them would
    be answering a question the caller did not ask.
    """
    if fluxes:
        out = _tglf.fluxes_kernel(inputs, ky=ky, sat_rule=sat_rule)
        kind = "quasilinear_flux"
    else:
        out = _tglf.linear_kernel(inputs, nmodes=nmodes)
        kind = "linear_eigenvalue"
    res = dict(out) if isinstance(out, dict) else {"result": out}
    res["provenance"] = provenance("tglf", kind=kind, sat_rule=sat_rule)
    return res
