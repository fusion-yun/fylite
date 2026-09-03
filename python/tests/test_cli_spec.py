"""The declarative CLI (engine generic builder + ``_cli.json`` spec).

Pins the convergence contract: the parser is built mechanically from the spec
file, every command's handler entry resolves to a real callable, semantics
ported from the old cli.py survive (mutually-exclusive source group, dest
remapping, defaults), and ``python -m fylite`` serves the same entry point.
"""
from __future__ import annotations

import json
import subprocess
import sys
import pathlib

import pytest

from fylite import engine

REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = engine.load_cli_spec()


def test_spec_lists_all_commands():
    #: ★`cache` is NOT in this list any more: it managed a Green-table
    #: cache that a removed generator filled, and two of the three names its
    #: handler called (`greens.list_entries`, `greens.clear`) had already
    #: stopped existing — the subcommand could only raise.
    #: ★`replay` joined on 2026-08-25: the executor for a recorded session
    #: (`engine/replay.py`), sitting beside `manifest` because both face the
    #: RECORD rather than the physics.
    #: ★`cases` joined on 2026-08-26, beside `describe` because both face
    #: the DECLARED (catalog / corpus), not the physics: the CLI is the
    #: primary debugging environment, and the scenario corpus (top-level
    #: `cases/`, fyo JSON-LD) has to be reachable from it.
    #: ★`report` joined on 2026-08-26, beside `replay` because both consume
    #: the record: the unified MyST run report (engine/report.py) is a
    #: projection of a run directory, and the CLI is where it is generated.
    #: ★`whence` joined on 2026-08-26 (A-4), beside `report` because it too
    #: faces the record — and it faces it BACKWARDS: every other command goes
    #: from a request to an artefact, this one goes from an artefact to the
    #: run that made it.  The lookup is by content hash, not by path, so a
    #: copied or renamed file still resolves.
    #: ★`alias` joined on 2026-08-26 (A-5), beside `whence` because the two
    #: are the same need from opposite ends: `whence` takes an artefact and
    #: gives back the run, `alias` gives a run a name a person can hold in
    #: their head.  Neither replaces the id.
    #: ★`app` / `data` / `case` joined on 2026-09-02 (FYL-DESIGN-15): the
    #: three commands the single Rust executable carries natively.  The
    #: Python host lists them too — same spec, same help — and DELEGATES
    #: them to the bundled binaries; a host that does not carry a command
    #: says so by name rather than by an argparse error.
    assert [c["name"] for c in SPEC["commands"]] == [
        "run", "plot", "describe", "cases", "manifest", "replay", "report",
        "whence", "alias", "serve", "mcp", "app", "data", "case"]


def test_every_handler_resolves():
    for cmd in SPEC["commands"]:
        assert callable(engine.resolve_entry(cmd["handler"])), cmd["name"]


def test_parser_builds_and_parses():
    ap = engine.build_cli(SPEC)
    args = ap.parse_args(["describe", "--text"])
    assert args.cmd == "describe" and args.text is True
    args = ap.parse_args(["run", "--east", "--shot", "70754",
                          "--time", "3.5", "--json"])
    assert args.east and args.shot == 70754 and args.time == 3.5
    assert args.as_json is True            # dest remapping survives
    assert args.point_fringe_gate == 0.15  # spec default survives


def test_source_modes_stay_mutually_exclusive():
    ap = engine.build_cli(SPEC)
    with pytest.raises(SystemExit):
        ap.parse_args(["run", "--east", "--input", "x.json"])


def test_point_sig_takes_two_floats():
    ap = engine.build_cli(SPEC)
    args = ap.parse_args(["run", "--east", "--shot", "1", "--time", "1",
                          "--point", "--point-sig", "0.1", "0.2"])
    assert args.point_sig == [0.1, 0.2]


def test_module_entry_point_round_trip():
    proc = subprocess.run(
        [sys.executable, "-m", "fylite", "describe"],
        capture_output=True, text=True, timeout=120,
        env={"PYTHONPATH": "python", "PATH": "/usr/bin:/bin"},
        cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    cat = json.loads(proc.stdout)
    assert cat["@id"] == "fylite:catalog"


def test_manifest_check_via_cli_spec():
    proc = subprocess.run(
        [sys.executable, "-m", "fylite", "manifest"],
        capture_output=True, text=True, timeout=120,
        env={"PYTHONPATH": "python", "PATH": "/usr/bin:/bin"},
        cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert "FAILED" not in proc.stdout


# --------------------------------------------------------------------------- #
# The agent skill is a THIRD reader of this spec
# --------------------------------------------------------------------------- #

#: ★★`.claude/skills/fylite/SKILL.md` tells an LLM host what this package can
#: be asked to do, and it named `fylite cache` — a subcommand retired with the
#: Green-table generator that filled it (see the note on
#: `test_spec_lists_all_commands`).  A human reading a stale line loses a
#: minute; a model reading one runs the command, gets an argparse error, and
#: reports the capability as broken.  The skill is not documentation about the
#: CLI, it is an INPUT to one of its callers, so it is gated like the spec.
SKILL = REPO / ".claude" / "skills" / "fylite" / "SKILL.md"

#: `` `fylite <a>/<b>` `` inside backticks — the form the skill uses to name
#: subcommands.  The space is what separates a subcommand from a module path
#: (`fylite.machine`) and from an MCP tool name (`fylite_describe`).
_SKILL_CMD = __import__("re").compile(r"`fylite ([a-z][a-z0-9/_-]*)")


def test_the_skill_only_names_real_subcommands():
    if not SKILL.is_file():                     # skill not in this checkout
        pytest.skip(f"no {SKILL.relative_to(REPO)}")
    known = {c["name"] for c in SPEC["commands"]}
    named = {tok for m in _SKILL_CMD.findall(SKILL.read_text())
             for tok in m.split("/") if tok}
    unknown = sorted(named - known)
    assert not unknown, (
        f"{SKILL.relative_to(REPO)} names subcommands this CLI does not have: "
        f"{unknown}\nKnown: {sorted(known)}")


# --------------------------------------------------------------------------- #
# the scenario corpus, reached from the CLI
# --------------------------------------------------------------------------- #
#
# ★★2026-08-26：算例语料从 `app/cases/` 提升到仓顶层 `cases/`，同批裁定
# **CLI 为主要调试环境**。★★2026-09-01 再搬一次，到 `cases/`：同批
# 裁定**页面不再取算例**，于是 CLI 与 Python 侧是语料仅有的读者，语料本身
# 归到它一直所属的那一类——文档数据。这几条闸子钉住三件事：语料在 CLI
# 够得到、目录与盘上文件互指成立（catalogue 名的都在、盘上的都被名了）、
# 以及找不到语料时**拒绝而不是回空**——空清单会被读成「没有算例」，那是
# 另一个事实。
from pathlib import Path as _Path

CORPUS_ROOT = _Path(__file__).resolve().parents[2]


def _cases(args):
    import io
    from contextlib import redirect_stdout

    from fylite.engine import cli as m

    class _A:
        name = None
        dir = None
        check = False
        as_json = False

    a = _A()
    for k, v in args.items():
        setattr(a, k, v)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = m._cli_cases(a, None)
    return rc, buf.getvalue()


def test_the_corpus_is_reachable_and_structurally_sound():
    rc, out = _cases({"check": True})
    assert rc == 0, out
    assert "0 problems" in out


def test_listing_names_every_catalogue_entry():
    import json as _json

    rc, out = _cases({"as_json": True})
    assert rc == 0
    got = _json.loads(out)
    cat = _json.loads((CORPUS_ROOT / "cases/catalogue.jsonld").read_text())
    #: the catalogue is an ICE whose ordered `has_part` names the plans by IRI
    #: (`cases/<case_id>`); the listing is those, in that order
    assert ([r["case_id"] for r in got["cases"]]
            == [m["id"].rsplit("/", 1)[-1] for m in cat["has_part"]])
    #: and every one prescribes a bar the registers know — the listing would
    #: otherwise print `?`, which is the sign a document lost its code
    assert all(r["bar"] for r in got["cases"]), got
    #: every case document carries a human-readable name — the corpus is a
    #: menu as well as a debug fixture, and a nameless row is unusable in
    #: one of its two jobs
    assert all(r["name"] for r in got["cases"]), got


def test_showing_one_case_prints_the_document_verbatim():
    rc, out = _cases({"name": "evolve-default"})
    assert rc == 0
    assert out.strip() == (CORPUS_ROOT / "cases/evolve-default.jsonld"
                           ).read_text().strip()


def test_a_missing_corpus_is_refused_not_empty(tmp_path):
    """★an empty listing reads as「there are no cases」— a different fact
    from「the corpus is not here」, and only one of them is true off a
    wheel install."""
    import pytest as _pytest

    from fylite.engine import cli as m
    with _pytest.raises(SystemExit, match="does not ship"):
        m._cases_dir(str(tmp_path / "nowhere"))


# --------------------------------------------------------------------------- #
# One file, three hosts (FYL-DESIGN-15)
# --------------------------------------------------------------------------- #
#
# ★The spec is shared with the Rust executable (`rust/fylite_engine/src/cli/
# mod.rs` includes it at compile time) and with the browser (its launch
# parameters are `hosts.app.params`).  These gates pin what the sharing
# means: the Rust side really includes THIS file, the browser really reads
# exactly the declared names, and a host-specific option stays with its host.

APP_ASSETS = REPO / "app" / "assets"
RUST_CLI = REPO / "rust" / "fylite_engine" / "src" / "cli" / "mod.rs"
_URL_READER = __import__("re").compile(
    r"URLSearchParams\((?:root|window)\.location\.search\)\.get\('([a-z_]+)'\)")


def test_the_spec_names_three_hosts_and_is_version_two():
    assert SPEC["spec_version"] == 2
    assert set(SPEC["hosts"]) == {"python", "rust", "app"}
    assert SPEC["hosts"]["rust"]["default_command"] == "app"
    for c in SPEC["commands"]:
        assert "python" in c["hosts"], c["name"]
    assert {c["name"] for c in SPEC["commands"] if "rust" in c["hosts"]} == {
        "app", "data", "case"}


def test_the_rust_host_includes_this_very_file():
    if not RUST_CLI.is_file():
        pytest.skip("no rust/fylite_engine checkout")
    m = __import__("re").search(r'include_str!\("([^"]+)"\)', RUST_CLI.read_text())
    assert m, "the Rust cli does not include_str! the spec"
    assert (RUST_CLI.parent / m.group(1)).resolve() == engine.CLI_SPEC_PATH.resolve()


def test_nested_commands_parse_and_record_their_path():
    ap = engine.build_cli(SPEC)
    args = ap.parse_args(["data", "convert", "in.json", "out.h5", "--to", "hdf5"])
    assert engine.cli.command_path(args) == ["data", "convert"]
    assert args.input == "in.json" and args.to == "hdf5"
    #: a group's option is accepted before AND after the subcommand (C-5)
    a = ap.parse_args(["data", "--bin-dir", "/x", "tables"])
    b = ap.parse_args(["data", "tables", "--bin-dir", "/x"])
    assert a.bin_dir == b.bin_dir == "/x"
    args = ap.parse_args(["case", "run", "p.jsonld", "--set", "a=1", "--set", "b=2",
                          "-o", "rec"])
    assert args.set == ["a=1", "b=2"] and args.record == "rec"
    with pytest.raises(SystemExit):
        ap.parse_args(["data", "merge", "a.json"])          # -o is required


def test_a_python_only_option_is_marked_and_a_rust_only_one_is_not_built():
    app = next(c for c in SPEC["commands"] if c["name"] == "app")
    by_flag = {a["flags"][0]: a for a in app["args"]}
    assert by_flag["--bin-dir"]["hosts"] == ["python"]
    assert by_flag["--app-dir"]["hosts"] == ["rust"]
    ap = engine.build_cli(SPEC)
    assert ap.parse_args(["app", "--bin-dir", "/x", "--no-open"]).bin_dir == "/x"
    with pytest.raises(SystemExit):
        ap.parse_args(["app", "--app-dir", "/x"])


def test_the_browser_reads_exactly_the_declared_launch_parameters():
    declared = {p["name"]: p for p in SPEC["hosts"]["app"]["params"]}
    query = {n for n, p in declared.items() if p["carrier"] == "query"}
    read = set()
    for js in sorted(APP_ASSETS.glob("*.js")):
        read |= set(_URL_READER.findall(js.read_text()))
    assert read == query, (
        f"pages read {sorted(read)} from the URL, the spec declares "
        f"{sorted(query)} — change the spec and the reader together")
    #: every launch parameter has its `fylite app --<name>` option, and no
    #: option names an undeclared parameter (C-6)
    app = next(c for c in SPEC["commands"] if c["name"] == "app")
    bound = {a["app_param"]: a for a in app["args"] if "app_param" in a}
    assert set(bound) == set(declared)
    for name, arg in bound.items():
        assert arg["flags"] == [f"--{name}"]
        assert arg.get("choices") == declared[name].get("choices")
