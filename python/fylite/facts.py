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
3. the repository's own ``facts/``, when running from a checkout — **before**
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

__all__ = ["FACTS_ENV", "Entry", "roots", "use", "find", "entries",
           "domains", "rights", "problems", "FactsMissing"]

#: The search path.  ``os.pathsep``-separated, like ``$PATH`` — the same
#: separator the platform already uses for the same idea, rather than a
#: private one a reader would have to look up.
FACTS_ENV = "FY_FACTS_PATH"

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
        p = self.dir / "rights.json" if self.dir else None
        return p if p and p.is_file() else None


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
    """The checkout's own ``facts/``, when this package is being run from one."""
    #: PKG is <repo>/python/fylite; the corpus is <repo>/facts.
    cand = PKG.parent.parent / "facts"
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
        has_doc, has_dir = doc.is_file(), sub.is_dir()
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
