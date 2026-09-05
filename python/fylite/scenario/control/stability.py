"""Rigid n=0 vertical-mode stability (P2, ledger E-5 rigid tier).

The massless rigid-displacement model: an axisymmetric plasma displaced
vertically feels the external-field stiffness k = Ip d2(psi_ext)/dZ2
(k > 0 destabilizing); the passive structure responds through the
coupling gradient G_k = dM_pk/dZ_p, and the growth rate solves the
dispersion relation

    k = gamma * Ip^2 * G^T (gamma*M_w + R_w)^-1 G

with the three regimes read off the same quantities: stable (k <= 0),
resistive-wall (0 < k < k_ideal), ideal-unstable (k >= k_ideal =
Ip^2 G^T M_w^-1 G).

PROVENANCE
----------
Adapted from fytok's ``fyeq/stability.py`` (fusion-yun/fytok @ 653b9ef6)
— copy-adaptation per the absorption contract, not an import; fixes on
either side must be checked against the other.  Differences here:
gradients use central differences of :func:`fylite.device.
mutual_filaments` (fyeq differentiates its analytic Green gradient), and
the dispersion root uses pure-numpy bisection (fyeq uses scipy brentq;
the dispersion LHS is monotone in gamma, so bisection is exact business).
The correction this module carries into the docs: the Tier-1 source for
E-5 is fyeq *stability.py*, not response.py (that one is the diagnostic
response cache).

Everything device-specific (plasma current map, conductor geometry,
resistivities) comes in through arguments — this layer stays machine-
neutral; the EAST wiring lives in the helpers taking a g-file plus the
Green-table deck.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: ★this module has a ``device=`` PARAMETER, so the module is imported
#: under an alias: a bare `device` name is silently the dict inside every
#: function that takes one (`AttributeError` far from the cause).
from ... import device as _device_mod
from ... import kernel
from ...device import Element, conductor_set, passive_set

__all__ = [
    "VerticalStability", "plasma_filaments", "coupling_gradient",
    "vertical_stiffness", "vertical_growth_rate", "vertical_mode",
    "plasma_mass",
]


# --------------------------------------------------------------------------- #
# plasma as rigid filaments, from a g-file                                    #
# --------------------------------------------------------------------------- #
def plasma_filaments(eq, *, coarsen: int = 2):
    """Rigid filament set (r, z, amps) from an equilibrium's own profiles.

    ``j_phi = R p'(psin) + FF'(psin)/(MU0 R)`` on grid cells inside the
    LCFS, scaled so the filament sum reproduces the g-file Ip exactly (the
    profile discretization would otherwise leave a percent-level gap, and
    every rigid-mode quantity downstream is quadratic in the current).
    ``coarsen`` merges cells to keep the filament count tractable.

    ★The kernel's (:func:`fylite.kernel.plasma_filaments`), including the
    containment rule — so "is this cell in the plasma" has one answer here
    and in the mask, the tracer and the metrics.

    ★★One measured consequence of that move: the kernel's grid is
    ``r0 + dr*i`` while this module used to build it with ``linspace``, and
    on this deck the two land 3e-15 apart at the top row — which is exactly
    where the boundary polygon's own vertex sits, so 46 of 3838 cells change
    side.  The filament sum is renormalised to Ip either way; measured on
    the bundled case the coupling gradient moves 6.5e-5 and the stiffness
    1.3e-4 at the production ``coarsen=2``, and both are exact at
    ``coarsen=3`` where no block straddles that row.  A cell whose centre
    lies ON the boundary is a coin flip in any implementation; what is worth
    having is ONE coin.
    """
    from ... import fyo, kernel
    doc = fyo.as_equilibrium(eq)
    grid, psi = fyo.psi_map_of(doc)
    psi_axis, psi_bnd = fyo.psi_range_of(doc)
    return kernel.plasma_filaments(
        grid, psi, psi_axis=psi_axis, psi_bnd=psi_bnd,
        pprime=fyo.profile_of(doc, "dpressure_dpsi"),
        ffprim=fyo.profile_of(doc, "f_df_dpsi"),
        boundary=fyo.boundary_of(doc),
        ip=fyo.ip_of(doc), coarsen=coarsen)


# --------------------------------------------------------------------------- #
# the rigid-mode ingredients (fyeq-adapted)                                   #
# --------------------------------------------------------------------------- #
def coupling_gradient(plasma, loops) -> np.ndarray:
    """G_k = dM_pk/dZ_p [Wb/A/m], plasma-current-weighted (rigid shift).

    The kernel's, including the filament-order accumulation and the
    numpy-pairwise plasma-current sum.

    ★There is no `_dMdz` here any more.  The derivative of the filament
    mutual by central difference was written twice — once here and once in
    `breakdown.py` — and both were the numpy half of an "if the library is
    here" branch.  One host now; the reference implementation the gates
    measure it against lives in `tests/oracles/em.py`.
    """
    from ... import kernel
    lr, lz, lt = (np.asarray(a, float) for a in zip(*loops))
    g = kernel.coupling_gradient(plasma, (lr, lz, lt))
    return g.reshape(lr.shape)


def vertical_stiffness(plasma, loops, currents, *, step: float = 1.0e-3) -> float:
    """External-field stiffness k = sum_i a_i d2psi_ext/dZ2 [N/m]; k > 0
    destabilizing.  Second derivative by central difference of the first
    (same construction as fyeq) — the kernel's."""
    from ... import kernel
    lr, lz, lt = (np.asarray(a, float) for a in zip(*loops))
    cur = np.atleast_1d(np.asarray(currents, float))
    if cur.shape != lr.shape:
        raise ValueError(f"currents length {cur.shape} != loops {lr.shape}")
    return kernel.vertical_stiffness(plasma, (lr, lz, lt), cur, step=step)


@dataclass(frozen=True)
class VerticalStability:
    """n=0 vertical-mode verdict; regime read off the model's own numbers."""
    growth_rate: float          # gamma [1/s]; 0 when stable, inf when ideal-unstable
    regime: str                 # "stable" | "resistive-wall" | "ideal-unstable"
    stiffness: float            # k [N/m] (> 0 destabilizing)
    ideal_stiffness: float      # k_ideal = Ip^2 G^T M_w^-1 G [N/m]
    margin: float               # k_ideal/k - 1 (> 0: passives can hold it)

    @property
    def stable(self) -> bool:
        return self.regime == "stable"


def plasma_mass(eq, *, n_e: float = 3.0e19, a_mass: float = 2.0) -> float:
    """Plasma mass [kg] = n_i m_i V, with the volume taken from the
    equilibrium boundary (V = 2*pi * integral R dA by the
    shoelace-with-centroid rule).

    Density and species are ASSUMPTIONS, not equilibrium content: neither a
    GEQDSK nor an ``fyo:equilibrium`` carries profiles of either.  Defaults
    are EAST-typical (3e19 m^-3, deuterium); pass your own to see the
    sensitivity.
    """
    from ... import fyo, kernel
    poly = np.column_stack(fyo.boundary_of(fyo.as_equilibrium(eq)))
    #: Pappus by way of Green's theorem — the kernel's, so the volume a mass
    #: is built on is the same number the metrics report
    volume = kernel.enclosed_volume(poly)
    m_i = a_mass * 1.66053906660e-27
    return float(n_e * m_i * volume)


def vertical_growth_rate(plasma, passive_loops, inductance, resistance, *,
                         stiffness: float, gamma_max: float = 1.0e6,
                         mass: float = 0.0) -> VerticalStability:
    """Solve k = gamma Ip^2 G^T (gamma M + R)^-1 G (monotone -> bisection).

    With ``mass`` > 0 the massless force balance is replaced by
    m gamma^2 + gamma Ip^2 G^T (gamma M + R)^-1 G = k, i.e. plasma
    inertia is retained.  The default 0 is the quasi-static limit every
    step-wise-GS code assumes; comparing the two is how this module
    answers "when does that assumption stop holding" without TSC.
    """
    pr, pz, pamp = (np.atleast_1d(np.asarray(a, float)) for a in plasma)
    ip = float(pamp.sum())
    g = coupling_gradient(plasma, passive_loops)
    m = np.asarray(inductance, float)
    r = np.atleast_1d(np.asarray(resistance, float))
    n = g.size
    if m.shape != (n, n):
        raise ValueError(f"inductance must be ({n},{n}), got {m.shape}")
    if r.shape != (n,):
        raise ValueError(f"resistance must have length {n}, got {r.shape}")
    if np.any(r <= 0.0):
        raise ValueError("passive-loop resistances must be positive")
    k = float(stiffness)
    from ... import kernel
    #: ★one host for both linear-algebra quantities.  The regime logic
    #: (which branch, and what "ideal-unstable" means) stays here because it
    #: is a classification of the answer, not the answer.
    k_ideal = kernel.ideal_stiffness(m, g, ip=ip)
    if k <= 0.0:
        return VerticalStability(0.0, "stable", k, k_ideal, float("inf"))
    if k >= k_ideal and not mass:
        return VerticalStability(float("inf"), "ideal-unstable", k,
                                 k_ideal, k_ideal / k - 1.0)
    gamma = kernel.dispersion_root(g, m, r, ip=ip, stiffness=k,
                                   mass=float(mass),
                                   gamma_max=float(gamma_max))
    if gamma is None:
        return VerticalStability(float("inf"), "ideal-unstable", k,
                                 k_ideal, k_ideal / k - 1.0)
    return VerticalStability(gamma, "resistive-wall", k, k_ideal,
                             k_ideal / k - 1.0)


# --------------------------------------------------------------------------- #
# EAST wiring: one call from a g-file + the device description                #
# --------------------------------------------------------------------------- #
def vertical_mode(eq, *, coil_aturns,
                  eta_vessel_uohm_m=None, device=None,
                  passive_groups=("inner_shell",), coarsen: int = 2,
                  vessel_scale: float = 1.0,
                  eta_scale: float = 1.0,
                  mass: float = 0.0) -> VerticalStability:
    """The growth-rate discriminator — assembled BY THE KERNEL from documents.

    ★★2026-09-05 (FYL-DESIGN-16 K-3): the passive-circuit recipe this function
    held — deck → conductors → channel fold → stiffness; passive set scaled
    about the axis → mutual matrix, resistances, coupling gradient → the
    dispersion root and the regime — is ``case.rs::vstab_case`` with
    ``circuit: passive`` now.  This builds the PLAN and reads the RECORD; the
    regime comes back read off the two stiffnesses in ONE place (the kernel),
    which is what :func:`fylite.scenario.control.vstab`'s docstring asked for.

    ``vessel_scale`` moves the passive elements radially about the magnetic
    axis (the wall-proximity discriminator); ``eta_scale`` scales their
    resistances; ``mass`` adds the inertia term to the dispersion.  Pass
    ``device`` (the deck as a dict) with ``passive_groups``, or the legacy
    ``eta_vessel_uohm_m`` for the inner shell alone.
    """
    from ... import fyo
    from ...io import fydoc
    from .vertical import _device_document
    doc = fyo.as_equilibrium(eq)
    if device is None and eta_vessel_uohm_m is None:
        raise ValueError("pass either device= (with passive_groups) or "
                         "eta_vessel_uohm_m= for the inner shell")
    dev = _device_document(device)
    settings = {"circuit": "passive", "passive": ",".join(passive_groups), "ic": 0.0,
                "coarsen": float(coarsen), "vessel_scale": float(vessel_scale),
                "eta_scale": float(eta_scale), "mass": float(mass)}
    if eta_vessel_uohm_m is not None:
        settings["eta_vessel"] = float(eta_vessel_uohm_m)
    plan = {"settings": settings,
            "inputs": {"device": dev, "equilibrium": doc,
                       "discharge": {"fylite:channel_aturns": np.asarray(coil_aturns, float)}}}
    rec = fydoc.complete("code/vstab", plan)
    f = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    regime = ("stable", "resistive-wall", "ideal-unstable")[int(f("regime_code"))]
    return VerticalStability(f("gamma"), regime, f("k"), f("k_ideal"), f("margin"))
