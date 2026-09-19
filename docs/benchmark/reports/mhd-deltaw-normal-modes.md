---
title: "mhd-deltaw-normal-modes"
---

# 动能归一与 ω²：**θ-pinch 解析谱、带边 1.0 / 1.0625、窗口闭合——锁死由中点减缩积分治掉**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-normal-modes.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-normal-modes.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：动能归一与 ω²：**θ-pinch 解析谱、带边 1.0 / 1.0625、窗口闭合——锁死由中点减缩积分治掉**
- **参考**：Newcomb (1960) Eqs. (6)–(10)；均匀 θ-pinch 的解析谱；FR-EQ-017 的解析带边
- **验的需求**：`FR-EQ-028`
- **跑在内核**：`fylite_kernel@0f7e5af3b3cf`（新鲜度 **current**）
- **记录版本**：1.10　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Newcomb (8) 的极小化前形式，(ξ, u, v) 实变量；真空以 I_m/K_m 精确标量势作边界项

**参考**：Newcomb (1960) Eqs. (6)–(10)；均匀 θ-pinch 的解析谱；FR-EQ-017 的解析带边

> 慢（尖点）连续谱底 $k^2c_s^2v_A^2/(c_s^2+v_A^2)$、Alfvén $k^2v_A^2$；均匀电流带边 $(m-1+(a/b)^{2m})/n$。

**口径与适用域**：

> 柱位形、单 $(m,k)$；ρ 常数；γ 为输入。μ₀ ≡ 1，SI 时 $\omega^2_{SI}=\omega^2/\mu_0$。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-normal-modes-headroom.svg
:alt: mhd-deltaw-normal-modes 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 转录符号闭合（对 $(u,v)$ 逐点极小化恰得 $f,g$ + 零拉氏量，$S$ 为 (17) 的分部积分项） | 1e-12 | machine_precision | 四组 $(m,k)$ × 39 点 | **成立** |
| θ-pinch 解析谱（慢连续谱底 · Alfvén 簇） | — | reference_self_reported | n = 100 · 200 · 400：7.8e-6 · 1.9e-6 · 4.7e-7 / 1.9e-6 · 4.8e-7 · 1.2e-7 | **成立** |
| 边缘同点；连续谱地板随网格收敛 | — | reference_self_reported | δW 核与 ω² 核的 m = 1 边缘 k 差 2.0e-12；共振在域内而 δW 稳时，ω² 地板 2.2e-11 → 4.2e-13（n = 100 → 800） | **成立** |
| 解析带边复现（有壁 1.0625 / 无壁 1.0 两支 < 0.01）；窗口闭合对照（差 > 10²） | 0.01 | reference_self_reported | 带边 0.99835 / 1.06053（$R/a=10$、400 单元）；刚性位形 $R/a=100$ 在 100 单元上即 0.999984；窗口：真空 −1.99e-2 对等离子体填充 −4e-17 | **成立** |
| 真空系数三独立核（$ka\to0$ 闭式 · 壁贴边发散 · 单调） | — | reference_self_reported | $\kappa a=10^{-5}$ 对闭式 1.2e-9；贴壁 $b/a=1+10^{-6}$ 给 2.4e5；$b/a$ 从 1.05 到 1e3 单调降到无壁值（9 位） | **成立** |
| $\omega^2\propto1/\rho$ 精确 · γ 无关边缘 · $\mathbf M$ 正定 $\mathbf A$ 对称 · 二阶收敛 | — | reference_self_reported | ρ ×4：ω² 比 4.000000000000000；γ = 5/3 与 1 的带边逐位相同；A 非对称 1.5e-16、M 无负本征值；不稳本征值逐档差比 3.95 / 3.99 | **成立** |
| 负压强 / 非正 γ / 坏 ρ fail-loud | — | reference_self_reported | 四种都按名拒绝；`omega2_to_si` 除 μ₀ | **成立** |

**两项残余 2.7e-15；$r\Lambda$ 对 $f\xi'^2+g\xi^2+(S\xi^2)'$ 2.6e-14**

- ★数值闭合（解析解出 u、v 后逐点代入），不是符号推导。$S=(k^2r^2B_z^2-m^2B_\theta^2)/(k^2r^2+m^2)$ 恰是 (17) 最后一项分部积分出的那一项。

**慢谱底 400 单元 4.7e-7（每加倍降 4 倍）；Alfvén 簇底 1.2e-7**

- ★上游记的 1.4e-8 / 6e-7 是它自己的网格；本条的慢谱底按 h² 收敛，要到 1.4e-8 约需 2300 单元。

**★δW 核与 ω² 核的 m = 1 边缘 k 差 2.0e-12；共振在域内而 δW 稳时，ω² 地板 2.2e-11 → 4.2e-13（n = 100 → 800）**

- ★要一个 **Suydam 稳定**的共振面：头一个试的剖面处处违反 Suydam，共振面上必有局域不稳模——δW λ = −0.79，那不是地板。换成弱电流剖面后才有「稳而有共振」的对照。

**★★带边 0.99835 / 1.06053（$R/a=10$、400 单元）；刚性位形 $R/a=100$ 在 100 单元上即 0.999984；窗口：真空 −1.99e-2 对等离子体填充 −4e-17**

- ★★**锁死，照实记**：约束项（$\gamma P(\eta+\nabla\cdot\xi)^2$ 与 $(\zeta-\zeta_0)^2$）按 4 点 Gauss 积分时，逐单元常值的 (u, v) 只有两个数，满足不了单元内处处成立的两条约束——$R/a=100$ 上带边 1.201 · 1.126 · 1.045 · 1.014（n = 100–800），ω² 只一阶收敛（比 1.9 / 2.3），边缘 k 对 δW 核差 2e-3。**约束项改取单元中点单点求积**后，两条约束在中点上恰能满足，离散能量就是 Eq. (14) 的 Gauss 积分——三处问题同时消失。
- ★窗口闭合：把真空换成铺到 $r=3$ 的无压强等离子体，共振面 $r=a\sqrt{2/q_a}$ 落在里面，冻结约束让它成了理想壁——同一 $q_a=1.5$ 从强不稳变成只剩地板。**真空不是无压强等离子体。**

**$\kappa a=10^{-5}$ 对闭式 1.2e-9；贴壁 $b/a=1+10^{-6}$ 给 2.4e5；$b/a$ 从 1.05 到 1e3 单调降到无壁值（9 位）**

- ★1.2e-9 是**物理**修正本身（$K_1$ 的 $x^2\ln x$ 项在 $x=10^{-5}$ 上约 1e-9），闭式是 κ = 0 的值。
- ★$I_m$ 改用幂级数：积分表示在小 $x$ 上是 O(1) 相消出 O($x^m$)，初版在这里只剩 1e-5 的相对精度、κ → 0 锚差 6.5e-7。

## 不可比的部分

- ★★**判决成立**：七格全过。锁死是本条最大的一处实测收获：SRS 规定的「线性元 ξ × 逐单元常值 u、v」必须配中点减缩积分才不锁。
- ★这是全 δW 支与 L0 **唯一**不依赖外部数据的连接点（带边 1.0 / 1.0625）。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.10　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-028` 判**成立**。`screwpinch.rs` 增正规模问题：(ξ, u, v) 实变量、真空 I_m/K_m 边界项。★★锁死：约束项全 Gauss 积分时 R/a = 100 的带边 1.20→1.01、ω² 一阶收敛——改中点减缩积分后带边 100 单元即 0.99998、ω² 比 3.95/3.99、两核边缘同点到 2e-12。带边 0.9984 / 1.0605；θ-pinch 慢谱底 4.7e-7；窗口闭合 −2e-2 对 −4e-17；I_m 改幂级数（积分表示小 x 相消）。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@0f7e5af3b3cf`（库 `sha256:ac8204aa49349cc0ac53b3b5f9d7b91630ce4d69380fc7aa37034c89ce54dfe8`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/screw_pinch_normal_modes.json`    `sha256:e77da431655f7e96f52c60f508dcaaac01e4f4f404e613b179351dc69b6109e6`    闭合、θ-pinch 谱、边缘同点与地板、带边与锁死、窗口、真空系数、标度、对称与正定、收敛、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::minimizing_over_u_and_v_closes_on_f_g_and_a_null_lagrangian` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::a_uniform_theta_pinch_has_its_analytic_spectrum` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::omega_squared_flips_where_the_energy_does` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::with_a_resonance_inside_the_stable_floor_converges_to_zero` —— 第三格：地板
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::the_vacuum_term_reproduces_the_analytic_band_edges` —— ★第四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::a_vacuum_is_not_a_pressureless_plasma` —— ★第四格：窗口闭合
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::the_vacuum_coefficient_has_three_independent_checks` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::omega_squared_scales_as_one_over_rho_and_the_edge_does_not_see_gamma` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::the_mass_is_positive_definite_and_the_potential_is_symmetric` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::the_unstable_eigenvalue_converges_at_second_order` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests28::bad_physics_is_refused_by_name` —— 第七格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
