"""Vertical-position feedback control (P3, ledger E-6/E-7 vertical tier).

Small-signal closed loop around the rigid n=0 mode of :mod:`fylite.
stability`.  The plasma is eliminated through the massless force balance
(k*xi + Ip*G^T dI = 0), which folds its motion into a rank-one correction
of the conductor inductance matrix:

    M* = M - (Ip^2/k) G G^T,      M* dI' + R dI = V,
    xi = -(Ip/k) G^T dI.

The open-loop growth rate is then the largest eigenvalue of -M*^-1 R —
and it must agree with the P2 dispersion root: the two formulations are
related by the Sherman-Morrison identity, so their agreement is a real
cross-check of the wiring, not a tautology (shipped as a test).

Note what this lifts: in this linearized regime the plasma DOES react
back on the circuits (the rank-one term) — the honest boundary left open
by P1's nonlinear evolution (dpsi_plasma = 0) is closed here for small
signals.

The actuator story follows the machine, not convenience: the PF supplies
carry a one-pole lag (a PF-supply time constant of order 10 ms) —
far slower than 1/gamma ~ 0.3 ms — so they CANNOT hold the mode; EAST
installed the in-vessel IC pair for exactly this reason.  The loop here
drives the antisymmetric IC pair (geometry in ``east_device.yaml``), and
the PF-with-lag failure ships as a test of the physics, not as a defect.

Observation: either the true xi (state feedback) or a flux-loop
estimate — the 35 loop responses to conductors come straight from the
bundled tables (rsilfc/rsilvs, the 1/(2*pi) convention verified in P0),
the plasma row is computed; xi is recovered by least squares given the
(measurable) conductor currents.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: ★this module has a ``device=`` PARAMETER, so the module is imported
#: under an alias: a bare `device` name is silently the dict inside every
#: function that takes one (`AttributeError` far from the cause).
from ... import device as _device_mod
from ... import fyo


@dataclass
class VerticalSystem:
    """Linearized vertical-mode plant in conductor space + IC actuators."""
    M_star: np.ndarray          # (n, n) rank-one-corrected inductance [H]
    R: np.ndarray               # (n,) resistances [Ohm]
    G: np.ndarray               # (n,) coupling gradient [Wb/A/m]
    C_xi: np.ndarray            # (n,) xi = C_xi @ dI [m]
    B_act: np.ndarray           # (n, n_act) actuator voltage injection map
    ip: float
    k: float                    # external-field stiffness [N/m]
    k_ideal: float
    gamma_openloop: float       # max eigenvalue of -M*^-1 R [1/s]
    mode: np.ndarray = field(default=None)      # unstable mode, C_xi . mode = 1
    loops_C: np.ndarray = field(default=None)   # (35, n) flux-loop rows [Wb/A]
    loops_P: np.ndarray = field(default=None)   # (35,) plasma xi rows [Wb/m]


def vertical_system(eq, *, coil_aturns, eta_coil_uohm_m,
                    eta_vessel_uohm_m=None, device=None,
                    passive_groups=("inner_shell",), ic_coils=(),
                    coarsen: int = 2) -> VerticalSystem:
    """The linearised vertical plant — assembled BY THE KERNEL from documents.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the first tool to sink): this function
    used to hold the recipe — deck → conductors → channel fold → mutual
    matrices, resistances, coupling gradient → rigid filaments off the ψ map
    → the ``vstab`` entry — as ~130 lines calling twelve flat kernel exports.
    Every number came from the kernel; the recipe was this host's, and the
    page's worker held a second copy.  The recipe is ``case.rs::vstab_case``
    now, reached through the document door: this function builds the PLAN
    (three documents and five settings) and reads the RECORD.

    ``eq`` — an ``fyo:equilibrium`` document, or a g-file at the door.
    ``device`` — the device document (the deck as a dict); ``None`` means the
    configured deck.  ``ic_coils`` — the fast actuators as ``{r, z, dr, dz,
    turns}`` dicts; a non-empty list REPLACES the document's ``ic_coil/coils``
    in the plan (the caller's override goes INTO the document — the kernel
    reads documents, not keyword arguments).  ``eta_vessel_uohm_m`` overrides
    the document's vessel resistivity.

    ★T-4 第二十五刀 (2026-09-06): the flux-loop rows ``loops_C`` / ``loops_P``
    are the door's as well — the response of every circuit member at the
    device document's ``magnetics/flux_loop`` (Wb/A, the plant's member order)
    and the plasma's rigid shift seen there, ``I_p G_loops``.  A device that
    declares no loops leaves both ``None``.  Only the actuator map ``B_act``
    (a placement) is formed here; this function makes no flat kernel call.
    """
    from ...io import fydoc
    doc = fyo.as_equilibrium(eq)
    dev = _device_document(device)
    ic_list = [dict(c) for c in ic_coils]
    if ic_list:
        dev = dict(dev)
        dev["ic_coil"] = dict(dev.get("ic_coil") or {}, coils=ic_list)
    settings = {"passive": ",".join(passive_groups), "ic": 1.0 if ic_list else 0.0,
                "coarsen": float(coarsen), "eta_coil": float(eta_coil_uohm_m)}
    if eta_vessel_uohm_m is not None:
        settings["eta_vessel"] = float(eta_vessel_uohm_m)
    plan = {"settings": settings,
            "inputs": {"device": dev, "equilibrium": doc,
                       "discharge": {"fylite:channel_aturns": np.asarray(coil_aturns, float)}}}
    rec = fydoc.complete("code/vstab", plan)
    n = int(rec["dims"]["n"])
    fields, facts = rec["fields"], rec["facts"]
    arr = lambda k: np.asarray(fields[k]["data"], float)  # noqa: E731
    M_star = arr("m_star").reshape(n, n)
    R, G, C_xi, mode = arr("r"), arr("g"), arr("c_xi"), arr("mode")
    ip = float(facts["ip"]["value"])
    k = float(facts["k"]["value"])
    k_ideal = float(facts["k_ideal"]["value"])
    gamma = float(facts["gamma"]["value"])
    n_ic = int(facts["n_fast_coils"]["value"])

    #: ---- the diagnostic side: the loop rows are the door's too (T-4 第二十五刀) ----
    #: `B_act` is a placement, not a computation: the fast coils are the last
    #: n_ic members of the plant and each takes its own voltage.
    B_act = np.zeros((n, n_ic))
    for j in range(n_ic):
        B_act[n - n_ic + j, j] = 1.0
    if "loops_c" in fields:
        n_loop = int(rec["dims"]["n_loop"])
        loops_C = arr("loops_c").reshape(n_loop, n)
        loops_P = arr("loops_p")
    else:
        loops_C = loops_P = None
    return VerticalSystem(M_star=M_star, R=R, G=G, C_xi=C_xi, B_act=B_act,
                          ip=ip, k=k, k_ideal=k_ideal,
                          gamma_openloop=gamma, mode=mode,
                          loops_C=loops_C, loops_P=loops_P)


def _device_document(device) -> dict:
    """The device as ONE document: the given dict, or the configured deck read whole."""
    if device is not None:
        return device
    import yaml
    return yaml.safe_load(_device_mod.deck_path("east_device.yaml").read_text(encoding="utf-8"))
