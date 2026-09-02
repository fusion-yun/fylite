"""Re-run a recorded session from its ledger — the executor a workflow
instance was written to be readable by.

★★What this closes, and what it deliberately does not.  ``engine.ledger``
made a session into a ``workflow-ir/2.0`` **instance**: one node per recorded
run, edges derived from the handles a call was given, each node bound to the
EXACT artifact version it ran.  That document could be validated, compared and
branched — but nothing could *execute* it, so「可重放」was a property claimed
about a file nobody had ever fed back in.  This module feeds it back in.

The loop is four steps per node, and each of them is a place a replay can
honestly fail rather than quietly produce something else:

1. **Resolve by ``artifact_ref``, not by name.**  The instance says which
   artifact and which version it ran; this looks that ``artifact_id`` up in
   the manifest set published TODAY.  A version that has moved is refused by
   default — an instance replayed against a different version is not a replay
   of it, and saying so is the whole point of binding exact versions.
2. **Read the arguments off the run's own manifest**, not off the node: the
   ledger records the SHAPE of a call (its ports), the run manifest records
   its VALUES.
3. **Rewrite the handles along the edges.**  A recorded argument names the
   original run (``fylite://r-…/psi``); the replay's source node produced a
   NEW run, so every inbound handle is re-pointed at it.  A node whose handle
   has no edge (a handle from another session) is refused, not guessed.
4. **Compare artefact hashes** with the recorded ones, per file, and report
   ``same`` / ``differs`` / ``new`` / ``missing``.

★**The limit is real and is stated up front**: a run manifest keeps bulk
inputs only as a DIGEST (``provenance.build_manifest`` digests them rather
than storing them), so a node that was called with an inline array — rather
than with a handle — cannot be replayed from the record alone.  Such a node is
REFUSED by name, with the argument named.  It is not skipped silently and it
is not re-run with the argument dropped, which would produce a different
computation wearing the same node id.

Module scope stays stdlib (DE-COMP-03); the physics is reached only through
the tool face, exactly as a caller reaches it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import handles, ledger

__all__ = ["plan", "replay", "REFUSED", "OK"]

#: a node's disposition after the driver looked at it
OK = "replayed"
REFUSED = "refused"


def _nodes_by_id(dag: dict) -> dict:
    return {n["id"]: n for n in dag.get("nodes") or []}


def _incoming(dag: dict) -> dict:
    """target node -> {target_port: (source_node, source_port)}."""
    inc: dict = {}
    for e in dag.get("edges") or []:
        inc.setdefault(e["target_node"], {})[e["target_port"]] = (
            e["source_node"], e["source_port"])
    return inc


def plan(doc: dict) -> list:
    """The instance's nodes in an order that respects its edges.

    ★A topological order, not the recorded order, even though for a session
    ledger the two coincide: the recorded order is the order things HAPPENED,
    and an executor that relied on that would break the moment an instance is
    edited or branched — which is precisely what the document type is for.
    A cycle raises rather than being broken arbitrarily.
    """
    dag = doc["fylite:projection"]["dag"]
    nodes = _nodes_by_id(dag)
    inc = _incoming(dag)
    ready, seen, order = list(nodes), set(), []
    # Kahn, kept simple: this is tens of nodes, not thousands
    while True:
        progressed = False
        for nid in list(ready):
            deps = {s for s, _ in inc.get(nid, {}).values()}
            if deps <= seen:
                order.append(nodes[nid])
                seen.add(nid)
                ready.remove(nid)
                progressed = True
        if not ready:
            return order
        if not progressed:
            raise ValueError(
                "the instance's edges contain a cycle; the nodes that cannot "
                f"be ordered are {sorted(ready)}")


def _run_dir_for(session_dir: Path, node: dict) -> Path:
    """Where the recorded run lives.

    ★Beside the LEDGER first, and the recorded absolute path only as a
    fallback: ``attrs.manifest`` was written with the run root that machine
    had, and a document meant to be re-read elsewhere cannot depend on it.
    """
    here = session_dir / node["id"]
    if (here / "manifest.json").is_file():
        return here
    recorded = node.get("attrs", {}).get("manifest")
    if recorded and Path(recorded).is_file():
        return Path(recorded).parent
    raise FileNotFoundError(
        f"node {node['id']}: no run manifest beside the ledger "
        f"({here / 'manifest.json'}) and none at the recorded path "
        f"({recorded!r})")


def _tool_for(node: dict, *, allow_version_drift: bool) -> tuple:
    """``(tool_name, note)`` for a node, resolved through its ``artifact_ref``.

    Raises ``ValueError`` when the artifact is gone or its version has moved
    (unless drift is explicitly allowed, in which case the note says so).
    """
    from .manifest import load_manifests
    ref = node.get("artifact_ref") or {}
    want_id, want_ver = ref.get("artifact_id"), ref.get("version")
    if not want_id:
        raise ValueError(f"node {node['id']} carries no artifact_ref")
    for name, doc in load_manifests().items():
        proj = doc.get("fylite:projection") or {}
        if proj.get("artifact_id") != want_id:
            continue
        have = proj.get("version")
        if have != want_ver and not allow_version_drift:
            raise ValueError(
                f"node {node['id']} ran {want_id} v{want_ver}; this checkout "
                f"publishes v{have}. A replay against a different version is "
                "not a replay of this instance — pass "
                "allow_version_drift=True to do it anyway, and say so in "
                "whatever you compare")
        note = None if have == want_ver else f"version {want_ver} -> {have}"
        return f"fylite_{name}", note
    raise ValueError(
        f"node {node['id']} ran artifact {want_id!r}, which this checkout "
        "does not publish")


def _arguments(run_dir: Path) -> tuple:
    """``(arguments, digested)`` recorded for one run.

    ``digested`` names the arguments the manifest kept only a digest of — the
    ones that make a node unreplayable.
    """
    man = json.loads((run_dir / "manifest.json").read_text())
    args = dict((man.get("config") or {}).get("arguments") or {})
    return args, sorted((man.get("inputs") or {}))


def _artifacts(run_dir: Path) -> dict:
    man = json.loads((run_dir / "manifest.json").read_text())
    return {a["name"]: a.get("sha256") for a in (man.get("artifacts") or [])}


#: The keys ``serve.deliver_result`` stamps on EVERY result: the record
#: naming its own location.  ★They are dropped before comparing, and the list
#: is short and closed on purpose — "normalise until it matches" is exactly
#: the failure this comparison exists to avoid, so what may be normalised is
#: named here and tied to the code that writes it
#: (``test_the_identity_keys_are_the_ones_the_service_stamps``).
IDENTITY_KEYS = ("run", "run_dir")

#: The verdicts a per-file comparison can return.  ★``SAME_MODULO_RUN_ID`` is
#: its own word rather than being folded into ``same``: it means「identical
#: once the run ids THIS REPLAY minted were mapped back to their nodes」, and a
#: reader is entitled to know that a normalisation happened at all.
SAME = "same"
SAME_MODULO_RUN_ID = "same (run ids)"
DIFFERS = "differs"


def _canonical_json(path: Path, run_to_node: dict):
    """A JSON artefact with every known run id replaced by its NODE id.

    ★★Why this is not fudging the comparison.  ``result.json`` embeds the
    handles the run produced (``fylite://r-20260825-110454/t``), so it names
    the run it came from — and a replay, by construction, produces a
    different run.  Compared byte for byte it would ALWAYS read「differs」,
    which is worse than no comparison: a reader would take a renaming for a
    changed number.  What is undone here is exactly the renaming the replay
    itself performed, and nothing else: only run ids present in the mapping
    are substituted, and only :data:`IDENTITY_KEYS` are dropped, so a value
    that changed for any other reason still shows.

    ★``run_dir`` is dropped rather than normalised because it is an ABSOLUTE
    path carrying the session directory — two runs of the same computation
    differ in it by construction, and it says nothing a reader of the
    comparison wants.  (That it is written at all is worth its own look: the
    ledger's ``attrs.manifest`` has the same problem, and this module reads
    it only as a fallback for that reason.)
    """
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    #: ★ONE PASS, longest id first.  Both halves are needed and each was
    #: learned the same way — by watching two identical files compare as
    #: different.  Run ids NEST (a second run in the same second is `r-…-2`,
    #: which contains `r-…`), so the order matters; and successive
    #: `str.replace` calls re-scan text they have already written, so the
    #: substitution `<node:r-…-2>` was itself rewritten into
    #: `<node:<node:r-…>>` on the next pass.  A single regex sweep can do
    #: neither.
    if run_to_node:
        pat = re.compile("|".join(
            re.escape(r) for r in sorted(run_to_node, key=len, reverse=True)))
        text = pat.sub(lambda m: f"<node:{run_to_node[m.group(0)]}>", text)
    try:
        body = json.loads(text)
    except ValueError:
        return None
    if isinstance(body, dict):
        body = {k: v for k, v in body.items() if k not in IDENTITY_KEYS}
    return body


def _compare(before: dict, after: dict, *, before_dir: Path = None,
             after_dir: Path = None, run_to_node: dict = None) -> dict:
    """Per-file verdict between two runs' artefacts.

    ★``manifest.json`` and ``acceptance.json`` are EXCLUDED, and not as a
    convenience: the manifest records the wall-clock time and the environment
    fingerprint of its own run, so comparing it would report every replay as
    different for reasons that have nothing to do with the computation.  What
    is compared is what the run PRODUCED.
    """
    skip = {"manifest.json", "acceptance.json"}
    out = {}
    for name in sorted(set(before) | set(after)):
        if name in skip:
            continue
        if name not in after:
            out[name] = "missing"
        elif name not in before:
            out[name] = "new"
        elif before[name] == after[name]:
            out[name] = SAME
        elif (name.endswith(".json") and before_dir is not None
              and after_dir is not None):
            a = _canonical_json(before_dir / name, run_to_node or {})
            b = _canonical_json(after_dir / name, run_to_node or {})
            out[name] = (SAME_MODULO_RUN_ID
                         if a is not None and a == b else DIFFERS)
        else:
            out[name] = DIFFERS
    return out


def replay(ledger_path, *, allow_version_drift: bool = False,
           session: str | None = None) -> dict:
    """Re-run every node of a recorded instance; return what happened.

    The replay lands in a FRESH session (its own run root entry), so the
    original stays intact and the two can be compared side by side.

    Returns ``{"source", "session", "nodes": [...], "replayed", "refused"}``;
    each node carries ``{"id", "tool", "status", "run", "artifacts", "note"}``
    and, when refused, ``"reason"``.
    """
    from . import serve

    ledger_path = Path(ledger_path)
    doc = json.loads(ledger_path.read_text())
    proj = doc.get("fylite:projection") or {}
    form = (proj.get("header") or {}).get("form")
    if form != "instance":
        raise ValueError(
            f"{ledger_path} is a workflow {form!r}, not an instance; a "
            "template says which versions it would accept, an instance says "
            "which one it ran — only the second can be replayed")
    session_dir = ledger_path.parent

    #: ★one session for the whole replay, taken once: `handles.session_id`
    #: caches per process, and a replay that let each node land in its own
    #: session would reproduce the very defect G-14 fixed.
    import os
    new_session = session or f"replay-{session_dir.name}"
    prev = os.environ.get("FYLITE_SESSION")
    os.environ["FYLITE_SESSION"] = new_session

    rows, mapping = [], {}
    try:
        for node in plan(doc):
            nid = node["id"]
            row = {"id": nid, "tool": node.get("display_name"),
                   "status": REFUSED, "run": None, "artifacts": {},
                   "note": None}
            rows.append(row)
            try:
                tool, note = _tool_for(
                    node, allow_version_drift=allow_version_drift)
                row["tool"], row["note"] = tool, note
                run_dir = _run_dir_for(session_dir, node)
                args, digested = _arguments(run_dir)
                if digested:
                    raise ValueError(
                        "the run manifest kept only a DIGEST of "
                        f"{digested} — a bulk argument passed inline cannot "
                        "be recovered from the record. Re-run the original "
                        "with a handle for it and the instance becomes "
                        "replayable")
                args = _rewire(node, args, mapping, doc)
                out = serve.call_mcp_tool(tool, args)
            except Exception as exc:                 # noqa: BLE001
                row["reason"] = f"{type(exc).__name__}: {exc}"
                continue
            if out.get("isError"):
                row["reason"] = out["content"][0]["text"]
                continue
            new_run = _run_of(out)
            if new_run is None:
                row["reason"] = ("the tool returned no handle, so this node "
                                 "produced nothing a later node could be "
                                 "fed")
                continue
            mapping[nid] = new_run
            row["run"] = new_run
            row["status"] = OK
            new_dir = handles.find_run(new_run)
            #: ★both directions of every node replayed SO FAR: an artefact may
            #: name an upstream run as well as its own.
            r2n = {node["id"]: node["id"], new_run: nid}
            r2n.update({rid: n for n, rid in mapping.items()})
            r2n.update({n: n for n in mapping})
            row["artifacts"] = _compare(
                _artifacts(run_dir), _artifacts(new_dir),
                before_dir=run_dir, after_dir=new_dir, run_to_node=r2n)
    finally:
        if prev is None:
            os.environ.pop("FYLITE_SESSION", None)
        else:
            os.environ["FYLITE_SESSION"] = prev

    return {"source": str(ledger_path), "session": new_session,
            "nodes": rows,
            "replayed": sum(1 for r in rows if r["status"] == OK),
            "refused": sum(1 for r in rows if r["status"] == REFUSED)}


def _rewire(node: dict, args: dict, mapping: dict, doc: dict) -> dict:
    """Point every inbound handle at the run the REPLAY produced.

    ★A recorded handle names the original run, and re-sending it would make
    the replay read the original's data — the nodes would all「succeed」and
    the run would prove nothing.  A handle whose source node is not in this
    instance (lineage from another session) raises: it is real provenance,
    and silently keeping it would be the same lie one level quieter.
    """
    dag = doc["fylite:projection"]["dag"]
    inc = _incoming(dag).get(node["id"], {})
    out = {}
    for k, v in args.items():
        #: ★BOTH spellings, and the second is the one that actually shows up:
        #: `serve._split_call` records a handle argument as a bare STRING
        #: (`config[k] = v["$ref"]`), because a handle is the most useful
        #: config value there is — it names the run this one was built on.
        #: So the record is unwrapped and the replay has to wrap it again for
        #: the service boundary to dereference it.  `handles.is_ref` answers
        #: about the ARGUMENT form (the dict), which is why the string case
        #: is tested against the scheme instead.
        if isinstance(v, dict) and set(v) == {"$ref"}:
            ref = v["$ref"]
        elif isinstance(v, str) and v.startswith(handles.SCHEME):
            ref = v
        else:
            ref = None
        if ref is None:
            out[k] = v
            continue
        src = inc.get(k)
        if src is None:
            raise ValueError(
                f"argument {k!r} is the handle {ref!r}, which this instance "
                "has no edge for — it came from a run outside this ledger, "
                "so the replay has nothing to re-point it at")
        src_node, src_port = src
        if src_node not in mapping:
            raise ValueError(
                f"argument {k!r} needs node {src_node!r}, which did not "
                "replay")
        out[k] = {"$ref": handles.handle(mapping[src_node], src_port)}
    return out


def _run_of(payload: dict):
    """The run id a shaped tool result came from — read off the handles it
    carries, since that is the one thing every array-returning tool has."""
    text = payload.get("content", [{}])[0].get("text")
    if not text:
        return None
    try:
        body = json.loads(text)
    except ValueError:
        return None
    if isinstance(body, dict) and isinstance(body.get("run"), str):
        return body["run"]
    for ref in _refs(body):
        try:
            return handles.parse(ref)[0]
        except ValueError:
            continue
    return None


def _refs(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "ref" and isinstance(v, str):
                yield v
            else:
                yield from _refs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _refs(v)
