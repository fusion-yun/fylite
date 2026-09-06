"""Every ``:mod:``/``:func:`` this package writes about itself resolves.

★★Why this exists.  Thirty-one cross-references across sixteen modules named
things that are not there — ``fylite.loop``, ``fylite.nbi``,
``fylite.circuits``, ``fylite.bundle``, ``fylite.machine`` — all of them
pre-refactor paths that the moves into ``scenario/``, ``io/`` and the kernel
left behind.  Four different ABI eras were represented, so this had been
accumulating rather than happening once.

★A dangling reference is not a typo.  These docstrings are the package's
own map of itself, they are what a reader follows to find the second half of
an answer, and this repository publishes them (``docs/``) and targets LLM
tool consumers that read them (``FR-TOOL-001..003``).  A name that resolves
to nothing sends the reader looking for a module that was deleted, which is
strictly worse than saying nothing: it asserts the wrong thing confidently.

★And one of them was worse than a wrong path.  ``device.point_response``
explained itself by pointing at ``breakdown.field_at``'s "numpy branch for
the no-kernel configuration", said the two were gated bit-identical, and
named the gate.  The function is gone, the branch was deliberately
dismantled (it was a second implementation of the same physics, reachable
by a missing build), and the gate now compares against a test-only oracle.
The sentence described an arrangement the repository had decided against.

Costs milliseconds and needs no kernel.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

import fylite

PKG = Path(fylite.__file__).resolve().parent

#: ``:role:`target``` — every Sphinx cross-reference role this package uses.
_ROLE = re.compile(r":(?:mod|func|class|meth|data|attr|obj):`~?([A-Za-z_][\w.]*)`")


def _resolves(dotted: str) -> bool:
    """Whether ``dotted`` names something importable or reachable by attribute.

    ★Two traps, both of which made an earlier version of this scan report
    live references as dangling:

    * a NESTED attribute (``fylite.fyo.Ladder.with_surfaces``) needs the walk
      to keep going after the module, not stop at the last dot;
    * a module can raise on IMPORT for a reason that has nothing to do with
      whether it exists — ``scenario.analysis.moments`` raises
      ``MachineDataMissing`` in a distribution with no device deck.  A scan
      that treats that as "missing" would have the package delete a correct
      reference.
    """
    parts = dotted.split(".")
    #: the longest importable prefix, whatever it raises on the way
    obj, i = None, 0
    for n in range(len(parts), 0, -1):
        head = ".".join(parts[:n])
        try:
            obj, i = importlib.import_module(head), n
            break
        except ImportError:
            continue
        except Exception:
            #: imported far enough to prove it exists, then refused for its
            #: own reasons — that is a live module
            return True
    if obj is None:
        return False
    for name in parts[i:]:
        try:
            obj = getattr(obj, name)
        except AttributeError:
            return False
    return True


def _module_of(src: Path) -> str:
    rel = src.relative_to(PKG).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(["fylite", *parts]) if parts else "fylite"


def _resolves_locally(src: Path, name: str) -> bool:
    """A BARE ``:func:`name``` — resolved against the module it is written in.

    ★★These are how the first version of this file missed six live defects.
    A bare name reads as "the one right here", so it is exactly the spelling
    a reader trusts without checking — and exactly the spelling that survives
    a rename, because a rename moves the definition and leaves the prose.
    ``neoclassical`` referred to ``neo_surface_inputs`` (its own old name,
    AND a different live function in :mod:`fylite.kernel` — a collision that
    has already cost this repository a rewritten ABI symbol);
    ``selfcal`` promised an ``assimilation_margin`` that would let a caller
    check the module's stated precondition, and there is no such function.

    A name may also be a member of a class defined in that module
    (``index_of`` is ``Ladder``'s), or a builtin — both count.
    """
    import builtins
    if hasattr(builtins, name):
        return True
    #: a bare ``:mod:`fylite``` is a module reference, not a local name
    try:
        importlib.import_module(name)
        return True
    except Exception:
        pass
    try:
        mod = importlib.import_module(_module_of(src))
    except Exception:
        return True                        # not this file's subject
    if hasattr(mod, name):
        return True
    return any(hasattr(c, name) for c in vars(mod).values()
               if isinstance(c, type))


SOURCES = sorted(PKG.rglob("*.py"))
assert SOURCES, "no package modules found"


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: str(p.relative_to(PKG)))
def test_every_self_reference_resolves(src: Path):
    bad = []
    for m in _ROLE.finditer(src.read_text(encoding="utf-8")):
        target = m.group(1)
        if "." not in target:
            if not _resolves_locally(src, target):
                line = (src.read_text(encoding="utf-8")[:m.start()]
                        .count("\n") + 1)
                bad.append(f"{src.relative_to(PKG)}:{line} -> {target} "
                           f"(bare, and not in this module)")
            continue
        if not target.startswith("fylite"):
            continue                       # numpy, pytest, the stdlib
        if not _resolves(target):
            line = src.read_text(encoding="utf-8")[:m.start()].count("\n") + 1
            bad.append(f"{src.relative_to(PKG)}:{line} -> {target}")
    assert not bad, (
        "docstrings point at names this package does not have:\n  "
        + "\n  ".join(bad)
        + "\n\nThese are usually pre-refactor paths.  The current layout is "
          "fylite.scenario.{model,analysis,control,design}.*, fylite.io.*, "
          "fylite.engine.*, fylite.device, fylite.fyo, fylite.kernel.")


def test_the_scan_can_tell_a_live_reference_from_a_dead_one():
    """★A gate for the gate.  This scan's whole value is its verdict on names
    it did not write, and both of its interesting cases are ones where the
    naive check is wrong: a nested attribute, and a module that exists and
    refuses to import here."""
    assert _resolves("fylite.fyo.Ladder.with_surfaces")
    #: a bare name is resolved against the module it was written in, and a
    #: class member counts — `index_of` is `Ladder`'s
    assert _resolves_locally(PKG / "fyo.py", "index_of")
    assert _resolves_locally(PKG / "fyo.py", "ValueError")
    assert not _resolves_locally(PKG / "fyo.py", "no_such_local_name")
    assert _resolves("fylite.scenario.analysis.moments")
    assert _resolves("fylite.kernel.neo_sauter")
    assert not _resolves("fylite.loop")               # moved to scenario.analysis
    assert not _resolves("fylite.fyo.Ladder.no_such_method")
    assert not _resolves("fylite.no_such_module")
