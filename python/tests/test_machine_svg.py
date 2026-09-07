"""通用装置截面图（:mod:`fylite.machine_svg`）的闸子。

★★一张图最容易撒的谎是「看着像那么回事」。所以这里查的不是「画出来了吗」，
而是四件具体的事：坐标**是文档里那些数**、矩形**按内核的同一个映射**展开、
`viewBox` **框得住每一个点**（没有画到框外去的线）、以及这个模块**不引入绘图依赖**。
"""
from __future__ import annotations

import ast
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from fylite import machine_svg

SVG_NS = "{http://www.w3.org/2000/svg}"

#: 一台合成的机器：DD 的四种写法各一份 —— 限制器折线、环状真空室的内外轮廓、
#: 元件轮廓、参数化矩形（带倾角）。真装置文档不在本仓，闸子不该依赖另一个仓的检出。
FIXTURE = {
    "@type": "fyo:DeviceDescription",
    "fylite:device_id": "synthetic",
    "wall": {
        "description_2d": [{
            "limiter": {"unit": [{"name": "first wall",
                                  "outline": {"r": [1.2, 2.3, 2.3, 1.2, 1.2],
                                              "z": [-1.0, -1.0, 1.0, 1.0, -1.0]}}]},
            "vessel": {"unit": [
                {"name": "annular shell",
                 "annular": {"outline_inner": {"r": [1.0, 2.5, 2.5, 1.0, 1.0],
                                               "z": [-1.2, -1.2, 1.2, 1.2, -1.2]},
                             "outline_outer": {"r": [0.9, 2.6, 2.6, 0.9, 0.9],
                                               "z": [-1.3, -1.3, 1.3, 1.3, -1.3]}}},
                {"name": "tilted plate", "fylite:a1": 0.0, "fylite:a2": 93.743,
                 "element": [{"geometry": {"geometry_type": "rectangle",
                                           "rectangle": {"r": 2.7286, "z": 0.0833,
                                                         "width": 0.008, "height": 0.1666}}}]},
                {"name": "already an outline",
                 "element": [{"outline": {"r": [2.0, 2.1, 2.1, 2.0, 2.0],
                                          "z": [0.0, 0.0, 0.1, 0.1, 0.0]}}]},
            ]},
        }],
    },
    "pf_active": {"coil": [
        {"name": "PF1", "element": [{"fylite:a1": 0.0, "fylite:a2": 90.0,
                                     "geometry": {"geometry_type": "rectangle",
                                                  "rectangle": {"r": 0.6, "z": 0.25,
                                                                "width": 0.15, "height": 0.44}}}]},
    ]},
    "magnetics": {
        "flux_loop": [{"name": "FL1", "position": [{"r": 1.27, "z": 0.0}]}],
        "b_field_pol_probe": [{"name": "BP1", "position": {"r": 1.29, "z": 0.0005}}],
    },
}


def _cs():
    return machine_svg.cross_section(FIXTURE)


def test_every_geometry_form_in_the_fixture_is_read():
    """四种写法各读出来一条，一条也不多。"""
    cs = _cs()
    assert cs.device == "synthetic"
    assert cs.counts() == {"limiter": 1, "vessel": 4, "coils": 1,
                           "flux_loops": 1, "probes": 1}
    #: 环状那一支给出内外两条，其余每个元件一条
    assert [c.name for c in cs.vessel] == ["annular shell", "annular shell",
                                           "tilted plate", "already an outline"]


def test_the_coordinates_are_the_numbers_in_the_document():
    cs = _cs()
    lim = cs.limiter[0]
    assert np.array_equal(lim.r, np.asarray([1.2, 2.3, 2.3, 1.2, 1.2]))
    assert np.array_equal(lim.z, np.asarray([-1.0, -1.0, 1.0, 1.0, -1.0]))
    assert lim.closed
    assert cs.probes[0].r == 1.29 and cs.probes[0].z == 0.0005
    assert cs.flux_loops[0].r == 1.27


def test_a_rectangle_opens_into_the_corners_the_kernel_would_fill():
    """展开用的是内核 `kernels::element_filaments` 的同一个映射。

    ★这里**不**照抄实现里的常数，而是从文档里的 `r/z/width/height/a2` 独立算一遍
    ——照抄的话，两边一起错也照样绿。
    """
    tilted = next(c for c in _cs().vessel if c.name == "tilted plate")
    r0, z0, w, h, a2 = 2.7286, 0.0833, 0.008, 0.1666, math.radians(93.743)
    assert len(tilted.r) == 5 and tilted.closed
    for i, (u, v) in enumerate([(-w / 2, -h / 2), (w / 2, -h / 2),
                                (w / 2, h / 2), (-w / 2, h / 2)]):
        assert tilted.r[i] == pytest.approx(r0 + u + v * math.cos(a2), abs=1e-12)
        assert tilted.z[i] == pytest.approx(z0 + v * math.sin(a2), abs=1e-12)


def test_a_tilt_actually_moves_the_corners():
    """★闸子的前提：倾角当作 90° 处理时上一条也会过——所以这里钉住两者不同。"""
    upright = machine_svg.rectangle_corners(2.7286, 0.0833, 0.008, 0.1666, 0.0, 90.0)
    tilted = machine_svg.rectangle_corners(2.7286, 0.0833, 0.008, 0.1666, 0.0, 93.743)
    assert not np.array_equal(upright[0], tilted[0])


def test_the_svg_parses_and_holds_every_layer():
    svg = machine_svg.render(FIXTURE, title="Synthetic")
    root = ET.fromstring(svg)
    assert root.tag == f"{SVG_NS}svg"
    ids = {g.get("id") for g in root.iter(f"{SVG_NS}g")}
    assert {"limiter", "vessel", "coils", "flux_loops", "probes", "scale"} <= ids
    assert root.findtext(f"{SVG_NS}title") == "Synthetic"
    assert len(list(root.iter(f"{SVG_NS}circle"))) == 2      #: 一个环、一个探针


def test_the_view_box_frames_every_point():
    """框外的线是一条画了却看不见的线 —— 比画错更难发现。"""
    cs = _cs()
    svg = machine_svg.render(cs)
    x, y, w, h = (float(v) for v in ET.fromstring(svg).get("viewBox").split())
    r0, z0, r1, z1 = cs.bbox()
    assert x <= r0 and x + w >= r1
    #: SVG 的 y 是 -z
    assert y <= -z1 and y + h >= -z0


def test_the_aspect_ratio_is_not_stretched():
    """极向截面拉伸之后形状是错的，而错得看不出来。"""
    svg = machine_svg.render(FIXTURE, width=300)
    root = ET.fromstring(svg)
    _, _, w, h = (float(v) for v in root.get("viewBox").split())
    px_w, px_h = float(root.get("width")), float(root.get("height"))
    assert px_w / px_h == pytest.approx(w / h, rel=0.01)


def test_rendering_is_reproducible(tmp_path):
    """同一份文档两次画出同一段文本 —— 图进了仓就要能对比，不能每次都变。"""
    a = machine_svg.render(FIXTURE, tmp_path / "a.svg")
    b = machine_svg.render(FIXTURE, tmp_path / "b.svg")
    assert a == b == (tmp_path / "a.svg").read_text(encoding="utf-8")


def test_an_empty_document_draws_nothing_rather_than_guessing():
    cs = machine_svg.cross_section({"wall": {}})
    assert cs.is_empty()
    root = ET.fromstring(machine_svg.render(cs))
    assert not list(root.iter(f"{SVG_NS}path")) or {
        g.get("id") for g in root.iter(f"{SVG_NS}g")} <= {None, "scale"}


def test_the_module_takes_no_plotting_dependency():
    """★本包的运行期依赖只有 numpy。这道闸读 **AST**，与环境里装了什么无关。"""
    src = Path(machine_svg.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "math", "dataclasses", "pathlib", "numpy"}, (
        f"machine_svg 引入了新的依赖：{sorted(imported)}")


# --------------------------------------------------------------------------
# 层轮廓 —— 唯一的近似产物，所以查得比别处细
# --------------------------------------------------------------------------

def _ring(n: int, *, r0: float = 2.0, a: float = 0.5, gap: float = 0.0,
          group: str = "shell", thickness: float = 0.01) -> dict:
    """一圈 `n` 块壳板：每块沿环切向长 `L`，径向厚 `thickness`，块间留 `gap`。

    ★合成的，不是哪台机器 —— 但它复现真装置的那个要害：**板的长轴一半在
    `height` 上、一半在 `width` 上**（顶底与内外侧的板朝向不同）。按字段名挑
    长边的实现在这条 fixture 上会挑错一半。
    """
    import math as _m
    units = []
    step = 2 * _m.pi / n
    length = 2 * _m.pi * a / n - gap
    for i in range(n):
        th = i * step
        r, z = r0 + a * _m.cos(th), a * _m.sin(th)
        #: 板的长轴与半径垂直：切向角 = th + 90°
        tangent = _m.degrees(th) + 90.0
        upright = abs(_m.sin(th)) < 0.5          #: 内外侧的板：长轴偏竖直
        if upright:
            rect = {"r": r, "z": z, "width": thickness, "height": length}
            a2 = tangent
        else:                                     #: 顶底的板：长轴在 width 上
            rect = {"r": r, "z": z, "width": length, "height": thickness}
            a2 = 90.0
        units.append({"fylite:group": group, "fylite:a1": 0.0, "fylite:a2": a2,
                      "element": [{"geometry": {"geometry_type": "rectangle",
                                                "rectangle": rect}}]})
    return {"wall": {"description_2d": [{"vessel": {"unit": units}}]}}


def test_a_ring_of_plates_becomes_two_closed_contours():
    outs, refused = machine_svg.layer_outlines(_ring(24))
    assert not refused and len(outs) == 1
    o = outs[0]
    assert o.group == "shell"
    assert o.inner.closed and o.outer.closed
    assert o.joints == 2 * 24, "内外各 24 个接头（含首尾那个）"
    #: 内轮廓整条比外轮廓离环心近
    import numpy as _np
    centre = _np.array([2.0, 0.0])
    ri = _np.linalg.norm(_np.stack([o.inner.r, o.inner.z], 1) - centre, axis=1)
    ro = _np.linalg.norm(_np.stack([o.outer.r, o.outer.z], 1) - centre, axis=1)
    assert ri.mean() < ro.mean(), "内外两条轮廓弄反了"


def _frame(side: float = 1.0, t: float = 0.1, r0: float = 2.0) -> dict:
    """四块板围成的方框，**外侧四角逐位重合**。

    ★上面那个圆环是「差不多挨着」的一般情形；这一个是「正好挨着」的精确情形，
    两者查的是容差的两侧。方框的**内**侧四角差一个斜接口（0.1414 m），所以同一份
    fixture 上「并成一点」与「跨过去」各出现四次。
    """
    h = side / 2
    units = [
        {"fylite:group": "frame", "fylite:a2": 90.0,      #: 上
         "element": [{"geometry": {"rectangle": {"r": r0, "z": h - t / 2,
                                                 "width": side, "height": t}}}]},
        {"fylite:group": "frame", "fylite:a2": 90.0,      #: 下
         "element": [{"geometry": {"rectangle": {"r": r0, "z": -(h - t / 2),
                                                 "width": side, "height": t}}}]},
        {"fylite:group": "frame", "fylite:a2": 90.0,      #: 左
         "element": [{"geometry": {"rectangle": {"r": r0 - h + t / 2, "z": 0.0,
                                                 "width": t, "height": side}}}]},
        {"fylite:group": "frame", "fylite:a2": 90.0,      #: 右
         "element": [{"geometry": {"rectangle": {"r": r0 + h - t / 2, "z": 0.0,
                                                 "width": t, "height": side}}}]},
    ]
    return {"wall": {"description_2d": [{"vessel": {"unit": units}}]}}


def test_ends_that_coincide_are_merged_and_the_rest_are_bridged():
    """★容差做的正是这一件事。方框外圈四角逐位重合，内圈四角差一个斜接口。"""
    o = machine_svg.layer_outlines(_frame())[0][0]
    assert o.joints == 8
    assert o.snapped == 4, "外圈四角重合，该并成一点"
    assert len(o.bridged) == 4
    for g in o.bridged:
        assert g == pytest.approx(math.hypot(0.1, 0.1), abs=1e-12), "内圈的斜接口"
    assert o.outer.closed and o.inner.closed


def test_the_tolerance_is_the_only_knob_and_it_bites():
    """容差不是装饰：放宽它，并掉的接头变多、轮廓的点数变少。"""
    doc = _ring(24)
    tight = machine_svg.layer_outlines(doc, tolerance=0.001)[0][0]
    loose = machine_svg.layer_outlines(doc, tolerance=0.05)[0][0]
    assert loose.snapped > tight.snapped
    assert len(loose.inner.r) < len(tight.inner.r)
    #: ★默认就是用户裁定的那个数，不是随手一个
    assert machine_svg.LAYER_TOLERANCE == 0.005
    assert machine_svg.layer_outlines(doc)[0][0].snapped == tight.snapped


def test_a_layer_with_plates_missing_is_refused_rather_than_guessed():
    """★一个比板还长的接头 = 那里少了板。轮廓该绕过去还是直穿过去无从判断。"""
    doc = _ring(12)
    units = doc["wall"]["description_2d"][0]["vessel"]["unit"]
    del units[3:5]
    outs, refused = machine_svg.layer_outlines(doc)
    assert not outs and len(refused) == 1
    assert "shell" in refused[0]


def test_the_default_picture_draws_the_data_not_the_approximation():
    doc = _ring(24)
    assert machine_svg.cross_section(doc).counts()["vessel"] == 24
    assert machine_svg.cross_section(doc, layers=True).counts()["vessel"] == 2


def test_the_outline_goes_under_a_local_name_with_its_own_reading():
    """★★近似产物**不许**写进 `annular/outline_inner` —— 那是实测几何的位置。"""
    doc = machine_svg.apply_layer_outlines(_ring(24, gap=0.02))
    vessel = doc["wall"]["description_2d"][0]["vessel"]
    assert "fylite:layer_outline" in vessel
    assert "annular" not in vessel
    entry = vessel["fylite:layer_outline"][0]
    assert set(entry) == {"fylite:group", "outline_inner", "outline_outer",
                          "fylite:approximation"}
    approx = entry["fylite:approximation"]
    assert approx["tolerance_m"] == machine_svg.LAYER_TOLERANCE == 0.005
    assert approx["snapped"] + len(approx["bridged"]) == approx["joints"]
    assert approx["method"]


def test_a_refused_layer_is_recorded_rather_than_left_out_silently():
    doc = _ring(12)
    del doc["wall"]["description_2d"][0]["vessel"]["unit"][3:5]
    out = machine_svg.apply_layer_outlines(doc)
    vessel = out["wall"]["description_2d"][0]["vessel"]
    assert vessel.get("fylite:layer_outline_refused")
    assert "fylite:layer_outline" not in vessel or not vessel["fylite:layer_outline"]
