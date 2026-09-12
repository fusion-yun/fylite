---
document_id: FYL-DESIGN-29
title: "场景：含时演化与仿真推进（一条时间轴，两档保真度） (Scenario: Time-Dependent Evolution and Simulation)"
shortname: fylite-scenario-evolve
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`evolve` · `sim`（交互推进）· `zerod` 的时间推进档 · `coupled` 的时序形）与 W-2 四件必备写成——
    物理算法流程图（`sc-evolve-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-evolve-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（S-7 时序演化（fypredict P3 `PulseEvolution` 全物理 1.5-D）；与 S-10 的边界以保真档分（`FYTOK-SRS-07` §S-7 / S-10 边界））。
    裁定不新增：正本在 `FYL-DESIGN-09`（D-11..D-17 · D-22）· `FYL-DESIGN-10`（P-19）· `FYL-DESIGN-18`（U-8..U-11）；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-evolve

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-29` |
| 文档名称 (Title) | 场景：含时演化与仿真推进（一条时间轴，两档保真度） |
| 短名 / Slug | `fylite-scenario-evolve` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-09`（D-11..D-17 · D-22）· `FYL-DESIGN-10`（P-19）· `FYL-DESIGN-18`（U-8..U-11）） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L1 物理建模（页面在 S-L4 的仿真模式，-09 D-22） · `FYL-DESIGN-09`（D-11..D-17 · D-22）· `FYL-DESIGN-10`（P-19）· `FYL-DESIGN-18`（U-8..U-11） · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `S-7 时序演化（fypredict P3 `PulseEvolution` 全物理 1.5-D）；与 S-10 的边界以保真档分（`FYTOK-SRS-07` §S-7 / S-10 边界）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-evolve-abstract)=
# 摘要 (Abstract)

〔一句话〕**一个应用只有一条时间轴：0-D 与 1.5-D 是它的两档保真度，批式与交互是它的两种 cadence，断点就是记录。**

实际工作情景（fytok S-7 `PulseEvolution`）：给起点与执行器波形，推进热 · 密度 · 动量 · 电流通道，每 k 步重解一次平衡
（couple），锯齿与台基按档位；研究者要么批式跑完整例（`evolve`，114 参数，19 份预设），要么在页面上拖滑块改未来
看走廊（`sim`）。**归并**：`sim` 不设模板（交互推进是浏览器的档位不是批式动作）；`zerod` 的时间推进与 1.5-D 是
同一时间轴上的两档（-09 D-22）；`coupled` 的时序形是 `couple` 参数。fytok 把 S-7 与 S-10 的边界画在**保真档**上
（全物理 1.5-D 预测归 S-7，0-D / 0.5-D 快扫设计引擎归 S-10）——本章按同一条线：1.5-D 推进归 model 线，
0-D **方案**快扫归 D1；而 0-D 作为推进的低保真档留在本章的开关上。页面上它住在放电设计页的仿真模式
（-09 D-22，建模页不含时 -10 P-19，搬栏未落 -10 G-11）。

**场景定义。** 线 `model`（S-L1 物理建模（页面在 S-L4 的仿真模式，-09 D-22））；归并进本章的名字：`evolve` · `sim`（交互推进）· `zerod` 的时间推进档 · `coupled` 的时序形。fytok 的对应面：S-7 时序演化（fypredict P3 `PulseEvolution` 全物理 1.5-D）；与 S-10 的边界以保真档分（`FYTOK-SRS-07` §S-7 / S-10 边界）。

(fylite-scenario-evolve-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-evolve-flow.svg
:name: fig-x29-flow
:align: center
:width: 100%

含时演化：起点与执行器波形进两档推进（0-D `code/zerod` · 1.5-D `code/evolve`），步是 U-8 的预算单元（断点即记录），平衡交替是模型边与回边，仿真档把滑块变成下一步的输入。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x29-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 起点 | `equilibrium + core_profiles`，或 Miller 标量 · 抛物剖面装配 | 端口绑定 / 内核装配（K-3） | 文档 → 状态 | 出处齐 | ✓ |
| 执行器 | Ip · P_aux · nₑ · 燃料对 t（波形），或滑块（仿真档，改未来不重算过去 D-12） | `code/waveform` · 页面 | 波形 → 每步输入 | — | ✓ |
| 0-D 档 | 集总能量 · 粒子 · 磁通账 | `code/zerod` | → `summary` 对 t | 磁通预算：能维持多久（D-17） | ✓ |
| 1.5-D 档 | 热 · 密度 · 动量 · 电流通道；锯齿 · 台基 · 闭包档 | `code/evolve`（entry `evolve_heat`） | → `core_profiles` · `core_transport` · `equilibrium` 逐片 | 每步能量账（实测 1.2e-13）· dt 上限 | ✓ |
| 步 | 步预算 · 进度按步实测 · 取消落在步界 · 断点 = 记录 | `run.js` / `fy run --resume-from` | 每步一份记录片 | 40 ≡ 20 + 续 20 逐位（常数与新经典闭合均已钉住） | ✓ |
| 平衡交替 | 每 k 步解一次平衡，新度规回到推进 | `couple` → `code/refit` · `code/steady_current` | — | Δψ · Δq 相对变化 | ◐ |
| 交出 | 记录集（含 `fylite:state`）；IMAS HDF5（`FYL-REPORT-06` §14.5） | 中间层 | — | h5py 独立读回一致 | ✓ |
:::

〔端口〕`device`（Miller 装配）或 `equilibrium` · `core_profiles`（起点）· `pulse` / 波形 · `core_sources`（表或 code）。产出：四份 IDS 文档逐片 + `fylite:state`。

(fylite-scenario-evolve-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
fy list scenarios evolve                                         # 114 参数全表（闭包档 · 通道 · 锯齿 · 台基 …）
fy run model --preset evolve-iter-15ma -o rec/e15                 # 400 步至 8 s，0.2 s；IMAS HDF5 出（预设自带）
fy run model evolve --device east nsteps=200 dt=0.002 closure=neoclassical ch-density=true -o rec/e1
# 断点就是记录：N 步 ≡ k 步 + 续 (N−k) 步
fy run docs/examples/evolve/evolve-default.jsonld nsteps=20 -o rec/a
fy run docs/examples/evolve/evolve-default.jsonld nsteps=20 --resume-from rec/a -o rec/b
# 0-D 档：同一时间轴的低保真档
fy run model zerod --device iter -o rec/z
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
r = S.model.evolve(device="iter", nsteps=400, dt=0.02, closure="stiff", couple=10)   # S7-FR-TR-1..5 ●
z = S.model.zerod(device="iter")                                                  # 0-D 档
from fylite.engine import resume
st = resume.carried("rec/a")            # 读交接单（settings · documents · step · t · lag_reset）
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_evolve` | 清单反射（`_manifest/evolve.jsonld`） | 批式推进 |
| `fylite_zerod` | 清单反射 | 0-D 档 |
| `fylite_open` | `fylite://<run>/core_profiles` · `index` | 读某一步的剖面（值不进对话） |

(fylite-scenario-evolve-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-evolve-page.svg
:name: fig-x29-page
:align: center
:width: 100%

仿真推进页（放电设计页的仿真模式，1.5-D 档）：左列执行器滑块（自当下生效）与档位，右上走廊（右缘 = 现在），右下现在这一片的剖面；解过的片实心、插值片空心（D-8）。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** `dt` · `nsteps` · 闭包档 · 通道开关 · `P_aux` · `nₑ` 都在 `evolve` 词表（114 条）里；「保真度开关」（0-D / 1.5-D）作为一个计划字段**待立**（今天是两个 code）。

(fylite-scenario-evolve-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 每步 | 能量账 · dt 上限 | `ConvergenceCriterion{metric: energy_balance}` | 1.2e-13（ITER 15 MA 验收算例） |
| 断点 | N ≡ k + 续 (N−k) 逐位 | 断点闸（`-18` §十三） | 常数闭合 0.000e+00；新经典闭合已钉（G-1 关闭） |
| 平衡交替 | Δψ · Δq 相对变化 | `ScenarioLoop.converges_by` | ◐ |
| 对照 | JINTRAC 102530 平顶 / 爬升 · TORAX · CASE-20 | `ComparisonRecord` | 登记册（`FYL-REPORT-04` 4.74 → 5.20 %） |

**X-3 阈值只写量过的。** 能量账 1e-13 量级与逐位续跑是实测；对拍成绩（5.20 %）是归因清单挂着的数，不是阈值。

(fylite-scenario-evolve-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 预设（19 份）· 装置 | 闭包档 · 通道 · 锯齿 / 台基档 · 执行器波形 · dt | 绑外部沉积表（NUBEAM 的产物）· 改回边（couple 频次）· 导出整份计划 |

(fylite-scenario-evolve-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | 含时演化栏搬进放电设计页未落（-10 G-11）；本章图是目标态 | 搬栏落地或图注改「实截」 |
| **X-G-2** | 0-D / 1.5-D 是两个 code，不是一个开关 | 计划字段 `fidelity` 由合成器展开为 code 选择（-09 D-22） |
| **X-G-3** | 页面尚不产生记录（`PLAN.md` G-4），仿真档的断点无可存之物 | 与 `PLAN.md` H-7 同出口 |

(fylite-scenario-evolve-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-09`（D-11..D-17 · D-22）· `FYL-DESIGN-10`（P-19）· `FYL-DESIGN-18`（U-8..U-11） · `docs/physics/` 相关章 · fytok `S-7 时序演化（fypredict P3 `PulseEvolution` 全物理 1.5-D）；与 S-10 的边界以保真档分（`FYTOK-SRS-07` §S-7 / S-10 边界）` | `sc-evolve-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-09` 仿真模式 · `FYL-DESIGN-18` U-8..U-11（执行与断点） | `sc-evolve-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
