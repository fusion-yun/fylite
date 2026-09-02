"""The EAST device document, against fydata's independent A-Box.

★**Why this file exists.**  ``fylite_port``'s copy of this machine says, in its
own header, that it carries the DD groups «以便与 fydata 的 A-Box 逐道对照（该
对照已多次用于源间一致性判定），但二者是独立副本» — the two are deliberately
INDEPENDENT copies of one machine, kept so that they can be diffed.  Nothing
diffed them.  This file does, for the diagnostics fylite actually fits.

★★It found a real divergence the first time it was run.  The two outermost
POINT chords were at ``z = ±0.422 m`` here and ``±0.425 m`` in both of
fydata's independent sources — and ``±0.425`` is also the only value that
keeps the array's uniform 85 mm ladder (0, ±0.085, ±0.17, ±0.255, ±0.34,
±0.425).  No upstream for ``0.422`` exists in this repository or in
``fylite_port``: no deck, no namelist, no note.

★And "only 3 mm" is exactly the reasoning to distrust here.  On #137985's
delivered equilibrium the TOP chord grazes the plasma — 8 cm of it lies
inside the boundary, against 55 cm for the midplane chord — so moving it
3 mm changes its ``∫n_e dl`` by **−23.1 %**.  (The bottom chord, deep inside,
moves −0.45 %.)  A tolerance loose enough to accept the difference would be
loose enough to hide a quarter of a channel.

The comparison needs a fydata checkout and SKIPS without one:

    FYDATA_DIR=~/workspace/fydata pytest python/tests/test_device_document_vs_fydata.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from conftest import requires_machine
from fylite import device

FYDATA_ENV = "FYDATA_DIR"

#: fydata's two independent EAST sources for the POINT sight lines.
_ABOX = "device/tokamak/east/fyo/0.0.0/static/legacy"
_IMAS3 = "device/tokamak/east/imas/3/static/interferometer.xml"


def _fydata() -> Path:
    root = os.environ.get(FYDATA_ENV)
    if not root:
        pytest.skip(f"set ${FYDATA_ENV} to a fydata checkout to run the "
                    "cross-source comparison")
    p = Path(root).expanduser()
    if not (p / _IMAS3).is_file():
        pytest.skip(f"${FYDATA_ENV}={p} does not look like a fydata checkout")
    return p


def _abox_z(root: Path, ids: str) -> list[float]:
    """POINT channel z from one fydata fyo A-Box, in channel order."""
    import yaml
    doc = yaml.safe_load((root / _ABOX / f"{ids}.yaml").read_text())
    return [float(c["line_of_sight"]["first_point"]["z"])
            for c in doc["channel"] if c["name"].startswith("POINT")]


def _imas3_z(root: Path) -> list[float]:
    """POINT channel z from the imas/3 XML — provider 刘海庆 (the POINT group
    leader named in fydata's own signal catalogue), 2022-12-05.

    ★A regex rather than an XML parse: the file is one ``<channel>`` per line
    with the values inline, and what is being asserted is the NUMBER, not the
    schema.  A shape change here should show up as "no channels found",
    which the length assertion below catches.
    """
    text = (root / _IMAS3).read_text()
    out = []
    for line in text.splitlines():
        m = re.search(r"<name>\s*(POINT\d+)\s*</name>", line)
        if not m:
            continue
        z = re.search(r"<first_point>.*?<z[^>]*>\s*(-?[\d.]+)\s*</z>", line)
        assert z, f"{m.group(1)}: no first_point z in {line[:120]}"
        out.append(float(z.group(1)))
    return out


def _ours(group: str) -> list[float]:
    return [float(c["line_of_sight"]["first_point"]["z"])
            for c in device.document()[group]["channel"]]


@requires_machine
@pytest.mark.parametrize("group", ["interferometer", "polarimeter"])
def test_point_chord_z_matches_fydata_a_box(group):
    root = _fydata()
    theirs = _abox_z(root, group)
    ours = _ours(group)
    assert len(theirs) == len(ours) == 11
    for i, (a, b) in enumerate(zip(ours, theirs), 1):
        assert a == pytest.approx(b, abs=1e-9), \
            f"{group} chord {i}: fylite {a} vs fydata A-Box {b} " \
            f"({1000 * (a - b):+.1f} mm)"


@requires_machine
def test_point_chord_z_matches_the_imas3_source_too():
    """The second source, and the one with a named provider.

    ★Two sources agreeing is what makes this a correction rather than a
    preference.  The A-Box derives from the 2015 diagnostic list; the imas/3
    XML is the instrument group's own.  They agree with each other, and
    (since 2026-08-21) with this document.
    """
    root = _fydata()
    theirs = _imas3_z(root)
    assert len(theirs) == 11, f"found {len(theirs)} POINT channels in {_IMAS3}"
    for i, (a, b) in enumerate(zip(_ours("polarimeter"), theirs), 1):
        assert a == pytest.approx(b, abs=1e-9), \
            f"POINT chord {i}: fylite {a} vs fydata imas/3 {b} " \
            f"({1000 * (a - b):+.1f} mm)"


@requires_machine
@pytest.mark.parametrize("group", ["interferometer", "polarimeter"])
def test_the_chord_ladder_is_uniform(group):
    """★A source-free check on the same fact, so a checkout with no fydata
    still catches the class of error.  The eleven chords are evenly spaced;
    a single mistyped channel breaks the spacing and nothing else does."""
    z = _ours(group)
    steps = [round(z[i] - z[i + 1], 6) for i in range(len(z) - 1)]
    assert len(set(steps)) == 1, \
        f"{group}: POINT chord spacing is not uniform: {steps}"
    assert steps[0] == pytest.approx(0.085, abs=1e-9)


@requires_machine
def test_the_browser_copy_carries_the_same_chords():
    """``fylite_device_east.json`` is a second copy of this machine for the
    app, generated by ``FyoDevice.toFyo``.  ★It is generated, and it is also
    committed — so it can be, and was, left behind by an edit to the
    document.  This is the diff that says it was not."""
    import json
    p = device.data_dir() / "fylite_device_east.json"
    if not p.is_file():
        pytest.skip(f"no browser device copy at {p}")
    browser = json.loads(p.read_text())["fylite:point"]
    for group in ("interferometer", "polarimeter"):
        theirs = [float(c["first_point"]["z"]) for c in browser[group]]
        assert theirs == pytest.approx(_ours(group)), group
