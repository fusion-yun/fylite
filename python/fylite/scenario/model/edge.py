"""The SOL/divertor model as a boundary condition for the core.

The kernel solves the extended Lengyel model (`fylite.kernel.lengyel_*`).
This module is the other end: it turns that answer into the two things a
core transport step can consume — a separatrix temperature and a rescaled
impurity profile — and it does so **explicitly**.

★★**This is the layer that changes who OWNS the boundary condition, and
that is why it hands them over rather than installing them.**  Every
boundary value `core_march` has ever taken came from its caller
(``transport.rs``: *"what arrives here is a measurement or another code's
answer"*).  An edge model that quietly wrote into the boundary would move
that ownership without anyone deciding to, and the first symptom would be
a run whose separatrix temperature nobody can account for.  So
:func:`boundary_conditions` RETURNS them, with the state they were computed
from, and the caller does the substitution.

★It is host-side for the same reason TX-1's fast-ion route and TX-3's
waveforms are: the kernel's architecture puts closures, sources and
boundary values on the caller's side of the line.  Nothing here touches the
ABI.

## What the model can and cannot tell you

The Lengyel solve answers **heat flux and detachment**: the parallel heat
flux, the target temperature, the impurity concentration that reaches it.
It does NOT solve transport in the SOL — there is no 2-D field, no
recycling, no parallel flow — so it cannot tell a caller how the plasma got
to the separatrix, only what the separatrix must look like for the divertor
to be where the model says it is.  ★``TODO.md``'s **T-C26** is the SOL
transport gap and this module does not close it; **T-C15** is the
wall/divertor heat flux, whose MODEL side this supplies while its stated
gap — an external validation case — stays open.
"""
from __future__ import annotations

import numpy as np

from ... import kernel

__all__ = ["ION_PROPERTIES", "enrichment_kallenbach", "boundary_conditions",
           "rescale_impurity_profile"]

#: `(Z, first ionisation energy [eV])` — the two numbers the Kallenbach
#: enrichment regression reads.  Spelled here rather than derived: the fit
#: was made against these values and a "better" ionisation energy would be
#: a different fit.
ION_PROPERTIES = {
    "D": (1.0, 13.602),
    "He": (2.0, 24.587),
    "Li": (3.0, 5.392),
    "Be": (4.0, 9.323),
    "C": (6.0, 11.26),
    "N": (7.0, 14.534),
    "O": (8.0, 13.618),
    "Ne": (10.0, 21.565),
    "Ar": (18.0, 15.76),
    "W": (74.0, 7.864),
}


def enrichment_kallenbach(symbol: str, *, pressure_neutral_divertor: float,
                          multiplier: float = 1.0) -> float:
    """Divertor enrichment `c_divertor / c_core`, Kallenbach 2024 Fig. 8.

    ``enrichment = 41 Z^-0.5 p0^-0.4 (E_ion,Z / E_ion,D)^-5.8``

    ★A REGRESSION, not a model: it is a fit to a set of AUG discharges and
    it carries their conditions with it.  The exponent of -5.8 on an
    ionisation-energy ratio is what a regression looks like when it is
    doing work a mechanism should be doing, and a caller extrapolating far
    from that machine should know that is what they are extrapolating.
    """
    if symbol not in ION_PROPERTIES:
        raise ValueError(f"no ionisation data for {symbol!r}; have "
                         f"{sorted(ION_PROPERTIES)}")
    z, e_ion = ION_PROPERTIES[symbol]
    e_d = ION_PROPERTIES["D"][1]
    #: the pressure floor is upstream's, and it is the regulariser value
    #: rather than a machine epsilon — see `edge.rs`
    p0 = max(float(pressure_neutral_divertor), 1e-7)
    return (41.0 * z**-0.5 * p0**-0.4 * (e_ion / e_d) ** -5.8) * multiplier


def rescale_impurity_profile(profile, *, edge_concentration: float,
                             enrichment: float):
    """Scale a core impurity profile so its LCFS value matches the edge.

    ``conc_lcfs = edge_concentration / enrichment``, and the WHOLE profile
    is multiplied by ``conc_lcfs / profile[-1]`` — the shape the caller
    chose is preserved and only its level moves.

    ★Refuses a profile that is zero at the LCFS rather than scaling by
    infinity: a shape with nothing at the edge cannot be given an edge
    value by scaling, and the caller has to change the shape instead.
    """
    p = np.asarray(profile, float)
    if p.size == 0:
        raise ValueError("an empty profile cannot be rescaled")
    if not np.isfinite(p[-1]) or p[-1] == 0.0:
        raise ValueError(
            "the impurity profile is zero at the LCFS, so no uniform scaling "
            "can give it the edge concentration — change the shape instead")
    if not (enrichment > 0.0):
        raise ValueError(f"enrichment must be positive, got {enrichment}")
    conc_lcfs = float(edge_concentration) / float(enrichment)
    return p * (conc_lcfs / p[-1])


def boundary_conditions(*, geometry: dict, params: dict,
                        t_e_target_ev: float | None = None,
                        seed_impurity_weights: dict | None = None,
                        fixed_impurity_concentrations: dict | None = None,
                        t_i_over_t_e: float = 1.0,
                        ne_tau: float = kernel.LENGYEL_NE_TAU,
                        main_ion_charge: float = 1.0,
                        enrichment_multiplier: float = 1.0) -> dict:
    """Run the edge model and return the boundary conditions it implies.

    Inverse mode when ``t_e_target_ev`` is given (with
    ``seed_impurity_weights``), forward mode otherwise.

    Returns ``{"T_e_sep_eV", "T_i_sep_eV", "enrichment",
    "lcfs_concentrations", "solution"}``.

    ★★**Nothing is installed.**  ``T_e_sep_eV`` is what the edge model says
    the separatrix must be at; whether a transport step uses it is the
    caller's decision, made where it can be seen.  ``solution`` carries the
    whole converged state so that decision can be made on more than one
    number — including ``outcome``, which is where "this target is
    unreachable" or "fully detached" is said.

    ★``T_i_sep_eV`` is ``T_e * t_i_over_t_e`` and nothing more.  The edge
    model has no ion energy equation; the ratio is an ASSUMPTION the caller
    supplies, defaulting to one, and it is returned separately rather than
    folded in so that it stays visible.
    """
    fixed = dict(fixed_impurity_concentrations or {})
    if t_e_target_ev is not None:
        if not seed_impurity_weights:
            raise ValueError("inverse mode needs seed_impurity_weights")
        solution = kernel.lengyel_inverse(
            geometry=geometry, params=params, t_e_target_ev=t_e_target_ev,
            seed_impurity_weights=seed_impurity_weights,
            fixed_impurity_concentrations=fixed, ne_tau=ne_tau,
            main_ion_charge=main_ion_charge)
        edge_conc = dict(solution["seed_impurity_concentrations"])
    else:
        if seed_impurity_weights:
            raise ValueError(
                "forward mode takes concentrations, not weights — pass them "
                "in fixed_impurity_concentrations (upstream refuses the "
                "other spelling rather than ignoring it)")
        solution = kernel.lengyel_forward(
            geometry=geometry, params=params,
            fixed_impurity_concentrations=fixed, ne_tau=ne_tau,
            main_ion_charge=main_ion_charge)
        edge_conc = dict(fixed)

    #: ★the divertor NEUTRAL pressure the enrichment regression needs is not
    #: something this port computes — upstream carries it as a model output
    #: and fylite's solve does not.  So enrichment is offered only when the
    #: caller supplies a pressure, and is otherwise absent rather than
    #: defaulted to one: an enrichment of one is a CLAIM (divertor and core
    #: concentrations equal), not a neutral placeholder.
    pressure = params.get("pressure_neutral_divertor")
    enrichment = None
    lcfs = None
    if pressure is not None:
        enrichment = {sym: enrichment_kallenbach(
            sym, pressure_neutral_divertor=pressure,
            multiplier=enrichment_multiplier) for sym in edge_conc}
        lcfs = {sym: edge_conc[sym] / enrichment[sym] for sym in edge_conc}

    return {
        "T_e_sep_eV": solution["T_e_separatrix_eV"],
        "T_i_sep_eV": solution["T_e_separatrix_eV"] * float(t_i_over_t_e),
        "edge_concentrations": edge_conc,
        "enrichment": enrichment,
        "lcfs_concentrations": lcfs,
        "solution": solution,
    }
