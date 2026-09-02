"""EFIT/efund deck formats — the non-fyo files an EAST deck directory carries.

These are somebody else's formats: fixed-column Fortran output and a namelist
snapshot, not fyo documents.  Reading one is this package's ``io/`` job, the
same as a g-file or an ``input.gacode``; what the machine IS comes from the
fyo device document (:mod:`fylite.device`).

* :func:`read_geom_box` — ``east_geom.txt``'s computational box;
* :func:`read_geom_turnfc` — ``TURNFC`` (12 values, EFIT coil order) out of the
  same snapshot.

★**Neither is a data source any more.**  The box and the turns are both in the
device document (``solver_dims`` + ``machine.default_grid``, and
``pf_active.coil[].turns`` with each coil's ``efit_index``), and that is where
the package reads them.  What survives here is the one job the file can do
that the document cannot do for itself: be the INDEPENDENT artifact the
document is checked against — see :func:`fylite.device.verify_solver_dims`.
A declaration that agrees with nothing is worse than a hard-coded number,
because it looks authoritative.

★So a caller who wants "the box" wants :func:`fylite.device.grid_box`.  These
two exist for the audit, and for importing a machine that has only a deck.
"""
from __future__ import annotations

from pathlib import Path


__all__ = ["read_geom_box", "read_geom_turnfc"]


def read_geom_box(path) -> dict:
    """The computational box out of an ``east_geom.txt`` snapshot.

    Line 1 is ``nw nh``; line 2 is ``rleft rdim zmid zdim``.  Returns
    ``nw`` / ``nh``, ``grid = (rmin, rmax, zmin, zmax)`` and ``source``.
    """
    p = Path(path)
    head = p.read_text().split("\n")
    nw, nh = (int(v) for v in head[0].split()[:2])
    rleft, rdim, zmid, zdim = (float(v) for v in head[1].split()[:4])
    return {"nw": nw, "nh": nh,
            "grid": (rleft, rleft + rdim, zmid - zdim / 2, zmid + zdim / 2),
            "source": str(p)}


def read_geom_turnfc(path) -> list[float]:
    """``TURNFC`` — 12 total-turn counts in EFIT F-coil order.

    EFIT F-coil order (see gnubuild/EFUND.md)::

        idx  1    2    3    4    5    6    7    8    9   10   11   12
        coil PF1  PF3  PF5  PF7  PF9  PF11 PF2  PF4  PF6  PF8  PF10 PF12

    ★The document's own answer to this is ``PF_TURNS`` reordered by each
    coil's ``efit_index`` (:func:`fylite.device.turnfc`), and that is what the
    channel map uses.  This reader is the cross-check and the importer.
    """
    with open(path) as f:
        f.readline()
        f.readline()
        mfc = int(f.readline().split()[0])
        return [float(f.readline().split()[6]) for _ in range(mfc)]
