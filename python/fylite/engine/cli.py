"""CLI: generic argparse builder over the declarative spec in _cli.json.

Adding or reshaping a command edits the spec file; only procedural glue
(mode resolution, output formatting) lives in the ``_cli_*`` handlers.
Physics entry points are imported inside the handlers.
"""

from __future__ import annotations

import json
import sys

from .. import _paths

from .manifest import (load_manifests, manifest_catalog, resolve_entry,
                       seal_manifest, seal_manifests, validate_projection,
                       validate_structure, write_manifests)
from .serve import mcp_stdio, serve_stdio


# --------------------------------------------------------------------------- #
# CLI (generic builder + declarative spec in _cli.json)
#
# The command-line face converged into the engine, same discipline as the
# channel map: the generic machinery below builds an argparse parser from the
# declarative spec file (``_cli.json`` — commands, options, handler entries)
# and dispatches to ``_cli_*`` handler functions.  Adding or reshaping a
# command edits the spec file; only genuinely procedural glue (mode
# resolution, output formatting) lives in the handlers.
# --------------------------------------------------------------------------- #

CLI_SPEC_PATH = _paths.PKG / "_cli.json"

_CLI_TYPES = {"int": int, "float": float, "str": str}


def load_cli_spec() -> dict:
    """Load the declarative CLI spec (commands / options / handlers)."""
    return json.loads(CLI_SPEC_PATH.read_text())


def build_cli(spec: dict):
    """Build the argparse parser from a CLI spec — purely mechanical."""
    import argparse
    ap = argparse.ArgumentParser(prog=spec["prog"],
                                 description=spec["description"])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in spec["commands"]:
        p = sub.add_parser(cmd["name"], help=cmd["help"])
        owner = {}
        for group in cmd.get("exclusive", ()):
            g = p.add_mutually_exclusive_group()
            for flag in group:
                owner[flag] = g
        for arg in cmd.get("args", ()):
            kw = {k: v for k, v in arg.items() if k != "flags"}
            if "type" in kw:
                kw["type"] = _CLI_TYPES[kw["type"]]
            if isinstance(kw.get("metavar"), list):
                kw["metavar"] = tuple(kw["metavar"])
            target = owner.get(arg["flags"][0], p)
            target.add_argument(*arg["flags"], **kw)
    return ap


def _corpus_missing():
    """`scenario.cases.CorpusMissing`，惰性取——`engine` 在 import 期保持 stdlib 纯。"""
    from ..scenario.cases import CorpusMissing
    return CorpusMissing


def cli_main(argv=None) -> int:
    """The ``fylite`` console entry point: spec -> parser -> handler."""
    spec = load_cli_spec()
    ap = build_cli(spec)
    args = ap.parse_args(argv)
    handlers = {c["name"]: c["handler"] for c in spec["commands"]}
    try:
        return resolve_entry(handlers[args.cmd])(args, ap)
    except _corpus_missing() as exc:
        #: ★★2026-09-01：语料缺席从库里抛上来的是 `scenario.cases.CorpusMissing`，
        #: 一个**普通异常**；退出码是 CLI 的关切，翻译落在这里。此前它在库里直接
        #: 抛 `SystemExit`——CLI 看着对，代价是任何库调用者（含 pytest 的 fixture）
        #: 都接不住它，因为 `SystemExit` 是 `BaseException`。
        print(str(exc), file=sys.stderr)
        return 2


# ---- command handlers (procedural glue only) ------------------------------- #

#: ★``_cli_parse_extra`` was here: it turned ``--extra KEY=VALUE`` into
#: namelist overrides for a solver whose namelist left with LICENSE 3.1.  Its
#: three siblings went with it — ``--kfile`` (an EFIT namelist as INPUT, and
#: nothing in this distribution reads one back into measurements),
#: ``--preset`` (fit-control recipes expressed as namelist rows) and
#: ``--workdir`` (the staging directory of a fork-isolated shared-library
#: call).  What replaced the flag is not another flag: the Rust inverse's
#: knobs are its own parameters, and ``--no-probes`` — the one ``--extra``
#: use with a meaning here — is now the solve's ``probes=False`` rather than
#: a row of zeroed weights.


def _cli_alias(args, parser) -> int:
    """A-5 — name a run, or read the register."""
    from .alias import AliasError, listing, register

    if args.as_list:
        reg = listing(root=args.root)
        for tag, rid in reg.items():
            print(f"{tag:<32} {rid}")
        return 0
    if not args.run or not args.name:
        parser.error("give a run and a name, or --list")
    try:
        print(register(args.run, args.name, root=args.root))
    except AliasError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def _cli_whence(args, parser) -> int:
    """A-4 — trace a file back to the run that made it.

    ★The exit code is the verdict: a file that resolves to no run exits
    non-zero, because「找不到」 is a result a pipeline has to be able to act
    on, not a line somebody has to read.
    """
    from .whence import whence

    recs = [whence(f, root=args.root) for f in args.file]
    if args.as_json:
        print(json.dumps(recs if len(recs) > 1 else recs[0], indent=2,
                         ensure_ascii=False))
    else:
        for rec in recs:
            print(rec["line"])
    return 0 if all(r["found"] for r in recs) else 1


def _cli_replay(args, parser) -> int:
    """Re-run a recorded session and report what came back the same.

    ★The exit code is the verdict, not decoration: a replay in which any node
    was refused, or any artefact differs, exits non-zero.  A driver whose
    report has to be read to find out whether it worked is one nobody puts in
    a pipeline.
    """
    from .replay import DIFFERS, OK, replay
    rep = replay(args.ledger, session=args.session,
                 allow_version_drift=args.allow_version_drift)
    if args.as_json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        print(f"{rep['source']}\n  -> session {rep['session']}")
        for row in rep["nodes"]:
            head = f"  {row['id']:<26} {row['tool'] or '?':<28} {row['status']}"
            print(head + (f"  [{row['note']}]" if row.get("note") else ""))
            if row["status"] != OK:
                print(f"    {row.get('reason', '')}")
            for name, verdict in sorted(row["artifacts"].items()):
                print(f"    {name:<20} {verdict}")
        print(f"  {rep['replayed']} replayed, {rep['refused']} refused")
    bad = rep["refused"] or any(v == DIFFERS for r in rep["nodes"]
                                for v in r["artifacts"].values())
    return 1 if bad else 0


def _cli_report(args, parser) -> int:
    """One recorded run -> one MyST report, on the unified template.

    模板与体例的正文在 ``engine/report.py``（:data:`report.SECTIONS`）与
    ``docs/reference/report-template.md``；this handler is only the faucet.
    """
    from . import report
    if args.stdout:
        print(report.render(args.run, figures=False))
        return 0
    print(report.write(args.run, out=args.out, figures=args.figures))
    return 0


def _cli_serve(args, parser) -> int:
    return serve_stdio()


def _cli_mcp(args, parser) -> int:
    return mcp_stdio()


def _cli_describe(args, parser) -> int:
    cat = manifest_catalog()
    if args.text:
        #: ★the environment first: every "it does not work" this face
        #: produces on a fresh host is one of these eleven being unset.
        print("environment:")
        for name, v in cat["fylite:environment"].items():
            print(f"  {name:<24} {v['governs']}")
            print(f"  {'':<24} default: {v['default']}")
        print()
        for e in cat["fylite:manifests"]:
            ports = e["ports"]
            sig = (", ".join(p["port_id"] for p in ports["in"])
                   + " -> "
                   + ", ".join(p["port_id"] for p in ports["out"]))
            print(f"{e['@id']:<30} {e['kind']:<12} {e['entry']:<28} {sig}")
            print(f"{'':<30} {e['title']}")
            #: ★the acceptance criteria, because「what does a pass mean for
            #: this one」is a question a caller has before it calls, not
            #: after: a `tbd` criterion says the capability HAS a criterion
            #: and no threshold yet, which is a different fact from silence.
            for key, spec in (e.get("acceptance") or {}).items():
                if key.startswith("@") or not isinstance(spec, dict):
                    continue
                if "tbd" in spec:
                    how = "[TBD] " + spec["tbd"]
                elif spec.get("require"):
                    how = "must be true"
                else:
                    how = f"pass <= {spec['pass']}, warn <= {spec['warn']}"
                print(f"{'':<30} accept {key}: {how}")
    else:
        print(json.dumps(cat, indent=2))
    return 0


def _cases_dir(explicit=None):
    """The scenario corpus, found honestly or refused honestly.

    ★The corpus is REPO DATA at ``cases/`` (out of ``app/`` on
    2026-08-26, under ``docs/`` on 2026-09-01) — it does not ship with the
    wheel, the same way the machine decks do not.  So the search is: an
    explicit ``--dir``, the working directory, then the checkout this module
    sits in; a miss is an error that says where the corpus lives, not an
    empty listing (an empty listing reads as「there are no cases」, which is
    a different fact).
    """
    #: ★one resolver: `scenario.cases` owns the corpus (S-2 gave it a second
    #: consumer, the mapping layer), and two spellings of "where is cases/"
    #: is how the CLI and the mapper would one day disagree about it.
    from ..scenario import cases as _cases
    return _cases.corpus_dir(explicit)


def _cli_cases(args, parser) -> int:
    """List / show / check the scenario corpus.

    ★Why the CLI grows this at all: the CLI is the PRIMARY DEBUGGING
    ENVIRONMENT (2026-08-26 裁定, with the corpus promotion), and the
    scenarios are fixed as fyo/JSON-LD session documents.  A corpus the
    primary environment cannot even list is browser-private data wearing a
    top-level directory's name.
    """
    d = _cases_dir(args.dir)
    from ..scenario import cases as _cases
    entries = _cases.catalogue(d)

    #: getattr, because test rigs build bare namespaces for the older
    #: sub-modes and should not have to know about the newer flags
    if getattr(args, "plan", False) or getattr(args, "run_case", False):
        if not args.name:
            parser.error("--plan/--run need a case id (see `fylite cases`)")
        if getattr(args, "plan", False):
            p = _cases.plan(args.name, d, predict=getattr(args, "predict", False))
            print(json.dumps(p, ensure_ascii=False, indent=1, default=str))
            return 0
        r = _cases.run(args.name, d, predict=getattr(args, "predict", False))
        a = r["accounting"]
        print(f"{r['case_id']}  bar={r['bar']} -> fylite_{r['tool']}"
              + (f"  [device {r['device']}]" if r.get("device") else ""))
        print(f"  run {r['run']}  ({r['run_dir']})")
        print(f"  fields: {len(a['mapped'])} mapped, {len(a['sub'])} "
              f"sub-capability, {len(a['shared'])} shared, {len(a['ui'])} ui")
        for note in a["notes"]:
            print(f"  note: {note}")
        from pathlib import Path as _Path
        acc = json.loads((_Path(r["run_dir"]) / "acceptance.json").read_text())
        print(f"  acceptance: {acc['state']}  "
              + ", ".join(f"{c['name']}={c['state']}" for c in acc["criteria"]))
        print(f"  report: fylite report {r['run']}")
        return 0

    if args.name:
        hit = next((e for e in entries if e["case_id"] == args.name), None)
        if hit is None:
            print(f"no case {args.name!r}; the catalogue has: "
                  + ", ".join(e["case_id"] or "?" for e in entries))
            return 1
        print((d / hit["file"]).read_text().rstrip())
        return 0

    if args.check:
        bad = []
        #: ★The corpus directory holds the catalogue and the shared `@context`
        #: beside the cases.  Excepted BY NAME, not by pattern: an unrecognised
        #: `.jsonld` landing here is still exactly the mistake this check exists
        #: to catch.
        NOT_CASES = {"catalogue.jsonld", "context.jsonld"}
        on_disk = {p.name for p in d.glob("*.jsonld")} - NOT_CASES
        named = set()
        from ..scenario import BROWSER_ONLY_BARS, TOOLS
        bars = {t["bar"] for t in TOOLS.values() if t["bar"]} | set(BROWSER_ONLY_BARS)
        for e in entries:
            cid, doc_name = e["case_id"], e["file"]
            if not cid or not doc_name:
                bad.append(f"entry {cid or doc_name!r}: missing id/concretization")
                continue
            named.add(doc_name)
            f = d / doc_name
            if not f.is_file():
                bad.append(f"{cid}: names {doc_name}, which is not on disk")
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except ValueError as exc:
                bad.append(f"{cid}: {doc_name} does not parse ({exc})")
                continue
            bad.extend(f"{cid}: {why}" for why in _case_problems(doc, cid, bars))
        for orphan in sorted(on_disk - named):
            bad.append(f"orphan file not in the catalogue: {orphan}")
        for line in bad:
            print(f"  BAD  {line}")
        print(f"{len(entries)} entries, {len(bad)} problems")
        return 1 if bad else 0

    rows = [{"case_id": e["case_id"], "bar": e["bar"], "device": e["device"],
             "task_kind": e["task_kind"], "name": e["name"]} for e in entries]
    if args.as_json:
        print(json.dumps({"dir": str(d), "cases": rows},
                         ensure_ascii=False, indent=1))
    else:
        print(f"{d}  ({len(rows)} cases)")
        for r in rows:
            dev = f"  [{r['device']}]" if r.get("device") else ""
            print(f"  {r['case_id']:<28} {r['bar'] or '?':<10}{dev}  {r['name']}")
    return 0


#: ★★K-5 (`FYL-REPORT-06`): the plan face carries fyo / spo vocabulary ONLY.  A
#: private prefix anywhere in a corpus document — a key, a type, a value — is a
#: problem `--check` reports, so the namespace cannot creep back one field at a time.
_RETIRED_PREFIXES = ("fylite:", "vv:")


def _case_problems(doc, cid: str, bars: set) -> list:
    """What is structurally wrong with one case document (empty = sound)."""
    from ..scenario import cases as _cases
    out = []
    if doc.get("type") != "fyo:ScenarioSpecification":
        out.append(f"type is {doc.get('type')!r}, not fyo:ScenarioSpecification")
    if str(doc.get("id", "")).rsplit("/", 1)[-1] != cid:
        out.append(f"document id {doc.get('id')!r} does not name the catalogue entry")
    bar = _cases.bar_of(doc)
    if bar not in bars:
        out.append(f"prescribes_code names bar {bar!r}, which neither the tool "
                   "register nor the browser-only register knows")
    if not doc.get("prescribed_task_kind"):
        out.append("no prescribed_task_kind")
    if not _cases._lang(doc.get("title")):
        out.append("no title")
    params = doc.get("parameters")
    if not params:
        out.append("no parameter settings")
    for p in params or []:
        ref = str(p.get("sets_parameter", ""))
        if not ref.startswith(f"code/{bar}#") or "literal_value" not in p:
            out.append(f"parameter setting {ref!r} is not `code/{bar}#<name>` "
                       "with a literal_value")
            break

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith(_RETIRED_PREFIXES):
                    yield k
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        elif isinstance(x, str) and any(t in x for t in _RETIRED_PREFIXES):
            yield x[:60]
    hits = list(walk(doc))
    if hits:
        out.append(f"retired vocabulary present ({len(hits)}): {hits[0]!r}")
    return out


def _cli_manifest(args, parser) -> int:
    if args.seal:
        for name, changed in seal_manifests(write=True).items():
            print(f"{name:<26} {'RESEALED' if changed else 'sealed'}")
        return 0
    if args.out:
        for p in write_manifests(args.out):
            print(p)
        return 0
    failures = 0
    for name, doc in load_manifests().items():
        problems = validate_structure(doc)
        if seal_manifest(doc) != doc:
            problems.append("derived hashes stale — run "
                            "`fylite manifest --seal`")
        try:
            validate_projection(doc)
            schema_note = "schema ok"
        except RuntimeError:
            schema_note = "schema skipped (no jsonschema)"
        except Exception as e:  # jsonschema.ValidationError
            problems.append(f"projection: {e}")
            schema_note = "schema FAILED"
        state = "ok" if not problems else "FAILED"
        print(f"{name:<26} {state}  ({schema_note})")
        for p in problems:
            print(f"  - {p}")
        failures += bool(problems)
    return 1 if failures else 0


def _cli_plot(args, parser) -> int:
    from ..plot import plot_gfile
    out = args.out or (args.gfile + ".png")
    print(plot_gfile(args.gfile, out))
    return 0


def _cli_run(args, parser) -> int:
    #: ★One reconstruction, through the SAME door the MCP tool uses
    #: (FR-TOOL-003: the tool face may not introduce a second execution
    #: path — and two faces resolving the input modes independently is
    #: exactly how one appears; both used to, and both were broken).
    from . import handles
    from .serve import deliver_gfile, deliver_result, run_reconstruction

    if args.input and args.time is None:
        parser.error("--input needs --time [s]: a measurement document is "
                     "time-resolved")
    if not args.input and (args.shot is None or args.time is None):
        parser.error("reading from MDSplus needs --shot and --time [s]")
    if (args.point or args.pressure or args.thomson_ne) and not args.east:
        parser.error("--point/--pressure/--thomson-ne require --east "
                     "(they are read from the EAST MDSplus trees)")
    try:
        opts = {
            "input": args.input, "east": args.east,
            "shot": args.shot, "time_s": args.time, "server": args.server,
            "point": args.point or None, "point_sig": args.point_sig,
            "point_window_ms": args.point_window_ms,
            "point_fringe_gate": args.point_fringe_gate,
            "pressure": args.pressure or None,
            "pressure_sig": args.pressure_sig,
            "te_ceiling": args.te_ceiling,
            "thomson_ne": args.thomson_ne or None,
            "probes": False if args.no_probes else None,
        }
        res = run_reconstruction(opts)
        #: ★``--out`` used to default to ``.``, so every run scattered a
        #: g-file (and a PNG) into whatever directory the caller happened to
        #: be in, and a second run of the same slice fought the first for the
        #: name.  Unset, the delivery now goes to a fresh run directory under
        #: ``$FYLITE_RUN_DIR``; the arrays are stored beside it, so the
        #: printed handles resolve afterwards.
        run = handles.new_run()
        res["gfile"] = deliver_gfile(res, args.out or run)
        #: ★the same recorded delivery the tool face makes: arrays stored,
        #: summaries carrying handles, and — FR-DATA-003 — a run manifest
        #: with the code revision, the environment fingerprint, the digested
        #: inputs, the hashed artifacts and the four-state verdict.
        payload = deliver_result(res, run=run, call={
            "tool": "fylite run", "arguments": opts, "artifact": "efit",
            "entry": "fylite.engine.serve:run_reconstruction"})
        res["run"], res["run_dir"] = payload["run"], payload["run_dir"]
    except Exception as e:
        print(f"fylite: FAILED: {e}", file=sys.stderr)
        return 1

    if args.plot:
        from ..plot import plot_gfile
        target = (res["gfile"] + ".png") if args.plot is True else args.plot
        res["plot"] = plot_gfile(res["gfile"], target)

    if args.as_json:
        #: ★shaped, not dumped: the result carries the 65x65 psi map and
        #: seven 1-D profiles, and `json.dumps(default=str)` turned each of
        #: them into a truncated numpy repr — a string that looks like data
        #: and cannot be read back.  `summarize` is the same shaping the tool
        #: face uses: scalars and paths pass, arrays become typed summaries
        #: (shape / dtype / range / sha256) that point at the g-file.
        print(json.dumps(payload, indent=1, default=str))
    else:
        print(f"run    : {res['run_dir']}")
        print(f"g-file : {res['gfile']}")
        print(f"device : {res['device']}")
        print(f"fit    : iterations={res['iterations']} "
              f"residual={res['residual']:.3e}")
        print(f"psi    : axis={res['psi_axis']:+.6f} bry={res['psi_bry']:+.6f}"
              f" [Wb/rad]")
        print(f"Ip     : {res['ip']:.4e} A   Btor(Rc)={res['bcentr']:+.3f} T")
        print(f"axis   : R={res['rmaxis']:.4f} Z={res['zmaxis']:+.4f} m")
        print(f"q      : q0={res['q0']:.3f} q95={res['q95']:.3f}")
        if "plot" in res:
            print(f"plot   : {res['plot']}")
    return 0
