---
document_id: FYL-DESIGN-23
title: "场景线总目录与章模板 (The Scenario Lines: Index and Chapter Template)"
shortname: fylite-scenario-lines
version: "0.1"
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
  change: 'v0.1（全新文档，设计书重组第二部的封面）：按场景重新划分功能线——四条 `fy run` 线
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
| 版本 (Version) | v0.1 |
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
| — | 装置参数优化 | S-L5 | **无线** | 〔工作假设〕可跑的部分（静态线圈反解 · 参数扫描）住在 `design` 线的 `discharge` 与放电设计页的配置模式；外层优化器归 FyTok |
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
| **`FYL-DESIGN-24`** | 动理学平衡重构（`reconstruction` + `kinetic` 开关；`posterior` 并入） | analysis | ✓ **样板，本批落地** | `-12` P-22 · `-21` Q-1..Q-9 · `PLAN.md` §H |
| — | 磁测量反演（`reconstruction` + `only_magnetic`） | analysis | 待整理（与 -24 同图，是它的阶段 0） | `-12` |
| — | 剖面拟合（`profile`）· 时间序列（`series`） | analysis | 待整理（内核门今天不认，先重测 G-1） | `-12` |
| — | 定态输运（`transport`）· 含时演化（`evolve`） | model | 待整理 | `-10` |
| — | 0-D 放电（`zerod`）· 位形与线圈电流（`discharge`）· 脉冲轨迹（`pfwave`） | design | 待整理 | `-09` |
| — | 击穿（`breakdown`） | control · design | 待整理 | `-09` |

★"待整理"的章**不是空缺的功能**：它们的裁定都在正本里，缺的只是按 W-2 的形重写一遍。
每写成一章，本表改一行。

(fylite-scenario-lines-trace)=
# 五 · 追溯 (Traceability)

| 本篇 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 | `FYL-CONOPS-00` S-L1..S-L5 · `lines.jsonld` `fylite:lines` | 各章的"场景定义"节 |
| §二 | `lines.jsonld` `fylite:scenarios`（生成物）· `FYL-DESIGN-17` E-8 / E-17 | G-1 → `tools/make-scenario-templates.py` |
| §三 | `FYL-DESIGN-22` T-3 / T-4 | `FYL-DESIGN-24` 及后续各章 |
