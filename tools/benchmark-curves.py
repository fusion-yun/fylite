#!/usr/bin/env python3
"""把**对标的曲线本身**抽成读数：磁面等高线与 q 剖面，两侧画在同一张图上。

★★**为什么要有这一步**：登记册此前的读数只存标量（RMS、max、轴位移）。一个标量回答
「差多少」，回答不了「**差在哪儿**」——芯部还是边缘？整体平移还是局部变形？
B-14 的边界最大 12.7 mm 对中位 3.4 mm 早就在说「偏差不均匀」，但只有画出来才知道不均匀在哪。

★**只抽曲线，不抽整片场**：等高线是折线（每条几十到几百个点），比整张 129x129 的 psi 场小两个
量级，而图要的正是折线。★这一条决定了读数件不会从几 KB 涨成几百 KB。

★**提线用 matplotlib，渲染不用**：这条链本来就依赖 scipy 与 matplotlib
（`benchmark-fixed-boundary.py` 的 `compare()` 就在用 `matplotlib.path`），
所以拿它提等高线是一致的；而画图的 `benchmark-figures.py` 一个第三方库都不用——
文档重建不该拖进绘图栈。

用法::

    FYLITE_KERNEL_LIB=… python tools/benchmark-curves.py solovev
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "benchmark" / "readings"
LEVELS = (0.1, 0.3, 0.5, 0.7, 0.9)      # psi_N 等高线画哪几条
Q_X = np.linspace(0.05, 0.95, 46)        # q 剖面取样点


def tool():
    spec = importlib.util.spec_from_file_location("fb", ROOT / "tools" / "benchmark-fixed-boundary.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def contours(psin_of, prob, levels=LEVELS, nr=241, nz=321) -> dict:
    """在保持的轮廓外接框上取 psi_N，提出每一条等值线的折线。

    ★等值线可能分成几段（尤其贴近边界那一条），所以每个 level 存**若干段**，不是一条。
    """
    import matplotlib.pyplot as plt   # 只用它的等值线算法，不画任何东西
    plt.switch_backend("Agg")
    r = np.linspace(prob["r"].min(), prob["r"].max(), nr)
    z = np.linspace(prob["z"].min(), prob["z"].max(), nz)
    R, Z = np.meshgrid(r, z, indexing="ij")
    V = psin_of(R.ravel(), Z.ravel()).reshape(R.shape)
    #: ★★**轮廓之外遮掉**：样条在等离子体外仍给得出值，于是同一条 level 会在真空区再穿越一次，
    #: 冒出几段杂散折线（实测 fylite 侧每条 level 多出六段）。解析解不会，因为它的形式不同——
    #: **于是三侧画在一起时，多出来的那几段看着像「fylite 算错了」，其实是没有遮。**
    #: 遮罩与 `benchmark-fixed-boundary.py:compare()` 用的是同一条判定，比较区域因此一致。
    from matplotlib.path import Path as MPath
    ins = MPath(np.c_[prob["r"], prob["z"]]).contains_points(np.c_[R.ravel(), Z.ravel()])
    V = np.where(ins.reshape(R.shape), V, np.nan)
    fig = plt.figure()
    cs = fig.gca().contour(R, Z, V, levels=list(levels))
    out = {}
    for lv, seg in zip(cs.levels, cs.allsegs):
        keep = []
        for s in seg:
            s = np.asarray(s, float)
            if len(s) < 8:
                continue
            #: 折线抽稀：图上看不出的点不必入库
            step = max(1, len(s) // 200)
            keep.append({"r": [round(float(x), 5) for x in s[::step, 0]],
                         "z": [round(float(x), 5) for x in s[::step, 1]]})
        if keep:
            out[f"{lv:g}"] = keep
    plt.close(fig)
    return out


def solovev() -> int:
    t = tool()
    sol = t.Solovev()
    prob, exact = sol.problem(), sol.side()
    fy = t.fylite_side(prob, 129)

    data = {
        "what": "eq-forward / Solov'ev 定边界：对标的曲线本身（等高线与 q 剖面）",
        "problem": {"r0": prob["r0"], "f_edge": prob["f_edge"], "ip_inside": prob["ip_inside"]},
        "boundary": {"r": [round(float(x), 5) for x in prob["r"]],
                     "z": [round(float(x), 5) for x in prob["z"]],
                     "comment": "保持的轮廓：两侧解的是同一条边界，所以它只画一次"},
        "levels": list(LEVELS),
        "contours": {
            "analytic": contours(exact["psin"], prob),
            "fylite_129": contours(fy["psin"], prob),
        },
        "axis": {"analytic": [float(exact["axis"][0]), float(exact["axis"][1])],
                 "fylite_129": [float(fy["axis"][0]), float(fy["axis"][1])]},
    }

    #: q 剖面：解析 Solov'ev 只给得出 q0（`q_of` 为 None），所以这一栏是 fylite 对 CHEASE
    if t.CHEASE.is_file():
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            run = t.chease_run(prob, pathlib.Path(td) / "ns80", 80, "Solov'ev fixed boundary (curves)")
            ch = t.gfile_side(run["EQDSK_COCOS_02.OUT"])
        data["q_profile"] = {
            "x": [round(float(v), 4) for v in Q_X],
            "fylite_129": [round(float(v), 6) for v in fy["q_of"](Q_X)],
            "chease_ns80": [round(float(v), 6) for v in ch["q_of"](Q_X)],
            "comment": "★解析 Solov'ev 只给得出 q0（没有 q(psi) 闭式），所以这一栏比的是两个码；"
                       "真值一侧只有 q0 那一个点，见记录的 criterion/5。",
        }
        data["contours"]["chease_ns80"] = contours(ch["psin"], prob)
        data["axis"]["chease_ns80"] = [float(ch["axis"][0]), float(ch["axis"][1])]
    else:
        data["q_profile"] = {"absent": f"CHEASE 未构建（{t.CHEASE}）——q 剖面一栏空着，不编"}

    p = OUT / "solovev_curves.json"
    p.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)}  ({p.stat().st_size / 1024:.0f} KB)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["solovev"])
    a = ap.parse_args()
    return {"solovev": solovev}[a.what]()


if __name__ == "__main__":
    raise SystemExit(main())
