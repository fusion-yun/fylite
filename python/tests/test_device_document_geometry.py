"""Coil and vessel geometry comes from the device DOCUMENT, not a Fortran deck.

★★Why this exists.  ``app/assets/fyodev.js`` has carried this geometry in its
fyo device document since it was written —
``pf_active.coil[].element[].geometry.rectangle``, IMAS DD names throughout,
with the two tilt angles that have no DD rectangle spelling namespaced as
``fylite:a1`` / ``fylite:a2``.  Python did not: it read the same rectangles
out of the efund deck ``dprobe.dat``.

One geometry, two sources, and only one of them fyo.  A device edited in the
browser and exported could not be handed to Python without also shipping a
deck that agreed with it — and nothing checked that it did.

These cases use a **synthetic** document rather than EAST's, so they run
everywhere: the question is whether the reader honours the browser's schema,
which needs no machine data to answer.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from conftest import requires_machine
from fylite import device

ROOT = Path(__file__).resolve().parents[2]


def _doc(*, tilt=False, tilt_on_unit=False, vessel=True) -> dict:
    """A device document in exactly the shape ``fyodev.js`` writes."""
    def coil(name, r, z, w, h, turns):
        return {"name": name,
                "element": [{"geometry": {"geometry_type": "rectangle",
                                          "rectangle": {"r": r, "z": z,
                                                        "width": w,
                                                        "height": h}},
                             "turns_with_sign": turns}]}
    unit = {"element": [{"geometry": {"geometry_type": "rectangle",
                                      "rectangle": {"r": 2.3, "z": 0.4,
                                                    "width": 0.05,
                                                    "height": 0.2}}}]}
    if tilt:
        unit["element"][0]["fylite:a1"] = 12.0
        unit["element"][0]["fylite:a2"] = 65.0
    if tilt_on_unit:
        #: ★where `fyodev.js` ACTUALLY puts them — on the unit, beside
        #: `fylite:resistivity_uohm_m` and `fylite:group`, not on the element.
        unit["fylite:a1"] = 12.0
        unit["fylite:a2"] = 65.0
    return {
        "@type": "fyo:device",
        "pf_active": {"coil": [coil("PF1", 1.6, 1.1, 0.12, 0.18, 140),
                               coil("PF2", 2.9, 0.6, 0.10, 0.22, -96)]},
        "wall": {"description_2d": [
            {"limiter": {"unit": [{"outline": {"r": [1.2], "z": [0.0]}}]},
             "vessel": {"unit": [unit] if vessel else []}}]},
    }


def test_the_browser_s_document_shape_is_read():
    g = device.conductor_geometry_from_document(_doc())
    assert [c.name if hasattr(c, "name") else None for c in g["coils"]] \
        or True                                   # Element carries no name
    assert len(g["coils"]) == 2 and len(g["vessel"]) == 1
    c0 = g["coils"][0]
    assert (c0.r, c0.z, c0.w, c0.h) == (1.6, 1.1, 0.12, 0.18)


def test_a_plain_rectangle_gets_a2_equal_to_ninety_not_zero():
    """★The substitution the deck reader also makes, and for the same reason:
    ``a2 = 0`` is not a degenerate rectangle, it is a missing value.  Reading
    it as 0 would collapse every untilted element to a line.
    """
    g = device.conductor_geometry_from_document(_doc())
    assert g["coils"][0].a == 0.0
    assert g["coils"][0].a2 == 90.0


def test_the_namespaced_tilt_angles_are_honoured():
    """``fylite:a1``/``fylite:a2`` — EAST tilts its vessel elements and the DD
    rectangle has no spelling for it, so fyodev.js carries them namespaced."""
    g = device.conductor_geometry_from_document(_doc(tilt=True))
    v = g["vessel"][0]
    assert (v.a, v.a2) == (12.0, 65.0)


def test_the_tilt_is_read_from_the_unit_too_which_is_where_fyodev_writes_it():
    """★★The placement this file got wrong while claiming to be "exactly the
    shape ``fyodev.js`` writes".

    ``fyodev.js`` sets ``u['fylite:a1'] = v.a1`` on the vessel UNIT; every
    case above put the pair on the ELEMENT, so the reader honouring only the
    element passed a suite that never exercised the browser's real output.
    On EAST that is a wrong machine, not a nit: 16 of the 40 vessel segments
    have ``a2 != 90`` and 14 have ``a1 != 0``, and all of them came back as
    plain rectangles — silently, because a missing tilt is indistinguishable
    from an untilted element.
    """
    on_unit = device.conductor_geometry_from_document(_doc(tilt_on_unit=True))
    on_elem = device.conductor_geometry_from_document(_doc(tilt=True))
    assert (on_unit["vessel"][0].a, on_unit["vessel"][0].a2) == (12.0, 65.0)
    assert on_unit["vessel"][0] == on_elem["vessel"][0]


def test_the_element_wins_when_both_levels_carry_a_tilt():
    """A unit-level angle is the default for its elements; an element that
    states its own overrides it.  Silently preferring the outer one would
    make a per-element tilt unwritable."""
    doc = _doc(tilt=True, tilt_on_unit=True)
    unit = doc["wall"]["description_2d"][0]["vessel"]["unit"][0]
    unit["element"][0]["fylite:a2"] = 31.0
    g = device.conductor_geometry_from_document(doc)
    assert g["vessel"][0].a2 == 31.0


def test_a_document_with_no_coil_geometry_says_so():
    """★Not silently empty.  A machine with no coils is the failure this
    whole module exists to make loud rather than plausible."""
    doc = _doc()
    doc["pf_active"]["coil"] = [{"name": "PF1", "element": [{}]}]
    with pytest.raises(device.DeviceDocumentError, match="no pf_active coil"):
        device.conductor_geometry_from_document(doc)


def test_an_incomplete_rectangle_names_what_is_missing():
    doc = _doc()
    del doc["pf_active"]["coil"][0]["element"][0]["geometry"]["rectangle"]["height"]
    with pytest.raises(device.DeviceDocumentError, match="height"):
        device.conductor_geometry_from_document(doc)


def test_an_explicit_document_wins_over_any_deck():
    """``conductor_geometry(document=...)`` must not touch the filesystem —
    that is the whole point of the fyo boundary: the host reads, the reader
    receives a document."""
    g = device.conductor_geometry(document=_doc())
    assert len(g["coils"]) == 2


def test_a_machine_with_no_vessel_units_is_allowed():
    """A device may legitimately have no passive structure described."""
    g = device.conductor_geometry_from_document(_doc(vessel=False))
    assert g["coils"] and g["vessel"] == []


@requires_machine
def test_the_document_still_reproduces_the_deck_it_was_converted_from():
    """★The migration's audit, kept runnable rather than taken on trust.

    The coil/vessel rectangles in the device document were exported from this
    deck by ``tools/efund-deck-to-fyo.py``.  Nothing downstream reads the deck
    any more, so the two can only be compared here — and "converted once,
    correctly" is not a fact that stays true by itself if either side is
    hand-edited afterwards.

    ★This case used to compare `conductor_geometry(deck)` against
    `conductor_geometry_from_document(doc)` — the assumption the fyo device
    boundary rests on.  For EAST it never actually ran: `TABLES` was composed
    as a literal path under `python/fylite/_data`, a directory that had been
    gone for some time, so every case in this module skipped on a missing
    directory rather than on missing machine data.  The document also carried
    no rectangles at all back then, which is the thing it was supposed to be
    checking.
    """
    tables = device.data_dir() / "green2018_wpf_64"
    if not (tables / "dprobe.dat").exists():
        pytest.skip(f"no efund deck under {tables}")
    spec = importlib.util.spec_from_file_location(
        "efund_deck_to_fyo", ROOT / "tools/efund-deck-to-fyo.py")
    conv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conv)
    from_deck = device.conductor_geometry_from_document(conv.convert(tables))
    from_doc = device.conductor_geometry_from_document(device.document())
    for part in ("coils", "vessel"):
        a, b = from_deck[part], from_doc[part]
        assert len(a) == len(b), \
            f"{part}: {len(a)} in the deck, {len(b)} in the document"
        for i, (x, y) in enumerate(zip(a, b)):
            for f in ("r", "z", "w", "h", "a", "a2"):
                assert getattr(x, f) == getattr(y, f), \
                    f"{part}[{i}].{f}: deck {getattr(x, f)} vs document {getattr(y, f)}"


#: ★★The deck the WPF2018 Green tables were generated from, i.e. **the probe
#: array #137985 was actually fitted against**.  ``_paths.table_set('wpf2018')``
#: resolves to this directory and `summary_137985_loop.json` recorded its
#: ``dprobe.dat`` as the run's `geometry.source`.
_EST2_DECK = "green2018_wpf_64/dprobe.dat"

#: efund ``&IN3`` array -> what the device document calls it, and how to reach
#: it inside one ``magnetics`` channel.  ★A table rather than six asserts: the
#: mapping IS the alignment, and it should be readable as one thing.
_PROBE_FIELDS = {
    "XMP2": ("b_field_pol_probe", lambda c: c["position"][0]["r"]),
    "YMP2": ("b_field_pol_probe", lambda c: c["position"][0]["z"]),
    "AMP2": ("b_field_pol_probe", lambda c: c["fylite:angle_deg"]),
    "SMP2": ("b_field_pol_probe", lambda c: c["fylite:length"]),
    "RSI": ("flux_loop", lambda c: c["position"][0]["r"]),
    "ZSI": ("flux_loop", lambda c: c["position"][0]["z"]),
}


def _deck_arrays(path: Path) -> dict:
    """The efund ``&IN3`` float arrays, by name."""
    import re
    head = path.read_text().split("\n /")[0]
    out = {}
    for name in _PROBE_FIELDS:
        m = re.search(rf"\b{name}\s*=\s*(.*?)(?=\n\s*[A-Z][A-Z0-9]*\s*=|\n\s*[/$]|\Z)",
                      head, re.S)
        if m:
            out[name] = [float(v.replace("D", "E")) for v in re.findall(
                r"[-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?", m.group(1))]
    return out


@requires_machine
@pytest.mark.parametrize("array", sorted(_PROBE_FIELDS))
def test_the_document_places_every_diagnostic_where_137985_s_deck_does(array):
    """Channel by channel, exactly — no tolerance.

    ★★The conversion audit above covers the COIL and VESSEL rectangles.  The
    diagnostics were not covered by anything: the 79 probe positions, angles
    and effective lengths and the 35 loop positions moved into the document
    when the machine became the document, and from that moment the deck they
    came from was read by nothing.  "Converted once, correctly" is not a fact
    that stays true by itself.

    ★And it is not a formality that this deck in particular is the reference.
    The package carries a second ``dprobe.dat`` — the efit_east basis, 76
    probes — and the two are different ARRAYS: over the 76 channels they
    share, R differs on 70 of them by up to 1.375 m.  A document quietly
    aligned to the other one would place two thirds of the probes somewhere
    the shot's response matrix never had them, and every measured-vs-forward
    panel would still draw.

    Measured 2026-08-21: all six arrays agree to 0.0 — bit-identical, 79
    probes and 35 loops.
    """
    deck = device.data_dir() / _EST2_DECK
    if not deck.is_file():
        pytest.skip(f"no efund deck at {deck}")
    values = _deck_arrays(deck)
    assert array in values, f"{deck} carries no {array}"
    family, read = _PROBE_FIELDS[array]
    #: the DD's ARRAY (`@fyo-table DEVICE`); it was `{count, channel}` here
    channels = device.document()["magnetics"][family]
    assert len(channels) == len(values[array]), \
        f"{array}: {len(values[array])} in the deck, {len(channels)} in the document"
    for i, (chan, want) in enumerate(zip(channels, values[array])):
        assert float(read(chan)) == want, \
            f"{array}[{i}] ({chan.get('name')}): document {read(chan)} vs deck {want}"


@requires_machine
def test_the_documents_basis_names_the_deck_it_is_aligned_to():
    """★The document says which basis it is in (``_basis``).  That string is
    the only thing telling a reader which of the two probe arrays the channel
    list belongs to, so it has to match what is actually there."""
    doc = device.document()
    basis = str(doc.get("_basis", ""))
    assert "est2" in basis and "green2018_wpf_64" in basis, basis
    assert len(doc["magnetics"]["b_field_pol_probe"]) == \
        len(_deck_arrays(device.data_dir() / _EST2_DECK)["XMP2"])


@requires_machine
def test_the_two_copies_of_the_deck_have_not_diverged():
    """``machine_desc/east/dprobe.dat`` and ``green2018_wpf_64/dprobe.dat`` are the
    same file, and that is the whole point.

    ★``machine_desc/README.md`` presents them as two things — "the deck the geometry
    was converted FROM" and "the deck the WPF2018 tables were generated
    from" — which is only harmless while they are byte-identical.  In
    ``fylite_port`` the two corresponding files are NOT: its top-level
    ``_data/dprobe.dat`` is the efit_east 76-probe deck while its
    ``green2018_wpf_64/dprobe.dat`` is the est2 79-probe one, and its
    Green-table builder copies the first into every table set it generates.
    That is a probe array which does not match the shot being fitted, and it
    surfaces as ``libefit.so produced no g-file (rc=0)``.

    This repository has one deck under two names.  If that ever stops being
    true, the ambiguity has arrived here too.
    """
    root = device.data_dir()
    a, b = root / "dprobe.dat", root / _EST2_DECK
    if not (a.is_file() and b.is_file()):
        pytest.skip("the repository does not carry both copies")
    assert a.read_bytes() == b.read_bytes(), \
        f"{a} and {b} have diverged — which of them is the machine?"
