#!/usr/bin/env python3
"""Generate ``app/facts/device/east-signals.json`` — the diagnostic catalogue the
device-data page selects signals by.

    python tools/east-signals-to-app.py \\
        --source ~/workspace/fydata/abox/device/tokamak/east/fyo/east_signal_catalog.yaml

★**Why the page needs this at all.**  A node path does not say which TREE it
lives in, and that mapping cannot be derived — it has to be known.  Measured on
#137985: EAST's own control signals (``\\PCRL01`` ``\\PCVLOOP`` ``\\LMSR``
``\\LMSZ`` ``\\DFSDEV`` ``\\PCPF1``) are all on ``pcs_east``; POINT and HCN are
on ``east``; core Thomson answers on both ``analysis`` and ``ts_east``; and
asking ``east`` for ``\\PCRL01`` returns ``%TREE-W-NNF`` — not empty data, but
*absent*.  Without a catalogue the page can only ask a reader to already know
the answer, which is exactly the work the site's own UDA client does for them.

★**It converts; it does not invent.**  Every field is copied from the upstream
harvest, and what the upstream does not carry is left null rather than guessed.
The tree name is the one exception and it is a rename, not an invention:
``EAST`` → ``east`` because mdsip tree names are matched case-insensitively and
the rest of this repository writes them lower-case.

★**What it deliberately does NOT do is verify.**  Whether a node holds data is
a property of a SHOT, not of the catalogue: #137985 stored 21 of its 79
magnetic probes, and a catalogue that had been filtered against one shot would
quietly become a claim about every other.  So every harvested entry is emitted,
and the page asks the gateway per shot.  `app/tests/validate-east-catalog.mjs`
checks the file's shape offline and, when pointed at a server, reports which
entries resolve — as a report, never as an edit to this file.

★**Private DAQs are emitted with no tree.**  Some diagnostics live on group-run
MDSplus servers on the operator's internal network rather than the central one, and "Private
DAQs" is not a tree name.  Dropping them would misrepresent the instrument set;
they are carried with ``tree: null`` and a reason, so the page can list the
diagnostic and say why it cannot fetch it.
"""

import argparse
import datetime
import hashlib
import json
import pathlib
import sys

import yaml

TOOL = "tools/east-signals-to-app.py"
SCHEMA = "fylite/east-signals/1"

#: Upstream writes tree names in the Wiki's capitalisation; mdsip does not care
#: but every other file in this repository writes them lower-case.
TREE_RENAME = {
    "EAST": "east",
    "PCS_EAST": "pcs_east",
    "Analysis": "analysis",
    "EFIT_EAST": "efit_east",
    "TS_EAST": "ts_east",
}

#: Not a tree — a family of group-run servers on another host.
PRIVATE = "Private DAQs"


def norm_tree(name):
    """-> (tree or None, reason or None)."""
    if name is None:
        return None, "upstream names no tree for this section"
    name = str(name).strip()
    if name == PRIVATE:
        return None, "private DAQ (group-run server, not the central mdsplus)"
    if name in TREE_RENAME:
        return TREE_RENAME[name], None
    # Anything else is passed through lower-cased if it can be a tree name at
    # all; if it cannot, say so rather than emitting something unfetchable.
    low = name.lower()
    if low and all(c.isalnum() or c == "_" for c in low):
        return low, None
    return None, f"upstream tree {name!r} is not a plain tree name"


def signals_of(block, kind):
    """The node rows of one `raw:`/`processed:` section."""
    if not block:
        return []
    tree, why = norm_tree(block.get("tree"))
    sub = block.get("sub_tree")
    out = []
    for n in block.get("nodes") or []:
        name = str(n.get("name") or "").strip()
        if not name:
            continue
        out.append({
            # ★The node is emitted as a TAG (a leading backslash), because that
            # is how these names resolve: `\POINT_F1` answers on `east` without
            # naming the sub-tree it structurally belongs to.  `sub_tree` is
            # kept alongside as provenance, not as part of the path.
            "node": name if name.startswith("\\") else "\\" + name,
            "tree": tree,
            "sub_tree": sub,
            "kind": kind,
            "unit": n.get("unit"),
            "dim": n.get("dim"),
            "desc": n.get("desc"),
        })
        if why:
            out[-1]["unfetchable"] = why
    return out


def provenance_path(src):
    """How the source file is NAMED in the published document.

    ★``str(src)`` was an ABSOLUTE PATH, and everything under ``app/`` is
    published — so the operator's home directory shipped to the website
    (measured 2026-09-02: ``~/workspace/fydata/...``).  It is also
    the field that rots first: the same file had already moved from
    ``fyo/0.0.0/`` to ``fyo/`` upstream while its sha256 stayed identical, so
    the recorded path pointed at nothing and the hash still identified the
    bytes exactly.  What provenance needs is *which artefact in which
    repository*, which is what a repo-qualified relative path says and what an
    absolute one only says by accident of where the operator keeps things.
    """
    src = src.resolve()
    for parent in src.parents:
        if (parent / ".git").exists():
            return f"{parent.name}:{src.relative_to(parent).as_posix()}"
    return src.name


def build(doc, source_path, source_sha):
    cats = doc.get("categories") or {}
    diagnostics = []
    for cat_name, cat in cats.items():
        for d in cat.get("diagnostics") or []:
            sig = signals_of(d.get("raw"), "raw") + signals_of(d.get("processed"), "processed")
            # ★A `raw.signals` string (a compressed name pattern such as
            # "PF1P, ..., PF12P") is NOT expanded into node rows: the upstream
            # marks those as approximate groupings, and expanding them would
            # manufacture node names nobody harvested.  The string is carried
            # so the page can show it as prose.
            raw = d.get("raw") or {}
            diagnostics.append({
                "title": d.get("title"),
                "category": cat_name,
                "description": d.get("description"),
                "location": d.get("location"),
                "responsible": d.get("responsible"),
                "specifications": d.get("specifications") or {},
                "source_url": d.get("source_url"),
                "signal_pattern": raw.get("signals"),
                "signals": sig,
            })

    live = doc.get("live_data_server") or {}
    return {
        "$schema": SCHEMA,
        "generated_by": TOOL,
        "generated_at": datetime.date.today().isoformat(),
        "source": {
            "file": str(source_path),
            "sha256": source_sha,
            "retrieved": doc.get("retrieved"),
            "index": doc.get("source_index"),
            "note": "EAST Wiki harvest (an internal wiki; the host is not written "
                    "into a published file). Names and units "
                    "are the upstream's; this file renames trees to lower case and "
                    "emits nodes as tags. Nothing is verified here — see "
                    "app/tests/validate-east-catalog.mjs.",
        },
        "server_hint": live.get("mdsplus"),
        "categories": sorted({d["category"] for d in diagnostics}),
        "diagnostics": diagnostics,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="east_signal_catalog.yaml from fydata")
    ap.add_argument("-o", "--out", default="app/facts/device/east-signals.json")
    a = ap.parse_args(argv)

    src = pathlib.Path(a.source).expanduser()
    if not src.is_file():
        sys.stderr.write(f"no such source: {src}\n")
        return 2
    blob = src.read_bytes()
    doc = yaml.safe_load(blob.decode("utf-8"))
    out = build(doc, provenance_path(src), hashlib.sha256(blob).hexdigest())

    n_sig = sum(len(d["signals"]) for d in out["diagnostics"])
    n_fetch = sum(1 for d in out["diagnostics"] for s in d["signals"] if s["tree"])
    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{dest}: {len(out['categories'])} categories, "
          f"{len(out['diagnostics'])} diagnostics, {n_sig} signals "
          f"({n_fetch} with a fetchable tree, {n_sig - n_fetch} without)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
