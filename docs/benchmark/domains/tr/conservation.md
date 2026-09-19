---
title: "守恒、金标 parity 与口径"
---

# 守恒、金标 parity 与口径

*输运 (Transport) · 本域答：守恒回归到 1e-12；对 FUSE.jl / TORAX 逐模块 parity；IMAS/DD 一致；核自包含。★这一域是横切的——它管的是另外五域的**产出合不合格**。*

这一域是**横切的**：它不对应输运求解器的某一块，它管的是另外五域的**产出合不合格**。
守恒回归、金标 parity、IMAS/DD 一致、核自包含——四件事都是"不管你怎么算，出来的东西
必须满足这个"。

守恒是其中最硬的一条，也是最该压到底的一条：$10^{-12}$。★**守恒容差松一位，就等于宣布
这一位以内的错误本册不管。** 而输运里绝大多数接线错误恰恰先表现为守恒的微小破坏，
在剖面上还看不出来的时候，守恒已经在第八位上不对了。

金标 parity 是另一件事，而且要小心它的位置：对 FUSE.jl / TORAX 逐模块对拍，量的是**两套
不同实现**的差。★**这是对拍，不是验证**——两边吻合不证明谁对。它有价值，但它的价值是
"没有明显分歧"，不是"正确"。本册把这一条明确记成 `benchmark`，容差取实测带。

自包含核是一条结构判据：核不 import `spdm` / `fytok`。它没有数值，靠源审视。★**没有数值的
判据一样要进册**——它守的东西（分发件能不能独立跑）与任何一条数值判据同等重要，
而它比数值判据更容易在某次重构里被悄悄破坏。

上一册这一域有 `C-01` / `C-02`（ASTRA ITER 15MA、$\alpha$ 加热）、`B-04`（METIS 0D 几何）。
★另有一批旧记录（`V-09`..`V-13` 的 Mavrin 非日冕辐射与 Lengyel 两点模型）**落在本册的域树
之外**——它们属于边界/辐射物理，上游在 `FYTOK-SRS-07`，不在 SRS-03/04 的需求树里。
本册不把它们硬塞进某一域：域树覆盖的是这两份 SRS，覆盖不到的就如实说覆盖不到。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`NR-TR-001` · 守恒性** — MUST · 验证方法：测试

> 见 FR-TR-004/010 判据

**`NR-TR-002` · 金标 parity 验证** — MUST · 验证方法：测试

> FUSE.jl / TORAX 金标模块级容差；制造解收敛阶

**`NR-TR-004` · 自包含数值核** — MUST · 验证方法：检查

> 自包含核不 import `spdm` / `fytok`

**`NR-TR-005` · IMAS / DD 一致性** — MUST · 验证方法：测试

> LinkML 校验通过；节点数组契约回归

**`NR-TR-006` · 可微性路线（近期 TODO）** — SHOULD · 验证方法：检查

> AD Jacobian / JAX 设计成文（近期 TODO [TBD]）

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-conservation-fyo-dd-contract`](../../reports/tr-conservation-fyo-dd-contract.md) | 验证 | 成立 | 仓内的 IMAS DD 表（`rust/fylite_runtime/ids/*.tsv`，82 个 IDS、26752 行） | 1.22 | 草稿 | [jsonld](../../records/tr-conservation-fyo-dd-contract.jsonld) |
| [`tr-conservation-time-order`](../../reports/tr-conservation-time-order.md) | 验证 | 成立 | 格式**自称**的阶（θ = 1 一阶 · θ = 0.5 二阶） | 1.21 | 草稿 | [jsonld](../../records/tr-conservation-time-order.jsonld) |

### 覆盖它的记录在别的域

★这几条本域需求由**别处**的记录答了——同一份证据同时回答两条需求时，它只能挂在一个域下。上面的记录表列的是「属于本域的记录」，所以这里点名说清它在哪。

| 需求 | 覆盖它的记录 | 它属于哪一域 |
| :--- | :--- | :--- |
| `NR-TR-001` | [`tr-pedestal-sawtooth-kadomtsev`](../../reports/tr-pedestal-sawtooth-kadomtsev.md) | tr-pedestal |
| `NR-TR-001` | [`tr-sources-power-closure`](../../reports/tr-sources-power-closure.md) | tr-sources |
| `NR-TR-004` | [`eq-forward-self-contained-core`](../../reports/eq-forward-self-contained-core.md) | eq-forward |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
