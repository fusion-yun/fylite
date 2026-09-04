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

#: The host THIS builder speaks for.  The spec is shared by three hosts
#: (`hosts` in the file: python / rust / app); a command or an argument may
#: name the hosts that carry it, and this builder only builds what names
#: `python` (or names nothing — the pre-`hosts` spelling, python-only).
HOST = "python"

#: Spec keys that describe an argument for the OTHER hosts and are not
#: argparse keywords: `hosts` (which host carries it), `app_param` (the
#: browser launch parameter a `fylite app` option writes into the URL).
_NOT_ARGPARSE = ("flags", "hosts", "app_param")


def load_cli_spec() -> dict:
    """Load the declarative CLI spec (commands / options / handlers)."""
    return json.loads(CLI_SPEC_PATH.read_text())


def carried_by(node: dict, host: str = HOST) -> bool:
    """Whether a command / argument entry names `host` (or names no host)."""
    hosts = node.get("hosts")
    return hosts is None or host in hosts


def _add_arguments(parser, cmd: dict, inherited: bool = False) -> None:
    import argparse
    owner = {}
    for group in cmd.get("exclusive", ()):
        g = parser.add_mutually_exclusive_group()
        for flag in group:
            owner[flag] = g
    for arg in cmd.get("args", ()):
        if not carried_by(arg):
            continue
        kw = {k: v for k, v in arg.items() if k not in _NOT_ARGPARSE}
        if "type" in kw:
            kw["type"] = _CLI_TYPES[kw["type"]]
        if isinstance(kw.get("metavar"), list):
            kw["metavar"] = tuple(kw["metavar"])
        if inherited:
            #: ★a group option re-declared on a child: without SUPPRESS the
            #: child's default would overwrite what the parent already
            #: parsed (`data --bin-dir D tables` would lose D) — argparse
            #: applies a subparser's defaults after the parent's values
            kw["default"] = argparse.SUPPRESS
            kw.pop("required", None)
        target = owner.get(arg["flags"][0], parser)
        target.add_argument(*arg["flags"], **kw)


def _add_command(sub, cmd: dict, depth: int, inherited=()) -> None:
    p = sub.add_parser(cmd["name"], help=cmd["help"],
                       description=cmd.get("description", cmd["help"]))
    #: ★a group's own options (`fylite data --bin-dir D …`) apply to every
    #: subcommand under it, and a reader types them where they think of
    #: them — usually AFTER the subcommand.  argparse only knows an option
    #: on the parser that declared it, so the group's options are declared
    #: on each child as well; the Rust parser applies an ancestor's options
    #: anywhere on the line, and this is the same rule spelled for argparse.
    for parent in inherited:
        _add_arguments(p, {"args": parent.get("args", ())}, inherited=True)
    _add_arguments(p, cmd)
    #: ★a command with `commands` is a GROUP (`fylite data convert …`): its
    #: own args are the group's, the children are one nesting level down.
    #: The child's name lands in `cmd<depth>` so a handler can read the path.
    if cmd.get("commands"):
        child = p.add_subparsers(dest=f"cmd{depth}", required=True)
        for c in cmd["commands"]:
            if carried_by(c):
                _add_command(child, c, depth + 1, (*inherited, cmd))


def build_cli(spec: dict):
    """Build the argparse parser from a CLI spec — purely mechanical."""
    import argparse
    ap = argparse.ArgumentParser(prog=spec["prog"],
                                 description=spec["description"])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in spec["commands"]:
        if carried_by(cmd):
            _add_command(sub, cmd, 1)
    return ap


def command_path(args) -> list:
    """The command words a parse produced: ``['data', 'convert']``."""
    path = [args.cmd]
    i = 1
    while hasattr(args, f"cmd{i}"):
        path.append(getattr(args, f"cmd{i}"))
        i += 1
    return path


def _library_refusals():
    """库抛上来的两种「说得清的拒绝」，惰性取——`engine` 在 import 期保持 stdlib 纯。

    `CorpusMissing`（语料 / 装置牌不在场）与 `RunFailed`（跑了但没跑成）都是**普通
    异常**：退出码是 CLI 的关切，翻译落在这里；库调用者（含 pytest 的 fixture）
    接得住它们。
    """
    from .cases import CorpusMissing, RunFailed
    return (CorpusMissing, RunFailed)


def cli_main(argv=None) -> int:
    """The ``fylite`` console entry point: spec -> parser -> handler."""
    spec = load_cli_spec()
    ap = build_cli(spec)
    argv = list(sys.argv[1:] if argv is None else argv)
    args = ap.parse_args(argv)
    #: the words as typed, for the handlers that hand a command on to
    #: another host verbatim (`app` / `data` / `case` -> the Rust executable)
    args._argv = argv
    handlers = {c["name"]: c["handler"] for c in spec["commands"]
                if carried_by(c)}
    try:
        return resolve_entry(handlers[args.cmd])(args, ap)
    except _library_refusals() as exc:
        #: ★★2026-09-01：语料缺席从库里抛上来的是 `engine.cases.CorpusMissing`，
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


# ---- the commands the Rust host carries natively ---------------------------- #
#
# `app` / `data` / `case` are in the spec for every host, so `fylite app
# --help` and `fylite --help` read the same words.  The Python host does
# not reimplement them: it finds the bundled executable and hands the words
# on verbatim (FYL-DESIGN-15 C-3).  What is stripped is the one Python-only
# option, `--bin-dir` — the spec marks it `hosts: ["python"]`, and the Rust
# parser would refuse it by name.
#
# ★★2026-09-03 ONE executable (user ruling).  There used to be three, and the
# lookup here was a LIST per command: try the alias binary `fylite-data`, then
# fall back to `fylite` with the word put back in front.  The alias
# binaries were ten lines each and did exactly that prepending themselves —
# so the fallback was the whole implementation and the alias was the
# redundant half.  Now the word is always put back in front, by the one
# caller that ever needed to.

#: the one executable, and the command word it is handed in front
_RUST_EXE = "fylite"


def _is_this_python_host(path) -> bool:
    """Is `path` the console script THIS package installs?

    ★★2026-09-04 起 Rust 可执行文件与 Python 控制台脚本**同名**（都叫 `fylite`，
    用户裁定）。同名之后 `$PATH` 那一步就有了一个新的失败方式，而且是最坏的一种：
    `shutil.which("fylite")` 会找到**我们自己**，于是 `fylite data …` 委托给
    `fylite data …`，一层层 fork 到进程表满——没有报错，只有机器变慢。

    两者好分：控制台脚本是一个 `#!` 文本脚本，而且它导入的正是本模块所在的包。
    原生可执行文件是 ELF / PE / Mach-O，头两个字节就说了。所以判据是**读文件**，
    不是猜路径。
    """
    try:
        with open(path, "rb") as f:
            head = f.read(2)
            if head != b"#!":
                return False          #: 二进制 —— 那就是我们要的那个
            f.seek(0)
            return b"fylite.engine" in f.read(4096)
    except OSError:
        return False


def _find_exe(name: str, bin_dir=None):
    """Where a bundled executable is: --bin-dir, the package's _bin/, $PATH.

    ★`$PATH` 那一步会跳过本包自己的控制台脚本（见 `_is_this_python_host`）。
    """
    import shutil
    from pathlib import Path
    for d in ([Path(bin_dir)] if bin_dir else []) + [_paths.PKG / "_bin"]:
        for cand in (d / name, d / (name + ".exe")):
            if cand.is_file():
                return str(cand)
    found = shutil.which(name)
    #: ★同名之后这一步必须挑一次：找到的若是我们自己，那不是「找到了」。
    return None if (found and _is_this_python_host(found)) else found


def _apply_facts(args) -> None:
    """`--facts` -> the process-wide search path, before anything reads it.

    ★Several `--facts` accumulate (the option is `append`), and each may itself
    be a `os.pathsep` list — the two spellings mean the same thing and both are
    accepted, because a reader who knows `$PATH` will try the separator and a
    reader who knows argparse will repeat the flag.
    """
    raw = getattr(args, "facts", None)
    if not raw:
        return
    import os as _os

    from .. import facts as _facts
    parts = []
    for item in raw:
        parts.extend(p for p in str(item).split(_os.pathsep) if p.strip())
    _facts.use(parts)
    bad = _facts.problems()
    if bad:
        #: 名字给了就该指到东西上：给错了当场说，而不是等到某个条目找不到时
        #: 才报「没有这台机器」——那句话会把「路径写错了」说成「语料里没有它」。
        for line in bad:
            print(f"fylite: {line}", file=sys.stderr)


def _strip_option(words: list, flag: str) -> list:
    """The words without `flag VALUE` / `flag=VALUE`."""
    out, skip = [], False
    for w in words:
        if skip:
            skip = False
            continue
        if w == flag:
            skip = True
            continue
        if w.startswith(flag + "="):
            continue
        out.append(w)
    return out


def _delegate(args, parser, command: str) -> int:
    import subprocess
    tail = _strip_option(list(getattr(args, "_argv", []))[1:], "--bin-dir")
    #: ★★`--facts` is NOT stripped: both hosts carry it now (the resolver lives in
    #: the middle layer, `fylite_runtime::facts`).  It is applied here as well so
    #: that anything this Python process reads before delegating resolves against
    #: the same path the executable will use — one flag, one meaning, two hosts.
    _apply_facts(args)
    path = _find_exe(_RUST_EXE, getattr(args, "bin_dir", None))
    if path:
        #: ★the command word is put back in front: `tail` is the line as typed
        #: MINUS argv[0]'s command word, and the executable's own parser wants
        #: it (its no-subcommand default is `app`, so an omitted word would
        #: silently start a web server instead of converting a file).
        return subprocess.call([path, command, *tail])
    print(f"fylite {command}: no {_RUST_EXE} executable found — this Python "
          f"host delegates `{command}` to the Rust executable, which is the "
          f"only one there is. Build it with `bash rust/build.sh --exe` "
          f"(into python/fylite/_bin/) or `bash tools/build-app-exe.sh linux`, "
          f"or point --bin-dir at a directory holding it.", file=sys.stderr)
    return 2


def _cli_app(args, parser) -> int:
    return _delegate(args, parser, "app")


def _cli_data(args, parser) -> int:
    return _delegate(args, parser, "data")


def _cli_case(args, parser) -> int:
    return _delegate(args, parser, "case")


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
    #: ★one resolver: `engine.cases` owns the corpus (S-2 gave it a second
    #: consumer, the mapping layer), and two spellings of "where is cases/"
    #: is how the CLI and the mapper would one day disagree about it.
    from . import cases as _cases
    return _cases.corpus_dir(explicit)


def _cli_cases(args, parser) -> int:
    """List / show / check the scenario corpus.

    ★Why the CLI grows this at all: the CLI is the PRIMARY DEBUGGING
    ENVIRONMENT (2026-08-26 裁定, with the corpus promotion), and the
    scenarios are fixed as fyo/JSON-LD session documents.  A corpus the
    primary environment cannot even list is browser-private data wearing a
    top-level directory's name.
    """
    #: ★2026-09-02 整合收敛：the SECOND corpus.  `--benchmark` reads the public V&V
    #: register (`benchmark/registry.jsonld`, fyo:ComparisonRecord) through the
    #: same verb — list / show / check / run — so a reader has one door to「what
    #: this code runs」and「what it was measured against」(scenario/benchmark.py).
    if getattr(args, "benchmark", False):
        return _cli_benchmark(args, parser)
    #: ★★2026-09-02 第三本册子：`--physics` 读物理校验批（`benchmark/physics/`）——
    #: 同一个动词，问的是另一个问题：不是「跑什么」（语料）也不是「对着外部答案
    #: 量到多少」（登记册），而是「这份产出满不满足定律、文档自己的定义与算例
    #: 声明的期望」（scenario/physics.py + scenario/suite.py）。
    if getattr(args, "physics", False):
        return _cli_physics(args, parser)
    #: ★the REPORT face of a case (2026-09-02, FYL-REPORT-06 §13): run it through the
    #: data layer's JSON door and render plan + record into MyST + SVG through a
    #: presentation spec — or render a record `fylite case run` already wrote (--from).
    if getattr(args, "report", False):
        from . import casereport
        src = getattr(args, "from_record", None)
        if not src and not args.name:
            parser.error("--report needs a case id (run it) or --from <record.jsonld | run dir>")
        if src:
            dest = casereport.render(src, out=args.out, presentation=getattr(args, "presentation", None),
                                     lang=getattr(args, "lang", "zh") or "zh")
        else:
            dest = casereport.run_and_render(args.name, args.dir, out=args.out,
                                             presentation=getattr(args, "presentation", None),
                                             lang=getattr(args, "lang", "zh") or "zh")
        print(dest)
        return 0
    d = _cases_dir(args.dir)
    from . import cases as _cases
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


def _cli_physics(args, parser) -> int:
    """List / show / check / run the physics-check suite (`fylite cases --physics`)."""
    from . import suite as _sc
    d = _sc.suite_dir(args.dir)
    doc = _sc.load_suite(d)
    parts = {str(p.get("id", "")).rsplit("/", 1)[-1]: p for p in doc.get("has_part") or []}
    if getattr(args, "run_case", False) or getattr(args, "plan", False):
        if not args.name:
            parser.error("--plan/--run need an entry id (see `fylite cases --physics`)")
        try:
            e = _sc.entry(args.name, d)
        except KeyError:
            print(f"no entry {args.name!r}; the suite has: " + ", ".join(parts))
            return 1
        if getattr(args, "plan", False):
            #: 跑之前先说：这条要读哪些量、判哪几条
            print(json.dumps({"entry": e["id"], "case": e["case"], "checks": e["checks"],
                              "options": e["options"], "products": e.get("products") or []},
                             ensure_ascii=False, indent=1))
            return 0
        row = _sc.run_entry(e, from_dir=getattr(args, "from_record", None),
                            corpus=getattr(args, "corpus", None),
                            kernel_lib=getattr(args, "kernel", None))
        if args.as_json:
            print(json.dumps({k: v for k, v in row.items() if k != "record"},
                             ensure_ascii=False, indent=1, default=str))
        else:
            print(_sc.render_report(row))
        #: 判据不过 → 非零码；「没有产出可判」不是不过，退 0 并已在报告里说明
        return 1 if row["summary"]["counts"][_sc.ph.FAIL] else 0
    if args.name:
        part = parts.get(args.name)
        if part is None:
            print(f"no entry {args.name!r}; the suite has: " + ", ".join(parts))
            return 1
        print(json.dumps(part, ensure_ascii=False, indent=1))
        return 0
    if args.check:
        bad = []
        for pid, part in parts.items():
            bad.extend(f"{pid}: {why}" for why in _sc.problems(part, d))
        for line in bad:
            print(f"  BAD  {line}")
        print(f"{len(parts)} entries, {len(bad)} problems")
        return 1 if bad else 0
    rows = _sc.entries(d)
    if args.as_json:
        print(json.dumps({"dir": str(d), "entries": rows}, ensure_ascii=False, indent=1))
    else:
        print(f"{d}  ({len(rows)} entries; check register: "
              f"{len(_sc.ph.CHECKS)} checks)")
        for r in rows:
            src = r["case"] or ("product " + ", ".join(r.get("products") or []))
            print(f"  {r['id']:<24} {len(r['checks']):>2} checks  "
                  f"{'+'.join(sorted(r['options'])) or '-':<28}  {src}")
    return 0


def _cli_benchmark(args, parser) -> int:
    """List / show / check / run the public V&V register (`fylite cases --benchmark`)."""
    from . import benchmark as _bm
    d = _bm.registry_dir(args.dir)
    if getattr(args, "run_case", False) or getattr(args, "plan", False):
        if not args.name:
            parser.error("--plan/--run need a record id (see `fylite cases --benchmark`)")
        rec = _bm.load(args.name, d)
        k = _bm.kernel_checkout(getattr(args, "kernel", None))
        plan = _bm.gate_plan(rec, k)
        if getattr(args, "plan", False):
            print(json.dumps({"record_id": args.name, "kernel": str(k) if k else None, **plan},
                             ensure_ascii=False, indent=1))
            return 0
        r = _bm.run(args.name, d, getattr(args, "kernel", None))
        print(f"{r['record_id']}  {r['summary']}")
        for c in r["commands"]:
            print(f"  ran: {c}")
        for why in r["plan"]["refused"]:
            print(f"  refused: {why}")
        return 0 if r["returncode"] == 0 else 1
    if args.name:
        try:
            rec = _bm.load(args.name, d)
        except KeyError:
            print(f"no record {args.name!r}; the register has: "
                  + ", ".join(_bm.short_id(r) for r in _bm.graph(d)))
            return 1
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0
    if args.check:
        bad = []
        for rec in _bm.graph(d):
            bad.extend(f"{_bm.short_id(rec)}: {why}" for why in _bm.problems(rec, d))
        for line in bad:
            print(f"  BAD  {line}")
        print(f"{len(_bm.graph(d))} records, {len(bad)} problems")
        return 1 if bad else 0
    rows = _bm.records(d)
    if args.as_json:
        print(json.dumps({"dir": str(d), "records": rows}, ensure_ascii=False, indent=1))
    else:
        print(f"{d}  ({len(rows)} records)")
        for r in rows:
            cls = ",".join(r["classes"]) or "-"
            print(f"  {r['record_id']:<6} {r['kind']:<13} {r['verdict']:<13} "
                  f"rerun={r['rerun'] or '-':<12} [{cls}]  {r['title']}")
    return 0


#: ★★K-5 (`FYL-REPORT-06`): the plan face carries fyo / spo vocabulary ONLY.  A
#: private prefix anywhere in a corpus document — a key, a type, a value — is a
#: problem `--check` reports, so the namespace cannot creep back one field at a time.
_RETIRED_PREFIXES = ("fylite:", "vv:")


def _case_problems(doc, cid: str, bars: set) -> list:
    """What is structurally wrong with one case document (empty = sound)."""
    from . import cases as _cases
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
