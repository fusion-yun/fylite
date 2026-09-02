"""Every ``fylite`` name a test imports still exists — including the ones
imported inside a function.

★★★Why this is not covered by "the tests pass".  ``test_moments.py`` did

    def _synthesise(...):
        from fylite import circuits
        from fylite.circuits import point_response

and ``fylite.circuits`` had been folded into :mod:`fylite.device` — the
module had converged onto the kernel until it computed nothing, and what it
still held was its ARGUMENT (which conductors, which channel split), which
``device`` already read.  The import was never updated.

Because it sat INSIDE a function, collection succeeded: pytest reported
five ordinary failures, not a collection error.  And because the file is
``physics``-marked, and that tier is deselected by default
(``pytest.ini``), those five failures became "the known baseline" — a
phrase this session repeated after every run.  A known-failing baseline is
where a permanently-broken test goes to be ignored: the module's claims
(plant a filament, recover it from synthetic probe signals) had not been
checked since the merge, and nothing said so.

A module-scope import gate would not have caught it.  This one resolves
every ``fylite`` import a test file names, wherever in the file it is
written.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

#: ★BOTH test trees, not just this one.  The suite split in two on
#: 2026-08-22 — the Python tier here, the physics/numerics tier in the
#: repository's own ``tests/`` — and this gate's whole subject is the tier
#: that is NOT run by default, where a dead import can sit for weeks.
#: Scanning only the directory it lives in would have aimed it at the half
#: that ordinary collection already covers.
TREES = (HERE, HERE.parents[1] / "tests")


def _fylite_imports(path: Path):
    """``(module, attribute_or_None, lineno)`` for every ``fylite`` import.

    ★``ast.walk``, not ``tree.body``: the point is the ones nested inside a
    function, which is where the dead one hid.  Relative imports are the
    test tree's own (``from oracles import ...``) and are left to ordinary
    collection, which does catch those.
    """
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "fylite":
                    yield alias.name, None, node.lineno
        elif isinstance(node, ast.ImportFrom) and not node.level:
            mod = node.module or ""
            if mod.split(".")[0] == "fylite":
                for alias in node.names:
                    yield mod, alias.name, node.lineno


@pytest.mark.parametrize(
    "path", sorted(p for t in TREES if t.is_dir() for p in t.rglob("test_*.py")),
    ids=lambda p: str(p.relative_to(HERE.parents[1])))
def test_every_fylite_import_in_this_file_resolves(path: Path):
    bad = []
    for mod, attr, lineno in _fylite_imports(path):
        try:
            m = importlib.import_module(mod)
        except ImportError as exc:
            bad.append(f"line {lineno}: import {mod} -> {exc}")
            continue
        if attr is not None and not hasattr(m, attr):
            #: a submodule is a valid `from pkg import name` target even
            #: before anything has imported it
            try:
                importlib.import_module(f"{mod}.{attr}")
            except ImportError:
                bad.append(f"line {lineno}: {mod} has no {attr!r}")
    assert not bad, (
        f"{path.name} imports fylite names that are gone:\n  "
        + "\n  ".join(bad)
        + "\n\nAn import written inside a function is not checked by "
          "collection — it fails when the case runs, which reads as an "
          "ordinary failure and can live in a known-failing tier.")
