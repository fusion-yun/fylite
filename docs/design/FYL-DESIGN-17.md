---
document_id: FYL-DESIGN-17
title: "场景运行命令 `fy run` 的详细设计 (The `fy run` Command: Detailed Design)"
shortname: fylite-preset-scenarios
version: "1.3"
date: 2026-09-04
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-04T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-04T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v1.3 补上七条门禁里只有对着产物才答得出的两条（`python/tests/test_run_behaviour.py`）：
    ①两种位置参数形产出同一份计划（实测相等），⑤`--offline` 解析不到时按名拒绝而不是
    连出去。同批把 `--dry-run` 下解析不到的输入端口由「拒绝」改为「一行输出」（A-3 后半，
    理由写在那一行里）。
    · v1.2 **P1 落地**（用户「完整实现 cli 设计」，2026-09-04）：`_cli.json` 加 `run`
    （`open_parameters`）与 `list`（七条子命令）、去 `case` 与 `data facts`、加 `retired`；
    解析器收开放记号并按名拒绝退役词；新增 `src/corpus.rs`（语料四级 + 模板）、
    `cli/run.rs`（两段解析 · 开关 · 装置两条路 · 测量三级 · 来源账 · 记录）、`cli/list.rs`
    （七条只读子命令），`cli/case.rs` 撤除；`facts.rs` 补 experiment 域；九份场景模板与
    场景目录由 `tools/make-scenario-templates.py` 从语料生成（279 个参数名逐条取自
    `code/<x>#<名>` IRI）；闸子 `test_scenario_templates.py` 新增，`test_cli_spec.py` /
    `test_cli_docs_match_the_artifact.py` 随之改；指南与参考的命令行两页重写。
    **三处 as-built 与设计不同，逐条记在 {ref}`fylite-preset-asbuilt`**：模板发九份
    （语料的九个 code）而不是十份（`pulse` / `vstab` 没有 code IRI，改 P2-c）；
    `fy list` 不带子命令时按名拒绝并列出七条，没有单独的总览；`--dry-run` 一个字节都不写。
    · v1.1 两条用户裁定（2026-09-04）：**`case` 收进 `run`，`case` 命令弃用**；**新增 `list` 命令**，
    列出 facts 装置、实验条目、场景模板、预设、语料根与内核 code 表（E-24）。`fy` 从此是 `app` /
    `data` / `run` / `list` 四条命令词：`run` 的位置参数既收线与场景，也收计划文件（E-2 的名字 / 路径规则）；原
    `case describe` / `plan` / `run` / `json` 分别成为 `list kernel` / `run … --dry-run` /
    `run …` / `run … --json`，`data facts` 成为 `list facts`（迁移表 tbl-e17-migration）；发现面
    **只在 `list` 上**（E-4），`run` 不再有 `--list` / `--show`；`--set` 整个撤除，`--code` 保留为固定
    选项；`fy case …` 按名拒绝并指向对应写法，映射表在 `_cli.json` 的 `retired` 键里（E-23）。
    Rust 库模块 `crate::case`（合成器）保留，撤的是命令词与 `cli/case.rs`。E-2 / E-4 / E-5 /
    E-6 / E-10 / E-21 相应修订，E-23 / E-24 新增；J-1 / J-7 改写；门禁 ① 改为 `run` 两种形之间的等价式。
    · v1.0 由「评估」升为「详细设计」（用户：*详细设计命令行完成日常建模分析，如
    `fy run analysis --device east shot=123456 time=4.4 --only-magnetic=true`*，2026-09-04）。
    新增第四条命令词 `run <线> [<场景>]`（E-10），场景是位置参数不是命令词；两段解析
    （静态语法在 `_cli.json`，参数表在场景模板，E-11）；参数记法 `key=value` ≡ `--key=value`、
    `--flag` ≡ `flag=true`（E-12）；合成次序模板 → 装置 → 预设 → `--plan` → 命令行 → 端口，
    逐值记来源（E-13）；装置信息两条路进计划（E-14）；测量文档三级解析且取数落进记录目录
    （E-15，**修订 E-6**：`case` 仍不开套接字，`run` 的取数是一个有界的前置阶段）；环境变量
    只供资源不供物理参数，全表（E-16）；每线一条缺省场景（E-17）；模板声明的开关
    （E-18，`only_magnetic` 是第一个）；记录目录自足与 `--dry-run`（E-19）；退出码与拒绝阶段
    （E-20）；`run` 不是第二个合成器（E-21）；模板随 `fy` 内嵌、预设走语料路径（E-22，
    关闭 v0.1 的开放项）。E-4 / E-5 修订（发现面上 `run`，v1.1 改为 `list`；`--set` 留在 `case`，v1.1 撤除）。场景目录
    逐条覆盖文档明确涉及的全部场景（CONOPS S-L1..S-L5 · 三页十三条栏 · 语料 9 个 code ·
    工具表 10 件 · 指南五章），含不设模板者的理由。`_cli.json` 增量与解析器改动写成落地清单。
    · v0.1 初稿：预设是数据不是动词（E-1..E-9），三张清单不一样长，六条常用预设，两档分期。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-preset-scenarios

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-17` |
| 文档名称 (Title) | 场景运行命令 `fy run` 的详细设计 (The `fy run` Command: Detailed Design) |
| 短名 / Slug | `fylite-preset-scenarios` |
| 版本 (Version) | v1.3 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性；规范条款经提案入 SRS / SDD) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / 用命令行跑日常建模与分析的人 / 加一条场景模板或预设的人 / 实现 `run.rs` 的人 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-15` v1.0（一条命令行、一份规格；R-1..R-6 · C-1..C-8）· `FYL-DESIGN-16`（K-1 文档门 · K-8 装置整份进内核 · B-1 先问后跑 · D-3 合成只在一处）· `FYL-DESIGN-14`（L-10 时间选择 · L-11 A-Box 读者）· `FYL-DESIGN-09` / `-10` / `-12`（三页十三条栏）· `FYL-CONOPS-00`（S-L1..S-L5；离线包络）· `FYL-SRS-01` FR-DATA-001 / FR-TOOL-001 / FR-TOOL-004 · 语料 `docs/examples/`（25 条，9 个 code，`code/<x>#<name>` 词表）· `fylite.scenario.TOOLS` / `LINES` · `rust/fylite_runtime/src/{facts,assembly,case}.rs` 与 `cli/{data,case}.rs` 的现行实现 · 2026-09-04 用户裁定（Python 侧没有命令行） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 本版取代 v1.0 / v0.1；`E-` 为本篇的裁定前缀。**`fy case` 自本版起弃用**（E-23）；`FYL-DESIGN-15` R-2 / R-4 对命令词的枚举（`app` / `data` / `case`）需在该篇下一版改为 `app` / `data` / `run`，本篇不代改 |
:::

(fylite-preset-intro)=
# 场景运行命令 `fy run` 的详细设计 (The `fy run` Command: Detailed Design)

〔一句话〕**一条命令跑一次日常建模或分析：**

```bash
fy run analysis --device east shot=123456 time=4.4 --only-magnetic=true
```

线（`analysis`）选出缺省场景（`reconstruction`）；场景**模板**给出参数表与缺省值；
`--device east` 经 facts 语料装出整份装置文档并补上装置相关的缺省；`shot=` / `time=`
解析出测量文档（先离线语料，再取数）；`--only-magnetic=true` 是模板声明的**开关**，展开成
六个基础参数；合成好的计划进内核的文档门；记录目录里落着计划、装置、测量、
记录与数据集，**离线可重放**。

〔为什么升版〕v0.1 回答的是「预设怎么调、预设哪几个」，裁定是「不新增命令词，
`fy case run <名字>`」。用户随后给出的目标形状是**按线调用、参数直接写在命令行上**——
这与 `case run <计划文件> --set k=v` 差着三样东西：①线与场景是**一等的位置参数**而不是文件名；
②参数是 `key=value` 而不是 `--set key=value`，且每个参数**有类型、有缺省、有出处**（模板）；
③装置与测量**由命令自己解析**，不要求用户先手工 `fy data fetch`。这三样都不是 `case` 的
职责——`case` 是「一份计划进，一份记录出」的**文档门**（`FYL-DESIGN-16` K-1），不该学会
线、装置与炮号。v1.0 因此在 `case` 之上加了一层 `run`。

〔已确立〕**v1.1：`case` 收进 `run`，`case` 弃用**（用户裁定 2026-09-04）。两条命令并存的代价
在 v1.0 里已经写出来了：同一个门有两个入口，一个收计划文件、一个收线与场景，而它们的选项
表**几乎逐条重合**（`-o` · `--format` · `--kernel` · `--bind` · `--facts` · `--json` · `--quiet`）。
`run` 的位置参数本来就能分辨名字与路径（E-2），所以「收计划文件」不需要第二条命令词：
`fy run plan.jsonld` 与 `fy run analysis` 走同一条解析、同一个合成器、同一条门。原 `case` 的四条
子命令各有对应写法（{numref}`tbl-e17-migration`）；`fy case …` 按名拒绝并指向那个写法（E-23）。

〔已确立〕**v1.1：新增 `list` 命令**（用户裁定 2026-09-04：*添加 list 命令，列出 facts device、
scenario 等预设信息*）。「有什么可用」这个问题此前散在三处（`data facts` · `case describe` ·
v1.0 草案里 `run` 的 `--list` / `--show`），答案各是一种形。v1.1 把它们收成**一条只读的命令词**：
`fy list devices | experiments | scenarios | presets | facts | kernel`，每类语料一条子命令，给名字
就打那一条的全部（{numref}`tbl-e17-list`，E-24）。`fy` 从此是 **`app` / `data` / `run` / `list`**
四条命令词：一条起页面，一条搬数据，一条算，一条看。

(fylite-preset-asis)=
# 一 · 家底 (As-Is)

〔已确立〕实测（2026-09-04，`fylite@6a5ef61`）：

:::{table} 本篇要用到的现行部件，逐件写明它今天做到哪。
:name: tbl-e17-asis
:align: left

| 部件 | 今天 | 出处 |
| :--- | :--- | :--- |
| 命令词 | `fy` 有 **三条**：`app` / `data`（8 条子命令）/ `case`（4 条子命令）；组级 `--facts PATH` | `_cli.json` spec_version 2；`FYL-DESIGN-15` R-4 |
| 计划合成 | `case::compose`（多份按序，后者覆盖前者）+ `set_override`（`k=v`，值按 JSON 字面量解析，否则字符串）+ `bind_override`（`port=path`）；一处实现 | `case.rs` L290-330；`FYL-DESIGN-16` D-3 |
| 内核门 | `CASE_CODES` **3** 个：`evolve` · `zerod` · `transport`；拒绝落 `run_state: rejected` | `fyo_interface.rs` L156-160；`cli/case.rs` |
| 装置解析 | `facts::find("device", name)`：`--facts` → `$FY_FACTS_PATH` → 检出 `facts/` → `$FY_FACTS_BUNDLED`，**逐条决胜**；条目 = `<id>.jsonld` 文档 和/或 `<id>/`（`abox/` · `rights.json` · `abox/device.jsonld` 清单） | `facts.rs`；`cli/data.rs` `resolve_device` |
| 取数 | `fy data fetch --device D --ids a,b --shot N [--time T]`：清单 → `assembly::from_manifest` → mdsip；`Overrides {shot, slots, time, max_points, select}`；时间记法 `4.5` / `4:5` / `4,4.5,5` | `cli/data.rs` L351；`assembly.rs` L80；`FYL-DESIGN-14` L-10 |
| 离线测量 | fydata 有**炮级**条目 `abox/experiment/east/137985/`：`manifest.fyo.jsonld` + 逐时刻 `slice_<ms>ms.fyo.jsonld` + `thomson_<ms>ms.fyo.jsonld`（`fylite:MeasurementCorpus`） | fydata 检出 `abox/experiment`；`facts.rs` 抬头把 `experiment/<machine>/<shot>` 列为一个域 |
| 语料 | `docs/examples/`（用户裁定 2026-09-04：一个例子一个目录）：25 条 `fyo:ScenarioSpecification`，9 个 code，参数 IRI `code/<x>#<name>`；**没有一条声明输入端口** | `catalogue.jsonld`；`engine/cases.py` L129 |
| 参数词表 | 逐 code 实测：`reconstruction` 46 · `evolve` 114 · `zerod` 33 · `discharge` 23 · `transport` 19 · `breakdown` 17 · `pfwave` 14 · `series` 8 · `profile` 5；名字里有连字符（`ch-heat` · `mc-basis` · `turb-nky`） | `docs/examples/**/*.jsonld` |
| 页面预设 | 反演栏五条：`mag`（磁测量单独）· `kin`（动理学）· `ramp` · `live`（真实炮）· `twin`；`mag` = `{kin, neon, probefit, pointfit, farfit, vesselfit} = false` | `scenario-analysis.js` L1447-1480 |
| 环境变量 | Rust：`FY_FACTS_PATH` · `FY_FACTS_BUNDLED` · `FYLITE_KERNEL_LIB` · `FYLITE_MDSIP_SERVER` · `FYLITE_MDSIP_USER` · `USER` · 编译期 `FYLITE_APP_DIR`；Python：`FYLITE_DEVICE_DIR` · `FYLITE_RUN_DIR` · `FYLITE_SESSION` · `FY_RUNTIME_LIB` · `KEFIT_MDS_SERVER` · `KEFIT_LIMITER` · `RAYON_NUM_THREADS` · `XDG_CACHE_HOME` | `grep env::var` / `os.environ` 实测 |
| 线 | 四条：`design` · `control` · `model` · `analysis`，各带工具集；十件工具，五条浏览器专有栏 | `fylite.scenario.LINES` / `TOOLS` / `BROWSER_ONLY_BARS` |
:::

〔已确立〕**用户例句里的五样东西，今天各在哪。** `analysis` 这个词只在 Python 的
`LINES` 里；`--device east` 在 `fy data fetch` 与 `fy app` 上各有一种含义（清单 / URL 参数）；
`shot=` / `time=` 只有 `--set` 的写法；`--only-magnetic` **没有对应物**——最近的是页面预设
`mag`，它不是一个参数而是六个参数的一组值。也就是说：这一行命令**没有一个字**能被今天的
`fy` 接住，而它每一段都有一个现成的部件可以接。本篇做的是把它们接起来。

(fylite-preset-criteria)=
# 二 · 判据 (Criteria)

| | 判据 | 出处 | v1.0 变化 |
| :--- | :--- | :--- | :--- |
| **J-1** | **不因场景新增命令词**：场景、装置、预设都是**数据**；`fy` 只有 `app` / `data` / `run` / `list` 四条命令词，每条一个动词 | `FYL-DESIGN-15` R-4；v0.1 S-1 的否决 | v1.0 由「不新增命令词」改写为「一个词承载全部场景」；v1.1 `run` 取代 `case`，`list` 收拢发现面 |
| **J-2** | **一份规格**：静态语法进 `_cli.json`；**动态参数表进模板**，两者都不进代码 | `FYL-DESIGN-15` C-1 | 补第二半 |
| **J-3** | **离线可用**：给了 `--input` 或语料里有这发炮，命令**不得**开套接字；`--offline` 下永不 | `FYL-CONOPS-00` 包络 | 不变 |
| **J-4** | **跑不成也回一份记录**，缺什么点名，且说出是**哪个阶段**缺的 | 原 `fy case` 现行行为 | 补「阶段」 |
| **J-5** | **加一条场景 = 加一份模板文档**，加一条预设 = 加一份计划文档 | `FYL-DESIGN-16` K-（门只认文档） | 不变 |
| **J-6** | **同词同义**：`--device` / `--shot` / `--time` 在 `fy` 的每条命令上一种含义、一种记法 | `fy data fetch` 已用这三个词 | 不变 |
| **J-7** | **合成只在一处，入口也只有一个**：合成器是 Rust 库模块 `crate::case`，命令词只有 `run`；两种位置参数形（线 / 计划文件）走同一段代码 | `FYL-DESIGN-16` D-3 | v1.0 新增；v1.1 补「入口只有一个」 |

(fylite-preset-grammar)=
# 三 · 语法 (Grammar)

〔已确立·设计〕

```text
fy run <target> [<selector>...] [<parameter>...] [<option>...]
fy list [<kind> [<name>...]] [--line L] [--json]     → 发现面（tbl-e17-list）；run 自己没有 --list / --show

target    ::= <line> [<scenario>]          ; 场景形
            | <plan> [<plan>...]           ; 计划文件形（原 fy case run）：含 `/` 或以 .json/.jsonld/.yaml 结尾（E-2）
line      ::= "analysis" | "model" | "design" | "control"
scenario  ::= <name>                       ; 缺省由线决定（E-17）
selector  ::= "--device" ID | "--preset" NAME | "--plan" FILE | "--input" FILE | "--bind" PORT=FILE
parameter ::= <key> "=" <value>            ; shot=123456
            | "--" <key> "=" <value>       ; --only-magnetic=true   （与上一行同义）
            | "--" <key>                   ; --only-magnetic        ≡ only_magnetic=true
            | "--no-" <key>                ; --no-only-magnetic     ≡ only_magnetic=false
option    ::= 固定选项（tbl-e17-fixed），值用 "=" 或空格
key       ::= [a-z][a-z0-9_-]*             ; `-` 与 `_` 等价（E-12）
value     ::= JSON 字面量 | 裸字符串 | 时间选择（`4.4` · `4:5` · `4,4.5,5`）
```

〔已确立·设计〕**两种形，一条路。** 场景形由线与场景选出模板；计划文件形（v1.1，原 `fy case run`）
把给出的计划按序合成，模板由合成后计划的 `prescribes_code` 末段解析（`code/transport` →
`scenario/transport`），于是 `key=value` 在两种形上**同样受模板校验**；找不到模板时开放参数
**不校验直接透传**（等于原 `--set`），`--dry-run` 把它们标成 `cli (unchecked)`。第一个位置参数
是四个线词之一就是场景形，否则按 E-2 判路径；两者都不是时按名拒绝并列出四个线词。

〔已确立·设计〕**三类记号，三种归属。** 位置参数（线与场景，或计划文件）；**固定选项**是规格里
写死的那些（`_cli.json`，解析器认识）；**参数**是模板里的那些（解析器**不认识**，只收集）。
用户例句里 `--device east` 是固定选项，`shot=123456` / `time=4.4` 是**通用参数**（每个
消费测量的场景都收），`--only-magnetic=true` 是**场景参数**（反演模板的一个开关）。

:::{table} `run` 的固定选项。★除 `--device` / `--shot` / `--time` 外，没有一个与物理有关——它们都是**资源**（文件、路径、格式、内核、连接）。
:name: tbl-e17-fixed
:align: left

| 选项 | 取值 | 作用 | 同词 |
| :--- | :--- | :--- | :--- |
| `--device ID` | facts 里 `device` 域的标识，或一份 `device.jsonld` 路径 | 装出整份装置文档绑到 `device` 端口；补装置相关缺省（E-14） | `fy data fetch --device` |
| `--shot N` / `--time T` | 整数 / 时间选择 | 与 `shot=N` / `time=T` **同一个参数**（E-12：固定选项名优先）；写成旗标是为了与 `fetch` 同形 | `fy data fetch --shot/--time` |
| `--preset NAME` | 预设名或计划文件路径（E-2） | 在模板与装置之上叠一份具名计划 | — |
| `--plan FILE`（可重复） | 计划文件 | 场景形下的显式计划，按序叠在预设之上（计划文件形直接把文件写成位置参数） | 原 `fy case run <plans>` |
| `--input FILE` | 文档 | 绑到场景模板声明的**主输入端口**（反演 = `measurements`，`profile` = `points`，`vstab` = `equilibrium`） | `--bind <主端口>=FILE` 的糖 |
| `--bind PORT=FILE`（可重复） | 端口绑定 | 其余端口 | 原 `fy case run --bind` |
| `--code IRI` | code IRI | 一份计划带多个 code 时选一个（计划文件形） | 原 `fy case --code` |
| `--cases PATH`（可重复） | 语料根 | 预设 / 模板的搜索路径前置（E-3） | `--facts` 的同构 |
| `--facts PATH`（可重复） | 语料根 | 装置 / 实验条目的搜索路径前置 | `data` 组级同名 |
| `-o, --record DIR` | 目录 | 记录目录；缺省 `$FYLITE_RUN_DIR/<戳>-<场景>/`（E-16）；给了 `--json` 而不给 `-o` 时不落目录 | 原 `fy case run -o` |
| `--format F` | `jsonld` / `hdf5` / `netcdf` / `imas-hdf5` | 数据集格式 | 原 `fy case run --format` |
| `--kernel PATH` | `.so` | 内核 | 原 `fy case --kernel` |
| `--mdsip HOST[:PORT]` / `--mds-user NAME` / `--timeout-ms MS` | 连接 | 取数阶段的连接（E-15） | `fy app --mdsip`；`fetch --host/--port/--mds-user/--timeout-ms` |
| `--offline` | 旗标 | 取数阶段**禁止**开套接字；解析不到测量即拒绝（J-3） | — |
| `--dry-run` | 旗标 | 合成并打印计划与解析表，不取数、不装内核（E-19） | `fetch --dry-run`；原 `fy case plan` |
| `--json` / `--quiet` | 旗标 | 机器可读 / 不打进度。`--json` 的含义随动作定：与 `--dry-run` 是合成好的计划，单独用是**记录连数据集内联打到 stdout**（原 `fy case json`） | 各命令同名 |
:::

〔已确立·设计〕**原 `case` 四条子命令的去处**（v1.1）：

:::{table} 迁移表。左列自本版起按名拒绝，拒绝话术指向右列（E-23）。
:name: tbl-e17-migration
:align: left

| 原写法 | 新写法 | 说明 |
| :--- | :--- | :--- |
| `fy case describe [--kernel P]` | `fy list kernel [--kernel P]` | 内核认哪些 code、哪些 entry、各自的声明块 |
| `fy case plan P… [--set k=v] [--bind …] [--code C] [--json]` | `fy run P… [k=v …] [--bind …] [--code C] --dry-run [--json]` | 合成到内核之前为止；`--json` 打合成好的计划 |
| `fy case run P… [--set k=v] … -o DIR [--format F]` | `fy run P… [k=v …] … -o DIR [--format F]` | 同一段代码；`--set` 整个撤除（E-5） |
| `fy case json P… [--kernel P]` | `fy run P… --json [--kernel P]` | 记录连数据集内联到 stdout；不给 `-o` 就不落目录；退出码同 E-20 |
| `fy case list` / `fy case show N`（v0.1 E-4，未落地） | `fy list presets` / `fy list presets N` | 预设是 `list` 的一类 |
| `fy data facts [--roots] [domain]` | `fy list facts [--roots] [domain]` | 原样搬家：语料根与逐条条目的来源根；`data` 从此只搬数据、不回答「有什么」 |
| `fy run --list` / `fy run … --show`（v1.1 草案，未落地） | `fy list scenarios [N]` | 发现面只在 `list` 上 |
:::

〔已确立·设计〕**`fy list`：一条只读的命令词，每类语料一条子命令（E-24）。** 不给子命令时打总览
（语料根 · 各类条目的数目 · 内核找没找到）；给子命令打该类的清单；子命令后再给名字，打那一条
的全部。**永不**开套接字；只有 `kernel` 与 `scenarios` 的「门认不认」一列会装内核，找不到内核时
那一列写「内核未找到」而不是失败。组级选项 `--facts` / `--cases` / `--kernel` / `--json`。

:::{table} `fy list` 的子命令。「来源」列说数据从哪个部件来——`list` 自己不持有任何清单。
:name: tbl-e17-list
:align: left

| 子命令 | 打什么（清单行） | 给名字时 | 来源 | 原来在 |
| :--- | :--- | :--- | :--- | :--- |
| `devices [<id>]` | facts `device` 域：标识 · 供它的根 · 卡片 / 清单（有清单才抓得动）· 许可（`rights.json` / `dataset_fair`）· 公开 / 内部 | 一台的全部：清单的 `epochs`、`providers` 及各自缺省、绑定的 IDS 计数、许可原文 | `facts::entries("device")` · `Entry::manifest_path` / `rights_path` · `assembly::from_manifest`（只读清单，不装文档） | 散在 `data facts device` 与 `fetch --dry-run` |
| `experiments [<device> [<shot>]]` | facts `experiment` 域：装置 · 炮 · 切片数 · 来源根 | 一发炮的切片时刻表（`fylite:slices`）、失败与缺席节点 | `facts::entries("experiment")` · `manifest.fyo.jsonld` | 无 |
| `scenarios [<name>] [--line L]` | 模板：名 · 线 · code · **门认不认**（E-8）· 主输入端口 · 通用参数 · 模板来源（内嵌 / 语料路径） | 参数表全表（名 · 类型 · 缺省 · `from_device` · 范围）· 开关及其展开 · 端口 | 模板目录 + `lines.jsonld` + 内核 code 表 | v1.1 草案 `run --list` / `--show` |
| `presets [<name>] [--line L] [--scenario S]` | 语料预设：名 · 场景 · 装置 · 可跑与否及理由 · 来源根 | 那份计划文档（合成前，原样） | `--cases` 四级路径 + `catalogue.jsonld` | v0.1 `case list` / `case show` |
| `facts [<domain>] [--roots]` | 语料根（优先级序）；给域时逐条条目与供它的根 | — | `facts::roots` / `problems` / `entries` | `data facts`（原样搬家） |
| `kernel` | 内核路径与校验和 · `CASE_CODES` · entry 表 · 每个 entry 的声明块 | — | `Kernel::load` · `fyo_interface::BLOCKS` | `case describe` |
| `lines` | 四条线 · 缺省场景 · 各线的场景数 | — | `lines.jsonld` | 无 |
:::

〔已确立·设计〕**为什么是一条命令词而不是各处一个 `--list`。** 「有什么」在 `fy` 里有六类答案，
而它们的形一样：一列名字、每个名字来自哪个根、今天能不能用。把六个 `--list` 分挂在三条命令上，
用户要先知道装置归 `data`、场景归 `run`、内核归 `case` 才问得出口；`list` 把那层先验知识收掉。
★它是**只读**的：不合成、不取数、不写记录——这条边界让它可以在任何机器上、没有内核、没有网络
时回答，而 `run --dry-run` 仍然是「这条命令**会**做什么」的那一问，两者不重叠。

〔已确立·设计〕**用户例句的解析轨迹**（{numref}`tbl-e17-trace`）——这张表就是 `--dry-run`
要打印的东西：

:::{table} `fy run analysis --device east shot=123456 time=4.4 --only-magnetic=true` 逐步发生什么。「今天」列按 P 期。
:name: tbl-e17-trace
:align: left

| 步 | 记号 | 判为 | 结果 | 今天 |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `analysis` | 线 | 缺省场景 `reconstruction`（`lines.jsonld`，E-17） | P1-a |
| 2 | （模板） | — | `scenario/reconstruction.jsonld`：46 个基础参数 + 开关 `only_magnetic` / `kinetic` + 端口 `device` · `measurements` · `pressure`（可选） | P1-a |
| 3 | `--device east` | 固定选项 | `facts::find("device","east")` → 根 R；`from_manifest` 装出 `fyo:DeviceDescription`（提供者取清单缺省：`pf_active: base` · `wall: base` · …）→ 绑 `device` 端口；`from_device` 表补 `basis` 等缺省（E-14） | P1-b |
| 4 | `shot=123456` `time=4.4` | 通用参数 | 测量解析（E-15）：无 `--input` → 查 `experiment/east/123456` 的 `slice_04400ms` → 无 → 取数：`ids` = 模板 `measurements` 端口声明的 IDS，`Overrides{shot, time: 4.4}` → `measurements.fyo.jsonld` 落进记录目录 → 绑 `measurements` 端口 | P1-c |
| 5 | `--only-magnetic=true` | 参数（开关） | 名归一 `only_magnetic`；模板 `switches` 里有 → 展开 `{kin,neon,probefit,pointfit,farfit,vesselfit} = false`，来源记 `cli:switch only_magnetic` | P1-a |
| 6 | （合成） | — | `crate::case::compose([模板, 装置缺省, 预设(无), --plan(无)])` + `set_override` × 6 + `bind_override` × 2（Rust 库模块，原 `case` 命令的合成器）；`plan.jsonld` 写出 | P1-a |
| 7 | （门） | — | `code/reconstruction` **今天不在 `CASE_CODES`** → 记录 `run_state: rejected`，`refusal.stage: kernel`，退出 1（E-20）；P2-b 之后出结果 | P2-b |
:::

〔评注〕**为什么例句里 `shot=` 不写成 `--shot`，而 `--only-magnetic` 又写成旗标。** 两种写法
在本设计下**同义**（E-12），例句只是各用了一种。规则是记号的**形**不决定归属，**名**决定：
`shot` 与 `time` 是固定选项名（与 `fetch` 同词），所以不论写 `shot=1` 还是 `--shot 1`，
都是那个固定选项；`only_magnetic` 不是固定选项名，所以不论写 `only_magnetic=true` 还是
`--only-magnetic`，都交给模板。

(fylite-preset-parsing)=
# 四 · 两段解析 (Two-Stage Parsing)

〔已确立·设计〕**第一段（静态）**由规格驱动，与今天 `cli/mod.rs` 的解析器同一个：识别
位置参数与固定选项（C-4 的一切规则照旧：类型、`choices`、`required`、未知**固定选项**按名
拒绝、退出 2）。差别只有一处：规格在 `run` 命令上声明 `"open_parameters": "scenario"`
（{numref}`tbl-e17-spec`），解析器遇到**不是固定选项**的 `--key=value` / `--key` / `--no-key`
/ `key=value` 记号时**不拒绝**，按出现顺序收进一张 `(key, raw_value, spelling)` 表。
没有这条声明的命令（`app` / `data`）行为不变。

〔已确立·设计〕**第二段（动态）**在 `run.rs` 里、模板加载之后：逐条对照模板的参数表——

| 检查 | 通过 | 不通过 |
| :--- | :--- | :--- |
| 名字 | 归一后（E-12）在基础参数、开关或通用参数里 | 按名拒绝，列最接近的三个名字（与 E-2 同一算法），退出 2，**不落记录** |
| 类型 | `bool` / `int` / `float` / `str` / `time` / `choice[…]`，按模板 | 拒绝并说出期望的类型与收到的字面量 |
| 范围 | 模板给了 `min` / `max` / `choices` 时检查 | 拒绝并说出范围 |
| 重复 | 同名后者覆盖前者（与 `--set` 同） | — |
| 开关与基础参数冲突 | 显式给的基础参数**胜过**开关展开的值（E-18） | — |

〔已确立·设计〕**值的解析与 `--set` 同一函数**：JSON 字面量能解析就按字面量（`true` ·
`123456` · `4.4` · `"raw"`），否则整段当字符串（`basis=delivered`）。**时间选择**是唯一的
例外类型：`time` 的记法沿 `FYL-DESIGN-14` L-10（`4.4` 一个点、`3:5` 一个窗、`3,3.5,4`
一个表），**不**按 JSON 解析（`3:5` 不是 JSON）。模板把一个参数标成 `type: time`，它就走这条路。

〔已确立·设计〕**为什么不把模板参数写进 `_cli.json`。** 写得进：`reconstruction` 46 个参数
逐条写成 `args` 也就是四百行 JSON。不写的理由是 J-5——参数表**属于场景**，而场景是数据；
把它抄进规格，规格与模板就是两份，某一天它们会不一样，而先发现的是敲错了名字的那个人。
规格只知道「这条命令后面跟着一张开放的参数表」，模板知道表里有什么。**闸子从两个方向查**
（{ref}`fylite-preset-stages`）。

(fylite-preset-precedence)=
# 五 · 合成次序与来源 (Precedence and Provenance)

〔已确立·设计〕自低到高，后者覆盖前者；**每个值带 `from`**（写进 `plan.jsonld` 每条
`spo:ParameterSetting` 的 `fylite:from` 字段），`fy list scenarios <名>`（模板与装置两层）与
`run --dry-run`（六层全部）逐列打印：

| 层 | 来源 | `from` 值 | 说明 |
| ---: | :--- | :--- | :--- |
| 1 | **模板缺省** | `template:<scenario>` | 模板的 `parameters[]` 里带 `literal_value` 的那些 |
| 2 | **装置** | `device:<id>@<root>` | 模板 `from_device` 表按 fyo 路径从装置文档取值（E-14）；取不到就**不设**，不报错 |
| 3 | **预设** | `preset:<name>@<root>` | `--preset`；一份计划文档，可含自己的 `performed_on`（装置）——与 `--device` 不一致时**拒绝**，不猜 |
| 4 | **显式计划** | `plan:<path>#<n>` | `--plan`，按序 |
| 5 | **命令行** | `cli` / `cli:switch <名>` | 参数与开关展开；开关展开的值低于显式参数（E-18） |
| 6 | **端口绑定** | `cli:input` / `cli:bind` / `resolved:<source>` | 端口不是参数，单列；`resolved:` 记测量文档从哪来（E-15） |

〔已确立·设计〕**环境变量不在这张表里。** 它们供资源（路径、内核、连接、记录目录），
**不供任何物理参数**（E-16）。一个 `FY_DEFAULT_SHOT` 会让同一条命令在两台机器上算两发炮，
而记录里看不出为什么。

〔已确立·设计〕**两种形的等价式**（J-7，也是门禁 ①的断言）：

```bash
fy run analysis --device east shot=123456 time=4.4 --only-magnetic=true -o rec/
# ≡（P1 之后逐字节相同的 plan.jsonld）——计划文件形，原 `fy case run` 的写法
fy run scenario/reconstruction.jsonld [device-defaults.jsonld] \
   shot=123456 time=4.4 \
   kin=false neon=false probefit=false pointfit=false farfit=false vesselfit=false \
   --bind device=rec/device.fyo.jsonld --bind measurements=rec/measurements.fyo.jsonld -o rec/
```

场景形比计划文件形多做的只有**解析**：把线变成模板、把装置名变成文档、把炮号变成文档、
把开关变成参数。合成与运行是同一段代码（E-21）。v1.0 把右边写成 `fy case run … --set …`；
v1.1 起那条命令词没有了，右边就是 `run` 自己的另一种形。

(fylite-preset-device)=
# 六 · 装置信息怎么进来 (Applying the Device Facts)

〔已确立·设计〕**两条路，各有边界：**

**路一：整份装置文档绑到 `device` 端口。** `FYL-DESIGN-16` K-8 已裁：装置自 A-Box 经中间层
以整份 `fyo:DeviceDescription` 进内核，内核不收路径。`run` 复用 `cli/data.rs` 的
`resolve_device`（名字 → facts 条目 → `abox/device.jsonld` 清单）与 `assembly::from_manifest`
（清单 → 提供者选择 → 文档）。**提供者取清单的 `default`**（EAST 清单实测：`pf_active: base`
· `wall: base`）；要换提供者写参数 `provider.<ids>=<name>`（通用参数，见
{numref}`tbl-e17-common`），不另开旗标。装出的文档**写进记录目录**（`device.fyo.jsonld`），
记录因此不依赖 facts 路径的下一次状态。

★**只有卡片、没有清单的装置**（facts 里多数装置：`<id>.jsonld` 文档在、`abox/device.jsonld`
不在），路一绑的是那份卡片文档本身。模板的 `device` 端口声明它要的是**卡片够不够**
（`requires: card | manifest`）：`transport` / `evolve` / `zerod` 只要几何与标称量，卡片够；
`reconstruction` 要线圈几何、探针与磁通环通道表，**要清单**——给了只有卡片的装置时按名拒绝
（`refusal.stage: device`），话术沿 `resolve_device` 现行的那句「that device is described by a
card, not by a manifest」。

**路二：模板的 `from_device` 表给参数缺省。** 一条场景的某些参数本来就是装置量
（`transport` 的 `rmaj` / `amin` / `kappa` / `delta` / `bunit`；`zerod` / `discharge` /
`breakdown` / `pfwave` 的 `r0` / `a` / `kappa`；`reconstruction` 的 `basis`）。模板里
一张表把参数名映到装置文档里的 fyo 路径，`run` 在第 2 层按表取值：

```json
"fylite:from_device": {
  "basis": "fylite:channel_basis",
  "r0":    "[待定：fyo:DeviceDescription 里的大半径路径]",
  "a":     "[待定]"
}
```

〔待定〕表里的**路径**逐场景待定——它们取决于 `fyo:DeviceDescription` 在 fyo v0.9 里的
形，本篇不从记忆里写 fyo 路径。**机制**已定：取到就设、`from` 记 `device:`；取不到**不设**
（模板缺省或用户值生效）；**用户显式给的值永远胜过装置**（第 5 层 > 第 2 层）。

〔已确立·设计〕**装置与预设不一致时拒绝。** 预设 `evolve-east-hmode` 的 `performed_on`
是 EAST；`fy run model --preset evolve-east-hmode --device iter` 是一个矛盾，不是一个覆盖。
拒绝并说出两边各是谁（`refusal.stage: compose`）。不给 `--device` 时预设的装置生效。

(fylite-preset-measurements)=
# 七 · 测量文档怎么来 (Resolving the Measurements)

〔已确立·设计〕消费测量的场景（模板声明 `measurements` 端口）按三级解析，**先到先得**：

| 级 | 条件 | 来源 | `from` |
| ---: | :--- | :--- | :--- |
| 1 | 给了 `--input FILE` | 那份文档（fyo / JSON-LD / IMAS 形 JSON-YAML，经 `data` 层的同一读者） | `cli:input` |
| 2 | 给了 `shot=`，facts 里有 `experiment/<device>/<shot>` 条目 | 该炮的离线切片：按 `time` 选最近的 `slice_<ms>ms.fyo.jsonld`（容差由清单给，缺省 ±1 ms；超出容差**不取邻片**，降到第 3 级）；`time` 是窗或表时逐片 | `resolved:experiment/<device>/<shot>@<root>` |
| 3 | 给了 `shot=`，未 `--offline`，装置有清单 | **取数**：`from_manifest(清单, ids, provider, host, port, Overrides{shot, time})` + `assemble`——与 `fy data fetch` 同一段代码；`ids` 取模板 `measurements` 端口声明的清单（反演：`magnetics, pf_active, tf`；动理学开关开时再加 `interferometer` 与 Thomson 所在的 IDS〔待定：EAST 绑定表今天有 `interferometer` 24 条，Thomson 无绑定〕） | `resolved:mdsip://<host>/<tree>?shot=…` |
| — | 都不成立 | 拒绝：`refusal.stage: measurements`，话术说出三级各为何没走通 | — |

〔已确立·设计〕**取回的文档落地再进门。** 第 3 级取回的测量**先写** `measurements.fyo.jsonld`
进记录目录，再绑端口。于是同一次分析可以离线重放：

```bash
fy run analysis --device east --input rec/measurements.fyo.jsonld --only-magnetic=true --offline
```

〔已确立·设计〕**这一条修订 E-6，但不推翻它的三条理由**：①离线包络——第 1、2 级不开
套接字，`--offline` 下第 3 级不存在；②可缓存——取回的文档就是文件，第 1 级吃它；
③失败面分开——`refusal.stage` 把「取不到」与「算不出」分成两个词。计划文件形（原 `fy case`
的用法）**仍然**不开套接字：它不给 `shot=`，第 3 级就不存在；开套接字的是一个**前置阶段**，
且只在「给了 `shot=`、前两级落空、未 `--offline`」三件同时成立时发生。

〔已确立·设计〕**连接参数的次序**：`--mdsip` > `$FYLITE_MDSIP_SERVER` > 清单里提供者的
`uri`；用户名 `--mds-user` > `$FYLITE_MDSIP_USER` > `$USER`。与 `fy app` / `fy data fetch`
**同一个次序**（J-6）。★`KEFIT_MDS_SERVER` 是 Python 库的旧名，`fy` **不读**（E-16）。

〔已确立·设计〕**`time` 的三种形一种语义。** `series` 场景收 `time=3:5`（窗）或 `time=3,3.5,4`
（表），每个点一片；`reconstruction` 收一个点；给错形时按类型拒绝（模板标 `time: point`
或 `time: selection`）。一个点、一个窗、一个表在 `fy data fetch --time` 上已是这三种写法——
这里不发明第四种。

(fylite-preset-template)=
# 八 · 场景模板 (Scenario Templates)

〔已确立·设计〕一条场景模板是一份 `fyo:ScenarioSpecification`（**与计划同一个类**：模板就是
一份把词表说全了的计划），外加本仓 `fylite:` 词的一个扩展块。反演模板的形（节选；
基础参数照抄语料现行的 `code/reconstruction#<name>` 词表，不新造）：

```json
{
  "@context": ["../context.jsonld"],
  "id": "scenario/reconstruction",
  "type": "fyo:ScenarioSpecification",
  "title": {"zh": "平衡反演", "en": "Equilibrium reconstruction"},
  "prescribed_task_kind": "fyo:ExperimentAnalysisTask",
  "prescribes_code": {"id": "code/reconstruction", "type": "spo:Code", "name": "fylite"},
  "fylite:lines": ["analysis"],
  "fylite:ports": {
    "device":       {"requires": "manifest", "type": "fyo:DeviceDescription"},
    "measurements": {"primary": true, "ids": ["magnetics", "pf_active", "tf"]},
    "pressure":     {"optional": true, "note": "profile 场景的产物；带 derived-from-reconstruction 来源者拒收"}
  },
  "fylite:common": ["shot", "time"],
  "fylite:vocabulary": {
    "basis":    {"type": "choice", "choices": ["delivered", "raw"], "from_device": "fylite:channel_basis"},
    "kin":      {"type": "bool"},
    "neon":     {"type": "bool"},
    "pointfit": {"type": "bool"},
    "probefit": {"type": "bool"},
    "farfit":   {"type": "bool"},
    "vesselfit":{"type": "bool"},
    "mcn":      {"type": "int", "min": 0, "note": "后验采样成员数；0 = 不跑后验"},
    "maxit":    {"type": "int", "min": 1},
    "kw":       {"type": "float", "min": 0},
    "kpts":     {"type": "int", "min": 1}
  },
  "fylite:switches": {
    "only_magnetic": {"kin": false, "neon": false, "probefit": false, "pointfit": false, "farfit": false, "vesselfit": false},
    "kinetic":       {"kin": true,  "neon": true,  "probefit": false, "pointfit": true,  "farfit": false, "vesselfit": false}
  },
  "parameters": [
    {"type": "spo:ParameterSetting", "sets_parameter": "code/reconstruction#basis", "literal_value": "delivered"},
    {"type": "spo:ParameterSetting", "sets_parameter": "code/reconstruction#maxit", "literal_value": 800}
  ]
}
```

〔已确立〕两个开关的展开值**逐字取自** `scenario-analysis.js` 的页面预设 `mag` 与 `kin`
（L1447-1455），不是本篇发明的组合；`kin` 预设另带滑块值 `kw: 0.2` · `kpts: 9`，那两个
留给用户或预设，开关只展开布尔。

〔待定〕`fylite:vocabulary` / `fylite:switches` / `fylite:ports` / `fylite:from_device`
在 fyo / spo 本体里的对应类**未定**（spo 有 `ParameterSetting`；「参数**声明**」是否已有类，
本篇未核验）。落地先用 `fylite:` 词，晋升本体是 fydoc 的一条工单，不阻塞 P1。

〔已确立·设计〕**模板住在哪、预设住在哪（E-22）。** 模板：`docs/examples/scenario/<name>.jsonld`
（语料根下一个新目录），**同时**在构建时内嵌进 `fy`（与 `_cli.json` 同一机制：一张
`include_str!` 表，`tools/make-scenario-embed.py` 生成——或并入 `make-app-embed.mjs` 的名单）。
搜索路径上找到的同名模板**覆盖**内嵌的那份（排障用；`fy list scenarios` 打印每份的来源）。预设：语料路径
`--cases` → `$FY_CASES_PATH` → 检出 `docs/examples/` → `$FY_CASES_BUNDLED`，与 facts 四步
同构（E-3）。**理由**：模板与内核的 code 表是一对，两者错版的后果（模板说有、门说无）由
门禁 ②当场抓住；预设是数据，随语料走。

〔已确立·设计〕**每线的缺省场景在数据里（E-17）**：`docs/examples/scenario/lines.jsonld`：

| 线 | 缺省场景 | 理由 |
| :--- | :--- | :--- |
| `analysis` | `reconstruction` | S-L2 的首要动作；用户例句 |
| `model` | `transport` | S-L1 里今天门认的那条；`evolve` 参数最多（114），不宜做缺省 |
| `design` | `zerod` | S-L4 的分析档；门认 |
| `control` | `vstab` → **落成 `breakdown`** | S-L3 里唯一有内核入口（`vstab` entry）的；但它没有 code 与词表，因而没有模板（as-built A-1），而一条线的缺省**必须**是一份存在的模板——落成 `breakdown`（击穿与上升段同属 S-L3，指南「稳定性与控制」有它一章）。`vstab` 一有 code，缺省改回去是改一份文档 |

(fylite-preset-catalogue)=
# 九 · 场景目录 (The Scenario Catalogue)

〔已确立〕逐条对账**文档明确涉及的每一个场景**：`FYL-CONOPS-00` S-L1..S-L5、三页十三条栏
（`FYL-DESIGN-09` / `-10` / `-12`）、语料 9 个 code、`TOOLS` 10 件、指南五章（平衡反演 ·
正解与演化 · 稳定性与控制 · 约束与权重 · 输入模式）。「模板」列：✅ 设模板；⤵ 并入另一
场景（写成它的参数）；✗ 不设模板并在 `lines.jsonld` 里给出理由（E-8）。「门」列：✅ 今天
`CASE_CODES` 认；⛔ 需内核补 code（P2）；「—」无内核路径。

:::{table} 场景目录。「主输入」是 `--input` 绑的端口；「通用」是它收的通用参数。
:name: tbl-e17-catalogue
:align: left

| 线 | 场景 | 问什么 | 文档出处 | 栏 / code / 工具 | 主输入 · 通用 | 模板 | 门 |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| analysis | **`reconstruction`** | 给一发炮的磁测量（+动理学约束），位形与内部剖面是什么；开关 `only_magnetic` / `kinetic`；`mcn>0` 即后验 | S-L2；`-12` 栏二 · 后验按钮 · P-22；指南「平衡反演」「约束与权重」 | `reconstruction` / `code/reconstruction`(46) / `analysis.reconstruction`；内核扁平入口 `recon` · `recon_mc` | `measurements` · `shot` `time`(点) | ✅ | ⛔ P2-b |
| analysis | **`series`** | 一发炮的一段时间逐片反演，标量随时间怎么走 | `-12` 栏三；`run_series` | `series` / `code/series`(8) / `recon_rs.run_series`；扁平入口 `recon_series` | `measurements`(逐片) · `shot` `time`(窗/表) | ✅ | ⛔ P2-c |
| analysis | **`profile`** | 一组带误差棒的测点，剖面与阶数是什么（GCV） | `-12` 栏一；指南「压强约束从哪来」 | `profile` / `code/profile`(5) / `analysis.profit`；entry `profit` 已在 | `points` · （`shot` `time` 取 Thomson〔待定〕） | ✅ | ⛔ P2-a |
| analysis | `posterior` | 不确定度 | `-12` P-9 · 后验按钮；指南「不确定度量化」 | 扁平入口 `recon_mc` | — | ⤵ `reconstruction` 的 `mcn` / `mc-*` | — |
| analysis | `batch` | 一队反演 | `-12` 栏四 | 浏览器专有（队列） | — | ✗ 队列是宿主机制：命令行上是 `series` 或一个 shell 循环 | — |
| analysis | `loop` | 反演—输运自洽外环（EFIT↔NEO） | S-L2 批式档；指南「自洽外环」 | `analysis.loop.self_consistent` | `shot` `time` | ✗ 指南自述「在本分发里跑不起来」；库路径复原后再设 | — |
| analysis | `sxr` | 软 X 射线层析 | S-L2 一句提及 | 无工具、无栏、无语料 | — | ✗ 文档提及、无实现 | — |
| model | **`transport`** | 固定几何下一次定态解，剖面长什么样 | S-L1；`-10` 栏一 | `transport` / `code/transport`(19) / `model.transport` | （无必需端口；`device` 可选补几何） | ✅ | ✅ |
| model | **`evolve`** | 含时演化：热通道推进到稳态，功率平衡怎么走；`couple=N` 即平衡交替 | S-L1；`-10` 栏二；指南「正解与演化」 | `evolve` / `code/evolve`(114) / `model.evolve`；entry `evolve_heat`；`ENTRY_SCOPE` 里 `beam` · `lh` · `wave` · `ipctl` · `ch-density` … 为 unsunk，给了按名拒绝 | （同上） | ✅ | ✅ |
| model | `coupled` | 平衡—输运静态交替 | `-10`（2026-08-26 栏让给 `evolve`） | `model.coupled`，无栏 | — | ⤵ `evolve` 的 `couple` | — |
| model | `tglf` | 局域线性稳定性与准线性通量 | S-L1 湍流闭包；`TOOLS['tglf']` | `model.tglf`；两条栏里的 `closure=turbulent` 模式 | `inputs` | ⤵ `transport` / `evolve` 的 `closure` · `turb-*`；独立模板 P2-c 候选 | — |
| model | `interp` | 剖面插到内核网格；功率平衡反演 χ | `-10` 栏 `interp` | `code/interpretive`（worker 的 `interpRun` 经文档门；2026-09-05 K-3 第八刀） | — | ✗ 工具不是场景：门上的 code，不出 `fy` 场景模板 | — |
| model / design | **`zerod`** | 0-D 放电：这套相位表与波形落在运行域哪里；`uqon` 即不确定度 | S-L4；`-09` 栏一 | `zerod` / `code/zerod`(33) / `model.zerod` | （`device` 可选） | ✅ | ✅ |
| design | **`discharge`** | 静态线圈反解 / 自由边界正解：目标形状 → 线圈电流 | S-L1 平衡正演 · S-L5 静态反解；`-09` 栏二；指南「前向自由边界正解」 | `discharge` / `code/discharge`(23) / `design.discharge` | `device`(要线圈几何) | ✅ | ⛔ P2-c |
| design | **`breakdown`** | 击穿零场设计与逐通道限值 | S-L3 / S-L4；`-09` 栏四；指南「击穿与上升段」 | `breakdown` / `code/breakdown`(17) / `design.breakdown` | `device` | ✅ | ⛔ P2-c |
| design | **`pfwave`** | PF 电源整定与波形 | `-09` 栏三 | 浏览器专有组合，无 Python 入口；语料 `pulse-iter` 用 `code/pfwave`（14 个参数） | `device` | ✅（as-built A-1：它有 code 与词表，`pulse` 没有） | ⛔ P2-c |
| design | `pulse` | 整脉冲前馈电压设计（GSPulse 型）与逐片校验；重线性化并入 | `-09` 栏五 · 批式 C；指南「前馈轨迹设计」「形状响应矩阵」 | `pulse` 栏 / `design.pulse.feedforward`（`code/pulse`，2026-09-05；`design_trajectory` · `verify_trajectory` 随 EFIT 谱系求解器退役） | `measurements`(初始平衡) · `device` | ✗ 无 code IRI（语料的 `pulse-iter` 用 `code/pfwave`）；模板要一个真实的 code——P2-c（as-built A-1） | — |
| design | `sim` | 交互时间推进（滑块） | `-09` 栏六 | 浏览器专有 | — | ✗ 交互档不是批式动作（P-1） | — |
| design | `feasible` | 二维参数扫描的可行域 | S-L5；`TOOLS['feasible']` | `design.feasible`，无栏、无语料 | `device` | 待设（P2-c）：扫描轴写成参数 `axis1.*` · `axis2.*`〔待定〕 | — |
| control | `vstab` | 刚体 n=0 垂直稳定：k · k_ideal · γ | S-L3；指南「n=0 垂直不稳定性」 | `control.vstab`；entry `vstab` 已在 | `equilibrium` · `device`(线圈 A·匝) | ✗ 有内核 entry，无 case code 与词表——P2-c（as-built A-1） | — |
| control | `vertical` | 垂直反馈回路闭环 | 指南「垂直反馈回路」 | 退役（2026-09-06）：`close_vertical_loop` 归内核仓测试树；对象模型 `vertical_system` 走 `code/vstab` | `equilibrium` · `device` | 待设：无栏无语料；参数词表要先立 | — |
| control | `evolution` | 电压驱动的自由边界位形演化 | S-L3；指南「电压驱动的位形演化」 | 退役（2026-09-06）：`control.evolution` 归内核仓测试树；前馈电压与电路走 `code/pulse` | `measurements` · `device` | 待设 | — |
| — | `benchmark` | 跨码对标 | 指南「跨码对标」；`-12` V&V 登记册 | `engine.benchmark` | — | ✗ 登记册不是场景 | — |
:::

〔已确立〕**覆盖检查。** 十三条栏逐条在表里（`profile` `reconstruction` `series` `batch` /
`evolve` `transport` `interp` / `zerod` `discharge` `pfwave` `breakdown` `pulse` `sim`）；
9 个 code 逐条在（`reconstruction` `series` `profile` `transport` `evolve` `zerod` `discharge`
`breakdown` `pfwave`）；10 件工具逐条在（`discharge` `breakdown` `feasible` `vstab` `zerod`
`transport` `coupled` `evolve` `tglf` `reconstruction`）；S-L1..S-L5 各至少一条设模板的场景；
指南五章的每个二级标题各落到一行。**没有一条场景只在散文里。**

:::{table} 通用参数：每个模板经 `fylite:common` 声明它收哪几个；不声明的场景给了就按名拒绝。
:name: tbl-e17-common
:align: left

| 名 | 类型 | 谁收 | 语义 |
| :--- | :--- | :--- | :--- |
| `shot` | int | 消费测量的场景 | 炮号；触发 E-15 的第 2、3 级 |
| `time` | time（点 / 窗 / 表；模板限定形） | 同上 | 时刻选择；L-10 记法 |
| `provider.<ids>` | str | 有 `device` 端口的场景 | 该 IDS 用清单里哪个提供者（缺省清单的 `default`） |
| `epoch` | str | 同上 | 装置年代（清单 `epochs`）；缺省由 `shot` 经 `boundary_policy` 判〔已确立：EAST 清单以炮号为 `resolve_key`〕 |
:::

(fylite-preset-env)=
# 十 · 环境变量 (Environment Variables)

〔已确立·设计〕**命名规则**：`FY_*` 是**可执行文件 `fy` 的搜索路径类**变量（`$PATH` 形，
平台分隔符）；`FYLITE_*` 是**单值资源**（一个文件、一个主机、一个目录）；两者都**不设物理参数**
（E-16）。`KEFIT_*` 是 Python 库的旧名，`fy` 不读。

:::{table} `fy run` 读的环境变量，以及它与命令行选项、缺省的次序。「新」列：本篇新增。
:name: tbl-e17-env
:align: left

| 变量 | 类 | 次序（高 → 低） | 用途 | 新 |
| :--- | :--- | :--- | :--- | :---: |
| `FY_FACTS_PATH` | 路径表 | `--facts` → 本变量 → 检出 `facts/` → `FY_FACTS_BUNDLED` | 装置 / 实验条目的语料 | 已有 |
| `FY_CASES_PATH` | 路径表 | `--cases` → 本变量 → 检出 `docs/examples/` → `FY_CASES_BUNDLED` | 预设与模板覆盖 | **新**（E-3 落地） |
| `FY_FACTS_BUNDLED` / `FY_CASES_BUNDLED` | 构建期 | 最后一级 | 发行版自带语料的位置；源码检出里没有 | 后者新 |
| `FYLITE_KERNEL_LIB` | 单值 | `--kernel` → 本变量 → 检出 `python/fylite/_lib/` | 内核 `.so` | 已有 |
| `FYLITE_MDSIP_SERVER` | 单值 | `--mdsip` → 本变量 → 清单提供者 `uri` | 取数阶段的 mdsip 主机 | 已有 |
| `FYLITE_MDSIP_USER` | 单值 | `--mds-user` → 本变量 → `USER` | mdsip 用户名 | 已有 |
| `FYLITE_RUN_DIR` | 单值 | `-o` → 本变量 → `records/` | 记录目录的父目录；Python `engine.handles` 已用同名 | 借用 |
| `FYLITE_OFFLINE` | 旗标 | `--offline` → 本变量（`1`） | 全局禁止套接字（CI、离线机器） | **新** |
| `FYLITE_APP_DIR` | 编译期 | — | `app` 内嵌；`run` 不读 | 已有 |
| `RAYON_NUM_THREADS` | 单值 | 直接由内核读 | 线程数；记录的 `environment` 里记下 | 已有（Python 记录它） |
:::

〔已确立·设计〕**退役与不采纳：**

| 变量 | 判 | 理由 |
| :--- | :--- | :--- |
| `FYLITE_DEVICE_DIR` | Python 库继续读；**`fy` 不读** | 它指一个「装置牌目录」，而 `fy` 的装置只有一个来处——facts（K-8）。两条路并存的结果是同一台机器两份描述（`facts.rs` 抬头那句「一台没人运行的机器」）。指南「平衡反演」里的 `export FYLITE_DEVICE_DIR=…` 是库用法，不是命令行用法 |
| `KEFIT_MDS_SERVER` / `KEFIT_LIMITER` | `fy` 不读 | 旧名；主机走 `FYLITE_MDSIP_SERVER`，限制器走装置文档的 `wall` 提供者（`provider.wall=`） |
| `FY_RUNTIME_LIB` | `fy` 不读 | 那是 Python 找中间层 `.so` 用的；`fy` 自己就是中间层 |
| `FYLITE_SESSION` | `fy` 不读 | Python 重放机制的会话 id；`fy run` 的记录 id 由时间戳与场景名构成（`case.rs` 现行） |

(fylite-preset-record)=
# 十一 · 记录目录与退出码 (The Record Directory and Exit Codes)

〔已确立·设计〕**记录目录自足（E-19）**：

```text
records/20260904T1530Z-reconstruction/
  plan.jsonld              合成好的计划；每个参数带 fylite:from；端口带 endpoint
  device.fyo.jsonld        装出的装置文档（路一）
  measurements.fyo.jsonld  第 3 级取回的测量（第 1、2 级时是一条相对路径 / 语料引用，不复制）
  record.jsonld            spo:ComputationRecord；run_state · refusal{stage, message} · environment
  <ids>.fyo.jsonld         产出的数据集（或 --format 指定的另一种）
```

`plan.jsonld` 先于一切写出（`case.rs` 现行：「一份记录引用它」）；取数阶段失败时目录里有
`plan.jsonld` 与 `record.jsonld`（`refusal.stage: measurements`），没有测量文件。

〔已确立·设计〕**退出码（E-20）**——沿用原 `case` 的三个值，只多了「阶段」：

| 码 | 含义 | 记录 | `refusal.stage` |
| ---: | :--- | :--- | :--- |
| 0 | 跑完 | 全套 | — |
| 1 | 合成之后的任何拒绝 | `plan.jsonld` + `record.jsonld`（`run_state: rejected`） | `compose`（装置与预设矛盾 · 端口缺绑定）· `device`（找不到 / 只有卡片）· `measurements`（三级落空 · `--offline` 下需取数）· `kernel`（门不认 code · 缺槽 · unsunk 范围） |
| 2 | 语法：未知固定选项 · 未知参数 · 类型不符 · 范围外 · 缺位置参数 | **不落记录** | — |

`--dry-run` 只可能退出 0 或 2：它停在装内核之前，且不开套接字（第 3 级在 dry-run 下打印
「将取：`ids` · `shot` · `time` · 主机」而不连接——与 `fetch --dry-run` 同形）。

(fylite-preset-spec)=
# 十二 · 规格增量与实现 (Spec Delta and Implementation)

〔已确立·设计〕`_cli.json` 增一条命令（`spec_version` 不变；`open_parameters` 是**可选键**，
旧解析器不认识时按 C-4 拒绝一切未知记号——即行为退化为「没有动态参数」，不会静默吞掉）：

:::{table} `run` 在 `_cli.json` 里的样子（节选）。
:name: tbl-e17-spec
:align: left

| 键 | 值 | 说明 |
| :--- | :--- | :--- |
| `name` | `run` | 第三条命令词，取代 `case`（v1.1） |
| `hosts` | `["rust"]` | 与其余三条同 |
| `open_parameters` | `"scenario"` | ★本篇唯一的格式扩展：未知的 `--k=v` / `--k` / `--no-k` / `k=v` 记号收集而不拒绝 |
| `args[0..]` | `target`，`nargs: "+"` | 线 `[场景]` 或计划文件（可多份）。★不用 `choices`：路径也从这里进 |
| `retired`（顶层键） | `{"case describe": "list kernel", "case plan": "run … --dry-run", "case run": "run …", "case json": "run … --json", "data facts": "list facts"}` | 撤掉的命令词 / 子命令与去处；解析器据此按名拒绝并指向（E-23）。数据不进代码（C-1） |
| 命令 `list` | `hosts: ["rust"]`；子命令 `devices` `experiments` `scenarios` `presets` `facts` `kernel` `lines`（{numref}`tbl-e17-list`）；组级 `--facts` `--cases` `--kernel` `--json`；子命令的位置参数 `name`，`nargs: "*"`；`scenarios` / `presets` 另有 `--line`，`presets` 另有 `--scenario`，`facts` 另有 `--roots` | 第四条命令词（E-24）；子命令表与 `data` 同形（C-5） |
| 其余 `args` | {numref}`tbl-e17-fixed` 的每一项，形制同 `data fetch` / `app` 的同名项与原 `case run` 的同名项（`action`、`metavar`、`choices`、`type` 逐字相同） | 同词同义（J-6）由闸子 ⑥ 钉住 |
:::

〔已确立·设计〕**解析器改动（`cli/mod.rs`）**：两处——①命令带 `open_parameters` 时，未知
记号进 `Args.open: Vec<(String, Option<String>, Spelling)>`，`Spelling ∈ {Bare, Flag, NoFlag}`；
②命令词在 `retired` 里时按名拒绝，话术带上那条子命令的去处（`fy case run x.jsonld` →
「`case` 已收进 `run`：`fy run x.jsonld`」），退出 2。与 `rust/build.sh --cli` 的处理同一姿态：
**按名拒绝而不是默默当成**。
`--k v`（空格形）**不**收：`v` 会与位置参数 `scenario` 二义（`--only-magnetic true` 里的
`true` 是场景名还是值？）；规则写进 `--help`。

〔已确立·设计〕**新模块 `cli/run.rs`**，职责按本篇章节逐一对应：

| 函数 | 做什么 | 复用 |
| :--- | :--- | :--- |
| `lines()` / `template(line, scenario)` | 读 `lines.jsonld` 与模板（内嵌表 + 语料路径覆盖） | `facts::roots` 的同构 `cases::roots` |
| `apply_device(plan, id)` | 路一：`resolve_device` + `from_manifest` → 写 `device.fyo.jsonld` → `bind_override`；路二：`from_device` 表 → `set_override`（`from = device:`） | `cli/data.rs` · `assembly.rs` |
| `resolve_measurements(plan, shot, time)` | 三级；第 3 级 = `fetch` 的函数体 | `cli/data.rs::fetch`（抽成库函数，`fetch` 子命令与本函数共用） |
| `apply_open(plan, args.open, vocab)` | 第二段解析：归一、类型、范围、开关展开、来源 | `case::set_override` 的值解析 |
| `run(args)` | 合成 → 运行 → 记录；原 `cli/case.rs` 的 `run_cmd` / `plan_cmd`（`--dry-run`）/ `json_cmd`（`--json`）**并入本模块** | 原 `cli/case.rs`（撤除） |

〔已确立·设计〕**新模块 `cli/list.rs`**：{numref}`tbl-e17-list` 逐行一个函数，全部只读；原
`cli/case.rs::describe` 与 `cli/data.rs` 的 `facts` 处理器搬进来。`scenarios` 的「门认不认」一列
调用 `Kernel::load` 的**可失败**版本（找不到内核不是错，是一列的取值）。

★**对现有代码的全部触动**：`fetch` 的函数体从 `data` 子命令处理器里抽出一个可调用的函数，
`fetch` 子命令与 `run` 共用；`cli/case.rs` 的四个处理器搬进 `run.rs`，该文件撤除；`crate::case`
（`compose` / `set_override` / `bind_override` / `resolve_inputs` / `kernel_settings`）**原样保留**——
撤的是命令词，不是合成器。这正是 J-7 / E-21 的实现形。

(fylite-preset-rulings)=
# 十三 · 裁定 E-1..E-22 (Rulings)

〔已确立〕v0.1 的九条保留编号；修订者标「v1.0 修订」并写明改了什么。

**E-1 预设是数据，不是动词。** 一条预设是一份 `fyo:ScenarioSpecification` 计划文档，住在
语料里；一条**场景模板**同样是一份文档（v1.0 补）。`fy` 的命令词**禁止 (MUST NOT)** 因为
新增场景或预设而增加。

**E-2 名字与路径同位（v1.1 修订）。** `run` 的位置参数与 `--preset` / `--plan` 的值：**含 `/`
或以 `.json` / `.jsonld` / `.yaml` 结尾**的当路径，否则当名字（位置参数上，名字先对四个线词）；
两者都解析不到时按名拒绝，列最接近的三个名字。（v1.0 曾把位置参数留给 `case run` 只收路径；
v1.1 `case` 撤除，路径回到 `run` 的位置参数。）

**E-3 语料解析与 `facts` 同构。** `--cases PATH`（可重复）→ `$FY_CASES_PATH` → 检出
`docs/examples/` → `$FY_CASES_BUNDLED`；先到先得，决胜单位是条目。（v1.0：补第三、四级，
与 `facts.rs` 四级逐位对应。）

**E-4 发现面只在 `list` 上（v1.1 修订）。** `fy list` 是唯一回答「有什么可用」的命令词
（{numref}`tbl-e17-list`）：装置、实验条目、场景模板、预设、语料根、内核 code 表、四条线，
各一条子命令，给名字打那一条的全部。`run` **不带** `--list` / `--show`；`data` **不再**带
`facts`（迁入 `list facts`）；原 `case describe` 迁入 `list kernel`。v0.1 的 `fy case list` /
`fy case show` 未曾落地，其内容是 `list presets`。

**E-5 固定选项只有三个与物理相邻：`--device` / `--shot` / `--time`（v1.1 修订）。** 其余
场景参数一律 `key=value`（或同义的 `--key=value` / `--key` / `--no-key`）。**`--set` 整个撤除**
（v1.0 曾留在 `case`；`case` 撤了，它没有别的地方可留）；计划文件形上 `key=value` 就是原来的
`--set k=v`，只是多了模板校验。v0.1 担心的「第四个词开一个先例」由 E-11 化解：解析器**不认识**场景参数，
所以加一个参数不改规格、不发二进制。

**E-6 不给 `shot=` 就不开套接字；取数是一个有界的前置阶段（v1.1 修订）。** 条件三件
同时成立才发生：给了 `shot=`、E-15 的前两级落空、未 `--offline` / `$FYLITE_OFFLINE`。取回的
文档**先落记录目录再进门**。三条理由（离线 · 可缓存 · 失败面分开）保持成立，见
{ref}`fylite-preset-measurements`。

**E-7 预设与模板声明它要什么，门按名拒绝。** 端口在模板 `fylite:ports` 里声明；缺绑定落
`run_state: rejected`，`refusal.stage` 写明阶段（v1.0 补阶段）。

**E-8 语料不得广告门拒绝的东西。** 每条**模板**与每条**预设**必须能被判定「今天可跑 /
不可跑」，不可跑者在数据里给理由（模板：`lines.jsonld` 的 `runnable` 字段；预设：目录条目
字段）。`fy list scenarios` / `fy list presets` 逐条打印。不设模板的场景**也**在 `lines.jsonld` 里登记理由
（{numref}`tbl-e17-catalogue` ✗ 列的每一条）。

**E-9 预设的命名。** `<code>-<限定>`，限定自粗到细；**禁止 (MUST NOT)** 与另一条只差大小写
或连字符。模板命名**等于 code 的末段**（`scenario/reconstruction` ↔ `code/reconstruction`）。

**E-10 `run` 取代 `case`，`list` 收拢发现面；`fy` 是 `app` / `data` / `run` / `list` 四条命令词（v1.1 修订）。**
`fy run <线> [<场景>]` 或 `fy run <计划>…`：线是四个固定词（`analysis` / `model` / `design` /
`control`，与 `fylite.scenario.LINES` 同词），场景是**位置参数**，取值来自模板目录；计划文件
也是位置参数（E-2）。〔已确立〕用户裁定（2026-09-04）：*case 功能收敛进 run，弃用 case 命令*。
★`FYL-DESIGN-15` R-2 / R-4 枚举的 `app` / `data` / `case` 要在该篇下一版改为 `app` / `data` /
`run` / `list`；J-1 从此写作「不因场景新增命令词」——四条词各是一个动词（起页面 · 搬数据 ·
算 · 看），场景、装置、预设从来不是词。

**E-11 两段解析。** 静态语法（位置参数、固定选项）在 `_cli.json`，由规格驱动的解析器处理；
动态参数表在模板，由 `run.rs` 在模板加载后处理。规格用 `open_parameters` 声明「这条命令
后面有一张开放的表」；没有这条声明的命令行为不变。未知参数在第二段**按名拒绝**并列最接近的
三个名字，退出 2，不落记录。

**E-12 参数记法。** ①`key=value` ≡ `--key=value`；②`--key` ≡ `key=true`，`--no-key` ≡
`key=false`，仅对 `bool` 类型合法；③名字里 `-` 与 `_` **等价**（归一为模板里的拼法；模板
**禁止**同时声明只差这两个字符的两个名字）；④**固定选项名优先**：`shot=1` 是固定选项
`--shot`，模板**禁止**声明与任何固定选项同名的参数（闸子 ④）；⑤值按 JSON 字面量解析，否则
字符串——与 `--set` 同一函数；`type: time` 例外，走 L-10 记法；⑥`--key value`（空格）**不是**
参数记法，只对固定选项合法。

**E-13 合成次序与来源。** 模板缺省 → 装置（`from_device`）→ 预设 → `--plan`（按序）→
命令行（参数；开关展开低于显式参数）→ 端口绑定。每个值带 `fylite:from`；`list scenarios <名>` /
`run --dry-run` 逐列打印；`plan.jsonld` 落盘时保留。

**E-14 装置信息两条路进计划。** 路一：整份 `fyo:DeviceDescription`（清单装出，或卡片本身）
绑到 `device` 端口，副本落记录目录；模板声明它要卡片还是清单，不够时按名拒绝
（`refusal.stage: device`）。路二：模板 `from_device` 表按 fyo 路径给参数缺省；取不到不设；
用户显式值永远胜过装置。装置与预设矛盾时拒绝（`refusal.stage: compose`）。

**E-15 测量文档三级解析。** `--input` → facts `experiment/<device>/<shot>` 的离线切片（按
`time` 取最近片，容差内；窗与表逐片）→ 取数（`from_manifest` + `assemble`，`ids` 取模板
`measurements` 端口声明）。三级落空时 `refusal.stage: measurements`，话术说出三级各为何没走通。
连接次序 `--mdsip` → `$FYLITE_MDSIP_SERVER` → 清单 `uri`；用户名 `--mds-user` →
`$FYLITE_MDSIP_USER` → `$USER`。

**E-16 环境变量只供资源，不供物理参数。** 全表见 {numref}`tbl-e17-env`；命名 `FY_*`
（搜索路径类）/ `FYLITE_*`（单值资源）；`fy` **不读** `FYLITE_DEVICE_DIR` / `KEFIT_*` /
`FY_RUNTIME_LIB` / `FYLITE_SESSION`。**禁止 (MUST NOT)** 新增一个决定物理量取值的环境变量。

**E-17 每线一条缺省场景，写在数据里。** `docs/examples/scenario/lines.jsonld`：
`analysis → reconstruction`，`model → transport`，`design → zerod`，`control → breakdown`
（本条最初写的是 `control → vstab`；`vstab` 没有 code 与参数词表，因而没有模板，见
as-built A-1）。一条线的缺省**必须**指向一份存在的模板，闸子逐条查；改缺省是改一份文档。

**E-18 开关是模板声明的派生布尔参数。** `fylite:switches` 把一个名字映到一组基础参数的值；
`--only-magnetic=true` 展开成 `mag` 预设的六个布尔（〔已确立〕逐字取自页面）。展开值的来源记
`cli:switch <名>`，且**低于**同一命令行上显式给的基础参数。开关只展开**布尔**；滑块值
（`kw` · `kpts`）不进开关。

**E-19 记录目录自足；`--dry-run` 停在内核之前且不开套接字。** 目录结构见
{ref}`fylite-preset-record`；`plan.jsonld` 先写；一次 `run` 的产物可以只凭这个目录在没有
facts 路径、没有网络的机器上用 `--input` / `--bind` 重放。

**E-20 退出码与阶段。** 0 跑完；1 合成之后的任何拒绝（记录在场，`refusal.stage ∈ {compose,
device, measurements, kernel}`）；2 语法（不落记录）。沿用原 `case` 的三个值。

**E-21 合成器只有一份，在库模块 `crate::case` 里（v1.1 修订）。** `run.rs` 调用
`case::compose` / `set_override` / `bind_override` / `resolve_inputs`，两种位置参数形走同一条
调用链；`fetch` 的函数体同样共用。**禁止 (MUST NOT)** 在 `run.rs` 里出现第二份「后者覆盖
前者」的实现（`FYL-DESIGN-16` D-3）。★模块名 `case` 保留：它说的是「一个算例」，与命令词无关。

**E-23 `case` 弃用：按名拒绝并指向。** `case` 及其四条子命令自 `_cli.json` 的 `commands` 撤除，
`data facts` 同去；都迁入顶层 `retired` 键（每条一个去处，{numref}`tbl-e17-migration`）；`fy case …` 退出 2，
话术带去处；`cli/case.rs` 撤除，`crate::case` 保留（E-21）。**禁止 (MUST NOT)** 保留一个静默
转发到 `run` 的 `case`：转发会让两个词长期并存，而 `--cli` → `--exe`、`fylite-data` / `fylite-case`
两次撤销的姿态都是**按名拒绝**。Python 库门 `fylite.io.fydoc.case_json` 不受影响——它不是命令行。

**E-24 `list` 是唯一的发现面，且只读。** 子命令按语料的类分（{numref}`tbl-e17-list`），
每条打「名字 · 来自哪个根 · 今天能不能用」三样，给名字时打那一条的全部；`--json` 逐条同形。
**禁止 (MUST NOT)** 在 `list` 里合成计划、取数或写记录；**禁止 (MUST NOT)** 在 `run` / `data` /
`app` 上再长出 `--list` 一类的旗标——新的一类语料进 `list`，作为一条子命令。〔已确立〕用户
裁定（2026-09-04）。

**E-22 模板随 `fy` 内嵌，预设走语料路径。** 模板与内核 code 表是一对，错版由门禁 ②抓；
语料路径上的同名模板覆盖内嵌份（排障）。这条关闭 v0.1 的开放项「语料装到哪里」的**模板**
一半；预设一半的答案是 E-3 的四级。

(fylite-preset-stages)=
# 十四 · 分期与门禁 (Stages and Gates)

:::{table} 分期。P1 不动内核；P2 是内核补 code（`FYL-DESIGN-16` K- 域）。
:name: tbl-e17-stages
:align: left

| 期 | 内容 | 关闭判据 |
| :--- | :--- | :--- |
| **P1-a** ✅ | `_cli.json` 加 `run`（`open_parameters`）与 `list`（七条子命令）、去 `case` 与 `data facts`、加 `retired`（E-23）；`cli/case.rs` 的三个处理器并入 `run.rs`，`describe` 与 `data facts` 并入新的 `cli/list.rs`；`test_cli_spec.py` 期望命令集 `{app, data, run, list}`；`cli/mod.rs` 收集开放记号、按 `retired` 拒绝；`run.rs` 的模板加载、第二段解析、开关、`--dry-run`；`list scenarios` / `lines` / `kernel` / `facts`；`lines.jsonld` 与 9 份模板（现有 code 各一）；模板内嵌 | `fy run model transport chi0=0.4 --dry-run` 与 `fy run <模板路径> chi0=0.4 --dry-run` 打出逐字节相同的计划；`fy case run x` 退出 2 并指向 `fy run x`；未知名按名拒绝 |
| **P1-b** ✅ | 装置两条路（E-14）；`device.fyo.jsonld` 落地；`from_device` 表先落 `reconstruction` 一份（`basis`），其余待 G-6 的 fyo 路径定下来 | `fy run model --device east --dry-run` 打印装置来源根与逐参数 `from = device:` |
| **P1-c** ✅ | 测量三级（E-15）；`--offline` / `$FYLITE_OFFLINE`；`experiment/<device>/<shot>` 切片选择（`facts::shot` / `Shot::slices`） | 用 fydata 的 `experiment/east/137985` 离线跑通第 2 级（`--offline` 下）；第 3 级在有 mdsip 的机器上取回并落地 |
| **P1-d** ◐ | 三条门认的场景端到端（`transport` · `evolve` · `zerod`）；`list devices` / `experiments` / `presets`（E-24）；E-8 的 `runnable` 字段。★发现面与 `runnable` 已落；**端到端那一条待一份内核 `.so`**——本次落地的容器里没有，所以走到门就停在 `refusal.stage: kernel` | 三条各出一份记录；`fy list scenarios` 里 `reconstruction` 显示为不可跑并给理由；`fy list devices east` 打出清单的提供者缺省与许可 |
| **P2-a** | 内核 case 门补 `code/profile` | `fy run analysis profile --input pts.jsonld` 出记录 |
| **P2-b** | 内核 case 门补 `code/reconstruction`；用户例句跑通 | `fy run analysis --device east shot=137985 time=4.0 --only-magnetic=true` 与库路径 `reconstruct_shot` 逐位一致 |
| **P2-c** | `series` · `vstab` · `discharge` · `breakdown` · `pulse` 的 code；`feasible` / `vertical` / `evolution` / `tglf` 的模板 | `fy list scenarios` 里不再有「模板有、门没有」的条目 |
:::

〔门禁〕七条，都便宜（★①与⑤只有对着**产物**才答得出，落在
`python/tests/test_run_behaviour.py`；其余五条是静态的，落在 `test_cli_spec.py` 与
`test_scenario_templates.py`）：

1. **等价式** ✅——场景形 `fy run <线> <场景> k=v` 与计划文件形 `fy run <模板路径> k=v` 产出逐字节
   相同的 `plan.jsonld`（去掉 `fylite:from` 后比较）；实测相等，且 `fylite:from` 本身记下了
   是哪一种形；
2. **模板与门对账**（E-8）——每份模板的 `prescribes_code` 要么在 `CASE_CODES` 里，要么
   `lines.jsonld` 里有 `runnable: false` 与理由，**否则红**；不设模板的场景也须在 `lines.jsonld`
   里有理由；
3. **词表对账**——每份模板的 `fylite:vocabulary` ⊇ 语料同 code 全部 `sets_parameter` 的名字
   （今天的实测数：46 · 114 · 33 · 23 · 19 · 17 · 14 · 8 · 5），且每条预设用到的名字都在模板里；
4. **同名禁止**（E-12 ③④）——模板里没有与固定选项同名的参数，没有只差 `-` / `_` 的两个名字；
5. **离线** ✅——`--offline` 下解析不到测量时给出 `refusal.stage: measurements` 并退 1，
   而不是 panic、也不是连出去；不带 `mdsip` 特性的构建同此（第 3 级不存在）；
6. **同词同义**（J-6）——`run` 的 `--device` / `--shot` / `--time` / `--mdsip` / `--mds-user` /
   `--timeout-ms` / `--format` / `--kernel` / `-o` 在规格里与 `fetch` / `app` 的同名项
   `type` · `choices` · `action` 逐字相同（`test_cli_spec.py` 加一条）；
7. **目录覆盖**——{numref}`tbl-e17-catalogue` 里每一行的名字在 `lines.jsonld` 里出现一次
   （模板、并入或不设的理由之一），且反向亦然（`test_docs_*` 一条）。

(fylite-preset-asbuilt)=
# 十五 · 落地与三处不同 (As Built)

〔已确立〕2026-09-04 落地（用户「完整实现 cli 设计」）。产物：

:::{table} P1 落了什么。行是本篇的裁定，列是它今天住在哪。
:name: tbl-e17-asbuilt
:align: left

| 裁定 | 落在哪 |
| :--- | :--- |
| E-10 四条命令词 | `_cli.json`：`app` / `data` / `run` / `list`；`src/bin/app/main.rs` 分派 |
| E-11 两段解析 | `_cli.json` 的 `open_parameters: "scenario"`；`cli/mod.rs` 收集 `Args::open`；`cli/run.rs::apply_open` 按模板校验 |
| E-12 参数记法 | `cli/mod.rs` 的 `open_bare` / `open_flag`；**固定选项名优先**在 `open_bare` 里（`shot=1` 走 `--shot` 并按 `int` 校验） |
| E-13 合成次序与来源 | `cli/run.rs::build` 六层 + `Prov`；`stamp()` 把 `fylite:from` 写进 `plan.jsonld` 每条参数 |
| E-14 装置两条路 | `load_device`（整份文档绑端口，卡片 / 清单两种，`requires` 不够时按名拒绝）+ `apply_device_defaults`（`from_device`，只盖模板那一层） |
| E-15 测量三级 | `resolve_measurements`：`--input` → `facts::shot(...).slices()`（容差 1 ms，超出不取邻片）→ `fetch_measurements`（取回先落 `measurements.fyo.jsonld` 再绑） |
| E-16 环境变量只供资源 | `FY_CASES_PATH` / `FY_CASES_BUNDLED`（`corpus.rs`）· `FYLITE_OFFLINE` · `FYLITE_RUN_DIR`；`fy` 不读 `FYLITE_DEVICE_DIR` / `KEFIT_*` |
| E-17 每线一条缺省场景 | `docs/examples/scenario/lines.jsonld` 的 `fylite:lines.<线>.default` |
| E-18 开关 | 模板的 `fylite:switches`；`apply_open` 两遍（开关先、显式后），实测 `--only-magnetic` 展开成六个布尔并记 `cli:switch only_magnetic` |
| E-20 退出码与阶段 | 实测 0 / 1 / 2 三档；`record.jsonld` 带 `fylite:refusal_stage` |
| E-21 合成器只有一份 | `run.rs` 全程调 `crate::case`（`compose` / `set_override` / `bind_override` / `resolve_inputs` / `record`）；`cli/case.rs` 撤除 |
| E-23 `case` 弃用 | `_cli.json` 的 `retired` 八条；`cli/mod.rs` 顶层与子命令两处按最长匹配指路 |
| E-24 `list` 只读 | `cli/list.rs` 七条子命令，全程不写、不连接；`scenarios` 的「今天」一列装内核来答，装不上改说目录里记的判定 |
:::

〔已确立〕**模板是生成物。** 九份模板与场景目录由 `tools/make-scenario-templates.py`
从语料生成：**279 个参数名逐条取自语料自己的 `code/<x>#<名>` IRI**，类型由字面量推断
（同名两种数值取宽的那个），只有语料说不出的那些（标题、端口、开关、`from_device`、
取值范围）写在生成器的 `OVERLAY` 里。闸子 `test_scenario_templates.py` 重跑生成器并比对，
另查四件：词表 ⊇ 语料实际用到的名字、开关只展开模板认得的布尔、没有参数与固定选项同名
（E-12 ④）、目录覆盖每一份模板且不设模板者在数据里给理由（E-8）。

〔已确立〕**三处 as-built 与设计不同**，逐条记下来：

| | 设计说 | 落成 | 为什么 |
| :--- | :--- | :--- | :--- |
| **A-1** | {numref}`tbl-e17-catalogue` 给 `pulse` 与 `vstab` 标 ✅ 模板，E-17 又把 `vstab` 定为 control 线的缺省 | **不发**这两份；P1-a 发的是**语料的九个 code** 各一份（含 `pfwave`），control 线的缺省落成 `breakdown` | 一份模板要 `prescribes_code` 指向一个**真实存在**的 code IRI 与一份真实的参数词表。`pulse` 没有 code（语料的 `pulse-iter` 用的是 `code/pfwave`），`vstab` 有内核 entry 而无 case code 与词表——发出去只能是两个凭空造的名字。本篇的分期表本来就写着「9 份模板（现有 code 各一）」，两处互相矛盾，这次按分期表落，目录表随之改（{numref}`tbl-e17-catalogue` 的这两行现记为不设模板，理由进 `lines.jsonld`）。 |
| **A-2** | `fy list` 不给子命令时打总览 | 按名拒绝并列出七条子命令 | 组命令要子命令，这是 C-5 既有的行为（`fy data` 同此），而拒绝话术本来就把七条都列了出来。为一条命令改解析器的通例，换来的只是同一份名单的另一种排版。 |
| **A-3** | `--dry-run` 停在装内核之前 | 还**一个字节都不写**（装置文档在内存里装、不落盘，第 3 级只打「将取什么」），且**解析不到的输入端口是一行输出而不是一次拒绝** | 前半：E-19 说记录目录不写，而实现时装置那一步仍会写 `device.fyo.jsonld`——一次 `--dry-run` 在别人的工作目录里留下文件，与「先看看会发生什么」是相反的承诺。后半：`fy run analysis --only-magnetic --dry-run` 本来会因为 `measurements` 没绑而退 1，于是「看一眼计划」要先把每个输入备齐——恰好取消了看一眼的用处。真跑的那一次照旧拒绝（`refusal.stage: measurements`），闸子两边都查。 |

〔评注〕**没有落的那一半，是内核的那一半。** 门今天认三个 code，所以九条场景里六条走到
`refusal.stage: kernel`——那不是缺陷，是 {numref}`tbl-e17-stages` 的 P2。本次落地把「入口
形状」全部做完：加一个 code 之后，那一条场景**不需要再改命令行**。

(fylite-preset-gaps)=
# 十六 · 缺口与关系 (Gaps and Relations)

| | 缺口 | 证据 | P |
| :--- | :--- | :--- | :--- |
| **G-1** | 磁重构与动理学反演没有命令行入口（v0.1 起）；本篇给出入口形状，门要 P2-b | `CASE_CODES` 3 条 | P0 |
| **G-2** | 语料广告门拒绝的东西；本篇把判定放进 `lines.jsonld`（E-8） | `reconstruction.md` L14 | P0 |
| **G-3** ✅ | 没有发现面；本篇 `fy list`（E-4 / E-24），七条子命令已落 | — | P1 |
| **G-4** ✅ | 语料不随 `fy` 走；模板内嵌（`corpus.rs` 的 `include_str!`，与 `_cli.json` 同一机制），预设四级（E-3）已落 | `docs/examples/` 在书里 | P1 |
| **G-5** | 三张清单的差集本篇已逐条对账（{numref}`tbl-e17-catalogue`）；剩下的是 P2-c 的 code 与四份待设模板 | — | P2 |
| **G-6** | `from_device` 表的 fyo 路径逐场景待定（fyo v0.9 的 `DeviceDescription` 形） | {ref}`fylite-preset-device` 〔待定〕 | P1-b |
| **G-7** | `fylite:vocabulary` / `switches` / `ports` 在本体里没有对应类 | fydoc 工单 | P1 后 |
| **G-8** | EAST 绑定表无 Thomson 绑定：`kinetic` 开关开时第 3 级取不全，只能走第 1 级（`--input`） | `_mds_bind.json` 的 IDS 计数 | P2-b |
| **G-9** ✅ | 语料 25 条没有一条声明输入端口；**端口现由模板声明**（`fylite:ports`），预设不必各写一遍 | 实测 | P1-a |
| **G-10** ✅ | `FYL-DESIGN-15` v1.1（R-2 / R-4 / C-1 / C-5 与 as-built）与 `docs/guide/cli.md` · `docs/reference/cli.md` · `docs/reference/data-layer.md` 已改为四条命令词，迁移表进参考篇 | 本篇 E-10 / E-23 | P1-a |
| **G-11** | 计划文件形上「找不到模板时开放参数不校验透传」是 E-11 的一个漏斗：一份 `prescribes_code` 不在模板目录里的计划可以带任何名字进门，由内核按名拒绝兜底 | {ref}`fylite-preset-grammar` | P1-a（`--dry-run` 标 `unchecked`） |

〔关系〕本篇是 `FYL-DESIGN-15`（命令行的**形**）与 `FYL-DESIGN-16`（内核的**门**）之间的
那一层：`run` 用 `-15` 的规格机制说话，用 `-16` 的文档门算数，自己只做**解析**。`FYL-SRS-01`
FR-TOOL-001（命令行入口覆盖求解）在 2026-09-04 撤 Python 命令行后由 `fy` 承担，本篇是它在
「日常建模与分析」这一档的落法；条款文本的相应修订作为提案登记在 SRS 附录，本篇不代改。
