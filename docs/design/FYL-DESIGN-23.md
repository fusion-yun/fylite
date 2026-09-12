---
document_id: FYL-DESIGN-23
title: "场景线总目录与章模板 (The Scenario Lines: Index and Chapter Template)"
shortname: fylite-scenario-lines
version: "0.2"
date: 2026-09-12
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - AI 协作（会话记录在案）
created: 2026-09-12T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-12T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.2（用户指示 2026-09-12「优化整理其他场景，合并冗余，考虑内在逻辑和实际工作情景，参考 fytok 设计文档」）：
    §一 design 线改承 S-L4 + S-L5（fytok `FYTOK-ADR-112` 把 S-10 / S-11 并成同一设计空间的两层，本仓同理）；
    新增 §二b〈归并〉——20 个场景名按内在逻辑与实际工作情景收成 **10 章**，逐条给理由与 fytok 对应面
    （面由意图定、不由保真度定，`FYTOK-ADR-116` D1）；§四 各章状态表改为十章全部落地（-24..-33）；
    新增 §二c〈单模型求值与对拍〉（fytok S-12 在本仓的形：一 code 一调 + 校验册，不另立章）。
    v0.1（全新文档，设计书重组第二部的封面）：按场景重新划分功能线——四条 `fy run` 线
    对应 CONOPS 的 S-L1..S-L4（S-L5 无线，见 §一），场景表**由 `docs/examples/scenario/lines.jsonld`
    生成**（不手抄）；每条场景指向它的正本设计篇；给出场景章的模板（W-1..W-4）与各章的整理状态。
    第一章样板 `FYL-DESIGN-24`（动理学平衡重构）同批落地。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-lines

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-23` |
| 文档名称 (Title) | 场景线总目录与章模板 |
| 短名 / Slug | `fylite-scenario-lines` |
| 版本 (Version) | v0.2 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 用户指示 2026-09-12 · `FYL-CONOPS-00` v1.2 §运行场景（S-L1..S-L5）· `docs/examples/scenario/lines.jsonld`（生成物）· `FYL-DESIGN-17` E-8 / E-17 · `FYL-DESIGN-22` T-1..T-4 |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本篇 `W-` 裁定在本篇内唯一。

(fylite-scenario-lines-abstract)=
# 摘要 (Abstract)

第二部按**场景**划分功能线。一条**线**是 `fy run <line>` 的第一个词（四条：`analysis` · `model` ·
`design` · `control`），一个**场景**是那条线上的一份计划模板（`docs/examples/scenario/<name>.jsonld`）。
本篇是总目录：线 ↔ CONOPS 任务的对应、每条场景的现状与正本、以及每章的模板。
**场景表由生成物 `lines.jsonld` 派生**，与 `fy list lines` / `fy list scenarios` 说的是同一份数据。

(fylite-scenario-lines-map)=
# 一 · 线与任务 (Lines and Tasks)

:::{table} 四条线 ↔ CONOPS 的五类任务。缺省场景是 `fy run <line>` 不给场景名时跑的那一个。
:name: tbl-w23-lines
:align: left

| 线 | 名 | CONOPS | 缺省场景 | 正本设计篇（页面） |
| :--- | :--- | :--- | :--- | :--- |
| `analysis` | 实验分析 | S-L2 | `reconstruction` | `FYL-DESIGN-12`（分析页）· `-21`（反演流程图页） |
| `model` | 物理建模 | S-L1 | `transport` | `FYL-DESIGN-10`（建模页） |
| `design` | 放电运行设计 | S-L4 | `zerod` | `FYL-DESIGN-09`（放电设计页） |
| `control` | 控制仿真 | S-L3 | `breakdown` | `FYL-DESIGN-09`（仿真模式） |
| `design`（同上） | 装置参数优化 | S-L5 | — | ★v0.2：**S-L5 归 design 线**——静态层定运行点（D2 位形与线圈电流 · D1 可行域）、动态层在其上实现放电（D3），与 fytok `FYTOK-ADR-112` 把 S-10 / S-11 并入一份 SRS 的理由相同：同一装置设计空间的两层。外层优化器仍归 FyTok（`FYL-CONOPS-00` S-L5） |
:::

(fylite-scenario-lines-catalogue)=
# 二 · 场景目录 (The Scenario Catalogue)

〔已确立·由 `lines.jsonld` 生成，2026-09-12〕

:::{table} 每条场景：线 · code · 参数数 · 今天能不能跑 · 不设或不跑的理由（理由来自数据，不来自散文）。
:name: tbl-w23-scenarios
:align: left

| 场景 | 线 | code | 参数 | 状态 | 理由 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `breakdown` | design · control | code/breakdown | 17 | ✓ 可跑 |  |
| `discharge` | design | code/discharge | 23 | ✓ 可跑 |  |
| `evolve` | model | code/evolve | 114 | ✓ 可跑 |  |
| `pfwave` | design | code/pfwave | 14 | ◐ 有模板，内核门今天不认 | 内核 case 门不认该 code（`FYL-DESIGN-17` P2） |
| `profile` | analysis | code/profile | 5 | ◐ 有模板，内核门今天不认 | 内核 case 门不认该 code（`FYL-DESIGN-17` P2） |
| `reconstruction` | analysis | code/reconstruction | 46 | ✓ 可跑 |  |
| `series` | analysis | code/series | 8 | ◐ 有模板，内核门今天不认 | 内核 case 门不认该 code（`FYL-DESIGN-17` P2） |
| `transport` | model | code/transport | 19 | ✓ 可跑 |  |
| `zerod` | model · design | code/zerod | 33 | ✓ 可跑 |  |
| `posterior` | analysis | — | — | — 不设模板 | 后验采样是反演的一组参数（mcn · mc-*），不是另一个场景。 |
| `batch` | analysis | — | — | — 不设模板 | 队列是宿主机制：命令行上是 series，或一个 shell 循环。 |
| `loop` | analysis | — | — | — 不设模板 | 反演—输运自洽外环在本分发里跑不起来（指南「自洽外环」自述）；库路径复原后再设。 |
| `sxr` | analysis | — | — | — 不设模板 | 软 X 射线层析：文档提及，无工具、无栏、无语料。 |
| `coupled` | model | — | — | — 不设模板 | 平衡—输运静态交替是 evolve 的 couple 参数（2026-08-26 栏让给 evolve）。 |
| `tglf` | model | — | — | — 不设模板 | 湍流通量是两条栏里的一个闭包模式（closure · turb-*），独立模板待 P2-c。 |
| `interp` | model | — | — | — 不设模板 | 剖面插值是工具不是场景。 |
| `sim` | design | — | — | — 不设模板 | 交互时间推进是浏览器的档位，不是批式动作（FYL-DESIGN-10 P-1）。 |
| `pulse` | design | — | — | — 不设模板 | 整脉冲前馈设计今天没有 code IRI（语料的 pulse-iter 用 code/pfwave），模板需要一个真实的 code——P2-c。 |
| `feasible` | design | — | — | — 不设模板 | 可行域扫描无栏、无语料，扫描轴的参数词表要先立——P2-c。 |
| `vstab` | control | — | — | — 不设模板 | 垂直稳定裕度有内核 entry（vstab）但无 case code、无语料词表——P2-c。 |
| `vertical` | control | — | — | — 不设模板 | 垂直反馈闭环无栏无语料，参数词表要先立。 |
| `evolution` | control | — | — | — 不设模板 | 电压驱动的位形演化同上。 |
:::

★**一处过期的自述（G-1）**：`lines.jsonld` 里"内核门今天不认"的理由字符串仍写着
`CASE_CODES` 只有 12 个 code，而内核声明面今天是 **35** 个（内核仓 `FYL-REPORT-08` §2.2）；
三个"不认"的判断本身要按今天的表**重测**（`code/pfwave` · `code/profile` · `code/series`）。
生成器 `tools/make-scenario-templates.py` 的那句理由应从内核声明读，不应写死。

(fylite-scenario-lines-merge)=
## 二b · 归并：20 个名字，10 章 (The Merge)

〔已确立·用户指示 2026-09-12；判据取自 fytok 设计书〕两条规矩借自 fytok：**面由意图定，不由保真度或单次
运行代价定**（`FYTOK-ADR-116` D1）；**S-10 与 S-11 是同一设计空间的两层**（`FYTOK-ADR-112`）。再加本仓
自己的三条：工具登记册 `BROWSER_ONLY_BARS` 已写明哪些栏是别的栏的合成；`-17` E-8 已写明哪些名字不设模板
及理由；`-10` P-19 / `-09` D-22「一个应用只有一条时间轴，保真度是开关」。按这五条，`lines.jsonld` 的 20 个名字
收成 10 章：

:::{table} 归并表。「实际工作情景」列说的是这一章在一次真实分析 / 建模 / 设计工作里对应哪一步。
:name: tbl-w23-merge
:align: left

| 章 | 线 | 收进来的名字 | 为什么并 | 实际工作情景 | fytok 对应 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **-24 动理学平衡重构** | analysis | `reconstruction` · `posterior` · `profile` · `loop` | 后验是反演的一组参数；剖面拟合是阶段 1；自洽外环是阶段 4 | 单炮单时刻重构，动理学外环至收敛 | S-8 · fyanalysis A1（M0 → M1 档） |
| **-25 逐片重构** | analysis | `series` · `batch` | 队列是宿主机制；series 是"算什么"，batch 是"怎么排队" | 炮后整段平顶逐片，对交付 EFIT 时序 | S-8 重构 L3 炮间 / L4 隔夜 |
| **-26 解释性分析** | analysis | 建模页「反演栏」（`code/interpretive`）· analysis 线的 `zerod` | 「给 T 反求 χ」按**意图**是分析不是建模；0-D 在此是解释性用法 | 这一炮反常还是新经典 · 0-D 账 | fyanalysis A2 剖面反演（q^PB / χ^eff） |
| **-27 平衡正解与位形** | model | `-10` P-20 的边界与度规栏 · forward / steady_equilibrium / ladder / metric / cocos / shape | 五个 code 是一个场景；它是 M2 的输入、D2 的正问题 | 建模第一步：拿到一个平衡与度规 | S-2（fyeq F0..F4） |
| **-28 定态输运与闭包** | model | `transport` · `coupled` · `tglf` | coupled 是 `couple` 参数；tglf 是闭包一档 | 给 χ 求 T；通量匹配 / 平衡交替至自洽 | S-3 + S-4（fypredict P1） |
| **-29 含时演化与仿真推进** | model | `evolve` · `sim` · `zerod` 的推进档 · `coupled` 的时序形 | 一条时间轴；0-D / 1.5-D 是保真度开关；交互 / 批式是 cadence | 推进一炮看会发生什么（批式或拖滑块） | S-7 `PulseEvolution`；S-7 / S-10 按保真档分界 |
| **-30 放电方案** | design | `zerod`（方案用法）· `feasible` | 0-D 定标是设计的第一步；可行域是它的扫描 | 这炮 / 这台机可行的工况在哪 | fydesign `ZeroDScan` + S11-FR-OPT-4 筛查 |
| **-31 配置** | design | `discharge` · `breakdown`（设计侧）· `pfwave` · `vstab` 的读数 | 一个时刻的同一张表：位形 → 电流 · 场零 · 电源 · 裕度 | 定了工况就配位形 | fyeq `inverse`（S11-FR-INV-1）；击穿在 fytok 是缺口 |
| **-32 整脉冲前馈设计** | design | `pulse` · `pfwave` 的时序用法 | pulse 是 D2 的序列 + 电路方程 | 试验前排整条放电 | fydesign `PulseDesign`（S-10）；五段登记 |
| **-33 垂直稳定与位置控制** | control | `vstab` · `vertical` · `evolution` · `breakdown` 的动力学侧 | 三个无模板的名字是一条链：裕度 → 反馈 → 闭环 | 拿到平顶平衡后判裕度、设计反馈、闭环看撞不撞限 | S-9 fycontrol `EvolutiveDischarge`；S-9 / S-10 分工 |
:::

**不成章的**：`interp`（剖面插值是工具，不是场景）· `sxr`（无工具无栏无语料，登记为缺口）。
**跨线的两个名字**：`zerod`（-26 解释性 · -30 方案 · -29 推进档：同一 code 三种输入，各章各说）；`breakdown`
（-31 场零设计 · -33 击穿动力学与上升段）。

★**与既有页面的对应**：页面不是场景。分析页四栏 → -24 / -25（-26 的栏今天在建模页）；建模页三栏 → -27（栏未落）
/ -28 / -29（栏待搬）；放电设计页三模式 → 配置 = -30 + -31，设计 = -32，仿真 = -29 + -33。页面裁定（`P-` · `D-` ·
`Q-`）一条不动。

(fylite-scenario-lines-s12)=
## 二c · 单模型求值与对拍 (One Model, Evaluated Alone)

〔已确立〕fytok 在 v0.8 新立 S-12「物理模型求值与对拍」（按名接入一个物理模型并单独对它求值，不在任何环里）。
本仓**不另立章**，因为这在 fylite 里本来就是常态：每个 `code/<x>` 都可以单独经文档门调一次（`fy run <计划>`
一份计划一个 code），校验册（`docs/benchmark/`）就是它的对拍登记。它是**横切**的：每章的"对照"行都是一次 S-12。

(fylite-scenario-lines-template)=
# 三 · 场景章的模板 (The Chapter Template)

**W-1 一章一场景，章名就是场景名。** 一章对应 `lines.jsonld` 里的一个场景（或一组被并入
同一场景的名字，如 `posterior` 并入 `reconstruction`）。

**W-2 四件必备**（`FYL-DESIGN-22` T-4）：

| 件 | 形 | 判据 |
| :--- | :--- | :--- |
| ① 物理算法流程图 | SVG（`docs/figures/sc-<scenario>-flow.svg`）+ 一张阶段表（阶段 · code · 端口 · 判据 · 状态 ✓/◐/✗） | 图上每个 code 节点在内核声明面里存在；缺的步画成关着的节点 |
| ② 命令面 | CLI · MCP · Python **三种写法对同一份计划**；命令原样贴，能跑的标"实测"，不能的标为什么 | 三种写法解析出的计划逐字段相同（能量的先量） |
| ③ 界面效果图 | SVG（`docs/figures/sc-<scenario>-page.svg`），概念图，数值示意 | 图上的每个控件在词表里有条目或标"待立" |
| ④ 判据与验收 | 各层判据 → fyo 类（`ConvergenceCriterion` / `AcceptanceCriterion` / `ComparisonRecord`）；阈值只写量过的 | 参照量级与本仓阈值分列 |

**W-3 可选件**：数据流表（端口 in/out）· 三级用户各改什么 · 缺口（指向 `PLAN.md` 或正本篇的 G-）。

**W-4 章不重述共性机制**（`-22` T-3）：续跑 · 导入导出 · 溯源 · 状态机只引用第一部。

(fylite-scenario-lines-status)=
# 四 · 各章整理状态 (Where Each Chapter Stands)

| 章 | 场景 | 线 | 状态 | 正本（裁定所在） |
| :--- | :--- | :--- | :--- | :--- |
| `FYL-DESIGN-24` | 动理学平衡重构 | analysis | ✓ 样板（手绘图） | `-12` P-22 · `-21` Q-1..Q-9 · `PLAN.md` §H |
| `FYL-DESIGN-25` | 逐片重构（时间序列） | analysis | ✓ v0.1 | `-12` P-23 |
| `FYL-DESIGN-26` | 解释性分析 | analysis | ✓ v0.1 | `-10` P-28 |
| `FYL-DESIGN-27` | 平衡正解与位形 | model | ✓ v0.1 | `-10` P-20 / P-21 · `-09` D-6 |
| `FYL-DESIGN-28` | 定态输运与闭包 | model | ✓ v0.1 | `-10` P-19 / P-28 · `-16` K-2 |
| `FYL-DESIGN-29` | 含时演化与仿真推进 | model | ✓ v0.1 | `-09` D-11..D-17 / D-22 · `-18` U-8..U-11 |
| `FYL-DESIGN-30` | 放电方案：0-D 工况与可行域 | design | ✓ v0.1 | `-09` D-2 / D-3 / D-9 |
| `FYL-DESIGN-31` | 配置：位形 · 线圈电流 · 击穿场零 · 电源尺寸 | design | ✓ v0.1 | `-09` D-6 / D-7 / D-14 / D-18 |
| `FYL-DESIGN-32` | 整脉冲前馈设计 | design | ✓ v0.1 | `-09` D-1..D-8 / D-14 |
| `FYL-DESIGN-33` | 垂直稳定与位置控制 | control | ✓ v0.1 | `-09` D-14 / D-22 · 指南〈稳定与控制〉 |

★-25..-33 的图由 `tools/make-scenario-figures.py` 从规格生成（`tools/_scenario_figure_specs.py`），不手画；
`--check` 是它的闸。-24 的两张是手绘样板，风格由生成器沿用。
★十章里"今天可跑"的是 -24（阶段 0 / 3）· -25（逐片，循环）· -28 · -29 · -30（0-D）· -31（反解 · 场零）；
其余各章的图是**目标态**，各章 §六 逐条登记缺口与关闭判据。

(fylite-scenario-lines-trace)=
# 五 · 追溯 (Traceability)

| 本篇 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 | `FYL-CONOPS-00` S-L1..S-L5 · `lines.jsonld` `fylite:lines` | 各章的"场景定义"节 |
| §二 | `lines.jsonld` `fylite:scenarios`（生成物）· `FYL-DESIGN-17` E-8 / E-17 | G-1 → `tools/make-scenario-templates.py` |
| §三 | `FYL-DESIGN-22` T-3 / T-4 | `FYL-DESIGN-24` 及后续各章 |
