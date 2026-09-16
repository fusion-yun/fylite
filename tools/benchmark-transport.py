#!/usr/bin/env python3
"""Pereverzev-Corrigan 稳定化的判据测量（记录 `tr-paradigm-pereverzev`）。

★★2026-09-16：本册重起后 `tr/` 组的第一条记录。量的是 `FR-TR-005` 抄录判据的三句话：

1. **P-C 离散精确对消** —— 加进去的那一项在**离散**意义下抵消，不是只在连续极限下抵消。
   一个只在连续意义上对消的构造，每一项光滑性检查都过得去，而定态落在另一条剖面上。
2. **定态对 $d_{pc}$ 不敏感** —— 于是定态解与 $d_{pc}$ 取多少无关。这两句其实是同一件事的
   因与果，所以一起量：扫 $d_{pc}$，比定态剖面。
3. **刚性闭包下 Picard 收敛（裸环停滞对照）** —— 这一句要的是**对照**：裸环停滞、加了
   稳定化的收敛。★没有对照，「跑通了」与「这一项在起作用」分不开。

★本工具不引外部码。参考是一条**解析不变性**：P-C 项按构造在不动点上恒等消去，所以定态
必须与 $d_{pc}$ 无关。这使本记录属 `verification`——参考是解析陈述，不是另一次运行。

★★**量到的第三句话没有落地**，如实记在读数里：`stagnation` 段扫遍 `stiff` 闭包的刚度盒
（`p1` × `p2`，chi 动态范围最高 8001 倍），裸环 **每一点都收敛**。机理在闭包的形式里——
`case.rs::diffusivity_of` 是 `chi0 * (p1 + p2 g/(1+g))`，对梯度**有界且饱和**：
g→∞ 时 chi 趋于 `chi0 (p1+p2)`。而 P-C 要对付的正是 chi 随梯度**不封顶**（或带阈值）的那类
闭包。于是这一族闭包里造不出停滞，判据的对照项**在本接口上无从演示**。

跑的是 `code/transport`（`case.rs::transport_case`），定态 = `dt = inf` · `steps = 1`；
`tol` / `max_inner` 取内核自己那道门 `the_pereverzev_corrigan_fixed_point_is_independent_of_d_pc`
的预算（1e-13 / 4000），它自报的接受档是 rel < 1e-9。

用法：``python tools/benchmark-transport.py readings --out docs/benchmark/readings``
环境：`$LD_LIBRARY_PATH` 指到 fylite-syslibs，`$PYTHONPATH` 指到 `python/`，一个带
`code/transport` 的内核。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: ★内核自己那道门的预算，照抄——本册量的是同一个不动点，换一套预算就不是同一件事了
TOL = 1e-13
MAX_INNER = 4000
N_RHO = 41

#: 扫的 d_pc。★0 是参照点（裸环），不是"关掉稳定化的一个特例"——判据比的就是它
D_PC = (0.0, 0.1, 1.0, 10.0, 40.0, 100.0)

#: 刚度盒：p1 是 chi 的地板，p2 是梯度驱动的幅度，动态范围 (p1+p2)/p1
STIFFNESS = tuple((p1, p2) for p1 in (0.25, 0.05, 0.01) for p2 in (1.75, 5.0, 20.0, 80.0))


def steady(closure: str, d_pc: float, **kw) -> dict:
    """一次定态解。`dt = inf` 且 `steps = 1` 是 prescribed 闭包的适定用法。"""
    from fylite.scenario.model import transport
    return transport(n_rho=N_RHO, closure=closure, dt=float("inf"), steps=1,
                     d_pc=d_pc, tol=TOL, max_inner=MAX_INNER, **kw)


def sweep(closure: str, **kw) -> dict:
    """扫 d_pc，把每一次的定态剖面与 d_pc = 0 的那一条比。"""
    base = steady(closure, 0.0, **kw)
    out = []
    for d in D_PC:
        r = base if d == 0.0 else steady(closure, d, **kw)
        #: ★逐点相对偏差的 inf 范数。分母夹一个下限，免得轴上的小值把比值放大成噪声
        dev = float(np.max(np.abs(r["y"] - base["y"]) / np.maximum(np.abs(base["y"]), 1e-30)))
        out.append({"d_pc": d, "converged": bool(r["converged"]),
                    "inner_iterations": int(r["inner_iterations"]),
                    "residual": float(r["residual"]),
                    "rel_deviation_from_d_pc_0": dev})
    return {"settings": dict(kw), "points": out}


def stagnation() -> list[dict]:
    """★判据的对照项：裸环（d_pc = 0）在刚度盒里停不停滞。

    量的是 `converged` 与 `inner_iterations`——**不是**剖面。一个停滞的裸环会顶到
    `max_inner` 且 `converged = False`；本盒里一个都没有，这才是要记下来的那件事。
    """
    rows = []
    for p1, p2 in STIFFNESS:
        r = steady("stiff", 0.0, chi0=1.0, p1=p1, p2=p2)
        rows.append({"p1": p1, "p2": p2,
                     #: chi = chi0 (p1 + p2 g/(1+g))：g→∞ 时的饱和值比上 g=0 的地板
                     "chi_dynamic_range": (p1 + p2) / p1,
                     "converged": bool(r["converged"]),
                     "inner_iterations": int(r["inner_iterations"]),
                     "residual": float(r["residual"])})
    return rows


def readings() -> dict:
    const = sweep("constant", chi0=1.0)
    stiff = sweep("stiff", chi0=1.0)
    stag = stagnation()
    return {
        "reference": "解析不变性：P-C 项按构造在不动点上恒等消去，故定态与 d_pc 无关。"
                     "接受档 rel < 1e-9 取内核自己那道门 "
                     "`transport.rs::the_pereverzev_corrigan_fixed_point_is_independent_of_d_pc` 的自报值。",
        "door": "code/transport (case.rs::transport_case)",
        "closure_form": "chi = chi0 * (p1 + p2 * |grad y| / (1 + |grad y|))  —— 有界、饱和",
        "settings": {"n_rho": N_RHO, "tol": TOL, "max_inner": MAX_INNER,
                     "steady": "dt = inf, steps = 1", "theta": 1.0},
        "d_pc_independence": {"constant": const, "stiff": stiff},
        "stagnation_control": {
            "question": "裸环（d_pc = 0）在刚度盒里停不停滞——判据要的对照",
            "answer": "本盒内无一停滞：每一点都收敛",
            "mechanism": "闭包对梯度有界且饱和（g→∞ 时 chi → chi0 (p1+p2)），"
                         "不是 P-C 要对付的那类不封顶 / 带阈值的刚性闭包",
            "rows": stag,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("readings", help="算 fylite 这一侧，写读数")
    p.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "benchmark" / "readings")
    a = ap.parse_args()

    data = readings()
    a.out.mkdir(parents=True, exist_ok=True)
    dest = a.out / "transport_pc.json"
    #: ★sort_keys + 末尾换行：读数要能逐位复现，否则它的 sha256 每次都变
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
