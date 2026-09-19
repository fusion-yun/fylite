---
title: "tr-closure-15d-source-switches"
---

# 1.5D 演化：加料 / 加热 / 驱动 / 台基 / 锯齿的开关都进了装配；驱动电流三道开了源就有数

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-closure-15d-source-switches.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [闭包插件面：输运系数与插件接入](../domains/tr/closure.md)　|　记录正本：`records/tr-closure-15d-source-switches.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：1.5D 演化：加料 / 加热 / 驱动 / 台基 / 锯齿的开关都进了装配；驱动电流三道开了源就有数
- **参考**：基线自身（同一算例、只改一个开关）
- **验的需求**：`FR-TR-004` · `FR-TR-009`
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.25　**评审**：草稿　**日期**：2026-09-19

## 问的是什么

**被量的**：能力 `code/evolve`，算例 `evolve-iter-15ma`；逐个打开控件与基线比

**参考**：基线自身（同一算例、只改一个开关）

> ★★**参考是它自己**：一个控件若打开后什么都不变，它就是**死的**——这一条不需要任何外部答案，却抓得住外部对拍抓不到的东西（对拍只会显示两边都「正常」）。★同源判法见 `tr-paradigm-pereverzev` 的「d_pc 真的进了装配」。

**口径与适用域**：

> 能力 `code/evolve`，算例 `evolve-iter-15ma`：31 个径向点 × 400 步，终点 t = 8 s。逐个变体只改**一个**控件，其余与基线逐位相同（参数由同一份 plan 深拷贝后覆盖）。★比较落在 21 个产出量上（剖面取绝对值的最大值，标量取末值）。★★**探针的键表见读数件**：它决定了「改变了几项」这句话的含义——漏列一个量，结论会反过来。

## 判据与量到多少

:::{figure} ../figures/tr-closure-15d-source-switches-headroom.svg
:alt: tr-closure-15d-source-switches 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 能量平衡的最劣残差 | 1e-12 | machine_precision | 最劣残差 **1.583e-13**（基线那档；判据 1e-12）。逐档（2026-09-19，耦合整体求解为缺省之后）：baseline 1.583e-13 · pedestal 1.159e-13 · current 1.583e-13 · density 9.111e-14 · dt_target 1.521e-13。★2026-09-18 更正：原记 1.154e-13 是基线那一档的，不是全部变体里最劣的 | **成立** |
| 每个打开的控件，至少改变一项产出（否则它是死的） | 1 | measured_band | 台基 8 项（含 `t_ped`）· 加料 9 项（含 `ne`/`ni`）· DT 7 项 · 电流道 2 项（`q` 0→3.416、`psi` 0→36.57） | **成立** |
| ★锯齿与 ipctl —— **按名拒绝**，并说明依赖 | — | — | `sawtooth=True` 单开被拒：": "the sawtooth needs the current channel: its trigger is q(0) < 1 and q is a result only where current diffusion is solved \u2014 pass `current=True | **成立** |
| 驱动电流三道（自举 / 外部 CD / LH）是否给得出非零值 | 1 | measured_band | 自举（`bootstrap`）：j_bs 峰值 3.518e+05 A/m²；给定 CD `i_cd` 1 MA / 2 MA：j_cd 峰值 1.598e+05 / 3.196e+05 A/m²，沉积积分 ∫j dA 对所给电流 -1.1e-16 / -1.1e-16，2 MA 恰为 1 MA 的两倍；三档能量平衡 1.58e-13。★LH（j_lh）与束的执行器：内核仓 `tests/test_evolve_executors_code.py` 在 EAST g-file 上逐位对上 `code/wave` / `code/beam`。★此前（开关扫描只开电流道、不给源）：三道恒为 0 | **成立** |
| 算例的默认姿态（读数） | — | — | 基线控件：`pedestal`=False · `current`=False · `ipctl`=False · `sawtooth`=False · `heat`=True · `closure`='constant' · `density`=False · `dt_target`=0.0 · `impurity`='Ne' · `brem`=True · `quasi`=False | **未判（读数）** |

**`能量平衡的最劣残差`** — ★平衡是恒等式，容差取舍入级；它是这一域最硬的一条自证。

**`每个打开的控件，至少改变一项产出（否则它是死的）`** — ★**下限判据**：改变项数 ≥ 1。★这一条守的是「控件接线了」，不是「接得对」。

**`驱动电流三道（自举 / 外部 CD / LH）是否给得出非零值`** — ★★下限判据：每一道**开了自己的源**之后给得出非零值。★2026-09-19 前这一格判 fail——开关扫描的 `current` 档只打开电流道、不给源，三道恒为零；那是算例的姿态，不是内核的缺口。

**能量平衡闭到舍入**

- ★这一条在**每个变体上都成立**：开台基、开加料、开 DT 之后平衡照样闭。**一个改了源项却仍然守恒的求解器，比一个守恒得好看但源项没接线的求解器可信。**

**★台基 / 加料 / DT / 电流道 —— 四个开关都真的进了装配**

- ★★**这一条差点被我误报成缺陷，经过值得留下**：首版探针的键表没列 `q` 与 `psi`，于是 `current=True` 显示「零项改变」——看着就像开关是死的。补上键表后才看见 q 从 0 变到 3.415。**探针的覆盖面本身要当成判据的一部分来审**：漏一个量，结论就反过来。
- ★电流道只改了 `q` 与 `psi`，**温度不受影响**——在本算例的配置下（`closure='constant'`、无外部 CD）这是预期的，但记在这里，好让将来接上欧姆耦合时看得出变化。

**★锯齿与 ipctl —— **按名拒绝**，并说明依赖**

- ★★**这是一条好的拒绝，所以记成成立**：它不是默默给个数，而是点名说「锯齿要电流道，它的触发是 q(0) < 1，而 q 只有在解了电流扩散的地方才是结果」。`ipctl=True` 单开同样按名拒绝。
- ★**一个安静地给出无意义结果的开关，比一个拒绝的开关危险得多**——后者至少让人知道缺什么。

**★★驱动电流三道 —— **成立**（2026-09-19）：开了源就有数，给定 CD 的沉积积分闭合到舍入**

- ★★**此前「恒为零」的原因**：开关扫描的 `current` 档只打开电流扩散，没有给任何一道**源**——`bootstrap`、`i_cd`、LH 功率都是各自的输入。那一档的零现在仍然是零（门照守），它说明的是「开了道不给源就没有电流」，不是「没有这三道」。
- ★2026-09-16 的裁定是「内核欠缺的功能也保留」、下一步「造一个带 CD 源的算例」；这一次造的就是它：`tools/benchmark-evolve15.py` 的 `DRIVEN` 三档，读数 `evolve15_driven_currents.json`。
- ★本格判的是**接线**（源进了装配、积分守恒），不是**物理**：自举系数、CD 效率对外部参照的比较在 `tr-closure` 域的别的记录里。

**算例的默认姿态（读数）**

- ★`evolve-iter-15ma` 默认只开 `heat` 与 `brem`，台基/驱动/锯齿/加料全关。**这是算例的选择，不是内核的缺口**——记在这里，免得读者把「本算例没有台基」读成「fylite 没有台基」。

## 不可比的部分

- ★★**本条验的是「接线了」，不是「接得对」**：一个开关改变了产出，只说明它进了装配，不说明它算的物理对。后者要外部参考——那是 `tr-closure` 域里另外几条记录的事。
- ★**整体判 pass**（2026-09-19 由 inconclusive 改）：平衡、四个开关、驱动三道都成立；锯齿按名拒绝（它依赖电流道），另有一档间接验。
- ★**哪些量是喂进去的**：几何、Ip、边界值、加热功率与沉积、杂质种类与浓度全是输入；算出来的是剖面演化、平衡残差与各源项的空间分布。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.25　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：1.5D 的开关-进装配判法；平衡闭到 1e-13，四个开关成立，驱动三道判 fail；探针漏键差点误报，经过留在 caveat 里 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核同日两次换代后的全册重验（原 1.1 与 1.2 两条，2026-09-18 合并——第二条当时误抄了第一条的摘要）：①`301a962b` → `ac8c0f5c`，`FR-EQ-002/008/010/011` 与 0D 三项入内核（内核仓 `3ea79df`），fylite 侧 110 道、内核侧 656 项全通过；②`ac8c0f5c` → `eb8c9022`，ETS 五型边界、燃烧→密度的接线、时间收敛阶入内核（内核仓 `acd1628`），165 道门禁全过、660 项既有内核测试一项没动。★两次本条的判据与数值都**未改口径**。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 补门：此前没有门，现五道，读数逐位复现（`cases.plan('evolve-iter-15ma')` 的 42 个参数，每档不到 0.1 s）。★★更正第一格的数：原记最劣能量平衡残差 1.154e-13，那是**基线那一档**的；全部可跑变体里最劣的是台基那档 **1.298e-13**，余量约 7.7 倍而非 9 倍——判据仍过。★锯齿那档当初就是按名拒绝（没开电流通道），现在的门照此验。判决不变（inconclusive：驱动电流三道仍恒为零）。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 合并重复的变更条目：1.1 与 1.2 是同日两次内核换代，第二条误抄了第一条的摘要；合并成一条（沿用 1.2），两次换代各自写明。★本条的判据与数值未动。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.17 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.22 | 2026-09-19 | Claude Opus 5 | ★驱动电流一格转成立（原 open_defect「内核欠缺的功能也保留」关闭：缺的是算例的源，不是内核）：自举非零、给定 CD 1 / 2 MA 沉积积分闭合到 1e-16。α 份额改后逐档重量，最劣平衡残差换到 DT 那档 1.347e-13。四份读数由新工具 `tools/benchmark-evolve15.py` 重生成。整体 inconclusive → pass。 内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.23 | 2026-09-19 | Claude Opus 5 | 耦合整体求解成为缺省后四份读数由 `tools/benchmark-evolve15.py` 重生成：最劣能量平衡换到基线那档 1.58e-13（判据 1e-12），驱动电流三道照旧（CD 沉积积分 1e-16）；判决不动。 内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 |
| 1.24 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.25 | 2026-09-19 | Claude Opus 5 | ★`FR-TR-004` 的章页由 `tr-closure` 移到新域 `tr-sources`（加热与电流驱动单立）；本条判的是源的**接线**，仍留在 `tr-closure`。判据与数值不动。 内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/evolve15_switch_sweep.json`    `sha256:c9d834a5c15574491ae8042686e77e8a95f152d105b2314eed6341efb9360c72`    开关扫描：基线 + 五个变体，逐量对比；2026-09-19 由 tools/benchmark-evolve15.py 在新内核上重生成
- `docs/benchmark/readings/evolve15_sources_pedestal.json`    `sha256:c8f0e94835be7ce0d08515cc598bc704b819b972c11a3f8c6e6d924e31ac71f8`    基线一次运行的源项逐项、台基与平衡读数；2026-09-19 同上重生成
- `docs/benchmark/readings/evolve15_driven_currents.json`    `sha256:320f804feb83374e6dbb1e527f245dcdfa0f456565d2aa46ee15c04fdb6a98f1`    ★驱动三道各开自己的源（自举 · 给定 CD 1 MA / 2 MA）；tools/benchmark-evolve15.py 生成
- `tools/benchmark-evolve15.py`    `sha256:172210dc9d62dde435d752f29b0fcacd15c17f9ee5d80003c7d65222499038d4`    ★四份读数的生成器（2026-09-19 补进；此前读数由一次性脚本量）

**守它的门**：

- `python/tests/test_benchmark_transport_gates.py::test_the_switch_sweep_reproduces_its_recorded_readings` —— 五档里可跑的四档 + 基线，p_alpha 与读数逐位相同
- `python/tests/test_benchmark_transport_gates.py::test_the_energy_balance_holds_on_every_variant` —— 第一格：按全部变体判，并逐档对上读数
- `python/tests/test_benchmark_transport_gates.py::test_every_opened_switch_moves_at_least_one_output` —— 第二格：打开的控件至少动一项产出
- `python/tests/test_benchmark_transport_gates.py::test_the_sawtooth_is_refused_without_the_current_channel` —— 锯齿那一档当初就是按名拒绝的，现在仍是
- `python/tests/test_benchmark_transport_gates.py::test_the_current_switch_alone_feeds_the_driven_channels_nothing` —— 开关扫描的 current 档只开道不给源：三道仍为零（算例姿态）
- `python/tests/test_benchmark_transport_gates.py::test_the_driven_currents_answer_when_their_sources_are_given` —— ★第三格：自举非零、CD 沉积积分闭合、线性，逐位对上读数

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
