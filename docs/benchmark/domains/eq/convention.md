---
title: "约定与口径：COCOS 与插件接入"
---

# 约定与口径：COCOS 与插件接入

*平衡 (Equilibrium) · 本域答：符号、方向、2π 因子、单位——两个码的数能不能放在一起比，先过这一关。*

这一章不产出任何物理结论，它管的是**两个码的数能不能放在一起比**。符号、方向、$2\pi$ 因子、
$\psi$ 的定义差一个 $2\pi$、$q$ 的符号随环向角方向翻——COCOS 这套约定编号存在的理由，
就是这些差别多到必须编号。

★**它排在这里而不是附录里，是因为它是前置条件，不是补充说明。** 口径没对齐时做的任何
比较，量出来的是约定差，不是实现差；而约定差常常长得像个物理结论——两个码的 $q$ 剖面
差一个负号，看上去像是有人把电流方向搞反了。本册把它单列一域，就是为了让每一条跨码记录
都能指着这一域说"我的口径在这里说清了"。

量它的办法是**往返**：外部件吞进来、按 COCOS 换算、再吐回去，逐字段比。往返不闭合，
说明换算表里有一格是错的。这一条不需要任何物理判断，纯粹是转换的自证。

插件接入也归在这一章：一个外部实现挂进来之后，它是不是真的按名解析、抽象层有没有偷偷
import 实现——这与口径是同一类问题，都是"接得对不对"，不是"算得准不准"。

上一册的 `V-15`（g 文件往返，COCOS 17）落在这一域。已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-03` v0.43）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-03` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`NR-EQ-001` · COCOS 一致性** — MUST · 验证方法：检查 + 测试

> 外部吞入经 COCOS 换算；无隐式同约定；geqdsk 摄入路 `sp_from_geqdsk` 转 COCOS 17（$\psi \times 2\pi$、$FF'/p'\div 2\pi$、$q\times \sigma _\rho \theta \phi$、F/p/Ip 不变）

**`NR-EQ-006` · 插件接入** — MUST · 验证方法：检查 + 测试

> 五族名下标解析全返 `EquilibriumSolver` 子类（实例化按需）；框架无特判（`fytok/model` 非 docstring 零 `fyeq` 字面量）

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-convention-gfile-cocos-roundtrip`](../../reports/eq-convention-gfile-cocos-roundtrip.md) | 验证 | 成立 | 恒等式：写之后再读，必须回到原处 · 同一读取函数的另一实现（Python 定宽参照读者 ↔ Rust 数据层读者） | 1.3 | 草稿 | [jsonld](../../records/eq-convention-gfile-cocos-roundtrip.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
