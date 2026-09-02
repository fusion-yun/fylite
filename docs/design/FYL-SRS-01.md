---
document_id: FYL-SRS-01
title: FyLite 软件需求规格 (FyLite Software Requirements Specification)
shortname: fylite-srs
version: "0.4"
date: 2026-08-23
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Fable 5
created: 2026-08-18T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-08-23T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.4 放电运行设计域补全（WD 期内 MINOR）：新增 FR-PULSE-003 运行域判据
    （须标明所对照公开量的性质）、FR-PULSE-004 磁通预算（未声明摆幅须报未知）、
    FR-PULSE-005 前馈逐通道电流与电压（限值只报告不裁剪，校验与设计分列）；
    FR-OPTIM-001 补起始状态与失败态措辞的约束（容差按量纲分别定义）；新增
    FR-OPTIM-003 位形判据（边界类别、打击点、壁间隙、q95、l_i(3)、虚拟垂直反馈
    比，带被动结构时并给 n = 0 增长率）。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-srs

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-SRS-01` |
| 文档名称 (Title) | FyLite 软件需求规格 (FyLite Software Requirements Specification) |
| 短名 / Slug | `fylite-srs` |
| 版本 (Version) | v0.4 |
| 发布日期 (Date of Issue) | 2026-08-23 |
| 信息分类 (Information Class) | Specification (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | IEEE Std 29148 |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | Yes (规范性) |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Fable 5 |
| 受众 (Audience) | maintainers / solver authors / LLM-tool integrators / FyTok developers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | FYL-CONOPS-00 v0.3（运行概念：五类应用任务轻量覆盖、资源包络与基准口径） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

(fylite-srs-abstract)=
# 摘要 (Abstract)

本文件规定 FyLite 的软件需求。需求自 {ref}`FYL-CONOPS-00 <conops-fylite-abstract>`
导出：五类应用任务的轻量覆盖（{ref}`conops-fylite-scope-tasks`）给出五个任务域的功能
需求，资源包络（{ref}`conops-fylite-envelope`）给出非功能需求，双宿主与工具面交付形态
给出横切域需求。本版覆盖 as-built 能力的需求化与包络的可验证化；后续版本随覆盖
深化扩充。

(fylite-srs-conventions)=
# 约定与术语 (Conventions and Terminology)

- 需求条款使用 RFC 2119 关键字（**必须 (MUST)** / **禁止 (MUST NOT)** /
  **应当 (SHOULD)** / **可以 (MAY)**），每条恰一个关键字，不携认识论标签。
- 需求 ID 形如 `FR-<DOMAIN>-NNN` / `NR-<DOMAIN>-NNN`；`<DOMAIN>` 权威清单在
  `.context/PROJECT.md` §4。
- 术语沿 `FYL-CONOPS-00` §约定与术语（轻量功能集、双宿主、交互档 / 批式档、协议成员、
  资源包络），本文件不重定义。
- **场景线（scenario line）**：四条面向任务的入口组织——物理建模、实验分析、放电设计、
  控制仿真——每条线在双宿主各有对应入口；五类应用任务中"放电运行设计"与"装置参数
  优化"共同落于放电设计线。
- **装置牌（device deck）**：装置几何 / 诊断 / 限值的外部数据目录，经环境变量或显式
  路径载入，不随包分发。

(fylite-srs-fr)=
# 功能需求 (Functional Requirements)

(fylite-srs-fr-model)=
## 物理建模域 MODEL (S-L1)

- **FR-MODEL-001** 系统**必须 (MUST)** 提供固定边界 Grad–Shafranov 平衡正演求解。
- **FR-MODEL-002** 系统**必须 (MUST)** 提供自由边界平衡正演，及其与导体回路耦合的
  时间演化。
- **FR-MODEL-003** 系统**必须 (MUST)** 提供 1.5-D 芯部输运推进步（给定平衡与剖面，
  推进输运方程）。
- **FR-MODEL-004** 系统**必须 (MUST)** 提供 0-D 规定剖面的放电集总演化。
- **FR-MODEL-005** 系统**必须 (MUST)** 提供局域线性稳定性与准线性湍流通量计算，
  且输运闭包档位（解析 / 新经典 / 湍流数值闭包）**必须 (MUST)** 可按名选取。

(fylite-srs-fr-analysis)=
## 实验分析域 ANALYSIS (S-L2)

- **FR-ANALYSIS-001** 系统**必须 (MUST)** 提供基于磁测量的平衡重构。
- **FR-ANALYSIS-002** 重构**必须 (MUST)** 可纳入动理约束，且约束权重取自逐点实测
  不确定度而非全局常数。
- **FR-ANALYSIS-003** 系统**必须 (MUST)** 提供带正则化与自动光滑度选择的剖面拟合。
- **FR-ANALYSIS-004** 系统**必须 (MUST)** 提供弦积分诊断的层析反演。

(fylite-srs-fr-control)=
## 控制仿真域 CONTROL (S-L3)

- **FR-CONTROL-001** 系统**必须 (MUST)** 提供 n=0 垂直稳定性判定（增长率与可镇定性）。
- **FR-CONTROL-002** 系统**应当 (SHOULD)** 提供位置控制的闭环演示（控制律作用于
  集总模型、逐步回显轨迹）。

(fylite-srs-fr-pulse)=
## 放电运行设计域 PULSE (S-L4)

- **FR-PULSE-001** 系统**必须 (MUST)** 提供分相位波形的 0-D 放电分析。
- **FR-PULSE-002** 系统**必须 (MUST)** 提供击穿可行性判定，且判定结果按约束通道
  逐条给出（可定位到越限通道）。
- **FR-PULSE-003** 系统**必须 (MUST)** 与 0-D 放电结果同时给出**运行域判据**
  （格林沃尔德分数、柱形安全因子、`β_t` / `β_p` / `β_N`），且每一项**必须 (MUST)**
  标明所对照的公开量及其性质——经验边界、无壁参考值或柱形估计——不得表述为本层
  能计算的极限。
- **FR-PULSE-004** 系统**必须 (MUST)** 给出脉冲的**磁通预算**（电感磁通、斜坡电阻
  磁通、已消耗磁通、平顶平均环电压）。给定可用摆幅时**必须 (MUST)** 换算为可维持的
  平顶时长；未声明摆幅时**必须 (MUST)** 报"未知"，**不得 (MUST NOT)** 以缺省值代替。
- **FR-PULSE-005** 系统**必须 (MUST)** 由一条位形轨迹给出**前馈的逐通道电流与
  电压波形**及被动结构的感应电流。声明了通道限值时，越限**必须 (MUST)** 逐通道
  报告，**不得 (MUST NOT)** 静默裁剪设计。校验用的正向求解**必须 (MUST)** 与设计
  分列，并标明其为"实际得到"而非"所要求"。

(fylite-srs-fr-optim)=
## 装置参数优化域 OPTIM (S-L5)

- **FR-OPTIM-001** 系统**必须 (MUST)** 提供静态线圈反解（目标形状 → 线圈电流）。
  反解**必须 (MUST)** 能在装置不带参考放电时自行给出起始状态，且该起始状态
  **必须 (MUST)** 声明其不是平衡。反解结果与目标的偏差超出容差时**必须 (MUST)**
  以失败态报出，**不得 (MUST NOT)** 与达标结果共用措辞；容差**必须 (MUST)** 按量纲
  分别定义。
- **FR-OPTIM-002** 系统**必须 (MUST)** 提供二维参数扫描并输出可行域判读。
- **FR-OPTIM-003** 系统**必须 (MUST)** 与反解结果同时给出**位形判据**：边界类别
  （限制器 / X 点）、打击点、最小壁间隙、`q95`、`l_i(3)`，以及维持该平衡所需的
  **虚拟垂直反馈电流与等离子体电流之比**。装置描述带被动结构时**必须 (MUST)** 一并
  给出 n = 0 垂直模增长率与其区制判据。

(fylite-srs-fr-host)=
## 双宿主域 HOST（横切）

- **FR-HOST-001** 四条场景线**必须 (MUST)** 在两个宿主（本机 Python 环境、浏览器
  WebAssembly 页面）均可执行；宿主绑定能力（如网络装置数据访问）**可以 (MAY)** 仅在
  单宿主提供，但其宿主限定**必须 (MUST)** 显式声明。
- **FR-HOST-002** 批式档任务（自洽外环、全网格扫描）**必须 (MUST)** 可分步执行且可
  中断；批式档任务**禁止 (MUST NOT)** 以交互档形式呈现。
- **FR-HOST-003** 系统**必须 (MUST)** 支持三类交互面——Python / shell 交互、浏览器
  页面、AI 平台工具插件（Claude / Claude Code / DeepSeek 等 harness，经 MCP / LLM
  工具 schema）；三类交互面**必须 (MUST)** 反射同一能力集（工具插件面经
  FR-TOOL-002 / FR-TOOL-003 的能力目录接入）。

(fylite-srs-fr-data)=
## 数据域 DATA（横切）

- **FR-DATA-001** 装置几何与限值**必须 (MUST)** 经外部装置牌载入（环境变量或显式
  路径）；装置牌与实验数据**禁止 (MUST NOT)** 随包分发。
- **FR-DATA-002** 平衡结果**必须 (MUST)** 可写出与读回 g-file 格式。
- **FR-DATA-003** 每次求解运行**必须 (MUST)** 发射运行清单，记录输入来源、参数、
  软件版本与产物指纹。

(fylite-srs-fr-tool)=
## 工具面域 TOOL（横切）

- **FR-TOOL-001** 系统**必须 (MUST)** 提供命令行入口，覆盖求解、绘图、能力描述与
  清单操作。
- **FR-TOOL-002** 系统**必须 (MUST)** 提供机器可读的能力目录，且目录**必须 (MUST)**
  自声明清单派生（禁手抄）。
- **FR-TOOL-003** LLM 工具面（MCP 与 JSON-RPC over stdio）**必须 (MUST)** 反射同一
  能力目录；工具面**禁止 (MUST NOT)** 引入第二条执行路径。

(fylite-srs-nr)=
# 非功能需求 (Non-functional Requirements)

(fylite-srs-nr-env)=
## 资源包络域 ENV

- **NR-ENV-001** 系统**禁止 (MUST NOT)** 依赖分布式运行时或必需的服务端组件；全部
  功能在单机完成，浏览器宿主加载后**必须 (MUST)** 离线可用。
- **NR-ENV-002** 交互档操作的响应时间**必须 (MUST)** 处于毫秒至秒量级（ms ~ s）。
  基准硬件口径为**单机笔记本电脑**（主流消费级，无独立加速器要求）。
- **NR-ENV-003** 并行度**必须 (MUST)** 限于单机工作线程（线程数可配置）；浏览器宿主
  以单线程为基线。
- **NR-ENV-004** 双宿主**必须 (MUST)** 共享同一计算核；核心数值结果的跨宿主一致性
  **必须 (MUST)** 由回归测试以显式容差断言。
- **NR-ENV-005** 每项主要功能（能力目录条目与场景入口）**必须 (MUST)** 声明其预期
  响应时间预算（毫秒至秒量级内的值或区间），且声明**必须 (MUST)** 随能力目录机器
  可读发布；实测响应超出所声明预算按回归缺陷处理。

(fylite-srs-nr-dep)=
## 依赖纪律域 DEP

- **NR-DEP-001** Python 宿主的必需运行时依赖**必须 (MUST)** 仅为 numpy；可选能力
  **必须 (MUST)** 经 extras 隔离，缺席时核心功能不降级。
- **NR-DEP-002** 包内代码**禁止 (MUST NOT)** 导入 `sp` 或任何 `fy*` 包（协议成员
  纯净），并由静态检查守门。

(fylite-srs-nr-qual)=
## 质量域 QUAL

- **NR-QUAL-001** 每条 `FR-*` 需求**应当 (SHOULD)** 有 ≥ 1 个自动化测试覆盖其验收
  行为。
- **NR-QUAL-002** 数值移植类功能**必须 (MUST)** 对冻结的参考夹具做容差显式的
  数值一致性回归。

(fylite-srs-ext)=
# 外部接口 (External Interfaces)

| 接口 | 形态 | 方向 |
| :--- | :--- | :--- |
| 命令行 | `fylite` 单命令多子命令 | 用户 → 系统 |
| JSON-RPC | JSON-RPC 2.0 over stdio | 集成方 ↔ 系统 |
| MCP | MCP server over stdio | LLM 宿主 ↔ 系统 |
| 浏览器页面 | 静态页面 + WebAssembly 模块 | 用户 ↔ 系统 |
| 装置牌 | 外部数据目录（环境变量 / 显式路径） | 数据 → 系统 |
| g-file | 平衡交换文件 | 系统 ↔ 外部工具 |
| 运行清单 | 机器可读运行记录（JSON 系） | 系统 → 集成方 |

(fylite-srs-constraints)=
# 约束条件 (Constraints)

- **位形边界**：适用范围限轴对称托卡马克（承 `FYL-CONOPS-00` §范围外）。
- **包络不变式**：`NR-ENV-*` 四条为定位性约束，功能演进**禁止 (MUST NOT)** 突破
  （承 {ref}`conops-fylite-envelope`）。
- **数据边界**：装置与实验数据不入仓、不随包分发（`FR-DATA-001`）。
- **文档边界**：受跟踪 / 分发内容对外部闭源仓库内部文档的引用**禁止 (MUST NOT)**
  （`.context/PROJECT.md` §6）；用户 / 参考文档**禁止 (MUST NOT)** 引用设计书文档。
- **许可**：Apache-2.0（随 LICENSE / NOTICE）。

(fylite-srs-trace)=
# 需求追溯矩阵 (Traceability Matrix)

:::{table} 需求 → FYL-CONOPS-00 上游锚点追溯。
:name: tbl-fylite-srs-trace
:align: left

| 需求 | ConOps 上游 |
| :--- | :--- |
| FR-MODEL-001..005 | S-L1 物理建模（{ref}`conops-fylite-scenarios`）；覆盖表 {numref}`tbl-conops-fylite-coverage` 行 1 |
| FR-ANALYSIS-001..004 | S-L2 实验分析；覆盖表行 2 |
| FR-CONTROL-001..002 | S-L3 控制仿真；覆盖表行 3 |
| FR-PULSE-001..005 | S-L4 放电运行设计；覆盖表行 4 |
| FR-OPTIM-001..003 | S-L5 装置参数优化；覆盖表行 5 |
| FR-HOST-001..002 | 双宿主与交互 / 批式档约定（{ref}`conops-fylite-conventions`、{ref}`conops-fylite-scenarios`） |
| FR-HOST-003 | 基准口径与运行环境：三类交互面（{ref}`conops-fylite-envelope`） |
| FR-DATA-001 | 范围外之数据边界与利益相关者"维护者"关切（{ref}`conops-fylite-scope-out`） |
| FR-DATA-002..003 | S-L1 / S-L2 产物交换与"验证面可断言"要求（{ref}`conops-fylite-scenarios`、{ref}`conops-fylite-evolution` 覆盖深化） |
| FR-TOOL-001..003 | 利益相关者"LLM 工具集成者"（{ref}`conops-fylite-stakeholders`） |
| NR-ENV-001..005 | 资源包络与响应预算（{ref}`conops-fylite-envelope`） |
| NR-DEP-001..002 | 生态关系：零代码依赖协议成员（{ref}`conops-fylite-abstract`） |
| NR-QUAL-001..002 | 系统演进"覆盖深化：验证可持续断言"（{ref}`conops-fylite-evolution`） |
:::

:::{note} Rationale
FyLite 为独立软件包，不接收平台层需求分配；追溯链止于本仓 ConOps
（`FYL-CONOPS-00`），其对上游概念（五类应用任务）的指认由 ConOps 承载，本文件不
直接引用外部仓库文档。
:::
