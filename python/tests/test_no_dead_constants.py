"""No module-level constant in the assembly layer is defined and never read.

★★Why this exists.  ``scenario/model/nbi.py`` carried ``_S1`` and ``_SZ`` —
the Janev/Boley/Post beam-stopping coefficients, 64 numbers, byte-for-byte
equal to ``heating.rs``'s ``S1`` and ``SZ`` — and **nothing called them**.
The fit had moved into the kernel; its coefficients stayed behind.  Alongside
them sat five dead physics constants and three dead deck-key sets across four
modules.

A dead table is not harmless, and this is the argument:

* it is indistinguishable from a live one at a glance, so the next person to
  correct the fit corrects **one of the two**;
* and **no test can fail**, because nothing evaluates the dead copy.  It is a
  divergence with no detector — the exact shape DE-COMP-02 exists to prevent,
  arrived at by deletion rather than by writing a second implementation.

So the rule is mechanical: in the assembly layer, a module-level constant is
either read, exported, or gone.  Anything kept for another reason says so
here, by name, with the reason.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "fylite"

#: ★Every tree a reader can live in.  The suite split in two on 2026-08-22
#: and the physics/numerics tier moved OUT of `python/` — so a scan rooted
#: at `python/` alone stopped seeing fifty modules' reads and reported live
#: constants as dead (`lh.ME_C2_EV`, read by `tests/test_lh.py`).  A rule
#: whose remedy is "delete the constant" has to see every reader.
#: ★★2026-09-01 那棵树**跨了仓**：物理数值档收敛进 fylite_kernel。同一条道理再走
#: 一遍——扫描根少一棵，活常数就会被报成死的。所以：探测内核检出，探到就把它的
#: `tests/` 一并纳入；**探不到就整档跳过**，因为此时这道闸给出的每一个「死常数」
#: 判词都可能是假的，而它的补救措施是「把常数删掉」。
#: ★宁可不判，也不要在看不全读者的情况下判。
def _kernel_tests():
    import os
    cands = ([Path(os.environ["FYLITE_KERNEL"])] if os.environ.get("FYLITE_KERNEL")
             else [PKG.parents[2] / "fylite_kernel", PKG.parents[2] / "fylite_dev"])
    for c in cands:
        if (c / "tests" / "oracles" / "__init__.py").is_file():
            return c / "tests"
    return None


_KTESTS = _kernel_tests()
TREES = (PKG.parent,) + ((_KTESTS,) if _KTESTS else ())
pytestmark = pytest.mark.skipif(
    _KTESTS is None,
    reason=("物理数值档在 fylite_kernel，本仓看不到它的读者；"
            "看不全读者就不判死常数（设 $FYLITE_KERNEL 即可跑）"))

#: Constants deliberately unread ANYWHERE — the scan below covers the whole
#: package and its tests, so an entry here means "kept for a reason outside
#: any Python file".  There are none today; the mechanism stays because the
#: alternative is a rule people disable rather than annotate.
ALLOWED: dict[str, str] = {}


def _repo_reads() -> set[str]:
    """Every name READ anywhere in either test tree or the package — by
    AST, not by grep.

    ★★By AST specifically, and this is the point.  Deciding this with a
    line-oriented search gets it wrong on

        from fylite.scenario.model.mapping import (
            AMU_GACODE,
            ME,
        )

    because no single line contains both the module and the name.  That
    exact miss happened while this rule was being written, and it would
    have deleted a constant three tests depend on.  A rule that deletes code
    has to be right about "unused", so it parses.
    """
    names: set[str] = set()
    for path in (p for t in TREES if t.is_dir() for p in t.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    names.add(a.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                #: `__all__` entries and `"mapping.MD"`-style references
                names.add(node.value)
    return names


def _module_constants(path: Path):
    tree = ast.parse(path.read_text())
    assigned: dict[str, int] = {}
    exported: set[str] = set()
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            if not isinstance(t, ast.Name):
                continue
            if t.id == "__all__" and isinstance(node, ast.Assign):
                exported |= {e.value for e in getattr(node.value, "elts", [])
                             if isinstance(e, ast.Constant)}
            #: SCREAMING_CASE only — a lower-case module global is usually
            #: mutable state, which this rule has nothing to say about
            elif t.id.lstrip("_").isupper() and t.id != "__all__":
                assigned[t.id] = t.lineno
    read = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    #: a re-export (`from .x import Y`) counts as a read of Y
    read |= {a.asname or a.name
             for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
             for a in n.names}
    return assigned, read, exported


TARGETS = sorted((PKG / "scenario").rglob("*.py"))
assert TARGETS, "no scenario modules found — has the package moved?"

READS = _repo_reads()


@pytest.mark.parametrize("path", TARGETS,
                         ids=lambda p: str(p.relative_to(PKG.parent)))
def test_no_constant_is_defined_and_never_read(path: Path):
    assigned, own_reads, exported = _module_constants(path)
    rel = str(path.relative_to(PKG.parent))
    dead = sorted(
        f"{name} (line {line})" for name, line in assigned.items()
        if name not in own_reads and name not in exported
        and name not in READS and f"{rel}::{name}" not in ALLOWED)
    assert not dead, (
        f"{rel} defines constants nothing anywhere reads:\n  "
        + "\n  ".join(dead)
        + "\n\nIf the value moved into the kernel, delete the copy — a dead "
          "table diverges from the live one with no test able to fail.")


def test_the_allowlist_has_no_stale_entries():
    """★An allowlist that outlives its entries is how a rule stops biting."""
    stale = []
    for key in ALLOWED:
        rel, _, name = key.partition("::")
        path = PKG.parent / rel
        if not path.exists():
            stale.append(f"{key}: no such file")
            continue
        assigned, own_reads, exported = _module_constants(path)
        if name not in assigned:
            stale.append(f"{key}: no longer defined")
        elif name in own_reads or name in exported or name in READS:
            stale.append(f"{key}: now read normally — the entry is obsolete")
    assert not stale, "\n".join(stale)


def test_the_scan_sees_a_name_imported_across_several_lines():
    """★The gate's own failure mode, pinned.

    `test_mapping.py` imports `ME` inside a parenthesised multi-line
    `from ... import (...)`.  A line-oriented search does not see it; the
    AST scan must.  If this ever fails, the rule has become able to delete
    live code.
    """
    assert "ME" in READS
    assert "AMU_GACODE" in READS
