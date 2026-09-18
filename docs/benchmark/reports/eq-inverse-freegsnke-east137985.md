---
title: "eq-inverse-freegsnke-east137985"
---

# 静态逆解对 FreeGSNKE：电流差了 70 倍，平衡却在毫米之内——逆问题的零空间

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-inverse-freegsnke-east137985.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [静态逆解：形状到线圈电流](../domains/eq/inverse.md)　|　记录正本：`records/eq-inverse-freegsnke-east137985.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：静态逆解对 FreeGSNKE：电流差了 70 倍，平衡却在毫米之内——逆问题的零空间
- **参考**：FreeGSNKE
- **验的需求**：`FR-EQ-005`
- **跑在内核**：`sha256:e15d03f542fa89ea…`（新鲜度 **current**）
- **记录版本**：1.6　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/inverse_shape，EAST 牌，退火**按供电额定逐路设限**

**参考**：FreeGSNKE（FreeGSNKE recorded inverse solve (CASE-23 freegsnke_vstab_east137985.tar.gz) on KEFIT's boundary）

> 参考是 FreeGSNKE 的记录逆解，目标同为 KEFIT 的边界；本处不重跑。

**口径与适用域**：

> EAST #137985 t = 4.041 s；目标是 KEFIT 的边界（g 文件 sha256 299c8746c1cc9758…），Ip = 392708.7 A，目标点 69 个；公平窗 z ∈ [-0.725559041, 0.63833942]、x 排除 0.1 m（两码只在同一段边界上比）。十二路线圈电路。★剖面取交付的 p'/FF' 表，beta0/emp/enp 在本条里是惰性的。

## 判据与量到多少

:::{figure} ../figures/eq-inverse-freegsnke-east137985-headroom.svg
:alt: eq-inverse-freegsnke-east137985 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 设计边界对目标（KEFIT 边界）的逐点距离 | 1.22 | measured_band | fylite 中位 1.211 mm（p95 3.873 · max 9.422，2025/2172 点）；FreeGSNKE 中位 5.002 mm（p95 27.38 · max 52.89，2074/2460 点） | **成立** |
| ★三组电流各自正解后，平衡之间的散布 | 0.005 | measured_band | 电流 RMS 之差：fylite↔KEFIT 25.56 kA·t · FreeGSNKE↔KEFIT 0.369 kA·t · fylite↔FreeGSNKE 25.56 kA·t（逐路最大 61.62）；而三组电流**各自正解**后对 KEFIT 的图：psi_N RMS 0.007364 / 0.00953 / 0.004619，散布仅 0.00491 | **成立** |
| 设计的收敛状态 | — | — | converged = 0 · settled = 1 · 残差 0.00167 · 62 次迭代 / 8 轮 · 触限路数 0 | **未判（读数）** |
| 两码电流之差必须**显著大于**噪声 | 5 | measured_band | ★**本条没有对应的量** | — |

**`设计边界对目标（KEFIT 边界）的逐点距离`** — 单位 mm；中位

**`★三组电流各自正解后，平衡之间的散布`** — ★★**本条记录存在的理由就是这一条判据。** 形状只把线圈电流约束到设计的零空间为止；要判「两个码是否一致」，不能看电流，要看**电流产生的平衡**。

**`两码电流之差必须**显著大于**噪声`** — ★这是一条**下限**判据：差一旦塌成噪声，说明零空间这件事没被演示出来，本条读数即失效。

**边界对目标：fylite 比 FreeGSNKE 近约 4.1 倍**

- ★★**「更近」不等于「更对」。** 逆问题是病态的：贴目标贴得更紧，也可能只是正则化更弱。要判对错，看下一条（零空间）。

**★★零空间：电流差得远，平衡对得上**

- ★★**这是本条最要紧的一行。** FreeGSNKE 基本复现了 KEFIT 的电流（0.369 kA·t），fylite 找到的是**另一组**（离 KEFIT 25.6 kA·t，约 69 倍远）——然而三组电流正解出来的平衡彼此在毫米量级内。**差落在零空间里，不是谁算错了。**
- ★**由此可知：拿电流逐路比对来判两个逆解码是否一致，是错的判法。** 这一域的比较必须落在电流**产生的平衡**上。
- ★fylite 那一组正解后离 KEFIT 的图最近（0.004619），但**这里 fylite 的前向解在回路里**——用自己的前向解评自己的逆解，这一档有偏，不能当作独立证据。

**设计的收敛状态**

- ★与 ITER 那条（`eq-inverse-iter-reference-separatrix`）同样是 settled 而非 converged——**这是本域一个跨算例的共性，不是单个算例的偶然**。
- ★但与 ITER 那条不同：**本条的退火是按供电额定逐路设限跑的**（触限 0 路），所以「买不起」那个问题在这里不存在。EAST 牌有额定，ITER 牌没有。

## 不可比的部分

- ★★**对拍不是验证**：两套实现吻合不证明谁对——两个错误也能互相抵消。本条给出的是「有没有明显分歧」，不是「正确」。容差因此取**实测带**，不取机器精度。
- ★**参考侧不在本处重跑**：它是 sha256 索引的归档记录。本处重算的只有 fylite 侧与比较本身，所以 fylite 前向解一变，这条记录会跟着动。
- ★★**本条的结论不是「fylite 比 FreeGSNKE 好」**，是「形状定不住电流」。任何把这条记录读成排名的用法都是误读。
- ★**正则化没有对齐**：两个码各有各的正则项与自由度处理，而正则项一变，「答案」就成了「这个码在这个正则下的答案」。两侧的设置记在各自的归档里。
- ★**目标边界本身来自 KEFIT**，所以 KEFIT 在这道题上天然占先（它是出题人）。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-18　版本 1.6　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-inverse 的对拍记录；零空间是本条存在的理由 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e15d03f542fa89ea3650ab02d199238a0f9d528b2c2b4df0cbe86b70070203dd`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/inverse_shape_freegsnke_metrics.json`    `sha256:8ae78e46d230b38047f5d89b6ab38ea85bffc6e49c100eaa4ff62a59ed225fed`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/inverse_shape_east137985.json`    `sha256:81dacc7ebe0d070a2881816fbec6ea9b8a066c1e240d13b5c8484b18c70c2333`    ★实验类原始读数，指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_inverse_shape.py::test_b21_the_designed_boundary_stays_in_the_band`
- `python/tests/test_benchmark_inverse_shape.py::test_b21_the_currents_differ_far_more_than_the_equilibria`
- `python/tests/test_benchmark_inverse_shape.py::test_b21_the_design_reproduces_its_recorded_readings`
- `python/tests/test_benchmark_inverse_shape.py::test_b21_the_target_curve_limits_are_recorded`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
