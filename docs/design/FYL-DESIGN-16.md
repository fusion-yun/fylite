---
document_id: FYL-DESIGN-16
title: "可替换内核与四层分工 (The Replaceable Kernel and the Four-Layer Split)"
shortname: fylite-kernel-contract
version: "2.1"
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
  change: 'v2.1 改口落文本：五条既有裁定的改口已随全书重排进入 CONOPS / SRS / SDD v1.0
    （KERNEL 域、DE-LOG-11 / -12），改口表改为〔已确立〕对照，分期 P0 的第一项标已落。
    v2.0 全文重写（用户「优化重写整个设计文档」，2026-09-04）。v0.1..v1.4 是十四次
    同日增量，每次把上一版的改口、作废与换理由叠在正文上；本版按裁定的**现行状态**重排，
    历史只留在本条与追溯表。实质变化四处：①编号去重——「补数据」改 B-1..B-4（原与「状态」
    同用 S-），「状态持有」三选项不再占 P- 号（与分期 P0..P3、SPM-ADR-111 的 P-1..P-6 三重
    撞号），扁平树的四条裁定立为 F-1..F-4（原散在 M-2 段落里），中间层进 wasm 的两条立为
    H-4 / H-5（原无编号）；②K-8b「按表定型的结构体」删除——它已被扁平树取代，不再作为
    工作假设并列；③N-2 并入 N-1，那条被证伪的改名理由缩成一段记录（不抹掉）；④回调式
    撤回的三条理由收成两条（浏览器那条已被 H-4 作废，v1.3 已如实标注），现按作废后的
    状态写。所有实测数字沿用 2026-09-04 的量法与结果，未重量。
    历史：v0.1 初稿（可替换内核、fyo 文档门唯一接口、K-1..K-7 / D-1..D-4 / H-1..H-3、
    分期 P0..P3、缺口 G-1..G-6）· v0.2 多宿主非双宿主；中间层改名评估 · v0.3 / v0.4 改名两次
    执行（fylite_data → fylite_engine → fylite_runtime；第一次理由经核查为假）· v0.6 K-8 装置
    自 A-Box 经中间层以整份文档进内核，G-3 关 · v0.7 K-8a 实测路径形静默撞名 · v0.8 内核收树
    四条路，推荐扁平树 · v0.9 / v1.0 扁平树定为交互接口且双向；回调式整条撤回；补数据四条路
    · v1.1 内核无状态，状态是文档里声明过的子树 · v1.2 状态管理五件事分归三层 · v1.3 中间层
    也进 wasm，两条旧理由如实作废 / 换理由 · v1.4 两组期号合成一条总线，H-2 改口，G-7 / G-8。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-kernel-contract

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-16` |
| 文档名称 (Title) | 可替换内核与四层分工 (The Replaceable Kernel and the Four-Layer Split) |
| 短名 / Slug | `fylite-kernel-contract` |
| 版本 (Version) | v2.1 |
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
| 上游输入 (Upstream Inputs) | `FYL-CONOPS-00`（零安装离线可用；「双宿主」在本篇改口为「多宿主」）· `FYL-SRS-01` NR-ENV-004 / FR-DATA-002..003 · `FYL-SDD-01` DE-COMP-01（计算核）/ DE-COMP-02（装配层：不实现物理）/ DE-COMP-03（Python 执行体）/ DE-COMP-09（数据层）· `FYL-DESIGN-14`（数据层）· `FYL-DESIGN-15`（一个可执行文件、一份命令行规格）· 内核仓 `fyo.rs`（「the kernel computes numbers; the hosts put them into documents」）· `SP-REPORT-15`（fylite 为 sp 协议成员）· `SPM-ADR-111`（执行体六相协议）· SpData `01_core` / `02_mapping` / SRS FR-CONF-002 |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 不取代任何文档；改口 `FYL-SRS-01` NR-ENV-004 与 `FYL-SDD-01` DE-COMP-01 / DE-COMP-02 的表述（{ref}`fylite-kernel-contract-deltas`） |
:::

(fylite-kernel-contract-intro)=
# 可替换内核 (The Replaceable Kernel)

〔一句话〕**内核是可替换的一层，fyo 文档门是它唯一的接口；门上传递的是一棵扁平树，双向、
不解析；中间层 `fylite_runtime` 负责数据的集成与转换、计划的合成与内核的选择；其上是多个
宿主——CLI、Python 库、网页、AI 面。** 一个内核可以是本地的 `libfylite_kernel.so`、页内的
wasm、另一台机器上的进程，或另一种实现；每个宿主对它们说同一种话——一份 fyo 计划进，
一份 fyo 记录出。

〔为什么〕这张图在写本篇之前**只对一条路成立**：`fylite case` 经中间层的 `fylite_rs_fyo`
一扇门走的是「结构进、结构出」；Python 宿主与浏览器页面各自绑在几百个扁平 C 导出上。那份
导出面是**这一个实现的形状**，不是契约——换实现即断，换版本靠一个整数硬拒。本篇把「可替换」
从三个 code 推广到全部能力，定下门的形状与内核的状态模型，并把要改动的既有裁定逐条点名。

〔与上游的分工〕`SP-REPORT-15` 规划的是 sp **向下**调 fylite（`ExternalBody` / `RemoteBody`，
六相协议）；本篇是 fylite **向下**调内核。两者是同一个模式的两层：fylite 对上是协议成员，
对下是内核宿主。远端内核的调用直接共形 `SPM-ADR-111` 的六相，不另立协议（K-5）。

〔裁定的来源〕本篇的裁定全部形成于 2026-09-04，其中十条是用户当日的裁定（在各条处标明），
其余是按这些裁定与当日实测推出的。实测数字均为当日量得，未重量。

(fylite-kernel-contract-asis)=
# 现状 (As-Is)

〔已确立〕以下为 2026-09-04 在 `fylite` 公开仓与 `fylite_kernel` 私有仓实测。

## 谁走哪扇门 (Which door each host uses)

:::{table} 各宿主走哪扇门。「扁平」＝直接调 `fylite_rs_*` 导出；「文档门」＝结构进结构出。
:name: tbl-fylite-kernel-asis-calls

| 宿主 | 走扁平 C 导出 | 走文档门 |
| :--- | ---: | :--- |
| Python（`scenario/` `fyo.py` `device.py` `engine/` `io/`） | **125** 个不同函数（`kernel.py` 声明 442 个签名） | `K.scenario` 5 个声明入口（`evolve_heat` `profit` `transport` `vstab` `zerod`）；十个能力工具里**只有 `evolve`** 声明了 `kernel_entry` |
| 浏览器（`app/assets/*.js`） | **146** 个不同导出（`fylite.js` 内 344 处调用点） | `.scenario()` 仅 2 处 |
| `fylite case`（经 `fylite_runtime`，`dlopen`） | 0 | `fylite_rs_fyo` 一扇门，**3 个 code**（`evolve` `zerod` `transport`） |
:::

:::{table} 内核今天怎么钉、怎么换。
:name: tbl-fylite-kernel-asis-pin

| 事项 | 实测 |
| :--- | :--- |
| 版本 | `ABI_VERSION = 125`，由内核仓构建生成进 `_abi.py`；装载器见到不符**硬拒** |
| 换内核 | `$FY_KERNEL_LIB`（Python）/ `FYLITE_KERNEL_LIB`（中间层）——都只是**文件路径**；两边各自 `dlopen` 同一个 `.so` |
| 第二种实现 | 无落点：没有后端表，没有「哪个后端完成哪些能力」的声明 |
| 远端 | 没有远端**内核**。存在的两样都是远端 **fylite**：`fylite serve` / `mcp` 暴露整个 fylite；`fylite-app` 的 `/api/*` 五个端点（`health` `shot` `tree` `node` `signal` `measurements`）全是 mdsip 取数 |
| 跨宿主一致性 | `engine.crosshost`：比的是**同一内核的两个构建**（原生 vs wasm），只对声明了 `kernel_entry` 的工具运行——今天一个 |
| 内核的全局态 | **零**：`static mut` · `thread_local` · `lazy_static` · `OnceLock` · `Mutex` 在 36 个源文件里一处都没有 |
| 内核的依赖 | `Cargo.toml` 依赖表只有 `rayon`（可选）；`cdylib` + `rlib`，同一份 `c_api.rs` 也编 `wasm32-unknown-unknown`；**没有文档模型，没有 JSON 解析器** |
| 中间层已有 | `document.rs`（710 行）· `json.rs`（488）· `yaml.rs`（793）· `fyodoc.rs`（460）——树、解析、语义都在这边；树类型是 `Node`（`Null` · `Bool` · `Int` · `Float` · `Str` · `Array{shape, F64\|I64\|Str}` · `List` · `Map`） |
:::

`fylite_rs_fyo` 已经是可替换内核该有的形：code + 按名的设置 + 输入进，结果的声明 + 平铺
数据出，缓冲区由内核持有、调用方经 `fylite_rs_free` 释放，装成文档是中间层 `case.rs` 的事。
它只是尚未成为**唯一**的门，而且入参与出参的形状都还是文本（下）。

(fylite-kernel-contract-path-defect)=
## 今天的门在做文本活，并且会静默取错数 (The door does text work, and silently mis-binds)

〔已确立〕直接经 `fylite_rs_fyo` 实测。**两个方向都是文本**：入参是一组 `(路径, 维数, 数值)`
三元组，由调用方逐条摊平；出参是内核格式化的一段 **TSV 清单**
（`field<TAB>ids<TAB>path<TAB>units<TAB>offset<TAB>len<TAB>dims`）外加一条平铺 f64，中间层
解析那段 TSV（`cells[4].parse()`），再按其中的路径字符串把树建出来（`documents()`）。

入参那一侧不只是笨。内核收下路径之后**当场把路径丢掉**——`case.rs`：

```rust
for (k, v) in req.inputs {
    let key = k.rsplit('/').next().unwrap_or(k);   // 只留最后一段
    if iblock.iter().any(|r| r[0] == key) { iv.push((key, v)); }
```

而 `pack` 对重复的 key **后写者胜**，不报错、不留注记。两份**不同文档**里同名收尾的路径
因此并成一条。拿 `entry/transport` 量：

| 绑了什么 | 答案 `y[-3:]` |
| :--- | :--- |
| 只绑 `equilibrium/profiles_1d/grid/rho` | 2548.98 · 1426.53 · 100 |
| 只绑 `core_profiles/profiles_1d/grid/rho` | 9895.92 · 5406.12 · 100 |
| **两条都绑** | **9895.92 · 5406.12 · 100**（后者胜，`rc=0`，无一句话） |

声明里 `rho` 被三个入口 declared、`vprime` 被两个——同名收尾不是假想。门**看起来**按路径，
**实际上**按叶子名，两者不一致时没有任何一侧会说话。这是 K-8 与 F-1..F-4 要关掉的那一类。

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
  subgraph D[中间层 fylite_runtime — SpData profile；本机 .so · 页内 wasm]
    ASM[装配 assemble / fetch]
    FMT[格式 g-file · JSON-LD · HDF5 · netCDF · mdsip]
    CASE[case.rs：计划 → 门 → 记录]
    TREE[扁平树 编码 / 解码]
  end
  subgraph K[内核 Kernel — 可替换]
    LOCAL[本地 libfylite_kernel.so]
    WASM[页内 wasm]
    REMOTE[远端进程 · JSON-RPC 六相]
    OTHER[另一种实现]
  end
  F -->|fyo 计划 fyo:ScenarioSpecification| D
  D -->|一扇门：code + 设置 + 扁平树（输入文档 · 状态）| K
  K -->|扁平树（结果 · 状态）| D
  D -->|fyo 记录 spo:ComputationRecord| F
```

〔已确立〕四层各自的**唯一职责**与**禁止事项**。每个宿主底下都有中间层：本机经 `ctypes`
取 `.so`，浏览器经 JS 取 `fylite_runtime.wasm`（H-4），远端就是那个进程。

| 层 | 职责 | 禁止 |
| :--- | :--- | :--- |
| 宿主（多个） | 把用户意图写成一份 fyo 计划；把一份 fyo 记录呈现出来；持久化自己的状态（S-5） | 不做装配算术，不直接触碰任何内核符号 |
| 中间层 | 计划的合成与绑定；把文档编成扁平树、把树解成文档；结果装成记录；格式与来源的读写与转换；内核的**发现与选择**；Rust 宿主的命令行与 `app/` 的伺服 | 不算物理；不写 MDSplus；不改状态（S-5 ③） |
| 内核 | 完成一个 code：从树到树；声明并产生自己的状态 | 不读文件、不开网络、**不认识数据源头**、不认识任何序列化格式、**不留住状态** |
| 内核契约 | code 表 + 每个 code 的输入声明与输出声明；每个后端自报「完成哪些 code、产哪些路径、什么单位」 | 不再有宿主可见的 ABI 号 |

(fylite-kernel-contract-rulings)=
# 裁定 (Rulings)

## 内核契约 K-1..K-8 (The kernel contract)

**K-1 文档门是唯一的内核接口。** 宿主（Python、浏览器、`fylite-app`）**只**经「一份计划进、
一份记录出」调用内核。`c_api.rs` 的 442 个导出降为**本地后端的实现细节**：`fylite.kernel`
与 `app/assets/fylite.js` 里那 125 / 146 个调用点，或者搬进内核成为 code 的一部分，或者
留下但只被本地后端自己用。判据：`scenario/` 与页面 JS 里不再出现 `fylite_rs_*` 符号名
（现有 `test_no_bare_kernel_aliases.py` 的思路推广一层）。

**K-2 code 表是能力的声明，输出声明是结果的声明。** 一个内核后端自报它完成哪些 code、
每个 code 要哪些输入、产哪些 fyo 路径、什么单位——`fylite case describe` 今天打印的就是这
张表。宿主按表选后端、按声明读结果；**不再按 ABI 号**判断能不能调。`ABI_VERSION` 保留给
本地 `.so` 的装载器自检（它守的是 C 签名，那是本地后端内部的事）。

**K-3 装配搬进内核，宿主退成计划构造器。** 今天 Python 与页面各持一份 Miller 度规、抛物
剖面、相位表的装配算术（`FYL-DESIGN-15` 已量：同一闭式三份拼法）。这些成为 code 的一部分
（`[assembled]` 那一类，`code/evolve` 已是先例）。这是用户 2026-09-03 裁定「kernel 中已经有
的功能不应再 python 侧重复实现」的延长，也是 `FYL-SDD-01` DE-COMP-02「本层不实现物理与
数值」的落实。★此前判为「要装置、故搬不进内核」的五个工具（`discharge` / `breakdown` /
`feasible` / `vstab` / `reconstruction`）按 K-8 只是**多收一份装置文档**，与 `evolve` 收度规、
`zerod` 收相位表同类——拦阻不存在。

**K-4 三种后端一张表。** 本地 `.so`、页内 wasm、远端进程登记在同一张后端表里，每条记：
怎么到达（路径 / 已加载的模块 / 地址）、code 表、环境指纹。选择规则显式（`--kernel <名或
地址>`、环境变量、缺省本地），**不静默回退**：要的后端不在场就说不在场，不换一个能力更少
的顶上。

**K-5 远端内核共形六相协议，不另立协议。** 远端调用的生命周期就是 `SPM-ADR-111` 的
P-1..P-6（interpret_inputs → provision → stage → execute → interpret_outputs + harvest →
dispose）；载荷就是那份计划与那份记录。`fylite serve` 的 JSON-RPC envelope 复用为 `compute.`
方法族还是另立，与 `SP-REPORT-15` T-0.4 一并裁定（G-2）。

**K-6 跨后端一致性是登记册的一类记录。** `engine.crosshost` 今天比「同一内核的两个构建」；
推广后比「同一 code 在两个后端」。判据形式**不变**：count / flag 逐位哈希、real 容差带、
noise 只判小、差异必须由环境指纹解释——`fyo:ComparisonRecord` 与公开 V&V 登记册已经承载
这种记录，不新开体例。

**K-7 一个后端一个环境指纹，记录里必须有。** 记录的 `environment` 写明是哪个后端（本地 /
wasm / 远端地址）、哪个版本、什么指纹，`whence` 追得回去。两个后端给出不同的数是**可能的、
合法的**，前提是记录里说得清是谁给的。

**K-8 装置自 A-Box 经中间层以整份文档进内核；内核不问来路，也不收路径。** 〔已确立〕用户
裁定（2026-09-04）：*device 信息从 abox 读入，由 runtime 导入，kernel 不需要管数据源头*；
*kernel 不接受 path，只接受完整的 fyo 结构体*。两件事：

| | 裁定 | 依据 |
| :--- | :--- | :--- |
| 来路 | A-Box（fydoc / fydata）是装置的真源（epoch × 提供者 × 绑定）；中间层读它（`assembly.rs` / `from_manifest` 已在做）并装成一份完整的 `fyo:DeviceDescription`；内核收下就算 | 内核 `fyo.rs` 早有 `@fyo-table DEVICE`（34 槽：线圈矩形、`turns_with_sign`、`fylite:channel_map`、真空室单元与电阻率、限制器轮廓），也早在算 M / R / 响应行（`mutual_matrix_self` · `mutual_matrix_cross` · `resistances` · `channel_fold` · `plasma_filaments` · `vertical_stiffness`）。它认识**这个形**，不认识 `$FYLITE_DEVICE_DIR`、`machine.yaml`、epoch 与提供者 |
| 交付单位 | 整份 fyo 文档（`fyo:equilibrium`、`fyo:DeviceDescription`、`fyo:core_profiles` …），内核自己在结构里走，**取不到按名拒绝** | 路径形把「`time_slice` 是结构数组、要落到第 0 个」留在调用方，每多一个宿主就多一份走法（本仓已为此生成过一条 `AOS_PATHS` 声明）；并且实测会静默撞名（{ref}`fylite-kernel-contract-path-defect`） |

★内核「不认识装置」是过强的说法，正确的是「不认识数据源头」。★「整份文档」在 ABI 上的
形就是下一节的扁平树；进是树，出也是树，**两头同一种东西**。门仍只有一扇（K-1 不受影响）。

(fylite-kernel-contract-tree)=
## 交互接口：扁平树 F-1..F-4 (The interface: a flat tree)

〔已确立〕用户裁定（2026-09-04）：*接受 flat tree，作为交互接口*；*内核不仅读还要写，但
不解析，只处理内存中的树结构*。

四条路曾并列评估；裁定取 M-2：

:::{table} 内核收下层次化数据的四条路。
:name: tbl-fylite-kernel-tree-options

| | 做法 | 内核新增 | 收半结构化 | 判 |
| :--- | :--- | :--- | :--- | :--- |
| M-1 | 定型完整记录：每张 `@fyo-table` 生成一个 struct，槽按声明齐全 | ~0（生成物） | ✗ 只认已声明的槽 | 是 M-2 的子集；不单独立项 |
| **M-2** | **已解析的扁平树**：中间层把 `Node` 摊成四段缓冲，内核借用着走 | ~300 行阅读器 + ~250 行构建器，零依赖 | ✓ | **裁定** |
| M-3 | 内核自带 JSON / CBOR 解析器 | ~500–900 行 | ✓ | 否——把 `json.rs` 在内核里再写一遍；文本浮点往返；内核本不许读文件，多出的能力无处可用 |
| M-4 | 回调式：内核按需回调宿主取节点 | ~100 行 | ✓ | 否——见 {ref}`fylite-kernel-contract-callback` |
:::

**F-1 形：四段缓冲，索引相连，先序排列。** ①节点表 `[Node32]` 定长记录：种类 · 名字
（偏移 + 长度）· 第一个孩子 · 下一个兄弟 · 载荷偏移与长度 · 形状（偏移 + 维数）——**用下标
相连，不用指针**，所以它既是「内存里的树」又能跨 C ABI 而不必序列化成文本；②名字块
UTF-8；③**f64 载荷，8 字节对齐、独立成段**——数值内核要的是 `&[f64]` 零拷贝，面向字节的
格式在这里恰恰最不合适；④整数 / 字符串载荷各一段。fyo 文档的重量在大 f64 数组上，结构
本身很小（装置文档最深 11 层，`pf_active/coil` 14 个元素——结构数组是常态）。

**F-2 双向：两侧各一读一写。**

| | 读 (decode) | 写 (encode) |
| :--- | :--- | :--- |
| 中间层 | 收内核交回的树 → 自己的 `Node` | 自己的 `Node` → 四段缓冲，随计划交出 |
| 内核 | 阅读器 `Doc<'a>` 借用四段：`root()` · `child(name)` · `at(i)` · `f64s()` · `str()` · `need(路径, 说明)`（取不到按名拒绝）；不分配、不解析 | 构建器 `Tree`：`map()` · `field()` · `array(name, shape, &[f64])` · `list()`，按已声明的输出路径落位，沿路补出中间的映射与结构数组；经既有的 `fylite_rs_alloc` 交回 |

所有权那一半不必发明：内核今天就在 `fylite_rs_alloc` / `hand_out` 里分配并交出缓冲、中间层
负责释放。〔工作假设〕读改写（收一份文档、添几个量、原样交回）由构建器从已解码的树播种
支持；第一版可以不做，但格式不能挡住它——B-2 与 S-2 都要它。

**F-3 进门校验一次，O(n)，之后不再信任缓冲。** 偏移全在界内 · 先序单调（无环）· f64 段
8 字节对齐 · 名字块是合法 UTF-8。畸形缓冲当场拒绝。

**F-4 半结构化的边界：看得见，不等于可以用。** 内核**看得见**未声明的键，但**只从已声明的槽
取数**，未声明的至多记一句注记。否则「声明或拒绝」（K-8）就散了。

★**这不是给两边加活，是把两边现有的文本活删掉**：

:::{table} 双向树取代的四处——两侧各两处，全是文本活。
:name: tbl-fylite-kernel-tree-removes

| 在哪 | 今天做什么 | 之后 |
| :--- | :--- | :--- |
| 内核 `c_api.rs::fyo_manifest` | 把结果格式化成 TSV 清单（约 30 行） | 删；改为建树 |
| 中间层 `case.rs::Outcome::parse` | 解析那段 TSV | 删 |
| 中间层 `case.rs::documents` | 按 `field` 行里的路径字符串把树建出来 | 删；树是收到的 |
| 内核 `case.rs` 那句按 `/` 切尾 | 丢掉入参路径、重复键后写者胜 | 删；两份文档是两个根，撞不上 |

净账：内核 +约 550 / −30 行，中间层 +约 350 / −100 行；**两边都不再有文本格式化或文本
解析**，fyo 树的形从此只有内核一处在按表落位，编码器与解码器只有中间层一份（Rust），
三种宿主共用（H-4）。**不变**：内核仍不读文件、不开网络、不认识数据源头、不认识任何序列化
格式；它会分配，用它今天就在用的那条 `fylite_rs_alloc`。ABI 号加一。

(fylite-kernel-contract-callback)=
### 回调式：已撤回 (Callbacks: withdrawn)

〔已确立〕2026-09-04 同日提出、评估、**由用户整条撤回**——包括评估时自留的「只做取消 /
进度 / 注记」的窄口子。**门上没有回调，一个也没有**；取消由 S-3 的步数预算承担。

提案是中间层向内核提供一组 entry（函数指针），内核在运行时回调过去读写中间层活着的那棵树。
对本机 `.so` 它只要一张约百行的 vtable，树的实现真的只有一份。两条把它否掉，各自足够：

| | |
| :--- | :--- |
| **远端内核**（K-5） | 每次取值一次网络往返 |
| **溯源**（K-7） | 输入集变成「内核当时恰好问了什么」，运行期才定；记录说不清、算例不可复算 |

回调式买到「一份实现」，卖掉的是**远端后端**与**可复算**，而 K-4 明写三种后端一张表、K-7
要记录说得清什么跑了。★评估时另给过一条「浏览器那侧宿主是 JS、得用 JS 再实现一遍树 API」，
已被 H-4 作废（中间层到了浏览器，那侧的树也是 Rust）；撤回不因此动摇。

(fylite-kernel-contract-more-data)=
## 内核跑到一半要补数据 B-1..B-4 (When the kernel needs more data mid-run)

〔已确立〕用户提问（2026-09-04）。这是回调唯一真正想解决的事，撤回之后必须正面答。四条路
按优先次序，**不含惰性取数**。

**B-1 先问后跑。**〔首选〕门加一个**只问不算**的相：给定 code 与设置，内核回答它将要什么
（哪些文档、哪些槽、哪些维数），中间层据此绑定，再跑。★不是新机制：`fylite case describe`
已在打印 code 表与逐入口的声明块，`fylite case plan` 已停在内核之前打印合成好的计划——缺的
只是让「要什么」随**设置**变化（`imp_id = 74` 就得绑钨的表）。★它正是 `SPM-ADR-111` 六相里
的 P-1 `interpret_inputs` / P-2 `provision`：K-5 已要求远端内核共形六相，本机内核照做只是
让三个后端说同一套话。

**B-2 按名拒绝，补齐后带树再入。**〔B-1 够不着时的兜底〕需求真的与数据有关、事先算不出来
时（组分算完才知道要哪条辐射曲线），内核**拒绝并说全**：这一轮发现的全部缺口一次列出，不
一条一条来回。机制在场——`ERR_MISSING` 与 `refuse(...)` 就是干这个的。★再入的代价是重算，
除非能续跑；续跑要一份状态，状态就是内核已经建好的那棵树——所以拒绝时一并交回**已算出的
部分 + 那棵树**，补齐后带着它再入。`evolve` 早有 `resume` 那一族参数，这条把「续跑」从一个
entry 的特例提成门的通例（S-2）。

**B-3 是常数就编进去。**〔物理表〕辐射系数、FLR 表、台基表这类不随算例变的东西随内核走，
今天已有四份（`edge_tables.rs` · `closure_tables.rs` · `pedestal_tables.rs` · `flr_tables.rs`）。
★判据是**许可**不是大小：四份里体量最小的 ADAS21 是唯一许可不过的（`FYDOC-REPORT-17`）。

**B-4 宁滥勿缺。**〔否决〕中间层把「可能要的」一股脑绑上。大数组上浪费，且「可能要的」
同样事先不知道——它没有解决问题，只是把问题挪到中间层。

:::{table} 四条路与撤回的回调。
:name: tbl-fylite-kernel-more-data

| | 做法 | 何时用 | 三个后端都成立 | 溯源 |
| :--- | :--- | :--- | :--- | :--- |
| **B-1** | 先问后跑（P-1 / P-2） | 需求可由设置算出——多数情形 | ✓ | 输入集显式，一次定 |
| **B-2** | 按名拒绝 + 带树再入 | 需求与数据有关 | ✓ | 两次调用都进记录，各自输入集显式 |
| **B-3** | 编进内核 | 不随算例变的物理表 | ✓ | 随制品的指纹 |
| B-4 | 宁滥勿缺 | — | ✓ | 输入集虚胖 |
| ~~回调~~ | ~~运行时回调取数~~ | — | ✗ | ✗ |
:::

★共同的那条线：**一次调用的输入集在调用开始时就已经定死**。惰性取数被否掉的根本原因不是
慢，是它让「这次跑用了什么」变成只有运行期才知道的答案——而那正是 `whence` / `replay` /
登记册要复算的东西。

(fylite-kernel-contract-state)=
## 内核的状态 S-1..S-6 (Kernel state)

〔一句话〕**内核不持有状态；状态是文档里一棵声明过的子树，随计划进、随记录出。**「单步
还是多步」是计划的选择，内核必须在每个步界上都能停下并交出完整状态。

〔已确立〕实测：内核全局态为零（{numref}`tbl-fylite-kernel-asis-pin`）；已有的跨调用状态
只在 `evolve_heat`，以二十个成对的槽传（`resume` · `t_start` · `dt_start` · `psi_prev`↔
`psi_prev_out` · `sigma_prev`↔`sigma_prev_out` · `exch_prev`↔`exch_prev_out` · `edge_te_in`↔
`edge_te_out` · `edge_ti_in`↔`edge_ti_out` · `capped_in`↔`dt_capped` · `saw_elapsed_in`↔
`saw_elapsed_out`）；状态体量五条数组 × n，n=65 → 2.5 KiB，n=201 → 7.9 KiB——拷贝不是问题。

:::{table} 内核持不持有状态：三条路。
:name: tbl-fylite-kernel-state

| 做法 | 三后端一致 | 溯源 / 复算 | 跨后端对拍（K-6） | 判 |
| :--- | :--- | :--- | :--- | :--- |
| **无状态，状态随文档走** | ✓ 完全一样 | ✓ 输入即全部 | ✓ 同入同出 | **裁定** |
| 内核持句柄（会话） | ✗ 远端要会话亲和 + 生命期 + 崩溃清理；wasm 要实例寿命 | ✗ 答案取决于看不见的累积 | ✗ | 否 |
| 不透明状态团，调用方原样交回 | ✓ | △ 存进记录也读不懂 | ✓ | 否——被「声明过的子树」取代 |
:::

**S-1 内核无状态，且这条不可交易。** 它是 K-4、K-6、K-7 三条同时成立的前提。内核可以
分配、可以交出，**不可以留住**——留住就要一张句柄册，那就是全局态。

**S-2 状态是一棵声明过的子树，不是二十个成对的槽。** `evolve_heat` 那套 `*_in` / `*_out`
是一个入口自己发明的约定；再来一个行进式的 code 就会再发明一套。改为：状态在 fyo 文档里有
自己的一块（`fylite:state`），声明过、可读、可记，随计划进、随记录出——它是内核建出来的那
棵树的一枝（F-2），不另立通道。形的细节见 G-8。

**S-3 单步还是多步是计划的选择；内核必须在每个步界能停并交出完整状态。** 内核照旧可以
在一次调用里走 `nt` 步，但断点续跑（少要几步、存状态）、崩溃恢复（从上一次记录的状态起）、
**取消**（把步数预算切小，在两次调用之间决定还跑不跑）都由此得到——控制权在宿主，代价是
每 N 步一次几 KiB 的交接。**取消因此不需要回调。**

**S-4 状态进记录，记录因此可以从中间起跑。** 一次运行的记录带着它收尾时的状态，`replay`
不必从头，登记册里一条含时记录可以只复算它关心的那一段。与 B-2 是同一件事的两面：能交出
状态，才谈得上再入。补数据再入 / 断点续跑 / 取消 / 从中间复算四件事**用的是同一个机制**。

**S-5 状态管理：机制居中，策略分散。**〔已确立〕用户提问「放中间层还是内核」——「管理」是
五件事，分属三层：

:::{table} 状态的五件事，各归各。
:name: tbl-fylite-kernel-state-who

| | 做什么 | 归谁 | 为什么只能是它 |
| :--- | :--- | :--- | :--- |
| ① | 声明状态是什么（哪些槽、什么形） | 内核 | 只有它知道续跑要什么（今天就声明在 `fyo.rs`） |
| ② | 产生 / 消费状态 | 内核 | 写在它建的那棵树上 |
| ③ | 携带（随计划进、随记录出） | 中间层 | 它本来就在搬文档；**只搬不改**——中间层一旦动状态，续跑语义就有第二份实现 |
| ④ | 持久化（落盘、命名、版本、回收） | 宿主，各自 | 实测早已分散：Python `engine` 的 holder / `restart()`（`body.py`）· `handles.py` · `versioning.py` · `ledger.py` / `replay.py`；浏览器四处 `localStorage` / `sessionStorage`（含 `handoff.js`）；远端的持有者就是调用方。★持久化要碰宿主的设施，wasm 里的中间层一样够不着 |
| ⑤ | 决定何时存、何时续、何时停 | 计划，由宿主执行 | S-3 |
:::

三个「只放某一层」的答案各被一条事实否掉：只放内核＝全局态回来（S-1）；只放中间层＝
持久化够不着宿主设施；只放 Python `engine`＝CLI、浏览器、远端都拿不到。各宿主的生命周期
本来就不同（一次 CLI 调用、一个 Python 会话、一个浏览器标签页、一个远端请求），策略就该
各自定。

**S-6 状态带着写它的那个内核的身份；内核拒绝不是自己写的状态。** 状态子树带内核的版本与
指纹（K-7 的环境指纹已在记录里），内核按名拒绝认不出的状态，除非调用方显式说「知道，
照跑」。先例现成：`engine/replay.py` 的 `allow_version_drift` 是一个要显式给的开关，给了还要
在记录里说明——照抄。

## 中间层 N-1 · D-1..D-4 (The middle layer)

(fylite-kernel-contract-naming)=
**N-1 这一层叫 `fylite_runtime`。**〔已确立〕用户裁定（2026-09-04，两次），**已执行**：crate
`rust/fylite_runtime/`、制品 `libfylite_runtime.so`、C 导出 `fylite_runtime_*`（31 个）、环境
变量 `FY_RUNTIME_LIB`；内核仓 `rust/build.sh` 的生成落点同批改。两次改名都在未推送之前完成，
对外没有一个版本用过中间的名字。

这一层今天做的是六件事：①格式读写与转换；②多源装配；③计划合成与绑定 → 门 → 记录
（`case.rs`）；④内核的加载与选择（`kernel.rs`）；⑤Rust 宿主的全部命令行（`src/cli/`）；
⑥内嵌并伺服 `app/`。原名 `data` 只说了①②。候选里 `io` 更窄，`core` 与内核撞，`host` 与
用户定下的「宿主」层撞，`fyo` 与本体仓和 Python `fylite.fyo` 撞，`engine` 与 Python 包
`fylite.engine` 撞词；`runtime` 在 wasm 语境里另有所指，但那是浏览器的运行时，不是 fylite
的组件名，实测无第二个读法。

★**一条被证伪的理由，记下不抹掉。** 第一次改名（→ `fylite_engine`）的理由是「与 Python
`fylite.engine` 同名正是要的：`FYL-SDD-01` DE-COMP-03 的职责与此 crate 逐条重合」。逐条
查过，二比五：命令行 ✓、原生库装载 ✓，`serve` / `mcp` / 制品清单与溯源 三项该 crate 零处。
逐模块量，二十项职责真重叠只有四项（命令行解析——`FYL-DESIGN-15` 一份规格三个宿主的
有意两份 · 内核装载 · 计划→内核→记录 · g-file ↔ `fyo:equilibrium`），重心完全不相交（只在
Rust 约 9 500 行：mdsip · mdsbind · yaml · netcdf · document · assembly · hdf5 · ids_meta ·
tensor · 桌面服务面；只在 Python 约 6 200 行：六相执行体 · `serve` / MCP · 算例报告 · 清单 ·
溯源 · 重放 · 底账 · 版本 · 别名 · 跨宿主）。两者是共用一个词的两个不同组件，故 `engine`
留给 Python 那一层（跑运行、记运行，与 `SPM-ADR-111` 用词一致）。随之：命令词 `fylite
data …` 不改（它说的是七个数据动词，不是层名）；`fylite.io.fydoc` 留在 `fylite.io` 下（它是
这层 `.so` 的 ctypes 面，不塞进另一个组件的包里）。

(fylite-kernel-contract-data)=
〔已确立〕对照实测：

| | SpData | `fylite_runtime` |
| :--- | :--- | :--- |
| 定位 | 规范集：HTree 逻辑树、标识符语法、`$op` 变换、查询 / 修补、PROV、mapping 文档、backend profile | 实现：读写器 + mdsip 只读客户端 + 装配 |
| Rust | `rust/src/lib.rs` 自述 **planned** | 83 个单元测试的完整数据面，两个制品 |
| Python | 三个插件（`file_hdf5` `file_netcdf` `mdsplus`） | 经 ctypes 取同一份 `.so` |
| 装配 | mapping 文档：逻辑目标路径 → 后端源 | `fylite:Assembly/1`：`$source` / `$link` / `merge` / `select` |
| `fylite_runtime` 没有的 | | `$op` 变换、查询 / 修补语法、惰性指针与分级载荷、标识符通配、conformance 向量 |

**D-1 中间层是 SpData 的一个 profile，不是它的简化重写。** 它是生态里最完整的 Rust 数据面，
而 SpData 的 Rust 投影还是空壳。SpData SRS `FR-CONF-002` 规定任何投影不得分叉契约语义；
`fylite_runtime` 的 `$link` 分解、合并键、时间开窗今天都是自己定的。定为 profile 的含义：
凡与 SpData 重叠的语义（树、路径、mapping、PROV）**以 SpData 为准**并跑它的 conformance
向量；不重叠的（mdsip 编解码、IMAS 两种布局、g-file）是 profile 自己的扩展，写明「profile
不含」的那些不算缺陷。

**D-2 中间层是内核的发现者与选择者。** K-4 的后端表住在中间层（`kernel.rs` 今天已在 `dlopen`
内核并读它的 code 表）；Python 的 `fylite.kernel` 与页面的加载器退为本地后端的两个驱动。理由
与 `FYL-DESIGN-14` L-1 同源：一棵中立的树居中，N 个后端是 N 条驱动而不是 N 份宿主代码。

**D-3 计划的合成只在一处。** 多份计划按序合成、`--set` / `--bind` 后叠、按 fyo 路径取绑定
输入——`case.rs` 已做；Python `engine.cases.plan` 与页面的会话文档合成是同一件事的第二、
第三份，收敛到中间层。

**D-4 中间层不算物理，也不写 MDSplus。** 与 `FYL-DESIGN-14` L-8 同。K-3「装配搬进内核」不是
「搬进中间层」：度规与剖面是物理，归内核；合成与绑定是文档操作，归中间层。

## 多宿主 H-1..H-5 (Hosts)

**H-1 宿主只写计划、只读记录。** 页面控件的每一次改动产生的是计划里的一个字段，「计算」键
送出一份计划；1.5-D 栏读 g-file、0-D 工况跨页交接（`FYL-DESIGN-09` / `-10`）都成为计划里的
一个绑定。页面里的装配算术随 K-3 撤出。

**H-2 浏览器的本地后端是页内内核 wasm，经中间层的 wasm 到达；远端后端是 `fylite-app` 的
一个端点。** JS 不再直接调内核的扁平导出（今天 `fylite.js` 344 处）。因为门只有一扇，
`/api/case` 是**一个**端点，不是一族；它与今天的五个 mdsip 端点同守回环、同做两侧守卫
（`FYL-DESIGN-13` P-12）。静态站点没有进程，只有本地后端；与「静态即无服务端组件」
（`FYL-DESIGN-15` R-3）一致。

**H-3 宿主是多个，数目不承重。**〔已确立〕用户裁定（2026-09-04）：是**多宿主**，不是
`FYL-CONOPS-00` 起的「双宿主」——「双」记的是分仓前 Python 与浏览器两个**运行时**。按前端
数今天四个：CLI（`fylite` / `fylite-app`）、Python 库、网页、AI 面（`serve` / `mcp` / BYOK）；
差别只在**谁写计划**。再来一个（notebook、另一种 GUI、另一台机器上的代理）不改本篇任何
一条；它们共享一份计划的词汇（`fyo:ScenarioSpecification`）与一份记录的词汇
（`spo:ComputationRecord`）。

(fylite-kernel-contract-runtime-wasm)=
**H-4 中间层也进浏览器：`fylite_runtime` 编成 wasm，由 JS 调用。**〔已确立〕用户裁定
（2026-09-04）。`Cargo.toml` 抬头早写着这条打算（`fylite_runtime.wasm ... ★不含 mdsip`），
只是没有脚本构建它。后果三条：

- **四层图在三种宿主上是同一张**（{ref}`fylite-kernel-contract-target`）。
- **JS 少三份实现**：`geqdsk.js` 286 行（本仓的**第三份** g-file 实现——Python 那份已并入
  中间层）· `fyo.js` 221 · `session.js` 241 的职责归中间层。生成物 `fyo-interface.js` /
  `deck-names.js` / `mds-request.js` 是从内核声明生成的，留着。
- **扁平树的编解码只有中间层一份**，三种宿主共用；G-5 随之可关。

wasm 那档以 `--no-default-features` 关掉 `mdsip`（浏览器打不开裸 TCP，`FYL-DESIGN-06` §1
已关死；另有用户裁定 2026-09-02）、`hdf5` / `netcdf`（两个 C 库链不进 wasm）与 `dlopen`。
留下的是：文档模型 · JSON · YAML · g-file · 内容识别 · fyo 语义 · 装配（文件源）· 扁平树
编解码 · 计划合成——正好是浏览器要的那些。

**H-5 wasm 上两个模块由 JS 接线，JS 不当翻译。**〔工作假设〕内核与中间层是两个 wasm 模块
（内核私有、中间层公开，不能互相 `use`），wasm 上没有 `dlopen`。页面实例化两个模块；中间层
建好四段缓冲，JS 把**字节**递给内核模块，再把内核交回的树递回中间层——JS 一个字节都不
需要看懂。这与 F-1 合拍：树本来就是为跨边界传递设计的扁平布局，从一次 C ABI 调用换成两个
wasm 实例的内存之间，性质不变。〔开放猜想〕链成一个 wasm 制品省掉接线，但要在构建期把
私有内核与公开中间层链在一起，发布面与许可面都要重判（G-7）。

(fylite-kernel-contract-deltas)=
# 要改口的既有裁定 (Deltas to Standing Rulings)

| 出处 | 现文 | 改为 | 理由 |
| :--- | :--- | :--- | :--- |
| `FYL-CONOPS-00` / `FYL-SRS-01` 通篇「双宿主」 | Python 与浏览器两个宿主 | **多宿主**：CLI、Python 库、网页、AI 面……数目不承重（H-3） | 用户裁定 2026-09-04；「双」记的是分仓前的两个运行时，不是设计约束。本仓另有 44 处散文沿用旧词，随各文档版本行改 |
| `FYL-SRS-01` NR-ENV-004 | 双宿主**必须**共享同一计算核 | **多宿主必须**共享同一**内核契约**；同一 code 在两个后端上的一致性由登记册记录（K-6） | 「同核」是本地 `.so` 与 wasm 出自同一次编译这一**实现事实**，不是需求 |
| `FYL-SDD-01` DE-COMP-02「双薄面」 | 宿主做装配（数组整形、单位与名字、调用顺序） | 宿主做**计划**；装配是内核 code 的一部分（K-3） | 「装配」里藏着物理（度规、剖面），三份拼法已被量到 |
| `FYL-SDD-01` DE-COMP-01 Interface | C-ABI 导出面 + `ABI_VERSION` | 文档门 + code 表 + 输出声明（K-1 / K-2）；门上是扁平树（F-1）；C-ABI 与 ABI 号降为本地后端内部 | 契约必须与实现分离才可替换 |
| `engine.crosshost` 抬头「单核双宿主」 | 两个构建的一致性 | 任意两个后端的一致性（K-6） | 同上 |

〔已确立〕★**五条已于 2026-09-04 落文本**（同日全书重排）：`FYL-CONOPS-00` v1.0 把
「宿主」与「运行时」分开命名；`FYL-SRS-01` v1.0 改写 HOST 域与 NR-ENV-004，并新立
KERNEL 域 FR-KERNEL-001..004 承载 K-1 / K-2 / K-4 / K-8 / F-1..F-4 / S-1..S-4；
`FYL-SDD-01` v1.0 改 DE-LOG-01 为「一份内核契约、多宿主」、DE-LOG-02 降为本地后端内部，
新增 DE-LOG-11（文档门与扁平树）与 DE-LOG-12（内核无状态）。`engine.crosshost` 抬头那
一句随分期 P1 改。本表留作改口的对照。

(fylite-kernel-contract-plan)=
# 分期：一条总线 (One Ordered Plan)

〔工作假设〕两件事交错着做：`P` 是「内核变成可替换的一层」，`T` 是「门换成双向的树」，
`W` 是「中间层进浏览器」。**两条硬约束**：T-1 必须在 P1 之前（否则七个工具照着一扇要换掉
的门写一遍）；T-1 的读与写必须同期（否则往返闸只验得了一半）。其余可并行。现在这扇门是
能用的，所以新形与旧形并行落地，不是换心脏。

| # | 期 | 做什么 | 判据 |
| ---: | :--- | :--- | :--- |
| 1 | **P0 契约** | code 表 + 输出声明定为唯一接口（K-1 / K-2）写进 SRS / SDD **已落**（FR-KERNEL-001..004 · DE-LOG-11 / -12，2026-09-04）；后端表的形（K-4）定下；与 `SP-REPORT-15` T-0.4 对齐远端 envelope（K-5）；改名（N-1）**已落** | 改口落文本 ✓；`fylite case describe` 的输出即契约的可读形 |
| 2 | **T-1 树的四份实现** | 定扁平树格式（F-1 / F-3）；中间层编码 + 解码、内核阅读器 + 构建器同期落；旧门一字不动 | 往返闸：编码 → 内核走 → 内核建树交回 → 解码 → 与源文档逐叶子比 |
| 3 | **T-2 一个 code 走新门** | 门加一条收树的路，先只接 `transport`（最小） | 同一算例两条门逐位相同 |
| 4 | **W-1 中间层进 wasm** | `fylite_runtime` 的 wasm 目标 + JS 接线（H-4 / H-5）；`geqdsk.js` / `fyo.js` / `session.js` 的职责移交 | 浏览器与本机读同一份 g-file 得同一批数；JS 不再自带 g-file 实现 |
| 5 | **T-3 其余 code 搬门** | 逐个搬；撞名按构造不可能 | 每搬一个，两门对拍一次 |
| 6 | **P1 补 code**〔关键路径〕 | 其余七个装配型工具补成内核 code（`vstab` 先），Python 与页面改走文档门；状态按 S-2 收成 `fylite:state` | `scenario/` 与页面 JS 里 `fylite_rs_*` 归零；十个工具全部声明 `kernel_entry`；crosshost 对十个运行 |
| 7 | **T-4 删旧形** | 删路径形、按 `/` 切尾、内核的 TSV 格式化、中间层的 TSV 解析 | 门只剩一种形状，两个方向都是树 |
| 8 | **P2 后端表** | 三种后端登记；`--kernel` 按名或地址选；`/api/case` 端点 | 同一份计划在三种后端各出一份记录，`environment` 各不相同、`whence` 各追得回 |
| 9 | **P3 中间层 profile** | 跑 SpData conformance 向量；「profile 不含」清单写进 `FYL-DESIGN-14` | 向量全过或逐条说明不含；`FR-CONF-002` 不违 |

★P1 是关键路径：唯一动物理代码的一期，也是量最大的一期（271 个调用点）。P0 · P3 是文本
与门禁，T 系与 W-1 是机械工程，P2 在 P1 之后是加法。

(fylite-kernel-contract-gaps)=
# 缺口与开放项 (Gaps and Open Items)

| 编号 | 缺口 | 状态 |
| :--- | :--- | :--- |
| G-1 | 装配搬进内核后，页面交互（拖滑块重算一栏）的延迟预算是否仍满足 `FYL-CONOPS-00` 的响应包络——一次门调用比一次扁平调用多一次编码 | 开；P1 实测 |
| G-2 | 远端后端的 envelope：复用 `fylite serve` 的 JSON-RPC 与 `DriverRequest`，还是另立 `compute.` 方法族 | 开；随 `SP-REPORT-15` T-0.4 裁定 |
| G-3 | ~~内核不认识装置，而导体几何现算归谁~~ | **已关**（K-8）：装置以整份文档进内核，来路归中间层 |
| G-4 | 两个后端给出不同的数时，登记册记录的纳入类别（V / B / C）怎么定——今天三类都以「外部答案」为对照，后端间对照是第四种 | 开；P2 |
| G-5 | ~~wasm 后端的 code 表怎么自报~~ | **随 W-1 即关**（H-4）：中间层的 wasm 像本机那样问内核要，不再靠生成的 `fyo-interface.js` 冒充运行期查询 |
| G-6 | 中间层与 SpData 重叠语义的对齐代价未量：`$link` 分解、`merge_key`、时间开窗三处各自定义，可能与 SpData 的 `$op` / 标识符语法冲突 | 开；P3 前先量 |
| G-7 | wasm 上两个模块由 JS 接线 vs 链成一个制品——后者省接线但要重判发布面与许可面 | 开；W-1 前定 |
| G-8 | `fylite:state` 的形：一块还是逐 code 一块；跨 code 的状态（`coupled` 里平衡与输运各有）怎么并 | 开；P1 与 S-2 一同定 |

(fylite-kernel-contract-trace)=
# 追溯 (Traceability)

| 本篇裁定 | 上游 | 下游落点 |
| :--- | :--- | :--- |
| K-1 / K-2 | 内核仓 `fyo.rs` 抬头；`FYL-SDD-01` DE-COMP-01 | `FYL-SRS-01`（新 FR：内核接口）· `FYL-SDD-01` DE-COMP-01 Interface |
| K-3 | 用户裁定 2026-09-03；`FYL-SDD-01` DE-COMP-02 Invariant | `FYL-SDD-01` DE-COMP-02 |
| K-4 / K-7 | `FYL-DESIGN-15` R-4（找不到就说、不退化） | 中间层 `kernel.rs`；`engine.provenance` |
| K-5 | `SPM-ADR-111`；`SP-REPORT-15` T-1.6 / T-0.4 | 平台 ADR（协议成员） |
| K-6 | `engine.crosshost`；`FYL-SRS-01` NR-ENV-004 | 公开 V&V 登记册 |
| K-8 | 用户裁定 2026-09-04；内核 `fyo.rs` `@fyo-table DEVICE`；`FYL-DESIGN-14` `from_manifest`；{ref}`fylite-kernel-contract-path-defect` 实测 | 中间层的装置绑定；`scenario/control` · `design` · `analysis` 的搬迁面 |
| F-1..F-4 | 用户裁定 2026-09-04（flat tree · 双向不解析）；内核 `fylite_rs_alloc` / `hand_out` | 内核阅读器 / 构建器；中间层编码器 / 解码器；内核 ABI 参考 `FYL-ABI-01` |
| B-1..B-4 | 用户提问 2026-09-04；`SPM-ADR-111` P-1 / P-2；内核 `ERR_MISSING` / `refuse` | `fylite case describe` / `plan`；门的「只问不算」相 |
| S-1..S-6 | 用户提问 2026-09-04（两次）；内核 `evolve_heat` 的 resume 槽；`engine/replay.py` `allow_version_drift` | `fylite:state` 子树的声明；各宿主的持久化 |
| N-1 | 用户裁定 2026-09-04（两次）；`FYL-SDD-01` DE-COMP-03 / DE-COMP-09 | Cargo 包名、制品名、C 导出前缀、`_environment.json`、`FYL-DESIGN-14` / `-15` 与 `FYL-SDD-01` 布局表 |
| D-1 | SpData SRS FR-CONF-002；`FYL-DESIGN-14` L-1 / L-8 | `FYL-DESIGN-14`（profile 不含清单） |
| H-1..H-3 | 用户裁定 2026-09-04（多宿主）；`FYL-DESIGN-09` / `-10` / `-13` / `-15` | 四个页面设计书的 as-built |
| H-4 / H-5 | 用户裁定 2026-09-04（中间层进 wasm）；`fylite_runtime/Cargo.toml` 抬头；`FYL-DESIGN-06` §1 | `rust/build.sh` 的 wasm 目标；`app/assets/` 的接线与三份职责移交 |
