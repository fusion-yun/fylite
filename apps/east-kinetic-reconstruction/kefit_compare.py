#!/usr/bin/env python3
"""档 M 对本地 KEFIT：同一炮、同一组原始测量、同一套选道 / 误差 / 基，两个程序各解一遍，同尺比较。

KEFIT 是 EFIT 的 EAST 分支（参考包 ``third_party/kefit_reference_bundle``，本机 gfortran 构建、65²、magpri 76、
``green2022_pcs`` 格林函数表）。它**不是**真值，是同一类程序的另一份实现——两者在同一份输入上给出的差，才是算法的差；
对离线 EFIT（efit_east 树，只作比较）的差里还混着对方自己的输入处理。所以这里把 KEFIT 当作「同输入」的参考：

  * 测量：本应用 ``MagneticsSource`` 从 east / pcs_east 树归约的读数（与 ``series`` 逐字节同一份），整炮取一次。
  * 选道：档 M 自己**最后一轮**的掩码（剔掉的道 KEFIT 也不用）；环只有 FL1B…FL35B（KEFIT 的 35 环就是它们），
    探针按 ``dprobe.dat`` 的位置 + 角度对到装置文档的槽（1 mm · 0.1°），对不上的 KEFIT 槽权 0。
  * 误差：σ = max(SERROR·|读数|, 位下限)，两边同式（KEFIT data_input：``tdata = max(serror|v|, bit·vbit)``，vbit = 1）；
    位下限取本应用的 ``LOOP_FLOOR`` / ``PROBE_FLOOR``。KEFIT 把槽 38–74 的探针权自己除 5（efitdu.f :3320），这里写 5 抵掉。
  * 基：KPPCUR = npp、KFFCUR = nff、PCURBD = FCURBD = 1（EFIT ``bsppel`` 的 x^(i−1) − x^n 与内核 ``poly`` 同一族）。
  * I_p：几乎等式（FWTCUR 100）；PF 电流：``--fwtfc fixed``（缺省，FWTFC 100 ≈ 本应用的固定）/ ``gui``（0.3，KEFIT GUI）/
    ``free``（0，完全自由）。竖直：KEFIT 的 ``fitdelz``，对应本应用的设定点扫描。限制器：本应用结果里的那一条。

比较（``kinetic_recon.compare`` 的同一段）：q0 · q95 · 同尺 l_i · β_p · W · 体积 · 磁轴距离 · 边界距离 · ψ_N 图之差 ·
**X 点平衡**（两个 X 点的 ψ_N 之差与 DN / LSN / USN / LIM）。``--also-efit`` 另比离线 EFIT（只作比较）。
``--check`` 按判据（形位逐片相同、磁轴距离 < ``AXIS_TOL`` · 边界平均距离 < ``BND_TOL``）给退出码——这是一条可重跑的对拍测试。

    python3 kefit_compare.py 137985 --t0 3.0 --t1 8.0 --at-efit --also-efit --workdir kefit_runs -o kefit_137985.json --check
    python3 kefit_compare.py 137985 --times 4.041 4.944 5.976 --fwtfc free -o kefit_free.json

要 ``$FYLITE_MDSIP_SERVER``（或 ``--server``）、本机的 KEFIT 可执行文件（``--exe`` 或 ``$KEFIT_EXE``）与参考包
（``--bundle`` 或 ``$KEFIT_BUNDLE``）。输出含实验数据派生量：不入仓。"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kinetic_recon as K  # noqa: E402

APP = "east-kinetic-reconstruction/kefit_compare"
DEFAULT_EXE = os.environ.get("KEFIT_EXE", str(Path.home() / ".local/opt/kefit/efitd6565d_76"))
DEFAULT_BUNDLE = os.environ.get("KEFIT_BUNDLE", str(Path(__file__).resolve().parents[3] / "third_party" / "kefit_reference_bundle"))
RCENTR = 1.8                        #: KEFIT GUI 的 RCENTR：BTOR 是这里的真空场
FWTFC = {"fixed": 100.0, "gui": 0.3, "free": 0.0}
FWTCUR = 100.0                      #: σ_Ip = max(SERROR·|Ip|, bitip) / 100 ≈ 0.05 %：本应用的 I_p 是等式
BITIP = 40000.0
BITFC = [50.0 * n for n in (140, 140, 140, 248, 60, 32)] * 2    #: 50 A × 匝数（EFIT 序：PF1 3 5 7 9 11，再 2 4 …）
SLOT_TOL_M, SLOT_TOL_DEG = 1e-3, 0.1
AXIS_TOL, BND_TOL = 0.010, 0.010    #: --check 的判据 [m]


def log(msg: str) -> None:
    print(f"[kefit_compare] {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------------------------------------ KEFIT geometry

def dprobe(tables: Path) -> dict:
    """``dprobe.dat`` 的 XMP2 · YMP2 · AMP2（探针）与 RSI · ZSI（环）。"""
    text = (tables / "dprobe.dat").read_text(encoding="latin-1")

    def arr(key):
        m = re.search(r"\b" + key + r"\s*=\s*(.*?)(?=\b[A-Za-z_][A-Za-z0-9_]*\s*=|/|\Z)", text, re.S | re.I)
        vals: list[float] = []
        for n, rv, v in re.findall(r"(\d+)\*([-+]?[\d.]+(?:[eEdD][-+]?\d+)?)|([-+]?[\d.]+(?:[eEdD][-+]?\d+)?)", m.group(1)):
            vals += [float(rv.replace("D", "E").replace("d", "e"))] * int(n) if n else [float(v.replace("D", "E").replace("d", "e"))]
        return vals
    return {k: arr(k) for k in ("XMP2", "YMP2", "AMP2", "RSI", "ZSI")}


def slot_map(card: dict, tables: Path) -> list:
    """KEFIT 探针槽 j → 装置文档的探针槽（位置 1 mm、角度 0.1° 之内恰好一个；同名的后几处槽不算——它们读的不是自己）。"""
    g = dprobe(tables)
    probes = K._aos(card["magnetics"].get("b_field_pol_probe"))
    names = [K._name(p) for p in probes]
    first = {}
    for i, nm in enumerate(names):
        first.setdefault(nm, i)
    out = []
    for x, y, a in zip(g["XMP2"], g["YMP2"], g["AMP2"]):
        hit = []
        for i, p in enumerate(probes):
            if first.get(names[i]) != i:
                continue
            r, z = K._rz(p)
            da = abs((math.degrees(float(p["poloidal_angle"])) - a + 180.0) % 360.0 - 180.0)
            if math.hypot(r - x, z - y) < SLOT_TOL_M and da < SLOT_TOL_DEG:
                hit.append(i)
        out.append(hit[0] if len(hit) == 1 else None)
    used = [i for i in out if i is not None]
    if len(used) != len(set(used)):
        raise SystemExit("slot_map: 一个装置槽被两个 KEFIT 槽读到")
    return out


# ------------------------------------------------------------------------------------------------ namelist

def _fmt(vals, f):
    return "".join(f % v for v in vals)


def namelist(shot: int, t: float, meas: dict, res: dict, smap: list, loop_names: list, basis: tuple, fwtfc: str) -> tuple[str, dict]:
    """GUI_v5 的写法（参考包 EFIT_POINT_GUI_v5.m :490–700），数值换成本片的原始读数、本应用档 M 最后的掩码与误差。
    返回 (namelist 文本, 用了什么的记录)。"""
    M = res["tiers"]["M"]
    used_l = {c["name"] for c in M["channels"]["loops"] if c["used"]}
    used_p = {i for i, c in enumerate(M["channels"]["probes"]) if c["used"]}
    coils = [float(v) for v in meas["coils"]]
    fl = []
    for k in range(1, 36):
        nm = f"FL{k}B"
        if nm not in loop_names:
            raise SystemExit(f"装置文档里没有 {nm}：KEFIT 的 35 环是 FL1B…FL35B")
        fl.append(loop_names.index(nm))
    silop = [coils[i] for i in fl]
    fwtsi = [1.0 if f"FL{k}B" in used_l else 0.0 for k in range(1, 36)]
    exp76 = [float(meas["expmp2"][i]) if i is not None else 0.0 for i in smap]
    fwt76 = []
    for j, i in enumerate(smap):
        w = 1.0 if (i is not None and i in used_p) else 0.0
        fwt76.append(w * (5.0 if 37 <= j <= 73 else 1.0))  #: 抵掉 KEFIT 自己对槽 38–74 的 /5
    lim = res["device"]["limiter"]
    npp, nff = basis
    btor = float(res["inputs"]["b_tor"]) * float(res["device"].get("r0") or 1.75) / RCENTR \
        if res["inputs"].get("b_tor") else None
    f_vac = (meas.get("tf") or {}).get("f_vac_Tm")
    if f_vac:
        btor = abs(float(f_vac)) / RCENTR
    L = ["&IN1", f"ISHOT ={shot}", f"ITIME={int(round(t * 1000)):05d}", f"RCENTR={RCENTR}", "iplcout=1",
         f"BTOR={btor:1.4f}", "ivesel=0", "IFITVS=0", "fitdelz=T", f"PLASMA={float(meas['plasma']):12.2f}", "",
         "EXPMP2=", _fmt(exp76, "%18.6f"), "coils=", _fmt(silop, "%18.6f"),
         "psibit=", _fmt([K.LOOP_FLOOR] * 35, "%12.6f"), "fwtsi=", " ".join("%.1f" % v for v in fwtsi),
         "bitmpi=", _fmt([K.PROBE_FLOOR] * len(smap), "%12.6f"), "fwtmp2=", " ".join("%.1f" % v for v in fwt76),
         f"bitip  ={BITIP:.0f} ", f"FWTCUR  =  {FWTCUR:g}", f"limitr  = {len(lim['r'])}",
         "xlim  = ", _fmt(lim["r"], "%12.5f"), "ylim  = ", _fmt(lim["z"], "%12.5f"),
         "BRSP  = ", _fmt(meas["brsp"], "%18.4f"), "bitfc  =" + _fmt(BITFC, "%18.5f"), f"FWTFC =12*{FWTFC[fwtfc]:g} ",
         #: itek 取 GUI 的 5：解不变（g-file 逐字节相同），多出日志末行的 wmhd,betap,li（kefit.reported）
         "itek =5 ", "mxiter=-50 ", f"serror={K.SERROR} ", " error=1e-3 ", " errmin=1e-3", " kersil=1",
         " KFFCUR  = ", f"{int(nff)}", " KPPCUR  = ", f"{int(npp)}", " pcurbd  = 1.0", " fcurbd  = 1.0",
         "NEXTRA  = 5", "relax  =0.5", " fwtqa  =0", " qvfit  =0.9", "/"]
    rec = {"loops_used": [f"FL{k}B" for k in range(1, 36) if fwtsi[k - 1] > 0],
           "kefit_probe_slots_used": sum(1 for v in fwt76 if v > 0),
           "fylite_probes_used": len(used_p), "fylite_probes_unmapped": sorted(
               c["name"] for i, c in enumerate(M["channels"]["probes"]) if i in used_p and i not in set(smap)),
           "basis": {"KPPCUR": npp, "KFFCUR": nff, "PCURBD": 1.0, "FCURBD": 1.0}, "FWTFC": FWTFC[fwtfc],
           "fwtfc_mode": fwtfc, "FWTCUR": FWTCUR, "BTOR_at_RCENTR": btor, "RCENTR": RCENTR,
           "loop_floor": K.LOOP_FLOOR, "probe_floor": K.PROBE_FLOOR, "serror": K.SERROR, "limiter_points": len(lim["r"])}
    return "\n".join(L) + "\n", rec


def run_kefit(exe: Path, tables: Path, pol2: Path | None, d: Path, text: str, shot: int, t: float) -> dict:
    if d.exists():
        shutil.rmtree(d)
    (d / "tables").mkdir(parents=True)
    for f in tables.iterdir():
        if f.is_file() and f.name != "pol2.est":
            (d / "tables" / f.name).symlink_to(f.resolve())
    if pol2 and pol2.exists():
        (d / "tables" / "pol2.est").symlink_to(pol2.resolve())
    (d / "temp").write_text(text, encoding="utf-8")
    t0 = time.time()
    try:
        p = subprocess.run([str(exe)], cwd=d, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
        rc, logtxt = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        rc, logtxt = "timeout", ""
    (d / "run.log").write_text(logtxt, encoding="utf-8")
    tag = f"{shot:06d}.{int(round(t * 1000)):05d}"
    g, a = d / f"g{tag}", d / f"a{tag}"
    out = {"rc": rc, "seconds": round(time.time() - t0, 2), "dir": d.name,
           "gfile": g.name if g.exists() else None, "afile": a.name if a.exists() else None}
    m = re.findall(r"wmhd,betap,li=\s*([-+\dEe.]+)\s+([-+\dEe.]+)\s+([-+\dEe.]+)", logtxt)
    if m:
        out["reported"] = {"w_mhd_J": float(m[-1][0]), "betap": float(m[-1][1]), "li": float(m[-1][2])}
    fo = d / "fitout.dat"
    if fo.exists():
        c = re.findall(r"chisq\s*=\s*([-+\dEe.]+)", fo.read_text(encoding="latin-1"), re.I)
        if c:
            out["chisq"] = float(c[-1])
    return out


# ------------------------------------------------------------------------------------------------ main

ROW_KEYS = (("q0", "q0"), ("q95", "q95"), ("li1", "li1_same_ruler"), ("betap", "betap_same_ruler"),
            ("w_mhd_J", "w_mhd_same_ruler_J"), ("volume_m3", "volume_m3"), ("axis_r", "axis_r"), ("axis_z", "axis_z"),
            ("xpt_dpsin", "xpoint_dpsin"))


def summarize(slices: list, src: str) -> dict:
    per: dict = {}
    for key, rk in ROW_KEYS:
        pts = []
        for s in slices:
            r = (s.get("rows") or {}).get(src)
            if r and K.fin(r[rk][0]) and K.fin(r[rk][1]):
                pts.append((s["time_s"], r[rk][0] - r[rk][1], r[rk][0], r[rk][1]))
        if pts:
            per[key] = K._stats([(p[0], p[1]) for p in pts], ours=[p[2] for p in pts], theirs=[p[3] for p in pts])
    for key, path in (("axis_distance_m", ("axis_distance_m",)), ("boundary_mean_m", ("boundary_distance", "mean_m")),
                      ("boundary_max_m", ("boundary_distance", "max_m")), ("psin_rms", ("psin_map_difference", "rms"))):
        v = [K._dig((s.get("rows") or {}).get(src) or {}, path) for s in slices]
        v = [x for x in v if x is not None]
        if v:
            per[key] = {"n": len(v), "mean": K.mean(v), "rms": math.sqrt(K.mean([x * x for x in v])), "max": max(v)}
    cfg = [((s.get("rows") or {}).get(src) or {}).get("xpoint_config") for s in slices]
    cfg = [c for c in cfg if c and c[0] and c[1]]
    if cfg:
        count = lambda xs: {k: xs.count(k) for k in sorted(set(xs))}  # noqa: E731
        per["xpoint_config"] = {"n": len(cfg), "match": sum(1 for a, b in cfg if a == b),
                                "ours": count([a for a, _ in cfg]), "theirs": count([b for _, b in cfg])}
    return per


def check(summary: dict, src: str) -> list:
    """--check 的判据：对 ``src``（kefit）形位逐片相同、磁轴距离与边界平均距离的均值在带内。返回没过的条目。"""
    per = summary.get(src) or {}
    bad = []
    c = per.get("xpoint_config")
    if not c or c["match"] != c["n"]:
        bad.append(f"X 点形位逐片相同 {0 if not c else c['match']}/{0 if not c else c['n']}")
    for key, tol in (("axis_distance_m", AXIS_TOL), ("boundary_mean_m", BND_TOL)):
        st = per.get(key)
        if not st or st["mean"] > tol:
            bad.append(f"{key} 均 {st['mean'] * 1e3 if st else float('nan'):.1f} mm > {tol * 1e3:.0f} mm")
    return bad


# ------------------------------------------------------------------------------------------------ page document

MU0 = 4e-7 * math.pi


def _floats(path: Path) -> list:
    """每行的数（KEFIT 的 flux.dat / Bprobe.dat：测量 · 计算 · σ；权 0 的行没有 σ）。"""
    out = []
    for line in path.read_text(encoding="latin-1").splitlines():
        v = [float(x.replace("D", "E")) for x in re.findall(r"[-+]?\d+\.\d*(?:[EeDd][-+]?\d+)?", line)]
        if v:
            out.append(v)
    return out


def _chi_blocks(fitout: Path) -> dict:
    """fitout.dat 最后一遍的逐道 χ²（环 35 · 探针 76；KEFIT 的 χ² = (fwt·(测 − 算)/σ)²）。"""
    t = fitout.read_text(encoding="latin-1").split("chi psi loops:")[-1]
    num = r"[-+]?\d\.\d+E[-+]\d+"
    loops = [float(x) for x in re.findall(num, t.split("chi inner magnetic probes:")[0])]
    probes = [float(x) for x in re.findall(num, t.split("chi inner magnetic probes:")[1].split("chi ip:")[0])]
    return {"loops": loops, "probes": probes}


def _namelist_array(text: str, key: str) -> list:
    m = re.search(r"(?mi)^\s*" + key + r"\s*=\s*\n?(.*?)(?=^\s*[A-Za-z_]\w*\s*=|^/)", text, re.S)
    return [float(x) for x in re.findall(r"[-+]?\d+\.\d*(?:[eE][-+]?\d+)?", m.group(1))] if m else []


def _psin_map(psi, pa, pb) -> list:
    return [[round((v - pa) / (pb - pa), 4) for v in row] for row in psi]


def _derived_pprime(psin, pres, dpsi_rad) -> list:
    """p′ = dp/dψ（ψ 按 Wb/rad）由 p(ψ_N) 中心差分——两边同一式，与各自的规范、正负号无关。"""
    n = len(psin)
    out = []
    for i in range(n):
        a, b = max(0, i - 1), min(n - 1, i + 1)
        out.append((pres[b] - pres[a]) / (psin[b] - psin[a]) / dpsi_rad if psin[b] != psin[a] else float("nan"))
    return out


def _same_sign(a: list, b: list) -> float:
    s = sum(x * y for x, y in zip(a, b) if K.fin(x) and K.fin(y))
    return -1.0 if s < 0 else 1.0


def _midplane_j(eq: dict, psi_axis: float, per_rad: float, axis_z: float) -> dict:
    """中平面（离磁轴最近的一行 Z）上的环向电流密度 J_φ = −Δ*ψ / (μ₀ R)，ψ 取 Wb/rad；只取边界内的点，
    正负号使等离子体里的均值为正。两边同一式（由 ψ 图直接差分，不经各自的剖面规范）。"""
    gr, gz, psi, bnd = eq["grid_r"], eq["grid_z"], eq["psi"], eq["boundary"]
    dr, dz = gr[1] - gr[0], gz[1] - gz[0]
    j = min(range(1, len(gz) - 1), key=lambda k: abs(gz[k] - axis_z))
    r_out, j_out = [], []
    for i in range(1, len(gr) - 1):
        r = gr[i]
        if not K._inside(bnd, r, gz[j]):
            continue
        p = [[psi[ii][jj] / per_rad for jj in (j - 1, j, j + 1)] for ii in (i - 1, i, i + 1)]
        d2r = (p[2][1] - 2 * p[1][1] + p[0][1]) / dr ** 2
        d1r = (p[2][1] - p[0][1]) / (2 * dr)
        d2z = (p[1][2] - 2 * p[1][1] + p[1][0]) / dz ** 2
        dstar = d2r - d1r / r + d2z
        r_out.append(r)
        j_out.append(-dstar / (MU0 * r))
    if j_out and sum(j_out) < 0:
        j_out = [-v for v in j_out]
    return {"r": [round(x, 4) for x in r_out], "j_A_m2": [round(v, 1) for v in j_out], "z": gz[j]}


def slice_doc(lib, t: float, meas: dict, res: dict, kdir: Path, gname: str, smap: list, loop_names: list,
              rows: dict) -> dict:
    """一片 → 页面「单片对拍」要的全部：两边的 ψ_N 图 · 边界 · X 点 · 剖面（p · p′ · FF′ · q）· 中平面 J_φ ·
    逐道（测量 · 两边的计算 · 用没用 · χ² · 权）· 两个解之间的距离。两边的量都换到同一规范（ψ 按 Wb/rad）。"""
    o = K.our_integrals(res)["M"]
    eq, fa, it = o["eq"], o["fa"], o["int"]
    per_rad = 2 * math.pi if it.get("psi_map_unit") == "Wb" else 1.0
    pr = res["tiers"]["M"]["profiles"]
    dpsi = (fa["psi_bnd"] - fa["psi_axis"]) / per_rad
    pp_ours = _derived_pprime(pr["psin"], pr["pres"], dpsi)
    s_ours = _same_sign([v * per_rad for v in pr["pprime"]], pp_ours)   #: 内核的 p′ 是每整圈 Wb；换每弧度、定号
    #: 共同规范：ψ 由磁轴向外增（两边的 ψ 方向不同——我们磁轴处最大、KEFIT 最小），p′ · FF′ 都按这个方向说
    o_dir = 1.0 if dpsi > 0 else -1.0
    pp_ours = [v * o_dir for v in pp_ours]
    xo = K.xpoint_balance(eq, fa["psi_axis"], fa["psi_bnd"])
    ours = {"label": "fylite 档 M", "grid": {"r": eq["grid_r"], "z": eq["grid_z"]},
            "psin": _psin_map(eq["psi"], fa["psi_axis"], fa["psi_bnd"]),
            "boundary": K._rt(eq["boundary"], 5), "axis": [fa["axis_r"], fa["axis_z"]], "xpoint": K._rt(xo, 5),
            "profiles": {"psin": pr["psin"], "pres": pr["pres"], "pprime": K._rt(pp_ours, 6),
                         "ffprim": K._rt([v * per_rad * s_ours * o_dir for v in pr["ffprim"]], 6), "q": pr["qpsi"]},
            "j_mid": _midplane_j(eq, fa["psi_axis"], per_rad, fa["axis_z"]),
            "scalars": {"q0": fa.get("q0"), "q95": fa.get("q95"), "li1": it["li1"], "betap": it["betap"],
                        "w_mhd_J": it["w_mhd_J"], "volume_m3": it["volume_m3"], "chi2_per_dof": fa.get("chi2_per_dof"),
                        "zc_m": res["tiers"]["M"].get("zc_anchor")}}
    g = lib.gfile((kdir / gname).read_text(encoding="utf-8", errors="replace"))
    e = K.read_reference(lib, str(kdir / gname))
    K._their_integrals(e, True)
    ke_rad = 2 * math.pi if (e.get("int") or {}).get("psi_map_unit") == "Wb" else 1.0
    n = len(g["pres"])
    xk = [i / (n - 1) for i in range(n)]
    sc = e["scalars"]
    pp_k = _derived_pprime(xk, list(g["pres"]), (sc["psi_bnd"] - sc["psi_axis"]) / ke_rad)
    s_k = _same_sign([v * ke_rad for v in g["pprime"]], pp_k)
    k_dir = 1.0 if sc["psi_bnd"] > sc["psi_axis"] else -1.0
    pp_k = [v * k_dir for v in pp_k]
    xe = K.xpoint_balance(e, sc["psi_axis"], sc["psi_bnd"])
    kefit = {"label": "本机 KEFIT（同输入）", "grid": {"r": e["grid_r"], "z": e["grid_z"]},
             "psin": _psin_map(e["psi"], sc["psi_axis"], sc["psi_bnd"]), "boundary": K._rt(e["boundary"], 5),
             "axis": [sc["axis_r"], sc["axis_z"]], "xpoint": K._rt(xe, 5),
             "profiles": {"psin": xk, "pres": list(g["pres"]), "pprime": K._rt(pp_k, 6),
                          "ffprim": K._rt([v * ke_rad * s_k * k_dir for v in g["ffprim"]], 6), "q": list(g["qpsi"])},
             "j_mid": _midplane_j(e, sc["psi_axis"], ke_rad, sc["axis_z"]),
             "scalars": {"q0": sc.get("q0"), "q95": sc.get("q95"), "li1": (e.get("int") or {}).get("li1"),
                         "betap": (e.get("int") or {}).get("betap"), "w_mhd_J": (e.get("int") or {}).get("w_mhd_J"),
                         "volume_m3": (e.get("int") or {}).get("volume_m3")}}
    #: 逐道：KEFIT 的道序（环 FL1B…FL35B · 探针 76 槽）；我们的计算值 = 测量 + 残差[σ] × σ（σ 与 KEFIT 同式）
    M = res["tiers"]["M"]
    temp = (kdir / "temp").read_text(encoding="utf-8")
    fwtsi, fwtmp2 = _namelist_array(temp, "fwtsi"), _namelist_array(temp, "fwtmp2")
    flux, bprobe = _floats(kdir / "flux.dat"), _floats(kdir / "Bprobe.dat")
    chi = _chi_blocks(kdir / "fitout.dat")
    loops = []
    for k in range(35):
        i = loop_names.index(f"FL{k + 1}B")
        m = float(meas["coils"][i]); sg = max(K.SERROR * abs(m), K.LOOP_FLOOR)
        c = M["channels"]["loops"][i]
        kf = flux[k] if k < len(flux) else [None, None]
        loops.append({"name": c["name"], "meas": m, "sigma": sg,
                      "ours": {"calc": m + c["sigma"] * sg if K.fin(c["sigma"]) else None, "used": c["used"],
                               "chi2": c["sigma"] ** 2 if K.fin(c["sigma"]) else None},
                      "kefit": {"calc": kf[1] if len(kf) > 1 else None, "used": (fwtsi[k] if k < len(fwtsi) else 0) > 0,
                                "weight": fwtsi[k] if k < len(fwtsi) else 0.0, "chi2": chi["loops"][k] if k < len(chi["loops"]) else None}})
    probes = []
    for jj, i in enumerate(smap):
        kb = bprobe[jj] if jj < len(bprobe) else [None, None]
        w = fwtmp2[jj] if jj < len(fwtmp2) else 0.0
        ent = {"slot": jj, "name": None, "meas": kb[0] if kb else None, "sigma": None, "ours": None,
               "kefit": {"calc": kb[1] if len(kb) > 1 else None, "used": w > 0, "weight": w,
                         "chi2": chi["probes"][jj] if jj < len(chi["probes"]) else None}}
        if i is not None:
            c = M["channels"]["probes"][i]
            m = float(meas["expmp2"][i]); sg = max(K.SERROR * abs(m), K.PROBE_FLOOR)
            ent.update(name=c["name"], meas=m, sigma=sg,
                       ours={"calc": m + c["sigma"] * sg if K.fin(c["sigma"]) else None, "used": c["used"],
                             "chi2": c["sigma"] ** 2 if K.fin(c["sigma"]) else None})
        probes.append(ent)
    r = rows.get("kefit") or {}
    return {"time_s": t, "ours": K._rt(ours, 6), "kefit": K._rt(kefit, 6), "channels": {"loops": K._rt(loops, 6), "probes": K._rt(probes, 6)},
            "between": {k: r.get(k) for k in ("axis_distance_m", "boundary_distance", "psin_map_difference", "xpoint_config", "xpoint_dpsin")},
            "efit_east": {k: (rows.get("efit") or {}).get(k) for k in ("q0", "q95", "xpoint_config", "xpoint_dpsin", "axis_distance_m")}
            if rows.get("efit") else None,
            "limiter": (res.get("device") or {}).get("limiter")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("shot", type=int)
    p.add_argument("--times", type=float, nargs="*", help="时刻 [s]（不给则用 --t0/--t1 取离线 EFIT 的片）")
    p.add_argument("--t0", type=float)
    p.add_argument("--t1", type=float)
    p.add_argument("--every", type=int, default=1, help="--t0/--t1 时每隔几片取一片")
    p.add_argument("--fwtfc", choices=sorted(FWTFC), default="fixed")
    p.add_argument("--npp", type=int, default=1)
    p.add_argument("--nff", type=int, default=2)
    p.add_argument("--also-efit", action="store_true", help="另比离线 EFIT（efit_east 树，只作比较）")
    p.add_argument("--exe", default=DEFAULT_EXE)
    p.add_argument("--bundle", default=DEFAULT_BUNDLE)
    p.add_argument("--tables", default=None, help="格林函数表目录（缺省 <bundle>/green2022_pcs）")
    p.add_argument("--jobs", type=int, default=K.JOBS)
    p.add_argument("--server", default=None)
    p.add_argument("--workdir", default="kefit_runs")
    p.add_argument("--results-dir", default=None, help="逐片的 fylite 完整结果写到这里")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--check", action="store_true", help="判据不过时退出码 1")
    p.add_argument("--page", metavar="OUT.json",
                   help="另写页面「单片对拍」的文档（fylite:KefitSlices：每片两边的 ψ_N 图 · 边界 · 剖面 · 逐道 χ²），结果页导入")
    p.add_argument("--lib", default=None)
    a = p.parse_args(argv)

    exe, bundle = Path(a.exe), Path(a.bundle)
    tables = Path(a.tables) if a.tables else bundle / "green2022_pcs"
    pol2 = bundle / "green2018_wpf_64" / "pol2.est"
    if not exe.exists():
        raise SystemExit(f"KEFIT 可执行文件不在：{exe}（--exe 或 $KEFIT_EXE）")
    if not (tables / "dprobe.dat").exists():
        raise SystemExit(f"格林函数表不在：{tables}（--tables / --bundle）")
    lib = K.Lib(Path(a.lib) if a.lib else K.DEFAULT_LIB)
    card, resolution = lib.device("east", a.shot, "east")
    smap = slot_map(card, tables)
    loop_names = [K._name(x) for x in K._aos(card["magnetics"].get("flux_loop"))]
    log(f"slot map: {sum(1 for i in smap if i is not None)}/{len(smap)} KEFIT probe slots matched to the device card")

    times = list(a.times or [])
    if not times:
        if a.t0 is None or a.t1 is None:
            raise SystemExit("给 --times，或 --t0 / --t1（取离线 EFIT 的片）")
        host, port = K.server_of(a.server)
        s = lib.mds_open(host, port, 120.0)
        try:
            eq = K.EquilibriumSeries(s, K.eq_signals(card, None), "efit", a.shot)
        finally:
            s.close()
        times = [x for x in eq.tb if a.t0 <= x <= a.t1][:: max(1, a.every)]
    log(f"#{a.shot}: {len(times)} time(s) {times[0]:.3f} … {times[-1]:.3f} s")
    src = K.MagneticsSource(lib, a.shot, "east", a.server, 120.0)
    try:
        src.prefetch(point=False)
    finally:
        src.close()

    work = Path(a.workdir)
    work.mkdir(parents=True, exist_ok=True)
    if a.results_dir:
        Path(a.results_dir).mkdir(parents=True, exist_ok=True)
    slices, page_slices = [], []
    for t in times:
        t_start = time.time()
        one: dict = {"time_s": t}
        meas = src.at(t, point=False)
        res = K.reconstruct(meas, None, lib=lib, origin={"kind": "kefit_compare", "time_s": t}, tiers="M",
                            npp=a.npp, nff=a.nff, jobs=a.jobs)
        M = res["tiers"]["M"]
        one["fylite_status"] = M.get("status")
        if a.results_dir:
            (Path(a.results_dir) / f"result_{a.shot}_{t:.6f}.json").write_text(
                json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        if M.get("status") not in ("ok", "unphysical"):
            one["why"] = M.get("error")
            slices.append(one)
            log(f"t {t:.4f}: fylite tier M failed ({one['why']})")
            continue
        text, rec = namelist(a.shot, t, meas, res, smap, loop_names, (a.npp, a.nff), a.fwtfc)
        d = work / f"t{int(round(t * 1000)):05d}_{a.fwtfc}"
        kr = run_kefit(exe, tables, pol2, d, text, a.shot, t)
        one["kefit"] = dict(kr, inputs=rec)
        refs = []
        if kr["gfile"]:
            #: a-file 不读：本机 KEFIT 的 a-file 头与 read_afile 认的那一代不同；同尺量由 g-file 积出，KEFIT 自报的
            #: W · β_p · l_i 从它的日志里取（kefit.reported）
            refs.append({"gfile": str(d / kr["gfile"]), "afile": None, "label": "kefit"})
        try:
            cmp = K.compare(res, lib=lib, sources="efit" if a.also_efit else "", server=a.server, refs=refs,
                            result_name=f"t{t:.4f}")
        except SystemExit as e:
            one["why"] = str(e)
            slices.append(one)
            continue
        one["rows"] = {r["source"]: K._rt(r, 6) for r in cmp["rows"]}
        if a.page and kr["gfile"]:
            try:
                page_slices.append(slice_doc(lib, t, meas, res, d, kr["gfile"], smap, loop_names, one["rows"]))
            except Exception as err:                     # noqa: BLE001 —— 一片画不了照记，不拦对拍
                page_slices.append({"time_s": t, "error": K.sanitize(f"{type(err).__name__}: {err}")[-300:]})
        one["unavailable"] = cmp.get("unavailable")
        one["seconds"] = round(time.time() - t_start, 1)
        r = one["rows"].get("kefit")
        if r:
            log(f"t {t:.4f}: KEFIT rc={kr['rc']} · X 点 ours {r['xpoint_config'][0]} ({r['xpoint_dpsin'][0]:+.4f}) / "
                f"kefit {r['xpoint_config'][1]} ({r['xpoint_dpsin'][1]:+.4f}) · 轴距 {1e3 * (r['axis_distance_m'] or float('nan')):.1f} mm")
        else:
            log(f"t {t:.4f}: KEFIT rc={kr['rc']}，没有 g-file")
        slices.append(one)

    sources = ["kefit"] + (["efit"] if a.also_efit else [])
    summary = {s: summarize(slices, s) for s in sources}
    failed = check(summary, "kefit")
    k = lib.linked_kernel()
    out = {"@type": "fylite:KefitCompare", "app": APP, "version": K.VERSION, "shot": a.shot,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "档 M 对本地 KEFIT（同一组原始测量、同一套选道 / 误差 / 基）；离线 EFIT 只作比较。含实验数据派生量：不入仓。服务器地址记作 mds.invalid。",
           "kefit": {"exe": exe.name, "tables": tables.name, "fwtfc": a.fwtfc,
                     "slots_matched": sum(1 for i in smap if i is not None), "slots": len(smap)},
           "fylite": {"library": lib.path.name, "kernel_built": k.get("built"), "npp": a.npp, "nff": a.nff},
           "criteria": {"xpoint_config": "逐片相同", "axis_distance_mean_m": AXIS_TOL, "boundary_mean_m": BND_TOL,
                        "xpoint_dn_tol": K.XPT_DN_TOL},
           "check_failed": failed, "summary": summary, "slices": slices}
    Path(a.out).write_text(json.dumps(K.strict_json(out), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
                           encoding="utf-8")
    for s in sources:
        print(f"ours − {s}：量 | n | 均差 | rms | 我们均 | 对方均 | 差>0 份额")
        for key, st in summary[s].items():
            if "mean_diff" in st:
                print(f"  {key} | {st['n']} | {st['mean_diff']:+.4g} | {st['rms_diff']:.4g} | {st['mean_ours']:.4g} | "
                      f"{st['mean_theirs']:.4g} | {st['positive_fraction']:.2f}")
            elif key == "xpoint_config":
                print(f"  X 点形位 | {st['n']} | 逐片相同 {st['match']} | 我们 {st['ours']} | 对方 {st['theirs']}")
            else:
                print(f"  {key} | {st['n']} | 均 {st['mean']:.4g} | rms {st['rms']:.4g} | 最大 {st['max']:.4g}")
    print("判据：" + ("全过" if not failed else "没过 — " + "；".join(failed)))
    log(f"-> {a.out}")
    if a.page:
        doc = {"@type": "fylite:KefitSlices", "app": APP, "version": K.VERSION, "shot": a.shot,
               "created": out["created"], "comment": out["comment"], "kefit": out["kefit"], "fylite": out["fylite"],
               "summary": summary, "check_failed": failed, "slices": page_slices}
        Path(a.page).write_text(json.dumps(K.strict_json(doc), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
                                encoding="utf-8")
        log(f"-> {a.page}（页面「单片对拍」：{sum(1 for x in page_slices if 'error' not in x)} 片）")
    K.close_jobs()
    return 1 if (a.check and failed) else 0


if __name__ == "__main__":
    sys.exit(main())
