---
title: "eq-inverse-core-field-recovery"
---

# 静态逆解的线性核：已知电流合成的场精确回收——约束行上 6e-14、未参与拟合的点上 1e-13

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-inverse-core-field-recovery.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [静态逆解：形状到线圈电流](../domains/eq/inverse.md)　|　记录正本：`records/eq-inverse-core-field-recovery.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：静态逆解的线性核：已知电流合成的场精确回收——约束行上 6e-14、未参与拟合的点上 1e-13
- **参考**：已知电流（孪生真值）
- **验的需求**：`FR-EQ-005`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★门在内核仓：本条唯一的门是 Rust 单测，本仓 CI 跑不到它（与 `tr-pedestal-sawtooth-kadomtsev` 同一处代价）。
:::

## 问的是什么

**被量的**：`breakdown::channel_field`（响应行）+ `linalg::ridge_lstsq`（解），λ = 0

**参考**：已知电流（孪生真值）

> ★抄录判据「已知电流合成场精确回收 rtol 1e-6」：参照是合成场用的那组电流本身。

**口径与适用域**：

> ITER 型 12 件 11 路线圈，ITER 型 D 形边界（R₀ 6.2、a 2、κ 1.8、δ 0.4）+ 下 X 点，已知电流为 ITER 量级两种符号。★判的是线性核（响应行 + 解），不是外层的退火设计策略——后者见 `eq-inverse-iter-reference-separatrix` 与 `eq-inverse-freegsnke-east137985`。

## 判据与量到多少

:::{figure} ../figures/eq-inverse-core-field-recovery-headroom.svg
:alt: eq-inverse-core-field-recovery 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 约束行上回收的场对合成场 | 1e-06 | reference_self_reported | 24 个边界点的 ψ + X 点的 B_R · B_Z（乘 R₀ 成通量单位），11 路（12 件，CS1 上下两半同一路）：5.7e-14 | **成立** |
| 十六个未参与拟合的点上回收的场 | 1e-06 | reference_self_reported | D 形内外两圈共 16 点：1.5e-13；电流 3.2e-12（读数，不判） | **成立** |

**`约束行上回收的场对合成场`** — ★抄录原文 rtol 1e-6。

**`十六个未参与拟合的点上回收的场`** — ★防假通过：只在拟合用的行上对上，可能只是把残差塞进了零空间；场在没见过的点上也对，才是场被回收了。

**未见点 1.5e-13；电流本身 3.2e-12**

- ★判的是**场**不是电流：本组 24 点 + 1 零点超定 11 路，所以电流也回来了；只拿形状或磁测时它们不必回来（零空间，见 `eq-inverse-freegsnke-east137985`）。
- ★线圈是 DINA 的 ITER 那一套（位置、尺寸、匝数取自其 tokamak_config），嵌在测试里——本仓的装置卡不入版本库，内核测试不能依赖它。

## 不可比的部分

- ★本条补的是 FR-EQ-005 抄录判据本身——此前册里的两条记录判的都是设计（退火、额定、目标形状），没有一条判「已知电流合成场的回收」。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（/goal「close FR-EQ-001/005」）：FR-EQ-005 抄录判据——已知电流合成场经静态逆解的线性核精确回收。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/inverse_core_field_recovery.json`    `sha256:1895604b6b541d7675c6e0529fac20e3fd169be6d65af60b9a621c81c076df4b`    内核测试 --nocapture 报出的三个数

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/case.rs::static_inverse_core_tests::the_static_inverse_core_recovers_a_field_synthesised_from_known_currents` —— ★两格：约束行与未见点都 < 1e-6

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
