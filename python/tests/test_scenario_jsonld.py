"""`docs/reference/scenario.fyo.jsonld` is generated, and stays that way.

★★Why this gate exists.  The document says which fyo documents a complete
scenario comprises and what every slot's path, unit and rank is — a copy of the
interface, and a copy of a contract is not a contract.  It is regenerated here
and compared, so a change in the kernel's declaration tables cannot leave the
published shape describing last week's interface.

★It also holds the two claims the document makes that are NOT a copy: the
`fylite:unmapped` list (quantities a real scenario carries that have no declared
slot at all) and the `FYDOC-CASE-20` binding.  The first is checked from the
other side — none of those paths may have quietly acquired a slot — and the
second must never carry a value, only a path and a digest.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/reference/scenario.fyo.jsonld"
TOOL = ROOT / "tools/make-scenario-jsonld.py"


@pytest.fixture(scope="module")
def doc():
    if not DOC.is_file():
        pytest.skip(f"no {DOC.relative_to(ROOT)} in this checkout")
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_the_scenario_document_is_the_generator_s_output(doc):
    """Regenerate and compare — the whole point of generating it."""
    p = subprocess.run([sys.executable, str(TOOL), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, (
        "docs/reference/scenario.fyo.jsonld is not what the generator writes "
        f"({p.stdout.strip()}{p.stderr.strip()}) — run "
        "`python3 tools/make-scenario-jsonld.py`")


def test_every_slot_matches_the_interface_this_package_ships(doc):
    """Each path, unit and rank is the interface's own, and nothing was invented."""
    from fylite import _fyo_interface as fi
    assert doc["fylite:interface_revision"] == fi.REVISION
    assert doc["fylite:interface_digest"] == fi.DIGEST
    for d in doc["fylite:documents"]:
        table = fi.TABLES[d["fylite:table"]]
        assert d["@type"] == table["type"]
        assert d["fylite:slot_count"] == len(table["slots"])
        for slot in d["fylite:slots"]:
            got = table["slots"][slot["fylite:key"]]
            assert slot["fylite:path"] == got["path"]
            assert slot["fylite:units"] == got["units"]
            assert slot["fylite:rank"] == got["rank"]
            #: the one derived column: a namespaced slot is one whose PATH carries
            #: the prefix, which is the rule `test_fyo_vocabulary` enforces
            assert slot["fylite:namespaced"] == ("fylite:" in got["path"])


def test_the_unmapped_list_is_still_unmapped(doc):
    """★The gap list checked from the other side.

    Every path in `fylite:unmapped` is a quantity with no declared slot.  If one
    of them ever gains a slot, this page's claim stops being true — and the way
    that goes wrong is silent, because the page would still read plausibly.
    """
    from fylite import _fyo_interface as fi
    declared = {v["path"] for t in fi.TABLES.values() for v in t["slots"].values()}
    still = []
    for item in doc["fylite:unmapped"]:
        if item["fylite:path"] in declared:
            still.append(item["fylite:path"])
    assert not still, (
        "these are listed as having no declared slot, and now they do: "
        f"{still} — the page has to be rewritten, not the list trimmed")
    assert doc["fylite:unmapped"], "the gap list is empty; that would be news"


def test_the_binding_carries_no_values(doc):
    """★★★The publication boundary, as a gate.

    `FYDOC-CASE-20` is `release: internal` — the design side's unpublished run.
    The binding may name its files and their digests, which is how this
    ecosystem reaches restricted data; it may not carry one number out of them.
    A list or a float appearing in this section is the failure this test exists
    to catch.
    """
    b = doc["fylite:binding"]
    assert b["fylite:case"] == "FYDOC-CASE-20"
    allowed = {"@id", "fylite:path", "fylite:sha256", "fylite:feeds", "fylite:registered"}
    for src in b["fylite:sources"]:
        assert set(src) <= allowed, f"unexpected key in a binding entry: {set(src) - allowed}"
        assert isinstance(src["fylite:path"], str)
        assert src["fylite:sha256"] is None or (
            isinstance(src["fylite:sha256"], str) and len(src["fylite:sha256"]) == 64)
        assert all(isinstance(x, str) for x in src["fylite:feeds"])
    #: and nothing numeric anywhere under the binding, at any depth
    def walk(node, where="binding"):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{where}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        else:
            assert not isinstance(node, (int, float)) or isinstance(node, bool), (
                f"a number rides in the binding at {where}: {node!r} — the case is "
                "release: internal and this section carries paths and digests only")
    walk(b)
