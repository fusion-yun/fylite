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
  Thomson / diamagnetic fetches;
* :mod:`.est2` — the est2-basis reduction (windowed means, drift, POINT)
  shared by the live MDSplus path and the offline fyo/HDF5 dump reader;
* :mod:`.fydoc` — the data layer's document face (``libfylite_data.so``):
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
