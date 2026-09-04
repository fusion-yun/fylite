"""The NOTICE names files that exist, and every derived file is named.

★★Why this exists.  ``NOTICE`` is not documentation — under Apache-2.0
section 4 it is the attribution that has to travel with the derivative work,
and the per-file list is the substance of it.  On 2026-08-21 **eleven of its
eighteen entries pointed at nothing**::

    python/fylite/{mapping,sources,solver,gacode_io,geo,neo,tglf,machine}.py
    tests/data/{tglf/ga-std,tgyro/treg01,frozen-libs}

Not one of those files had been deleted as a work — they had MOVED, into the
Rust kernel or into the ``scenario/`` and ``io/`` subpackages, and the notice
did not move with them.  Meanwhile three Rust files that had BECOME derived
works in the same refactors (``sources.rs``, ``bundle.rs``, part of
``transport.rs``) were absent from it altogether.

★A licence obligation kept in a plain-text file with nothing checking it
decays exactly like a docstring, and it decays in the direction that matters:
towards claiming less provenance than the code actually has.  Both halves are
gated here, because only checking the paths would let a NEW port land
unattributed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOTICE = ROOT / "NOTICE"

pytestmark = pytest.mark.skipif(not NOTICE.exists(),
                                reason="no NOTICE in this tree")

#: a path-looking token in the NOTICE's per-file lists
_PATH = re.compile(r"(?:python|rust|app|tools|tests|machine_desc)/[\w./{},*-]*")


def _expand(tok: str) -> list[str]:
    """``a/{x,y}.py`` -> ``[a/x.py, a/y.py]``; a trailing ``*`` is a prefix."""
    m = re.search(r"\{([^}]*)\}", tok)
    if m:
        return [p for alt in m.group(1).split(",")
                for p in _expand(tok[:m.start()] + alt.strip() + tok[m.end():])]
    return [tok]


def _listed() -> set[str]:
    """Every path token the NOTICE names, brace-expanded."""
    out: set[str] = set()
    for line in NOTICE.read_text(encoding="utf-8").splitlines():
        #: only the indented file lists, not the prose around them
        if not line.startswith("    "):
            continue
        for tok in _PATH.findall(line):
            out.update(_expand(tok.rstrip(".,")))
    return out


def test_every_path_the_notice_names_exists():
    """★The half that had rotted.  A glob is satisfied by ANY match, which is
    the right reading: ``tests/data/frozen-libs/tglf*`` says "the tglf recordings are
    derived", not "exactly these files are"."""
    missing = []
    for p in sorted(_listed()):
        if "*" in p:
            head, _, _ = p.partition("*")
            d = ROOT / Path(head).parent
            stem = Path(head).name
            if not (d.is_dir() and any(f.name.startswith(stem)
                                       for f in d.iterdir())):
                missing.append(p)
        elif not (ROOT / p).exists():
            missing.append(p)
    assert not missing, (
        "the NOTICE attributes files that are not in this tree:\n  "
        + "\n  ".join(missing)
        + "\n\nThey were almost certainly MOVED, not deleted — find where the "
          "work went and update the entry.  Dropping the entry instead drops "
          "an Apache-2.0 section 4 obligation.")


#: Source files may declare upstream provenance without being derived works —
#: a comparison against an oracle is not a translation.  Each waiver says
#: which, and why, so the distinction stays visible rather than assumed.
NOT_DERIVED = {
    "rust/fylite/src/c_api.rs":
        "the ABI layer: it NAMES the ported entries and carries their unit "
        "and layout contracts, but the translations are in the modules it "
        "calls.",
    "rust/fylite/src/heating.rs":
        "an original beam/wave deposition kernel; the upstream reference in "
        "its header is to a formula's provenance, not to transcribed code.",
    "rust/fylite/src/lib.rs":
        "the crate root — a module list with the same names.",
    "rust/fylite/src/linalg.rs":
        "written from scratch to REPLACE LAPACK/UMFPACK; it names them to say "
        "what it stands in for.",
    "rust/fylite/src/inverse.rs":
        "its own header says it is not a port of any library.",
    "rust/fylite/src/equilibrium.rs":
        "the Grad-Shafranov solve, this project's own.",
    "rust/fylite/src/surfaces.rs":
        "surface tracing, this project's own.",
    "rust/fylite/src/kernels.rs":
        "a dispatch table.",
}

#: What a header says when the file below it is a translation.
_CLAIMS = re.compile(
    r"white-box|NOT clean room|a port of|ported from|port of|translation of",
    re.I)


def test_every_rust_file_claiming_a_port_is_attributed():
    """★★The half that only fails LATER, and is therefore the one worth
    writing.  Missing paths are visible the moment someone reads the file;
    a new port that never got an entry is invisible until somebody
    downstream needs the attribution and it is not there."""
    listed = _listed()
    bad = []
    for src in sorted((ROOT / "rust/fylite/src").glob("*.rs")):
        rel = str(src.relative_to(ROOT))
        head = "\n".join(src.read_text(encoding="utf-8").splitlines()[:40])
        if not _CLAIMS.search(head):
            continue
        if rel in listed or rel in NOT_DERIVED:
            continue
        bad.append(rel)
    assert not bad, (
        "these files declare an upstream translation in their header and are "
        "not in the NOTICE:\n  " + "\n  ".join(bad)
        + "\n\nAdd them, or — if the header means an oracle rather than a "
          "port — say so in NOT_DERIVED in this file.")


def test_the_waivers_still_describe_real_files():
    """A waiver for a file that is gone reads as a considered decision and is
    a leftover; it also hides the next file that needs one."""
    gone = sorted(p for p in NOT_DERIVED if not (ROOT / p).exists())
    assert not gone, f"NOT_DERIVED names files that no longer exist: {gone}"


@pytest.mark.parametrize(
    "lineage,marker",
    [("GACODE", "gafusion/gacode"),
     ("METIS", "CeCILL-C"),
     ("fytrans", "fytrans/channels.py")])
def test_each_transcribed_lineage_has_its_own_section(lineage, marker):
    """★Three codes were transcribed and the NOTICE named one.

    ``nbi.py`` states in its own docstring that it is transcribed from METIS
    (CEA, CeCILL-C) and lists the six ``.m`` files; ``assembly.py`` states
    that its channel grammar is kept identical to fytrans (MIT).  Neither
    appeared in the NOTICE, so the distribution shipped a Chinese-wall
    argument in one file and a licence header that only knew about GACODE.
    """
    text = NOTICE.read_text(encoding="utf-8")
    assert f"DERIVED WORK — {lineage}" in text, \
        f"the NOTICE has no section for {lineage}"
    assert marker in text, \
        f"the {lineage} section does not identify the upstream ({marker!r})"


def test_the_phantom_licence_citation_resolves():
    """★★Twenty-seven comments explain a removal with "left with LICENSE 3.1"
    or "3.2", citing sections of a document that does not exist — the LICENSE
    beside the NOTICE is plain Apache-2.0 and has none.

    Rewriting twenty-seven sites (six of them in the changelog, which is a
    record and should not be edited) buys less than defining the term once
    where a reader looking up a licence phrase will actually go.  So the
    NOTICE defines it, and this fails if the definition is dropped while the
    citations remain.
    """
    citing = []
    for root in ("python/fylite", "python/tests", "tests",
                 "rust/fylite/src", "machine_desc"):
        for f in (ROOT / root).rglob("*"):
            if f.suffix in (".py", ".rs", ".md", ".yaml") and f.is_file():
                if re.search(r"LICENSE\s*(?:§\s*)?3\.[12]",
                             f.read_text(encoding="utf-8", errors="ignore")):
                    citing.append(str(f.relative_to(ROOT)))
    if not citing:
        pytest.skip("nothing cites the phrase any more")
    text = NOTICE.read_text(encoding="utf-8")
    assert '"LICENSE 3.1" / "LICENSE 3.2"' in text, (
        f"{len(citing)} file(s) cite LICENSE 3.1/3.2 and the NOTICE no longer "
        f"says what that means:\n  " + "\n  ".join(sorted(citing)[:8]))
    assert "libefit.so" in text and "libtglf.so" in text, (
        "the definition no longer names what each clause removed")


# --------------------------------------------------------------------------- #
# The capability catalog may not advertise a library that left
# --------------------------------------------------------------------------- #

#: ★★The manifests under ``python/fylite/_manifest/`` are what a machine reads
#: to find out what this package computes — ``fylite describe``, the JSON-RPC
#: catalog and every reflected LLM tool description come from them.  One of
#: them said "NEO drift-kinetic bootstrap current (**libneo.so**)" while the
#: NOTICE says that library was removed (§3.2) and what stands in its place is
#: a white-box translation.  For a human that is a stale parenthesis; for a
#: model choosing a tool it is a claim about HOW the number is produced, and
#: the wrong one — it reads as a binding to a vendored binary that this
#: distribution does not contain.
#:
#: The removed set is DERIVED, never listed here: a library the NOTICE names
#: and the tree does not ship is a library that left.
_LIB = re.compile(r"lib\w+\.so")
MANIFESTS = ROOT / "python" / "fylite" / "_manifest"


def _departed_libraries() -> set[str]:
    named = set(_LIB.findall(NOTICE.read_text(encoding="utf-8")))
    shipped = {p.name for p in (ROOT / "python" / "fylite" / "_lib").glob("*.so")}
    return named - shipped


def test_the_notice_names_at_least_one_departed_library():
    """★A detector that finds nothing to look for is not passing, it is idle."""
    assert _departed_libraries(), (
        "no removed library found in the NOTICE — either §3 changed shape or "
        "the scan stopped seeing it; the gate below is meaningless either way.")


@pytest.mark.parametrize("doc", sorted(MANIFESTS.glob("*.jsonld")),
                         ids=lambda p: p.stem)
def test_no_manifest_advertises_a_departed_library(doc):
    text = doc.read_text(encoding="utf-8")
    named = sorted(lib for lib in _departed_libraries() if lib in text)
    assert not named, (
        f"{doc.relative_to(ROOT)} advertises {named}, which the NOTICE says "
        "this distribution does not ship. Name what actually computes the "
        "answer (the Rust port), not the library it was translated from.")
