#!/usr/bin/env python3
"""从 A-Box 拖回 ``machine_desc/<id>/<id>_device.yaml``。

★★2026-09-02 从内核仓搬到本仓并改名（原 ``fydata-to-fyo-device.py``）：装置牌是
**按需拖回的输入**，不是随仓走的数据。``machine_desc/`` 在本仓 gitignore ——
要用的时候跑这个，用完不进版本库。

    python tools/abox-to-machine-desc.py --all          # 全部机器
    python tools/abox-to-machine-desc.py iter west      # 指定几台

★★**它不是一次「刷新」，是一次「换成上游今天的样子」。** 2026-09-02 实测：内核仓
committed 的那七张卡片是从**旧 epoch / 旧布局**生成的，拖回来的与它们不同，而且不止
出处路径——ITER 那张会**丢掉 `machine.fylite:b0`（5.3 T）**，壁面轮廓也从 `points`
换成 `r`/`z` 两个数组。所以拖回来之后要复核消费者，不能当作等价替换。

★**What this closes.**  `machine_desc/` held ONE machine — EAST — and the
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

★**EAST is not regenerated.**  `machine_desc/east/east_device.yaml` is
hand-maintained and strictly richer than fydata's EAST tree (the est2 79-probe
basis, the fit-control block, the passive set, the power-supply parameters —
none of which is upstream).  Asking for it here is refused, not silently
overwritten.

    python3 tools/fydata-to-fyo-device.py --list
    python3 tools/fydata-to-fyo-device.py iter
    python3 tools/fydata-to-fyo-device.py --all
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: ★★**fydoc 是权威源**（用户裁定 2026-09-02）。fydata 那侧同名内容是誊录，两边
#: 实测**逐值相同**（十台，差别只有记下来的出处路径），所以指哪一边都出得来同样的
#: 卡片——而权威在 fydoc，那就读 fydoc。`--source` 仍可显式指到 fydata。
FYDOC = pathlib.Path("/home/salmon/workspace/fydoc")
OUT = ROOT / "machine_desc"

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

    ★fydata 还做过顶层重规划（`machine/tokamak/` → `device/tokamak/` →
    `abox/device/tokamak/`），本文件从前把路径写死在三处、只改了一处，于是对着今天的
    fydata 直接答「找不到」。现在只有这一个函数知道布局。
    """
    for c in (root / "device",                        # fydoc
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
    `machine_desc/east/east_device.yaml` wrote before that table existed and
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
    elif tf and tf.get("r0") is not None:
        out["r_centre"] = float(tf["r0"])
        out["r_centre_note"] = "tf.r0 from the upstream description"
        rb = tf.get("b_field_phi_vacuum_r")
        #: ★`data` FIRST, `value` as the fallback.  fydata standardised the
        #: {quantity, unit} wrapper key on `data` (78d2544); reading only
        #: `value` made `fylite:b0` vanish from best / cfedr / cfetr WITHOUT
        #: an error — a dropped field reads as「上游没有这个量」, which is the
        #: worst failure mode a converter has.
        value = rb.get("data", rb.get("value")) if isinstance(rb, dict) else rb
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
        "_basis": f"{manifest_path.parent} (epoch "
                  f"{(manifest.get('epochs') or [{}])[0].get('id', '?')})",
        "provenance": {
            "generator": "tools/abox-to-machine-desc.py",
            "source": str(manifest_path),
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


HEADER = """\
# {machine} device description — fyo/JSON-LD semantics over IMAS DD v4 keys.
#
# GENERATED by tools/fydata-to-fyo-device.py from
#   fydata/abox/device/tokamak/{dev}/
# Do not hand-edit: re-run the generator, then diff.
#
# Read through fylite.device.load_device, like machine_desc/east/.  A group
# the upstream description does not carry is present and marked
# `fylite:absent` — declared, not defaulted, and not quietly missing.
"""


def write(dev: str, doc: dict, out_root: pathlib.Path) -> pathlib.Path:
    d = out_root / dev
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dev}_device.yaml"
    body = yaml.dump(doc, allow_unicode=True, sort_keys=False,
                     default_flow_style=False, width=100)
    p.write_text(HEADER.format(machine=doc["_machine"], dev=dev) + body,
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
    a = ap.parse_args(argv)

    if not device_root(a.fydata).is_dir():
        print(f"no fydata device tree at {a.fydata}", file=sys.stderr)
        return 2
    known = devices(a.fydata)
    if a.list:
        for d in known:
            print(d, "(hand-maintained here)" if d in HANDWRITTEN else "")
        return 0
    want = known if a.all else list(a.device)
    if not want:
        ap.error("name a machine, or pass --all/--list")
    rc = 0
    for dev in want:
        if dev in HANDWRITTEN:
            if not a.all:
                print(f"{dev}: hand-maintained here and strictly richer than "
                      f"the upstream tree — refusing to overwrite",
                      file=sys.stderr)
                rc = 1
            continue
        if dev not in known:
            print(f"{dev}: no machine manifest under {a.fydata}", file=sys.stderr)
            rc = 1
            continue
        p = write(dev, build(dev, a.fydata), a.out)
        try:
            shown = p.relative_to(ROOT)
        except ValueError:      #: -o outside the checkout (a temp dir)
            shown = p
        print(f"{dev} -> {shown}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
