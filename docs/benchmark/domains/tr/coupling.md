---
title: "双模、平衡耦合与代理栈"
---

# 双模、平衡耦合与代理栈

*输运 (Transport) · 本域答：解释性/预测性双模、与平衡的松散耦合、NN 代理对上游权重的逐位一致。*

解释性与预测性双模、与平衡的松散耦合、NN 代理栈。这一章的共同点是：★**它们都是接口，
不是物理**——错在接口上的时候，物理看起来完全正常。

双模的判据是同一份数据两个方向走得通：预测模式给定输运系数解剖面，解释模式给定剖面反演
输运系数。两条路串起来应当回到出发点。这是一条往返判据，性质与平衡那边的 g 文件往返相同。

平衡耦合的难处在**步幅**。输运与平衡不是每步都同步解的，松散耦合的步幅取多大，结果就
差多少。★记录必须把步幅写进 `validity_domain`：同一个算例在不同耦合步幅下给不同的答案，
这不是谁错了，是耦合方案的性质。不写步幅的耦合记录不可复算。

NN 代理栈有一条硬判据：**权重外置 + 逐位对拍**。权重不进分发件，从外置路径装载，装载后
对上游实现逐位一致。逐位这一档是可以做到的（NN 的前向传播是确定的），所以就该要求逐位——
松到 $10^{-6}$ 反而会把装载路径里的错放过去。

上一册这一域有 `V-02`（NN 代理）、`B-02` / `B-03`（JINTRAC ITER / JET）。已退役。

### 解释性反演核（2026-09-18）

`FR-TR-011` 入册，判**成立**。★★这条**早就实现了，只是没入册**：`transport::interpretive_channel`
（功率平衡反演 $q_{PB}$ 与 $\chi_{eff}$，平直剖面按名屏蔽）、C ABI 导出与 `code/interpretive` 门都在内核仓，
测试也在。本册一直把它列作空缺，是因为没有记录。

入册时补了一样数值证据：以常数 $\chi_0$ 预测求解出的剖面反演回去，$\chi_{eff}\cdot$gm7 对 $\chi_0$ 按 $h^2$ 收敛
（61 → 481 点：2.1e-3 → 3.8e-5）。★约定照实记：通量取 gm7 的面积、导热律取 gm3，所以反演回来是 $\chi_0/$gm7。
★顺带修掉 kernel 仓自 `12e603b`（通量规统一）起恒红的 5 道门——参照梯子把每弧度的 dpsi 喂给了整圈的
`equilibrium_ladder`，ρ 小 $\sqrt{2\pi}$。
详见 [`tr-coupling-interpretive-inversion`](../../reports/tr-coupling-interpretive-inversion.md)。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-TR-011` · 解释性 / 分析模式通量反演（路线项）** — MUST · 验证方法：检查

> 反演核接口成文（路线 [TBD]）

**`FR-TR-012` · 平衡耦合接口** — MUST · 验证方法：测试 + 检查

> 松散步幅回归；体积分取平衡网（源审视）

**`FR-TR-013` · NN 代理栈与权重外置** — MUST · 验证方法：检查 + 测试

> 权重不入分发件；外置路径装载 + NN 逐位对拍

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-coupling-equilibrium-outer-loop`](../../reports/tr-coupling-equilibrium-outer-loop.md) | 验证 | 成立 | ★**三组对照**：平衡held不重解 · 只追踪不重解 · 状态挂在 psi_N 标签上 | 1.23 | 草稿 | [jsonld](../../records/tr-coupling-equilibrium-outer-loop.jsonld) |
| [`tr-coupling-interpretive-inversion`](../../reports/tr-coupling-interpretive-inversion.md) | 验证 | 成立 | SRS-04 Eq. (eq-srs04-interp) 与本仓的预测性导热求解 | 1.13 | 草稿 | [jsonld](../../records/tr-coupling-interpretive-inversion.jsonld) |
| [`tr-coupling-nn-weights-external`](../../reports/tr-coupling-nn-weights-external.md) | 验证 | 成立 | 制品与打包声明本身 | 1.24 | 草稿 | [jsonld](../../records/tr-coupling-nn-weights-external.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
