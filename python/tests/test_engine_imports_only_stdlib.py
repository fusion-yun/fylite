"""FYL-SDD-01 DE-COMP-03's invariant, checked rather than stated.

    ``fylite.engine`` 顶层导入仅标准库；numpy 与重型依赖一律函数内惰性导入。

★★★It did not hold, and nothing could tell.  Two breaches, of two
different kinds:

* ``engine/provenance.py`` had a module-scope ``import numpy as np`` — the
  literal text, broken by one line, in the one engine module that used
  numpy at all.
* And the invariant was UNOBSERVABLE regardless, because importing any
  submodule runs the package's ``__init__`` first and
  ``fylite/__init__.py`` eagerly imported ``device``, ``engine``, ``io``,
  ``kernel``, ``run`` and ``scenario``.  Measured before the fix: ``import
  fylite.engine`` loaded numpy and nine ``fylite.scenario.*`` modules and
  took ~155 ms, however careful the engine was about its own imports.

An invariant with no witness is a sentence in a document.  These cases are
the witness, and they check both kinds: what the modules SAY (their import
statements) and what importing them DOES (a fresh interpreter).
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import fylite

ENGINE = Path(fylite.__file__).resolve().parent / "engine"


def _module_scope_imports(path: Path):
    """``(name, lineno)`` for every ABSOLUTE import at module scope.

    Relative imports are excluded on purpose: ``from .. import _paths`` and
    ``from .manifest import ...`` are intra-package and are what a
    subpackage is made of.  What the invariant is about is a THIRD-PARTY or
    heavy dependency being pulled in merely by importing the mechanism.
    """
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom) and not node.level:
            yield node.module or "", node.lineno


@pytest.mark.parametrize(
    "path", sorted(ENGINE.glob("*.py")), ids=lambda p: p.name)
def test_an_engine_module_imports_only_the_stdlib_at_module_scope(path: Path):
    """★The literal text.  ``__future__`` counts as stdlib; so does
    everything in ``sys.stdlib_module_names``."""
    bad = [f"line {ln}: {name}"
           for name, ln in _module_scope_imports(path)
           if name.split(".")[0] not in sys.stdlib_module_names]
    assert not bad, (
        f"engine/{path.name} imports a non-stdlib module at module scope:\n  "
        + "\n  ".join(bad)
        + "\n\nFYL-SDD-01 DE-COMP-03: the mechanism kernel's top-level "
          "imports are stdlib only, and numpy and heavy dependencies are "
          "imported inside the functions that use them.")


def _in_fresh_interpreter(source: str) -> str:
    """Run ``source`` in a subprocess and return its stdout, stripped.

    ★A subprocess and not this one: the test session has already imported
    numpy, so ``"numpy" in sys.modules`` here says nothing at all about
    what importing the engine costs.
    """
    out = subprocess.run([sys.executable, "-c", source], capture_output=True,
                         text=True, cwd=str(Path(fylite.__file__).parents[1]))
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_importing_the_engine_does_not_load_numpy():
    """★★The half the source-level check cannot see, and the half that was
    false for a different reason than the source was."""
    got = _in_fresh_interpreter(
        "import sys, fylite.engine; print('numpy' in sys.modules)")
    assert got == "False", (
        "import fylite.engine pulled numpy in.  Either an engine module "
        "imports it at module scope, or fylite/__init__.py has gone back to "
        "importing the package eagerly.")


def test_importing_the_package_does_not_load_the_package():
    """★``import fylite`` is the door, not the whole house.

    It used to import ``device``, ``engine``, ``io``, ``kernel``, ``run``
    and ``scenario`` eagerly — which is why the engine's own care did not
    matter.  The names still answer (PEP 562); they are just built when
    touched.
    """
    got = _in_fresh_interpreter(
        "import sys, fylite; "
        "print('numpy' in sys.modules, "
        "len([m for m in sys.modules if m.startswith('fylite.scenario')]))")
    assert got == "False 0", f"import fylite loaded: {got}"

    #: and the names still resolve, which is the whole obligation of a
    #: lazy package
    got = _in_fresh_interpreter(
        "import fylite; print(fylite.scenario.__name__, "
        "fylite.kernel.__name__, fylite.device_geometry.__name__)")
    assert got == "fylite.scenario fylite.kernel device_geometry"


@pytest.mark.parametrize(
    "mod", ["fylite.device", "fylite.engine", "fylite.io", "fylite.kernel",
            "fylite.run", "fylite.scenario", "fylite.fyo"])
def test_every_top_level_submodule_imports_on_its_own(mod: str):
    """★★No import ORDER.  ``fylite.run`` re-exported two private helpers
    from ``scenario.analysis.recon_rs`` while that module imported
    ``KefitRunError`` back out of ``run`` — the package's only cycle, and
    it resolved only if ``run`` went first.  ``fylite/__init__.py`` forced
    that order eagerly and said so in a comment, which is not a check: the
    day someone entered from the ``scenario`` end, the package failed to
    import at all.

    The re-export had no caller in the package (see ``run.py``), so cutting
    it left one direction and no rule to remember.
    """
    _in_fresh_interpreter(f"import {mod}")
