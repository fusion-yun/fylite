"""IMAS IDS, HDF5 flat backend → plain dicts.

★★What this is FOR.  An integrated-modelling run (JINTRAC / JETTO here)
writes its answer as IMAS IDSs, and that answer is the only kind of
reference this repository can hold a prediction against: it carries the
METRIC the run actually used (`dvolume_drho_tor`, `gm2`, `gm3`, `f`) beside
the profiles it reached.  Handed both, a reproduction isolates the
TRANSPORT — which is the comparison worth making.  Given only profiles, a
disagreement could always be blamed on a geometry nobody could check.

★The flat backend writes one dataset per leaf with ``&`` where the IDS path
has ``/``, and array-of-structure indices collapsed into the leading axis.
So ``profiles_1d[]&electrons&temperature`` is ``(n_time, n_rho)``.  This
module does not model the IDS tree; it reads named leaves and says so.

★★``-9e40`` is IMAS's EMPTY_FLOAT and it is NOT a number: a source that
never fired writes it, and a caller that averaged it would get a power of
minus ten to the forty.  :func:`slab` turns it into NaN at the door, once,
so nothing downstream has to know the sentinel exists — and NaN is the
value that PROPAGATES rather than quietly biasing a mean.

This reads; it does not decide physics.  Nothing here interpolates,
re-grids or fills.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

#: IMAS's own "this was never set" marker for a float leaf.
EMPTY_FLOAT = -9e40


class ImasError(ValueError):
    """The file is not an IDS this reader can state that quantity from."""


def _root(path, ids: str):
    import h5py

    p = Path(path)
    if not p.is_file():
        raise ImasError(f"{p} is not a file")
    f = h5py.File(p, "r")
    if ids not in f:
        raise ImasError(
            f"{p.name} carries {list(f.keys())}, not {ids!r} — an IDS file is "
            "named for the IDS it holds and this one is not that")
    return f, f[ids]


def slab(path, ids: str, leaf: str) -> np.ndarray:
    """One named leaf, with ``EMPTY_FLOAT`` turned into NaN.

    ``leaf`` is the flat-backend name, e.g.
    ``profiles_1d[]&electrons&temperature``.
    """
    f, g = _root(path, ids)
    try:
        if leaf not in g:
            near = [k for k in g.keys() if leaf.split("&")[-1] in k][:6]
            raise ImasError(
                f"{Path(path).name}: no leaf {leaf!r}"
                + (f"; did you mean one of {near}?" if near else ""))
        v = np.asarray(g[leaf])
    finally:
        f.close()
    if v.dtype.kind == "f":
        v = np.where(np.isclose(v, EMPTY_FLOAT, rtol=1e-6), np.nan, v)
    return v


def labels(path, ids: str, leaf: str) -> list:
    """A string leaf as a flat list of ``str``."""
    v = slab(path, ids, leaf)
    return [x.decode() if isinstance(x, bytes) else str(x)
            for x in np.asarray(v).ravel()]


def times(path, ids: str) -> np.ndarray:
    """The IDS's own time base."""
    return slab(path, ids, "time")


def at_time(path, ids: str, t: float):
    """``(index, time)`` of the slice NEAREST ``t``.

    ★The index and the TIME come back together on purpose: a caller that
    asked for 83.5 s and silently got 78.6 s would report a comparison at a
    time that is not the one it names.  Everything here reports the slice it
    actually used.
    """
    ts = np.asarray(times(path, ids), float)
    if ts.size == 0:
        raise ImasError(f"{Path(path).name}: empty time base")
    i = int(np.argmin(np.abs(ts - float(t))))
    return i, float(ts[i])


def metric(equilibrium_h5, t: float) -> dict:
    """The transport METRIC one equilibrium slice states.

    ``{t, rho, vprime, gm2, gm3, fpol, q, psi, volume}`` — the columns
    ``evolve_heat`` takes as its input block, read off the run's OWN
    equilibrium rather than rebuilt from a shape.
    """
    i, tt = at_time(equilibrium_h5, "equilibrium", t)
    P = lambda k: slab(equilibrium_h5, "equilibrium",
                       "time_slice[]&profiles_1d&" + k)[i]
    return {"t": tt, "rho": P("rho_tor"), "vprime": P("dvolume_drho_tor"),
            "gm2": P("gm2"), "gm3": P("gm3"), "fpol": P("f"),
            "q": P("q"), "psi": P("psi"), "volume": P("volume")}


def profiles(core_profiles_h5, t: float) -> dict:
    """One core-profiles slice: ``{t, rho, rho_n, te, ti, ne, q, zeff}``.

    Temperatures in eV and densities in m^-3, which is what IMAS states and
    what this package computes in — no conversion happens here, and that is
    the point: a unit change belongs at a door somebody can name.
    """
    i, tt = at_time(core_profiles_h5, "core_profiles", t)
    P = lambda k: slab(core_profiles_h5, "core_profiles",
                       "profiles_1d[]&" + k)[i]
    return {"t": tt, "rho": P("grid&rho_tor"), "rho_n": P("grid&rho_tor_norm"),
            "te": P("electrons&temperature"), "ne": P("electrons&density"),
            "ti": P("t_i_average"), "q": P("q"), "zeff": P("zeff")}


def source_powers(core_sources_h5, t: float) -> dict:
    """``{name: (P_e, P_i)}`` in W, for the sources that state a power.

    ★A source whose power is EMPTY_FLOAT is LEFT OUT rather than reported
    as zero: 「这一档没有点」 and 「点了，是零」 are different facts, and
    only the first is what an unfired actuator means.
    """
    i, tt = at_time(core_sources_h5, "core_sources", t)
    names = labels(core_sources_h5, "core_sources",
                   "source[]&identifier&name")
    pe = slab(core_sources_h5, "core_sources",
              "source[]&global_quantities[]&electrons&power")
    pi = slab(core_sources_h5, "core_sources",
              "source[]&global_quantities[]&total_ion_power")
    out = {"t": tt}
    for k, n in enumerate(names):
        e, s = float(pe[k, i]), float(pi[k, i])
        if np.isfinite(e) or np.isfinite(s):
            out[n] = (e if np.isfinite(e) else 0.0,
                      s if np.isfinite(s) else 0.0)
    return out
