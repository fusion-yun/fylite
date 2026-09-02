"""Data handles + the run root (engine concern 4).

★★The problem this solves.  A reconstruction result carries a 65x65 psi map
and seven 1-D profiles.  A tool face that returns them inline floods its
caller's context; one that drops them lies.  :func:`fylite.engine.summarize`
already answered half of that — arrays become typed summaries with a
``sha256`` — but a summary can prove identity and cannot get the data BACK,
so the only way to carry a result into the next call was to inline it or to
pass a bare filesystem path with no type, no provenance and no record.

A **handle** is the missing half: ``fylite://<run-id>/<port>``, resolvable to
the bytes the summary describes.  It is a TOOL-FACE concept and stops here —
nothing in ``scenario/`` or the kernel knows a handle exists; arguments are
dereferenced at the service boundary, exactly where they are shaped on the
way out.

★The run root is the other half of the same idea: results have to be
somewhere before they can be referred to.  ``$FYLITE_RUN_DIR`` (default: the
user's cache directory) holds one directory per session and one per run
inside it, written once — so a handle stays valid for as long as the run
directory does, and a second run never overwrites a first.

Module scope stays stdlib (DE-COMP-03): numpy is imported inside the two
functions that touch an array.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from datetime import timezone
from pathlib import Path

#: where runs are written; unset -> the user's cache directory, never the
#: current working directory (a tool that scatters g-files across whatever
#: directory the host happened to start in is a tool nobody can clean up).
RUN_ENV = "FYLITE_RUN_DIR"

#: an explicit session id, so several processes can share one session's root
SESSION_ENV = "FYLITE_SESSION"

SCHEME = "fylite://"

#: the two files a run directory always has once it is delivered
ARRAYS = "arrays.npz"
RESULT = "result.json"

_REF = re.compile(r"^fylite://(?P<run>[A-Za-z0-9._-]+)/(?P<port>[^/].*)$")


# --------------------------------------------------------------------------- #
# where things live
# --------------------------------------------------------------------------- #
def runs_root() -> Path:
    """The directory runs are written under."""
    raw = os.environ.get(RUN_ENV)
    if raw:
        return Path(raw).expanduser()
    cache = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(cache).expanduser() / "fylite" / "runs"


#: the derived session id, computed once per process (see below)
_SESSION: str | None = None


def session_id() -> str:
    """This session's id — ``$FYLITE_SESSION`` when set, else one derived
    from the process, so runs made by one server process group together.

    ★★It used to derive the id on EVERY call, from the current second — so a
    process that ran two tools a second apart put them in two different
    "sessions".  Measured: one process, two calls 1.2 s apart, two session
    directories, two one-node ledgers, **and the lineage edge between them
    silently gone** — the handle still resolved, the numbers were right, and
    the only thing that was wrong was the record, which is what the ledger
    exists for.  The environment variable still wins on every call (a host
    may set it late); only the DERIVED id is fixed, once, per process.
    """
    global _SESSION
    env = os.environ.get(SESSION_ENV)
    if env:
        return env
    if _SESSION is None:
        _SESSION = f"s-{_stamp()}-{os.getpid()}"
    return _SESSION


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def new_run(*, session: str | None = None) -> Path:
    """Create and return a fresh run directory.

    Never reuses one: a run id that is already taken gets ``-2``, ``-3``…
    (the non-clobbering rule :func:`fylite.engine.reserve_dir` applies to a
    delivery, applied here to the run itself).

    ★★The id is unique across the WHOLE run root, not only within its own
    session, and that is a correctness requirement rather than tidiness: a
    handle is ``fylite://<run>/<port>`` with no session in it, and
    :func:`find_run` searches every session — so two sessions holding the
    same id make a handle resolve to whichever one sorts first.  It was
    reachable: the ids are second-stamped, so any second process (the replay
    driver re-running a recorded session is the obvious one) could mint a
    colliding id, and the collision is silent — the handle still resolves,
    to somebody else's numbers.
    """
    root = runs_root()
    base = root / (session or session_id())
    stem = f"r-{_stamp()}"
    cand, n = base / stem, 1
    while cand.exists() or any(root.glob(f"*/{cand.name}")):
        n += 1
        cand = base / f"{stem}-{n}"
    cand.mkdir(parents=True)
    return cand


def run_id_of(run_dir) -> str:
    return Path(run_dir).name


def find_run(run_id: str) -> Path:
    """The directory of ``run_id``, searched across the sessions under the
    run root — a handle names the RUN, not the session that made it, so it
    survives being passed to a different process."""
    root = runs_root()
    direct = root / run_id
    if direct.is_dir():
        return direct
    for p in sorted(root.glob(f"*/{run_id}")):
        if p.is_dir():
            return p
    #: ★★A READABLE ALIAS is tried LAST, never first (A-5).  The id is the
    #: identity — it is what the ledger's edges join and what a manifest
    #: records — so a run whose id is present must resolve to it even if some
    #: alias happens to share the spelling.  The register is a second way to
    #: SAY a run, and a second way to say something must never become a
    #: second thing to keep in step.
    from .alias import AliasError, resolve as _alias
    try:
        rid = _alias(run_id)
    except AliasError:
        rid = None
    if rid and rid != run_id:
        return find_run(rid)
    raise LookupError(
        f"no run {run_id!r} under {root} — the handle may be from another "
        f"machine, the run root (${RUN_ENV}) may have been cleaned, or the "
        "name may never have been registered (`fylite alias`)")


# --------------------------------------------------------------------------- #
# handles
# --------------------------------------------------------------------------- #
def handle(run_id: str, port: str) -> str:
    return f"{SCHEME}{run_id}/{port}"


def parse(ref: str) -> tuple[str, str]:
    """``fylite://<run-id>/<port>`` -> ``(run_id, port)``."""
    m = _REF.match(str(ref))
    if not m:
        raise ValueError(f"not a fylite handle: {ref!r} "
                         f"(expected {SCHEME}<run-id>/<port>)")
    return m.group("run"), m.group("port")


def is_ref(obj) -> bool:
    """True for the argument form ``{"$ref": "fylite://…"}``."""
    return (isinstance(obj, dict) and set(obj) == {"$ref"}
            and isinstance(obj["$ref"], str)
            and obj["$ref"].startswith(SCHEME))


def deref(obj):
    """Replace every ``{"$ref": …}`` in a tool's arguments with its value.

    Recursive and total: a handle can sit anywhere an argument can, including
    inside a list or under a nested key.
    """
    if is_ref(obj):
        return resolve(obj["$ref"])
    if isinstance(obj, dict):
        return {k: deref(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deref(v) for v in obj]
    return obj


def resolve(ref: str):
    """The value a handle points at: an array from ``arrays.npz``, or the
    scalar/path recorded under the same name in ``result.json``."""
    import numpy as np
    run, port = parse(ref)
    d = find_run(run)
    npz = d / ARRAYS
    if npz.is_file():
        with np.load(npz, allow_pickle=False) as z:
            if port in z.files:
                return z[port]
            ports = sorted(z.files)
    else:
        ports = []
    scalar = _scalar_at(d, port)
    if scalar is not _MISS:
        return scalar
    shown = ", ".join(ports[:12]) + (" …" if len(ports) > 12 else "")
    raise LookupError(
        f"run {run} has no port {port!r}"
        + (f"; it carries: {shown}" if ports else " (no arrays were stored)"))


_MISS = object()


def _scalar_at(run_dir: Path, port: str):
    """A value out of ``result.json`` addressed the way a handle addresses
    an array — so a path (``gfile``) is reachable by handle too."""
    p = Path(run_dir) / RESULT
    if not p.is_file():
        return _MISS
    node = json.loads(p.read_text())
    for seg in _segments(port):
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        elif isinstance(node, list) and str(seg).isdigit() and \
                int(seg) < len(node):
            node = node[int(seg)]
        else:
            return _MISS
    return _MISS if isinstance(node, (dict, list)) else node


def _segments(port: str):
    """``a.b[2].c`` -> ``['a', 'b', '2', 'c']`` — the path grammar handles and
    the stored array keys share."""
    return [s for s in re.split(r"\.|\[|\]", port) if s]


# --------------------------------------------------------------------------- #
# storing a result
# --------------------------------------------------------------------------- #
def collect_arrays(obj, prefix: str = "") -> dict:
    """``{port: array}`` for every bulk numeric leaf of a result.

    The port names are the SAME paths :func:`fylite.engine.summarize` stamps
    into its summaries — one grammar, two readers, and
    ``test_handles.py::test_every_ref_a_summary_emits_resolves`` is what keeps
    them from drifting.
    """
    import numpy as np
    out: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(collect_arrays(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(obj, np.ndarray):
        if obj.size:
            out[prefix] = obj
        return out
    if isinstance(obj, (list, tuple)):
        arr = None
        if not _is_short_scalar_list(obj):
            try:
                arr = np.asarray(obj)
            except Exception:                    # noqa: BLE001 — ragged input
                arr = None
        if arr is not None and arr.size and np.issubdtype(arr.dtype,
                                                          np.number):
            out[prefix] = arr
            return out
        for i, v in enumerate(obj):
            out.update(collect_arrays(v, f"{prefix}[{i}]"))
    return out


#: mirrors ``summarize``'s inline rule: a short list of plain scalars travels
#: in the payload itself and is not a stored array.
_MAX_INLINE = 16


def _is_short_scalar_list(obj) -> bool:
    return (len(obj) <= _MAX_INLINE
            and all(isinstance(v, (int, float, bool, str)) or v is None
                    for v in obj))


def store(run_dir, result: dict, payload: dict) -> Path:
    """Write ``arrays.npz`` + ``result.json`` into ``run_dir``; return it."""
    import numpy as np
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    arrays = collect_arrays(result)
    if arrays:
        np.savez_compressed(d / ARRAYS, **arrays)
    (d / RESULT).write_text(json.dumps(payload, indent=1, default=str))
    return d
