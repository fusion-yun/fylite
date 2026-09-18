---
title: "台基、锯齿与 0D 存量"
---

# 台基、锯齿与 0D 存量

*输运 (Transport) · 本域答：台基高度、锯齿触发与 Kadomtsev 重分布、加料抽气的存量账——守不守得住。*

台基高度、锯齿触发与重分布、加料抽气的 0D 存量账。三件事合一章，因为它们都是**事件
或闭包式的模型**，不是连续求解——它们的判据形状彼此相似，与前面几章不同。

台基的判据是对 EPED 类模型的反馈收敛。★这里有一个容易被忽略的边界：**代理模型有训练箱**。
定 $\chi$ 的燃烧算例会把状态推出 EPED1-NN 的训练范围，而 NN 在箱外不会报错，它会给一个数。
上一册把这条判据挂在 `B-01`（FUSE ITER）上正是为此。**一个不报错的外推是本册最该防的
那类错。**

锯齿的判据是守恒：Kadomtsev 重分布前后含量守恒到 $10^{-12}$，外加 $\psi$ 态的 $q$ 判据。
守恒这一条不需要外部参考，是自证；而且它对"重分布写错了"极其敏感。

0D 存量是第三件：加料、抽气、衰变的账要平。★这一条的上游追溯落在 `FYTOK-SRS-01` 的
`FR-ENG-003`，而 SRS-04 的验证矩阵里**没有给它判据行**——这是上游的缺口，在下面的生成块里
如实标着，等它补。

上一册这一域有 `B-01`（FUSE ITER，台基外推）、`C-09`（ITPA TC33）。已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-TR-009` · 连续台基模型** — MUST · 验证方法：测试

> $\chi_{ped}$ 反馈收敛到 EPED-NN 目标（金标 <4e-15 档 NN 对拍）

**`FR-TR-010` · 锯齿触发与 Kadomtsev 重分布** — MUST · 验证方法：测试

> 混合前后含量守恒 1e-12；$\psi$-态 $q$ 判据

**`FR-TR-014` · 0D 存量守恒（加料 / 抽气 / 衰变）** — MUST

> ★`FYTOK-SRS-04` 的〈验证矩阵〉**没有这一条的判据行**。上游追溯写的是「`FYTOK-SRS-01` **FR-ENG-003**（加料 / 抽气与存量守恒，在内档）」。没有判据就无从验起——这是上游的缺口，记在这里等它补。

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-pedestal-sawtooth-kadomtsev`](../../reports/tr-pedestal-sawtooth-kadomtsev.md) | 验证 | 成立 | 它自己混合前的含量积分，以及 Kadomtsev 重联要求的 q = 1 | 1.10 | 草稿 | [jsonld](../../records/tr-pedestal-sawtooth-kadomtsev.jsonld) |
| [`tr-pedestal-zerod-bookkeeping-metis`](../../reports/tr-pedestal-zerod-bookkeeping-metis.md) | 对拍 | 不成立 | METIS | 1.13 | 草稿 | [jsonld](../../records/tr-pedestal-zerod-bookkeeping-metis.jsonld) |

### 覆盖它的记录在别的域

★这几条本域需求由**别处**的记录答了——同一份证据同时回答两条需求时，它只能挂在一个域下。上面的记录表列的是「属于本域的记录」，所以这里点名说清它在哪。

| 需求 | 覆盖它的记录 | 它属于哪一域 |
| :--- | :--- | :--- |
| `FR-TR-009` | [`tr-closure-15d-source-switches`](../../reports/tr-closure-15d-source-switches.md) | tr-closure |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
