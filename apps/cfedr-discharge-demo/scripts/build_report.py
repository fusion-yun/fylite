"""Build the CFEDR 1.5-D discharge report page: data JSON injected into report_template.html.

Usage: python build_report.py TEMPLATE.html HYBRID.json ZEROD.json RUN15.csv SNAP_150.json SNAP_FLAT.json OUT.html
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

#: published values only (a published reference tables; paper numbers as in its citations)
LITERATURE_FLAT = [
    # key, label, unit, literature value, source
    ("p_fus", "聚变功率 P_fus", "GW", 1.51, "Fan 2025 (PST 27 104007) 表 1"),
    ("q", "聚变增益 Q", "", 14.9, "Fan 2025 表 1（METIS 时序给 ≈13）"),
    ("w_th", "热储能 W_th", "MJ", None, "专辑未给（设计方运行件 807 MJ，未发表）"),
    ("te0", "轴上 T_e0", "keV", 30.0, "Jiang 2025 ICRF §2.1 · Fan 2025 图 2"),
    ("ti0", "轴上 T_i0", "keV", 24.0, "Jiang 2025 ICRF §2.1"),
    ("ne0", "轴上 n_e0", "10²⁰ m⁻³", 1.4, "Jiang 2025 ICRF §2.1"),
    ("ne_bar", "线平均 n̄_e", "10²⁰ m⁻³", 1.12, "Fan 2025 表 1"),
    ("f_gw", "Greenwald 份额", "", 1.41, "Fan 2025 §3.1"),
    ("beta_n", "β_N（含快 α）", "", 2.6, "Fan 2025 表 1"),
    ("h98", "H_98y2", "", 1.0, "Fan 2025 表 1"),
    ("i_bs", "自举电流 I_bs", "MA", 6.60, "Fan 2025 表 1（f_bs 0.44 × 15 MA）"),
    ("v_loop", "燃烧段圈电压", "V", 0.03, "Huang 2025 控制篇 §2（METIS）"),
    ("p_rad", "辐射功率（不含钨）", "MW", 136.0, "REPORT-20 功率平衡表（104008 表 1）"),
    ("p_sep", "越过 LCFS 功率 P_sep", "MW", 267.0, "104002 表 1 · Fan 2025 §3.1"),
    ("p_lh", "L-H 阈值（Martin08）", "MW", 121.0, "104008 表 1（按表面积；按 a、R 为 138）"),
]

LITERATURE_TIMELINE = [
    # t [s], phase, literature statement, source
    (0.0, "击穿", "高场侧击穿；I_p 0.5 MA；n̄_e 0.1×10¹⁹ m⁻³", "控制篇 · 平衡篇"),
    (1.0, "L 模爬升（限制器）", "I_p 0.25 MA、HFS 限制器（a ≈ 1.9 m）、l_i(3) = 1.3；n̄_e 自 8×10¹⁸ 随电流线性升", "平衡篇"),
    (17.0, "位形转换", "转入偏滤器（SND）位形（控制篇记 13 s）；a ≈ 2.1 m", "平衡篇"),
    (10.0, "爬升加热", "EC 5 MW @ ρ≈0.36（10–30 s）· EC 10 MW @ ρ≈0.39（30–60 s）", "EC 篇"),
    (60.0, "电流平顶", "I_p 15 MA（0.25 MA/s）；κ 1.90；n̄_e 经 4.5×10¹⁹（50 s）到 1.14×10²⁰", "两篇"),
    (65.0, "满功率", "82 MW EC + 20 MW IC", "控制篇"),
    (150.0, "进入燃烧 H 模", "密度与热能到燃烧水平；P_α 于 170 s 稳定（METIS）", "两篇"),
    (6150.0, "燃烧末（本回放）", "磁通预算给燃烧约 1 h 40 min；本回放平顶至 6150 s，下降段节点为合成", "控制篇 · 回放文件"),
]


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def main():
    template, hybrid, zerod, run_csv, snap150, snapflat, out = sys.argv[1:8]
    rd_dir = Path(sys.argv[8]) if len(sys.argv) > 8 else None
    H = json.loads(Path(hybrid).read_text(encoding="utf-8"))
    Z = json.loads(Path(zerod).read_text(encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(run_csv, encoding="utf-8", newline=""))]
    windows = list(csv.DictReader(open(run_csv + ".windows.csv", encoding="utf-8", newline="")))
    summ = {}
    sp = Path(run_csv + ".summary.json")
    if sp.exists():
        summ = json.loads(sp.read_text(encoding="utf-8"))

    def model_at(snap_path):
        s = json.loads(Path(snap_path).read_text(encoding="utf-8"))
        fc = s["prev"]["facts"]
        v = lambda k: fc[k]["value"] if k in fc else None  # noqa: E731
        t = s["t"] if "t" in s else v("t_end")
        r = min(rows, key=lambda x: abs(float(x["t"]) - float(t)))
        cp = s["prev"]["fields"]["core_profiles"]["profiles_1d"]
        ne = cp["electrons"]["density"]["data"]
        return {
            "t": float(t),
            "p_fus": (v("p_fus") or 0) / 1e9, "q": v("q_fus"), "w_th": (v("w_th") or 0) / 1e6,
            "te0": cp["electrons"]["temperature"]["data"][0] / 1e3, "ti0": cp["t_i_average"]["data"][0] / 1e3,
            "ne0": ne[0] / 1e20, "ne_bar": num(r["ne_bar_cmd"]) / 1e20 if num(r["ne_bar_cmd"]) else None,
            "f_gw": v("f_gw"), "beta_n": v("beta_n_tot"), "h98": v("h98"), "i_bs": (v("i_bs") or 0) / 1e6,
            "v_loop": v("v_loop_end"), "p_rad": num(r["p_rad"]) / 1e6 if num(r["p_rad"]) else None,
            "p_sep": num(r["p_sep"]) / 1e6 if num(r["p_sep"]) else None,
            "p_lh": num(r["p_lh"]) / 1e6 if num(r["p_lh"]) else None,
            "w_fast": (v("w_fast") or 0) / 1e6, "li3": v("li3"), "tau_e": v("tau_e"),
        }

    m150, mflat = model_at(snap150), model_at(snapflat)
    flat = [{"key": k, "label": lab, "unit": u, "lit": lit, "src": src, "m150": m150.get(k), "mflat": mflat.get(k)}
            for k, lab, u, lit, src in LITERATURE_FLAT]
    rampdown = []
    variants = [("V0", "回放原指令", "6155 s 切 IC、6170 s EC 82 → 10 MW；n̄_e 按 Greenwald 份额恒定降"),
                ("V1", "RF 保持", "EC 82 MW 保持到 6193 s 再降到 10 MW"),
                ("V2", "H→L 判据放宽", "lh_off_factor 0.8 → 0.5"),
                ("V3", "粒子排出加快", "d_over_chi 0.1 → 0.3"),
                ("V4", "V1 + V2 + V3", "先降密度、保 H 模、后降加热")]
    for v, name, what in variants:
        if rd_dir is None or not (rd_dir / f"{v}.csv.summary.json").exists():
            continue
        s = json.loads((rd_dir / f"{v}.csv.summary.json").read_text(encoding="utf-8"))
        vr = list(csv.DictReader(open(rd_dir / f"{v}.csv", encoding="utf-8", newline="")))
        h2l = next((float(r["t"]) for r in vr if num(r["lh_phase"]) is not None and num(r["lh_phase"]) < 0.5), None)
        at = lambda t: min(vr, key=lambda r: abs(float(r["t"]) - t))  # noqa: E731
        last = vr[-1]
        rampdown.append({"id": v, "name": name, "what": what, "t_end": s.get("t_end"), "h2l": h2l,
                         "ip_end": num(last["ip_cmd"]) / 1e6, "p_rad_6170": num(at(6170)["p_rad"]) / 1e6,
                         "p_fus_6170": num(at(6170)["p_fus"]) / 1e6, "wall_s": round(s.get("wall_ms", 0) / 1e3)})
    zt = Z["traces"]
    #: the in-page viewer (replaces the MP4): solved equilibria, coils, wall, and the uniform-speed frames
    #: (HYBRID should be the uniform_json.py output; its keyframe twin works too, just unevenly spaced)
    view = {k: H[k] for k in ("equilibria", "coils", "limiter", "grid", "rho", "frames")}
    data = {
        "view": view, "uniform_dt": H["meta"].get("uniform_dt"),
        "rampdown": rampdown, "t_back": H["meta"].get("t_back"),
        "traces": H["traces"], "zerod": {k: zt[k] for k in ("t", "ip_ma", "p_aux_mw", "ne_bar_19", "te0_kev",
                                                             "p_fus_mw", "w_th_mj", "beta_n", "v_loop")},
        "t_hand": H["meta"].get("t_hand"), "t_last": H["meta"].get("t_last"),
        "flat": flat, "m150": m150, "mflat": mflat,
        "timeline": [{"t": t, "phase": p, "text": x, "src": s} for t, p, x, s in LITERATURE_TIMELINE],
        "run": {"windows": len(windows), "calls": sum(int(w["calls"] or 0) for w in windows),
                "steps": sum(int(w["kernel_steps"] or 0) for w in windows),
                "wall_s": round(sum(float(w["wall_ms"] or 0) for w in windows) / 1e3, 1),
                "stopped": summ.get("stopped"), "t_end": summ.get("t_end")},
    }
    page = Path(template).read_text(encoding="utf-8").replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"), 1)
    Path(out).write_text(page, encoding="utf-8")
    print(f"{out}: {Path(out).stat().st_size / 1e6:.2f} MB · flat-top row at {mflat['t']:g} s · {len(windows)} windows")


if __name__ == "__main__":
    main()
