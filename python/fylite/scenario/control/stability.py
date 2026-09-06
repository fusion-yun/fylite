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

#: ★the rigid-filament recipe (`plasma_filaments` · `vertical_stiffness` ·
#: `vertical_growth_rate` · `plasma_mass`) had no caller
#: here or in the app: it is the kernel repository's oracle tree since T-4
#: 第十一刀 (2026-09-06), and `coupling_gradient` followed it on 第二十五刀 —
#: `code/vstab` is the plant AND answers `vertical_system`'s loop rows.
__all__ = ["VerticalStability", "vertical_mode"]


# --------------------------------------------------------------------------- #
# EAST wiring: one call from a g-file + the device description                #
# --------------------------------------------------------------------------- #
#: ★the verdict `vertical_mode` returns — the type stays public with it (T-4 第十一刀)
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
