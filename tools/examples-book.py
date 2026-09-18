#!/usr/bin/env python3
"""算例篇的生成器：给每一章写「本章的文件」那一块，把目录里的每份文件链进书。

★★**为什么要链，而不只是在正文里写文件名**：MyST 只把**被链接到**的文件拷进站点。
算例章从前在正文里用行内代码写 `evolve-iter-15ma.jsonld`——读的人看得见名字，站点上
却没有那个文件，照着「原样跑、原样改、原样发给别人」做不下去。校验册的记录能下载，
正是因为它的章页用 Markdown 链接指着它们。

★**一章一块，块里是那一章目录下的全部文件**（`examples/<章>/*`，散文本身除外）；
篇首 `index.md` 收根上的目录与上下文、以及 `scenario/` 下的场景模板——那个目录没有
自己的章，它的文件由语料总章收。

★标题取自文件自己（`title.zh`），不在这里另写一份；一份文件改了标题，重跑本工具即可。

用法::

    python tools/examples-book.py            # 写各章的生成块
    python tools/examples-book.py --check    # 只核对是否最新（门用），不写盘
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EX = ROOT / "docs" / "examples"
BEGIN = "<!-- BEGIN GENERATED: tools/examples-book.py —— 勿手改 -->"
END = "<!-- END GENERATED -->"
#: 章页自己、笔记本（它本身就是一页）与构建残留不列
_SKIP_SUFFIX = {".md", ".ipynb"}
_SKIP_NAME = {"__pycache__", ".DS_Store"}
#: 篇首那一页收的文件：根上的两份，加上没有自己一章的 `scenario/` 目录
INDEX_DIRS = ("", "scenario")


def _what(p: pathlib.Path) -> tuple[str, str]:
    """(id, 标题)：JSON-LD 读它自己的 `id` 与 `title.zh`；脚本读 docstring 的第一行。"""
    if p.suffix == ".jsonld":
        d = json.loads(p.read_text(encoding="utf-8"))
        t = d.get("title")
        title = (t.get("zh") or t.get("en")) if isinstance(t, dict) else (t or "")
        if not title and "@context" in d and len(d) == 1:
            title = "JSON-LD 上下文（语料的词表映射）"
        return str(d.get("id", "")), str(title)
    if p.suffix == ".py":
        doc = p.read_text(encoding="utf-8").split('"""')
        first = doc[1].strip().splitlines()[0] if len(doc) > 2 else ""
        return "", first
    return "", ""


def files_of(dirs: tuple[str, ...]) -> list[pathlib.Path]:
    out = []
    for d in dirs:
        base = EX / d if d else EX
        out += sorted(p for p in base.iterdir()
                      if p.is_file() and p.suffix not in _SKIP_SUFFIX and p.name not in _SKIP_NAME)
    return out


def block(page: pathlib.Path, files: list[pathlib.Path]) -> str:
    rows = []
    for p in files:
        rel = p.relative_to(page.parent).as_posix()
        ident, title = _what(p)
        rows.append(f"| [`{rel}`]({rel}) | {f'`{ident}`' if ident else '—'} | {title.replace('|', '·')} |")
    head = ("## 本章的文件\n\n"
            "点文件名即得原文。计划可以原样跑、原样改（`fy run <文件>`），脚本用 `python <文件>`；"
            "目录、上下文与场景模板是给计划引用的，不单独跑。\n\n"
            "| 文件 | id | 标题 |\n| :--- | :--- | :--- |")
    return "\n".join([BEGIN, "", head, *rows, "", END])


def pages() -> dict[pathlib.Path, list[pathlib.Path]]:
    plan = {EX / "index.md": files_of(INDEX_DIRS)}
    for d in sorted(p for p in EX.iterdir() if p.is_dir() and p.name not in INDEX_DIRS):
        page = d / f"{d.name}.md"
        fs = files_of((d.name,))
        if page.is_file() and fs:
            plan[page] = fs
    return plan


def render(text: str, blk: str) -> str:
    if BEGIN in text:
        i, j = text.index(BEGIN), text.index(END, text.index(BEGIN)) + len(END)
        return text[:i] + blk + text[j:]
    return text.rstrip("\n") + "\n\n" + blk + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只核对，不写盘；过期则退 1")
    a = ap.parse_args()
    stale = []
    for page, fs in pages().items():
        old = page.read_text(encoding="utf-8")
        new = render(old, block(page, fs))
        if new != old:
            stale.append(page.relative_to(ROOT).as_posix())
            if not a.check:
                page.write_text(new, encoding="utf-8")
    if a.check and stale:
        print("过期（重跑 python tools/examples-book.py）：\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    if not a.check:
        print(f"wrote {len(stale)} page(s)" + (": " + ", ".join(stale) if stale else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
