"""起始设计的**电流分配不由输入决定** —— 一次实测，和一次试着修它的记录。

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
* **是**解法与目标函数**合起来**：无界时这是一个有闭式解的岭最小二乘，而内核走的是
  投影 Barzilai-Borwein 梯度。一阶法停在「投影梯度 ≤ 1e-12·pg0」上，而在一条平谷里
  **梯度小不蕴含位置定**。同一份输入两次跑逐位相同；把任意一个输入动 1e-13，
  迭代数从 499 变成 295 / 169 / 574 / 230 —— **整条轨迹换了**。

★★**试过直接解，又改回去了**，因为它把一件事换成了另一件事：

=========================  ==============  ==============
量（EAST，λ=1e-3，无控制行） 迭代（今天）     直接解（试过）
=========================  ==============  ==============
`Δchan/chan` @ ε=1e-13      1.1e-1          1.4e-10
`psi_rms`                   0.0016778       0.00094762
`‖chan‖` [A·turns]          2.18e6          **8.24e6**
=========================  ==============  ==============

精确极小点把边界拟合得更紧，代价是**四倍的电流**。问题不在解法，在目标：λ=1e-3
的岭太轻，那个目标本来就偏好更大的电流；而迭代从 0 出发提前停下，**等于额外一层
正则**（early stopping），一直在替这个太轻的岭兜底。撤掉它，数学上更对，工程上是
另一台机器的启动电流。

★★**所以决定点是 λ（或一个显式的电流范数目标），不是解法。** 岭扫描（同一个
ε = 1e-13，迭代解法下）：

=======  ==========  ==========  ==============
`lam`    `‖chan‖`    `psi_rms`   `Δchan/chan`
=======  ==========  ==========  ==============
1e-3     2.18e6      0.00168     1.1e-1  ← 缺省
3e-2     1.59e6      0.00287     7.9e-3
1e-1     1.43e6      0.00429     5.9e-4
3e-1     1.26e6      0.01187     1.0e-8
1.0      6.59e5      0.05712     4.8e-9
=======  ==========  ==========  ==============

λ 定下来之后再换直接解，才是纯粹的改进。这道闸不替那个判断做主，只把两侧的数量出来。

★这道闸**变红是好消息的一种**：若某天分配也稳了，说明 λ 或解法改了。那时删掉相应的
行，并把改了什么写下来 —— 不要把界放宽了事。
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
def test_a_perturbation_at_the_last_bit_moves_the_current_split(doc, base, coil):
    """ε = 1e-13 进去，出来是百分之几 —— 实测 2.4 % / 7.1 % / 11.1 %。

    ★下界取 1e-2：实测最小的那台是 2.4 %，留一点余地，好让这条闸问的是
    「分配定不定得下来」，而不是「今天恰好是 11.1 % 还是 11.2 %」。
    """
    moved = _moved(base, _run(_nudged(doc, 1e-13, coil)))
    assert moved > 1e-2, (
        f"线圈 {coil} 的半径动 1e-13，设计出来的电流只动了 {moved:.3e} —— "
        "比实测（2–11 %）稳得多。λ 或解法大概是改了：删掉这道闸，"
        "并把改了什么、电流范数变成多少写下来。")


def test_the_field_it_makes_is_determined_even_when_the_split_is_not(doc, base):
    """★这一条才是要点：**场是定的**。

    同一个 ε 下拟合残差只在 0.0016–0.0018 之间动 —— 两组差着一成的电流把目标边界
    拟合得一样好。所以「分配变了」不等于「答案错了」，而**把分配逐位钉进夹具**
    等于钉住一个没有被问题定下来的量（`validate-worker-summary` 因此按容差比它）。
    """
    near = _run(_nudged(doc, 1e-13))
    rel = abs(near["psi_rms"] - base["psi_rms"]) / base["psi_rms"]
    assert rel < 0.2, (
        f"拟合残差动了 {rel:.1%}（{base['psi_rms']:.6g} -> {near['psi_rms']:.6g}）"
        "—— 那就不只是分配在动了，是这一解本身变了，要查。")


def test_the_response_does_not_shrink_with_the_perturbation(doc, base):
    """★★「跳」的指纹：1e-13 到 1e-7 的扰动，位移一律 10 % 上下 —— 不随扰动缩小。

    这一条把「病态放大」与「解在平谷里乱跳」分开。前者的位移与扰动成正比，
    后者不成比例；实测是后者。
    """
    seen = {eps: _moved(base, _run(_nudged(doc, eps))) for eps in (1e-13, 1e-9, 1e-7)}
    assert min(seen.values()) > 1e-2, f"位移不再是一个量级：{seen}"
    spread = max(seen.values()) / min(seen.values())
    assert spread < 10.0, (
        f"1e-13 到 1e-7 的位移差了 {spread:.1f} 倍（{seen}）—— 看起来变成了"
        "随扰动成比例的放大，那是另一种行为，要重新量。")


def test_the_solver_says_whether_it_converged(doc, base):
    """★求解器的收敛旗**说得出来**。它一度在 `let (x, _) = …` 里被丢掉，于是
    「跑满预算停下」与「收敛了停下」在记录上一模一样。
    """
    facts = base["facts"]
    assert facts.get("start_converged") == 1.0, (
        f"起始设计报告未收敛：{facts.get('start_iterations')} 次迭代")
    #: ★迭代数**要在**，而且远小于预算（4000）：它是上面第二条假设被否掉的证据，
    #: 也是下一个读到这里的人分辨「跑满了」与「停在谷里」的唯一手段。
    it = facts.get("start_iterations")
    assert 0 < it < 4000, f"起始设计的迭代数是 {it} —— 0 说明它不迭代了，4000 说明它跑满了"


def test_a_heavier_ridge_buys_reproducibility_and_says_what_it_costs(doc, base):
    """λ = 0.3 上分配稳到 1e-8，代价是边界残差差约 7 倍、电流小 42 %。

    ★三头都断言：**稳住了**、**代价多少**、**电流往哪边走**。只断言第一条，
    会让「把 lam 调大」看起来是免费的。
    """
    heavy = _run(doc, lam=3e-1)
    heavy_near = _run(_nudged(doc, 1e-13), lam=3e-1)
    assert _moved(heavy, heavy_near) < 1e-6, (
        f"λ=0.3 上分配仍动了 {_moved(heavy, heavy_near):.3e} —— 实测 1e-8。")
    cost = heavy["psi_rms"] / base["psi_rms"]
    assert cost > 3.0, (
        f"λ 从 1e-3 提到 0.3，边界残差只差了 {cost:.1f} 倍 —— 实测约 7 倍。")
    n0 = float(np.linalg.norm(np.asarray(base["aturns"], float)))
    n1 = float(np.linalg.norm(np.asarray(heavy["aturns"], float)))
    assert n1 < n0, f"岭调大而电流没变小（{n0:.3g} -> {n1:.3g}）—— 那不是正则该有的样子"
