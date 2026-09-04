"""The public V&V register (`benchmark/`), readable and runnable from the CLI.

★★Same face as the scenario corpus (:mod:`.cases`), second corpus.  A case is
one ``fyo:ScenarioSpecification`` the code RUNS; a benchmark record is one
``fyo:ComparisonRecord`` (FYO-ADR-08 over ``spo:RegistryRecord``) that says
what the code was MEASURED against, by which gates, to what number.  Both are
fyo / spo JSON-LD on disk beside the checkout, neither ships with the wheel,
and ``fylite cases`` is the one verb that lists, shows, checks and runs
either — ``--benchmark`` selects this one (2026-09-02 整合收敛).

★The register here is a RENDERING: the kernel repository's
``docs/cases/registry.jsonld`` is the source, ``tools/benchmark-publish.py``
(there) writes this directory — the same records with every in-tree pointer
turned into an out-of-tree one (``$FYLITE_KERNEL/…`` for the private checkout,
``$FYDOC_ORACLE/…`` for the reference store), each reference dataset given
its admissibility class and sha256, and one extra finding per record: the
outcome of running its gates on the day of publication.  Nothing here is
edited by hand; a stale record is fixed at the source and re-rendered.

★★**Running a record runs the PRIVATE gates.**  The gates a record names live
in the kernel checkout (``pytest tests/…`` there, or ``cargo test``); this
module runs them only when ``$FYLITE_KERNEL`` names such a checkout with the
store mounted, and otherwise REFUSES BY NAME — it never re-derives a number
the record claims (宁可拒绝，不给假数), because a comparison recomputed by a
different route would be a second record, not a re-run of this one.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .cases import CorpusMissing, _lang

#: the admissibility classes the register uses (`license` on a pointer)
CLASSES = ("public", "public-derived", "restricted", "restricted-derived",
           "experiment", "private-artefact")
KINDS = ("verification", "benchmark", "validation")
BASES = ("reference_stated", "measured_band", "machine_precision")
VERDICTS = ("pass", "fail", "inconclusive", "unevaluated")
STATES = ("proposed", "under_test", "accepted", "retired")
KERNEL_ENV = "FYLITE_KERNEL"
STORE_ENV = "FYDOC_ORACLE"
#: 旧名，仍然认。2026-09-04 冻结判据库随 `oracle/` 自 fydata 迁入 fydoc，变量名跟着改；
#: 但名字是**部署已经设好的东西**，改名而不认旧名，会让既有部署静默退回 `tests/data`
#: ——那正是本包最不该发生的一类失灵（指针解析不报错，只是解析不到）。
STORE_ENV_LEGACY = "FYDATA_ORACLE"


def registry_dir(explicit=None) -> Path:
    """The V&V register — repo data beside the checkout, absent → refuse.

    ★★2026-09-04 实测：它搬到 `docs/benchmark/` 之后这里没跟上，于是**十条闸子
    整体转为 skip**（`test_public_register.py` 报「registry.jsonld not in this
    checkout」）而没有一处报错——一个解析不到的指针不会失败，只会安静地不看。
    新旧位置都认：搬家期间两边都可能是对的，而认错位置的代价是「看起来绿」。
    """
    here = Path(__file__).resolve().parents[3]
    roots = ([Path(explicit)] if explicit else
             [Path("docs/benchmark"), here / "docs" / "benchmark",
              Path("benchmark"), here / "benchmark"])
    for r in roots:
        if (r / "registry.jsonld").is_file():
            return r
    raise CorpusMissing(
        "the V&V register: no registry.jsonld found (looked in "
        + ", ".join(str(r) for r in roots)
        + ") — the V&V register is repository data and does not ship with the wheel; "
          "run from a checkout or pass --dir")


def graph(d: Path | None = None) -> list[dict]:
    d = registry_dir() if d is None else Path(d)
    return json.loads((d / "registry.jsonld").read_text(encoding="utf-8"))["@graph"]


def short_id(rec: dict) -> str:
    return str(rec.get("id", "")).rsplit("/", 1)[-1]


def rerun(rec: dict) -> dict | None:
    """The publication-day finding (`finding_kind` starting with `re-run`), if any."""
    for f in reversed(rec.get("findings") or []):
        if str(f.get("finding_kind", "")).startswith("re-run"):
            return f
    return None


def classes_of(rec: dict) -> list[str]:
    return sorted({c.get("license") for c in (rec.get("run") or {}).get("has_input", [])
                   if c.get("license")})


def gates_of(rec: dict) -> list[str]:
    return [g["name"] for g in (rec.get("run") or {}).get("realizes", [])]


def records(d: Path | None = None) -> list[dict]:
    """One row per record, in register order."""
    out = []
    for r in graph(d):
        rr = rerun(r)
        out.append({"record_id": short_id(r), "kind": r.get("comparison_kind"),
                    "title": _lang(r.get("title")),
                    "reference": "；".join(x.get("name", "") for x in r.get("compared_reference") or []),
                    "scenario": r.get("scenario"), "classes": classes_of(r),
                    "verdict": r.get("overall_verdict"), "state": r.get("assertion_state"),
                    "rerun": (rr or {}).get("verdict"), "rerun_note": (rr or {}).get("deviation_literal"),
                    "gates": gates_of(r),
                    "report": ((r.get("report") or {}).get("storage_uri"))})
    return out


def load(record_id: str, d: Path | None = None) -> dict:
    for r in graph(d):
        if short_id(r) == record_id or r.get("id") == record_id:
            return r
    raise KeyError(record_id)


def problems(rec: dict, d: Path) -> list[str]:
    """What is structurally wrong with one record (empty = sound).

    ★The same list `python/tests/test_public_register.py` asserts empty;
    the CLI's ``--check`` and the gate read one function so they cannot drift.
    """
    rid = short_id(rec)
    out = []
    if rec.get("type") != "fyo:ComparisonRecord":
        out.append(f"type is {rec.get('type')!r}, not fyo:ComparisonRecord")
    if rec.get("comparison_kind") not in KINDS:
        out.append(f"comparison_kind {rec.get('comparison_kind')!r}")
    for key in ("title", "compared_subject", "compared_reference", "criteria", "findings",
                "run", "assertion_state", "overall_verdict", "account", "report"):
        if rec.get(key) is None:
            out.append(f"no {key}")
    if rec.get("assertion_state") not in STATES:
        out.append(f"assertion_state {rec.get('assertion_state')!r}")
    if rec.get("overall_verdict") not in VERDICTS:
        out.append(f"overall_verdict {rec.get('overall_verdict')!r}")
    for f in rec.get("findings") or []:
        if f.get("verdict") not in VERDICTS:
            out.append(f"finding {f.get('title')!r} verdict {f.get('verdict')!r}")
    for c in rec.get("criteria") or []:
        if c.get("tolerance_basis") not in BASES:
            out.append(f"criterion {c.get('quantity_label')!r} has no tolerance_basis")
        if c.get("tolerance_basis") == "machine_precision" and rec.get("comparison_kind") != "verification" \
                and not any("verification" in str(x) for x in c.get("caveat", [])):
            out.append(f"criterion {c.get('quantity_label')!r} claims machine precision in a "
                       f"{rec.get('comparison_kind')} record without saying why")
    if rerun(rec) is None:
        out.append("no re-run finding (finding_kind `re-run…`) — the register was not published by the tool")
    run = rec.get("run") or {}
    if not run.get("realizes"):
        out.append("names no gate")
    for g in run.get("realizes", []):
        name = g.get("name", "")
        if name.startswith("$"):
            if not g.get("caveat"):
                out.append(f"out-of-tree gate {name} carries no caveat")
        elif not (d.parents[0] / name).exists():
            out.append(f"in-tree gate {name} is gone")
    for c in run.get("has_input", []):
        uri = c.get("storage_uri", "")
        if not uri.startswith("$"):
            out.append(f"input {uri!r} is not an out-of-tree pointer")
        if c.get("license") not in CLASSES:
            out.append(f"input {uri!r} has no admissibility class")
        if not c.get("checksum") and not any("sha256" in str(x) for x in c.get("caveat", [])):
            out.append(f"input {uri!r} has neither a checksum nor a caveat saying why")
    rep = (rec.get("report") or {}).get("storage_uri")
    if rep and not (d / rep).is_file():
        out.append(f"report {rep} is gone")
    scn = rec.get("scenario")
    if scn:
        name = scn.rsplit("/", 1)[-1]
        if not (d / "scenarios" / f"{name}.fyo.jsonld").is_file():
            out.append(f"scenario {scn} has no document")

    #: ★retired vocabulary = a CURIE (`fylite:x`, `vv:x` — no space after the colon)
    #: as a key, a type or a value.  Prose such as「fylite: kernel.gs_inverse_solve …」
    #: in a comment is a colon in a sentence, not a namespace, and is not flagged.
    curie = re.compile(r"(?<![\w/])(?:fylite|vv):(?=\S)")

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if curie.match(k):
                    yield k
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        elif isinstance(x, str) and curie.search(x):
            yield x[:60]
    hits = list(walk(rec))
    if hits:
        out.append(f"retired vocabulary present ({len(hits)}): {hits[0]!r}")
    return out


# --------------------------------------------------------------------------- #
# running the gates
# --------------------------------------------------------------------------- #
def store_dir() -> Path | None:
    """Where `$FYDOC_ORACLE/…` pointers resolve: the variable, else the checkout's
    `tests/data` (the symlink `.gitignore` describes); None when neither is a directory."""
    raw = os.environ.get(STORE_ENV) or os.environ.get(STORE_ENV_LEGACY)
    cands = [Path(raw).expanduser()] if raw else []
    cands.append(Path(__file__).resolve().parents[3] / "tests" / "data")
    return next((c for c in cands if c.is_dir()), None)


def resolve_pointer(uri: str) -> Path | None:
    """A record's `$FYDOC_ORACLE/…` pointer as a local path, or None when the store
    is not bound.  Other pointers (`$FYLITE_KERNEL/…`) are not resolved here — they
    name the private checkout, which :func:`kernel_checkout` binds."""
    if not uri.startswith(("$" + STORE_ENV + "/", "$" + STORE_ENV_LEGACY + "/")):
        return None
    root = store_dir()
    name = STORE_ENV if uri.startswith("$" + STORE_ENV + "/") else STORE_ENV_LEGACY
    return root / uri[len(name) + 2:] if root else None


def kernel_checkout(explicit=None) -> Path | None:
    p = Path(explicit) if explicit else (Path(os.environ[KERNEL_ENV]) if os.environ.get(KERNEL_ENV) else None)
    return p if p and (p / "tests").is_dir() else None


def gate_plan(rec: dict, kernel: Path | None) -> dict:
    """What running this record would execute, and what it cannot."""
    py, rust, here, refused = [], [], [], []
    for name in gates_of(rec):
        if name.startswith("$FYLITE_KERNEL/tests/"):
            py.append(name[len("$FYLITE_KERNEL/"):])
        elif name.startswith("$FYLITE_KERNEL/rust/"):
            rust.append(name[len("$FYLITE_KERNEL/"):])
        elif name.startswith("app/tests/"):
            here.append(name)
        else:
            refused.append(f"{name}: no host for this gate")
    if (py or rust) and kernel is None:
        refused.append(f"{len(py) + len(rust)} private gates: set ${KERNEL_ENV} to a kernel checkout "
                       "with fydata's oracle/ mounted at tests/data")
    if here:
        refused.append(f"{len(here)} browser gates: run `node app/tests/…` with playwright and a served site "
                       "(not driven from here)")
    #: the reference store: which of the record's inputs this host can see
    inputs = [c.get("storage_uri", "") for c in (rec.get("run") or {}).get("has_input", [])]
    store = store_dir()
    present = [u for u in inputs if (resolve_pointer(u) or Path("/nonexistent")).exists()]
    return {"pytest": py, "cargo": rust, "browser": here, "refused": refused,
            "store": str(store) if store else None,
            "inputs_present": present,
            "inputs_absent": [u for u in inputs if u.startswith("$" + STORE_ENV) and u not in present]}


def run(record_id: str, d: Path | None = None, kernel=None, *, python_pkg: Path | None = None) -> dict:
    """Run the record's private pytest gates in the kernel checkout; refuse what it cannot.

    Returns ``{record_id, plan, commands, returncode, summary}``; the pytest
    output goes to the caller's stdout so a person sees the same thing the
    publishing tool parsed.
    """
    d = registry_dir() if d is None else Path(d)
    rec = load(record_id, d)
    k = kernel_checkout(kernel)
    plan = gate_plan(rec, k)
    out = {"record_id": record_id, "plan": plan, "commands": [], "returncode": None, "summary": ""}
    if not plan["pytest"] or k is None:
        out["summary"] = "refused: " + "; ".join(plan["refused"]) if plan["refused"] else "nothing runnable"
        return out
    pkg = python_pkg or Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rA", "--tb=short",
           "-W", "ignore::pytest.PytestUnknownMarkWarning", *plan["pytest"]]
    out["commands"].append(" ".join(cmd))
    proc = subprocess.run(cmd, cwd=k, env=env)
    out["returncode"] = proc.returncode
    out["summary"] = ("gates passed" if proc.returncode == 0 else f"pytest exit {proc.returncode}") + (
        "; refused: " + "; ".join(plan["refused"]) if plan["refused"] else "")
    return out
