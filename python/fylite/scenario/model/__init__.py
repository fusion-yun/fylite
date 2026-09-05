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
           torque: float = 0.0) -> dict:
    """March the heat channel in time — BY THE KERNEL (``code/evolve``).

    ★2026-09-05 第十五刀: ``density=True`` marches the main-ion density beside
    the heat (a PRESCRIBED particle closure — ``D = d_over_chi * chi_e`` and a
    constant ``pinch`` [m/s] — with ``fuel`` [1/s] deposited on a Gaussian);
    ``quasi=True`` puts the named ``impurity`` INTO the quasi-neutrality: the
    main ion diluted by ``zeff`` (``ion_dilution``), the impurity a second ion
    channel with its own ``d_over_chi_z`` / ``pinch_z`` / ``fuel_z`` (defaults:
    the main ion's), and Z_eff a RESULT of the two species; ``momentum=True``
    advances the toroidal rotation beside the march (``chi_phi = prandtl *
    chi_i``, ``torque`` [N m] on the aux deposit, Dirichlet zero at the edge).

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
    }
    inputs: dict = {}
    if equilibrium is None:
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
    if chi_e_profile is not None:
        inputs["core_transport"] = {"model": [{"profiles_1d": {
            "electrons": {"energy": {"d": np.asarray(chi_e_profile, float)}},
            "total_ion_energy": {"d": np.asarray(chi_i_profile, float)}}}]}
    rec = fydoc.complete("code/evolve", {"settings": settings, "inputs": inputs})

    F = rec["fields"]
    arr = lambda k: np.asarray(F[k]["data"], float)  # noqa: E731
    fact = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    cp = F["core_profiles"]["profiles_1d"]
    lad = F["equilibrium"]["time_slice"]["profiles_1d"]
    sm = F["summary"]
    gq = sm["global_quantities"]
    steps = int(fact("steps"))
    geometry = "miller" if equilibrium is None else "ladder"
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
        "notes": list(rec.get("notes", [])),
        "provenance": provenance("evolve", closure="constant",
                                 channels=("heat", "current") if current
                                          else ("heat",),
                                 sawtooth="mixing" if sawtooth else None,
                                 geometry=geometry,
                                 reference_channels=ref_used,
                                 driven_current=(float(i_cd) if i_cd
                                                 else None),
                                 pedestal="eped1nn" if pedestal else None,
                                 loop="kernel (evolve_heat)"),
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
