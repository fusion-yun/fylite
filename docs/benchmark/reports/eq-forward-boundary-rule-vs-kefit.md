---
title: "eq-forward-boundary-rule-vs-kefit"
---

# 两种边界规则对 KEFIT 的图：收敛的那一条反而更远

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-boundary-rule-vs-kefit.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-boundary-rule-vs-kefit.jsonld`*

## 摘要

- **类**：对拍　**判决**：**未判（读数）**
- **量的是**：两种边界规则对 KEFIT 的图：收敛的那一条反而更远
- **参考**：KEFIT
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`sha256:e0e1b16cf0004c12…`（新鲜度 **stale**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-16

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-16 记名读数（非缺陷但未定）：edge 规则收敛而离 KEFIT 更远，node 规则不收敛却更近；两者差在虚拟对是否带电流。判它需要独立于两者的真值，这道题上没有。用户裁定「保留负面结果」，本条以 inconclusive 原样留册。
:::

## 问的是什么

**被量的**：同一道前向题的**两种边界规则**：node（节点规则，带虚拟对）与 edge（边规则）

**参考**：KEFIT

> KEFIT 的记录运行（同 eq-forward-kefit-east137985 的那一批），本处不重跑。

**口径与适用域**：

> EAST #137985 四个切片（t = 4.041 / 4.944 / 5.976 s，末片带 POINT 剖面）。两种规则跑在同一批输入、同一台机器、同一内核上，只差边界条件的提法。★比较落在 KEFIT 边界之内的网格节点上。

## 判据与量到多少

:::{figure} ../figures/eq-forward-boundary-rule-vs-kefit-headroom.svg
:alt: eq-forward-boundary-rule-vs-kefit 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 两种规则各自对 KEFIT 的 psi_N 偏差，以及各自的收敛状态 | 0 | measured_band | node：psi_N RMS 0.007364 · 轴 4.11 mm · 虚拟对 10525.4 A · **converged = 0 / settled = 1**（残差 0.00291，62 次，0.2 s）；edge：psi_N RMS 0.01834 · 轴 9.24 mm · 虚拟对 34.1 A · **converged = 1 / settled = 0**（残差 9.77e-10，5664 次，14.1 s） | **未判（读数）** |
| 四个切片的全貌 | — | — | t4041_mag：node 0.007364 / edge 0.01834 · t4944_mag：node 0.006545 / edge 0.02265 · t5976_mag：node 0.006637 / edge 0.02363 · t5976_primary：node 0.02212 / edge 0.02861 | **未判（读数）** |

**`两种规则各自对 KEFIT 的 psi_N 偏差，以及各自的收敛状态`** — ★★**本条没有带，是一条读数。** 两种规则解的是同一道题的两种提法，谁离 KEFIT 近不等于谁对——KEFIT 自己也只是一次运行。给它画一条带，等于替这个选择预先判了案。

**★t4041_mag：收敛的那条更远**

- ★★**这正是本条存在的理由**：edge 规则**真收敛了**（残差 9.77e-10），而它离 KEFIT 的图比**没收敛**的 node 规则远 2.5 倍。
- ★差别在那个虚拟对上：node 规则让它带着约 10.5 kA，edge 规则把它削到几十安培。**B-14 的读数是靠那对电流撑起来的平衡**——所以 B-14 与本条要一起读。
- ★**不判谁对。** 判它需要一个独立于两者的真值，而这道题上没有。若哪天 edge 规则不再收敛、或 node 规则开始收敛，本读数即失效。
- ★代价也记上：edge 规则用了 5664 次迭代 / 14.1 s，node 规则 62 次 / 0.2 s。

**四个切片的全貌**

- ★四片同向：node 规则都更靠近 KEFIT。**一致的方向说明这不是某一片的偶然**，是两种提法的系统差。

## 不可比的部分

- ★★**对拍不是验证**：两套提法与 KEFIT 的差，说明不了谁对——三方都可能偏。
- ★**本条不给带、不给判决**，它是一条读数（登记册允许这样：`overall_verdict = inconclusive`）。把一个未定的选择写成一条「通过」的记录，比不记更坏。
- ★参考侧（KEFIT）是归档记录，不在本处重跑。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-16　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：两种边界规则对 KEFIT 的读数，不判谁对 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e0e1b16cf0004c128eaaaff81c3d9c36d8a971ce024b2b411c6d7ea5be165ced`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/forward_edge_rule_metrics.json`    `sha256:f7be7c606e3212d3371558a631e97fedb157bde868b668164b4712922aa9558e`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/evolve_free_boundary_east137985.json`    `sha256:3ed068ab61d9d59ec67ad727513015301f471fa440e8be9656d5584e4d44fe1a`    ★实验类原始读数，指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_the_forward_edge_rule_is_a_reading_not_a_band`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
