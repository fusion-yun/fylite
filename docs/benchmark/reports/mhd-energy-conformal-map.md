---
title: "mhd-energy-conformal-map"
---

# 星形域到单位圆盘的共形映射：**机器全对，而谱收敛的快慢是形状的事**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-conformal-map.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-conformal-map.jsonld`*

## 摘要

- **类**：验证　**判决**：**未判（读数）**
- **量的是**：星形域到单位圆盘的共形映射：**机器全对，而谱收敛的快慢是形状的事**
- **参考**：共形映射的数学性质（Riemann 映射定理；Theodorsen 积分方程）与判据自带的数
- **验的需求**：`FR-EQ-025`
- **跑在内核**：`sha256:94645111a7e2eb3f…`（新鲜度 **current**）
- **记录版本**：1.3　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Theodorsen 迭代 + FFT 共轭函数，M = 1024；逆映射初值取自边界对应

**参考**：共形映射的数学性质（Riemann 映射定理；Theodorsen 积分方程）与判据自带的数

> 边界落在曲线上、单叶、圆域精确退化、调和函数在共形基上谱收敛——这些与实现无关。★判据给的 6/12/20 模 → 1.3e-2 / 1.1e-3 / 5.7e-5 **没说是哪个形状**。

**口径与适用域**：

> 星形域（$\rho(\theta)>0$ 单值）、Theodorsen 迭代收敛（近圆的形状）、$M=1024$。★强 D 形（κ1.6 δ0.35）仍收敛且单叶，但调和表示的谱收敛慢。★**不含**非星形域与带 X 点的边界。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-conformal-map-headroom.svg
:alt: mhd-energy-conformal-map 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 边界落在 $\Gamma$ 上（判据 1.4e-15） | 1e-12 | machine_precision | $\max_\phi\big\|\|f(e^{i\phi})\|-\rho(\arg f)\big\|$：椭圆 $b/a=1.6$ **6.661e-15**（41 次迭代）；Miller κ1.6 δ0.35 **7.994e-15**（76 次） | **成立** |
| 单叶 | — | reference_self_reported | 强 D 形：$\theta(\phi)$ 严格单调（`theodorsen` 自己也查，不单调即拒绝）；41 × 128 点网格上 $\min\|f'\|$ = **0.7123** | **成立** |
| 往返（判据 2.5e-16，含近边界 0.999） | 1e-12 | machine_precision | 768 个内点（12 半径 × 64 角）加 $\|\zeta\|=0.999$ 一圈 64 点：椭圆 **3.51e-16**，强 D **5.55e-16**；内点像 $\max\|\zeta\|$ = 0.9903 / 0.9928 | **成立** |
| 圆域精确退化为 $f=a\zeta$、边界对应为恒等 | — | reference_self_reported | $\rho\equiv0.7$：1 次迭代，$\|a-0.7\|<10^{-15}$，$g_{k\ge1}$ 逐位 0，$\theta_j$ 逐位等于 $2\pi j/M$ | **成立** |
| ★★共形基谱收敛（6/12/20 模 → 1.3e-2 / 1.1e-3 / 5.7e-5，每档至少降 3 倍），同等模数下优于星形基 > 5× | — | reference_self_reported | 调和函数 $u=\operatorname{Re}w$ 在 768 内点上的最大误差，N = 6 · 12 · 20：Miller κ1.3 δ0.2 共形 **2.29e-2 · 4.05e-3 · 4.64e-4**，星形 4.37e-2 · 4.37e-2 · 4.37e-2（星/共形 1.9 · 10.8 · 94）；Miller κ1.6 δ0.35 共形 **1.21e-1 · 5.11e-2 · 1.81e-2**，星形 7.10e-2（星/共形 **0.59** · 1.39 · 3.9）。上游：1.3e-2 · 1.1e-3 · 5.7e-5，形状未写 | **未判（读数）** |
| 圆域上两基逐点相同 | — | reference_self_reported | $\rho\equiv1$：N = 6 · 12 · 20 两基误差都是 6.1e-15 · 6.1e-15 · 6.2e-15，逐 N 相同 | **成立** |
| ★朴素 Newton 初值跑出单位圆的反证；逆映射像在闭圆盘内 | — | reference_self_reported | 初值 $w/f'(0)$、不设护栏：强 D 形 768 个内点中 **76** 个的迭代出了 $\|\zeta\|\le1$；稳健版（边界对应给初值、出圆步长减半）$\max\|\zeta\|$ = 0.9928 | **成立** |
| 边界谱换算：形变泄漏、圆域不泄漏 | — | reference_self_reported | 共形角上的 $\cos m\phi$ 在几何角上重展开：圆域 $c_m=1$、其余 $\le$ 1.77e-16；强 D 形 $m$ = 1 · 2 · 3 时 $c_m$ = 0.898 · 0.983 · 0.913，模外 $\ell_2$ 泄漏 **0.130 · 0.270 · 0.398** | **成立** |
| 不收敛 / 坏网格 / 负半径 fail-loud | — | reference_self_reported | $M=1000$、$M=8$ → `CONFORMAL_BAD_GRID`；$\rho=\cos\theta$ → `CONFORMAL_NEGATIVE_RADIUS`；3 次迭代封顶 → `CONFORMAL_NO_CONVERGENCE` | **成立** |

**边界落在曲线上 6.7e-15 / 8.0e-15**

- ★判据字面 1.4e-15 是上游在它自己的形状上量的；这里是 5 倍，仍在机器精度量级（$M=1024$ 点上的 FFT 舍入）。门按 1e-12 设，数照实记。

**★★温和 D 形上共形基每档降 5.7× / 8.7×，星形基停在 4.4e-2；**强 D 形只降 2.4× / 2.8×，N=6 时还不如星形基****

- ★★**判据说的「表示」是什么，先要读对**：拿边界 $\rho(\theta)$ 本身比，星形基（就是 $\rho$ 的傅里叶级数）反而远好于共形基——那个读法是错的。判据有意义的读法是**域内调和函数**：$\delta W$ 的真空势是调和的，共形拉回后在圆盘上是 $\operatorname{Re}\sum c_k\zeta^k$；星形基 $(r/\rho)^{|k|}e^{ik\theta}$ 在域内**不调和**，于是停在一个平台上不再下降。本格按后一读法验。
- ★★**谱收敛的速率是形状的事，不是实现的事**：给定精确映射，截断到 N 模的误差由 $f$ 的解析延拓在圆外最近的奇点决定。强 D 形的奇点离单位圆近，所以慢——**任何正确的实现都给同样的数**。所以强 D 形的 2.4× / 2.8× 不是缺陷，照实留作负面结果（门 `a_strong_d_is_where_the_five_fold_drop_is_lost` 把它钉住）。
- ★「> 5×」在温和 D 形的 N=6 上只有 1.9×，N=12 起才 > 5×——照实记。
- ★★**判未判**：上游的 1.3e-2 / 1.1e-3 / 5.7e-5 没有说形状，本条无从复现那三个数；两个形状照实报，谁也不挑出来冒充上游的那个。

**★朴素 Newton 在强 D 形上 76 / 768 个点跑出单位圆；稳健逆映射的像全在圆内**

- ★原型里朴素 Newton 直接给出 NaN——截断级数在圆外发散。**这个反证是判据自己要的**，它说明「初值取自边界对应」不是装饰。

## 不可比的部分

- ★★**判未判**：机器的八格全过；谱收敛那一格上游的数没有形状，而本条量到的收敛速率随形状从 5.7×/8.7× 降到 2.4×/2.8×——这是数学性质，照实报两个形状，不挑。
- ★这一条给 `FR-EQ-023` 的真空能铺路：共形拉回之后真空势在圆盘上是谱收敛的，前提是形状别太 D。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.3　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-025` 从空缺转为记录，判**未判**。内核新写 `conformal.rs`：Theodorsen 迭代 + FFT 共轭函数，逆映射初值取自边界对应。边界 8e-15、单叶、往返 5.6e-16（含 0.999）、圆域逐位退化、两基在圆上相同、边界谱圆域不泄漏、fail-loud——机器八格全过。★★**判据的「表示」要读成域内调和函数**：拿边界本身比，星形基反而更好。★★温和 D 形共形基每档降 5.7×/8.7×、星形基停在 4.4e-2；强 D 形只降 2.4×/2.8×、N=6 还不如星形基——速率是形状的数学性质，留作负面结果。上游的三个数没说形状，无从复现，故判未判。★朴素 Newton 在强 D 形上 76/768 个点跑出单位圆——判据要的反证。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:94645111a7e2eb3ff131ac2163078d5200afba5cbe6bc6bcf2537f466ad153fc`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/conformal_map.json`    `sha256:46efa9e6d4d2409c4733b3bcb870d06c6dd5d92c36913496107b48e68daf79e2`    三个形状上的边界、单叶、往返、调和表示两基对比、朴素 Newton 反证、边界谱、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_boundary_lands_on_the_curve` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_map_is_univalent_on_the_disk` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_robust_inverse_round_trips_up_to_the_edge` —— 第三格与第七格后半
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_circle_degenerates_exactly` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::a_harmonic_function_converges_spectrally_only_in_the_conformal_basis` —— 第五格：温和 D 形
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::a_strong_d_is_where_the_five_fold_drop_is_lost` —— ★第五格：强 D 形的负面结果
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::both_bases_coincide_on_the_circle` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::naive_newton_leaves_the_disk` —— ★第七格：反证
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_boundary_spectrum_leaks_only_on_a_deformed_domain` —— 第八格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::bad_input_is_refused_by_name` —— 第九格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
