---
document_id: FYL-DESIGN-16
title: "可替换内核与四层分工 (The Replaceable Kernel and the Four-Layer Split)"
shortname: fylite-kernel-contract
version: "0.4"
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
  change: 'v0.4 N-2（用户裁定 2026-09-04，同日）：中间层再改名 `fylite_engine` → `fylite_runtime`。
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
| 版本 (Version) | v0.4 |
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

〔已确立〕`fylite_rs_fyo` 已经是可替换内核该有的形：code + 按名的设置 + 按 fyo 路径的
输入进，按 fyo 路径的 manifest（字段与偏移）+ 平铺数据出，缓冲区由内核持有、调用方经
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
| 内核 | 完成一个 code：从结构到结构 | 不读文件、不开网络、不认识装置 |
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
取绑定输入——`case.rs` 已做；Python `scenario.cases.plan` 与页面的会话文档合成是
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
| G-3 | 内核不认识装置（目标表「禁止」列），但今天 `device.py` 的导体几何现算（互感、响应行）是 Python 调内核扁平函数完成的——这批是「装配」还是「装置层」，归内核 code 还是留在宿主，需逐个裁 | 开；P1 |
| G-4 | 两个后端给出不同的数时，登记册记录的**纳入类别**（V / B / C）怎么定——今天三类都以「外部答案」为对照，后端间对照是第四种 | 开；P2 |
| G-5 | wasm 后端的 code 表怎么自报：`fyo-interface.js` 是生成物而非运行期查询 | 开；P2 |
| G-6 | 中间层与 SpData 重叠语义的**对齐代价**未量：`$link` 分解、`merge_key`、时间开窗三处各自定义，可能与 SpData 的 `$op` / 标识符语法冲突 | 开；P3 前先量 |

(fylite-kernel-contract-trace)=
# 追溯 (Traceability)

| 本篇裁定 | 上游 | 下游落点 |
| :--- | :--- | :--- |
| K-1 / K-2 | 内核仓 `fyo.rs` 抬头；`FYL-SDD-01` DE-COMP-01 | `FYL-SRS-01`（新 FR：内核接口）· `FYL-SDD-01` DE-COMP-01 Interface |
| K-3 | 用户裁定 2026-09-03；`FYL-SDD-01` DE-COMP-02 Invariant | `FYL-SDD-01` DE-COMP-02 |
| K-4 / K-7 | `FYL-DESIGN-15` R-4（找不到就说、不退化） | 数据层 `kernel.rs`；`engine.provenance` |
| K-5 | `SPM-ADR-111`；`SP-REPORT-15` T-1.6 / T-0.4 | 平台 ADR（协议成员） |
| K-6 | `engine.crosshost`；`FYL-SRS-01` NR-ENV-004 | 公开 V&V 登记册 |
| N-1 · N-2 | 用户裁定 2026-09-04（两次）；`FYL-SDD-01` DE-COMP-03 / DE-COMP-09 | Cargo 包名、制品名、C 导出前缀、`_environment.json`、`FYL-DESIGN-14` / `-15` 与 `FYL-SDD-01` 布局表 |
| D-1 | SpData SRS FR-CONF-002；`FYL-DESIGN-14` L-1 / L-8 | `FYL-DESIGN-14`（profile 不含清单） |
| H-1..H-3 | `FYL-DESIGN-09` / `-10` / `-13` / `-15` | 四个页面设计书的 as-built |
