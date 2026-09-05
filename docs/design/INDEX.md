---
document_id: FYL-DESIGN-00
title: 设计书目录 (Design Book Index)
shortname: fylite-design-index
version: "5.26"
date: 2026-09-05
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Fable 5
created: 2026-08-18T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-05T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v5.27 `FYL-DESIGN-16` 升 v2.2 · `FYL-DESIGN-15` 升 v1.2（2026-09-05 两条用户裁定，
    算力面从「一次发行两个实现路径」收到一个）：**（一）webui 中 fylite_rs /
    fylite_kernel_ext wasm 功能由 api 端提供，只静态网页走 wasm** —— H-6：`POST /api/kernel`
    是一次内核调用的逐参数转述，参数种类表由内核仓自 `c_api.rs` 生成给服务端与页面两侧
    （251 个导出桥 248 个；结构门与分配器一对按名拒绝，后者若照桥就是让内核释放桥自己的
    内存）；页面 140 处调用点一处未改。**（二）fy 封装 fylite_kernel 静态库，.so 留给
    python 层，wasm 留给静态网页发布** —— K-9 / K-10：内核有三种形，各有唯一读者；`fy run`
    与内嵌页面因此在没有任何 `.so` 的机器上都完整可用。实测：静态库 +3.10 MB、去掉的两份
    内核 wasm −1.46 MB；两条算力路逐位比对，纯算术相同、含超越函数的差在末位（最大
    1.4e-15，判读为两份 libm 的末位取舍）。G-7 原生那半关闭，新记 G-9（NOTICE 不随可执行
    文件与站点走）与 G-10（迭代型入口的往返延迟未量）。
    · v5.26 `FYL-DESIGN-19` 升 v0.5（A-15 收口：两条用户裁定关掉 G-10 与 G-9——**接受混合来源**
    〔A-16：不设合成轴，电气一侧与线圈几何合住一份 `pf_active`，来路逐段写明，校核判定随之
    `consistent` → `partial`〕与 **operational 作为自定入 fyo**〔A-17：新模块
    `fyo/schema/src/process/operational.linkml.yaml`，根类走 `fyo_path`；namelist 逐组承载
    不逐键入本体〕。fyo 另开三个自有槽：`circuit_model_resistivity` · `time_constant` ·
    `element_weight`，三个都是为了不让一句假话写得合法。EAST 四块全部到位）。
    v5.25 `FYL-DESIGN-19` 升 v0.4（A-15 落地一块、剩两块：EAST 被动结构 90 个 loop 已进 fydata 与
    fydoc，双门禁 0 error；电源那批**一半本来就在**——匝数与 IC1/IC2 早在 `providers/pf_active/base.yaml`，
    剩下的卡在新记的 G-10「一个 IDS 一份文档，没有合成轴」；`operational` 仍卡 G-9。另记 G-11：
    fydoc 的 `dataset_fair.jsonld` 带着 fydata 侧没有的再分发裁定块，重跑誊录器会静默删掉）。
    v5.24 `FYL-DESIGN-19` 升 v0.3（两条用户裁定：缺省即全功能版含 EAST，作为内部工具发布——A-14
    并已实施，六处缺省翻成 `internal`，公开面自此必须明写 `--public`，内嵌资源表闸随之换向并修好
    一条恒真断言；EAST 四块进 fydoc 的 A-Box——A-15，并更正 A-10：79 探针基**已在** fydoc，缺的是
    另外三块，且路线须走 fydata → `abox2jsonld.py` → fydoc。新增 G-8 / G-9）。另修 `_environment.json`
    与 `test_environment_table.py`：扫描前缀漏了 `FYDOC_`，令两向闸子**两向都红**，并补声明
    `FYDATA_ORACLE`（代码仍认的旧名）。
    v5.23 `FYL-DESIGN-19` 升 v0.2（用户裁定：`wall_ggd` 不入仓，只带 `wall` / `pf_active` / `tf` /
    `magnetics` 加必要诊断——A-13 的逐 IDS 白名单，实测白名单文本面 731 KB 而 `wall_ggd` 一项 10.1 MB）。
    v5.22 新增 `FYL-DESIGN-19`（facts 的发行形态：评估「从 fydoc 收装置 A-Box，合成 `facts.jsonld`
    与 `facts.rs` 两份生成物，顶层不留 `facts/`」——方向判对，改写为搜索路径的**自带那一档**；
    裁定 A-1..A-12）。
    v5.21 `FYL-DESIGN-18` 升 v1.5（合并后随 `-17` v1.1 的 E-23 改口：`fy case run` → `fy run`）。
    v5.20 **两条线合并**（`develop` ← `claude/fylite-frontend-design-78szkh`）。★两边都在改这本
    登记册，且**各自用过 v5.6..v5.9 指不同的事**——命令行那条线在写 `FYL-DESIGN-17`，前端那条线
    在写 `FYL-DESIGN-18`。号已经发出去了，改号会让两边的提交信息都对不上，所以**两段历史各自
    保留、按来源标明**，本条取一个高于双方的号。合并本身没有内容取舍：`E-` 与 `U-` 两个编号域
    互不相干，目录表两行各归各位。
    〔命令行线，原 v5.6..v5.9〕
    v5.9 `FYL-DESIGN-17` 升 v1.3（补上门禁 ① 与 ⑤ 的可执行形；`--dry-run` 下未解析的端口改为一行输出）。
    v5.8 **P1 落地**（用户「完整实现 cli 设计」）：`FYL-DESIGN-17` 升 v1.2（as-built 一节 + 三处与设计
    不同的落法）、`FYL-DESIGN-15` 升 v1.1（四条命令词；C-1 补规格与模板的分工）。
    v5.7 `FYL-DESIGN-17` 升 v1.1（两条用户裁定：`case` 收进 `run`、`case` 弃用；新增 `list` 命令——
    `fy` = `app` / `data` / `run` / `list`；E-23 / E-24，E-2 / E-4 / E-5 / E-6 / E-10 / E-21 修订）。
    v5.6 `FYL-DESIGN-17` 升 v1.0（由评估升为详细设计：第四条命令词 `run <线> [<场景>]`，两段解析、
    参数记法、合成次序、装置两条路、测量三级、环境变量全表、场景目录；E-10..E-22，E-4 / E-5 / E-6 修订）。
    〔前端线，原 v5.6..v5.19〕
    v5.19 `FYL-DESIGN-18` 升 v1.4（裁定 U-25：导入 h5wasm，浏览器读 HDF5 走「第三方读者 → fyo 文档
    → 源栈一层」，按需加载不进预缓存；HDF5 闸与原生读法逐叶子一致）。
    v5.18 `FYL-DESIGN-18` 升 v1.3（中间层 wasm 门开一半：17 个导出；拦路的不是 mdsip 而是一刀切的
    wasm 排除；`assemble` 仍留本机）。
    v5.17 `FYL-DESIGN-18` 升 v1.2（用户裁定「Python 不接入前端」：源栈闸不再借 Python 执行合并；
    新缺口 G-15——中间层的 wasm 层零导出，H-4 / W-1 今天不成立）。
    v5.16 `FYL-DESIGN-18` 升 v1.1（§五 源栈落地，装配文档由真中间层验证；新缺口 G-14）。
    v5.15 `FYL-DESIGN-18` 升 v1.0（§八 试改落地；内核在本环境构建，两端规格比对首次跑通，G-13 关）。
    v5.14 `FYL-DESIGN-18` 升 v0.9（G-13 的调用已修：报告闸改为库调用，由抛异常变为按内核缺席跳过）。
    v5.13 `FYL-DESIGN-18` 升 v0.8（离线预缓存落地，断网实测通过，G-5 关）。
    v5.12 `FYL-DESIGN-18` 升 v0.7（文档集与往返闸；设计点名的四道闸全部存在且通过）。
    v5.11 `FYL-DESIGN-18` 升 v0.6（U0 第四步：工作台与 `fylite:layout`，工作台闸成立；U0 四条落齐）。
    v5.10 `FYL-DESIGN-18` 升 v0.5（U0 第三步：执行分片、进度、取消与断点仓，断点闸成立）。
    v5.9 `FYL-DESIGN-18` 升 v0.4（U0 第二步：图形改由呈现规格驱动，规格闸成立；新缺口 G-13）。
    v5.8 `FYL-DESIGN-18` 升 v0.3（U0 第一步落地：model 页表单由词表生成，表单闸成立）。
    v5.7 `FYL-DESIGN-18` 升 v0.2（按分析工作评估：茎 / 表 / 对照三种视图、图上改权重、视图状态
    收成两种、解释性文字去向；U-21..U-24；〈评估〉一节）。
    v5.6 新增 `FYL-DESIGN-18` v0.1（应用前端详细设计：场景驱动的输入页 · 多源组合 · 执行与断点 ·
    呈现规格与报告 · 交互图形四件 · 文档集交换；裁定前缀 `U-` 入编号登记；八张 `fe-*.svg`
    预览图与 `-11` 共用一条外壳）。
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
| 版本 (Version) | v5.26 |
| 发布日期 (Date of Issue) | 2026-09-05 |
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
   功能页各一篇，`-18` 四页共用的输入生成、图形交互与文档交换。设计书的规范条款经提案入 SRS / SDD；尚未落文本的提案编号集中登记在
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
| `K-` `F-` `B-` `S-` `N-` `D-` `H-` | `FYL-DESIGN-16` | K-1..K-10 · F-1..F-4 · B-1..B-4 · S-1..S-6 · N-1 · D-1..D-4 · H-1..H-6 | 内核契约 · 扁平树 · 补数据 · 状态 · 命名 · 中间层 · 宿主。★`-16` 的 `D-` 与 `-09` 的 `D-` 是两套，各在各篇内唯一 |
| `E-` | `FYL-DESIGN-17` | E-1..E-24 | 场景运行命令 `fy run` 与发现面 `fy list`（v0.1 的 E-1..E-9 保留编号；E-4 / E-5 / E-6 在 v1.0 修订，E-2 / E-4 / E-5 / E-6 / E-10 / E-21 在 v1.1 再修订） |
| `A-` | `FYL-DESIGN-19` | A-1..A-17 | facts 的发行形态：装置书 → 两份生成物；A-13 逐 IDS 白名单；A-14 缺省即全功能版；A-15 EAST 四块的迁移路线；A-16 混合来源；A-17 `operational` 自定入 fyo |
| `U-` | `FYL-DESIGN-18` | U-1..U-25 | 应用前端：输入生成 · 源栈 · 执行与断点 · 呈现规格 · 交互图形 · 文档集 · 第三方读者（U-25）；下一号 U-26。★`-18` 的 `J-` 是判据不是裁定，与 `-17` 的 `J-` 各在各篇内唯一 |
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
| [`FYL-DESIGN-19`](FYL-DESIGN-19.md) | **facts 的发行形态**——评估「从 fydoc 收集 device A-Box，合并成 `facts.jsonld`（进 app）与 `facts.rs`（进 rust）两份生成物，fylite 顶层不保留 `facts/`」。方向判**对**：它与本仓已有的四处生成物同一条规矩，且治住 2026-09-05 实测的两次失败（全功能构建**编不过**；公开版站点打包 **0 台**却成功）。两处按字面带不动——**清单不是卡片**（取数要的那一份，实测 13 台里只有 EAST 有）与**域有三个不是一个**（`device` · `amns` 5.8 MB · `experiment`）；一处改写——两份生成物是搜索路径的**自带那一档**而非替代，于是 `--facts` 指自己机器的能力留着、「顶层不留 `facts/`」照样成立。尺寸实测：并进去约 550 KB，A-Box 的 10.8 MB HDF5 与 `amns` 不并。★v0.2 收进「只带必要 IDS」的裁定：A-13 的逐 IDS 白名单（`wall` · `pf_active` · `tf` · `magnetics` 加 `interferometer` · `thomson_scattering` · `ece`），判据是**谁读它**而不是体量——`wall_ggd` 一项 10.1 MB 占装置书 88% 却无消费者（代码读的是 `wall` 的限制器轮廓，不是 GGD 网格）；白名单文本面实测 731 KB。★v0.3 收进两条裁定：**A-14 缺省即全功能版**（含 EAST，作为内部工具发布——六处缺省已翻成 `internal`，公开面自此必须明写 `--public`；许可判据未动，仍逐条在 `rights.json`），**A-15 EAST 三块的迁移路线**（fydata A-Box → `abox2jsonld.py` → fydoc，因 fydoc 的 `abox/` 是生成物、不得手改），并更正 A-10：**79 探针基已在 fydoc**（`efit_w_pf.jsonld` 记 79 探针 + 35 磁通环，与卡片逐数相同），缺的是 `pf_passive` / 电源四件 / `operational` 三块。★v0.5 A-15 收口：**接受混合来源**（A-16——不设合成轴，电气一侧与线圈几何合住一份，代价是校核判定由 `consistent` 降为 `partial`）与 **`operational` 自定入 fyo**（A-17——新根类走 `fyo_path`，namelist 逐组承载不逐键入本体）。EAST 四块全部到位，G-9 / G-10 关闭。裁定 A-1..A-17，三档分期加一期已实施，五条门禁，缺口 G-1..G-11 | v0.5 · WD |
| [`FYL-DESIGN-18`](FYL-DESIGN-18.md) | **应用前端详细设计**——前端不持有第二份真源：输入页是**计划经控制词表**的投影（一条声明一个控件，八行类型 → 控件表）；一个端口可组合多个源（源栈，中间层合并，逐量出处，「记录作为源」收编页间交接）；执行是一串门调用（步预算是计划字段，进度按步实测，取消切预算，**断点是一份记录**，恢复是再入，内核身份不符则拒绝）；输出经**场景自带的呈现规格**渲染为报告，工作台改的是同一份规格（`fylite:layout`）。交互图形：LCFS 把手 / 路点与剖面节点的试改（改写计划、可撤销、A/B/C 档）· 二维整合视图（图层即规格里的 layer 词）· 剖面查看器（任选两个共格点的量作轴、多信道叠加、框选缩放、时序按坐标族共域共光标）· 工作台。导入 / 导出 / 移步离线只有一种交换单元：文档集。裁定 U-1..U-24（★v0.2：茎 / 表 / 对照视图、图上改权重、视图状态两种、解释性文字去向，附〈评估〉），提案 FR-UI-003..008 · NR-QUAL-007 · DE-LOG-13..15，三期四闸，缺口 G-1..G-12，八张预览图。★v0.3：U0 第一步已落——`model` 页 141 个控件由 `vocab-model.js` + `form.js` 生成，表单闸 `validate-form.mjs` 双向成立；v0.4：图形由 `fig.js` 按呈现规格画，规格闸 `validate-fig.mjs` 成立；v0.5：执行分片与断点仓，断点闸 `validate-checkpoint.mjs` 成立（等价性判据可断言）；v0.6：工作台与 `fylite:layout`，U0 四条落齐；v0.7：文档集（存储法 zip，外部读者验证），**四道闸全部成立**；v0.8：离线预缓存（断网实测），G-5 关；v0.9：报告闸的调用已修；v1.0：§八 试改（把手 · 路点 · 剖面节点 · 通道权重，拒绝不改数），内核已构建、两端规格比对首次跑通（**G-13 关**），带生成表单的 model 页与原生一致到 1e-7；v1.1：§五 源栈（栈顶优先 ↔ merge 末位优先，由契约断言），G-14 · **G-15**（wasm 门已开一半：17 个导出；`assemble` 仍读盘）；v1.4：**U-25 导入 h5wasm**（源栈一层 · 4.2 MB 按需 · NIST 许可三项义务落实）；v1.5：随 `-17` v1.1 的 E-23 把 `fy case run` 改为 `fy run` | v1.5 · WD |
| [`FYL-DESIGN-17`](FYL-DESIGN-17.md) | **场景运行命令 `fy run` 的详细设计**（v1.2 起含 as-built）——一条命令跑一次日常建模或分析：`fy run <线> [<场景>] [--device D] [shot=N time=T] [key=value …]`，或 `fy run <计划文件>…`。**v1.1：`case` 收进 `run`、`case` 弃用（按名拒绝并指向，E-23）；新增只读的发现面 `fy list devices | experiments | scenarios | presets | facts | kernel | lines`（E-24）——`fy` = `app` / `data` / `run` / `list`（E-10）。**两段解析（静态语法在 `_cli.json`，参数表在场景模板；未知参数按名拒绝，E-11）；参数记法 `key=value` ≡ `--key=value`、`--flag` ≡ `flag=true`（E-12）；合成次序模板 → 装置 → 预设 → `--plan` → 命令行 → 端口，逐值记来源（E-13）；装置信息两条路（整份文档绑端口 + `from_device` 缺省，E-14）；测量三级解析 `--input` → 离线切片 → 取数落进记录目录（E-15）；环境变量只供资源不供物理参数，全表（E-16）；每线一条缺省场景（E-17）；模板声明的开关（`only_magnetic`，E-18）；记录目录自足（E-19）；退出码与阶段（E-20）；合成器只有一份（E-21）；模板内嵌、预设走语料路径（E-22）。场景目录逐条覆盖文档明确涉及的全部场景（S-L1..S-L5 · 十三条栏 · 9 code · 10 工具 · 指南五章），迁移表，分期 P1-a..d / P2-a..c，七条门禁 | v1.3 · WD |
| [`FYL-DESIGN-16`](FYL-DESIGN-16.md) | **可替换内核与四层分工**——内核以 fyo 文档门为唯一接口，门上是双向扁平树；内核无状态、状态随文档走；`fylite_runtime` 是中间层（SpData profile、后端表）；多宿主只写计划只读记录；内核三种形（静态库进 `fy`、`.so` 进 Python、wasm 进静态站点）与桌面宿主的算力面 `/api/kernel`；一条总线九步 | v2.2 · WD |
| [`FYL-DESIGN-15`](FYL-DESIGN-15.md) | **发布形态与统一命令行**——单一可执行文件 `fy` · 静态 / 动态网页 · Python 包，一份源；三份命令行由 `_cli.json` 一个文件建出（R-1..R-6 · C-1..C-8） | v1.2 · WD |
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
