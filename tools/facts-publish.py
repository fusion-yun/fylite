#!/usr/bin/env python3
"""把**这一版构建可以带**的装置文档收成一个制品：`facts.rs`。

    python3 tools/facts-publish.py                    --out dist   # 缺省 internal
    python3 tools/facts-publish.py --flavour public   --out dist
    python3 tools/facts-publish.py --flavour public   --list       # 只问不发

★★**为什么是一个独立的工具。** 2026-09-04 起本仓的构建分内部版与公开版，而
`app/facts/device` 是**指向 `facts/device/` 的符号链接**（用户裁定：单一数据源，单一发布
规则）。于是任何「把 `app/` 整棵拷出去」的动作都会连**整个语料**一起发出去——逐台
的卡片、许可账、以及只进内部版的机器。这不是假想的失败：`cp -RL` 的 `-L` 正是为了
解引用符号链接而在那里的。

所以发布装置文档这件事从「拷一个目录」变成「按规则逐份发」，而规则只有一处实现：
每个条目的 `facts/<域>/<id>/rights.json`（由 `tools/abox-to-facts.py` 从 A-Box 的
`dataset_fair.jsonld` 加本仓裁定生成）。两个发布者（静态站点与桌面可执行文件）都调
本工具，谁都不自己判许可——两个地方各判一遍，某一天它们会给出不同的答案，而**先
发现的人是拿到制品的那个**。

发什么：**一个文件**，`facts.rs`——`(域, 标识, 文档正文)` 的一张 Rust 表，逐台按
`rights.json` 判，外加按实际发出去的那几台重写过的目录（`catalogue`）。

★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。此前发的是
「目录 + 逐台一份 JSON」，页面 fetch 它们，而命令行另有一张编进二进制的表——同一批
432 KB、两份字节、两条通路，且**没有任何东西保证它们描述同一批机器**。今天只剩一份：
`libfylite_runtime.so` 与 `fylite_runtime.wasm` 各把它编进去，命令行经
`facts::embedded_*` 读，页面经 wasm 的 `fylite_runtime_facts_ids` / `_doc` 读。

不发什么：`facts/<域>/<id>/`（卡片与许可账本身）——它们是本地输入，不是发布物。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: ★★优先级与「谁供了这一条」由 `fylite.facts` 一处决定，本工具不自己走目录。
#: 两处各实现一遍搜索顺序，某天它们会给出不同的答案——而发布是那个答案**发出去**
#: 的地方，先发现的人是拿到制品的那个。
sys.path.insert(0, str(ROOT / "python"))
from fylite import facts as _facts  # noqa: E402
#: ★★2026-09-04 `devices/` → `facts/`，按域分轴（用户裁定）。今天只有 `device` 一域
#: 有内容；`amns` / `experiment` 进来时本工具**不必改**——它按域走目录。
FACTS = ROOT / "facts"
#: ★★2026-09-04 用户裁定：`app/` 那侧也叫 `facts/device`，所以**一个名字贯穿全程**
#: ——仓里 `facts/device/`、页面取 `facts/device/`、发布出去还是 `facts/device/`。
#: 先前留过一层 URL 前缀映射（发成 `devices/`），现在不需要了：少一层映射，就少一处
#: 「存的和发的不同名」要记。`app/facts` 是指向仓根 `facts/` 的符号链接。


def plan(domain: str, flavour: str):
    """(可发的 [(id, 文档路径, 供它的根)], [(id, 为什么不发)])。

    ★**没有许可账 = 不发。**「账说不行」与「没有账」在这里是同一个答案，理由是
    同一条：发布的默认答案必须是「不能」，否则一个新拖回来的条目会因为**没人给它
    写账**而被发出去。
    """
    ok, no = [], []
    for e in _facts.entries(domain):
        if e.document is None:
            continue                      #: 只有卡片没有页面文档：不是发布物
        r = _facts.rights(domain, e.ident)
        if r is None:
            no.append((e.ident, "没有 rights.json —— 许可未声明，默认不发"))
        elif flavour == "internal" and r.get("internal", True):
            ok.append((e.ident, e.document, e.root))
        elif flavour == "public" and r.get("public"):
            ok.append((e.ident, e.document, e.root))
        else:
            no.append((e.ident, (r.get("ruling") or "").strip()
                       or "rights.json 说这一版不带"))
    return ok, no


def _strict(c):
    raise ValueError(f"bare {c}")


def _hashes(text: str) -> str:
    """一段文本放进 Rust 原始字符串要几个 `#`。"""
    n = 1
    while '"' + "#" * n in text:
        n += 1
        if n > 64:
            raise SystemExit("[facts] 文档里有 64 个连续的 '#'？——请手工核对")
    return "#" * n


def catalogue_doc(domain: str, shipped: set, out: pathlib.Path):
    """目录按**实际发出去的那几个**重写，落成一个临时文件，返回它的路径。

    ★一份广告了一台不在这里的机器的目录，读者点下去得到「没有这一条」，而页面会把它
    读成「装置数据坏了」而不是「这一版不带它」。所以目录不是照抄，是按发布计划重写，
    并把摘掉的那几台连理由一起记在 `fylite:not_presets` 里。

    ★★写成文件再交给 `artifacts()`，与逐台的文档走**同一条**路径：那一条路径上有
    「按严格 JSON 读一遍」的检查，而目录若走另一条路就绕过了它。
    """
    src = None
    for r in _facts.roots():
        c = r / domain / "catalogue.jsonld"
        if c.is_file():
            src = c
            break
    if src is None:
        return None
    d = json.loads(src.read_text(encoding="utf-8"), parse_constant=_strict)
    kept, dropped = [], []
    for e in d.get("fylite:devices", []):
        (kept if e.get("fylite:device_id") in shipped else dropped).append(e)
    d["fylite:devices"] = kept
    if dropped:
        d.setdefault("fylite:not_presets", []).extend(
            {"fylite:device_id": e.get("fylite:device_id"),
             "fylite:why": "不在这一版构建里——判据见 facts/<域>/<id>/rights.json 的裁定。"}
            for e in dropped)
        print("  目录：摘掉 " + " ".join(e.get("fylite:device_id", "?") for e in dropped))
    out.mkdir(parents=True, exist_ok=True)
    p = out / f".catalogue.{domain}.jsonld"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1, allow_nan=False) + chr(10),
                 encoding="utf-8")
    return p


def artifacts(out: pathlib.Path, flavour: str, rows_in) -> int:
    """**一个制品**：`facts.rs`——装置信息编进 Rust 那一侧（`FYL-DESIGN-19` A-8）。

    ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。
    在此之前同一批字节要发两遍：一遍给页面 fetch（站点上是文件，可执行文件里是
    `assets.rs` 的 `include_bytes!`），一遍编进 Rust 给命令行。两份字节、两条通路，
    而**没有任何东西保证它们描述同一批机器**——`FYL-DESIGN-19` A-9 本来打算用一道
    闸子去比对它们，而不必比对是更强的保证。

    今天只剩这一份：`libfylite_runtime.so` 与 `fylite_runtime.wasm` 各编进它，
    命令行经 `facts::embedded_*` 读，页面经 wasm 的
    `fylite_runtime_facts_ids` / `_doc` 读——同一份字节，两个宿主。

    ★许可闸一个字没动：进这份表的是 `plan()` 按每台 `rights.json` 选出来的那几台。
    """
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for domain, ident, doc in rows_in:
        #: ★按**严格 JSON** 读一遍再写出去：裸 NaN / Infinity 在这里当场炸。
        #: `json.loads` 缺省认它们，而浏览器的 `JSON.parse` 不认——一份带 NaN 的
        #: 文档编进制品之后，那一台在页面上整份读不出来，且构建全绿。
        text = doc.read_text(encoding="utf-8")
        try:
            json.loads(text, parse_constant=_strict)
        except ValueError as e:
            raise SystemExit(f"[facts] {domain}/{ident}: 不是严格 JSON（{e}）——"
                             f"上游修，不要编进制品")
        h = _hashes(text)
        rows.append(f'    ("{domain}", "{ident}", r{h}"{text}"{h}),')
    src = (
        "// facts —— 装置信息的**自带那一档**，生成物（`tools/facts-publish.py`），勿手改。\n"
        "//\n"
        "// ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。于是这是\n"
        "// facts 唯一的制品：`libfylite_runtime.so` 与 `fylite_runtime.wasm` 各把它编进去，\n"
        "// 命令行经 `facts::embedded_*` 读，页面经 wasm 的 `fylite_runtime_facts_ids` /\n"
        "// `_doc` 读——同一份字节，两个宿主，没有第二份可以跟它不一致。\n"
        "//\n"
        f"// 版别 {flavour}；{len(rows)} 条（含各域的 catalogue）。\n"
        "//\n"
        "// 由 `build.rs` 抄进 `$OUT_DIR` 再 `include!` 进 `src/facts.rs`——**不入库**：\n"
        "// 装置文档是受许可约束的数据，写成 `.rs` 提交进公开仓就是换一种语法发布同一批字节。\n"
        "pub static EMBEDDED: &[(&str, &str, &str)] = &[\n"
        + "\n".join(rows)
        + ("\n" if rows else "")
        + "];\n"
    )
    (out / "facts.rs").write_text(src, encoding="utf-8")
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    #: ★缺省 **internal**（2026-09-05 裁定，`FYL-DESIGN-19` A-14）。许可判据没有松：
    #: 它仍逐条在 `facts/<域>/<id>/rights.json`。公开面必须明写 `--flavour public`。
    ap.add_argument("--flavour", choices=("public", "internal"), default="internal")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--list", action="store_true", help="只列出这一版带哪几个")
    ap.add_argument("--facts", action="append", metavar="PATH",
                    help="要参与的 facts 语料，按优先级；可重复，也可用平台路径分隔符分隔"
                         "（缺省读 $FY_FACTS_PATH 与自带的那一份）")
    ap.add_argument("--roots", action="store_true",
                    help="只打印生效的搜索路径（排错用）")
    a = ap.parse_args(argv)

    #: ★★多源：`--facts` / `$FY_FACTS_PATH` 上的每一个根都参与，按优先级逐条决胜，
    #: 而**决胜的单位是条目**——第一个有 `<域>/<id>` 的根供出它的全部（文档、卡片、
    #: 许可账）。不跨根拼一份文档：那会造出一台没人运行的机器，而且不报错。
    if a.facts:
        parts = []
        for item in a.facts:
            parts.extend(x for x in item.split(os.pathsep) if x.strip())
        _facts.use(parts)
    for line in _facts.problems():
        print(f"[facts] {line}", file=sys.stderr)

    if a.roots:
        for r in _facts.roots():
            print(r)
        return 0

    doms = _facts.domains()
    if not doms:
        print("[facts] facts 搜索路径上没有语料"
              "（拖回：python3 tools/abox-to-facts.py --all；或给 --facts / "
              f"${_facts.FACTS_ENV}）", file=sys.stderr)
        return 0

    rows: list = []
    for domain in doms:
        ok, no = plan(domain, a.flavour)
        if a.list or not a.out:
            for ident, _doc, _root in ok:
                print(f"{domain}/{ident}")
            for ident, why in no:
                print(f"# {domain}/{ident}: {why}", file=sys.stderr)
            continue
        for ident, why in no:
            print(f"  {a.flavour} 版：不带 {domain}/{ident}（{why[:56]}…）")
        rows.extend((domain, ident, doc) for ident, doc, _r in ok)
        cat = catalogue_doc(domain, {i for i, _d, _r in ok}, a.out)
        if cat is not None:
            rows.append((domain, "catalogue", cat))
        #: ★发出去的东西要说得清是哪几个根供的——多源之后这不再是显然的。
        srcs = sorted({r.name for _i, _d, r in ok})
        print(f"[facts] {domain}: {a.flavour} 版 {len(ok)} 个"
              + (f"（{' '.join(i for i, _d, _r in ok)}）" if ok else "")
              + (f" ← {' + '.join(srcs)}" if len(srcs) > 1 else ""))
    if a.out is not None:
        n = artifacts(a.out, a.flavour, rows)
        #: 目录那份临时件用完就撤——制品只有一个文件，多出来的一个会让下一个人问
        #: 「这个也是发布物吗」。
        for _d, ident, doc in rows:
            if ident == "catalogue":
                doc.unlink(missing_ok=True)
        print(f"[facts] 一个制品 -> {a.out / 'facts.rs'}（{n} 条，{a.flavour} 版）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
