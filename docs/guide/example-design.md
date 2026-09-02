---
title: 典型算例 · 放电设计 (Worked Example · Discharge Design)
---

# 放电设计：从场零到平顶位形

**问的是**：线圈电流该给多少，才有这个位形。这一族有三步，各自回答不同的问题——

| 步 | 算例 | 问的是 | 解的是 |
| :--- | :--- | :--- | :--- |
| 击穿前 | `breakdown-iter` | 场零区够不够干净、磁通够不够 | 无等离子体的零场区设计 |
| 轨迹 | `pulse-iter` | 电源要多大、爬升怎么走 | 前馈轨迹（**浏览器专属**） |
| 平顶 | `discharge-iter` | 这个边界要多少线圈电流 | 自由边界**反解** |

三步都要装置牌：`export FYLITE_DEVICE_DIR=~/fylite-decks/iter    # 见「安装与环境」：牌从 A-Box 拖回`。

## 一 · 场零（击穿前）

```bash
fylite cases --run breakdown-iter
```

```text
breakdown-iter  bar=breakdown -> fylite_breakdown  [device iter]
  fields: 11 mapped, 0 sub-capability, 6 shared, 0 ui
  acceptance: unevaluated  flux_error=unevaluated
```

| 量 | 值 | 读法 |
| :--- | ---: | :--- |
| `feasible` | `True` | 在给定限值内找到了解 |
| `null_ok` / `b_max` | `True` / 2.070e-5 T | 零场区内最大剩磁，容差 `b_tol` = 2e-3 T |
| `b_rms` / `b_centre` | 1.148e-5 / 6.077e-7 T | 区内均方根 / 中心点 |
| `flux_Wb` / `flux_target_Wb` | 0.478683 / 0.5 Wb | 拿到的磁通 / 要的磁通 |
| `flux_error` | **−0.0213** | 差 2.1 %——**欠**，不是超 |
| `iterations` | 485 | |
| `limits_enforced` | `True` | 逐通道电流上限（`i_max_aturn` 各 2e7 A·匝）确实生效 |
| `over` / `at_bound` / `channels_over_current` | 空 | 没有通道顶到限值 |

★**「可行」与「达标」是两件事**：`feasible=True` 且 `null_ok=True` 说零场区合格，而
`flux_error = −2.1 %` 说磁通没给够。两者同时为真，是设计上很常见的一步——它告诉你要
么放宽零场区半径，要么加磁通预算，而不是「失败了」。

## 二 · 轨迹（浏览器专属）

```bash
fylite cases --run pulse-iter
# 拒绝：browser-only by declaration —— PF supply sizing over the design bar's
# target controls；它读设计栏的输入并给出电源电流与电压，不回答新问题
```

★**这是按名拒绝，不是缺功能。** 实测过：不跑设计栏直接按它，得到的数与设计栏**逐位
相同**——它是那条栏输入的一次组合，不是一条独立能力。要它的答案，在浏览器的
[放电设计页](browser-app.md)上按；要 Python 侧的等价物，见 `scenario.design.pulse`
（前馈轨迹、通道限值、带界最小二乘）。

## 三 · 平顶位形（自由边界反解）

```bash
fylite cases --run discharge-iter
```

```text
discharge-iter  bar=discharge -> fylite_discharge  [device iter]
  fields: 16 mapped, 0 sub-capability, 0 shared, 7 ui
  note: icap 0 == no per-channel cap (page currentCap())
  acceptance: unevaluated  error=unevaluated
```

解出来的位形与它要付的代价：

| 量 | 值 |
| :--- | ---: |
| `pass` 退火趟数 | 7 |
| `shape_error` 形状残差 | 0.157777 |
| `equilibrium.ip` | 1.5e7 A |
| `equilibrium.axis_r` / `axis_z` | 6.3561 / 0.075947 m |
| `equilibrium.psi_axis` / `psi_bnd` | 146.132 / 64.8455 |
| `equilibrium.iterations` / `residual` | 76 / 8.218e-4 |
| `equilibrium.fb_amp` | −566470（垂直反馈幅度） |
| `aturns` 12 个线圈 | −26.27 … +36.65 MA·匝 |

解出来的**形状观测量**，与目标对照着读：

| | `a` | `kappa` | `delta_upper` | `delta_lower` | `r0` | `z0` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 解出 | 1.66563 | 1.90106 | 0.236713 | 0.0262301 | 6.21155 | 0.147592 |

★**`shape_error` 是这一步唯一诚实的总结数**。逐个形状量去对目标会误导：反解是在**一组**
观测量上做最小二乘，某一个量差得多、另一个差得少，是加权的结果而不是缺陷。

★**`pass: 7` 是退火趟数，不是「通过」。** 它 ≥ 1 才说明搜索确实改进过设计起点；
`pass: 0` 意味着起点就是终点——那通常是限值把解卡死了。

## Python 入口

```python
from fylite import scenario as S, device

dev = device.load_device(device.deck_path("iter_device.yaml"))

b = S.design.breakdown(r0=6.2, z0=0.0, radius=0.3, flux_target=0.5,
                       device=dev, b_tol=2e-3, i_max_aturn=[2e7] * 12)
b["feasible"], b["null_ok"], b["flux_Wb"], b["flux_error"]
# True, True, 0.48020945528328374, -0.019790544716716263

d = S.design.discharge(target={"r0": 6.2, "a": 2.0, "kappa": 1.85,
                               "delta_upper": 0.45, "delta_lower": 0.45, "z0": 0.0},
                       ip=15e6, i_max=[2e7] * 12)
d["pass"], d["shape_error"]                     # 7, 0.1617371112287015
```

三处**签名上的坑**，都是实测踩过的：

- 目标边界要 `delta_upper` / `delta_lower` **两个**三角度，没有合起来的 `delta`；
- `discharge` 的装置来自 `$FYLITE_DEVICE_DIR`，**不收 `device=`**——多给一个会被
  `**solve_kw` 一路传到 `gs_free_solve` 那里报 `unexpected keyword argument`；
  `breakdown` 则**收** `device=`。两者不一样，不是笔误。
- 逐通道电流上限缺省从装置牌的 `power_supply` 组读；**拖回来的 ITER 牌没有这一组**
  （见[安装与环境](install.md)里那条「拖回来不是等价替换」），所以上面显式给了
  `i_max_aturn` / `i_max`。不给且牌里也没有，会得到 `KeyError: 'power_supply'`——
  按名失败，不是静默取一个缺省限值。

另有 `S.design.feasible(axis1=…, axis2=…, r0=…, device=dev)`：只问「这套限值下有没有解」，
不返回设计。

## 报告与边界

```bash
fylite cases --report discharge-iter --out out/discharge
```

- **自由边界反解不是平衡反演**：这里给的是**要什么位形**、求线圈电流；反演给的是
  **测到了什么**、求位形。两者的输入与判据完全不同，见[诊断分析：平衡反演](example-reconstruction.md)。
- 线圈几何、匝数、电阻与限值**全部取自装置牌**；换一台机器就是换一份牌，代码不动。
- 垂直稳定性是另一件事：`fb_amp` 只是这一解所需的反馈幅度，γ 与被动导体集的关系见
  [稳定性与控制](stability-and-control.md)。
