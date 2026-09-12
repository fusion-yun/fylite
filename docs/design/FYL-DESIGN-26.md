---
document_id: FYL-DESIGN-26
title: "场景：解释性分析（给 T 反求 χ · 0-D 放电账） (Scenario: Interpretive Analysis)"
shortname: fylite-scenario-interpretive
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（建模页的「反演栏」（`code/interpretive`）· analysis 线上的 `zerod`（S8-FR-INF-2 ◐））与 W-2 四件必备写成——
    物理算法流程图（`sc-interpretive-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-interpretive-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（fyanalysis A2 剖面反演（q^PB / χ^eff，`FYTOK-SDD-07`）与 S8-FR-INF-2 的单时片状态估计一侧）。
    裁定不新增：正本在 `FYL-DESIGN-10`（P-28 同一符号两个方向）· `FYL-DESIGN-12`；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-interpretive

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-26` |
| 文档名称 (Title) | 场景：解释性分析（给 T 反求 χ · 0-D 放电账） |
| 短名 / Slug | `fylite-scenario-interpretive` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-10`（P-28 同一符号两个方向）· `FYL-DESIGN-12`） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L2 实验分析 · `FYL-DESIGN-10`（P-28 同一符号两个方向）· `FYL-DESIGN-12` · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `fyanalysis A2 剖面反演（q^PB / χ^eff，`FYTOK-SDD-07`）与 S8-FR-INF-2 的单时片状态估计一侧` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-interpretive-abstract)=
# 摘要 (Abstract)

〔一句话〕**同一条能量方程反着解：给实测剖面与源项，求 χ_e · χ_i；再用 0-D 账核对这一炮的 W · τ_E · H98。**

实际工作情景（fytok fyanalysis A2）：重构出平衡与剖面之后，研究者要问"这一炮的输运是反常的还是新经典的"——
把功率平衡反过来解出 χ，与 M2 的闭包档对照；同时用 0-D 账（W · τ_E · H98 · V_loop）核对定标。**归并**：
建模页今天的"反演栏"（`FYL-DESIGN-10` 说它"给 T 反求 χ"）按**意图**属于实验分析而不是建模（fytok ADR-116：
面由意图定，不由保真度定）；analysis 线上的 `zerod` 是"解释性 0-D"，与 design 线上的"方案 0-D"（D1）
是同一 code 的两种输入。fytok 把**参数标定**（时间依赖、每次前向是一次时程解）与单时片状态估计分列
（S8-FR-INF-2）；本章只收**单时片**的功率平衡反演，时程标定在 fylite 包络之外。

**场景定义。** 线 `analysis`（S-L2 实验分析）；归并进本章的名字：建模页的「反演栏」（`code/interpretive`）· analysis 线上的 `zerod`（S8-FR-INF-2 ◐）。fytok 的对应面：fyanalysis A2 剖面反演（q^PB / χ^eff，`FYTOK-SDD-07`）与 S8-FR-INF-2 的单时片状态估计一侧。

(fylite-scenario-interpretive-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-interpretive-flow.svg
:name: fig-x26-flow
:align: center
:width: 100%

解释性分析：实测剖面与平衡进源项装配（beam · rf_ray · ADAS · α），`code/interpretive` 反求 χ；放电波形进 `code/zerod` 做 0-D 账；两者对照 M2 的闭包档。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x26-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 取输入 | 实测剖面（A1 的 `pressure` 或导入）· 平衡（A1 阶段 3）· 放电波形 | 端口绑定 / 三级解析 | 文档 → 文档 | 出处齐（P-13） | ✓ |
| 源项装配 | 在给定剖面上算沉积：束 · 射频 · 辐射 · 欧姆 · α | `code/beam` · `code/rf_ray` · ADAS 表 | 剖面 + 平衡 → `core_sources` | 守恒账：Σ源 = 输运 + dW/dt | ◐（ECCD 部分，`FYL-REPORT-07` C-20） |
| 功率平衡反演 | 同一条能量方程反着解 | `code/interpretive` | 剖面 + 源 → χ_e · χ_i | χ ≥ 0 · 边界不发散 | ◐（code 在声明面，页面栏在建模页） |
| 0-D 放电账 | 规定剖面下 W · τ_E · H98 · V_loop · P_fus · Q 对 t | `code/zerod` | 波形 + 平衡 → `summary` 时序 | 与定标对照 | ✓ |
| 对照 | χ 对新经典 / TGLF 档（M2） | `fyo:ComparisonRecord` | 两份 `core_transport` → 逐通道判读 | 「反常 / 新经典」是判读不是阈值 | ◐ |
:::

〔端口〕`core_profiles`（实测剖面）· `equilibrium` · `pulse` / 波形（0-D 用）。产出：`core_transport`（反演出的 χ）· `core_sources` · `summary`。

(fylite-scenario-interpretive-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
# 0-D 账（zerod 在 analysis 线上是解释性用法：输入是实测波形，不是方案）
fy run model zerod --device east --input shot137985_waveforms.fyo.jsonld -o rec/zerod

# 功率平衡反演：code/interpretive 在内核声明面里，但没有场景模板——今天走计划文档
fy run plan-interpretive.jsonld --bind core_profiles=rec/A1/pressure.fyo.jsonld \
   --bind equilibrium=rec/A1/equilibrium.fyo.jsonld -o rec/interp        # 模板缺：X-G-1
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
z = S.model.zerod(device="east", waveforms=wf)          # 0-D 账（S8-FR-INF-2 ◐）
# 功率平衡反演：无登记的 Python 入口（工具登记册无 interpretive）——经文档门：
from fylite.io import fydoc
rec = fydoc.complete("code/interpretive", plan)
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_zerod` | 清单反射（`_manifest/zerod.jsonld`） | 0-D 账 |
| `fylite_open` | `fylite://<run>/core_transport` | 读反演出的 χ |
| — | `code/interpretive` 无清单、无工具 | X-G-1 |

(fylite-scenario-interpretive-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-interpretive-page.svg
:name: fig-x26-page
:align: center
:width: 100%

解释性分析页：左列输入与档位（剖面 · 平衡由记录绑入，源项与反演量按档位选），右上 χ 剖面对新经典 / TGLF 档，右下功率账逐项（守恒残差来自记录）。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** `ρ_b` · 平滑 `λ` · 源项档位今天没有词表条目（`code/interpretive` 无模板）——**待立**；`zerod` 的 33 个参数有词表。

(fylite-scenario-interpretive-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 守恒 | Σ源 = 输运 + dW/dt 的残差 | `ComparisonFinding{norm: balance}` | 记录 `summary/balance` 行（M3 已有先例 1e-13） |
| 反演解 | χ ≥ 0 · 边界不发散 | `AcceptanceCriterion` | — |
| 0-D | H98 与定标对照 | `ComparisonFinding` | `zerod` 的 `summary` |
| 判读 | 反常 / 新经典 | `ComparisonRecord` 对 M2 的 `core_transport` | — |

**X-3 阈值只写量过的。** 守恒残差有量（M3 的能量账 1e-13 是同一账在演化里的读数）；反演解的正定性是判据不是阈值；"反常"没有阈值，是对照的判读。

(fylite-scenario-interpretive-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 炮号 · 时刻（剖面来自 A1 记录） | 源项档 · 边界 ρ_b · 平滑 · Tᵢ 形状 | 绑自己的剖面 / 源项文档；换对照档（外部闭包的产物） |

(fylite-scenario-interpretive-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `code/interpretive` 无场景模板、无清单、无 Python 登记入口 | `docs/examples/scenario/interpretive.jsonld` 由生成器出，`fy list scenarios interpretive` 有表 |
| **X-G-2** | 反演栏今天在建模页（`-10`），本章按意图归 analysis | `-10` / `-12` 各改一行指向本章；页面搬栏另裁 |
| **X-G-3** | 时程参数标定不在包络（fytok S8-FR-INF-2 的另一半） | 不做；写进 `FYL-REPORT-07` §8 负面清单的引用 |

(fylite-scenario-interpretive-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-10`（P-28 同一符号两个方向）· `FYL-DESIGN-12` · `docs/physics/` 相关章 · fytok `fyanalysis A2 剖面反演（q^PB / χ^eff，`FYTOK-SDD-07`）与 S8-FR-INF-2 的单时片状态估计一侧` | `sc-interpretive-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-10` 反演栏（本章归到 analysis 线） | `sc-interpretive-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
