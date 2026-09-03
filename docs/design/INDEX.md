---
document_id: FYL-DESIGN-00
title: 设计书目录 (Design Book Index)
shortname: fylite-design-index
version: "3.9"
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
  change: 'v3.9：`FYL-DESIGN-16` 升 v0.4（N-2：中间层同日再改名 `fylite_engine` → `fylite_runtime`；
    N-1 给的「与 Python `fylite.engine` 同一组件」经逐条核查为假〔二比五〕，两者是共用一个词的
    两个不同组件，`engine` 让给 Python 那一层；错的理由留在正文里记着）。
    v3.8：`FYL-DESIGN-16` 升 v0.3（N-1 已执行：`fylite_data` → `fylite_runtime`，两仓一批）。
    v3.7：`FYL-DESIGN-16` 升 v0.2（用户裁定 2026-09-04：宿主是**多宿主**非双宿主；
    `fylite_runtime` 是**中间层**，裁定 N-1 推荐改名 `fylite_runtime`、备选 `fylite_runtime`，
    命令词 `fylite data` 不改，波及面已量、本版只裁不改）。
    v3.6：收编 `FYL-DESIGN-16` v0.1（**可替换内核与四层分工**）——内核可替换
    （本地 / wasm / 远端、不同实现），fyo 文档门为唯一接口（裁定 K-1..K-7）；`fylite_runtime`
    定为 SpData 的一个 profile（D-1..D-4）；前端只写计划只读记录（H-1..H-3）。以实测为底：
    Python 125 个、浏览器 146 个扁平 C 调用 vs 文档门 3 个 code。提出两条既有裁定改口
    （NR-ENV-004 同核→同契约、DE-COMP-02 双薄面→宿主做计划），落文本另行。
    v3.5：`FYL-DESIGN-15` 的规范条款**上提**进规范链——`FYL-SDD-01` v0.13
    （布局表按分仓与数据层改写、新增组件 DE-COMP-09 数据层、声明面 `_cli.json` 成为三宿主
    共同定义并立不变式、机械核记委托、浏览器前端页面清单按实、接口视图与追溯矩阵各补一行）、
    `FYL-SRS-01` v0.5（FR-TOOL-001 改写 + 新增 FR-TOOL-004「一份规格三个宿主」，外部接口
    补单一可执行文件与静态站点）。★同批修**本表自身的漂移**：SDD 与 SRS 的版本列停在
    v0.9 / v0.3，而两篇实际已到 v0.12 / v0.4——版本号以文档自身的控制信息为准，本表补齐。
    v3.4：收编 `FYL-DESIGN-15` v0.1（**发布形态与统一命令行**）——三种发布形态（单一可执行文件 · 静态/动态网页 · Python 包）写成一份设计（裁定 R-1..R-6），三个宿主的命令行收敛到同一个定义文件 `python/fylite/_cli.json`（裁定 C-1..C-8）：
    Python 的 argparse、Rust 可执行文件的解析器与浏览器的启动参数都由它建出，只属一个宿主的少数参数在文件里标 `hosts`。
    v3.3：**共享外壳落地**（用户裁定 2026-09-01）——`app/pages/page_*.html`
    四张新页面，由 `tools/make-page-v2.mjs` 从原页面生成、`assets/shell.js` 运行时
    搬节点；**原四页一字未动留作对照组**。闸子 `app/tests/validate-page-v2.mjs`。
    随之闭合 `-11` G-10 / G-11 · `-09` G-21 · `-10` G-15 · `-13` G-19，
    `-11` G-9 降为「已落在新页面、尚未提为正本」。
    v3.2：**四页的视觉设计按共享外壳细化**（用户裁定 2026-09-01）。
    四页共用一节新增三条视觉纪律 **P-25 / P-26 / P-27**（正本在 `FYL-DESIGN-10`），
    各页再加一条自己的：`-09` D-23/D-24/D-25 · `-10` P-28 · `-12` P-29 · `-13` P-30。
    新增七张 16:9 预览图（放电设计页三个模式 + 四页各一张视觉词汇表），与外壳预览
    同一个生成器、同一条 `strip()`。★同批修一处**编号表自身的漂移**：
    `FYL-DESIGN-10` 那张声称全局唯一的 `P-` 表漏了 P-22 / P-23 / P-24，而它下面
    写着「新裁定续 P-22 起」——补齐并续到 P-30，另立缺口给它配闸子。
    v3.1：`FYL-DESIGN-11` **重构为整体桌面版应用的视觉设计**（用户裁定
    2026-09-01）：它此后管的是**四个功能页面共用的外壳**——一条常驻的两行 header
    toolbar（V-11）、四页只差的那三个槽（V-12）、16:9 定尺与首屏判据（V-13）、
    预览图纪律（V-14）与外壳／页体的分工线（V-15）；V-1..V-10 编号与含义不动。
    ★本册此前把它记作 v0.1，而它当时已是 v0.2——版本号已按实际对齐。
    v3.0：**浏览器前端四页各有一份设计文档**。`FYL-DESIGN-10` 原为
    「建模 · 分析 · 数据三页」，本次拆开——它此后**只写建模页**（v1.0），实验分析页
    与装置数据页分立为 `FYL-DESIGN-12` / `FYL-DESIGN-13`；连同放电设计页
    `FYL-DESIGN-09`，四页齐。★拆分**不重排编号**：`P-` 是四页之间的一条**全局
    序列**，条搬家不改号（P-9 / P-16 去分析页，P-10 / P-11 / P-12 / P-18 去数据页，
    P-17 / P-19 留建模页），对照表在 `FYL-DESIGN-10`
    `tbl-fylite-pages-numbering`；**四页共同的十一条纪律**（P-1..P-8 ·
    P-13 · P-14 · P-15）留在 `FYL-DESIGN-10`，另外三篇**引用而不抄**。
    同批新增 `FYL-DESIGN-11`（**视觉设计——桌面版查看器**，裁定编号 `V-`），
    并把 `FYL-DESIGN-09` 修到 v1.2（分期 P5 已落地，as-built 按实测重写，四处
    内部不一致修掉，另记一处已修的闸子失明）。
    v2.9：一条跨两篇的裁定入册（用户裁定 2026-08-31）——**建模页的含时演化栏
    收敛进放电设计页**，在那里成为仿真推进的 1.5-D 保真度档（`FYL-DESIGN-09` v1.1
    D-22：0-D / 1.5-D 由一个开关切换）；建模页此后**不含时**，只留定态输运、边界与
    度规、功率平衡反演三条栏（`FYL-DESIGN-10` v0.2 P-19）。一个应用只有一条时间轴，
    它属于放电设计页。
    v2.8：收编 FYL-DESIGN-10 v0.1（建模 · 分析 · 数据三页——与 FYL-DESIGN-09
    配套，把浏览器前端另外三页的构造、裁定 P-1..P-18、界面概念图、分档、缺口与门禁
    写在一处；裁定编号取 P- 以免与 D- 同名）。
    v2.7：FYL-DESIGN-09 改写为 v1.0（直述放电设计页的功能，移除成稿沿革）。
    v2.6：FYL-DESIGN-09 升 v0.4（命名裁定 D-21：pulse_design · pages · data）。
    v2.5：FYL-DESIGN-09 升 v0.3（三页合一裁定入册，第三幅概念图）。
    v2.4：FYL-DESIGN-09 升 v0.2（两页落地，as-built 一节入册）。
    v2.3：收编 FYL-DESIGN-09 v0.1（脉冲设计工作台——S-L4 的交互形态，
    设计与仿真两种模式；用户裁定 2026-08-31：平顶 PF 电流在 LCFS 锁定条件下随
    等离子体状态，且全脉冲设计与交互仿真并立而非互相取代）。
    FYL-DESIGN 序号续用：归档是逐篇冻结重定位之前的笔记，不是停用该系列。
    v2.2：FYL-CONOPS-00 升 v0.4（建设原则六条入册，用户裁定 2026-08-30；
    评估依据 FYL-REPORT-04）。
    v2.1：收编 FYL-SDD-01 v0.1（软件设计描述），活动编目三篇，规范链
    ConOps → SRS → SDD 齐。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-design-index

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-00` |
| 文档名称 (Title) | 设计书目录 (Design Book Index) |
| 短名 / Slug | `fylite-design-index` |
| 版本 (Version) | v3.9 |
| 发布日期 (Date of Issue) | 2026-09-02 |
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

本书收录 FyLite 的运行概念与规格文档。`FYL-CONOPS-00` 是全仓定位的锚点——FyLite 以
**轻量功能集**验证与展示 `FYTOK-CONOPS-00` 定义的五类应用任务，资源包络为单机、
交互档毫秒至秒量级响应（按功能声明预算）、有限多线程、跨平台双宿主；`FYL-SRS-01` 在该定位下给出软件需求，
`FYL-SDD-01` 给出五视图设计描述（组合视图为仓内布局的规范源）；规范链之外的**设计
笔记**（`FYL-DESIGN-NN`）按场景规划单条能力线的落法，信息性，其规范条款经提案入
SRS / SDD。

★**浏览器前端四页各有一份**：`FYL-DESIGN-09`（放电设计）· `-10`（物理建模）·
`-12`（实验分析）· `-13`（装置数据），外加 `-11` 写四页共用的那一层（视觉，
桌面版查看器）。四页的**共同纪律**与 `P-` 编号总表在 `FYL-DESIGN-10`——**编号在
四页之间是一条全局序列，条搬家不改号**，因为控制器与门禁里有按编号引用裁定的
注释，重编号会让那些引用悄悄指错。重定位之前的设计笔记已冻结归档（见 {ref}`fylite-design-index-archive`）
——归档是逐篇冻结，`FYL-DESIGN` 的编号因此续用而不重置。

本目录是设计书文档集的**唯一路径权威**：文档以 `document_id` 指认、经本表解析路径；
文档集增删或改版时，本表与 `docs/myst.yml` 的 `toc:` 在同一变更中更新。

(fylite-design-index-catalog)=
# 文档目录 (Document Catalog)

| 文档标识 | 主题（简） | 版本 / 状态 |
| :--- | :--- | :--- |
| [`FYL-SDD-01`](FYL-SDD-01.md) | 软件设计描述——五视图；**九组件**（含 DE-COMP-05.1 BYOK LLM 前端、DE-COMP-05.2 LLM 位置纪律、DE-COMP-08 语义层、**DE-COMP-09 数据层**）+ 七逻辑元素（DE-LOG-07 语义单源），DE 全量回接 SRS；组合视图为仓内布局的规范源（分仓后内核 crate 在私有仓、制品不入库） | v0.13 · WD |
| [`FYL-SRS-01`](FYL-SRS-01.md) | 软件需求规格——五任务域 + 横切域 FR（含 FR-TOOL-004「一份命令行规格、三个宿主」）、包络 / 依赖 / 质量 NR、外部接口（命令行 / 单一可执行文件 / 静态站点 / 页面 / 协议面）、追溯矩阵 | v0.5 · WD |
| [`FYL-CONOPS-00`](FYL-CONOPS-00.md) | FyLite 运行概念——轻量验证 / 展示 FYTOK-CONOPS-00 五类应用任务，资源包络四条 + 基准口径与响应预算 + 建设原则六条（v0.4，评估依据 FYL-REPORT-04） | v0.4 · WD |
| [`FYL-DESIGN-09`](FYL-DESIGN-09.md) | **放电设计页**（`pulse_design`）——三个模式：配置（单时刻：工况 · 静态反解 · 击穿）· 设计（整条脉冲 → 逐通道电流与电压波形，播放头选片，已解 / 插值分得清）· 仿真（推进：开关起落、滑块改未来、定态与磁通余量）；共用一份脉冲脚本与三块视图；仿真推进分 0-D / 1.5-D 两档保真度（D-22）。裁定 D-1..D-22，三幅界面概念图、分档响应、缺口与落地状态。**v1.2：分期 P5 已落地（三条入口收成一页），as-built 按实测重写**。★**v1.3 增视觉一节**：D-23 外壳报状态、页体放开关（改口 v1.2 的「模式开关在标题栏」）· D-24 16:9 首屏必须落一处输出（实测首条功能栏在 1265 px）· D-25 每种状态带一个非颜色通道；三个模式各一张 16:9 预览图 + 一张视觉词汇表。★v1.4：D-24 落地（`page_pulse_design` 首处输出 297 px），G-22 按实测更正——模式开关本来就在页体里 | v1.4 · WD |
| [`FYL-DESIGN-10`](FYL-DESIGN-10.md) | **物理建模页**（`model`）——三条栏**全部不含时**：给 χ 求 T（定态输运）· 给电流与位形求 ψ 与度规（边界成栏，P-20）· 给 T 反求 χ（功率平衡反演）。裁定 P-17 · P-19 · P-20 · P-21。★**四页共同的十四条纪律**（P-1..P-8 · P-13 · P-14 · P-15 · P-25 · P-26 · P-27）与 **`P-` 编号总表**也在本篇，另外三页引用不抄。★v1.1 起本篇还持有**四页共用的视觉纪律**：P-25（页面只写外壳以下，外壳报状态、页体放开关）· P-26（16:9 首屏必须落一处输出——实测四页里三页不满足）· P-27（每种状态带一个非颜色通道）；本页自己的 P-28＝同一个 χ / T 在两条栏里方向相反，图元上必须分得开。★v1.2：P-25 / P-26 落地（`page_model` 首处输出 790 px） | v1.2 · WD |
| [`FYL-DESIGN-11`](FYL-DESIGN-11.md) | **视觉设计——桌面版应用**（`fylite-app` 单文件 + 系统浏览器）——管的是**四页共用的外壳**，不是各页的信息架构（V-15）。桌面**没有窗饰可设计**（V-1），能改的只有页面那一层；★**外壳收成一条常驻的两行 header toolbar**（V-11——今天页眉与工具条都 `static`，而页高 2212–6364 px，计算键与它的进度可隔五千像素）；四页在它上面**只差三个槽**（V-12）；**16:9 是桌面的定尺，首屏必须落一处输出**（V-13——实测四页里三页不满足）。预览图是生成物（V-14，五张 16:9、无固定尺寸、`--check` 守）。不该改的是主题三态 · 物理量色的语义绑定 · 字级级数与行长 · 不引 Web Font。★**v0.4：外壳已落地**——`app/pages/page_*.html` 四张新页面带共享外壳，由 `tools/make-page-v2.mjs` 从原页面**生成**、`assets/shell.js` 运行时**搬节点**（不重建任何控件）；实测 16:9 首处输出 297 / 790 / 336 / 335 px（原页面 无 / 1327 / 553 / 无）。**原四页一字未动，留作对照组**。裁定 V-1..V-15，九条不可回退 | v0.4 · WD |
| [`FYL-DESIGN-12`](FYL-DESIGN-12.md) | **实验分析页**（`analysis`）——四条栏：剖面拟合 · 平衡反演 · 时间序列 · 批处理；把「由测量恢复位型」当作统一的正向—推断问题。**磁测量单独约束不住内部剖面，把解定下来的是动理学约束**（P-22）。裁定 P-9 · P-16 · P-22 · P-23。★v0.2 增 **P-29**（不确定度画成什么样取决于它度量了什么：带是带、残差是杆、测量是点而拟合是线）与视觉词汇表；**本页是四页里唯一满足 16:9 首屏判据的**（首处输出 553 px），因此闸子照跑不豁免 | v0.2 · WD |
| [`FYL-DESIGN-13`](FYL-DESIGN-13.md) | **装置数据页**（`data`）——四页里唯一的**工具页**：没有内核、没有 worker、没有功能栏，**它什么也不算**。缺进程时如实降级（P-10）· 抽稀不是归约（P-11）· 守卫两侧各做一遍、两个宿主一组端点（P-12）· 目录说存在从不说这一炮记了（P-18）· 产物是「你看过了什么」（P-24）。★v0.2 增 **P-30**（抽稀必须画得出来：采样点画出、图注写两个数、横拖是回服务器重取）与视觉词汇表；外壳的输入槽在这一页装的是 **mdsip 数据源**，出口槽为空且不留空格。★v0.3：落地（`page_data` 空态图，首处输出 335 px） | v0.3 · WD |
| [`FYL-DESIGN-14`](FYL-DESIGN-14.md) | **数据层**（`rust/fylite_runtime/`，源码公开）——不同数据源 ↔ fyo 文档的读写转换、多源合并、按 JSON-LD 装配。只读 MDSplus / a-file；读写 JSON / g-file / HDF5 / netCDF，各带 fyo 与 IMAS DD 两种布局；IMAS 布局以 imas-python / imas-core 读回逐叶子相同为判据，元数据从 DD 的 `IDSDef.xml` 生成（`nc_metadata.py` 逐条移植）；文件类型看内容识别。裁定 L-1..L-9，缺口 G-1..G-6 | v0.1 · WD |
| [`FYL-DESIGN-15`](FYL-DESIGN-15.md) | **发布形态与统一命令行**——单一可执行文件 `fylite-app`（Rust 宿主的全部命令行：`app` 缺省、`data` / `case` 子命令）· 静态网页（`app/` + 三个 wasm，`tools/build-site.sh`）与动态网页（同一份字节由 `fylite-app` 伺服并答 `/api/*`）· Python 包（承载全部命令，`app` / `data` / `case` 逐字委托）；三个宿主的命令行从同一个 `_cli.json` 建出，只属一个宿主的参数标 `hosts`，浏览器启动参数 `device` / `lang` / `theme` / `page` 定义一次并受门核对。裁定 R-1..R-6、C-1..C-8，缺口 6 条 | v0.1 · WD |
| [`FYL-DESIGN-16`](FYL-DESIGN-16.md) | **可替换内核与四层分工**——内核（本地 `.so` / 页内 wasm / 远端进程 / 另一种实现）以 **fyo 文档门为唯一接口**：code 表声明能力、manifest 声明结果，ABI 号降为本地后端内部物；装配搬进内核，宿主退成计划构造器；`fylite_runtime` 定为 **SpData 的 profile**（重叠语义以 SpData 为准并跑其向量）并持有后端表；前端只写计划只读记录。实测底账：Python 125 / 浏览器 146 个扁平调用 vs 文档门 3 个 code。裁定 K-1..K-7 · **N-1（改名：推荐 `fylite_runtime`）** · D-1..D-4 · H-1..H-3，五条既有裁定改口（含「双宿主」→「多宿主」），分期 P0..P3，缺口 G-1..G-6。★v0.2：**多宿主**（CLI / Python 库 / 网页 / AI 面）与**中间层**改口 · ★v0.3 / v0.4：改名**已执行**，落定 `fylite_runtime`（N-2 记下 N-1 那条被证伪的理由与两层的重叠实测） | v0.4 · WD |

(fylite-design-index-archive)=
# 归档文档 (Archived Documents)

下列重定位（`FYL-CONOPS-00`）之前的设计笔记已冻结归档：正文移至 `docs/archive/`
（不入 MyST 构建与任何 `toc:`），仅存为仓内历史记录；文档站活动页面不引用其内容
（仓外围的机械读取——如按路径核对台账的测试门禁——不在此限）。

| 文档标识 | 主题（简） | 版本 / 状态 | 归档路径 |
| :--- | :--- | :--- | :--- |
| `FYL-DESIGN-08` | Python 端四场景与物理数值收敛 | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-08.md` |
| `FYL-DESIGN-07` | `app/` 应用场景——入口与页面收敛为四条线 | v0.5 · Withdrawn | `docs/archive/FYL-DESIGN-07.md` |
| `FYL-DESIGN-06` | 装置数据面——mdsip 只读客户端 | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-06.md` |
| `FYL-DESIGN-05` | 0D 放电分析线规划 | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-05.md` |
| `FYL-DESIGN-04` | 浏览器端算力边界——能力谱逐项判定 | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-04.md` |
| `FYL-DESIGN-03` | 芯部输运求解器（1.5D 转写） | v0.3 · Withdrawn | `docs/archive/FYL-DESIGN-03.md` |
| `FYL-DESIGN-02` | Rust 输运内核——GEO / NEO / TGLF | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-02.md` |
| `FYL-DESIGN-01` | Rust 平衡内核设计 | v0.1 · Withdrawn | `docs/archive/FYL-DESIGN-01.md` |
