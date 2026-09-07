"""起始设计的**电流分配不由输入决定** —— 一次实测，钉在这里。

★★由来。2026-09-07 换 EAST 的装置文档（同一台机器，两份文档，数只差最后几位）时，
`validate-worker-summary` 的 `start.chan` 动了 **2.8 倍**，而它要满足的目标边界
**逐位相同**、拟合残差 `psiRms` 还略好了一点（0.016759 → 0.015696）。那不是
「换了一台机器」，是**这道反解的答案在它自己的输入上不连续**。

★★实测（EAST，`lam=1e-3`，把**一个线圈的半径**乘上 1+ε）：

======  =====================  =========
ε        `Δchan/chan`           `psi_rms`
======  =====================  =========
1e-13    **11 %**               0.00162
1e-11    11 %                   0.00162
1e-9     7.7 %                  0.00179
1e-7     8.1 %                  0.00181
======  =====================  =========

响应**不随 ε 缩小**：从 1e-13 到 1e-7 都是 10% 上下。那不是放大，是解在一条平谷里
乱跳 —— 目标函数在那个方向上几乎是平的，答案由舍入决定。而 `psi_rms` 一直在
0.0016–0.0018：**场是定的，分配不是**。

★★把岭参数扫一遍，可复现性在哪里回来（同一个 ε = 1e-13）：

=======  ==========  ==========  ======================
`lam`    `‖chan‖`    `psi_rms`   `Δchan/chan`
=======  ==========  ==========  ======================
1e-3     2.18e6      0.00168     1.1e-1   ← 今天的缺省
3e-2     1.59e6      0.00287     7.9e-3
1e-1     1.43e6      0.00429     5.9e-4
3e-1     1.26e6      0.01187     **1.0e-8**
1.0      6.59e5      0.05712     4.8e-9
=======  ==========  ==========  ======================

一条教科书式的 L 曲线：缺省的 1e-3 落在**欠正则**那一段——边界拟合得好，
而电流分配是那条平谷里的任意一点。要它可复现，代价是边界残差差 7 倍。

★★**这道闸不主张该取哪个值。** 换缺省是一次有真实代价的工程判断（0.0017 → 0.0119），
该由人来定。这里只钉住**测量本身**，好让它不腐烂：机理见内核
`case.rs::discharge_case`（岭按响应自己的列范数定尺度 `alpha * g_scale`）与
`linalg::ridge_lstsq`（组**正规方程** `AᵀA + λ²I` 再 Cholesky —— 条件数因此平方，
λ 在 `AᵀA` 上的相对阻尼是 `alpha²` = 1e-6，不是 1e-3）。

★这道闸**变红是好消息的一种**：若某天 `lam=1e-3` 下的分配也稳了，说明正则或解法
改了。那时删掉这一行，并把改了什么写下来 —— 不要把界放宽了事。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "dist" / "facts" / "device" / "east.jsonld"

#: 一次 `start_state` 是一次真的线性反解，四次要几秒 —— 值这个钱，
#: 它查的是别处查不到的东西。
pytestmark = pytest.mark.skipif(
    not DOC.is_file(),
    reason=f"没有 {DOC.relative_to(REPO)} —— 先跑 python3 tools/abox-to-facts.py east")


def _target(doc: dict) -> dict:
    """与 `app/tests/validate-worker-summary.mjs` 同一个目标位形（限制器包围盒的 0.6）。"""
    lim = doc["wall"]["description_2d"][0]["limiter"]["unit"][0]["outline"]
    r = np.asarray(lim["r"], float)
    z = np.asarray(lim["z"], float)
    return {"r0": 0.5 * (r.min() + r.max()), "z0": 0.5 * (z.min() + z.max()),
            "a": 0.6 * 0.5 * (r.max() - r.min()),
            "kappa": 1.6, "deltaU": 0.4, "deltaL": 0.5}


def _run(doc: dict, lam: float) -> dict:
    from fylite.scenario.design import start_state
    return start_state(target=_target(doc), ip=393459.5, n_points=24, n_ring=4,
                       peaking=1.0, x_weight=0.0, lam=lam, device=doc)


def _nudged(doc: dict, eps: float) -> dict:
    """把**一个线圈的半径**乘上 1+ε —— 输入能做的最小改动。"""
    out = copy.deepcopy(doc)
    rect = out["pf_active"]["coil"][0]["element"][0]["geometry"]["rectangle"]
    rect["r"] = rect["r"] * (1.0 + eps)
    return out


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(DOC.read_text(encoding="utf-8"))


def _split_moved(a: dict, b: dict) -> float:
    ca = np.asarray(a["aturns"], float)
    cb = np.asarray(b["aturns"], float)
    return float(np.linalg.norm(cb - ca) / np.linalg.norm(ca))


def test_a_perturbation_at_the_last_bit_moves_the_current_split(doc):
    """ε = 1e-13 的输入改动，把电流分配挪动百分之几 —— 实测 11%。

    ★下界取 1%：实测是 11%，留一个数量级的余地，好让这条闸子问的是
    「分配是不是不由输入决定」，而不是「今天恰好是 11.4% 还是 11.5%」。
    """
    base = _run(doc, 1e-3)
    near = _run(_nudged(doc, 1e-13), 1e-3)
    moved = _split_moved(base, near)
    assert moved > 1e-2, (
        f"ε=1e-13 下电流分配只动了 {moved:.3e} —— 比实测（11%）稳得多。"
        "正则或解法大概是改了：删掉这道闸，并把改了什么写下来。")


def test_the_field_it_makes_is_determined_even_when_the_split_is_not(doc):
    """★这一条才是要点：**场是定的**。

    同一个 ε 下拟合残差只在 0.0016–0.0018 之间动 —— 也就是说，两组差着 11% 的
    电流把目标边界拟合得一样好。所以「分配变了」不等于「答案错了」，而
    **把分配逐位钉进夹具**等于钉住一个没有被问题定下来的量。
    """
    base = _run(doc, 1e-3)
    near = _run(_nudged(doc, 1e-13), 1e-3)
    rel = abs(near["psi_rms"] - base["psi_rms"]) / base["psi_rms"]
    assert rel < 0.2, (
        f"拟合残差动了 {rel:.1%}（{base['psi_rms']:.6g} -> {near['psi_rms']:.6g}）"
        "—— 那就不只是分配在动了，是这一解本身变了，要查。")


def test_a_heavier_ridge_makes_the_split_reproducible_and_says_what_it_costs(doc):
    """λ = 0.3 上分配稳到 1e-8，代价是边界残差差约 7 倍。

    ★两头都断言：**稳住了**，以及**代价是多少**。只断言前者，会让「把 lam 调大」
    看起来是免费的。
    """
    base = _run(doc, 3e-1)
    near = _run(_nudged(doc, 1e-13), 3e-1)
    moved = _split_moved(base, near)
    assert moved < 1e-6, (
        f"λ=0.3 上分配仍动了 {moved:.3e} —— 实测是 1e-8。"
        "平谷比记下来的更宽，或者解法变了。")
    loose = _run(doc, 1e-3)
    cost = base["psi_rms"] / loose["psi_rms"]
    assert cost > 3.0, (
        f"λ 从 1e-3 提到 0.3，边界残差只差了 {cost:.1f} 倍 —— 实测约 7 倍。"
        "代价变小了是好事，但要先弄清为什么，再改这个数。")
