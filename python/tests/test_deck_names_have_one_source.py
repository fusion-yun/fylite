"""No host spells a generated deck-name order by hand.

★★What this is guarding.  ``rust/build.sh`` publishes the upstream deck-name
orders from the kernel into both hosts (``_deck_names.py``,
``deck-names.json``).  A batch later, five hand-written copies were still in
the Python layer — the NEO deck's species set was **byte-for-byte** the
generated ``NEO_DECK_SPECIES``, and TGLF's species order was written out
three more times in ``gyrofluid.py`` plus once in ``mapping.py``.

The shared artifact existed and the hosts kept their own anyway.  That is not
a tidiness problem: the TGLF tuples are a **positional contract** — the ABI
takes the arrays as separate pointers, so a caller's tuple order has to match
the C parameter order or every species field is quietly the wrong one, with
no shape or type able to catch it.  Four spellings is four chances to
transpose two names.

So: if the kernel publishes an order, a host reads it.  A literal that
reproduces a generated table is the thing this test fails on, whether or not
it currently agrees — agreeing today is what a copy does right up until it
does not.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fylite import _deck_names

PKG = Path(_deck_names.__file__).resolve().parent

#: {frozenset of names: the table that publishes them}
TABLES = {name: tuple(getattr(_deck_names, name))
          for name in dir(_deck_names) if name.isupper()}

assert TABLES, "no generated deck tables — has rust/build.sh stopped running?"

SOURCES = sorted(p for p in PKG.rglob("*.py")
                 if p.name not in ("_deck_names.py",))


def _literal_name_groups(tree: ast.AST):
    """Every literal tuple/list/set of identifier-ish strings, with its line.

    ★★Case-INSENSITIVE, and that is the fix this function needed.  It used to
    require ``v.isupper()``, on the reasoning that deck names are
    SCREAMING_CASE — true of the deck, but not of a host that copies one.
    ``neoclassical.GEO_KEYS`` was ``NEO_DECK_GEOMETRY`` lowercased, a
    hand-typed copy of a positional contract, and it sat in plain sight of
    this test for as long as it existed: the one gate written to find exactly
    that could not see it because of capitalisation.

    The cost of widening is a few more candidate tuples to compare against
    the tables, which is nothing; the cost of not widening was a whole class
    of copy going unchecked.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            continue
        vals = [e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if len(vals) < 3 or len(vals) != len(node.elts):
            continue
        if all(v and v.replace("_", "").isalnum() and not v[0].isdigit()
               for v in vals):
            yield node.lineno, vals


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_host_reproduces_a_generated_deck_order(path: Path):
    bad = []
    for lineno, vals in _literal_name_groups(ast.parse(path.read_text())):
        low = [v.lower() for v in vals]
        for table, names in TABLES.items():
            lown = [n.lower() for n in names]
            #: an exact order, or the same set in another order — both are
            #: the copy this rule is about; compared case-folded, so a
            #: lowercased copy is the same finding as a verbatim one
            if low == lown or set(low) == set(lown):
                bad.append(f"line {lineno}: reproduces {table} "
                           f"({'same order' if low == lown else 'REORDERED'})")
    assert not bad, (
        f"{path.name} spells a generated deck order by hand:\n  "
        + "\n  ".join(bad)
        + "\n\nImport it from fylite._deck_names instead.  These orders are a "
          "positional contract with the ABI; a second spelling is a second "
          "chance to transpose two names, and nothing downstream can catch it.")


def test_the_generated_tables_are_actually_reaching_their_consumers():
    """★The positive half.  Every check above is satisfied by a host that
    stopped using the names at all, so pin the live consumers by name.
    """
    from fylite.scenario.model import gyrofluid
    from fylite import kernel

    #: ★★It pinned ``gacode._VECTOR_KEYS``, and that name was DEAD — nothing
    #: in this package called the splitter it belonged to, in that commit or
    #: the one before.  So this case was doing precisely what its own
    #: docstring warns the checks above can be fooled by: agreeing with a
    #: host that had stopped using the names.  It pinned a NAME, not a use.
    #:
    #: The live consumer of the NEO species order is the kernel's row table,
    #: which every NEO call unpacks BY POSITION on the other side of the ABI.
    assert kernel.NEO_SPECIES_ROWS == tuple(
        n.lower() for n in _deck_names.NEO_DECK_SPECIES)
    #: ★★And it happened AGAIN, one module over: this line pinned
    #: ``gyrofluid._VECTOR_KEYS``, which existed only to feed
    #: ``gyrofluid._split_index`` — a splitter with no caller in the package,
    #: the identical dead trio already removed from ``io.gacode``.  So the
    #: case was once more agreeing with a host that had stopped using the
    #: names, under a docstring recording that it had been fixed for exactly
    #: that.  A name a test pins is not a use; pin the CALL.
    #:
    #: The live consumer of the rotating species order is ``_species``,
    #: which reads it POSITIONALLY into the arrays both ported entries send
    #: across the ABI.  Asked for a deck with every rotating row present, it
    #: must return one row per name, in that order.
    ns = 2
    deck = {f"{name}_{i + 1}": float(j)
            for j, name in enumerate(_deck_names.TGLF_DECK_SPECIES_ROTATING)
            for i in range(ns)}
    rows = gyrofluid._species(deck, _deck_names.TGLF_DECK_SPECIES_ROTATING, ns)
    assert [r[0] for r in rows] == [
        float(j) for j in range(len(_deck_names.TGLF_DECK_SPECIES_ROTATING))]
    assert tuple(kernel.TGLF_DECK_SPECIES) == tuple(
        _deck_names.TGLF_DECK_SPECIES)


def test_every_generated_table_is_a_tuple_of_strings():
    """★A one-name vocabulary is where a generator quietly stops making
    tuples.  ``("fisch")`` is a STRING, and ``.index(x)`` on it answers 0 for
    the only valid value — so the selector keeps working while
    ``list(...)`` prints the letters of the name.  This caught exactly that.
    """
    bad = []
    for name, table in TABLES.items():
        if not isinstance(table, tuple):
            bad.append(f"{name}: {type(table).__name__}, not tuple")
        elif not all(isinstance(x, str) for x in table):
            bad.append(f"{name}: not all strings")
    assert not bad, "\n".join(bad)


def test_the_index_vocabularies_still_decode_the_way_the_kernel_reads_them():
    """★The four whose INDEX is the wire format, pinned against the kernel's
    own decode order.  These are not deck names: the host looks a name up and
    sends its position, so a reorder on either side silently selects a
    different thing and returns a plausible array.
    """
    from fylite import kernel

    assert tuple(kernel.WAVEFORMS) == ("trapezoid", "ip", "ne", "te",
                                       "actuator", "phase"), (
        "c_api's `match which` reads 0 trapezoid, 1..=3 centre, 4 actuator, "
        "5 phase")
    assert tuple(kernel.PHASE_NAMES) == ("breakdown", "rampup", "flattop",
                                         "rampdown"), (
        "zerod::phase_label returns 0 breakdown .. 3 rampdown")
    assert tuple(kernel.TAU_LAWS) == ("ipb98y2", "iter89p"), (
        "zerod::TauLaw::from_index maps 0 Ipb98y2, 1 Iter89p")
    assert tuple(kernel.LH_EFFICIENCY_MODELS) == ("fisch",)
    #: and they are the generated tables, not a second spelling that agrees
    assert tuple(kernel.WAVEFORMS) == tuple(_deck_names.WAVEFORM_NAMES)
    assert tuple(kernel.PHASE_NAMES) == tuple(_deck_names.PHASE_NAMES)
    assert tuple(kernel.TAU_LAWS) == tuple(_deck_names.TAU_LAW_NAMES)
    assert tuple(kernel.LH_EFFICIENCY_MODELS) == tuple(
        _deck_names.LH_EFFICIENCY_MODEL_NAMES)


def test_the_miller_slots_carry_a_default_for_every_slot():
    """★The Miller block is a 14-slot positional read; the kernel owns the
    ORDER and the host owns the DEFAULTS, so the one way they can fall out of
    step is a slot with no default.  ``_MILLER_DEFAULTS[k]`` would raise —
    but only on the deck that omits that key, which may be nobody's for
    months.
    """
    from fylite.scenario.model import gyrofluid

    slots = tuple(_deck_names.TGLF_MILLER_SLOTS)
    assert tuple(k for k, _ in gyrofluid._MILLER_KEYS) == slots
    missing = [k for k in slots if k not in gyrofluid._MILLER_DEFAULTS]
    assert not missing, f"slots with no default: {missing}"
    extra = [k for k in gyrofluid._MILLER_DEFAULTS if k not in slots]
    assert not extra, f"defaults for slots the kernel does not read: {extra}"


def test_the_two_tglf_geometry_orders_are_kept_apart():
    """★★They share a vocabulary and differ in order, which is exactly the
    pair a reader collapses by mistake.  ``TGLF_DECK_GEOMETRY`` is the order
    ``tglf_local`` RETURNS values in; ``TGLF_MILLER_SLOTS`` is the order
    ``tglf_units`` READS them.  If they are ever made equal, one of the two
    call sites is being fed the other's layout.
    """
    ret = tuple(_deck_names.TGLF_DECK_GEOMETRY)
    read = tuple(_deck_names.TGLF_MILLER_SLOTS)
    assert ret != read, (
        "the two TGLF geometry orders have become identical — one of "
        "tglf_local / tglf_units is now being handed the other's layout")
    #: and they really are two views of one vocabulary, not unrelated lists
    assert len(set(ret) & set(read)) >= 10


def test_the_two_four_name_species_subsets_stay_distinct():
    """★★They share three of four names and go to different ABI entries.

    ``TGLF_DECK_SPECIES_KYGRID`` is ``(ZS, MASS, AS, TAUS)`` for
    ``tglf_kygrid``; ``TGLF_DECK_SPECIES_PRESSURE`` is
    ``(AS, TAUS, RLNS, RLTS)`` for ``tglf_dlnpdr``.  Neither is a prefix of
    the full order, and each is exactly the tuple someone reaches for when
    writing the other's call.
    """
    kg = tuple(_deck_names.TGLF_DECK_SPECIES_KYGRID)
    pr = tuple(_deck_names.TGLF_DECK_SPECIES_PRESSURE)
    assert kg != pr, "the two four-name subsets have become identical"
    assert len(set(kg) & set(pr)) == 2, (
        f"the overlap changed: {sorted(set(kg) & set(pr))} — one of the two "
        "call sites may now be fed the other's arrays")


def test_the_kygrid_subset_is_a_prefix_of_the_full_order():
    """★Not decoration: the four-name kygrid form and the eight-name form are
    passed to different ABI entries, and the subset only stays correct while
    it is the *leading* four.  If someone reorders the full tuple, this is
    what notices.
    """
    full = tuple(_deck_names.TGLF_DECK_SPECIES_ROTATING)
    assert tuple(_deck_names.TGLF_DECK_SPECIES_KYGRID) == full[:4]
    assert tuple(_deck_names.TGLF_DECK_SPECIES) == full[:6]


# --------------------------------------------------------------------------- #
# The TGYRO boundary's constants
# --------------------------------------------------------------------------- #
def test_no_host_redeclares_a_kernel_cgs_constant():
    """★★A physical constant with two hosts is worse than a name order with
    two spellings, because nothing downstream can tell them apart.

    ``mapping.py`` declared ``MD`` and ``ME`` with the same values as
    ``mapping.rs``'s ``cgs`` module.  Its own comment had already worked out
    why that is bad — four others "sat beside them and were read by nothing …
    each indistinguishable from a live one — so the next correction lands on
    whichever the reader happens to open, and no test can fail" — and then
    left three of them, the LIVE ones, in place.

    The set is generated into :mod:`fylite._cgs` from the kernel now.  This
    fails on any package module that writes one of those values as a literal
    again, whatever it calls it: the value is the thing that must not be
    duplicated, not the name.
    """
    import ast
    from fylite import _cgs

    vals = {v: k for k, v in vars(_cgs).items()
            if isinstance(v, float) and not k.startswith("_")}
    assert vals, "fylite/_cgs.py declares no constants — did the build run?"
    bad = []
    for f in SOURCES:
        if f.name == "_cgs.py":
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Constant)
                    and isinstance(node.value, float)
                    and node.value in vals):
                bad.append(f"{f.name}:{node.lineno} {node.value!r} "
                           f"(= _cgs.{vals[node.value]})")
    assert not bad, (
        "a kernel CGS constant is written out again:\n  " + "\n  ".join(bad)
        + "\n\nImport it from fylite._cgs — it is generated from "
          "rust/fylite/src/mapping.rs, which is where it is corrected.")


def test_the_browser_species_table_is_the_kernel_declaration():
    """★★The atomic data has ONE declaration (``sources.rs``
    ``@species-table ADAS_ZA``) and BOTH hosts now read it.

    It used to be two literals in ``app/assets/fylite.js`` and nothing at all
    in Python — so a Python caller naming an impurity could not say what it
    weighed, and the browser's copy could drift from a charge the
    bremsstrahlung term squares.  This holds the two generated copies against
    each other and refuses a return to a handwritten table.
    """
    import re
    from fylite import _deck_names as D

    root = Path(__file__).resolve().parents[2]
    js = (root / "app/assets/fylite.js").read_text(encoding="utf-8")
    assert "var ABI_EXPECT = root.FyVersion.abi" in js, (
        "fylite.js no longer reads the generated ABI — a hand-kept literal "
        "there has drifted before (the provenance ledger records a v62 "
        "binary committed against a v66 declaration)")
    assert "var ADAS_Z = root.FyDeck.ADAS_Z" in js, (
        "fylite.js no longer reads the generated species table — if it went "
        "back to a literal, that is a ratchet going the wrong way")
    for which in ("Z", "A"):
        assert not re.search(r"var ADAS_" + which + r" = \{", js), (
            f"fylite.js carries a handwritten ADAS_{which} again")

    gen = (root / "app/assets/deck-names.js").read_text(encoding="utf-8")
    got = {}
    for which in ("Z", "A"):
        m = re.search(r"D\.ADAS_" + which + r" = \{(.*?)\n  \};", gen, re.S)
        assert m, f"deck-names.js has no ADAS_{which} — run rust/build.sh"
        got[which] = {k: float(v) for k, v in
                      re.findall(r"(\w+):\s*([\d.]+)", m.group(1))}
    assert got["Z"] == D.ADAS_Z, {
        "only in the browser": sorted(set(got["Z"]) - set(D.ADAS_Z)),
        "only in Python": sorted(set(D.ADAS_Z) - set(got["Z"])),
        "disagree": {k: (got["Z"][k], D.ADAS_Z[k]) for k in
                     set(got["Z"]) & set(D.ADAS_Z)
                     if got["Z"][k] != D.ADAS_Z[k]}}
    assert got["A"] == D.ADAS_A


def test_the_generated_vocabularies_load_before_their_reader():
    """★A page (or the worker) that forgot the generated script would reach
    `fylite.js`'s throw — loudly, but only at runtime.  This says it at
    build time, for every host that loads the reader."""
    root = Path(__file__).resolve().parents[2]
    worker = (root / "app/assets/worker.js").read_text(encoding="utf-8")
    #: ★the CALL, not the file: the header comment names `fylite.js` long
    #: before the import list does, and slicing from zero compared a comment
    #: with an import
    at = worker.index("importScripts(")
    imports = worker[at:worker.index(");", at)]
    #: ★BOTH generated files the binding reads: the vocabularies and the ABI
    #: it must expect.  `fylite.js` throws on either being absent rather than
    #: running with an empty table or an unknown ABI.
    for gen in ("'version.js'", "'deck-names.js'"):
        assert imports.index(gen) < imports.index("'fylite.js'"), gen
    for page in sorted((root / "app/pages").glob("*.html")):
        html = page.read_text(encoding="utf-8")
        if "assets/fylite.js" not in html:
            continue
        for gen in ("assets/version.js", "assets/deck-names.js"):
            assert html.index(gen) < html.index("assets/fylite.js"), \
                f"{page.name}: {gen}"
    #: ★★AND THE NODE HARNESSES, which this gate claimed to cover and did
    #: not.  Four gates (`validate-geqdsk` / `-limits` / `-q` / `-em-hosts`)
    #: build their own host: they read `app/assets/*.js` off disk and run it
    #: in a `vm` context, so they are hosts in exactly the sense that matters
    #: here — and all four died at load the day `fylite.js` started reading
    #: `version.js`, because "every host" meant the worker and the pages.
    #: A claim about every host has to enumerate them from the tree.
    #: (six since T-4 第二十刀: `validate-fyphys-miller.mjs` builds its own host too)
    harness = []
    for mjs in sorted((root / "app/tests").glob("*.mjs")):
        src = mjs.read_text(encoding="utf-8")
        #: the ones that LOAD THE FILE THEMSELVES.  A gate that hands the
        #: browser a URL (`page.addScriptTag`) is served by the page's own
        #: markup, which the loop above already holds.
        if "vm.runIn" not in src or "'fylite.js'" not in src:
            continue
        harness.append(mjs.name)
        for gen in ("'version.js'", "'deck-names.js'"):
            assert gen in src and src.index(gen) < src.index("'fylite.js'"), \
                (f"{mjs.name} loads fylite.js without {gen} before it — "
                 "the binding throws on a missing generated file, so this "
                 "harness dies at load rather than at its first assertion")
    #: ★the count is asserted so that a harness DELETED or renamed shows up
    #: here as a change to argue about, rather than as a loop that silently
    #: found nothing to check (measured 2026-08-26: four)
    #: ★2026-09-05 起是**五**个：`validate-kernel-api.mjs` 也自建宿主——它比的是
    #: 同一批内核调用走 `/api/kernel` 与走 wasm 的结果（当天用户裁定：webui 的算力
    #: 由 api 端提供，只静态网页走 wasm），所以它同样要先加载那两份生成文件。
    #: ★同日稍后是**六**个：`validate-fyo-tree.mjs`（W-1，页面这一侧的树门）也自建宿主，
    #: 它在真 wasm 上敲 `fylite_rs_fyo_tree`，先要 `fylite.js` 的 ABI 检查过。
    assert len(harness) == 6, harness
    #: ★6 → 5 on 2026-09-06 (T-4 第十二刀): `validate-limits.mjs` retired — it had driven the
    #: flat design-criteria wrappers, dead since T-4 第一刀; `validate-worker-design.mjs`
    #: and the kernel repository's `test_zerod_code.py` hold what it held
