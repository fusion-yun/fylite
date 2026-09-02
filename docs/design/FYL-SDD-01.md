---
document_id: FYL-SDD-01
title: FyLite 软件设计描述 (FyLite Software Design Description)
shortname: fylite-sdd
version: "0.13"
date: 2026-08-18
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Fable 5
created: 2026-08-18T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-02T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.13：**三种发布形态与统一命令行入册**（`FYL-DESIGN-15` 的规范条款上提）。
    ①布局表：`rust/fylite/` 注明在私有内核仓、制品装进本仓且不入库，新增
    `rust/fylite_data/`（DE-COMP-09 数据层，兼 Rust 宿主的命令行）与三条发布路径的脚本；
    ②新增组件 **DE-COMP-09 数据层**（取数与格式 + Rust 命令行；一份源三个制品）；
    ③DE-COMP-06 声明面：`_cli.json` 自 2026-09-02 起是**三个宿主共同的**命令行定义，
    新增不变式「命令行只有一份声明式定义」；④DE-COMP-03 机械核：`app` / `data` / `case`
    三条命令逐字委托 Rust 可执行文件；⑤DE-COMP-05：制品不入库、页面清单按实（四个场景页
    + 算例报告页），启动参数由共享规格声明；⑥接口视图增「三宿主 ↔ 命令行规格」一行；
    ⑦追溯矩阵补 DE-COMP-09 与 FR-TOOL-004。
    v0.12：`docs/` 定型为**书集**。放弃 `docs/index.md`（站点封面），`docs/myst.yml` 改为 `site.projects` 挂四本书、自己不再持有任何 toc——先前那份 toc 是四本书目录的**抄本**，只为让根上能有封面而存在，封面一撤它就没有理由了。同批裁定 `note/`（含原 `benchmark/`）**不入册**：参考书的「实测笔记」一章与报告书的「V&V 登记册」一章从各自 toc 撤出，文件原地不动、每一条 `docs/note/…` 路径引用照旧成立。理由是那条 `../`——一本书的 toc 伸到自己目录之外，是在替不属于它的文件安排 URL；而这些文件在仓里是**按路径被引用的记录**（测试、`TODO.md`、`FEATURE.md`、语料的 `account`/`report` 字段），要的是稳定路径不是章节号。★守「一份对拍报告不会被遗忘」的从 toc 换成登记册本身（`test_every_benchmark_report_is_named_by_the_registry`）：toc 只能保证可达，登记册保证**有主**。实测：书集构建 29 页（6/13/4/6），`--strict` 通过。
    v0.11：场景语料与 V&V 登记册合并为一处 `docs/cases/`（顶层 `cases/` 与顶层 `benchmark/` 同时消失），布局表相应改写。★同批**页面不再取算例**：`S.cases` 与六个算例选择器撤除，`app/cases` 符号链接删除，`validate-cases.mjs` / `validate-initial-case.mjs` 撤销，发布流水线不再带语料（连带撤掉「剔九份 `evolve-fuse-*` 再改写 `catalogue.jsonld`」那套子集规则与三条自检），桌面版内嵌表 123 → 97 个文件。理由：语料是文档数据，一份真源一组读者；先前是三份副本（仓、站点、二进制）各自可漂。★读者失去的是菜单与「首访施用初始算例」，会话文件的导入导出不变——一份算例仍然就是一份会话文档。
    v0.10：①装置牌一份真源——`app/devices/<dev>.jsonld` 改为指向 `machine_desc/<dev>/` 的符号链接（页面树只留形状），发布工作流据此从源树 `cp -L` 落实体（`cp -r` 不解引用，实测；这些链接指向 `app/` 之外，否则站点上是断链）。②布局表增顶层 `mapping/`（采集绑定，数据非代码）——MDSplus 读入的节点／标度／时间基／目标语义位置外置为逐机器一份 JSON，两宿主读同一份；机器事实仍在装置牌，映射只按 `device:` 引用指向它，不复制（这条边界由`test_mds_map.py` 的引用闸守卫）。本批**不切换消费者**，等价性由两道闸子断言：Python 侧把标度用合成输入**跑出来**再与声明比，浏览器侧比对两宿主拼出的 `\EFIT_EAST::TOP…` 节点全集。
    v0.9：DE-COMP-03 增报告面——`fylite report` 把一次已记录运行渲染为统一
    MyST 报告（学术体例：摘要/方法/结果/验收/复现性；表题在上、图题在下、
    tbl-/fig- 锚点；只投影不复制数组，验收逐字引用不重判；规范正文
    `docs/reference/report-template.md`，模板与代码经 `test_report.py` 互钉）。
    v0.8：布局表增顶层 `cases/`（场景语料，由 `app/cases/` 提升；页面经符号
    链接保形、发布落实体、CLI 经 `fylite cases` 直达）。同批裁定 **CLI 为主要调试
    环境**（记录在 TODO 口径与 `FYL-REPORT-03` §5 的基准面裁定，此处只落布局）。
    v0.7：`FYL-REPORT-03` §9 四条经确认升格。①组合视图增跨宿主逻辑组件
    **DE-COMP-08 语义层（fyo）**（声明源 / 生成制品 / 宿主门面三类成员；不改目录
    指派）并给出五层视图在组件上的落点；②逻辑视图增 **DE-LOG-07「语义单源」**——
    新增共享语义必须表化，宿主手写语义面只减不增（棘轮），生成物禁改；★逐位一致
    闸子随 A-1 落，落地前如实注明「已声明未全闸」；③接口视图增「能力目录 ↔ 双宿主」
    一行，目标口径与现状分开写——wasm 15 条命令未入目录，MUST 自 A-2 落地起生效；
    ④增 **DE-COMP-05.2「LLM 位置纪律」**：两个合法位置一个禁区，LLM 的合法产出只有
    调用 / 未提升文档 / 文字，与「宁可拒绝，不给假数」同源。追溯矩阵补 DE-COMP-08
    与 DE-LOG-07 两行。v0.6：DE-COMP-05 增可选部件 **DE-COMP-05.1「BYOK LLM 前端」**——读者自带
    LLM 服务与密钥，页面据以规划并指挥 wasm 计算。五条不变式：密钥存 `sessionStorage`
    且禁用 `document.cookie`（cookie 随每次同源请求自动发出）· 密钥禁入任何导出物与
    运行记录 · 禁止声称产出受管工件（浏览器产不出 owner/signature，与 `session.js`
    已有裁定同一条）· LLM 只规划不执行生成代码（调用面限于已声明入口，这是本前端安全
    论证的正身）· 共享 origin 须告知或迁址。接口视图增一行「浏览器 ↔ LLM 服务」，
    并写明请求不经本仓任何服务端。判据与实测见 `FYL-REPORT-01` §14。
    v0.5：DE-COMP-07 的宿主由 `machine.py` 改为 `device.py`——「牌在哪」与
    「牌说什么」合为一个模块（定位规则此前写了两遍，限制器有两个读法且其一无调用者）。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-sdd

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-SDD-01` |
| 文档名称 (Title) | FyLite 软件设计描述 (FyLite Software Design Description) |
| 短名 / Slug | `fylite-sdd` |
| 版本 (Version) | v0.13 |
| 发布日期 (Date of Issue) | 2026-09-02 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | IEEE Std 1016-2009 |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | Yes (规范性) |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Fable 5 |
| 受众 (Audience) | maintainers / solver authors / LLM-tool integrators |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | FYL-SRS-01 v0.3（软件需求）; FYL-CONOPS-00 v0.3（运行概念） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

(fylite-sdd-abstract)=
# 摘要 (Abstract)

本文件按 IEEE Std 1016-2009 描述 FyLite 的软件设计：背景 / 组合 / 逻辑 / 接口 / 行为
五个视图。设计元素（`DE-*`）逐一回接 {ref}`FYL-SRS-01 <fylite-srs-abstract>` 的需求；
组合视图是仓内包分层的**规范源**，其变更**必须 (MUST)** 与 `.context/PROJECT.md`
源布局节同批同步。本版描述 as-built 设计。

(fylite-sdd-conventions)=
# 约定与术语 (Conventions and Terminology)

- 设计元素 ID：`DE-COMP-NN`（组件 / 结构）、`DE-LOG-NN`（逻辑 / 行为）、
  `DE-STR-NN`（物理结构）；每个元素携四字段块（职责 / Traces to / 不变式 / 接口）。
- 术语沿 `FYL-CONOPS-00`（双宿主、交互档 / 批式档、装置牌）与 `FYL-SRS-01`
  （场景线）；本文件不重定义。
- **计算核（compute core）**：以 Rust 实现的数值内核集合，编译为本机动态库与
  WebAssembly 模块两种制品。
- **机械核（mechanism kernel）**：与物理无关的运行机械——命令行、进程间服务、
  能力目录、运行清单。

(fylite-sdd-context)=
# 背景视图 (Context View)

FyLite 是单仓交付的独立软件包，对外呈现两个宿主与七个接口面
（`FYL-SRS-01` §外部接口）。系统边界上有三条固定关系：

1. **装置数据在外**：装置牌经环境变量或显式路径接入，仓与分发件不含装置 / 实验数据
   （FR-DATA-001）。
2. **生态零代码耦合**：不导入任何 `sp` / `fy*` 包；互操作只经声明清单与语言中立的
   进程间接口（NR-DEP-002）。
3. **双宿主同源**：浏览器宿主与 Python 宿主共享同一 Rust 计算核制品，不存在第二套
   数值实现（NR-ENV-004）。

(fylite-sdd-composition)=
# 组合视图 (Composition View)

本节为仓内布局的**规范源**。{numref}`tbl-fylite-sdd-layout` 给出目录到组件的映射；
{numref}`fig-fylite-sdd-components` 给出组件依赖方向。

:::{table} 仓树 → 组件映射（规范）。仓根不是 Python 工程：Python 工程自含于 `python/`。
:name: tbl-fylite-sdd-layout
:align: left

| 目录 | 组件 | 说明 |
| :--- | :--- | :--- |
| `rust/fylite/` | DE-COMP-01 Rust 计算核 | 单 crate；本机 cdylib 与 wasm 模块同源构建（`rust/build.sh`，wasm 产物出 `rust/wasm/dist/`）。★★**2026-09-01 仓一分为二后这棵 crate 在私有仓 `fylite_kernel`**：那边的 `rust/build.sh` 把制品与生成物（`libfylite_kernel.so`、三个 `.wasm`、`_abi.py` / `version.js` / `fyo-interface.*`）**装进本仓**。本行留在布局表里，因为它指派的是那些制品的落点与本仓对它的依赖方向，不是本仓的源码目录。★制品**不入库**（`.gitignore` 抬头）：打包发布时装入 |
| `rust/fylite_data/` | DE-COMP-09 数据层 | 本仓**唯一的 Rust 源码树**，源码公开（协议编解码与文件格式，不是物理 IP）：mdsip 只读客户端、g/a-file、HDF5 / netCDF、YAML 子集、多源装配，外加 **Rust 宿主的命令行**（`src/cli/`，由共享规格 `python/fylite/_cli.json` 编译期建出）。一份源三个制品：`libfylite_data.so`（Python 经 ctypes 取）、`fylite-app`（单一可执行文件，内嵌整个 `app/`）、`fylite-data` / `fylite-case`（同一份代码的薄壳别名）。构建 `rust/build.sh`（本仓的那一份）|
| `python/fylite/*.py` | DE-COMP-02 Python 装配层 | 平铺物理 / 装配模块；`python/` 内含 `pyproject.toml` / `pytest.ini` / `tests/` |
| `python/fylite/engine/` | DE-COMP-03 机械核 | 子包（CLI / 服务 / 清单 / 溯源 / 注册 / 版本 / 原生库装载） |
| `python/fylite/scenario/` | DE-COMP-04 场景层 | 四条场景线各一模块 |
| `app/` | DE-COMP-05 浏览器前端 | 静态页面 + `app/assets/*.wasm`（随仓提交的 wasm 制品）+ `app/tests/` 门禁；含**可选的 BYOK LLM 前端**（读者自带服务与密钥，见 {ref}`§DE-COMP-05.1 <de-comp-05-1>`） |
| `python/fylite/_manifest/` `_spec/` `_cli.json` | DE-COMP-06 声明面 | 数据非代码；随 wheel 分发 |
| `python/fylite/device.py` 及装置牌协议 | DE-COMP-07 装置牌接入 | 数据在外，代码在内；「牌在哪」与「牌说什么」同一模块。★★★**2026-09-02 起本仓不再存装置牌。** 它的真源是 **fydoc 的 A-Box**（`fydoc/device/<dev>/abox/`，用户裁定：fydoc 是权威源），公开仓在需要时用`tools/abox-to-machine-desc.py` **拖回**到本地 `machine_desc/`（那边 gitignore，不进版本库）。★页面树里的 `app/devices/<dev>.jsonld` 也**不再是符号链接**：分仓之后那些链接指向另一个仓，克隆下来就是断链（实测两条），现已改为实拷。下一段那套 `cp -L` 的讲究随之作废——留在这里是因为它记的是当时为什么那么做。★这原先与 `cases` 同姿态；`cases` 的那条链接 2026-09-01 随算例菜单撤除，装置牌这一条**留着**——页面确实要读装置卷宗，语料则不再读。★发布时必须**落实体**——`cp -r` 保留链接而不解引用（实测），而这些链接指向 `app/` 之外，照拷出去就是断链、页面取装置文档 404 而站点本身构建得好好的；`publish-app.yml` 因此从**源树**逐个 `cp -L`（链接的相对目标只在源树下成立）|
| `docs/` | 文档**书集** | 四本各自独立的 MyST 书——`design/` `guide/` `reference/` `report/`，每本自带 `myst.yml`、可单独构建；`docs/myst.yml` 只用 `site.projects` 把四本挂成一个站点，**自己没有 toc、根上没有页面**（2026-09-01 放弃 `index.md`；MyST 1.10.1 在多 project 下不构建根 project，封面既然不要，这条限制就不再拦路）。★**不入册**三处：`note/`（实测笔记 + V&V 对拍报告，按路径被引用的记录）、`cases/`（语料 + 登记册机器可读的一半）、`archive/`（冻结的历史）|
| `docs/cases/` | 场景语料 + V&V 登记册（数据） | fyo/JSON-LD 会话文档 + `catalogue.jsonld`，与 V&V 登记册 `registry.jsonld` / `context.jsonld` / `scenarios/` 同处（2026-09-01：顶层 `cases/` 与顶层 `benchmark/` 一并折进来；先前 `cases/` 由 `app/cases/` 提升）。★★**单宿主**：读者是 `fylite cases`、`fylite.scenario.cases` 与书，**浏览器不读**——同批撤掉页面的算例菜单，于是 `app/cases` 符号链接、发布流水线的子集规则（剔九份 `evolve-fuse-*` 并改写目录）与桌面版内嵌的那第三份副本一并消失。语料不随 wheel 分发，与装置牌同一姿态。闸子：`fylite cases --check`（`test_cli_spec` 语料段）与 `test_benchmark_registry.py` |
| `mapping/` | 采集绑定（数据） | 逐机器一份 MDSplus → fyo 采集映射（`<machine>-mds.json`）+ 其格式 `mds-map.schema.json`。★它只载**绑定**：哪个节点喂哪个语义位置、过哪个标度、按哪条时间基取片；机器自己的事实（逐通道节点名、匝数、门限、窗口）留在装置牌里，由 `device:` 引用指着，不抄。两宿主消费同一份文件，闸子 `test_mds_map.py` （含把标度**跑出来**再比的等价判据）与 `validate-mds-map.mjs`（两宿主节点全集比对）|
| `tools/` `examples/` | 辅助 + **发布路径** | 合成算例生成器与示例；三种发布形态各一条构建路径（`build-app-exe.sh` 单一可执行文件 · `build-site.sh` 静态站点 · `build-wheel.sh` Python 轮），外加内嵌资源表生成器 `make-app-embed.mjs`（产物入库、门 `app/tests/validate-embed.mjs` 校验同步）。形态之间的边界与裁定见 `FYL-DESIGN-15` |
:::

:::{figure}
:name: fig-fylite-sdd-components
:align: center

```{mermaid}
graph TD
    APP["DE-COMP-05 浏览器前端 (app/)"]
    WASM["wasm 模块 (app/assets/*.wasm)"]
    CORE["DE-COMP-01 Rust 计算核 (rust/fylite)"]
    CDYLIB["本机 cdylib (_lib)"]
    ASM["DE-COMP-02 Python 装配层 (fylite.*)"]
    ENG["DE-COMP-03 机械核 (fylite.engine)"]
    SCN["DE-COMP-04 场景层 (fylite.scenario)"]
    DECL["DE-COMP-06 声明面 (_manifest/_spec)"]
    DEV["DE-COMP-07 装置牌接入"]
    APP --> WASM
    WASM --> CORE
    CDYLIB --> CORE
    ASM --> CDYLIB
    ASM --> DEV
    SCN --> ASM
    ENG --> DECL
    SCN --> ENG
    FYO["DE-COMP-08 语义层 (fyo)"]
    ASM --> FYO
    APP --> FYO
    FYO --> CORE
```

组件依赖方向：两宿主分别经 wasm 模块与本机 cdylib 依赖同一 Rust 计算核；场景层
组合装配层与机械核；机械核唯一消费声明面。语义层（DE-COMP-08）被两宿主消费，
其声明源在计算核 crate 内（浏览器只依赖它的 JS/JSON 生成物，不违反不变式 2）。
:::

(de-comp-08)=
### DE-COMP-08 语义层（fyo，跨宿主逻辑组件）

**唯一不映射到单一目录的组件**——它按语义归属划分，不改 {numref}`tbl-fylite-sdd-layout`
的目录指派（成员文件物理上仍在各宿主目录里，不变式 1 口径不变）：

| 成员 | 角色 |
| :--- | :--- |
| `rust/fylite/src/fyo.rs` 的 `@fyo-table` / `@fyo-block` / `@fyo-entry` 注记 + `python/fylite/_fyo_vocab.json` | **声明源**（语义只声明一次，DE-LOG-07） |
| `python/fylite/_fyo_interface.py` · `app/assets/fyo-interface.js` · `rust/wasm/fyo-interface.json` | **生成制品**（`rust/build.sh` 产出；禁改，与 `_abi.py` 同理） |
| `python/fylite/fyo.py` · `app/assets/fyo.js` | **宿主门面**（手写部分受 DE-LOG-07 棘轮约束） |

★五层视图（`FYL-REPORT-03` §2，本表为其在组件上的落点）：L0=DE-COMP-01，
**L1=DE-COMP-08**，L2=DE-COMP-06，L3=DE-COMP-03 的记录半边（句柄 / 清单 / 账本 /
重放 / 验收），L4=DE-COMP-05 与 DE-COMP-03 的 CLI / MCP 面。

(de-comp-01)=
**DE-COMP-01: Rust 计算核**（Rust compute core）

| Field | Value |
|:---|:---|
| Description | 平衡 / 演化 / 电磁 / 输运与动理学内核的唯一数值实现，单 crate 同源编译为本机 cdylib 与 wasm 模块。 |
| Traces to | FR-MODEL-001, FR-MODEL-002, FR-MODEL-003, FR-MODEL-005, NR-ENV-003, NR-ENV-004 |
| Invariant | crate 在 `wasm32-unknown-unknown` 目标上**必须 (MUST)** 始终可构建（无 std::fs / 线程依赖泄入 wasm 特性集）；线程并行仅经特性开关在本机构建启用。**同一物理量只有一个实现在此**：宿主（Python / 浏览器）经 C ABI 取用，不得转写。 |
| Interface | C ABI（`c_api.rs`）；wasm 导出面。 |

(de-comp-02)=
**DE-COMP-02: Python 装配层**（Python assembly layer）

| Field | Value |
|:---|:---|
| Description | 平铺的装配模块：任务级编排、数据装配（g-file / 装置数据 / 剖面映射）、命名与序列化、判据与报告，数值步一律下沉计算核。 |
| Traces to | FR-ANALYSIS-001..004, FR-PULSE-001..002, FR-OPTIM-001..002, FR-CONTROL-001..002, FR-DATA-002, NR-DEP-001, NR-DEP-002 |
| Invariant | 必需运行时依赖仅 numpy；不导入 `sp` / `fy*`（静态检查守门）。**本层不实现物理与数值**：离散化、闭合、拟合、积分与归一化归 DE-COMP-01（{ref}`de-comp-01`），本层只做装配（数组整形、单位与名字、调用顺序）——同一物理量的第二份实现即缺陷，无论它与第一份是否一致。 |
| Interface | `fylite.*` 公共模块函数面。 |

(de-comp-03)=
**DE-COMP-03: 机械核**（mechanism kernel）

| Field | Value |
|:---|:---|
| Description | 与物理无关的机械：CLI 构建与入口、JSON-RPC / MCP 服务、能力目录与清单校验、运行溯源、报告渲染（`engine/report.py`——运行记录的 MyST 投影，统一模板见 `docs/reference/report-template.md`）、ABI 版本核对与原生库装载。 |
| Traces to | FR-TOOL-001..003, FR-DATA-003, NR-DEP-001 |
| Invariant | `fylite.engine` 顶层导入仅标准库；numpy 与重型依赖一律函数内惰性导入。 |
| Note | 后端注册（原 DE-LOG-03）**已退出本组件**，`engine/registry.py` 删除——退役理由见 DE-LOG-03 条目。★★本不变式此前**并不成立**且无门禁，2026-08-21 已修并立闸（`python/tests/test_engine_imports_only_stdlib.py`）。两处破口性质不同：一是 `engine/provenance.py` 顶层裸 `import numpy`（字面文本，四个用处改为函数内导入）；二是这条不变式**根本无从观测**——导入任何子模块都会先跑包的 `__init__`，而 `fylite/__init__.py` 当时顶层就 `from . import device, engine, io, kernel` / `.run` / `.scenario`，实测 `import fylite.engine` 拉进 numpy 与九个 `fylite.scenario.*`、耗时 ~155 ms，engine 自己再克制也没用。现 `fylite/__init__.py` 改为惰性（PEP 562 `__getattr__`），名字照旧、按需构建：`import fylite` 2.7 ms 且不加载 numpy，`import fylite.engine` 91 ms 且不加载 numpy。★顺带去掉了本包唯一的**导入环**：`run` 曾把 `scenario.analysis.recon_rs` 的两个私有辅助函数再导出（包内无调用者），而 `recon_rs` 反向导入 `KefitRunError`——于是 `__init__` 必须强制 `run` 先于 `scenario`，而那条顺序只是一行注释、无人校验。剪掉那次再导出后只剩单向，`__init__` 不再需要任何顺序。 |
| Interface | `fylite.engine` 入口（CLI main / serve / mcp）。★命令行由 **DE-COMP-06 的 `_cli.json`** 机械建出；其中 `app` / `data` / `case` 三条由 Rust 可执行文件承载，本层**逐字委托**（`--bin-dir` → 包内 `_bin/` → `$PATH`，找不到时按名说明要构建什么并退出 2；`FYL-DESIGN-15` R-4），不另写第二份实现。 |

(de-comp-04)=
**DE-COMP-04: 场景层**（scenario layer）

| Field | Value |
|:---|:---|
| Description | 四条场景线（物理建模 / 实验分析 / 放电设计 / 控制仿真）的任务级入口目录，双宿主各有对应入口。 |
| Traces to | FR-HOST-001, FR-MODEL-004, FR-ANALYSIS-001, FR-PULSE-001, FR-OPTIM-002, FR-CONTROL-001 |
| Invariant | 场景入口只组合装配层与机械核既有能力，**禁止 (MUST NOT)** 内联新数值实现。 |
| Interface | `fylite.scenario.<line>.<entry>`。 |

(de-comp-05)=
**DE-COMP-05: 浏览器前端**（browser front end）

| Field | Value |
|:---|:---|
| Description | 静态场景页面与 wasm 制品（**制品不入库**，构建时装入）；页面控件驱动单步求解并即时回显。同一份页面字节有两种交付：静态站点（`tools/build-site.sh`）与单一可执行文件内嵌（`fylite-app`，另答一组只读 `/api/*`）——差别由页面在运行时判别（`assets/host.js` 探 `/api/health`），**禁止 (MUST NOT)** 构建时分叉出两份页面（`FYL-DESIGN-15` R-1 / R-3）。 |
| Traces to | FR-HOST-001, FR-HOST-002, NR-ENV-001, NR-ENV-002 |
| Invariant | 页面仅消费 wasm 模块与静态资产；加载后离线可用（零远程请求依赖）。 |
| Interface | `app/` 的页面：三个散文页各中英两份（`tools/make-app-pages.mjs` 由词条生成，无 i18n 运行时）、四个场景页与一个算例报告页（`pages/{pulse_design,model,analysis,data,report}.html`，运行时切换语言）；`app/tests/` 门禁按台账校验页面。**启动参数**（`device` / `lang` / `theme` / `page`）在共享规格的 `hosts.app.params` 里声明一次，页面按名读取、门禁核对（`FYL-DESIGN-15` C-6）。 |

(de-comp-06)=
**DE-COMP-06: 声明面**（declaration plane）

| Field | Value |
|:---|:---|
| Description | 能力清单（撰写源）、vendored 交换 schema 与 CLI 规格——数据而非代码，随 wheel 分发；能力条目携预期响应时间预算声明。★★**2026-09-02 起 `_cli.json` 是三个宿主共同的命令行定义**（`spec_version: 2`）：Python 由它建 argparse、Rust 单一可执行文件在**编译期** `include_str!` 纳入并建自己的解析器与用法、浏览器把它的 `hosts.app.params` 当启动参数；只属一个宿主的命令或参数在文件里以 `hosts` 标出（`FYL-DESIGN-15` C-1 / C-2）。 |
| Note | **后端族表已退出本组件并已不存在**。它原是 `_backends.json`：十个 `"module:Class"` 字符串，包内无第二读者（无 JS / Rust / 工具 / 文档生成器读它），且 `register_backend` 原地改写解析后的全局 dict——不是稳定声明，而是一个可变全局的初值。代价是实打实的：那十个类在 Python 里没有任何调用点，对全树静态检查不可见，拼错要等到用户**选中**该后端才炸（实测默认档只抓到四族中的两族）。先改为 `_backends.py`（持有类本身），随后随注册表一并退役——见 DE-LOG-03。 |
| Traces to | FR-TOOL-001, FR-TOOL-002, FR-TOOL-004, FR-MODEL-005, NR-ENV-005 |
| Invariant | 能力目录**必须 (MUST)** 自清单文件派生；派生目录**禁止 (MUST NOT)** 落盘提交；vendored schema **禁止 (MUST NOT)** 本地改写。★命令行**必须 (MUST)** 只有这一份声明式定义：任一宿主**禁止 (MUST NOT)** 另持一张命令表或选项名单，不承载某命令的宿主**必须 (MUST)** 按名委托或按名拒绝（`FYL-DESIGN-15` C-1 / C-3）。 |
| Interface | 清单文件集（JSON 系）+ 机械核的目录派生函数。 |

(de-comp-07)=
**DE-COMP-07: 装置牌接入**（device-deck access）

| Field | Value |
|:---|:---|
| Description | 装置几何 / 诊断 / 限值的外部目录协议与装载器；数据在外、代码在内。 |
| Traces to | FR-DATA-001 |
| Invariant | 仓与分发件不含装置 / 实验数据；测试基准仅用内核自产合成算例。 |
| Interface | 环境变量 / 显式路径 → 装置对象。 |

(de-comp-09)=
**DE-COMP-09: 数据层**（data plane）

| Field | Value |
|:---|:---|
| Description | 取数与格式，**不做物理**：不同数据源 ↔ fyo 文档的读写转换（MDSplus 只读、a-file、g-file、JSON(-LD)、HDF5、netCDF、YAML 子集，各带 fyo 与 IMAS DD 两种布局）、多源合并、按 JSON-LD / YAML 装配、按炮号与时间的服务端切片；外加 **Rust 宿主的命令行**与算例的输入 / 输出半边（一份 fyo 计划进、一份 spo 记录出，经运行期 dlopen 的内核）。源码公开——这里是协议与格式，不是物理 IP。 |
| Traces to | FR-DATA-002, FR-TOOL-001, FR-TOOL-004 |
| Invariant | 本层**禁止 (MUST NOT)** 实现任何物理或数值（判据同 DE-COMP-02：同一物理量的第二份实现即缺陷）；对 MDSplus **必须 (MUST)** 只读，且**禁止 (MUST NOT)** 暴露取表达式的入口（每个 TDI 串由校验过的节点路径与整数拼出）；浏览器制品**禁止 (MUST NOT)** 含 mdsip（浏览器打不开裸 TCP）。 |
| Interface | `libfylite_data.so` 的 C ABI（`fylite_data_*`，Python 侧 `fylite.io.fydoc`）；三个可执行文件 `fylite-app` / `fylite-data` / `fylite-case`，其命令行由 DE-COMP-06 的规格建出。 |
| Note | 2026-09-02 从内核仓搬来：内核那本自己写着 *the kernel computes numbers; the hosts put them into documents*，而网络协议与文件格式按同一条判据是宿主的活（DE-COMP-02 的分层理由）。搬动同时收掉了两份重复实现——两个 g-file 读入（Python 与 JS 各一）与两份 mdsip 客户端。设计正本 `FYL-DESIGN-14`，命令行部分 `FYL-DESIGN-15`。 |

(fylite-sdd-composition-invariants)=
## 分层不变式 (Layering Invariants)

1. 源文件**必须 (MUST)** 落在 {numref}`tbl-fylite-sdd-layout` 指派的目录；仓根不放
   源文件与测试。
2. 依赖方向**必须 (MUST)** 遵循 {numref}`fig-fylite-sdd-components`；浏览器前端
   **禁止 (MUST NOT)** 依赖 Python 宿主。
3. 每个 Python 源模块在 `python/tests/test_<module>.py` 有镜像测试模块；页面台账由
   `app/tests/` 门禁核对。
4. 本视图与 `.context/PROJECT.md` 源布局节**必须 (MUST)** 同批变更。

(de-comp-05-1)=
### DE-COMP-05.1 BYOK LLM 前端（可选部件）

浏览器前端**可以 (MAY)** 携带一个 LLM 前端：读者输入自己的服务端点与密钥，页面
据以规划并指挥 wasm 计算、渲染输出。它是**可选部件**——页面在没有密钥时**必须
(MUST)** 完整可用，"每一次计算都在本地"这一条不因它而改变。

约束如下（判据与实测见 `FYL-REPORT-01` §14）：

5. 密钥**必须 (MUST)** 存于 `sessionStorage`；**禁止 (MUST NOT)** 使用
   `document.cookie`。★理由不是偏好：cookie 随每一次同源请求自动发出，页面每取一份
   资产都会把密钥送去一趟。升级到 `localStorage` **必须 (MUST)** 由读者显式勾选。
6. 密钥**禁止 (MUST NOT)** 进入任何导出物、会话文档、`fylite:` 键、运行记录或控制台
   输出。
7. 本前端**禁止 (MUST NOT)** 声称产出**受管工件**：它能产 run id、代码哈希与内核
   `sha256`，产不出 `owner` / `tenancy_scope` / `signature`。其产出**必须 (MUST)**
   标注为自描述文档且"未经提升"——与 `app/assets/session.js` 已有的裁定同一条
   （identity a browser page cannot produce and must not fake）。
8. LLM **禁止 (MUST NOT)** 执行生成的代码：它只**规划**，调用面限于已声明的固定入口
   （worker 命令 / 能力清单）。★这条是本前端安全论证的正身——边界封闭，不需要沙箱、
   fuel 与子进程管控。
9. 站点当前发布于共享 origin（`fusion-yun.github.io/fylite/`），而浏览器存储按
   **origin** 隔离、**不按路径**。密钥输入处**必须 (MUST)** 告知这一点，或站点迁至
   独立 origin。

(de-comp-05-2)=
### DE-COMP-05.2 LLM 位置纪律（跨宿主）

`FYL-REPORT-03` §7 的裁定，升格为规矩：

10. LLM 的合法位置仅两个：**外部宿主**（经 DE-LOG-06 的能力目录调用，主形态）与
    **页内 BYOK**（DE-COMP-05.1，可选）。二者读同一套声明面，差别只在能力目录的
    投影与记录级别。
11. 任一位置：LLM **禁止 (MUST NOT)** 执行其生成的代码，**禁止 (MUST NOT)** 产出
    进入计算路径或数据产物的数值（物理量、阈值、`[TBD]` 的填充）。LLM 的合法产出
    只有三类：**调用**（对已声明入口）、**文档**（fyo 文档与工作流草案，一律未提升）、
    **文字**。★这一条与「宁可拒绝，不给假数」同源——LLM 是编数最便捷的入口，
    所以在架构上焊死。
12. LLM 会话产出的工作流草案与浏览器会话文档**同级**：自描述、`sandbox_local`、
    未经有身份宿主的人审提升不得当作已注册流程（与账本既有语义同一条）。

(fylite-sdd-logical)=
# 逻辑视图 (Logical View)

(de-log-01)=
**DE-LOG-01: 单核双宿主**（one core, two hosts）

| Field | Value |
|:---|:---|
| Description | 同一 Rust crate 构建出本机 cdylib（Python 宿主装载）与 wasm 模块（浏览器宿主装载），数值行为同源。 |
| Traces to | NR-ENV-004, FR-HOST-001 |
| Invariant | 任一在双宿主可用的数值内核**必须 (MUST)** 只有 Rust 一份实现；**禁止 (MUST NOT)** 在 JS / Python 各写一份。 |
| Interface | cdylib 装载器（机械核）；页面 wasm 装载。 |

(de-log-02)=
**DE-LOG-02: ABI 单源**（single-source ABI）

| Field | Value |
|:---|:---|
| Description | ABI 版本与导出签名单点定义于计算核 C ABI 源，构建脚本生成 Python 侧常量；装载时核对版本。 |
| Traces to | NR-ENV-004, NR-QUAL-002 |
| Invariant | ABI 版本常量**必须 (MUST)** 恰有一处手写源；消费侧文件全部为生成物（禁手改）。 |
| Interface | 生成的 ABI 常量模块 + 装载时版本核对。 |

(de-log-03)=
**DE-LOG-03: 后端注册表**（backend registry）— **已退役 2026-08-21**

| Field | Value |
|:---|:---|
| Description | ~~输运闭包与源项等可换实现按族注册、按名解析；族与内建项由声明面表驱动。~~ 可换实现由**调用方直接构造并以对象传入**（`self_consistent(current_source=…, beam_source=…, wave_source=…)`，与既有的 `transport=` 同形）。 |
| Traces to | FR-MODEL-005 |
| Invariant | （原）机械核仅暴露通用注册 / 解析原语；**禁止 (MUST NOT)** 出现按族特判的门面。 |
| Interface | ~~`backend(family, name)` / `register_backend`~~ |

**退役理由**，逐条可核：

1. **它并不实现所追溯的需求。** FR-MODEL-005 要求的是「输运闭包档位（解析 / 新经典 / 湍流数值闭包）**必须**可按名选取」。那件事由**内核**做：`kernel.TRANSPORT_MODELS = {"constant", "stiff", "neoclassical", "given"}`，经 `model.transport(closure=…)` 按名选取。注册表的三个族是 `current_source` / `beam_source` / `wave_source`，都不是输运闭包档位。删掉注册表不触及 FR-MODEL-005。
2. **十个内建项里六个不是模型**（2026-08-21 前一批）：`sauter`/`sauter2021` 各一行、取同一次 NEO 答案的另一列；`profile_fitter` 整族只为一个字符串；两个 `"none"` 是与真成员不可区分的空对象。
3. **两个消费者都仍按名字分支。** `loop.py` 先查 `backend_meta("current_source")["neo_backed"]` 才知道该传什么；`fyo.neoclassical_source` 在 `if` 的一支里处理 `redl`、在另一支里查 `solver`——而那次查找只有**一个**可达答案。一个不给任何调用方多态的 name→factory 映射，是加了仪式的 dict。
4. **扩展点无人使用。** `register_backend` 在全树只有一个调用者，且是测试；文件在 wheel 内部，第三方本就改不了。传对象既覆盖同样的场景，又不需要注册步骤、名字或私有 dict。

(de-log-04)=
**DE-LOG-04: 交互 / 批式分档**（interactive / batch tiering）

| Field | Value |
|:---|:---|
| Description | 单步求解走同步调用即时回显（响应以该功能声明的预算为判）；多步外环（自洽迭代、网格扫描）以显式步进接口暴露，可中断、可续跑。 |
| Traces to | FR-HOST-002, NR-ENV-002, NR-ENV-005 |
| Invariant | 批式任务**禁止 (MUST NOT)** 占用同步工具槽或以单次交互操作形式呈现。 |
| Interface | 步进式循环入口 + 页面 / CLI 的进度回显。 |

(de-log-05)=
**DE-LOG-05: 运行清单发射**（run-manifest emission）

| Field | Value |
|:---|:---|
| Description | 每次求解运行发射机器可读运行记录：输入来源、参数、软件与 ABI 版本、产物指纹。 |
| Traces to | FR-DATA-003 |
| Invariant | 运行记录由机械核统一发射；求解路径**禁止 (MUST NOT)** 各自拼装记录格式。 |
| Interface | 机械核溯源模块 → 运行清单（JSON 系）。 |

(de-log-06)=
**DE-LOG-06: 能力目录反射**（capability-catalog reflection）

| Field | Value |
|:---|:---|
| Description | 声明面清单派生唯一能力目录；CLI describe、JSON-RPC、MCP 与 LLM 工具 schema 全部反射该目录——AI 平台工具插件交互面（FR-HOST-003）由此承载。 |
| Traces to | FR-TOOL-002, FR-TOOL-003, FR-HOST-003 |
| Invariant | 全部工具面共享同一执行路径；**禁止 (MUST NOT)** 为任一工具面另设执行通道或手抄目录。 |
| Interface | 目录派生函数 → describe / serve / mcp / 工具 schema 发射。 |

(de-log-07)=
**DE-LOG-07: 语义单源**（semantic single source）

| Field | Value |
|:---|:---|
| Description | 共享语义——文档表 / 打包块 / 场景入口 / 词汇——在 `rust/fylite/src/fyo.rs` 注记与 `_fyo_vocab.json` 里**声明一次**，`rust/build.sh` 生成三份宿主制品；两宿主的语义面读生成物，不各写一遍。★依据：`FYL-REPORT-02` 实测两宿主手写语义面 41 : 13 且已双写装配 14k 行——手写第二遍是已被付过一次的学费。 |
| Traces to | FR-HOST-003, FR-DATA-002 |
| Invariant | 新增共享语义**必须 (MUST)** 走表化声明；宿主门面（`fyo.py` / `fyo.js`）的手写语义**只减不增**（棘轮，与豁免登记簿同一纪律）；生成制品**禁止 (MUST NOT)** 手改。判据：两宿主对同一份文档取同一槽，结果逐位相同。★执行闸子如实注明现状：生成半边已有 in-step 闸子（`test_fyo_vocabulary` / `test_fyo_interface`）；**逐位相同那一条的闸子随 `FYL-REPORT-03` A-1 落**，落地前本条是已声明未全闸的规矩。 |
| Interface | `@fyo-table` / `@fyo-block` / `@fyo-entry` 注记 + `_fyo_vocab.json` → `build.sh` → `_fyo_interface.py` / `fyo-interface.js` / `fyo-interface.json`。 |

(fylite-sdd-interface)=
# 接口视图 (Interface View)

外部接口以 `FYL-SRS-01` §外部接口为准（CLI / JSON-RPC / MCP / 浏览器页面 / 装置牌 /
g-file / 运行清单）。内部接口两条为设计承诺：

| 内部接口 | 契约 | 稳定性 |
| :--- | :--- | :--- |
| Python ↔ 计算核 | C ABI：平面数组 + 显式长度；版本经 DE-LOG-02 单源核对，失配拒载 | ABI 版本随核演进递增 |
| 浏览器 ↔ 计算核 | wasm 导出面：与 C ABI 同源生成，按功能拆分模块（核心 / 湍流 / 动理学） | 与页面资产同批提交 |
| 浏览器 ↔ LLM 服务（可选） | 读者自带端点与密钥；请求由页面发起，**不经本仓任何服务端**（本仓不运营服务端） | 随服务方演进；本仓不承诺 |
| 能力目录 ↔ 双宿主 | **目标口径**（`FYL-REPORT-03` A-2，已确认）：声明面按 `kernel_id` 覆盖两宿主，`fylite:entry` 由单列变为按宿主的多列；届时「换 runner 不换协议」在 wasm 侧由巧合变为承诺。★现状如实：native 17 件已入目录，wasm 15 条 worker 命令**未入**——MUST 自 A-2 落地起生效，本行在此之前是排期不是规矩 | 随 A-2 |
| 三宿主 ↔ 命令行规格 | 一份 `python/fylite/_cli.json`：Python 建 argparse、Rust 可执行文件编译期 `include_str!` 建自己的解析器与用法、浏览器读 `hosts.app.params` 作启动参数；宿主特有项以 `hosts` 标出，不承载者按名委托或按名拒绝 | 命令与选项随规格演进；闸子 `python/tests/test_cli_spec.py`（含「三宿主同一份文件」四条）与 `cargo test cli::` |

跨接口数据**必须 (MUST)** 为平面显式形（数组 + 长度、扁平结构、序列化消息）；
panic / 异常**禁止 (MUST NOT)** 穿越宿主边界（在边界处映射为错误码或宿主异常）。

(fylite-sdd-behavior)=
# 行为视图 (Behavioral View)

- **交互求解循环**：宿主入口（页面控件 / CLI / 场景入口）→ 参数装配（装配层）→
  单步数值调用（计算核）→ 结果塑形与回显。该循环受 NR-ENV-002 响应量级（ms ~ s）
  与 NR-ENV-005 各功能声明的响应时间预算约束，实测以预算为判。
- **批式外环**：外环以步为单位推进（每步 = 一次交互档调用集合），步间可中断、
  状态可续；进度对用户可见（DE-LOG-04）。
- **运行落档**：任一求解完成即经 DE-LOG-05 发射运行清单；产物（g-file、图件）与
  清单互相指认（指纹）。
- **能力自述**：集成方经 describe / JSON-RPC / MCP 查询能力目录（DE-LOG-06），
  再按目录发起调用——查询与调用共享同一目录与执行路径。

(fylite-sdd-trace)=
# 追溯矩阵 (Traceability Matrix)

:::{table} SDD 设计元素 → SRS 需求追溯。
:name: tbl-fylite-sdd-trace
:align: left

| SDD Design Element | SRS Requirement |
|:---|:---|
| DE-COMP-01 | FR-MODEL-001, FR-MODEL-002, FR-MODEL-003, FR-MODEL-005, NR-ENV-003, NR-ENV-004 |
| DE-COMP-02 | FR-ANALYSIS-001..004, FR-PULSE-001..002, FR-OPTIM-001..002, FR-CONTROL-001..002, FR-DATA-002, NR-DEP-001..002 |
| DE-COMP-03 | FR-TOOL-001..004, FR-DATA-003, NR-DEP-001 |
| DE-COMP-04 | FR-HOST-001, FR-MODEL-004, FR-ANALYSIS-001, FR-PULSE-001, FR-OPTIM-002, FR-CONTROL-001 |
| DE-COMP-05 | FR-HOST-001..002, NR-ENV-001..002 |
| DE-COMP-06 | FR-TOOL-002, FR-MODEL-005, NR-ENV-005 |
| DE-COMP-07 | FR-DATA-001 |
| DE-COMP-08 | FR-HOST-003, FR-DATA-002 |
| DE-COMP-09 | FR-DATA-002, FR-TOOL-001, FR-TOOL-004 |
| DE-LOG-01 | NR-ENV-004, FR-HOST-001 |
| DE-LOG-02 | NR-ENV-004, NR-QUAL-002 |
| DE-LOG-03（已退役） | FR-MODEL-005（由 DE-COMP-01 的 `TRANSPORT_MODELS` 按名选取满足） |
| DE-LOG-04 | FR-HOST-002, NR-ENV-002, NR-ENV-005 |
| DE-LOG-05 | FR-DATA-003 |
| DE-LOG-06 | FR-TOOL-002, FR-TOOL-003, FR-HOST-003 |
| DE-LOG-07 | FR-HOST-003, FR-DATA-002 |
:::
