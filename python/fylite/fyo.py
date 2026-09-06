"""fyo-semantic documents — the shape the Python side speaks in.

★**The division of labour this module exists to make literal.**  The physics
and the numerics live in the Rust kernel; Python's job is to *convert* what
a machine or a code wrote (a g-file, a device deck, an MDSplus reduction)
into an fyo-semantic structured document, hand that document's arrays to the
kernel, receive the answer as another fyo-semantic document, and put it on
disk.  Nothing here computes a plasma quantity — every number in a derived
document comes back from one kernel call.

Two directions, both declarative:

``equilibrium(g)``
    g-file (path or :func:`fylite.io.geqdsk.read_geqdsk` dict) → an
    ``fyo:equilibrium`` document laid out in IMAS DD names
    (``time_slice/profiles_2d/psi``, ``vacuum_toroidal_field/b0``, …).
``Ladder(doc)`` / ``derive(doc)``
    that document → the kernel's surface ladder, traced ONCE and held as
    an object the models share; ``derive`` returns it as a *second*
    ``fyo:equilibrium`` document whose ``profiles_1d`` carries ρ_tor, V,
    dV/dψ and the flux-surface averages, and whose ``fylite:miller`` section
    carries the local shape ladder — the SAME surfaces, because they come
    from the same kernel call.
``write(doc, path)`` / ``read(path)``
    the disk face: JSON(-LD) or HDF5 by suffix, generic over the document
    (groups for mappings, datasets for arrays, ``@``-keys as attributes), so
    a new section is a new key rather than a new writer branch.

Names are IMAS DD v4 where the DD has one; anything without a DD home is
prefixed ``fylite:`` so a reader can tell a standard field from ours.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import kernel

from . import _fyo_interface as _iface

from .io import geqdsk
from .engine import RunManifest as _RunManifest
from .engine import (apply_channel_map, invert_channel_map,
                     is_semantic, load_document, strip_semantic)

__all__ = ["FYO_PREFIX", "FYLITE_PREFIX", "CONTEXT", "vocabulary", "equilibrium", "as_geqdsk", "derive",
           "write", "read",
           "measurements", "as_measurements", "resolve_probe_basis",
           "MeasurementInputError",
           "grid_of", "flux_map_of", "psi_map_of", "core_profiles", "profiles_of",
           "beam_sources", "wave_sources", "merge_sources"]

#: fyo ontology IRI prefix (fyo-core prefix declaration) — a vocabulary
#: reference, never an import.  ★Home is here: it used to be defined in the
#: measurement module and imported BY this one, the document layer taking
#: its own prefix from a feeder.
FYO_PREFIX = "https://fusion-yun.github.io/fyo/latest/"

#: This package's own term space.  ★One spelling, declared once and
#: imported by every writer — see :data:`CONTEXT`.
FYLITE_PREFIX = "urn:fylite:"

#: The ``@context`` every document this module writes carries.  ``fylite:``
#: is this package's own term space — a document that mixes DD names with
#: local ones has to say which is which.
#:
#: ★★``urn:fylite:``, and it is the ONLY spelling.  There were three, one per
#: writer: this module said ``https://github.com/fusion-yun/fylite#``,
#: ``app/assets/fyodev.js`` said ``https://fusion-yun.github.io/fylite/ns#``,
#: and the run manifest and browser session said ``urn:fylite:``.  Three IRIs
#: for one term space means ``fylite:angle_deg`` in a device document and
#: ``fylite:angle_deg`` in a manifest are, to any reader that resolves a
#: prefix, two unrelated properties that merely look alike — so the
#: vocabulary gate could keep both hosts spelling the TERM identically while
#: they disagreed about what it named.  The urn form wins because it is what
#: the documents already on disk carry (the manifest, the device deck, the
#: browser's session export) and because it claims no web location this
#: project does not serve.
CONTEXT = {"fyo": FYO_PREFIX, "fylite": FYLITE_PREFIX}

_VOCAB_PATH = Path(__file__).resolve().parent / "_fyo_vocab.json"


def vocabulary() -> dict:
    """The ``fylite:`` terms **more than one host** writes into an fyo document.

    ``{term: {"gated": bool, "gloss": str}}``.

    ★This is the interchange contract, and it is a published artifact rather
    than knowledge spread through the writers.  A term only one host writes
    is that page's private extension and cannot diverge; these can, because
    two independent writers spell them — and one of them did, differently:
    ``psi_norm`` went out bare from two browser writers and prefixed from
    every Python one, inside documents all typed ``fyo:equilibrium``.  Bare,
    it claims IMAS-DD provenance the term does not have, so a reader looking
    for ``fylite:psi_norm`` found nothing and nothing raised.

    The browser reads the same table through the generated
    ``app/assets/fyo-names.js`` (``rust/build.sh``), for the same reason
    ``_abi.py`` is generated: two copies of a contract are not a contract.
    """
    import json as _json
    return _json.loads(_VOCAB_PATH.read_text())["terms"]

#: The fyo interface, GENERATED from the kernel's own declaration
#: (``rust/fylite/src/fyo.rs`` → ``rust/build.sh``): which document path
#: each kernel slot is written under, in which unit, at which rank.
#:
#: ★★It used to be literals here and different literals in
#: ``app/assets/session.js``, with only the *term* list shared — and the
#: browser copy of that had no reader at all.  A path is a contract between
#: two hosts, so it is declared once beside the code that produces the
#: numbers and generated into both, the way ``_abi.py`` is.
TABLES = _iface.TABLES

#: Path segments that are ARRAYS of structure: a walker steps into index 0
#: at each.  Declared with the paths rather than known by each walker.
AOS = frozenset(_iface.AOS)


def slot(table: str, key: str) -> dict:
    """The declared ``{path, units, rank}`` of one kernel slot."""
    try:
        return TABLES[table]["slots"][key]
    except KeyError:
        known = sorted(TABLES) if table not in TABLES else sorted(
            TABLES[table]["slots"])
        raise KeyError(
            f"fyo interface has no slot {table}/{key}; have {known}. "
            "Slots are declared in rust/fylite/src/fyo.rs and generated "
            "into _fyo_interface.py — add it there, not here.") from None


def path_of(table: str, key: str) -> str:
    """The document path of one kernel slot."""
    return slot(table, key)["path"]


def units_of(table: str, key: str) -> str:
    """The declared unit of one kernel slot."""
    return slot(table, key)["units"]


def _dig(node, path: str, *, create: bool):
    """Walk a declared path to ``(container, leaf)``.

    ★An AoS segment steps into index 0 — that is what
    ``time_slice/global_quantities/ip`` MEANS, and it is declared rather
    than known by each walker: a host that read ``time_slice`` as a mapping
    would build a document that looks right and that no DD reader can open.
    """
    segs = path.split("/")
    for seg in segs[:-1]:
        if seg in AOS:
            nxt = node.get(seg) if isinstance(node, dict) else None
            if not isinstance(nxt, list) or not nxt:
                if not create:
                    return None, segs[-1]
                nxt = [{}]
                node[seg] = nxt
            node = nxt[0]
            continue
        nxt = node.get(seg) if isinstance(node, dict) else None
        if not isinstance(nxt, dict):
            if not create:
                return None, segs[-1]
            nxt = {}
            node[seg] = nxt
        node = nxt
    return node, segs[-1]


_MISSING = object()


def get(doc: dict, table: str, key: str, default=_MISSING):
    """Read one declared slot out of a document."""
    node, leaf = _dig(doc, path_of(table, key), create=False)
    if node is None or leaf not in node:
        if default is _MISSING:
            raise KeyError(f"{table}/{key} ({path_of(table, key)}) is not in "
                           f"this {TABLES[table]['type']} document")
        return default
    return node[leaf]


def put(doc: dict, table: str, key: str, value):
    """Write one declared slot into a document, making the path as it goes."""
    node, leaf = _dig(doc, path_of(table, key), create=True)
    node[leaf] = value
    return doc


#: Kernel metric-row key → the ``profiles_1d`` name it is written under —
#: the leaf of each ``LADDER`` path, kept under its old name because that is
#: what the writers read.  ★The mapping itself is no longer spelled here.
PROFILE_NAMES = {k: v["path"].rsplit("/", 1)[-1]
                 for k, v in TABLES["LADDER"]["slots"].items()}


def _doc(type_: str, id_: str, **sections) -> dict:
    return {"@context": dict(CONTEXT), "@id": id_, "@type": type_, **sections}


def equilibrium(g, *, source: str | None = None,
                check_convention: bool | None = None,
                convention: str = "dpsi, per radian") -> dict:
    """A g-file → an ``fyo:equilibrium`` document (IMAS DD names).

    This is a *conversion*, not a computation: every number below is read
    from the deck.  ``source`` names the provenance in ``@id``; a path
    argument names itself.

    ★★T-C22 〔二〕's live half.  When this function OPENS THE FILE ITSELF —
    ``g`` is a path — the file's convention is measured before any of it is
    converted, and a file that does not measure as ``convention`` is REFUSED
    by name.  That is the whole point of the T-C22 series: a g-file carries
    no convention field, so reading one as though it were in ours is a
    guess, and the guess is silent.  The measurement (residual, margin, the
    region it was tested on) is stamped into the document, so what comes out
    says what was checked rather than merely having been checked.

    ★The line is「谁读的谁负责」: a caller that parsed the file itself and
    hands a dict is not second-guessed — it may be a deck this repository
    just wrote, or one being deliberately inspected.  Such a caller has
    :func:`fylite.io.geqdsk.require_convention` and
    :func:`~fylite.io.geqdsk.to_convention` to hand.  ``check_convention``
    forces either way; ``False`` is how you convert a file you know is odd.

    ★Cost: one Delta* application on the file's own grid — **measured 9 ms**
    for a 129x129 EAST reconstruction, 5 ms for the 65x65 fixture, paid once
    per file opened.
    """
    if not isinstance(g, dict):
        source = source or Path(g).name
        opened = Path(g)
        g = geqdsk.read_geqdsk(opened)
        if check_convention is None:
            check_convention = True
    measured = None
    if check_convention:
        #: raises by name, naming what was measured instead — deliberately
        #: without transforming: which factor a mismatch needs depends on
        #: the quantity the caller is about to use (T-C22 〔三〕)
        measured = geqdsk.require_convention(g, profile_gauge=convention)
    r, z, _ = geqdsk.grid(g)
    n = len(np.asarray(g["fpol"], float))
    psi1d = (float(g["simag"])
             + np.linspace(0.0, 1.0, n) * (float(g["sibry"]) - float(g["simag"])))
    arr = lambda k: np.asarray(g.get(k, []), float)   # noqa: E731
    #: ★★deck key → the DECLARED slot it lands in.  Every path this
    #: function writes now comes from the kernel's own table
    #: (``rust/fylite/src/fyo.rs``), so the g-file's names stop here and
    #: the document's names are stated once, for both hosts.
    doc = _doc("fyo:equilibrium",
               "fylite:equilibrium/" + str(source or "unknown"))
    if measured is not None:
        #: ★what was CHECKED, not merely that something was.  A document
        #: saying「约定已核」without the numbers is a claim nobody can audit.
        doc["fylite:psi_convention"] = {
            "measured": measured["profile_gauge"],
            "gs_residual": measured["residual"],
            "margin": measured["margin"],
            "region": measured["mask"],
            "psi_axis": measured["psi_axis"],
        }
    for key, value in (
            ("ip", float(g["current"])),
            ("axis_r", float(g["rmaxis"])),
            ("axis_z", float(g["zmaxis"])),
            ("psi_axis", float(g["simag"])),
            ("psi_boundary", float(g["sibry"])),
            ("r0", float(g["rcentr"])),
            ("b0", float(g["bcentr"])),
            ("psi_1d", psi1d),
            ("f", arr("fpol")),
            ("pressure", arr("pres")),
            ("f_df_dpsi", arr("ffprim")),
            ("dpressure_dpsi", arr("pprime")),
            ("q_1d", arr("qpsi")),
            ("grid_r", np.asarray(r, float)),
            ("grid_z", np.asarray(z, float)),
            #: ★IMAS order: ``psi[dim1, dim2]`` = ``[R, Z]``.  A g-file
            #: writes ``[z, r]``; the document is where that ends, so a
            #: reader of the document never has to know which deck it came
            #: from.  The RANK the table declares for this slot (``2d``) is
            #: what a reader checks that against.
            ("psi_2d", np.asarray(g["psirz"], float)
                         .reshape(len(z), len(r)).T.copy()),
            ("boundary_r", arr("rbbbs")),
            ("boundary_z", arr("zbbbs")),
            #: ★The limiter travels WITH the equilibrium.  It is the wall's,
            #: not the equilibrium's, in the DD — but a document without it
            #: makes every surface trace fall back to the grid box, and the
            #: outermost shell then bounds a different plasma (measured: the
            #: last beam shell moved 30 %).
            ("limiter_r", arr("rlim")),
            ("limiter_z", arr("zlim"))):
        put(doc, "EQUILIBRIUM", key, value)
    p2 = _slice(doc)["profiles_2d"][0]
    p2["@type"] = "fyo:equilibrium_profiles_2d"
    p2["grid_type"] = {"index": 1, "name": "rectangular"}
    return doc


def _slice(doc: dict) -> dict:
    ts = doc.get("time_slice")
    if not isinstance(ts, list) or not ts:
        raise ValueError("fyo:equilibrium document has no time_slice")
    return ts[0]


def as_equilibrium(eq) -> dict:
    """The ``fyo:equilibrium`` document — or the IO door into one.

    ★★The document is the package's equilibrium record; a g-file is one
    way it arrives.  Every model entry that takes an equilibrium takes it
    through here, so a g-file path or a :func:`fylite.io.geqdsk.read_geqdsk`
    dict is still
    accepted at the door and is converted ON THE WAY IN — nothing inside
    reads a g-file key.  Before this, ``_as_geqdsk`` did the reverse: the
    document was flattened BACK into g-file keys because the models were
    written against the deck, and the deck's names and its ``[z, r]``
    storage order leaked into every consumer.
    """
    if isinstance(eq, dict) and (eq.get("@type") == "fyo:equilibrium"
                                 or "time_slice" in eq):
        return eq
    if _is_reconstruction(eq):
        return reconstruction(eq)
    return equilibrium(eq)


#: The keys a reconstruction result carries that a g-file dict does not, and
#: which :func:`equilibrium` needs under other names.
_RECON_KEYS = ("psin_1d", "rgrid", "zgrid", "psi_bry")


def _is_reconstruction(obj) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in _RECON_KEYS)


def reconstruction(res: dict, *, source: str | None = None) -> dict:
    """An in-memory reconstruction result → an ``fyo:equilibrium`` document.

    ★★The bridge that did not exist.  ``recon_rs.reconstruct`` produced a psi
    map, the global quantities and — since 2026-08-21 — the 1-D profiles and
    the boundary, all in memory and all in float64; the model layer takes
    ``fyo:equilibrium`` documents.  Between the two there was nothing, so the
    only way to get a reconstruction into a model was to write a g-file and
    read it back, which `loop.py` did twice an iteration through a fixed
    text format that carries fewer digits than the numbers going into it.

    ★The result's keys are EFIT's (``psi_bry``, ``rmaxis``, ``ffprim``) —
    that is a separate debt and this function is where it stops travelling:
    everything downstream of here reads DD names.
    """
    rg = np.asarray(res["rgrid"], float)
    zg = np.asarray(res["zgrid"], float)
    psi = np.asarray(res["psi"], float)
    if psi.shape != (rg.size, zg.size):
        raise ValueError(f"reconstruction psi has shape {psi.shape}, expected "
                         f"{(rg.size, zg.size)} ([R, Z])")
    doc = _doc("fyo:equilibrium",
               "fylite:equilibrium/" + str(source or "reconstruction"))
    arr = lambda k: np.asarray(res[k], float)      # noqa: E731
    for key, value in (
            ("ip", float(res["ip"])),
            ("axis_r", float(res["rmaxis"])),
            ("axis_z", float(res["zmaxis"])),
            ("psi_axis", float(res["psi_axis"])),
            ("psi_boundary", float(res["psi_bry"])),
            ("r0", float(res["rcentr"])),
            ("b0", float(res["bcentr"])),
            ("psi_1d", float(res["psi_axis"])
                       + np.asarray(res["psin_1d"], float)
                       * (float(res["psi_bry"]) - float(res["psi_axis"]))),
            ("f", arr("fpol")),
            ("pressure", arr("pres")),
            ("f_df_dpsi", arr("ffprim")),
            ("dpressure_dpsi", arr("pprime")),
            ("q_1d", arr("qpsi")),
            ("grid_r", rg),
            ("grid_z", zg),
            #: ★already ``[R, Z]``: the solve works in the kernel's order,
            #: so unlike the g-file door there is no transpose here and
            #: never was one to get wrong.
            ("psi_2d", np.ascontiguousarray(psi)),
            ("boundary_r", arr("rbbbs")),
            ("boundary_z", arr("zbbbs")),
            ("limiter_r", arr("rlim")),
            ("limiter_z", arr("zlim"))):
        put(doc, "EQUILIBRIUM", key, value)
    p2 = _slice(doc)["profiles_2d"][0]
    p2["@type"] = "fyo:equilibrium_profiles_2d"
    p2["grid_type"] = {"index": 1, "name": "rectangular"}
    return doc


def as_geqdsk(eq, *, header: str | None = None) -> dict:
    """An equilibrium → a **g-file dict** (:func:`fylite.io.geqdsk.read_geqdsk`'s
    shape), ready for :func:`fylite.io.geqdsk.write_geqdsk`.

    Takes whatever :func:`as_equilibrium` takes — a document, an in-memory
    reconstruction result, a g-file path or dict — so a caller with a result
    in hand can deliver a deck without knowing which of those it holds.

    ★★This is the inverse of :func:`equilibrium`, and it is deliberately the
    ONLY one.  A doc→deck flattening used to exist as a private helper and was
    removed because the models were reading g-file keys through it, which let
    the deck's names and its ``[z, r]`` storage order leak back into every
    consumer.  Nothing inside the package calls this: it is an EXPORT, the
    write half of ``FR-DATA-002``'s round trip, and the transpose below is
    where the deck's storage order begins and ends.

    ★A conversion, not a computation: a profile whose length disagrees with
    the grid RAISES rather than being resampled onto it.  Resampling here
    would put a numerical choice inside a format converter, and the caller
    who wanted one would never see that it happened.
    """
    doc = as_equilibrium(eq)
    slot = lambda k, d=_MISSING: get(doc, "EQUILIBRIUM", k, d)   # noqa: E731
    r = np.asarray(slot("grid_r"), float)
    z = np.asarray(slot("grid_z"), float)
    nw, nh = int(r.size), int(z.size)
    psi2d = np.asarray(slot("psi_2d"), float)
    if psi2d.shape != (nw, nh):
        raise ValueError(f"psi_2d has shape {psi2d.shape}, expected "
                         f"{(nw, nh)} ([R, Z]) for this grid")
    deck = {}
    for name, key in (("fpol", "f"), ("pres", "pressure"),
                      ("ffprim", "f_df_dpsi"), ("pprime", "dpressure_dpsi"),
                      ("qpsi", "q_1d")):
        v = np.asarray(slot(key), float)
        if v.size != nw:
            raise ValueError(
                f"{key} has {v.size} points and the deck's radial grid has "
                f"nw={nw}; a g-file carries both on ONE grid. Resample before "
                "writing — this converter will not choose for you.")
        deck[name] = v
    bnd_r = np.asarray(slot("boundary_r", []), float)
    bnd_z = np.asarray(slot("boundary_z", []), float)
    lim_r = np.asarray(slot("limiter_r", []), float)
    lim_z = np.asarray(slot("limiter_z", []), float)
    return {
        "header": header or f"fylite {doc.get('@id', 'equilibrium')}",
        "nw": nw, "nh": nh,
        "rdim": float(r[-1] - r[0]), "zdim": float(z[-1] - z[0]),
        "rleft": float(r[0]), "zmid": float(0.5 * (z[0] + z[-1])),
        "rcentr": float(slot("r0")), "bcentr": float(slot("b0")),
        "current": float(slot("ip")),
        "rmaxis": float(slot("axis_r")), "zmaxis": float(slot("axis_z")),
        "simag": float(slot("psi_axis")), "sibry": float(slot("psi_boundary")),
        #: ★the document stores ``psi[R, Z]``; the deck stores ``[z, r]``
        #: flattened with R fastest.  One transpose, in one place.
        "psirz": psi2d.T.ravel(),
        "nbbbs": int(bnd_r.size), "rbbbs": bnd_r, "zbbbs": bnd_z,
        "limitr": int(lim_r.size), "rlim": lim_r, "zlim": lim_z,
        **deck,
    }


def axis_of(doc: dict):
    """``(R, Z)`` of the magnetic axis [m]."""
    return (float(get(doc, "EQUILIBRIUM", "axis_r")),
            float(get(doc, "EQUILIBRIUM", "axis_z")))


def psi_range_of(doc: dict):
    """``(psi_axis, psi_boundary)`` [Wb/rad]."""
    return (float(get(doc, "EQUILIBRIUM", "psi_axis")),
            float(get(doc, "EQUILIBRIUM", "psi_boundary")))


def field_of(doc: dict):
    """``(R0, B0)`` of ``vacuum_toroidal_field`` — B0 SIGNED, as the deck
    had it; a consumer that wants the magnitude says so."""
    return (float(get(doc, "EQUILIBRIUM", "r0")),
            float(get(doc, "EQUILIBRIUM", "b0")))


def ip_of(doc: dict) -> float:
    return float(get(doc, "EQUILIBRIUM", "ip", 0.0))


def profile_of(doc: dict, name: str) -> np.ndarray:
    """A ``profiles_1d`` array (``q``, ``f``, ``pressure``, ``psi``, …) —
    on the uniform ψ_N grid the deck's tables are written on."""
    return np.asarray(_slice(doc)["profiles_1d"][name], float)


def boundary_of(doc: dict):
    """``(r, z)`` of the boundary outline — empty arrays when none."""
    return (np.asarray(get(doc, "EQUILIBRIUM", "boundary_r", []), float),
            np.asarray(get(doc, "EQUILIBRIUM", "boundary_z", []), float))


def limiter_of(doc: dict):
    """``(r, z)`` of the limiter that travels with the equilibrium — empty
    when none; what empty MEANS is the kernel's rule (the grid)."""
    return (np.asarray(get(doc, "EQUILIBRIUM", "limiter_r", []), float),
            np.asarray(get(doc, "EQUILIBRIUM", "limiter_z", []), float))


def psi_map_of(doc: dict):
    """``(grid, ψ[R, Z])`` — the RAW poloidal flux map [Wb/rad].

    ★Straight from ``profiles_2d``: the document stores ``psi[R, Z]`` (IMAS
    order), which IS the kernel's order, so no transpose happens here or
    anywhere downstream of a document.  A g-file writes ``[z, r]`` and
    :func:`equilibrium` is where that ends.

    ★Its own face rather than a branch of :func:`flux_map_of`, because two
    consumers want the unnormalised map — the rigid-filament set, whose
    kernel entry takes ψ with ``psi_axis``/``psi_bnd`` beside it, and the
    app-session reader.  Both used to reach into ``profiles_2d[0]``
    themselves, which is how the document's internals became four modules'
    business.
    """
    r = np.asarray(get(doc, "EQUILIBRIUM", "grid_r"), float)
    z = np.asarray(get(doc, "EQUILIBRIUM", "grid_z"), float)
    psi = np.asarray(get(doc, "EQUILIBRIUM", "psi_2d"), float)
    if psi.shape != (r.size, z.size):
        raise ValueError(f"profiles_2d psi has shape {psi.shape}, expected "
                         f"{(r.size, z.size)} ([R, Z])")
    return kernel.grid_of(r, z), np.ascontiguousarray(psi)


def flux_map_of(doc: dict):
    """``(grid, ψ_N in kernel index order, dψ)`` for this document.

    Raises on a flat ψ: there is no normalisation then, and a floor would
    hand every consumer a plasma filling the box.
    """
    grid, psi = psi_map_of(doc)
    psi_axis, psi_bnd = psi_range_of(doc)
    dpsi = psi_bnd - psi_axis
    if dpsi == 0.0:
        raise ValueError("flat psi (psi_boundary == psi_axis) — no flux map")
    return grid, np.ascontiguousarray((psi - psi_axis) / dpsi), dpsi


def grid_of(doc: dict) -> kernel.Grid:
    """The kernel grid this document's ψ map lives on."""
    return flux_map_of(doc)[0]


# --------------------------------------------------------------------------- #
# The ladder: one equilibrium, traced once                                    #
# --------------------------------------------------------------------------- #
# ★This used to be ``fylite.metrics``.  The tracing, the line integrals and
# the ladder are the kernel's (``rust/fylite/src/surfaces.rs``, reached
# through ``code/ladder`` since T-4 第二十六刀); what is here reads the
# ``fyo:equilibrium`` document and hands the kernel its arguments — which is
# exactly this module's remit, so a second module for it was a second name
# for the same job, stitched to this one by a lazy import to dodge the cycle.
# The history that module carried, kept because it is still load-bearing:
#
# * It once held a second implementation, on contourpy contours with a scipy
#   spline for |∇ψ|; the two were measured against each other before that
#   one was removed (V and V′ to 0.7 %, ``gm3``/``gm2`` to 1.1 %, ``gm7`` to
#   0.8 %, both within ±1 % of the independent grid quadrature below, which
#   is the tolerance this geometry supports at all).
# * ★★One trace, held as an object.  Before :class:`Ladder`, the functions
#   were the only door and every call was a full trace: the closure hook
#   built its surface states on every outer step, three traces (~30 ms on a
#   65×65 map) per step of a march that takes up to five hundred — for an
#   equilibrium that never changed — and the three were three DIFFERENT
#   level sets, so the "same surfaces" promise the kernel's single call
#   makes was being unmade one layer up.
# * Second computation path (non-negotiable for geometry): this repo has
#   paid for silently-transposed masks and mis-scaled flux labels before, so
#   :func:`direct_integrals` computes V(ψ_N) and Φ(ψ_N) a second, independent
#   way — 2-D quadrature over the grid cells inside the surface — and the
#   tests hold the two paths together.  ★It earned its keep again during the
#   move into the kernel: the first kernel call passed ψ_N in the wrong
#   index order, and this path is what said so.

#: The default transport ladder: 41 surfaces on ``[0.02, edge]``.  The axis
#: point is not on it (the contour degenerates there); a transport grid
#: carries its own axis node (:func:`fylite.kernel.with_axis_node`).
TRANSPORT_LADDER = (0.02, 41)
#: The default standalone Miller ladder: 24 surfaces on ``[0.1, edge]`` —
#: the near-axis shape derivatives are the first thing a coarse map loses.
MILLER_LADDER = (0.1, 24)


def _setup(eq):
    """equilibrium → (document, kernel grid, ψ_N in the kernel's index
    order, dψ).

    ★The document is the record (:func:`as_equilibrium`); a
    g-file path or dict is converted at this door and never read past it.
    Both the normalisation and the index order are the document's: it
    stores ``psi[R, Z]``, which is the kernel's order, so the transpose
    that three modules once each carried with its own ★comment does not
    exist downstream of a document at all.
    """
    doc = as_equilibrium(eq)
    try:
        grid, psin, dpsi = flux_map_of(doc)
    except ValueError as exc:
        raise ValueError(f"transport metrics: {exc}") from exc
    return doc, grid, psin, dpsi


def _levels(psin, default, n_surfaces, edge):
    if psin is not None:
        return np.asarray(psin, float)
    lo, n = default
    return np.linspace(lo, edge, n_surfaces if n_surfaces is not None else n)


def a_minor(eq) -> float:
    """The boundary's minor radius [m] from the equilibrium's own outline.

    ★The kernel's shape metric, not a local ``(R_max - R_min)/2``.  There is
    one definition of "minor radius" in this package and every consumer of
    the ladder reads it from the same place; a second one here would be a
    different plasma size in the same result dict.
    """
    rb, zb = boundary_of(as_equilibrium(eq))
    if rb.size < 3 or zb.size != rb.size:
        return float("nan")
    #: ★T-4 第二十一刀 (2026-09-06): through `code/shape` — the same
    #: `surfaces::shape_metrics`, answered as the `a` fact
    from .io import fydoc
    rec = fydoc.complete("code/shape", {"settings": {}, "inputs": {"equilibrium": {
        "time_slice": {"boundary": {"outline": {"r": np.asarray(rb, float), "z": np.asarray(zb, float)}}}}}})
    return float(rec["facts"]["a"]["value"])


#: The Miller row of a traced surface, in the order the kernel's ladder wrote
#: it (`fyo.derive`'s ``fylite:miller`` set keeps this order); and the metric
#: row beside it.  ★Names, not a wire layout: `code/ladder` answers both on the
#: LADDER rows by name since T-4 第二十六刀 (2026-09-06).
MILLER_KEYS = ("psin", "r", "rmaj", "zmag", "q", "shear", "shift", "kappa",
               "s_kappa", "delta", "s_delta", "zeta", "s_zeta", "s_zmag")
METRIC_KEYS = ("psin", "rho", "volume", "vprime", "gm3", "gm7", "gm2", "q",
               "fpol", "dv_dpsin")
#: Miller key -> the LADDER row it is answered on
_MILLER_ROWS = {"psin": "psin", "r": "rmin", "rmaj": "rmaj", "zmag": "zmag", "q": "q", "shear": "shear",
                "shift": "shift", "kappa": "kappa", "s_kappa": "s_kappa", "delta": "delta",
                "s_delta": "s_delta", "zeta": "zeta", "s_zeta": "s_zeta", "s_zmag": "dzmag"}


def equilibrium_ladder(doc, grid, psin2d, dpsi, levels) -> dict:
    """The ONE kernel call the metric ladder and the Miller ladder share.

    ★★They used to be two kernel entries that traced the same ψ map at the
    same levels and each kept its own ladder — and they were reached with
    different DEFAULT level sets (41 surfaces on [0.02, 0.95] against 24 on
    [0.1, 0.95]), so a caller holding both a metric and a shape held them for
    surfaces that are not the same surfaces.  One trace, one acceptance (a
    level is on the ladder only if it yields BOTH an integral and a shape),
    two views.  Measured bit-identical to the two entries it replaces on the
    synthetic deck and on ``g063982.04800``, at both default ladders.

    ★The limiter goes in as the document has it, empty included: "no
    limiter means the grid is the limiter" is the kernel's rule
    (``surfaces::trace``), where it used to be a four-point box this module
    built — and ``nbi.py`` borrowed through a private name.
    """
    #: ★T-4 第二十六刀 (2026-09-06): BY THE KERNEL, whole — `code/ladder` is
    #: `trace_document_ladder` on its own: the document's map, axis, limiter,
    #: q and F tables and boundary read there, the flux gauge honoured, the
    #: levels bound under `fylite:ladder_levels`, the metrics and the Miller
    #: shape answered on the LADDER rows.  `grid` / `psin2d` / `dpsi` are the
    #: caller's view of the same document and are not sent: the door forms
    #: them itself, by the same rules (bit for bit — the kernel repository's
    #: `test_ladder_code.py`).
    from .io import fydoc
    #: a shallow copy carries the request beside the document's own sections
    plan_doc = put(dict(doc), "EQUILIBRIUM", "ladder_levels", np.asarray(levels, float))
    rec = fydoc.complete("code/ladder", {"settings": {"n_theta": 181.0},
                                         "inputs": {"equilibrium": plan_doc}})
    lad = rec["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
    col = lambda key: np.asarray(lad[PROFILE_NAMES[key]]["data"], float)  # noqa: E731
    n = int(rec["dims"]["n"])
    cols = {k: col(v) for k, v in _MILLER_ROWS.items()}
    return {"metrics": {k: col(k) for k in METRIC_KEYS},
            "miller": [{k: float(cols[k][i]) for k in MILLER_KEYS} for i in range(n)]}


class Ladder:
    """One g-file, traced once: the transport metrics and the Miller shapes
    of the SAME surfaces, and the scalars every consumer reads beside them.

    ``eq`` is an ``fyo:equilibrium`` document (or, at the door, a g-file
    path or dict — :func:`as_equilibrium`); ``levels`` the ψ_N
    surfaces to trace (default :data:`TRANSPORT_LADDER` on ``[0.02, edge]``).  A level is on
    the ladder only if the kernel could both integrate and shape it, so
    ``psin`` may be shorter than ``levels`` — :meth:`index_of` says which
    survived.

    Attributes: ``psin, rho, volume, vprime, gm3, gm7, gm2, q, fpol,
    dv_dpsin`` (arrays, one per surface — the kernel's
    :data:`METRIC_KEYS`), ``miller`` (one dict per surface,
    :data:`MILLER_KEYS`), ``psi`` [Wb/rad], ``dpsi``, ``b0``
    [T], ``a_minor`` [m], ``rho_b`` (ρ at the outermost traced surface —
    NOT the separatrix when the ladder stops short of it), ``b0_signed``
    (as the deck had it) and ``eq`` (the document it came from).
    """

    def __init__(self, eq, levels=None, *, n_surfaces: int | None = None,
                 edge: float = 0.95):
        self.eq, self.grid, self.psin2d, self.dpsi = _setup(eq)
        self.levels = _levels(levels, TRANSPORT_LADDER, n_surfaces, edge)
        out = equilibrium_ladder(self.eq, self.grid, self.psin2d, self.dpsi,
                                 self.levels)
        self.metrics = out["metrics"]
        self.miller = out["miller"]
        for k in METRIC_KEYS:
            setattr(self, k, self.metrics[k])
        self.psi = psi_range_of(self.eq)[0] + self.psin * self.dpsi
        self.b0_signed = field_of(self.eq)[1]
        self.b0 = abs(self.b0_signed)
        self.a_minor = a_minor(self.eq)
        self.rho_b = float(self.rho[-1])

    # -- construction for a consumer that names its surfaces ---------------

    @classmethod
    def with_surfaces(cls, eq, psin, *, n_surfaces: int | None = None,
                      edge: float = 0.95) -> "Ladder":
        """A dense transport ladder that ALSO carries the surfaces ``psin``
        — one trace over the union, so the local quantities at ``psin``
        (Miller shape, ``B_unit``, ρ) and the dense maps they are
        normalised against are read off the same surfaces, with no
        interpolation between two ladders.

        ``eq`` may already be a ``Ladder``; it is returned as is when it
        carries every requested surface and refused when it does not —
        silently tracing a second ladder is the thing this class exists to
        stop.
        """
        psin = np.atleast_1d(np.asarray(psin, float))
        if isinstance(eq, cls):
            eq.index_of(psin)
            return eq
        dense = _levels(None, TRANSPORT_LADDER, n_surfaces, edge)
        levels = np.union1d(dense, psin)
        lad = cls(eq, levels)
        lad.index_of(psin)
        return lad

    def index_of(self, psin) -> np.ndarray:
        """Row indices of the surfaces ``psin`` — exact matches, because a
        level the kernel keeps comes back as the float that went in.
        Raises when one was lost in tracing (or never asked for): the
        caller must refine, not interpolate."""
        psin = np.atleast_1d(np.asarray(psin, float))
        hits = [np.flatnonzero(self.psin == v) for v in psin]
        lost = [float(v) for v, h in zip(psin, hits) if h.size == 0]
        if lost:
            raise ValueError(f"surfaces {lost} are not on the ladder (lost "
                             f"in tracing, or not requested); refine psin")
        return np.array([int(h[0]) for h in hits])

    # -- views ---------------------------------------------------------------

    def transport_metrics(self) -> dict:
        """The dict :func:`transport_metrics` returns — arrays keyed
        ``psin, psi, rho, volume, vprime, gm3, gm7, gm2, fpol, q, dv_dpsin``
        plus scalars ``rho_b, b0, a_minor``.

        ★A TRANSPORT ladder of four surfaces is an error, not a short
        answer — the policy is enforced here, where it is meant, and not in
        the kernel, where it also refused a four-surface MILLER ladder (an
        ordinary request from a local solve).
        """
        if self.psin.size < 5:
            raise ValueError(f"transport metrics: only {self.psin.size} of "
                             f"{self.levels.size} surfaces survived tracing")
        out = {k: v for k, v in self.metrics.items()}
        out["psi"] = self.psi
        out["rho_b"] = self.rho_b
        out["b0"] = self.b0
        out["a_minor"] = self.a_minor
        return out

    def miller_geometry(self, psin=None) -> list[dict]:
        """The Miller rows — all of them, or those at the surfaces ``psin``
        (exact matches through :meth:`index_of`)."""
        if psin is None:
            return list(self.miller)
        return [self.miller[i] for i in self.index_of(psin)]

    def __len__(self) -> int:
        return int(self.psin.size)

    def __repr__(self) -> str:
        return (f"Ladder({len(self)} surfaces on [{self.psin[0]:.3g}, "
                f"{self.psin[-1]:.3g}], a={self.a_minor:.3g} m, "
                f"b0={self.b0:.3g} T)")


#: Elementary permeability [H/m] — the one constant this module needs.
MU0 = 4e-7 * np.pi


def transport_metrics(eq, *, psin=None, n_surfaces: int = 41,
                      edge: float = 0.95) -> dict:
    """Transport metrics on a ψ_N ladder (default 41 surfaces on [0.02, edge]).

    ``eq`` is an ``fyo:equilibrium`` document (or a g-file path / dict at
    the door).  Returns arrays keyed ``psin, psi
    [Wb/rad], rho [m], volume [m³], vprime [m²], gm3, gm7, gm2, fpol, q``
    plus scalars ``rho_b`` (ρ at the outermost extracted surface — NOT the
    separatrix when ``edge < 1``), ``b0`` [T] and ``a_minor`` [m].

    The axis point is not on the ladder (the contour degenerates there); a
    transport grid should carry its own axis node with V′→0 handled by the
    FVM's zero-flux face, or start where this ladder does.

    A view of a fresh :class:`Ladder`: a caller that also needs the Miller
    rows, or needs these metrics more than once, holds the object.
    """
    return Ladder(eq, _levels(psin, TRANSPORT_LADDER, n_surfaces, edge)
                  ).transport_metrics()


#: The 22 extended (MXH) harmonics of a local surface in GEO's order — the
#: columns of ``code/metric``'s ``fylite:mxh_harmonics`` row (cos0..cos6 with
#: their s_, then sin3..sin6 with theirs).  ★An interface fact: the kernel
#: reads the row by position.
GEO_SHAPE_KEYS = (
    "cos0", "s_cos0", "cos1", "s_cos1", "cos2", "s_cos2", "cos3", "s_cos3",
    "cos4", "s_cos4", "cos5", "s_cos5", "cos6", "s_cos6",
    "sin3", "s_sin3", "sin4", "s_sin4", "sin5", "s_sin5", "sin6", "s_sin6",
)

#: ``code/metric``'s answer: the DD-named ladder moments (LADDER keys) and
#: GEO's own normalised scalars beside them (bare fields).
METRIC_LADDER = ("volume", "vprime", "gm3", "gm7", "gm2", "r2")
METRIC_RAW = ("f", "ffprime", "fsa_bp2", "fsa_bt2", "grad_r0", "surf", "bt0", "bp0",
              "thetascale", "bl")


def surface_metric(*, rmin, rmaj, q, shear=0.0, kappa=1.0, delta=0.0, shift=0.0,
                   s_kappa=0.0, s_delta=0.0, zeta=0.0, s_zeta=0.0, zmag=0.0,
                   dzmag=0.0, shape=None, signb: float = 1.0,
                   n_theta: int = 1001) -> dict:
    """Flux-surface moments of a Miller / MXH surface row — BY THE KERNEL
    (``code/metric``, GACODE's GEO through ``geometry::solve``).

    ★T-4 第二十四刀 (2026-09-06): the flat ``geo_surface`` export left the
    interface.  Every host that built a ladder from it packed GEO's fourteen
    positional scalars itself — the mis-packing that invites was what the
    old wiring gate existed to catch.  Here the surfaces go in as the
    LADDER rows fyo already declares (``r_minor`` · ``r_major`` · ``q`` ·
    ``magnetic_shear`` · ``elongation`` · ``triangularity`` · ``shift``) plus
    the MXH rows the DD has no slot for, one node per element; a scalar is
    broadcast to every node.  Scale-covariant exactly as the entry was:
    metres in, ``vprime`` = dV/dr in m² out, ``gm3`` = <|∇r|²>, ``gm7`` =
    <|∇r|>, ``gm2`` = <|∇r|²/R²> (m⁻²), ``r2`` = <R²> (m²), ``volume`` (m³),
    and GEO's normalised ``f, ffprime, fsa_bp2, fsa_bt2, grad_r0, surf, bt0,
    bp0, thetascale, bl`` beside them — every value an array on the row.

    ``shape`` is a dict of :data:`GEO_SHAPE_KEYS` (one surface's harmonics,
    broadcast) or an ``(n, 22)`` array; a misspelled harmonic is refused
    rather than dropped, because a harmonic silently dropped is a different
    surface with no sign that it is one.
    """
    from .io import fydoc
    r = np.atleast_1d(np.asarray(rmin, float))
    n = r.size
    doc: dict = {}
    put(doc, "LADDER", "rmin", r)
    for key, val in (("rmaj", rmaj), ("q", q), ("shear", shear), ("kappa", kappa),
                     ("delta", delta), ("shift", shift), ("s_kappa", s_kappa),
                     ("s_delta", s_delta), ("zeta", zeta), ("s_zeta", s_zeta),
                     ("zmag", zmag), ("dzmag", dzmag)):
        arr = np.asarray(val, float)
        put(doc, "LADDER", key, np.full(n, float(arr)) if arr.ndim == 0 else arr)
    if shape is not None:
        if isinstance(shape, dict):
            unknown = set(shape) - set(GEO_SHAPE_KEYS)
            if unknown:
                raise ValueError(f"unknown shape harmonic(s) {sorted(unknown)}; "
                                 f"expected a subset of {GEO_SHAPE_KEYS}")
            row = np.array([float(shape.get(k, 0.0)) for k in GEO_SHAPE_KEYS])
            coef = np.tile(row, (n, 1))
        else:
            coef = np.asarray(shape, float).reshape(n, 22)
        put(doc, "LADDER", "mxh", coef)
    rec = fydoc.complete("code/metric", {"settings": {"signb": float(signb),
                                                      "n_theta": float(n_theta)},
                                         "inputs": {"equilibrium": doc}})
    #: the record's `time_slice` is a mapping (one slice), not the document's AoS
    lad = rec["fields"]["equilibrium"]["time_slice"]["profiles_1d"]
    out = {k: np.asarray(lad[PROFILE_NAMES[k]]["data"], float) for k in METRIC_LADDER}
    for k in METRIC_RAW:
        out[k] = np.asarray(rec["fields"][k]["data"], float)
    return out


def enclosed_plasma_current(rho, vprime, gm2, psi):
    r"""Toroidal plasma current enclosed by each ladder surface [A].

    .. math::
        I(\rho) = \frac{V' \langle |\nabla\rho|^2/R^2 \rangle}{2\pi\mu_0}
                  \frac{d\psi}{d\rho}

    ``rho`` [m], ``vprime`` [m²], ``gm2`` = ⟨|∇ρ|²/R²⟩ [m⁻²] and ``psi``
    [Wb/rad] are the ladder rows :func:`transport_metrics` returns.

    ★★**The constant is READ OFF THE KERNEL'S OWN OPERATOR, not fitted.**
    ``transport::solve_psi`` carries the current-diffusion channel on the
    metric ``M = V' gm2 / (4 pi^2 F)`` with psi in Wb/rad, and the enclosed
    current is what that metric's flux term integrates to — which fixes
    ``1/(2 pi mu0)``.  Measured on the bundled synthetic g-file (header
    current 700 kA) the candidates land at 6.08x (``1/mu0``), 0.154x
    (``1/(4 pi^2 mu0)``), 38.2x (``2 pi/mu0``) and **0.968x** for the one
    above: the constant is IDENTIFIED, not tuned.

    ★★**And 3.2 % of that does not go away.**  Pushing the ladder's outer
    edge from psi_N = 0.95 to 0.9999 moves the ratio only 0.9664 -> 0.9682,
    so it is NOT current sitting outside the last surface: it is the
    ladder's own quadrature accuracy (this module's own note above: V and
    V' to 0.7 %, ``gm2`` to 1.1 %) plus the finite difference below.
    **A caller using this as a FEEDBACK quantity must control the RATIO to
    its own t=0 reading rather than the absolute value**, or it will drive
    the loop steadily onto an I_p that is 3 % wrong.  Said here because a
    number with a known bias and no warning beside it is exactly the
    failure this docstring exists to prevent.

    ★The derivative is written out rather than taken from
    ``numpy.gradient`` so the browser host can carry the SAME formula
    (second order central on a non-uniform grid, second order one-sided at
    both ends) and the two hosts can be held to each other.
    """
    rho = np.asarray(rho, dtype=float)
    vprime = np.asarray(vprime, dtype=float)
    gm2 = np.asarray(gm2, dtype=float)
    psi = np.asarray(psi, dtype=float)
    if not (rho.shape == vprime.shape == gm2.shape == psi.shape):
        raise ValueError("enclosed_plasma_current: rows differ in length")
    if rho.size < 3:
        raise ValueError("enclosed_plasma_current: need at least 3 surfaces")
    return vprime * gm2 * nonuniform_gradient(psi, rho) / (2.0 * np.pi * MU0)


def nonuniform_gradient(f, x):
    """df/dx: second order central inside, second order one-sided at the ends.

    ★Spelled out rather than delegated: the browser host carries the same
    six lines, and「两个宿主逐位相同」 is only a judgeable claim when both
    are looking at one formula.
    """
    f = np.asarray(f, dtype=float)
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    d = np.empty(n, dtype=float)
    hs = x[1:-1] - x[:-2]
    hd = x[2:] - x[1:-1]
    d[1:-1] = (hs * hs * f[2:] + (hd * hd - hs * hs) * f[1:-1]
               - hd * hd * f[:-2]) / (hs * hd * (hd + hs))
    #: ★★THE ENDS ARE FIRST ORDER, AND THAT IS MEASURED RATHER THAN LAZY.
    #: The second-order one-sided stencil is the textbook choice and it is
    #: NOT resolution-stable on a packed transport ladder: on the bundled
    #: synthetic g-file the last node came out at 0.923 / 0.952 / 0.960 of
    #: the header current at 81 / 201 / 401 surfaces — still creeping —
    #: while every CENTRAL node sat at 0.9676-0.9679 at all three.  A
    #: three-point one-sided formula differences a quantity the contour
    #: extraction is noisiest in exactly where the surfaces are most
    #: crowded, and amplifies it.  First order does not.
    d[0] = (f[1] - f[0]) / (x[1] - x[0])
    d[-1] = (f[-1] - f[-2]) / (x[-1] - x[-2])
    return d


def miller_geometry(eq, *, psin=None, n_surfaces: int = 24,
                    edge: float = 0.95) -> list[dict]:
    """Per-surface local Miller geometry from an equilibrium (the standalone bridge).

    ``eq`` is an ``fyo:equilibrium`` document (or a g-file at the door).  ``psin`` is
    the list of normalized-flux surfaces to extract (default ``n_surfaces``
    evenly on ``[0.1, edge]`` — the axis and the last ~5 % are skipped: the
    near-axis contour degenerates and the separatrix is open).  Returns one
    dict per surface with ``psin, r=rmin/a, rmaj=R0/a, zmag=Z0/a, q, shear,
    shift, kappa, s_kappa, delta, s_delta, zeta(0), s_zeta(0), s_zmag``.

    A view of a fresh :class:`Ladder`, same caveat as :func:`transport_metrics`.
    """
    return Ladder(eq, _levels(psin, MILLER_LADDER, n_surfaces, edge)
                  ).miller_geometry()


def direct_integrals(eq, psin_levels) -> dict:
    """V(ψ_N) and Φ(ψ_N) by 2-D grid quadrature — the independent second path.

    ``V = ∬ 2πR dR dZ`` and ``Φ = ∬ (F/R) dR dZ`` over the cells whose ψ_N
    lies inside each level, restricted to the region enclosed by the g-file's
    boundary outline: outside the last closed surface ψ_N dips back below 1
    (private flux, coils), which a bare threshold would silently include.
    First-order in the cell size — a cross-check with its own error bar, not
    a replacement for the line integrals.
    """
    doc, grid, psin2d, _ = _setup(eq)
    rb, zb = boundary_of(doc)
    bnd = (rb, zb) if rb.size >= 3 else None
    return kernel.direct_integrals(grid, psin2d,
                                   f_table=profile_of(doc, "f"),
                                   boundary=bnd,
                                   levels=np.asarray(psin_levels, float))


def derive(doc: dict, *, psin=None, n_surfaces: int = 41,
           edge: float = 0.95) -> dict:
    """The kernel's surface ladder for an ``fyo:equilibrium`` document,
    returned as an ``fyo:equilibrium`` document.

    One kernel call (``surfaces::equilibrium_ladder``) produces both the
    flux-surface-average transport metrics and the local Miller shapes, so
    the two sections below describe the SAME surfaces — which is exactly
    what two separate ladder calls could not promise.

    Nothing is computed here.  The levels are chosen, the arrays are handed
    over, and what comes back is renamed into the DD.

    ★The ladder is a :class:`Ladder` — the same object the
    closure holds — so the default levels, ``psi`` from ``psin`` and the
    scalars beside the arrays are stated once, there, and not a second
    time in document clothing here.
    """
    lad = Ladder(doc, psin, n_surfaces=n_surfaces, edge=edge)
    p1 = {PROFILE_NAMES[k]: v for k, v in lad.metrics.items()}
    p1["psi"] = lad.psi
    miller = {"@type": "fyo:miller_surface_set",
              **{k: np.array([r[k] for r in lad.miller], float)
                 for k in MILLER_KEYS}}
    out = _doc("fyo:equilibrium", str(doc.get("@id", "fylite:equilibrium"))
               + "/derived")
    #: the field the ladder was traced on travels with it, through the same
    #: two declared slots the source document carries them in
    for key in ("r0", "b0"):
        put(out, "EQUILIBRIUM", key, get(doc, "EQUILIBRIUM", key))
    #: ★the ladder's own rows, under the paths the table declares for them
    slice_ = _dig(out, path_of("LADDER", "psin"), create=True)[0]
    slice_.update(p1)
    gq = _dig(out, path_of("EQUILIBRIUM", "ip"), create=True)[0]
    #: ★two scalars with no DD home and only ONE writer — a private
    #: extension of this function, which is why they are not table rows
    gq["fylite:a_minor"] = float(lad.a_minor)
    gq["fylite:rho_tor_boundary"] = float(lad.rho_b)
    out["fylite:derived_from"] = doc.get("@id")
    out["fylite:miller"] = miller
    return out


# --------------------------------------------------------------------------- #
# The disk face                                                                #
# --------------------------------------------------------------------------- #


def write(doc: dict, path: str | Path) -> Path:
    """Persist an fyo document — ``.h5``/``.hdf5`` → HDF5, else JSON-LD.

    Generic over the document: mappings become groups, numeric arrays
    datasets, ``@``-keys and scalars attributes.  ★A new section in a
    document is not a new branch here — the day this file grows a
    ``if section == ...`` is the day the documents stopped being data.
    """
    p = Path(path)
    if p.suffix.lower() in (".h5", ".hdf5"):
        #: ★★2026-09-04：the HDF5 branch is the ENGINE's (`fylite.io.fydoc`,
        #: fyo layout).  It used to be a walker of its own here over the
        #: h5 library — groups for mappings, datasets for arrays, `@`-keys
        #: as attributes, a `fylite:aos` marker for arrays of structure — a
        #: second spelling of a layout the engine already writes and reads.
        #: What the walker refused (an `object()`), the engine's JSON step
        #: refuses too.
        from .io import fydoc
        fydoc.write(doc, p, format="hdf5", layout="fyo")
        return p
    import json
    p.write_text(json.dumps(_jsonable(doc), indent=1))
    return p


def _jsonable(obj):
    if isinstance(obj, np.ndarray):
        return [_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def read(path: str | Path) -> dict:
    """Read back what :func:`write` wrote (HDF5 or JSON by suffix)."""
    p = Path(path)
    if p.suffix.lower() in (".h5", ".hdf5"):
        #: the engine's reader; arrays come back as nested lists (JSON form),
        #: which is what the JSON branch below hands back as well
        from .io import fydoc
        b = fydoc.read(p)
        try:
            return b.to_dict()
        finally:
            b.close()
    return load_document(p)


def payload(doc: dict) -> dict:
    """The document without its semantic channel (``@context``/``@id``/…)."""
    return strip_semantic(doc)


# --------------------------------------------------------------------------- #
# The MODEL layer's face: documents in, documents out                          #
# --------------------------------------------------------------------------- #
# ★The physics models (`scenario.model.nbi` / `.lh` / `.redl` / `.neo` /
# `.gyrofluid` / `.solver`) speak arrays to the kernel, which is what an ABI
# is for.  What a CALLER hands them, and what it gets back, is a document:
# an `fyo:core_profiles` in, an `fyo:core_sources` out, both in IMAS DD
# names, both writable by `write` without a new branch.  That is the whole
# of "fyo is the interface" — the models did not grow a second numerical
# path, they grew a face that carries its own units and provenance.
# --------------------------------------------------------------------------- #

def core_profiles(psin, *, ne, te, ti=None, zeff=None, ni=None,
                  source: str | None = None) -> dict:
    """Kinetic profiles → an ``fyo:core_profiles`` document.

    ``psin`` is the normalised-flux grid the profiles live on; ``ne`` [m⁻³],
    ``te``/``ti`` [eV].  ★The grid travels WITH the profiles: a profile
    passed without the coordinate it was sampled on is the oldest way to get
    a plausible wrong answer out of this chain.
    """
    doc = _doc("fyo:core_profiles",
               "fylite:core_profiles/" + str(source or "unknown"))
    put(doc, "CORE_PROFILES", "psin", np.asarray(psin, float))
    put(doc, "CORE_PROFILES", "ne", np.asarray(ne, float))
    put(doc, "CORE_PROFILES", "te", np.asarray(te, float))
    if ti is not None:
        put(doc, "CORE_PROFILES", "ti", np.asarray(ti, float))
    if zeff is not None:
        put(doc, "CORE_PROFILES", "zeff",
            np.asarray(zeff, float) if np.ndim(zeff) else float(zeff))
    if ni is not None:
        put(doc, "CORE_PROFILES", "ni", np.asarray(ni, float))
    return doc


def profiles_of(doc: dict) -> dict:
    """An ``fyo:core_profiles`` document → the arrays a model takes."""
    #: ★the reader is the writer's table read backwards — the two cannot
    #: disagree about a path any more, which is the failure this layer has
    #: paid for before (a section written under one spelling and looked for
    #: under another is a document that silently lost it)
    out = {k: np.asarray(get(doc, "CORE_PROFILES", k), float)
           for k in ("psin", "ne", "te")}
    for k in ("ti", "ni"):
        v = get(doc, "CORE_PROFILES", k, None)
        if v is not None:
            out[k] = np.asarray(v, float)
    z = get(doc, "CORE_PROFILES", "zeff", None)
    if z is not None:
        out["zeff"] = float(z) if np.ndim(z) == 0 else np.asarray(z, float)
    return out


def _source_entry(name: str, index: int, psin, *, j_par=None, p_e=None,
                  p_i=None, extras=None, globals_=None) -> dict:
    """One ``core_sources.source`` element, IMAS DD names."""
    entry = {}
    put(entry, "CORE_SOURCES", "psin", np.asarray(psin, float))
    for key, value in (("j_par", j_par), ("p_e", p_e), ("p_i", p_i)):
        if value is not None:
            put(entry, "CORE_SOURCES", key, np.asarray(value, float))
    p1 = entry["profiles_1d"]
    for k, v in (extras or {}).items():
        p1[k] = np.asarray(v, float) if np.ndim(v) else float(v)
    return {"@type": "fyo:core_sources_source",
            #: the DD's own identifier indices: 2 = nbi, 4 = lh,
            #: 13 = bootstrap current
            "identifier": {"name": name, "index": int(index)},
            "profiles_1d": p1,
            "global_quantities": dict(globals_ or {})}


def _sources_doc(id_: str, entries: list, **extra) -> dict:
    return _doc("fyo:core_sources", id_, source=entries, **extra)


def beam_sources(eq: dict, prof: dict, beams, **kw) -> dict:
    """Neutral-beam deposition for a pair of documents → ``fyo:core_sources``.

    ``eq`` an ``fyo:equilibrium`` document, ``prof`` an ``fyo:core_profiles``
    one.  Everything numerical is :func:`fylite.scenario.model.nbi.deposit`'s
    (and through it the kernel's); what is added here is the DD spelling and
    the provenance.
    """
    from .scenario.model import nbi
    #: ★lifted at the door, once — see `neoclassical_source`.  Reading
    #: `eq.get("@id")` off the RAW argument made the g-file spelling every
    #: docstring here promises raise `AttributeError` after the work was done.
    doc = as_equilibrium(eq)
    pr = profiles_of(prof)
    out = nbi.deposit(doc, pr["ne"], pr["te"], beams,
                      psin_prof=pr["psin"], ti=pr.get("ti"),
                      zeff=pr.get("zeff", 1.0), **kw)
    entry = _source_entry(
        "nbi", 2, out["psin"], j_par=out["j_nbi"], p_e=out["p_e"],
        p_i=out["p_i"],
        extras={"fylite:pressure_fast": out["p_fast"],
                "fylite:power_density": out["p_dep"],
                "fylite:pitch": out["pitch"],
                "fylite:dvolume": out["dvolume"]},
        globals_={"current": out["i_nbi"], "power": out["p_absorbed"],
                  "fylite:power_injected": out["p_injected"],
                  "fylite:shinethrough": out["shinethrough"],
                  "fylite:orbit_loss_fraction": out["orbit_loss_fraction"],
                  "fylite:fast_energy": out["fast_energy"]})
    return _sources_doc(str(doc.get("@id", "fylite:equilibrium")) + "/nbi",
                        [entry], **{"fylite:derived_from": doc.get("@id"),
                                    "fylite:profiles_from": prof.get("@id")})


def wave_sources(eq: dict, prof: dict, launchers, *, eta_cd, **kw) -> dict:
    """Lower-hybrid deposition for a pair of documents → ``fyo:core_sources``.

    Returns a document with an EMPTY source list when nothing resonated or
    no launcher had power — ★a result, not a failure, and one a persisted
    document should be able to state.
    """
    from .scenario.model import lh
    #: ★lifted at the door, once — see `neoclassical_source`.
    doc = as_equilibrium(eq)
    pr = profiles_of(prof)
    out = lh.deposit(doc, pr["ne"], pr["te"], launchers,
                     eta_cd=eta_cd, psin_prof=pr["psin"], **kw)
    entries = []
    if out is not None:
        entries.append(_source_entry(
            "lh", 4, out["psin"], j_par=out["j_lh"],
            p_e=out["p_dep"],
            extras={"fylite:j_sigma": out["sigma_j"],
                    "fylite:n_parallel_accessible": out["n_parallel_accessible"],
                    "fylite:dvolume": out["dvolume"]},
            globals_={"current": out["i_lh"], "power": out["p_absorbed"],
                      "fylite:deposited": bool(out["deposited"]),
                      "fylite:eta_cd": out["eta_cd"]}))
    return _sources_doc(str(doc.get("@id", "fylite:equilibrium")) + "/lh",
                        entries, **{"fylite:derived_from": doc.get("@id"),
                                    "fylite:profiles_from": prof.get("@id")})


def merge_sources(*docs: dict) -> dict:
    """Several ``fyo:core_sources`` documents into one.

    ★Concatenation, not addition: a caller that wants the total current adds
    the entries it means to add, on a grid it chose.  Summing here would
    hide that two sources were computed on different ladders.
    """
    entries: list = []
    for d in docs:
        if d.get("@type") != "fyo:core_sources":
            raise ValueError(f"merge_sources: {d.get('@type')!r} is not "
                             f"an fyo:core_sources document")
        entries.extend(d.get("source", []))
    return _sources_doc("fylite:core_sources/merged", entries)


#: What the two retired ``current_source`` backends spell as a ``key``.
#: ★A refusal table, not an alias table: it maps the old name to the call
#: that replaces it and is used to say so, because quietly accepting both
#: is what gave this signature two spellings of one choice.
_RETIRED_SOLVERS = {"sauter": "jpar_sauter", "sauter2021": "jpar_sauter_2021"}


# --------------------------------------------------------------------------- #
# Measurement documents: the EAST channel contract as a declarative table      #
# --------------------------------------------------------------------------- #
# ★This used to be ``fylite.imas_io``.  It is the measurement analogue of
# ``equilibrium`` / ``as_equilibrium``: :func:`measurements` lifts the flat
# measurement dict into an fyo-shaped document, :func:`as_measurements` reads
# one (path, plain dict or JSON-LD normal form) back into the flat dict.
# Both directions are driven by ONE table — ``device.EAST_CHANNEL_MAP`` —
# through the generic applier in :mod:`fylite.engine`
# (``apply_channel_map`` / ``invert_channel_map``), so the forward parse and
# the inverse cannot drift apart.  The est2 reduction that shared the old
# file is a data SOURCE and lives in :mod:`fylite.io.est2` now.
#
# Input contract (dict, JSON or YAML file):
#
#     magnetics:
#       flux_loop:                # EXACTLY 35, efit_east SILOPT channel order
#         - flux: {data: [...], time: [...]}     # or scalar data
#       b_field_pol_probe:        # EXACTLY 76, efit_east EXPMPI channel order
#         - field: {data: [...], time: [...]}
#       ip:                       # optional; else top-level scalar `ip`
#         - {data: [...], time: [...]}
#     pf_active:
#       coil:                     # EXACTLY 12, EFIT coil order
#         - current: {data: [...], time: [...]}  #   PF1 PF3 PF5 PF7 PF9 PF11
#                                                #   PF2 PF4 PF6 PF8 PF10 PF12
#     tf:
#       b_field_tor_vacuum_r: {data: [...], time: [...]}   # R*Bt [T.m]
#     # OR top-level scalars:
#     ip: <A>
#     btor: <T at RCENTR=1.75 m>
#     coil_current_units: "A" | "A.turns"        # default "A" (IMAS semantics)
#
# Every ``{data, time}`` signal may instead be a bare scalar (or 1-element
# array); time arrays are linearly interpolated to the requested time.
#
# Units: flux loops as efit_east SILOPT (passed through to ``COILS``); probes
# in tesla, EXPMPI convention (to ``EXPMP2``); coil currents default "A"
# (IMAS conductor current) multiplied by TURNFC from the device deck into
# the A-turns ``BRSP`` EFIT expects — ``coil_current_units: "A.turns"``
# passes them through; ``tf.b_field_tor_vacuum_r`` is R*Bt [T.m] → BTOR =
# value/RCENTR, a top-level ``btor`` is BTOR [T] directly.
#
# The table grammar follows the dict-canonical spirit of SpData ``sp:read``;
# when the three-key expression form is finalized upstream (SP-REPORT-15
# OI-3 / SPD-ADR-104), the table serializes into the ``fylite:east_mdsplus``
# DataArtifact's ``sp:read`` entries mechanically.

class MeasurementInputError(ValueError):
    """A measurement input that does not meet the channel contract (counts,
    orders, units) or a dump that is not there.

    ★Distinct from :class:`fylite.device.MachineDataMissing`, which is about
    the DEVICE deck; this is about the measurements fed against it.

    ★Home is here, with the face whose contract it names — the same move
    :data:`FYO_PREFIX` made.  It used to be defined in :mod:`fylite.io.est2`
    and imported BY this module, so the document layer took its own public
    exception from one of its feeders; :mod:`fylite.io.est2` is a consumer of
    this type, not its owner, and reaches it the way it reaches
    :mod:`fylite.device` — lazily, at the call.
    """


#: The measurement document's ``@context``: the manifest's (``sp`` /
#: ``prov`` / ``fylite``) plus ``fyo``.  ★It and :data:`CONTEXT` now agree on
#: the ``fylite`` IRI; they did not until 2026-08-21, and this line used to
#: say so and leave it.
_MEASUREMENT_CONTEXT = {**_RunManifest.SEMANTIC_CONTEXT, "fyo": FYO_PREFIX}

#: fyo class tags stamped on the payload sections by :func:`measurements`.
#:
#: ★★A-1: these were three literals here and three more in
#: ``app/assets/session.js`` — one contract kept in two places.  They are
#: declared in the kernel now (``@fyo-table MAGNETICS`` / ``PF_ACTIVE`` /
#: ``TF``, slotless: the tag is the shared fact, the payload inside is a
#: device deck's own) and read out of the generated table, so neither host
#: spells the string.
_SECTION_TYPES = {name.lower(): TABLES[name]["type"]
                  for name in ("MAGNETICS", "PF_ACTIVE", "TF")}


def _device():
    """The device module, imported lazily: the channel map lives with the
    deck it is derived from; this module reads it, it does not own it."""
    from . import device
    return device


def _basis_of(n_channels: int) -> str:
    """:func:`fylite.device.probe_basis_of`, re-raised in this module's
    vocabulary.

    ★A probe count that matches no basis is a MEASUREMENT fault, not a
    device-document one: the machine is fine, the file handed to it is not.
    :class:`MeasurementInputError` is documented as "counts, orders, units",
    which is exactly this, so callers keep one exception to catch.
    """
    dev = _device()
    try:
        return dev.probe_basis_of(n_channels)
    except dev.DeviceDocumentError as exc:
        raise MeasurementInputError(str(exc)) from None


def resolve_probe_basis(d: dict, basis: str | None = None) -> str:
    """Which probe basis an IMAS-shaped document is in.

    Three sources, in order: an explicit ``basis`` argument, the document's
    own ``fylite:channel_basis`` declaration, and the length actually
    present.  ★Any two that are both available must AGREE — a document
    declaring ``est2`` while carrying 76 channels is corrupt, and reading it
    as either basis would be a guess.  With none available the device
    module's default stands, and "no probes at all" is reported by the
    channel map, which is where that belongs.
    """
    dev = _device()
    declared = d.get(dev.BASIS_KEY)
    if declared is not None and declared not in dev.probe_bases():
        raise MeasurementInputError(
            f"{dev.BASIS_KEY} says {declared!r}; "
            f"known: {sorted(dev.probe_bases())}")
    mag = d.get("magnetics")
    probes = mag.get("b_field_pol_probe") if isinstance(mag, dict) else None
    observed = _basis_of(len(probes)) if isinstance(probes, list) else None
    for a, b, why in ((basis, declared, f"the caller and {dev.BASIS_KEY}"),
                      (basis, observed, "the caller and the document"),
                      (declared, observed, f"{dev.BASIS_KEY} and the document")):
        if a is not None and b is not None and a != b:
            raise MeasurementInputError(
                f"probe basis disagreement between {why}: {a!r} vs {b!r}")
    return basis or declared or observed or dev.DEFAULT_BASIS


def _measurements_from_dict(d: dict, time_s: float, *,
                            source: str = "dict",
                            basis: str | None = None) -> dict:
    """An already-loaded IMAS-shaped dict → the flat measurement dict.  Every
    door funnels through here, so the channel contract (counts, orders,
    units — ``device.east_channel_map``) is enforced once."""
    resolved = resolve_probe_basis(d, basis)
    out = apply_channel_map(_device().east_channel_map(resolved), d, time_s,
                            error=MeasurementInputError)
    #: ★The basis travels ON the flat dict: a consumer that has to pick a
    #: weight mask, a limiter or a table set needs it, and re-deriving it
    #: from ``len(expmp2)`` at each such site is how one of them ends up
    #: assuming.
    out.update(source=source, time_s=float(time_s), basis=resolved)
    return out


def as_measurements(obj, time_s: float, *, source: str | None = None,
                    basis: str | None = None) -> dict:
    """Measurement document (path, plain dict, or JSON-LD normal-form dict)
    → the flat fylite measurement dict.

    The P-1 (interpret_inputs) hook of the data plane: semantic documents are
    stripped and funnelled through the same channel contract as plain
    IMAS-shaped input; nothing about the physics path changes.
    """
    if isinstance(obj, (str, Path)):
        return as_measurements(load_document(obj), time_s,
                               source=source or f"imas:{obj}", basis=basis)
    if not isinstance(obj, dict):
        raise TypeError(f"expected a path or dict, got {type(obj).__name__}")
    if is_semantic(obj):
        #: ★``strip_semantic`` drops ``@``/``$`` keys; ``fylite:channel_basis``
        #: is neither, so the declaration survives the strip.  That is why
        #: the basis is declared under a prefixed ORDINARY key.
        return _measurements_from_dict(strip_semantic(obj), time_s,
                                       source=source or "semantic:normal-form",
                                       basis=basis)
    return _measurements_from_dict(obj, time_s, source=source or "dict",
                                   basis=basis)


def measurements(meas: dict) -> dict:
    """Lift a flat measurement dict (``plasma``/``btor``/``brsp``/``coils``/
    ``expmp2``) into an fyo-shaped, ``@type``-annotated document — the
    materialization face of the ``fylite:east_mdsplus`` DataArtifact, driven
    by the same ``EAST_CHANNEL_MAP`` as the forward parse.

    Coil currents are emitted in ``A.turns`` (the flat dict's ``brsp`` is
    already ampere-turns), declared via ``coil_current_units`` so the reverse
    path does not re-multiply by TURNFC; ``btor`` is re-expressed as the IMAS
    ``tf.b_field_tor_vacuum_r`` (R*Bt at RCENTR).
    """
    dev = _device()
    #: ★The basis is settled BEFORE anything is written, from the length the
    #: flat dict actually carries; a length belonging to no known basis
    #: raises here rather than producing a document nothing can read.  This
    #: is the half of the round trip that used to be missing — the inverse
    #: wrote whatever it was handed while the forward parse checked one
    #: fixed count.
    basis = (_basis_of(len(meas["expmp2"])) if "expmp2" in meas
             else dev.DEFAULT_BASIS)
    payload = invert_channel_map(dev.east_channel_map(basis), meas)
    for section, tag in _SECTION_TYPES.items():
        if section in payload:
            payload[section]["@type"] = tag
    doc = {
        "@context": dict(_MEASUREMENT_CONTEXT),
        "@id": "fylite:measurements/" + str(meas.get("source", "unknown")),
        "@type": "fylite:MeasurementSet",
        dev.BASIS_KEY: basis,
        **payload,
        "coil_current_units": "A.turns",
    }
    if "time_s" in meas:
        doc["fylite:time_s"] = float(meas["time_s"])
    return doc
