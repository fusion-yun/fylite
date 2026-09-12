---
document_id: FYL-DESIGN-28
title: "场景：定态输运与闭包（给 χ 求 T） (Scenario: Steady-State Transport and Closures)"
shortname: fylite-scenario-transport
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`transport` · `coupled`（evolve / transport 的 `couple` 参数）· `tglf`（闭包的一档））与 W-2 四件必备写成——
    物理算法流程图（`sc-transport-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-transport-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（S-3 输运求解 + S-4 多物理收敛（fypredict P1 稳态收敛环，`FYTOK-SRS-07` S7-FR-LOOP-1））。
    裁定不新增：正本在 `FYL-DESIGN-10`（P-19 · P-28）· `FYL-DESIGN-16` K-2（档位是声明）；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-transport

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-28` |
| 文档名称 (Title) | 场景：定态输运与闭包（给 χ 求 T） |
| 短名 / Slug | `fylite-scenario-transport` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-10`（P-19 · P-28）· `FYL-DESIGN-16` K-2（档位是声明）） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L1 物理建模 · `FYL-DESIGN-10`（P-19 · P-28）· `FYL-DESIGN-16` K-2（档位是声明） · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `S-3 输运求解 + S-4 多物理收敛（fypredict P1 稳态收敛环，`FYTOK-SRS-07` S7-FR-LOOP-1）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-transport-abstract)=
# 摘要 (Abstract)

〔一句话〕**给 χ 求 T：在一份度规上解定态输运，闭包按档位选，通量匹配与平衡交替是两条可选的外环。**

实际工作情景（fytok S-3 / S-4，fypredict P1）：给定平衡与源项，选一档闭包（常数 · 刚性 · 新经典 · TGLF），解到
定态；要自洽就在外环做通量匹配（TGYRO 型）或平衡—输运交替（Picard，S7-FR-LOOP-1 的显式残差与上限）。
**归并**：`coupled` 与 `tglf` 都不设独立模板（`-17` E-8）——前者是本场景的一个外环参数 `couple`，后者是
闭包的一档；本章把它们放回它们所属的环，不另立场景。与 A3 是同一条能量方程的两个方向（-10 P-28），
与 M3 的差别只在有没有时间轴（-10 P-19）。

**场景定义。** 线 `model`（S-L1 物理建模）；归并进本章的名字：`transport` · `coupled`（evolve / transport 的 `couple` 参数）· `tglf`（闭包的一档）。fytok 的对应面：S-3 输运求解 + S-4 多物理收敛（fypredict P1 稳态收敛环，`FYTOK-SRS-07` S7-FR-LOOP-1）。

(fylite-scenario-transport-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-transport-flow.svg
:name: fig-x28-flow
:align: center
:width: 100%

定态输运：度规 · 源项 · 边界条件进闭包档位与 `code/transport` 的 Picard 定态解；两条可选外环——通量匹配（冻结 χ）与平衡交替（couple）；产物对 JINTRAC / TGYRO 列。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x28-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 输入 | 度规（M1 工件或 Miller 标量装配）· 源项（表或 code）· 边界条件（含台基档） | 端口绑定 · `code/beam` / `code/rf_ray` / ADAS | 文档 → 文档 | — | ✓ |
| 闭包 | 常数 / 刚性 / 新经典 / TGLF（扩展面） | `closure` 参数 · `code/bootstrap` · `turbulence`（`fylite_ext`） | 剖面 + 度规 → χ · D · j_bs | 档位是参数不是插件 | ✓ |
| 定态解 | θ-隐式有限体积 · Picard | `code/transport`（entry `transport`，19 参数） | 上述 → `core_profiles` · `core_transport` | 残差 < ε · 迭代上限（刚性闭包内迭代 2–28 次） | ✓ |
| 通量匹配（外环） | 冻结 χ，目标通量，TGYRO 型 | 宿主外环（`_flux_match_answer`） | 每轮一份记录 | 匹配区逐点 ±3.5 %（CASE-20 实测） | ✓（Python 侧） |
| 平衡交替（外环） | 每轮解一次平衡，在新度规上弛豫 | `couple` 参数 → `code/refit` / `code/steady_current` | 每轮一份记录 | Δψ · Δq 相对变化 | ◐ |
| 对照 | JINTRAC / TGYRO 逐列 | `fyo:ComparisonRecord` | — | 登记册 B-02 / B-03 | ✓ |
:::

〔端口〕`device`（Miller 装配用）或 `equilibrium`（M1 工件）· `core_sources`（可选）· `transport_inputs`。产出：`core_profiles` · `core_transport` · `summary`。

(fylite-scenario-transport-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
fy list scenarios transport                                   # 19 参数全表
fy run model transport --device iter chi0=0.55 closure=stiff -o rec/tr
fy run model --preset transport-iter-15ma -o rec/tr15            # 语料预设：一次定态解，Picard 2 轮收敛（-06 §14.2）
fy run model transport --bind equilibrium=rec/eq/equilibrium.fyo.jsonld -o rec/tr2   # 在 M1 的工件上解
# 通量匹配与平衡交替是参数，不是别的场景：
fy run model transport flux_match=true couple=true max_rounds=6 -o rec/tr3
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
r = S.model.transport(device="iter", chi0=0.55, closure="stiff")         # S7-FR-TR-1..5 ●
c = S.model.coupled(device="iter", rounds=6)                              # S7-FR-LOOP-1 ●：平衡—输运交替
# TGLF 档：闭包参数，同一入口
r2 = S.model.transport(device="iter", closure="tglf")
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_transport` | 清单反射 | 定态解 |
| `fylite_coupled` | 清单反射 | 平衡—输运交替 |
| `fylite_tglf` · `fylite_neo` | 清单反射，**`executable: false`** | 闭包单独求值（fytok S-12 的形），今天在神谕树 |

(fylite-scenario-transport-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-transport-page.svg
:name: fig-x28-page
:align: center
:width: 100%

定态输运页：左列闭包与边界（控件由词表生成），右上剖面对参照列，右下逐轮收敛与通量失配（读数来自记录）。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 闭包档 · `chi0` · 临界梯度 · `ρ_b` · 边界温度在 `transport` / `evolve` 词表里；「通量匹配 on/off」作为计划字段**待立**（今天是 Python 外环的参数）。

(fylite-scenario-transport-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 内层 | Picard 残差 < ε · 迭代上限 | `ConvergenceCriterion{metric: profile_residual}` | 记录 `notes` 有残差与轮数 |
| 通量匹配 | 逐点失配 · 匹配区 | `ConvergenceCriterion{metric: flux_mismatch}` | CASE-20：±3.5 %，最差残差 8.06e-3，`converged 1` |
| 平衡交替 | Δψ 二维 RMS 或 Tₑ 轮间相对 RMS（S7-FR-LOOP-1 二择一） | `ScenarioLoop.converges_by` | ◐ |
| 对照 | 对 JINTRAC 102530 · TGYRO 列 | `ComparisonRecord` | B-02 / B-03；TGLF 低 ky 增长率四位小数（`FYL-REPORT-04`） |

**X-3 阈值只写量过的。** ±3.5 % 与 8.06e-3 是 CASE-20 量出的读数，不是承诺；S7-FR-LOOP-1 的 `tolerance` / `max_iter` 在本仓对应 `caltol` / `maxit` 一类参数，含义待 code 表自报。

(fylite-scenario-transport-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 装置 · 预设 | 闭包档 · `chi0` · 边界与台基档 · 外环开关 | 绑自己的度规 / 源项文档；绑外部闭包的产物（TGLF 表） |

(fylite-scenario-transport-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | 通量匹配与平衡交替在 Python 侧是外环函数，`fy run` 无对应参数 | 模板声明 `flux_match` · `couple` · `max_rounds`，宿主逐轮驱动（`PLAN.md` H-12 同机制） |
| **X-G-2** | `fylite_tglf` / `fylite_neo` 在神谕树，MCP 面标 `executable: false` | 按内核仓 `FYL-REPORT-08` P-2 升格到条目面或扩展面 |

(fylite-scenario-transport-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-10`（P-19 · P-28）· `FYL-DESIGN-16` K-2（档位是声明） · `docs/physics/` 相关章 · fytok `S-3 输运求解 + S-4 多物理收敛（fypredict P1 稳态收敛环，`FYTOK-SRS-07` S7-FR-LOOP-1）` | `sc-transport-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-10` 输运栏 · `FYL-DESIGN-18` U-1（141 个控件由词表生成） | `sc-transport-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
