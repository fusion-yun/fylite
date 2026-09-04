# 安全问题的报告方式 · Reporting a security issue

**请不要**把安全问题写成公开 issue。

Please do **not** open a public issue for a security problem.

发邮件给维护者（见 [`CONTRIBUTORS.md`](CONTRIBUTORS.md)），标题带
`[fylite security]`。请附上：制品名与版本号、接口版本（ABI）、sha256、
以及能让人复现的最小输入。

Email the maintainers listed in [`CONTRIBUTORS.md`](CONTRIBUTORS.md) with
`[fylite security]` in the subject. Include the artifact name and version,
the interface (ABI) version, its sha256, and a minimal reproducing input.

★**报告里不要附实验数据。** 复现用的输入请尽量用合成算例（`cases/` 下的任一份，
或内核自己生成的合成平衡）。真炮数据、装置描述、内网主机名都不必寄给我们——
指出哪一份、哪个时刻即可。

★**Do not attach experimental data to a report.** Reproduce with a synthetic
case where you can (any plan under `cases/`, or the synthetic equilibrium the
kernel generates). Shot data, device descriptions and internal hostnames do not
need to be mailed to us — naming which one, and which time slice, is enough.

## 范围 · Scope

分发面不是一件东西，是四件，各自的暴露面不同。**先看你报的是哪一件。**

The distribution is not one thing but four, with different exposure. **Start by
saying which one.**

| 制品 Artifact | 网络 Network | 文件 Files |
| :--- | :--- | :--- |
| 内核 `libfylite_kernel.so` / `.wasm` | **不开任何连接** none | 只碰调用方点名的路径 only paths the caller names |
| 数据层 `libfylite_runtime.so` · `fylite data` · `fylite case` | 只在计划或调用方**点名端点**时外连（mdsip 只读） outbound only to an endpoint the plan or caller names | 读写计划与命令行点名的路径 |
| 桌面查看器 `fylite app` / `fylite` | **只绑回环**（`Ipv4Addr::LOCALHOST`，端口由 `--port` 或系统挑）；`--mdsip HOST:PORT` 才有外连 binds loopback **only** | 伺服随包嵌入的站点资产 |
| 静态站点 <https://fusion-yun.github.io/fylite/> | 页面内算完，无上传、不保存访问者数据 | — |

因此这里的「安全问题」主要是：**内存安全**（越界、未定义行为）、**恶意输入下的
崩溃或挂死**、以及下面那条文档信任边界。不是 Web 服务类漏洞——没有服务端。

Security issues here are therefore **memory safety**, **denial of service on
hostile input**, and the document trust boundary below. Not web-service
vulnerabilities: there is no server.

## 文档是数据，不是标记 · A document is data, never markup

站点上有两个**工具页**会打开**读者自己给的文档**：装置数据页（导入装置描述）与
算例报告页（`app/pages/report.html`：文件选择、拖放，以及 `?src=<地址>` —— 一条
链接就能替读者选定一份远端文档）。

Two **tool pages** open documents the reader supplies: the device-data page
(imported device descriptions) and the case-report page
(`app/pages/report.html`: file picker, drag-and-drop, and `?src=<url>` — a link
can choose a remote document on the reader's behalf).

★★**规矩：文档里的任何字段都以文本落地，不作标记解释。** 页面自己的词条与本模块
生成的 SVG 才走 `innerHTML`。2026-09-02 实测修掉一处违例：算例报告页把计划的
`note` 字段当 HTML 注入，为的是让语料自带的 `<strong>` 渲染出来——代价是任何被打开
的文档都能在页面源上跑脚本。语料的排版不值这个价，该字段现在是文本，
`app/tests/validate-report.mjs` 用一份带 `<img onerror>` 的计划把它钉住。

★★**The rule: every field of a document lands as text, never interpreted as
markup.** Only this repository's own catalogue strings and the SVG this code
generated go through `innerHTML`. One violation was found and fixed on
2026-09-02: the case-report page injected a plan's `note` as HTML so the
corpus's own `<strong>` would render — which let any opened document run script
in the page's origin. The corpus's typography is not worth that; the field is
text now, and `validate-report.mjs` pins it with a plan carrying `<img onerror>`.

报这一类问题时，请附上**触发它的那份文档**（合成的即可）与页面地址。

## 已发布制品里的信息 · What published artifacts may carry

已发布的文件里**不得**出现运营方的内网地址与构建者的家目录路径。占位写法是
RFC 2606 的 `mds.invalid`，路径写仓名相对形。这条曾被破过一次（2026-09-02，
`c58c2c6` 清理），现在由判据守着：`test_machine_desc` 逐份扫描随站点发布的装置
预置，命中 IPv4 字面量或 `/home/<user>/` 即红。

Published files must carry **no** operator-internal address and no builder home
path; the placeholder is RFC 2606's `mds.invalid`, and paths are written
repo-relative. This was broken once (cleaned up in `c58c2c6`) and is now gated:
`test_machine_desc` scans every device preset shipped with the site and fails on
an IPv4 literal or a `/home/<user>/` path.

★如果你在**任何已发布制品**（站点、wheel、release 附件）里看到这类字符串，按安全
问题报给我们——即便它看起来无害。

★If you find such a string in **any published artifact** — the site, a wheel, a
release attachment — report it as a security issue, even if it looks harmless.

## 不在本仓的东西 · What is not here

实验数据、装置描述与冻结的外码答案在**私有**数据仓，不随本仓分发；公开的 V&V
登记册（[`benchmark/`](benchmark/)）存的是**指针与 sha256**，不是本体。所以
「本仓某个文件泄露了受限数据」这类问题，请连**文件路径与那一行**一起报。

Experimental data, device descriptions and frozen external answers live in a
**private** data repository and are not distributed here; the public V&V
register ([`benchmark/`](benchmark/)) stores **pointers and sha256**, not
bodies. For "a file in this repository leaks restricted data", name the file and
the line.

## 支持范围 · Supported versions

**alpha**（当前 `VERSION` = `0.0.1-alpha`）。只修**最新**发行版：接口与结果格式
仍在移动，没有回移分支。公开面是 Linux x86-64 的轮与那个静态站点；别的平台在安装
时就被拒绝，而不是装完之后崩。

**alpha** (`VERSION` = `0.0.1-alpha`). Only the **latest** release is fixed:
interfaces and result formats still move, and there is no backport branch. The
published surface is the Linux x86-64 wheel and the static site; other platforms
are refused at install time rather than crashing later.

## 处置 · What happens next

收到后一周内回执。确认成立的问题在下一个 Release 修复，并在 Release 说明里
记名（除非你要求不记）。★如果我们判定它**不是**安全问题（例如是一条按名拒绝的
正常行为），会把理由写给你，而不是沉默。

You get an acknowledgement within a week. A confirmed issue is fixed in the next
release and credited in its notes (unless you ask us not to). ★If we judge it
**not** to be a security issue — a refusal-by-name working as designed, say — you
get the reasoning, not silence.
