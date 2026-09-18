---
title: "eq-surface-mxh-gfile-fit"
---

# MXH 边界拟合：**残差不是散开的，它堆在 X 点上**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-surface-mxh-gfile-fit.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [磁面几何、全局量与形状表示](../domains/eq/surface.md)　|　记录正本：`records/eq-surface-mxh-gfile-fit.jsonld`*

## 摘要

- **类**：验证　**判决**：**未判（读数）**
- **量的是**：MXH 边界拟合：**残差不是散开的，它堆在 X 点上**
- **参考**：闭式 —— 圆的精确退化与一个已知 MXH 形的原样回收 · 本机拿得到的 g-file 边界
- **验的需求**：`FR-EQ-013`
- **跑在内核**：`sha256:94645111a7e2eb3f…`（新鲜度 **current**）
- **记录版本**：1.6　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：此前内核只**吃** MXH 参数（`code/metric`），没有「给边界拟合 MXH」这一步

**参考**：闭式 —— 圆的精确退化与一个已知 MXH 形的原样回收

> ★★这两条是一对：圆钉**退化**（每条谐波为零），已知形钉**非退化**（系数原样回来）。★只验圆会放过一个把角度偏移算错的实现——圆的偏移恒为零，它照样过。

**参考**：本机拿得到的 g-file 边界

> ★判据点名「7 机型 MAST / DIII-D / JET RMS ≤ 2.4 %」。**本机只有 4 个机型**：EAST（3 炮）· DIII-D（1 炮）· CFEDR（3 份）· 合成（1 份）。**MAST 与 JET 没有**，那两格未评。

**口径与适用域**：

> g-file 的 `rbbbs` / `zbbbs` 边界轮廓，MXH 六阶谐波（与 `geometry::Surface::shape` 同一个 11 槽排列，$\delta=\sin s_1$、$\zeta=-s_2$）。★**只判边界这一条曲线**——判据里「合成 core_profiles → q 锁定定形重解贯通」那一段本条不涉及。★闭式两格在合成形上量，真机三格在实测轮廓上量。

## 判据与量到多少

:::{figure} ../figures/eq-surface-mxh-gfile-fit-headroom.svg
:alt: eq-surface-mxh-gfile-fit 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 圆的精确退化：每条谐波与 RMS | — | machine_precision | $R_0 = 3$、$a = 0.8$、512 点：$\kappa$ = 1.000000000000、$a$ 逐位、**每条谐波 ≤ 6.512e-16**、RMS **5.336e-16** | **成立** |
| 已知 MXH 形的系数原样回收（随轮廓点数收敛） | 1e-05 | analyst_declared | 造一个 $c_0..c_3$ / $s_1..s_3$ 已知的形（EAST 一档形变），点数 256 / 512 / 1024：最劣系数差 **4.869e-5 / 1.849e-5 / 4.052e-6**，RMS 2.561e-5 / 1.198e-5 / 1.781e-6。四倍点数缩 **12 倍** | **成立** |
| 真装置 g-file 边界的拟合 RMS（按小半径归一） | 0.024 | reference_self_reported | RMS（按 $a$ 归一）：**EAST** 0.953 / 1.348 / 1.284 % · **CFEDR** 1.358 / 0.543 / 0.307 % · **DIII-D 2.460 %**（判据带 2.4 %，**刚出**）。★★最劣残差的位置：EAST $\theta/\pi$ = 0.34–0.36、$z/a$ ≈ +1.4…+1.5（**上** X 点）；DIII-D $\theta/\pi$ = 1.615、$z/a$ = −1.65（**下** X 点）；CFEDR $\theta/\pi$ ≈ 1.53–1.66、$z/a$ ≈ −1.68…−1.91（下 X 点）——**无一例外** | **不成立** |
| 判据点名的 7 机型（MAST / DIII-D / JET …） | 7 | reference_self_reported | ★**未评**。判据点名 7 机型；本机 g-file 语料覆盖 **4 个**（EAST · DIII-D · CFEDR · 合成），**MAST 与 JET 一份也没有** | **未评估** |

**★★已知 MXH 形原样回来——而这条把两个分支 bug 揪了出来**

- ★★**这条测试逮住了两个分支 bug，而圆那条对它们一声不响**：〔一〕初版拿 $\cos\theta_R$ 的符号去分 $\theta$ 的支，而那是**另一个角**——偏移大到让两者落进不同半平面时（本例 $s_1=0.31$）分支就挑错，系数偏到 **2.385e-2**；〔二〕改完仍有 **4.7e-4 且不随点数收敛**（6.6e-4 / 5.3e-4 / 4.7e-4，比值 1.2），那是 $\theta_R$ 取「离 $\theta$ 最近的一支」——**$\theta\approx\pi$ 处两个候选都贴着 $\pi$**，挑法在那一带失效。改成与 $\theta$ 同一个办法（由 $\mathrm{d}R$ 的符号定）之后降到 4e-6。
- ★★**「不收敛」这件事本身是诊断**：离散化误差会按幂次缩，而系统性挑错不会。若当初调松容差让它过了，那块偏差会一直在。
- ★判据按**跨两档**看而不是单步：$\kappa$ 从包围盒取，误差由「哪个采样点离 $Z$ 极值最近」决定，**是阶梯式的**——实测 256 与 512 上 $\kappa$ 完全相同（1.750015905），到 1024 才跳。

**★★真机上残差**堆在 X 点**，EAST / CFEDR 在带内，DIII-D 刚出带**

- ★★**判 fail 是因为 DIII-D 那一份出带，而不是因为拟合有毛病**。残差在每一个真位形里都落在 X 点上，而 MXH 的六阶谐波**表达不了尖角**——这是这族参数化的性质。★要压进带里有两条路：加谐波阶数，或在 X 点邻域另行处理。**两条都没做**，因为那会改变与 GACODE 同口径的那 11 个槽。
- ★**合成件不参与带的判定**：它的轮廓首尾差 **3.14 % 小半径**（不闭合），且外侧有一段**竖直平面**（前 6 点 $R$ 全等于 $R_{max}$），总转角只有 $0.995\times2\pi$——**它不是一条 MXH 可表达的星形曲线**。它的 26.716 % 是关于那份语料的真话，不是拟合的。
- ★**一条不花钱的自洽检查**：MXH 的 $\kappa$ 与包围盒的 $\kappa$ **逐位相同**（8 份全部，差 0.0）——两者都从 $Z$ 的极值来。★它对不上一定是错的；对得上却不说明拟合对（分支挑错时 $\kappa$ 不受影响）——所以它只能当**必要条件**用。

**★MAST 与 JET：本机没有**

- ★缺的是语料不是能力：工具按机型分组、带就写在那里，一份 MAST 或 JET 的 g-file 进来即可入列。
- ★★**球形托卡马克（MAST）恰恰是最该验的那一个**：它的 $\kappa$ 与形变都远大于 EAST，而本条的结论「残差堆在 X 点」是在常规环径比上得到的。**在 MAST 上它未必还成立**，而这一条本册答不了。

## 不可比的部分

- ★★**判决 inconclusive**：四格里两格成立、一格不成立（DIII-D 出带）、一格未评（MAST / JET 没有语料）。★不成立那一格的成因已经量清楚了（X 点尖角），所以它是一条**可解释的**不成立，不是一个待查的谜。
- ★★2026-09-18 之前内核只**吃** MXH 参数（`code/metric` 按面算度规），**没有拟合**。本条同时是这项能力的入册与它的第一次检验。
- ★判据整句还包含「合成 core_profiles → q 锁定定形重解贯通」与「对真 EFIT q 定性符合」，本条**不替它们声明**——那要走 `code/fixed_boundary`，是另一条。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.6　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-013` 的边界拟合一格从空缺转为记录，判 **inconclusive**。内核新写 `geometry::fit_mxh`（Arbon–Candy–Belli 参数化，与 `Surface::shape` 同一个 11 槽排列），经 `code/shape` 报出。圆精确退化到 6.5e-16；已知形系数随点数收敛（256/512/1024 上 4.87e-5 / 1.85e-5 / 4.05e-6）。★★**已知形那条测试逮住了两个分支 bug**（用 $\cos\theta_R$ 的符号分 $\theta$ 的支、$\theta_R$ 取「最近的一支」在 $\theta\approx\pi$ 处失效），而圆那条对两者一声不响——两条必须成对。★真机：EAST 与 CFEDR 在 2.4 % 带内，**DIII-D 2.460 % 刚出带**，判 fail；★★成因已量清：**最劣残差在每一个真位形里都落在 X 点上**（$\|z/a\|>1.4$），MXH 六阶谐波表达不了尖角。★合成件（26.7 %）点名排除：轮廓不闭合 3.1 % 且外侧有竖直平面。★MAST / JET 未评——本机没有那两个机型的 g-file。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:94645111a7e2eb3ff131ac2163078d5200afba5cbe6bc6bcf2537f466ad153fc`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/mxh_fit_gfiles.json`    `sha256:89273f522def8192ece2058dbaadfecc1636edd19ac32258d0435f61dbca84a8`    8 份 g-file 的 MXH 拟合：RMS、谐波、最劣残差的位置、轮廓闭合度

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/geometry.rs::tests::a_circle_is_mxh_with_every_harmonic_zero` —— 第一格的锚
- `$FYLITE_KERNEL/rust/fylite/src/geometry.rs::tests::a_known_mxh_shape_comes_back_with_its_own_coefficients` —— ★第二格的锚——两个分支 bug 都是它逮住的
- `python/tests/test_benchmark_mxh_fit.py::test_every_real_machine_boundary_fits_inside_the_band` —— 第三格的门
- `python/tests/test_benchmark_mxh_fit.py::test_the_residual_sits_on_the_x_point` —— ★守的是「残差堆在尖角上」这个结论本身
- `python/tests/test_benchmark_mxh_fit.py::test_the_mxh_kappa_is_the_bounding_box_kappa` —— 自洽检查（必要条件）
- `python/tests/test_benchmark_mxh_fit.py::test_an_unclosed_outline_is_named_not_averaged_in` —— ★守的是合成件被点名排除而不是摊进平均
- `python/tests/test_benchmark_mxh_fit.py::test_the_recorded_readings_are_what_this_checkout_computes` —— ★守的是记录里的数不会悄悄过期

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
