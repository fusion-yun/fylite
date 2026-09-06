"""GACODE's formats — ``input.gacode``, and NEO's own namelist grammar.

``input.gacode`` is the interchange format of the GACODE suite: one file
carrying the flux-surface shape, the kinetic profiles, and the per-channel
power deposition on a common radial grid.  It is what ``profiles_gen`` writes
and what TGYRO/NEO/CGYRO read, so it is also the natural reference for
fylite's own bundle (``oracles/mapping.py`` (the kernel repository's test tree, since T-4 第十五刀)).

The format is a sequence of blocks::

    # <name>[ | <unit>]
    <value>                        scalar
    ...
    # <name> | <unit>
      1  <v1>[ <v2> ...]           profile: leading 1-based index, then one
      2  <v1>[ <v2> ...]           column per species for the ion-resolved
    ...                            fields (ni, ti, vpol, vtor)

Only the parsing lives here — every *derived* quantity (``b_unit``, ``V'``,
``<|grad r|>``, the gyro-Bohm units) is computed in ``oracles/mapping.py`` (the kernel repository's test tree, since T-4 第十五刀),
mirroring upstream's split between ``expro_read`` and ``expro_compute_derived``.

★★NEO's ``neo_dump_local`` namelist replay used to be the module's other
half, on the argument that somebody else's deck grammar is an ``io`` subject.
It is not, once the deck has no live reader: a REPLAY is a fixture, and this
one had no caller in the package at all — every one was a test.  It moved to
``tests/oracles/neo.py`` on 2026-08-21, and with it went the namelist
splitter and the branch constants, which had already been dead in this file
before the move.  What an ``io`` module is for is a format something still
reads, and that is ``input.gacode``.
"""
from __future__ import annotations

from pathlib import Path


import numpy as np

#: Fields that are text, not numbers.
_TEXT = frozenset({"name", "type"})

#: Fields that are single integers.
_INT = frozenset({"nexp", "nion", "shot", "time"})


class GacodeIOError(ValueError):
    """``input.gacode`` could not be parsed."""


def read_input_gacode(path) -> dict:
    """Parse ``input.gacode`` into ``{field: value}``.

    Scalars come back as ``int``/``float``, ``name``/``type`` as lists of
    strings, radial profiles as 1-D arrays of length ``nexp``, and the
    ion-resolved profiles as ``(nion, nexp)`` arrays — the same shape upstream
    uses, so ``ni[0]`` is the first ion.

    Units are upstream's and are **not** converted: lengths in m, ``te``/``ti``
    in keV, densities in 10^19 m^-3, powers in MW/m^3, ``polflux``/``torfluxa``
    in Wb/radian.  ``oracles/mapping.py`` (the kernel repository's test tree, since T-4 第十五刀) documents where each is needed in
    another unit.
    """
    path = Path(path)
    lines = path.read_text().splitlines()

    blocks: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith("#"):
            name = line[1:].split("|")[0].strip()
            if not name:                      # a bare '#' separator line
                continue
            blocks.append((name, []))
        elif blocks and line.strip():
            blocks[-1][1].append(line)

    out: dict = {}
    for name, body in blocks:
        if not body:
            continue
        if name in _TEXT:
            out[name] = body[0].split()
        elif name in _INT:
            out[name] = int(body[0].split()[0])
        elif len(body) == 1 and len(body[0].split()) == 1:
            out[name] = float(body[0])
        else:
            rows = [ln.split() for ln in body]
            # A radial profile carries a leading 1-based row index; a short
            # per-species vector (`mass`, `z`) does not — and putting them on
            # one line makes the two look alike, so require the index column to
            # actually BE 1,2,3,... before stripping it.
            indexed = (len(rows) > 1
                       and all(r[0] == str(i + 1) for i, r in enumerate(rows)))
            if indexed:
                data = np.array([[float(x) for x in r[1:]] for r in rows])
                out[name] = data[:, 0] if data.shape[1] == 1 else data.T
            else:
                flat = [float(x) for r in rows for x in r]
                out[name] = np.array(flat) if len(flat) > 1 else flat[0]

    for required in ("nexp", "nion", "rmin"):
        if required not in out:
            raise GacodeIOError(f"{path}: missing '{required}' block")
    n = out["nexp"]
    if len(np.atleast_1d(out["rmin"])) != n:
        raise GacodeIOError(f"{path}: rmin has {len(out['rmin'])} points, "
                            f"nexp says {n}")
    return out


#: ★``_INT_KEYS`` — the list of deck names that are integers on the Fortran
#: side — used to sit here.  It was never read: nothing in this module ever
#: coerced by it, and the same dead list sat in the sibling module too.
#:
#: The reason it was never needed is worth keeping, because it is the actual
#: invariant: the integer-ness is preserved AT THE SOURCE, not enforced at
#: the deck writer.  `mapping.neo_inputs` builds ``IPCCW``/``BTCCW`` from
#: ``signb``/``signq``, which are Python ints, so they arrive as ints — and
#: that is load-bearing, since the recorded NEO oracle is keyed by a JSON
#: digest of the dict and ``-1`` is not ``-1.0``.  A coercion pass here
#: would be a SECOND mechanism for the same guarantee, and the weaker one:
#: it would repair a float that should never have been made.

#: ★The ``neo_dump_local`` namelist splitter (``_split_index`` /
#: ``_VECTOR_KEYS``) and the ``DKE`` / ``HIRSHMAN_SIGMAR`` branch constants
#: were here.  They went with the replay — and two of them had already been
#: DEAD before it left: nothing in this file called ``_split_index``, in this
#: commit or the one before it.  A helper that survives the thing it helped
#: is how a module keeps growing after its subject stops.

#: ★``neo_run_inputs`` was here, and it left for ``tests/oracles/neo.py``
#: on 2026-08-21.  It replayed a recorded NEO namelist run, and the reason
#: given for keeping it in the package — "a namelist run is a recording by
#: nature" — is the reason it is not package code: a recording is a FIXTURE.
#: Nothing in ``fylite`` called it; every caller was a test.  The port is
#: :func:`fylite.scenario.model.neoclassical.bootstrap`, which takes a species
#: list, because a namelist is the shape of the thing that is gone.
#:
#: What stays here is the ``input.gacode`` READER, which is a live format this
#: package reads — that is what an ``io`` module is for.

#: ★``gyrobohm_factors`` used to sit here as a one-line forward to
#: :func:`fylite.kernel.neo_gyrobohm`.  Its own docstring gave the reason it
#: had to go: the three exponents (1.5, 2.5, 2.0) "may not be written down
#: twice" — and a second NAME for the entry that holds them is the way a
#: second writing-down begins.  Callers use the kernel directly.


# --------------------------------------------------------------------------- #
# Current-source models (K-18 called them "current_source" backends; the
# registry is retired — FYL-SDD-01 DE-LOG-03) — adapters over this module's
# NEO kernel.
# --------------------------------------------------------------------------- #
