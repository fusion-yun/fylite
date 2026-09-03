"""`docs/` is ONE book: one `myst.yml`, one toc, one cover.

★★**它曾经是四本，然后是三本，2026-09-02 起是一本。**  分仓那阵 `docs/myst.yml` 用
``site.projects`` 挂三本各自独立的书（guide / reference / design）。那个形制有一处
躲不开的代价，也是这次改回来的全部理由：**MyST 1.10 在多 project 站点下不构建根
project**（三种写法都实测过：隐式根、显式 ``- path: .``、封面单放一个目录用
``slug: ''``），于是站点根上没有页面，``/`` 只能 302 到列表里的第一本——「哪本排
第一」成了承重的排版决定，而封面无处可放。一本书没有这个问题：根就是这本书。

于是这道闸问的东西换了，但**它防的三件事没变**：

  A PAGE IN NO TOC is a page nobody reaches, and the MyST build does not fail
  on an orphan.  Every ``.md`` under a documented section must be in the toc.

  A PAGE DELIBERATELY IN NO TOC is a different fact, and it has to be stated
  rather than merely observed.  ``benchmark/`` (the V&V registry and its
  reports) is out of the book by ruling: those files are referred to BY PATH
  from gates, CI and the corpus's ``account`` fields, and machine-read through
  ``registry.jsonld``.  A record referred to by path wants a stable path, not a
  chapter number.  So the exclusion is asserted in both directions — it is in
  no toc, and nothing else is.

  THE COLLECTION FORM MUST NOT COME BACK by accident.  A ``myst.yml`` appearing
  under a section would make it build separately and give its pages a second
  URL — and would take the root page away again, silently.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BOOK = DOCS / "myst.yml"

#: 书里五篇各占一个目录；两页在根上（封面与致谢）。
#: ★★2026-09-02 `physics/` 从 `reference/` 提上来单独成篇：十五章 4 800 行，是参考篇
#: 其余部分的三倍，答的也是另一个问题（「哪条方程、出自哪里、验到什么容差」）。
#: ★★2026-09-03 `examples/` 同理从 `guide/` 提上来：五族可跑算例加一页语料目录，答的是
#: 「照抄一条完整路径」而不是「怎么用」。两次判据相同——**答另一个问题、篇幅又与母篇
#: 其余部分相当**，那就是一篇，不是母篇目录下的第三级。
SECTIONS = ("guide", "examples", "reference", "physics", "design")
#: 在树里、**有意**不入册的目录，各自的理由写在 `docs/myst.yml` 抬头与 `INDEX.md`
NOT_IN_THE_BOOK = ("benchmark",)
#: 不是章节、也不含章节的目录
NOT_CONTENT = ("figures", "_build")


def toc_files(myst: Path) -> set[str]:
    """The `- file:` entries of a myst/public yml, as paths relative to `docs/`."""
    text = myst.read_text(encoding="utf-8")
    #: comments carry example paths ("`docs/benchmark/…`"), so read only real entries
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    return {str((myst.parent / rel).resolve().relative_to(DOCS))
            for rel in re.findall(r"-\s+file:\s*(\S+)", body)}


@pytest.fixture(scope="module")
def book() -> dict:
    return yaml.safe_load(BOOK.read_text(encoding="utf-8"))


def markdown_under(*dirs: str) -> set[str]:
    return {str(p.relative_to(DOCS)) for d in dirs
            for p in (DOCS / d).rglob("*.md") if "_build" not in p.parts}


def test_the_docs_are_one_book(book: dict):
    """★A `project:` with a toc — that is what a single book is, and it is what
    gives the site a root page to put the cover on."""
    assert "project" in book, (
        "docs/myst.yml has no `project:` — the collection form is back, and "
        "with it a site whose root has no page")
    assert book["project"].get("toc"), "the book declares no toc"
    assert not book.get("site", {}).get("projects"), (
        "docs/myst.yml mounts `site.projects` — that is the collection form; "
        "one book is one project")


def test_no_section_has_a_myst_of_its_own():
    """★★One book, one table of contents.  A `myst.yml` under a section makes it
    a project again: it would build separately, its pages would get a second
    URL, and the root page would silently disappear."""
    stray = [str(p.relative_to(DOCS)) for p in DOCS.rglob("myst.yml")
             if p != BOOK and "_build" not in p.parts]
    assert not stray, f"these turn sections back into separate books: {stray}"


def test_the_cover_is_the_first_page(book: dict):
    """★The cover is what the change to one book bought; the first toc entry is
    where a reader lands.  ★`docs/INDEX.md`, not `index.md`: the design section
    already addresses its own registry as `INDEX.md`, and one spelling for the
    same role across the tree is one less thing to remember."""
    first = book["project"]["toc"][0]
    assert first.get("file") == "INDEX.md", (
        f"the book's first entry is {first} — the cover has moved or gone")
    assert (DOCS / "INDEX.md").is_file()


def test_every_page_the_toc_lists_exists(book: dict):
    missing = sorted(rel for rel in toc_files(BOOK) if not (DOCS / rel).is_file())
    assert not missing, f"docs/myst.yml lists pages that are not here: {missing}"


def test_no_page_is_listed_twice():
    """Two toc entries for one file means two URLs for one page, and a reader
    who bookmarks the wrong one.  ★Counted from the text, because the set the
    other tests use has already collapsed any duplicate."""
    body = "\n".join(ln for ln in BOOK.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith("#"))
    entries = re.findall(r"-\s+file:\s*(\S+)", body)
    dupes = sorted({e for e in entries if entries.count(e) > 1})
    assert not dupes, f"listed more than once: {dupes}"


def test_every_page_in_the_book_sections_is_in_the_toc():
    """★A page in no toc is a page nobody reaches.  The MyST build does not
    fail on an orphan, so this does."""
    listed = toc_files(BOOK)
    on_disk = markdown_under(*SECTIONS)
    assert on_disk <= listed, {"in a section but in no toc": sorted(on_disk - listed)}


def test_the_pages_outside_the_book_are_outside_by_ruling():
    """★★Asserted in BOTH directions, so 「不入册」 stays a ruling rather than an
    observation: nothing out-of-book is in the toc, and nothing else is out."""
    listed = toc_files(BOOK)
    outside = markdown_under(*NOT_IN_THE_BOOK)
    assert not (listed & outside), {
        "the book lists a page that is out of the book": sorted(listed & outside)}
    everything = {str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md")
                  if "_build" not in p.parts}
    assert everything - listed == outside, {
        "in no toc and not accounted for": sorted(everything - listed - outside)}


def test_the_directories_that_hold_no_chapters_hold_none():
    """`figures/` is images and `_build/` is output; a `.md` appearing in either
    is a chapter in a place no toc will ever look."""
    for d in NOT_CONTENT:
        if d == "_build" or not (DOCS / d).is_dir():
            continue
        stray = sorted(p.name for p in (DOCS / d).glob("*.md"))
        assert not stray, f"docs/{d}/ grew chapters: {stray}"


def test_the_public_guide_subset_is_a_subset_of_the_book():
    """`guide/public.yml` names what ships with the browser demo.  It is a
    subset of the book, not a second toc — a chapter that ships but is in no
    toc would be published and unreachable at the same time.

    ★It stays a separate file on purpose: merge the two and adding an in-repo
    chapter to `guide/` would silently publish it."""
    public = toc_files(DOCS / "guide" / "public.yml")
    assert public <= toc_files(BOOK), sorted(public - toc_files(BOOK))
