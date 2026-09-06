"""The machine: where its description comes from, what it says, and what its
hardware DOES.

★**This distribution ships no machine data, and that is a deliberate
boundary, not an omission.**  fylite is code: a Grad-Shafranov kernel, the
transport and turbulence ports, the reconstruction row, the scenario layer.
A device — coil and vessel geometry, diagnostic positions, a limiter contour,
per-supply limits — is somebody's machine, described by whoever operates it,
under whatever terms they set.  Bundling one would make every copy of this
package a copy of that description too, and would put the licence of the code
and the licence of the data in the same box.

So the description is an INPUT.  Point ``$FYLITE_DEVICE_DIR`` at a directory
holding it, or hand every entry point an explicit path.  Nothing here guesses
a location: a wrong path is harder to diagnose than no path.

Layout the readers expect (all optional — you need only what you call):

===========================  ==================================================
``east_device.yaml``         fyo / IMAS-shaped device document (:func:`document`)
                             — **what the machine IS**: geometry, channels,
                             turns, both limiter contours, the passive set
``east_geom.txt``            optional; the computational box as an INDEPENDENT
                             check on what the document declares
                             (:func:`verify_solver_dims`, via
                             :mod:`fylite.io.efund`) — not a source
``rv6565.ddd``               vessel → loop/probe/grid response tables —
                             **cross-check only** (``vessel_table_check``, an oracle-tree function since T-4 第十刀)
``rfcoil.ddd``               coil → loop/probe response tables —
                             **cross-check only**: nothing on a live path
                             reads one any more (see
                             :func:`coil_response_tables`)
``kfile_defaults.nml``       EFIT ``&IN1`` / ``&BASIS`` namelist defaults.
                             ★不再有读者：`io.kfile` 已于 2026-09-01 移除；
                             这一格留着是因为装置卷宗仍可能带它
===========================  ==================================================

★``dprobe.dat``, ``limiter.json`` and ``fitweight.dat`` are NOT in that table
any more.  The first two described the machine — diagnostic positions, coil
and vessel rectangles, the validation-era limiter — in formats that were not
fyo, so the same machine was described twice and only one of the two
descriptions was the document.  Both are in ``east_device.yaml`` now
(``tools/efund-deck-to-fyo.py`` converts a deck that has only the Fortran
side).  ``fitweight.dat`` was never opened by this package at all: the
per-channel weights are the document's ``weight`` fields, and the probe gate
that inherited its ROLE is in ``operational.probe_gate``.

What remains above is either a binary response table or somebody else's
namelist — non-fyo formats, read in :mod:`fylite.io`, never re-described here.

A caller that has none of this can still use everything that does not need a
machine: the kernel, the 0-D layer, the transport step, the profile fit, TGLF
and NEO on a local flux surface.  Those take their geometry as arguments.

★**Why one module.**  "Where the deck is" and "what the deck says" were two
(``machine`` and ``device``), and the split cost more than it named: the
resolution rule was written twice (once as ``machine.path``, once as this
module's directory-or-file fallback), a caller had to know which half held a
given accessor, and the limiter had two readers — one of them with no callers
at all.  Locating a description and parsing it are the same subject: the
machine, as this package knows it.

★★**And so is what the hardware does.**  ``circuits`` and ``chords`` were two
more modules on that subject — a conductor's field and inductance, a sight
line's geometry and its integral along a flux map.  Both had converged onto
the kernel entry by entry until neither computed anything: what each still
held was the ARGUMENT — which conductors, which channel split, which sight
line — and every one of those arguments is read here.  ``circuits`` in
particular had to import this module to answer any of its questions, and
until recently took a deck PATH so it could re-read what its caller had
already resolved.  A face whose whole input is another module's output is
not a layer; it is that module's far side.

Sections: **1** where the description is · **2** what it says ·
**3** what the CONDUCTORS do · **4** what the SIGHT LINES do.

Nothing here decides physics.  The kernel computes its own mutual
inductances, its own elliptic integrals, its own quadrature; there are no
precomputed inductances and no second implementation of a formula in this
package.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: ★§4 samples a chord against a g-file's flux map, so this module reads
#: one.  `io.geqdsk` imports nothing from here, so the direction is one-way.
from .io import geqdsk

__all__ = ["MachineDataMissing", "DEVICE_ENV", "configured", "data_dir",
           "deck_path", "document",
           "probe_geometry", "device_geometry", "grid_box", "turnfc",
           "limiter_unit", "LIMITER_OPERATIONAL", "Element",
           "conductor_geometry", "conductor_geometry_from_document",
           "vessel_response_tables",
           "coil_response_tables", "flux_loop_positions", "pf_channel_map",
           "passive_set", "PASSIVE_GROUPS",
           #: ★the three point responses (`point_response` · `channel_response` ·
           #: `probe_element_response`) left with the rest of the old `fylite.circuits`
           #: face for the kernel repository's oracle tree (T-4 第十刀 · 第二十五刀,
           #: 2026-09-06): the loop and probe rows are `code/vstab`'s and
           #: `code/coilshare`'s now, and nothing in this package or the app
           #: called them.
           "element_arrays", "conductor_set"]


def _kernel():
    """The typed kernel face, imported lazily — this module is also read by
    tooling that has no library to load, and reading a deck must not require
    a library to be loadable."""
    from . import kernel
    return kernel


# --------------------------------------------------------------------------- #
# 1. WHERE the description is                                                 #
# --------------------------------------------------------------------------- #
#: Environment variable naming the directory that holds the device deck.
DEVICE_ENV = "FYLITE_DEVICE_DIR"


class MachineDataMissing(RuntimeError):
    """A machine description is needed and none is configured.

    Raised at the point of USE, never at import: a package that cannot be
    imported without a device deck cannot be used for the many things that
    do not need one.
    """


def _hint(what: str) -> str:
    return (f"{what} needs a machine description, and this distribution "
            f"ships none (see fylite.device).  Set ${DEVICE_ENV} to a "
            "directory holding the device deck, or pass an explicit path.")


def configured() -> bool:
    """True iff a device directory is set and exists."""
    raw = os.environ.get(DEVICE_ENV)
    return bool(raw) and Path(raw).expanduser().is_dir()


def data_dir() -> Path:
    """The configured device directory, or a loud error."""
    raw = os.environ.get(DEVICE_ENV)
    if not raw:
        raise MachineDataMissing(_hint("this call"))
    p = Path(raw).expanduser()
    if not p.is_dir():
        raise MachineDataMissing(
            f"${DEVICE_ENV} points at {p}, which is not a directory")
    return p


def deck_path(name: str) -> Path:
    """One file inside the configured device directory, checked to exist."""
    p = data_dir() / name
    if not p.exists():
        raise MachineDataMissing(
            f"{p} is missing — ${DEVICE_ENV} is set to {data_dir()}, but it "
            f"does not carry {name}")
    return p


_device_cache: dict[str, dict] = {}


def document(name: str | None = None) -> dict:
    """Load and contract-check a device document, cached per path.

    Reading and validation are :func:`load_device`'s; this only decides
    WHERE the document is, which is the decision that has to happen in
    exactly one place.

    ★``name=None`` resolves the DIRECTORY'S device document rather than a
    hard-coded ``east_device.yaml``: the historical default was an EAST-ism
    from when EAST was the only deck, and it made ``$FYLITE_DEVICE_DIR=
    machine_desc/iter`` fail on a filename while ``iter_device.yaml`` sat
    right there.  Exactly one ``*_device.yaml`` in the directory is that
    document; zero or several is refused with both facts named — guessing
    among machines is how a run gets the wrong tokamak.
    """
    if name is None:
        found = sorted(data_dir().glob("*_device.yaml"))
        if len(found) != 1:
            raise MachineDataMissing(
                f"${DEVICE_ENV} is set to {data_dir()}, which carries "
                f"{len(found)} *_device.yaml documents"
                + (f" ({', '.join(p.name for p in found)})" if found else "")
                + " — need exactly one, or an explicit name")
        name = found[0].name
    p = deck_path(name)
    key = str(p)
    if key not in _device_cache:
        _device_cache[key] = load_device(p)
    return _device_cache[key]


#: :func:`document` under a name that is not shadowed by the ``document=``
#: parameter of :func:`conductor_geometry`.
_configured_document = document


# --------------------------------------------------------------------------- #
# 2. WHAT the DOCUMENT says — the fyo/IMAS-shaped description and the names   #
#    derived from it                                                          #
# --------------------------------------------------------------------------- #
#: IDS groups a device description must carry (fail loud if one is missing —
#: a half-read device file would silently produce a half-built machine).
DEVICE_REQUIRED = ("magnetics", "pf_active", "wall", "interferometer",
                   "polarimeter", "data_source", "operational",
                   "machine", "solver_dims")


class DeviceDocumentError(ValueError):
    """A device description that cannot be read, or does not carry what a
    machine needs.

    ★Distinct from :class:`fylite.fyo.MeasurementInputError`, which is about a
    MEASUREMENT document.  They used to be one class because both halves
    lived in one module; a caller catching "bad input" around a shot's
    magnetics was also catching "this machine is not described".
    """


def load_device(path: str | Path) -> dict:
    """Read an fyo/JSON-LD device description keyed by IMAS DD v4 group names.

    This is the **one** place a device document is read and checked.  Reading
    itself is :func:`engine.load_document` (the single JSON/YAML loader);
    what this adds is the device contract: the semantic header must be present
    and every required IDS group must exist, because a device file that is
    quietly missing ``pf_active`` yields a machine with no coils rather than an
    error.

    The semantic keys (``@context``/``@id``/``@type``) are **kept** — callers
    that want the plain payload can pass it through
    :func:`engine.strip_semantic`.
    """
    from .engine import is_semantic, load_document
    doc = load_document(path)
    if not isinstance(doc, dict):
        raise DeviceDocumentError(f"device document {path}: expected a mapping, "
                             f"got {type(doc).__name__}")
    if not is_semantic(doc):
        raise DeviceDocumentError(
            f"device document {path}: no semantic header — expected one of "
            f"@context/@id/@type (fyo/JSON-LD)")
    missing = [g for g in DEVICE_REQUIRED if g not in doc]
    if missing:
        raise DeviceDocumentError(
            f"device document {path}: missing IDS group(s) {missing}; "
            f"present: {sorted(k for k in doc if not k.startswith(('@', '_')))}")
    return doc


# =========================================================================== #
# The device description, resolved LAZILY from configured machine data        #
# =========================================================================== #
# ★This distribution bundles NO device description (see this module).
# These names used to be module constants built at import from a bundled EAST
# document; a package that cannot be IMPORTED without a machine deck cannot be
# used for the many things that need no machine at all — the kernel, the 0-D
# layer, a transport step, a local TGLF solve.  So the document is read on
# first use of a name that depends on it, and the failure, when there is one,
# names the missing input instead of a traceback through the import system.
#
# ★The names are listed explicitly rather than caught by a bare __getattr__:
# a typo must still be an AttributeError, not a machine-data error.

_DERIVED_NAMES = frozenset({"LH_SYSTEMS", "ICRH_SYSTEMS", "ICRH_ANTENNAS", "ICRH_FREQUENCY_RANGE", "ECRH_SYSTEMS", "EAST_DEVICE", "EAST_CHANNEL_MAP", "POINT_NE_NODES", "POINT_FARADAY_C", "EAST_OPERATIONAL", "MDS_SERVER", "SOLVER_DIMS", "NPROBE", "PCS_TREE", "POINT_RPOL", "NMAGPRI", "NW", "NFCOIL", "POINT_ZPOL", "POINT_BASELINE_TOL", "B_PROBE_NODES", "FWTSI_MASK", "POINT_NCHORD", "PCS_PROBE_NODES", "BITMPI", "LIMITR", "PF_TURNS", "POINT_BASELINE_S", "BITFC", "PF_NODES", "POINT_THETAPOL", "DEFAULT_GRID", "POINT_FR_NODES", "PF_EFIT_ORDER", "POINT_WINDOW_MS", "MDS_IP", "XLIM", "POINT_LASER_LAMBDA", "EAST_MACHINE", "FWTMP2_MASK", "RCENTR", "PCS_PROBE_NODES_GEOM", "FLUX_LOOP_NODES", "NH", "MDS_BT", "NSILOP", "PSIBIT", "YLIM", "MDS_TREE"})

_DERIVED: dict | None = None


# --------------------------------------------------------------------------- #
# One spelling, declared; two tolerated on the way in                         #
# --------------------------------------------------------------------------- #
#: ★★The CANONICAL spelling of every shared device field is declared once, in
#: `rust/fylite/src/fyo.rs` (`@fyo-table DEVICE`), and generated into this
#: package and the browser (`_fyo_interface.py` / `app/assets/fyo-interface.js`).
#: Canonical means the DD's own where the DD has a name — so
#: `magnetics.flux_loop` is an ARRAY of structure, and `wall.description_2d`
#: is too.
#:
#: ★This repository wrote two other spellings before that table existed:
#: `east_device.yaml` wrapped the arrays as `{count, note, channel: [...]}`
#: and made `description_2d` a bare mapping, while `app/assets/fyodev.js`
#: wrote the DD arrays.  One machine, two dialects, and the divergence was
#: not caught until something compared them
#: (`python/tests/test_east_descriptions_agree.py`).
#:
#: ★★So reading TOLERATES the legacy shapes and writing does not.  A device
#: document is user-supplied input — somebody's machine, written by whoever
#: describes it — and refusing a shape this repository itself shipped would
#: turn a rename into a broken deck for them.  What must not happen is a NEW
#: file in the old shape, and that is a gate's job, not a reader's.
def _aos(node, legacy: str = "channel") -> list:
    """A DD array of structure, however this document spells it."""
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        seq = node.get(legacy)
        if isinstance(seq, list):
            return seq
        if isinstance(seq, dict):          #: a one-entry array written bare
            return [seq]
    return []


def _n(node, legacy: str = "channel") -> int:
    """How many entries an array of structure has.

    ★From the array, never from a `count` field beside it.  A count that can
    disagree with the thing it counts is a second source for a fact the first
    source already carries — and this document had one.
    """
    return len(_aos(node, legacy))


#: The limiter contours a device document may carry, by DD ``unit`` name.
#: EAST has two and they are not interchangeable: the inner wall is
#: ERA-DEPENDENT (``m-file`` is the validation-era 48-point contour, inner
#: R~1.30 m; ``efit_w_pf`` is the GUI-v5 60-point one, inner R~1.36 m), and
#: choosing the other one moves a limited boundary — on #70754, psi_bry
#: -0.393 -> -0.415.  So the name is part of the request, never a default
#: someone can drift.
LIMITER_OPERATIONAL = "efit_w_pf"


def limiter_unit(dev: dict | None = None, name: str | None = None) -> dict:
    """One ``wall.description_2d.limiter.unit`` entry, by DD ``name``.

    ★``unit`` is an ARRAY of STRUCTURES in the DD, and EAST genuinely has two
    contours, so this package reads it as one.  A document that carries a
    single mapping there — the shape this one had before the m-file contour
    moved in from ``limiter.json`` — is still accepted and returned as is:
    a machine with one wall should not have to spell it as a list.
    """
    d2 = (dev if dev is not None else _ensure()["EAST_DEVICE"])["wall"]["description_2d"]
    #: canonical is the DD's array; `east_device.yaml` wrote a bare mapping
    if isinstance(d2, list):
        d2 = d2[0] if d2 else {}
    unit = d2["limiter"]["unit"]
    if isinstance(unit, dict):
        return unit
    want = name or LIMITER_OPERATIONAL
    for u in unit:
        if str(u.get("name", "")) == want:
            return u
    #: ★only the CALLER's name is worth an error.  The default
    #: (`LIMITER_OPERATIONAL`) is an EAST document convention — 'efit_w_pf',
    #: the GUI-v5 operational contour — and demanding it of every machine
    #: made ITER's deck ('First Wall', 'Divertor') unreadable.  With no
    #: explicit name, the document's FIRST unit is its primary contour: that
    #: is the document's own ordering, not a guess of ours.
    if name is None and unit:
        return unit[0]
    raise DeviceDocumentError(
        f"no limiter unit named {want!r}; the document carries "
        + ", ".join(repr(str(u.get("name", "?"))) for u in unit))


def _limiter_unit(dev: dict) -> dict:
    """:func:`limiter_unit` during derivation, before ``_ensure`` can answer."""
    return limiter_unit(dev)


def _derive(dev: dict) -> dict:
    #: ★The diagnostic and data-source groups are OPTIONAL, per document:
    #: this used to subscript them all eagerly, which made `magnetics.pcs` —
    #: an EAST real-time tree — a precondition for computing a VACUUM CIRCUIT
    #: on ITER's deck.  A group the document does not carry now simply leaves
    #: its derived names out of the register, and module ``__getattr__``
    #: raises :class:`MachineDataMissing` naming the group at the point of
    #: USE — the same door-and-doorstep rule every other machine datum
    #: follows.  ``pf_active`` / ``wall`` / ``machine`` / ``solver_dims``
    #: stay required: without those there is no machine at all.
    _mag = dev["magnetics"]
    _probe = _mag.get("b_field_pol_probe")
    _loop = _mag.get("flux_loop")
    _pcs = _mag.get("pcs")
    _pf = dev["pf_active"]
    _lim = _limiter_unit(dev)
    _lh = dev.get("lh_antennas", {}).get("antenna", ())
    _itf = dev.get("interferometer")
    _pol = dev.get("polarimeter")
    _mds = (dev.get("data_source") or {}).get("mdsplus")

    #: the document itself, for the few callers that need a part of it no
    #: derived name covers (§2's `pf_channel_map` reads
    #: `pf_channel_elements`, which is where the BRSP map was frozen)
    EAST_DEVICE = dev
    EAST_MACHINE = dev["machine"]
    SOLVER_DIMS = dev["solver_dims"]

    # Machine facts (were literals in `_paths`; `_paths` is about paths).
    RCENTR = float(EAST_MACHINE["r_centre"])
    _g = EAST_MACHINE["default_grid"]
    DEFAULT_GRID = (float(_g["r_min"]), float(_g["r_max"]),
                    float(_g["z_min"]), float(_g["z_max"]))

    # Compile-time dimensions of the bundled solver.  DECLARED here, not chosen:
    # editing the config cannot change the `.so`.  `verify_solver_dims` checks the
    # declaration against the shipped tables so the two cannot drift apart.
    #: ★conditional on the numbers being THERE: a deck for a machine no
    #: libefit was ever built for declares `fylite:absent` instead (ITER's
    #: does, honestly), and the vacuum-circuit capabilities that deck CAN
    #: serve never read these.  Point-of-use refusal via __getattr__.
    if "nw" in SOLVER_DIMS:
        NW = int(SOLVER_DIMS["nw"])
        NH = int(SOLVER_DIMS["nh"])
        NFCOIL = int(SOLVER_DIMS["nfcoil"])
        NSILOP = int(SOLVER_DIMS["nsilop"])
        NPROBE = int(SOLVER_DIMS["nprobe"])


    EAST_OPERATIONAL = dev["operational"]
    """Non-IDS program settings from the same document (EFIT fit-control,
    read-time gates).  Kept as a mapping rather than re-exported as named
    constants: their consumer is the namelist writer, which names them there."""

    # --- diagnostic dimensions (est2 basis) -----------------------------------
    # NMAGPRI = 79 here is the est2 magpri count; the efit_east path uses a
    # DIFFERENT 76-probe basis (_paths.NPROBE) — distinct names on purpose.
    NFCOIL = _n(_pf, "coil")             # F-coils fitted by EFIT
    if _probe is not None and _loop is not None:
        NMAGPRI = _n(_probe)             # b_field_pol_probe (magpri), est2 basis
        NSILOP = _n(_loop)               # flux loops
        FLUX_LOOP_NODES = tuple(c["name"] for c in _aos(_loop))
        B_PROBE_NODES = tuple(c["name"] for c in _aos(_probe))

    # --- MDSplus node names ----------------------------------------------------
    if _mds is not None:
        MDS_TREE = _mds["tree"]
        MDS_SERVER = _mds["server"]
        MDS_IP = _mds["ip_node"]         # plasma current [kA] -> *1e3 = A
        MDS_BT = _mds["btor_node"]       # toroidal-field FoCS
        PCS_TREE = _mds["pcs_tree"]

    PF_NODES = tuple(c["name"] for c in _aos(_pf, "coil"))

    # --- coil model -----------------------------------------------------------
    #: ★EAST-deck flattenings, not DD canon: `turns` / `efit_index` /
    #: `bit_error` at COIL level exist only in the EAST document (the DD
    #: spells turns per element, `turns_with_sign`, which the circuit face
    #: reads).  Their consumers are the EFIT namelist flows; derive them only
    #: where the document carries them, refuse at the point of use elsewhere.
    def _coils_all_have(key):
        cs = _aos(_pf, "coil")
        return bool(cs) and all(key in c for c in cs)
    if _coils_all_have("turns"):
        PF_TURNS = tuple(int(c["turns"]) for c in _aos(_pf, "coil"))
    if _coils_all_have("efit_index"):
        PF_EFIT_ORDER = tuple(int(c["efit_index"]) for c in _aos(_pf, "coil"))
    if _coils_all_have("bit_error"):
        BITFC = tuple(float(c["bit_error"]) for c in _aos(_pf, "coil"))

    # --- per-channel absolute-error floors & operational weight masks ---------
    if (_probe is not None and _loop is not None
            and all("bit_error" in c and "weight" in c
                    for c in (*_aos(_probe), *_aos(_loop)))):
        BITMPI = tuple(float(c["bit_error"]) for c in _aos(_probe))
        PSIBIT = tuple(float(c["bit_error"]) for c in _aos(_loop))
        FWTMP2_MASK = tuple(float(c["weight"]) for c in _aos(_probe))
        FWTSI_MASK = tuple(float(c["weight"]) for c in _aos(_loop))

    # --- limiter ---------------------------------------------------------------
    #: from the outline, not from a `count` beside it (see :func:`_n`)
    LIMITR = len(_lim["outline"]["r"])
    XLIM = tuple(float(v) for v in _lim["outline"]["r"])
    YLIM = tuple(float(v) for v in _lim["outline"]["z"])

    # --- PCS real-time probe family (pcs_east tree, already-calibrated Tesla) --
    if _pcs is not None:
        PCS_PROBE_NODES_GEOM = tuple(
            (c["name"], float(c["position"]["r"]), float(c["position"]["z"]),
             float(c["angle"])) for c in _aos(_pcs.get("b_field_pol_probe")))
        PCS_PROBE_NODES = tuple(p[0] for p in PCS_PROBE_NODES_GEOM)

    # --- POINT polarimeter-interferometer -------------------------------------
    # Each chord yields TWO EFIT constraints: interferometer -> line-integrated n_e
    # (knelcur=1), polarimeter -> Faraday rotation (kpolar=1), EAST's MSE-analog.
    if (_itf is not None and _pol is not None and _aos(_itf)
            and _aos(_pol) and "gui_v5_fig" in EAST_OPERATIONAL):
        POINT_NCHORD = _n(_itf)
        POINT_NE_NODES = tuple(c["name"] for c in _aos(_itf))
        POINT_FR_NODES = tuple(c["name"] for c in _aos(_pol))
        POINT_ZPOL = tuple(float(c["line_of_sight"]["first_point"]["z"]) for c in _aos(_itf))
        POINT_RPOL = float(_aos(_itf)[0]["line_of_sight"]["first_point"]["r"])
        POINT_THETAPOL = float(_aos(_itf)[0]["line_of_sight"]["theta"])
        POINT_LASER_LAMBDA = float(_itf["laser_wavelength"])
        POINT_FARADAY_C = float(_pol["faraday_constant"])
        POINT_BASELINE_S = float(_pol["baseline"]["centre_s"])
        POINT_BASELINE_TOL = float(_pol["baseline"]["tolerance_s"])
        POINT_WINDOW_MS = float(EAST_OPERATIONAL["gui_v5_fig"]["intev_pol"]) * 1e3  # 30 ms

    # --- lower-hybrid antennas ------------------------------------------------
    # ★★These were a tuple of dicts in `scenario/model/lh.py` — frequencies,
    # nameplate powers, n_parallel bands, ports and MDSplus node names, as a
    # DEFAULT ARGUMENT of `east_launchers`.  A machine description in a
    # function signature, in a package whose README says it ships none.
    #
    # ★The machine-neutrality scan did not catch it because it looks for nine
    # SPECIFIC literals that leaked out of `_east_device.py` once, not for
    # machine constants — so it can only ever re-find the leak it was written
    # for.  `test_est2_gui.py` now also refuses an MDSplus-shaped node name
    # anywhere but here.
    LH_SYSTEMS = tuple(
        {"name": a["name"],
         "frequency": float(a["frequency"]),
         "max_power": float(a["fylite:max_power"]),
         "n_parallel": tuple(float(x) for x in a["fylite:n_parallel"]),
         "port": a.get("fylite:port"),
         "nodes": dict(a.get("fylite:nodes", {}))}
        for a in _lh)

    # --- ion- and electron-cyclotron systems ----------------------------------
    # ★The names are `ICRH_`/`ECRH_` and not `IC_`/`EC_` because this document
    # already carries `ic_coil` — the in-vessel FAST CONTROL COILS.  Two
    # unrelated machines' worth of hardware abbreviate to "ic" here, and a
    # reader who has to disambiguate from context will eventually not.
    #
    # ★★These carry no geometry, and that is the machine description, not an
    # omission: the ICRF frequency is a PER-SHOT quantity (the system covers
    # 25-70 MHz and `ic_antenna.xml`'s frequency node is empty) and the EC
    # launch position and steering angles are `[TBD]` in fydata's description
    # too.  Those two are exactly what sets the resonance layer and the
    # deposition location, so a model must take them as ARGUMENTS.  What is
    # NOT here cannot be defaulted from here — the lower-hybrid lesson
    # (a machine description living in a function signature), one block up.
    #
    # ★`ICRH_SYSTEMS` mixes two LEVELS, as the machine does: two antennas
    # (`I`, `B`) and eight transmitters that feed them.  Summing the power of
    # all ten DOUBLE-COUNTS; `level` is carried on every entry so that a
    # caller has to say which it means.  `ICRH_ANTENNAS` is the antenna-level
    # subset, for the common case (total launched power).
    _ic = dev.get("ic_antennas", {})
    _ec = dev.get("ec_launchers", {})
    ICRH_SYSTEMS = tuple(
        {"name": a["name"],
         "level": a.get("level"),
         "port": a.get("fylite:port"),
         "nodes": dict(a.get("fylite:nodes", {}))}
        for a in _ic.get("antenna", ()))
    ICRH_ANTENNAS = tuple(s for s in ICRH_SYSTEMS if s["level"] == "antenna")
    #: What the ICRF system can be TUNED to [Hz] — a capability, not a
    #: setting.  A model that takes a frequency should check it against this
    #: rather than invent one.
    ICRH_FREQUENCY_RANGE = tuple(
        float(x) for x in _ic.get("fylite:frequency_range", ()))
    ECRH_SYSTEMS = tuple(
        {"name": b["name"],
         "frequency": float(b["frequency"]),
         "mode": int(b["mode"]),
         "max_power": float(b["fylite:max_power"]),
         "port": _ec.get("fylite:port"),
         "nodes": dict(b.get("fylite:nodes", {}))}
        for b in _ec.get("beam", ()))


    #: The EAST measurement channel contract, one entry per flat target
    #: (grammar: fylite.engine channel-map table).  Counts and the TURNFC vector
    #: are reflected from the bundled geometry snapshot, not hand-copied.
    #:
    #: ★This name is the ``efit_east`` basis (76 probes), because that is what
    #: every existing caller means by it.  The est2 basis (79) is the same
    #: table with one row's count changed — see :func:`east_channel_map`.
    EAST_CHANNEL_MAP = None if "nw" not in SOLVER_DIMS else (
        {"target": "coils",
         "sources": [{"path": ("magnetics", "flux_loop", "*", "flux")}],
         "count": NSILOP,
         "label": "magnetics.flux_loop", "note": "efit_east SILOPT order",
         "missing": "magnetics.flux_loop is required"},
        {"target": "expmp2",
         "sources": [{"path": ("magnetics", "b_field_pol_probe", "*", "field")}],
         "count": NPROBE,
         "label": "magnetics.b_field_pol_probe", "note": "efit_east EXPMPI order",
         "missing": "magnetics.b_field_pol_probe is required"},
        {"target": "plasma",
         "sources": [{"path": ("ip",), "scalar_only": True},
                     {"path": ("magnetics", "ip", 0)},
                     {"path": ("ip",)}],
         "missing": "no plasma current: magnetics.ip[0] or scalar ip",
         "invert": {"path": ("magnetics", "ip", 0)}},
        {"target": "btor",
         "sources": [{"path": ("btor",)},
                     {"path": ("tf", "b_field_tor_vacuum_r"),
                      "scale": 1.0 / RCENTR}],
         "missing": "no toroidal field: tf.b_field_tor_vacuum_r or scalar btor",
         "invert": {"path": ("tf", "b_field_tor_vacuum_r"), "scale": RCENTR}},
        {"target": "brsp",
         "sources": [{"path": ("pf_active", "coil", "*", "current")}],
         "count": NFCOIL,
         "label": "pf_active.coil",
         "note": "EFIT order PF1 PF3 PF5 PF7 PF9 PF11 PF2 PF4 PF6 PF8 PF10 PF12",
         "missing": "pf_active.coil is required",
         "units": {"key": "coil_current_units", "default": "A",
                   "per_channel": {"A": turnfc},
                   "passthrough": ("A.turns", "A*turns", "A.turn", "At"),
                   "expose": "coil_current_units"}},
    )
    return {k: v for k, v in locals().items()
            if k in _DERIVED_NAMES and v is not None}


def _ensure(device: dict | None = None) -> dict:
    """Build (once) the names derived from the device description."""
    global _DERIVED
    if _DERIVED is None:
        _DERIVED = _derive(device if device is not None else document())
        #: published into the module namespace as well, because in-module
        #: functions look these up as globals and module __getattr__ does not
        #: fire for a global-name lookup inside the module itself
        globals().update(_DERIVED)
    return _DERIVED


#: Probe basis -> ``(channel count, order note)``.  Resolved through
#: :func:`_ensure` because both counts come from the device document.
#:
#: ★★EAST is described on two probe bases and this package speaks both: the
#: est2 / GUI_v5 path fits 79 magpri channels, the processed ``efit_east``
#: tree 76.  The channel map hard-wired the second while
#: :func:`fylite.fyo.measurements` wrote whatever the flat dict carried — so
#: a document this package WROTE for an est2 shot could not be read back by
#: this package:
#:
#:     MeasurementInputError: magnetics.b_field_pol_probe needs exactly 76
#:                            channels (efit_east EXPMPI order), got 79
#:
#: Measured on #137985 @ 4.0 s, which is an est2 shot — the reference
#: discharge this repository's own examples are built on.
#:
#: ★The fix is not "accept either length".  Different basis = different probe
#: SET = different response rows; a 76-channel document read on an est2 host
#: would be read against the wrong ones.  The basis is DECLARED in the
#: document (:data:`BASIS_KEY`) and checked against what is actually there.
BASIS_KEY = "fylite:channel_basis"

#: The basis assumed for a document that declares none — the efit_east files
#: predate the declaration and are still read.
DEFAULT_BASIS = "efit_east"


def probe_bases() -> dict:
    d = _ensure()
    return {"efit_east": (int(d["NPROBE"]), "efit_east EXPMPI order"),
            "est2": (int(d["NMAGPRI"]), "est2 magpri order")}


def probe_basis_of(n_channels: int) -> str:
    """The basis whose probe count is ``n_channels`` — fail loud on any other
    length.  Total and unambiguous: the two counts differ."""
    bases = probe_bases()
    for basis, (count, _) in bases.items():
        if count == n_channels:
            return basis
    known = ", ".join(f"{b}={c}" for b, (c, _) in bases.items())
    raise DeviceDocumentError(
        f"magnetics.b_field_pol_probe has {n_channels} channels, which is no "
        f"known EAST probe basis ({known})")


def east_channel_map(basis: str = DEFAULT_BASIS) -> tuple:
    """The channel contract for one probe basis.

    Only the probe row differs — the 35 flux loops and the 12 F-coils are the
    same set either way — so this rewrites that one entry rather than
    carrying a second table to keep in step.
    """
    bases = probe_bases()
    if basis not in bases:
        raise DeviceDocumentError(
            f"unknown probe basis {basis!r}; known: {sorted(bases)}")
    count, note = bases[basis]
    return tuple({**e, "count": count, "note": note}
                 if e["target"] == "expmp2" else e
                 for e in _ensure()["EAST_CHANNEL_MAP"])


from contextlib import contextmanager as _contextmanager


@_contextmanager
def bound(deck_dir):
    """Resolve device-derived names from ``deck_dir`` WITHIN this block.

    ★The one-machine-per-process rule stands — :func:`use_device` still
    refuses to re-bind silently, because half the package may hold
    references to the derived constants.  What the case corpus needs
    (S-2: `fylite cases --run`, where the CATALOGUE names the machine) is
    a bounded exception with a restore contract: the previous resolution —
    `_DERIVED` and every published global — is saved and put back whichever
    way the block exits, so a holder outside the block never observes the
    other machine.  Single-threaded by assumption, like the CLI it serves.
    """
    global _DERIVED
    saved_env = os.environ.get(DEVICE_ENV)
    saved_derived = _DERIVED
    saved_globals = {k: globals()[k] for k in _DERIVED_NAMES if k in globals()}
    os.environ[DEVICE_ENV] = str(deck_dir)
    _DERIVED = None
    for k in saved_globals:
        del globals()[k]
    try:
        yield
    finally:
        if saved_env is None:
            os.environ.pop(DEVICE_ENV, None)
        else:
            os.environ[DEVICE_ENV] = saved_env
        for k in _DERIVED_NAMES:
            globals().pop(k, None)
        globals().update(saved_globals)
        _DERIVED = saved_derived


def use_device(device: dict) -> None:
    """Use ``device`` (an already-loaded document) for the derived names.

    For a caller that has the description in hand and does not want it read
    from ``$FYLITE_DEVICE_DIR``.  Refuses to re-bind silently: the constants
    are cached and half the package may already hold references to them.
    """
    global _DERIVED
    if _DERIVED is not None:
        raise DeviceDocumentError(
            "the device description is already resolved; call use_device() "
            "before anything else touches a device-derived name")
    _ensure(device)


def __getattr__(name: str):
    if name in _DERIVED_NAMES:
        got = _ensure()
        if name not in got:
            #: derived from an OPTIONAL group the document does not carry —
            #: the refusal happens here, at the point of use, so a vacuum
            #: circuit on a deck without EAST's diagnostics still computes
            raise MachineDataMissing(
                f"{name} derives from a diagnostic / data-source group the "
                f"configured device document does not carry "
                f"(${DEVICE_ENV}={data_dir()})")
        return got[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def verify_solver_dims(geom_path=None) -> dict:
    """Check the declared solver dims against the geometry DECK's box.

    The declaration lives in config so the code carries no machine numbers,
    but a config that disagrees with the shipped artifact is worse than a
    literal — it looks authoritative and is wrong.

    ★★This must read the DECK, not :func:`grid_box`.  ``grid_box`` answers
    from the document now, so checking against it would compare the
    declaration with itself and pass unconditionally — a green light that
    means nothing, which is the failure mode this function exists to prevent.
    The deck reader lives in :mod:`fylite.io.efund`, and this is the one
    caller that wants it.

    Skips (``ok`` is None) when the deck directory carries no
    ``east_geom.txt``: there is then nothing independent to check against,
    and reporting that plainly beats inventing a verdict.
    """
    from .io import efund
    p = Path(geom_path) if geom_path is not None else None
    if p is None:
        p = deck_path("east_geom.txt")
        if not p.exists():
            return {"declared": {"nw": _ensure()["NW"], "nh": _ensure()["NH"]},
                    "box": None, "ok": None,
                    "note": f"no independent geometry deck at {p}"}
    got = efund.read_geom_box(p)
    nw, nh = _ensure()["NW"], _ensure()["NH"]
    if (got["nw"], got["nh"]) != (nw, nh):
        raise DeviceDocumentError(
            f"solver_dims declares {nw}x{nh} but the geometry deck "
            f"{got['source']} defines {got['nw']}x{got['nh']}")
    box = tuple(float(v) for v in _ensure()["DEFAULT_GRID"])
    if tuple(got["grid"]) != box:
        raise DeviceDocumentError(
            f"machine.default_grid declares {box} but the geometry deck "
            f"{got['source']} defines {tuple(got['grid'])}")
    return {"declared": {"nw": nw, "nh": nh}, "box": got, "ok": True}


# --------------------------------------------------------------------------- #
# 3. WHAT the deck says                                                       #
# --------------------------------------------------------------------------- #
def _resolve(path, name: str) -> Path:
    """``name`` inside ``path`` when that is a directory, ``path`` itself when
    it names a file, and the configured deck when it is ``None``.

    ★All three forms are in use: this module's readers were written against a
    file, the conductor-deck readers that joined it were written against a
    DIRECTORY, and most callers pass nothing at all.  Resolving that here is
    one rule; leaving it to each reader is how a deck directory ends up being
    opened as a namelist.

    ★★An explicit path used to skip the existence check that the configured
    deck gets: only the ``None`` branch went through :func:`deck_path`, so a
    caller who passed a directory lacking the file got a bare
    ``FileNotFoundError`` naming a path, while a caller who passed nothing got
    :class:`MachineDataMissing` naming the file, the variable and what to do.
    That is the wrong way round — the explicit-path caller is the one who
    handed over a directory and is owed the more specific error — and it is
    how ``fylite run`` came to report ``[Errno 2] ... rfcoil.ddd`` instead of
    saying that this distribution ships no Green response tables.
    """
    if path is not None:
        p = Path(path)
        q = p / name if p.is_dir() else p
        if not q.exists():
            raise MachineDataMissing(
                f"{q} is missing: {name} was looked for in {p}, which does "
                f"not carry it. Point ${DEVICE_ENV} (or the explicit path) at "
                "a deck that has it — note that this distribution ships no "
                "Green response tables (rfcoil.ddd / rv6565.ddd).")
        return q
    return deck_path(name)


def diagnostic_geometry_from_document(doc: dict) -> dict:
    """Magnetic-diagnostic positions out of an **fyo device document**.

    Reads ``magnetics.b_field_pol_probe`` and ``magnetics.flux_loop`` in the
    DD spelling ``app/assets/fyodev.js`` writes: ``position: [{r, z}]`` on
    both, plus ``poloidal_angle`` [rad] and the namespaced ``fylite:angle_deg``
    / ``fylite:length`` on a probe.  Either the browser's bare
    ``b_field_pol_probe: [...]`` list or this package's
    ``b_field_pol_probe: {count, note, channel: [...]}`` wrapper is accepted —
    the same machine described two ways round should not need two readers.

    ★★Why this exists.  These positions used to come out of the efund Fortran
    deck ``dprobe.dat``, which made the Python side the only host that needed
    a deck at all: the browser has always carried them in the document.  That
    is the same one-geometry-two-sources split
    :func:`conductor_geometry_from_document` was written to close, one IDS
    over.  ``fylite:angle_deg`` is carried BESIDE the DD ``poloidal_angle``
    rather than derived from it because the derivation is lossy — 12 of
    EAST's 79 probe angles do not survive a degrees->radians->degrees round
    trip, and a k-file writes the degrees.
    """
    mag = doc.get("magnetics") or {}

    def channels(name):
        sec = mag.get(name)
        if isinstance(sec, dict):            # this package's wrapper
            sec = sec.get("channel")
        return list(sec or ())

    def pos(c, what, i):
        p = c.get("position")
        if isinstance(p, list):
            p = p[0] if p else None
        if not p or "r" not in p or "z" not in p:
            raise DeviceDocumentError(
                f"{what} {i} ({c.get('name', '?')}) carries no position/r,z; "
                "the device document does not describe where its diagnostics "
                "are")
        return float(p["r"]), float(p["z"])

    probes, loops = channels("b_field_pol_probe"), channels("flux_loop")
    pr = [pos(c, "b_field_pol_probe", i) for i, c in enumerate(probes)]
    fl = [pos(c, "flux_loop", i) for i, c in enumerate(loops)]

    def angle_deg(c):
        #: ★the namespaced degrees win when present; `poloidal_angle` is the
        #: DD spelling and the fallback, exactly as `fyodev.js` reads it back.
        if c.get("fylite:angle_deg") is not None:
            return float(c["fylite:angle_deg"])
        return math.degrees(float(c.get("poloidal_angle") or 0.0))

    return {
        "probes": {"r": [r for r, _ in pr], "z": [z for _, z in pr],
                   "angle_deg": [angle_deg(c) for c in probes],
                   "length": [float(c.get("fylite:length") or 0.0)
                              for c in probes],
                   "node": [str(c.get("name", "")) for c in probes]},
        "flux_loops": {"r": [r for r, _ in fl], "z": [z for _, z in fl],
                       "node": [str(c.get("name", "")) for c in loops]},
    }


def grid_box() -> dict:
    """The computational box, from the fyo device document.

    Returns ``nw``/``nh``, the box ``grid = (rmin, rmax, zmin, zmax)``, the
    uniform axes ``rgrid``/``zgrid`` on it, and ``source``.

    ★It used to parse ``east_geom.txt``, which said the same thing the
    document already said — ``solver_dims.nw``/``nh`` and
    ``machine.default_grid`` — down to the last digit.  Two spellings of one
    box is the arrangement that lets them drift; the deck reader is
    :func:`fylite.io.efund.read_geom_box` now and its job is to be the thing
    the document is CHECKED against (:func:`verify_solver_dims`), not a
    second place to read it from.
    """
    d = _ensure()
    #: ★no compiled solver, no compiled dims: a deck whose `solver_dims`
    #: honestly says `fylite:absent` (ITER's) still has a default BOX, and
    #: the free-boundary grid on it is the KERNEL's choice — 65 x 65, the
    #: same square the browser twin solves every machine on.
    nw = int(d["NW"]) if "NW" in d else 65
    nh = int(d["NH"]) if "NH" in d else 65
    rmin, rmax, zmin, zmax = (float(v) for v in d["DEFAULT_GRID"])
    return {"nw": nw, "nh": nh,
            "grid": (rmin, rmax, zmin, zmax),
            "rgrid": np.linspace(rmin, rmax, nw),
            "zgrid": np.linspace(zmin, zmax, nh),
            "source": "fyo:device_document"}


def turnfc() -> list[float]:
    """``TURNFC`` — total turns per coil in EFIT F-coil order.

    ★The document's ``pf_active.coil[].turns`` reordered by each coil's own
    ``efit_index``, rather than the sixth column of ``east_geom.txt``.  Same
    twelve numbers; one of them is a description of the machine and the other
    is a Fortran snapshot that happens to agree.
    """
    d = _ensure()
    turns, order = d["PF_TURNS"], d["PF_EFIT_ORDER"]
    return [float(turns[i]) for i in order]


def probe_geometry(*, document=None) -> dict:
    """Per-channel probe R, Z, angle [deg] and length, from the device
    document (:func:`document` when none is passed).

    ★It used to take a deck path and parse ``dprobe.dat``'s ``XMP2`` /
    ``YMP2`` / ``AMP2`` / ``SMP2``.  The parameter is gone rather than
    ignored: a caller that still hands over a deck should fail loudly, not
    be quietly answered from a different machine's description.
    """
    doc = document if document is not None else _configured_document()
    g = diagnostic_geometry_from_document(doc)["probes"]
    return {**g, "source": "fyo:device_document"}


def device_geometry(*, document=None) -> dict:
    """Where every fitted diagnostic sits in the (R, Z) plane.

    * ``probes`` — the 79 est2 magnetic probes with their ``east``-tree names;
    * ``flux_loops`` — the 35 loops (``RSI``/``ZSI``) with their node names;
    * ``point_chords`` — the 11 POINT horizontal chords, each carrying an
      interferometer and a polarimeter constraint;
    * ``limiter`` — the GUI_v5 60-point contour.

    Channel order matches the diagnostic vectors on a reconstruction result,
    so an ``alive``/``fwt`` mask indexes straight into ``probes`` /
    ``flux_loops``.

    ★Everything here comes from ONE place — the fyo device document.
    Positions used to come from the Fortran deck ``dprobe.dat`` while the
    names, chords and limiter came from the document, and the two had to be
    checked against each other for channel count because nothing else made
    them agree.  A machine described in one place cannot disagree with
    itself, so the check that guarded the seam is gone with the seam.
    """
    doc = document if document is not None else _configured_document()
    g = diagnostic_geometry_from_document(doc)
    pr, fl = g["probes"], g["flux_loops"]
    #: ★the names still come from the DERIVED table rather than from the
    #: channel entries read just above: `B_PROBE_NODES` is what every
    #: measurement path indexes by, so a mismatch between it and the section
    #: it is derived from is a defect in `_derive`, not a fact to paper over.
    for what, have, names in (("probes", pr["r"], _ensure()["B_PROBE_NODES"]),
                              ("flux loops", fl["r"], _ensure()["FLUX_LOOP_NODES"])):
        if len(have) != len(names):
            raise DeviceDocumentError(
                f"the device document positions {len(have)} {what} but names "
                f"{len(names)} of them")
    return {
        "probes": {"r": pr["r"], "z": pr["z"],
                   "angle_deg": pr["angle_deg"], "length": pr["length"],
                   "node": list(_ensure()["B_PROBE_NODES"])},
        "flux_loops": {"r": fl["r"], "z": fl["z"],
                       "node": list(_ensure()["FLUX_LOOP_NODES"])},
        "point_chords": {"z": list(_ensure()["POINT_ZPOL"]),
                         "r_ref": float(_ensure()["POINT_RPOL"]),
                         "theta": float(_ensure()["POINT_THETAPOL"]),
                         "node_ne": list(_ensure()["POINT_NE_NODES"]),
                         "node_faraday": list(_ensure()["POINT_FR_NODES"])},
        "limiter": {"r": list(_ensure()["XLIM"]), "z": list(_ensure()["YLIM"])},
        "source": "fyo:device_document",
    }


# --------------------------------------------------------------------------- #
# the conductor deck                                                          #
# ★These readers used to live in `circuits`, beside the field formulas that   #
# consume them — so "where the conductors are" and "what a conductor does"    #
# were one module.  Reading a deck is machine description; it belongs here    #
# with the probes and the box, and `circuits` is left with the physics faces. #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Element:
    """One axisymmetric conductor element, EFIT/efund parallelogram convention.

    (r, z) is the element centre; ``w`` the horizontal extent; ``h`` the
    length of the side that makes angle ``a2`` [deg] with the horizontal
    (a2 = 90 -> plain w x h rectangle); ``a`` an overall rotation [deg]
    (zero for every EAST element in the bundled deck).
    """
    r: float
    z: float
    w: float
    h: float
    a: float = 0.0
    a2: float = 90.0

    @property
    def area(self) -> float:
        # plain w*h — the deck's dr*dz convention
        return self.w * self.h


def flux_loop_positions(*, document=None):
    """``(R, Z)`` of the flux loops, as arrays.

    ★The same two arrays :func:`device_geometry` returns under
    ``flux_loops``; this face exists because two callers want the positions
    without the names, and it reads them through the SAME document parser —
    the second reader it replaced (in ``circuits``) had its own regex for
    the deck's ``RSI`` / ``ZSI``.
    """
    g = diagnostic_geometry_from_document(
        document if document is not None else _configured_document())
    return (np.asarray(g["flux_loops"]["r"], float),
            np.asarray(g["flux_loops"]["z"], float))


def conductor_geometry_from_document(doc: dict) -> dict:
    """The coil + vessel geometry out of an **fyo device document**.

    Reads ``pf_active.coil[].element[].geometry.rectangle`` and
    ``wall.description_2d[].vessel.unit[].element[].geometry.rectangle``,
    with the two tilt angles that have no DD rectangle spelling carried as
    ``fylite:a1`` / ``fylite:a2`` — exactly the shape
    ``app/assets/fyodev.js`` writes.

    ★★Why this exists.  The BROWSER has carried this geometry in its device
    document since fyodev.js was written; Python did not, and read the same
    rectangles out of the Fortran deck ``dprobe.dat`` instead.  One geometry,
    two sources, and only one of them fyo — so a device edited in the browser
    and exported could not be handed to Python without also shipping a deck
    that agrees with it, and nothing checked that it did.

    :func:`conductor_geometry` prefers this whenever the document carries the
    rectangles, and falls back to the deck when it does not.  The deck stays
    the importer for a machine that only has one; it stops being a second
    source for a machine that has both.
    """
    def rect(el: dict, unit: dict):
        """``Element``, or ``None`` when the element carries no rectangle.

        ★The two cases are NOT the same and must not share an answer.  An
        element with no ``geometry.rectangle`` at all means this document
        does not carry geometry — a machine described somewhere else.  An
        element with a PARTIAL rectangle means the document is malformed,
        and answering anyway would silently run the wrong machine.
        """
        g = (el.get("geometry") or {}).get("rectangle")
        if not g:
            return None
        missing = [k for k in ("r", "z", "width", "height") if k not in g]
        if missing:
            raise DeviceDocumentError(
                f"element geometry.rectangle missing {missing}; "
                f"got {sorted(g)}")

        def tilt(key, default):
            """``fylite:a1`` / ``fylite:a2`` from the ELEMENT, else its UNIT.

            ★★Both placements are real and this reader used to honour only
            one.  ``app/assets/fyodev.js`` writes the pair on the vessel
            **unit** (``u['fylite:a1'] = v.a1``, beside
            ``fylite:resistivity_uohm_m`` and ``fylite:group``); this reader
            looked for it on the **element**, and the case that claimed to
            use "exactly the shape fyodev.js writes" put it on the element
            too, so nothing caught the disagreement.  On EAST that is not
            cosmetic: 16 of the 40 vessel segments have ``a2 != 90`` and 14
            have ``a1 != 0``, so a browser-exported document read here came
            back with every one of them flattened into a plain rectangle —
            a wrong machine that raises nothing.
            """
            for src in (el, unit):
                if src.get(key) is not None:
                    return float(src[key])
            return default

        #: ★a2 defaults to 90 (a plain rectangle), NOT to 0 — the efund deck
        #: uses the same substitution and for the same reason: a2 = 0 is not
        #: a degenerate rectangle, it is a missing value.
        return Element(float(g["r"]), float(g["z"]),
                       float(g["width"]), float(g["height"]),
                       tilt("fylite:a1", 0.0), tilt("fylite:a2", 90.0) or 90.0)

    def elements(units) -> list:
        out = []
        for u in units or ():
            for el in u.get("element", ()) or ():
                e = rect(el, u)
                if e is not None:
                    out.append(e)
        return out

    coils = elements((doc.get("pf_active") or {}).get("coil", ()))
    d2 = (doc.get("wall") or {}).get("description_2d") or []
    if isinstance(d2, dict):
        d2 = [d2]
    vessel = []
    for d in d2:
        vessel += elements(((d.get("vessel") or {}).get("unit")) or ())
    if not coils:
        raise DeviceDocumentError(
            "device document carries no pf_active coil element geometry — "
            "use conductor_geometry() to read the deck instead")
    return {"coils": coils, "vessel": vessel}


#: ★``_document_has_rectangles`` stood here — a predicate with no caller.
#: It asked whether a device document carried conductor rectangles, from
#: when the reader had to choose between the document and a deck; the deck
#: readers are gone, so there is nothing to choose.


def conductor_geometry(*, document=None) -> dict:
    """The coil + vessel geometry, from the fyo device document.

    ★It used to fall back to parsing the efund deck ``dprobe.dat`` — the
    &IN3 namelist followed by 14 F-coil lines and 40 vessel lines — whenever
    the document carried no rectangles, and EAST's document carried none, so
    the fallback WAS the path.  The rectangles are in the document now
    (exported from that deck, bit-identical), and the deck parser lives in
    ``tools/efund-deck-to-fyo.py`` where an importer belongs: converting
    somebody else's format is a one-time job, not a thing the runtime does on
    every call.  See :func:`conductor_geometry_from_document`.
    """
    return conductor_geometry_from_document(
        document if document is not None else _configured_document())


def vessel_response_tables(path=None) -> dict:
    """Read ``rv6565.ddd``: three sequential unformatted records.

    rsilvs (nsilop x nvesel), rmp2vs (magpri x nvesel),
    gridvs (nw*nh x nvesel); nvesel=40, nsilop=35, magpri=79, nw=nh=65.
    Record markers are int32 byte counts and are verified, not assumed.
    """
    raw = _resolve(path, "rv6565.ddd").read_bytes()
    pos, rec = 0, []
    while pos < len(raw):
        n = int(np.frombuffer(raw, np.int32, 1, pos)[0]); pos += 4
        rec.append(np.frombuffer(raw, np.float64, n // 8, pos)); pos += n
        n2 = int(np.frombuffer(raw, np.int32, 1, pos)[0]); pos += 4
        if n2 != n:
            raise ValueError(f"rv6565.ddd: record marker mismatch {n} != {n2}")
    if [r.size for r in rec] != [35 * 40, 79 * 40, 65 * 65 * 40]:
        raise ValueError(f"rv6565.ddd: unexpected record sizes {[r.size for r in rec]}")
    return {
        "rsilvs": rec[0].reshape((40, 35)).T,          # Fortran (nsilop, nvesel)
        "rmp2vs": rec[1].reshape((40, 79)).T,
        # gridvs(kk, n), kk = (i-1)*nh + j with i the R index -> (n, iR, jZ)
        "gridvs": rec[2].reshape((40, 65, 65)),
    }


def coil_response_tables(path=None) -> dict:
    """Read ``rfcoil.ddd``: rsilfc (nsilop x nfcoil) + rmp2fc (magpri x nfcoil).

    Responses of the 35 flux loops / 79 probes to 1 A-turn in each of the
    12 BRSP channels, in the same Wb/rad convention as ``rv6565.ddd``.

    ★★**Nothing on a live path calls this.**  It is here for the same job
    the oracle tree's ``vessel_table_check`` does for the vessel: asking whether a
    machine's own Green table and its geometry still describe the same
    machine.  Both halves are computed now — the loop rows by
    the oracle tree's ``coil_loop_rows`` (kernel repository, since T-4 第十一刀)
    (``channel_response``/2π) and the probe rows by the kernel's probe
    response (``code/coilshare`` · ``code/reconstruction``), which is why
    ``rmp2fc`` has no reader at all — so a deck that is absent no longer
    stops a reconstruction.

    ★It mattered because this file was the ONE gate on the whole Python
    reconstruction path: this distribution ships no ``rfcoil.ddd``, the read
    was unconditional, and it happened before the first kernel call — so the
    path raised :class:`MachineDataMissing` for every input, and zeroing the
    coil currents did not help (the read is not conditional on their value).

    ★The two-path agreement is measured, not assumed (fywork CASE-09 G-01):
    computed vs frozen EAST ``rfcoil.ddd``, 7.7e-5 relative at ``nu=nv=8``,
    falling monotonically with quadrature order, uniform across channels
    (7.0e-6…7.7e-5) — filamentisation, not structure."""
    raw = _resolve(path, "rfcoil.ddd").read_bytes()
    pos, rec = 0, []
    while pos < len(raw):
        n = int(np.frombuffer(raw, np.int32, 1, pos)[0]); pos += 4
        rec.append(np.frombuffer(raw, np.float64, n // 8, pos)); pos += n
        n2 = int(np.frombuffer(raw, np.int32, 1, pos)[0]); pos += 4
        if n2 != n:
            raise ValueError(f"rfcoil.ddd: record marker mismatch {n} != {n2}")
    if [r.size for r in rec] != [35 * 12, 79 * 12]:
        raise ValueError(f"rfcoil.ddd: unexpected record sizes {[r.size for r in rec]}")
    return {"rsilfc": rec[0].reshape((12, 35)).T,
            "rmp2fc": rec[1].reshape((12, 79)).T}


def pf_channel_map() -> list[list[tuple[int, float]]]:
    """Which deck element(s) each BRSP channel drives — the MEASURED map (E-14).

    Per channel a list of ``(element_index, weight)`` with weights summing to
    ~1 (BRSP is ampere-total-turns).  Ten of the twelve channels drive one
    element; TWO drive a pair at ~0.175 / 0.825, the 44:204 turn split of a
    248-turn channel — which is why this was measured rather than taken from
    the channel names.

    ★★It is now READ, not measured.  The measurement compared each channel's
    flux-loop response column in ``rfcoil.ddd`` against the computed per-turn
    mutual of every deck element, and that table has been removed (LICENSE
    3.1).  The result it produced is frozen in ``_data/east_device.yaml``
    under ``pf_channel_elements``.

    ★This map is on the LIVE path — breakdown and vertical stability both
    need it — so it is device description shipped with the package, not a
    test fixture.  A frozen answer on the live path is worth saying out loud:
    the drift check the old code performed ("a residual here means tables and
    deck no longer agree") is GONE with the table, so a change to the deck
    geometry can no longer be caught by this route.

    """
    dev = _ensure()["EAST_DEVICE"]
    rows = dev.get("pf_channel_elements")
    if rows:
        return [[(int(e["element"]), float(e["weight"])) for e in row]
                for row in rows]
    #: ★No frozen map — derive it from the DOCUMENT's own statement: one
    #: channel per `pf_active.coil`, each element weighted by its share of
    #: the coil's total turns (`turns_with_sign`, DD canon).  That is exactly
    #: the rule the frozen EAST map encodes (44:204 of a 248-turn channel =
    #: 0.177/0.823), measured there only because EAST's deck predates the
    #: per-element turn counts.  A coil whose elements carry no turn count
    #: is refused — apportioning by guess would drive the wrong element.
    coil = dev["pf_active"]["coil"]
    coil = coil if isinstance(coil, list) else [coil]
    out, flat = [], 0
    for c in coil:
        elems = c.get("element") or []
        elems = elems if isinstance(elems, list) else [elems]
        turns = []
        for e in elems:
            tw = e.get("turns_with_sign", c.get("turns"))
            if tw is None:
                raise ValueError(
                    f"pf_active coil {c.get('name', '?')!r} carries neither "
                    "pf_channel_elements (frozen map) nor per-element "
                    "turns_with_sign — no honest way to say which element "
                    "this channel drives, or by how much")
            turns.append(abs(float(tw)))
        total = sum(turns) or 1.0
        out.append([(flat + i, w / total) for i, w in enumerate(turns)])
        flat += len(elems)
    return out


def element_arrays(elems):
    """An Element list as the six parallel C-contiguous arrays the kernel
    reads — ``(r, z, w, h, a, a2)``.

    ★The marshalling shape of :class:`Element`, so it belongs beside the
    class rather than in whichever caller needs it first.  It was private to
    ``circuits`` and reached across module lines by the design layer, which
    is how a private name ends up being a public one without being written
    down as such.
    """
    return tuple(np.ascontiguousarray([getattr(e, f) for e in elems], float)
                 for f in ("r", "z", "w", "h", "a", "a2"))


def conductor_set(*, document=None) -> dict:
    """Everything the circuit faces need from the machine, resolved ONCE:
    ``coils`` / ``vessel`` (Element lists), ``weights`` (the dense
    ``(n_channel, n_element)`` BRSP map) and ``channels`` (its sparse form).

    ★★This used to be the ONE place that decided document-or-deck for a
    circuit calculation, and that decision is gone: the geometry is the
    document's, always.  The history is worth keeping because it explains
    the signature.  Every scenario line resolved a deck DIRECTORY eagerly
    (``table_dir or data_dir()``) and handed the path down to five separate
    faces, each of which re-read it; an eagerly-resolved default is
    indistinguishable from an explicit override, so
    :func:`conductor_geometry`'s "the document wins when it carries
    rectangles" never fired on any of those lines — they always arrived with
    a path.  A machine described in the browser and exported was read from
    its deck instead, and nothing said so.  Taking the path away is what
    finally makes that unrepresentable.

    ★★``table_dir`` has since gone from those callers as well.  It meant
    the directory the Green RESPONSE TABLES live in (``rfcoil.ddd`` /
    ``rv6565.ddd``), and with the last live read of one gone — the
    reconstruction's coil→loop rows are computed now
    (the oracle tree's ``coil_loop_rows`` (kernel repository, since T-4 第十一刀)) — a parameter
    naming that directory said the machine could come from two places while
    every face here read only one.  What it never was is where the
    machine's GEOMETRY lives, and passing one path for both is how the two
    came apart.

    ★It also ends the possibility of half a machine: ``weights`` is built
    against the coil count of THIS geometry.  Resolving the two separately —
    which is what a caller holding a path and calling ``channel_weights()``
    with none was doing — could take the element count from the document and
    the elements from the deck.
    """
    geo = conductor_geometry(document=document)
    chans = pf_channel_map()
    #: ★the dense form is the KERNEL's: the index direction is the entire
    #: content of this map (a transposed one is a different machine), so it
    #: has one host.  Imported lazily — reading a deck must not require a
    #: library to be loadable.
    from . import kernel
    return {"coils": geo["coils"], "vessel": geo["vessel"],
            "weights": kernel.channel_weights(chans, len(geo["coils"])),
            "channels": chans}


#: Which passive groups exist, and where each one's geometry comes from.
PASSIVE_GROUPS = ("inner_shell", "outer_shell", "passive_plates")


def passive_set(device, groups=("inner_shell",)):
    """Assemble the passive conductor set from the device document.

    ``inner_shell`` is the 40-element vessel; ``outer_shell`` and
    ``passive_plates`` are the groups EFIT has no response columns for.  All
    three come from ``east_device.yaml`` now — the first used to come from
    the Green-table deck, which is why this took a ``path``.

    ★That ``path`` was the last of it, and it outlived its reader: it was
    still being forwarded as ``conductor_geometry(path)`` after
    ``conductor_geometry`` became keyword-only, so this raised ``TypeError``
    on its own DEFAULT group.  Nothing caught it —
    ``test_call_sites_match.py`` only checked imported names at the time, and
    this is a module-local call.  It checks those too now.

    Returns ``(elements, eta_uohm_m_per_element, group_slices)``.

    The distinction that matters: the LINEARIZED work (M, R, coupling
    gradient -> growth rate, feedback) needs geometry only, so it can use
    all three groups.  The NONLINEAR evolution path pushes vessel current
    into the GS solve through ``VCURRT``, which is dimensioned to the 40
    tabulated segments — the extra groups have no response columns there
    (see ledger E-18's sibling note in E-17).
    """
    pp = device["pf_passive"]
    elems, etas, slices, start = [], [], {}, 0
    for name in groups:
        if name not in PASSIVE_GROUPS:
            raise ValueError(f"unknown passive group {name!r}; "
                             f"expected any of {PASSIVE_GROUPS}")
        if name == "inner_shell":
            got = conductor_geometry()["vessel"]
            eta = pp["vessel"]["resistivity_uohm_m"]
        else:
            spec = pp[name]
            got = [Element(*row) for row in spec["element"]]
            eta = spec["resistivity_uohm_m"]
        elems.extend(got)
        etas.extend([float(eta)] * len(got))
        slices[name] = slice(start, start + len(got))
        start += len(got)
    return elems, np.asarray(etas, float), slices


# =========================================================================== #
# 3. What the CONDUCTORS do — the electromagnetic face (was `circuits`)       #
# =========================================================================== #
#: PROVENANCE
#: ---------
#: * Algorithm structure adapted from fytok's ``fyeq/circuits.py``
#:   (fusion-yun/fytok @ b0648816).  Per the absorption contract this is a
#:   copy-adaptation, not an import: fixes on either side must be checked
#:   against the other.  ★It arrived as pure numpy — that half now lives in
#:   ``tests/oracles/em.py``, where being a second implementation is
#:   the point, and every formula named below is the kernel's.
#: * Resistivities are **device data**: they are carried in the device
#:   document under ``pf_passive`` / ``pf_active``, not here.  This module
#:   holds the formula and the unit conversion, never the values.
#:
#: Verified against independent references at introduction time:
#:
#: * R of vessel element 1 from η·2πR/(dR·dZ): 9.5189e-3 Ω from the deck
#:   geometry.  ★2026-09-01 移除了与一份机构内部工具的逐值核对记录（它引的是
#:   对方的数）：**留公式与本仓自己的值，不留别人的数**——去掉出处却留着数字，
#:   比两样都留更糟。
#: * the two-path acceptance: ψ response of the 40 vessel elements on the
#:   65×65 grid recomputed here vs the bundled ``rv6565.ddd`` — see
#:   ``vessel_table_check`` (the kernel repository's oracle tree since T-4 第十刀),
#:   run in its ``tests/test_circuits.py``.
#:
#: Units: SI throughout (H, Ω, m, Wb/A); µ0 is 4e-7·π exactly on both sides
#: of the ABI, matching the Fortran this line was checked against.
#:
#: ★There is no ``_RUST_MIN_SIZE`` and no ``_rust()`` returning None.  Both
#: existed to choose between a numpy half and the kernel below a size
#: threshold — two implementations of every quantity here, with an array
#: length deciding which one a caller got.


