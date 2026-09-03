---
document_id: FYL-DESIGN-15
title: "发布形态与统一命令行 (Release Forms and the Unified Command Line)"
shortname: fylite-release-cli
version: "0.2"
date: 2026-09-03
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-03T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.2 只保留一个可执行文件（用户裁定）：`fylite-data` / `fylite-case` 两个薄壳
    别名二进制撤销，`fylite-app` 成为本仓唯一的可执行文件并承载全部命令词。它们各十行、
    做的就是把命令词前置——而那一次前置由调用方给即可（Python 宿主委托时前置，人在命令行上
    直接写 `fylite data …`）。随之：R-2 / R-4 / R-5 改写，C-8 从「别名是薄壳」改为
    「一个可执行文件」，`hosts.rust.aliases` 从规格里去掉，`rust/build.sh --cli` 撤销
    （并入 `--exe`，给 `--cli` 按名拒绝并指向 `--exe`）。
    v0.1 初稿：把三种发布形态（单一可执行文件 · 静态/动态网页 · Python 包）写成一份设计，
    并把三个宿主（Rust / Python / 浏览器）的命令行收敛到**同一个定义文件**
    `python/fylite/_cli.json`——Python 的 argparse、Rust 的解析器与浏览器的启动参数
    都由它建出，只属于一个宿主的少数参数在文件里标 `hosts`。裁定 R-1..R-6、C-1..C-8。
    as-built：`rust/fylite_engine/src/cli/`（规格驱动解析器 + `data` / `case` 主体）、
    `fylite-app` 成为 Rust 侧唯一命令行（`app` 缺省、`data` / `case` 子命令、
    `--page/--device/--lang/--theme/--app-dir`），`fylite-data` / `fylite-case` 退为薄壳；
    Python 侧 `fylite app / data / case` 逐字委托；页面读 `?lang=` `?theme=`。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-release-cli

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-15` |
| 文档名称 (Title) | 发布形态与统一命令行 (Release Forms and the Unified Command Line) |
| 短名 / Slug | `fylite-release-cli` |
| 版本 (Version) | v0.2 |
| 发布日期 (Date of Issue) | 2026-09-02 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite maintainers / packagers / anyone adding a command or a release channel |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-CONOPS-00`（双宿主、零安装离线可用）· `FYL-SRS-01` FR-TOOL-001（命令行入口）/ NR-ENV-004（双宿主同核）· `FYL-SDD-01` DE-COMP-03（机械核）/ DE-COMP-06（声明面：`_cli.json` 是数据非代码）· 内核仓 `FYL-REPORT-05`（发布通道评估与裁定：版本同源、alpha 期 pip 只发 Linux x86-64、桌面单文件第四条通道）· `FYL-DESIGN-14`（数据层与它的命令行 `data`） |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 承接 `FYL-REPORT-05` §3b（桌面单文件）与 §6 的裁定；不改动它们 |
:::

(fylite-release-cli-intro)=
# 发布形态与命令行 (Release Forms and the Command Line)

〔一句话〕**三种发布形态，一份源；三个宿主的命令行，一个定义文件。**
fylite 以三种形态到达使用者：一个内嵌整个 `app/` 的**单一可执行文件**（`fylite-app`）、
一个**静态网页**（`app/` + 三个 wasm，可选地由一个进程伺服而成为**动态**网页）、一个
**Python 包**（wheel）。三者装的是同一份页面、同一份内核制品；它们的命令行——
Rust 可执行文件、Python 的 `fylite`、浏览器页面的启动参数——从**同一个文件**
`python/fylite/_cli.json` 建出，只属于一个宿主的少数参数在该文件里标出，而不是在代码里各自记一份。

〔为什么〕2026-09-02 之前这三样东西各自成立、互不引用：`fylite-app` 手写了一个四选项的
参数循环，`fylite-data` 与 `fylite-case` 各手写一份 `Args`（**同一段代码复制两遍**，各带一张
"哪些选项带值"的名单——不在名单上的未知选项被**静默接受**），Python 的 `fylite` 由
`_cli.json` 机械生成（11 条命令），页面从 URL 读 `?device=`，此外没有任何一处说页面接受什么。
发布形态则散在三个脚本与一份内核仓报告里。本篇把它们写成一处，并把命令行定义收敛到一个文件：
**加一条命令是改一个文件**，三个宿主同时得到同一份用法。

〔与上游的分工〕`FYL-REPORT-05` 裁定了"发什么、发给谁"（版本同源、alpha 期 pip 只发
Linux x86-64、桌面单文件是第四条通道、Rust 源保持闭源）；本篇不重开那些裁定，只写**形态之间的边界**
与**命令行的收敛**。`FYL-SDD-01` DE-COMP-06 已把 `_cli.json` 列为声明面（数据非代码，随 wheel 分发）；
本篇让另外两个宿主也读它。

(fylite-release-cli-forms)=
# 三种发布形态 (The Three Release Forms)

:::{table} 三种形态：给谁、里面有什么、计算在哪、请求面在哪。
:name: tbl-fylite-release-forms
:align: left

| 形态 | 给谁 | 装的是什么 | 计算在哪 | 请求面（`/api/*`） | 构建 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **单一可执行文件** `fylite-app`（Linux ELF / Windows PE32+） | 离线的人、没有 Python 的人（尤其 Windows） | 整个 `app/`（内嵌字节，生成表 `src/bin/app/assets.rs`）+ mdsip 只读客户端 + `data` / `case` 的全部代码 | 页面里的 **wasm**（不是原生内核）；`case` 子命令经 dlopen 用原生内核 | **有**：`/api/health` 恒答；六个只读 mdsip 端点在给了 `--mdsip` 时活 | `tools/build-app-exe.sh` |
| **静态网页**（站点） | 联网的人，零安装 | `app/`（减 `tests/`）+ `assets/fylite_{rs,tglf,dke}.wasm`；装置牌 `cp -L` 落实体 | 页面里的 wasm；加载后离线可用 | **无**：页面探 `/api/health` 不通即自禁用装置数据面板 | `tools/build-site.sh` |
| **动态网页** | 本机、或经隧道可达 mdsip 的人 | **同一份 `app/` 字节**，由一个进程伺服 | 页面里的 wasm | **有**：伺服进程答 `/api/*` | `fylite-app`（= `fylite app`） |
| **Python 包**（wheel，alpha 期 Linux x86-64） | 写脚本的人、LLM 宿主、集成方 | `python/fylite/` + `_lib/libfylite_kernel.so` + `_lib/libfylite_engine.so` + `_cli.json` 等声明面 + `_bin/fylite-app`（**一个**可执行文件，构建时在则带） | 原生内核（ctypes） | `serve`（JSON-RPC stdio）/ `mcp`（MCP stdio）；`app` 委托可执行文件 | `tools/build-wheel.sh`（内核制品由内核仓 `rust/build.sh` 装入） |
:::

〔评注〕"静态"与"动态"不是两套页面：它们是**同一份字节的两种伺服方式**。区别只在有没有一个
进程站在页面后面答 `/api/*`，而页面用**端点是否回答**（不是主机名）判别（`assets/host.js`）。
所以动态网页没有自己的构建：`fylite-app` 就是它。

## 裁定 R-1..R-6 (Rulings on release forms)

**R-1 三形态一份源。** 三种形态装的是同一份 `app/`、同一版内核制品（`.so` 与 `.wasm` 出自同一个
`c_api.rs`，`FYL-SDD-01` DE-LOG-01）、同一份 `_cli.json`。一个形态**禁止 (MUST NOT)** 带另一个
形态没有的页面或参数名；不同之处只能是**运行时**判别的（`host.js` 的 `data-fy-host`），不能是构建时
分叉的页面。

**R-2 只有一个可执行文件，它是 Rust 宿主的全部命令行。** `fylite-app` 不带子命令即 `app`
（起服务、开浏览器——双击仍可用）；`fylite-app data …` 与 `fylite-app case …` 就是从前的
`fylite-data` / `fylite-case`。★★v0.2（2026-09-03，用户裁定）：那两个二进制**已撤销**。
v0.1 把它们保留为薄壳，理由是 `rust/build.sh --cli` 把它们装进 `_bin/`、脚本按名调用——
但那条理由是**自己造出来的**：薄壳各十行，做的就是把命令词前置到 argv，而调用方本来就要
写出那个词（`fylite data …`）或已经在前置它（Python 宿主的委托）。撤掉之后少两个二进制、
少两条 `_bin/` 项、少一处「用法里 `fylite-data data` 折回 `fylite-data`」的字符串替换，
**能力一条没少**。

**R-3 静态即无服务端组件；动态即同一份字节被一个进程伺服。** 静态站点的构建只做三件事：取 `app/`
的发布子集（去 `tests/`）、把装置牌符号链接落成实体、核对三个 wasm 在。动态网页由 `fylite-app`
（或 wheel 里的 `fylite app`，它委托同一个可执行文件）伺服，并答 `/api/*`；请求面**只绑回环**、
只读、无表达式端点（`FYL-REPORT-05` §3b.5 与 `api.rs` 抬头）。把原生内核接到请求面（页面改走
HTTP 而不是 wasm）仍是下一步，本篇不做。

**R-4 wheel 承载全部命令，原生的三条委托。** Python 的 `fylite` 列出规格里的每一条命令；`app` /
`data` / `case` 不在 Python 里重写，而是把命令词**逐字**交给 `_bin/` 里的可执行文件：
**把命令词放回最前面**，其余的字原样交过去（查找次序 `--bin-dir` → 包内 `_bin/` → `$PATH`）。
★v0.2 起这条查找只认一个名字 `fylite-app`；v0.1 里它是每条命令一份候选**列表**（先试别名
二进制，再退回 `fylite-app` 并前置命令词），而那个「退回」分支才是全部实现——别名是多余的那半。
★命令词**总是**前置，`app` 也不例外：那个可执行文件无词时的缺省是 `app`，省掉词就意味着
`fylite data convert` 会静默地起一个网页服务而不是转换文件。找不到可执行文件时按名说明
要构建什么，退出码 2——**不**退化成一个能力更少的 Python 实现。`_bin/*` 在 `package-data` 里，
构建时在就随轮走。

**R-5 版本同源与制品不入库，照旧。** `VERSION` 是发行版本的唯一来源；`.so` / `.wasm` /
`_bin/*` 不进 git，打包时装入（`FYL-REPORT-05` §6.1、公开仓 `.gitignore` 抬头）。本篇新增的
`_bin/` 项（v0.1 三项，v0.2 起**一项** `_bin/fylite-app`）同此规矩。

**R-6 每个形态一条构建命令，产物与门禁在表里。** 见 {numref}`tbl-fylite-release-build`。
构建脚本**不生成**规格的副本——三个宿主都直接读 `_cli.json`（编译期 `include_str!`、
运行期 `json.loads`、门禁核对页面读的名字），所以没有第四份需要同步的东西。

:::{table} 构建路径与门禁（2026-09-02 as-built）。
:name: tbl-fylite-release-build
:align: left

| 形态 | 命令 | 产物 | 门禁 |
| :--- | :--- | :--- | :--- |
| 单一可执行文件 | `bash tools/build-app-exe.sh [linux\|windows\|windows-msvc\|both]`（先跑 `node tools/make-app-embed.mjs`） | `rust/fylite_engine/target/release/fylite-app`、`…/x86_64-pc-windows-{gnu,msvc}/release/fylite-app.exe` | `app/tests/validate-embed.mjs`（资源表与 `app/` 同步）；二进制自带测试（首页、wasm MIME、穿越、活目录穿越、启动 URL） |
| 静态网页 | `bash tools/build-site.sh [输出目录]` | `dist/site/`：`app/` 发布子集 + 三个 wasm + 落实体的装置牌 | 脚本自检：三个 wasm 在、无 `tests/`、无悬空符号链接 |
| 动态网页 | `fylite-app [--port N] [--mdsip HOST:PORT] …` 或 `fylite app …` | 运行中的进程 | `app/tests/validate-app-mdsip.mjs --exe <fylite-app>` |
| Python 包 | `bash rust/build.sh --exe`（数据层 `.so` + `_bin/fylite-app`；★v0.2 起 `--cli` 已撤，给它会被按名拒绝并指向 `--exe`）→ 内核仓 `rust/build.sh`（内核 `.so`、生成物）→ `bash tools/build-wheel.sh` | `python/dist/fylite-<ver>-py3-none-manylinux_x_y_x86_64.whl` | `test_bundled_artifacts.py`（ABI 一致、制品不入库）；`test_cli_spec.py` |
:::

(fylite-release-cli-spec)=
# 统一命令行：一个定义文件 (One Definition File for Three Hosts)

〔一句话〕`python/fylite/_cli.json`（`spec_version: 2`）定义每一条命令、每一个参数、每一句帮助；
Python 的 argparse 由它**机械生成**（`engine/cli.py`），Rust 宿主在**编译期**把它纳入
（`rust/fylite_engine/src/cli/mod.rs` 的 `include_str!`）并由它建自己的解析器与用法，浏览器的
**启动参数**是它的 `hosts.app.params`。

## 文件的形状 (The shape of the file)

:::{table} `_cli.json` v2 的键。未列出的参数键（`type` `action` `nargs` `default` `metavar` `dest` `const` `choices` `required`）沿 argparse 的含义，Rust 解析器实现其子集并对不识别的组合按名拒绝。
:name: tbl-fylite-cli-schema
:align: left

| 键 | 在哪 | 含义 |
| :--- | :--- | :--- |
| `spec_version` | 顶层 | `2`：带 `hosts` 与嵌套命令的版本；v1 的文件（无 `hosts`）读作"全部只属 Python" |
| `prog` / `description` | 顶层 | 命令族的名字与一段话 |
| `hosts.python.exe` · `hosts.rust.exe` · `hosts.app.entry` | 顶层 | 三个宿主各叫什么、从哪进 |
| `hosts.rust.default_command` | 顶层 | Rust 可执行文件无命令词时运行的命令（`app`） |
| `hosts.app.params[]` | 顶层 | 浏览器启动参数：`name` · `carrier`（`query` 写进 `?name=`；`path` 决定页面）· `choices` · `help` |
| `commands[].hosts` | 命令 | 承载它的宿主；**缺省 = 全部** |
| `commands[].commands[]` | 命令 | 子命令（组）：`data` / `case` |
| `commands[].handler` | 命令 | Python 的处理函数（`module:function`）；Rust 按命令名分派，不读它 |
| `args[].hosts` | 参数 | 只属一个宿主的参数（`--bin-dir` 属 python，`--app-dir` 属 rust） |
| `args[].app_param` | 参数 | 这个选项写入 URL 的启动参数名（`--device` → `device`） |
:::

## 裁定 C-1..C-8 (Rulings on the command line)

**C-1 一个文件。** 命令、参数、帮助只写在 `_cli.json`；任何宿主的代码里**禁止 (MUST NOT)**
再出现一张"选项名单"（这正是 2026-09-02 之前两份 Rust `Args` 里那张 `takes_value` 名单）。
Python 由它建 argparse；Rust 由它建解析器与用法（`cli::parse` / `cli::usage`）；页面读的启动参数名
由它声明、由门禁核对。

**C-2 少量特有参数用 `hosts` 标出，不用代码分支。** 命令级 `hosts` 说谁承载；参数级 `hosts`
说谁接受。缺省是全部。截至本版只有三处特有：`--bin-dir`（python：可执行文件在哪）、
`--app-dir`（rust：伺服一棵活目录，开发用）、以及 `hosts.app.params`（浏览器：`device` `lang`
`theme` `page`）。一个不承载某参数的宿主对它**按名拒绝**（Rust：`unknown option "--bin-dir"`），
不是静默吃掉。

**C-3 不承载的命令要么委托要么按名拒绝。** Python 承载全部命令，其中 `app` / `data` / `case`
逐字委托给 Rust 可执行文件（R-4）；Rust 只承载这三条，对 `fylite-app run …` 答"命令不归本程序"。
两个方向都**不**试图用另一套实现回答。

**C-4 帮助与拒绝由规格生成。** Rust 的 `--help` 是 `cli::usage` 从规格排出来的（概要行 + 一句话 +
子命令表 + 参数表），argparse 的是它自己的排版；**内容**同源，措辞可以不同。未知选项、缺参数、
类型不符、不在 `choices` 里、`required` 缺席——两侧都按名拒绝，退出码 2。

**C-5 嵌套命令与组级选项。** `data` / `case` 是组；组自己的参数对每个子命令有效，且**写在子命令之前
或之后都可以**：Rust 解析器对祖先的参数不分位置，argparse 侧把组的参数再声明到每个子命令上，
两侧同一规则。

**C-6 浏览器的启动参数定义一次。** `hosts.app.params` 是页面从 URL 接受什么的唯一声明；
`fylite app --<name>` 把它们写进打开的 URL（`--page` 决定路径，其余进查询串）；页面侧
`devices.js` 读 `device`、`i18n.js` 读 `lang`、`theme.js` 读 `theme`。门禁 `test_cli_spec.py`
核对：每个声明的 `query` 参数在 `app/assets/` 里恰有读者，且页面不读未声明的名字；
`app` 命令的每个 `app_param` 指向一个已声明的参数，反之亦然（Rust 单元测试同此）。

**C-7 Rust 宿主的缺省命令是 `app`。** `fylite-app` 与 `fylite-app --port 8123` 都是 `app`
（第一个词是选项即取缺省命令）；这是双击可用的条件，写在规格里（`hosts.rust.default_command`）
而不是代码里。

**C-8 一个可执行文件，命令词由调用方给。** ★★v0.2（2026-09-03，用户裁定）改写。
v0.1 的 C-8 是「别名二进制是薄壳」：`fylite-data` / `fylite-case` 各十行，把 `data` / `case`
前置到 argv 再交给同一份 `cli::parse` 与 `cli::data::run` / `cli::case::run`，并把用法里的
`fylite-data data` 折回 `fylite-data`。既然那十行只做前置，而**调用方本来就在写那个词**，
它们就是可以取消的一层。今天：`[[bin]]` 只有 `fylite-app` 一个，规格里没有 `hosts.rust.aliases`，
Python 侧的委托表从「每条命令一份候选列表」缩成一个名字加一次前置。用法里也不再有需要
折回的字符串——`fylite-app data --help` 打的就是它自己的名字。

(fylite-release-cli-asbuilt)=
# as-built（2026-09-02）

- **规格**：`python/fylite/_cli.json` 升到 v2——原 11 条命令逐字保留并加 `hosts: ["python"]`；
  新增 `app`（`--port` `--no-open` `--mdsip` `--mds-user` `--page` `--device` `--lang` `--theme`；
  `--app-dir` 属 rust、`--bin-dir` 属 python）、`data`（`info` `dump` `convert` `merge` `assemble`
  `tables`）、`case`（`describe` `plan` `run` `json`）——它们的参数从两个二进制的手写用法**逐条**转录，
  两处冲突改名：`info` / `dump` 的位置参数叫 `file`（从前叫 `path`，与 `dump --path` 同名）。
- **Rust**：`rust/fylite_engine/src/cli/mod.rs`（规格驱动解析器：命令树下降、`--k=v`、短选项、
  `--` 结束选项、`append`、位置参数按 `nargs` 绑定、`required` / `choices` / 类型检查、用法生成；
  六条单元测试）；`cli/data.rs` 与 `cli/case.rs`（主体从两个 `main.rs` 搬入，改读规格名：
  `flag("file")` `all("plans")` `flag("out")` `flag("record")`）；`src/bin/app/main.rs` 用解析器分派
  `app` / `data` / `case`，`app` 新增 `--page/--device/--lang/--theme`（拼成启动 URL，名字来自
  `hosts.app.params`）与 `--app-dir`（活目录，同一张 MIME 表，仍拒绝 `..`）；`src/bin/data/main.rs`
  与 `src/bin/case/main.rs` 退为薄壳（★v0.2 已删除，连同 Cargo.toml 的那两个 `[[bin]]`）。
`lib.rs` 在非 wasm 目标上导出 `cli`。
- **Python**：`engine/cli.py` 的 `build_cli` 支持 `hosts` 过滤、嵌套命令（`cmd1` … 记路径）、
  组级选项下放、非 argparse 键（`hosts` `app_param`）过滤；`cli_main` 记下原始词；
  `_cli_app` / `_cli_data` / `_cli_case` 委托（`--bin-dir` → `_bin/` → `$PATH`）。
  `pyproject.toml` 的 `package-data` 加 `_bin/*` 三项（★v0.2 收成一项 `_bin/fylite-app`）。
- **浏览器**：`assets/i18n.js` 的 `initial()` 先读 `?lang=`（并记住）；`assets/theme.js` 在
  `apply(stored())` 之前读 `?theme=`（`light` / `dark` 记住，`system` 清除）；`?device=` 原已在。
- **门禁**：`test_cli_spec.py`（命令表含三条新命令；嵌套解析；`hosts.app.params` ↔ 页面读者 ↔
  `app_param`；python 特有参数不进 Rust 用法）；Rust `cargo test --lib cli::` 与 `--bin fylite-app`。

(fylite-release-cli-gaps)=
# 缺口与后续 (Gaps and residuals)

| # | 事项 | 关闭判据 |
| :--- | :--- | :--- |
| 1 | 原生内核经请求面（页面走 HTTP 而不是 wasm）——`FYL-REPORT-05` §3b.4 的残留，本篇不做 | 一套请求面设计 + 页面的双路加载 |
| 2 | 站点发布 CI：`publish-app.yml` 随仓拆分后不在本仓；`tools/build-site.sh` 只出目录 | 一条 workflow 跑它并发布 |
| 3 | Windows 侧未实机验证（`FYL-REPORT-05` §3b.4 照录） | Windows 上双击运行、页面加载、数值与 Linux 逐位相同 |
| 4 | `serve` / `mcp` 无参数（stdio 固定）；`run` 的文档仍写 EFIT 时代的一句 | 文档按规格重生成（guide / reference 的 CLI 节） |
| 5 | Rust 解析器实现的是 argparse 的**子集**（无 `const`、无 `dest`、`nargs='?'` 只对选项）；规格里用了子集之外的键而又标给 rust 的参数会被静默照录 | 规格门禁：标给 rust 的参数只用子集内的键 |
| 6 | `--app-dir` 没有目录列表也不跟随符号链接之外的东西；只为开发 | 保持 |
