---
title: 物理校验 (Physics checks — what a product is judged against)
---

# 物理校验

**这一章讲的是第三本册子。** 前两本各回答一个问题：算例语料（`cases/`）说
「这套代码跑什么」，公开 V&V 登记册（`benchmark/`）说「对着外部答案量到多少」。
本章讲的这一本说：**跑出来的东西自洽吗**——温度是不是正的、ψ 的两端对不对得上
它自己的全局量、二维平衡满不满足它自己声称在解的那道方程、这一炮落没落在算例
声明的窗口里。

三本谁也替不了谁：一次跑得又快又收敛的解可以是负温度的；一条与另一个码吻合到
1 % 的曲线可以违反 Grad–Shafranov（两处错互相抵消）。

| 册子 | 问的是 | 参考是什么 | 在哪 |
| :--- | :--- | :--- | :--- |
| 算例语料 | 这套代码跑什么 | —— | `cases/` |
| 公开 V&V 登记册 | 对着外部答案量到多少 | 另一个码、解析解、实验 | `benchmark/` |
| **物理校验册** | **这份产出自洽吗** | **物理定律与文档自身的定义** | `benchmark/physics/` |

## 三类判据，读法不同

| 类 | 参考是什么 | 不满足意味着 |
| :--- | :--- | :--- |
| **定律** `law` | 物理定律本身 | 产出不是一个物理态——这是缺陷 |
| **定义** `definition` | 文档自己的定义 | 文档内部不自洽，或口径与册子声明的不同 |
| **期望** `expectation` | 算例声明的窗口 | 这一炮没落在声明的窗口里，不一定是缺陷 |

判决是**四态**——`pass` / `conditional` / `fail` / `unevaluated`——与
`fylite.engine.provenance` 的验收同一套（比登记册的三态多一个「有条件」：量到的
落在 1 到 3 倍容差之间）。**读不到就是 `unevaluated`，并点名缺了哪一个量**；
统计表把它单列，永远不并进「通过」。一批全「未评估」的结果必须一眼看得出来，
否则它会被读成「零个失败」。

## 册子上现有的检查

每一条都声明**读哪些量**（经内核自己的槽表 `fylite.fyo` / `_fyo_interface.TABLES`，
不在校验册里手写 fyo 路径）、**判据的式子**、**默认容差**与**容差的来路**：

| 检查 | 类 | 量的是什么 | 判据 | 默认容差 | 来路 |
| :--- | :--- | :--- | :--- | ---: | :--- |
| `finite` | law | 产出的每个数都是有限的 | `∀x ∈ datasets: isfinite(x)` | `0` | machine_precision |
| `positive-temperature` | law | 绝对温度为正 | `min(T_e, T_i) > 0` | `0` | machine_precision |
| `positive-density` | law | 粒子数密度为正 | `min(n_e, n_i) > 0` | `0` | machine_precision |
| `grad-shafranov` | law | 二维平衡满足 Grad–Shafranov 方程 | `Δ*ψ = −μ₀R²·dp/dψ − f·df/dψ，Δ* = ∂_RR − (1/R)∂_R + ∂_ZZ` | `0.02` | measured_band |
| `grid-monotone` | definition | 网格与时间轴单调，归一化网格在 [0, 1] | `diff(x) > 0；0 ≤ ρ_norm, ψ_norm ≤ 1` | `0` | machine_precision |
| `psi-endpoints` | definition | 一维 ψ 的两端就是 ψ_axis 与 ψ_boundary | `|ψ₁ᴰ[0] − ψ_axis| / |ψ_bnd − ψ_axis| ≤ tol，另一端同` | `1e-06` | machine_precision |
| `volume-monotone` | definition | 体积随 ρ 单调增，V′ 在轴外为正 | `diff(V) ≥ 0；V′[1:] > 0` | `0` | machine_precision |
| `boundary-closed` | definition | 最外闭合磁面闭合，且在限制器内 | `|X[0] − X[-1]| / median|ΔX| ≤ tol（tol = 1.5 个采样步）；越出限制器的深度 ≤ limiter_tolerance × a` | `1.5` | measured_band |
| `pressure-consistency` | definition | 平衡压强对得上剖面的动理压强 | `max|p_eq − e(n_e T_e + n_i T_i)| / max|p| ≤ tol` | `0.05` | measured_band |
| `energy-balance` | definition | 能量约束时间的定义式逐时刻成立 | `|W_th/τ_E + dW_th/dt − P_heat| / |P_heat| ≤ tol（中位数）` | `0.05` | measured_band |
| `greenwald-definition` | definition | 记下的 Greenwald 分数对得上定义 | `f_G = n̄_e / n_G，n_G[m⁻³] = 10²⁰·I_p[MA]/(π a²[m²])` | `0.15` | measured_band |
| `beta-normalized-definition` | definition | 记下的 β_N 对得上定义 | `β_N = 100·β_t·a·B₀/I_p[MA]，β_t = 2μ₀⟨p⟩/B₀²` | `0.15` | measured_band |
| `q-order` | expectation | |q95| > |q_axis|（单调 q 的常规位形） | `|q95| > |q_axis| 逐时刻` | 算例声明 | reference_stated |
| `steady-state` | expectation | 准稳态窗口：steady_change 在声明的界内 | `max|steady_change| ≤ 算例声明的 tolerance` | 算例声明 | reference_stated |
| `declared-bounds` | expectation | 算例声明的运行界（β_N、f_G、q95…） | `min/max(quantity) 落在算例声明的 [min, max] 内` | 算例声明 | reference_stated |

★**每条检查都写明它假设了什么**，因为结论只在假设成立时有意义。两个例子：

* `pressure-consistency` 假设平衡压强是**热压强**、单一等效离子、无快离子压强。
  带快粒子的算例会给出一个正的偏差——那是口径差别，不是缺陷，所以它的容差来路是
  `measured_band` 而不是 `machine_precision`。
* `grad-shafranov` 假设 ψ 是**每弧度**的、且 $\Delta^*\psi = -\mu_0 R^2 p' - ff'$。
  另一套 COCOS 写出来的文档，残差会落在另一个符号支上——那时给的是一条**注记**
  （「先核对 COCOS」），不是一个假的「不满足定律」。

## Grad–Shafranov 那一条怎么量的

平衡产出唯一一条定律级检查，也是最值得说清楚的一条。它量的不是「与谁吻合」，
而是这份 $\psi$ 是不是它自己那对源函数的解：

$$
\Delta^*\psi \equiv \pdv[2]{\psi}{R} - \frac{1}{R}\pdv{\psi}{R} + \pdv[2]{\psi}{Z}
= -\mu_0 R^2 \dv{p}{\psi} - f\dv{f}{\psi}
$$

算法：二阶中心差分算 $\Delta^*\psi$；源函数 $p'(\psi)$、$ff'(\psi)$ 按 $\psi(R,Z)$
在一维 ψ 网格上插值；只在**边界外形内**且离网格边一格以上的点上取；残差按
$\lVert\Delta^*\psi\rVert$ 与 $\lVert\mathrm{RHS}\rVert$ 的均方根归一。

判据本身是**可证的**，闸子因此不是录音：`python/tests/test_physics_checks.py` 用一族
精确解构造平衡——

$$
\psi = aR^4 + bR^2Z^2 + cZ^2 + dR^2 + e
\;\Longrightarrow\;
\Delta^*\psi = (8a + 2b)R^2 + 2c ,
$$

取 $p'$、$ff'$ 为常数并令 $8a+2b = -\mu_0 p'$、$2c = -ff'$ 即逐项配平。精确解的残差
只剩差分截断误差（$\mathcal{O}(h^2)$，实测 $1.5\times10^{-4}$ 量级），动过手脚的
（$\psi$ 上加 2 % 的正弦扰动）落在 $10^{-2}$ 以上——**成对判**，只判前者的闸子
会让一条永远返回 `pass` 的检查活下来。

## 一次校验批走的三步

```{mermaid}
flowchart LR
  A["算例<br/>fyo:ScenarioSpecification<br/>cases/*.jsonld"] --> B["产出<br/>spo:ComputationRecord<br/>（现跑 / 已记录 / 盘上的文件）"]
  B --> C["判决<br/>fyo:ComparisonRecord<br/>benchmark/physics/*.jsonld"]
  C --> D["报告与统计<br/>*.md · summary.jsonld · BENCHMARK.md"]
```

**产出从哪来，只有三条路，都不许猜**：

1. 算例声明的**产出文件**（`has_output`：一份 g-file 就是一份平衡产出）；
2. **已经跑出来的记录**（`--from`，`fylite-case run` 写的 `record.jsonld`）；
3. 经数据层的 JSON 门**现跑**（要 `libfylite_kernel.so`）。

内核不在场时第三条**按名拒绝**，那些条目记成「未评估」并写明缺的是哪一件——
不拿任何别的算法顶上。所以公开检出里这一册大半是「未评估」：那是**检出的事实**，
不是判据的沉默。

## 怎么用

```bash
fylite cases --physics                            # 列出预设算例与它们的判据
fylite cases --physics --check                    # 结构检查（与 pytest 闸子同一函数）
fylite cases --physics --plan zerod-iter-15ma     # 这一条要读哪些量、判哪几条
fylite cases --physics --run equilibrium-gfile    # 跑一条，打印报告

python tools/benchmark-run.py                     # 整批，统计表打到屏幕
python tools/benchmark-run.py --write             # 并写进 benchmark/physics/ 与仓根 BENCHMARK.md
python tools/benchmark-run.py --from records/     # 判已经跑出来的记录（不需要内核）
```

在 Python 里，判据册与批次都是普通函数：

```python
from fylite.scenario import physics, suite

rows = physics.evaluate({"equilibrium": eq_doc, "summary": sum_doc})   # 逐条结论
physics.summarize(rows)                                               # {"overall": ..., "counts": {...}}
suite.run_entry(suite.entry("zerod-iter-15ma"))                       # 取产出 + 判
```

## 添一条算例

在 `benchmark/physics/suite.jsonld` 的 `has_part` 里加一条：点名跑哪个算例
（`scenario` + `concretized_as`）或判哪份产出（`has_output`），再把这个场景**多出来**的
判据写进 `criteria`——定律与定义一律跑，不必写。

```jsonc
{
  "id": "physics/zerod-iter-15ma",
  "title": {"zh": "…"},
  "scenario": "cases/zerod-iter-15ma",
  "concretized_as": [{"type": "spo:Concretization", "storage_uri": "cases/zerod-iter-15ma.jsonld", …}],
  "criteria": [
    {"type": "fyo:AcceptanceCriterion", "quantity_label": "energy-balance",
     "tolerance": {"type": "spo:QuantityValue", "numeric_value": 0.02},
     "tolerance_basis": "measured_band"},
    {"type": "fyo:AcceptanceCriterion", "quantity_label": "declared-bounds",
     "tolerance_basis": "reference_stated",
     "bounds": [{"quantity": "SUMMARY/greenwald", "maximum": 1.2}]}
  ]
}
```

结构由 `fylite.scenario.suite.problems` 判：算例文件在不在检出里、判据在不在册子上、
声明的界点的是不是内核产得出的量。`fylite cases --physics --check` 与
`python/tests/test_physics_suite.py` 读的是**同一个函数**。

## 添一条检查

在 `python/fylite/scenario/physics.py` 里加一个 `Check`：声明 `kind`（定律 / 定义 /
期望）、`title`、`formula`、`reads`（`(表, 槽)` 对，槽名必须在内核的槽表里）、默认
容差与容差来路，以及 `assumes`——**它假设了什么，逐条写出来**。判据函数收一个
`Reader` 和一份参数，返回一个 `Result`；读不到的量记进 `missing` 并给
`unevaluated`，绝不拿缺省值顶上。

闸子要求**成对判**：满足的构造要 `pass`，动过手脚的要不 `pass`。
