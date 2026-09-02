"""The two test trees stay two, and the boundary is the DIRECTORY.

★★**What this replaces.**  Until 2026-08-22 both tiers lived in this
directory and were told apart by a marker: `pytest.ini` carried
`-m "not physics"`, and a module made it into the paused tier by remembering
to write `pytestmark = pytest.mark.physics`.  A boundary that a new file
observes by remembering a decorator is a boundary that leaks — and it did,
inside one file: `test_fyo_documents.py` ran twenty-three conversion claims
by default and hid five physics claims at the bottom behind a mark.

The tiers are directories now — `python/tests` for the layer this package
owns (assembly, IO, the protocol/CLI faces, the registries, the ABI
marshalling), the repository's own `tests/` for the physics/numerics
comparisons and their fixtures.  A directory cannot be forgotten.  What CAN
happen is the old habit coming back, so it is checked here.

★These cases cost milliseconds, need no kernel and no machine data.
"""
from __future__ import annotations

import ast
import pathlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: ★★2026-09-01 边界从**目录**变成了**仓**。物理数值档（85 个模块 + `oracles/`
#: + `PHYSICS-MIGRATION.md` 台账）随物理计算一起收敛进 **fylite_kernel**；本仓是
#: 封装层，只留 `python/tests` 一档。
#: ★这道闸原来的三条断言里，有两条问的是「那棵树在不在本仓」——前提没了，问法要改，
#: **但它真正防的那件事没变**：`physics` 标记不许回到本档来。那才是它当初立起来的
#: 理由（标记式边界会漏，目录式不会；现在是仓式的，更不会）。
#: 探测到内核检出时，跨仓的重名检查照旧做——重名会让 pytest 的收集直接失败，
#: 而两棵树分居两个仓之后，这件事更不容易被发现。
def _physics_tier_root():
    import os
    cands = ([pathlib.Path(os.environ["FYLITE_KERNEL"])] if os.environ.get("FYLITE_KERNEL")
             else [ROOT.parent / "fylite_kernel", ROOT.parent / "fylite_dev"])
    for c in cands:
        if (c / "tests" / "oracles" / "__init__.py").is_file():
            return c / "tests"
    return None


PHYSICS = _physics_tier_root()

PY_TIER = sorted(HERE.rglob("test_*.py"))
PHYS_TIER = sorted(PHYSICS.rglob("test_*.py")) if PHYSICS else []


def _marks(path: Path) -> set[str]:
    """Every ``pytest.mark.<name>`` this module names, at any depth."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) \
                and isinstance(node.value.value, ast.Name) \
                and node.value.value.id == "pytest" and node.value.attr == "mark":
            out.add(node.attr)
    return out


@pytest.mark.parametrize("path", PY_TIER, ids=lambda p: p.name)
def test_no_physics_claim_is_left_in_the_python_tier(path: Path):
    """★A `physics` mark HERE is the old boundary coming back.

    Nothing deselects it any more, so a module that carries one either runs
    a physics claim in the tier that is meant to own no physics, or — worse —
    reads as paused to anyone who remembers the marker and is not.  Either
    way the file belongs in `tests/`.
    """
    assert "physics" not in _marks(path), (
        f"{path.name} marks a claim `physics`; that tier is the repository's "
        f"`tests/` directory now, not a marker.  Move the module (or just "
        f"those cases) there.")


def test_the_physics_tier_is_not_in_this_repository():
    """★★本仓**不该**有物理数值档——它在 fylite_kernel。

    这条替换了原来的「`tests/` 存在且非空」。前提反过来了：物理计算收敛进内核之后，
    本仓再出现一棵物理档，说明判据又开始往封装层这边长。
    ★仓根的 `tests/` 允许存在，但只能装那条指向冻结语料的符号链接（见 .gitignore）。
    """
    local = ROOT / "tests"
    stray = sorted(local.rglob("test_*.py")) if local.is_dir() else []
    assert not stray, (
        f"本仓出现了物理档模块 {[str(p.relative_to(ROOT)) for p in stray]}——"
        "物理判据属 fylite_kernel 的 tests/，本仓只有 python/tests 一档")


@pytest.mark.skipif(PHYSICS is None,
                    reason="物理档在 fylite_kernel；设 $FYLITE_KERNEL 指向一份检出即可跑这条")
def test_the_fixtures_moved_with_the_claims_that_read_them():
    """The recorded decks and the deck builders live beside the tier that
    compares against them, not beside the one that does not."""
    assert (PHYSICS / "oracles" / "__init__.py").is_file()
    assert not (HERE / "oracles").exists(), (
        "python/tests/oracles/ is back — the reference IMPLEMENTATIONS "
        "belong with the physics tier")
    assert not (HERE / "data").exists(), (
        "python/tests/data/ is back — the recorded decks belong with the "
        "physics tier")


def test_no_module_basename_is_used_by_both_trees():
    """★★A collision here does not fail one test — it fails COLLECTION.

    Neither tree is a package (no `__init__.py`, deliberately: the suites are
    run by path, not imported by name), so pytest imports each module under
    its bare basename.  Two files called `test_kernel.py` in two such
    directories are two modules with one name, and the second import comes
    back as `import file mismatch` — a message that reads like a stale
    `__pycache__` and sends the reader to delete caches instead of to the
    duplicate.
    """
    if not PHYS_TIER:
        pytest.skip("物理档在 fylite_kernel；设 $FYLITE_KERNEL 才能做跨仓重名检查")
    dup = {p.name for p in PY_TIER} & {p.name for p in PHYS_TIER}
    assert not dup, (
        "the same module basename is in both test trees, which breaks "
        f"collection when both are run: {sorted(dup)}")
