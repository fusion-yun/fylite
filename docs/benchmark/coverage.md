---
title: 需求覆盖 (Requirement coverage)
---

# 需求覆盖 (Requirement coverage)

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。手维护的索引一定会与记录漂开——旧册的 reports/README.md 就是这么漏掉最后一条的。 -->

这一页只答一个问题：**够不够。** 每条需求一行，没有记录覆盖它的显示为空行——★空行不是排版，是缺口本身。按谁答什么问题读：这一页答「够不够」，各域的章页答「对着谁量到多少」，[`status.md`](status.md) 答「这些记录还作不作数」。

- 生成于 (recorded)：2026-09-17
- 需求 (requirements)：**57** 条，其中 **MUST 52** 条
- 已有记录覆盖 (covered)：**31** 条（54 %）
- ★**MUST 级空缺 (open MUST)：22 条**
- ★上游未给判据 (no criterion in the SRS)：**1** 条

## 平衡 (Equilibrium) · 前向自由边界与 Green 响应核

从线圈电流与剖面正着解 Grad-Shafranov，解得对不对；正反两向共用的那张响应核是不是同一张。　→ [本域章页](domains/eq/forward.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-001` | MUST | 自由边界前向 G-S 求解 | [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md) · [`eq-forward-chease-solovev`](reports/eq-forward-chease-solovev.md) · [`eq-forward-kefit-east137985`](reports/eq-forward-kefit-east137985.md) · [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md) | 对拍 · 对拍 · 对拍 · 验证 | 未判（读数） · 成立 · 成立 · 成立 |
| `FR-EQ-002` | MUST | Green 响应核为共享一等资产 | [`eq-forward-green-response-shared`](reports/eq-forward-green-response-shared.md) | 验证 | 成立 |
| `NR-EQ-002` | MUST | 解析基准精度 | [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md) | 验证 | 成立 |
| `NR-EQ-005` | MUST | 自包含数值核（无后端依赖） | [`eq-forward-self-contained-core`](reports/eq-forward-self-contained-core.md) | 验证 | 成立 |

## 平衡 (Equilibrium) · 磁面几何、全局量与形状表示

解出来的磁面上那些积分量（gm1..gm9 · 磁剪切 · Mercier · beta_p · l_i · W_mhd）与形状参数（MXH）算得对不对。　→ [本域章页](domains/eq/surface.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-003` | MUST | 磁面分析（0 维 / 1 维几何量与磁面积分） | [`eq-surface-chease-fixed-boundary-east`](reports/eq-surface-chease-fixed-boundary-east.md) | 对拍 | 成立 |
| `FR-EQ-012` | SHOULD | 固定边界高精度重解与磁面平均目录 | [`eq-surface-chease-fixed-boundary-east`](reports/eq-surface-chease-fixed-boundary-east.md) | 对拍 | 成立 |
| `FR-EQ-013` | SHOULD | MXH 磁面形状参数化与拟合 | — | — | — |

## 平衡 (Equilibrium) · 演化自由边界与涡流电路

让平衡随时间走，被动结构里的涡流跟不跟得上——轨迹对不对。　→ [本域章页](domains/eq/evolve.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-004` | MUST | 演化自由边界与涡流电路 | [`eq-evolve-analytic-circuit-limits`](reports/eq-evolve-analytic-circuit-limits.md) | 验证 | 成立 |

## 平衡 (Equilibrium) · 静态逆解：形状到线圈电流

反过来问：要这个形状，线圈该通多大电流。　→ [本域章页](domains/eq/inverse.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-005` | MUST | 静态逆解（形状$\to$线圈电流） | [`eq-inverse-freegsnke-east137985`](reports/eq-inverse-freegsnke-east137985.md) · [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md) | 对拍 · 验证 | 成立 · 未判（读数） |

## 平衡 (Equilibrium) · 测量重构与约束阶梯

从一炮的磁测量、MSE、动理学剖面反推平衡，反得准不准——★判准必须落在**可观测空间**。　→ [本域章页](domains/eq/reconstruct.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-006` | MUST | 测量重构与约束阶梯 | [`eq-reconstruct-kefit-twin`](reports/eq-reconstruct-kefit-twin.md) · [`eq-reconstruct-twin-truth-recovery`](reports/eq-reconstruct-twin-truth-recovery.md) | 对拍 · 验证 | 成立 · 成立 |
| `FR-EQ-007` | SHOULD | MSE 全形响应行 | — | — | — |
| `FR-EQ-008` | MUST | 快离子压强外部强迫项 | [`eq-reconstruct-fast-ion-pressure`](reports/eq-reconstruct-fast-ion-pressure.md) | 验证 | 成立 |
| `FR-EQ-009` | MUST | 内部约束行几何门控 | — | — | — |
| `FR-EQ-010` | MUST | kinetic-EFIT 自洽外环接口 | [`eq-reconstruct-kinetic-outer`](reports/eq-reconstruct-kinetic-outer.md) | 验证 | 成立 |
| `FR-EQ-011` | MUST | 源剖面曲率正则 | [`eq-reconstruct-curvature-prior`](reports/eq-reconstruct-curvature-prior.md) | 验证 | 成立 |
| `NR-EQ-003` | MUST | 不确定度传播 | — | — | — |
| `NR-EQ-004` | MUST | 孪生实验可验证（可观测空间） | [`eq-reconstruct-twin-observable-space`](reports/eq-reconstruct-twin-observable-space.md) | 验证 | 成立 |

## 平衡 (Equilibrium) · 约定与口径：COCOS 与插件接入

符号、方向、2π 因子、单位——两个码的数能不能放在一起比，先过这一关。　→ [本域章页](domains/eq/convention.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `NR-EQ-001` | MUST | COCOS 一致性 | [`eq-convention-gfile-cocos-roundtrip`](reports/eq-convention-gfile-cocos-roundtrip.md) | 验证 | 成立 |
| `NR-EQ-006` | MUST | 插件接入 | [`eq-convention-gfile-cocos-roundtrip`](reports/eq-convention-gfile-cocos-roundtrip.md) | 验证 | 成立 |

## MHD 稳定性 (MHD Stability) · 竖直稳定性、线圈受力与电磁线性模型

拉长的位形会不会竖直漂走、增长率多快；线圈受多大力；导出的线性模型对不对。　→ [本域章页](domains/mhd/vertical.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-014` | MUST | 线圈受力与导体表面场 | — | — | — |
| `FR-EQ-015` | MUST | 装置电磁线性模型导出（路线） | — | — | — |
| `FR-EQ-016` | MUST | 轴对称 $n=0$ 竖直稳定性判读 | — | — | — |

## MHD 稳定性 (MHD Stability) · 解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界

教科书有闭式答案的那两级：均匀电流柱的 q 带边、气球模 alpha_c(s) 曲线。★它们是本册的**尺**——尺不准，上面的都不算数。　→ [本域章页](domains/mhd/analytic.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-017` | MUST | 理想外扭曲模的 q 极限（L0） | — | — | — |
| `FR-EQ-018` | MUST | 气球模第一稳定边界（L1） | — | — | — |

## MHD 稳定性 (MHD Stability) · 能量原理变分内核 L2

delta-W 变分求解器本身：柱极限对不对、环几何耦合装配对不对、共形映射对不对。　→ [本域章页](domains/mhd/energy.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-019` | MUST | 能量原理变分内核（L2 的 B1：柱极限） | — | — | — |
| `FR-EQ-020` | MUST | 环几何耦合的组装机器（L2 的 B2 机器面） | — | — | — |
| `FR-EQ-021` | MUST | 表面电流模型的解析 β 极限（L2 的 oracle，非 L2 本体） | — | — | — |
| `FR-EQ-022` | MUST | 高 $\beta$ 序约化流体能量 $\delta W_F$（L2 的物理面） | — | — | — |
| `FR-EQ-023` | MUST | 一般位形的真空扰动能 $\delta W_V$（L2 三项的最后一项） | — | — | — |
| `FR-EQ-024` | MUST | 三项装配层 | — | — | — |
| `FR-EQ-025` | MUST | 星形域到单位圆盘的共形映射 | — | — | — |

## MHD 稳定性 (MHD Stability) · 全 delta-W、V5 基准与阻性壁模

三项齐全的 delta-W 对着国际 V5 基准的五码带落不落得进去；阻性壁模窗口在哪。　→ [本域章页](domains/mhd/deltaw.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-EQ-026` | MUST | MHD 判读的交付层 | — | — | — |
| `FR-EQ-027` | MUST | 完整 $\delta W$：螺旋箍缩（V5 的第一级） | — | — | — |
| `FR-EQ-028` | MUST | 动能归一与 $\omega^2$（全 $\delta W$ 支 F2） | — | — | — |
| `FR-EQ-029` | MUST | 环几何全 $\delta W$：定形边界 V5（全 $\delta W$ 支 F3 第一段） | — | — | — |
| `FR-EQ-030` | MUST | 环几何真空标量势与无壁 V5（全 $\delta W$ 支 F3 收口段） | — | — | — |
| `FR-EQ-031` | MUST | 理想壁分支与薄壁阻性壁模（E-3 第一级） | — | — | — |

## 输运 (Transport) · 方程组求解与边界条件

多通道 1.5D 方程组本身：离散、时间推进、五类边界条件、电流边界驱动。　→ [本域章页](domains/tr/equations.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-TR-001` | MUST | 多通道 1.5D 输运方程组求解 | — | — | — |
| `FR-TR-002` | MUST | 边界条件族与电流边界驱动 | [`tr-equations-boundary-family`](reports/tr-equations-boundary-family.md) | 验证 | 不成立 |

## 输运 (Transport) · 闭包插件面：输运系数与源项

chi / D 从哪来、源项怎么沉积——每个插件对着它移植自的那个上游码，逐位对不对。　→ [本域章页](domains/tr/closure.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-TR-003` | MUST | 输运系数插件族与统一无量纲前端 | [`tr-closure-plugin-dispatch`](reports/tr-closure-plugin-dispatch.md) | 验证 | 成立 |
| `FR-TR-004` | MUST | 源项插件族与 exp / imp 契约 | [`tr-closure-15d-source-switches`](reports/tr-closure-15d-source-switches.md) · [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md) | 验证 · 对拍 | 未判（读数） · 未判（读数） |
| `NR-TR-003` | MUST | 插件接入 | [`tr-closure-lazy-plugin-resolution`](reports/tr-closure-lazy-plugin-resolution.md) | 验证 | 成立 |

## 输运 (Transport) · 求解范式：刚性稳定化与稳态通量匹配

刚性闭包下还收不收敛（Pereverzev-Corrigan）；稳态通量匹配的根找不找得到、找得准不准。　→ [本域章页](domains/tr/paradigm.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-TR-005` | MUST | 刚性稳定化生产路径 | [`tr-paradigm-pereverzev`](reports/tr-paradigm-pereverzev.md) | 验证 | 未判（读数） |
| `FR-TR-006` | MUST | 耦合隐式块解（可选，候选 ADR） | [`tr-paradigm-coupled-block-adr`](reports/tr-paradigm-coupled-block-adr.md) | 验证 | 未判（读数） |
| `FR-TR-007` | MUST | 稳态通量匹配 | [`tr-paradigm-flux-match-vs-pde`](reports/tr-paradigm-flux-match-vs-pde.md) | 验证 | 成立 |
| `FR-TR-008` | SHOULD | 环向动量 / 转动通道（路线项） | — | — | — |

## 输运 (Transport) · 台基、锯齿与 0D 存量

台基高度、锯齿触发与 Kadomtsev 重分布、加料抽气的存量账——守不守得住。　→ [本域章页](domains/tr/pedestal.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-TR-009` | MUST | 连续台基模型 | [`tr-closure-15d-source-switches`](reports/tr-closure-15d-source-switches.md) | 验证 | 未判（读数） |
| `FR-TR-010` | MUST | 锯齿触发与 Kadomtsev 重分布 | [`tr-pedestal-sawtooth-kadomtsev`](reports/tr-pedestal-sawtooth-kadomtsev.md) | 验证 | 成立 |
| `FR-TR-014` | MUST | 0D 存量守恒（加料 / 抽气 / 衰变） | [`tr-pedestal-zerod-bookkeeping-metis`](reports/tr-pedestal-zerod-bookkeeping-metis.md) | 对拍 | 不成立 |

## 输运 (Transport) · 双模、平衡耦合与代理栈

解释性/预测性双模、与平衡的松散耦合、NN 代理对上游权重的逐位一致。　→ [本域章页](domains/tr/coupling.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `FR-TR-011` | MUST | 解释性 / 分析模式通量反演（路线项） | — | — | — |
| `FR-TR-012` | MUST | 平衡耦合接口 | [`tr-coupling-equilibrium-outer-loop`](reports/tr-coupling-equilibrium-outer-loop.md) | 验证 | 成立 |
| `FR-TR-013` | MUST | NN 代理栈与权重外置 | [`tr-coupling-nn-weights-external`](reports/tr-coupling-nn-weights-external.md) | 验证 | 成立 |

## 输运 (Transport) · 守恒、金标 parity 与口径

守恒回归到 1e-12；对 FUSE.jl / TORAX 逐模块 parity；IMAS/DD 一致；核自包含。★这一域是横切的——它管的是另外五域的**产出合不合格**。　→ [本域章页](domains/tr/conservation.md)

| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `NR-TR-001` | MUST | 守恒性 | [`tr-pedestal-sawtooth-kadomtsev`](reports/tr-pedestal-sawtooth-kadomtsev.md) | 验证 | 成立 |
| `NR-TR-002` | MUST | 金标 parity 验证 | [`tr-conservation-time-order`](reports/tr-conservation-time-order.md) | 验证 | 成立 |
| `NR-TR-004` | MUST | 自包含数值核 | [`eq-forward-self-contained-core`](reports/eq-forward-self-contained-core.md) | 验证 | 成立 |
| `NR-TR-005` | MUST | IMAS / DD 一致性 | [`tr-conservation-fyo-dd-contract`](reports/tr-conservation-fyo-dd-contract.md) | 验证 | 成立 |
| `NR-TR-006` | SHOULD | 可微性路线（近期 TODO） | — | — | — |

## MUST 级空缺 (open MUST requirements)

★这些是**硬缺口**：SRS 写的是「必须」，而本册没有任何记录覆盖它们。

| 需求 | 域 | 标题 |
| :--- | :--- | :--- |
| `FR-EQ-009` | 测量重构与约束阶梯 | 内部约束行几何门控 |
| `FR-EQ-014` | 竖直稳定性、线圈受力与电磁线性模型 | 线圈受力与导体表面场 |
| `FR-EQ-015` | 竖直稳定性、线圈受力与电磁线性模型 | 装置电磁线性模型导出（路线） |
| `FR-EQ-016` | 竖直稳定性、线圈受力与电磁线性模型 | 轴对称 $n=0$ 竖直稳定性判读 |
| `FR-EQ-017` | 解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界 | 理想外扭曲模的 q 极限（L0） |
| `FR-EQ-018` | 解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界 | 气球模第一稳定边界（L1） |
| `FR-EQ-019` | 能量原理变分内核 L2 | 能量原理变分内核（L2 的 B1：柱极限） |
| `FR-EQ-020` | 能量原理变分内核 L2 | 环几何耦合的组装机器（L2 的 B2 机器面） |
| `FR-EQ-021` | 能量原理变分内核 L2 | 表面电流模型的解析 β 极限（L2 的 oracle，非 L2 本体） |
| `FR-EQ-022` | 能量原理变分内核 L2 | 高 $\beta$ 序约化流体能量 $\delta W_F$（L2 的物理面） |
| `FR-EQ-023` | 能量原理变分内核 L2 | 一般位形的真空扰动能 $\delta W_V$（L2 三项的最后一项） |
| `FR-EQ-024` | 能量原理变分内核 L2 | 三项装配层 |
| `FR-EQ-025` | 能量原理变分内核 L2 | 星形域到单位圆盘的共形映射 |
| `FR-EQ-026` | 全 delta-W、V5 基准与阻性壁模 | MHD 判读的交付层 |
| `FR-EQ-027` | 全 delta-W、V5 基准与阻性壁模 | 完整 $\delta W$：螺旋箍缩（V5 的第一级） |
| `FR-EQ-028` | 全 delta-W、V5 基准与阻性壁模 | 动能归一与 $\omega^2$（全 $\delta W$ 支 F2） |
| `FR-EQ-029` | 全 delta-W、V5 基准与阻性壁模 | 环几何全 $\delta W$：定形边界 V5（全 $\delta W$ 支 F3 第一段） |
| `FR-EQ-030` | 全 delta-W、V5 基准与阻性壁模 | 环几何真空标量势与无壁 V5（全 $\delta W$ 支 F3 收口段） |
| `FR-EQ-031` | 全 delta-W、V5 基准与阻性壁模 | 理想壁分支与薄壁阻性壁模（E-3 第一级） |
| `FR-TR-001` | 方程组求解与边界条件 | 多通道 1.5D 输运方程组求解 |
| `FR-TR-011` | 双模、平衡耦合与代理栈 | 解释性 / 分析模式通量反演（路线项） |
| `NR-EQ-003` | 测量重构与约束阶梯 | 不确定度传播 |

## 上游未给判据 (requirements the SRS gives no criterion for)

★这些需求在 SRS 的〈验证矩阵〉里**没有判据行**。没有判据就无从验起——这是上游的缺口，不是本册的，照实记在这里等它补。

- `FR-TR-014` 0D 存量守恒（加料 / 抽气 / 衰变）
