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
from ... import kernel
from ...device import (Element, conductor_set, flux_loop_positions,
                       passive_set)
from . import stability

TWOPI = 2.0 * np.pi


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
    """Build the linearized plant from an equilibrium + the device description.

    ``eq`` — an ``fyo:equilibrium`` document, or a g-file at the door.

    ★It took a Green-table directory as its second positional argument and
    never opened it; the machine is the document's, resolved once below.

    ``ic_coils``: list of dicts {r, z, dr, dz, turns} (from
    ``east_device.yaml`` ``ic_coil.coils``) — the fast actuators; they are
    full circuit members (rows in M*), driven by per-turn voltage.
    """
    plasma = stability.plasma_filaments(eq, coarsen=coarsen)
    ip = float(np.asarray(plasma[2]).sum())
    #: ★★ONE resolution of the machine for the whole plant.  The geometry and
    #: the channel map used to be resolved twice on different terms — this
    #: line with a deck path, and a bare ``channel_weights()`` further down
    #: with none — so a configuration whose fyo document carried rectangles
    #: could take the element COUNT from the document and the elements
    #: themselves from the deck, and build W against the wrong one.
    cond = conductor_set()
    geo = {"coils": cond["coils"], "vessel": cond["vessel"]}
    if device is not None:
        pas_el, pas_eta, _ = passive_set(device, passive_groups)
    else:
        pas_el = geo["vessel"]
        pas_eta = np.full(len(pas_el), float(eta_vessel_uohm_m))
    #: ★the channel-space block assembly is `channel_matrices` with THIS
    #: passive set — it used to be spelled out again here in numpy, once
    #: for the deck vessel and once for the extended structure
    cm = _device_mod.channel_matrices(cond,
                                   eta_coil_uohm_m=eta_coil_uohm_m,
                                   passive=(pas_el, pas_eta), nu=3, nv=3)
    W = cm["weights"]

    ic_elems = [Element(c["r"], c["z"], c["dr"], c["dz"]) for c in ic_coils]
    ic_turns = np.array([float(c["turns"]) for c in ic_coils])
    n_ic = len(ic_elems)

    g_el = stability.coupling_gradient(plasma, [(e.r, e.z, 1.0) for e in geo["coils"]])
    g_vs = stability.coupling_gradient(plasma, [(e.r, e.z, 1.0) for e in pas_el])
    if n_ic:
        # extend the channel-space matrices with the IC conductors (per-turn state)
        M_ic = _device_mod.mutual_matrix(ic_elems, nu=3, nv=3) * np.outer(ic_turns, ic_turns)
        M_ic_el = _device_mod.mutual_matrix(ic_elems, geo["coils"], nu=3, nv=3) * ic_turns[:, None]
        M_ic_vs = _device_mod.mutual_matrix(ic_elems, pas_el, nu=3, nv=3) * ic_turns[:, None]
        R_ic = _device_mod.resistance_vector(ic_elems, eta_coil_uohm_m, turns=ic_turns)
        M = np.block([[cm["M"], np.vstack([(M_ic_el @ W.T).T, M_ic_vs.T])],
                      [np.hstack([M_ic_el @ W.T, M_ic_vs]), M_ic]])
        R = np.concatenate([cm["R"], R_ic])
        g_ic = stability.coupling_gradient(
            plasma, [(e.r, e.z, float(t)) for e, t in zip(ic_elems, ic_turns)])
        G = np.concatenate([W @ g_el, g_vs, g_ic])
    else:
        M, R = cm["M"], cm["R"]
        G = np.concatenate([W @ g_el, g_vs])
    n = M.shape[0]

    # stiffness from the active coils at their equilibrium ampere-turns
    el_at = W.T @ np.asarray(coil_aturns, float)
    k = stability.vertical_stiffness(plasma, [(e.r, e.z, 1.0) for e in geo["coils"]], el_at)

    #: the rank-one elimination, the growth rate and the ideal stiffness are
    #: the kernel's — one place where the plasma is removed from the circuit
    #: equations, so the browser and this host cannot eliminate it differently
    pl = kernel.vertical_plant(M, R, G, ip=ip, stiffness=float(k))
    M_star, C_xi = pl["m_star"], pl["c_xi"]
    k_ideal = pl["k_ideal"]
    B_act = np.zeros((n, n_ic))
    for j in range(n_ic):
        B_act[n - n_ic + j, j] = 1.0

    #: ★★Flux-loop observation rows are now COMPUTED for everything.  They
    #: used to be read from the Green tables for the tabulated channels and
    #: vessel groups, and computed with `mutual_filaments` only for the
    #: passive groups the tables did not cover — two paths for one quantity,
    #: with the table as a shortcut.  The tables are gone (LICENSE 3.1) and
    #: the remaining path is the one that was already here, so this is a
    #: convergence rather than a substitution: one definition of the mutual,
    #: evaluated by the kernel, for every conductor.
    #:
    #: ★The channel rows fold through the FROZEN channel map: a channel
    #: drives one or two deck elements at measured weights, and its loop flux
    #: is the weighted sum of theirs.  Two of the twelve are split pairs, so
    #: taking one element per channel would be wrong for those two.
    rsi, zsi = flux_loop_positions()

    #: ★★The per-element psi at the loop positions is
    #: :func:`fylite.device.point_response`'s first output, and this module used
    #: to filament-average it here instead — a third spelling of the same
    #: quantity (``rusteq`` had the second).  Gated bit-identical against
    #: the loop it replaces before the change, so the anchors below did not
    #: move: the kernel accumulates per filament and divides once, which is
    #: what ``np.mean`` over nine filaments does too.
    def _rows(elems, turns=None):
        psi = _device_mod.point_response(elems, rsi, zsi, nu=3, nv=3)[0]
        return psi if turns is None else psi * np.asarray(turns, float)

    #: ★★and the channel fold is the KERNEL's — :func:`fylite.device.channel_response`,
    #: which is `element_response` and the fold in one call.  Spelling it as
    #: `_rows(coils) @ W.T` here was the FOURTH host for a fold that has one
    #: (and it rebuilt W from a second resolution of the machine while doing
    #: it).  A channel drives one or two deck elements at measured weights and
    #: two of the twelve are split pairs, so taking one element per channel
    #: would be wrong for exactly those two.
    tabf = _device_mod.channel_response(cond, rsi, zsi, nu=3, nv=3)[0] * TWOPI
    tabv = _rows(pas_el) * TWOPI
    ic_rows = (_rows(ic_elems, ic_turns) if n_ic
               else np.empty((rsi.size, 0)))
    loops_C = np.hstack([tabf, tabv, ic_rows])
    #: ★the plasma's own flux-loop rows are the coupling gradient again,
    #: un-normalised: the kernel returns dM/dZ per unit plasma current, and
    #: these rows are per metre of rigid shift, so they are `ip` times it.
    #: This used to call a private central-difference in `stability`; that
    #: was the numpy half of a two-path arrangement, and the multiplication
    #: below is the whole difference between the two quantities.
    loops_P = ip * stability.coupling_gradient(
        plasma, [(r_, z_, 1.0) for r_, z_ in zip(rsi, zsi)])

    return VerticalSystem(M_star=M_star, R=R, G=G, C_xi=C_xi, B_act=B_act,
                          ip=ip, k=float(k), k_ideal=k_ideal,
                          gamma_openloop=pl["gamma_openloop"],
                          mode=pl["mode"],
                          loops_C=loops_C, loops_P=loops_P)


def close_vertical_loop(sys: VerticalSystem, *, t_end: float, dt: float,
                        kp: float, kd: float, xi0: float = 1.0e-3,
                        direction=(1.0, -1.0), use_observer: bool = False,
                        v_max: float | None = None,
                        actuator_tau: float | None = None,
                        noise_rms: float = 0.0, seed: int = 7) -> dict:
    """Simulate the loop: implicit-Euler plant, PD controller with a
    one-step measurement delay, optional actuator saturation and one-pole
    actuator lag (the PF-supply model; ``actuator_tau`` is the caller's).

    ``kp/kd = 0`` is the broken-loop control run of the discriminator.
    The initial state is the unstable eigenvector scaled to ``xi0``.
    """
    nstep = int(round(t_end / dt))
    observer = use_observer
    noise = None
    if observer and noise_rms:
        #: ★the draws are made HERE and handed to the kernel.  A random
        #: number generator is not physics, and a run that redraws inside
        #: the loop cannot be reproduced from the other host — the same
        #: reason the kernel takes a chi rather than a closure.
        rng = np.random.default_rng(seed)
        psi_scale = float(np.abs(sys.loops_P).max() * xi0)
        noise = rng.normal(scale=noise_rms * psi_scale,
                           size=(nstep + 1, sys.loops_P.size))
    out = kernel.vertical_loop(
        {"m_star": sys.M_star, "c_xi": sys.C_xi, "mode": sys.mode},
        sys.R, t_end=t_end, dt=dt, kp=kp, kd=kd, xi0=xi0,
        direction=np.asarray(direction, float), b_act=sys.B_act,
        loops_c=sys.loops_C if observer else None,
        loops_p=sys.loops_P if observer else None,
        noise=noise, v_max=v_max, actuator_tau=actuator_tau)
    return {"t": out["t"], "xi": out["xi"], "u": out["u"],
            "state_final": out["state_final"]}
