"""The fyo shared vocabulary: a term two hosts write must be spelled once.

★★Why this exists.  ``psi_norm`` was written **bare** by
``app/assets/session.js`` and by one block of ``app/assets/scenario-analysis.js``,
while ``fyo.py`` and the *other* block of ``scenario-analysis.js`` wrote
``fylite:psi_norm`` — inside documents all typed ``fyo:equilibrium``.

The failure mode is the quiet one.  ``psi_norm`` is **not** an IMAS-DD name —
the DD has no normalised-flux coordinate, which is precisely why the term is
namespaced.  A bare spelling claims a provenance it does not have, and a
reader looking for the prefixed field simply does not find it: no error, just
a document that silently lost a section.  Nothing raised, and no reader ever
consumed the bare form — the write was unreachable.

The rule is one-directional, so it needs no list of DD names:

    **a term in the shared vocabulary MUST always carry the ``fylite:``
    prefix.**

Scope is chosen, not arbitrary.  The vocabulary holds the terms **more than
one host writes**: a term only one host writes is that page's private
extension and cannot diverge; these can, because two independent writers
spell them.

★And the gate binds only the terms a spelling check *can* bind.  ``q``,
``config``, ``result`` and five others are equally part of the contract, but
they are also ordinary local names in both hosts — gating them by spelling
would bury the rule in false positives, which is how a rule stops being read.
The vocabulary carries that distinction per term rather than leaving the gap
unexplained.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = ROOT / "python/fylite/_fyo_vocab.json"
GENERATED_JS = ROOT / "app/assets/fyo-interface.js"
#: the generated PATH tables — one declaration, both hosts (see
#: ``rust/fylite/src/fyo.rs``)
INTERFACE_PY = ROOT / "python/fylite/_fyo_interface.py"

VOCAB = json.loads(VOCAB_PATH.read_text())
TERMS: dict[str, dict] = VOCAB["terms"]
GATED = sorted(t for t, v in TERMS.items() if v["gated"])

#: Sources that write fyo documents, in both hosts.
SOURCES = sorted(
    [p for p in (ROOT / "app/assets").glob("*.js")
     if not p.name.startswith("lang-") and p.name != GENERATED_JS.name]
    + [p for p in (ROOT / "python/fylite").rglob("*.py")
       if p.name != INTERFACE_PY.name])

from fylite.fyo import FYLITE_PREFIX  # noqa: E402

_TRIPLE = ('"' * 3, "'" * 3)


def _strip_prose(text: str, suffix: str) -> str:
    """Blank out comments and docstrings, keeping line numbers.

    ★Needed, not defensive: ``fyo.py``'s measurement-input comment block
    DESCRIBES an input format and names ``coil_current_units`` bare while
    doing so (it was ``imas_io.py``'s module docstring before the split; the
    prose moved with the face it documents).  That is prose about a different
    format, not a document write, and a gate that called it a defect would
    simply be wrong.
    """
    out: list[str] = []
    open_q: str | None = None
    for line in text.splitlines():
        st = line.strip()
        if suffix == ".py":
            if open_q is not None:
                if open_q in st:
                    open_q = None
                out.append("")
                continue
            for q in _TRIPLE:
                if st.startswith(q):
                    if not (len(st) > 2 * len(q) and st.endswith(q)):
                        open_q = q
                    st = ""
                    break
            if st.startswith("#"):
                st = ""
        elif st.startswith(("//", "*", "/*")):
            st = ""
        out.append(st)
    return "\n".join(out)


def _bare_uses(text: str, term: str, suffix: str) -> list[int]:
    """Lines where ``term`` is written as a document field WITHOUT its prefix.

    ``name:`` as a dict/object key, and ``["name"]`` as a subscript — the two
    ways either host writes a field.
    """
    text = _strip_prose(text, suffix)
    esc = re.escape(term)
    pats = (re.compile(r"^\s*" + esc + r"\s*:", re.M),
            re.compile(r"""\[\s*['"]""" + esc + r"""['"]\s*\]"""))
    hits = []
    for pat in pats:
        for m in pat.finditer(text):
            #: the prefixed spelling CONTAINS the bare one — skip those
            if "fylite:" in text[max(0, m.start() - 10):m.end()]:
                continue
            hits.append(text[:m.start()].count("\n") + 1)
    return sorted(hits)


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.name)
def test_no_host_writes_a_gated_term_without_its_prefix(src: Path):
    bad = [f"{term!r} bare at line {line}"
           for term in GATED
           for line in _bare_uses(src.read_text(), term, src.suffix)]
    assert not bad, (
        f"{src.relative_to(ROOT)} writes shared vocabulary terms bare:\n  "
        + "\n  ".join(bad)
        + "\n\nA gated term in _fyo_vocab.json must always be spelled "
          "'fylite:<term>'.  Bare, it claims IMAS-DD provenance it does not "
          "have, and no reader of the prefixed spelling will find it.")


def test_the_generated_browser_copy_is_in_step():
    """★Generated, not kept in step by hand — the same reason ``_abi.py`` is.

    If this fails, run ``rust/build.sh``; do not edit ``fyo-names.js``.
    """
    assert GENERATED_JS.exists(), "run rust/build.sh"
    listed = set(re.findall(r"^\s*'([a-z_0-9]+)',", GENERATED_JS.read_text(), re.M))
    assert listed == set(TERMS), (
        "app/assets/fyo-interface.js is stale.\n"
        f"  only in json: {sorted(set(TERMS) - listed)}\n"
        f"  only in js:   {sorted(listed - set(TERMS))}\n"
        "Run rust/build.sh.")


def test_one_term_space_has_exactly_one_iri():
    """★★Every ``fylite:`` prefix declaration in the tree must be the same IRI.

    There were THREE, one per writer: ``fyo.CONTEXT`` said
    ``https://github.com/fusion-yun/fylite#``, ``app/assets/fyodev.js`` said
    ``https://fusion-yun.github.io/fylite/ns#``, and the run manifest and the
    browser's session export said ``urn:fylite:``.

    ★Why the rest of this file could not catch it.  Everything above checks
    how a TERM is spelled — that ``psi_norm`` never goes out bare, that both
    hosts agree on the listed set.  All of that passed while the two hosts
    disagreed about what the prefix RESOLVED to, and a prefix is the half
    that decides identity: `fylite:angle_deg` under two IRIs is two unrelated
    properties that merely look alike.  A vocabulary is a term space, not a
    term list, so the space needs a gate of its own.
    """
    import json as _json
    #: ★the key may be BARE — `fyodev.js` and `session.js` write JS object
    #: literals (`fylite: 'urn:fylite:'`), not JSON.  The first version of
    #: this gate required quotes around it, passed, and went on passing when
    #: a divergent IRI was injected into `session.js` to check that it could
    #: fail at all.  The value must be quoted and must look like an IRI, which
    #: is what keeps `'fylite:AppSession/1'` from matching.
    pat = re.compile(r"""["']?fylite["']?\s*:\s*["']([a-z]+:[^"']*)["']""")
    scanned = list(SOURCES) + [ROOT / "python/fylite/_fyo_vocab.json"]
    #: the shipped documents too: a prefix that drifts in DATA is the case
    #: that actually reaches a reader.
    scanned += sorted((ROOT / "machine_desc").rglob("*.json")) \
        + sorted((ROOT / "machine_desc").rglob("*.yaml"))
    found: dict[str, list[str]] = {}
    for p in scanned:
        for iri in pat.findall(p.read_text(encoding="utf-8")):
            found.setdefault(iri, []).append(str(p.relative_to(ROOT)))
    assert found, "no fylite: prefix declaration found at all — check the regex"
    ns = _json.loads((ROOT / "python/fylite/_fyo_vocab.json").read_text())["namespace"]
    assert ns == FYLITE_PREFIX, f"_fyo_vocab.json namespace is {ns!r}"
    assert set(found) <= {FYLITE_PREFIX}, (
        "the fylite: term space is declared under more than one IRI:\n  "
        + "\n  ".join(f"{k} <- {', '.join(sorted(set(v)))}"
                      for k, v in sorted(found.items()))
        + f"\n\nOne term space, one IRI: {FYLITE_PREFIX}.")


#: A write of a shared term, in either of the two ways a host may spell it:
#: the literal, or the generated file's own ``FyNames.q('term')`` helper.
#: ★The helper has to count.  It exists so a host does not spell the prefix
#: itself — and a gate that could not see it would quietly punish the one
#: spelling the vocabulary actually wants.
_WRITES = re.compile(r"""['"]fylite:([a-z_0-9]+)['"]"""
                     r"""|\bq\(\s*['"]([a-z_0-9]+)['"]\s*\)""")


def _by_host() -> tuple[set[str], set[str]]:
    browser: set[str] = set()
    python: set[str] = set()
    for p in SOURCES:
        found = {a or b for a, b in _WRITES.findall(p.read_text())}
        (browser if p.suffix == ".js" else python).update(found)
    return browser, python


#: Terms whose PATH is declared once and generated into both hosts
#: (``rust/fylite/src/fyo.rs`` → ``_fyo_interface.py`` /
#: ``fyo-interface.js``).  ★★They are exempt from the both-hosts rule
#: BELOW, and the exemption is a strengthening rather than a hole: the rule
#: exists because two independent spellings can diverge, and these have one
#: spelling.  A term drops out of this set the moment its path leaves the
#: table, and then the rule binds it again.
def _declared() -> set[str]:
    import re as _re
    text = INTERFACE_PY.read_text()
    return set(_re.findall(r"fylite:([a-z_0-9]+)", text))


def test_every_listed_term_is_actually_written_by_both_hosts():
    """★A vocabulary that outgrows its rule stops meaning anything.

    The entry criterion IS the scope: a term only one host writes is a private
    extension, and listing it would bind code that has no counterpart to
    diverge from.

    ★★Unless its path is DECLARED — generated into both hosts from the
    kernel's own table — in which case there is nothing for two spellings to
    disagree about, which is what this rule was protecting against.
    """
    browser, python = _by_host()
    declared = _declared()
    orphan = sorted(t for t in TERMS
                    if t not in (browser & python) and t not in declared)
    assert not orphan, (
        f"listed but not written by both hosts: {orphan}\n"
        "Either it is a private extension (remove it), or a writer was "
        "removed (remove it too), or its path belongs in the generated "
        "interface table (rust/fylite/src/fyo.rs).")


def test_a_term_that_becomes_shared_must_be_listed():
    """★The other direction — this is how the vocabulary keeps up without
    anyone having to remember to update it."""
    browser, python = _by_host()
    missing = sorted((browser & python) - set(TERMS))
    assert not missing, (
        f"written by both hosts but absent from _fyo_vocab.json: {missing}\n"
        "Add each with a one-line gloss and a `gated` decision — the gloss is "
        "what makes it a vocabulary rather than a list.")
