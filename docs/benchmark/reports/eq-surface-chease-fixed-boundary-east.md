---
title: "eq-surface-chease-fixed-boundary-east"
---

# KEFIT 的 psi_N = 0.995 面上重解：磁面量与 q 剖面对 CHEASE

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-surface-chease-fixed-boundary-east.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [磁面几何、全局量与形状表示](../domains/eq/surface.md)　|　记录正本：`records/eq-surface-chease-fixed-boundary-east.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：KEFIT 的 psi_N = 0.995 面上重解：磁面量与 q 剖面对 CHEASE
- **参考**：CHEASE
- **验的需求**：`FR-EQ-003` · `FR-EQ-012`
- **跑在内核**：`sha256:e16301fa3acd72ca…`（新鲜度 **current**）
- **记录版本**：1.15　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/fixed_boundary，129x129 网格，经 tools/benchmark-fixed-boundary.py east

**参考**：CHEASE（NS = NT = 80（归档记录，sha256 sha256:f8088bd7bd1d…））

> ★CHEASE 是定边界高精度重解的常用参照；两侧解的是**同一道题**（同一条边界、同一对 p'/FF' 表）。

**口径与适用域**：

> KEFIT raw-tree 运行的 g 文件（sha256 299c8746c1cc9758…），取住 psi_N = 0.995 的面；r0 = 1.75 m · f_edge = 4.501726288 T·m · 面内 Ip = 393379.2 A · 剖面 101 点 · 射线 360 条。★两侧同一条边界、同一对 p'/FF' 表；比较落在面内 17945 个点上。

## 判据与量到多少

:::{figure} ../figures/eq-surface-chease-fixed-boundary-east-contours.svg
:alt: eq-surface-chease-fixed-boundary-east 的等高线对照图
:width: 100%

两侧的 psi_N 等高线画在一起（R-Z 等比例）。★曲线在线宽内重合——**这就是结果**，不是画漏了；定量见下。
:::

:::{figure} ../figures/eq-surface-chease-fixed-boundary-east-qprofile.svg
:alt: eq-surface-chease-fixed-boundary-east 的q 剖面对照图
:width: 100%

上格是两个码各自的 q 剖面，下格是它们的相对差。★**差异在上格看不出来，在下格才看得见**——这正是只给一个 RMS 说不清的那部分。
:::

:::{figure} ../figures/eq-surface-chease-fixed-boundary-east-headroom.svg
:alt: eq-surface-chease-fixed-boundary-east 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| psi_N 两码之差（面内 RMS / max） | 4.92e-05 | measured_band | RMS 4.92e-05 · max 0.0002655 | **成立** |
| q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS / max）与 q95 | 0.00105 | measured_band | q[0.1,0.9] RMS 0.001043 · max 0.001821 · q95 0.001855 · q0 0.001895 | **成立** |
| 磁轴、环向磁通跨度与 Ip | 0.000968 | measured_band | 轴 0.004677 mm · 跨度 -0.0007535 · Ip -0.0009679 | **成立** |
| 网格依赖：65² 那一档 | — | — | 65² 对同一 CHEASE：psi_N RMS 7.192e-05 · q[0.1,0.9] RMS 0.001598 · q0 0.004758 | **未判（读数）** |
| ★★q0 与 CHEASE 的分歧**变大了**——而这未必是退步 | — | — | 内核把 q0 改为轴上解析极限之后（内核仓 d13376b）：本条 q0 对 CHEASE 从 +7.45e-05 变到 +1.89e-03（大 25 倍）；同时 q0 对 KEFIT 从 −1.16e-03 变到 +6.59e-04（小了），而 65² 与 129² 两档之间的自洽从 −7.75e-03 变到 +2.86e-03（也小了） | **未判（读数）** |

**`q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS / max）与 q95`** — ★**这一条才是本域的主判据**：磁面量与 q 剖面是下游真正用掉的东西。

**q 剖面与 q95**

- ★★**注意 q0：这里两码只差 0.00189**，而同一个 q0 在 Solov'ev 解析题上对闭式解差 3.27e-03（见 eq-forward-solovev-fixed-boundary，那条判 fail）。两个数不矛盾——**这里比的是两码，那里比的是真值**，而两码可以一起偏。★所以这条对拍**不能**用来宽慰那条验证：它证明不了 q0 算对了。

**网格依赖：65² 那一档**

- ★记下来而不判：加密到 129² 后 q0 从 0.00476 改善到 0.00189，说明这一档的差里有一部分是**本侧的离散**，不全是两码的模型差。★只报一个网格上的数，看不出这件事。

**★★q0 与 CHEASE 的分歧**变大了**——而这未必是退步**

- ★★**这道题没有真值，所以「离 CHEASE 远了」说明不了谁退步。** 在有解析真值的那道题上（`eq-forward-solovev-fixed-boundary`）新法是明确更准的：−3.26e-03 → −1.97e-05，而 CHEASE 在那道题上对解析解只差 3.56e-06。
- ★于是两种读法都还活着：**其一**，此前 7.45e-05 的一致是两个码在这道带形变的面上犯了**同一个**错（旧法也是某种外推，CHEASE 的 q0 取法未核）；**其二**，新法在强形变面上确实不如在 Solov'ev 上准。**本条判不了，两种都记着。**
- ★**能支持第一种读法的旁证**：新法的网格自洽变好了（两档之差 7.75e-03 → 2.86e-03），对 KEFIT 也变近了。一个更差的算法很难同时改善这两项。
- ★要判它，得在这个形状上拿到一个独立真值——例如同一条边界上的制造解。本域尚无。

## 不可比的部分

- ★★**对拍不是验证**：两套实现吻合不证明谁对——两个错误也能互相抵消。本条给出的是「有没有明显分歧」，不是「正确」。容差因此取**实测带**，不取机器精度。
- ★**CHEASE 的 NS/NT 是它的收敛旋钮**：换一档，这里每个数都会变。带是「在 NS=NT=80 这一档上实测的」，不是 CHEASE 的固有精度。
- ★**边界与剖面都是喂进去的**（来自 KEFIT 的 g 文件）。算出来的是面内的 psi 与由它导出的 q 与磁面量。
- ★本条**不覆盖** `FR-EQ-012` 的 q 锁定重解那一档，也不覆盖 gm 目录的九项定义核验——那两件本仓没有门，见本域缺口栏。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-18　版本 1.15　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-surface 的第一条记录（此前该域为空）；对 CHEASE 的定边界重解对拍 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核 q0 改为轴上解析极限后重验：判据各档仍在带内；新增一条发现——q0 对 CHEASE 的分歧变大 25 倍，而对 KEFIT 与网格自洽反而变好，本条判不了，两种读法都记着。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核同日两次换代后的全册重验（原 1.2 与 1.3 两条，2026-09-18 合并——第二条当时误抄了第一条的摘要）：①`301a962b` → `ac8c0f5c`，`FR-EQ-002/008/010/011` 与 0D 三项入内核（内核仓 `3ea79df`），fylite 侧 110 道、内核侧 656 项全通过；②`ac8c0f5c` → `eb8c9022`，ETS 五型边界、燃烧→密度的接线、时间收敛阶入内核（内核仓 `acd1628`），165 道门禁全过、660 项既有内核测试一项没动。★两次本条的判据与数值都**未改口径**。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.5 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 合并重复的变更条目：1.2 与 1.3 是同日两次内核换代，第二条误抄了第一条的摘要；合并成一条（沿用 1.3），两次换代各自写明。★本条的判据与数值未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e16301fa3acd72ca3bbe19c05775bbc2c4d78fd9e7b5b693f9b8756ce6d8669b`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/fixed_boundary_chease_east_metrics.json`    `sha256:52cedf86f64897bea7d902b150528cea672539316a04e0417c782bafd3e4f867`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/fixed_boundary_east137985.json`    `sha256:b9c0eac5c5ff518a22a5b5c8d224547857114f8d913bf4ddc93f240c0efcc745`    ★实验类原始读数，指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_fixed_boundary.py::test_b16_fylite_reproduces_its_readings_and_stays_in_the_band_against_chease`
- `python/tests/test_benchmark_fixed_boundary.py::test_b16_kefit_context_is_a_reading`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
