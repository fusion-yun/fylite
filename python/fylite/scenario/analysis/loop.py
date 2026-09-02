"""Self-consistent kinetic-EFIT outer loop (EFIT ↔ NEO current source).

Closes the current-source self-consistent loop entirely inside fylite: an
Reconstruction gives the equilibrium; :func:`fylite.fyo.miller_geometry`
extracts the per-surface
Miller geometry + profiles; :mod:`~fylite.scenario.model.neoclassical` computes the neoclassical
bootstrap current at each surface; the bootstrap-shaped current profile is fed
back through EFIT's flux-surface-averaged current constraint
(``KZEROJ``/``RZEROJ=0``/``SIZEROJ=ψN``/``VZEROJ=j/⟨j⟩``); iterate until q₀
converges.

Current model (first cut, documented): the constrained current-profile SHAPE is
a blend ``(1-f_bs-f_nbi)·ohmic + f_bs·bootstrap + f_nbi·beam`` — the ohmic part a
Spitzer proxy (``∝ Te^1.5``), the bootstrap part NEO's ``jpar_dke`` shape at the
current equilibrium, and the beam part (K-20, optional — see ``beams``)
:mod:`fylite.scenario.model.nbi`'s driven current, whose weight ``f_nbi = |I_NBI|/|I_p|`` is
*computed* rather than set because the injected beam power is measured.
``f_bs`` (``bootstrap_fraction``) sets the bootstrap weight; the
*shape* self-updates each iteration from NEO physics, so q(ψ) converges to a
bootstrap-consistent profile.  The **absolute** bootstrap magnitude (converting
NEO's normalized ⟨j·B⟩ to A/m² without a fraction parameter) needs NEO's
reference constants or a K-9 oracle — a documented calibration step, not the
loop mechanics.
"""
from __future__ import annotations

import logging

import numpy as np

from ... import engine, fyo, kernel
from ..model import lh, nbi, neoclassical
from ..model.neoclassical import NeoclassicalError
from ..model import neoclassical as neo_geometry
#: ★★These three are imported because the loop CONSTRUCTS its defaults.  It
#: used to reach them through the backend registry, by name, and the comment
#: here said that was the point — "never by name" was the phrasing, for a
#: mechanism whose whole interface was a name.  What it actually bought was
#: that `loop.neo` did not look like a dependency; the dependency was real
#: either way, and it is now visible to a reader and to a static check.
#: Tests stub `fylite.scenario.model.neoclassical.bootstrap` where that
#: function lives, which is unchanged.
#: ★the EFIT driver is gone (LICENSE 3.1); reconstruction is the Rust
#: inverse, which takes the same measurement dict it was written against
#: ★★The reconstruction door, and it is the SHOT/TIME one.  This alias used
#: to be `recon_rs.reconstruct` — the measurement-dict door — called with the
#: signature of the EFIT driver that left with LICENSE 3.1, so every call
#: raised `TypeError` on contact and this loop, the oldest thing in the
#: repository, could not execute its first statement.  What kept it that way
#: was not the wiring but a DESIGN question, now settled: the loop's current
#: prior is a flux-surface-AVERAGED target and `reconstruct` took only a
#: per-interior-cell source, so rewiring it would have changed what the loop
#: computes.  The kernel takes the FSA target itself now
#: (`gs_inverse_solve_fsa`, ABI v113), which is why this line can finally be
#: the door it names.
from .recon_rs import reconstruct_shot as _efit_run

#: silent by default (library convention); the app configures handlers/level
_LOG = logging.getLogger("fylite.loop")


class ProfileError(ValueError):
    """The reconstruction cannot supply the kinetic profiles the loop needs.

    Raised instead of substituting an invented profile: the bootstrap current is
    a *gradient* functional, so a placeholder profile does not degrade the answer
    gracefully — it produces a confident, wrong current shape (K-22).  Pass
    ``allow_synthetic=True`` / ``allow_synthetic_profiles=True`` to opt into the
    labelled parametric stand-ins, or feed a pressure-constrained reconstruction
    (``pressure=True``, plus ``thomson_ne=True`` for the density).
    """


#: parametric stand-in profiles, used ONLY under ``allow_synthetic`` and always
#: reported as ``"synthetic"`` in the loop's ``profile_source``.  Representative
#: EAST H-mode shapes, not measurements.
def _synthetic_ne19(psin):
    return 4.0 * (1 - 0.8 * np.asarray(psin, float) ** 2)


def _synthetic_te_ev(psin):
    return 3000.0 * (1 - 0.9 * np.asarray(psin, float) ** 2) + 50.0


def pressure_health(eq) -> dict:
    """Whether an equilibrium's total pressure can carry a kinetic T_e derivation.

    A magnetics-only reconstruction fits ``p(ψ)`` as a low-order polynomial with
    no positivity constraint, so it routinely turns **negative** in the outer
    half.  Dividing a floored version of that by ``2 n_e e`` yields a T_e pinned
    at ~0.1 eV there, which zeroes every temperature and pressure gradient the
    bootstrap depends on.  Returns the counts a caller needs to decide, and never
    raises.

    ★``eq`` goes through :func:`fylite.fyo.as_equilibrium`, so a g-file path, a
    ``read_geqdsk`` dict, an ``fyo:equilibrium`` document and an in-memory
    reconstruction result are all accepted — and the deck spelling ``pres``
    stops here rather than travelling."""
    pres = np.asarray(fyo.profile_of(fyo.as_equilibrium(eq), "pressure"),
                      float)
    bad = int(np.count_nonzero(pres <= 0.0))
    return {"n": int(pres.size), "n_nonphysical": bad,
            "min_pa": float(pres.min()) if pres.size else 0.0,
            "usable": bad == 0}


def _profiles_from_result(res: dict, eq=None, n: int = 40, *,
                          allow_synthetic: bool = False):
    """Kinetic profiles n_e(ψ_N), T_e(ψ_N) from a reconstruction, on a ψ_N grid.

    ``n_e`` comes from the POINT-fitted density spline (``ne_profile``, 1e19 m⁻³);
    ``T_e`` from the g-file total pressure and ``n_e``
    (``p ≈ 2 n_e T_e e`` → ``T_e ≈ p/(2 e n_e)``), i.e. self-consistent with the
    reconstruction's own pressure — which is why that pressure has to be
    physical.  :func:`pressure_health` decides; a non-physical one raises
    :class:`ProfileError` rather than being floored (K-22).

    ``allow_synthetic=True`` substitutes the labelled parametric stand-ins for
    whichever input is missing or unusable — for a mechanism demo or a
    magnetics-only start, where the loop's *plumbing* is under test rather than
    its physics.  Use :func:`profile_source` to record which path ran.
    """
    #: ★★The reconstruction IS the equilibrium — no file in between.  This
    #: read a g-file the EFIT driver had written; the Rust reconstruction
    #: answers in memory, and `fyo.as_equilibrium` takes that result directly
    #: (`fyo.reconstruction`, built for exactly this: "the only way to get a
    #: reconstruction into a model was to write a g-file and read it back,
    #: which `loop.py` did twice an iteration through a fixed text format
    #: that carries fewer digits than the numbers going into it").
    doc = fyo.as_equilibrium(res if eq is None else eq)
    pres = np.asarray(fyo.profile_of(doc, "pressure"), float)   # Pa on ψ_N
    psin = np.linspace(0.0, 1.0, len(pres))
    src = profile_source(res, doc)

    if src["ne"] == "measured":
        ne19 = np.asarray(res["ne_profile"], float)
        ne19 = kernel.interp(psin, np.linspace(0, 1, len(ne19)), ne19)
    elif allow_synthetic:
        ne19 = _synthetic_ne19(psin)
    else:
        raise ProfileError(
            "no density profile on the reconstruction (`ne_profile`) — run with "
            "thomson_ne=True / point=True, or pass allow_synthetic_profiles=True "
            "to accept a labelled parametric n_e")
    ne = np.clip(ne19, 0.05, None) * 1e19               # m^-3

    e = 1.602176634e-19
    if src["te"] == "pressure":
        te = pres / (2.0 * e * ne)                      # eV (p = 2 n T e)
    elif allow_synthetic:
        te = _synthetic_te_ev(psin)
    else:
        h = src["pressure"]
        raise ProfileError(
            f"the equilibrium's total pressure is non-physical on "
            f"{h['n_nonphysical']}/{h['n']} points (min {h['min_pa']:.4g} Pa), so "
            "T_e = p/(2 n_e e) cannot be derived — flooring it would zero dTe/dpsi "
            "over that whole region and hand the bootstrap a confident wrong "
            "shape. Start from a pressure-constrained reconstruction "
            "(pressure=True), or pass allow_synthetic_profiles=True to accept a "
            "labelled parametric T_e")
    xs = np.linspace(0.05, 0.95, n)
    return (kernel.interp(xs, psin, ne), kernel.interp(xs, psin, te), xs)


def profile_source(res: dict, g=None) -> dict:
    """Where each kinetic profile would come from, for provenance (K-22).

    ``{"ne": "measured"|"synthetic", "te": "pressure"|"synthetic", "pressure":
    <:func:`pressure_health`>}`` — the single predicate
    :func:`_profiles_from_result` branches on, exposed so the loop can record it
    without repeating the test.  Pass ``g`` when the equilibrium is already read,
    to avoid a second parse.

    Provenance must never be the thing that breaks a run: when no ``g`` is given
    and the equilibrium cannot be read, ``te`` is reported as ``"unknown"`` with
    ``pressure=None`` rather than raising.  The physics path
    (:func:`_profiles_from_result`) always supplies a real ``g``, so it never sees
    that state.
    """
    if g is None:
        try:
            g = fyo.as_equilibrium(res)
        except Exception:                            # noqa: BLE001 — diagnostic only
            return {"ne": "measured" if res.get("ne_profile") else "synthetic",
                    "te": "unknown", "pressure": None}
    health = pressure_health(g)
    return {"ne": "measured" if res.get("ne_profile") else "synthetic",
            "te": "pressure" if health["usable"] else "synthetic",
            "pressure": health}


def effective_sigma(sigma) -> float:
    """Reduce a **radial** relative σ on the current prior to the one scalar the
    constraint channel can carry (K-23, candidate ③).

    The solver scales every ``KZEROJ`` row by the same ``fwtxxj``-derived weight,
    so a σ(ψ) has to become a single number.  The reduction preserves the block's
    **total information** rather than its mean: for independent rows weighted
    ``1/σ_i``, the common σ satisfying ``N/σ_eff² = Σ 1/σ_i²`` is

        σ_eff = (mean(σ_i⁻²))^(-1/2)

    i.e. the quadratic mean of the *weights*.  It is dominated by the best-known
    radii, which is the correct behaviour for a constraint that is imposed as a
    block: the fit keeps the information it has, and what is lost is **where**
    that information sits — the reason K-23 keeps per-row σ as the end state.

    A scalar σ passes through unchanged.  Non-finite or non-positive entries are
    dropped (a radius with no stated uncertainty carries no weight information);
    if nothing survives, :class:`ProfileError` is raised rather than inventing a
    default.
    """
    arr = np.atleast_1d(np.asarray(sigma, float))
    good = arr[np.isfinite(arr) & (arr > 0.0)]
    if not good.size:
        raise ProfileError(
            "current_sigma has no positive finite entry — state a relative "
            "uncertainty (sigma/j) or leave it None")
    return float(np.sqrt(1.0 / np.mean(good ** -2.0)))


def sigma_to_weight(sigma) -> float:
    """Map a relative σ on the current prior to ``FWTXXJ`` (K-23).

    ``FWTXXJ = 1/σ_eff``, anchored so that ``σ_eff = 1`` — a prior as uncertain as
    the quantity it constrains — reproduces the solver's built-in default of
    ``1.0``.  A 20%-uncertain prior therefore weighs 5×, a 200%-uncertain one
    0.5×.  This anchor is a **convention of this port**, not a calibration: the
    solver's absolute scale (``fwtxxx = fwtxxj*1000/brspmin``) is arbitrary, so
    only ratios between runs are meaningful.
    """
    return 1.0 / effective_sigma(sigma)


def _current_components(surf, jbs, te_s, bootstrap_fraction: float,
                        nbi_shape=None, nbi_fraction: float = 0.0):
    """Decompose the constrained current density into its components.

    All normalized to ⟨j⟩=1 units (``VZEROJ = j/⟨j⟩``): the ohmic contribution
    ``(1-f_bs-f_nbi)·ohmic(∝Te^1.5)``, the bootstrap contribution
    ``f_bs·bootstrap(NEO)`` and — when a beam is configured (K-20) — the
    beam-driven contribution ``f_nbi·nbi(METIS-class fast model)``; their sum is
    the constraint target (renormalized to mean 1 for ``VZEROJ``).

    Unlike ``f_bs``, which is a *parameter* because the analytic bootstrap
    magnitude is uncalibrated, ``f_nbi = |I_NBI|/|I_p|`` is **computed** — the
    beam model's current is absolute, because the injected power is measured.

    Returns ``(psin, j_ohm, j_bootstrap, j_nbi, j_total, vzeroj)``.
    """
    psin = np.array([s["psin"] for s in surf])
    ohm = (te_s / te_s.max()) ** 1.5
    ohm = ohm / (ohm.mean() or 1.0)
    bs = np.clip(np.asarray(jbs, float), 0.0, None)
    bs = bs / (bs.mean() or 1.0)
    f = float(bootstrap_fraction)
    f_nbi = float(np.clip(nbi_fraction, 0.0, max(0.0, 1.0 - f)))
    if nbi_shape is None or f_nbi <= 0.0:
        j_nbi = np.zeros_like(psin)
        f_nbi = 0.0
    else:
        nb = np.clip(np.asarray(nbi_shape, float), 0.0, None)
        nb = nb / (nb.mean() or 1.0)
        j_nbi = f_nbi * nb
    j_ohm = (1 - f - f_nbi) * ohm
    j_bootstrap = f * bs
    j_total = j_ohm + j_bootstrap + j_nbi
    vzeroj = j_total / (j_total.mean() or 1.0)
    return (psin, j_ohm, j_bootstrap, j_nbi, j_total, vzeroj)


def self_consistent(shot: int, time_s: float, *, max_iter: int = 8,
                    tol: float = 0.02, n_surfaces: int = 16,
                    bootstrap_fraction: float = 0.3, server=None,
                    out=None, archive=None, final_uncertainty: int | None = None,
                    current_source=None, current_key: str = "jpar_dke",
                    profile_kind: str = "linear",
                    neo_resolution="fast", allow_synthetic_profiles: bool = False,
                    current_weight: float | None = None, current_sigma=None,
                    beam_source=None, beams=None,
                    wave_source=None, launchers=None,
                    transport=None,
                    verbose: bool = False, **run_kw) -> dict:
    """Run the EFIT↔NEO self-consistent current-profile loop (K-12/Qian-Z 2024).

    Starts from a diagnostic-constrained east reconstruction (pass the usual
    ``point``/``pressure``/``thomson_ne`` via ``**run_kw``), then iterates:
    extract per-surface Miller geometry + profiles, NEO bootstrap per surface,
    assemble the FSA current constraint, re-solve.  Converges when
    ``|Δq0| < tol`` (or ``max_iter``).

    ★★The constraint is handed to the KERNEL, not to a namelist.  It used to
    be written as EFIT's ``KZEROJ``/``SIZEROJ``/``VZEROJ`` rows and passed
    through ``extra_namelist`` to a driver that left with LICENSE 3.1 — which
    is why this loop could not run at all: the surviving ``reconstruct`` took
    a per-interior-cell current SOURCE, and a flux-surface-averaged TARGET is
    not that.  The kernel takes the target itself now (``current_fsa``, ABI
    v113), so the loop states the same physics it always did, to something
    that is here.

    ★``out`` and ``final_uncertainty`` are **refused**, not ignored.  Both
    named the EFIT driver's behaviour — persisting the converged g-file, and
    re-running the converged constraint with ``uncertainty=N`` for
    errorbars/profiles/diagnostics — and the driver left with LICENSE 3.1.
    The Rust reconstruction answers in memory: write it out yourself with
    :func:`fylite.io.geqdsk.write_geqdsk` if you want a file, and there is no
    uncertainty pass on this backend.  ``result["current"]`` still carries the
    J_ohm/J_bootstrap decomposition.

    ``current_source``/``beam_source``/``wave_source`` take a MODEL OBJECT,
    the way ``transport`` below does, and ``None`` builds this loop's
    default: :class:`~fylite.scenario.model.neoclassical.NeoSource`
    (``key=current_key``, ``resolution=neo_resolution``),
    :class:`~fylite.scenario.model.nbi.MetisBeam` and
    :class:`~fylite.scenario.model.lh.LHAnalytic`.  Pass an object to use
    another — ``current_source=neoclassical.RedlSource()`` for the
    standalone Redl-2021 transcription, ``beam_source=nbi.MetisBeam(zeff=2)``
    to configure the default one.

    ★★They were ``current_backend="neo"`` and friends, NAMES resolved
    through a pluggable-backend registry (K-18, FYL-SDD-01 DE-LOG-03).  The
    registry is retired: it had three families and four built-ins, and both
    of its consumers — this function and ``fyo.neoclassical_source`` — still
    had to branch on the name, so it gave neither of them the polymorphism a
    name→factory map is for.  An object is what the registry constructed
    anyway, and it needs no registration step to be new.

    ``current_key`` picks which of the NEO solve's currents the default
    source reports, and is how the analytic branches are reached:
    ``"jpar_sauter"`` and ``"jpar_sauter_2021"`` are what the retired
    ``"sauter"``/``"sauter2021"`` backends named.  ★They were never separate
    models — one NEO call returns all three — and a ``*_sauter*`` key skips
    the drift-kinetic solve, which is what those backends' ``analytic_only``
    did.

    ``profile_kind`` is the interpolant the temperature profile is read
    through, ``"linear"`` (default, ``np.interp``) or ``"pchip"`` (monotone
    cubic — a linear interpolant's DERIVATIVE is a staircase, and the
    derivative is what a closure consumes).  ★It was ``profile_backend``,
    a pluggable family of two classes that differed by this string.

    ``allow_synthetic_profiles`` (default **False**) governs what happens when the
    reconstruction cannot supply a kinetic profile: by default the loop refuses
    (:class:`ProfileError`) rather than inventing one, because the bootstrap is a
    gradient functional and a placeholder yields a confident wrong current shape
    (K-22).  A magnetics-only start therefore needs either ``pressure=True`` /
    ``thomson_ne=True`` (so ``p>0`` and a measured ``n_e`` exist) or an explicit
    ``allow_synthetic_profiles=True`` — which substitutes labelled parametric
    stand-ins, logs a warning, and records the substitution in
    ``result["profile_source"]``.  Use it for plumbing demos, not for physics.

    ``current_weight`` sets ``FWTXXJ``, the weight the solver applies to the
    **whole** flux-surface-averaged current constraint block, i.e. how strongly the
    assembled ``VZEROJ`` prior is imposed relative to the magnetic measurements.
    ``None`` (default) leaves the solver's built-in ``1.0``, which is what every
    kefit run used before the ``&INWANT`` group could be written at all — the
    behaviour is unchanged unless you set it.  Lower it to state the current
    profile as a *soft* prior rather than a near-equality.

    ``current_sigma`` states that softness as a **relative uncertainty** (σ/j)
    instead of a bare weight — a scalar, or a profile on the constraint grid.  It
    is reduced to the one scalar the channel accepts by :func:`sigma_to_weight`
    and delivered *unreduced* on ``result["current_sigma"]``.  Give one of
    ``current_sigma`` / ``current_weight``, never both.

    :::{note}
    The channel takes **one scalar for the block**: the solver forms
    ``fwtxxx = fwtxxj*1000/brspmin`` and applies it to every constraint row, so a
    per-radius σ on the current prior cannot enter the fit (K-23).  The reduction
    (:func:`effective_sigma`) preserves the block's *total* information but not
    **where** that information sits, so a source whose uncertain part is its
    *deposition location* — lower-hybrid drive above all — still must not be
    folded into the target: a loose block weight says "this prior is weak
    everywhere", which is not the same claim as "this prior is weak near the
    deposition".  Per-row σ stays K-23's end state.
    :::

    ``neo_resolution`` (default ``"fast"``) sets the NEO velocity/angle resolution
    for the loop's per-surface solves — see :data:`fylite.scenario.model.neoclassical.RESOLUTION`.  The
    loop re-solves every surface each iteration, so this is the term that decides
    its wall time: ``"fast"`` is ~8x cheaper per surface than ``"accurate"`` for a
    **measured 0.22%** shift in ``jpar_dke`` (16 surfaces: 6.9 s → 0.8 s per
    round).  Pass ``"accurate"`` to reproduce the pre-K-21 numbers exactly, or
    ``None`` to leave :func:`fylite.scenario.model.neoclassical.bootstrap`'s own defaults alone.  It is
    ignored by a current source with no drift-kinetic branch
    (:class:`~fylite.scenario.model.neoclassical.RedlSource`).

    ``beams`` (a :class:`~fylite.scenario.model.nbi.Beam`
    list, e.g. from :func:`fylite.scenario.model.nbi.east_beams`) adds the external NBI
    drive (K-20, :mod:`fylite.scenario.model.nbi`): the beam-driven current enters the
    current constraint with the *computed* fraction ``|I_NBI|/|I_p|``, and the
    fast-ion pressure ``p_fast`` comes back on the result as ``fast_pressure``
    for the pressure channel (``p_total = p_thermal + p_fast``).  Note the loop
    does **not** yet feed ``p_fast`` back into EFIT's pressure constraint — that
    is the caller's decision, since it changes what ``pressure=`` means; the
    profile is delivered, the closure is not assumed.  With no ``beams`` the
    loop is bit-for-bit as it was — the beam source returns ``None``.  ★That
    used to be the job of a null backend, ``beam_backend="none"``, which was
    also the DEFAULT: passing ``beams`` and forgetting the backend name
    computed no beam at all, silently.

    ``launchers`` (see
    :func:`fylite.scenario.model.lh.east_launchers`) with
    ``wave_source=lh.LHAnalytic(eta_cd=...)`` evaluates
    the lower-hybrid drive (K-20, :mod:`fylite.scenario.model.lh`) at each round and returns
    it on ``result["lh"]``.  It is a **result channel only**: ``j_lh`` is not added
    to the current decomposition or to the ``VZEROJ`` target, because the term
    belongs in the fit as a *soft prior with a radial σ* and this constraint
    channel carries only one scalar weight for the whole block (``current_weight``).
    Folding it in as a fixed forcing term would state a deposition location the
    model does not know that precisely.

    ``transport`` closes the fourth layer of the loop (FYL-DESIGN-03 P4:
    equilibrium ↔ current ↔ **profiles** ↔ fluxes): a callable
    ``transport(eq=..., ne=..., te=..., ti=..., psin_prof=...) -> dict``
    returning at least ``te`` (optionally ``ti``) on ``psin_prof`` — typically
    :func:`fylite.scenario.model.closure.loop_transport`, which relaxes the temperatures
    through the core-transport solver on the *current* equilibrium's metrics.
    It is called at the top of every iteration, so the bootstrap and beam/wave
    stages below see transport-consistent profiles; ``result["profile_source"]
    ["te"]`` is then labelled ``"transport"`` and ``result["transport"]``
    carries the hook's last report.  The default ``None`` leaves the loop
    bit-for-bit as it was — measurement stays the default profile source.

    ``archive`` (a directory) writes each iteration as a write-once ``iter-NNN``
    snapshot (K-15, :mod:`fylite.engine`) — its constraint namelist
    (input), g-file (artifact) and state (q₀/q95/|Δq₀|/current) — so a round can
    be recovered/compared/branched; a :class:`~engine.Staleness` tracker
    records which stages were recomputed each round.  The returned dict carries a
    ``convergence_panel`` (cross-round q₀/q95/|Δq₀| series).
    """
    # the resolution knob only means something to a source that solves the DKE
    if current_sigma is not None:
        if current_weight is not None:
            raise ProfileError(
                "pass current_sigma OR current_weight, not both — the σ is "
                "converted to the weight (sigma_to_weight), so giving both "
                "states two different strengths for the same constraint")
        current_weight = sigma_to_weight(current_sigma)
    #: ★the default is CONSTRUCTED here, not looked up.  `neo_resolution`
    #: and `current_key` are the default source's knobs, so a caller who
    #: passes their own object has already said what it should be.
    src = (neoclassical.NeoSource(key=current_key, resolution=neo_resolution)
           if current_source is None else current_source)
    bsrc = nbi.MetisBeam() if beam_source is None else beam_source
    #: ★★These two are REFUSED rather than ignored, and this is the whole
    #: reason the check is here.  Both named the EFIT driver's file-writing
    #: behaviour: `out` persisted the converged g-file, `final_uncertainty`
    #: re-ran the converged constraint through `run(uncertainty=N)`.  The
    #: driver left with LICENSE 3.1 and the Rust reconstruction returns its
    #: answer IN MEMORY — it writes no g-file and has no uncertainty pass.
    #: Silently accepting them would be the same mistake this loop just came
    #: out of: an argument addressed to something that is not there.
    if out is not None or final_uncertainty is not None:
        raise NotImplementedError(
            "self_consistent(out=…/final_uncertainty=…) named the EFIT "
            "driver's g-file output and its uncertainty pass, both of which "
            "left with the driver (LICENSE 3.1).  The Rust reconstruction "
            "answers in memory; persisting it is `fylite.io.geqdsk."
            "write_geqdsk` on the returned result, and an uncertainty pass "
            "does not exist on this backend")

    wsrc = lh.LHAnalytic() if wave_source is None else wave_source
    stale = engine.Staleness()
    #: ★no scratch directory any more: the reconstruction answers in
    #: memory and nothing in this loop writes a file.  The temp dir was
    #: the EFIT driver's `out=`, and it outlived the driver by one
    #: refactor — created and removed on every call, never written to.
    res = _efit_run(shot, time_s, server=server, **run_kw)
    #: ★★Converted ONCE per solve, and it is the DOCUMENT that travels.
    #: Handing `res` itself to each model door would convert it six times an
    #: iteration, and — the reason this is not merely wasteful — the loop
    #: later writes `res["current"] = comps` (the J decomposition), which
    #: collides head-on with a g-file's own `current` (the plasma current).
    #: A document taken before any of that cannot be moved under the models.
    eq = fyo.as_equilibrium(res)
    stale.recomputed("equilibrium")          # a fresh equilibrium staleifies all downstream
    prof_src = profile_source(res, eq)
    ne, te, psin_prof = _profiles_from_result(
        res, eq, allow_synthetic=allow_synthetic_profiles)
    if allow_synthetic_profiles and "synthetic" in (prof_src["ne"], prof_src["te"]):
        health = prof_src["pressure"] or {"n_nonphysical": "?", "n": "?"}
        _LOG.warning(
            "kinetic profiles are partly SYNTHETIC (ne=%s, te=%s; pressure "
            "non-physical on %s/%s points) — the bootstrap shape below is a "
            "plumbing demo, not a measurement (K-22)",
            prof_src["ne"], prof_src["te"],
            health["n_nonphysical"], health["n"])
    te_fit = engine.fit_profile(psin_prof, te, kind=profile_kind)
    stale.refresh("profiles")
    history = [{"iter": 0, "q0": res["q0"], "q95": res.get("q95"),
                "constrained": False, "stale": stale.snapshot()}]
    if archive is not None:
        engine.snapshot(archive, 0, inputs={"constrained": False},
                            state={"q0": res["q0"], "q95": res.get("q95"),
                                   "constrained": False},
                            artifacts=[res["gfile"]] if res.get("gfile") else None)
    prev_q0, dq = res["q0"], None
    jbs_last = None
    nbi_last = None
    lh_last = None
    comps = {"psin": [], "j_ohm": [], "j_bootstrap": [], "j_nbi": [],
             "j_total": []}
    ti = None
    transport_last = None
    for it in range(1, int(max_iter) + 1):
        if transport is not None:
            # fourth layer: relax the profiles through the transport
            # solver on the CURRENT equilibrium before anything downstream
            # (bootstrap, beam, wave) consumes them
            tr = transport(eq=eq, ne=ne, te=te, ti=ti,
                           psin_prof=psin_prof)
            te = np.asarray(tr["te"], float)
            if tr.get("ti") is not None:
                ti = np.asarray(tr["ti"], float)
            te_fit = engine.fit_profile(psin_prof, te, kind=profile_kind)
            transport_last = {k: v for k, v in tr.items()
                              if k not in ("te", "ti")}
            prof_src["te"] = "transport"
            stale.refresh("transport")
        surf = neo_geometry.surface_inputs(
            eq, ne=ne, te=te, psin_prof=psin_prof, ti=ti,
            n_surfaces=n_surfaces)
        stale.refresh("mapping")             # geometry re-extracted from current equilibrium
        te_s = np.asarray(te_fit([s["psin"] for s in surf]), float)
        jbs = src.bootstrap(surf, context={"eq": eq, "ne": ne,
                                           "te": te, "psin_prof": psin_prof})
        stale.refresh("bootstrap")           # NEO re-run at current surfaces
        jbs_last = jbs
        # external beam drive (K-20): absolute j_NBI + p_fast at the current
        # equilibrium; f_nbi = |I_NBI|/|I_p| is computed, not a parameter.
        nbi_last = bsrc.deposit(eq=eq, ne=ne, te=te,
                                psin_prof=psin_prof, beams=beams)
        # the stage counts as evaluated either way: a null beam is a result,
        # not an omission, so it must not read as stale downstream.
        stale.refresh("beam")
        # RF drive (K-20 LH): a RESULT CHANNEL only.  j_lh is deliberately
        # NOT folded into the VZEROJ target: its deposition location is the
        # least certain of the four wave sources, so it belongs in the fit as
        # a soft prior with a radial sigma — and EFIT's FSA-current channel
        # takes one scalar weight for the whole block (see current_weight),
        # so a radial sigma is not expressible there yet.
        lh_last = wsrc.drive(eq=eq, ne=ne, te=te,
                             psin_prof=psin_prof, launchers=launchers)
        stale.refresh("wave")
        f_nbi, nbi_shape = 0.0, None
        if nbi_last is not None:
            ip = abs(float(res.get("ip") or 0.0))
            if ip > 0.0:
                f_nbi = abs(float(nbi_last["i_nbi"])) / ip
            nbi_shape = kernel.interp([s["psin"] for s in surf],
                                  nbi_last["psin"], np.abs(nbi_last["j_nbi"]))
        psin, j_ohm, j_bs, j_nb, j_tot, vzeroj = _current_components(
            surf, jbs, te_s, bootstrap_fraction, nbi_shape, f_nbi)
        comps = {"psin": psin.tolist(), "j_ohm": j_ohm.tolist(),
                 "j_bootstrap": j_bs.tolist(), "j_nbi": j_nb.tolist(),
                 "j_total": j_tot.tolist(), "nbi_fraction": f_nbi}
        stale.refresh("constraint")          # FSA target rebuilt
        #: ★the same three rows EFIT took as `KZEROJ`/`SIZEROJ`/`VZEROJ`
        #: at `RZEROJ = 0`, handed to the kernel as what they are: a
        #: SHAPE in units of its own mean, on named surfaces, with one
        #: weight.  ★`FWTXXJ` was a namelist scalar for a namelist that
        #: is gone; the weight is now the row weight it always was.
        final_fsa = {"x": psin.tolist(), "shape": vzeroj.tolist()}
        if current_weight is not None:
            final_fsa["weights"] = [float(current_weight)] * len(psin)
        res = _efit_run(shot, time_s, server=server,
                        current_fsa=final_fsa, **run_kw)
        eq = fyo.as_equilibrium(res)
        stale.recomputed("equilibrium")      # new equilibrium -> downstream stale again
        dq = abs(res["q0"] - prev_q0)
        #: ★★How many constraint rows REACHED the fit, per round.  The loop
        #: asks for one row per surface; a surface whose contour the tracer
        #: cannot close carries none, and a round that imposed nine of the
        #: sixteen it asked for has to say so — otherwise the history reads
        #: as if the constraint held everywhere it was written.
        rows_used = res.get("fsa_rows_used")
        if rows_used is not None and rows_used < len(psin):
            _LOG.warning(
                "iteration %d: the FSA current constraint reached %d of the "
                "%d surfaces asked for — the rest could not be traced on "
                "this field", it, rows_used, len(psin))
        row = {"iter": it, "q0": res["q0"], "q95": res.get("q95"),
               "dq0": dq, "constrained": True, "stale": stale.snapshot(),
               "fsa_rows_used": rows_used, "fsa_rows_asked": len(psin)}
        history.append(row)
        if archive is not None:
            engine.snapshot(archive, it, inputs=final_fsa,
                                state={k: row[k] for k in ("q0", "q95", "dq0",
                                                           "constrained")}
                                | {"current": comps},
                                artifacts=[res["gfile"]] if res.get("gfile") else None)
        if verbose:
            print(f"[loop] it={it} q0={res['q0']:.4f} dq0={dq:.4f}")
        if dq < tol:
            row["converged"] = True
            break
        prev_q0 = res["q0"]

    #: ★The converged equilibrium needs no re-solve: `res` already IS
    #: the last constrained solve, in memory.  This block used to re-run
    #: it only to make the driver write a g-file into `out` — an
    #: expensive way to obtain a file, and the file is what the caller
    #: can write itself from the result.  Attaching the decomposition is
    #: the part that was never about the file.
    if final_fsa is not None:
        res["current"] = comps       # attach the decomposition to the result
    # Redl-2021 analytic baseline for the converged equilibrium — the
    # cross-check for NEO's drift-kinetic jpar_dke (K-19).
    #
    # PREFER NEO's OWN OUTPUT.  The loop's per-surface solves already
    # evaluated the Redl-2021 coefficients (NEO's compute_Sauter_mod) on
    # exactly these surfaces, this geometry and this collisionality, and
    # reported them in the same units as jpar_dke — so the two are directly
    # comparable and cannot drift apart.  The standalone transcription is
    # the fallback when the source has no drift-kinetic branch.
    #
    # ★This said the fallback was "for a current source that does not run
    # libneo" — now every source — and that its j_bs was "NOT the NEO
    # normalization, so it is comparable in *shape* only".  Both sides are
    # in A·T/m² now (`neoclassical.surface_inputs` carries the unit), so
    # the units no longer separate them.  What still does is a measured
    # ~5.4x in the standalone branch's MAGNITUDE, pinned in
    # `test_bootstrap_units.py`: shape-only remains the right posture,
    # for a reason that is now a number rather than a normalisation.
    baseline = None
    solves = getattr(src, "last_solves", None)
    if (solves and len(solves) == len(comps["psin"])
            and all("jpar_sauter_2021" in r for r in solves)):
        baseline = {
            "source": "neo:jpar_sauter_2021",
            "psin": list(comps["psin"]),
            "j_bs": [r["jpar_sauter_2021"] for r in solves],
            "jpar_sauter_1999": [r["jpar_sauter"] for r in solves],
            "units": "NEO <j.B>/j_norm (same as jpar_dke)",
        }
    redl_xcheck = None
    if baseline is None:
        try:
            redl_xcheck = neoclassical.bootstrap_profile(
                eq, ne, te, psin_prof=psin_prof)
        except NeoclassicalError:                # a diagnostic, never fatal
            pass
        except Exception as exc:                 # noqa: BLE001
            #: ★★NOT a bare swallow.  This branch used to catch
            #: `Exception` and `pass`, and when the merge left the name
            #: `redl` unbound here the resulting `NameError` came back as
            #: "there is no baseline" — a silently missing diagnostic that
            #: read exactly like a machine without the analytic path.  A
            #: fallback may decline to answer; it may not hide a defect in
            #: itself.
            _LOG.warning("the analytic bootstrap baseline could not be "
                         "computed: %s: %s", type(exc).__name__, exc)
        if redl_xcheck is not None:
            baseline = {"source": "python:redl",
                        "psin": list(redl_xcheck["psin"]),
                        "j_bs": list(redl_xcheck["j_bs"]),
                        "units": "|<j.B>|/B0 [A/m^2] — shape-comparable only"}
    return {"result": res, "history": history,
            "convergence_panel": engine.convergence_panel(history),
            "converged": bool(dq is not None and dq < tol),
            "n_iter": len(history) - 1,
            "bootstrap_fraction": bootstrap_fraction,
            #: ★the MODEL's own name, read off the object.  It used to
            #: be the registry key the caller typed, which is the same
            #: string only for as long as the two cannot diverge.
            "current_source": getattr(src, "name", type(src).__name__),
            "current_key": current_key,
            "profile_kind": profile_kind,
            "neo_resolution": (neo_resolution if current_source is None
                               else None),
            "profile_source": prof_src,   # K-22: measured vs synthetic, per profile
            "current_weight": current_weight,   # None -> solver default 1.0
            # K-23: the radial sigma is delivered even though the channel
            # could only carry its scalar reduction — no information is
            # destroyed, it is just not inside the fit yet.
            "current_sigma": (None if current_sigma is None else
                              np.atleast_1d(current_sigma).tolist()),
            "current_sigma_effective": (None if current_sigma is None else
                                       effective_sigma(current_sigma)),
            "archive": str(archive) if archive is not None else None,
            "jpar_dke": jbs_last,               # raw NEO <j.B>, per surface
            "bootstrap_baseline": baseline,     # Redl-2021 baseline, NEO-first (K-19)
            "redl_bootstrap": redl_xcheck,      # set only on the Python fallback
            "beam_source": getattr(bsrc, "name", type(bsrc).__name__),
            "wave_source": getattr(wsrc, "name", type(wsrc).__name__),
            # FYL-DESIGN-03 P4: the fourth-layer report (None when the
            # loop ran measurement-only, the default)
            "transport": transport_last,
            "lh": lh_last,          # K-20: result channel, NOT in VZEROJ
            "nbi": nbi_last,                    # full beam deposition dict (K-20)
            "fast_pressure": (None if nbi_last is None else
                              {"psin": nbi_last["psin"].tolist(),
                               "p_fast": nbi_last["p_fast"].tolist()}),
            "current": comps,                   # {psin, j_ohm, j_bootstrap, j_nbi, j_total}
            "surface_psin": comps["psin"]}
