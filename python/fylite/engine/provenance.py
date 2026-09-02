"""Run provenance + structured delivery (K-17; engine concern 2).

The reproducibility record around a result: acceptance verdicts,
:class:`RunManifest`, environment fingerprints, versioned non-clobbering
delivery.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path

#: ★★``import numpy as np`` was here, at module scope, and it was the ONE
#: thing in this subpackage that broke DE-COMP-03's invariant — "``fylite
#: .engine``'s top-level imports are stdlib only; numpy and heavy
#: dependencies are imported lazily inside functions".  Every other engine
#: module already obeyed it.  Four call sites need numpy and each of them
#: now imports it where it is used, which is what the invariant asks for
#: and what ``test_engine_imports_only_stdlib.py`` checks.

from .. import _paths

from ._util import sha256_file
from .body import RunTrace


# =========================================================================== #
# Run provenance + structured delivery (K-17)
# =========================================================================== #
# Four-state acceptance (FYDOC-REPORT-04 R04).
PASS = "pass"
CONDITIONAL = "conditional"
FAIL = "fail"
UNEVALUATED = "unevaluated"


# --------------------------------------------------------------------------- #
# Fingerprints
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")



def _canonical(obj):
    """A JSON-serializable, order-stable projection (numpy → list, sorted keys)."""
    import numpy as np
    if isinstance(obj, dict):
        return {str(k): _canonical(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, np.ndarray):
        return _canonical(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def digest(obj) -> str:
    """SHA-256 of the canonical JSON of ``obj`` (arrays/dicts order-stable)."""
    blob = json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def git_rev(repo=None) -> dict:
    """Best-effort code revision of the fylite checkout (``rev`` + ``dirty``)."""
    root = Path(repo) if repo else _paths.PKG
    try:
        rev = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5).stdout.strip())
        return {"rev": rev or "unknown", "dirty": dirty}
    except Exception:                                # noqa: BLE001 — provenance is best-effort
        return {"rev": "unknown", "dirty": False}


def env_fingerprint() -> dict:
    """Python / platform / numpy versions, the solver library's hash, the
    result-bearing environment variables and the thread setting.

    ★It used to hash ``libefit``/``libneo``/``libgeo``.  Those are gone
    (LICENSE 3.1/3.2) and so are their paths, and the fingerprint is BETTER
    for it rather than poorer: what a run needs to be reproducible from is
    the library it actually used, and there is now exactly one.  A record
    naming three libraries that were never present said less, not more.
    """
    import numpy as np
    libs = {}
    for name, p in (("libfylite", _paths.KERNEL_LIB),):
        if Path(p).exists():
            libs[name] = {"path": str(p), "sha256": sha256_file(p)}
    return {"python": sys.version.split()[0], "platform": platform.platform(),
            #: ★★WHICH BUILD produced the numbers (A-7).  A record that does
            #: not name the host cannot explain a cross-host difference, and
            #: explaining one is exactly what A-7's criterion asks the record
            #: to do — so「哪个宿主」has to be IN it, not inferred from the
            #: fact that a Python process wrote it.
            "host": "native",
            "numpy": np.__version__, "libraries": libs,
            "variables": _result_bearing_variables(),
            "threads": _thread_setting()}


def _result_bearing_variables() -> dict:
    """The environment variables that can change a NUMBER, and their values.

    ★★A-3.  Which variables those are is READ OFF THE DECLARATION
    (``_environment.json``, ``affects_result``), not remembered here: a
    fingerprint that carries a hand-kept list is a list that goes stale on
    the day someone adds a variable, and the failure is silent — the run
    records an environment it was not run in.

    A variable that is unset is recorded as ``None`` rather than omitted:
    「没有设」 is a fact about the run, and a key that simply is not there
    cannot be told apart from a fingerprint written before the variable
    existed.
    """
    try:
        from .manifest import environment as _declared
        declared = _declared()
    except Exception:                            # noqa: BLE001
        #: ★the fingerprint must not be the thing that breaks a run; say so
        #: rather than silently reporting an empty environment
        return {"$error": "the environment declaration could not be read"}
    return {name: os.environ.get(name)
            for name, spec in sorted(declared.items())
            if spec.get("affects_result")}


def _thread_setting() -> dict:
    """What the kernel's parallel paths were allowed to use.

    ★MEASURED not to change an answer (2026-08-26, `breakdown-iter` and
    `discharge-iter` bit-identical at 1 and 4 threads), and recorded anyway:
    the day that stops being true, this is what says which count produced
    which numbers.  ``rayon`` is asked for at pool-build time and falls back
    to the machine's available parallelism, so BOTH are recorded — the
    request and what the machine could have given it.
    """
    try:
        avail = len(os.sched_getaffinity(0))     # what this process may use
    except AttributeError:                       # pragma: no cover - non-Linux
        avail = os.cpu_count()
    return {"RAYON_NUM_THREADS": os.environ.get("RAYON_NUM_THREADS"),
            "available_parallelism": avail}


# --------------------------------------------------------------------------- #
# Human-decision records (audit trail)
# --------------------------------------------------------------------------- #
def record_decision(actor: str, action: str, rationale: str, **fields) -> dict:
    """One human-decision record for the manifest's audit trail.

    E.g. a banned channel, a constraint choice, a threshold override, or a
    manual acceptance — ``actor`` is who decided, ``rationale`` is why.
    """
    rec = {"actor": actor, "action": action, "rationale": rationale, "at": _now()}
    rec.update(_canonical(fields))
    return rec


# --------------------------------------------------------------------------- #
# Four-state acceptance
# --------------------------------------------------------------------------- #
# Project-level default thresholds (override per delivery).  A criterion passes
# at <= pass, is conditional at <= warn, else fails; a missing input → unevaluated.
DEFAULT_THRESHOLDS = {
    "terror": {"pass": 0.03, "warn": 0.10},         # EFIT fit residual
    "chi_pressure": {"pass": 5.0, "warn": 50.0},    # reduced pressure χ² (if present)
    "require_converged": True,                       # `converged` must be truthy
}

# Ordered worst-first so the overall verdict is the worst criterion.
_ORDER = {FAIL: 3, CONDITIONAL: 2, PASS: 1, UNEVALUATED: 0}


def _score_upper(value, thr) -> str:
    import numpy as np
    if value is None or not np.isfinite(value):
        return UNEVALUATED
    if value <= thr["pass"]:
        return PASS
    if value <= thr["warn"]:
        return CONDITIONAL
    return FAIL


def acceptance(result: dict, thresholds: dict | None = None) -> dict:
    """Four-state acceptance verdict for a ``result``.

    ``thresholds`` is a criterion register — one entry per criterion, in one
    of three forms:

    ``{"pass": x, "warn": y}``
        an UPPER-bounded metric (``terror``, ``chi_pressure``): at or below
        ``pass`` passes, at or below ``warn`` is conditional, above fails.
    ``{"require": true}``
        a flag the run reports about ITSELF (``converged``, ``settled``):
        true passes, false fails, absent is ``unevaluated``.
    ``{"tbd": "<why>"}``
        a criterion that EXISTS but has no threshold yet.  It scores
        ``unevaluated`` and carries its reason — ★which is the point: a
        capability with no criterion at all is indistinguishable from one
        whose criteria all happened to be missing, and the second is a
        different fact.

    ★★What is NOT a criterion.  ``stable``, ``feasible`` and their kind are
    RESULTS: a vertical-stability analysis that correctly reports an unstable
    column, or a breakdown design that correctly reports「not feasible under
    these limits」, is a SUCCESSFUL run with an unwelcome answer.  Scoring
    them here would collapse「can this number be trusted」into「is the physics
    favourable」, and a caller reading `fail` would not be able to tell which
    one it had.  Each manifest says so where the temptation arises.

    The overall ``state`` is the worst criterion; a criterion whose metric is
    absent is ``unevaluated`` and never silently passed.  Returns
    ``{state, criteria:[…], thresholds}``.
    """
    #: ★★A declared register REPLACES the defaults; it does not merge with
    #: them.  Merging is how a transport march came to be scored against the
    #: reconstruction's `terror` and `chi_pressure` — two criteria it can
    #: never meet, sitting `unevaluated` in its record forever and saying
    #: nothing except that the wrong register was applied.  A capability that
    #: states its criteria has stated ALL of them; passing nothing still
    #: gets :data:`DEFAULT_THRESHOLDS`, which is what an un-declared caller
    #: (a bare `deliver`) should be held to.
    thr = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    criteria = []

    import numpy as np

    for name, spec in thr.items():
        if name.startswith("@") or name == "require_converged":
            continue
        if not isinstance(spec, dict):
            continue
        if "tbd" in spec:
            criteria.append({"name": name, "value": None,
                             "state": UNEVALUATED, "tbd": spec["tbd"]})
        elif spec.get("require"):
            v = result.get(name)
            criteria.append({"name": name,
                             "value": None if v is None else bool(v),
                             "state": (UNEVALUATED if v is None
                                       else (PASS if v else FAIL))})
        elif "pass" in spec and "warn" in spec:
            v = result.get(name)
            v = float(v) if isinstance(v, (int, float, np.floating)) else None
            criteria.append({"name": name, "value": v,
                             "pass": spec["pass"], "warn": spec["warn"],
                             "state": _score_upper(v, spec)})

    #: ★the legacy spelling, kept because the reconstruction path and the
    #: shipped default both use it.  It says the same thing as
    #: ``{"converged": {"require": true}}`` and is scored once, not twice.
    if thr.get("require_converged") and not any(
            c["name"] == "converged" for c in criteria):
        conv = result.get("converged")
        criteria.append({"name": "converged",
                         "value": None if conv is None else bool(conv),
                         "state": (UNEVALUATED if conv is None
                                   else (PASS if conv else FAIL))})

    criteria.sort(key=lambda c: c["name"])
    if not criteria:
        overall = UNEVALUATED
    else:
        overall = max((c["state"] for c in criteria), key=lambda s: _ORDER[s])
    return {"state": overall, "criteria": criteria,
            "thresholds": _canonical(thr)}


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
@dataclass
class RunManifest:
    """The reproducibility + acceptance record delivered beside a result."""
    created: str
    code: dict
    environment: dict
    config: dict = field(default_factory=dict)
    inputs: dict = field(default_factory=dict)
    artifacts: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    acceptance: dict | None = None
    #: the execution :class:`RunTrace` (environment identity / duration /
    #: disposition) that produced the result — ties the delivery to its call.
    trace: dict | None = None

    #: JSON-LD context for the semantic keys (SP-REPORT-15 T-1.3).  Kept here,
    #: values duplicated from :mod:`fylite.engine.manifest`, so engine.py stays
    #: import-free beyond the stdlib (conformance invariant I-8).
    SEMANTIC_CONTEXT = {
        "sp": "https://spdata.org/sp#",
        "prov": "http://www.w3.org/ns/prov#",
        "fylite": "urn:fylite:",
    }

    def to_dict(self, *, semantic: bool = True) -> dict:
        """The manifest as a JSON-ready dict.

        With ``semantic=True`` (default) the flat record is prefixed with
        JSON-LD identity keys — strictly additive: every legacy key keeps its
        name, place, and value, so flat-JSON consumers are unaffected.  The
        manifest is typed ``prov:Entity`` (it is the delivered *record*; the
        run it documents is the ``prov:Activity`` captured under ``trace``).
        """
        d = asdict(self)
        if not semantic:
            return d
        return {
            "@context": dict(self.SEMANTIC_CONTEXT),
            "@id": "urn:fylite:run/" + self.created,
            "@type": ["fylite:RunManifest", "prov:Entity"],
            **d,
        }

    def write(self, path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False))
        return p


def _trace_dict(trace) -> dict | None:
    """Normalize a :class:`RunTrace` (or plain dict) into a JSON-friendly dict."""
    if trace is None:
        return None
    if isinstance(trace, RunTrace):
        return _canonical(asdict(trace))
    return _canonical(trace)


def build_manifest(result: dict, *, config=None, inputs=None, decisions=None,
                   thresholds=None, artifacts=None, trace=None) -> RunManifest:
    """Assemble a :class:`RunManifest` from a result (no files written).

    ``config`` is the run parameters, ``inputs`` a dict of named input objects
    (each digested, not stored verbatim), ``artifacts`` a list of on-disk paths
    (each hashed).  ``trace`` is the execution :class:`RunTrace` (or the result's
    ``run_trace``) — the environment identity + duration that produced the result.
    Acceptance is scored from ``result`` + ``thresholds``.
    """
    art = []
    for a in (artifacts or []):
        p = Path(a)
        art.append({"name": p.name, "path": str(p), "sha256": sha256_file(p),
                    "bytes": p.stat().st_size if p.is_file() else None})
    return RunManifest(
        created=_now(),
        code=git_rev(),
        environment=env_fingerprint(),
        config=_canonical(config or {}),
        inputs={k: digest(v) for k, v in (inputs or {}).items()},
        artifacts=art,
        decisions=[_canonical(d) for d in (decisions or [])],
        acceptance=acceptance(result, thresholds),
        trace=_trace_dict(trace if trace is not None else result.get("run_trace")),
    )


# --------------------------------------------------------------------------- #
# Versioned, non-overwriting delivery
# --------------------------------------------------------------------------- #
def reserve_dir(base, *, overwrite: bool = False) -> Path:
    """Reserve an output directory that never silently clobbers a prior delivery.

    If ``base`` is absent or empty it is used as-is; if it already holds files
    and ``overwrite`` is false, the next free ``…-v2`` / ``…-v3`` is created and
    returned instead (immutable versioning).  With ``overwrite=True`` the exact
    ``base`` is used (and reused).
    """
    base = Path(base)
    if overwrite or not base.exists() or not any(base.iterdir()):
        base.mkdir(parents=True, exist_ok=True)
        return base
    stem = base.name
    n = 2
    while True:
        cand = base.with_name(f"{stem}-v{n}")
        if not cand.exists() or not any(cand.iterdir()):
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        n += 1


def deliver(result: dict, out, *, config=None, inputs=None, decisions=None,
            thresholds=None, trace=None, overwrite: bool = False) -> dict:
    """Deliver a reconstruction into a versioned, manifested directory.

    Reserves ``out`` (non-overwriting unless ``overwrite``), copies the result's
    g-file + any a-files into it, scores four-state acceptance, and writes
    ``manifest.json`` + ``acceptance.json``.  ``trace`` is the execution
    :class:`RunTrace` (defaults to the result's ``run_trace``) — its environment
    identity + duration are recorded in the manifest, tying the delivery to the
    call that produced it.  Returns ``{dir, manifest, acceptance}`` — ``dir`` is
    the *actual* directory used (may be a ``…-vN`` sibling of ``out``).
    """
    dest = reserve_dir(out, overwrite=overwrite)
    delivered = []
    gfile = result.get("gfile")
    if gfile and Path(gfile).is_file():
        g = dest / Path(gfile).name
        if Path(gfile).resolve() != g.resolve():
            shutil.copyfile(gfile, g)
        delivered.append(g)
        wd = result.get("workdir")
        if wd and Path(wd).is_dir():
            for a in Path(wd).glob("a[0-9]*.*"):
                shutil.copyfile(a, dest / a.name)
                delivered.append(dest / a.name)

    manifest = build_manifest(result, config=config, inputs=inputs,
                              decisions=decisions, thresholds=thresholds,
                              artifacts=delivered, trace=trace)
    manifest.write(dest / "manifest.json")
    (dest / "acceptance.json").write_text(
        json.dumps(manifest.acceptance, indent=2))
    return {"dir": str(dest), "manifest": manifest.to_dict(),
            "acceptance": manifest.acceptance}
