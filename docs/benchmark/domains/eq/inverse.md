---
title: "静态逆解：形状到线圈电流"
---

# 静态逆解：形状到线圈电流

*平衡 (Equilibrium) · 本域答：反过来问：要这个形状，线圈该通多大电流。*

反过来问：要这个形状，线圈该通多大电流。这是装置设计与波形规划天天在用的一步，也是
少数几个**有硬真值**的问题——因为它可以自证。

★**合成场回收**是这一章的主判据，而且它足够硬：取一组已知的线圈电流，正着算出它产生的场，
再把那个场当作"目标形状"喂给逆解，看它能不能把原来那组电流找回来。真值是已知的，
容差可以压到 $10^{-6}$ 量级。这一档过不了，后面对别的码量多少都没有意义。

难处在**正则化**。逆问题是病态的：形状只约束了少数几个自由度，而线圈有十几个，解不唯一。
于是每个码都会加自己的正则项，而正则项一加，"答案"就成了"这个码在这个正则下的答案"。
★**两个码的逆解结果差 20 % 完全可以两边都没错。** 所以这一域对外部码的比较，记录里必须
写清双方的正则设置与自由度数——不写，那个比较就不可复算，也就不该收。

★2026-09-19 ITER 那条有了线圈额定：DINA-IMAS（ITER Organization 的场景码）的每匝上限乘本卡片匝数——
同一套线圈，匝数逐一相同。无界设计要 PF1 的 1.22 倍、PF6 的 1.27 倍额定，**这台机器给不出**；
在额定内重解守住额定，边规则下 628 次**收敛**（节点规则下它不收敛，那是节点规则的抖动）。

★★**主判据本身（合成场回收）2026-09-19 才有记录**：
[`eq-inverse-core-field-recovery`](../../reports/eq-inverse-core-field-recovery.md)。
ITER 型 11 路线圈、已知电流合成的边界通量与 X 点场，经逆解的线性核（响应行 + 最小二乘，不加正则）回收：
约束行上 $6\times10^{-14}$、十六个没参与拟合的点上 $1.5\times10^{-13}$。★判的是**场**，不是电流——
只给形状时电流本就定不住（零空间）。
★★ITER 参考分离面那条同日由「判不了」转判成立，靠的是一个**正对照**：拿额定内的一组已知电流正解出一条
机器做得到的分离面，让设计去复原它——kappa、delta_lower 回到 0.3 % 内，而参考分离面上差 3 % 与 10 %。
差是**目标的**（这条 METIS 曲线要的形状，本剖面族配这组额定给不出），不是设计的。
★delta_upper 在正对照上**没回来**（−16 %），记为局限。
★EAST 那条（对 FreeGSNKE）在边规则上重量：没有位置控制器时，设计把柱子锚在上一次解的位置、在线圈自己的场上
读残差，末尾撤锚——撤锚后线圈自己立得住（虚拟对 59 A），零空间的结论照旧成立。

上一册的 `V-22`（ITER 参考分离面上的静态逆解）与 `B-21`（对 FreeGSNKE 的逆解）在这一域。已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-03` v0.43）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-03` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-EQ-005` · 静态逆解（形状$\to$线圈电流）** — MUST · 验证方法：测试

> 已知电流合成场精确回收 rtol 1e-6

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-inverse-core-field-recovery`](../../reports/eq-inverse-core-field-recovery.md) | 验证 | 成立 | 已知电流（孪生真值） | 1.1 | 草稿 | [jsonld](../../records/eq-inverse-core-field-recovery.jsonld) |
| [`eq-inverse-freegsnke-east137985`](../../reports/eq-inverse-freegsnke-east137985.md) | 对拍 | 成立 | FreeGSNKE | 1.24 | 草稿 | [jsonld](../../records/eq-inverse-freegsnke-east137985.jsonld) |
| [`eq-inverse-iter-reference-separatrix`](../../reports/eq-inverse-iter-reference-separatrix.md) | 验证 | 成立 | ITER 参考分离面（装置牌上的数字化曲线） | 1.26 | 草稿 | [jsonld](../../records/eq-inverse-iter-reference-separatrix.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
