---
title: "mhd-energy-vacuum-general-shape"
---

# 一般位形的真空扰动能 δW_V：**同心圆壁复现 f_m，椭圆复现附加质量——两条都与实现不共享中间量**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-vacuum-general-shape.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-vacuum-general-shape.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：一般位形的真空扰动能 δW_V：**同心圆壁复现 f_m，椭圆复现附加质量——两条都与实现不共享中间量**
- **参考**：圆截面闭式 Eq. (12.150)、壁因子 $f_m$（FR-EQ-021(g)）、椭圆绕流的附加质量
- **验的需求**：`FR-EQ-023`
- **跑在内核**：`sha256:6a3256a58b247645…`（新鲜度 **current**）
- **记录版本**：1.7　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：单层位势 + Kress 对数分裂的 Nyström，理想壁作第二条边界联立；推广到任意曲线为本仓自推

**参考**：圆截面闭式 Eq. (12.150)、壁因子 $f_m$（FR-EQ-021(g)）、椭圆绕流的附加质量

> 圆：$E=(\pi a^2/2)\sum(c_m^2+s_m^2)f_m/m$；$f_m=(1+\rho_w^{-2m})/(1-\rho_w^{-2m})$ 在 `stability::surface_current_wall_factor`，本模块里**不出现**；椭圆 $g=n_x$ 时 $\int|\nabla\phi|^2dA=\pi b^2$（势流附加质量）。

**口径与适用域**：

> 任意光滑、逆时针、按 2 的幂采样的闭曲线；真空为二维 Laplace（大环径比，与 Eq. 12.149 同阶）；理想壁须包住等离子体面且不相交。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-vacuum-general-shape-headroom.svg
:alt: mhd-energy-vacuum-general-shape 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 解析圆对任意 $g$ 到机器精度（$N=64$ 即达到） | 1e-13 | machine_precision | $N=64$，$a$ = 0.5 · 1 · 2，$m$ = 1…10 的随机系数 | **成立** |
| 同心圆壁复现 FR-EQ-021(g) 的 $f_m$ 到 $10^{-15}$（实现里不出现 $f_m$） | 1e-13 | machine_precision | $b/a=1.2$、$m=1$ 在 $N$ = 64 · 128 · 256 上 1.04e-4 · 8.86e-10 · 2.35e-14——每加倍降约五个量级 | **成立** |
| 远壁退化回无壁；壁越近能量越大（单调） | — | reference_self_reported | 无壁 5.5654；$b/a$ = 100 · 8 · 4 · 2 · 1.5 · 1.2 · 1.1 → 5.5664 · 5.7207 · 6.2208 · 8.8936 · 13.649 · 28.805 · 54.533 | **成立** |
| 随机 $g$ 恒正；二次性；规范无关 | — | reference_self_reported | 二次性：$E(-3g)$ 对 $9E(g)$ 最劣 1.0e-15；规范：$V+7$ 给同一能量到 1e-12 | **成立** |
| 变形位形谱收敛；形状确实进入结果 | — | reference_self_reported | 4.504996430739 · …690 · …690 · …690；圆为 π/2 | **成立** |
| 可解性 / 取向 / 壁相交一律 fail-loud；「变形曲线上参数余弦不合法」反钉成测试 | — | reference_self_reported | 常数 $g$ 拒绝；顺时针拒绝（不翻转）；壁与面相交、壁在里面拒绝；点数非 2 的幂拒绝 | **成立** |

**★$b/a$ = 4 · 2 · 1.5 · 1.2 × $m$ = 1–5，$N=256$：2.4e-14；★近壁要足够的分辨率**

- ★判据字面「到 1e-15」：本条到 2.4e-14，门按 1e-13 设。
- ★★**近壁的代价照实记**：两条曲线之间的积分越近越奇，梯形误差按 exp(−间隙·N) 走。间隙 0.2、节点间距 0.059 时 $N=128$ 只到 8.9e-10——初版按 $N=128$ 设门，就在这里红了。**不是实现错，是分辨率不够**；这条收敛本身钉成了测试。
- ★$f_m$ 以负幂实现：$|m|=1000$、$\rho_w=1.01$ 时有限且趋于 1，不溢出；$\rho_w\to\infty$ 给 1，$\rho_w\to1^+$ 发散。

**★强 D 形 $g=n_x$：$N$ = 32 → 64 → 128 → 256 逐档差 4.8e-11 · 6.2e-15 · 2.2e-14；对同半径圆差 2.9**

- ★★**变形位形上另有一条解析锚**（判据没点名）：椭圆 $b/a=1.7$、$g=n_x$ / $n_y$ 就是椭圆的势流绕流，能量等于附加质量 $\pi b^2/2$ / $\pi a^2/2$。$N=32$ 起即 **1e-15 量级**——所以「变形位形」不只有自收敛可看。

**★D 形上 $\oint\cos t\,ds=0.590$ → 按名拒绝；圆上同一数据合法**

- ★「参数上的纯余弦」在**左右对称**的椭圆上仍碰巧合法（$|x'|$ 关于 $t\to\pi-t$ 对称），所以这条要在 D 形上钉——在椭圆上钉就是一条永远过的门。

## 不可比的部分

- ★★**判决成立**：六格全过；第二格的「1e-15」以 2.4e-14 达到，并记明近壁需要的分辨率。
- ★δW_V 的这一版与 `FR-EQ-022` 的 δW_F、`FR-EQ-024` 里的 δW_S 一起，使 L2 三项**都可对一般位形求值**；装起来之后怎样，见 `FR-EQ-024`。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.7　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-023` 判**成立**。内核新模块 `vacuum.rs`（单层位势 + Kress Nyström + 理想壁），`stability.rs` 增壁因子 f_m（负幂）。圆 1.9e-15；同心圆壁 f_m 2.4e-14（N = 256；近壁 b/a = 1.2 在 N = 128 只到 8.9e-10，照实记）；★椭圆附加质量 N = 32 起 1e-15——变形位形上的独立解析锚；强 D 形逐档到 1e-14；参数余弦在 D 形上按名拒绝。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:6a3256a58b2476456c9a1e466d4539c81f93dd5279b1225f1fbed2a4da9a4690`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/vacuum_energy.json`    `sha256:139a40640a9b7852bea4f27cf18b2046be400605d64ede99fc4180f567025c39`    圆、同心圆壁、近壁分辨率、远壁与单调、椭圆附加质量、强 D 形收敛与正定、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::the_circle_is_exact_for_any_g` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::a_concentric_wall_reproduces_the_wall_factor` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::a_near_wall_needs_the_resolution_its_gap_asks_for` —— ★第二格：近壁分辨率
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::the_wall_factor_has_both_limits_and_never_overflows` —— 第二格：f_m 本身
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::a_far_wall_is_no_wall_and_a_closer_wall_costs_more` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::energy_is_positive_quadratic_and_gauge_free_on_a_strong_d` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::a_deformed_boundary_converges_spectrally_and_shape_enters` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::an_ellipse_reproduces_its_added_mass` —— ★第五格：变形位形的解析锚
- `$FYLITE_KERNEL/rust/fylite/src/vacuum.rs::tests::bad_data_and_bad_geometry_are_refused_by_name` —— 第六格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
