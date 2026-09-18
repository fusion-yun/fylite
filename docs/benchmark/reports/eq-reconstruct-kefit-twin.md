---
title: "eq-reconstruct-kefit-twin"
---

# 孪生合成测量上的 KEFIT：同一个已知真值，另一个码回收得如何

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-reconstruct-kefit-twin.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [测量重构与约束阶梯](../domains/eq/reconstruct.md)　|　记录正本：`records/eq-reconstruct-kefit-twin.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：孪生合成测量上的 KEFIT：同一个已知真值，另一个码回收得如何
- **参考**：孪生真值（同 eq-reconstruct-twin-truth-recovery 的那一个）
- **验的需求**：`FR-EQ-006`
- **跑在内核**：`sha256:8252123281c07bcb…`（新鲜度 **current**）
- **记录版本**：1.5　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：KEFIT 的记录运行，从 fylite 造出的那批合成测量反推

**参考**：孪生真值（同 eq-reconstruct-twin-truth-recovery 的那一个）

> ★两个码打同一个靶，靶是已知的——所以这条对拍读得出方向，不只是「有没有分歧」。

**口径与适用域**：

> EAST #137985 t = 4.041 s 的线圈电流；剖面取解析族 e_mp = e_np = 1；合成测量**不含噪声**。比较落在轮廓内的网格节点上。★两侧打的是同一个真值、用的是同一批合成测量。

## 判据与量到多少

:::{figure} ../figures/eq-reconstruct-kefit-twin-headroom.svg
:alt: eq-reconstruct-kefit-twin 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| KEFIT 重构 psi_N 对真值（轮廓内 RMS） | 0.00681 | measured_band | psi_N RMS 0.00681（max 0.01317）· 轴 1.329 mm · 边界中位 1.563 mm（max 4.16）· X 点 2.186 mm · q0 -0.05022 · q95 -0.01061 | **成立** |
| ★与 fylite 在同一靶上的对照 —— 以及为什么不能读成「fylite 更准」 | — | — | psi_N RMS：fylite 0.002337 vs KEFIT 0.00681（fylite 约优 2.9 倍）；q0：fylite -0.00119 vs KEFIT -0.0502 | **未判（读数）** |
| KEFIT 磁轴对真值 | 1.33 | measured_band | ★**本条没有对应的量** | — |
| KEFIT 边界与 X 点对真值 | 4.17 | measured_band | ★**本条没有对应的量** | — |
| KEFIT q0 / q95 对真值 | 0.0487 | measured_band | ★**本条没有对应的量** | — |

**`KEFIT 磁轴对真值`** — 单位 mm

**`KEFIT 边界与 X 点对真值`** — 单位 mm

**★与 fylite 在同一靶上的对照 —— 以及为什么不能读成「fylite 更准」**

- ★★**fylite 在这张靶上有主场优势，这个数不能当作它更准的证据。** 真值是 **fylite 自己的前向解**造出来的，于是 fylite 的重构与真值**共用同一套离散**，共同误差在相减时抵消；KEFIT 没有这个便利。
- ★要去掉主场优势，得把真值换成第三方造的，或者把判准移到**可观测空间**（正过来预测测量再比）。两件都还没做——所以这一行判 inconclusive，不判谁赢。

## 不可比的部分

- ★★**对拍不是验证**：两套实现吻合不证明谁对——两个错误也能互相抵消。本条给出的是「有没有明显分歧」，不是「正确」。容差因此取**实测带**，不取机器精度。
- ★**参考侧（KEFIT）是归档记录，不在本处重跑**；重算的是真值与比较——所以 fylite 前向解一变，这条记录也会动。
- ★与 `eq-reconstruct-twin-truth-recovery` 同源：那条是验证（对已知真值），本条是对拍（两个码）。拆成两条，是因为它们能声称的东西不同。
- ★同样覆盖不到 `NR-EQ-004`：判准仍在内部量，不在可观测空间。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-18　版本 1.5　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-reconstruct 的对拍记录；与 fylite 的对照判 inconclusive（主场优势） |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:8252123281c07bcbb632c6472624e2282e8f0f87e9922f279567c6876976c122`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/twin_kefit_metrics.json`    `sha256:4b71902608a78a2634dd62d78013b47ba495c0922e7508680b2ca548ed3c8cee`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/twin_east137985.json`    `sha256:c82d0a01347dc692bed8e2f417b8535964f29422aaf252ae3ea6f47ca38c9420`    ★实验类原始读数，指针 + sha256
- `FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_twin_east137985.tar.gz`    `sha256:ea9c108c43a1433e296aa037f3bbc858e0d0d9c53a5e671d7e3a6627314611c4`    KEFIT 的记录运行归档

**守它的门**：

- `python/tests/test_benchmark_equilibrium.py::test_b15_kefit_on_the_twin_measurements_stays_in_its_band`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
