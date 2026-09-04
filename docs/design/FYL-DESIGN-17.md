---
document_id: FYL-DESIGN-17
title: "预设场景与算例入口 (Preset Scenarios and the Case Entry)"
shortname: fylite-preset-scenarios
version: "0.1"
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
  change: 'v0.1 初稿：回答「常用场景（磁重构 · 动理学平衡反演 · 芯部输运…）怎么从命令行调、
    预设哪几个」。实测三张清单不一样长——内核 case 门 **3** 个 code、语料 **9** 个、能力工具
    **10** 个——于是问题分两半：**入口形状**（怎么调，现在就能定）与**门的宽度**（能调到什么，
    要内核补 code）。裁定 E-1..E-9：预设是**数据不是动词**（不新增命令词，`fy case run <名字>`）、
    名字解析与 `facts` 同构、发现面是 `case list` / `case show`、只有 `--device` / `--shot` /
    `--time` 三个通用旗标（与 `fy data fetch` 同词）、语料不得广告门拒绝的东西。给出六条常用预设
    与两档分期，缺口 G-1..G-5。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-preset-scenarios

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-17` |
| 文档名称 (Title) | 预设场景与算例入口 (Preset Scenarios and the Case Entry) |
| 短名 / Slug | `fylite-preset-scenarios` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性；规范条款经提案入 SRS / SDD) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / 用命令行跑算例的人 / 加一条预设的人 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-15`（命令行只有一条，规格一个文件；C-1..C-8）· `FYL-DESIGN-16`（内核以 fyo 文档门为唯一接口；K- / H-）· `FYL-DESIGN-14`（数据半边与 `fy data fetch`）· `FYL-CONOPS-00`（离线包络；四条交互面）· `FYL-SRS-01` FR-TOOL-001 / FR-TOOL-004 · 语料 `docs/examples/`（25 条，9 个 code）· 2026-09-04 用户裁定（Python 侧没有命令行） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；`E-` 为本篇新开的裁定前缀 |
:::

(fylite-preset-intro)=
# 预设场景与算例入口 (Preset Scenarios and the Case Entry)

〔一句话〕**预设是数据，不是动词。** 常用场景不该各得一条命令词，而该是**一份具名的计划**：
`fy case run <名字>`。名字经与 `facts` **同构**的语料解析（`--cases` / `$FY_CASES_PATH` / 内置语料，
先到先得、决胜单位是条目）；只有 `--device` / `--shot` / `--time` 三个通用旗标，其余一律 `--set`。

〔为什么这是当下的问题〕2026-09-04 的裁定撤掉了 Python 侧的命令行，其中包括 `fylite run`——
而那条命令**正是磁重构与动理学平衡反演唯一的命令行入口**（`--east --shot --time --point
--pressure --thomson-ne …`）。撤除时的判读是「十一条动词都只是库的薄包装，直接调库即可」，
这对九条成立；对**反演那两条不成立**，因为它们不是「一次函数调用」，而是「取一发炮 → 装配测量
→ 反演 → 落一份记录」这条**流程**，而流程正是命令行的用途。本篇不重开那条裁定——恰恰相反，
它给出**不新增动词**的复原路径。

(fylite-preset-asis)=
# 一 · 家底：三张不一样长的清单 (Three Lists of Different Lengths)

〔已确立〕实测（2026-09-04，`fylite@c47e938`）：

:::{table} 谁认得哪些场景。★列是本篇要合上的那道缝。
:name: tbl-e17-three-lists
:align: left

| 清单 | 数量 | 内容 | 出处 |
| :--- | ---: | :--- | :--- |
| **内核 case 门的 code** | **3** | `evolve` · `zerod` · `transport` | `fyo_interface.rs` `CASE_CODES` 三行 |
| 内核的 raw entry | 5 | `zerod` · `transport` · `profit` · `vstab` · `evolve_heat` | 同上 `ENTRIES` |
| **语料 prescribes 的 code** | **9** | `reconstruction` · `series` · `transport` · `profile` · `zerod` · `discharge` · `breakdown` · `pfwave` · `evolve` | `docs/examples/**/*.jsonld` 25 条 |
| **能力工具（库）** | **10** | `discharge` `breakdown` `feasible` `vstab` `zerod` `transport` `coupled` `evolve` `tglf` `reconstruction` | `fylite.scenario.TOOLS` |
:::

〔已确立〕**用户点名的三个场景，今天各在哪：**

| 场景 | 库里 | 语料里 | **命令行上** |
| :--- | :--- | :--- | :--- |
| 芯部输运 | `S.model.transport` ✅ | `transport-iter-15ma` · `profile-default` ✅ | **✅ `fy case run <plan.jsonld>`** |
| 磁重构 | `S.analysis.reconstruction` ✅ | `reconstruction-default` ⚠️ | **❌ 无入口** |
| 动理学平衡反演 | 同上（加约束参数）✅ | 无专条 | **❌ 无入口** |

〔已确立〕**语料在广告一件门做不到的事。** `docs/examples/reconstruction/reconstruction.md`
自己写着：`reconstruction-default` **跑不了**，`cases.run()` 会点名拒绝——它冻的是**合成孪生
生成器**的旋钮，而那个生成器只在浏览器的 `worker.js` 里。也就是说：语料里有 9 个 code，门只认
3 个，而剩下 6 个里至少有一个的「跑不了」只写在**散文**里，不在数据里。这是本篇 {ref}`E-8 <fylite-preset-rulings>`
要修的：**不能让目录说存在、门却拒绝**（与 `FYL-DESIGN-13` 那条「目录说存在不说记了什么」同源）。

〔评注〕**问题因此分成两半，且可以分开定。** 一半是**入口形状**——怎么把一个常用场景敲出来；
这一半今天就能定，且不动内核。另一半是**门的宽度**——能敲到什么；这一半是内核补 code
（`FYL-DESIGN-16` 的 K- 域），排期在后。**先定形状**：形状定了，补一个 code 就自动多一条预设，
而不必再讨论一次命令行长什么样。

(fylite-preset-criteria)=
# 二 · 判据 (Criteria)

〔已确立〕全部承自既有裁定，本篇不新造：

| | 判据 | 出处 |
| :--- | :--- | :--- |
| **J-1** | **不新增命令词**：`fy` 只有 `app` / `data` / `case` | `FYL-DESIGN-15` R-4；刚撤掉十一条动词的那次裁定 |
| **J-2** | **一份规格**：新参数进 `_cli.json`，不进代码 | `FYL-DESIGN-15` C-1 |
| **J-3** | **离线可用**：跑一个预设不得强制联网 | `FYL-CONOPS-00` 包络 |
| **J-4** | **跑不成也回一份记录**，缺什么点名 | `fy case` 现行行为（`run_state: rejected`）|
| **J-5** | **语料是数据**：加一条预设是加一份文档，不是加一段代码 | 语料的既有姿态；`FYL-DESIGN-16` K-（门只认文档）|
| **J-6** | **同词同义**：`--device` / `--shot` / `--time` 在 `fy` 里只有一种含义 | `fy data fetch` 已用这三个词 |

(fylite-preset-options)=
# 三 · 方案对照 (Options)

| | 方案 | 满足 | 不满足 | 判 |
| :--- | :--- | :--- | :--- | :--- |
| **S-1** | 每个场景一条命令词（`fy recon` / `fy transport` / `fy kinetic`…） | 好敲 | **J-1**（这正是 2026-09-04 撤掉的那个面，换个仓重来一遍）；J-5（场景进代码）| 否 |
| **S-2** | **预设即具名计划**：`fy case run <名字>`，名字解析进语料 | J-1..J-6 全中 | 需要一条名字解析与一个发现面 | **采纳** |
| **S-3** | shell 别名 / 示例脚本 | J-1 | J-4（脚本不回记录）；J-5（预设散在 README 里，不可发现、不可校验）| 否 |
| **S-4** | 预设回 Python 层（重开控制台脚本） | 好写 | **J-1**（直接推翻当日裁定）| 否 |
| **S-5** | S-2 + 少量通用旗标（`--device` / `--shot` / `--time`） | 同 S-2，且常用路径不必写 `--set` 三遍 | 需要克制：旗标只此三个 | **采纳（= S-2 的落法）** |

〔评注〕**S-1 之所以诱人又必须否掉。** `fy recon --shot 138569 --time 4.0` 读起来最短。
但它把「有哪些场景」写进了**可执行文件的命令表**：加一个场景要改 Rust、要发一版二进制，
而场景恰恰是**最常增删的东西**。S-2 把同一句话写成 `fy case run recon-magnetic --shot 138569
--time 4.0`——长了十二个字符，换来的是「加一条预设 = 加一份 JSON-LD 文档」。

(fylite-preset-rulings)=
# 四 · 裁定 E-1..E-9 (Rulings)

**E-1 预设是数据，不是动词。** 一条预设是一份 `fyo:ScenarioSpecification` 计划文档，住在语料里。
`fy` 的命令词**禁止 (MUST NOT)** 因为新增场景而增加。

**E-2 名字与路径同位。** `fy case run <参数>` 的位置参数既收路径也收名字：**含 `/` 或以
`.json` / `.jsonld` / `.yaml` 结尾**的当路径，否则当名字。两者都解析不到时按名拒绝，
并列出最接近的三个名字。

**E-3 名字解析与 `facts` 同构。** 次序 `--cases PATH`（可重复）→ `$FY_CASES_PATH` → 内置语料；
**先到先得，决胜单位是条目**（不是整棵树）。★这条不是新机制：`--facts` / `$FY_FACTS_PATH`
已经是这个形状，预设照抄它，于是「语料从哪来」在 `fy` 里只有一套规矩。

**E-4 发现面是 `case` 的子命令，不是新命令词。** 新增两条：

- `fy case list [--json]`——有哪些预设、各属哪条线、**今天能不能跑**（见 E-8）；
- `fy case show <名字>`——把那份计划打出来（等于 `plan` 子命令对名字生效）。

★与 `fy data facts`（哪些语料在场、每条条目由谁供）同形：**每一类语料都有一条“说出你有什么”的子命令**。

**E-5 只有三个通用旗标：`--device` / `--shot` / `--time`。** 它们是 `--set` 的糖，写的是语料
本来就有的那三个参数名；**其余一律 `--set k=v`**。理由是 J-6：这三个词在 `fy data fetch` 上
已经是这个意思，第四个词会开一个先例，而先例的终点是 S-1。

**E-6 取数与算数是两条命令，不合并。** 反演类预设的输入是**一份测量文档**：

```bash
fy data fetch --device east --ids magnetics --shot 138569 --time 4.0 -o meas.json
fy case run  recon-magnetic --bind measurements=meas.json -o rec/
```

**禁止 (MUST NOT)** 让 `fy case` 自己去开套接字取数。三条理由：①离线包络（J-3）——算例在没有
网络的机器上必须能跑；②取数是**可缓存**的，一份测量文档可以反复喂给不同预设；③失败面分开——
取不到数与算不出来是两件事，混在一条命令里，用户只看得到后一个错。

**E-7 预设声明它要什么，门按名拒绝。** 一条预设的输入端口在计划里声明；缺绑定时
`fy case run` 落一份 `run_state: rejected` 的记录，`comment` 写明缺哪个端口——这是现行行为，
本篇只是把它定为预设的契约（J-4）。

**E-8 语料不得广告门拒绝的东西。** 每条语料条目**必须 (MUST)** 能被判定「今天可跑 / 不可跑」，
且不可跑者**必须**在**数据里**给出理由（目录条目的一个字段），不能只写在散文里。
`fy case list` 逐条打印该判定。★这条直接由 `reconstruction-default` 的现状催生：
它的「跑不了」今天只有读了 `reconstruction.md` 的人知道。

**E-9 预设的命名。** `<code>-<限定>`，沿用语料现行的样子（`evolve-east-hmode` ·
`transport-iter-15ma`）；限定部分自左向右从粗到细（装置 → 工况 → 变体）。
一条预设**禁止 (MUST NOT)** 与另一条只差大小写或连字符。

(fylite-preset-menu)=
# 五 · 预设哪几个 (Which Presets to Ship)

〔判读〕**六条**为「常用」的一档——它们覆盖四条场景线里**每条线至少一条**，且每条都对应一个
已经有人问过的问题。分两档，判据是**今天门认不认**：

:::{table} 建议的常用预设。「今天」列：✅ 门认这个 code；⛔ 需内核补 code（见 {numref}`tbl-e17-stages`）。
:name: tbl-e17-menu
:align: left

| 预设 | 场景（问什么） | 线 | code | 输入 | 今天 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **`recon-magnetic`** | **磁重构**：给定一发炮的磁测量，位形是什么 | analysis | `reconstruction` | 测量文档（`fy data fetch`）+ 装置牌 | ⛔ |
| **`recon-kinetic`** | **动理学平衡反演**：加 POINT 法拉第内部电流约束与汤姆逊压强约束，位形与内部剖面是什么 | analysis | `reconstruction` | 同上（多两组通道） | ⛔ |
| **`transport-steady`** | **芯部输运**：定几何下一步稳态解，剖面长什么样 | model | `transport` | 装置牌 / 剖面参数 | ✅ |
| **`evolve-flattop`** | 含时演化：平顶段推进到稳态，功率平衡怎么走 | model | `evolve` | 同上 | ✅ |
| **`zerod-scenario`** | 0-D 放电：这套参数落在运行域的哪里 | design | `zerod` | 相位表 / 波形 | ✅ |
| **`profile-fit`** | 剖面拟合：一组带误差棒的测点，剖面与置信区间是什么（GCV 定阶） | analysis | `profile` | 测点文档 | ⛔（entry `profit` 已在） |
:::

〔判读〕**第二波（不进「常用」，但门一宽就该有）**：`vstab-margin`（垂直稳定裕度，entry `vstab`
已在）· `discharge-design` / `breakdown` / `pulse`（设计线三条，语料已有 `code/discharge` ·
`code/breakdown` · `code/pfwave`）· `recon-series`（时间序列反演，`code/series`）·
`tglf-scan`（湍流通量扫描）。

〔为什么是这六条〕①**用户点名的三个都在**（磁重构 · 动理学反演 · 芯部输运）；
②每条场景线至少一条，于是「这个工具属于哪条线」在命令行上也看得见；
③`profile-fit` 是反演线的**前置**——动理学反演要的压强剖面正是它拟合出来的，
把它留在菜单里，两条命令就能串起动理学那条路；④其余能力（`coupled` · `feasible` ·
`tglf`）今天更像库调用而不是一次「跑一个算例」，先不占预设名额。

〔已确立·边界〕**`recon-magnetic` / `recon-kinetic` 需要装置牌**（`$FYLITE_DEVICE_DIR` 或
facts 语料里的装置卷宗）。没有牌时按 E-7 拒绝并点名，而不是拿一个默认装置算出一组数——
装置数据不随包分发是 `FYL-SRS-01` FR-DATA-001，本篇不放宽。

(fylite-preset-stages)=
# 六 · 分期与门禁 (Stages and Gates)

:::{table} 两档。P1 不动内核，P2 是内核补 code。
:name: tbl-e17-stages
:align: left

| 期 | 内容 | 关闭判据 |
| :--- | :--- | :--- |
| **P1-a** | `_cli.json` 加 `case list` / `case show`，`run` 的位置参数收名字（E-2 / E-4），加 `--cases`（E-3）与三个通用旗标（E-5） | `fy case list` 打印 25 条语料条目；`fy case run transport-iter-15ma` 与给路径等价 |
| **P1-b** | 目录条目加「可跑与否 + 理由」字段（E-8），`list` 逐条打印 | `reconstruction-default` 在 `list` 里显示为不可跑并给出理由，且**散文与数据一致** |
| **P1-c** | 三条 ✅ 预设落地（`transport-steady` · `evolve-flattop` · `zerod-scenario`） | 三条各跑出一份记录；门禁跑其中一条 |
| **P2-a** | 内核 case 门补 `code/profile`（entry `profit` 已在，缺 code 与块声明） | `fy case run profile-fit` 出记录 |
| **P2-b** | 内核 case 门补 `code/reconstruction`；`recon-magnetic` / `recon-kinetic` 落地 | 两条预设各跑一发真实炮，与库路径逐位一致 |
| **P2-c** | 第二波预设（`vstab` · 设计线三条 · `series`） | 各出记录；`list` 里不再有「语料有、门没有」的条目 |
:::

〔门禁〕三条，都便宜：①**名字解析**——`fy case run <名字>` 与 `fy case run <该名字解析到的路径>`
产出同一份计划；②**目录与门对账**（E-8）——语料每个 `prescribes_code` 要么在 `CASE_CODES` 里，
要么条目自带不可跑理由，**否则红**；③**旗标即糖**——`--shot 1 --time 2` 与
`--set shot=1 --set time=2` composed 出的计划逐字节相同。

(fylite-preset-gaps)=
# 七 · 缺口 (Gaps)

| | 缺口 | 证据 | P |
| :--- | :--- | :--- | :--- |
| **G-1** | **磁重构与动理学反演今天没有命令行入口**；撤 `fylite run` 时的「都是薄包装」判读对这两条不成立（它们是流程不是调用） | `_cli.json` 三条命令词；`FYL-DESIGN-15` v1.0 的撤除记录 | P0 |
| **G-2** | **语料广告门拒绝的东西**：9 个 code vs 门的 3 个；`reconstruction-default` 的「跑不了」只在散文里 | {numref}`tbl-e17-three-lists`；`reconstruction.md` | P0 |
| **G-3** | **没有发现面**：语料在 `docs/examples/`，`fy` 不认识它，用户只能翻目录 | `fy case` 三条子命令均收路径 | P1 |
| **G-4** | 语料不随 `fy` 走（在文档树里），故「内置语料」这一层今天是空的 | `docs/examples/` 是书的一部分 | P1 |
| **G-5** | `code/series` · `code/pfwave` 等四个 code 语料有、门无、库里也未必有对应工具，三张清单的差集**未逐条对账** | {numref}`tbl-e17-three-lists` | P2 |

〔开放项〕**语料装到哪里。** E-3 说的「内置语料」需要一个位置：随可执行文件内嵌（同 `app/`）、
随 wheel 走（`_facts/` 已有先例）、还是只认外部根。三种各有代价，**本篇不裁**——它与
`FYL-DESIGN-15` 的发布形态表相关，宜在那一篇的下一版一并定。
