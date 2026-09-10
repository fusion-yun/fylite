"""`fy --help` 的每一屏：写给**用户**，不写给这个仓。

★★两条判据，都出自 2026-09-08 的一次通读：

  1. 帮助信息里不出现**项目内部的编号与出处**——设计书号（`FYL-DESIGN-…`）、条目号
     （`E-10`）、日期裁定（`2026-09-05 ruling`）、源文件名（`_cli.json`、`facts.rs`）。
     它们对写这个仓的人是索引，对敲这条命令的人是噪声：读者手上没有那些文件，
     查不到那些编号，而一句「按某年某月的裁定」既不说明该怎么用，也不说明为什么。
  2. 全局选项 `--nobanner` 在**任何位置**都收，并且每一屏用法上都印得出来。

★**例外（用户裁定）**：开发中未完成的功能可以点名——那种句子要说清「今天还不能用」，
而它凭什么不能用，往往只有内部的那个名字说得清。所以下面按**标记**判，不按话题判：
一条说明可以说某个功能未完成，但不该拿设计书号当理由。

★没有产物就跳过（源码检出里没有它是常态，`bash rust/build.sh --exe` 之后才有）。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"
SPEC = json.loads((REPO / "python" / "fylite" / "_cli.json").read_text(encoding="utf-8"))

#: 内部标记：设计书号 · 条目号 · 日期与裁定 · 本仓源文件名。
INTERNAL = re.compile(
    r"FYL-[A-Z]+-\d+"          # 设计书 / 报告号
    r"|FYD-[A-Z]+-\d+|SP-[A-Z]+-\d+"
    r"|\b[A-Z]-\d+\b"          # 条目号 E-10 / D-1 / T-C37
    r"|\b\d{4}-\d{2}-\d{2}\b"  # 日期
    r"|用户裁定|ruling\b"
    r"|_cli\.json|\.rs\b"
)


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not FY.is_file():
        pytest.skip(f"no built executable ({FY.relative_to(REPO)}) — bash rust/build.sh --exe")


def screens() -> list[tuple[str, str]]:
    """每一屏用法：顶层、每条命令、每个子命令。★屏幕清单**从规格现推**，
    不写死——写死的那天新加一条命令，这道闸子照绿。"""
    out = [("", _help())]
    for c in SPEC["commands"]:
        out.append((c["name"], _help(c["name"])))
        for sub in c.get("commands", []):
            out.append((f"{c['name']} {sub['name']}", _help(c["name"], sub["name"])))
    return out


def _help(*words: str) -> str:
    r = subprocess.run([str(FY), *words, "--help"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"`fy {' '.join(words)} --help` 退出 {r.returncode}：{r.stderr}"
    return r.stdout


def test_no_help_screen_cites_the_repository():
    bad = {}
    for name, text in screens():
        for line in text.splitlines():
            hits = INTERNAL.findall(line)
            if hits:
                bad.setdefault(name or "(top)", []).append((sorted(set(hits)), line.strip()[:110]))
    assert not bad, "帮助信息引用了项目内部的编号 / 出处：\n" + "\n".join(
        f"  {k}: {h} — {l}" for k, v in bad.items() for h, l in v)


def test_every_screen_prints_the_global_options():
    """全局选项在哪条命令上都收，所以在哪一屏都得说。"""
    flags = [f for g in SPEC.get("globals", []) for f in g["flags"]]
    assert flags, "规格里没有声明全局选项"
    for name, text in screens():
        for f in flags:
            assert f in text, f"`fy {name} --help` 没有印出 {f}"


@pytest.mark.parametrize("argv", [
    ["--nobanner", "list", "lines"],
    ["list", "--nobanner", "lines"],
    ["list", "lines", "--nobanner"],
])
def test_the_global_flag_is_accepted_anywhere(argv):
    """★三个位置都试：全局选项若靠每条命令各自声明，漏一条就报 unknown option，
    而漏的那条只在有人那么敲的时候才发作。"""
    r = subprocess.run([str(FY), *argv], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"`fy {' '.join(argv)}` 失败：{r.stderr}"
    plain = subprocess.run([str(FY), "list", "lines"], capture_output=True, text=True, timeout=120)
    assert r.stdout == plain.stdout, "全局选项改变了命令自己的产物"
