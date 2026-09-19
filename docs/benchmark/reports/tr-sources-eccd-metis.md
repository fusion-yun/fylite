---
title: "tr-sources-eccd-metis"
---

# ECCD 对 METIS 认证库：Giruzzi 拟合复现 METIS 的驱动电流 0.944–1.192（32 行）；伴随 ECCD 在 0.03–0.64、中位 0.35，趋势对数相关 0.976

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-sources-eccd-metis.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [源项：加热与电流驱动](../domains/tr/sources.md)　|　记录正本：`records/tr-sources-eccd-metis.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：ECCD 对 METIS 认证库：Giruzzi 拟合复现 METIS 的驱动电流 0.944–1.192（32 行）；伴随 ECCD 在 0.03–0.64、中位 0.35，趋势对数相关 0.976
- **参考**：METIS
- **验的需求**：`FR-TR-004`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.1　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★门在内核仓：两格的门都是 Rust 单测，本仓 CI 只守登记读数落在带里，不重跑。
:::

## 问的是什么

**被量的**：每行取 METIS 在沉积处给的 T_e · n_e · Z_eff · x · 极向角与 eccdmul × P_EC

**参考**：METIS（认证库（fydoc CASE-10 metis_cert_hcd.csv）：P_EC > 100 kW、I_EC > 0、无 LH 的行）

> ★METIS 的 ECCD 本身就是 Giruzzi 拟合：第一格判的是「本码的拟合是不是 METIS 那个」，第二格判的是「第一性原理的伴随 ECCD 落在 METIS 的哪里」。★带 LH 的行故意排除：METIS 在那些行上乘一个 LH/EC 协同因子，本码不建模它。

**口径与适用域**：

> METIS 认证库中 ECCD 开、无 LH 的行（拟合 32 行、伴随 30 行）；伴随 ECCD 在 Lin-Liu 圆截面 eps = a x / R 的面上、METIS 的极向角处、X2 支、N∥ 0.3。

## 判据与量到多少

:::{figure} ../figures/tr-sources-eccd-metis-headroom.svg
:alt: tr-sources-eccd-metis 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| Giruzzi 拟合对 METIS 驱动电流的比（每行） | 0.25 | measured_band | 32 行，比值 0.9441 – 1.1915 | **成立** |
| 伴随 ECCD 对 METIS 的比：范围、中位与对数相关 | — | measured_band | 30 行：本码 / METIS 最小 0.026 · 中位 0.351 · 最大 0.639；本码 / 拟合 0.027 · 0.341 · 0.677；log I 对 METIS 相关 0.9761、对拟合 0.9728 | **成立** |

**`Giruzzi 拟合对 METIS 驱动电流的比（每行）`** — 带 0.85–1.25；另要求散布不为零（lo < 0.99、hi > 1.01）——若每行都对到 1 %，这个拟合就不再是 METIS 的了。

**`伴随 ECCD 对 METIS 的比：范围、中位与对数相关`** — 带：最小 > 0.015、最大 < 1、中位 0.2–0.6、对 METIS 与对拟合的对数相关都 > 0.9。★这一格判的是**趋势**，不是量值。

**伴随 ECCD：中位 0.35、对数相关 0.976**

- ★★**系统偏低约 3 倍，而且照记**：伴随 ECCD 在 N∥ 0.3 处的相对论共振够不到拟合所保留的那部分电子，拟合（及 METIS）把它算进去了。趋势是同一个（相关 0.976），量值不是。在 TORAY 那一个设计点上本码与 TORAY 差 4.6 %（`tr-sources-ec-toray-cfedr`）——两个第一性原理的码彼此近、都离拟合远，这是本条最该读的一行。
- ★两行（test_regul_q0）在该密度与场下没有 X2 根，跳过、照记。

## 不可比的部分

- ★★**参考不是真值**：METIS 的 ECCD 是拟合式。第一格说本码的拟合就是那个拟合；第二格说第一性原理的伴随 ECCD 与它趋势同、量值低 3 倍——不判谁对。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.1　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（新域 tr-sources）：ECCD 的 Giruzzi 拟合与伴随 ECCD 对 METIS 认证库——内核仓已有的两道门登记入册，读数由测试的 [register] 行抄出。 |
| 1.1 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`b27d7145ab3e`：新门 `code/icrh`——ICRH 少数离子加热第一次经门可达，`CASE_CODES` 41 → 42，只加不改）。内核侧：`icrh_door` 2 · `fyo` 7 全过。★没有一处既有缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/hcd_metis_kernel.json`    `sha256:7adbbe36c3c0526570a9fcbbe7dfe55392765b3379ebcd0e51aa4127b657eff8`    内核测试的 [register] 行（tools/benchmark-hcd.py kernel）
- `tools/benchmark-hcd.py`    `sha256:4ace082c4d14898369f529f7e87a1c2e277a1e1dd1bb629cccd3cb5858bf8d28`    读数生成器（closure · toray · kernel 三个子命令）
- `FYDOC-CASE-10-metis/corpus/metis_cert_hcd.csv`    `sha256:344a7584194c5541da74c7b5089b9ba9db8b17ca5d178f177c95a41c9a20690a`    METIS 认证库（HCD 列），指针 + sha256

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_eccd_efficiency_reproduces_metis_driven_current` —— 第一格（内核仓）
- `$FYLITE_KERNEL/rust/fylite/src/rfray.rs::tests::the_adjoint_eccd_sits_in_the_band_of_metis_and_its_giruzzi_fit` —— 第二格（内核仓）
- `python/tests/test_benchmark_hcd.py::test_hcd_the_kernel_metis_readings_sit_in_the_kernel_bands` —— 公开仓侧：登记的读数落在内核测试的带里

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
