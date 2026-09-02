"""Read the web app's session documents (``fylite:AppSession/1``).

The browser page at ``app/`` exports one self-describing JSON-LD document
carrying its inputs and, optionally, its outputs.  This module is the other
end: it reads that document, converts the one convention that differs, and
hands back plain dicts the rest of the package already understands —
including a g-file dict that :mod:`fylite.io.geqdsk` consumers accept.

Why the app does not write HDF5 itself: the only browser-side library that
can *write* HDF5 is h5wasm at ~5.7 MB, against a 187 kB solver kernel.  The
conversion belongs here, where h5py already is.

GAUGE.  The document states its own convention rather than pre-converting,
so the flip happens once, here, under test:

===================  =========================  =========================
quantity             app (``full_flux_Wb_axis_max``)  IMAS / EFIT
===================  =========================  =========================
psi                  full flux [Wb], axis max   psi/(-2 pi), axis min
p', FF'              d/d(psi/2pi)               negated
coil current         A.turns                    A.turns (unchanged)
===================  =========================  =========================
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import fyo, kernel

TYPE = "fylite:AppSession/1"
APP_CONVENTION = "full_flux_Wb_axis_max"

TWO_PI = 2.0 * math.pi


class AppSessionError(ValueError):
    """The document is absent, malformed, or not one of ours."""


def load(path: str | Path) -> dict:
    """Load and validate a session document.

    Refuses anything without our ``@type``: a file that merely looks like
    JSON is not a session, and guessing at its shape is how a wrong number
    ends up in a plot.
    """
    p = Path(path)
    try:
        doc = json.loads(p.read_text())
    except Exception as exc:                       # noqa: BLE001 - reported
        raise AppSessionError(f"{p}: 读不成 JSON — {exc}") from exc
    got = doc.get("@type") if isinstance(doc, dict) else None
    if got != TYPE:
        raise AppSessionError(
            f"{p}: @type = {got!r}，需要 {TYPE!r}")
    conv = doc.get("fylite:psi_convention")
    if conv != APP_CONVENTION:
        raise AppSessionError(
            f"{p}: 未知的 psi 规约 {conv!r}（本读法只认 {APP_CONVENTION!r}）")
    if "fylite:config" not in doc:
        raise AppSessionError(f"{p}: 缺 fylite:config")
    return doc


def config(doc: dict) -> dict:
    """The page's inputs, as-is."""
    return dict(doc["fylite:config"])


def has_result(doc: dict) -> bool:
    return bool(doc.get("fylite:result"))


def _slice(doc: dict, key: str = "fylite:result"):
    res = doc.get(key)
    if not res:
        raise AppSessionError("这份会话只有配置，没有结果")
    eq = res.get("equilibrium")
    if not eq or not eq.get("time_slice"):
        raise AppSessionError("结果里没有 equilibrium.time_slice")
    return res, eq["time_slice"][0]


def to_geqdsk(doc: dict, *, rcentr: float = 1.75, bcentr: float = 1.8,
              limiter: tuple | None = None, truth: bool = False) -> dict:
    """A g-file dict (same keys as :func:`fylite.io.geqdsk.read_geqdsk`).

    ``rcentr``/``bcentr`` are not carried by the equilibrium itself — the
    forward model never sees the toroidal field — so they come in from the
    machine description, defaulting to EAST's.

    With ``truth=True`` the synthetic twin's own truth slice is converted
    instead of the reconstruction, when the document carries one.
    """
    res, sl = _slice(doc)
    if truth:
        t = res.get("fylite:truth")
        if not t:
            raise AppSessionError("这份会话没有真值切片")
        sl = t["time_slice"][0]

    p2 = sl["profiles_2d"][0]
    r = list(p2["grid"]["dim1"])
    z = list(p2["grid"]["dim2"])
    nw, nh = len(r), len(z)
    psi_app = p2["psi"]
    if len(psi_app) != nw * nh:
        raise AppSessionError(
            f"psi 长度 {len(psi_app)} 与网格 {nw}x{nh} 不符")

    gq = sl["global_quantities"]
    #: app layout ``[i*nh + j]`` (i = R) -> g-file layout ``[j*nw + i]``
    #: (R fastest), and full flux [Wb] -> Wb/rad with the axis at the
    #: minimum.  ★One transpose, written as one — the hand-rolled double
    #: loop this replaces was a third copy of the index rule that
    #: :func:`fylite.io.geqdsk.kernel_flux_map` exists to hold.
    psirz = (-np.asarray(psi_app, float).reshape(nw, nh) / TWO_PI).T.ravel()

    p1 = sl.get("profiles_1d") or {}
    pres = list(p1.get("pressure", []))
    ppr = [-v for v in p1.get("dpressure_dpsi", [])]
    ffp = [-v for v in p1.get("f_df_dpsi", [])]
    fpol = list(p1.get("f", []))
    qpsi = _q_on_uniform(p1.get("fylite:q_psi_norm"), p1.get("q"), nw)

    bd = (sl.get("boundary") or {}).get("outline") or {"r": [], "z": []}
    lim_r, lim_z = (limiter or ([], []))

    return {
        "header": f"fylite AppSession {doc.get('fylite:created', '')}",
        "nw": nw, "nh": nh,
        "rdim": r[-1] - r[0], "zdim": z[-1] - z[0],
        "rcentr": rcentr, "rleft": r[0], "zmid": 0.5 * (z[0] + z[-1]),
        "rmaxis": gq["magnetic_axis"]["r"], "zmaxis": gq["magnetic_axis"]["z"],
        "simag": -gq["psi_axis"] / TWO_PI, "sibry": -gq["psi_boundary"] / TWO_PI,
        "bcentr": bcentr, "current": gq["ip"],
        "fpol": _fit(fpol, nw), "pres": _fit(pres, nw),
        "ffprim": _fit(ffp, nw), "pprime": _fit(ppr, nw),
        "psirz": psirz, "qpsi": qpsi,
        "nbbbs": len(bd["r"]), "rbbbs": list(bd["r"]), "zbbbs": list(bd["z"]),
        "limitr": len(lim_r), "rlim": list(lim_r), "zlim": list(lim_z),
    }


def _fit(src, n: int):
    """A uniform-grid profile resampled onto ``n`` points — the kernel's.

    Only the "no profile at all" policy is decided here: a page that ran
    without one gets zeros, not an extrapolated nothing.
    """
    return np.zeros(n) if not len(src) else kernel.resample_uniform(src, n)


def _q_on_uniform(x, q, n: int):
    """``q`` sampled onto ``n`` uniform points, extrapolated past both ends
    — the kernel's (:func:`fylite.kernel.to_uniform_extrap`, where the
    reason it extrapolates rather than clamps is written down).

    The page traces q only over roughly [0.06, 0.995]: the surface
    degenerates at the axis and the separatrix is singular at the boundary.
    """
    if not x or not q or len(x) < 2:
        return np.zeros(n)
    return kernel.to_uniform_extrap(x, q, n)


def write_geqdsk(doc: dict, path: str | Path, **kw) -> Path:
    """Convert a session document and write it out as a g-file.

    ★The formatter used to live here — a full copy of the format's column
    rules, in the module that reads the browser's session JSON.  It is in
    :mod:`fylite.io.geqdsk` now, beside the reader; what stays here is the
    one thing that is genuinely this module's: the app→IMAS conversion
    :func:`to_geqdsk` does.
    """
    from .io import geqdsk as _g
    return _g.write_geqdsk(to_geqdsk(doc, **kw), path)


def to_document(doc: dict, **kw) -> dict:
    """The session as an **fyo document** (:mod:`fylite.fyo`).

    ★The session's own JSON is the browser's shape; this is the shape the
    rest of the world reads — the equilibrium in IMAS DD names via
    :func:`fylite.fyo.equilibrium`, the page's inputs kept verbatim under
    ``fylite:config``, and the result channels beside them.  Sessions
    without a result convert to their config alone: a page that only holds
    inputs is a document, not an error.
    """
    if not has_result(doc):
        return {"@context": dict(fyo.CONTEXT), "@type": TYPE,
                "@id": str(doc.get("@id", "fylite:session")),
                "fylite:config": config(doc), **_provenance(doc)}
    out = fyo.equilibrium(to_geqdsk(doc, **kw),
                          source=str(doc.get("@id", "session")))
    out["fylite:session_type"] = TYPE
    out["fylite:config"] = config(doc)
    out.update(_provenance(doc))
    res = doc["fylite:result"]
    if "pf_active" in res:
        coils = res["pf_active"]["coil"]
        out["pf_active"] = {
            "@type": "fyo:pf_active",
            "fylite:name": [c["name"] for c in coils],
            "current": np.asarray([c["current"]["data"] for c in coils], float),
        }
    if "magnetics" in res:
        fl = res["magnetics"]["flux_loop"]
        out["magnetics"] = {
            "@type": "fyo:magnetics",
            "flux": np.asarray([c["flux"]["data"] for c in fl], float),
            "fylite:reconstructed": np.asarray(
                [c["fylite:reconstructed"] for c in fl], float),
            "fylite:weight": np.asarray([c["fylite:weight"] for c in fl], float),
        }
    return out


def _provenance(doc: dict) -> dict:
    return {k: str(doc[k]) for k in
            ("fylite:page", "fylite:created", "fylite:psi_convention",
             "fylite:coil_current_units") if k in doc}


def to_hdf5(doc: dict, path: str | Path, **kw) -> Path:
    """Write the session as fyo-semantic HDF5 (needs ``h5py``).

    ★A one-liner on purpose: the session becomes an fyo document and
    :func:`fylite.fyo.write` puts it on disk.  This function used to be the
    package's SECOND HDF5 writer, with its own branch per section — so a
    section added to a document reached disk in one shape here and another
    there.  This is the HDF5 exit the browser deliberately does not carry
    itself (the only browser-side library that can write HDF5 is h5wasm at
    ~5.7 MB, against a 187 kB solver kernel).
    """
    return fyo.write(to_document(doc, **kw), path)
