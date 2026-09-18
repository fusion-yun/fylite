---
title: "mhd-energy-three-term-assembly"
---

# 三项装配层：**装配路与闭式路的残差是三阶，不是一阶——表面项的一阶修正被压强平衡精确抵消**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-three-term-assembly.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-three-term-assembly.jsonld`*

## 摘要

- **类**：验证　**判决**：**未判（读数）**
- **量的是**：三项装配层：**装配路与闭式路的残差是三阶，不是一阶——表面项的一阶修正被压强平衡精确抵消**
- **参考**：Freidberg, *Ideal MHD* (2014) §12.8.3：Eqs. (12.129)–(12.131)、(12.135)–(12.140)、(12.146)–(12.147)、(12.151)–(12.153)、(12.159)、(12.164)
- **验的需求**：`FR-EQ-024`
- **跑在内核**：`sha256:94645111a7e2eb3f…`（新鲜度 **current**）
- **记录版本**：1.2　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：三项各自只交出「ξ → 标量」，非对角元由极化取出；闭式路按 §12.8.3 的一般 k 分支

**参考**：Freidberg, *Ideal MHD* (2014) §12.8.3：Eqs. (12.129)–(12.131)、(12.135)–(12.140)、(12.146)–(12.147)、(12.151)–(12.153)、(12.159)、(12.164)

> 闭式路 = 该书的序化约化式；它在 $k^2=1$ 上必须逐元复现 Eq. (12.164) 的转录（这同时是 `FR-EQ-021(c')` 要的第二条路）。

**口径与适用域**：

> 高 β 表面电流模型、圆截面、三谐波基、$n=1$；**约化**泛函——原则上复现不了 Chance 1978 / Cheng–Chance 1987 的 Table I（那是全 δW + 动能归一）。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-three-term-assembly-headroom.svg
:alt: mhd-energy-three-term-assembly 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| ★★装配路 vs 闭式路四档 ε 的 $\Delta/\varepsilon$ 同值（0.10208） | — | reference_self_reported | $k^2=0.5$：ε = 0.4 · 0.2 · 0.1 时 $\Delta q_*$ = −4.84e-2 · −6.20e-3 · −7.58e-4（比 7.81 · 8.18）；表面项矩阵残差 ε = 0.4…0.05 比 7.88 · 8.09 · 8.07 | **未判（读数）** |
| 边缘点亦一阶收敛；$k^2=0.5/0.7/0.9$ 上同样成立 | — | reference_self_reported | $k^2$ = 0.5 · 0.7 · 0.9 的比值 7.81/8.18 · 7.64/8.14 · 7.59/8.13。流体项（`fluid.rs` 代 12.146）对 (12.147) **4.1e-15**；真空项（边界积分）对 $G_{ml}$ 级数 (12.153) **3.6e-15**——两套完全不同的真空解法到机器精度 | **未判（读数）** |
| 网格已收敛 | 1e-12 | machine_precision | $\varepsilon=0.2$、$q_*=1.4$、$k^2=0.7$：表面 256→512、真空 64→128，总矩阵最大元差 2.39e-15 | **成立** |
| 解析导数对谱求导 | 1e-10 | machine_precision | 128 点，最劣相对 6.13e-14 | **成立** |
| ★$k^2\ge1$ 拒绝给出（真发散，不平滑） | — | reference_self_reported | `HB_SEPARATRIX_ON_SURFACE` | **成立** |
| ★「有限差分导数会破坏可解性」已反钉成测试 | — | reference_self_reported | `numpy.gradient` 式（内点中心、两端单侧、不环绕） | **成立** |
| 几何 / 求根 fail-loud | — | reference_self_reported | `HB_BAD_INPUT` · `HB_NO_CROSSING` | **成立** |

**★★序化平衡下 $\Delta q_*$ 每 ε 减半降 **8 倍**（三阶）；$\Delta/\varepsilon$ 不是常数，更不是 0.10208**

- ★★**为什么是三阶**（解析）：表面项一般式 (12.135) 里，磁项 $\tfrac12(\hat B^2+B^2)(\hat\kappa_n-\kappa_n)$ 乘面元 $2\pi Ra\,d\theta$ 后，$(\cos\theta/R-1/a)\cdot Ra=-(R-a\cos\theta)=-R_0$ **精确**，于是磁项 $=-2\pi R_0B_\theta^2F$、$F-1\approx-\beta/2$，给出 $+\pi R_0\beta B_\theta^2$；压强项的一阶修正恰为 $-\pi R_0\beta B_\theta^2$。**二者等值反号，一阶修正被压强平衡抵消**，(12.137) 对这一平衡准到相对 $O(\varepsilon^2)$。
- ★Rust 与一段独立 Python 分别算出同一组比值（每个谐波各 8.3–8.5）——不是一处实现的巧合。
- ★★**改用有限 ε 的精确压强平衡**（Eq. 12.127）取 $B_\theta$：残差回到**一阶**，$\Delta q_*/\varepsilon$ 趋于随 $k^2$ 变的常数（Richardson 外推：$k^2=0.5$ 约 −0.48，$k^2=0.9$ 约 −0.36）。**两种口径都不是 0.10208**——SRS 没写 Δ 的定义（marginal $q_*$？相对差？某个矩阵元？），本条无从复现那个数，**不去凑**。故判未判。
- ★判据的实质（「一致的阶次即证明三项的符号 · 归一 · 基全对」）是满足的：三档 $k^2$ 上比值都在 7.6–8.2，阶次一致；流体项与真空项对闭式路到 1e-15（见下），错只可能在表面项，而表面项残差的阶次有解析解释。

**$k^2$ = 1.0 / 1.2 按名拒绝**

- ★照实记拒绝的理由：$k^2=1$ 时 (12.129) 的 $B_\theta\propto|\cos(\theta/2)|$ 在 θ = π 有尖点，边界数据不再光滑、谱方法失效；$k^2>1$ 时 $B_\theta^2<0$。闭式路在 $k^2=1$ 上不受此限——它用 (12.159) 的闭式谱系数。

## 不可比的部分

- ★★**判未判**：机器的五格全过；阶次那两格量到的东西与判据写的不同——序化平衡下三阶（有解析解释），精确平衡下一阶但系数随 $k^2$ 变，上游的 0.10208 两种口径都不复现。
- ★★**附带交付 `FR-EQ-021` 的两条**：闭式路在 $k^2=1$ 上逐元复现 (12.164) 的转录（截断按 $1/m_{max}^2$ 降，$m_{max}=1000$ 时 7.4e-8），$\lambda_{min}=0$ 的根 1.690113290 对转录路 1.690113289——这是 (c') 要的「由三式合成」；整条稳定边界（(e)）从 $k^2\to0$ 的 $q_*\to1$ 到 $k^2=1$ 的 1.690113、落在平衡极限上。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.2　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-024` 判**未判**。内核新模块 `highbeta.rs`：闭式路（§12.8.3 一般 k）与装配路（三项标量接口 + 极化）。★★序化平衡下残差三阶（Δq* 每 ε 减半降 8 倍，三档 k² 同），表面项一阶修正被压强平衡精确抵消——Rust 与独立 Python 同值，并有解析解释；精确平衡下一阶、系数随 k² 变；上游 0.10208 两种口径都不复现（SRS 未写 Δ 的定义），不去凑。流体项、真空项对闭式路 4e-15。附带交付 FR-EQ-021 的 (c')（12.164 三式合成 7.4e-8、根 1.690113290）与 (e)（整条边界两端）。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:94645111a7e2eb3ff131ac2163078d5200afba5cbe6bc6bcf2537f466ad153fc`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/three_term_assembly.json`    `sha256:21c93eeaa0d406817d870a8b0dc88d2706962735b07aa539f2f3bc5d3702572a`    12.164 重建、整条边界、分项对闭式、两种平衡下的阶次、网格、导数、差分反证、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::under_the_ordered_equilibrium_the_residual_is_third_order` —— ★第一、二格：序化平衡
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_surface_term_alone_is_third_order_too` —— 第一格：表面项本身
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::under_exact_pressure_balance_the_residual_is_first_order` —— ★第一、二格：精确平衡
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_fluid_and_vacuum_terms_are_the_closed_form_ones_at_any_eps` —— 第二格：分项
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_default_grid_is_converged` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_analytic_derivative_agrees_with_the_spectral_one` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::k2_at_or_above_one_is_refused_and_bad_input_is_named` —— 第五、七格
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::a_one_sided_difference_breaks_solvability` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::polarization_recovers_a_known_form` —— 附：极化与三角法本征值
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_closed_form_route_rebuilds_12_164_at_k2_equal_one` —— ★附：FR-EQ-021(c')
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_whole_boundary_has_both_analytic_ends` —— ★附：FR-EQ-021(e)

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
