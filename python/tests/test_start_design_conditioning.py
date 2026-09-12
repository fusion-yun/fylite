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

★★顺序是先定 λ，再换解法。下表是直接解法下的 L 曲线（EAST 公共卡，ε=1e-13，
24 个边界点，无控制行、无 null 行）：

=======  ==========  ==========  ==============
`lam`    `‖chan‖`    `psi_rms`   `Δchan/chan`
=======  ==========  ==========  ==============
1e-3     8.24e6      0.00095     1.4e-10
3e-2     1.61e6      0.00278     3.3e-12
1e-1     1.43e6      0.00428     1.8e-13  ← 缺省
3e-1     1.26e6      0.01187     8.9e-14
1.0      6.59e5      0.05712     6.0e-14
=======  ==========  ==========  ==============

★★**这张表定不了缺省，它只有一头。** 它说的是「λ 越大越可复现」，照它选就该选
1.0。缺省 2026-09-07 先按它定在 3e-1，**2026-09-08 用真机数据量过之后改到 1e-1**
—— 另一头在那里：λ≥2e-1 时退火一趟都不接受，交出来的等离子体 κ 比要的低 18%、
磁轴离实测轴 102 mm。那道闸是 `fylite_kernel` 仓
`tests/test_start_against_the_machine.py`（EAST #137985 实测放电），**它才是定
缺省的那一道**；本闸只管纯数值这一面。两道都要过。

选中的这一行在数值这一面买到的是：1e-13 的扰动只动 1.8e-13，位移与扰动同量级 ——
良态线性响应该有的样子，不是「病态放大」，更不是原先那种「在平谷里乱跳」
（当时 1e-13 到 1e-7 的扰动一律动 10 % 上下，**不随扰动缩小**）。

★这道闸**变红是好消息的一种**：若某天在更小的 λ 上也稳得住，说明解法或标度改了。
那时改的是下面的数，不是把界放宽 —— 并把新的三列写下来，且**同时**去看那道真机闸。
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
#: ★由来见上：数值这一面给上界，真机那一面给下界，1e-1 是两头都在界内的那个。
#: ★这里不传 `lam`，走缺省 —— 这道闸查的就是**缺省**定在哪。
LAM_DEFAULT = 1e-1
#: 最初的缺省，留作对照行（下面最后一条量它的代价）。真机上它要的最大通道
#: 电流是 EAST 实测最大值的 2.04 倍 —— 那一头由那道真机闸挡。
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
    """★★ε = 1e-13 进去，出来同量级 —— 实测 1.8e-13 / 1.8e-13 / 2.2e-13。

    上界取 1e-10：实测最大的那台是 2.2e-13，留将近三个量级的余地，好让这条闸问的
    是「分配定不定得下来」，而不是某一位的舍入。2026-09-07 上午同一个量是
    **2–11 %**（λ=1e-3 + 投影梯度），差着十二个量级。
    """
    moved = _moved(base, _run(_nudged(doc, 1e-13, coil)))
    assert moved < 1e-10, (
        f"线圈 {coil} 的半径动 1e-13，设计出来的电流动了 {moved:.3e} —— "
        "分配又不由输入决定了。先看 `start_iterations`（0 = 直接解）与缺省 λ，"
        "再看是不是退回了迭代那一支。")


def test_the_response_is_proportional_to_the_perturbation(doc, base):
    """★★「定下来了」的指纹：位移**随扰动线性缩小**，放大倍数 0.372（三个 ε 上
    **同一个数**，到三位有效数字）。

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
    看起来是纯亏。实测：残差 0.00428 → 0.00095（好 4.5 倍），电流
    1.43e6 → 8.24e6 A·turns（大 5.8 倍），稳定度 1.8e-13 → 1.4e-10（差 770 倍）。
    ★而那 5.8 倍的电流，真机那一道闸量出来是机器实测最大值的 2.04 倍 —— 交不出来。
    """
    light = _run(doc, lam=LAM_OLD)
    assert light["psi_rms"] < base["psi_rms"], (
        f"λ 调小而边界残差没变小（{base['psi_rms']:.6g} -> {light['psi_rms']:.6g}）"
        "—— 那不是正则该有的样子")
    assert _norm(light) > 3.0 * _norm(base), (
        f"λ 从 {LAM_DEFAULT} 调到 {LAM_OLD}，电流只涨了 "
        f"{_norm(light) / _norm(base):.1f} 倍 —— 实测约 5.8 倍。裁定 λ 的那笔账"
        "是按这个数算的，它变了就要重算。")
    near = _run(_nudged(doc, 1e-13), lam=LAM_OLD)
    assert _moved(light, near) > 10.0 * _moved(base, _run(_nudged(doc, 1e-13))), (
        "λ 调小而分配没有变得更敏感 —— 那说明这条 L 曲线塌了，要重新量")


#: ★★F-16（2026-09-12）：上面几条**实测**落点稳不稳；这三条把那件事的**来由**
#: 报出来 —— 内核新增的事实 `start_cond`，即闭式解那条正规方程
#: `AᵀA + λ²I` 的 κ₂（`pulse.rs::start_currents`，λ 的增广行已在 `aa` 里，
#: 所以 `AᵀA` **就是**那条方程的矩阵）。它是一个**先验界**：输入的相对扰动最多被
#: 放大 √κ 倍（最小二乘的解算子的条件数是 κ₂(A)=√κ₂(AᵀA)），于是
#: 「换一份只差最后几位的装置文档，设计电流动 2.8 倍」不必每次事后实测复现。
#: 缺省 λ=1e-1 上的实测（EAST 公共卡，24 个边界点，无控制行）：
#:
#: =======  ============  ===========  ==========
#: `lam`    `start_cond`  `√cond`      `cond·λ²`
#: =======  ============  ===========  ==========
#: 1e-3     2.5562e8      1.599e4      2.556e2
#: 1e-2     2.7410e6      1.656e3      2.741e2
#: 1e-1     2.7431e4      1.656e2      2.743e2  ← 缺省
#: 1.0      2.7530e2      1.659e1      2.753e2
#: =======  ============  ===========  ==========
#:
#: `cond·λ²` 三个量级上是**同一个数**（275.3 / 255.6 = 1.077）—— 这说的是
#: λ² ≫ σ_min²：小头是**岭**定的，不是数据定的，所以这个响应矩阵在 1e-2…1e-1
#: 的尺度上已经实质降秩。**推论**（可测、已测）：κ ∝ λ⁻²，每降一个量级 κ 涨 100 倍。
COND_LAM2 = 274.3


def test_the_start_reports_how_reproducible_its_landing_is(doc, base):
    """★★落点的可复现度**说得出来**：`start_cond` 是有限正数，且在实测带内。

    这条钉的是**事实在**、且它的量级是量过的那个。带取 ±15 %：三台机器上
    实测 2.41e4（ITER）· 2.74e4（EAST）· 3.99e4（best），机器之间差不到两倍，
    而 λ 动一个量级就差 100 倍 —— 所以这条带分得开「换了机器」与「岭漂了」。
    """
    cond = base["facts"].get("start_cond")
    assert cond is not None, "内核没报 `start_cond` —— 事实丢了，见 case.rs::start_facts"
    assert np.isfinite(cond) and cond > 0.0, f"`start_cond` 不是有限正数：{cond}"
    assert abs(cond / (COND_LAM2 / LAM_DEFAULT**2) - 1.0) < 0.15, (
        f"EAST 缺省 λ 上的 κ₂ 是 {cond:.4e}，实测 {COND_LAM2 / LAM_DEFAULT**2:.4e} —— "
        "要么装置文档换了，要么响应矩阵的标度动了。先看 `psi_rms` 有没有跟着动。")


def test_the_conditioning_is_set_by_the_ridge_not_by_the_data(doc):
    """★★κ₂·λ² 在三个量级上是同一个数 —— **岭定小头**，即 λ² ≫ σ_min²。

    这不是拟合出来的，是 κ₂ = (σ_max²+λ²)/(σ_min²+λ²) 在 σ_min ≪ λ 下的极限。
    实测 255.6…275.3（比值 1.077）。这条一旦变红，说的是响应矩阵**不再**在这个
    尺度上降秩 —— 那时 λ 的裁定要重算，因为「λ 越大越可复现」不再按 λ⁻² 走。
    """
    seen = {lam: _run(doc, lam=lam)["facts"]["start_cond"] for lam in (1e-2, 1e-1, 1.0)}
    scaled = {lam: c * lam * lam for lam, c in seen.items()}
    spread = max(scaled.values()) / min(scaled.values())
    assert spread < 1.15, (
        f"κ₂·λ² 不再是常数（{ {k: round(v, 1) for k, v in scaled.items()} }，"
        f"比值 {spread:.3f}）—— 小头不再由岭定，λ 的那笔账要重算")
    assert abs(max(scaled.values()) / COND_LAM2 - 1.0) < 0.15, (
        f"σ_max² 实测 {max(scaled.values()):.1f}，此前 {COND_LAM2} —— 标度动了")


@pytest.mark.parametrize("lam", [1e-1, 1e-2])
def test_the_measured_displacement_stays_under_the_prior_bound(doc, lam):
    """★★实测放大倍数 ≤ √κ₂ —— 报出来的那个数**真的是个界**。

    这条把「报了一个数」与「报了一个有用的数」分开。实测（ε=1e-9）：
    λ=1e-1 放大 0.372，界 165.6；λ=1e-2 放大 0.681，界 1656。界松了两到三个
    量级（最小二乘的界按最坏方向给，扰动落在最坏方向上才取到），但**方向对**：
    λ 小一个量级，实测放大与界**同时**变大。★变红有两种读法 —— 实测越界（那是
    界算错了，查 `normal_cond` 的装配）或单调性反了（那是响应矩阵换了性质）。
    """
    r = _run(doc, lam=lam)
    moved = _moved(r, _run(_nudged(doc, 1e-9), lam=lam)) / 1e-9
    bound = float(np.sqrt(r["facts"]["start_cond"]))
    assert moved <= bound, (
        f"λ={lam:g}：实测放大 {moved:.4g} 超过 √κ₂ = {bound:.4g} —— "
        "那不是界，查 `pulse.rs` 里 `normal_cond` 是不是用了同一个 `aa`")
    assert moved > 0.0, f"λ={lam:g}：ε=1e-9 进去，电流逐位不动 —— 扰动没进到求解器"
