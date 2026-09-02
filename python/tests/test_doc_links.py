"""A book must not link to a page that is in no book.

★Why this exists, precisely.  `docs/note/**` is deliberately in no book's toc
(2026-09-01 ruling): those files are referred to by PATH from source comments,
gates, CI and the corpus's `account` fields, so they keep stable paths instead
of chapter URLs.  But three book chapters still carried Markdown links into
them — and a link to a file the site does not publish **does not 404**.  MyST
copies the file in as a static asset and points the link at
`/build/<name>-<hash>.md`, so the reader clicks 「应用制品来源」 and gets raw
Markdown source instead of a page.  Nothing warns, the build stays green, and
the only way to see it is to click.

Same family as the day's other inert failures: something is declared, it never
takes effect the way it reads, and nothing complains.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BOOKS = ("design", "guide", "reference", "report")

#: a link with a scheme, an anchor-only link, or a non-page target is not a page
#: reference and is out of scope here
LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s#]+\.md)(?:#[^)\s]*)?\)")


def toc_targets(book: str) -> set[Path]:
    """Resolved `- file:` entries of one book's myst.yml."""
    myst = DOCS / book / "myst.yml"
    body = "\n".join(
        ln for ln in myst.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )
    return {(myst.parent / rel).resolve()
            for rel in re.findall(r"-\s+file:\s*(\S+)", body)}


#: ★★2026-09-01 仓一分为二：`design` / `report` 两本书跟 Rust 源码留在
#: fylite_kernel（它们讲的是内核），`guide` / `reference` / `cases` 在本仓。
#: 于是这道闸只能检查**本仓在场的那几本**。
#:
#: ★不在场就跳过，但**要点名跳过了谁**——声明缺席≠默认没有。此前这里是
#: 无条件 `read_text()`，缺一本就是模块级 `FileNotFoundError`，而 pytest 在
#: 收集期出错会**中断整档**：一本书搬到另一个仓，代价是本仓 2037 条一条都跑
#: 不了。闸子该报告边界变了，不该把自己变成一堵墙。
ABSENT: list[str] = []
PUBLISHED: set[Path] = set()
for _b in BOOKS:
    if (DOCS / _b / "myst.yml").is_file():
        PUBLISHED |= toc_targets(_b)
    else:
        ABSENT.append(_b)


def test_the_absent_books_are_the_ones_that_moved_to_the_kernel_repo():
    """★哪几本缺席是**判据**，不是背景。

    缺席集合一旦变大，说明又有一本书离开了本仓而没人说；变小则说明书回来了
    而这份名单没跟上。两种都该在这里红一次，而不是让上面那个循环默默少查一本。

    ★2026-09-02 变小过一次：`design` 从内核仓搬了回来。它按「讲的是内核就留在
    那边」归过去，而它讲的是四个页面与它们的运行概念——读者在这边。
    """
    assert sorted(ABSENT) == ["report"], (
        f"本仓在场的书变了：缺席的是 {sorted(ABSENT)}，此前是 ['report']"
        "（那一本讲内核的评估研究，跟 Rust 源码留在 fylite_kernel）。"
        "若确有搬动，改这里的名单，并说明书去了哪。")

BOOK_PAGES = sorted(p for p in PUBLISHED if p.is_file())


def test_the_published_set_is_not_empty():
    """★A set built from a glob that matched nothing would make every
    assertion below vacuous — the failure shape this repo has now hit three
    times in one day.

    ★★2026-09-01 这里原是 `> 20`，一个按**四本书**标定的整数。仓拆开后本仓只
    剩两本（17 页），闸子就红了——而它红的不是「解析不出页」，是「书少了两
    本」，那件事上面那道闸已经在说了。**一个按当时规模标定的整数，会在规模合
    法地变化时误报**，而误报的代价是把它调松，调松之后它就再也拦不住真正的
    空集。改成**逐本非空**：判据从「总数够多」换成「每一本在场的书都真的贡献
    了页」——它不随书的数目漂移，而空集正是它抓的那件事。
    """
    per_book = Counter(p.relative_to(DOCS).parts[0] for p in BOOK_PAGES)
    present = [b for b in BOOKS if b not in ABSENT]
    assert present, "本仓一本书都不在场——这道闸下面的每条断言都会空过"
    empty = [b for b in present if not per_book[b]]
    assert not empty, (
        f"这些书在场却一页都没解析出来：{empty}（各书页数 {dict(per_book)}）——"
        "多半是 myst.yml 的 toc 写法变了，而不是书空了")


@pytest.mark.parametrize("page", BOOK_PAGES, ids=lambda p: str(p.relative_to(DOCS)))
def test_every_page_link_points_at_a_published_page(page: Path):
    text = page.read_text(encoding="utf-8")
    for rel in LINK.findall(text):
        target = (page.parent / rel).resolve()
        assert target.exists(), (
            f"{page.relative_to(DOCS)} links to {rel}, which does not exist")
        assert target in PUBLISHED, (
            f"{page.relative_to(DOCS)} links to {rel}, which is in no book's toc. "
            f"That link will not 404 — MyST serves the file as a raw-Markdown "
            f"asset under /build/. Cite it as a repo path instead, or add it to "
            f"a book.")
