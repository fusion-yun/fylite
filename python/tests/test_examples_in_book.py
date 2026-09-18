"""算例篇的每份文件都链进书里（`tools/examples-book.py` 写的生成块）。

★★MyST 只拷**被链接到**的文件。算例章从前只在正文里写文件名，站点上没有那些文件；
这道门守两件事：生成块是最新的，且 `docs/examples/` 下每份非章页的文件都被某一页链到。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "docs" / "examples"


def _tool():
    spec = importlib.util.spec_from_file_location("examples_book", ROOT / "tools" / "examples-book.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_generated_blocks_are_current():
    tool = _tool()
    stale = [p for p, fs in tool.pages().items()
             if tool.render(p.read_text(encoding="utf-8"), tool.block(p, fs)) != p.read_text(encoding="utf-8")]
    assert not stale, f"重跑 python tools/examples-book.py：{[str(p.relative_to(ROOT)) for p in stale]}"


def test_every_example_file_is_linked_from_a_page():
    tool = _tool()
    linked = set()
    for page in EX.rglob("*.md"):
        for target in re.findall(r"\]\(([^)#\s]+)\)", page.read_text(encoding="utf-8")):
            linked.add((page.parent / target).resolve())
    files = {p.resolve() for p in EX.rglob("*")
             if p.is_file() and p.suffix not in tool._SKIP_SUFFIX
             and not (set(p.parts) & tool._SKIP_NAME)}
    orphans = sorted(str(p.relative_to(ROOT)) for p in files - linked)
    assert not orphans, {"在 docs/examples/ 下却没有任何一页链到（站点上不会有它）": orphans}
