#!/usr/bin/env python3
"""Draw the front-end design previews (`FYL-DESIGN-18`).

    python tools/make-frontend-design-figures.py [-d docs/figures] [--check]

Eight drawings, all **1600 x 900 — 16:9** (V-13), each one section of
`FYL-DESIGN-18`:

    fe-input-page.svg     a page GENERATED from a scenario document: one control
                          per declared parameter, the control chosen by type
    fe-sources.svg        one input port, several sources: the source stack,
                          merge order, and where every quantity came from
    fe-geometry-edit.svg  trying a shape: LCFS handles and profile knots, the
                          ghost of the shape before the edit, tier A / tier B
    fe-composite-2d.svg   the poloidal composite: one isometric view, layers
                          switched on and off, each with a non-colour channel
    fe-profiles.svg       the profile viewer: any two quantities on a shared
                          grid, channels overlaid, a box zoom, time traces with
                          one shared cursor and one shared domain
    fe-workbench.svg      the workbench: views as tiles, moved and resized, the
                          layout written back into the presentation spec
    fe-run-checkpoint.svg a run as a sequence of steps: progress measured per
                          step, a checkpoint that is a record, resume, cancel
    fe-report.svg         the report as the projection of record + spec, the
                          same spec the workbench edited

★The shell strip is NOT drawn here.  It is imported from
`make-desktop-preview.py` and called — the rule of that file (two generators
drawing the shell would be two shells, V-11 / V-12) holds for this one.  The
palette, the helpers and the `--check` discipline are that module's as well.

★Concept drawings, not screenshots.  Nothing here exists in `app/` today; the
numbers on the drawings (step counts, milliseconds) are ILLUSTRATIVE and are
labelled as such where a reader could mistake them for measurements.  The
measured facts the design rests on are in the document's §一, not here.

Standard library only, same reason as the module it imports.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("make_desktop_preview",
                                               HERE / "make-desktop-preview.py")
M = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(M)

W, H, GUT = M.W, M.H, M.GUT
rect, text, line, btn, select, panel = M.rect, M.text, M.line, M.btn, M.select, M.panel
add, esc, slider, dshape = M.add, M.esc, M.slider, M.dshape

#: extra styles for the concept drawings — appended to the shared sheet
EXTRA = """
.tile { fill:var(--panel); stroke:var(--accent); stroke-width:1.2; }
.tile-sel { fill:var(--sel); stroke:var(--accent); stroke-width:1.6; stroke-dasharray:6 3; }
.grip { fill:var(--accent); }
.ghost { fill:none; stroke:var(--muted); stroke-width:1.6; stroke-dasharray:6 4; opacity:.8; }
.knot { fill:var(--panel); stroke:var(--lcfs); stroke-width:2; }
.knot-drag { fill:var(--lcfs); stroke:var(--panel); stroke-width:1.5; }
.coil { fill:var(--coil); opacity:.55; }
.coil-neg { fill:none; stroke:var(--coil); stroke-width:1.6; }
.probe { fill:var(--alt); }
.loop { fill:none; stroke:var(--alt); stroke-width:1.4; }
.chord { stroke:var(--warn); stroke-width:1.2; stroke-dasharray:2 3; }
.fluxl { fill:none; stroke:var(--flux); stroke-width:1.1; }
.cursor { stroke:var(--lcfs); stroke-width:1.4; }
.zoombox { fill:var(--accent); opacity:.12; stroke:var(--accent); stroke-width:1; stroke-dasharray:4 3; }
.step-done { fill:var(--accent); }
.step-ckpt { fill:var(--alt); }
.step-todo { fill:var(--grid); }
.step-cur { fill:var(--panel); stroke:var(--accent); stroke-width:2; }
.arrow { fill:none; stroke:var(--muted); stroke-width:1.4; marker-end:url(#arr); }
.arrow-a { fill:none; stroke:var(--accent); stroke-width:1.6; marker-end:url(#arra); }
.src { fill:var(--panel); stroke:var(--grid); stroke-width:1; }
.src-top { fill:var(--sel); stroke:var(--accent); stroke-width:1.2; }
.src-off { fill:var(--panel); stroke:var(--grid); stroke-width:1; stroke-dasharray:4 3; opacity:.7; }
.prov { fill:var(--head); }
.tag { fill:none; stroke:var(--muted); stroke-width:1; }
.tag-a { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.tag-b { fill:var(--pill); stroke:var(--warn); stroke-width:1; }
.sw-on { fill:var(--accent); }
.sw-off { fill:var(--grid); }
.sw-k { fill:#ffffff; }
.doc { fill:var(--panel); stroke:var(--fg); stroke-width:1; }
.doc-t { fill:var(--fg); }
.seg { fill:none; stroke:var(--grid); stroke-width:1; }
.seg-on { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.meas { fill:var(--alt); }
.ref { fill:none; stroke:var(--coil); stroke-width:1.6; stroke-dasharray:5 3; }
"""
M.STYLE = M.STYLE + EXTRA


def head(title: str, aria: str) -> None:
    M.head(title, aria)
    add('<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"'
        ' markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"'
        ' fill="var(--muted)"/></marker>'
        '<marker id="arra" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"'
        ' markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"'
        ' fill="var(--accent)"/></marker></defs>')


def strip(page: str, state: str, status: str, progress=None, handoff=None) -> None:
    """The shared strip, with slot ⑤ (run state) set for the drawing."""
    label, value = "装置", "EAST"
    M.SLOTS[page] = (label, value, state, status, handoff)
    M.strip(page, progress=progress)


def note(x, y, w, lines, cls="tag") -> float:
    h = 12 + len(lines) * 16
    rect(x, y, w, h, cls, rx=5)
    for i, s in enumerate(lines):
        text(x + 9, y + 18 + i * 16, s, "mut" if cls == "tag" else "lbl", 11)
    return y + h


def switch(x, y, on: bool, label: str) -> None:
    rect(x, y, 30, 16, "sw-on" if on else "sw-off", rx=8)
    add(f'<circle cx="{x + (22 if on else 8):.1f}" cy="{y + 8:.1f}" r="6" class="sw-k"/>')
    text(x + 38, y + 12.5, label, "lbl", 11.5)


def tag(x, y, s, cls="tag", size=10.5) -> float:
    w = len(s) * size * 0.62 + 14
    w = max(w, sum(size * (1.0 if ord(c) > 255 else 0.58) for c in s) + 14)
    rect(x, y, w, 18, cls, rx=9)
    text(x + w / 2, y + 13, s, "mut" if cls == "tag" else ("acc-t" if cls == "tag-a" else "warn-t"),
         size, "middle")
    return x + w + 6


def doc_icon(x, y, w, h, title, sub=None, cls="doc") -> None:
    add(f'<path d="M{x:.1f} {y:.1f}h{w - 12:.1f}l12 12v{h - 12:.1f}h{-w:.1f}z" class="{cls}"/>')
    add(f'<path d="M{x + w - 12:.1f} {y:.1f}v12h12" class="{cls}"/>')
    text(x + 8, y + 22, title, "doc-t", 11.5, weight="700")
    if sub:
        text(x + 8, y + 38, sub, "mut", 10.5)


def arrow(x1, y1, x2, y2, cls="arrow") -> None:
    add(f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}" class="{cls}"/>')


def ctl_range(x, y, w, label, unit, frac, value, tier="A") -> float:
    text(x, y, label, "lbl", 12)
    tag(x + w - 24, y - 13, tier, "tag-a" if tier == "A" else "tag-b", 10)
    text(x + w - 30, y, f"{value} {unit}", "acc-t", 12, "end")
    line(x, y + 14, x + w, y + 14, "track")
    line(x, y + 14, x + w * frac, y + 14, "track-on")
    add(f'<circle cx="{x + w * frac:.1f}" cy="{y + 14:.1f}" r="5.5" class="handle"/>')
    return y + 36


def ctl_number(x, y, w, label, unit, value, tier="A") -> float:
    text(x, y, label, "lbl", 12)
    tag(x + w - 24, y - 13, tier, "tag-a" if tier == "A" else "tag-b", 10)
    rect(x, y + 6, w - 60, 24, "input", rx=5)
    text(x + 8, y + 22, value, "mono", 12)
    text(x + w - 30, y + 22, unit, "mut", 11.5, "end")
    return y + 42


def ctl_enum(x, y, w, label, choices, on) -> float:
    text(x, y, label, "lbl", 12)
    cx = x
    for c in choices:
        cw = max(48, len(c) * 13 + 16)
        rect(cx, y + 6, cw, 24, "seg-on" if c == on else "seg", rx=5)
        text(cx + cw / 2, y + 22, c, "acc-t" if c == on else "mut", 11.5, "middle")
        cx += cw + 4
    return y + 42


def ctl_bool(x, y, label, on) -> float:
    switch(x, y + 2, on, label)
    return y + 40


def ctl_port(x, y, w, label, ids, sources) -> float:
    text(x, y, label, "lbl", 12)
    text(x + w, y, ids, "mono", 11, "end")
    yy = y + 8
    for i, (s, cls) in enumerate(sources):
        rect(x, yy, w, 22, cls, rx=5)
        text(x + 8, yy + 15, f"{i + 1} · {s}", "lbl" if cls != "src-off" else "mut", 11)
        yy += 25
    return yy + 8


def axes(x, y, w, h, iso=False):
    rect(x, y, w, h, "panel", rx=6)
    ax, ay, aw, ah = x + 36, y + 12, w - 48, h - 36
    if iso:
        sq = min(aw, ah)
        ax, ay = ax + (aw - sq) / 2, ay + (ah - sq) / 2
        aw = ah = sq
    rect(ax, ay, aw, ah, "axes")
    for i in range(1, 4):
        line(ax, ay + ah * i / 4, ax + aw, ay + ah * i / 4, "grid")
        line(ax + aw * i / 4, ay, ax + aw * i / 4, ay + ah, "grid")
    return ax, ay, aw, ah


def poly(ax, ay, aw, ah, pts, cls) -> None:
    d = " ".join(f"{ax + aw * u:.1f},{ay + ah * (1 - v):.1f}" for u, v in pts)
    add(f'<polyline points="{d}" class="{cls}"/>')


def closed(ax, ay, aw, ah, pts, cls) -> None:
    d = " ".join(f"{ax + aw * u:.1f},{ay + ah * (1 - v):.1f}" for u, v in pts)
    add(f'<polygon points="{d}" class="{cls}"/>')


def curve(a, b, c, n=40):
    """v(u) = a + (b - a) * (1 - u^2)^c on u in [0,1] — a profile-like shape."""
    return [(i / n, a + (b - a) * (1 - (i / n) ** 2) ** c) for i in range(n + 1)]


def flux_family(kappa=1.7, delta=0.3, n=6):
    fam = []
    for k in range(1, n + 1):
        s = k / n
        fam.append([(0.5 + 0.24 * s * math.cos(t + delta * s * math.sin(t)),
                     0.5 + 0.24 * s * kappa * math.sin(t))
                    for t in (i / 60 * 2 * math.pi for i in range(61))])
    return fam


def wall_outline():
    return [(0.5 + 0.40 * math.cos(t) * (1 + 0.08 * math.cos(2 * t)),
             0.5 + 0.46 * math.sin(t)) for t in (i / 48 * 2 * math.pi for i in range(49))]


# --------------------------------------------------------------------------- #
# 1. the input page generated from a scenario document
# --------------------------------------------------------------------------- #
def draw_input_page(d: Path) -> None:
    head("fylite 前端 — 由场景文档生成的输入页",
         "由 fyo 场景文档与控制词表生成的动态输入页概念图")
    strip("model", "ready", "定态输运 · 就绪 · 计划 transport-iter-15ma · 未改动")
    y0 = M.body_top()

    # left: the scenario document, and the vocabulary it points at
    x, w = GUT, 300
    yy = panel(x, y0, w, 380, "场景文档（计划）")
    doc_icon(x + 14, yy, 150, 52, "transport-iter-15ma", "fyo:ScenarioSpecification")
    text(x + 176, yy + 18, "prescribes_code", "mono", 10.5)
    text(x + 176, yy + 33, "code/transport", "mono", 10.5, weight="700")
    text(x + 176, yy + 48, "parameters[] · inputs[]", "mono", 10.5)
    yy += 66
    text(x + 14, yy + 14, "每条 sets_parameter 指向词表里的一条：", "mut", 11)
    yy += 26
    rows = [("code/transport#a", "double · m · [0.5, 2.5]", "范围 → 滑杆+数字"),
            ("code/transport#nr", "integer · 1 · [17, 401]", "整数 → 步进"),
            ("code/transport#closure", "enum · {fixed, neo, tglf}", "枚举 → 分段选择"),
            ("code/transport#usepedestal", "boolean", "布尔 → 开关"),
            ("code/transport#te", "array[n] on grid/rho_tor_norm", "剖面 → 节点编辑器"),
            ("port core_profiles", "fyo:core_profiles · optional", "端口 → 源栈")]
    for iri, ty, ctl in rows:
        text(x + 14, yy + 12, iri, "mono", 10.5)
        text(x + 14, yy + 25, ty, "mut", 10)
        text(x + w - 14, yy + 18, ctl, "acc-t", 10.5, "end")
        line(x + 14, yy + 32, x + w - 14, yy + 32, "sep")
        yy += 36
    note(x, y0 + 394, w, ["U-1  页面是计划的投影：一条声明一个控件，", "     没有声明的参数不得有控件。",
                          "U-2  控件由词表里的类型决定，不由页面决定。",
                          "U-4  值域三层：词表 → 装置卷宗 → 用户改。"])

    # middle: the generated form
    x2, w2 = x + w + 20, 440
    yy = panel(x2, y0, w2, H - y0 - 40, "生成的输入页 · code/transport")
    text(x2 + 14, yy + 12, "这台机器", "head-t", 12, weight="700")
    tag(x2 + 92, yy, "来自装置卷宗 ITER", "tag")
    yy += 34
    cx, cw = x2 + 14, w2 - 28
    yy = ctl_range(cx, yy, cw, "小半径 a", "m", 0.62, "1.750")
    yy = ctl_range(cx, yy, cw, "拉长比 κ", "1", 0.55, "1.90")
    yy = ctl_range(cx, yy, cw, "环向场 B₀", "T", 0.48, "5.30")
    text(x2 + 14, yy + 6, "求解", "head-t", 12, weight="700")
    yy += 24
    yy = ctl_number(cx, yy, cw, "径向网格点 nr", "1", "65")
    yy = ctl_enum(cx, yy, cw, "闭合", ["fixed", "neo", "tglf"], "neo")
    yy = ctl_bool(cx, yy, "台基（EPED1-NN）", True)
    yy = ctl_range(cx, yy, cw, "步数预算", "步", 0.3, "60", tier="C")
    text(x2 + 14, yy + 6, "输入端口", "head-t", 12, weight="700")
    yy += 24
    yy = ctl_port(cx, yy, cw, "初始剖面", "fyo:core_profiles",
                  [("MDSplus 取数文档 · EAST #138569 · 4.0 s", "src-top"),
                   ("g-file g138569.04000", "src"),
                   ("卷宗默认 · 抛物线剖面", "src-off")])
    text(x2 + 14, yy + 4, "剖面（可编辑）", "head-t", 12, weight="700")
    ax, ay, aw, ah = axes(x2 + 14, yy + 12, cw, 130)
    poly(ax, ay, aw, ah, curve(0.1, 0.9, 1.5), "c1")
    for u in (0.0, 0.3, 0.6, 0.85, 1.0):
        v = 0.1 + 0.8 * (1 - u * u) ** 1.5
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="4.5" class="knot"/>')
    text(ax + aw / 2, ay + ah + 20, "Tₑ 对 ρ_tor_norm（节点在量自己的坐标上）", "mut", 10.5, "middle")

    # right: the first output, inside the first screen
    x3 = x2 + w2 + 20
    w3 = W - GUT - x3
    yy = panel(x3, y0, w3, 420, "首屏输出 · 由呈现规格的第一个视图决定（P-26）")
    ax, ay, aw, ah = axes(x3 + 14, yy, w3 - 28, 330)
    poly(ax, ay, aw, ah, curve(0.08, 0.92, 1.4), "c1")
    poly(ax, ay, aw, ah, curve(0.06, 0.78, 1.8), "c2")
    poly(ax, ay, aw, ah, curve(0.12, 0.60, 1.1), "c3")
    text(ax + aw - 8, ay + 16, "Tₑ  Tᵢ  nₑ  对 ρ_tor_norm", "mut", 11, "end")
    text(ax + aw / 2, ay + ah + 20, "结果 · core_profiles · 每条线绑定记录里的一个量（P1）", "mut", 10.5, "middle")
    yy = y0 + 434
    yy = panel(x3, yy, w3, H - yy - 40, "读数（每个数带出处，P-13）")
    M.readings(x3 + 14, yy + 12, w3 - 28,
               [("τ_E", "3.42 s", "code/transport · 记录 r-… · 环境指纹 wasm@…"),
                ("β_N", "1.86", "同上"),
                ("台基外推距离", "0.00", "acceptance · pass")])
    M.foot("概念图 · 数值仅示意 · FYL-DESIGN-18 §四 —— 控件由词表的类型决定，页面不再手写控件")
    M.write(d, "fe-input-page.svg")


# --------------------------------------------------------------------------- #
# 2. one port, several sources
# --------------------------------------------------------------------------- #
def draw_sources(d: Path) -> None:
    head("fylite 前端 — 多数据源组合成一份输入文档",
         "一个输入端口上的源栈、合并次序与逐量出处的概念图")
    strip("analysis", "ready", "平衡反演 · 就绪 · 端口 magnetics 由 3 个源装配")
    y0 = M.body_top()

    # left column: the stack
    x, w = GUT, 420
    yy = panel(x, y0, w, 470, "端口 magnetics · 源栈（自上而下，先到先得，决胜单位是叶子）")
    srcs = [("1", "MDSplus 取数文档", "EAST #138569 · 4.0–4.2 s · 38 探针 35 磁通环", "src-top",
             "b_field_pol_probe[*].field · flux_loop[*].flux"),
            ("2", "装置 A-Box（卷宗）", "providers/magnetics/pcs.yaml · 几何", "src",
             "…[*].position · name"),
            ("3", "会话文档（上次导出）", "analysis-2026-09-03.jsonld · 权重", "src",
             "fylite:weight[*]"),
            ("—", "手填", "关闭的通道 · 只改权重", "src-off", "（未启用）")]
    for i, (n, t, s, cls, leaves) in enumerate(srcs):
        rect(x + 14, yy, w - 28, 76, cls, rx=6)
        text(x + 26, yy + 22, f"{n}  {t}", "lbl", 12.5, weight="700")
        text(x + 26, yy + 40, s, "mut", 11)
        text(x + 26, yy + 60, "给出：" + leaves, "mono", 10)
        if cls != "src-off":
            btn(x + w - 92, yy + 8, 26, 22, "↑", "btn", "mut")
            btn(x + w - 62, yy + 8, 26, 22, "↓", "btn", "mut")
        switch(x + w - 32 - 30, yy + 48, cls != "src-off", "")
        yy += 86
    note(x, y0 + 484, w, ["U-5  组合只在中间层做一次（D-3）；页面只排次序与开关。",
                          "U-6  每个量标出它来自哪一源；同名叶子由上面的源赢，",
                          "     被盖住的那一份仍列出，不静默（U-7）。",
                          "L-12 结构数组按 name 对齐合并，不按下标。"])

    # middle: the middle-layer wasm doing the merge
    x2 = x + w + 60
    doc_icon(x2, y0 + 40, 170, 60, "取数文档", "fyo:magnetics（切片）")
    doc_icon(x2, y0 + 130, 170, 60, "装置文档", "fyo:DeviceDescription")
    doc_icon(x2, y0 + 220, 170, 60, "会话文档", "fylite:AppSession/1")
    bx, by = x2 + 250, y0 + 90
    rect(bx, by, 220, 150, "panel", rx=10)
    text(bx + 110, by + 30, "fylite_runtime.wasm", "mono", 12.5, "middle", "700")
    text(bx + 110, by + 52, "assemble · merge · select", "mut", 11, "middle")
    text(bx + 110, by + 78, "L-1 一棵中立的树", "lbl", 11.5, "middle")
    text(bx + 110, by + 96, "L-12 按 name 对齐", "lbl", 11.5, "middle")
    text(bx + 110, by + 114, "fylite:assembly 记来源", "lbl", 11.5, "middle")
    text(bx + 110, by + 134, "JS 不看字节（H-5）", "mut", 11, "middle")
    for yy_ in (y0 + 70, y0 + 160, y0 + 250):
        arrow(x2 + 172, yy_, bx - 6, by + 75)
    doc_icon(bx + 280, by + 40, 190, 64, "一份输入文档", "fyo:magnetics · 绑定到端口")
    arrow(bx + 222, by + 75, bx + 274, by + 72, "arrow-a")

    # bottom right: per-quantity provenance table
    tx, ty, tw = x2, y0 + 330, W - GUT - x2
    yy = panel(tx, ty, tw, H - ty - 40, "逐量出处（U-6）—— 表是页面画的，数据是 fylite:assembly 记的")
    cols = [("量（fyo 路径）", 0), ("来自", 330), ("被盖住的", 520), ("时间选择", 690)]
    for c, dx in cols:
        text(tx + 14 + dx, yy + 12, c, "mut", 11, weight="700")
    line(tx + 14, yy + 20, tx + tw - 14, yy + 20, "sep")
    rows = [("b_field_pol_probe[3].field.data", "1 · MDSplus", "—", "4.0–4.2 s · 索引 [812:852]"),
            ("b_field_pol_probe[3].position", "2 · A-Box pcs.yaml", "—", "静态"),
            ("b_field_pol_probe[3].name", "2 · A-Box（对齐键）", "1 · 同值", "静态"),
            ("flux_loop[7].flux.data", "1 · MDSplus", "—", "4.0–4.2 s"),
            ("fylite:weight[3]", "3 · 会话文档", "—", "—"),
            ("flux_loop[12].flux.data", "（缺）· 窗里无样本，按名拒绝", "—", "L-10 点不外推")]
    ry = yy + 38
    for r in rows:
        for (c, dx), v in zip(cols, r):
            cls = "mono" if dx == 0 else ("warn-t" if "缺" in v else "lbl")
            text(tx + 14 + dx, ry, v, cls, 10.5)
        ry += 24
    M.foot("概念图 · 通道数与索引仅示意 · FYL-DESIGN-18 §五 —— 源栈排次序，中间层合并，每个量带出处")
    M.write(d, "fe-sources.svg")


# --------------------------------------------------------------------------- #
# 3. trying a shape: LCFS handles and profile knots
# --------------------------------------------------------------------------- #
def draw_geometry_edit(d: Path) -> None:
    head("fylite 前端 — 几何与剖面形状的试改",
         "LCFS 把手与剖面节点的交互试改概念图：改前的幽灵、档位与撤销")
    strip("pulse_design", "busy", "配置 · 试改 #3 · A 档预览 4 ms · 松手后 B 档求解（≈1.2 s）", progress=0.6)
    y0 = M.body_top()

    # left: the poloidal view with handles
    x, w = GUT, 560
    yy = panel(x, y0, w, H - y0 - 40, "位形 · 等比例（拖把手改参数，拖路点改轮廓）")
    ax, ay, aw, ah = axes(x + 14, yy, w - 28, H - y0 - 100, iso=True)
    closed(ax, ay, aw, ah, wall_outline(), "wall")
    # ghost: the shape before this edit
    closed(ax, ay, aw, ah, dshape(1.50, 0.30), "ghost")
    # current: the edited shape
    cur = dshape(1.70, 0.45)
    closed(ax, ay, aw, ah, cur, "lcfs")
    # parameter handles: top (kappa), outboard (a), top-outer (delta_u), bottom-outer (delta_l)
    for (u, v), lab in (((0.5, 0.5 + 0.26 * 1.70), "κ"), ((0.76, 0.5), "a"),
                        ((0.5 - 0.26 * 0.45, 0.5 + 0.26 * 1.70 * 0.72), "δᵤ"),
                        ((0.5 - 0.26 * 0.45, 0.5 - 0.26 * 1.70 * 0.72), "δₗ"),
                        ((0.5, 0.5), "R₀")):
        px, py = ax + aw * u, ay + ah * (1 - v)
        cls = "knot-drag" if lab == "κ" else "knot"
        add(f'<rect x="{px - 6:.1f}" y="{py - 6:.1f}" width="12" height="12" class="{cls}" rx="2"/>')
        text(px + 10, py - 8, lab, "lbl", 12, weight="700")
    # free waypoints on the outline
    for i in (7, 19, 31, 43, 55):
        u, v = cur[i]
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="3.6" class="knot"/>')
    # X-point marker
    px, py = ax + aw * 0.5, ay + ah * (1 - (0.5 - 0.26 * 1.70))
    add(f'<path d="M{px - 6} {py - 6}l12 12M{px + 6} {py - 6}l-12 12" class="badmark"/>')
    text(ax + aw - 8, ay + ah - 58, "灰虚线：改前（幽灵）", "mut", 11, "end")
    text(ax + aw - 8, ay + ah - 42, "红实线：本次试改", "lbl", 11, "end")
    text(ax + aw - 8, ay + ah - 26, "方把手 → 参数（R₀ a κ δᵤ δₗ）", "lbl", 11, "end")
    text(ax + aw - 8, ay + ah - 10, "圆点 → 路点（outline/r,z）", "lbl", 11, "end")
    text(ax + aw / 2, ay + ah + 20, "R–Z · 等比例强制（P-26 的图不拉伸）", "mut", 10.5, "middle")

    # middle: what the drag writes
    x2, w2 = x + w + 20, 420
    yy = panel(x2, y0, w2, 250, "拖动写进计划的是什么（H-1）")
    text(x2 + 14, yy + 14, "拖 κ 把手 →", "lbl", 12)
    text(x2 + 14, yy + 34, '{ "sets_parameter": "code/discharge#kappa",', "mono", 10.5)
    text(x2 + 14, yy + 50, '  "literal_value": 1.90 }', "mono", 10.5)
    text(x2 + 14, yy + 76, "拖路点 →", "lbl", 12)
    text(x2 + 14, yy + 96, "inputs[boundary].bound_to =", "mono", 10.5)
    text(x2 + 14, yy + 112, "  fyo:equilibrium · time_slice/boundary/outline/{r,z}", "mono", 10.5)
    text(x2 + 14, yy + 128, '  fylite:edited_from = "g138569.04000#…/outline"', "mono", 10.5)
    text(x2 + 14, yy + 156, "页面没有第二份几何：图上的形状永远是计划里那份", "mut", 11)
    text(x2 + 14, yy + 174, "（U-15）。撤销 = 回到上一版计划。", "mut", 11)
    yy = panel(x2, y0 + 264, w2, 210, "档位（D-9 · DE-LOG-04）")
    rows = [("A", "拖动中", "解析 Miller 轮廓 + 一列重算", "≤ 50 ms/帧", "tag-a"),
            ("B", "松手", "一次自由边界求解", "≈ 1.2 s（实测 65×65）", "tag-a"),
            ("C", "只按键", "退火 / 扫描", "分步 · 可中断 · 有进度", "tag-b")]
    ry = yy + 12
    for t, when, what, cost, cls in rows:
        tag(x2 + 14, ry - 12, t, cls)
        text(x2 + 52, ry, when, "lbl", 11.5, weight="700")
        text(x2 + 110, ry, what, "lbl", 11.5)
        text(x2 + w2 - 14, ry, cost, "mut", 11, "end")
        ry += 30
    text(x2 + 14, ry + 6, "滑杆与把手永远到不了 C 档；C 档只有按键。", "warn-t", 11)
    yy = panel(x2, y0 + 488, w2, H - y0 - 528, "试改历史（每一次是计划的一个版本）")
    for i, (n, s, st) in enumerate([("#1", "κ 1.62 → 1.80", "位形误差 0.041 · 超差"),
                                     ("#2", "δᵤ 0.33 → 0.45", "0.031 · 超差"),
                                     ("#3", "κ 1.80 → 1.90（当前）", "求解中…")]):
        text(x2 + 14, yy + 14 + i * 24, n, "mono", 11)
        text(x2 + 50, yy + 14 + i * 24, s, "lbl", 11.5)
        text(x2 + w2 - 14, yy + 14 + i * 24, st, "mut" if "中" in st else "warn-t", 11, "end")
    btn(x2 + 14, yy + 88, 70, 24, "采纳")
    btn(x2 + 92, yy + 88, 70, 24, "放弃")
    btn(x2 + 170, yy + 88, 90, 24, "回到 #1")

    # right: profile knots
    x3 = x2 + w2 + 20
    w3 = W - GUT - x3
    yy = panel(x3, y0, w3, 300, "剖面形状 · 节点在量自己的坐标上")
    ax, ay, aw, ah = axes(x3 + 14, yy, w3 - 28, 220)
    poly(ax, ay, aw, ah, curve(0.1, 0.8, 1.5), "ghost")
    knots = [(0.0, 0.92), (0.3, 0.84), (0.6, 0.55), (0.85, 0.30), (1.0, 0.1)]
    # pchip-ish smooth polyline through knots (illustrative)
    pts = []
    for i in range(len(knots) - 1):
        (u0, v0), (u1, v1) = knots[i], knots[i + 1]
        for k in range(11):
            s = k / 10
            sm = s * s * (3 - 2 * s)
            pts.append((u0 + (u1 - u0) * s, v0 + (v1 - v0) * sm))
    poly(ax, ay, aw, ah, pts, "c2")
    for j, (u, v) in enumerate(knots):
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="5"'
            f' class="{"knot-drag" if j == 1 else "knot"}"/>')
    text(ax + aw - 8, ay + 16, "Tₑ [keV] 对 ρ_tor_norm", "mut", 11, "end")
    text(ax + aw / 2, ay + ah + 20, "单调三次插值过节点；边界值由词表约束，负值拒绝", "mut", 10.5, "middle")
    yy = panel(x3, y0 + 314, w3, H - y0 - 354, "约束与拒绝（P-6）")
    for i, s in enumerate(["✓ 闭合、简单多边形", "✓ 在限制器之内（wall 图层）",
                           "✗ 节点 #2 使 Tₑ 非单调 —— 允许，但标出", "✗ 边界值 0.1 keV 低于词表下限 → 拒绝",
                           "拒绝画在图上，不自动修正。"]):
        text(x3 + 14, yy + 14 + i * 22, s, "warn-t" if s.startswith("✗") else ("mut" if s[0] not in "✓✗" else "ok-t"), 11.5)
    M.foot("概念图 · 数值仅示意（1.2 s 为 FYL-DESIGN-10 实测）· FYL-DESIGN-18 §八 —— 试改是计划的一次改写")
    M.write(d, "fe-geometry-edit.svg")


# --------------------------------------------------------------------------- #
# 4. the poloidal composite with layers
# --------------------------------------------------------------------------- #
def draw_composite(d: Path) -> None:
    head("fylite 前端 — 二维整合视图与图层",
         "极向截面整合视图：磁面、LCFS、装置几何、诊断各为一层，可开关，各有非颜色通道")
    strip("analysis", "ready", "平衡反演 · 完成 · 位形误差 0.0242 · 8 层中 6 层显示")
    y0 = M.body_top()

    x, w = GUT, 760
    yy = panel(x, y0, w, H - y0 - 40, "极向截面 · fyo:PoloidalSectionView · 等比例")
    ax, ay, aw, ah = axes(x + 14, yy, w - 28, H - y0 - 100, iso=True)
    # vessel + limiter
    closed(ax, ay, aw, ah, [(u * 1.06 - 0.03, v * 1.04 - 0.02) for u, v in wall_outline()], "wall")
    closed(ax, ay, aw, ah, wall_outline(), "wall")
    # PF coils
    for (u, v, s) in ((0.12, 0.88, 1), (0.88, 0.88, -1), (0.06, 0.5, 1), (0.94, 0.5, 1),
                      (0.12, 0.12, -1), (0.88, 0.12, 1), (0.3, 0.97, 1), (0.7, 0.03, -1)):
        px, py = ax + aw * u, ay + ah * (1 - v)
        rect(px - 11, py - 8, 22, 16, "coil" if s > 0 else "coil-neg", rx=2)
    # flux surfaces
    for fam in flux_family():
        closed(ax, ay, aw, ah, fam, "fluxl")
    closed(ax, ay, aw, ah, dshape(1.7, 0.3), "lcfs")
    closed(ax, ay, aw, ah, dshape(1.62, 0.33), "tgt")
    # axis + x-point
    px, py = ax + aw * 0.53, ay + ah * 0.5
    add(f'<path d="M{px - 6} {py}h12M{px} {py - 6}v12" class="okmark"/>')
    px, py = ax + aw * 0.5, ay + ah * (1 - (0.5 - 0.26 * 1.7))
    add(f'<path d="M{px - 6} {py - 6}l12 12M{px + 6} {py - 6}l-12 12" class="badmark"/>')
    # probes & loops
    for t in (i / 20 * 2 * math.pi for i in range(20)):
        u, v = 0.5 + 0.41 * math.cos(t) * (1 + 0.08 * math.cos(2 * t)), 0.5 + 0.47 * math.sin(t)
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="2.6" class="probe"/>')
    for t in (i / 8 * 2 * math.pi + 0.2 for i in range(8)):
        u, v = 0.5 + 0.44 * math.cos(t), 0.5 + 0.5 * math.sin(t)
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="4.5" class="loop"/>')
    # chords (interferometer)
    for u in (0.42, 0.5, 0.58):
        line(ax + aw * u, ay + 6, ax + aw * u, ay + ah - 6, "chord")
    text(ax + aw / 2, ay + ah + 20, "R [m] — Z [m] · 1 px : 1 px（-12 G-16 由构造关闭）", "mut", 10.5, "middle")

    # right: the layer list
    x2 = x + w + 20
    w2 = W - GUT - x2
    yy = panel(x2, y0, w2, 470, "图层（写在呈现规格里：flux_layer · structure_layer · overlay_layer）")
    layers = [("磁面 ψ 等值线", True, "细实线 · 淡", "flux_layer", "profiles_2d/psi"),
              ("LCFS", True, "粗实线 · 红", "flux_layer", "boundary/outline"),
              ("目标 / 参考轮廓", True, "虚线 · 灰", "overlay_layer", "reference"),
              ("磁轴 · X 点", True, "＋ · ×", "flux_layer", "global_quantities"),
              ("限制器 · 真空室", True, "点划线 · 灰蓝", "structure_layer", "wall/description_2d"),
              ("PF 线圈（电流填充）", True, "实心=正 · 空心=负", "structure_layer", "pf_active/coil"),
              ("磁探针 · 磁通环", False, "点 · 圈", "overlay_layer", "magnetics"),
              ("干涉仪弦", False, "点线 · 橙", "overlay_layer", "interferometer")]
    for i, (nm, on, chan, key, src) in enumerate(layers):
        ry = yy + i * 50
        switch(x2 + 14, ry + 4, on, nm)
        text(x2 + 14, ry + 34, f"非颜色通道：{chan}", "mut", 10.5)
        text(x2 + w2 - 14, ry + 14, key, "mono", 10, "end")
        text(x2 + w2 - 14, ry + 34, src, "mono", 10, "end")
        if i < len(layers) - 1:
            line(x2 + 14, ry + 44, x2 + w2 - 14, ry + 44, "sep")
    note(x2, y0 + 484, w2, ["U-16  图层即规格里的 layer 词：开关状态随规格导出，报告照画。",
                            "P-27  每层一个非颜色通道；关掉的层在图例里留一行灰字，不消失。",
                            "缺的层按名列出（如无 magnetics 文档 → 「磁探针：无数据」）。"])
    yy = panel(x2, y0 + 566, w2, H - y0 - 606, "图例（图内，跟随图层）")
    for i, (nm, on, chan, _, _) in enumerate(layers[:8]):
        cx_, cy_ = x2 + 14 + (i % 2) * (w2 / 2), yy + 14 + (i // 2) * 24
        text(cx_, cy_, ("● " if on else "○ ") + nm, "lbl" if on else "mut", 11)
    M.foot("概念图 · FYL-DESIGN-18 §八 —— 一张等比例的图，八层各自可关，每层一个非颜色通道")
    M.write(d, "fe-composite-2d.svg")


# --------------------------------------------------------------------------- #
# 5. the profile viewer and synchronized time traces
# --------------------------------------------------------------------------- #
def draw_profiles(d: Path) -> None:
    head("fylite 前端 — 剖面查看器与多时序同步",
         "剖面查看器：任选两个共格点的量作坐标轴、多信道叠加、框选缩放；时序栈共用光标与定义域")
    strip("model", "ready", "含时演化 · 完成 60/60 步 · 光标 t = 3.20 s")
    y0 = M.body_top()

    # left: the profile viewer
    x, w = GUT, 720
    yy = panel(x, y0, w, H - y0 - 40, "剖面 · 横轴与纵轴各选一个量（须共格点或有映射）")
    # axis pickers
    text(x + 14, yy + 16, "横轴", "mut", 11.5)
    select(x + 50, yy + 2, 190, 24, "ρ_tor_norm（格点）")
    text(x + 256, yy + 16, "纵轴", "mut", 11.5)
    select(x + 292, yy + 2, 150, 24, "Tₑ [keV]")
    btn(x + 452, yy + 2, 90, 24, "＋ 叠加信道")
    btn(x + 552, yy + 2, 60, 24, "复位")
    tag(x + 622, yy + 5, "对数 y", "tag")
    ax, ay, aw, ah = axes(x + 14, yy + 36, w - 28, H - y0 - 150)
    # measured points, computed line, reference dashed, envelope
    band = [(u, 0.1 + 0.8 * (1 - u * u) ** 1.5 + 0.06) for u in (i / 20 for i in range(21))]
    band += [(u, 0.1 + 0.8 * (1 - u * u) ** 1.5 - 0.06) for u in (i / 20 for i in range(20, -1, -1))]
    closed(ax, ay, aw, ah, band, "postband")
    poly(ax, ay, aw, ah, curve(0.1, 0.9, 1.5), "c1")
    poly(ax, ay, aw, ah, curve(0.12, 0.86, 1.3), "ref")
    for u in (i / 12 for i in range(13)):
        v = 0.1 + 0.8 * (1 - u * u) ** 1.5 + 0.05 * math.sin(u * 17)
        add(f'<circle cx="{ax + aw * u:.1f}" cy="{ay + ah * (1 - v):.1f}" r="3" class="meas"/>')
    # zoom box
    rect(ax + aw * 0.55, ay + ah * 0.35, aw * 0.3, ah * 0.4, "zoombox")
    text(ax + aw * 0.55 + 6, ay + ah * 0.35 + 14, "框选缩放 · 滚轮 · 双击复位", "acc-t", 10.5)
    # legend with non-colour channels
    lx, ly = ax + 12, ay + ah - 62
    text(lx, ly, "—— 计算 · code/evolve（实线）", "lbl", 11)
    text(lx, ly + 16, "- - 参考 · g-file（虚线）", "lbl", 11)
    text(lx, ly + 32, "● 测量 · Thomson #138569（点）", "lbl", 11)
    text(lx, ly + 48, "▒ 后验带 · 覆盖：68 %（P-29 写明）", "lbl", 11)
    text(ax + aw / 2, ay + ah + 20, "横轴选项来自量的容器声明的坐标集；无映射的选项灰掉并说明，不隐藏（P-3）", "mut", 10.5, "middle")

    # right: the time-trace stack
    x2 = x + w + 20
    w2 = W - GUT - x2
    yy = panel(x2, y0, w2, H - y0 - 40, "时序栈 · 同一坐标族（time）共用定义域与光标（U-17）")
    names = [("Iₚ [MA]", "c1"), ("⟨Tₑ⟩ [keV]", "c2"), ("β_N", "c3"), ("dt_capped", "c5")]
    th = (H - y0 - 40 - 70) / len(names)
    tcur = 0.53
    for i, (nm, cls) in enumerate(names):
        ax, ay, aw, ah = axes(x2 + 14, yy + i * th, w2 - 28, th - 10)
        if i == 0:
            pts = [(u, min(1, u * 3) * 0.8 + 0.05 if u < 0.33 else 0.85 - (u > 0.8) * (u - 0.8) * 3) for u in (k / 60 for k in range(61))]
        elif i == 1:
            pts = [(u, 0.1 + 0.7 * (1 - math.exp(-u * 4)) + 0.05 * math.sin(u * 30)) for u in (k / 60 for k in range(61))]
        elif i == 2:
            pts = [(u, 0.1 + 0.6 * (1 - math.exp(-u * 3))) for u in (k / 60 for k in range(61))]
        else:
            pts = [(u, 0.15 + 0.6 * (0.42 < u < 0.5)) for u in (k / 60 for k in range(61))]
        poly(ax, ay, aw, ah, pts, cls)
        text(ax + 8, ay + 14, nm, "lbl", 11)
        line(ax + aw * tcur, ay, ax + aw * tcur, ay + ah, "cursor")
        v = pts[int(tcur * 60)][1]
        add(f'<circle cx="{ax + aw * tcur:.1f}" cy="{ay + ah * (1 - v):.1f}" r="3.5" class="knot"/>')
        if i == 0:
            text(ax + aw * tcur + 6, ay + 14, "t = 3.20 s", "bad-t", 11)
        # shared zoom window
        rect(ax + aw * 0.38, ay, aw * 0.34, ah, "zoombox")
    text(x2 + 14, H - 52, "框选一格，四格同时缩放；拖光标，四格同一时刻；剖面图跟着光标换时间片。", "mut", 10.5)
    M.foot("概念图 · 曲线仅示意 · FYL-DESIGN-18 §八 —— 坐标轴来自量的坐标声明，缩放与光标按坐标族共享")
    M.write(d, "fe-profiles.svg")


# --------------------------------------------------------------------------- #
# 6. the workbench
# --------------------------------------------------------------------------- #
def draw_workbench(d: Path) -> None:
    head("fylite 前端 — 工作台",
         "工作台：视图是可移动、可缩放的瓦片，布局写回呈现规格，同一份规格驱动报告")
    strip("model", "ready", "工作台 · 6 个视图 · 布局未保存（呈现规格 v3 → v4）")
    y0 = M.body_top()

    # left: palette of available views
    x, w = GUT, 250
    yy = panel(x, y0, w, H - y0 - 40, "可用视图（按规则从记录推出 + 自组）")
    items = [("剖面 Tₑ Tᵢ nₑ", "line_chart", True), ("时序 Iₚ β_N", "line_chart", True),
             ("极向截面", "map", True), ("读数", "scalar_readout", True),
             ("χ 对 ρ", "line_chart", False), ("验收表", "acceptance", True),
             ("台基外推距离", "line_chart", False), ("＋ 自组：任选两量", "xy", False)]
    for i, (nm, kind, used) in enumerate(items):
        ry = yy + i * 44
        rect(x + 14, ry, w - 28, 36, "src-off" if used else "src", rx=5)
        text(x + 24, ry + 15, nm, "mut" if used else "lbl", 11.5)
        text(x + 24, ry + 29, kind, "mono", 9.5)
        if used:
            text(x + w - 24, ry + 22, "已在台上", "mut", 10, "end")
        else:
            text(x + w - 24, ry + 22, "拖到台上 →", "acc-t", 10, "end")
    note(x, yy + 8 * 44 + 6, w - 28 + 28 - 28 + 28 - 28, ["U-14 布局是规格的扩展词", "fylite:layout {x,y,w,h}", "Python 渲染器不认它，顺序流排"], "tag")

    # right: the 12-column grid with tiles
    gx, gw = x + w + 20, W - GUT - (x + w + 20)
    gy, gh = y0, H - y0 - 64
    rect(gx, gy, gw, gh, "panel", rx=8)
    cols = 12
    cw = gw / cols
    for c in range(1, cols):
        line(gx + cw * c, gy, gx + cw * c, gy + gh, "grid")
    rh = gh / 8
    for r in range(1, 8):
        line(gx, gy + rh * r, gx + gw, gy + rh * r, "grid")

    def tile(c0, r0, cs, rs, title, sel=False, body=None):
        tx, ty = gx + cw * c0 + 6, gy + rh * r0 + 6
        tw, th = cw * cs - 12, rh * rs - 12
        rect(tx, ty, tw, th, "tile-sel" if sel else "tile", rx=6)
        rect(tx, ty, tw, 26, "head", rx=6)
        rect(tx, ty + 18, tw, 8, "head-sq")
        text(tx + 10, ty + 17, title, "head-t", 11.5, weight="700")
        text(tx + tw - 10, ty + 17, "≡  ⤢  ×", "mut", 11, "end")
        add(f'<path d="M{tx + tw - 4} {ty + th - 12}l-8 8M{tx + tw - 4} {ty + th - 6}l-2 2" class="grip" stroke="var(--accent)" stroke-width="2"/>')
        if body:
            body(tx + 8, ty + 32, tw - 16, th - 40)
        return tx, ty, tw, th

    def b_profiles(bx, by, bw, bh):
        ax, ay, aw, ah = axes(bx, by, bw, bh)
        poly(ax, ay, aw, ah, curve(0.08, 0.92, 1.4), "c1")
        poly(ax, ay, aw, ah, curve(0.06, 0.78, 1.8), "c2")
        poly(ax, ay, aw, ah, curve(0.12, 0.60, 1.1), "c3")

    def b_section(bx, by, bw, bh):
        ax, ay, aw, ah = axes(bx, by, bw, bh, iso=True)
        closed(ax, ay, aw, ah, wall_outline(), "wall")
        for fam in flux_family(n=4):
            closed(ax, ay, aw, ah, fam, "fluxl")
        closed(ax, ay, aw, ah, dshape(1.7, 0.3), "lcfs")

    def b_traces(bx, by, bw, bh):
        ax, ay, aw, ah = axes(bx, by, bw, bh)
        poly(ax, ay, aw, ah, [(u, 0.1 + 0.7 * (1 - math.exp(-u * 4))) for u in (k / 30 for k in range(31))], "c1")
        line(ax + aw * 0.53, ay, ax + aw * 0.53, ay + ah, "cursor")

    def b_readings(bx, by, bw, bh):
        M.readings(bx, by + 14, bw, [("τ_E", "3.42 s", None), ("β_N", "1.86", None), ("q₉₅", "3.1", None)])

    def b_accept(bx, by, bw, bh):
        for i, (k, v, c) in enumerate([("balance_worst", "9.8e-13", "ok-t"), ("dt_capped", "0", "ok-t"),
                                        ("ped_extrapolation", "0.49", "warn-t"), ("settled", "[TBD]", "mut")]):
            text(bx, by + 16 + i * 20, k, "mono", 10.5)
            text(bx + bw, by + 16 + i * 20, v, c, 10.5, "end")

    tile(0, 0, 5, 4, "剖面 · Tₑ Tᵢ nₑ 对 ρ", body=b_profiles)
    tile(5, 0, 4, 5, "极向截面 · 6 层", body=b_section)
    tx, ty, tw, th = tile(9, 0, 3, 2, "读数", body=b_readings)
    tile(9, 2, 3, 3, "验收", body=b_accept)
    tile(0, 4, 5, 4, "时序 · Iₚ（光标共享）", sel=True, body=b_traces)
    tile(5, 5, 7, 3, "剖面 · χ 对 ρ（拖入中…）", body=None)
    text(gx + cw * 5 + 20, gy + rh * 5 + 60, "松手落在 (5, 5, 7×3)；写回 fylite:layout", "acc-t", 11)
    text(gx + 10, gy + gh + 16, "12 列栅格 · 拖标题移动 · 拖右下角缩放 · 首行第一块是首屏输出（P-26）", "mut", 10.5)
    M.foot("概念图 · FYL-DESIGN-18 §八 —— 工作台编辑的是呈现规格，不是图片")
    M.write(d, "fe-workbench.svg")


# --------------------------------------------------------------------------- #
# 7. a run as steps: progress, checkpoint, resume, cancel
# --------------------------------------------------------------------------- #
def draw_run(d: Path) -> None:
    head("fylite 前端 — 执行进度、断点与恢复",
         "运行是一串门调用：每步交回状态，进度按步实测，断点是一份记录，恢复是再入")
    strip("model", "busy", "含时演化 · 第 23/60 步 · 每步 36 ms（实测）· 剩余约 1.3 s（报出，不承诺）",
          progress=23 / 60)
    y0 = M.body_top()

    # top: the step ribbon
    x, w = GUT, W - 2 * GUT
    yy = panel(x, y0, w, 150, "步带 · 计划字段 fylite:step_budget = 60（S-3）· 每步一次门调用，状态随记录进出（S-4）")
    n = 60
    sw = (w - 28) / n
    for i in range(n):
        sx = x + 14 + sw * i
        cls = "step-done" if i < 23 else ("step-cur" if i == 23 else "step-todo")
        if i in (10, 20) and i < 23:
            cls = "step-ckpt"
        rect(sx + 1, yy + 10, sw - 2, 26, cls, rx=2)
    text(x + 14, yy + 56, "■ 已算   ■ 断点（记录已落 IndexedDB）   □ 当前   ░ 未算", "mut", 11)
    text(x + 14 + sw * 10, yy + 74, "▲ ckpt @10", "ok-t", 10.5, "middle")
    text(x + 14 + sw * 20, yy + 74, "▲ ckpt @20", "ok-t", 10.5, "middle")
    text(x + 14 + sw * 23, yy + 90, "▲ 现在（第 24 次调用在内核里）", "acc-t", 10.5, "middle")
    text(x + w - 14, yy + 56, "取消 = 把剩余预算切到 0，本步结束即停（U-9）；不 terminate", "warn-t", 11, "end")
    text(x + w - 14, yy + 74, "硬中断（仅当一步超预算 ×10）= terminate + 重放 init，标为「硬」", "mut", 10.5, "end")

    # middle-left: the call sequence
    x2, w2 = GUT, 700
    yy = panel(x2, y0 + 164, w2, H - y0 - 204, "一步的往返（H-5 · F-2）")
    seq = [("页面", "计划 + fylite:state(k) → 中间层 wasm", "编码为四段扁平树"),
           ("中间层", "字节 → 内核 wasm", "JS 不看字节"),
           ("内核", "code/evolve · 1 步 · 建树交回", "无状态；状态在树里（S-1 / S-2）"),
           ("中间层", "解码 → 记录(k+1) · fylite:state(k+1)", "只搬不改（S-5 ③）"),
           ("页面", "画增量 · 更新进度 · 每 10 步落断点", "策略归宿主（S-5 ④⑤）")]
    for i, (who, what, why) in enumerate(seq):
        ry = yy + 10 + i * 58
        rect(x2 + 14, ry, 90, 40, "src-top" if who == "页面" else ("src" if who == "中间层" else "doc"), rx=6)
        text(x2 + 59, ry + 25, who, "lbl", 12, "middle", "700")
        text(x2 + 120, ry + 17, what, "lbl", 11.5)
        text(x2 + 120, ry + 33, why, "mut", 10.5)
        if i < len(seq) - 1:
            arrow(x2 + 59, ry + 42, x2 + 59, ry + 56)
    text(x2 + 14, yy + 10 + 5 * 58 + 6, "N 步一次调用 ≡ k 步 + 恢复(N−k) 步，逐位相同 —— 这是断点闸的判据。", "acc-t", 11)
    text(x2 + 14, yy + 10 + 5 * 58 + 26, "进度不来自回调（门上没有回调）：它是页面数出来的调用次数与量出来的每步耗时。", "mut", 11)

    # right: the checkpoint store and resume
    x3 = x2 + w2 + 20
    w3 = W - GUT - x3
    yy = panel(x3, y0 + 164, w3, 250, "断点 = 记录（U-10）· IndexedDB fylite:checkpoints")
    rows = [("evolve-flattop · @20", "r-…c4a1 · state 7.9 KiB · wasm sha256 3f9a…", "恢复"),
            ("evolve-flattop · @10", "r-…b210 · state 7.9 KiB · wasm sha256 3f9a…", "恢复"),
            ("transport-steady · 完成", "r-…9e77 · 无状态（单步 code）", "打开"),
            ("evolve-east-hmode · @400", "r-…1d02 · wasm sha256 77c0… ≠ 当前", "拒绝 · S-6")]
    for i, (a, b, act) in enumerate(rows):
        ry = yy + 10 + i * 52
        text(x3 + 14, ry + 14, a, "lbl", 12, weight="700")
        text(x3 + 14, ry + 30, b, "mono", 10)
        cls = "btn-a" if act in ("恢复", "打开") else "btn"
        rect(x3 + w3 - 84, ry + 4, 70, 24, cls, rx=5)
        text(x3 + w3 - 49, ry + 20, act, "btn-at" if cls == "btn-a" else "warn-t", 11.5, "middle")
        if i < 3:
            line(x3 + 14, ry + 44, x3 + w3 - 14, ry + 44, "sep")
    yy = panel(x3, y0 + 428, w3, H - y0 - 468, "移步（U-19）· 同一份文档集在别处继续")
    doc_icon(x3 + 14, yy + 6, 150, 56, "bundle.zip", "plan · inputs · record@20")
    text(x3 + 14, yy + 84, "→ 桌面：fy case run plan.jsonld --resume record.jsonld", "mono", 10.5)
    text(x3 + 14, yy + 104, "→ Python：cases.run(plan, resume=record)", "mono", 10.5)
    text(x3 + 14, yy + 124, "→ 另一台浏览器：导入即认（按内容识别，不问文件名）", "mono", 10.5)
    text(x3 + 14, yy + 150, "断点带着写它的内核身份；别的内核拒绝，除非显式开关并记入记录。", "mut", 10.5)
    M.foot("概念图 · 36 ms/步为 evolve-default 语料实测（_manifest/evolve.jsonld），其余数值示意 · FYL-DESIGN-18 §六")
    M.write(d, "fe-run-checkpoint.svg")


# --------------------------------------------------------------------------- #
# 8. the report as a projection
# --------------------------------------------------------------------------- #
def draw_report(d: Path) -> None:
    head("fylite 前端 — 报告是记录与呈现规格的投影",
         "报告页：记录 + 呈现规格 → 五节 MyST 与 SVG；工作台改的是同一份规格")
    M.SLOTS["report"] = ("装置", "EAST", "ready", "报告 · 记录 r-…c4a1 · 规格 v4（来自工作台）", None)
    M.PAGE_TITLE["report"] = ("算例报告", "记录的投影 · 不内联数组 · 不重新评判")
    M.strip("report")
    y0 = M.body_top()

    # left: the inputs
    x, w = GUT, 330
    yy = panel(x, y0, w, 300, "输入（三份文档，按 type 认，不按文件名）")
    doc_icon(x + 14, yy + 6, 140, 56, "plan.jsonld", "fyo:ScenarioSpecification")
    doc_icon(x + 170, yy + 6, 140, 56, "record.jsonld", "spo:ComputationRecord")
    doc_icon(x + 14, yy + 80, 296, 56, "presentation.jsonld", "spo:PresentationSpecification · v4 · fylite:layout")
    text(x + 14, yy + 160, "规格来源三选一（U-12）：", "lbl", 11.5)
    text(x + 14, yy + 180, "① 场景自带（presents 指向计划）", "mut", 11)
    text(x + 14, yy + 198, "② 工作台改过的（导出时写回）", "mut", 11)
    text(x + 14, yy + 216, "③ 都没有 → 按规则推出（casereport 现行）", "mut", 11)
    text(x + 14, yy + 244, "两端推出同一份规格：validate-report.mjs 逐字段比", "acc-t", 10.5)
    yy = panel(x, y0 + 314, w, H - y0 - 354, "导出（U-18 文档集）")
    for i, s in enumerate(["report.md（五节，同 report-template）", "figures/fig-NN.svg（手写 SVG）",
                           "presentation.jsonld（画时依据）", "record.jsonld（正本；报告是投影）",
                           "plan.jsonld · inputs/…（可再跑）", "environment.json（内核身份 · K-7）"]):
        text(x + 14, yy + 14 + i * 22, "▸ " + s, "lbl", 11.5)
    text(x + 14, yy + 14 + 6 * 22 + 8, "一个 zip；导入时按内容识别每一份（appio sniff）。", "mut", 10.5)

    # right: the rendered report
    x2 = x + w + 20
    w2 = W - GUT - x2
    rect(x2, y0, w2, H - y0 - 40, "panel", rx=8)
    tx = x2 + 40
    text(tx, y0 + 40, "ITER 15 MA 平顶 · 含时演化 · 报告", "title", 20, weight="700")
    text(tx, y0 + 62, "正本为记录 r-…c4a1；本报告是其投影 · 2026-09-04", "mut", 11.5)
    sec_y = y0 + 96
    sections = [("1  摘要", ["code/evolve · 60 步 · 验收 conditional（台基外推 0.49）· 内核 wasm 3f9a…"]),
                ("2  方法", ["参数表（记录原文）· 输入按端口引用（不复制数组）· 源栈三层"]),
                ("3  结果", None),
                ("4  验收", ["balance_worst 9.8e-13 pass · dt_capped 0 pass · ped_extrapolation 0.49 conditional · settled [TBD]"]),
                ("5  复现性", ["环境指纹 · 落盘工件 sha256 · 重放入口 · 规格 v4"])]
    for name, lines in sections:
        text(tx, sec_y, name, "lbl", 14, weight="700")
        sec_y += 22
        if lines:
            for s in lines:
                text(tx, sec_y, s, "mut", 11.5)
                sec_y += 20
            sec_y += 8
        else:
            # the figures, in the workbench's layout order
            fx, fy = tx, sec_y
            fw = (w2 - 80 - 24) / 3
            ax, ay, aw, ah = axes(fx, fy, fw, 170)
            poly(ax, ay, aw, ah, curve(0.08, 0.92, 1.4), "c1")
            poly(ax, ay, aw, ah, curve(0.06, 0.78, 1.8), "c2")
            text(ax + aw / 2, ay + ah + 18, "图 1 · 剖面 Tₑ Tᵢ 对 ρ_tor_norm", "mut", 10.5, "middle")
            ax, ay, aw, ah = axes(fx + fw + 12, fy, fw, 170, iso=True)
            closed(ax, ay, aw, ah, wall_outline(), "wall")
            for fam in flux_family(n=4):
                closed(ax, ay, aw, ah, fam, "fluxl")
            closed(ax, ay, aw, ah, dshape(1.7, 0.3), "lcfs")
            text(fx + fw + 12 + fw / 2, fy + 170 + 18, "图 2 · 极向截面（6 层，与工作台一致）", "mut", 10.5, "middle")
            ax, ay, aw, ah = axes(fx + 2 * fw + 24, fy, fw, 170)
            poly(ax, ay, aw, ah, [(u, 0.1 + 0.7 * (1 - math.exp(-u * 4))) for u in (k / 30 for k in range(31))], "c1")
            text(fx + 2 * fw + 24 + fw / 2, fy + 170 + 18, "图 3 · 时序 Iₚ 对 time", "mut", 10.5, "middle")
            sec_y = fy + 170 + 34
            text(tx, sec_y, "表 1 · 结果量摘要（形状 / dtype / min / max / mean / sha256 前 12 位）—— 不内联数组", "mut", 11.5)
            sec_y += 30
    text(x2 + w2 - 14, H - 52, "浏览器 casereport.js 与 Python casereport.py 画同一份规格，图是 SVG", "acc-t", 10.5, "end")
    M.foot("概念图 · FYL-DESIGN-18 §七 —— 报告不重新评判、不内联数组；它画的是工作台交回的那份规格")
    M.write(d, "fe-report.svg")


NAMES = ["fe-input-page", "fe-sources", "fe-geometry-edit", "fe-composite-2d",
         "fe-profiles", "fe-workbench", "fe-run-checkpoint", "fe-report"]
DRAWERS = [draw_input_page, draw_sources, draw_geometry_edit, draw_composite,
           draw_profiles, draw_workbench, draw_run, draw_report]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", default="docs/figures", type=Path)
    ap.add_argument("--check", action="store_true",
                    help="fail if what is on disk differs from what would be written")
    a = ap.parse_args()
    if a.check:
        M.CHECK = {}
    else:
        a.dir.mkdir(parents=True, exist_ok=True)
    print("前端设计预览图（16:9，viewBox 无固定尺寸）：")
    for fn in DRAWERS:
        fn(a.dir)
    if M.CHECK is not None:
        stale = [k for k, v in M.CHECK.items() if v]
        if stale:
            raise SystemExit("生成物已漂移，请重跑 tools/make-frontend-design-figures.py：\n  "
                             + "\n  ".join(stale))
        print(f"{len(M.CHECK)} 张预览图与生成器一致。")


if __name__ == "__main__":
    main()
