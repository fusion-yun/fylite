---
document_id: FYL-DESIGN-33
title: "场景：垂直稳定与位置控制（裕度 → 反馈 → 闭环演化） (Scenario: Vertical Stability and Position Control)"
shortname: fylite-scenario-vertical
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`vstab` · `vertical` · `evolution`（三个无模板的名字）· `breakdown` 的上升段一侧）与 W-2 四件必备写成——
    物理算法流程图（`sc-vertical-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-vertical-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（S-9（fycontrol `EvolutiveDischarge`：电路 × 自由边界 G-S 交替时间推进 + 主动垂直位置控制；`FYTOK-SRS-03` FR-EQ-016 刚体 n=0 模由既有原语装配）；S-9 / S-10 分工：设计判「可不可行」，控制判「闭环会不会撞限」）。
    裁定不新增：正本在 `FYL-DESIGN-09`（D-14 · D-22）· `guide/stability-and-control.md`；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-vertical

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-33` |
| 文档名称 (Title) | 场景：垂直稳定与位置控制（裕度 → 反馈 → 闭环演化） |
| 短名 / Slug | `fylite-scenario-vertical` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-09`（D-14 · D-22）· `guide/stability-and-control.md`） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L3 控制仿真 · `FYL-DESIGN-09`（D-14 · D-22）· `guide/stability-and-control.md` · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `S-9（fycontrol `EvolutiveDischarge`：电路 × 自由边界 G-S 交替时间推进 + 主动垂直位置控制；`FYTOK-SRS-03` FR-EQ-016 刚体 n=0 模由既有原语装配）；S-9 / S-10 分工：设计判「可不可行」，控制判「闭环会不会撞限」` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-vertical-abstract)=
# 摘要 (Abstract)

〔一句话〕**先判裕度，再设计反馈，再闭环演化——三个「无模板」的名字在实际工作里是一条链，本章把它们收成一章。**

实际工作情景（fytok S-9）：拿到平顶平衡后，控制工程师先算 n=0 垂直模的裕度（k / k_ideal · γ），再设计垂直反馈
（增益 · 观测器），再把线圈电压驱动的位形演化与控制律闭合起来跑——看会不会撞限（S-9 / S-10 分工：设计侧判
可行，控制侧判闭环撞不撞限）。**归并**：`vstab`（内核 entry，无 case code）· `vertical`（闭环，无栏无语料）·
`evolution`（电压驱动的位形演化，无栏无语料）三者不设模板（-17 P2-c），指南〈稳定与控制〉已把它们写成一条链。
`breakdown` 在 control 线上是缺省场景：击穿**动力学**与上升段是本章的起点，场零**设计**归 D2。

**场景定义。** 线 `control`（S-L3 控制仿真）；归并进本章的名字：`vstab` · `vertical` · `evolution`（三个无模板的名字）· `breakdown` 的上升段一侧。fytok 的对应面：S-9（fycontrol `EvolutiveDischarge`：电路 × 自由边界 G-S 交替时间推进 + 主动垂直位置控制；`FYTOK-SRS-03` FR-EQ-016 刚体 n=0 模由既有原语装配）；S-9 / S-10 分工：设计判「可不可行」，控制判「闭环会不会撞限」。

(fylite-scenario-vertical-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-vertical-flow.svg
:name: fig-x33-flow
:align: center
:width: 100%

垂直稳定与位置控制：平衡与线圈进 n=0 模（entry `vstab`）与形状响应矩阵，反馈回路与电压驱动的演化闭合成逐步的环（步预算 · 断点在步界），判定与轨迹对 TokSys。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x33-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 输入 | 平衡（D2 或 A1）· 线圈与真空室（`pf_passive` 缺）· 控制律（PD 增益 · 观测器） | 端口 / 参数 | — | — | ◐ |
| n=0 垂直模 | 刚体：k · k_ideal · γ（电阻壁）；刚性滤丝配方 | entry `vstab`（无 case code） | `equilibrium` → 裕度 | k / k_ideal < 1 · γ τ_wall | ◐ |
| 形状响应 | ∂(形状)/∂(I_coil)；线性化（过期的是它，D-7） | `code/vessel` · `code/coilshare` | → 矩阵 | 条件数 | ✓ |
| 反馈回路 | Z 观测 → 律 → 电压 | `vertical`（无模板；指南〈垂直反馈回路〉） | — | 稳定 / 失控 | ✗ |
| 闭环演化 | 电路 + 自由边界逐步；步预算 · 断点在步界 · 取消在步界 | `evolution`（无模板；指南〈电压驱动的位形演化〉） | 每步一份记录 | 撞限即停（P-8） | ✗ |
| 判定 | 稳定 / 失控 · 何时 · Z(t) · V(t) | `fyo:ComparisonRecord` 对 TokSys（B-04） | — | — | ◐ |
:::

〔端口〕`equilibrium` · `pf_active` · `pf_passive`（缺）· 控制律参数。产物：Z(t) · V(t) 轨迹 · 判定块。

(fylite-scenario-vertical-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
fy list scenarios --line control                    # breakdown 可跑；vstab · vertical · evolution 无模板
fy run control --device iter -o rec/bd              # 缺省 = breakdown（击穿动力学起点）
# 裕度：内核有 entry vstab，无 case code —— 走原始条目
fy run plan-vstab.jsonld --bind equilibrium=rec/cfg/equilibrium.fyo.jsonld -o rec/vs   # X-G-1
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
vs = S.control.vstab(equilibrium=eq)          # S9-FR-EVO-1 ◐：k · k_ideal · γ
# 闭环与演化：无登记入口（-17 P2-c）；指南〈稳定与控制〉给出的调用今天只在内核仓神谕树
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_vstab` | 清单反射 | 裕度 |
| `fylite_gaps` | `line: control` | 这条线没做的（今天最长的一张表） |

(fylite-scenario-vertical-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-vertical-page.svg
:name: fig-x33-page
:align: center
:width: 100%

垂直稳定页（目标态）：左列平衡与真空室、控制律增益，右上裕度读数与判定，右下闭环的 Z(t) 与线圈电压；失控的一步标红并停在步界。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** `K_p` · `K_d` · 观测噪声 · `dt` 都**待立**（无词表）；平衡与真空室经端口。

(fylite-scenario-vertical-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 裕度 | k / k_ideal < 1 · γ τ_wall | `AcceptanceCriterion` × 2 | entry `vstab` 有读数；SRS-03 判据：耦合梯度中心差分 rel < 1e-6 · 刚度恒等式 rel < 1e-4（fytok 的闸，本仓对拍待立） |
| 闭环 | 撞限即停；Z 回到带内 | `AcceptanceCriterion` | — |
| 对照 | TokSys（登记册 B-04） | `ComparisonRecord` | ✓（裕度一侧） |

**X-3 阈值只写量过的。** 裕度判据是不等式不是阈值；闭环的"撞限"由装置的电压上限定，今天缺件。

(fylite-scenario-vertical-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 平衡与预设增益 | 增益 · 观测器 · dt | 绑自己的控制律（外部产物：增益表）· 绑真空室 |

(fylite-scenario-vertical-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `vstab` 无 case code；`vertical` · `evolution` 无栏无语料 | 三者各一份声明的 code 或并为一个 `code/vertical` 多步计划；词表先立（-17 P2-c） |
| **X-G-2** | `pf_passive` 缺（A-15） | 装置文档带真空室 |
| **X-G-3** | 闭环的执行在本分发无处跑（指南所述调用在内核仓神谕树） | 与 `PLAN.md` H-12 同一出口：宿主逐步驱动 |

(fylite-scenario-vertical-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-09`（D-14 · D-22）· `guide/stability-and-control.md` · `docs/physics/` 相关章 · fytok `S-9（fycontrol `EvolutiveDischarge`：电路 × 自由边界 G-S 交替时间推进 + 主动垂直位置控制；`FYTOK-SRS-03` FR-EQ-016 刚体 n=0 模由既有原语装配）；S-9 / S-10 分工：设计判「可不可行」，控制判「闭环会不会撞限」` | `sc-vertical-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-09`（控制仿真在放电设计页的仿真模式里，PF 两档驱动 D-14） | `sc-vertical-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
