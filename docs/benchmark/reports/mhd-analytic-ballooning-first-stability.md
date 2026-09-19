---
title: "mhd-analytic-ballooning-first-stability"
---

# 气球模第一稳定边界：**截断误差严格按 1/N 走，于是它能被外推掉**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-analytic-ballooning-first-stability.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界](../domains/mhd/analytic.md)　|　记录正本：`records/mhd-analytic-ballooning-first-stability.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：气球模第一稳定边界：**截断误差严格按 1/N 走，于是它能被外推掉**
- **参考**：s-α 模型的教科书性质（Connor · Hastie · Taylor 1978）
- **验的需求**：`FR-EQ-018`
- **跑在内核**：`sha256:6a3256a58b247645…`（新鲜度 **current**）
- **记录版本**：1.9　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：s-α 气球模方程的打靶解

**参考**：s-α 模型的教科书性质（Connor · Hastie · Taylor 1978）

> α = 0 必稳；第一稳定边界 $\alpha_c(s)$ 随剪切单调升；大剪切端 $\alpha_c\approx0.6\,s$。★这一格没有一个能到 1e-10 的闭式——判据给的是**性质与区间**，本条照它验。

**口径与适用域**：

> s-α 模型（圆截面、大环径比、局部）、偶模、Newcomb 节点判据。★**不含**形状效应、有限 $n$ 修正与第二稳定区——判据只问第一稳定边界。★截断 $\theta_{max}=N\pi$，每 π 200 步 RK4。

## 判据与量到多少

:::{figure} ../figures/mhd-analytic-ballooning-first-stability-headroom.svg
:alt: mhd-analytic-ballooning-first-stability 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| α = 0 必稳（符号锚） | — | machine_precision | $s$ = 0 · 0.3 · 1 · 2.5 · 5：$S(0)$ **逐位等于 1** | **成立** |
| 边界处打靶量为零且两侧异号 | — | reference_self_reported | $s$ = 0.6 · 1 · 2 · 4：$S(\alpha_c\mp10^{-3}\alpha_c)$ **正 / 负**，$\|S(\alpha_c)\|$ < 1e-6 × 两侧量级 | **成立** |
| $\alpha_c(s)$ 单调增，大剪切端 $\alpha_c/s\in(0.5,0.75)$ | — | reference_self_reported | 截断外推后 $\alpha_c(s)$：$s$ = 0.4 · 0.6 · 1 · 1.5 · 2 · 3 · 4 → **0.35444 · 0.42453 · 0.60855 · 0.87750 · 1.17124 · 1.80573 · 2.48250**，严格单调升；$\alpha_c/s$ 在 $s$ = 3 / 4 上 **0.602 / 0.621**（判据带 0.5–0.75） | **成立** |
| 截断收敛（24 vs 32 差 < 1e-3），并**记明 16 不够** | 0.001 | reference_self_reported | $s=1$、截断 $\theta_{max}=N\pi$：$N$ = 16 · 24 · 32 · 48 → **0.614450 · 0.612466 · 0.611484 · 0.610507**。逐段差除以 $\Delta(1/N)$ = **0.0952 · 0.0943 · 0.0938**（彼此差 < 1.5 %）；Richardson 外推 (16,32) **0.608517**、(24,48) **0.608548**（差 3.1e-5）。判据字面 **24 vs 32 = 9.826e-4 < 1e-3**；★**16 对极限 +0.97 %** | **成立** |
| 域内无跨越时报错，不外推 | — | reference_self_reported | $s=1$ 的边界在 0.61 附近：只扫到 0.5 → `BALLOON_NO_CROSSING`；扫到 1.0 → 照常给出 | **成立** |

**★α = 0 时打靶量**精确**为 1**

- ★α = 0 时方程退化为 $((1+s^2\theta^2)F')'=0$，配上 $F'(0)=0$ 只剩 $F\equiv1$——没有驱动就没有节点。验的是**精确的 1**，不是「接近 1」：一个在零驱动下仍有数值漂移的积分器，会在这里露馅。

**★边界上打靶量为零、两侧异号**

- ★打靶量取 $S(\alpha)=F(\theta_{max})$：无节点时为正，节点刚进入域内时变负——**所以它的零点就是 Newcomb 节点判据的边界**，不是另立的一个判据。

**★★第一稳定边界随剪切单调升，$s=1$ 处 0.6086，大剪切端斜率 0.60 / 0.62**

- ★$s=1$ 处 0.6086 正是教科书 s-α 图上那一点（$\approx0.6$）——**这是一个与实现无关的外部锚**，虽然只到两位。
- ★$\alpha_c/s$ **本身不单调**：0.886（$s$=0.4）→ 0.585（$s$=1.5）→ 0.621（$s$=4）——低剪切端边界弯起来，这是 s-α 第一稳定边界的已知形状。判据只约束大剪切端，所以只在那里验斜率。

**★★截断误差严格 $\propto 1/N$、从上方收敛——**而上游的「16 偏低」在这里是偏高****

- ★★**方向与判据写的相反，照实记**：判据说上游「16 不够，偏低 3.6 %」；本实现的 16 是**偏高 0.97 %**。原因是结构性的：真边界上节点在无穷远，有限 $\theta_{max}$ 要等 α 再大一点、把节点拉进域内才看得见，所以 $\alpha_c(N)>\alpha_\infty$。★**方向不同说明两边的「截断」不是同一个量**——上游的可能是基函数阶数或别的截断，这里无从得知。**不去凑那个 3.6 %**：凑出来的数就不再是测量。
- ★★**1/N 律比「24 vs 32 < 1e-3」有用得多**：后者在这里只以 1.7 % 的余量通过，而且 32→48 同样动 ~1e-3——**单看两档之差不能说明收敛**。律一旦量准，Richardson 一阶消去就是对的那一阶，外推换一对 $N$ 只动 3e-5，这才是收敛的证据。
- ★「记明 16 不够」这一条的实质照做了：16 的偏差被**断言**大于 0.5 %，并记明了方向。
- ★步长不是瓶颈：每 π 100 / 200 / 400 步给 0.6114835896 / …879 / …878，200 步已收敛到 1e-9。**误差全在截断上**。

**★域内无跨越时按名拒绝，扫得到时照常给数**

- ★一个在区间外「延长出来」的边界是编的。★第二半同样要验：拒绝要**精确**，一个见区间就拒的实现能过前一半。

## 不可比的部分

- ★★**判决成立**：五格全过。第四格的字面（24 vs 32 < 1e-3）以薄余量通过，其实质（记明 16 不够）照做，**方向与上游相反且照实记**——本实现的截断从上方收敛，并以 1/N 律刻画到可外推的程度。
- ★这是本域行文所说「尺」的第二格。**`mhd-analytic` 这一域到此清空**（`FR-EQ-017` · `FR-EQ-018` 都已入册）。
- ★门在内核仓，本仓 CI 跑不到——与 `FR-EQ-017` 同一处代价；没有开门的理由也相同：交付面等 `FR-EQ-026`（判据点名气球模 `n_phi` 缺省留空、`growthrate` 留空）。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.9　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-018` 从空缺转为记录，判**成立**——尺的第二格，`mhd-analytic` 域到此清空。内核新写 s-α 气球模的打靶解（偶模、Newcomb 节点判据、打靶量 $F(\theta_{max})$）。α = 0 时打靶量逐位为 1；边界两侧异号；$\alpha_c(s)$ 单调升，$s=1$ 处 0.6086（教科书 ≈ 0.6），大剪切端 $\alpha_c/s$ = 0.602 / 0.621。★★**截断误差严格 ∝ 1/N**（系数 0.0952 / 0.0943 / 0.0938），于是能 Richardson 外推，换一对 N 只动 3.1e-5。★★**方向与判据相反，照实记**：上游写「16 偏低 3.6 %」，本实现的 16 偏高 0.97 %——截断从上方收敛，说明两边的「截断」不是同一个量；不去凑那个数。★**先量后断言**：这一条的断言全是在探测之后写的，不再重演上一条凭直觉写断言的错。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:6a3256a58b2476456c9a1e466d4539c81f93dd5279b1225f1fbed2a4da9a4690`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/ballooning_first_stability.json`    `sha256:dedc4b7a4ef9ff7191b280174c5890de512c8ea7ed8045f504cd6f2b43245f45`    α_c(s) 表、截断梯子与 1/N 系数、外推、符号锚、拒绝两例

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::alpha_zero_is_stable_for_every_shear` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_shooting_quantity_changes_sign_across_the_boundary` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_first_stability_boundary_rises_with_shear_at_the_textbook_slope` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::the_truncation_error_goes_as_one_over_n_and_sixteen_is_not_enough` —— ★第四格：1/N 律、外推稳定、并钉住 16 的偏差与方向
- `$FYLITE_KERNEL/rust/fylite/src/stability.rs::tests::no_crossing_in_the_scanned_domain_is_refused` —— 第五格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
