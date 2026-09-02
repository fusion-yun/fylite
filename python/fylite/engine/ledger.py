"""The session ledger: one LLM session, materialised as a workflow instance.

★★A conversation is not a record.  It is summarised, truncated and re-opened,
and a number quoted out of one has left every place its caveat was written
down.  What a session actually produces, if anything is to survive it, is a
sequence of recorded runs and the data dependencies between them — and that
is a DAG, which this ecosystem already has a normative document type for:
``workflow-ir/2.0`` (vendored in ``fylite/_spec``, and already used by the
authored ``kinetic_reconstruction`` template).

So the ledger is that document in its ``instance`` form, appended to as the
session goes: one node per recorded run, and one edge for every handle a call
was given — because a handle names the run it came from, the data-flow edges
are DERIVED, never declared.  The result is not a chat log: it is a flow that
can be re-read, compared, branched, and — after a human has looked at it —
promoted into a template.

★``provenance_class: sandbox_local`` + ``egress_allowed: false``, always.
That is the schema's own vocabulary for "assembled outside the registry, may
not reach production unpromoted", which is exactly what a session is.  The
authored template says the same thing about itself; this is not a new rule.

Module scope stays stdlib (DE-COMP-03).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import handles

LEDGER = "ledger.jsonld"

CONTEXT = {"sp": "https://spdata.org/sp#",
           "prov": "http://www.w3.org/ns/prov#",
           "fylite": "urn:fylite:"}

OWNER = "did:spharness:fylite/maintainers"

#: how far apart nodes are laid out; the ledger is a document a visual editor
#: can open, and a pile of nodes at the origin is not one.
_DX, _DY = 220, 120


def path_for(session_dir) -> Path:
    return Path(session_dir) / LEDGER


def _empty(session: str) -> dict:
    return {
        "@context": dict(CONTEXT),
        "@id": f"urn:fylite:session/{session}",
        "@type": ["fylite:SessionLedger", "prov:Bundle"],
        "fylite:session": session,
        "fylite:projection": {
            "$schema": "workflow-ir/2.0",
            "artifact_id": f"fylite/session/workflow_instance/{_local(session)}",
            "version": "0.1.0",
            "header": {
                "form": "instance",
                "display_name": f"fylite session {session}",
                "description": "Runs recorded in one session, in the order "
                               "they happened; edges are the handles one run "
                               "was given from another.",
                "owner": OWNER,
                "tenancy_scope": "project_local",
                "provenance_class": "sandbox_local",
                "egress_allowed": False,
                #: filled as runs land: an instance is bound to the EXACT
                #: artifact versions it ran (the schema requires at least
                #: one, and it is right to — an instance that names no
                #: version is not reproducible).
                "bound_artifact_versions": {},
            },
            "dag": {"nodes": [], "edges": []},
            "semantic_signature": "sha256:" + "0" * 64,
            "storage_hash": "sha256:" + "0" * 64,
            "signature": {
                "algorithm": "ed25519",
                "signer": OWNER,
                "signer_chain": [OWNER],
                "value": "UNSIGNED",
                "signed_at": "1970-01-01T00:00:00Z",
                "canonical_form_version": "jcs-1.0",
            },
        },
    }


def _local(name: str) -> str:
    """A session id as an ArtifactId local name (the pattern allows
    ``[A-Za-z0-9_/-]``)."""
    return "".join(c if (c.isalnum() or c in "_-/") else "-" for c in name)


def load(session_dir) -> dict:
    p = path_for(session_dir)
    if p.is_file():
        return json.loads(p.read_text())
    return _empty(Path(session_dir).name)


def record(run_dir, call: dict, *, ports=None) -> Path:
    """Append one recorded run to its session's ledger; return the path.

    ``call`` is the record :func:`fylite.engine.serve.deliver_result` already
    assembles — ``{tool, entry, arguments}``.  Every argument that is a handle
    becomes an EDGE from the run it names: the lineage is read off the call,
    not asserted by the caller.
    """
    run_dir = Path(run_dir)
    session_dir = run_dir.parent
    doc = load(session_dir)
    dag = doc["fylite:projection"]["dag"]
    rid = run_dir.name
    if any(n["id"] == rid for n in dag["nodes"]):
        return path_for(session_dir)

    tool = str(call.get("tool") or "call")
    artifact_id, artifact_version = _artifact_of(call)
    args = call.get("arguments") or {}
    inbound = {k: v["$ref"] for k, v in args.items()
               if isinstance(v, dict) and set(v) == {"$ref"}}

    i = len(dag["nodes"])
    dag["nodes"].append({
        "id": rid,
        "kind": "task",
        "node_type": "task",
        "display_name": tool,
        "node_path": f"fylite/session/workflow_instance/"
                     f"{_local(session_dir.name)}/{_local(rid)}",
        "parent_id": None,
        "attrs": {"run": rid, "tool": tool,
                  "entry": call.get("entry"),
                  "manifest": str(run_dir / "manifest.json")},
        "ports": {
            "in": [{"port_id": k, "label": k, "data_type": "sp:Handle",
                    "side": "left"} for k in sorted(inbound)],
            "out": [{"port_id": "result", "label": "result",
                     "data_type": "sp:Handle", "side": "right"}],
        },
        "readonly_fields": [],
        "position": {"x": (i % 4) * _DX, "y": (i // 4) * _DY},
        #: ★an EXACT version, not a range: a template says which versions it
        #: would accept, an instance says which one it ran.
        "artifact_ref": {"artifact_id": artifact_id,
                         "version": artifact_version},
    })
    known = {n["id"] for n in dag["nodes"]}
    for k, ref in sorted(inbound.items()):
        try:
            src_run, src_port = handles.parse(ref)
        except ValueError:                       # not ours; not an edge
            continue
        if src_run not in known:
            #: ★a handle from another session (or from a run this ledger never
            #: saw) is real lineage and must not be dropped — it is recorded
            #: on the node, where a reader can follow it, rather than as an
            #: edge to a node that is not here.
            continue
        dag["edges"].append({
            "id": f"e{len(dag['edges']) + 1}",
            "source_node": src_run, "source_port": src_port,
            "target_node": rid, "target_port": k,
        })

    doc["fylite:projection"]["header"]["bound_artifact_versions"][
        artifact_id] = artifact_version
    doc = seal(doc)
    p = path_for(session_dir)
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return p


def _artifact_of(call: dict) -> tuple[str, str]:
    """The manifest a recorded call ran, as ``(artifact_id, version)``.

    ★It RAISES when a call names no artifact this package publishes, rather
    than binding the instance to a placeholder.  Both recording paths know
    their artifact (the tool face by name, the CLI by declaring one), so a
    miss means a new path forgot — and an instance bound to "unknown" would
    be a document asserting reproducibility it does not have.
    """
    from .manifest import load_manifests
    name = call.get("artifact")
    tool = str(call.get("tool") or "")
    if not name and tool.startswith("fylite_"):
        name = tool[len("fylite_"):]
    docs = load_manifests()
    if name not in docs:
        raise ValueError(
            f"recorded call {tool!r} names no published artifact "
            f"(artifact={name!r}); a workflow instance must bind the exact "
            f"versions it ran. Known: {sorted(docs)}")
    proj = docs[name]["fylite:projection"]
    return proj["artifact_id"], proj["version"]


def seal(doc: dict) -> dict:
    """Recompute the instance's derived hashes — the same rule the authored
    manifests are sealed by (``engine.manifest.seal_manifest``), reused rather
    than restated."""
    from .manifest import seal_manifest
    return seal_manifest(doc)
