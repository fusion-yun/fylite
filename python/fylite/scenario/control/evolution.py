"""Voltage-driven free-boundary evolution (P1, ledger E-4).

Couples the circuit layer (:mod:`fylite.device`) with the stepwise-GS
forward solver (:func:`fylite.run.forward_equilibrium`):

    per-turn voltages U/N ──► implicit-Euler circuit advance
                              (12 BRSP channels + 40 vessel segments)
                                     │ x_ch [A-turn], I_v [A]
                                     ▼
                     forward GS solve with BRSP = x_ch,
                     IVESEL=1 + VCURRT = I_v  (vessel field IN the solve)

State conventions (see ``device.channel_matrices``): the coil state IS
the BRSP ampere-turn value, so what the circuit evolves is exactly what
the GS solver consumes — no turn table in between; the vessel field
enters the solve through EFIT's own vessel response columns (``rv6565``),
the same tables the P0 acceptance verified against this module's Green
functions.

Honest boundary: the plasma does not yet react back on the circuits
(``dpsi_plasma`` stays zero — the vessel sees coil ramps, not plasma
motion).  That is enough for the P1 discriminator (the boundary must feel
the vessel) but NOT for vertical-stability work: growth rates need the
plasma response, which is P2 (ledger E-5).
"""
from __future__ import annotations

import tempfile

import numpy as np

from ... import device, fyo, kernel

from ...run import forward_equilibrium


def evolve_free_boundary(measurements, time, voltages_per_turn, *,
                         eta_coil_uohm_m, eta_vessel_uohm_m,
                         x0=None, vessel: bool = True, gs_every: int = 5,
                         profile=None, out=None, **run_kw) -> dict:
    """Evolve coil + vessel currents under per-turn voltage waveforms and
    solve the forward equilibrium along the way.

    Args:
        measurements: base measurement dict (shot/time/btor/plasma/...);
            its ``brsp`` is overridden by the evolving state.
        time: (n_time,) strictly increasing [s].
        voltages_per_turn: (n_time, 12) per-turn coil voltages [V/turn]
            (vessel rows are always 0 — passive).
        eta_coil_uohm_m / eta_vessel_uohm_m: resistivities [uOhm-m]; pass
            the values from ``east_device.yaml`` (``pf_active_circuits`` /
            ``pf_passive``) — they are data, not code.
        x0: initial channel state [A-turn]; defaults to measurements["brsp"].
        vessel: False freezes the vessel at zero current (the acceptance
            control — everything else identical).
        gs_every: forward-solve every k-th time sample.
        profile: dict of profile kwargs for ``forward_equilibrium``
            (betap0/emp/enp), default betap0=0.69.

    Returns dict with the full current trajectory, the equilibrium
    snapshots, and the matrices' metadata.
    """
    t = np.asarray(time, float)
    v_ch = np.asarray(voltages_per_turn, float)
    cond = device.conductor_set()
    cm = device.channel_matrices(cond, eta_coil_uohm_m=eta_coil_uohm_m,
                                   eta_vessel_uohm_m=eta_vessel_uohm_m)
    n_ch, n_vs = cm["n_channels"], cm["n_vessel"]
    if v_ch.shape != (t.size, n_ch):
        raise ValueError(f"voltages_per_turn MUST be ({t.size},{n_ch}), got {v_ch.shape}")
    x0 = np.asarray(x0 if x0 is not None else measurements["brsp"], float)
    if x0.size != n_ch:
        raise ValueError(f"x0 MUST have {n_ch} channels, got {x0.size}")

    if vessel:
        M, R = cm["M"], cm["R"]
        volts = np.hstack([v_ch, np.zeros((t.size, n_vs))])
        state0 = np.concatenate([x0, np.zeros(n_vs)])
    else:                       # control run: identical channels, no vessel
        M, R = cm["M"][:n_ch, :n_ch], cm["R"][:n_ch]
        volts = v_ch
        state0 = x0

    traj = device.evolve_circuits_voltage(M, R, state0, t, volts)

    outdir = out or tempfile.mkdtemp(prefix="fylite_evolve_")
    profile = dict(profile or {"betap0": 0.69})
    snaps = []
    for k in range(0, t.size, gs_every):
        x = traj[k, :n_ch]
        iv = traj[k, n_ch:] if vessel else np.zeros(n_vs)
        meas = {**measurements, "brsp": list(x)}
        nml = dict(run_kw.pop("extra_namelist", {}) or {})
        if vessel:
            nml.update({"IVESEL": 1, "VCURRT": list(iv)})
        r = forward_equilibrium(meas, **profile, extra_namelist=nml,
                                out=outdir, **run_kw)
        #: ★the solve writes a g-file; the snapshot is read from the DOCUMENT
        #: that g-file becomes, so no EFIT header name appears here.
        doc = fyo.equilibrium(r["gfile"])
        q = fyo.profile_of(doc, "q")
        rb, _ = fyo.boundary_of(doc)
        r_ax, z_ax = fyo.axis_of(doc)
        psi_axis, _ = fyo.psi_range_of(doc)
        snaps.append({"t": float(t[k]), "q0": float(q[0]),
                      "q95": float(kernel.interp(0.95, np.linspace(0, 1, q.size), q)),
                      "rmaxis": r_ax, "zmaxis": z_ax,
                      "r_bry": (float(rb.min()), float(rb.max())),
                      "psi_axis": psi_axis,
                      "vessel_current_max": float(np.max(np.abs(iv)))})
    return {"time": t, "trajectory": traj, "snapshots": snaps,
            "n_channels": n_ch, "n_vessel": n_vs, "vessel": vessel,
            "channels": cm["channels"], "outdir": outdir}


#: ★★``evolve_free_boundary_rs`` was here (66 lines): a second driver for the
#: voltage-driven free-boundary march, taking the grid and the limiter directly
#: instead of a device document.  **No caller anywhere** — measured across the
#: package, the tests, the tools, the browser gates, the manifests, the case
#: corpus and the whole documentation tree (2026-09-04).  The live path is
#: :func:`evolve_free_boundary` above, which the `control` line and the
#: manifests name.  Removed rather than kept "in case": a second entry into the
#: same march is a second place for its conventions to drift, and this one had
#: no gate on it at all.
