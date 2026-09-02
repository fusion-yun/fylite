"""`docs/` is four independent books, collected by a site that owns no pages.

★★THE SITE FILE HAS NO TOC OF ITS OWN.  It used to: MyST 1.10 will not serve a
root page in multi-project mode — measured, with an implicit root project, with
an explicit ``- path: .``, and with a cover directory mounted at ``slug: ''`` —
so while the site wanted a cover page, the only way to get one was to run
``docs/`` as a SINGLE project and spell the four books' tocs out a second time
there.  That copy needed a gate, and this file was it.

The cover was dropped on 2026-09-01, and with it the reason for the copy.
``docs/myst.yml`` is now ``site.projects``: four paths, no toc, nothing to
drift.  What this file checks is therefore no longer "does the copy agree" but
the two things that still can go wrong silently:

  A PAGE IN NO TOC is a page nobody reaches, and the MyST build does not fail
  on an orphan.  Every ``.md`` under a book must be in that book's toc.

  A PAGE DELIBERATELY IN NO TOC is a different fact, and it has to be stated
  rather than merely observed.  ``note/`` (measured notes and the V&V reports)
  is out of the books by ruling: those files are referred to BY PATH from
  source comments, gates, CI and the corpus's ``account`` fields, and a record
  that is referred to by path wants a stable path, not a chapter number.  So
  the exclusion is asserted in both directions — they are in no book, and
  nothing else is.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

#: ★★2026-09-01 仓一分为二：`design` / `report` 两本书讲的是内核，随 Rust 源码留在
#: **fylite_kernel**，站点文件 `docs/myst.yml` 也在那边（它是四本书的站点，不是本仓的）。
#: 本仓只有 `guide` / `reference`。
#: ★于是这道闸分成两半：**在场的书照查**（每本自带 myst、页都存在、无跨书重页），
#: **站点级的三条**（四本齐、站点文件不持页、书外页按裁定在外）在本仓查不了，
#: 按 `$FYLITE_KERNEL` 探测；探不到就点名跳过。
#: ★不把 BOOKS 直接改成两本：那会让「少了一本」变成静默通过。名单仍是四本，
#: 缺席由下面那条闸点名——判据是「谁不在」，不是「在的那些对不对」。
BOOKS = ("design", "guide", "reference", "report")
BOOKS_HERE = tuple(b for b in BOOKS if (DOCS / b / "myst.yml").is_file())
BOOKS_AWAY = tuple(b for b in BOOKS if b not in BOOKS_HERE)
SITE_FILE = DOCS / "myst.yml"
requires_site = pytest.mark.skipif(
    not SITE_FILE.is_file(),
    reason=("站点文件 docs/myst.yml 与 design/report 两本书在 fylite_kernel；"
            "本仓只有 guide/reference"))


def test_the_books_that_left_are_the_ones_that_describe_the_kernel():
    """★哪几本不在本仓是**判据**，不是背景。缺席集合变了就该在这里红一次。"""
    assert BOOKS_AWAY == ("design", "report"), (
        f"本仓在场的书变了：缺席 {BOOKS_AWAY}，此前是 ('design', 'report')"
        "（那两本讲内核，随 Rust 源码留在 fylite_kernel）")
#: in the tree, deliberately in no book — each for its own reason, spelled out
#: in the header of `docs/myst.yml`
NOT_A_BOOK = ("note", "cases", "figures", "archive", "_build")
#: …and of those, the two that hold pages a build would otherwise have swept up
OUT_OF_THE_BOOKS = ("note", "archive")


def toc_files(myst: Path) -> set[str]:
    """The `- file:` entries of one myst.yml, as paths relative to `docs/`."""
    text = myst.read_text(encoding="utf-8")
    #: comments carry example paths ("`docs/note/…`"), so read only real entries
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    out = set()
    for rel in re.findall(r"-\s+file:\s*(\S+)", body):
        p = (myst.parent / rel).resolve()
        out.add(str(p.relative_to(DOCS)))
    return out


def every_page_the_books_list() -> set[str]:
    union: set[str] = set()
    for book in BOOKS_HERE:
        union |= toc_files(DOCS / book / "myst.yml")
    return union


@pytest.fixture(scope="module")
def site() -> dict:
    return yaml.safe_load((DOCS / "myst.yml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("book", BOOKS_HERE)
def test_each_book_has_its_own_myst(book: str):
    assert (DOCS / book / "myst.yml").is_file(), (
        f"docs/{book}/ is one of the four books and must build on its own")


@pytest.mark.parametrize("book", BOOKS_HERE)
def test_every_page_a_book_lists_exists(book: str):
    for rel in toc_files(DOCS / book / "myst.yml"):
        assert (DOCS / rel).is_file(), f"docs/{book}/myst.yml lists a missing {rel}"


@requires_site
def test_the_site_collects_exactly_the_four_books(site: dict):
    """★The site's whole content is the four projects; a fifth book that is
    built but unlisted, or a listed one that is not there, is a book with no
    URL or a URL with no book."""
    projects = site.get("site", {}).get("projects")
    assert projects, "docs/myst.yml must mount the books under `site.projects`"
    paths = [p["path"] for p in projects]
    assert sorted(paths) == sorted(BOOKS), {"mounted": sorted(paths),
                                            "books": sorted(BOOKS)}
    for p in projects:
        assert p.get("slug") == p["path"], (
            f"{p['path']} is mounted at /{p.get('slug')} — keep the slug equal "
            "to the directory so a path in the repo and a path on the site are "
            "the same string")


@requires_site
def test_the_site_file_owns_no_pages(site: dict):
    """★★The derived-toc copy must not come back.  It existed only to give the
    site a cover page under a single project; the cover is gone (2026-09-01),
    and a toc here would once again be a second spelling of the books' own —
    one that drifts silently, because a page missing from it is simply a page
    nobody reaches."""
    assert "project" not in site, (
        "docs/myst.yml declares a `project:` — in collection form the four "
        "books are the projects and this file only mounts them")
    assert not (DOCS / "index.md").exists(), (
        "docs/index.md is back.  The site has no root project (MyST 1.10 does "
        "not build one in multi-project mode), so a cover here is a page that "
        "is never built — put it in a book, or leave it out")


def test_no_page_is_claimed_by_two_books():
    """Two books listing the same file means two URLs for one page, and a
    reader who bookmarks the wrong one."""
    seen: dict[str, str] = {}
    for book in BOOKS_HERE:
        for rel in toc_files(DOCS / book / "myst.yml"):
            assert rel not in seen, f"{rel} is in both {seen[rel]} and {book}"
            seen[rel] = book


def test_every_page_inside_a_book_is_in_that_books_toc():
    """★A page in no toc is a page nobody reaches.  The MyST build does not
    fail on an orphan, so this does."""
    listed = every_page_the_books_list()
    on_disk = {str(p.relative_to(DOCS))
               for book in BOOKS_HERE for p in (DOCS / book).rglob("*.md")
               if "_build" not in p.parts}
    assert on_disk == listed & on_disk, {
        "inside a book but in no toc": sorted(on_disk - listed)}


@requires_site
def test_the_pages_outside_the_books_are_outside_by_ruling():
    """★★`note/` is in no book ON PURPOSE — measured notes and the V&V reports
    are referred to by path from tests, TODO/FEATURE and the corpus's `account`
    fields, and a record referred to by path wants a stable path rather than a
    chapter number.  Asserted in both directions so that「不入册」 stays a
    ruling: none of them is in a toc, and nothing else is out of one."""
    listed = every_page_the_books_list()
    outside = {str(p.relative_to(DOCS))
               for d in OUT_OF_THE_BOOKS for p in (DOCS / d).rglob("*.md")}
    assert not (listed & outside), {
        "a book lists a page that is out of the books": sorted(listed & outside)}
    everything = {str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md")
                  if "_build" not in p.parts}
    assert everything - listed == outside, {
        "in no book and not accounted for": sorted(everything - listed - outside)}


@requires_site
def test_the_non_books_are_not_books():
    """`note/` `cases/` `figures/` `archive/` are directories, not books: they
    must not grow a `myst.yml`, because that would make them build separately
    and give their pages a second URL."""
    for d in NOT_A_BOOK:
        assert not (DOCS / d / "myst.yml").exists(), (
            f"docs/{d}/ acquired a myst.yml — it is not one of the four books")


def test_the_public_guide_subset_is_a_subset_of_the_guide_book():
    """`guide/public.yml` names what ships with the browser demo.  It is a
    subset of the guide, not a second book — a chapter that ships but is in no
    book's toc would be published and unreachable at the same time."""
    public = toc_files(DOCS / "guide" / "public.yml")
    guide = toc_files(DOCS / "guide" / "myst.yml")
    assert public <= guide, sorted(public - guide)
