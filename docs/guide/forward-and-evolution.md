---
title: 正解与演化 (Forward Solve & Evolution)
---

# 正解与演化

## 前向自由边界正解

:::{important}
**本节记的是 EFIT 的行为，而这条入口在本分发里已经不作答。** 驱动它的 `libefit.so`、
Green 表生成器与全部表按 LICENSE 3.1 移除，它们的**录得输出**也随之移除（那些答案是
被移除求解器的产物）。所以 `fylite.run.forward_equilibrium` 今天对任何输入都抛
`KefitRunError` 并说明为什么——签名保留，是为了在**调用处**给出有理由的失败。见
[Fortran 制品去哪了](#fortran-artifacts)。

下面的数字是**当年在库还在时实测**的，留着是因为它们仍是判据：它们说明这条路走的确实
是正解而不是拟合，也说明「给定剖面」这个通道到底能规定什么。今天要做一次**新的**自由边界
正解，走 `code/forward` 门（`fydoc.complete`）——它**说自己是谁**，不冒名顶替。
:::

同一 GS 核的另一种驱动：`iconvr=3` 跳过外层拟合，给定 $I_p$、线圈电流与剖面，
让边界随线圈场浮动。

```python
r = forward_equilibrium(meas, betap0=0.69, preset="gui_v5", tables="wpf2018")
```

**一次约 0.05 s**（当年实测），故扫参数、做对照、跑优化都可行。

**`chisq is None` 不是缺陷**：被跳过的正是那个拟合外层，报拟合优度会是无意义的。
（这也正是判据：同一份 k-file 去掉 `ICONVR=3` 反而根本产不出 g-file。）

### 剖面只能经解析三参数规定

可规定的剖面是 `ICURRT=4` 的 `BETAP0`/`EMP`/`ENP`。p′/FF′ 的**多项式**通道在平衡
模式下是**惰性的**——`ICURRT` 取 2/4 各配约束行有无，四种组合给出**逐位相同**的
平衡。故 `forward_equilibrium(pprime_coefs=…)` 当年**直接抛错**而非静默无效。

### 边界确实浮在线圈场上

判据不靠断言靠对照——12 个 PF 归零：

| 量 | 线圈=实测 | 线圈=0 |
| :--- | ---: | ---: |
| $q_{95}$ | 3.9741 | 2.2383 |
| 边界 $R$ 区间 | [1.379, 2.225] | [1.625, 2.370] |

## 电磁对象层

演化与控制的全部信息量在 $M$、$R$ 与一个时间推进上——静态 GS 里 $R$ 根本不出现。

```python
from fylite import device as D

#: ★机器只解析一次：`conductor_set` 先看装置 fyo 文档（浏览器一直用的那份），
#: 文档不带矩形时才回落到 deck。把 deck 目录**急切地**解析出来再逐个面传下去，
#: 与调用方显式指定路径无法区分——文档因此永远轮不到被问。
cond = D.conductor_set()                  # 或 D.conductor_set(TABLES)
els, etas, sl = D.passive_set(DEV, ("inner_shell", "outer_shell", "passive_plates"))
cm = D.channel_matrices(cond, eta_coil_uohm_m=..., eta_vessel_uohm_m=...)
```

- 导体几何权威 = 装置 fyo 文档；文档不带几何时才回落到 efund deck。**本仓的
  `east_device.yaml` 两者都带**，所以这条回落轮不上：外壳 40 段与铜板 10 块本来就只在
  文档里（deck 无此批）。
- **两算路验收**：由 deck 几何自算的 ψ 响应对 `rv6565.ddd` 逐段比值恒为
  $1/(2\pi)$（表存 Wb/rad/A，EFIT 的 ψ 约定）。★这是**当年的**对照——`rv6565.ddd`
  属于按 LICENSE 3.1 移除的那批表，本分发里没有它，这道检验因此跑不起来。
  它留在这里是判据，不是可复算的步骤。
- 真空室本征时间常数 $\tau=M/R \in [0.39, 13.1]$ ms。

## 电压驱动的位形演化

```python
from fylite.scenario.control.evolution import evolve_free_boundary
r = evolve_free_boundary(meas, time, voltages_per_turn,
                         eta_coil_uohm_m=..., eta_vessel_uohm_m=...)
```

链条是：每匝电压 → 隐式 Euler 推进（12 通道 + 40 壳段）→ 逐步正解，
涡流场经 `IVESEL=1`+`VCURRT` **真正进入 GS**。

判据是**关掉被动结构位形演化须显著改变**：CS 电压阶跃下求解器自产涡流 ~500 A，
有壳 vs 冻壳的 Δq95 随暂态单调建立至 +0.044。

:::{note}
非线性路径的涡流只能走 40 段**制表列**——IC 快控线圈与外壳/铜板无 Green 响应列
（缺口 E-18）。线性化路径不受此限（只需几何）。
:::

★走查用的 notebook 已不在本仓，仓根 `examples/` 也已删除——今天的可跑示例是算例语料（`cases/`），见[算例语料](../examples/index.md)起的五章。