---
document_id: FYL-DESIGN-15
title: "发布形态与统一命令行 (Release Forms and the Unified Command Line)"
shortname: fylite-release-cli
version: "1.0"
date: 2026-09-04
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-04T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v1.0 全文整理（用户「优化重写整个设计文档」，2026-09-04）。v0.2 那次「两个薄壳别名
    撤销」的沿革（R-2 / R-4 / R-5 / C-8 里各一段「v0.1 写的是…现在…」）收成现行陈述加
    一句记录；as-built 改标 2026-09-04（`_bin/fylite-app` 一项、`rust/build.sh --cli` 已撤、
    `data` 子命令七条含 `fetch`）；发布形态表按 `FYL-DESIGN-16` H-4 补第四个制品
    `fylite_runtime.wasm`（裁定，未建）并注明静态站点的装置描述已是实拷；术语「三个宿主」
    在本篇指**三份命令行的建出者**（Python · Rust · 浏览器启动参数），与 `-16` 的多宿主
    不冲突，写明。缺口表补 W-1 一行。
    · v0.2 只保留一个可执行文件（用户裁定 2026-09-03）：`fylite-data` / `fylite-case`
    撤销，`fylite-app` 承载全部命令词；`hosts.rust.aliases` 去掉，`--cli` 并入 `--exe`。
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
| 版本 (Version) | v1.0 |
| 发布日期 (Date of Issue) | 2026-09-04 |
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

〔一句话〕**三种发布形态，一份源；三份命令行，一个定义文件。**
fylite 以三种形态到达使用者：一个内嵌整个 `app/` 的**单一可执行文件**（`fylite-app`）、
一个**静态网页**（`app/` + wasm 制品，可选地由一个进程伺服而成为**动态**网页）、一个
**Python 包**（wheel）。三者装的是同一份页面、同一份内核制品；它们的命令行——
Rust 可执行文件、Python 的 `fylite`、浏览器页面的启动参数——从**同一个文件**
`python/fylite/_cli.json` 建出，只属于一个建出者的少数参数在该文件里标出。

〔术语〕本篇说的「三个宿主」是**三份命令行的建出者**：Python 控制台脚本、Rust 可执行
文件、浏览器的启动参数——与 `FYL-CONOPS-00` v1.0 的四个宿主（命令行 · Python 库 ·
浏览器 · AI 面）是两种切法：AI 面没有命令行，命令行这一个宿主有两个建出者。

〔为什么〕2026-09-02 之前这三样东西各自成立、互不引用：`fylite-app` 手写了一个四选项的
参数循环，两个数据 / 算例二进制各手写一份 `Args`（同一段代码复制两遍，各带一张
「哪些选项带值」的名单——不在名单上的未知选项被**静默接受**），Python 的 `fylite` 由
`_cli.json` 机械生成（11 条命令），页面从 URL 读 `?device=`，此外没有任何一处说页面
接受什么。本篇把它们写成一处，并把命令行定义收敛到一个文件：**加一条命令是改一个
文件**，三份命令行同时得到同一份用法。

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
| **单一可执行文件** `fylite-app`（Linux ELF / Windows PE32+） | 离线的人、没有 Python 的人（尤其 Windows） | 整个 `app/`（内嵌字节，生成表 `src/bin/app/assets.rs`）+ mdsip 只读客户端 + `data` / `case` 的全部代码 | 页面里的 **wasm**（不是原生内核）；`case` 子命令经 dlopen 用原生内核 | **有**：`/api/health` 恒答；六个只读 mdsip 端点在给了 `--mdsip` 时活 | `tools/build-app-exe.sh` |
| **静态网页**（站点） | 联网的人，零安装 | `app/`（减 `tests/`）+ `assets/fylite_{rs,tglf,dke}.wasm`；装置描述 `app/devices/*.jsonld` 是实拷（脚本里那段 `cp -L` 落实体的讲究是符号链接时代留下的，今天无链接可解） | 页面里的 wasm；加载后离线可用 | **无**：页面探 `/api/health` 不通即自禁用装置数据面板 | `tools/build-site.sh` |
| **动态网页** | 本机、或经隧道可达 mdsip 的人 | **同一份 `app/` 字节**，由一个进程伺服 | 页面里的 wasm | **有**：伺服进程答 `/api/*` | `fylite-app`（= `fylite app`） |
| **Python 包**（wheel，alpha 期 Linux x86-64） | 写脚本的人、LLM 宿主、集成方 | `python/fylite/` + `_lib/libfylite_kernel.so` + `_lib/libfylite_runtime.so` + `_cli.json` 等声明面 + `_bin/fylite-app`（**一个**可执行文件，构建时在则带） | 原生内核（ctypes） | `serve`（JSON-RPC stdio）/ `mcp`（MCP stdio）；`app` 委托可执行文件 | `tools/build-wheel.sh`（内核制品由内核仓 `rust/build.sh` 装入） |
:::

〔评注〕「静态」与「动态」不是两套页面：它们是**同一份字节的两种伺服方式**。区别只在有
没有一个进程站在页面后面答 `/api/*`，而页面用**端点是否回答**（不是主机名）判别
（`assets/host.js`）。所以动态网页没有自己的构建：`fylite-app` 就是它。

〔裁定，未建〕**第四个制品 `fylite_runtime.wasm`**（`FYL-DESIGN-16` H-4，用户裁定
2026-09-04）：中间层也进浏览器，由 JS 调用，`--no-default-features`（无 mdsip / hdf5 /
netcdf）。它落地后静态网页装的是四个 wasm，`geqdsk.js` / `fyo.js` / `session.js` 的职责
归它；构建脚本与它的门禁归 `-16` 分期 W-1，本篇的表到时补一列。

## 裁定 R-1..R-6 (Rulings on release forms)

**R-1 三形态一份源。** 三种形态装的是同一份 `app/`、同一版内核制品（`.so` 与 `.wasm`
出自同一个 `c_api.rs`，`FYL-SDD-01` DE-LOG-01）、同一份 `_cli.json`。一个形态**禁止
(MUST NOT)** 带另一个形态没有的页面或参数名；不同之处只能是**运行时**判别的
（`host.js` 的 `data-fy-host`），不能是构建时分叉的页面。

**R-2 只有一个可执行文件，它是 Rust 宿主的全部命令行。** `fylite-app` 不带子命令即
`app`（起服务、开浏览器——双击仍可用）；`fylite-app data …` 与 `fylite-app case …` 承载
数据与算例两组动词。★2026-09-03 用户裁定：此前的两个薄壳别名二进制（各十行，只把
命令词前置到 argv）撤销——那一次前置由调用方给即可，撤掉之后少两个二进制、少两条
`_bin/` 项、少一处用法里的字符串折回，**能力一条没少**。

**R-3 静态即无服务端组件；动态即同一份字节被一个进程伺服。** 静态站点的构建只做三件事：
取 `app/` 的发布子集（去 `tests/`）、核对装置描述在、核对三个 wasm 在。动态网页由
`fylite-app`（或 wheel 里的 `fylite app`，它委托同一个可执行文件）伺服，并答 `/api/*`；
请求面**只绑回环**、只读、无表达式端点（`FYL-REPORT-05` §3b.5 与 `api.rs` 抬头）。
把原生内核接到请求面（页面改走 HTTP 而不是 wasm）是 `FYL-DESIGN-16` K-4 / H-2 的
远端后端 `/api/case`，归那一篇的分期 P2，本篇不做。

**R-4 wheel 承载全部命令，原生的三条委托。** Python 的 `fylite` 列出规格里的每一条命令；
`app` / `data` / `case` 不在 Python 里重写，而是把命令词**逐字**交给 `_bin/` 里的可执行
文件：**把命令词放回最前面**，其余的字原样交过去（查找次序 `--bin-dir` → 包内 `_bin/`
→ `$PATH`，只认一个名字 `fylite-app`）。★命令词**总是**前置，`app` 也不例外：那个
可执行文件无词时的缺省是 `app`，省掉词就意味着 `fylite data convert` 会静默地起一个
网页服务而不是转换文件。找不到可执行文件时按名说明要构建什么，退出码 2——**不**
退化成一个能力更少的 Python 实现。

**R-5 版本同源与制品不入库，照旧。** `VERSION` 是发行版本的唯一来源；`.so` / `.wasm` /
`_bin/*` 不进 git，打包时装入（`FYL-REPORT-05` §6.1、本仓 `.gitignore` 抬头）。
`package-data` 里的 `_bin/` 项只有一项 `_bin/fylite-app`。

**R-6 每个形态一条构建命令，产物与门禁在表里。** 见 {numref}`tbl-fylite-release-build`。
构建脚本**不生成**规格的副本——三份命令行都直接读 `_cli.json`（编译期 `include_str!`、
运行期 `json.loads`、门禁核对页面读的名字），所以没有第四份需要同步的东西。

:::{table} 构建路径与门禁（2026-09-04 as-built）。
:name: tbl-fylite-release-build
:align: left

| 形态 | 命令 | 产物 | 门禁 |
| :--- | :--- | :--- | :--- |
| 单一可执行文件 | `bash tools/build-app-exe.sh [linux\|windows\|windows-msvc\|both]`（先跑 `node tools/make-app-embed.mjs`） | `rust/fylite_runtime/target/release/fylite-app`、`…/x86_64-pc-windows-{gnu,msvc}/release/fylite-app.exe` | `app/tests/validate-embed.mjs`（资源表与 `app/` 同步）；二进制自带测试（首页、wasm MIME、穿越、活目录穿越、启动 URL） |
| 静态网页 | `bash tools/build-site.sh [输出目录]` | `dist/site/`：`app/` 发布子集 + 三个 wasm + 装置描述 | 脚本自检：三个 wasm 在、无 `tests/`、无悬空符号链接 |
| 动态网页 | `fylite-app [--port N] [--mdsip HOST:PORT] …` 或 `fylite app …` | 运行中的进程 | `app/tests/validate-app-mdsip.mjs --exe <fylite-app>` |
| Python 包 | `bash rust/build.sh --exe`（中间层 `.so` + `_bin/fylite-app`；`--cli` 已撤，给它会被按名拒绝并指向 `--exe`）→ 内核仓 `rust/build.sh`（内核 `.so`、生成物）→ `bash tools/build-wheel.sh` | `python/dist/fylite-<ver>-py3-none-manylinux_x_y_x86_64.whl` | `test_bundled_artifacts.py`（ABI 一致、制品不入库）；`test_cli_spec.py` |
:::

(fylite-release-cli-spec)=
# 统一命令行：一个定义文件 (One Definition File for Three Builders)

〔一句话〕`python/fylite/_cli.json`（`spec_version: 2`）定义每一条命令、每一个参数、每一句
帮助；Python 的 argparse 由它**机械生成**（`engine/cli.py`），Rust 宿主在**编译期**把它
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
| `commands[].commands[]` | 命令 | 子命令（组）：`data` / `case` |
| `commands[].handler` | 命令 | Python 的处理函数（`module:function`）；Rust 按命令名分派，不读它 |
| `args[].hosts` | 参数 | 只属一个建出者的参数（`--bin-dir` 属 python，`--app-dir` 属 rust） |
| `args[].app_param` | 参数 | 这个选项写入 URL 的启动参数名（`--device` → `device`） |
:::

## 裁定 C-1..C-8 (Rulings on the command line)

**C-1 一个文件。** 命令、参数、帮助只写在 `_cli.json`；任何建出者的代码里**禁止 (MUST
NOT)** 再出现一张「选项名单」（这正是 2026-09-02 之前两份 Rust `Args` 里那张 `takes_value`
名单）。Python 由它建 argparse；Rust 由它建解析器与用法（`cli::parse` / `cli::usage`）；
页面读的启动参数名由它声明、由门禁核对。

**C-2 少量特有参数用 `hosts` 标出，不用代码分支。** 命令级 `hosts` 说谁承载；参数级
`hosts` 说谁接受。缺省是全部。截至本版只有三处特有：`--bin-dir`（python：可执行文件
在哪）、`--app-dir`（rust：伺服一棵活目录，开发用）、以及 `hosts.app.params`（浏览器：
`device` `lang` `theme` `page`）。一个不承载某参数的建出者对它**按名拒绝**（Rust：
`unknown option "--bin-dir"`），不是静默吃掉。

**C-3 不承载的命令要么委托要么按名拒绝。** Python 承载全部命令，其中 `app` / `data` /
`case` 逐字委托给 Rust 可执行文件（R-4）；Rust 只承载这三条，对 `fylite-app run …` 答
「命令不归本程序」。两个方向都**不**试图用另一套实现回答。

**C-4 帮助与拒绝由规格生成。** Rust 的 `--help` 是 `cli::usage` 从规格排出来的（概要行 +
一句话 + 子命令表 + 参数表），argparse 的是它自己的排版；**内容**同源，措辞可以不同。
未知选项、缺参数、类型不符、不在 `choices` 里、`required` 缺席——两侧都按名拒绝，
退出码 2。

**C-5 嵌套命令与组级选项。** `data` / `case` 是组；组自己的参数对每个子命令有效，且
**写在子命令之前或之后都可以**：Rust 解析器对祖先的参数不分位置，argparse 侧把组的
参数再声明到每个子命令上，两侧同一规则。

**C-6 浏览器的启动参数定义一次。** `hosts.app.params` 是页面从 URL 接受什么的唯一声明；
`fylite app --<name>` 把它们写进打开的 URL（`--page` 决定路径，其余进查询串）；页面侧
`devices.js` 读 `device`、`i18n.js` 读 `lang`、`theme.js` 读 `theme`。门禁 `test_cli_spec.py`
核对：每个声明的 `query` 参数在 `app/assets/` 里恰有读者，且页面不读未声明的名字；
`app` 命令的每个 `app_param` 指向一个已声明的参数，反之亦然（Rust 单元测试同此）。

**C-7 Rust 宿主的缺省命令是 `app`。** `fylite-app` 与 `fylite-app --port 8123` 都是 `app`
（第一个词是选项即取缺省命令）；这是双击可用的条件，写在规格里
（`hosts.rust.default_command`）而不是代码里。

**C-8 一个可执行文件，命令词由调用方给。** `[[bin]]` 只有 `fylite-app` 一个，规格里没有
`hosts.rust.aliases`，Python 侧的委托表是一个名字加一次前置；用法里没有需要折回的字符串
——`fylite-app data --help` 打的就是它自己的名字。★v0.1 的 C-8 是「别名二进制是薄壳」，
2026-09-03 用户裁定改为本条（理由见 R-2）。

(fylite-release-cli-asbuilt)=
# as-built（2026-09-04）

- **规格**：`python/fylite/_cli.json` v2——11 条 Python 命令（`run` `plot` `describe` `cases`
  `manifest` `replay` `report` `whence` `alias` `serve` `mcp`，`hosts: ["python"]`）；
  `app`（`--port` `--no-open` `--mdsip` `--mds-user` `--page` `--device` `--lang` `--theme`；
  `--app-dir` 属 rust、`--bin-dir` 属 python）、`data`（`info` `dump` `convert` `merge`
  `assemble` `fetch` `tables`）、`case`（`describe` `plan` `run` `json`）——后两组的参数
  从两个二进制的手写用法**逐条**转录，两处冲突改名：`info` / `dump` 的位置参数叫 `file`。
- **Rust**：`rust/fylite_runtime/src/cli/mod.rs`（规格驱动解析器：命令树下降、`--k=v`、
  短选项、`--` 结束选项、`append`、位置参数按 `nargs` 绑定、`required` / `choices` /
  类型检查、用法生成）；`cli/data.rs` 与 `cli/case.rs`；`src/bin/app/main.rs` 用解析器
  分派 `app` / `data` / `case`，`app` 带 `--page/--device/--lang/--theme`（拼成启动 URL）
  与 `--app-dir`（活目录，同一张 MIME 表，仍拒绝 `..`）。`Cargo.toml` 只有一个 `[[bin]]`。
- **Python**：`engine/cli.py` 的 `build_cli` 支持 `hosts` 过滤、嵌套命令、组级选项下放、
  非 argparse 键过滤；`cli_main` 记下原始词；`_cli_app` / `_cli_data` / `_cli_case` 委托
  （`--bin-dir` → `_bin/` → `$PATH`，只认 `fylite-app`）。`pyproject.toml` 的
  `package-data` 有 `_bin/fylite-app` 一项。
- **浏览器**：`assets/i18n.js` 的 `initial()` 先读 `?lang=`（并记住）；`assets/theme.js`
  在 `apply(stored())` 之前读 `?theme=`（`light` / `dark` 记住，`system` 清除）；
  `?device=` 原已在。
- **门禁**：`test_cli_spec.py`（命令表含三条 Rust 命令；嵌套解析；`hosts.app.params` ↔
  页面读者 ↔ `app_param`；python 特有参数不进 Rust 用法）；Rust `cargo test --lib cli::`
  与 `--bin fylite-app`。
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
