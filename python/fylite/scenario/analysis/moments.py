"""Current-centroid position from the magnetic probes (the anchors, without EFIT).

The Rust reconstruction closes on the Fortran path only when it is told where
the current column sits: the flux loops constrain the plasma's *total* and its
outboard reach, but leave the vertical position nearly free (measured: the
un-anchored twin lands ~45 mm off in Z, while its axis R is already good to
0.6 mm).  Until now those anchors were read out of an EFIT a-file
(``zcurrt``/``rcurrt``) — which is fine for a twin experiment and useless for
a standalone path, because it makes the Rust answer depend on the Fortran one.

This module derives them from the measurement itself: a current-filament fit
to the poloidal-field probes.

The model is one filament at (R_c, Z_c) carrying the measured I_p.  Each probe
reads the field along its own orientation,

    B_probe = B_R cos(a) + B_Z sin(a),          a = the deck's AMP2 angle,

so with the coils' own contribution subtracted (their currents are measured,
their geometry is the deck's), the residual is the plasma's field and the fit
has two unknowns against ~76 channels.  For a compact column seen from outside
the dipole term dominates, and the filament position is the current centroid —
which is exactly what ``rcurrt``/``zcurrt`` are.

Accuracy is measured, not assumed: see ``test_moments_recover_the_efit_centroid``.
"""
from __future__ import annotations

import numpy as np

from ... import device, kernel
from ...device import FWTMP2_MASK, conductor_set

__all__ = ["probe_geometry", "plasma_probe_field", "current_centroid"]


def probe_geometry() -> dict:
    """Per-channel probe R / Z / angle [deg] / length from the fyo device
    document — the same source the k-file writer and the geometry audit use.

    ★It used to take a ``table_dir`` and read ``dprobe.dat`` under it.  The
    positions are device data, not Green-table data; they live in the device
    document now and this face just forwards.  ★★The two faces below have
    since dropped the parameter too: neither ever read it, and a face that
    takes a path it does not use advertises a second source for facts that
    have one.
    """
    from ...device import probe_geometry as _load_probe_geometry
    return _load_probe_geometry()


def plasma_probe_field(meas: dict, *, weights=None) -> tuple:
    """Probe readings with the coils' own field removed.

    Returns ``(b_plasma, r, z, angle_deg, weight)`` — the plasma-only probe
    signal [T] and the geometry/weight of each channel.  Channels the
    measurement masks off (``fwtmp2`` = 0) keep weight 0 and are simply not
    fitted; nothing is silently dropped.
    """
    geo = probe_geometry()
    r = np.asarray(geo["r"], float)
    z = np.asarray(geo["z"], float)
    ang = np.deg2rad(np.asarray(geo["angle_deg"], float))
    b_meas = np.asarray(meas["expmp2"], float)
    n = min(r.size, b_meas.size)
    r, z, ang, b_meas = r[:n], z[:n], ang[:n], b_meas[:n]

    if weights is not None:
        w = np.asarray(weights, float)[:n]
    else:
        w = meas.get("fwtmp2")
        w = (np.asarray(w, float)[:n] if w is not None
             else np.asarray(FWTMP2_MASK, float)[:n])

    # coils' contribution at the probe positions, from the measured amp-turns
    cond = conductor_set()
    deck = {"coils": cond["coils"]}
    #: ★the channel-to-element fold is `Wᵀx` and it has one host: the kernel.
    #: Written out as a double loop here it was an inline copy of the BRSP
    #: map, whose index direction is the entire content of the map.
    el = kernel.channel_fold(cond["weights"], np.asarray(meas["brsp"], float))
    #: ★what a probe READS from a conductor — the angle projection included
    #: — is the kernel's.  It used to be spelled here as
    #: ``br @ el * cos(ang) + bz @ el * sin(ang)``, and the same sentence
    #: was written again in `recon_rs`: two copies of a SIGN convention that
    #: does not raise when it is wrong (a fit converges on a plasma tilted
    #: to match).
    b_coils = device.probe_element_response(deck["coils"], r, z, ang) @ el
    return b_meas - b_coils, r, z, ang, w


def current_centroid(meas: dict, *, guess=None, weights=None) -> dict:
    """Fit one current filament to the plasma-only probe field.

    Returns ``{"r": R_c, "z": Z_c, "residual": rms, "n_used": k}`` — the
    anchors :func:`fylite.scenario.analysis.recon_rs.reconstruct` takes, in metres.

    The fit is the kernel's (Levenberg-Marquardt on the two coordinates,
    with the filament field evaluated by the same element response every
    other consumer uses); what stays here is which probes are live, and the
    current-weighted first guess.
    """
    b_pl, r, z, ang, w = plasma_probe_field(meas, weights=weights)
    live = w > 0
    if live.sum() < 4:
        raise ValueError(
            f"only {int(live.sum())} live probes — cannot locate the current "
            "centroid.  A loops-only measurement masks every probe off "
            "(fwtmp2 all zero); pass weights= explicitly to fit anyway.")
    rr, zz, aa, bb, ww = r[live], z[live], ang[live], b_pl[live], w[live]
    ip = float(meas["plasma"])

    if guess is None:                       # current-weighted probe field guess
        guess = (float(np.average(rr, weights=ww * np.abs(bb) + 1e-12)),
                 float(np.average(zz, weights=ww * np.abs(bb) + 1e-12)))
    from ... import kernel
    out = kernel.current_centroid(rr, zz, aa, bb, ww, ip=ip, guess=guess)
    return {"r": out["r"], "z": out["z"], "residual": out["residual"],
            "n_used": int(live.sum())}
