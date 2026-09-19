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
- **跑在内核**：`fylite_kernel@94ca1a29d6ed`（新鲜度 **current**）
- **记录版本**：1.21　**评审**：草稿　**日期**：2026-09-16

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

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.21　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：两种边界规则对 KEFIT 的读数，不判谁对 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核同日两次换代后的全册重验（原 1.1 与 1.2 两条，2026-09-18 合并——第二条当时误抄了第一条的摘要）：①`301a962b` → `ac8c0f5c`，`FR-EQ-002/008/010/011` 与 0D 三项入内核（内核仓 `3ea79df`），fylite 侧 110 道、内核侧 656 项全通过；②`ac8c0f5c` → `eb8c9022`，ETS 五型边界、燃烧→密度的接线、时间收敛阶入内核（内核仓 `acd1628`），165 道门禁全过、660 项既有内核测试一项没动。★两次本条的判据与数值都**未改口径**。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 合并重复的变更条目：1.1 与 1.2 是同日两次内核换代，第二条误抄了第一条的摘要；合并成一条（沿用 1.2），两次换代各自写明。★本条的判据与数值未动。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.17 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@94ca1a29d6ed`（库 `sha256:d7bb2708e0594700521df0703ab6345fcb232511e39b652ff061c0ecd69d4119`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/forward_edge_rule_metrics.json`    `sha256:f7be7c606e3212d3371558a631e97fedb157bde868b668164b4712922aa9558e`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/evolve_free_boundary_east137985.json`    `sha256:3ed068ab61d9d59ec67ad727513015301f471fa440e8be9656d5584e4d44fe1a`    ★实验类原始读数，指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_the_forward_edge_rule_is_a_reading_not_a_band`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
