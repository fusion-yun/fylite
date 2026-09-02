"""Every `app/tests/*.mjs` gate's PYTHON half must still import and resolve.

★★Why this exists.  On 2026-08-20 the whole `app/` browser gate suite was
found unrunnable: **nine** stale imports across **six** files, left by
**five** different refactors (ABI 67 -> 72) — `fylite.geqdsk`, `fylite.geo`,
`fylite.breakdown`, `fylite.rustlib`, `fylite.tglf`, `fylite.stability`,
`fylite.zerod`.  Modules moved; the gates did not follow.

Nobody noticed for four ABI versions, and the reason is the whole lesson:
**those gates are node scripts that nothing invokes.**  Most need Playwright
and a served site, so they never ran in the loop that runs on every change.
A gate that cannot start reports nothing — and reports it silently, which
reads exactly like passing.

This test cannot drive a browser, and does not try to.  It checks the one
thing that broke every time and needs no browser at all: that the modules
and attributes each gate's embedded Python names still exist.  That is
cheap, it runs in the default tier, and it would have caught all nine.
"""
from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

GATES = sorted((Path(__file__).resolve().parents[2] / "app/tests").glob("*.mjs"))

#: `from X import a, b` / `import X` inside the JS template literals that hold
#: each gate's Python.  Deliberately a regex over the raw text: the Python is
#: embedded in JS, so it cannot be parsed as a module.
_IMPORT = re.compile(
    r"^\s*(?:from\s+(fylite[\w.]*)\s+import\s+([^\n#]+)|import\s+(fylite[\w.]*))",
    re.M)


def _imports(text: str):
    for m in _IMPORT.finditer(text):
        if m.group(3):
            yield m.group(3), []
            continue
        names = [n.strip().split(" as ")[0].strip()
                 for n in m.group(2).split(",")]
        yield m.group(1), [n for n in names if n and n.isidentifier()]


assert GATES, "no app/tests/*.mjs found — has the suite moved?"


@pytest.mark.parametrize("gate", GATES, ids=lambda p: p.name)
def test_the_gate_s_python_half_still_resolves(gate: Path):
    text = gate.read_text()
    bad = []
    for mod, names in _imports(text):
        try:
            m = importlib.import_module(mod)
        except Exception as exc:                # noqa: BLE001 — report, don't raise
            bad.append(f"{mod}: {type(exc).__name__}: {exc}")
            continue
        for n in names:
            #: a submodule is a legitimate `from pkg import sub`
            if hasattr(m, n):
                continue
            try:
                importlib.import_module(f"{mod}.{n}")
            except Exception:                   # noqa: BLE001
                bad.append(f"{mod}.{n} does not exist")
    assert not bad, (
        f"{gate.name} names things that have moved:\n  " + "\n  ".join(bad)
        + "\n\nThe gate cannot start, so it reports nothing — which reads "
          "exactly like passing.  Repoint it at the current module.")


def test_the_embedded_python_is_syntactically_valid():
    """★A gate that dies on a SyntaxError is as silent as one that dies on an
    import.  The Python lives inside JS template literals, so nothing else in
    the toolchain ever parses it.
    """
    bad = []
    for gate in GATES:
        text = gate.read_text()
        for block in re.findall(r"`\n?(import sys[\s\S]*?)`", text):
            #: `${...}` are JS interpolations; a string literal keeps the
            #: surrounding Python parseable without pretending to evaluate them
            src = re.sub(r"\$\{[^}]*\}", '"_"', block)
            try:
                ast.parse(src)
            except SyntaxError as exc:
                bad.append(f"{gate.name}: line {exc.lineno}: {exc.msg}")
    assert not bad, "\n".join(bad)
