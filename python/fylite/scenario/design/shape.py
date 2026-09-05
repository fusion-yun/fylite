"""Plasma-shape observables and their response to the coil channels (E-16).

The ingredient shape control needs and the rigid vertical model cannot
give: how gaps, isoflux errors and the boundary move when each BRSP
channel moves.

Where a perturbed-GS response code reaches for an analytic linearisation,
fylite differentiates **the real solver**: a forward equilibrium costs
~0.05 s here, so a central-difference column is two honest GS solves.
That trades a little noise for a large gain in fidelity — the response
is of the operator actually used downstream, including its boundary
tracing and its profile parameterization, with no second model to keep
in sync.

Observables (all in metres, all signed so that "target minus actual"
reads naturally):

* ``gap`` — distance from a wall reference point inward along a given
  direction to the boundary;
* ``isoflux`` — psi(control point) - psi_boundary, converted to an
  equivalent radial distance by the local |grad psi| so every row of the
  response matrix carries the same units;
* ``axis`` / ``boundary point`` — R and Z of the magnetic axis and of the
  boundary at a given poloidal angle.  The boundary point is found by
  intersecting the psi FIELD along a ray from the axis, not by
  interpolating the g-file's boundary polyline: that polyline is sampled
  for plotting, and interpolating it in angle cost 10-25 % of linear-
  response accuracy (E-19).

★The sampling and the ray casting are the kernel's
(:func:`fylite.kernel.sample` / the kernel's ``ray_level`` behind
:func:`shape_observables`): a gap, an
isoflux distance and a boundary point at an angle are the same question,
and answering it here on a private stencil is how a boundary comes to move
differently in two places on one equilibrium.

The response matrix is validated, not assumed: see
``tests/test_shape.py`` for the linearity check (predicts a finite
perturbation) and the up-down mirror check (channels identified as a
mirrored pair in E-14 must produce mirrored Z-responses).
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass

import numpy as np

from ... import fyo, kernel

from ...io import geqdsk
from ...run import forward_equilibrium

__all__ = ["ShapeTargets", "shape_observables", "shape_response",
           "predict_shape_change"]


@dataclass(frozen=True)
class ShapeTargets:
    """What to observe on a boundary.

    gaps: list of (r_wall, z_wall, dr, dz) — ray start and inward direction.
    isoflux: list of (r, z) control points.
    angles: poloidal angles [deg] at which to report boundary (R, Z),
        measured about the magnetic axis.
    """
    gaps: tuple = ()
    isoflux: tuple = ()
    angles: tuple = ()

    def labels(self) -> list[str]:
        out = [f"gap{i}" for i in range(len(self.gaps))]
        out += [f"iso{i}" for i in range(len(self.isoflux))]
        for a in self.angles:
            out += [f"bR@{a:g}", f"bZ@{a:g}"]
        return out + ["Raxis", "Zaxis"]


#: ★`_ray_gap` is gone: the ray cast belonged to the observable vector, and
#: the vector is the kernel's now.  The flat `ray_level` export went with
#: T-4 (2026-09-05): one ray on its own is a question nobody asked.


def shape_observables(eq, targets: ShapeTargets) -> np.ndarray:
    """Evaluate the observable vector on one equilibrium — the kernel's.

    ``eq`` — an ``fyo:equilibrium`` document, or a g-file at the door.

    ★What moved and why: the gaps, the isoflux flux-to-distance conversion
    (a 1 mm stencil and a division by ``|∇ψ|``) and the boundary points at
    given angles are ONE question asked three ways, and each used to be
    answered here on its own stencil.  A controller whose observables
    disagree about where the boundary is does not fail — it converges on a
    different plasma.

    What stays here is which points to ask about: the wall gaps, the
    isoflux targets and the angles are the MACHINE's, and the span of the
    angle rays comes from this equilibrium's own boundary trace.
    """
    #: ★`_grid_and_psi` is gone with the g-file keys: rebuilding the grid
    #: from `rleft`/`rdim`/`nw` and transposing `psirz` out of the deck's
    #: `[z, r]` was this module's private copy of what the document already
    #: settles once, in `fyo.psi_map_of`.
    doc = fyo.as_equilibrium(eq)
    grid, psi = fyo.psi_map_of(doc)
    rax, zax = fyo.axis_of(doc)
    _, psi_bnd = fyo.psi_range_of(doc)
    span = 1.2
    if targets.angles:
        #: the ray has to reach the boundary and no further; the trace is
        #: only used for its EXTENT, which is what it is good for
        rb, zb = fyo.boundary_of(doc)
        span = 1.05 * max(np.max(np.abs(rb - rax)), np.max(np.abs(zb - zax)))
    return kernel.shape_observables(grid, psi, psi_bnd,
                                    gaps=targets.gaps,
                                    isoflux=targets.isoflux,
                                    angles=targets.angles,
                                    axis=(rax, zax), angle_span=span)


def _solve(meas, aturns, profile, outdir, **run_kw):
    r = forward_equilibrium({**meas, "brsp": list(np.asarray(aturns, float))},
                            out=outdir, **profile, **run_kw)
    return geqdsk.read_geqdsk(r["gfile"])


def shape_response(measurements, aturns0, targets: ShapeTargets, *,
                   step=None, profile=None, out=None, **run_kw) -> dict:
    """Central-difference response matrix d(observables)/d(channel A-turn).

    ``step`` is per-channel [A-turn]; scalar or length-12.  Defaults to
    1 % of each channel's own magnitude (floored), which keeps every
    column in the linear regime while staying well above solver noise.
    """
    x0 = np.asarray(aturns0, float)
    n_ch = x0.size
    if step is None:
        step = np.maximum(0.01 * np.abs(x0), 1.0e3)
    step = np.broadcast_to(np.asarray(step, float), (n_ch,)).copy()
    profile = dict(profile or {"betap0": 0.69})
    outdir = out or tempfile.mkdtemp(prefix="fylite_shape_")

    base = shape_observables(_solve(measurements, x0, profile, outdir, **run_kw),
                             targets)
    J = np.empty((base.size, n_ch))
    for c in range(n_ch):
        xp, xm = x0.copy(), x0.copy()
        xp[c] += step[c]
        xm[c] -= step[c]
        op = shape_observables(_solve(measurements, xp, profile, outdir, **run_kw), targets)
        om = shape_observables(_solve(measurements, xm, profile, outdir, **run_kw), targets)
        J[:, c] = (op - om) / (2.0 * step[c])
    return {"J": J, "base": base, "step": step, "labels": targets.labels(),
            "aturns0": x0, "outdir": outdir}


def predict_shape_change(response: dict, delta_aturns) -> np.ndarray:
    """Linear prediction of the observable change for a channel step."""
    return response["J"] @ np.asarray(delta_aturns, float)
