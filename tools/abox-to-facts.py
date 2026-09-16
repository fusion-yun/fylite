#!/usr/bin/env python3
"""从 A-Box 拖回 ``facts/device/<id>/<id>_device.yaml``，并把它的**许可**一并带来。

★★2026-09-02 从内核仓搬到本仓并改名（原 ``fydata-to-fyo-device.py``）：装置牌是
**按需拖回的输入**，不是随仓走的数据。``facts/`` 在本仓 gitignore ——
要用的时候跑这个，用完不进版本库。

    python tools/abox-to-facts.py --all          # 全部机器
    python tools/abox-to-facts.py iter west      # 指定几台

★★**它不是一次「刷新」，是一次「换成上游今天的样子」。** 2026-09-02 实测：内核仓
committed 的那七张卡片是从**旧 epoch / 旧布局**生成的，拖回来的与它们不同，而且不止
出处路径——ITER 那张会**丢掉 `machine.fylite:b0`（5.3 T）**，壁面轮廓也从 `points`
换成 `r`/`z` 两个数组。所以拖回来之后要复核消费者，不能当作等价替换。

★**What this closes.**  the pulled tree held ONE machine — EAST — and the
only other device this repository could describe was a browser asset
(`app/assets/dev-iter.js`, since retired) in a shape nothing on the Python
side could read.  So "which machines does fylite know?" had two answers, in
two formats, and neither was the fyo device document that
`fylite.device.load_device` takes.

fydata already carries typed fyo A-Boxes per IDS (`fyo/0.0.0/…`, converted
from the upstream XML/MAT by its own `xml2fyo.py`), selected by a declarative
manifest (`machine.yaml`: epoch × provider × binding).  This assembles those
per-IDS files into the single fyo/JSON-LD document keyed by DD v4 group names
that this package reads — the same shape `east_device.yaml` has.

★**It converts; it does not invent.**  Every value is copied from a named
source file, and what the source does not carry is DECLARED absent
(``fylite:absent``) rather than defaulted.  That distinction is the whole
point of the exercise: `load_device` refuses a document that is quietly
missing an IDS group, because a half-read machine is worse than an error —
but a machine whose description genuinely has no interferometer is a fact,
not a half-read file, and it has to be sayable.

★★**machine_desc is retired (user ruling 2026-09-13).**  Every machine —
EAST included — is generated here from its A-Box, through the same loop, the
same rights ledger and the same derived `<id>.jsonld`.  There is no
hand-maintained device description any more and no second source to stage
one from.  EAST needs more groups than `build()`'s generic conversion emits
(operational, POINT chords, H&CD, pf_passive, the BRSP channel map, a PF set
paired from two providers), so `build()` hands it to its own assembler
(`ASSEMBLERS`); values that belong to the program rather than the machine sit
in `PROGRAM_SIDE`.

    python3 tools/abox-to-facts.py --list
    python3 tools/abox-to-facts.py iter
    python3 tools/abox-to-facts.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: ★★**fydoc 是权威源**（用户裁定 2026-09-02）。fydata 那侧同名内容是誊录，两边
#: 实测**逐值相同**（十台，差别只有记下来的出处路径），所以指哪一边都出得来同样的
#: 卡片——而权威在 fydoc，那就读 fydoc。`--source` 仍可显式指到 fydata。
#: ★不写死绝对路径：写死既换台机器即失效，又把构建者的目录布局发了出去。
#: 顺序是 `$FYDOC` → 同级目录探测 → 一个不存在的占位（调用方会看到清楚的报错）。
FYDOC = pathlib.Path(
    os.environ.get("FYDOC")
    or next((str(c) for c in (pathlib.Path(__file__).resolve().parents[2] / "fydoc",)
             if c.is_dir()), "fydoc"))
#: ★★2026-09-04 用户裁定：这些东西收在仓根 **`facts/`**，按**域**分轴——
#: `facts/device/<id>`（装置）· 将来 `facts/amns/<provider>`（原子分子）·
#: `facts/experiment/<machine>/<shot>`（实验切片）。**入 .gitignore**：不随
#: fylite 源码发布，但**可以进二进制与生成制品**（受 `rights.json` 的许可闸约束）。
#:
#: ★名字的由来：它装的是**关于具名个体的断言**——A-Box 的字面含义，用一个不需要
#: 术语表就读得懂的词说出来。与 `cases/` 成对：`cases/` 是**要跑什么**，
#: `facts/` 是**跑在什么之上**。（历经 `machine_desc/` → `devices/` → `facts/device/`：
#: 前两个名字都只说得了装置那一域。）
#: ★`models/` **不在这里**：神经网络权重不是关于世界的断言，是制品——它更靠近内核
#: 的 `.so` 而不是一份装置描述。它同样要许可账，但在自己的根下。
DOMAIN = "device"
#: ★★2026-09-05 用户裁定：**fylite 下已无 `facts/` 目录**。拖回来的语料落进
#: `dist/facts/`——一个构建暂存区（`dist/` 本来就不入库），发布器与打包器从这里取。
OUT = ROOT / "dist" / "facts" / DOMAIN

CONTEXT = {
    "sp": "https://spdata.org/sp#",
    "prov": "http://www.w3.org/ns/prov#",
    "fylite": "urn:fylite:",
    "fyo": "https://fusion-yun.github.io/fyo/latest/",
}

#: The groups `fylite.device.load_device` requires.  Every one of them is
#: written, either with content or with a `fylite:absent` reason.
REQUIRED = ("magnetics", "pf_active", "wall", "interferometer", "polarimeter",
            "data_source", "operational", "machine", "solver_dims")

#: ITER's own `tf` marks b0 "需要确认", so the vacuum field comes from the
#: reference equilibrium's header, which is where the browser descriptor
#: took it too before it became a document.
ITER_GFILE = ("reference/15MA inductive - burn/Standard domain R-Z/"
              "Low resolution - 65x129/g900003.00230_ITER_15MA_eqdsk16LR.txt")


# --------------------------------------------------------------------------- #
# reading the fydata side                                                     #
# --------------------------------------------------------------------------- #
def _load(path: pathlib.Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def device_root(root: pathlib.Path) -> pathlib.Path:
    """装置树的根 —— **fydoc 与 fydata 两种源都认**。

    ★★2026-09-02 用户裁定「以 `fydoc/device/*/abox` 为数据源」。fydoc 那侧的布局是
    `device/<id>/abox/`（JSON-LD），fydata 那侧是 `abox/device/tokamak/<id>/`
    （YAML）；两者内容等价（实测 `limiter`/`vessel` 逐值相同），差别在序列化与层级。

    ★两侧都重规划过不止一次（fydata：`machine/tokamak/` → `device/tokamak/` →
    `abox/device/tokamak/`；fydoc：`device/` → `facts/device/`，2026-09-04）。本文件
    从前把路径写死在三处、只改了一处，于是对着当时的 fydata 直接答「找不到」。
    现在**只有这一个函数知道布局**，而它按序探测——旧布局的检出照样能用。
    """
    for c in (root / "facts" / "device",              # fydoc（2026-09-04 起）
              root / "device",                        # fydoc（此前）
              root / "abox" / "device" / "tokamak",   # fydata（今天）
              root / "device" / "tokamak",            # fydata（旧）
              root / "machine" / "tokamak"):          # fydata（更旧）
        if c.is_dir():
            return c
    return root / "device"


def _abox(dev_dir: pathlib.Path) -> pathlib.Path:
    """一台机器的 A-Box 目录：fydoc 是 `<id>/abox/`，fydata 是 `<id>/` 本身。"""
    return dev_dir / "abox" if (dev_dir / "abox").is_dir() else dev_dir


#: ★★按炮号与测量链出卡（公开仓 PLAN H-35 选项 2；用户裁定 2026-09-13「测量链定装置构型」）。缺省卡片
#: 跟 manifest 的 `default` 走（EAST 当日裁定 R-S2：不给炮号即按最新炮），而一份测量要的是**它那一代、
#: 它那条测量链**的装置描述。`--shot N` 与 `--measurement-chain C` 只作用于 `TARGET` 里点名的机器。
SHOT = None
CHAIN = None
TARGET: set = set()
#: ★★2026-09-13 user rulings: **the rule lives only in the runtime, and card generation calls it.**
#: `--shot` / `--measurement-chain` are resolved by `fylite_runtime::device_resolve` through
#: `libfylite_runtime.so` (:func:`variant_card`) — the same entry `fylite.device.document(shot=,
#: measurement_chain=)` and `fy run --device` use — so a variant card is exactly what use-time
#: resolution gives.  No provider is named and no provider comparison is made in this file.


def _manifest(dev_dir: pathlib.Path):
    """`machine.jsonld`（fydoc）或 `machine.yaml`（fydata），谁在读谁。"""
    a = _abox(dev_dir)
    j, y = a / "machine.jsonld", a / "machine.yaml"
    if j.is_file():
        return json.loads(j.read_text(encoding="utf-8")), j
    if y.is_file():
        return yaml.safe_load(y.read_text(encoding="utf-8")), y
    return None, None


def devices(fydata: pathlib.Path) -> list[str]:
    """Machines that carry a manifest, in name order."""
    root = device_root(fydata)
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and _manifest(p)[0] is not None)


def _cite(path) -> str:
    """绝对路径 -> `<仓名>:<仓内相对路径>`。

    ★★**出处要能被别人解析，而不是能被我解析。** 这两份生成物一份进公开仓、一份
    随装置牌流转，写 `/home/<我>/workspace/fydoc/...` 有两个毛病：读者那里没有这个
    路径，以及它把构建者的目录布局连用户名一起发了出去（内核的制品加固为同一件事
    加过 `--remap-path-prefix`）。
    ★格式抄的是 A-Box 自己的写法——它的 `dcterms:source` 就是
    `fydata:abox/device/tokamak/iter/machine.yaml`。
    """
    p = pathlib.Path(path).resolve()
    for anc in p.parents:
        if (anc / ".git").exists():
            return f"{anc.name}:{p.relative_to(anc).as_posix()}"
    return p.name


def _pick(abox: pathlib.Path, rel: str):
    """manifest 里写的相对路径 -> A-Box 里真实存在的那个文件。

    ★★manifest 是 **fydata 的逐字誊录**，所以它里面的路径说的是 fydata 的层级
    （`fyo/latest/static/now/wall.yaml`）与序列化（`.yaml`）。fydoc 那侧同一份内容
    落在 `abox/static/now/wall.jsonld`。这里做的是那个映射，**且只做这一个映射**：
    去掉 `fyo/latest/` 前缀、换 `.jsonld` 后缀，两者各试一次。
    ★猜不出就返回 None，由调用方报错——不去目录里「找一个像的」：`wall` 的默认是
    `base`（落在 `static/now/`），而 fydoc 的 `providers/wall/` 里只有非默认的
    `metis`，按目录猜会稳定地挑错那一份。
    """
    cands = [rel]
    if rel.startswith("fyo/latest/"):
        cands.append(rel[len("fyo/latest/"):])
    out = []
    for c in cands:
        out.append(c)
        if c.endswith(".yaml"):
            out.append(c[:-5] + ".jsonld")
    for c in out:
        p = abox / c
        if p.is_file():
            return p
    return None


def _load(path: pathlib.Path):
    """`.jsonld` 走 json，其余走 yaml。"""
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".jsonld" else yaml.safe_load(text)


def _resolve(dev_dir: pathlib.Path, manifest: dict) -> dict:
    """``{ids_name: path}`` for the first epoch's default selection.

    ★The manifest's third axis (``bindings``) is about LIVE data and is not
    read here: a device description is the static side, and the only binding
    any of these machines declares is ``static`` anyway.  ``"@provider"``
    means "several variants exist" — the manifest's own ``default`` decides,
    which is the same rule fydata's own resolver follows.
    """
    epochs = manifest.get("epochs") or []
    if not epochs:
        return {}
    ep = epochs[0]
    abox = _abox(dev_dir)
    static_rel = ep.get("static", "")
    providers = manifest.get("providers") or {}
    out: dict[str, pathlib.Path] = {}
    missing: list[str] = []
    for ids, value in (ep.get("ids") or {}).items():
        if value == "@provider":
            spec = providers.get(ids) or {}
            avail = spec.get("available") or {}
            chosen = avail.get(spec.get("default")) or {}
            rel = chosen.get("path")
            if not rel:
                #: ★★不猜。见 `_pick` 的注记：按目录挑会稳定地挑错。
                missing.append(ids)
                continue
            p = _pick(abox, rel)
        else:
            p = _pick(abox, f"{static_rel}/{value}")
        if p is not None:
            out[ids] = p
    if missing:
        raise SystemExit(
            f"{dev_dir.name}: A-Box 的 manifest 没有 `providers` 选择表，而 "
            f"{sorted(missing)} 这几组标着 `@provider`。\n"
            "  ★fydoc 是权威源，所以这是 fydoc 那侧要补的一个键——它的 machine.jsonld\n"
            "  是 fydata machine.yaml 的誊录，而誊录时把 `providers` 丢了。\n"
            "  在补上之前，本工具不会替它挑一个默认：`wall` 的默认是 `base`（在\n"
            "  static/now/），而 providers/wall/ 里只放着非默认的 metis，按目录挑\n"
            "  会稳定地挑错那一份，而且不会报错。")
    return out


def _absent(ids: str, why: str) -> dict:
    #: ★没有 `count: 0`。一个计数放在它数的那个数组旁边，是同一个事实的第二个
    #: 出处；而这里连数组都没有，`count: 0` 数的是空气。它还是**裸**的——DD 里
    #: 没有这个名字，所以写进 IMAS 数据入口时逐条被丢掉（2026-09-07 实测：六台
    #: 机器每一台都丢它）。用户裁定 2026-09-07：不写。
    return {"@type": f"fyo:{ids}", "fylite:absent": why}


# --------------------------------------------------------------------------- #
# normalising each IDS into this package's document shape                     #
# --------------------------------------------------------------------------- #
def _rect(geometry: dict) -> dict | None:
    """One rectangular element, however the upstream spelled it.

    Two spellings are in the trees: ``{type: rectangle, center: [r, z],
    width, height}`` (the MAT-derived decks) and ``{geometry_type: 2,
    rectangle: {r, z, width, height}}`` (the XML-derived ones).  They are the
    same rectangle; a reader that knows only one silently drops half the
    machines.
    """
    if not isinstance(geometry, dict):
        return None
    if isinstance(geometry.get("rectangle"), dict):
        r = geometry["rectangle"]
        return {"r": float(r["r"]), "z": float(r["z"]),
                "width": float(r["width"]), "height": float(r["height"])}
    centre = geometry.get("center") or geometry.get("centre")
    if isinstance(centre, (list, tuple)) and len(centre) == 2 \
            and "width" in geometry and "height" in geometry:
        return {"r": float(centre[0]), "z": float(centre[1]),
                "width": float(geometry["width"]),
                "height": float(geometry["height"])}
    return None


def _elements(coil: dict) -> list[dict]:
    """``element`` as a list of rectangles, in the shape `device` reads.

    ★``fylite:a1`` / ``fylite:a2`` are the efund rectangle angles, and 90 is
    not a formality: ``a2 = 0`` collapses the coil onto a horizontal line.
    Every upstream rectangle here is upright, which is what 90 says.
    """
    raw = coil.get("element")
    items = raw if isinstance(raw, list) else ([raw] if raw else [])
    out = []
    for el in items:
        if not isinstance(el, dict):
            continue
        rect = _rect(el.get("geometry") or {})
        if rect is None:
            continue
        entry = {"geometry": {"geometry_type": "rectangle", "rectangle": rect},
                 "fylite:a1": 0.0, "fylite:a2": 90.0}
        #: ★the DD puts the turn count on the ELEMENT, and so does the
        #: canonical table (`@fyo-table DEVICE`): a channel total is a SUM of
        #: its elements, not a second field that can disagree with them.
        if el.get("turns_with_sign") is not None:
            entry["turns_with_sign"] = float(el["turns_with_sign"])
        out.append(entry)
    return out


def pf_active(doc: dict, source: str) -> dict:
    coils = []
    for i, c in enumerate(doc.get("coil") or []):
        entry = {"name": str(c.get("name") or c.get("identifier") or f"PF{i}")}
        #: ★K-2 (2026-09-13): the DD `function` identifier travels — it is what marks
        #: EAST's IC1/IC2 as fast vertical-control coils (`b_field_fb`), which every
        #: PF-set reader skips.
        if c.get("function"):
            entry["function"] = [dict(f) for f in c["function"]]
        entry["element"] = _elements(c)
        #: ★PCS I-5 (2026-09-14): the A-Box's per-coil limit travels — but NOT under the DD's
        #: `coil/current_limit_max`, which DD 4.1.1 defines as the tolerable current IN THE
        #: CONDUCTOR, a 2-D table over `b_field_max`.  The upstream value is the coil's whole
        #: ampere-turns (limit per turn × turns, e.g. CFEDR CS 60 kA × 738 = 44.28 MA), which is
        #: what `code/breakdown` / `code/discharge` call `i_max_aturn`.  Which door reads it from
        #: the card is ledger F-9's question; this only converts, it does not decide.
        lim = c.get("current_limit_max")
        if isinstance(lim, dict) and _num(lim.get("value")) is not None:
            if str(lim.get("unit", "A")) != "A":
                raise SystemExit(f"coil {entry['name']}: current_limit_max unit {lim.get('unit')!r} is not A")
            entry["fylite:i_max_aturn"] = _num(lim.get("value"))
        elif _num(lim) is not None:
            entry["fylite:i_max_aturn"] = _num(lim)
        if c.get("resistance") is not None:
            entry["resistance"] = float(c["resistance"])
        if c.get("description"):
            entry["fylite:description"] = str(c["description"])
        coils.append(entry)
    #: ★没有 `count`：`len(coil)` 已经是这个数，见 `_absent` 那一段。
    out = {"@type": "fyo:pf_active", "fylite:source": source, "coil": coils}
    #: ★K-2: the supplies travel too — `pf_active/supply[].{voltage,current}_limit_max`
    #: are what `code/breakdown` folds into per-channel ampere-turn limits.
    if doc.get("supply"):
        out["supply"] = [dict(s) for s in doc["supply"]]
    if doc.get("provenance"):
        out["fylite:upstream"] = doc["provenance"]
    return out


def _channels(entries, kind: str) -> list[dict]:
    out = []
    for i, c in enumerate(entries or []):
        pos = c.get("position")
        if isinstance(pos, list) and pos and isinstance(pos[0], dict):
            p = pos[0]
        elif isinstance(pos, dict):
            p = pos
        else:
            continue
        item = {"name": str(c.get("name") or c.get("identifier") or f"{kind}{i}"),
                "position": [{"r": float(p["r"]), "z": float(p["z"])}]}
        if c.get("poloidal_angle") is not None:
            item["poloidal_angle"] = float(c["poloidal_angle"])
        if c.get("length") is not None:
            item["length"] = float(c["length"])
        out.append(item)
    return out


def reference_boundary(dev_dir: pathlib.Path, manifest: dict) -> dict | None:
    """这台机器**自己记着的目标位形**——参考分离面，一条，由 A-Box 指名。

    ★★为什么卡片要带它（2026-09-08）。页面的「默认目标位形」此前是从限制器包围盒
    **推**出来的（`a = 0.66·amax` · `κ = 1.65` · `δ` 定值，见 `app/assets/device.js`
    的 `ranges()`）——对没有记录形状的机器那是个合理的起点，但对**记着自己形状**的
    机器，它是拿一个几何猜测去覆盖一份真数据。实测后果：ITER 的设计环恒定停在位形
    误差 0.0707（容差 0.0284），四次一模一样——不是没收敛，是那个目标它够不着。

    ★**不猜哪一条**：A-Box 的 `reference.separatrix` 列了四条，缺省由 `default` 指名
    （fydoc 2026-09-08 定为 `digitized_2`，理由记在那里：四条里唯一判 `partial`、
    主段与 ITER 官方目标分离面吻合的一条）。没有 `default` 就返回 None——挑哪一条是
    数据的事，不是转换器的事。

    ★NaN 按原样存在源里（断口），这里丢掉：一条要当目标用的曲线不能带断点。
    """
    ref = (manifest.get("reference") or {}).get("separatrix") or {}
    which = ref.get("default")
    if not which or which not in ref:
        return None
    rel = str(ref[which])
    #: A-Box 记的是 fydata 那侧的相对路径（`fyo/latest/reference/<x>.yaml`）；
    #: fydoc 这侧同名文件在 `abox/reference/` 下，扩展名是 `.jsonld`。
    cand = [_abox(dev_dir) / "reference" / (pathlib.Path(rel).stem + ".jsonld"),
            _abox(dev_dir) / rel]
    src = next((c for c in cand if c.is_file()), None)
    if src is None:
        return None
    doc = _load(src)
    ts = doc.get("time_slice")
    slice0 = ts[0] if isinstance(ts, list) and ts else ts
    found: dict = {}

    def dig(o, depth=0):
        if depth > 6 or found.get("r") is not None:
            return
        if isinstance(o, dict):
            if isinstance(o.get("r"), list) and isinstance(o.get("z"), list):
                found["r"], found["z"] = o["r"], o["z"]
                return
            for v in o.values():
                dig(v, depth + 1)
        elif isinstance(o, list) and o:
            for v in o[:4]:
                dig(v, depth + 1)

    dig(slice0)
    r, z = found.get("r"), found.get("z")
    if not r or not z:
        return None
    pts = [(float(a), float(b)) for a, b in zip(r, z)
           if a is not None and b is not None
           and math.isfinite(float(a)) and math.isfinite(float(b))]
    if len(pts) < 16:
        return None
    return {"@type": "fyo:reference_boundary",
            "fylite:source": _cite(src),
            "fylite:which": which,
            "r": [p[0] for p in pts], "z": [p[1] for p in pts],
            "fylite:dropped_non_finite": len(r) - len(pts)}


def payload(doc: dict, path: pathlib.Path) -> dict:
    """壳 + 同目录 payload：把 `.h5` 里的数值读回文档里。

    ★★**为什么会有「壳」这种东西**。ITER 的 magnetics 提供者
    `providers/magnetics/imas_md.jsonld` 只放标识 / 类型 / 出处 / 许可，数值存在同目录的
    `imas_md.h5`（485 KB）——那是 fydoc 那侧的裁定，理由写在它自己的 `dev:payloadNote`
    里：摊成 JSON-LD 约 1 399 951 字节，改一个标量要整文件重写，读回要先解析全文。

    ★★而本转换器此前**只读 JSON / YAML**，于是这一组安静地空了出来，卡片上写着
    `flux_loop: []`——空组读作「ITER 没有磁测量」，那是假的（实测：261 环 · 931 极向
    探针 · 45 环向 · 341 Rogowski）。这个函数就是把那句「读不了」变成「读得了」。

    ★**md5 要核**：壳自己记着 payload 的 md5 与字节数。核对不上就当场停——一份与壳
    对不上的 payload，比没有 payload 更坏：它会以壳的名义（出处、许可）被发出去。
    """
    pay = doc.get("dev:payload")
    if not isinstance(pay, dict) or pay.get("dev:format") != "hdf5":
        return doc
    name = str(pay.get("dev:filename") or "")
    h5path = path.parent / name
    if not h5path.is_file():
        raise SystemExit(f"{path}: 壳指着 payload {name}，而它不在同目录")
    raw = h5path.read_bytes()
    want_md5, want_len = pay.get("dev:md5"), pay.get("dev:bytes")
    if want_len is not None and len(raw) != int(want_len):
        raise SystemExit(f"{h5path}: {len(raw)} 字节，壳记的是 {want_len}")
    if want_md5:
        import hashlib
        got = hashlib.md5(raw).hexdigest()
        if got != want_md5:
            raise SystemExit(f"{h5path}: md5 {got} != 壳记的 {want_md5}")
    try:
        import h5py
    except ImportError:
        raise SystemExit(
            f"{path}: 这份提供者的数值在 {name} 里，读它要 h5py（pip install h5py）")
    import numpy as np

    def txt(a):
        return [x.decode() if isinstance(x, bytes) else str(x) for x in a]

    out = dict(doc)
    with h5py.File(h5path, "r") as f:
        g = f.get("magnetics")
        if g is None:
            return out
        #: ★★**分段环不是点环，两者不可混**（实测 2026-09-08）。IMAS 的
        #: `flux_loop.position` 是一串点：EAST 的 35 环每环 **1** 个点（整周环，测的是
        #: 该处的极向磁通 ψ），ITER 这 261 环每环 **5** 个点（`Partial Flux Loops`，
        #: 鞍形，测的是所围面积上的磁通）。本仓的反演把磁通环当作 (r,z) 上的点传感器
        #: ——把五点鞍形环取第一个顶点塞进去，得到的不是「精度差一点的环」，而是
        #: **另一个物理量按错误的模型参与拟合**，而它照样能算出一张图。所以这里只收
        #: 单点环，多点的逐条记下并说明为什么没收。
        if "flux_loop" in g:
            fl = g["flux_loop"]
            pos = fl["position"]
            off = pos["__offsets"][:] if "__offsets" in pos else None
            r, z = pos["r"][:], pos["z"][:]
            names = txt(fl["name"][:]) if "name" in fl else []
            desc = txt(fl["description"][:]) if "description" in fl else []
            loops, skipped = [], []
            n = len(names) if names else (len(off) - 1 if off is not None else len(r))
            for i in range(n):
                lo, hi = (int(off[i]), int(off[i + 1])) if off is not None else (i, i + 1)
                nm = names[i] if i < len(names) else f"FL{i}"
                if hi - lo != 1:
                    skipped.append({"name": nm, "points": hi - lo,
                                    "description": desc[i] if i < len(desc) else ""})
                    continue
                loops.append({"name": nm,
                              "position": [{"r": float(r[lo]), "z": float(z[lo])}]})
            out["flux_loop"] = loops
            if skipped:
                out["fylite:flux_loop_not_taken"] = {
                    "count": len(skipped),
                    "why": ("多点（分段 / 鞍形）磁通环：本仓的反演模型把磁通环当作 "
                            "(r,z) 上的点传感器，测的是该处的极向磁通；分段环测的是"
                            "所围面积上的磁通，是另一个观测量。按点收进来会以错误的"
                            "模型参与拟合，且不会报错。"),
                    "names": [s["name"] for s in skipped[:8]],
                }
        #: 极向探针两侧同型：点 + 极向角，直接可用。
        if "b_field_pol_probe" in g:
            bp = g["b_field_pol_probe"]
            r, z = bp["position"]["r"][:], bp["position"]["z"][:]
            names = txt(bp["name"][:]) if "name" in bp else []
            ang = bp["poloidal_angle"][:] if "poloidal_angle" in bp else None
            probes = []
            for i in range(len(r)):
                item = {"name": names[i] if i < len(names) else f"BP{i}",
                        "position": [{"r": float(r[i]), "z": float(z[i])}]}
                if ang is not None and np.isfinite(ang[i]):
                    item["poloidal_angle"] = float(ang[i])
                probes.append(item)
            out["b_field_pol_probe"] = probes
    return out


def magnetics(doc: dict, source: str) -> dict:
    """★The DD's own ARRAYS — the canonical spelling (`@fyo-table DEVICE`).

    It emitted `{count, channel: [...]}` for one batch, which is what
    `facts/device/east/east_device.yaml` wrote before that table existed and
    what `app/assets/fyodev.js` never wrote.  A count beside the array it
    counts is a second source for a fact the first one carries.
    """
    loops = _channels(doc.get("flux_loop"), "FL")
    probes = _channels(doc.get("b_field_pol_probe"), "BP")
    out = {"@type": "fyo:magnetics", "fylite:source": source,
           "flux_loop": loops, "b_field_pol_probe": probes}
    if not probes:
        out["fylite:b_field_pol_probe_absent"] = (
            "the upstream magnetics description carries flux loops only")
    #: ★★**没收进来的，要在卡片上留痕**（2026-09-08）。`payload()` 会拒收多点（分段 /
    #: 鞍形）磁通环——那是另一个观测量，按点收会以错误的模型参与拟合而不报错。但只在
    #: 转换器里拒收是不够的：卡片上只剩 `flux_loop: []`，下一个人读作「这台机器没有
    #: 磁通环」，然后去「修」它。把拒收的条数与理由一并写在卡片上，那句「没有」才有出处。
    if doc.get("fylite:flux_loop_not_taken"):
        out["fylite:flux_loop_not_taken"] = doc["fylite:flux_loop_not_taken"]
    if doc.get("provenance"):
        out["fylite:upstream"] = doc["provenance"]
    return out


def _points(outline) -> tuple[list[float], list[float]]:
    """``{r: [...], z: [...]}`` from whichever way the outline is written."""
    if isinstance(outline, dict) and "points" in outline:
        pts = outline["points"]
        return ([float(p[0]) for p in pts], [float(p[1]) for p in pts])
    if isinstance(outline, dict) and "r" in outline and "z" in outline:
        return ([float(x) for x in outline["r"]],
                [float(x) for x in outline["z"]])
    return ([], [])


def wall(doc: dict, source: str) -> dict:
    """``description_2d`` in this package's shape, from either upstream form.

    ITER's wall puts ``limiter`` / ``vessel`` at the top level; WEST's wraps
    them in a ``description_2d`` LIST (which is what the DD says).  Both mean
    the same machine.
    """
    d2 = doc.get("description_2d")
    if isinstance(d2, list) and d2:
        d2 = d2[0]
    elif not isinstance(d2, dict):
        d2 = doc
    units = []
    raw = ((d2.get("limiter") or {}).get("unit")) or []
    if isinstance(raw, dict):
        raw = [raw]
    for u in raw:
        r, z = _points(u.get("outline") or {})
        if not r:
            continue
        #: ★没有 `count`：`len(outline/r)` 已经是这个数，见 `_absent` 那一段。
        units.append({"name": str(u.get("name") or "limiter"),
                      "outline": {"r": r, "z": z}})
    inner = {"limiter": {"unit": units}}
    vessel = d2.get("vessel")
    if vessel:
        inner["vessel"] = vessel
    #: ★`description_2d` is an ARRAY of structure in the DD, and the canonical
    #: table declares it as one.  It was a bare mapping here for one batch.
    out = {"@type": "fyo:wall", "fylite:source": source,
           "description_2d": [inner]}
    if not units:
        out["fylite:absent"] = (
            "the upstream wall description carries no limiter outline")
    if doc.get("provenance"):
        out["fylite:upstream"] = doc["provenance"]
    return out


def _iter_gfile_field(fydata: pathlib.Path) -> tuple[float, float] | None:
    """``(RCENTR, BCENTR)`` from the ITER reference equilibrium's header.

    ★The g-file, not the upstream ``tf``, and not literature.  ITER's own
    ``tf.xml`` carries ``r0`` and marks ``b0`` 需要确认, so a vacuum field
    typed in from a paper would be a number with no source in either tree.
    It is the file the browser descriptor took B0 from as well, back when
    that descriptor was hand-generated JavaScript; the preset is generated
    from THIS document now, so the two cannot disagree at all.
    """
    p = fydata / ITER_GFILE
    if not p.is_file():
        return None
    lines = p.read_text(errors="ignore").splitlines()
    if len(lines) < 3:
        return None
    #: line 2: rdim zdim rcentr rleft zmid · line 3: rmaxis zmaxis simag sibry bcentr
    head = re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", lines[1])
    axis = re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", lines[2])
    if len(head) < 3 or len(axis) < 5:
        return None
    return float(head[2]), float(axis[4])


def _num(v):
    """一个标量：裸数，或 `{data|value, unit}` 包装里的那个数。取不出就是 None。"""
    if isinstance(v, dict):
        v = v.get("data", v.get("value", v.get("@value")))
    if isinstance(v, (list, tuple)):
        v = v[0] if len(v) == 1 else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def machine_block(name: str, tf: dict | None, limiter_units: list[dict],
                  extra_note: str | None, field: tuple | None = None) -> dict:
    out: dict = {"@type": "fyo:machine", "name": name}
    if field:
        rcentr, bcentr = field
        out["r_centre"] = float(rcentr)
        out["r_centre_note"] = "RCENTR from the reference equilibrium header"
        #: the MAGNITUDE: the g-file's sign is its COCOS convention's, and
        #: this field is the machine's vacuum field, not a signed component.
        out["fylite:b0"] = abs(float(bcentr))
        out["fylite:b0_note"] = ("|BCENTR| from the same header; the sign "
                                 "there is the g-file's COCOS convention")
    elif tf and _num(tf.get("r0")) is not None:
        #: ★`r0` 与 `b_field_phi_vacuum_r` 同形：可能是裸数，也可能是
        #: `{data|value, unit}` 包装（实测 cmod 是后者，而这里从前只当裸数读，
        #: 于是 `float(dict)` 当场抛异常、`--all` 在第四台上整批停住）。同一个
        #: 解包规则两处共用，不各写一份。
        out["r_centre"] = _num(tf.get("r0"))
        out["r_centre_note"] = "tf.r0 from the upstream description"
        rb = tf.get("b_field_phi_vacuum_r")
        #: ★`data` FIRST, `value` as the fallback.  fydata standardised the
        #: {quantity, unit} wrapper key on `data` (78d2544); reading only
        #: `value` made `fylite:b0` vanish from best / cfedr / cfetr WITHOUT
        #: an error — a dropped field reads as「上游没有这个量」, which is the
        #: worst failure mode a converter has.
        value = _num(rb)
        r0 = _num(tf.get("r0"))
        if value is not None and r0:
            out["fylite:b0"] = float(value) / r0
            out["fylite:b0_note"] = (
                "b_field_phi_vacuum_r / r0, both from the upstream tf")
        #: ★★上游写 `b0` 而不写 `b_field_phi_vacuum_r` 的那一形（ITER 的文献件就是
        #: 这一形：`b0` 5.3 T，两条一手源，并注明「Baseline 2024 下仍然成立」）。
        #: 只认前一个名字的那一版把这个量整个丢掉了 —— 实测 2026-09-07：ITER 的
        #: `machine` 块**根本没有 `fylite:b0`**，而上游明明有，且有出处。
        #: 这不是换算，是**读上游已经写下的那个数**。
        elif _num(tf.get("b0")) is not None:
            out["fylite:b0"] = _num(tf.get("b0"))
            out["fylite:b0_note"] = "tf.b0 from the upstream description"
    else:
        out["r_centre"] = None
        out["r_centre_note"] = "[TBD] the upstream description carries no tf.r0"
    if extra_note:
        out["fylite:note"] = extra_note
    grid = _grid(limiter_units)
    out["default_grid"] = grid if grid else {
        "fylite:absent": "[TBD] no limiter outline to bound a grid box with"}
    return out


def _grid(units: list[dict]) -> dict | None:
    """A computational box that contains every limiter outline, with a margin.

    ★Rounded OUTWARD to a centimetre.  A box derived from the wall and then
    rounded the other way clips the wall it was derived from, which shows up
    as a boundary that limits on the box rather than on the machine.
    """
    rs = [x for u in units for x in u["outline"]["r"]]
    zs = [x for u in units for x in u["outline"]["z"]]
    if not rs:
        return None
    import math
    pad = 0.05
    return {"r_min": math.floor((min(rs) - pad) * 100) / 100,
            "r_max": math.ceil((max(rs) + pad) * 100) / 100,
            "z_min": math.floor((min(zs) - pad) * 100) / 100,
            "z_max": math.ceil((max(zs) + pad) * 100) / 100,
            "note": ("derived from the limiter outline(s) in this document "
                     "with a 5 cm margin, rounded outward")}


# --------------------------------------------------------------------------- #
# assembly                                                                     #
# --------------------------------------------------------------------------- #
def _has_content(name: str, node) -> bool:
    """这一组里有没有**实际内容**（而不只是一个壳）。

    ★★这把尺必须与闸子 `test_machine_desc.py::_has_content` **逐字**是同一把：
    转换器数一套、闸子数另一套，就会出现「工具认为写了张好卡片、闸子认为它什么也
    没转出来」——2026-09-04 实测正是如此（工具数「任何带 fylite:source 的组」，
    而 `tf` 总是带，于是五台只有 tf 的机器各写出一张空卡片）。
    """
    if not isinstance(node, dict):
        return bool(node)
    if name == "magnetics":
        return any(node.get(k) for k in ("flux_loop", "b_field_pol_probe"))
    if name == "pf_active":
        return bool(node.get("coil"))
    if name == "wall":
        d2 = node.get("description_2d") or [{}]
        return bool((d2[0] or {}).get("limiter", {}).get("unit"))
    if name in ("interferometer", "polarimeter"):
        return bool(node.get("channel"))
    return bool(node)


def build(dev: str, fydata: pathlib.Path, providers: dict | None = None) -> dict:
    #: ★a machine whose document needs more than the generic conversion has its
    #: own assembler — still from the A-Box, still through this entry point
    if dev in ASSEMBLERS:
        return ASSEMBLERS[dev](fydata, providers)
    if providers:
        raise SystemExit(f"{dev}: providers are chosen per request only for {sorted(ASSEMBLERS)}")
    dev_dir = device_root(fydata) / dev
    manifest, manifest_path = _manifest(dev_dir)
    files = _resolve(dev_dir, manifest)
    rel = {k: str(v.relative_to(fydata)) for k, v in files.items()}

    doc: dict = {
        "@context": dict(CONTEXT),
        "@id": f"fylite:device/{dev}",
        "@type": "fyo:DeviceDescription",
        "_dd_version": str(manifest.get("dd_source", "imas/4")).split("/")[-1],
        "_machine": str(manifest.get("device", dev.upper())),
        "_basis": f"{_cite(manifest_path.parent)} (epoch "
                  f"{(manifest.get('epochs') or [{}])[0].get('id', '?')})",
        "provenance": {
            "generator": "tools/abox-to-facts.py",
            "source": _cite(manifest_path),
            "identity_iri": manifest.get("identity_iri"),
            "source_files": rel,
            "note": (
                "Converted, not authored: every value below is copied from "
                "the file named in `fylite:source`, and a group the upstream "
                "description does not carry is marked `fylite:absent` rather "
                "than defaulted.  Re-run the generator to re-derive and diff."),
        },
    }

    tf = _load(files["tf"]) if "tf" in files else None
    note, field = None, None
    #: ★参考平衡的头行只在上游**两个名字都没有**时才用得着。ITER 的文献件
    #: 2026-09-03 起带 `b0`（两条一手源），所以那条退路今天走不到 —— 留着是因为
    #: 上游换一个提供者就可能又走得到，而它自己会说清那个数是从哪来的。
    if (dev == "iter" and tf is not None
            and "b_field_phi_vacuum_r" not in tf and _num(tf.get("b0")) is None):
        field = _iter_gfile_field(fydata)
        if field:
            rcentr, bcentr = field
            note = (f"the upstream tf carries r0 only and marks b0 unconfirmed, "
                    f"so R0/B0 come from the reference equilibrium header "
                    f"(fydata {ITER_GFILE}: RCENTR={rcentr}, BCENTR={bcentr}) "
                    f"— and the browser preset inherits them from this "
                    f"document, so the two cannot disagree")

    if "pf_active" in files:
        doc["pf_active"] = pf_active(_load(files["pf_active"]), rel["pf_active"])
    else:
        doc["pf_active"] = _absent(
            "pf_active", "the upstream tree carries no pf_active IDS")
        doc["pf_active"]["coil"] = []

    #: ★这台机器自己记着的目标位形，见 `reference_boundary()` 的抬头。没有就没有
    #: ——页面那边照旧从包围盒推一个起点。
    rb = reference_boundary(dev_dir, manifest)
    if rb:
        doc["fylite:reference_boundary"] = rb

    if "magnetics" in files:
        doc["magnetics"] = magnetics(
            payload(_load(files["magnetics"]), files["magnetics"]),
            rel["magnetics"])
        #: ★★**解析得到一个文件、而那个文件不带内容**，与「上游没有这个 IDS」是
        #: 两件事，必须分开说。实测 2026-09-04：ITER 的默认 magnetics 提供者
        #: `providers/magnetics/imas_md.jsonld` 是一份**元数据旁挂**（出处 + 许可，
        #: CC-BY-4.0 / Zenodo DOI），真正的数据在同目录的 `imas_md.h5`（485 KB）——
        #: 而本转换器只读 JSON / YAML。于是这一组安静地空了出来，而空组读作
        #: 「ITER 没有磁测量」，那是假的。
        if not _has_content("magnetics", doc["magnetics"]):
            src = rel["magnetics"]
            doc["magnetics"] = _absent(
                "magnetics",
                f"解析到 {src}，但它不带测量内容——"
                f"（实测：该提供者是元数据旁挂，数据在同名 .h5 里，"
                f"本转换器只读 JSON / YAML）")
            doc["magnetics"]["fylite:source"] = src
            doc["magnetics"]["b_field_pol_probe"] = []
            doc["magnetics"]["flux_loop"] = []
    else:
        doc["magnetics"] = _absent(
            "magnetics", "the upstream tree carries no magnetics IDS — this "
            "machine has no described diagnostic set here")
        doc["magnetics"]["flux_loop"] = []
        doc["magnetics"]["b_field_pol_probe"] = []

    units: list[dict] = []
    if "wall" in files:
        doc["wall"] = wall(_load(files["wall"]), rel["wall"])
        units = doc["wall"]["description_2d"][0]["limiter"]["unit"]
    else:
        doc["wall"] = _absent("wall", "the upstream tree carries no wall IDS")
        doc["wall"]["description_2d"] = [{"limiter": {"unit": []}}]

    #: ★the passive conductors, when the A-Box carries them.  Without this the vessel
    #: units reach the card as `annular` outlines only, and BOTH passive readers go
    #: silent on them: `case.rs::device_passive` says so in as many words ("units
    #: carrying only an outline have no elements and contribute nothing"), and
    #: `passive_set` refuses outright.  Measured on ITER before this: `pf_passive` was
    #: absent from the card and not one of its fourteen vessel units had an `element`,
    #: so `code/vstab` and `code/wall` saw NO passive structure on that machine at all.
    if "pf_passive" in files:
        doc["pf_passive"], vessel_units = generic_pf_passive(
            _load(files["pf_passive"]), rel["pf_passive"], VESSEL_GROUP.get(dev))
        if vessel_units:
            doc["wall"]["description_2d"][0]["vessel"] = {"unit": vessel_units}
            doc["fylite:vessel_resistivity_uohm_m"] = \
                doc["pf_passive"]["vessel"]["resistivity_uohm_m"]

    if tf is not None:
        #: ★三个量都过 `_num`：上游有两种写法（裸数，或 `{data|value, unit}` 包装），
        #: 原样抄过来的那一版把包装也抄了进去，下游读到的是一个映射。
        #: ★`coils_n` 上游也有两种写法：`coils_n`（fydata 的静态件），或
        #: `coil.dev:count`（文献件 —— ITER 的 18 个 TF 线圈就在那里，带出处）。
        #: 只认前一个的那一版把它写成 `null`，而「没有这个数」与「有，只是叫别的
        #: 名字」是两件事。两个都没有才是 `null`，那时它真的没有。
        coil = tf.get("coil")
        coils_n = _num(tf.get("coils_n"))
        if coils_n is None and isinstance(coil, dict):
            coils_n = _num(coil.get("dev:count"))
        doc["tf"] = {"@type": "fyo:tf", "fylite:source": rel["tf"],
                     "r0": _num(tf.get("r0")),
                     "coils_n": int(coils_n) if coils_n is not None else None,
                     "b_field_phi_vacuum_r": tf.get("b_field_phi_vacuum_r")}
        #: ★上游只有 `b0` 的那一形原样带过来：`fylite_runtime` 归一化时按
        #: `b_field_phi_vacuum_r/data = r0 * b0` 换算成 DD 要的那一支。
        #: 在这里先乘一遍也算得出同一个数，但那会让**同一条换算**有两个实现。
        if _num(tf.get("b0")) is not None:
            doc["tf"]["b0"] = _num(tf.get("b0"))

    for ids, why in (
            ("interferometer", "no interferometer in the upstream description"),
            ("polarimeter", "no polarimeter in the upstream description")):
        doc[ids] = _absent(ids, why)
        doc[ids]["channel"] = []

    doc["data_source"] = {
        "fylite:absent": (
            "no live data tree for this machine in this repository — the "
            "upstream manifest declares a `static` binding only"),
    }
    doc["operational"] = {
        "@type": "fylite:OperationalSettings",
        "fylite:absent": (
            "fit control and read-time gates are an OPERATOR's settings; the "
            "upstream description carries none for this machine"),
    }
    doc["machine"] = machine_block(str(manifest.get("device", dev.upper())),
                                   tf, units, note, field)
    if "solver_dims" in PROGRAM_SIDE.get(dev, {}):
        #: ★PCS I-5: a program-side solve resolution for a machine with no libefit build —
        #: the free-boundary box grid `code/discharge` reads beside `machine/default_grid`
        doc["solver_dims"] = dict({"@type": "fylite:CompiledDimensions",
                                   "note": ("solve-box resolution chosen by the program for this machine "
                                            "(PROGRAM_SIDE in the generator — not a device fact, and no "
                                            "compiled libefit exists for it)")},
                                  **PROGRAM_SIDE[dev]["solver_dims"])
    else:
        doc["solver_dims"] = {
            "@type": "fylite:CompiledDimensions",
            "fylite:absent": (
                "compiled EFIT array dimensions are a property of a built "
                "libefit.so for one machine; none exists for this one"),
        }
    missing = [g for g in REQUIRED if g not in doc]
    assert not missing, missing
    return doc


# --------------------------------------------------------------------------- #
# EAST from the A-Box (P2a of the machine_desc retirement, 2026-09-13)         #
# --------------------------------------------------------------------------- #
#: ★★Why EAST has its own assembler (reached through `build()`, see `ASSEMBLERS`).
#: EAST's document needs groups the generic conversion never emits (operational,
#: POINT chords, H&CD, pf_passive, the BRSP channel map) and a PF set paired from
#: TWO providers.  Provider selection is the manifest's own `default` for the card, and the
#: runtime's rule (shot + measurement chain) per request — nothing here re-selects a provider.
#:
#: ★★★The rule is the same as everywhere in this file: convert, never invent.
#: A field the A-Box does not carry is named under `fylite:absent` with a
#: reason — not defaulted.

#: ★User ruling 2026-09-13: PF cross-sections are the deck/Luo ones (`yu`, the
#: geometry libefit's Green tables were built on, in deck element order); every
#: electrical field (resistance, turns, IC coils, supplies, BRSP circuit) is
#: `base`, paired to a deck element BY RECTANGLE CENTRE, never by list position.
EAST_PF_GEOMETRY_PROVIDER = "yu"
EAST_PF_ELECTRICAL_PROVIDER = "base"
#: centres agree to the digit between the two providers; a tolerance well
#: below the smallest coil spacing (0.25 m) and above print rounding
CENTRE_TOL_M = 1e-4

#: ★★PROGRAM-SIDE values, not device facts (user ruling 2026-09-13): the
#: compiled libefit.so dimensions, the Faraday-rotation constant, the default
#: solver box, the POINT chords EFIT fits, and the page preset.  They belong to
#: fylite, not to fydoc — so they do not come from the A-Box, and for now they
#: live in this small table, keyed by device id, values copied from the retired
#: card.  ★FOLLOW-UP: move this table into the package proper (next to the
#: solver it describes) and stop writing it into the device document.
PROGRAM_SIDE = {
    #: ★PCS I-5 (2026-09-14): CFEDR has no libefit build; its solve box is resolved 65 × 65 —
    #: the grid the kernel's CFEDR gates measured on (position control C4 settles at 65 and
    #: does not at 129 with the same gains, ledger I-3)
    "cfedr": {
        "solver_dims": {"nw": 65, "nh": 65},
    },
    "east": {
        #: ★2026-09-13: no `nsilop` / `nprobe` — the probe and loop counts are the resolved
        #: magnetics group's own (`fylite.device._derive`), not a compiled constant beside it
        "solver_dims": {"nw": 65, "nh": 65, "nfcoil": 12},
        "faraday_constant": 2.62e-13,
        #: ★2026-09-14: the POINT pre-shot offset window — every chord has the mean of the
        #: samples with |t - centre_s| < tolerance_s subtracted before the slice window is averaged
        #: (`fylite.io.raw.reduce_series`).  PROGRAM-SIDE, like `faraday_constant`: it is a
        #: constant in the reduction code, not a property of the diagnostic —
        #: `EFIT_POINT_GUI_v5.m:388` hard-codes `find(abs(t_point+0.9)<0.01)`, the retired card
        #: (kernel 71c7cef `polarimeter.baseline`) carried the same -0.9 / 0.01, and fydoc's
        #: polarimeter pages and provenance record no such window.  ★That GUI line's own comment
        #: says "offset at -8ms", which does not match -0.9 s; the code is what ran, so the code's
        #: numbers are kept.
        "point_baseline": {"centre_s": -0.9, "tolerance_s": 0.01},
        "default_grid": {"r_min": 1.2, "r_max": 2.8, "z_min": -1.4, "z_max": 1.4},
        #: the chords the EFIT POINT constraint uses (the interferometer IDS also
        #: carries HCN / SSI / DI, which EFIT does not fit)
        "point_chord_prefix": "POINT",
        #: ★2026-09-14: the R every POINT chord's `first_point` is written at — the ORIGIN the
        #: chord is cast from, inward along -R for `length` (kernel `code/chords`, `case.rs`
        #: `chords_case` -> `diagnostics::chord_samples`; the page's `chordLines` the same;
        #: `fylite.device.POINT_RPOL`).  PROGRAM-SIDE, like `point_baseline`: fydoc states the
        #: chords' z and that they are horizontal, but its `first_point.r` 0.0 / `second_point.r`
        #: 3.0 are a symbolic segment (polarimeter provenance: "象征性远端点非实测光阑位置"), and
        #: no launch-port R is recorded.  A horizontal chord is the same line for any R, so the
        #: number only has to lie OUTBOARD of the plasma: from 0.0 a 2.2 m inward cast reaches
        #: R 2.2 at most and drops the outboard edge (kernel run 2026-09-14, synthetic
        #: R0 1.85 / a 0.45 / kappa 1.65 on the EAST box: the mid-plane chord keeps 0.80 m of
        #: 0.90 m, n_e line -4.9 %, Faraday -3.8 %; 3.0 equals 2.5 to 1e-4).  The value is
        #: `EFIT_POINT_GUI_v5.m:658` `rpol=11*2.5` (also :968), which the retired card (kernel
        #: 71c7cef `first_point.r`) and the pre-facts browser preset carried.  ★In EFIT itself
        #: `rpol` is inert: it is only the pivot of `zzpol = zpol - 0.0*(rrpol - rpol)*sin(thetapol)`
        #: (kefit bundle `active/point/efit_w_pf/efitbuild/efitdu.f:18015`, the tilt multiplied
        #: out) and the integration grid is hard-coded `rrpol = 1.35 .. 2.55` (:18012).
        "point_chord_origin_r": 2.5,
        "ui": {"r0": {"value": 1.85}, "z0": {"value": 0}, "a": {"value": 0.45},
               "kappa": {"value": 1.65}, "du": {"value": 0.4}, "dl": {"value": 0.5},
               "ip": {"value": 400}, "xr": {"value": 1.606}, "xz": {"value": -0.722}},
        #: wall provider key -> the limiter unit NAME this package's readers select
        #: by (`device.LIMITER_OPERATIONAL`, the `recon_rs` limiter aliases).  The
        #: manifest default goes first; only providers named here are carried.
        #: ★2026-09-13: the default is `base` again (efit_w_pf removed with est2)
        "limiter_units": {"base": "base", "m093060": "m-file"},
        #: the operational namelist whose PF-channel array (`bitfc`, EFIT fcoil order) is
        #: carried onto the PF channels.  ★2026-09-13: its est2-ordered probe / loop arrays
        #: are gone from fydoc (est2 removed), so nothing attaches to magnetics channels
        "channel_fit": {"namelist": "efit_w_pf_channel_fit", "pf_bit_error": "bitfc"},
        "pf_channels": {"namelist": "gui_v5_pf_channels",
                        "fields": {"turns": "turn", "efit_index": "fcoil_channel",
                                   #: ★2026-09-15: the tree node each channel is read from (GUI_v5 `Rog_PF`)
                                   "fylite:mds_node": "rogowski_node"}},
        #: ★★R-S1 / R-S2 (user rulings 2026-09-13): shipped EAST data is resolved BY SHOT at
        #: use time.  These IDS are chosen per request — every static provider of theirs is
        #: converted here, once (`east_resolution`) — and the runtime's rule
        #: (`fylite_runtime::device_resolve`) picks among the converted groups.
        "resolved_ids": ("magnetics", "wall"),
        #: the document keys each resolved IDS owns, i.e. what a resolution writes over the card
        "owned": {"magnetics": ("magnetics", "_basis"), "wall": ("wall",)},
        "fixed": {"pf_active": (
            "deck/Luo cross-sections (`yu`) paired by rectangle centre with the `base` electrical "
            "set (user ruling 2026-09-13) — one converted set; a pf_active provider is not a "
            "per-request choice")},
        #: ★2026-09-13 (measurement-chain ruling): which magnetics provider a measurement gets is
        #: the fydoc manifest's `measurement_chains` table and each provider's `measurement_chain`,
        #: read by the runtime — no provider table here.
    },
}

#: Optional per-entry fields, read BY KEY when the A-Box carries them and
#: otherwise declared absent.  Output key -> accepted source spellings; a
#: `{value, unit, …}` wrapper is unwrapped (fydoc writes `dev:powerMax` so).
_LH_OPTIONAL = {"fylite:max_power": ("fylite:max_power", "dev:powerMax", "max_power", "power_max"),
                "fylite:n_parallel": ("fylite:n_parallel", "dev:nParallelRange", "n_parallel")}
_EC_OPTIONAL = {"mode": ("mode",),
                "fylite:max_power": ("fylite:max_power", "dev:powerMax", "max_power", "power_max")}
_CHANNEL_OPTIONAL = ("length", "weight", "bit_error")
_PF_CHANNEL_OPTIONAL = ("turns", "efit_index", "bit_error")
#: pf_passive loop-name prefix -> the document's passive group
_PASSIVE_GROUPS = {"VV_INNER": "vessel", "VV_OUTER": "outer_shell", "PLATE": "passive_plates"}


def _provider_file(dev_dir: pathlib.Path, manifest: dict, ids: str, key: str) -> pathlib.Path:
    spec = ((manifest.get("providers") or {}).get(ids) or {}).get("available") or {}
    rel = (spec.get(key) or {}).get("path")
    p = _pick(_abox(dev_dir), rel) if rel else None
    if p is None:
        raise SystemExit(f"{dev_dir.name}: manifest has no `providers.{ids}.available.{key}` "
                         f"file in the A-Box (path {rel!r})")
    return p


def _binding_file(dev_dir: pathlib.Path, manifest: dict, ids: str) -> pathlib.Path | None:
    mds = (manifest.get("bindings") or {}).get("mdsplus") or {}
    name = (mds.get("ids") or {}).get(ids)
    return _pick(_abox(dev_dir), f"{mds.get('root', '')}/{name}") if name else None


_LINK = re.compile(r"^\s*(\w+)\s*:\s*DATA\(\s*(\\[\w:]+)\s*\)")


def _link_node(link) -> tuple[str, str] | None:
    """``east:DATA(\\FOCS4 )*1000`` -> ``("east", "\\FOCS4")``; anything else None."""
    if isinstance(link, dict):
        link = link.get("$link")
    m = _LINK.match(link) if isinstance(link, str) else None
    return (m.group(1), m.group(2)) if m else None


def _first(entry: dict, names) -> object:
    v = next((entry[n] for n in names if entry.get(n) is not None), None)
    return v["value"] if isinstance(v, dict) and "value" in v else v


def _one_rect(coil: dict) -> dict:
    els = _elements(coil)
    if len(els) != 1:
        raise SystemExit(f"pf_active coil {coil.get('name')!r}: expected one rectangle, got {len(els)}")
    return els[0]["geometry"]["rectangle"]


def _by_centre(rect: dict, coils: list[dict], what: str) -> int:
    hits = [i for i, c in enumerate(coils)
            if abs(_one_rect(c)["r"] - rect["r"]) < CENTRE_TOL_M
            and abs(_one_rect(c)["z"] - rect["z"]) < CENTRE_TOL_M]
    if len(hits) != 1:
        raise SystemExit(f"{what}: {len(hits)} coils centred at "
                         f"(r={rect['r']}, z={rect['z']}) — pairing by centre needs exactly one")
    return hits[0]


def _turns_geometry(elements: list[dict]) -> float:
    """``Σ 2π r N² / (w h)`` over rectangles — the circuit model's R = η·this."""
    return sum(2.0 * math.pi * _rect_of(e)["r"] * float(e.get("turns_with_sign") or 0.0) ** 2
               / (_rect_of(e)["width"] * _rect_of(e)["height"]) for e in elements)


def _rect_of(e: dict) -> dict:
    return e["geometry"]["rectangle"]


def _pf_resistivity_uohm_m(coils: list[dict]) -> float:
    """η [μΩ·m] the provider's own `resistance` values were derived from.

    Recovered per coil on that provider's own rectangles; one value (to 1e-3)
    or refused, then given to six figures — the resistances carry no more.
    """
    vals = [float(c["resistance"]) / _turns_geometry(_elements(c)) * 1e6
            for c in coils if c.get("resistance") is not None]
    if not vals:
        raise SystemExit("EAST pf_active: the electrical provider states no `resistance`")
    if max(vals) - min(vals) > 1e-3 * max(vals):
        raise SystemExit(f"EAST pf_active: the resistances imply different resistivities {vals}")
    return float(f"{sum(vals) / len(vals):.6g}")


def east_pf_active(geo: dict, ele: dict, geo_src: str, ele_src: str):
    """``(pf_active, pf_channel_elements)`` — deck geometry, base electrics, by centre.

    ★Output element order is the DECK order (the geometry provider's non-fast
    coils, which is what base `circuit[].element_weight[].element_index`
    counts), grouped into the 12 BRSP channels as the circuit states them, then
    the fast coils (`function` = b_field_fb) from the electrical provider.
    ★★`supply[i]` pairs with element i — the readers (`case.rs` breakdown,
    `pulse.channel_limits`) index it by element position and only check the
    length — so each supply is attached to its coil by name (`PS_<coil>`) after
    the coil was found by centre; a list copied in fydoc order would pass the
    length check and mis-pair every limit past the third element.
    ★The index↔deck-element pairing is checked against physics, not list order:
    each channel's measured weights must match the turns share of the elements
    it names (44:204 of a 248-turn pair is 0.177; the map says 0.175).
    """
    ecoils = list(ele.get("coil") or [])
    deck = [c for c in (geo.get("coil") or []) if not c.get("function")]
    circuits = ele.get("circuit") or []
    if not circuits:
        raise SystemExit("EAST pf_active: the electrical provider carries no `circuit[]`")
    eta = _pf_resistivity_uohm_m(ecoils)
    supplies = {s["name"]: s for s in ele.get("supply") or []}
    if len(supplies) != len(ele.get("supply") or []):
        raise SystemExit("EAST pf_active: supply names are not unique")

    def element_for(k: int):
        rect = _one_rect(deck[k])
        j = _by_centre(rect, ecoils, f"deck element {k}")
        ec = ecoils[j]
        if ec.get("function"):
            raise SystemExit(f"deck element {k} pairs with fast coil {ec.get('name')!r}")
        tw = _elements(ec)[0].get("turns_with_sign")
        el = {"geometry": {"geometry_type": "rectangle", "rectangle": dict(rect)},
              "fylite:a1": 0.0, "fylite:a2": 90.0}
        if tw is not None:
            el["turns_with_sign"] = tw
        el["fylite:name"] = str(ec["name"])
        return el, ec

    coils, supply, flat_of, used = [], [], {}, []
    for ch in circuits:
        ws = ch.get("element_weight") or []
        built = [(int(w["element_index"]), float(w["weight"])) + element_for(int(w["element_index"]))
                 for w in ws]
        total = sum(abs(e.get("turns_with_sign") or 0.0) for _, _, e, _ in built)
        for k, w, e, ec in built:
            share = abs(e.get("turns_with_sign") or 0.0) / total if total else float("nan")
            if not abs(w - share) < 0.01:
                raise SystemExit(
                    f"circuit {ch.get('name')}: element_index {k} (= {e['fylite:name']} by centre) "
                    f"has weight {w} but a turns share of {share:.4f} — the index does not "
                    f"count the deck elements this converter pairs it with")
        entry = {"name": str(ch["name"])}
        for key in _PF_CHANNEL_OPTIONAL:
            if ch.get(key) is not None:
                entry[key] = ch[key]
        #: ★user ruling 2026-09-13: R is RECOMPUTED on the rectangles this document
        #: carries (deck/Luo), from the η the provider's values were derived from —
        #: copying the provider's R (Guo cross-sections) would imply η 0.014–0.016
        entry["resistance"] = eta * 1e-6 * _turns_geometry([e for _, _, e, _ in built])
        entry["element"] = []
        for k, w, e, ec in built:
            if k in flat_of:
                raise SystemExit(f"deck element {k} is driven by two circuits")
            flat_of[k] = len(used)
            used.append(k)
            entry["element"].append(e)
            s = supplies.get(f"PS_{ec['name']}")
            if s is None:
                raise SystemExit(f"no supply PS_{ec['name']} for coil {ec['name']}")
            supply.append(dict(s))
        coils.append(entry)
    if sorted(used) != list(range(len(deck))):
        raise SystemExit(f"circuits cover deck elements {sorted(used)}, "
                         f"the geometry provider has {len(deck)}")
    for ec in ecoils:
        if not ec.get("function"):
            continue
        entry = {"name": str(ec["name"]), "function": [dict(f) for f in ec["function"]]}
        if ec.get("resistance") is not None:
            entry["resistance"] = float(ec["resistance"])
        els = _elements(ec)
        for e in els:
            e["fylite:name"] = str(ec["name"])
        entry["element"] = els
        coils.append(entry)
    channel_elements = [
        [{"element": flat_of[int(w["element_index"])], "weight": float(w["weight"])}
         for w in ch["element_weight"]] for ch in circuits]
    out = {"@type": "fyo:pf_active",
           "fylite:source": {"geometry": geo_src, "electrical": ele_src},
           "fylite:pairing": ("element rectangles from the geometry provider in deck order; "
                              "turns, fast coils, supplies and the BRSP circuit from the "
                              "electrical provider, each paired to its deck element by "
                              "rectangle centre. `supply[i]` drives element i."),
           "fylite:resistance_note": (
               f"PF channel `resistance` is RECOMPUTED on the cross-sections this document "
               f"carries: R = η·Σ2πr·N²/(w·h) over the channel's elements, η = {eta} μΩ·m "
               f"recovered from the electrical provider's own `resistance` on its own "
               f"geometry (user ruling 2026-09-13). Fast coils keep the provider's value: "
               f"their geometry is that provider's, so the two already agree."),
           "coil": coils, "supply": supply}
    return out, channel_elements


def _probe_entries(entries, *, angle_deg: bool) -> list[dict]:
    out = []
    for c in entries or []:
        pos = c.get("position")
        p = pos[0] if isinstance(pos, list) and pos else pos
        if not isinstance(p, dict):
            raise SystemExit(f"magnetics channel {c.get('name')!r} carries no position")
        item = {"name": str(c["name"]), "position": [{"r": float(p["r"]), "z": float(p["z"])}]}
        if c.get("poloidal_angle") is not None:
            item["poloidal_angle"] = float(c["poloidal_angle"])
            if angle_deg:
                item["fylite:angle_deg"] = math.degrees(float(c["poloidal_angle"]))
        for key in _CHANNEL_OPTIONAL:
            if c.get(key) is not None:
                item[key] = float(c[key])
        out.append(item)
    return out


def east_magnetics(doc: dict, pcs: dict | None, src: str, pcs_src: str | None,
                   provider: str, chain: str | None) -> dict:
    """The magnetics group of ONE provider.  ★It names that provider (`fylite:provider`)
    and the measurement chain the manifest gives it (`measurement_chain`) — which is what a
    measurement's own declaration is held against (the pairing refusal: two chains are never
    paired).  A provider the manifest gives no chain carries none."""
    probes = _probe_entries(doc.get("b_field_pol_probe"), angle_deg=True)
    loops = _probe_entries(doc.get("flux_loop"), angle_deg=False)
    out = {"@type": "fyo:magnetics", "fylite:source": src, "fylite:provider": provider}
    if chain:
        out["measurement_chain"] = chain
    out.update({"b_field_pol_probe": probes, "flux_loop": loops})
    absent = {k: f"the magnetics provider carries no per-channel `{k}`"
              for k in _CHANNEL_OPTIONAL
              if not any(k in c for c in (*probes, *loops))}
    if absent:
        out["fylite:absent"] = absent
    if pcs is not None:
        out["pcs"] = {"fylite:source": pcs_src, "b_field_pol_probe": [
            {"name": str(c["name"]),
             "position": {"r": float(c["position"][0]["r"]), "z": float(c["position"][0]["z"])},
             "angle": math.degrees(float(c["poloidal_angle"]))}
            for c in pcs.get("b_field_pol_probe") or []]}
    return out


def _oblique_rect(geom: dict) -> tuple[float, float, float, float, float, float]:
    """DD ``oblique`` -> efund ``(r, z, w, h, a1, a2)`` [m, deg].

    ``a1 = alpha``; ``a2`` is the side angle efund measures from the w edge,
    ``beta - alpha + 90`` (an upright rectangle is alpha = beta = 0 -> 0 / 90).
    """
    o = geom.get("oblique")
    if not isinstance(o, dict):
        raise SystemExit(f"pf_passive element without `oblique` geometry: {sorted(geom)}")
    a, b = math.degrees(float(o["alpha"])), math.degrees(float(o["beta"]))
    return (float(o["r"]), float(o["z"]), float(o["length_alpha"]),
            float(o["length_beta"]), a, b - a + 90.0)


def east_pf_passive(doc: dict, src: str):
    """``(pf_passive, vessel_units)`` — loop[] regrouped into the reader's three groups.

    Resistivity Ω·m -> μΩ·m (×1e6).  One resistivity per group, or refused.
    """
    rows: dict[str, list] = {}
    eta: dict[str, set] = {}
    for loop in doc.get("loop") or []:
        prefix = str(loop["name"]).rsplit("_", 1)[0]
        group = _PASSIVE_GROUPS.get(prefix)
        if group is None:
            raise SystemExit(f"pf_passive loop {loop['name']!r}: no group for prefix {prefix!r}")
        for el in loop.get("element") or []:
            rows.setdefault(group, []).append(_oblique_rect(el.get("geometry") or {}))
        eta.setdefault(group, set()).add(float(loop["resistivity"]) * 1e6)
    out = {"@type": "fyo:pf_passive", "fylite:source": src}
    for group in _PASSIVE_GROUPS.values():
        if group not in rows:
            continue
        if len(eta[group]) != 1:
            raise SystemExit(f"pf_passive {group}: resistivities differ {sorted(eta[group])}")
        out[group] = {"resistivity_uohm_m": eta[group].pop()}
        if group != "vessel":
            out[group]["element"] = [list(r) for r in rows[group]]
    out.setdefault("vessel", {})["fylite:geometry"] = "wall.description_2d[0].vessel.unit"
    vessel_units = [{"element": [{"geometry": {"geometry_type": "rectangle",
                                               "rectangle": {"r": r, "z": z, "width": w, "height": h}},
                                  "fylite:a1": a1, "fylite:a2": a2}]}
                    for r, z, w, h, a1, a2 in rows.get("vessel", [])]
    return out, vessel_units


def generic_pf_passive(doc: dict, src: str, vessel_group: str | None = None):
    """``(pf_passive, vessel_units)`` — loop[] grouped by its own name prefix.

    ★Why this exists beside :func:`east_pf_passive`: that one maps three FIXED prefixes
    (``VV_INNER`` / ``VV_OUTER`` / ``PLATE``) onto the three group names EAST's readers
    know, and REFUSES any prefix outside them.  ITER's passive set has fourteen groups
    (two vessel shells, the OTS ring, two divertor rails, four cryostat ribs, two thermal
    shields, three port inner shells), so that map cannot be stretched — the group name
    here is simply the loop prefix, lowercased.

    ★``vessel_group`` names the ONE group that also travels as
    ``wall.description_2d[0].vessel.unit``.  That path is not decoration: the kernel's
    ``passive_set`` resolves the group names ``inner_shell`` / ``vessel`` from it, while
    every other name is looked up under ``pf_passive/<group>``.  Naming it here is what
    makes ``passive: "inner_shell"`` (the door's default) mean something on this machine.

    Resistivity Ω·m -> μΩ·m (×1e6).  One resistivity per group, or refused.
    """
    rows: dict[str, list] = {}
    eta: dict[str, set] = {}
    order: list[str] = []
    for loop in doc.get("loop") or []:
        group = str(loop["name"]).rsplit("_", 1)[0].lower()
        if group not in rows:
            order.append(group)
        for el in loop.get("element") or []:
            rows.setdefault(group, []).append(_oblique_rect(el.get("geometry") or {}))
        eta.setdefault(group, set()).add(float(loop["resistivity"]) * 1e6)
    out = {"@type": "fyo:pf_passive", "fylite:source": src}
    vessel_key = (vessel_group or "").lower() or None
    for group in order:
        if len(eta[group]) != 1:
            raise SystemExit(f"pf_passive {group}: resistivities differ {sorted(eta[group])}")
        out[group] = {"resistivity_uohm_m": eta[group].pop(),
                      "element": [list(r) for r in rows[group]]}
    if vessel_key is not None:
        if vessel_key not in rows:
            raise SystemExit(f"pf_passive: vessel_group {vessel_key!r} is not one of {sorted(rows)}")
        #: ★the same elements reached two ways, on purpose — see the docstring.  The
        #: group keeps its `element` list (so `passive: "vv_inner"` works), and the
        #: vessel units carry it too (so `passive: "inner_shell"` works).
        out["vessel"] = {"resistivity_uohm_m": out[vessel_key]["resistivity_uohm_m"],
                         "fylite:geometry": "wall.description_2d[0].vessel.unit",
                         "fylite:group": vessel_key}
        vessel_units = [{"element": [{"geometry": {"geometry_type": "rectangle",
                                                   "rectangle": {"r": r, "z": z, "width": w, "height": h}},
                                      "fylite:a1": a1, "fylite:a2": a2}]}
                        for r, z, w, h, a1, a2 in rows[vessel_key]]
    else:
        vessel_units = []
    return out, vessel_units


#: the group a machine's `pf_passive` sends to `wall…vessel.unit` — the one the kernel's
#: `inner_shell` / `vessel` door names resolve to.  A machine not listed sends none.
VESSEL_GROUP = {"iter": "vv_inner"}


def _namelists(op: dict | None) -> dict:
    """``{namelist: {parameter: value | values}}`` from an operational A-Box."""
    return {str(nl["name"]): {str(p["name"]): p["values"] if "values" in p else p.get("value")
                              for p in nl.get("parameter") or []}
            for nl in (op or {}).get("namelist") or []}


def east_channel_fit(doc: dict, op: dict | None, op_src: str, prog: dict) -> list[str]:
    """Per-PF-channel fit settings -> ``turns`` / ``efit_index`` / ``bit_error``.

    The operational A-Box states them as arrays in PF order; the readers
    (`device.PF_TURNS` · `PF_EFIT_ORDER` · `BITFC`) read them per channel.  Paired BY
    INDEX in channel (BRSP) order, and only when every length matches.  Returns the
    namelists it consumed.

    ★2026-09-13 (measurement-chain ruling, est2 removed): the per-PROBE / per-LOOP weight
    and bit-error arrays that used to attach here were in the est2 channel order and are
    gone from fydoc; a magnetics group states `weight` / `bit_error` absent (east_magnetics).
    ``pf_active`` is therefore the same for every magnetics provider.
    """
    nls, used = _namelists(op), []
    cf, pc = prog["channel_fit"], prog["pf_channels"]
    fit = nls.get(cf["namelist"])
    if fit is not None:
        used.append(cf["namelist"])

    channels = [c for c in doc["pf_active"]["coil"] if not c.get("function")]
    pf_absent = {}
    pfn = nls.get(pc["namelist"])
    arrays = {dst: (pfn or {}).get(src) for dst, src in pc["fields"].items()}
    if fit is not None:
        arrays["bit_error"] = fit.get(cf["pf_bit_error"])
    for dst, vals in arrays.items():
        if isinstance(vals, list) and len(vals) == len(channels):
            for c, v in zip(channels, vals):
                c[dst] = (int(v) if dst in ("turns", "efit_index")
                          else str(v) if dst == "fylite:mds_node" else float(v))
        else:
            pf_absent[dst] = "the operational A-Box states no per-channel array of this length"
    if pfn is not None:
        used.append(pc["namelist"])
    if "bit_error" in arrays and "bit_error" not in pf_absent:
        #: ★named divergence: fydoc states bitfc in EFIT fcoil order, and it is
        #: carried by list position — as the retired card did, which is what
        #: `device.BITFC` hands on unchanged (no reader re-orders it)
        doc["pf_active"]["fylite:bit_error_note"] = (
            f"`bit_error` is {cf['namelist']}.{cf['pf_bit_error']} by LIST POSITION; the "
            "A-Box states that array in EFIT fcoil order (see `efit_index`), not BRSP order")
    if pf_absent:
        doc["pf_active"]["fylite:absent"] = pf_absent
    return used


def east_operational(doc: dict, src: str, carried: dict | None = None) -> dict:
    out = {"@type": "fylite:OperationalSettings", "fylite:source": src}
    if doc.get("description"):
        out["note"] = doc["description"]
    if doc.get("source"):
        out["source"] = doc["source"]
    gate = doc.get("probe_gate")
    if isinstance(gate, dict):
        out["probe_gate"] = {"min_tesla": float(gate["b_field_min"]),
                             "max_tesla": float(gate["b_field_max"])}
        if gate.get("description"):
            out["probe_gate"]["note"] = gate["description"]
    for nl in doc.get("namelist") or []:
        name = str(nl["name"])
        if carried and name in carried:
            continue                  #: stated once: on the channels it indexes
        if name in out:
            raise SystemExit(f"operational namelist {name!r} collides with a document key")
        block = {}
        for p in nl.get("parameter") or []:
            if ("value" in p) == ("values" in p):
                raise SystemExit(f"namelist {name} parameter {p.get('name')!r}: "
                                 "needs exactly one of value / values")
            block[str(p["name"])] = p["value"] if "value" in p else list(p["values"])
        out[name] = block
    if carried:
        out["fylite:carried_on_channels"] = dict(carried)
    return out


def east_chords(ids: str, doc: dict, bind: dict | None, src: str, prefix: str) -> dict:
    """POINT chords: the channels EFIT fits, with θ from the two points.

    ★`name` is the MDSplus node the binding reads (that is what the readers use
    it as).  Paired by chord NUMBER (`POINT<k>` ↔ `\\POINT_N<k>`), not by list
    position — the binding lists 14 entries against 16 static channels.  With no
    binding for the group the upstream channel name stays, and says so.
    """
    nodes = {}
    for b in (bind or {}).get("channel") or []:
        for v in b.values():
            got = _link_node(((v or {}).get("data") if isinstance(v, dict) else None))
            m = re.fullmatch(r"\\POINT_[A-Z](\d+)", got[1], re.I) if got else None
            if m:
                nodes[int(m.group(1))] = got[1].lstrip("\\")
    chans = []
    for c in doc.get("channel") or []:
        m = re.fullmatch(rf"{prefix}(\d+)", str(c.get("name")))
        if not m:
            continue
        los = c["line_of_sight"]
        p1, p2 = los["first_point"], los["second_point"]
        item = {"name": nodes.get(int(m.group(1)), str(c["name"])),
                "line_of_sight": {
                    "first_point": {"r": float(p1["r"]), "z": float(p1["z"])},
                    "second_point": {"r": float(p2["r"]), "z": float(p2["z"])},
                    "theta": math.atan2(float(p2["z"]) - float(p1["z"]),
                                        float(p2["r"]) - float(p1["r"]))}}
        chans.append(item)
    out = {"@type": f"fyo:{ids}", "fylite:source": src, "channel": chans}
    if bind is None:
        out["fylite:absent"] = {"mds_node_names": (
            f"the A-Box has no MDSplus binding for {ids}; channel names are the "
            "upstream channel names, not node names")}
    return out


def east_hcd(lh: dict | None, ic: dict | None, ec: dict | None, rel: dict) -> dict:
    """Static H&CD fields.  Port letters, node names and IC level / source power /
    frequency range have no production reader and are not carried (ruling)."""
    out = {}

    def entries(doc, key, optional):
        items, absent = [], {}
        for a in doc.get(key) or []:
            item = {"name": str(a["name"])}
            if a.get("frequency") is not None:
                item["frequency"] = float(a["frequency"])
            for dst, names in optional.items():
                v = _first(a, names)
                if v is not None:
                    item[dst] = v
            items.append(item)
        for dst in optional:
            if not any(dst in i for i in items):
                absent[dst] = f"not carried as data by the A-Box {key}[] entries"
        return items, absent

    for ids, doc, key, opt in (("lh_antennas", lh, "antenna", _LH_OPTIONAL),
                               ("ic_antennas", ic, "antenna", {}),
                               ("ec_launchers", ec, "beam", _EC_OPTIONAL)):
        if doc is None:
            continue
        items, absent = entries(doc, key, opt)
        out[ids] = {"@type": f"fyo:{ids}", "fylite:source": rel[ids], key: items}
        if absent:
            out[ids]["fylite:absent"] = absent
    #: ★the EC steering RANGE (a capability, not a setting): the A-Box carries it
    #: only as the eastwiki line its `ec_launchers` page quotes verbatim in
    #: `provenance.comment` — copied as that prose, never parsed into numbers
    if ec is not None and "ec_launchers" in out:
        line = next((m.group(1).strip() for t in _strings((ec.get("provenance") or {}).get("comment"))
                     for m in [re.search(r"injection angle range of wave beam:\s*([^\n]+)", t, re.I)]
                     if m), None)
        if line:
            out["ec_launchers"]["fylite:steering_range_note"] = line
            out["ec_launchers"]["fylite:steering_range_source"] = (
                f"{rel['ec_launchers']} provenance.comment (eastwiki, verbatim)")
    return out


def east_data_source(dev_dir: pathlib.Path, manifest: dict) -> dict:
    """Tree and node names, read off the MDSplus bindings.

    ★No server address: which host serves the tree is a DEPLOYMENT setting
    (ruling 2026-09-13), and the binding prefix is a local rig anyway.
    """
    mds = (manifest.get("bindings") or {}).get("mdsplus") or {}
    trees = mds.get("trees") or {}
    out: dict = {}
    absent = {"server": "deployment setting, not a device fact (ruling 2026-09-13)"}

    def links(ids, pick):
        p = _binding_file(dev_dir, manifest, ids)
        return _link_node(pick(_load(p))) if p else None

    tf = links("tf", lambda d: d["coil"][0]["current"]["data"])
    if tf and tf[0] in trees:
        out["tree"] = tf[0]
    pf = links("pf_active", lambda d: d["coil"][0]["current"]["data"])
    if pf and pf[0] in trees:
        out["pcs_tree"] = pf[0]
    ip = links("magnetics", lambda d: d["ip"][0]["data"])
    if ip and ip[0] == out.get("tree"):
        out["ip_node"] = ip[1]
    else:
        absent["ip_node"] = (
            f"the default magnetics binding reads Ip from {ip[1] if ip else None} in tree "
            f"{ip[0] if ip else None!r}, not from the main tree {out.get('tree')!r}; the "
            "main-tree Rogowski nodes (IPG/IPE/IPM/IPV1) are listed as alternates only, "
            "and which one is not stated")
    #: the toroidal-field node is era-dependent; the binding names one era's node
    #: and the read rule names the current (open-ended) one
    rule = next((r for r in mds.get("read_rules") or [] if r.get("id") == "tf-focs-node-era"), None)
    current = [c for c in ((rule or {}).get("rule") or {}).get("candidates") or []
               if isinstance(c.get("shots"), list) and c["shots"][1] is None]
    if len(current) == 1:
        out["btor_node"] = current[0]["node"]
        out["fylite:btor_node_note"] = ("read rule tf-focs-node-era, open-ended era "
                                        f"(shots >= {current[0]['shots'][0]})")
    elif tf:
        out["btor_node"] = tf[1]
    out["fylite:absent"] = absent
    return {"mdsplus": out}


def _strings(node):
    """Every string inside a JSON node (depth-first)."""
    if isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, str):
        yield node


def _east_basis(manifest: dict, manifest_path: pathlib.Path, mag: dict | None, key: str) -> str:
    """`_basis`: the A-Box epoch AND the selected magnetics provider with its measurement chain.

    ★Both are read off the manifest and the provider page (`provenance.provider`), never
    written here: a provider switch must change this string, and a provider the manifest
    gives no chain leaves the chain unstated rather than inherited.
    """
    epoch = (manifest.get("epochs") or [{}])[0].get("id", "?")
    out = f"{_cite(manifest_path.parent)} (epoch {epoch})"
    spec = ((((manifest.get("providers") or {}).get("magnetics") or {}).get("available") or {})
            .get(key) or {})
    chain = spec.get("measurement_chain")
    prov = (mag.get("provenance") or {}).get("provider") if mag else None
    parts = [x for x in (prov, f"measurement chain {chain}" if chain else None) if x]
    return out + (f"; magnetics provider {key}: " + " — ".join(parts) if parts else "")


def _east_dd_version(manifest: dict, loaded: list) -> tuple[str, str]:
    """`_dd_version`: the most specific DD version upstream states.

    The manifest says only `imas/4`; the A-Box pages converted into this document
    carry `_dd_version` themselves (e.g. "4.1.1").  Taken when they agree with one
    another and with the manifest's major version; else the manifest's.
    Returns (version, where it was read).
    """
    major = str(manifest.get("dd_source", "imas/4")).split("/")[-1]
    seen = {str(d["_dd_version"]) for d in loaded if isinstance(d, dict) and d.get("_dd_version")}
    if len(seen) == 1 and next(iter(seen)).split(".")[0] == major.split(".")[0]:
        return next(iter(seen)), "the A-Box pages' own `_dd_version` (manifest: dd_source " \
            f"imas/{major})"
    return major, "manifest dd_source" + (f" (pages disagree: {sorted(seen)})" if len(seen) > 1 else "")


def _east_selection(manifest: dict, providers: dict | None, prog: dict) -> dict:
    """``{ids: provider}`` for the resolved IDS of ONE build: named, else the manifest ``default``.

    ★This is not the shot rule — it only says which provider set THIS conversion is
    for.  Which set a request gets is decided at use time by the runtime
    (``device_resolve``), over the groups :func:`east_resolution` converts.
    """
    provs = manifest.get("providers") or {}
    unknown = sorted(set(providers or {}) - set(prog["resolved_ids"]))
    if unknown:
        raise SystemExit(f"EAST: {unknown} are not chosen by provider "
                         f"(resolved per request: {list(prog['resolved_ids'])})")
    out = {}
    for ids in prog["resolved_ids"]:
        spec = provs.get(ids) or {}
        name = (providers or {}).get(ids) or spec.get("default")
        avail = spec.get("available") or {}
        static = sorted(k for k, v in avail.items() if (v.get("backend") or "static") == "static")
        if name not in static:
            raise SystemExit(f"EAST {ids}: provider {name!r} is not a static provider in the manifest "
                             f"(static: {static})")
        out[ids] = name
    return out


def build_east_from_abox(fydoc: pathlib.Path, providers: dict | None = None) -> dict:
    """EAST's device document, assembled from fydoc's A-Box (see the section header).

    ``providers`` names the provider of a resolved IDS (``PROGRAM_SIDE['resolved_ids']``,
    e.g. ``{"magnetics": "east_new"}``) for the ONE conversion :func:`east_resolution` makes per
    provider; unnamed ones take the manifest's ``default``.  ★Not a request surface: which
    converted group a request gets is the runtime's rule (shot + measurement chain).
    """
    dev = "east"
    dev_dir = device_root(fydoc) / dev
    manifest, manifest_path = _manifest(dev_dir)
    if manifest is None:
        raise SystemExit(f"no EAST manifest under {fydoc}")
    files = _resolve(dev_dir, manifest)
    prog = PROGRAM_SIDE[dev]
    sel = _east_selection(manifest, providers, prog)
    files["magnetics"] = _provider_file(dev_dir, manifest, "magnetics", sel["magnetics"])
    files["wall"] = _provider_file(dev_dir, manifest, "wall", sel["wall"])
    #: the wall provider THIS build is for (its unit goes first); the others named in
    #: PROGRAM_SIDE['limiter_units'] follow as alternatives
    wall_default = sel["wall"]
    for key in prog["limiter_units"]:
        if key != wall_default and key in (((manifest.get("providers") or {}).get("wall") or {})
                                           .get("available") or {}):
            files[f"wall:{key}"] = _provider_file(dev_dir, manifest, "wall", key)
    files["pf_active:geometry"] = _provider_file(dev_dir, manifest, "pf_active",
                                                 EAST_PF_GEOMETRY_PROVIDER)
    files["pf_active:electrical"] = _provider_file(dev_dir, manifest, "pf_active",
                                                   EAST_PF_ELECTRICAL_PROVIDER)
    files.pop("pf_active", None)
    files["magnetics:pcs"] = _provider_file(dev_dir, manifest, "magnetics", "pcs")
    for ids in ("interferometer", "polarimeter"):
        b = _binding_file(dev_dir, manifest, ids)
        if b is not None:
            files[f"{ids}:binding"] = b
    rel = {k: str(v.relative_to(fydoc)) for k, v in files.items()}
    load = lambda k: _load(files[k]) if k in files else None  # noqa: E731
    dd_version, dd_where = _east_dd_version(manifest, [load(k) for k in files])

    doc: dict = {
        "@context": dict(CONTEXT),
        "@id": f"fylite:device/{dev}",
        "@type": "fyo:DeviceDescription",
        "_dd_version": dd_version,
        "_machine": str(manifest.get("device", dev.upper())),
        "_basis": _east_basis(manifest, manifest_path, load("magnetics"), sel["magnetics"]),
        "provenance": {
            "dd_version_source": dd_where,
            "generator": "tools/abox-to-facts.py (build_east_from_abox)",
            "source": _cite(manifest_path),
            "identity_iri": manifest.get("identity_iri"),
            "source_files": dict(sorted(rel.items())),
            "note": ("Converted, not authored: every device value is copied from the file "
                     "named in `fylite:source`; a field the A-Box does not carry is named "
                     "under `fylite:absent`.  `solver_dims`, `default_grid`, "
                     "`polarimeter.faraday_constant`, `polarimeter.baseline` and `fylite:ui` "
                     "are program-side values "
                     "(PROGRAM_SIDE in the generator), not device facts."),
        },
    }
    doc["data_source"] = east_data_source(dev_dir, manifest)
    mag_spec = (((manifest.get("providers") or {}).get("magnetics") or {}).get("available")
                or {}).get(sel["magnetics"]) or {}
    doc["magnetics"] = east_magnetics(load("magnetics"), load("magnetics:pcs"),
                                      rel["magnetics"], rel["magnetics:pcs"],
                                      sel["magnetics"], mag_spec.get("measurement_chain"))
    doc["pf_active"], doc["pf_channel_elements"] = east_pf_active(
        load("pf_active:geometry"), load("pf_active:electrical"),
        rel["pf_active:geometry"], rel["pf_active:electrical"])
    doc["wall"] = wall(load("wall"), rel["wall"])
    doc["wall"].pop("fylite:upstream", None)
    units = doc["wall"]["description_2d"][0]["limiter"]["unit"]
    if wall_default not in prog["limiter_units"]:
        raise SystemExit(f"EAST wall: provider {wall_default!r} has no "
                         f"reader-facing unit name in PROGRAM_SIDE['limiter_units']")
    for u in units:
        #: the unit is named by the provider that was selected for it; the
        #: manifest default is the operational contour and goes first
        u["fylite:upstream_name"] = u["name"]
        u["name"] = prog["limiter_units"][wall_default]
        u["fylite:provider"] = wall_default
        u["fylite:operational"] = True
    for key, name in prog["limiter_units"].items():
        if f"wall:{key}" not in files:
            continue
        for u in wall(load(f"wall:{key}"), rel[f"wall:{key}"])["description_2d"][0]["limiter"]["unit"]:
            u["fylite:upstream_name"] = u["name"]
            u["name"] = name
            u["fylite:provider"] = key
            u["fylite:source"] = rel[f"wall:{key}"]
            units.append(u)
    if "pf_passive" in files:
        doc["pf_passive"], vessel = east_pf_passive(load("pf_passive"), rel["pf_passive"])
        doc["wall"]["description_2d"][0]["vessel"] = {"unit": vessel}
        doc["fylite:vessel_resistivity_uohm_m"] = doc["pf_passive"]["vessel"]["resistivity_uohm_m"]
    doc.update(east_hcd(load("lh_antennas"), load("ic_antennas"), load("ec_launchers"), rel))
    for ids in ("interferometer", "polarimeter"):
        if ids in files:
            doc[ids] = east_chords(ids, load(ids), load(f"{ids}:binding"), rel[ids],
                                   prog["point_chord_prefix"])
            #: the cast origin is program-side (PROGRAM_SIDE['point_chord_origin_r'] says why);
            #: theta was already taken from the A-Box pair, so moving the origin along the
            #: horizontal line leaves it (and the chord) unchanged
            for c in doc[ids]["channel"]:
                c["line_of_sight"]["first_point"]["r"] = float(prog["point_chord_origin_r"])
        else:
            doc[ids] = _absent(ids, f"the A-Box resolves no {ids} file")
            doc[ids]["channel"] = []
    itf = doc["interferometer"]
    wl = {float(w["value"]) for c in (load("interferometer") or {}).get("channel") or []
          if str(c.get("name", "")).startswith(prog["point_chord_prefix"])
          for w in (c.get("wavelength") or []) if isinstance(w, dict) and "value" in w}
    if len(wl) == 1:
        itf["laser_wavelength"] = wl.pop()
    else:
        itf.setdefault("fylite:absent", {})["laser_wavelength"] = (
            "the A-Box interferometer carries no single channel wavelength for the POINT chords")
    pol = doc["polarimeter"]
    pol["faraday_constant"] = prog["faraday_constant"]
    #: program-side (PROGRAM_SIDE['point_baseline'] says why); one source, so the A-Box is not consulted
    pol["baseline"] = {k: float(v) for k, v in prog["point_baseline"].items()}
    if "operational" in files:
        used = east_channel_fit(doc, load("operational"), rel["operational"], prog)
        carried = {n: ("pf_active.coil[].bit_error"
                       if n == prog["channel_fit"]["namelist"] else
                       "pf_active.coil[].turns / efit_index") for n in used}
        doc["operational"] = east_operational(load("operational"), rel["operational"], carried)
    else:
        doc["operational"] = {"@type": "fylite:OperationalSettings",
                              "fylite:absent": "the A-Box resolves no operational file"}
    tf = load("tf")
    doc["machine"] = machine_block(doc["_machine"], tf, units, None)
    doc["machine"]["default_grid"] = dict(
        prog["default_grid"], note="program-side solver box (PROGRAM_SIDE), not a device fact")
    #: ★★the machine reference radius is its OWN recorded fact, not `tf.r0`: fydoc
    #: records both (tf `r0` 1.7 · `dev:rCentre` 1.75, result `divergent`) and the
    #: ruling is to carry both with sources and never pick one silently
    rc = (tf or {}).get("dev:rCentre")
    if _num(rc) is None:
        raise SystemExit("EAST tf: no `dev:rCentre` — the machine reference radius is not "
                         "derived from `tf.r0` (ruling 2026-09-13); fydoc must record it")
    doc["machine"]["r_centre"] = _num(rc)
    doc["machine"]["r_centre_note"] = (
        f"{rel['tf']} `dev:rCentre` ({rc.get('dev:source')}: {rc.get('dev:locator')}); "
        "tf.r0 takes the same value (user ruling 2026-09-13) — see provenance.reference_radii")
    #: ★★user ruling 2026-09-13: tf.r0 = machine.r_centre (the card's convention), so the
    #: nominal b0 stays paired with the radius it was stated at; the other recorded
    #: radii are kept in provenance, with the reason they are not used
    #: the locator names it in prose: "efit/efitbuild/ 同名件（129×129，…）同位写 1.79999995"
    other_gfile = re.search(r"efitbuild/[^（(]*[（(](\d+×\d+)[^0-9]*?(\d+\.\d+)",
                            str(rc.get("dev:locator") or ""))
    doc["provenance"]["reference_radii"] = {
        "used": {"value": _num(rc), "for": ["machine.r_centre", "tf.r0"],
                 "source": f"{rel['tf']} dev:rCentre", "locator": rc.get("dev:locator"),
                 "why": ("user ruling 2026-09-13: tf.r0 <- machine.r_centre (the retired "
                         "card's convention), so the nominal tf.b0 "
                         f"{_num((tf or {}).get('b0'))} T stays paired with the radius it "
                         "was stated at")},
        "recorded_not_used": [
            {"value": _num((tf or {}).get("r0")), "source": f"{rel['tf']} r0",
             "why": ("fydoc's tf page value; a different reference radius from the one the "
                     "nominal b0 is paired with (fydoc marks the radii divergent)")},
        ] + ([{"value": float(other_gfile.group(2)),
               "source": (f"{rel['tf']} dev:rCentre dev:locator (prose): the other reference "
                          f"g-file efit/efitbuild/g093060.01000 ({other_gfile.group(1)}) rcentr"),
               "why": ("the two reference g-files of the same shot and time disagree; the "
                       "65×65 one (the compiled solver dimensions) is the one used")}]
             if other_gfile else [])}
    if "fylite:b0" not in doc["machine"]:
        doc["machine"]["fylite:absent"] = {"fylite:b0": "the A-Box tf carries no vacuum field"}
    if tf is not None:
        doc["tf"] = {"@type": "fyo:tf", "fylite:source": rel["tf"],
                     "r0": doc["machine"]["r_centre"],        # ruling 2026-09-13, see provenance
                     "coils_n": int(_num(tf.get("coils_n"))) if _num(tf.get("coils_n")) else None}
    doc["solver_dims"] = dict({"@type": "fylite:CompiledDimensions",
                               "note": ("编译期维度：随包 libefit.so 的数组维度，是声明不是旋钮 "
                                        "(program-side, PROGRAM_SIDE in the generator — not a "
                                        "device fact)")},
                              **prog["solver_dims"])
    doc["fylite:ui"] = json.loads(json.dumps(prog["ui"]))
    missing = [g for g in REQUIRED if g not in doc]
    assert not missing, missing
    return doc


#: machine id -> its own assembler, reached through `build()` (see the header).
ASSEMBLERS = {"east": build_east_from_abox}


def east_resolution(fydoc: pathlib.Path) -> dict:
    """EAST's ``fylite:DeviceResolution`` (user rulings R-S1 / R-S2, 2026-09-13).

    Every static provider of every resolved IDS, converted ONCE by
    :func:`build_east_from_abox` and cut to the keys that IDS owns
    (``PROGRAM_SIDE['owned']``), in both spellings — ``card`` (the YAML card Python
    reads) and ``document`` (the derived page document the runtime and the pages
    read, :func:`derive_document`).  A provider that cannot be converted into this
    document carries ``fylite:absent`` with the converter's own reason.

    ★What this does NOT hold is the rule: which group a request gets is
    ``fylite_runtime::device_resolve`` — reading ``manifest`` (the providers with their
    ``default``, ``valid_shots`` and ``measurement_chain``, and the ``measurement_chains``
    table, trimmed from fydoc's manifest).  One converter here, one rule there.
    """
    dev = "east"
    dev_dir = device_root(fydoc) / dev
    manifest, manifest_path = _manifest(dev_dir)
    prog = PROGRAM_SIDE[dev]
    provs = manifest.get("providers") or {}
    variants: dict = {}
    for ids in prog["resolved_ids"]:
        variants[ids] = {}
        for name, spec in ((provs.get(ids) or {}).get("available") or {}).items():
            if (spec.get("backend") or "static") != "static":
                continue
            try:
                one = build_east_from_abox(fydoc, providers={ids: name})
            except SystemExit as e:
                variants[ids][name] = {"fylite:absent": f"not convertible into this document: {e}"}
                continue
            #: the same values the card on disk will hold (the card is written as YAML)
            card = yaml.safe_load(yaml.dump(one, allow_unicode=True, sort_keys=False))
            page = derive_document(dev, json.loads(json.dumps(card)))
            owned = prog["owned"][ids]
            variants[ids][name] = {
                "card": {k: card[k] for k in owned if k in card},
                "document": {k: page[k] for k in owned if k in page},
                "source_files": {k: v for k, v in card["provenance"]["source_files"].items()
                                 if k == ids or k.startswith(ids + ":")},
            }
    keep = ("backend", "path", "valid_shots", "measurement_chain", "preferred")
    return {
        "@context": dict(CONTEXT),
        "@id": f"fylite:device/{dev}/resolution",
        "@type": "fylite:DeviceResolution",
        "fylite:device_id": dev,
        "fylite:note": (
            "GENERATED by tools/abox-to-facts.py (east_resolution). Resolves the EAST card BY SHOT "
            "AND MEASUREMENT CHAIN at use time (user rulings R-S1 / R-S2 and the measurement-chain "
            "ruling, 2026-09-13): the runtime's rule (fylite_runtime::device_resolve) picks a provider "
            "per IDS in `resolved_ids` from `manifest.providers` — within the requested chain "
            "(`manifest.measurement_chains`) for an IDS whose providers carry `measurement_chain`, else "
            "the shot-anchored provider covering the shot (no shot = the latest shot), else the "
            "default — and writes that provider's converted group (`variants`) over the card. The card "
            "beside this file is the no-shot resolution."),
        "manifest": {
            "source": _cite(manifest_path),
            "device": manifest.get("device"),
            "measurement_chains": manifest.get("measurement_chains") or {},
            "providers": {ids: {"default": (provs.get(ids) or {}).get("default"),
                                "available": {n: {k: s[k] for k in keep if k in s}
                                              for n, s in ((provs.get(ids) or {}).get("available")
                                                           or {}).items()}}
                          for ids in (*prog["resolved_ids"], *prog["fixed"]) if ids in provs},
        },
        "resolved_ids": list(prog["resolved_ids"]),
        "fixed": {ids: {"why": why} for ids, why in prog["fixed"].items()},
        "variants": variants,
    }


#: machine id -> its resolution-document builder (a card that resolves by shot)
RESOLUTIONS = {"east": east_resolution}


def _device_module():
    if str(ROOT / "python") not in sys.path:
        sys.path.insert(0, str(ROOT / "python"))
    from fylite import device as _device
    return _device


def resolve_card(doc: dict, resolution: dict, **request) -> dict:
    """``doc`` resolved for ``request`` (none = the no-shot resolution, R-S2) — through the
    RUNTIME's rule (``fylite.device.resolve_document`` -> ``libfylite_runtime.so``), never a
    copy of it here."""
    card = yaml.safe_load(yaml.dump(doc, allow_unicode=True, sort_keys=False))
    return _device_module().resolve_document(card, resolution, form="card", **request)["document"]


def variant_card(dev: str, fydata: pathlib.Path, doc: dict, *, shot: int | None = None,
                 measurement_chain: str | None = None,
                 resolution: dict | None = None) -> dict:
    """The card for ``--shot`` / ``--measurement-chain`` — the use-time resolution, plus what it
    was generated for (``_selection`` · ``_shot`` · ``_measurement_chain``; ``_valid_shots`` is the
    runtime's).

    ★The runtime decides everything (2026-09-13 rulings): the providers, the refusals — a gap in
    the chain, an undeclared chain, two providers of one chain covering the shot, a default that
    does not cover the shot (``strict``) — and ``_valid_shots`` (the intersection of the ranges the
    chosen providers declare; ``[N, N]`` when none declares one; date-anchored providers never
    vouch for all shots).  ``doc`` is the card built from the manifest defaults.
    """
    if dev not in RESOLUTIONS:
        raise SystemExit(f"{dev}: --shot / --measurement-chain resolve through the runtime's rule, and "
                         f"only {sorted(RESOLUTIONS)} ship a resolution document")
    res = resolution if resolution is not None else RESOLUTIONS[dev](fydata)
    dm = _device_module()
    try:
        card = resolve_card(doc, res, shot=shot, measurement_chain=measurement_chain, strict=True)
    except dm.ProviderSelectionError as e:
        raise SystemExit(f"{dev}: {e}") from None
    valid = card.pop("_valid_shots", None)
    card["_selection"] = {k: v["provider"]
                          for k, v in sorted(card["provenance"]["fylite:resolution"]["ids"].items())}
    if measurement_chain is not None:
        card["_measurement_chain"] = measurement_chain
    if shot is not None:
        card["_shot"] = shot
    if valid is not None:
        card["_valid_shots"] = valid
    return card


def write_resolution(dev: str, res: dict, out_root: pathlib.Path) -> pathlib.Path:
    d = out_root / dev
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dev}_resolution.jsonld"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=False) + "\n",
                 encoding="utf-8")
    return p


#: ★★★出处那一行**从实际拉的那棵树derive**，不写死。此前它固定印
#: `fydata/abox/device/tokamak/{dev}/`，而这次拉的是 fydoc —— 于是同一份卡片里，
#: 机读的 `_basis` / `dcterms:source` 说 fydoc，给人看的抬头说 fydata。两者矛盾时
#: 人只会读抬头，而「哪边是数据真实源头」正是本仓要靠出处回答的问题。
HEADER = """\
# {machine} device description — fyo/JSON-LD semantics over IMAS DD v4 keys.
#
# GENERATED by tools/abox-to-facts.py from
#   {source}
# Do not hand-edit: re-run the generator, then diff.
#
# Read through fylite.device.load_device, like facts/device/east/.  A group
# the upstream description does not carry is present and marked
# `fylite:absent` — declared, not defaulted, and not quietly missing.
"""


#: 一台机器可不可以进**发布出去的制品**，由两件事共同决定，两件都记在 `rights.json` 里：
#:
#:   1. **A-Box 自己声明的许可**（`declared`）——上游的事实，本仓不改写；
#:   2. **本仓的裁定**（`ruling`）——谁可以进哪一种构建。
#:
#: ★★2026-09-04 用户裁定（本仓是 ASIPP 自有数据的权属方，这一条是权属方的决定）：
#:   * fylite 构建分**内部版**与**公开版**；
#:   * **公开版不含 EAST 装置数据**——它带着一次真实放电（#137985 的实测通道电流与
#:     磁通环读数），那是运行方的数据，不随公开制品走；
#:   * 其余装置的事实源于公开文献，可打包；
#:   * **其他 NOT OPEN 数据同理**——按同一条内部 / 公开分界处理。
#:
#: 于是判据落成一句可执行的话：**公开版只带「上游没有说不可以」的那些**。
#: 上游明写 `redistributable: false` 的（ITER 的 `tf` 与 `pf_active`，权属方是
#: ITER Organization 而不是本仓）**不因本仓的裁定而放行**——那不是本仓能给的授权。
#: ★★★2026-09-04 用户裁定：**裁定收敛进 `dataset_fair.jsonld`**（fydoc 那侧的
#: `abox/static/now/dataset_fair.jsonld` 的 `dev:redistribution` 块），本文件不再持有
#: 一张 `INTERNAL_ONLY` 表。理由是许可只该有一处**可编辑的真源**：表留在这里，改一台
#: 机器的密级就要改 fylite 的代码，而那台机器的数据、它的出处、它的 FAIR 记录全都在
#: fydoc——判断与被判断的东西隔着一个仓，迟早各说各的。
#: ★fydoc 的生成器 `lit2abox.py` 已改为**把这个块带过重生成**，否则下一次重生成会静默
#: 丢掉它（见那边的注释）。
RULING_KEY = "dev:redistribution"

#: 上游逐 IDS 明说不可再分发的，公开版一律不带——与本仓的裁定无关，是第三方权属。
def _blocked_ids(fair: dict) -> dict:
    by = fair.get("license_by_ids")
    if not isinstance(by, dict):
        return {}
    return {k: v for k, v in by.items()
            if isinstance(v, dict) and v.get("redistributable") is False}


def _fair(dev_dir: pathlib.Path) -> dict | None:
    """A-Box 自己的 FAIR 记录，没有就是没有（不猜）。"""
    p = _abox(dev_dir) / "static" / "now" / "dataset_fair.jsonld"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def rights(dev: str, dev_dir: pathlib.Path) -> dict:
    """这台机器的许可账：上游声明 + 本仓裁定 -> 它进得了哪一种构建。

    ★这份账**与卡片同住**（`facts/device/<id>/rights.json`）。一份没有许可账的装置描述，
    下一个人无从判断它能不能发出去——而制品闸子要的正是那个判断，且它必须来自
    记下来的事实，不是来自谁还记得。
    """
    fair = _fair(dev_dir) or {}
    rule = fair.get(RULING_KEY) or {}
    rh = fair.get("rights_holder")
    blocked = _blocked_ids(fair)
    out: dict = {
        "device": dev,
        "source": _cite(_abox(dev_dir)),
        "declared": fair.get("license"),
        "rights_holder": rh if isinstance(rh, str) else (json.dumps(rh, ensure_ascii=False) if rh else None),
        "internal": bool(rule.get("dev:internal", True)),
        #: ★**无裁定即不发布**。缺了这个块不退回一个「大概可以」的缺省——
        #: 缺省会让一台从没被判过的机器悄悄进公开制品。
        "public": bool(rule.get("dev:public")) if rule else False,
        "public_excluded_ids": sorted(blocked),
        "ruling": rule.get("dev:statement"),
        "note": None,
    }
    if not rule:
        out["note"] = (f"fydoc 的 FAIR 件没有 {RULING_KEY} —— 无裁定，不进任何公开制品。")
    if not fair:
        out["note"] = "A-Box 没有 static/now/dataset_fair.jsonld —— 上游许可未声明。"
    if blocked:
        out["note"] = ((out["note"] + " ") if out["note"] else "") + (
            "上游逐 IDS 明写 redistributable=false 的不进公开版（第三方权属，"
            f"rights_holder={out['rights_holder']!r}）：" + "、".join(sorted(blocked)))
    return out


def write_rights(dev: str, dev_dir: pathlib.Path, out_root: pathlib.Path) -> pathlib.Path:
    d = out_root / dev
    d.mkdir(parents=True, exist_ok=True)
    p = d / "rights.json"
    p.write_text(json.dumps(rights(dev, dev_dir), ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    return p


def write(dev: str, doc: dict, out_root: pathlib.Path, src: str = "") -> pathlib.Path:
    d = out_root / dev
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dev}_device.yaml"
    body = yaml.dump(doc, allow_unicode=True, sort_keys=False,
                     default_flow_style=False, width=100)
    #: 抬头与机读的 `_basis` 引同一个字符串，两者不会再各说各的。
    p.write_text(HEADER.format(machine=doc["_machine"],
                               source=src or doc.get("_basis", dev)) + body,
                 encoding="utf-8")
    write_document(dev, out_root)
    return p


def write_document(dev: str, out_root: pathlib.Path) -> pathlib.Path | None:
    """把卡片**同一份内容**再落一份 `facts/device/<id>.jsonld`。

    ★★两种语法，一个来源。卡片（YAML）是人读人改的那一份，文档（JSON）是页面
    `fetch` 的那一份——`app/assets/devices.js` 读 `facts/device/<id>.jsonld`，
    可执行文件把同一棵树 `include_bytes!` 进去。**从前没有任何东西产出它**：
    抓回来的是 `<id>/<id>_device.yaml`，而发布器 `facts-publish.py` 与页面都问
    `<id>.jsonld`，于是 `[facts] device: public 版 0 个`——构建成功、一台装置也
    没带；`--features desktop` 那一档更是直接编不过（内嵌资源表里的
    `include_bytes!` 找不到文件）。产出方与消费方对「一条条目长什么样」的看法
    不一致，而两边都没说出来。

    ★这一份是**派生物**，从盘上刚写出的卡片转，而不是从上游再转一次。卡片不在
    就不写，返回 `None`。
    """
    card = out_root / dev / f"{dev}_device.yaml"
    if not card.is_file():
        return None
    doc = yaml.safe_load(card.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return None
    derive_document(dev, doc)
    p = out_root / f"{dev}.jsonld"
    #: ★`allow_nan=False`：Python 的缺省会写出裸 `NaN` / `Infinity`，**那不是 JSON**。
    #: 上面的 `finite()` 已经把唯一一种无歧义的情形（成对轮廓末尾的补位）摘掉了；
    #: 到这里还剩非有限值，就该在这里当场炸，而不是发出去让 `JSON.parse` 去炸。
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False) + "\n",
                 encoding="utf-8")
    return p


def derive_document(dev: str, doc: dict) -> dict:
    """The page document derived from a card (in place; returned) — the steps
    :func:`write_document` applies, callable on a card in memory: the per-provider
    groups of :func:`east_resolution` go through exactly these steps."""
    finite(dev, doc)
    identity(dev, doc)
    grid(dev, doc)
    vacuum_field(dev, doc)
    one_limiter(dev, doc)
    pf_flatten(dev, doc)
    channel_map(dev, doc)
    return doc


def one_limiter(dev: str, doc: dict) -> None:
    """几条**各自闭合**的限制器轮廓 → 只留第一条，其余记下来。

    ★★页面把 `limiter.unit[]` 当作**一条轮廓切成的几段**，按端点首尾相接缝起来
    （`app/assets/fyodev.js` 的 `stitchOutline`，那里的注释写着为什么）。EAST 的卡片
    里那两个单元不是两段，是**两条各自闭合的整轮廓**（`efit_w_pf` 60 点、`m-file`
    48 点）；缝起来是一个没有意义的多边形，而限制器多边形正是自由边界解的接触判据。
    实测 2026-09-07：两条一起交出去，同一组参考电流解出来的轴位置差 0.75 m，
    自由边界迭代跑满 600 次上限。

    ★判据是**每一条都闭合**：那时它们只能是互为备选（两堵墙不可能都是这堵墙）。
    WEST 的卡片有 89 个单元、其中 8 条闭合、其余是开口的段 —— 那是真正的分段形，
    这条规则不碰它。留第一条，被留下的记进 `fylite:limiter_alternatives`：
    换一条是一次要人来定的改动，而不是这里挑一个。
    """
    d2 = (doc.get("wall") or {}).get("description_2d")
    d2 = d2[0] if isinstance(d2, list) and d2 else d2
    units = ((d2 or {}).get("limiter") or {}).get("unit")
    if not isinstance(units, list) or len(units) < 2:
        return

    def closed(u):
        o = u.get("outline") or {}
        r, z = o.get("r") or [], o.get("z") or []
        return len(r) > 2 and r[0] == r[-1] and z[0] == z[-1]

    #: ★2026-09-13（est2 移除、wall 缺省回 base）：`base` 那条轮廓在 fydoc 里写着 `closed: 1`，
    #: 但首末点并不重合（z 0.485 / 0.309），`wall()` 又不带 `closed` 标志——只按首末点判，它会被
    #: 当成「一段」，两条整轮廓于是一起交给页面缝。EAST 的装配器给每个单元记下它的 provider
    #: （`fylite:provider`）；**每个单元各属一个不同的 provider** 时，它们按构造就是互为备选的整轮廓。
    providers = [u.get("fylite:provider") for u in units]
    alternatives = all(providers) and len(set(providers)) == len(units)
    if not (alternatives or all(closed(u) for u in units)):
        return                                  #: 分段形，交给页面去缝
    kept, rest = units[0], units[1:]
    d2["limiter"]["unit"] = [kept]
    d2["limiter"]["fylite:limiter_alternatives"] = [
        {"name": u.get("name"), "points": len(((u.get("outline") or {}).get("r")) or [])}
        for u in rest]


def pf_flatten(dev: str, doc: dict) -> None:
    """把**按 PCS 通道分组**的线圈摊成一元件一线圈 —— 页面文档的那一形。

    ★★两种形，同一台机器。手工卡片（EAST）按**通道**记：12 个通道，其中两个各驱动
    一对串联元件，共 14 个元件；页面读的 `<id>.jsonld` 按**线圈**记：14 个线圈，
    各一个元件。`app/assets/fyodev.js` 的 `fromFyo` 只认后一形，而通道图的下标数的
    正是那 14 个元件 —— 把分组形原样交出去，页面会说
    「channel 10 points at a coil that does not exist (there are 12)」。

    ★★这一步 2026-09-07 补上。此前派生这一份**不摊**，于是从卡片转出来的 EAST 在
    五道 worker 闸子上要么算出另一台机器，要么反解当场拒绝（`kernel code -104700`）。
    摊开之后逐位核对过：矩形 · 名字 · 匝数与内核仓 `fylite_device_east.json`
    **完全相同**（那一份正是同一张卡片的摊开形）。

    ★名字取元件自己的 `fylite:name`：通道名是 `PF1P`（一对串联共用一个名字），
    线圈名是 `PF1` / `PF2`。用通道名会让两个线圈重名，而重名的线圈在任何按名字
    找回来的地方都是一个坑。
    """
    coils = (doc.get("pf_active") or {}).get("coil")
    if not isinstance(coils, list):
        return
    if all(len(c.get("element") or []) <= 1 for c in coils) \
            and not any(e.get("fylite:name") for c in coils for e in c.get("element") or []):
        return                                  #: 已经是一元件一线圈
    flat = []
    for ch in coils:
        for el in ch.get("element") or []:
            el = dict(el)
            name = el.pop("fylite:name", None) or ch.get("name")
            coil = {"name": name, "element": [el]}
            #: ★★the DD `function` travels onto every coil the channel flattens into.
            #: Dropping it (as this did until 2026-09-13) made EAST's IC1/IC2 plain
            #: PF coils to every reader of this document — `case.rs::is_fast_coil`,
            #: `device.is_fast_coil` — so the start design solved 16 channels, not 12.
            if ch.get("function"):
                coil["function"] = [dict(f) for f in ch["function"]]
            flat.append(coil)
    doc["pf_active"]["coil"] = flat


def channel_map(dev: str, doc: dict) -> None:
    """`pf_channel_elements`（卡片的拼法）→ `fylite:channel_map`（文档的拼法）。

    ★★同一个量、两种拼法，`test_east_descriptions_agree.py::test_the_channel_map_is_the_same_map`
    早写着这条对应。**派生这一步从前不翻译它**，于是从卡片转出来的 `east.jsonld`
    根本没有通道图 —— 而页面读的正是 `fylite:channel_map`
    （`app/assets/fyodev.js`）。后果不是少一行：没有通道基，反解**当场拒绝**
    （实测 2026-09-07：`validate-worker-recon` 报 `the inverse solve refused
    the request; kernel code -104700` —— 第 47 次拟合失败）。

    ★只在文档还没有那个键时写：卡片自己带 `fylite:channel_map` 的那天，
    以它为准，这里不覆盖。

    ★★**两种拼法都留**（2026-09-13 改）：此前这里 `pop` 掉 `pf_channel_elements`，而
    `case.rs::device_coils` 与 `device.pf_channel_map` 读的正是它，找不到就退回「一线圈
    一通道」——EAST 的起始设计因此解 14 个通道而不是 12 个，且不报错。页面
    （`fyodev.js`）读 `fylite:channel_map`；两者都在 `@fyo-table DEVICE` 里声明，
    所以两个都写，由同一份行转出。
    """
    if "fylite:channel_map" in doc:
        return
    rows = doc.get("pf_channel_elements")
    if not isinstance(rows, list):
        return
    doc["fylite:channel_map"] = [
        [[int(t["element"]), float(t["weight"])] for t in ch] for ch in rows]


#: ★分辨率的缺省：EFIT 的老约定，也是本仓随包 `libefit.so` 的编译期维度。
#: **只在卡片没有编译期维度可抄时才用**——见 `grid()` 抬头。
DEFAULT_GRID_N = 65


def identity(dev: str, doc: dict) -> None:
    """让文档**自报家门**：`fylite:device_id` 与 `name`。

    ★★为什么这一步存在（2026-09-05 实测）。发布出去的文档只在 `@id` 里带机器名
    （`fylite:device/east/est2` —— 那串还编着变体），而页面的读法
    `app/assets/fyodev.js` 认的是 `fylite:device_id`，认不到就叫 `imported`。
    自带的那批不受影响（id 由目录 `catalogue.jsonld` 给），**受影响的是拿到一份
    文档、把它拖进页面的读者**：三台机器进来会叫 `imported`、`imported-imported`、
    `imported-imported-2`，而且不报错。页面自己的写法 `FyoDevice.toFyo` 从来就写
    这两个键，所以这不是新契约，是发布侧漏了它写的那一份。

    ★`name` 取卡片的 `_machine`（manifest 的 `device` 字段，如 `EAST`）——不造词：
    卡片没有就不写，读者那侧退回 id。
    """
    doc.setdefault("fylite:device_id", dev)
    machine = doc.get("_machine")
    if isinstance(machine, str) and machine.strip():
        doc.setdefault("name", machine.strip())


def grid(dev: str, doc: dict) -> None:
    """把卡片的 `machine.default_grid` 铸成文档的 `fylite:grid`。

    ★★为什么这一步存在（2026-09-05 实测）。页面的装置读法 `app/assets/fyodev.js`
    **硬要** `fylite:grid`，而**没有任何一份发布出去的文档带它**——于是浏览器的装置
    面板一台预设机器也列不出来（每台带一句「文档里没有 fylite:grid」，不是崩溃，
    所以更难发现）。三种制品全带着这个毛病，构建从头到尾是绿的。

    ★★**盒是机器的，分辨率是计算的**——这句不是本函数的发明，是闸子
    `test_east_descriptions_agree.py::test_the_grid_box_agrees` 早就写着的契约，
    也是 `fyodev.js` 抬头那句「`fylite:grid` 是计算的属性，不是机器的」的另一半。
    所以：

    * **盒**逐字抄卡片的 `machine.default_grid`（`r_min` / `r_max` / `z_min` /
      `z_max`）。它本来就在每一份卡片里——手工那张记的是参考表盒（EAST 的
      `g093060.01000` 表头），生成的那些由 `machine_block()` 从本文档的限制器轮廓
      加 5 cm 边距导出。**这里不另算一遍**：算两遍就是两份答案。
    * **分辨率**取卡片自己的编译期维度 `solver_dims.nw` / `.nh`（EAST 65×65，那是
      随包 `libefit.so` 的数组维度，改不了——它的 `default_grid.note` 原话就是
      「盒可选，分辨率不可」）；卡片没有那一组时用 `DEFAULT_GRID_N`，并在
      `fylite:grid_note` 里说明这个数是**选的**、不是量出来的。

    ★卡片没有 `machine.default_grid` 就**不写**这个键，而不是编一个盒：一个凭空的
    计算域会让重构在一个不含等离子体的框里跑，而那不会报错，只会给出一个看起来
    合理的错答案。页面那侧会因此拒绝这一台并说出理由，这正是想要的。
    """
    m = doc.get("machine")
    box = m.get("default_grid") if isinstance(m, dict) else None
    if not isinstance(box, dict):
        return
    need = ("r_min", "r_max", "z_min", "z_max")
    if not all(isinstance(box.get(k), (int, float)) for k in need):
        return
    sd = doc.get("solver_dims")
    nw = sd.get("nw") if isinstance(sd, dict) else None
    nh = sd.get("nh") if isinstance(sd, dict) else None
    compiled = isinstance(nw, int) and isinstance(nh, int)
    nr, nz = (nw, nh) if compiled else (DEFAULT_GRID_N, DEFAULT_GRID_N)
    doc["fylite:grid"] = {
        "nr": nr, "nz": nz,
        "rmin": box["r_min"], "rmax": box["r_max"],
        "zmin": box["z_min"], "zmax": box["z_max"],
    }
    why = box.get("note") or ""
    doc["fylite:grid_note"] = (
        ("分辨率取本文档 `solver_dims` 的编译期维度（随包 libefit.so 的数组维度，改不了）。"
         if compiled else
         f"分辨率是**选的**缺省 {DEFAULT_GRID_N}×{DEFAULT_GRID_N}（EFIT 约定），"
         "不是量出来的：本文档没有编译期维度可抄。")
        + "盒逐字取 `machine.default_grid`" + (f"：{why}" if why else "。"))


def vacuum_field(dev: str, doc: dict) -> None:
    """把卡片记的标称环向场铸成文档的 `tf.r0` / `tf.b0`。

    ★★同 `grid()` 一样是**契约路径的映射**，不是新的物理。生成的契约表
    （`app/assets/fyo-interface.js` 的 `TABLES.DEVICE`）把这两格钉在 `tf/r0` 与
    `tf/b0`，而卡片把同样两个数记在 `machine.r_centre` 与 `machine.fylite:b0`——
    后者由 `machine_block()` 自上游的 `b_field_phi_vacuum_r / r0` 导出（或 ITER
    那样自参考平衡表头取）。两处名字不同，于是页面读任何一台都拿不到，
    而**没有任何东西会红**：装置面板只是列不出机器。

    ★`tf.r0` 在上游可能是裸数，也可能是 `{value, unit, …}` 一个块（实测 ITER 是块、
    BEST 是裸数）。页面要的是数，所以这里**只在拿得到裸数时才写**，写不出就不写：
    一个把 `{value: 6.2}` 当数用的读者会得到 `NaN`，而 `NaN` 在求解器里不会当场炸，
    它会给出一个看起来合理的错平衡。

    ★★**拿不到就不写，绝不编。** 实测有两台没有标称场：ITER（上游的 `tf` 只有 r0
    且把 b0 标为「需要确认」，真值要从参考平衡表头取，而那份 g 文件不在本检出里）与
    WEST（上游没有 `b_field_phi_vacuum_r`）。页面因此按名拒绝这两台并说出理由——
    那是对的：EAST 的环向场本来就是**逐炮的测量**（`\\focs_it`），卡片不把它当机器常量
    正是它的严谨处，而页面需要一个数来画图是页面的事，不是卡片该迁就的事。
    """
    m = doc.get("machine")
    if not isinstance(m, dict):
        return
    tf = doc.get("tf")
    if not isinstance(tf, dict):
        tf = {}
        doc["tf"] = tf
    took = []

    def plain(v):
        """裸数就取，`{value: …}` 一类的块不取——见抬头。"""
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    if plain(tf.get("r0")) is None:
        r0 = plain(m.get("r_centre"))
        if r0 is not None:
            tf["r0"] = r0
            took.append("r0 <- machine.r_centre")
    if plain(tf.get("b0")) is None:
        b0 = plain(m.get("fylite:b0"))
        if b0 is not None:
            tf["b0"] = b0
            took.append("b0 <- machine.fylite:b0")
    if took:
        doc["fylite:tf_note"] = (
            "标称环向场按契约路径落到 `tf`：" + "；".join(took)
            + "。★数是卡片的，这里只搬位置不改值。"
            + (f" b0 的由来：{m['fylite:b0_note']}" if m.get("fylite:b0_note") else ""))


def _nonfinite(node, trail: str = ""):
    """逐个非有限浮点：`(路径, 下标, 值)`。"""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _nonfinite(v, f"{trail}.{k}" if trail else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, float) and not math.isfinite(v):
                yield trail, i, v
            else:
                yield from _nonfinite(v, f"{trail}[{i}]")
    elif isinstance(node, float) and not math.isfinite(node):
        yield trail, None, node


def finite(dev: str, doc: dict) -> None:
    """把文档改成 **JSON 写得出来**的样子，或者按名拒绝。

    ★★为什么这一步存在（2026-09-05 实测）。WEST 的壁面轮廓 `Baffle` 是 44 个点，
    而**末点的 r 与 z 都是 NaN**——上游 MATLAB 定长数组的补位，`metis2fyo.py` 照录进
    A-Box，本工具再照录进 `facts/device/west.jsonld`。Python 的 `json.dumps` 缺省把它
    写成裸 `NaN`，而 **JSON 没有这个词**：页面 `fetch(...).then(r => r.json())` 当场抛
    `SyntaxError`，于是这一台装置在浏览器里整份读不出来。三种制品**全部**带着这份读不
    出来的文档发了出去，而构建从头到尾是绿的——先发现的人是拿到制品的那个。

    做两件事，分得很死：

    * **成对轮廓的末位补位**（`{r: [...], z: [...]}` 两条同长、同在末位非有限）——摘掉。
      它不是几何：同一份文件里其余 88 个 unit 都没有它，而这一个有。
    * **其余任何非有限值**——**拒绝**，点名路径。中间的一个 NaN 是缺一个点，不是补位；
      摘掉它会把折线接错，而那种错不报警。

    ★为什么不写成 `null`：JS 里 `+null === 0`，一个 `null` 顶点会被画到原点去——比
    `NaN`（画布直接跳过那一段）更糟。摘掉或拒绝，没有第三条。
    """
    dropped = []

    def trim(node, trail=""):
        if isinstance(node, dict):
            r, z = node.get("r"), node.get("z")
            if (isinstance(r, list) and isinstance(z, list) and len(r) == len(z) >= 2
                    and isinstance(r[-1], float) and not math.isfinite(r[-1])
                    and isinstance(z[-1], float) and not math.isfinite(z[-1])):
                node["r"], node["z"] = r[:-1], z[:-1]
                dropped.append(f"{trail}.r/z[{len(r) - 1}]")
            for k, v in node.items():
                trim(v, f"{trail}.{k}" if trail else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                trim(v, f"{trail}[{i}]")

    trim(doc)
    if dropped:
        print(f"  {dev}: 摘掉 {len(dropped)} 个成对轮廓的末位补位（NaN）："
              + " ".join(dropped[:3]) + (" …" if len(dropped) > 3 else ""))
    left = list(_nonfinite(doc))
    if left:
        where = ", ".join(f"{t}[{i}]={v}" if i is not None else f"{t}={v}"
                          for t, i, v in left[:5])
        raise SystemExit(
            f"[facts] {dev}: 文档里有 {len(left)} 个非有限值，JSON 写不出来：{where}\n"
            f"[facts]   它们不是成对轮廓的末位补位，摘掉会改变几何——请在上游"
            f"（fydata 的转换器）修，不要在这里猜。")


def write_catalogue(out_root: pathlib.Path) -> pathlib.Path:
    """目录：这个语料里有哪几台，各在哪份文档里。

    页面按它逐份取（`devices.js` 的 `load()`），发布器按实际发出去的那几个重写它
    （`facts-publish.py` 的 `catalogue()`）——所以这里写的是**盘上真有的**那些，
    许可裁决留给发布器那一步，两处不重复判。
    """
    ids = sorted(p.stem for p in out_root.glob("*.jsonld") if p.stem != "catalogue")
    entries = []
    for dev in ids:
        e = {"fylite:device_id": dev, "fylite:document": f"{dev}.jsonld"}
        r = out_root / dev / "rights.json"
        if r.is_file():
            acct = json.loads(r.read_text(encoding="utf-8"))
            e["fylite:rights_holder"] = acct.get("rights_holder")
            e["fylite:declared"] = acct.get("declared")
        entries.append(e)
    doc = {
        "@context": {"fylite": "urn:fylite:"},
        "@id": "fylite:facts/device/catalogue",
        "@type": "fylite:DeviceCatalogue",
        "fylite:note": (
            "GENERATED by tools/abox-to-facts.py — 盘上真有的那几台。"
            "哪一台进哪一种构建是**另一个**判据（每台自己的 rights.json，由 "
            "tools/facts-publish.py 施用），发布时这份目录按实际发出去的重写。"),
        "fylite:devices": entries,
    }
    p = out_root / "catalogue.jsonld"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("device", nargs="*", help="machine id(s), e.g. iter west")
    ap.add_argument("--source", "--fydata", dest="fydata", type=pathlib.Path,
                    default=FYDOC, help="A-Box 的根（缺省 fydoc，权威源）")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--all", action="store_true",
                    help="every machine with a manifest")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--publishable", action="store_true",
                    help="只列出进得了这一种构建的机器（许可闸；不写文件）")
    #: ★缺省是 **internal**（2026-09-05 裁定，`FYL-SDD-03` A-14）：fylite 以内部
    #: 工具发布，全功能构建含 EAST。许可判据没有跟着松——它仍在每台自己的
    #: `rights.json` 里；变的只是「不说话时装哪一版」。公开面因此必须**明写**
    #: `--flavour public`，见 A-14 的门禁。
    ap.add_argument("--flavour", choices=("public", "internal"), default="internal",
                    help="哪一种构建：internal（缺省，全部，含 EAST）"
                         "/ public（不含 EAST 与上游禁分发的 IDS）")
    ap.add_argument("--shot", type=int, default=None,
                    help="generate the card for this shot: providers must cover it; recorded as _shot / _valid_shots")
    ap.add_argument("--measurement-chain", dest="measurement_chain", default=None, metavar="CHAIN",
                    help="the measurement chain (the measurement document's `measurement_chain`, declared in the "
                         "manifest's measurement_chains): resolves the measurement-ordered IDS within that chain")
    a = ap.parse_args(argv)
    global SHOT, CHAIN
    SHOT = a.shot
    CHAIN = a.measurement_chain
    if SHOT is not None or CHAIN is not None:
        if a.all or len(a.device) != 1:
            ap.error("--shot / --measurement-chain generate a variant card for ONE named machine")
        if a.out.resolve() == OUT.resolve():
            ap.error("--shot / --measurement-chain write a VARIANT: give -o (e.g. "
                     "dist/facts/device/<id>/variants/<name>) so the default card is not overwritten")
        TARGET.update(a.device)

    if not device_root(a.fydata).is_dir():
        print(f"no fydata device tree at {a.fydata}", file=sys.stderr)
        return 2
    known = devices(a.fydata)
    if a.publishable:
        #: ★制品闸的**唯一**问答面：哪一台进哪一种构建。构建脚本读它，不自己判许可。
        root = device_root(a.fydata)
        for dev in known:
            r = rights(dev, root / dev)
            if a.flavour == "internal" or r["public"]:
                ex = r["public_excluded_ids"] if a.flavour == "public" else []
                print(dev + ("" if not ex else "  # 去掉 " + " ".join(ex)))
        return 0
    if a.list:
        for d in known:
            print(d)
        return 0
    want = known if a.all else list(a.device)
    if not want:
        ap.error("name a machine, or pass --all/--list")
    rc = 0
    root = device_root(a.fydata)
    for dev in want:
        if dev not in known:
            print(f"{dev}: no machine manifest under {a.fydata}", file=sys.stderr)
            rc = 1
            continue
        #: ★★许可账**先于卡片**写，而且对每一台都写——包括手工维护的那台，以及
        #: 转不出卡片的那些。理由：一份没有许可账的装置描述，下一个人无从判断它能不能
        #: 发出去；而「没有账」与「账说不行」在制品闸子那里必须是同一个答案（都不发）。
        rp = write_rights(dev, root / dev, a.out)
        r = json.loads(rp.read_text(encoding="utf-8"))
        mark = "内部版 + 公开版" if r["public"] else "仅内部版"
        print(f"  {dev}: {mark}（上游 declared {r['declared']!r}"
              + (f"，公开版去掉 {' '.join(r['public_excluded_ids'])}"
                 if r["public_excluded_ids"] else "") + ")")
        doc = build(dev, a.fydata)
        if dev in TARGET:
            #: ★the card says what it was generated FOR (`_selection` · `_shot` · `_valid_shots`) —
            #: and every one of those answers is the runtime's (see `variant_card`)
            doc = variant_card(dev, a.fydata, doc, shot=SHOT, measurement_chain=CHAIN)
        #: ★★A-Box 里没有 epoch 的机器（实测 cmod / d3d / hl2m / hl3 只有一份
        #: `machine.jsonld`，没有任何 IDS 文件）会转出一张**空卡片**。空卡片比没有
        #: 卡片更坏：`load_device` 会拒绝它，而任何「这台机器有描述吗」的检查都会
        #: 答「有」。所以不写，并说清楚为什么。
        #: ★★数的是 `magnetics` / `pf_active` / `wall` **有内容的那几组**，与闸子
        #: `test_every_generated_group_names_the_file_it_came_from` 同一把尺。
        #: 从前这里数的是「任何带 `fylite:source` 的组」，而 `tf` 总是带——于是
        #: 只有 tf 的机器（实测 cmod · d3d · hl3 · sparc · ste1）照样写出一张卡片，
        #: 而那张卡片正是本段注释说的**空卡片**：`load_device` 拒绝它，任何
        #: 「这台机器有描述吗」的检查却答「有」。两处各数各的，就会这样。
        groups = [k for k in ("magnetics", "pf_active", "wall")
                  if _has_content(k, doc.get(k))]
        if not groups:
            #: ★话术要说**实际成立的那件事**：这五台（cmod · d3d · hl3 · sparc ·
            #: ste1）是有静态文件的，只是只有 `tf`；hl2m 才是连静态目录都没有。
            #: 原来那句「没有 epoch 或没有静态文件」对前五台是错的，而人会照它去
            #: 上游找一个并不存在的毛病。
            carried = sorted(k for k in doc if not k.startswith("_")
                             and _has_content(k, doc.get(k)))
            print(f"{dev}: A-Box 没有 magnetics / pf_active / wall 中的任何一组"
                  + (f"（只有 {' '.join(carried)}）" if carried else "（没有静态文件）")
                  + "——不写空卡片", file=sys.stderr)
            continue
        if dev in RESOLUTIONS and dev not in TARGET:
            #: (a `--shot` / `--measurement-chain` variant is written as resolved, not re-resolved)
            #: ★★R-S1 / R-S2 (user rulings 2026-09-13): the groups of every provider ship
            #: beside the card, and the card itself is the NO-SHOT resolution — resolved by
            #: the runtime's rule, and saying per IDS which provider and shot range it is
            res = RESOLUTIONS[dev](a.fydata)
            rpath = write_resolution(dev, res, a.out)
            doc = resolve_card(doc, res)
            sel = doc["provenance"]["fylite:resolution"]["ids"]
            print(f"  {dev}: no-shot resolution "
                  + ", ".join(f"{k}={v['provider']} {v['shots']}" for k, v in sel.items())
                  + f"; resolution document -> {rpath.name}")
        p = write(dev, doc, a.out)
        try:
            shown = p.relative_to(ROOT)
        except ValueError:      #: -o outside the checkout (a temp dir)
            shown = p
        print(f"{dev} -> {shown}")
    #: ★目录最后写一次：它说的是**这一趟之后盘上有什么**，所以要在每一台都写完
    #: 之后再落——写在循环里的话，中途失败的那一趟会留下一份广告了不存在文档的目录。
    cat = write_catalogue(a.out)
    ids = json.loads(cat.read_text(encoding="utf-8"))["fylite:devices"]
    print(f"[facts] catalogue: {len(ids)} 台 -> {cat}")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
