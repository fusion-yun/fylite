"""MXH boundary fit on every g-file this checkout can reach (register record `FR-EQ-013`).

★★判据点名「7 机型 MAST / DIII-D / JET RMS ≤ 2.4 %」。g-file 语料有 EAST（3 炮）· DIII-D（1 炮，
来自 GACODE/NEO 的 profile_data）· CFEDR（3 份）与一份合成件；★2026-09-18 起再加 `third_party/` 里的
MAST（2 份）与 JET（6 份）真 EFIT——共 5 个真机型，判据点名的三个都在。

★量的是什么：把 g-file 的 `rbbbs/zbbbs` 边界拟合成 MXH 形（`code/shape` 的 `mxh_*`），
报每份件的 RMS（已按小半径归一）与拟合出的 kappa / delta / zeta，并与同一扇门用包围盒
读出来的 Miller 度量并排——★**两者不是一回事**：Miller 是读数，MXH 是拟合，只有后者有残差。

Subcommands: ``readings --out DIR`` · ``crosscheck --out DIR`` (needs Julia + MillerExtendedHarmonic.jl).
Environment: ``$FYDOC_ORACLE``, ``$FYLITE_THIRD_PARTY``, ``$FYLITE_JULIA`` / ``$FYLITE_JULIA_PROJECT``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
READINGS = "mxh_fit_gfiles.json"
#: 判据点名的带：RMS ≤ 2.4 %
BAND = 0.024
#: 本机 g-file 与它们的机型（路径 -> 机型），判据点名的 MAST / JET 不在其中
SOURCES = [
    ("east",      "FYDOC-CASE-19-east-efit/corpus/g070754.05000"),
    ("east",      "FYDOC-CASE-19-east-efit/corpus/g063982.04800"),
    ("east",      "FYDOC-CASE-19-east-efit/corpus/g080307.63000"),
    ("d3d",       "FYDOC-CASE-05-gacode/corpus/upstream/neo/profile_data/g141459.03890"),
    ("cfedr",     "FYDOC-CASE-21-cfedr-hmode-20ma/corpus/CFEDR_260114/EFIT/FILES/g0.30000"),
    ("cfedr",     "FYDOC-CASE-21-cfedr-hmode-20ma/corpus/CFEDR_260114/EFIT/FILES/g260110.00300_teq"),
    ("cfedr",     "FYDOC-CASE-21-cfedr-hmode-20ma/corpus/CFEDR_260114/ONETWO/FILES/gEQDSK/g0.99999"),
    ("synthetic", "FYDOC-CASE-12-synthetic/corpus/g_synthetic.geqdsk"),
]
#: ★2026-09-18：MAST 与 JET 的真 EFIT 在 `third_party/`（公开仓的兄弟目录，或 `$FYLITE_THIRD_PARTY`）。
#: ★**只收真重建**：`scpn-fusion-core/.../jet_*.geqdsk` 是 Solov'ev 合成件（生成脚本自己这么说），不收；
#: `solps/.../mast/g002951.00223` 的轮廓首尾差 23 % 小半径（不闭合），点名排除，不平均进来。
THIRD_PARTY_SOURCES = [
    ("mast", "FUSE/MXHEquilibrium.jl/test/g029908.00221_MAST"),
    ("mast", "solps/solps_data/data/DivGeo/class/mast/g002948.00189"),
    ("jet",  "FUSE/MXHEquilibrium.jl/test/g96100_0-53.0012.eqdsk_JET"),
    ("jet",  "solps/solps_data/data/DivGeo/class/jet/g045462.59381.65x65"),
    ("jet",  "solps/solps_data/data/DivGeo/class/jet/g075733.60022"),
    ("jet",  "solps/solps_data/data/DivGeo/class/jet/g040000.61137.65x65"),
    ("jet",  "solps/solps_data/data/DivGeo/class/jet/g046532.61380.65x65"),
    ("jet",  "solps/solps_data/data/DivGeo/class/jet/g045464.60360.65x65"),
    #: ★2026-09-19：JT-60SA 的设计平衡（与 CFEDR 同属「机型的设计平衡」，不是实测重建），CRONOS 自带；边界闭合。
    ("jt60sa", "cronos/equi/equibord/data/jt60sa/MHD_equilibrium_data_24VDPC_v1_0.geqdsk"),
    #: ★NSTX（R0 0.87 m、a 0.61 m、B0 0.44 T——几何认的机型），DCON 3.80 算例。它存的 rbbbs 首尾差 11 % 小半径（不闭合），
    #: 所以**从 ψ 图重描**：ψ_N = 1 那条等值线从 X 点漏出去（首尾差 1.23 a），ψ_N = 0.999 闭合，R0 / a / κ 与存的那段一致。
    ("nstx", "dcon_3.80/equilibria/sabbagh/g108418.00361#psin=0.999"),
]
#: 判据点名却本机没有的机型（找得到 third_party 时为空）
ABSENT = ["mast", "jet"]


def third_party_dir():
    """`$FYLITE_THIRD_PARTY`，否则公开仓旁边的 `third_party/`；都没有就 None（那几行照实记 skipped）。"""
    env = os.environ.get("FYLITE_THIRD_PARTY")
    for cand in ([Path(env)] if env else []) + [ROOT.parent / "third_party"]:
        if cand.is_dir():
            return cand
    return None


def all_sources(store: Path):
    """(机型, 标签, 绝对路径)。标签是记进读数的名字：语料库里的相对路径，或 `third_party:` 前缀。"""
    rows = [(m, rel, store / rel) for m, rel in SOURCES]
    tp = third_party_dir()
    for m, rel in THIRD_PARTY_SOURCES:
        rows.append((m, "third_party:" + rel, (tp / rel) if tp else Path("/nonexistent") / rel))
    return rows


def _chain(seg: np.ndarray, tol: float) -> list[np.ndarray]:
    """把 marching-squares 的线段接成折线（端点在 tol 内相接）。"""
    segs = [((a, b), (c, d)) for a, b, c, d in seg]
    used = [False] * len(segs)
    loops = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        pts = [segs[i][0], segs[i][1]]
        grown = True
        while grown:
            grown = False
            for j, (p, q) in enumerate(segs):
                if used[j]:
                    continue
                e = pts[-1]
                if np.hypot(p[0] - e[0], p[1] - e[1]) < tol:
                    pts.append(q); used[j] = True; grown = True
                elif np.hypot(q[0] - e[0], q[1] - e[1]) < tol:
                    pts.append(p); used[j] = True; grown = True
        loops.append(np.array(pts))
    return loops


def _encloses(poly: np.ndarray, x: float, y: float) -> bool:
    c = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def traced_boundary(path: Path, psin: float):
    """ψ_N 等值线（内核的 marching squares）里围住磁轴的那一圈——给 rbbbs 缺失或不闭合的 g-file 用。"""
    from fylite import kernel as K
    from fylite.io import geqdsk
    g = geqdsk.read_geqdsk(path)
    nw, nh = int(g["nw"]), int(g["nh"])
    psi = np.asarray(g["psirz"], float).reshape(nh, nw).T
    sgn = 1.0 if g["simag"] > g["sibry"] else -1.0
    grid = K.Grid(g["rleft"], g["zmid"] - g["zdim"] / 2, g["rdim"] / (nw - 1), g["zdim"] / (nh - 1), nw, nh)
    seg = K.contour(grid, sgn * psi, sgn * (g["simag"] + psin * (g["sibry"] - g["simag"])), max_seg=20000)
    loops = [L for L in _chain(seg, 1e-6 * g["rdim"]) if len(L) > 20 and _encloses(L, g["rmaxis"], g["zmaxis"])]
    if not loops:
        raise RuntimeError(f"no closed psi_N = {psin} contour around the axis in {path}")
    L = max(loops, key=len)
    #: ★与 g-file 的 rbbbs 同一个约定：首点在末尾重复一次（闭合的轮廓）
    if not np.allclose(L[0], L[-1]):
        L = np.vstack([L, L[:1]])
    return L[:, 0], L[:, 1], len(L), 0


def read_boundary(path: Path):
    """★用包**自己的** g-file 读取器，不另写一个。

    初版手搓了一个按标量数数的解析器，在 `.../ONETWO/FILES/gEQDSK/g0.99999` 上当场
    崩在抬头（那一行的末两个字段不是 nw / nh）。★**一份格式已经有读取器时，
    第二个解析器不是省事，是又一处会漂的约定。**
    """
    if "#psin=" in str(path):
        base, lev = str(path).split("#psin=")
        return traced_boundary(Path(base), float(lev))
    from fylite.io import geqdsk
    g = geqdsk.read_geqdsk(path)
    rb = np.asarray(g["rbbbs"], float)
    zb = np.asarray(g["zbbbs"], float)
    return rb, zb, rb.size, 0


def wv_fields(rec):
    """★复用 wall-vstab 的 `_flat_fields`，不再写第二个摊平器。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "benchmark_wall_vstab", ROOT / "tools" / "benchmark-wall-vstab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._flat_fields(rec["fields"])


def readings(store: Path) -> dict:
    from fylite.io import fydoc
    out = {"band_rms": BAND, "absent_machines": [],
           "_comment": "判据点名 7 机型（其中点名 MAST / DIII-D / JET）；语料库 + third_party 覆盖 7 个机型（EAST · DIII-D · CFEDR · MAST · JET · JT-60SA · NSTX）",
           "files": [], "by_machine": {}}
    for machine, rel, p in all_sources(store):
        if not Path(str(p).split("#")[0]).is_file():
            out["files"].append({"machine": machine, "file": rel, "skipped": "not in the case store / third_party"})
            continue
        rb, zb, nbbbs, _ = read_boundary(p)
        if rb.size < 8:
            out["files"].append({"machine": machine, "file": rel, "skipped": f"only {rb.size} boundary points"})
            continue
        #: ★轮廓闭不闭合，是这一支里唯一会把「语料的毛病」误记成「拟合的毛病」的地方
        gap = float(np.hypot(rb[0] - rb[-1], zb[0] - zb[-1]))
        a_est = 0.5 * float(rb.max() - rb.min())
        rec = fydoc.complete("code/shape", {"settings": {}, "inputs": {
            "equilibrium": {"time_slice/boundary/outline/r": rb,
                             "time_slice/boundary/outline/z": zb}}})
        f = {k: float(v["value"]) for k, v in rec["facts"].items()}
        row = {"machine": machine, "file": rel, "n_boundary": int(rb.size),
               "mxh_rms": f["mxh_rms"], "mxh_kappa": f["mxh_kappa"],
               "mxh_delta": f["mxh_delta"], "mxh_zeta": f["mxh_zeta"],
               #: ★并排放着的包围盒读数，不是同一件事
               "miller_kappa": f["kappa"], "miller_delta_upper": f["delta_upper"],
               "miller_delta_lower": f["delta_lower"], "a_m": f["a"], "r0_m": f["r0"],
               "closure_gap_over_a": gap / a_est,
               "in_band": bool(f["mxh_rms"] <= BAND)}
        #: 逐点残差：最劣落在哪，是判「取样不够」还是「形状本身」的那把尺
        h = np.asarray(wv_fields(rec)["mxh_harmonics"], float).reshape(2, 7)
        c, s = h[0], h[1]
        z0f, kapf, af, r0f = f["z0"], f["mxh_kappa"], f["a"], f["r0"]
        sz = np.clip((zb - z0f) / (kapf * af), -1.0, 1.0)
        area2 = float(np.sum(rb * np.roll(zb, -1) - np.roll(rb, -1) * zb))
        ccw = 1.0 if area2 >= 0 else -1.0
        dz = ccw * (np.roll(zb, -1) - np.roll(zb, 1))
        th = np.where(dz >= 0, np.where(np.arcsin(sz) < 0, np.arcsin(sz) + 2 * np.pi, np.arcsin(sz)),
                      np.pi - np.arcsin(sz))
        off = c[0] + sum(c[k] * np.cos(k * th) + s[k] * np.sin(k * th) for k in range(1, 7))
        res = np.hypot(rb - (r0f + af * np.cos(th + off)), zb - (z0f + kapf * af * np.sin(th)))
        iw = int(np.argmax(res))
        row["worst_residual_over_a"] = float(res[iw] / af)
        row["worst_residual_theta_over_pi"] = float(th[iw] / np.pi)
        #: ★★它落在下方尖角上吗——下单零的 X 点在 theta ~ 1.5 pi 一带
        row["worst_residual_z_over_a"] = float((zb[iw] - z0f) / af)
        row["z_extent_asymmetry"] = float((zb.max() + zb.min() - 2 * z0f) / af)
        out["files"].append(row)
    got = [r for r in out["files"] if "mxh_rms" in r]
    out["absent_machines"] = [m for m in ABSENT if m not in {r["machine"] for r in got}]
    for m in sorted({r["machine"] for r in got}):
        rows = [r for r in got if r["machine"] == m]
        out["by_machine"][m] = {"n_files": len(rows),
                                "worst_rms": max(r["mxh_rms"] for r in rows),
                                "all_in_band": all(r["in_band"] for r in rows)}
    out["summary"] = {"n_files": len(got), "n_machines": len(out["by_machine"]),
                      "worst_rms": max((r["mxh_rms"] for r in got), default=None),
                      "all_in_band": all(r["in_band"] for r in got) if got else None,
                      #: ★★MXH 的 kappa 与包围盒的 kappa 该几乎相同（两者都从 Z 的极值来）——
                      #: 差得大就说明拟合的 theta 分支挑错了，这是一条不花钱的自洽检查
                      "worst_kappa_gap": max((abs(r["mxh_kappa"] - r["miller_kappa"]) for r in got), default=None)}
    return out


#: ★第二套实现：FUSE 的 MillerExtendedHarmonic.jl（Meneghini），同为梯形矩法，但分支由沿轮廓走过的极值点定，
#: 与本仓按 dZ / dR 符号定分支是两份独立写的代码。★约定不同：它取 `Z = Z0 − κ a sin θ`，θ 反向 ⇒
#: `c_J = −c`、`s_J = +s`（实测确认，不是推了就算）。
JULIA_FIT = """
using MillerExtendedHarmonic, DelimitedFiles
for f in sort(filter(x->startswith(x,"b"), readdir(ARGS[1])))
    d = readdlm(joinpath(ARGS[1], f)); m = MXH(d[:,1], d[:,2], 6)
    println(f, " ", m.R0, " ", m.Z0, " ", m.ϵ*m.R0, " ", m.κ, " ", m.c0, " ", join(m.c, " "), " ", join(m.s, " "))
end
"""
CROSSCHECK = "mxh_fit_julia_crosscheck.json"


def _curve(r0, z0, a, kap, c, s, zsign, n):
    th = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    off = c[0] + sum(c[k] * np.cos(k * th) + s[k] * np.sin(k * th) for k in range(1, 7))
    return r0 + a * np.cos(th + off), z0 + zsign * kap * a * np.sin(th)


def _dist(R, Z, rb, zb):
    return np.array([np.min(np.hypot(R - r, Z - z)) for r, z in zip(rb, zb)])


def crosscheck(store: Path, julia: str, project: str) -> dict:
    """同一批轮廓交给两套实现，逐份比系数、比重构曲线、比到数据点的几何距离（同一把尺）。"""
    import subprocess
    import tempfile
    from fylite.io import fydoc
    rows, meta = [], []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for k, (machine, rel, p) in enumerate(all_sources(store)):
            if machine == "synthetic" or not Path(str(p).split("#")[0]).is_file():
                continue
            rb, zb, _, _ = read_boundary(p)
            rec = fydoc.complete("code/shape", {"settings": {}, "inputs": {"equilibrium": {
                "time_slice/boundary/outline/r": rb, "time_slice/boundary/outline/z": zb}}})
            f = {kk: float(v["value"]) for kk, v in rec["facts"].items()}
            h = np.asarray(wv_fields(rec)["mxh_harmonics"], float).reshape(2, 7)
            np.savetxt(tdp / f"b{k:02d}.txt", np.c_[rb, zb])
            meta.append((k, machine, rel, rb, zb, f, h))
        (tdp / "fit.jl").write_text(JULIA_FIT, encoding="utf-8")
        run = subprocess.run([julia, f"--project={project}", str(tdp / "fit.jl"), td],
                             capture_output=True, text=True, check=True)
    jl = {}
    for line in run.stdout.splitlines():
        p = line.split()
        if p and p[0].startswith("b"):
            v = list(map(float, p[1:]))
            jl[int(p[0][1:3])] = v
    for k, machine, rel, rb, zb, f, h in meta:
        v = jl[k]
        r0j, z0j, aj, kj, c0j = v[:5]
        cj = np.array([c0j] + v[5:11]); sj = np.array([0.0] + v[11:17])
        a = f["a"]
        Rf, Zf = _curve(f["r0"], f["z0"], a, f["mxh_kappa"], h[0], h[1], +1.0, 20000)
        Rj, Zj = _curve(r0j, z0j, aj, kj, cj, sj, -1.0, 20000)
        Rf2, Zf2 = _curve(f["r0"], f["z0"], a, f["mxh_kappa"], h[0], h[1], +1.0, 2000)
        rows.append({"machine": machine, "file": rel, "n_boundary": int(rb.size),
                     "geom_rms_fylite": float(np.sqrt(np.mean((_dist(Rf, Zf, rb, zb) / a) ** 2))),
                     "geom_rms_julia": float(np.sqrt(np.mean((_dist(Rj, Zj, rb, zb) / a) ** 2))),
                     "curve_gap_max_over_a": float(_dist(Rj, Zj, Rf2, Zf2).max() / a),
                     "max_abs_c_plus_cj": float(np.max(np.abs(h[0] + cj))),
                     "max_abs_s_minus_sj": float(np.max(np.abs(h[1][1:] - sj[1:]))),
                     "max_abs_c_minus_cj": float(np.max(np.abs(h[0] - cj))),
                     "geometry_gap": float(max(abs(r0j - f["r0"]), abs(z0j - f["z0"]), abs(aj - a)) / a + abs(kj - f["mxh_kappa"]))})
    return {"second_implementation": "FUSE MillerExtendedHarmonic.jl 2.1.2, MXH(pr, pz, 6), trapezoidal moments",
            "convention": "Julia Z = Z0 - kappa a sin(theta) => c_J = -c, s_J = +s",
            "metric": "geometric distance from each g-file boundary point to a 20000-point reconstruction, over a",
            "files": rows,
            "summary": {"n_files": len(rows),
                        "worst_coeff_gap": max(max(r["max_abs_c_plus_cj"], r["max_abs_s_minus_sj"]) for r in rows),
                        "worst_curve_gap_over_a": max(r["curve_gap_max_over_a"] for r in rows),
                        "worst_geometry_gap": max(r["geometry_gap"] for r in rows)}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=Path, required=True)
    x = sub.add_parser("crosscheck", help="the same outlines through MillerExtendedHarmonic.jl")
    x.add_argument("--out", type=Path, required=True)
    x.add_argument("--julia", default=os.environ.get("FYLITE_JULIA", "julia"))
    x.add_argument("--project", default=os.environ.get("FYLITE_JULIA_PROJECT", ""))
    args = ap.parse_args()
    from fylite.engine import benchmark as bm
    store = bm.store_dir() or Path(os.environ["FYDOC_ORACLE"])
    if args.cmd == "crosscheck":
        res = crosscheck(store, args.julia, args.project)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / CROSSCHECK).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
        print(json.dumps(res["summary"], indent=1, default=float))
        return 0
    res = readings(store)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res["summary"], indent=1, default=float))
    print(json.dumps(res["by_machine"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
