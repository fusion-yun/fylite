#!/usr/bin/env python3
"""复现 Wei et al. 2026（AIP Advances 16, 085007）：一炮的关键剖面快速处理 → 加热沉积 → 输运反演。

两条命令::

    python wei2026.py profiles  --shot 63948 --t0 4 --t1 8 -o prof_63948.json     # 阶段 A：逐 TS 时刻剖面
    python wei2026.py transport --shot 81481 --time 5.3   -o tr_81481.json        # 阶段 A + B + C：一个时刻

与文献的同与不同（逐条写进结果 JSON 的 ``method``）：

* **同**：只给炮号；以 TS 时刻为基准、其余诊断在 50 ms 窗内配；n_e 主源反射计、缺时 TS；T_i 由 XCS 给芯部、
  台基取 T_i = T_e；局部稳健清洗一次剔一个（式 (2)–(7)）；H98 ≥ 0.7 走 H 模分段拟合（芯部样条 + mtanh +
  式 (11) 斜率积分过渡）、否则全段样条；T_e,sep = 50 eV；NRMSE 照式 (14)。
* **不同**：平衡是**本应用自己反演的**（档 M，磁测量），不读 P-EFIT——efit_east 树只作对拍（fylite 2026-09-15
  裁定）；ρ_tor 由 ``code/ladder`` 在这份平衡上描迹。LH 用 ``code/wave``（快速模型，不是 METIS），EC 用
  ``code/rf_ray``（射线追踪，不是 TORAY），输运用 ``code/interpretive``（不是 ONETWO）。清洗的阈值文献没公布，
  用 ``wei_profiles.CLEAN_DEFAULTS``。

★独立发行的约束不变：只用标准库与 ``libfylite.so``。诊断的树与节点名**从库里编进的装置事实解析**
（``<ids>/fylite:signal``）；``--signals FILE`` 可以给一份覆盖（同一形状的 JSON），本仓不写任何新节点名。
★实验数据不入仓：输出写在调用方给的路径；服务器地址在输出里一律记作 ``mds.invalid``。
"""
from __future__ import annotations

import argparse
import bisect
import datetime
import json
import math
import multiprocessing as mp
import sys
import time
from pathlib import Path

import kinetic_recon as K
import wei_profiles as W

APP = "east-kinetic-reconstruction/wei2026"
REF = "Wei et al. 2026, AIP Advances 16, 085007, doi:10.1063/5.0324803"
WINDOW_S = 0.050          #: 文献：其余诊断在以 TS 时刻为中心的 50 ms 窗内配
H98_THRESHOLD = 0.7       #: 文献：H98 ≥ 0.7 走 H 模分支；取不到 H98 时缺省 H 模
TE_SEP_KEV = 0.050        #: 文献：T_e,sep 固定 50 eV
N_OUT = 101
ETA_CD_DEFAULT = 1.0e19   #: code/wave 的 LH 驱动效率 n_e R0 I / P [A/W/m²]——内核记 EAST「量级 1e19」，不按文献调


def log(msg: str) -> None:
    print(f"[wei2026] {msg}", file=sys.stderr, flush=True)


# ================================================================================================ signals


def signal_map(doc: dict, override: dict | None) -> dict:
    """装置文档里的诊断绑定 → {ids: {量: {tree, node, scale, units}}}；``override`` 同形，逐项覆盖。"""
    out: dict = {}
    for ids in ("thomson_scattering", "reflectometer_profile", "spectrometer_x_ray_crystal", "ece", "nbi", "magnetics"):
        m = (doc.get(ids) or {}).get("fylite:signal")
        if isinstance(m, dict):
            out[ids] = dict(m)
    for ids, key in (("lh_antennas", "antenna"), ("ec_launchers", "beam")):
        items = []
        for a in (doc.get(ids) or {}).get(key) or []:
            items.append(dict(a))
        if items:
            out[ids] = items
    for ids, m in (override or {}).items():
        if isinstance(m, dict) and isinstance(out.get(ids), dict):
            out[ids] = dict(out[ids], **m)
        else:
            out[ids] = m
    return out


class Fetch:
    """一炮一个会话：每个节点的全时序只读一次（批处理的取数账从「每片」降到「每炮」）。"""

    def __init__(self, lib: K.Lib, shot: int, server, timeout_s: float):
        host, port = K.server_of(server)
        self.s = lib.mds_open(host, port, timeout_s)
        self.shot = int(shot)
        self.cache: dict = {}
        self.missing: list = []

    def close(self):
        self.s.close()

    def _open(self, tree: str):
        if self.s.tree != tree:
            self.s.open_tree(tree, self.shot)

    def series(self, tree: str, node: str):
        """(值, 时基) 或 None（节点不在或没数：是数据，不是故障）。"""
        key = ("series", tree.lower(), node)
        if key not in self.cache:
            try:
                self._open(tree)
                v, _ = self.s.read("data", node)
                tb, _ = self.s.read("dim_of", node)
                self.cache[key] = (v, tb)
            except (K.KernelError, K.Refused) as e:
                self.cache[key] = None
                self.missing.append({"tree": tree, "node": node, "why": K.sanitize(str(e))[-120:]})
        return self.cache[key]

    def array(self, tree: str, node: str):
        """(值, dims) 或 None。"""
        key = ("array", tree.lower(), node)
        if key not in self.cache:
            try:
                self._open(tree)
                self.cache[key] = self.s.read("data", node)
            except (K.KernelError, K.Refused) as e:
                self.cache[key] = None
                self.missing.append({"tree": tree, "node": node, "why": K.sanitize(str(e))[-120:]})
        return self.cache[key]

    def sig(self, spec: dict | None, kind: str = "series"):
        if not spec:
            return None
        r = (self.series if kind == "series" else self.array)(spec["tree"], spec["node"])
        if r is None:
            return None
        sc = float(spec.get("scale", 1.0))
        return ([v * sc for v in r[0]], r[1]) if sc != 1.0 else r


def rows_by_time(vals: list, dims: list, times: list):
    """二维节点按时间取行：线上 dims 快轴在前；哪一维是时间由时基长度判。返回 [行]（每行一个时刻）。"""
    if len(dims) < 2:
        return [vals]
    w, h = dims[0], len(vals) // dims[0]
    rows = [vals[i * w:(i + 1) * w] for i in range(h)]
    if len(times) == h:
        return rows
    if len(times) == w:
        return [[rows[i][j] for i in range(h)] for j in range(w)]
    return rows


def window_mean(v: list, tb: list, t: float, half: float) -> float | None:
    sel = [v[k] for k in range(min(len(v), len(tb))) if abs(tb[k] - t) <= half and math.isfinite(v[k])]
    if sel:
        return sum(sel) / len(sel)
    return None


# ================================================================================================ one shot's data


def thomson_series(f: Fetch, sm: dict) -> dict | None:
    """Thomson：自动判两种排布——行首是时刻（#81481 · #137985 一代），或没有时刻列、时基在 dim_of（#63948 一代）。"""
    ts = sm.get("thomson_scattering") or {}
    if "te" not in ts:
        return None
    te_a, ne_a = f.sig(ts["te"], "array"), f.sig(ts.get("ne"), "array")
    r_a, z_a = f.sig(ts.get("r"), "array"), f.sig(ts.get("z"), "array")
    if te_a is None or ne_a is None or r_a is None or z_a is None:
        return None
    nch = len(z_a[0])
    te_v, te_d = te_a
    w = te_d[0] if te_d else len(te_v)
    te_rows = [te_v[i * w:(i + 1) * w] for i in range(len(te_v) // w)]
    ne_rows = [ne_a[0][i * w:(i + 1) * w] for i in range(len(ne_a[0]) // w)]

    def err_rows(key):
        e = f.sig(ts.get(key), "array")
        if e is None or len(e[0]) != len(te_v):
            return None
        return [e[0][i * w:(i + 1) * w] for i in range(len(e[0]) // w)]
    te_e, ne_e = err_rows("te_err"), err_rows("ne_err")
    if w == nch + 1:
        layout = "column0=time"
        times = [row[0] for row in te_rows]
        strip = lambda rows: [row[1:] for row in rows] if rows else rows  # noqa: E731
        te_rows, ne_rows, te_e, ne_e = strip(te_rows), strip(ne_rows), strip(te_e), strip(ne_e)
    elif w == nch:
        layout = "no time column; dim_of"
        tb = f.series(ts["te"]["tree"], ts["te"]["node"])
        times = list(tb[1]) if tb else []
        if len(times) != len(te_rows):
            raise RuntimeError(f"Thomson: {len(te_rows)} profiles, dim_of has {len(times)} times")
    else:
        raise RuntimeError(f"Thomson: row length {w} fits neither {nch} channels nor {nch}+1")
    sc_te = float(ts["te"].get("scale", 1.0))
    return {"layout": layout, "times": times, "r": r_a[0][:nch], "z": z_a[0][:nch], "te": te_rows, "ne": ne_rows,
            "te_err": te_e, "ne_err": ne_e, "te_units": ts["te"].get("units", "eV"), "te_scale": sc_te}


def reflect_series(f: Fetch, sm: dict) -> dict | None:
    rf = sm.get("reflectometer_profile") or {}
    if "ne" not in rf:
        return None
    ne = f.sig(rf["ne"], "array")
    tb = f.series(rf["ne"]["tree"], rf["ne"]["node"])
    r = f.sig(rf.get("r"), "array")
    z = f.sig(rf.get("z"), "array")
    if ne is None or tb is None or r is None:
        return None
    times = list(tb[1])
    ne_rows, r_rows = rows_by_time(ne[0], ne[1], times), rows_by_time(r[0], r[1], times)
    return {"times": times, "ne": ne_rows, "r": r_rows, "z": (z[0][0] if z and z[0] else 0.0)}


def xcs_series(f: Fetch, sm: dict) -> dict | None:
    xc = sm.get("spectrometer_x_ray_crystal") or {}
    if "ti" not in xc:
        return None
    ti = f.sig(xc["ti"], "array")
    tb = f.series(xc["ti"]["tree"], xc["ti"]["node"])
    z = f.sig(xc.get("z"), "array")
    if ti is None or tb is None or z is None or len(ti[1]) < 2:
        return None
    times = list(tb[1])
    rows = rows_by_time(ti[0], ti[1], times)
    err = f.sig(xc.get("ti_err"), "array")
    err_rows = rows_by_time(err[0], err[1], times) if err and len(err[0]) == len(ti[0]) else None
    return {"times": times, "ti": rows, "ti_err": err_rows, "z": z[0][:len(rows[0])], "units": xc["ti"].get("units", "eV")}


def heating_series(f: Fetch, sm: dict) -> dict:
    out = {"lh": [], "ec": [], "nbi": []}
    for a in sm.get("lh_antennas") or []:
        la, re = f.sig(a.get("fylite:power_launched")), f.sig(a.get("fylite:power_reflected"))
        out["lh"].append({"name": a.get("name"), "frequency": a.get("frequency"), "n_parallel": a.get("fylite:n_parallel"),
                          "launched": la, "reflected": re})
    for b in sm.get("ec_launchers") or []:
        la = f.sig(b.get("fylite:power_launched"))
        out["ec"].append({"name": b.get("name"), "frequency": b.get("frequency"), "mode": b.get("mode"),
                          "launched": la, "baseline_window": b.get("fylite:baseline_window") or [-3.0, -1.0]})
    for key, spec in (sm.get("nbi") or {}).items():
        out["nbi"].append({"name": key, "launched": f.sig(spec)})
    return out


def heating_at(h: dict, t: float, half: float = 0.025) -> dict:
    """各系统在 t 的净功率 [W]：LH = 入射 − 反射；EC 减炮前基线（常值偏置）；NBI 是**源**功率（不是注入等离子体的）。"""
    res = {"lh": [], "ec": [], "nbi": []}
    for a in h["lh"]:
        if a["launched"] is None:
            continue
        pl = window_mean(*a["launched"], t, half) or 0.0
        pr = (window_mean(*a["reflected"], t, half) or 0.0) if a["reflected"] else 0.0
        res["lh"].append({"name": a["name"], "frequency": a["frequency"], "n_parallel": a["n_parallel"],
                          "launched": pl, "reflected": pr, "net": max(0.0, pl - pr)})
    for b in h["ec"]:
        if b["launched"] is None:
            continue
        v, tb = b["launched"]
        w0, w1 = b["baseline_window"]
        base = [v[k] for k in range(min(len(v), len(tb))) if w0 <= tb[k] <= w1]
        off = sum(base) / len(base) if base else 0.0
        p = (window_mean(v, tb, t, half) or 0.0) - off
        res["ec"].append({"name": b["name"], "frequency": b["frequency"], "mode": b["mode"], "baseline": off,
                          "net": max(0.0, p)})
    for n in h["nbi"]:
        if n["launched"] is None:
            continue
        #: NBI 在 #63948 是调制的（1L 峰 1.29 MW、均值约 0.2 MW）：±25 ms 窗取到哪个相位全凭运气，按 ±0.1 s 平均
        res["nbi"].append({"name": n["name"], "source_power": max(0.0, window_mean(*n["launched"], t, max(half, 0.1)) or 0.0)})
    res["p_lh"] = sum(a["net"] for a in res["lh"])
    res["p_ec"] = sum(b["net"] for b in res["ec"])
    res["p_nbi_source"] = sum(n["source_power"] for n in res["nbi"])
    return res


def pull_shot(lib: K.Lib, shot: int, chain: str, server, timeout_s: float, override: dict | None) -> dict:
    """一炮的全部原始序列（磁测量 · TF · Thomson · 反射计 · XCS · 加热 · 抗磁能 · 环电压），读一次。"""
    t0 = time.time()
    doc, res = lib.device("east", shot, chain)
    names = K.device_names(doc, res)
    sm = signal_map(doc, override)
    f = Fetch(lib, shot, server, timeout_s)
    try:
        def get(leaf, where):
            nd = leaf if leaf.startswith("\\") else "\\" + leaf
            return f.series(where, nd)
        # 磁测量：把归约要读的节点先全读进缓存（归约本身在各时刻上做）
        for nd in names["loops"] + names["probes"] + names["pf_nodes"] + [names["ip_node"]] + list(names["point_ne"] or []) \
                + list(names["point_fr"] or []):
            if nd:
                get(nd, names["tree"])
        if names["pcs_tree"]:                            #: Ip 的回退源（reduce_series 在主树 Ip 缺或 < 50 kA 时读它）
            get(r"\pcrl01", names["pcs_tree"])
        tf_mid = {"tf": None}
        mds = (doc.get("data_source") or {}).get("mdsplus") or {}
        th = thomson_series(f, sm)
        # TF 电流：节点选择按 TS 中段的一个时刻判（旧炮退到 btor_node，见 kinetic_recon.tf_series）
        t_mid = th["times"][len(th["times"]) // 2] if th and th["times"] else 5.0
        tf, tf_node = K.tf_series(get, names, mds, t_mid)
        tf_mid.update(tf=tf, node=tf_node)
        rf = reflect_series(f, sm)
        xc = xcs_series(f, sm)
        ti0 = f.sig((sm.get("spectrometer_x_ray_crystal") or {}).get("ti0"))
        heat = heating_series(f, sm)
        mag = sm.get("magnetics") or {}
        wdia = f.sig(mag.get("w_dia"))
        vloop = f.sig(mag.get("v_loop"))
    finally:
        f.close()
    return {"shot": int(shot), "chain": chain, "names": names, "signals": sm, "cache": f.cache, "tf": tf_mid["tf"],
            "tf_node": tf_mid.get("node"),
            "thomson": th, "reflect": rf, "xcs": xc, "ti0": ti0, "heating": heat, "w_dia": wdia, "v_loop": vloop,
            "missing": f.missing, "seconds": round(time.time() - t0, 1)}


def magnetics_at(shot_data: dict, t: float) -> dict:
    names, cache = shot_data["names"], shot_data["cache"]

    def get(leaf, where):
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        return cache.get(("series", where.lower(), nd))
    meas = K.reduce_series(get, shot_data["shot"], t, names, source=f"mdsplus:mds.invalid:{names['tree']}:{shot_data['shot']}")
    if shot_data["tf"] is not None:
        v, tb = shot_data["tf"]
        i_tf = window_mean(v, tb, t, 0.005)
        if i_tf is not None:
            meas["tf"] = {"node": shot_data.get("tf_node"), "i_tf_A": i_tf, "turns_total": K.TF_TURNS, "f_vac_Tm": 2e-7 * K.TF_TURNS * i_tf}
    return meas


# ================================================================================================ equilibrium


def equilibrium(lib: K.Lib, shot_data: dict, t: float, warm: dict | None, reject_sigma: float = 4.0) -> dict:
    """档 M（磁测量）：一段的第一片照本应用全扫；其后各片**继承**上一片的剔道与竖直设定点，只在它 ±8 mm 的 5 个设定点上解。"""
    meas = magnetics_at(shot_data, t)
    card, _ = lib.device("east", shot_data["shot"], shot_data["chain"])
    c = K.Case(lib, meas, card, "B+readmit")
    settings = dict(K.SETTINGS)
    if warm:
        for r in warm["rejected"]:
            names = c.loop_names if r["kind"] == "loop" else c.probe_names
            if r["index"] < len(names) and names[r["index"]] == r["name"]:
                (c.lw if r["kind"] == "loop" else c.pw)[r["index"]] = 0.0
        for r in warm.get("readmitted", []):
            if r["kind"] == "loop" and r["index"] < len(c.lw) and not r.get("reverted"):
                c.lw[r["index"]] = 1.0 / c.loop_sigma[r["index"]]
        zc = warm["zc"]
        saved = K.ZC_SCAN[:]
        K.ZC_SCAN[:] = [round(zc + d, 3) for d in (-0.008, -0.004, 0.0, 0.004, 0.008)]
        try:
            view, base = K.tier_m(c, reject_sigma, 2, 3, settings, False)
        finally:
            K.ZC_SCAN[:] = saved
        if base is None:                                 #: 继承的起点解不出：退回全扫
            c = K.Case(lib, meas, card, "B+readmit")
            view, base = K.tier_m(c, reject_sigma, 4, 3, settings, True)
    else:
        view, base = K.tier_m(c, reject_sigma, 4, 3, settings, True)
    if base is None:
        return {"status": "error", "why": view.get("error"), "meas": meas}
    fa, fi, zc = base
    rejected = list((warm or {}).get("rejected", [])) + [r for r in view["rejected"] if not r.get("reverted")]
    return {"status": "ok", "fa": fa, "fi": fi, "zc": zc, "meas": meas, "loop_start_rule": c.loop_start_rule,
            "rejected": rejected, "readmitted": view.get("readmitted", []),
            "chi2_per_dof": fa.get("chi2_per_dof"), "b_tor": c.b_tor, "card": card}


def eq_document(fa: dict, fi: dict) -> dict:
    """反演结果 → DD 形的平衡文档（内核自己的 COCOS 17 规：整圈 Wb、轴上极大）。"""
    b = fi["boundary"]
    return {"time_slice": {"profiles_2d": {"grid": {"dim1": fi["grid_r"], "dim2": fi["grid_z"]}, "psi": fi["psi"]},
                           "global_quantities": {"psi_axis": fa["psi_axis"], "psi_boundary": fa["psi_bnd"], "ip": fa["ip"],
                                                 "magnetic_axis": {"r": fa["axis_r"], "z": fa["axis_z"]}},
                           "profiles_1d": {"f": fi["fpol"], "q": fi["qpsi"], "psi_norm": fi["psin_1d"]},
                           "boundary": {"outline": {"r": [p[0] for p in b], "z": [p[1] for p in b]}}},
            "fylite:limiter": {"r": fi["limiter_r"], "z": fi["limiter_z"]},
            "vacuum_toroidal_field": {"r0": fa["rcentr"], "b0": fa["bcentr"]}, "fylite:psi_convention": 17}


LP = "equilibrium/time_slice/profiles_1d/"


def ladder(lib: K.Lib, eq: dict, n: int = 51) -> dict:
    lf, li, _ = lib.door("code/ladder", {"n_surfaces": n, "axis_node": 1, "edge": 0.995}, {"equilibrium": eq})
    lad = {k[len(LP):]: v for k, v in li.items() if k.startswith(LP)}
    lad["facts"] = lf
    return lad


class RhoMap:
    """ψ_N ↔ ρ_tor,N（ρ_tor / ρ_b），在本片平衡的描迹梯子上；梯子最外一面（ψ_N 0.995）以外按 √ψ_N 的斜率外推。"""

    def __init__(self, fa: dict, fi: dict, lad: dict):
        self.fa, self.fi = fa, fi
        self.pn = lad["psi_norm"]
        rb = lad["rho_tor"][-1]
        # ρ_b：梯子最外一面到 ψ_N = 1 按 √ψ_N 外推（面 0.995 与分界面只差 0.25 %）
        self.rho_b = rb / math.sqrt(self.pn[-1]) if self.pn[-1] > 0 else rb
        self.rhon = [v / self.rho_b for v in lad["rho_tor"]]

    def rho(self, psin: float) -> float:
        if psin <= 0:
            return 0.0
        if psin >= self.pn[-1]:
            return self.rhon[-1] * math.sqrt(psin / self.pn[-1])
        return K.interp(psin, self.pn, self.rhon)

    def psin(self, rho: float) -> float:
        if rho >= self.rhon[-1]:
            return self.pn[-1] * (rho / self.rhon[-1]) ** 2
        return K.interp(rho, self.rhon, self.pn)

    def at(self, r: float, z: float) -> float:
        return self.rho(K.psin_at(self.fa, self.fi, r, z))

    def min_on_chord(self, z: float, r_lo: float = 1.40, r_hi: float = 2.40) -> float:
        """水平弦（高度 z）上最内的一面：切向弦积分诊断的 ρ 标签。"""
        best = min(K.psin_at(self.fa, self.fi, r_lo + (r_hi - r_lo) * k / 200, z) for k in range(201))
        return self.rho(best)


# ================================================================================================ profiles


def point_ne(lib: K.Lib, eq: dict, rm: "RhoMap"):
    """POINT 11 弦的线积分密度 → ``code/chords`` 在本片平衡上拟 n_e = n_e0 (1 − ψ_N²)^α（内核的剖面族，x = ψ_N）。
    ★文献没有这一路：它的 n_e 只有反射计与 TS。本应用在两者都用不了时（#81481：没有反射计，5.517 s 的 TS n_e 有
    1–4×10²⁰ 的坏道）拿它顶上，并照实标出来源。返回 (ρ → n_e[1e19], 事实) 或 None。"""
    p = (eq["meas"].get("point") or {})
    nel, w = p.get("bnel"), p.get("fwtnel")
    if not nel or not w or sum(w) < 3:
        return None
    try:
        fit, _, _ = lib.door("code/chords", {"ne0": 3e19, "rows": 0},
                             {"device": eq["card"], "equilibrium": K._eq_doc(eq["fa"], eq["fi"]),
                              "discharge": {"fylite:chord_nel": [v * 1e19 for v in nel], "fylite:chord_nel_weight": w}})
    except (K.KernelError, K.Refused):
        return None
    n0, al = fit.get("fit_ne0"), fit.get("fit_peaking")
    if not n0 or al is None:
        return None
    return (lambda r: n0 * 1e-19 * max(0.0, 1.0 - rm.psin(min(r, 1.0)) ** 2) ** al,
            {"ne0": K._r(n0), "peaking": K._r(al, 4), "chi2": K._r(fit.get("fit_chi2"), 4), "chords": int(sum(w))})




def ts_points(th: dict, it: int, rm: RhoMap):
    """TS 第 it 个脉冲 → (ρ, T_e[keV], n_e[1e19])，丢非有限与非正值；ψ_N > 1 的点只留给 n_e 边界参照。"""
    pts = []
    for k, (r, z) in enumerate(zip(th["r"], th["z"])):
        te, ne = th["te"][it][k] * (1e-3 if th["te_units"] == "eV" else 1.0), th["ne"][it][k]
        if not (K.fin(te) and K.fin(ne)) or te <= 0 or ne <= 0:
            continue
        pts.append((rm.at(r, z), te, ne * 1e-19))
    pts.sort()
    return pts


def refl_points(rf: dict, t: float, rm: RhoMap):
    """反射计：TS 时刻 ±25 ms 内各剖面按径向位置取中位（10 ms 一幅，约 5 幅）。"""
    idx = [k for k, tt in enumerate(rf["times"]) if abs(tt - t) <= WINDOW_S / 2]
    if not idx:
        return []
    npt = len(rf["ne"][idx[0]])
    pts = []
    for j in range(npt):
        ns = [rf["ne"][k][j] for k in idx if j < len(rf["ne"][k]) and K.fin(rf["ne"][k][j]) and rf["ne"][k][j] > 0]
        rs = [rf["r"][k][j] for k in idx if j < len(rf["r"][k]) and K.fin(rf["r"][k][j])]
        if ns and rs:
            pts.append((rm.at(K.median(rs), rf["z"]), K.median(ns) * 1e-19))
    pts.sort()
    return pts


def xcs_points(xc: dict, t: float, rm: RhoMap):
    """XCS：TS 时刻 ±25 ms 内均值（没有则取 ±50 ms 内最近一幅）；每道弦标在它切到的最内一面。"""
    idx = [k for k, tt in enumerate(xc["times"]) if abs(tt - t) <= WINDOW_S / 2]
    if not idx:
        k = min(range(len(xc["times"])), key=lambda i: abs(xc["times"][i] - t))
        if abs(xc["times"][k] - t) > WINDOW_S:
            return []
        idx = [k]
    pts = []
    for j, z in enumerate(xc["z"]):
        v = [xc["ti"][k][j] for k in idx if K.fin(xc["ti"][k][j]) and xc["ti"][k][j] > 0]
        if v:
            pts.append((rm.min_on_chord(z), sum(v) / len(v) * 1e-3))
    pts.sort()
    return pts


def ipb98(ip_ma, bt, n19, p_mw, r, a, kappa, m=2.0):
    """IPB98(y,2) 约束时间 [s]（ITER Physics Basis 1999）。"""
    if min(ip_ma, bt, n19, p_mw, r, a, kappa) <= 0:
        return float("nan")
    return 0.0562 * ip_ma ** 0.93 * bt ** 0.15 * n19 ** 0.41 * p_mw ** -0.69 * r ** 1.97 * kappa ** 0.78 * (a / r) ** 0.58 * m ** 0.19


def volume_integral(f, lad: dict, rho_b: float) -> float:
    rt, vp = lad["rho_tor"], lad["dvolume_drho_tor"]
    return sum(0.5 * (f(rt[k] / rho_b) * vp[k] + f(rt[k - 1] / rho_b) * vp[k - 1]) * (rt[k] - rt[k - 1]) for k in range(1, len(rt)))


def line_average(prof, rm: RhoMap, z: float) -> float:
    """中平面（z）水平弦上的线平均：LCFS 内的段。"""
    vals = []
    for k in range(401):
        r = 1.35 + 1.1 * k / 400
        pn = K.psin_at(rm.fa, rm.fi, r, z)
        if 0 <= pn <= 1:
            vals.append(prof(rm.rho(pn)))
    return sum(vals) / len(vals) if vals else float("nan")


def fit_slice(th, rf, xc, it: int, rm: RhoMap, lad: dict, fa: dict, heat: dict, w_dia, v_loop, meas: dict,
              b_tor: float, clean_opts: dict | None = None, ti0=None, point=None) -> dict:
    """一个 TS 时刻：取点 → 清洗 → 定 L / H → 分段拟合 → NRMSE；另算 H98 的账。"""
    t = th["times"][it]
    ts = ts_points(th, it, rm)
    te_pts = [(r, te) for r, te, _ in ts if r <= 1.0]
    ne_ts = [(r, ne) for r, _, ne in ts if r <= 1.05]
    ne_rf = refl_points(rf, t, rm) if rf else []
    ne_src = "reflectometer" if len([p for p in ne_rf if p[0] <= 1.0]) >= 8 else "thomson"
    ne_pts = [p for p in ne_rf if p[0] <= 1.05] if ne_src == "reflectometer" else ne_ts
    ti_pts = xcs_points(xc, t, rm) if xc else []

    def cleaned(pts):
        xs, ys, ws = W.merge_ties([p[0] for p in pts], [p[1] for p in pts], [1.0] * len(pts), tol=1e-4)
        c = W.clean_profile(xs, ys, clean_opts) if len(xs) >= 5 else {"keep": [True] * len(xs), "removed": []}
        return xs, ys, c
    tx, ty, tc = cleaned(te_pts)
    nx, ny, nc = cleaned(ne_pts)
    ne_point = None
    if ne_src == "thomson" and point is not None:
        #: TS n_e 可用与否：清洗后 L 模样条的 NRMSE > 0.1 视为不可用（坏道多到局部稳健尺度也压不住），改用 POINT
        kx = [x for x, k in zip(nx, nc["keep"]) if k]
        ky = [y for y, k in zip(ny, nc["keep"]) if k]
        bad = len(kx) < 5 or W.nrmse(kx, ky, W.fit_profile(kx, ky, mode="L")["profile"]) > 0.1
        if bad:
            ne_src, ne_point = "point", point
    tkx = [x for x, k in zip(tx, tc["keep"]) if k]
    tky = [y for y, k in zip(ty, tc["keep"]) if k]
    nkx = [x for x, k in zip(nx, nc["keep"]) if k]
    nky = [y for y, k in zip(ny, nc["keep"]) if k]
    if len(tkx) < 5 or (len(nkx) < 5 and ne_point is None):
        return {"time_s": t, "status": "skipped", "why": f"too few points (Te {len(tkx)}, ne {len(nkx)})"}
    # H98：先用 L 模全段样条算一份 W_th（或用抗磁能），P_loss = LH + EC + NBI 源 + 欧姆
    te_l = W.fit_profile(tkx, tky, mode="L")["profile"]
    ne_l = ne_point[0] if ne_point else W.fit_profile(nkx, nky, mode="L")["profile"]
    ti_guess = (lambda r: te_l(r) * (ti_pts[0][1] / te_l(ti_pts[0][0]) if ti_pts else 1.0))
    rho_b = rm.rho_b
    w_th = volume_integral(lambda r: 1.5 * ne_l(r) * 1e19 * (te_l(r) + ti_guess(r)) * 1e3 * K.E_CHARGE, lad, rho_b)
    w_d = window_mean(*w_dia, t, 0.010) if w_dia else None
    ip = abs(float(meas["plasma"]))
    vl = window_mean(*v_loop, t, 0.025) if v_loop else None
    p_oh = abs(vl * ip) if vl is not None else 0.0
    p_loss = heat["p_lh"] + heat["p_ec"] + heat["p_nbi_source"] + p_oh
    lf = lad["facts"]
    r_geo = lad.get("fylite:r_major", [fa["rcentr"]])[-1]
    kappa = (lad.get("elongation") or [1.6])[-1]
    n_line = line_average(ne_l, rm, fa["axis_z"])
    w_use, w_from = (w_d, "diamagnetic") if w_d and w_d > 0 else (w_th, "kinetic (L-fit, T_i scaled to XCS)")
    tau98 = ipb98(ip / 1e6, b_tor, n_line, p_loss / 1e6, r_geo, lf["a_minor"], kappa)
    h98 = (w_use / p_loss) / tau98 if p_loss > 0 and math.isfinite(tau98) else float("nan")
    mode = "H" if not math.isfinite(h98) or h98 >= H98_THRESHOLD else "L"
    te_f = W.fit_profile(tkx, tky, mode=mode, y_sep=TE_SEP_KEV)
    ne_f = {"profile": ne_point[0], "mode": "point"} if ne_point else W.fit_profile(nkx, nky, mode=mode, y_sep=None)
    te_p, ne_p = te_f["profile"], ne_f["profile"]
    # T_i：芯部 XCS 样条；台基取 T_i = T_e（文献），过渡段照式 (11)
    ti_p, ti_note = None, None
    if len(ti_pts) >= 2:
        core_x = [p[0] for p in ti_pts if p[0] <= 0.8]
        core_y = [p[1] for p in ti_pts if p[0] <= 0.8]
        if te_f["mode"] == "H" and len(core_x) >= 2:
            core = W.axis_spline(core_x + [0.9, 0.95, 1.0], core_y + [te_p(0.9), te_p(0.95), te_p(1.0)], None, 1e-3)
            ti_p = W.Profile(core, te_f["profile"].ped, te_f["profile"].rho_s, te_f["rho_e"])
            L = ti_p.rho_e - ti_p.rho_s
            ti_p.delta = ti_p.ped(ti_p.rho_e) - (ti_p.fs + (ti_p.ss + ti_p.se) * L / 2)
            ti_note = "core XCS spline; pedestal T_i = T_e (ρ > ρ_e); Eq. (11) transition"
        else:
            xs = core_x + [0.9, 0.95, 1.0]
            ys = core_y + [te_p(0.9), te_p(0.95), te_p(1.0)]
            ti_p = W.axis_spline(xs, ys, None, 1e-3)
            ti_note = "XCS spline, edge tied to T_e (ρ ≥ 0.9)"
    if ti_p is None and ti0 is not None:
        #: 没有 XCS 剖面（#81481 一代）但有芯部 T_i0 时序：T_i = T_i,edge + (T_i0 − T_i,edge)(1 − ρ²)^1.5（ρ ≤ 0.9），
        #: T_i,edge 取 T_e(0.9)（台基 T_i = T_e，文献），过 0.9 以后 T_i = T_e。★这是本应用的构造，文献对这种炮没说怎么做。
        #: 不用「T_e 形状按 T_i0/T_e(0) 缩放」：LH 只加热电子、T_e 极尖（#81481 5.517 s：T_e(0) 6 keV、T_e(0.6) 0.54 keV），
        #: 缩放后中半径 T_i ≈ 0.16 T_e，电子–离子交换被人为放大到等于全部注入功率（实测 2.83 MW 对 2.80 MW）。
        v0 = window_mean(*ti0, t, WINDOW_S / 2) or window_mean(*ti0, t, WINDOW_S)
        if v0 and v0 > 0:
            t0k, tek = v0 * 1e-3, te_p(0.9)

            def ti_from_ti0(r, t0k=t0k, tek=tek):
                return tek + (t0k - tek) * max(0.0, 1.0 - (r / 0.9) ** 2) ** 1.5 if r <= 0.9 else te_p(r)
            ti_p, ti_note = ti_from_ti0, (f"no XCS profile: T_i = T_i,edge + (T_i0 − T_i,edge)(1 − (ρ/0.9)²)^1.5 with core "
                                          f"T_i0 = {v0:.0f} eV, T_i = T_e for ρ ≥ 0.9 (assumed shape)")
            ti_pts = [(0.0, v0 * 1e-3)]
    grid = [k / (N_OUT - 1) for k in range(N_OUT)]

    def floored(prof):
        #: 输出剖面的地板：峰值的 1 %（最外一个测点以外样条线性外推会过零）；NRMSE 只在测点上算，不受影响
        vals = [prof(r) for r in grid]
        lo = 0.01 * max(vals)
        return [max(v, lo) for v in vals]
    out = {"time_s": t, "status": "ok", "mode": mode, "h98": K._r(h98, 4), "h98_inputs": {
        "w": K._r(w_use), "w_from": w_from, "w_th_kinetic": K._r(w_th), "w_dia": K._r(w_d) if w_d else None,
        "p_loss": K._r(p_loss), "p_lh": K._r(heat["p_lh"]), "p_ec": K._r(heat["p_ec"]),
        "p_nbi_source": K._r(heat["p_nbi_source"]), "p_ohm": K._r(p_oh), "ip": K._r(ip), "b_tor": K._r(b_tor),
        "n_line_19": K._r(n_line, 4), "r_geo": K._r(r_geo, 4), "a": K._r(lf["a_minor"], 4), "kappa": K._r(kappa, 4),
        "tau98": K._r(tau98, 4)},
        "rho": K._r(grid, 5),
        "te": {"source": "thomson", "fit": K._r(floored(te_p), 5), "rho_e": K._r(te_f.get("rho_e"), 4),
               "pedestal": te_f.get("pedestal"), "points": _pts(tx, ty, tc), "nrmse": K._r(W.nrmse(tkx, tky, te_p), 4)},
        "ne": {"source": ne_src, "fit": K._r(floored(ne_p), 5), "rho_e": K._r(ne_f.get("rho_e"), 4),
               "pedestal": ne_f.get("pedestal"), "points": _pts(nx, ny, nc), "nrmse": None if ne_point else K._r(W.nrmse(nkx, nky, ne_p), 4),
               "n_reflectometer": len(ne_rf), "n_thomson": len(ne_ts),
               **({"point_fit": ne_point[1], "note": "Thomson n_e unusable (cleaned L-spline NRMSE > 0.1), no reflectometer: POINT chord fit"}
                  if ne_point else {})},
        "ti": ({"source": "xcs", "fit": K._r(floored(ti_p), 5), "note": ti_note,
                "points": [[K._r(p[0], 4), K._r(p[1], 4)] for p in ti_pts],
                "nrmse": K._r(W.nrmse([p[0] for p in ti_pts], [p[1] for p in ti_pts], ti_p), 4) if len(ti_pts) >= 2 else None}
               if ti_p else {"source": None, "why": "no XCS profile in the 50 ms window"})}
    if ti_p is not None and ti_note and ti_note.startswith("no XCS"):
        out["ti"]["source"] = "xcs core T_i0"
    for key, f in (("te", te_f), ("ne", ne_f)):
        if f.get("pedestal"):
            out[key]["pedestal"] = {k: K._r(v, 5) for k, v in f["pedestal"].items()}
    return out


def _pts(xs, ys, c):
    removed = {i: (s, side) for i, s, side in c["removed"]}
    return [[K._r(x, 4), K._r(y, 4), 0 if i in removed else 1] for i, (x, y) in enumerate(zip(xs, ys))]


# ================================================================================================ batch


_WORKER: dict = {}


def _init_worker(lib_path: str, shot_data: dict):
    _WORKER["lib"] = K.Lib(Path(lib_path))
    _WORKER["shot"] = shot_data


def _run_chunk(args):
    chunk, clean_opts = args
    return chunk_job(_WORKER["lib"], _WORKER["shot"], chunk, clean_opts)


def chunk_job(lib: K.Lib, sd: dict, chunk: list, clean_opts: dict | None) -> list:
    """一段相邻的 TS 时刻，顺序做：第一片全扫，其后每片从**上一片**热启动（竖直位置随时间漂，#63948 从 −30 mm
    漂到 +18 mm——只从全炮第一片热启动时，后面的片几乎都退回全扫）。"""
    out, warm = [], None
    for it in chunk:
        r = slice_job(lib, sd, it, warm, clean_opts)
        warm = r.get("_warm") or warm
        out.append(r)
    return out


def slice_job(lib: K.Lib, sd: dict, it: int, warm: dict | None, clean_opts: dict | None) -> dict:
    th = sd["thomson"]
    t = th["times"][it]
    t0 = time.time()
    try:
        eq = equilibrium(lib, sd, t, warm)
        if eq["status"] != "ok":
            return {"time_s": t, "status": "error", "why": f"equilibrium: {eq['why']}"}
        t1 = time.time()
        lad = ladder(lib, eq_document(eq["fa"], eq["fi"]))
        rm = RhoMap(eq["fa"], eq["fi"], lad)
        heat = heating_at(sd["heating"], t)
        pt = point_ne(lib, eq, rm)
        res = fit_slice(th, sd["reflect"], sd["xcs"], it, rm, lad, eq["fa"], heat, sd["w_dia"], sd["v_loop"],
                        eq["meas"], eq["b_tor"], clean_opts, sd.get("ti0"), pt)
        res["equilibrium"] = {"zc": eq["zc"], "chi2_per_dof": K._r(eq["chi2_per_dof"], 4), "q0": K._r(eq["fa"]["q0"], 4),
                              "q95": K._r(eq["fa"]["q95"], 4), "rho_b": K._r(rm.rho_b, 5), "a": K._r(lad["facts"]["a_minor"], 4),
                              "n_rejected": len(eq["rejected"]), "loop_start_rule": eq["loop_start_rule"], "warm": warm is not None}
        res["heating"] = {k: (K._r(v) if isinstance(v, float) else v) for k, v in heat.items()}
        res["seconds"] = {"equilibrium": round(t1 - t0, 2), "total": round(time.time() - t0, 2)}
        res["_warm"] = {"zc": eq["zc"], "rejected": eq["rejected"], "readmitted": eq["readmitted"]}
        return res
    except Exception as e:  # noqa: BLE001 —— 一片出错是一片的读数，不让整炮失败
        return {"time_s": t, "status": "error", "why": K.sanitize(f"{type(e).__name__}: {e}")[-300:]}


def cmd_profiles(a) -> int:
    lib_path = Path(a.lib) if a.lib else K.DEFAULT_LIB
    lib = K.Lib(lib_path)
    override = json.loads(Path(a.signals).read_text()) if a.signals else None
    t_start = time.time()
    try:
        sd = pull_shot(lib, a.shot, a.chain, a.server, a.timeout, override)
    except (K.KernelError, K.Refused) as e:
        log(f"#{a.shot}: 取不到 —— {K.sanitize(str(e))}")
        Path(a.out).write_text(json.dumps({"shot": a.shot, "status": "unavailable", "why": K.sanitize(str(e))},
                                          ensure_ascii=False) + "\n")
        return 2
    th = sd["thomson"]
    if th is None:
        log("没有 Thomson：以 TS 时刻为基准的批处理无从起步")
        return 2
    idx = [k for k, t in enumerate(th["times"]) if a.t0 <= t <= a.t1]
    log(f"#{a.shot}: 取数 {sd['seconds']} s；TS {len(th['times'])} 个脉冲（{th['layout']}），[{a.t0}, {a.t1}] s 内 {len(idx)} 片")
    t_fetch = time.time()
    clean_opts = json.loads(a.clean) if a.clean else None
    results = []
    nw = max(1, min(a.workers, len(idx)))
    chunks = [idx[k * len(idx) // nw:(k + 1) * len(idx) // nw] for k in range(nw)]
    chunks = [c for c in chunks if c]
    jobs = [(c, clean_opts) for c in chunks]
    if nw > 1:
        ctx = mp.get_context("fork")
        with ctx.Pool(nw, initializer=_init_worker, initargs=(str(lib_path), sd)) as pool:
            for part in pool.imap(_run_chunk, jobs):
                results.extend(part)
    else:
        for c in chunks:
            results.extend(chunk_job(lib, sd, c, clean_opts))
    results.sort(key=lambda r: r["time_s"])
    for r in results:
        log(f"  {r['time_s']:.3f} s: {r['status']} {r.get('why', '')[:80]} "
            f"(eq {r.get('seconds', {}).get('equilibrium')} s, warm {r.get('equilibrium', {}).get('warm')})")
    for r in results:
        r.pop("_warm", None)
    ok = [r for r in results if r["status"] == "ok"]

    def stats(key):
        v = [r[key]["nrmse"] for r in ok if r.get(key, {}).get("nrmse") is not None]
        return {"n": len(v), "mean": K._r(sum(v) / len(v), 4) if v else None, "min": K._r(min(v), 4) if v else None,
                "max": K._r(max(v), 4) if v else None}
    out = {"@type": "fylite:Wei2026Profiles", "app": APP, "version": K.VERSION, "reference": REF,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "shot": a.shot, "window_s": [a.t0, a.t1], "source": f"mdsplus:mds.invalid:{a.shot}",
           "method": method_card(clean_opts),
           "data": {"thomson_layout": th["layout"], "thomson_pulses": len(th["times"]),
                    "reflectometer": sd["reflect"] is not None, "xcs_profile": sd["xcs"] is not None,
                    "diamagnetic_energy": sd["w_dia"] is not None, "loop_voltage": sd["v_loop"] is not None,
                    "missing": sd["missing"]},
           "summary": {"slices": len(results), "ok": len(ok), "nrmse_te": stats("te"), "nrmse_ne": stats("ne"),
                       "nrmse_ti": stats("ti"), "modes": {m: sum(1 for r in ok if r["mode"] == m) for m in ("L", "H")},
                       "seconds": {"fetch": sd["seconds"], "slices_wall": round(time.time() - t_fetch, 1),
                                   "total": round(time.time() - t_start, 1), "workers": a.workers}},
           "slices": results}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    s = out["summary"]
    log(f"-> {a.out}: {s['ok']}/{s['slices']} 片；NRMSE T_e {s['nrmse_te']}，n_e {s['nrmse_ne']}；"
        f"取数 {sd['seconds']} s + 各片 {s['seconds']['slices_wall']} s")
    return 0 if ok else 1


def method_card(clean_opts):
    return {"cleaning": dict(W.CLEAN_DEFAULTS, **(clean_opts or {}), note="thresholds not published by the paper; defaults"),
            "fit": dict(W.FIT_DEFAULTS, te_sep_keV=TE_SEP_KEV, h98_threshold=H98_THRESHOLD,
                        join_note="Eq. (11) plus a value correction δ((ρ−ρ_s)/(ρ_e−ρ_s))² at ρ_e (not in the paper)"),
            "equilibrium": "own magnetic reconstruction (tier M), warm-started from the first slice; not P-EFIT",
            "rho": "rho_tor_norm from code/ladder on that equilibrium",
            "window_s": WINDOW_S}


def advance_in_vacuum(r0: float, z0: float, pol_deg: float, tor_deg: float, r_max: float):
    """EC 束从发射镜（文献给的是 R ≈ 3 m 处，在反演网格外）沿直线走进网格：真空里的直线传播是精确的，
    到新点后把方向在当地 (R, φ, Z) 框架里重算成内核的两个角。内核约定：k̂ = (−cosθp·cosθt, −sinθt, −sinθp·cosθt)，
    θp > 0 朝下，θt > 0 朝 −y，θp = θt = 0 径向向内（fylite_kernel rfray.rs Launch::from_launcher）。"""
    tp, tt = math.radians(pol_deg), math.radians(tor_deg)
    k = (-math.cos(tp) * math.cos(tt), -math.sin(tt), -math.sin(tp) * math.cos(tt))
    x, y, z = r0, 0.0, z0
    step = 0.001
    for _ in range(5000):
        if math.hypot(x, y) <= r_max:
            break
        x, y, z = x + step * k[0], y + step * k[1], z + step * k[2]
    r, phi = math.hypot(x, y), math.atan2(y, x)
    kr = k[0] * math.cos(phi) + k[1] * math.sin(phi)
    kp = -k[0] * math.sin(phi) + k[1] * math.cos(phi)
    tt2 = math.asin(max(-1.0, min(1.0, -kp)))
    tp2 = math.atan2(-k[2] / math.cos(tt2), -kr / math.cos(tt2))
    return r, z, math.degrees(tp2), math.degrees(tt2)


def source_rows(fi: dict, code: str) -> dict:
    """``code/wave`` · ``code/rf_ray`` 的 core_sources 输出 → {grid_psin, p_e, j}（按后缀认键，不猜下标拼法）。"""
    cs = {k: v for k, v in fi.items() if k.startswith("core_sources")}

    def pick(suffix):
        for k, v in cs.items():
            if k.endswith(suffix):
                return v
        return None
    out = {"grid_psin": pick("grid/psi_norm"), "p_e": pick("electrons/energy"), "j": pick("j_parallel")}
    if out["grid_psin"] is None or out["p_e"] is None:
        raise RuntimeError(f"{code}: no core_sources psi_norm / electrons/energy in its output (keys: {sorted(cs)[:12]})")
    return out


# ================================================================================================ transport (B + C)


def cmd_transport(a) -> int:
    lib_path = Path(a.lib) if a.lib else K.DEFAULT_LIB
    lib = K.Lib(lib_path)
    override = json.loads(Path(a.signals).read_text()) if a.signals else None
    t_start = time.time()
    sd = pull_shot(lib, a.shot, a.chain, a.server, a.timeout, override)
    th = sd["thomson"]
    if th is None:
        log("没有 Thomson")
        return 2
    it = min(range(len(th["times"])), key=lambda k: abs(th["times"][k] - a.time))
    t = th["times"][it]
    log(f"#{a.shot}: 要 {a.time} s，最近的 TS 脉冲 {t:.3f} s（本炮只存 {len(th['times'])} 幅）")
    eq = equilibrium(lib, sd, t, None)
    if eq["status"] != "ok":
        log(f"平衡解不出：{eq['why']}")
        return 1
    fa, fi = eq["fa"], eq["fi"]
    eqd = eq_document(fa, fi)
    lad = ladder(lib, eqd)
    rm = RhoMap(fa, fi, lad)
    heat = heating_at(sd["heating"], t)
    pt = point_ne(lib, eq, rm)
    prof = fit_slice(th, sd["reflect"], sd["xcs"], it, rm, lad, fa, heat, sd["w_dia"], sd["v_loop"], eq["meas"],
                     eq["b_tor"], None, sd.get("ti0"), pt)
    if prof["status"] != "ok":
        log(f"剖面没做成：{prof.get('why')}")
        return 1
    grid = prof["rho"]
    te = [v * 1e3 for v in prof["te"]["fit"]]
    ne = [v * 1e19 for v in prof["ne"]["fit"]]
    ti = [v * 1e3 for v in prof["ti"]["fit"]] if prof["ti"].get("fit") else None
    psin_grid = [rm.psin(r) for r in grid]
    cp_psi = {"profiles_1d": {"grid": {"psi_norm": psin_grid}, "electrons": {"temperature": te, "density": ne}}}
    sources, report = [], {}
    # ---- B: LH（code/wave）
    ants = [x for x in heat["lh"] if x["net"] > 0]
    if ants:
        lh_doc = {"antenna": [{"name": x["name"], "frequency": x["frequency"], "power_launched": {"data": x["launched"]},
                               "power_reflected": {"data": x["reflected"]},
                               "fylite:n_parallel_min": x["n_parallel"][0], "fylite:n_parallel_max": x["n_parallel"][1]}
                              for x in ants]}
        u_lo, u_hi = (float(v) for v in a.lh_upshift.split(","))
        wf, wi, wn = lib.door("code/wave", {"eta_cd": a.eta_cd, "upshift_min": u_lo, "upshift_max": u_hi}, {"equilibrium": eqd, "core_profiles": cp_psi,
                                                                  "lh_antennas": lh_doc})
        sources.append(dict(source_rows(wi, "code/wave"), name="lh"))
        report["lh"] = {"i_lh": K._r(wf.get("i_lh")), "p_absorbed": K._r(wf.get("p_absorbed")), "upshift": [u_lo, u_hi],
                        "deposition": {"psin": K._r(sources[-1]["grid_psin"], 5),
                                       "rho": K._r([rm.rho(v) for v in sources[-1]["grid_psin"]], 5),
                                       "p_e": K._r(sources[-1]["p_e"], 5),
                                       "j": K._r(sources[-1]["j"], 5) if sources[-1]["j"] else None},
                        "p_deposited": K._r(wf.get("p_deposited")), "eta_cd": a.eta_cd,
                        "eta_cd_for_paper_181kA": K._r(a.eta_cd * 181.3e3 / wf["i_lh"], 4) if wf.get("i_lh") else None,
                        "notes": wn, "antennas": ants}
    # ---- B: EC（code/rf_ray；发射几何要用户给——fylite 记它为未知）
    ec_on = [b for b in heat["ec"] if b["net"] > 0]
    if ec_on and a.ec_launch:
        r_m, z_m, pol_m, tor_m = (float(v) for v in a.ec_launch.split(","))
        #: 发射点在反演网格外时，沿束直线走到网格边内 2 cm（真空传播，物理不变）
        r0, z0, pol, tor = advance_in_vacuum(r_m, z_m, pol_m, tor_m, fi["grid_r"][-1] - 0.02)
        beams = [{"name": b["name"], "frequency": {"data": b["frequency"]}, "power_launched": {"data": b["net"]},
                  "launching_position": {"r": r0, "z": z0}, "fylite:angle_pol": math.radians(pol),
                  "fylite:angle_tor": math.radians(tor), "mode": b["mode"]} for b in ec_on]
        cp_ec = {"profiles_1d": dict(cp_psi["profiles_1d"], zeff=[a.zeff] * len(grid))}
        eqd_l = json.loads(json.dumps(eqd))
        eqd_l["time_slice"]["profiles_1d"].update({"psi_norm": lad["psi_norm"], "rho_tor": lad["rho_tor"],
                                                   "dvolume_drho_tor": lad["dvolume_drho_tor"]})
        ef, ei, en = lib.door("code/rf_ray", {"deposit": 1, "current_drive": 1, "zeff": a.zeff},
                              {"equilibrium": eqd, "core_profiles": cp_ec, "ec_launchers": {"beam": beams}})
        sources.append(dict(source_rows(ei, "code/rf_ray"), name="ec"))
        report["ec"] = {"p_absorbed": K._r(ef.get("power_absorbed")), "i_ec": K._r(ef.get("current_driven")),
                        "deposition": {"psin": K._r(sources[-1]["grid_psin"], 5),
                                       "rho": K._r([rm.rho(v) for v in sources[-1]["grid_psin"]], 5),
                                       "p_e": K._r(sources[-1]["p_e"], 5),
                                       "j": K._r(sources[-1]["j"], 5) if sources[-1]["j"] else None},
                        "launch": {"r": r0, "z": z0, "angle_pol_deg": pol, "angle_tor_deg": tor},
                        "launch_mirror": {"r": r_m, "z": z_m, "angle_pol_deg": pol_m, "angle_tor_deg": tor_m}, "notes": en}
    elif ec_on:
        report["ec"] = {"skipped": True, "p_net": K._r(heat["p_ec"]),
                        "why": "EC launch geometry is not in the device facts; give --ec-launch R,Z,pol_deg,tor_deg"}
    # ---- C: 功率平衡反解（code/interpretive，给定源剖面 + 电子–离子交换）
    rho_m = [r * rm.rho_b for r in grid]
    cps = {"profiles_1d": {"grid": {"rho_tor": rho_m}, "electrons": {"temperature": te, "density": ne}}}
    if ti:
        cps["profiles_1d"]["t_i_average"] = ti
    inputs = {"core_profiles": cps,
              "equilibrium": {"time_slice": {"profiles_1d": {"psi_norm": lad["psi_norm"], "rho_tor": lad["rho_tor"],
                                                             "dvolume_drho_tor": lad["dvolume_drho_tor"],
                                                             "gm3": lad["gm3"], "gm7": lad["gm7"]}}}}
    settings = {"geometry": "ladder", "a": lad["facts"]["a_minor"], "r0": fa["rcentr"], "b0": abs(fa["bcentr"]),
                "exchange": 1, "brem": 1, "zeff": a.zeff}
    vl = window_mean(*sd["v_loop"], t, 0.025) if sd["v_loop"] else None
    if vl:
        settings["v_loop"] = vl
    if sources:
        srcs = []
        for s in sources:
            n = len(s["grid_psin"])
            srcs.append({"profiles_1d": {"grid": {"psi_norm": s["grid_psin"]}, "electrons": {"energy": s["p_e"]},
                                         "total_ion_energy": [0.0] * n, "j_parallel": s["j"] or [0.0] * n}})
        inputs["core_sources"] = {"source": srcs}
        settings["sources"] = "table"
    tf_, ti_, tn = lib.door("code/interpretive", settings, inputs)
    out = {"@type": "fylite:Wei2026Transport", "app": APP, "version": K.VERSION, "reference": REF,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "shot": a.shot, "time_asked_s": a.time, "time_s": t, "source": f"mdsplus:mds.invalid:{a.shot}",
           "method": method_card(None), "profiles": prof, "heating": report,
           "transport": {"facts": {k: K._r(v) for k, v in tf_.items()}, "notes": tn,
                         "rho": K._r([v / rm.rho_b for v in ti_["core_profiles/profiles_1d/grid/rho_tor"]], 5),
                         **{k: K._r(ti_[k], 5) for k in ("chi_e", "chi_i", "valid_e", "valid_i", "src_e", "src_i",
                                                          "exchange", "rad", "ohm", "j_cd")}},
           "equilibrium": prof.get("equilibrium") or {"zc": eq["zc"], "chi2_per_dof": K._r(eq["chi2_per_dof"], 4),
                                                       "q0": K._r(fa["q0"], 4), "q95": K._r(fa["q95"], 4)},
           "seconds": round(time.time() - t_start, 1), "fetch_seconds": sd["seconds"]}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"-> {a.out}: I_LH {report.get('lh', {}).get('i_lh')} A，<χ_e> {K._r(tf_.get('avg_chi_e'), 3)}，"
        f"<χ_i> {K._r(tf_.get('avg_chi_i'), 3)} m²/s，{out['seconds']} s")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wei2026.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("profiles", "transport"):
        p = sub.add_parser(name)
        p.add_argument("--shot", type=int, required=True)
        p.add_argument("--chain", default="east")
        p.add_argument("--server", help="主机:端口（缺省 $FYLITE_MDSIP_SERVER）")
        p.add_argument("--timeout", type=float, default=60.0)
        p.add_argument("--lib", help="另一份 libfylite.so（缺省本目录的）")
        p.add_argument("--signals", help="诊断绑定的覆盖 JSON（{ids: {量: {tree, node, scale, units}}}）；缺省只用库里的")
        p.add_argument("-o", "--out", required=True)
    pp = sub.choices["profiles"]
    pp.add_argument("--t0", type=float, default=4.0)
    pp.add_argument("--t1", type=float, default=8.0)
    pp.add_argument("--workers", type=int, default=max(1, min(8, (mp.cpu_count() or 2) - 1)))
    pp.add_argument("--clean", help="清洗参数覆盖（JSON，键见 wei_profiles.CLEAN_DEFAULTS）")
    pt = sub.choices["transport"]
    pt.add_argument("--time", type=float, required=True)
    pt.add_argument("--eta-cd", type=float, default=ETA_CD_DEFAULT)
    pt.add_argument("--zeff", type=float, default=2.0)
    pt.add_argument("--lh-upshift", default="1.5,2.5",
                    help="code/wave 的 n∥ 上移范围 min,max（缺省 1.5,2.5：内核自己的 LH 测试用的范围；没有上移时 EAST 的 T_e 吸收不了）")
    pt.add_argument("--ec-launch", help="EC 发射几何 R,Z,极向角°,环向角°（fylite 装置事实里没有）")
    a = ap.parse_args(argv)
    return cmd_profiles(a) if a.cmd == "profiles" else cmd_transport(a)


if __name__ == "__main__":
    sys.exit(main())
