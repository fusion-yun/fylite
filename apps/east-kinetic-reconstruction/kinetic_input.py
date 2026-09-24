"""动理学反演的输入文件（``fylite:KineticReconInput``）→ 档 X。

一份 JSON，把 KEFIT 一次动理学反演要手改的东西（``third_party/kefit_bundle`` 的流程、``KEFIT_wuxm`` 的 settinglib.m）
收成一处，逐项可关：

1. 诊断逐道置信度 c（磁通环 · 磁探针 · POINT 法拉第 / 线密度 · Thomson）：σ_eff = σ / c，c = 0 即关掉这道，缺省 1。
   与 EFIT 的 FWT 同义（FWT 乘在 1/σ 上）。
2. 边界台基：p′（可选 FF′）多一个 sech² 台基基函数，位置 x、宽 w 给定，幅值自由（KEDGEP · PE_PSIN · PE_WIDTH）。
3. 预设 q0：一行 1/q0 的约束（FWTQA · QVFIT），σ 给在 q0 上。
4. p′ / FF′ 的基：多项式阶数（KPPCUR · KFFCUR）、张力样条（KPPFNC = 6：结点 · 张力）、或直接给定剖面（不拟合）。
5. 电流项：NEO 自举电流 j_bs（内核 ``code/bootstrap``，Redl）与外加电流 j_ext(ψ_N)；每项可当「给定电流」（进 GS 的
   j_pre，拟合只管其余）或当「电流密度约束」（KZEROJ · SIZEROJ · VZEROJ：边缘几处 ⟨J⟩ = j_bs + j_ohm + j_ext）。
   外环：解 → 在解上算 j_bs → 再解，直到 I_bs 与 q0 不再动（ONETWO ↔ EFIT 的来回，这里在一个进程里）。

用法：
    kinetic_input.py template PULL.json -o input.json        # 由 pull 的测量文档生成一份缺省输入（各道 c = 1）
    kinetic_input.py run input.json -o result.json           # 跑 M（+K）+ X；结果与 run -o 同一种文档，多一档 X
    kinetic_input.py serve --root DIR                        # 本机回环服务：页面上编辑、保存、运行（见 README §4.7）
"""
from __future__ import annotations

import argparse
import copy
import http.server
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kinetic_recon as K  # noqa: E402
import wei_profiles as W  # noqa: E402

TYPE = "fylite:KineticReconInput"
N_BINS = 25                  #: ⟨J_φ⟩(ψ_N) 的分箱数（电流面板与约束行都用它）
N_PROF = 41                  #: 给 code/bootstrap 的 n_e / T_e 剖面点数（ψ_N 上均匀）

#: 缺省输入（除 data 与逐道表以外的全部键；template 再按测量文档填上逐道表）
DEFAULTS = {
    "@type": TYPE, "version": 1,
    "data": {"file": None, "time_s": None, "thomson_file": None},
    "magnetics": {"loops": {}, "probes": {}},
    "point": {"on": True, "faraday": [], "density": []},
    "pressure": {"on": True, "source": "thomson", "thomson": [], "profile": {"psin": [], "p": [], "sigma": []},
                 "sigma_floor": 0.05, "psin_max": 0.98, "fast_frac": 0.0, "on_tier": "M"},
    "pedestal": {"on": False, "x": 0.95, "w": 0.03, "ffprime": False},
    "q0": {"on": False, "target": 1.0, "sigma": 0.02},
    "basis": {"pprime": {"mode": "poly", "n": 1, "edge_zero": True, "knots": [0.0, 0.5, 0.9, 1.0], "tension": 1.0,
                         "psin": [], "value": []},
              "ffprime": {"mode": "poly", "n": 2, "edge_zero": True, "knots": [0.0, 0.5, 0.9, 1.0], "tension": 1.0,
                          "psin": [], "value": []}},
    "currents": {"passes": 4, "tol": 0.01, "relax": 0.5,
                 "bootstrap": {"on": False, "use": "constraint", "x": [0.9, 0.925, 0.95, 0.97, 0.99], "weight": 1.0,
                               "zeff": 2.0, "tite": 1.0, "profiles": "thomson", "given": {"psin": [], "ne": [], "te": []}},
                 "external": {"on": False, "use": "source", "psin": [0.0, 0.3, 0.6, 1.0], "j": [1.0, 1.0, 0.2, 0.0],
                              "total_A": 0.0, "x": [], "weight": 1.0}},
    "ip": {"on": False, "sigma_A": 2000.0},
    "curv": 0.0,
    #: 求解器：warm_start = auto（选了样条 / 台基 / 给定剖面时先解普通多项式再从它接着解）· true · false；
    #: condin = 截断的特征值比（空 = 内核缺省 1e8）
    "solver": {"warm_start": "auto", "condin": None},
}


# ================================================================================================ the document

def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = {k: copy.deepcopy(v) for k, v in base.items()}
        for k, v in over.items():
            out[k] = _merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def normalize(doc: dict) -> dict:
    """缺省键补齐 + 查错；错的输入拒（写错的键不静默地不起作用）。"""
    if doc.get("@type") not in (None, TYPE):
        raise SystemExit(f"不是动理学反演的输入文件（@type = {doc.get('@type')!r}，要 {TYPE}）")
    unknown = [k for k in doc if k not in DEFAULTS]
    if unknown:
        raise SystemExit(f"输入文件里有不认识的键 {unknown}（认的：{sorted(DEFAULTS)}）")
    d = _merge(DEFAULTS, doc)
    ws = d["solver"]["warm_start"]                      #: 页面的下拉框给字符串
    d["solver"]["warm_start"] = {"true": True, "false": False}.get(ws, ws) if isinstance(ws, str) else ws
    bad = []
    if d["pressure"]["source"] not in ("thomson", "profile", "kfile"):
        bad.append("pressure.source ∈ thomson | profile | kfile")
    if d["pressure"]["on_tier"] not in ("M", "K"):
        bad.append("pressure.on_tier ∈ M | K")
    for w in ("pprime", "ffprime"):
        b = d["basis"][w]
        if b["mode"] not in ("poly", "spline", "fixed"):
            bad.append(f"basis.{w}.mode ∈ poly | spline | fixed")
        if b["mode"] == "poly" and not (1 <= int(b["n"]) <= 6):
            bad.append(f"basis.{w}.n ∈ 1…6")
        if b["mode"] == "spline" and (len(b["knots"]) < 3 or sorted(b["knots"]) != list(b["knots"])):
            bad.append(f"basis.{w}.knots：至少 3 个、递增")
        if b["mode"] == "fixed" and (len(b["psin"]) < 2 or len(b["psin"]) != len(b["value"])):
            bad.append(f"basis.{w}：fixed 要 psin 与 value 等长（≥ 2 点）")
    for k in ("bootstrap", "external"):
        if d["currents"][k]["use"] not in ("source", "constraint"):
            bad.append(f"currents.{k}.use ∈ source | constraint")
    ex = d["currents"]["external"]
    if ex["on"] and (len(ex["psin"]) < 2 or len(ex["psin"]) != len(ex["j"])):
        bad.append("currents.external：psin 与 j 等长（≥ 2 点）")
    if d["solver"]["warm_start"] not in ("auto", True, False):
        bad.append("solver.warm_start ∈ auto | true | false")
    if d["solver"]["condin"] is not None and not float(d["solver"]["condin"]) > 1:
        bad.append("solver.condin > 1（或空）")
    if d["q0"]["on"] and not d["q0"]["sigma"] > 0:
        bad.append("q0.sigma > 0")
    pr = d["pressure"]["profile"]
    if d["pressure"]["on"] and d["pressure"]["source"] == "profile" and (
            len(pr["psin"]) < 3 or not len(pr["psin"]) == len(pr["p"]) == len(pr["sigma"])):
        bad.append("pressure.profile：psin · p · sigma 等长（≥ 3 点）")
    if bad:
        raise SystemExit("输入文件不成立：" + "；".join(bad))
    return d


def template(pull_path: str, lib: "K.Lib | None" = None) -> dict:
    """由 pull 的测量文档生成一份缺省输入：逐道表按装置事实的道名列全、c = 1。"""
    meas, th, _ = K.load_input(pull_path, None, None)
    lib = lib or K.Lib(K.DEFAULT_LIB)
    card, _ = lib.device("east", int(meas["shot"]), meas.get("measurement_chain", "east"))
    mag = card["magnetics"]
    loops = [K._name(x) for x in K._aos(mag.get("flux_loop"))][:len(meas["coils"])]
    probes = [K._name(x) for x in K._aos(mag.get("b_field_pol_probe"))][:len(meas["expmp2"])]
    d = copy.deepcopy(DEFAULTS)
    d["data"] = {"file": os.path.relpath(pull_path, os.getcwd()), "time_s": meas.get("time_s"), "thomson_file": None}
    d["magnetics"]["loops"] = {n: 1.0 for n in loops if n}
    d["magnetics"]["probes"] = {n: 1.0 for n in dict.fromkeys(probes) if n}
    npt = len((meas.get("point") or {}).get("bpolar") or [])
    d["point"]["faraday"], d["point"]["density"] = [1.0] * npt, [1.0] * npt
    d["point"]["on"] = npt > 0
    d["pressure"]["thomson"] = [1.0] * len((th or {}).get("te") or [])
    if th is None:
        d["pressure"]["on"] = bool(meas.get("kinetic_pressure"))
        d["pressure"]["source"] = "kfile"
    return d


def load(path: str) -> tuple[dict, dict, dict | None, dict]:
    """(规范化的输入, 测量, Thomson, 出处)；数据文件路径相对输入文件所在目录。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    d = normalize(raw)
    base = Path(path).resolve().parent
    f = d["data"]["file"]
    if not f:
        raise SystemExit("输入文件没有 data.file（pull 的测量文档）")
    fp = Path(f) if Path(f).is_absolute() else base / f
    tf = d["data"].get("thomson_file")
    tp = None if not tf else str(Path(tf) if Path(tf).is_absolute() else base / tf)
    meas, th, origin = K.load_input(str(fp), d["data"].get("time_s"), tp)
    origin["input_file"] = Path(path).name
    return d, meas, th, origin


def apply_point(meas: dict, d: dict) -> dict:
    """POINT 逐弦置信度 → 测量文档副本的 fwtpol / fwtnel（法拉第行权 = fwtpol / σ，所以乘 c 就是 σ / c）。"""
    m = copy.deepcopy(meas)
    p = m.get("point")
    if not p:
        return m
    for key, conf in (("fwtpol", d["point"]["faraday"]), ("fwtnel", d["point"]["density"])):
        w = [float(v) for v in p.get(key) or []]
        p[key] = [v * max(float(conf[i]), 0.0) if i < len(conf) else v for i, v in enumerate(w)]
    return m


# ================================================================================================ fit settings

def _interp(x, xp, fp):
    return K.interp(min(max(x, xp[0]), xp[-1]), xp, fp)


def fit_settings(d: dict, n_profile: int) -> tuple[dict, dict, list, dict]:
    """输入文件 → (内核设定, discharge 行, 约束清单, 记录)。只管 2 · 3 · 4 与 I_p、曲率；电流项另算。"""
    st: dict = {}
    disc: dict = {}
    cons: list = []
    rec: dict = {}
    for which, npk in (("pprime", "npp"), ("ffprime", "nff")):
        b = d["basis"][which]
        if b["mode"] == "poly":
            st[f"{which}_basis"] = "poly" if b.get("edge_zero", True) else "poly_free"
            st[npk] = int(b["n"])
            cons.append(f"{which}：多项式 {int(b['n'])} 阶" + ("（边界为零）" if b.get("edge_zero", True) else "（边界自由）"))
        elif b["mode"] == "spline":
            st[f"{which}_basis"] = "spline"
            st[f"{which}_knots"] = " ".join(repr(float(v)) for v in b["knots"])
            st[f"{which}_tension"] = float(b["tension"])
            st[f"{which}_edge"] = "zero" if b.get("edge_zero") else "free"
            st["spline_tension_scale"] = "mean_interval"
            cons.append(f"{which}：张力样条 结点 {b['knots']} τ {float(b['tension']):g}"
                        "（★EAST #137985 上冷热启动都被内核拒：磁测量只带得住一两个 p′ 方向，见 README §6.7）")
        else:
            #: 给定剖面（不拟合）：插到内核的剖面格（ψ_N 上均匀 n_profile 点），单位同输出的 pprime / ffprim
            xs = [k / (n_profile - 1) for k in range(n_profile)]
            st[f"{which}_basis"] = "fixed"
            disc["fylite:pprime_fixed" if which == "pprime" else "fylite:ffprim_fixed"] = [
                _interp(x, b["psin"], b["value"]) for x in xs]
            cons.append(f"{which}：给定剖面（{len(b['psin'])} 点，不拟合）")
        rec[which] = b
    pd = d["pedestal"]
    if pd["on"]:
        st["pprime_ped_x"], st["pprime_ped_w"] = float(pd["x"]), float(pd["w"])
        if pd.get("ffprime"):
            st["ffprime_ped_x"], st["ffprime_ped_w"] = float(pd["x"]), float(pd["w"])
        cons.append(f"台基 sech²((ψ_N − {pd['x']:g}) / {pd['w']:g})，幅值自由" + ("（p′ 与 FF′）" if pd.get("ffprime") else "（p′）"))
        rec["pedestal"] = pd
    q = d["q0"]
    if q["on"]:
        #: 内核的 q0 行：权 = 1/σ，σ 在 q 的单位上（EFIT 的 FWTQA / QVFIT）
        st["q0_target"] = float(q["target"])
        st["q0_weight"] = 1.0 / float(q["sigma"])
        cons.append(f"磁轴 q0 = {q['target']:g} ± {q['sigma']:g}")
        rec["q0"] = q
    if d["ip"]["on"]:
        st["ip_sigma"] = float(d["ip"]["sigma_A"])
        cons.append(f"I_p 作测量（σ {st['ip_sigma']:g} A）")
    if d["curv"] > 0:
        st["curv_p"] = st["curv_f"] = float(d["curv"])
    sv = d["solver"]
    extended = pd["on"] or any(d["basis"][w]["mode"] in ("spline", "fixed") for w in ("pprime", "ffprime"))
    if sv["warm_start"] is True or (sv["warm_start"] == "auto" and extended):
        st["warm_start"] = 1
        cons.append("先解普通多项式、再从它接着解所选的基（warm_start）")
    if sv["condin"] is not None:
        st["condin"] = float(sv["condin"])
        cons.append(f"截断特征值比 condin = {float(sv['condin']):g}")
    return st, disc, cons, rec


# ================================================================================================ currents

def _cells(fa: dict, fi: dict):
    """内部格 (i, j)（(nr − 2)(nz − 2)，i 沿 R，与内核 j_pre 同序）上的 (R, ψ_N, 在 LCFS 内, 面积)。"""
    gr, gz, psi = fi["grid_r"], fi["grid_z"], fi["psi"]
    span = fa["psi_bnd"] - fa["psi_axis"]
    bd = fi.get("boundary") or []
    da = (gr[1] - gr[0]) * (gz[1] - gz[0])
    out = []
    for i in range(1, len(gr) - 1):
        row = []
        for j in range(1, len(gz) - 1):
            x = (psi[i][j] - fa["psi_axis"]) / span
            row.append((gr[i], x, 0.0 <= x <= 1.0 and bool(bd) and K._inside(bd, gr[i], gz[j])))
        out.append(row)
    return out, da


def binned_j(cells_a, geo, da) -> dict:
    """格上的电流 [A/格] → ψ_N 分箱的面平均 ⟨J_φ⟩ [A/m²] 与各箱面积。"""
    s, a = [0.0] * N_BINS, [0.0] * N_BINS
    for i, row in enumerate(geo):
        for j, (_, x, inside) in enumerate(row):
            if inside:
                k = min(int(x * N_BINS), N_BINS - 1)
                s[k] += cells_a[i][j]
                a[k] += da
    return {"psin": [(k + 0.5) / N_BINS for k in range(N_BINS)],
            "j": [sk / ak if ak > 0 else float("nan") for sk, ak in zip(s, a)], "area": a}


def external_cells(ex: dict, geo, da, sign: float) -> tuple[list, float]:
    """外加电流 j_ext(ψ_N)（形状，任意单位）→ 格电流，按 total_A 归一；方向随 I_p（total_A > 0 = 同向）。"""
    raw = [[_interp(x, ex["psin"], ex["j"]) * da if inside else 0.0 for (_, x, inside) in row] for row in geo]
    tot = sum(map(sum, raw))
    scale = sign * float(ex["total_A"]) / tot if tot else 0.0
    return [[v * scale for v in row] for row in raw], tot


def kinetic_profiles(c: "K.Case", th: dict | None, fa: dict, fi: dict, bs: dict, a) -> dict | None:
    """code/bootstrap 的 n_e / T_e：Thomson 点映到本解的 ψ_N 上、拟合（wei_profiles：H 模 mtanh 台基，不成退 L 模样条）；
    或输入文件给定的表。返回 ψ_N 均匀 N_PROF 点上的 {ne [m⁻³], te [eV]}。"""
    xs = [k / (N_PROF - 1) for k in range(N_PROF)]
    if bs["profiles"] == "given":
        g = bs["given"]
        if len(g["psin"]) < 2:
            return None
        return {"psin": xs, "ne": [_interp(x, g["psin"], g["ne"]) for x in xs],
                "te": [_interp(x, g["psin"], g["te"]) for x in xs], "source": "input file"}
    if th is None:
        return None
    p = K.pressure_from_thomson(th, sigma_floor=a.sigma_floor)
    gr, gz = fi["grid_r"], fi["grid_z"]
    pts = []
    for r, z, te, ne in zip(p["r"], p["z"], p["te"], p["ne"]):
        if gr[0] <= r <= gr[-1] and gz[0] <= z <= gz[-1]:
            x = K.psin_at(fa, fi, r, z)
            if 0.0 <= x < 1.0:
                pts.append((math.sqrt(x), te * 1e-3, ne * 1e-19))
    if len(pts) < 5:
        return None
    pts.sort()
    rho = [q[0] for q in pts]
    out = {"psin": xs, "source": "thomson", "points": [[K._r(q[0] ** 2, 4), K._r(q[1] * 1e3, 5), K._r(q[2] * 1e19, 5)]
                                                        for q in pts]}
    for key, col, ysep, scale in (("te", 1, 0.05, 1e3), ("ne", 2, None, 1e19)):
        y = [q[col] for q in pts]
        xm, ym, wm = W.merge_ties(rho, y, [1.0] * len(y), tol=1e-4)
        try:
            f = W.fit_profile(xm, ym, wm, mode="H", y_sep=ysep)
        except Exception:                                # noqa: BLE001 —— 台基拟合不成就退 L 模，记下
            f = W.fit_profile(xm, ym, wm, mode="L")
        prof = f["profile"]
        vals = [prof(math.sqrt(x)) for x in xs]
        lo = 0.02 * max(vals)
        out[key] = [max(v, lo) * scale for v in vals]
        out[key + "_mode"] = f.get("mode")
    return out


def bootstrap(c: "K.Case", fa: dict, fi: dict, prof: dict, bs: dict, a) -> tuple[dict, dict]:
    """在解 (fa, fi) 上跑 code/bootstrap（Redl）；返回 (facts, fields)。"""
    eq = {"time_slice": {"profiles_2d": {"psi": fi["psi"]},
                         "global_quantities": {"psi_axis": fa["psi_axis"], "psi_boundary": fa["psi_bnd"],
                                               "magnetic_axis": {"r": fa["axis_r"], "z": fa["axis_z"]}},
                         "profiles_1d": {"psi_norm": fi["psin_1d"], "pressure": fi["pres"], "dpressure_dpsi": fi["pprime"],
                                         "f_df_dpsi": fi["ffprim"], "f": fi["fpol"], "q": fi["qpsi"]}}}
    disc = {"fylite:ne_profile": prof["ne"], "fylite:te_profile": prof["te"]}
    if a.p_fast_frac > 0:
        pk = max(fi["pres"])
        disc["fylite:p_fast_profile"] = [a.p_fast_frac * pk * (1.0 - x * x) for x in prof["psin"]]
    bf, bi, _ = c.lib.door("code/bootstrap", {"zeff": float(bs["zeff"]), "tite": float(bs["tite"])},
                           {"device": c.card, "equilibrium": eq, "discharge": disc})
    return bf, bi


def ohmic_flat(bi: dict, bins: dict, i_ohm: float) -> list:
    """稳态（环电压处处相等）的欧姆电流：⟨J_ohm⟩ ∝ σ_neo ⟨1/R⟩，按各箱面积归一到 ``i_ohm``。"""
    xs, sg, ri = bi["x"], bi["sigma_neo"], bi["r_inv"]
    shape = [_interp(x, xs, [s * r if math.isfinite(s) else 0.0 for s, r in zip(sg, ri)]) for x in bins["psin"]]
    tot = sum(s * a for s, a in zip(shape, bins["area"]))
    return [s * i_ohm / tot if tot else 0.0 for s in shape]


# ================================================================================================ tier X

def channel_detail(c: "K.Case", fi: dict) -> dict:
    """面板 (a)–(d)：逐道 测量 · 计算 · σ_eff · 置信度 · χ²（χ² 按 σ_eff；关掉的道照列、不计）。"""
    out = {}
    for which, meas, model, sig, conf, w, names in (
            ("loops", c.coils, [lm + lc for lm, lc in zip(fi["loop_model"], c.loop_coil)], c.loop_sigma, c.loop_conf,
             c.lw, c.loop_names),
            ("probes", c.probes, fi["probe_model"], c.probe_sigma, c.probe_conf, c.pw, c.probe_names)):
        rows = []
        for i, (m, v, s, cf, wt, n) in enumerate(zip(meas, model, sig, conf, w, names)):
            chi = ((v - m) / s) ** 2
            rows.append({"name": n, "meas": K._r(m, 6), "calc": K._r(v, 6), "sigma": K._r(s, 5), "conf": cf,
                         "used": wt > 0, "chi2": K._r(chi, 4)})
        out[which] = rows
    return out


def _solve_plain(c, base, kin, a, settings, extra, hold) -> dict:
    """压强关掉时：档 M / K 的行 + 输入文件的设定直接解一次。"""
    fa_b, fi_b, zc = base
    st = dict(settings, zc_anchor=zc, **(extra.get("st") or {}))
    disc = dict(K._p_base_disc(c, base, kin), **(extra.get("disc") or {}))
    try:
        fa, fi, notes = c.lib.door("code/reconstruction", st, {"device": c.card, "discharge": disc})
    except (K.Refused, K.KernelError) as e:
        return {"status": "error", "error": str(e)[-300:]}
    hold.update(fa=fa, fi=fi, st=st, disc=disc)
    return K.tier_view(fa, fi, zc, {"label": "X · 磁" + (" + POINT" if kin else "") + "（不用压强）",
                                    "constraints": ["磁（同 M）"] + (["POINT 法拉第行（同 K）"] if kin else [])
                                                   + list(extra.get("constraints") or []),
                                    "channels": c.channel_table(fi), "notes": list(notes or [])})


def tier_x(c: "K.Case", base_m, base_k, kin, th, a, settings: dict, d: dict) -> dict:
    """档 X：输入文件驱动的动理学反演（见模块说明）。"""
    use_k = base_k is not None and d["pressure"]["on_tier"] == "K"
    base, kin_use = (base_k, kin) if use_k else (base_m, None)
    st0, disc0, cons0, rec = fit_settings(d, int(settings.get("n_profile", 201)))
    pr = d["pressure"]
    cur = d["currents"]
    bs, ex = cur["bootstrap"], cur["external"]
    fa_b, fi_b, _ = base
    geo, da = _cells(fa_b, fi_b)
    sign = 1.0 if float(c.meas["plasma"]) >= 0 else -1.0
    n_pass = 1 + (int(cur["passes"]) if bs["on"] else 0)
    passes, hist, view, hold = [], [], None, {}
    boot = None
    bs_given = None
    prev_j = None
    for k in range(n_pass):
        st, disc, cons = dict(st0), dict(disc0), list(cons0)
        src = None
        targets = {"x": [], "j": []}
        rows_x, rows_v = [], []
        ip = abs(float(c.meas["plasma"]))
        area = abs(K._poly_area(fi_b.get("boundary") or [])) if not hold else abs(K._poly_area(hold["fi"]["boundary"]))
        if ex["on"]:
            geo_now = geo if not hold else _cells(hold["fa"], hold["fi"])[0]
            ext_cells, _ = external_cells(ex, geo_now, da, sign)
            if ex["use"] == "source":
                src = ext_cells
                cons.append(f"外加电流（给定）{float(ex['total_A']) / 1e3:g} kA，形状 j(ψ_N) {len(ex['psin'])} 点")
            else:
                eb = binned_j(ext_cells, geo_now, da)
                xs = ex["x"] or bs["x"]
                for x in xs:
                    rows_x.append(x)
                    rows_v.append(_interp(x, eb["psin"], eb["j"]))
                cons.append(f"外加电流（约束）{float(ex['total_A']) / 1e3:g} kA 进 ⟨J⟩ 行 × {len(xs)}")
        if bs["on"] and boot is not None:
            bf, bi, bb = boot
            if bs["use"] == "source":
                #: 欠松弛：给定的 j_bs 取 α·新 + (1 − α)·上一遍给定的（直接代入在 #137985 上来回放大：q0 1.6 → 4.6）
                al = float(cur["relax"])
                cells = bi["current_source"] if bs_given is None else [
                    [al * u + (1.0 - al) * v for u, v in zip(r1, r2)] for r1, r2 in zip(bi["current_source"], bs_given)]
                bs_given = cells
                src = cells if src is None else [[u + v for u, v in zip(r1, r2)] for r1, r2 in zip(src, cells)]
                cons.append(f"自举电流（给定，Redl）I_bs = {bf['i_bs'] / 1e3:.1f} kA")
            else:
                i_ext = float(ex["total_A"]) if ex["on"] else 0.0
                j_ohm = ohmic_flat(bi, bb, ip - abs(bf["i_bs"]) - abs(i_ext))
                jb = binned_j(bi["current_source"], hold_geo, da)
                for x in bs["x"]:
                    v = sign * abs(_interp(x, jb["psin"], jb["j"])) + sign * _interp(x, bb["psin"], j_ohm)
                    if x in rows_x:
                        rows_v[rows_x.index(x)] += v
                    else:
                        rows_x.append(x)
                        rows_v.append(v)
                cons.append(f"⟨J⟩ 约束行 × {len(bs['x'])}：j_bs（Redl）+ 稳态欧姆（σ_neo⟨1/R⟩，I_p − I_bs）")
        if src is not None:
            disc["fylite:current_source"] = K.flat(src)
        if rows_x:
            st["fsa_norm"] = "ip_area"
            w = float(bs["weight"] if bs["on"] and bs["use"] == "constraint" else ex["weight"])
            disc.update({"fylite:fsa_x": rows_x, "fylite:fsa_shape": [v / (ip / area) * sign for v in rows_v],
                         "fylite:fsa_weight": [w] * len(rows_x)})
            targets = {"x": rows_x, "j": rows_v}
        extra = {"st": st, "disc": disc, "constraints": cons}
        hold = {}
        if not pr["on"]:
            view = _solve_plain(c, base, kin_use, a, settings, extra, hold)
        elif pr["source"] == "thomson":
            if th is None:
                return {"status": "skipped", "why": "输入文件要 Thomson 压强，但测量文档里没有 Thomson"}
            view = K.tier_p(c, base, kin_use, th, a, settings, dict(extra, conf=pr["thomson"]), hold)
        else:
            if pr["source"] == "profile":
                pp = pr["profile"]
                kp = {"psin": pp["psin"], "pressr": pp["p"], "sigpre": pp["sigma"], "source": "input file",
                      "note": "压强剖面由输入文件给定"}
            else:
                kp = c.meas.get("kinetic_pressure")
                if not kp:
                    return {"status": "skipped", "why": "输入文件要 k-file 压强，但测量文档里没有 kinetic_pressure"}
            view = K.tier_p_psin(c, base, kin_use, kp, a, settings, dict(extra, conf=pr.get("thomson") if pr["source"] == "kfile" else None), hold)
        if view.get("status") != "ok" or "fa" not in hold:
            view.setdefault("kinetic", {})["passes"] = passes
            return dict(view, label="X · 输入文件", input=d)
        fa, fi = hold["fa"], hold["fi"]
        hold_geo, _ = _cells(fa, fi)
        jb_this = binned_j(fi["current"], hold_geo, da)
        entry = {"pass": k, "q0": K._r(fa["q0"], 5), "chi2": K._r(fa.get("chi2"), 5), "ip": K._r(fa.get("ip"), 6),
                 "constraint_x": K._r(targets["x"], 4), "constraint_j": K._r(targets["j"], 5)}
        prof = None
        if bs["on"]:
            prof = kinetic_profiles(c, th, fa, fi, bs, a)
            if prof is None:
                view.setdefault("notes", []).append("自举电流要 n_e / T_e：没有 Thomson 也没有给定表 → 这一项没算")
                bs = dict(bs, on=False)
            else:
                try:
                    bf, bi = bootstrap(c, fa, fi, prof, bs, a)
                    boot = (bf, bi, jb_this)
                    entry.update(i_bs=K._r(bf.get("i_bs"), 6), f_bs=K._r(bf.get("f_bs"), 4))
                except (K.Refused, K.KernelError) as e:
                    view.setdefault("notes", []).append(f"code/bootstrap 拒：{str(e)[-200:]}")
                    bs = dict(bs, on=False)
        passes.append(entry)
        hist.append(jb_this)
        log(f"X pass {k}: q0 {fa['q0']:.3f}" + (f", I_bs {entry['i_bs'] / 1e3:.1f} kA" if entry.get("i_bs") else ""))
        if k >= 2 and bs["on"]:
            p0, p1 = passes[-2], passes[-1]
            dq = abs(p1["q0"] - p0["q0"]) / max(abs(p0["q0"]), 1e-9)
            di = abs((p1.get("i_bs") or 0) - (p0.get("i_bs") or 0)) / max(abs(p1.get("i_bs") or 1.0), 1.0)
            if dq < float(cur["tol"]) / 10 and di < float(cur["tol"]):
                break
        prev_j = hist[-2] if len(hist) > 1 else None
    # ---- 面板用的读数
    fa, fi = hold["fa"], hold["fi"]
    geo_f, _ = _cells(fa, fi)
    this = binned_j(fi["current"], geo_f, da)
    currents = {"psin": K._r(this["psin"], 4), "this": K._r(this["j"], 5),
                "previous": K._r(prev_j["j"], 5) if prev_j else None,
                "constraint": {"x": passes[-1]["constraint_x"], "j": passes[-1]["constraint_j"]}}
    if boot is not None:
        bf, bi, _ = boot
        jb = binned_j(bi["current_source"], geo_f, da)
        currents.update(boot=K._r([sign * abs(v) if math.isfinite(v) else v for v in jb["j"]], 5),
                        i_bs=K._r(bf.get("i_bs"), 6), f_bs=K._r(bf.get("f_bs"), 4),
                        boot_ladder={"x": K._r(bi["x"], 4), "j_bs_tor": K._r(bi["j_bs_tor"], 5),
                                     "j_tot_tor": K._r(bi["j_tot_tor"], 5)})
    if ex["on"]:
        ec, _ = external_cells(ex, geo_f, da, sign)
        currents["external"] = K._r(binned_j(ec, geo_f, da)["j"], 5)
    view["label"] = "X · 输入文件（" + "、".join(
        [s for s, on in (("压强", pr["on"]), ("台基", d["pedestal"]["on"]), ("q0", d["q0"]["on"]),
                         ("j_bs", bs["on"]), ("外加电流", ex["on"])) if on] or ["只有磁"]) + "）"
    view["on"] = "K" if use_k else "M"
    view["kinetic"] = {"passes": passes, "currents": currents, "channels": channel_detail(c, fi),
                       "profiles": prof if bs["on"] else None, "fit": rec,
                       "settings_sent": {k_: v for k_, v in hold["st"].items() if k_ not in K.SETTINGS},
                       "kernel_echo": {k_: fa[k_] for k_ in ("pprime_basis", "ffprime_basis", "q0_target", "q0_axis_row",
                                                             "q0_minus_target", "pprime_ped_coef", "ffprime_ped_coef",
                                                             "jzero_rows", "jzero_rms", "ip_measured") if k_ in fa}}
    ignored = []
    if d["pedestal"]["on"] and "pprime_ped_coef" not in fa:
        ignored.append("pedestal")
    if d["q0"]["on"] and "q0_target" not in fa:
        ignored.append("q0")
    if ignored:
        view.setdefault("notes", []).append("★这份 libfylite.so 不认 " + "、".join(ignored)
                                            + " 的设定（内核缺 feat/recon-kinetic-input）：读数是没有它们的解")
        view["kinetic"]["ignored"] = ignored
    view["input"] = d
    return view


def log(msg: str) -> None:
    K.log(msg)


# ================================================================================================ run · serve

def run_file(path: str, lib: "K.Lib | None" = None, **opts) -> dict:
    d, meas, th, origin = load(path)
    return K.reconstruct(meas, th, lib=lib, origin=origin, kinetic_input=d, **opts)


def cmd_template(a) -> int:
    d = template(a.pull, K.Lib(Path(a.lib)) if a.lib else None)
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"-> {a.out}")
    return 0


def cmd_run(a) -> int:
    out = run_file(a.input, K.Lib(Path(a.lib)) if a.lib else None, jobs=a.jobs)
    Path(a.out).write_text(json.dumps(K.strict_json(out), ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    log(f"-> {a.out} ({out['seconds']} s)")
    x = out["tiers"].get("X") or {}
    return 0 if x.get("status") == "ok" else 1


class _Handler(http.server.SimpleHTTPRequestHandler):
    """回环服务：静态页（本目录）+ 工作目录下的输入 / 结果文件 + /api/*。只听 127.0.0.1。"""
    root: Path = Path(".")
    lock = threading.Lock()

    def __init__(self, *args, **kw):
        super().__init__(*args, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, obj) -> None:
        body = json.dumps(K.strict_json(obj), ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe(self, name: str) -> Path:
        p = (self.root / name).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise PermissionError(name)
        return p

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/files"):
            files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*.json") if p.is_file())
            return self._json(200, {"files": files})
        if self.path.startswith("/api/file?name="):
            from urllib.parse import unquote
            try:
                p = self._safe(unquote(self.path.split("=", 1)[1]))
                return self._json(200, json.loads(p.read_text(encoding="utf-8")))
            except Exception as e:                       # noqa: BLE001
                return self._json(404, {"error": str(e)})
        if self.path.startswith("/api/template?pull="):
            from urllib.parse import unquote
            try:
                d = template(str(self._safe(unquote(self.path.split("=", 1)[1]))))
                d["data"]["file"] = os.path.relpath(self._safe(d["data"]["file"]) if not Path(d["data"]["file"]).is_absolute()
                                                    else d["data"]["file"], self.root)
                return self._json(200, d)
            except Exception as e:                       # noqa: BLE001
                return self._json(400, {"error": str(e)})
        if self.path in ("/", ""):
            self.path = "/kinetic_recon.html"
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/save":
                p = self._safe(body["name"])
                p.write_text(json.dumps(normalize(body["input"]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                return self._json(200, {"saved": str(p.relative_to(self.root.resolve()))})
            if self.path == "/api/run":
                p = self._safe(body["name"])
                p.write_text(json.dumps(normalize(body["input"]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                with self.lock:                          #: 一次一个：内核库进程内单例
                    t0 = time.time()
                    out = run_file(str(p))
                res = p.with_name(p.stem + ".result.json")
                res.write_text(json.dumps(K.strict_json(out), ensure_ascii=False, separators=(",", ":")) + "\n",
                               encoding="utf-8")
                out["result_file"] = str(res.relative_to(self.root.resolve()))
                log(f"serve: ran {p.name} in {time.time() - t0:.1f} s -> {res.name}")
                return self._json(200, out)
        except PermissionError as e:
            return self._json(403, {"error": f"不在 --root 之下：{e}"})
        except SystemExit as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:                           # noqa: BLE001
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        return self._json(404, {"error": self.path})


def cmd_serve(a) -> int:
    _Handler.root = Path(a.root).resolve()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), _Handler)
    log(f"serving {HERE / 'kinetic_recon.html'} + {_Handler.root} on http://127.0.0.1:{a.port}/ (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kinetic_input.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--lib", help="libfylite.so 的路径（缺省与 kinetic_recon.py 同目录）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template", help="由 pull 的测量文档生成一份缺省输入文件（各道置信度 1）")
    t.add_argument("pull")
    t.add_argument("-o", "--out", required=True)
    r = sub.add_parser("run", help="输入文件 → 结果 JSON（档 M、K 与 X）")
    r.add_argument("input")
    r.add_argument("--jobs", type=int, default=K.JOBS)
    r.add_argument("-o", "--out", required=True)
    s = sub.add_parser("serve", help="本机回环服务：页面上编辑 · 保存 · 运行输入文件")
    s.add_argument("--root", default=".", help="输入 / 测量 / 结果文件所在目录（只读写它下面的文件）")
    s.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    return {"template": cmd_template, "run": cmd_run, "serve": cmd_serve}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
