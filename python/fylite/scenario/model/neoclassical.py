r"""Neoclassical transport — the assembly layer over the kernel's neoclassical
solvers.

One subject, one module: the bootstrap current and the neoclassical fluxes, in
every form this package can compute them.  The solvers are all the kernel's
(``rust/fylite/src/neoclassical.rs`` and ``dke.rs``) —

* the drift-kinetic solve (:func:`fylite.kernel.dke_solve`) — first principles;
* Sauter-1999 and the Redl-2021 update NEO evaluates alongside it
  (:func:`fylite.kernel.neo_sauter`), free with the same solve;
* the standalone Redl-2021 transcription (:func:`fylite.kernel.redl_bootstrap`),
  which needs no drift-kinetic branch at all.

What this module holds is the shaping around them: the species table and the
Miller-geometry vector a call takes (:func:`surface_inputs`, :func:`_geo_kw`),
the named velocity/angle resolutions, the ``pressure_source`` policy, and the
two ``current_source`` backends the registry names — ``neo`` and ``redl``.

★``sauter`` and ``sauter2021`` were registered backends too, and they were
not models: one NEO call returns ``jpar_dke``, ``jpar_sauter`` and
``jpar_sauter_2021`` together, so choosing among them is ``key=`` of the
``neo`` backend.  See :class:`NeoSource` and the note where the two
one-line subclasses used to be.

★★**Why ``redl`` is in here and not beside it.**  It was its own module, and
the split had no subject behind it: both compute the SAME quantity — IMAS
``core_sources`` ``bootstrap_current``, identifier index 13 — off the same
kernel file, onto the same surfaces, and the fyo layer had two faces
(``bootstrap_source`` and ``neoclassical_source``) emitting the same DD term
with different provenance.  What separated them was which Fortran code the
Python was once written around, and both of those are gone.  A reader asking
"how does this package compute a bootstrap current" had to know that history
to find the second half of the answer.

★★**And the module is named for the physics now, not for GACODE's solver.**
It was ``neo``.  ``libneo.so`` — the in-memory bind-C binding it was first
written around — left with LICENSE 3.2, and what stayed is a kernel that
computes neoclassical transport; naming the module after the upstream code
kept a dependency alive in the vocabulary after it had gone from the build.
The one face that really IS GACODE's — the ``neo_dump_local`` namelist
grammar, replayed from recordings — moved to :mod:`fylite.io.gacode`, where
this package keeps other people's formats.

★★**The two-lineage Redl question, adjudicated 2026-08-21: this package
means the IMAS.jl lineage.**

The kernel hosts two things called "Redl 2021" and they are not the same
model.  ``redl_coefficients`` — the standalone transcription, the IMAS.jl
lineage — evaluates the ``f31`` fit at a second effective trapped fraction
``f34t`` to get L34.  ``sauter_redl``, the branch NEO's own solve uses, sets
``L34 = L31`` unconditionally.  They agree to the bit on the collisionless
axis — which is where every published-limit check lives, and why the
disagreement went unnoticed — and differ by 4.1 % at ν\* = 0.1 and 15.7 % at
ν\* = 1.

``redl`` is the adopted spelling of the paper.  ``sauter2021`` is NEO's
internal convention and stays reachable — as ``key="jpar_sauter_2021"`` —
but it is no longer a candidate for what "Redl 2021" means here; it is what
NEO computes.
``tests/test_redl.py`` pins the gap between them so a change in either
host is loud.

★And the ruling settles WHICH TRANSCRIPTION, not whether that transcription
tracks a drift-kinetic solve.  Those are separate claims and only the first
is adjudicated: measured against ``jpar_dke`` on the synthetic equilibrium,
the adopted lineage sits at 0.359 shape-RMS against a 0.30 drop-in bar
(``tests/test_bootstrap_gate.py``).  It has not been promoted on the
strength of being the right paper.
"""
from __future__ import annotations

import numpy as np

from ... import _deck_names, fyo, kernel



class NeoclassicalError(RuntimeError):
    """A neoclassical solve failed (kernel error, or an unrecorded oracle
    input).  ★Was ``NeoError``; the module is named for the physics now."""


class RedlError(ValueError):
    """The analytic path was handed a pressure it cannot use.

    ★Distinct from :class:`NeoclassicalError` on purpose, and kept through
    the merge: one says a solve failed, the other says the INPUT does not
    meet the ``pressure_source`` contract (a non-physical reconstruction
    pressure is refused rather than floored).  Collapsing them would make
    "bootstrap failed" mean two different things — the split this package
    has paid for twice already."""


#: Named velocity/angle resolutions for :func:`bootstrap` — ``(n_energy, n_xi,
#: n_theta)``.  A drift-kinetic solve costs roughly ``n_energy·n_xi·n_theta``, so
#: the resolution dominates the price of an iterative outer loop.  The cost and
#: the error are **measured** on an EAST surface (``g137985.04000`` at
#: ψ_N ≈ 0.5, D+e, ``collision_model=4``), relative to ``accurate``:
#:
#:   accurate  6/17/17   397 ms   (reference)
#:   medium    6/13/13   173 ms   jpar_dke within 0.01%
#:   fast      4/11/11    51 ms   jpar_dke within 0.22%   <- outer-loop default
#:   coarse    3/9/9      18 ms   jpar_dke within 1.84%
#:
#: ``accurate`` is the :func:`bootstrap` signature default, so a direct call is
#: unchanged; ``fast`` is what :func:`fylite.scenario.analysis.loop.self_consistent` uses, where
#: the same surfaces are re-solved every iteration and 0.22% is far inside the
#: standing calibration uncertainty (K-9).
RESOLUTION: dict[str, dict[str, int]] = {
    "accurate": {"n_energy": 6, "n_xi": 17, "n_theta": 17},
    "medium":   {"n_energy": 6, "n_xi": 13, "n_theta": 13},
    "fast":     {"n_energy": 4, "n_xi": 11, "n_theta": 11},
    "coarse":   {"n_energy": 3, "n_xi": 9,  "n_theta": 9},
}


def resolution_kwargs(resolution) -> dict:
    """Resolve a :data:`RESOLUTION` name (or an explicit dict) into NEO kwargs.

    ``None`` → ``{}`` (keep :func:`bootstrap`'s own defaults).  An unknown name
    is an error, not a silent fallback to a different accuracy."""
    if resolution is None:
        return {}
    if isinstance(resolution, str):
        try:
            return dict(RESOLUTION[resolution])
        except KeyError:
            raise NeoclassicalError(f"unknown NEO resolution {resolution!r}; have "
                           f"{sorted(RESOLUTION)}") from None
    return dict(resolution)




def bootstrap(species: list, *, rmin_over_a: float, rmaj_over_a: float,
              q: float, shear: float, shift=0.0,
              kappa=1.0, s_kappa=0.0, delta=0.0, s_delta=0.0,
              zeta=0.0, s_zeta=0.0, nu_1=0.1, rho_star=1.0e-3,
              ipccw=-1, btccw=-1,
              collision_model=4, equilibrium_model=2,
              n_energy=6, n_xi=17, n_theta=17,
              analytic_only: bool = False,
              backend: str | None = None) -> dict:
    """Run one NEO flux surface, return its neoclassical current (in memory).

    ``species`` is a list of per-species dicts with keys ``z`` (charge),
    ``mass`` (in units of deuterium mass), ``dens``/``temp`` (normalized), and
    ``dlnndr``/``dlntdr`` (``-a/n dn/dr`` / ``-a/T dT/dr`` gradient scale
    lengths); electrons included explicitly (``z=-1``).  Geometry is the local
    Miller set at the surface (``equilibrium_model=2``); ``rmin_over_a`` is the
    flux-surface label.  ``nu_1`` is the normalizing collision frequency.

    ★★``rho_star`` is ``rho_s / a`` and it is NOT a detail: every current
    NEO returns is exactly LINEAR in it, so the default (1e-3, NEO's own
    nominal) gives a SHAPE and not a magnitude.  A caller that wants amps
    must pass the physical value — with
    :func:`fylite.kernel.neo_current_unit` it is the difference between a
    bootstrap current and one wrong by ``rho_star_physical / 1e-3``.

    ``analytic_only`` drops the drift-kinetic branch — the two analytic
    vintages are what comes back, and ``jpar_dke``/``jtor_dke`` are ABSENT
    rather than present and stale.

    Returns ``{jpar_dke, jtor_dke, jpar_sauter, jpar_sauter_2021}``.
    ``jpar_dke`` is NEO's full drift-kinetic ``<j_par·B>`` (the accurate
    bootstrap); the other three are the analytic cross-checks NEO evaluates on
    the **same** run and the same geometry:

    * ``jpar_sauter`` — Sauter et al., Phys. Plasmas 6, 2834 (1999);
    * ``jpar_sauter_2021`` — the **Redl et al., Phys. Plasmas 28, 022502 (2021)**
      update of those coefficients (NEO's ``compute_Sauter_mod``);
    All three come from one solve, so comparing them costs nothing and is
    apples-to-apples: same species, same local geometry, same collisionality.

    ★NCLASS is deliberately NOT among them.  NEO runs it only for
    ``SIM_MODEL`` 1 or 3 ("... with nclass"), and this entry pins
    ``SIM_MODEL = 2`` ("NUMERICAL (with theory)"), so ``jpar_nclass``
    was structurally zero on every call while being advertised as a
    cross-check — a consumer comparing against it was comparing against
    zero.  The key is gone rather than left returning a plausible-looking
    number.  Redl 2021 (``jpar_sauter_2021``) is the modern analytic
    baseline and is the one this repo's own bootstrap gate prefers.
    """
    #: ★the library is NOT loaded here.  It used to be, one line into the
    #: function and above both the Rust dispatch and the recorded oracle, so
    #: a caller asking for the Rust backend still needed libneo present — a
    #: dependency nothing about the request implied, and one that only became
    #: visible when the library was removed.
    n = len(species)
    if n < 1:
        raise NeoclassicalError("bootstrap: need at least one species")
    # Rust path (FYL-DESIGN-02 T1a): NEO is Apache-2.0 (LICENSE 3.2), so
    # the port is a white-box translation and was gated bit-for-bit
    # against this library while it was here.  It covers the
    # DRIFT-KINETIC solve as well as the analytic models: geometry,
    # assembly, a hand-written sparse LU in place of UMFPACK, and the
    # transport moments, with no Fortran in the path.  Measured against
    # libneo+UMFPACK across four species/geometry cases at two
    # resolutions: 1e-14 to 3e-10 relative on jpar and jtor, the residual
    # being the two factorizations' different pivoting rather than the
    # port.
    from ... import kernel
    #: ★`backend=` is accepted and ignored: there is one host (FYL-DESIGN-08
    #: D-4′), so the name is no longer resolved.  The parameter survives
    #: because callers still pass ``backend="rust"``.
    kernel.require()
    #: ★★The marshalling is :mod:`fylite.kernel`'s.  This module used to
    #: call three ABI entries itself, with its own buffers and its own
    #: return-code checks, beside the identical machinery there — the same
    #: defect ``rusteq`` carried.  What is left here is NEO's own
    #: vocabulary: a species list, a named resolution, and which of the
    #: analytic vintages goes with which key.
    #: ★the row order is the kernel's (``NEO_SPECIES_ROWS``), not spelled
    #: again here: ``cols`` is unpacked BY POSITION on the other side of the
    #: ABI, so a transposed pair would be a wrong species field with nothing
    #: able to notice.
    cols = [[float(sp.get(k, 0.0)) for sp in species]
            for k in kernel.NEO_SPECIES_ROWS]
    geo14 = [rmin_over_a, rmaj_over_a, q, shear, shift, 0.0, 0.0,
             kappa, s_kappa, delta, s_delta, zeta, s_zeta, float(n_theta)]
    try:
        sauter = kernel.neo_sauter(cols, geo14, nu_1=nu_1, rho_star=rho_star,
                                   ipccw=ipccw, btccw=btccw,
                                   vintage=kernel.SAUTER_1999)
        redl = kernel.neo_sauter(cols, geo14, nu_1=nu_1, rho_star=rho_star,
                                 ipccw=ipccw, btccw=btccw,
                                 vintage=kernel.REDL_2021)
        #: ★`analytic_only` skips the drift-kinetic solve, which is the
        #: expensive half by three orders: measured at 1.3 s per surface
        #: against ~1 ms for the two analytic branches.  A caller that asked
        #: for an analytic key was paying all of it and throwing the
        #: answer away — ten seconds for eight surfaces, which is the
        #: difference between a gate that runs by default and one that gets
        #: marked slow and then stops running.
        dke = ({} if analytic_only else
               kernel.dke_solve(cols, geo14[:13], n_energy=n_energy,
                                n_xi=n_xi, n_theta=n_theta, nu_1=nu_1,
                                rho_star=rho_star))
    except kernel.KernelError as exc:
        raise NeoclassicalError(str(exc)) from exc
    return {**dke,
            "jpar_sauter": float(sauter[0]), "jtor_sauter": float(sauter[1]),
            "jpar_sauter_2021": float(redl[0]),
            "jtor_sauter_2021": float(redl[1]),
            "kpar": float(sauter[2]), "uparB": float(sauter[3]),
            "ftrap": float(sauter[4]), "i_div_psip": float(sauter[5]),
            "backend": "rust"}


try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    Protocol = object

    def runtime_checkable(cls):
        return cls


@runtime_checkable
class CurrentSource(Protocol):
    """A neoclassical current-source backend.

    ``bootstrap(surfaces)`` takes the per-surface inputs produced by
    :func:`surface_inputs` (each a dict with ``species``, the local Miller
    geometry kwargs, and the surface's ``nu_1`` / ``rho_star`` /
    ``current_unit``) and returns ``<j·B>`` per surface **in A·T/m²**.

    ★★It said "the per-surface parallel current shape ``<j.B>`` (arbitrary
    units — the loop renormalizes to ⟨j⟩=1)", and this is the Protocol — the
    one place the contract is written down rather than implied.  "Arbitrary
    units" was true and was the whole problem: it let
    :func:`fylite.fyo.neoclassical_source` put the number into an IMAS field
    measured in A/m², beside a backend that returned A/m², eight orders
    apart.  A caller that only wants a shape is free to renormalise; a
    contract that declines to name a unit is not free of consequences.

    ★And the reference above named ``neo_surface_inputs``, which is this
    module's OLD name for :func:`surface_inputs` and is also, still, a
    different function in :mod:`fylite.kernel`.  That collision has already
    cost this repository once: a blanket rename of the module-level name
    rewrote the kernel's ABI symbol.
    ``context`` (optional) carries profile/equilibrium data a backend may need
    beyond the surface dicts (e.g. the g-file + n_e/T_e for the analytic
    :class:`fylite.scenario.model.neoclassical.RedlSource`); kernel backends ignore it.
    """

    name: str

    def bootstrap(self, surfaces: list, *, context: dict | None = None) -> list: ...


#: The geometry a :func:`bootstrap` call takes, as this module spells it.
#:
#: ★★DERIVED from the generated table, not written out again.  These are
#: ``_deck_names.NEO_DECK_GEOMETRY`` lowercased, and they were a hand-typed
#: copy of exactly that — the same defect ``test_deck_names_have_one_source``
#: was built to catch for the SPECIES set, hidden from it only by case: its
#: literal detector matches SCREAMING_CASE, so a lowercase copy of an
#: upstream deck order was invisible to the one gate that exists to find one.
#:
#: ★Two of the thirteen are absent on purpose and are named here rather than
#: silently dropped: ``ZMAG_OVER_A`` and ``S_ZMAG`` describe an up-down
#: asymmetric surface, and :func:`bootstrap` does not take them — the kernel
#: entry has no argument for either.  Filtering by an explicit exclusion set
#: means adding a fourteenth deck name upstream shows up here as a KeyError
#: in the caller rather than as a silently ignored input.
_GEO_NOT_TAKEN = frozenset({"ZMAG_OVER_A", "S_ZMAG"})
GEO_KEYS = tuple(n.lower() for n in _deck_names.NEO_DECK_GEOMETRY
                 if n not in _GEO_NOT_TAKEN)


def _geo_kw(s: dict) -> dict:
    return {k: s[k] for k in GEO_KEYS if k in s}


#: The keys of a `bootstrap` result that are CURRENTS and therefore carry
#: NEO's normalisation.  ★A list rather than a prefix match: `i_div_psip`
#: starts with an `i` and is a geometric ratio, and a rule that guessed from
#: the name would scale it.
_CURRENT_KEYS = ("jpar_dke", "jtor_dke", "jpar_sauter", "jtor_sauter",
                 "jpar_sauter_2021", "jtor_sauter_2021")


def _as_current(result: dict, surface: dict) -> dict:
    """One `bootstrap` result with its currents in A·T/m²."""
    try:
        unit = surface["current_unit"]
    except KeyError as exc:
        #: ★REFUSED, not defaulted to 1.0.  A surface with no
        #: `current_unit` cannot yield a current, and substituting one would
        #: hand back NEO's normalised number wearing an amps label — the
        #: exact defect this contract exists to remove.
        raise NeoclassicalError(
            "a surface carries no 'current_unit', so its bootstrap current "
            "has no unit to be in.  Build surfaces with "
            "`neoclassical.surface_inputs`, which computes it from the "
            f"kernel ({exc}).") from exc
    return {k: (v * unit if k in _CURRENT_KEYS else v)
            for k, v in result.items()}


class NeoSource:
    """NEO drift-kinetic bootstrap — the default current source.

    ★It said "(``libneo.so``)".  The solve is the Rust port's
    (:func:`fylite.kernel.dke_solve`), gated against that library to
    1e-14..3e-10 while it was still here; naming the departed binary as the
    backend told a reader to look for a build they cannot do.

    ``bootstrap(...)["jpar_dke"] * current_unit`` per surface: the full
    drift-kinetic ``<j_par·B>``, **in A·T/m²**.  Divide by ``B0`` for the
    IMAS ``j_parallel`` of a ``core_sources`` entry, which is what
    :func:`fylite.fyo.neoclassical_source` does.

    ``resolution`` names a :data:`fylite.scenario.model.neoclassical.RESOLUTION` preset (or gives an
    explicit ``{n_energy, n_xi, n_theta}`` dict) — the knob that decides what a
    solve costs.  Individual ``n_*`` kwargs still win over the preset, so an
    explicit override is never silently replaced.
    """

    name = "neo"

    def __init__(self, *, key: str = "jpar_dke", resolution=None, **neo_kw):
        if key not in _CURRENT_KEYS:
            raise NeoclassicalError(
                f"{key!r} is not one of the NEO solve's currents "
                f"{_CURRENT_KEYS}")
        self._key = key
        #: ★The drift-kinetic branch runs only for a ``*_dke`` key, and that
        #: RULE is here rather than at the call sites.  It used to be an
        #: ``analytic_only=True`` written out by two subclasses whose whole
        #: content it was — so "which answer do I want" and "what has to be
        #: solved to get it" were two independent arguments that had to
        #: agree, and a caller could ask for ``jpar_sauter`` while paying
        #: 1.3 s per surface for a ``jpar_dke`` it discarded.  An explicit
        #: ``analytic_only=`` still wins, for a caller who wants the DKE
        #: solve in ``last_solves`` alongside an analytic answer.
        analytic = {"analytic_only": not key.endswith("_dke")}
        self._neo_kw = {**analytic, **resolution_kwargs(resolution),
                        **neo_kw}
        #: Full per-surface NEO result dicts from the most recent
        #: :meth:`bootstrap` call.  One solve yields ``jpar_dke`` *and* every
        #: analytic baseline NEO evaluates alongside it (``jpar_sauter``,
        #: ``jpar_sauter_2021``), so a consumer wanting a
        #: cross-check should read it from here rather than re-deriving the
        #: same coefficients — same solve, same geometry, same collisionality,
        #: free.
        #:
        #: ★★The ``jpar_*``/``jtor_*`` entries are DENORMALISED, in the same
        #: A·T/m² :meth:`bootstrap` returns.  They are the cross-check for the
        #: number that method hands back, so they have to be in its units:
        #: leaving them in NEO's normalisation would put the primary result
        #: and its own baseline six orders apart inside one object, which is
        #: the defect this contract was changed to remove, one level down.
        #: The rest (``kpar``, ``uparB``, ``ftrap``, ``i_div_psip``) are flow
        #: coefficients, a fraction and a geometric ratio — dimensionless,
        #: untouched, and listed so "no factor" is findable.
        self.last_solves: list = []

    def bootstrap(self, surfaces: list, *, context: dict | None = None) -> list:
        del context
        #: ★`nu_1` and `rho_star` come from the SURFACE, and both are
        #: magnitude-bearing: NEO's currents are linear in `rho_star` and its
        #: collisionality sets the trapped-particle terms.  They used to be
        #: left at `bootstrap`'s nominal defaults for every surface of every
        #: plasma, which is a shape and was consumed as one — until a
        #: document face started reporting it in A/m^2.
        raw = [bootstrap(s["species"], **_geo_kw(s),
                         **{k: s[k] for k in ("nu_1", "rho_star") if k in s},
                         **self._neo_kw)
               for s in surfaces]
        self.last_solves = [_as_current(r, s) for r, s in zip(raw, surfaces)]
        #: ★★A CURRENT comes back — ``<j·B>`` in A·T/m² — not NEO's
        #: normalised number.  That is the whole contract change: NEO
        #: normalises each surface to ITS OWN density and temperature, so the
        #: raw ``jpar`` array is nearly flat and the profile lives entirely in
        #: ``current_unit``.  A consumer that took the raw array for a shape
        #: got a plausible, wrong, almost featureless one — and both kinds of
        #: consumer this package has (the loop, which renormalises to
        #: ``<j> = 1``, and the document face, which reports A/m²) want the
        #: same physical profile.  So the denormalisation happens once, here,
        #: rather than being a step each of them could forget.
        try:
            return [r[self._key] for r in self.last_solves]
        except KeyError as exc:
            raise NeoclassicalError(
                f"the NEO solve returned no {self._key!r} ({exc})") from exc


#: ★★``SauterSource`` and ``Sauter2021Source`` were here, and each was one
#: line: ``super().__init__(key="jpar_sauter", analytic_only=True)`` and the
#: same with ``key="jpar_sauter_2021"``.  They were registered as two more
#: ``current_source`` BACKENDS beside ``neo``, which said there were three
#: models.  There is one: a single NEO call returns ``jpar_dke``,
#: ``jpar_sauter`` and ``jpar_sauter_2021`` together, on the same geometry
#: and the same collisionality, and picking among them is reading a
#: different key of one answer.
#:
#: The give-away was in :func:`fylite.fyo.neoclassical_source`, which
#: carried BOTH spellings in one signature — ``solver="sauter2021"`` and
#: ``solver="neo", key="jpar_sauter_2021"`` were the same call, and its own
#: docstring said ``key`` "selects which of the NEO solve's answers is
#: reported".  ``python/tests/test_model_selection.py`` pins that they agree
#: to the bit.
#:
#: So the family is what genuinely differs: ``neo`` and ``redl``, two
#: different KERNEL FUNCTIONS with a measured 4.1 % / 15.7 % disagreement
#: (the module docstring's adjudication).  The branch within NEO is
#: ``key=``, which :class:`NeoSource` always took.
#:
#: ★The analytic names survive as keys, not as backends:
#:   ``solver="neo", key="jpar_sauter"``       was ``solver="sauter"``
#:   ``solver="neo", key="jpar_sauter_2021"``  was ``solver="sauter2021"``

def surface_inputs(eq, *, ne, te, psin_prof, ti=None, zeff=1.0,
                       mass_i=2.0, **geo_kw) -> list[dict]:
    """Per-surface ``bootstrap`` kwargs from an equilibrium + kinetic profiles.

    ``eq`` an ``fyo:equilibrium`` document (or a g-file at the door);
    ``ne``/``te`` (and optional ``ti``) are profile values on the
    ``psin_prof`` grid (ne in m⁻³, T in eV).  One ion, quasineutral at
    ``n_i = n_e/Z_eff`` (:data:`fylite.scenario.model.closure.ION_MIX`
    ``"effective"``) — NEO's convention, kept.

    Each entry carries NEO's species table, the Miller geometry
    :data:`GEO_KEYS`, and the three numbers a MAGNITUDE needs:

    * ``nu_1`` — this surface's normalising collision frequency;
    * ``rho_star`` — ``rho_s/a``, physical;
    * ``current_unit`` — ``e n_e v_norm B_unit`` [A·T/m²], so that
      ``jpar * current_unit`` is ``<j·B>``
      (:func:`fylite.kernel.neo_current_unit`).

    ★★It used to build the species table from
    :func:`fylite.kernel.neo_surface_inputs`, which normalises every profile
    TO THE FIRST SURFACE and leaves ``nu_1`` at NEO's nominal 0.1, and it
    returned nothing else.  For the loop, which renormalises the current to
    ``<j> = 1``, that was enough and honest.  For
    :func:`fylite.fyo.neoclassical_source`, which writes the result into an
    IMAS field measured in A/m², it was not: a shape computed at somebody
    else's collisionality, put where a current belongs.

    ★So the surface is assembled ONCE now, by the same builder the transport
    closure uses (:func:`fylite.scenario.model.closure.surface_states`), and
    NEO's normalisation is read off the kernel
    (:func:`fylite.kernel.neo_local`) rather than done a second time here.
    That was the other cost of two builders: they disagreed about the ion mix
    AND about the collisionality, and neither disagreement could raise.
    """
    from . import closure
    from ... import kernel as K

    lad = fyo.Ladder(fyo.as_equilibrium(eq),
                     _levels_for(eq, geo_kw))
    ps = lad.psin
    states = closure.surface_states(lad, psin=ps, psin_prof=psin_prof,
                                    ne=ne, te=te, ti=ti, zeff=zeff,
                                    ion_mix="effective")
    out = []
    for st, row in zip(states, lad.miller):
        loc = K.neo_local({**st, "shear": st["s"]},
                          rho_star=st["rho_s"] / st["a"])
        #: the species table is the kernel's, in ITS row order — electrons
        #: first.  Spelling the six names again here is how a transposed
        #: pair becomes a different plasma with nothing to notice.
        cols = [loc[k] for k in K.NEO_SPECIES_ROWS]
        species = [{k: float(cols[j][i]) for j, k in
                    enumerate(K.NEO_SPECIES_ROWS)}
                   for i in range(len(cols[0]))]
        for sp in species:
            #: `bootstrap` reads `dens`/`temp`/`dlnndr`/`dlntdr`; NEO's own
            #: row names are the same six words, so this is a check rather
            #: than a rename
            sp.setdefault("mass", sp.get("mass", mass_i))
        out.append({
            "species": species,
            "rmin_over_a": row["r"], "rmaj_over_a": row["rmaj"],
            "q": row["q"], "shear": row["shear"], "shift": row["shift"],
            "kappa": row["kappa"], "s_kappa": row["s_kappa"],
            "delta": row["delta"], "s_delta": row["s_delta"],
            "zeta": row["zeta"], "s_zeta": row["s_zeta"],
            "psin": row["psin"],
            "nu_1": float(loc["nu_1"]),
            "rho_star": float(st["rho_s"] / st["a"]),
            "current_unit": K.neo_current_unit(
                ne=st["ne"], ti1=st["ions"][0]["ti"], b_unit=st["b_unit"]),
        })
    return out


def _levels_for(eq, geo_kw) -> "np.ndarray":
    """The ψ_N ladder ``miller_geometry`` would have used, so that moving to
    a :class:`fylite.fyo.Ladder` does not silently change WHICH surfaces are
    reported."""
    return fyo._levels(geo_kw.get("psin"), fyo.MILLER_LADDER,
                       int(geo_kw.get("n_surfaces", 24)),
                       float(geo_kw.get("edge", 0.95)))


# --------------------------------------------------------------------------- #
# The standalone Redl-2021 analytic path — no drift-kinetic branch needed.     #
#                                                                             #
# ★It was `scenario/model/redl.py`.  Same quantity as everything above (IMAS  #
# `core_sources` bootstrap_current, index 13), same kernel file               #
# (`neoclassical.rs`), same surfaces — what separated it into its own module  #
# was which Fortran code the Python was once written around.                  #
#                                                                             #
# ★What it is FOR, now that `key="jpar_sauter_2021"` gets the same           #
# coefficient set out of the NEO solve itself: an environment with no         #
# drift-kinetic branch, the coefficients wanted symbolically                  #
# (`coefficients`), and an independent second implementation of the same      #
# paper.  It is not the preferred baseline and its docstring has said so      #
# since before the merge.                                                     #
# --------------------------------------------------------------------------- #

#: ★``trapped_fraction`` and ``coefficients`` used to sit here, each a
#: one-line forward to :func:`fylite.kernel.trapped_fraction_eps` and
#: :func:`fylite.kernel.redl_coefficients` with the same arguments and no
#: work of its own.
#:
#: Not a second implementation — a second NAME, which is a smaller thing and
#: a harder one to see: one quantity reachable by two paths, with two
#: docstrings free to drift.  What hid them was their neighbours in
#: ``nbi.py``: four functions that look identical and are not, because each
#: restores the caller's scalar-or-array shape.  A bare alias standing next
#: to four that earn their keep reads as one of them.
#:
#: Callers use the kernel directly now.

def _total_pressure(source, surf, ne_s, te_s, ni_s, ti_s, ps) -> np.ndarray:
    """Total thermal pressure (Pa) on the surface grid, per ``pressure_source``.

    ``kinetic`` builds it from the caller's own profiles — ``p = (nₑTₑ + nᵢTᵢ)e``
    — so the pressure gradient that drives the bootstrap is the *same* profile
    set the collisionality and L-coefficients see.  ``gfile`` takes the
    reconstruction's own ``pres`` instead and **validates** it: a
    magnetics-only reconstruction routinely returns a non-physical (negative)
    outer pressure, and flooring that to a small positive value would zero
    ``dP/dψ`` over the whole outer half — silently deleting the dominant
    ``L31·∇p`` term and moving the ``j_bs`` peak inward.  That failure mode is
    raised, never floored.

    ★Both branches now read a KERNEL-resampled profile: the g-file pressure
    rides the same interpolation as ``ne``/``te``/``fpol``
    (:func:`fylite.kernel.redl_surface_inputs`'s ``p_gfile`` row).  It used
    to be resampled here with a second interpolator, which was the last
    place two of one surface's inputs could disagree about that surface.
    """
    if source == "kinetic":
        #: the kernel's: the pressure that drives the bootstrap has to be
        #: built from the SAME profile set the coefficients see
        return kernel.redl_drive(ne_s, te_s, ni_s, ti_s, ps,
                                 psi_axis=0.0, psi_bnd=1.0)[0]
    if source != "equilibrium":
        #: ★``'gfile'`` was this value's name and is refused rather than
        #: aliased: it selects the EQUILIBRIUM's own pressure profile, which
        #: arrives from a document as readily as from a deck.  A silent alias
        #: would keep the wrong word alive in every caller that has one.
        hint = (" — that value is 'equilibrium' now; it never meant the file "
                "format, only whose pressure to use"
                if source == "gfile" else "")
        raise RedlError("pressure_source must be 'kinetic' or 'equilibrium', "
                        f"not {source!r}{hint}")
    #: ``p_gfile`` is the KERNEL's row name (`redl_surface_inputs`), left as
    #: the kernel spells it — this package does not rename the ABI.
    p_th = surf["p_gfile"]
    bad = int(np.count_nonzero(p_th <= 0.0))
    if bad:
        raise RedlError(
            f"pressure_source='equilibrium': {bad}/{len(p_th)} surfaces have "
            f"non-physical total pressure (min {p_th.min():.4g} Pa) — this "
            "equilibrium's pressure cannot drive a bootstrap evaluation (flooring it "
            "would zero dP/dpsi and delete the dominant L31 term). Use "
            "pressure_source='kinetic' to build p from the ne/te you passed.")
    return p_th


def bootstrap_profile(eq, ne, te, *, psin_prof=None, ti=None, zeff=1.0, ni=None,
                      z_ion=1.0, n_surfaces=32, collisionless=False,
                      pressure_source: str = "kinetic") -> dict:
    """Redl-2021 analytic bootstrap ``<j·B>`` from an equilibrium + kinetic profiles.

    ``eq`` is an ``fyo:equilibrium`` document (or a g-file at the door);
    ``ne`` (m⁻³) and ``te`` (eV) are profiles on
    ``psin_prof`` (default a uniform ψ_N grid matching their length), optional
    ``ti``/``ni``/``zeff``/``z_ion``.  Per-surface Miller geometry (ε, q) comes
    from :func:`fylite.fyo.miller_geometry`; ``collisionless=True`` drops
    the ν* corrections (the analytic ceiling).

    ``pressure_source`` selects what drives ``dP/dψ`` (see :func:`_total_pressure`):
    ``"kinetic"`` (default) derives ``p`` from the passed ``ne``/``te``(/``ti``),
    which keeps every term of the formula on one self-consistent profile set;
    ``"equilibrium"`` uses the equilibrium's own ``pressure`` profile and **raises**
    :class:`RedlError` when that profile is non-physical rather than flooring it.

    Returns ``{psin, j_bs, L31, L32, L34, alpha, ft, nu_e_star, nu_i_star, eps,
    pressure_source}`` — ``j_bs`` is ``|<j·B>|/B0`` (A/m², axis pinned to 0).
    Magnitude carries the usual analytic-normalization caveat; the *shape* is the
    cross-check, and it is gated against NEO (``tests/test_bootstrap_gate.py``).
    """
    doc = fyo.as_equilibrium(eq)
    ne = np.asarray(ne, float)
    if psin_prof is None:
        psin_prof = np.linspace(0.0, 1.0, len(ne))

    geo = fyo.miller_geometry(doc, n_surfaces=n_surfaces)
    ps = np.array([row["psin"] for row in geo])

    #: ★the profiles-onto-surfaces map is the KERNEL's, floors and clips
    #: included (10 eV on T before the interpolation, ε into [1e-4, 0.99],
    #: |q| ≥ 1e-3, Z_eff into the fitted [1, 10], the quasineutral default
    #: ion density).  Each of those is a physics statement whose failure
    #: mode is a wrong bootstrap current rather than an exception, which is
    #: exactly why they may not be spelled per caller.
    m = kernel.redl_surface_inputs(
        ps, [row["r"] for row in geo], [row["rmaj"] for row in geo],
        [row["q"] for row in geo], psin_prof=psin_prof, ne=ne, te=te,
        ti=ti, ni=ni, zeff=zeff, f_table=fyo.profile_of(doc, "f"),
        p_table=fyo.profile_of(doc, "pressure"))
    eps, q_abs = m["eps"], m["q_abs"]
    ne_s, te_s, ti_s, ni_s = m["ne"], m["te"], m["ti"], m["ni"]
    p_th = _total_pressure(pressure_source, m, ne_s, te_s, ni_s, ti_s, ps)
    r0 = fyo.axis_of(doc)[0] or fyo.field_of(doc)[0] or 1.75
    b0 = abs(fyo.field_of(doc)[1]) or 1.0

    #: ψ per radian — the normalisation the coefficients are written in, and
    #: the kernel's: the per-turn value scales every gradient term by 2π,
    #: which is a plausible-looking bootstrap wrong by exactly that factor
    _, psi_bar = kernel.redl_drive(ne_s, te_s, ni_s, ti_s, ps,
                                   psi_axis=fyo.psi_range_of(doc)[0],
                                   psi_bnd=fyo.psi_range_of(doc)[1])
    out = kernel.redl_bootstrap(
        eps=eps, q_abs=q_abs, ne=ne_s, te=te_s, ti=ti_s, ni=ni_s,
        zeff=m["zeff"], p_th=p_th, i_psi=m["i_psi"], psi_bar=psi_bar,
        r_maj=r0, b0=b0, z_ion=z_ion, collisionless=collisionless)
    j_bs = out["j_bs"]
    if len(j_bs):
        #: ∇ψ→0 on axis, so j_bs(0) = 0.  The kernel leaves it as computed
        #: because only this side knows whether the innermost surface IS
        #: the axis; on this ladder it is.
        j_bs[0] = 0.0
    return {"psin": ps, "j_bs": j_bs, "L31": out["L31"], "L32": out["L32"],
            "L34": out["L34"], "alpha": out["alpha"], "ft": out["ft"],
            "nu_e_star": out["nu_e_star"], "nu_i_star": out["nu_i_star"],
            "eps": eps, "pressure_source": pressure_source}


# --------------------------------------------------------------------------- #
# Current-source model (K-18 named it a "current_source" backend, declared
# in fylite/_backends.py; both the registry and that table are retired —
# FYL-SDD-01 DE-LOG-03) — this module's analytic model behind the same
# interface as the NEO-backed sources (fylite.scenario.model.neoclassical.CurrentSource).
# --------------------------------------------------------------------------- #

class RedlSource:
    """Redl-2021 analytic bootstrap — the standalone transcription, the
    IMAS.jl lineage, and the adopted spelling of the paper (see the module
    docstring's adjudication).

    ★★It said "**pure Python** (this module) — NOT a kernel".  Both halves
    are false and have been since the transcription moved into Rust:
    :func:`bootstrap_profile` below runs entirely on
    :func:`fylite.kernel.redl_surface_inputs`,
    :func:`~fylite.kernel.redl_drive` and
    :func:`~fylite.kernel.redl_bootstrap`.  The module header says so
    correctly three paragraphs up, so the file asserted both at once — and
    "NOT a kernel" is the sentence a reader would act on when deciding
    where the physics lives.

    What survives the correction is what the word INDEPENDENT was doing.
    This is a different kernel function from the one NEO's own solve uses:
    ``redl_coefficients`` evaluates the ``f31`` fit at a second effective
    trapped fraction to get L34, ``sauter_redl`` (behind ``sauter2021``)
    sets ``L34 = L31``.  They agree to the bit on the collisionless axis and
    differ by 4.1 % at ν* = 0.1 and 15.7 % at ν* = 1 — two implementations
    of one paper, not two names for one function.  The other difference is
    the ENTRY: this one is profile-level and needs ``context``, and it is
    reached without a drift-kinetic branch at all.

    Needs the g-file + kinetic profiles via ``context``
    (``gfile``/``ne``/``te``/``psin_prof``/…), computes ``<j·B>`` over the
    whole profile, and returns it interpolated onto the surface ψ_N grid.
    ``collisionless=True`` selects the ν*-free ceiling; ``pressure_source``
    (default ``"kinetic"``) is passed through — with ``"equilibrium"`` a non-physical
    reconstruction pressure raises instead of being floored."""

    name = "redl"

    def __init__(self, *, collisionless: bool = False, **redl_kw):
        self._collisionless = collisionless
        self._redl_kw = redl_kw

    def bootstrap(self, surfaces: list, *, context: dict | None = None) -> list:
        if not context or context.get("eq") is None:
            #: ★``engine.BackendError``, imported here, used to be what this
            #: raised — a REGISTRY error for a model complaining about its
            #: own inputs, which put the mechanism in the traceback of a
            #: physics mistake.  The registry is retired (FYL-SDD-01
            #: DE-LOG-03) and this is this module's error.
            raise NeoclassicalError(
                "the 'redl' current source needs context={'eq', 'ne', 'te', "
                "'psin_prof', ...} — it is a profile-level analytic model, not "
                "a per-surface kernel")
        prof = bootstrap_profile(
            context["eq"], context["ne"], context["te"],
            psin_prof=context.get("psin_prof"), ti=context.get("ti"),
            zeff=context.get("zeff", 1.0), collisionless=self._collisionless,
            **self._redl_kw)
        ps = [s["psin"] for s in surfaces]
        return list(kernel.interp(ps, prof["psin"], prof["j_bs"]))
