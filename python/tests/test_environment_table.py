"""The declared environment surface, held against the source both ways.

★★Fourteen variables across five prefixes (`FYLITE_` / `FY_` / `KEFIT_` /
`RAYON_` / `FYDOC_`+`FYDATA_` — `KEFIT_` is the EFIT lineage's, kept because
that is what existing deployments set), and until the table existed **not one
place listed them**.  A first-time caller — and an LLM is always a first-time
caller — learned them one failed call at a time.

A hand-written list would drift on the first refactor, so it is gated in both
directions: every variable the package actually reads must be declared, and
every declared variable must be read by something.  The scan is static (AST),
so it sees the two spellings this package uses — ``os.environ.get("X")`` and a
module constant handed to it.

★It also caught two names that were never variables at all: ``FY_TGLF_EXEC``
and ``FY_MDSPLUS_ROOT`` appeared in one docstring, as the "same override
pattern" that ``FY_KERNEL_LIB`` follows, and **nothing anywhere reads either**.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import fylite
from fylite import engine

PKG = Path(fylite.__file__).resolve().parent
#: ★``RAYON_`` joined the three own-prefixes in 2026-08-26 (A-3).  It is not
#: this package's variable — rayon reads it inside the kernel — but the run
#: manifest now RECORDS it, so it is a variable the package reads, and the
#: both-ways rule is what keeps「记了什么」and「声明了什么」the same list.
#: ★★`FYDOC_` 2026-09-05 补入。它缺席时这道两向闸子**两向都错了**：
#: `FYDOC_ORACLE`（今天的名字）不带任何已知前缀，扫描看不见它，于是「声明了没人读」
#: 一侧红；而它的旧名 `FYDATA_ORACLE` 带 `FYDATA_` 前缀、被看见了却没人声明，于是
#: 「读了没声明」一侧也红。两条红指向的是**同一个漏掉的前缀**，不是两处代码缺陷。
PREFIXES = ("FYLITE_", "FY_", "KEFIT_", "RAYON_", "FYDATA_", "FYDOC_")


def _string_constants() -> dict:
    """Module-level ``NAME = "FY_SOMETHING"`` bindings — the spelling this
    package prefers for a variable it reads more than once."""
    out = {}
    for src in sorted(PKG.rglob("*.py")):
        for node in ast.parse(src.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.Assign):
                continue
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str) \
                    and v.value.startswith(PREFIXES):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = v.value
    return out


def _read_by_the_package() -> dict:
    """``{variable: {module, …}}`` for every environment read in the package."""
    consts = _string_constants()
    found: dict[str, set] = {}
    for src in sorted(PKG.rglob("*.py")):
        rel = str(src.relative_to(PKG))
        local = {}
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in tree.body:                       # this module's own consts
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        local[t.id] = node.value.value
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.args and node.func.attr in ("get", "getenv"):
                name = _env_name(node.args[0], local, consts)
            elif isinstance(node, ast.Subscript):
                name = _env_name(node.slice, local, consts)
            if isinstance(name, str) and name.startswith(PREFIXES):
                found.setdefault(name, set()).add(rel)
    return found


def _env_name(node, local: dict, consts: dict):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return local.get(node.id) or consts.get(node.id)
    if isinstance(node, ast.Attribute):
        return consts.get(node.attr)
    return None


DECLARED = engine.environment()
READ = _read_by_the_package()


def test_the_scan_finds_something():
    """★A detector that finds nothing to check is not passing, it is idle."""
    assert len(READ) >= 4, f"only found {sorted(READ)} — the scan lost its grip"


@pytest.mark.parametrize("name", sorted(READ))
def test_every_variable_the_code_reads_is_declared(name):
    assert name in DECLARED, (
        f"{name} is read by {sorted(READ[name])} and is not in "
        f"_environment.json — a caller has no way to learn it exists")


@pytest.mark.parametrize("name", sorted(DECLARED))
def test_every_declared_variable_is_actually_read(name):
    assert name in READ, (
        f"{name} is declared and nothing in the package reads it — either the "
        "code that read it left, or the entry was written for a variable that "
        "never existed (FY_TGLF_EXEC / FY_MDSPLUS_ROOT were exactly that)")


@pytest.mark.parametrize("name", sorted(DECLARED))
def test_each_entry_says_what_it_governs_and_what_happens_without_it(name):
    e = DECLARED[name]
    for field in ("governs", "needed_for", "default", "example"):
        assert e.get(field), f"{name}: {field} is empty"


def test_the_catalog_publishes_it():
    """NR-ENV: machine-readable, beside the capabilities, not in prose."""
    assert engine.manifest_catalog()["fylite:environment"] == DECLARED
