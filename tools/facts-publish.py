#!/usr/bin/env python3
"""把 `devices/` 里**这一版构建可以带**的装置文档发到一个输出目录。

    python3 tools/facts-publish.py --flavour public   --out dist/site
    python3 tools/facts-publish.py --flavour internal --out dist/site
    python3 tools/facts-publish.py --flavour public   --list      # 只问不发

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

发什么：

* `facts/<域>/<id>.jsonld` —— 页面读的文档（发布路径与仓内路径同名），逐个按 `rights.json` 判；
* `facts/<域>/catalogue.jsonld` —— 目录，**按实际发出去的那几个重写**。一份广告了一台
  不在这里的机器的目录，读者点下去得到 404，而页面会把它读成「装置数据坏了」而不是
  「这一版不带它」。

不发什么：`facts/<域>/<id>/`（卡片与许可账本身）——它们是本地输入，不是发布物。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: ★★2026-09-04 `devices/` → `facts/`，按域分轴（用户裁定）。今天只有 `device` 一域
#: 有内容；`amns` / `experiment` 进来时本工具**不必改**——它按域走目录。
FACTS = ROOT / "facts"
#: ★★2026-09-04 用户裁定：`app/` 那侧也叫 `facts/device`，所以**一个名字贯穿全程**
#: ——仓里 `facts/device/`、页面取 `facts/device/`、发布出去还是 `facts/device/`。
#: 先前留过一层 URL 前缀映射（发成 `devices/`），现在不需要了：少一层映射，就少一处
#: 「存的和发的不同名」要记。`app/facts` 是指向仓根 `facts/` 的符号链接。


def rights(entry_dir: pathlib.Path) -> dict | None:
    p = entry_dir / "rights.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def domains() -> list[pathlib.Path]:
    """`facts/` 下有内容的那几个域。"""
    if not FACTS.is_dir():
        return []
    return sorted(d for d in FACTS.iterdir() if d.is_dir())


def plan(domain: pathlib.Path, flavour: str):
    """(可发的 id, [(不可发的 id, 为什么)])。

    ★**没有许可账 = 不发。**「账说不行」与「没有账」在这里是同一个答案，理由是
    同一条：发布的默认答案必须是「不能」，否则一个新拖回来的条目会因为**没人给它
    写账**而被发出去。
    """
    ok, no = [], []
    for doc in sorted(domain.glob("*.jsonld")):
        name = doc.stem
        if name == "catalogue":
            continue
        r = rights(domain / name)
        if r is None:
            no.append((name, "没有 rights.json —— 许可未声明，默认不发"))
        elif flavour == "internal" and r.get("internal", True):
            ok.append(name)
        elif flavour == "public" and r.get("public"):
            ok.append(name)
        else:
            no.append((name, (r.get("ruling") or "").strip() or "rights.json 说这一版不带"))
    return ok, no


def catalogue(domain: pathlib.Path, out: pathlib.Path, shipped: set) -> None:
    src = domain / "catalogue.jsonld"
    if not src.is_file():
        return
    d = json.loads(src.read_text(encoding="utf-8"))
    kept, dropped = [], []
    for e in d.get("fylite:devices", []):
        (kept if e.get("fylite:device_id") in shipped else dropped).append(e)
    d["fylite:devices"] = kept
    if dropped:
        d.setdefault("fylite:not_presets", []).extend(
            {"fylite:device_id": e.get("fylite:device_id"),
             "fylite:why": "不在这一版构建里——判据见 facts/<域>/<id>/rights.json 的裁定。"}
            for e in dropped)
    out.joinpath("catalogue.jsonld").write_text(
        json.dumps(d, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    if dropped:
        print("  目录：摘掉 " + " ".join(e.get("fylite:device_id", "?") for e in dropped))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flavour", choices=("public", "internal"), default="public")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--list", action="store_true", help="只列出这一版带哪几台")
    a = ap.parse_args(argv)

    if not domains():
        print("[facts] 没有 facts/ —— 这一版不带任何参考数据"
              "（拖回：python3 tools/abox-to-facts.py --all）", file=sys.stderr)
        return 0

    total = 0
    for domain in domains():
        ok, no = plan(domain, a.flavour)
        name = domain.name
        if a.list or not a.out:
            for e in ok:
                print(f"{name}/{e}")
            for e, why in no:
                print(f"# {name}/{e}: {why}", file=sys.stderr)
            continue
        out = a.out / "facts" / name
        out.mkdir(parents=True, exist_ok=True)
        for e in ok:
            shutil.copyfile(domain / f"{e}.jsonld", out / f"{e}.jsonld")
        for e, why in no:
            print(f"  {a.flavour} 版：不带 {name}/{e}（{why[:56]}…）")
        catalogue(domain, out, set(ok))
        total += len(ok)
        print(f"[facts] {name}: {a.flavour} 版 {len(ok)} 个"
              + (f"（{' '.join(ok)}）" if ok else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
