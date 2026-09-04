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
    assert {c["name"] for c in SPEC["commands"]} == {"app", "data", "case"}
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
