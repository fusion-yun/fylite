#!/usr/bin/env python3
"""Draw the app's page concept figures (FYL-DESIGN-09 · FYL-DESIGN-10).

    python tools/make-app-figures.py [-d docs/figures]

★**Why a generator and not a hand-drawn SVG.**  The wireframe carries
NUMBERS — the four phase times, the flat-top current, the heating windows and
the play-head instant — and they are the same numbers as the design page's
defaults (`app/pages/design.html`).  A drawing whose Ip trapezoid does not
break where its own phase fields say it breaks is a picture of a discharge
nobody designed, and hand-editing a 900-line SVG is exactly how that happens.
Here the traces are computed from the schedule below, so the figure cannot
disagree with itself; changing the schedule redraws every panel at once.

★It is a CONCEPT drawing, not a screenshot: the panels are the ones
FYL-DESIGN-09 argues for, not the panels the page has today.  Nothing here
computes physics — the curves are illustrative shapes chosen to make the
layout legible (a flux consumption that saturates, a q95 that falls onto the
flat top), and the figure says so in its own footer.

Standard library only, deliberately: a docs figure must not add a dependency
to a repository whose runtime dependency is numpy alone.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

# --------------------------------------------------------------------------- #
# The schedule the figure draws.  These are `app/pages/design.html`'s own
# defaults; the play-head is a flat-top-approaching instant chosen so that the
# heating lane already shows two steps behind it.
# --------------------------------------------------------------------------- #
T_BD, T_RAMP, T_FLAT, T_END = 0.0, 1.0, 8.0, 10.0
IP_FLAT = 400.0                       # kA
T_NOW = 3.2                           # s — the play-head
PHASES = [(T_BD, T_RAMP, "上升 ramp-up"), (T_RAMP, T_FLAT, "平顶 flat-top"),
          (T_FLAT, T_END, "下降 ramp-down")]
#: 辅助加热：(名字, 单位功率, [(t_on, t_off, P)])
HEATING = [("NBI", "MW", [(1.0, 8.0, 2.0), (3.0, 6.5, 4.0)]),
           ("ECRH", "MW", [(2.0, 6.0, 1.0)]),
           ("LHCD", "MW", [(3.0, 8.0, 0.5)])]

W, H = 1240, 900 + 16
H_SIM = 1052 + 16
M = 16

# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
out: list[str] = []


def add(s: str) -> None:
    out.append(s)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def tw(s: str, size: float) -> float:
    """Rough advance width of a mixed CJK / latin string.

    ★A wrong estimate here is not cosmetic: pills and badges are sized from
    it, and a CJK label measured at latin width prints outside its own
    rounded rectangle.  CJK glyphs are full-width (1 em), latin about 0.55.

    ★★The full-width block is not the only thing that renders full-width.
    The punctuation these labels actually use — ★ ⟨⟩ —— … ⇒ — lives BELOW
    U+2E7F and was being charged latin width, which is how a verdict badge
    ended up with its own text hanging out of the right-hand end.  Measured
    on the rendered page, not guessed.
    """
    wide = "★☆⟨⟩—…‖⇒→←↔·—～‧′″"
    return sum(size * (1.0 if (ord(c) > 0x2E7F or c in wide) else 0.55)
               for c in s)


def rect(x, y, w, h, cls, rx=6, extra=""):
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{rx}" class="{cls}"{extra}/>')


def text(x, y, s, cls="lbl", size=11, anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" '
        f'text-anchor="{anchor}"{w}>{esc(s)}</text>')


def line(x1, y1, x2, y2, cls="grid", extra=""):
    add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'class="{cls}"{extra}/>')


def poly(points, cls, extra=""):
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    add(f'<polyline points="{d}" class="{cls}"{extra}/>')


def panel(x, y, w, h, title, num=None, badge=None, badge_cls="badge"):
    """A titled card.  ``num`` is the ①..⑧ callout the document refers to."""
    rect(x, y, w, h, "panel")
    ty = y + 19
    if num is not None:
        add(f'<circle cx="{x + 17:.1f}" cy="{ty - 4:.1f}" r="9" class="call"/>')
        add(f'<text x="{x + 17:.1f}" y="{ty - 0.5:.1f}" class="callt" '
            f'font-size="11" text-anchor="middle">{num}</text>')
        text(x + 31, ty, title, "title", 12.5, weight="600")
    else:
        text(x + 12, ty, title, "title", 12.5, weight="600")
    if badge:
        bw = tw(badge, 10) + 16
        rect(x + w - bw - 10, y + 7, bw, 17, badge_cls, rx=8)
        text(x + w - bw / 2 - 10, y + 19.5, badge, "badget", 10, "middle")
    line(x + 10, y + 29, x + w - 10, y + 29, "sep")
    return y + 29


def field(x, y, w, label, value):
    """A small labelled input box, as the page would draw one."""
    text(x, y + 8, label, "mut", 9.5)
    rect(x, y + 12, w, 19, "input", rx=4)
    text(x + 6, y + 25.5, value, "lbl", 10.5)


def chip(x, y, s, cls="chip", size=10):
    w = tw(s, size) + 16
    rect(x, y, w, 18, cls, rx=9)
    text(x + w / 2, y + 12.5, s, "chipt", size, "middle")
    return w


def handle(x, y, r=4.0, cls="handle"):
    add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" class="{cls}"/>')


class Axes:
    """A plot box with data->pixel mapping and no ceremony."""

    def __init__(self, x, y, w, h, xr, yr, *, frame=True):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.x0, self.x1 = xr
        self.y0, self.y1 = yr
        if frame:
            rect(x, y, w, h, "axes", rx=3)

    def px(self, t):
        return self.x + (t - self.x0) / (self.x1 - self.x0) * self.w

    def py(self, v):
        return self.y + self.h - (v - self.y0) / (self.y1 - self.y0) * self.h

    def plot(self, pts, cls, extra=""):
        poly([(self.px(t), self.py(v)) for t, v in pts], cls, extra)

    def vline(self, t, cls="playhead", extra=""):
        line(self.px(t), self.y, self.px(t), self.y + self.h, cls, extra)

    def band(self, t0, t1, cls):
        rect(self.px(t0), self.y, self.px(t1) - self.px(t0), self.h, cls, rx=0)


# --------------------------------------------------------------------------- #
# the illustrative traces
# --------------------------------------------------------------------------- #
def ramp(t, pts):
    """Piecewise-linear sampling helper (the shapes are illustrative)."""
    for (ta, va), (tb, vb) in zip(pts, pts[1:]):
        if ta <= t <= tb:
            f = 0.0 if tb == ta else (t - ta) / (tb - ta)
            return va + f * (vb - va)
    return pts[-1][1] if t > pts[-1][0] else pts[0][1]


def sample(fn, n=180, t0=T_BD, t1=T_END):
    return [(t0 + i * (t1 - t0) / n, fn(t0 + i * (t1 - t0) / n))
            for i in range(n + 1)]


IP = [(T_BD, 0.0), (T_RAMP, IP_FLAT), (T_FLAT, IP_FLAT), (T_END, 0.0)]
ip_of = lambda t: ramp(t, IP)                                     # noqa: E731
#: 消耗磁通：斜坡里几乎全部支出，平顶上按环电压线性慢涨，下降沿收回一点
flux_of = lambda t: (0.62 * (t / T_RAMP) ** 0.8 if t <= T_RAMP    # noqa: E731
                     else 0.62 + 0.031 * (min(t, T_FLAT) - T_RAMP)
                     - (0.10 * (t - T_FLAT) / (T_END - T_FLAT) if t > T_FLAT
                        else 0.0))
ne_of = lambda t: ramp(t, [(T_BD, 0.0), (T_RAMP, 3.4), (2.5, 4.0),   # noqa: E731
                           (T_FLAT, 4.0), (T_END, 0.6)])
#: n_GW ∝ Ip，所以格林沃尔德分数在斜坡上最紧张，而不是与密度同形
gw_of = lambda t: min(1.4, ne_of(t) / max(0.011 * ip_of(t), 0.6))  # noqa: E731
paux_of = lambda t: sum(p for a, b, p in                            # noqa: E731
                        [w for _, _, ws in HEATING for w in ws] if a <= t < b)
pohm_of = lambda t: ramp(t, [(T_BD, 0.0), (0.4, 1.5), (T_RAMP, 0.9),  # noqa: E731
                             (T_FLAT, 0.55), (T_END, 0.05)])
prad_of = lambda t: 0.28 * ne_of(t) ** 0.9 / 2.4                    # noqa: E731
q95_of = lambda t: (14.0 if t < 0.25 else                           # noqa: E731
                    ramp(t, [(0.25, 14.0), (T_RAMP, 4.4), (T_FLAT, 4.1),
                             (T_END, 9.0)]))
bn_of = lambda t: ramp(t, [(T_BD, 0.0), (T_RAMP, 0.7), (3.0, 1.0),  # noqa: E731
                           (3.6, 1.55), (6.5, 1.62), (T_FLAT, 1.2),
                           (T_END, 0.1)])
li_of = lambda t: ramp(t, [(T_BD, 1.45), (T_RAMP, 1.05), (T_FLAT, 0.92),  # noqa: E731
                           (T_END, 1.30)])


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #
#: The v2 shell, as these figures draw it (`FYL-DESIGN-11` V-11 / V-12).
#:
#: ★What was here before was an INVENTED page chrome: a 「脉冲设计工作台
#: (Pulse Design Workspace)」 title bar with a 装置 dropdown and a 预设 dropdown.
#: The workspace title never existed on the page, and the preset selector was
#: removed on 2026-09-01 — so these drawings were showing readers two controls
#: they would not find, in a strip shaped like nothing in the product.  A
#: concept drawing may invent a LAYOUT (that is what it is for); it may not
#: invent the chrome around it, because the reader has no way to tell which
#: half is the proposal.
#:
#: Now all the figures in this family carry the same strip as the 16:9
#: previews in `tools/make-desktop-preview.py`: two rows and a progress edge,
#: with the three per-page slots ④⑤⑥ filled from the arguments.
SHELL_R1, SHELL_R2, SHELL_PROG = 34, 36, 3
SHELL_H = SHELL_R1 + SHELL_R2 + SHELL_PROG          # 73
#: panels start here; every layout below is written against it
TOP = SHELL_H + 11                                   # 84


def nav_glyph(x, y, kind, on=False):
    """One 24 px page icon — the same four marks the strip carries."""
    rect(x, y, 24, 24, "chip-on" if on else "none", rx=5)
    cx, cy = x + 12, y + 12
    g = "navg-on" if on else "navg"
    if kind == "pulse_design":
        add(f'<path d="M{cx-7:.1f} {cy+4:.1f}L{cx-2:.1f} {cy-4:.1f}'
            f'L{cx+2:.1f} {cy-4:.1f}L{cx+7:.1f} {cy+4:.1f}" class="{g}"/>')
    elif kind == "model":
        add(f'<path d="M{cx-7:.1f} {cy-5:.1f}C{cx-2:.1f} {cy-5:.1f} {cx:.1f} {cy+5:.1f}'
            f' {cx+7:.1f} {cy+5:.1f}" class="{g}"/>')
    elif kind == "analysis":
        add(f'<path d="M{cx-7:.1f} {cy+3:.1f}Q{cx:.1f} {cy-7:.1f} {cx+7:.1f} {cy+2:.1f}"'
            f' class="{g}"/>')
    elif kind == "data":
        add(f'<path d="M{cx-6:.1f} {cy-6:.1f}v12M{cx-6:.1f} {cy-6:.1f}h5'
            f'M{cx-6:.1f} {cy:.1f}h5M{cx-6:.1f} {cy+6:.1f}h5" class="{g}"/>')
    elif kind == "theme":
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" class="{g}"/>')
        add(f'<path d="M{cx:.1f} {cy-6:.1f}a6 6 0 0 1 0 12z" class="{g}f"/>')


def shell_header(page, title, sub, state, *, exit_label=None, badges=(),
                 progress=None):
    """The shared strip: ①②③ from the page table, ④⑤⑥ from this page."""
    rect(0, 0, W, SHELL_H, "panel", rx=0)
    y2 = SHELL_R1
    add(f'<line x1="0" y1="{y2}" x2="{W}" y2="{y2}" class="sep"/>')

    # --- row 1: identity, the notice, and where else you can go -------------
    rect(14, 6, 22, 22, "mark", rx=5)
    text(25, 21, "Fy", "markt", 10.5, "middle", weight="700")
    text(44, 22, title, "head-t", 13, weight="700")
    text(48 + tw(title, 13), 22, sub, "mut", 9.5)
    pill = "仅限内部测试"
    pw = tw(pill, 9.5) + 22
    rect(W / 2 - pw / 2, 7, pw, 20, "stale", rx=10)
    text(W / 2, 21, pill, "stalet", 9.5, "middle", weight="700")
    x = W - 14 - 24
    nav_glyph(x, 5, "theme")
    x -= 8
    add(f'<line x1="{x}" y1="9" x2="{x}" y2="25" class="sep"/>')
    for k in reversed(["pulse_design", "model", "analysis", "data"]):
        x -= 27
        nav_glyph(x, 5, k, on=(k == page))

    # --- row 2: ④ input · ⑤ run state · ⑥ exit ------------------------------
    ty = y2 + 23
    text(14, ty, "装置", "mut", 10)
    bx = 14 + tw("装置", 10) + 8
    dw = tw("EAST ▾", 10) + 26
    rect(bx, y2 + 8, dw, 21, "input", rx=4)
    text(bx + 10, ty, "EAST ▾", "lbl", 10)
    bx += dw + 8
    for lab in ("导入", "导出"):
        w = tw(lab, 10) + 20
        rect(bx, y2 + 8, w, 21, "btn", rx=4)
        text(bx + w / 2, ty, lab, "lbl", 10, "middle")
        bx += w + 6
    add(f'<circle cx="{bx + 12:.1f}" cy="{y2 + 18:.1f}" r="4" class="dot-run"/>')
    text(bx + 22, ty, state, "mut", 10)
    #: ★the two page-state badges keep their place — they are content, not
    #: decoration: 「平顶 PF 随状态更新」 is D-6 and 「响应矩阵已漂移」 is D-7,
    #: and they are exactly the kind of thing ⑤ is for.
    rx_ = W - 14
    if exit_label:
        ew = tw(exit_label, 10) + 22
        rect(rx_ - ew, y2 + 8, ew, 21, "btn-accent", rx=4)
        text(rx_ - ew / 2, ty, exit_label, "acc-t", 10, "middle")
        rx_ -= ew + 10
    for b, cls, tcls in reversed(badges):
        bw = tw(b, 9.5) + 18
        rect(rx_ - bw, y2 + 9, bw, 19, cls, rx=9)
        text(rx_ - bw / 2, ty - 0.5, b, tcls, 9.5, "middle")
        rx_ -= bw + 8

    # --- the progress edge ---------------------------------------------------
    py = y2 + SHELL_R2
    rect(0, py, W, SHELL_PROG, "prog-bg", rx=0)
    if progress:
        rect(0, py, W * progress, SHELL_PROG, "prog", rx=0)


def header():
    shell_header(
        "pulse_design", "放电设计", "一份脚本 · 三种时间观：配置 · 设计 · 仿真",
        "设计 · 整条脉冲已存在 · 播放头 t = 3.20 s",
        exit_label="交给建模场景", progress=None,
        badges=[("平顶 PF：随等离子体状态更新 · LCFS 锁定", "badge-ok", "ok-t"),
                ("响应矩阵：β_p 漂移 12 %，建议重线性化", "stale", "stalet")])


def phase_bar(ax, y, h, *, labels=True):
    """The four-phase ribbon every time axis on the page shares."""
    for i, (a, b, name) in enumerate(PHASES):
        x0, x1 = ax.px(a), ax.px(b)
        rect(x0, y, x1 - x0, h, f"ph{i}", rx=0)
        if labels:
            text((x0 + x1) / 2, y + h - 4, name, "pht", 9.5, "middle")


def p_ip(x, y, w, h):
    """① 相位与 Ip 波形 — the trapezoid whose corners are dragged."""
    top = panel(x, y, w, h, "相位与 Ip 波形", 1, "内核 zerod_waveform")
    ax = Axes(x + 40, top + 22, w - 56, 66, (T_BD, T_END), (0, 460))
    phase_bar(ax, top + 8, 12, labels=False)
    ax.plot(IP, "ip")
    for t, v in IP:
        handle(ax.px(t), ax.py(v))
    ax.vline(T_NOW)
    text(x + 35, top + 20, "kA", "mut", 8.5, "end")
    text(x + 35, ax.py(IP_FLAT) + 3, f"{IP_FLAT:.0f}", "mut", 8.5, "end")
    text(x + 35, ax.py(0) + 3, "0", "mut", 8.5, "end")
    text(ax.px(0.55), top + 104, "dIp/dt 0.4 MA/s", "mut", 9, "middle")
    text(ax.px(9.0), top + 104, "−0.2 MA/s", "mut", 9, "middle")
    fw = (w - 28 - 3 * 6) / 4
    for i, (lab, val) in enumerate((("击穿", "0.00"), ("斜坡结束", "1.00"),
                                    ("平顶结束", "8.00"), ("放电结束", "10.00"))):
        field(x + 14 + i * (fw + 6), top + 112, fw, lab + " [s]", val)


def p_lcfs(x, y, w, h):
    """② LCFS 轨迹 — the waypoint list, and the shapes it interpolates."""
    top = panel(x, y, w, h, "LCFS 位形轨迹", 2, "波点 5")
    rows = (("0.30", "限制器", "0.20", "1.05", "0.10"),
            ("1.00", "限制器", "0.38", "1.35", "0.25"),
            ("2.20", "双零", "0.45", "1.65", "0.45"),
            ("8.00", "双零", "0.45", "1.65", "0.45"),
            ("9.60", "限制器", "0.26", "1.20", "0.15"))
    cols = (14, 52, 104, 146, 186)
    hdr = ("t [s]", "边界", "a [m]", "κ", "δ̄")
    for cx, hlab in zip(cols, hdr):
        text(x + cx, top + 14, hlab, "mut", 9)
    for i, r in enumerate(rows):
        ry = top + 30 + i * 17
        if abs(float(r[0]) - T_NOW) < 1.3:
            rect(x + 10, ry - 11, w - 96, 16, "rowsel", rx=3)
        for cx, v in zip(cols, r):
            text(x + cx, ry, v, "lbl", 9.5)
    # the shapes themselves, nested, at the right
    cx, cy, sc = x + w - 46, top + 62, 34.0
    for a, k, d, cls in ((0.20, 1.05, 0.10, "shape-a"), (0.38, 1.35, 0.25, "shape-a"),
                         (0.45, 1.65, 0.45, "shape-b")):
        pts = []
        for i in range(65):
            th = 2 * math.pi * i / 64
            pts.append((cx + sc * a / 0.45 * math.cos(th + d * math.sin(th)),
                        cy - sc * a / 0.45 * k / 1.65 * 1.35 * math.sin(th)))
        poly(pts + [pts[0]], cls)
    text(cx, top + 118, "轨迹插值", "mut", 9, "middle")
    text(x + 14, top + 130, "加一个时刻 +   ·   逐波点为静态反解的目标", "mut", 9)


def p_heat(x, y, w, h):
    """③ 辅助加热波形 — the interactive one; drag re-integrates 0-D live."""
    top = panel(x, y, w, h, "辅助加热波形", 3, "拖动 → 0-D 即时")
    lane = (h - 46) / len(HEATING)
    for i, (name, unit, wins) in enumerate(HEATING):
        ly = top + 6 + i * lane
        ax = Axes(x + 44, ly, w - 60, lane - 14, (T_BD, T_END), (0, 7.0))
        pts = [(T_BD, 0.0)]
        for t in [T_BD + j * (T_END - T_BD) / 240 for j in range(241)]:
            pts.append((t, sum(p for a, b, p in wins if a <= t < b)))
        ax.plot(pts, "heat")
        for a, b, p in wins:
            handle(ax.px(a), ax.py(p), 3.4)
            handle(ax.px(b), ax.py(p), 3.4)
        ax.vline(T_NOW)
        text(x + 40, ly + (lane - 14) / 2 + 3, name, "lbl", 10, "end")
        text(x + w - 14, ly + 10, f"{sum(p for _, _, p in wins):.1f} {unit}",
             "mut", 9, "end")
    text(x + 14, y + h - 10,
         "0-D 全程重积分 1–3 ms → 走廊随拖动重画；平衡与剖面待松手", "mut", 9)


def p_equil(x, y, w, h):
    """④ 当前时间片 · 平衡截面."""
    top = panel(x, y, w, h, f"当前时间片 · 平衡截面   t = {T_NOW:.2f} s", 4,
                "已解 · 1.2 s", "badge-ok")
    cx, cy = x + w / 2 - 30, top + (h - 40) / 2 - 8
    sc = (h - 70) / 2 / 1.75
    # vessel + limiter
    add(f'<path d="M {cx - 1.30 * sc:.1f} {cy - 1.55 * sc:.1f} '
        f'q {2.6 * sc:.1f} {-0.35 * sc:.1f} {2.6 * sc:.1f} {0.0:.1f} '
        f'l 0 {3.1 * sc:.1f} q {-2.6 * sc:.1f} {0.35 * sc:.1f} '
        f'{-2.6 * sc:.1f} 0 z" class="vessel"/>')
    add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{1.12 * sc:.1f}" '
        f'ry="{1.42 * sc:.1f}" class="limiter"/>')
    # coils
    for dx, dy, hot in ((-1.50, -1.28, 1), (-1.50, -0.42, 0), (-1.50, 0.42, 0),
                        (-1.50, 1.28, 1), (1.50, -1.28, 1), (1.50, -0.42, 0),
                        (1.50, 0.42, 0), (1.50, 1.28, 1),
                        (-0.98, 1.62, 1), (0.98, 1.62, 0)):
        rect(cx + dx * sc - 8, cy + dy * sc - 6, 16, 12,
             "coil-hot" if hot else "coil", rx=2)
    # flux surfaces + the two boundaries
    def miller(a, k, d, n=97):
        p = []
        for i in range(n):
            th = 2 * math.pi * i / (n - 1)
            p.append((cx + sc * a * math.cos(th + d * math.sin(th)),
                      cy - sc * a * k * math.sin(th)))
        return p
    for f in (0.25, 0.5, 0.75):
        poly(miller(0.92 * f, 1.62, 0.42 * f), "flux")
    poly(miller(0.92, 1.62, 0.42), "lcfs")
    poly([(px + 3.5, py + 2.0) for px, py in miller(0.95, 1.60, 0.40)],
         "lcfs-target")
    handle(cx + 3, cy - 0.10 * sc, 2.6, "axis")
    xr, xz = cx - 0.38 * sc, cy + 1.49 * sc
    add(f'<path d="M {xr - 5:.1f} {xz:.1f} l 10 0 M {xr:.1f} {xz - 5:.1f} '
        f'l 0 10" class="xpt"/>')
    text(xr + 8, xz + 13, "X 点", "mut", 9)
    # legend
    lx, ly = x + w - 104, top + 16
    for lab, cls in (("目标 LCFS", "lcfs-target"), ("实现 LCFS", "lcfs"),
                     ("PF 线圈（着色=电流）", "coil-hot"), ("限制器", "limiter")):
        line(lx, ly, lx + 16, ly, cls)
        text(lx + 22, ly + 3.5, lab, "mut", 9)
        ly += 15
    text(x + 14, y + h - 10,
         "本片由 PF 波形正解得到；形状误差 RMS 8.6 mm（容差 20 mm）", "mut", 9)


def p_prof(x, y, w, h):
    """⑤ 当前时间片 · 剖面."""
    top = panel(x, y, w, h, "当前时间片 · 剖面", 5, "0-D 规定剖面")
    cellw, cellh = (w - 36) / 2, (h - 82) / 2
    specs = (("n_e [10¹⁹ m⁻³]", lambda r: 4.0 * (1 - r ** 2) ** 1.0 + 0.3),
             ("T_e , T_i [keV]", lambda r: 3.0 * (1 - r ** 2) ** 1.5 + 0.1),
             ("q", lambda r: 0.95 + 3.6 * r ** 2),
             ("j_φ [MA/m²]", lambda r: 1.15 * (1 - r ** 2) ** 1.6 + 0.02))
    for i, (name, fn) in enumerate(specs):
        px = x + 14 + (i % 2) * (cellw + 8)
        py = top + 14 + (i // 2) * (cellh + 18)
        vals = [fn(j / 40) for j in range(41)]
        ax = Axes(px, py, cellw, cellh, (0, 1), (0, max(vals) * 1.15))
        ax.plot([(j / 40, v) for j, v in enumerate(vals)], "prof")
        if i == 1:
            ax.plot([(j / 40, 0.9 * v) for j, v in enumerate(vals)], "prof2")
        text(px + 2, py - 3, name, "mut", 9)
    text(x + 14, y + h - 10, "ρ = √(Φ/Φ_b) ·  剖面随 0-D 峰化参数与该片标量重建",
         "mut", 9)


def p_pf(x, y, w, h):
    """⑥ PF 通道波形 — currents and voltages, with the declared limits."""
    top = panel(x, y, w, h, "PF 通道波形", 6, "斜坡前馈 · 平顶随状态")
    hh = (h - 86) / 2
    ax = Axes(x + 42, top + 16, w - 58, hh, (T_BD, T_END), (-14, 14))
    phase_bar(ax, top + 4, 10, labels=False)
    rect(ax.x, ax.py(11), ax.w, ax.py(-11) - ax.py(11), "limband", rx=0)
    chans = ((1.0, 9.4, 6.2, "c1"), (-0.6, -7.5, -5.0, "c2"),
             (0.4, 5.0, 2.2, "c3"), (-0.2, -3.0, -1.2, "c4"),
             (0.8, 12.6, 8.0, "c5"))
    #: ★平顶段不是一段常数：LCFS 被锁住，而 β_p / l_i 在动，所以持住同一条边界
    #: 所需的电流跟着状态走（D-6）。图上因此画两条——虚影是加热改变之前的状态
    #: 解出的同一通道，实线是现在这个状态的；两者的 LCFS 是同一条。
    def i_of(t, a, b, c, *, frozen=False):
        base = ramp(t, [(T_BD, a), (T_RAMP, b), (2.2, c * 1.05),
                        (T_FLAT, c), (T_END, a * 0.4)])
        if T_RAMP < t < T_END:
            #: 平顶上持住同一条 LCFS 所需的电流是 β_p / l_i 的函数——加热一变，
            #: 这条线就在原地抬起来，而边界一动不动
            bn = bn_of(2.9) if frozen else bn_of(min(t, T_FLAT))
            wgt = (min(1.0, (t - T_RAMP) / 0.6)
                   * min(1.0, max(0.0, (T_END - t) / 0.9)))
            base *= 1.0 + 0.45 * (bn - 1.0) * wgt
        return base
    for i0, ipk, iflat, cls in chans:
        ax.plot(sample(lambda t, a=i0, b=ipk, c=iflat: i_of(t, a, b, c), 160),
                cls)
    for i0, ipk, iflat, cls in chans[:2]:
        ghost = [(t, v) for t, v in
                 sample(lambda t, a=i0, b=ipk, c=iflat:
                        i_of(t, a, b, c, frozen=True), 160) if t >= 2.7]
        ax.plot(ghost, "ghost")
    text(x + 38, top + 24, "kA·匝", "mut", 9, "end")
    text(ax.px(T_END) - 4, ax.py(11) - 3, "声明限值 ±11", "warn-t", 9, "end")
    text(ax.px(4.6), ax.py(13.2), "虚影＝加热改变前的同一通道（LCFS 同一条）",
         "mut", 8.6, "middle")
    ax.vline(T_NOW)
    # 两个区制的括注：斜坡是前馈电压，平顶是等 LCFS 的反馈轨迹
    by = top + 16 + hh + 8
    for t0, t1, s, cls in ((T_BD, T_RAMP, "前馈", "reg-ff"),
                           (T_RAMP, T_FLAT, "平顶：等 LCFS 反馈轨迹 I(β_p, l_i)",
                            "reg-fb"),
                           (T_FLAT, T_END, "前馈", "reg-ff")):
        line(ax.px(t0) + 1, by, ax.px(t1) - 1, by, cls)
        text((ax.px(t0) + ax.px(t1)) / 2, by - 3, s, "mut", 8.6, "middle")
    ax2 = Axes(x + 42, top + 22 + hh + 16, w - 58, hh, (T_BD, T_END), (-24, 24))
    for i, (i0, ipk, iflat, cls) in enumerate(chans):
        pts = sample(lambda t, b=ipk: ramp(
            t, [(T_BD, 0.0), (0.15, 2.1 * b), (T_RAMP, 0.35 * b),
                (1.4, 0.10 * b), (T_FLAT, 0.06 * b), (8.4, -0.9 * b),
                (T_END, -0.15 * b)]), 120)
        ax2.plot(pts, cls)
    ax2.vline(T_NOW)
    text(x + 38, top + 30 + hh + 16, "V/匝", "mut", 9, "end")
    text(x + 14, y + h - 10,
         "越限逐通道报告，不静默裁剪（FR-PULSE-005）", "mut", 9)


def p_table(x, y, w, h):
    """⑦ 逐通道用量."""
    top = panel(x, y, w, h, "逐通道用量与判定", 7)
    cols = (14, 96, 176, 258, 340)
    hdr = ("通道", "|I|max [kA·匝]", "|V|max [V/匝]", "所声明限值", "判定")
    for cx, s in zip(cols, hdr):
        text(x + cx, top + 15, s, "mut", 9)
    rows = (("PF1", "9.4", "19.7", "11 · 24", "✓", "ok"),
            ("PF2", "7.5", "15.8", "11 · 24", "✓", "ok"),
            ("PF3", "5.0", "10.5", "11 · 24", "✓", "ok"),
            ("PF5", "12.6", "26.4", "11 · 24", "越限 I,V", "bad"),
            ("OH", "18.2", "31.0", "未声明", "限值未声明", "unk"))
    for i, (a, b, c, d, e, kind) in enumerate(rows):
        ry = top + 33 + i * 19
        if kind != "ok":
            rect(x + 10, ry - 12, w - 20, 17,
                 "rowbad" if kind == "bad" else "rowunk", rx=3)
        for cx, s in zip(cols, (a, b, c, d)):
            text(x + cx, ry, s, "lbl", 9.5)
        text(x + cols[4], ry, e,
             "bad-t" if kind == "bad" else ("warn-t" if kind == "unk" else "ok-t"),
             9.5)
    text(x + 14, y + h - 24,
         "峰值取自当前状态下的整条轨迹——平顶段随 β_p、l_i 变而重算", "mut", 9)
    text(x + 14, y + h - 10,
         "限值来自装置描述；缺表时页面写明「上限是你给的一个统一值」", "mut", 9)


def corridor(x, y, w, h):
    """⑧ 滚动时序走廊 — the 0-D signals, and the play-head everything shares."""
    top = panel(x, y, w, h, "0-D 时序走廊（滚动）", 8,
                f"t = {T_NOW:.2f} s · 播放 ×1")
    lanes = (
        ("Ip [kA] / 消耗磁通 [Wb]", ((sample(ip_of), "ip", (0, 460)),
                                     (sample(lambda t: flux_of(t) * 460), "flux2", (0, 460)))),
        ("n_e0 [10¹⁹] / f_GW", ((sample(ne_of), "ne", (0, 6.0)),
                                (sample(lambda t: 4.0 * gw_of(t)), "gw",
                                 (0, 6.0)))),
        ("P [MW]: aux · ohm · rad", ((sample(paux_of, 240), "heat", (0, 8.0)),
                                     (sample(pohm_of), "pohm", (0, 8.0)),
                                     (sample(prad_of), "prad", (0, 8.0)))),
        ("q95 · β_N · l_i(3)", ((sample(q95_of), "q95", (0, 15.0)),
                                (sample(lambda t: bn_of(t) * 5, ), "bn", (0, 15.0)),
                                (sample(lambda t: li_of(t) * 5), "li", (0, 15.0)))),
    )
    lh = (h - 96) / len(lanes)
    axes = []
    for i, (name, series) in enumerate(lanes):
        ly = top + 18 + i * lh
        ax = Axes(x + 128, ly, w - 150, lh - 8, (T_BD, T_END), (0, 1))
        axes.append(ax)
        if i == 0:
            phase_bar(ax, top + 6, 14)
        for pts, cls, (v0, v1) in series:
            ax.y0, ax.y1 = v0, v1
            ax.plot(pts, cls)
        text(x + 122, ly + (lh - 8) / 2 + 3, name, "lbl", 9.5, "end")
        ax.vline(T_NOW)
    ax = axes[-1]
    for t in (0.0, 2.0, 4.0, 6.0, 8.0, 10.0):
        text(ax.px(t), ax.y + ax.h + 12, f"{t:.0f}", "mut", 9, "middle")
    text(ax.px(6.6), ax.y + ax.h + 24, "t [s]", "mut", 9, "middle")
    # solved-slice ticks: which instants actually carry an equilibrium
    for t in (0.30, 1.00, 2.20, T_NOW, 5.00, 8.00, 9.60):
        cls = "tick-now" if abs(t - T_NOW) < 1e-9 else "tick"
        line(ax.px(t), ax.y + ax.h + 16, ax.px(t), ax.y + ax.h + 22, cls)
    text(x + 122, ax.y + ax.h + 22, "已解片", "mut", 9, "end")
    # transport controls
    bx = x + 14
    for s in ("⏮", "⏯", "⏭"):
        rect(bx, y + h - 30, 26, 20, "btn", rx=4)
        text(bx + 13, y + h - 16, s, "lbl", 11, "middle")
        bx += 30
    bx += 6
    for s in ("×0.25", "×1", "×4", "循环"):
        bx += chip(bx, y + h - 30, s, "chip" if s != "×1" else "chip-on") + 6
    lx = x + w - 330
    for lab, cls in (("已解片", "tick"), ("插值片（未解，标注）", "tick-i"),
                     ("过期（输入已变）", "stale-line")):
        line(lx, y + h - 20, lx + 14, y + h - 20, cls)
        text(lx + 20, y + h - 16.5, lab, "mut", 9)
        lx += tw(lab, 9) + 42


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #
#: ★**Light only** (2026-09-01 用户裁定).  These drawings used to carry a
#: `prefers-color-scheme: dark` block and therefore came out dark on a
#: dark-themed machine.  The app is three-state on purpose, and the reason
#: given there is exactly why a FIGURE must not be: these get screenshotted
#: into slides and printed, and a drawing whose ground follows whoever renders
#: it exports differently on two machines.  A page can offer the reader a
#: switch; a picture has none.  Same ruling as `tools/make-desktop-preview.py`
#: (`FYL-DESIGN-11` V-14) — the two generators now agree.
STYLE = """
:root {
  --bg:#f4f5f7; --panel:#ffffff; --fg:#1c2128; --muted:#666f7a; --grid:#d8dce2;
  --line:#e3e6ea; --accent:#1668c8; --lcfs:#d0342c; --alt:#10897a;
  --coil:#8a53c4; --wall:#5a6270; --flux:#9aa6b8; --warn:#a75909;
  --head:#eceff3; --sel:#e7f0fb; --bad:#c0392b; --ok:#10897a;
}
text { font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,
       -apple-system,'Segoe UI',sans-serif; fill:var(--fg); }
.bg { fill:var(--bg); }
.panel { fill:var(--panel); stroke:var(--line); stroke-width:1; }
.head { fill:var(--head); stroke:var(--line); }
.head-t { fill:var(--fg); }
.title { fill:var(--fg); }
.lbl { fill:var(--fg); }
.mut { fill:var(--muted); }
.sep { stroke:var(--line); stroke-width:1; }
.grid { stroke:var(--grid); stroke-width:1; }
.axes { fill:none; stroke:var(--grid); stroke-width:1; }
.input { fill:none; stroke:var(--grid); stroke-width:1; }
.chip { fill:none; stroke:var(--grid); stroke-width:1; }
.chip-on { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.chipt { fill:var(--muted); }
.btn { fill:none; stroke:var(--grid); stroke-width:1; }
.call { fill:var(--accent); }
.callt { fill:#ffffff; font-weight:600; }
.badge { fill:none; stroke:var(--grid); }
.badge-ok { fill:none; stroke:var(--ok); }
.badget { fill:var(--muted); }
.stale { fill:none; stroke:var(--warn); stroke-width:1.2; stroke-dasharray:4 3; }
.stalet { fill:var(--warn); }
.stale-line { stroke:var(--warn); stroke-width:2; stroke-dasharray:4 3; }
.handle { fill:var(--panel); stroke:var(--accent); stroke-width:1.6; }
.axis { fill:var(--lcfs); stroke:none; }
.playhead { stroke:var(--accent); stroke-width:1.2; stroke-dasharray:3 3; }
.ph0 { fill:var(--accent); opacity:.10; }
.ph1 { fill:var(--alt); opacity:.12; }
.ph2 { fill:var(--warn); opacity:.10; }
.pht { fill:var(--muted); }
.rowsel { fill:var(--sel); }
.rowbad { fill:var(--bad); opacity:.10; }
.rowunk { fill:var(--warn); opacity:.10; }
.bad-t { fill:var(--bad); } .ok-t { fill:var(--ok); } .warn-t { fill:var(--warn); }
.mark { fill:var(--accent); }
.markt { fill:#ffffff; }
.none { fill:none; stroke:none; }
.navg { fill:none; stroke:var(--muted); stroke-width:1.5;
        stroke-linecap:round; stroke-linejoin:round; }
.navg-on { fill:none; stroke:var(--accent); stroke-width:1.7;
           stroke-linecap:round; stroke-linejoin:round; }
.navgf { fill:var(--muted); stroke:none; }
.navg-onf { fill:var(--accent); stroke:none; }
.btn-accent { fill:none; stroke:var(--accent); stroke-width:1.1; }
.acc-t { fill:var(--accent); }
.dot-run { fill:var(--ok); }
.prog-bg { fill:var(--line); }
.prog { fill:var(--accent); }
.limband { fill:var(--alt); opacity:.07; }
.tick { stroke:var(--accent); stroke-width:2; }
.tick-i { stroke:var(--muted); stroke-width:2; stroke-dasharray:2 2; }
.tick-now { stroke:var(--lcfs); stroke-width:2.6; }
polyline { fill:none; stroke-linejoin:round; stroke-linecap:round; }
.ip { stroke:var(--accent); stroke-width:2; }
.flux2 { stroke:var(--warn); stroke-width:1.4; stroke-dasharray:5 3; }
.ne { stroke:var(--alt); stroke-width:1.8; }
.gw { stroke:var(--muted); stroke-width:1.2; stroke-dasharray:4 3; }
.heat { stroke:var(--lcfs); stroke-width:1.8; }
.pohm { stroke:var(--accent); stroke-width:1.4; }
.prad { stroke:var(--muted); stroke-width:1.4; }
.q95 { stroke:var(--accent); stroke-width:1.6; }
.bn { stroke:var(--lcfs); stroke-width:1.6; }
.li { stroke:var(--alt); stroke-width:1.4; stroke-dasharray:4 3; }
.prof { stroke:var(--accent); stroke-width:1.8; }
.prof2 { stroke:var(--lcfs); stroke-width:1.4; stroke-dasharray:4 3; }
.flux { stroke:var(--flux); stroke-width:1; }
.lcfs { stroke:var(--lcfs); stroke-width:2; }
.lcfs-target { stroke:var(--muted); stroke-width:1.4; stroke-dasharray:5 4; }
.vessel { fill:none; stroke:var(--wall); stroke-width:1.6; }
.limiter { fill:none; stroke:var(--wall); stroke-width:1; stroke-dasharray:3 3; }
.coil { fill:var(--coil); opacity:.35; stroke:var(--coil); }
.coil-hot { fill:var(--coil); opacity:.85; stroke:var(--coil); }
.xpt { stroke:var(--lcfs); stroke-width:1.6; }
.c1 { stroke:var(--accent); stroke-width:1.5; }
.c2 { stroke:var(--lcfs); stroke-width:1.5; }
.c3 { stroke:var(--alt); stroke-width:1.5; }
.c4 { stroke:var(--coil); stroke-width:1.5; }
.c5 { stroke:var(--warn); stroke-width:1.8; }
.ghost { stroke:var(--muted); stroke-width:1.2; stroke-dasharray:3 3; opacity:.8; }
.reg-ff { stroke:var(--muted); stroke-width:1.4; }
.reg-fb { stroke:var(--alt); stroke-width:2; }
.track { stroke:var(--grid); stroke-width:4; stroke-linecap:round; }
.trackon { stroke:var(--accent); stroke-width:4; stroke-linecap:round; }
.trail1 { stroke:var(--accent); stroke-width:1.2; opacity:.42; }
.trail2 { stroke:var(--accent); stroke-width:1.2; opacity:.20; }
.wth { stroke:var(--warn); stroke-width:1.5; }
.future { fill:var(--grid); opacity:.28; }
.future-l { stroke:var(--grid); stroke-width:5; }
.nowedge { stroke:var(--lcfs); stroke-width:2; }
.sliderline { stroke:var(--warn); stroke-width:1.4; stroke-dasharray:4 3; }
.seg { fill:none; stroke:var(--grid); stroke-width:1; }
.seg-on { fill:var(--sel); stroke:var(--accent); stroke-width:1.4; }
.tag { fill:none; stroke:var(--grid); stroke-width:1; }
.tagt { fill:var(--muted); }
.card-back { fill:none; stroke:var(--grid); stroke-width:1; stroke-dasharray:3 3; }
.card-front { fill:var(--sel); stroke:var(--accent); stroke-width:1.2; }
.runsw { fill:var(--ok); opacity:.85; }
.runt { fill:#ffffff; }
.runknob { fill:#ffffff; stroke:var(--ok); stroke-width:1.6; }
.ph-on { fill:var(--sel); stroke:var(--accent); stroke-width:1.2; }
.ph-off { fill:none; stroke:var(--grid); stroke-width:1; }
.ip-open { stroke:var(--accent); stroke-width:1.6; stroke-dasharray:5 4; opacity:.7; }
.target { stroke:var(--muted); stroke-width:1.3; stroke-dasharray:5 3; }
"""


# --------------------------------------------------------------------------- #
# 图二：交互仿真模式 (interactive simulation)
#
# ★Why a SECOND figure and not a second tab drawn on the first.  The two modes
# differ in what the time axis MEANS — in design mode the whole pulse exists
# and the play-head reads it; in simulation mode only the past exists and the
# right-hand edge is now.  One drawing showing both would have to lie about
# one of them.
# --------------------------------------------------------------------------- #
T_SIM = 4.35          # 墙上的「现在」
SIM_WIN = 4.0         # 走廊窗口 [s]
T_SLIDER = 4.05       # 用户刚推过滑块的时刻
T_EQ_LAST = 4.20      # 上一次真解平衡的时刻
#: (名字, 单位, 推之前 [MW], 现在 [MW], 滑块行程占比)
SIM_DRIVE = [("NBI 中性束", "MW", 2.0, 4.5, 0.45),
             ("ECRH 电子回旋", "MW", 1.0, 1.0, 0.17),
             ("LHCD 低杂波驱动", "MW", 0.5, 1.5, 0.25),
             ("充气 Γ", "10²¹/s", 1.2, 1.2, 0.30)]


def paux_sim(t):
    return sum((now if t >= T_SLIDER else was)
               for _, _, was, now, _ in SIM_DRIVE[:3])


def w_sim(t):
    """储能：滑块推上去之后爬得更快（示意）。"""
    base = ramp(t, [(T_BD, 0.0), (T_RAMP, 0.10), (2.5, 0.17), (T_SIM + 1, 0.19)])
    if t > T_SLIDER:
        base += 0.055 * (1 - math.exp(-(t - T_SLIDER) / 0.35))
    return base


def ich_sim(t, base, resp):
    """平顶通道电流：LCFS 锁定，所以滑块之后它自己动（D-6）。"""
    v = base + 0.04 * base * math.sin(t)
    if t > T_SLIDER:
        v += resp * (1 - math.exp(-(t - T_SLIDER) / 0.30))
    return v


def slider(x, y, w, label, value, frac, *, changed=False):
    """One drive control.  ``frac`` is where the knob sits on its track."""
    text(x, y, label, "lbl", 10)
    text(x + w, y, value, "warn-t" if changed else "mut", 10, "end")
    line(x, y + 12, x + w, y + 12, "track")
    line(x, y + 12, x + w * frac, y + 12, "trackon")
    handle(x + w * frac, y + 12, 5.5)


def sim_header():
    shell_header(
        "pulse_design", "放电设计", "一份脚本 · 三种时间观：配置 · 设计 · 仿真",
        "仿真 · 只有过去 · 现在 t = 4.15 s · 实时 0.8×",
        exit_label="交给建模场景", progress=0.415,
        badges=[("0-D 保真度档 · 平衡每 5 步真解", "badge-ok", "ok-t")])


def s_console(x, y, w, h):
    """① 驱动控制台 — the run switch, the Ip target, the shape, the sliders.

    ★The switch is the panel's first element on purpose: in simulation mode it
    is the switch, not a schedule, that decides which phase the discharge is
    in (D-16).
    """
    top = panel(x, y, w, h, "驱动控制台", 1, "滑块 → 从现在起生效")
    yy = top + 10
    #: 启动开关：开＝放电开始，关＝进入受控下降沿（不是急停）
    rect(x + 14, yy, 98, 32, "runsw", rx=16)
    text(x + 30, yy + 21, "启动", "runt", 12, weight="600")
    handle(x + 95, yy + 16, 12, "runknob")
    text(x + 124, yy + 14, "运行中 · 平顶（稳态）", "lbl", 10.5)
    text(x + 124, yy + 28, "关 → 受控下降沿，不是急停", "mut", 9)
    yy += 44
    states = ("待机", "上升", "平顶", "下降", "结束")
    sw = (w - 28) / len(states)
    for i, st in enumerate(states):
        on = st == "平顶"
        rect(x + 14 + i * sw, yy, sw - 4, 20, "ph-on" if on else "ph-off", rx=4)
        text(x + 14 + i * sw + (sw - 4) / 2, yy + 14, st,
             "lbl" if on else "mut", 9.5, "middle")
    text(x + 14, yy + 33, "相位是开关与斜坡率的结果，不是预先给定的时刻（D-16）",
         "mut", 9)
    yy += 50
    #: ★保真度不是模式：同一份脚本、同一条走廊，换的只是推进状态的那个方程
    #: （D-22）。它与相位机分开画，因为它们换的不是同一件事。
    text(x + 14, yy + 4, "保真度", "lbl", 10)
    cx_ = x + 14 + tw("保真度", 10) + 10
    #: 图上画的是 1.5-D 档——它是 D-22 之后这一页的完整形态；0-D 档在它旁边，
    #: 下面那句说明「切过去会少掉什么」。
    for name, on, sub in (("0-D 集总", False, "整条 1–3 ms"),
                          ("1.5-D 输运", True, "每步 ≈12 ms")):
        wsw = tw(name, 9.6) + 20
        rect(cx_, yy - 8, wsw, 22, "chip-on" if on else "chip", rx=6)
        text(cx_ + wsw / 2, yy + 7, name, "lbl" if on else "chipt", 9.6,
             "middle")
        text(cx_ + wsw / 2, yy + 22, sub, "mut", 8.2, "middle")
        cx_ += wsw + 6
    text(x + 14, yy + 38, "换的是推进状态的那个方程，不是时间轴的含义（D-22）；",
         "mut", 9)
    text(x + 14, yy + 50, "0-D 档没有剖面、χ、台基与沉积——那几块空着并说明。",
         "mut", 9)
    yy += 66
    #: Ip 目标：过去是实现值，未来只画到「若现在关」为止——它没有预定的终点
    text(x + 14, yy + 8, "Ip 目标 [kA]", "lbl", 10)
    text(x + w - 14, yy + 8, "400 · +0.4 / −0.2 MA/s", "mut", 9, "end")
    ax = Axes(x + 14, yy + 14, w - 28, 52, (0, 8.4), (0, 470))
    ax.plot([(0, 0), (1.0, 400), (T_SIM, 400)], "ip")
    ax.plot([(T_SIM, 400), (6.6, 400)], "ip-open")
    ax.plot([(6.6, 400), (8.4, 0)], "ip-open")
    for t, v in ((1.0, 400), (T_SIM, 400)):
        handle(ax.px(t), ax.py(v), 4)
    ax.vline(T_SIM, "nowedge")
    text(ax.px(7.2), ax.py(250), "关 → 由此下降", "mut", 8.6, "middle")
    yy += 86
    #: LCFS 目标：仿真里它是随时可改的目标，改完再开机是最常见的用法
    text(x + 14, yy, "LCFS 目标", "lbl", 10)
    text(x + w - 14, yy, "双零 · 拖动即改目标", "mut", 9, "end")
    fw = (w - 28 - 2 * 6) / 3
    for i, (lab, val) in enumerate((("a [m]", "0.45"), ("κ", "1.65"),
                                    ("δ̄", "0.45"))):
        field(x + 14 + i * (fw + 6), yy + 4, fw, lab, val)
    yy += 48
    for name, unit, was, now, frac in SIM_DRIVE:
        changed = abs(now - was) > 1e-9
        val = f"{now:.1f} {unit}" + (f"  ← {was:.1f}" if changed else "")
        slider(x + 14, yy, w - 28, name, val, frac, changed=changed)
        yy += 36
    yy += 4
    for lab, on in (("形状反馈：等 LCFS", True),
                    ("按设计的前馈电压驱动", False)):
        rect(x + 14, yy - 9, 26, 14, "chip-on" if on else "chip", rx=7)
        handle(x + (33 if on else 21), yy - 2, 5.0)
        text(x + 48, yy, lab, "lbl", 10)
        yy += 22
    #: 这一次运行的账：产物是记录，不是设计（D-11）
    yy += 10
    line(x + 14, yy, x + w - 14, yy, "sep")
    text(x + 14, yy + 18, "本次运行", "title", 11, weight="600")
    text(x + w - 14, yy + 18, "362 步 · 平衡真解 18 次 · 产物＝运行记录",
         "mut", 9.5, "end")
    text(x + 14, y + h - 26,
         f"滑块改动自 t = {T_SLIDER:.2f} s 起生效——过去不重算（D-12）；",
         "mut", 9)
    text(x + 14, y + h - 12,
         "无操作则定态维持，能维持多久由磁通预算说（D-17）。", "mut", 9)


def s_equil(x, y, w, h):
    """② 磁面演化 — solved on its own cadence, and it says so."""
    top = panel(x, y, w, h, "磁面演化（当前状态）", 2,
                f"上次重解 t = {T_EQ_LAST:.2f} s", "badge-ok")
    cx, cy = x + w / 2, top + (h - 150) / 2
    sc = (h - 210) / 2 / 1.72
    add(f'<path d="M {cx - 1.30 * sc:.1f} {cy - 1.55 * sc:.1f} '
        f'q {2.6 * sc:.1f} {-0.35 * sc:.1f} {2.6 * sc:.1f} 0 '
        f'l 0 {3.1 * sc:.1f} q {-2.6 * sc:.1f} {0.35 * sc:.1f} '
        f'{-2.6 * sc:.1f} 0 z" class="vessel"/>')
    for dx, dy, hot in ((-1.50, -1.20, 1), (-1.50, 0.0, 0), (-1.50, 1.20, 1),
                        (1.50, -1.20, 1), (1.50, 0.0, 0), (1.50, 1.20, 1)):
        rect(cx + dx * sc - 8, cy + dy * sc - 6, 16, 12,
             "coil-hot" if hot else "coil", rx=2)

    def miller(a, k, d, n=97):
        return [(cx + sc * a * math.cos(2 * math.pi * i / (n - 1)
                                        + d * math.sin(2 * math.pi * i / (n - 1))),
                 cy - sc * a * k * math.sin(2 * math.pi * i / (n - 1)))
                for i in range(n)]
    for f in (0.3, 0.55, 0.78):
        poly(miller(0.84 * f, 1.60, 0.40 * f), "flux")
    poly(miller(0.82, 1.55, 0.36), "ghost")          # 0.5 s 之前的边界
    poly(miller(0.84, 1.62, 0.42), "lcfs")
    handle(cx + 4, cy - 0.08 * sc, 2.6, "axis")
    #: 状态快照 + 磁通余量：定态维持能撑多久，答案在这一行而不在直觉里
    sy = y + h - 140
    line(x + 14, sy, x + w - 14, sy, "sep")
    text(x + 14, sy + 18, "当前状态快照", "title", 11, weight="600")
    snap = (("β_p", "0.86", " ↑12 %"), ("l_i(3)", "0.94", ""),
            ("q95", "4.1", ""), ("f_GW", "0.62", ""),
            ("H₉₈", "1.05", " ↑"), ("形状误差", "9 mm", ""))
    for i, (k, v, d) in enumerate(snap):
        ry = sy + 38 + (i // 3) * 18
        rx = x + 14 + (i % 3) * (w - 28) / 3
        text(rx, ry, k, "mut", 9.5)
        text(rx + (w - 28) / 3 - 12, ry, v + d, "warn-t" if d else "lbl", 9.5,
             "end")
    text(x + 14, sy + 78, "★剩余磁通摆幅 3.2 Wb ≈ 定态还能维持 6.4 s——",
         "warn-t", 9)
    text(x + 14, sy + 92, "「不操作就不变」是模型的性质，不是机器的承诺",
         "warn-t", 9)
    text(x + 14, y + h - 26,
         "实线＝当前边界；虚影＝0.5 s 之前", "mut", 9)
    text(x + 14, y + h - 12,
         "★步间为面度规插值：磁面每 K 步才真解一次", "mut", 9)


def s_prof(x, y, w, h):
    """③ 剖面随时间 — with the trail that makes an evolution visible."""
    top = panel(x, y, w, h, "剖面随时间（1.5-D 三通道推进）", 3,
                "core_march · 12 ms/步")
    cellw, cellh = (w - 40) / 2, (h - 86) / 2
    specs = (("T_e , T_i [keV]", lambda r, g: (3.0 + 0.9 * g)
              * (1 - r ** 2) ** 1.5 + 0.1),
             ("n_e [10¹⁹ m⁻³]", lambda r, g: (4.0 + 0.15 * g)
              * (1 - r ** 2) + 0.3),
             ("q", lambda r, g: 0.95 - 0.08 * g + (3.6 + 0.1 * g) * r ** 2),
             ("j_φ [MA/m²]", lambda r, g: (1.15 + 0.10 * g)
              * (1 - r ** 2) ** 1.7 + 0.02))
    for i, (name, fn) in enumerate(specs):
        px = x + 16 + (i % 2) * (cellw + 8)
        py = top + 16 + (i // 2) * (cellh + 20)
        top_v = max(fn(0.0, 1.0), fn(1.0, 1.0)) * 1.15
        ax = Axes(px, py, cellw, cellh, (0, 1), (0, top_v))
        for g, cls in ((0.0, "trail2"), (0.5, "trail1")):
            ax.plot([(j / 40, fn(j / 40, g)) for j in range(41)], cls)
        ax.plot([(j / 40, fn(j / 40, 1.0)) for j in range(41)], "prof")
        if i == 0:
            ax.plot([(j / 40, 0.9 * fn(j / 40, 1.0)) for j in range(41)],
                    "prof2")
        text(px + 2, py - 3, name, "mut", 9)
    text(x + 16, y + h - 40,
         "淡影＝前两个记录时刻（拖影即演化本身，不是装饰）", "mut", 9)
    text(x + 16, y + h - 26,
         "热 / 粒子 / 电流三通道同步推进；源随温度逐步重建", "mut", 9)
    text(x + 16, y + h - 12,
         "★这一块只属于 1.5-D 档：切到 0-D 档它空着并说明，不用规定剖面顶替（D-22）",
         "mut", 9)


def s_corr(x, y, w, h):
    """④ 滚动走廊 — the right edge is NOW, and the future is not drawn."""
    top = panel(x, y, w, h, "滚动走廊（右缘＝现在）", 4,
                f"窗口 {SIM_WIN:.0f} s · 记录写入运行清单")
    t0, t1 = T_SIM - SIM_WIN, T_SIM + 0.55
    lanes = (
        ("Ip [kA]：目标 / 实现", ((sample(lambda t: 1.035 * ip_of(t) + 6, 160, t0,
                                          T_SIM), "target", (0, 460)),
                                 (sample(ip_of, 160, t0, T_SIM), "ip",
                                  (0, 460)))),
        ("n_e0 [10¹⁹] / W_th [MJ]", ((sample(ne_of, 160, t0, T_SIM), "ne",
                                      (0, 6.0)),
                                     (sample(lambda t: 20 * w_sim(t), 160, t0,
                                             T_SIM), "wth", (0, 6.0)))),
        ("P [MW]: 束 · 波 · 欧姆", ((sample(paux_sim, 320, t0, T_SIM), "heat",
                                    (0, 9.0)),
                                   (sample(pohm_of, 160, t0, T_SIM), "pohm",
                                    (0, 9.0)))),
        ("PF 通道电流 [kA·匝]", ((sample(lambda t: ich_sim(t, 6.2, 2.4), 160, t0,
                                        T_SIM), "c1", (-12, 12)),
                                (sample(lambda t: ich_sim(t, -5.0, -1.9), 160,
                                        t0, T_SIM), "c2", (-12, 12)),
                                (sample(lambda t: ich_sim(t, 2.2, 1.3), 160, t0,
                                        T_SIM), "c3", (-12, 12)))),
    )
    lh = (h - 96) / len(lanes)
    axes = []
    for i, (name, series) in enumerate(lanes):
        ly = top + 18 + i * lh
        ax = Axes(x + 150, ly, w - 172, lh - 8, (t0, t1), (0, 1))
        axes.append(ax)
        rect(ax.px(T_SIM), ax.y, ax.px(t1) - ax.px(T_SIM), ax.h, "future", rx=0)
        for pts, cls, (v0, v1) in series:
            ax.y0, ax.y1 = v0, v1
            ax.plot(pts, cls)
        if i == 3:
            ax.y0, ax.y1 = -12, 12
            rect(ax.x, ax.py(10.5), ax.px(T_SIM) - ax.x,
                 ax.py(-10.5) - ax.py(10.5), "limband", rx=0)
        line(ax.px(T_SIM), ax.y, ax.px(T_SIM), ax.y + ax.h, "nowedge")
        line(ax.px(T_SLIDER), ax.y, ax.px(T_SLIDER), ax.y + ax.h, "sliderline")
        text(x + 144, ly + (lh - 8) / 2 + 3, name, "lbl", 9.5, "end")
    ax = axes[-1]
    for t in (1.0, 2.0, 3.0, 4.0):
        text(ax.px(t), ax.y + ax.h + 12, f"{t:.0f}", "mut", 9, "middle")
    text(ax.px(T_SIM), ax.y + ax.h + 12, f"现在 {T_SIM:.2f}", "bad-t", 9,
         "middle")
    text(x + 144, ax.y + ax.h + 12, "t [s]", "mut", 9, "end")
    text(ax.px(T_SLIDER), axes[0].y - 6, f"滑块 {T_SLIDER:.2f} s", "warn-t", 9,
         "middle")
    bx = x + 16
    for s_ in ("⏸", "⏭", "⟲"):
        rect(bx, y + h - 32, 26, 20, "btn", rx=4)
        text(bx + 13, y + h - 18, s_, "lbl", 11, "middle")
        bx += 30
    bx += 6
    for s_ in ("×0.5", "×1", "×2", "尽快"):
        bx += chip(bx, y + h - 32, s_, "chip-on" if s_ == "×1" else "chip") + 6
    lx = x + w - 372
    for lab, cls in (("已真解磁面", "tick"), ("度规插值区间", "tick-i"),
                     ("滑块改动点", "sliderline"), ("尚未发生", "future-l")):
        line(lx, y + h - 22, lx + 14, y + h - 22, cls)
        text(lx + 20, y + h - 18.5, lab, "mut", 9)
        lx += tw(lab, 9) + 30


# --------------------------------------------------------------------------- #
# 图三：三合一 —— 一个页面，一份脚本，三种时间观
#
# ★Why a third figure rather than a variant of the first two.  The merge is not
# a layout change: 配置 / 设计 / 仿真 differ in what the TIME AXIS MEANS (one
# instant · a whole pulse that exists · a past that is still growing), and that
# is the one thing a mockup of a single mode cannot show.  So the page is drawn
# once, in its 设计 mode, and the axis is drawn three times underneath.
def build_sim() -> str:
    out.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H_SIM}" '
        f'width="{W}" height="{H_SIM}" role="img" '
        f'aria-label="fylite 交互仿真模式界面概念图">')
    add("<title>fylite 脉冲设计 · 交互仿真 — 界面概念图</title>")
    add(f"<style>{STYLE}</style>")
    rect(0, 0, W, H_SIM, "bg", rx=0)
    sim_header()
    lw = 336
    s_console(M, TOP, lw, 638)
    cw = 400
    s_equil(M + lw + 10, TOP, cw, 638)
    rw = W - M - (M + lw + 10 + cw + 10)
    s_prof(M + lw + cw + 20, TOP, rw, 638)
    s_corr(M, TOP + 648, W - 2 * M, 314)
    text(M + 2, H_SIM - 12,
         "概念图（非截图）：仿真模式的时间轴只有过去——右缘是现在，右侧留白是"
         "尚未发生的部分。曲线为示意形状，不是任何一次推进的输出。",
         "mut", 9.5)
    add("</svg>")
    return "\n".join(out) + "\n"


def build() -> str:
    out.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="fylite 脉冲设计工作台交互界面概念图">')
    add("<title>fylite 脉冲设计工作台 — 交互界面概念图</title>")
    add(f"<style>{STYLE}</style>")
    rect(0, 0, W, H, "bg", rx=0)
    header()
    # left column
    lx, lw = M, 284
    p_ip(lx, TOP, lw, 190)
    p_lcfs(lx, TOP + 198, lw, 168)
    p_heat(lx, TOP + 374, lw, 158)
    # centre column
    cx_, cw = lx + lw + 10, 480
    p_equil(cx_, TOP, cw, 332)
    p_prof(cx_, TOP + 340, cw, 192)
    # right column
    rx_, rw = cx_ + cw + 10, W - M - (cx_ + cw + 10)
    p_pf(rx_, TOP, rw, 332)
    p_table(rx_, TOP + 340, rw, 192)
    # bottom
    corridor(M, TOP + 542, W - 2 * M, 260)
    text(M + 2, H - 12,
         "概念图（非截图）：面板为 FYL-DESIGN-09 所裁定的布局，曲线为示意形状，"
         "不是任何一次求解的输出。相位时刻与平顶电流取 app/pages/design.html 的缺省值。",
         "mut", 9.5)
    add("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 图四 · 五 · 六：建模 / 分析 / 数据三页 (FYL-DESIGN-10)
#
# ★These three share the pulse figures' primitives on purpose.  The reader who
# has looked at one page's concept drawing must not have to re-learn what a
# chip, a callout or a dimmed row means when they look at the next; the
# vocabulary IS the claim that these are one application and not four.
#
# ★Same discipline as above: concept, not screenshot.  Every number drawn here
# is either a default the markup carries or a measurement this repository has
# actually made (they are named in the captions and in FYL-DESIGN-10); the
# curves are illustrative shapes.
# --------------------------------------------------------------------------- #
H_MODEL, H_ANALYSIS, H_DATA = 1234, 1184, 1262


def app_header(title, *, bars=(), chips=(), badge=None, badge_cls="badge-ok",
               badge_t="ok-t", bx=None):
    """The one header shape the three pages share: name · 功能栏 · 徽章."""
    rect(M, M, W - 2 * M, 40, "head")
    text(M + 14, M + 26, title, "head-t", 15, weight="600")
    x = bx if bx is not None else M + 30 + tw(title, 15)
    for name, on in bars:
        wsw = tw(name, 10) + 20
        rect(x, M + 9, wsw, 22, "chip-on" if on else "chip", rx=6)
        text(x + wsw / 2, M + 24, name, "lbl" if on else "chipt", 10, "middle")
        x += wsw + 4
    x += 10
    for s in chips:
        x += chip(x, M + 11, s) + 8
    if badge:
        bw = tw(badge, 10.5) + 18
        rect(W - M - bw - 12, M + 10, bw, 20, badge_cls, rx=10)
        text(W - M - bw / 2 - 12, M + 24, badge, badge_t, 10.5, "middle")


def note(x, y, lines, size=9, cls="mut"):
    """The small print under a panel — one call, so the leading is uniform."""
    for i, s in enumerate(lines):
        text(x, y + i * 12.5, s, cls, size)


def rowbox(x, y, w, cols, hdr, rows, *, row_h=18, size=9.3):
    """A read-out table.  ``rows`` is (cells, kind); kind tints the row."""
    for cx, s in zip(cols, hdr):
        text(x + cx, y, s, "mut", size)
    yy = y + 6
    for cells, kind in rows:
        yy += row_h
        if kind:
            rect(x + 4, yy - 12, w - 8, row_h - 2,
                 {"bad": "rowbad", "unk": "rowunk", "sel": "rowsel"}[kind],
                 rx=3)
        for i, (cx, s) in enumerate(zip(cols, cells)):
            cls = "lbl"
            if i == len(cells) - 1 and kind == "bad":
                cls = "bad-t"
            elif i == len(cells) - 1 and kind == "unk":
                cls = "warn-t"
            text(x + cx, yy, s, cls, size)
    return yy


def checks(x, y, items, *, gap=17, size=9.6):
    """A column of checkboxes; ``items`` is (label, on|'off'|'disabled')."""
    for lab, st in items:
        rect(x, y - 8, 10, 10, "chip-on" if st == "on" else "chip", rx=2)
        if st == "on":
            add(f'<path d="M {x + 2:.1f} {y - 3.4:.1f} l 2.6 2.6 l 4.4 -5.2" '
                f'class="nowedge" fill="none"/>')
        text(x + 16, y, lab, "mut" if st == "off" else "lbl", size)
        if st == "off":
            text(x + 16 + tw(lab, size) + 6, y, "· 度规定不出，禁用", "warn-t",
                 8.4)
        y += gap
    return y


def minifig(x, y, w, h, label, fns, xr=(0, 1), *, marks=()):
    """A small profile figure: one box, one caption, one or two curves."""
    vals = [[f(i / 40) for i in range(41)] for f in fns]
    hi = max(max(v) for v in vals) * 1.15 or 1.0
    lo = min(0.0, min(min(v) for v in vals))
    ax = Axes(x, y, w, h, xr, (lo, hi))
    for i, v in enumerate(vals):
        ax.plot([(xr[0] + (xr[1] - xr[0]) * j / 40, u)
                 for j, u in enumerate(v)], "prof" if i == 0 else "prof2")
    for mx in marks:
        ax.vline(mx)
    text(x + 2, y - 3, label, "mut", 9)
    return ax


# --------------------------------------------------------------------------- #
# 图四：物理建模页
# --------------------------------------------------------------------------- #
MODEL_BARS = (("1.5D 定态输运", True), ("边界与度规", False),
              ("功率平衡反演", False))


def m_shared(x, y, w, h):
    """① 这台机器（两条栏共读）."""
    top = panel(x, y, w, h, "这台机器（三条栏共读）", 1, "栏外")
    fw = (w - 28 - 12) / 3
    vals = (("a [m]", "0.45"), ("R/a", "4.1"), ("κ", "1.65"),
            ("δ", "0.45"), ("边界 q", "4.2"), ("B₀ [T]", "1.80"),
            ("n_e(0) [10¹⁹]", "4.0"), ("χ₀ [m²/s]", "1.0"), ("—", "—"))
    for i, (lab, val) in enumerate(vals[:6]):
        field(x + 14 + (i % 3) * (fw + 6), top + 12 + (i // 3) * 40, fw,
              lab, val)
    for i, (lab, val) in enumerate(vals[6:8]):
        field(x + 14 + i * (fw + 6), top + 92, fw, lab, val)
    note(x + 14, y + h - 32,
         ["★一个量一个控件：它住在栏外，因为栏一折就会",
          "把自己的面板收起来，共用控件不能跟着消失（P-3）。"])


def m_transport(x, y, w, h):
    """② 栏一 · 1.5D 芯部输运."""
    top = panel(x, y, w, h, "栏一 · 1.5D 定态输运", 2, "主线程 · 41 点")
    yy = top + 14
    text(x + 14, yy, "闭包", "mut", 9.5)
    cx = x + 14
    yy += 6
    for s, on in (("常数 χ", False), ("刚性", False), ("中子", True),
                  ("TGLF", False)):
        cx += chip(cx, yy, s, "chip-on" if on else "chip", 9.5) + 5
    yy += 30
    fw = (w - 28 - 6) / 2
    for i, (lab, val) in enumerate((("源峰值 [任意单位]", "1.0"),
                                    ("沉积宽度", "0.30"),
                                    ("边界值 T(1) [keV]", "0.10"),
                                    ("网格点数", "41"))):
        field(x + 14 + (i % 2) * (fw + 6), yy + (i // 2) * 40, fw, lab, val)
    yy += 86
    gw = (w - 28 - 8) / 2
    minifig(x + 14, yy + 10, gw, 56, "T(r) [keV]",
            [lambda r: 3.0 * (1 - r ** 2) ** 1.5 + 0.1])
    minifig(x + 22 + gw, yy + 10, gw, 56, "χ(r) [m²/s] · 源（虚）",
            [lambda r: 0.6 + 2.4 * r ** 2,
             lambda r: 2.4 * math.exp(-(r / 0.3) ** 2) + 0.2])
    note(x + 14, y + h - 38,
         ["★网格是米，不是 r/a——旧网格上少了一个 a²，χ 还是滑块时看不出来，",
          "换成物理闭包的那一天就错了（P-17）。",
          "★它报不出 W、τ_E、β_N：几何固定，压强不改变它所在的磁面。"])


def m_interp(x, y, w, h):
    """③ 栏三 · 功率平衡反演."""
    top = panel(x, y, w, h, "栏三 · 功率平衡反演", 3, "反着解，不拟合")
    yy = top + 14
    fw = (w - 28 - 6) / 2
    for i, (lab, val) in enumerate((("几何来源", "device ▾"), ("磁面数", "65"),
                                    ("梯度地板", "1e-3"), ("V_loop [V]", "0.9"))):
        field(x + 14 + (i % 2) * (fw + 6), yy + (i // 2) * 40, fw, lab, val)
    yy += 88
    text(x + 14, yy, "剖面来自「含时演化」栏的导入（一页一份文档）", "mut", 9)
    #: ★the break is the point: below the gradient floor there is NO answer,
    #: and the figure has to show a gap rather than a number.
    ax = Axes(x + 14, yy + 24, w - 28, 74, (0, 1), (0, 6))
    chi = lambda r: 0.7 + 5.2 * r ** 2.4                          # noqa: E731
    ax.plot([(r / 60, chi(r / 60)) for r in range(9, 57)], "prof")
    for a, b in ((0.0, 0.14), (0.945, 1.0)):
        rect(ax.px(a), ax.y, ax.px(b) - ax.px(a), ax.h, "rowunk", rx=0)
    text(ax.px(0.07), ax.y + 12, "断口", "warn-t", 8.6, "middle")
    text(ax.px(0.5), ax.y - 3, "χ_e , χ_i [m²/s]", "mut", 9)
    text(ax.px(0.5), ax.y + ax.h + 11,
         "0.15 ≤ ρ/a ≤ 0.93 把 χ₀ 找回到百分之一以内", "mut", 8.6, "middle")
    note(x + 14, y + h - 50,
         ["★没有任何量被极小化：不是拟合，也不是预测。",
          "★两端照画不误，但不进体积平均——ρ/a = 0.03 高 50 %、",
          "  0.07 高 6.8 %；边界节点高 110 %（单侧差分）。",
          "★半径盖不住这套度规时拒绝，不外推（P-6）。"])


def m_profiles(x, y, w, h):
    """⑥ 终态剖面."""
    top = panel(x, y, w, h, "定态解 · 剖面", 7, "ρ̂ = √(Φ/Φ_b)")
    cw, ch = (w - 36) / 2, (h - 126) / 2
    specs = (("T_e , T_i [keV]", (lambda r: 3.2 * (1 - r ** 2) ** 1.4 + 0.35,
                                  lambda r: 2.7 * (1 - r ** 2) ** 1.5 + 0.30)),
             ("n_e [10¹⁹ m⁻³]", (lambda r: 4.0 * (1 - r ** 2) ** 0.8 + 0.6,)),
             ("q", (lambda r: 0.95 + 3.5 * r ** 2,)),
             ("χ_e [m²/s]（这一档的闭包）", (lambda r: 0.6 + 4.4 * r ** 2.2,)))
    for i, (lab, fns) in enumerate(specs):
        minifig(x + 14 + (i % 2) * (cw + 8), top + 20 + (i // 2) * (ch + 24),
                cw, ch, lab, list(fns))
    note(x + 14, y + h - 30,
         ["★边界值是你给的一个数：这一页没有台基模型——台基属于含时那一档，",
          "  它随栏一起迁去了放电设计页（P-19 推论 1）。",
          "★四张图都画在栏二解出来的那张 ψ 上；它没收敛时页面如实说。"])


def m_boundary(x, y, w, h):
    """④ 栏二 · 边界与度规（控件与判据）."""
    top = panel(x, y, w, h, "栏二 · 边界与度规（当前栏）", 4, "不含时 · 解一次",
                "badge-ok")
    yy = top + 14
    fw = (w - 28 - 3 * 6) / 4
    for i, (lab, val) in enumerate((("边界类别", "双零 ▾"), ("R₀ [m]", "1.85"),
                                    ("a [m]", "0.45"), ("I_p [kA]", "400"))):
        field(x + 14 + i * (fw + 6), yy, fw, lab, val)
    yy += 44
    for i, (lab, val) in enumerate((("线圈电流来源", "静态反解 ▾"),
                                    ("磁面数", "65"), ("迭代上限", "600"),
                                    ("容差", "1e-6"))):
        field(x + 14 + i * (fw + 6), yy, fw, lab, val)
    yy += 48
    text(x + 14, yy, "位形判据（与放电设计页同一组）", "mut", 9.5)
    cols = (14, 150, 250, 340)
    rowbox(x, yy + 12, w, cols, ("判据", "得到", "所要求", "判定"),
           [(("形状误差 RMS", "8.6 mm", "≤ 20 mm", "✓"), ""),
            (("X 点位置", "(1.44, −1.02)", "壁内", "✓"), ""),
            (("最小壁间隙", "38 mm", "≥ 40 mm", "越界"), "bad"),
            (("q₉₅ · l_i(3)", "4.12 · 0.92", "—", "报出"), "")])
    note(x + 14, y + h - 44,
         ["★这一栏解的是一条边界，不是一串时刻：它把 ψ、逐面度规与判据一次给",
          "  出来，交给另外两条栏站着（P-19 推论 2）。",
          "★自由边界没收敛就说没收敛——收敛自报是这一栏的产物之一（P-5）。"])


def m_equil(x, y, w, h):
    """⑤ 这一页解出来的那条边界."""
    top = panel(x, y, w, h, "平衡截面（这一页解出来的那条边界）", 5,
                "已解 · ≈1.2 s", "badge-ok")
    cx, cy = x + w / 2 - 20, top + (h - 60) / 2
    sc = (h - 120) / 2 / 1.75
    add(f'<path d="M {cx - 1.30 * sc:.1f} {cy - 1.55 * sc:.1f} '
        f'q {2.6 * sc:.1f} {-0.35 * sc:.1f} {2.6 * sc:.1f} {0.0:.1f} '
        f'l 0 {3.1 * sc:.1f} q {-2.6 * sc:.1f} {0.35 * sc:.1f} '
        f'{-2.6 * sc:.1f} 0 z" class="vessel"/>')
    for dx, dy, hot in ((-1.50, -1.28, 1), (-1.50, -0.42, 0), (-1.50, 0.42, 0),
                        (-1.50, 1.28, 1), (1.50, -1.28, 1), (1.50, -0.42, 0),
                        (1.50, 0.42, 0), (1.50, 1.28, 1)):
        rect(cx + dx * sc - 8, cy + dy * sc - 6, 16, 12,
             "coil-hot" if hot else "coil", rx=2)

    def miller(a, k, d, n=121):
        p = []
        for i in range(n):
            th = 2 * math.pi * i / (n - 1)
            p.append((cx + sc * a * math.cos(th + d * math.sin(th)),
                      cy - sc * a * k * math.sin(th)))
        return p
    for f in (0.25, 0.5, 0.75):
        poly(miller(0.92 * f, 1.60, 0.36 * f), "flux")
    poly(miller(0.92, 1.60, 0.36), "lcfs")
    poly([(px + 3.0, py + 1.6) for px, py in miller(0.95, 1.58, 0.34)],
         "lcfs-target")
    handle(cx + 3, cy - 0.10 * sc, 2.6, "axis")
    xr, xz = cx - 0.34 * sc, cy + 1.47 * sc
    add(f'<path d="M {xr - 5:.1f} {xz:.1f} l 10 0 M {xr:.1f} {xz - 5:.1f} '
        f'l 0 10" class="xpt"/>')
    lx, ly = x + w - 116, top + 14
    for lab, cls in (("目标边界", "lcfs-target"), ("解出来的 LCFS", "lcfs"),
                     ("PF 线圈（着色＝电流）", "coil-hot")):
        line(lx, ly, lx + 16, ly, cls)
        text(lx + 22, ly + 3.5, lab, "mut", 9)
        ly += 15
    note(x + 14, y + h - 38,
         ["★这一片没有时刻：它是一条边界，不是一炮里的某一秒。",
          "  「这一片是哪一时刻的」那个问题属于放电设计页（D-8 · D-22）。",
          "★壁间隙越界已按判据报出（见上一栏），页面不静默收窄。"])


def m_metric(x, y, w, h):
    """⑥ 逐面度规 — what the other two bars actually stand on."""
    top = panel(x, y, w, h, "逐面度规（交出去的那一半）", 6, "V′ · ⟨|∇ρ|²⟩ · gm7")
    gw = (w - 36) / 3
    specs = (("V′(ρ̂)", lambda r: 0.05 + 2.6 * r),
             ("⟨|∇ρ|²⟩", lambda r: 1.35 - 0.45 * r ** 2),
             ("gm7 = ⟨|∇ρ|⟩", lambda r: 1.02 + 0.22 * r))
    for i, (lab, fn) in enumerate(specs):
        minifig(x + 14 + i * (gw + 8), top + 22, gw, h - 92, lab, [fn])
    note(x + 14, y + h - 50,
         ["★电流道要求逐面度规（它要 ⟨|∇ρ|²/R²⟩，四个标量定不出来），",
          "  所以 Miller 几何下那条道是禁用的，不是被悄悄忽略。",
          "★这三条曲线是交给另外两条栏、也交给放电设计页 1.5-D 档的那份",
          "  工件的一半；另一半是边界本身与 χ 的标定。"])


def m_readout(x, y, w, h):
    """⑧ 解的读数 · 判定（定态，不含时）."""
    top = panel(x, y, w, h, "解的读数 · 判定", 8, "全是定态量")
    cols = (14, 150, 250)
    rows = ((("轴温 T(0)", "3.14 keV", "定态解"), ""),
            (("峰边比 T(0)/T(1)", "31.4", ""), ""),
            (("内迭代次数 · 残差", "12 · 4.2e-7", "已收敛"), ""),
            (("耗时", "0.9 ms", "主线程（P-15）"), ""),
            (("边界 q", "4.20", "由栏二的度规读"), ""),
            (("几何来源", "本页栏二解出", "不是导入的"), ""),
            (("自由边界", "600 次内达 4.2e-5", "收敛自报"), ""),
            (("W_th · τ_E · β_N", "—", "本页报不出"), "unk"))
    yy = rowbox(x, top + 16, w, cols, ("量", "值", "它自己说的话"), rows)
    yy += 16
    for s_, cls in (("★定态解在 12 次内迭代内收敛", "badge-ok"),
                    ("★未收敛（残差 …）——宁可如实报出来", "stale")):
        bw = min(w - 28, tw(s_, 9.4) + 16)
        rect(x + 14, yy + 4, bw, 19, cls, rx=6)
        text(x + 22, yy + 17, s_,
             "ok-t" if cls == "badge-ok" else "stalet", 9.4)
        yy += 24
    note(x + 14, y + h - 50,
         ["★最后一行是这次搬迁换来的诚实：W、τ_E、β_N 需要时间演化，",
          "  它们在放电设计页的 1.5-D 档里（D-22），不在这一页。",
          "★迁走的那条栏也把它那句过期的自述一起带走了（G-1 · P-19 推论 1）。"])


def m_handoff(x, y, w, h):
    """⑨ 交出去的那份工件."""
    top = panel(x, y, w, h, "交出去的那份工件", 9, "主路，不是备份")
    yy = top + 12
    for lab, sub in (("度规", "V′ · ⟨|∇ρ|²⟩ · gm7 · 逐面"),
                     ("边界", "LCFS · X 点 · 判据与它们的判定"),
                     ("χ 的标定", "闭包档位与它标在哪条剖面上")):
        rect(x + 14, yy, w - 28, 26, "card-back", rx=5)
        text(x + 24, yy + 11, lab, "lbl", 10, weight="600")
        text(x + 24, yy + 22, sub, "mut", 8.8)
        yy += 30
    ay = yy + 2
    line(x + w / 2, ay, x + w / 2, ay + 14, "reg-fb")
    add(f'<path d="M {x + w / 2 - 4:.1f} {ay + 10:.1f} l 4 6 l 4 -6" '
        f'class="reg-fb" fill="none"/>')
    b = "放电设计页 · 仿真 · 1.5-D 档"
    bw = tw(b, 10) + 20
    rect(x + w / 2 - bw / 2, ay + 20, bw, 24, "chip-on", rx=6)
    text(x + w / 2, ay + 36, b, "lbl", 10, "middle")
    note(x + 14, y + h - 52,
         ["★P-19 之后这条边是主路：含时推进站在这一页解出来的度规上，因此它要",
          "  有名字、有双宿主一致性判据、有「这条剖面站在哪一次平衡上」的出处",
          "  （P-13）。今天它只是一份导出 / 导入的文件（G-3 · G-11）。"])


def m_directions(x, y, w, h):
    """⑩ 三条栏，三个方向——而且都不含时."""
    top = panel(x, y, w, h, "三条栏，三个方向（同一套度规、同一条能量平衡）", 10,
                "三条都不含时")
    cw = (w - 40) / 3
    cards = (
        ("栏一 · 1.5D 定态输运", "给 χ，求 T",
         ["在栏二解出的度规上求定态剖面；网格是米。",
          "报不出 W、τ_E、β_N——那需要时间演化。",
          "χ 是规定的。"]),
        ("栏二 · 边界与度规", "给电流与位形，求 ψ",
         ["固定边界 / 自由边界平衡，解一次，给出逐面度规、",
          "边界与它的判据；另外两条栏站在它上面。",
          "χ 不参与——这一栏不解输运。"]),
        ("栏三 · 功率平衡反演", "给 T，反求 χ",
         ["把同一条能量平衡反过来解，一个量都不极小化；",
          "半径盖不住这套度规就拒绝，不外推。",
          "χ 是算出来的——和你给的源一样可靠。"]))
    for i, (name, dirn, lines) in enumerate(cards):
        px = x + 14 + i * (cw + 6)
        rect(px, top + 12, cw, h - 96, "card-front" if i == 0 else "card-back",
             rx=6)
        text(px + 12, top + 32, name, "lbl", 11, weight="600")
        bw = tw(dirn, 10) + 16
        rect(px + 12, top + 40, bw, 18, "chip-on" if i == 0 else "chip", rx=9)
        text(px + 12 + bw / 2, top + 52.5, dirn, "lbl", 10, "middle")
        note(px + 12, top + 76, lines)
    note(x + 14, y + h - 42,
         ["★这一页没有时间轴。原先那条含时演化栏收敛进放电设计页，在那里成为仿真"
          "推进的 1.5-D 保真度档（P-19 · FYL-DESIGN-09 D-22）——能力一件没少，",
          "  只是不再有两条时间轴：时间是「这一炮怎么打」的事，不是「剖面长什么样」"
          "的事。",
          "★三条栏共读页顶那一份共用参数；栏与栏之间靠页内文档相接，不靠一条互相"
          "唤醒的总线（P-4）。"])


def build_model() -> str:
    out.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H_MODEL}" '
        f'width="{W}" height="{H_MODEL}" role="img" '
        f'aria-label="fylite 物理建模页界面概念图">')
    add("<title>fylite 物理建模页 — 界面概念图（不含时）</title>")
    add(f"<style>{STYLE}</style>")
    rect(0, 0, W, H_MODEL, "bg", rx=0)
    app_header("fylite · 物理建模 (Physics Modelling)", bars=MODEL_BARS,
               chips=("装置：EAST ▾",),
               badge="三条栏都不含时 · 时间轴在放电设计页", bx=M + 356)
    lw, mw = 316, 448
    rw = W - 2 * M - lw - mw - 20
    m_shared(M, 68, lw, 206)
    m_transport(M, 282, lw, 300)
    m_interp(M, 590, lw, 330)
    m_boundary(M + lw + 10, 68, mw, 296)
    m_equil(M + lw + 10, 372, mw, 356)
    m_metric(M + lw + 10, 736, mw, 224)
    m_profiles(M + lw + mw + 20, 68, rw, 300)
    m_readout(M + lw + mw + 20, 376, rw, 340)
    m_handoff(M + lw + mw + 20, 724, rw, 264)
    m_directions(M, 1000, W - 2 * M, 200)
    text(M + 2, H_MODEL - 12,
         "概念图（非截图）：这是 FYL-DESIGN-10 裁定 P-19 之后的形状——含时演化栏"
         "收敛进放电设计页（D-22），本页只留定态、边界与反演。曲线为示意形状。",
         "mut", 9.5)
    add("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 图五：实验分析页
# --------------------------------------------------------------------------- #
ANALYSIS_BARS = (("剖面拟合", False), ("平衡反演", True), ("时间序列", False),
                 ("批处理队列", False))


def a_source(x, y, w, h):
    """① 数据源与预设."""
    top = panel(x, y, w, h, "分析预设 · 数据源", 1, "预设只填，不跑")
    yy = top + 14
    cx = x + 14
    for s, on in (("实炮反演", True), ("纯磁反演", False), ("动理学反演", False),
                  ("爬升段", False), ("孪生自检", False)):
        wch = tw(s, 9.5) + 16
        if cx + wch > x + w - 14:
            cx, yy = x + 14, yy + 24
        cx += chip(cx, yy, s, "chip-on" if on else "chip", 9.5) + 5
    yy += 34
    fw = (w - 28 - 6) / 2
    field(x + 14, yy, fw, "炮号 · 时刻", "#137985 @ 4.00 s")
    field(x + 20 + fw, yy, fw, "来源", "真实测量 ▾")
    yy += 42
    text(x + 14, yy, "通道基准", "mut", 9.5)
    cx = x + 14 + tw("通道基准", 9.5) + 10
    for s, on in (("交付重构的通道值", True), ("原始 est2 读数", False)):
        cx += chip(cx, yy - 12, s, "chip-on" if on else "chip", 9.3) + 5
    note(x + 14, y + h - 26,
         ["★★两套通道基准不可混用：同一 (炮号, 时刻) 用两种拼法曾给出",
          "  相反的判定——所以它是一个显式开关，不是一个缺省（P-1 推论）。"])


def a_constraints(x, y, w, h):
    """② 约束的来源."""
    top = panel(x, y, w, h, "约束的来源（拟合里到底有什么）", 2, "★不是只有磁")
    yy = checks(x + 14, top + 22,
                [("磁通环 35 道", "on"), ("磁探针（权重 0.6）", "on"),
                 ("压强约束行（动理学）", "on"),
                 ("干涉 / 法拉第 弦", "on"),
                 ("线圈电流参与拟合（两个 σ）", "on"),
                 ("真空室涡流为未知量", "on"),
                 ("Thomson n_e / T_e", "off"),
                 ("MSE · SXR 层析", "off")], gap=19)
    yy += 6
    text(x + 14, yy, "自举—欧姆—拟合电流：外环 6 轮 · 容差 1e-3", "mut", 9.3)
    yy += 18
    text(x + 14, yy, "压强分解：T_i/T_e = 1.0 · 快离子份额 0.15", "mut", 9.3)
    note(x + 14, y + h - 62,
         ["★磁测量单独约束不住内部剖面——很不一样的剖面能给出几乎一样好的",
          "  磁场拟合。把解定下来的是动理学约束，这正是「动理学重构」的分别。",
          "★关掉的两行不是接线缺失，是装置数据缺失：内核有层析基与响应行，",
          "  缺的是随包卷宗里的几何（G-4）。",
          "★把热剖面当总压交给拟合，是束加热放电给出错误 p′ 的标准途径，",
          "  而拟合本身发现不了。"])


def a_verdict(x, y, w, h):
    """③ 判定与三条拒绝判据."""
    top = panel(x, y, w, h, "判定 · 三条拒绝判据", 3, "判据只有一处")
    yy = top + 16
    s = "这次拟合：χ²/自由度 = 1.42（dof 41），约束来自"
    text(x + 14, yy, s, "lbl", 9.6)
    yy += 15
    text(x + 14, yy, "磁通环 33 道 + 磁探针 21 道 + 压强 24 点 + 法拉第 3 弦；",
         "lbl", 9.6)
    yy += 15
    text(x + 14, yy, "按 3·RMS 判有 2 道离群；真空室已拟（投影后残存 5.6 %）。",
         "lbl", 9.6)
    yy += 20
    bw = w - 28
    rect(x + 14, yy, bw, 19, "stale", rx=6)
    text(x + 22, yy + 13, "★未跑后验——这一行里没有不确定度。", "stalet", 9.3)
    yy += 32
    text(x + 14, yy, "拒绝：解出来的不是等离子体（worker 里的一处判据）",
         "mut", 9.5)
    yy += 6
    for i, (t1, t2) in enumerate(
            (("① I_p 等式约束偏离 > 50 %", "「求解器返回了，返回的不是所问那个问题」"),
             ("② 拟合 a < 装置半宽的 0.1", "「是一团贴着限制器的电流丝」"),
             ("③ 线圈被拉动 > 判据 σ", "「靠不再相信标定把残差压下去」"))):
        ry = yy + 18 + i * 30
        rect(x + 14, ry - 12, bw, 27, "rowbad" if i == 2 else "rowunk", rx=4)
        text(x + 22, ry, t1, "lbl", 9.4)
        text(x + 22, ry + 12, t2, "mut", 8.8)
    note(x + 14, y + h - 52,
         ["★实测：默认 σ 下九片卷宗的最大线圈拉动为 1.04–1.60 σ。",
          "★批处理队列不另立判据——同一处判据判所有的行；",
          "  没解出来的行写明是哪一条不成立（P-7）。"])


def a_cross(x, y, w, h):
    """④ 重构截面 · 逐道着色."""
    top = panel(x, y, w, h, "重构截面 · 磁通环按残差着色", 4,
                "空心＝权重为零", "badge")
    cx, cy = x + w / 2 - 24, top + 138
    sc = (h - 232) / 2 / 1.75
    add(f'<path d="M {cx - 1.30 * sc:.1f} {cy - 1.55 * sc:.1f} '
        f'q {2.6 * sc:.1f} {-0.35 * sc:.1f} {2.6 * sc:.1f} {0.0:.1f} '
        f'l 0 {3.1 * sc:.1f} q {-2.6 * sc:.1f} {0.35 * sc:.1f} '
        f'{-2.6 * sc:.1f} 0 z" class="vessel"/>')

    def miller(a, k, d, n=121):
        p = []
        for i in range(n):
            th = 2 * math.pi * i / (n - 1)
            p.append((cx + sc * a * math.cos(th + d * math.sin(th)),
                      cy - sc * a * k * math.sin(th)))
        return p
    for f in (0.3, 0.55, 0.8):
        poly(miller(0.92 * f, 1.58, 0.34 * f), "flux")
    poly(miller(0.92, 1.58, 0.34), "lcfs")
    handle(cx + 4, cy - 0.08 * sc, 2.6, "axis")
    #: flux loops around the wall — filled = in the fit, hollow = weight zero,
    #: red = flagged by the k·RMS criterion.  A row of dots IS the fit report.
    n = 18
    for i in range(n):
        th = 2 * math.pi * i / n
        lx = cx + 1.44 * sc * math.cos(th)
        ly = cy + 1.66 * sc * math.sin(th)
        if i in (4, 11):
            add(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4.2" fill="none" '
                f'stroke="var(--bad)" stroke-width="1.8"/>')
        elif i in (7, 15):
            add(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" fill="none" '
                f'stroke="var(--grid)" stroke-width="1.4"/>')
        else:
            add(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" class="axis" '
                f'opacity="{0.30 + 0.5 * abs(math.sin(th)):.2f}"/>')
    lx, ly = x + w - 150, top + 18
    for lab, kind in (("在拟合里（深浅＝|Δ|）", "f"), ("权重为零（空心）", "h"),
                      ("按 k·RMS 判为离群", "b")):
        if kind == "f":
            add(f'<circle cx="{lx + 6:.1f}" cy="{ly:.1f}" r="3.6" '
                f'class="axis"/>')
        elif kind == "h":
            add(f'<circle cx="{lx + 6:.1f}" cy="{ly:.1f}" r="3.6" fill="none" '
                f'stroke="var(--grid)" stroke-width="1.4"/>')
        else:
            add(f'<circle cx="{lx + 6:.1f}" cy="{ly:.1f}" r="4.2" fill="none" '
                f'stroke="var(--bad)" stroke-width="1.8"/>')
        text(lx + 16, ly + 3.5, lab, "mut", 9)
        ly += 16
    cols = (14, 120, 210, 330)
    rowbox(x, y + h - 112, w, cols,
           ("量", "重构", "真值 / 参考", "钉住"),
           [((("q₉₅"), "4.12", "—", "4.05"), ""),
            ((("l_i(3)"), "18.06", "先验前 21.30", "—"), "unk"),
            ((("I_p"), "398 kA", "400 kA（等式约束）", "—"), "")])


def a_channels(x, y, w, h):
    """⑤ 逐道残差."""
    top = panel(x, y, w, h, "逐道残差（磁通环 / 磁探针）", 5, "加权 χ² 就是这张表")
    cols = (14, 52, 118, 186, 250, 304, 358)
    rows = ((("✓", "FL-03", "0.412", "0.409", "+0.003", "0.28", "1.0"), ""),
            (("✓", "FL-07", "0.288", "0.291", "−0.003", "0.31", "1.0"), ""),
            (("✗", "FL-11", "0.104", "0.161", "−0.057", "4.90", "0.0"), "bad"),
            (("✓", "MP-21", "0.0182", "0.0180", "+0.0002", "0.19", "0.6"), ""),
            (("*", "MP-34", "—", "—", "—", "—", "卷宗不用"), "unk"))
    rowbox(x, top + 16, w, cols,
           ("用", "通道", "实测", "重构", "Δ", "wΔ", "权重"), list(rows))
    note(x + 14, top + 132,
         ["★标 * 的是卷宗自己不用的道。这张表打不开它们——用一个复选框",
          "  推翻一次标定决定，不是这张表的职权。",
          "★同一炮的原始探针读数与「交付重构的通道值」不一致时，",
          "  那个不一致本身也是一次测量，页面并排给出而不选一个。"])
    yy = top + 200
    text(x + 14, yy, "后验（误差棒）· 抽哪几样", "mut", 9.5)
    cx = x + 14
    for s, on in (("压强 σ", True), ("磁通环 σ", True), ("线圈相对 σ", True),
                  ("拟合基阶数 ±1", False), ("自洽外环", False)):
        cx += chip(cx, yy + 6, s, "chip-on" if on else "chip", 9.3) + 5
    yy += 40
    ax = Axes(x + 14, yy + 12, w - 28, 56, (0, 5), (3.86, 4.42))
    for i, (v, s) in enumerate(((4.10, 0.09), (4.12, 0.10), (4.16, 0.14),
                                (4.08, 0.08), (4.13, 0.11))):
        px = ax.px(i + 0.5)
        line(px, ax.py(v - s), px, ax.py(v + s), "lcfs")
        handle(px, ax.py(v), 3.2)
    text(x + 14, yy + 6, "q₉₅ 后验 · 200 成员", "mut", 9)
    note(x + 14, y + h - 46,
         ["★带的含义完全由「抽哪几样」决定：这不是「所有输入的不确定度」，",
          "  而是「这几样只知道到 σ」。诊断几何、装置描述与模型本身都不在里面。",
          "★自洽外环那一格是灰的——闭环已经关上，后验却还没抽它（G-5）。"])


def a_profilefit(x, y, w, h):
    """⑥ 栏一 · 剖面拟合."""
    top = panel(x, y, w, h, "栏一 · 剖面拟合（GCV 选阶）", 6, "一次内核调用")
    gw = (w - 36) / 2
    gh = h - 150
    ax = Axes(x + 14, top + 22, gw, gh, (0, 1), (0, 3.6))
    fit = lambda r: 3.0 * (1 - r ** 2) ** 1.4 + 0.2                # noqa: E731
    ax.plot([(i / 40, fit(i / 40)) for i in range(41)], "prof")
    for i, r in enumerate((0.05, 0.18, 0.31, 0.44, 0.58, 0.71, 0.86, 0.96)):
        v = fit(r) * (1.0 + 0.06 * math.sin(9.1 * i))
        handle(ax.px(r), ax.py(v), 2.8)
        line(ax.px(r), ax.py(v * 0.92), ax.px(r), ax.py(v * 1.08), "grid")
    text(x + 14, top + 19, "T_e(ψ̄)：点是数据，线是拟合", "mut", 9)
    #: GCV: steep on the under-fitting side, then FLAT — that flatness is the
    #: point the caption makes, so the curve has to actually be flat.
    gcv = lambda o: 0.30 + 0.72 * math.exp(-1.7 * (o - 2))  # noqa: E731
    ax2 = Axes(x + 22 + gw, top + 22, gw, gh, (2, 9), (0, 1.15))
    ax2.plot([(2 + 7 * i / 60, gcv(2 + 7 * i / 60)) for i in range(61)],
             "prof")
    handle(ax2.px(5), ax2.py(gcv(5)), 3.4)
    text(ax2.px(5), ax2.py(gcv(5)) - 8, "选中：5 阶", "mut", 8.6, "middle")
    text(x + 22 + gw, top + 19, "GCV 分数 vs 阶数", "mut", 9)
    text(x + 22 + gw + gw / 2, top + gh + 38,
         "★曲线平坦＝这些阶几乎一样好，", "mut", 8.8, "middle")
    text(x + 22 + gw + gw / 2, top + gh + 50,
         "此时「选中的阶」不承重。", "mut", 8.8, "middle")
    note(x + 14, y + h - 38,
         ["★「由卷宗剖面重采样」那一档是合成的，它不是测量：一份重采样的",
          "  剖面若以数据的身份回到拟合里，就是这一页在拟合自己的假设（P-6）。",
          "★发布到页面总线上不会唤醒读它的那条栏——今天要手动再跑一次（G-2）。"])


def a_recon_profiles(x, y, w, h):
    """⑦ 重构剖面 — what the fit actually produced, split into its parts."""
    top = panel(x, y, w, h, "重构剖面（拟合的产物，不是输入）", 7,
                "自举 · 欧姆 · 拟合三部分")
    cw, ch = (w - 36) / 2, (h - 168) / 2
    specs = (("q(ψ̄)", (lambda r: 0.95 + 3.4 * r ** 2,)),
             ("p(ψ̄) [kPa]", (lambda r: 22.0 * (1 - r ** 1.8) + 0.5,)),
             ("⟨j_φ⟩ · j_bs（虚）",
              (lambda r: 1.15 * (1 - r ** 2) ** 1.6 + 0.03,
               lambda r: 0.42 * r * (1 - r ** 2) ** 0.6)),
             ("p′(ψ̄) · FF′（虚）", (lambda r: 1.5 * (1 - r) ** 1.2,
                                    lambda r: 1.1 * (1 - r) ** 2.0,)))
    for i, (lab, fns) in enumerate(specs):
        minifig(x + 14 + (i % 2) * (cw + 8), top + 20 + (i // 2) * (ch + 24),
                cw, ch, lab, list(fns))
    note(x + 14, y + h - 66,
         ["★自举—欧姆—拟合三者之间的自洽闭环已经关上（外环收敛后 ⟨j·B⟩ 与",
          "  ⟨j_φ⟩ 的逐面换算才成立），但后验不抽这个外环——误差棒说的是",
          "  抽到的那几样，不是自洽迭代的不确定度。",
          "★这四张图是拟合的产物：把它们当作独立测量再喂回拟合，就是这一页",
          "  在拟合自己的假设。"])


def a_bus(x, y, w, h):
    """⑧ 栏间怎么相接 — the page bus, and the wake it does not do."""
    top = panel(x, y, w, h, "栏间怎么相接（页面总线）", 8, "publish 不唤醒读者")
    bw = (w - 28 - 3 * 6) / 4
    names = ("剖面拟合", "平衡反演", "时间序列", "批处理队列")
    for i, nm in enumerate(names):
        px = x + 14 + i * (bw + 6)
        rect(px, top + 16, bw, 26, "chip-on" if i == 1 else "chip", rx=5)
        text(px + bw / 2, top + 33, nm, "lbl", 9.8, "middle")
        if i:
            line(px - 6, top + 29, px, top + 29, "reg-fb")
    text(x + 14, top + 60, "publish → take：剖面 → 动理学约束 → 逐片 → 队列",
         "mut", 9.3)
    note(x + 14, top + 78,
         ["★注册顺序就是运行顺序，也是依赖顺序：一条栏读的是上一条栏发布的东西。",
          "★发布不唤醒读者——今天要手动再跑一次那条栏。实测：重新拟合剖面后",
          "  等着，那句提示逐字不变地留在原处，永远（G-2）。",
          "★四条栏共用一条状态行：状态行第一句先说话的是哪一条栏。"])


def a_series(x, y, w, h):
    """⑦ 时间序列 + ⑧ 批处理队列（底栏两块）."""
    cw = (w - 10) * 0.58
    top = panel(x, y, cw, h, "栏三 · 时间序列（逐片完整重构，不插值）", "⑨",
                "卷宗只带一片：这是关于卷宗的事实")
    gw = (cw - 40) / 3
    for i, (lab, fn) in enumerate((
            ("I_p [kA]", lambda t: 380 + 22 * t),
            ("q₉₅", lambda t: 4.4 - 0.10 * t),
            ("χ² / dof", lambda t: 1.2 + 0.35 * math.sin(1.7 * t)))):
        px = x + 14 + i * (gw + 6)
        ax = Axes(px, top + 22, gw, h - 92, (0, 5),
                  (0, 460) if i == 0 else ((3.6, 4.8) if i == 1 else (0, 2.4)))
        for k in range(6):
            tt = k
            handle(ax.px(tt), ax.py(fn(tt)), 2.8)
        ax.plot([(k, fn(k)) for k in range(6)], "tick-i")
        text(px + 2, top + 19, lab, "mut", 9)
    note(x + 14, y + h - 34,
         ["★时片之间不插值：一条中间是插出来的 q₉₅ 曲线，画的是插值而不是放电。",
          "★逐道跨时片标定：因子在整炮里稳定的道是标定不准，因子飘的道是噪声大——",
          "  这是一个时片给不出的东西。"])
    bx = x + cw + 10
    bw = w - cw - 10
    top2 = panel(bx, y, bw, h, "栏四 · 批处理队列", "⑩", "三态自报")
    cols = (14, 100, 168, 250)
    rowbox(bx, top2 + 16, bw, cols, ("炮号 @ 时刻", "状态", "I_p 拟合", "未解出的原因"),
           [(("#137985 @ 4.0", "已收敛", "398 kA", "—"), ""),
            (("#137985 @ 1.2", "未解出", "—", "判据 ②：一团电流丝"), "bad"),
            (("#165704 @ 3.9", "未解出", "—", "法方程奇异"), "bad"),
            (("#165704 @ 5.9", "未运行", "—", "—"), "unk")])
    note(bx + 14, y + h - 46,
         ["★整条队列用的是「平衡反演」栏在开跑那一刻的那套设定——",
          "  一张各行设定不同的表，比较的不是任何东西。",
          "★无人盯着的一趟最容易把「求解器返回了」读成「解出来了」，",
          "  所以每一行自报三态之一。"])


def build_analysis() -> str:
    out.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H_ANALYSIS}" width="{W}" height="{H_ANALYSIS}" '
        f'role="img" aria-label="fylite 实验分析页界面概念图">')
    add("<title>fylite 实验分析页 — 界面概念图</title>")
    add(f"<style>{STYLE}</style>")
    rect(0, 0, W, H_ANALYSIS, "bg", rx=0)
    app_header("fylite · 实验分析 (Experiment Analysis)", bars=ANALYSIS_BARS,
               chips=("装置：EAST ▾",),
               badge="四条栏 · 一条状态行 · 一条页面总线", bx=M + 356)
    lw, mw = 316, 448
    rw = W - 2 * M - lw - mw - 20
    a_source(M, 68, lw, 186)
    a_constraints(M, 262, lw, 300)
    a_verdict(M, 570, lw, 358)
    a_cross(M + lw + 10, 68, mw, 420)
    a_channels(M + lw + 10, 496, mw, 432)
    a_profilefit(M + lw + mw + 20, 68, rw, 300)
    a_recon_profiles(M + lw + mw + 20, 376, rw, 300)
    a_bus(M + lw + mw + 20, 684, rw, 244)
    a_series(M, 940, W - 2 * M, 210)
    text(M + 2, H_ANALYSIS - 12,
         "概念图（非截图）：面板取自 app/pages/analysis.html 的实际分组，"
         "曲线与残差为示意；引用的实测数字见 FYL-DESIGN-10 正文。", "mut", 9.5)
    add("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 图六：装置数据页
# --------------------------------------------------------------------------- #
def d_gateway(x, y, w, h):
    """① 数据网关."""
    top = panel(x, y, w, h, "数据网关", 1, "只读 · 六个端点", "badge-ok")
    field(x + 14, top + 12, w - 100, "mdsip 服务器", "202.127.204.12:8000")
    rect(x + w - 78, top + 24, 64, 19, "btn", rx=4)
    text(x + w - 46, top + 37.5, "切过去", "lbl", 10, "middle")
    yy = top + 58
    rect(x + 14, yy, w - 28, 20, "badge-ok", rx=6)
    text(x + 22, yy + 14, "网关在：127.0.0.1:8100 · 上限 20 000 点 / 次",
         "ok-t", 9.4)
    yy += 28
    rect(x + 14, yy, w - 28, 20, "stale", rx=6)
    text(x + 22, yy + 14,
         "没有网关。这一页当作静态文件打开时不会有数据。", "stalet", 9.4)
    note(x + 14, y + h - 30,
         ["★没有网关时页面印出启动它的那条命令，而不是画一条空曲线——",
          "  失败方式教给读者的东西，和成功方式一样多（P-10）。"])


def d_shot(x, y, w, h):
    """② 树与炮号."""
    top = panel(x, y, w, h, "树与炮号", 2)
    fw = (w - 28 - 12) / 3
    field(x + 14, top + 12, fw, "树", "east ▾")
    field(x + 20 + fw, top + 12, fw, "炮号", "137985")
    rect(x + 26 + 2 * fw, top + 24, fw, 19, "chip-on", rx=4)
    text(x + 26 + 2.5 * fw, top + 37.5, "打开", "lbl", 10, "middle")
    cx = x + 14
    for s, on in (("上一炮", False), ("下一炮", False), ("最新", True),
                  ("叠加这一炮", False)):
        cx += chip(cx, top + 54, s, "chip-on" if on else "chip", 9.4) + 5
    note(x + 14, y + h - 30,
         ["★「上一炮 / 下一炮」只走一格，不替你跳过没数的炮号；",
          "  「最新」是这一行里唯一要问服务器的一个（`current_shot`）。"])


def d_status(x, y, w, h):
    """③ 状态行 — six cells, each printing where it came from."""
    top = panel(x, y, w, h, "状态行（六格，各自报出处）", 3)
    cells = (("炮号", "137985", "你给的"),
             ("I_p", "398 kA", "\\PCRL01 · Rogowski"),
             ("放电时长", "6.1 s", "本页自己的规矩，非站点定义"),
             ("B_t", "1.80 T", "\\EFIT_EAST…:BCENTR"),
             ("I_t", "8.6 kA", "\\TOP.T2:TFP（不是 B_t）"),
             ("日期", "2019-11-06", "TIME_INSERTED，记录写下的时刻"))
    cw = (w - 28 - 12) / 3
    for i, (lab, val, src) in enumerate(cells):
        px = x + 14 + (i % 3) * (cw + 6)
        py = top + 12 + (i // 3) * 46
        rect(px, py, cw, 40, "input", rx=4)
        text(px + 6, py + 14, lab, "mut", 9)
        text(px + 6, py + 27, val, "lbl", 10.5)
        text(px + 6, py + 37, src, "mut", 7.6)
    note(x + 14, y + h - 30,
         ["★`\\PCRL01` 是 Rogowski 读数，不等于等离子体电流：本仓在 #137985",
          "  平顶实测它与重构的 `cpasma` 差 1.9 %。先看它对，做等式约束错。"])


def d_zero(x, y, w, h):
    """④ 关键零级量."""
    top = panel(x, y, w, h, "关键零级量（每个自带它的树）", 4)
    cx, yy = x + 14, top + 16
    for s in ("I_p · pcs_east", "V_loop · east", "W_mhd · efit", "n̄_e · pcs",
              "β_p · efit", "l_i · efit", "q₉₅ · efit", "B_t · efit",
              "I_t · east"):
        wch = tw(s, 9.2) + 16
        if cx + wch > x + w - 14:
            cx, yy = x + 14, yy + 23
        cx += chip(cx, yy, s, "chip", 9.2) + 5
    note(x + 14, y + h - 30,
         ["★节点路径不说明它住在哪棵树上，而那个映射推不出来——`east` 对",
          "  `\\PCRL01` 答 `%TREE-W-NNF`。所以每个量各自带着自己的树（P-18）。"])


def d_browse(x, y, w, h):
    """⑤ 节点浏览 + 目录."""
    top = panel(x, y, w, h, "节点浏览 · 诊断目录", 5, "字节数≠取得到")
    text(x + 14, top + 14, "\\EAST::TOP  ›  MAGNETICS  ›  ", "mut", 9.5)
    cols = (14, 210, 300)
    rowbox(x, top + 32, w, cols, ("节点", "用途", "字节数"),
           [(("MP01", "signal", "48 kB"), ""),
            (("MP02", "signal", "48 kB"), ""),
            (("MP03", "signal", "0"), "unk"),
            (("FLUX_LOOP", "structure", "—"), ""),
            (("PCRL01（标签，须直接给路径）", "signal", "62 kB"), "sel")])
    yy = top + 150
    text(x + 14, yy, "诊断目录：73 项诊断 · 376 路信号（随包）", "mut", 9.4)
    note(x + 14, yy + 16,
         ["★空节点是灰的，不是隐藏的：一个把另外 58 道藏起来的浏览器，",
          "  等于在回答「这台装置有 21 个探针」——那是假的，而且从页面上",
          "  证伪不了（#137985 存了 79 个磁探针里的 21 个）。",
          "★目录说某路信号在这台机器上存在，从不说这一炮记了它。",
          "★字节数为零的一定取不到；不为零的也未必取得到——真取不到时",
          "  右边如实报错，不给一条空曲线。"])


def d_figs(x, y, w, h):
    """⑥ 信号时序 — the page's centre of gravity."""
    top = panel(x, y, w, h, "信号时序", 6, "抽稀，不是归约", "badge")
    cx = x + 14
    for s, on in (("取回", True), ("采样：自动 ▾", False), ("列数：2 ▾", False),
                  ("整炮", False), ("导出 JSON", False)):
        cx += chip(cx, top + 12, s, "chip-on" if on else "chip", 9.4) + 5
    gw = (w - 36) / 2
    gh = (h - 196) / 2
    traces = (("\\PCRL01 [kA]", lambda t: 420 * ip_of(t) / 400, (0, 470),
               "12 812 点 · 每 9 个取一个 · 画了 1 424 点"),
              ("\\VP1 [V]", lambda t: 3.4 * pohm_of(t), (0, 6),
               "12 812 点 · 每 9 个取一个"),
              ("\\DFSDEV [10¹⁹ m⁻³]", ne_of, (0, 6),
               "6 406 点 · 整炮，未抽稀"),
              ("\\WMHD [kJ]", lambda t: 420 * bn_of(t) / 1.7, (0, 460),
               "取不到：本炮该节点存的是一条引到别处的表达式"))
    for i, (lab, fn, yr, cap) in enumerate(traces):
        px = x + 14 + (i % 2) * (gw + 8)
        py = top + 46 + (i // 2) * (gh + 44)
        ax = Axes(px, py, gw, gh, (T_BD, T_END), yr)
        if i == 3:
            rect(px, py, gw, gh, "rowbad", rx=3)
            text(px + gw / 2, py + gh / 2, "取不到", "bad-t", 11, "middle")
        else:
            ax.plot(sample(fn, 90), "ip" if i == 0 else
                    ("prof" if i == 1 else "ne"))
            if i == 0:
                for k in range(0, 91, 6):
                    tt = T_BD + k * (T_END - T_BD) / 90
                    handle(ax.px(tt), ax.py(fn(tt)), 1.8)
        text(px + 2, py - 3, lab, "mut", 9)
        text(px + 2, py + gh + 12, cap, "bad-t" if i == 3 else "mut", 8.6)
    note(x + 14, y + h - 46,
         ["★画出来的是每隔 N 个取一个样点，不是均值、不是 min/max 包络——",
          "  比步长更窄的尖峰不在这条曲线里。图注里的「抽稀」二字就是这个意思。",
          "★在图上拖出一个窗：点数几乎不变，步长塌下来——采样率跟着窗走，",
          "  不跟着整炮走；双击回到整炮。叠加的炮同窗重取，两炮共用一个步长。"])


def d_table(x, y, w, h):
    """⑦ 读数表."""
    top = panel(x, y, w, h, "读数", 7)
    cols = (14, 92, 250, 330, 396, 470, 545, 620)
    rowbox(x, top + 16, w, cols,
           ("炮号", "树", "节点", "单位", "样点数", "步长", "最小 / 最大",
            "时间跨度"),
           [(("137985", "pcs_east", "\\PCRL01", "kA", "12 812", "0.78 ms",
              "−2 / 421", "0–10.0 s"), ""),
            (("137985", "east", "\\VP1", "V", "12 812", "0.78 ms",
              "−0.4 / 5.8", "0–10.0 s"), ""),
            (("137985", "efit_east", "\\WMHD", "—", "—", "—", "—",
              "取不到"), "bad")])
    note(x + 14, y + h - 30,
         ["★步长是这张表里最该看的一列：它是这条曲线的采样率，",
          "  也是「比它更窄的东西你在图上看不见」的那个数。"])


def d_pick(x, y, w, h):
    """⑧ 已选信号 · 直接路径 · 工作区."""
    cw = (w - 20) / 3
    top = panel(x, y, cw, h, "已选信号（上限 6 路）", 8)
    for i, (s, cls) in enumerate((("\\PCRL01", "c1"), ("\\VP1", "c2"),
                                  ("\\DFSDEV", "c3"))):
        ry = top + 20 + i * 22
        line(x + 14, ry, x + 30, ry, cls)
        text(x + 36, ry + 3.5, s, "lbl", 9.6)
    text(x + 14, y + h - 14, "全部去掉", "mut", 9)
    bx = x + cw + 10
    panel(bx, y, cw, h, "直接给节点路径", None)
    field(bx + 14, y + 40, cw - 76, "标签 / 路径", "\\PCRL01")
    rect(bx + cw - 56, y + 52, 42, 19, "btn", rx=4)
    text(bx + cw - 35, y + 65.5, "加入", "lbl", 10, "middle")
    note(bx + 14, y + h - 34,
         ["★标签不是任何节点的成员——", "  一层层展开永远走不到它。"])
    cx2 = bx + cw + 10
    panel(cx2, y, cw, h, "工作区", None)
    for i, s in enumerate(("存工作区", "读工作区")):
        rect(cx2 + 14 + i * 84, y + 44, 76, 20, "btn", rx=4)
        text(cx2 + 52 + i * 84, y + 58, s, "lbl", 10, "middle")
    note(cx2 + 14, y + h - 34,
         ["★存的是设定，不存样点——这一页不是数据仓库；",
          "  存了样点的工作区就是一份没有出处的数据副本。"])


def d_hosts(x, y, w, h):
    """⑨ 两个宿主，一组端点."""
    top = panel(x, y, w, h, "两个宿主，一组端点（页面是同一份）", 9,
                "守卫两侧各做一遍")
    eps = ("/api/health", "/api/shot", "/api/tree", "/api/node",
           "/api/signal", "/api/measurements")
    ew = (w - 28 - 5 * 6) / 6
    for i, s in enumerate(eps):
        px = x + 14 + i * (ew + 6)
        rect(px, top + 46, ew, 24, "chip-on" if i == 4 else "chip", rx=6)
        text(px + ew / 2, top + 61, s, "lbl", 9.6, "middle")
    hx = x + 14
    #: ★一个宿主：Node 网关 `app/server/` 2026-09-01 退役，`/api/*` 只剩这一份。
    for s, sub in (("单文件宿主 `rust/…/bin/app/api.rs`",
                    "fylite-app --mdsip 127.0.0.1:8000"),
                   ("离线回放 `app/tests/_mdsip-replay.mjs`",
                    "夹具 fixtures/mdsip-east.json（真机录的帧）")):
        rect(hx, top + 12, (w - 34) / 2, 26, "card-back", rx=5)
        text(hx + 10, top + 22, s, "lbl", 9.8)
        text(hx + 10, top + 33, sub, "mut", 8.4)
        hx += (w - 34) / 2 + 6
    for i in range(2):
        x0 = x + 14 + (w - 34) / 4 + i * ((w - 34) / 2 + 6)
        line(x0, top + 38, x0, top + 46, "reg-fb")
    note(x + 14, top + 82,
         ["★没有取表达式的端点，因为没有取表达式的客户端方法——每个 TDI 串"
          "都由校验过的节点路径与整数拼出（FYL-DESIGN-06 §5）。",
          "★树名、节点路径与整数在网关里检一遍、客户端里再检一遍；离开回环"
          "地址时先检来访地址，403 在第一个字节之前。",
          "★没给 `--mdsip` 时 `/api/health` 照答，只是 `ok:false` 并带一句为什么"
          "——这比 404（面板凭空消失）教给读者的多。"])


def build_data() -> str:
    out.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H_DATA}" '
        f'width="{W}" height="{H_DATA}" role="img" '
        f'aria-label="fylite 装置数据页界面概念图">')
    add("<title>fylite 装置数据页 — 界面概念图</title>")
    add(f"<style>{STYLE}</style>")
    rect(0, 0, W, H_DATA, "bg", rx=0)
    app_header("fylite · 装置数据 (Device Data)",
               chips=("网关：127.0.0.1:8100 ▾", "树：east ▾", "炮号：137985"),
               badge="只读 · 无内核 · 无 worker · 不留存样点",
               bx=M + 330)
    lw = 400
    rw = W - 2 * M - lw - 10
    d_gateway(M, 68, lw, 184)
    d_shot(M, 260, lw, 150)
    d_status(M, 418, lw, 176)
    d_zero(M, 602, lw, 140)
    d_browse(M, 750, lw, 300)
    d_figs(M + lw + 10, 68, rw, 560)
    d_table(M + lw + 10, 636, rw, 200)
    d_pick(M + lw + 10, 844, rw, 192)
    d_hosts(M, 1048, W - 2 * M, 180)
    text(M + 2, H_DATA - 12,
         "概念图（非截图）：面板取自 app/pages/data.html 的实际分组；曲线为示意，"
         "样点数与步长为示例值。引用的实测数字见 FYL-DESIGN-10 正文。", "mut", 9.5)
    add("</svg>")
    return "\n".join(out) + "\n"



def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", default="docs/figures",
                    help="output directory for both figures")
    a = ap.parse_args()
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    #: ★`pulse-design-page.svg` retired 2026-09-01.  It drew the page at
    #: STRUCTURE level — the four panel classes and the swap slot — which is
    #: what `FYL-DESIGN-09` §页面的构造 already says in words, and its ①–⑥
    #: callouts were a second numbering over the same panels the design-mode
    #: figure numbers ①–⑧.  Two drawings and two numberings of one page is the
    #: redundancy the 2026-09-01 rewrite of that document removed.
    for name, fn in (("pulse-design-mode.svg", build),
                     ("pulse-design-sim.svg", build_sim),
                     ("model-page.svg", build_model),
                     ("analysis-page.svg", build_analysis),
                     ("data-page.svg", build_data)):
        p = d / name
        p.write_text(fn(), encoding="utf-8")
        print(f"wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
