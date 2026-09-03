"""Every document's frontmatter must parse, and say the same version twice.

★Why this exists.  `FYL-DESIGN-09`'s `change:` scalar lost its closing quote in
8109330 and stayed broken through four commits.  Nothing went red: MyST does
not fail on unparseable frontmatter, it **silently ignores the whole block**.
The visible effect was that the built page's title became 「摘要 (Abstract)」 —
the first heading in the body — instead of 「放电设计页」, and no `document_id`
reached the site.  A document that has quietly lost its identity still builds,
still renders, and still looks right to anyone not comparing it with the file.

The second assertion is the same failure in slow motion.  Each document states
its version twice — once in frontmatter (machine-readable) and once in the
15289 控制信息 table (what a reader sees) — and the table had drifted behind in
four documents at once, by as much as three releases.  Two statements of one
fact need something holding them together, or they are just two facts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
#: `archive/` is frozen history and `_build/` is output; neither is maintained.
SKIP = {"_build", "archive"}

DOCUMENTS = sorted(
    p for p in DOCS.rglob("*.md")
    if not SKIP & set(p.relative_to(DOCS).parts)
)


def frontmatter(path: Path):
    """The YAML block, or None when the file simply has no frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.group(1) if m else None), text


def test_there_are_documents_to_check():
    """★A glob that matches nothing passes every assertion under it — the exact
    mechanism that let a blind gate print `ok` for a whole page earlier today."""
    #: ★★2026-09-01：原来是 `> 20`，一个按**四本书**标定的整数。design/report 随内核
    #: 走后本仓只剩两本（17 篇），这条就红了——而它红的不是「扫不到文档」，是
    #: 「书少了两本」，那件事由 `test_docs_books` 点名。**按当时规模标定的整数，会在
    #: 规模合法变化时误报**，而误报的代价是把它调松，调松之后它就再也拦不住空集。
    #: 改成「每一部分都真的贡献了文档」——不随部分的数目漂移，空集仍然抓得住。
    #: ★2026-09-02：`docs/` 收成**一本书**，子目录不再各有 `myst.yml`，于是「哪些是
    #: 成章的目录」改由「不是 `figures/` / `benchmark/` / `_build/`」认——这三处
    #: 不入册的理由写在 `docs/myst.yml` 抬头，`test_docs_books` 双向断言着。
    from collections import Counter
    per_dir = Counter(p.relative_to(DOCS).parts[0] for p in DOCUMENTS)
    sections = sorted({d.name for d in DOCS.iterdir()
                       if d.is_dir() and d.name not in ("_build", "figures",
                                                        "benchmark")})
    assert sections, "docs/ 下一个成章的目录都没有"
    empty = [d for d in sections if not per_dir[d]]
    assert not empty, f"这些目录在场却一篇文档都没扫到：{empty}（各目录 {dict(per_dir)}）"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: str(p.relative_to(DOCS)))
def test_frontmatter_parses(path: Path):
    """An unparseable block is not a parse error anywhere else in the chain —
    MyST drops it and carries on, so this is the only thing that will say so."""
    block, _ = frontmatter(path)
    if block is None:
        return
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        pytest.fail(f"{path.relative_to(DOCS)}: frontmatter is not valid YAML — "
                    f"{type(exc).__name__}: {str(exc).splitlines()[0]}")
    assert isinstance(data, dict), (
        f"{path.relative_to(DOCS)}: frontmatter parsed to {type(data).__name__}, "
        f"not a mapping")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: str(p.relative_to(DOCS)))
def test_the_version_is_the_same_in_both_places(path: Path):
    """Frontmatter `version` vs the 控制信息 table's 版本 row."""
    block, text = frontmatter(path)
    if block is None:
        return
    data = yaml.safe_load(block)
    if not isinstance(data, dict) or "version" not in data:
        return
    row = re.search(r"\|\s*版本 \(Version\)\s*\|\s*v?([0-9.]+)\s*\|", text)
    if row is None:
        return  #: not every page carries the 15289 control block
    assert str(data["version"]).lstrip("v") == row.group(1), (
        f"{path.relative_to(DOCS)}: frontmatter says v{data['version']}, "
        f"the 控制信息 table says v{row.group(1)} — bump both or neither")


@pytest.mark.parametrize(
    "path",
    [p for p in DOCUMENTS if p.name.startswith("FYL-")],
    ids=lambda p: p.name,
)
def test_numbered_documents_carry_their_identity(path: Path):
    """`FYL-*` files are registry-addressed documents: they are cited by
    `document_id`, not by path, so losing that field unhooks them from the
    registry while the page still builds."""
    block, _ = frontmatter(path)
    assert block is not None, f"{path.name}: a FYL-* document with no frontmatter"
    data = yaml.safe_load(block)
    for key in ("document_id", "title", "version"):
        assert key in data, f"{path.name}: frontmatter has no `{key}`"
    assert path.name.startswith(data["document_id"]), (
        f"{path.name}: declares document_id {data['document_id']!r}, "
        f"which the filename does not carry")
