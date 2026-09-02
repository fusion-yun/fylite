"""The deck mappers are name tables, and a name table does no arithmetic.

★★The rule is ``mapping.py``'s own, in its module docstring: **a name table
is a lookup; a normalisation is not, and this is the layer whose
normalisation errors do not raise.**  This module turns that sentence into
something a machine checks.

It is the line the whole fyo-boundary series converged on.  What moved into
the kernel was every entry that carried a normalisation -- ``RMIN_OVER_A``
and ``RMIN_LOC`` are ``rmin / a``, ``Q`` and ``Q_SA`` are ``abs(q)``, and a
host that reproduces an upstream normalisation is the host that gets one of
them wrong.  ``NU_1`` was 58x to 80x out for exactly that reason, on a live
reconstruction path, with nothing raising.

What stayed is what DE-COMP-02 assigns here by name: the names, the integer
flags (whose TYPE is load-bearing -- the oracle store is keyed by a JSON
digest, so a ``0`` that became ``0.0`` makes every recorded answer
unreachable), and the caller's own resolution knobs.

So the check is narrow and exact: **no division, no ``abs``, no power** in
either mapper.  Counting (``1 + len(ions)``), 1-based name indexing
(``i + 1``) and the MXH flag's 0/1 mask are allowed by name, because each is
a statement about the TABLE rather than about the physics -- and each is
listed here so that adding a fourth exception has to be argued.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from fylite.scenario.model import mapping
#: ★★2026-09-01：`oracles/`（参考实现）随物理数值档一起收敛进 fylite_kernel。
#: 本仓是封装层，没有它——不在场就点名跳过，而不是让整个模块以 ImportError 落地。
pytest.importorskip(
    "oracles",
    reason="oracles/ 随物理档在 fylite_kernel；把它放上 PYTHONPATH 才能跑这一档")
from oracles import gacode_derived

#: ``{mapper: the module that hosts it}``.
#:
#: ★``neo_inputs`` moved to the TEST tree on 2026-08-21 — it had no caller in
#: the package, because production reaches NEO through
#: :func:`fylite.kernel.neo_local` and never forms a deck.  The rule this file
#: checks is about the MAPPER, not about which tree it sits in, so the gate
#: follows it rather than losing sight of it: resolved by module here, so a
#: mapper cannot escape the check by moving.
HOSTS = {"tglf_inputs": mapping, "neo_inputs": gacode_derived}
MAPPERS = tuple(HOSTS)

#: Every arithmetic node allowed in a mapper, and why.  A `/`, an `abs()` or
#: a `**` is never on this list: those are the shapes a normalisation takes.
ALLOWED = {
    "count": "1 + len(ions) — how many species there are",
    "index": "i + 1 — NEO and TGLF number species from one",
    "mask": "shape_fac * ... — TGYRO_TGLF_MXH_FLAG, a 0/1 gate, upstream's",
    "sign": "-signb * signq — the sign rename, kept for its INTEGER type",
}


def _source(name: str) -> str:
    return Path(inspect.getsourcefile(HOSTS[name])).read_text()


def _tree(name: str) -> ast.FunctionDef:
    return next(n for n in ast.parse(_source(name)).body
                if isinstance(n, ast.FunctionDef) and n.name == name)


@pytest.mark.parametrize("name", MAPPERS)
def test_a_mapper_does_no_division_no_abs_and_no_power(name: str):
    """★The three shapes a normalisation takes.  None may appear here."""
    fn = _tree(name)
    bad = []
    for node in ast.walk(fn):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div,
                                                                ast.FloorDiv,
                                                                ast.Pow)):
            bad.append(f"line {node.lineno}: {type(node.op).__name__}")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "abs"):
            bad.append(f"line {node.lineno}: abs()")
    assert not bad, (
        f"{name} performs a normalisation:\n  " + "\n  ".join(bad)
        + "\n\nA name table is a lookup; a normalisation is not.  Compute it "
          "in mapping.rs, name it in a `@deck-names` const, and let "
          "rust/build.sh generate the name order into both hosts.")


@pytest.mark.parametrize("name", MAPPERS)
def test_every_multiply_or_add_is_one_of_the_four_listed_reasons(name: str):
    """★The looser half, kept honest by enumeration rather than by taste.

    ``*``, ``+`` and unary ``-`` have innocent uses here — counting, indexing,
    a 0/1 mask, a sign rename — so they cannot simply be banned.  Listing the
    four means a fifth has to be argued for rather than slipped in.
    """
    fn = _tree(name)
    src = _source(name).splitlines()
    ok = ("len(", "i + 1", "shape_fac", "signb", "range(")
    bad = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.BinOp)
                and isinstance(node.op, (ast.Mult, ast.Add, ast.Sub))):
            continue
        line = src[node.lineno - 1]
        if not any(t in line for t in ok):
            bad.append(f"line {node.lineno}: {line.strip()[:70]}")
    assert not bad, (
        f"{name} has arithmetic outside the four allowed reasons "
        f"({', '.join(ALLOWED)}):\n  " + "\n  ".join(bad)
        + "\n\nIf it is a fifth legitimate reason, add it to ALLOWED with a "
          "sentence.  If it is a normalisation, it belongs in the kernel.")


def test_the_moved_geometry_blocks_still_come_from_the_kernel():
    """★The positive half: the blocks really are kernel-sourced, not merely
    absent.  A mapper that quietly stopped emitting them would pass every
    check above.
    """
    for name in MAPPERS:
        fn = _tree(name)
        seg = "\n".join(_source(name).splitlines()[fn.lineno - 1:fn.end_lineno])
        assert '**loc["geometry"]' in seg, (
            f"{name} no longer splices the kernel's geometry block")
