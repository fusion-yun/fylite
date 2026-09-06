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

#: `plasma_probe_field` · `current_centroid` are the kernel repository's oracle
#: tree since T-4 第十一刀 (2026-09-06): no caller here or in the app
__all__ = ["probe_geometry"]


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
