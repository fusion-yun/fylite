---
document_id: FYL-DESIGN-18
title: "应用前端详细设计——场景驱动的输入页、交互图形与工作台 (App Front End — Scenario-Driven Input Pages, Interactive Figures and the Workbench)"
shortname: fylite-app-frontend
version: "0.6"
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
  change: 'v0.6 U0 第四步落地：`app/assets/workbench.js`（瓦片布局写回 `fylite:layout`、`has_view` 按
    先行后列重排、缩放与光标按坐标族共享、钉住把瞬态写进规格、图层开关即时入规格），`plot.js` 补
    正向映射 `toPixel` 与 `box`；工作台闸 `validate-workbench.mjs` 十三项通过并逮到一处真缺陷
    （程序化 `move()` 未把宽度夹在 12 列内）。**U0 四条至此在本环境内全部落地**，余下的接线要内核。
    · v0.5 U0 第三步落地：`app/assets/run.js`（步预算分片 · 进度按步实测 · 取消切预算）与
    `app/assets/checkpoint.js`（断点即记录，IndexedDB；内核身份不符按名拒绝，漂移写进 environment）；
    断点闸 `validate-checkpoint.mjs` 十四项通过，并逮到两处真缺陷——恢复后步号从头开始（等价性判据
    当场不成立）、分片可跨过断点间隔使 `checkpointEvery` 形同虚设（实测一次也没落）。
    · v0.4 U0 第二步落地：`app/assets/fig.js` 由呈现规格画图（复用 `casereport.js` 的唯一解析器），
    `plot.js` 增 `stems` 记号，规格词表补 `layout` / `visible` / `domain`（G-3 关），规格闸
    `app/tests/validate-fig.mjs` 十项通过并当场逮到一处自造缺陷。新缺口 G-13：两端规格比对的闸
    `validate-report.mjs` 调的是已撤除的 Python 命令行，今天根本没跑——U-12 的判据是纸面的。
    · v0.3 U0 第一步落地（model 页）：141 个手写控件誊录为 `app/assets/vocab-model.js`，页面只剩
    `data-form` 挂点，`app/assets/form.js` 按词表画控件；表单闸 `app/tests/validate-form.mjs` 双向成立；
    首屏输出仍在 790 px；一处潜在缺陷（`width` 默认值不在格上）由闸子暴露并改正。§十三 U0 行记
    已落与未落。· v0.2 按分析工作适用性评估修改：补三种视图（U-21 茎与表 · U-22 对照记录）、通道权重在图上编辑
    （U-23）、视图状态由三种收成两种（U-17 改写：瞬态 / 入规格，瓦片带标记）、解释性文字的去向（U-24：
    词表只给一句 gloss，长注留在场景 `note` 与页面）；新增〈十五 · 评估〉记三种角色的学习曲线；缺口
    G-10..G-12。· v0.1 初稿：回答「fylite app 前端怎么详细设计」——输入页由 scenario fyo 文档**生成**
    （一条声明一个控件，控件由词表类型决定），一个输入端口可**组合多个数据源**（源栈，
    中间层合并，逐量出处）；执行是一串门调用，**进度按步实测、断点是一份记录、恢复是再入**；
    输出记录经**场景自带的呈现规格**渲染为报告，工作台改的是同一份规格。交互图形四件：
    LCFS / 剖面形状的试改（把手与节点，档位 A/B/C，改写计划可撤销）、二维整合视图（图层
    即规格里的 layer 词）、剖面查看器（任选两个共格点的量作轴、多信道叠加、框选缩放、
    时序按坐标族共域共光标）、工作台（瓦片布局写回规格）。导入 / 导出 / 移步离线只有一种
    交换单元：文档集。实测家底九条；裁定 U-1..U-20；提案 FR-UI-003..008 · NR-QUAL-007 ·
    DE-LOG-13..15；分期 U0 / U1 / U2 与四道闸；缺口 G-1..G-12；八张 16:9 预览图
    （`tools/make-frontend-design-figures.py`，与 `-11` 共用一条外壳）。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-app-frontend

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-18` |
| 文档名称 (Title) | 应用前端详细设计——场景驱动的输入页、交互图形与工作台 (App Front End — Scenario-Driven Input Pages, Interactive Figures and the Workbench) |
| 短名 / Slug | `fylite-app-frontend` |
| 版本 (Version) | v0.6 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性；规范条款经提案入 SRS / SDD) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / 写页面 JS 的人 / 写 code 词表的人 / 加一条场景的人 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-16`（K-1..K-8 · F-1..F-4 · B-1..B-4 · S-1..S-6 · H-1..H-5）· `FYL-DESIGN-17`（E-1..E-9：预设是数据）· `FYL-DESIGN-14`（L-1 · L-10 · L-12：多源装配）· `FYL-DESIGN-11`（V-8 · V-11..V-13）· `FYL-DESIGN-10`（P-3 · P-6 · P-13 · P-16 · P-23 · P-26 · P-27）· `FYL-DESIGN-09`（D-9 · D-12 · D-19）· `FYL-DESIGN-12`（P-29 · G-2 · G-16）· `FYL-SRS-01` v1.0 FR-HOST-001..003 · NR-ENV-001..005 · `FYL-SDD-01` v1.3 DE-COMP-05 · DE-LOG-04 · DE-LOG-07 · `docs/reference/case-report.md` · `docs/reference/report-template.md` · 用户需求（2026-09-04：根据 scenario fyo 文件创建动态输入页…移步离线等） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；`U-` 为本篇新开的裁定前缀。`-09` / `-10` / `-12` 关于各页**物理内容**的裁定不动；本篇管的是**四页共用的输入生成、图形交互与交换机制** |
:::

(fylite-app-frontend-intro)=
# 应用前端详细设计 (App Front End — Detailed Design)

〔一句话〕**前端不持有第二份真源。** 输入页是**计划**（`fyo:ScenarioSpecification`）经**控制词表**
投影出来的；图是**记录**（`spo:ComputationRecord`）经**呈现规格**（`spo:PresentationSpecification`）
投影出来的；断点是一份带 `fylite:state` 的记录；工作台改的是规格，不是图片；导入、导出、
移步离线只有一种交换单元——**文档集**。四条投影关系定了，「动态输入页」「多源组合」
「交互试改」「整合显示」「工作台」「断点恢复」都是它们的推论，不是各自的功能。

〔为什么这是当下的问题〕`FYL-DESIGN-16` 把内核收成一扇文档门（K-1），把宿主退成
「只写计划、只读记录」（H-1），把状态收进文档（S-4）。四个功能页今天的做法与此相反：
控件手写在 HTML 里（§一 之 1），会话文档与场景文档是**两种**文档（之 2），图是画布上的
像素而不是规格的投影（之 4），取消靠 `terminate()`（之 6），持久化只有 `localStorage`
（之 7）。`-16` 的九步总线走到 P1 之后，页面 JS 里的 `fylite_rs_*` 归零，**页面剩下的
只有「怎么生成输入、怎么呈现输出、怎么交换文档」三件事**——那正是本篇的全部范围。
本篇不重开 `-09` / `-10` / `-12` / `-13` 对各页物理内容的裁定，也不动 `-11` 的外壳；
它给出四页**共用**的那一层。

(fylite-app-frontend-asis)=
# 一 · 家底 (As-Is)

〔已确立〕实测于 `fylite@6a5ef61`（2026-09-04）。每条给出处，本篇后文按条号引用。

:::{table} 前端今天的九件事实——每条都是一个后文要合上的缝。
:name: tbl-u18-asis
:align: left

| # | 事实 | 出处 |
| :--- | :--- | :--- |
| 1 | **控件是手写的**：`<input type="range" id="pulse_design-ip" min="50" max="1000" step="5">`，单位写在 i18n 标签文字里（`[kA]`），没有类型 → 控件的映射；生成的 `BLOCKS` 表带 `units` / `shape` / `gloss`，**只用于打包，从不用于建表单** | `app/pages/page_pulse_design.html:163-223` · `app/assets/fyo-interface.js:215-217` · `app/assets/session.js:29-70` |
| 2 | **「场景」有两种文档**：页面导出的是 `fylite:AppSession/1`（`FySession.envelope`，`fylite:config` 是控件值的平面表），语料里的是 `fyo:ScenarioSpecification`（`parameters[]` 每条 `sets_parameter: code/<cap>#<name>`）；两者不互认。`_manifest/*.jsonld` 另有 `fylite:ports`（端口名 · `data_type` · `optional`） | `app/assets/session.js:92-113` · `docs/examples/design/breakdown-iter.jsonld` · `python/fylite/_manifest/evolve.jsonld` |
| 3 | **呈现规格已经存在**：`spo:PresentationSpecification` → `has_panel[]` → `has_view[]`（`view_kind` ∈ `line_chart` / `scalar_readout` / `map`）→ `has_series[]`（`binds_quantity` = `<数据集 id>#<fyo 路径>`）；`fyo:PoloidalSectionView` 带 `flux_layer` / `structure_layer` / `overlay_layer`；两端**按规则推出同一份**并逐字段比对。规格只在报告页用，四个功能页不认它 | `python/fylite/engine/casereport.py:237-310` · `app/assets/casereport.js:133-201` · `docs/examples/context.jsonld` · `app/tests/validate-report.mjs` |
| 4 | **图是画布**：`FyPlot.poloidal` / `FyPlot.xy`，2-D canvas，无缩放、无交互库；`xy` 把反变换留在 `canvas.fyxy.toData(px,py)`；`poloidal` 有 `handles` 选项与 `drawHandle`，等比例**强制**；`xy` 有 `envelope` / `bars` / `dots` 与 `bands` | `app/assets/plot.js:80-320, 410-464, 326` |
| 5 | **数据页有一种缩放**：横向框选 = 向服务端重取样，双击回整炮；两次取样（256 → 1024 / 4096 / 16000） | `FYL-DESIGN-13` P-11 · P-30 |
| 6 | **取消是终止**：一次求解是一次阻塞 wasm 调用，`abort()` = `worker.terminate()` + 重建 + 重放 `init`（约 100 ms）；`evolve` 例外——worker **每步一次 ABI 调用**，ABI 带 `resume` / `t_start` / `dt_start` / `*_in` ↔ `*_out` 二十个成对槽 | `app/assets/scenario.js:409-427` · `app/assets/worker.js:8290-8371` · `FYL-DESIGN-16` S-2 |
| 7 | **持久化只有 `localStorage`**：折叠状态、交接槽（`fylite:handoff`，一个槽，3 MB 上限）、语言、主题；无 IndexedDB、无 service worker、无 web app manifest；交接**从不自动应用** | `app/assets/handoff.js:17-45` · `app/assets/scenario.js:856-868` |
| 8 | **导入按内容认，不问文件名**：`sniff(text)` 由 `@type` / `fylite:page` / `text:` 判定，匹配的格式各自 `apply`；导出是菜单（只有写者知道要哪种形） | `app/assets/appio.js:152-192, 209-263, 309-368` |
| 9 | **进度是 worker 自报**：`{type:'progress', frac}` 或 `{phase, pass, total}`；门上**没有回调，一个也没有**（`-16` 撤回记录） | `app/assets/worker.js:749, 796, 952` · `app/assets/scenario.js:163-166` · `FYL-DESIGN-16`〔回调：撤回〕 |
:::

〔判读〕九条里有三条是**资产**而不是缺陷：之 3 的规格词表、之 4 的 `handles` 与 `fyxy`、
之 8 的按内容识别——本篇建在它们上面。之 1 与之 2 是**同一个缝的两面**：因为页面不认
`code/<cap>#<name>`，它只能手写控件；因为它手写控件，它导出的只能是控件值表。合上一面，
另一面自动合上。

(fylite-app-frontend-criteria)=
# 二 · 判据 (Criteria)

本篇不发明判据；下列条款是上游已裁定、本篇必须同时满足的。

- **J-1 宿主只写计划、只读记录**（`-16` H-1）。页面的任何一次交互，落点是计划里的
  一个字段或一份绑定；页面不持有计划之外的输入。
- **J-2 一次调用的输入集在调用开始时已定死；门上没有回调**（`-16` B-、〔回调：撤回〕）。
  进度与取消都不能依赖内核回头问。
- **J-3 内核无状态；状态是记录里一棵声明过的子树；单步还是多步是计划的选择**
  （`-16` S-1..S-4）。
- **J-4 离线是包络，不是特性**（`FYL-CONOPS-00`；`FYL-SRS-01` NR-ENV-001）。静态站点
  载入后零远程请求；桌面版没有服务端组件。
- **J-5 交互档毫秒至秒，按功能声明预算；批式档分步、可中断、有进度，且不得由滑杆触发**
  （NR-ENV-002 / -005；`FYL-SDD-01` DE-LOG-04；`-09` D-9）。
- **J-6 预设只填不跑**（`-10` P-23）；**折叠的控件仍是控件**（`-12` P-16）；**灰掉不消失**
  （`-10` P-3 · `-13` P-18）。
- **J-7 每个数带出处**（`-10` P-13）；**每个状态有非颜色通道**（`-10` P-27 · `-11` V-8）；
  **不确定度带说明它覆盖什么**（`-12` P-29）。
- **J-8 首屏落一处输出**（`-11` V-13 · `-10` P-26）；**外壳报告、页体切换**（`-10` P-25）。
- **J-9 语料不得广告门拒绝的东西**（`-17` E-8）；**DD 的文字一个字不抄**（`-14` L-4）——
  控制词表里的 `gloss` 是本仓自己写的句子，不是 DD 的 `documentation`。
- **J-10 手写的宿主外观只许缩小**（`FYL-SDD-01` DE-LOG-07 的棘轮）。本篇每一处
  「生成」都要能指出它删掉了哪些手写行。

(fylite-app-frontend-arch)=
# 三 · 总体架构：四份文档，四条投影 (Architecture: Four Documents, Four Projections)

〔一句话〕前端是四份文档之间的四条投影，外加一个把它们搬来搬去的交换层。

:::{figure}
:name: fig-u18-architecture
:align: center

```{mermaid}
flowchart LR
    subgraph docs["四份文档（真源）"]
        plan["计划 fyo:ScenarioSpecification"]
        vocab["控制词表（K-2 增列）"]
        rec["记录 spo:ComputationRecord + fylite:state"]
        pres["呈现规格 spo:PresentationSpecification + fylite:layout"]
    end
    subgraph page["页面（投影与交互）"]
        form["输入页 form.js"]
        srcs["源栈 sources.js"]
        run["执行器 run.js"]
        figs["图形 fig/*.js"]
        wb["工作台 workbench.js"]
        rep["报告页 casereport.js"]
    end
    subgraph mid["中间层 wasm（H-4）"]
        asm["assemble / merge / select"]
        tree["扁平树编解码（F-2）"]
    end
    kern["内核 wasm：code，无状态"]
    store[("IndexedDB fylite:checkpoints")]
    bundle["文档集 bundle.zip"]
    vocab -- "U-1 U-2" --> form
    plan -- "投影 1" --> form
    form -- "写回（H-1）" --> plan
    srcs -- "端口绑定" --> plan
    asm --> srcs
    plan --> run
    run -- "每步一次" --> tree
    tree --> kern
    kern --> tree
    tree -- "记录 k+1" --> rec
    rec -- "U-10" --> store
    rec -- "投影 2（规则或自带）" --> pres
    pres -- "投影 3" --> figs
    figs -- "试改（U-15）" --> plan
    wb -- "投影 4：布局写回（U-14）" --> pres
    pres --> rep
    rec --> rep
    plan --> bundle
    rec --> bundle
    pres --> bundle
```

前端的四条投影：计划 → 输入页（①）、记录 → 呈现规格（②）、呈现规格 → 图形（③）、
工作台 → 呈现规格（④）。箭头上的 U- 号是本篇的裁定；中间层与内核的形状来自 `-16`，
此图不改它们。
:::

〔已确立〕四份文档里，三份今天已经有词表（§一 之 2 · 之 3）；**缺的只有控制词表**——
`code/<cap>#<name>` 这个 IRI 今天只是一个名字，它的类型、单位、值域、默认值、档位、
分组都没有落在任何机器可读的地方。`BLOCKS` 表有 `units` / `shape` / `gloss`，缺
`range` / `default` / `enum` / `tier` / `group`。本篇把控制词表定为 **K-2 code 表的
一部分**（{ref}`fylite-app-frontend-deltas`），而不是页面自己的一份 JSON：词表跟着
code 走，三个宿主（命令行 `--set k=v` 的校验、Python 的参数检查、页面的控件）读同一份。

〔判读·模块〕页面 JS 分六个模块（{numref}`fig-u18-architecture`），每个模块只认一份文档：
`form.js` 认词表与计划，`sources.js` 认端口与装配文档，`run.js` 认记录与状态，`fig/*.js`
认呈现规格，`workbench.js` 认规格的布局词，`casereport.js` 现行不动。六个模块之间不传
JS 对象，传的是**文档里的路径**——这是把 `-16` F-4「看得见不等于可以用」搬到页面里：
一个模块只从它声明认识的文档取数。

(fylite-app-frontend-input)=
# 四 · 动态输入页 (The Scenario-Driven Input Page)

```{figure} ../figures/fe-input-page.svg
:name: fig-u18-input-page
:align: center
:width: 100%

由场景文档生成的输入页（概念图）。左：计划文档与它指向的词表条目，每条给出
「类型 → 控件」的落点；中：生成出来的表单——滑杆、步进、分段选择、开关、端口源栈、
剖面节点编辑器，每个控件带档位标记 A / C；右：首屏输出与带出处的读数。数值仅示意。
```

**U-1 页面是计划的投影：一条声明一个控件，没有声明的参数不得有控件。** 输入页由
`prescribes_code` 指向的 code 的控制词表**生成**；计划里的 `parameters[]` 给初值，
`inputs[]` 给端口绑定。页面 HTML 里**禁止 (MUST NOT)** 出现手写的 `<input>` 承载一个
`code/<cap>#<name>`。理由是 J-1 与 J-10：手写的控件是第二份真源，它与词表的漂移
无人察觉（§一 之 1 的 `[kA]` 写在标签里，改单位要改两种语言的四处文字）。

**U-2 控件由词表里的类型决定，不由页面决定。** 映射表是 {numref}`tbl-u18-controls`；
一种类型只有一种控件，页面不得为同一类型另选控件。★这张表**只有八行**，且第八行不是
控件而是端口：控制词表不承载「怎么画」，只承载「是什么」。

:::{table} 类型 → 控件映射（U-2）。「类型」是控制词表里的字段，「控件」是 form.js 的落点。
:name: tbl-u18-controls
:align: left

| 词表类型 | 附加字段 | 控件 | 备注 |
| :--- | :--- | :--- | :--- |
| `xsd:double`，有 `range` | `units` · `step` · `default` | **滑杆 + 数字孪生**（同一 id，两种输入） | 滑杆量程 = 有效值域（U-4）；数字框允许量程外输入，超界**标红不拒收**——拒绝归门（E-7） |
| `xsd:double`，无 `range` | `units` · `default` | 数字框 | 无滑杆：没有量程就没有滑杆，不猜 |
| `xsd:integer` | `range` · `default` | 步进框（`step=1`） | 网格点数、步数预算之类 |
| `xsd:boolean` | `default` | 开关 | 开关驱动的「高级组」按 P-16：开 ⇒ 组展开，关 ⇒ 组折叠但仍是控件 |
| `enum`（`choices[]`） | `default` | 分段选择（≤ 4 项）/ 下拉（> 4 项） | 选项文字来自词表 `gloss`，不来自页面 i18n |
| `xsd:string` | — | 文本框 | 只用于名字与备注；**禁止 (MUST NOT)** 用字符串承载数值 |
| `array[n]`，声明坐标（`on: grid/rho_tor_norm` 等） | `units` · `range`（逐点） | **剖面节点编辑器**（{ref}`fylite-app-frontend-figures-profile-edit`） | 无坐标声明的数组按名拒绝生成控件，列入「未生成」表（J-9） |
| `array[m]` × 2，声明为轮廓（`outline/r` + `outline/z`） | — | **几何编辑器**（{ref}`fylite-app-frontend-figures-geometry`） | 只在极向截面视图里编辑，不另出表单 |
| 端口（`fylite:ports.in[]`） | `data_type` · `optional` | **源栈**（§五） | 必需端口缺绑定 ⇒ 页面标出，运行由门按名拒绝（E-7） |
:::

**U-3 词表决定分组与次序，页面决定折叠。** 词表每条带 `group`（如「这台机器」「求解」
「输入端口」）与组内序号；页面按组生成面板，折叠状态是页面的（`localStorage`，今天的
`fylite:fold:*` 不变）。★这条把 `-12` 的「一个高级组属于它上面那个开关」做成词表字段
`advanced_of: <boolean 参数名>`，而不是页面里的一份固定清单。

**U-4 值域三层：词表 → 装置卷宗 → 用户改。** 滑杆的**有效量程**是三层的交：词表给
物理上有意义的范围；选定装置后，卷宗给这台机器的范围（`-09` 已有先例：选 ITER 后
`a ∈ [0.665, 1.895]`，因为器壁给了上限）；用户只能在有效量程里拖。导入的计划值超出
有效量程时**照收并标红**（沿用 `session.js:63-65` 的「导入文件不可信」，但由 clamp 改为
标记——clamp 会静默改数，J-7 不许）。

〔已确立·删掉什么〕U-1 落地后删除的手写行：`app/pages/*.html` 里每个 `.ctl` 块（放电
设计页 `:163-223` 一段即 60 行 × 4 页）、每个 bar 的 `sliders: {id: decimals}` 表、
`lang-*-{zh,en}.js` 里所有参数标签键（单位随词表走）。**保留**的是：模式条、共享面板的
壳、`data-result` / `data-advanced` 的折叠机制、运行键。

(fylite-app-frontend-sources)=
# 五 · 多数据源组合 (Composing Several Sources into One Input)

```{figure} ../figures/fe-sources.svg
:name: fig-u18-sources
:align: center
:width: 100%

一个输入端口上的源栈（概念图）。左：端口 `magnetics` 的三个源与一个未启用的手填层，
可排序、可开关，每层写明它给出哪些叶子；中：三份文档进中间层 wasm 合并成一份输入文档；
右下：逐量出处表——每个量来自哪一层、被盖住的那一份、时间选择。通道数与索引仅示意。
```

**U-5 组合只在中间层做一次；页面只排次序与开关。** 端口上的多个源在页面里是一个
**源栈**（自上而下的有序列表）；页面把源栈写成一份装配文档（`fylite:Assembly/1`，
`$source` / `merge` / `select`，`-14` L-1 · L-12），交给中间层 wasm 的 `assemble`；
得到的一份文档绑定到端口。页面**禁止 (MUST NOT)** 自己合并两个文档——那是 `-14` D-3
「计划的合成只在一处」的第三份拷贝（§一 之 2 已经是第二份）。

**U-6 每个量标出它来自哪一源。** 中间层写在 `fylite:assembly` 里的来源（`-14` L-11
已记炮号、窗、源），页面渲染成逐量出处表（{numref}`fig-u18-sources` 右下）。表是页面
画的，数据是中间层记的；页面不得另算一份。这是 P-13「每个数带出处」在输入侧的落点。

**U-7 同名叶子由上面的源赢，被盖住的那一份仍列出。** 先到先得、决胜单位是叶子
（与 `-17` E-3「决胜单位是条目」同形，粒度取叶子是因为一个 IDS 文档里几何与测量常来自
两处）。被覆盖的值**不静默**：出处表有一列「被盖住的」。

〔已确立·源的种类〕源栈接受的层与它们在两种投递面上的可用性：

:::{table} 源栈可接受的层。★「静态站点」列是 J-4 的直接推论：没有进程就没有取数。
:name: tbl-u18-source-kinds
:align: left

| 层 | 文档类型 | 桌面（`fy`） | 静态站点 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| MDSplus 取数文档 | `fyo:<ids>`（切片，带 `fylite:assembly`） | `fy data fetch` 经 `/api/*` | **不可用**——按 P-10 降级：打印那条 `fy data fetch` 命令 | E-6：取数与算数是两条命令 |
| 取数文档（文件） | 同上，从文件导入 | ✓ | ✓ | 取数是可缓存的（E-6 ②） |
| 装置卷宗（A-Box） | `fyo:DeviceDescription` | ✓ | ✓（`app/facts/device/`） | K-8：整份文档进内核 |
| g-file / a-file | `fyo:equilibrium` | ✓ | ✓（中间层 wasm 读，`geqdsk.js` 退役，H-4） | |
| 记录（上一次的输出） | `spo:ComputationRecord` 的输出端口 | ✓ | ✓ | 这就是页内交接与跨页交接的统一形（替代 `-10` P-4 的两种机制与 `handoff.js` 的单槽） |
| 语料预设 | `fyo:ScenarioSpecification` 的 `inputs[]` | ✓ | ✓ | E-1：预设是数据 |
| 手填 | 页面生成的小文档 | ✓ | ✓ | 只用于权重、开关类叶子；手填层写 `fylite:edited_from` |
:::

★**「记录作为源」是本篇最重要的一行。** 它把 `-10` P-4 的两种交接（页内文档 vs 页总线）、
P-21 的「命名工件」、`handoff.js` 的单槽、`-12` G-2 的「发布不叫醒读者」全部收成一件事：
下游 bar 的端口上有一层「上游 bar 的记录」，上游重跑出新记录，这一层**标为过期**（世代号，
`-09` DE-LOG-08 的提案），读者看得见、点一下才更新（P-23 的「只填不跑」在交接上的对应）。

(fylite-app-frontend-run)=
# 六 · 执行、进度与断点 (Execution, Progress and Checkpoints)

```{figure} ../figures/fe-run-checkpoint.svg
:name: fig-u18-run
:align: center
:width: 100%

一次运行作为一串门调用（概念图）。上：步带——已算 / 断点 / 当前 / 未算四态，取消与硬中断
的区别；左下：一步的往返，状态随记录进出，JS 不看字节；右下：断点仓（IndexedDB）与
移步——同一份文档集在桌面、Python、另一台浏览器上继续；别的内核写的断点按 S-6 拒绝。
36 ms/步为 `evolve-default` 语料实测（`_manifest/evolve.jsonld`），其余数值示意。
```

**U-8 步预算是计划字段，运行是一串门调用。** 多步 code 的计划带 `fylite:step_budget`
（S-3：单步还是多步是计划的选择）；页面每次调用请求 `min(剩余预算, 分片)` 步，分片由
实测每步耗时决定，目标是**每次调用 ≤ 200 ms**（J-5：交互档；这个数是**工作假设**，
G-1 要求实测定下）。每次调用交回记录(k) 与 `fylite:state(k)`，下一次调用把它们带进去
（S-4：从中间起跑与正常推进是同一机制）。

**U-9 进度是数出来的，取消是切预算，不是回调也不是终止。** 进度 = 已完成步数 / 预算，
每步耗时 = 页面量的墙钟；剩余时间**报出、不承诺**（`-13` 「时间不承诺」同款措辞）。
取消 = 把剩余预算切到 0，本次调用结束即停，记录(k) 完整可用。`worker.terminate()`
只保留为**硬中断**：当一次调用超过其预算 10 倍仍未返回；硬中断后记录(k−1) 仍在，
运行标为「硬中断」而不是「取消」（两种状态两个词，P-27）。★这条与 §一 之 6 的关系：
今天 `evolve` 已经是每步一次调用，`abort()` 的 terminate 是给单次阻塞求解用的；U-8
把所有多步 code 收成 `evolve` 的形，U-9 把 terminate 收成例外。单步 code（一次
自由边界解 ≈ 1.2 s）没有中间态，取消它就是硬中断——页面对单步 code **不显示进度条**，
显示的是「求解中 · 预算 ≤ 1.5 s」（NR-ENV-005 的预算是声明出来的）。

**U-10 断点是一份记录，不是页面的私有状态。** 每 N 步（词表给默认，用户可改）把记录(k)
（含 `fylite:state(k)`、计划的 `sha256`、内核身份 K-7）写进 IndexedDB `fylite:checkpoints`；
崩溃后重开页面，断点仓列出可恢复的运行；恢复 = 把记录(k) 作为「记录源」绑到计划上
再入（U-5 的第五行）。**没有断点专用格式**：断点仓里的东西与导出的 `record.jsonld`
逐字节相同，所以「移步」（U-19）不需要转换。

**U-11 断点带着写它的内核身份；别的内核拒绝，除非显式开关并记入记录。** 这是 S-6 在
页面上的落点：内核 wasm 的 `sha256` 变了（站点更新、桌面版升级），旧断点列出但
「恢复」灰掉，旁边一句「内核已变：3f9a… → 77c0…」，一个显式开关允许漂移，开了就
写进记录的 `environment`。

〔已确立·删掉什么〕`scenario.js` 的 `abort()` 重放 `init` 的路径保留为硬中断；
`progress` 消息的三种形（`frac` / `phase, pass, total`）删除，进度不再由 worker 报。
`worker.js` 里 `evolve` 的逐步驱动（`:8290-8371`）**升格为所有多步 code 的驱动**，
而不是被删。

(fylite-app-frontend-output)=
# 七 · 输出、呈现规格与报告 (Output, the Presentation Spec and the Report)

```{figure} ../figures/fe-report.svg
:name: fig-u18-report
:align: center
:width: 100%

报告是记录与呈现规格的投影（概念图）。左：三份输入文档按 `type` 认，规格来源三选一，
导出的文档集清单；右：五节报告，「结果」一节的三张图按工作台交回的规格与布局画，
表不内联数组。
```

**U-12 场景可以自带呈现规格；没有就按规则推出；工作台改过的写回。** 规格来源按序
三选一：①计划的 `presents` 指向的 `spo:PresentationSpecification`（语料里一条预设可以
连同「怎么看它」一起入库——这就是用户说的「模板含在 scenario 模板里」）；②本次会话工作台
改过的规格；③都没有时 `casereport.js` 现行的 `derive()`。三者是**同一种文档**，
`validate-report.mjs` 的两端比对对①②同样成立。

**U-13 报告是记录的投影：不内联数组、不重新评判。** 五节次序与 `report-template.md`
同（摘要 · 方法 · 结果 · 验收 · 复现性）；图是规格里的视图按序画出的 SVG；表只给摘要
（形状 / dtype / min / max / mean / sha256 前 12 位）。页面**禁止 (MUST NOT)** 在报告里
放一张画布截图：截图不是规格的投影，改了规格它不跟着变。

**U-14 布局是规格的扩展词，不是规格的一部分。** 工作台的瓦片位置写成视图上的
`fylite:layout {x, y, w, h}`（12 列栅格）；Python 渲染器不认这个词，按 `has_view` 的
顺序流排——**顺序**才是规格的语义，位置是页面的。★因此工作台移动瓦片时，规格里
`has_view` 的顺序按「先行后列」重排，报告里的图序与工作台的阅读序一致。

(fylite-app-frontend-figures)=
# 八 · 交互图形 (Interactive Figures)

四种图形交互，一条共同纪律：**图是规格的投影，交互写回的要么是计划（试改），要么是
规格（视图、图层、布局），从不写回图本身。**

(fylite-app-frontend-figures-geometry)=
## 几何的试改：LCFS 把手与路点 (Trying a Shape: LCFS Handles and Waypoints)

```{figure} ../figures/fe-geometry-edit.svg
:name: fig-u18-geometry-edit
:align: center
:width: 100%

几何与剖面形状的试改（概念图）。左：等比例极向截面上的方把手（R₀ a κ δᵤ δₗ）与圆路点，
灰虚线是改前的幽灵；中：拖动写进计划的是什么、三档位、试改历史与采纳 / 放弃；
右：剖面节点编辑器与约束 / 拒绝清单。1.2 s 为 `FYL-DESIGN-10` 实测，其余数值示意。
```

**U-15 试改是计划的一次改写，可撤销；页面没有第二份几何。** 两种把手，两种落点：
**方把手**对应参数化边界（`code/<cap>#r0 · #a · #kappa · #du · #dl`），拖动写
`sets_parameter`；**圆路点**对应自由轮廓（`inputs[boundary]` 绑定的 `fyo:equilibrium`
里的 `time_slice/boundary/outline/{r,z}`），拖动写一份带 `fylite:edited_from` 的小文档
绑回端口（源栈的手填层，U-5）。每一次试改是计划的一个版本（世代号），「回到 #k」是
换回那个版本的计划，「采纳」是把当前版本定为工作版本。改前的形状以**幽灵**（灰虚线，
`-09` D-12 已有先例）留在图上，直到采纳。

〔已确立·档位〕拖动中 = A 档：解析 Miller 轮廓即时重画 + 内核一列重算（≤ 50 ms/帧，
`-09` 的 A 档预算）；松手 = B 档：一次求解（自由边界 65×65 ≈ 1.2 s，`-10` 实测），
只在该 bar 声明 B 档时触发；C 档（退火、扫描）**只由按键触发**（D-9）。把手永远到不了
C 档。

〔已确立·约束〕路点编辑的约束：闭合 · 简单多边形 · 在限制器之内（用 `wall` 图层判，
没有 `wall` 文档时**不判并说明**）。违反时**画在图上、不自动修正**（P-6：拒绝而不外推）；
运行时由门按名拒绝。

(fylite-app-frontend-figures-profile-edit)=
## 剖面形状的试改：量自己坐标上的节点 (Trying a Profile: Knots on the Quantity's Own Grid)

节点编辑器是 `array[n]` 类型的控件（{numref}`tbl-u18-controls` 第七行）。节点放在**量自己
声明的坐标**上（`casereport` P2 规则的输入侧对应），节点间用单调三次插值（PCHIP），
因为剖面编辑要的是「形状」而不是「拟合」——拟合基（移位 Legendre，`-12` 剖面拟合 bar）
是分析侧的事，两者不混。约束来自词表（`range` 逐点、边界值）；结果作为数组参数写进
计划，带 `fylite:edited_from` 指向它派生自的源（一条 g-file、一份记录、或「抛物线默认」）。
时间序列的剖面（`time_slice[]`）只编辑光标所在的那一片（U-17），其余片不动。

(fylite-app-frontend-figures-composite)=
## 二维整合视图与图层 (The Poloidal Composite and Its Layers)

```{figure} ../figures/fe-composite-2d.svg
:name: fig-u18-composite
:align: center
:width: 100%

极向截面整合视图（概念图）。左：一张等比例的图上叠八层——磁面、LCFS、目标轮廓、
磁轴与 X 点、限制器与真空室、PF 线圈（电流填充）、磁探针与磁通环、干涉仪弦；右：图层
列表，每层可开关，写明它的非颜色通道与它在规格里的 layer 词及数据来源，关掉的层在
图例里留灰字。
```

**U-16 图层即规格里的 layer 词；开关状态随规格导出，报告照画。** `fyo:PoloidalSectionView`
已经有 `flux_layer` / `structure_layer` / `overlay_layer`（§一 之 3）；本篇只补两件事：
① `overlay_layer` 是集合，每一项带 `fylite:visible`（默认真），开关的写入走 U-17 的「钉住」
路径（v0.2）；② 图层的**来源是数据集**，
不是页面选项——有 `magnetics` 文档才有探针层，没有就在图层列表里写「磁探针：无数据」
（P-18 的「灰掉不隐藏」）。八层的非颜色通道见图右列；等比例由视图**强制**（`plot.js`
已如此；`-12` G-16 由构造关闭）。

〔判读〕「可选择隐藏或显示」是用户的原话；本篇把它做成规格里的字段而不是页面里的
勾选框，理由只有一条：报告页画的是规格，页面上关掉的层报告里也该关掉——否则「整合
显示」在页面与报告上是两张图。

(fylite-app-frontend-figures-profile)=
## 剖面查看器与多时序同步 (The Profile Viewer and Synchronized Traces)

```{figure} ../figures/fe-profiles.svg
:name: fig-u18-profiles
:align: center
:width: 100%

剖面查看器与时序栈（概念图）。左：横轴与纵轴各选一个量（须共格点或有映射），计算 /
参考 / 测量 / 后验带四种序列各有非颜色通道，框选缩放；右：四条时序共用一个定义域
（框选一格四格同缩放）与一个光标（拖一下四格同一时刻，剖面图跟着换时间片）。
```

**U-17 坐标轴来自量的坐标声明；缩放与光标按坐标族共享。**

- **横轴**的候选是量的容器声明的坐标集（`grid/rho_tor_norm` · `grid/rho_tor` · `grid/psi` ·
  `grid/rho_pol_norm`，`casereport` `_GRID_COORDS` 同一张表），外加**经映射可达**的坐标
  （如中平面外侧 `R`，当同一记录里有 `equilibrium` 给出 ρ → R 的映射时）；映射不存在的
  选项**灰掉并说明**，不隐藏（P-3）。
- **纵轴**是任何与横轴共格点的一维量。「任选两个量」——把纵轴换成另一个量、横轴也换成
  一个量（如 Tₑ 对 nₑ）——只在两者共格点或有映射时可选；这就是把 x–y 图收进同一条规则，
  不另开一种视图。
- **多信道叠加**：一个视图的 `has_series[]` 可以来自多个数据集（记录的输出 · 记录源 ·
  取数文档 · 参考），`series_role` ∈ `computed` / `measured` / `reference` / `posterior`
  决定 `mark_kind`（线 / 点 / 虚线 / 带），P-27 与 P-29 由此按构造满足。
- **缩放**：框选 · 滚轮 · 双击复位。★v0.2 改写：视图的交互状态**只有两种**——**瞬态**
  （缩放、光标、悬停读数；关页即失，不进规格、不进报告）与**入规格**（横纵轴、序列、图层、
  布局、钉住的定义域 `fylite:domain`）。每块瓦片的标题栏有一个**标记**：有瞬态改动未钉住时
  显示「未钉住」，钉住即写进规格并清掉标记。原 v0.1 的第三种（图层开关直接入规格而缩放不入）
  取消：图层开关与钉住走同一条路，所以用户能从标记预知「导出的报告带不带我刚才的操作」。
  数据页那种「框选 = 重取样」（§一 之 5）不变——它是取数面的事，图上用同一手势、状态行
  说清是哪一种。
- **同步**：同一坐标族（横轴绑定同一个坐标路径，例如 `time`）的所有视图**共用一个定义域
  与一个光标**；剖面视图的时间片跟随时序光标。同步的单位是坐标族而不是「所有图」，因为
  ρ 与 t 不该同缩放。

(fylite-app-frontend-figures-workbench)=
## 工作台 (The Workbench)

```{figure} ../figures/fe-workbench.svg
:name: fig-u18-workbench
:align: center
:width: 100%

工作台（概念图）。左：可用视图——按规则从记录推出的、已在台上的、可自组的；右：12 列
栅格上的瓦片，拖标题移动、拖右下角缩放，一块正在拖入，松手即写回 `fylite:layout`。
```

工作台是规格的编辑器：左栏是可用视图（`derive()` 从记录推出的全部视图，加上用户自组的
「任选两量」），右栏是 12 列栅格上的瓦片。每块瓦片是规格里的一个 `has_view` 项；移动与
缩放写 `fylite:layout`（U-14）；每块瓦片自己的菜单（横轴、图层、导出 SVG）写视图自己的
字段。首行第一块是首屏输出（P-26 由默认布局满足：`derive()` 的第一个视图落在 (0, 0)）。
台上的图与报告里的图是**同一份规格的两次投影**——工作台不导出图片，导出的是规格。

(fylite-app-frontend-figures-analysis)=
## 分析工作要的三种视图与一种手势 (Three Views and One Gesture for Analysis Work)

〔为什么〕v0.1 的规格只有 `line_chart` / `scalar_readout` / `map` 三种视图。`FYL-DESIGN-12`
要求逐通道残差画成**零线上的茎**（明文禁止折线，因为横轴不连续）、逐通道残差**表**、
批处理与时间序列的**判定行表**、以及「钉住列作比较」；反演 bar 的常规动作是在截面上
点一个通道改权重。这四件在 v0.1 里没有落点，是评估找出的最实质的缺口。

**U-21 视图种类增列 `stem` 与 `table`。** `view_kind: stem`：每条序列绑定一个按通道
索引的一维量（如 `magnetics#…/residual`），画成零线上的茎，横轴是通道序号，通道名从
`name` 取；`view_kind: table`：列绑定量（逐通道残差表：名 · 权重 · 实测 · 拟合 · 残差；
判定行表：行 · 状态 · 判据）。两种都是规格里的视图，报告照渲染（Python 端 `casereport.py`
对 `table` 已有表格体例，对 `stem` 需补一种 SVG）。**禁止 (MUST NOT)** 把不连续横轴的量
画成 `line_chart`（P-27 的「横轴不连续」条款的机器化）。

**U-22 对照是规格里的一个角色：`series_role: baseline`。** 工作台的每块瓦片有「以另一份
记录为对照」操作：选一份记录（断点仓、导入的记录、上游 bar 的记录），该视图的每条序列
得到一条同路径的 `baseline` 序列（细虚线，非颜色通道），`stem` 视图得到成对的茎，`table`
视图得到对照列与差值列。对照记录进 `presents[]`，报告的「方法」节列出它。

**U-23 通道权重在图上编辑：点通道，写手填层。** 极向截面里点一个探针 / 磁通环，弹出
该通道的权重与开关；改动写进端口源栈的手填层（U-5 第七行，`fylite:weight[i]` 与
`fylite:enabled[i]`，带 `fylite:edited_from`），并按 U-15 成为计划的一个版本。★卷宗关掉的
通道**不能**在这里打开（`-12` G-9 的分权：卷宗说「这台机器上它坏了」，页面只能在卷宗
允许的集合内取舍）；这类通道在图上画成空心并带「卷宗禁用」的悬停说明。

**U-24 解释性文字的去向：词表一句，场景一段，页面一段。** 词表的 `gloss` 只许**一句**
（控件旁的一行）；一条场景的**为什么取这个值**留在它自己的 `note`（语料现行的
`breakdown-iter` 式长注），由输入页在表单顶部渲染为可折叠的一段；页面级的方法说明
（`data-i18n` 长注）**不删**，仍是页面内容。三处各答一个问题：这是什么 · 这里为什么这么设 ·
这一页怎么用。U-1 删的是手写控件，不是这三种文字。

(fylite-app-frontend-exchange)=
# 九 · 导入、导出与移步离线 (Import, Export and Moving Elsewhere)

**U-18 只有一种交换单元：文档集。** 导出的东西是一个 zip（或桌面上的一个目录）：
`plan.jsonld` · `inputs/*.jsonld`（源栈里每一层的文档）· `record.jsonld`（含状态）·
`presentation.jsonld` · `environment.json`（内核身份，K-7）· 可选 `report.md` +
`figures/*.svg`。导入按内容认每一份（`appio.js` 的 `sniff` 从 `@type` 判，§一 之 8），
**不问文件名**；缺哪一份就少哪一条投影（只有计划 → 输入页；计划 + 记录 → 图与报告），
不报错。★`fylite:AppSession/1` 退役：它的 `fylite:config` 就是 `parameters[]`，
`fylite:result` 就是记录——两种文档合成一种（§一 之 2 的缝）。

**U-19 移步 = 同一份文档集在别处继续。** 四个宿主（`-16` H-3）都认这份文档集：
桌面 `fy case run plan.jsonld --bind … --resume record.jsonld`；Python
`cases.run(plan, resume=record)`；另一台浏览器导入即认；AI 面收计划、回记录。
「移步离线」于是没有专门机制：静态站点载入后本来就是离线的（J-4），要带走的只是
文档集。★`--resume` 与 `resume=` 是**本篇的提案**（G-4），`-17` 的 `fy case run` 今天
没有这个旗标；它落地时须走 `_cli.json`（C-1）。

**U-20 离线是默认态；持久化分两处。** 静态站点补一份 web app manifest 与一个只做
预缓存的 service worker（今天没有，§一 之 7），使**断网后重新打开**也能载入——今天
「载入后离线可用」成立，「断网后重开」不成立，这是 NR-ENV-001「浏览器运行时须离线可用」
没有量到的半句。桌面版不需要（bytes 在可执行文件里）。持久化：断点仓与草稿计划进
**IndexedDB**（大小与结构化），偏好（折叠、语言、主题）留 `localStorage`；两处都在 try/catch
里（§一 之 7 的理由不变）。`handoff.js` 的单槽退役为「记录作为源」（U-5）。

(fylite-app-frontend-rulings)=
# 十 · 裁定汇总 U-1..U-24 (Rulings)

:::{table} 本篇二十四条裁定，一行一条；「删掉」列是 J-10 的账。
:name: tbl-u18-rulings
:align: left

| 编号 | 一句话 | 上游 | 删掉 / 替代 |
| :--- | :--- | :--- | :--- |
| U-1 | 页面是计划的投影，一条声明一个控件 | H-1 · DE-LOG-07 | 四页手写 `.ctl` 块 · `sliders` 表 |
| U-2 | 控件由词表类型决定（八行映射表） | K-2 | 页面 i18n 里的单位文字 |
| U-3 | 词表管分组次序，页面管折叠 | P-16 | 各页固定的「高级」清单 |
| U-4 | 值域三层：词表 → 卷宗 → 用户 | `-09` 卷宗量程先例 | `session.apply` 的 clamp → 标记 |
| U-5 | 组合只在中间层做一次，页面排源栈 | D-3 · L-1 | 页面自己的合并逻辑 · `handoff.js` |
| U-6 | 每个量标出来源 | P-13 · L-11 | — |
| U-7 | 同名叶子上面赢，被盖住的仍列出 | E-3 同形 | — |
| U-8 | 步预算是计划字段，运行是一串门调用 | S-3 · S-4 | `evolve` 的特例升格为通则 |
| U-9 | 进度数出来，取消切预算，终止只留硬中断 | 〔回调撤回〕 | worker 的 `progress` 消息 |
| U-10 | 断点是一份记录（IndexedDB） | S-4 · S-5 ④ | — |
| U-11 | 断点带内核身份，别的内核拒绝 | S-6 · K-7 | — |
| U-12 | 规格三选一：自带 → 工作台 → 规则 | `casereport` 现行 | — |
| U-13 | 报告是记录的投影，不内联不评判 | `report-template` | 画布截图 |
| U-14 | 布局是规格的扩展词（`fylite:layout`） | — | — |
| U-15 | 试改是计划的改写，可撤销，无第二份几何 | H-1 · D-12 | 页面私有的几何状态 |
| U-16 | 图层即规格里的 layer 词 | FYO-ADR-09 · P-18 | 页面私有的勾选框状态 |
| U-17 | 坐标轴来自声明；缩放与光标按坐标族共享 | `casereport` P2 · P-3 | — |
| U-18 | 只有一种交换单元：文档集 | E-1 · K-7 | `fylite:AppSession/1` |
| U-19 | 移步 = 同一份文档集在别处继续 | H-3 | — |
| U-20 | 离线是默认态；断点进 IndexedDB | NR-ENV-001 | — |
| U-21 | 视图增列 `stem` 与 `table`；不连续横轴不得画折线 | `-12` 残差茎 · P-27 | 各页手画的残差图与判定表 |
| U-22 | 对照是规格里的角色 `baseline` | `-12` 钉住列 | 页面私有的「钉住列」状态 |
| U-23 | 通道权重在图上编辑，写手填层；卷宗禁用的不能打开 | `-12` G-9 | 逐通道权重滑杆表 |
| U-24 | 解释性文字：词表一句 · 场景一段 · 页面一段 | L-4 · 语料 `note` | — |
:::

(fylite-app-frontend-proposals)=
# 十一 · 提案 (Proposals into SRS / SDD)

〔信息性〕编号在 `FYL-SRS-01` 附录〈提案登记〉登记，落文本走 SRS / SDD 的版本行。
`NR-QUAL-006` 空置（`-11` / `-12` 撞号后并入 005），本篇从 007 起。

:::{table} 本篇提出的需求与设计元素编号。
:name: tbl-u18-proposals
:align: left

| 提案 ID | 大意 | 本篇裁定 |
| :--- | :--- | :--- |
| FR-UI-003 | 功能页的参数控件由 code 控制词表生成；声明与控件一一对应 | U-1 · U-2 · U-3 |
| FR-UI-004 | 输入端口可绑定多个源；合并由中间层完成；逐量出处可见 | U-5 · U-6 · U-7 |
| FR-UI-005 | 多步 code 以步预算分片执行；进度按步实测；取消不丢已算步 | U-8 · U-9 |
| FR-UI-006 | 断点与恢复以记录为单位；跨宿主可恢复；内核身份不符时拒绝 | U-10 · U-11 · U-19 |
| FR-UI-007 | 页面图形与报告由同一份呈现规格驱动；图层、布局、视图写回规格；视图含茎、表与对照 | U-12 · U-14 · U-16 · U-17 · U-21 · U-22 |
| FR-UI-008 | 几何、剖面与通道权重的交互试改改写计划，可撤销，无页面私有几何 | U-15 · U-23 |
| NR-QUAL-007 | 表单 ↔ 词表一致性、两端规格一致性、断点等价性、文档集往返各有门禁 | §十二 四道闸 |
| DE-LOG-13 | 表单生成（词表 → 控件；`form.js`） | U-1..U-4 |
| DE-LOG-14 | 断点即记录（`run.js` ↔ IndexedDB ↔ 文档集） | U-8..U-11 · U-18 |
| DE-LOG-15 | 呈现规格双向（`fig/*.js` · `workbench.js` ↔ `presentation.jsonld`） | U-12..U-17 · U-21 · U-22 |
:::

(fylite-app-frontend-deltas)=
# 十二 · 要改口的既有裁定 (Deltas to Standing Rulings)

:::{table} 本篇对上游裁定的三处改口——都是**增列**，不删已有条款。
:name: tbl-u18-deltas
:align: left

| 出处 | 现文 | 改为 | 理由 |
| :--- | :--- | :--- | :--- |
| `FYL-DESIGN-16` K-2 | code 表声明「需要哪些输入、产出哪些 fyo 路径、什么单位」 | 增列**每个参数的控制词表条目**：`type` · `units` · `range` · `step` · `default` · `choices` · `group` · `advanced_of` · `tier` · `gloss`（本仓自写） | U-2 需要类型；三个宿主校验同一份（`--set k=v` · Python · 页面）；`gloss` 自写是 L-4 |
| `FYL-DESIGN-10` P-4 | bar 间交接两种机制（页内文档 / 页总线） | 两种收成一种：**记录作为源**（源栈的一层，带世代号） | U-5；同时关 `-12` G-2、替代 `handoff.js` |
| `FYL-DESIGN-17` E-5 | `fy case run` 只有三个通用旗标 | 增列 `--resume <record>`——它不是 `--set` 的糖，是绑定一份记录源 | U-19；须走 `_cli.json`（C-1）；E-5 的「其余一律 `--set`」对**绑定**本就不适用（`--bind` 已在） |
:::

(fylite-app-frontend-stages)=
# 十三 · 分期与门禁 (Stages and Gates)

〔判读〕本篇的落地与 `-16` 的九步总线咬合：词表要等 K-2 增列（P0 之后），源栈要等
中间层进 wasm（W-1），把手到不了 C 档不用等任何人。

:::{table} 三期。「不动内核」的一期先走，因为它删的手写行最多。
:name: tbl-u18-stages
:align: left

| 期 | 前置 | 做什么 | 判据 |
| :--- | :--- | :--- | :--- |
| **U0 不动内核** | 无 | 从今天的 `BLOCKS` + `_manifest/*.jsonld` 生成五个 raw entry 的词表草表（缺 `range` / `tier` 的先由页面现有 `min/max` 誊录，标 `[TBD]`）；`form.js` 生成一页（先 `model`，因为它的 41 点解在页线程上，A 档最容易量）；`fig/*.js` 从画布改画规格（先 `line_chart` 与 `map`）；`evolve` 的断点进 IndexedDB；`fylite:layout` 与工作台 | 表单闸 · 规格闸对 `model` 页通过；`page_model.html` 手写 `.ctl` 归零 |
| ★U0 已落（2026-09-04，第四步） | — | **工作台与布局**：`app/assets/workbench.js` 把规格的每个视图做成 12 列栅格上的一块瓦片——拖标题移动、拖右下角缩放，落点写 `fylite:layout`，并把 `has_view` **按先行后列重排**（U-14：不认识该词的渲染器读的是次序，所以次序必须与看到的一致）；框选缩放与光标**按坐标族共享**（时序动、剖面不动，U-17）；瞬态与入规格**两种状态**，未钉住的瓦片带「未钉住」标记，钉住把定义域写进 `fylite:domain` 并清标记；图层开关立刻入规格（U-16）。导入的规格与导入的会话文件同样不可信：布局一律夹进栅格。`plot.js` 补正向映射 `toPixel` 与绘图框 `box`（画光标需要，与既有的逆映射对称）。**未落**：把工作台挂进某一页（要先有记录）；自组视图（任选两量）的入口；瓦片菜单里的换轴与图层清单 | `validate-workbench.mjs` 两节十三项通过。★闸子逮到一处真缺陷：夹到栅格内的钳位只写在拖拽处理器里，程序化的 `move()`（预设布局、导入的规格、自己算坐标的调用方）能把一块瓦片放到第 6 列却给 12 列宽，CSS 静默溢出——钳位已移进 API |
| ★U0 已落（2026-09-04，第三步） | — | **执行与断点**：`app/assets/run.js` 把一次多步运行做成**一串门调用**——步预算分片（每次调用瞄准 200 ms，交互档 DE-LOG-04）、进度由**调用方数出来**而非内核回报（门上没有回调）、剩余时间**报出不承诺**、`cancel()` 把剩余预算切到 0（本片结束即停，已算的步全在），`terminate` 只留作**硬中断**并另有其名。步进器是**注入的**：`run.js` 不认识 worker、wasm 或 fyo，这正是等价性能在无内核环境下被断言的原因。`app/assets/checkpoint.js` 把断点存进 IndexedDB——**没有断点格式**，存的就是那份记录的原文本（与导出同一批字节，U-18）；清单行的每个值都读自记录；`resumable()` 按 K-7 的内核身份判可否续，不符按名拒绝并说出两个哈希，显式允许漂移时把它写进 `environment` 与 `caveat`（U-11 · S-6）。**未落**：把 `worker.js` 的 `evolve` 逐步驱动接到 `FyRun`（要 wasm）；单步 code 的「求解中 · 预算 ≤ 1.5 s」措辞；硬中断的超时判定 | `validate-checkpoint.mjs` 两节十四项通过。★**闸子逮到两处真缺陷**：①恢复后的行军从步 0 重新开始，「N 步一次 ≡ k 步 + 恢复(N−k) 步」当场不成立（改为从 `state.step` 续号）；②分片可以跨过断点间隔，实测 30 步、每 10 步一存的行军**一次也没存**（改为分片不得越过断点边界）。第三处是闸子自己的假阳性：它把注释里的 `terminate()` 当成代码 |
| ★U0 已落（2026-09-04，第二步） | — | **规格驱动的图形**：`app/assets/fig.js` 把 `spo:PresentationSpecification` 的五种视图（`line_chart` · `stem` · `map` · `table` · `scalar_readout`）画到页面画布上，解析一律走 `casereport.js` 导出的 `index` / `resolve` / `coordinateOf`（**不另写第二份**）；`plot.js` 增 `stems` 记号（U-21：不连续横轴不画折线）；`series_role: baseline` 以虚线区分（U-22）；`fylite:domain` 与 `fylite:visible` 被采用（U-17 · U-16）；画不了的视图按名拒绝并计入 `refused`（P-6 · P-10）。规格词表 `docs/examples/context.jsonld` 补 `layout` / `visible` / `domain` 与 `fylite:` 前缀（**G-3 关**）。**未落**：功能栏仍直接调 `FyPlot`——把它们改成「产出记录 → 画规格」要先有记录，而记录要内核（G-13 与 `-16` 分期）；交互（框选 · 光标 · 钉住）属工作台 | `validate-fig.mjs` 三节十项通过：解析不重复、词表三词在、浏览器里五种视图各画对（横轴取自坐标声明、茎带零线与通道序号、表逐行、baseline 有非颜色通道、钉住的定义域被采用、三种画不了各出一句指名的拒绝）。★闸子首跑即逮到 `fig.js` 自身一处缺陷：未知 `view_kind` 画了拒绝句却仍计为「已画」 |
| ★U0 已落（2026-09-04，第一步） | — | **`model` 页的表单生成**：`tools/transcribe-form-vocab.mjs` 一次性把 141 个控件（108 滑杆 · 8 枚举 · 25 布尔）誊录进 `app/assets/vocab-model.js`，页面只剩 `data-form` 挂点；`app/assets/form.js` 在 `scenario.js` 之前同步画出控件（同 id · 同 i18n 键 · 同读数），控制器与会话层一行不改。**未落**：词表的 `iri` / `tier` / `group` 全为 `[TBD]`（G-1）；数字孪生未画；分组仍由页面结构决定（U-3 待 U2）；`transport` 的 `BLOCKS` 与词表未对账 | `validate-form.mjs` 三节通过（141 ↔ 141 双向；浏览器逐条相符；`FySession.collect` 读回默认值）；`page_model.html` 无 `<input>` / `<select>`；首屏输出 790 px 不变；闸子暴露并改正一处潜在缺陷（`width` 默认 0.35 不在 0.02 格上，浏览器一直吸附为 0.36） |
| **U1 中间层进 wasm 之后** | W-1 | 源栈经 `assemble`；`geqdsk.js` / `session.js` 退役（H-4 已定）；`AppSession/1` 退役为文档集；service worker 预缓存 | 往返闸通过；静态站点断网重开可载入 |
| **U2 十个工具全过门之后** | P1 | 词表从内核 code 表读（K-2 增列落地）；四页全部生成；U-8 对所有多步 code；`--resume` 入 `_cli.json` | 四页 `fylite_rs_*` 归零（`-16` P1 判据）+ 四页手写控件归零；断点闸对每个多步 code |
:::

〔门禁〕四道闸，各对应 NR-QUAL-007 的一句：

1. **表单闸**（`validate-form.mjs`）：对每个 code，词表里每条参数在页面上恰有一个控件
   （id = `code/<cap>#<name>` 的确定映射），页面上没有任何控件不对应词表；两个方向都查
   （`-10` G-14 的「双向」教训）。
2. **规格闸**（扩展 `validate-report.mjs`）：同一份记录，页面 `derive()` 与 Python
   `derive_presentation()` 逐字段相同——**已有**；增列：带 `fylite:layout` 的规格经 Python
   渲染时该词被忽略且视图顺序不变。
3. **断点闸**（`validate-checkpoint.mjs`）：N 步一次调用 ≡ k 步 + 恢复 (N−k) 步，逐位相同
   （`worker.js:8290-8371` 对 `evolve` 已声明此性质；闸把它做成断言并推广到每个多步 code）。
4. **往返闸**（`validate-bundle.mjs`）：导出文档集 → 清空 → 导入 → 再导出，`plan.jsonld`
   与 `presentation.jsonld` 逐字节相同；`record.jsonld` 逐叶子相同。

(fylite-app-frontend-gaps)=
# 十四 · 缺口 (Gaps)

| | 缺口 | 证据 | P |
| :--- | :--- | :--- | :--- |
| **G-1** | **控制词表今天不存在**：`code/<cap>#<name>` 只是名字；`BLOCKS` 有单位无值域；U-2 的映射表没有输入 | `fyo-interface.js:215-217` · §一 之 1 | P0 |
| **G-2** | **A 档在文档门上未实测**：拖把手每帧一次门调用（编码 + 一列重算）能否 ≤ 50 ms，`-16` G-1 同问；U-8 的「每次调用 ≤ 200 ms」是工作假设 | `-16` G-1 · U-8 | P0 |
| **G-3** | **规格词表缺三个词**：`fylite:layout` · `fylite:visible` · `fylite:domain` 尚未进 `context.jsonld`，U-14 / U-16 / U-17 无处落 | `docs/examples/context.jsonld` | P1 |
| **G-4** | **`--resume` 不在 `_cli.json`**，Python `cases.run` 无 `resume=`；U-19 的移步今天只有浏览器一端 | `python/fylite/_cli.json` · `-17` E-5 | P1 |
| **G-5** | **静态站点断网重开不可载入**：无 manifest、无 service worker；NR-ENV-001 的「离线可用」只量了「载入后」 | §一 之 7 | P1 |
| **G-6** | **ρ → R 映射的来源未定**：U-17 允许以中平面 R 作横轴，需要记录里有 `equilibrium` 的 `profiles_1d/r_outboard` 或等价量；今天的 `LADDER` 表有无此列未查 | `fyo-interface.js` `TABLES.LADDER` | P2 |
| **G-7** | **路点编辑的「在限制器之内」判据**：多边形包含测试在页面里做还是在中间层做（它是文档操作，D-4 归中间层）未裁 | U-15 | P2 |
| **G-8** | **报告页与四页的外壳关系**：`-11` G-9 说 `report` 是否入闸的四页要在 `page_*` 提正本时一并定；本篇把报告页当第五页画（{numref}`fig-u18-report`），但外壳的 ⑤ 槽对一个不算的页说什么，未裁 | `-11` G-9 | P2 |
| **G-9** | **预览图与页面无闸**：八张图是概念图，`-11` G-12 对 `desktop-*.svg` 的同一缺口 | `tools/make-frontend-design-figures.py` | P2 |
| **G-10** | **`stem` · `table` · `baseline` 三个词未进规格词表**，Python 端 `casereport.py` 对 `stem` 无 SVG、对 `baseline` 无成对渲染；U-21 / U-22 今天只在浏览器端可落 | `docs/examples/context.jsonld` · `casereport.py` | P1 |
| **G-11** | **权重编辑的判据来源**：U-23 要求页面知道「卷宗禁用」的通道集合；该信息在装置文档的哪个槽（`fylite:channel_map` 或另一处）未查 | `fyo-interface.js` `TABLES.DEVICE` | P1 |
| **G-13** | **两端规格比对today没在跑**：`app/tests/validate-report.mjs` 调 `python3 -m fylite cases --report`，而 2026-09-04 的裁定撤掉了 Python 侧命令行（实测 `No module named fylite.__main__`）。U-12「两端推出同一份规格」今天没有任何门在断言 | 实测 `node app/tests/validate-report.mjs`；`FYL-DESIGN-15` 的撤除记录 | P0 |
| **G-12** | **场景 `note` 的渲染位置未量**：U-24 把长注放在表单顶部折叠段，它是否把首屏输出推出 900 px（P-26）未在 `page_*` 上实测 | `-11` V-13 闸 | P2 |

〔开放项〕**词表与 i18n 的关系。** U-2 让 `gloss` 与 `choices` 的文字来自词表而非页面
i18n；词表是否分语言（`gloss: {zh, en}`，同语料的 `title` 形）、还是词表只有一种语言而
页面译——本篇倾向前者（与 `title` / `note` 同形，J-9 的「自写」对两种语言各成立一次），
**不裁**，宜与 K-2 增列一并定。

〔开放项〕**工作台的自组视图在报告里的位置。** 「任选两量」的 x–y 视图不是 `derive()`
能推出的，报告的「结果」节按 `has_view` 顺序画它没有问题；但它是否该进「方法」节说明
「这张图是人组的」——`casereport` 的 `caveat` 可以承载，措辞未定。

(fylite-app-frontend-assessment)=
# 十五 · 评估：分析工作 · 认知负担 · 学习曲线 (Assessment)

〔已确立·方法〕对象是 `FYL-DESIGN-12` 的四条 bar（剖面拟合 → 平衡反演 → 时间序列 → 批处理）；
评估依据是本篇文本与 `-12` 的裁定，无用户实测。v0.2 的 U-21..U-24 与 U-17 改写即此评估
的结论落文本。

〔判读·适用性〕输入侧与流程侧覆盖充分：测量装配天然多源（源栈），四条 bar 的依赖由
「记录作为源」承载，拟合对比由多角色序列承载，批处理与序列由步预算与断点承载。输出侧
在 v0.1 缺三种视图（茎 · 表 · 对照）与一种手势（点通道改权重），v0.2 补入；仍开的是它们在
Python 端的渲染（G-10）。试改机制（U-15）对分析工作只有剖面节点一项相关。

〔已确立·概念计数〕用户可见的新概念九个：计划 · 记录 · 呈现规格 · 控制词表 · 源栈及其
叶子级优先序 · A/B/C 档 · 世代与过期 · 断点 · 文档集；今天的页面是四个（bar · 滑杆 ·
导入 · 导出）。负担最重的两处：视图状态（v0.1 三种，v0.2 收成两种并加标记）与叶子级
优先序（U-7；出处表能解释，源栈本身不能——这是接受的代价，理由是一个 IDS 里几何与
测量常来自两处）。减轻机制：P-16 折叠、`derive()` 的默认视图、预设只填不跑，使只跑预设的
人不接触上述大部分概念。

:::{table} 三种角色的学习曲线（工作假设，无实测）。
:name: tbl-u18-personas
:align: left

| 角色 | 需掌握的概念 | 曲线 | 依据 |
| :--- | :--- | :--- | :--- |
| 跑预设、读报告 | 导入文档集 · 运行键 · 报告五节 | 平缓，与今天相当 | P-23 · U-12 ③ · U-18 |
| 做分析（装配测量 · 调权重 · 比拟合 · 跑序列） | 源栈 · 记录作为源与过期 · 坐标族 · 两种视图状态 · 断点恢复 | 中等；台阶在源栈与「未钉住」标记 | U-5..U-7 · U-17 · U-22 · U-23 |
| 加场景、写词表、带规格入库 | JSON-LD 词表字段 · `spo:PresentationSpecification` · `fylite:layout` · 四道闸 | 陡峭；复杂度有意推向此端 | U-2 · U-12 ① · U-14 · §十三 |
:::

〔结论〕设计把复杂度从「每页手写」搬到「词表与规格」：第一类角色负担下降，第三类上升，
做分析的人基本持平但换了一套心智模型。v0.2 之后仍需实测的是 G-2（A 档延迟）与 G-12
（长注对首屏的影响）。
