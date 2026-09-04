---
document_id: FYL-SRS-01
title: FyLite 软件需求规格 (FyLite Software Requirements Specification)
shortname: fylite-srs
version: "1.0"
date: 2026-09-04
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Fable 5
created: 2026-08-18T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-04T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v1.0 全文整理（用户「优化重写整个设计文档」，2026-09-04）。四处实质变化：
    ①「双宿主」退役（`FYL-CONOPS-00` v1.0）：HOST 域改写——FR-HOST-001 说的是**两个运行时**
    （本机 / 浏览器），FR-HOST-003 说的是**四个宿主**（命令行 · Python 库 · 浏览器页面 ·
    AI 工具面）；NR-ENV-004 由「双宿主共享同一计算核」改为「多宿主共享同一内核契约，
    跨运行时一致性由 V&V 登记册记录」（`FYL-DESIGN-16` K-6 的改口落文本）。
    ②新增 **KERNEL 域** FR-KERNEL-001..004（内核契约：文档门唯一接口 · code 表与输出
    声明 · 后端显式选择不静默回退 · 内核无状态、状态随文档走），出自 `FYL-DESIGN-16`
    v2.0 的用户裁定；域表同步登记于 `.context/PROJECT.md` §4。
    ③FR-DATA-001 改写：**实验数据**不入仓不随包；**公开的装置描述**自 A-Box 誊录进
    `app/facts/device/`（实拷，随站点与可执行文件走）——此前那句「装置牌不随包分发」与
    2026-09-02 起的仓树不符。
    ④新增附录「提案登记」：把八份设计文档各自提出、尚未落文本的需求 / 设计元素编号
    集中登记，消掉两处撞号（首屏判据只留 NR-QUAL-005；`DE-LOG-08..10` 留给页面提案，
    内核契约的设计元素在 SDD 取 DE-LOG-11 起），并登记 UI 域。追溯矩阵相应补行。
    · v0.5 工具面与交付形态：FR-TOOL-001 改写、新增 FR-TOOL-004（一份规格三个宿主）；
    外部接口补单一可执行文件与静态站点（依据 `FYL-DESIGN-15`）。
    · v0.4 放电运行设计域补全：FR-PULSE-003..005、FR-OPTIM-003，FR-OPTIM-001 补起始态
    与失败态措辞。
    · v0.3 / v0.2 / v0.1：自 FYL-CONOPS-00 导出五任务域 FR、包络 NR、横切域与追溯矩阵。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-srs

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-SRS-01` |
| 文档名称 (Title) | FyLite 软件需求规格 (FyLite Software Requirements Specification) |
| 短名 / Slug | `fylite-srs` |
| 版本 (Version) | v1.0 |
| 发布日期 (Date of Issue) | 2026-09-04 |
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
| 上游输入 (Upstream Inputs) | FYL-CONOPS-00 v1.0（运行概念：五类应用任务轻量覆盖、资源包络与基准口径、宿主与运行时）· FYL-DESIGN-16 v2.0（内核契约的用户裁定，KERNEL 域的来源） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

(fylite-srs-abstract)=
# 摘要 (Abstract)

本文件规定 FyLite 的软件需求。需求自 {ref}`FYL-CONOPS-00 <conops-fylite-abstract>`
导出：五类应用任务的轻量覆盖（{ref}`conops-fylite-scope-tasks`）给出五个任务域的功能
需求，资源包络（{ref}`conops-fylite-envelope`）给出非功能需求，宿主与运行时、数据、
工具面与内核契约给出横切域需求。本版覆盖 as-built 能力的需求化、包络的可验证化，以及
2026-09-04 裁定的内核契约；后续版本随覆盖深化扩充。

(fylite-srs-conventions)=
# 约定与术语 (Conventions and Terminology)

- 需求条款使用 RFC 2119 关键字（**必须 (MUST)** / **禁止 (MUST NOT)** /
  **应当 (SHOULD)** / **可以 (MAY)**），每条恰一个关键字，不携认识论标签。
- 需求 ID 形如 `FR-<DOMAIN>-NNN` / `NR-<DOMAIN>-NNN`；`<DOMAIN>` 权威清单在
  `.context/PROJECT.md` §4（本版新增 `KERNEL` 与 `UI` 两域）。
- 术语沿 `FYL-CONOPS-00` §约定与术语（轻量功能集、**宿主** / **运行时**、交互档 /
  批式档、协议成员、资源包络），本文件不重定义。
- **场景线（scenario line）**：四条面向任务的入口组织——物理建模、实验分析、放电设计、
  控制仿真——每条线在两个运行时各有对应入口；五类应用任务中「放电运行设计」与「装置
  参数优化」共同落于放电设计线。
- **装置描述（device description）**：装置几何 / 诊断 / 限值的文档（`fyo:DeviceDescription`），
  真源是外部 A-Box；本仓只持有它的公开誊录。**实验数据**（炮的测量）是另一件事，
  不入仓。
- **内核契约（kernel contract）**：内核后端自报的 code 表与逐 code 的输入 / 输出声明，
  外加「一份 fyo 计划进、一份 fyo 记录出」的文档门（`FYL-DESIGN-16`）。

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
  平顶时长；未声明摆幅时**必须 (MUST)** 报「未知」，**不得 (MUST NOT)** 以缺省值代替。
- **FR-PULSE-005** 系统**必须 (MUST)** 由一条位形轨迹给出**前馈的逐通道电流与
  电压波形**及被动结构的感应电流。声明了通道限值时，越限**必须 (MUST)** 逐通道
  报告，**不得 (MUST NOT)** 静默裁剪设计。校验用的正向求解**必须 (MUST)** 与设计
  分列，并标明其为「实际得到」而非「所要求」。

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
## 宿主与运行时域 HOST（横切）

- **FR-HOST-001** 四条场景线**必须 (MUST)** 在两个运行时（本机、浏览器 WebAssembly
  页面）均可执行；只在一个运行时可用的能力（如网络装置数据访问）**可以 (MAY)** 存在，
  但其运行时限定**必须 (MUST)** 显式声明。
- **FR-HOST-002** 批式档任务（自洽外环、全网格扫描）**必须 (MUST)** 可分步执行且可
  中断；批式档任务**禁止 (MUST NOT)** 以交互档形式呈现。
- **FR-HOST-003** 系统**必须 (MUST)** 支持四个宿主——命令行、Python 库、浏览器页面、
  AI 平台工具面（Claude / Claude Code / DeepSeek 等 harness，经 MCP / LLM 工具 schema）；
  各宿主**必须 (MUST)** 反射同一能力集（工具面经 FR-TOOL-002 / FR-TOOL-003 的能力目录
  接入）。新增一个宿主**禁止 (MUST NOT)** 要求内核契约（FR-KERNEL-*）改变。

(fylite-srs-fr-kernel)=
## 内核契约域 KERNEL（横切，2026-09-04 新立）

〔来源〕`FYL-DESIGN-16` v2.0 的用户裁定（K-1 / K-2 / K-4 / K-8 / F-1..F-4 / S-1..S-4）。
这些条款描述的是**目标态**：今天只有 `fylite case` 一条路经文档门（3 个 code），其余宿主
仍直接调用扁平 C 导出；分期见 `FYL-DESIGN-16` §分期。

- **FR-KERNEL-001** 宿主与中间层调用内核**必须 (MUST)** 只经文档门——一份 fyo 计划进、
  一份 fyo 记录出；内核的 C / wasm 扁平导出面**禁止 (MUST NOT)** 出现在宿主代码中，
  它是本地后端的实现细节。门上传递的结构**必须 (MUST)** 是不解析的扁平树（四段缓冲、
  索引相连），双向；内核**禁止 (MUST NOT)** 收路径字符串或自带任何序列化格式的解析器。
- **FR-KERNEL-002** 每个内核后端**必须 (MUST)** 自报 code 表——它完成哪些 code、每个
  code 要哪些输入、产哪些 fyo 路径、什么单位；宿主按表选后端、按声明读结果，**禁止
  (MUST NOT)** 以 ABI 版本号判断可否调用。内核对声明中缺失的槽**必须 (MUST)** 按名拒绝
  并一次列全，**禁止 (MUST NOT)** 以缺省值或同名尾段的另一个量顶替。
- **FR-KERNEL-003** 本地动态库、页内 WebAssembly、远端进程**必须 (MUST)** 登记在同一
  张后端表里并可按名或地址显式选择；所选后端不在场时系统**必须 (MUST)** 如实报出，
  **禁止 (MUST NOT)** 静默回退到能力更少的后端。每份记录**必须 (MUST)** 写明产生它的
  后端及其环境指纹。
- **FR-KERNEL-004** 内核**禁止 (MUST NOT)** 在调用之间留住状态；续跑所需的状态
  **必须 (MUST)** 作为文档里声明过的子树随计划进、随记录出，并带写它的那个内核的
  身份；内核**必须 (MUST)** 在每个步界能停下并交出完整状态，且对认不出的状态按名拒绝，
  除非调用方显式允许版本漂移。

(fylite-srs-fr-data)=
## 数据域 DATA（横切）

- **FR-DATA-001** 装置描述**必须 (MUST)** 以 fyo 文档（`fyo:DeviceDescription`）进入
  系统，其真源在外部 A-Box，本仓只持有公开誊录；**实验数据**（炮的测量与切片）
  **禁止 (MUST NOT)** 入仓或随包分发，只在运行时经数据源取回。
- **FR-DATA-002** 平衡结果**必须 (MUST)** 可写出与读回 g-file 格式。
- **FR-DATA-003** 每次求解运行**必须 (MUST)** 发射运行清单，记录输入来源、参数、
  软件版本、后端与产物指纹。

(fylite-srs-fr-tool)=
## 工具面域 TOOL（横切）

- **FR-TOOL-001** 系统**必须 (MUST)** 提供命令行入口，覆盖求解、绘图、能力描述、清单
  操作、算例语料与 V&V 登记册、运行记录的重放 / 报告 / 溯源、数据层的识别与格式转换、
  算例（计划 → 内核 → 记录），以及本机应用的启动。命令行的**命令与参数必须 (MUST) 由
  一份声明式规格定义**（见 FR-TOOL-004），不得逐宿主手写。
- **FR-TOOL-002** 系统**必须 (MUST)** 提供机器可读的能力目录，且目录**必须 (MUST)**
  自声明清单派生（禁手抄）。
- **FR-TOOL-003** LLM 工具面（MCP 与 JSON-RPC over stdio）**必须 (MUST)** 反射同一
  能力目录；工具面**禁止 (MUST NOT)** 引入第二条执行路径。
- **FR-TOOL-004** 提供命令行的**每个宿主**（Python 控制台脚本、Rust 单一可执行文件、
  浏览器页面的启动参数）**必须 (MUST)** 由同一份声明式规格建出其解析面与用法；任一宿主
  **禁止 (MUST NOT)** 另持一份命令表或选项名单。只属某一宿主的命令或参数**必须 (MUST)**
  在规格内标出其宿主；不承载某命令的宿主**必须 (MUST)** 按名委托或按名拒绝，**禁止
  (MUST NOT)** 静默接受，也**禁止 (MUST NOT)** 以能力更少的第二份实现回答。

(fylite-srs-nr)=
# 非功能需求 (Non-functional Requirements)

(fylite-srs-nr-env)=
## 资源包络域 ENV

- **NR-ENV-001** 系统**禁止 (MUST NOT)** 依赖分布式运行时或必需的服务端组件；全部
  功能在单机完成，浏览器运行时加载后**必须 (MUST)** 离线可用。远端内核后端
  （FR-KERNEL-003）**必须 (MUST)** 是可选项，缺省为本地。
- **NR-ENV-002** 交互档操作的响应时间**必须 (MUST)** 处于毫秒至秒量级（ms ~ s）。
  基准硬件口径为**单机笔记本电脑**（主流消费级，无独立加速器要求）。
- **NR-ENV-003** 并行度**必须 (MUST)** 限于单机工作线程（线程数可配置）；浏览器运行时
  以单线程为基线。
- **NR-ENV-004** 多个宿主**必须 (MUST)** 共享同一内核契约（FR-KERNEL-001 / -002）；
  同一 code 在两个后端（本机与浏览器，或任意两个后端）上的数值一致性**必须 (MUST)**
  由回归测试以显式容差断言，并作为 V&V 登记册的一类记录（差异须由环境指纹解释）。
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
| 命令行 | `fylite` 单命令多子命令（Python 宿主）与 `fylite`（Rust 宿主，**唯一的可执行文件**，同样是单命令多子命令）；两者由同一份规格建出（FR-TOOL-004） | 用户 → 系统 |
| JSON-RPC | JSON-RPC 2.0 over stdio | 集成方 ↔ 系统 |
| MCP | MCP server over stdio | LLM 宿主 ↔ 系统 |
| 浏览器页面 | 静态页面 + WebAssembly 模块；启动参数由命令行规格声明 | 用户 ↔ 系统 |
| 单一可执行文件 | 内嵌浏览器前端的本机程序：回环地址伺服 + 拉起系统浏览器，另答一组只读 `/api/*` | 用户 ↔ 系统 |
| 静态站点 | 浏览器前端的发布子集（页面 + wasm 制品），任意静态主机，加载后离线可用 | 用户 ↔ 系统 |
| 内核文档门 | 一份 fyo 计划进、一份 fyo 记录出（FR-KERNEL-001）；本地 / 页内 wasm / 远端三种后端同一扇门 | 中间层 ↔ 内核 |
| 装置描述 | `fyo:DeviceDescription` 文档（公开誊录随站点走；真源在外部 A-Box） | 数据 → 系统 |
| 实验数据源 | MDSplus（mdsip）只读，运行时按炮号与时间取 | 数据 → 系统 |
| g-file | 平衡交换文件 | 系统 ↔ 外部工具 |
| 运行清单 | 机器可读运行记录（JSON-LD） | 系统 → 集成方 |

(fylite-srs-constraints)=
# 约束条件 (Constraints)

- **位形边界**：适用范围限轴对称托卡马克（承 `FYL-CONOPS-00` §范围外）。
- **包络不变式**：`NR-ENV-*` 为定位性约束，功能演进**禁止 (MUST NOT)** 突破
  （承 {ref}`conops-fylite-envelope`）。
- **数据边界**：实验数据不入仓、不随包分发（`FR-DATA-001`）。
- **文档边界**：受跟踪 / 分发内容对外部闭源仓库内部文档的引用**禁止 (MUST NOT)**
  （`.context/PROJECT.md` §6）；用户 / 参考文档**禁止 (MUST NOT)** 引用设计书文档。
- **许可**：Apache-2.0（随 LICENSE / NOTICE）；内核源码在私有仓，制品随包。

(fylite-srs-proposals)=
# 附录：提案登记 (Appendix: Proposal Register)

〔信息性〕八份设计文档各自提出了尚未落文本的条款。此处**只登记编号与出处**，不给
条款力——落文本仍走本文件 / `FYL-SDD-01` 的版本行。登记的目的是让编号在文档之间
**唯一**：2026-09-04 整理时发现首屏判据被提了两次（`-11` NR-QUAL-005 与 `-12`
NR-QUAL-006），页面提案与内核契约的设计元素又都想用 `DE-LOG-08` 起——本表定下归属。

| 提案 ID | 出处 | 大意 |
| :--- | :--- | :--- |
| FR-PULSE-006..012 | `FYL-DESIGN-09` | 脉冲脚本单源 · 平顶随状态 · 已解 / 插值标注 · 仿真产物是记录 · 两档驱动 · 启动开关 · 两档保真度 |
| FR-MODEL-006 / -007 | `FYL-DESIGN-10` | 时间轴归放电场景线 · 边界与度规为独立入口 |
| FR-DATA-004 / -005 / -007 | `FYL-DESIGN-13` | 只读无表达式端点 · 抽稀步长随图声明 · 取数会话可导出足迹 |
| FR-DATA-006 | `FYL-DESIGN-10` | 建模 → 放电的交接须为命名工件 |
| FR-ANALYSIS-005..008 | `FYL-DESIGN-12` | 后验语义 · 判据只有一处 · 约束来源可见 · 预设只填不跑 |
| FR-HOST-004 / -005 | `FYL-DESIGN-13` | 缺网关时如实降级 · 两个宿主同一组端点 |
| FR-HOST-006 / -007 | `FYL-DESIGN-11` | 宿主自述由探测决定 · 桌面下显示伺服地址 |
| FR-UI-001 / -002 | `FYL-DESIGN-11` | 常驻外壳 · 四页只差三个槽（UI 域：浏览器前端外壳与页面，横切） |
| NR-QUAL-003 | `FYL-DESIGN-11` | 视觉系统自述与取值一致 |
| NR-QUAL-004 | `FYL-DESIGN-11`（正本）；`-10` / `-12` / `-13` 引用 | 判定类信息不得以颜色为唯一编码 |
| NR-QUAL-005 | `FYL-DESIGN-11`（正本）；`-10` / `-12` 引用 | 功能页面 16:9 首屏须落一处输出（★`-12` 原写 NR-QUAL-006，并入本号；NR-QUAL-006 空置） |
| DE-LOG-08 | `FYL-DESIGN-09` | 世代与脏标记 |
| DE-LOG-09 | `FYL-DESIGN-10` | 自述与能力一致 |
| DE-LOG-10 | `FYL-DESIGN-10`（正本）；`-12` 引用 | 判定块为一等产物 |
| DE-COMP-05 增列 | `-09` / `-10` / `-11` / `-13` | 浏览器前端逐页列明形态、投递面与门禁 |
| DE-LOG-11 / -12 | `FYL-SDD-01` v1.0 **已取用** | 文档门与扁平树 · 内核无状态（内核契约，来自 `FYL-DESIGN-16`） |

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
| FR-HOST-001..002 | 运行时与交互 / 批式档约定（{ref}`conops-fylite-conventions`、{ref}`conops-fylite-scenarios`） |
| FR-HOST-003 | 基准口径与运行环境：四个宿主（{ref}`conops-fylite-envelope`） |
| FR-KERNEL-001..004 | 系统演进「内核可替换」（{ref}`conops-fylite-evolution`）；建设原则 5（{ref}`conops-fylite-principles`）；设计正本 `FYL-DESIGN-16` |
| FR-DATA-001 | 范围外之数据边界与利益相关者「维护者」关切（{ref}`conops-fylite-scope-out`） |
| FR-DATA-002..003 | S-L1 / S-L2 产物交换与「验证面可断言」要求（{ref}`conops-fylite-scenarios`、{ref}`conops-fylite-evolution` 覆盖深化） |
| FR-TOOL-001..004 | 利益相关者「LLM 工具集成者」（{ref}`conops-fylite-stakeholders`）；四个宿主（{ref}`conops-fylite-envelope`） |
| NR-ENV-001..005 | 资源包络与响应预算（{ref}`conops-fylite-envelope`）；NR-ENV-004 另承「内核可替换」 |
| NR-DEP-001..002 | 生态关系：零代码依赖协议成员（{ref}`conops-fylite-abstract`） |
| NR-QUAL-001..002 | 系统演进「覆盖深化：验证可持续断言」（{ref}`conops-fylite-evolution`） |
:::

:::{note} Rationale
FyLite 为独立软件包，不接收平台层需求分配；追溯链止于本仓 ConOps
（`FYL-CONOPS-00`），其对上游概念（五类应用任务）的指认由 ConOps 承载，本文件不
直接引用外部仓库文档。KERNEL 域的条款是 2026-09-04 用户裁定的需求化：它们今天多数
**未落地**，NR-QUAL-001 要求的测试随 `FYL-DESIGN-16` 的分期一并到来。
:::
