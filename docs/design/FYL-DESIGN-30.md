---
document_id: FYL-DESIGN-30
title: "场景：放电方案：0-D 工况与可行域 (Scenario: Discharge Scoping: 0-D Operating Point and Feasible Region)"
shortname: fylite-scenario-scoping
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`zerod`（design 线上的「方案 0-D」）· `feasible`（可行域扫描，无模板））与 W-2 四件必备写成——
    物理算法流程图（`sc-scoping-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-scoping-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（fydesign `ZeroDScan`（S-10 快扫，E0 档）+ `DesignSpaceScreening`（S11-FR-OPT-4 可行域筛查）；`FYTOK-ADR-112` 把 S-10 / S-11 并入一份 SRS）。
    裁定不新增：正本在 `FYL-DESIGN-09`（D-2 · D-3 · D-9）· `FYL-CONOPS-00` S-L4 / S-L5；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-scoping

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-30` |
| 文档名称 (Title) | 场景：放电方案：0-D 工况与可行域 |
| 短名 / Slug | `fylite-scenario-scoping` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-09`（D-2 · D-3 · D-9）· `FYL-CONOPS-00` S-L4 / S-L5） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L4 放电运行设计 + S-L5 装置参数优化（同一设计空间的两层，见 `-23` v0.2） · `FYL-DESIGN-09`（D-2 · D-3 · D-9）· `FYL-CONOPS-00` S-L4 / S-L5 · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `fydesign `ZeroDScan`（S-10 快扫，E0 档）+ `DesignSpaceScreening`（S11-FR-OPT-4 可行域筛查）；`FYTOK-ADR-112` 把 S-10 / S-11 并入一份 SRS` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-scoping-abstract)=
# 摘要 (Abstract)

〔一句话〕**方案从 0-D 开始：给装置与目标，算工况（W · τ_E · H98 · V_loop · Q），再在两个参数轴上扫出可行域，每格说清卡在哪一路。**

实际工作情景（fytok S-10 `ZeroDScan` + S-11 `DesignSpaceScreening`）：设计一炮或一台机器都先做 0-D 定标——
Ip · 平顶时长 · P_aux · nₑ/n_GW 之间哪些组合可行，磁通够不够，密度与 β 极限撞不撞；可行的点交给 D2 配位形。
**归并**：fytok 把 S-10 与 S-11 并成一份 SRS，理由是"同一装置设计空间的两层：静态层定运行点，动态层在其上
实现放电"（ADR-112）；fylite 的 design 线因此同时承 S-L4 与 S-L5——`-23` v0.1 说"S-L5 无线"，v0.2 改为
**S-L5 归 design 线**。`zerod` 在这里是"方案 0-D"，在 A3 里是"解释性 0-D"（同一 code，输入不同）；`feasible`
无模板（扫描轴词表要先立），Python 有 `design.feasible`（S11-FR-OPT-4 ●）。

**场景定义。** 线 `design`（S-L4 放电运行设计 + S-L5 装置参数优化（同一设计空间的两层，见 `-23` v0.2））；归并进本章的名字：`zerod`（design 线上的「方案 0-D」）· `feasible`（可行域扫描，无模板）。fytok 的对应面：fydesign `ZeroDScan`（S-10 快扫，E0 档）+ `DesignSpaceScreening`（S11-FR-OPT-4 可行域筛查）；`FYTOK-ADR-112` 把 S-10 / S-11 并入一份 SRS。

(fylite-scenario-scoping-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-scoping-flow.svg
:name: fig-x30-flow
:align: center
:width: 100%

放电方案：装置与目标进 `code/zerod`（相位表与梯形波形由内核单源，D-3），扫描是回边，每格一解，可行域逐格报出卡住的通道，选定工况交给 D2 / M3。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x30-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 输入 | 装置（R · a · B₀ · 线圈上限 · 磁通预算）· 目标（Ip · 平顶 · P_aux · Q） | 端口 / 参数 | — | 线圈上限缺（F-19） | ◐ |
| 0-D 工况 | 相位表 · 梯形波形 · W · τ_E · H98 · V_loop · P_fus · Q | `code/zerod`（33 参数） | 目标 → `summary` 对 t | 定标对照 · 密度极限 · β 极限 · 磁通预算 | ✓ |
| 扫描 | 二维参数格，每格一次 0-D 解；确定性采样、参照点在区间内（S11-FR-OPT-4） | `feasible`（Python `design.feasible`；无模板） | 格 → 逐格记录 | 逐格报出卡住的通道 | ◐ |
| 可行域 | 交付可行域不是通过率：逐参数可行区间 + 卡住的限值计数 | `fyo:ComparisonRecord` 逐格 | — | 判据只有一处（P-7） | ◐ |
| 交出 | 选定工况 → D2（位形）· M3（推进） | 记录 | — | — | ✓ |
:::

〔端口〕`device`。产出：`summary`（0-D 时序）· 可行域记录。

(fylite-scenario-scoping-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
fy list scenarios zerod                                        # 33 参数
fy run design zerod --device iter ip=15 t_flat=400 paux=50 -o rec/z      # design 线的缺省场景就是 zerod
fy run design --preset zerod-iter-15ma -o rec/z15
# 可行域扫描：无模板（扫描轴词表待立，-17 P2-c）——今天是 shell 循环 + 逐格记录
for ip in 12 13.5 15 16.5; do fy run design zerod --device iter ip=$ip ne_gw=0.85 -o rec/scan/ip$ip --quiet; done
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
z = S.model.zerod(device="iter", ip=15e6, t_flat=400, paux=50e6)          # S10-FR-ENG-1 ● · S7-FR-PULSE-1/2 ●
f = S.design.feasible(device="iter", axes={"ip": (12e6, 16.5e6, 4), "ne_gw": (0.6, 1.0, 3)})   # S11-FR-OPT-4 ●
f["feasible"], f["blocked_by"]          # 逐格：可行 / 卡在哪一路
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_zerod` | 清单反射 | 0-D 工况 |
| `fylite_feasible` | 清单反射（`_manifest/feasible.jsonld`） | 可行域扫描 |
| `fylite_gaps` | `line: design` | 这条线没做的 |

(fylite-scenario-scoping-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-scoping-page.svg
:name: fig-x30-page
:align: center
:width: 100%

放电方案页（配置模式）：左列工况参数（词表生成）与扫描轴，右上 0-D 轨迹（相位表来自内核），右下可行域格，每格的「卡在哪一路」来自记录。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** `ip` · `t_flat` · `paux` · `ne_gw` · `h98` 在 `zerod` 词表里；「扫描轴」**待立**（feasible 无词表，-17 P2-c）。

(fylite-scenario-scoping-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 工况 | 密度极限 · β 极限 · 磁通预算 | `AcceptanceCriterion` × 3 | `code/zerod` 有逐项判定（`summary`） |
| 扫描 | 参照点在区间内 · 求值失败不得静默跳过（S11-FR-OPT-4） | 逐格 `ComparisonFinding` | Python 侧有 |
| 可行域 | 逐参数可行区间 + 卡住的限值计数 | `ComparisonRecord` | — |

**X-3 阈值只写量过的。** 密度与 β 极限是定标（Greenwald · Troyon），阈值即定标本身；磁通预算按装置线圈上限算，而线圈铭牌上限今天缺（F-19），该项判定标「未评估」。

(fylite-scenario-scoping-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 预设 · 装置 | 工况参数 · 相位 | 定义扫描轴（先立词表）· 绑外部定标 |

(fylite-scenario-scoping-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `feasible` 无模板、页面无栏 | 扫描轴词表立 → 模板由生成器出 → `fy run design feasible` |
| **X-G-2** | 线圈铭牌上限缺（fydoc，`TODO` F-19） | 装置文档带上限，磁通预算判定由「未评估」变有读数 |

(fylite-scenario-scoping-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-09`（D-2 · D-3 · D-9）· `FYL-CONOPS-00` S-L4 / S-L5 · `docs/physics/` 相关章 · fytok `fydesign `ZeroDScan`（S-10 快扫，E0 档）+ `DesignSpaceScreening`（S11-FR-OPT-4 可行域筛查）；`FYTOK-ADR-112` 把 S-10 / S-11 并入一份 SRS` | `sc-scoping-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-09` 配置模式的 0-D 工况栏 | `sc-scoping-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
