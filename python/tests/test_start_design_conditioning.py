"""起始设计的电流分配**由输入决定** —— 一次实测，和它花了什么代价。

★★由来。2026-09-07 换 EAST 的装置文档（同一台机器，两份文档，数只差最后几位）时，
`validate-worker-summary` 的 `start.chan` 动了 **2.8 倍**，而它要满足的目标边界
**逐位相同**、拟合残差 `psiRms` 还略好了一点。

★★三次假设，前两次被测量否掉：

* **不是**岭没起作用 —— 它按响应自己的列范数定尺度（`pulse.rs::start_currents`
  里 `lam = sp.lambda * g_scale`），augment 之后正定。
  （我一度写「有效阻尼是 `alpha²`」，**那是错的**：用 `λI` 增广与在 `AᵀA` 上加
  `λ²` 是同一件事，阻尼就是 `λ`。）
* **不是**迭代跑满预算 —— 把求解器的收敛旗接出来看（同日补的
  `start_iterations` / `start_converged`，此前在 `let (x, _) = …` 里被丢掉），
  它在 499 / 4000 次上按自己的判据停了。
* **是**解法与目标函数**合起来**，而且**两处都得动**：无界时这是一个有闭式解的岭
  最小二乘，而内核当时走投影 Barzilai-Borwein 梯度；一阶法停在「投影梯度 ≤
  1e-12·pg0」上，在一条平谷里**梯度小不蕴含位置定**。但只换解法不够 ——
  λ=1e-3 上的精确极小点要 **8.24e6 A·turns**，是迭代解的近四倍：迭代从 0 出发
  提前停下，一直在**当一层隐式正则**（early stopping）替这个太轻的岭兜底。

★★**顺序是先定 λ，再换解法。** 用户裁定（2026-09-07）：λ 缺省 **3e-1**，直接解。
下表是直接解法下的 L 曲线（EAST，ε=1e-13，24 个边界点，无控制行、无 null 行）：

=======  ==========  ==========  ==============
`lam`    `‖chan‖`    `psi_rms`   `Δchan/chan`
=======  ==========  ==========  ==============
1e-3     8.24e6      0.00095     1.4e-10
3e-2     1.61e6      0.00278     3.3e-12
1e-1     1.43e6      0.00428     1.8e-13
3e-1     1.26e6      0.01187     8.9e-14  ← 缺省
1.0      6.59e5      0.05712     6.0e-14
=======  ==========  ==========  ==============

选中的这一行**买到的**是：1e-13 的扰动只动 8.9e-14，即位移与扰动同量级 ——
这是一个良态线性响应该有的样子，不是「病态放大」，更不是原先那种「在平谷里乱跳」
（当时 1e-13 到 1e-7 的扰动一律动 10 % 上下，**不随扰动缩小**）。
**付出的**是边界残差从 0.00168（旧缺省，迭代）涨到 0.01187，约七倍。
**换来的另一件**是电流小了 42 %（2.18e6 → 1.26e6 A·turns）。

★这道闸**变红是好消息的一种**：若某天在更小的 λ 上也稳得住，说明解法或标度改了。
那时改的是下面的数，不是把界放宽 —— 并把新的三列（稳定度 · 残差 · 电流范数）写下来。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "dist" / "facts" / "device" / "east.jsonld"

#: 内核 `case.rs` 两处 `s.get("lam", …)` 与 Python `start_state(lam=…)` 的缺省。
#: ★这里不传 `lam`，走缺省 —— 这道闸查的就是**缺省**定在哪。
LAM_DEFAULT = 3e-1
#: 2026-09-07 之前的缺省，留作对照行（下面最后一条量它的代价）。
LAM_OLD = 1e-3

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


def _run(doc: dict, lam: float | None = None, ip: float = 393459.5) -> dict:
    """起始设计一次，连同内核报回来的求解器事实。`lam=None` 走缺省。"""
    import fylite.scenario.design as design
    settings = design._start_settings(_target(doc), ip, n_points=24,
                                      xpoint=None, x_weight=0.0)
    settings.update(stage="start", n_ring=4.0, peaking=1.0)
    if lam is not None:
        settings.update(lam=float(lam))
    rec = design._complete(settings, {}, device=doc)
    facts = rec["facts"]
    if isinstance(facts, dict):
        facts = {k: (v["value"] if isinstance(v, dict) else v) for k, v in facts.items()}
    else:
        facts = {f["key"]: f["value"] for f in facts}
    out = design._start_of(rec)
    out["facts"] = facts
    return out


def _nudged(doc: dict, eps: float, coil: int = 0) -> dict:
    """把**一个线圈的半径**乘上 1+ε —— 输入能做的最小改动。"""
    out = copy.deepcopy(doc)
    rect = out["pf_active"]["coil"][coil]["element"][0]["geometry"]["rectangle"]
    rect["r"] = rect["r"] * (1.0 + eps)
    return out


def _moved(a: dict, b: dict) -> float:
    ca = np.asarray(a["aturns"], float)
    cb = np.asarray(b["aturns"], float)
    return float(np.linalg.norm(cb - ca) / np.linalg.norm(ca))


def _norm(a: dict) -> float:
    return float(np.linalg.norm(np.asarray(a["aturns"], float)))


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(DOC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base(doc) -> dict:
    return _run(doc)


def test_the_same_input_gives_the_same_answer(doc, base):
    """★先钉最起码的一条：确定性。它一旦不成立，下面几条都不必读。"""
    assert _moved(base, _run(doc)) == 0.0


def test_the_default_ridge_is_the_one_that_was_decided(doc, base):
    """★缺省 λ 是一个**被裁定的数**，不是碰巧的那个 —— 所以显式钉住。

    钉法是**对比**而不是读设置：不传 `lam` 与显式传 `LAM_DEFAULT` 必须逐位相同，
    而传旧缺省必须不同。这样内核与 Python 两侧任何一处的缺省漂了都会被说出来，
    且不依赖某个内部字段的名字。
    """
    assert _moved(base, _run(doc, lam=LAM_DEFAULT)) == 0.0, (
        f"缺省与显式 λ={LAM_DEFAULT} 不是同一个答案 —— 某一侧的缺省漂了")
    assert _moved(base, _run(doc, lam=LAM_OLD)) > 1e-3, (
        f"λ={LAM_OLD}（旧缺省）与缺省给出同一个答案 —— 那说明 `lam` 没被读进去")


@pytest.mark.parametrize("coil", [0, 5, 11])
def test_the_current_split_is_determined_by_the_input(doc, base, coil):
    """★★ε = 1e-13 进去，出来同量级 —— 实测 8.9e-14 / 1.3e-13 / 8.8e-14。

    上界取 1e-10：实测最大的那台是 1.3e-13，留三个量级的余地，好让这条闸问的是
    「分配定不定得下来」，而不是某一位的舍入。2026-09-07 上午同一个量是
    **2–11 %**（λ=1e-3 + 投影梯度），差着十二个量级。
    """
    moved = _moved(base, _run(_nudged(doc, 1e-13, coil)))
    assert moved < 1e-10, (
        f"线圈 {coil} 的半径动 1e-13，设计出来的电流动了 {moved:.3e} —— "
        "分配又不由输入决定了。先看 `start_iterations`（0 = 直接解）与缺省 λ，"
        "再看是不是退回了迭代那一支。")


def test_the_response_is_proportional_to_the_perturbation(doc, base):
    """★★「定下来了」的指纹：位移**随扰动线性缩小**，放大倍数 ~0.5。

    这一条把三种行为分开 —— 成比例（良态线性响应，现在）· 成比例但倍数很大
    （病态放大）· 不成比例（解在平谷里乱跳，2026-09-07 上午的样子）。
    """
    seen = {eps: _moved(base, _run(_nudged(doc, eps))) for eps in (1e-9, 1e-7, 1e-5)}
    gains = {eps: m / eps for eps, m in seen.items()}
    assert max(gains.values()) < 10.0, f"放大倍数不再是 O(1)：{gains}"
    spread = max(gains.values()) / min(gains.values())
    assert spread < 3.0, (
        f"1e-9 到 1e-5 的放大倍数差了 {spread:.1f} 倍（{gains}）—— 位移不再与扰动"
        "成正比，那是另一种行为，要重新量。")


def test_the_solver_says_it_did_not_iterate(doc, base):
    """★求解器的两个事实**说得出来**，而且说的是**走了哪一支**。

    无界（这道闸就是无界：`i_max` 没给）时内核直接解正规方程，所以迭代数是 **0**
    —— 不是「迭代了 0 次就停」，是**没有迭代**。有界那一支照旧投影梯度，那时这个
    数会是正的。这两个事实一度在 `let (x, _) = …` 里被丢掉。
    """
    facts = base["facts"]
    assert facts.get("start_converged") == 1.0, (
        f"起始设计报告未收敛：{facts.get('start_iterations')} 次迭代")
    assert facts.get("start_iterations") == 0.0, (
        f"起始设计报了 {facts.get('start_iterations')} 次迭代 —— 无界时它该走直接解。"
        "非零说明 Cholesky 退回了迭代（数值上非正定），要查响应矩阵。")


def test_the_ridge_that_was_dropped_says_what_it_would_cost(doc, base):
    """★λ=1e-3（旧缺省）在直接解下**残差更小而电流大得多** —— 三头都断言。

    只断言「稳定」会让「把 λ 调回去」看起来是免费的；只断言「残差」会让调大
    看起来是纯亏。实测：残差 0.01187 → 0.00095（好 12 倍），电流
    1.26e6 → 8.24e6 A·turns（大 6.5 倍），稳定度 8.9e-14 → 1.4e-10（差 1600 倍）。
    """
    light = _run(doc, lam=LAM_OLD)
    assert light["psi_rms"] < base["psi_rms"], (
        f"λ 调小而边界残差没变小（{base['psi_rms']:.6g} -> {light['psi_rms']:.6g}）"
        "—— 那不是正则该有的样子")
    assert _norm(light) > 3.0 * _norm(base), (
        f"λ 从 {LAM_DEFAULT} 调到 {LAM_OLD}，电流只涨了 "
        f"{_norm(light) / _norm(base):.1f} 倍 —— 实测约 6.5 倍。裁定 λ 的那笔账"
        "是按这个数算的，它变了就要重算。")
    near = _run(_nudged(doc, 1e-13), lam=LAM_OLD)
    assert _moved(light, near) > 10.0 * _moved(base, _run(_nudged(doc, 1e-13))), (
        "λ 调小而分配没有变得更敏感 —— 那说明这条 L 曲线塌了，要重新量")
