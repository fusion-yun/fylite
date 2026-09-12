#!/usr/bin/env python3
"""Generate the scenario-chapter figures (`docs/figures/sc-<name>-flow.svg` and
`sc-<name>-page.svg`) from the specs in ``SPECS`` below.

★Why a generator and not hand-drawn SVG.  `FYL-DESIGN-23` W-2 asks every
scenario chapter for an algorithm flow graph and a page mock-up; nine chapters
is eighteen figures, and a hand-drawn figure drifts from its chapter the first
time a stage is renamed.  The spec here is the one place a chapter's stages,
edges and panels are written; the SVG is derived.  The palette and the visual
vocabulary (solid = data edge, dashed = model edge, red = back edge, orange =
comparison, dashed frame = a step with no code today) are the ones the
hand-drawn exemplar `sc-kinetic-flow.svg` established, so the two kinds read
the same.

Usage:  python tools/make-scenario-figures.py [--check]
  --check   regenerate into memory and fail if any file on disk differs.

stdlib only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

STYLE = """
:root { --bg:#f4f5f7; --panel:#ffffff; --fg:#1c2128; --muted:#666f7a; --grid:#d8dce2; --line:#e3e6ea;
  --accent:#1668c8; --lcfs:#d0342c; --alt:#10897a; --warn:#a75909; --sel:#e7f0fb; --head:#eceff3; --wall:#5a6270; --ok:#10897a; }
text { font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,sans-serif; font-size:12.5px; fill:var(--fg); }
.h { font-size:16px; font-weight:600; } .t { font-size:13.5px; font-weight:600; }
.s { font-size:11px; fill:var(--muted); }
.k { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; fill:var(--accent); }
.tag { font-size:10.5px; fill:var(--warn); } .off-t { font-size:11.5px; fill:var(--muted); }
.mono { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; fill:var(--muted); }
.node { fill:var(--panel); stroke:var(--grid); stroke-width:1.2; }
.node-code { fill:var(--panel); stroke:var(--accent); stroke-width:1.4; }
.node-off { fill:var(--panel); stroke:var(--grid); stroke-width:1.2; stroke-dasharray:5 4; }
.doc { fill:var(--sel); stroke:var(--accent); stroke-width:1; }
.crit { fill:#fff7ed; stroke:var(--warn); stroke-width:1; }
.loop { fill:var(--panel); stroke:var(--accent); stroke-width:1.4; }
.edge { fill:none; stroke:var(--wall); stroke-width:1.6; marker-end:url(#a); }
.edge-model { fill:none; stroke:var(--wall); stroke-width:1.6; stroke-dasharray:6 4; marker-end:url(#a); }
.back { fill:none; stroke:var(--lcfs); stroke-width:2; marker-end:url(#ab); }
.gate { fill:none; stroke:var(--warn); stroke-width:1.4; marker-end:url(#aw); }
.panel { fill:var(--panel); stroke:var(--grid); stroke-width:1; } .head { fill:var(--head); stroke:var(--grid); stroke-width:1; }
.btn { fill:none; stroke:var(--grid); stroke-width:1; } .btn-on { fill:var(--accent); } .btn-on-t { fill:#fff; font-weight:600; }
.slider { stroke:var(--grid); stroke-width:3; stroke-linecap:round; } .knob { fill:var(--panel); stroke:var(--accent); stroke-width:1.6; }
.axes { fill:none; stroke:var(--grid); } .grid { stroke:var(--grid); stroke-width:.8; }
polyline { fill:none; stroke-linejoin:round; stroke-linecap:round; }
.c1 { stroke:var(--accent); stroke-width:2; } .c2 { stroke:var(--alt); stroke-width:2; } .c3 { stroke:var(--lcfs); stroke-width:1.6; stroke-dasharray:5 3; }
.badge-ok { fill:none; stroke:var(--ok); } .badge-run { fill:none; stroke:var(--accent); } .badge-stale { fill:none; stroke:var(--warn); }
.ok-t { fill:var(--ok); } .warn-t { fill:var(--warn); } .acc-t { fill:var(--accent); }
.warnbox { fill:#fff7ed; stroke:var(--warn); } .zone { fill:var(--alt); opacity:.10; stroke:var(--alt); stroke-dasharray:3 3; }
"""

DEFS = """<defs>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#5a6270"/></marker>
  <marker id="ab" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#d0342c"/></marker>
  <marker id="aw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#a75909"/></marker>
</defs>"""


NBSP = "\u00a0"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# flow graph
# --------------------------------------------------------------------------- #
COL_X = [24, 250, 530, 810, 1060]          # column left edges
NODE_W = {"doc": 170, "code": 230, "off": 230, "loop": 230, "crit": 176}


def flow_svg(spec: dict) -> str:
    """A flow graph from a spec: nodes placed on a (col, row) grid, edges by id."""
    nodes = {n["id"]: n for n in spec["nodes"]}
    W, H = 1240, spec.get("height", 720)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(spec["title"])}：物理算法流程图">',
           f"<title>{esc(spec['title'])} — 物理算法流程</title>", f"<style>{STYLE}</style>", DEFS,
           f'<rect width="{W}" height="{H}" fill="#f4f5f7"/>',
           f'<text x="24" y="34" class="h">{esc(spec["title"])} · 物理算法流程</text>',
           '<text x="24" y="54" class="s">实线边 = 数据 · 虚线边 = 模型 · 红边 = 回边 · 橙边 = 对照 / 判定 · 虚框 = 今天无 code 的步 · 橙底行 = 该步的判据</text>']
    geom = {}
    for n in spec["nodes"]:
        kind = n.get("kind", "code")
        x = n.get("x", COL_X[n["col"]]); y = n["y"]
        w = n.get("w", NODE_W[kind]); lines = n.get("lines", [])
        crit = n.get("crit")
        h = n.get("h", (70 + 22 * len(lines)) if kind == "loop" else 26 + 18 * len(lines) + (34 if crit else 8))
        geom[n["id"]] = (x, y, w, h)
        if kind == "loop":
            cx, cy = x + w / 2, y + h / 2
            out.append(f'<path d="M{cx},{y} L{x+w},{cy} L{cx},{y+h} L{x},{cy} Z" class="loop"/>')
            ty = cy - 4 - 8 * len(lines)
            out.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" class="t">{esc(n["title"])}</text>')
            for i, ln in enumerate(lines):
                out.append(f'<text x="{cx}" y="{ty+18+16*i}" text-anchor="middle" class="{"k" if ln.startswith("`") else "s"}">{esc(ln.replace("`", ""))}</text>')
            continue
        cls = {"doc": "doc", "code": "node-code", "off": "node-off", "crit": "crit"}[kind]
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" class="{cls}"/>')
        tcls = "off-t" if kind == "off" else ("t" if kind in ("code", "crit") else "")
        out.append(f'<text x="{x+12}" y="{y+20}" class="{tcls}">{esc(n["title"])}</text>')
        for i, ln in enumerate(lines):
            c = "k" if ln.startswith("`") else ("off-t" if kind == "off" else "s")
            out.append(f'<text x="{x+12}" y="{y+38+18*i}" class="{c}">{esc(ln.replace("`", ""))}</text>')
        if crit:
            cy = y + h - 30
            out.append(f'<rect x="{x+1}" y="{cy}" width="{w-2}" height="29" class="crit"/>')
            out.append(f'<text x="{x+12}" y="{cy+19}" class="tag">{esc(crit)}</text>')
    # edges
    def side(nid, s):
        x, y, w, h = geom[nid]
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[s]
    for e in spec.get("edges", []):
        (x1, y1), (x2, y2) = side(e["from"], e.get("fs", "r")), side(e["to"], e.get("ts", "l"))
        cls = {"data": "edge", "model": "edge-model", "back": "back", "gate": "gate"}[e.get("kind", "data")]
        if "path" in e:
            d = e["path"]
        elif abs(y1 - y2) < 2:
            d = f"M{x1},{y1} L{x2},{y2}"
        else:
            mx = (x1 + x2) / 2
            d = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}"
        out.append(f'<path d="{d}" class="{cls}"/>')
        if e.get("label"):
            lx, ly = e.get("lx", (x1 + x2) / 2), e.get("ly", (y1 + y2) / 2 - 6)
            col = {"back": ' style="fill:#d0342c"', "gate": ""}.get(e.get("kind"), "")
            c = "tag" if e.get("kind") in ("back", "gate") else "s"
            out.append(f'<text x="{lx}" y="{ly}" class="{c}"{col}>{esc(e["label"])}</text>')
    if spec.get("legend"):
        ly = H - 24 - 18 * len(spec["legend"]) - 12
        out.append(f'<rect x="24" y="{ly}" width="{W-48}" height="{18*len(spec["legend"])+16}" rx="6" class="node"/>')
        for i, ln in enumerate(spec["legend"]):
            out.append(f'<text x="36" y="{ly+20+18*i}" class="s">{esc(ln)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# page mock-up
# --------------------------------------------------------------------------- #
def page_svg(spec: dict) -> str:
    W = 1240
    H = spec.get("height", max(p["y"] + p["h"] for p in spec["panels"]) + 40)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(spec["title"])}：页面效果图">',
           f"<title>{esc(spec['title'])} — 页面效果图（概念图，数值示意）</title>", f"<style>{STYLE}</style>", DEFS,
           f'<rect width="{W}" height="{H}" fill="#f4f5f7"/>']
    # shell strip
    out.append('<rect x="16" y="16" width="1208" height="44" rx="4" class="head"/>')
    out.append(f'<text x="28" y="43" class="h">{esc(spec["shell"])}</text>')
    out.append(f'<text x="520" y="43" class="s">{esc(spec.get("context", ""))}</text>')
    for i, b in enumerate(("导入", "导出", "报告")):
        out.append(f'<rect x="{900+i*84}" y="26" width="72" height="24" rx="4" class="btn"/><text x="{914+i*84}" y="43">{b}</text>')
    # control bar
    out.append('<rect x="16" y="72" width="1208" height="40" rx="4" class="panel"/>')
    x = 28
    for i, b in enumerate(spec.get("actions", ["运行到此", "单步", "从此重跑", "断点", "取消"])):
        w = 14 * len(b) + 34
        cls = "btn-on" if i == 0 else "btn"
        out.append(f'<rect x="{x}" y="80" width="{w}" height="24" rx="4" class="{cls}"/>')
        out.append(f'<text x="{x+14}" y="97" class="{"btn-on-t" if i == 0 else ""}">{esc(b)}</text>')
        x += w + 8
    out.append(f'<text x="{x+20}" y="97" class="s">{esc(spec.get("action_note", "没有「跳过」：可选步的开关在计划里"))}</text>')
    # panels
    for p in spec["panels"]:
        px, py, pw, ph = p["x"], p["y"], p["w"], p["h"]
        out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="4" class="panel"/>')
        out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="26" rx="4" class="head"/>')
        out.append(f'<text x="{px+12}" y="{py+18}" class="t">{esc(p["title"])}</text>')
        yy = py + 50
        for it in p.get("items", []):
            kind, txt = it[0], it[1]
            if kind == "text":
                out.append(f'<text x="{px+12}" y="{yy}" class="s">{esc(txt)}</text>'); yy += 18
            elif kind == "code":
                out.append(f'<text x="{px+12}" y="{yy}" class="k">{esc(txt)}</text>'); yy += 18
            elif kind == "slider":
                val = it[2] if len(it) > 2 else 0.5
                out.append(f'<text x="{px+12}" y="{yy}" class="s">{esc(txt)}</text>')
                out.append(f'<line x1="{px+150}" y1="{yy-4}" x2="{px+pw-90}" y2="{yy-4}" class="slider"/>')
                out.append(f'<circle cx="{px+150+(pw-240)*val}" cy="{yy-4}" r="6" class="knob"/>')
                if len(it) > 3: out.append(f'<text x="{px+pw-80}" y="{yy}" class="k">{esc(it[3])}</text>')
                yy += 26
            elif kind == "badge":
                bc = {"ok": ("badge-ok", "ok-t"), "run": ("badge-run", "acc-t"), "stale": ("badge-stale", "warn-t")}[it[2]]
                out.append(f'<text x="{px+12}" y="{yy}" class="s">{esc(txt)}</text>')
                out.append(f'<rect x="{px+150}" y="{yy-12}" width="{9*len(it[3])+14}" height="16" rx="8" class="{bc[0]}"/>')
                out.append(f'<text x="{px+157}" y="{yy}" class="{bc[1]}" style="font-size:10px">{esc(it[3])}</text>'); yy += 24
            elif kind == "chips":
                out.append(f'<text x="{px+12}" y="{yy}" class="s">{esc(txt)}</text>')
                cx = px + 150
                for j, c in enumerate(it[2]):
                    w = 8 * len(c) + 20
                    cls = "btn-on" if j == it[3] else "btn"
                    out.append(f'<rect x="{cx}" y="{yy-13}" width="{w}" height="18" rx="9" class="{cls}"/>')
                    out.append(f'<text x="{cx+10}" y="{yy}" class="{"btn-on-t" if j == it[3] else ""}" style="font-size:10.5px">{esc(c)}</text>')
                    cx += w + 8
                yy += 26
            elif kind == "plot":
                # a small axes with polylines: it[2] = list of (class, points-in-unit-square)
                ax, ay, aw, ah = px + 40, yy, pw - 60, it[3] if len(it) > 3 else 150
                out.append(f'<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" class="axes"/>')
                for gy in (0.25, 0.5, 0.75):
                    out.append(f'<line x1="{ax}" y1="{ay+ah*gy}" x2="{ax+aw}" y2="{ay+ah*gy}" class="grid"/>')
                for cls, pts in it[2]:
                    P = " ".join(f"{ax+aw*u},{ay+ah*(1-v)}" for u, v in pts)
                    out.append(f'<polyline class="{cls}" points="{P}"/>')
                out.append(f'<text x="{ax}" y="{ay+ah+16}" class="s">{esc(txt)}</text>')
                yy += ah + 34
            elif kind == "warn":
                out.append(f'<rect x="{px+8}" y="{yy-14}" width="{pw-16}" height="36" rx="4" class="warnbox"/>')
                out.append(f'<text x="{px+16}" y="{yy+2}" class="warn-t" style="font-size:11px">{esc(txt)}</text>')
                if len(it) > 2: out.append(f'<text x="{px+16}" y="{yy+16}" class="warn-t" style="font-size:11px">{esc(it[2])}</text>')
                yy += 44
            elif kind == "table":
                for r in it[2]:
                    cell = esc(r).replace(" ", NBSP)
                    out.append(f'<text x="{px+12}" y="{yy}" class="mono">{cell}</text>'); yy += 16
                yy += 6
    if spec.get("note"):
        out.append(f'<text x="24" y="{H-14}" class="s">{esc(spec["note"])}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# the specs — one per scenario chapter (the kinetic-reconstruction pair is
# hand-drawn and NOT generated here; see FYL-DESIGN-24)
# --------------------------------------------------------------------------- #
SPECS: dict[str, dict] = {}

try:
    from _scenario_figure_specs import SPECS as _S  # noqa: E402  (beside this script)
    SPECS.update(_S)
except ImportError:  # pragma: no cover - the specs module ships next to this file
    pass


def render_all() -> dict[Path, str]:
    files = {}
    for name, spec in SPECS.items():
        files[OUT / f"sc-{name}-flow.svg"] = flow_svg(spec["flow"])
        files[OUT / f"sc-{name}-page.svg"] = page_svg(spec["page"])
    return files


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files = render_all()
    bad = 0
    for path, text in files.items():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print(f"  stale  {path.relative_to(ROOT)}"); bad += 1
        else:
            path.write_text(text, encoding="utf-8")
            print(f"  wrote  {path.relative_to(ROOT)}")
    if check and not bad:
        print(f"  ok     {len(files)} figures match their specs")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main(sys.argv[1:]))
