"""TGLF/NEO transport-coefficient closure from an equilibrium (FYL-DESIGN-03 P4).

The last wiring of the kernel closure: `fylite.scenario.model.mapping.surface_state` (the
parameter-checked TGYRO map port) was fed from ``input.gacode`` tables until
now; :func:`equilibrium_surface_states` builds the same states straight from an
reconstruction — Miller shape and ``B_unit = (dΦ/dr)/(2π r)`` from ONE
:class:`fylite.fyo.Ladder` (:func:`surface_states` is the same builder
on a ladder the caller already holds), profile gradients re-expressed
against the Miller minor-radius label, in SI, with upstream's gradient sign
convention.

:func:`kernel_chi` then packages the whole chain as a ``chi(rho, te, ti)``
hook for :func:`fylite.scenario.model.assembly.solve_te_ti`: per surface, TGLF
(``fluxes_kernel``) plus NEO's Hirshman–Sigmar branch give gyro-Bohm
fluxes — ★both channels on the KERNEL now, so the hook answers for any
equilibrium rather than only for surfaces a departed libtglf was recorded
on; ``Q_GB = n_e e T_e c_s (ρ_s/a)²`` converts them to W/m² per V′-area;
:func:`fylite.kernel.chi_from_flux` turns that into the effective χ the PDE
consumes.  Impurity split: D + one impurity (default carbon) from Z_eff by
the standard quasi-neutral partition.
"""
from __future__ import annotations

import numpy as np

from ... import fyo, kernel
from . import mapping

from . import assembly

__all__ = ["equilibrium_surface_states", "surface_states", "gyrobohm_q",
           "kernel_chi", "kernel_coefficients", "loop_transport",
           "momentum_chi_phi", "MomentumClosureUnavailable"]


#: The two single-ion closures of quasineutrality this package uses, and
#: they are DIFFERENT PLASMAS rather than two spellings of one.
#:
#: ★★``"dilution"`` is TGYRO's LOC_N_ION=1 posture: deuterium at
#: ``n_D = n_e (Z_imp − Z_eff)/(Z_imp − 1)``, the impurity present only
#: through the dilution it causes.  ``"effective"`` is NEO's: one ion
#: carrying the whole charge, ``n_i = n_e / Z_eff``.  At Z_eff = 1.6 with
#: carbon they differ by 40 % in the ion density, so a builder that picked
#: one silently would hand the other's consumer a plasma it did not ask for.
#: The name is a parameter for exactly that reason — this used to be two
#: assembly functions, one per convention, which is how the two also came to
#: disagree about the collisionality.
ION_MIX = ("dilution", "effective")


def _main_ion_density(ne, zeff, z_imp, mix: str):
    """Main-ion density under one of :data:`ION_MIX`.

    The kernel's, refusal included: a ``Z_eff`` the impurity cannot represent
    is raised rather than floored."""
    if mix == "effective":
        #: no impurity model to refuse against — one ion, all the charge
        return np.asarray(ne, float) / float(zeff)
    if mix != "dilution":
        raise ValueError(f"ion_mix must be one of {ION_MIX}, not {mix!r}")
    try:
        return kernel.ion_dilution(ne, zeff=zeff, z_imp=z_imp)
    except kernel.KernelError as exc:
        raise ValueError(str(exc)) from exc


def equilibrium_surface_states(eq, *, psin, psin_prof, ne, te, ti=None,
                         zeff: float = 1.6, z_imp: int = 6,
                         ion_mix: str = "dilution") -> list[dict]:
    """Per-surface `mapping.surface_state` dicts straight from an equilibrium
    (an ``fyo:equilibrium`` document, or a g-file at the door).

    ★It was ``gfile_surface_states``.  The name said g-file while the
    parameter has taken anything ``fyo.as_equilibrium`` accepts for some
    time — a document, a reconstruction, a path — so the format in the name
    was the one input it does NOT require.

    The standalone door: traces the equilibrium once (a
    :class:`fylite.fyo.Ladder` carrying ``psin``) and hands it to
    :func:`surface_states`.  A caller that evaluates more than once — the
    closure hook does, on every outer step — builds the ladder itself and
    calls :func:`surface_states` directly.
    """
    lad = fyo.Ladder.with_surfaces(eq, psin)
    return surface_states(lad, psin=psin, psin_prof=psin_prof, ne=ne, te=te,
                          ti=ti, zeff=zeff, z_imp=z_imp, ion_mix=ion_mix)


def surface_states(lad, *, psin, psin_prof, ne, te, ti=None,
                   zeff: float = 1.6, z_imp: int = 6,
                   ion_mix: str = "dilution", omega=None,
                   p_fast=None) -> list[dict]:
    """Per-surface `mapping.surface_state` dicts from ONE traced ladder.

    ``lad`` — a :class:`fylite.fyo.Ladder` that carries every surface
    in ``psin`` (:meth:`~fylite.fyo.Ladder.with_surfaces`); ``ne``
    [m⁻³] / ``te`` / ``ti`` [eV] on ``psin_prof`` (``ti`` defaults to
    ``te``).  Ion mix: D + one impurity (charge ``z_imp``) at constant
    ``zeff``, both at the common ``ti``.

    ★``omega`` [rad/s] on ``psin_prof`` turns rotation ON: it fills each
    state's ``w0`` and ``w0p = dω/dr`` (against the SAME midplane ``r``,
    by the same kernel end rule the other profiles use), which is what
    ``mapping.tglf_inputs(..., rotation=True)`` needs in order to write
    ``VPAR_SHEAR`` / ``VPAR`` / ``VEXB_SHEAR``.  **Omitted means no
    rotation** (``w0 = w0p = 0``) — the EAST tier of this design, and the
    state every recorded deck was built in.

    ★``p_fast`` [Pa] on ``psin_prof`` turns the NON-THERMAL pressure on:
    it fills each state's ``pext`` and ``dpext = -d p_fast/dr`` (against the
    same midplane ``r`` every other gradient here uses), which is how a
    fast-ion population reaches TGLF on this path — through ``beta_unit``,
    ``p_prime`` and ``alpha_sa``, i.e. as **alpha stabilisation**.
    **Omitted means no fast ions**, which is what every recorded deck was
    built in.  ``nbi.deposit(...)["p_fast"]`` is the producer.

    ★★**Why this route and not a fast-ion SPECIES.**  ``mapping.Ion`` has a
    ``therm`` flag, and a ``therm=False`` entry would put the fast ions in
    TGLF as a kinetic species — dilution, its own drive, its own resonance.
    That is the more complete physics and it is deliberately NOT taken here:
    it needs a fast-ion density AND temperature profile with gradients that
    the slowing-down model does not produce (it produces a pressure), it
    enlarges the dispersion matrix on every one of up to five hundred outer
    steps, and TGYRO — the port this whole mapping layer follows line by
    line — takes the ``ptot`` route for exactly these reasons.  The species
    route stays available for a caller that has the profiles; nothing here
    forecloses it.

    ★★This used to take the g-file and trace it THREE times per call —
    the Miller rows at ``psin``, a 41-surface metric ladder for ρ and ``a``,
    and a 24-surface Miller ladder for the ``r(ψ_N)`` map that ``B_unit``
    is differentiated on — and then interpolated between the three, because
    they were three different surface sets.  It was called from the closure
    hook on every outer step of a march (up to five hundred) for an
    equilibrium that did not change.  Now the one ladder carries the
    requested surfaces, so ρ, ``r`` and the shape at a surface are read off
    that surface, and ``B_unit`` is differentiated on the ladder it is
    read from.  ★Measured on the synthetic deck at ψ_N = 0.3/0.5/0.7: the
    shape rows and ``a`` are bit-identical (same kernel, same levels);
    ``B_unit`` moves by what the removed interpolations were worth — see
    the changelog entry for the numbers.
    """
    psin = np.asarray(psin, float)
    idx = lad.index_of(psin)
    rows = [lad.miller[i] for i in idx]
    a_m = lad.a_minor
    if not np.isfinite(a_m):
        raise ValueError("g-file carries no boundary polyline; cannot fix a")
    #: ★B_unit is the kernel's — `|dΦ/dr|/(2πr)` with `Φ = πB₀ρ²`, in
    #: tesla, and it stays in tesla: this layer used to multiply it by 1e4
    #: because CGS was what the mapping port spoke.  It is the number the
    #: whole gyro-Bohm normalisation hangs on and nothing raises when it is
    #: wrong.  The `r(ψ_N)` it is differentiated on is the ladder's own
    #: Miller `r`, on the SAME surfaces as ρ — no second ladder, no
    #: interpolation.
    r_dense = np.array([w["r"] for w in lad.miller]) * a_m          # m
    b_unit_dense = kernel.b_unit_from_rho(lad.b0, lad.rho, r_dense)  # T
    b_unit_t = b_unit_dense[idx]
    r_m = np.array([w["r"] for w in rows]) * a_m

    # profiles on the ladder + gradients against r [1/m], upstream sign
    ne_l = kernel.interp(psin, psin_prof, np.asarray(ne, float))     # m^-3
    te_l = kernel.interp(psin, psin_prof, np.asarray(te, float))
    ti_l = te_l if ti is None else kernel.interp(psin, psin_prof,
                                             np.asarray(ti, float))

    def _mlog(vals):
        #: the kernel's log-gradient, with the FLOOR policy (a profile that
        #: dips to zero is a numerical guard here, not a signal) — and its
        #: end rule, which is the same one every other profile in this
        #: package is differentiated with
        return kernel.gradient(vals, r_m, log=True, floor=1e-30)

    dlnne = _mlog(ne_l)
    dlnte = _mlog(te_l)
    dlnti = _mlog(ti_l)
    nd = _main_ion_density(ne_l, zeff, z_imp, ion_mix)
    #: ★rotation, if the caller supplied any.  `w0p` is dω/dr against the
    #: MIDPLANE MINOR RADIUS in metres — the same `r_m` the log-gradients
    #: above are taken against, because `tglf_local` divides it by the
    #: same `a` when it forms VPAR_SHEAR.  Taking it against ρ instead
    #: would be wrong by dρ/dr and nothing would raise.
    if omega is None:
        w0_l = np.zeros_like(ne_l)
        w0p_l = np.zeros_like(ne_l)
    else:
        w0_l = kernel.interp(psin, psin_prof, np.asarray(omega, float))
        w0p_l = kernel.gradient(w0_l, r_m)

    #: ★the non-thermal pressure, on the SAME `r_m` — `dpext` is
    #: `-d p_fast/dr`, upstream's sign (positive for a falling profile),
    #: which is what `mapping.surface_state` documents and what every
    #: other gradient in this function already carries.
    if p_fast is None:
        pext_l = np.zeros_like(ne_l)
        dpext_l = np.zeros_like(ne_l)
    else:
        pext_l = kernel.interp(psin, psin_prof, np.asarray(p_fast, float))
        dpext_l = -kernel.gradient(pext_l, r_m)

    signb = 1.0 if lad.b0_signed >= 0 else -1.0

    states = []
    for i, w in enumerate(rows):
        signq = 1.0 if w["q"] >= 0 else -1.0
        ions = [
            {"z": 1.0, "mass": 2.0 * mapping.AMU_GACODE, "ni": float(nd[i]),
             "ti": float(ti_l[i]), "dlnnidr": float(dlnne[i]),
             "dlntidr": float(dlnti[i])},
        ]
        states.append(mapping.surface_state(
            a=a_m, rmin=w["r"] * a_m, rmaj=w["rmaj"] * a_m,
            zmag=w["zmag"] * a_m, drmaj=w["shift"], dzmag=w["s_zmag"],
            q=w["q"], s=w["shear"], kappa=w["kappa"], s_kappa=w["s_kappa"],
            delta=w["delta"], s_delta=w["s_delta"],
            zeta=w["zeta"], s_zeta=w["s_zeta"],
            b_unit=b_unit_t[i], te=te_l[i], ne=ne_l[i],
            dlnnedr=dlnne[i], dlntedr=dlnte[i],
            ions=ions, z_eff=zeff, signb=signb, signq=signq,
            w0=float(w0_l[i]), w0p=float(w0p_l[i]),
            pext=float(pext_l[i]), dpext=float(dpext_l[i])))
    return states


def gyrobohm_q(st: dict) -> float:
    """Gyro-Bohm energy-flux unit of one surface state, in W/m²
    (``Q_GB = n_e e T_e c_s (ρ_s/a)²``, SI throughout)."""
    return kernel.gyrobohm_q(ne=st["ne"], te=st["te"], c_s=st["c_s"],
                             rho_s=st["rho_s"], a=st["a"])


def kernel_chi(eq, *, psin, psin_prof, ne, gm3_at, width,
               zeff: float = 1.6, sat_rule: int = 2,
               tglf_extra: dict | None = None, chi_floor: float = 0.05,
               chi_cap: float = 50.0, tgyro_revision: int | str | None = "auto"):
    """A ``chi(rho, te, ti)`` closure hook backed by TGLF (+ NEO HS analytic).

    ★This is :func:`kernel_coefficients`'s energy half, kept under its own
    name because it is the contract every heat-channel driver already
    speaks — see there for the arguments.  A caller that also wants the
    density channel's ``D`` takes both hooks from that factory rather than
    building a second one: the two share ONE turbulence run per state.
    """
    #: ★The arguments are SPELLED here rather than forwarded as `**kw`.
    #: `width` has no default anywhere in this package on purpose (a mode
    #: width invented by a closure is a physics choice made silently on
    #: every surface of every march), and a gate asserts that by
    #: INTROSPECTING this signature — which a `**kw` delegation erases.
    return kernel_coefficients(
        eq, psin=psin, psin_prof=psin_prof, ne=ne, gm3_at=gm3_at,
        width=width, zeff=zeff, sat_rule=sat_rule, tglf_extra=tglf_extra,
        chi_floor=chi_floor, chi_cap=chi_cap,
        tgyro_revision=tgyro_revision)["chi"]


def kernel_coefficients(eq, *, psin, psin_prof, ne, gm3_at, width,
                        zeff: float = 1.6, sat_rule: int = 2,
                        tglf_extra: dict | None = None,
                        chi_floor: float = 0.05, chi_cap: float = 50.0,
                        d_floor: float = 0.02, d_cap: float = 20.0,
                        omega=None, p_fast=None,
                        mass_main: float | None = None,
                        tgyro_revision: int | str | None = "auto"):
    """``{"chi": hook, "particles": hook}`` — plus ``"momentum"`` when a
    rotation profile is supplied.  All channels, one run.

    ★★The particle flux was there all along.  The port returns
    ``particle`` / ``energy`` / ``exchange`` per species and only the middle
    one was ever read, so the density channel — which `core_march` can now
    advance beside the temperatures — had to take its ``D`` from a caller
    while the model that knows it was being run anyway, once per surface
    per pass.

    ``particles(state) -> (D, v)`` takes the march's state dict
    (``{rho, te, ti, ne, psi}``), which is what lets the turbulence run
    happen at the density the solver is actually at.  ``v`` is zero and says
    so: one flux cannot be split into a diffusion and a pinch.

    ``eq`` — an ``fyo:equilibrium`` document (or a g-file at the door), or
    a :class:`fylite.fyo.Ladder` already carrying ``psin`` (what
    :func:`fylite.fyo.turbulent_transport`
    passes, so the face and the closure trace once between them);
    ``psin`` — kernel surfaces (a handful; χ is interpolated between them);
    ``gm3_at(rho)`` — callable or array giving ⟨|∇ρ|²⟩ on the transport grid;
    ``ne`` [m⁻³] on ``psin_prof`` (locked density, per the design);
    ``width`` — the TGLF mode width, and REQUIRED.  Each hook
    call rebuilds the surface states at the CURRENT ``te``/``ti`` iterate, runs
    ``tglf.fluxes_kernel`` per surface + NEO's
    Hirshman–Sigmar branch, converts the summed gyro-Bohm fluxes through
    :func:`gyrobohm_q` and :func:`fylite.kernel.chi_from_flux`, and clips to
    ``[chi_floor, chi_cap]`` (the closure's own stiffness guard — pair with
    ``d_pc`` in the solver).

    ★★``omega`` [rad/s] on ``psin_prof`` turns the MOMENTUM channel on.
    With it the per-surface decks carry ``VPAR_SHEAR`` / ``VPAR`` /
    ``VEXB_SHEAR`` (``mapping.tglf_inputs(..., rotation=True)``, which is
    upstream's ``tgyro_tglf_map.f90`` mapping), the port's ``stress_tor``
    becomes a sheared toroidal stress rather than the residual one, and a
    third hook appears: ``momentum(state) -> chi_phi`` [m²/s], ready for
    :func:`fylite.scenario.model.assembly.solve_momentum`.  **Without it
    there is no ``"momentum"`` key** — a flat profile has no diffusivity to
    resolve, and returning one would be inventing a number
    (:func:`momentum_chi_phi` refuses for the same reason).  ``mass_main``
    [kg] defaults to deuterium, and must match the ``mass=`` the momentum
    solve is marched with.

    ★★★``tgyro_revision`` is the host-level preset
    :data:`~fylite.scenario.model.mapping.TGYRO_TGLF_REVISION` — TGYRO's
    own ``TGYRO_TGLF_REVISION``, ported from ``tgyro_tglf_map.f90``.
    ``"auto"`` (the default) picks the revision TGYRO pairs with this
    ``sat_rule``: rule 1 -> revision 2, rule 2 -> revision 3.  ``None``
    applies nothing.

    ★It is a default rather than an option because **SAT2 is not just a
    saturation rule**: revision 3 is what upstream calls "the recommended
    setting for using SAT_RULE = 2", and it turns ``USE_BPER`` on,
    ``USE_MHD_RULE`` OFF (that one zeroes the pressure term in the drift),
    and the ky grid to model 4 with 18 points and 8 modes.  This closure
    used to run SAT2 with all three at library defaults, i.e. two of them
    inverted.  Measured on TGYRO's treg01: the preset moves the electron
    particle flux by **5.45x** and the energy flux by **3.92x** at
    r/a = 0.2, falling to a few per cent at r/a = 0.65 — and the
    correction changes sign between radii, so it is not a scale factor
    somebody could absorb.

    ★``NMODES`` rides in with the preset (8 for revision 3) and is
    honoured: measured at 4.70 s per surface against 4.62 s at one mode,
    so multi-mode is **2 %**, while the preset as a whole costs 3.2x
    (that is ``NBASIS_MAX = 6`` and ``NKY = 18``, not the mode count).

    ★★One thing this deliberately does NOT copy: TGYRO's
    ``TGYRO_TGLF_MXH_FLAG`` defaults to **0**, which zeroes the extended
    shape harmonics on the way into TGLF even though its own geometry
    used them.  This closure keeps them (``mxh=True``).  That is a
    geometry-fidelity choice, not a model setting, and it is stated here
    rather than left to be discovered: a deck built here is NOT
    bit-identical to TGYRO's for the ``SHAPE_*`` family.

    ★★``width`` has no default because there is nothing honest to default
    it to.  libtglf BISECTED for the mode width, and that search is not in
    this repository; the port solves at the width it is given.  A number
    invented here would be a physics choice made by the closure, silently,
    on every surface of every march — so the caller states the operating
    point, exactly as :func:`fylite.scenario.model.gyrofluid.fluxes_kernel`
    and ``S.model.tglf(fluxes=True)`` already require of theirs.

    The transport grid ``rho`` must be the metrics ρ ladder of the same
    g-file with an axis node prepended (the `test_transport_east` layout):
    ψ_N ↔ ρ mapping is taken from `fyo.transport_metrics` once.
    """
    #: ★imported here rather than at module scope: `gyrofluid` reaches the
    #: kernel, and the closure is the only thing in this module that needs
    #: it.  It used to have `from . import neo as neo_mod` beside it — a
    #: name the `neo` -> `neoclassical` rename left behind, bound to
    #: nothing and read by nothing, but still EXECUTED.  Every caller of
    #: this function got `ImportError` on contact, which is to say the
    #: whole TGLF/NEO production path did.
    from . import gyrofluid as tglf_mod

    psin = np.asarray(psin, float)
    #: ★ONE trace for the life of the hook.  The dense ladder carries the
    #: requested surfaces, so ρ at a surface is read, not interpolated —
    #: and `surface_states` below reads the same object on every call
    #: instead of tracing the g-file three more times per outer step.
    lad = fyo.Ladder.with_surfaces(eq, psin)
    rho_k = lad.rho[lad.index_of(psin)]
    #: the axis-node layout is the kernel's — the traced ladder excludes
    #: the axis on purpose, and which quantities are zero there is the rule
    (rho_full, psin_full), _ = kernel.with_axis_node(
        zero=(lad.rho, lad.psin))

    #: ★``SAT_RULE`` is NOT written into the deck here: `fluxes_kernel` takes
    #: it as an argument and refuses a deck that disagrees, so a caller
    #: putting it in `tglf_extra` gets a refusal rather than a run whose
    #: presets and whose saturation come from two different rules.
    tglf_over = {"WIDTH": float(width), **(tglf_extra or {})}

    #: ★the momentum channel is on iff a rotation profile was supplied, and
    #: it is decided ONCE here rather than per call: a closure that gained
    #: and lost a channel between outer steps would be two closures.
    rotating = omega is not None
    #: ★TGYRO pairs a saturation rule with a revision; "auto" follows it
    #: rather than making the caller remember the pairing.
    if tgyro_revision == "auto":
        tgyro_revision = {0: 1, 1: 2, 2: 3}.get(int(sat_rule))
    if tgyro_revision is not None:
        tgyro_revision = int(tgyro_revision)
        if tgyro_revision not in mapping.TGYRO_TGLF_REVISION:
            raise ValueError(
                f"tgyro_revision {tgyro_revision} is not one of "
                f"{sorted(mapping.TGYRO_TGLF_REVISION)}")
    #: deuterium, matching the single main ion `surface_states` builds and
    #: the `mass=` `solve_momentum` is normally marched with
    m_main = (2.0 * 1.66053906660e-27 if mass_main is None
              else float(mass_main))

    def coefficients(rho, te, ti, ne_g=None):
        rho = np.asarray(rho, float)
        # profiles live on the transport grid; express them on psin_prof for
        # the state builder by mapping through this g-file's rho ladder
        psin_of_rho = kernel.interp(rho, rho_full, psin_full)
        te_p = kernel.interp(np.asarray(psin_prof, float), psin_of_rho, te)
        ti_p = kernel.interp(np.asarray(psin_prof, float), psin_of_rho, ti)
        #: ★★the density the closure sees is the MARCHING one when the
        #: density channel is on.  It used to be locked (the design's
        #: deliberate deviation ②) and that is still the default — but a
        #: turbulence run evaluated at a density the solver has already
        #: left is a closure for a different plasma, and the density
        #: channel is exactly what makes that possible.
        ne_p = (np.asarray(ne, float) if ne_g is None else
                kernel.interp(np.asarray(psin_prof, float), psin_of_rho,
                              np.asarray(ne_g, float)))
        states = surface_states(
            lad, psin=psin, psin_prof=psin_prof, ne=ne_p, te=te_p, ti=ti_p,
            zeff=zeff, omega=omega, p_fast=p_fast)
        #: the density ON the transport grid, and its gradient by the same
        #: kernel rule the temperatures use — computed once, not per surface
        ne_rho = (np.asarray(ne_g, float) if ne_g is not None else
                  kernel.interp(psin_of_rho, np.asarray(psin_prof, float),
                                np.asarray(ne, float)))
        grad_ne = kernel.gradient(ne_rho, rho)
        #: ★∂ω/∂ρ on the TRANSPORT grid and by the solver's end rule —
        #: `solve_momentum` writes its flux with ∂ω/∂ρ, so the closure must
        #: divide by the same derivative the solver will multiply back.
        #: (`surface_states` separately takes dω/dr against the midplane
        #: minor radius, which is what upstream's VPAR_SHEAR is defined on;
        #: the two labels are different and both are needed.)
        grad_omega = (kernel.gradient(
            kernel.interp(psin_of_rho, np.asarray(psin_prof, float),
                          np.asarray(omega, float)), rho)
            if rotating else None)
        pi_k, n_k, r2_k, gm3_k = (
            tuple(np.empty(len(states)) for _ in range(4)) if rotating
            else (None, None, None, None))
        chi_e_k = np.empty(len(states))
        chi_i_k = np.empty(len(states))
        d_n_k = np.empty(len(states))
        for i, st in enumerate(states):
            #: ★★The PORT, on this channel too.  This was
            #: `tglf_mod.run_isolated`, a REPLAY keyed by a JSON digest of
            #: the deck — so the production turbulence path answered only
            #: for surfaces some vanished libtglf had been recorded on, and
            #: every other equilibrium got `OracleMissing` where a flux
            #: belonged.  Both of the tests that called it caught that as a
            #: skip.
            #:
            #: What kept it a replay was the WIDTH: libtglf bisected for the
            #: mode width and the port does not.  That is a missing INPUT,
            #: not a missing model, and an input is something a caller can
            #: state — hence `width=` above.
            #: ★``rotation=rotating``: with a rotation profile the deck
            #: gains VPAR_SHEAR / VPAR / VEXB_SHEAR and `stress_tor`
            #: becomes a SHEARED stress.  Without one the deck is written
            #: exactly as before — bit for bit, which is what keeps every
            #: recorded answer reachable.
            deck = {**mapping.tglf_inputs(st, rotation=rotating,
                                          revision=tgyro_revision),
                    **tglf_over}
            #: ★``NMODES`` arrives with the preset and `fluxes_kernel`
            #: refuses a deck that names one while the call says another,
            #: so it is read out here rather than being left to clash.
            n_modes = int(deck.pop("NMODES", 1))
            #: ``SAT_RULE`` likewise: the preset writes the rule this
            #: closure was already asked for, so they agree by
            #: construction — but the deck must not carry it twice.
            deck.pop("SAT_RULE", None)
            turb = tglf_mod.fluxes_kernel(
                deck, sat_rule=int(sat_rule), nmodes=n_modes,
                stress=rotating)
            #: Measured before switching, on all nine recorded
            #: Hirshman-Sigmar cases: worst relative difference 5.8e-15.
            #: That is machine precision, not a physics change.
            nloc = kernel.neo_local({**st, "shear": st["s"]})
            nsp = [nloc[k] for k in kernel.NEO_SPECIES_ROWS]
            nout = kernel.neo_sauter(
                nsp, kernel.neo_geo14(nloc["geometry"]),
                nu_1=nloc["nu_1"],
                ipccw=int(-st["signb"] * st["signq"]),
                btccw=int(-st["signb"]),
                vintage=kernel.HIRSHMAN_SIGMAR_VINTAGE)
            n_sp = len(nsp[0])
            neoc = {"pflux": list(nout[:n_sp]),
                    "eflux": list(nout[n_sp:2 * n_sp])}
            gbf = kernel.neo_gyrobohm(
                1.0, st["ions"][0]["ti"] / st["te"],
                st["rho_s"] / st["a"])
            q_gb = gyrobohm_q(st)
            #: ★``energy``, not ``eflux``: the port names its channels
            #: ``particle`` / ``energy`` / ``exchange``, the replay named
            #: the middle one ``eflux``.  Same quantity, same
            #: gyro-Bohm normalisation, same species order.
            flux_e = (turb["energy"][0] + neoc["eflux"][0] / gbf["eflux"]) * q_gb
            flux_i = (sum(turb["energy"][1:])
                      + sum(neoc["eflux"][1:]) / gbf["eflux"]) * q_gb
            #: ★The ELECTRON particle flux, and only it: ambipolarity ties
            #: the ion fluxes to it, so summing the species would count the
            #: same transport twice.  ★★It comes back in the PARTICLE
            #: gyro-Bohm unit — `Gamma_GB`, not `Q_GB` — and the two differ
            #: by `e T_e`, about 1e19 here.  This channel existed in the
            #: port's answer all along (`turb["particle"]`) and nothing
            #: read it; the density channel had to take its D from a
            #: caller.
            gamma_gb = kernel.gyrobohm_gamma(
                ne=st["ne"], c_s=st["c_s"], rho_s=st["rho_s"], a=st["a"])
            flux_n = (turb["particle"][0]
                      + neoc["pflux"][0] / gbf["pflux"]) * gamma_gb
            i_rho = float(rho_k[i])
            g3 = gm3_at(i_rho) if callable(gm3_at) else float(
                kernel.interp(i_rho, rho, np.broadcast_to(np.asarray(gm3_at, float),
                                                      rho.shape)))
            n_si = float(kernel.interp(psin[i], np.asarray(psin_prof, float),
                                   np.asarray(ne, float)))
            #: ★the kernel's derivative, for its END RULE.  A closure whose
            #: temperature gradient is computed by a different rule than
            #: the solver's is a different closure at the two nodes where
            #: the rules differ — and those are the axis and the edge.
            gt_e = float(kernel.interp(i_rho, rho, kernel.gradient(te, rho)))
            gt_i = float(kernel.interp(i_rho, rho, kernel.gradient(ti, rho)))
            chi_e_k[i] = kernel.chi_from_flux(flux_e, n_si, gt_e, g3)
            chi_i_k[i] = kernel.chi_from_flux(flux_i, n_si, gt_i, g3)
            gn = float(kernel.interp(i_rho, rho, grad_ne))
            d_n_k[i] = kernel.d_from_flux(flux_n, gn, g3)
            if rotating:
                #: ★★the momentum channel, in the SAME shape as the two
                #: above: a model flux and its gyro-Bohm unit.  The
                #: effective coefficient is formed AFTER the loop, on the
                #: whole profile at once — `momentum_chi_phi` refuses a
                #: FLAT profile, and「flat」is a property of the profile,
                #: not of one surface.  Per-surface it would raise at any
                #: interior node where ∂ω/∂ρ happens to vanish, which is
                #: exactly the case `d_from_flux`'s floored denominator
                #: exists to report rather than to crash on.
                #:
                #: ★``stress_tor`` is summed over the IONS only: the
                #: electron row carries a mass ratio's worth of momentum,
                #: and the ion stress is what upstream's own transport
                #: target is.  ★No neoclassical part is added — NEO's
                #: momentum flux is not on this path, and adding zero
                #: silently would read as「neoclassical included」.
                pi_k[i] = sum(turb["stress_tor"][1:]) * kernel.gyrobohm_pi(
                    ne=st["ne"], te=st["te"], c_s=st["c_s"],
                    rho_s=st["rho_s"], a=st["a"])
                n_k[i] = n_si
                r2_k[i] = float(st["rmaj"]) ** 2
                gm3_k[i] = g3
        chi_e_k = np.clip(chi_e_k, chi_floor, chi_cap)
        chi_i_k = np.clip(chi_i_k, chi_floor, chi_cap)
        #: ★the same stiffness guard the heat channels get, and for the
        #: same reason: a flat iterate reports an unbounded D honestly, and
        #: a solver cannot march on it
        d_n_k = np.clip(d_n_k, d_floor, d_cap)
        out = {"chi_e": kernel.interp(rho, rho_k, chi_e_k),
               "chi_i": kernel.interp(rho, rho_k, chi_i_k),
               "d_n": kernel.interp(rho, rho_k, d_n_k)}
        if rotating:
            gw_k = kernel.interp(rho_k, rho, grad_omega)
            chi_phi_k = momentum_chi_phi(
                stress=pi_k, dens=n_k, mass=m_main, r2=r2_k,
                grad_omega=gw_k, gm3=gm3_k)
            #: the same stiffness guard the other channels get
            out["chi_phi"] = kernel.interp(
                rho, rho_k, np.clip(chi_phi_k, chi_floor, chi_cap))
        return out

    def chi(rho, te, ti):
        out = _memo(rho, te, ti)
        return out["chi_e"], out["chi_i"]

    #: ★ONE run per state, shared by the two hooks.  `solve_core` asks for
    #: chi and then for D at the same iterate, and a turbulence run is the
    #: expensive thing here — so the second question must not pay for it
    #: again.  The key is the state itself: a memo keyed by anything less
    #: would answer for a plasma the solver has left.
    cache = {}

    def _memo(rho, te, ti, ne_g=None):
        rho = np.asarray(rho, float)
        key = (rho.tobytes(), np.asarray(te, float).tobytes(),
               np.asarray(ti, float).tobytes(),
               None if ne_g is None else np.asarray(ne_g, float).tobytes())
        if cache.get("key") != key:
            cache["key"] = key
            cache["out"] = coefficients(rho, te, ti, ne_g)
        return cache["out"]

    def particles(state):
        """``(D, v)`` for the density channel, from the same run as chi."""
        out = _memo(state["rho"], state["te"], state["ti"], state["ne"])
        #: ★v is ZERO and says so: one flux cannot be separated into a
        #: diffusion and a pinch, so what comes back is an EFFECTIVE D
        #: carrying the whole flux.  Reporting a pinch of zero is the
        #: honest form of "not separated", and it is what `d_from_flux`'s
        #: own docstring says.
        return out["d_n"], np.zeros_like(np.asarray(state["rho"], float))

    def momentum(state):
        """``chi_phi`` [m²/s] for the toroidal-momentum channel, from the
        same run as chi.  Present only when the factory was given
        ``omega``."""
        return _memo(state["rho"], state["te"], state["ti"],
                     state.get("ne"))["chi_phi"]

    hooks = {"chi": chi, "particles": particles}
    if rotating:
        hooks["momentum"] = momentum
    return hooks



class MomentumClosureUnavailable(NotImplementedError):
    """Asked for a turbulent momentum diffusivity from a state that cannot
    resolve one — a flat rotation profile, where the stress is residual."""


def momentum_chi_phi(*, stress, dens, mass, r2, grad_omega, gm3,
                     floor: float = 1e-30):
    """A model toroidal stress → the effective ``chi_phi`` the momentum
    channel takes.

    ``stress`` is Π/V′ [N/m], the toroidal-stress flux per unit V′-area —
    the currency :func:`fylite.kernel.gyrobohm_pi` converts upstream's
    dimensionless ``stress_tor`` into.  ``dens`` [m⁻³], ``mass`` [kg],
    ``r2`` = ⟨R²⟩ [m²], ``grad_omega`` = ∂ω/∂ρ [rad/s], ``gm3`` = ⟨|∇ρ|²⟩.

    :func:`fylite.scenario.model.assembly.solve_momentum` writes the law as
    ``Π = −V′ ⟨|∇ρ|²⟩ n m ⟨R²⟩ χ_φ ∂ω/∂ρ``, so

        ``χ_φ = (Π/V′) / (⟨|∇ρ|²⟩ · n m ⟨R²⟩ · |∂ω/∂ρ|)``

    which is :func:`fylite.kernel.d_from_flux` applied to the stress
    divided by the capacity ``n m ⟨R²⟩`` — the same algebra, the same
    floored denominator, and deliberately not a second implementation of
    it.

    ★★**This refused until 2026-08-29, and the reason it gave was wrong.**
    It said upstream's toroidal-stress QL weights were not ported.  They
    were — what was not ported was the toroidal PROJECTION of the rotation
    drive: ``solve_ky_modes`` computed ``rotation_scaled`` and then handed
    ``write_all_rows`` the RAW species, so ``vpar_shear`` reached the
    matrix missing ``sign_It`` and ``ave_c_tor_par(1,1)/Rmaj``.  Zero on
    every recorded deck, therefore invisible.  With the projection wired,
    the stress matches upstream's own ``out.tglf.gbflux`` to **2.3e-5**
    over three surfaces and two shear strengths (V-01).

    ★It still refuses on a FLAT rotation profile, and that refusal is
    physics rather than a gap: at ∂ω/∂ρ = 0 what remains is the RESIDUAL
    stress, a torque source and not a diffusivity — dividing it by a zero
    gradient would manufacture an unbounded χ_φ that a solver would
    happily march on.  ★★And on an up-down symmetric equilibrium it is
    not merely unusable, it is **zero by symmetry**: Peeters et al.,
    *Nucl. Fusion* **51**, 094027 (2011) §2 shows the momentum flux
    changes sign under a transformation the gyrokinetic equation is
    invariant under, once rotation, rotation shear, E×B shear and up-down
    asymmetry are all absent.  Measured here at 2.7e-10 of Q_i
    (``tests/test_tglf_momentum.py``).  A residual stress worth feeding to
    ``torque=`` therefore requires one of those symmetries to be broken —
    it is not something a flat profile hands you for free.  Feed that term to
    ``solve_momentum``'s ``torque`` instead.

    ★It is an EFFECTIVE diffusivity, for the reason
    :func:`fylite.kernel.d_from_flux` gives: one flux cannot be split into
    a diffusion and a pinch, and this does not pretend to.
    """
    g = np.asarray(grad_omega, float)
    if not np.any(np.abs(g) > 0.0):
        raise MomentumClosureUnavailable(
            "the rotation profile is flat (grad_omega is zero everywhere), "
            "so the toroidal stress at this state is the RESIDUAL stress — "
            "a torque source, not a diffusivity.  Pass it to "
            "assembly.solve_momentum's `torque` argument, or supply a "
            "rotation profile with shear")
    cap = (np.asarray(dens, float) * float(mass) * np.asarray(r2, float))
    return kernel.d_from_flux(np.asarray(stress, float) / cap, g, gm3,
                              floor=floor)


def loop_transport(*, chi, sources_fn, ions=None, dt: float = 0.05,
                   max_outer: int = 60, tol_steady: float = 1e-8,
                   d_pc: float = 0.0, edge_psin: float = 0.95,
                   n_surfaces: int = 41, b0_dot: float = 0.0,
                   b0: float | None = None):
    """Build the ``transport=`` hook for :func:`fylite.scenario.analysis.loop.self_consistent` —
    the fourth layer of the self-consistent loop (FYL-DESIGN-03 P4).

    Per loop iteration the hook: extracts the transport metrics from the
    CURRENT equilibrium's g-file (dense ladder + axis node, the
    `test_transport_east` layout), maps the loop's ψ_N profiles onto ρ, builds
    the per-channel sources through ``sources_fn(rho, vprime) -> SourceSet``
    (the caller wires nbi/lh/ohmic/radiation there — actuator modules stay the
    producers), relaxes Te/Ti through :func:`fylite.scenario.model.assembly.solve_te_ti`
    (``max_outer`` backward-Euler steps — one transport relaxation per loop
    round; full steadiness is the LOOP's fixed point, not each round's), and
    maps the result back to ψ_N.

    ``chi`` is the closure hook (analytic, or :func:`kernel_chi` — note the
    latter is bound to ONE g-file's metrics; for an evolving equilibrium pass
    a factory-fresh closure or an analytic tier).  ``ions`` as in
    `solve_te_ti` (omit to run the channels uncoupled).  The returned dict
    carries ``te``/``ti`` on ``psin_prof`` plus the relaxation report the loop
    stores on ``result["transport"]``.
    """
    from . import assembly as asm

    #: ★`b0` is asked for rather than read off the equilibrium, because the
    #: hook takes a g-file, a document OR a traced ladder and only one of
    #: the three can be asked for a vacuum field.  A ramp with no field to
    #: ramp is a caller error, and it is refused here rather than silently
    #: normalised away inside the kernel.
    if b0_dot != 0.0 and not b0:
        raise ValueError("loop_transport: b0_dot needs the vacuum field b0 "
                         "[T] it is a rate of change of")

    #: ★★The metric this hook marches on is re-traced from the CURRENT
    #: equilibrium every round, so between two rounds the volume a profile
    #: sits in has changed — and until the kernel could say `dV'/dt` there
    #: was nowhere to put that change: the temperature was carried across
    #: unchanged and the energy `(3/2) T dV' n` came from nowhere.  The
    #: previous round's V' is held here, on the hook, because that is the
    #: only place that sees two consecutive rounds.
    #:
    #: ★It is a LIST and not a plain name because the hook is a closure the
    #: loop calls; rebinding a name inside it would need `nonlocal`, and a
    #: one-slot list says "this is state the hook carries" more plainly
    #: than a keyword does.
    last_vprime = []

    def hook(*, eq, ne, te, ti, psin_prof):
        tm = fyo.transport_metrics(eq, n_surfaces=n_surfaces,
                                   edge=edge_psin)
        #: ★the same one host as above, and the reason it IS one: the
        #: flux-surface AVERAGES take their innermost traced value where the
        #: labels and V' take zero, and that asymmetry was spelled out at
        #: five call sites before it had a name
        (rho, vp, psin_g), (gm3,) = kernel.with_axis_node(
            zero=(tm["rho"], tm["vprime"], tm["psin"]), repeat=(tm["gm3"],))

        psin_prof = np.asarray(psin_prof, float)
        ne_r = kernel.interp(psin_g, psin_prof, np.asarray(ne, float))
        te_r = kernel.interp(psin_g, psin_prof, np.asarray(te, float))
        ti_src = te if ti is None else ti
        ti_r = kernel.interp(psin_g, psin_prof, np.asarray(ti_src, float))

        ions_r = None
        if ions is not None:
            ions_r = [{**ion, "ni": kernel.interp(psin_g, psin_prof,
                                              np.asarray(ion["ni"], float))
                       if np.ndim(ion["ni"]) else ion["ni"]}
                      for ion in ions]

        #: the metric the profiles arrived on — absent on the first round,
        #: where there is no previous one and nothing has moved
        vp_old = last_vprime[0] if last_vprime else None
        if vp_old is not None and np.shape(vp_old) != np.shape(vp):
            #: ★a ladder that changed LENGTH is not a moved metric, it is a
            #: different grid; carrying it across would be comparing two
            #: different radii node by node
            vp_old = None
        out = asm.solve_core(
            rho, vprime=vp, vprime_old=vp_old, gm3=gm3, ne=ne_r,
            te=te_r, ti=ti_r, chi=chi,
            sources=sources_fn(rho, vp), ions=ions_r, b0_dot=b0_dot,
            b0=abs(float(b0)) if b0 else 1.0,
            dt=dt, max_outer=max_outer, tol_steady=tol_steady, d_pc=d_pc)
        last_vprime.append(np.array(vp, float))
        del last_vprime[:-1]

        return {
            "te": kernel.interp(psin_prof, psin_g, out["te"]),
            "ti": kernel.interp(psin_prof, psin_g, out["ti"]),
            "steady": out["steady"], "delta": out["delta"],
            "outer_steps": out["outer_steps"],
            "te_axis": float(out["te"][0]), "ti_axis": float(out["ti"][0]),
        }

    return hook
