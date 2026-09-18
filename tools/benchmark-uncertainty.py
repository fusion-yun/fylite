"""Posterior covariance and sigma bands from the reconstruction fit (register record `NR-EQ-003`).

★★判据只有一句：「后验 / sigma 带随 fit 报告出」。这一支量的是它**报出来之后对不对**——
一个协方差唯一可证伪的检验是「照它说的噪声反复拟合，系数真的按它散开吗」，而那一道锚在内核仓
（`the_posterior_covariance_is_the_scatter_the_fit_would_actually_have`，4000 次蒙特卡洛）。
这里问的是另外两件：**带在真算例上是多宽**，以及**它随测量权重怎么走**。

★★后者才是这一支的要害：sigma 带若不随输入的 sigma 动，那它就不是不确定度，是一条装饰。
把所有测量的 sigma 整体放大 k 倍，后验 sigma 该同步放大 k 倍——这是线性拟合的精确性质。

Subcommand: ``readings --out DIR``.  Environment: ``$FYDOC_ORACLE``, ``$FYLITE_DEVICE_DIR``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "uncertainty_east137985.json"
#: 测量 sigma 的整体缩放档
SIGMA_SCALE = (0.5, 1.0, 2.0)


def _eq():
    spec = importlib.util.spec_from_file_location(
        "benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def readings(case: Path) -> dict:
    eqt = _eq()
    truth, meas, dev, _ = eqt.twin_truth(case)
    out = {"case": CASE, "sigma_scale": list(SIGMA_SCALE), "runs": {}}
    base = None
    #: ★★**缩放的是权重，不是测量字典里某个 `_sigma` 键**——这个孪生的测量里根本
    #: 没有那种键，权重是从 `SERROR` × 量值现算的。初版按键名缩放，什么也没改到，
    #: 于是三档比值全是 1.0000，看着像「sigma 带不随输入动」的重大缺陷。
    #: ★**那是我的量法错，不是门的错**；留在这里因为它是这一支最容易踩的一脚：
    #: 一个什么都没改的对照组，产出的正是「完美的不变性」。
    lw0, pw0 = eqt.sigma_weights(meas)
    for k in SIGMA_SCALE:
        lw, pw = lw0 / k, pw0 / k          # w = 1/sigma
        disc = {"fylite:channel_aturns": meas["aturns"], "fylite:ip": np.array([meas["ip"]]),
                "fylite:b_tor": np.array([meas["b_tor"]]),
                "fylite:flux_loop": meas["flux_loop"], "fylite:loop_weight": lw,
                "fylite:probe_field": meas["probe_field"], "fylite:probe_weight": pw}
        f, fl, _ = eqt.door("code/reconstruction", dict(eqt.RECON, zc_anchor=0.0),
                            {"device": dev, "discharge": disc})
        cov = np.asarray(fl["coefficient_covariance"], float)
        n = int(round(np.sqrt(cov.size)))
        cov = cov.reshape(n, n)
        ps = np.asarray(fl["pprime_sigma"], float)
        fs = np.asarray(fl["ffprim_sigma"], float)
        pp = np.asarray(fl["pprime"], float)
        row = {"chi2_per_dof": f.get("chi2_per_dof"), "dof": f.get("dof"),
               "n_coef": n,
               "coef_sigma": [float(np.sqrt(max(cov[i, i], 0.0))) for i in range(n)],
               "pprime_sigma_max": float(np.nanmax(ps)),
               "ffprim_sigma_max": float(np.nanmax(fs)),
               #: ★带相对于剖面本身有多宽——这是读者真正想知道的那个数
               #: ★下限取**剖面自身的尺度**而非 `tiny`：p' 在边上可以真的过零，
               #: 除以一个次正规数得到的是 inf，那不是「带无限宽」，是除法的产物
               "pprime_band_over_value_median": float(np.nanmedian(
                   np.abs(ps) / np.maximum(np.abs(pp), 1e-6 * np.nanmax(np.abs(pp))))),
               "cov_is_symmetric": float(np.max(np.abs(cov - cov.T))),
               "cov_min_eigenvalue": float(np.min(np.linalg.eigvalsh(0.5 * (cov + cov.T))))}
        out["runs"][str(k)] = row
        if k == 1.0:
            base = row
    b = out["runs"]["1.0"]
    out["scaling"] = {
        "_comment": "线性拟合的精确性质：测量 sigma 整体乘 k，后验 sigma 也该乘 k",
        "pprime_sigma_ratio": {str(k): out["runs"][str(k)]["pprime_sigma_max"] / b["pprime_sigma_max"]
                               for k in SIGMA_SCALE},
        "coef_sigma_ratio": {str(k): [a / c for a, c in zip(out["runs"][str(k)]["coef_sigma"], b["coef_sigma"])]
                             for k in SIGMA_SCALE}}
    assert base is not None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--case", type=Path)
    args = ap.parse_args()
    case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE
    res = readings(case)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1, default=float)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
