---
title: "mhd-energy-variational-cylinder"
---

# 能量原理变分内核 B1：**两条完全不同的数值路线给同一个带边**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-variational-cylinder.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-variational-cylinder.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：能量原理变分内核 B1：**两条完全不同的数值路线给同一个带边**
- **参考**：柱极限外扭曲模的解析带边与 FR-EQ-017 的打靶路
- **验的需求**：`FR-EQ-019`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.12　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：线性元装配 → 边界项 → 广义本征值（惯性二分）→ marginal 求根

**参考**：柱极限外扭曲模的解析带边与 FR-EQ-017 的打靶路

> 均匀电流下带边闭式 `(m−1+λ)/n`；峰化剖面上没有闭式，对打靶路（`stability::kink_marginal`，3201 点 RK4）。★两路共用同一条欧拉方程，数值路线完全不同。

**口径与适用域**：

> 柱几何、单 $m$、无 $m$ 谱耦合、无环效应压强驱动——**不是** β 极限。线性元、4 点 Gauss、$\psi(0)=0$。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-variational-cylinder-headroom.svg
:alt: mhd-energy-variational-cylinder 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 变分路 marginal $q_a$ 复现解析带边 | 0.0001 | reference_self_reported | 均匀电流、400 单元：$(m,n)$ = (2,1)(3,1)(3,2)(4,1) × $b/a$ = 1.2 · 1.5 · 2 · 4 · ∞，对 $(m-1+\lambda)/n$ **最劣相对 5.208e-7** | **成立** |
| 与打靶路相符（含峰化剖面使内部驱动项真正参与的一档） | 0.0002 | reference_self_reported | $m/n=3/1$：$\nu$ = 0 · 0.3 · 0.7 · 1.2 × $b/a$ = 2 · ∞，FEM 400 单元对打靶 3201 点 **最劣相对 3.91e-7**。$\nu=0.7$ 时拿掉内部驱动项 $rV\psi^2$，marginal 从 2.29374 移到 2.42096（**−0.127**）；$\nu=0$ 时拿不拿掉逐位相同 | **成立** |
| $\mathbf A$ 对称（$10^{-14}$）且 $\mathbf B$ 正定 | 1e-14 | machine_precision | $\nu$ = 0 / 0.7：非对称 **0**，$\mathbf B$ 最小 Cholesky 主元 1.667e-5 > 0；往一条副对角线注入 1e-12 的相对错，检查读到 1.469e-13；把 $\mathbf B$ 一个对角元翻负，主元转负 | **成立** |
| 二阶收敛（误差比 $\in(3.5,4.5)$） | — | reference_self_reported | 50 · 100 · 200 单元：均匀电流对闭式误差 4.846e-5 · 1.211e-5 · 3.028e-6；$\nu=0.7$ 对 3200 单元 9.393e-6 · 2.347e-6 · 5.849e-7 | **成立** |
| 共振面在域内时拒绝组装 | — | reference_self_reported | $q$ 从 1.9 升到 3.8（$m/n=3$ 在域内）→ `VAR_RESONANT_INSIDE`；整条剖面在 3 之下 → 照常；$\lambda_{min}$ 两端同号 → `VAR_NO_CROSSING` | **成立** |

**★四档剖面 × 有无壁，两路最劣 3.9e-7；★峰化剖面上驱动项真的参与**

- ★判据要「含峰化剖面使内部驱动项真正参与的一档」——这一句要**验**，不是假定：一个只装了边界项的实现在均匀电流上照样全对。所以另设一条测试把驱动项拿掉，看 marginal 动不动。
- ★泛函由打靶路的 Riccati 形读出：对欧拉解分部积分，体积分恰为 $\psi(a)^2u(a)$，于是 $\delta W=\psi(a)^2W(q_a)$——正是打靶路的边缘余量。质量阵 $\int r\psi^2dr$ 只改 λ 的刻度，不改 marginal；**λ 不是增长率**。

**★非对称 0（两条副对角线各自独立装配），且**检查能失败**：注入 1e-12 读到 1.5e-13**

- ★「恒为零」型验收须先证其可非零：这里上下两条副对角线在同一次求积里算出、浮点运算完全相同，所以非对称**逐位为零**——那恰恰说明这条检查若不另行证明能失败，就什么也没验。

**共振在域内按名拒绝；在共振之下照常组装；同侧区间不给根**

- ★共振在**节点与每个求积点**上查：节点之间过零也要抓到。

## 不可比的部分

- ★★**判决成立**：五格全过。这是 L2 唯一**不依赖任何外部数据**的整体校验，环几何之前必须过。
- ★门在内核仓，本仓 CI 跑不到——同 `FR-EQ-017` / `018`。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.12　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-019` 判**成立**。内核新模块 `variational.rs`：线性元装配、惯性二分取 λ_min、marginal 求根。带边对闭式最劣 5.2e-7，两路互证最劣 3.9e-7，收敛比 4.000 / 4.012。★峰化剖面上拿掉驱动项 marginal 移 0.127——验了「驱动项真正参与」而不是假定它。★对称性逐位为零，所以另证检查能失败。 |
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
| 1.12 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/variational_cylinder.json`    `sha256:4fdb0a32d161bf853044b35a92a5bac05f7dce2391346509d3c8fb2dfe2d6f81`    带边、两路互证、驱动参与、对称与正定、收敛阶、标度、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::the_variational_marginal_reproduces_the_analytic_band_edge` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::the_two_routes_agree_including_a_peaked_profile` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::on_a_peaked_profile_the_internal_drive_really_takes_part` —— ★第二格：驱动项真的参与
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::a_is_symmetric_and_b_is_positive_definite` —— 第三格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::the_symmetry_check_can_fail` —— ★第三格：检查能失败
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::linear_elements_converge_at_second_order` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::a_resonance_inside_the_plasma_is_refused` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/variational.rs::tests::a_is_a_length_scale` —— 附：对 a 标度不变

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
