"""Execution engine: call-lifespan substrate + run provenance + iteration versioning.

Three concerns share this module because they form one **engine** around a run —
how a call executes, how its result is delivered/audited, and how an iterative
run is versioned:

* :class:`ExecutionBody` — the domain-neutral execution substrate (below);
* **run provenance + structured delivery** (K-17): :class:`RunManifest`,
  four-state :func:`acceptance`, versioned non-overwriting :func:`deliver`;
* **immutable iteration versioning + staleness** (K-15): write-once
  :func:`snapshot`, the :class:`Staleness` dependency graph, :func:`convergence_panel`.

The :class:`ExecutionBody` substrate below names nothing about EFIT/KEFIT; the
provenance/versioning helpers reference the bundled-library paths (:mod:`._paths`)
only to fingerprint the environment.

:class:`ExecutionBody` is the reusable substrate for wrapping any legacy Fortran/C ``.so`` that

* keeps **global (COMMON-block / module / file-static) state**, so it must run
  *one call at a time in a pristine process*, and
* may **abort the whole process** on error (Fortran ``STOP``, ``exit()``),

by running every call in a **fresh forked child**: the child inherits the parent
interpreter but *not* a loaded library, so its global state starts pristine, and
a ``STOP`` in the child aborts only that child.  A typed result is returned
through **shared-memory buffers** (``multiprocessing.RawArray``, inherited across
the fork) — no output-file text round-trip.

:class:`ExecutionBody` is the single handle (kefit's own solver stack in
:mod:`fylite.run` is a thin adapter over it), managing a call's **whole
lifespan** — workdir provisioning, execution, timeout, log capture, failure
surfacing, and reclamation.

It is named for and implements the **ExecutionBody** protocol (as defined by
SpModel's ``sp.core.execution.ExecutionBody``, SPM-ADR-111 D1/D2/D3/D6/D7 +
SPM-ADR-112 D4): a *persistent environment scope* (``cold`` → ``ready`` →
``poisoned``: the pinned tables / COW holder, consumed by one call at a time when
:attr:`ExecutionBody.exclusive_environment`) plus a *per-call scope* driven through
**six phases** — P-1 :meth:`~ExecutionBody.interpret_inputs`, P-2
:meth:`~ExecutionBody.provision` (acquire the per-call lease, :class:`CallScope`), P-3
:meth:`~ExecutionBody.stage`, P-4 :meth:`~ExecutionBody.execute`, P-5
:meth:`~ExecutionBody.interpret_outputs` + :meth:`~ExecutionBody.harvest` (extract the
outcome + decide the :class:`Disposition` — forced ``RETAIN`` on failure), P-6
:meth:`~ExecutionBody.dispose` (release the lease; always runs).
:meth:`ExecutionBody.invoke` is the six-phase driver (:meth:`~ExecutionBody.ainvoke`
is the awaitable form off the event loop); it returns a :class:`_CallResult`
carrying a :class:`CallTrace` (disposition / log / environment identity / duration).

**This module is the protocol's reference implementation case — and its
validator — while importing nothing from the sp / fy ecosystem.**  ``sp.core``
defines the six-phase contract but ships no native-library body; this module is
that body, so it is where the contract gets exercised against a real
non-reentrant Fortran solver.  Two rules follow, and both are enforced by
``python/tests/test_protocol_conformance.py``:

* **Support.** Every protocol member of the call contract is implemented here
  under the upstream name with the upstream semantics — the phase set, the
  ``cold``/``ready``/``poisoned`` environment scope with its idempotent
  :meth:`~ExecutionBody.acquire` / :meth:`~ExecutionBody.close` pair and fail-fast
  poisoning, the three-value :class:`Disposition` decided at harvest and forced to
  ``RETAIN`` whenever any phase raises, the single-in-flight guard, and the
  provenance pair (:meth:`~ExecutionBody.environment_identity` /
  :meth:`~ExecutionBody.last_disposition`).  The parts of the upstream
  ``ExecutionBody`` that presuppose an ``Operator`` / ``RuntimeBackend`` (compile
  and artifact caching, port validation) are **declared not-applicable** rather
  than faked — see ``PROTOCOL`` below, which carries that ruling as data.
* **Independence.** Nothing here imports ``sp`` (or ``fytok``): the protocol is
  restated locally as :data:`PROTOCOL` and checked against this module, so the
  suite runs on stdlib + a stand-in ``libc``.  The conformance suite additionally
  cross-checks :data:`PROTOCOL` against the real ``sp.core.execution`` **only when
  it happens to be importable**, and skips otherwise — drift is detected where the
  ecosystem is present without ever becoming a dependency.

Three execution modes:

* **fork-per-call** — :meth:`ExecutionBody.invoke` with no holder.  The parent never
  loads the library; each call forks a child that loads it fresh, runs the
  caller's ``child(lib)`` closure, and captures a result.  Simplest and fully
  isolated.
* :meth:`ExecutionBody.cow` → :meth:`ExecutionBody.invoke` — **load-once, fork-per-solve**
  (copy-on-write).  A holder process loads the library + its large read-only
  tables once; each solve forks a child that inherits them via COW (never
  re-read).  Use when a solve re-reads a large, input-independent dataset that
  dominates its cost.
* **pin** — a large read-only dataset staged on tmpfs once at construction, read
  at RAM speed by every later call.  Subclass to add a domain ``run`` / ``solve``
  (see ``fylite.run.EFITSession``).

Plus small helpers: :meth:`ExecutionBody.tmpfs_dir` (a RAM-backed work area), :meth:`ExecutionBody.stage_dir`
(pin a data directory in RAM), :meth:`ExecutionBody.alloc_buffers` (the shared-memory result
buffers), and :meth:`ExecutionBody.reap_orphans` (clear tmpfs dirs a killed process stranded).

Call-lifespan management is deliberate throughout: private workdirs come from
:meth:`ExecutionBody.scratch` (PID-tagged, tracked), are consumed by the flow or
detached via :meth:`ExecutionBody.release` (kept-on-purpose / post-mortem dirs), and
whatever is still tracked is swept by :meth:`ExecutionBody.close` (also run at exit) —
while :meth:`ExecutionBody.reap_orphans` covers dirs stranded across a SIGKILL.  Every call is
timeout-bounded (a hung slice child is killed, a wedged holder terminated), a
first-solve library abort fails fast with the captured log
(:meth:`_CallResult.tail`), and ``close()`` releases the holder, the pipe, and
the staged copy.

To wrap a new library, supply: its ``.so`` path; the stdin bytes its entry
prompts expect (if any); a buffer spec ``{name: (typecode, count)}``; and small
closures that push inputs / call the entry / copy the result into the buffers.
Everything else — fork, timeout, crash isolation, RAM work area — is here.

CAVEAT (fork start method): closures and callables are passed to child/holder
processes as ``Process`` *arguments*, which under the ``fork`` context are shared
by memory copy (never pickled), so closures are fine there.  Data sent to a live
holder over its :class:`~multiprocessing.Pipe` (the per-request payload) *is*
pickled — keep it plain (dict / tuple / str), not a closure.

Package layout (2026-08-10: the single 3.4k-line module split; the import
surface ``fylite.engine.<name>`` is unchanged — everything below is
re-exported here):

* :mod:`.body` — the ExecutionBody substrate (concern 1);
* :mod:`.provenance` — RunManifest / acceptance / deliver (concern 2);
* :mod:`.versioning` — write-once iteration snapshots (concern 3);
* :mod:`.serve` — result shaping + JSON-RPC + MCP (generic service faces);
* :mod:`.manifest` — artifact-manifest machinery + LLM tool schemas;
* :mod:`.handles` — the run root + data handles (``fylite://<run-id>/<port>``);
* :mod:`.ledger` — the session ledger (a ``workflow-ir/2.0`` instance);
* :mod:`.documents` — document / signal / channel-map mechanics;
* :mod:`.cli` — the argparse builder over ``_cli.json``;
* :mod:`.fitters` — profile representation (the interpolant, generic numerics);
* :mod:`._util` — helpers shared by two or more of the above.

Only :mod:`.serve` and :mod:`.cli` reach into the physics modules, and only
inside their handlers — the engine's own import surface stays stdlib.
"""

from . import (  # noqa: F401  (submodules are part of the public surface)
    body, cli, documents, fitters, handles, ledger, manifest,
    provenance, serve, versioning,
)
from .body import (
    PROTOCOL, CallCancelled, CallScope, CallTimeout, CallTrace,
    ConcurrentInvocationError, DELIVER, Disposition, EngineError,
    EnvironmentAcquireError, ExecuteError, ExecutionBody, PoisonedBodyError,
    RECLAIM, RETAIN, RunTrace,
)
from .cli import (
    CLI_SPEC_PATH, build_cli, cli_main, load_cli_spec,
)
from .documents import (
    apply_channel_map, invert_channel_map, load_document, signal_at,
)
from .fitters import KINDS as PROFILE_KINDS  # noqa: F401
from .fitters import ProfileEvaluator, fit as fit_profile
from .handles import (
    RUN_ENV, deref, find_run, new_run, resolve as resolve_handle, runs_root,
)
from .manifest import (
    ENVIRONMENT_PATH, MANIFEST_DIR, SEMANTIC_KEYS, SPEC_DIR, environment,
    is_semantic, llm_tools,
    load_manifests, load_spec, manifest_catalog, resolve_entry, seal_manifest,
    seal_manifests, strip_semantic, to_anthropic_tool, to_openai_tool,
    validate_projection, validate_structure, write_manifests,
)
from .provenance import (
    CONDITIONAL, DEFAULT_THRESHOLDS, FAIL, PASS, RunManifest, UNEVALUATED,
    acceptance, build_manifest, deliver, digest, env_fingerprint, git_rev,
    record_decision, reserve_dir,
)
from .serve import (
    call_mcp_tool, deliver_result, handle_mcp_message, handle_rpc_request,
    json_sanitize, list_mcp_resources, list_mcp_tools, mcp_entry_for_tool,
    mcp_stdio, read_mcp_resource, serve_stdio, summarize,
)
from .versioning import (
    STAGES, SnapshotError, Staleness, convergence_panel, list_snapshots,
    load_snapshot, snapshot,
)
from ._util import sha256_file

# Internal symbols with live consumers (tests patch/construct them); kept
# importable from the package root so the pre-split call sites stand.
from .body import _CallResult, _Process  # noqa: F401

#: the package's public surface — everything else is internal
__all__ = [
    # execution substrate (the ExecutionBody protocol)
    "ExecutionBody", "CallScope", "CallTrace", "RunTrace", "Disposition",
    "RECLAIM", "RETAIN", "DELIVER", "PROTOCOL",
    # protocol error taxonomy (mirrors sp.core.execution's OperatorError family)
    "EngineError", "EnvironmentAcquireError", "PoisonedBodyError",
    "ConcurrentInvocationError", "ExecuteError", "CallTimeout", "CallCancelled",
    # run provenance + structured delivery
    "RunManifest", "acceptance", "build_manifest", "deliver", "reserve_dir",
    "record_decision", "sha256_file", "digest", "git_rev", "env_fingerprint",
    "PASS", "CONDITIONAL", "FAIL", "UNEVALUATED", "DEFAULT_THRESHOLDS",
    # immutable iteration versioning + staleness
    "Staleness", "SnapshotError", "STAGES", "snapshot", "load_snapshot",
    "list_snapshots", "convergence_panel",
    # the run root + data handles
    "RUN_ENV", "runs_root", "new_run", "find_run", "resolve_handle", "deref",
    # generic service faces
    "summarize", "json_sanitize", "deliver_result", "handle_rpc_request", "serve_stdio",
    "list_mcp_tools", "call_mcp_tool", "handle_mcp_message", "mcp_stdio",
    "mcp_entry_for_tool", "list_mcp_resources", "read_mcp_resource",
    # artifact manifests + LLM tool schemas
    "SPEC_DIR", "MANIFEST_DIR", "SEMANTIC_KEYS", "ENVIRONMENT_PATH",
    "environment", "is_semantic",
    "strip_semantic", "load_spec", "load_manifests", "manifest_catalog",
    "resolve_entry", "validate_structure", "validate_projection",
    "seal_manifest", "seal_manifests", "write_manifests", "llm_tools",
    "to_anthropic_tool", "to_openai_tool",
    # document / signal / channel-map mechanics
    "load_document", "signal_at", "apply_channel_map", "invert_channel_map",
    # CLI
    "CLI_SPEC_PATH", "load_cli_spec", "build_cli", "cli_main",
    # profile representation
    #: ★★`BackendError`, `backend`, `backend_names`, `backend_meta`,
    #: `declare_family`, `register_backend`, `families` and
    #: `BACKENDS_SPEC_PATH` are gone with `registry.py` (FYL-SDD-01
    #: DE-LOG-03, retired).  It was a generic name->factory map with three
    #: families, four built-ins and two consumers — and BOTH consumers had
    #: to branch on the name anyway, so it gave neither of them
    #: polymorphism.  A model is constructed where it is chosen.
    "ProfileEvaluator",
    #: ★`ProfileFitter`, `LinearFitter` and `PchipFitter` are gone with the
    #: `profile_fitter` backend family: the two "fitters" differed by the
    #: string they handed one class, so the family was a `kind=` argument
    #: wearing a registry.  `fit_profile(x, y, kind=...)` is that argument.
    "fit_profile", "PROFILE_KINDS",
]
