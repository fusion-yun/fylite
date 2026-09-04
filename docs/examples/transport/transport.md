---
title: 典型算例 · 1.5-D 芯部输运 (Worked Example · 1.5-D Core Transport)
---

# 1.5-D 芯部输运：固定几何、单通道、定态

**问的是**：给定一套度规（`V′`、`⟨|∇ρ|²⟩`）、一个源分布与一条 χ 闭包，定态剖面长什么样。
**不问**储能与约束时间——这一档没有热容项，报不出 `W_th` / `τ_E`，那是[含时演化](../evolve/evolve.md)那一栏的事。

算例 `transport-iter-15ma`：ITER 15 MA 的剖面，不绑装置（度规解析给出）。

## 跑它

```python
from fylite.engine import cases
cases.run("transport-iter-15ma")
```

```text
transport-iter-15ma  bar=transport -> fylite_transport
  fields: 13 mapped, 6 sub-capability, 0 shared, 0 ui
  acceptance: pass  converged=pass, settled=pass
```

结果（`result.json` 的摘要行）：

| 量 | 形状 | 范围 |
| :--- | :--- | :--- |
| `rho` 径向坐标 | 41 | 0 … 2 |
| `y` 解出的剖面 | 41 | 3 … 17.7765（均值 10.7194） |
| `residual` | 标量 | 9.99e-17 |
| `converged` / `settled` / `steps` | | `True` / `True` / 1 |

★**两条判据判的不是一件事**：`converged` 说这一步的非线性迭代收住了，`settled` 说再走
一步剖面不再变（定态）。一个刚性闭包可以收敛到一个仍在漂的状态——那时前者绿、后者红。

## Python 入口

```python
from fylite import scenario as S

t = S.model.transport(power=4.0)
t["converged"], t["residual"]          # True, 1.772e-16
t["y"][0], t["y"][-1]                  # 0.626454（轴）, 0.3（边界值）
sorted(t)
# ['converged', 'history', 'inner_iterations', 'provenance', 'residual',
#  'rho', 'settled', 'source', 'steps', 'vprime', 'y']
```

常用的几个旋钮，以及它们各自换的是什么问题：

| 参数 | 缺省 | 换的是 |
| :--- | ---: | :--- |
| `closure` | `"constant"` | 闭包：`constant` 常数 χ · `stiff` 刚性（临界梯度）· `neoclassical` 新经典 |
| `chi0` | 1.0 | 常数档的 χ [m²/s] |
| `power` / `width` | 4.0 / 0.35 | 源的总量与高斯宽度 |
| `edge_value` | 0.3 | 边界值（Dirichlet） |
| `steps` / `dt` | 1 / ∞ | 单步定态 → 多步含时；`dt=inf` 就是「直接解定态」 |
| `d_pc` | 0.0 | 箍缩项 |
| `chi_given` / `neo` | None | 外部给定的 χ 剖面 / 新经典系数（接自 NEO 端口） |

## 换一条闭包

```python
a = S.model.transport(closure="constant", chi0=1.0)
b = S.model.transport(closure="stiff",    p1=0.25, p2=1.75)
c = S.model.transport(closure="neoclassical")
```

★**三条不是同一个模型的三种精度**，是三个模型。刚性档的剖面会被临界梯度钉住，改源
的总量几乎不改梯度、只改通量——这正是刚性输运的定义性行为，不是数值问题。

## 与湍流闭包接线

χ 也可以来自回旋朗道流体端口（TGLF）而不是一条解析闭包：

```python
d = S.model.tglf(...)                      # 局域 TGLF：给定面上的通量与增长率谱
t = S.model.transport(chi_given=chi_from_flux)   # 把它换算出的 χ 喂回来
```

★**这一步的口径最容易咬人**：TGLF 按 GACODE 的归一给答案（`B_unit`、Miller `r/a`），
而输运方程按 ρ 标签走。`scenario.model.mapping` 是**唯一**做这一层归一的地方——不要在
调用处自己换算，那是移植缺陷最常见的落点（见公开登记册的 V-06 / V-07 记录）。

## 报告

```python
from fylite.engine import casereport, cases
casereport.render(cases.run("transport-iter-15ma"), out="out/transport")
```

剖面对 `rho_tor`，源与度规各自成图。★`y` 是**求解量**，不是温度：这一档解的是一条
一般的输运方程，量的物理身份由调用者给的源与边界条件决定。报告如实印它的路径与单位，
不替它起名字。

## 边界

- **固定几何**：度规是输入，不与平衡交替更新。要几何随剖面一起走，见[含时演化](../evolve/evolve.md)。
- **单通道**：一次解一条方程。多通道（电子/离子/密度/电流）在演化那一栏。
- 无热容项 ⇒ 无 `W_th` / `τ_E` / `β_N` / `Q`。这一档拒绝报它们，而不是拿定态量凑一个。
