---
document_id: FYL-DESIGN-16
title: "可替换内核与四层分工 (The Replaceable Kernel and the Four-Layer Split)"
shortname: fylite-kernel-contract
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
  change: 'v1.3 新增一章「中间层也进浏览器」（用户裁定：`fylite_runtime` 编成 wasm 由 JS 调用）。四层图
    从此三个宿主同一张；JS 侧 `geqdsk.js`(286，本仓第三份 g-file 实现) / `fyo.js`(221) / `session.js`(241)
    的职责归中间层；扁平树的编解码从预期三份降为两份。wasm 上两个模块由 **JS 接线**（无 dlopen，JS 只搬
    不透明字节）。★★如实改口两处：撤回回调时给的「浏览器没有中间层」理由**作废**（撤回不变，另外两条
    本来就是决定性的）；状态「不能只放中间层」的理由**换成**「持久化要碰宿主设施，wasm 里的中间层一样
    够不着」（结论不变）。G-5 关闭在望。
    v1.2 「状态管理归谁」（用户提问 2026-09-04）：把「管理」拆成五件事——声明与产生归内核、
    携带归中间层、持久化与决定归各宿主。实测持久化**早已分散**（Python engine 的 holder/restart ·
    handles · versioning · ledger/replay；浏览器四处 localStorage 含 handoff.js；远端即调用方），
    而三个「只放某一层」的答案各被一条事实否掉（内核=全局态回来、中间层=浏览器侧根本没有中间层、
    Python engine=另外三个宿主拿不到）。新增 S-5（中间层只搬不改，改了续跑语义就有第二份实现）与
    S-6（状态带写它那个内核的身份，认不出就按名拒绝——照抄 replay 的 allow_version_drift 规矩）。
    结论：机制居中，策略分散。
    v1.1 新增一章「内核的状态」：**无状态，状态在文档里**（S-1..S-4）。实测内核 36 个源文件里
    全局态为零（static mut / thread_local / lazy_static / OnceLock / Mutex 一处都没有），而 evolve_heat
    已经在传二十个成对的槽——那是一个入口自己发明的约定，改为 fyo 文档里一块声明过的 `fylite:state`
    子树，搭在 K-8 的双向树上。持句柄（P-2）否决：远端要会话亲和、wasm 要实例寿命、答案取决于看不见的
    累积、跨后端无法对拍。单步/多步是**计划**的选择，内核须在每个步界能停并交出完整状态（实测状态
    5 数组 × n，n=201 时 7.9 KiB，拷贝不是问题）——**取消因此不需要回调**：切小步数预算，在两次调用
    之间决定。补数据再入 / 断点续跑 / 取消 / 从中间复算四件事共用一个机制。
    v1.0 回调式**整条撤回**（用户裁定，含评估时自留的取消/进度窄口子——门上没有回调）；
    并正面回答它唯一想解决的问题「内核跑到一半要补数据怎么办」：S-1 先问后跑（门加一个只问不算的相，
    即六相的 P-1/P-2，`case describe` / `plan` 已有半条）· S-2 按名拒绝并**带着已建好的树**再入
    （`ERR_MISSING` 在场，`evolve` 的 resume 提成通例——「可写的树」在这里第二次付账）· S-3 不随算例
    变的物理表编进内核（判据是许可不是大小，ADAS21 已有前车）· S-4 宁滥勿缺，否决。共同的线：
    一次调用的输入集在开始时就定死，惰性取数让「这次跑用了什么」只有运行期才知道，而那正是
    whence / replay / 登记册要复算的东西。
    v0.9 两条用户裁定（2026-09-04）：**接受 flat tree 作为交互接口**；**树是双向的**——内核
    不只读也要写，不解析，只处理内存里的树结构。据此把 M-2 改写成「一种布局两个方向」，两侧各一读一写。
    ★实测这不是加活而是删活：今天内核在格式化 TSV 清单、中间层在解析它并按路径字符串建树，双向树把这
    四处一起删掉（净账 内核 +550/−30，中间层 +350/−100）。新增一节评估「中间层给内核一组 entry」的
    回调式：对本机 .so 漂亮，但浏览器那侧宿主是 JS（三个 wasm 制品全是内核，runtime.wasm 无人构建）、
    远端每次取值一次往返、溯源说不清输入集——否决取数用回调，只为取消/进度/注记留一个可空的窄口子。
    T-1 改为读写四份实现同期落地。
    v0.8 新增一章「内核怎样收下一棵树」：把 K-8b 那条工作假设正面摆开（它把「今天没有文档
    模型」当成了「不该有」）。四条路 M-1..M-4 逐条判，推荐 **M-2 已解析的扁平树**——中间层把树摊成
    四段缓冲（节点表 · 名字块 · **8 字节对齐的 f64 载荷** · 整数字符串段），内核借用着走，约 300 行、
    零依赖、wasm 上成立、大数组零拷贝；解析仍不进内核。半结构化的边界：看得见未声明的键，但只从
    已声明的槽取数。分期 T-1..T-4 与旧门并行，不换心脏。
    v0.7 K-8a / K-8b：**实测**今天的路径形会静默取错数——内核当场把路径按 / 切开只留最后一段、
    `pack` 后写者胜，两份文档里同名收尾的路径并成一条（`entry/transport` 三次调用，`rc=0` 无一句话）；
    并定下「完整 fyo 结构体」在 ABI 上的形：每张已声明的表一个类型、槽按声明齐全，走树留在中间层
    （内核无文档模型也无 JSON，给它一个就是把 `document.rs`+`json.rs` 再写一遍）。
    v0.6 K-8（用户裁定 2026-09-04，两句）：**装置信息从 A-Box 读入、由中间层导入、以**整份
    fyo 结构体**进内核；内核不管数据源头，也不收路径**。第二句改动了今天的门（`fylite_rs_fyo` 现收
    「路径, 维数, 数值」三元组），理由是走树的责任该在内核一处而不是每个宿主一份。据此关闭 G-3，并改正目标表里过强的一句——内核「不认识装置」改为
    「不认识数据源头」：它早有 `@fyo-table DEVICE`（34 槽）声明机器的 fyo 路径，也早在算 M / R /
    响应行。这解除了 K-3 对五个「要装置」工具的拦阻。
    v0.4 N-2（用户裁定 2026-09-04，同日）：中间层再改名 `fylite_engine` → `fylite_runtime`。
    N-1 给的理由「与 Python `fylite.engine` 同名正是要的，DE-COMP-03 的职责与此 crate 逐条重合」
    **经逐条核查为假（二比五：serve / mcp / 清单溯源三项该 crate 零处）**——两者是共用一个词的
    两个不同组件（真重叠只有四项，重心互不相交）。错的理由留在正文里记着，不抹掉。
    `engine` 一词让给 Python 那一层（跑运行、记运行，与 SPM-ADR-111 六相用词一致）。
    随之撤销 N-1 那条「`fydoc` 改归 `fylite.engine` 之下」的推论。两次改名都在推送之前完成。
    v0.3 N-1 **已执行**（用户「改名」，2026-09-04）：crate `rust/fylite_runtime/`、制品
    `libfylite_runtime.so`、C 导出 `fylite_runtime_*`（31 个）、环境变量 `FY_RUNTIME_LIB`；命令词
    `fylite data …` 与 `fylite.io.fydoc` 的 Python 入口按裁定不动；内核仓 `rust/build.sh` 的生成
    落点同批改。
    v0.2 两条用户裁定（2026-09-04）：①「宿主」是**多宿主**，不是双宿主——CLI（`fylite` /
    `fylite-app`）、Python 库、网页、AI 面各是一个，全篇改口，并给 `FYL-CONOPS-00` /
    `FYL-SRS-01` 加一条改口行；②`fylite_runtime` 是**中间层**，`data` 这个名字只说了它六项职责里
    的两项——评估五个候选名，裁定 N-1：推荐 `fylite_runtime`（与 Python `fylite.engine` 是同一
    组件的两种语言，DE-COMP-03），备选 `fylite_runtime`；命令词 `fylite data …` 不随之改
    （它说的是数据动词，不是层名）。改名的波及面已量（本仓 303 处 / 31 个 C 导出 / 内核仓 7 文件），
    **本版只裁不改**。
    v0.1 初稿：评估 fylite 与 fylite_kernel 的关系并写成目标架构——内核可替换
    （本地 / 远端、不同版本与实现），统一以 fyo 文档门为唯一接口；`fylite_runtime` 是数据
    集成与转换层并定为 SpData 的一个 profile；GUI / CLI / AI 是其上的前端。以 2026-09-04
    实测为底：Python 宿主 125 个、浏览器 146 个扁平 C 调用，文档门只承载 3 个 code；
    ABI 号硬钉、路径覆盖、无远端。裁定 K-1..K-7（内核契约）、D-1..D-4（数据层）、
    H-1..H-3（前端）；两条既有裁定改口（NR-ENV-004 同核→同契约、「双薄面」→「宿主做计划」）；
    分期 P0..P3；缺口 G-1..G-6。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-kernel-contract

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-16` |
| 文档名称 (Title) | 可替换内核与四层分工 (The Replaceable Kernel and the Four-Layer Split) |
| 短名 / Slug | `fylite-kernel-contract` |
| 版本 (Version) | v1.3 |
| 发布日期 (Date of Issue) | 2026-09-04 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性——规范条款待上提 `FYL-SRS-01` / `FYL-SDD-01`，见 {ref}`fylite-kernel-contract-deltas`) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite / fylite_kernel maintainers · 要接第二个内核实现或远端内核的人 · sp 平台集成方 |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-CONOPS-00`（双宿主、零安装离线可用——「双」在本篇改口为「多」，见 {ref}`fylite-kernel-contract-deltas`）· `FYL-SRS-01` NR-ENV-004（双宿主同核）/ FR-DATA-002..003 · `FYL-SDD-01` DE-COMP-01（计算核）/ DE-COMP-02（装配层：不实现物理）/ DE-COMP-09（数据层）· `FYL-DESIGN-14`（数据层）· `FYL-DESIGN-15`（一个可执行文件、一份命令行规格）· 内核仓 `fyo.rs`（「the kernel computes numbers; the hosts put them into documents」）· `SP-REPORT-15`（fylite 为 sp 协议成员的集成规划）· `SPM-ADR-111`（执行体六相协议）· SpData `01_core` / `02_mapping` / SRS FR-CONF-002（投影不得分叉契约语义） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；改口 `FYL-SRS-01` NR-ENV-004 与 `FYL-SDD-01` DE-COMP-02「双薄面」的两条表述（{ref}`fylite-kernel-contract-deltas`） |
:::

(fylite-kernel-contract-intro)=
# 可替换内核 (The Replaceable Kernel)

〔一句话〕**内核是可替换的一层，fyo 文档门是它唯一的接口；中间层（`fylite_runtime`，原 `fylite_data`，改名见 N-1）负责数据的集成与转换、计划的合成与内核的选择；其上是
多个宿主——CLI、Python 库、网页、AI 面。** 一个内核可以是本地的 `libfylite_kernel.so`、
页内的 wasm、另一台机器上的进程，或另一种实现；每个宿主对它们说同一种话——一份 fyo
计划进，一份 fyo 记录出。

★**「多宿主」，不是「双宿主」**（用户裁定 2026-09-04）。`FYL-CONOPS-00` 起的「双宿主」
指 Python 与浏览器两个**运行时**；按前端数，今天已经是四个：CLI（`fylite` 控制台脚本与
`fylite-app` 可执行文件）、Python 库、网页、AI 面（`serve` / `mcp` / BYOK）。它们的差别只在
**谁写计划**（H-3），所以「几个」不是承重的数——本篇一律写「多宿主」。

〔为什么〕这张图今天**只对一条路成立**。`fylite case` 经数据层的 `fylite_rs_fyo` 一扇门
走的正是「结构进、结构出」；而 Python 宿主与浏览器页面各自绑在几百个扁平 C 导出上，
那份导出面是**这一个实现的形状**，不是契约——换实现即断，换版本靠一个整数硬拒。
本篇把「可替换」从三个 code 推广到全部能力，并把它需要改动的既有裁定逐条点名。

〔与上游的分工〕`SP-REPORT-15` 规划的是 sp **向下**调 fylite（`ExternalBody` /
`RemoteBody`，六相协议）；本篇是 fylite **向下**调内核。两者是同一个模式的两层：fylite
对上是协议成员，对下是内核宿主。远端内核的调用直接共形 `SPM-ADR-111` 的六相，
**不另立协议**。数据层与 SpData 的关系另有一节（{ref}`fylite-kernel-contract-data`）。

(fylite-kernel-contract-asis)=
# 现状：内核被谁、怎么调 (As-Is)

〔已确立〕以下为 2026-09-04 在 `fylite` 公开仓与 `fylite_kernel` 私有仓实测。

:::{table} 三个宿主各走哪扇门。「扁平」＝直接调 `fylite_rs_*` 导出；「文档门」＝结构进结构出。
:name: tbl-fylite-kernel-asis-calls

| 宿主 | 走扁平 C 导出 | 走文档门 |
| :--- | ---: | :--- |
| Python（`scenario/` `fyo.py` `device.py` `engine/` `io/`） | **125** 个不同函数（`kernel.py` 声明 442 个签名） | `K.scenario` 5 个声明入口（`evolve_heat` `profit` `transport` `vstab` `zerod`）；十个能力工具里**只有 `evolve`** 声明了 `kernel_entry` |
| 浏览器（`app/assets/*.js`） | **146** 个不同导出 | `.scenario()` 仅 2 处调用 |
| `fylite case`（经 `fylite_runtime`，`dlopen`） | 0 | `fylite_rs_fyo` 一扇门，**3 个 code**（`evolve` `zerod` `transport`） |
:::

:::{table} 内核今天怎么钉、怎么换。
:name: tbl-fylite-kernel-asis-pin

| 事项 | 实测 |
| :--- | :--- |
| 版本 | `ABI_VERSION = 125`，由内核仓构建生成进 `_abi.py`；装载器见到不符**硬拒** |
| 换内核 | `$FY_KERNEL_LIB`（Python）/ `FYLITE_KERNEL_LIB`（数据层）——都只是**文件路径**；两边各自 `dlopen` 同一个 `.so` |
| 第二种实现 | 无落点：没有后端表，没有「哪个后端完成哪些能力」的声明 |
| 远端 | 没有远端**内核**。存在的两样都是远端 **fylite**：`fylite serve` / `mcp`（`fylite.invoke`、六个 MCP 工具）暴露整个 fylite；`fylite-app` 的 `/api/*` 五个端点（`health` `shot` `tree` `node` `signal` `measurements`）全是 mdsip 取数 |
| 跨宿主一致性 | `engine.crosshost`：比的是**同一内核的两个构建**（原生 vs wasm），只对声明了 `kernel_entry` 的工具运行——今天一个 |
:::

〔已确立〕`fylite_rs_fyo` 已经是可替换内核该有的形：code + 按名的设置 + 输入进
（**今天按 fyo 路径；K-8 改为整份 fyo 结构体**），按 fyo 路径的 manifest（字段与偏移）+ 平铺数据出，缓冲区由内核持有、调用方经
`fylite_rs_free` 释放，装成文档是数据层 `case.rs` 的事。内核仓 `fyo.rs` 抬头那句
「the kernel computes numbers; the hosts put them into documents」写的就是这个分工——
它只是尚未成为**唯一**的门。

(fylite-kernel-contract-target)=
# 目标架构：四层 (Target: Four Layers)

```{mermaid}
flowchart TB
  subgraph F[多宿主 Hosts]
    GUI[网页 app/]
    CLI[CLI：fylite · fylite-app]
    PY[Python 库]
    AI[AI 面：serve / mcp · BYOK LLM]
  end
  subgraph D[中间层 fylite_runtime（原 fylite_data，N-1）— SpData profile]
    ASM[装配 assemble / fetch]
    FMT[格式 g-file · JSON-LD · HDF5 · netCDF · mdsip]
    CASE[case.rs：计划 → 门 → 记录]
  end
  subgraph K[内核 Kernel — 可替换]
    LOCAL[本地 libfylite_kernel.so]
    WASM[页内 wasm]
    REMOTE[远端进程 · JSON-RPC 六相]
    OTHER[另一种实现]
  end
  F -->|fyo 计划 fyo:ScenarioSpecification| D
  D -->|一扇门：code + 设置 + 按路径输入| K
  K -->|manifest + 平铺数据| D
  D -->|fyo 记录 spo:ComputationRecord| F
```

〔工作假设〕四层各自的**唯一职责**与**禁止事项**：

| 层 | 职责 | 禁止 |
| :--- | :--- | :--- |
| 宿主（多个） | 把用户意图写成一份 fyo 计划；把一份 fyo 记录呈现出来 | 不做装配算术，不直接触碰任何内核符号 |
| 中间层 | 计划的合成与绑定（多份计划、`--set` / `--bind`、按路径取输入）；结果装成文档；格式与来源的读写与转换；内核的**发现与选择**；Rust 宿主的命令行与 `app/` 的伺服 | 不算物理；不写 MDSplus |
| 内核 | 完成一个 code：从结构到结构（**装置几何按 fyo 路径作为输入进来**，见 K-8） | 不读文件、不开网络、**不认识数据源头** |
| 内核契约 | code 表 + 按路径的 manifest；每个后端自报「完成哪些 code、产哪些路径、什么单位」 | 不再有宿主可见的 ABI 号 |

(fylite-kernel-contract-rulings)=
# 裁定 (Rulings)

## 内核契约 K-1..K-7 (The kernel contract)

**K-1 文档门是唯一的内核接口。** 宿主（Python、浏览器、`fylite-app`）**只**经「一份计划
进、一份记录出」调用内核。`c_api.rs` 的 442 个导出降为**本地后端的实现细节**：
`fylite.kernel` 与 `app/assets/fylite.js` 里那 125 / 146 个调用点，或者搬进内核成为
code 的一部分，或者留下但只被本地后端自己用。判据：`scenario/` 与页面 JS 里不再出现
`fylite_rs_*` 符号名（现有 `test_no_bare_kernel_aliases.py` 的思路推广一层）。

**K-2 code 表是能力的声明，manifest 是结果的声明。** 一个内核后端自报它完成哪些 code、
每个 code 产哪些 fyo 路径、什么单位——`fylite case describe` 今天打印的就是这张表。
宿主按表选后端、按 manifest 读结果；**不再按 ABI 号**判断能不能调。`ABI_VERSION`
保留给本地 `.so` 的装载器自检（它守的是 C 签名，那是本地后端内部的事）。

**K-3 装配搬进内核，宿主退成计划构造器。** 今天 Python 与页面各持一份 Miller 度规、
抛物剖面、相位表的装配算术（`FYL-DESIGN-15` 之前已量过：同一闭式三份拼法）。
这些成为 code 的一部分（`[assembled]` 那一类，`code/evolve` 已是先例）。这与用户
2026-09-03 的裁定「kernel 中已经有的功能不应再 python 侧重复实现」是同一条的延长，
也是 `FYL-SDD-01` DE-COMP-02「本层不实现物理与数值」的落实。

**K-4 三种后端一张表。** 本地 `.so`、页内 wasm、远端进程登记在同一张后端表里，
每条记：怎么到达（路径 / 已加载的模块 / 地址）、code 表、manifest 能力、环境指纹。
选择规则显式（`--kernel <名或地址>`、环境变量、缺省本地），**不静默回退**：要的后端不在
场就说不在场，不换一个能力更少的顶上。

**K-8 装置：A-Box → 中间层 → **整份 fyo 结构体**进内核；内核不问来路。** 〔已确立〕
用户裁定（2026-09-04，两句）：*device 信息从 abox 读入，由 runtime 导入，kernel 不需要管
数据源头*；*kernel 不接受 path，只接受完整的 fyo 结构体*。

**两件事，分开说。**

**其一，来路归中间层。** 这条关掉 G-3。内核 `fyo.rs` 里早有一张 `@fyo-table DEVICE`
（`fyo:DeviceDescription`，34 个槽）声明机器的形——线圈矩形
（`pf_active/coil/element/geometry/rectangle/{r,z,width,height}`）、匝数
（`turns_with_sign`）、通道图（`fylite:channel_map`）、真空室单元与其电阻率
（`wall/description_2d/vessel/…/fylite:resistivity_uohm_m`）、限制器轮廓。内核认识**这个形**，
不认识 `$FYLITE_DEVICE_DIR`、`machine.yaml`、epoch 与提供者。

| 谁 | 做什么 |
| :--- | :--- |
| A-Box（fydoc / fydata） | 装置的真源：epoch × 提供者 × 绑定 |
| 中间层 `fylite_runtime` | 读 A-Box（`assembly.rs` / `from_manifest` 已在做），装成一份完整的 `fyo:DeviceDescription`，随计划交给内核 |
| 内核 | 收下那份结构体，算 M / R / 响应行——它**已经**这么算（`mutual_matrix_self` · `mutual_matrix_cross` · `resistances` · `channel_fold` · `plasma_filaments` · `vertical_stiffness`） |

**其二，交付单位是文档，不是叶子地址。** ★★这一条**改动了今天的门**：`fylite_rs_fyo` 现在
收的是「设置按名 + 输入**按 fyo 路径**」——一组 `(路径, 维数, 数值)` 三元组，由调用方逐条摊平。
按本裁定，它应当收**整份 fyo 结构体**（`fyo:equilibrium`、`fyo:DeviceDescription`、
`fyo:core_profiles` …），内核自己在结构里走。

理由不是美观，是**谁承担走树的责任**。路径形把「`time_slice` 是结构数组、要落到第 0 个」
这类知识留在调用方，于是每多一个宿主就多一份走法——本仓已经为此立过一条生成的
`AOS_PATHS` 声明，正因为两个走树的实现各写过一遍。文档形把它收进内核一处：调用方交出
一份合法文档，内核按自己的表取自己要的槽，**取不到就按名拒绝**，而不是收下一个少了几条
路径的袋子照算。

★这也让 K-2 更整齐：进是文档，出是 manifest + 平铺数据，**两头同一种东西**。
★★不影响 K-1：门仍然只有一扇。变的是那扇门的入参形状，不是门的数目。

(fylite-kernel-contract-path-defect)=
**K-8a 今天的路径形不只是笨，它会静默取错数（实测）。** 〔已确立〕2026-09-04 直接经
`fylite_rs_fyo` 实测。内核收下路径之后**当场把路径丢掉**——`case.rs`：

```rust
for (k, v) in req.inputs {
    let key = k.rsplit('/').next().unwrap_or(k);   // 只留最后一段
    if iblock.iter().any(|r| r[0] == key) { iv.push((key, v)); }
```

而 `pack` 对重复的 key **后写者胜**，不报错、不留注记。于是两份**不同文档**里同名收尾的
路径会并成一条。拿 `entry/transport` 量：

| 绑了什么 | 答案 `y[-3:]` |
| :--- | :--- |
| 只绑 `equilibrium/profiles_1d/grid/rho` | 2548.98 · 1426.53 · 100 |
| 只绑 `core_profiles/profiles_1d/grid/rho` | 9895.92 · 5406.12 · 100 |
| **两条都绑** | **9895.92 · 5406.12 · 100**（后者胜，`rc=0`，无一句话） |

两条路径写的是**两个文档的两个量**，内核把它们当成同一个 `rho`。声明里 `rho` 被三个入口
declared、`vprime` 被两个——同名收尾不是假想。

★所以「按路径」这个说法本身就是虚的：门**看起来**按路径，**实际上**按叶子名，而两者不一致
时没有任何一侧会说话。K-8 的文档形正是关掉这一类：一份完整的结构体交进来，内核按自己的表
取自己的槽，**缺一槽按名拒绝**，两份文档各是各的，不再有一个共享的名字空间可撞。

(fylite-kernel-contract-struct-form)=
**K-8b 「完整的 fyo 结构体」在 ABI 上是什么。** 〔工作假设〕内核**没有文档模型，也没有
JSON 解析器**（36 个源文件，依赖表为空，全是数值与表）。给它一个，就是把中间层的
`document.rs`（710 行）与 `json.rs`（488 行）在内核里再写一遍——正是本篇要消掉的那类第二
实现。所以「结构体」按字面取：**每张已声明的表（`EQUILIBRIUM` / `DEVICE` /
`CORE_PROFILES` …）一个类型，槽按声明齐全**，ABI 上按表交付而不是按调用方挑出来的一袋路径。
走树仍然只有一处，只是那一处在**中间层**（它已经有 `document.rs` / `json.rs` / `fyodoc.rs`），
而内核收到的是走完之后的完整结构。

★这与 K-8 的理由一致：责任要么整个在内核，要么整个在中间层，**不能像今天这样一半一半**
——调用方走树、内核丢路径、谁都不负责名字。

★★**K-8b 是〔工作假设〕，而且被追问了。** 它的推理是「内核没有文档模型 ⇒ 只能收定型记录」，
把「今天没有」当成了「不该有」。下一节把这个问题正面摆开：内核要收下一棵树，需要什么。

★**解除了 K-3 的第一道拦阻**：`discharge` / `breakdown` / `feasible` / `vstab` /
`reconstruction` 五个工具此前被判为「要装置、故搬不进内核」，按本条它们只是**多收一份
装置文档**，与 `evolve` 收度规、`zerod` 收相位表同类。

**K-5 远端内核共形六相协议，不另立协议。** 远端调用的生命周期就是 `SPM-ADR-111`
的 P-1..P-6（interpret_inputs → provision → stage → execute → interpret_outputs + harvest →
dispose）；载荷就是那份计划与那份记录。`fylite serve` 的 JSON-RPC envelope 复用为
`compute.` 方法族还是另立，与 `SP-REPORT-15` T-0.4 一并裁定（本篇不预设）。

**K-6 跨后端一致性是登记册的一类记录。** `engine.crosshost` 今天比「同一内核的两个
构建」；推广后比「同一 code 在两个后端」。判据形式**不变**：count / flag 逐位哈希、
real 容差带、noise 只判小、差异必须由环境指纹解释——`fyo:ComparisonRecord` 与公开
V&V 登记册已经承载这种记录，不新开体例。

**K-7 一个后端一个环境指纹，记录里必须有。** 记录的 `environment` 写明是哪个后端
（本地 / wasm / 远端地址）、哪个版本、什么指纹，`whence` 追得回去。两个后端给出不同的
数是**可能的、合法的**，前提是记录里说得清是谁给的。

## 中间层 N-1 · N-2 · D-1..D-4 (The middle layer: its name, and SpData)

(fylite-kernel-contract-naming)=
**N-1 这一层叫什么。** 〔已确立〕用户裁定（2026-09-04）：这一层是**中间层**，`data`
只说了它六项职责里的两项。按 {numref}`tbl-fylite-kernel-asis-calls` 与 `FYL-DESIGN-14` /
`-15` 的 as-built，这一层今天做的是：①格式读写与转换；②多源装配；③计划合成与绑定 →
门 → 记录（`case.rs`）；④内核的加载与选择（`kernel.rs`，K-4 后是后端表）；⑤Rust 宿主的
全部命令行（`src/cli/`）；⑥内嵌并伺服 `app/`。①②是数据，③④⑤⑥不是。

:::{table} 候选名，按「名字说的是不是这一层做的事」判。
:name: tbl-fylite-kernel-naming

| 候选 | 说到了 | 没说到 / 冲突 | 判 |
| :--- | :--- | :--- | :--- |
| `fylite_data`（原名） | ①② | ③④⑤⑥；读者会以为它只是 I/O | 否 |
| `fylite_io` | ① | 比原名更窄 | 否 |
| `fylite_core` | — | 「核」是内核的名字；两个 core 必混 | 否 |
| `fylite_host` | ③④⑤⑥ | 「宿主」已由用户定为前端那一层的名字（多宿主，H-3）；一个 crate 叫 host 就把 Python 与网页排除在宿主之外 | 否 |
| `fylite_fyo` | ①②③ | ④⑤⑥；与本体仓 `fyo` 和 Python `fylite.fyo`（文档层）同名 | 否 |
| `fylite_engine` | ③④⑤⑥ | **与 Python 包 `fylite.engine` 撞词**——见 N-2 | 用过一次，已撤 |
| **`fylite_runtime`** | ③④⑤⑥ + ①②作为它的 I/O | 「运行时」在 wasm 语境里另有所指（页内 wasm 的宿主运行时是浏览器）——但那是**浏览器的**运行时，不是 fylite 的组件名，实测无第二个读法 | **裁定** |
:::

(fylite-kernel-contract-naming-2)=
**N-2 为什么不是 `engine`。** ★★〔已确立〕2026-09-04 同日两次改名：先
`fylite_data` → `fylite_engine`，当天又 → `fylite_runtime`。**第一次的理由是错的，这里
把它记下来而不是抹掉**——它是一句可证伪的话，被证伪了。

那句话是：「与 Python `fylite.engine` 同名正是要的——`FYL-SDD-01` DE-COMP-03『机械核』
定义的职责（CLI / 服务 / 清单 / 溯源 / 原生库装载）与此 crate **逐条重合**」。逐条查过，
**二比五**：

| DE-COMP-03 的职责 | 这个 crate |
| :--- | :--- |
| 命令行 | ✓（`src/cli/`） |
| `serve`（JSON-RPC） | ✗ 零处 |
| `mcp` | ✗ 零处 |
| 制品清单 / 溯源 | ✗（`manifest` 的命中是 fydata 的 `machine.yaml`；`prov:` 是写记录时的输出键） |
| 原生库装载 | ✓（`kernel.rs`） |

所以两者不是「同一组件的两种语言」，是**共用一个词的两个不同组件**。逐模块量过，
二十项职责里真正重叠的只有四项：命令行解析（**有意的两份**，`FYL-DESIGN-15` 一份规格
三个宿主）· 内核装载（两个装载器取同一个 `.so`）· 计划→内核→记录（K-3 / P1 要收的那条）·
g-file ↔ `fyo:equilibrium`（`eqdsk_fyo.rs` 抬头已声明，且由 `test_fyo_interface.py` 对拍）。
重心则完全不相交：只在 Rust 的约 9 500 行（mdsip · mdsbind · yaml · netcdf · document ·
assembly · hdf5 · ids_meta · tensor · 桌面服务面），只在 Python 的约 6 200 行（六相执行体 ·
`serve` / MCP · 算例报告 · 清单 · 溯源 · 重放 · 底账 · 版本 · 别名 · 跨宿主）。

〔已确立〕**裁定：`fylite_runtime`**（crate `rust/fylite_runtime/`，制品
`libfylite_runtime.so`，C 导出前缀 `fylite_runtime_*`，环境变量 `FY_RUNTIME_LIB`）——
**已于 2026-09-04 执行**（两个仓各一次机械提交）。`engine` 这个词**留给 Python 那一层**：
它跑运行、记运行，与 `SPM-ADR-111` 六相执行体的用词一致。三件事随之说清：

- **命令词 `fylite data …` 不改。** 它说的是七个数据动词（`info` / `dump` / `convert` /
  `merge` / `assemble` / `fetch` / `tables`），不是层名；`fylite case …` 与 `fylite app`
  本来就是同一个 crate 的另外两组动词。用户指南与参考里的命令行一字不动。
- **`fylite.io.fydoc` 留在 `fylite.io` 下。** 它是这层 `.so` 的 ctypes 面。★N-1 那一版曾
  写「改名后归 `fylite.engine` 之下」——那是顺着错理由推的，随 N-2 一并作废：把中间层的
  ctypes 面塞进另一个组件的包里，正是这次要避免的混淆。
- **波及面两次都已量。** 第一次（`data` → `engine`）：本仓 303 处 / 67 文件、C 导出 31 个、
  内核仓 7 文件、fydoc 2 文件。第二次（`engine` → `runtime`）：本仓 53 文件、同一批 31 个
  C 导出、内核仓同 5 份文档与 `rust/build.sh` 的生成落点。两次都是 `git mv` + 全仓替换 +
  重建两个制品，跨两个仓、动 C ABI 名，各自单独一次提交。

★**窗口**：两次改名都在**未推送**之前完成，所以对外没有一个版本用过中间的那个名字。

(fylite-kernel-contract-data)=
〔已确立〕对照实测（2026-09-04）：

| | SpData | `fylite_runtime` |
| :--- | :--- | :--- |
| 定位 | 规范集：HTree 逻辑树、标识符语法、`$op` 变换、查询 / 修补、PROV、mapping 文档、backend profile | 实现：读写器 + mdsip 只读客户端 + 装配 |
| Rust | `rust/src/lib.rs` 自述 **planned**（`axes.rs` + 生成物） | 83 个单元测试的完整数据面，两个制品 |
| Python | 三个插件（`file_hdf5` `file_netcdf` `mdsplus`） | 经 ctypes 取同一份 `.so` |
| 装配 | mapping 文档：逻辑目标路径 → 后端源 | `fylite:Assembly/1`：`$source` / `$link` / `merge` / `select`，出处块 `fylite:assembly` |
| `fylite_runtime` 没有的 | | `$op` 变换、查询 / 修补语法、惰性指针与分级载荷、标识符通配、conformance 向量 |

**D-1 中间层是 SpData 的一个 profile，不是它的简化重写。** 事实上它是生态里
最完整的 Rust 数据面，而 SpData 的 Rust 投影还是空壳。SpData SRS `FR-CONF-002`
规定任何投影**不得分叉契约语义**；`fylite_runtime` 的 `$link` 分解、合并键、时间开窗
今天都是自己定的。定为 profile 的含义：凡与 SpData 重叠的语义（树、路径、mapping、
PROV）**以 SpData 为准**并跑它的 conformance 向量；不重叠的（mdsip 编解码、IMAS
两种布局、g-file）是 profile 自己的扩展，写明「profile 不含」的那些不算缺陷。

**D-2 中间层是内核的发现者与选择者。** K-4 的后端表住在数据层（`case.rs` / `kernel.rs`
今天已经在 `dlopen` 内核并读它的 code 表）；Python 的 `fylite.kernel` 与页面的加载器
退为**本地后端**的两个驱动。理由与 `FYL-DESIGN-14` L-1 同源：一棵中立的树居中，
N 个后端是 N 条驱动而不是 N 份宿主代码。

**D-3 计划的合成只在一处。** 多份计划按序合成、`--set` / `--bind` 后叠、按 fyo 路径
取绑定输入——`case.rs` 已做；Python `engine.cases.plan` 与页面的会话文档合成是
同一件事的第二、第三份，收敛到数据层。

**D-4 中间层不算物理，也不写 MDSplus。** 与 `FYL-DESIGN-14` L-8 同；本篇只是重申它在
四层里的位置，防止「装配搬进内核」（K-3）被误读成「装配搬进中间层」——度规与剖面是
物理，归内核；合成与绑定是文档操作，归中间层。

## 多宿主 H-1..H-3 (Hosts)

**H-1 宿主只写计划、只读记录。** 页面控件的每一次改动产生的是计划里的一个字段，
「计算」键送出一份计划；1.5-D 栏读 g-file、0-D 工况跨页交接（`FYL-DESIGN-09` / `-10`）
都成为「计划里的一个绑定」。页面里的装配算术随 K-3 撤出。

**H-2 浏览器的本地后端是页内 wasm，远端后端是 `fylite-app` 的一个端点。** 因为门只有
一扇，`/api/case` 是**一个**端点，不是一族；它与今天的五个 mdsip 端点同守回环、同做
两侧守卫（`FYL-DESIGN-13` P-12）。静态站点没有进程，只有本地后端；这与「静态即无
服务端组件」（`FYL-DESIGN-15` R-3）一致。

**H-3 宿主是多个，数目不承重。** CLI（`fylite` / `fylite-app`）、Python 库、网页、AI 面
（`serve` / `mcp` / BYOK）今天四个，差别只在**谁写计划**；再来一个（notebook、另一种
GUI、另一台机器上的代理）不改本篇任何一条；它们共享一份计划的词汇
（`fyo:ScenarioSpecification`）与一份记录的词汇（`spo:ComputationRecord`），
不各有一份。

(fylite-kernel-contract-tree)=
# 内核怎样收下一棵树 (How the Kernel Takes a Tree)

〔一句话〕**内核与中间层之间传一棵扁平树，双向、可读可写、不解析。**〔已确立〕用户裁定
（2026-09-04）：*接受 flat tree，作为交互接口*；*内核不仅读还要写，但不解析，只处理内存中的
树结构*。树是一段**扁平、索引相连**的内存布局——它本身就是「内存里的树」，只是不用指针，
所以能跨过 C ABI 而不必序列化成文本。

★★**这不是给两边加活，是把两边现有的文本活删掉。** 实测今天的往返：内核把结果格式化成一段
**TSV 清单**（`code` / `dim` / `field<TAB>ids<TAB>path<TAB>units<TAB>offset<TAB>len<TAB>dims`）
外加一条平铺 f64；中间层**解析那段 TSV**（`case.rs` 里 `cells[4].parse()`），再按其中的
**路径字符串**把树建出来（`documents()`）。**内核今天在格式化文本，中间层今天在解析文本**
——两边都在做本该没有的事，而 K-8a 那个静默撞名，正是从「把路径当字符串传」来的。

## 约束（先量，再选）

〔已确立〕2026-09-04 实测：

| 约束 | 事实 |
| :--- | :--- |
| 依赖 | 内核 `Cargo.toml` 的依赖表只有 `rayon`（可选）。**实质零依赖** |
| 目标 | `cdylib` + `rlib`，同一份 `c_api.rs` 也编 `wasm32-unknown-unknown`。**任何方案必须 wasm 上成立** |
| 载荷形状 | fyo 文档的重量在**大 f64 数组**上（剖面、ψ 面、响应行），结构本身很小 |
| 真实深度 | 装置文档最深 **11** 层，`pf_active/coil` 14 个元素——**结构数组是常态，不是边角** |
| 中间层已有 | `document.rs`（710）· `json.rs`（488）· `yaml.rs`（793）· `fyodoc.rs`（460）——树、解析、语义都在那边 |

中间层的树是 `Node`：`Null` · `Bool` · `Int` · `Float` · `Str` · `Array{shape, F64|I64|Str}` ·
`List` · `Map`（插入有序）。**要跨过去的就是这个类型。**

## 四种做法 (Four mechanisms)

:::{table} 内核收下层次化数据的四条路。
:name: tbl-fylite-kernel-tree-options

| | 做法 | 内核新增 | 能收半结构化吗 | 判 |
| :--- | :--- | :--- | :--- | :--- |
| **M-1** | **定型完整记录**：每张 `@fyo-table` 生成一个 struct，ABI 按表交付、槽按声明齐全 | ~0（生成物） | ✗ 只认已声明的槽 | K-8b 原案；**是 M-2 的子集**，可作第一步 |
| **M-2** | **已解析的扁平树**：中间层把 `Node` 摊成四段缓冲（节点表 · 名字块 · f64 载荷 · 整数/字符串），内核借用着走 | **~300 行**，零依赖 | ✓ | **推荐** |
| **M-3** | 内核自带 JSON / CBOR 解析器 | ~500–900 行 | ✓ | 否——把 `json.rs` 在内核里再写一遍，正是本篇要消的那类；且文本浮点往返、wasm 变大，而内核**本来就不许读文件**，多出来的能力无处可用 |
| **M-4** | 回调式：内核按需回调宿主取节点 | ~100 行 | ✓ | 否——每次取值一次 FFI、重入风险、wasm 上别扭，且打破「一次调用一个答案」 |
:::

## M-2 的形：一种布局，两个方向 (One layout, both directions)

**四段缓冲，索引相连，先序排列。**

1. **节点表** `[Node32]`，定长记录：种类 · 名字（偏移 + 长度）· 第一个孩子 · 下一个兄弟 ·
   载荷偏移与长度 · 形状（偏移 + 维数）。**用下标相连，不用指针**——这正是它既是「内存里的
   树」又能跨 ABI 的原因。
2. **名字块** UTF-8 字节，按偏移 + 长度取。
3. **f64 载荷** —— **8 字节对齐、独立成段**。数值内核要的是 `&[f64]` **零拷贝**；面向字节的
   格式（JSON / CBOR）在这里恰恰最不合适。
4. **整数 / 字符串载荷** 各一段。

**两侧各有一读一写**，因为传递是双向的：

| | 读 (decode) | 写 (encode) |
| :--- | :--- | :--- |
| 中间层 | 收内核交回的树 → 自己的 `Node` | 自己的 `Node` → 四段缓冲，随计划交出 |
| 内核 | 借用四段缓冲，走树取**已声明的槽** | 建树写**已声明的输出**，经既有的 `fylite_rs_alloc` 交回 |

★**写这一侧内核已经有了半条**：它今天就在 `fylite_rs_alloc` / `hand_out` 里分配并交出缓冲、
中间层负责释放。所有权那一半不必发明——交出去的东西从「TSV + 平铺数组」换成「四段树」而已。

内核侧两样东西：

* **阅读器** `Doc<'a>`：借用四段，给 `root()` · `child(name)` · `at(i)`（结构数组下标）·
  `f64s()` · `str()` · `need(路径, 说明)`（**取不到按名拒绝**）。不分配、不解析。
* **构建器** `Tree`：`map()` · `field(name, …)` · `array(name, shape, &[f64])` · `list()`，
  按已声明的输出路径落位——`time_slice/0/profiles_1d/psi` 这类要**沿路补出中间的映射与结构
  数组**（约一百行）。★这条正是 K-8a 的反面：路径不再当字符串交给别人去猜，**内核自己按
  自己的表把它落成树**。
* 〔工作假设〕**读改写**（收一份文档、添几个量、原样交回）由构建器从已解码的树**播种**支持
  ——`evolve` 的 resume 那类会要它。第一版可以不做，但格式不能挡住它。

**进门先校验一次，O(n)，之后不再信任缓冲**：偏移全在界内 · 先序单调（无环）· f64 段 8 字节
对齐 · 名字块是合法 UTF-8。**畸形缓冲当场拒绝**。

★**「半结构化」的边界**：内核**看得见**未声明的键。看得见不等于可以用——**只从已声明的槽取
数**，未声明的至多**记一句注记**。否则「声明或拒绝」这条就散了。

## 它删掉什么 (What it removes)

:::{table} 双向树取代的四处——两侧各两处，全是文本活。
:name: tbl-fylite-kernel-tree-removes

| 在哪 | 今天做什么 | 之后 |
| :--- | :--- | :--- |
| 内核 `c_api.rs::fyo_manifest` | 把结果格式化成 TSV 清单（约 30 行） | 删；改为建树 |
| 中间层 `case.rs::Outcome::parse` | 解析那段 TSV，`parse()` 出偏移与长度 | 删 |
| 中间层 `case.rs::documents` | 按 `field` 行里的**路径字符串**把树建出来 | 删；树是收到的 |
| 内核 `case.rs` 那句按 `/` 切尾 | 丢掉入参路径、重复键后写者胜（K-8a） | 删；两份文档是两个根，撞不上 |

**净账**：内核 +约 550 行（阅读器 ~300 + 构建器 ~250，零依赖），−30；中间层 +约 350
（编码器 ~200 + 解码器 ~150），−100。**两边都不再有文本格式化或文本解析**，而 fyo 树的形
从此**只有内核一处**在按表落位。

(fylite-kernel-contract-callback)=
## 回调式：已撤回 (The callback vtable: withdrawn)

〔已确立〕2026-09-04 同日提出、评估、**由用户撤回**。留这一节，是因为撤回的理由本身是判据。

提案是：中间层向内核提供一组 entry（函数指针），内核在运行时回调过去读写中间层活着的那棵树。
对**本机 `.so`** 那一档它很漂亮——内核只要一张约百行的 vtable，树的实现真的只有一份。三条
把它否掉：

| | |
| :--- | :--- |
| ~~浏览器~~ | ~~那侧宿主是 JavaScript，回调就得用 JS 把整套树 API 再实现一遍~~ ★★**这一条已作废**（用户裁定 2026-09-04：`fylite_runtime` 进 wasm、由 JS 调用，见 {ref}`fylite-kernel-contract-runtime-wasm`）。中间层到了浏览器，那侧的树也是 Rust。**如实记下：撤回回调时我给的三条理由，这一条不再成立。** |
| **远端内核**（K-5） | 每次取值一次网络往返 |
| **溯源**（K-7） | 输入集变成「内核当时恰好问了什么」，运行期才定，记录说不清、算例不可复算 |

★决定性的本来就是后两条，不是浏览器那条：回调式买到「一份实现」，卖掉的是**远端后端**与
**可复算**，而 K-4 明写三种后端一张表、K-7 要记录说得清什么跑了。**浏览器那条作废之后这两条
仍各自足够**，所以撤回不动摇——但一条理由塌了就该说它塌了，不该留在表里充数。
★★用户裁定**整条撤回**，包括评估时给自己留的那个「只做取消 / 进度 / 注记」的窄口子——
**门上没有回调，一个也没有**；取消由 S-3 的步数预算承担。

(fylite-kernel-contract-more-data)=
## 内核跑到一半要补数据，怎么办 (When the kernel needs more data mid-run)

〔已确立〕用户提问（2026-09-04）。回调撤回之后这个问题必须正面答，因为它是回调唯一真正想
解决的事。**四条路，按优先次序，不含惰性取数。**

**S-1 先问后跑：把「要什么」变成可以事先算出来的。**〔推荐，首选〕门加一个**只问不算**的
相：给定 code 与设置，内核回答**它将要什么**（哪些文档、哪些槽、哪些维数），中间层据此绑定，
再跑。★这不是新机制：`fylite case describe` 已经在打印 code 表与逐入口的声明块，
`fylite case plan` 已经**停在内核之前**打印合成好的计划——缺的只是让「要什么」随**设置**变化
（`imp_id = 74` 就得绑钨的表）。★★它也正是 `SPM-ADR-111` 六相里的 P-1 `interpret_inputs` /
P-2 `provision`：K-5 已经要求远端内核共形六相，**本机内核照做只是让三个后端说同一套话**。

**S-2 按名拒绝，补齐再入。**〔S-1 够不着时的兜底〕需求真的与数据有关、事先算不出来时
（组分算完才知道要哪条辐射曲线），内核**拒绝并说全**：把这一轮发现的**全部**缺口一次列出，
不要一次一条地来回。机制已经在场——`ERR_MISSING` 与 `refuse(...)` 就是干这个的，今天的话术
是「the case sets no `x` … and this code has no default for it」。

★★**「可写的树」恰恰是让这条便宜的东西。** 再入的代价是重算，除非能续跑；而续跑要一份
**状态**，状态就是内核已经建好的那棵树。所以拒绝时一并交回**已算出的部分 + 那棵树**，
补齐后带着它再入。`evolve` 早有 `resume` 那一族参数（`resume` / `t_start` / `psi_prev` /
`sigma_prev` / `exch_prev` / `saw_elapsed_in`），这条只是把「续跑」从一个 entry 的特例
提成门的通例。★于是用户那条「不仅读还要写」的裁定，在这里第二次付账。

**S-3 是常数就编进去。**〔物理表〕辐射系数、FLR 表、台基表这类**不随算例变**的东西，本就
该随内核走——今天已有四份（`edge_tables.rs` · `closure_tables.rs` · `pedestal_tables.rs` ·
`flr_tables.rs`）。★但**许可先于方便**：本仓已经量到过一份表（ADAS21）体量最小却是四份里
唯一许可不过的（`FYDOC-REPORT-17`），所以这条的判据是许可，不是大小。

**S-4 宁滥勿缺。**〔否决〕中间层把「可能要的」一股脑绑上。大数组上浪费，且「可能要的」
同样事先不知道——它没有解决问题，只是把问题挪到中间层。

:::{table} 四条路，以及为什么次序是这个。
:name: tbl-fylite-kernel-more-data

| | 做法 | 何时用 | 三个后端都成立吗 | 溯源 |
| :--- | :--- | :--- | :--- | :--- |
| **S-1** | 先问后跑（P-1 / P-2） | 需求可由设置算出——**多数情形** | ✓ | 输入集显式，一次定 |
| **S-2** | 按名拒绝 + 带树再入 | 需求与数据有关 | ✓ | 两次调用都进记录，各自输入集显式 |
| **S-3** | 编进内核 | 不随算例变的物理表 | ✓ | 随制品的指纹 |
| **S-4** | 宁滥勿缺 | — | ✓ | 输入集虚胖 |
| ~~回调~~ | ~~运行时回调取数~~ | ~~—~~ | **✗** | **✗** | 

★**共同的那条线**：无论走哪一条，**一次调用的输入集在调用开始时就已经定死**。惰性取数被
否掉的根本原因不是慢，是它让「这次跑用了什么」变成一个只有运行期才知道的答案——而那正是
`whence` / `replay` / 登记册要复算的东西。
:::

## 分期 (Phasing)

★现在这扇门**是能用的**，所以新形与旧形并行落地，不是换心脏。

| 期 | 做什么 | 判据 |
| :--- | :--- | :--- |
| **T-1** | 定格式；**四份实现一起落**（中间层 编码 + 解码、内核 阅读器 + 构建器）；**旧门一字不动** | 往返闸：中间层编码 → 内核走一遍 → 内核**建树交回** → 中间层解码 → 与源文档逐叶子比。★读写必须同期，否则这道闸只验得了一半 |
| **T-2** | 门加一条收文档的路（新符号或版本位），**先只接一个 code**（`transport` 最小） | 同一算例两条门给**逐位相同**的数 |
| **T-3** | 其余 code 逐个搬过来；K-8a 那类撞名**按构造不可能**（两份文档是两个根） | 每搬一个，两门对拍一次 |
| **T-4** | 删掉路径形、那句按 `/` 切尾、内核的 TSV 格式化与中间层的 TSV 解析 | 门只剩一种形状，**两个方向都是树** |

**代价**：见上「它删掉什么」的净账。Python 侧**先不动**（它经中间层）。ABI 号加一。

**不变**：内核仍不读文件、不开网络、不认识数据源头、不认识任何序列化格式。★它**会分配**
——为交回的那棵树，用它今天就在用的那条 `fylite_rs_alloc`。

(fylite-kernel-contract-state)=
# 内核的状态：无状态，状态在文档里 (Kernel State: Stateless, State Travels)

〔一句话〕**内核不持有状态；状态是文档里一棵声明过的子树，随计划进、随记录出。**
「单步还是多步」不是内核的选择——**是计划的选择**，而内核**必须在每个步界上都能停下并交出
完整状态**。

## 先量 (Measured, 2026-09-04)

| 事实 | 实测 |
| :--- | :--- |
| 内核的全局态 | **零**：`static mut` · `thread_local` · `lazy_static` · `OnceLock` · `Mutex` 在 36 个源文件里**一处都没有**。「可重入、无全局态」不是声明，是量得出来的 |
| 已有的跨调用状态 | `evolve_heat` 已经在传：`resume` · `t_start` · `dt_start` · `psi_prev`↔`psi_prev_out` · `sigma_prev`↔`sigma_prev_out` · `exch_prev`↔`exch_prev_out` · `edge_te_in`↔`edge_te_out` · `edge_ti_in`↔`edge_ti_out` · `capped_in`↔`dt_capped` · `saw_elapsed_in`↔`saw_elapsed_out`——**二十个槽，一个入口自己发明的一套** |
| 状态的体量 | 五条数组 × n：n=65 → **2.5 KiB**，n=201 → **7.9 KiB**。**拷贝不是问题** |
| 宿主侧已有 | `engine/body.py` 的 holder / `restart()`（`_holder_spec`）——会话与重启的机械**已经在宿主那边** |

## 三条路 (Three options)

:::{table} 内核持不持有状态。
:name: tbl-fylite-kernel-state

| | 做法 | 三后端一致？ | 溯源 / 复算 | 跨后端对拍（K-6） | 判 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P-1** | **无状态，状态随文档走** | ✓ 完全一样 | ✓ 输入即全部 | ✓ 同入同出 | **裁定** |
| **P-2** | 内核持句柄（会话） | ✗ 远端要会话亲和 + 生命期 + 崩溃清理；wasm 要实例寿命 | ✗ 答案取决于看不见的累积 | ✗ 无法对拍 | 否 |
| **P-3** | 不透明状态团，调用方存了原样交回 | ✓ | △ 存进记录也读不懂 | ✓ | 否（被 P-1 的「声明过的子树」取代） |
:::

**P-2 否决的不是性能，是那三列。** 内核今天**分配也交出**（`fylite_rs_alloc`），但它**从不留住**
——留住就要一张句柄册，那就是全局态，量到的那个零就没了；而远端后端要会话亲和与崩溃清理，
`replay` 与登记册再也复算不出一次运行。

## 裁定 (Rulings)

**S-1 内核无状态，且这条不可交易。** 它是「三种后端一张表」（K-4）、「跨后端一致性」（K-6）
与「记录说得清什么跑了」（K-7）三条同时成立的前提。★内核可以分配、可以交出，**不可以留住**。

**S-2 状态是一棵声明过的子树，不是二十个成对的槽。** `evolve_heat` 那套 `*_in` / `*_out`
是**一个入口自己发明的约定**；再来一个行进式的 code 就会再发明一套。改为：状态在 fyo 文档里
有自己的一块（`fylite:state`），**声明过、可读、可记**，随计划进、随记录出。★这正好搭在
K-8 的双向扁平树上——**状态是内核建出来的那棵树的一枝**，不必另立通道。

**S-3 单步还是多步，是计划的选择，不是内核的。** 内核照旧可以在一次调用里走 `nt` 步
（`evolve_heat` 今天就是），但**必须在每个步界上都能停下并交出完整状态**。于是：
* 长跑要断点续跑 → 少要几步，把状态存下来；
* 崩溃恢复 → 从上一次记录的状态起；
* **取消**——★这条把上一节撤回的回调补上了：**不需要回调也能取消**，把步数预算切小，在两次
  调用之间决定还跑不跑。**控制权在宿主，代价是每 N 步一次交接**，而交接只值几 KiB。

**S-4 状态进记录，记录因此可以从中间起跑。** 一次运行的记录带着它**收尾时**的状态，所以
`replay` 不必从头，登记册里一条含时记录也可以只复算它关心的那一段。★与 S-2 的「补数据后
带树再入」是同一件事的两面：**能交出状态，才谈得上再入**。

★★**一句话的因果**：因为内核无状态，所以状态必须显式；因为状态显式且是一棵树，所以
「补数据再入」「断点续跑」「取消」「从中间复算」四件事**用的是同一个机制**，不是四套。

## 状态管理归谁：机制居中，策略分散 (Where state management lives)

〔已确立〕用户提问（2026-09-04）：状态管理放在中间层还是内核？——**先把「管理」拆开**，
因为它不是一件事，而五件事分属三层。

:::{table} 状态的五件事，各归各。
:name: tbl-fylite-kernel-state-who

| | 做什么 | 归谁 | 为什么只能是它 |
| :--- | :--- | :--- | :--- |
| ① | **声明**状态是什么（哪些槽、什么形） | **内核** | 只有它知道续跑要什么。今天 `evolve_heat` 的二十个槽就声明在 `fyo.rs` |
| ② | **产生 / 消费**状态 | **内核** | 同上；写在它建的那棵树上（K-8） |
| ③ | **携带**状态（随计划进、随记录出） | **中间层** | 它本来就在搬文档；状态是文档的一枝，不必另立通道 |
| ④ | **持久化**（落盘、命名、版本、回收） | **宿主，各自** | 实测各宿主早已各有一套（见下） |
| ⑤ | **决定**何时存、何时续、何时停 | **计划**，由宿主执行 | S-3：单步多步是计划的选择 |
:::

**④ 已经是分散的，而且应当继续分散。**〔已确立〕实测：Python `engine` 有 holder / `restart()`
（`body.py`，48 处）· 数据句柄与运行根（`handles.py`）· 不可变迭代版本与陈旧判定
（`versioning.py`）· 底账与重放（`ledger.py` / `replay.py`）；浏览器那侧四个资源在用
`localStorage` / `sessionStorage`（含跨页交接 `handoff.js`）；远端那档持有者就是**调用方**。

★**所以「管理放中间层还是内核」这个问法本身要修正**：两个都不是**唯一**的答案。

* **不能只放内核**——S-1 已裁：内核留住状态就要句柄册，那是全局态，量到的那个零会没；
  远端要会话亲和与崩溃清理；跨后端再也对拍不了。
* **不能只放中间层**——★★**这条的理由换了**（2026-09-04 同日）：原先写的是「浏览器那侧没有
  中间层」，而 `fylite_runtime` 进 wasm 之后**它有了**。今天的理由是另一条，而且更硬：
  ④ 持久化要碰的是**宿主的设施**——落盘、`localStorage`、远端调用方的存储——**wasm 里的中间层
  一样够不着**，仍要经宿主。能搬进中间层的是「携带」，不是「持久化」。
* **不能只放 Python `engine`**——同一条镜像过来：CLI、浏览器、远端都拿不到。

**S-5 中间层只搬不改。** 状态经中间层时**不解释、不编辑**。它是声明过的子树，所以中间层
**读得懂**——但读得懂不等于可以改：中间层一旦动状态，续跑语义就有了第二份实现，正是本篇一路
在删的那件事。

**S-6 状态带着写它的那个内核的身份；内核拒绝不是自己写的状态。** 内核换了版本，旧状态可能
已经不成立。判据落在门上：状态子树带内核的版本与指纹（K-7 的环境指纹已经在记录里），内核
**按名拒绝**认不出的状态，除非调用方显式说「知道，照跑」。★先例现成：`engine/replay.py`
今天就在守制品的版本漂移，`allow_version_drift` 是一个**要显式给**的开关，给了还要在记录里
说明。状态照抄这条规矩即可，不必发明。

★★**一句话**：**机制居中，策略分散**。机制是那棵文档里的状态子树——内核声明它、产生它，
中间层原样搬运它；策略是各宿主自己的事，因为各宿主的生命周期本来就不同（一次 CLI 调用、
一个 Python 会话、一个浏览器标签页、一个远端请求），而**它们已经各有一套了**。

(fylite-kernel-contract-runtime-wasm)=
# 中间层也进浏览器 (The Middle Layer Ships to the Browser Too)

〔已确立〕用户裁定（2026-09-04）：**`fylite_runtime` 编成 wasm，由 JS 调用**。
`Cargo.toml` 抬头早就写着这条打算（`fylite_runtime.wasm ... ★不含 mdsip`），只是没有脚本
构建它；现在它是裁定。

## 它改掉了什么 (What it changes)

**四层图从此在三个宿主上是同一张。** 此前浏览器那一列缺一层：宿主是 JS，直接调内核 wasm。
现在每个宿主底下都有中间层——本机经 `ctypes` 取 `.so`，浏览器经 JS 取 `fylite_runtime.wasm`，
远端就是那个进程。

**JS 那边少三份实现。** 实测浏览器今天自带：`geqdsk.js` **286 行**（★本仓的**第三份** g-file
实现——Python 那份 2026-09-04 已并入中间层，JS 这份还在）· `fyo.js` 221 · `session.js` 241。
中间层的 wasm 一到，这三份的职责就有了唯一实现。★生成物 `fyo-interface.js` / `deck-names.js` /
`mds-request.js` 是另一回事：它们本来就是从内核声明生成的，留着。

**扁平树的实现从三份变两份。** K-8 的四段缓冲此前预期「浏览器得用 JS 建」；现在**编码器与
解码器只有中间层一份**（Rust），三个宿主共用。M-2 因此比记它的时候更划算。

## wasm 上两个模块怎么见面 (Two wasm modules, one page)

★本机那条路上，中间层用 `dlopen` 取内核（`fylite_runtime/src/kernel.rs`）。**wasm 上没有
`dlopen`**，而内核与中间层是**两个 wasm 模块**（内核私有、中间层公开，不能互相 `use`）。

〔工作假设〕**JS 当接线员，不当翻译。** 页面实例化两个模块；中间层建好四段缓冲，JS 把
**字节**递给内核模块，再把内核交回的树递回中间层。JS **一个字节都不需要看懂**——它搬的是
不透明缓冲，语义在两端。★这与 K-8 的形正好合拍：树是扁平的、索引相连的内存布局，本来就是
为跨边界传递设计的；从一次 C ABI 调用换成两个 wasm 实例的内存之间，性质不变。

〔开放猜想〕另一条是把两者链成**一个** wasm 制品。它省掉接线，但要在构建期把私有内核与公开
中间层链在一起——发布面与许可面都要重判，本篇不预设。

## 边界：wasm 那档没有什么 (What the wasm build does not carry)

`--no-default-features` 关掉三项，都是**原生专用**且理由早已成立：

| 特性 | wasm 上 | 为什么 |
| :--- | :--- | :--- |
| `mdsip` | 无 | 浏览器打不开裸 TCP（`FYL-DESIGN-06` §1 早已关死）；另有用户裁定（2026-09-02） |
| `hdf5` / `netcdf` | 无 | 两个 C 库，链不进 wasm |
| `dlopen` 取内核 | 无 | 见上，改由 JS 接线 |

所以 wasm 那档的中间层是：**文档模型 · JSON · YAML · g-file · 内容识别 · fyo 语义 ·
装配（文件源）· 扁平树的编解码 · 计划合成**。★正好是浏览器要的那些，一个不多。

## 随之要改的 (Consequences)

* **H-2 改口**：浏览器的本地后端仍是页内内核 wasm，但**它经中间层的 wasm 到达**，不再由 JS
  直接调内核的扁平导出。K-1 的判据（`scenario/` 与页面 JS 里不再出现 `fylite_rs_*`）在浏览器
  这一侧因此有了可走的路——今天 `app/assets/fylite.js` 有 **344 处**。
* **G-5 关闭在望**：「wasm 后端的 code 表怎么自报」——中间层的 wasm 在场之后，它像本机那样
  问内核要 code 表即可，不必再靠生成的 `fyo-interface.js` 冒充运行期查询。
* **回调那条理由作废**（见上），但撤回不变。
* **状态那条理由换了**（见上），结论不变。

(fylite-kernel-contract-deltas)=
# 要改口的既有裁定 (Deltas to Standing Rulings)

| 出处 | 现文 | 改为 | 理由 |
| :--- | :--- | :--- | :--- |
| `FYL-CONOPS-00` / `FYL-SRS-01` 通篇「双宿主」 | Python 与浏览器两个宿主 | **多宿主**：CLI、Python 库、网页、AI 面……数目不承重（H-3） | 用户裁定 2026-09-04；「双」记的是分仓前的两个运行时，不是设计约束。本仓另有 44 处散文沿用旧词，随各文档版本行改 |
| `FYL-SRS-01` NR-ENV-004 | 双宿主**必须**共享同一计算核 | **多宿主必须**共享同一**内核契约**；同一 code 在两个后端上的一致性由登记册记录（K-6） | 「同核」是本地 `.so` 与 wasm 出自同一次编译这一**实现事实**，不是需求；可替换之后它仍成立于本地后端，但不再是多宿主一致的定义 |
| `FYL-SDD-01` DE-COMP-02「双薄面」 | 宿主做装配（数组整形、单位与名字、调用顺序） | 宿主做**计划**；装配是内核 code 的一部分（K-3） | 「装配」里藏着物理（度规、剖面），三份拼法已被量到 |
| `FYL-SDD-01` DE-COMP-01 Interface | C-ABI 导出面 + `ABI_VERSION` | 文档门 + code 表 + manifest（K-1 / K-2）；C-ABI 与 ABI 号降为本地后端内部 | 契约必须与实现分离才可替换 |
| `engine.crosshost` 抬头「单核双宿主」 | 两个构建的一致性 | 任意两个后端的一致性（K-6）；「双」同上改「多」 | 同上 |

〔工作假设〕这五条改口在本篇只是**提出**；落文本走 `FYL-SRS-01` / `FYL-SDD-01` 各自的
版本行，本篇不改它们。

(fylite-kernel-contract-plan)=
# 分期 (Phased Plan)

| 期 | 做什么 | 判据 |
| :--- | :--- | :--- |
| **P0 契约** | code 表 + manifest 定为唯一接口（K-1 / K-2）写进 SRS / SDD；后端表的形（K-4）定下；与 `SP-REPORT-15` T-0.4 对齐远端 envelope（K-5）；**改名 `fylite_runtime`（N-1）单独一次提交** | 两处改口落文本；`fylite case describe` 的输出即契约的可读形 |
| **P1 补 code** | 其余 7 个装配型能力工具（`discharge` `breakdown` `feasible` `vstab` `zerod` `coupled` `reconstruction` `tglf` 之中尚未成 code 的）补成内核 code；Python 与页面改走文档门 | `scenario/` 与页面 JS 里 `fylite_rs_*` 归零；十个工具全部声明 `kernel_entry`；crosshost 对十个工具运行 |
| **P2 后端表** | 本地 `.so`、wasm、远端三种后端登记；`--kernel` 按名或地址选；`/api/case` 端点 | 同一份计划在三种后端上各出一份记录，`environment` 各不相同、`whence` 各追得回 |
| **P3 中间层 profile** | 中间层跑 SpData conformance 向量；重叠语义对齐；「profile 不含」清单写进 `FYL-DESIGN-14` | 向量全过或逐条说明不含；`FR-CONF-002` 不违 |

〔工作假设〕P1 是关键路径：它是唯一动物理代码的一期，也是量最大的一期
（271 个调用点）。P0 与 P3 是文本与门禁，P2 在 P1 之后是加法。

(fylite-kernel-contract-gaps)=
# 缺口与开放项 (Gaps and Open Items)

| 编号 | 缺口 | 状态 |
| :--- | :--- | :--- |
| G-1 | 装配搬进内核后，页面**交互**（拖滑块重算一栏）的延迟预算是否仍满足 `FYL-CONOPS-00` 的响应包络——一次门调用比一次扁平调用多一次序列化 | 开；P1 实测 |
| G-2 | 远端后端的 envelope：复用 `fylite serve` 的 JSON-RPC 与 `DriverRequest`，还是另立 `compute.` 方法族 | 开；随 `SP-REPORT-15` T-0.4 裁定 |
| G-3 | ~~内核不认识装置，而导体几何现算归谁~~ | **已关**（K-8，用户裁定 2026-09-04）：装置按 fyo 路径进内核，来路归中间层。内核认识几何，不认识源头 |
| G-4 | 两个后端给出不同的数时，登记册记录的**纳入类别**（V / B / C）怎么定——今天三类都以「外部答案」为对照，后端间对照是第四种 | 开；P2 |
| G-5 | wasm 后端的 code 表怎么自报 | **关闭在望**：中间层进 wasm 之后（{ref}`fylite-kernel-contract-runtime-wasm`）它像本机那样问内核要，不再靠生成的 `fyo-interface.js` 冒充运行期查询 |
| G-6 | 中间层与 SpData 重叠语义的**对齐代价**未量：`$link` 分解、`merge_key`、时间开窗三处各自定义，可能与 SpData 的 `$op` / 标识符语法冲突 | 开；P3 前先量 |

(fylite-kernel-contract-trace)=
# 追溯 (Traceability)

| 本篇裁定 | 上游 | 下游落点 |
| :--- | :--- | :--- |
| K-1 / K-2 | 内核仓 `fyo.rs` 抬头；`FYL-SDD-01` DE-COMP-01 | `FYL-SRS-01`（新 FR：内核接口）· `FYL-SDD-01` DE-COMP-01 Interface |
| K-3 | 用户裁定 2026-09-03；`FYL-SDD-01` DE-COMP-02 Invariant | `FYL-SDD-01` DE-COMP-02 |
| K-4 / K-7 | `FYL-DESIGN-15` R-4（找不到就说、不退化） | 中间层 `kernel.rs`；`engine.provenance` |
| K-8 | 用户裁定 2026-09-04；内核 `fyo.rs` `@fyo-table DEVICE`；`FYL-DESIGN-14` `from_manifest` | 中间层的装置绑定；`scenario/control` · `design` · `analysis` 的搬迁面 |
| K-5 | `SPM-ADR-111`；`SP-REPORT-15` T-1.6 / T-0.4 | 平台 ADR（协议成员） |
| K-6 | `engine.crosshost`；`FYL-SRS-01` NR-ENV-004 | 公开 V&V 登记册 |
| N-1 · N-2 | 用户裁定 2026-09-04（两次）；`FYL-SDD-01` DE-COMP-03 / DE-COMP-09 | Cargo 包名、制品名、C 导出前缀、`_environment.json`、`FYL-DESIGN-14` / `-15` 与 `FYL-SDD-01` 布局表 |
| D-1 | SpData SRS FR-CONF-002；`FYL-DESIGN-14` L-1 / L-8 | `FYL-DESIGN-14`（profile 不含清单） |
| H-1..H-3 | `FYL-DESIGN-09` / `-10` / `-13` / `-15` | 四个页面设计书的 as-built |
