"""Every device description spells its fields the way the table declares.

★★**What the table is.**  `rust/fylite/src/fyo.rs` declares
`@fyo-table DEVICE` — the document path of every field both hosts read out of
a machine description — and `rust/build.sh` generates it into
`python/fylite/_fyo_interface.py` and `app/assets/fyo-interface.js`.  It is
the same mechanism `_abi.py` and `_deck_names.py` already use, for the same
reason: two copies of a contract are not a contract.

★**And what it fixed.**  Before it existed the two hosts spelled the machine
differently — `magnetics.flux_loop` as `{count, note, channel: [...]}` here
and as the DD's array in the browser, `wall.description_2d` as a mapping here
and an array there, the turn count on the channel here and on the element
there.  Nothing could see the difference, and under it EAST was running on
two different WALLS (`test_east_descriptions_agree.py`).

This gate walks each committed description against the declared paths.  It
does not check VALUES — that is what the per-machine gates do — only that a
field a host will look for is where the table says it is.

★A path that resolves nowhere in a given document is not automatically an
error: `machine_desc/jt60sa/` genuinely has no coils, and says so with
`fylite:absent`.  What is an error is a field that EXISTS under a
non-canonical name, because that is the dialect coming back.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fylite import _fyo_interface as IFACE

ROOT = Path(__file__).resolve().parents[2]
DESC = ROOT / "machine_desc"

DEVICE = IFACE.TABLES["DEVICE"]["slots"]
AOS = set(IFACE.AOS)

DOCS = sorted(DESC.glob("*/*_device.yaml")) + sorted(DESC.glob("*/fylite_device_*.json"))

pytestmark = pytest.mark.skipif(not DOCS, reason="no machine_desc/ in this tree")


def _load(p: Path):
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _walk(doc, path: str):
    """Follow one declared path, stepping into index 0 of every AoS segment.

    Returns ``(True, value)`` when it resolves and ``(False, where_it_stopped)``
    when it does not — the two are different answers and a caller that gets
    them confused reports "missing" for a document that is simply built for a
    machine with no such hardware.
    """
    node, seen = doc, []
    for seg in path.split("/"):
        if not isinstance(node, dict) or seg not in node:
            return False, "/".join(seen) or "<root>"
        node = node[seg]
        seen.append(seg)
        if seg in AOS:
            if not isinstance(node, list):
                return False, ("/".join(seen) + " (declared an array of "
                               "structure, found a mapping)")
            if not node:
                return False, "/".join(seen) + " (empty)"
            node = node[0]
    return True, node


@pytest.mark.parametrize("doc_path", DOCS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_declared_field_hides_under_a_non_canonical_name(doc_path: Path):
    """★★The one that matters: a field that is THERE but spelled otherwise.

    A missing coil set is a fact about a machine.  A coil set reachable at
    `magnetics.flux_loop.channel` when the table says `magnetics.flux_loop`
    is the second dialect returning, and it is invisible to every reader that
    believes the table.
    """
    doc = _load(doc_path)
    bad = []
    for key, slot in DEVICE.items():
        ok, _ = _walk(doc, slot["path"])
        if ok:
            continue
        legacy = _legacy_hit(doc, slot["path"])
        if legacy:
            bad.append(f"{key}: declared at {slot['path']!r}, found at "
                       f"{legacy!r}")
    assert not bad, (
        f"{doc_path.relative_to(ROOT)} spells declared fields its own way:\n  "
        + "\n  ".join(bad)
        + "\n(the declaration is rust/fylite/src/fyo.rs, @fyo-table DEVICE)")


def _legacy_hit(doc, path: str) -> str | None:
    """The non-canonical spellings this repository has actually shipped.

    ★Named, not guessed.  A gate that searched the document for anything
    shaped like the missing field would report a machine's own extension as
    a dialect; these three are the ones that were here, and the list may only
    shrink.
    """
    for canon, legacy in (
            ("magnetics/flux_loop/", "magnetics/flux_loop/channel/"),
            ("magnetics/b_field_pol_probe/",
             "magnetics/b_field_pol_probe/channel/"),
            ("pf_active/coil/element/turns_with_sign", "pf_active/coil/turns")):
        if path.startswith(canon):
            alt = legacy + path[len(canon):] if canon.endswith("/") else legacy
            ok, _ = _walk(doc, alt)
            if ok:
                return alt
    #: `wall/description_2d` as a bare mapping — the AoS step is what fails
    if path.startswith("wall/description_2d/"):
        node = (doc.get("wall") or {}).get("description_2d")
        if isinstance(node, dict):
            return "wall/description_2d (a mapping, not an array)"
    return None


@pytest.mark.parametrize(
    "doc_path", [p for p in DOCS if p.suffix == ".json"],
    ids=lambda p: p.parent.name)
def test_a_browser_document_resolves_every_slot_its_machine_has(doc_path: Path):
    """★The browser document is the one an import channel parses, and
    `FyoDevice.fromFyo` is strict about what it needs: coils, a limiter, a
    grid and `tf.b0`.  Those four must resolve or the machine cannot be
    opened at all."""
    doc = _load(doc_path)
    must = ["coil_r", "coil_turns", "limiter_r", "limiter_z", "r0", "b0", "grid"]
    missing = [k for k in must if not _walk(doc, DEVICE[k]["path"])[0]]
    assert not missing, (
        f"{doc_path.relative_to(ROOT)} cannot be imported: {missing}")


def test_the_table_declares_every_field_the_browser_reader_needs():
    """★★A path the browser reads and the table does not declare is a
    spelling that can drift again — the exact hole this table closed.

    Checked against `fyodev.js`'s source rather than a list kept here: a
    second list would be the third copy of the contract.
    """
    src = (ROOT / "app" / "assets" / "fyodev.js").read_text(encoding="utf-8")
    declared = {s["path"] for s in DEVICE.values()}
    #: leaves the reader names in the shape they appear in that file
    for leaf, path in (("turns_with_sign", "pf_active/coil/element/turns_with_sign"),
                       ("poloidal_angle", "magnetics/b_field_pol_probe/poloidal_angle"),
                       ("fylite:channel_map", "fylite:channel_map"),
                       ("fylite:grid", "fylite:grid"),
                       ("fylite:a1", "pf_active/coil/element/fylite:a1")):
        assert leaf in src, f"fyodev.js no longer reads {leaf}"
        assert path in declared, f"{leaf} is read but not declared: {path}"
