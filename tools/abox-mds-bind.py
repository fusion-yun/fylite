#!/usr/bin/env python3
"""Decompose the fydoc A-Box MDSplus bindings into the flat table both hosts read.

    python tools/abox-mds-bind.py \\
        --source ~/workspace/fydoc/device/east/abox

★**Why a build-time projection and not a runtime parse.**  The A-Box lives in
**fydoc**, a private documentation repository, and fylite is a protocol member
that never imports `sp`/`fy*` — so "the front end parses the A-Box" is an option
that works on the author's machine and nowhere else.  Projecting it at build time
puts the cross-repository dependency in one place: this script, run by a person
who has both checkouts.  `tools/east-signals-to-app.py` already does exactly this
for the signal catalogue; the binding table is the second of its kind.

★★**Why ONE table and not one parser per host.**  Writing the decomposition twice
— once in `python/fylite/io/mds.py`, once in the browser host — is a path this
repository has already taken three times, and each time it produced the same
defect shape: the device description came out with a DIFFERENT WALL on the two
sides (`fyo.rs`, now gated by `test_east_descriptions_agree.py`); the `zerod`
parameter order was spelled in three places, so reordering any one of them asks
silently for another discharge; and the MDS node names were spelled by
`io/mds.py` and `bin/app/api.rs` separately.  All three share a shape: **a wrong
answer that does not raise.**  A binding that reads `SILOPB` for `SILOPT` returns
an array of plausible numbers from another channel.  So the decomposition happens
once, here, and both hosts read the result in five lines (`fyo.rs`: "small enough
that both hosts parse it in five lines").

## What it emits, and what it deliberately does not

Each binding is decomposed into the pieces the kernel's mdsip client already
assembles a TDI string from — a validated node path and integers
(FYL-DESIGN-06 §5: `mdsip::Client` has, deliberately, no method taking an
expression).  **Nothing here relaxes that**: a binding this script cannot
decompose into `{verb, node, subscript}` is not emitted as an expression, it is
listed in `unsupported` with the reason.

★**Scale stays out of the kernel.**  `DATA(\\PLHI1)*1000` emits `scale: 1000`
and the host multiplies.  This is the boundary the retired `mapping/east-mds.json`
drew and gave the reason for: the table carries the binding, the device card
carries the machine's own facts, and the layer that computes carries neither.

★★**Units are NOT carried, because the A-Box does not carry them.**  The retired
`mapping/east-mds.json` declared `units_out` per group — including an explicit
`[TBD]` for the flux loops, with the note that "writing a guessed unit is worse
than leaving it blank".  The A-Box bindings are `$link` and nothing else, so that
declaration has no source here.  Every entry gets `units: null`; a consumer that
needs one must get it from the DD or from a person, and must not invent it.
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys

TOOL = "tools/abox-mds-bind.py"
SCHEMA = "fylite/mds-bind/1"

#: `DATA(...)` and `DIM_OF(...)` are the only two verbs the A-Box uses (measured:
#: 436 of 485 bindings).  Anything else is refused rather than guessed.
VERBS = {"DATA": "data", "DIM_OF": "dim_of"}

#: A node path, by the SAME rule the kernel validates with (`mdsip::is_node_path`):
#: letters, digits, `_ $ \ . : -`.  Written here so a binding that would be
#: refused at the door is refused HERE, where the reason can be printed.
NODE = r"[A-Za-z0-9_$\\.:-]+"
_NODE_RE = re.compile(rf"^{NODE}$")
_ITEM_RE = re.compile(r"^(?:(-?\d+)|(\*)|\{([A-Za-z_][A-Za-z0-9_]*)\})$")
_NUM_RE = re.compile(r"^-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$")


def _subscript(text):
    """`'0, *, {time_slice}'` -> list of index items, or None if any item is not
    an integer / `*` / a `{slot}`.

    ★The rejected shape is real and is exactly two bindings:
    `BDRY[0, 0: NBDRY[{time_slice}]-1, {time_slice}]` — the slice bound is
    ANOTHER NODE's value, so it cannot be an integer until that node has been
    read.  Those need two round trips and are named in `unsupported`.
    """
    out = []
    for raw in text.split(","):
        m = _ITEM_RE.match(raw.strip())
        if not m:
            return None
        i, star, slot = m.groups()
        out.append({"int": int(i)} if i is not None
                   else {"all": True} if star else {"slot": slot})
    return out


def decompose(expr):
    """`'DATA(\\PLHI1 )*1000'` -> (binding, None) | (None, reason)."""
    e = expr.strip()

    #: A literal, not a fetch.  One binding is `efit_east:1` (`boundary/type`).
    #: Emitted as a constant rather than dropped: the consumer still has to put
    #: a value there, and a missing key is how it would put `null`.
    if _NUM_RE.match(e):
        return {"verb": "const", "node": None, "subscript": None,
                "subscript_inside": False,
                "value": float(e) if "." in e else int(e), "scale": None}, None

    #: ★Peel from the OUTSIDE IN, in this order: scale, subscript, verb, then the
    #: subscript that may sit INSIDE the verb's parentheses.  Both placements
    #: occur — `DATA(\\X)[0,*]` (111 bindings) and `DATA(\\X[0,*])` (16) — and
    #: peeling the verb first leaves `DATA(\\X)` standing where a node path
    #: belongs, which the node rule then refuses.
    #: ★★Measured while writing this: with the two steps the other way round,
    #: 113 decomposable bindings land in `unsupported` **and the run still
    #: succeeds** — it just emits a third of the table.  That is this file's own
    #: failure mode, so the count is asserted by the gate, not eyeballed.
    scale = None
    m = re.search(r"\*\s*(-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\s*$", e)
    if m:
        scale = float(m.group(1))
        e = e[:m.start()].strip()

    e, sub, why = _peel_subscript(e)
    if why:
        return None, why

    verb, inside = "raw", False
    m = re.match(r"^([A-Za-z_]+)\s*\((.*)\)$", e, re.S)
    if m:
        name = m.group(1).upper()
        if name not in VERBS:
            return None, "unknown verb %r (only DATA / DIM_OF)" % m.group(1)
        verb = VERBS[name]
        e, inner, why = _peel_subscript(m.group(2).strip())
        if why:
            return None, why
        if inner is not None:
            if sub is not None:
                return None, "subscripted both inside and outside the verb"
            sub, inside = inner, True

    if "[" in e or "]" in e:
        return None, "nested or unbalanced subscript"

    node = e.strip()
    if not _NODE_RE.match(node):
        return None, "not a node path by the kernel's rule: %r" % node
    return {"verb": verb, "node": node, "subscript": sub,
            "subscript_inside": inside, "value": None, "scale": scale}, None


def _peel_subscript(text):
    """`'\\X[0, *]'` -> `('\\X', [items], None)`; `(text, None, None)` when there
    is no trailing subscript; `(text, None, reason)` when there is one this
    layer must not guess at."""
    if not text.endswith("]"):
        return text, None, None
    m = re.match(r"^(.*?)\s*\[([^\[\]]*)\]$", text, re.S)
    if not m:
        #: ★Balanced but NESTED — a subscript whose bound is another node's
        #: value, e.g. `BDRY[0, 0: NBDRY[{time_slice}]-1, {time_slice}]`.
        #: Say that, not "unbalanced": the shape is legal TDI and the reason it
        #: cannot be a Request is specific — the bound is unknown until NBDRY
        #: has been read, so it is two round trips, not one.
        if "[" in text[text.index("[") + 1:]:
            return text, None, ("subscript bound reads another node "
                                "(NBDRY-style) — needs two round trips")
        return text, None, "unbalanced subscript"
    items = _subscript(m.group(2))
    if items is None:
        return text, None, ("subscript bound is not an integer — it reads "
                            "another node, so it needs two round trips")
    return m.group(1).strip(), items, None


def _walk(node, path, out):
    """Collect `(semantic_path, $link)`; an array element carries its own `$id`
    (`"*"` for a template) instead of its numeric index."""
    if isinstance(node, dict):
        if isinstance(node.get("$link"), str):
            out.append(("/".join(path), node["$link"]))
            return
        for k, v in node.items():
            if k.startswith("@") or k.startswith("$") or k.startswith("dcterms:") \
               or k.startswith("prov:") or k.startswith("rdfs:") or k == "provenance":
                continue
            _walk(v, path + [k], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            seg = v.get("$id") if isinstance(v, dict) else None
            _walk(v, path + [str(seg if seg is not None else i)], out)


def build(files, source_dir):
    bindings, unsupported, sources = [], [], {}
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        ids = path.stem
        src = doc.get("$source") or {}
        for alias, uri in src.items():
            m = re.search(r"tree_name=([A-Za-z0-9_]+)", uri)
            sources.setdefault(alias, {"tree": (m.group(1) if m else alias).lower(),
                                       "uri": uri})
        leaves = []
        _walk(doc, [], leaves)
        for sem, link in leaves:
            alias, expr = None, link
            if ":" in link:
                head, rest = link.split(":", 1)
                if head in src:
                    alias, expr = head, rest
            row = {"ids": ids, "path": sem, "source": alias, "link": link}
            if alias is None:
                unsupported.append({**row, "why": "no `$source` alias on the link"})
                continue
            got, why = decompose(expr)
            if got is None:
                unsupported.append({**row, "why": why})
                continue
            bindings.append({**row, "tree": sources[alias]["tree"], **got,
                             "units": None})
    return bindings, unsupported, sources


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True,
                    help="the A-Box directory (the one holding bind/mdsplus/)")
    ap.add_argument("--public", default=os.environ.get("FYLITE_PUBLIC"),
                    help="the public checkout to write into ($FYLITE_PUBLIC)")
    ap.add_argument("--check", action="store_true",
                    help="re-generate and compare; write nothing, exit 1 on drift")
    a = ap.parse_args(argv)

    abox = pathlib.Path(a.source).expanduser()
    bind = abox / "bind" / "mdsplus"
    if not bind.is_dir():
        sys.stderr.write(f"no bind/mdsplus/ under {abox}\n")
        return 2
    files = sorted(bind.glob("*.jsonld"))

    #: ★Probe, and REFUSE rather than guess — this script writes generated files
    #: into another repository, and guessing wrong does not fail the run, it
    #: succeeds against the wrong tree.  Same rule as `rust/build.sh`.
    pub = a.public
    if not pub:
        here = pathlib.Path(__file__).resolve().parents[1]
        for c in (here / ".." / "fylite", here / ".." / "fylite_public"):
            if (c / "python" / "fylite").is_dir() and (c / "app" / "assets").is_dir():
                pub = str(c.resolve())
                break
    if not pub or not (pathlib.Path(pub) / "python" / "fylite").is_dir():
        sys.stderr.write("cannot find the public checkout (needs python/fylite/ "
                         "and app/assets/).\n  give it: --public /path/to/fylite\n")
        return 2
    pub = pathlib.Path(pub)

    bindings, unsupported, sources = build(files, abox)
    blob = b"".join(sorted(p.read_bytes() for p in files))
    out = {
        "$schema": SCHEMA,
        "machine": "east",
        "title": "EAST MDSplus 绑定——由 A-Box 分解出的扁平表，两个宿主读同一份",
        "provenance": {
            "tool": TOOL,
            "source": str(abox),
            "files": [p.name for p in files],
            "sha256": hashlib.sha256(blob).hexdigest(),
            #: ★★两个指纹，因为它们回答的是两个问题。`sha256` 是**读了哪些字节**
            #: ——出处必须能指回一个具体的源版本，所以它盖住整份文件，散文改了它
            #: 也变。`bindings_sha256` 是**分解出来的意思**。上游 A-Box 是生成物、
            #: 会被反复重写（实测 2026-09-02 一小时内两次），只有一个指纹的话，
            #: 闸子每次都红而没人说得出「这次到底有没有变绑定」——红得没有信息量
            #: 的闸子，读者会开始跳过它。
            "bindings_sha256": hashlib.sha256(json.dumps(
                [bindings, unsupported], sort_keys=True,
                ensure_ascii=False).encode("utf-8")).hexdigest(),
            "note": "Decomposed, not interpreted. `verb`+`node`+`subscript` are "
                    "what the kernel assembles a TDI string from; `scale` is the "
                    "host's to apply; `units` is null because the A-Box carries "
                    "none — do not invent one.",
        },
        "sources": sources,
        "bindings": bindings,
        "unsupported": unsupported,
    }
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"

    dests = [pub / "python" / "fylite" / "_mds_bind.json",
             pub / "app" / "assets" / "mds-bind.json"]
    if a.check:
        bad = [d for d in dests if not d.is_file()
               or d.read_text(encoding="utf-8") != text]
        for d in bad:
            sys.stderr.write(f"drift: {d}\n")
        #: ★漂移了就说清楚是哪一种：**意思变了**（要看 diff），还是**只是上游
        #: 重写过**（重跑一次即可）。见 provenance 里那两个指纹的注记。
        if bad and dests[0].is_file():
            was = json.loads(dests[0].read_text(encoding="utf-8"))
            same = (was.get("provenance", {}).get("bindings_sha256")
                    == out["provenance"]["bindings_sha256"])
            sys.stderr.write(
                "  绑定内容未变，只是上游 A-Box 被重写过——重跑生成器即可\n"
                if same else
                "  ★绑定内容变了——先看 diff，别直接覆盖\n")
        print(f"{len(bindings)} bindings / {len(unsupported)} unsupported — "
              f"{'DRIFT' if bad else 'in step'}")
        return 1 if bad else 0
    for d in dests:
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(text, encoding="utf-8")
    print(f"{len(files)} IDS · {len(bindings)} bindings · "
          f"{len(unsupported)} unsupported -> {dests[0]}, {dests[1]}")
    for u in unsupported:
        print(f"    unsupported  {u['ids']}:{u['path']}  {u['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
