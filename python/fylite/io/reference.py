"""A reference profile table — the page's own reference import, in Python.

★★What this is FOR.  ``evolve-iter-15ma-benchmark`` starts its march on
published profiles rather than on the shape controls, so what the readings
then measure is 「this transport model drifts THIS far from them」 — the
reproduction test itself, and not a fit.  Until now that start existed only
in the browser (``scenario-model.js``'s ``modelParseReference``), so the
richest comparison in the corpus could not be run from Python at all.

★This is a TRANSCRIPTION of that parser, column names included, not a
second idea about what a profile table is.  The two hosts must accept the
same file and read the same numbers out of it, or a case that runs in one
place is a different discharge in the other.

★★What it is NOT: a re-gridding convention.  The table arrives on
``rho_tor`` [m], which is the label the 1.5-D march runs on, so putting it
on a march's radii is a linear interpolation and nothing else — no fit, no
smoothing, no spline.  :func:`at` clamps outside the table's own span
rather than extrapolating: a reference says nothing beyond its last point,
and a polynomial's opinion there is not the reference's.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

#: The ASTRA table's own column names, in the aliases the page accepts.
#: ★The first column has NO name (it is the row index), which is why the
#: header is matched by NAME and never by position.
_COLS = {
    "rho": ("rho", "rho_tor", "RHO"),
    "x": ("x", "rho_n"),
    "te": ("TE", "Te", "te"),
    "ti": ("TI", "Ti", "ti"),
    "ne": ("NE", "Ne", "ne"),
    "q": ("q", "Q", "qpsi"),
}

#: keV and 1e19 m^-3 are the table's units; eV and m^-3 are this package's.
#: One conversion, here, at the door.
_SCALE = {"te": 1e3, "ti": 1e3, "ne": 1e19, "q": 1.0}


class ReferenceError(ValueError):
    """The table is not one this reader can state a profile from."""


def read_reference(path: str | Path) -> dict:
    """One reference profile table → ``{name, rho, te, ti, ne, q, x_norm}``.

    ``te``/``ti`` in eV, ``ne`` in m^-3, ``rho`` in metres (or normalised,
    with ``x_norm`` true when the table carried only ``x``).  A column the
    table does not have comes back as an all-NaN array rather than as a
    missing key: ``at`` then declines to state it, and a caller can tell
    「表里没有这一列」 from 「这一列是零」.
    """
    p = Path(path)
    text = p.read_text(errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ReferenceError(
            f"{p.name}: fewer than three non-empty lines — a header and two "
            "rows is the least a profile can be stated with")
    hdr = [h.strip() for h in lines[0].split(",")]

    def at(key):
        for i, h in enumerate(hdr):
            if h in _COLS[key]:
                return i
        return -1

    idx = {k: at(k) for k in _COLS}
    if idx["te"] < 0 or (idx["rho"] < 0 and idx["x"] < 0):
        raise ReferenceError(
            f"{p.name}: needs an electron temperature column "
            f"({'/'.join(_COLS['te'])}) and a radius "
            f"({'/'.join(_COLS['rho'])} or {'/'.join(_COLS['x'])}); the "
            f"header has {hdr[:12]}{' ...' if len(hdr) > 12 else ''}")
    #: ★the page reads the radius from `rho` when it is there and from `x`
    #: only otherwise, and says which it used — the two are different labels
    #: and a march on the wrong one is a different plasma
    r_col = idx["rho"] if idx["rho"] >= 0 else idx["x"]
    x_norm = idx["rho"] < 0

    cols: dict[str, list] = {k: [] for k in ("rho", "te", "ti", "ne", "q")}
    for ln in lines[1:]:
        cell = ln.split(",")
        if r_col >= len(cell):
            continue
        try:
            r = float(cell[r_col])
        except ValueError:
            continue
        if not np.isfinite(r):
            continue
        cols["rho"].append(r)
        for k in ("te", "ti", "ne", "q"):
            i = idx[k]
            v = float("nan")
            if 0 <= i < len(cell):
                try:
                    v = float(cell[i]) * _SCALE[k]
                except ValueError:
                    v = float("nan")
            cols[k].append(v)

    if len(cols["rho"]) < 3:
        raise ReferenceError(
            f"{p.name}: only {len(cols['rho'])} row(s) parsed — a profile "
            "needs at least three")
    out = {k: np.asarray(v, float) for k, v in cols.items()}
    out["name"] = p.name
    out["x_norm"] = x_norm
    return out


def at(ref: dict, key: str, radii) -> np.ndarray:
    """``ref[key]`` on ``radii`` — linear, CLAMPED at both ends.

    ★Clamped rather than extrapolated: past the table's last point the
    reference states nothing, and the value a polynomial would invent there
    is not the reference's.  This is the page's ``refAt`` rule.

    Returns all-NaN when the table has no such column, so a caller can
    decline that channel rather than fill it with something.
    """
    v = np.asarray(ref[key], float)
    r = np.asarray(ref["rho"], float)
    want = np.asarray(radii, float)
    if not np.any(np.isfinite(v)):
        return np.full(want.shape, np.nan)
    return np.interp(want, r, v, left=v[0], right=v[-1])
