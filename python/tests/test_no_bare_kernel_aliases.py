"""No assembly-layer function is a bare second name for a kernel entry.

★★What this is about, and why it is subtler than the rules around it.  The
doctrine forbids a second IMPLEMENTATION of a physical quantity.  A bare
alias is not that — it is a second NAME: one quantity reachable by two
paths, with two docstrings free to drift apart while both keep working.

Three were found by asking why the model files still existed at all:
``redl.trapped_fraction``, ``redl.coefficients`` and ``neo.gyrobohm_factors``,
each ``return kernel.X(<same args>)`` and nothing else.  The last one's own
docstring gave the reason it had to go — the three gyro-Bohm exponents "may
not be written down twice" — and a second name for the entry holding them is
how a second writing-down starts.

★What hid them is the thing this test has to get right.  Four functions in
``nbi.py`` look identical and are NOT aliases: each wraps the call in
``_shaped(...)`` to restore the caller's scalar-or-array shape, and one also
picks a single field out of the kernel's dict.  That is array shaping —
exactly what DE-COMP-02 gives this layer.  A bare alias standing next to four
that earn their keep reads as one of them, which is why a person scanning the
file does not see it and a machine does.

So the rule is narrow: the body is one ``return``, its value is a direct
``kernel.X(...)`` call, and nothing wraps or indexes it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import fylite

PKG = Path(fylite.__file__).resolve().parent

#: Bare aliases that are deliberate, each with what makes it worth a name.
#: "It reads better" is not a reason — the kernel entry can be renamed.
ALLOWED: dict[str, str] = {
    #: `target_boundary` (design) left this list in T-4 第二十刀 (2026-09-06): it
    #: goes through `code/outlines` now and is no longer a second name for a
    #: kernel entry
}

SOURCES = sorted(p for p in PKG.rglob("*.py") if p.name != "kernel.py")


def _bare_aliases(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [n for n in node.body
                if not (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str))]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        val = body[0].value
        #: ★a DIRECT call only.  `_shaped(kernel.x(...), ...)` wraps it and
        #: `kernel.x(...)["g"]` indexes it — both do work, both are this
        #: layer's job, and neither is an alias.
        if not (isinstance(val, ast.Call)
                and isinstance(val.func, ast.Attribute)
                and isinstance(val.func.value, ast.Name)
                and val.func.value.id in ("kernel", "K")):
            continue
        #: ★★and the arguments must be EXACTLY this function's own, in
        #: order.  A nested `def ne_of(x): return kernel.interp(x, px, ne)`
        #: binds `px` and `ne` from the enclosing scope — that is partial
        #: application, which is real work and the reason the closure
        #: exists.  Without this clause the rule flags every such helper
        #: and has to be muted, which would take the three real ones with
        #: it.
        #: ★★`kwonlyargs` too.  Leaving them out let every keyword-only
        #: pass-through escape: `assembly.chi_from_flux(..., *, floor)`
        #: forwarded `floor=floor` and the check read that as "supplies a
        #: default the kernel does not", which is the one thing that WOULD
        #: have been work.  Found while evaluating assembly.py, one batch
        #: after this file was written — a gate that under-covers reads
        #: exactly like a clean codebase.
        params = [a.arg for a in node.args.args]
        kwparams = [a.arg for a in node.args.kwonlyargs]
        passed = [a.id for a in val.args if isinstance(a, ast.Name)]
        if len(passed) != len(val.args) or passed != params:
            continue
        #: a keyword the caller computes, or one the kernel does not take,
        #: is work; a bare `floor=floor` is not
        if any(k.arg not in kwparams
               or not (isinstance(k.value, ast.Name) and k.value.id == k.arg)
               for k in val.keywords):
            continue
        yield node.name, node.lineno, val.func.attr


@pytest.mark.parametrize("path", SOURCES,
                         ids=lambda p: str(p.relative_to(PKG.parent)))
def test_no_function_is_only_a_second_name_for_a_kernel_entry(path: Path):
    rel = str(path.relative_to(PKG.parent))
    bad = [f"line {ln}: {name}() is just kernel.{target}()"
           for name, ln, target in _bare_aliases(path)
           if f"{rel}::{name}" not in ALLOWED]
    assert not bad, (
        f"{rel} defines a second name for a kernel entry:\n  "
        + "\n  ".join(bad)
        + "\n\nCall the kernel directly at the call sites, or add the name to "
          "ALLOWED with what it is for.  A second name is one quantity with "
          "two docstrings, and they drift while both keep working.")


def test_the_shaping_wrappers_are_not_mistaken_for_aliases():
    """★The other half: this rule must not push the assembly layer into
    deleting the wrappers that DO work.  ``nbi.field_ion_sum`` restores the caller's shape — if this test ever
    starts flagging them, the rule has become the wrong rule.

    ★★It listed four, and two of them (``coulomb_log``,
    ``electron_shielding``) had no caller in the package or the tests.  So
    this case was keeping two dead names alive: it asserts a wrapper is NOT
    flagged, which a deleted wrapper satisfies as well as a live one, and
    meanwhile the name appearing here read as evidence that something used
    it.  A keeper list is a list of examples, and an example has to be a
    real one — see :func:`test_a_shaping_wrapper_with_no_caller_is_dead`
    for the half that catches this rather than resting on it.
    """
    nbi = PKG / "scenario" / "model" / "nbi.py"
    flagged = {name for name, _, _ in _bare_aliases(nbi)}
    #: ``shielding_factor`` was the other example until its last caller sank
    #: (``code/beam``, 2026-09-05) and the dead-wrapper half retired it
    #: ★T-4 第十七刀 (2026-09-06): `field_ion_sum` and the other shaping wrappers
    #: left with the slowing-down helpers for the kernel repository's oracle
    #: tree (`tests/oracles/beam.py`); the keeper list is empty until a real
    #: shaping wrapper lives here again — an example has to be a real one
    for keeper in ():
        assert keeper not in flagged, (
            f"nbi.{keeper} restores the caller's shape via _shaped(); "
            "flagging it means this rule is now catching real work")


def _shaping_wrappers(path: Path):
    """``def f(...): return _shaped(kernel.X(...), ...)`` — name and line.

    The shape the rule above deliberately does NOT flag, which is why it
    is the shape a dead name hides in.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [n for n in node.body
                if not (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str))]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        val = body[0].value
        if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Name)
                and val.func.id == "_shaped"):
            continue
        inner = ast.dump(val)
        if "'kernel'" in inner or "'K'" in inner:
            yield node.name, node.lineno


def test_a_shaping_wrapper_with_no_caller_is_dead():
    """★★A wrapper over a kernel entry that nothing calls is not shaping
    anything.

    ``nbi.coulomb_log`` and ``nbi.electron_shielding`` were exactly that —
    one ``return _shaped(kernel.X(...)[field], ...)`` each, zero callers in
    the package and zero in the tests.  Every rule around them was
    satisfied: they are not bare aliases (the shaping is real work), the
    module declares no ``__all__`` so nothing said they were not public,
    and the case above named them as examples of wrappers worth keeping.

    So the rule that finds them is not about the body.  It is REACHABILITY:
    this layer's wrappers exist to be called, and one with no call site is
    a name the kernel entry already provides.
    """
    used = set()
    for src in list(PKG.rglob("*.py")) + list(
            (PKG.parent / "tests").rglob("*.py")):
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:                       # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.Name):
                used.add(node.id)

    dead = []
    for path in SOURCES:
        rel = str(path.relative_to(PKG.parent))
        for name, lineno in _shaping_wrappers(path):
            #: its own `def` is not a use, and neither is a call from
            #: inside the file it is defined in — that would keep a pair of
            #: mutually-dead names alive
            others = {n for n, _ in _shaping_wrappers(path)}
            if name in used - others:
                continue
            calls_here = [
                n for n in ast.walk(ast.parse(path.read_text()))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == name]
            if calls_here:
                continue
            dead.append(f"{rel}:{lineno}: {name}()")
    assert not dead, (
        "these wrap a kernel entry and nothing calls them:\n  "
        + "\n  ".join(dead)
        + "\n\nThe kernel entry is the interface; a wrapper with no call "
          "site is a second name for it that nobody reads.  Delete it, or "
          "call it.")


def test_the_allowlist_has_no_stale_entries():
    stale = []
    for key in ALLOWED:
        rel, _, name = key.partition("::")
        path = PKG.parent / rel
        if not path.exists():
            stale.append(f"{key}: no such file")
        elif name not in {n for n, _, _ in _bare_aliases(path)}:
            stale.append(f"{key}: no longer a bare alias")
    assert not stale, "\n".join(stale)
