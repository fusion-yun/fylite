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

★**EAST is not regenerated.**  `facts/device/east/east_device.yaml` is
hand-maintained and strictly richer than fydata's EAST tree (the est2 79-probe
basis, the fit-control block, the passive set, the power-supply parameters —
none of which is upstream).  Asking for it here is refused, not silently
overwritten.

    python3 tools/abox-to-facts.py --list
    python3 tools/abox-to-facts.py iter
    python3 tools/abox-to-facts.py --all
"""

from __future__ import annotations

import argparse
import json
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
OUT = ROOT / "facts" / DOMAIN

#: EAST's document is hand-maintained and richer than the upstream tree.
HANDWRITTEN = {"east"}

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
    return {"@type": f"fyo:{ids}", "count": 0,
            "fylite:absent": why}


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
        entry = {"name": str(c.get("name") or c.get("identifier") or f"PF{i}"),
                 "element": _elements(c)}
        if c.get("resistance") is not None:
            entry["resistance"] = float(c["resistance"])
        if c.get("description"):
            entry["fylite:description"] = str(c["description"])
        coils.append(entry)
    out = {"@type": "fyo:pf_active", "count": len(coils),
           "fylite:source": source, "coil": coils}
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
            item["fylite:length"] = float(c["length"])
        out.append(item)
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
        units.append({"name": str(u.get("name") or "limiter"),
                      "count": len(r), "outline": {"r": r, "z": z}})
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
        if value is not None:
            out["fylite:b0"] = float(value) / float(tf["r0"])
            out["fylite:b0_note"] = (
                "b_field_phi_vacuum_r / r0, both from the upstream tf")
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


def build(dev: str, fydata: pathlib.Path) -> dict:
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
    if dev == "iter" and tf is not None and "b_field_phi_vacuum_r" not in tf:
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

    if "magnetics" in files:
        doc["magnetics"] = magnetics(_load(files["magnetics"]), rel["magnetics"])
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

    if tf is not None:
        doc["tf"] = {"@type": "fyo:tf", "fylite:source": rel["tf"],
                     "r0": tf.get("r0"),
                     "coils_n": tf.get("coils_n"),
                     "b_field_phi_vacuum_r": tf.get("b_field_phi_vacuum_r")}

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
    doc["solver_dims"] = {
        "@type": "fylite:CompiledDimensions",
        "fylite:absent": (
            "compiled EFIT array dimensions are a property of a built "
            "libefit.so for one machine; none exists for this one"),
    }
    missing = [g for g in REQUIRED if g not in doc]
    assert not missing, missing
    return doc


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
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("device", nargs="*", help="machine id(s), e.g. iter west")
    ap.add_argument("--source", "--fydata", dest="fydata", type=pathlib.Path,
                    default=FYDOC, help="A-Box 的根（缺省 fydoc，权威源）")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--all", action="store_true",
                    help="every machine with a manifest, EAST excepted")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--publishable", action="store_true",
                    help="只列出进得了这一种构建的机器（许可闸；不写文件）")
    ap.add_argument("--flavour", choices=("public", "internal"), default="public",
                    help="哪一种构建：public（缺省，不含 EAST 与上游禁分发的 IDS）"
                         "/ internal（全部）")
    a = ap.parse_args(argv)

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
            print(d, "(hand-maintained here)" if d in HANDWRITTEN else "")
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
        if dev in HANDWRITTEN:
            if not a.all:
                print(f"{dev}: hand-maintained here and strictly richer than "
                      f"the upstream tree — refusing to overwrite the card "
                      f"(rights.json written)", file=sys.stderr)
                rc = 1
            continue
        doc = build(dev, a.fydata)
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
        p = write(dev, doc, a.out)
        try:
            shown = p.relative_to(ROOT)
        except ValueError:      #: -o outside the checkout (a temp dir)
            shown = p
        print(f"{dev} -> {shown}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
