---
title: "闭包插件面：输运系数与源项"
---

# 闭包插件面：输运系数与源项

*输运 (Transport) · 本域答：chi / D 从哪来、源项怎么沉积——每个插件对着它移植自的那个上游码，逐位对不对。*

$\chi$ 与 $D$ 从哪来、源项怎么沉积。这一章是本册**记录密度最高**的一域，因为每一个闭包
插件都是从某一个上游码移植过来的，而每一次移植都欠一条"移植对了没有"的记录。

★★**这一域的判据性质与别处不同：它可以做到逐位。** 一个插件如果是同一个函数的另一实现，
那么对着它移植自的那个上游码，答案应当在机器精度内一致——不是"吻合到 1 %"，是逐位。
容差一旦松到百分之几，就说明中间有一步没对上，而那一步迟早会咬人。上一册在这里有过一次
很有教益的经过：`V-01`（GACODE 三个白盒端口）当日两转，先因逐 $k_y$ 增长率只有 3/17 吻合而
降档，同日查出根因是 Debye 屏蔽未接线，接上后 17/17 吻合到 $10^{-3}$。★**那次降档是记录
制度在起作用**——判据够硬，缺陷才会自己浮出来。

第二类陷阱是**跨设置比较**。同一册还踩过：参照夹具录在 `SAT_RULE=0`，而测量跑在
`SAT_RULE=2`，于是"对不上"被误读成移植错误。★**记录必须把双方的设置写进 `validity_domain`；
设置不同的两个数放在一起，比出来的差没有含义。**

源项的判据是另一路：沉积积分闭合。源沉积不管形状多复杂，总量必须守住——这一条与插件
对不对无关，是纯粹的自证，但它抓得住一类别的判据抓不住的错。

上一册这一域有 `V-01`..`V-05`（GACODE 端口、NN 代理、QLKNN、回归套件、动量 parity）、
`C-05`（Waltz 2007 动量）、`C-11`（QuaLiKiz 基准）。已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-TR-003` · 输运系数插件族与统一无量纲前端** — MUST · 验证方法：检查 + 测试

> （FR-TR-003/004）插件按名分派；统一前端共享；沉积积分闭合

**`FR-TR-004` · 源项插件族与 exp / imp 契约** — MUST · 验证方法：检查 + 测试

> （FR-TR-003/004）插件按名分派；统一前端共享；沉积积分闭合

**`NR-TR-003` · 插件接入** — MUST · 验证方法：检查 + 测试

> `TransportSolver["fytrans"]` 惰性解析；抽象类不 import 实现

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-closure-15d-source-switches`](../../reports/tr-closure-15d-source-switches.md) | 验证 | 成立 | 基线自身（同一算例、只改一个开关） | 1.24 | 草稿 | [jsonld](../../records/tr-closure-15d-source-switches.jsonld) |
| [`tr-closure-dt-burn-astra`](../../reports/tr-closure-dt-burn-astra.md) | 对拍 | 成立 | DT 分支比 3.5 / 17.6 · ASTRA | 1.25 | 草稿 | [jsonld](../../records/tr-closure-dt-burn-astra.jsonld) |
| [`tr-closure-lazy-plugin-resolution`](../../reports/tr-closure-lazy-plugin-resolution.md) | 验证 | 成立 | 导入后 `sys.modules` 的增量本身 | 1.21 | 草稿 | [jsonld](../../records/tr-closure-lazy-plugin-resolution.jsonld) |
| [`tr-closure-plugin-dispatch`](../../reports/tr-closure-plugin-dispatch.md) | 验证 | 成立 | 彼此 | 1.22 | 草稿 | [jsonld](../../records/tr-closure-plugin-dispatch.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
