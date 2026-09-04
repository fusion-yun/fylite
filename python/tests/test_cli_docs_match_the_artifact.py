"""文档里的命令行，必须是**产物真有的**那一个。

★★2026-09-04：这条闸子起因于一次实测。同一天里可执行文件改了名（`fylite-app` →
`fylite` → `fy`）、Python 侧的命令行整层撤除、数据层又多了一条 `facts` 子命令——三件
事各自都改了文档，而**文档仍旧说「七条子命令」、仍旧写 `fylite data …`**。散文没有
编译器，所以它只会在读者按着做、命令报「unknown option」的时候才报错。

这里问的是一句话：**指南与参考里写出来的每一条命令、每一个选项，`fy --help` 认不认。**
反方向（产物有而文档没写）不判——那是编辑取舍，不是错误。

没有构建产物就跳过（源码检出里没有它是常态，`bash rust/build.sh --exe` 之后才有）。
"""
from __future__ import annotations

import re
import subprocess

import pytest

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = json.loads((REPO / "python" / "fylite" / "_cli.json").read_text(encoding="utf-8"))

#: 撤掉的命令词与子命令（`_cli.json` 的 `retired`）。文档**应当**写它们——迁移表就是
#: 写给还在敲旧词的人看的——所以它们在这条闸子里是合法的出现，而不是错。
RETIRED = set(SPEC.get("retired", {}))

#: 场景参数不是选项：它们属于场景模板，而模板是数据（FYL-DESIGN-17 E-11）。一条
#: 声明了 `open_parameters` 的命令后面的 `--foo`，要么是它自己的固定选项，要么得是
#: **某份模板真有的**一个名字——两头都不是才是错。
OPEN_COMMANDS = {c["name"] for c in SPEC["commands"] if c.get("open_parameters")}


def _template_names() -> set[str]:
    out: set[str] = set()
    for f in (REPO / "docs" / "examples" / "scenario").glob("*.jsonld"):
        if f.stem == "lines":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        out |= set(doc.get("fylite:vocabulary", {}))
        out |= set(doc.get("fylite:switches", {}))
        out |= set(doc.get("fylite:common", []))
    return {n.replace("_", "-") for n in out} | {n.replace("-", "_") for n in out}
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"

#: 读者会照着敲的那些页；`_build/` 与设计集不在内（后者写的是裁定，不是用法）
PAGES = ["docs/guide/cli.md", "docs/guide/quickstart.md", "docs/guide/install.md",
         "docs/guide/browser-app.md", "docs/guide/browser.md",
         "docs/reference/cli.md", "docs/reference/data-layer.md",
         "docs/reference/case-report.md", "docs/examples/index.md", "README.md"]

#: ★★2026-09-04 第二条裁定（FYL-DESIGN-17 E-10 / E-24）：`case` 收进 `run`，发现面
#: 收进 `list`。旧词从这里去掉——留着它，一页写 `fy case run` 的文档会**通过**这条
#: 闸子（`case` 不再是命令，`(app|data|case)` 匹配到的东西在 surface 里查不到而被
#: 报为「no such subcommand」……只有在它带子命令时）。四个词与产物同一份名单。
_CMD = re.compile(r"\bfy (app|data|run|list)(?: ([a-z_]+))?((?:\s+--?[a-z][a-z0-9-]*|\s+\S+)*)")
_FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")


def _usage(*path: str) -> str:
    return subprocess.run([str(FY), *path, "--help"], capture_output=True,
                          text=True, timeout=60).stdout


def _subcommands(*path: str) -> set[str]:
    m = re.search(r"^commands:\n((?:  \S.*\n)+)", _usage(*path), re.M)
    return set(re.findall(r"^  ([a-z_]+)\s", m.group(1), re.M)) if m else set()


@pytest.fixture(scope="module")
def surface():
    if not FY.is_file():
        pytest.skip(f"no built executable ({FY.relative_to(REPO)}) — bash rust/build.sh --exe")
    out: dict[tuple[str, ...], set[str]] = {}
    for c in sorted(_subcommands()):
        group = set(_FLAG.findall(_usage(c))) | {"--help"}
        out[(c,)] = group
        for s in sorted(_subcommands(c)):
            out[(c, s)] = set(_FLAG.findall(_usage(c, s))) | group
    assert out, "the executable lists no commands"
    return out


def test_every_command_and_option_the_docs_show_exists(surface):
    bad = []
    for page in PAGES:
        p = REPO / page
        if not p.is_file():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CMD.finditer(line):
                cmd, sub, tail = m.group(1), m.group(2), m.group(3) or ""
                real = sorted(k[1] for k in surface if len(k) == 2 and k[0] == cmd)
                #: ★★a command with NO subcommands takes positionals instead
                #: (`fy run analysis`, `fy run plan.jsonld`), so the word after
                #: it is an argument and there is nothing to look up.  Checking
                #: it as a subcommand would report every documented invocation
                #: of `run` as wrong.
                if not real:
                    sub, tail = None, (f" {sub}" if sub else "") + tail
                key = (cmd, sub) if sub else (cmd,)
                if sub and key not in surface:
                    if f"{cmd} {sub}" in RETIRED:
                        continue          #: 迁移表里的旧词，写它是有意的
                    bad.append(f"{page}:{i}: `fy {cmd} {sub}` — no such subcommand (real: {real})")
                    continue
                for flag in _FLAG.findall(tail):
                    if flag in surface[key]:
                        continue
                    if cmd in OPEN_COMMANDS and flag.lstrip("-") in _template_names():
                        continue          #: 场景参数，由 test_scenario_templates.py 管
                    bad.append(f"{page}:{i}: `fy {cmd}{' ' + sub if sub else ''}` has no {flag}")
    assert not bad, "文档写的命令行与产物对不上：\n  " + "\n  ".join(bad)


def test_the_subcommand_count_the_prose_claims_is_the_real_one(surface):
    """★散文里的「N 条子命令」是最容易悄悄过期的一句：加一条子命令不会改它。"""
    real = {c: sorted(k[1] for k in surface if len(k) == 2 and k[0] == c)
            for c in ("data", "list")}
    CN = {7: "七", 8: "八", 9: "九", 4: "四", 5: "五"}
    for page in PAGES:
        p = REPO / page
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        for group, subs in real.items():
            want = CN.get(len(subs))
            for m in re.finditer(r"([一二三四五六七八九十]+)条子命令", text):
                if want and m.group(1) != want and group == "data":
                    line = text[:m.start()].count("\n") + 1
                    pytest.fail(f"{page}:{line}: 说「{m.group(1)}条子命令」，"
                                f"而 `fy {group}` 有 {len(subs)} 条：{subs}")
