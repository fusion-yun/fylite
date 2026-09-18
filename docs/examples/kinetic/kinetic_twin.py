#!/usr/bin/env python3
"""KEFIT 动理学反演算例：在 EAST #137985 @ 4.041 s 的孪生上把整条链逐段跑一遍。

★★为什么用孪生而不是真炮：动理学反演的每一步都要问「对不对」，而真炮上没有答案——
没有人测过 q0。孪生的真值平衡是 fylite 自己的前向解（`code/forward`），它自带压强剖面，
于是「动理学测点该落在哪个 psi_N」「q0 该是多少」都是**算得出来的**。本脚本因此能对
每一段报一个**相对真值**的数，而不只是「跑通了」。代价照实说：真值与测量同出 fylite
的前向解，所以这里证明的是「反演与前向互为逆」那一层，不是「重构准」。

逐段（与本目录 `kinetic.md` 的节号一一对应）：

    s0   阶段 0 · 基准平衡：纯磁测量反演（npp = nff = 1）
    s1   阶段 1 · 剖面构造：9 个中平面测点 → code/profile_fit（GCV 定阶）；
                    code/separatrix_align 按 Te,sep 平移标签（合成台基）
    s3   阶段 3 · 动理学反演：压强行进设计矩阵（映射给对 / 故意给错 +0.12）
    s4   阶段 4 · 自洽外环：kinetic_passes = 6，逐遍证书（chi2/dof · 映射移动 · 最优遍）
    fi   快离子压强扣除（p_fast_profile）：sigma 一位不动
    cp   源剖面曲率正则（curv_p / curv_f）：把 (2,2) 简并档压回

需要（与 `python/tests/test_benchmark_equilibrium.py` 同一套，缺一样就按名退出）：

    $FYDOC_ORACLE        fydoc 的 cases/ 树（FYDOC-CASE-23：#137985 的线圈电流与 Ip）
    $FYLITE_DEVICE_DIR   EAST 装置牌（dist/facts/device/east）
    $FYLITE_KERNEL_LIB   内核库（缺省用 python/fylite/_lib/ 里随包的那一份）

    uv run --no-project --with numpy --with pyyaml python docs/examples/kinetic/kinetic_twin.py

输出一份 JSON（stdout），`kinetic.md` 里的数都出自它。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))
CASE = "FYDOC-CASE-23-east-137985-efit-east"
#: 故意推错的映射量（psi_N）——与校验册 `eq-reconstruct-kinetic-outer` 同一个数
WRONG = 0.12


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _case() -> Path:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / "case.yaml").is_file():
        sys.exit(f"no {CASE} in the case store: set $FYDOC_ORACLE to the fydoc cases/ tree")
    return store / CASE


def main() -> int:
    tool = _tool()
    case = _case()
    truth, meas, dev, _ = tool.twin_truth(case)
    tf_ = truth["facts"]
    q0_true = tf_["q0"]
    lw, pw = tool.sigma_weights(meas)
    disc = {"fylite:channel_aturns": meas["aturns"], "fylite:ip": np.array([meas["ip"]]),
            "fylite:b_tor": np.array([meas["b_tor"]]),
            "fylite:flux_loop": meas["flux_loop"], "fylite:loop_weight": lw,
            "fylite:probe_field": meas["probe_field"], "fylite:probe_weight": pw}

    def recon(extra=None, **settings):
        d = dict(disc); d.update(extra or {})
        st = dict(tool.RECON, zc_anchor=-0.002); st.update(settings)
        return tool.door("code/reconstruction", st, {"device": dev, "discharge": d})

    def rel(f):
        return {"q0": f["q0"], "q0_err": f["q0"] / q0_true - 1.0, "q95": f["q95"],
                "li3": f["li3"], "chi2_per_dof": f["chi2_per_dof"], "chi2_kin": f["chi2_kin"],
                "kinetic_rows": int(f["kinetic_rows"]), "residual": f["residual"],
                "iterations": int(f["iterations"])}

    out: dict = {"case": f"EAST #137985 @ 4.041 s twin ({CASE})",
                 "truth": {"q0": q0_true, "q95": tf_["q95"],
                           "axis_r": tf_["axis_r"], "axis_z": tf_["axis_z"]}}

    # ---- s0 · 基准平衡：纯磁 ------------------------------------------------------------
    f0, fl0, _ = recon()
    s0 = rel(f0)
    s0.update({"n_loops": int(f0["n_loops"]), "n_probes_used": int(f0["n_probes_used"]),
               "worst_channel_sigma": f0["worst_channel_sigma"]})
    if "pprime_sigma" in fl0 and "pprime" in fl0:
        sp, pp = np.abs(np.asarray(fl0["pprime_sigma"], float)), np.abs(np.asarray(fl0["pprime"], float))
        ok = pp > 1e-12 * max(pp.max(), 1e-300)
        s0["pprime_band_median_rel"] = float(np.median(sp[ok] / pp[ok]))
    out["s0_magnetics_only"] = s0

    # ---- s1 · 剖面构造：中平面 9 点 → psi_N → 拟合 -----------------------------------------
    _, tfld, _ = tool.door("code/forward", truth["settings"],
                           {"device": dev, "discharge": {"fylite:channel_aturns": meas["aturns"],
                                                         "fylite:ip": np.array([meas["ip"]])}})
    gr, gz = np.asarray(tfld["grid_r"], float), np.asarray(tfld["grid_z"], float)
    psi = np.asarray(tfld["psi"], float).reshape(len(gr), len(gz))
    psin1d, pres1d = np.asarray(tfld["psin_1d"], float), np.asarray(tfld["pres"], float)
    span = tf_["psi_axis"] - tf_["psi_bnd"]

    def psi_at(r, z):
        i = int(np.clip(np.searchsorted(gr, r) - 1, 0, len(gr) - 2))
        j = int(np.clip(np.searchsorted(gz, z) - 1, 0, len(gz) - 2))
        a = (r - gr[i]) / (gr[i + 1] - gr[i]); b = (z - gz[j]) / (gz[j + 1] - gz[j])
        return ((1 - a) * (1 - b) * psi[i, j] + a * (1 - b) * psi[i + 1, j]
                + (1 - a) * b * psi[i, j + 1] + a * b * psi[i + 1, j + 1])

    r_pts = np.linspace(tf_["axis_r"] + 0.02, tf_["axis_r"] + 0.42, 9)
    z_pts = np.full(9, tf_["axis_z"])
    xn = np.array([float(np.clip((tf_["psi_axis"] - psi_at(r, z)) / span, 0.0, 1.0)) for r, z in zip(r_pts, z_pts)])
    p_pts = np.interp(xn, psin1d, pres1d)
    w_pts = np.full(9, 1.0 / (0.05 * max(abs(p_pts).max(), 1.0)))

    from fylite import scenario as S
    fit = S.analysis.profit(xn, p_pts, sigma_frac=0.05)
    out["s1_profile"] = {"r_m": r_pts.round(4).tolist(), "psin_true": xn.round(4).tolist(),
                         "p_peak_pa": float(p_pts.max()), "profit_order": fit["order"],
                         "profit_chi2_per_dof": fit["chi2_per_dof"],
                         "profit_basis": fit["provenance"]["basis"]}
    #: 1.4 分离面对齐：一条合成的 tanh 台基（Te 挂在 psi_N 上，Te(1) ≈ 19 eV），要它落到 Te,sep = 80 eV
    x = np.linspace(0.0, 1.0, 201)
    te = 900.0 * (1.0 - x ** 2) ** 1.5 + 200.0 * (1.0 - np.tanh((x - 0.97) / 0.02))
    prof = {"core_profiles": {"profiles_1d/grid/psi_norm": x, "profiles_1d/electrons/temperature": te}}
    fa, _, _ = tool.door("code/separatrix_align", {"te_sep": 80.0}, prof)
    sa = {k: fa[k] for k in ("te_sep", "separatrix_shift", "te_at_one_before", "te_at_one_after",
                             "te_grad_before", "te_grad_after")}
    try:                    #: ★它不产生 Te,sep：不给就按名拒绝，而不是用一个缺省值
        tool.door("code/separatrix_align", {}, prof)
        sa["without_te_sep"] = "ran (unexpected)"
    except Exception as e:  # noqa: BLE001 — a refusal is a reading
        sa["without_te_sep_refused"] = str(e).splitlines()[0][:240]
    out["s1_separatrix_align"] = sa

    # ---- s3 · 动理学反演：映射给对 / 给错 -------------------------------------------------
    rows_true = {"fylite:pressure": p_pts, "fylite:pressure_x": xn, "fylite:pressure_weight": w_pts}
    f3, _, _ = recon(rows_true)
    out["s3_kinetic_true_map"] = rel(f3)
    wrong = np.clip(xn + WRONG, 0.0, 1.0)
    rows_wrong = {"fylite:pressure": p_pts, "fylite:pressure_x": wrong, "fylite:pressure_weight": w_pts,
                  "fylite:pressure_r": r_pts, "fylite:pressure_z": z_pts}
    f3w, _, _ = recon(rows_wrong, kinetic_passes=1)
    s3w = rel(f3w); s3w["kinetic_map_shift"] = f3w["kinetic_map_shift"]
    out["s3_kinetic_wrong_map_single_pass"] = s3w

    # ---- s4 · 自洽外环 -------------------------------------------------------------------
    f4, fl4, n4 = recon(rows_wrong, kinetic_passes=6, kinetic_tol=1e-4)
    s4 = rel(f4)
    s4.update({"kinetic_passes_run": int(f4["kinetic_passes_run"]), "kinetic_best_pass": int(f4["kinetic_best_pass"]),
               "kinetic_map_shift": f4["kinetic_map_shift"],
               "pass_chi2_per_dof": np.asarray(fl4["kinetic_pass_chi2_per_dof"], float).tolist(),
               "pass_map_shift": np.asarray(fl4["kinetic_pass_map_shift"], float).tolist(),
               "improvement_q0": abs(s3w["q0_err"]) / max(abs(s4["q0_err"]), 1e-300),
               "notes": [s for s in n4 if "kinetic" in s]})
    out["s4_outer_loop"] = s4

    # ---- fi · 快离子压强扣除 ---------------------------------------------------------------
    xf = np.linspace(0.0, 1.0, 41)
    p_fast = 0.15 * np.interp(xf, xn, p_pts) * (1.0 - xf ** 2)
    ff0, ffl0, _ = recon(rows_true)
    ff1, ffl1, nf = recon(dict(rows_true, **{"fylite:p_fast_profile": p_fast}))
    out["fast_ion"] = {"p_fast_max": ff1["p_fast_max"],
                       "weights_bit_identical": bool(np.array_equal(np.asarray(ffl0["meas_weight"], float),
                                                                    np.asarray(ffl1["meas_weight"], float))),
                       "chi2_kin_without": ff0["chi2_kin"], "chi2_kin_with": ff1["chi2_kin"],
                       "q0_without": ff0["q0"], "q0_with": ff1["q0"],
                       "notes": [s for s in nf if "p_fast" in s]}

    # ---- cp · 源剖面曲率正则 ---------------------------------------------------------------
    fd, _, _ = recon(npp=2, nff=2)
    fr, _, _ = recon(npp=2, nff=2, curv_p=1e-3, curv_f=1e-3)
    out["curvature_prior"] = {"base_q0_err": f0["q0"] / q0_true - 1.0,
                              "deg_22_q0_err": fd["q0"] / q0_true - 1.0, "deg_22_chi2_per_dof": fd["chi2_per_dof"],
                              "reg_1e-3_q0_err": fr["q0"] / q0_true - 1.0, "reg_1e-3_chi2_per_dof": fr["chi2_per_dof"],
                              "curv_p_echo": fr["curv_p"], "curv_f_echo": fr["curv_f"]}

    json.dump(out, sys.stdout, indent=1, ensure_ascii=False, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
