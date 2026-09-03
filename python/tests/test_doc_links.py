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
BOOK = DOCS / "myst.yml"

#: a link with a scheme, an anchor-only link, or a non-page target is not a page
#: reference and is out of scope here
LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s#]+\.md)(?:#[^)\s]*)?\)")


def toc_targets(myst: Path) -> set[Path]:
    """Resolved `- file:` entries of a myst/public yml."""
    body = "\n".join(
        ln for ln in myst.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )
    return {(myst.parent / rel).resolve()
            for rel in re.findall(r"-\s+file:\s*(\S+)", body)}


#: ★★2026-09-02 `docs/` 收成**一本书**：一个 `myst.yml`，一个 toc。此前这里按
#: 「四本书各自 myst.yml」枚举，还要处理「某一本搬去了另一个仓」的缺席——那两件
#: 事都没有了：`docs/myst.yml` 的 toc 就是全部已发布页面。
#:
#: ★「本仓有哪几部分、少了哪一部分」现在由 `test_docs_books.py` 一处回答，不在
#: 这里重复一遍——两处台账记同一件事，迟早只有一处被改。
PUBLISHED: set[Path] = toc_targets(BOOK)

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
    #: ★★2026-09-02 又改了一次口径。收成一本书之后「逐本非空」没有了主语，而
    #: 上一版那个「按当时规模标定的整数」的教训仍然管用：判据改成**每一个成章的
    #: 目录都真的贡献了页**——不随部分的数目漂移，空集仍然抓得住。
    per_dir = Counter(p.relative_to(DOCS).parts[0] for p in BOOK_PAGES)
    sections = sorted({d.name for d in DOCS.iterdir()
                       if d.is_dir() and d.name not in ("_build", "figures",
                                                        "benchmark")})
    assert sections, "docs/ 下一个成章的目录都没有——下面每条断言都会空过"
    empty = [d for d in sections if not per_dir[d]]
    assert not empty, (
        f"这些目录在场却一页都没解析出来：{empty}（各目录页数 {dict(per_dir)}）——"
        "多半是 docs/myst.yml 的 toc 写法变了，而不是目录空了")


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
