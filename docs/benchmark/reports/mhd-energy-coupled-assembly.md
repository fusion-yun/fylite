---
title: "mhd-energy-coupled-assembly"
---

# 环几何耦合的组装机器 B2：**第 k 阶谐波只连 |m − m′| = k，只给 k = 0 时块间逐位为零**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-coupled-assembly.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-coupled-assembly.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：环几何耦合的组装机器 B2：**第 k 阶谐波只连 \|m − m′\| = k，只给 k = 0 时块间逐位为零**
- **参考**：`(1 + ε cos θ)^{-2}` 的精确 Fourier 级数与 FR-EQ-019 的柱极限
- **验的需求**：`FR-EQ-020`
- **跑在内核**：`sha256:3250d2a411eae26a…`（新鲜度 **current**）
- **记录版本**：1.6　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：θ-Fourier 谐波 + 耦合 m 谱的带状有限元组装；**组装层不含任何 δW 系数表达式**，系数由调用方逐谐波注入

**参考**：`(1 + ε cos θ)^{-2}` 的精确 Fourier 级数与 FR-EQ-019 的柱极限

> `(a + ε cos θ)^{-1}` 的闭式对 a 求导得 `1/R²` 各阶谐波的精确值；首谐波 −2ε + O(ε³)。退化验收对 FR-EQ-019 的 marginal。

**口径与适用域**：

> θ 均匀采样的实值度规量；耦合只用 cos 谐波（上下对称位形），sin 谐波作自检返回——**上下不对称位形的复耦合不在本机器内**。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-coupled-assembly-headroom.svg
:alt: mhd-energy-coupled-assembly 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| $1/R^2$ 首谐波对 $-2\varepsilon$ 的解析锚 | — | reference_self_reported | ε = 0.05 · 0.1 · 0.2 · 0.3、$k\le6$、128 点：对精确级数最劣 **4.163e-15**；$c_1+2\varepsilon$ 在 ε = 0.2 · 0.1 · 0.05：2.526e-2 · 3.038e-3 · 3.762e-4 | **成立** |
| 零测试：只有 $k=0$ 时跨块严格为 0 | — | reference_self_reported | 模 1–4，只注入 $k=0$ 谐波：块间最大元 **0**（`assert_eq!`） | **成立** |
| 第 $k$ 阶只连 $\|m-m'\|=k$ | — | reference_self_reported | 块间最大元：(1,2) 60.0 · (2,3) 60.0 · (3,4) 60.1 · (1,3) 14.9 · (2,4) 14.9 · **(1,4) 0** | **成立** |
| 耦合对幅值线性 | — | reference_self_reported | 最劣相对 3.462e-16 | **成立** |
| 组装对称 | — | reference_self_reported | 四模、$k\le3$：非对称 **1.919e-17**（这里不是逐位零——两个方向的乘子次序不同，所以检查本来就能动） | **成立** |
| 单模退化回 FR-EQ-019 | — | reference_self_reported | $m/n=3/1$、$\nu=0.7$、$b/a=2$：2.293741560974357 对 2.293741560974372 | **成立** |
| 上下对称位形 sin 谐波作自检量 | — | reference_self_reported | `theta_harmonics` 照样返回 sin 谐波，不丢 | **成立** |
| 超 Nyquist 拒绝 | — | reference_self_reported | `VAR_BEYOND_NYQUIST` | **成立** |

**★各阶谐波对精确级数 4.2e-15；$c_1+2\varepsilon$ 的残差 ε 减半降 8.3 / 8.1 倍（三阶）**

- ★判据写「对 −2ε 的解析锚」——−2ε 只是首阶。本条对的是**精确**级数（由 $(a+\varepsilon\cos\theta)^{-1}$ 的闭式对 $a$ 求导），另把 −2ε 的残差按 ε³ 降这一件事单独钉住：只对 −2ε 的门在 ε = 0.3 上差 7 %，无从区分「对」与「差不多」。

## 不可比的部分

- ★★**判决成立**：八格全过。交付的是**机器**：几何谐波 + 耦合组装。环几何 δW 的系数表达式不在这里，由 `FR-EQ-022` 的被积函数给。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.6　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-020` 判**成立**。`variational.rs` 增 θ 谐波提取与耦合 m 谱的带状组装（节点主序，带宽 2M−1，惯性二分取 λ_min）。1/R² 谐波对精确级数 4.2e-15、−2ε 残差三阶；只给 k = 0 块间逐位零、k ≤ 2 时 (1,4) 块仍为零；线性 3.5e-16；单模退化对 B1 差 1.5e-14。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:3250d2a411eae26a58930a6c611468d94724d3610dcef2da735a6c6ab3418338`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/coupled_assembly.json`    `sha256:cf3ca45484b1f422de9e1bf2fb5615ebbec9f07ed535ebba91994a5596d1ff2a`    1/R² 谐波、零测试、只连 |Δm| = k、线性、对称、退化、sin 自检、Nyquist

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::the_first_harmonic_of_inverse_r_squared_is_minus_two_epsilon` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::with_only_k_zero_the_blocks_do_not_talk_and_order_k_only_links_delta_m_k` —— 第二、三格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::coupling_is_linear_in_the_harmonic_amplitude` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::the_coupled_assembly_is_symmetric_and_the_check_can_fail` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::a_single_mode_with_only_k_zero_is_the_cylinder_again` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::sine_harmonics_are_returned_as_a_self_check` —— 第七格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::orders_beyond_nyquist_are_refused` —— 第八格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
