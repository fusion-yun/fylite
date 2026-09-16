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
- **跑在内核**：`sha256:e0e1b16cf0004c12…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-16

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

- 首次入册 2026-09-16　末次修订 2026-09-16　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-forward 的对拍记录；POINT 剖面切片按裁定原样记在带外 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e0e1b16cf0004c128eaaaff81c3d9c36d8a971ce024b2b411c6d7ea5be165ced`

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
