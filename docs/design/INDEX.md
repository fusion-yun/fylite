---
document_id: FYL-DESIGN-00
title: 设计书目录 (Design Book Index)
shortname: fylite-design-index
version: "5.5"
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
    v5.5 `FYL-DESIGN-14` 升 v1.3（imas-python 的 documentation 警告＝L-4「一个字不抄」的影子）。
    v5.4 `FYL-DESIGN-14` 升 v1.2（L-13 搬家表；G-10 关闭）。
    v5.3 `FYL-DESIGN-14` 升 v1.1（G-10：wall 转 IMAS 出空件）；`FYL-SDD-01` 升 v1.3
    （更正实测：失败的 fetch 退出码是 1；原记的 0 取自管道末端的 head）。
    v5.2 `FYL-SDD-01` 升 v1.2（facts 搜索路径：多源、优先级、逐条决胜）。
    v5.1 `FYL-SDD-01` 升 v1.1（装置语料 `devices/` 与公开版 / 内部版构建入册）。
    v5.0 全书重排（用户「优化重写整个设计文档整体架构和详细章节」，2026-09-04）。
    十一篇文档同日各出一个大版本：规格链 `FYL-CONOPS-00` v1.0 · `FYL-SRS-01` v1.0 ·
    `FYL-SDD-01` v1.0，设计书 `-09` v2.0 · `-10` v2.0 · `-11` v1.0 · `-12` v1.0 · `-13` v1.0 ·
    `-14` v1.0 · `-15` v1.0 · `-16` v2.1。共同的整理：沿革叙述收进各篇的版本行，正文只写
    现行状态；「双宿主」退役为「多宿主 / 两个运行时」；失效路径按 2026-09-04 仓树改正
    （`docs/note` `docs/cases` `docs/archive` `mapping/` `app/server/` 已不在本仓）；提案编号
    在 SRS 附录集中登记。本书的**架构**随之定型：规格链在前，设计书按层分两组——
    内核与中间层（`-16` `-14` `-15`）、浏览器前端（`-11` 外壳 + 四页），`myst.yml` 的 toc
    同批改序。本目录的目录行按 STANDARD 收成一行一篇，编号登记表新立，归档表改指内核仓。
    · v4.6 `-16` 升 v2.0（全文重写）。· v4.5..v3.6 `-16` v0.1..v1.3 十四次同日增量
    （可替换内核 · 多宿主 · 改名 fylite_runtime · K-8 装置 · 扁平树 · 回调撤回 · 无状态 ·
    状态管理 · 中间层进 wasm）。· v3.5 `-15` 的规范条款上提 SDD v0.13 / SRS v0.5。
    · v3.4 收编 `-15`。· v3.3 共享外壳落地。· v3.2 四页视觉细化，P-25..P-30。
    · v3.1 `-11` 重构为桌面版外壳。· v3.0 四页各一份文档（`-10` 拆出 `-12` / `-13`），
    新增 `-11`。· v2.9 含时演化栏收敛进放电设计页。· v2.8..v2.3 收编 `-10` / `-09` 各版。
    · v2.2 CONOPS 建设原则。· v2.1 收编 SDD，规范链 ConOps → SRS → SDD 齐。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-design-index

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-00` |
| 文档名称 (Title) | 设计书目录 (Design Book Index) |
| 短名 / Slug | `fylite-design-index` |
| 版本 (Version) | v5.5 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | concept (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性) |
| 生命周期状态 (Status) | Released |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Fable 5 |
| 受众 (Audience) | new project members / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | (none) |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

(fylite-design-index-intro)=
# 设计书 (The Design Book)

本书回答的是**「它为什么长这样」**。三层，按读的次序：

1. **规格链**（规范性）：`FYL-CONOPS-00` 定位——FyLite 以**轻量功能集**验证与展示
   `FYTOK-CONOPS-00` 的五类应用任务，包络为单机 · 交互档毫秒至秒量级响应（按功能
   声明预算）· 有限多线程 · 跨平台（本机与浏览器两个运行时，多宿主一份内核契约）；
   `FYL-SRS-01` 在该定位下给出需求；`FYL-SDD-01` 给出五视图设计描述，其组合视图是
   仓内布局的规范源。
2. **设计书**（信息性）：按四层架构分两组。**内核与中间层**——`FYL-DESIGN-16`
   可替换内核与四层分工（全书的架构正本）、`-14` 中间层的数据半边、`-15` 发布形态与
   命令行；**浏览器前端**——`-11` 四页共用的外壳，`-09` / `-10` / `-12` / `-13` 四个
   功能页各一篇。设计书的规范条款经提案入 SRS / SDD；尚未落文本的提案编号集中登记在
   `FYL-SRS-01` 附录，免得撞号。
3. **归档**：重定位之前的八篇设计笔记冻结在内核仓，不在本书构建内
   （{ref}`fylite-design-index-archive`）。

本目录是设计书文档集的**唯一路径权威**：文档以 `document_id` 指认、经本表解析路径；
文档集增删或改版时，本表与 `docs/myst.yml` 的 `toc:` 在同一变更中更新。

(fylite-design-index-numbering)=
## 编号登记 (Numbering Registers)

裁定编号在**代码与闸子里被按号引用**，所以条搬家不改号、已闭合的划掉留行不删号。
各篇的编号前缀与下一个空号：

| 前缀 | 正本 | 范围 | 说明 |
| :--- | :--- | :--- | :--- |
| `K-` `F-` `B-` `S-` `N-` `D-` `H-` | `FYL-DESIGN-16` | K-1..K-8 · F-1..F-4 · B-1..B-4 · S-1..S-6 · N-1 · D-1..D-4 · H-1..H-5 | 内核契约 · 扁平树 · 补数据 · 状态 · 命名 · 中间层 · 宿主。★`-16` 的 `D-` 与 `-09` 的 `D-` 是两套，各在各篇内唯一 |
| `L-` | `FYL-DESIGN-14` | L-1..L-12 | 数据半边 |
| `R-` `C-` | `FYL-DESIGN-15` | R-1..R-6 · C-1..C-8 | 发布形态 · 命令行 |
| `V-` | `FYL-DESIGN-11` | V-1..V-15 | 外壳与不随宿主改变的视觉 |
| `D-` | `FYL-DESIGN-09` | D-1..D-25 | 放电设计页 |
| `P-` | `FYL-DESIGN-10` 持总表 | P-1..P-30，**四页一条全局序列**（`-10` / `-12` / `-13` 各持若干号） | 四页共同纪律 P-1..P-8 · P-13..P-15 · P-25..P-27 在 `-10`，另外三篇引用不抄；下一号 P-31 |
| `G-` | 各篇自己 | 逐篇独立 | 缺口；`-10` / `-12` / `-13` 的 G- 是拆分前的同一条序列，条搬家不改号 |
| `FR-` `NR-` `DE-` | `FYL-SRS-01` / `FYL-SDD-01` | 域表在 `.context/PROJECT.md` §4 | 提案登记在 SRS 附录；DE-LOG-08..10 留给页面提案，内核契约取 DE-LOG-11 / -12 |

(fylite-design-index-catalog)=
# 文档目录 (Document Catalog)

| 文档标识 | 主题（简） | 版本 / 状态 |
| :--- | :--- | :--- |
| [`FYL-DESIGN-16`](FYL-DESIGN-16.md) | **可替换内核与四层分工**——内核以 fyo 文档门为唯一接口，门上是双向扁平树；内核无状态、状态随文档走；`fylite_runtime` 是中间层（SpData profile、后端表）；多宿主只写计划只读记录；一条总线九步 | v2.1 · WD |
| [`FYL-DESIGN-15`](FYL-DESIGN-15.md) | **发布形态与统一命令行**——单一可执行文件 `fy` · 静态 / 动态网页 · Python 包，一份源；三份命令行由 `_cli.json` 一个文件建出（R-1..R-6 · C-1..C-8） | v1.0 · WD |
| [`FYL-DESIGN-14`](FYL-DESIGN-14.md) | **中间层的数据半边**——数据源 ↔ fyo：MDSplus 只读、a/g-file、JSON-LD、HDF5、netCDF 各带 fyo 与 IMAS 布局，多源合并与按 A-Box 装配（L-1..L-12）。★v1.2：**L-13 搬家表**（`limiter` / `vessel` → `description_2d[]`），G-10 已关 · ★v1.3：记下 L-4 许可裁定在 imas-python 警告上的影子 | v1.3 · WD |
| [`FYL-DESIGN-13`](FYL-DESIGN-13.md) | **装置数据页**（`data`）——什么也不算的工具页：如实降级 · 抽稀不是归约 · 守卫两侧各做一遍 · 目录说存在不说记了 · 产物是足迹（P-10..P-12 · P-18 · P-24 · P-30） | v1.0 · WD |
| [`FYL-DESIGN-12`](FYL-DESIGN-12.md) | **实验分析页**（`analysis`）——剖面拟合 · 平衡反演 · 时间序列 · 批处理；磁测量约束不住内部剖面，定下来的是动理学约束（P-9 · P-16 · P-22 · P-23 · P-29） | v1.0 · WD |
| [`FYL-DESIGN-11`](FYL-DESIGN-11.md) | **视觉设计——桌面版应用的外壳**——四页共用一条常驻两行工具条、只差三个槽、16:9 首屏落一处输出；已落在 `page_*` 五页，未提为正本（V-1..V-15） | v1.0 · WD |
| [`FYL-DESIGN-10`](FYL-DESIGN-10.md) | **物理建模页**（`model`）——三条栏全部不含时：定态输运 · 边界与度规 · 功率平衡反演；兼持**四页共同的纪律**与 `P-` 编号总表（P-1..P-8 · P-13..P-15 · P-17 · P-19..P-21 · P-25..P-28） | v2.0 · WD |
| [`FYL-DESIGN-09`](FYL-DESIGN-09.md) | **放电设计页**（`pulse_design`）——一份脉冲脚本、三个模式（配置 / 设计 / 仿真）、同一套视图；平顶 PF 电流是 LCFS 锁定下的反馈轨迹；仿真两档保真度（D-1..D-25） | v2.0 · WD |
| [`FYL-SDD-01`](FYL-SDD-01.md) | 软件设计描述——五视图；四层组合（九组件保号，DE-COMP-01 内核可替换、DE-COMP-09 中间层、DE-COMP-04 退役中）；逻辑视图新增 DE-LOG-11 文档门 · DE-LOG-12 内核无状态。★v1.1：装置语料与公开版 / 内部版构建入册 · ★v1.2：facts **搜索路径**（多源、前置、逐条决胜）· ★v1.3：更正一处实测（失败的 fetch 退出码是 1，不是 0） | v1.3 · WD |
| [`FYL-SRS-01`](FYL-SRS-01.md) | 软件需求规格——五任务域 + 横切域（HOST · **KERNEL** · DATA · TOOL）FR、包络 / 依赖 / 质量 NR、外部接口、提案登记附录、追溯矩阵 | v1.0 · WD |
| [`FYL-CONOPS-00`](FYL-CONOPS-00.md) | FyLite 运行概念——轻量验证 / 展示 FYTOK-CONOPS-00 五类应用任务；包络四条；建设原则六条；宿主与运行时；内核可替换为演进方向 | v1.0 · WD |

(fylite-design-index-archive)=
# 归档文档 (Archived Documents)

重定位（`FYL-CONOPS-00`）之前的设计笔记已冻结归档。★2026-09-01 仓一分为二后它们随
内核走：正文在**内核仓** `docs/archive/`（私有），不在本书构建内、不在任何 `toc:` 里；
本书活动页面不引用其内容。编号续用不重置——归档是逐篇冻结，不是停用该系列。

| 文档标识 | 主题（简） | 版本 / 状态 | 归档路径 |
| :--- | :--- | :--- | :--- |
| `FYL-DESIGN-08` | Python 端四场景与物理数值收敛 | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-08.md` |
| `FYL-DESIGN-07` | `app/` 应用场景——入口与页面收敛为四条线 | v0.5 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-07.md` |
| `FYL-DESIGN-06` | 装置数据面——mdsip 只读客户端 | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-06.md` |
| `FYL-DESIGN-05` | 0D 放电分析线规划 | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-05.md` |
| `FYL-DESIGN-04` | 浏览器端算力边界——能力谱逐项判定 | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-04.md` |
| `FYL-DESIGN-03` | 芯部输运求解器（1.5D 转写） | v0.3 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-03.md` |
| `FYL-DESIGN-02` | Rust 输运内核——GEO / NEO / TGLF | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-02.md` |
| `FYL-DESIGN-01` | Rust 平衡内核设计 | v0.1 · Withdrawn | 内核仓 `docs/archive/FYL-DESIGN-01.md` |
