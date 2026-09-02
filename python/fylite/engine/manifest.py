"""Artifact-manifest machinery (generic; CONTENT lives in _manifest/*.jsonld).

Load, validate, seal, catalog and reflect the authored JSON-LD manifests,
and emit LLM tool schemas from them.  Nothing here knows what an efit run
or a flux loop is — adding an artifact is adding a file, not code.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import _paths


# --------------------------------------------------------------------------- #
# Artifact-manifest machinery (generic; the CONTENT lives in _manifest/*.jsonld)
#
# The declarative plane inverted to "files are the source": the JSON-LD
# manifests under ``_manifest/`` are *authored* description documents (SP-ADR-101
# D5: an offline-readable contract is data, not code); this section is the
# generic machinery that loads, validates, seals, catalogs, and reflects them.
# Nothing here knows what efit or a flux loop is — adding a new artifact to the
# package is adding a file, not code.  Derived hash fields are recomputed by
# :func:`seal_manifest` (edit file -> ``fylite manifest --seal`` -> conformance
# verifies the seal is idempotent).
# --------------------------------------------------------------------------- #

SPEC_DIR = _paths.PKG / "_spec"
MANIFEST_DIR = _paths.PKG / "_manifest"

#: ★★The environment this package reads, declared where a caller can find it.
#: There were eleven variables across three prefixes and **not one place that
#: listed them**: a first-time caller learned them one failed call at a time.
#: Data rather than code, and gated both ways against the source
#: (``test_environment_table.py``) — a variable the code reads and the file
#: does not name is a failure, and so is an entry naming a variable nothing
#: reads.
ENVIRONMENT_PATH = _paths.PKG / "_environment.json"


def environment() -> dict:
    """The declared environment surface: name -> what it governs."""
    return json.loads(ENVIRONMENT_PATH.read_text())["variables"]

#: JSON-LD keywords and their SpData ``$``-surface aliases — the semantic
#: channel (identity / concept / context), removed to obtain the plain payload
#: (mirrors the upstream rule that semantic keys leave the content plane).
SEMANTIC_KEYS = frozenset({
    "@context", "@id", "@type",
    "$context", "$id", "$type", "$onto",
})


def is_semantic(doc) -> bool:
    """True when *doc* carries any top-level JSON-LD semantic key."""
    return isinstance(doc, dict) and bool(SEMANTIC_KEYS & doc.keys())


def strip_semantic(obj):
    """Recursively remove semantic keys, returning the plain payload."""
    if isinstance(obj, dict):
        return {k: strip_semantic(v) for k, v in obj.items()
                if k not in SEMANTIC_KEYS}
    if isinstance(obj, list):
        return [strip_semantic(v) for v in obj]
    return obj


def _canonical_sha256(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def load_spec(name: str) -> dict:
    """Load a vendored SpData schema from ``_spec/`` by basename."""
    return json.loads((SPEC_DIR / f"{name}.schema.json").read_text())


def load_manifests(dirpath=None) -> dict:
    """Load the authored manifest set, name -> document (sorted by name)."""
    d = Path(dirpath) if dirpath else MANIFEST_DIR
    return {p.stem: json.loads(p.read_text())
            for p in sorted(d.glob("*.jsonld"))}


def manifest_catalog(docs: dict | None = None) -> dict:
    """The machine-readable capability catalog (the ``fylite describe``
    payload), derived from the authored manifests — never stored, never
    hand-copied, so it cannot drift from the files."""
    docs = docs if docs is not None else load_manifests()
    entries = []
    context, version = {}, "0.0.0"
    for name, doc in docs.items():
        context = context or doc.get("@context", {})
        version = doc.get("fylite:version", version)
        proj = doc["fylite:projection"]
        entries.append({
            "@id": doc["@id"],
            "@type": doc["@type"],
            "artifact_id": proj["artifact_id"],
            "kind": proj.get("kind", proj["$schema"].split("/")[0]),
            "title": doc["fylite:title"],
            "version": doc["fylite:version"],
            "entry": doc["fylite:entry"],
            "ports": doc["fylite:ports"],
            #: ★a capability can be PUBLISHED and not callable — a workflow
            #: template is a plan an engine runs, and one whose entry does
            #: not bind must say so where a caller looks, not only in a
            #: waiver inside the test suite.
            "executable": doc.get("fylite:executable", True),
            #: NR-ENV-005: the declared response envelope travels WITH the
            #: catalog, machine-readable — a caller that cannot tell a 30 ms
            #: call from a twenty-minute one will either block on a batch
            #: task or treat an interactive one as expensive.
            "response": doc.get("fylite:response"),
            #: ★What「good」means for THIS capability, travelling with the
            #: catalog for the same reason the response envelope does: a
            #: caller reading `unevaluated` off a verdict has to be able to
            #: find out whether nothing could be scored, or whether nobody
            #: has yet said what to score — and the `tbd` reasons are where
            #: that is written.
            "acceptance": doc.get("fylite:acceptance"),
        })
    return {
        "@context": dict(context),
        "@id": "fylite:catalog",
        "@type": "fylite:Catalog",
        "fylite:version": version,
        "fylite:environment": environment(),
        "fylite:manifests": entries,
    }


def resolve_entry(entry: str):
    """Import and return the callable named by a manifest ``fylite:entry``
    (``"module:attr"``).  Only fylite-internal targets are accepted."""
    import importlib
    mod, _, attr = entry.partition(":")
    if not mod.startswith("fylite"):
        raise ValueError(f"entry must be fylite-internal, got {entry!r}")
    return getattr(importlib.import_module(mod), attr)


#: semantic-layer keys every manifest document must carry
_REQUIRED_MANIFEST_KEYS = ("@context", "@id", "@type", "fylite:title",
                           "fylite:version", "fylite:entry", "fylite:ports",
                           "fylite:projection")


def validate_structure(doc: dict) -> list:
    """Own-layer structural check (always available, stdlib only).
    Returns a list of problems; empty means pass."""
    problems = [f"missing key {k}" for k in _REQUIRED_MANIFEST_KEYS
                if k not in doc]
    if problems:
        return problems
    ctx = doc["@context"]
    for prefix in ("sp", "prov", "fylite"):
        if prefix not in ctx:
            problems.append(f"@context lacks the {prefix!r} prefix")
    if not str(doc["@id"]).startswith("fylite:"):
        problems.append(f"@id not in the fylite: namespace: {doc['@id']}")
    ports = doc["fylite:ports"]
    for side in ("in", "out"):
        for p in ports.get(side, ()):
            dt = p.get("data_type", "")
            if not (dt.startswith("fyo:") or dt.startswith("sp:")):
                problems.append(
                    f"port {p.get('port_id')} data_type {dt!r} is not "
                    "fyo:/sp:-typed")
    proj = doc["fylite:projection"]
    if "$schema" not in proj or "artifact_id" not in proj:
        problems.append("projection lacks $schema/artifact_id")
    return problems


_PROJECTION_SCHEMA = {
    "compute-artifact/2.0": "compute_artifact",
    "data-artifact/2.0": "data_artifact",
    "workflow-ir/2.0": "workflow_ir",
}


def validate_projection(doc: dict) -> None:
    """Validate ``fylite:projection`` against the matching **vendored** SpData
    schema.  Needs the optional ``jsonschema`` package (RuntimeError if absent);
    raises ``jsonschema.ValidationError`` on a non-conformant projection."""
    try:
        import jsonschema
    except ImportError as exc:                                # pragma: no cover
        raise RuntimeError("projection validation needs the optional "
                           "'jsonschema' package") from exc
    proj = doc["fylite:projection"]
    schema = load_spec(_PROJECTION_SCHEMA[proj["$schema"]])
    common = load_spec("common")
    try:  # jsonschema >= 4.18: explicit registry
        from referencing import Registry, Resource
        registry = Registry().with_resources([
            ("common.schema.json", Resource.from_contents(common)),
            (schema.get("$id", ""), Resource.from_contents(schema)),
        ])
        jsonschema.Draft202012Validator(schema, registry=registry).validate(proj)
    except ImportError:                                       # pragma: no cover
        resolver = jsonschema.RefResolver(
            base_uri="", referrer=schema,
            store={"common.schema.json": common})
        jsonschema.Draft202012Validator(schema, resolver=resolver).validate(proj)


def seal_manifest(doc: dict) -> dict:
    """Recompute the derived hash fields of one manifest, returning a sealed
    copy (the input is not mutated).  Rules:

    * ``workflow-ir/2.0`` — ``semantic_signature`` = sha256 of
      ``{header, dag}``; ``storage_hash`` = sha256 of the projection minus
      ``storage_hash``/``signature``.
    * ``data-artifact/2.0`` with a live source (``byte_size == 0`` and a
      ``fylite:addressing`` block) — ``storage_hash`` = sha256 of the
      addressing descriptor (the live-source convention; open alignment item
      SP-REPORT-15 OI-2).
    * ``compute-artifact/2.0`` — nothing derived.
    """
    doc = json.loads(json.dumps(doc))
    proj = doc["fylite:projection"]
    kind = proj.get("$schema")
    if kind == "workflow-ir/2.0":
        proj["semantic_signature"] = _canonical_sha256(
            {"header": proj["header"], "dag": proj["dag"]})
        body = {k: v for k, v in proj.items()
                if k not in ("storage_hash", "signature")}
        proj["storage_hash"] = _canonical_sha256(body)
    elif (kind == "data-artifact/2.0" and proj.get("byte_size") == 0
          and "fylite:addressing" in doc):
        proj["storage_hash"] = _canonical_sha256(doc["fylite:addressing"])
    return doc


def seal_manifests(dirpath=None, *, write: bool = False) -> dict:
    """Seal every manifest in *dirpath*; returns name -> changed (bool).
    With ``write=True`` the changed files are rewritten in place."""
    d = Path(dirpath) if dirpath else MANIFEST_DIR
    changed = {}
    for name, doc in load_manifests(d).items():
        sealed = seal_manifest(doc)
        changed[name] = sealed != doc
        if write and changed[name]:
            (d / f"{name}.jsonld").write_text(
                json.dumps(sealed, indent=2, sort_keys=False) + "\n")
    return changed


def write_manifests(outdir, docs: dict | None = None) -> list:
    """Export the manifest set + the derived catalog into *outdir*."""
    docs = docs if docs is not None else load_manifests()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, doc in docs.items():
        p = out / f"{name}.jsonld"
        p.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
        written.append(p)
    p = out / "catalog.jsonld"
    p.write_text(json.dumps(manifest_catalog(docs), indent=2,
                            sort_keys=False) + "\n")
    written.append(p)
    return written


# ---- LLM tool-schema emission (SP-REPORT-15 route C) ----------------------- #

#: annotation text (this package writes ``from __future__ import
#: annotations``, so a signature carries STRINGS) -> JSON Schema type.
_JSON_TYPES = {
    "float": "number", "int": "integer", "bool": "boolean", "str": "string",
    "dict": "object", "list": "array", "tuple": "array", "set": "array",
    "np.ndarray": "array", "ndarray": "array", "Sequence": "array",
    "Path": "string", "str | Path": "string",
}

#: the argument form that carries data BY REFERENCE (``engine.handles``).
#: Advertised on every parameter that takes bulk data, so a caller can see
#: that it may pass a handle instead of inlining an array.
_HANDLE_SCHEMA = {
    "type": "object",
    "properties": {"$ref": {"type": "string", "pattern": "^fylite://"}},
    "required": ["$ref"],
    "description": "a fylite:// handle, resolved at the service boundary",
}

#: types for which a handle is an alternative — bulk data, not a scalar knob
_BY_REFERENCE = ("array", "object")


def _annotation_text(par) -> str | None:
    if par.annotation is par.empty:
        return None
    a = par.annotation
    return a if isinstance(a, str) else getattr(a, "__name__", str(a))


def _json_type(text: str | None, default) -> str | None:
    """The JSON Schema type of one parameter, from its annotation, else from
    its default.  ``None`` when neither says — and the caller then marks the
    parameter ``[TBD]`` rather than leaving a silent blank."""
    if text:
        #: ``float | None`` / ``Optional[float]`` -> the non-None member;
        #: ``tuple[float, ...]`` -> its container.
        parts = [q.strip() for q in text.replace("Optional[", "").split("|")]
        for part in parts:
            base = part.split("[")[0].strip().rstrip("]")
            if base in ("None", "NoneType", ""):
                continue
            if base in _JSON_TYPES:
                return _JSON_TYPES[base]
            if part.strip() in _JSON_TYPES:
                return _JSON_TYPES[part.strip()]
        return None
    if isinstance(default, bool):          # before int: bool IS an int
        return "boolean"
    if isinstance(default, int):
        return "integer"
    if isinstance(default, float):
        return "number"
    if isinstance(default, str):
        return "string"
    if isinstance(default, dict):
        return "object"
    if isinstance(default, (list, tuple)):
        return "array"
    return None


def _entry_input_schema(entry: str, shapes: dict | None = None) -> dict:
    """JSON Schema for an entry's keyword arguments, reflected from the real
    function signature (``inspect``) — never hand-copied, so it cannot drift.

    ★★It used to emit the parameter NAMES and nothing else: no ``type``, and
    a description that read ``parameter 'inputs' of fylite.scenario.model:
    tglf``.  A model calling that tool had to guess whether ``inputs`` was a
    number, a name or a whole deck — and for the parameters that take bulk
    data (a measurement set, a profile) there was no way to pass one at all
    without inlining it into the conversation.  Types now come from the
    annotation, or from the default when there is none; a parameter that
    declares neither is marked ``[TBD]`` rather than silently blank, because
    an unknown type and an untyped parameter must not look the same.

    ★A parameter that takes bulk data also advertises the handle form
    (``{"$ref": "fylite://…"}``), which is what makes composing two tools
    possible without either result travelling through the caller's context.

    ★★``shapes`` (the manifest's ``fylite:argument_shapes``) says what a
    STRUCTURED parameter must contain.  Reflection cannot see that: a
    signature says ``meas: dict`` and the deck it wants is three named
    arrays.  Measured, before this: ``fylite_efit(meas={})`` answered
    ``KeyError: 'brsp'`` — the truth, one key at a time, with the caller
    guessing between rounds.  The declaration is held against that behaviour
    by ``test_manifest_conformance.py``: the entry is called with the
    structure empty and the error it raises must name a key the manifest
    declares, so a shape that drifts from the code goes red.
    """
    import inspect as _inspect
    sig = _inspect.signature(resolve_entry(entry))
    properties, required = {}, []
    for name, p in sig.parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        text = _annotation_text(p)
        has_default = p.default is not p.empty
        jtype = _json_type(text, p.default if has_default else None)
        desc = f"{name}: {text}" if text else f"{name}: [TBD] (no annotation)"
        prop: dict = {"description": desc}
        if jtype in _BY_REFERENCE:
            prop["anyOf"] = [{"type": jtype}, dict(_HANDLE_SCHEMA)]
        elif jtype:
            prop["type"] = jtype
        if has_default and isinstance(p.default, (int, float, bool, str)):
            prop["default"] = p.default
        shape = (shapes or {}).get(name)
        if shape and "anyOf" in prop:
            #: the object branch gains the keys the entry actually needs
            prop["anyOf"][0].update(
                {"required": list(shape["required"]),
                 "properties": {k: {} for k in shape["required"]}})
            prop["description"] += f" — {shape['note']}"
        properties[name] = prop
        if not has_default:
            required.append(name)
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def llm_tools(docs: dict | None = None) -> list:
    """The manifest set as neutral LLM tool definitions — one tool per
    manifest, name ``fylite_<name>``, description from the manifest title +
    fyo-typed port signature, input schema reflected from the entry callable's
    signature.  Format adapters: :func:`to_anthropic_tool` /
    :func:`to_openai_tool`."""
    docs = docs if docs is not None else load_manifests()
    tools = []
    for name, doc in docs.items():
        if doc.get("fylite:executable") is False:
            #: ★★it stays in the CATALOG (a reader should see the plan and
            #: why it cannot be called) and leaves the TOOL FACE, because a
            #: tool a model can select and cannot run costs it a turn and
            #: teaches it the wrong thing about this package.
            continue
        ports = doc["fylite:ports"]
        sig = (", ".join(f"{p['port_id']}:{p['data_type']}"
                         for p in ports["in"])
               + " -> "
               + ", ".join(f"{p['port_id']}:{p['data_type']}"
                           for p in ports["out"]))
        tools.append({
            "name": f"fylite_{name}",
            "description": (f"{doc['fylite:title']}. Ports: {sig}. "
                            f"Entry: {doc['fylite:entry']}."
                            + _response_note(doc)
                            + _reduced_tier_note(doc)),
            "input_schema": _entry_input_schema(
                doc["fylite:entry"], doc.get("fylite:argument_shapes")),
        })
    return tools


def _response_note(doc: dict) -> str:
    """The declared response envelope, in the description a caller reads.

    ★``FR-HOST-002`` forbids presenting a batch task as an interactive one.
    On a tool face that rule has to be visible BEFORE the call, or the caller
    blocks on a twenty-minute scan waiting for an answer it expected in
    milliseconds.
    """
    r = doc.get("fylite:response") or {}
    tier = r.get("tier")
    if not tier:
        return ""
    if r.get("budget_ms"):
        return f" Response: {tier}, budget {r['budget_ms']} ms."
    return (f" Response: {tier} — no interactive budget; run it stepwise and "
            "do not wait on it as if it were interactive.")


def _reduced_tier_note(doc: dict) -> str:
    """The D-2 statement — what this tool answers and where it is NOT
    equivalent to the requirement it reduces — appended to the description a
    caller reads BEFORE choosing the tool.

    ★★Not copied: the manifest declares WHICH tool it is (``fylite:tool``)
    and the sentences come from :data:`fylite.scenario.TOOLS`, the register
    that ``test_scenario.py`` already holds against FYL-DESIGN-07 §8 row for
    row.  A caveat pasted into twelve manifests would drift from that table
    on the first edit, and the drift would be invisible — a stale caveat
    reads exactly like a current one.

    ★It is on the DESCRIPTION rather than only in the result's
    ``provenance`` because the two answer different questions: provenance
    travels with a number that has already been computed, and this is what a
    caller needs in order to decide whether to compute it at all.
    """
    key = doc.get("fylite:tool")
    if not key:
        return ""
    try:  # in-function: the engine's module surface stays stdlib (DE-COMP-03)
        from ..scenario import TOOLS
    except Exception:                    # noqa: BLE001 — a note, not a gate
        return ""
    t = TOOLS.get(key)
    if not t:
        return ""
    return f" Answers: {t['scope']} NOT equivalent where: {t['caveat']}"


def to_anthropic_tool(tool: dict) -> dict:
    """Neutral tool definition -> Anthropic Messages API ``tools[]`` entry."""
    return {"name": tool["name"], "description": tool["description"],
            "input_schema": tool["input_schema"]}


def to_openai_tool(tool: dict) -> dict:
    """Neutral tool definition -> OpenAI ``tools[]`` (function-calling) entry."""
    return {"type": "function",
            "function": {"name": tool["name"],
                         "description": tool["description"],
                         "parameters": tool["input_schema"]}}
