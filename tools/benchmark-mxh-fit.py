"""MXH boundary fit on every g-file this checkout can reach (register record `FR-EQ-013`).

★★判据点名「7 机型 MAST / DIII-D / JET RMS ≤ 2.4 %」。**本机没有那 7 个机型**——
g-file 语料只有 EAST（3 炮）· DIII-D（1 炮，来自 GACODE/NEO 的 profile_data）· CFEDR（3 份）
与一份合成件，共 4 个机型。所以这一支量的是**本机拿得到的那些**，MAST / JET 两格照实标未评。

★量的是什么：把 g-file 的 `rbbbs/zbbbs` 边界拟合成 MXH 形（`code/shape` 的 `mxh_*`），
报每份件的 RMS（已按小半径归一）与拟合出的 kappa / delta / zeta，并与同一扇门用包围盒
读出来的 Miller 度量并排——★**两者不是一回事**：Miller 是读数，MXH 是拟合，只有后者有残差。

Subcommand: ``readings --out DIR``.  Environment: ``$FYDOC_ORACLE``, a kernel with ``code/shape``.
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
#: 判据点名却本机没有的机型
ABSENT = ["mast", "jet"]


def read_boundary(path: Path):
    """★用包**自己的** g-file 读取器，不另写一个。

    初版手搓了一个按标量数数的解析器，在 `.../ONETWO/FILES/gEQDSK/g0.99999` 上当场
    崩在抬头（那一行的末两个字段不是 nw / nh）。★**一份格式已经有读取器时，
    第二个解析器不是省事，是又一处会漂的约定。**
    """
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
    out = {"band_rms": BAND, "absent_machines": ABSENT,
           "_comment": "判据点名 7 机型（含 MAST / JET），本机只有 4 个机型；那两格未评",
           "files": [], "by_machine": {}}
    for machine, rel in SOURCES:
        p = store / rel
        if not p.is_file():
            out["files"].append({"machine": machine, "file": rel, "skipped": "not in the case store"})
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    from fylite.engine import benchmark as bm
    store = bm.store_dir() or Path(os.environ["FYDOC_ORACLE"])
    res = readings(store)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res["summary"], indent=1, default=float))
    print(json.dumps(res["by_machine"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
