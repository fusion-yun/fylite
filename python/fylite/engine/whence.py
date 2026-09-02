"""A-4 — given a file, say which run made it and where that run came from.

★★The register goes one way and this is the other.  A run writes a manifest
naming its artefacts; nothing could take an artefact and get back to the run.
That gap is felt exactly when it matters: somebody has a ``result.json`` in a
directory, or a g-file a colleague sent on, and the question is「这是哪次跑出
来的、喂给它的是什么」.  Reading a path is not an answer — a file can be
copied, renamed, or handed over stripped of its directory.

So the lookup is BY CONTENT.  The file is hashed and matched against the
``sha256`` every run manifest already records for its artefacts; the path is
used only as a hint that lets the common case answer without a sweep.  A
renamed file still resolves; a file whose bytes changed does NOT, and saying
「找不到」 is the honest answer there — it is no longer the artefact that run
produced.

The lineage line comes from the session ledger, which already records one
edge per handle a call was given, so「上游是谁」is read off the record rather
than reconstructed.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import handles, ledger
from ._util import sha256_file

__all__ = ["whence", "NOT_FOUND"]

#: what a file that matches nothing gets — a value, so a caller can branch on
#: it, and a sentence, so a reader is told what was searched
NOT_FOUND = "no run in this run root recorded an artefact with these bytes"


def _manifests(root: Path):
    """Every run manifest under a run root, newest session first.

    ★Sorted so the common case — a file from the run somebody just did — is
    found early; correctness does not depend on the order, only the cost.
    """
    for session in sorted(root.iterdir(), reverse=True):
        if not session.is_dir():
            continue
        for run in sorted(session.iterdir(), reverse=True):
            m = run / "manifest.json"
            if m.is_file():
                yield run, m


def _lineage(run_dir: Path) -> dict:
    """The one-line lineage of a run: what it was, and what fed it."""
    doc = ledger.load(run_dir.parent)
    dag = (doc.get("fylite:projection") or {}).get("dag") or {}
    rid = run_dir.name
    node = next((n for n in dag.get("nodes") or [] if n.get("id") == rid), None)
    attrs = (node or {}).get("attrs") or {}
    #: ★`source_node` / `target_node` — the keys `ledger.record` actually
    #: writes.  This read `source`/`from` and `target`/`to`, so `upstream`
    #: was always empty and every assertion about its SHAPE still passed.
    #: The gate that would have caught it skipped itself for want of a chain,
    #: which is why it now builds one.
    upstream = sorted({e["source_node"] for e in dag.get("edges") or []
                       if e.get("target_node") == rid})
    return {"run": rid, "session": run_dir.parent.name,
            "tool": attrs.get("tool"), "entry": attrs.get("entry"),
            "upstream": upstream}


def whence(path, *, root=None) -> dict:
    """Which run produced ``path``, and a one-line lineage.

    Returns ``{"found", "file", "sha256", "run", "session", "tool", "entry",
    "created", "code", "host", "upstream", "artifact", "line"}``.  When
    nothing matches, ``found`` is ``False`` and ``note`` says what was
    searched — never a guess from the path.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = sha256_file(path)
    root = Path(root) if root else handles.runs_root()
    rec = {"found": False, "file": str(path), "sha256": digest,
           "root": str(root), "note": NOT_FOUND, "line": ""}
    #: ★`line` is on EVERY record, found or not.  It was set only on the
    #: found path and a caller printing it had to branch — which is how a
    #: not-found result ends up printed as nothing at all.
    if not root.is_dir():
        rec["note"] = f"{root} is not a run root — nothing has been recorded"
        rec["line"] = line(rec)
        return rec

    #: ★the file's own directory FIRST, when it is inside a run: it costs one
    #: read instead of a sweep, and it is the case a reader is usually in.
    #: ★It is a HINT, not the answer — the hash still has to match, so a file
    #: dropped into a run directory it did not come from is not adopted by it.
    order = []
    for parent in (path.parent, path.parent.parent):
        m = parent / "manifest.json"
        if m.is_file():
            order.append((parent, m))
    order += [p for p in _manifests(root) if p not in order]

    for run_dir, mpath in order:
        try:
            man = json.loads(mpath.read_text())
        except Exception:                        # noqa: BLE001
            continue                             # a half-written manifest
        for art in man.get("artifacts") or []:
            if art.get("sha256") != digest:
                continue
            env = man.get("environment") or {}
            rec.update(_lineage(run_dir), found=True, note=None,
                       artifact=art.get("name"),
                       created=man.get("created"),
                       code=(man.get("code") or {}).get("rev"),
                       dirty=bool((man.get("code") or {}).get("dirty")),
                       host=env.get("host"))
            rec["line"] = line(rec)
            return rec
    rec["line"] = line(rec)
    return rec


def line(rec: dict) -> str:
    """The one line A-4 asks for."""
    if not rec.get("found"):
        return f"{Path(rec['file']).name}: {rec['note']}"
    up = ", ".join(rec["upstream"]) if rec["upstream"] else "no upstream run"
    dirty = "+dirty" if rec.get("dirty") else ""
    return (f"{rec['artifact']} <- {rec['run']} ({rec['tool'] or '?'}) "
            f"in session {rec['session']} at {rec['created']} "
            f"[{rec['code']}{dirty} on {rec.get('host') or '?'}] <- {up}")
