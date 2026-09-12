---
document_id: FYL-DESIGN-25
title: "场景：逐片重构（时间序列） (Scenario: Slice-by-Slice Reconstruction (Time Series))"
shortname: fylite-scenario-series
version: "0.1"
date: 2026-09-12
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - AI 协作（会话记录在案）
created: 2026-09-12T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-12T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`series` · `batch`）与 W-2 四件必备写成——
    物理算法流程图（`sc-series-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-series-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（S-8 重构四级中的 L3 炮间 / L4 隔夜（`FYTOK-CONOPS-00` ITER 用例表））。
    裁定不新增：正本在 `FYL-DESIGN-12`（P-23 时片之间不插值）· `-24`（每片就是一次 A1）；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-series

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-25` |
| 文档名称 (Title) | 场景：逐片重构（时间序列） |
| 短名 / Slug | `fylite-scenario-series` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-12`（P-23 时片之间不插值）· `-24`（每片就是一次 A1）） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L2 实验分析 · `FYL-DESIGN-12`（P-23 时片之间不插值）· `-24`（每片就是一次 A1） · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `S-8 重构四级中的 L3 炮间 / L4 隔夜（`FYTOK-CONOPS-00` ITER 用例表）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-series-abstract)=
# 摘要 (Abstract)

〔一句话〕**一炮多片：同一份反演设定，逐片换测量，片间不插值；队列是宿主机制，不是第二个场景。**

实际工作情景（fytok S-8 的重构四级）：炮后分析不是一片，是整个平顶段的几十片——同一套约束与权重，
逐时刻跑一遍 A1，把 q₀ · q₉₅ · l_i · β_p 排成时序，再对交付的 EFIT 时序看偏离。**归并**：`series`（8 参数
模板，内核门今天不认 `code/series`）与 `batch`（围着反演栏的队列，命令行上是 series 或 shell 循环）在
实际工作里是同一件事的两个层次——前者说"算什么"，后者说"怎么排队"；本章把它们收成一章，队列只是
本章的执行形（`FYL-DESIGN-22` 共性功能〈执行〉），不另立场景。

**场景定义。** 线 `analysis`（S-L2 实验分析）；归并进本章的名字：`series` · `batch`。fytok 的对应面：S-8 重构四级中的 L3 炮间 / L4 隔夜（`FYTOK-CONOPS-00` ITER 用例表）。

(fylite-scenario-series-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-series-flow.svg
:name: fig-x25-flow
:align: center
:width: 100%

逐片重构：每片一次 A1（`code/reconstruction`），宿主逐片串行（队列是回边），`code/series` 把逐片记录汇成时序文档；对照边指向交付 EFIT 时序。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x25-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 取片 | 时刻列表 t₁..t_N 的测量文档（语料切片或 mdsip） | 测量三级解析（`-17` E-15） | `magnetics` × N → N 份测量文档 | — | ✓ |
| 每片一次反演 | 同一份设定，逐片换测量；**片间不插值**（P-23） | `code/reconstruction`（A1 的阶段 0 或 3） | 测量 + `pressure`（可选）→ N 份 `equilibrium` | 每片各自：GS 残差 · χ² | ✓ |
| 队列 | 宿主逐片串行，步预算 = 片数，取消落在片界 | 宿主（`run.js` / shell 循环） | N 份记录 | 已算的片完整可用（U-9） | ◐（页面有栏，命令行是循环） |
| 汇总 | 逐片标量排成时序文档 | `code/series` | N 份记录 → 一份 `summary` 时序 | 无合成判据：逐片判据照录 | ✗（门今天不认；重测 `-23` G-1） |
| 对照 | 与交付 EFIT 时序逐片比 | `fyo:ComparisonRecord` | 两份时序 → 逐片一行 | 逐片偏离可解释（A1 §四后验） | ◐ |
:::

〔端口〕`device` · `measurements`（主，多片）；`pressure` 可选（每片各绑或共用一份）。产出：逐片 `equilibrium` + 一份时序 `summary`。

(fylite-scenario-series-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
# 一片：就是 A1
fy run analysis reconstruction --device east shot=137985 time=4.0 --only_magnetic -o rec/t4000

# 多片：命令行上的 series 今天就是一个循环（batch 不是场景）
for t in 3.5 3.6 3.7 3.8 3.9 4.0; do
  fy run analysis reconstruction --device east shot=137985 time=$t --only_magnetic -o rec/t$t --quiet
done

# 模板在（8 参数），内核门今天不认这个 code：
fy list scenarios series
fy run analysis series --device east shot=137985 t_start=3.5 t_end=4.5 n=11   # → 按名拒绝，指向 -23 G-1
```

## Python（`fylite.scenario`）

```python
from fylite.scenario.analysis import recon_rs
# 同一能力，函数而非登记的工具（工具登记册 BROWSER_ONLY_BARS 的说明）
res = recon_rs.run_series(meas_slices, only_magnetic=True)      # 逐片记录列表
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_run` | `shot` · `time_s` … 一片 | 一片一调；多片由 MCP 宿主循环（与 CLI 同形） |
| `fylite_open` | `fylite://<run>/summary` | 读逐片标量 |
| `fylite_east_mdsplus` | 清单反射 | 取数（`-17` E-15 第三级） |

(fylite-scenario-series-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-series-page.svg
:name: fig-x25-page
:align: center
:width: 100%

逐片重构页：片表的状态列 = 各片记录的 `run_state`；时序图已算片实心、未算片空；点一片看它的逐道残差与截面。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 片表 · 时序图 · 逐道残差表都是 `-12` 时间序列栏与反演栏的既有部件；`t_start` · `t_end` · `n` 在 `series` 模板词表里。

(fylite-scenario-series-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 每片 | GS 残差 · χ² 饱和 | A1 §四 | 每片记录 |
| 时序 | 无合成判据（不把 N 片合成一个绿灯） | 逐片 `ComparisonFinding` | — |
| 对照 | 与交付 EFIT 的 q₀ · q₉₅ · l_i 逐片偏离 | `ComparisonRecord` | B-06 先例（单片） |

**X-3 阈值只写量过的。** 逐片沿用 A1；时序层没有阈值，也不该有——一条时序的"好坏"是逐片判据的集合，不是一个数。

(fylite-scenario-series-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 炮号 · 时间窗 · 片数（预设） | 与 A1 同（每片同一档位） | 每片各绑自己的 `pressure`；导出整份逐片计划 |

(fylite-scenario-series-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `code/series` 内核门不认（模板在） | 按 `-23` G-1 重测；认了则 `fy run analysis series` 跑通 |
| **X-G-2** | 命令行无队列语义（循环由用户写） | `fy run` 收时刻列表并逐片串行，取消落在片界（`PLAN.md` H-8 的取消同源） |

(fylite-scenario-series-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-12`（P-23 时片之间不插值）· `-24`（每片就是一次 A1） · `docs/physics/` 相关章 · fytok `S-8 重构四级中的 L3 炮间 / L4 隔夜（`FYTOK-CONOPS-00` ITER 用例表）` | `sc-series-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-12` 时间序列栏 · 批处理栏 | `sc-series-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
