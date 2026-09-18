---
title: "mhd-energy-surface-current-beta-limit"
---

# 表面电流模型的解析 β 极限：**根是 1.69，而 0.21 属于 1.71**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-surface-current-beta-limit.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-surface-current-beta-limit.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：表面电流模型的解析 β 极限：**根是 1.69，而 0.21 属于 1.71**
- **参考**：Freidberg, *Ideal MHD* (Cambridge, 2014), §12.8, Eqs. (12.154)–(12.166)
- **验的需求**：`FR-EQ-021`
- **跑在内核**：`sha256:e16301fa3acd72ca…`（新鲜度 **current**）
- **记录版本**：1.5　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Freidberg §12.8 三谐波（m = 1, 2, 3；n = 1）的表面电流模型

**参考**：Freidberg, *Ideal MHD* (Cambridge, 2014), §12.8, Eqs. (12.154)–(12.166)

> 书印的 $M_{lp}$ 分数、(12.164) 右端两三位的数值系数、根 1.69、β/ε ≈ 0.21（在 20 谐波的 $q_{crit}=1.71$ 上）、低 β 极限 (12.156) 与 Kruskal–Shafranov (12.157)。★这是 L2 的 **oracle**，不是 L2 本体。

**口径与适用域**：

> Freidberg §12.8 的表面电流模型：圆截面、$n=1$、三谐波 $m=1,2,3$、以 $\xi_2$ 为主谐波对 $\xi_1,\xi_3$ 取极小。★**只在 $D=W_{11}W_{33}-W_{13}^2>0$ 处成立**（$q_*>1.00035$）。★多谐波的 1.71 不在本实现内。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-surface-current-beta-limit-headroom.svg
:alt: mhd-energy-surface-current-beta-limit 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| $M_{lp}$ 级数自算对书印分数 | 1e-12 | machine_precision | Eq. (12.165) Kahan 求和到 $N=10^6$：$M_{11}$ · $M_{22}$ · $M_{33}$ · $M_{12}$ · $M_{23}$ · $M_{13}$ 对 5/4 · 89/36 · 1111/300 · −11/12 · −277/180 · 1/180，**最劣 6.262e-14**（尾巴 ~$1/(16N^2)$） | **成立** |
| 由 $M_{lp}$ 复现 Eq. (12.164) 右端的数值系数（到书印位数） | — | reference_self_reported | 自算 0.0326 · 2.477 · 4.939 · −0.0172 · 1.227 · 0.0111，按书印位数舍入后逐个**等于** 0.033 · 2.48 · 4.94 · −0.017 · 1.23 · 0.011 | **成立** |
| $W(q_*)=0$ 的根复现 1.69；$(\pi/4q_{crit})^2$ 复现 0.21 | — | reference_self_reported | 根 **1.690113**（书印 1.69）；$(\pi/4q)^2$ 在该根上 **0.2159**，在书 (12.166) 的 $q_{crit}=1.71$ 上 **0.2110**（书印 0.21） | **成立** |
| $W$ 的符号方向，阈值附近单调 | — | reference_self_reported | $W(1.2)<0<W(3.0)$；$q_{crit}(1+0.01k)$，$k=-10..10$ 上 $W$ 严格递增 | **成立** |
| $W_{13}$ **无 $\pi^2$ 项** | — | reference_self_reported | $q_*$ = 1.2 · 1.69 · 2.5：对闭式相对差 < 1e-15；照 $W_{12}$ / $W_{23}$ 的样子多抄一个 $-3\pi^2/16q_*^2$ 会差 > 0.1——两个版本**分得开** | **成立** |
| 低 β 极限无交叉项、Kruskal–Shafranov 阈值、$m=2,3$ 系数恒正 | — | reference_self_reported | $q_*$ = 0.8 · 0.99 · 1.01 · 1.5 · 2 · 3 · 5：$c_1>0 \iff q_*>1$；$c_3>0$；$c_2\ge0$，**$c_2(2)=0$ 逐位** | **成立** |
| `source` 非空且含节号式号 | — | reference_self_reported | 含 `Freidberg`、`12.8`、`(12.154)`、`(12.166)` | **成立** |
| 区间不变号时 fail-loud | — | reference_self_reported | (2, 3)：`SURFACE_CURRENT_NO_CROSSING`；(1.0, 1.5)：两端异号，而 `SURFACE_CURRENT_OUTSIDE_DOMAIN`；(1.2, 3.0) 照常给根 | **成立** |

**★$M_{lp}$ 六个分数全部复现，最劣差 6.3e-14**

- ★书只印了分数，没印级数怎么求——级数是按 (12.165) 自己求的。分数对上，说明读页没有抄错式子的分母。

**(12.164) 右端 $1/q_*^2$ 系数六个全对到书印位数**

- ★判据是「到书印位数」而不是一个容差：书印两三位，比容差更能说明哪一位错了。

**★★三谐波根 1.690113；**0.21 是在 1.71 上算的，不是在 1.69 上****

- ★★**判据里藏着一个陷阱**：「根复现 1.69」和「$(\pi/4q_{crit})^2$ 复现 0.21」看起来是同一个 $q$，其实不是。书先用三谐波得 1.69，再说多谐波收敛到 1.71，0.21 是用 1.71 算的。在 1.69 上它是 0.216——舍入到两位是 0.22，**对不上**。照实记两个数，不去把 1.69 挪向 1.71。
- ★本实现只有三谐波，所以 1.71 是**书的数**，不是本实现算出来的；本条验到的是「0.21 ⇔ 1.71」这个算术关系。

**★$W_{13}=4/(15q_*)+2M_{13}/q_*^2$，**没有** $\pi^2$ 项**

- ★「分得开」要验：一个在 $q_*$ 很大时才探的门，会让两个版本都过。

**低 β 极限：Kruskal–Shafranov，$m=3$ 恒正，★**$m=2$ 在 $q_*=2$ 处恰为零****

- ★**「无交叉项」是结构性的**：(12.156) 只有对角三项、只依赖 $q_*$，实现直接返回这三个系数。这一格验的是它们的值与符号，不是一个量出来的「交叉项为零」。
- ★书说「$m=2$ 与 $m=3$ 的系数都为正」，严格说 $m=2$ 是**非负**、在 $q_*=2$ 有二重零点——边缘，不是不稳。照实钉住。

**★★不变号拒绝；**异号但中间是极点也拒绝****

- ★★**这一半判据没点名，是实测逼出来的**：初版在 (1.0, 1.5) 上二分，报出「根」1.00035——那是 (12.163) 分母 $D=W_{11}W_{33}-W_{13}^2$ 的**零点**，$W$ 在它两侧从 +∞ 跳到 −∞。它离 Kruskal–Shafranov 只差 3.456e-4：$m=1$ 在那里自己就不稳，与 $m=3$ 的环向耦合把边界往上推了一点。(12.163) 是对 $\xi_1,\xi_3$ 取极小，**只在这一块正定处成立**；现在先扫 $D>0$，不满足按名拒绝。

## 不可比的部分

- ★★**判决成立**：八格全过。两处照实记了与字面不同的东西——0.21 属于 1.71 不属于 1.69；$m=2$ 的系数是非负不是正。
- ★这是 L2 的 **oracle**：它给后面 `FR-EQ-019…024` 的变分内核一个有解析答案的对照。本条自己不含变分机器。
- ★门在内核仓，本仓 CI 跑不到——与 `FR-EQ-017` / `018` 同一处代价。
- ★2026-09-18 v1.1：SRS 此条的正文还有 (c') 第二条路、(e) 整条边界、(g) 有壁支，抄录的验证矩阵没点名。三条随 L2 一起补上了门：闭式路在 $k^2=1$ 上由 (12.147)+(12.140)+(12.153) 合成 $W_{lp}$，逐元对 (12.164) 的转录到 7.4e-8（真空谐波截断，按 $1/m_{max}^2$ 降），$\lambda_{min}=0$ 的根 1.690113290 对转录路 1.690113289；整条边界 $k^2\to0$ 给 $q_*\to1$、$k^2=1$ 给 1.690113 且落在平衡极限上；$f_m$ 以负幂实现，$|m|=1000$ 不溢出，并由 `FR-EQ-023` 的边界积分在同心圆上**独立复现**到 2.4e-14。★有壁时的**不稳带**（下边缘出现、带收窄、闭合）本条仍未做。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.5　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-021` 从空缺转为记录，判**成立**——L2 的 oracle。内核新写 Freidberg §12.8 三谐波表面电流模型。$M_{lp}$ 六分数对书最劣 6.3e-14；(12.164) 系数到书印位数全对；根 1.690113。★★**0.21 属于 1.71**：书在 20 谐波的 $q_{crit}=1.71$ 上算的 β/ε，在三谐波根 1.69 上是 0.216——两个数分开钉。★★**极点不是根**：初版二分把 (12.163) 分母的零点 $q_*=1.00035$ 报成了根；现在先要求 $\xi_1$–$\xi_3$ 块正定，否则按名拒绝。★$m=2$ 的低 β 系数在 $q_*=2$ 恰为零，书说「为正」，照实记为非负。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 补 SRS 正文的三条（验证矩阵未点名）：(c') 三式合成 W_lp 对 (12.164) 7.4e-8、两路的根差 1e-9；(e) 整条稳定边界两端；(g) 壁因子 f_m（负幂），由 FR-EQ-023 的边界积分独立复现到 2.4e-14。有壁不稳带仍未做。判决不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e16301fa3acd72ca3bbe19c05775bbc2c4d78fd9e7b5b693f9b8756ce6d8669b`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/surface_current_beta_limit.json`    `sha256:45685caf9ec24d979fe29904a3ff2c6885da5a59e7870a1fe4b116956412d339`    M_lp 对书、(12.164) 系数对书、根与 β/ε、极点、低 β 系数、拒绝三例

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_mlp_series_reproduces_the_printed_fractions` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_matrix_coefficients_reproduce_the_right_hand_side_of_12_164` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_root_is_1_69_and_the_beta_limit_0_21_belongs_to_q_crit_1_71` —— ★第三格：两个 q 分开钉
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::w_is_negative_below_the_threshold_and_rises_through_it` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::w13_has_no_pi_squared_term` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_low_beta_limit_is_the_cylinder_with_the_kruskal_shafranov_threshold` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_source_names_the_section_and_the_equations` —— 第七格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::no_sign_change_in_the_interval_is_refused` —— 第八格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_reduction_holds_only_where_the_xi1_xi3_block_is_positive` —— ★第八格的另一半：极点不是根
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_closed_form_route_rebuilds_12_164_at_k2_equal_one` —— ★(c')：三式合成 W_lp，不经过 12.164
- `$FYLITE_KERNEL/rust/fylite/src/highbeta.rs::tests::the_whole_boundary_has_both_analytic_ends` —— ★(e)：整条稳定边界的两端
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::the_wall_factor_has_both_limits_and_never_overflows` —— ★(g)：壁因子 f_m（负幂）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
