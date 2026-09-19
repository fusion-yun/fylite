---
title: "mhd-vertical-coil-forces-analytic"
---

# 线圈受力：**四条锚全钉牢了，而没有第二套实现说过话**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-vertical-coil-forces-analytic.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [竖直稳定性、线圈受力与电磁线性模型](../domains/mhd/vertical.md)　|　记录正本：`records/mhd-vertical-coil-forces-analytic.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：线圈受力：**四条锚全钉牢了，而没有第二套实现说过话**
- **参考**：闭式解（判据点名的三条锚 + 牛顿第三定律 + 远场偶极极限） · DINA PF scenario database（`B_*` / `Fr_*` / `Fz_*` 列）
- **验的需求**：`FR-EQ-014`
- **跑在内核**：`fylite_kernel@94ca1a29d6ed`（新鲜度 **current**）
- **记录版本**：1.18　**评审**：草稿　**日期**：2026-09-17

## 问的是什么

**被量的**：2026-09-17 新写：此前内核里受力计算一处都没有

**参考**：闭式解（判据点名的三条锚 + 牛顿第三定律 + 远场偶极极限）

> ★判据点名：单环自感环向力 · 双环互感力 $\mathrm{d}M/\mathrm{d}z$ · 环心场 $\mu_0I/2R$ · 系统 $F_z$ 合力为零。★★本条**自己加了一条**：远场偶极极限——理由写在第②格的 finding 里，那一格按构造近乎恒真，需要一条不与实现共享代数的锚来补。

**参考**：DINA PF scenario database（`B_*` / `Fr_*` / `Fz_*` 列）

> ★**本机没有**：`fydoc/third_party/DINA-IMAS.md` 只是一份代码说明，全仓没有带这些列的数据。判据点名的这一半因此**未评**，不拿别的数字冒充。

**口径与适用域**：

> 轴对称矩形（EFIT 平行四边形）导体、无等离子体。★**不含等离子体对线圈的作用力**——那要等离子体电流分布，是另一扇门的事。★受力是**每元件**的净值，判据若指的是每匝或每线圈，需要先折叠（元件到通道的映射在设备卡里）。★表面场的有效性见它自己那一格：相对比较可用，绝对值不可。

## 判据与量到多少

:::{figure} ../figures/mhd-vertical-coil-forces-analytic-headroom.svg
:alt: mhd-vertical-coil-forces-analytic 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 单环自感环向力对闭式解 | 0.05 | analyst_declared | $R = 1.8$ m、截面 5 × 5 cm、$I = 1$ MA、12 × 12 细丝：fylite **3.435715e6 N**，闭式解 $\tfrac{\mu_0I^2}{2}[\ln(8R/a)-3/4]$（$a$ 取等面积半径）**3.446532e6 N**，相对 **−3.138e-3** | **成立** |
| 双环互感力对 `$I_1I_2`\,\mathrm{d}M/\mathrm{d}z$ | 1e-05 | reference_self_reported | 两个共轴环（$R = 1.5$ m、间距 0.3 m、$I_1 = 7\times10^5$、$I_2 = -3\times10^5$ A）：$F_z$ **1.263273e6 N**，`$I_1I_2`\,\mathrm{d}M/\mathrm{d}z$（元件级互感中心差分）**1.263273e6 N**，相对 **+3.861e-8**；反号电流相斥，符号自洽 | **成立** |
| 环心场对 $\mu_0I/2R$ | 0.0001 | reference_self_reported | $R = 1.2$ m、$I = 5\times10^5$ A，$\mu_0I/2R = 2.617994\mathrm{e}{-1}$ T。在 $r/R$ = 1e-2 / 1e-3 / 1e-4 处读得 **+7.501e-5 / +7.545e-7 / +1.550e-8** | **成立** |
| 系统 $F_z$ 合力为零 | — | machine_precision | 四环合成算例：合力 −3.405e-9 N 对最大单件 7.332e5 N，相对 **4.64e-15**。★EAST #137985 的 14 件 PF 元件、真实安匝：细丝 4 × 4 / 8 × 8 / 16 × 16 三档相对 **+2.74e-14 / +2.21e-14 / −1.78e-14** | **成立** |
| ★远场偶极极限（本册自加的独立锚） | 0.005 | analyst_declared | 两个小环（$a = 5$ cm）沿轴分开，对 $F_z = 3\mu_0m_1m_2/(2\pi d^4)$：$d$ = 1.0 / 1.5 / 2.0 / 3.0 / 4.0 / 6.0 / 8.0 m 上相对 **−1.14e-2 / −4.54e-3 / −2.12e-3 / −3.89e-4 / +2.17e-4 / +7.22e-4 / +5.96e-4** | **成立** |
| 系统 $F_z$ 合力为零 | — | machine_precision | EAST 14 件 PF 元件：环向项 **14/14 全向外**；但 #6 / #13（$R = 3.27$ m，仅 0.018 / 0.021 MA·t）的**净**径向力 **−0.0058 / −0.0063 MN** 向内，而它们自身的环向项只有 **+0.0011 / +0.0015 MN**——内侧那摞的互吸大约五倍。最大件：#9 径向 +5.95 MN、#11 轴向 +3.89 MN | **成立** |
| 系统 $F_z$ 合力为零 | — | machine_precision | EAST PF 峰值 $\|B\|$：细丝 4 × 4 / 8 × 8 / 16 × 16 上 **2.8070 / 2.8079 / 2.8081 T**，散布 **3.9e-04**（中位 2.085 T @ 8 × 8）。★改前（半格外的细丝采样）2.548 / 2.679 / 2.744 T，散布 7.1 %。★内核锚：10 cm 方导体外侧面中点 3.197797 T，求积 24 / 48 阶差 3e-7，外侧细丝（256 × 256）线性外推到面上 3.197151 T（2e-4），峰值与细丝数逐位无关 | **成立** |
| 对拍 DINA PF scenario database 的 $B$ / $F_r$ / $F_z$ 列 | — | reference_self_reported | FreeGS4E `Coil.getForces`（互作用 I×B、Green 函数场；自力 Garren & Chen 1994）对本仓虚功 $I_aI_b\nabla M$，EAST #137985 卡片 14 件、同一个单丝几何（nu = nv = 1，细环自感半径 $\sqrt{wh/\pi}$ 两边相同）：F_r 最劣 **6.7e-12**、F_z 最劣 **6.0e-12**（相对最大单件）；净径向力向内的两件（#6 / #13，外侧弱励磁）两边一致 | **成立** |

**`单环自感环向力对闭式解`** — ★5 % 是本册自立的口径：闭式解里的截面等效半径对**圆**截面成立，而元件是方的，两者的几何均距之差本来就在百分之几。实测好一个量级。

**`系统 $F_z$ 合力为零`** — ★★这不是收敛判据，是牛顿第三定律——不成立就是符号或配对错了，不是解得不够好。所以卡在机器精度，不卡工程容差。

**★单环环向力对闭式解差 3.1e-3**

- ★★**环向力走的是虚功，不是 $I\mathbf{L}\times\mathbf{B}$**：后者要导体**处**的场，而自场恰在那里发散。写成 $(I^2/2)\,\mathrm{d}L/\mathrm{d}R$ 之后，奇异的那一块正好是自感本身，而自感这个实现早就有了闭式的细丝自项——**奇点被关进一个已经有人守着的盒子里**。
- ★**单环没有轴向力，而这里连这一项都没有形成**：一个环自己的场推不动它沿自己的轴走。这句话因此是结构性的，不是一次可能漂掉的相消。

**★★双环力对 $\mathrm{d}M/\mathrm{d}z$ 差 3.9e-8——**但这一格按构造近乎恒真****

- ★★**照实说**：`coil_forces` 算的**就是** $I_aI_b\nabla M$，所以这一格不是一次独立检验。它仍值得留着——它守的是**元件级的 $\mathrm{d}M/\mathrm{d}z$ 与丝级求和可交换**，以及每根丝分到的电流对：符号错、因子错、丝数除错都会在这里露馅。
- ★★**但它挡不住整体的定标错**，所以本册自加了第⑥格（远场偶极极限）——那条闭式解不与实现共享任何代数。★把一格「按构造为真」的判据当成通过的证据，是这一册最容易犯的错。

**★环心场随 $r/R$ 收敛到 1.5e-8**

- ★轴上 $B_Z = (\mathrm{d}\psi/\mathrm{d}r)/(2\pi r)$ 是 $0/0$，所以在小 $r$ 处读、**把收敛本身当成测量**：若近轴行为错了，这个数不会随 $r$ 缩小而稳下来。三档各差两个量级，正是中心差分该有的二阶。

**★★系统 $F_z$ 合力为零：合成算例 4.6e-15，**真装置卡上 2e-14 且三个细丝档都成立****

- ★★**它与细丝多细无关**，这一点本身是证据：抵消来自 $\mathrm{d}M/\mathrm{d}z$ 在交换配对下的反对称性，而不是来自求和求得够准。一个靠精度「凑」出来的零会随细丝档变。
- ★**径向合力不为零，而且不该为零**——环向力是每个环自己对自己的，没有反作用对象。合成算例里也一并验了这一句，免得有人把「合力为零」错推到径向。

**★★远场偶极极限：近场趋近，**而远场有一个数值噪声底****

- ★★**这一支是两段，记在这里因为它是这个实现的一条真限制**：$d \le 3$ m 上负偏差随距离系统缩小，那是有限尺寸的物理修正；再远，$F_z$ 掉了四个量级（3.7e-3 → 9.0e-7 N），`mutual_grad` 的有限差分留下的**绝对**误差变成增长的**相对**误差，符号随之随机（$d = 4$ m 起转正）。**交叉点约 3.5 m**。
- ★★**所以门停在物理那一段，不往更远推**——往远推测到的是步长，不是力。★门也不卡一个固定容差，而是验它**在趋近**：一个算错了的实现可以碰巧落进容差，但它的偏差不会随距离变远而系统地缩小。
- ★这条锚是本册自加的，判据没点名。加它的理由见第②格。

**★环向项与**净**径向力在真机上连符号都不同**

- ★★**这是物理不是缺陷**：环向项按 $I^2$ 走，互吸按 $I_aI_b$ 走，于是弱励磁的外侧线圈上后者必然占优。★**两者因此分开报**（`f_r` 与 `f_r_hoop` 两个场）——只给净值的读者会把它读成环向力算反了。★本条最初的读数脚本正是只看净值，标志报 `false`，查下去才是这件事；那个误判留在这里。

**★表面场**收敛了**：自场改为面积分，4 / 8 / 16 档峰值散布 4e-4（此前 7.1 %）；旧的半格采样低 7–10 %**

- ★★**旧的取样按构造不会收敛，所以换了算法而不是加密**：导体自己的场是对均匀载流平行四边形的面积分，以面上那一点为极点做极坐标 Gauss 求积——环的场近处按 1/ρ 走，乘上面元的 ρ 就有界；θ 在四个角的方向处分段，每段上出射距离光滑。**这里没有细丝数这个旋钮**。
- ★环的场改用椭圆积分的闭式（`loop_field`），而不是互感的定步长中心差分——后者在离细丝 1e-4 以内失准，而求积点恰恰要贴到那里。它在远处对中心差分到 1e-6（锚在内核）。
- ★剩下的 4e-4 来自**其他**线圈的细丝离散（它们离得远，收敛快）；受力的数一位未动（受力本来就不经表面场）。

**★★外部对拍：DINA 无语料，由**第二套实现 FreeGS4E** 代行——14 件线圈 F_r / F_z 对到 7e-12，净向内的外侧线圈两边一致**

- ★★**这是一个替代，用户 2026-09-19 裁定同意**（「同意 FreeGS4E may stand in for DINA」）：判据点名的是 DINA PF scenario database；third_party 的 DINA-IMAS 里没有那份库（只有 ITER 输入，`f_cs` 被注释掉）。这一格要答的是「约定对不对」——四条解析锚共享同一套代数、答不了这一层——而一套**不共享代码**的实现正能答：FreeGS4E 用场与叉乘，本仓用互感梯度，符号、因子、每匝 / 每线圈的口径都得各自对才能对到 1e-11。
- ★两边的环向自力在单丝上是同一个式子（$\mu_0I^2/2\,(\ln 8R/a-3/4)$），所以 F_r 那一半不独立验环向项的模型，只验接线；F_z 全是互作用，是纯的独立对拍。
- ★FreeGS4E 在 uv 临时环境里跑（`tools/freegs4e/coil_forces.py`），不进本仓依赖；门只重算本仓那一侧。
- ★★**2026-09-19 查过 third_party 里的 DINA-IMAS**（ITER Organization，LGPL-3.0）：只有 ITER 场景的**输入**，没有 PF 受力 / 表面场的输出；`src/scenario/forces_for_control.f` 的 `f_cs` 只算 Fr / Fz（无环向项、无表面场），唯一的调用在 `n_matlab_kav2.f:1416` 被注释掉，要的 `koor_pf` 不在仓里，运行还要 IMAS Access Layer。**这一格仍缺语料**。
- ★★**这一格缺的是语料，不是能力**——门已经在，读数格式也定了，一份带这三列的表进来就能对。与 `tr-closure-15d-source-switches` 缺 CD 波源输入是同一类空缺。
- ★★**在它补上之前，本条的判决只能是 inconclusive**：四条解析锚全部钉牢说明**接线**对，但它们都在同一套代数里；一个约定级的错（例如安匝的符号约定、或每匝力与每线圈力的口径）能同时满足全部四条。**只有第二套实现能答这一层。**

## 不可比的部分

- ★★**判成立**（2026-09-19）：解析锚全过、表面场收敛（散布 4e-4）、外部对拍由第二套实现 FreeGS4E 代行（7e-12）。★判据点名的 DINA 没有语料——用 FreeGS4E 代替**经用户 2026-09-19 裁定同意**。
- ★2026-09-17 之前**内核里受力计算一处都没有**（全仓搜 `coil_force` / `hoop` 零命中）。本条同时是这项能力的入册与它的第一次检验。
- ★同域的 `FR-EQ-015`（装置电磁线性模型导出）仍空，且判据原文写着「**待落**（`FYTOK-ADR-119` OI-2）」——那一条等的是上游，不是这里。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-19　版本 1.18　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-014` 从空缺转为记录，判 **inconclusive**。内核新写 `em::coil_forces` / `hoop_forces` / `surface_field` 与门 `code/forces`（此前受力计算一处都没有）。判据点名的四条锚全过：环向力对闭式解 −3.1e-3 · 双环对 $\mathrm{d}M/\mathrm{d}z$ +3.9e-8 · 环心场 1.5e-8 · 系统 $F_z$ 合力 4.6e-15（合成）与 2e-14（真卡，三个细丝档）。★本册**自加**了远场偶极极限一条，因为第②格按构造近乎恒真。★三处照实记下：远场有数值噪声底（交叉点约 3.5 m）· 表面场不收敛（细丝 4→16 散布 7.1 %）· 净径向力在弱励磁外侧线圈上向内（物理，非缺陷；最初的脚本只看净值而误判，留证）。★**对拍 DINA 未评——本机没有那份语料**，而四条锚共享同一套代数、答不了约定对不对，所以判决只能是 inconclusive。★读数原取在 `309d59bfb717…` 上；随后为补齐 wasm 归档又重建了一次（内核**原生代码一字未改**，只是那一次构建把两份 wasm 一并出了），基准随之成为 `4662bd0d5be5…`。★**在新库上重跑了全部 11 道门并重取读数：逐字节相同**——所以这次重盖不是挪一个指纹，是验过了才挪。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.12 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.13 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.14 | 2026-09-19 | Claude Opus 5 (1M context) | 表面场一格转成立：内核 `surface_field_converged`——导体自场改为极坐标 Gauss 面积分（环场用椭圆积分闭式），4 / 8 / 16 档峰值 2.8070 / 2.8079 / 2.8081 T，散布 4e-4（此前 7.1 %，旧值低 7–10 %）。受力逐位不变。DINA 一格查过 third_party 仍无受力输出，未评；整体仍 inconclusive，只剩这一个原因。 |
| 1.15 | 2026-09-19 | Claude Opus 5 (1M context) | 外部对拍一格由未评转成立：DINA 仍无语料，按可推翻的缺省决定由第二套实现 FreeGS4E（`Coil.getForces`：I×B + Garren–Chen）代行——EAST 14 件线圈 F_r / F_z 对到 7e-12，外侧线圈净向内两边一致。整体 inconclusive → pass；用户若要 DINA 的数，回到 inconclusive。 |
| 1.16 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.17 | 2026-09-19 | Claude Opus 5 | 用户裁定同意 FreeGS4E 代替 DINA 作外部对拍——把「可推翻的缺省决定」改记为裁定。判决不变（成立）。 |
| 1.18 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@94ca1a29d6ed`（库 `sha256:d7bb2708e0594700521df0703ab6345fcb232511e39b652ff061c0ecd69d4119`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/coil_forces_east137985.json`    `sha256:8abaf75b57d3adf528ed93422288942f407bcd86b1b68a855bc1d19f469a4e05`    EAST #137985 真实安匝下的逐件受力与表面场，含三档细丝扫描
- `docs/benchmark/readings/coil_forces_freegs4e_east137985.json`    `sha256:4a61259e4a8406afef3fbf65c487700a4a25fde32cc9fcba30b3df9b5fcddb53`    FreeGS4E 第二套实现的逐件受力对照

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::a_single_ring_feels_the_hoop_force_the_closed_form_gives` —— 第①格的锚
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::two_coaxial_rings_push_with_the_gradient_of_their_mutual` —— 第②格的锚（按构造近乎恒真，见 finding）
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::the_field_at_a_rings_centre_is_the_textbook_one` —— 第③格的锚
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::the_set_pushes_on_itself_and_nothing_else` —— 第④格的锚（合成算例）
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::far_apart_rings_become_two_dipoles` —— 第⑥格的锚（本册自加的独立那条）
- `python/tests/test_benchmark_coil_forces.py::test_the_vertical_forces_cancel_over_the_whole_set` —— 第④格在**真装置卡**上的门
- `python/tests/test_benchmark_coil_forces.py::test_the_hoop_term_is_outward_on_every_energised_conductor` —— 环向项符号的门
- `python/tests/test_benchmark_coil_forces.py::test_a_weakly_energised_outer_coil_is_pulled_inward_by_the_stack` —— ★守的是「环向项与净径向力分开报」这件事本身
- `python/tests/test_benchmark_coil_forces.py::test_the_recorded_readings_are_what_this_checkout_computes` —— ★守的是记录里的数不会悄悄过期
- `python/tests/test_benchmark_coil_forces.py::test_the_surface_field_now_converges_with_the_filament_count` —— ★表面场收敛（4e-4）
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::the_converged_surface_field_matches_the_field_just_outside_and_ignores_the_filament_count` —— ★内核：面积分对外侧外推 2e-4、与细丝数无关
- `$FYLITE_KERNEL/rust/fylite/src/electromagnetics.rs::tests::the_loop_field_closed_form_is_the_gradient_of_the_mutual_inductance` —— 环场闭式对互感梯度
- `python/tests/test_benchmark_coil_forces.py::test_a_second_implementation_gives_the_same_forces` —— ★FreeGS4E 对拍（7e-12）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
