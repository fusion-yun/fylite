"""ICRH deposition — the assembly layer over the kernel's minority model.

★★**This module is the second half of a model that could not be called.**
``heating.rs`` has carried the ICRF minority physics since the 1a batch —
resonance layer, Stix minority distribution, the ``P_el``/``P_ion`` split
and ``W_fast``, seven criteria measured against METIS
(``docs/note/icrh-ecrh-gap.md`` §7) — and until 2026-08-30 it
had **no C export at all**.  The model existed, the criteria passed, and no
host could reach it; this package's own scenario layer said so in as many
words ("what ``ic`` does NOT do is deposit").  The kernel entries landed as
ABI 119 and this is the layer that puts them on a flux-surface grid.

★Nothing here is new physics.  What it adds is the assembly the other
heating channels already have: profiles on ``x`` normalised on the caller's
``V'``, a fast-ion pressure in the shape :func:`fylite.scenario.model.
closure.surface_states` takes, and refusals that keep their reason.

## What it gives the rest of the package

``deposit`` returns power densities AND ``p_fast`` [Pa], which is exactly
the input TX-1 wired into the turbulence closure — so ICRH fast ions now
reach TGLF by the same ``pext`` route NBI's do, through ``beta_unit`` and
the alpha-stabilisation term.  ★That route is the whole reason this wiring
was worth doing before the rest of 1b: the deposition profile has been
computable in the kernel for months, and the thing it unlocks is a fast-ion
population the transport model can see.
"""
from __future__ import annotations

import numpy as np

from ... import kernel

__all__ = ["MINORITIES", "GASES", "IcrhRefused", "deposit"]

MINORITIES = kernel.ICRH_MINORITY
GASES = kernel.ICRH_GAS

#: re-exported so a caller catching a refusal does not have to import the
#: kernel module to name the type
IcrhRefused = kernel.IcrhRefused


#: ★The resonance layer has no wrapper here on purpose.  It is pure
#: geometry — ``kernel.icrh_resonance(setup=..., geometry=...)`` returns
#: ``{r_res, x_res, harmonic, b_res, offset}`` — and this layer would add a
#: second name and a second docstring to it without adding a decision.
#: ``deposit`` below returns the same dict as its ``layer`` key, so a caller
#: assembling a deposition never needs the standalone call at all.


def deposit(*, setup: dict, geometry: dict, local: dict, power_w: float,
            x, vpr, width: float = 0.1, ti_over_te: float = 1.0) -> dict:
    """One antenna's deposition on the flux-surface grid ``x``.

    ``x`` is the normalised minor radius the profile is wanted on and
    ``vpr`` is ``V'`` there — the profile is normalised on it, so the
    volume integral of ``p_total`` is the absorbed power by construction
    rather than by a separate renormalisation.

    ``width`` is the Gaussian half-width of the deposition on ``x``.  ★It
    has NO physical default here and 0.1 is a placeholder a caller should
    replace: the kernel computes a heated VOLUME FRACTION
    (``volume_fraction``, returned below) and the honest width follows from
    it, but tying the two together is a modelling choice this layer has not
    made and will not make silently.

    Returns the three power densities [W/m^3], the fast-ion pressure
    ``p_fast`` [Pa] and its stored energy, the layer, and the kernel's own
    scalars (``t_eff``, ``e_crit``, ``tau_s``, ``volume_fraction``,
    ``n_minority``) so a caller can see what the split was built on.

    ★``p_fast`` is ``2/3 W_fast`` distributed on the deposition shape: the
    kernel returns a fast-ion energy DENSITY averaged over the heated
    volume, and the pressure the transport closure wants is the local one.
    A caller that needs the anisotropic split has ``nbi``'s
    ``fast_ion_pressure_split`` for the beam case; the minority tail here
    is treated as isotropic, which is what the Stix distribution the kernel
    builds is.
    """
    x = np.asarray(x, float).ravel()
    vpr = np.asarray(vpr, float).ravel()
    if x.size != vpr.size:
        raise ValueError(f"x has {x.size} points and vpr has {vpr.size}")

    heat = kernel.icrh_minority(setup=setup, geometry=geometry, local=local,
                                power_w=power_w)
    p_total = heat["p_el"] + heat["p_ion"]
    prof = kernel.icrh_profile(x, vpr, x_res=heat["layer"]["x_res"],
                               width=width, p_total=p_total,
                               p_ion=heat["p_ion"])

    #: ★the fast-ion pressure on the SAME shape the power is deposited on,
    #: and normalised by the SAME quadrature the kernel used — the
    #: trapezoid in ``x`` with ``V'`` as the weight
    #: (``heating.rs::icrh_profile``).  Using a different rule here would
    #: put the energy and the pressure on two slightly different profiles
    #: for no reason a reader could find.
    shape = prof["p_total"]

    def _vpr_integral(f):
        return float(np.sum(0.5 * (f[1:] * vpr[1:] + f[:-1] * vpr[:-1])
                            * np.diff(x)))

    volume = _vpr_integral(np.ones_like(shape))
    weighted = _vpr_integral(shape)
    if volume > 0.0 and weighted != 0.0:
        #: `w_fast` is an energy density averaged over the heated volume;
        #: the local one is it times the shape re-normalised to a
        #: V'-weighted mean of one
        w_local = heat["w_fast"] * shape / (weighted / volume)
    else:
        w_local = np.zeros_like(shape)
    out = {
        "p_total": prof["p_total"],
        "p_ion": prof["p_ion"],
        "p_el": prof["p_el"],
        "w_fast": w_local,
        #: p = (2/3) w for an isotropic distribution
        "p_fast": (2.0 / 3.0) * w_local,
        "layer": heat["layer"],
        "power_absorbed_w": p_total,
    }
    for key in ("t_eff", "e_crit", "e_gamma", "tau_s", "volume_fraction",
                "n_minority", "e_mean"):
        out[key] = heat[key]
    return out
