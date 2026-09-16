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
- **跑在内核**：`sha256:e0e1b16cf0004c12…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/fixed_boundary，129x129 网格，经 tools/benchmark-fixed-boundary.py east

**参考**：CHEASE（NS = NT = 80（归档记录，sha256 sha256:f8088bd7bd1d…））

> ★CHEASE 是定边界高精度重解的常用参照；两侧解的是**同一道题**（同一条边界、同一对 p'/FF' 表）。

**口径与适用域**：

> KEFIT raw-tree 运行的 g 文件（sha256 299c8746c1cc9758…），取住 psi_N = 0.995 的面；r0 = 1.75 m · f_edge = 4.501726288 T·m · 面内 Ip = 393379.2 A · 剖面 101 点 · 射线 360 条。★两侧同一条边界、同一对 p'/FF' 表；比较落在面内 17945 个点上。

## 判据与量到多少

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| psi_N 两码之差（面内 RMS / max） | 4.92e-05 | measured_band | RMS 4.92e-05 · max 0.0002655 | **成立** |
| q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS / max）与 q95 | 0.00105 | measured_band | q[0.1,0.9] RMS 0.001043 · max 0.001821 · q95 0.001855 · q0 7.446e-05 | **成立** |
| 磁轴、环向磁通跨度与 Ip | 0.000968 | measured_band | 轴 0.004677 mm · 跨度 -0.0007535 · Ip -0.0009679 | **成立** |
| 网格依赖：65² 那一档 | — | — | 65² 对同一 CHEASE：psi_N RMS 7.192e-05 · q[0.1,0.9] RMS 0.001598 · q0 -0.007675 | **未判（读数）** |

**`q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS / max）与 q95`** — ★**这一条才是本域的主判据**：磁面量与 q 剖面是下游真正用掉的东西。

**q 剖面与 q95**

- ★★**注意 q0：这里两码只差 7.45e-05**，而同一个 q0 在 Solov'ev 解析题上对闭式解差 3.27e-03（见 eq-forward-solovev-fixed-boundary，那条判 fail）。两个数不矛盾——**这里比的是两码，那里比的是真值**，而两码可以一起偏。★所以这条对拍**不能**用来宽慰那条验证：它证明不了 q0 算对了。

**网格依赖：65² 那一档**

- ★记下来而不判：加密到 129² 后 q0 从 -0.00768 改善到 7.45e-05，说明这一档的差里有一部分是**本侧的离散**，不全是两码的模型差。★只报一个网格上的数，看不出这件事。

## 不可比的部分

- ★★**对拍不是验证**：两套实现吻合不证明谁对——两个错误也能互相抵消。本条给出的是「有没有明显分歧」，不是「正确」。容差因此取**实测带**，不取机器精度。
- ★**CHEASE 的 NS/NT 是它的收敛旋钮**：换一档，这里每个数都会变。带是「在 NS=NT=80 这一档上实测的」，不是 CHEASE 的固有精度。
- ★**边界与剖面都是喂进去的**（来自 KEFIT 的 g 文件）。算出来的是面内的 psi 与由它导出的 q 与磁面量。
- ★本条**不覆盖** `FR-EQ-012` 的 q 锁定重解那一档，也不覆盖 gm 目录的九项定义核验——那两件本仓没有门，见本域缺口栏。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-16　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-surface 的第一条记录（此前该域为空）；对 CHEASE 的定边界重解对拍 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e0e1b16cf0004c128eaaaff81c3d9c36d8a971ce024b2b411c6d7ea5be165ced`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/fixed_boundary_chease_east_metrics.json`    `sha256:e0bb37c2c317c3501f37245494d3a38e0f102ccd90fdd2962e6c5827f6dfce85`
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/fixed_boundary_east137985.json`    `sha256:1c1dca4624223e6d4064f742cfd2763c27a331b20b3d5ba57bbac0b702640b2d`    ★实验类原始读数，指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_fixed_boundary.py::test_b16_fylite_reproduces_its_readings_and_stays_in_the_band_against_chease`
- `python/tests/test_benchmark_fixed_boundary.py::test_b16_kefit_context_is_a_reading`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
