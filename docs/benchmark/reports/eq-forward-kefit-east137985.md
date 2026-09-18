---
title: "eq-forward-kefit-east137985"
---

# 前向解对 KEFIT：EAST #137985 的三个纯磁测切片，外加一个落在带外的 POINT 剖面切片

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-kefit-east137985.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-kefit-east137985.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：前向解对 KEFIT：EAST #137985 的三个纯磁测切片，外加一个落在带外的 POINT 剖面切片
- **参考**：KEFIT
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`sha256:a7a86a75fc27ac15…`（新鲜度 **current**）
- **记录版本**：1.16　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/forward，经 tools/benchmark-equilibrium.py forward-kefit

**参考**：KEFIT（KEFIT raw-tree runs (CASE-23 kefit_raw_east137985.tar.gz, variant rejected)）

> 参考是 KEFIT 的**记录运行**（归档 sha256 sha256:001d33a06fdc），本处不重跑。…

**口径与适用域**：

> EAST #137985，四个时刻切片（t = 4.041 / 4.944 / 5.976 s）。前三片为**纯磁测**约束，第四片带 POINT 剖面。比较落在 KEFIT 边界之内的 814 个网格节点上；psi_N 为归一极向磁通。★双方在同一 COCOS 与同一 psi 口径下比较（见 eq-convention 那条记录）。

## 判据与量到多少

:::{figure} ../figures/eq-forward-kefit-east137985-headroom.svg
:alt: eq-forward-kefit-east137985 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| psi_N 对 KEFIT 的偏差（轮廓内 RMS），三个纯磁测切片取最劣 | 0.00737 | measured_band | t4041_mag psi_N RMS 0.007364（max 0.01801） · t4944_mag psi_N RMS 0.006545（max 0.0157） · t5976_mag psi_N RMS 0.006637（max 0.01518）；最劣 0.007364，判据 0.00737 | **成立** |
| 磁轴位置 | 4.87 | measured_band | t4041_mag 轴 4.11 mm、边界中位 3.42 mm、X 点 4.31 mm · t4944_mag 轴 4.02 mm、边界中位 2.67 mm、X 点 6.03 mm · t5976_mag 轴 4.87 mm、边界中位 2.74 mm、X 点 6.5 mm | **成立** |
| POINT 剖面切片必须**记在带外** | 0.00737 | measured_band | psi_N RMS 0.02212（纯磁测带 0.00737 的 3.0 倍）· 轴 9.17 mm · 边界中位 5.48 mm · X 点 14.6 mm · **settled = 0** | **成立** |
| 边界与 X 点位置 | 15.5 | measured_band | ★**本条没有对应的量** | — |

**`磁轴位置`** — 单位 mm

**`边界与 X 点位置`** — 单位 mm；中位与最大分开记

**`POINT 剖面切片必须**记在带外**`** — ★★这一条是**反向判据**：它要求那个切片 psi_N 偏差**大于**纯磁测的带。把它塞进带里才是错——那等于假装约束条件不影响结果。

**三个纯磁测切片**

- ★三个切片都 settled；带按最劣者定，不按平均——平均会把最差的那一片藏起来。

**★POINT 剖面切片 `t5976_primary` —— 记在带外的那一片**

- ★★**这一片故意留在带外，而且它的 `settled = 0`——它根本没停稳。** 换了约束条件（带 POINT 剖面而不是只有磁测），解就到了另一处，且不再收敛。
- ★**把它并进上面的带是错的**：那等于宣称约束条件不影响答案。登记册宁可让它露着，也不让一条带把两种问题糊成一个数。
- ★2026-09-16 用户裁定「保留负面结果」：本片原样留册。

## 不可比的部分

- ★★**对拍不是验证**：两套实现吻合不证明谁对——两个错误也能互相抵消。本条给出的是「有没有明显分歧」，不是「正确」。容差因此取**实测带**，不取机器精度。
- ★**参考侧不在本处重跑**：它是 sha256 索引的归档记录。本处重算的只有 fylite 侧与比较本身，所以 fylite 前向解一变，这条记录会跟着动。
- ★**哪些量是喂进去的**：线圈电流、Ip、磁测量，双方用的是同一批。算出来的是 psi 分布与由它导出的几何量。
- ★**KEFIT 侧取自 raw-tree 运行的 `rejected` 变体**（见 reference 字段）：这是那一批里与本比较口径一致的一支，不是 KEFIT 的「最佳答案」。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-18　版本 1.16　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-forward 的对拍记录；POINT 剖面切片按裁定原样记在带外 |
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

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:a7a86a75fc27ac155dcfb3ed1c1d752729aef8fea9573a9218444ae2c442b4a0`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/forward_kefit_metrics.json`    `sha256:fc8187c587c2e219004ddc7446abd97a2e151b48c369e01b42b6ddee6f2f6957`    本条的派生指标
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/forward_kefit_east137985.json`    `sha256:a54852d884c396b77b050f387334a8bae29a942965b3d5750b32e2bb23e31f1c`    ★原始读数为实验类，留在 fydoc 算例库，公开册只记指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_equilibrium.py::test_b14_the_forward_solve_stays_in_the_band_on_kefits_magnetics_answers`
- `python/tests/test_benchmark_equilibrium.py::test_b14_the_forward_solve_reproduces_its_recorded_readings`
- `python/tests/test_benchmark_equilibrium.py::test_b14_the_point_profile_slice_is_recorded_outside_the_band`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
