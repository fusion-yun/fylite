"""Where the facts are: a search path of corpora, in priority order.

`facts/` holds assertions about named individuals — a machine, an element's
atomic data, a measured shot — on a domain axis (``facts/device/east``,
``facts/amns/<provider>``, ``facts/experiment/<machine>/<shot>``).  This module
answers one question: **given a domain and an identifier, which file is it?**

★★**Several roots, and the first one wins the WHOLE entry.**  A distribution
ships one corpus, a site has another, and somebody debugging has a third; they
are consulted in order, like ``$PATH``.  What this module refuses to do is
*merge* them.  Two roots that both describe EAST describe it differently — one
may carry a reference discharge, another may have newer coil geometry — and a
document assembled half from each is a machine **nobody operates**, produced
without an error.  So resolution is per ENTRY: the first root that has
``<domain>/<id>`` supplies the document, its card and its rights ledger, all
three together, and :func:`find` records which root that was.

★Value-level merging is a different layer and a deliberate one: the middle
layer's ``assembly`` builds ONE document out of several providers, driven by a
manifest that says how (``$source`` / ``$link`` / ``merge`` / ``merge_key``).
That is a declared composition.  Silently preferring file A's coils and file
B's wall because they happen to sit in two roots is not.

Order, highest priority first:

1. an explicit override — ``--facts`` on the command line, or
   :func:`use` in-process;
2. ``$FY_FACTS_PATH`` — a ``os.pathsep``-separated list, read left to right;
3. the checkout's staged ``dist/facts/``, when running from one — **before**
   the bundled copy, so a corpus you just pulled is not shadowed by one frozen
   at packaging time;
4. the corpus this distribution ships (``fylite/_facts/``), when it has one.

★A root that does not exist is **skipped silently**; one that exists but holds
no domain directory is reported by :func:`problems`.  The difference matters:
"I have not pulled the corpus yet" is the normal state of a fresh checkout,
while "this path is set and is not a corpus" is a mistake worth naming.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ._paths import PKG

__all__ = ["FACTS_ENV", "ABOX", "RIGHTS", "FAIR", "MANIFEST", "Entry", "roots", "use",
           "find", "entries", "domains", "rights", "problems", "FactsMissing"]

#: The search path.  ``os.pathsep``-separated, like ``$PATH`` — the same
#: separator the platform already uses for the same idea, rather than a
#: private one a reader would have to look up.
FACTS_ENV = "FY_FACTS_PATH"

#: fydoc 那侧的 A-Box 目录名：**一条条目的数据部分**。★★★用户裁定 2026-09-04：
#: **`abox/` 外是散文，内是数据**。这条线已经在树里了，不必另立白名单——fydoc 的一台
#: 机器是 `<id>/{abox/, corpus/, figures/, *.md, *.bib, provenance.yaml}`，实测 13 台全有
#: `abox/`，而 `tools/`（书的构建脚本）没有，于是它自己就落在机器表之外。
ABOX = "abox"

#: 本仓生成的许可账（上游声明 + 本仓裁定，完整），与卡片同住。
RIGHTS = "rights.json"

#: fydoc 那侧的许可记录，相对条目目录。★★★**不另立 `rights.yaml`**（用户裁定）：
#: 许可只该有一处可编辑的真源，而 FAIR 件本来就是回答「这份数据可以拿来做什么」的
#: 那一份。它也是 JSON，所以两种账用同一个读者。
FAIR = (ABOX, "static", "now", "dataset_fair.jsonld")

#: 装置清单：★2026-09-04 由条目根的 `machine.yaml` 收进 A-Box（用户裁定）——
#: 清单也是关于这台装置的断言，它属于 `abox/`。
MANIFEST = (ABOX, "device.jsonld")

#: Where a wheel keeps the corpus it was built with.  Populated at packaging
#: time by ``tools/facts-publish.py``; absent in a source checkout, which is
#: why nothing here treats its absence as an error.
BUNDLED = PKG / "_facts"

#: In-process override, set by ``--facts`` (see ``engine.cli``).  A list, not
#: a string: the parse happens once, at the edge.
_override: list[Path] | None = None


class FactsMissing(LookupError):
    """An entry was asked for by name and no root on the path has it."""


@dataclass(frozen=True)
class Entry:
    """One resolved entry, and the root it came from.

    ★``root`` is not decoration.  With several corpora on the path, "which
    EAST is this?" has a different answer per machine, and a record that
    cannot say which root supplied a document cannot be replayed on another
    machine — the same reason every run manifest names its inputs.
    """

    domain: str
    ident: str
    root: Path
    #: the page document, when the entry has one
    document: Path | None
    #: the directory holding the card and the rights ledger
    dir: Path | None

    @property
    def rights_path(self) -> Path | None:
        """许可账：本仓生成的那份优先，否则 fydoc 的 FAIR 件。都在同一个根里。"""
        if self.dir is None:
            return None
        generated = self.dir / RIGHTS
        if generated.is_file():
            return generated
        fair = self.dir.joinpath(*FAIR)
        return fair if fair.is_file() else None

    @property
    def abox_path(self) -> Path | None:
        """这条条目的 A-Box 目录（fydoc 形状），存在才给。"""
        p = self.dir / ABOX if self.dir else None
        return p if p and p.is_dir() else None


def _is_entry_dir(d: Path, ident: str) -> bool:
    """这个目录是一条条目，还是恰好躺在域目录下的别的东西？

    ★★判据是「里面有没有本层认得出的部件」——A-Box、装置清单、装置牌、许可账。
    一个都认不出就不是条目：fydoc 的 `device/tools/` 正是这种东西，而在有这条判据
    之前 ``fy data facts device`` 会把它列成第 14 台机器。
    """
    return ((d / ABOX).is_dir()
            or d.joinpath(*MANIFEST).is_file()
            or (d / f"{ident}_device.yaml").is_file()
            or (d / RIGHTS).is_file())


def _split(raw: str) -> list[Path]:
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def use(paths=None) -> None:
    """Set (or with ``None`` clear) the in-process override.

    ★Called once by the command line.  It is not a context manager on
    purpose: a search path that changes under a running call would make two
    reads in one run resolve differently, and the record would name one root
    for both.
    """
    global _override
    if paths is None:
        _override = None
        return
    if isinstance(paths, (str, os.PathLike)):
        paths = _split(str(paths))
    _override = [Path(p).expanduser() for p in paths]


def _repo_facts() -> Path | None:
    """The checkout's staged corpus, when this package is being run from one.

    ★★2026-09-05 用户裁定：**fylite 下已无 `facts/` 目录**。拖回来的语料从此落在
    `dist/facts/`——一个构建暂存区（`dist/` 本来就不入库），而不是仓顶的一个目录。
    仓顶那个目录曾经是「gitignore 的输入」，一种只靠一行 `.gitignore` 撑着的安排：
    它看起来像仓的一部分，`app/facts` 还有一条符号链接指着它，于是「哪些字节属于
    这个仓」要靠记忆回答。搬进 `dist/` 之后，那个问题由目录名自己回答。
    """
    #: PKG is <repo>/python/fylite; the staged corpus is <repo>/dist/facts.
    cand = PKG.parent.parent / "dist" / "facts"
    return cand if cand.is_dir() else None


def roots() -> list[Path]:
    """Every root on the path that exists, in priority order, de-duplicated.

    ★De-duplicated by resolved path: a root named twice (once by the env var
    and once by the checkout probe, say) would otherwise make "which root
    supplied this" ambiguous in a way that reads as a real second source.
    """
    out: list[Path] = []
    if _override is not None:
        out.extend(_override)
    elif os.environ.get(FACTS_ENV):
        out.extend(_split(os.environ[FACTS_ENV]))
    #: ★★检出的 `facts/` 排在**自带的那一份之前**。反过来会让一份打包时冻结的
    #: 语料盖住刚拖回来的那一份——而它盖得悄无声息：两边都是合法文档，答案只是
    #: 旧的。装好的包里没有检出，所以这条排序在那里不起作用（`_repo_facts` 探不到）。
    repo = _repo_facts()
    if repo is not None:
        out.append(repo)
    if BUNDLED.is_dir():
        out.append(BUNDLED)

    seen, keep = set(), []
    for p in out:
        if not p.is_dir():
            continue
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        keep.append(p)
    return keep


def problems() -> list[str]:
    """Roots that are named but unusable, each with what is wrong.

    ★Separate from :func:`roots` because they are separate facts: a path that
    is set and wrong should be said out loud, while a path that is simply not
    there is the normal state of a checkout whose corpus has not been pulled.
    """
    named: list[Path] = []
    if _override is not None:
        named = list(_override)
    elif os.environ.get(FACTS_ENV):
        named = _split(os.environ[FACTS_ENV])
    where = "--facts" if _override is not None else f"${FACTS_ENV}"
    out = []
    for p in named:
        if not p.exists():
            out.append(f"{where}: {p} does not exist")
        elif not p.is_dir():
            out.append(f"{where}: {p} is not a directory")
        elif not any(d.is_dir() for d in p.iterdir()):
            out.append(f"{where}: {p} holds no domain directory "
                       "(expected facts/<domain>/, e.g. device/)")
    return out


def domains() -> list[str]:
    """Every domain any root carries, in name order."""
    seen = set()
    for r in roots():
        for d in r.iterdir():
            if d.is_dir() and not d.name.startswith((".", "_")):
                seen.add(d.name)
    return sorted(seen)


def find(domain: str, ident: str) -> Entry | None:
    """The first root that carries ``<domain>/<ident>``, or ``None``.

    An entry is a document (``<ident>.jsonld``), a directory
    (``<ident>/`` with the card and the rights ledger), or both — a root that
    has either half answers, and the OTHER half is taken from the SAME root,
    never from the next one down.
    """
    for r in roots():
        doc = r / domain / f"{ident}.jsonld"
        sub = r / domain / ident
        has_doc, has_dir = doc.is_file(), sub.is_dir() and _is_entry_dir(sub, ident)
        if has_doc or has_dir:
            return Entry(domain=domain, ident=ident, root=r,
                         document=doc if has_doc else None,
                         dir=sub if has_dir else None)
    return None


def require(domain: str, ident: str) -> Entry:
    """:func:`find`, or a loud error naming every root that was consulted."""
    hit = find(domain, ident)
    if hit is not None:
        return hit
    looked = [str(r) for r in roots()]
    raise FactsMissing(
        f"no {domain}/{ident} on the facts path"
        + (f" — looked in {', '.join(looked)}" if looked else
           f" — the path is empty; set ${FACTS_ENV} or pass --facts")
        + (". " + "; ".join(problems()) if problems() else ""))


def entries(domain: str) -> list[Entry]:
    """Every identifier in ``domain``, in name order, each from its winning root.

    ★The union across roots, resolved per entry — so a lower-priority root
    contributes the machines the higher one does not have, and none of the
    ones it does.
    """
    names = set()
    for r in roots():
        d = r / domain
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_dir():
                if _is_entry_dir(p, p.name):
                    names.add(p.name)
            elif p.suffix == ".jsonld" and p.stem != "catalogue":
                names.add(p.stem)
    out = []
    for n in sorted(names):
        hit = find(domain, n)
        if hit is not None:
            out.append(hit)
    return out


def rights(domain: str, ident: str) -> dict | None:
    """The rights ledger of the entry that wins, or ``None`` if it has none.

    ★From the winning root, never merged across roots — the ledger says what
    may be published, and a ledger assembled from two sources would answer for
    a document that does not exist.
    """
    hit = find(domain, ident)
    p = hit.rights_path if hit else None
    if p is None:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
