"""Execution substrate — the ExecutionBody protocol (engine concern 1).

The domain-neutral machine around one call: environment lease, workdir
lifecycle, the six phases, fork/COW execution, retries and deadlines.
No physics, and no fylite module beyond :mod:`._util`.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import enum
import logging
import multiprocessing as mp
import os
import random
import shutil
import threading
import time
import typing
import uuid
from dataclasses import dataclass
from pathlib import Path

from ._util import sha256_file


# --------------------------------------------------------------------------- #
# The ExecutionBody protocol, restated as data (the conformance target)
# --------------------------------------------------------------------------- #
#: The SpModel ``ExecutionBody`` protocol, restated **locally as data** so that
#: conformance is machine-checkable without importing ``sp`` (see the module
#: docstring's Independence rule).  ``python/tests/test_protocol_conformance.py`` walks
#: every entry here against this module, and — only when ``sp.core.execution``
#: happens to be importable — cross-checks the vocabulary against upstream so
#: drift is caught wherever the ecosystem is installed.
#:
#: Keys mirror the SPM-ADR-111 decision axes; ``not_applicable`` carries the
#: explicit ruling for the upstream members that presuppose an ``Operator`` /
#: ``RuntimeBackend`` — recorded with a reason rather than stubbed out, because a
#: fake compile step would validate nothing.
PROTOCOL: dict = {
    #: SPM-ADR-111 D1 — body identity + SPM-ADR-112 D4 manifest projection.
    "declarations": ("kind", "async_native", "exclusive_environment",
                     "manifest_kind", "needs_workdir"),
    #: D2 — environment scope: the state names are part of the contract.
    "environment_states": ("cold", "ready", "poisoned"),
    "environment_members": ("acquire", "close", "_acquire_environment",
                            "_close_environment"),
    #: D2/D3/D7 scope state, under the upstream attribute names.
    "scope_state_attrs": ("_env_state", "_env_error", "_call_guard",
                          "_in_flight", "_last_disposition"),
    #: D3 — the six call phases, in driver order: (phase id, method, 中文名).
    "phases": (
        ("P-1", "interpret_inputs", "解释"),
        ("P-2", "provision", "准备"),
        ("P-3", "stage", "装配"),
        ("P-4", "execute", "执行"),
        ("P-5", "interpret_outputs", "解释产出"),
        ("P-5", "harvest", "收割"),
        ("P-6", "dispose", "释放"),
    ),
    #: D3 — the three-value disposition vocabulary (values, not member names).
    "dispositions": ("reclaim", "deliver", "retain"),
    #: D3 — the driver entries and the guarantee-carrying helpers.
    "call_members": ("invoke", "ainvoke", "_begin_call", "_end_call",
                     "_dispose_safely"),
    #: D6 — what a call's provenance is assembled from.
    "provenance_members": ("environment_identity", "last_disposition",
                           "manifest_projection", "cache_identity"),
    #: D6 — keys every ``environment_identity()`` carries (subclasses extend).
    "identity_keys": ("body_kind", "body_class"),
    #: Error taxonomy: local name -> upstream ``sp.core.execution`` name.  The
    #: local base subclasses ``RuntimeError`` exactly as ``OperatorError`` does.
    "errors": {
        "EngineError": "OperatorError",
        "EnvironmentAcquireError": "EnvironmentAcquireError",
        "PoisonedBodyError": "PoisonedBodyError",
        "ConcurrentInvocationError": "ConcurrentInvocationError",
        "ExecuteError": "ExecuteError",
    },
    #: Upstream members deliberately NOT implemented here, with the ruling.
    "not_applicable": {
        "bind": "no Operator: there is no body-to-callable binding step",
        "compile": "no RuntimeBackend: a .so is loaded, never compiled",
        "execute_backend_spi": "P-4 here is fork/COW dispatch, not backend dispatch",
        "ensure_compiled": "no compiled artifact, hence no artifact cache",
        "cache_key": "no compile cache to key",
        "prepare_inputs": "no Operator ports to prepare inputs for",
        "InputValidationError": "no Operator.inports to reject inputs",
        "OutputValidationError": "no Operator.outports to reject outputs",
        "CompilerError": "no compile step that could fail",
    },
    #: Local extensions **beyond** the protocol — this body needs them for a
    #: non-reentrant native library; upstream has no equivalent, so they must not
    #: be mistaken for protocol members when reading this module as the reference
    #: case (and the cross-check must not demand them upstream).
    "local_extensions": {
        "environment_ready": "cheap non-raising probe of the D2 state",
        "poison": "mark the environment broken from inside a failed call",
        "restart": "replace a poisoned COW environment (see acquire's ruling)",
        "cow": "alternate constructor for a load-once holder body",
        "start_holder": "attach a COW holder to an existing body, in place",
        "warm": "pay the one-time table load explicitly, at startup",
        "scratch": "provision a tracked private workdir",
        "release": "detach a workdir from the close-time sweep",
        "reap_orphans": "clear tmpfs dirs a SIGKILLed process stranded",
        "stats": "call/failure/retry/restart/cancel counters",
        "alloc_buffers": "shared-memory result buffers across the fork",
        "stage_dir": "pin a read-only dataset on tmpfs",
        "tmpfs_dir": "resolve a RAM-backed work area",
        "on_deliver": "enact a DELIVER disposition at P-6",
    },
    #: Behavioural invariants the suite asserts by observation, not by
    #: introspection — the part of the contract that signatures cannot express.
    "invariants": {
        "I-1": "phases run in PROTOCOL['phases'] order, once per attempt",
        "I-2": "P-6 dispose always runs, including when an earlier phase raises",
        "I-3": "any phase raising forces the disposition to RETAIN (keep the scene)",
        "I-4": "acquire() is idempotent; a poisoned environment raises PoisonedBodyError",
        "I-5": "close() is idempotent and leaves a poisoned environment poisoned",
        "I-6": "an exclusive environment admits one in-flight call "
               "(ConcurrentInvocationError otherwise)",
        "I-7": "last_disposition() reports the disposition of the most recent call",
        "I-8": "no sp / fytok import anywhere in the implementing module",
    },
}


# --------------------------------------------------------------------------- #
# Protocol error taxonomy (mirrors the upstream OperatorError family)
# --------------------------------------------------------------------------- #
class EngineError(RuntimeError):
    """Base of the engine's invocation-scoped errors — the local counterpart of
    ``sp.core.execution.OperatorError`` (same ``RuntimeError`` base, so callers
    written against the pre-taxonomy ``RuntimeError`` behaviour still work)."""


class EnvironmentAcquireError(EngineError):
    """Environment acquisition failed (D2).  Acquisition failure poisons the
    body: every later :meth:`ExecutionBody.acquire` raises
    :class:`PoisonedBodyError` until a fresh environment is built."""


class PoisonedBodyError(EngineError):
    """A call was attempted on a body whose environment is poisoned (D2: never
    serve calls on a broken environment).  Here the usual cause is a COW holder
    that died on a solve — :meth:`ExecutionBody.restart` builds a fresh one."""


class ConcurrentInvocationError(EngineError):
    """Re-entrant call on a body already serving one (D7).  The COW pipe and the
    single-slot shared buffers are environment singletons; concurrency needs one
    body per worker, not one body shared."""


class ExecuteError(EngineError):
    """P-4 execution failed — the base of the two concrete execution faults
    below (a library abort surfaces as a not-ok :class:`_CallResult`, not an
    exception, so it is reportable rather than raised)."""


class CallTimeout(ExecuteError, TimeoutError):
    """A call exceeded its deadline and the in-flight child (or a wedged COW
    holder) was killed.  Subclasses :class:`TimeoutError` as well, so existing
    ``except TimeoutError`` callers keep working."""


class CallCancelled(ExecuteError):
    """A call was cancelled (its ``cancel_token`` fired) — the in-flight child
    was terminated before it finished.  Distinct from :class:`CallTimeout`
    (deadline) and a library abort (non-zero exit)."""


# --------------------------------------------------------------------------- #
# Per-call scope, disposition, trace (the ExecutionBody call contract, local)
# --------------------------------------------------------------------------- #
class Disposition(str, enum.Enum):
    """The call-workspace disposition decided at harvest (P-5) — the three-value
    vocabulary of ``sp.core.execution.Disposition``:

    * :attr:`RECLAIM` — remove the workspace at P-6 (a disposable private dir);
    * :attr:`RETAIN`  — keep it (caller-consumed, session-fixed, or the driver's
      forced retain-on-failure);
    * :attr:`DELIVER` — keep it AND flag it as a deliverable (a successful call
      whose workspace holds artifacts to be delivered downstream).

    Deliberate superset of upstream: the ``str`` mixin makes a member compare
    equal to its own value, so ``disposition == "retain"`` and JSON round-trips
    keep working while ``is Disposition.RETAIN`` and ``.value`` behave exactly as
    upstream's plain :class:`enum.Enum` does.
    """
    RECLAIM = "reclaim"
    DELIVER = "deliver"
    RETAIN = "retain"

    def __str__(self) -> str:                # keep f-strings/logs on the value
        return self.value


#: module-level aliases — the enum members under their historical names
RECLAIM = Disposition.RECLAIM
RETAIN = Disposition.RETAIN
DELIVER = Disposition.DELIVER


@dataclass
class CallScope:
    """The per-call lease (ExecutionBody CallScope, phase P-2 → P-6).

    Acquired by :meth:`ExecutionBody.provision`, staged by :meth:`ExecutionBody.stage`,
    consumed by :meth:`ExecutionBody.execute`, its ``disposition`` decided at
    :meth:`ExecutionBody.harvest`, and released by :meth:`ExecutionBody.dispose` — always,
    via the driver's ``finally``.  A subclass may carry extra prepared state
    (assign attributes in its ``provision``/``stage``); it is a plain per-call
    scratchpad, never shared between calls.
    """
    #: what to execute: the ``child(lib)`` closure (fork-per-call) or the
    #: picklable payload sent to a COW holder.  Local addition: upstream carries
    #: the resolved inputs on the ``Operator``, which does not exist here.
    request: object
    #: this call's work dir (already created)
    workdir: Path
    #: P-6 workspace disposition — :data:`RECLAIM` removes the dir (a private COW
    #: dir), :data:`RETAIN` keeps it (caller-consumed, session-fixed, or the
    #: driver's forced retain-on-failure)
    disposition: Disposition = RETAIN
    #: stable identity of this call, constant across retries (protocol field)
    call_id: str = ""
    #: whether the body created this workdir and may therefore reclaim it; False
    #: for a caller-supplied / session-fixed dir, which P-6 never removes
    owns_workdir: bool = False

    @property
    def reclaim(self) -> bool:
        return self.disposition == RECLAIM

    @property
    def deliver(self) -> bool:
        return self.disposition == DELIVER


@dataclass
class CallTrace:
    """Provenance of one call: the harvested workspace ``disposition``, a
    reference to the captured run ``log``, the executing ``environment_identity``
    (which library / holder ran it), the wall-clock ``duration_s``, a stable
    ``call_id`` (constant across retries), the number of ``attempts`` it took,
    and ``phase_timings`` (per-phase seconds) — enough to tie a call's trace to
    its delivery manifest and to observe where time went.

    Named ``CallTrace``, **not** ``RunTrace``, on purpose: upstream's
    ``sp.core.prov.RunTrace`` is the *operator-level* record (operator name/uuid,
    runtime, device, timestamps, input/output hashes, code version) and this is
    the *call-level* record.  The two intersect exactly in the D6 provenance pair
    — ``environment_identity`` and ``disposition`` — which is what an operator
    lifts from a body; same-name/different-shape would have invited silent drift.
    ``RunTrace`` remains a module-level alias for back-compat.
    """
    disposition: Disposition | str
    log: str
    environment_identity: dict | None = None
    duration_s: float | None = None
    call_id: str | None = None
    attempts: int | None = None
    phase_timings: dict | None = None


#: back-compat alias — this record's historical name (see :class:`CallTrace`)
RunTrace = CallTrace


@dataclass
class _CallResult:
    """Outcome of one :meth:`ExecutionBody.invoke`, with its :class:`CallTrace`."""
    exitcode: int
    flag: int              #: the int returned by the ``child`` closure (0 == no result)
    workdir: str
    log: str
    #: log tail captured before a private workdir was removed (ExecutionBody.invoke) —
    #: keeps diagnostics readable after the dir is gone
    cached_tail: str | None = None
    #: wall-clock seconds of the execute phase (P-4), stamped by the driver
    duration_s: float | None = None
    #: call provenance, set at harvest (P-5)
    trace: CallTrace | None = None

    @property
    def ok(self) -> bool:
        return self.exitcode == 0 and self.flag != 0

    @staticmethod
    def read_tail(path, n: int = 1500) -> str:
        """Last ``n`` chars of a run log, or a placeholder — never raises."""
        p = Path(path)
        try:
            return p.read_text(errors="replace")[-n:] if p.exists() else \
                "(no log captured)"
        except OSError:
            return "(log unreadable)"

    def tail(self, n: int = 1500) -> str:
        """Last ``n`` chars of the captured run log (for failure reports).
        Served from :attr:`cached_tail` when the workdir no longer exists."""
        if self.cached_tail is not None:
            return self.cached_tail[-n:]
        return self.read_tail(self.log, n)


# --------------------------------------------------------------------------- #
# The CHILD side of the fork boundary
# --------------------------------------------------------------------------- #
class _Process:
    """The program a forked process runs — everything on the CHILD side of the
    fork boundary (the mirror of :class:`ExecutionBody`, which is the parent side).

    An instance carries one child's wiring — run dir, log name, the stdin bytes
    its prompts consume — and is created in the parent, then memory-copied into
    the child by ``fork`` (never pickled).  It deliberately holds **no ExecutionBody
    reference**: child-side code cannot touch parent-side state (pipes, scratch
    ledger, staged dirs), and everything that crosses the process boundary is
    an explicit constructor/method argument — enumerable at the call site.

    Entries: :meth:`run` (fork-per-call child main, ``ExecutionBody.call``),
    :meth:`slice` (COW slice-child main) and :meth:`holder` (COW holder main,
    both ``ExecutionBody.cow``/``run``), over the shared :meth:`wire` prologue and
    :meth:`abort` crash epilogue.

    :attr:`lib` is **holder-process-local**: set once in the holder after
    ``CDLL``, inherited by its forked slice children via COW; never set in the
    parent (each process sees its own copy of the class state after fork).
    """

    lib = None      #: loaded CDLL — holder-process-local (see class docstring)

    #: resource.RLIMIT_* names accepted in an ExecutionBody(rlimits=...) dict
    _RLIMIT_NAMES = ("AS", "CPU", "DATA", "FSIZE", "NOFILE", "NPROC", "STACK")

    def __init__(self, rundir, log_name: str, stdin: bytes = b"",
                 rlimits: dict | None = None) -> None:
        self.rundir = str(rundir)
        self.log_name = log_name
        self.stdin = stdin
        self.rlimits = rlimits

    def apply_rlimits(self) -> None:
        """Apply per-child resource limits in the fork child (before the work).

        ``rlimits`` maps a short name (``AS``/``CPU``/``NOFILE``/…) to a soft
        limit (int) or an explicit ``(soft, hard)`` pair.  Best-effort: an
        unknown name or a limit the OS rejects is skipped, not fatal — a resource
        cap must not turn into a spurious call failure."""
        if not self.rlimits:
            return
        import resource
        for name, val in self.rlimits.items():
            key = getattr(resource, f"RLIMIT_{name}", None)
            if key is None:
                continue
            soft, hard = val if isinstance(val, tuple) else (val, val)
            try:
                resource.setrlimit(key, (int(soft), int(hard)))
            except (ValueError, OSError):
                pass

    def wire(self) -> None:
        """Child prologue: chdir into the run dir, feed the stdin bytes via a
        pipe, redirect stdout+stderr to the log file."""
        os.chdir(self.rundir)
        if self.stdin:
            rfd, wfd = os.pipe()
            os.write(wfd, self.stdin)
            os.close(wfd)
            os.dup2(rfd, 0)
        fo = os.open(self.log_name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.dup2(fo, 1)
        os.dup2(fo, 2)

    @staticmethod
    def abort() -> None:
        """Crash epilogue (call from an ``except`` block): traceback to **fd 2**
        — the redirected run log; ``sys.stderr`` may be an in-memory capture
        object under a host like pytest — then hard-exit 111.  Never returns."""
        import traceback
        try:
            os.write(2, traceback.format_exc().encode())
        except OSError:
            pass
        os._exit(111)

    def run(self, child, lib_path, flag) -> None:
        """Fork-per-call child main (:meth:`ExecutionBody.call`): wire I/O, load the
        library fresh (pristine global state), run ``child(lib)``, store its
        int flag, hard-exit.  Never returns normally."""
        try:
            import ctypes
            self.wire()
            self.apply_rlimits()          # cap this child's resources (best-effort)
            lib = ctypes.CDLL(str(lib_path))
            flag.value = int(child(lib))
            os._exit(0)
        except BaseException:
            self.abort()

    def slice(self, req, buffers, flag, slice_fn) -> None:
        """COW slice-child main: wire the log (no stdin — the holder's setup
        consumed it), run ``slice_fn`` on the COW-inherited tables via
        :attr:`lib`, capture into ``buffers``, hard-exit."""
        try:
            self.wire()
            self.apply_rlimits()          # cap this slice child (not the holder)
            flag.value = int(slice_fn(self.lib, buffers, req))
            os._exit(0)
        except BaseException:
            self.abort()

    @classmethod
    def holder(cls, conn, lib_path, buffers, flag, on_load, warmup_fn,
               slice_fn, stdin, log_name, rlimits=None) -> None:
        """COW holder main: load the library (+ its tables via ``on_load``)
        ONCE, then serve requests — the first warmed in-holder, every later one
        in a forked child that inherits the loaded tables via copy-on-write."""
        import ctypes
        lib = ctypes.CDLL(str(lib_path))
        if on_load is not None:
            on_load(lib)
        cls.lib = lib               # hand the loaded lib to fork children
        warmed = False
        while True:
            msg = conn.recv()
            if msg is None:
                os._exit(0)
            rundir, req, timeout = msg
            if not warmed:
                # warm IN-HOLDER: this loads every large table into the holder,
                # so subsequent forked children inherit them via COW.  Two
                # consequences, both by design: a library STOP/segfault here
                # kills the WHOLE holder (there is no child to absorb it — the
                # parent's recv then sees EOF); and a soft failure (flag 0)
                # means the tables did not load, so the holder is unusable.
                # Report the result, then — on failure — exit so later solves
                # fail loudly instead of running slices on un-loaded state
                # (fail-fast); ``warmed`` is set only once the warm succeeded.
                cls(rundir, log_name, stdin).wire()
                flag.value = int(warmup_fn(lib, buffers, req))
                conn.send(flag.value)
                if flag.value == 0:
                    os._exit(1)
                warmed = True
            else:
                p = ExecutionBody._CTX.Process(
                                 target=cls(rundir, log_name, rlimits=rlimits).slice,
                                 args=(req, buffers, flag, slice_fn))
                p.start()
                p.join(timeout)
                if p.is_alive():                 # slice hung -> kill just it
                    ExecutionBody._end_process(p)      # (SIGTERM->SIGKILL), keep the
                conn.send(flag.value if p.exitcode == 0 else 0)  # holder alive


# --------------------------------------------------------------------------- #
# Persistent handle — pin a dataset in RAM and/or hold a COW holder process
# --------------------------------------------------------------------------- #
class ExecutionBody:
    """Persistent handle over a non-reentrant native library — it manages a
    call's **whole lifespan** (workdir, execution, timeout, logs, reclamation).

    A non-reentrant solver still runs one fork per call; what a session persists
    is the **parent**.  It manages three kinds of resource, torn down together by
    :meth:`close` (also at interpreter exit):

    * **calls** — :meth:`invoke`, the six-phase driver (interpret → provision
      → stage → :meth:`execute` → harvest → dispose).  Fork-per-call when the
      body owns only a library (the parent never loads it; each call forks a
      child that loads it fresh), fork-per-solve on COW-inherited tables once
      :meth:`cow` has spawned a holder.  Timeout-bounded, and the run log is
      captured either way.

      ★This said ``call`` and ``run`` — two entry points that were folded into
      :meth:`invoke` and no longer exist, along with five more names below
      (``wire``, ``deliver``, ``holder``, ``slice``, ``abort``).  Seven dead
      method names in the class docstring of the module this package
      advertises as its architecture-validation case.
    * **work dirs** — private per-call dirs come from :meth:`scratch`
      (PID-tagged tmpfs) and are **tracked**: consumed by the caller's flow,
      detached via :meth:`release` (kept-on-purpose / post-mortem), and whatever
      remains is swept by :meth:`close` — no in-process leak;
      :meth:`ExecutionBody.reap_orphans` covers a SIGKILLed process's leftovers.
    * a **RAM-pinned dataset** — a large, read-only directory staged on tmpfs
      **once** at construction (``pin=True``), read at RAM speed by every later
      call; and the **COW holder** process (:meth:`cow`), whose **first** solve
      warms *in the holder* (that is how the tables land in the holder's
      address space for children to COW-inherit; :meth:`warm` triggers it
      explicitly) — so a library ``STOP``/segfault during the first solve takes
      down the **whole session** and raises with the captured log, while
      **every later** solve forks a child and a ``STOP`` there aborts only that
      child.

    Plain ``ExecutionBody(data_dir)`` is **pin-only**;
    ``ExecutionBody(lib_path=...)`` enables the fork-per-call path;
    :meth:`ExecutionBody.cow` spawns the holder and switches to
    fork-per-solve.  Subclass it to add a domain entry point (resolve the
    dataset in ``__init__`` then ``super().__init__``).  ``pin=False`` keeps
    the original directory (no copy); ``tmpfs_env`` and ``stage_prefix`` tune
    the RAM staging (see :meth:`ExecutionBody.stage_dir`); ``timeout`` is the
    default bound.  Usable as a context manager.

    ★The subclass this pointed at as the example — ``fylite.run.EFITSession``
    — left with the EFIT driver, and it was the only one.  What remains is a
    body with no domain subclass in this distribution: the class earns its
    place as the SpModel ``ExecutionBody`` reference implementation (see the
    package docstring), not as live plumbing, and saying so beats naming a
    subclass a reader cannot open.

    **Not thread-safe**: one in-flight :meth:`invoke` per ExecutionBody (the
    COW pipe is a single request/response channel); use one ExecutionBody per
    worker for parallelism.  Fork-based, so Linux/POSIX only — and forking a
    heavily multi-threaded parent has the usual fork-vs-threads hazards.
    """

    # ---- protocol declarations (D1; SPM-ADR-112 D4) ------------------------- #
    #: What kind of executable body this is — the D1 identity, reported in every
    #: :meth:`environment_identity`.  Upstream's vocabulary is open (``callable``
    #: / ``async_callable`` / ``ir`` / ``external`` / ``remote``); this body is the
    #: native-shared-library kind upstream does not ship.
    kind: typing.ClassVar[str] = "native_library"

    #: Whether the body executes natively on an event loop.  ``False``: the fork
    #: driver is blocking, so :meth:`ainvoke` offloads it to a worker thread.
    async_native: typing.ClassVar[bool] = False

    #: The ComputeArtifact manifest cell this body concretizes (SPM-ADR-112 D4).
    #: ``external`` — the executed thing is an out-of-tree native artifact, not a
    #: Python script block or an expression.
    manifest_kind: typing.ClassVar[str | None] = "external"

    #: The persistent environment (pinned tables / COW holder) is consumed by one
    #: call at a time -> :meth:`invoke` takes the single-in-flight guard.  A
    #: subclass with no environment singletons may set this ``False``.
    exclusive_environment: typing.ClassVar[bool] = True

    #: Calls need a private per-call working directory (provisioned at P-2,
    #: reclaimed at P-6 unless the disposition retains it).
    needs_workdir: typing.ClassVar[bool] = True

    #: When True, :meth:`harvest` promotes a *successful* call's disposition to
    #: :data:`DELIVER` (keep the workspace + flag it as a deliverable) instead of
    #: the default reclaim/retain.  Off by default (behaviour unchanged); a domain
    #: subclass that always wants the workspace delivered sets it True.
    deliver_on_success: typing.ClassVar[bool] = False

    #: parent-side event log (holder lifecycle, timeouts, kills, reaping).
    #: Silent by default (library convention) — the app configures handlers/
    #: level.  This is NOT the native ``.so``'s own stdout/stderr: that is
    #: fd-redirected to the per-call log file (see ``_DEFAULT_LOG`` / _Process.wire).
    _LOG = logging.getLogger("fylite.engine")

    #: default run-log basename written inside each call's work dir
    _DEFAULT_LOG = "_lib.log"

    #: one fork context shared by the fork-per-call path, the COW holder and
    #: its slice children — a forked child inherits the interpreter but not a loaded
    #: library (pristine global state), and closures pass through as Process
    #: args by memory copy, never pickled.
    _CTX = mp.get_context("fork")

    #: seconds the parent waits *beyond* a solve's own timeout before deciding
    #: the COW holder itself (not the slice it bounds) is wedged — covers fork/
    #: terminate/IPC overhead.  Small enough to notice a hang, large enough not
    #: to false-trip.
    _POLL_MARGIN = 30.0

    #: seconds granted after SIGTERM before escalating to SIGKILL (_end_process)
    _TERM_GRACE = 5.0

    def __init__(self, data_dir=None, *, lib_path=None, stdin: bytes = b"",
                 log_name: str = _DEFAULT_LOG, timeout: float = 900.0,
                 pin: bool = True, tmpfs_env: str | None = None,
                 stage_prefix: str = "native_stage_",
                 workdir_prefix: str = "native_run_", workdir=None,
                 exclusive_environment: bool | None = None,
                 max_concurrency: int | None = None,
                 rlimits: dict | None = None) -> None:
        # opportunistically clear dirs stranded by a previously killed process
        # (best-effort; never let housekeeping break construction)
        try:
            self.reap_orphans(self.tmpfs_dir(tmpfs_env),
                              (stage_prefix, workdir_prefix, "native_cow_"))
        except Exception:
            pass
        self._staged = (self.stage_dir(data_dir, prefix=stage_prefix,
                                       env_var=tmpfs_env)
                        if (pin and data_dir is not None) else None)
        #: the directory calls read from (tmpfs if pinned), or None if unset
        self.data_dir = (self._staged
                         or (Path(data_dir) if data_dir is not None else None))
        #: the shared object each forked child loads (None -> no library, so
        #: this body is pin-only)
        self.lib_path = str(lib_path) if lib_path is not None else None
        self.stdin = stdin
        self.log_name = log_name
        self.workdir_prefix = workdir_prefix
        #: fixed work dir for every call (caller-owned: used
        #: as-is, never tracked, never removed), or None -> each call gets a
        #: private tracked :meth:`scratch` dir.
        #:
        #: CAVEAT: the dir is **reused, not cleared**, so a legacy library that
        #: opens its output files with Fortran ``STATUS='NEW'`` can fail on the
        #: second call into the same dir (kefit does: a COW :meth:`run` after
        #: the in-holder warm dies on ``errorm.log``).  Safe for a single call,
        #: or when the caller clears the dir between calls; leave it None for
        #: repeated runs.
        self.workdir = Path(workdir) if workdir is not None else None
        self._timeout = timeout
        self._base = self.tmpfs_dir(tmpfs_env)
        self._scratch: list[Path] = []       # tracked private workdirs (see scratch)
        # COW holder state (populated only by ExecutionBody.cow)
        self._holder = None
        self._conn = None
        self._flag = None
        self._holder_spec = None              # (buffers, warmup, slice, on_load) for restart()
        self._lib_hash = None                 # cached sha256 of lib_path (environment_identity)
        # --- ExecutionBody scope state (env scope + single-in-flight guard) ---
        # env scope: cold (no live environment) -> ready (lib available / holder
        # warmed) -> poisoned (holder died on a solve; the session is unusable).
        self._env_state = "ready" if self.lib_path is not None else "cold"
        self._env_error = ""
        self._call_guard = threading.Lock()  # exclusive_environment guard
        self._in_flight = False
        #: per-instance override of the class-level exclusive_environment (a
        #: reentrant fork-per-call session may run concurrently — None = inherit).
        self._exclusive = exclusive_environment
        #: bounded-concurrency backpressure for a REENTRANT body — caps concurrent
        #: in-flight calls (blocks the excess) so reentrancy can't fork-storm.
        self._concurrency = (threading.BoundedSemaphore(int(max_concurrency))
                             if max_concurrency else None)
        #: per-child resource limits applied in the fork child (resource.setrlimit):
        #: {"AS"|"CPU"|"NOFILE"|"DATA"|"FSIZE": soft_or_(soft,hard)}
        self._rlimits = dict(rlimits) if rlimits else None
        #: lightweight telemetry counters (see :meth:`stats`).
        self._stats = {"calls": 0, "failures": 0, "retries": 0, "restarts": 0,
                       "cancels": 0}
        self._stats_lock = threading.Lock()
        #: disposition of the most recent call (D6) — "" before any call
        self._last_disposition = ""
        atexit.register(self.close)

    # ---- environment scope (ExecutionBody D2/D7) --------------------------- #
    def environment_ready(self) -> bool:
        """Whether the persistent environment can serve a call (not poisoned)."""
        return self._env_state == "ready"

    def poison(self, reason: str) -> None:
        """Mark the environment unusable (a holder died on a solve) — every
        later :meth:`invoke` then fails fast until a fresh session is built (or
        :meth:`restart` respawns a COW holder)."""
        self._env_state = "poisoned"
        self._env_error = reason

    def _lib_sha256(self) -> str | None:
        """SHA-256 of the loaded library, cached (used in the run trace)."""
        if self.lib_path is None:
            return None
        if self._lib_hash is None:
            self._lib_hash = sha256_file(self.lib_path)
        return self._lib_hash

    def environment_identity(self) -> dict:
        """Identity of the environment that executes a call (**D6**) — folded into
        each :class:`CallTrace` (P-5) so a call's trace names *what* ran it, and
        into :meth:`manifest_projection` as the concretization facet.

        Carries the two protocol keys every body reports — ``body_kind`` (:attr:`kind`)
        and ``body_class`` (the fully-qualified implementing class) — then this
        body's own environment spec: ``mode`` is ``cow`` (load-once holder),
        ``fork`` (fork-per-call) or ``pin`` (data-only); ``library`` /
        ``library_sha256`` fingerprint the ``.so`` (the checksum is what makes a
        call reproducible across a library upgrade); ``holder_pid`` is present for
        a COW session.  Subclasses extend with their own dataset checksums."""
        mode = ("cow" if self._holder is not None
                else "fork" if self.lib_path is not None else "pin")
        cls = type(self)
        ident = {"body_kind": cls.kind,
                 "body_class": f"{cls.__module__}.{cls.__qualname__}",
                 "mode": mode, "library": self.lib_path,
                 "library_sha256": self._lib_sha256(), "pid": os.getpid()}
        if self._holder is not None:
            ident["holder_pid"] = self._holder.pid
        return ident

    def cache_identity(self) -> str:
        """Stable identity of the implementing body class (D1).  Upstream keys the
        compiled-artifact cache with it; there is no compile step here, so it
        serves only as the body's class identity in provenance."""
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}"

    def manifest_projection(self) -> dict:
        """Project this body onto the ComputeArtifact manifest facets
        (**SPM-ADR-112 D4**): ``kind`` is the manifest vocabulary cell this body
        concretizes, ``concretization`` the serialized environment spec (the
        ``iao:is_concretized_as`` facet).  Signing and governance stay with the
        platform; this layer only supplies the projection."""
        return {"kind": type(self).manifest_kind,
                "concretization": self.environment_identity()}

    def last_disposition(self) -> str:
        """Disposition of the most recent call (**D6**), ``""`` before any call.

        Recorded at P-6 by :meth:`_dispose_safely` — i.e. *before* the workspace
        is acted on — so a caller assembling provenance after the call still sees
        what was decided at harvest."""
        return self._last_disposition

    @property
    def _is_exclusive(self) -> bool:
        """Whether one call runs at a time.  A COW holder's pipe is a single
        request/response channel, so a COW session is **always** exclusive; a
        fork-per-call session honours the instance/class ``exclusive_environment``
        (a reentrant one forks a fresh isolated child per call)."""
        if self._holder is not None:
            return True
        if self._exclusive is not None:
            return self._exclusive
        return self.exclusive_environment

    def _bump(self, key: str, n: int = 1) -> None:
        """Thread-safe telemetry counter bump (reentrant bodies run concurrently)."""
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + n

    def stats(self) -> dict:
        """Lightweight telemetry: cumulative ``calls`` / ``failures`` / ``retries``
        / ``restarts`` / ``cancels`` since construction (a snapshot copy)."""
        with self._stats_lock:
            return dict(self._stats)

    def _acquire_environment(self) -> None:
        """**D2 hook** — acquire the durable environment: (re)spawn the COW holder
        from its stored spec when this body owns one.  A plain library body needs
        nothing beyond ``lib_path``, and a pin-only body staged its dataset at
        construction, so both are no-ops here.  Runs at most once per environment
        lifetime, inside the process that will serve the calls; a raise poisons
        the body (see :meth:`acquire`)."""
        if self._holder_spec is not None:
            self.restart()                    # (re)spawn the COW holder

    def _close_environment(self) -> None:
        """**D2 hook** — release the durable environment: stop the COW holder,
        release its pipe, and drop the tmpfs-staged dataset.  Idempotent."""
        h = getattr(self, "_holder", None)
        if h is not None and h.is_alive():
            if self._conn is not None:
                try:
                    self._conn.send(None)     # ask the holder to exit cleanly
                except (BrokenPipeError, OSError):
                    pass                      # holder already gone — fine
            try:
                h.join(5)
            finally:
                if h.is_alive():
                    self._end_process(h)      # SIGTERM -> grace -> SIGKILL
        self._holder = None
        if self._conn is not None:
            try:
                self._conn.close()            # release the pipe FD now, not at GC
            except OSError:
                pass
            self._conn = None
        if self._staged is not None:
            shutil.rmtree(self._staged, ignore_errors=True)
            self._staged = None

    def acquire(self) -> None:
        """Bring the environment to ``ready`` (**D2**; symmetric to :meth:`close`,
        idempotent, poison-guarded).

        A ``ready`` environment returns unchanged; a ``cold`` one runs
        :meth:`_acquire_environment` and becomes ``ready``; a hook failure poisons
        the body and raises :class:`EnvironmentAcquireError`.  A **poisoned**
        environment is terminal for this scope and raises
        :class:`PoisonedBodyError` — never serve a call on a broken environment.
        To replace a poisoned COW environment, call :meth:`restart` explicitly
        (which is what :meth:`invoke`'s ``retries`` does): healing is a deliberate
        act, not a side effect of asking for service."""
        if self._env_state == "poisoned":
            raise PoisonedBodyError(
                f"{type(self).__name__} environment is poisoned and refuses "
                f"service: {self._env_error}; restart() it or build a fresh body")
        if self._env_state == "ready":
            return
        try:
            self._acquire_environment()
        except BaseException as e:
            self.poison(str(e) or type(e).__name__)
            raise EnvironmentAcquireError(
                f"environment acquisition failed for {type(self).__name__}: "
                f"{self._env_error}") from e
        self._env_state = "ready"
        self._env_error = ""

    def on_deliver(self, call: CallScope) -> None:
        """P-6 hook fired when a call's disposition is :data:`DELIVER` — the
        workspace is a deliverable.  A no-op by default; override to enact
        delivery (copy artifacts, call :func:`deliver`, notify a sink).  Runs
        inside :meth:`dispose`, which swallows its exceptions (delivery must not
        break teardown)."""
        del call

    # ---- work-dir lifespan ------------------------------------------------- #
    def scratch(self, prefix: str | None = None) -> Path:
        """Provision a private per-call work dir (PID-tagged, tmpfs when
        available) and **track** it: anything still tracked at :meth:`close` is
        swept, so a caller that forgets cleanup cannot leak RAM in-process."""
        d = self._scratch_dir(self._base, prefix or self.workdir_prefix)
        self._scratch.append(d)
        return d

    def release(self, path) -> None:
        """Detach a :meth:`scratch` dir from the close-time sweep — for dirs
        deliberately kept past the session (``keep_workdir``, post-mortem after
        a failed call).  A released dir is PID-tagged, so a *later* process's
        :meth:`ExecutionBody.reap_orphans` still clears it once this process is gone.
        Unknown paths are ignored."""
        p = Path(path)
        self._scratch = [d for d in self._scratch if d != p]

    # ======================================================================== #
    # ExecutionBody six-phase call driver (SPM-ADR-111 D3), mirrored locally:
    #   P-1 interpret · P-2 provision · P-3 stage · P-4 execute ·
    #   P-5 harvest · P-6 dispose
    #
    # `invoke` is the driver (`run` is a back-compat alias); it holds the
    # single-in-flight guard for the exclusive environment, runs the phases, and
    # guarantees P-6 in `finally`.  Override any phase in a subclass to add
    # domain behaviour (the EFIT session that used to supply it is gone) — the mechanism
    # (fork / COW / timeout / reclamation) stays here.  The 准备/执行/收尾 split
    # of the original three-phase driver maps onto provision / execute / (harvest
    # + dispose).
    # ======================================================================== #
    def _begin_call(self) -> bool:
        """Enter the call scope (**D7**): an exclusive environment admits **one**
        in-flight call and fails loud on a second (:class:`ConcurrentInvocationError`);
        a reentrant body instead takes a bounded-concurrency slot, blocking for it
        so reentrancy cannot fork-storm.

        Returns whether the exclusive guard is held — the caller hands that back
        to :meth:`_end_call`.  (Upstream's pair takes no argument because it has
        only the one guard; here the two modes are distinguished explicitly rather
        than by re-reading mutable state in the ``finally``.)"""
        held = self._is_exclusive
        if held:
            if not self._call_guard.acquire(blocking=False):
                raise ConcurrentInvocationError(
                    "ExecutionBody is single-in-flight (exclusive_environment) — one "
                    "call at a time; use one ExecutionBody per worker for parallelism")
            self._in_flight = True
        elif self._concurrency is not None:
            self._concurrency.acquire()       # bounded reentrant concurrency (backpressure)
        return held

    def _end_call(self, held: bool) -> None:
        """Leave the call scope (**D7**) — release whichever guard
        :meth:`_begin_call` took.  Always runs from the driver's ``finally``."""
        if held:
            self._in_flight = False
            self._call_guard.release()
        elif self._concurrency is not None:
            self._concurrency.release()

    def interpret_inputs(self, request):
        """**P-1 解释** — resolve the raw ``request`` into what P-2/P-4 consume.

        A pass-through by default (the fork-per-call closure / COW payload is
        already executable).  Override to translate a high-level request (a
        descriptor, a filename, a domain object) into the executable form
        :meth:`provision`/:meth:`execute` expect — the one place request
        interpretation belongs, kept out of the mechanism.

        Upstream additionally validates the result against ``Operator.inports``;
        there are no ports here, so interpretation is all P-1 does (see
        ``PROTOCOL['not_applicable']``)."""
        return request

    def provision(self, request, *, workdir=None) -> CallScope:
        """**P-2 准备** — acquire this call's per-call lease (work dir + context).

        Work dir precedence: an explicit ``workdir`` (needed when the caller
        stages input files into it *before* the fork — used as-is, never
        tracked) > the session's ``ExecutionBody(workdir=)`` > a private per-call dir.

        A private COW dir is disposable (:data:`RECLAIM`, removed at P-6); a
        caller-consumed fork-per-call dir or a session-fixed dir is
        :data:`RETAIN`.  ``owns_workdir`` records whether this body created the
        dir: a caller-supplied / session-fixed dir is **never** removed at P-6, no
        matter what the disposition says.  Override to translate ``request`` /
        carry prepared state on the returned :class:`CallScope`."""
        fixed = Path(workdir) if workdir is not None else self.workdir
        if fixed is not None:
            fixed.mkdir(parents=True, exist_ok=True)
            return CallScope(request, fixed, disposition=RETAIN,
                             owns_workdir=False)   # caller owns it
        if self._holder is not None:            # COW: private, reclaimed at P-6
            # tracked (not a bare _scratch_dir): a failure now forces RETAIN, and
            # a retained dir must still be swept by close() rather than leak.
            return CallScope(request, self.scratch("native_cow_"),
                             disposition=RECLAIM, owns_workdir=True)
        d = self.scratch()                      # fork-per-call: caller consumes
        d.mkdir(parents=True, exist_ok=True)
        return CallScope(request, d, disposition=RETAIN, owns_workdir=True)

    def stage(self, call: CallScope) -> None:
        """**P-3 装配** — materialize the resolved request into the workspace.

        A no-op here (fork-per-call closures carry their own inputs; the COW
        payload is sent over the pipe).  Override to write input files into
        ``call.workdir`` before P-4 forks/serves."""
        del call

    def invoke(self, request=None, *, workdir=None,
               timeout: float | None = None, retries: int = 0,
               retry_backoff: float = 0.0, retry_jitter: bool = False,
               cancel_token=None) -> _CallResult:
        """The six-phase call driver: interpret → provision → stage → execute →
        harvest → dispose, under the concurrency guard.

        Execution (P-4) dispatches on what this session owns: a **COW** session
        (built by :meth:`cow`) serves ``request`` through its holder, which forks
        a slice child per call on the COW-inherited tables; otherwise the session
        **forks per call** and ``request`` is the ``child(lib) -> int`` closure
        run in that child (it pushes inputs, calls the entry, copies results into
        shared buffers it closes over; 0 == no result).

        Bounded by ``timeout`` (default: the session's) in both modes — a hung
        fork/slice child is killed, and a wedged COW holder is terminated with
        :class:`CallTimeout` (which :meth:`poison`\\ s the session).  ``retries``
        (default 0) re-attempts a call that raises or returns not-ok, self-healing
        a poisoned COW holder via :meth:`restart` between attempts;
        ``retry_backoff`` (seconds) adds exponential backoff ``backoff*2**attempt``
        (``retry_jitter`` randomizes it).  ``cancel_token`` (a
        :class:`threading.Event`) cancels an in-flight fork child mid-call →
        :class:`CallCancelled` (cancellation is never retried).

        Concurrency: an **exclusive** environment serves one call at a time (a
        concurrent call raises :class:`ConcurrentInvocationError`); a **reentrant**
        body (``exclusive_environment=False``) runs concurrently, capped by
        ``max_concurrency`` (excess calls block for a slot — no fork-storm)."""
        self.acquire()                        # D2: idempotent, poison-guarded
        held = self._begin_call()             # D7: one in-flight call per environment
        self._bump("calls")
        call_id = uuid.uuid4().hex
        try:
            attempt = 0
            while True:
                call: CallScope | None = None
                res: _CallResult | None = None
                timings: dict = {}

                def _phase(name, fn):
                    t = time.perf_counter()
                    out = fn()
                    timings[name] = time.perf_counter() - t
                    return out

                try:
                    resolved = _phase("interpret_inputs",                             # P-1
                                      lambda: self.interpret_inputs(request))
                    call = _phase("provision",                                        # P-2
                                  lambda: self.provision(resolved, workdir=workdir))
                    call.call_id = call_id
                    _phase("stage", lambda: self.stage(call))                         # P-3
                    res = _phase("execute",                                           # P-4
                                 lambda: self.execute(call, timeout, cancel_token))
                    if res is not None:
                        res.duration_s = timings["execute"]
                    res = _phase("interpret_outputs",                                 # P-5a
                                 lambda: self.interpret_outputs(res))
                    res = _phase("harvest", lambda: self.harvest(call, res))          # P-5b
                    if res is not None and res.trace is not None:
                        res.trace.call_id = call_id
                        res.trace.attempts = attempt + 1
                        res.trace.phase_timings = timings
                    if res is None or res.ok:
                        return res
                    self._bump("failures")        # not-ok result
                    if attempt >= retries:
                        return res
                # D3: every raising path below forces RETAIN before P-6 — the
                # failure scene is never reclaimed, which is exactly when it is
                # worth keeping (a timed-out COW solve used to have its private
                # dir wiped by the reclaim disposition it was provisioned with).
                except CallCancelled:
                    self._bump("cancels")
                    if call is not None:
                        call.disposition = RETAIN
                    raise                         # cancellation is never retried
                except (TimeoutError, RuntimeError):
                    self._bump("failures")
                    if call is not None:
                        call.disposition = RETAIN
                    if attempt >= retries:
                        raise
                    # self-heal a poisoned COW holder before the next attempt
                    if not self.environment_ready() and self._holder_spec is not None:
                        self.restart()
                except BaseException:
                    if call is not None:
                        call.disposition = RETAIN
                    raise
                finally:
                    if call is not None:
                        self._dispose_safely(call, res)           # P-6: always
                self._bump("retries")
                if retry_backoff > 0:
                    delay = retry_backoff * (2 ** attempt)
                    if retry_jitter:
                        delay *= 0.5 + random.random()
                    time.sleep(delay)
                attempt += 1
        finally:
            self._end_call(held)

    async def ainvoke(self, request=None, *, workdir=None,
                      timeout: float | None = None, retries: int = 0) -> _CallResult:
        """Awaitable :meth:`invoke` — the six-phase driver off the event loop.

        Runs the (blocking, fork-based) driver in a worker thread
        (:func:`asyncio.to_thread`) so an async host is not stalled on the
        fork/join.  Semantics match :meth:`invoke`: an exclusive environment
        still serves one call at a time (a concurrent :meth:`ainvoke` raises
        single-in-flight), while a reentrant fork-per-call body
        (``exclusive_environment=False``) runs concurrent :meth:`ainvoke`\\ s each
        in its own isolated child.

        Cancelling the awaiting task **really cancels the call**: the in-flight
        fork child is terminated (via an internal cancel token) and
        :class:`asyncio.CancelledError` propagates once the worker unwinds — no
        orphaned child left running to the timeout.

        CAVEAT (fork-vs-threads): the worker thread then *forks* — the child runs
        the closure and hard-exits without touching parent locks (safe for the
        fork-per-call/COW model here), but Python 3.12+ warns on fork from a
        multi-threaded process.  Do not add closures that block on threading
        primitives inherited across the fork."""
        token = threading.Event()
        fut = asyncio.ensure_future(asyncio.to_thread(
            self.invoke, request, workdir=workdir, timeout=timeout,
            retries=retries, cancel_token=token))
        try:
            return await asyncio.shield(fut)
        except asyncio.CancelledError:
            token.set()                          # tell the worker to kill its child
            with contextlib.suppress(BaseException):
                await fut                        # let it unwind (CallCancelled)
            raise

    def interpret_outputs(self, res: _CallResult | None) -> _CallResult | None:
        """**P-5a 解释产出** — interpret what P-4 produced, before harvest decides
        the disposition.

        A pass-through by default.  Upstream validates the outputs against
        ``Operator.outports`` here; there are no ports on this side, so the hook
        exists as the declared place to normalize / reshape a raw call result
        (a subclass that returns a domain object rather than a
        :class:`_CallResult` does it here, not in :meth:`harvest`)."""
        return res

    def harvest(self, call: CallScope, res: _CallResult | None) -> _CallResult | None:
        """**P-5b 收割** — extract the outcome and decide the workspace disposition.

        Decides the three-value :data:`~fylite.engine.RECLAIM` /
        :data:`RETAIN` / :data:`DELIVER` disposition: a **failed** call's
        workspace is force-:data:`RETAIN`\\ ed (never reclaimed — kept for
        post-mortem), and a **successful** call is promoted to :data:`DELIVER`
        when :attr:`deliver_on_success`.  Caches a reclaimed dir's log tail into
        the result (so ``res.tail()`` stays readable after P-6 removes the dir)
        and stamps the :class:`CallTrace` with the environment identity + duration.
        Override to post-process the result (call ``super().harvest`` first)."""
        if res is not None:
            if not res.ok and call.reclaim:
                call.disposition = RETAIN         # retain-on-failure (post-mortem)
            elif res.ok and self.deliver_on_success and call.disposition == RETAIN:
                call.disposition = DELIVER
            if call.reclaim:
                res.cached_tail = _CallResult.read_tail(res.log, 20000)
            res.trace = CallTrace(call.disposition, res.log,
                                  environment_identity=self.environment_identity(),
                                  duration_s=res.duration_s)
        return res

    def _dispose_safely(self, call: CallScope, res: _CallResult | None) -> None:
        """Run P-6 without masking the primary error — :meth:`dispose` never
        raises out of the driver's ``finally``.

        Records :meth:`last_disposition` **first**, so a caller assembling
        provenance sees what harvest decided even if disposal itself fails."""
        self._last_disposition = str(call.disposition)
        try:
            self.dispose(call, res)
        except Exception as e:                # noqa: BLE001 — teardown must not raise
            ExecutionBody._LOG.error("dispose failed (call %s, disposition %s): %s",
                                     call.call_id, call.disposition, e)

    def dispose(self, call: CallScope, res: _CallResult | None) -> None:
        """**P-6 释放** — release the per-call lease; always runs.

        Reclaims the workspace only when the disposition is :data:`RECLAIM` (a
        private COW dir — diagnostics were already captured at P-5); a
        :data:`RETAIN` (caller-consumed / session-fixed / retain-on-failure) dir
        is left in place; a :data:`DELIVER` dir is left in place **and** the
        :meth:`on_deliver` hook is fired (exceptions swallowed — delivery must not
        break teardown).  Never raises.

        A workspace this body does not own (``owns_workdir=False``: caller-supplied
        or session-fixed) is never removed, whatever the disposition says."""
        del res
        if call.reclaim and call.owns_workdir:
            shutil.rmtree(call.workdir, ignore_errors=True)
            self.release(call.workdir)        # drop it from the close-time sweep
        elif call.deliver:
            try:
                self.on_deliver(call)
            except Exception as e:                # noqa: BLE001 — teardown must not raise
                ExecutionBody._LOG.error("on_deliver failed for %s: %s",
                                         call.workdir, e)

    #: cancel-token poll interval (s) — how promptly a cancel/​token kills a child
    _CANCEL_POLL = 0.05

    # ---- execution mechanism (the P-4 body; not an override point) ---------- #
    def execute(self, call: CallScope, timeout: float | None,
                cancel_token=None) -> _CallResult:
        """**P-4 执行** — dispatch one prepared call: COW holder when we own one,
        else fork-per-call.  ``cancel_token`` (a :class:`threading.Event`) kills
        the in-flight child when set (fork-per-call: promptly; COW: by tearing
        the holder down)."""
        t = self._timeout if timeout is None else timeout
        if self._holder is not None:
            return self._execute_cow(call, t, cancel_token)
        return self._execute_forked(call, t, cancel_token)

    def _join_or_cancel(self, p, t: float, rundir, cancel_token):
        """Join child ``p`` within ``t`` while honouring ``cancel_token``.

        Returns normally when the child exits in time.  Raises
        :class:`CallCancelled` if the token fires first (killing the child), or
        :class:`CallTimeout` at the deadline (killing the child)."""
        if cancel_token is None:
            p.join(t)
        else:
            deadline = time.perf_counter() + t
            while p.is_alive():
                if cancel_token.is_set():
                    ExecutionBody._LOG.info("call cancelled in %s — killing child", rundir)
                    self._end_process(p)
                    raise CallCancelled(f"cancelled in {rundir}")
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                p.join(min(remaining, ExecutionBody._CANCEL_POLL))
        if p.is_alive():
            ExecutionBody._LOG.warning("call timed out after %.0fs in %s — killing child",
                                 t, rundir)
            self._end_process(p)       # SIGTERM -> grace -> SIGKILL: always reaps
            raise CallTimeout(f"{self.lib_path} timed out after {t}s in {rundir}")

    def _execute_forked(self, call: CallScope, t: float,
                        cancel_token=None) -> _CallResult:
        """Fork a child, load the library fresh, run ``child(lib) -> int``.

        The child gets pristine global state (it inherits the interpreter but
        not a loaded library) and a ``STOP`` there aborts only the child."""
        if self.lib_path is None:
            raise EngineError("invoke() needs a library — ExecutionBody(lib_path=...)")
        rundir = call.workdir
        flag = ExecutionBody._CTX.Value("i", 0)
        p = ExecutionBody._CTX.Process(
            target=_Process(rundir, self.log_name, self.stdin, self._rlimits).run,
            args=(call.request, self.lib_path, flag))
        p.start()
        self._join_or_cancel(p, t, rundir, cancel_token)   # raises on timeout/cancel
        rc = p.exitcode if p.exitcode is not None else 111
        return _CallResult(rc, int(flag.value), str(rundir),
                          str(rundir / self.log_name))

    @classmethod
    def cow(cls, lib_path, buffers, *, warmup, slice, on_load=None,
            stdin: bytes = b"", log_name: str = _DEFAULT_LOG,
            tmpfs_env: str | None = None, workdir_base: str | None = None,
            workdir=None, data_dir=None, pin: bool = False,
            stage_prefix: str = "native_stage_",
            timeout: float = 900.0, rlimits: dict | None = None) -> "ExecutionBody":
        """Build a ExecutionBody that owns a **COW holder** (load-once, fork-per-solve).

        A holder process loads ``lib_path`` (+ its tables via ``on_load``) once;
        the first :meth:`run` warms it in-holder (loading every table there),
        every later :meth:`run` forks a child that inherits them via
        copy-on-write.  Callbacks (fork-shared, so closures are fine):

        * ``on_load(lib)`` — once after ``CDLL``; load-directory / one-time setup.
        * ``warmup(lib, buffers, req)`` — the **first** request, run in-holder: it
          must trigger the full one-time table load (e.g. setup + one slice) and
          capture the result into ``buffers``; returns an int flag.
        * ``slice(lib, buffers, req)`` — every **later** request, run in a forked
          child on the COW-inherited tables; captures into ``buffers``; a flag.

        ``buffers`` (from :meth:`ExecutionBody.alloc_buffers`) is created by the caller so it is
        shared across the holder and its fork children — a **single slot**: the
        next :meth:`run` overwrites it, so copy results out before re-solving.
        Per-request ``req`` (given to :meth:`run`) is sent over a pipe and MUST
        be picklable.  A ``data_dir`` may also be pinned (rarely needed — tables
        load in-holder).

        **Fail-fast:** the first (warming) :meth:`run` runs in the holder;
        if it aborts the library or returns 0 (tables not loaded), the holder is
        torn down and that :meth:`run` raises — a first-solve failure kills the
        session, so a fresh :meth:`cow` is needed.  Later solves are fork-isolated.
        ``timeout`` bounds each :meth:`run` (see there); :meth:`warm` triggers
        the one-time load explicitly.
        """
        self = cls(data_dir, lib_path=lib_path, stdin=stdin, log_name=log_name,
                   timeout=timeout, pin=pin, tmpfs_env=tmpfs_env,
                   stage_prefix=stage_prefix, workdir=workdir, rlimits=rlimits)
        if workdir_base is not None:
            self._base = workdir_base
        self.start_holder(buffers, warmup=warmup, slice=slice, on_load=on_load)
        return self

    def start_holder(self, buffers, *, warmup, slice, on_load=None) -> None:
        """Attach a **COW holder** to this (already built) session.

        The load-once half of :meth:`cow`, split out so a subclass that is
        already a ExecutionBody — with its dataset resolved and pinned — can turn
        itself into a COW session in place (see :meth:`warm`) instead of
        delegating to a second ExecutionBody.  Once attached, :meth:`run` dispatches
        through the holder.  Idempotent-ish: a live holder is kept as-is."""
        if self._holder is not None and self._holder.is_alive():
            return
        if self.lib_path is None:
            raise EngineError("start_holder() needs a library — ExecutionBody(lib_path=...)")
        self._holder_spec = (buffers, warmup, slice, on_load)  # for restart()
        self._flag = ExecutionBody._CTX.Value("i", 0)
        self._conn, child_conn = ExecutionBody._CTX.Pipe()
        self._holder = ExecutionBody._CTX.Process(
            target=_Process.holder,
            args=(child_conn, str(self.lib_path), buffers, self._flag, on_load,
                  warmup, slice, self.stdin, self.log_name, self._rlimits))
        self._holder.start()
        self._env_state = "ready"
        ExecutionBody._LOG.debug("COW holder started (pid=%s) for %s",
                           self._holder.pid, self.lib_path)

    def warm(self, req=None) -> _CallResult:
        """Trigger the first (warming) :meth:`run` explicitly.

        A convenience for services that want to pay the one-time table-load cost —
        and surface a warmup failure — at startup rather than on the first real
        request.  Identical to the first :meth:`run`; a no-op-ish call on an
        already-warmed holder (it just runs one more slice)."""
        return self.invoke(req)

    def restart(self) -> None:
        """Respawn a dead/poisoned **COW holder** from its stored spec (self-heal).

        A COW holder that died on a solve leaves the session ``poisoned``; when
        the failure was transient, ``restart()`` tears the remnant down and spawns
        a fresh holder (which re-warms on the next :meth:`invoke`), clearing the
        poison.  Only valid for a COW session (built by :meth:`cow` / attached via
        :meth:`start_holder`); a deterministic library abort will just poison
        again on the next solve.  :meth:`invoke`'s ``retries`` calls this
        automatically.

        This is the **only** way a poisoned environment becomes serviceable again,
        and it is not a loophole in D2's fail-fast rule: ``restart()`` tears the
        old environment down and builds a *new* one, which is exactly what
        discarding the body and constructing a fresh one would do — it just keeps
        the resolved dataset and holder spec.  :meth:`acquire` deliberately refuses
        to do this implicitly."""
        if self._holder_spec is None:
            raise EngineError("restart() is only for a COW session (no holder spec)")
        h = self._holder
        if h is not None and h.is_alive():
            self._end_process(h)              # SIGTERM -> grace -> SIGKILL
        self._holder = None
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None
        self._env_state = "cold"
        self._env_error = ""
        buffers, warmup, slice_fn, on_load = self._holder_spec
        self.start_holder(buffers, warmup=warmup, slice=slice_fn, on_load=on_load)
        self._bump("restarts")
        ExecutionBody._LOG.info("COW holder restarted for %s", self.lib_path)

    def _execute_cow(self, call: CallScope, t: float,
                     cancel_token=None) -> _CallResult:
        """Serve one prepared request through the COW holder.

        The holder forks a slice child on the COW-inherited tables and always
        replies; a hung slice is killed there and reported not-ok.  If the
        **holder itself** is unresponsive (e.g. a wedged in-holder warmup) it is
        terminated and :class:`CallTimeout` raised — the session is then dead
        (build a fresh :meth:`cow`).  ``cancel_token`` is honoured coarsely: a COW
        slice runs inside the holder, so cancelling tears the **holder** down
        (:meth:`poison`) and raises :class:`CallCancelled` — heavier than a
        fork-per-call cancel, but real."""
        holder = self._holder
        if holder is None or not holder.is_alive():
            raise ExecuteError(
                "COW holder is not running — it died on an earlier solve (a "
                "first-solve library abort takes the holder down) or the session "
                "was closed; build a fresh ExecutionBody.cow(...)")
        rundir = str(call.workdir)
        try:
            self._conn.send((rundir, call.request, t))
            # holder bounds the forked slice by `t` and always replies; give it a
            # margin, and if it still hasn't answered the HOLDER itself is wedged.
            margin = t + ExecutionBody._POLL_MARGIN
            if cancel_token is None:
                answered = self._conn.poll(margin)
            else:
                deadline = time.perf_counter() + margin
                answered = False
                while True:
                    if cancel_token.is_set():
                        ExecutionBody._LOG.info("COW call cancelled in %s — "
                                                "terminating holder", rundir)
                        self._end_process(self._holder)
                        self.poison("cancelled")
                        raise CallCancelled(f"cancelled in {rundir}")
                    remaining = deadline - time.perf_counter()
                    if remaining <= 0:
                        break
                    if self._conn.poll(min(remaining, ExecutionBody._CANCEL_POLL)):
                        answered = True
                        break
            if not answered:
                ExecutionBody._LOG.error("COW holder unresponsive after %.0fs (in %s) "
                                   "— terminating", margin, rundir)
                self._end_process(self._holder)  # SIGTERM -> grace -> SIGKILL
                self.poison("COW holder unresponsive")   # env scope -> poisoned
                raise CallTimeout(
                    f"COW holder unresponsive after {margin:.0f}s "
                    f"(in {rundir}) — terminated; build a fresh ExecutionBody.cow(...)")
            flag = int(self._conn.recv())
            return _CallResult(0 if flag else 111, flag, rundir,
                               str(call.workdir / self.log_name))
        except (CallCancelled, TimeoutError):
            raise                             # holder-wedged (TimeoutError ⊂ OSError)
        except (EOFError, BrokenPipeError, OSError) as e:
            # the holder died mid-solve — almost always a library STOP/segfault.
            # The FIRST solve runs in the holder itself (it loads the tables
            # there for COW), so a first-solve abort kills the session; later
            # solves are fork-isolated.  Surface the captured log, not a bare EOF.
            self.poison(f"COW holder died ({type(e).__name__})")  # env -> poisoned
            ExecutionBody._LOG.error("COW holder died during solve (%s) in %s — library "
                               "likely aborted (STOP/segfault)", type(e).__name__,
                               rundir)
            raise ExecuteError(
                f"COW holder died during solve ({type(e).__name__}); the library "
                f"likely aborted (STOP/segfault).\n--- {self.log_name} tail ---\n"
                f"{_CallResult.read_tail(call.workdir / self.log_name)}") from e

    def close(self) -> None:
        """End the session's whole lifespan (**D2**; idempotent): run
        :meth:`_close_environment` (stop the COW holder, release the pipe, drop
        the staged copy) and sweep every still-tracked :meth:`scratch` dir.

        A **poisoned** environment stays poisoned — closing does not launder a
        broken environment into a fresh one (:meth:`restart` is the explicit way
        to replace it).  Hook failures are logged, never raised: teardown must
        complete.

        Deliberate deviation from the upstream base, which returns early while
        ``cold``: this body acquires tmpfs resources at **construction** (the
        pinned dataset) and per call (:meth:`scratch` dirs), so ``cold`` is not
        proof that there is nothing to release.  Sweeping unconditionally keeps
        ``close()`` idempotent *and* leak-free for a never-invoked body."""
        atexit.unregister(self.close)         # drop the strong ref we registered
        try:
            self._close_environment()
        except Exception as e:                # noqa: BLE001 — teardown must finish
            ExecutionBody._LOG.warning("close: environment hook failed: %s", e)
        for d in getattr(self, "_scratch", ()):   # un-consumed, un-released dirs
            shutil.rmtree(d, ignore_errors=True)
        self._scratch = []
        if self._env_state != "poisoned":
            self._env_state = "cold"          # environment torn down

    def __enter__(self) -> "ExecutionBody":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- session-domain utilities (implementations live HERE — ExecutionBody is the
    #      module's only public name; the child side of the fork is _Process)
    @staticmethod
    def tmpfs_dir(env_var: str | None = None) -> str | None:
        """A RAM-backed (tmpfs) directory to run in, or ``None``.

        A non-reentrant solver typically writes scratch/output files to its
        working directory every call; on a tmpfs those writes never reach a
        block device (no writeback, RAM-speed), which matters under frequent
        iteration.  Order: ``$env_var`` (if given and set), then ``/dev/shm``
        (the conventional Linux tmpfs) when present and writable.  ``None`` →
        fall back to the default ``TMPDIR`` (possibly a block device).
        """
        cands = []
        if env_var:
            cands.append(os.environ.get(env_var))
        cands.append("/dev/shm")
        for c in cands:
            if c and os.path.isdir(c) and os.access(c, os.W_OK):
                return c
        return None

    @classmethod
    def stage_dir(cls, src, *, prefix: str = "native_stage_",
                  env_var: str | None = None) -> Path | None:
        """Copy a directory's files onto tmpfs; return the staged dir or ``None``.

        A one-time "pre-read" that pins a large read-only dataset in RAM so
        every later access is at RAM speed and never risks page-cache eviction
        under memory pressure.  ``None`` when no tmpfs is available (keep the
        original).  Not recursive — only top-level regular files are copied.
        The dir name embeds the creator PID (see :meth:`reap_orphans`); a
        mid-copy failure removes the half-staged dir rather than leaking it.
        """
        import tempfile
        base = cls.tmpfs_dir(env_var)
        if base is None:
            return None
        src = Path(src)
        dst = Path(tempfile.mkdtemp(prefix=f"{prefix}{os.getpid()}_", dir=base))
        try:
            for f in src.iterdir():
                if f.is_file():
                    shutil.copyfile(f, dst / f.name)
        except BaseException:
            shutil.rmtree(dst, ignore_errors=True)   # no half-staged dir left
            raise
        return dst

    @staticmethod
    def alloc_buffers(spec: dict[str, tuple[str, int]]) -> dict:
        """Allocate one ``multiprocessing.RawArray`` per output array.

        ``spec`` maps ``name -> (typecode, count)`` (typecodes as for
        ``RawArray``: ``"d"`` double, ``"i"`` int, ...).  Allocate in the
        **parent, before the fork**, so the child fills the same shared memory
        the parent then reads back.  Returns ``{name: RawArray}``.
        """
        return {name: mp.RawArray(tc, n) for name, (tc, n) in spec.items()}

    #: work/stage dir prefixes this module creates (PID-tagged; see reap_orphans)
    _NATIVE_PREFIXES = ("native_run_", "native_cow_", "native_stage_")

    @classmethod
    def reap_orphans(cls, base=None,
                     prefixes: tuple[str, ...] = _NATIVE_PREFIXES) -> int:
        """Best-effort removal of stale run/stage dirs left by a **dead** process.

        A parent killed by ``SIGKILL``/segfault skips ``atexit``, stranding its
        tmpfs dirs (a staged dataset can be ~100 MB of RAM).  Names embed the
        creator PID (``<prefix><pid>_<rand>``), so this removes only dirs whose
        PID is no longer alive — a **concurrent live** process's dirs (PID
        alive) are never touched.  ``base`` defaults to the tmpfs dir.  Returns
        the count removed; every failure is swallowed (another process may race
        us).  Safe to call at any time.
        """
        import re
        base = base or cls.tmpfs_dir()
        if not base or not os.path.isdir(base):
            return 0
        try:
            names = os.listdir(base)
        except OSError:
            return 0
        n = 0
        for name in names:
            pfx = next((p for p in prefixes if name.startswith(p)), None)
            if pfx is None:
                continue
            m = re.match(re.escape(pfx) + r"(\d+)_", name)
            if m and not cls._pid_alive(int(m.group(1))):
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
                n += 1
        if n:
            cls._LOG.info("reaped %d orphaned dir(s) under %s", n, base)
        return n

    @staticmethod
    def _scratch_dir(base: str | None, prefix: str) -> Path:
        """Create a fresh run directory (on tmpfs ``base`` when given).

        The "make a workdir" half of run management; **teardown stays with the
        caller** — a fork-per-call run leaves it in place (the caller reads the
        output files), a COW solve removes it (the result is in shared
        buffers).  The name embeds the creator PID so :meth:`reap_orphans` can
        recognise leftovers.
        """
        import tempfile
        return Path(tempfile.mkdtemp(prefix=f"{prefix}{os.getpid()}_", dir=base))

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        """True if ``pid`` names a live process (``PermissionError`` → alive,
        not ours).  Conservative: on any doubt, treat as alive (never reap)."""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return True
        return True

    @staticmethod
    def _end_process(p) -> None:
        """Reliably end a child: SIGTERM → bounded join → SIGKILL → join.

        ``terminate()`` alone is not enough — a legacy code that installs a
        SIGTERM handler (or ignores it) would survive, turning every timeout
        path into an unbounded hang.  SIGKILL cannot be caught, so this always
        reaps."""
        p.terminate()
        p.join(ExecutionBody._TERM_GRACE)
        if p.is_alive():
            ExecutionBody._LOG.warning("child pid=%s ignored SIGTERM within %.1fs — SIGKILL",
                                 p.pid, ExecutionBody._TERM_GRACE)
            p.kill()
            p.join()
