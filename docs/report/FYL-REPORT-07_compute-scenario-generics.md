---
document_id: FYL-REPORT-07
title: fy 体系对计算场景通用功能的完备性 · 自洽性 · 易用性评估 (Assessing the fy Ecosystem's Generic Compute-Scenario Functions — Completeness, Self-Consistency, Usability)
shortname: fylite-report-compute-scenario-generics
version: "0.3"
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
  change: 'v0.3：新增 §9「落地记录」——用户「落地 R1～9」（2026-09-12）。九条逐条给出
    落成什么、量到什么、没落成的那一条为什么。R-5 · R-6 · R-7 · R-8（其可落地的部分）·
    R-2 与 R-1 的大半已落地并带闸；R-3 半落；R-4 **不落**并改判（前提是错的，见 C-28）；
    R-9 不落。自洽性登记增 C-28（code 层参数面无声明）· C-29（`fy list` 有错话而退出 0）；
    C-1..C-4 · C-6 · C-10 · C-11 · C-12 · C-15 · C-16 · C-21 · C-23 · C-26 · C-27 判关。
    v0.2：新增 §8「补充讨论：fylite 与 fytok 的功能界限」（用户裁定 2026-09-12：同一 fyo
    描述协议；fytok 含完整功能——插件 · 工作流 · 开放集成外部物理代码；fylite 是完成核心目标的
    最小工具集，自包含、不依赖外部物理模块、保持轻量）——把界限落成八项功能的归属表、协议
    须携带的三条不变式、两侧的负面清单，并据此把 R-1..R-9 分为「协议承重」与「fylite 内部」两档。
    v0.1（全新文档）：以 fyo 对计算场景的描述为参照，逐项评估 fy 体系
    （fylite · fylite_kernel · fyo · fydata · fydoc）在编辑 / 可视化 / 执行 / 状态追踪 /
    导入 / 导出 / 断点恢复 / 溯源八项通用功能上的完备性、自洽性与易用性。证据为六个检出的
    源码与文档、本环境一次内核与中间层构建、两次 pytest 全量实测。登记自洽性缺口 C-1..C-29（v0.3 关 14 条）、
    易用性观察 U-1..U-9，给出九条建议 R-1..R-9（各带关闭判据）。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-report-compute-scenario-generics

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-REPORT-07` |
| 文档名称 (Title) | fy 体系对计算场景通用功能的完备性 · 自洽性 · 易用性评估 |
| 短名 / Slug | `fylite-report-compute-scenario-generics` |
| 版本 (Version) | v0.3 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | `Report`（ISO/IEC/IEEE 15289 Annex A；评估 study） |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | `concept`（ISO/IEC/IEEE 15288） |
| 规范性 (Normative) | No（信息性——建议须经 `FYL-SRS-01` / `FYL-SDD-01` / `FYO-ADR-*` 才成规矩） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | 维护者 / FyTok developers / fyo · fydata · fydoc 维护者 / LLM-tool integrators |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 用户裁定 2026-09-12（fylite / fytok 界限）· `FYL-CONOPS-00` v1.0 §范围外 · 内核仓 `FYL-REPORT-06` v0.8（算例模型与排期 B-1..B-10）· `FYL-DESIGN-16` v2（内核契约 S-1..S-6 · H-1..H-8）· `FYL-DESIGN-17`（`fy run`）· `FYL-DESIGN-18`（前端 U-1..U-25）· `FYL-DESIGN-20`（状态报告 M-1..M-13）· fyo 仓 `FYO-ADR-07` · `FYO-REPORT-05` v0.5 · fydata `README.md` G-* · fydoc `cases/README.md` · 本仓 `TODO.md` |
| 批准 (Approval) | — |
:::

(fylite-report-07-abstract)=
# 摘要 (Abstract)

**问题。** fy 体系以 fyo 本体描述计算场景（`fyo:ScenarioSpecification` 进、`spo:ComputationRecord` 出）。
本报告评估这套体系对**与物理无关的通用功能**——编辑 · 可视化 · 执行 · 状态追踪 · 导入 · 导出 ·
断点恢复 · 溯源——的**完备性**（描述面 / 设计面 / 落地面 / 闸禁面各覆盖到哪）、**自洽性**
（层与层、仓与仓、文档与代码之间有无矛盾）与**易用性**（从检出到一次可信运行要几步、失败时说不说清）。

**结论（〔已确立〕，证据在正文各节）。**

1. **描述面完备、但不在手边。** 八项功能所需的本体词——计划 / 记录 / 检查点 / 端口绑定 / 具体化 /
   执行环境 / 呈现规格——**全部**来自上游 `spo`；fyo 自铸的只是聚变域特化（任务分类学 · 比较记录 ·
   格式枚举 · 一种视图）。`spo` **不在任何一个检出里**（fyo `catalog.yaml` 委托到同级目录 `../spo`），
   fyo 的 CQ 套件对 `Checkpoint` / `run_state` 的断言在本环境无法解析。**施动者**（谁执行了运行）
   在两侧都没有类（`FYO-ADR-07` OI-3）。
2. **设计面完备。** 八项功能各有裁定与关闭判据（`FYL-REPORT-06` B-1..B-10、`-16` S-1..S-6、`-18` U-8..U-19、
   `-20` M-1..M-13）。设计与落地之间的差是本报告登记的主体。
3. **落地面不均衡。** 按四个宿主（命令行 `fy` · Python 库 · 浏览器页面 · AI 工具面）计：
   **执行**（单步 / 整案）4/4，**导入 / 导出** 4/4（宿主间端点能力不同），**可视化** ✓3 ✗1，
   **编辑** ✓2 ◐2，**溯源** 4/4 但**两种记录形**（Rust `spo:ComputationRecord` 与 Python `RunManifest`）
   字段互不相交，**状态追踪** 只有终态两值（`succeeded` / `rejected`）且宿主间三份词表，
   **断点恢复 1/4**——只在浏览器，且该模块**没有任何页面加载**、闸子用的是**假步进器**、
   `fy run` 没有 `--resume`、Python 没有 `resume=`、`fylite:state` 不在任何 fyo 表里。
   断点恢复是八项里最不完备的一项。
4. **自洽性：登记 27 条矛盾（C-1..C-27）。** 集中在四处：文档滞后于 2026-09-04 的宿主收敛
   （5 条）、记录形 · 状态词表 · 身份键 · 续跑语义在 Rust / Python / JS 三端各一份（8 条）、
   本体与仓际的前缀与指针（4 条）、数据仓的发布与审查闸按字面而非按意图实现（6 条）；
   另 4 条出自本环境实测（含 `fy` 一次真跑）。
5. **易用性：实测。** 干净容器里按文档走一遍：内核可建；中间层 `.so` 因缺系统 HDF5 / netCDF 走
   `--static`，编译成功后被制品卫生闸拒绝安装（284 条开发机路径），无文档化的绕行；
   无该库时 pytest **73 失败 / 10 错误**，而 README 承诺「缺内核按名跳过」——**缺的是数据库
   而非内核，跳过没有覆盖到它**；手工装上后 **2046 通过 / 405 跳过 / 3 失败**（三条为本报告
   自身与手工安装所致）。「按名拒绝」的纪律在 `fy` 与语料上执行得很彻底，是易用性最强的一面。

**升格建议**九条（R-1..R-9，{ref}`fylite-report-07-recommendations`），首位是把断点恢复从
「一个宿主的一个未接线模块」做成 `-16` S-2 / S-4 裁定的样子：`fylite:state` 子树入 fyo 表、
`--resume` / `resume=` 入 `_cli.json` 与 `cases.run`、闸子换成真内核。

(fylite-report-07-criteria)=
# 1. 问题与判据 (The question, and what counts as answered)

**评估对象。** 六个检出（{numref}`tbl-r07-baseline`）；参照物是 fyo 对计算场景的描述
（`fyo:ScenarioSpecification` ⊑ `spo:ComputationPlan`；`spo:ComputationRecord`；
`FYO-ADR-07` D-1「一份结构进、一份结构出」）。物理保真度不在本报告范围——那是
`docs/reference/fidelity.md` 与校验册的事。

**八项功能的操作定义。** 每项按四个面判：

| 面 | 问什么 | 证据从哪来 |
| :--- | :--- | :--- |
| 描述面 | 本体有没有词说它 | fyo / spo 类与槽（`schema/src/`、`FYO-ADR-*`） |
| 设计面 | 有没有裁定与关闭判据 | `FYL-REPORT-06` · `FYL-DESIGN-16/17/18/20` · `FYL-SRS-01` |
| 落地面 | 四个宿主各能不能做 | 源码（`rust/` · `python/fylite/` · `app/assets/`）与本环境实测 |
| 闸禁面 | 有没有自动化断言守着 | `python/tests/` · `app/tests/validate-*.mjs` · `cargo test` · 数据仓 `tools/` |

**三个判据。**

- **完备性**：一项功能在四个面上各覆盖到哪；落地面按「四宿主中几个」计，不按「能不能用某种办法凑出来」计。
- **自洽性**：任意两处对同一事实的陈述是否一致——本体 ↔ 设计、设计 ↔ 代码、代码 ↔ 代码（Rust / Python / JS）、
  文档 ↔ 代码、仓 ↔ 仓。每条矛盾给证据与关闭判据。
- **易用性**：从干净检出到一次可信运行的步数与失败模式；失败是否按名报出；四个宿主之间一份工作能否搬动。
  只记**量到的**，不记印象。

**认识论标签。** 〔已确立〕有源码 / 实测证据；〔工作假设〕设计已定、落地未验；〔开放猜想〕两侧都未定。
缺失值记 `[TBD]`。本报告**只出证据与建议，不作裁定**——裁定归各仓治理。

(fylite-report-07-baseline)=
# 2. 证据基线 (Evidence baseline)

:::{table} 检出与本环境的构建产物（2026-09-12 实测）。
:name: tbl-r07-baseline
:align: left

| 仓 | 检出 | 版本自述 | 本环境做了什么 |
| :--- | :--- | :--- | :--- |
| `fylite` | `78b1531` (2026-09-11) | `VERSION` 0.0.1-alpha | pytest 全量两次（无 / 有数据库）；中间层 `--static` 构建 |
| `fylite_kernel` | `2e8684d` (2026-09-11) | 0.0.1 · ABI 153 · `sha256 97d1cc7a…` | `rust/build.sh` 成功，`.so` 装入 `fylite/python/fylite/_lib/` |
| `fyo` | `994dc3f` (2026-09-08) | v0.11 | 只读 |
| `fydata` | `da90d3d` (2026-09-10) | — | 只读 |
| `fydoc` | `d913456` (2026-09-11) | — | 只读；`tools/check_cases.py` 结果引自同日实测 |
| `IMAS-Data-Dictionary` | `f5d44e8` (2026-09-04) | — | 只读（中间层的 DD 表是提交进仓的生成物，DD 4.1.1） |
| `spo` | **不在环境中** | — | fyo `catalog.yaml` 委托到 `../spo`；本报告对 spo 词的陈述转引自 fyo 文档与 `FYL-REPORT-06` |
:::

实测命令与完整数字在 {ref}`fylite-report-07-appendix-measured`。

(fylite-report-07-ontology)=
# 3. 描述面：fyo / spo 对八项功能各说了什么 (What the ontologies can say)

〔已确立〕fyo 场景层（`schema/src/scenario/`，8 个模块）自铸的是**聚变域特化**：`ApplicationTask`
（⊑ `ComputationalProcess`）、`ScenarioSpecification`（⊑ `ComputationPlan`，加 `prescribed_task_kind` /
`solver_selection` / `iteration_cap`）、`ForwardOperator` / `OuterOperator` / `PhysicsModel` / `InferenceEngine`
（均 ⊑ `Code`）、`ConvergenceCriterion`、`SolverInvocation` 族、`EngineeringPortRun`（`live` / `stub` / `archive`）、
比较记录族（`ComparisonRecord` / `AcceptanceCriterion` / `ComparisonFinding`，`Verdict` 四值）、格式枚举
`FusionSerializationFormat`（`geqdsk` · `aeqdsk` · `imas_hdf5` · `gacode_input` · `jetto_binary`）、一种视图
`PoloidalSectionView`。

:::{table} 八项功能 × 本体词。「在检出内」指本环境能否解析到该类的定义。
:name: tbl-r07-ontology
:align: left

| 功能 | spo 词（fyo 引用、未自铸） | fyo 自铸 | 在检出内 | 缺口 |
| :--- | :--- | :--- | :---: | :--- |
| 编辑 | `ParameterDefinition` / `ParameterSetting` / `PortDefinition` / `Code.declares_*`；`Control`（呈现骨架） | `ScenarioSpecification` 三属性 | ✗ | 控制词表（值域 / 缺省 / 档位）无落点：`FYO-ADR-07` D-3 明令不为实现的控件名铸类 |
| 可视化 | `PresentationSpecification` / `Panel` / `View` / `Series`（视图种类封闭五值） | `PoloidalSectionView` 四图层 | ✗ | `fylite:layout` / `visible` / `domain`、`stem` / `table` / `baseline` 未进 `context.jsonld`（`-18` G-3 / G-10） |
| 执行 | `ComputationPlan` / `ComputationalProcess` / `has_step` / `has_occurrent_part` | `ApplicationTask` 五类、`ScenarioLoop` | ✗ | 无 `Step` 类（步 = `SolverInvocation` 挂 `has_occurrent_part`）；无批式执行器（fyo `G-B5`） |
| 状态追踪 | `ComputationRecord.run_state`（`FYL-REPORT-06` §9.3 给七值） | 无 | ✗ | fyo 内**无任何**运行状态枚举；`run_state` 只在 CQ 套件被断言 |
| 导入 | `DataSourceEndpoint` / `PortBinding` / `bound_endpoint` / `Concretization.format_iri` | `FusionSerializationFormat` | ✗ | 多文档组合语法（`@included` / `$link`）划归 SpData（`FYO-ADR-07` OI-4） |
| 导出 | `Concretization`（`storage_uri` · `checksum` · `byte_size` · `format_iri`） | 同上 | ✗ | 输出**表示**的请求（画哪张图、哪种网格）无落点（OI-1） |
| 断点恢复 | `Checkpoint`（`state_content` · `opaque_state` · `resumable_by` · `at_process_boundary`）· `resumes_from` · `produced_checkpoint` | 无 | ✗ | 「停下再续 ≡ 一次跑完」的判据推给下游对拍门，fyo 不预设容差（D-5） |
| 溯源 | `ProvenanceMixin` / `generated_by_process` / `executed_code` / `ExecutionEnvironment` / `UncertaintyStatement` | `IdsCode` ⊑ `Code`；DD 原生 `IdsProvenance*`（字符串型，不与 spo 相连） | ✗ | **无施动者类**（OI-3，上游 BLOCKED）；`prov:` 前缀声明了、只在散文里用过一次；`UncertaintyStatement` 无 fyo 槽指向（fydata G-10 · 本仓 `TODO.md` O-2） |
:::

〔判读〕描述面的完备性成立**于 spo + fyo 之和**；单看 fyo，八项里没有一项能独立描述。这不是缺陷——
`FYO-ADR-07` 的分层就是这么定的——但它有一个工程后果：**fyo 的 CQ 套件与 fylite 的语料闸在没有
`../spo` 的机器上解析不到自己引用的类**，而本环境正是这样一台机器（C-13）。

〔已确立〕`fylite:` 前缀在描述面的含义（`FYO-REPORT-05` §O-4）：内核对「DD 无此名」的显式声明，
235 条量槽中 108 条走 `gap` 机制；四张内核自有表（`discharge` 48 · `transport_inputs` 10 · `uq` 5 ·
`pulse` 4）是对 `fyo:` 命名空间的提案，待 `FYO-ADR-*`（本仓 `TODO.md` O-1）。同一个前缀在数据仓
另有两种用法（C-14）。

(fylite-report-07-functions)=
# 4. 逐项评估 (Function by function)

每小节四段：设计裁定 → 四宿主落地表 → 闸 → 判。宿主缩写：**CLI** = `fy`；**PY** = Python 库；
**WEB** = 浏览器页面；**AI** = MCP / JSON-RPC 工具面（`engine/serve.py`）。符号：✓ 落地 · ◐ 部分 · ✗ 无 · ⊘ 有代码但未接入。

(fylite-report-07-edit)=
## 4.1 编辑 (Edit)

〔设计〕`-16` H-1「宿主只写计划、只读记录」；`-17` E-11 / E-13 两段解析与六层合成
（模板 → 装置 → 预设 → `--plan` → 命令行 → 端口绑定），每个参数带 `fylite:from`；`-18` U-1 / U-2
「输入页由控制词表投影」，U-15 / U-23「试改写回计划的一个版本」。

:::{table} 编辑：四宿主。
:name: tbl-r07-edit
:align: left

| 宿主 | 落地 | 证据 | 判 |
| :--- | :--- | :--- | :---: |
| CLI | `fy run <线> <场景> k=v … --preset --plan --bind --input --code --dry-run`；参数按模板校验、固定选项名优先；`--dry-run` 一个字节不写 | `_cli.json` `run`；`cli/run.rs::build` / `stamp`；`-17` 表 as-built | ✓ |
| PY | `cases.plan()` / `settings()` 读；**无编辑 API**，改计划 = 改 dict；`cases.run(case_id, d, predict=)` | `engine/cases.py:944, 998` | ◐ |
| WEB | `model` 页 141 个控件由 `vocab-model.js` 生成（`form.js`）；其余三页手写；`edit.js` 拖把手写 `sets_parameter`、路点写带 `fylite:edited_from` 的文档 | `-18` §十三 U0 各行；`app/assets/{form,edit,vocab-model}.js` | ◐ |
| AI | `fylite_run` 工具收 `arguments` 字典；工具 schema 自清单派生（`manifest.llm_tools`） | `engine/serve.py:590, 385`；`engine/manifest.py:396` | ✓ |
:::

〔闸〕`test_scenario_templates.py`（模板由语料生成、词表 ⊇ 语料用名、开关只展开已知布尔）；
`validate-form.mjs`（词表 ↔ 控件双向）；`validate-edit.mjs`（C 档不可达）。

〔判〕**◐。** 三个宿主各有一份「参数是什么」的来源：CLI 读模板的 `fylite:vocabulary`（**只有类型**：
`float` / `int` / `bool` / `str`，无值域 / 缺省 / 枚举）；页面读 `vocab-model.js`（`iri` / `tier` / `group`
全为 `[TBD]`）；内核读 `BLOCKS`（有单位无值域）。`-18` G-1「控制词表今天不存在」与 `-16` K-2 增列仍开。
用户学到参数边界的方式是**被拒绝**（`fy run model transport chi_zero=0.4` → 按名拒并指向 `fy list scenarios`），
这在纪律上正确，在易用性上是代价（U-8）。另：计划文件形上 `prescribes_code` 不在模板目录时开放参数
**不校验透传**（`-17` G-11），由内核按名兜底。

(fylite-report-07-visualise)=
## 4.2 可视化 (Visualise)

〔设计〕`FYL-REPORT-06` §13 呈现规格 = 指令性 ICE，只声明不计算；P1..P4 四规则；`-18` U-12「两端推出同一份规格」、
U-14 工作台布局写回。

:::{table} 可视化：四宿主。
:name: tbl-r07-vis
:align: left

| 宿主 | 落地 | 证据 | 判 |
| :--- | :--- | :--- | :---: |
| CLI | **无 `report` 动词**（随 Python 命令行一并撤除）；`--page` 选项集不含 `report` 页 | `_cli.json` `hosts.app.params.page.choices`；`docs/reference/case-report.md` 末段 | ✗ |
| PY | `engine.casereport`：计划 + 记录 → 规格 → MyST + 手写 SVG（stdlib，五种视图）；`engine.report`（运行目录报告）；`plot.py` 三个 matplotlib 入口 | `casereport.py:237, 345, 434, 716`；`report.py:161`；`plot.py:72, 349, 483` | ✓ |
| WEB | `fig.js` 五种视图从规格画；`workbench.js` 12 列栅格布局写 `fylite:layout`；`report.html` 读同一份记录 | `-18` §十三 U0 第二、四步 | ✓ |
| AI | `fylite_plot` 工具 | `serve.py:686` | ✓ |
:::

〔闸〕`validate-report.mjs`（页面 `derive()` ≡ Python `derive_presentation()` 逐字段；2026-09-04 起真跑通，
`-18` G-13 关）；`validate-fig.mjs`；`validate-workbench.mjs`；`test_casereport.py` / `test_report.py`。

〔判〕**✓（数据视图）/ ◐（词表）。** 两端同一份规格有闸在守。缺的是词：`fylite:layout` / `visible` /
`domain`（G-3）与 `stem` / `table` / `baseline`（G-10）未进 `docs/examples/context.jsonld`，Python 端对
`stem` 无 SVG、对 `baseline` 无成对渲染——U-21 / U-22 今天只在浏览器端可落。CLI 没有可视化动词是
2026-09-04 裁定的直接后果，不是遗漏，但 `docs/reference/case-report.md` 仍写着 `--from` 与 `fy case run`（C-3）。

(fylite-report-07-execute)=
## 4.3 执行 (Execute)

〔设计〕`-16` K-1 一扇文档门（树进树出）、K-4 找不到就拒；`-17` E-19 记录目录自足、E-20 退出码 0 / 1 / 2 与
`refusal.stage` 四阶段；`FR-HOST-002` 批式档**可分步、可中断**；`-18` U-8 步预算是计划字段、U-9 取消是切预算。

:::{table} 执行：四宿主。
:name: tbl-r07-exec
:align: left

| 宿主 | 单步 / 整案 | 批式档（分步 · 中断） | 证据 | 判 |
| :--- | :---: | :---: | :--- | :---: |
| CLI | ✓ `fy run`；退出码三档；`refusal.stage` ∈ compose · device · measurements · kernel；记录目录 `plan.jsonld` + `record.jsonld` + `<ids>.fyo.jsonld` | ✗ 无 `--step` / `--resume` / 取消；`signal()` 只用于 SIGPIPE，无 SIGINT 处理，内核调用无超时 | `cli/run.rs:53, 1015, 1040, 1419`；`_cli.json` | ◐ |
| PY | ✓ `cases.run()`；`ExecutionBody` 六相协议（cold → ready → poisoned，`cancel_token`，`restart()`） | ◐ 进程级取消有，**步级**无；`_turbulent_march` / `_coupled_march` 以具名槽块续 | `engine/body.py:1263`；`scenario/model/__init__.py:847, 1015` | ◐ |
| WEB | ✓ 四页各自 worker | ✓ `run.js`：预算分片（目标 200 ms / 次）、进度由调用方数、`cancel()` 切预算、`hard` 另名——**但无页面加载它**（只被 `fylite.js` 注释与闸子引用；`evolve` 页走 `scenario-model.js` 自己的续跑路） | `app/assets/run.js:1-30, 157`；`grep -l run.js app/pages/*.html` = 空 | ⊘ |
| AI | ✓ `fylite_run` 等五工具 | ✗ 无 `submit` / `status` / `stream` / `cancel`（`FYL-REPORT-06` B-8 未落） | `serve.py:385-711` | ◐ |
:::

〔闸〕`test_case_runs.py`（语料每条可跑或按名拒）、`test_run_records.py`、`test_engine_*`、`test_serve.py` /
`test_mcp.py`；中间层 `tests/json_door.rs` / `acceptance_iter15ma.rs`；`validate-checkpoint.mjs`（假步进器）。

〔实测〕内核门今天认的 code：`-20` 家底「模板 22 · 门认 6」；语料九个 code 里六条走到
`refusal.stage: kernel`（`-17` §十五）。这是分期（P2），不是缺陷；但「33 个 code 里验过几个」
今天**无从算**（`-20` §二），可用性矩阵 22 × 13 = 286 格从未算过（`-20` G-5）。

〔判〕**单步 / 整案 4/4，批式档 1/4 且未接线。** `FR-HOST-002` 的「可分步可中断」在 CLI 与 AI 面上
不成立；Python 的取消是进程级；浏览器的实现是完整的但停在 U0「不动内核」阶段，`run.js` / `checkpoint.js`
没有被任何页面 `<script>` 引用。`-16` 撤回回调（〔回调：撤回〕）之后，进度只能由调用方数——这条裁定
在 `run.js` 里落实了，在另外三个宿主上尚无对应物。

(fylite-report-07-state)=
## 4.4 状态追踪 (State tracking)

〔设计〕`FYL-REPORT-06` §9.3：`RunState` = submitted → validating → (rejected | running) → (succeeded | failed | cancelled)，
「运行状态是记录的属性」；`-20` M-1..M-13 三张表（面 · 覆盖 · 可用性）+ 版本轴；`-18` U-9 两种停止两个词。

:::{table} 状态词表：谁产、谁读。
:name: tbl-r07-state
:align: left

| 词表 | 取值 | 产者 | 读者 |
| :--- | :--- | :--- | :--- |
| 记录 `run_state`（Rust） | `succeeded` · `rejected` | `case.rs:1007` | `casereport.py:58` 以 **7 值**映射（`running` / `submitted` / `validating` / `cancelled` / `failed` 无产者） |
| 验收 `acceptance` | `pass` · `conditional` · `fail` · `unevaluated` | `provenance.py:42-45, 206` | `report.py`；Rust **无对应** |
| 重放处置 | `replayed` · `refused`；`same` · `same (run ids)` · `differs` | `replay.py:52, 177` | `test_replay.py` |
| 执行处置 | `RECLAIM` · `RETAIN` · `DELIVER` | `body.py` | 进程内 |
| 浏览器运行 | `done` · `cancelled` · `hard` | `run.js` | 页面（未接线） |
| 数据仓 | 采集状态八值 · `review.status` 二值 · `dev:status` 五值 · `machine.yaml` 规则状态 | fydoc / fydata 人工 | 无工具校验 |
:::

〔落地〕Python 侧另有账本（`ledger.py`：`workflow-ir/2.0` instance，边由句柄推出）、依赖图
`Staleness`（七阶段）、写一次快照 `iter-NNN`（`versioning.py:131`）、别名（`alias.py`）。浏览器侧只有
断点仓的索引行；CLI 与 AI 面无中间态。数据仓无任何运行状态词。

〔判〕**◐。** 终态可追（记录里的 `run_state` + `refusal.stage`），**中间态不存在**：没有任何宿主产出
`running` / `cancelled`，B-8 的四方法未落，`-20` 的三张表未生成。同一个词 `run_state` 在产者（2 值）、
消费者（7 值）、设计（7 值状态机）三处不一致（C-5）。

(fylite-report-07-import)=
## 4.5 导入 (Import)

〔设计〕`-14` L-1..L-12 数据半边；`-16` K-8 装置整份文档进内核；`-17` E-14 / E-15 装置两条路、测量三级；
`-18` U-5..U-7 源栈；`FYL-REPORT-06` B-3 端点取回与回退。

:::{table} 导入：格式 × 宿主。
:name: tbl-r07-import
:align: left

| 来源 | CLI / PY（中间层 `.so`） | WEB（`fylite_web.wasm` + JS） | 判 |
| :--- | :---: | :---: | :---: |
| g-file / a-file | ✓ / ✓（a 只读） | ✓（经 wasm，`geqdsk.js` 第三份实现已撤） | ✓ |
| JSON-LD（fyo 布局） | ✓ | ✓ | ✓ |
| HDF5 / netCDF（fyo · IMAS 两布局） | ✓（imas-python 往返验证） | ◐ `h5wasm` 读 `.h5` 为源栈一层 | ✓ |
| MDSplus（mdsip） | ✓ 只读、由构造保证 | ✗ 浏览器无裸 TCP；桌面经 `/api/*` | ◐ |
| fydata A-Box YAML | ✓ | ✓（`fylite_facts.wasm` 内嵌 13 台） | ✓ |
| 多源装配（`$source` / `$link` / `merge`） | ✓ `fy data assemble` | ✓ `sources.js` 产 `fylite:Assembly/1`，页面自己不合并 | ✓ |
| GACODE `input.gacode` | PY 只读（无 Rust 读者） | ✗ | ◐ |
:::

〔数据仓一侧〕fydata 五个转换器 + 两道形状闸（S1..S10）；fydoc 三条互不混读的溯源线
（原件浇铸 · 文献浇铸 · 自持）+ 设计方运行件的**门控导入**（源 sha256 须等于 `data.checksums`、
定义自证、与本书数字化图交叉核对，任一不过即拒绝产出）。

〔判〕**✓。** 八项里最完备的一项：类型看内容不看扩展名、七种格式一棵树、IMAS 兼容是量出来的。
两处缺口：装配后的文档**不记逐叶子出处**（`-18` G-14：只有 `fylite:assembly.merged`，没有「这片叶子来自哪一源」）；
mdsplus 端点的优先序回退未做（B-3 半开）。数据仓侧 `lit2abox.py` **不幂等**（重跑抹掉后生成的
`dev:redistribution` 块）是一处已登记的导入风险。

(fylite-report-07-export)=
## 4.6 导出 (Export)

〔设计〕`FYL-REPORT-06` B-6 输出具体化（`format_iri` 驱动写手，每份带校验和，同一平衡写三种读回等价）；
`-18` U-18 只有一种交换单元——文档集。

:::{table} 导出：四宿主。
:name: tbl-r07-export
:align: left

| 宿主 | 落地 | 证据 | 判 |
| :--- | :--- | :--- | :---: |
| CLI | `--format jsonld \| hdf5 \| netcdf \| imas-hdf5`（后者写一个 IMAS 数据入口 `imas/master.h5` + 每 IDS 一文件）；每份产出在记录里有 `storage_uri` + `sha256` + `byte_size` | `cli/run.rs:1270-1352`；`docs/guide/cli.md` §记录目录 | ✓ |
| PY | `fyo.write()` / `as_geqdsk()`；`io.fydoc.Bundle.write(layout="imas")` | `fyo.py:401, 1058`；`io/fydoc.py:229` | ✓ |
| WEB | `bundle.js` 文档集 zip（`plan` · `inputs/*` · `record` · `presentation` · `environment.json` · 可选 `report.md` + `figures/`），读回按 `@type` 不问文件名 | `-18` U1 提前落地行 | ✓ |
| AI | 结果以摘要 + `fylite://<run>/<port>` 句柄交付，大数组不进对话 | `serve.py:81, 499` | ✓ |
:::

〔发布闸（fydoc）〕`tools/check_release.py` **按内容寻址**（MyST 会把链接到的文件改名为内容哈希搬进产物），
默认 `internal`，`public` 逐条要 DOI / 许可 / 核验方式；自陈的盲区：`corpus/gacode/` 里以 TGLF / NEO
变量名重表达的同一批受限剖面**闸子抓不到**，靠「不入 toc、不超链」守。

〔判〕**✓（宿主）/ ◐（闸）。** B-6 的「同一平衡三种具体化读回等价」有 `V-15`（g-file 往返）与中间层
`device_to_imas.rs`，但**没有一道闸同时写三种再互比**。fydoc 的发布闸本身工作，其配置**失效**：
`cases/RELEASE.yaml` 的 `public:` 前缀仍是 2026-09-04 改名前的短名（`gene` · `itpa-tc33`），目录不存在，
两条公开条目永不生效（C-15）；`internal:` 键被脚本读取而三份文件里都不存在。失效方向是安全的
（一切留在 internal），但声明的公开发布没有发生。

(fylite-report-07-checkpoint)=
## 4.7 断点恢复 (Checkpoint and resume)

〔设计〕这是设计最完整的一项：`-16` S-1 内核无状态且不可交易、S-2 状态是一棵声明过的 `fylite:state` 子树、
S-3 每个步界能停并交出完整状态、S-4 状态进记录、S-5 五件事三层分、S-6 状态带内核身份；`-18` U-8..U-11、
U-19「同一份文档集在别处继续」；`FYL-REPORT-06` §7（`spo:Checkpoint` 对应表）与 B-5；`FR-KERNEL-004`。

〔已确立·落地〕四层各有一段，**互不相接**：

:::{table} 断点恢复：各层现状。
:name: tbl-r07-checkpoint
:align: left

| 层 | 有什么 | 证据 | 与设计的差 |
| :--- | :--- | :--- | :--- |
| 内核状态机 | `TwoTemperatureMarch` / `FluxMatch` / `CoreMarch` 各有 `save` / `load`，状态在调用方缓冲区；往返闸在 `cargo test` | `transport.rs:1557, 2022, 2703` | 三台状态机的十二个 C 导出**全部** `#[cfg(feature = "oracle")]`（ABI 152：核心导出 54 → 42），**发行的 `.so` / `.wasm` 上没有可断点的步进器** |
| 内核文档门 | `code/evolve` 的 `resume = 1` + 二十个成对槽（`psi_prev` ↔ `psi_prev_out` …）；`lag_reset = 1` 表示「状态被重映射，首步无欧姆项」；缺绑定按 `ERR_MISSING` 拒 | `fyo.rs:847, 1147, 1229`；`case.rs:365, 672-701` | 状态是**逐个具名的槽**，不是 `fylite:state` 子树（SDD DE-LOG-12 自记「兑现了一半」；`-16` G-8 开） |
| 中间层 / CLI | **无** `--resume`；`grep resume rust/fylite_runtime/src` 只命中词表行 | `_cli.json`；`fyo_interface.rs:373, 513` | `-18` G-4 开；U-19 的「桌面 `fy run … --resume record.jsonld`」是提案 |
| Python | **无** `resume=`；`replay.py` 是**重放**（从计划重跑、逐件比哈希）不是续跑；块续只在 `_turbulent_march` / `_coupled_march` 内部以具名槽做 | `cases.py:998`；`replay.py:12-42, 259` | 同上；`test_evolve_entry.py:782-830` 有 `evolve_heat` 的块等价断言（真内核） |
| 浏览器 | `checkpoint.js`（IndexedDB，断点 = 记录本身，带内核身份，异核按名拒、显式放行写进 `environment`）+ `run.js`（分片 · 取消 · 每 N 步存） | `app/assets/checkpoint.js:1-24, 95`；`run.js` | **无页面加载**这两个模块；`fylite:state` 只由 `scenario-analysis.js:4272` 产出，内核与中间层从不产出；`fy run` 写的记录没有 `fylite:state` 也没有 `environment` 键，按 `checkpoint.js:95` **被拒**（C-6 · C-7） |
| 闸 | `validate-checkpoint.mjs`：N 步 ≡ k + resume(N−k)、存取逐字节 | 文件抬头 | 步进器是**确定性假件**——「with a real kernel that is a bit-for-bit comparison … here the stepper is a deterministic fake」；真内核上的等价只对 `evolve_heat` 的块协议在 Python 侧断过 |
:::

〔判读·两种「续跑」〕同一个词今天指两件事：(i) **块续**（`resume = 1`，携 `psi_prev` 等滞后量，
`FYL-REPORT-06` §7 要求 N 块 k 步逐位等于一次 N×k 步，`test_evolve_entry.py` 断言之）；(ii) **从一份态重新推进**
（页面的 `msg.resume` + `tStart`，`validate-worker-evolve-resume.mjs` 抬头自陈「滞后的通量与电导、交换上限、
台基、控制器都从头来」，内核以 `lag_reset` 标之）。两者对「停下再续 ≡ 一次跑完」的答案不同，而
`-18` U-10 / §十三 的闸判据只写了前一种。这不是 bug，是**一个词两个语义未被命名**（C-8）。

〔判〕**1/4，且那一个未接线。** 断点恢复是八项中设计最完整、落地最薄的一项。`-16` S-1 / S-3 的
前提（内核无状态、每步界能停）**成立**——问题全在 S-2（子树）与 S-5 ③④（携带与持久化）尚未
跨宿主落地。

(fylite-report-07-provenance)=
## 4.8 溯源 (Provenance)

〔设计〕`FYL-REPORT-06` §8（`RunManifest` 逐字段到 `spo:ComputationRecord` 的映射，`fylite:RunManifest` 退役；
重放 = 新运行同一计划同一具体化；`whence` 改查端口绑定）与 B-4；`-16` K-7 环境指纹、S-6；`-20` M-5
「每个数带内核身份」、M-13「换版不继承结论」；`FR-DATA-003`。

:::{table} 溯源：五种记录形。
:name: tbl-r07-prov
:align: left

| 形 | 谁写 | 携带 | 不携带 |
| :--- | :--- | :--- | :--- |
| `spo:ComputationRecord`（Rust） | `case.rs:961` | 计划的 `Concretization{storage_uri, sha256, byte_size}`；`executed_code{version: "abi N", concretized_as[].checksum}`；每个参数的 `fylite:from`；输入 / 输出端口绑定各带 sha256；`run_state`；`comment[]` | **无 `environment` 键**；无验收；无决策；无调用迹 |
| `RunManifest`（Python） | `provenance.py:295, 352` | `code{rev, dirty}`；`environment{python, platform, host, numpy, libraries.libfylite.sha256, variables, threads}`；`acceptance` 四值；`decisions`；`trace`；输入**摘要** | 无 `storage_uri`；无计划校验和；类型仍是 `fylite:RunManifest` |
| 结果内 `provenance` 字典 | `scenario/__init__.py` | `tool` · `lines` · `fr` · `scope` · `caveat` · `kernel_abi` | 不进记录文件 |
| 会话账本 `ledger.jsonld` | `ledger.py:104` | `workflow-ir/2.0` instance，`provenance_class: sandbox_local`，边由句柄推出 | — |
| 数据仓 | `case.yaml` `provenance{kind, citation, upstream}` + `environment{host, recorded}` + `review{…}`；A-Box `dev:AboxProvenance{dev:result, …}`；fydata `prov:wasGeneratedBy` **配方**；`corpus/material/process/provenance.yaml` 第四种 schema | 五种 `provenance.kind`；六 / 七值 `dev:result` | 与 spo 记录**零交集** |
:::

〔已确立·反查〕`engine/whence.py` 按内容哈希反查（目录只是提示，哈希不匹配不认领），
是 `FYL-REPORT-06` §8.3 要的那个查询——但它查的是 `manifest.json` 的 `artifacts[]`，不是记录的端口绑定。

〔已确立·内核身份〕本环境构建产出 `rust/kernel-lib/kernel-static.json`（`kernel_version` · `abi` · `built` ·
`sha256` · `toolchain`）；Rust 记录把它写进 `executed_code.concretized_as[0].checksum`；浏览器断点仓却读
`record.environment.kernel_sha256`（`checkpoint.js:69-72` · `bundle.js:142, 156`）——**同一件事两个键**（C-6）。
公开登记册 25 条记录**多半不带内核身份**（`-20` G-9，`V-14` 只记参考侧版本），`covers` 边未回填（G-1）。

〔判〕**◐。** 一次 `fy run` 的溯源在 Rust 记录里成立（计划 · 代码 · 参数来源 · 端口 · 校验和五者齐）。
跨层看，**五种形状互不归一**：B-4 的 Python 半边未做，浏览器与 Rust 对身份键各说各话，登记册与
数据仓各有自己的 schema，sha256 与 md5 并存（C-18）。描述面上「谁执行的」无类（OI-3），
所以任何一种形都没有施动者槽——`ledger.py` 的 `OWNER = "did:spharness:fylite/maintainers"` 是唯一写死的施动者。

(fylite-report-07-consistency)=
# 5. 自洽性缺口登记 (Self-consistency register C-1..C-27)

每条：矛盾的两侧 · 证据 · 归属 · 关闭判据。「归属」按 `TODO.md` 的规矩是硬约束。

:::{table} 文档 ↔ 代码（宿主收敛之后的滞后）。
:name: tbl-r07-c-docs
:align: left

| # | 两侧 | 证据 | 归属 | 关闭判据 |
| :--- | :--- | :--- | :--- | :--- |
| C-1 | `FYL-CONOPS-00` v1.0 §包络写宿主为「`fylite` 控制台脚本 + `fylite` 可执行文件承载 `app` / `data` / `case`」；README 与 `_cli.json` 是**唯一**可执行文件 `fy`，命令词 `app` / `data` / `run` / `list`，`case` 已退役 | `FYL-CONOPS-00.md` 基准口径段；`README.md` §Quick start；`_cli.json` `hosts.rust` | fylite | CONOPS 该段改写并升版；`test_cli_docs_match_the_artifact.py` 扩到设计集 |
| C-2 | `docs/guide/python.md` §命令行在别处写 `fy` 承载 `app` / `data` / `case` 三条；同页 §与浏览器互通以 `fylite:AppSession/1` 为交换单元，而 `-18` U-18 已裁定该类型退役 | `python.md:45-64`；`-18` U-18；`session.js:22` / `appsession.py:34` 仍活 | fylite | 页面改口；`AppSession/1` 要么正式退役（删代码）要么撤回 U-18 |
| C-3 | `docs/reference/case-report.md` 与 `casereport.py` 抬头写 `fy case run` / `fylite case json` / `--from`——`case` 在 `_cli.json` `retired` 表里按名拒绝，`--from` 不是 `fy run` 的旗标；同页末段又说 2026-09-04 起是库调用 | `case-report.md` 首段与末段；`casereport.py:5-8` | fylite | 页面与 docstring 改口；闸 `test_cli_docs_match_the_artifact` 覆盖 `reference/` |
| C-4 | `checkpoint.js:6-7` 称断点「就是 `fy run --resume` 读回的那份」；`_cli.json` 无 `--resume`（`-18` G-4 自记为提案） | `checkpoint.js`；`_cli.json` | fylite | `--resume` 落地，或注释改为「提案」 |
| C-11 | `_cli.json` `--page` 取值 `home / pulse_design / model / analysis / data`，且注记「有闸断言页面只读这些名字」；`app/pages/report.html` 在盘上、文档指引直接打开 | `_cli.json`；`app/pages/` | fylite | `report` 入选项集，或文档说明它不经 `fy app` 打开 |
:::

:::{table} 代码 ↔ 代码（Rust / Python / JS 三端各一份）。
:name: tbl-r07-c-code
:align: left

| # | 两侧 | 证据 | 归属 | 关闭判据 |
| :--- | :--- | :--- | :--- | :--- |
| C-5 | `run_state` 产者 2 值（`case.rs:1007`）；消费者 7 值（`casereport.py:58`）；设计 7 值状态机（`FYL-REPORT-06` §9.3） | 同左 | fylite | 一份枚举一处定义（spo `RunState`），产者覆盖 `cancelled` / `failed` 至少各一 |
| C-6 | 内核身份：Rust 记录写 `executed_code.concretized_as[].checksum`；浏览器读 `record.environment.kernel_sha256` / `abi` / `app_version`；Rust 记录**无** `environment` 键 | `case.rs:989-1000`；`checkpoint.js:69-72`；`bundle.js:142, 156` | fylite | `validate-bundle.mjs` 导入一份 `fy run` 写的 `record.jsonld` 并通过身份检查 |
| C-7 | `fylite:state` 在 `fyo.rs` / `_fyo_interface.py` / `fyo_interface.rs` 中**不存在**；只有 `scenario-analysis.js:4272` 产出；SDD DE-LOG-12 标〔目标态〕 | `grep -rn "fylite:state"` | kernel · fylite | `fylite:state` 进 `fyo.rs` 某张表（`-16` G-8 定形）；`_fyo_interface.py` 生成物含之 |
| C-8 | 「续跑」两义：块续（逐位等价，`test_evolve_entry.py:827-830`）与从态重推（滞后量重置，`validate-worker-evolve-resume.mjs` 抬头、`lag_reset`）；`-18` §十三 断点闸判据只写前者 | 同左 | fylite · kernel | 两种语义各有名（如 `continue` / `restart_from`），闸子分别断言 |
| C-9 | Rust `spo:ComputationRecord` 与 Python `RunManifest` 字段零交集；B-4 自记「Python 侧 `RunManifest` 未改」 | {numref}`tbl-r07-prov` | fylite | `RunManifest` 退役，`deliver()` 写 `spo:ComputationRecord`；`whence` 查端口绑定 |
| C-19 | 声明面的计数无单一来源：`CASE_CODES` 35（`fyo.rs:869`）· `-20` 家底「code 33」· 模板 22 · 门认 6；无机器可读的进度表 | 同左 | kernel · fylite | `-20` M-1..M-4 三张表生成并入 `docs/benchmark/` |
| C-20 | `fyo.rs:869` `code/rf_ray` 注记「吸收与伴随 ECCD **未实现**，请求即拒」；内核 `changelog.md` 2026-09-11 记 rfray ECCD 与束宽已落 | 同左 | kernel | 门注记与 changelog 同批更新；`fy list kernel` 的答案与 changelog 一致 |
| C-22 | 内核 C ABI 有版本号（`fylite_rs_abi_version`，`fyo.rs:37-45` 要求装载方每次核对）；中间层的 35 个 `fylite_runtime_*` 导出**无版本符号**，只有 `runtime-version.js` | `fylite_runtime/src/c_api.rs` | fylite | 增 `fylite_runtime_abi_version`，Python 装载器核对 |
:::

:::{table} 本体 ↔ 仓 ↔ 仓。
:name: tbl-r07-c-repos
:align: left

| # | 两侧 | 证据 | 归属 | 关闭判据 |
| :--- | :--- | :--- | :--- | :--- |
| C-13 | fyo 的运行 / 溯源 T-Box 全部引用 spo；`spo` 不在本环境，`catalog.yaml:44-45` 委托 `../spo`；CQ-SCE-9 等断言在无同级检出时不可解析 | fyo `catalog.yaml`；`.context/PROJECT.md` §2.1 不变式 6 | fyo | 要么 vendor 一份钉版本的 spo 到 `schema/tests/`（同 fylite `_spec/` 先例），要么 CQ 门在缺 spo 时按名跳过而非红 |
| C-14 | `fylite:` 前缀三种绑定：内核文档路径的「DD 无此名」段（`FYO-REPORT-05`）；fydata JSON-LD `"fylite": "urn:fylite:"`；fydoc 散文与工具里的仓定位符 `fylite:python/…`（未声明为命名空间） | `slice_04000ms.fyo.jsonld:5`；`abox2jsonld.py:46-55`；`point_chords.py:14` | fyo · fydata · fydoc | 一条裁定：`fylite:` 的 IRI 与用途；fydoc 的仓定位符改成 CLAUDE.md 规定的仓限定行内代码形 |
| C-24 | 内核声明面对 DD：6 条裸路径的叶不在 DD、16 条首段不是任何 IDS、`vacuum_toroidal_field/b0` 秩不符、12 处单位写法不同 | `TODO.md` K-1..K-4；`FYO-REPORT-05` O-1 / O-2 / O-5 / O-8 | kernel · fyo | `TODO.md` K-* 各自关闭判据 |
| C-25 | fydata `README.md` §5 仍指 `fydoc/oracle`；该树同日改名 `cases/` | fydata `README.md:207`；fydoc `cases/README.md` §1 | fydata | 改指针 |
:::

:::{table} 数据仓：闸按字面而非按意图实现。
:name: tbl-r07-c-data
:align: left

| # | 两侧 | 证据 | 归属 | 关闭判据 |
| :--- | :--- | :--- | :--- | :--- |
| C-15 | `cases/RELEASE.yaml` `public:` 前缀为改名前短名（`gene` · `itpa-tc33`），目录不存在；`internal:` 键被 `check_release.py:113` 读取而三份 `RELEASE.yaml` 均只有 `internal_notes:` | 同左 | fydoc | 前缀改为 `FYDOC-CASE-<NN>-<short>`；`check_release.py` 对匹配不到任何文件的前缀**报错**而非静默 |
| C-16 | `cases/README.md` 说 `[TBD]` 视为未满足；`check_cases.py:51` 只匹配**整字段等于** `[TBD]`，`host: '[TBD] —— …'` 与 `recorded: …[TBD]` 通过 | `FYDOC-CASE-13-teq/case.yaml:15`；`FYDOC-CASE-05-gacode/case.yaml:17` | fydoc | 子串匹配；两处回红 |
| C-17 | `dev:result` 装置书 6 值（`abox2jsonld.py:104`），实验层 7 值（多 `revised`，`facts/experiment/INDEX.md`）；实验层自陈七值无一适用于自洽五面态（E-4） | 同左 | fydoc | 一份词表；`revised` 入或不入有裁定 |
| C-18 | 校验和算法：`case.yaml` / 实验层 / `process/provenance.yaml` 用 sha256；`SOURCES.yaml` 与 `dev:md5` 用 md5 | `check_abox_corpus.py:12-17` | fydoc | 一种算法，或文档写明为何两种 |
| C-21 | `review.status` 只见 `pending` / `not-required`，无「已审」值，无校验；`check_cases.py` 今天 **FAIL：21 组 28 处，16 组待补 reviewer / contact**，红是稳态 | 2026-09-12 实测 | fydoc | 词表三值以上含终态；红的原因是人未署名而非闸子无终态 |
| C-23 | `data.payload` 是固定键（README §5），21 份 `case.yaml` 中 13 份未写，落入「在仓」分支被当作字节在盘上检查 | `check_cases.py:124` | fydoc | 键缺失即拒 |
:::

:::{table} 文档 ↔ 实测（本环境）。
:name: tbl-r07-c-measured
:align: left

| # | 两侧 | 证据 | 归属 | 关闭判据 |
| :--- | :--- | :--- | :--- | :--- |
| C-10 | README「缺内核的检出照常收集，需要内核的按名跳过、不失败」；实测**有内核、缺数据库**（`libfylite_runtime.so`）时 73 失败 / 10 错误，全部 `KernelError: the data library is not built` | {ref}`fylite-report-07-appendix-measured` | fylite | 数据库缺席 → `pytest.skip` 按名；或 README 改口「需要两份库」 |
| C-12 | 内核 `rust/build.sh` 把公开仓已提交的生成物 `python/fylite/_flavour.py` 从 `internal` 改写为 `none`（本环境无 facts 语料）；一次构建在别人的仓里留下未提交的差异 | `git diff python/fylite/_flavour.py` | kernel | 构建在 flavour 无法判定时**拒绝**或不写，而不是写一个提交进仓的文件 |
| **C-28** | `FR-KERNEL-002` 要每个 code 自报「要哪些输入、什么单位」；**code 层的参数面无任何声明**——模板的 `fylite:vocabulary` 是语料用过的名字（装配层），内核的 `*_PARAMS` 是原始入口的参数，`code/transport` 两者**交集为零**；六个 code 连 `*_PARAMS` 块都没有 | {ref}`fylite-report-07-landing-r4` 实测 | kernel · fylite | `-16` K-2 落地：`fy list kernel --json` 对每个 `code/<x>` 交出它自己的参数表；`test_scenario_templates.py` 据此对账 |
| **C-29** | `fy list devices` 在无内嵌语料的构建上把错话印在 stderr 上而**退出 0**；本仓的退出码纪律里 0 是「跑完」 | 2026-09-12 实测 | fylite | 答不出东西时的退出码有一条成文的规矩，闸子照它断言 |
| C-26 | `-16` K-7 / `-20` M-5「每份记录带内核身份」；`fy`（静态链接内核）写出的记录 `executed_code.concretized_as[0]` **无 `checksum`**——`run.rs:1168` 以读 `kernel.path` 文件取 sha256，静态链接时无此文件；而同一次构建的 `kernel-static.json` 明明带 `sha256` | {ref}`fylite-report-07-appendix-measured` A.6 | fylite | 静态链接时把 `kernel-static.json` 的 `sha256` 编进 `fy` 并写进记录；闸：`fy run` 的记录 `checksum` 非空 |
| C-27 | 文档示例 `fy run model --preset zerod-iter-15ma`（`cli.md` §跑一次算例）跑出的计划 `id: scenario/transport`（线的缺省模板）而 `prescribes_code: code/zerod`；记录 id 尾缀 `-transport`；`realizes.id` 因此指错场景 | A.6 | fylite | 预设自带场景时以预设的场景为计划 `id`，或文档示例改写 `fy run model zerod --preset …`；闸：`realizes.id` 与 `prescribes_code` 属同一模板 |
:::

(fylite-report-07-usability)=
# 6. 易用性 (Usability)

只记量到的。每条：观察 · 量 · 判。

- **U-1 从干净检出到可运行。** 内核：`FYLITE_PUBLIC=… bash rust/build.sh` 一次成功（cargo 拉取 rayon）。
  中间层：缺省链系统 `libhdf5` / `libnetcdf`（本环境 `apt` 不可达）；按文档走 `--static`，
  编译成功，**制品卫生闸拒绝安装**（`::error:: libfylite_runtime.so 里有 284 条开发机路径`），
  `build.sh` 无文档化的绕行开关。可执行文件 `fy`：`include_bytes!` 三份 `.wasm`，需先装 wasm32 目标、跑内核
  `--wasm-check`、再单独编中间层的 `abi_gfile` wasm（本环境照此走通，A.6）。判：**六步、两处无提示的死路**（HDF5 缺席 → 静态 → 卫生闸；exe → 三份 wasm）。
  〔判读〕`-16` H-6 裁定「桌面算力是本进程的，只静态站点走 wasm」，而 `fy` 仍**内嵌**三份 wasm——
  裁定与 `assets.rs` 的 `include_bytes!` 不一致（登记为 C-26 候选，未计入 25 条，因 H-6 的落地进度本报告未逐行核）。
- **U-2 没有数据库时的体验。** 73 失败 / 10 错误，同一句错误重复 44 次；有库后 2046 通过 / 405 跳过 / 3 失败
  （两条为本报告新增目录触发的文档闸，一条为手工安装未经账本登记——`test_bundled_artifacts.py`
  正确地拒绝了「树里有账本不认识的制品」）。判：失败是**按名**的（每条都说该跑 `rust/build.sh`），但
  README 的承诺没有覆盖它（C-10）。
- **U-3 四个宿主，四套动词。** CLI `run` / `list` / `data` / `app`；Python `cases.run` / `casereport.render` /
  `replay.replay` / `whence.whence`；浏览器四页；MCP `fylite_run` / `open` / `gaps` / `inspect` / `plot`。
  一份工作跨宿主搬动：浏览器 → 浏览器有文档集 zip；`fy run` → 浏览器**被拒**（C-6）；Python ↔ 浏览器经
  已退役的 `AppSession/1`（C-2）。判：U-19「同一份文档集在别处继续」今天成立于一个宿主。
- **U-4 拒绝的质量。** `retired` 表按最长匹配指路（`fy case run` → `fy run <the same plans>`）；退出码三档、
  `refusal.stage` 四阶段；参数错按名并指向 `fy list scenarios`；数据库缺席一句话说该跑什么。判：**强**。
  这是体系里执行得最一致的一条纪律。
- **U-5 文档时效。** 五处滞后（C-1..C-4、C-11），全部围绕 2026-09-04 的宿主收敛。有闸的部分
  （`docs/reference/cli.md` ↔ `_cli.json`）没有滞后；无闸的部分（CONOPS、`guide/python.md`、
  `reference/case-report.md`、JS 注释）滞后。判：闸覆盖到哪，文档准到哪。
- **U-6 发现面。** `fy list` 七条子命令只读；`scenarios` 的 `today` 列量的是**门认不认**，不是**输入齐不齐**
  （`cli.md:76-79` 自陈）；装置 × 场景可用性矩阵从未算过（`-20` G-5）。判：读者要知道「ITER 上能不能跑
  `discharge`」唯一办法是跑一次。
- **U-7 数据仓的闸是稳态红。** `check_cases.py` 28 处不满足（全为 reviewer / contact 未署名）。红的原因
  正确（不虚构评审人），但**没有任何值表示「已审」**（C-21）——即便有人署名，闸也无从转绿。
- **U-8 参数边界靠拒绝学。** 模板词表只有类型；页面词表 `iri` / `tier` / `group` 全 `[TBD]`；三个宿主三份来源
  （§4.1）。
- **U-9 生成件里的手写段没有活路。** `TODO.md` F-2：手写归因活不过下一次 `--write`，且不报错。本报告自身
  就是一份手写文档放在生成物旁边的例子——它不在任何生成器的输出路径上，故不受此影响，但登记册
  `docs/benchmark/` 的散文半边受。

(fylite-report-07-recommendations)=
# 7. 结论与建议 (Conclusions and recommendations R-1..R-9)

〔已确立〕**总判**：fy 体系对计算场景通用功能的**描述**是完备的（借 spo），**设计**是完备的
（每项有裁定与判据），**落地**在导入 / 导出 / 单步执行上齐整，在状态追踪 / 溯源上分裂为多份形，
在断点恢复上只有一个宿主的一个未接线模块。**自洽性**的失分集中在「同一件事在三端各写一份」——
记录形、状态词表、内核身份键、续跑语义、`fylite:` 前缀——而不是在物理或本体上。**易用性**的强项是
按名拒绝，弱项是干净环境的构建路径与四宿主之间的搬动。

建议按依赖序排列；每条带关闭判据，无判据的条目与一句抱怨在使用上没有区别（`FYL-REPORT-00` 规矩）。

| # | 建议 | 落点 | 关闭判据 |
| :--- | :--- | :--- | :--- |
| **R-1** | **断点恢复做成 S-2 / S-4 的样子**：`fylite:state` 子树进 `fyo.rs`（`-16` G-8 定形），`--resume` 入 `_cli.json`、`resume=` 入 `cases.run`，`run.js` / `checkpoint.js` 接入至少一页，`validate-checkpoint.mjs` 的步进器换成真门 | kernel · fylite | 同一份 `record.jsonld` 在 CLI / Python / 浏览器三处续跑，N ≡ k + (N−k) 对 `count` / `flag` 逐位、`real` 带内；C-4 · C-7 · C-8 关 |
| **R-2** | **一种记录形**：Python `RunManifest` 退役为 `spo:ComputationRecord`（B-4 后半）；`environment` 键（或裁定另一个键）由 Rust 记录写出，浏览器身份检查读之 | fylite | `validate-bundle.mjs` 导入 `fy run` 的记录并恢复；`whence` 查端口绑定；C-6 · C-9 关 |
| **R-3** | **一份运行状态词表、有产者**：采 spo `RunState` 七值；`serve` 增 `submit` / `status` / `stream` / `cancel`（B-8）；CLI 至少产 `cancelled`（SIGINT → 停在步界、记录写出） | fylite | 取消一次 200 步演化 → 记录 `cancelled` + 断点，从它续跑与一次跑完逐位相同（B-8 原判据）；C-5 关 |
| **R-4** | **控制词表入 K-2 code 表**（`range` / `default` / `enum` / `tier` / `group`），三宿主读同一份 | kernel · fylite | `validate-form.mjs` 与 `test_scenario_templates.py` 读同一生成物；`vocab-model.js` 无 `[TBD]`；U-8 消 |
| **R-5** | **文档时效清扫 + 闸扩面**：C-1 · C-2 · C-3 · C-11 · C-27 改口；`test_cli_docs_match_the_artifact.py` 覆盖 `design/` 与 `reference/` 中出现的命令词 | fylite | 五处清零；闸对 `fy case` 一类退役词在任何 `.md` 出现即红 |
| **R-6** | **干净环境的构建路径**：数据库缺席时 `pytest.skip` 按名；`--static` 的卫生闸在非发行构建下降为警告或提供 `--allow-dev-paths`（并写进制品身份）；`fy` 的 wasm 内嵌与 H-6 对齐（要么不嵌，要么文档写明前置） | fylite · kernel | 新容器按 README 三条命令得到 0 失败；C-10 · C-12 关 |
| **R-7** | **数据仓的闸按意图实现**：`RELEASE.yaml` 前缀改名并对空匹配报错；`[TBD]` 子串匹配；`review.status` 增终态；`payload` 缺失即拒 | fydoc | C-15 · C-16 · C-21 · C-23 关；`check_release.py` 两条公开条目实际生效 |
| **R-8** | **本体侧三件**：施动者 / 执行者的最小类（`FYO-ADR-*`，或推动上游 OI-3）；`UncertaintyStatement` 的 fyo 槽（O-2）；`fylite:vocabulary` / `switches` / `ports` 的对应类（`-17` G-7）；`fylite:` 前缀一条裁定（C-14）；CQ 门在缺 `../spo` 时按名跳过或 vendor 钉版本（C-13） | fyo · fydata | fyo CQ 套件在无同级 spo 的检出上要么通过要么按名跳过；`TODO.md` O-1 / O-2 关 |
| **R-9** | **`-20` 的三张表落地**（面 · 覆盖 · 可用性 + 版本轴），286 格矩阵生成 | kernel · fylite | `fy list scenarios --device <d>` 的答案与矩阵同源；C-19 关；U-6 消 |

〔工作假设〕R-1 与 R-2 是同一件事的两半：断点是一份记录（U-10），所以记录形不归一，断点就不能跨宿主。
先 R-2 后 R-1 的代价最小。

〔开放猜想〕R-3 的 `cancelled` 在 CLI 上需要内核在步界交出状态——`-16` S-3 已裁定内核必须能，
但今天 `fy run` 一次调用跑完整案，宿主没有介入点；是把 U-8 的「一串门调用」搬到 `run.rs`，
还是给门一个步预算参数，本报告不裁。

(fylite-report-07-boundary)=
# 8. 补充讨论：fylite 与 fytok 的功能界限 (Supplementary: the fylite / fytok boundary)

〔已确立·用户裁定 2026-09-12〕四句话定界：

1. **同一 fyo 描述协议。** 两者对计算场景说同一种话：`fyo:ScenarioSpecification` 进、`spo:ComputationRecord` 出。
2. **fytok 含完整功能**——插件（FyModule）、工作流、开放集成外部物理代码、复杂工作流。
3. **fylite 提供完成核心目标的最小工具集**：自包含、不依赖外部物理模块、保持轻量。
4. 因此 fytok 是**开放的集成者**，fylite 是**封闭的参照实现**；两者不互为子系统。

本节把这四句话落成可判的形：既有裁定里已经写着的（§8.1）、协议必须携带的（§8.2）、
八项功能的归属（§8.3）、两侧的负面清单（§8.4）、对本报告建议的重排（§8.5）、未定项（§8.6）。
★fytok 仓**不在本环境的检出里**；本节对 fytok 一侧的陈述来自 `FYL-CONOPS-00` 的引用、fyo 场景层的
注记与本次裁定，标〔工作假设〕；fytok 侧 as-built 待其自己的文档核对。

(fylite-report-07-boundary-standing)=
## 8.1 既有裁定里已经写着什么 (What is already ruled)

| 已有裁定 | 出处 | 与本次裁定的关系 |
| :--- | :--- | :--- |
| 「FyLite 内核反插件；装置 / 求解器集成的插件机制归 FyTok（FyModule）」 | `FYL-CONOPS-00` 建设原则 3 | 同一句话 |
| 「HPC 尺度码消费其产物、不吞并其本体」 | `FYL-CONOPS-00` 建设原则 6 | fylite 的「不依赖外部物理模块」在原则 6 里已有形：外部码的**产物**可进（作为数据），外部码的**本体**不进 |
| 范围外表：高保真物理归 FyTok 求解器生态；跨节点编排 · 批量作业归 Sp 平台；治理归平台 | `FYL-CONOPS-00` §范围外 | 「复杂工作流」在原表里归 Sp 平台编排层，本次裁定把它归给 fytok——两者不冲突：fytok 是平台上的集成者（〔工作假设〕），fylite 两边都不做 |
| fylite 在分布式工作流里是**一个 worker**：收一份步计划、发一份步记录；DAG 编排、调度、跨节点搬运归平台；「fylite 不知道 DAG 的存在」 | `FYL-REPORT-06` §9.1 / §9.4 | 本次裁定的协议半边，已成文 |
| 异构 = 各步各有 `Code`：Rust 内核入口、est2 归约器、外部工程码的端口运行 `EngineeringPortRun`〔live / stub / archive〕、平台侧代理模型；「异构在本体里只是不同的 `Code` 具体化，没有第二种机制」 | `FYL-REPORT-06` §9.2；fyo `EngineeringPortRun` · `PortExecutionMode`（`fyo-scenario.linkml.yaml:445, 109`，`FYTOK-ADR-126` 契约） | fytok 集成外部物理代码的本体形已经在 fyo 里；fylite 不实现 `EngineeringPortRun`，只可能**消费**它的产物 |
| 「零代码依赖：FyLite 与 FyTok 互不导入；FyLite 以协议成员方式互操作」；`NR-DEP-002` 包内禁 import `sp` / `fy*` | `FYL-CONOPS-00` 摘要；`FYL-SRS-01` | 「自包含」的机器可判形，已有静态检查守门 |
| 「对照基线：与 FyTok 就同一任务、同一输入建立参照对」 | `FYL-CONOPS-00` §系统演进〔开放猜想〕 | 同一协议使参照对可机械构造（同一份计划、两个 `Code`、两份记录逐端口比） |

〔判读〕本次裁定**没有新增**一条与既有文本冲突的规矩；它做的是把散在四份文档里的分工收成一句话，
并把「同一协议」从「事实上如此」升为「界限的定义」。

(fylite-report-07-boundary-protocol)=
## 8.2 同一协议要携带什么 (What the shared protocol must carry)

「同一 fyo 描述协议」只有在下面三条成立时才是界限而不是口号：

- **I-1 计划可互认。** fytok 的工作流计划是 `ComputationPlan.has_step[]`；其中一步 `prescribes_code` 一个 fylite 的
  `code/<x>`，该步的子计划就是一份 fylite 能直接吃的 `fyo:ScenarioSpecification`——**不经翻译**。这要求 fylite
  的 code 表（`FR-KERNEL-002`：完成哪些 code、要哪些输入、产哪些路径、什么单位）以 `spo:Code.declares_port /
  declares_parameter` 自述（`FYL-REPORT-06` B-2），而不是以 `fylite:vocabulary` / `fylite:ports` 这类本体里没有
  对应类的私有键（`-17` G-7）。今天的模板正是后者（§4.1）。
- **I-2 记录可编排。** fytok 从记录推出边（`FYL-REPORT-06` §8.3：节点 = 记录，边 = 输入具体化等于另一记录的输出
  具体化）、判状态、决定重试与续跑。这要求记录携带：`run_state`（七值中至少产 `succeeded` / `failed` / `rejected` /
  `cancelled`）、每个端口的 `bound_concretization.checksum`、`executed_code` 的具体化校验和（内核身份）、
  `produced_checkpoint`。今天四项里只有校验和齐（§4.8），且静态链接时内核校验和为空（C-26）。
- **I-3 断点可搬动。** fytok 把检查点跨节点搬、在另一台机器上续（`FYL-REPORT-06` §9.4「fylite 写、平台搬」）。
  这要求 `spo:Checkpoint` 的 `opaque_state` 是记录里一棵**声明过**的子树（`-16` S-2），带 `resumable_by`（S-6），
  且 fylite 的每个宿主都能从它续（`-18` U-19）。今天只有浏览器一侧、且未接线（§4.7）。

〔判〕三条不变式今天**没有一条完整成立**。这把本报告 §4 的三处最大缺口（编辑词表 · 状态追踪 · 断点恢复）
从「fylite 的易用性问题」改判为「**界限本身尚未落地**的问题」：在 I-1..I-3 成立之前，fytok 集成 fylite 的
方式只能是调 `fy run` 拿目录，而不是把 fylite 当一个 `Code` 编进工作流。

(fylite-report-07-boundary-table)=
## 8.3 八项功能的归属 (Ownership per function)

:::{table} 界限表。「协议携带」列是两侧都必须遵守的那一份；「fylite」列是最小工具集的上界；「fytok」列标〔工作假设〕。
:name: tbl-r07-boundary
:align: left

| 功能 | fylite（最小工具集，自包含） | fytok（完整功能，开放集成）〔工作假设〕 | 协议携带 |
| :--- | :--- | :--- | :--- |
| 编辑 | 一份计划的六层合成（模板 → 装置 → 预设 → `--plan` → 命令行 → 端口绑定）；参数按 code 表校验；页面控件由词表投影 | 工作流编辑（DAG · 视觉编程 `workflow-ir/2.0`——fylite 只把它当**投影**写账本，不当编辑器）；插件参数面；多代码的计划拼装 | `ParameterDefinition` / `PortDefinition` 自述（I-1）；`has_parameter_setting` / `has_port_binding` |
| 可视化 | 记录 → 呈现规格的**推出规则**（P1..P4）与两个渲染器（MyST + SVG · 页面）；五种视图 + 极向截面 | 跨步、跨代码、跨运行的综合视图与仪表板；自定义视图种类 | `spo:PresentationSpecification` 词表；fylite 的推出规则可作参考实现，不作规范 |
| 执行 | **一步 / 一案**：单机、本进程、一次门调用；批式档 = 同一进程内可分步可中断（`FR-HOST-002`） | DAG 调度、重试、并行、跨节点；外部物理代码经 `EngineeringPortRun`（live / stub / archive）接入；HPC 码的产物作为数据进入 | fylite = 一个 `Code`；fytok 只经文档门调用（`FR-KERNEL-001`），永不调扁平导出 |
| 状态追踪 | **一份记录**的 `run_state` + `refusal.stage`；进度由调用方数（`-16` 撤回回调） | 工作流级状态（排队 · 依赖等待 · 重试次数）、多记录账本、审计 | 记录的 `run_state` 七值（I-2）；fylite 不产工作流级状态 |
| 导入 | 文件端点（七种格式）· mdsip 只读 · A-Box 语料 · 文件源的装配 | 平台端点（`shm://` · `s3://` · 数据契约 SpData）、外部码专有格式、多源治理 | `DataSourceEndpoint` / `Concretization.format_iri`；`x+run://` 句柄 |
| 导出 | 记录目录自足（`plan` · `record` · `<ids>` 文件）；四种数据集格式；浏览器文档集 zip | 发布、版本、许可与治理信封、跨仓分发 | `Concretization{storage_uri, checksum, byte_size}` |
| 断点恢复 | 每个步界**交出**完整状态并能从它**续**（S-3 / S-4）；四宿主同一份记录可续（U-19） | 检查点的存放、搬运、重启策略、跨节点续 | `spo:Checkpoint{opaque_state, state_content, resumable_by}`（I-3） |
| 溯源 | 一次运行的完整记录：计划 · 代码 · 参数来源 · 端口 · 校验和 · 内核身份 · 环境指纹 | 跨运行谱系、施动者 / DID / 签名、治理信封、审计链；推动上游补施动者类（`FYO-ADR-07` OI-3） | `spo:ComputationRecord`；fylite **不载**身份与签名（`FYL-REPORT-06` §9.4「本体不载身份」） |
:::

(fylite-report-07-boundary-negative)=
## 8.4 两侧的负面清单 (What each side must not do)

**fylite 禁止（MUST NOT）**——多数已有条款，此处只是并排：

- 插件机制（建设原则 3）；工作流引擎 / DAG 调度（`FYL-REPORT-06` §9.1）；分布式运行时或必需的服务端组件（`NR-ENV-001`）。
- 导入 `sp` / `fy*` 任何包（`NR-DEP-002`）；运行时依赖任何外部物理模块——**vendored 参考实现只在内核仓的
  神谕树 `tests/oracles/` 里作对拍裁判**（建设原则 1），不进发行制品；`EngineeringPortRun` 不在 fylite 实现。
- 超出四条包络（单机 · 毫秒至秒交互档 · 有限多线程 · 跨平台）的功能深化（`FYL-CONOPS-00` §系统演进「包络不变式」）。
- 载身份、签名、治理信封（归平台数据契约层）。
- 「轻量」的可判形：Python 必需依赖仅 numpy（`NR-DEP-001`）；一个可执行文件（`-15` R-2）；浏览器零安装离线可用；
  内核一个可选依赖（`rayon`）。

**fytok 禁止（MUST NOT）〔工作假设〕**——从「同一协议」推出，待 fytok 侧文档确认：

- 以 fylite 的扁平导出或 Python 内部 API 集成 fylite（只经文档门，`FR-KERNEL-001` 的镜像条款）。
- 要求 fylite 为集成而增加宿主专属接口（`FR-HOST-003`：新增宿主不得要求内核契约改变——fytok 是「再来一个宿主」）。
- 把 fylite 当作必需依赖：fytok 的工作流对 fylite 的引用是 `prescribes_code` 一个 IRI，fylite 缺席时按名拒（`FR-KERNEL-003` 同款）。

(fylite-report-07-boundary-consequences)=
## 8.5 对本报告建议的重排 (Consequences for R-1..R-9)

界限把九条建议分成两档。**协议承重**的一档是界限成立的前提，其关闭判据应改为「fytok 能把 fylite 当一个
`Code` 编进工作流」；**fylite 内部**的一档只影响 fylite 自己的易用性，不阻塞集成。

| 档 | 条目 | 为什么 |
| :--- | :--- | :--- |
| 协议承重 | **R-2**（一种记录形）· **R-1**（断点成子树、四宿主可续）· **R-3**（状态词表与产者）· **R-8** 中的「`fylite:vocabulary` / `switches` / `ports` 的对应类」与施动者类 | 分别对应 I-2 · I-3 · I-2 · I-1；缺任一条，fytok 只能调 `fy run` 拿目录 |
| fylite 内部 | R-4（控制词表入 code 表）· R-5（文档时效）· R-6（构建路径）· R-7（数据仓的闸）· R-9（`-20` 三张表） | 不改变协议；R-4 与 I-1 相邻但方向相反——它是 fylite 三个宿主读同一份，I-1 是 fytok 也读同一份；做 R-4 时按 `spo:Code.declares_*` 的形做，两者合一 |

〔判读〕R-3 在 §7 留了一条开放猜想（CLI 上的 `cancelled` 要不要把「一串门调用」搬进 `run.rs`）。
界限给了答案的一半：**分步与中断是 fylite 的义务**（`FR-HOST-002`、S-3），**调度是 fytok 的**。
所以 `fy run` 需要一个步预算参数与一个 SIGINT 落点（停在步界、记录写出 `cancelled` + 断点），
但**不需要**队列、不需要 `submit` / `status` 的服务端——B-8 的四方法在 fylite 里只是 `serve` 的可选面，
真正的异步面归 fytok。R-3 的落点因此收窄为「CLI 与 Python 产 `cancelled` 与断点」；`stream` 与队列从 fylite 的排期里去掉。

(fylite-report-07-boundary-open)=
## 8.6 未定项 (Open items)

- **B-1 fytok 侧的对应文档。** 本节 fytok 列全部〔工作假设〕；应由 fytok 的 CONOPS / SDD 出一份镜像表，
  两表逐行对读——判据：两表对同一功能的「协议携带」列**逐字相同**。
- **B-2 `FYL-CONOPS-00` 范围外表要改一行。** 「跨节点 / 分布式编排、批量作业管理 → Sp 平台编排层」与本次裁定
  「复杂工作流 → fytok」的关系（fytok 是平台上的集成者？还是平台之外另一层？）待裁；本报告不代改 CONOPS。
- **B-3 `EngineeringPortRun` 的产物进 fylite 的形。** 建设原则 6 允许 HPC 码的**产物**进入；产物以哪种
  `Concretization` 形进 fylite 的输入端口、由谁保证其 `format_iri` 是 fylite 认的七种之一——归 fytok 的
  导出面还是 fylite 的导入面，未裁。
- **B-4 参照对基线。** `FYL-CONOPS-00`〔开放猜想〕的「轻量档 × 全功能档」参照对，在同一协议下可机械构造：
  同一份计划，`prescribes_code` 分别指 fylite 与 fytok 的 `Code`，两份记录逐端口比，进登记册作第四类记录
  （`-16` G-4 「后端间对照」）。载体与判据待 fyo `ComparisonRecord` 能否表达「同一计划两个代码」——未核。

(fylite-report-07-landing)=
# 9. 落地记录 (What was landed, 2026-09-12)

〔已确立〕用户「落地 R1～9」。本节逐条记**落成什么 · 量到什么 · 没落成的为什么**。
规矩同 `FYL-REPORT-00`：没有关闭判据的条目与一句抱怨等价，所以未落的也要带判据。

:::{table} 九条的落地状态。「闸」列写钉住它的那道断言。
:name: tbl-r07-landed
:align: left

| # | 状态 | 落成什么 | 闸 |
| :--- | :--- | :--- | :--- |
| **R-1** | **大半落地** | `fylite:state` 进记录；`fy run --resume-from`；`fylite.engine.resume` + `cases.run(resume=)`。三处读**同一个**子树 | `test_resume.py` 六条（真制品） |
| **R-2** | **落地** | 记录增 `environment`（内核指纹 · ABI · 版本）；静态链接的内核指纹不再为空；计划身份改末层优先 | `test_resume.py::…kernel_wrote_it`；浏览器 `identity()` 实测 |
| **R-3** | **半落** | `RunState` 收成一份枚举（七值 + 反解 + 全表）；`record()` 由调用方给终态 | `cargo test`；`cancelled` **仍无产者** |
| **R-4** | **不落（前提有误）** | 见 {ref}`fylite-report-07-landing-r4` | — |
| **R-5** | **落地** | C-1 · C-2 · C-3 · C-11 · C-27 改口；三处算例章把退役写法发给读者的代码块修正 | 新闸 `test_no_reader_page_hands_out_a_retired_command`（对原缺陷验证过会红） |
| **R-6** | **落地** | 数据层缺席按名跳过；`--static` 的开发机路径归零；卫生闸话术给出路；`_flavour.py` 被改写时出声 | 干净检出实测 0 失败 |
| **R-7** | **落地**（fydoc） | `RELEASE.yaml` 前缀改真名并对空匹配报错；`[TBD]` 子串判据；`review.status` 增终态并校验；`payload` 缺失即拒 | `check_cases.py` 28 → **51 处**（全部是应当红的新发现） |
| **R-8** | **部分落地**（fyo） | 缺 spo 检出时按名跳过（并修掉 **7 条空洞通过**）；`FYO-ADR-14` / `-15` 两份 Proposed | `check_competency.py` 由 exit 1 变 exit 0（17 过 / 0 败 / 45 点名跳过） |
| **R-9** | **不落** | 见 {ref}`fylite-report-07-landing-rest` | — |
:::

(fylite-report-07-landing-measured)=
## 9.1 量到的三个数 (Three measurements)

**① 续跑的等价性**——`FYL-REPORT-06` B-5 / `-18` §十三 的那条判据，第一次在**真内核**上量
（浏览器那道闸用的是确定性假件）：

| 档位 | `nsteps=40` 一次 vs `20` + 续 `20` | 时钟 |
| :--- | ---: | :--- |
| 常数闭合（算例缺省） | Te **0.000e+00** · n_e **0.000e+00** | 逐位相同 |
| 新经典闭合 + 密度 + 动量通道 | Te **6.08e-01** · n_e **6.99e-01** | 0.41806 vs 0.41096 s |

第二行**不是本次落地的缺陷，是 `-16` G-8 的大小**：内核从 `evolve/fylite:*` 读回三条
滞后量（`psi_prev` / `sigma_prev` / `exch_prev`），却把它们写进自己的**原始条目块**，
而中间层只把**声明过的表**里的槽压进扁平树（F-2）——那个块没有表，所以它们过不去。
今天的处置是**如实**而不是近似：续跑时打开内核自己的 `lag_reset`（「状态被重映射，
首步不加欧姆项」），命令行说一句，计划里留痕。★★这一条的第一版是**拒绝**，而那是错的：
常数闭合那一档 `exch_prev_out` 也非零却逐位相同——**非零不等于起作用**，那一版把一次
完全正确的续跑判红了。判据要么是内核的（只有它知道用不用得上），要么就别装作是判据。

**② 干净检出的失败数**——README 那条路（不建内核、不建数据层）：

| | 失败 | 错误 | 通过 | 跳过 |
| :--- | ---: | ---: | ---: | ---: |
| 落地前 | **73** | 10 | 1960 | 411 |
| 落地后 | **0** | 0 | 1972 | 491 |

73 条里 44 条是**同一句话**（数据层没建）。README 承诺「缺内核的按名跳过」，而缺的
常常是**第二份库**——那一条承诺没有覆盖到它。

**③ `--static` 的开发机路径**：**284 → 0**。原因不是洁癖失灵，是 `RUSTFLAGS` 的
`--remap-path-prefix` **管不到 `cc`**，而 `--static` 要用 `cc` 编 vendored 的 HDF5 C 源码。
加 `-ffile-prefix-map`（先探编译器认不认）之后清零。★剩下两条含 `$HOME` 的字符串是
HDF5 把**它被给的 C flags** 原样刻了进去——也就是那条 remap 自己的记录；判据因此改成
「数真的路径」，源码路径一条不许剩。

(fylite-report-07-landing-r4)=
## 9.2 R-4 不落，且它的前提要改判 (R-4 is withdrawn, and why)

〔已确立·实测〕R-4 写的是「控制词表入 K-2 code 表，三宿主读同一份」，判据是
「`validate-form.mjs` 与 `test_scenario_templates.py` 读同一生成物」。**这条建议假定
存在两份互相漂移的清单**，而实测不是这样：

| code | 模板 `fylite:vocabulary` | 内核 `*_PARAMS` | 交集 |
| :--- | ---: | ---: | ---: |
| `code/transport` | 19（`amin` · `chi0` · `q95` · `kappa` …） | 12（`d_pc` · `theta` · `tol` · `relax` …） | **0** |
| `code/evolve` | 114 | 83 | 26 |
| `code/zerod` | 33 | 10 | 4 |
| `breakdown` · `discharge` · `reconstruction` · `pfwave` · `profile` · `series` | 17 / 23 / 46 / 14 / 5 / 8 | **无 `*_PARAMS` 块** | — |

两列**不是同一层的东西**：模板名的是**装配层**的参数（`code/<x>` 门收的），内核的
`*_PARAMS` 名的是**原始入口**的参数（`evolve_heat` 一类收的）。`code/transport` 交集
为零正是因为它们各说各的层；`code/evolve` 有 26 条交集，只因为那扇门把一批入口参数
原样透传。

〔判读〕所以**code 层的参数面今天没有任何一处声明**（新登记 **C-28**）——`FR-KERNEL-002`
（「每个内核后端必须自报 code 表：每个 code 要哪些输入、产哪些路径、什么单位」）在
**code 这一层**未兑现；`-16` K-2 的增列正是它。模板那份是 `tools/make-scenario-templates.py`
从**语料用过的名字**生成的，页面那份是一次性誊录的，两份都不是声明。

〔已确立〕这不是纸上推演：本次落地被它绊了**两次**，两次都是**不报错的错**——
按模板的 `fylite:ports` 筛，交接文档一份都没绑（内核随后按名拒绝，还算好的）；
按模板的 `fylite:vocabulary` 筛，交接标量全被丢掉，**续跑从 t = 0 起而退出 0**。
两处筛子都已删除，判据改回内核的声明面。

〔判据〕R-4 改写为：**先落 `-16` K-2 的 code 表自报**（`spo:Code.declares_parameter` /
`declares_port`，含 `range` / `default` / `enum` / `tier` / `group`），再谈三宿主读同一份。
关闭判据：`fy list kernel --json` 对每个 `code/<x>` 交出它自己的参数表，且
`test_scenario_templates.py` 能据此对账——今天它无从对账，因为对面是空的。
这同时是 §8 的 **I-1**：fytok 要把一份 fylite 计划当一步吃下去，靠的就是这张表。

(fylite-report-07-landing-rest)=
## 9.3 其余未落的，与它们卡在哪 (What is still open)

- **R-3 的 `cancelled` 没有产者。** `fy run` 一次门调用跑完整个 march，**宿主没有介入点**
  ——要产 `cancelled`，得先把 `-18` U-8 的「一串门调用」搬进 `run.rs`（步预算 + 分片）。
  枚举已经收成一份（本次），产者归那件事。判据不变：取消一次 200 步演化 → 记录
  `cancelled` + 断点，从它续跑与一次跑完逐位相同。
- **R-1 的浏览器一端未接线。** `run.js` / `checkpoint.js` 仍然没有任何页面 `<script>` 引用
  （`-18` 分期 U0 未完），断点闸仍用假步进器。本次把**真内核上的等价**补上了（Python 侧），
  但「页面上按恢复」这一步没有走通。判据：`app/pages/` 至少一页加载它们，
  `validate-checkpoint.mjs` 的步进器换成真门。
- **R-8 的 schema 改动落不了地。** fyo `PROJECT.md` §5 要求 `../spo/scripts/check_conformance.py`
  退 0 才准提交 `schema/`，而那份检出不在——`UncertaintyStatement` 的槽名与基数
  也无从核对。两份 ADR（`FYO-ADR-14` / `-15`）是 Proposed，**没有**凭空铸类。
- **R-9 三张表未生成。** `surface/` 可从 `fy list kernel` 派生；`coverage/` 的 `covers`
  边**要人逐条判断**（`-20` G-1 自陈「机器猜不出一条记录验证的是哪个 code」）；
  `availability/` 的 286 格要装置卡片在场，而公开检出不含它们（`-20` G-5）。
  三者里只有第一张今天算得出，单出一张表会让「一处产、两处渲染」（M-2）变成
  「一处产一张、两处渲染半张」，故不单出。
- **C-29（新）**：`fy list devices` 在没有内嵌语料的构建上把「语料路径是空的」印在
  stderr 上而**退出 0**。按本仓自己的退出码纪律（0 = 跑完），答不出东西时退 0 是可议的；
  本次只把闸子的判据说准（答出东西时管道才必须干净），**不代它裁定**。

(fylite-report-07-landing-closed)=
## 9.4 判关的条目 (Closed)

C-1 · C-2 · C-3（文档改口）· C-4（`--resume-from` 落地，注释与产物一致）· C-6（记录带
`environment`，浏览器 `identity()` 实测读得到）· C-10（数据层按名跳过）· C-11（`report`
入 `--page` 并加「盘上每一页都叫得出名字」的闸）· C-12（改写生成物时出声）·
C-15 · C-16 · C-21 · C-23（fydoc 四条）· C-26（静态链接的内核指纹）· C-27（计划身份末层优先）。

**仍开**：C-5（`cancelled` 无产者）· C-7（`fylite:state` 有了名字，但**形**仍归 `-16` G-8）·
C-8（两种「续跑」仍是一个词）· C-9（Python `RunManifest` 未退役）· C-13（spo 不在场，已改为
按名跳过，但 schema 仍验不了）· C-14 · C-17..C-20 · C-22 · C-24 · C-25 · **C-28**（新）· **C-29**（新）。


(fylite-report-07-appendix-measured)=
# 附录 A · 实测记录 (Measured record)

全部在本环境（Linux x86-64 容器，rustc 1.94.1，Python 3 经 `uv run --no-project`）于 2026-09-12 量得。
每个数都可按下列命令重取。

**A.1 内核构建。**

```console
$ cd fylite_kernel && FYLITE_PUBLIC=../fylite bash rust/build.sh
[build] static exports: 57 个 fylite_rs_* + fylite_ext_abi_version ✓  (31783014 bytes)
[build] -> …/fylite/rust/kernel-lib/libfylite_kernel_static.a （附 kernel-static.json）
[soname] …/python/fylite/_lib/libfylite_kernel.so -> .so.0 -> .so.0.0.1 (3600056 bytes)
[soname] …/python/fylite/_lib/libfylite_kernel_ext.so -> .so.0 -> .so.0.0.1 (1418840 bytes)
$ cat fylite/rust/kernel-lib/kernel-static.json
{"kernel_version": "0.0.1", "abi": 153, "built": "2026-09-12T06:32:54Z",
 "sha256": "97d1cc7adbf4407f4b181fcbf85fb599a654242577707987debace6d3d89ad1c", …}
$ git -C fylite status --short
 M python/fylite/_flavour.py          # FLAVOUR "internal" -> "none"（C-12）
```

**A.2 中间层构建。** 系统无 `libhdf5-dev` / `libnetcdf-dev`（`apt-get` 404）。

```console
$ cd fylite && bash rust/build.sh --exe --static --no-kernel-check
    Finished `release` profile [optimized] target(s) in 1m 39s
::error:: …/rust/fylite_runtime/target/release/libfylite_runtime.so 里有 284 条开发机路径
```

制品未安装。为完成测量，把 `target/release/libfylite_runtime.so` 手工装入 `_lib/`（三级符号链接同 `soname.sh`）。
此步不在任何文档里，且使 `test_bundled_artifacts.py` 正确地转红。

`fy` 可执行文件：`cargo build --release --features desktop,static --bin fy` 失败于 `assets.rs:27-30`
的 `include_bytes!`（缺 `app/assets/fylite_{rs,kernel_ext,web}.wasm.0.0.1`）；wasm32 目标本环境未预装。

**A.3 pytest 全量。**

| 条件 | 结果 | 失败归因 |
| :--- | :--- | :--- |
| 有内核、无数据库（`-x` 首停） | 300 passed · 12 skipped · 1 failed | `test_case_runs.py::test_the_transport_case_runs_and_passes`：`KernelError: the data library is not built` |
| 有内核、无数据库（全量） | **1960 passed · 411 skipped · 73 failed · 10 errors**（29.6 s） | 44 处同一 `KernelError`；涉及 `test_evolve_entry` 29 · `test_ledger` 10 · `test_run_records` 7 · `test_replay` 6 · `test_report` 6 · `test_case_runs` 5 · `test_whence` 5 · `test_scenario` 3 · `test_run_modes` 3 · `test_gfile_roundtrip` 3 · 其余各 1 |
| 有内核、有数据库（手工装） | **2046 passed · 405 skipped · 3 failed**（58.9 s） | `test_doc_links` / `test_doc_frontmatter`（本报告新增 `docs/report/` 时尚空）· `test_bundled_artifacts`（手工装的 `.so` 不在账本） |

**A.4 数据仓闸。** `python3 fydoc/tools/check_cases.py` → `FAIL — 21 组, 28 处不满足, 16 组 review 待补`。

**A.5 静态核对。**

```console
$ grep -rln "fylite:state" fylite/python fylite/rust fylite/app/assets fylite_kernel/rust
fylite/app/assets/bundle.js  fylite/app/assets/scenario-analysis.js  fylite/app/assets/checkpoint.js
$ grep -c resume fylite/python/fylite/_cli.json
0
$ grep -l "run.js\|checkpoint.js" fylite/app/pages/*.html
(空)
$ grep -n "def \(submit\|status\|stream\|cancel\)" fylite/python/fylite/engine/serve.py
(空)
```

**A.6 `fy` 一次真跑。** wasm32 目标装上、内核 `--wasm-check` 出三份 `.wasm`、中间层 `abi_gfile` 出
`fylite_web.wasm` 后，`cargo build --release --features desktop,static --bin fy` 成功（24.3 MB）。

```console
$ fy list scenarios          # 22 行：9 份模板中 6 条 today=runs，3 条「the kernel door does not carry this code」，13 条无模板并各给理由
$ fy list kernel             # kernel: <linked> (abi 153)；列出门认的 code 与其装配说明
$ fy run model --preset zerod-iter-15ma -o rec
run/20260912T064723Z-transport  scenario/transport -> code/zerod  entry zerod  nt=201 nr=41
  summary / core_profiles / entry  三份 .fyo.jsonld；record: rec/record.jsonld        # 退出 0
$ fy run model --preset zerod-iter-15ma --resume rec/record.jsonld -o rec2
fy run: unknown scenario `rec/record.jsonld` on the model line                      # 退出 2（按名拒；话术指向位置参数而非旗标）
$ fy case run x
fy: `case run` is retired — use `fy run <the same plans>`                           # 按名指路
```

`rec/record.jsonld` 顶层键：`@context` · `id` · `type` · `title` · `realizes` · `executed_code` · `run_state` ·
`started_at` · `ended_at` · `parameters` · `inputs` · `comment` · `caveat`。`run_state = succeeded`；**无** `environment`
键；**无** `fylite:state`；`executed_code = {name: fylite, version: "abi 153", concretized_as: [{… checksum 缺}]}`（C-26）；
`realizes = {id: scenario/transport, …}` 而 `plan.jsonld` 的 `prescribes_code = code/zerod`（C-27）；七条端口绑定各带
`bound_concretization`。

(fylite-report-07-appendix-trace)=
# 附录 B · 追溯 (Traceability)

| 本报告 | 既有登记 |
| :--- | :--- |
| §4.7 · C-7 · R-1 | `FYL-DESIGN-16` G-8 · S-2 / S-4；`FYL-SDD-01` DE-LOG-12〔目标态〕；`FYL-REPORT-06` B-5；`FR-KERNEL-004` |
| C-4 · U-3 · R-1 | `FYL-DESIGN-18` G-4 · U-19 |
| §4.1 · U-8 · R-4 | `FYL-DESIGN-18` G-1；`FYL-DESIGN-16` K-2 增列 |
| §4.2 | `FYL-DESIGN-18` G-3 · G-10 · G-13（已关） |
| §4.3 · R-3 | `FYL-REPORT-06` B-8 · §9.3；`FR-HOST-002` |
| §4.4 · C-19 · R-9 | `FYL-DESIGN-20` M-1..M-13 · G-1 · G-5 · G-9 |
| §4.5 | `FYL-DESIGN-18` G-14；`FYL-REPORT-06` B-3 |
| §4.6 · C-15 | fydoc `cases/README.md` §2；`cases/RELEASE.yaml` 自陈盲区 |
| §4.8 · C-9 · R-2 | `FYL-REPORT-06` §8 · B-4；`FYL-DESIGN-20` M-5 |
| §3 · C-13 · R-8 | `FYO-ADR-07` D-1 / D-5 / OI-1 / OI-3 / OI-4；fyo `.context/PROJECT.md` §2.1 不变式 6；`FYO-REPORT-05` O-3 / O-4 |
| C-14 | `FYO-REPORT-05` §O-4；fydata `README.md` G-10 |
| C-24 | 本仓 `TODO.md` K-1..K-4 |
| C-21 · C-16 · C-23 · R-7 | 本仓 `TODO.md` E-6；fydoc `tools/check_cases.py` |
| U-9 | 本仓 `TODO.md` F-2 |
