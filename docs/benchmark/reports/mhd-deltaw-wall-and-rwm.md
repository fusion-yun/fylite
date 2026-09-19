---
title: "mhd-deltaw-wall-and-rwm"
---

# 理想壁分支与薄壁阻性壁模：**Λ = 2 两行到 PEST 0.05 % 内，阻性壁窗口的转换点落在解析带边上**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-wall-and-rwm.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-wall-and-rwm.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：理想壁分支与薄壁阻性壁模：**Λ = 2 两行到 PEST 0.05 % 内，阻性壁窗口的转换点落在解析带边上**
- **参考**：Chance 1978 Table I 的 Λ = 2 两行；Freidberg (2014) §11.5 Eqs. (11.148)–(11.150)、(11.169)–(11.170)
- **验的需求**：`FR-EQ-031`
- **跑在内核**：`sha256:e4040bbf79e390d9…`（新鲜度 **current**）
- **记录版本**：1.6　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：环隙 MFS（源点在等离子体内与壁外）；柱位形薄壁 RWM（边缘方程积分 + 两个参考 δW）

**参考**：Chance 1978 Table I 的 Λ = 2 两行；Freidberg (2014) §11.5 Eqs. (11.148)–(11.150)、(11.169)–(11.170)

> 壁在 $\Psi_W=\Lambda^2\Psi_B$ 那张解析延拓的磁面上；RWM 的窗口转换点须落在 $q=1$ · $q_{marg}(b)$ · $m/n$。

**口径与适用域**：

> Λ = 2 两行：Solov'ev ε = 1/6、E = 1；RWM：柱位形、薄壁（w/b ≤ 0.1）、单 (m, k)。★**环几何 RWM 本条未做**（上游补记里的 Schur 缩聚 + 单 τ 薄壳插值不在本仓）。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-wall-and-rwm-headroom.svg
:alt: mhd-deltaw-wall-and-rwm 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 环隙 Bessel NtD 锚（$\chi'(b)=0$）< 1 % | 0.01 | reference_self_reported | 细环 a = 0.02、b = 0.04：最劣 3.2e-5 | **成立** |
| Λ = 2 两行（容差 15 %）；三支排序 $\omega^2(\Lambda=1)\ge\omega^2(\Lambda)\ge\omega^2(\infty)$ | 0.15 | reference_self_reported | ε = 1/6、E = 1、n = 1、160 单元、m ∈ [−6, 10]；320 单元逐位同到 4 位 | **成立** |
| RWM 窗口三段转换点 = 解析带边（rwm ↔ ideal 对 1.48225 差 < 0.01） | 0.01 | reference_self_reported | 均匀电流 m = 2、n = 1、ka = 0.1、b/a = 1.2；rwm ↔ ideal 差 0.002（有限 ka） | **成立** |
| 壁越近 γ 越小；几何因子精确 / 近似互证；$(r\xi'/\xi)_a$ 与壁无关逐位 | — | reference_self_reported | γτ_w 0.133 → 0.373 → 0.886 → 2.563（b/a = 1.1 → 1.4）；几何因子 ka = 0.1 / 0.01 时精确对近似 5.3e-4 / 5.2e-6；(rξ'/ξ)_a 四个壁位置逐位相同 | **成立** |
| 守卫（Λε ≥ 1/2 / 厚壁 / m = 0 / 域内共振）fail-loud | — | reference_self_reported | 2εΛ ≥ 1 的壁、w/b > 0.1、m = 0、b ≤ a、域内共振都按名拒绝 | **成立** |

**★★0.2041（PEST 0.204，+0.05 %）· 0.5058（PEST 0.506，−0.04 %）；定形 ≤ 有壁 ≤ 无壁（0 ≤ 0.204 ≤ 0.247；0.077 ≤ 0.506 ≤ 0.532）**

- ★Table I 全八行至此都在容差内：定形 0.4314 / 0.1199、无壁 0.758 / 0.673 / 1.377 / 1.065、有壁 0.2041 / 0.5058。

**★★0.99835 · 1.48023（对 1.48225）· 2.00024**

- ★第三个转换点只到 2.4e-4：q_a → m/n 时 $f\propto F^2$ 在整个等离子体里一起趋零，边缘方程变刚。恰在 m/n 上 F ≡ 0，边缘方程按名拒绝——测试的二分括号初版正落在 2.0 上，就被拒了（那是对的）。

**γτ_w 0.133 → 0.373 → 0.886 → 2.563（b/a = 1.1 → 1.4）；几何因子 ka = 0.1 / 0.01 时精确对近似 5.3e-4 / 5.2e-6；(rξ'/ξ)_a 四个壁位置逐位相同**

- ★精确几何因子为**负**（$K_b'<0$），书上近似是它的绝对值，符号由 $\tau_w=-(\mu_0wb/\eta)g$ 吸收。
- ★★`FF†/k₀²` 那一项就是 (f, g) 分部形式与 Eq. (8) 口径之差的边界项 $[S\xi^2]_a$：拿掉它，q_a = 1.5 的 δW_∞ 从 −1.0e-2 变成 +7.4e-3——不稳带内被错判为稳，**静默**。这一条钉成了测试。
- ★τ_w 的 SI 值另给（`wall_time_si`，η 取电阻率 Ω·m、μ₀ 取 SI）：1 cm 铜壁、b = 1.2 m 约 0.115 s。交付量是无量纲 γτ_w。

## 不可比的部分

- ★★**判决成立**：五格全过。至此 Chance 1978 Table I **全八行**都在容差内。
- ★(甲) 是对拍、(乙) 是对解析带边的验证，合在一条记录里是因为 SRS 把它们放在一条需求里。
- ★门在内核仓，本仓 CI 跑不到；Λ = 2 两行在 `cargo test --release` 下跑。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.6　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-031` 判**成立**。环隙 MFS 柱锚 3.2e-5；Λ = 2 两行 0.2041 / 0.5058（对 PEST ±0.05 %），三支排序成立——Table I 全八行在容差内。柱位形薄壁 RWM：窗口转换点 0.998 / 1.480 / 2.000 对 1 / 1.48225 / 2；γτ_w 随壁移近单调降；几何因子精确/近似互证；★去掉 FF†/k₀² 边界项 δW_∞ 被错判为正——钉成测试。环几何 RWM 未做。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.4 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e4040bbf79e390d949739fc5023d63e8ba5759242ad7ca52839becab115ba3f6`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/toroidal_wall_and_rwm.json`    `sha256:104345171948ce5ec579f59feed0f41fcee474e2d946adeb7a3a6bf3a3f04853`    环隙柱锚、Λ = 2 两行与三支、RWM 窗口、壁距、几何因子、零拉氏量边界项、守卫

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests31::the_annulus_map_has_the_cylinder_limit` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests31::table_i_wall_rows_land_and_the_three_branches_are_ordered` —— 第二格（--release）
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests31::a_wall_that_crosses_the_axis_is_refused` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests31::the_window_switches_at_the_analytic_band_edges` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests31::a_closer_wall_slows_the_mode_and_the_edge_solution_ignores_the_wall` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests31::the_geometry_factor_exact_and_approximate_agree_for_small_kb` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests31::dropping_the_null_lagrangian_boundary_term_hides_the_instability` —— ★第四格：边界项
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests31::guards_are_named` —— 第五格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
