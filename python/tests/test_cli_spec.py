"""``_cli.json`` — the command-line spec, now shared by TWO hosts.

★★2026-09-04 用户裁定：**Python 侧没有命令行层**。`engine/cli.py`（`_cli.json` 上的
argparse 建造者、`cli_main`、以及把 `app` / `data` / `case` 委派给原生可执行文件的那
一段）、`__main__.py`、控制台脚本 `fylite` 一并撤除，本包从此是**库**。

于是这一份闸子的题目也变了。原来它钉的是「一份规格，三个建造者」——那时大半条目
问的是 Python 那个 argparse 建得对不对（互斥组、dest 重映射、缺省值、`python -m
fylite` 与控制台脚本同一入口），以及经 CLI 处理器读算例语料。**那些主体没有了**，
条目跟着走，不留下问一个不存在的东西的闸子。

留下的是仍然成立的那一半，也是这份文件今天的全部意义：规格被**两个**宿主读——
Rust 可执行文件 `fy`（编译期 `include_str!`）与浏览器页面（`hosts.app.params` 就是
它的启动参数）——而这两者之间没有第三处需要同步的东西。
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / "python" / "fylite" / "_cli.json"
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

APP_ASSETS = REPO / "app" / "assets"
RUST_CLI = REPO / "rust" / "fylite_runtime" / "src" / "cli" / "mod.rs"
_URL_READER = re.compile(
    r"URLSearchParams\((?:root|window)\.location\.search\)\.get\('([a-z_]+)'\)")


def test_the_spec_names_two_hosts_and_is_version_two():
    assert SPEC["spec_version"] == 2
    #: ★`python` left this set with the layer that read it.
    assert set(SPEC["hosts"]) == {"rust", "app"}
    assert SPEC["hosts"]["rust"]["default_command"] == "app"
    #: the program name in every usage line comes from here (`main.rs` hands
    #: `spec.prog` to the parser), so a rename lands in one place
    assert SPEC["prog"] == SPEC["hosts"]["rust"]["exe"] == "fy"
    #: every command left in the file is carried by the executable — a command
    #: nothing carries is a line of documentation for a program that has none
    for c in SPEC["commands"]:
        assert c["hosts"] == ["rust"], c["name"]
    #: ★★2026-09-04 第二条裁定（FYL-DESIGN-17 E-10）：`case` 收进 `run`，发现面收进
    #: `list`。四条命令词各是一个动词——起页面 · 搬数据 · 算 · 看。
    assert {c["name"] for c in SPEC["commands"]} == {"app", "data", "run", "list"}
    #: and no argument may be marked for a host that no longer exists
    def hosts_of(node):
        if isinstance(node, dict):
            if isinstance(node.get("hosts"), list):
                assert "python" not in node["hosts"], node
            for v in node.values():
                hosts_of(v)
        elif isinstance(node, list):
            for v in node:
                hosts_of(v)
    hosts_of(SPEC["commands"])


def test_the_rust_host_includes_this_very_file():
    """The one host that builds a parser from the spec must include THIS file.

    ★This is what keeps the spec a single source: the executable's parser is
    generated at compile time from the bytes in this repository, so a change
    here cannot reach the user as a stale parser.
    """
    if not RUST_CLI.is_file():
        pytest.skip("no rust/fylite_runtime checkout")
    m = re.search(r'include_str!\("([^"]+)"\)', RUST_CLI.read_text())
    assert m, "the Rust cli does not include_str! the spec"
    assert (RUST_CLI.parent / m.group(1)).resolve() == SPEC_PATH.resolve()


def test_the_browser_reads_exactly_the_declared_launch_parameters():
    declared = {p["name"]: p for p in SPEC["hosts"]["app"]["params"]}
    query = {n for n, p in declared.items() if p["carrier"] == "query"}
    read = set()
    for js in sorted(APP_ASSETS.glob("*.js")):
        read |= set(_URL_READER.findall(js.read_text()))
    assert read == query, (
        f"pages read {sorted(read)} from the URL, the spec declares "
        f"{sorted(query)} — change the spec and the reader together")
    #: every launch parameter has its `fy app --<name>` option, and no option
    #: names an undeclared parameter (FYL-DESIGN-15 C-6)
    app = next(c for c in SPEC["commands"] if c["name"] == "app")
    bound = {a["app_param"]: a for a in app["args"] if "app_param" in a}
    assert set(bound) == set(declared)
    for name, arg in bound.items():
        assert arg["flags"] == [f"--{name}"]
        assert arg.get("choices") == declared[name].get("choices")


def _command(name):
    return next(c for c in SPEC["commands"] if c["name"] == name)


def _flags(cmd):
    """{long flag: the argument declaration} for one command."""
    out = {}
    for a in cmd.get("args", []):
        for f in a["flags"]:
            if f.startswith("--"):
                out[f] = a
    return out


def test_a_retired_word_says_where_it_went():
    """`retired` is the data behind the parser's refusal (E-23).

    ★It is a table rather than a branch for the usual reason: the words that
    left are the ones a reader still has in a shell history and in already
    published documentation, and the useful reply names the replacement.  A
    replacement that does not start with a command this file still carries
    would send them somewhere else that does not exist.
    """
    retired = SPEC["retired"]
    live = {c["name"] for c in SPEC["commands"]}
    assert "case" in retired and "data facts" in retired
    for old, new in retired.items():
        assert new.split()[0] in live, f"{old!r} points at {new!r}, which is not a command"
        #: a retired word must not also be a live one — that is two words for
        #: one thing, which is what the fold removed
        assert old.split()[0] not in live or old.split()[0] == "data", old


def test_only_run_takes_a_parameter_table_of_its_own():
    """`open_parameters` is the seam between this file and the templates.

    The scenario parameters (279 names across nine codes) are NOT here: they
    belong to the scenario, and a scenario is data (E-11).  What is here is
    the declaration that the command has such a table, so the parser collects
    unknown tokens instead of refusing them — and only that one command does.
    """
    assert _command("run")["open_parameters"] == "scenario"
    for c in SPEC["commands"]:
        if c["name"] != "run":
            assert "open_parameters" not in c, c["name"]


def test_a_word_means_the_same_thing_on_every_command():
    """J-6, as a gate: `--device` / `--shot` / `--time` and the connection
    options are declared identically on `run` and on `data fetch`.

    ★`required` is deliberately excluded from the comparison: `data fetch`
    cannot run without a device and `run` can (a scenario may need none).
    What must not differ is what the word MEANS — its type, its choices, the
    way it takes a value.
    """
    run, fetch = _flags(_command("run")), _flags(_command("data")["commands"][5])
    assert _command("data")["commands"][5]["name"] == "fetch"
    shared = set(run) & set(fetch)
    assert {"--device", "--shot", "--time", "--mds-user", "--timeout-ms"} <= shared
    for f in sorted(shared):
        for key in ("type", "action", "choices"):
            assert run[f].get(key) == fetch[f].get(key), f"{f} differs in {key}"


def test_the_discovery_face_is_one_command_with_one_subcommand_per_corpus():
    """E-24: `list` answers "what is available", and nothing else does."""
    lst = _command("list")
    assert {c["name"] for c in lst["commands"]} == {
        "devices", "experiments", "scenarios", "presets", "facts", "kernel", "lines"}
    #: `data` no longer answers it (its `facts` subcommand moved here)
    assert "facts" not in {c["name"] for c in _command("data")["commands"]}
    #: and `run` grew no --list / --show of its own
    assert "--list" not in _flags(_command("run"))
    assert "--show" not in _flags(_command("run"))
