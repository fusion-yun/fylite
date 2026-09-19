---
title: "mhd-energy-conformal-map"
---

# 星形域到单位圆盘的共形映射：**机器全对，而谱收敛的快慢是形状的事**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-energy-conformal-map.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [能量原理变分内核 L2](../domains/mhd/energy.md)　|　记录正本：`records/mhd-energy-conformal-map.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：星形域到单位圆盘的共形映射：**机器全对，而谱收敛的快慢是形状的事**
- **参考**：共形映射的数学性质（Riemann 映射定理；Theodorsen 积分方程）与判据自带的数
- **验的需求**：`FR-EQ-025`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.15　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Theodorsen 迭代 + FFT 共轭函数，M = 1024；逆映射初值取自边界对应

**参考**：共形映射的数学性质（Riemann 映射定理；Theodorsen 积分方程）与判据自带的数

> 边界落在曲线上、单叶、圆域精确退化、调和函数在共形基上谱收敛——这些与实现无关。★判据给的 6/12/20 模 → 1.3e-2 / 1.1e-3 / 5.7e-5 **没说是哪个形状**。

**口径与适用域**：

> 星形域（$\rho(\theta)>0$ 单值）、Theodorsen 迭代收敛（近圆的形状）、$M=1024$。★强 D 形（κ1.6 δ0.35）仍收敛且单叶，但调和表示的谱收敛慢。★**不含**非星形域与带 X 点的边界。

## 判据与量到多少

:::{figure} ../figures/mhd-energy-conformal-map-headroom.svg
:alt: mhd-energy-conformal-map 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 边界落在 $\Gamma$ 上（判据 1.4e-15） | 1e-12 | machine_precision | $\max_\phi\big\|\|f(e^{i\phi})\|-\rho(\arg f)\big\|$：椭圆 $b/a=1.6$ **6.661e-15**（41 次迭代）；Miller κ1.6 δ0.35 **7.994e-15**（76 次） | **成立** |
| 单叶 | — | reference_self_reported | 强 D 形：$\theta(\phi)$ 严格单调（`theodorsen` 自己也查，不单调即拒绝）；41 × 128 点网格上 $\min\|f'\|$ = **0.7123** | **成立** |
| 往返（判据 2.5e-16，含近边界 0.999） | 1e-12 | machine_precision | 768 个内点（12 半径 × 64 角）加 $\|\zeta\|=0.999$ 一圈 64 点：椭圆 **3.51e-16**，强 D **5.55e-16**；内点像 $\max\|\zeta\|$ = 0.9903 / 0.9928 | **成立** |
| 圆域精确退化为 $f=a\zeta$、边界对应为恒等 | — | reference_self_reported | $\rho\equiv0.7$：1 次迭代，$\|a-0.7\|<10^{-15}$，$g_{k\ge1}$ 逐位 0，$\theta_j$ 逐位等于 $2\pi j/M$ | **成立** |
| ★★共形基谱收敛（6/12/20 模 → 1.3e-2 / 1.1e-3 / 5.7e-5，每档至少降 3 倍），同等模数下优于星形基 > 5× | — | reference_self_reported | 上游算例（fyeq `test_conformal_basis_converges_spectrally_on_a_shaped_domain`）：$r_b=A(1+0.18\cos2\theta-0.07\cos3\theta)$、边界数据 $(0.31-0.12i)e^{i\theta}+(-0.18+0.05i)e^{2i\theta}$，按 $\|c_k\|$ 取前 6 / 12 / 20 个共形模，调和延拓的能量相对差 **1.3136e-2 / 1.0886e-3 / 5.7257e-5**（每档降 12.1× / 19.0×）；两项星形基 3.594e-2，12 个共形模好 **33.0 倍**（判据 > 5×）。★另记（形状依赖）：调和函数 $u=\operatorname{Re}w$ 在 768 内点上的最大误差，N = 6 · 12 · 20：Miller κ1.3 δ0.2 共形 **2.29e-2 · 4.05e-3 · 4.64e-4**，星形 4.37e-2 · 4.37e-2 · 4.37e-2（星/共形 1.9 · 10.8 · 94）；Miller κ1.6 δ0.35 共形 **1.21e-1 · 5.11e-2 · 1.81e-2**，星形 7.10e-2（星/共形 **0.59** · 1.39 · 3.9）。上游：1.3e-2 · 1.1e-3 · 5.7e-5，形状未写 | **成立** |
| 圆域上两基逐点相同 | — | reference_self_reported | $\rho\equiv1$：N = 6 · 12 · 20 两基误差都是 6.1e-15 · 6.1e-15 · 6.2e-15，逐 N 相同 | **成立** |
| ★朴素 Newton 初值跑出单位圆的反证；逆映射像在闭圆盘内 | — | reference_self_reported | 初值 $w/f'(0)$、不设护栏：强 D 形 768 个内点中 **76** 个的迭代出了 $\|\zeta\|\le1$；稳健版（边界对应给初值、出圆步长减半）$\max\|\zeta\|$ = 0.9928 | **成立** |
| 边界谱换算：形变泄漏、圆域不泄漏 | — | reference_self_reported | 共形角上的 $\cos m\phi$ 在几何角上重展开：圆域 $c_m=1$、其余 $\le$ 1.77e-16；强 D 形 $m$ = 1 · 2 · 3 时 $c_m$ = 0.898 · 0.983 · 0.913，模外 $\ell_2$ 泄漏 **0.130 · 0.270 · 0.398** | **成立** |
| 不收敛 / 坏网格 / 负半径 fail-loud | — | reference_self_reported | $M=1000$、$M=8$ → `CONFORMAL_BAD_GRID`；$\rho=\cos\theta$ → `CONFORMAL_NEGATIVE_RADIUS`；3 次迭代封顶 → `CONFORMAL_NO_CONVERGENCE` | **成立** |
| (e) 解析导数链：ζ' = 1/f'、ζ'' = −f''/f'³ ⇒ δW_F 对 U 的两次求导全解析；对 (12.147) 的误差与步长无关；线性组合保持解析性 | — | reference_self_reported | (12.147)：解析链 2.28e-16（SRS 6.7e-16）；中心差分 h/a = 1e-2 / 1e-3 / 1e-4 / 1e-5 / 1e-6 → 6.76e-5 / 6.76e-7 / 6.76e-9 / 6.91e-11 / 1.36e-10；f'' 对 f' 差分收敛比 4.0000（强 D 形）；P = f ⇒ U = w 的 jet 对闭式 3.7e-16；jet(ΣP) = Σ jet(P) 到 1e-15 | **成立** |

**边界落在曲线上 6.7e-15 / 8.0e-15**

- ★判据字面 1.4e-15 是上游在它自己的形状上量的；这里是 5 倍，仍在机器精度量级（$M=1024$ 点上的 FFT 舍入）。门按 1e-12 设，数照实记。

**★★上游算例**复现**：前 6 / 12 / 20 个共形模 1.314e-2 / 1.089e-3 / 5.726e-5（上游 1.31e-2 / 1.09e-3 / 5.73e-5），比星形基好 33 倍；Miller 形上的形状依赖另记**

- ★★**此前判未判，是因为上游的数没写形状**——形状与量都在上游测试里：一个 $\cos2\theta$ / $\cos3\theta$ 的星形域、两个物理角谐波的边界数据、量的是**能量**而不是逐点误差。按它的算例量，三档到三位有效数字。
- ★**参照不用 BEM**：Dirichlet 能量共形不变，圆盘上 $\zeta^k$ 与 $\bar\zeta^{|k|}$ 两两正交、各带 $2\pi|k||c_k|^2$，所以截断误差就是没取的那部分能量占比——比上游的 BEM 参照少一层近似。
- ★★**判据说的「表示」是什么，先要读对**：拿边界 $\rho(\theta)$ 本身比，星形基（就是 $\rho$ 的傅里叶级数）反而远好于共形基——那个读法是错的。判据有意义的读法是**域内调和函数**：$\delta W$ 的真空势是调和的，共形拉回后在圆盘上是 $\operatorname{Re}\sum c_k\zeta^k$；星形基 $(r/\rho)^{|k|}e^{ik\theta}$ 在域内**不调和**，于是停在一个平台上不再下降。本格按后一读法验。
- ★★**谱收敛的速率是形状的事，不是实现的事**：给定精确映射，截断到 N 模的误差由 $f$ 的解析延拓在圆外最近的奇点决定。强 D 形的奇点离单位圆近，所以慢——**任何正确的实现都给同样的数**。所以强 D 形的 2.4× / 2.8× 不是缺陷，照实留作负面结果（门 `a_strong_d_is_where_the_five_fold_drop_is_lost` 把它钉住）。
- ★「> 5×」在温和 D 形的 N=6 上只有 1.9×，N=12 起才 > 5×——照实记。
- ★★**判未判**：上游的 1.3e-2 / 1.1e-3 / 5.7e-5 没有说形状，本条无从复现那三个数；两个形状照实报，谁也不挑出来冒充上游的那个。

**★朴素 Newton 在强 D 形上 76 / 768 个点跑出单位圆；稳健逆映射的像全在圆内**

- ★原型里朴素 Newton 直接给出 NaN——截断级数在圆外发散。**这个反证是判据自己要的**，它说明「初值取自边界对应」不是装饰。

**★★解析链对 (12.147) 2.3e-16，**没有步长可挑**；同一个 U 的差分路随 h 在 6.8e-5 … 6.9e-11 间变动**

- ★(12.147) 那道锚在圆域上（`delta_w_fluid` 的积分域是圆截面），圆域上 f = aζ，链式里 f'' = 0——所以它验的是整条装配与换到 (r, θ) 的那一步，**不单独**验 f''。f'' 在强 D 形上另有两道：对 f' 差分二阶收敛，与 P = f ⇒ U = w 的恒等（那一道里 ζ'' 的项必须与 ζ'² 的项精确相消）。
- ★差分路在 h/a = 1e-6 上掉头（1.4e-10，舍入）：差分要在截断与舍入之间挑一个 h，解析链把这个自由度整个去掉。

## 不可比的部分

- ★★**判成立**（2026-09-19）：十格全过。谱收敛那一格按上游自己的算例复现到三位（1.31e-2 / 1.09e-3 / 5.73e-5），且比星形基好 33 倍；Miller 形上收敛速率随形状从 5.7×/8.7× 降到 2.4×/2.8× 的读数照留——那是数学性质，不是判据的对象。
- ★这一条给 `FR-EQ-023` 的真空能铺路：共形拉回之后真空势在圆盘上是谱收敛的，前提是形状别太 D。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.15　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-025` 从空缺转为记录，判**未判**。内核新写 `conformal.rs`：Theodorsen 迭代 + FFT 共轭函数，逆映射初值取自边界对应。边界 8e-15、单叶、往返 5.6e-16（含 0.999）、圆域逐位退化、两基在圆上相同、边界谱圆域不泄漏、fail-loud——机器八格全过。★★**判据的「表示」要读成域内调和函数**：拿边界本身比，星形基反而更好。★★温和 D 形共形基每档降 5.7×/8.7×、星形基停在 4.4e-2；强 D 形只降 2.4×/2.8×、N=6 还不如星形基——速率是形状的数学性质，留作负面结果。上游的三个数没说形状，无从复现，故判未判。★朴素 Newton 在强 D 形上 76/768 个点跑出单位圆——判据要的反证。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 补 `FR-EQ-025(e)` 解析导数链（新判据格，成立）：`d2f` · `chain_jet` · `poly_jet`；对 (12.147) 2.3e-16 且无步长，差分路随 h 在 6.8e-5 … 6.9e-11 间变动。整体仍判未判（谱收敛那一格不变）。同批内核换代（`e16301fa` → `3b703891`），内核侧 792 项全通过。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 (1M context) | 谱收敛一格转成立：上游的算例在 fyeq 测试里（星形域 1 + 0.18 cos2θ − 0.07 cos3θ、两谐波边界数据、量调和延拓的能量），按它量得 1.314e-2 / 1.089e-3 / 5.726e-5 对上游 1.31e-2 / 1.09e-3 / 5.73e-5，比星形基好 33 倍。Miller 形上的形状依赖另记。整体 inconclusive → pass。 |
| 1.9 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.11 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.12 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.13 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.14 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 ★本条的判据与数值**未改口径**。 |
| 1.15 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`b27d7145ab3e`：新门 `code/icrh`——ICRH 少数离子加热第一次经门可达，`CASE_CODES` 41 → 42，只加不改）。内核侧：`icrh_door` 2 · `fyo` 7 全过。★没有一处既有缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/conformal_map.json`    `sha256:46efa9e6d4d2409c4733b3bcb870d06c6dd5d92c36913496107b48e68daf79e2`    三个形状上的边界、单叶、往返、调和表示两基对比、朴素 Newton 反证、边界谱、拒绝
- `docs/benchmark/readings/conformal_derivative_chain.json`    `sha256:2165619b10feee471b40b44a0d72603869efbbe8a5fd5d18989abc455874b8e1`    (e) 解析导数链：(12.147)、差分路、f''、恒等、线性
- `docs/benchmark/readings/conformal_upstream_case.json`    `sha256:1bc0441390bd8df34e8d14a507597186b0c4dfdeec699fa38e37cf4503802d5a`    上游算例的形状、边界数据与复现读数

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_boundary_lands_on_the_curve` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_map_is_univalent_on_the_disk` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_robust_inverse_round_trips_up_to_the_edge` —— 第三格与第七格后半
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_circle_degenerates_exactly` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::a_harmonic_function_converges_spectrally_only_in_the_conformal_basis` —— 第五格：温和 D 形
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::a_strong_d_is_where_the_five_fold_drop_is_lost` —— ★第五格：强 D 形的负面结果
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::both_bases_coincide_on_the_circle` —— 第六格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::naive_newton_leaves_the_disk` —— ★第七格：反证
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_boundary_spectrum_leaks_only_on_a_deformed_domain` —— 第八格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::bad_input_is_refused_by_name` —— 第九格
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::f_second_derivative_is_the_limit_of_differenced_f_prime` —— (e) f''
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_chain_turns_p_equal_f_into_u_equal_w_exactly` —— (e) P = f ⇒ U = w
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_analytic_chain_lands_on_12_147_with_no_step_to_choose` —— ★(e) (12.147) 与差分路
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_poly_basis_keeps_its_derivatives_through_a_linear_combination` —— (e) 线性组合
- `$FYLITE_KERNEL/rust/fylite/src/conformal.rs::tests::the_upstream_spectral_convergence_case_is_reproduced_on_its_own_shape` —— ★上游算例三档 + 星形基对照

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
