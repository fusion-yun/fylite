"""装置的极向截面示意图 —— 一份装置文档进来，一段 SVG 出去。

★★**通用**：读的是**文档**，不是某一台机器。同一个函数吃三种来源，因为它们
是同一棵树的三种写法：

* fylite 的装置描述（`@type: fyo:DeviceDescription`，一个装着若干 IDS 的容器）；
* 一个 IMAS 数据入口（`fy data convert … --layout imas`，或 :func:`fylite.io.fydoc.read`
  读回来的那份）；
* 上面两者的任意子集 —— 只有 `wall` 也画得出来。

★★**为什么是 SVG，不是 matplotlib**：本包的运行期依赖只有 numpy（`pyproject.toml`
的 `dependencies`），matplotlib 是 extra。截面图是几十条折线，画它不需要一个绘图库；
写成 SVG 文本，它在没有 matplotlib 的环境里也出得来，而且是**矢量**的——放大看得到
每一个角点，这正是校核几何要看的东西。:mod:`fylite.plot` 那一侧（通量图、重建面板）
仍旧走 matplotlib，两者分工不同。

★★这个模块**不做物理**。它不算面积、不判包含、不补缺失的点；文档里有什么就画什么，
没有的就不画（并在 :class:`CrossSection` 里如实计数）。一张示意图最容易撒的谎是
「看着完整」——所以画不出来的部分留白，而不是描一条像样的曲线。

    from fylite import machine_svg
    cs = machine_svg.cross_section(doc)      # 读出几何，不画
    print(cs.counts())                       # {'limiter': 2, 'vessel': 14, ...}
    open("iter.svg", "w").write(machine_svg.render(doc, title="ITER"))

支持的几何写法（DD 与 fylite 两侧都收，因为导出前后要能对照着看同一台机器）：

======================================  ===================================
`wall/…/limiter/unit/*/outline`          DD：一条折线
`wall/…/vessel/unit/*/annular/*`         DD：内/外轮廓或中心线（`outline_inner`
                                         `outline_outer` `centreline`）
`wall/…/vessel/unit/*/element/*/outline` DD：元件轮廓（EAST 导出后是这一种）
`wall/…/vessel/unit/*/element/*/geometry/rectangle`
                                         fylite：参数化矩形（EAST 源文档）
`pf_active/coil/*/element/*/geometry/rectangle`
                                         线圈元件；`outline` 同样收
`magnetics/flux_loop/*/position`         点
`magnetics/b_field_pol_probe/*/position` 点
======================================  ===================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

#: 画不出来的东西一律不画；这是那条规则的唯一例外表 —— 什么算「一条曲线」。
_MIN_POINTS = 2

#: 层轮廓合成时，两块板的端点落在这个距离内就当作同一点（米）。
#: ★用户裁定 2026-09-07：5 mm。见 :func:`layer_outlines`。
LAYER_TOLERANCE = 0.005


# --------------------------------------------------------------------------
# 几何
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Curve:
    """一条极向折线：`r` / `z` 等长，`closed` 说首尾是否同一点。"""

    r: np.ndarray
    z: np.ndarray
    name: str = ""
    #: 来源路径 —— 一张图上某条线不对时，这是回到文档里那一行的唯一线索
    path: str = ""
    #: 这条线属于哪一层（真空室的 `fylite:group`），没有分层就是空
    group: str = ""

    @property
    def closed(self) -> bool:
        return (len(self.r) > 2 and float(self.r[0]) == float(self.r[-1])
                and float(self.z[0]) == float(self.z[-1]))


@dataclass(frozen=True)
class Point:
    r: float
    z: float
    name: str = ""
    path: str = ""


@dataclass
class CrossSection:
    """一台机器的极向截面 —— 只是坐标，没有画法。"""

    device: str = ""
    limiter: list[Curve] = field(default_factory=list)
    vessel: list[Curve] = field(default_factory=list)
    coils: list[Curve] = field(default_factory=list)
    flux_loops: list[Point] = field(default_factory=list)
    probes: list[Point] = field(default_factory=list)

    def curves(self) -> list[Curve]:
        return [*self.limiter, *self.vessel, *self.coils]

    def points(self) -> list[Point]:
        return [*self.flux_loops, *self.probes]

    def counts(self) -> dict[str, int]:
        return {"limiter": len(self.limiter), "vessel": len(self.vessel),
                "coils": len(self.coils), "flux_loops": len(self.flux_loops),
                "probes": len(self.probes)}

    def is_empty(self) -> bool:
        return not self.curves() and not self.points()

    def bbox(self) -> tuple[float, float, float, float]:
        """`(r_min, z_min, r_max, z_max)`；空截面给一个单位框而不是抛错。"""
        rs: list[float] = []
        zs: list[float] = []
        for c in self.curves():
            rs.extend(np.asarray(c.r, dtype=float).tolist())
            zs.extend(np.asarray(c.z, dtype=float).tolist())
        for p in self.points():
            rs.append(p.r)
            zs.append(p.z)
        if not rs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(rs), min(zs), max(rs), max(zs))


# --------------------------------------------------------------------------
# 读文档
# --------------------------------------------------------------------------

def _as_dict(source) -> dict:
    """路径 / Bundle / 字典 → 字典。路径与 Bundle 都经中间层，看内容识别。"""
    if isinstance(source, dict):
        return source
    if hasattr(source, "to_dict"):          #: fylite.io.fydoc.Bundle
        return source.to_dict()
    if isinstance(source, (str, Path)):
        from .io import fydoc
        return fydoc.read(source).to_dict()
    raise TypeError(f"cross_section: 不认识的来源 {type(source).__name__}")


def _seq(node, key: str) -> list:
    """`node[key]` 当作序列取：DD 的结构数组在文档里可能是列表，也可能是单个映射。"""
    if not isinstance(node, dict):
        return []
    v = node.get(key)
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    if isinstance(v, dict):
        return [v]
    return []


def _curve(node, key: str, name: str, path: str, group: str = "") -> Curve | None:
    """`node[key]` 若是一对等长的 `r` / `z`，取成一条线；否则 None。"""
    if not isinstance(node, dict):
        return None
    sub = node.get(key)
    if not isinstance(sub, dict):
        return None
    r, z = sub.get("r"), sub.get("z")
    if r is None or z is None:
        return None
    r = np.atleast_1d(np.asarray(r, dtype=float))
    z = np.atleast_1d(np.asarray(z, dtype=float))
    if len(r) != len(z) or len(r) < _MIN_POINTS:
        return None
    return Curve(r, z, name=name, path=f"{path}/{key}", group=group)


def _point(node, key: str, name: str, path: str) -> list[Point]:
    """位置：DD 把一处写成结构、把可以多点的写成结构数组，两种都收。"""
    if not isinstance(node, dict):
        return []
    v = node.get(key)
    items = v if isinstance(v, list) else [v]
    out = []
    for i, it in enumerate(items):
        if isinstance(it, dict) and "r" in it and "z" in it:
            try:
                out.append(Point(float(it["r"]), float(it["z"]), name, f"{path}/{key}/{i}"))
            except (TypeError, ValueError):
                continue
    return out


def rectangle_corners(r: float, z: float, width: float, height: float,
                      a1: float = 0.0, a2: float = 90.0) -> tuple[np.ndarray, np.ndarray]:
    """参数化矩形 → 四个角，首点重复一次以闭合。

    ★★与内核 `kernels::element_filaments` 和 `fylite_runtime` 的 DD 归一化**同一个
    映射**（那两处一个逐格取样、一个只取四角）。三处写同一件事是有代价的，但
    比这里另起一套「差不多」的展开要好：差出来的那点角度不会报错，只会让图和数据
    悄悄对不上。`a2` 是平行四边形的第二边倾角（度，90° 即直角），`a1` 是整体绕
    `(r, z)` 的转角。
    """
    ca2, sa2 = math.cos(math.radians(a2)), math.sin(math.radians(a2))
    ca1, sa1 = math.cos(math.radians(a1)), math.sin(math.radians(a1))
    rr, zz = [], []
    for u, v in ((-width / 2, -height / 2), (width / 2, -height / 2),
                 (width / 2, height / 2), (-width / 2, height / 2)):
        pr, pz = r + u + v * ca2, z + v * sa2
        if a1 != 0.0:
            dr, dz = pr - r, pz - z
            pr, pz = r + dr * ca1 - dz * sa1, z + dr * sa1 + dz * ca1
        rr.append(pr)
        zz.append(pz)
    rr.append(rr[0])
    zz.append(zz[0])
    return np.asarray(rr), np.asarray(zz)


def _element_curve(el: dict, name: str, path: str,
                   a1: float | None, a2: float | None, group: str = "") -> Curve | None:
    """一个元件的形状：先认 DD 的 `outline`，再认 fylite 的参数化矩形。

    ★次序不是随便的。导出成 DD 之后，元件**两样都有**（矩形改挂 `fylite:geometry`
    留作参考）；这时该画的是 DD 那一份，因为它才是数据入口里真正携带的几何。
    """
    got = _curve(el, "outline", name, path, group)
    if got is not None:
        return got
    for key in ("geometry", "fylite:geometry"):
        geom = el.get(key)
        if not isinstance(geom, dict):
            continue
        got = _curve(geom, "outline", name, f"{path}/{key}", group)
        if got is not None:
            return got
        rect = geom.get("rectangle")
        if isinstance(rect, dict) and {"r", "z", "width", "height"} <= set(rect):
            ea1 = _num(el, "fylite:a1", a1 if a1 is not None else 0.0)
            ea2 = _num(el, "fylite:a2", a2 if a2 is not None else 90.0)
            r, z = rectangle_corners(float(rect["r"]), float(rect["z"]),
                                     float(rect["width"]), float(rect["height"]), ea1, ea2)
            return Curve(r, z, name=name, path=f"{path}/{key}/rectangle", group=group)
    return None


def _num(node: dict, key: str, default: float) -> float:
    try:
        return float(node[key])
    except (KeyError, TypeError, ValueError):
        return default


def _description_2d(wall: dict) -> list[dict]:
    """`description_2d` 的各片；**顶层也认**（EAST 的源文档把两支挂在 IDS 顶上）。"""
    slices = _seq(wall, "description_2d")
    if slices:
        return slices
    if any(k in wall for k in ("limiter", "vessel")):
        return [wall]
    return []


def cross_section(source, *, device: str = "", layers: bool = False,
                  tolerance: float = LAYER_TOLERANCE) -> CrossSection:
    """一份装置文档 → 它的极向截面。文档里没有的部分不补。

    `layers=True` 时，分了层的真空室壳板换成 :func:`layer_outlines` 合成的内外
    轮廓（**近似**，见那里）；合不成的层原样保留它的板。默认 `False` —— 一张
    图上默认画的应当是数据本身。
    """
    doc = _as_dict(source)
    cs = CrossSection(device=device or _device_name(doc))

    wall = doc.get("wall") if isinstance(doc.get("wall"), dict) else None
    for si, sl in enumerate(_description_2d(wall or {})):
        for section, sink in (("limiter", cs.limiter), ("vessel", cs.vessel)):
            for ui, unit in enumerate(_seq(sl.get(section), "unit")):
                base = f"wall/description_2d/{si}/{section}/unit/{ui}"
                name = str(unit.get("name", "") or "")
                grp = str(unit.get("fylite:group", "") or "")
                got = _curve(unit, "outline", name, base, grp)
                if got is not None:
                    sink.append(got)
                annular = unit.get("annular")
                if isinstance(annular, dict):
                    for key in ("outline_inner", "outline_outer", "centreline"):
                        got = _curve(annular, key, name, f"{base}/annular", grp)
                        if got is not None:
                            sink.append(got)
                a1, a2 = unit.get("fylite:a1"), unit.get("fylite:a2")
                for ei, el in enumerate(_seq(unit, "element")):
                    got = _element_curve(el, name, f"{base}/element/{ei}",
                                         _opt(a1), _opt(a2), grp)
                    if got is not None:
                        sink.append(got)

    pf = doc.get("pf_active") if isinstance(doc.get("pf_active"), dict) else {}
    for ci, coil in enumerate(_seq(pf, "coil")):
        name = str(coil.get("name", "") or "")
        for ei, el in enumerate(_seq(coil, "element")):
            got = _element_curve(el, name, f"pf_active/coil/{ci}/element/{ei}", None, None)
            if got is not None:
                cs.coils.append(got)

    if layers:
        got, _refused = layer_outlines(doc, tolerance=tolerance)
        merged = {o.group for o in got}
        if merged:
            #: ★按**层**换掉，不按名字：EAST 的真空室单元根本没有 `name`，
            #: 按名字挑会一块板也换不掉，而图上多出两条轮廓叠在板上 —— 实测踩过。
            keep = [c for c in cs.vessel if c.group not in merged]
            cs.vessel = keep + [c for o in got for c in (o.inner, o.outer)]

    mag = doc.get("magnetics") if isinstance(doc.get("magnetics"), dict) else {}
    for key, sink in (("flux_loop", cs.flux_loops), ("b_field_pol_probe", cs.probes)):
        for i, item in enumerate(_seq(mag, key)):
            sink.extend(_point(item, "position", str(item.get("name", "") or ""),
                               f"magnetics/{key}/{i}"))
    return cs


def _opt(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _device_name(doc: dict) -> str:
    for key in ("fylite:device_id", "name", "@id"):
        v = doc.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


# --------------------------------------------------------------------------
# 层轮廓 —— 一个**明确标注为近似**的派生产物
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LayerOutline:
    """一层壳板合成的内外两条轮廓 —— **近似**，且自带它有多近似的读数。"""

    group: str
    inner: Curve
    outer: Curve
    #: 合一的容差（米）
    tolerance: float
    #: 两块板的端点落在容差内、被并成一点的接头数
    snapped: int
    #: 其余接头的间距（米，从大到小）—— 这些是**直线跨过去**的，不是数据
    bridged: tuple[float, ...]
    #: 板的长边中位长度（米）。上面那些间距要对着它读：接头 1 cm、板 16 cm，
    #: 是「板与板之间有缝」；接头比板还长，就是「少了一块板」。
    plate_length: float

    @property
    def joints(self) -> int:
        return self.snapped + len(self.bridged)

    def note(self) -> str:
        """一句话，写进文档或图注。"""
        worst = max(self.bridged) if self.bridged else 0.0
        return (f"approximate: {self.joints} joints, {self.snapped} merged at "
                f"<= {self.tolerance * 1000:g} mm, {len(self.bridged)} bridged "
                f"(worst {worst * 1000:.1f} mm against a {self.plate_length * 1000:.0f} mm plate)")


def layer_outlines(source, *, tolerance: float = LAYER_TOLERANCE,
                   group_key: str = "fylite:group") -> tuple[list[LayerOutline], list[str]]:
    """把按 `fylite:group` 分层的矩形壳板合成每层的内外轮廓。

    返回 `(轮廓, 拒绝的层与理由)`。

    ★★**这是这个模块唯一的近似产物，所以它单独一个函数、默认不参与画图。**
    做法逐条：

    1. 每块板取它的**两条长边**（短边是板端的封头，正是要去掉的「相邻短边」）。
       长边由 `max(width, height)` 认，不按哪个字段叫什么 —— EAST 的壳板上下段
       长轴在 `width` 上、内外侧段在 `height` 上，按字段挑会把一半的板挑错。
    2. 两条长边里，中点离该层形心近的是**内**轮廓的一段，另一条是**外**。
    3. 板按对形心的极向角排一圈，首尾相接；相邻两段端点距离 <= `tolerance`
       的**并成一点**，其余**直线跨过去**并逐条记下距离。
    4. 一层里若有一个接头比板的长边还长，说明那里**少了一块板**，轮廓该绕过去
       还是直穿过去无从判断 —— **拒绝这一层**，不猜。

    ★★**它不冒充 DD。**产物挂在 `fylite:layer_outline` 下（:func:`apply_layer_outlines`），
    不写进 `annular/outline_inner`：DD 的那两支说的是「这层壳实际的内外面」，
    而这里是把离散的板连起来画的一条线，跨过的每一段都不是数据。
    实测 EAST（2026-09-07，容差 5 mm）：内外两层各 40 块板、40 个接头，
    16 个合一、24 个跨过（最大 103 / 107 mm，板长 161 / 172 mm），
    首尾闭合到 0.1 mm 以内；`passive_plates` 被拒（最大接头 1 582 mm，板长 55 mm）。
    """
    doc = _as_dict(source)
    wall = doc.get("wall") if isinstance(doc.get("wall"), dict) else {}
    groups: dict[str, list[dict]] = {}
    for sl in _description_2d(wall or {}):
        for unit in _seq(sl.get("vessel"), "unit"):
            g = unit.get(group_key)
            if not isinstance(g, str):
                continue
            for el in _seq(unit, "element"):
                plate = _plate(unit, el)
                if plate is not None:
                    groups.setdefault(g, []).append(plate)

    out, refused = [], []
    for g, plates in groups.items():
        if len(plates) < 3:
            refused.append(f"{g}: {len(plates)} 块板，连不成一圈")
            continue
        got = _chain(g, plates, tolerance)
        (out if isinstance(got, LayerOutline) else refused).append(got)
    return out, refused


def _plate(unit: dict, el: dict) -> dict | None:
    """一块矩形板的两条长边与中心。倾角在元件上找不到就上溯到单元。"""
    geom = el.get("geometry") or el.get("fylite:geometry")
    rect = geom.get("rectangle") if isinstance(geom, dict) else None
    if not isinstance(rect, dict) or not {"r", "z", "width", "height"} <= set(rect):
        return None
    w, h = float(rect["width"]), float(rect["height"])
    a1 = _num(el, "fylite:a1", _num(unit, "fylite:a1", 0.0))
    a2 = _num(el, "fylite:a2", _num(unit, "fylite:a2", 90.0))
    r, z = rectangle_corners(float(rect["r"]), float(rect["z"]), w, h, a1, a2)
    p = np.stack([r[:4], z[:4]], axis=1)          #: 四角，首点未重复
    #: 长边：h >= w 时是 u = ±w/2 的两条，否则是 v = ±h/2 的两条
    faces = ([p[[3, 0]], p[[1, 2]]] if h >= w else [p[[0, 1]], p[[3, 2]]])
    return {"faces": faces, "centre": p.mean(axis=0), "long": max(w, h)}


def _chain(group: str, plates: list[dict], tol: float) -> LayerOutline | str:
    centre = np.mean([p["centre"] for p in plates], axis=0)
    for p in plates:
        near = int(np.argmin([np.linalg.norm(f.mean(axis=0) - centre) for f in p["faces"]]))
        p["inner"], p["outer"] = p["faces"][near], p["faces"][1 - near]
    order = sorted(range(len(plates)),
                   key=lambda i: math.atan2(plates[i]["centre"][1] - centre[1],
                                            plates[i]["centre"][0] - centre[0]))
    plate_length = float(np.median([p["long"] for p in plates]))

    sides = {}
    for side in ("inner", "outer"):
        #: ★第一块板的朝向要**对着第二块**定。不定的话首尾差一整块板的长度，
        #: 而那个数看着就像一个真实的缺口 —— 实测就踩过。
        first = plates[order[0]][side]
        second = plates[order[1]][side]
        if (min(np.linalg.norm(first[0] - q) for q in second)
                < min(np.linalg.norm(first[1] - q) for q in second)):
            first = first[::-1]
        pts, gaps = [first[0], first[1]], []
        for i in order[1:]:
            f = plates[i][side]
            da, db = np.linalg.norm(f[0] - pts[-1]), np.linalg.norm(f[1] - pts[-1])
            if db < da:
                f = f[::-1]
            gap = float(min(da, db))
            gaps.append(gap)
            if gap <= tol:
                pts[-1] = (pts[-1] + f[0]) / 2.0      #: 并成一点
                pts.append(f[1])
            else:
                pts.extend([f[0], f[1]])
        close = float(np.linalg.norm(pts[0] - pts[-1]))
        gaps.append(close)
        if close <= tol:
            pts[0] = pts[-1] = (pts[0] + pts[-1]) / 2.0
        else:
            pts.append(pts[0])                        #: 直线闭合，记在 bridged 里
        sides[side] = (np.asarray(pts, dtype=float), gaps)

    worst = max(max(g for g in gaps) for _, gaps in sides.values())
    if worst > plate_length:
        return (f"{group}: 最大接头 {worst * 1000:.0f} mm 比板还长 "
                f"（{plate_length * 1000:.0f} mm）—— 那里少了一块板，"
                f"轮廓该绕过去还是直穿过去无从判断")

    gaps = sides["inner"][1] + sides["outer"][1]
    snapped = sum(1 for g in gaps if g <= tol)
    bridged = tuple(sorted((g for g in gaps if g > tol), reverse=True))
    curves = {}
    for side, (pts, _) in sides.items():
        curves[side] = Curve(pts[:, 0], pts[:, 1], name=f"{group} ({side})", group=group,
                             path=f"wall/description_2d/vessel/fylite:layer_outline/{group}")
    return LayerOutline(group=group, inner=curves["inner"], outer=curves["outer"],
                        tolerance=tol, snapped=snapped, bridged=bridged,
                        plate_length=plate_length)


def apply_layer_outlines(doc: dict, *, tolerance: float = LAYER_TOLERANCE) -> dict:
    """把层轮廓写进文档的 `wall/description_2d/*/vessel/fylite:layer_outline`。

    ★**本地名，不是 DD 名**：它是一条近似曲线，写进 `annular/outline_inner` 就是
    冒充实测几何。每条都带自己的 `fylite:approximation` 读数，被拒的层记在
    `fylite:layer_outline_refused` 里 —— 拒绝也是结论，不能不说。
    """
    outlines, refused = layer_outlines(doc, tolerance=tolerance)
    if not outlines and not refused:
        return doc
    slices = _description_2d((doc.get("wall") or {}))
    if not slices:
        return doc
    vessel = slices[0].get("vessel")
    if not isinstance(vessel, dict):
        return doc
    vessel["fylite:layer_outline"] = [
        {"fylite:group": o.group,
         "outline_inner": {"r": o.inner.r.tolist(), "z": o.inner.z.tolist()},
         "outline_outer": {"r": o.outer.r.tolist(), "z": o.outer.z.tolist()},
         "fylite:approximation": {
             "method": "plate long faces chained by poloidal angle; "
                       "end caps dropped; joints merged within the tolerance, "
                       "the rest bridged by a straight segment",
             "tolerance_m": o.tolerance, "joints": o.joints, "snapped": o.snapped,
             "bridged": list(o.bridged), "plate_length_m": o.plate_length}}
        for o in outlines]
    if refused:
        vessel["fylite:layer_outline_refused"] = list(refused)
    return doc


# --------------------------------------------------------------------------
# 画
# --------------------------------------------------------------------------

#: 每一层一个颜色。深浅两种主题下都读得出来的中间调 —— SVG 独立成文件时
#: 没有主题变量可用，所以颜色写死，背景留透明。
STYLE = {
    "limiter": ("#1b6ec2", 1.6),
    "vessel": ("#6b6f76", 1.1),
    "coils": ("#c2571b", 1.2),
    "flux_loops": ("#1a8a5a", 0.0),
    "probes": ("#8a1a7a", 0.0),
}


def render(source, out=None, *, title: str = "", width: int = 420,
           margin: float = 0.06, show_diagnostics: bool = True,
           scale_bar: bool = True) -> str:
    """截面 → 一段 SVG 文本；给了 `out` 就同时写出去。

    `width` 是像素宽，高度按几何的长宽比定 —— **不拉伸**：极向截面拉伸之后
    形状是错的，而错得看不出来。
    """
    cs = source if isinstance(source, CrossSection) else cross_section(source)
    r0, z0, r1, z1 = cs.bbox()
    dr, dz = max(r1 - r0, 1e-9), max(z1 - z0, 1e-9)
    pad = margin * max(dr, dz)
    r0, z0, r1, z1 = r0 - pad, z0 - pad, r1 + pad, z1 + pad
    dr, dz = r1 - r0, z1 - z0
    height = max(1, int(round(width * dz / dr)))
    #: 线宽按数据单位给，再由 viewBox 缩放；这样不同大小的机器画出来一样粗
    unit = max(dr, dz) / 400.0

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="{_f(r0)} {_f(-z1)} {_f(dr)} {_f(dz)}" '
        f'role="img" aria-label="{_esc(title or cs.device or "machine")} poloidal cross-section">',
        f'<title>{_esc(title or cs.device or "machine")}</title>',
        #: ★不用 `scale(1,-1)` 翻组，改成每个点写 `(r, -z)`：翻组会把文字和线宽
        #: 一起翻过去，得再翻回来一次；写坐标只此一处要记得，且导出的路径数据
        #: 与人读到的一样
        '<g fill="none" stroke-linejoin="round" stroke-linecap="round">',
    ]
    for kind in ("vessel", "limiter", "coils"):
        colour, w = STYLE[kind]
        curves = getattr(cs, kind)
        if not curves:
            continue
        parts.append(f'<g id="{kind}" stroke="{colour}" stroke-width="{_f(w * unit)}">')
        for c in curves:
            parts.append(f'<path d="{_path_d(c)}"/>')
        parts.append("</g>")
    if show_diagnostics:
        for kind in ("flux_loops", "probes"):
            colour, _ = STYLE[kind]
            pts = getattr(cs, kind)
            if not pts:
                continue
            rad = 1.5 * unit
            parts.append(f'<g id="{kind}" fill="{colour}" stroke="none">')
            for p in pts:
                parts.append(f'<circle cx="{_f(p.r)}" cy="{_f(-p.z)}" r="{_f(rad)}"/>')
            parts.append("</g>")
    if scale_bar:
        parts.append(_scale_bar(r0, z0, dr, unit))
    parts.append("</g></svg>")
    svg = "\n".join(parts) + "\n"
    if out is not None:
        Path(out).write_text(svg, encoding="utf-8")
    return svg


def _scale_bar(r0: float, z0: float, dr: float, unit: float) -> str:
    """一根一米的尺。★没有刻度轴：示意图上比例尺读得比坐标轴快，也不会被裁掉。"""
    length = 1.0
    while length > dr / 3:
        length /= 10.0
    x0, y0 = r0 + 0.06 * dr, -(z0 + 0.04 * dr)
    label = f"{length:g} m"
    return (f'<g id="scale"><path d="M {_f(x0)} {_f(y0)} h {_f(length)}" '
            f'stroke="#333" stroke-width="{_f(unit)}"/>'
            f'<text x="{_f(x0 + length / 2)}" y="{_f(y0 - 2 * unit)}" fill="#333" '
            f'stroke="none" font-size="{_f(9 * unit)}" '
            f'text-anchor="middle">{label}</text></g>')


def _path_d(c: Curve) -> str:
    r = np.asarray(c.r, dtype=float)
    z = np.asarray(c.z, dtype=float)
    d = [f"M {_f(r[0])} {_f(-z[0])}"]
    d.extend(f"L {_f(rr)} {_f(-zz)}" for rr, zz in zip(r[1:], z[1:]))
    if c.closed:
        d.append("Z")
    return " ".join(d)


def _f(v: float) -> str:
    """六位有效数字够一张示意图，且让文件可比对（同一份文档两次画出同一段文本）。"""
    s = f"{float(v):.6g}"
    return "0" if s in ("-0", "-0.0") else s


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
