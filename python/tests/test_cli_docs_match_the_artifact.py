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

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"

#: 读者会照着敲的那些页；`_build/` 与设计集不在内（后者写的是裁定，不是用法）
PAGES = ["docs/guide/cli.md", "docs/guide/quickstart.md", "docs/guide/install.md",
         "docs/guide/browser-app.md", "docs/guide/browser.md",
         "docs/reference/cli.md", "docs/reference/data-layer.md",
         "docs/reference/case-report.md", "docs/examples/index.md", "README.md"]

_CMD = re.compile(r"\bfy (app|data|case)(?: ([a-z_]+))?((?:\s+--?[a-z][a-z0-9-]*|\s+\S+)*)")
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
                key = (cmd, sub) if sub else (cmd,)
                if sub and key not in surface:
                    real = sorted(s for c, s in surface if c == cmd and s)
                    bad.append(f"{page}:{i}: `fy {cmd} {sub}` — no such subcommand (real: {real})")
                    continue
                for flag in _FLAG.findall(tail):
                    if flag not in surface[key]:
                        bad.append(f"{page}:{i}: `fy {cmd}{' ' + sub if sub else ''}` has no {flag}")
    assert not bad, "文档写的命令行与产物对不上：\n  " + "\n  ".join(bad)


def test_the_subcommand_count_the_prose_claims_is_the_real_one(surface):
    """★散文里的「N 条子命令」是最容易悄悄过期的一句：加一条子命令不会改它。"""
    real = {c: sorted(k[1] for k in surface if len(k) == 2 and k[0] == c)
            for c in ("data", "case")}
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
