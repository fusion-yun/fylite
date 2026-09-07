"""起始设计**由它的输入决定** —— 一次实测，钉在这里。

★★由来。2026-09-07 换 EAST 的装置文档（同一台机器，两份文档，数只差最后几位）时，
`validate-worker-summary` 的 `start.chan` 动了 **2.8 倍**，而它要满足的目标边界
**逐位相同**、拟合残差 `psiRms` 还略好了一点。那不是「换了一台机器」。

★★查清的原因（同日，第三次假设才对）：

* **不是**病态到没法解 —— 岭是按响应自己的列范数定尺度的（`pulse.rs::start_currents`
  里 `lam = sp.lambda * g_scale`），augment 之后的问题正定；
* **不是**迭代跑满预算 —— 求解器报的迭代数是 499 / 4000，按它自己的判据收敛了；
* **是**：没有上下界时，这个问题是一个**无约束的岭最小二乘，有闭式解**，而内核
  当时无论有没有界都走 `bounded_lstsq`（投影 Barzilai-Borwein 梯度 + 非单调线搜）。
  一阶方法停在「投影梯度 ≤ 1e-12·pg0」上，而在一条平谷里，**梯度小不蕴含位置定**。
  实测：同一份输入两次跑逐位相同，但把任意一个输入动 1e-13（三个不同线圈的半径，
  或 `ip` 本身），迭代次数从 499 变成 295 / 169 / 574 / 230 —— **整条轨迹换了**，
  停在谷里的另一点。

★★修法与代价（`pulse.rs::start_currents`）：无界时直接解正规方程
（`aa` 已经把 λ 作为附加行带上，所以 `AᵀA` 里已含 λ²），一次 Cholesky 给出唯一极小点；
有界那一支照旧迭代（带箱约束的最小二乘没有闭式解）。实测**两头都变好**：

=========================  ==============  ==============
量                          迭代那一版       直接解
=========================  ==============  ==============
`Δchan/chan` @ ε=1e-13      1.1e-1          **1.4e-10**
`psi_rms`                   0.0016778       **0.00094762**
=========================  ==============  ==============

残差小了 **43 %** —— 也就是说，迭代那一版不只是「停在谷里的另一点」，它**根本没走到
极小点**。所以这不是调容差，是修了一个求解器缺陷。

★这道闸**变红是坏消息**：它说起始设计又对自己的输入不连续了。那时先看
`start_iterations` / `start_converged` 两个事实（同日补上，此前求解器的收敛旗在
`let (x, _) = …` 里被丢掉了），再看是不是又走回了迭代那一支。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "dist" / "facts" / "device" / "east.jsonld"

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


def _run(doc: dict, lam: float = 1e-3, ip: float = 393459.5) -> dict:
    """起始设计一次，连同内核报回来的求解器事实。"""
    import fylite.scenario.design as design
    settings = design._start_settings(_target(doc), ip, n_points=24,
                                      xpoint=None, x_weight=0.0)
    settings.update(stage="start", n_ring=4.0, peaking=1.0, lam=float(lam))
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


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(DOC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base(doc) -> dict:
    return _run(doc)


def test_the_same_input_gives_the_same_answer(doc, base):
    """★先钉最起码的一条：确定性。它一旦不成立，下面几条都不必读。"""
    assert _moved(base, _run(doc)) == 0.0


@pytest.mark.parametrize("coil", [0, 5, 11])
def test_a_perturbation_at_the_last_bit_stays_at_the_last_bit(doc, base, coil):
    """ε = 1e-13 进去，出来还是 1e-10 量级 —— 迭代那一版这里是 2–11 %。

    ★界取 1e-6：实测 1.4e-10 ~ 5.1e-10，留四个数量级的余地，好让这条闸问的是
    「答案由输入决定吗」，而不是「今天恰好是 1.4e-10 还是 1.5e-10」。
    """
    moved = _moved(base, _run(_nudged(doc, 1e-13, coil)))
    assert moved < 1e-6, (
        f"线圈 {coil} 的半径动 1e-13，设计出来的电流动了 {moved:.3e} —— "
        "起始设计又对自己的输入不连续了。先看 start_iterations / start_converged，"
        "再看是不是走回了投影梯度那一支（无界时该直接解）。")


def test_the_answer_scales_with_the_perturbation_instead_of_jumping(doc, base):
    """★★这一条查的是「不跳」：迭代那一版从 1e-13 到 1e-7 一律 10 % 上下——
    响应**不随扰动缩小**，那正是「解在谷里乱跳」的指纹。现在它是线性的。
    """
    seen = {eps: _moved(base, _run(_nudged(doc, eps))) for eps in (1e-9, 1e-6)}
    gain = {eps: d / eps for eps, d in seen.items()}
    assert max(gain.values()) < 10.0, f"放大倍数 {gain} —— 实测约 0.3"
    assert seen[1e-6] > seen[1e-9], (
        f"扰动大了一千倍而位移没跟着涨（{seen}）—— 又是「跳」而不是「随」。")


def test_the_solver_says_whether_it_converged(doc, base):
    """★求解器的收敛旗**说得出来**。它一度在 `let (x, _) = …` 里被丢掉，于是
    「跑满预算停下」与「收敛了停下」在记录上一模一样。
    """
    facts = base["facts"]
    assert facts.get("start_converged") == 1.0, (
        f"起始设计报告未收敛：{facts.get('start_iterations')} 次迭代")
    #: 直接解没有轨迹，迭代数报 0 —— 那正是「这一支不迭代」的记号
    assert facts.get("start_iterations") == 0.0, (
        f"无界的起始设计走了 {facts.get('start_iterations')} 次迭代 —— "
        "它应当直接解（`aa` 已含 λ 行，正规方程正定）。")


def test_a_heavier_ridge_costs_boundary_accuracy(doc, base):
    """★岭调大仍然要付代价 —— 记在这里，好让「把 lam 调大」不显得免费。

    ★这一条与上面几条无关：解法修好之后 `lam` 该取多少仍是一个工程判断，
    这道闸不替它做主，只把代价量出来。
    """
    heavy = _run(doc, lam=3e-1)
    cost = heavy["psi_rms"] / base["psi_rms"]
    assert cost > 3.0, (
        f"λ 从 1e-3 提到 0.3，边界残差只差了 {cost:.1f} 倍 —— 实测约 12 倍。"
        "代价变小是好事，但要先弄清为什么。")
