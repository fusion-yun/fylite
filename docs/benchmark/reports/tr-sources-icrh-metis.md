---
title: "tr-sources-icrh-metis"
---

# ICRH 对 METIS（经 code/icrh 门逐行重跑）：共振层 1.9 %、少数离子四料 ≤ 7.8 %、定常行电子功率 0.955–1.079 与快离子能 0.948–1.015、剖面峰 ≤ 0.05；FWCD 对测量中位 0.979

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-sources-icrh-metis.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [源项：加热与电流驱动](../domains/tr/sources.md)　|　记录正本：`records/tr-sources-icrh-metis.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：ICRH 对 METIS（经 code/icrh 门逐行重跑）：共振层 1.9 %、少数离子四料 ≤ 7.8 %、定常行电子功率 0.955–1.079 与快离子能 0.948–1.015、剖面峰 ≤ 0.05；FWCD 对测量中位 0.979
- **参考**：METIS · FWCD 测量（JFT-2M · DIII-D · Tore-Supra，METIS fitetafwcd.m 所回归的表）
- **验的需求**：`FR-TR-004`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.1　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★第五格（FWCD 对测量）的门仍只在内核仓；前四格已可由公开仓经门重跑。★IC 尚未进 1.5D 源。
:::

## 问的是什么

**被量的**：每一行 METIS 的机器、层处等离子体与天线以设定喂门；FWCD 仍是内核函数级对照

**参考**：METIS（认证库（fydoc CASE-10 metis_cert_hcd.csv），含 ICRH 的行）

> METIS 自己的共振层、少数离子密度与份额、Stix 两能量、电子 / 离子分配与快离子能、剖面

**参考**：FWCD 测量（JFT-2M · DIII-D · Tore-Supra，METIS fitetafwcd.m 所回归的表）

> ★认证库的每一例都 fwcd = 0，判不了 FWCD；判它的是拟合所依据的**测量**——比另一个码更好的判官。

**口径与适用域**：

> METIS 认证库含 ICRH 的行（共振层 40 行全判；四料与剖面判 36 行；电子分配只判上游自己标定常的 16 行）；有纹波的机器按名拒绝（本码无上一时间步可减纹波损失）。FWCD：20 个测量点中 ≥ 0.02 的 18 点。

## 判据与量到多少

:::{figure} ../figures/tr-sources-icrh-metis-headroom.svg
:alt: tr-sources-icrh-metis 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 共振层 R_res 对 METIS 的相对差（每行）；x_res 一格 | 0.03 | measured_band | 经门 36 行：R_res 最劣 1.918e-02、中位 1.493e-03；x_res 最劣 0.0670；谐波 0 处不一致。有纹波的 4 行按名拒绝。（内核函数级另判 40 行，含纹波机器的层：最劣 1.9 %） | **成立** |
| 少数离子四料：n_min · 受热体积份额 · E_crit · tau_s | 0.1 | measured_band | 经门 36 行最劣：n_min 2.145e-02 · 份额 2.462e-02 · E_crit 5.064e-02 · tau_s 7.843e-02 | **成立** |
| 定常行的电子功率与快离子能对 METIS 的比 | 0.15 | measured_band | 经门定常 16 行：p_el 0.9553 – 1.0791、W_fast 0.9480 – 1.0145（两道之和 = 吸收，0e+00）；未定常 20 行（排除）0.0197 – 38.85 倍 | **成立** |
| 剖面：峰位与宽度对 METIS 写下的那条 | 0.05 | measured_band | 经门 36 行：峰位最劣 0.0500（恰一格）、宽度最劣 2.407e-02 | **成立** |
| FWCD 效率对测量的比（测量 ≥ 0.02 的点） | 0.3 | measured_band | 18 点：0.7683 – 1.2439，中位 0.9788 | **成立** |

**`共振层 R_res 对 METIS 的相对差（每行）；x_res 一格`** — ★3 % 是量出来的：去掉 Shafranov 位移或 |B| 的极向项，有行越过 10 %。x_res 在上游自己的 21 点网格上量化，只守一格（0.075）。

**`少数离子四料：n_min · 受热体积份额 · E_crit · tau_s`** — 带分别 3 % · 5 % · 10 % · 10 %；tau_s 带 1/Z²，二次谐波时乘少数离子电荷——漏掉就差四倍。

**`定常行的电子功率与快离子能对 METIS 的比`** — 带 0.85–1.15。★未定常的行必须**排除**：它们散布 0.02–39 倍，本条把这一散布也断言住，免得哪天选择规则把它们放进来。

**`剖面：峰位与宽度对 METIS 写下的那条`** — 峰 ±0.05（一格网格）、宽度 < 5 %。

**`FWCD 效率对测量的比（测量 ≥ 0.02 的点）`** — 带 0.70–1.30、中位离 1 不过 5 %。

**共振层：最劣 1.92 %、中位 0.16 %（40 行）**

- ★内核注释原记「32 行最劣 1.2 %、中位 0.07 %」；2026-09-19 实测表里是 40 行、1.9 % / 0.16 %，注释已照实改——判据没动。

**定常 16 行：p_el 0.955–1.079、W_fast 0.948–1.014**

- ★METIS 的电子道是整段放电上的 ODE，定常态的答案离了平顶就不该对得上——未定常行的千倍散布是**被断言的**，不是被藏的。

**剖面：峰 ≤ 0.05、宽度 2.4 %（36 行）**

- ★峰位 0.05 恰在带上：那是 21 点网格的一格，不是余量耗尽。

**FWCD 对测量：中位 0.979（18 点）**

- ★拟合是对这些测量回归出来的：这一格证「本码的式子就是那个拟合」，不证它外推到 ITER 也对——外推由内核另一道门对 ITER Physics Basis 的陈述守。

## 不可比的部分

- ★★2026-09-19 起 ICRH **有了门**（`code/icrh`），本条的前四格改在公开仓经门逐行重跑——数与内核函数级逐位相同。★仍缺：1.5D 源里没有 IC（`code/evolve` 只沉入 beam 与 lh），IC 进输运只能经 `code/interpretive` 的表。
- ★参考不是真值：METIS 用它自己的峰化形式，本码读真实剖面——剩下的层平均差就在 3–15 % 的带里。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.1　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（新域 tr-sources）：ICRH 的共振层、少数离子、分配、剖面对 METIS，FWCD 对测量——内核仓已有的门登记入册，读数由测试的 [register] 行抄出。 |
| 1.1 | 2026-09-19 | Claude Opus 5 | ★前四格（共振层、少数离子四料、定常分配、剖面）改为公开仓经新门 `code/icrh` 逐行重跑 METIS 认证库（读数 `icrh_metis_door.json`，数与内核函数级逐位相同）；有纹波的 4 行按名拒绝。判据不动。 内核换代（`b27d7145ab3e`：新门 `code/icrh`——ICRH 少数离子加热第一次经门可达，`CASE_CODES` 41 → 42，只加不改）。内核侧：`icrh_door` 2 · `fyo` 7 全过。★没有一处既有缺省数值变动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/icrh_metis_door.json`    `sha256:52b8a38170ae46835371a589cb8d5ba5a7464eb9048817f55a60488dea392cf3`    经门逐行重跑（tools/benchmark-hcd.py icrh）
- `docs/benchmark/readings/hcd_metis_kernel.json`    `sha256:7adbbe36c3c0526570a9fcbbe7dfe55392765b3379ebcd0e51aa4127b657eff8`    内核测试的 [register] 行（tools/benchmark-hcd.py kernel）
- `tools/benchmark-hcd.py`    `sha256:9fbebb10c8e0d65fe11cb0e298b0ab1631996865a0d2979ddd1e39cf62d784eb`    读数生成器（closure · toray · kernel 三个子命令）
- `FYDOC-CASE-10-metis/corpus/metis_cert_hcd.csv`    `sha256:344a7584194c5541da74c7b5089b9ba9db8b17ca5d178f177c95a41c9a20690a`    METIS 认证库（HCD 列），指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_hcd.py::test_icrh_the_door_places_the_layer_where_metis_does` —— 第一格（经门）
- `python/tests/test_benchmark_hcd.py::test_icrh_the_tail_and_the_split_land_in_metis_band` —— 第二、三格（经门）
- `python/tests/test_benchmark_hcd.py::test_icrh_the_profile_peaks_and_spreads_where_metis_wrote_it` —— 第四格（经门）
- `python/tests/test_benchmark_hcd.py::test_icrh_reproduces_its_reading`
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_resonance_layer_is_where_metis_puts_it` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_tail_is_built_from_metis_own_ingredients` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_split_and_the_tail_land_in_metis_band` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_unsettled_rows_are_excluded_because_they_disagree_wildly` —— 第三格的排除
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_profile_shape_reproduces_the_one_metis_wrote` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_fwcd_efficiency_reproduces_the_measurements_it_was_fitted_to` —— 第五格
- `python/tests/test_benchmark_hcd.py::test_hcd_the_kernel_metis_readings_sit_in_the_kernel_bands` —— 公开仓侧：登记的读数落在内核测试的带里

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
