---
document_id: FYL-DESIGN-19
title: "facts 的发行形态——从 fydoc 的装置书到两份生成物 (Distributing the Facts: from fydoc's Device Book to Two Generated Artifacts)"
shortname: fylite-facts-distribution
version: "0.1"
date: 2026-09-05
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-05T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-05T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v0.1 初稿：评估用户提案「从 fydoc 收集 device A-Box，合并成两份文件——`facts.jsonld`
    进 app、`facts.rs` 进 rust；fylite 顶层不再保留单独的 `facts/`」。方向判为**对**，
    且与本仓既有的四处生成物同一条规矩（A-1）；提案按字面有两处带不动的东西——**清单
    不是卡片**（取数要的那一份，实测 13 台里只有 EAST 有，A-4）与**域有三个不是一个**
    （`device` · `amns` 5.8 MB · `experiment`，A-5）；并给出一处改写：两份生成物是搜索
    路径的**自带那一档**，不是它的替代（A-2）——保住 `--facts` 指自己机器的能力，而
    「顶层不留 `facts/`」照样成立。裁定 A-1..A-12，尺寸取舍表，三档分期，缺口 G-1..G-6。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-facts-distribution

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-19` |
| 文档名称 (Title) | facts 的发行形态——从 fydoc 的装置书到两份生成物 |
| 短名 / Slug | `fylite-facts-distribution` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-05 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性；规范条款经提案入 SRS / SDD) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / 发行制品的人 / 加一台装置的人 / fydoc 装置书的维护者 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 2026-09-04 用户裁定（装置信息在 fydoc 的装置书 `facts/device/`；公开版不含 EAST）· 2026-09-05 用户裁定（制品版本化命名，`tools/soname.sh`：一条规则、两个仓、一份实现）· `FYL-DESIGN-15`（三种发行形态；C-1 一份规格）· `FYL-DESIGN-16` K-8（装置以整份 fyo 文档进内核）· `FYL-DESIGN-17` E-3 / E-22（语料四级；模板内嵌而预设走路径）· `FYL-DESIGN-14` L-11（A-Box 方言的 YAML 读者）· `rust/fylite_runtime/src/facts.rs`（595 行）· `python/fylite/facts.py`（305 行）· `tools/abox-to-facts.py` · `tools/facts-publish.py` · fydoc `facts/device/`（13 台） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；`A-` 为本篇新开的裁定前缀 |
:::

(fylite-facts-intro)=
# facts 的发行形态 (Distributing the Facts)

〔一句话〕**方向对，两处带不动，一处该改写。** 把 fydoc 的装置 A-Box 收成两份生成物
（`facts.jsonld` 给页面、`facts.rs` 给 Rust）与本仓已有的四处生成物是同一条规矩，而且
正好治住 2026-09-05 实测的两次失败。按字面它带不动**清单**（取数要的那一份）与**另外
两个域**；而「两份生成物」最好理解为搜索路径的**自带那一档**，不是搜索路径的替代——
这样「fylite 顶层不留 `facts/`」照样成立，`--facts` 指自己机器的能力也留着。

〔为什么现在问〕2026-09-05 实测两次失败，都是同一个原因：**没有产出方**。

| 实测 | 现象 |
| :--- | :--- |
| `bash rust/build.sh --exe` | `error: couldn't read app/facts/device/catalogue.jsonld` — 全功能可执行文件**编不过**，因为内嵌资源表里的 `include_bytes!` 指着不存在的文件 |
| `bash tools/build-site.sh` | `[facts] device: public 版 0 个`，而**构建成功** —— 发出去的站点一台装置也没有 |

两处都不是许可判错，是产出方与消费方对「一条条目长什么样」看法不一致：抓回来的是
`facts/device/<id>/<id>_device.yaml`（目录形），而页面、发布器与内嵌表问的是
`facts/device/<id>.jsonld`（文档形）。本仓当日补了派生产出（`write_document` /
`write_catalogue`），把这两处堵上——**而提案要问的是更前面那一步：这份东西到底该以
什么形态发行。**

(fylite-facts-asis)=
# 一 · 家底 (As-Is, 实测 2026-09-05)

〔已确立〕`facts` 今天**不是一个目录，是一条搜索路径**：`--facts` → `$FY_FACTS_PATH`
→ 检出的 `facts/` → 自带的 `$FY_FACTS_BUNDLED`，**逐条决胜**（决胜单位是条目，不是
整棵树）。两份实现，一道闸子比对：Rust `facts.rs` 595 行 18 个公开项，Python
`facts.py` 305 行。

:::{table} 三个域，三种体量，三个来路。★「域」不是装饰：本篇提案只说了第一行。
:name: tbl-a19-domains
:align: left

| 域 | 来路 | 体量（实测） | 谁读它 |
| :--- | :--- | ---: | :--- |
| `device` | fydoc 装置书 `facts/device/`（2026-09-04 用户裁定） | A-Box 14 MB / 13 台 | 页面预设 · `fy list devices` · `fy run --device` · `fy data fetch --device` |
| `amns` | fydata `abox/amns/`（metis） | 5.8 MB | 原子分子数据；今天没有命令行读者 |
| `experiment` | fydata `abox/experiment/`（EAST #137985，9 片） | 104 KB | `fy list experiments` · `fy run` 测量解析第 2 级（`FYL-DESIGN-17` E-15） |
:::

〔已确立〕**装置 A-Box 里，文本与二进制是两回事：**

| | 文件数 | 体量 |
| :--- | ---: | ---: |
| 文本（`.jsonld` / `.yaml` / `.json`） | 147 | **2.5 MB** |
| 二进制（`.h5`） | 3 | **10.8 MB**（其中 ITER `wall_ggd.h5` 10.1 MB） |

〔已确立〕**一台装置有两种形，用途不同，今天只有一台两样都有：**

| 形 | 是什么 | 谁要它 | 实测在场 |
| :--- | :--- | :--- | ---: |
| **卡片 / 文档** | 蒸馏过的 `fyo:DeviceDescription`（几何、通道表、标称量） | 页面预设、内核（K-8 整份文档进）、`fy run --device` | 7 台有内容（另 6 台 A-Box 里没有 magnetics / pf_active / wall，**不写空卡片**） |
| **清单** `abox/device.jsonld` | 年代 × 提供者 × 绑定——**抓一发炮**跑得起来的那一份 | `fy data fetch --device`、`fy run` 测量第 3 级 | **13 台里只有 EAST** |

〔已确立〕派生文档今天的体量：**7 台共 432 KB**（west 195 KB · east 142 KB · iter 40 KB
· 其余各 4–16 KB），外加 1.5 KB 目录。

〔已确立〕**许可闸已经伸进可执行文件了。** 内嵌资源表（`src/bin/app/assets.rs`，由
`tools/make-app-embed.mjs` 生成）今天列的 7 条**正好是公开版那一档**（best · cfedr ·
cfetr · iter · jt60sa · west + 目录，**没有 east**）——它是问 `facts-publish.py --list`
问出来的。所以「哪一台进哪一种制品」这条规矩已经是一处实现、三个消费者（站点、
可执行文件、轮）。

〔已确立〕Rust 侧读 `facts::` 的有四处：`corpus.rs` · `cli/data.rs` · `cli/list.rs` ·
`cli/run.rs`。

(fylite-facts-proposal)=
# 二 · 提案 (The Proposal, Restated)

〔已确立〕用户提案（2026-09-05），四句：

1. 从 **fydoc** 收集 device A-Box；
2. 合并成**两个文件**；
3. `facts.jsonld` 进 `app`，`facts.rs` 进 `rust`；
4. fylite 顶层**不保留**单独的 `facts/`。

〔判读〕第 3 句里的 `facts.rs` 与今天那个 `facts.rs`（搜索路径的解析器）**不是同一个
东西**：提案说的是一份**生成的数据**，与 `src/ids_tables.rs`（由 `tools/dd-ids-table.py`
从 DD 的 `IDSDef.xml` 生成、提交进仓）同类。本篇按这个读法评估；两者重名要在落地时
解决（A-11）。

(fylite-facts-right)=
# 三 · 它对在哪 (What the Proposal Gets Right)

**其一：它与本仓已有的四处生成物是同一条规矩，不是新发明。**〔已确立〕

| 生成物 | 源 | 落到哪 |
| :--- | :--- | :--- |
| `_abi.py` · `version.js` · `abi.json` | 内核 `abi.rs` 的一个常数 | 两个宿主 |
| `fyo_interface.rs` · `_fyo_interface.py` · `fyo-interface.js` | 内核 `fyo.rs` 的 `@fyo-table` | 三个宿主 |
| `ids_tables.rs` + `ids/*.tsv` | DD 的 `IDSDef.xml` | Rust，**提交进仓** |
| `_mds_request.py` · `mds-request.js` | `mdsip.rs` 的 `REQUEST_VERBS` | 两个宿主 |
| `docs/examples/scenario/*.jsonld` | 语料的 `code/<x>#<名>` IRI | 语料 + 编译期内嵌 |

每一处的理由都写着同一句：**两份手工保持一致的东西不是一份契约**。装置描述今天恰恰
是那个反例——三处（页面 fetch 的、发布器拷的、内嵌表 `include_bytes!` 的）问同一份
文件，而**没有任何东西产出它**。

**其二：它治的是「不在」这一类失败，而那一类今天会静默通过。**〔已确立〕站点构建打出
`0 个`**并成功**。一份生成物**不可能不在**：不在就编不过、或门禁红，而不是发出去之后
由读者发现。

**其三：尺寸站得住。**〔已确立〕要合并的是**派生层**（432 KB / 7 台），不是 A-Box
（14 MB）。作为一次 `fetch` 与 1 MB 的 wasm 同量级；编进 8.9 MB 的可执行文件里是 +5%。

**其四：它把「顶层 `facts/`」这个今天名不副实的东西去掉。**〔已确立〕`facts/` 在本仓
是 **gitignore 的按需产物**：新检出里空的，要跑 `tools/abox-to-facts.py` 才有。一个
「有时在、有时不在，而在不在决定构建过不过」的目录，正是本仓其它地方不允许的形状。

(fylite-facts-carry)=
# 四 · 它必须带上的六件事 (What It Must Not Lose)

**A 清单不是卡片，而取数要清单。**〔已确立〕`fy data fetch --device east` 与 `fy run`
测量第 3 级走的是 `abox/device.jsonld`（提供者 × 年代 × 绑定），**不是**卡片。合并卡片
不会让取数跑得起来。★实测缓和了这一条：**13 台里只有 EAST 有清单**，所以今天能抓炮的
只有一台；但那一台正是最要紧的一台。

**B 域有三个。**〔已确立〕`experiment`（104 KB，`fy run` 的离线测量靠它）与 `amns`
（5.8 MB）不在提案里。前者小到可以一起并；后者不该编进任何东西。

**C 许可闸今天是逐条的，合并之后要变成逐**版**的。**〔已确立〕`rights.json` 一台一份，
`facts-publish.py` 按版取舍。合成一份文件之后，「一份」实际上是「每种版一份」——或者
一份文件里逐条带许可、由构建期筛。这不是缺陷，是要说清楚的代价：**「两个文件」的准确
说法是「每种发行版两个文件」**。

**D 搜索路径存在的理由不是「有几个语料」，是「有人要指自己那台机器」。**〔已确立〕
`--facts` / `$FY_FACTS_PATH` 让一个不随发行走的装置（某人自己的托卡马克、一次实验的
私有描述）进得来。生成物若是**唯一**来源，这条能力没有了。

**E 「哪个根供的」这个答案会消失。**〔已确立〕`Entry::root` 与记录里的出处今天答得出
「这次用的是哪一份 EAST」。合并之后来源只有一个——更简单，但记录少了一句它本来说得出的话。

**F 更新的节拍变了。**〔工作假设〕内嵌的数据只能靠重新构建改。装置描述在重新勘测时会变
（fydoc 的装置书正是为此存在）。今天重拖一次即可；之后要发一版。

(fylite-facts-options)=
# 五 · 方案对照 (Options)

:::{table} 三种落法。「顶层 `facts/`」列答的是用户第 4 句。
:name: tbl-a19-options
:align: left

| | 方案 | 顶层 `facts/` | 带得动 A–F 吗 | 判 |
| :--- | :--- | :--- | :--- | :--- |
| **S-1** | **取代**：两份生成物是唯一来源，搜索路径撤除 | 去掉 ✅ | D 没了（指不了自己的机器）；E 没了；A / B 要另想办法；`facts.rs` 595 行 + `facts.py` 305 行 + 那道比对闸子一并撤 | 否 |
| **S-2** | **自带那一档**：两份生成物是搜索路径的最后一级（今天 `$FY_FACTS_BUNDLED` 那一格），前面三级不动 | 去掉 ✅（检出里不再需要它，生成物在制品里） | A–F 全带得动：D / E 靠前三级，A / B 靠「并进去什么」的取舍表 | **采纳** |
| **S-3** | 现状 + 把今天补的派生产出留着 | 留着 ❌ | 用户第 4 句不满足；两次失败已堵，但「按需产物决定构建过不过」的形状还在 | 否 |
:::

〔评注〕**S-1 与 S-2 的差别只有一处，而那一处是全部。** 两者都生成同样的两份文件、都
让顶层 `facts/` 消失、都让制品自足。差的是**这两份文件是不是唯一来源**。S-2 把它们放进
一个**已经写好、已经有两份实现与一道闸子**的四级路径的最后一格——那一格今天就叫
「自带的那一份」（`$FY_FACTS_BUNDLED`），本来就是留给它的。S-1 则要拆掉 900 行已在的
代码去换一个更少能力的东西。

〔评注〕**这与 `FYL-DESIGN-17` E-22 的形状逐字相同。** 场景模板就是这么落的：**内嵌一份**
（`corpus.rs` 的 `include_str!`），**搜索路径上的同名文件覆盖它**。当时的理由今天照样
成立：一份装到 `$PATH` 上的 `fy` 必须自带一套能用的东西，而排障的人要能换掉其中一份而
不必重建二进制。

(fylite-facts-rulings)=
# 六 · 裁定 A-1..A-12 (Rulings)

**A-1 装置描述是生成物，且源只有一个：fydoc 的装置书。** 本仓**禁止 (MUST NOT)** 手工
维护任何一台装置的描述；`tools/abox-to-facts.py` 是那条唯一的转换。〔已确立〕上游裁定
（2026-09-04）已把源定在 `facts/device/`。

**A-2 两份生成物是搜索路径的自带那一档，不是它的替代。** 次序不变：`--facts` →
`$FY_FACTS_PATH` → 检出（若在）→ **自带**。生成物填的是最后一格。`facts.rs` 与
`facts.py` 两份解析器与那道比对闸子**保留**。

**A-3 fylite 顶层不再保留 `facts/`。** 〔已确立〕用户裁定。它今天是 gitignore 的按需
产物，而 A-2 之后没有任何构建步骤需要它在场；`--facts` 仍可指向任何一份检出。
`app/facts` 那条符号链接随之撤除（页面改读内嵌 / 发布出去的那一份）。

**A-4 并进去的是卡片，不是 A-Box；清单**也**并进去。** 卡片（`fyo:DeviceDescription`）
是页面与内核要的那一份；清单（`abox/device.jsonld`）是取数要的那一份，**两份都是文本、
都小**（实测清单只有 EAST 一份）。**禁止 (MUST NOT)** 把 `.h5` 并进任何一份生成物——
实测那是 10.8 MB 里的 10.1 MB，且它是数据不是描述。

**A-5 三个域各有各的答案，不能只答一个。** `device` 并进去（A-4）；`experiment` 并进去
（104 KB，`fy run` 的离线测量靠它，`FYL-DESIGN-17` E-15 第 2 级）；`amns` **不并**
（5.8 MB，且今天没有命令行读者）——它留在搜索路径的前三级，要用的人指过去。

**A-6 「两个文件」的准确说法是「每种发行版两个文件」。** 许可闸不动：判据仍是每台自己的
`rights.json`，由 `tools/facts-publish.py` 施用；生成的是 `facts.public.jsonld` 与
`facts.internal.jsonld` 两套（命名待定，G-3）。**禁止 (MUST NOT)** 在生成物里放一台
它那一版不该带的机器——「目录说有、文件里没有」与反过来同样坏。

**A-7 `facts.jsonld` 是页面读的那一份，形不变。** 它把今天的 `catalogue.jsonld` 与逐台
`<id>.jsonld` 合成一份：`fylite:devices` 仍是目录那一段，每条多一个 `fylite:description`
内联整份文档。★页面的读者（`devices.js` 的 `load()`）因此从 **1 + N 次 fetch 变成 1 次**。

**A-8 `facts.rs` 是 Rust 读的那一份，与 `ids_tables.rs` 同类：生成、提交进仓、`include`。**
它不参与解析路径的逻辑，只提供最后一格的字节。

**A-9 两份生成物出自同一次转换，且门禁比对。** 一次运行同时写两份；闸子断言两份描述
**同一批机器、同一批字节**（JSON 归一化后逐台比较）。理由与 `_abi.py` / fyo 接口那几处
逐字相同。

**A-10 EAST 的手工卡片是一处待还的债，本篇不掩盖它。** 〔已确立〕实测**三仓皆无**
（`535d087` 的记录与本次复核一致）：它随 `machine_desc/` 在内核仓 `b4dce77` 删除，而
那次改动的前提是「卡片按需拖回」——EAST 恰恰是唯一不拖的一张。A-1 说源只有一个，那么
EAST 那些上游没有的内容（est2 79 探针基、拟合控制块、被动结构、电源参数）**要么进
fydoc 的装置书，要么承认它没了**。在它回到源之前，EAST 进不了生成物（G-1）。

**A-11 `facts.rs` 这个名字今天被解析器占着，两者必须分名。** 建议：解析器保留
`facts.rs`，生成物叫 `facts_table.rs`（与 `ids_tables.rs` 同形）。**禁止 (MUST NOT)** 让
同一个文件名在同一个 crate 里指两样东西。

**A-12 记录仍要说得出「这一份从哪来」。** 生成物里逐台带 `fylite:from`（fydoc 的提交号
与路径），于是一份记录引用的装置描述仍可回溯到装置书的某一版——A-2 保住的是**路径**的
出处，这一条保住的是**内容**的出处。

(fylite-facts-sizes)=
# 七 · 并什么、不并什么 (What Goes In)

:::{table} 逐项取舍，尺寸为实测。
:name: tbl-a19-what
:align: left

| 项 | 体量 | 判 | 理由 |
| :--- | ---: | :---: | :--- |
| 装置卡片 / 文档（7 台有内容） | 432 KB | **并** | 页面与内核的输入；A-4 |
| 装置清单 `abox/device.jsonld` | 1 台，KB 级 | **并** | 取数跑得起来的那一份；A-4 |
| 目录 `catalogue.jsonld` | 1.5 KB | **并**（成为 `facts.jsonld` 的一段） | A-7 |
| 逐台许可账 `rights.json` | KB 级 | **并**（作为每条的字段） | 发行版判据要能自证；A-6 |
| `experiment/<机器>/<炮>` 切片 | 104 KB | **并** | `fy run` 离线测量第 2 级；A-5 |
| `amns/` | 5.8 MB | **不并** | 无命令行读者，且体量与用途都不像「随程序走的描述」；A-5 |
| A-Box 的 `.h5`（3 个） | 10.8 MB | **不并** | 数据不是描述；ITER 一个文件就 10.1 MB；A-4 |
| A-Box 的其余文本（147 个文件里未被卡片吸收的那些） | ≤2.5 MB | **不并** | 卡片就是它的蒸馏；两份都带等于带两遍 |
:::

〔判读〕合并后的量级：**约 550 KB**（432 + 104 + 目录与许可账）。作为一次页面 fetch 与
1 MB 的 wasm 同量级；编进 8.9 MB 的可执行文件是 +6%。

(fylite-facts-stages)=
# 八 · 分期 (Stages)

| 期 | 内容 | 关闭判据 |
| :--- | :--- | :--- |
| **P1** | `tools/abox-to-facts.py` 增一条「合并」出口：一次运行写 `facts.<版>.jsonld` 与 `facts_table.rs`（A-9）；`corpus.rs` 同形的 `facts` 自带档读后者 | `fy list devices` 在**空搜索路径**上仍列出该版的机器；两份生成物门禁比对通过 |
| **P2** | 顶层 `facts/` 与 `app/facts` 符号链接撤除（A-3）；`make-app-embed.mjs` 与 `build-site.sh` 改取生成物；`facts-publish.py` 的职责收成「生成哪一版」 | `bash rust/build.sh --exe` 与 `tools/build-site.sh` 在**没有 `facts/`** 的检出上都成功，且站点带该版的机器 |
| **P3** | `experiment` 域并入（A-5）；`fy run` 的测量第 2 级在自带档上跑通 | `fy run analysis --device east shot=137985 time=4.0 --offline` 在空搜索路径上解析到切片 |

〔门禁〕四条：①两份生成物描述同一批机器同一批字节（A-9）；②生成物里的机器集 = 该版
`rights.json` 允许的集合，两个方向都查（A-6）；③空搜索路径上 `fy list devices` 与
`fy run --device` 都答得出——即制品自足（A-2 的可执行形）；④生成物逐台带得出 fydoc 的
出处（A-12）。

(fylite-facts-gaps)=
# 九 · 缺口 (Gaps)

| | 缺口 | 证据 | P |
| :--- | :--- | :--- | :--- |
| **G-1** | **EAST 的手工卡片三仓皆无**，而它是唯一有清单、唯一能抓真炮的那台；不回到 fydoc 就进不了生成物 | 本次复核；`535d087` 的记录 | P0 |
| **G-2** | 13 台里 **6 台 A-Box 没有 magnetics / pf_active / wall**，转不出卡片（有意不写空卡片）——生成物因此只有 7 台，而目录要说清楚为什么少 | `abox-to-facts.py --all` 实测 | P1 |
| **G-3** | 两份生成物的**命名与版次**未定（`facts.public.jsonld`？随 `tools/soname.sh` 的版本化命名走？） | 2026-09-05 制品命名裁定 | P1 |
| **G-4** | `amns` 留在路径上之后**没有任何自带档**，于是它在一份纯制品上不可用——今天也如此，但本篇把它写成明账 | {numref}`tbl-a19-what` | P2 |
| **G-5** | 更新节拍（F）没有答案：装置书改了之后，已发出去的制品怎么知道自己旧了 | 〔工作假设〕 | P3 |
| **G-6** | `facts.py`（Python 侧解析器）要不要也读自带档；不读的话 Python 与 Rust 在「空路径」上答案不同，而那道比对闸子会红 | `test_facts_corpus.py::test_the_two_resolvers_agree` | P1 |

〔关系〕本篇与 `FYL-DESIGN-17` E-3 / E-22 是**同一条规矩用在第二类语料上**：那一篇管
算例语料（模板内嵌、预设走路径），本篇管 facts。两条路径此后形状一致，`fy list facts`
一条命令把两条都答了——那一条今天就已经这么打印。
