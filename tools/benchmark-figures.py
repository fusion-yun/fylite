#!/usr/bin/env python3
"""逐条记录的**余量图**：每条判据离它的带还有多远，对数轴。

★★**为什么先画这一张**：这一轮至少三处贴着带跑——演化的驱动复现余量 0.2 %、
孪生的 q0 余量 0.05 %、B-14 的边界最大值——而它们在表上与余量一千倍的判据**长得一样**，
全是绿的。那三句话现在只活在各自记录的 caveat 里，得有人读到才知道。
一张按余量排的对数图，把「岌岌可危的绿」和「宽裕的绿」分开，这是任何一张表都答不了的。

★**余量的算法由 `bound` 决定**，缺它会算反：

    upper     实测须 <= 容差      余量 = 容差 / 实测
    lower     实测须 >= 容差      余量 = 实测 / 容差
    identity  须相等 / 为真       无余量可言，画成一个标记
    reading   没有带，本就不判     不画

★★**手写 SVG，不用 matplotlib**：仓库的硬依赖只有 numpy，文档重建不该拖进一整套绘图栈；
文本 SVG 的 diff 可读（这些是入库的生成件）。★**颜色写字面值，不用 CSS 变量**——
`var(--x)` 只在浏览器里解析，librsvg（任何 SVG->PNG/PDF 管线）解析不了，整张图会渲成全黑，
而在文本编辑器里看是好的。这条是旧册留下的教训，原样承下来。
★取中间调的颜色，浅色与深色主题下都读得出；背景留空（透明），跟着主题走。

用法::

    python tools/benchmark-figures.py            # 写 docs/benchmark/figures/*.svg
    python tools/benchmark-figures.py --check    # 只核对是否最新（门用），不写盘
"""
from __future__ import annotations

import argparse
import html
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BM = ROOT / "docs" / "benchmark"
FIG = BM / "figures"

#: 中间调：白底与深底都读得出
INK = "#8a8a8a"       # 轴、刻度、说明
TEXT = "#9a9a9a"      # 标签
PASS = "#2e9e4f"      # 成立侧
FAIL = "#d64545"      # 不成立侧
TIGHT = "#e0a030"     # 余量 < 2 倍：绿，但不是宽裕的绿
MARK = "#6f8fbf"      # 恒等档的标记

LO, HI = 1e-2, 1e3    # 对数轴显示范围（倍）
W, LEFT, RIGHT = 900, 380, 40
ROW, TOP, BOT = 28, 54, 46
SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def headroom(f: dict, tol) -> float | None:
    """余量倍数：>1 在成立那一侧，<1 越界。"""
    m, b = f.get("measured_deviation"), f.get("bound")
    if m is None or tol in (None, 0) or b not in ("upper", "lower"):
        return None
    m = abs(float(m))
    if b == "upper":
        return math.inf if m == 0 else float(tol) / m
    return 0.0 if float(tol) == 0 else m / float(tol)


def x_of(v: float) -> float:
    v = min(max(v, LO), HI)
    return LEFT + (math.log10(v) - math.log10(LO)) / (math.log10(HI) - math.log10(LO)) * (W - LEFT - RIGHT)


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def rows_of(rec: dict) -> list[dict]:
    by_cid = {c["id"]: c for c in rec.get("criteria") or []}
    out = []
    for f in rec.get("findings") or []:
        c = by_cid.get(f.get("criterion"))
        tol = (c or {}).get("tolerance", {}).get("numeric_value")
        label = (c or {}).get("quantity_label") or f.get("title", "-")
        out.append({"label": label, "bound": f.get("bound"), "verdict": f.get("verdict"),
                    "h": headroom(f, tol)})
    return out


def svg(rec: dict) -> str:
    rid = rec["id"].split("/")[-1]
    rows = rows_of(rec)
    h = TOP + ROW * len(rows) + BOT
    L = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="img" '
         f'aria-label="{esc(rid)}: 每条判据离它的带还有多远">',
         f"<title>{esc(rid)} - 判据余量</title>",
         '<desc>横轴为余量倍数（对数）。1 倍处是判据本身：右侧成立，左侧越界。'
         '恒等档没有余量可言，画成标记。</desc>',
         f'<text x="8" y="22" font-size="14" font-weight="600" fill="{TEXT}">'
         f'判据余量 —— 离带还有多远（对数轴，1 倍即判据本身）</text>']

    e0, e1 = int(math.log10(LO)), int(math.log10(HI))
    for e in range(e0, e1 + 1):
        x = x_of(10.0 ** e)
        strong = (e == 0)
        dash = "" if strong else ' stroke-dasharray="2 4"'
        L.append(f'<line x1="{x:.1f}" y1="{TOP - 14}" x2="{x:.1f}" y2="{h - BOT + 6}" '
                 f'stroke="{INK}" stroke-width="{1.4 if strong else 0.5}"{dash} '
                 f'opacity="{0.9 if strong else 0.45}"/>')
        lab = "1x" if e == 0 else ("10" + ("⁻" if e < 0 else "") + SUP[abs(e)] + "x")
        L.append(f'<text x="{x:.1f}" y="{h - BOT + 22}" font-size="11" fill="{INK}" '
                 f'text-anchor="middle">{lab}</text>')
    L.append(f'<text x="{x_of(1.0):.1f}" y="{TOP - 20}" font-size="11" fill="{INK}" '
             f'text-anchor="middle">judgement</text>')

    for i, r in enumerate(rows):
        y = TOP + ROW * i + ROW / 2
        lab = r["label"]
        if len(lab) > 30:
            lab = lab[:29] + "…"
        L.append(f'<text x="{LEFT - 10}" y="{y + 4:.1f}" font-size="12" fill="{TEXT}" '
                 f'text-anchor="end">{esc(lab)}</text>')
        hv = r["h"]
        if hv is None:
            tag = {"identity": "恒等：" + ("成立" if r["verdict"] == "pass" else "不成立"),
                   "reading": "读数：不判"}.get(r["bound"], "无数值")
            col = MARK if (r["bound"] == "identity" and r["verdict"] == "pass") else INK
            L.append(f'<circle cx="{x_of(1.0):.1f}" cy="{y:.1f}" r="4" fill="{col}"/>')
            L.append(f'<text x="{x_of(1.0) + 12:.1f}" y="{y + 4:.1f}" font-size="11" '
                     f'fill="{INK}">{esc(tag)}</text>')
            continue
        if hv == math.inf:
            L.append(f'<line x1="{x_of(1.0):.1f}" y1="{y:.1f}" x2="{W - RIGHT:.1f}" y2="{y:.1f}" '
                     f'stroke="{PASS}" stroke-width="7" stroke-linecap="round" opacity="0.85"/>')
            L.append(f'<text x="{W - RIGHT - 4:.1f}" y="{y - 8:.1f}" font-size="11" fill="{PASS}" '
                     f'text-anchor="end">精确零（余量无穷）</text>')
            continue
        if hv == 0.0:
            #: ★下限判据而实测为零：不是「差一点」，是**一条都没有**。
            #: 画成贯穿左侧的红条，别让它缩成一个看不见的点。
            L.append(f'<line x1="{LEFT:.1f}" y1="{y:.1f}" x2="{x_of(1.0):.1f}" y2="{y:.1f}" '
                     f'stroke="{FAIL}" stroke-width="7" stroke-linecap="round" opacity="0.85"/>')
            L.append(f'<text x="{LEFT + 4:.1f}" y="{y - 8:.1f}" font-size="11" fill="{FAIL}">'
                     f'\u5b9e\u6d4b\u4e3a\u96f6\uff08\u4e0b\u9650\u5224\u636e\uff09</text>')
            continue
        col = FAIL if hv < 1 else (TIGHT if hv < 2 else PASS)
        x0, x1 = x_of(min(1.0, hv)), x_of(max(1.0, hv))
        L.append(f'<rect x="{x0:.1f}" y="{y - 7:.1f}" width="{max(x1 - x0, 2):.1f}" height="14" '
                 f'rx="3" fill="{col}" opacity="0.85"/>')
        txt = ("%.3gx" % hv) if hv >= 1 else ("超出 %.3g 倍" % (1 / hv))
        ax, anchor = (x1 + 6, "start") if hv >= 1 else (x0 - 6, "end")
        L.append(f'<text x="{ax:.1f}" y="{y + 4:.1f}" font-size="11" fill="{col}" '
                 f'text-anchor="{anchor}">{esc(txt)}</text>')

    L.append(f'<text x="8" y="{h - 8}" font-size="10.5" fill="{INK}">'
             f'★绿而窄（&lt; 2 倍）另着色：'
             f'它与余量一千倍的判据在表上长得一样，'
             f'在这里不一样。　'
             f'生成：tools/benchmark-figures.py</text>')
    L.append("</svg>")
    return "\n".join(L) + "\n"




# ───────────────────────────────── 对标曲线本身：等高线叠画 与 剖面叠画

#: ★★**这两张图与余量图答的不是同一个问题**：余量图答「离判据还有多远」（元信息），
#: 这两张答「**差在哪儿**」（数据本身）。一个标量说不出偏差是整体平移还是局部变形，
#: 也说不出它落在芯部还是边缘——那得把两侧画在一起才看得见。
CURVE_COLORS = {"analytic": "#6f8fbf", "fylite_129": "#d64545", "chease_ns80": "#2e9e4f"}
CURVE_DASH = {"analytic": "", "fylite_129": ' stroke-dasharray="6 4"', "chease_ns80": ' stroke-dasharray="1 5"'}
CURVE_ZH = {"analytic": "Solov'ev 闭式解", "fylite_129": "fylite 129²", "chease_ns80": "CHEASE NS=80"}


def contour_svg(d: dict) -> str:
    """R-Z 面上把三侧的 psi_N 等高线画在一起。"""
    b = d["boundary"]
    rs, zs = b["r"], b["z"]
    r0, r1, z0, z1 = min(rs), max(rs), min(zs), max(zs)
    PAD, W2, TOPB = 0.06, 760, 56
    #: ★等比例：R-Z 面上拉伸纵横比会把形状画歪，而形状正是这张图要说的事
    span_r, span_z = (r1 - r0) * (1 + 2 * PAD), (z1 - z0) * (1 + 2 * PAD)
    plot_w = 430
    scale = plot_w / span_r
    plot_h = span_z * scale
    H2 = TOPB + plot_h + 52
    ox, oy = 44, TOPB
    cr0, cz1 = r0 - (r1 - r0) * PAD, z1 + (z1 - z0) * PAD

    def px(r): return ox + (r - cr0) * scale
    def py(z): return oy + (cz1 - z) * scale

    L = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W2} {H2:.0f}" role="img" '
         f'aria-label="psi_N 等高线：三侧画在一起">',
         '<title>psi_N 等高线 — 对标两侧画在一起</title>',
         '<desc>R-Z 面，等比例。灰色粗线是两侧共同保持的边界轮廓；'
         '五条 psi_N 等值线各由三侧分别给出。</desc>',
         f'<text x="8" y="22" font-size="14" font-weight="600" fill="{TEXT}">'
         f'psi_N 等高线（{", ".join(str(v) for v in d["levels"])}）—— 三侧画在一起</text>']

    poly = " ".join(f"{px(r):.1f},{py(z):.1f}" for r, z in zip(rs, zs))
    L.append(f'<polyline points="{poly}" fill="none" stroke="{INK}" stroke-width="2.4" opacity="0.8"/>')

    for who, levels in d["contours"].items():
        col, dash = CURVE_COLORS.get(who, INK), CURVE_DASH.get(who, "")
        for segs in levels.values():
            for s in segs:
                pts = " ".join(f"{px(r):.1f},{py(z):.1f}" for r, z in zip(s["r"], s["z"]))
                L.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                         f'stroke-width="1.3"{dash} opacity="0.95"/>')
    for who, (ar, az) in d.get("axis", {}).items():
        L.append(f'<circle cx="{px(ar):.1f}" cy="{py(az):.1f}" r="3" fill="{CURVE_COLORS.get(who, INK)}"/>')

    lx, ly = ox + plot_w + 26, TOPB + 14
    for i, who in enumerate(d["contours"]):
        col, dash = CURVE_COLORS.get(who, INK), CURVE_DASH.get(who, "")
        y = ly + i * 22
        L.append(f'<line x1="{lx}" y1="{y}" x2="{lx + 34}" y2="{y}" stroke="{col}" '
                 f'stroke-width="2"{dash}/>')
        L.append(f'<text x="{lx + 42}" y="{y + 4}" font-size="12" fill="{TEXT}">'
                 f'{esc(CURVE_ZH.get(who, who))}</text>')
    L.append(f'<line x1="{lx}" y1="{ly + len(d["contours"]) * 22}" x2="{lx + 34}" '
             f'y2="{ly + len(d["contours"]) * 22}" stroke="{INK}" stroke-width="2.4" opacity="0.8"/>')
    L.append(f'<text x="{lx + 42}" y="{ly + len(d["contours"]) * 22 + 4}" font-size="12" '
             f'fill="{TEXT}">保持的边界（两侧共用）</text>')
    L.append(f'<text x="{lx}" y="{ly + len(d["contours"]) * 22 + 34}" font-size="11" fill="{INK}">'
             f'★三侧在线宽内重合——</text>')
    L.append(f'<text x="{lx}" y="{ly + len(d["contours"]) * 22 + 50}" font-size="11" fill="{INK}">'
             f'**这就是结果**，不是画漏了。</text>')
    L.append(f'<text x="{lx}" y="{ly + len(d["contours"]) * 22 + 66}" font-size="11" fill="{INK}">'
             f'定量见 q 剖面图与判据表。</text>')

    L.append(f'<text x="8" y="{H2 - 10:.0f}" font-size="10.5" fill="{INK}">'
             f'R-Z 等比例　生成：tools/benchmark-figures.py（数据 readings/solovev_curves.json）</text>')
    L.append("</svg>")
    return "\n".join(L) + "\n"


def qprofile_svg(d: dict) -> str:
    """上：两侧的 q(psi_N) 画在一起；下：它们的相对差——差异在这一格才看得见。"""
    q = d.get("q_profile") or {}
    if "x" not in q:
        return ""
    x, a, b = q["x"], q["fylite_129"], q["chease_ns80"]
    rel = [(bb / aa - 1.0) * 100.0 for aa, bb in zip(a, b)]   # CHEASE 相对 fylite，百分比
    W2, OX, RIGHT2 = 900, 66, 26
    H1, H2h, GAP, TOPB = 200, 130, 46, 54
    H = TOPB + H1 + GAP + H2h + 46
    pw = W2 - OX - RIGHT2

    def px(v): return OX + (v - x[0]) / (x[-1] - x[0]) * pw

    qlo, qhi = min(min(a), min(b)), max(max(a), max(b))
    qlo, qhi = qlo - (qhi - qlo) * 0.08, qhi + (qhi - qlo) * 0.08

    def py1(v): return TOPB + (qhi - v) / (qhi - qlo) * H1

    m = max(abs(min(rel)), abs(max(rel))) or 1.0

    def py2(v): return TOPB + H1 + GAP + H2h / 2 - v / (m * 1.15) * (H2h / 2)

    L = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W2} {H}" role="img" '
         f'aria-label="q 剖面：两侧画在一起，以及它们的相对差">',
         '<title>q 剖面 — 两侧画在一起</title>',
         '<desc>上格是两个码各自的 q(psi_N)；下格是它们的相对差（百分比）——'
         '差异在上格看不出来，在下格才看得见。</desc>',
         f'<text x="8" y="22" font-size="14" font-weight="600" fill="{TEXT}">'
         f'q 剖面：两侧画在一起（上），以及它们差多少（下）</text>']

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        xv = x[0] + (x[-1] - x[0]) * frac
        L.append(f'<line x1="{px(xv):.1f}" y1="{TOPB}" x2="{px(xv):.1f}" y2="{TOPB + H1}" '
                 f'stroke="{INK}" stroke-width="0.5" stroke-dasharray="2 4" opacity="0.4"/>')
        L.append(f'<text x="{px(xv):.1f}" y="{TOPB + H1 + 16}" font-size="11" fill="{INK}" '
                 f'text-anchor="middle">{xv:.2f}</text>')
    L.append(f'<text x="{OX + pw / 2:.0f}" y="{H - 10}" font-size="11" fill="{INK}" '
             f'text-anchor="middle">psi_N</text>')
    for v in (qlo, (qlo + qhi) / 2, qhi):
        L.append(f'<text x="{OX - 8}" y="{py1(v) + 4:.1f}" font-size="11" fill="{INK}" '
                 f'text-anchor="end">{v:.3f}</text>')
    L.append(f'<text x="{OX - 8}" y="{TOPB - 8}" font-size="11" fill="{TEXT}" text-anchor="end">q</text>')

    for who, ys in (("fylite_129", a), ("chease_ns80", b)):
        pts = " ".join(f"{px(xx):.1f},{py1(yy):.1f}" for xx, yy in zip(x, ys))
        L.append(f'<polyline points="{pts}" fill="none" stroke="{CURVE_COLORS[who]}" '
                 f'stroke-width="2"{CURVE_DASH[who]}/>')
    for i, who in enumerate(("fylite_129", "chease_ns80")):
        y = TOPB + 14 + i * 20
        L.append(f'<line x1="{OX + 14}" y1="{y}" x2="{OX + 48}" y2="{y}" '
                 f'stroke="{CURVE_COLORS[who]}" stroke-width="2"{CURVE_DASH[who]}/>')
        L.append(f'<text x="{OX + 56}" y="{y + 4}" font-size="12" fill="{TEXT}">'
                 f'{esc(CURVE_ZH[who])}</text>')

    y0 = py2(0.0)
    L.append(f'<line x1="{OX}" y1="{y0:.1f}" x2="{W2 - RIGHT2}" y2="{y0:.1f}" '
             f'stroke="{INK}" stroke-width="1"/>')
    pts = " ".join(f"{px(xx):.1f},{py2(vv):.1f}" for xx, vv in zip(x, rel))
    L.append(f'<polyline points="{pts}" fill="none" stroke="{FAIL}" stroke-width="2"/>')
    L.append(f'<text x="{OX - 8}" y="{py2(m):.1f}" font-size="11" fill="{INK}" '
             f'text-anchor="end">{m:+.3f}%</text>')
    L.append(f'<text x="{OX - 8}" y="{py2(-m):.1f}" font-size="11" fill="{INK}" '
             f'text-anchor="end">{-m:.3f}%</text>')
    L.append(f'<text x="{OX + 14}" y="{TOPB + H1 + GAP - 10}" font-size="12" fill="{TEXT}">'
             f'相对差（CHEASE 对 fylite），最劣 {m:.3f} %</text>')
    L.append(f'<text x="8" y="{H - 26}" font-size="10.5" fill="{INK}">'
             f'★上格两条线肉眼重合——**差异只在下格看得见**。'
             f'★解析 Solov\'ev 没有 q(psi) 闭式，所以这一张比的是两个码，真值一侧只有 q0 那一个点。</text>')
    L.append("</svg>")
    return "\n".join(L) + "\n"


CURVE_DATA = {"eq-forward-solovev-fixed-boundary": "solovev_curves.json"}


def curve_figures() -> dict[pathlib.Path, str]:
    out = {}
    for rid, fname in CURVE_DATA.items():
        p = BM / "readings" / fname
        if not p.is_file():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out[FIG / f"{rid}-contours.svg"] = contour_svg(d)
        q = qprofile_svg(d)
        if q:
            out[FIG / f"{rid}-qprofile.svg"] = q
    return out


def build() -> dict[pathlib.Path, str]:
    out = {}
    for p in sorted((BM / "records").glob("*.jsonld")):
        if p.name == "TEMPLATE.jsonld":
            continue
        out[FIG / f"{p.stem}-headroom.svg"] = svg(json.loads(p.read_text(encoding="utf-8")))
    out.update(curve_figures())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    out = build()
    if a.check:
        stale = [p for p, s in out.items() if not p.is_file() or p.read_text(encoding="utf-8") != s]
        extra = [p for p in FIG.glob("*.svg") if p not in out] if FIG.is_dir() else []
        if stale or extra:
            for p in stale:
                print(f"已过期：{p.relative_to(ROOT)}", file=sys.stderr)
            for p in extra:
                print(f"多余（记录已不在）：{p.relative_to(ROOT)}", file=sys.stderr)
            print("跑 `python tools/benchmark-figures.py` 重写", file=sys.stderr)
            return 1
        print("figures are current")
        return 0
    FIG.mkdir(parents=True, exist_ok=True)
    n = 0
    for p, s in out.items():
        if not p.is_file() or p.read_text(encoding="utf-8") != s:
            p.write_text(s, encoding="utf-8")
            n += 1
    #: ★记录删了，它的图也要跟着走——留下一张没有正本的图是最坏的
    for p in sorted(FIG.glob("*.svg")):
        if p not in out:
            p.unlink()
            print(f"removed {p.relative_to(ROOT)}")
    print(f"wrote {n} / {len(out)} figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
