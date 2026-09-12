---
document_id: FYL-DESIGN-22
title: "总体设计逻辑原则与共性功能 (Design Principles and the Common Functions)"
shortname: fylite-design-overview
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
  change: 'v0.1（全新文档，设计书重组第一部）：用户指示 2026-09-12「fylite 设计文档重组：先阐述
    总体设计逻辑原则和 common 功能描述；然后具体功能线按场景重新整理划分」。本篇是第一部的
    正文：十二条逻辑原则（各指向它的正本与实测出处）、八项共性功能 × 四个宿主的一张表、
    共享的六个文档种类、六层合成与七值状态机。**不新增裁定**——原则与功能的正本仍在
    `FYL-CONOPS-00` / `FYL-DESIGN-16` / `-17` / `-18` 等篇；本篇裁定的只是设计书的**读法**
    （T-1..T-4）。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-design-overview

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-22` |
| 文档名称 (Title) | 总体设计逻辑原则与共性功能 |
| 短名 / Slug | `fylite-design-overview` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；原则的正本在 `FYL-CONOPS-00`，规范条款在 `FYL-SRS-01` / `FYL-SDD-01`） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | new project members / physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 用户指示 2026-09-12（设计书重组）· `FYL-CONOPS-00` v1.2（建设原则六条 · 包络四条 · 场景 S-L1..S-L5 · 用户级别）· `FYL-DESIGN-16` v3.0（K-1..K-11 · S-1..S-6 · H-1..H-8）· `FYL-DESIGN-17` v1.4（E-10..E-21）· `FYL-DESIGN-18` v1.6（U-1..U-26）· `FYL-REPORT-07`（八项通用功能的评估与 §8 界限）· 内核仓 `FYL-REPORT-04` / `-08` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本篇 `T-` 裁定在本篇内唯一。凡引「`-16`」等者指本书同目录的 `FYL-DESIGN-16`。

(fylite-design-overview-abstract)=
# 摘要 (Abstract)

〔一句话〕**fylite 是一份内核、一套文档协议、四个宿主：宿主只写一份计划、只读一份记录，
内核在文档门后算数；场景是计划的形状，页面与命令行是计划的两个投影。**

本篇是重组后设计书的**第一部**：先说**逻辑原则**（十二条，各指向正本与实测出处），再说
**共性功能**（编辑 · 可视化 · 执行 · 状态追踪 · 导入 · 导出 · 断点恢复 · 溯源，八项 × 四宿主），
以及所有场景共享的**六种文档**与**一套合成规则**。第二部（`FYL-DESIGN-23` 起）按**场景**
划分功能线，每章四件必备：物理算法流程图 · 命令面（CLI / MCP / Python）· 界面效果图 · 判据。

**T-1 设计书分两部，读法固定。** 第一部说"所有场景共有的"，第二部说"这个场景独有的"；
一条规矩若在两部都出现，第一部是正本、第二部只引用。〔用户指示 2026-09-12〕

**T-2 重组不动正本。** 既有各篇（`-09`..`-21`）的编号裁定（`K-` · `S-` · `E-` · `U-` · `P-` · `Q-` …）
在闸子与提交信息里被按号引用，**一条不搬、一号不改**；场景章是它们的**投影**，
两处不一致时以正本为准。

(fylite-design-overview-principles)=
# 一 · 逻辑原则 (The Principles)

〔已确立〕十二条。前六条是 `FYL-CONOPS-00` 的建设原则（用户裁定 2026-08-30，评估依据
内核仓 `FYL-REPORT-04`），后六条是此后逐条落成规矩的架构裁定。每条给**它在制品里可判的形**。

:::{table} 逻辑原则：一句话 · 可判的形 · 正本。
:name: tbl-t22-principles
:align: left

| # | 原则 | 在制品里可判的形 | 正本 |
| :--- | :--- | :--- | :--- |
| 1 | **公开文献 + 公开代码** | 每个移植的物理模块有 vendored 参考实现同甲板同跑（神谕树 `tests/oracles/`，只作裁判、不进发行制品） | `FYL-CONOPS-00` 原则 1 |
| 2 | **一个功能一套框架实现；模型以档位并存** | 闭包 `constant` / `stiff` / `neoclassical` / TGLF 是一个参数的取值，不是四个插件 | 原则 2 |
| 3 | **不做插件机制** | 内核无注册表；能力由声明的 code 表（35 code · 617 参数）回答，宿主按表选、按名拒 | 原则 3 · `-16` K-2 |
| 4 | **统一内核，放弃多源集成** | 一份 `c_api.rs` 出 native 与 wasm；对拍基础设施（参考数据 · 冻结甲板 · 双边裁判）是一等资产 | 原则 4 |
| 5 | **Rust 内核，薄前端** | 宿主只写一份 fyo 计划、只读一份记录；装配算术归内核；Python 必需依赖仅 numpy | 原则 5 · `-16` K-3 / H-1 |
| 6 | **完备的约化模型内核；HPC 码消费其产物、不吞并本体** | 范围三层：可白盒移植 / 约化进内核 / 消费不吞并 | 原则 6 · `FYL-REPORT-04` §4 |
| 7 | **文档门是唯一的内核接口** | 两个宿主到内核只有 `fylite_rs_fyo_tree` 一条路；扁平门上物理算子 = 0（棘轮只准变窄） | `-16` K-1 · 内核仓 `seam.rs` |
| 8 | **内核无状态；状态随文档走** | 一次调用一次运行，无句柄；中间态是记录里的 `fylite:state`；续跑 = 再入 | `-16` S-1..S-6 |
| 9 | **声明驱动，生成不手抄** | 17 表 · 35 code · 5 条目向四个消费者生成同一批名字，带 `revision` / `digest`；控件由词表生成 | `-16` K-2 · `-18` U-1 · `FYL-ABI-01` |
| 10 | **只写量得出的** | 每项保真度声明附零假设与残余归因；不确定的值写 `[TBD]`；参照量级不当本仓阈值 | `FYL-CONOPS-00` 〈保真度〉· `-21` §八 |
| 11 | **fylite 是封闭的参照实现，fytok 是开放的集成者** | 同一 fyo 协议；fylite 不做工作流引擎 / DAG / 分布式 / 服务端；收外部码的产物、不调外部程序 | `FYL-REPORT-07` §8 |
| 12 | **三级用户按"改动计划的哪一层"分** | L1 只选（预设 · 炮号 · 时刻）· L2 改模型档位与精细参数 · L3 定义场景 / 接入外部；级别是标签不是权限 | `FYL-CONOPS-00` 〈用户级别〉· `FYL-SRS-01` FR-LEVEL |
:::

〔判读〕十二条不是并列的，它们有**一条依赖链**：7（文档门）使 8（无状态）可判，8 使 4 的
"一份内核三种形"成立，9 使 3（不做插件）不牺牲能力，10 与 1 是同一件事的两面，
11 与 12 划定谁来改什么。抽掉 7，其余多数退化为口号。

**包络四条**（`FYL-SRS-01` NR-ENV）：单机 · 交互档毫秒至秒量级（按功能声明预算）· 有限多线程 ·
跨平台（本机 + 浏览器）。**禁止**依赖分布式运行时或必需的服务端组件。

(fylite-design-overview-common)=
# 二 · 共性功能 (The Common Functions)

〔已确立·`FYL-REPORT-07` 评估过的八项〕每一项对四个宿主给**同一种形**——差别只在谁写计划、
谁读记录。表中"正本"列是规矩所在；本篇只做一张总表。

:::{table} 八项共性功能 × 四个宿主。✓ 落地 · ◐ 部分 · ✗ 缺。
:name: tbl-t22-common
:align: left

| 功能 | 形态（所有场景同一） | CLI `fy` | Python | 浏览器 | MCP / JSON-RPC | 正本 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **编辑** | 计划是六层合成：模板 → 装置 → 预设 → `--plan` → 命令行 → 端口绑定，逐值记来源（E-13）；页面的控件由词表生成（U-1） | ✓ | ✓ | ✓ | ◐（`fylite_run` 收的是旧形参数，不是计划） | `-17` E-11..E-14 · `-18` U-1..U-3 |
| **可视化** | 呈现规格（`spo:PresentationSpecification`）只声明不计算；两端同一规则推出（`casereport.py` ≡ `casereport.js`） | ✓（`--report`） | ✓ | ✓ | ◐（`fylite_plot` 只画 g-file） | `-18` U-12..U-17 · 内核仓 `FYL-REPORT-06` §13 |
| **执行** | 一步 / 一案：一次门调用；多步是一串门调用，步预算是计划字段，进度按步实测（U-8） | ✓ | ✓ | ◐（`run.js` 已装载，页面尚不产记录） | ✓ | `-16` K-1 / S-3 · `-18` U-8..U-9 |
| **状态追踪** | 记录的 `run_state` 七值（submitted · validating · running · succeeded · failed · rejected · cancelled）+ `refusal.stage`；`cancelled` 今天无产者 | ◐ | ◐ | ◐ | ◐ | `FYL-REPORT-07` R-3 · `PLAN.md` G-3 |
| **导入** | 文件端点（7 种格式，按内容认不按扩展名）· mdsip 只读 · A-Box 语料 · 记录作为源（源栈） | ✓ | ✓ | ✓（h5wasm） | ◐ | `-14` L-1..L-12 · `-18` U-4..U-7 · U-25 |
| **导出** | 记录目录（`record.jsonld` + `plan.jsonld` + `<ids>.fyo.jsonld`）；IMAS HDF5 / netCDF 经数据层；浏览器的文档集 zip | ✓ | ✓ | ✓ | ◐ | `-17` E-19 · `-18` U-18 |
| **断点恢复** | 断点**就是**一份记录（`fylite:state`）；`--resume-from` 再入；内核身份不符则拒绝 | ✓ | ✓（只读） | ◐ | ✗ | `-16` S-2..S-6 · `-18` U-10..U-11 |
| **溯源** | 记录带 `executed_code`（内核 sha256）· `environment` · 逐端口校验和 · 每值来源；`fylite:` 词有共享词表 | ✓ | ✓ | ✓ | ◐ | `-16` K-7 · `FYL-REPORT-06` §8 |
:::

**T-3 共性功能的正本只有一处，场景章不得重述其机制。** 一章若需要说"这一步怎么续跑"，
它写的是**这个场景的断点落在哪个步界**，而不是断点机制本身。

(fylite-design-overview-documents)=
## 六种共享文档 (The Six Shared Document Kinds)

〔已确立〕所有场景、所有宿主之间交换的只有这六种（都是 fyo / spo 的实例，JSON-LD 紧凑形）：

| 种类 | 类 | 谁写 | 谁读 |
| :--- | :--- | :--- | :--- |
| **计划** | `fyo:ScenarioSpecification`（⊑ `spo:ComputationPlan`） | 宿主（六层合成） | 中间层 → 内核门 |
| **记录** | `spo:ComputationRecord`（含 `fylite:state` · `run_state` · `environment`） | 中间层 | 宿主 · 报告 · 下一次运行（`x+run://`） |
| **数据集** | `fyo:<ids>` 文档（IMAS DD 布局）· `spo:Concretization` 指向 | 内核经中间层 | 宿主 · 外部工作流（IMAS HDF5） |
| **装置文档** | `fyo:DeviceDescription`（A-Box 生成，随二进制内嵌） | fydoc（生成） | 计划的 `device` 端口 |
| **呈现规格** | `spo:PresentationSpecification` | 由计划 + 记录推出，或场景自带 | 报告与页面 |
| **断点** | 就是一份**记录**（不是第七种） | 中间层 | `--resume-from` |

(fylite-design-overview-hosts)=
# 三 · 四个宿主一份内核 (Four Hosts, One Kernel)

| 宿主 | 内核的形 | 谁写计划 | 谁读记录 | 正本 |
| :--- | :--- | :--- | :--- | :--- |
| `fy`（单一可执行文件：`app` · `data` · `run` · `list`） | 静态库链进 | 命令行的六层合成 | 记录目录 | `-15` R-1..R-6 · `-17` E-10 |
| Python 库（`fylite`） | `.so`（两份：核心 + 扩展） | `S.<line>.<scenario>(...)` 或 `fydoc.case_json(plan)` | dict / 文件 | `-16` H-3 |
| 浏览器（静态站点 / 桌面查看器） | 页内 wasm / 本进程 `/api/kernel` | 表单（词表生成） | 报告页 · 工作台 | `-11` · `-18` · `-16` H-2 / H-6 |
| MCP / JSON-RPC（`fylite.engine.serve`） | 经 Python | 工具参数 | 摘要 + 句柄（`fylite://<run>/<port>`） | 内核仓 `FYL-REPORT-01` / `-03` |

★**四个宿主的差别只在端点能力**（浏览器解析不了 `mdsplus://`），不在计划的形状。

(fylite-design-overview-template)=
# 四 · 第二部每章的四件必备 (What Every Scenario Chapter Carries)

**T-4 场景章的形固定。** 每章按 `FYL-DESIGN-23` 的模板写，四件必备：
① **物理算法流程图**（SVG，节点是步、边是端口绑定、判据挂节点、缺的步画成关着的）；
② **命令面**（CLI / MCP / Python 三种写法**对同一份计划**，实测过的命令原样贴）；
③ **界面效果图**（SVG，概念图，数值示意）；④ **判据与验收**（各层判据落到 fyo 的哪个类）。
可选：数据流表、三级用户各改什么、缺口。**样板**是 `FYL-DESIGN-24`（动理学平衡重构）。

(fylite-design-overview-trace)=
# 五 · 追溯 (Traceability)

| 本篇 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 | `FYL-CONOPS-00` 原则六条 · `-16` K / S · `FYL-REPORT-07` §8 · 用户级别 | `FYL-DESIGN-23` 总目录 |
| §二 · §六种文档 | `FYL-REPORT-07` §1–§4 · `-17` E-13 · `-18` U-1 / U-8 / U-18 · `-16` S-4 | 各场景章只引用不重述（T-3） |
| §三 | `-15` · `-16` H-2 / H-3 / H-6 · 内核仓 `FYL-REPORT-08` §2.1 | — |
| §四 | 用户指示 2026-09-12 | `FYL-DESIGN-23` 模板 · `FYL-DESIGN-24` 样板 |
