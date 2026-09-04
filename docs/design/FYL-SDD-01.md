---
document_id: FYL-SDD-01
title: FyLite 软件设计描述 (FyLite Software Design Description)
shortname: fylite-sdd
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
    v1.0 全文重写（用户「优化重写整个设计文档」，2026-09-04）。组合视图按 `FYL-DESIGN-16`
    v2.0 的**四层**重排（多宿主 → 中间层 → 内核，语义层横跨），布局表按 2026-09-04 的仓树
    重写——v0.13 那张表里 `docs/cases/` `docs/note/` `docs/archive/` `mapping/` `machine_desc/`
    与「四本书集」都已不存在：语料在仓根 `cases/`，实测笔记与归档随内核进了私有仓，
    `docs/` 是**一本书五篇**外加不入册的 `benchmark/`。九个组件保号：DE-COMP-01 改为
    「内核（可替换）」并注明源码在私有仓、C ABI 降为本地后端内部；DE-COMP-09 改为
    「中间层」（数据层是它的一半）；DE-COMP-04 场景层注明退役中（四个校验模块已迁入
    `engine/`，装配随 K-3 进内核）。逻辑视图：DE-LOG-01 由「单核双宿主」改为「一份内核
    契约、多宿主」；新增 **DE-LOG-11 文档门与扁平树**、**DE-LOG-12 内核无状态**（编号
    自 11 起，08..10 留给页面文档的提案，登记见 `FYL-SRS-01` 附录）。接口视图重列为
    宿主 ↔ 中间层 ↔ 内核三段并分「今天 / 目标」两列。追溯矩阵补 FR-KERNEL-*。历次
    版本里的沿革叙述（导入环、`_backends.json`、`cp -L`、书集改一本）各压成一句。
    · v0.13 三种发布形态与统一命令行入册（新增 DE-COMP-09；`_cli.json` 成为三宿主共同定义）。
    · v0.12 `docs/` 定为书集、`note/` 不入册（★2026-09-02 已改回一本书，见 v1.0）。
    · v0.11 语料与 V&V 登记册合并；页面不再取算例。
    · v0.10 装置牌一份真源；`mapping/` 入布局表（★后已退役）。
    · v0.9 报告面 `fylite report`。· v0.8 `cases/` 提升；CLI 为主要调试环境。
    · v0.7 DE-COMP-08 语义层、DE-LOG-07 语义单源、DE-COMP-05.2 LLM 位置纪律。
    · v0.6 DE-COMP-05.1 BYOK LLM 前端。· v0.5 装置牌宿主 `device.py`。
    · v0.4 及以前：五视图初稿，DE-LOG-03 后端注册表（2026-08-21 退役）。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-sdd

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-SDD-01` |
| 文档名称 (Title) | FyLite 软件设计描述 (FyLite Software Design Description) |
| 短名 / Slug | `fylite-sdd` |
| 版本 (Version) | v1.0 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | IEEE Std 1016-2009 |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | Yes (规范性) |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Fable 5 |
| 受众 (Audience) | maintainers / solver authors / LLM-tool integrators / 要接第二个内核实现的人 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | FYL-SRS-01 v1.0（软件需求）· FYL-CONOPS-00 v1.0（运行概念）· FYL-DESIGN-16 v2.0（可替换内核与四层分工）· FYL-DESIGN-14（中间层的数据半边）· FYL-DESIGN-15（发布形态与命令行） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

(fylite-sdd-abstract)=
# 摘要 (Abstract)

本文件按 IEEE Std 1016-2009 描述 FyLite 的软件设计：背景 / 组合 / 逻辑 / 接口 / 行为
五个视图。设计元素（`DE-*`）逐一回接 {ref}`FYL-SRS-01 <fylite-srs-abstract>` 的需求；
组合视图是仓内包分层的**规范源**，其变更**必须 (MUST)** 与 `.context/PROJECT.md`
源布局节同批同步。本版描述 2026-09-04 的 as-built 设计，并把 `FYL-DESIGN-16` 裁定的
**目标态**（可替换内核、文档门、无状态内核）作为设计元素登记，逐条标明今天落到哪。

(fylite-sdd-conventions)=
# 约定与术语 (Conventions and Terminology)

- 设计元素 ID：`DE-COMP-NN`（组件 / 结构）、`DE-LOG-NN`（逻辑 / 行为）；每个元素携
  四字段块（职责 / Traces to / 不变式 / 接口），目标态元素另带「今天」一行。
- 术语沿 `FYL-CONOPS-00`（宿主 / 运行时、交互档 / 批式档）与 `FYL-SRS-01`（场景线、
  装置描述、内核契约）；本文件不重定义。
- **内核（kernel）**：以 Rust 实现的数值内核，源码在私有仓 `fylite_kernel`，编译为本机
  动态库与 WebAssembly 模块两种制品装进本仓。**可替换**：本地 / 页内 wasm / 远端 /
  另一种实现，对上只经文档门。
- **中间层（middle layer）**：`rust/fylite_runtime/`——数据的集成与转换、计划的合成与
  绑定、内核的发现与选择、Rust 宿主的命令行与 `app/` 的伺服。
- **执行体（engine）**：`python/fylite/engine/`——跑运行、记运行：命令行、服务、清单、
  溯源、重放、报告、校验。与中间层是**共用一个词根的两个不同组件**。
- **后端（backend）**：一个可被选中的内核实例——本地 `.so`、页内 wasm、远端进程。

(fylite-sdd-context)=
# 背景视图 (Context View)

FyLite 以一个公开仓（本仓）加一个私有内核仓交付，对外呈现四个宿主、两个运行时与
`FYL-SRS-01` §外部接口的十一个接口面。系统边界上有四条固定关系：

1. **实验数据在外，装置描述誊录在内**：炮的测量只在运行时经 mdsip 取回；装置描述的
   真源是外部 A-Box，本仓持有公开誊录 `app/devices/*.jsonld`（FR-DATA-001）。
2. **生态零代码耦合**：不导入任何 `sp` / `fy*` 包；互操作只经声明清单与语言中立的
   进程间接口（NR-DEP-002）。
3. **一份内核契约，多宿主**：宿主经中间层、中间层经文档门到达内核；内核可替换
   （FR-KERNEL-001..003，NR-ENV-004）。
4. **内核源码在私有仓，制品在本仓且不入库**：`libfylite_kernel.so` 与三个 `.wasm` 由
   内核仓的构建脚本装入，打包时随包；本仓唯一的 Rust 源码树是中间层。

(fylite-sdd-composition)=
# 组合视图 (Composition View)

本节为仓内布局的**规范源**。{numref}`tbl-fylite-sdd-layout` 给出目录到组件的映射
（2026-09-04 as-built）；{numref}`fig-fylite-sdd-components` 给出四层与依赖方向。

:::{table} 仓树 → 组件映射（规范）。仓根不是 Python 工程：Python 工程自含于 `python/`。
:name: tbl-fylite-sdd-layout
:align: left

| 目录 | 组件 | 说明 |
| :--- | :--- | :--- |
| （私有仓 `fylite_kernel`）`rust/fylite/` | DE-COMP-01 内核 | 单 crate；本机 cdylib 与 wasm 模块同源构建。**制品落进本仓、不入库**：`python/fylite/_lib/libfylite_kernel.so`、`app/assets/fylite_{rs,tglf,dke}.wasm`，以及生成物（`_abi.py` / `_fyo_interface.py` / `app/assets/fyo-interface.js` / `version.js` 等，禁手改）。本行留在表里是因为它指派的是制品落点与依赖方向 |
| `rust/fylite_runtime/` | DE-COMP-09 中间层 | 本仓**唯一的 Rust 源码树**，源码公开（协议编解码、文件格式、计划与门，不是物理 IP）。一份源两个制品：`libfylite_runtime.so`（Python 经 ctypes）与 `fylite-app`（**唯一的可执行文件**，内嵌整个 `app/`，承载 `app` / `data` / `case`）；第三个制品 `fylite_runtime.wasm` 是裁定（`FYL-DESIGN-16` H-4），尚无构建脚本。构建 `rust/build.sh` |
| `python/fylite/*.py` `io/` | DE-COMP-02 Python 装配层 | `fyo.py` `device.py` `kernel.py` `run.py` `plot.py` `nn.py` `appsession.py` 与 `io/`（`fydoc` `geqdsk` `mds` `est2` `gacode` `efund` `reference`）；`python/` 内含 `pyproject.toml` / `pytest.ini` / `tests/` |
| `python/fylite/engine/` | DE-COMP-03 执行体 | 22 个模块：命令行 · `serve` / `mcp` · 清单 · 溯源 · 重放 · 报告 · 底账 · 版本 · 别名 · 跨运行时 · 语料 / 物理校验 / 套件 / 登记册（2026-09-04 自 `scenario/` 迁入） |
| `python/fylite/scenario/` | DE-COMP-04 场景层（退役中） | `analysis/` `control/` `design/` `model/` 四条线的装配 + `waveform.py`；按 `FYL-DESIGN-16` K-3 逐个进内核 |
| `app/` | DE-COMP-05 浏览器前端 | 三个散文页（中英各一）· `pages/` 五页正本（`pulse_design` `model` `analysis` `data` `report`）+ 五张 `page_*` v2 外壳页（生成物，未提为正本）· `assets/`（JS、样式、wasm 制品、生成物）· `devices/`（装置描述誊录）· `guide/`（用户指南的公开子集，生成物）· `tests/` 门禁 |
| `python/fylite/_manifest/` `_spec/` `_cli.json` `_environment.json` `_fyo_vocab.json` | DE-COMP-06 声明面 | 数据非代码；随 wheel 分发。13 份能力清单、4 份 vendored schema、一份三宿主共用的命令行规格、一份环境变量表、一份 fyo 词表 |
| `app/devices/` + `python/fylite/device.py` | DE-COMP-07 装置接入 | 装置描述的公开誊录（`catalogue` / `east` / `iter`，自 A-Box 实拷）与 Python 侧的定位与读法 |
| `cases/` | 场景语料（数据） | fyo / JSON-LD 会话文档 + `catalogue.jsonld` + `context.jsonld`；读者是 `fylite cases`、`fylite.engine.cases` 与书，**浏览器不读**；不随 wheel 分发 |
| `docs/` | 文档：**一本书，五篇** | `guide/` `examples/` `reference/` `physics/` `design/` 一份 `myst.yml`；**不入册**：`benchmark/`（公开 V&V 登记册：`registry.jsonld` + `reports/` + `scenarios/` + `physics/`——按路径被引用的记录）、`figures/`、`_build/`。实测笔记与归档设计笔记随内核进了私有仓 |
| `tools/` | 辅助 + 发布路径 | 三种发布形态各一条构建路径（`build-app-exe.sh` · `build-site.sh` · `build-wheel.sh`）、页面 / 图 / 预览生成器、A-Box 投影（`abox-mds-bind.py` `abox-to-machine-desc.py`）、语料与基准工具 |
| `TODO.md` `VERSION` | 台账 · 发行版本 | 仓级开放任务台账；`VERSION` 是发行版本的唯一来源 |
:::

:::{figure}
:name: fig-fylite-sdd-components
:align: center

```{mermaid}
flowchart TB
  subgraph H[多宿主 Hosts]
    CLI[命令行 fylite · fylite-app]
    PY[Python 库 DE-COMP-02 · 04]
    APP[浏览器 DE-COMP-05]
    AI[AI 工具面 serve / mcp]
    ENG[执行体 DE-COMP-03]
    DECL[声明面 DE-COMP-06]
  end
  subgraph M[中间层 DE-COMP-09 fylite_runtime]
    DATA[格式 · 装配 · 装置接入 DE-COMP-07]
    CASE[计划 → 门 → 记录]
    SEL[后端表 · 发现与选择]
  end
  subgraph K[内核 DE-COMP-01 — 可替换]
    SO[本地 .so]
    WASM[页内 wasm]
    REMOTE[远端进程]
  end
  FYO[语义层 DE-COMP-08 fyo]
  CLI --> ENG
  AI --> ENG
  PY --> ENG
  ENG --> DECL
  ENG -->|ctypes| M
  APP -->|JS ↔ wasm| M
  M -->|文档门：扁平树| K
  FYO -.声明源在内核，生成物在两侧.-> M
  FYO -.-> H
```

四层：宿主写计划、读记录；中间层合成计划、编成扁平树、选后端、装成记录；内核从树到
树。语义层（DE-COMP-08）横跨——声明源在内核，生成制品被中间层与宿主消费。
★今天的依赖边**多出两条**未画：Python `kernel.py` 与 `app/assets/fylite.js` 仍直接调用
内核的扁平导出（125 / 146 个不同函数，`FYL-DESIGN-16` 实测），它们随分期 P1 消失。
:::

(de-comp-01)=
**DE-COMP-01: 内核（可替换）**（kernel, replaceable）

| Field | Value |
|:---|:---|
| Description | 平衡 / 演化 / 电磁 / 输运与动理学的唯一数值实现，单 crate 同源编译为本机 cdylib 与 wasm 模块；源码在私有仓。对上只经文档门（DE-LOG-11）：一个 code 从树到树。 |
| Traces to | FR-MODEL-001..005, FR-KERNEL-001..004, NR-ENV-003, NR-ENV-004 |
| Invariant | crate 在 `wasm32-unknown-unknown` 目标上**必须 (MUST)** 始终可构建；线程并行仅经特性开关在本机构建启用。**同一物理量只有一个实现在此**；宿主不得转写。内核**禁止 (MUST NOT)** 读文件、开网络、认识数据源头或任何序列化格式，**禁止 (MUST NOT)** 持有全局态（实测 2026-09-04 为零，DE-LOG-12）。 |
| Interface | 文档门 `fylite_rs_fyo`（目标：扁平树双向）；C ABI（`c_api.rs`，442 个导出）与 wasm 导出面是**本地后端的实现细节**，`ABI_VERSION` 只守 C 签名（DE-LOG-02）。 |
| 今天 | 文档门承载 3 个 code（`evolve` `zerod` `transport`），入参按路径、出参 TSV 清单；Python 与页面各绑 125 / 146 个扁平导出。 |

(de-comp-02)=
**DE-COMP-02: Python 装配层**（Python assembly layer）

| Field | Value |
|:---|:---|
| Description | 平铺的装配模块：任务级编排、数据装配（g-file / 装置描述 / 剖面映射）、命名与序列化、判据与报告；数值步一律下沉内核。`io/` 是各数据源的 Python 门面，其中 `fydoc` 是中间层 `.so` 的 ctypes 面（2026-09-04 起 `.h5`、mdsip 在线路径都经它）。 |
| Traces to | FR-ANALYSIS-001..004, FR-PULSE-001..002, FR-OPTIM-001..002, FR-CONTROL-001..002, FR-DATA-002, NR-DEP-001, NR-DEP-002 |
| Invariant | 必需运行时依赖仅 numpy；不导入 `sp` / `fy*`（静态检查守门）。**本层不实现物理与数值**：离散化、闭合、拟合、积分与归一化归 DE-COMP-01；同一物理量的第二份实现即缺陷。 |
| Interface | `fylite.*` 公共模块函数面。 |
| 目标 | `FYL-DESIGN-16` K-3：Miller 度规、抛物剖面、相位表等装配算术成为内核 code 的一部分，本层退成**计划构造器**（H-1）；`kernel.py` 退为本地后端的驱动（D-2）。 |

(de-comp-03)=
**DE-COMP-03: 执行体**（engine）

| Field | Value |
|:---|:---|
| Description | 与物理无关的机械：命令行构建与入口、JSON-RPC / MCP 服务、能力目录与清单校验、运行溯源（`whence`）、底账与重放（`ledger` / `replay`）、报告渲染（`report.py`，统一模板 `docs/reference/report-template.md`）、迭代版本、别名、跨运行时一致性（`crosshost`）、语料与物理校验（`cases` / `physics` / `suite` / `benchmark`）、ABI 核对与原生库装载。 |
| Traces to | FR-TOOL-001..004, FR-DATA-003, NR-DEP-001, NR-ENV-004 |
| Invariant | `fylite.engine` 顶层导入仅标准库；numpy 与重型依赖一律函数内惰性导入（闸子 `test_engine_imports_only_stdlib.py`；`fylite/__init__.py` 为此改为 PEP 562 惰性，`import fylite` 2.7 ms 不加载 numpy）。 |
| Interface | `fylite.engine` 入口（`cli_main` / serve / mcp）。命令行由 DE-COMP-06 的 `_cli.json` 机械建出；`app` / `data` / `case` 三条由**那一个** Rust 可执行文件承载，本层**逐字委托**（`--bin-dir` → 包内 `_bin/` → `$PATH`，命令词放回最前；找不到时按名说明要构建什么并退出 2），不另写第二份实现。 |
| Note | 后端注册（原 DE-LOG-03）已退出本组件。★与中间层的重叠只有四项（命令行解析——有意的两份、内核装载、计划→内核→记录、g-file ↔ `fyo:equilibrium`），重心互不相交（`FYL-DESIGN-16` N-1）。 |

(de-comp-04)=
**DE-COMP-04: 场景层（退役中）**（scenario layer, being retired）

| Field | Value |
|:---|:---|
| Description | 四条场景线（`analysis` / `control` / `design` / `model`）的任务级装配与 `waveform.py`。2026-09-04 起语料与校验四模块已迁入 DE-COMP-03；留下的是 K-3 要搬进内核的装配算术。 |
| Traces to | FR-HOST-001, FR-MODEL-004, FR-ANALYSIS-001, FR-PULSE-001, FR-OPTIM-002, FR-CONTROL-001 |
| Invariant | 场景入口只组合装配层与执行体既有能力，**禁止 (MUST NOT)** 内联新数值实现；**禁止 (MUST NOT)** 新增模块（本层只减不增）。 |
| Interface | `fylite.scenario.<line>.<entry>`。 |
| 目标 | 十个能力工具全部声明 `kernel_entry`，`scenario/` 里 `fylite_rs_*` 归零（`FYL-DESIGN-16` 分期 P1，`vstab` 先）；届时本组件退役、本条留号。 |

(de-comp-05)=
**DE-COMP-05: 浏览器前端**（browser front end）

| Field | Value |
|:---|:---|
| Description | 静态页面与 wasm 制品（制品不入库，构建时装入）；页面控件驱动单步求解并即时回显。同一份页面字节两种交付：静态站点（`tools/build-site.sh`）与单一可执行文件内嵌（`fylite-app`，另答一组只读 `/api/*`）——差别由页面在运行时判别（`assets/host.js` 探 `/api/health`），**禁止 (MUST NOT)** 构建时分叉出两份页面（`FYL-DESIGN-15` R-1 / R-3）。 |
| Traces to | FR-HOST-001, FR-HOST-002, NR-ENV-001, NR-ENV-002 |
| Invariant | 页面仅消费 wasm 模块与静态资产；加载后离线可用（零远程请求依赖）。 |
| Interface | 三个散文页各中英两份（`tools/make-app-pages.mjs` 生成，无 i18n 运行时）；四个功能页 + 一个算例报告页（运行时切换语言）；五张 `page_*` v2 外壳页（`tools/make-page-v2.mjs` 生成，`FYL-DESIGN-11`）。**启动参数**（`device` / `lang` / `theme` / `page`）在共享规格的 `hosts.app.params` 里声明一次（`FYL-DESIGN-15` C-6）。逐页设计：`FYL-DESIGN-09` / `-10` / `-12` / `-13`，外壳 `-11`。 |
| 目标 | `FYL-DESIGN-16` H-2 / H-4：页面经中间层的 wasm 到达内核 wasm，JS 只搬不透明字节；`geqdsk.js` / `fyo.js` / `session.js` 的职责归中间层；`fylite.js` 的 344 处扁平调用随 P1 消失。 |

(de-comp-05-1)=
### DE-COMP-05.1 BYOK LLM 前端（可选部件）

浏览器前端**可以 (MAY)** 携带一个 LLM 前端：读者输入自己的服务端点与密钥，页面据以
规划并指挥 wasm 计算、渲染输出。它是**可选部件**——页面在没有密钥时**必须 (MUST)**
完整可用。约束（判据与实测见 `FYL-REPORT-01` §14）：

1. 密钥**必须 (MUST)** 存于 `sessionStorage`；**禁止 (MUST NOT)** 使用 `document.cookie`
   （cookie 随每一次同源请求自动发出）。升级到 `localStorage` **必须 (MUST)** 由读者
   显式勾选。
2. 密钥**禁止 (MUST NOT)** 进入任何导出物、会话文档、`fylite:` 键、运行记录或控制台。
3. 本前端**禁止 (MUST NOT)** 声称产出**受管工件**：它产不出 `owner` / `tenancy_scope` /
   `signature`，产出**必须 (MUST)** 标注为自描述文档且「未经提升」（与 `session.js`
   的裁定同一条）。
4. LLM **禁止 (MUST NOT)** 执行生成的代码：它只**规划**，调用面限于已声明的固定入口。
   这条是本前端安全论证的正身。
5. 站点发布于共享 origin（`fusion-yun.github.io/fylite/`）而浏览器存储按 origin 隔离：
   密钥输入处**必须 (MUST)** 告知这一点，或站点迁至独立 origin。

(de-comp-05-2)=
### DE-COMP-05.2 LLM 位置纪律（跨宿主）

6. LLM 的合法位置仅两个：**外部宿主**（经 DE-LOG-06 的能力目录调用，主形态）与
   **页内 BYOK**（DE-COMP-05.1，可选）。二者读同一套声明面。
7. 任一位置：LLM **禁止 (MUST NOT)** 执行其生成的代码，**禁止 (MUST NOT)** 产出进入
   计算路径或数据产物的数值。LLM 的合法产出只有三类：**调用**（对已声明入口）、
   **文档**（fyo 文档与工作流草案，一律未提升）、**文字**——与「宁可拒绝，不给假数」
   同源。
8. LLM 会话产出的工作流草案与浏览器会话文档**同级**：自描述、未经有身份宿主的人审提升
   不得当作已注册流程。

(de-comp-06)=
**DE-COMP-06: 声明面**（declaration plane）

| Field | Value |
|:---|:---|
| Description | 能力清单（撰写源）、vendored 交换 schema、命令行规格、环境变量表、fyo 词表——数据而非代码，随 wheel 分发；能力条目携预期响应时间预算声明。`_cli.json`（`spec_version: 2`）是**三个宿主共同的**命令行定义：Python 由它建 argparse、Rust 可执行文件在编译期 `include_str!` 纳入、浏览器读 `hosts.app.params`；只属一个宿主的命令或参数以 `hosts` 标出（`FYL-DESIGN-15` C-1 / C-2）。 |
| Traces to | FR-TOOL-001, FR-TOOL-002, FR-TOOL-004, FR-MODEL-005, NR-ENV-005 |
| Invariant | 能力目录**必须 (MUST)** 自清单文件派生；派生目录**禁止 (MUST NOT)** 落盘提交；vendored schema **禁止 (MUST NOT)** 本地改写。命令行**必须 (MUST)** 只有这一份声明式定义（`FYL-DESIGN-15` C-1 / C-3）。 |
| Interface | 清单文件集（JSON 系）+ 执行体的目录派生函数。 |
| 目标 | `FYL-DESIGN-16` K-2 / K-4：后端表与 code 表加入声明面；能力目录按后端覆盖（原「按 `kernel_id` 覆盖两宿主」的 A-2 口径由此承接）。 |

(de-comp-07)=
**DE-COMP-07: 装置接入**（device access）

| Field | Value |
|:---|:---|
| Description | 装置描述的读法与定位：`app/devices/{catalogue,east,iter}.jsonld` 是自外部 A-Box 誊录的**实拷**（不再是符号链接——分仓后链接指向另一个仓，克隆即断链）；Python 侧 `device.py` 合「牌在哪」与「牌说什么」为一个模块。 |
| Traces to | FR-DATA-001 |
| Invariant | 实验数据不入仓不随包；装置描述的**权威值在 A-Box**，本仓誊录不手改（订正方向是 A-Box → 本仓）；测试基准仅用内核自产合成算例。 |
| Interface | 环境变量 / 显式路径 / 页面目录 → `fyo:DeviceDescription` 文档。 |
| 目标 | `FYL-DESIGN-16` K-8：中间层读 A-Box（`assembly::from_manifest` 已在做）装成完整文档随计划交给内核；内核不认识数据源头。 |

(de-comp-08)=
**DE-COMP-08: 语义层（fyo，跨宿主逻辑组件）**

唯一不映射到单一目录的组件——按语义归属划分，不改 {numref}`tbl-fylite-sdd-layout`
的目录指派：

| 成员 | 角色 |
| :--- | :--- |
| 内核仓 `rust/fylite/src/fyo.rs` 的 `@fyo-table` / `@fyo-block` / `@fyo-entry` 注记 + `python/fylite/_fyo_vocab.json` | **声明源**（语义只声明一次，DE-LOG-07） |
| `python/fylite/_fyo_interface.py` · `app/assets/fyo-interface.js` · 中间层 `fyo_interface.rs` 所读的同一份 | **生成制品**（内核仓构建产出；禁改） |
| `python/fylite/fyo.py` · `app/assets/fyo.js` · 中间层 `fyodoc.rs` | **宿主门面**（手写部分受 DE-LOG-07 棘轮约束） |

★`FYL-DESIGN-16` H-4 之后 `fyo.js` 的职责归中间层的 wasm；生成物留着。五层视图
（`FYL-REPORT-03` §2）在组件上的落点：L0=DE-COMP-01，**L1=DE-COMP-08**，L2=DE-COMP-06，
L3=DE-COMP-03 的记录半边，L4=DE-COMP-05 与 DE-COMP-03 的 CLI / MCP 面。

(de-comp-09)=
**DE-COMP-09: 中间层**（middle layer, `fylite_runtime`）

| Field | Value |
|:---|:---|
| Description | 六件事：①格式读写与转换（MDSplus 只读、a-file、g-file、JSON(-LD)、HDF5、netCDF、YAML 子集，各带 fyo 与 IMAS DD 两种布局）；②多源装配（`assembly`，按 JSON-LD / YAML，按炮号与时间的服务端切片）；③计划合成与绑定 → 门 → 记录（`case.rs`）；④内核的加载与选择（`kernel.rs`，dlopen）；⑤Rust 宿主的全部命令行（`src/cli/`）；⑥内嵌并伺服 `app/`（`src/bin/app/`，含只读 mdsip 请求面 `api.rs`）。①②是数据层（`FYL-DESIGN-14`），⑤⑥见 `FYL-DESIGN-15`，③④见 `FYL-DESIGN-16`。**SpData 的一个 profile**（D-1）。 |
| Traces to | FR-DATA-001..002, FR-TOOL-001, FR-TOOL-004, FR-KERNEL-001..003 |
| Invariant | **禁止 (MUST NOT)** 实现任何物理或数值（判据同 DE-COMP-02）；对 MDSplus **必须 (MUST)** 只读且**禁止 (MUST NOT)** 暴露取表达式的入口（每个 TDI 串由校验过的节点路径与整数拼出）；浏览器制品**禁止 (MUST NOT)** 含 mdsip、hdf5、netcdf（`--no-default-features`）；携带内核状态时**禁止 (MUST NOT)** 解释或编辑它（DE-LOG-12）。 |
| Interface | `libfylite_runtime.so` 的 C ABI（`fylite_runtime_*`，31 个；Python 侧 `fylite.io.fydoc`）；`fylite-app`（命令词 `app` / `data` / `case`）；`fylite_runtime.wasm`（裁定，未建）。 |
| 今天 / 目标 | 今天：dlopen 一个内核、`fylite_rs_fyo` 三元组入参、TSV 出参、`Outcome::parse` + `documents()` 按路径建树。目标（DE-LOG-11）：扁平树编码器 / 解码器各一份，后端表三种后端，wasm 上由 JS 接线两个模块。 |

(fylite-sdd-composition-invariants)=
## 分层不变式 (Layering Invariants)

1. 源文件**必须 (MUST)** 落在 {numref}`tbl-fylite-sdd-layout` 指派的目录；仓根不放
   源文件与测试。
2. 依赖方向**必须 (MUST)** 遵循 {numref}`fig-fylite-sdd-components`；浏览器前端
   **禁止 (MUST NOT)** 依赖 Python 宿主。
3. 每个 Python 源模块在 `python/tests/test_<module>.py` 有镜像测试模块；页面台账由
   `app/tests/` 门禁核对。
4. 本视图与 `.context/PROJECT.md` 源布局节**必须 (MUST)** 同批变更。
5. 〔目标态，`FYL-DESIGN-16` K-1〕宿主代码（`scenario/`、页面 JS）**禁止 (MUST NOT)**
   出现 `fylite_rs_*` 符号名；判据是 `test_no_bare_kernel_aliases.py` 的思路推广一层。
   今天不成立（125 / 146 个调用点），随分期 P1 生效。

(fylite-sdd-logical)=
# 逻辑视图 (Logical View)

(de-log-01)=
**DE-LOG-01: 一份内核契约，多宿主**（one contract, many hosts）

| Field | Value |
|:---|:---|
| Description | 命令行、Python 库、浏览器页面、AI 工具面对内核说同一种话——一份 fyo 计划进、一份 fyo 记录出；内核可以是本地 `.so`、页内 wasm、远端进程或另一种实现。本机与浏览器两个运行时的数值一致性由 V&V 登记册的一类记录承载（`fyo:ComparisonRecord`，`engine.crosshost`）。 |
| Traces to | NR-ENV-004, FR-HOST-001, FR-HOST-003, FR-KERNEL-001 |
| Invariant | 任一在两个运行时可用的数值内核**必须 (MUST)** 只有 Rust 一份实现；**禁止 (MUST NOT)** 在 JS / Python 各写一份。新增宿主**禁止 (MUST NOT)** 改变契约。 |
| Interface | 文档门（DE-LOG-11）；本地后端的装载器（执行体 / 中间层）与页面的 wasm 装载。 |
| 今天 | `crosshost` 比的是同一内核的两个构建，只对声明了 `kernel_entry` 的一个工具运行；推广后比任意两个后端上的同一 code（`FYL-DESIGN-16` K-6）。 |

(de-log-02)=
**DE-LOG-02: ABI 单源（本地后端内部）**（single-source ABI）

| Field | Value |
|:---|:---|
| Description | ABI 版本与导出签名单点定义于内核 C ABI 源，构建脚本生成 Python 侧常量；本地 `.so` 装载时核对版本。★`FYL-DESIGN-16` K-2 之后它守的是 C 签名——**本地后端内部**的事，不再是宿主判断「能不能调」的依据。 |
| Traces to | NR-ENV-004, NR-QUAL-002 |
| Invariant | ABI 版本常量**必须 (MUST)** 恰有一处手写源；消费侧文件全部为生成物（禁手改）。 |
| Interface | 生成的 ABI 常量模块 + 装载时版本核对。 |

(de-log-03)=
**DE-LOG-03: 后端注册表 — 已退役 2026-08-21**

可换实现由调用方直接构造并以对象传入（`self_consistent(current_source=…, …)`）。退役
理由四条，逐条可核：它并不实现所追溯的 FR-MODEL-005（闭包档位由内核
`TRANSPORT_MODELS` 按名选取）；十个内建项里六个不是模型；两个消费者仍按名字分支；
扩展点无人使用（`register_backend` 全树只有测试调用）。本条留号。

(de-log-04)=
**DE-LOG-04: 交互 / 批式分档**（interactive / batch tiering）

| Field | Value |
|:---|:---|
| Description | 单步求解走同步调用即时回显（响应以该功能声明的预算为判）；多步外环以显式步进接口暴露，可中断、可续跑。★与 DE-LOG-12 同一机制：步进的状态就是随记录走的那棵子树。 |
| Traces to | FR-HOST-002, NR-ENV-002, NR-ENV-005 |
| Invariant | 批式任务**禁止 (MUST NOT)** 占用同步工具槽或以单次交互操作形式呈现。 |
| Interface | 步进式循环入口 + 页面 / CLI 的进度回显。 |

(de-log-05)=
**DE-LOG-05: 运行清单发射**（run-manifest emission）

| Field | Value |
|:---|:---|
| Description | 每次求解运行发射机器可读运行记录：输入来源、参数、软件与后端版本、环境指纹、产物指纹。 |
| Traces to | FR-DATA-003, FR-KERNEL-003 |
| Invariant | 运行记录由执行体 / 中间层统一发射；求解路径**禁止 (MUST NOT)** 各自拼装记录格式；记录**必须 (MUST)** 写明产生它的后端（K-7）。 |
| Interface | 溯源模块 → 运行清单（JSON-LD）。 |

(de-log-06)=
**DE-LOG-06: 能力目录反射**（capability-catalog reflection）

| Field | Value |
|:---|:---|
| Description | 声明面清单派生唯一能力目录；CLI describe、JSON-RPC、MCP 与 LLM 工具 schema 全部反射该目录——AI 工具面（FR-HOST-003）由此承载。 |
| Traces to | FR-TOOL-002, FR-TOOL-003, FR-HOST-003 |
| Invariant | 全部工具面共享同一执行路径；**禁止 (MUST NOT)** 为任一工具面另设执行通道或手抄目录。 |
| Interface | 目录派生函数 → describe / serve / mcp / 工具 schema 发射。 |

(de-log-07)=
**DE-LOG-07: 语义单源**（semantic single source）

| Field | Value |
|:---|:---|
| Description | 共享语义——文档表 / 打包块 / 场景入口 / 词汇——在内核仓 `fyo.rs` 注记与 `_fyo_vocab.json` 里**声明一次**，构建生成各宿主制品；宿主的语义面读生成物，不各写一遍。依据：`FYL-REPORT-02` 实测两宿主手写语义面 41 : 13 且已双写装配 14k 行。 |
| Traces to | FR-HOST-003, FR-DATA-002 |
| Invariant | 新增共享语义**必须 (MUST)** 走表化声明；宿主门面（`fyo.py` / `fyo.js` / `fyodoc.rs`）的手写语义**只减不增**（棘轮）；生成制品**禁止 (MUST NOT)** 手改。判据：两运行时对同一份文档取同一槽，结果逐位相同（生成半边有闸子 `test_fyo_vocabulary` / `test_fyo_interface`；逐位相同那一条随 DE-LOG-11 的往返闸落）。 |
| Interface | `@fyo-table` / `@fyo-block` / `@fyo-entry` 注记 + `_fyo_vocab.json` → 构建 → `_fyo_interface.py` / `fyo-interface.js` / `fyo-interface.json`。 |

(de-log-11)=
**DE-LOG-11: 文档门与扁平树**（the document door, a flat tree both ways）〔目标态〕

| Field | Value |
|:---|:---|
| Description | 内核唯一的接口是一扇门：code + 按名设置 + 一棵扁平树进，一棵扁平树出。树是四段缓冲（先序节点表 · 名字块 · 8 字节对齐的 f64 载荷 · 整数 / 字符串载荷），索引相连、不解析；中间层编码 / 解码各一份，内核阅读器 / 构建器各一份；进门校验一次。装置文档、剖面、状态都是树上的枝。正本 `FYL-DESIGN-16` K-1 / K-2 / K-8 / F-1..F-4。 |
| Traces to | FR-KERNEL-001, FR-KERNEL-002, NR-ENV-004 |
| Invariant | 内核**禁止 (MUST NOT)** 收路径字符串、**禁止 (MUST NOT)** 自带序列化格式的解析器；对缺失的槽按名拒绝并一次列全；未声明的键**看得见但不取数**。中间层**禁止 (MUST NOT)** 为文档门另立第二种入参形状。 |
| Interface | 内核 `fylite_rs_fyo`（新形）；中间层 `case.rs`；wasm 上两个模块由 JS 搬不透明字节（H-5）。 |
| 今天 | 入参 `(路径, 维数, 数值)` 三元组、出参 TSV 清单；实测两份文档同名收尾的路径会静默并成一条（`rc=0`）。分期 T-1..T-4（`FYL-DESIGN-16` §分期），T-1 必须在 P1 之前。 |

(de-log-12)=
**DE-LOG-12: 内核无状态，状态在文档里**（stateless kernel, state travels）〔目标态〕

| Field | Value |
|:---|:---|
| Description | 内核不持有状态；续跑所需的状态是文档里一棵声明过的子树（`fylite:state`），随计划进、随记录出，带写它的内核的身份。单步 / 多步是计划的选择；补数据再入、断点续跑、取消、从中间复算共用这一个机制。管理拆五件：声明与产生归内核、携带归中间层、持久化与决定归各宿主。正本 `FYL-DESIGN-16` S-1..S-6 / B-1..B-4。 |
| Traces to | FR-KERNEL-004, FR-HOST-002, FR-DATA-003 |
| Invariant | 内核**禁止 (MUST NOT)** 留住状态（可分配、可交出）；**必须 (MUST)** 在每个步界能停并交出完整状态；中间层**只搬不改**；内核对认不出的状态按名拒绝，除非显式允许漂移（先例 `engine/replay.py` 的 `allow_version_drift`）。门上**没有回调**。 |
| Interface | `fylite:state` 子树；门的「只问不算」相（B-1，`case describe` / `plan` 已有半条）。 |
| 今天 | 内核全局态实测为零；跨调用状态只在 `evolve_heat`，以二十个成对的 `*_in` / `*_out` 槽传（状态 2.5–7.9 KiB）；持久化已分散在 Python `engine`（holder / `restart` / `handles` / `versioning` / `ledger`）与浏览器（四处 `localStorage`）。 |

(fylite-sdd-interface)=
# 接口视图 (Interface View)

外部接口以 `FYL-SRS-01` §外部接口为准。内部接口按四层分三段，「今天」与「目标」
分列——目标态的出处都在 `FYL-DESIGN-16`：

| 内部接口 | 今天（2026-09-04） | 目标 | 稳定性 / 闸子 |
| :--- | :--- | :--- | :--- |
| 宿主 ↔ 执行体 ↔ 中间层（Python） | `fylite.io.fydoc` 经 ctypes 取 `libfylite_runtime.so`（31 个 `fylite_runtime_*`） | 不变；执行体另经中间层选后端（D-2） | C 导出随中间层演进；`test_fyo_interface.py` 对拍 g-file ↔ `fyo:equilibrium` |
| 宿主 ↔ 中间层（浏览器） | **没有**：JS 直接调内核 wasm 的扁平导出（`fylite.js` 344 处）；`geqdsk.js` / `fyo.js` / `session.js` 各自实现 | JS 取 `fylite_runtime.wasm`，中间层建好扁平树，JS 把字节递给内核 wasm（H-4 / H-5） | 随 W-1 |
| 中间层 ↔ 内核（本地） | dlopen `libfylite_kernel.so`；`fylite_rs_fyo` 三元组入、TSV 出；Python `kernel.py` 另绑 125 个扁平导出（442 个签名） | 一扇门、两个方向都是扁平树（DE-LOG-11）；扁平导出降为内部 | ABI 号只守 C 签名（DE-LOG-02）；往返闸（T-1） |
| 中间层 ↔ 内核（远端） | 无远端内核（`serve` / `mcp` 与 `/api/*` 暴露的是远端 **fylite**，非内核） | 共形 `SPM-ADR-111` 六相的 JSON-RPC 端点 `/api/case`，登记在后端表（K-4 / K-5） | 随 P2；envelope 与 `SP-REPORT-15` T-0.4 一并定 |
| 后端 ↔ 能力目录 | native 17 件已入目录；wasm 侧靠生成的 `fyo-interface.js` | 每个后端自报 code 表（K-2）；中间层在 wasm 上像本机一样问内核要（G-5 随 W-1 关） | 随 P2 |
| 三宿主 ↔ 命令行规格 | 一份 `_cli.json`：Python 建 argparse、Rust 编译期 `include_str!`、浏览器读 `hosts.app.params`；宿主特有项以 `hosts` 标出 | 不变 | `test_cli_spec.py` 与 `cargo test cli::` |
| 浏览器 ↔ LLM 服务（可选） | 读者自带端点与密钥；请求由页面发起，**不经本仓任何服务端** | 不变 | 本仓不承诺 |

跨接口数据**必须 (MUST)** 为平面显式形（扁平树、数组 + 长度、序列化消息）；panic /
异常**禁止 (MUST NOT)** 穿越宿主边界（在边界处映射为错误码或宿主异常）。

(fylite-sdd-behavior)=
# 行为视图 (Behavioral View)

- **交互求解循环**：宿主入口（页面控件 / CLI / 场景入口）→ 计划（宿主写）→ 合成与绑定
  （中间层）→ 门 → 内核从树到树 → 记录（中间层装）→ 宿主呈现。受 NR-ENV-002 与
  NR-ENV-005 约束，实测以预算为判。★今天 Python 与页面绕过中间层直接调扁平导出，
  循环的形状一样，只是门还不是唯一的。
- **门的相**（目标，DE-LOG-11 / -12）：**只问不算**（给定 code 与设置，内核答它将要
  什么）→ 绑定 → 算 → 交回记录与状态；要的东西不在场时**按名拒绝并一次列全**，补齐后
  带着已建好的树再入。一次调用的输入集在开始时就定死——没有惰性取数、没有回调。
- **批式外环**：外环以步为单位推进；步间可中断、状态可续（状态就是记录里那棵子树）；
  取消＝把步数预算切小，在两次调用之间决定；进度对用户可见（DE-LOG-04）。
- **运行落档**：任一求解完成即经 DE-LOG-05 发射运行清单，写明后端与环境指纹；产物
  （g-file、图件）与清单互相指认。
- **能力自述**：集成方经 describe / JSON-RPC / MCP 查询能力目录（DE-LOG-06），再按
  目录发起调用——查询与调用共享同一目录与执行路径；后端按 code 表被选中（K-4），
  不在场就说不在场。

(fylite-sdd-trace)=
# 追溯矩阵 (Traceability Matrix)

:::{table} SDD 设计元素 → SRS 需求追溯。
:name: tbl-fylite-sdd-trace
:align: left

| SDD Design Element | SRS Requirement |
|:---|:---|
| DE-COMP-01 | FR-MODEL-001..005, FR-KERNEL-001..004, NR-ENV-003, NR-ENV-004 |
| DE-COMP-02 | FR-ANALYSIS-001..004, FR-PULSE-001..002, FR-OPTIM-001..002, FR-CONTROL-001..002, FR-DATA-002, NR-DEP-001..002 |
| DE-COMP-03 | FR-TOOL-001..004, FR-DATA-003, NR-DEP-001, NR-ENV-004 |
| DE-COMP-04（退役中） | FR-HOST-001, FR-MODEL-004, FR-ANALYSIS-001, FR-PULSE-001, FR-OPTIM-002, FR-CONTROL-001 |
| DE-COMP-05 | FR-HOST-001..002, NR-ENV-001..002 |
| DE-COMP-06 | FR-TOOL-001..002, FR-TOOL-004, FR-MODEL-005, NR-ENV-005 |
| DE-COMP-07 | FR-DATA-001 |
| DE-COMP-08 | FR-HOST-003, FR-DATA-002 |
| DE-COMP-09 | FR-DATA-001..002, FR-TOOL-001, FR-TOOL-004, FR-KERNEL-001..003 |
| DE-LOG-01 | NR-ENV-004, FR-HOST-001, FR-HOST-003, FR-KERNEL-001 |
| DE-LOG-02 | NR-ENV-004, NR-QUAL-002 |
| DE-LOG-03（已退役） | FR-MODEL-005（由 DE-COMP-01 的 `TRANSPORT_MODELS` 按名选取满足） |
| DE-LOG-04 | FR-HOST-002, NR-ENV-002, NR-ENV-005 |
| DE-LOG-05 | FR-DATA-003, FR-KERNEL-003 |
| DE-LOG-06 | FR-TOOL-002, FR-TOOL-003, FR-HOST-003 |
| DE-LOG-07 | FR-HOST-003, FR-DATA-002 |
| DE-LOG-11（目标态） | FR-KERNEL-001, FR-KERNEL-002, NR-ENV-004 |
| DE-LOG-12（目标态） | FR-KERNEL-004, FR-HOST-002, FR-DATA-003 |
:::
