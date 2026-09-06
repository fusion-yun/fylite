"""The machine has ONE source: the device document under ``$FYLITE_DEVICE_DIR``.

★★**Why this exists.**  Until now it had two.  Geometry, diagnostic positions,
channel map, limiter and grid all came from the fyo device document — and then
:func:`fylite.scenario.analysis.recon_rs.reconstruct` read one more thing out
of a binary Green deck: ``rfcoil.ddd``'s ``rsilfc``, the coil→loop response it
subtracts from the flux-loop readings.  That single read was the gate on the
whole Python reconstruction path.  This distribution ships no ``rfcoil.ddd``,
the read was unconditional and happened before the first kernel call, so every
input — measurement dict, IMAS document, shot number — raised
``MachineDataMissing`` there.  「Zero the coil currents to get past it」 does
not work either: arithmetic that would come out zero is not code that is
skipped.

The rows are computed now (``recon_rs.coil_loop_rows``, the same
``channel_response``/2π the browser has always used), and with them the last
reader of a response table left the live path.  What remains to keep is the
STATE: two things that used to name a second machine source must not come
back.

  * **No live caller of a Green response table.**  ``coil_response_tables``
    and ``vessel_response_tables`` stay as READERS — they are how a deck that
    has one can be cross-checked against the geometry (``vessel_table_check``)
    — but nothing on a path that computes may call them.
  * **No entry point takes a table directory.**  ``table_dir`` was threaded
    through the analysis, design, control and model lines, and by the end not
    one of them read it: it survived as a parameter that says the machine can
    come from somewhere else while every face resolves the document.  A
    parameter like that is not inert — it is the shape a second source grows
    back into.

★These are SOURCE assertions on purpose.  Both failures are silent at run
time: a re-added read fails only where a deck is missing, and a re-added
parameter simply gets ignored.
"""
from __future__ import annotations

import ast
from pathlib import Path

import fylite

PKG = Path(fylite.__file__).resolve().parent
#: where the readers themselves live — the definitions are not the offence
READERS = ("coil_response_tables", "vessel_response_tables")


def _modules():
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _called_names(tree):
    """Every name a call site uses, ``f(...)`` and ``m.f(...)`` alike."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                yield f.id, n.lineno
            elif isinstance(f, ast.Attribute):
                yield f.attr, n.lineno


def test_no_live_caller_reads_a_green_response_table():
    """★The reconstruction's coil rows are computed; nothing calls the deck.

    A caller here is what made this distribution's reconstruction path
    unusable — and it would not fail on a machine that HAS the deck, which is
    exactly how it survived so long.
    """
    hits = {}
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name, line in _called_names(tree):
            if name in READERS:
                hits.setdefault(str(path.relative_to(PKG)), []).append((name, line))
    assert not hits, (
        f"a Green response table is read on a live path again: {hits}.  The "
        "coil→loop and coil→probe rows are the kernel's (code/coilshare · "
        "code/vstab · code/reconstruction, the oracle tree's recon_rows); the readers "
        "exist for cross-checking a deck that has one, not for computing "
        "with.")


def test_no_entry_point_takes_a_table_directory():
    """★★One machine source means one argument for it — and it is not a path.

    ``table_dir`` named the Green-table directory.  Every face that took one
    had already stopped reading it; what it still did was let a caller believe
    the machine could be pointed somewhere else, and let an eagerly-resolved
    default (``table_dir or data_dir()``) look exactly like an explicit
    override — which is how the fyo document was shut out of the design and
    control lines while nothing said so.
    """
    offenders = {}
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = n.args
            names = [x.arg for x in (list(a.posonlyargs) + list(a.args)
                                     + list(a.kwonlyargs))]
            if "table_dir" in names:
                offenders.setdefault(str(path.relative_to(PKG)), []).append(
                    (n.name, n.lineno))
    assert not offenders, (
        f"an entry point takes a table directory again: {offenders}.  The "
        "machine is the device document behind $FYLITE_DEVICE_DIR; a path "
        "parameter beside it is a second source that no face reads.")
