---
document_id: FYL-DESIGN-20
title: "内核状态的报告机制——面 · 覆盖 · 可用性 · 版本 (Reporting the Kernel's State: Surface, Coverage, Availability, Version)"
shortname: fylite-kernel-status-reporting
version: "0.1"
date: 2026-09-08
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-08T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-08T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v0.1 开篇。用户裁定（2026-09-08）：*针对 fylite_kernel 形成报告页，分别落入 docs 与 app*，
    三问——（一）物理功能 · 函数 · 工作流的自动化验证与对拍，模块增减替换与验证进度动态更新；
    （二）各主要 case / scenario 在各装置上的可用性；（三）区分内核版本，全寿命周期追踪。
    同日第二条裁定：**落在 `docs/benchmark/`**，不另起一棵树。
    本篇把三问收成三张生成表加一条发布路径，裁定 M-1..M-12，分期 P0..P3，四条门禁，缺口 G-1..G-8。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-kernel-status-reporting

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-20` |
| 文档名称 (Title) | 内核状态的报告机制——面 · 覆盖 · 可用性 · 版本 |
| 短名 / Slug | `fylite-kernel-status-reporting` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-08 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性；规范条款经提案入 SRS / SDD) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | 内核维护者 / 发行制品的人 / 读登记册的外部读者 / 前端页面的维护者 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 2026-09-08 用户裁定（**三问 + 报告页分别落入 docs 与 app** → M-1..M-12）· 2026-09-08 用户裁定（**落在 `docs/benchmark/`** → M-1）· `docs/benchmark/README.md`（三类记录不可混 · 一条记录自带的四样）· `docs/benchmark/registry.jsonld`（25 条，实测）· `docs/benchmark/physics/`（7 算例 · 88 检查）· `docs/benchmark/plan/plan.jsonld`（定序与阻塞规则）· 内核仓 `docs/cases/registry.jsonld`（真源）· 内核仓 `tools/benchmark-publish.py`（渲染路径）· `FYL-ABI-01`（C ABI 声明面）· `FYL-DESIGN-15` R-1..R-6（三种发行形态）· `FYL-DESIGN-17` E-24（发现面只有一处）· `FYL-DESIGN-19` A-14（缺省即全功能版） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；`M-` 为本篇新开的裁定前缀 |
:::

(fylite-kernel-status-intro)=
# 内核状态的报告机制 (Reporting the Kernel's State)

〔一句话〕**三问都不是「再测一遍」，是「把已经知道的事连起来」——今天缺的是三个连接件：
记录不指向它验证了哪个 `code`（覆盖率因此算不出来）、可用性只在运行期发作（没有矩阵）、
**记录不带内核身份**（因此说不出它对哪一版成立）。** 机制是三张**生成**表加一条已有的发布
路径；`docs/` 与 `app/` 是同一份 JSON 的两种渲染，谁也不持有第二份判断。

★★三者里第三条是承重的（用户裁定 2026-09-08：*V&V 应追踪 kernel 版本*）：**一条 V&V 记录
是对某一份内核字节说的话，不是对「fylite」这个名字说的话。** 没有身份，前两张表也立不住——
覆盖率会把三个月前对另一份实现量到的数算进今天的分子，而可用性矩阵会把上一版的拒绝码
当成这一版的现状。所以身份不是三张新表的一个字段，是**登记册本身的必填项**（M-5 / M-13）。

# 一 · 家底 (As-Is, 实测 2026-09-08)

`docs/benchmark/` 已经是一本成形的册子，本篇不重建它，只往上接三张表。实测：

| 已有 | 是什么 | 数（实测） | 谁生成 |
| :--- | :--- | ---: | :--- |
| `registry.jsonld` | 公开 V&V 登记册 | 25 条（V 14 · B 6 · C 5） | 内核仓 `tools/benchmark-publish.py` 渲染 |
| `reports/` | 每条记录的散文报告 | 25 篇 + 索引 | 手写 |
| `scenarios/` | 对拍场景规格 | 11 份 | 手写 |
| `plan/` | 验证定序册（DAG · 阻塞规则） | 手写件 | 手写 |
| `physics/` | 自洽校验批 | 7 算例 · 88 检查（评 24 · 未过 1） | `tools/benchmark-run.py` |
| `BENCHMARK.md` | 仓根一页统计 | 同上 | 同上 |

内核那一侧今天答得出的事实（`fy list` 与制品自述，实测）：

- **声明面**：ABI `152`；`code/*` **33** 个（assembled 31 · operator 1 · extension 1）；entry **5** 个；声明表 **13** 张。静态归档导出 **57** 个（核心 42 + 扩展 15），wasm 两份各 **42 / 20** 个函数。
- **场景**：模板 **22** 个，其中内核门今天认的 **6** 个——**这个比值本身就是一份进度**，而今天没有任何一页把它写下来。
- **装置**：facts 条目 **13** 台，带清单（可取数）的 **1** 台。
- **身份**：`rust/kernel-lib/kernel-static.json`（`kernel_version` · `abi` · `built` · `sha256`）、`python/fylite/_abi.py`（`ABI_VERSION`）、内核仓 `docs/note/app-provenance.md`（逐份 wasm 的 sha256）。

# 二 · 三问，与它们各自缺的那个连接件 (The Three Questions and the Missing Joins)

**（一）功能 · 函数 · 工作流的验证与对拍，及模块增减替换。** 分子有了（25 条记录、88 条自洽
检查），**分母与连接件没有**：登记册的 `scenario` 字段指向 `scenarios/`，与 `code/*` 之间
没有任何一条边。实测 `record/V-14` 的 `compared_subject` 写的是
`fylite: scenario.model.qlknn.flux_from_targets / fluxes + nn.rs`——一段**散文**里的路径，
机器读不出它覆盖了哪个 `code`。于是「33 个 code 里验过几个」今天不是难算，是**无从算**。

模块增减替换同理：退役历史是散文（内核仓 `app-provenance.md` 的「第 N 刀」逐条叙述，从
251 个导出降到今天的 57 个），一条也没有落成机器可读的差分。

**（二）case / scenario × 装置的可用性。** 今天只有两个半答案：`fy list scenarios` 的
`runnable_kernel`（22 中 6），以及运行期才发作的拒绝——实测 `BENCHMARK.md` 里两条：
`refused: [-30] no code code/discharge` 与 `refused: [-33] this case is outside the sunk
scope of evolve_heat`。**矩阵是 22 × 13 = 286 格**，而没有一处把它算出来过；读者要知道
「ITER 上能不能跑 discharge」，唯一办法是跑一次。

**（三）版本与全寿命。** 记录不带内核身份。实测 `record/V-14` 记了参考侧的版本
（`git:b4d40633（TORAX 1.4.3）`），**自己这一侧只有代码路径，没有 version / abi / sha256**。
后果不是记错，是**说不清**：今天的内核是 `0.0.1 · ABI 152 · sha 290c3df5…`，而 V-14 量到
`2.238e-15` 时是哪一份字节，登记册答不出——那条记录因此只能当作历史，不能当作**现在**的
证据。这与本仓已经立过的一条规矩自相矛盾：制品发布前要核对 sha256（`app-provenance.md`），
而**结论**却不核对。

# 三 · 裁定 (Rulings)

**M-1 三张新表进 `docs/benchmark/`，不另起一棵树。**〔已确立〕用户裁定（2026-09-08）。
册子已经有真源在内核仓、渲染在公开仓、机器读 JSON-LD、人读 Markdown 的完整形制；再开一棵
`docs/status/` 会把「这个内核处在什么状态」劈成两处，而两处从此可以互相矛盾而不报错。
新增三个目录：`surface/`（面与增减替换）· `coverage/`（验证进度）· `availability/`（可用性矩阵），
外加一条版本轴 `lifecycle/`。

**M-2 一处产、两处渲染。** 三张表由**内核仓**生成——只有那边同时有声明面（ABI 生成物）、
oracle（`tests/data`）与私有登记册真源。生成物是 JSON-LD，经既有发布路径落进公开仓
`docs/benchmark/`；`app/` 的页面**读同一份 JSON**，不另抄一份数。★判据与 `facts` 那条一样
（`FYL-DESIGN-19` A-1）：同一批字节两条通路，某天它们会描述两个不同的内核，而**先发现的人
是拿到制品的那个**。

**M-3 分母来自声明，不来自散文。** `surface.jsonld` 是 **ABI 声明面的投影**——`code/*`、
`entry`、声明表、导出符号，逐项由生成物现推（`_abi.py` / `fyo-interface` / `nm` 的导出表），
**禁止手写清单**。理由：手写清单与真实导出面的偏差不报错，只让覆盖率悄悄变好看。

**M-4 记录必须声明它覆盖谁（join key）。** 每条 `fyo:ComparisonRecord` 增一个必填字段
`covers: ["code/…", "entry/…"]`。覆盖率 = 面表的项被至少一条**当前身份**的记录指到的比例。
没写 `covers` 的记录进「未归属」一栏并逐条列名——**不是丢掉，是显式欠账**。

**M-5 每个数带内核身份——登记册在内。**〔已确立〕用户裁定（2026-09-08）：*V&V 应追踪
kernel 版本*。登记册的每条 `fyo:ComparisonRecord`、自洽批的每个算例、可用性矩阵的每一格，
都带三元组 `kernel: {version, abi, sha256}` 加 `recorded` 日期。sha256 取**运行时真正装载的
那一份**（`fydoc.linked_kernel()`——`rust/build.sh` 的内核检查已经在用同一个来源），不取
仓库声明：版本号与 ABI 都可能对得上而字节是旧的，那正是本仓 2026-09-05 实测过的一种失败。

★字段落在记录的 `compared_subject` 一侧——它今天写的是
`{type: spo:Code, name: "fylite", comment: "…代码路径…"}`，那句 comment 是散文，
机器读不出版本。加 `version` / `abi` / `sha256` 三个键即可，词汇不变（`spo:Code` 本来就有
版本位，参考侧 25 条里已经这么记了：`rev 6357db306` · `git:b4d40633（TORAX 1.4.3）` ·
`0.7.0`）。**参考侧记得住版本，被测侧记不住**——这是今天最刺眼的一处不对称。

**M-6 三档取值，未评估与身份不明各占一档。** 任何一格是 `pass` / `fail` / `unknown` 之一；
`unknown` 再分 `not-evaluated`（没跑）与 `stale-identity`（跑过，但不是这一版的内核）。
**禁止**把任何一种 `unknown` 并进 `pass`——`BENCHMARK.md` 已经这么做了（「未评估」单列），
本机制把它升为全册规则。

**M-7 增减替换由差分给出，不由人写。** 每次发布把 `surface.jsonld` 按身份存一份快照；
`added` / `removed` / `replaced` 是**两版快照的差**。退役项必须带去处
（`retired` · `moved-to-oracle` · `replaced-by: <项>`），缺去处则门禁红。★这条把
`app-provenance.md` 里逐刀的散文叙述变成机器可读的历史——那些叙述仍然写，但不再是**唯一**
的记载。

**M-8 可用性按判据算，不跑全量。** 286 格逐格跑一次是几十分钟且要装置数据；机制只做
**组装期判定**（`fy run <scenario> --device <id> --dry-run` 那条路：装置卡片够不够、
`code` 门认不认、要不要 MDSplus 绑定），每格记 `verdict` 加 `reason`（拒绝码原文）。
真跑过的格子由登记册与自洽批**回填**，覆盖到哪算哪——**判据算出来的「可用」不等于「跑过」**，
两者在同一张表里是两列，不是一列。

**M-9 页面不产生结论。** `docs/` 的 Markdown 与 `app/` 的页面都只渲染 JSON 里**已有的字段**；
任何一个百分比、任何一句「通过」都必须能在 JSON 里指到出处。★理由是本仓反复付过的学费：
一处算、一处抄，抄的那处会在下一次改动后继续说旧话。

**M-10 陈旧即红。** 状态表带的身份与当前制品不符时，门禁失败并打印两个 sha 的前 12 位——
与 `rust/build.sh` 的内核检查、`app-provenance.md` 的发布闸同一条规矩、同一种报错形状。

**M-11 公开面只发结论与指针。** oracle 本体、私有 deck、受限参考一律不进公开仓（沿用
`docs/benchmark/README.md` 已有的纳入规矩）；三张新表发的是计数、判决、拒绝原因与
`$FYLITE_KERNEL` / `$FYDOC_ORACLE` 相对指针。

**M-13 一条记录的有效期绑在它量到的那一份内核上；换版不继承。**
新内核不自动继承旧记录的结论——它继承的是**旧结论加一个问号**。续期只有一条路：
**复测**（登记册已有 `finding_kind: re-run` 这一档，发布当日把门跑一遍），而复测的
finding **必须记下它跑在哪一份身份上**。于是每一版内核都能算出三个数：
`renewed`（本版复测通过）· `inherited-unverified`（上版通过、本版没测）· `broken`（本版复测未过）。
★这不是给记录设有效期去作废它们——历史照留（M-12）；它只是**不让上一版的绿灯替这一版说话**。
★代价说在明处：一次内核构建之后，登记册会立刻从「25 条通过」变成「25 条待复测」，直到
复测跑完。这是实情，不是退步——今天那 25 条绿灯本来就没说清是对哪一版说的。

**M-12 历史只追加。** `lifecycle/<version>+abi<N>+<sha12>.jsonld` 每次发布追加一份，
**不改写**已发的快照。全寿命追踪 = 这些快照的时间序列；「某个 code 是什么时候第一次有验证
记录的」由序列回答，不由记忆回答。

# 四 · 三张表 (The Three Tables)

`surface.jsonld` —— 面与它的历史：

| 字段 | 说明 |
| :--- | :--- |
| `kernel` | 身份三元组（M-5） |
| `codes[]` | `id` · `entry` · `kind`（assembled / operator / extension）· `since`（首次出现的版本）· `state`（见下） |
| `entries[]` `tables[]` `exports[]` | 同上三项，各自的计数与逐项 |
| `delta` | 对上一份快照的 `added` / `removed` / `replaced`（M-7），每项带去处 |

每项的 `state` 是一条状态机，也是「验证进度」的取值域：
`declared`（面上有）→ `implemented`（门认）→ `self-checked`（自洽批评过）→
`verified`（有 V 类记录）→ `benchmarked`（有 B / C 类记录）→ `retired`。
★**逆行是允许的**：换了实现之后回落到 `implemented` 是正常的，掩盖它才不正常。

`coverage.jsonld` —— 进度：面表逐项 × 记录，给出计数与逐项归属；分母是面表，分子是
**当前身份**下指到该项的记录（M-4 / M-5）；另列「未归属记录」与「陈旧身份记录」两栏。

`lifecycle/<身份>.jsonld` —— 逐版一份快照，含**该版的 V&V 状态**：逐条记录
`renewed` / `inherited-unverified` / `broken`（M-13），加三张表当时的计数。
「某个 `code` 什么时候第一次有验证记录」「哪一版起 B-05 就没再复测过」由这串快照回答。

`availability.jsonld` —— 矩阵：`scenario × device` 每格
`{verdict, reason, evidence}`——`verdict` 三档（M-6），`reason` 是拒绝码原文，
`evidence` 是「判据算的」还是「真跑过的」（M-8）。

# 五 · 流程 (The Process)

| 何时 | 跑什么 | 要什么 | 退出码 |
| :--- | :--- | :--- | :--- |
| 每次内核构建之后 | `status scan`：面表 + 差分 + 可用性判据 | 只要制品与声明面（**不要 oracle**，秒级） | 差分里有无去处的退役项 → 1 |
| 发布之前 | `status verify`：跑自洽批与登记册的门，回填覆盖率 | oracle（`$FYDOC_ORACLE`）与内核 | 有 `fail` → 1；身份不符 → 1 |
| 发布时 | `status publish`：渲染进公开仓 `docs/benchmark/` 与 `app/` | 公开仓检出 | 陈旧 → 1（M-10） |

三步分开的理由与 `rust/build.sh` 不替谁构建内核是同一条：**扫描是廉价且总是可跑的，
验证要外部数据，发布要写另一个仓**。把它们合成一条命令，等于让「看一眼状态」变成
「必须有 oracle 且必须能写公开仓」。

# 六 · 两种渲染 (The Two Renderings)

**docs/**：`docs/benchmark/` 下三个目录各一页 `SUMMARY.md`（生成）加机器读的 `.jsonld`，
与 `physics/` 今天的形制逐字相同。册子按现行裁定**不入站点 toc**（记录是按路径引用的，
见 `docs/myst.yml` 的说明），仓根 `BENCHMARK.md` 增三行摘要并链过去。

**app/**：新增一页「内核状态」，读同一份 JSON。三块：面与差分（增减替换的时间线）、
覆盖率（逐 code 的状态机着色）、可用性矩阵（22 × 13 的格子，点开一格给拒绝原文）。
离线发布时随页面内嵌那三份 JSON——与页面已有的做法一致，且**不改数**（M-9）。

# 七 · 分期 (Stages)

- **P0 身份**（最先，且不依赖任何回填）：登记册真源加 `kernel` 三元组并从此必填（M-5），发布路径带过来；`surface.jsonld` + 快照 + 差分。落地后立刻能答两句今天答不出的话——「这一版有哪 33 个 code、比上一版多了什么少了什么」，以及「这 25 条记录各是对哪一份内核说的」。★**身份排在覆盖率之前**：没有身份的覆盖率是一个会自己变好看的数。
- **P1 可用性矩阵**：`availability.jsonld` 由判据算出 286 格。落地后能答「哪台装置上能跑哪个场景，不能跑的话卡在哪一句拒绝上」。
- **P2 覆盖率**：给登记册加 `covers` 字段并**回填 25 条**；`coverage.jsonld` 出第一版真实分母。同期补 M-13 的复测账：本版 `renewed` 几条、`inherited-unverified` 几条。
- **P3 全寿命**：`lifecycle/` 时间序列与页面上的时间线；覆盖率与可用性按版本对比。

# 八 · 门禁 (Gates)

1. **面表与制品同身份**（M-10）：不符即红，打印两个 sha 前 12 位。
2. **退役必须带去处**（M-7）：差分里出现无去处的 `removed` 即红。
3. **未评估不得并进通过**（M-6）：统计表的四列（pass / fail / not-evaluated / stale-identity）之和必须等于总数——**和不对就是有一档被并掉了**。
4. **页面不产生结论**（M-9）：页面上出现的每个数字，必须在对应 JSON 里能按字段名找到。
5. **登记册每条都带身份**（M-5）：`registry.jsonld` 里出现一条没有 `kernel` 三元组的记录即红。★这条门禁**先于**回填落地：先让新记录不可能漏，再回填旧的（否则回填期间新写的记录会继续漏，而门禁要等回填完才开得起来）。

# 九 · 缺口 (Gaps)

- **G-1** 25 条记录要回填 `covers`，逐条要人判断——机器猜不出一条记录验证的是哪个 `code`。
- **G-2** 覆盖率的分母是**声明面**，而声明面不等于物理功能：一个 `code` 可以只被验证了它的一条分支。本机制给的是「有没有记录指着它」，不是「验得多严」。
- **G-3** oracle 不在公开仓，因此覆盖率只能在内核仓算；公开仓拿到的是结论，读者无法自行复算这一步（与登记册本身的既有局限同源）。
- **G-4** 可用性矩阵的「判据算的」与「真跑过的」之间必然长期存在差额——判据宽松则高估，严格则低估；差额本身要在表上写明。
- **G-5** 286 格的 dry-run 需要装置卡片在场；公开版不含 EAST（`FYL-DESIGN-19` A-14），公开发布的矩阵会少一列或那一列全 `unknown`——按 M-6 记 `unknown`，不留空。
- **G-6** 状态机的 `self-checked` 一档依赖自洽批覆盖到该 `code`，而今天 7 个算例只覆盖到少数几条路径（22 个模板中门认 6 个）。
- **G-7** `app/` 页面内嵌三份 JSON 会增大离线包；量级未测。
- **G-8** 本篇未定「谁批准一次退役」——M-7 只要求写去处，不要求评审。
- **G-9** 25 条旧记录的内核身份**多半已不可考**：它们量到数的那次构建没有留下 sha256（那时也没有 `kernel-static.json`）。回填只能到「版本 + ABI + 日期」这一级，`sha256` 记 `[TBD]` 并标明为何不可考——**不倒推、不假填**，一个编出来的 sha 比没有 sha 坏得多。
- **G-10** M-13 落地后，复测成本成为发布成本的一部分（25 条 × 每版）。哪些记录必须逐版复测、哪些可以按变更面挑（只测差分碰到的 `code`）本篇未定——挑，就要先有 M-4 的 `covers`。
