"""Data sources ↔ the shapes the package computes on.

Everything here reads an external format or a live source and hands back
plain dicts / arrays, or writes one out; nothing here decides physics.
The package-wide semantic shape is the fyo document (:mod:`fylite.fyo`),
and these are its feeders:

* :mod:`.geqdsk` — EFIT g-file / a-file readers;
* :mod:`.gacode` — GACODE ``input.gacode`` profile + geometry bundle;
* (`.kfile` — the EFIT ``&IN1`` k-file writer — was removed 2026-09-01: it
  prepared input for a solver that is not in this distribution, and
  transcribed that solver's internals. Its live EAST MDSplus read moved
  into :mod:`.est2`, beside the reduction it always called.)
* :mod:`.mds` — EAST MDSplus (``efit_east`` tree) → measurement dict,
  Thomson / diamagnetic fetches.  ★Transport is the engine's read-only mdsip
  client (:class:`fylite.kernel.MdsSession`) since 2026-09-04 — the site
  ``MDSplus`` package is not imported anywhere in this package any more, and
  the local-tree mode (``KEFIT_MDS_ROOT``) went with it: the engine speaks
  the wire protocol, not the tree file format, and the only local tree that
  mode ever pointed at lived under the retired ``machine_desc/``;
* :mod:`.est2` — the est2-basis reduction (windowed means, drift, POINT)
  shared by the live mdsip path and the offline fyo/HDF5 dump reader;
* (`.imas_h5` and `.jetto_bin` — an IMAS-HDF5 flat reader and a JETTO
  binary reader — were removed 2026-09-04: no caller anywhere, and the
  engine reads IMAS HDF5 itself, in both layouts.)
* :mod:`.fydoc` — the data layer's document face (``libfylite_runtime.so``):
  any file → a bundle of fyo documents by CONTENT sniffing, and back out as
  fyo or IMAS DD layout (JSON / HDF5 / netCDF / g-file), plus merge and
  JSON-LD assembly of several sources;
* :mod:`.efund` — the EFIT/efund deck formats an EAST deck directory carries
  (``east_geom.txt``).  ★Not a data source: the box and the coil turns are in
  the device document, and this reads the deck only so the document can be
  CHECKED against it.

What stays outside: the device deck (:mod:`fylite.device` says where it
is, :mod:`fylite.device` parses it), the fyo documents themselves —
equilibrium AND measurement faces both in :mod:`fylite.fyo` — and the
browser session reader (:mod:`fylite.appsession`).
"""
from __future__ import annotations

from . import efund, est2, fydoc, gacode, geqdsk, mds  # noqa: F401

__all__ = ["efund", "est2", "fydoc", "gacode", "geqdsk", "mds"]
