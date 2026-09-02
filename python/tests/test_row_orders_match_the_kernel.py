"""Every name tuple in ``kernel.py`` still matches the order the kernel uses.

★★What these tuples are.  ``kernel.py`` holds sixteen SCREAMING_CASE tuples.
Fifteen of them are **positional contracts**: the kernel writes a buffer in
one order and Python names the slots in another place, or Python packs an
input block in an order the kernel reads back by index.  Get them out of step
and every field is silently mislabelled — the array is the right length and
full of plausible numbers, so nothing downstream can notice.

★Why the names stay in Python at all.  DE-COMP-02 gives this layer "units and
names"; what it does not give it is the ORDER, which is the kernel's.  So the
right shape is not to move these tuples but to hold them to the kernel's own
write order — which is what this file does.  (The four whose *index is the
wire format* were a different case and did move: see
``test_deck_names_have_one_source.py``.)

★A note on the checking, because it cost three false alarms to get right.  A
naive scan reported ``GEO_SCALARS`` mismatched (it names a deliberate leading
12 of 14), ``FREE_SOLVE_KEYS`` mismatched (slot 11 is a reserved ``0.0``,
correctly named ``_``), and ``SURFACE_KEYS`` wildly wrong (it is an INPUT
block, and the scan was reading an output buffer).  All three were the
checker's fault.  A checker that cries wolf gets muted, so this one extracts
one function body exactly, knows about prefixes and reserved slots, and says
plainly which tuples it cannot verify.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from fylite import kernel as K

C_API = (Path(__file__).resolve().parents[2]
         / "rust" / "fylite" / "src" / "c_api.rs")

pytestmark = pytest.mark.skipif(not C_API.exists(), reason="kernel source absent")
SRC = C_API.read_text() if C_API.exists() else ""


def _fn_body(export: str) -> str | None:
    """One export's body: signature to the closing brace at column 0.

    ★Not a fixed span.  A window that overruns picks up the next function's
    writes, which is what produced a phantom 14-slot ``FREE_SOLVE_KEYS``.
    """
    m = re.search(rf'pub unsafe extern "C" fn fylite_rs_{export}\b', SRC)
    if not m:
        return None
    end = re.compile(r"^\}", re.M).search(SRC, m.end())
    return SRC[m.start():end.end()] if end else None


def _from_loop(body: str, nth: int):
    """``for (k, v) in [&b.x, &b.y, ...]`` — the row-block form."""
    groups = re.findall(r"for \(k, v\) in \[(.*?)\]\.iter\(\)", body, re.S)
    if len(groups) <= nth:
        return None
    return [f.split(".")[-1]
            for f in re.findall(r"&([a-z]\.[a-z_0-9.]+)", groups[nth])]


def _from_indexed(body: str, buf: str):
    """``buf[N] = something;`` at the body's top level."""
    hits = re.findall(rf"(?<![A-Za-z0-9_]){buf}\[(\d+)\]\s*=\s*([^;]+);", body)
    return _collect(hits)


def _from_row(body: str, buf: str):
    """``let row = &mut buf[..]`` then ``row[N] = X.field``."""
    m = re.search(rf"let row = &mut {buf}\[.*?\];(.*?)\n\s*\}}", body, re.S)
    if not m:
        return None
    return _collect(re.findall(r"row\[(\d+)\]\s*=\s*([^;]+);", m.group(1)))


def _collect(hits):
    if not hits:
        return None
    seen: dict[int, str] = {}
    for i, rhs in hits:
        #: `res.psi_axis` -> `psi_axis`; `m.rho[i]` -> `rho`; `0.0` -> `0.0`
        name = re.sub(r"\[i\]$", "", rhs.strip().rstrip(";)"))
        name = name.rsplit(".", 1)[-1] if re.match(r"^[a-z_]+\.", name) else name
        seen.setdefault(int(i), name.split()[0])
    return ([seen[i] for i in range(len(seen))]
            if set(seen) == set(range(len(seen))) else None)


#: tuple -> (export, extractor).  Each is an OUTPUT buffer the kernel fills.
COVERED = {
    "BUNDLE_ROWS":     ("bundle_derive",      lambda b: _from_loop(b, 0)),
    "GYROBOHM_ROWS":   ("bundle_derive",      lambda b: _from_loop(b, 1)),
    "GEO_SCALARS":     ("geo_surface",        lambda b: _from_indexed(b, "o")),
    "FREE_SOLVE_KEYS": ("gs_free_solve",      lambda b: _from_indexed(b, "o")),
    "FREE_SOLVE_TAB_KEYS": ("gs_free_solve_tab",
                            lambda b: _from_indexed(b, "o")),
    "METRIC_ROW":      ("equilibrium_ladder", lambda b: _from_row(b, "om")),
    "MILLER_ROW":      ("equilibrium_ladder", lambda b: _from_row(b, "ok")),
    #: T-A5 — the inverse solve's coil-fitting entry.  Same `o[N] = ...`
    #: shape as the free solve, and it needs its own tuple rather than
    #: borrowing `FREE_SOLVE_KEYS`: the free solve packs an X-point into
    #: slots 7-8 and this one packs the feedback amplitude and the coil
    #: diagnostics there.
    "INVERSE_COIL_KEYS": ("gs_inverse_solve_coils",
                          lambda b: _from_indexed(b, "o")),
    #: ★★The plain inverse entry, and the pair that made the case for it.
    #: `gs_inverse_solve` used to borrow `FREE_SOLVE_KEYS`, and a SHARED
    #: tuple is exactly what this file cannot check: it was verified against
    #: `gs_free_solve`, where it is right, while the same names sat over the
    #: inverse's different write order — `res["xpt_r"]` carrying fb_amp and
    #: `res["fb_amp"]` a hard 0.0, on every delivered reconstruction.  One
    #: tuple per export is the invariant; these two restore it.
    "INVERSE_KEYS":     ("gs_inverse_solve", lambda b: _from_indexed(b, "o")),
    "INVERSE_FSA_KEYS": ("gs_inverse_solve_fsa",
                         lambda b: _from_indexed(b, "o")),
}

#: Everything else, with the reason it is not checked HERE.  An entry that is
#: merely inconvenient does not belong on this list.
#: ★★``ZEROD_PARAMS`` was here, as "an INPUT block, same reason" — and
#: that reason was true and was not the whole story: an input block the
#: kernel reads back by index is exactly the shape that CANNOT be checked
#: from this side, so it sat unchecked while its order was spelled in three
#: places (this tuple and two ``par[0]..par[9]`` blocks in ``c_api.rs``).
#: It is now DECLARED once (``rust/fylite/src/fyo.rs``) and generated into
#: both hosts, so it is no longer a hand-kept tuple and drops out of this
#: file's scope entirely — which is the outcome this list is for.  See
#: ``test_fyo_interface.py``.
UNCHECKED = {
    "SURFACE_KEYS": "an INPUT block — Python packs it, the kernel reads it "
                    "back by index; checking it needs the reader, not a "
                    "write buffer",
    "MXH_HARMONICS": "an input row order AND the suffix of an output dict; "
                     "the kernel copies the block wholesale, so there is no "
                     "per-slot write to read",
    "REDL_INPUT_ROWS": "written through a helper that fills rows by loop "
                       "index rather than by name",
    "GEO_SHAPE_KEYS": "used as a SET for validation, never positionally",
    #: ★TX-4's three key tuples are INPUT blocks, exactly `SURFACE_KEYS`'
    #: case: Python packs `geometry`/`params`/`state` and the kernel reads
    #: them back by index, so checking them needs the READER and not a write
    #: buffer.  Named here rather than left off the list, because the
    #: completeness test below is what stops that from happening silently.
    "LENGYEL_GEOMETRY_KEYS": "an INPUT block — same case as SURFACE_KEYS",
    "LENGYEL_SOL_KEYS": "an INPUT block — same case as SURFACE_KEYS",
    "LENGYEL_STATE_KEYS": "an INPUT block — same case as SURFACE_KEYS",
    #: ★not positional at all: the species crosses the ABI as a UTF-8
    #: SYMBOL (`fylite_rs_edge_noncoronal` takes `symbol`/`symbol_len`), so
    #: the tuple is a vocabulary and its order carries nothing
    "EDGE_SPECIES": "crosses the ABI as a symbol string, never as an index",
}

#: tuple -> (pattern over c_api.rs, what the match arms are).  These three
#: ARE positional — the index is the wire format — and the kernel decodes
#: them with a numbered `match`, which is readable, so they get checked
#: rather than waived.
CODED = {
    "ICRH_MINORITY": r"(\d+) => Minority::(\w+)",
    "ICRH_GAS": r"(\d+) => MainGas::(\w+)",
}

#: ★The index-is-wire-format vocabularies are absent from both lists on
#: purpose: they are no longer written as literals here at all — they are
#: bound to the generated tables, so the scan below does not see them and
#: `test_deck_names_have_one_source.py` owns them.  This comment exists
#: because "why is WAVEFORMS not listed" is the first question a reader has.
#:
#: ★★``TGLF_SPECIES_ROWS`` and ``NEO_SPECIES_ROWS`` joined them on
#: 2026-08-21.  The first WAS listed above, waived as a "lower-case mirror of
#: the generated TGLF_DECK_SPECIES" — and a mirror is what it was: typed out
#: by hand, agreeing by luck.  It is derived now, so the waiver goes with the
#: literal.  The second is new, and exists because three call sites were
#: spelling NEO's six species fields out instead of reading one table.


@pytest.mark.parametrize("name", sorted(CODED))
def test_the_coded_vocabularies_decode_to_the_same_names(name: str):
    """★These tuples' INDEX is the wire format: Python sends
    ``ICRH_MINORITY.index("He3")`` and the kernel decodes ``3`` with a
    numbered match.  Insert a name in the middle of either side and every
    later species is silently the wrong one — a run with He4 physics
    labelled He3 finishes and looks fine.

    Compared case-insensitively because the two sides spell the same thing
    in their own conventions (``He3`` against ``He3``, ``DT`` against
    ``DT``); what is checked is the ORDER.
    """
    arms = re.findall(CODED[name], SRC)
    assert arms, f"{name}: no numbered match arms found in c_api.rs"
    rust = [v for _, v in sorted(arms, key=lambda kv: int(kv[0]))]
    assert [int(k) for k, _ in sorted(arms, key=lambda kv: int(kv[0]))] \
        == list(range(len(arms))), f"{name}: the kernel's codes are not 0..N"
    py = [n.lower() for n in getattr(K, name)]
    assert py == [n.lower() for n in rust], (
        f"{name} is out of step with the kernel's decoder:\n"
        f"  Python: {list(getattr(K, name))}\n  kernel: {rust}")


def test_the_lengyel_outcome_codes_decode_to_the_same_names():
    """★Same shape, different spelling: the kernel writes an outcome as a
    float code and Python names it by index.  The two sides use different
    case conventions, so the comparison strips underscores and case."""
    arms = re.findall(r"PhysicsOutcome::(\w+) => (\d+)\.0", SRC)
    assert arms, "no PhysicsOutcome arms found in c_api.rs"
    rust = [n for n, _ in sorted(arms, key=lambda kv: int(kv[1]))]
    flat = lambda s: s.replace("_", "").lower()  # noqa: E731
    assert [flat(n) for n in K.LENGYEL_OUTCOMES] == [flat(n) for n in rust], (
        f"Python: {list(K.LENGYEL_OUTCOMES)}\n  kernel: {rust}")


@pytest.mark.parametrize("name", sorted(COVERED))
def test_the_python_names_match_the_kernel_write_order(name: str):
    export, extract = COVERED[name]
    body = _fn_body(export)
    assert body, f"fylite_rs_{export} not found — has the export been renamed?"
    rust = extract(body)
    assert rust, (
        f"could not read {name}'s write order out of fylite_rs_{export}. "
        "The checker is now blind here: either restore a readable write "
        "pattern or move this tuple to UNCHECKED with the reason.")

    py = tuple(getattr(K, name))
    assert len(py) <= len(rust), (
        f"{name} names {len(py)} slots but the kernel writes {len(rust)}")

    bad = []
    for i, (want, got) in enumerate(zip(rust, py)):
        #: ★a slot the kernel fills with a literal is reserved padding, and
        #: naming it `_` is right — `gs_free_solve`'s slot 11 is `0.0`
        if got == "_" and not re.match(r"^[a-z_]", want):
            continue
        if want != got:
            bad.append(f"slot {i}: kernel writes {want!r}, Python calls it {got!r}")
    assert not bad, (
        f"{name} is out of step with fylite_rs_{export}:\n  "
        + "\n  ".join(bad)
        + "\n\nEvery field from the first mismatch on is mislabelled, and the "
          "array is still the right length and full of plausible numbers.")


def test_the_miller_slot_names_match_the_slots_the_kernel_actually_reads():
    """★★Tie the DECLARATION to the READER.

    ``TGLF_MILLER_SLOTS`` is generated, so the host cannot drift from it —
    but the const itself can drift from ``fylite_rs_tglf_units``, which reads
    ``rmin: g[0], rmaj: g[1], ...``.  Nothing checked that, and a probe that
    swapped two names in the const stayed green: the generated table and its
    consumer moved together, which is what generation is FOR and also why it
    cannot be its own witness.

    The tie is a prefix match — ``rmin`` against ``RMIN_LOC``, ``q`` against
    ``Q_LOC``, ``ms`` against ``MS`` — which holds for all fourteen and goes
    red the moment two slots trade places, because ``q`` is not a prefix of
    ``kappa_loc``.
    """
    from fylite import _deck_names

    body = _fn_body("tglf_units")
    assert body, "fylite_rs_tglf_units not found"
    reads = re.findall(r"([a-z_0-9]+):\s*g\[(\d+)\]", body)
    assert reads, "could not read the Miller slot assignments"
    by_slot = {int(i): f for f, i in reads}

    slots = tuple(_deck_names.TGLF_MILLER_SLOTS)
    assert set(by_slot) == set(range(len(slots))), (
        f"kernel reads slots {sorted(by_slot)} but the table names "
        f"{len(slots)}")

    bad = [f"slot {i}: kernel reads {by_slot[i]!r}, table calls it {name!r}"
           for i, name in enumerate(slots)
           if not name.lower().startswith(by_slot[i])]
    assert not bad, (
        "TGLF_MILLER_SLOTS disagrees with fylite_rs_tglf_units:\n  "
        + "\n  ".join(bad)
        + "\n\nEvery slot from the first mismatch on feeds the wrong "
          "geometry field, and the block is still 14 plausible floats.")


def test_the_neo_sauter_slots_match_the_slots_the_kernel_reads():
    """★★NEO's block order, tied to its reader — the same tie TGLF has.

    ``NEO_SAUTER_SLOTS`` and ``NEO_DECK_GEOMETRY`` share a vocabulary and
    differ in sequence.  Building ``geo14`` from the DECK order instead of
    the block order produced fluxes 200x out, and it read as a physics
    disagreement rather than a transposition: every value finite, ordered
    and plausible.  That is what this ties down.
    """
    from fylite import _deck_names

    body = _fn_body("neo_sauter")
    assert body, "fylite_rs_neo_sauter not found"
    reads = re.findall(r"([a-z_0-9]+):\s*g\[(\d+)\]", body)
    assert reads, "could not read the geo14 slot assignments"
    by_slot = {int(i): f for f, i in reads}

    slots = tuple(_deck_names.NEO_SAUTER_SLOTS)
    assert set(by_slot) == set(range(len(slots)))
    bad = [f"slot {i}: kernel reads {by_slot[i]!r}, table calls it {name!r}"
           for i, name in enumerate(slots)
           if not name.lower().startswith(by_slot[i].rstrip("_"))]
    assert not bad, "NEO_SAUTER_SLOTS disagrees with the reader:\n  " + "\n  ".join(bad)


def test_the_two_neo_geometry_orders_are_kept_apart():
    """★They must not become equal: one is what a deck spells, the other what
    ``neo_sauter`` reads by index."""
    from fylite import _deck_names
    deck = tuple(_deck_names.NEO_DECK_GEOMETRY)
    block = tuple(_deck_names.NEO_SAUTER_SLOTS)
    assert deck != block[:len(deck)], (
        "the NEO deck order and the neo_sauter block order have converged — "
        "one of the two call sites is now being handed the other's layout")
    assert len(set(deck) & set(block)) >= 12


def test_the_flux_inputs_struct_is_assembled_in_exactly_one_place():
    """★★``FluxInputs`` has forty-odd fields filled from flat blocks by index.

    A second literal assembly — the obvious way to add an entry that starts
    from a surface rather than a deck — is the shape that drifts silently:
    every field is a plausible float, so a transposed pair changes the answer
    and nothing raises.  The blocks are already checked against their readers
    elsewhere in this file; this checks that there is only one reader to
    check.

    The production assembly lives in ``flux_inputs_from_blocks``.  Test
    helpers inside ``#[cfg(test)]`` are not production and are not counted.
    """
    gf = C_API.parent / "gyrofluid.rs"
    assert gf.exists(), "gyrofluid.rs missing"

    #: `c_api.rs` has no `#[cfg(test)]` module, so every hit there is
    #: production; in `gyrofluid.rs` only the struct definition should
    #: appear outside the test module.
    #: ★`-> gf::FluxInputs {` is a RETURN TYPE, not an assembly.  Counting
    #: it made the builder itself look like a second filling — the check
    #: failing on the very refactor that satisfies it.
    api_hits = [ln for ln in SRC.splitlines()
                if "gf::FluxInputs {" in ln and "->" not in ln]
    assert len(api_hits) == 1, (
        f"{len(api_hits)} assemblies of FluxInputs in c_api.rs — there must "
        "be one.  A new entry reaches the struct through "
        "flux_inputs_from_blocks, not by filling it again:\n  "
        + "\n  ".join(h.strip() for h in api_hits))

    gf_src = gf.read_text()
    cut = gf_src.find("#[cfg(test)]")
    production = gf_src[:cut] if cut != -1 else gf_src
    lits = [ln for ln in production.splitlines()
            if "FluxInputs {" in ln and "pub struct" not in ln]
    assert not lits, (
        "gyrofluid.rs assembles FluxInputs outside its test module:\n  "
        + "\n  ".join(l.strip() for l in lits))


def test_every_tuple_is_either_checked_or_explained():
    """★The completeness half.  Without it this file silently covers six of
    sixteen while reading like it covers the contract.
    """
    declared = set(re.findall(r"^([A-Z][A-Z_0-9]{3,}) = \(", 
                              (Path(K.__file__)).read_text(), re.M))
    accounted = set(COVERED) | set(CODED) | set(UNCHECKED) | {"LENGYEL_OUTCOMES"}
    missing = sorted(declared - accounted)
    assert not missing, (
        "kernel.py declares name tuples this file neither checks nor "
        f"explains: {missing}\n\nAdd each to COVERED (with the export it "
        "belongs to) or to UNCHECKED (with the reason it cannot be read).")
    stale = sorted(accounted - declared)
    assert not stale, f"listed here but no longer declared in kernel.py: {stale}"
