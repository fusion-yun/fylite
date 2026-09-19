---
title: "tr-closure-dt-burn-astra"
---

# DT 燃烧的 α 加热：份额（Q 值之比，精确）、总量（同一剖面对 ASTRA −0.3 %）、电子 / 离子分配（Post 式 1.3 %）——三格成立

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-closure-dt-burn-astra.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [闭包插件面：输运系数与插件接入](../domains/tr/closure.md)　|　记录正本：`records/tr-closure-dt-burn-astra.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：DT 燃烧的 α 加热：份额（Q 值之比，精确）、总量（同一剖面对 ASTRA −0.3 %）、电子 / 离子分配（Post 式 1.3 %）——三格成立
- **参考**：DT 分支比 3.5 / 17.6 · ASTRA
- **验的需求**：`FR-TR-004`
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.26　**评审**：草稿　**日期**：2026-09-19

## 问的是什么

**被量的**：能力 `code/zerod`，算例 `zerod-iter-15ma`，201 步；取 p_fus 最大的那一步

**参考**：DT 分支比 3.5 / 17.6

> ★**这不是另一个码，是一个常数**：DT 聚变每 17.6 MeV 里 3.5 MeV 归 α。所以这一条是**验证级**的判据，容差该取机器精度量级，不该是实测带。

**参考**：ASTRA（ITER 15 MA inductive at burn（CASE-01，153 个径向点））

> ASTRA 自己的 D-T α 答案：加热道与它留下的快离子布居。本处不重跑。

**口径与适用域**：

> fylite：能力 `code/zerod`，算例 `zerod-iter-15ma`（ITER 15 MA 感应场景，201 步，取 p_fus 最大那一步，t = 1 s）。剖面由峰化因子给定，**不是自洽解**。ASTRA：ITER 15 MA inductive 的燃烧点，153 个径向点，给 ne / te / ti / n_DT / n_alpha（快与热）/ p_alpha 及其 e、i 分量。★两侧的径向标签不同（fylite 用归一 rho，ASTRA 另给 rho_m），剖面对照只在轴上逐点取，不做整条重采样。

## 判据与量到多少

:::{figure} ../figures/tr-closure-dt-burn-astra-headroom.svg
:alt: tr-closure-dt-burn-astra 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| α 份额 p_alpha / p_fus 对 Q 值之比 3.52/17.59 的相对偏差 | 0.001 | reference_self_reported | 实测份额 0.2001137010，3.52/17.59 = 0.2001137010，相对偏差 0.0e+00（判据 1e-3）。★对旧参照 3.5/17.6：+0.0063——那是参照自己的舍入。★此前：0.20130，对 3.5/17.6 +0.0123（超出约 12 倍） | **成立** |
| α 总功率对 ASTRA 的体积分 | 0.2 | measured_band | ASTRA 自己的 T_i / n_DT 上（153 点每 8 取一，19 点）：体积分（dV ∝ x dx）−0.0029（判据 0.2）；T_i > 10 keV 逐点最劣 0.0166；边缘（T_i < 5 keV）逐点最低 −0.122。★此前（两侧各在各的工作点）：fylite 67.5 MW 对 ASTRA ≈ 101.5 MW，−0.335，判不了 | **成立** |
| α 功率的电子 / 离子分配 | 0.05 | reference_self_reported | `zerod::alpha_power_split_post` 在 ASTRA 自己的四个点（x = 0.003 · 0.27 · 0.53 · 0.72，喂它的 T_e、n_e、n_DT、n_α）上电子份额对 ASTRA 最劣 0.0129（带 0.05）。★Wesson / Stix 式（`alpha_power_split`，门 `code/zerod` 的缺省）在轴上 0.6352 对 ASTRA 0.5848，偏高 8.6 % | **成立** |
| 剖面对照（读数，不判） | — | — | fylite te(0) 20 keV / ti(0) 18 keV / ne(0) 1e+20 m^-3；ASTRA 27 / 23.5 / 1.13e+20（相对 -0.258 / -0.234 / -0.114） | **未判（读数）** |

**`α 份额 p_alpha / p_fus 对 Q 值之比 3.52/17.59 的相对偏差`** — ★判据 1e-3 不是实测带：分支比是**常数**，这一条本该到舍入。★2026-09-19 参照由 3.5/17.6 改为 **3.52/17.59**——α 的 Q 值（3.52 MeV）对反应的 Q 值（17.59 MeV）；3.5/17.6 是它的两位四舍五入，自身就偏 −0.63 %，拿它当参照判的是舍入。

**`α 总功率对 ASTRA 的体积分`** — ★★2026-09-19 改在**同一工作点**上判：内核的 α 功率密度（`zerod::dt_reactivity` × α 的 Q 值）喂 ASTRA 自己的 T_i、n_DT，对 ASTRA 的 PDT 逐点比、并按 dV ∝ x dx 积成总量。此前两侧各在各的工作点（0D 的给定剖面对 ASTRA 的自洽解），33 % 里分不开工作点与反应率。

**`α 功率的电子 / 离子分配`** — ★★2026-09-17 内核补上了这一项（Stix 慢化分配），于是这一格**从等它变成判它**；2026-09-19 补上 Post 式（电子 / 主离子 / α 三个库仑对数分开）。★带取 5 %：在 ITER 量级上，电子份额差 5 % 就是 3 MW 以上换道，对 T_e / T_i 分开演化不是小数。

**★α 份额 —— **成立**（2026-09-19）：精确等于 Q 值之比 3.52/17.59**

- ★★**成因与修法**：`zerod.rs` 写死 `E_ALPHA_FRACTION = 0.2013`，与它自己的注释 `3.52/17.59` 差 +0.59 %——三个差得很远的工作点上份额都恰好 0.2013，与等离子体状态无关。2026-09-17 的裁定是「不改内核、保留负面结果」；用户 2026-09-19「close FR-TR-*」取代之，常数改为 `3.52 / 17.59` 本身，内核测试的带从 1 % 收到 1e-15。
- ★α 功率一律 −0.59 %；1.5D 燃烧（evolve-iter-15ma）上 α 功率降 2.1 %、T_e 降 0.9 %——α 少了、温度低了、反应率又低了，是反馈，不是另一处错。
- ★这一条与工作点无关：不管剖面多热多稠，每次 DT 反应的 α 份额都是同一个比。

**★α 总功率对 ASTRA —— **成立**（同一剖面）：体积分 −0.3 %，芯部逐点 ≤ 1.7 %**

- ★★**这回比的是反应率与 α 能量，不是两个等离子体**：同一组 T_i、n_DT（n_D = n_T = n_DT/2）进内核的 Bosch–Hale 反应率。0D 的给定剖面对 ASTRA 自洽解那一种比法（−33 %）留在 deviation_literal 里，它量的是工作点。
- ★ASTRA 的 PDT 用的是 Putvinskii 1988 的拟合（`fml/svdt`），内核用 Bosch–Hale：两者在 5–23 keV 差 +1.4…+2.2 %，芯部那 1.7 % 大半是它。
- ★★**边缘未归因，照实记**：T_i < 5 keV 处内核的局域燃烧比 ASTRA 的 PDT 低到 12 %，而反应率拟合在那里的差是**另一个符号**（BH 高 1.4 %）——所以不是拟合。PDT 本身是局域的（`fml/pdt`：5.632·NDEUT·NTRIT·SVDT，不含快 α 再分布），所以剩下的候选是 ASTRA 在边缘的 NDEUT·NTRIT 不等于 (n_DT/2)²（表里的 n_DT 列与它算 PDT 用的两支不是同一个量），**没查**。边缘那几点只占 α 功率的 1 % 以下，体积分不受它左右；内核测试把「边缘不低于 −13 %」钉住，免得它无声变大。
- ★体积元用的是 dV ∝ x dx（x 为 ASTRA 的归一环向磁通半径），不是 ASTRA 的 dV/dx——总量是比值，几何常数相消，形状差在这一格的带里可以忽略。

**★★α 的电子 / 离子分配 —— **成立**（Post 式，2026-09-19）：对 ASTRA 最劣 1.3 %；门的缺省仍是 Wesson 式**

- ★★**差在哪里查到了**：Stix / Wesson 式把电子与离子的库仑对数合成一个、并忽略 α 自身的拖曳；Post 式（ASTRA 的 `fml/pedt` · `pidt` 的出处）三个库仑对数分开：$y=7.3\times10^{-4}/\ln\Lambda_e\,(\ln\Lambda_i\,n_i/A+\ln\Lambda_\alpha n_\alpha)$、$v_c=y^{1/3}\sqrt{2T_e/m_e}$。换成它，8.6 % 落到 1.3 %。
- ★★**照实记**：判成立的是内核的 Post 式；`code/zerod` 的 α 分配（0D 只有体平均 T_e、没有 n_α）与 1.5D 的缺省仍是 Wesson 式，没换——换缺省会动每一条已有的 1.5D 读数，另立一件事。
- ★方向一直是对的（电子占多数，约六成）；不是成分差（`dt_fraction` 0.50 → 0.40 电子份额只动 0.635 → 0.629），是公式。

**剖面对照（读数，不判）**

- ★fylite 这一侧的剖面是**输入**（0D 的峰化因子），不是算出来的——所以这一行是**记两侧各自在哪个点上**，不是判谁准。读数入册是为了让上面那条「判不了」有据可查。

## 不可比的部分

- ★★**三格都成立**（2026-09-19）：份额精确等于 Q 值之比；总量改在同一剖面上判，体积分 −0.3 %；分配用 Post 式 1.3 %。剖面对照那一行仍是读数（两侧各在各的工作点）。整体 pass（由 inconclusive 改）。
- ★**哪些量是喂进去的**：fylite 侧的 ne / te / ti 剖面、Ip、加热功率都是输入；算出来的是 p_fus、p_alpha 与 v_loop。把「剖面对不上」读成「算错了」是这一域最容易犯的错。
- ★**ASTRA 侧不在本处重跑**：它是 sha256 索引的归档表。
- ★另记一处**输出面的毛病**：0D 运行的 `q` 迹在无外加热处写 DD 空值（−9e40 量级），下游若不过滤会被它污染——2026-09-08 内核定为「不适用」写空值而非 NaN，本条照录。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.26　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：DT 燃烧的 α 加热；份额判 fail，总量判不了，e/i 分配是内核缺口 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | ★★α 的 e/i 分配**从记名缺口变成量出来的对拍**：内核 2026-09-17 补上（Stix 慢化），在 ASTRA 轴上温度 26.96 keV 处给 0.6352 / 0.3648，对 ASTRA 的 0.5848 / 0.4145 偏高 8.6 %，判 fail。★已排除成分差（扫 dt_fraction 只动 0.006） |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核再次换代后的全册重验（`ac8c0f5c` → `eb8c9022`：ETS 五型边界、燃烧→密度的接线、时间收敛阶，内核仓 `acd1628`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：165 道门禁全过、660 项既有内核测试一项没动。（★2026-09-18 改正：原文误抄了 1.1 的摘要。） |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.5 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 补门，并**答上了本条自己挂着的问题**：α 份额为何偏 +1.23 %。★成因是 `zerod.rs` 写死的 `E_ALPHA_FRACTION = 0.2013`，它与自己的注释 `3.52/17.59` 就差 +0.59 %；三个差得很远的工作点上份额都恰好 0.2013，与等离子体状态无关——**是一个常数，不是物理**。既有内核测试特意把带放宽到 1 % 来容纳它。按「不改内核、保留负面结果」的裁定常数不动；门钉住它，常数一动即红。电子 / 离子分配那一处（+8.6 %）仍未查。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 改正误抄的变更摘要：1.3 原文照抄了 1.1，而两条之间隔着一条真实改动，合并会打乱时序，故只把 1.3 改写成它实际对应的那次换代（`eb8c9022`）。★本条的判据与数值未动。 |
| 1.17 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.18 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.21 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.22 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.23 | 2026-09-19 | Claude Opus 5 | ★三格转成立（用户「close FR-TR-*」，取代 09-17「不改内核、保留负面结果」的裁定，原 open_defect 关闭）：份额——内核常数 0.2013 → 3.52/17.59，参照随之改为 Q 值之比，偏差 0；总量——改在 ASTRA 自己的剖面上判，体积分 −0.3 %（边缘 −12 % 未归因，照记）；分配——Post 式 1.3 %（门的缺省仍是 Wesson 式，照记）。读数由新工具 `tools/benchmark-dt-burn.py` 重生成（p_fus 逐位复现原读数）。整体 inconclusive → pass。 内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.24 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.25 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.26 | 2026-09-19 | Claude Opus 5 | ★`FR-TR-004` 的章页由 `tr-closure` 移到新域 `tr-sources`；本条判的是 α 加热接进输运的那一步，仍留在 `tr-closure`。判据与数值不动。 内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/dt_burn_astra_metrics.json`    `sha256:01e135a22aad5dd2211506582537492d09c5ad3e5e5e6068bd9340015b58d5df`    本条读数：两侧的标量与剖面（当日实跑 + ASTRA 归档表抽出）
- `FYDOC-CASE-01-astra/corpus/iter15ma_astra_burn.csv`    `sha256:6dc1c70b94ef31c8ae8513522e847fdba47495ed64425a44306bd43adb5f326e`    ★ASTRA 侧原件（实验/参考类，指针 + sha256）
- `third_party/astra/fml/svdt`    `sha256:99f6f0f9353c0824791f390db48fb7f94f419a21f5807aa657eebd82f79635ba`    ★ASTRA 的 DT 反应率（Putvinskii 1988），参考类指针；PDT = 5.632 n_D n_T SVDT 见同目录 `fml/pdt`

**守它的门**：

- `python/tests/test_benchmark_transport_gates.py::test_the_alpha_share_is_the_q_value_ratio_at_every_operating_point` —— ★第一格：三个工作点上份额恰为 3.52/17.59（1e-12）
- `python/tests/test_benchmark_transport_gates.py::test_the_alpha_share_against_the_rounded_branching_is_the_rounding` —— 第一格：对 3.5/17.6 的 +0.63 % 是参照的舍入；读数由 tools/benchmark-dt-burn.py 重生成
- `$FYLITE_KERNEL/rust/fylite/src/zerod.rs::tests::alpha_fraction_is_the_physical_one` —— 内核：E_ALPHA_FRACTION == 3.52/17.59（1e-15）
- `$FYLITE_KERNEL/rust/fylite/src/zerod.rs::tests::the_alpha_power_density_lands_on_astra_s_profiles` —— ★第二格：同一剖面体积分 < 1 %、芯部 < 2 %，边缘下限钉住
- `$FYLITE_KERNEL/rust/fylite/src/zerod.rs::tests::the_post_split_lands_on_astra_s_iter_burn` —— ★第三格：Post 式电子份额对 ASTRA 四点 < 2 %

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
