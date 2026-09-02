#!/usr/bin/env python3
"""Draw the desktop app's shell previews (`FYL-DESIGN-11`).

    python tools/make-desktop-preview.py [-d docs/figures]

Twelve drawings, all **1600 x 900 — 16:9**, which is the desktop viewer's own
default measure (V-13):

    desktop-shell.svg           the shared header toolbar, annotated, with the
                                MEASURED fold diagram of the four pages under it
    desktop-data.svg            \\
    desktop-pulse-design.svg     |  one first screen per function page, each
    desktop-model.svg            |  carrying the SAME strip
    desktop-analysis.svg        /

    pd-config.svg               \\  the pulse-design page in each of its three
    pd-design.svg                |  modes (`FYL-DESIGN-09` D-18) — the same
    pd-sim.svg                  /   strip, and three different meanings of time
    pd-vocab.svg                \\  one visual vocabulary per page: every state
    model-vocab.svg              |  the page draws, with the channel it uses
    an-vocab.svg                 |  BESIDES colour, and the decision it comes
    data-vocab.svg              /   from (`FYL-DESIGN-10` P-27)

★The mode drawings live here and not in a second generator **on purpose**: they
have to carry the same `strip()` as the four page previews.  Two files drawing
the shell would be two shells, which is the failure V-11 and V-12 exist to
prevent — and a drawing that contradicts the decision it illustrates is worse
than no drawing.

★**No `width` / `height` attributes, only a `viewBox`.**  An SVG that declares
both has an intrinsic size and stops at it; one that declares neither takes the
width it is given and keeps 16:9.  That is what "scalable" has to mean here —
the same file has to read on a docs page at 700 px, in a `file://` tab at
full width, and in a slide.  The existing page figures (`make-app-figures.py`)
DO declare both; they are a different kind of drawing (tall wireframes with a
natural size) and are not changed by this file.

★**A concept drawing, not a screenshot.**  The strip drawn here does not exist
yet — it is what V-11 argues for.  What IS measured is the fold diagram in
`desktop-shell.svg`: those four page heights, the toolbar offsets and the
first-output offsets come from a 1600x900 run of the real pages, and they are
the evidence for the decision.  Numbers live in `MEASURED` below, in one place,
so the drawing cannot disagree with the prose that cites them.

Standard library only, deliberately: a docs figure must not add a dependency to
a repository whose runtime dependency is numpy alone.
"""
from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

W, H = 1600, 900                      # 16:9 — the desktop's default measure

# --------------------------------------------------------------------------- #
# The shell's geometry.  One table, because the five drawings must agree about
# it: a preview whose strip is 84 px on one page and 92 px on the next is a
# picture of two shells.
# --------------------------------------------------------------------------- #
ROW1_H = 40                           # identity and destinations
ROW2_H = 41                           # this page's work
PROG_H = 3                            # the progress line, on the bottom edge
STRIP_H = ROW1_H + ROW2_H + PROG_H    # = 84
PAD = 18                              # the strip's own side padding
GUT = 26                              # the body's side margin

#: Measured on the real pages at 1600x900 (2026-09-01).  See FYL-DESIGN-11
#: §今天的外壳.  `first_out` is the first canvas/table taller than 40 px;
#: `toolbar` is `.panel.toolbar`, absent on the data page.
MEASURED = [
    # id,            label,        doc_h, toolbar_y, first_bar_y, first_out_y
    ("data",         "装置数据",     3844, None,  None, None),
    ("pulse_design", "放电设计",     2212,  386,  1265, None),
    ("model",        "物理建模",     6364,  277,   971, 1327),
    ("analysis",     "实验分析",     6202,  277,   412,  553),
]

NAV_ORDER = ["pulse_design", "model", "analysis", "data"]
PAGE_TITLE = {
    "data": ("装置数据", "MDSplus 树浏览 · 指定炮号 · 取回选定信号"),
    "pulse_design": ("放电设计", "一份脚本 · 三种时间观：配置 · 设计 · 仿真"),
    "model": ("物理建模 / 预测", "1.5D 输运 · 含时演化（两条功能栏，各有计算键）"),
    "analysis": ("实验分析 / 反演", "由测量恢复位型 · 正向算子 · 不确定度"),
}
#: The three slots that differ between the four pages, and nothing else (V-12).
#: `state` drives the dot; ★it is never the only encoding — the sentence beside
#: it says the same thing in words (V-8), because a page read in greyscale or by
#: someone who cannot separate those two hues must still know what is running.
SLOTS = {
    "data":         ("数据源", "202.127.204.12:8000", "blocked",
                     "网关未连 —— 这一页需要一个能开套接字的进程", None),
    "pulse_design": ("装置", "EAST", "idle",
                     "待机 —— 摆好目标，合开关起放电", "交给建模场景"),
    "model":        ("装置", "EAST", "busy",
                     "含时演化 · 第 23/60 步 · 约 7 s", "交给反演场景"),
    "analysis":     ("装置", "EAST", "ready",
                     "剖面拟合 · 就绪（线圈响应矩阵 109 ms）", "交给建模场景"),
}
DOT = {"busy": "dot-busy", "ready": "dot-ok", "idle": "dot-idle", "blocked": "dot-bad"}

out: list[str] = []


def add(s: str) -> None:
    out.append(s)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rect(x, y, w, h, cls, rx=0, extra="") -> None:
    rxa = f' rx="{rx}"' if rx else ""
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"'
        f'{rxa} class="{cls}"{extra}/>')


def text(x, y, s, cls="lbl", size=12.5, anchor="start", weight=None) -> None:
    w = f' font-weight="{weight}"' if weight else ""
    add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}"'
        f' text-anchor="{anchor}"{w}>{esc(s)}</text>')


def line(x1, y1, x2, y2, cls="sep") -> None:
    add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"/>')


def btn(x, y, w, h, label, cls="btn", tcls="lbl", size=12) -> float:
    rect(x, y, w, h, cls, rx=5)
    text(x + w / 2, y + h / 2 + size * 0.36, label, tcls, size, "middle")
    return x + w


def select(x, y, w, h, label) -> None:
    rect(x, y, w, h, "input", rx=5)
    text(x + 9, y + h / 2 + 4.4, label, "lbl", 12)
    add(f'<path d="M{x + w - 18:.1f} {y + h / 2 - 2:.1f}l4 5 4-5" class="caret"/>')


def panel(x, y, w, h, title=None, hh=30) -> float:
    """A body panel; returns the y of its content top."""
    rect(x, y, w, h, "panel", rx=8)
    if title is None:
        return y + 12
    rect(x, y, w, hh, "head", rx=8)
    rect(x, y + hh - 8, w, 8, "head-sq")
    line(x, y + hh, x + w, y + hh)
    text(x + 12, y + hh / 2 + 4.6, title, "head-t", 12.5, weight="700")
    return y + hh + 10


def slider(x, y, w, frac, label, value) -> None:
    text(x, y, label, "mut", 11.5)
    text(x + w, y, value, "acc-t", 11.5, "end")
    line(x, y + 12, x + w, y + 12, "track")
    line(x, y + 12, x + w * frac, y + 12, "track-on")
    add(f'<circle cx="{x + w * frac:.1f}" cy="{y + 12:.1f}" r="5" class="handle"/>')


def dshape(kappa=1.62, delta=0.33, n=61):
    """A Miller-ish boundary in [0,1]^2 — elongated and triangular.

    ★An ellipse would be a picture of a machine nobody builds: elongation and
    triangularity are exactly the two numbers the page's own controls set, and
    a drawing that shows neither invites the reader to read the shape as data.
    """
    pts = []
    for i in range(n + 1):
        th = i / n * 2 * math.pi
        r = .5 + .26 * math.cos(th + delta * math.sin(th))
        z = .5 + .26 * kappa * math.sin(th)
        pts.append((r, z))
    return pts


def readings(x, y, w, rows, cols=2) -> float:
    """A readings block: name, value, and — where it matters — its provenance.

    ★Every number carries where it came from (`FYL-DESIGN-10` P-13); a table of
    bare numbers is the thing this whole family of pages exists not to be.
    """
    ry = y
    for i, (name, val, src) in enumerate(rows):
        if i:
            line(x, ry - 13, x + w, ry - 13, "sep")
        text(x, ry, name, "lbl", 12)
        text(x + w, ry, val, "acc-t", 12, "end")
        if src:
            text(x, ry + 14, src, "mut", 10.5)
            ry += 16
        ry += 26
    return ry


def figure(x, y, w, h, caption, curves, xlab="", ylab="", windows=None,
           stems=None, zero=False, iso=False) -> None:
    """An axes box with illustrative polylines.  Shapes only — no physics.

    `iso=True` gives the data area equal pixels per unit in both directions:
    a poloidal cross-section stretched to fill a tall box misreads elongation,
    which is one of the two numbers the reader is looking at.
    """
    rect(x, y, w, h, "panel", rx=6)
    ax, ay = x + 34, y + 10
    aw, ah = w - 46, h - 32
    if iso:
        sq = min(aw, ah)
        ax, ay = ax + (aw - sq) / 2, ay + (ah - sq) / 2
        aw = ah = sq
    rect(ax, ay, aw, ah, "axes")
    for i in range(1, 4):
        line(ax, ay + ah * i / 4, ax + aw, ay + ah * i / 4, "grid")
        line(ax + aw * i / 4, ay, ax + aw * i / 4, ay + ah, "grid")
    if zero:
        line(ax, ay + ah / 2, ax + aw, ay + ah / 2, "zero")
    #: ★heating windows are LANES, not stacked bars.  Drawn from the axis up
    #: they overlap where the systems overlap in time, and the overlap is the
    #: one thing a reader looks at this panel to see.
    for i, (cls, t0, t1, nm, pw) in enumerate(windows or []):
        n = len(windows)
        ly, lh = ay + ah * i / n + 4, ah / n - 8
        line(ax, ly + lh / 2, ax + aw, ly + lh / 2, "lane")
        rect(ax + aw * t0, ly, aw * (t1 - t0), lh, cls, rx=3)
        text(ax + 6, ly + lh / 2 + 4, nm, "mut", 10.5)
        text(ax + aw * (t0 + t1) / 2, ly + lh / 2 + 4, pw, "lbl", 10.5, "middle")
    for cls, t, v in (stems or []):                 # a residual is a stem
        line(ax + aw * t, ay + ah / 2, ax + aw * t, ay + ah * (1 - v), cls)
        add(f'<circle cx="{ax + aw * t:.1f}" cy="{ay + ah * (1 - v):.1f}" r="2.2"'
            f' class="{cls}f"/>')
    for cls, pts in curves:
        d = " ".join(f"{ax + aw * t:.1f},{ay + ah * (1 - v):.1f}" for t, v in pts)
        add(f'<polyline points="{d}" class="{cls}"/>')
    if ylab:
        add(f'<text x="{x + 12:.1f}" y="{ay + ah / 2:.1f}" class="mut" font-size="10"'
            f' text-anchor="middle" transform="rotate(-90 {x + 12:.1f} {ay + ah / 2:.1f})">'
            f'{esc(ylab)}</text>')
    text(ax + aw / 2, y + h - 6, caption + (f"    {xlab}" if xlab else ""),
         "mut", 10.5, "middle")


# --------------------------------------------------------------------------- #
# glyphs — the four nav icons, drawn as marks rather than words (as-built)
# --------------------------------------------------------------------------- #
def navicon(x, y, kind, on=False) -> None:
    s = 28
    rect(x, y, s, s, "navic-on" if on else "navic", rx=6)
    cx, cy = x + s / 2, y + s / 2
    g = "navg-on" if on else "navg"
    if kind == "pulse_design":                      # a trapezoid: the Ip waveform
        add(f'<path d="M{cx-8:.1f} {cy+5:.1f}L{cx-3:.1f} {cy-5:.1f}'
            f'L{cx+3:.1f} {cy-5:.1f}L{cx+8:.1f} {cy+5:.1f}" class="{g}"/>')
    elif kind == "model":                           # a decaying profile
        add(f'<path d="M{cx-8:.1f} {cy-6:.1f}C{cx-2:.1f} {cy-6:.1f} {cx:.1f} {cy+6:.1f}'
            f' {cx+8:.1f} {cy+6:.1f}" class="{g}"/>')
    elif kind == "analysis":                        # a fit through points
        add(f'<path d="M{cx-8:.1f} {cy+4:.1f}Q{cx:.1f} {cy-9:.1f} {cx+8:.1f} {cy+2:.1f}"'
            f' class="{g}"/>')
        for dx, dy in ((-5, 1), (0, -4), (5, 0)):
            add(f'<circle cx="{cx+dx:.1f}" cy="{cy+dy:.1f}" r="1.6" class="{g}f"/>')
    elif kind == "data":                            # a tree of signals
        add(f'<path d="M{cx-7:.1f} {cy-7:.1f}v14M{cx-7:.1f} {cy-7:.1f}h5'
            f'M{cx-7:.1f} {cy:.1f}h5M{cx-7:.1f} {cy+7:.1f}h5" class="{g}"/>')
        for dy in (-7, 0, 7):
            add(f'<circle cx="{cx+4:.1f}" cy="{cy+dy:.1f}" r="1.9" class="{g}f"/>')
    elif kind == "theme":                           # the half-filled disc
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" class="{g}"/>')
        add(f'<path d="M{cx:.1f} {cy-7:.1f}a7 7 0 0 1 0 14z" class="{g}f"/>')


# --------------------------------------------------------------------------- #
# THE SHELL — one function, called by all five drawings.  This is the point of
# the whole exercise: if the strip differed between previews, the previews
# would be arguing against the decision they illustrate.
# --------------------------------------------------------------------------- #
def strip(page_id: str | None, work: bool = True, progress: float | None = None,
          ghost: bool = False) -> None:
    """Draw the shared header toolbar.  `page_id=None` = a prose page (row 1 only)."""
    h = ROW1_H + (ROW2_H + PROG_H if work else 0)
    rect(0, 0, W, h, "strip-ghost" if ghost else "strip")
    line(0, h, W, h, "strip-edge")

    # --- row 1: who you are looking at, and where else you can go ------------
    rect(PAD, 6, 28, 28, "mark", rx=6)
    text(PAD + 14, 25, "Fy", "markt", 13, "middle", "700")
    if page_id:
        t, sub = PAGE_TITLE[page_id]
        text(PAD + 40, 25, t, "title", 15, weight="700")
        tw = len(t) * 15 + 14
        text(PAD + 40 + tw, 25, sub, "mut", 11.5)
    else:
        text(PAD + 40, 25, "fylite", "title", 15, weight="700")

    # the internal-testing pill: keeps its prominence, gives back its slack
    pw = 200
    rect(W / 2 - pw / 2, 8, pw, 24, "pill", rx=12)
    text(W / 2, 24, "仅限内部测试", "pillt", 11.5, "middle", "700")

    x = W - PAD - 28
    navicon(x, 6, "theme")
    x -= 12
    line(x, 11, x, 29, "sep")
    for k in reversed(NAV_ORDER):
        x -= 32
        navicon(x, 6, k, on=(k == page_id))
    if not work:
        return

    # --- row 2: this page's work.  Three slots vary, nothing else does -------
    y = ROW1_H
    line(0, y, W, y, "strip-inner")
    dev_label, dev_value, state, status, handoff = SLOTS[page_id]
    text(PAD, y + 26, dev_label, "mut", 12)
    lx = PAD + len(dev_label) * 12 + 10
    select(lx, y + 8, 200, 26, dev_value)
    btn(lx + 208, y + 8, 26, 26, "×", "btn", "mut")
    bx = lx + 246
    bx = btn(bx, y + 8, 62, 26, "导入") + 8
    bx = btn(bx, y + 8, 62, 26, "导出") + 8

    # the run STATE, not a run key: the key stays in the bar that owns it
    add(f'<circle cx="{bx + 16:.1f}" cy="{y + 21:.1f}" r="4.5" class="{DOT[state]}"/>')
    text(bx + 28, y + 25, status, "mut", 12)

    rx_ = W - PAD
    if handoff:
        rect(rx_ - 118, y + 8, 118, 26, "btn-a", rx=5)
        text(rx_ - 59, y + 25, handoff, "btn-at", 12, "middle")

    # --- the progress line, welded to the bottom edge ------------------------
    py = ROW1_H + ROW2_H
    rect(0, py, W, PROG_H, "prog-bg")
    if progress:
        rect(0, py, W * progress, PROG_H, "prog")


# --------------------------------------------------------------------------- #
# document frame
# --------------------------------------------------------------------------- #
#: ★**Light only, deliberately** — no `prefers-color-scheme` block.
#:
#: The app itself is three-state on purpose (V-5), and the reason given there
#: applies to these drawings with more force, not less: a figure whose ground
#: follows the reader's operating system is a figure that exports differently
#: on two machines, and these get screenshotted into slides and printed.  So
#: the previews commit to the light palette and stay put.  ★The other figure
#: generator in this repo (`make-app-figures.py`) does carry a dark block;
#: that is a difference, and this comment is where it is recorded rather than
#: left for someone to find and "fix".
STYLE = """
:root {
  --bg:#f4f5f7; --panel:#ffffff; --fg:#1c2128; --muted:#666f7a; --grid:#d8dce2;
  --line:#e3e6ea; --accent:#1668c8; --lcfs:#d0342c; --alt:#10897a;
  --coil:#8a53c4; --wall:#5a6270; --flux:#9aa6b8; --warn:#a75909;
  --head:#eceff3; --sel:#e7f0fb; --strip:#ffffff; --pill:#fdf1e3;
}
text { font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,
       -apple-system,'Segoe UI',sans-serif; fill:var(--fg); }
.bg { fill:var(--bg); }
.strip { fill:var(--strip); }
.strip-ghost { fill:var(--strip); opacity:.55; }
.strip-edge { stroke:var(--line); stroke-width:1.5; }
.strip-inner { stroke:var(--line); stroke-width:1; }
.mark { fill:var(--accent); }
.markt { fill:#ffffff; }
.title { fill:var(--fg); }
.mut { fill:var(--muted); }
.lbl { fill:var(--fg); }
.acc-t { fill:var(--accent); }
.sep { stroke:var(--line); stroke-width:1; }
.pill { fill:var(--pill); stroke:var(--warn); stroke-width:1; }
.pillt { fill:var(--warn); }
.navic { fill:none; stroke:none; }
.navic-on { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.navg { fill:none; stroke:var(--muted); stroke-width:1.6;
        stroke-linecap:round; stroke-linejoin:round; }
.navg-on { fill:none; stroke:var(--accent); stroke-width:1.8;
           stroke-linecap:round; stroke-linejoin:round; }
.navgf { fill:var(--muted); stroke:none; }
.navg-onf { fill:var(--accent); stroke:none; }
.input { fill:var(--panel); stroke:var(--grid); stroke-width:1; }
.caret { fill:none; stroke:var(--muted); stroke-width:1.4; stroke-linecap:round; }
.btn { fill:none; stroke:var(--grid); stroke-width:1; }
.btn-a { fill:none; stroke:var(--accent); stroke-width:1.2; }
.btn-at { fill:var(--accent); }
.dot-busy { fill:var(--accent); }
.dot-ok { fill:var(--alt); }
.dot-idle { fill:none; stroke:var(--muted); stroke-width:1.4; }
.dot-bad { fill:var(--warn); }
.prog-bg { fill:var(--line); }
.prog { fill:var(--accent); }
.panel { fill:var(--panel); stroke:var(--line); stroke-width:1; }
.head { fill:var(--head); stroke:var(--line); stroke-width:1; }
.head-sq { fill:var(--head); stroke:none; }
.head-t { fill:var(--fg); }
.axes { fill:none; stroke:var(--grid); stroke-width:1; }
.grid { stroke:var(--grid); stroke-width:.7; }
.track { stroke:var(--grid); stroke-width:4; stroke-linecap:round; }
.track-on { stroke:var(--accent); stroke-width:4; stroke-linecap:round; }
.handle { fill:var(--panel); stroke:var(--accent); stroke-width:1.6; }
polyline { fill:none; stroke-linejoin:round; stroke-linecap:round; }
.c1 { stroke:var(--accent); stroke-width:2; }
.c2 { stroke:var(--lcfs); stroke-width:2; }
.c3 { stroke:var(--alt); stroke-width:1.8; }
.c4 { stroke:var(--coil); stroke-width:1.6; }
.c5 { stroke:var(--muted); stroke-width:1.4; stroke-dasharray:4 3; }
.zero { stroke:var(--muted); stroke-width:1; }
.lane { stroke:var(--grid); stroke-width:1; stroke-dasharray:2 3; }
.w1 { fill:var(--lcfs); opacity:.28; }
.w2 { fill:var(--alt); opacity:.30; }
.w3 { fill:var(--coil); opacity:.30; }
.s1 { stroke:var(--alt); stroke-width:1.4; }
.s1f { fill:var(--alt); }
.wall { fill:none; stroke:var(--wall); stroke-width:1.6; stroke-dasharray:5 4; }
.lcfs { fill:none; stroke:var(--lcfs); stroke-width:2.2; }
.bar-v { fill:var(--accent); opacity:.55; }
.bar-over { fill:var(--warn); opacity:.72; }
.lim { stroke:var(--wall); stroke-width:1.4; stroke-dasharray:3 2; }
.future { fill:url(#hatch); }
.future-e { fill:none; stroke:var(--muted); stroke-width:1; stroke-dasharray:3 3; }
.solved { fill:var(--accent); }
.interp { fill:var(--panel); stroke:var(--muted); stroke-width:1.4; }
.edit { stroke:var(--lcfs); stroke-width:1.6; }
.editf { fill:var(--lcfs); }
.tgt { fill:none; stroke:var(--muted); stroke-width:1.6; stroke-dasharray:5 3; }
.ff { fill:none; stroke:var(--coil); stroke-width:2; }
.fb { fill:none; stroke:var(--coil); stroke-width:2; stroke-dasharray:5 3; }
.chip-on { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.chip-off { fill:none; stroke:var(--grid); stroke-width:1; }
.gauge-bg { fill:var(--grid); opacity:.5; }
.gauge { fill:var(--alt); }
.warnbox { fill:none; stroke:var(--warn); stroke-width:1.4; stroke-dasharray:4 3; }
.warn-t { fill:var(--warn); }
.c-dot { stroke:var(--accent); stroke-width:1.8; stroke-dasharray:1.5 3.5;
         stroke-linecap:round; }
.postband { fill:var(--accent); opacity:.16; }
.okmark { fill:none; stroke:var(--alt); stroke-width:2; stroke-linecap:round;
          stroke-linejoin:round; }
.badmark { fill:none; stroke:var(--lcfs); stroke-width:2; stroke-linecap:round; }
.mono { fill:var(--fg); font-family:ui-monospace,"SFMono-Regular",Menlo,
        Consolas,"Liberation Mono",monospace; }
.ph0 { fill:var(--accent); opacity:.09; }
.ph1 { fill:var(--alt); opacity:.13; }
.ph2 { fill:var(--warn); opacity:.09; }
.null1 { fill:none; stroke:var(--flux); stroke-width:1.2; }
.null2 { fill:none; stroke:var(--accent); stroke-width:1.8; }
.foot { fill:var(--muted); }
.zone { fill:none; stroke:var(--accent); stroke-width:1.2; stroke-dasharray:5 4; }
.zone-t { fill:var(--accent); }
.brace { fill:none; stroke:var(--accent); stroke-width:1.2; }
.bar-h { fill:var(--grid); }
.bar-seen { fill:var(--accent); opacity:.20; }
.fold { stroke:var(--lcfs); stroke-width:2; stroke-dasharray:6 4; }
.fold-t { fill:var(--lcfs); }
.tick { stroke:var(--muted); stroke-width:1.4; }
.ok-t { fill:var(--alt); }
.bad-t { fill:var(--lcfs); }
.rowsel { fill:var(--sel); }
.badge { fill:var(--accent); }
.badget { fill:#ffffff; }
.bar-rest { fill:var(--grid); opacity:.45; }
.bar-seen { fill:var(--sel); }
.bar-edge { fill:none; stroke:var(--grid); stroke-width:1; }
.brk { fill:none; stroke:var(--bg); stroke-width:6; }
"""


def head(title: str, aria: str) -> None:
    out.clear()
    #: ★viewBox only — see the module docstring.  `preserveAspectRatio` is left
    #: at its default (`xMidYMid meet`), which is what keeps 16:9 when the box
    #: it is given is not.
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"'
        f' role="img" aria-label="{esc(aria)}">')
    add(f'<title>{esc(title)}</title>')
    add(f'<style>{STYLE}</style>')
    #: the "not computed yet" hatch — a texture, so the region reads as absent
    #: rather than as a value of zero even in greyscale (V-8)
    add('<defs><pattern id="hatch" width="8" height="8" '
        'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="8" height="8" fill="var(--bg)"/>'
        '<line x1="0" y1="0" x2="0" y2="8" stroke="var(--grid)" '
        'stroke-width="2.4"/></pattern></defs>')
    rect(0, 0, W, H, "bg")


def foot(note: str) -> None:
    text(W / 2, H - 12, note, "foot", 11, "middle")
    add("</svg>")


#: set by --check; collects (path, differs) instead of writing
CHECK: dict[str, bool] | None = None


def write(d: Path, name: str) -> None:
    #: ★Parse before writing.  An unquoted attribute value ships a file that
    #: every browser renders as a red XML error box and no build step notices,
    #: because nothing downstream reads an SVG as anything but bytes.  This
    #: caught exactly that (`rx=8` for `rx="8"`) on the first run.
    body = "\n".join(out) + "\n"
    root_el = ET.fromstring(body)
    #: ★No Markdown in an SVG.  These strings are written next to prose that is
    #: Markdown, and `**bold**` / `` `code` `` were copied across twice — SVG
    #: renders them as literal asterisks and backticks, and nothing complains.
    #: So the generator reads its own output.
    for t in root_el.iter("{http://www.w3.org/2000/svg}text"):
        txt = "".join(t.itertext())
        bad = [m for m in ("**", "`") if m in txt]
        if bad:
            raise SystemExit(f"{name}: 文本里带了 Markdown 记号 {bad}："
                             f"{txt.strip()[:60]!r} —— SVG 会原样画出来")
    p = d / name
    if CHECK is not None:
        old = p.read_text(encoding="utf-8") if p.exists() else None
        CHECK[str(p)] = old != body
        print(f"  {'DIFFERS' if old != body else 'ok     '}  {p}")
        return
    p.write_text(body, encoding="utf-8")
    print(f"  {p}  ({p.stat().st_size / 1024:.1f} kB)")


# --------------------------------------------------------------------------- #
# 1. the shell, annotated, over the measured fold diagram
# --------------------------------------------------------------------------- #
def draw_shell(d: Path) -> None:
    head("fylite 桌面版 — 共享 header toolbar",
         "fylite 桌面版共享 header toolbar 概念图与四页首屏实测")
    strip("model", progress=0.38)

    # --- ①..⑥ badges, in a gutter UNDER the strip -----------------------------
    #: ★Not on the strip and not on leader lines.  Leaders converging on an
    #: 84 px band were unreadable at 16:9; badges placed ON it landed inside
    #: the select and inside the status line.  A gutter row with a short tick
    #: says the same thing and collides with nothing.
    #: (badge x, the x on the strip it points at, label)
    badges = [(78, 78, "1"), (800, 800, "2"), (1500, 1500, "3"),
              (200, 200, "4"), (560, 560, "5"), (1290, 1523, "6")]
    gy = STRIP_H + 14
    for bx, tx, n in badges:
        add(f'<path d="M{tx:.1f} {STRIP_H + 1:.1f}L{bx:.1f} {gy - 9:.1f}" class="brace"/>')
        add(f'<circle cx="{bx:.1f}" cy="{gy:.1f}" r="8.5" class="badge"/>')
        text(bx, gy + 4, n, "badget", 10.5, "middle", "700")

    y0 = STRIP_H + 48
    text(GUT, y0, "两行 · 84 px · 常驻（sticky）", "lbl", 14, weight="700")
    text(GUT + 176, y0, "—— ①②③ 取自静态登记表，④⑤⑥ 取自这一页的运行时；"
                        "外壳只读，改变状态的控件留在页体（V-12）", "mut", 12.5)

    legend = [
        ("1", "身份", "标记 · 页名 · 副标题 —— 逐页不同，但由那一张页面表给出"),
        ("2", "警示", "仅限内部测试。保住显著性，交回它占着的 500 px 空白"),
        ("3", "去处", "四页图标 · 主题三态 —— 顺序即两张表的顺序，不重排"),
        ("4", "★输入", "装置（数据页是 mdsip 数据源）· 导入 / 导出"),
        ("5", "★运行态", "哪一条栏在跑 · 第几步 · 还要多久 —— 只报告，不操作"),
        ("6", "★出口", "交给另一个场景。这一页没有出口时不留空格"),
    ]
    ly = y0 + 28
    for i, (n, k, v) in enumerate(legend):
        cx = GUT + 10 + (i // 3) * 780
        cyy = ly + (i % 3) * 26
        add(f'<circle cx="{cx:.1f}" cy="{cyy - 4:.1f}" r="8.5" class="badge"/>')
        text(cx, cyy, n, "badget", 10.5, "middle", "700")
        text(cx + 18, cyy, k, "lbl", 12.5, weight="700")
        text(cx + 18 + 62, cyy, v, "mut", 12)

    # --- the measured fold diagram, on a broken axis -------------------------
    fy = 242
    text(GUT, fy, "为什么要常驻：今天没有一样东西是常驻的", "lbl", 14, weight="700")
    text(GUT + 330, fy, "（实测 1600 × 900，2026-09-01；页眉与工具条都是 position: static）",
         "mut", 12.5)

    TOPSEG = 1500.0        # px of page drawn to scale
    SEG_H = 500.0          # px of drawing for that segment
    sc = SEG_H / TOPSEG
    top = fy + 44
    bw, gap = 300, 44
    bx0 = GUT + 108
    for i, (pid, label, doc_h, tb_y, bar_y, out_y) in enumerate(MEASURED):
        bx = bx0 + i * (bw + gap)
        seen = 900 * sc
        rect(bx, top, bw, SEG_H, "bar-rest")                # below the fold
        rect(bx, top, bw, seen, "bar-seen")                 # the first screen
        rect(bx, top, bw, SEG_H, "bar-edge")
        text(bx + bw / 2, top - 12, label, "lbl", 13, "middle", "700")
        # the break, then the remainder as a labelled stub
        by = top + SEG_H
        add(f'<path d="M{bx:.1f} {by:.1f}l{bw / 6:.1f} -7l{bw / 3:.1f} 14'
            f'l{bw / 3:.1f} -14l{bw / 6:.1f} 7" class="brk"/>')
        rect(bx, by + 12, bw, 26, "bar-rest")
        rect(bx, by + 12, bw, 26, "bar-edge")
        text(bx + bw / 2, by + 29, f"…到 {doc_h} px（还有 {doc_h - int(TOPSEG)} px）",
             "mut", 11, "middle")
        marks = [(65, "页眉 65 —— 随页滚走", None),
                 (tb_y, f"工具条 {tb_y} —— 随页滚走" if tb_y else None, None),
                 (bar_y, f"首条功能栏 {bar_y}" if bar_y else None, None),
                 (out_y, f"首处输出 {out_y}" if out_y else None,
                  "ok-t" if out_y and out_y < 900 else "bad-t")]
        for v, lab, cls in marks:
            if v is None or lab is None:
                continue
            my = top + v * sc
            line(bx, my, bx + bw, my, "tick")
            text(bx + 7, my + 14, lab, cls or "mut", 11)
        if tb_y is None:
            text(bx + 7, top + 150, "没有工具条 —— 这一页从来没有过一条，", "bad-t", 11)
            text(bx + 7, top + 165, "它的「装置」是左栏里的一个面板", "bad-t", 11)
        if out_y is None:
            text(bx + 7, top + SEG_H - 22, "整整 1500 px 内没有一处输出", "bad-t", 11)
        fyy = top + seen
        line(bx - 10, fyy, bx + bw + 10, fyy, "fold")
        text(bx + bw / 2, fyy - 9, "首屏无输出" if (out_y is None or out_y > 900)
             else "首屏有输出", "bad-t" if (out_y is None or out_y > 900) else "ok-t",
             12.5, "middle", "700")
    text(bx0 - 14, top + 900 * sc + 4, "16:9 首屏 900 px", "fold-t", 11.5, "end")
    text(bx0 - 14, top + 4, "0", "mut", 11, "end")
    text(bx0 - 14, top + SEG_H + 4, "1500", "mut", 11, "end")

    foot("概念图：上半那条工具条是 V-11 主张的形状，尚未落地；下半四条是实测页高与偏移，"
         "纵轴 0–1500 px 按比例、其余截断（V-13 的判据）。生成物 —— tools/make-desktop-preview.py")
    write(d, "desktop-shell.svg")


# --------------------------------------------------------------------------- #
# 2..5 — one first screen per function page.  Same strip, four bodies.
# --------------------------------------------------------------------------- #
def body_top() -> float:
    return STRIP_H + 16


def lead(x, w, ytop, lines) -> float:
    """The page's one-paragraph lead — kept, but capped so an output fits."""
    h = 14 + len(lines) * 19
    rect(x, ytop, w, h, "panel", rx=8)
    rect(x, ytop, 3, h, "mark")
    for i, s in enumerate(lines):
        text(x + 14, ytop + 20 + i * 19, s, "lbl" if i == 0 else "mut", 12.5)
    return ytop + h + 14


def draw_data(d: Path) -> None:
    head("fylite 桌面版 — 装置数据页首屏",
         "fylite 装置数据页在 16:9 首屏上的概念布局")
    strip("data")
    y = body_top()
    y = lead(GUT, W - 2 * GUT, y, [
        "把一台 MDSplus 服务器当成可以走进去的目录：选一棵树、给一个炮号，挑几路信号取回来画出来。",
        "它只读 —— 没有入口能写、能删、能求值任意表达式。画出来的是每隔 N 个取一个样点，不是均值。"])

    lw, rw = 380, W - 2 * GUT - 380 - 16
    lx, rx_ = GUT, GUT + 380 + 16
    bh = H - y - 34
    cy = panel(lx, y, lw, bh, "信号树")
    text(lx + 12, cy + 4, "炮号 137985 · 树 EAST", "mut", 11.5)
    rows = [("\\EAST::TOP", 0, False), ("PCS", 1, False), ("IP", 2, True),
            ("VLOOP", 2, False), ("MAGNETICS", 1, False), ("FLUX_LOOP", 2, False),
            ("PROBE", 2, False), ("EFIT", 1, False), ("Q95", 2, True),
            ("BETAP", 2, False), ("THOMSON", 1, False), ("NE", 2, True)]
    ry = cy + 18
    for name, depth, sel in rows:
        if sel:
            rect(lx + 8, ry - 11, lw - 16, 20, "rowsel", rx=4)
        text(lx + 16 + depth * 16, ry + 3, ("· " if depth else "") + name,
             "acc-t" if sel else "lbl", 12)
        ry += 24
    text(lx + 12, ry + 12, "★三路已选。取回后每路在图注里写自己取了几点。", "mut", 11)
    line(lx + 12, ry + 30, lx + lw - 12, ry + 30, "sep")
    text(lx + 12, ry + 52, "读数 —— 取回的三路", "lbl", 12.5, weight="700")
    readings(lx + 12, ry + 76, lw - 24, [
        ("PCS:IP", "256 / 12480 点", "步长 4.9 ms —— 跟窗口走，不跟整炮走"),
        ("EFIT:Q95", "256 / 3100 点", "步长 20 ms"),
        ("THOMSON:NE", "121 / 121 点", "全取 —— 本来就少于 256")])

    cy2 = panel(rx_, y, rw, bh, "信号时序 —— 三路已取回")
    fh = (bh - 46) / 2 - 8
    figure(rx_ + 12, cy2, rw - 24, fh, "Ip [kA] · 抽稀 256/12480 点", [
        ("c1", [(0, .05), (.08, .05), (.18, .82), (.72, .86), (.85, .80), (1, .06)])],
        ylab="Ip")
    figure(rx_ + 12, cy2 + fh + 12, rw - 24, fh,
           "n_e [10¹⁹ m⁻³] · q95 —— 同一时间窗，同一口径", [
        ("c3", [(0, .1), (.2, .55), (.5, .62), (.8, .58), (1, .12)]),
        ("c2", [(0, .9), (.25, .40), (.6, .35), (.9, .38), (1, .85)])], ylab="n_e · q95")
    foot("概念图：数据页在共享工具条下的 16:9 首屏；工具条第 ④ 槽在这一页是 mdsip 数据源，"
         "第 ⑥ 槽为空。生成物 —— tools/make-desktop-preview.py")
    write(d, "desktop-data.svg")


def draw_pulse(d: Path) -> None:
    head("fylite 桌面版 — 放电设计页首屏",
         "fylite 放电设计页在 16:9 首屏上的概念布局")
    strip("pulse_design")
    y = body_top()
    y = lead(GUT, W - 2 * GUT, y, [
        "这一炮该怎么打，以及照这么打会发生什么。同一份脚本，三个模式换的是时间轴的含义。",
        "★配置没有时间轴；设计里整条脉冲已经存在，播放头在其中回读；仿真里只有过去。"])

    # the three modes: one control, three readings of the same script
    mx = GUT
    for i, (lab, on) in enumerate([("配置", False), ("设计", True), ("仿真", False)]):
        rect(mx, y, 92, 28, "navic-on" if on else "btn", rx=6)
        text(mx + 46, y + 19, lab, "acc-t" if on else "mut", 12.5, "middle",
             "700" if on else None)
        mx += 100
    text(mx + 12, y + 19, "三个模式读同一份「这一炮」——位形、电流、相位与加热在页面上各只有一个控件",
         "mut", 11.5)
    y += 42

    lw = 330
    lx, rx_ = GUT, GUT + 330 + 16
    rw = W - 2 * GUT - 330 - 16
    bh = H - y - 34
    cy = panel(lx, y, lw, bh, "这一炮（三个模式共用）")
    sy = cy + 10
    for lab, val, f in [("平顶电流 Ip [kA]", "400", .40), ("大半径 R₀ [m]", "1.85", .55),
                        ("平顶小半径 a [m]", "0.445", .62), ("拉长比 κ", "1.65", .58),
                        ("上三角度 δu", "0.40", .40), ("击穿 → 平顶 → 结束 [s]", "0 · 1 · 8 · 10", .80)]:
        slider(lx + 14, sy, lw - 28, f, lab, val)
        sy += 42
    text(lx + 14, sy + 6, "★一个量一个控件：三个模式读的是同一份。", "mut", 11)
    line(lx + 14, sy + 22, lx + lw - 14, sy + 22, "sep")
    text(lx + 14, sy + 44, "加热窗口（与上面那张图同源）", "lbl", 12.5, weight="700")
    for i, (nm, cls, txt) in enumerate([
            ("NBI", "w1", "1.0 – 8.0 s · 4.0 MW"),
            ("ECRH", "w2", "2.0 – 6.0 s · 1.0 MW"),
            ("LHCD", "w3", "3.0 – 8.0 s · 0.5 MW")]):
        wy = sy + 62 + i * 26
        rect(lx + 14, wy, 14, 14, cls)
        text(lx + 36, wy + 12, nm, "lbl", 12)
        text(lx + lw - 14, wy + 12, txt, "mut", 11.5, "end")
    text(lx + 14, sy + 62 + 3 * 26 + 14,
         "★色块与图上的窗口是同一组值 —— 不是两处输入。", "mut", 10.5)

    cy2 = panel(rx_, y, rw, bh, "整条脉冲 —— 播放头 t = 3.2 s")
    fh = (bh - 46) / 3 - 8
    trap = [(0, .04), (.10, .04), (.20, .88), (.80, .88), (.92, .30), (1, .04)]
    figure(rx_ + 12, cy2, rw - 24, fh, "Ip [kA] —— 上升 · 平顶 · 下降",
           [("c1", trap)], ylab="Ip")
    figure(rx_ + 12, cy2 + fh + 10, rw - 24, fh,
           "辅助加热 —— 三条泳道，重叠处就是同时在加热", [], ylab="P_aux",
           windows=[("w1", .10, .80, "NBI", "4.0 MW"),
                    ("w2", .20, .60, "ECRH", "1.0 MW"),
                    ("w3", .30, .80, "LHCD", "0.5 MW")])
    figure(rx_ + 12, cy2 + 2 * (fh + 10), rw - 24, fh, "PF 线圈电流 [kA] —— 形状反馈的稳态解", [
        ("c4", [(0, .5), (.2, .72), (.5, .70), (.8, .66), (1, .5)]),
        ("c5", [(0, .5), (.2, .30), (.5, .34), (.8, .38), (1, .5)])], ylab="I_PF")
    # the play-head, across all three lanes
    ph = rx_ + 12 + 34 + (rw - 24 - 46) * .32
    line(ph, cy2 - 2, ph, cy2 + 3 * (fh + 10) - 12, "fold")
    text(ph + 6, cy2 + 10, "t = 3.2 s", "fold-t", 10.5)
    foot("概念图：设计页在共享工具条下的 16:9 首屏；三个模式的切换在体内，"
         "不在工具条上（V-12）。生成物 —— tools/make-desktop-preview.py")
    write(d, "desktop-pulse-design.svg")


def draw_model(d: Path) -> None:
    head("fylite 桌面版 — 物理建模页首屏",
         "fylite 物理建模页在 16:9 首屏上的概念布局")
    strip("model", progress=0.38)
    y = body_top()
    y = lead(GUT, W - 2 * GUT, y, [
        "这个场景把一炮的剖面算出来：一条栏在固定几何上定态求解，另一条把热、粒子与电流三道随时间推进。",
        "★1.5D 那一栏的几何是固定的，它报不出储能与约束时间；含时那一栏没有台基模型，边界是你给的一个数。"])

    # the bar switcher: which of the page's three bars you are in
    mx = GUT
    for lab, on in [("1.5D 芯部输运", False), ("含时演化", True), ("功率平衡反演", False)]:
        wpx = len(lab) * 12 + 26
        rect(mx, y, wpx, 28, "navic-on" if on else "btn", rx=6)
        text(mx + wpx / 2, y + 19, lab, "acc-t" if on else "mut", 12.5, "middle",
             "700" if on else None)
        mx += wpx + 10
    text(mx + 10, y + 19, "★每条栏自己有一个计算键 —— 工具条上没有第二个（V-11）", "mut", 11.5)
    y += 42

    lw = 330
    lx, rx_ = GUT, GUT + 330 + 16
    rw = W - 2 * GUT - 330 - 16
    bh = H - y - 34
    cy = panel(lx, y, lw, bh, "这台机器（两条栏共读）")
    sy = cy + 10
    for lab, val, f in [("小半径 a [m]", "0.60", .35), ("R/a", "3.00", .50),
                        ("拉长比 κ", "1.60", .60), ("三角度 δ", "0.30", .55),
                        ("边界 q", "3.5", .62), ("B_unit [T]", "2.0", .30),
                        ("中心密度 n_e(0)", "3.0", .18), ("χ₀ [m²/s]", "0.60", .28)]:
        slider(lx + 14, sy, lw - 28, f, lab, val)
        sy += 36
    line(lx + 14, sy + 2, lx + lw - 14, sy + 2, "sep")
    text(lx + 14, sy + 24, "这一步的读数", "lbl", 12.5, weight="700")
    ry = readings(lx + 14, sy + 46, lw - 28, [
        ("W_th", "184 kJ", "(3/2)∫p dV，本步"),
        ("τ_E", "0.31 s", "W_th / P_loss —— 不是标度律"),
        ("β_N", "1.42", None),
        ("Q", "—", "无聚变功率：这套输入没有 D-T")])
    text(lx + 14, ry + 6, "★1.5D 那一栏报不出这四个数 —— 它的几何是固定的。", "mut", 10.5)

    cy2 = panel(rx_, y, rw, bh, "含时演化 —— 第 23/60 步，t = 2.3 s")
    fw = (rw - 36) / 3
    fh = (bh - 46) / 2 - 8
    prof = lambda k: [(t / 10, (1 - (t / 10) ** 2) ** k * .9 + .05) for t in range(11)]
    for i, (cap, cls, k) in enumerate([("n_e [10¹⁹ m⁻³]", "c1", 0.7),
                                       ("T_e [keV]", "c2", 1.6),
                                       ("T_i [keV]", "c3", 1.4)]):
        figure(rx_ + 12 + i * (fw + 6), cy2, fw, fh, cap + "  ρ", [(cls, prof(k))])
    for i, (cap, cls, pts) in enumerate([
            ("W_th [kJ] —— 随时间", "c1", [(0, .1), (.3, .55), (.6, .74), (1, .80)]),
            ("q(ρ) —— 当前一步", "c4", [(0, .25), (.3, .30), (.7, .55), (1, .90)]),
            ("χ_i [m²/s] —— 闭包给出", "c2", [(0, .15), (.4, .30), (.8, .62), (1, .85)])]):
        figure(rx_ + 12 + i * (fw + 6), cy2 + fh + 10, fw, fh, cap, [(cls, pts)])
    foot("概念图：建模页在共享工具条下的 16:9 首屏；进度贴在工具条底缘，"
         "与它下面那条栏的计算键相隔多远都还看得见（V-11）。生成物 —— tools/make-desktop-preview.py")
    write(d, "desktop-model.svg")


def draw_analysis(d: Path) -> None:
    head("fylite 桌面版 — 实验分析页首屏",
         "fylite 实验分析页在 16:9 首屏上的概念布局")
    strip("analysis")
    y = body_top()
    y = lead(GUT, W - 2 * GUT, y, [
        "把「由测量恢复位型」当作一个统一的正向—推断问题：磁通环与磁探针、干涉与法拉第、Thomson 密度一起拟合。",
        "★磁测量单独约束不住内部剖面；误差棒只度量压强 σ 这一个来源 —— 诊断几何与模型本身的不确定度都不在其中。"])

    lw = 330
    lx, rx_ = GUT, GUT + 330 + 16
    rw = W - 2 * GUT - 330 - 16
    bh = H - y - 34
    cy = panel(lx, y, lw, bh, "约束与数据点")
    sy = cy + 8
    for lab, val, ok in [("磁通环", "38 路", True), ("磁探针", "35 路", True),
                         ("POINT 干涉", "11 弦", True), ("法拉第旋转", "11 弦", True),
                         ("Thomson n_e", "65 点", True), ("压强 p(ψ) 动理学约束", "GCV 第 6 阶", True),
                         ("MSE", "无此炮", False)]:
        rect(lx + 12, sy, lw - 24, 26, "input", rx=5)
        text(lx + 22, sy + 17, lab, "lbl", 12)
        text(lx + lw - 34, sy + 17, val, "ok-t" if ok else "mut", 11.5, "end")
        sy += 32
    text(lx + 14, sy + 10, "★误差棒的来源在图注里逐条写出，", "mut", 11)
    text(lx + 14, sy + 26, "不写「±」两个字了事。", "mut", 11)

    cy2 = panel(rx_, y, rw, bh, "拟合与位形 —— EAST #137985 @ 4 s")
    xw = rw * .40
    xh = xw * 0.86
    figure(rx_ + 12, cy2, xw, xh,
           "位形：解出的 LCFS（红）与限制器（灰虚）—— 等比例  R [m]", [
        ("wall", [((r - .5) * 1.16 + .5, (z - .5) * 1.16 + .5) for r, z in dshape()]),
        ("lcfs", dshape())], ylab="Z [m]", iso=True)
    ry0 = panel(rx_ + 12, cy2 + xh + 12, xw, bh - 58 - xh, "读数 —— 每个数带自己的出处")
    readings(rx_ + 26, ry0 + 10, xw - 28, [
        ("q₀", "1.04", "解出，非拟合参数"),
        ("β_p", "0.86", "由解出的 p(ψ) 积分"),
        ("I_p 复算 / 测量", "398 / 400 kA", "闭合差 0.5 % —— 收敛判据之一"),
        ("χ² / dof", "1.12", "84 路测量 · 7 个自由度")])
    rw2 = rw - xw - 30
    fh = (bh - 46) / 2 - 8
    pp = lambda k: [(t / 20, .06 + k * (1 - (t / 20) ** 1.8) ** 1.6) for t in range(21)]
    figure(rx_ + 24 + xw, cy2, rw2, fh,
           "p(ψ) 拟合 —— 带后验采样带  ψ", [
        ("c5", pp(.90)), ("c5", pp(.66)), ("c1", pp(.78))], ylab="p [Pa]")
    figure(rx_ + 24 + xw, cy2 + fh + 10, rw2, fh,
           "残差 / σ —— 每一路测量各一根，零线是拟合", [], ylab="残差 / σ", zero=True,
           stems=[("s1", (i + .5) / 30,
                   .5 + .30 * math.sin(i * 2.1) * math.cos(i * .7))
                  for i in range(30)])
    foot("概念图：分析页在共享工具条下的 16:9 首屏；这一页今天是四页里唯一首屏有输出的"
         "（实测 553 px），改后四页都是。生成物 —— tools/make-desktop-preview.py")
    write(d, "desktop-analysis.svg")


# --------------------------------------------------------------------------- #
# 6..9 — the pulse-design page in its three modes, and its visual vocabulary.
#
# ★These four say what `FYL-DESIGN-11` leaves to the page documents (V-15):
# the shell is the same in all three, and everything BELOW it changes meaning
# because the time axis changed meaning (`FYL-DESIGN-09` D-18).
# --------------------------------------------------------------------------- #
MODES = [("config", "配置"), ("design", "设计"), ("sim", "仿真")]
#: ★one line per mode, and the shell's ⑤ slot says WHICH TIME you are in
#: before it says anything else — that is what a mode is on this page.
MODE_STATE = {
    "config": ("idle", "配置 · 无时间轴 · 单时刻 —— 待机", None),
    "design": ("ready", "设计 · 整条脉冲已存在 · 播放头 t = 3.20 s", 0.32),
    "sim": ("busy", "仿真 · 只有过去 · 现在 t = 4.15 s · 实时 0.8×", 0.415),
}


def pd_head(mode: str, title: str, aria: str) -> float:
    """Shell + mode bar + the collapsed lead.  Returns the body's top y.

    ★The lead is ONE LINE here, not the four-line block the page carries today.
    That is not a drawing convenience: at 16:9 this page's first functional bar
    sits at 1265 px (measured), and V-13 asks for one output inside 900.  The
    lead folded to a line with an 展开 affordance is the cheapest of the three
    routes V-13 names, and it is the one drawn.
    """
    head(title, aria)
    state, status, prog = MODE_STATE[mode]
    SLOTS["pulse_design"] = ("装置", "EAST", state, status, "交给建模场景")
    strip("pulse_design", progress=prog)

    y = STRIP_H + 12
    #: ★the mode switch is a BODY control, pinned under the shell.  V-12:
    #: the shell reports state, the body changes it — and D-18 still wants the
    #: current mode never out of sight, which the shell's ⑤ slot now provides.
    rect(0, y - 12, W, 46, "panel")
    line(0, y + 34, W, y + 34, "strip-inner")
    mx = GUT
    for mid, lab in MODES:
        on = mid == mode
        rect(mx, y - 2, 84, 26, "chip-on" if on else "chip-off", rx=6)
        text(mx + 42, y + 15, lab, "acc-t" if on else "mut", 12.5, "middle",
             "700" if on else None)
        mx += 92
    text(mx + 10, y + 15,
         "三个模式换的是时间轴的含义，不是三个工具（D-18）；"
         "切模式只换中间那一块卡片，上下两块原地不动（D-19）", "mut", 11.5)
    text(W - GUT, y + 15, "★开关在页体，状态在外壳（V-12）", "mut", 11, "end")

    y += 46
    rect(GUT, y, W - 2 * GUT, 26, "panel", rx=6)
    rect(GUT, y, 3, 26, "mark")
    text(GUT + 14, y + 17, "这一炮该怎么打，以及照这么打会发生什么。", "lbl", 12.5)
    text(GUT + 320, y + 17, "展开说明 ▾", "acc-t", 12)
    text(W - GUT - 10, y + 17,
         "★引言折成一行 —— 首屏要留给输出（V-13）", "mut", 11, "end")
    return y + 38


def shared_column(x, y, w, h, mode: str) -> None:
    """The two shared panels plus the one card that changes with the mode."""
    card_h = 214
    ch = h - card_h - 12
    cy = panel(x, y, w, ch, "这一炮 · 加热与驱动（三个模式共用）")
    sy = cy + 8
    for lab, val, f in [("平顶电流 Ip [kA]", "400", .40), ("大半径 R₀ [m]", "1.85", .55),
                        ("平顶小半径 a [m]", "0.445", .62), ("拉长比 κ", "1.65", .58),
                        ("上三角度 δu", "0.40", .40),
                        ("击穿 → 平顶 → 结束 [s]", "0 · 1 · 8 · 10", .80),
                        ("NBI [MW]", "4.0", .50), ("ECRH [MW]", "1.0", .20)]:
        slider(x + 14, sy, w - 28, f, lab, val)
        sy += 34
    text(x + 14, sy + 6, "★一个量一个控件（D-20）：三个模式读的是同一份，", "mut", 10.5)
    text(x + 14, sy + 20, "所以它住在功能栏之外。", "mut", 10.5)

    # --- the one card that changes ------------------------------------------
    ky = y + ch + 12
    titles = {"config": "配置：求解器 · 击穿 · 单时刻",
              "design": "设计：波点与校验",
              "sim": "仿真：驱动控制台"}
    ky2 = panel(x, ky, w, card_h, titles[mode])
    rect(x - 4, ky - 4, w + 8, card_h + 8, "zone", rx=10)
    text(x + w / 2, ky - 10, "③ 随模式而换的一块（D-19）", "zone-t", 10.5, "middle")
    if mode == "config":
        for i, (lab, val) in enumerate([("平衡求解器", "自由边界 · Picard"),
                                        ("网格", "129 × 129"),
                                        ("击穿场零目标", "|B| < 2 mT")]):
            text(x + 14, ky2 + 10 + i * 30, lab, "mut", 11.5)
            text(x + w - 14, ky2 + 10 + i * 30, val, "lbl", 11.5, "end")
        btn(x + 14, ky2 + 104, w - 28, 28, "静态反解这一时刻", "btn-a", "btn-at")
        text(x + 14, ky2 + 152, "★这一档说的是「这组目标存在一个静态解」，", "mut", 10.5)
        text(x + 14, ky2 + 166, "不等于能这么运行（D-16）。", "mut", 10.5)
    elif mode == "design":
        text(x + 14, ky2 + 8, "波点（LCFS 目标）", "mut", 11.5)
        for i, (t, ok) in enumerate([("0.40 s", True), ("1.00 s", True),
                                     ("3.20 s", True), ("8.00 s", False)]):
            ry = ky2 + 26 + i * 26
            rect(x + 14, ry, w - 28, 22, "input", rx=4)
            add(f'<circle cx="{x + 26:.1f}" cy="{ry + 11:.1f}" r="4" '
                f'class="{"solved" if ok else "interp"}"/>')
            text(x + 38, ry + 15, t, "lbl", 11.5)
            text(x + w - 24, ry + 15, "已解" if ok else "未校验",
                 "ok-t" if ok else "warn-t", 11, "end")
        text(x + 14, ky2 + 148, "★每个波点是静态反解的目标，", "mut", 10.5)
        text(x + 14, ky2 + 162, "不是已实现的位形（D-1 · D-5）。", "mut", 10.5)
    else:
        text(x + 14, ky2 + 10, "相位", "mut", 11.5)
        text(x + w - 14, ky2 + 10, "平顶（第 3 态 / 共 5）", "lbl", 11.5, "end")
        text(x + 14, ky2 + 36, "保真度", "mut", 11.5)
        for i, (lab, on) in enumerate([("0-D", True), ("1.5-D", False)]):
            rect(x + 62 + i * 74, ky2 + 24, 66, 22, "chip-on" if on else "chip-off", rx=5)
            text(x + 95 + i * 74, ky2 + 39, lab, "acc-t" if on else "mut", 11.5,
                 "middle", "700" if on else None)
        text(x + 14, ky2 + 60, "★只有仿真有这个开关 —— 只有它有时间在走（D-22）",
             "mut", 10.5)
        btn(x + 14, ky2 + 74, w - 28, 28, "断开 —— 停止推进", "btn-a", "btn-at")
        text(x + 14, ky2 + 132, "磁通余量", "mut", 11.5)
        rect(x + 14, ky2 + 140, w - 28, 10, "gauge-bg", rx=5)
        rect(x + 14, ky2 + 140, (w - 28) * .38, 10, "gauge", rx=5)
        text(x + 14, ky2 + 168, "★还能撑 2.4 s（未声明摆幅时报「未知」，D-17）",
             "mut", 10.5)


def corridor(x, y, w, h, mode: str) -> None:
    """The 0-D corridor — the panel whose time axis IS the mode (D-18)."""
    caps = {"config": "⑧ 这一时刻（配置模式没有时间轴 —— 这一格画的是击穿场零）",
            "design": "⑧ 时序走廊：整条脉冲已经存在，播放头在其中回读（D-8）",
            "sim": "⑧ 滚动走廊：右缘就是现在，右边没有画出来（D-11 · D-12）"}
    cy = panel(x, y, w, h, caps[mode])
    ax, ay = x + 46, cy + 6
    #: ★the axes stop 96 px short of the panel, not 62: the solved/interpolated
    #: markers live BELOW the axis (that is the point — they are a property of
    #: the time grid, not of the trace) and they need the room, as does the one
    #: line that says what a hollow ring means.
    aw, ah = w - 62, h - 96
    rect(ax, ay, aw, ah, "axes")
    for i in range(1, 4):
        line(ax, ay + ah * i / 4, ax + aw, ay + ah * i / 4, "grid")

    if mode == "config":
        #: ★A poloidal map has to be isometric or it misreads — and a 1200 x 190
        #: box cannot hold one.  So the map takes a square at the left and the
        #: rest of the row goes to what this mode actually owes the reader:
        #: whether a static solution EXISTS, and how far off the targets it is.
        mw = ah
        figure(ax - 34, ay - 6, mw + 46, ah + 12,
               "击穿场零 —— 等比例", [
            ("wall", [((r - .5) * 1.10 + .5, (z - .5) * 1.10 + .5)
                      for r, z in dshape()]),
            ("null1", [(.5 + .30 * math.cos(a / 60 * 6.2832),
                        .5 + .30 * math.sin(a / 60 * 6.2832)) for a in range(61)]),
            ("null1", [(.5 + .19 * math.cos(a / 60 * 6.2832),
                        .5 + .19 * math.sin(a / 60 * 6.2832)) for a in range(61)]),
            ("null2", [(.5 + .09 * math.cos(a / 60 * 6.2832),
                        .5 + .09 * math.sin(a / 60 * 6.2832)) for a in range(61)]),
        ], ylab="Z [m]", iso=True)
        rx2 = ax + mw + 40
        text(rx2, ay + 12, "这一时刻的判定", "lbl", 12.5, weight="700")
        text(rx2 + 108, ay + 12, "（左图：|B| 等值线，灰虚线＝真空室内壁）",
             "mut", 11)
        readings(rx2, ay + 38, 420, [
            ("静态解", "存在", "自由边界 Picard，17 次迭代收敛"),
            ("形状误差 (RMS)", "6.2 mm", "对 24 个控制点"),
            ("场零 |B| 半径", "0.11 m", "判据 |B| < 2 mT")])
        text(rx2 + 480, ay + 38,
             "★这一档说的是「这组目标存在一个静态解」，", "mut", 11.5)
        text(rx2 + 480, ay + 56,
             "不等于能这么运行（D-16）：这里没有控制器的增益、", "mut", 11.5)
        text(rx2 + 480, ay + 74,
             "时滞与噪声，也没有一条时间轴可以违反。", "mut", 11.5)
        text(rx2 + 480, ay + 106,
             "★没有时间轴，所以这一格不是走廊：一个时刻，一张图（D-18）。",
             "mut", 11.5)
        return

    # the phase bands, and their boundaries drawn as lines (not colour alone)
    for t0, t1, cls, lab in [(.00, .10, "ph0", "击穿"), (.10, .20, "ph1", "上升"),
                             (.20, .80, "ph2", "平顶"), (.80, 1.0, "ph1", "下降")]:
        rect(ax + aw * t0, ay, aw * (t1 - t0), ah, cls)
        line(ax + aw * t1, ay, ax + aw * t1, ay + ah, "sep")
        text(ax + aw * (t0 + t1) / 2, ay + 14, lab, "mut", 10.5, "middle")
    trap = [(0, .06), (.10, .06), (.20, .86), (.80, .86), (.92, .30), (1, .06)]
    now = MODE_STATE[mode][2]
    if mode == "sim":
        rect(ax + aw * now, ay, aw * (1 - now), ah, "future")
        rect(ax + aw * now, ay, aw * (1 - now), ah, "future-e")
        text(ax + aw * (now + 1) / 2, ay + ah / 2, "未来未算", "mut", 12.5, "middle", "700")
        trap = [(t, v) for t, v in trap if t <= now] + [(now, .86)]
    d = " ".join(f"{ax + aw * t:.1f},{ay + ah * (1 - v):.1f}" for t, v in trap)
    add(f'<polyline points="{d}" class="c1"/>')

    if mode == "design":
        #: ★solved vs interpolated: filled disc + a tick on the axis, hollow
        #: ring for the rest.  Two channels, because a reader in greyscale must
        #: still be able to tell which slices were actually solved (D-8 · V-8)
        for t in [i / 20 for i in range(21)]:
            solved = abs(t * 20 - round(t * 20)) < 1e-9 and int(round(t * 20)) % 4 == 0
            px, py = ax + aw * t, ay + ah + 9
            if solved:
                add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.4" class="solved"/>')
                line(px, ay + ah, px, ay + ah + 4, "tick")
            else:
                add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" class="interp"/>')
        text(ax, ay + ah + 30, "● 已解片（真解过的时刻）    ○ 插值片 —— "
                               "圈是空的，不只是颜色浅（D-8）", "mut", 11)
    else:
        for t, lab in [(.24, "改了 NBI"), (.33, "改了 Ip 目标")]:
            px = ax + aw * t
            line(px, ay, px, ay + ah, "edit")
            add(f'<path d="M{px - 4:.1f} {ay + ah + 2:.1f}h8l-4 7z" class="editf"/>')
            text(px + 7, ay + ah + 16, lab, "bad-t", 10.5)
        text(ax, ay + ah + 32, "★滑块改的是未来：改动点与它的后果在同一条轴上，"
                               "改动点左边一个点也没有重算（D-12）", "mut", 11)

    ph = ax + aw * now
    line(ph, ay, ph, ay + ah, "fold")
    text(ph + 6, ay + 16, ("播放头 t = 3.20 s" if mode == "design"
                           else "现在 t = 4.15 s"), "fold-t", 11)


def views(x, y, w, h, mode: str) -> None:
    """The three view panels: cross-section, profiles, PF channels."""
    gw = (w - 24) / 3
    # ---- ④ the equilibrium slice -------------------------------------------
    badge = {"config": ("已解 @ 这一时刻", "ok-t"),
             "design": ("插值 —— 最近真解 2.80 s", "warn-t"),
             "sim": ("已解 @ 4.10 s（上一节拍）", "ok-t")}[mode]
    c = panel(x, y, gw, h, "④ 平衡截面 · 这一片")
    text(x + 12, c + 2, badge[0], badge[1], 11, weight="700")
    figure(x + 10, c + 10, gw - 20, h - 58,
           "LCFS（红）· 目标（灰虚）—— 等比例", [
        ("tgt", [((r - .5) * 1.06 + .5, (z - .5) * 1.06 + .5) for r, z in dshape()]),
        ("lcfs", dshape())], iso=True)
    # ---- ⑤ the profiles -----------------------------------------------------
    x2 = x + gw + 12
    c = panel(x2, y, gw, h, "⑤ 剖面 · 这一片")
    text(x2 + 12, c + 2, "0-D 规定剖面 —— 不是解出来的", "warn-t", 11, weight="700")
    prof = lambda k: [(t / 12, (1 - (t / 12) ** 2) ** k * .88 + .06) for t in range(13)]
    fh = (h - 62) / 2 - 6
    figure(x2 + 10, c + 10, gw - 20, fh, "n_e [10¹⁹ m⁻³]  ρ", [("c1", prof(.7))])
    figure(x2 + 10, c + 16 + fh, gw - 20, fh, "T_e · T_i [keV]  ρ",
           [("c2", prof(1.6)), ("c3", prof(1.3))])
    # ---- ⑥ the PF channels --------------------------------------------------
    x3 = x2 + gw + 12
    c = panel(x3, y, gw, h, "⑥ PF 通道")
    if mode == "config":
        text(x3 + 12, c + 2, "这一时刻的电流 —— 没有时间轴，所以是柱不是波形",
             "mut", 11)
        n, bx0, bw2 = 6, x3 + 26, (gw - 52) / 6
        base = c + h - 74
        for i, (v, over) in enumerate([(.62, False), (.38, False), (.86, False),
                                       (1.12, True), (.44, False), (.70, False)]):
            hh = min(v, 1.25) * 108
            rect(bx0 + i * bw2 + 4, base - hh, bw2 - 8, hh,
                 "bar-over" if over else "bar-v", rx=2)
            text(bx0 + i * bw2 + bw2 / 2, base + 14, f"PF{i + 1}", "mut", 10, "middle")
            if over:
                add(f'<path d="M{bx0 + i * bw2 + bw2 / 2 - 5:.1f} {base - hh - 6:.1f}'
                    f'h10l-5-8z" class="editf"/>')
                text(bx0 + i * bw2 + bw2 / 2, base - hh - 14, "越限", "bad-t", 10, "middle")
        line(x3 + 20, base - 108, x3 + gw - 20, base - 108, "lim")
        text(x3 + gw - 22, base - 112, "上限（你给的统一值）", "mut", 10, "end")
        text(x3 + 12, c + h - 44, "★装置描述里没有逐路电源上限 —— 页面把这句话",
             "mut", 10.5)
        text(x3 + 12, c + h - 30, "写在控件旁边，不假装有一张限值表。", "mut", 10.5)
    else:
        text(x3 + 12, c + 2, "实线＝按设计的前馈　虚线＝随等离子体状态（D-14）",
             "mut", 11)
        fh2 = h - 78
        cut = MODE_STATE[mode][2]
        #: two channels, each a feed-forward ramp (solid) that hands over to a
        #: state-following flat top (dashed) at the end of the ramp — the two
        #: halves of D-14 drawn as two LINE STYLES, not two colours
        segs = []
        for k, (a0, a1) in enumerate([(.50, .80), (.50, .26)]):
            ramp = [(t / 10 * .20, a0 + (a1 - a0) * (t / 10) ** 1.4)
                    for t in range(11)]
            flat = [(.20 + t / 20 * .80,
                     a1 + (.05 if k == 0 else -.04) * math.sin(t / 20 * 5.0))
                    for t in range(21)]
            if mode == "sim":
                flat = [(t, v) for t, v in flat if t <= cut]
            segs += [("ff", ramp), ("fb", flat)]
        figure(x3 + 10, c + 14, gw - 20, fh2, "I_PF [kA]  t [s]", segs, ylab="I_PF")
        text(x3 + 12, c + fh2 + 34, "★上升沿是前馈（D-4），平顶随状态（D-6）——", "mut", 10.5)
        text(x3 + 12, c + fh2 + 48, "两段线型不同，不只是颜色不同。", "mut", 10.5)


def draw_pd_mode(d: Path, mode: str) -> None:
    lab = dict(MODES)[mode]
    y = pd_head(mode, f"fylite 放电设计页 — {lab}模式",
                f"fylite 放电设计页{lab}模式在 16:9 首屏上的概念布局")
    lw = 320
    bh = H - y - 34
    corr_h = 250
    shared_column(GUT, y, lw, bh, mode)
    rx_ = GUT + lw + 14
    rw = W - GUT - rx_
    views(rx_, y, rw, bh - corr_h - 12, mode)
    corridor(rx_, y + bh - corr_h, rw, corr_h, mode)
    foot(f"概念图：放电设计页 {lab}模式的 16:9 首屏。外壳三张图逐字相同；"
         f"变的是时间轴的含义，以及跟着它变的那四类面板。"
         f"生成物 —— tools/make-desktop-preview.py")
    write(d, f"pd-{mode}.svg")


#: The other three pages' vocabularies.  Each row is
#: (状态, 样例, 除颜色之外的通道, 出处) — and the third column is the point.
VOCAB_MODEL = [
    ("输运栏：你给的 χ", ("line-solid", "输入"), "实线 + 抬头写「你给的」", "P-28"),
    ("反演栏：反求的 χ", ("line-dot", "由 T 反求"), "同色点线 —— 线型说方向", "P-28"),
    ("解出来的 T", ("line-points", ""), "实线 + 实心采样点", "P-28"),
    ("给定的 T（反演的输入）", ("line-dash", "反演的输入"), "灰虚线，无点", "P-28"),
    ("判定：通过", ("chip-ok", "位形误差 6.2 mm < 10 mm"), "勾 + 判据与实测值都写出", "P-5"),
    ("判定：不通过", ("chip-bad", "边界 q 2.8 < 3.0"), "叉 + 差在哪写出", "P-5"),
    ("超出适用域，拒绝", ("hatch", "拒绝外推"), "斜纹 + 写「拒绝」，不给数", "P-6"),
    ("输入变了，尚未重算", ("grey", "上一次的答案已作废 —— 未重算"), "整块变灰 + 一句话",
     "P-8"),
    ("网格与单位", ("mono", "129×129 · SI · ρ_tor · COCOS 17"), "解旁边一行等宽小字",
     "P-17"),
    ("自由边界 / 固定边界", ("two-line", "两种来源"), "线型 + 抬头写哪一种",
     "P-20"),
    ("交出去的工件", ("mono", "model-2026-09-01T14:03.fyo"), "有名字，不是一条总线",
     "P-21"),
    ("这一栏报不出的量", ("text-only", "τ_E —— 这一栏的几何是固定的，报不出"),
     "写明为什么报不出，不留空", "P-14"),
]

VOCAB_ANALYSIS = [
    ("后验采样带", ("band", "只含压强 σ"), "带 + 抬头写它包了什么", "P-9"),
    ("未计入的不确定度", ("grey", "诊断几何 · 模型本身：未计入"), "灰底 + 逐条列出",
     "P-9"),
    ("残差", ("stem", ""), "零线上的杆 + 点，不是一条折线", "P-29"),
    ("动理学约束在场", ("chip-ok", "p(ψ) 已约束（Thomson 65 点）"),
     "勾 + 写清是哪一路约束", "P-22"),
    ("只有磁测量", ("chip-bad", "内部剖面未被约束"), "叉 + 写明约束不住什么", "P-22"),
    ("折起来的控件仍在生效", ("chip-mut", "重采样 ▸｜3 项已设，仍在生效"),
     "折叠标题上一枚计数芯片", "P-16"),
    ("预设只填不跑", ("chip-mut", "填入预设｜不会自动运行"), "按钮写「填入」+ 旁注",
     "P-23"),
    ("这一路诊断缺席", ("grey", "MSE —— 无此炮"), "灰行 + 写「无此炮」而不是留空",
     "P-9"),
    ("拟合 vs 测量", ("points-only", "点＝测量，线＝拟合"), "点与线，两种图元", "P-29"),
    ("复算对上没对上", ("mono", "I_p 复算 / 测量  398 / 400 kA（0.5 %）"),
     "两个数并排 + 闭合差", "P-13"),
    ("拟合优度", ("mono", "χ² / dof 1.12 · 84 路测量 · 7 自由度"),
     "数旁边写它的分母", "P-13"),
    ("批处理里失败的那几炮", ("grey", "12 / 40 炮 · 3 炮失败，逐炮列出原因"),
     "计数 + 逐条原因，不是一个进度条", "P-8"),
]

VOCAB_DATA = [
    ("抽稀取回的曲线", ("line-points", "256 / 12480 点"),
     "采样点画出来 + 图注写两个数", "P-11 · P-30"),
    ("全取的曲线", ("line-points", "121 / 121 点（全取）"), "同样画点，两个数相等",
     "P-30"),
    ("没有网关", ("grey", "这一页需要一个能开套接字的进程"),
     "命名那个缺失的进程，不画空图", "P-10"),
    ("目录说「存在」", ("text-only", "存在 —— 不是「已记录」"),
     "用词本身就是那条区分", "P-18"),
    ("该炮没有这个节点", ("grey", "\\EAST::TOP.MSE —— 该炮无此节点"),
     "写出路径 + 写出为什么", "P-10"),
    ("服务器拒绝了", ("badge", "服务器返回 TreeNODATA，未改写"),
     "虚线框 + 原样转述服务器的话", "P-12"),
    ("这一页只读", ("chip-mut", "只读｜没有入口能写、能删、能求值"),
     "抬头一枚芯片 + 一句话", "P-11"),
    ("工作区的足迹", ("mono", "树 · 炮号 · 节点 · 窗 · 步长（指针，不是值）"),
     "等宽列出，并写明是指针", "P-24"),
    ("时间窗改了", ("window", "重取一遍"), "选区 + 写「重取」，不是本地放大", "P-11"),
    ("单位缺失", ("grey", "单位：树里没写"), "写「树里没写」，不猜一个", "P-13"),
    ("两次取回步长不同", ("two-line", "窗变 → 步长变"),
     "两条线 + 一句因果", "P-11"),
    ("直接路径", ("mono", "\\EAST::TOP.PCS:IP"), "等宽 + 可复制", "P-13"),
]

def _generic_sample(x, y, kind, lab) -> None:
    """The generic sample set the other three pages draw from.

    ★Deliberately small.  A vocabulary table whose every row needs its own
    drawing code is a table nobody will extend, and an unextended vocabulary
    table is worse than none: it says "these are all the states", and it is
    wrong the first time a state is added.
    """
    W_ = 200
    if kind == "line-solid":
        add(f'<polyline points="{x},{y + 7} {x + 60},{y - 6} {x + 130},{y - 4} '
            f'{x + W_},{y + 2}" class="c1"/>')
    elif kind == "line-dash":
        add(f'<polyline points="{x},{y + 7} {x + 60},{y - 6} {x + 130},{y - 4} '
            f'{x + W_},{y + 2}" class="c5"/>')
    elif kind == "line-dot":
        add(f'<polyline points="{x},{y + 7} {x + 60},{y - 6} {x + 130},{y - 4} '
            f'{x + W_},{y + 2}" class="c-dot"/>')
    elif kind == "line-points":
        add(f'<polyline points="{x},{y + 7} {x + 50},{y - 5} {x + 100},{y - 7} '
            f'{x + 150},{y - 2} {x + W_},{y + 4}" class="c1"/>')
        for k, dy in ((0, 7), (50, -5), (100, -7), (150, -2), (200, 4)):
            add(f'<circle cx="{x + k:.1f}" cy="{y + dy:.1f}" r="2.8" class="solved"/>')
    elif kind == "points-only":
        #: points ARE the measurement and the line IS the fit — two figure
        #: kinds, so the reader never has to ask which is which
        add('<polyline points="' + " ".join(
            f"{x + k:.1f},{y + 4 - 8 * math.sin(k / 44):.1f}"
            for k in range(0, 201, 10)) + '" class="c1"/>')
        for k in range(0, 201, 25):
            dy = 4 - 8 * math.sin(k / 44) + (2.4 if (k // 25) % 2 else -2.6)
            add(f'<circle cx="{x + k:.1f}" cy="{y + dy:.1f}" r="2.8" class="interp"/>')
    elif kind == "band":
        add(f'<path d="M{x},{y - 3} L{x + W_},{y - 11} L{x + W_},{y + 7} '
            f'L{x},{y + 13} Z" class="postband"/>')
        add(f'<polyline points="{x},{y + 5} {x + W_},{y - 2}" class="c1"/>')
    elif kind == "stem":
        line(x, y, x + W_, y, "zero")
        for k in range(10, 201, 20):
            v = 11 * math.sin(k * .7) * math.cos(k * .21)
            line(x + k, y, x + k, y - v, "s1")
            add(f'<circle cx="{x + k:.1f}" cy="{y - v:.1f}" r="2.2" class="s1f"/>')
    elif kind == "hatch":
        rect(x, y - 11, W_, 22, "future")
        rect(x, y - 11, W_, 22, "future-e")
        text(x + W_ / 2, y + 4, lab, "mut", 10.5, "middle")
        return
    elif kind == "grey":
        rect(x, y - 11, W_, 22, "bar-rest", rx=4)
        text(x + 8, y + 4, lab, "mut", 11)
        return
    elif kind == "chip-ok":
        rect(x, y - 11, 22, 22, "chip-on", rx=4)
        add(f'<path d="M{x + 6:.1f} {y:.1f}l4 5 7-9" class="okmark"/>')
        text(x + 30, y + 4, lab, "ok-t", 11.5, weight="700")
        return
    elif kind == "chip-bad":
        rect(x, y - 11, 22, 22, "chip-off", rx=4)
        add(f'<path d="M{x + 7:.1f} {y - 4:.1f}l8 8M{x + 15:.1f} {y - 4:.1f}l-8 8"'
            f' class="badmark"/>')
        text(x + 30, y + 4, lab, "bad-t", 11.5, weight="700")
        return
    elif kind == "chip-mut":
        rect(x, y - 11, 78, 22, "chip-off", rx=11)
        text(x + 39, y + 4, lab.split("｜")[0], "mut", 11, "middle")
        text(x + 88, y + 4, lab.split("｜")[-1], "mut", 11)
        return
    elif kind == "badge":
        rect(x, y - 11, 150, 22, "warnbox", rx=4)
        text(x + 8, y + 4, lab, "warn-t", 11)
        return
    elif kind == "mono":
        rect(x, y - 11, W_, 22, "bar-rest", rx=4)
        add(f'<text x="{x + 8:.1f}" y="{y + 4:.1f}" class="mono" font-size="11">'
            f'{esc(lab)}</text>')
        return
    elif kind == "bars":
        for i, (v, over) in enumerate([(.5, False), (.8, False), (1.1, True),
                                       (.35, False), (.65, False)]):
            hh = min(v, 1.2) * 18
            rect(x + i * 26, y + 10 - hh, 18, hh, "bar-over" if over else "bar-v", rx=2)
        line(x - 3, y - 8, x + 132, y - 8, "lim")
        text(x + 142, y + 4, lab, "mut", 11)
        return
    elif kind == "window":
        line(x, y + 8, x + W_, y + 8, "axes")
        add(f'<polyline points="{x},{y + 6} {x + 40},{y - 6} {x + 120},{y - 4} '
            f'{x + W_},{y + 5}" class="c1"/>')
        rect(x + 60, y - 11, 70, 22, "bar-seen")
        text(x + 95, y + 4, lab, "acc-t", 10, "middle")
        return
    elif kind == "two-line":
        add(f'<polyline points="{x},{y + 8} {x + 70},{y - 5} {x + W_},{y - 3}"'
            f' class="c1"/>')
        add(f'<polyline points="{x},{y + 10} {x + 70},{y + 1} {x + W_},{y + 3}"'
            f' class="c3"/>')
    elif kind == "text-only":
        text(x, y + 4, lab, "mut", 11.5)
        return
    if lab:
        text(x + W_ + 12, y + 4, lab, "mut", 10.5)


def draw_vocab(d: Path, name: str, page: str, doc: str, rows) -> None:
    """A page's visual vocabulary: every state it draws, and the channel it
    uses BESIDES colour.

    ★One function for all four pages, because the discipline is one discipline
    (`FYL-DESIGN-10` P-27).  What differs is the row list — which is exactly
    what each page document owns.
    """
    head(f"fylite {page} — 视觉词汇",
         f"{page}的状态编码表：每一种状态的颜色与它的非颜色通道")
    text(GUT, 46, f"{page}的视觉词汇", "lbl", 18, weight="700")
    text(GUT, 74, "左列是这一页把它画成什么样，中列是它除颜色之外还带的那个通道。"
                  "中列不是可选项：", "mut", 13)
    text(GUT, 96, "一张只靠颜色分状态的图，灰度打印之后就什么也没分 —— "
                  f"FYL-DESIGN-11 的 V-8，与 {doc} 的那一条是同一件事。", "mut", 13)
    top = 134
    rh = (H - top - 40) / len(rows)
    cw = 300
    for i, (nm, sample, chan, prov) in enumerate(rows):
        ry = top + i * rh
        if i:
            line(GUT, ry, W - GUT, ry, "sep")
        text(GUT + 6, ry + rh / 2 + 5, nm, "lbl", 13)
        _vocab_sample(GUT + cw, ry + rh / 2, sample)
        text(GUT + cw + 360, ry + rh / 2 + 5, chan, "mut", 12.5)
        text(W - GUT - 6, ry + rh / 2 + 5, prov, "acc-t", 11.5, "end")
    line(GUT, top - 2, W - GUT, top - 2, "strip-inner")
    text(GUT + 6, top - 12, "状态", "mut", 11.5, weight="700")
    text(GUT + cw, top - 12, "画出来的样子", "mut", 11.5, weight="700")
    text(GUT + cw + 360, top - 12, "★除颜色之外的那个通道", "mut", 11.5, weight="700")
    text(W - GUT - 6, top - 12, "出处", "mut", 11.5, "end", "700")
    foot(f"概念图：{doc} 的状态编码。左列是页面上的样子，"
         "中列是它在灰度下仍然读得出来的理由。生成物 —— tools/make-desktop-preview.py")
    write(d, name)


def draw_pd_vocab(d: Path) -> None:
    """Every state this page draws, and the channel it uses BESIDES colour."""
    head("fylite 放电设计页 — 视觉词汇",
         "放电设计页的状态编码表：每一种状态的颜色与它的非颜色通道")
    #: ★plain text only — this is SVG, and Markdown emphasis would ship as
    #: literal asterisks and backticks.  It did, on the first run.
    text(GUT, 46, "放电设计页的视觉词汇", "lbl", 18, weight="700")
    text(GUT, 74, "左列是这一页把它画成什么样，中列是它除颜色之外还带的那个通道。"
                  "中列不是可选项：", "mut", 13)
    text(GUT, 96, "一张只靠颜色说「这一片没解过」的图，灰度打印之后什么也没说"
                  "—— FYL-DESIGN-11 的 V-8，与 D-8 是同一条。", "mut", 13)

    rows = [
        ("已解片", "solved-dot", "实心圆点 + 轴上一道刻线", "D-8"),
        ("插值片", "interp-dot", "空心圆环，圈是空的", "D-8"),
        ("相位带（击穿 / 上升 / 平顶 / 下降）", "phase", "带上写字 + 边界一条竖线", "D-3 · D-16"),
        ("PF 前馈段", "ffline", "实线", "D-4 · D-14"),
        ("PF 随状态段", "fbline", "同色虚线", "D-6 · D-14"),
        ("越限通道", "over", "柱变色 + 柱顶一个三角 + 写「越限」", "D-6 推论 2"),
        ("限值缺失", "nolim", "灰底 + 写明「上限是你给的统一值」", "as-built"),
        ("线性化过期", "stale", "虚线框 + 徽章文字", "D-7"),
        ("滑块改动点", "editm", "竖线 + 轴下一个三角 + 写改了什么", "D-12"),
        ("未来未算", "fut", "斜纹底 + 写「未来未算」", "D-11"),
        ("目标 vs 实现", "tgtreal", "目标虚线、实现实线", "D-16"),
        ("这一片解过 / 没解过", "badge", "面板抬头写成一句话，不只是边框颜色", "D-8"),
    ]
    top = 134
    rh = (H - top - 40) / len(rows)
    cw = 300
    for i, (name, kind, chan, prov) in enumerate(rows):
        ry = top + i * rh
        if i:
            line(GUT, ry, W - GUT, ry, "sep")
        text(GUT + 6, ry + rh / 2 + 5, name, "lbl", 13)
        sx, sy = GUT + cw, ry + rh / 2
        _vocab_sample(sx, sy, kind)
        text(GUT + cw + 360, ry + rh / 2 + 5, chan, "mut", 12.5)
        text(W - GUT - 6, ry + rh / 2 + 5, prov, "acc-t", 11.5, "end")
    line(GUT, top - 2, W - GUT, top - 2, "strip-inner")
    text(GUT + 6, top - 12, "状态", "mut", 11.5, weight="700")
    text(GUT + cw, top - 12, "画出来的样子", "mut", 11.5, weight="700")
    text(GUT + cw + 360, top - 12, "★除颜色之外的那个通道", "mut", 11.5, weight="700")
    text(W - GUT - 6, top - 12, "出处", "mut", 11.5, "end", "700")
    foot("概念图：FYL-DESIGN-09 的状态编码。左列是页面上的样子，"
         "中列是它在灰度下仍然读得出来的理由。生成物 —— tools/make-desktop-preview.py")
    write(d, "pd-vocab.svg")


def _vocab_sample(x, y, spec) -> None:
    """One 200 x 26 sample of a state, drawn the way the page draws it.

    `spec` is either a bare kind (the pulse page's hand-drawn set) or a
    `(kind, label)` pair from the generic set below.
    """
    if isinstance(spec, tuple):
        _generic_sample(x, y, spec[0], spec[1])
        return
    kind = spec
    if kind == "solved-dot":
        line(x, y - 8, x + 200, y - 8, "axes")
        for k in (0, 60, 120, 180):
            line(x + 30 + k, y - 8, x + 30 + k, y - 3, "tick")
            add(f'<circle cx="{x + 30 + k:.1f}" cy="{y + 3:.1f}" r="4" class="solved"/>')
    elif kind == "interp-dot":
        for k in (0, 60, 120, 180):
            add(f'<circle cx="{x + 30 + k:.1f}" cy="{y + 3:.1f}" r="3.2" class="interp"/>')
        line(x, y - 8, x + 200, y - 8, "axes")
    elif kind == "phase":
        for t0, t1, cls, lab in [(0, .18, "ph0", "击穿"), (.18, .34, "ph1", "上升"),
                                 (.34, .82, "ph2", "平顶"), (.82, 1, "ph1", "下降")]:
            rect(x + 200 * t0, y - 11, 200 * (t1 - t0), 22, cls)
            line(x + 200 * t1, y - 11, x + 200 * t1, y + 11, "sep")
            text(x + 200 * (t0 + t1) / 2, y + 4, lab, "mut", 9, "middle")
    elif kind in ("ffline", "fbline"):
        cls = "ff" if kind == "ffline" else "fb"
        add(f'<polyline points="{x},{y + 6} {x + 60},{y - 6} {x + 140},{y - 2} '
            f'{x + 200},{y + 4}" class="{cls}"/>')
    elif kind == "over":
        rect(x + 20, y - 10, 26, 20, "bar-over", rx=2)
        add(f'<path d="M{x + 28:.1f} {y - 14:.1f}h10l-5-8z" class="editf"/>')
        text(x + 56, y + 4, "越限 12.4 > 12.0 kA", "bad-t", 11)
    elif kind == "nolim":
        rect(x, y - 11, 200, 22, "bar-rest", rx=4)
        text(x + 8, y + 4, "上限 12.0 kA（你给的统一值）", "mut", 11)
    elif kind == "stale":
        rect(x, y - 11, 150, 22, "warnbox", rx=4)
        text(x + 8, y + 4, "线性化已过期", "warn-t", 11)
    elif kind == "editm":
        line(x + 60, y - 11, x + 60, y + 6, "edit")
        add(f'<path d="M{x + 56:.1f} {y + 7:.1f}h8l-4 7z" class="editf"/>')
        text(x + 72, y + 4, "改了 NBI", "bad-t", 11)
    elif kind == "fut":
        rect(x, y - 11, 100, 22, "bar-seen")
        rect(x + 100, y - 11, 100, 22, "future")
        rect(x + 100, y - 11, 100, 22, "future-e")
        text(x + 150, y + 4, "未来未算", "mut", 10, "middle")
    elif kind == "tgtreal":
        add(f'<polyline points="{x},{y + 7} {x + 70},{y - 7} {x + 200},{y - 7}"'
            f' class="tgt"/>')
        add(f'<polyline points="{x},{y + 8} {x + 80},{y - 3} {x + 200},{y - 5}"'
            f' class="c1"/>')
    elif kind == "badge":
        text(x, y - 3, "插值 —— 最近真解 2.80 s", "warn-t", 11.5, weight="700")
        text(x, y + 13, "已解 @ 3.20 s", "ok-t", 11.5, weight="700")


def main() -> None:
    global CHECK
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", default="docs/figures", type=Path)
    #: ★`--check` because these are COMMITTED generated artifacts.  A figure
    #: that has drifted from its generator is the failure this whole family of
    #: documents keeps naming: a drawing that still shows the layout somebody
    #: argued for two revisions ago, and nothing goes red.
    ap.add_argument("--check", action="store_true",
                    help="fail if what is on disk differs from what would be written")
    a = ap.parse_args()
    if a.check:
        CHECK = {}
    else:
        a.dir.mkdir(parents=True, exist_ok=True)
    print("桌面版外壳预览图（16:9，viewBox 无固定尺寸）：")
    draw_shell(a.dir)
    draw_data(a.dir)
    draw_pulse(a.dir)
    draw_model(a.dir)
    draw_analysis(a.dir)
    for mid, _ in MODES:
        draw_pd_mode(a.dir, mid)
    draw_pd_vocab(a.dir)
    draw_vocab(a.dir, "model-vocab.svg", "物理建模页", "FYL-DESIGN-10", VOCAB_MODEL)
    draw_vocab(a.dir, "an-vocab.svg", "实验分析页", "FYL-DESIGN-12", VOCAB_ANALYSIS)
    draw_vocab(a.dir, "data-vocab.svg", "装置数据页", "FYL-DESIGN-13", VOCAB_DATA)
    if CHECK is not None:
        stale = [k for k, v in CHECK.items() if v]
        if stale:
            raise SystemExit("生成物已漂移，请重跑 tools/make-desktop-preview.py：\n  "
                             + "\n  ".join(stale))
        print(f"{len(CHECK)} 张预览图与生成器一致。")


if __name__ == "__main__":
    main()
