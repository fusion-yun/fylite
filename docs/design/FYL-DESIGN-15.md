---
document_id: FYL-DESIGN-15
title: "发布形态与统一命令行 (Release Forms and the Unified Command Line)"
shortname: fylite-release-cli
version: "1.2"
date: 2026-09-05
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-05T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v1.2 R-1 / R-3 与构建表按 2026-09-05 两条用户裁定改写（落文在 `FYL-DESIGN-16` H-6 / K-9）：
    内核制品从两种形变成**三种**（静态库进 `fy`、`.so` 进 Python 层、wasm 只进静态站点），
    可执行文件的内嵌树里**一份 wasm 也没有**——装置信息走本进程的 `/api/facts`，算力走
    `/api/kernel` 与链进去的静态库。R-3 原文说「把原生内核接到请求面归 `-16` 的 P2，本篇
    不做」，那句话已被裁定超过：做了，只是走的是逐调用门而不是文档门，理由与代价记在
    H-6。三种形态的差别表因此从「谁伺服」扩到「装置信息与算力各在哪里」。
    · v1.1 命令词由三条改为四条（`FYL-DESIGN-17` E-10 / E-23 / E-24 落地，2026-09-04）：
    `case` 收进 `run`、发现面收进 `list`，于是 `fy` 是 `app` / `data` / `run` / `list`，
    一个词一个动词。R-2 / R-4 / C-5 的枚举随之改写；C-1 补一句**规格与模板的分工**
    （静态语法在 `_cli.json`，场景的参数表在模板——`open_parameters` 是那道缝的声明）；
    as-built 一节按落地重记（`cli/case.rs` 撤除，新增 `cli/run.rs` · `cli/list.rs` ·
    `corpus.rs`，`retired` 表进规格）。裁定的**理由**一条没改：一份规格、一个可执行文件、
    不承载的命令按名拒绝——这次只是被拒绝的那两个词换成了 `case` 与 `data facts`。
    · v1.0 全文整理（用户「优化重写整个设计文档」，2026-09-04）。v0.2 那次「两个薄壳别名
    撤销」的沿革（R-2 / R-4 / R-5 / C-8 里各一段「v0.1 写的是…现在…」）收成现行陈述加
    一句记录；as-built 改标 2026-09-04（可执行文件改名 `fy` 且**不再随轮发**、`rust/build.sh --cli` 已撤、
    `data` 子命令七条含 `fetch`）；发布形态表按 `FYL-DESIGN-16` H-4 补第四个制品
    `fylite_runtime.wasm`（裁定，未建）并注明静态站点的装置描述已是实拷；术语「三个宿主」
    在本篇指**命令行的建出者**（Rust · 浏览器启动参数；2026-09-04 前还有 Python），与 `-16` 的多宿主
    不冲突，写明。缺口表补 W-1 一行。
    · v0.2 只保留一个可执行文件（用户裁定 2026-09-03）：`fylite-data` / `fylite-case`
    撤销，`fylite` 承载全部命令词；`hosts.rust.aliases` 去掉，`--cli` 并入 `--exe`。
    · v0.1 初稿：三种发布形态一份设计（R-1..R-6）；三个宿主的命令行收敛到 `_cli.json`
    （C-1..C-8）。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-release-cli

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-15` |
| 文档名称 (Title) | 发布形态与统一命令行 (Release Forms and the Unified Command Line) |
| 短名 / Slug | `fylite-release-cli` |
| 版本 (Version) | v1.2 |
| 发布日期 (Date of Issue) | 2026-09-05 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性——规范条款已上提 `FYL-SRS-01` FR-TOOL-004 与 `FYL-SDD-01` DE-COMP-03 / -06 / -09) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / packagers / anyone adding a command or a release channel |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-CONOPS-00`（零安装离线可用；宿主与运行时）· `FYL-SRS-01` FR-TOOL-001 / FR-TOOL-004 / NR-ENV-004 · `FYL-SDD-01` DE-COMP-03（执行体）/ DE-COMP-06（声明面）/ DE-COMP-09（中间层）· 内核仓 `FYL-REPORT-05`（发布通道评估：版本同源、alpha 期 pip 只发 Linux x86-64、桌面单文件第四条通道）· `FYL-DESIGN-14`（数据半边与它的命令行 `data`）· `FYL-DESIGN-16`（中间层进 wasm） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 承接 `FYL-REPORT-05` §3b（桌面单文件）与 §6 的裁定；不改动它们 |
:::

(fylite-release-cli-intro)=
# 发布形态与命令行 (Release Forms and the Command Line)

〔一句话〕**三种发布形态，一份源；两份命令行，一个定义文件。**
fylite 以三种形态到达使用者：一个内嵌整个 `app/` 的**单一可执行文件**（`fy`）、
一个**静态网页**（`app/` + wasm 制品，可选地由一个进程伺服而成为**动态**网页）、一个
**Python 包**（wheel）。三者装的是同一份页面、同一份内核制品；命令行——Rust 可执行
文件与浏览器页面的启动参数——从**同一个文件** `python/fylite/_cli.json` 建出，
只属于一个建出者的少数参数在该文件里标出。

★★**2026-09-04 用户裁定：Python 侧没有命令行。** 控制台脚本 `fylite`、`python -m
fylite` 与 `engine/cli.py`（`_cli.json` 上的 argparse 建造者与三条委托）一并撤除，
wheel 装的是一个**库**。规格的第三个读者随之消失，它只属 Python 的十一条命令
（`run` · `plot` · `describe` · `cases` · `manifest` · `replay` · `report` · `whence` ·
`alias` · `serve` · `mcp`）、`hosts.python` 与 `--bin-dir` 也一并从 `_cli.json` 撤出。
那十一条能力**一条没少**——它们从来只是库的薄包装，今天直接调库（对照表在
`docs/guide/cli.md` 末节）；两个 stdio 服务改由 `python -c "from fylite.engine.serve
import mcp_stdio; …"` 起。

〔术语〕本篇说的「宿主」是**命令行的建出者**：Rust 可执行文件与浏览器的启动参数——
与 `FYL-CONOPS-00` v1.0 的四个宿主（命令行 · Python 库 · 浏览器 · AI 面）是两种切法：
AI 面与 Python 库都没有命令行。

〔为什么〕2026-09-02 之前这三样东西各自成立、互不引用：`fylite` 手写了一个四选项的
参数循环，两个数据 / 算例二进制各手写一份 `Args`（同一段代码复制两遍，各带一张
「哪些选项带值」的名单——不在名单上的未知选项被**静默接受**），Python 的 `fylite` 由
`_cli.json` 机械生成（11 条命令），页面从 URL 读 `?device=`，此外没有任何一处说页面
接受什么。本篇把它们写成一处，并把命令行定义收敛到一个文件：**加一条命令是改一个
文件**，每一份命令行同时得到同一份用法。★2026-09-04 之后建出者从三个减到两个
（Python 那一份连同它的十一条命令一起撤除），收敛这件事本身不变。

〔与上游的分工〕`FYL-REPORT-05` 裁定了「发什么、发给谁」（版本同源、alpha 期 pip 只发
Linux x86-64、桌面单文件是第四条通道、内核源保持闭源）；本篇不重开那些裁定，只写
**形态之间的边界**与**命令行的收敛**。

(fylite-release-cli-forms)=
# 三种发布形态 (The Three Release Forms)

:::{table} 三种形态：给谁、里面有什么、计算在哪、请求面在哪。
:name: tbl-fylite-release-forms
:align: left

| 形态 | 给谁 | 装的是什么 | 计算在哪 | 请求面（`/api/*`） | 构建 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **单一可执行文件** `fy`（Linux ELF / Windows PE32+） | 离线的人、没有 Python 的人（尤其 Windows） | 整个 `app/`（内嵌字节，生成表 `src/bin/app/assets.rs`）+ mdsip 只读客户端 + `data` / `run` / `list` 的全部代码 + 九份场景模板（`corpus.rs` 的 `include_str!`） | 页面里的 **wasm**（不是原生内核）；`run` 经 dlopen 用原生内核 | **有**：`/api/health` 恒答；六个只读 mdsip 端点在给了 `--mdsip` 时活 | `tools/build-app-exe.sh` |
| **静态网页**（站点） | 联网的人，零安装 | `app/`（减 `tests/`）+ `assets/fylite_{rs,tglf,dke}.wasm`；装置描述 `app/facts/device/*.jsonld` 是实拷（脚本里那段 `cp -L` 落实体的讲究是符号链接时代留下的，今天无链接可解） | 页面里的 wasm；加载后离线可用 | **无**：页面探 `/api/health` 不通即自禁用装置数据面板 | `tools/build-site.sh` |
| **动态网页** | 本机、或经隧道可达 mdsip 的人 | **同一份 `app/` 字节**，由一个进程伺服 | 页面里的 wasm | **有**：伺服进程答 `/api/*` | `fylite`（= `fylite app`） |
| **Python 包**（wheel，alpha 期 Linux x86-64） | 写脚本的人、LLM 宿主、集成方 | `python/fylite/` + `_lib/libfylite_kernel.so` + `_lib/libfylite_runtime.so` + `_cli.json` 等声明面（**不带**可执行文件，2026-09-04 用户裁定） | 原生内核（ctypes） | `serve`（JSON-RPC stdio）/ `mcp`（MCP stdio）；命令行整层已撤，用 `$PATH` 上的 `fy` | `tools/build-wheel.sh`（内核制品由内核仓 `rust/build.sh` 装入） |
:::

〔评注〕「静态」与「动态」不是两套页面：它们是**同一份字节的两种伺服方式**。区别只在有
没有一个进程站在页面后面答 `/api/*`，而页面用**端点是否回答**（不是主机名）判别
（`assets/host.js`）。所以动态网页没有自己的构建：`fylite` 就是它。

〔裁定，未建〕**第四个制品 `fylite_runtime.wasm`**（`FYL-DESIGN-16` H-4，用户裁定
2026-09-04）：中间层也进浏览器，由 JS 调用，`--no-default-features`（无 mdsip / hdf5 /
netcdf）。它落地后静态网页装的是四个 wasm，`geqdsk.js` / `fyo.js` / `session.js` 的职责
归它；构建脚本与它的门禁归 `-16` 分期 W-1，本篇的表到时补一列。

## 裁定 R-1..R-6 (Rulings on release forms)

**R-1 三形态一份源。** 三种形态装的是同一份 `app/`、同一版内核制品（`.a` / `.so` /
`.wasm` 出自同一个 `c_api.rs`，`FYL-SDD-01` DE-LOG-01）、同一份 `_cli.json`。一个形态**禁止
(MUST NOT)** 带另一个形态没有的页面或参数名；不同之处只能是**运行时**判别的
（`host.js` 的 `data-fy-host`），不能是构建时分叉的页面。

★★**「同一版内核制品」自 2026-09-05 起是三种形，不是两种**（用户裁定，`FYL-DESIGN-16` K-9）：
静态库进 `fy`、`.so` 进 Python 层、wasm 只进静态站点。三者出自同一次构建，所以这条裁定
不受影响——变的是**每种形态带哪一份**，以及随之而来的一件更要紧的事：一次发行里同一批
物理**只有一个实现路径**在跑（此前可执行文件里有两个：内嵌页面的 wasm 与进程自己的原生
内核）。哪几个字节进哪个形态，见 K-9 的表。

**R-2 只有一个可执行文件，它是 Rust 宿主的全部命令行。** `fylite` 不带子命令即
`app`（起服务、开浏览器——双击仍可用）；`fy data …` 搬数据、`fy run …` 算一个算例、
`fy list …` 看有什么可用。★2026-09-04 第二次收敛（`FYL-DESIGN-17`）：`case` 收进
`run`（位置参数既收线与场景，也收计划文件），`data facts` 收进 `list facts`——两个词
指同一件事时，撤掉的那个**按名拒绝并指出去处**，不静默转发。★2026-09-03 用户裁定：此前的两个薄壳别名二进制（各十行，只把
命令词前置到 argv）撤销——那一次前置由调用方给即可，撤掉之后少两个二进制、少两条
`_bin/` 项、少一处用法里的字符串折回，**能力一条没少**。

**R-3 静态即无服务端组件；动态即同一份字节被一个进程伺服。** 静态站点的构建只做三件事：
取 `app/` 的发布子集（去 `tests/`）、核对装置描述在、核对三个 wasm 在。动态网页由 `fy`（`fy app`）伺服，并答 `/api/*`；
请求面**只绑回环**、只读、无表达式端点（`FYL-REPORT-05` §3b.5 与 `api.rs` 抬头）。

★★**这一条 2026-09-05 由两条用户裁定改写了一半**（`FYL-DESIGN-16` H-6 / K-9）：把原生内核
接到请求面这件事**已经做了**，只是走的不是当初设想的 `/api/case`（文档门），而是
`/api/kernel`（逐调用门）——因为页面今天真有的是 140 处细粒度调用点，等它们改写成计划
等于让裁定等一个季度。于是三种形态的差别不再只是「谁伺服」，还包括**算力在哪里**：

| 形态 | 装置信息 | 算力 | 请求面 |
| :--- | :--- | :--- | :--- |
| 静态网页 | 中间层 wasm 里的 `facts.rs` | **页内内核 wasm**（唯一还需要 wasm 的宿主） | 无 |
| 单一可执行文件 / 动态网页 | 本进程的 `/api/facts` | **本进程**（内核静态库链在里面），页面经 `/api/kernel` | `/api/*`，只绑回环 |
| Python 包 | `.so` 里的同一张表 | `dlopen` 的 `.so` | 无 |

「只绑回环、只读」没有松：`/api/kernel` 是这台机器上唯一的 POST，读完请求体当参数用，
一个字节也不落盘；服务器依旧没有写入面、没有目录列表。

**R-4 命令行只有一条，它是那个可执行文件。** `fy` 承载规格里的每一条命令
（`app` / `data` / `run` / `list`）；无命令词时跑 `app`，所以双击可用。Python 包**不是**
第二份命令行：它是库，没有控制台脚本，也不再把命令词转交给谁。

★★**沿革（三次改名与两条裁定，值得留着）。** 二进制先叫 `fylite-app`，2026-09-04
先改叫 `fylite`——与本包装的控制台脚本**同名**，于是 `$PATH` 那一步会找到**我们
自己**，`fylite data …` 委托给 `fylite data …`，一层层 fork 到进程表满（没有报错，
只有机器变慢）；`engine/cli.py` 为此长出一段「读文件头判断这是不是我自己」的守卫。
同日两条裁定把这类失败方式从源头去掉：**改名 `fy`**（名字不同，找不到自己）、
**Python 侧不产出可执行文件也不再有命令行**（没有委托，也就没有查找次序）。
世上只有一份二进制，在 `rust/fylite_runtime/target/release/fy`，把它装到 `$PATH`
上是**发行**的事，不是 `pip install` 的事。

**R-5 版本同源与制品不入库，照旧。** `VERSION` 是发行版本的唯一来源；`.so` / `.wasm`
不进 git，打包时装入（`FYL-REPORT-05` §6.1、本仓 `.gitignore` 抬头）。
`package-data` **没有** `_bin/` 项：轮里带 `.so` 与声明面，不带可执行文件（R-4）。

**R-6 每个形态一条构建命令，产物与门禁在表里。** 见 {numref}`tbl-fylite-release-build`。
构建脚本**不生成**规格的副本——命令行直接读 `_cli.json`（编译期 `include_str!`、
门禁核对页面读的名字），所以没有第二份需要同步的东西。

:::{table} 构建路径与门禁（2026-09-04 as-built）。
:name: tbl-fylite-release-build
:align: left

| 形态 | 命令 | 产物 | 门禁 |
| :--- | :--- | :--- | :--- |
| 单一可执行文件 | `bash tools/build-app-exe.sh --mode cli\|web\|full [linux\|windows\|both]` | `rust/fylite_runtime/target/release/fy`、`…/x86_64-pc-windows-{gnu,msvc}/release/fy.exe`。**内嵌树里一份 wasm 也没有**（2026-09-05）：装置信息与算力都是本进程的 | `app/tests/validate-embed.mjs`（资源表与 `app/` 同步）；`validate-kernel-api.mjs`（两条算力路逐位比对）；二进制自带测试（首页、wasm MIME、穿越、活目录穿越、启动 URL） |
| 静态网页 | `bash tools/build-site.sh [--internal\|--public] [输出目录]` | `dist/site/`（实测 10 MB）：`app/` 发布子集 + 三个 wasm——两个内核（算力）加 `fylite_facts.wasm`（装置信息，0.43 MB，**进预缓存**）。中间层的全套 `fylite_runtime.wasm` 暂不发：页面没有读者 | 脚本自检：三个 wasm 在、全套那一份**不在**、无 `tests/`、无悬空符号链接；`validate-site.mjs` · `validate-offline.mjs`（断网后逃逸请求为 0） |
| 动态网页 | `fy [--port N] [--mdsip HOST:PORT] …`（= `fy app …`） | 运行中的进程 | `app/tests/validate-app-mdsip.mjs --exe <fy>` |
| Python 包 | `bash rust/build.sh --exe`（中间层 `.so`；`fy` 留在 `target/release/`，**不进轮**；`--cli` 已撤，给它会被按名拒绝并指向 `--exe`）→ 内核仓 `rust/build.sh`（内核 `.so`、生成物）→ `bash tools/build-wheel.sh` | `python/dist/fylite-<ver>-py3-none-manylinux_x_y_x86_64.whl` | `test_bundled_artifacts.py`（ABI 一致、制品不入库）；`test_cli_spec.py` |
:::

(fylite-release-cli-spec)=
# 统一命令行：一个定义文件 (One Definition File for Three Builders)

〔一句话〕`python/fylite/_cli.json`（`spec_version: 2`）定义每一条命令、每一个参数、每一句
帮助；Rust 宿主在**编译期**把它
纳入（`rust/fylite_runtime/src/cli/mod.rs` 的 `include_str!`）并由它建自己的解析器与用法，
浏览器的**启动参数**是它的 `hosts.app.params`。

## 文件的形状 (The shape of the file)

:::{table} `_cli.json` v2 的键。未列出的参数键（`type` `action` `nargs` `default` `metavar` `dest` `const` `choices` `required`）沿 argparse 的含义，Rust 解析器实现其子集并对不识别的组合按名拒绝。
:name: tbl-fylite-cli-schema
:align: left

| 键 | 在哪 | 含义 |
| :--- | :--- | :--- |
| `spec_version` | 顶层 | `2`：带 `hosts` 与嵌套命令的版本；v1 的文件（无 `hosts`）读作「全部只属 Python」 |
| `prog` / `description` | 顶层 | 命令族的名字与一段话 |
| `hosts.python.exe` · `hosts.rust.exe` · `hosts.app.entry` | 顶层 | 三个建出者各叫什么、从哪进 |
| `hosts.rust.default_command` | 顶层 | Rust 可执行文件无命令词时运行的命令（`app`） |
| `hosts.app.params[]` | 顶层 | 浏览器启动参数：`name` · `carrier`（`query` 写进 `?name=`；`path` 决定页面）· `choices` · `help` |
| `commands[].hosts` | 命令 | 承载它的建出者；**缺省 = 全部** |
| `commands[].commands[]` | 命令 | 子命令（组）：`data` / `list` |
| `commands[].handler` | 命令 | Python 的处理函数（`module:function`）；Rust 按命令名分派，不读它 |
| `args[].hosts` | 参数 | 只属一个建出者的参数（`--bin-dir` 属 python，`--app-dir` 属 rust） |
| `args[].app_param` | 参数 | 这个选项写入 URL 的启动参数名（`--device` → `device`） |
:::

## 裁定 C-1..C-8 (Rulings on the command line)

**C-1 一个文件，以及它的边界。** 命令、参数、帮助只写在 `_cli.json`；任何建出者的代码里**禁止 (MUST
NOT)** 再出现一张「选项名单」（这正是 2026-09-02 之前两份 Rust `Args` 里那张 `takes_value`
名单）。Rust 由它建解析器与用法（`cli::parse` / `cli::usage`）；页面读的启动参数名由它
声明、由门禁核对。★第三个建出者（Python 的 argparse）随 2026-09-04 的裁定撤除。

★★**边界在哪：这份文件管语法，不管场景的参数表。** `fy run` 后面的
`chi0=0.4` / `--only-magnetic` 是**场景的**参数（`FYL-DESIGN-17` E-11），逐 code 几十到
上百个，且随语料增删——把它们抄进本文件，规格与模板就是两份，而先发现两份不一样的是
敲错了名字的那个人。所以本文件只声明**「这条命令后面有一张开放的表」**（`open_parameters`），
解析器据此把不认识的记号收起来而不是拒绝，由 `run.rs` 拿着模板按名拒绝。一条没有这个
声明的命令，行为与从前逐字相同。同理，撤掉的命令词写在 `retired` 里而不是写在代码里
的一个 `match` 分支上。

**C-2 少量特有参数用 `hosts` 标出，不用代码分支。** 命令级 `hosts` 说谁承载；参数级
`hosts` 说谁接受。缺省是全部。★2026-09-04 之后只剩两处特有：`--app-dir`（rust：伺服
一棵活目录，开发用）与 `hosts.app.params`（浏览器：`device` `lang` `theme` `page`）——
`--bin-dir`（从前 python 专有：那个可执行文件在哪）随委托一起撤除。一个不承载某参数的
建出者对它**按名拒绝**，不是静默吃掉。

**C-3 不承载的命令按名拒绝。** ★本条的另一半（Python 承载全部命令、其中三条逐字
委托）随 2026-09-04 的裁定撤除：规格里今天只剩 `fy` 承载的三条，`_cli.json` 不再
描述任何一个别处实现的命令。`fy` 对不认识的命令词按名拒绝，**不**试图用另一套
实现回答。

**C-4 帮助与拒绝由规格生成。** `--help` 是 `cli::usage` 从规格排出来的（概要行 +
一句话 + 子命令表 + 参数表），程序名取自规格的 `hosts.rust.exe`（今天是 `fy`），
不写死在 `main.rs` 里。未知选项、缺参数、类型不符、不在 `choices` 里、`required`
缺席——都按名拒绝，退出码 2。

**C-5 嵌套命令与组级选项。** `data` / `list` 是组；组自己的参数对每个子命令有效，且
**写在子命令之前或之后都可以**：解析器对祖先的参数不分位置。

**C-6 浏览器的启动参数定义一次。** `hosts.app.params` 是页面从 URL 接受什么的唯一声明；
`fylite app --<name>` 把它们写进打开的 URL（`--page` 决定路径，其余进查询串）；页面侧
`devices.js` 读 `device`、`i18n.js` 读 `lang`、`theme.js` 读 `theme`。门禁 `test_cli_spec.py`
核对：每个声明的 `query` 参数在 `app/assets/` 里恰有读者，且页面不读未声明的名字；
`app` 命令的每个 `app_param` 指向一个已声明的参数，反之亦然（Rust 单元测试同此）。
★同一道门禁今天还核一件事：规格里**没有**第三个宿主的残留（`hosts.python`、只属它的
命令、`--bin-dir`）。

**C-7 Rust 宿主的缺省命令是 `app`。** `fylite` 与 `fy --port 8123` 都是 `app`
（第一个词是选项即取缺省命令）；这是双击可用的条件，写在规格里
（`hosts.rust.default_command`）而不是代码里。

**C-8 一个可执行文件，命令词由调用方给。** `[[bin]]` 只有 `fylite` 一个，规格里没有
`hosts.rust.aliases`，Python 侧的委托表是一个名字加一次前置；用法里没有需要折回的字符串
——`fylite data --help` 打的就是它自己的名字。★v0.1 的 C-8 是「别名二进制是薄壳」，
2026-09-03 用户裁定改为本条（理由见 R-2）。

(fylite-release-cli-asbuilt)=
# as-built（2026-09-04）

- **规格**：`python/fylite/_cli.json` v2——11 条 Python 命令（`run` `plot` `describe` `cases`
  `manifest` `replay` `report` `whence` `alias` `serve` `mcp`，`hosts: ["python"]`）；
  `app`（`--port` `--no-open` `--mdsip` `--mds-user` `--page` `--device` `--lang` `--theme`；
  `--app-dir` 属 rust、`--bin-dir` 属 python）、`data`（`info` `dump` `convert` `merge`
  `assemble` `fetch` `tables`）、`run`（开放参数表）、`list`（`devices` `experiments`
  `scenarios` `presets` `facts` `kernel` `lines`）——这几组的参数
  从两个二进制的手写用法**逐条**转录，两处冲突改名：`info` / `dump` 的位置参数叫 `file`。
- **Rust**：`rust/fylite_runtime/src/cli/mod.rs`（规格驱动解析器：命令树下降、`--k=v`、
  短选项、`--` 结束选项、`append`、位置参数按 `nargs` 绑定、`required` / `choices` /
  类型检查、用法生成、开放参数收集、退役词按名拒绝）；`cli/data.rs` · `cli/run.rs` ·
  `cli/list.rs`（`cli/case.rs` 于 2026-09-04 撤除，其四个处理器分别并入后两者）；
  `src/bin/app/main.rs` 用解析器分派 `app` / `data` / `run` / `list`，`app` 带
  `--page/--device/--lang/--theme`（拼成启动 URL）
  与 `--app-dir`（活目录，同一张 MIME 表，仍拒绝 `..`）。`Cargo.toml` 只有一个 `[[bin]]`。
- **Python**：★**没有了**（2026-09-04）。`engine/cli.py`、`__main__.py` 与
  `[project.scripts]` 一并撤除；`pyproject.toml` 的 `package-data` 既无 `_bin/` 项，
  也不再带 `_cli.json`——包里没有读它的东西。
- **浏览器**：`assets/i18n.js` 的 `initial()` 先读 `?lang=`（并记住）；`assets/theme.js`
  在 `apply(stored())` 之前读 `?theme=`（`light` / `dark` 记住，`system` 清除）；
  `?device=` 原已在。
- **门禁**：`test_cli_spec.py`（两个宿主；命令表恰是 `fy` 的三条；`prog` = `hosts.rust.exe`；
  `hosts.app.params` ↔ 页面读者 ↔ `app_param`；规格里没有 python 残留）；Rust `cargo test --lib cli::`
  与 `--bin fy`。
- **规范落点**：FR-TOOL-004（`FYL-SRS-01`）、DE-COMP-03 / -06 / -09（`FYL-SDD-01`）——
  本篇的规范条款已上提，本篇留作理由与 as-built。

(fylite-release-cli-gaps)=
# 缺口与后续 (Gaps and residuals)

| # | 事项 | 关闭判据 |
| :--- | :--- | :--- |
| 1 | 原生内核经请求面（页面走 HTTP 而不是 wasm）——已归 `FYL-DESIGN-16` K-4 / H-2 的远端后端 `/api/case`（分期 P2） | 那一篇的判据 |
| 2 | 站点发布 CI：`publish-app.yml` 随仓拆分后不在本仓；`tools/build-site.sh` 只出目录 | 一条 workflow 跑它并发布 |
| 3 | Windows 侧未实机验证（`FYL-REPORT-05` §3b.4 照录） | Windows 上双击运行、页面加载、数值与 Linux 逐位相同 |
| 4 | `serve` / `mcp` 无参数（stdio 固定）；`run` 的文档仍写 EFIT 时代的一句 | 文档按规格重生成（guide / reference 的 CLI 节） |
| 5 | Rust 解析器实现的是 argparse 的**子集**（无 `const`、无 `dest`、`nargs='?'` 只对选项）；规格里用了子集之外的键而又标给 rust 的参数会被静默照录 | 规格门禁：标给 rust 的参数只用子集内的键 |
| 6 | `--app-dir` 没有目录列表也不跟随符号链接之外的东西；只为开发 | 保持 |
| 7 | `fylite_runtime.wasm` 无构建脚本（`FYL-DESIGN-16` H-4 / W-1） | `rust/build.sh` 出 wasm 目标；静态站点带四个 wasm；JS 接线闸子 |
