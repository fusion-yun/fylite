"""A case and its record -> one MyST report with SVG figures, through a presentation spec.

★★What this renders and what it refuses.  The inputs are two fyo / spo
documents: the PLAN (``fyo:ScenarioSpecification`` — what was asked) and
the RECORD (``spo:ComputationRecord`` — what came back, its datasets inline
on the output ports as ``fylite case json`` / :func:`fylite.io.fydoc.case_json`
hand them over, or beside it as files when ``fylite case run`` wrote them).
Between them sits a PRESENTATION SPECIFICATION (``spo:PresentationSpecification``,
FYL-REPORT-06 §13 / FYO-ADR-09): panels of views, each view a list of series
bound to quantities of the record.  The spec is either supplied (a case may
carry its own) or DERIVED here by rule — and the derived one is written out
beside the report, so the same spec drives the browser page
(``app/pages/report.html``) and a reader can see exactly what was drawn.

The rules are §13's principles, made executable:

* **P1 — a presentation is about information, not information.**  The spec
  binds quantities by path (``<dataset id>#<fyo path>``); no number is copied
  into it, and the report inlines no array (the record is the 正本).
* **P2 — the abscissa is the quantity's own coordinate.**  A 1-D quantity is
  drawn against the grid it sits on (``…/grid/rho_tor_norm`` / ``…/grid/rho_tor``
  / ``…/grid/psi`` in its own container, ``time`` for a trace of that length,
  the equilibrium's ``profiles_1d/rho_tor`` for a ladder column); units come
  from the record's own manifest lines.  A 1-D quantity with no coordinate is
  TABLED, never plotted against a guess.
* **P3 / P4 — state and verdicts are read, not made.**  ``run_state`` and the
  kernel's sentences are quoted; a plain case run has no comparison record,
  so 验收 says「未评估」rather than inventing one.
* **The poloidal section is the one fusion view** (``fyo:PoloidalSectionView``):
  drawn when an equilibrium dataset carries a boundary outline (and, when
  present, a 2-D ψ on its grid); refused BY NAME otherwise, and the rest of
  the page renders.

★stdlib only.  The SVG is written by hand (a line chart and a poloidal
section, 1-2-5 ticks, an isometric section) — matplotlib is optional in this
package and a report face that needed it would be a report face most hosts
cannot run.  The browser renderer (``app/assets/casereport.js``) is a port of
the same rules; ``app/tests/validate-report.mjs`` holds the two together on
the derived spec.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
from pathlib import Path

from .report import SECTIONS

#: coordinate paths, by preference, RELATIVE to the container of the quantity
_GRID_COORDS = ("grid/rho_tor_norm", "grid/rho_tor", "grid/psi", "grid/rho_pol_norm")
#: names a leaf must not be drawn as a quantity (they are coordinates)
_COORD_LEAVES = {"time", "rho_tor", "rho_tor_norm", "psi", "dim1", "dim2", "rho_pol_norm"}
#: fixed series colours (six hues, the same list in casereport.js)
PALETTE = ("#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2")

_STATE_ZH = {"succeeded": "成功", "failed": "失败", "rejected": "拒绝", "running": "运行中",
             "submitted": "已提交", "validating": "校验中", "cancelled": "已取消"}


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def _lang(v, lang="zh") -> str:
    if isinstance(v, dict):
        return v.get(lang) or next((x for x in v.values() if x), "")
    return "" if v is None else str(v)


def load_record(src: str | Path) -> tuple[dict, dict | None, Path | None]:
    """A record from a file or a run directory -> (record, plan-or-None, base dir).

    Datasets not inline on their ports are read from the port's
    ``bound_concretization.storage_uri`` relative to the record; the composed
    plan is read from ``plan.jsonld`` beside it when present.
    """
    p = Path(src)
    if p.is_dir():
        base, rec_path = p, p / "record.jsonld"
    else:
        base, rec_path = p.parent, p
    if not rec_path.is_file():
        raise FileNotFoundError(f"no record at {rec_path}")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    if isinstance(rec, dict) and rec.get("type") != "spo:ComputationRecord":
        raise ValueError(f"{rec_path} is not an spo:ComputationRecord (type {rec.get('type')!r})")
    for b in rec.get("inputs") or []:
        bt = b.get("bound_to")
        conc = b.get("bound_concretization") or {}
        uri = conc.get("storage_uri", "")
        if isinstance(bt, dict) and not _has_arrays(bt) and uri.endswith(".jsonld") and (base / uri).is_file():
            doc = json.loads((base / uri).read_text(encoding="utf-8"))
            doc.setdefault("comment", bt.get("comment"))
            b["bound_to"] = doc
    plan = None
    if (base / "plan.jsonld").is_file():
        plan = json.loads((base / "plan.jsonld").read_text(encoding="utf-8"))
    return rec, plan, base


def _has_arrays(doc: dict) -> bool:
    for k, v in doc.items():
        if k.startswith("@") or k in ("id", "type", "comment"):
            continue
        if isinstance(v, list) and v and isinstance(v[0], (int, float)):
            return True
        if isinstance(v, dict) and _has_arrays(v):
            return True
        if isinstance(v, list) and v and isinstance(v[0], dict) and _has_arrays(v[0]):
            return True
    return False


# --------------------------------------------------------------------------- #
# the record's quantities
# --------------------------------------------------------------------------- #
def _units_from_comment(doc: dict) -> dict:
    """``{path: units}`` out of the manifest lines the kernel left on the port."""
    out = {}
    lines = doc.get("comment") or []
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        if not isinstance(line, str) or " [" not in line:
            continue
        path, _, rest = line.partition(" [")
        units = rest.split("]", 1)[0]
        out[path.strip()] = units
    return out


def _walk(node, prefix: str, out: list):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("@") or k in ("id", "type", "comment"):
                continue
            _walk(v, f"{prefix}/{k}" if prefix else k, out)
    elif isinstance(node, list):
        if node and isinstance(node[0], dict):
            #: an array of structures: index 0 is what the declared path means
            _walk(node[0], prefix, out)
        elif node and isinstance(node[0], list):
            out.append((prefix, node, 2))
        elif node and all(isinstance(x, (int, float)) or x is None for x in node):
            out.append((prefix, node, 1))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append((prefix, node, 0))


def quantities(doc: dict) -> list[dict]:
    """Every numeric leaf of one dataset: ``{path, data, ndim, units, n}``."""
    units = _units_from_comment(doc)
    leaves: list = []
    _walk(doc, "", leaves)
    out = []
    for path, data, ndim in leaves:
        n = len(data) if ndim == 1 else (len(data), len(data[0]) if data else 0) if ndim == 2 else 1
        out.append({"path": path, "data": data, "ndim": ndim, "units": units.get(path, ""), "n": n})
    return out


_LAYER_PREFIXES = ("time_slice/boundary/outline/", "fylite:limiter/", "time_slice/profiles_2d/")


def _is_layer(path: str) -> bool:
    return path.startswith(_LAYER_PREFIXES)


def _container(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def coordinate_of(q: dict, qs: list[dict], eq_qs: list[dict] | None = None) -> dict | None:
    """The coordinate a 1-D quantity is drawn against (P2), or None."""
    if q["ndim"] != 1 or q["n"] < 2:
        #: a one-sample array is a reading, not a curve (an axis position on a
        #: one-slice time base is the case in point)
        return None
    leaf = q["path"].rsplit("/", 1)[-1]
    if leaf in _COORD_LEAVES:
        return None
    by_path = {x["path"]: x for x in qs if x["ndim"] == 1}
    #: the grid of the quantity's own container, or of an ancestor container —
    #: `profiles_1d/electrons/temperature` sits on `profiles_1d/grid/rho_tor`
    cont = _container(q["path"])
    ancestors = []
    while True:
        ancestors.append(cont)
        if not cont:
            break
        cont = _container(cont)
    for anc in ancestors:
        for rel in _GRID_COORDS:
            c = by_path.get(f"{anc}/{rel}" if anc else rel)
            if c is not None and c["n"] == q["n"]:
                return c
        #: a ladder column beside the equilibrium's own rho (profiles_1d/rho_tor)
        for cand in (f"{anc}/rho_tor", f"{anc}/psi"):
            c = by_path.get(cand)
            if c is not None and c["n"] == q["n"] and c is not q:
                return c
    #: a trace: the dataset's time base of the same length
    t = by_path.get("time")
    if t is not None and t["n"] == q["n"] and t is not q:
        return t
    #: a column on the equilibrium's grid (an equilibrium dataset of the same run)
    for x in eq_qs or []:
        if x["path"].endswith("profiles_1d/rho_tor") and x["n"] == q["n"]:
            return x
    return None


# --------------------------------------------------------------------------- #
# the presentation, derived
# --------------------------------------------------------------------------- #
def _datasets(record: dict) -> list[tuple[str, dict]]:
    """(port name, dataset document) for every OUTPUT port carrying arrays."""
    out = []
    for b in record.get("inputs") or []:
        port = (b.get("binds_port") or {}).get("port_name", "")
        direction = (b.get("binds_port") or {}).get("port_direction", "")
        bt = b.get("bound_to")
        if direction == "output" and isinstance(bt, dict) and _has_arrays(bt):
            out.append((port, bt))
    return out


def _label(path: str) -> str:
    """A short series label: the path with the container prefix folded."""
    parts = path.split("/")
    skip = {"profiles_1d", "time_slice", "global_quantities", "value", "model", "0", "local"}
    kept = [x for x in parts if x not in skip]
    return "/".join(kept) if kept else path


def derive_presentation(plan: dict | None, record: dict) -> dict:
    """The spec this renderer would draw for the record, as a document."""
    rid = record.get("id", "run")
    sets = _datasets(record)
    eq_qs = next((quantities(d) for p, d in sets if d.get("type") == "fyo:equilibrium"), None)
    views_profile, views_trace, readouts, tabled, section = [], [], [], [], None
    for port, doc in sets:
        did = doc.get("id", port)
        qs = quantities(doc)
        groups: dict[tuple, list] = {}
        for q in qs:
            if q["ndim"] == 0 or (q["ndim"] == 1 and q["n"] == 1 and q["path"].rsplit("/", 1)[-1] not in _COORD_LEAVES):
                readouts.append({"type": "spo:Series", "binds_quantity": f"{did}#{q['path']}",
                                 "series_role": "computed",
                                 "display_label": {"zh": f"{port}·{_label(q['path'])}", "en": f"{port}·{_label(q['path'])}"}})
                continue
            if q["ndim"] != 1:
                continue
            c = coordinate_of(q, qs, eq_qs)
            if c is None:
                #: outline and limiter polylines are LAYERS of the section view, not curves
                if q["path"].rsplit("/", 1)[-1] not in _COORD_LEAVES and not _is_layer(q["path"]):
                    tabled.append((did, q))
                continue
            key = (c["path"], q["units"])
            groups.setdefault(key, []).append((q, c))
        for (cpath, units), items in groups.items():
            c = items[0][1]
            is_trace = cpath.rsplit("/", 1)[-1] == "time"
            cname = cpath.rsplit("/", 1)[-1]
            labels = ", ".join(_label(q["path"]) for q, _ in items)
            view = {
                "type": "spo:View", "view_kind": "line_chart",
                "caption": {"zh": f"{port}：{labels}（{units or '1'}）对 {cname}（{c['units'] or '1'}）",
                            "en": f"{port}: {labels} [{units or '1'}] against {cname} [{c['units'] or '1'}]"},
                "has_series": [
                    {"type": "spo:Series", "binds_quantity": f"{did}#{q['path']}", "series_role": "computed",
                     "mark_kind": "line", "line_style": "solid",
                     "display_label": {"zh": _label(q["path"]), "en": _label(q["path"])}}
                    for q, _ in items],
                "comment": f"abscissa {did}#{cpath}",
            }
            (views_trace if is_trace else views_profile).append(view)
        if doc.get("type") == "fyo:equilibrium" and section is None:
            paths = {q["path"] for q in qs}
            if "time_slice/boundary/outline/r" in paths and "time_slice/boundary/outline/z" in paths:
                section = {"type": "fyo:PoloidalSectionView", "view_kind": "map",
                           "caption": {"zh": "极向截面：边界轮廓、磁轴" + ("、ψ 等值线" if "time_slice/profiles_2d/psi" in paths else ""),
                                       "en": "Poloidal section: boundary outline, magnetic axis" + (", psi contours" if "time_slice/profiles_2d/psi" in paths else "")},
                           "has_coordinate_system": "spo:CylindricalRZ",
                           "flux_layer": did}
    panels = []
    if readouts:
        panels.append({"type": "spo:Panel", "panel_kind": "readings",
                       "title": {"zh": "读数", "en": "Readings"},
                       "has_view": [{"type": "spo:View", "view_kind": "scalar_readout",
                                     "caption": {"zh": "记录中的标量", "en": "Scalars of the record"},
                                     "has_series": readouts}]})
    results = views_profile + views_trace + ([section] if section else [])
    if results:
        panels.append({"type": "spo:Panel", "panel_kind": "results",
                       "title": {"zh": "结果", "en": "Results"}, "has_view": results})
    spec = {
        "@context": ["context.jsonld", {"@base": "../"}],
        "id": f"{rid}/presentation",
        "type": "spo:PresentationSpecification",
        "title": {"zh": "按规则推出的呈现规格", "en": "Presentation derived by rule"},
        "presents": [x for x in ((plan or {}).get("id"), rid) if x],
        "has_panel": panels,
        "caveat": ["derived by fylite.engine.casereport (FYL-REPORT-06 §13 P1–P4): no number is copied here, "
                   "every series binds a quantity of the record by path"]
                  + ([f"tabled, not drawn (no coordinate declared): " + ", ".join(f"{d}#{q['path']}" for d, q in tabled)] if tabled else [])
                  + ([] if section else ["fyo:PoloidalSectionView refused by name: no equilibrium dataset carries a boundary outline"]),
    }
    return spec


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #
def _nice_step(span: float, span_px: float, min_px: float = 48.0) -> float:
    if not (span > 0) or not (span_px > 0):
        return 1.0
    want = span * min_px / span_px
    pw = 10 ** math.floor(math.log10(want))
    m = want / pw
    return (1 if m <= 1 else 2 if m <= 2 else 5 if m <= 5 else 10) * pw


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if 1e-3 <= a < 1e5:
        s = f"{v:.6g}"
    else:
        s = f"{v:.3g}"
    return s


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _finite(xs):
    return [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]


def svg_line_chart(series: list[dict], *, xlabel: str, ylabel: str, title: str = "",
                   width: int = 560, height: int = 320) -> str:
    """``series``: ``[{label, x: [...], y: [...], color?, dashed?}]`` -> an SVG document."""
    pad_l, pad_r, pad_t, pad_b = 62, 16, 28 if title else 12, 44
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    xs = _finite([v for s in series for v in s["x"]])
    ys = _finite([v for s in series for v in s["y"]])
    if not xs or not ys:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
                f'<text x="{width/2}" y="{height/2}" text-anchor="middle" font-size="13" fill="currentColor">no finite samples</text></svg>')
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    if xmax == xmin:
        xmax = xmin + 1
    if ymax == ymin:
        ymax, ymin = ymin + (abs(ymin) or 1) * 0.5, ymin - (abs(ymin) or 1) * 0.5
    yr = ymax - ymin
    ymin, ymax = ymin - 0.04 * yr, ymax + 0.04 * yr
    sx = lambda v: pad_l + (v - xmin) / (xmax - xmin) * w
    sy = lambda v: pad_t + h - (v - ymin) / (ymax - ymin) * h
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="system-ui, sans-serif" font-size="11" fill="currentColor">']
    if title:
        o.append(f'<text x="{pad_l}" y="16" font-size="12" font-weight="600">{_esc(title)}</text>')
    o.append(f'<rect x="{pad_l}" y="{pad_t}" width="{w}" height="{h}" fill="none" stroke="currentColor" stroke-opacity="0.35"/>')
    # grid + ticks
    stx = _nice_step(xmax - xmin, w, 60)
    v = math.ceil(xmin / stx) * stx
    while v <= xmax + 1e-12 * stx:
        X = sx(v)
        o.append(f'<line x1="{X:.1f}" y1="{pad_t}" x2="{X:.1f}" y2="{pad_t + h}" stroke="currentColor" stroke-opacity="0.12"/>')
        o.append(f'<text x="{X:.1f}" y="{pad_t + h + 14}" text-anchor="middle">{_esc(_fmt(v))}</text>')
        v += stx
    sty = _nice_step(ymax - ymin, h, 34)
    v = math.ceil(ymin / sty) * sty
    while v <= ymax + 1e-12 * sty:
        Y = sy(v)
        o.append(f'<line x1="{pad_l}" y1="{Y:.1f}" x2="{pad_l + w}" y2="{Y:.1f}" stroke="currentColor" stroke-opacity="0.12"/>')
        o.append(f'<text x="{pad_l - 6}" y="{Y + 3.5:.1f}" text-anchor="end">{_esc(_fmt(v))}</text>')
        v += sty
    o.append(f'<text x="{pad_l + w / 2:.1f}" y="{height - 8}" text-anchor="middle" font-size="12">{_esc(xlabel)}</text>')
    o.append(f'<text transform="translate(14,{pad_t + h / 2:.1f}) rotate(-90)" text-anchor="middle" font-size="12">{_esc(ylabel)}</text>')
    for i, s in enumerate(series):
        col = s.get("color") or PALETTE[i % len(PALETTE)]
        pts = [(sx(x), sy(y)) for x, y in zip(s["x"], s["y"])
               if isinstance(x, (int, float)) and isinstance(y, (int, float)) and math.isfinite(x) and math.isfinite(y)]
        if not pts:
            continue
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        dash = ' stroke-dasharray="6 4"' if s.get("dashed") else ""
        o.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6"{dash}/>')
    # legend (top-right inside the plot)
    lx, ly = pad_l + w - 10, pad_t + 8
    for i, s in enumerate(series):
        col = s.get("color") or PALETTE[i % len(PALETTE)]
        yy = ly + 14 * i + 6
        o.append(f'<line x1="{lx - 22}" y1="{yy}" x2="{lx - 6}" y2="{yy}" stroke="{col}" stroke-width="2"/>')
        o.append(f'<text x="{lx - 26}" y="{yy + 3.5}" text-anchor="end">{_esc(s.get("label", ""))}</text>')
    o.append("</svg>")
    return "\n".join(o)


def _contour_segments(z, x, y, level):
    """Marching squares: line segments of the iso-line ``z == level`` on the (x, y) grid."""
    segs = []
    ny, nx = len(z), len(z[0]) if z else 0
    if len(x) != nx or len(y) != ny:
        return segs

    def interp(p1, v1, p2, v2):
        t = 0.5 if v2 == v1 else (level - v1) / (v2 - v1)
        return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
    for j in range(ny - 1):
        for i in range(nx - 1):
            v = (z[j][i], z[j][i + 1], z[j + 1][i + 1], z[j + 1][i])
            if any(not isinstance(a, (int, float)) or not math.isfinite(a) for a in v):
                continue
            p = ((x[i], y[j]), (x[i + 1], y[j]), (x[i + 1], y[j + 1]), (x[i], y[j + 1]))
            pts = []
            for k in range(4):
                a, b = v[k], v[(k + 1) % 4]
                if (a < level) != (b < level):
                    pts.append(interp(p[k], a, p[(k + 1) % 4], b))
            if len(pts) == 2:
                segs.append((pts[0], pts[1]))
            elif len(pts) == 4:
                segs.append((pts[0], pts[1])); segs.append((pts[2], pts[3]))
    return segs


def svg_poloidal(boundary: tuple[list, list], *, axis: tuple[float, float] | None = None,
                 limiter: tuple[list, list] | None = None,
                 psi: tuple[list, list, list] | None = None, n_levels: int = 8,
                 title: str = "", height: int = 380) -> str:
    """An isometric (R, Z) section: outline, axis, limiter, optional ψ contours."""
    br, bz = boundary
    rs = _finite(br) + (_finite(limiter[0]) if limiter else [])
    zs = _finite(bz) + (_finite(limiter[1]) if limiter else [])
    if not rs or not zs:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    rmin, rmax, zmin, zmax = min(rs), max(rs), min(zs), max(zs)
    m = 0.06 * max(rmax - rmin, zmax - zmin) or 0.1
    rmin, rmax, zmin, zmax = rmin - m, rmax + m, zmin - m, zmax + m
    pad = 40
    ph = height - 2 * pad - (18 if title else 0)
    scale = ph / (zmax - zmin)
    pw = (rmax - rmin) * scale
    width = int(pw + 2 * pad + 20)
    top = pad + (18 if title else 0)
    sx = lambda r: pad + (r - rmin) * scale
    sy = lambda z: top + ph - (z - zmin) * scale
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="system-ui, sans-serif" font-size="11" fill="currentColor">']
    if title:
        o.append(f'<text x="{pad}" y="16" font-size="12" font-weight="600">{_esc(title)}</text>')
    o.append(f'<rect x="{pad}" y="{top}" width="{pw:.1f}" height="{ph:.1f}" fill="none" stroke="currentColor" stroke-opacity="0.35"/>')
    st = _nice_step(rmax - rmin, pw, 60)
    v = math.ceil(rmin / st) * st
    while v <= rmax:
        o.append(f'<text x="{sx(v):.1f}" y="{top + ph + 14}" text-anchor="middle">{_esc(_fmt(v))}</text>'); v += st
    st = _nice_step(zmax - zmin, ph, 40)
    v = math.ceil(zmin / st) * st
    while v <= zmax:
        o.append(f'<text x="{pad - 6}" y="{sy(v) + 3.5:.1f}" text-anchor="end">{_esc(_fmt(v))}</text>'); v += st
    o.append(f'<text x="{pad + pw / 2:.1f}" y="{height - 6}" text-anchor="middle" font-size="12">R [m]</text>')
    o.append(f'<text transform="translate(12,{top + ph / 2:.1f}) rotate(-90)" text-anchor="middle" font-size="12">Z [m]</text>')
    if psi:
        z2, gx, gy = psi
        flat = _finite([v for row in z2 for v in row])
        if flat:
            lo, hi = min(flat), max(flat)
            for k in range(1, n_levels + 1):
                lev = lo + (hi - lo) * k / (n_levels + 1)
                d = " ".join(f"M{sx(a[0]):.1f},{sy(a[1]):.1f} L{sx(b[0]):.1f},{sy(b[1]):.1f}" for a, b in _contour_segments(z2, gx, gy, lev))
                if d:
                    o.append(f'<path d="{d}" fill="none" stroke="#7c8ea6" stroke-width="0.9"/>')
    if limiter:
        pts = [(sx(r), sy(z)) for r, z in zip(*limiter) if math.isfinite(r) and math.isfinite(z)]
        if pts:
            o.append('<path d="M' + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '" fill="none" stroke="#666" stroke-width="1.6"/>')
    pts = [(sx(r), sy(z)) for r, z in zip(br, bz) if math.isfinite(r) and math.isfinite(z)]
    if pts:
        o.append('<path d="M' + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts) + ' Z" fill="none" stroke="#dc2626" stroke-width="1.8"/>')
    if axis and all(math.isfinite(v) for v in axis):
        o.append(f'<circle cx="{sx(axis[0]):.1f}" cy="{sy(axis[1]):.1f}" r="3.5" fill="#dc2626"/>')
    o.append("</svg>")
    return "\n".join(o)


# --------------------------------------------------------------------------- #
# resolving a spec against the record, and rendering
# --------------------------------------------------------------------------- #
def _index(record: dict) -> dict:
    """``{dataset id: {path: quantity}}`` for every output port."""
    out = {}
    for port, doc in _datasets(record):
        out[doc.get("id", port)] = {q["path"]: q for q in quantities(doc)}
    return out


def _resolve(ref: str, idx: dict) -> dict | None:
    did, _, path = ref.partition("#")
    return (idx.get(did) or {}).get(path)


def render_figures(record: dict, spec: dict, out_dir: Path, *, lang: str = "zh") -> list[dict]:
    """Every view of the spec -> ``{name, path, caption, kind}``; refused views carry ``refused``."""
    idx = _index(record)
    fig_dir = out_dir / "figures"
    figs = []
    n = 0
    for panel in spec.get("has_panel") or []:
        for view in panel.get("has_view") or []:
            kind = view.get("view_kind")
            cap = _lang(view.get("caption"), lang)
            if kind == "line_chart":
                series, coord = [], None
                for s in view.get("has_series") or []:
                    q = _resolve(s["binds_quantity"], idx)
                    if q is None or q["ndim"] != 1:
                        continue
                    did = s["binds_quantity"].partition("#")[0]
                    qs = list(idx[did].values())
                    eq = next((list(v.values()) for k, v in idx.items() if k.endswith("/equilibrium")), None)
                    c = coordinate_of(q, qs, eq)
                    if c is None:
                        continue
                    coord = coord or c
                    series.append({"label": _lang(s.get("display_label"), lang) or _label(q["path"]),
                                   "x": c["data"], "y": q["data"], "dashed": s.get("line_style") == "dashed",
                                   "units": q["units"]})
                if not series or coord is None:
                    figs.append({"kind": kind, "caption": cap, "refused": "no series of this view resolves to a 1-D quantity with a coordinate"})
                    continue
                n += 1
                name = f"fig-{n:02d}"
                units = series[0]["units"]
                svg = svg_line_chart(series, xlabel=f"{coord['path'].rsplit('/', 1)[-1]} [{coord['units'] or '1'}]",
                                     ylabel=f"[{units or '1'}]")
                fig_dir.mkdir(parents=True, exist_ok=True)
                (fig_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
                figs.append({"kind": kind, "name": name, "path": f"figures/{name}.svg", "caption": cap})
            elif kind == "map" or view.get("type") == "fyo:PoloidalSectionView":
                did = view.get("flux_layer")
                qs = idx.get(did) or {}
                br, bz = qs.get("time_slice/boundary/outline/r"), qs.get("time_slice/boundary/outline/z")
                if not (br and bz):
                    figs.append({"kind": "map", "caption": cap, "refused": f"flux layer {did} carries no boundary outline"})
                    continue
                ar, az = qs.get("time_slice/global_quantities/magnetic_axis/r"), qs.get("time_slice/global_quantities/magnetic_axis/z")
                axis = (ar["data"], az["data"]) if ar and az and ar["ndim"] == 0 and az["ndim"] == 0 else None
                if ar and az and ar["ndim"] == 1 and az["ndim"] == 1:
                    axis = (ar["data"][0], az["data"][0])
                lim = None
                lr, lz = qs.get("fylite:limiter/r"), qs.get("fylite:limiter/z")
                if lr and lz:
                    lim = (lr["data"], lz["data"])
                psi = None
                p2, gx, gy = qs.get("time_slice/profiles_2d/psi"), qs.get("time_slice/profiles_2d/grid/dim1"), qs.get("time_slice/profiles_2d/grid/dim2")
                if p2 and gx and gy and p2["ndim"] == 2:
                    psi = (p2["data"], gx["data"], gy["data"])
                n += 1
                name = f"fig-{n:02d}"
                svg = svg_poloidal((br["data"], bz["data"]), axis=axis, limiter=lim, psi=psi)
                fig_dir.mkdir(parents=True, exist_ok=True)
                (fig_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
                figs.append({"kind": "map", "name": name, "path": f"figures/{name}.svg", "caption": cap})
            elif kind == "scalar_readout":
                rows = []
                for s in view.get("has_series") or []:
                    q = _resolve(s["binds_quantity"], idx)
                    if q is not None and (q["ndim"] == 0 or (q["ndim"] == 1 and q["n"] == 1)):
                        val = q["data"][0] if q["ndim"] == 1 else q["data"]
                        rows.append((_lang(s.get("display_label"), lang) or q["path"], val, q["units"]))
                figs.append({"kind": kind, "caption": cap, "rows": rows})
            elif kind == "verdict":
                figs.append({"kind": kind, "caption": cap, "refused": "a plain case record carries no comparison record"})
            else:
                figs.append({"kind": kind, "caption": cap, "refused": f"view kind {kind!r} is not rendered by this host"})
    return figs


def _md_cell(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_myst(plan: dict | None, record: dict, spec: dict, out_dir: Path, *, lang: str = "zh") -> str:
    """The report text (MyST); figures are written under ``out_dir/figures``."""
    figs = render_figures(record, spec, out_dir, lang=lang)
    rid = record.get("id", "run")
    title = _lang((plan or {}).get("title") or record.get("title"), lang) or rid
    started = record.get("started_at") or ""
    date = started[:10] if started else _dt.date.today().isoformat()
    code = record.get("executed_code") or {}
    state = record.get("run_state", "")
    L = []
    w = L.append
    w("---")
    w(f"title: {title}")
    w(f"subtitle: 算例报告——正本为记录 `{rid}`，本报告是它经呈现规格的投影")
    w(f"date: {date}")
    w("---")
    w("")
    w(f"# {title}")
    w("")
    # 摘要
    w(f"## {SECTIONS[0]}")
    w("")
    n_par = len(record.get("parameters") or [])
    n_out = len(_datasets(record))
    dev = _lang(((plan or {}).get("about_discharge") or {}).get("performed_on", {}).get("title"), lang) if plan else ""
    w(f"计划 `{(plan or {}).get('id') or (record.get('realizes') or {}).get('id', '—')}`"
      + (f"（{dev}）" if dev else "") + f"，代码 `{code.get('id', '—')}`（{code.get('name', '')} {code.get('version', '')}），"
      f"记录 `{rid}`：状态 **{_STATE_ZH.get(state, state)}** （`{state}`），{n_par} 项参数设置，{n_out} 个产出端口，"
      f"{started} → {record.get('ended_at', '')}。呈现规格 `{spec.get('id')}`（{'随算例提供' if spec.get('caveat') is None else '按规则推出'}）。")
    note = _lang((plan or {}).get("note"), lang) if plan else ""
    if note:
        w("")
        w(note)
    w("")
    # 方法
    w(f"## {SECTIONS[1]}")
    w("")
    w(":::{table} 表 1：参数设置（记录原文，`sets_parameter` 的键 → JSON 字面量）")
    w(":label: tbl-parameters")
    w("")
    w("| 参数 | 值 |")
    w("| :--- | :--- |")
    for p in record.get("parameters") or []:
        k = str(p.get("sets_parameter", "")).rsplit("#", 1)[-1]
        w(f"| `{_md_cell(k)}` | `{_md_cell(json.dumps(p.get('literal_value'), ensure_ascii=False))}` |")
    w(":::")
    w("")
    w(":::{table} 表 2：端口绑定（输入与产出，按记录）")
    w(":label: tbl-ports")
    w("")
    w("| 端口 | 方向 | 绑定 |")
    w("| :--- | :--- | :--- |")
    for b in record.get("inputs") or []:
        bp = b.get("binds_port") or {}
        bt = b.get("bound_to")
        conc = b.get("bound_concretization") or {}
        how = ("inline dataset " + str(bt.get("id", "")) if isinstance(bt, dict) and _has_arrays(bt)
               else "endpoint " + str((b.get("bound_endpoint") or {}).get("endpoint_uri", "")) if b.get("bound_endpoint")
               else ("file " + conc.get("storage_uri", "")) if conc.get("storage_uri") else "open")
        w(f"| `{_md_cell(bp.get('port_name', ''))}` | {bp.get('port_direction', '')} | {_md_cell(how)} |")
    w(":::")
    w("")
    # 结果
    w(f"## {SECTIONS[2]}")
    w("")
    k = 0
    for f in figs:
        if f["kind"] == "scalar_readout":
            w(f":::{{table}} 表 3：{f['caption']}")
            w(":label: tbl-readings")
            w("")
            w("| 量 | 值 | 单位 |")
            w("| :--- | ---: | :--- |")
            for lab, val, units in f.get("rows") or []:
                w(f"| `{_md_cell(lab)}` | {_fmt(val) if isinstance(val, (int, float)) else _md_cell(val)} | {units or '1'} |")
            w(":::")
            w("")
        elif f.get("path"):
            k += 1
            w(f":::{{figure}} {f['path']}")
            w(f":label: {f['name']}")
            w(f":alt: {f['caption']}")
            w("")
            w(f"图 {k}：{f['caption']}")
            w(":::")
            w("")
        elif f.get("refused"):
            w(f"> 视图「{f['caption']}」未渲染：{f['refused']}。")
            w("")
    for c in spec.get("caveat") or []:
        if c.startswith("tabled"):
            w(f"> {c}")
            w("")
    for line in record.get("comment") or []:
        w(f"> 内核附注：{line}")
        w("")
    # 验收
    w(f"## {SECTIONS[3]}")
    w("")
    w(f"记录状态 `{state}`（{_STATE_ZH.get(state, state)}）。本记录**不含比较记录**（`fyo:ComparisonRecord`），"
      "本报告不评判：验收 **未评估**。对拍见公开登记册（`benchmark/`）中引用同一场景的记录。")
    w("")
    # 复现性
    w(f"## {SECTIONS[4]}")
    w("")
    w(":::{table} 表 4：具体化与校验")
    w(":label: tbl-provenance")
    w("")
    w("| 项 | 存储 | 校验 |")
    w("| :--- | :--- | :--- |")
    for c in ((record.get("realizes") or {}).get("concretized_as") or []):
        w(f"| 计划 | `{_md_cell(c.get('storage_uri', ''))}` | `{_md_cell(c.get('checksum', '—'))}` |")
    for c in code.get("concretized_as") or []:
        w(f"| 代码 `{code.get('version', '')}` | `{_md_cell(Path(c.get('storage_uri', '')).name)}` | `{_md_cell(c.get('checksum', '—'))}` |")
    for b in record.get("inputs") or []:
        conc = b.get("bound_concretization") or {}
        if conc.get("checksum"):
            w(f"| 产出 `{(b.get('binds_port') or {}).get('port_name', '')}` | `{_md_cell(conc.get('storage_uri', ''))}` | `{_md_cell(conc['checksum'])}` |")
    w(":::")
    w("")
    w("重跑：`fylite cases --report <case id>`（经数据层的 JSON 门 `fylite_engine_case_json`）或 "
      "`fylite case run <plan.jsonld>` 后 `fylite cases --report --from <记录目录>`；呈现规格见旁边的 `presentation.jsonld`。")
    w("")
    return "\n".join(L)


def render(src: str | Path | dict, *, plan: dict | None = None, out: str | Path | None = None,
           presentation: dict | str | Path | None = None, lang: str = "zh") -> Path:
    """Render one record (a file, a run directory, or a dict) -> ``report.md`` path."""
    if isinstance(src, dict):
        record, base = src, None
    else:
        record, plan_beside, base = load_record(src)
        plan = plan or plan_beside
    rid = record.get("id", "run").rsplit("/", 1)[-1]
    out_dir = Path(out) if out else (base or Path(os.environ.get("FYLITE_RUN_DIR") or "records") / rid)
    out_dir.mkdir(parents=True, exist_ok=True)
    if presentation is None:
        spec = derive_presentation(plan, record)
    elif isinstance(presentation, dict):
        spec = presentation
    else:
        spec = json.loads(Path(presentation).read_text(encoding="utf-8"))
    (out_dir / "presentation.jsonld").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if isinstance(src, dict) and not (out_dir / "record.jsonld").is_file():
        (out_dir / "record.jsonld").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    #: the plan beside the record, so a reader (the browser page included) gets the
    #: same two documents this renderer had — a report directory is self-contained
    if isinstance(plan, dict) and not (out_dir / "plan.jsonld").is_file():
        (out_dir / "plan.jsonld").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    text = render_myst(plan, record, spec, out_dir, lang=lang)
    dest = out_dir / "report.md"
    dest.write_text(text, encoding="utf-8")
    return dest


def run_and_render(case_id: str, corpus=None, *, out=None, presentation=None, lang: str = "zh") -> Path:
    """Run a corpus case through the JSON door and render its report."""
    from ..io import fydoc
    from ..scenario import cases
    d = cases.corpus_dir() if corpus is None else Path(corpus)
    _entry, plan = cases.load(case_id, d)
    record = fydoc.case_json(plan, base=d)
    return render(record, plan=plan, out=out, presentation=presentation, lang=lang)
