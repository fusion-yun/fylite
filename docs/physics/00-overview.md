---
title: 物理与数值 · 总览 (Physics & Numerics — Overview)
subtitle: 阅读协议、证据等级图例、模块→章节映射、引文核验协议、路径与快照约定
---

(phys00-intro)=
# 引言：这一部分述什么 (Introduction)

〔范围〕"物理与数值"十四章（`physics-01` … `physics-14`）逐模块详述 fylite Rust 内核（`fylite_kernel` 仓，
`rust/fylite/src/*.rs`）**实际实现**的物理理论与数值算法：每个模块用到的方程、其成立所依赖的假设、参数域与守卫
（钳制、拒绝码、NaN 约定）、离散与迭代格式，以及每一条公式与算法的**一手出处**。它与本书其余三篇的分工：
`fidelity.md` 划保真度边界（能算什么、不能算什么），`kernels.md` 列内核清单（有哪些模块、导出什么），
`api.md` 述调用面；本部分回答"**这些模块里写的到底是什么物理、出自哪里、验到什么程度**"。

〔姿态〕各章描述的是**代码**，不是文献中的模型：凡代码与文献有出入（系数被重标、开关被预设钉死、上游分支被拒绝、
常数对一次运行拟合），章节以代码为准并把出入写明。理论推导本身不在本书重复——它们属于 SpResearch 的理论手册
（`GK-TMT-NN`，跨仓，见 {ref}`phys00-citations`）。

(phys00-protocol)=
# 阅读协议：每章的固定结构 (Reading Protocol)

每章按同一骨架组织，节名与锚点前缀固定（`physNN-*`），便于跨章引用与对照：

1. **引言**——〔范围〕（模块、行数量级、上游）、〔出处姿态〕（源码本身引了什么、没引什么）、〔与理论手册的分工〕。
2. **物理与数值各节**——方程以 `(eq-pNN-*)` 编号；每一条物理或文献断言带证据等级标记（{ref}`phys00-evidence`）；
   源码逐字注释以引号照录，源码中的 ★ 保留为原作者的强调。
3. **适用域与失效条件**（`physNN-limits`）——硬拒绝（负 `i32` 错误码、NaN）、软钳制、已知偏差与开放项。
4. **验证锚点**（`tbl-pNN-verify`）——每条锚点写明参照物（上游库的录得值、解析解、独立实现）与判据（容差）。
5. **与内核的对应**（`tbl-pNN-asbuilt`）——内容 → 内核函数 → C-ABI 入口（`fylite_rs_*`）→ Python 入口；标注快照日期。
6. **来源与出处**（`physNN-sources`）——分四类：〔一手文献（源码逐字引）〕、〔编者对应/源码只给姓名〕、〔转引〕
   （上游代码文件、数据集、作业号）、〔源码未注出处（实现即定义）〕与〔本仓选择〕。
7. **参考来源**——`{bibliography}` 指令，只列本章引用的条目。

方程、表、锚点的编号由 MyST 自动生成；章内不写手工编号。

(phys00-evidence)=
# 证据等级图例 (Evidence Classes)

:::{table} 各章使用的标记及其含义。**无标记的物理或文献断言是缺陷。**
:name: tbl-p00-evidence
:align: left

| 标记 | 含义 | 升级条件 |
| :--- | :--- | :--- |
| 〔源码〕 | 代码实际做的事，由阅读源码逐行核对；引号内为源码注释原文 | — |
| 〔已确立〕 | 教科书级或被广泛验证的结果，所引文献为其公认出处 | — |
| 〔凭记忆〕 | 编者凭记忆补出的文献对应或断言。条目**字段**的核验状态记录在 `references-physics.bib` 的 `note`（2026-09-02：178 条中 175 条已核验，3 条软件条目未核验）；正文标记指**对应关系**——该文献确为该公式或算法的出处——尚未以论文原文逐项对照 | 以论文原文对照该公式后改标 〔已确立〕 |
| 〔未核验〕 | 文献存在，但代码中的系数/形式与论文原文的逐项一致性**未**查证 | 逐项比对后改标 |
| 〔推测〕 | 编者对代码意图或物理机制的推断，无源码或文献直接支持 | 找到源码注释或文献后改标 |
| 〔评注〕 | 编者的解读、对比或提示；不作为断言 | — |
| 〔本仓选择〕 | 上游没有对应、由本仓自行裁定的常数、钳制或拒绝 | — |
| "源码未注出处" | 公式或常数从上游逐字转录，上游只给例程名，无文献；以对上游库的锚点为证 | 不替上游补未经核验的出处 |
:::

〔纪律〕(i) 不把 〔凭记忆〕 写成 〔已确立〕；(ii) 不把"实现即定义"的常数附会到一篇论文上；(iii) 不给代码中不存在
的分支（例如 TGLF 的 SAT_RULE 0 饱和公式）写公式；(iv) 数值锚点只写测试文件中实际硬编码的值与容差。

(phys00-map)=
# 模块 → 章节映射 (Module-to-Chapter Map)

:::{table} 内核物理模块与所在章节（`lib.rs`、仓根 `NOTICE` 与各模块头部，2026-09-02 快照）。特性门为 `Cargo` feature。`NOTICE` 只列 GACODE、METIS、fytrans 三个上游；其余来源取自模块头部的自述。
:name: tbl-p00-map
:align: left

| 章 | 模块（`rust/fylite/src/`） | 上游 / 来源（据 `NOTICE` 与模块头部） | 特性门 |
| :--- | :--- | :--- | :--- |
| 01 数值内核 | `kernels.rs`, `linalg.rs` | 自研（"Textbook algorithm — NOT a port of any library"）；算法出处见章内 | 无门 |
| 02 平衡正解 | `equilibrium.rs` | **清洁室**（EFIT 血统代码未读；仅据公开文献） | `core` |
| 03 平衡重建 | `inverse.rs` | **清洁室**（同上） | `core` |
| 04 几何与归一 | `surfaces.rs`, `geometry.rs`, `mapping.rs`, `bundle.rs` | `surfaces` 自研；`geometry` ← GACODE GEO；`mapping` ← `tgyro_tglf_map.f90` / `tgyro_neo_map.f90`；`bundle` ← `expro_util.f90` | `core`（`bundle` 亦 `dke`） |
| 05 芯部输运 | `transport.rs` | 自研离散；fytrans 为**oracle 而非来源**；部分 ← `tgyro_residual`（通量匹配） | `core` |
| 06 零维 | `zerod.rs` | 自研（`python/fylite/zerod.py` 物理半部的 Rust 转录）；标度律与界限出处见章内 | `core` |
| 07 新经典 | `neoclassical.rs`, `dke.rs` | ← GACODE NEO（解析族 / 漂移动理学） | `core` / `dke` |
| 08 湍流 | `gyrofluid.rs`, `closure_tables.rs`, `flr_tables.rs`, `nn.rs`, `bgb.rs` | `gyrofluid` 与两张数表 ← GACODE TGLF；`nn` 自研评估器（权重外置）；`bgb` 文献清洁室（Bohm 系数对 JINTRAC 101612 冻结） | `tglf` / `core` |
| 09 加热与电流驱动 | `heating.rs` | ← METIS（CeCILL-C）**转录**，六处声明的偏离 | `core` |
| 10 源项 | `sources.rs` | ← `tgyro_source.f90` / `tgyro_rad.f90` | `core` |
| 11 边缘与台基 | `edge.rs`, `edge_tables.rs`, `neutrals.rs`, `pedestal.rs`, `pedestal_tables.rs` | `edge` ← TORAX 的 Mavrin/Lengyel 实现；`neutrals` 清洁室（EIRENE 方法类）；`pedestal` ← EPEDNN.jl | `core`（`pedestal` 无门） |
| 12 电磁与控制 | `electromagnetics.rs`, `evolution.rs`, `stability.rs`, `control.rs` | 自研；文献出处见章内 | `core` |
| 13 放电设计与击穿 | `pulse.rs`, `breakdown.rs` | 自研；GSPulse 型构造的出处见章内 | `core` |
| 14 拟合与诊断 | `fitting.rs`, `diagnostics.rs` | 自研；算法出处见章内 | `core` |
:::

〔范围外〕`fyo.rs`（文件格式声明，"it is data"）、`scenario.rs`（编排面）、`c_api.rs`（"Device data plane, not a
physics layer: it moves bytes, computes nothing"）不含物理，不设章；其调用面见 `api.md`。Python 侧
（`python/fylite/scenario/model/*.py`）只在"与内核的对应"表中作为入口出现；其自身的算术（例如 QLKNN 的通量组合、
束路径几何）在相应章节以〔源码〕标注。

(phys00-citations)=
# 引文与核验协议 (Citation and Verification Protocol)

〔三类出处〕每一条公式或算法的出处属于且只属于下列一类，章末"来源与出处"按类列出：

1. **源码逐字引**——上游或本仓源码中给出的文献（期刊、卷、页或 DOI）。照录；若编者核验发现字段有误，在文献库
   条目的 `note` 中记差异，正文不改动源码所引的形式。
2. **编者补出的一手文献**——源码只给姓名（"Hammett–Perkins"、"Waltz–Miller"）或只给例程名时，编者补出公认的原始
   文献并标 〔凭记忆〕；核验后改标 〔已确立〕。凡系数与论文的逐项一致性未查，另标 〔未核验〕。
3. **无文献的常数与构造**——上游未注出处、也不存在可对照闭式的数值（拟合表、经验常数、网格断点）。列入
   "源码未注出处（实现即定义）"，以对上游库录得值的锚点为唯一证据；本仓自定的钳制与拒绝列入〔本仓选择〕。

〔文献库〕全部条目在 `references-physics.bib`（本书 `myst.yml` 的 `bibliography`）。每条带 `note` 字段：
`核验 <日期>：… 命中〈…〉，字段一致 | 字段有改：…`；`未核验 <日期>：…`；或所转录的源码引文原文。核验于
2026-09-02 以出版社 / 索引库落地页的检索结果为据完成（构建环境无 DOI 解析能力）：178 条中 175 条至少一次命中
可判读来源，其中 1 条（`erba1997bgb`）仅刊、卷、起页得到确认而题名与作者表未获确认；3 条软件 / 预印本条目
（TORAX、FUSE、GACODE 文档页）沿用 SpResearch 文献库著录，未核验。未能解析者保留 `未核验` 字段，**不**以推测补齐。
核验改变了条目身份或年份的三个键已改名（`huba2013nrl`、`hofmann1990isoflux`、`wai2026gspulse`），`note` 记原键；
此后条目键名一经引用不再更改。

〔跨仓〕理论推导与判据在 SpResearch 理论手册 `GK-TMT-01` … `GK-TMT-11`（例如 `GK-TMT-08` 输运闭包）。本书以
文档号在正文提及，不建链接、不复述其内容；两仓的数学宏一致（`\vb \pdv \dv \dd \expval \abs \norm`），便于对读。

(phys00-paths)=
# 路径与快照约定 (Paths and Snapshots)

- `rust/fylite/src/*.rs`、`rust/tools/*.py`、仓根 `NOTICE` 与 `tests/` 均以 **`fylite_kernel` 仓**为根；
  `python/fylite/**`、`docs/**` 以本仓为根。本书公开，内核仓私有：章节不复制内核源码，只引其注释原文。
- 各章的"与内核的对应"表与行数量级为 **2026-09-02 快照**；内核函数改名、C-ABI 增删、Python 入口迁移时须同步该表。
- 锚点数值（例如 TGLF 参考卡的 $\gamma=0.3241554304484416$）取自测试文件硬编码的参照值；`tests/data/` 中的录得
  oracle 文件不在本书范围内（见 `kernels.md`）。
- 引用的上游修订号（GACODE `5efddfdf1` / `6357db306`、TORAX `b4d40633`、fusion_surrogates `d678186`）以 `NOTICE`
  与各章引言为准。

(phys00-limits)=
# 本部分的边界 (What This Part Does Not Do)

〔评注〕本部分不评价模型的物理正确性，不比较模型间的优劣，不给出参数推荐值；它记录代码实现了什么、在什么条件下
拒绝或退化、对什么参照验到什么容差。凡"是否应当采用某模型"的判断属调用方与理论手册的范围。
