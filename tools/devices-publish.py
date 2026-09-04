#!/usr/bin/env python3
"""把 `devices/` 里**这一版构建可以带**的装置文档发到一个输出目录。

    python3 tools/devices-publish.py --flavour public   --out dist/site/devices
    python3 tools/devices-publish.py --flavour internal --out dist/site/devices
    python3 tools/devices-publish.py --flavour public   --list      # 只问不发

★★**为什么是一个独立的工具。** 2026-09-04 起本仓的构建分内部版与公开版，而
`app/devices` 是**指向仓根 `devices/` 的符号链接**（用户裁定：单一数据源，单一发布
规则）。于是任何「把 `app/` 整棵拷出去」的动作都会连**整个语料**一起发出去——逐台
的卡片、许可账、以及只进内部版的机器。这不是假想的失败：`cp -RL` 的 `-L` 正是为了
解引用符号链接而在那里的。

所以发布装置文档这件事从「拷一个目录」变成「按规则逐份发」，而规则只有一处实现：
每台机器的 `devices/<id>/rights.json`（由 `tools/abox-to-devices.py` 从 A-Box 的
`dataset_fair.jsonld` 加本仓裁定生成）。两个发布者（静态站点与桌面可执行文件）都调
本工具，谁都不自己判许可——两个地方各判一遍，某一天它们会给出不同的答案，而**先
发现的人是拿到制品的那个**。

发什么：

* `devices/<id>.jsonld` —— 页面读的装置文档，逐台按 `rights.json` 判；
* `devices/catalogue.jsonld` —— 目录，**按实际发出去的那几台重写**。一份广告了一台
  不在这里的机器的目录，读者点下去得到 404，而页面会把它读成「装置数据坏了」而不是
  「这一版不带它」。

不发什么：`devices/<id>/`（卡片与许可账本身）——它们是本地输入，不是发布物。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "devices"


def rights(dev_dir: pathlib.Path) -> dict | None:
    p = dev_dir / "rights.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def plan(flavour: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(可发的 id, [(不可发的 id, 为什么)])。

    ★**没有许可账 = 不发。** 「账说不行」与「没有账」在这里是同一个答案，理由是
    同一条：发布的默认答案必须是「不能」，否则一台新拖回来的机器会因为**没人给它
    写账**而被发出去。
    """
    if not CORPUS.is_dir():
        return [], []
    ok: list[str] = []
    no: list[tuple[str, str]] = []
    for doc in sorted(CORPUS.glob("*.jsonld")):
        dev = doc.stem
        if dev == "catalogue":
            continue
        r = rights(CORPUS / dev)
        if r is None:
            no.append((dev, "没有 rights.json —— 许可未声明，默认不发"))
        elif flavour == "internal" and r.get("internal", True):
            ok.append(dev)
        elif flavour == "public" and r.get("public"):
            ok.append(dev)
        else:
            no.append((dev, (r.get("ruling") or "").strip() or "rights.json 说这一版不带"))
    return ok, no


def catalogue(out: pathlib.Path, shipped: set[str]) -> None:
    src = CORPUS / "catalogue.jsonld"
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
             "fylite:why": "不在这一版构建里——判据见 devices/<id>/rights.json 的裁定。"}
            for e in dropped)
    out.joinpath("catalogue.jsonld").write_text(
        json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if dropped:
        print("  目录：摘掉 " + " ".join(e.get("fylite:device_id", "?") for e in dropped))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flavour", choices=("public", "internal"), default="public")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--list", action="store_true", help="只列出这一版带哪几台")
    a = ap.parse_args(argv)

    if not CORPUS.is_dir():
        print("[devices] 没有 devices/ —— 这一版不带任何装置数据"
              "（拖回：python3 tools/abox-to-devices.py --all）", file=sys.stderr)
        return 0
    ok, no = plan(a.flavour)
    if a.list or not a.out:
        for dev in ok:
            print(dev)
        for dev, why in no:
            print(f"# {dev}: {why}", file=sys.stderr)
        return 0

    a.out.mkdir(parents=True, exist_ok=True)
    for dev in ok:
        shutil.copyfile(CORPUS / f"{dev}.jsonld", a.out / f"{dev}.jsonld")
    for dev, why in no:
        print(f"  {a.flavour} 版：不带 {dev}（{why[:60]}…）")
    catalogue(a.out, set(ok))
    print(f"[devices] {a.flavour} 版：{len(ok)} 台"
          + (f"（{' '.join(ok)}）" if ok else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
