---
document_id: FYL-DESIGN-27
title: "场景：平衡正解与位形（给电流与位形求 ψ 与度规） (Scenario: Equilibrium Forward Solve and Geometry)"
shortname: fylite-scenario-equilibrium
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`FYL-DESIGN-10` P-20 的「边界与度规」栏（今天未落）· `code/forward` · `code/steady_equilibrium` · `code/ladder` · `code/metric` · `code/cocos` · `code/shape`）与 W-2 四件必备写成——
    物理算法流程图（`sc-equilibrium-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-equilibrium-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（S-2 平衡求解（fyeq，`FYTOK-SDD-03` F0..F4 保真档））。
    裁定不新增：正本在 `FYL-DESIGN-10`（P-20 · P-21）· `FYL-DESIGN-09`（D-6 共用正解器）；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-equilibrium

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-27` |
| 文档名称 (Title) | 场景：平衡正解与位形（给电流与位形求 ψ 与度规） |
| 短名 / Slug | `fylite-scenario-equilibrium` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-10`（P-20 · P-21）· `FYL-DESIGN-09`（D-6 共用正解器）） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L1 物理建模 · `FYL-DESIGN-10`（P-20 · P-21）· `FYL-DESIGN-09`（D-6 共用正解器） · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `S-2 平衡求解（fyeq，`FYTOK-SDD-03` F0..F4 保真档）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-equilibrium-abstract)=
# 摘要 (Abstract)

〔一句话〕**给电流与位形求 ψ 与度规：固定 / 自由边界正解，描迹成逐面度规，交出一份有名字的平衡工件。**

实际工作情景（fytok S-2）：建模的第一步是拿到一个平衡——要么给剖面假设与线圈电流做自由边界正解，要么给
边界做固定边界解；然后描迹磁面得到 M2 要的度规（gm 系数 · q · 体积 · 通量），并把 COCOS 说清楚。
**归并**：`FYL-DESIGN-10` P-20 说"边界与度规是一条栏，不是一个下拉菜单"，而今天建模页没有这条栏
（-10 G-11）；能力散在五个 code 里。本章把它们收成一个场景：**平衡正解**（fytok S-2 的 fylite 形），它是
M2 的输入、D2 的正问题（D2 是它的反问题，两者共用同一个正解器，-09 D-6）、A1 阶段 0 的对照。

**场景定义。** 线 `model`（S-L1 物理建模）；归并进本章的名字：`FYL-DESIGN-10` P-20 的「边界与度规」栏（今天未落）· `code/forward` · `code/steady_equilibrium` · `code/ladder` · `code/metric` · `code/cocos` · `code/shape`。fytok 的对应面：S-2 平衡求解（fyeq，`FYTOK-SDD-03` F0..F4 保真档）。

(fylite-scenario-equilibrium-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-equilibrium-flow.svg
:name: fig-x27-flow
:align: center
:width: 100%

平衡正解：装置 · 剖面假设 · 目标位形或线圈电流进正解（`code/forward` 自由边界 / `code/steady_equilibrium` 固定边界），描迹成度规，交出 `equilibrium` 工件；旁路是约定与往返（COCOS · g-file）。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x27-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 输入 | 装置文档 · 剖面假设（p′ · FF′ 或 β_p · l_i）· 目标位形或线圈电流 | 端口绑定 | 文档 → 文档 | — | ✓ |
| 正解 | 自由边界 Picard（边界由线圈电流定）或固定边界 | `code/forward` · `code/steady_equilibrium` | 剖面 + 电流 → `equilibrium`（ψ 图 · 边界 · 轴 · X 点） | GS 残差 < ε · 轴 / X 点定位 | ✓ |
| 描迹与度规 | 逐面 gm 系数 · q · 体积 · 通量 · l_i(3) | `code/ladder` · `code/metric` · `code/li3` · `code/xpoints` · `code/outlines` | `equilibrium` → `LADDER` 表 | 体积 / 通量守恒检验 | ✓ |
| 约定与往返 | COCOS 判定；g-file 往返；形状标量 | `code/cocos` · `code/shape` · 中间层 g-file 读写 | — | 往返逐位（登记册 V-15）· COCOS 自报 | ✓ |
| 交出 | 有名字的工件（P-21），不是总线 | 记录目录 | `equilibrium` → M2 / D2 / A1 | — | ✓ |
:::

〔端口〕`device`（`pf_active · wall · tf`）· 剖面假设作参数或 `core_profiles` · `pf_active` 电流或目标位形。产出：`equilibrium`（含 `profiles_2d/psi` · 边界 · `profiles_1d` 度规）。★今天没有名为 `equilibrium` 的场景模板：`fy run` 这一场景经计划文档（X-G-1）。

(fylite-scenario-equilibrium-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
# 今天：正解经计划文档（无场景模板，X-G-1）；页面的正解走 code/forward
fy run plan-forward.jsonld --device iter -o rec/eq            # code/forward，自由边界
fy run plan-fixed.jsonld   --device iter -o rec/eqf           # code/steady_equilibrium，固定边界

# 描迹一次：把 equilibrium 文档变成梯子（度规）
fy run plan-ladder.jsonld --bind equilibrium=rec/eq/equilibrium.fyo.jsonld -o rec/ladder

# g-file 进出（中间层，7 种格式之一）
fy data convert g137985.04000 --to fyo -o eq.fyo.jsonld
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
eq = S.design.discharge(device="iter", shape=..., ip=15e6)     # 反问题：目标位形 → 线圈电流（D2）
# 正解与描迹经文档门：
from fylite.io import fydoc
fwd = fydoc.complete("code/forward", plan)                     # equilibrium
lad = fydoc.complete("code/ladder", {"inputs": {"equilibrium": fwd["fields"]["equilibrium"]}})
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_efit` | 清单反射（`_manifest/efit.jsonld`） | 平衡（重构形的入口，正解借用它的产物读法） |
| `fylite_inspect` | `path`（g-file） | 读一份 g-file 并整形 |
| `fylite_plot` | g-file → PNG | 磁通图 |

(fylite-scenario-equilibrium-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-equilibrium-page.svg
:name: fig-x27-page
:align: center
:width: 100%

平衡正解页（目标态，-10 P-20 的栏）：左列边界与剖面档、形状滑杆；中间极向截面（ψ 等值线 · LCFS · X 点 · 线圈）；右列读数每个数带出处，「交给输运」交出命名工件。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 形状标量（R₀ · a · κ · δ）与 `ip` · `beta0` 在 `discharge` / `reconstruction` 词表里；「剖面档」与「固定 / 自由」开关**待立**（正解无模板）。

(fylite-scenario-equilibrium-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 内层 | GS 残差 < ε | `ConvergenceCriterion{metric: psi_residual}` | 内核外层迭代有残差与上限 |
| 几何 | 轴 / X 点定位；体积与通量守恒 | `AcceptanceCriterion` | `code/xpoints` · `code/metric` 有读数 |
| 往返 | g-file 读→写→读逐位 | `ComparisonFinding` | 登记册 V-15 |
| 对照 | 固定边界对 CHEASE | `ComparisonRecord` | 登记册 B-10：5.257e-02（带 8e-2） |

**X-3 阈值只写量过的。** B-10 的 5.257e-02 是量过的且"加密盒子不是收敛检验"；自由边界正解自己的 GS 残差与 D2 共用同一个数（同一正解器）。

(fylite-scenario-equilibrium-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 装置 · 预设（ITER 15 MA） | 剖面档 · 形状标量 · 固定 / 自由 | 绑自己的线圈电流 / 剖面文档；换 code（另一个内核后端） |

(fylite-scenario-equilibrium-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | 无 `equilibrium` 场景模板（能力在五个 code 里） | 生成器出 `equilibrium.jsonld`（`prescribes_code: code/forward`，固定边界为开关），`fy list scenarios equilibrium` 有表 |
| **X-G-2** | 建模页无「边界与度规」栏（-10 G-11） | 栏落地或本章图注改「实截」 |
| **X-G-3** | 度规的守恒检验无判据行 | `code/metric` 写 `ComparisonFinding{norm: volume_flux}` 进记录 |

(fylite-scenario-equilibrium-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-10`（P-20 · P-21）· `FYL-DESIGN-09`（D-6 共用正解器） · `docs/physics/` 相关章 · fytok `S-2 平衡求解（fyeq，`FYTOK-SDD-03` F0..F4 保真档）` | `sc-equilibrium-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-10` §概念图与面板（边界与度规栏，目标态） | `sc-equilibrium-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
