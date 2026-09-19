---
title: "前向自由边界与 Green 响应核"
---

# 前向自由边界与 Green 响应核

*平衡 (Equilibrium) · 本域答：从线圈电流与剖面正着解 Grad-Shafranov，解得对不对；正反两向共用的那张响应核是不是同一张。*

正着解一次 Grad-Shafranov：给定线圈电流、给定 $p'$ 与 $FF'$，问磁面在哪里。这是平衡这一组
的地基——本组另外五章、乃至 MHD 稳定性那一整组，全都站在这一次求解的结果上。地基量不准，
上面量什么都不算数。

量它的难处不在"解出来了没有"，在**拿什么当真答案**。自由边界解没有闭式解，两个码的差
也说明不了谁对：两套离散、两套边界处理，差百分之几是常态。所以这一域的主判据必须落在
**解析解**上——Solov'ev 平衡有闭式 $\psi(R,Z)$，拿它当尺，差多少就是错多少，没有商量余地。
上游 SRS 的〈验证基准〉写的正是这一条，且写成 MUST。

★**Green 响应核是这一章的第二件事，而且它是个容易漏的地方。** 正问题与逆问题、重构，
三条链共用同一张线圈到网格的响应阵。共用得对不对，光看正问题的答案看不出来——正问题
自己跟自己一致，是废话。要验的是**同一张核在两个方向上是同一张**：磁族的雅可比应当等于
Green 响应阵。这一条只能用交叉检验抓，抓不到就会以一种很安静的方式错下去。

★★**2026-09-17 抓过了**，记在
[`eq-forward-green-response-shared`](../../reports/eq-forward-green-response-shared.md)。
做法是把那张阵**装出来**：逐通道打单位电流，得到 $154\times12$ 的响应阵 $G$；再问三件事。
一，叠加成不成立——$\lVert G I-\text{coilshare}(I)\rVert/\lVert\cdot\rVert = 2.2\times10^{-16}$。
二，有限差分量到的雅可比是不是 $G$ 的列——最劣 $6.8\times10^{-13}$。
三，零输入给不给**恰好**的零——给了，是 0 而不是小量。
★第三问单列不是凑数：只验叠加的差分形式，会放过一个带常数偏置的仿射映射，
而线圈响应里若掺了常数项，反演出来的电流分布就会系统地偏。
★★**这三格都是恒等式检验，不是对标**——别读成「精度很高」，该读成「这确实是同一个东西」。

★源审视那一半也做了，结论比预想的**更弱一点，也更诚实**：正向 `coilshare_case` 调
`em::element_response`，反向 `reconstruction_case` 调 `breakdown::channel_field`，而后者头一件事
就是调同一个 `em::element_response`——**两条路不是同一句调用，是同一个被调函数**，
差别只在先折通道还是先折元件，代数上恒等。
★★**但抄录要的那个 `ResponseCache` 在内核里根本不存在。** 两侧各自现算，而且
**求积阶数不共享**：`coilshare` 的两个设置项（默认 4/3）对重构侧一个设置项（默认 8）加一处硬编码（3）。
配错要付多少代价，量出来了：环上 $2.8\times10^{-4}$、探针上 $4.0\times10^{-3}$——
**与孪生回路本身的残差同一量级**，而不会有任何东西报警。本册现有算例恰好配对，
所以结论不受影响；★**但那是碰对的，不是保证**，已作记名缺口留着。

★另一条也补上了：[`eq-forward-self-contained-core`](../../reports/eq-forward-self-contained-core.md)
答 `NR-EQ-005`。数值核 crate 的 `[dependencies]` 只有一行 `rayon`（可选，开不开结果逐位相同），
整个依赖闭包的外部包是 rayon 那条线程栈的六个，**科学计算包一个没有**——
线性代数与特殊函数全是自写件。Python 层 63 个文件、0 处生态导入；
再把 `sp`/`spdm`/`fytok` 三根在 `sys.meta_path` 上**封死**整包导一遍，62 个模块全导得进。
★最后这一步是抄录点名要的，理由很实在：**AST 扫描抓不到动态导入**。
★这一条比抄录问的更强（问的是「有没有 import 上游」，答的是「连第三方数学库都没有」），
代价也是真的：那些数学都得自己验，**本册其余各条量的正是那些自写件**。

上一册在这一域留下过两条：`B-14` 前向对 KEFIT、`V-17` Solov'ev 制造解，另有 `V-16` 读
GS 残差、`B-16` / `V-19` 定边界对 CHEASE 与 Solov'ev。★它们属于**上一套编号**，已随旧册
退役（`docs/benchmark-legacy/`，移出版本控制、仅存盘查阅），在这里点名只为记住这一域
被量过什么，不作为本册的记录。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-03` v0.43）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-03` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-EQ-001` · 自由边界前向 G-S 求解** — MUST · 验证方法：测试

> 定边界 Solov'ev 深内点 < 5e-4；自由边界 $I_p$ 约束收敛 rel 1e-6；收敛参数显式回显

**`FR-EQ-002` · Green 响应核为共享一等资产** — MUST · 验证方法：检查 + 测试

> 磁族雅可比 = Green 响应阵；正 / 反向共用同一 `ResponseCache`

**`NR-EQ-002` · 解析基准精度** — MUST · 验证方法：测试

> 见 FR-EQ-001 判据

**`NR-EQ-005` · 自包含数值核（无后端依赖）** — MUST · 验证方法：检查 + 测试

> 自包含**八模块**（numerics/circuits/contour/forces/solver_core/response/inverse_core/reconstruction_core）模块级链无 `spdm`/`fytok`/`sp`（2026-08-05：`greens_function` 死遗留已删；仓内 AST 测试固化，匹配面含 `sp.*`）+ 封锁三根隔离加载

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-forward-boundary-rule-vs-kefit`](../../reports/eq-forward-boundary-rule-vs-kefit.md) | 对拍 | 未判（读数） | KEFIT | 1.17 | 草稿 | [jsonld](../../records/eq-forward-boundary-rule-vs-kefit.jsonld) |
| [`eq-forward-chease-solovev`](../../reports/eq-forward-chease-solovev.md) | 对拍 | 成立 | CHEASE | 1.17 | 草稿 | [jsonld](../../records/eq-forward-chease-solovev.jsonld) |
| [`eq-forward-green-response-shared`](../../reports/eq-forward-green-response-shared.md) | 验证 | 成立 | 它自己的有限差分雅可比，以及由单位电流装出的响应阵 | 2.15 | 草稿 | [jsonld](../../records/eq-forward-green-response-shared.jsonld) |
| [`eq-forward-kefit-east137985`](../../reports/eq-forward-kefit-east137985.md) | 对拍 | 成立 | KEFIT | 1.17 | 草稿 | [jsonld](../../records/eq-forward-kefit-east137985.jsonld) |
| [`eq-forward-self-contained-core`](../../reports/eq-forward-self-contained-core.md) | 验证 | 成立 | 各自的依赖声明与导入图 | 1.18 | 草稿 | [jsonld](../../records/eq-forward-self-contained-core.jsonld) |
| [`eq-forward-solovev-fixed-boundary`](../../reports/eq-forward-solovev-fixed-boundary.md) | 验证 | 成立 | Solov'ev 解析平衡 (closed form) | 1.18 | 草稿 | [jsonld](../../records/eq-forward-solovev-fixed-boundary.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
