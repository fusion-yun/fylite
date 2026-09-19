---
title: "mhd-energy-three-term-assembly"
---

# 三项装配层：**装配路与闭式路的残差是三阶，不是一阶——表面项的一阶修正被压强平衡精确抵消**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-three-term-assembly.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-three-term-assembly.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：三项装配层：**装配路与闭式路的残差是三阶，不是一阶——表面项的一阶修正被压强平衡精确抵消**
- **参考**：Freidberg, *Ideal MHD* (2014) §12.8.3：Eqs. (12.129)–(12.131)、(12.135)–(12.140)、(12.146)–(12.147)、(12.151)–(12.153)、(12.159)、(12.164)
- **验的需求**：`FR-EQ-024`
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.13　**评审**：草稿　**日期**：2026-09-18

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
| ★★装配路 vs 闭式路四档 ε 的 $\Delta/\varepsilon$ 同值（0.10208） | — | reference_self_reported | 上游口径（fyeq `test_high_beta_stability.py`）：Δ = max\|W_asm − W_closed\|（3×3 矩阵元），$k^2=0.9$、$q_*=1.5247$；表面项取该书 Eq. (12.136) 的序化曲率 $\kappa_n=-(\cos\theta/R_0)(1-\varepsilon\cos\theta)$、$B^2=\hat B^2=B_0^2$、面元 $2\pi R_0\,a\,d\theta$：ε = 0.2 · 0.1 · 0.05 · 0.025 → Δ/ε = 0.10207981262 · …453 · …459 · …472（上游 0.10208）。★真几何（本内核缺省，$R=R_0+a\cos\theta$、两侧真 $B^2$）下同一差是三阶：比值 7.81 · 8.18 | **成立** |
| 边缘点亦一阶收敛；$k^2=0.5/0.7/0.9$ 上同样成立 | — | reference_self_reported | 上游口径：边缘点 $\|\Delta q_*\|/\varepsilon$ 在 ε = 0.1 · 0.05 · 0.025 为 **0.099875 · 0.101134 · 0.101770**（上游 0.0999 · 0.1011 · 0.1018）；$k^2$ = 0.5 · 0.7 · 0.9 上 Δ/ε 在 ε = 0.1 与 0.05 两档 0.04099178 / 0.04099178 · 0.06656500 / 0.06656500 · 0.10207981 / 0.10207981。$k^2$ = 0.5 · 0.7 · 0.9 的比值 7.81/8.18 · 7.64/8.14 · 7.59/8.13。流体项（`fluid.rs` 代 12.146）对 (12.147) **4.1e-15**；真空项（边界积分）对 $G_{ml}$ 级数 (12.153) **3.6e-15**——两套完全不同的真空解法到机器精度 | **成立** |
| 网格已收敛 | 1e-12 | machine_precision | $\varepsilon=0.2$、$q_*=1.4$、$k^2=0.7$：表面 256→512、真空 64→128，总矩阵最大元差 2.39e-15 | **成立** |
| 解析导数对谱求导 | 1e-10 | machine_precision | 128 点，最劣相对 6.13e-14 | **成立** |
| ★$k^2\ge1$ 拒绝给出（真发散，不平滑） | — | reference_self_reported | `HB_SEPARATRIX_ON_SURFACE` | **成立** |
| ★「有限差分导数会破坏可解性」已反钉成测试 | — | reference_self_reported | `numpy.gradient` 式（内点中心、两端单侧、不环绕） | **成立** |
| 几何 / 求根 fail-loud | — | reference_self_reported | `HB_BAD_INPUT` · `HB_NO_CROSSING` | **成立** |

**★★上游的 Δ/ε = 0.10208 **复现**（四档 ε 逐档 0.1020798，同值到 1e-12）——在上游自己的表面项截断下；真几何下是三阶**

- ★★**此前判未判，是因为没找到 Δ 的定义**——SRS 正文没写。定义在上游测试里（`fytok/python/fyeq/tests/test_high_beta_stability.py`），连同它喂表面项的四样东西（`high_beta_stability.py::_pieces`）。按它的口径喂同一个一般式，Δ/ε 逐档同值到 1e-12、就是 0.10208。
- ★★**两种截断都对，量的是不同的东西**：上游只在曲率里留一个 $(1-\varepsilon\cos\theta)$，于是对闭式 (12.140) 的差**恰好一阶**——那个 0.10208 就是这一个因子的系数；本内核的缺省取真几何，面元乘出 $R-a\cos\theta=R_0$ 后一阶修正被压强平衡精确抵消，残差三阶（原 caveat 的解析推导仍成立）。本批新增 `surface_energy_book` 作为上游口径，缺省不变。
- ★★**为什么是三阶**（解析）：表面项一般式 (12.135) 里，磁项 $\tfrac12(\hat B^2+B^2)(\hat\kappa_n-\kappa_n)$ 乘面元 $2\pi Ra\,d\theta$ 后，$(\cos\theta/R-1/a)\cdot Ra=-(R-a\cos\theta)=-R_0$ **精确**，于是磁项 $=-2\pi R_0B_\theta^2F$、$F-1\approx-\beta/2$，给出 $+\pi R_0\beta B_\theta^2$；压强项的一阶修正恰为 $-\pi R_0\beta B_\theta^2$。**二者等值反号，一阶修正被压强平衡抵消**，(12.137) 对这一平衡准到相对 $O(\varepsilon^2)$。
- ★Rust 与一段独立 Python 分别算出同一组比值（每个谐波各 8.3–8.5）——不是一处实现的巧合。

**$k^2$ = 1.0 / 1.2 按名拒绝**

- ★照实记拒绝的理由：$k^2=1$ 时 (12.129) 的 $B_\theta\propto|\cos(\theta/2)|$ 在 θ = π 有尖点，边界数据不再光滑、谱方法失效；$k^2>1$ 时 $B_\theta^2<0$。闭式路在 $k^2=1$ 上不受此限——它用 (12.159) 的闭式谱系数。

## 不可比的部分

- ★★**判成立**（2026-09-19）：七格全过。阶次那两格按上游自己的 Δ 定义与表面项截断复现到位（0.10208、边缘点 0.0999 / 0.1011 / 0.1018）；真几何下同一差是三阶，照实并列，不是矛盾。
- ★★**附带交付 `FR-EQ-021` 的两条**：闭式路在 $k^2=1$ 上逐元复现 (12.164) 的转录（截断按 $1/m_{max}^2$ 降，$m_{max}=1000$ 时 7.4e-8），$\lambda_{min}=0$ 的根 1.690113290 对转录路 1.690113289——这是 (c') 要的「由三式合成」；整条稳定边界（(e)）从 $k^2\to0$ 的 $q_*\to1$ 到 $k^2=1$ 的 1.690113、落在平衡极限上。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.13　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-024` 判**未判**。内核新模块 `highbeta.rs`：闭式路（§12.8.3 一般 k）与装配路（三项标量接口 + 极化）。★★序化平衡下残差三阶（Δq* 每 ε 减半降 8 倍，三档 k² 同），表面项一阶修正被压强平衡精确抵消——Rust 与独立 Python 同值，并有解析解释；精确平衡下一阶、系数随 k² 变；上游 0.10208 两种口径都不复现（SRS 未写 Δ 的定义），不去凑。流体项、真空项对闭式路 4e-15。附带交付 FR-EQ-021 的 (c')（12.164 三式合成 7.4e-8、根 1.690113290）与 (e)（整条边界两端）。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 阶次两格转成立：Δ 的定义在上游测试里（max\|W_asm − W_closed\|，k² = 0.9、q* = 1.5247），按上游喂表面项的口径（Eq. 12.136 序化曲率、B² = B₀²、面元 2πR₀a dθ）新增 `surface_energy_book`，Δ/ε 逐档 0.1020798（到 1e-12）、边缘点 0.0999 / 0.1011 / 0.1018 全复现。真几何缺省下三阶，并列记。整体 inconclusive → pass。 |
| 1.8 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.11 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.12 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.13 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/three_term_assembly.json`    `sha256:21c93eeaa0d406817d870a8b0dc88d2706962735b07aa539f2f3bc5d3702572a`    12.164 重建、整条边界、分项对闭式、两种平衡下的阶次、网格、导数、差分反证、拒绝
- `docs/benchmark/readings/three_term_assembly_upstream_delta.json`    `sha256:97ddc23697936e600ff3bf286188b0a0d8d4710fcfb42ed536d8ce7ff98ca9dd`    上游 Δ 的定义、表面项口径与复现读数

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
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_book_ordered_surface_term_reproduces_the_upstream_delta_over_eps` —— ★Δ/ε = 0.10208
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::with_the_book_surface_term_the_marginal_point_and_every_k_are_first_order` —— ★边缘点与三档 k²

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
