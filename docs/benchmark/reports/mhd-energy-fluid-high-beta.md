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
- **跑在内核**：`sha256:bdd970709d521f7a…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-18

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

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-022` 判**成立**。内核新模块 `fluid.rs`：Eq. (12.123)/(12.124) 三项分取，极坐标方向导数含基矢转动项。(12.147) 闭合 5.6e-15（数值闭合，非符号）；直角坐标复算 2.3e-16；均匀 B_p 第二部分逐位零、漏转动项的写法 0.61；Stokes 恒等式 13 位。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:bdd970709d521f7a0722b9776e188d440a155cf86e567aec5e253f62c1420f45`

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
