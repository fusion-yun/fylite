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
