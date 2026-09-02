"""Generic service faces: result shaping, JSON-RPC 2.0, MCP stdio.

The tool plane that exposes the package to external callers
(SP-REPORT-15).  Physics stays out; the fylite-specific *content* comes
from :mod:`.manifest`, and physics entry points are imported inside the
handlers so this module's import surface stays stdlib.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from . import handles
from .manifest import (llm_tools, load_manifests, manifest_catalog,
                       resolve_entry)


# --------------------------------------------------------------------------- #
# Generic service faces (non-physics, converged into the engine)
#
# The engine is the package's one non-physics substrate: call lifecycle,
# provenance, versioning — and, below, the generic tool faces that expose the
# package to external callers: LLM-facing result shaping, the JSON-RPC 2.0
# stdio service, and the MCP stdio server (SP-REPORT-15 tool plane).  Physics
# stays out; the fylite-specific *content* (which artifacts exist, their fyo
# typing) stays in :mod:`fylite.engine.manifest` — these faces only consume it, via
# in-function imports so the engine's module-level import surface stays stdlib.
# --------------------------------------------------------------------------- #

# ---- result shaping (summary + artifact-by-reference) ---------------------- #

#: lists no longer than this whose items are all plain scalars pass through
_SHAPE_MAX_INLINE = 16


#: ★★``json.dumps`` writes ``Infinity`` / ``NaN`` for a non-finite float, and
#: those are **not JSON** — RFC 8259 has no such literals, so a strict client
#: (which is what an MCP host is) rejects the whole message rather than one
#: field.  It is not hypothetical: ``vstab`` reports ``margin = inf`` for a
#: stable equilibrium, which is the correct physical answer and would have
#: made the tool result unparseable.  They travel as their own names, in
#: quotes: a reader can still tell an infinite margin from a missing one,
#: which ``null`` would not allow.

def _json_number(v: float):
    import math
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    return v


def _array_summary(arr, ref: str | None = None) -> dict:
    import numpy as np
    out = {
        "@type": "fylite:ArraySummary",
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "sha256": hashlib.sha256(
            np.ascontiguousarray(arr).tobytes()).hexdigest(),
    }
    if arr.size and np.issubdtype(arr.dtype, np.number):
        finite = (arr[np.isfinite(arr)]
                  if np.issubdtype(arr.dtype, np.floating) else arr)
        if finite.size:
            out.update(min=float(np.min(finite)), max=float(np.max(finite)),
                       mean=float(np.mean(finite)))
    if ref is not None:
        #: ★the half a digest cannot do.  ``sha256`` proves that two
        #: summaries describe the same bytes; ``ref`` is how the caller GETS
        #: those bytes — into the next tool call as ``{"$ref": …}``, or into
        #: its own context, a few points at a time, through ``fylite_open``.
        out["ref"] = ref
    return out


def summarize(obj, *, max_inline: int = _SHAPE_MAX_INLINE, run_id=None,
              _path: str = ""):
    """Shape a result for an LLM tool caller: scalars and paths pass, bulk
    numeric data becomes a typed ``ArraySummary`` (shape / dtype / range /
    mean / sha256 — the by-reference philosophy of the DataArtifact applied to
    tool output; the digest ties the summary back to the real bytes), unknown
    leaves become ``repr``.  A result that dumps raw arrays floods the
    caller's context; one that silently drops them lies — this does neither.

    With ``run_id`` every summary also carries a ``ref``
    (``fylite://<run-id>/<port>``) naming where those bytes were stored.  The
    port paths are :func:`fylite.engine.handles.collect_arrays`' paths — one
    grammar for what is written and what is advertised.
    """
    import numpy as np
    kw = {"max_inline": max_inline, "run_id": run_id}
    ref = (handles.handle(run_id, _path) if run_id and _path else None)
    if isinstance(obj, dict):
        return {str(k): summarize(v, _path=f"{_path}.{k}" if _path else str(k),
                                  **kw)
                for k, v in obj.items()}
    if isinstance(obj, np.ndarray):
        return _array_summary(obj, ref if obj.size else None)
    if isinstance(obj, (list, tuple)):
        if (len(obj) <= max_inline
                and all(isinstance(v, (int, float, bool, str)) or v is None
                        for v in obj)):
            return list(obj)
        try:
            arr = np.asarray(obj)
        except Exception:
            arr = None
        if arr is not None and np.issubdtype(arr.dtype, np.number):
            return _array_summary(arr, ref if arr.size else None)
        return ([summarize(v, _path=f"{_path}[{i}]", **kw)
                 for i, v in enumerate(obj[:max_inline])]
                + [f"... (+{len(obj) - max_inline} more)"]
                if len(obj) > max_inline
                else [summarize(v, _path=f"{_path}[{i}]", **kw)
                      for i, v in enumerate(obj)])
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        return _json_number(obj)
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    return repr(obj)


def json_sanitize(obj):
    """Full-fidelity JSON coercion (numpy -> native, unknown leaves -> repr) —
    the raw counterpart of :func:`summarize`, used by the JSON-RPC invoke path
    where the caller wants the data, not a summary."""
    import numpy as np
    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_sanitize(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return json_sanitize(obj.tolist())
    if isinstance(obj, np.generic):
        return json_sanitize(obj.item())
    if isinstance(obj, float):
        return _json_number(obj)
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    return repr(obj)


# ---- JSON-RPC 2.0 stdio service (`fylite serve`) --------------------------- #
#
# A minimal process-boundary face so a non-Python consumer (or an sp-side
# RemoteBody) can discover and invoke fylite without importing it.  Framing
# mirrors the SpData sidecar convention (one JSON-RPC 2.0 message per line);
# the method vocabulary is fylite's own, ``fylite.``-prefixed — whether
# compute invocation should ride a platform-standard envelope instead is an
# open platform decision (SP-REPORT-15 OI-4 / T-0.4).  Methods:
# ``fylite.describe`` / ``fylite.manifest`` / ``fylite.invoke``.

_RPC_PARSE_ERROR = -32700
_RPC_INVALID_REQUEST = -32600
_RPC_METHOD_NOT_FOUND = -32601
_RPC_INVALID_PARAMS = -32602
_RPC_EXECUTION_ERROR = -32000


def _rpc_error(rid, code: int, message: str, data=None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err}


def _rpc_result(rid, payload) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def handle_rpc_request(req: dict) -> dict:
    """One JSON-RPC request dict -> one response dict (pure; no I/O)."""
    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
        return _rpc_error(None, _RPC_INVALID_REQUEST,
                          "not a JSON-RPC 2.0 request")
    rid = req.get("id")
    method = req.get("method")
    params = req.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _rpc_error(rid, _RPC_INVALID_PARAMS, "params must be an object")

    if method == "fylite.describe":
        return _rpc_result(rid, manifest_catalog())

    if method == "fylite.manifest":
        name = params.get("name")
        docs = load_manifests()
        if name not in docs:
            return _rpc_error(rid, _RPC_INVALID_PARAMS,
                              f"unknown manifest {name!r}",
                              data={"known": sorted(docs)})
        return _rpc_result(rid, docs[name])

    if method == "fylite.invoke":
        entry = params.get("entry")
        kwargs = params.get("kwargs") or {}
        if not isinstance(entry, str) or not isinstance(kwargs, dict):
            return _rpc_error(rid, _RPC_INVALID_PARAMS,
                              "invoke needs entry:str and kwargs:object")
        try:
            fn = resolve_entry(entry)
        except (ValueError, ImportError, AttributeError) as e:
            return _rpc_error(rid, _RPC_INVALID_PARAMS,
                              f"cannot resolve entry: {e}")
        try:
            return _rpc_result(rid, json_sanitize(fn(**handles.deref(kwargs))))
        except Exception as e:  # boundary: every failure is a typed fault
            return _rpc_error(rid, _RPC_EXECUTION_ERROR, "invocation failed",
                              data={"type": type(e).__name__,
                                    "message": str(e)})

    return _rpc_error(rid, _RPC_METHOD_NOT_FOUND, f"unknown method {method!r}")


def serve_stdio(stdin=None, stdout=None) -> int:
    """Serve line-delimited JSON-RPC 2.0 until EOF (`fylite serve`)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            resp = _rpc_error(None, _RPC_PARSE_ERROR, f"parse error: {e}")
        else:
            resp = handle_rpc_request(req)
        stdout.write(json.dumps(resp) + "\n")
        stdout.flush()
    return 0


# ---- MCP stdio server (`fylite mcp`) --------------------------------------- #
#
# The LLM-native tool face: any MCP client can list and call fylite's
# capabilities.  Two tool groups, one source of truth: curated task-level
# tools (describe / run / inspect / plot) plus tools reflected from the
# manifest catalog (one per first-batch manifest, input schema reflected from
# the entry signature).  Results ride ``summarize``; tool-execution failures
# return ``isError: true``; protocol failures use JSON-RPC errors; stdout
# carries nothing but protocol messages.

_MCP_PROTOCOL_FALLBACK = "2024-11-05"

_MCP_CURATED = [
    {
        "name": "fylite_describe",
        "description": "The fylite capability catalog (JSON-LD): the "
                       "first-batch artifact manifests — efit/neo/tglf "
                       "compute artifacts, the kinetic-reconstruction "
                       "workflow, the EAST MDSplus data artifact — with "
                       "fyo-typed ports and entry points.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "fylite_run",
        "description": "Reconstruct one equilibrium (EAST 65x65, Rust "
                       "inverse) and return a shaped summary plus the g-file "
                       "written into out/. Modes: input= a measurement "
                       "document (IMAS-shaped JSON/YAML or JSON-LD normal "
                       "form; needs time_s); east=true reads the EAST MDSplus "
                       "trees through the est2/GUI_v5 path (needs network and "
                       "a machine deck; optional POINT / pressure kinetic "
                       "constraints); otherwise shot+time_s reads the "
                       "efit_east measurement nodes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "shot": {"type": "integer", "description": "shot number"},
                "time_s": {"type": "number", "description": "time [s]"},
                "input": {"type": "string",
                          "description": "measurement document "
                                         "(.json/.jsonld/.yaml)"},
                "east": {"type": "boolean",
                         "description": "read the EAST MDSplus trees "
                                        "(est2/GUI_v5 path)"},
                "server": {"type": "string",
                           "description": "(east) MDSplus server host"},
                "point": {"type": "boolean",
                          "description": "(east) POINT polarimeter "
                                         "constraint"},
                "pressure": {"type": "boolean",
                             "description": "(east) Thomson+TXCS pressure "
                                            "constraint"},
                "thomson_ne": {"type": "boolean",
                               "description": "(east, with point) pin the "
                                              "density spline with Thomson "
                                              "n_e points"},
                "probes": {"type": "boolean",
                           "description": "include the magnetic probes in the "
                                          "fit (false = flux-loop-only)"},
                "out": {"type": "string", "default": ".",
                        "description": "output directory for the g-file"},
            },
        },
    },
    {
        "name": "fylite_inspect",
        "description": "Read a result artifact and return it shaped: a GEQDSK "
                       "g-file (parsed; arrays become typed summaries) or a "
                       "JSON/JSON-LD document (e.g. a RunManifest or a "
                       "manifest/*.jsonld). Optional keys= selects fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "file to inspect"},
                "keys": {"type": "array", "items": {"type": "string"},
                         "description": "top-level fields to keep"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "fylite_open",
        "description": "Read the data behind a handle "
                       "(fylite://<run-id>/<port>, as carried by every "
                       "ArraySummary a run returns). Without index/head it "
                       "returns the summary plus up to 16 evenly spaced "
                       "samples; index= picks entries (an integer, a list of "
                       "integers, or one index per dimension for a 2-D map); "
                       "head= the first n. Use this to look at a profile "
                       "instead of inlining it — to FEED it to another tool, "
                       "pass {\"$ref\": \"fylite://…\"} as that tool's "
                       "argument and nothing is inlined at all.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string",
                        "description": "fylite://<run-id>/<port>"},
                "index": {"description": "an integer, a list of integers, or "
                                         "one index per dimension"},
                "head": {"type": "integer",
                         "description": "return the first n entries"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "fylite_gaps",
        "description": "What is NOT built, per scenario line, and what each "
                       "item waits on. An unbuilt capability has no function "
                       "and no tool here BY DESIGN — ask this before "
                       "concluding that a missing tool is an oversight, and "
                       "quote `blocked_on` rather than inventing a "
                       "workaround. Response: interactive, budget 1000 ms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "line": {"type": "string",
                         "description": "one of the four scenario lines; "
                                        "omit for all of them"},
            },
        },
    },
    {
        "name": "fylite_plot",
        "description": "Render a GEQDSK g-file flux map to PNG/JPG and "
                       "return the image path. Without out= the image goes "
                       "into a fresh run directory (never beside the input "
                       "file). Response: interactive, budget 5000 ms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gfile": {"type": "string"},
                "out": {"type": "string",
                        "description": "output image (default: inside the "
                                       "run directory)"},
            },
            "required": ["gfile"],
        },
    },
]


def list_mcp_tools() -> list[dict]:
    """Curated tools + tools reflected from the manifest catalog."""
    return _MCP_CURATED + llm_tools()


# ---- one reconstruction request, shared by both tool faces ---------------- #
#
# ★★`fylite run` and the MCP `fylite_run` tool each resolved the input mode
# themselves, and each resolved it into the signature of the EFIT driver that
# left with LICENSE 3.1 — so both raised `TypeError` on their first statement,
# in every mode.  FR-TOOL-003 says the tool face may not introduce a second
# execution path; two faces resolving the same modes independently is how one
# appears.  The mode logic proper is `recon_rs.reconstruct_input` (solver
# side); what lives here is the surface mapping — option names a caller types
# to the keywords the door takes — stated ONCE for both faces.

#: option name a tool caller uses -> the keyword the reconstruction door takes.
#: A flag whose value has to be reshaped (an error-bar pair, a ceiling) is
#: assembled below instead; everything that is a straight rename is here.
_RUN_DIRECT = {
    "server": "server",
    "point": "read_point",
    "point_window_ms": "point_window_ms",
    "point_fringe_gate": "point_fringe_gate",
    "pressure": "read_pressure",
    "thomson_ne": "read_thomson_ne",
    "probes": "probes",
}


def run_reconstruction(opts: dict) -> dict:
    """One reconstruction from the option set both tool faces accept.

    Modes, in the order they are tried: ``input`` (a measurement document,
    with ``time_s``), ``east`` (the est2/GUI_v5 path into the EAST MDSplus
    trees, with ``shot`` + ``time_s``), else a bare ``shot`` + ``time_s``
    through the ``efit_east`` measurement nodes.  Returns the result dict;
    nothing is written — see :func:`deliver_gfile`.
    """
    from ..scenario.analysis.recon_rs import reconstruct_input

    kw = {v: opts[k] for k, v in _RUN_DIRECT.items()
          if opts.get(k) is not None}
    if opts.get("point_sig"):
        kw["point_opts"] = {"signel": opts["point_sig"][0],
                            "sigpol": opts["point_sig"][1]}
    pressure_opts = {k: opts[o] for k, o in (("sigpre_frac", "pressure_sig"),
                                             ("te_ceiling", "te_ceiling"))
                     if opts.get(o) is not None}
    if pressure_opts:
        kw["pressure_opts"] = pressure_opts

    shot, time_s = opts.get("shot"), opts.get("time_s")
    if opts.get("east"):
        return reconstruct_input(shot, time_s, kind="east", **kw)
    #: everything above that reads a tree belongs to the est2/GUI_v5 path
    #: only.  The other two modes get the SOLVE's keywords alone — the
    #: router would raise on a stray one, which is right, but a mode that
    #: never accepted the option should not have to be told about it.
    solve = {k: v for k, v in kw.items()
             if k not in ("server", "read_point", "read_pressure",
                          "read_thomson_ne", "point_opts", "pressure_opts",
                          "point_window_ms", "point_fringe_gate")}
    if opts.get("input"):
        return reconstruct_input(opts["input"], time_s, kind="imas",
                                 shot=shot, **solve)
    return reconstruct_input(shot, time_s, kind="shot", **solve)


def deliver_gfile(res: dict, out) -> str:
    """Write the solved equilibrium into ``out`` as a g-file; return the path.

    ★The result is not a deck and never was — the kernel returns structured
    data and a g-file is what this layer converts it into (``fyo.as_geqdsk``
    -> ``io.geqdsk.write_geqdsk``).  Written here rather than by the solver so
    that the same result can also be delivered as an fyo document, a figure or
    a run manifest without the solve growing an opinion about which.
    """
    from .. import fyo
    from ..io import geqdsk
    name = geqdsk.gfile_name(res.get("shot"), res.get("time_s"))
    return str(geqdsk.write_geqdsk(fyo.as_geqdsk(res), Path(out) / name))


#: how many values one ``fylite_open`` answer may carry back into a caller's
#: context.  A handle exists so that bulk data does NOT travel in the
#: conversation; a reader that returns the whole profile when asked for "the
#: profile" would undo it.
_OPEN_MAX = 64


#: argument values that go into the manifest's ``config`` verbatim — the
#: knobs a reader needs to see.  Everything else (a measurement set, a
#: profile, an array that arrived by handle) is DIGESTED into ``inputs``
#: instead: a manifest that inlined it would be a copy of the data wearing
#: the name of a record.
def _split_call(arguments: dict) -> tuple[dict, dict]:
    config, inputs = {}, {}
    for k, v in (arguments or {}).items():
        if v is None or isinstance(v, (str, int, float, bool)):
            config[k] = v
        elif (isinstance(v, dict) and set(v) == {"$ref"}):
            #: ★a handle is the most useful config value there is: it names
            #: the run this one was built on, which is the lineage edge.
            config[k] = v["$ref"]
        elif (isinstance(v, (list, tuple)) and len(v) <= 8
              and all(isinstance(x, (str, int, float, bool)) or x is None
                      for x in v)):
            config[k] = list(v)
        else:
            inputs[k] = v
    return config, inputs


def deliver_result(result, *, run=None, call: dict | None = None):
    """Shape a tool result for its caller, storing bulk arrays in a run
    directory so every summary carries a resolvable handle.

    ★★This is what makes a handle worth having: it is applied to EVERY tool
    that returns arrays, not only to a reconstruction.  A face where one tool
    hands back references and the rest hand back walls of numbers gives a
    caller no way to compose them — and composition (this run's profiles into
    that solver) is the entire reason the tool plane exists.

    ``call`` — ``{"tool", "entry", "arguments"}`` — turns the delivery into a
    RECORDED one: the run directory also gets ``manifest.json`` (code
    revision, environment fingerprint, digested inputs, hashed artifacts) and
    ``acceptance.json`` (the four-state verdict).  That is ``FR-DATA-003``,
    which until now existed only as machinery: :func:`fylite.engine.
    build_manifest` and :func:`fylite.engine.deliver` had **no caller outside
    the test suite**, so not one run of this package ever emitted the record
    its own requirement asks for.

    ★Without ``call`` — a lookup rather than a computation, e.g. reading a
    g-file back — nothing is recorded, and a result with nothing bulky in it
    does not even open a run directory: a catalog query would otherwise leave
    one behind per call, and a run root full of empty runs is a run root
    nobody prunes.
    """
    arrays = handles.collect_arrays(result) if isinstance(
        result, (dict, list, tuple)) else {}
    if not arrays and run is None and call is None:
        return summarize(result)
    run = run or handles.new_run()
    rid = handles.run_id_of(run)
    if isinstance(result, dict):
        result = {**result, "run": rid, "run_dir": str(run)}
    payload = summarize(result, run_id=rid)
    handles.store(run, result, payload)
    if call is not None:
        _record_run(run, result, call)
    return payload


def _acceptance_for(call: dict) -> dict | None:
    """The acceptance criteria the called capability declares, or ``None``.

    ★``None`` means「this call ran no published capability」and leaves the
    shipped defaults in place; it does NOT mean「no criteria」.  A published
    capability that declares none is a gap, and
    ``test_every_capability_declares_its_acceptance_criteria`` is where that
    shows up rather than here.
    """
    name = call.get("artifact")
    tool = str(call.get("tool") or "")
    if not name and tool.startswith("fylite_"):
        name = tool[len("fylite_"):]
    doc = load_manifests().get(name)
    if not doc:
        return None
    crit = doc.get("fylite:acceptance")
    return dict(crit) if isinstance(crit, dict) else None


def _record_run(run, result, call: dict) -> None:
    """Write the run manifest + acceptance verdict beside the result."""
    from . import provenance
    config, inputs = _split_call(call.get("arguments") or {})
    config = {k: v for k, v in
              (("tool", call.get("tool")), ("entry", call.get("entry")))
              if v is not None} | {"arguments": config}
    artifacts = [p for p in sorted(Path(run).iterdir())
                 if p.is_file() and p.name != "manifest.json"]
    manifest = provenance.build_manifest(
        result if isinstance(result, dict) else {"result": result},
        config=config, inputs=inputs, artifacts=artifacts,
        #: ★★The criteria are the CAPABILITY's, read off its own manifest.
        #: Until now every tool was scored against the reconstruction's three
        #: (`terror`/`chi_pressure`/`converged`), so a 0-D discharge and a
        #: transport march both came back `unevaluated` — truthfully, but for
        #: the wrong reason: not「this run had nothing to score」but「nobody
        #: had said what to score it on」.  Those are different facts and a
        #: caller can act on only one of them.
        thresholds=_acceptance_for(call),
        trace=(result.get("run_trace") if isinstance(result, dict) else None))
    manifest.write(Path(run) / "manifest.json")
    (Path(run) / "acceptance.json").write_text(
        json.dumps(manifest.acceptance, indent=1))
    #: ★and the session's own record of what it did: one node per recorded
    #: run, edges derived from the handles this call was given.  A session
    #: that ends leaves a flow someone can re-read and re-run, not a chat log.
    from . import ledger
    ledger.record(run, call)


def _mcp_run_tool(args: dict, call: dict | None = None):
    """One reconstruction, delivered into a fresh run directory.

    Returns the SHAPED payload (not the raw result): scalars inline, arrays as
    typed summaries carrying ``fylite://`` handles, the g-file as a path.  The
    arrays themselves are written beside it, so the next call can take them by
    reference instead of by value.
    """
    run = handles.new_run()
    res = run_reconstruction(args)
    res["gfile"] = deliver_gfile(res, args.get("out") or run)
    return deliver_result(res, run=run, call=call)


def _mcp_open_tool(args: dict):
    import numpy as np
    ref = args["ref"]
    value = handles.resolve(ref)
    if not isinstance(value, np.ndarray):
        return {"ref": ref, "value": value}

    index, head = args.get("index"), args.get("head")
    if index is not None:
        idx = index if isinstance(index, (list, tuple)) else [index]
        if value.ndim > 1 and len(idx) == value.ndim:
            return {"ref": ref, "index": list(idx),
                    "value": float(value[tuple(int(i) for i in idx)])}
        if value.ndim > 1:
            raise ValueError(
                f"{ref} is {value.ndim}-D {list(value.shape)}: pass one index "
                "per dimension")
        taken = [int(i) for i in idx][:_OPEN_MAX]
        return {"ref": ref, "index": taken,
                "value": [float(value[i]) for i in taken]}
    if value.ndim > 1:
        #: ★a 2-D map has no useful "first n"; it has a summary and a
        #: question about WHERE, which the caller has to answer.
        return {"ref": ref, "summary": _array_summary(value, ref),
                "note": f"{value.ndim}-D {list(value.shape)}: pass index="
                        "[i, j] for one point, or hand the whole map to "
                        'another tool as {"$ref": "' + ref + '"}'}
    if head is not None:
        n = max(0, min(int(head), _OPEN_MAX, value.size))
        return {"ref": ref, "index": list(range(n)),
                "value": [float(v) for v in value[:n]]}
    n = min(_SHAPE_MAX_INLINE, value.size)
    take = [int(round(i * (value.size - 1) / max(1, n - 1)))
            for i in range(n)] if n > 1 else [0]
    return {"ref": ref, "summary": _array_summary(value, ref),
            "index": take, "sample": [float(value[i]) for i in take]}


def _mcp_gaps_tool(args: dict):
    """The unbuilt capabilities, per line, with what each waits on.

    ★★``scenario.control.gaps()`` and ``scenario.analysis.gaps()`` have been
    the honest half of this package's coverage story from the start — an
    unbuilt capability gets no function, so the register is the only place it
    is visible.  The skill told a caller to ask for it and the tool face had
    no way to.  A model that cannot see the gap list reads a missing tool as
    an oversight and invents a workaround, which is the one failure this
    register exists to prevent.
    """
    from .. import scenario
    want = args.get("line")
    lines = [want] if want else sorted(scenario.LINES)
    out = {}
    for line in lines:
        if line not in scenario.LINES:
            raise ValueError(f"unknown line {line!r}; have "
                             f"{sorted(scenario.LINES)}")
        fn = getattr(getattr(scenario, line), "gaps", None)
        #: ★a line with no register is not a line with no gaps: it says so
        #: rather than reporting an empty list, which would read as "nothing
        #: missing here".
        out[line] = list(fn()) if fn else "no gap register on this line"
    return out


def _mcp_inspect_tool(args: dict):
    path = Path(args["path"])
    suffix = path.suffix.lower()
    if suffix in (".json", ".jsonld"):
        doc = json.loads(path.read_text())
    elif suffix in (".yaml", ".yml"):
        import yaml
        doc = yaml.safe_load(path.read_text())
    else:
        from ..io.geqdsk import read_geqdsk
        doc = read_geqdsk(str(path))
    keys = args.get("keys")
    if keys and isinstance(doc, dict):
        doc = {k: doc.get(k) for k in keys}
    return doc


def _mcp_plot_tool(args: dict, call: dict | None = None):
    """Render a flux map into a run directory (or an explicit ``out``).

    ★★The default used to be ``<gfile>.png`` — beside the INPUT.  On a tool
    face that is the same defect ``--out .`` was for ``fylite run``, one step
    worse: the g-file a model hands this tool is usually a path inside the
    user's own checkout, so the render lands in their working copy, with
    nothing recording who wrote it.  (Measured: a single probe call left a
    217 kB PNG in ``tests/data/synthetic/``.)  Unset, it goes to a fresh run
    directory like every other product of a call.
    """
    from ..plot import plot_gfile
    gfile = args["gfile"]
    run = handles.new_run()
    out = args.get("out") or str(Path(run) / (Path(gfile).name + ".png"))
    return deliver_result({"gfile": gfile, "plot": plot_gfile(gfile, out)},
                          run=run, call=call)


def mcp_entry_for_tool(tool_name: str) -> str:
    """Reflected tool name (``fylite_<manifest>``) -> its manifest entry."""
    name = tool_name.removeprefix("fylite_")
    return load_manifests()[name]["fylite:entry"]


def call_mcp_tool(name: str, args: dict) -> dict:
    """Execute one tool; returns the MCP ``tools/call`` result payload.
    Raises ``KeyError`` for an unknown tool (protocol-level error).

    ★★Whether the tool EXISTS is decided here, before anything runs, and the
    ``KeyError`` that says so is raised outside the execution guard.  It used
    to be raised inside it, under a bare ``except KeyError: raise`` — so a
    ``KeyError`` from the physics (``fylite_tglf`` with an incomplete deck
    raises ``KeyError('NS')``; ``fylite_efit`` raises ``KeyError('brsp')``)
    escaped as the SAME protocol error, and the caller was told
    ``unknown tool 'fylite_tglf'`` — word for word what it is told about a
    tool that does not exist.  A model reading that concludes the capability
    is not there and stops asking for it, which is the most expensive wrong
    answer this face can give.
    """
    if name not in _tool_names():
        note = _not_executable(name)
        if note is None:
            raise KeyError(name)
        #: ★published but not callable: that is a different fact from "no
        #: such tool", and the caller can only act on the difference if it
        #: is told which one it hit.
        return {"content": [{"type": "text",
                             "text": json.dumps({"error": "NotExecutable",
                                                 "message": note})}],
                "isError": True}
    try:
        #: ★arguments are dereferenced HERE and nowhere deeper: a handle is a
        #: tool-face convenience, and the physics layer must not learn about
        #: it (FYL-SDD-01 DE-COMP-03 — the mechanism knows about transport,
        #: not about what is being transported).
        #: ★the record keeps the arguments AS THE CALLER WROTE THEM — a
        #: handle stays a handle in the manifest's config, which is the
        #: lineage edge to the run it came from.  Dereferencing first and
        #: recording second would replace that edge with a copy of the data.
        raw = dict(args) if isinstance(args, dict) else args
        args = handles.deref(args)
        if name == "fylite_describe":
            payload = manifest_catalog()
        elif name == "fylite_run":
            payload = _mcp_run_tool(
                args, {"tool": name, "arguments": raw, "artifact": "efit",
                       "entry": "fylite.engine.serve:run_reconstruction"})
        elif name == "fylite_open":
            payload = _mcp_open_tool(args)
        elif name == "fylite_gaps":
            payload = _mcp_gaps_tool(args)
        elif name == "fylite_inspect":
            payload = deliver_result(_mcp_inspect_tool(args))
        elif name == "fylite_plot":
            payload = _mcp_plot_tool(
                args, {"tool": name, "arguments": raw, "artifact": "efit",
                       "entry": "fylite.plot:plot_gfile"})
        else:
            entry = mcp_entry_for_tool(name)
            payload = deliver_result(
                resolve_entry(entry)(**args),
                call={"tool": name, "entry": entry, "arguments": raw})
    except Exception as e:  # boundary: execution failure -> isError result
        return {"content": [{"type": "text",
                             "text": json.dumps({"error": type(e).__name__,
                                                 "message": str(e)})}],
                "isError": True}
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, default=str)}],
            "isError": False}


def _tool_names() -> set:
    return {t["name"] for t in list_mcp_tools()}


def _not_executable(name: str) -> str | None:
    """The reason a PUBLISHED capability is not callable, or ``None`` when the
    name is simply unknown."""
    doc = load_manifests().get(name.removeprefix("fylite_"))
    if not doc or doc.get("fylite:executable") is not False:
        return None
    return (doc.get("fylite:executable_note")
            or f"{name} is published but not callable")


# ---- MCP resources: the records a session leaves behind ------------------- #
#
# ★★``tools`` was the only capability this server declared, so everything a
# run produced could only come back as a tool RESULT — which means through the
# caller's context.  The records (a run manifest, a four-state verdict, the
# session ledger) are exactly the things a caller wants to read ON DEMAND and
# rarely: `resources` is the channel for that, and it is the other half of the
# handle idea — one names data for another tool, this one names a record for a
# reader.

#: what a run directory publishes, and as what.  Arrays are NOT here: they
#: are data, they are addressed by handle, and a caller reads them through
#: ``fylite_open`` a few points at a time rather than as a blob.
_RESOURCE_FILES = {
    "manifest.json": ("run manifest (code / environment / inputs / artifacts)",
                      "application/json"),
    "acceptance.json": ("four-state acceptance verdict", "application/json"),
    "result.json": ("the shaped result, with handles", "application/json"),
    "ledger.jsonld": ("session ledger — a workflow-ir instance",
                      "application/ld+json"),
}

#: a listing is a page in someone's context, not a database dump
_RESOURCE_LIMIT = 200


def list_mcp_resources() -> list[dict]:
    """Every record under the run root, newest run first."""
    root = handles.runs_root()
    if not root.is_dir():
        return []
    out = []
    for session in sorted(root.iterdir(), reverse=True):
        if not session.is_dir():
            continue
        led = session / "ledger.jsonld"
        if led.is_file():
            desc, mime = _RESOURCE_FILES["ledger.jsonld"]
            out.append({"uri": f"fylite://{session.name}/ledger.jsonld",
                        "name": f"{session.name} ledger",
                        "description": desc, "mimeType": mime})
        for run in sorted(session.iterdir(), reverse=True):
            if not run.is_dir():
                continue
            for fname, (desc, mime) in _RESOURCE_FILES.items():
                if fname == "ledger.jsonld" or not (run / fname).is_file():
                    continue
                out.append({"uri": f"fylite://{run.name}/{fname}",
                            "name": f"{run.name} {fname}",
                            "description": desc, "mimeType": mime})
            if len(out) >= _RESOURCE_LIMIT:
                return out[:_RESOURCE_LIMIT]
    return out[:_RESOURCE_LIMIT]


def read_mcp_resource(uri: str) -> dict:
    """One record, as text.  ``fylite://<run-or-session>/<file>``."""
    who, _, fname = str(uri).removeprefix(handles.SCHEME).partition("/")
    if fname not in _RESOURCE_FILES:
        raise LookupError(
            f"{uri}: this face serves the records {sorted(_RESOURCE_FILES)}; "
            "data is addressed by handle and read with fylite_open")
    root = handles.runs_root()
    candidates = [root / who / fname] + [p / fname
                                         for p in sorted(root.glob(f"*/{who}"))]
    for p in candidates:
        if p.is_file():
            return {"uri": str(uri), "mimeType": _RESOURCE_FILES[fname][1],
                    "text": p.read_text()}
    raise LookupError(f"{uri}: no {fname} under {who} in {root}")


def handle_mcp_message(msg: dict):
    """One MCP message -> a response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _rpc_error(None, _RPC_INVALID_REQUEST,
                          "not a JSON-RPC 2.0 message")
    method = msg.get("method")
    rid = msg.get("id")
    params = msg.get("params") or {}

    if rid is None:  # notification (e.g. notifications/initialized): no reply
        return None

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion",
                                          _MCP_PROTOCOL_FALLBACK),
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "fylite",
                           "version": manifest_catalog()["fylite:version"]},
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        tools = [{"name": t["name"], "description": t["description"],
                  "inputSchema": t["input_schema"]}
                 for t in list_mcp_tools()]
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"resources": list_mcp_resources()}}
    if method == "resources/read":
        try:
            content = read_mcp_resource((params or {}).get("uri", ""))
        except LookupError as e:
            return _rpc_error(rid, _RPC_INVALID_PARAMS, str(e))
        return {"jsonrpc": "2.0", "id": rid, "result": {"contents": [content]}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = call_mcp_tool(name, args)
        except KeyError:
            return _rpc_error(rid, _RPC_INVALID_PARAMS,
                              f"unknown tool {name!r}")
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    return _rpc_error(rid, _RPC_METHOD_NOT_FOUND, f"unknown method {method!r}")


def mcp_stdio(stdin=None, stdout=None) -> int:
    """Serve MCP over stdio until EOF (`fylite mcp`; stdout carries only
    protocol messages)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            resp = _rpc_error(None, _RPC_PARSE_ERROR, f"parse error: {e}")
        else:
            resp = handle_mcp_message(msg)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0
