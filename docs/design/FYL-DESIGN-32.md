---
document_id: FYL-DESIGN-32
title: "场景：整脉冲前馈设计（路点序列 → 逐通道电流与电压） (Scenario: Whole-Pulse Feedforward Design)"
shortname: fylite-scenario-pulse
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`pulse`（浏览器专有栏）· `pfwave` 的时序用法 · `-09` 设计模式）与 W-2 四件必备写成——
    物理算法流程图（`sc-pulse-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-pulse-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（fydesign `PulseDesign`（S10-FR-DRV-1/2：`V = clip(V_ff + V_fb, ±V_max)`，可行 = 饱和分数 0）；全放电五段登记（击穿 → 爬升 → 平顶 → 下降 → 终止，`FYTOK-SRS-01` FR-SCN-002））。
    裁定不新增：正本在 `FYL-DESIGN-09`（D-1..D-8 · D-14）；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-pulse

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-32` |
| 文档名称 (Title) | 场景：整脉冲前馈设计（路点序列 → 逐通道电流与电压） |
| 短名 / Slug | `fylite-scenario-pulse` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-09`（D-1..D-8 · D-14）） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L4 放电运行设计（动态层：在运行点上实现放电） · `FYL-DESIGN-09`（D-1..D-8 · D-14） · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `fydesign `PulseDesign`（S10-FR-DRV-1/2：`V = clip(V_ff + V_fb, ±V_max)`，可行 = 饱和分数 0）；全放电五段登记（击穿 → 爬升 → 平顶 → 下降 → 终止，`FYTOK-SRS-01` FR-SCN-002）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-pulse-abstract)=
# 摘要 (Abstract)

〔一句话〕**整条脉冲是 D2 的序列：逐路点配置，再用电路方程算前馈电压；平顶是 LCFS 锁定下的稳态解；下降沿是一等公民。**

实际工作情景（fytok S-10 `PulseDesign`，ITER 用例「脉冲规划」）：试验前把整条放电排成路点（击穿 → 爬升 → 平顶 → 下降
→ 终止），每个路点一次 D2，路点之间用电路方程 L dI/dt + RI = V 算前馈电压，核验不越工程限值（逐线圈电流 · 电压 · 磁通）。
**归并**：`pulse` 今天是浏览器专有栏，"重复 discharge 答的问题、按路点排开"（工具登记册）；语料 `pulse-iter` 用
`code/pfwave`，而内核声明面里有 `code/pulse` 与 `code/waveform`——模板要一个真实的 code（-17 P2-c）。fytok 要求
未覆盖的段**必须报「未覆盖」**而不得外推（FR-SCN-002）；本章沿用：五段里今天覆盖爬升与平顶，击穿段是 D2 的
场零，下降与终止按 -09 D-5 是自己的问题而非上升沿取负。

**场景定义。** 线 `design`（S-L4 放电运行设计（动态层：在运行点上实现放电））；归并进本章的名字：`pulse`（浏览器专有栏）· `pfwave` 的时序用法 · `-09` 设计模式。fytok 的对应面：fydesign `PulseDesign`（S10-FR-DRV-1/2：`V = clip(V_ff + V_fb, ±V_max)`，可行 = 饱和分数 0）；全放电五段登记（击穿 → 爬升 → 平顶 → 下降 → 终止，`FYTOK-SRS-01` FR-SCN-002）。

(fylite-scenario-pulse-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-pulse-flow.svg
:name: fig-x32-flow
:align: center
:width: 100%

整脉冲前馈：脉冲脚本的路点逐个走 D2（解过的片与插值片分得清），前馈电压由电路方程与电压上限给出，平顶由 LCFS 锁定的稳态电流作边界；产物是逐通道 I(t) · V(t)，对 GSPulse 型参考校验。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x32-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 脚本 | 相位 · Ip(t) · 位形轨迹 · 路点表（D-1 一份脚本多个视图；D-2 预设是脚本） | `pulse` 文档 | — | — | ✓（页面） |
| 逐路点 | 每路点一次 D2；解过的片 vs 插值片（D-8） | `code/discharge` × N | 路点 → N 份配置 | 每路点 D2 的判据 | ✓（页面 worker `pulse`） |
| 平顶 | LCFS 锁定，PF 电流随等离子体状态（D-6）；过期的是线性化不是电流（D-7） | `code/steady_current` | 平顶片 → 稳态电流 | Δ形状 | ✓ |
| 前馈电压 | L dI/dt + RI = V；上升沿 / 下降沿各自（D-4 · D-5） | `code/waveform` · `code/pulse` | 电流轨迹 + 电路 → V(t) | 电压上限逐通道 · 磁通预算 | ◐（无模板） |
| 产物 | 逐通道 I(t) · V(t) · 0-D 走廊 → M3 的执行器波形 | 记录 | — | — | ◐ |
| 校验 | 对 GSPulse 型参考；供电 / 电压 / 磁通三账 | `fyo:ComparisonRecord` | — | 饱和分数 = 0 即可行（S10-FR-DRV-2 的形） | ◐ |
:::

〔端口〕`device`（含电路：电阻 · 互感 · 电压上限）· `pulse`（脚本）。产出：`pulse`（逐通道波形）· 逐路点 `equilibrium`。

(fylite-scenario-pulse-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
# 今天：命令行无 pulse 模板（-17 P2-c）；语料预设 pulse-iter 用 code/pfwave，门不认
fy list presets pulse-iter
fy run pulse-iter.jsonld -o rec/pulse                          # → 按名拒绝（code/pfwave）
# 可跑的是它的两块：逐路点 D2，与平顶稳态电流
fy run design discharge --device iter ip=7.5 kappa=1.6 -o rec/wp2
fy run design discharge --device iter ip=15  kappa=1.85 -o rec/wp3
```

## Python（`fylite.scenario`）

```python
# 无登记的 Python 入口（工具登记册 BROWSER_ONLY_BARS：pulse 无 Python 组合）——逐路点用 D2：
from fylite import scenario as S
wps = [S.design.discharge(device="iter", ip=ip, kappa=k) for ip, k in [(0.5e6,1.3),(7.5e6,1.6),(15e6,1.85)]]
# 前馈电压经文档门（code/waveform 在声明面里）：
from fylite.io import fydoc
ff = fydoc.complete("code/waveform", plan)
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_discharge` | 清单反射 | 逐路点 |
| — | `pulse` / `waveform` 无清单 | X-G-1 |

(fylite-scenario-pulse-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-pulse-page.svg
:name: fig-x32-page
:align: center
:width: 100%

整脉冲设计页（设计模式）：左列脉冲脚本路点表（解过的片 ✓，未解 ○）与 PF 驱动档，右上走廊（Ip · 位形轨迹 · 播放头），右下逐通道电流与电压带上限带；超限的片标红并说明是哪一路。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 路点表 · 相位 · `V_max` 是 `-09` 设计模式的既有控件；作为**计划字段**的词表**待立**（`pulse` 无模板）。

(fylite-scenario-pulse-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 每路点 | D2 的判据 | A2 §四 | ✓ |
| 前馈 | 电压上限逐通道 · 饱和分数 = 0 | `AcceptanceCriterion` | 页面侧 |
| 磁通 | 全程磁通预算 | `AcceptanceCriterion` | `code/zerod` 的磁通账 |
| 覆盖 | 未覆盖的段报「未覆盖」，不外推（FR-SCN-002） | `caveat` | 下降 / 终止段 |
| 对照 | GSPulse 型参考 | `ComparisonRecord` | `guide/stability-and-control.md`〈前馈轨迹设计〉 |

**X-3 阈值只写量过的。** 电压上限来自装置文档（今天缺电源件）；饱和分数的判据是 0 不是阈值。

(fylite-scenario-pulse-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 预设脚本 | 路点 · 相位 · PF 驱动档（反馈 / 前馈） | 导出脚本 · 绑外部轨迹 · 把整份脚本交给 FyTok 做 CVP 优化（S-10 的外层归 FyTok） |

(fylite-scenario-pulse-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `pulse` 无模板、无清单、无 Python 入口；语料 `pulse-iter` 指向门不认的 `code/pfwave` | 模板 `prescribes_code: code/pulse`（声明面已有），语料改指；`fy run design pulse` 跑通 |
| **X-G-2** | 下降与终止段未覆盖（五段登记） | 按 FR-SCN-002 的形：段有起止判据，未覆盖段报「未覆盖」 |

(fylite-scenario-pulse-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-09`（D-1..D-8 · D-14） · `docs/physics/` 相关章 · fytok `fydesign `PulseDesign`（S10-FR-DRV-1/2：`V = clip(V_ff + V_fb, ±V_max)`，可行 = 饱和分数 0）；全放电五段登记（击穿 → 爬升 → 平顶 → 下降 → 终止，`FYTOK-SRS-01` FR-SCN-002）` | `sc-pulse-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-09` 设计模式（走廊 · 播放头 · 已解片 / 插值片） | `sc-pulse-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
