---
title: "mhd-energy-fluid-high-beta"
---

# 高 β 序约化流体能量 δW_F：**闭合到 Eq. (12.147)，直角坐标复算钉住了基矢转动项**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-fluid-high-beta.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-fluid-high-beta.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：高 β 序约化流体能量 δW_F：**闭合到 Eq. (12.147)，直角坐标复算钉住了基矢转动项**
- **参考**：Freidberg, *Ideal MHD* (Cambridge, 2014), §12.8.2–12.8.3, Eqs. (12.123)–(12.124), (12.141)–(12.147)
- **验的需求**：`FR-EQ-022`
- **跑在内核**：`fylite_kernel@0f7e5af3b3cf`（新鲜度 **current**）
- **记录版本**：1.11　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Eq. (12.123)/(12.124) 的被积函数与积分，三项分取；U 以解析导数的 jet 进来，全程无差分

**参考**：Freidberg, *Ideal MHD* (Cambridge, 2014), §12.8.2–12.8.3, Eqs. (12.123)–(12.124), (12.141)–(12.147)

> 表面电流极限下 (12.142)/(12.143)，代 (12.146) 的三谐波试探函数得 (12.147)：无自由参数。

**口径与适用域**：

> 高 β 托卡马克序、$n\sim1$（Eq. 12.117）、圆截面 $r<a$、大环径比 $d\mathbf r=2\pi R_0dA$。★**不许**与 `FR-EQ-018` 的 $n\gg1$ 互相外推；$\delta W_F>0$ **不许**单独断稳。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-fluid-high-beta-headroom.svg
:alt: mhd-energy-fluid-high-beta 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 闭合到 Eq. (12.147)（差恒为零，无自由参数） | 1e-14 | machine_precision | 极化取 3×3，加两组 ξ 直接对 (12.147)：最劣相对 **5.625e-15** | **成立** |
| $\mathbf Q_p$ 退化到 Eq. (12.142)；$\delta W_F$ 退化到 Eq. (12.143) | — | reference_self_reported | (12.143) 右边另起一套求积 | **成立** |
| 直角坐标独立复算（钉住基矢转动项） | 1e-14 | machine_precision | 复多项式 U、非均匀 $\mathbf B_p$，四个点：最劣相对 **2.288e-16** | **成立** |
| 均匀 $\mathbf B_p$ 时第二项严格为零 | — | reference_self_reported | 直角意义上的常矢量 $\mathbf B_p$：极坐标分量的 θ 导数不为零，是 $-B_\theta$ / $+B_r$ 把它抵掉 | **成立** |
| $n^2$ 标度；线弯曲项恒 $\ge0$ | — | reference_self_reported | $\mathbf B_p=0$：$E(n{=}2)/E(n{=}1)-4=0$，$E(n{=}3)/E(n{=}1)-9=1.07\times10^{-14}$；带 $\mathbf B_p$ / $p'$ / $J_\parallel$、$n$ = 1 · 2、5 组 ξ：线弯曲项最小 1.294e5、虚部逐位为零 | **成立** |
| 表面电流极限无交叉项 | — | reference_self_reported | 三谐波互不耦合——表面电流极限下线弯曲项对 $e^{im\theta}$ 正交 | **成立** |
| 三项可分取；默认网格已收敛 | — | reference_self_reported | 非多项式 $U=0.5(e^r-1)e^{i\theta}$、带 $\mathbf B_p$ / $p'$ / $J_\parallel$：线弯曲 2.56e6、压强 −0.400、电流 −5.23 | **成立** |
| 半给极向场 / 粗网格 / 非整数 $n$ fail-loud | — | reference_self_reported | `FLUID_HALF_GIVEN_FIELD` · `FLUID_COARSE_GRID`（径向 < 8 或极向 < 16）· `FLUID_NON_INTEGER_N` | **成立** |

**★二次型逐元对 $n^2\,\mathrm{diag}(2,1,2/3)$，$n$ = 1 · 2 · 3 最劣 5.6e-15**

- ★**是数值闭合，不是符号推导**：被积函数在 $\rho$ 上是多项式、在 θ 上是三角多项式，Gauss 16 点 × 梯形 32 点对它**精确**，所以残差只剩舍入。判据说「差恒为零」，这里的「零」是机器精度的零；上游用 SymPy 做过符号那一步，本仓没有。

**★均匀场第二部分**逐位为零**；成对：非均匀 0.48，漏掉转动项的写法在均匀场上 0.61**

- ★这条恒等式**只有带着转动项才成立**——所以它和直角坐标复算一起，是「方向导数须含基矢转动项」的两道门。

**★三项各自非零；缺省网格（32 × 64）对加倍 2.9e-15**

- ★头一版取 $U=e^re^{i\theta}$：轴上不单值，$|\nabla U|^2\sim1/r^2$，积分对数发散——「网格不收敛」是题错了，不是实现错了。换成轴上正则的函数后到 2.9e-15。
- ★结构恒等式另验：$\mathbf B_p=0$、$J_\parallel$ 为常数时电流项经 Stokes 化为纯边界项，体积分对一维边界积分到 13 位——**同时钉住这一项的符号与系数**。

## 不可比的部分

- ★★**判决成立**：八格全过，第一格是数值闭合而非符号闭合，照实记。
- ★SRS 此条后来又增了 (g) 表面项一般式、(h)–(m) 内部 U 极小化等条款；表面项一般式落在 `FR-EQ-024` 那条里用到了，内部极小化**本条没做**。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.11　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-022` 判**成立**。内核新模块 `fluid.rs`：Eq. (12.123)/(12.124) 三项分取，极坐标方向导数含基矢转动项。(12.147) 闭合 5.6e-15（数值闭合，非符号）；直角坐标复算 2.3e-16；均匀 B_p 第二部分逐位零、漏转动项的写法 0.61；Stokes 恒等式 13 位。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.11 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@0f7e5af3b3cf`（库 `sha256:ac8204aa49349cc0ac53b3b5f9d7b91630ce4d69380fc7aa37034c89ce54dfe8`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/fluid_energy.json`    `sha256:53677b27c2fa710e0b0d5954e1e44019b6138accfcd49c5af5a03eb33307fb36`    (12.147) 闭合、(12.142)/(12.143) 退化、直角复算、均匀场恒等式、n²、三项、网格、Stokes、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::the_surface_current_limit_closes_on_12_147` —— 第一、六格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::q_p_reduces_to_12_142` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::delta_w_f_reduces_to_12_143` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::the_cartesian_route_agrees` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::a_uniform_poloidal_field_leaves_no_second_part` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::line_bending_scales_as_n_squared_and_is_never_negative` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::the_three_terms_come_apart_and_the_default_grid_is_converged` —— 第七格
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::with_constant_current_the_current_term_is_a_boundary_integral` —— ★附：Stokes 结构恒等式
- `$FYLITE_KERNEL/rust/fylite/src/fluid.rs::tests::half_a_field_a_coarse_grid_and_a_fractional_n_are_refused` —— 第八格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
