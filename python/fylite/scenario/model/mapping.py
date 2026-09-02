"""Profiles + geometry → TGLF / NEO inputs — the silent-failure layer.

This is the port of ``tgyro_tglf_map.f90`` and ``tgyro_neo_map.f90``: it turns
a local flux surface (shape, kinetic profiles, gradients) into the input set
each solver expects.  It is not a rename table — every quantity crosses a
normalization boundary:

* ``BETAE`` is referenced to ``B_unit``, not to the vacuum field;
* ``XNUE`` is a collision frequency in units of ``a/c_s``;
* ``Q_PRIME_LOC``/``P_PRIME_LOC`` carry ``(q/(r/a))`` factors and the
  **total**-pressure beta, not the electron one;
* the sign conventions ``SIGN_BT``/``SIGN_IT`` are derived from the toroidal
  flux and current orientation, and the momentum flux is signed on the way
  back out;
* and — the classic trap — **NEO normalizes to the first ion's temperature
  while TGLF normalizes to the electron temperature**.

None of those errors crash anything.  They produce plausible, wrong fluxes.
So this module is checked parameter-by-parameter against a TGYRO run's own
``out.tglf.localdump`` / ``out.neo.localdump`` (``tests/test_mapping.py``).

Everything here is in **CGS with eV temperatures**, the units TGYRO itself
works in — the conversion happens once, on the way in (:func:`surface_state`),
rather than being spread through the formulas where it could go wrong quietly.

★**Where the physics lives.**  The rates, the derived state and the two maps'
NUMBERS are the kernel's (``rust/fylite/src/mapping.rs``, reached through
:mod:`fylite.kernel`); what remains here is the state dict and the two NAME
tables — which parameter of ``input.tglf`` / the NEO namelist each number is
written to.  A name table is a lookup; a normalisation is not, and this is
the layer whose normalisation errors do not raise.
"""
from __future__ import annotations

import numpy as np

from ... import kernel

# CGS constants — the KERNEL's, re-exported, not declared.
#
#: ★★The last three were still spelled out here, and the comment they carried
#: was already most of the argument: four others "sat beside them and were
#: read by nothing … each indistinguishable from a live one — so the next
#: correction lands on whichever the reader happens to open, and no test can
#: fail."  The four dead ones were deleted; these three were live, which made
#: them worse, not better — `MD` and `ME` existed in TWO hosts with the same
#: values, and agreeing today is what a copy does right up until it does not.
#:
#: They come from ``mapping.rs``'s ``cgs`` module now, published as
#: :mod:`fylite._cgs` by ``rust/build.sh`` — the mechanism the deck orders
#: already use.  Re-exported under these names because that is what this
#: module's callers import.
from ..._cgs import C_LIGHT, E, K, MD, ME, MP  # noqa: F401
#: Grams to kilograms.  ★A unit factor, not a constant: the physical value
#: has one host (the kernel's table above), and the SI spelling of it is that
#: value with this applied here rather than a second number to keep in step.
G_TO_KG = 1.0e-3
#: The mass unit of ``input.gacode``'s ``mass`` column, **in kg**.  NOT the
#: proton mass: TGYRO reads it as ``mi = mass * (md/2)``
#: (tgyro_init_profiles.f90), so a deuteron is exactly 2.0 there.  Using m_p
#: instead puts MASS_2 at 1.00048 rather than 1, and shifts every
#: collision-frequency-derived quantity.
AMU_GACODE = 0.5 * MD * G_TO_KG


#: ★``derive`` moved to ``tests/oracles/gacode_derived.py`` on
#: 2026-08-21.  It computed the derived geometry and gyro-Bohm units of an
#: ``input.gacode`` bundle (a port of ``expro_compute_derived``) and had NO
#: caller in this package — all five were tests, comparing the port against
#: TGYRO's own dumps.  That is what it is FOR, and the test tree is where a
#: comparison against somebody else's dump belongs.



#: ★``bound_deriv`` and ``gyrobohm`` used to be re-exported here under the
#: kernel's own names, each a one-line forward with a docstring shorter than
#: the one it forwarded to.  Callers use the kernel directly.

#: ★``coulomb_log`` was here — a five-line forward to
#: :func:`fylite.kernel.collision_rates`'s ``loglam``.  Deleted rather than
#: moved: it had no caller at all, in the package OR the tests.



def collision_rates(ne_cgs, te_ev, ni_cgs, ti_ev, mass_g, z, therm=None) -> dict:
    """Belli-2008 collision frequencies [1/s] and the e-i exchange rate.

    ``ni_cgs``/``ti_ev``/``mass_g``/``z`` are per-ion sequences.  Returns
    ``{"nue", "nui", "nu_exch"}``: the electron and per-ion collision rates
    and the classical electron-ion energy-exchange rate ``nu_exch`` (the
    coefficient of ``1.5 n_e k (T_e - T_i)``, and the main Te/Ti coupling in
    a two-channel solve).  Profiles broadcast; the kernel's.

    ★The ION axis comes FIRST in ``ni``/``ti``.  A flat list of per-ion
    scalars is the shape that reads correctly for one ion and raises for
    two, which is how the wrong axis order survives a test suite.
    """
    out = kernel.collision_rates(ne_cgs, te_ev, ni_cgs, ti_ev, mass_g, z,
                                 therm)
    return {"nue": out["nue"], "nui": out["nui"], "nu_exch": out["nu_exch"]}


def surface_state(*, a, rmin, rmaj, zmag, drmaj, dzmag,
                  q, s, kappa, s_kappa, delta, s_delta, zeta, s_zeta,
                  b_unit, te, ne, dlnnedr, dlntedr,
                  ions, z_eff, signb, signq, shape=None,
                  w0=0.0, w0p=0.0, pext=0.0, dpext=0.0) -> dict:
    """Assemble one surface's derived plasma state, **in SI**.

    Lengths [m], ``b_unit`` [T], ``ne`` [m^-3], ``te`` [eV], log-gradients
    [1/m].  ``ions`` is a sequence of per-ion dicts with ``z``, ``mass``
    [kg], ``ni`` [m^-3], ``ti`` [eV], ``dlnnidr``, ``dlntidr`` [1/m] and
    optional ``therm`` (default ``True``).  Gradients are ``-d ln x/dr``,
    i.e. upstream's sign convention (positive for a decreasing profile).

    ★★It took CGS — ``a_cm``, ``b_unit_g``, ``ne_cgs`` — and the conversion
    was the CALLER's: ``closure.py`` multiplied by 100, by 1e4 and by 1e-6
    on the way in, so the assembly layer spoke TGYRO's units and anything
    that wanted a surface state had to.  The conversion is in the kernel
    now, at the ABI (``c_api.rs::surface_from_block``), where it happens once
    for all three entries that take this block instead of once per caller.
    ``te``/``ti`` did not move: eV is what the DD and TGYRO both use.

    ``pext`` [Pa] / ``dpext`` [Pa/m] carry any non-thermal (fast-ion)
    pressure, as TGYRO's ``ptot`` path does; they are zero for a purely
    thermal state.  They enter ``pr``, and through it ``beta_unit`` and
    ``dlnpdr`` — which is how a fast-ion population reaches TGLF at all on
    this path: as the alpha-stabilisation term ``alpha_sa`` and the
    ``p_prime`` the eigenvalue problem is solved with, not as a species.

    ★``dpext`` is ``-d p_fast/dr``, upstream's sign — POSITIVE for a
    pressure that falls outward, like every other gradient in this
    signature.  ``closure.surface_states`` takes the profile and forms it.

    ★★These two were the ONE pair in this SI signature that the kernel
    read as CGS, until 2026-08-30.  A caller doing the obvious thing was
    ten times low, and nothing raised.  Fixed at the ABI
    (``PA_TO_BARYE``), where the rest of the block is already converted.

    Returns the quantities every downstream map needs — ``c_s``, ``rho_s``,
    ``nue``, ``beta_unit``, ``betae_unit``, ``dlnpdr``, ``pr`` — alongside the
    inputs, so the maps below are pure lookups.
    """
    ions = list(ions)
    st = {
        "a": a, "rmin": rmin, "rmaj": rmaj, "zmag": zmag,
        "drmaj": drmaj, "dzmag": dzmag, "q": q, "s": s,
        "kappa": kappa, "s_kappa": s_kappa, "delta": delta, "s_delta": s_delta,
        "zeta": zeta, "s_zeta": s_zeta, "shape": dict(shape or {}),
        "b_unit": b_unit, "te": te, "ne": ne,
        "dlnnedr": dlnnedr, "dlntedr": dlntedr,
        "ions": ions, "z_eff": z_eff, "signb": signb, "signq": signq,
        "w0": w0, "w0p": w0p,
    }
    #: the derived half — one host, because every quantity in it crosses a
    #: normalisation boundary and none of the crossings raise.  ★The shear
    #: is `s` in this dict and `shear` in the kernel's block; the alias is
    #: written here, once, rather than being a second name for a column read
    #: positionally on the other side.
    st.update(kernel.surface_derived({**st, "shear": st["s"]},
                                     pext=pext, dpext=dpext))
    return st


#: TGLF's MXH names, in the order ``tgyro_tglf_map`` assigns them.
_TGLF_SHAPE = {"cos0": "SHAPE_COS0", "cos1": "SHAPE_COS1", "cos2": "SHAPE_COS2",
               "cos3": "SHAPE_COS3", "sin3": "SHAPE_SIN3"}


#: ``TGYRO_TGLF_REVISION`` — the host-level presets ``tgyro_tglf_map.f90``
#: applies on top of the physics mapping, ported from its ``select case``
#: (upstream lines 281-355), with the papers each one names.
#:
#: ★★**These are not solver taste, they are part of the published model.**
#: Revision 3 is "the recommended setting for using SAT_RULE = 2", and it
#: turns on ``USE_BPER``, turns OFF ``USE_MHD_RULE``, and switches the ky
#: grid to model 4 with 18 points and 8 modes.  Running SAT_RULE 2 without
#: them is not "SAT2 with different numerics" — ``USE_MHD_RULE`` alone
#: zeroes the pressure term in the drift.
#:
#: ★It lived as a dict in one test file, so the test knew the answer and
#: production did not: `closure.kernel_coefficients` assembled a deck at
#: SAT_RULE 2 with ``USE_BPER = 0`` and ``USE_MHD_RULE = 1``, both opposite
#: to what TGYRO does.  Found by diffing the whole key set against
#: TGYRO's own ``out.tglf.localdump`` rather than the handful of keys the
#: mapping tests happened to list.
#:
#: Revision 0 is "use defaults and overwrites" — deliberately empty.
TGYRO_TGLF_REVISION: dict[int, dict] = {
    #: defaults, no preset
    0: {},
    #: SAT0 with the Waltz quench rule and the old electron collision model
    #: — Kinsey, Staebler & Waltz, Phys. Plasmas 15, 055908 (2008)
    1: {"SAT_RULE": 0, "UNITS": "GYRO", "ALPHA_QUENCH": 1.0,
        "XNU_MODEL": 1},
    #: SAT1, multi-scale ETG zonal-flow mixing, spectral-shift ExB instead
    #: of the quench rule — Staebler et al., Nucl. Fusion 57, 066046 (2017)
    #: and Phys. Rev. Lett. 110, 055003 (2013)
    2: {"SAT_RULE": 1, "XNU_MODEL": 2, "UNITS": "GYRO",
        "ALPHA_QUENCH": 0.0, "ALPHA_E": 1.0},
    #: SAT2, fit to 64 CGYRO runs, tuned on JET DTE2 — Staebler et al.,
    #: PPCF 63, 015013 (2021) and Nucl. Fusion 61, 116007 (2021).
    #: **The recommended setting for SAT_RULE 2.**
    3: {"SAT_RULE": 2, "UNITS": "CGYRO", "ALPHA_QUENCH": 0.0,
        "ALPHA_E": 1.0, "ALPHA_P": 1.0, "ALPHA_MACH": 0.0,
        "USE_BPER": 1, "USE_BPAR": 0, "USE_AVE_ION_GRID": 1,
        "KYGRID_MODEL": 4, "NBASIS_MAX": 6, "NMODES": 8,
        "GEOMETRY_FLAG": 1, "USE_MHD_RULE": 0, "NKY": 18},
    #: ★momentum transport WITHOUT the electromagnetic terms, at any
    #: saturation rule.  Upstream's own comment gives the reason and it is
    #: a defect in TGLF, not a modelling choice: parallel flow
    #: (``ALPHA_MACH = 1``) and ``USE_BPER`` together trigger a bug, while
    #: parallel flow is what supplies the momentum pinch — so a low-beta
    #: momentum study takes this and gives up the EM terms.
    4: {"ALPHA_QUENCH": 0.0, "ALPHA_E": 1.0, "ALPHA_P": 1.0,
        "ALPHA_MACH": 1.0, "USE_BPER": 0, "USE_BPAR": 0},
}


def tglf_inputs(st: dict, *, betae_scale=1.0, nu_scale=1.0,
                rotation=False, mxh=True, revision: int | None = None) -> dict:
    """One surface's state → the ``input.tglf`` name/value mapping.

    Port of ``tgyro_tglf_map.f90``.  The result feeds
    :func:`fylite.scenario.model.gyrofluid.fluxes_kernel` directly.

    ★``revision`` applies one of :data:`TGYRO_TGLF_REVISION` on top —
    ``TGYRO_TGLF_REVISION`` in ``input.tgyro``, and the thing that makes a
    SAT_RULE 2 run the published SAT2 rather than SAT2's saturation with
    everything else left at library defaults.  ``None`` (the default)
    applies nothing, which is what a caller reproducing a bare
    ``input.tglf`` wants; a caller reproducing a TGYRO run states the
    revision.  ★The preset is applied **over** the mapped keys, not
    under them, because that is the order upstream uses: the
    ``select case`` runs after the physics assignment, and revision 3
    deliberately overwrites ``GEOMETRY_FLAG`` and ``ALPHA_MACH``.

    ``mxh`` mirrors TGYRO's ``TGYRO_TGLF_MXH_FLAG``: when off, the extended
    harmonics are zeroed on the way into TGLF even though GEO still used them
    for the metrics — an asymmetry that is upstream's, not ours.
    """
    loc = kernel.tglf_local({**st, "shear": st["s"]},
                            betae_scale=betae_scale, nu_scale=nu_scale,
                            rotation=rotation)
    shape_fac = 1.0 if mxh else 0.0

    out = {
        "USE_TRANSPORT_MODEL": 1,
        "GEOMETRY_FLAG": 1,
        "SIGN_BT": loc["sign_bt"],
        "SIGN_IT": loc["sign_it"],
        "NS": 1 + len(st["ions"]),
        "DEBYE": loc["debye"],
        "BETAE": loc["betae"],
        "XNUE": loc["xnue"],
        "ZEFF": st["z_eff"],
        #: ★★the geometry block comes back NAMED from the kernel — both the
        #: Miller names and the s-alpha trio that repeats them.  It was
        #: spelled out here, which meant this host had to know that TGLF
        #: calls the normalised minor radius `RMIN_LOC` AND that it wants it
        #: divided by `a`: an upstream Fortran convention plus a
        #: normalisation.  A host that reproduces an upstream normalisation
        #: is the host that gets one of them wrong.  `neo_inputs` below took
        #: its geometry from the kernel first; this one now does too.
        **loc["geometry"],
        "Q_LOC": loc["q_abs"],
        "Q_PRIME_LOC": loc["q_prime"],
        "P_PRIME_LOC": loc["p_prime"],
        #: beta stays 0 unless the total-pressure path is on — TGLF then
        #: computes its own dlnpdr and P_PRIME carries beta_unit instead
        "BETA_LOC": 0.0,
        "KX0_LOC": 0.0,
        "ALPHA_SA": loc["alpha_sa"],
        #: ★the remaining s-alpha entries and the flags below stay here and
        #: stay INTEGERS.  They are upstream's fixed choices, not computed —
        #: and the type is load-bearing: the recorded oracle is keyed by a
        #: JSON digest of this dict, so a `0` that became `0.0` would make
        #: every recorded answer unreachable.  That is not hypothetical; it
        #: cost three re-keyed records earlier in this series.
        "XWELL_SA": 0.0,
        "THETA0_SA": 0.0,
        "B_MODEL_SA": 0,
        "FT_MODEL_SA": 1,
        "IBRANCH": -1,
        "ADIABATIC_ELEC": 0,
        "NEW_EIKONAL": 1,
    }
    for key, name in _TGLF_SHAPE.items():
        out[name] = shape_fac * st["shape"].get(key, 0.0)
        out[f"SHAPE_S_{name.split('_', 1)[1]}"] = \
            shape_fac * st["shape"].get(f"s_{key}", 0.0)

    #: ★The species table is the kernel's, not this table's — it is the
    #: half of the classic trap that used to be written out by hand here.
    #: TGLF references temperature to the ELECTRONS and NEO to the FIRST
    #: ION; the two blocks are otherwise the same six fields over the same
    #: species list, so a table built for one reads as valid in the other
    #: and rescales every flux with nothing raising.  ``neo_inputs`` below
    #: already took its block from the kernel; this one now does too, and
    #: the difference between the two norms is one diff apart rather than
    #: one host apart.  What is left here is the NAMES: ``ZS_1``,
    #: ``MASS_1``, ... with the electrons at index 1.
    for i in range(out["NS"]):
        for key, name in zip(kernel.TGLF_SPECIES_ROWS,
                             kernel.TGLF_DECK_SPECIES):
            out[f"{name}_{i + 1}"] = float(loc[key][i])

    if rotation:
        out["VEXB_SHEAR"] = loc["vexb_shear"]
        for i in range(1, out["NS"] + 1):
            out[f"VPAR_SHEAR_{i}"] = loc["vpar_shear"]
            out[f"VPAR_{i}"] = loc["vpar"]
    if revision is not None:
        try:
            preset = TGYRO_TGLF_REVISION[int(revision)]
        except KeyError:
            raise ValueError(
                f"TGYRO_TGLF_REVISION {revision} is not one of "
                f"{sorted(TGYRO_TGLF_REVISION)} — upstream's select case "
                f"falls through to no preset, which is revision 0; naming "
                f"a number it does not have is a typo, not a request"
            ) from None
        #: ★OVER, not under: upstream's `select case` runs after the
        #: physics assignment and overwrites it (revision 3 sets
        #: GEOMETRY_FLAG and ALPHA_MACH that the mapping also writes).
        out.update(preset)
    return out


#: ★★``neo_inputs`` moved to ``tests/oracles/gacode_derived.py`` on
#: 2026-08-21, and where it went says what it was.  It turned a surface state
#: into upstream's NEO parameter NAMES — its own docstring gave the purpose,
#: "so it can be diffed against ``out.neo.localdump``" — and it had no caller
#: in this package.  Production reaches NEO through
#: :func:`fylite.kernel.neo_local`, which returns the same numbers without
#: ever forming a deck.
#:
#: ★So it did not need "converging into the kernel": the kernel already had
#: the arithmetic, and what stayed here was the naming.  A deck writer with
#: only test callers is a test's deck writer.

