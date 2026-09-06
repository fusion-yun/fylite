"""The TGLF turbulent transport model — deck grammar over the Rust port.

★**Why the file is named for the model and not for the code.**  The
capability this package exposes is ``S.model.tglf(...)``, a function in
this package's ``__init__``; a module called ``tglf`` beside it would be
shadowed by that function on every ``from . import tglf``, silently, since
a function has attributes too.  ``gyrofluid`` is the name the KERNEL module
this fronts already carries (``rust/fylite/src/gyrofluid.rs``), so the two
halves of the port share a name and the capability keeps the one callers
type.

TGLF (GACODE, Staebler et al.) is the trapped-gyro-Landau-fluid quasilinear
model: from local flux-surface geometry + kinetic profiles it returns the
gyro-Bohm-normalized turbulent particle / energy / momentum fluxes (transport
model), or the linear eigenvalues of a single ``ky`` (stability mode).

★**What this module is, after the library left.**  It is the ``input.tglf``
NAME/VALUE GRAMMAR and nothing else: which name means which slot of the
kernel's packed argument arrays, and what a missing name defaults to.  The
solve, the matrix assembly, the ky spectrum, the derived units, and the
three rules libtglf applies to a deck before it solves anything are the
kernel's (``rust/fylite/src/gyrofluid.rs``, reached through
:mod:`fylite.kernel`).

★★It used to declare its own ``ctypes`` ``argtypes`` at five call sites and
marshal its own buffers beside the identical machinery in
:mod:`fylite.kernel` — the same defect ``rusteq`` carried, and the reason
both are gone: a second marshalling of one entry drifts in what it raises
and in how it sizes a buffer, and nothing can catch it because both are
"right".

Where NEO gives the neoclassical (collisional) transport and the bootstrap
current, TGLF gives the turbulent part; both take the same local Miller
description of a surface, so a coupling layer can drive them from one
reconstruction.

★libtglf WAS not re-entrant — module state, and ``tglf_error`` called
``STOP`` on a fatal — and this module said so in the present tense, ending
with "in a loop, call it fork-isolated".  Nothing here can fail that way:
every entry below is a pure function over its arguments.  The replay that
carried the isolation entry is a test fixture
(``tests/oracles/tglf.py``).
"""
from __future__ import annotations

from ..._deck_names import (TGLF_DECK_SPECIES,
                            TGLF_DECK_SPECIES_KYGRID,
                            TGLF_DECK_SPECIES_ROTATING,
                            TGLF_DECK_SPECIES_PRESSURE,
                            TGLF_MILLER_SLOTS)
from ... import kernel


class TglfError(RuntimeError):
    """A TGLF call was refused, or the deck it was given is not one this
    port can answer for (a missing species row, an unported branch, a
    width that was never stated, a kernel refusal).

    ★It used to read "unknown input name, bad index, non-zero status",
    which were ``libtglf.so``'s three failures, not this module's.  The
    replay in ``tests/oracles/tglf.py`` raises it too, for the one
    that survived: a deck that was never recorded."""


#: ★``NSM``, ``_INT_KEYS``, ``_VECTOR_KEYS``, ``_split_index``, ``_as_int``,
#: ``species_inputs``, ``run``, ``run_inputs`` and ``run_isolated`` were
#: here.  They were the ``input.tglf`` NAMELIST half — a species list to
#: suffixed keys, a deck to a RECORDED answer, and the isolation entry
#: libtglf's module state used to need.  The recordings are a fixture, so
#: they live in ``tests/oracles/tglf.py`` now; what stays here is the
#: grammar the PORT reads.
#:
#: ★★Three of them were dead where they stood.  ``_split_index`` (with
#: ``_VECTOR_KEYS`` and ``_as_int`` behind it) had no caller in this module
#: or any other — the identical dead trio was already found and removed from
#: ``fylite.io.gacode``, and ``_VECTOR_KEYS`` was meanwhile being held up by
#: ``test_deck_names_have_one_source`` as a LIVE consumer of a generated
#: table, which is the exact failure that case's own docstring records
#: having been fixed for once before.  A name pinned by a test is not a use.


# ---------------------------------------------------------------------
# The Rust linear solver
# ---------------------------------------------------------------------

def _presets(inputs: dict, nbasis_max: int) -> dict:
    """``{XNU_MODEL, WDIA_TRAPPED}`` for this deck — the kernel's.

    ★These are statements about the LIBRARY, not the model, and the kernel
    is where they belong: ``USE_PRESETS`` is hardcoded ``.TRUE.`` in
    ``tglf_startup.f90`` (a local variable, not an input — nothing can turn
    it off) and it overwrites ``xnu_model_in`` from ``sat_rule_in``, so a
    caller's ``XNU_MODEL`` is discarded and the ``xnu_*`` family that
    models 0 and 1 would select is unreachable from any input.  The same
    entry refuses an odd ``NBASIS_MAX`` and a non-zero ``VPAR_MODEL`` — see
    :func:`fylite.kernel.tglf_presets` for what each of those costs.
    """
    try:
        return kernel.tglf_presets(
            sat_rule=int(inputs.get("SAT_RULE", 0)), nbasis_max=nbasis_max,
            vpar_model=int(inputs.get("VPAR_MODEL", 0)))
    except kernel.KernelError as exc:
        raise TglfError(str(exc)) from exc


def _with_derived_units(inputs: dict) -> dict:
    """Fill in R_UNIT, Q_UNIT, B_UNIT and FT from the flux surface.

    They used to be required of the caller, which was a defect rather
    than a convenience: the geometry stage computes all four, so asking
    for them invited a mismatch between the numbers used to build the
    matrix and the ones used to scale it.  Supplied values still win —
    a caller reproducing a specific reference run needs to be able to
    pin them — but nothing has to supply them.
    """
    if all(k in inputs for k in ("R_UNIT", "Q_UNIT", "B_UNIT", "FT")):
        return inputs
    try:
        derived = kernel.tglf_units(
            _miller14(inputs),
            p_prime=float(inputs.get("P_PRIME_LOC", 0.0)),
            q_prime=float(inputs.get("Q_PRIME_LOC", 16.0)),
            width=float(inputs["WIDTH"]),
            theta_trapped=float(inputs.get("THETA_TRAPPED", 0.7)))
    except kernel.KernelError as exc:
        raise TglfError(str(exc)) from exc
    out = dict(inputs)
    for name, v in derived.items():
        out.setdefault(name, v)
    return out


#: What an absent key means, by deck name.  ★One spelling: these defaults
#: used to be written out three times (the units call, the linear pack and
#: the flux pack), so a deck could describe three slightly different
#: surfaces inside one chain.
#:
#: ★★The ORDER is not here.  It is `TGLF_MILLER_SLOTS`, generated from the
#: kernel — a 14-slot positional block, and a subtle one: the same deck
#: names appear in `TGLF_DECK_GEOMETRY` in a DIFFERENT order, because that
#: one is the order `tglf_local` returns values in and this is the order
#: `tglf_units` reads them.  Two contracts sharing a vocabulary is exactly
#: the pair someone collapses by mistake, so the host holds neither order.
#:
#: What the host does own is the defaults: "a missing KAPPA_LOC means 1.0"
#: is the deck grammar's statement about an absent key, not the kernel's
#: about a slot.
_MILLER_DEFAULTS = {
    "RMIN_LOC": 0.5, "RMAJ_LOC": 3.0, "ZMAJ_LOC": 0.0, "Q_LOC": 2.0,
    "KAPPA_LOC": 1.0, "S_KAPPA_LOC": 0.0, "DELTA_LOC": 0.0,
    "S_DELTA_LOC": 0.0, "ZETA_LOC": 0.0, "S_ZETA_LOC": 0.0,
    "DRMAJDX_LOC": 0.0, "DZMAJDX_LOC": 0.0, "DRMINDX_LOC": 1.0, "MS": 128,
}
_MILLER_KEYS = tuple((k, _MILLER_DEFAULTS[k]) for k in TGLF_MILLER_SLOTS)


def _miller14(inputs: dict) -> list:
    return [float(inputs.get(k, d)) for k, d in _MILLER_KEYS]


#: The species rows a linear solve cannot proceed without — the GENERATED
#: table, not spelled again.  ★It is exactly ``TGLF_DECK_SPECIES``, and
#: writing those six words here was caught by
#: ``test_no_host_reproduces_a_generated_deck_order`` on the first run: a
#: second spelling of a positional deck order is a second chance to
#: transpose two of them.
#:
#: ★``VPAR``/``VPAR_SHEAR`` are the difference between this and
#: ``TGLF_DECK_SPECIES_ROTATING``: optional in ``input.tglf`` and absent from
#: most decks, where a missing key means NO ROTATION and zero is right.  The
#: other six are the plasma.
_REQUIRED_SPECIES = frozenset(TGLF_DECK_SPECIES)


def _species(inputs: dict, names, ns: int) -> list:
    """Per-species arrays in the kernel's order, in EITHER deck grammar.

    ``input.tglf`` numbers species in the KEY — ``ZS_1``, ``ZS_2`` — and that
    is what a deck written by
    ``oracles.mapping.tglf_inputs``, or read from a real
    file, carries.  A bare ``ZS: [-1.0, 1.0]`` is the packed form the kernel
    entries take.  Both are accepted here; the suffixed form wins nothing by
    being second-class, because it is the one that actually appears on disk.

    ★★It read ONLY the bare form, and silently returned zeros for anything it
    did not find.  A deck in the file grammar therefore reached the kernel
    with every species row zeroed — an eigenproblem with no plasma in it —
    and the QR iteration ran to its iteration cap and returned ``-1``.  That
    error names ``linalg.rs``, so the diagnosis pointed at the eigensolver,
    and the closure's TGLF channel looked like a numerics failure at every
    width and every ``ky`` on every surface.  It was a missing rename.

    ★So a required row that is absent in BOTH grammars now raises.  Defaulting
    the plasma to zero is not a default, it is a different problem.
    """
    out = []
    for name in names:
        v = inputs.get(name)
        if v is None:
            #: the file grammar: `NAME_1` .. `NAME_ns`
            per = [inputs.get(f"{name}_{i + 1}") for i in range(ns)]
            if all(x is not None for x in per):
                v = [float(x) for x in per]
            elif name in _REQUIRED_SPECIES:
                have = [f"{name}_{i + 1}" for i, x in enumerate(per)
                        if x is not None]
                raise TglfError(
                    f"{name} is missing: a species row the solve needs, in "
                    f"neither the packed form ({name}) nor the deck form "
                    f"({name}_1..{name}_{ns})"
                    + (f"; found only {have}" if have else "")
                    + ".  Zeroing it would hand the kernel an eigenproblem "
                      "with no plasma in it.")
            else:
                v = [0.0] * ns
        elif isinstance(v, (int, float)):
            v = [float(v)] * ns
        out.append([float(x) for x in list(v)[:ns]])
    return out


def _pack_linear(inputs: dict) -> dict:
    """The kernel's argument pack for one linear solve.

    ★It was shared by :func:`linear_kernel` and ``dispersion_matrices``, so
    that the matrices exported for anchoring were the ones the solve
    actually used — a second copy of this packing would be a second place
    for a deck to be interpreted differently.  The second caller is gone
    (see the note where it stood); the reason to keep the packing in one
    place is unchanged.

    ★Everything here is GRAMMAR: which name fills which slot, and what a
    missing name means.  The three rules that are not grammar — the
    collision presets, and the refusals of an odd ``NBASIS_MAX`` and a
    non-zero ``VPAR_MODEL`` — are the kernel's (:func:`_presets`), because
    they are statements about what libtglf does to a deck rather than about
    what this reader thinks a deck says.
    """
    ns = int(inputs["NS"])
    for name in ("WIDTH", "KY"):
        if name not in inputs:
            raise TglfError(
                f"{name} is required: the Rust path does not search for "
                "a width, so the caller must state one"
            )
    inputs = _with_derived_units(inputs)
    nbasis = int(inputs.get("NBASIS_MAX", 4))
    pre = _presets(inputs, nbasis)

    miller = _miller14(inputs) + [
        float(inputs.get("P_PRIME_LOC", 0.0)),
        float(inputs.get("Q_PRIME_LOC", 16.0)),
        float(inputs["WIDTH"]), float(inputs.get("KX0_LOC", 0.0)),
    ]
    scal = [float(inputs["KY"]), float(inputs["R_UNIT"]),
            float(inputs["Q_UNIT"]), float(inputs["B_UNIT"]),
            float(inputs.get("SIGN_BT", 1.0)), float(inputs["FT"]),
            # collisions.  XNUE defaults to zero, which reproduces every
            # result anchored before the collision operator was ported.
            float(inputs.get("XNUE", 0.0)),
            float(inputs.get("ZEFF", 1.0)),
            float(pre["XNU_MODEL"]),
            float(inputs.get("XNU_FACTOR", 1.0)),
            float(inputs.get("PARK", 1.0)),
            float(pre["WDIA_TRAPPED"]),
            float(inputs.get("THETA_TRAPPED", 0.7)),
            # rotation.  VPAR_MODEL is refused above unless it is 0, and
            # ALPHA_MACH defaults to 0, so VPAR alone still moves nothing.
            float(inputs.get("VPAR_MODEL", 0)),
            float(inputs.get("ALPHA_MACH", 0.0)),
            float(inputs.get("ALPHA_P", 1.0)),
            float(inputs.get("SIGN_IT", 1.0)),
            # magnetic
            float(inputs.get("BETAE", 0.0)),
            float(bool(int(inputs.get("USE_BPER", 0)))),
            float(bool(int(inputs.get("USE_BPAR", 0)))),
            float(inputs.get("DAMP_PSI", 0.0)),
            float(inputs.get("DAMP_SIG", 0.0)),
            float(inputs.get("LINSKER_FACTOR", 0.0)),
            # ★USE_MHD_RULE defaults to TRUE, which ZEROES the pressure
            # term in the drift.  Defaulting it to false here made every
            # finite-P_PRIME deck wrong and no zero-P_PRIME deck notice.
            float(bool(int(inputs.get("USE_MHD_RULE", 1)))),
            # ★WD_ZERO — the floor `modwd` clamps small |w_d| eigenvalues
            # to, and NOT a numerical epsilon: the library default is
            # 0.1, which is large enough to reshape the drift matrix
            # whenever an eigenvalue falls inside it.  This port passed
            # 1e-12, so the clamp never fired.
            float(inputs.get("WD_ZERO", 0.1))]
    #: ★this block is the 25-slot LINEAR contract; the flux chain builds
    #: its own 32-slot one below.  Appending here too (the first attempt
    #: did) hands `tglf_linear` 27 numbers and it refuses — correctly.
    return {"ns": ns, "nbasis": nbasis, "miller": miller, "scal": scal,
            "nxgrid": int(inputs.get("NXGRID", 16)),
            "arrays": _species(inputs, TGLF_DECK_SPECIES_ROTATING, ns)}


def linear_kernel(inputs: dict, *, nmodes: int = 2) -> dict:
    """One linear TGLF solve through the Rust port.

    This is the same physics as ``USE_TRANSPORT_MODEL=0`` in an
    ``input.tglf``, computed by :mod:`fylite`'s own port rather than by
    ``libtglf.so``.  It exists for the reason the port did: libtglf was
    not re-entrant, so the Fortran path cost a process launch per call,
    while this one is a plain function.

    The port covers the **electrostatic, collisionless** configuration
    with ``VPAR_MODEL=2`` and ``NBASIS>1``.  Every other branch raises
    rather than returning a quietly reduced answer — a collisional or
    finite-beta case is not silently run without those terms.

    ``inputs`` takes the ``input.tglf`` names for the subset that
    applies.  ``WIDTH`` and the unit normalisations must be given:
    unlike the Fortran, this entry point does not bisect for the width,
    so the caller says which operating point it wants.

    Returns ``{"growthrate": [...], "frequency": [...]}``.
    """
    packed = _pack_linear(inputs)
    try:
        return kernel.tglf_linear(packed["miller"], packed["scal"],
                                  packed["arrays"], ns=packed["ns"],
                                  nbasis=packed["nbasis"],
                                  nxgrid=packed["nxgrid"], nmodes=nmodes)
    except kernel.KernelError as exc:
        raise TglfError(str(exc)) from exc


#: ★★``dispersion_matrices`` stood here — ``_pack_linear`` plus
#: :func:`fylite.kernel.tglf_matrices`, exposing the A and B matrices of one
#: linear solve so that "is the MATRIX wrong or is the SOLVE wrong" stays
#: two questions.  That is worth having and it is the KERNEL entry that has
#: it: this wrapper had no caller in the package, the tests, the browser or
#: the docs.  A debugging entry nobody can be shown to have used is a second
#: name for ``kernel.tglf_matrices``.
#:
#: ★It also used to return a ``"fortran"`` key beside ``"rust"``; libtglf
#: left with LICENSE 3.2 and the element-level anchors it provided are
#: recorded in the kernel's own ``libtglf_anchor`` tests.


def _units_ky_factor(inputs: dict, sat_rule: int) -> float:
    """Upstream's `ky_factor`: 1 under GYRO units, `grad_r0` under CGYRO.

    ★★**It is not a deck key.** `KY_FACTOR` appears nowhere in upstream's
    input list — `tglf_kygrid.f90` opens by setting it from `UNITS`
    (`= 1.0` for GYRO, `= grad_r0_out` for CGYRO).  This host used to pass
    the deck key it invented, defaulting to 1, so **every SAT_RULE >= 2
    run built its spectrum on a grid stretched wrong by `grad_r0`** —
    8.2 % low on the JINTRAC x = 0.758 deck (ours 0.10130 at every point
    against upstream's 0.10961, a constant 0.92413 = 1/1.0821).

    ★It survived because the flux is an integral over a smooth spectrum:
    a uniformly rescaled grid still gives a plausible number.  It showed
    up only when the per-ky spectra were compared point by point (T-C29).

    The units themselves are the preset's, not the caller's — the same
    ruling `fluxes_kernel` already applies to the intensity — so this is
    decided here rather than read from the deck.
    """
    if sat_rule < 2:
        return 1.0
    q = float(inputs["Q_LOC"])
    rmin = float(inputs["RMIN_LOC"])
    #: `S_LOC` is not a deck field: upstream carries the shear as
    #: `Q_PRIME_LOC = q^2 s / r^2`, so it is inverted here rather than
    #: asked for
    shear = float(inputs["Q_PRIME_LOC"]) * rmin * rmin / (q * q)
    g = kernel.geo_surface(
        rmin_over_a=rmin, rmaj_over_a=float(inputs["RMAJ_LOC"]), q=q,
        shear=shear, drmaj=float(inputs.get("DRMAJDX_LOC", 0.0)),
        zmag=float(inputs.get("ZMAJ_LOC", 0.0)),
        dzmag=float(inputs.get("DZMAJDX_LOC", 0.0)),
        kappa=float(inputs["KAPPA_LOC"]),
        s_kappa=float(inputs.get("S_KAPPA_LOC", 0.0)),
        delta=float(inputs.get("DELTA_LOC", 0.0)),
        s_delta=float(inputs.get("S_DELTA_LOC", 0.0)),
        zeta=float(inputs.get("ZETA_LOC", 0.0)),
        s_zeta=float(inputs.get("S_ZETA_LOC", 0.0)))
    return float(g["grad_r0"])


def ky_grid_kernel(inputs: dict) -> dict:
    """The ky spectrum a ``KYGRID_MODEL`` implies, and its gyroradii.

    Saves the caller from supplying a ky table, and from getting one
    subtly different from the reference's: model 1 — the default — is
    nine linear points to ``k_theta rho_ion = 0.9`` followed by
    ``NKY`` LOGARITHMIC points out to ``k_theta rho_e = 0.4``, which is
    not a grid one writes down by hand.

    Returns ``{"ky": [...], "dky": [...], "rho_ion": ..., "rho_e": ...}``.

    ★``USE_AVE_ION_GRID`` is read here and defaults to 0, as upstream's
    does: the grid is built on the FIRST ion unless the deck asks for the
    charge-weighted average.
    """
    ns = int(inputs["NS"])
    try:
        return kernel.tglf_kygrid(
            _species(inputs, TGLF_DECK_SPECIES_KYGRID, ns), ns=ns,
            kygrid_model=int(inputs.get("KYGRID_MODEL", 1)),
            nky=int(inputs.get("NKY", 12)),
            ky=float(inputs.get("KY", 0.3)),
            #: ★the library default is FALSE — the FIRST ion, not the
            #: charge-weighted average.  See `kernel.tglf_kygrid`.
            use_ave_ion_grid=bool(int(inputs.get("USE_AVE_ION_GRID", 0))),
            ky_factor=float(inputs.get("KY_FACTOR", 1.0)))
    except kernel.KernelError as exc:
        raise TglfError(str(exc)) from exc


def fluxes_kernel(inputs: dict, ky=None, *, sat_rule: int = 1,
                find_width: bool = False, nmodes: int = 1,
                stress: bool = False) -> dict:
    """Transport fluxes from a ky spectrum, through the Rust port.

    ★``stress=True`` asks for the two momentum rows (``stress_tor`` /
    ``stress_par``) in the answer.  They live on the searched entry point
    — the plain one has no room for them — so this routes there with the
    search OFF (``nwidth=0``) and the mode count untouched, which is the
    SAME run: same width, same modes, same fluxes bit for bit (asserted
    in ``tests/test_closure.py``).  It costs nothing but the two extra
    rows, and it is a separate flag from ``find_width`` because asking
    for a channel and asking for a width search are different requests
    that happened to share a doorway.

    The whole chain in one call: a linear solve at each ``ky``, the
    zonal-flow saturation, and ``flux = intensity * quasilinear weight``
    integrated over the spectrum.

    All three saturation rules.  Rule 3's amplitude comes from the
    quasilinear weights themselves — the electron share of the energy
    flux at the mixing peak decides whether a mode is treated as ITG or
    TEM — so it needed the flux layer before it could be wired.

    Like :func:`linear_kernel`, the operating point is the caller's to
    state: ``WIDTH`` is required, because this path does not bisect for
    one.  ``R_UNIT``, ``Q_UNIT``, ``B_UNIT`` and ``FT`` follow from the
    surface and the width (:func:`_with_derived_units`), and ``RHO_ION``
    from the ky grid, so only the width has to be said.

    Returns ``{"particle": [...], "energy": [...], "exchange": [...],
    "growthrate": [...], "frequency": [...]}`` — the first three per
    species, the last two per ``ky``.
    """
    if sat_rule not in (1, 2, 3):
        raise TglfError(
            f"SAT_RULE={sat_rule} is not a saturation rule "
            "(1, 2 and 3 are ported)"
        )
    #: ★★ONE saturation rule per call.  It was spelled twice: the
    #: ``sat_rule=`` argument reached the kernel's flux integral, while
    #: ``_presets`` below read ``inputs["SAT_RULE"]`` — and a deck that
    #: does not carry the name defaults it to 0 there.  So
    #: ``fluxes_kernel(deck, sat_rule=2)`` on a deck without ``SAT_RULE``
    #: integrated rule 2 with rule 0's presets, which is to say with
    #: ``XNU_MODEL=2`` and ``WDIA_TRAPPED=0`` instead of 3 and 1.  That is
    #: the same pair the linear tests measure at 5.5-11.4 % on the
    #: SAT_RULE 2/3 path, re-entering through the second spelling.
    #:
    #: The argument is the spelling.  A deck that also names the rule must
    #: agree with it rather than be silently overruled either way.
    deck_rule = inputs.get("SAT_RULE")
    if deck_rule is not None and int(deck_rule) != sat_rule:
        raise TglfError(
            f"the deck says SAT_RULE={int(deck_rule)} and the call says "
            f"sat_rule={sat_rule}: one call runs one rule, and the "
            "presets (XNU_MODEL, WDIA_TRAPPED) come from it")
    inputs = {**inputs, "SAT_RULE": sat_rule}
    #: ★★``UNITS`` decides whether the saturated intensity carries the
    #: flux-surface geometry weight, and the kernel applies the LIBRARY'S
    #: PRESET rather than the deck's word: ``tglf_startup.f90`` forces
    #: CGYRO for rules 2 and 3 and GYRO for rule 0, and leaves rule 1 at
    #: the caller's (default GYRO).  A deck that asks for something else
    #: is refused rather than answered in the other units — the difference
    #: is a factor ``SAT_geo0`` (1.115 on the anchored surface), which is
    #: exactly the size that passes for "close enough" and is not.
    units = str(inputs.get("UNITS", "")).strip().upper() or None
    if units is not None:
        applied = "CGYRO" if sat_rule >= 2 else "GYRO"
        if units != applied:
            raise TglfError(
                f"UNITS={units} with SAT_RULE={sat_rule}: this path applies "
                f"the library's preset ({applied}) and cannot be told "
                "otherwise — the units field has nowhere to ride in the "
                "kernel's scalar block (FEATURE.md §3.2)")
    if ky is None:
        #: ★★the ky GRID carries the units preset too, and it did not
        #: until 2026-08-29.  Upstream's `tglf_kygrid.f90` opens with
        #: `ky_factor = 1.0` for GYRO and `= grad_r0_out` for CGYRO, so a
        #: rule-2 run's whole spectrum is stretched by `grad_r0`.  This
        #: host passed `KY_FACTOR` — a key upstream does not have —
        #: defaulting to 1, so every SAT_RULE >= 2 deck ran on a grid
        #: 8 % below the reference's, silently: the fluxes still integrate
        #: to something reasonable because the spectrum is smooth, which
        #: is exactly why it survived.
        #:
        #: Measured on the JINTRAC x = 0.758 deck: ours 0.10130 against
        #: upstream's 0.10961 at every point, a constant 0.92413 = 1/1.0821
        #: = 1/grad_r0.
        grid = ky_grid_kernel({**inputs, "KY_FACTOR": _units_ky_factor(
            inputs, sat_rule)})
        ky = grid["ky"]
        inputs = {"RHO_ION": grid["rho_ion"], **inputs}
    ky = [float(k) for k in ky]
    if not ky:
        raise TglfError("an empty ky spectrum has no fluxes")
    if any(b <= a for a, b in zip(ky, ky[1:])):
        raise TglfError("the ky spectrum must increase")

    ns = int(inputs["NS"])
    #: ★With ``find_width`` the width is the SCAN'S UPPER BOUND rather
    #: than the operating point, and a deck that does not state one gets
    #: the library's own default — which is what a deck recorded with
    #: ``FIND_WIDTH`` on was run at.
    if find_width:
        inputs = {"WIDTH": float(inputs.get("WIDTH", 1.65)), **inputs}
    required = ("RHO_ION",) if find_width else ("WIDTH", "RHO_ION")
    for name in required:
        if name not in inputs:
            raise TglfError(
                f"{name} is required: the Rust path does not search for "
                "a width, so the caller must state one"
            )
    inputs = _with_derived_units(inputs)
    nbasis = int(inputs.get("NBASIS_MAX", 4))
    pre = _presets(inputs, nbasis)

    #: ★The flux path's Miller slots 13-17 are ZERO and its p_prime /
    #: q_prime / kx0 / MS ride in `geom4` instead — a different layout from
    #: the linear entry's, which is why `_miller14` is truncated here
    #: rather than reused whole.
    miller = _miller14(inputs)[:13] + [0.0] * 5
    #: the pressure-gradient scale is the KERNEL's, clamps included — it
    #: sets SAT_RULE 2's normalisation and used to be re-derived here
    dlnpdr = kernel.tglf_dlnpdr(
        _species(inputs, TGLF_DECK_SPECIES_PRESSURE, ns), ns=ns,
        rmaj=float(inputs.get("RMAJ_LOC", 3.0)),
        rlnp_cutoff=float(inputs.get("RLNP_CUTOFF", 18.0)))
    scal = [float(inputs["R_UNIT"]), float(inputs["Q_UNIT"]),
            float(inputs["B_UNIT"]), float(inputs.get("SIGN_BT", 1.0)),
            float(inputs["FT"]), float(inputs["RHO_ION"]),
            float(inputs["WIDTH"]), dlnpdr,
            float(inputs.get("VEXB_SHEAR", 0.0)),
            float(inputs.get("ALPHA_E", 1.0)),
            float(inputs.get("ALPHA_QUENCH", 0.0)),
            # collisions.  XNUE defaults to zero; the model and the
            # diamagnetic trapping shift come from SAT_RULE (see _presets).
            float(inputs.get("XNUE", 0.0)),
            float(inputs.get("ZEFF", 1.0)),
            float(pre["XNU_MODEL"]),
            float(inputs.get("XNU_FACTOR", 1.0)),
            float(inputs.get("PARK", 1.0)),
            float(pre["WDIA_TRAPPED"]),
            float(inputs.get("THETA_TRAPPED", 0.7)),
            # rotation.  VPAR_MODEL is refused above unless it is 0, and
            # ALPHA_MACH defaults to 0, so VPAR alone still moves nothing.
            float(inputs.get("VPAR_MODEL", 0)),
            float(inputs.get("ALPHA_MACH", 0.0)),
            float(inputs.get("ALPHA_P", 1.0)),
            float(inputs.get("SIGN_IT", 1.0)),
            # magnetic
            float(inputs.get("BETAE", 0.0)),
            float(bool(int(inputs.get("USE_BPER", 0)))),
            float(bool(int(inputs.get("USE_BPAR", 0)))),
            float(inputs.get("DAMP_PSI", 0.0)),
            float(inputs.get("DAMP_SIG", 0.0)),
            float(inputs.get("LINSKER_FACTOR", 0.0)),
            # ★USE_MHD_RULE defaults to TRUE, which ZEROES the pressure
            # term in the drift.  Defaulting it to false here made every
            # finite-P_PRIME deck wrong and no zero-P_PRIME deck notice.
            float(bool(int(inputs.get("USE_MHD_RULE", 1)))),
            # WD_ZERO — see linear_kernel
            float(inputs.get("WD_ZERO", 0.1)),
            # DEBYE / DEBYE_FACTOR — see linear_kernel; quadratic in ky, so
            # this is the electron-scale end of the spectrum
            float(inputs.get("DEBYE", 0.0)),
            float(inputs.get("DEBYE_FACTOR", 1.0))]
    geom = [float(inputs.get("P_PRIME_LOC", 0.0)),
            float(inputs.get("Q_PRIME_LOC", 16.0)),
            float(inputs.get("KX0_LOC", 0.0)),
            float(inputs.get("MS", 128))]
    species_rot = _species(inputs, TGLF_DECK_SPECIES_ROTATING, ns)
    #: ``NMODES`` rides the same entry as the width search — the plain one
    #: has no room for it — so a multi-mode request goes there with the
    #: search switched off (``nwidth=0``).
    #: ★the same two-spellings rule as ``SAT_RULE``: the argument is the
    #: spelling, and a deck that also names ``NMODES`` must agree with it
    #: rather than silently overrule it — the count changes rule 2's
    #: normalisation as well as the number of terms, so the two answers
    #: differ by more than "one more mode".
    deck_modes = inputs.get("NMODES")
    if deck_modes is not None and int(deck_modes) != nmodes:
        raise TglfError(
            f"the deck says NMODES={int(deck_modes)} and the call says "
            f"nmodes={nmodes}: one call runs one mode count, and rule 2's "
            "normalisation constant comes from it")
    try:
        if find_width or nmodes > 1 or stress:
            return kernel.tglf_flux_searched(
                miller, scal, geom, species_rot, ky, ns=ns, nbasis=nbasis,
                nxgrid=int(inputs.get("NXGRID", 16)), sat_rule=sat_rule,
                width_min=float(inputs.get("WIDTH_MIN", 0.3)),
                nwidth=int(inputs.get("NWIDTH", 21)) if find_width else 0,
                use_bisection=bool(int(inputs.get("USE_BISECTION", 1))),
                nbasis_min=int(inputs.get("NBASIS_MIN", 2)),
                nmodes=nmodes)
        return kernel.tglf_flux(
            miller, scal, geom, species_rot,
            ky, ns=ns, nbasis=nbasis,
            nxgrid=int(inputs.get("NXGRID", 16)), sat_rule=sat_rule)
    except kernel.KernelError as exc:
        raise TglfError(str(exc)) from exc
