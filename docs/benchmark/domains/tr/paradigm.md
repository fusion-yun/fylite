---
title: "求解范式：刚性稳定化与稳态通量匹配"
---

# 求解范式：刚性稳定化与稳态通量匹配

*输运 (Transport) · 本域答：刚性闭包下还收不收敛（Pereverzev-Corrigan）；稳态通量匹配的根找不找得到、找得准不准。*

刚性稳定化与稳态通量匹配——两种求解范式，共一章，因为它们答的是同一个问题的两半：
**当输运系数对梯度极度敏感时，怎么才能算得下去。**

刚性稳定化（Pereverzev-Corrigan）的判据有一条很漂亮的性质：★**离散层面精确对消。** 加进去
的那一项在离散意义下应当恰好抵消，于是定态解不依赖稳定化参数 $d_{pc}$ 取多少。这给了一条
不需要任何外部参考的硬判据——定态对 $d_{pc}$ 不敏感，不敏感到什么程度是可以量的。再加一条
对照：刚性闭包下裸 Picard 环停滞，而加了稳定化的收敛。**有对照的判据才说明这一项在起作用，
没有对照只能说明"跑通了"。**

★★**本册第一条记录 [`tr-paradigm-pereverzev`](../records/tr-paradigm-pereverzev.jsonld)
量的就是这三句话，而它判 `inconclusive`——因为上一段最后那条对照，本接口上演示不了。**
前两句成立：扫 $d_{pc}$ = 0 … 40，两种闭包的定态逐点相对偏差最大 **1.4e-11**，且内迭代
次数从 2 次变到 1010 次（constant）——定态相同而路径不同，两句合起来才说明这一项装上了
且只改条件数。★但那个数**不是机器精度，是 Picard 容差限**：偏差随 $d_{pc}$ 单调上行，
因为两条路走到同一不动点的精度由 `tol` 定，不由对消的代数定。对消在代数上精确，量出来的
数是收敛容差的像——这两件事必须分开说，合起来说就成了夸大。

★而第三句演示不了，理由不在参数没扫够，在闭包的形式里：内核的 `stiff` 闭包是
$\chi_0(p_1 + p_2 g/(1+g))$，对梯度**有界且饱和**。扫遍刚度盒十二点（$\chi$ 动态范围
最高 8001 倍），裸环**一点都没停滞**，最慢 495 次内迭代。梯度→$\chi$→梯度 的回授被饱和
封住，Picard 映射保持压缩；而 P-C 要对付的正是 $\chi$ 随梯度**不封顶**或**带阈值**的那类
闭包。★**所以这一条不是「没人去量」，是「在这一族闭包里不存在可量的操作点」**——要量它
得换一路（`evolve` 的 `turbulent` / `flux-match`，或 `nn_tables/` 里的 QLKNN / TGLFNN 代理），
那属于另一条记录。

★还有一件顺带量到、判据没问的事，记在记录里：**稳定化在这一族闭包上多数区间是净变贵的。**
内迭代 constant 2 → 13 → 42 → 277 → 1010 → 2406，stiff 43 → 28 → 71 → 550 → 1996 → 顶格；
只有 stiff 闭包 $d_{pc}=0.1$ 那一点上它**减少**了迭代（43 → 28）。"稳定化"不等于"更快"。

稳态通量匹配是另一路：不推时间，直接解"输运通量等于源"的稳态方程。它与推时间到定态
应当给出同一个答案——★**这是一条极好的交叉检验，因为两条路的数值性质完全不同**（一个是
时间推进，一个是 Newton 求根）。两条路的根若有差异，记录要把差异记下来而不是取其一：
差异本身是关于问题条件数的信息。

上一册这一域有 `B-07`（TGYRO 收敛态）、`V-06` / `V-07`（TGYRO 映射与算例）。已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-TR-005` · 刚性稳定化生产路径** — MUST · 验证方法：测试

> P-C 离散精确对消；定态对 $d_{pc}$ 不敏感；刚性闭包下 Picard 收敛（裸环停滞对照）

**`FR-TR-006` · 耦合隐式块解（可选，候选 ADR）** — MUST · 验证方法：检查

> ADR 裁决记录

**`FR-TR-007` · 稳态通量匹配** — MUST · 验证方法：测试

> 匹配残差收敛；根差异（PDE vs Newton）记录

**`FR-TR-008` · 环向动量 / 转动通道（路线项）** — SHOULD · 验证方法：检查

> 动量通道设计成文（路线 [TBD]；**描述子落点已备**——`momentum_tor` 声明可解析、求解 fail-loud 指向本条）

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-paradigm-coupled-block-adr`](../../reports/tr-paradigm-coupled-block-adr.md) | 验证 | 未判（读数） | 抄录的判据：「ADR 裁决记录」，证据栏「候选 ADR（[TBD]）」 | 1.5 | 草稿 | [jsonld](../../records/tr-paradigm-coupled-block-adr.jsonld) |
| [`tr-paradigm-flux-match-vs-pde`](../../reports/tr-paradigm-flux-match-vs-pde.md) | 验证 | 成立 | fylite · `transport::solve_steady`（PDE，dt = inf） | 1.5 | 草稿 | [jsonld](../../records/tr-paradigm-flux-match-vs-pde.jsonld) |
| [`tr-paradigm-pereverzev`](../../reports/tr-paradigm-pereverzev.md) | 验证 | 未判（读数） | P-C 项在不动点上的恒等对消（解析不变性） | 1.7 | 草稿 | [jsonld](../../records/tr-paradigm-pereverzev.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
