---
document_id: FYL-DESIGN-31
title: "场景：位形 · 线圈电流 · 击穿场零 · 电源尺寸（一个时刻） (Scenario: Configure: Shape, Coil Currents, Field Null, Supply Sizing)"
shortname: fylite-scenario-configure
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
  change: 'v0.1（全新文档，第二部场景章）：按 `FYL-DESIGN-23` v0.2 的归并（`discharge` · `breakdown`（design 侧：场零设计）· `pfwave`（电源尺寸，浏览器专有栏）· `vstab` 的读数（裕度作配置的判据之一））与 W-2 四件必备写成——
    物理算法流程图（`sc-configure-flow.svg`，由 `tools/make-scenario-figures.py` 生成）· 命令面（CLI / Python / MCP）·
    界面效果图（`sc-configure-page.svg`）· 判据与验收。参照 fytok 设计书的对应面（fyeq `inverse`（S11-FR-INV-1 静态线圈反解 · Tikhonov）；击穿在 fytok 是缺口（`plasma_initiation` 载体尚缺）；S-12 的「位形属性」类（零场品质 · 裕度））。
    裁定不新增：正本在 `FYL-DESIGN-09`（D-6 · D-7 · D-14 · D-18）· `FYL-DESIGN-13`；本章自己的编号只有 X-1.. 与 X-G-..。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-configure

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-31` |
| 文档名称 (Title) | 场景：位形 · 线圈电流 · 击穿场零 · 电源尺寸（一个时刻） |
| 短名 / Slug | `fylite-scenario-configure` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-09`（D-6 · D-7 · D-14 · D-18）· `FYL-DESIGN-13`） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` v0.2（归并与模板）· `FYL-CONOPS-00` v1.2 S-L4 / S-L5（静态层：定运行点） · `FYL-DESIGN-09`（D-6 · D-7 · D-14 · D-18）· `FYL-DESIGN-13` · `docs/examples/scenario/lines.jsonld` · `python/fylite/scenario/__init__.py` 工具登记册 · fytok `fyeq `inverse`（S11-FR-INV-1 静态线圈反解 · Tikhonov）；击穿在 fytok 是缺口（`plasma_initiation` 载体尚缺）；S-12 的「位形属性」类（零场品质 · 裕度）` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本章 `X-` 在本章内唯一（`X-1..` 判据 · `X-G-..` 缺口）；物理与页面裁定归各自正本。

(fylite-scenario-configure-abstract)=
# 摘要 (Abstract)

〔一句话〕**一个时刻一个解：目标位形反解成线圈电流，场零设计击穿，电源按需求尺寸，裕度作判据——四件合成一份「配置」。**

实际工作情景（fytok S-11 静态层 + S-10 的工程限值层）：定了工况就要配位形——目标 LCFS → PF 电流（自由边界内环 +
岭回归外环），逐线圈对限值；击穿前的场零与连接长度；电源的电流 · 电压是否够；垂直裕度够不够。这四件在实际
工作里是**同一个时刻的同一张表**。**归并**：`discharge` 与 `breakdown`（design 侧）合章；`pfwave` 按实测重复
`discharge` 的输入（不跑设计栏也给逐位相同的数），它是电源尺寸不是第二个场景；`vstab` 的读数进本章的判定块，
其闭环归 C1。`breakdown` 同时挂在 control 线：击穿**动力学**与上升段归 C1，本章只收场零**设计**。

**场景定义。** 线 `design`（S-L4 / S-L5（静态层：定运行点））；归并进本章的名字：`discharge` · `breakdown`（design 侧：场零设计）· `pfwave`（电源尺寸，浏览器专有栏）· `vstab` 的读数（裕度作配置的判据之一）。fytok 的对应面：fyeq `inverse`（S11-FR-INV-1 静态线圈反解 · Tikhonov）；击穿在 fytok 是缺口（`plasma_initiation` 载体尚缺）；S-12 的「位形属性」类（零场品质 · 裕度）。

(fylite-scenario-configure-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-configure-flow.svg
:name: fig-x31-flow
:align: center
:width: 100%

配置：装置 · 目标位形 · 工况进静态线圈反解（`code/discharge`）与击穿场零（`code/breakdown`），电源尺寸与垂直裕度是旁路，四路判定合流成一个时刻的配置。
```

:::{table} 阶段 · code · 进 → 出 · 判据 · 今天的状态（✓ / ◐ / ✗）。
:name: tbl-x31-stages
:align: left

| 阶段 | 做什么 | code / 入口 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 输入 | 装置（线圈几何 · 上限）· 目标位形（Miller / 轮廓 / X 点，或 A1 的重构边界）· 工况（D1） | 端口 / 参数 | — | 上限缺（F-19） | ◐ |
| 静态线圈反解 | 自由边界 G-S 内环 + 岭回归外环 → PF 电流 | `code/discharge`（23 参数） | 位形 + 工况 → `equilibrium` + `pf_active` 电流 | 形状误差 · 逐通道限值 | ✓ |
| 击穿场零 | 真空场零 + Townsend 判据；逐通道工程限值 | `code/breakdown`（17 参数） | 装置 + 预充电流 → 场零品质 | B_null · 连接长度 · E_tor 阈 | ✓ |
| 电源尺寸 | 读本栏输入，给电流 · 电压需求 | `pfwave`（浏览器合成；门不认 `code/pfwave`） | — | 电压上限逐通道 | ◐ |
| 垂直裕度 | k · k_ideal · γ | entry `vstab`（无 case code） | `equilibrium` → 裕度 | 裕度 > 0 | ◐ |
| 合流 | 一个时刻的配置 + 判定块（可行 / 卡在哪一路） | 记录 | → D3 路点 · M3 起点 | 判定块是一等产物（P-5） | ✓ |
:::

〔端口〕`device`（`pf_active · wall · tf`；`pf_passive` 缺，A-15）· 目标位形（参数或文档）。产出：`equilibrium` · `pf_active`（电流）· 判定块。

(fylite-scenario-configure-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · Python · MCP)

**X-1 三种写法对同一份计划**（`FYL-DESIGN-24` X-1 的同款判据）。今天的实况见下；不成立处登记在 §六。

## CLI（`fy`）

```bash
fy list scenarios discharge                                 # 23 参数
fy run design discharge --device iter ip=15 kappa=1.85 delta=0.45 -o rec/cfg
fy run design --preset discharge-iter -o rec/cfg-iter
fy run design breakdown --device iter -o rec/null              # 也是 control 线的缺省场景
fy run control --device iter -o rec/null2                      # 同一 code：control 线的缺省
# 电源尺寸：门今天不认 code/pfwave（-23 G-1 重测）
fy run design pfwave --device iter -o rec/supply               # → 按名拒绝
```

## Python（`fylite.scenario`）

```python
from fylite import scenario as S
cfg = S.design.discharge(device="iter", ip=15e6, kappa=1.85, delta=0.45)   # S11-FR-INV-1 ● · S7-FR-EQ-1/2/3 ●
nul = S.design.breakdown(device="iter")                                     # S10-FR-LIM-1/2 ●
vs  = S.control.vstab(equilibrium=cfg["equilibrium"])                       # S9-FR-EVO-1 ◐：裕度进判定块
```

## MCP（`fylite.engine.serve`，`python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"`）

| 工具 | 参数 / 来源 | 做什么 |
| :--- | :--- | :--- |
| `fylite_discharge` | 清单反射 | 静态线圈反解 |
| `fylite_breakdown` | 清单反射 | 击穿场零 |
| `fylite_vstab` | 清单反射 | 裕度 |
| — | `pfwave` 无清单 | X-G-1 |

(fylite-scenario-configure-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-configure-page.svg
:name: fig-x31-page
:align: center
:width: 100%

配置页：左列目标位形与工况（把手改 LCFS，-18 U-12 试改可撤销），中间极向截面（目标 vs 解出的 LCFS · 线圈电流色标 · 场零区），右列逐通道判定块（P-5）。
```

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 形状标量 · `ip` · `beta0` · X 点档在 `discharge` 词表；击穿参数在 `breakdown` 词表；「电源尺寸」的电压上限**待立**（pfwave 无内核词表）。

(fylite-scenario-configure-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

| 层 | 判据 | fyo 落点 | 本仓今天量得出 |
| :--- | :--- | :--- | :--- |
| 反解 | 形状误差 rms · 逐通道电流限值 | `AcceptanceCriterion` × 2 | `code/discharge` 有读数；上限缺（F-19） |
| 场零 | B_null · 连接长度 · E_tor 阈 | `AcceptanceCriterion` × 3 | `code/breakdown` 逐项判定 |
| 电源 | 电压上限逐通道 | `AcceptanceCriterion` | 页面侧 |
| 裕度 | k / k_ideal < 1 · γ τ_wall | `AcceptanceCriterion` | entry `vstab` |
| 对照 | TokSys（登记册 B-04） | `ComparisonRecord` | ✓ |

**X-3 阈值只写量过的。** 形状误差与场零品质各有读数；线圈与电源上限今天缺件，判定列相应标「未评估」而不是通过。

(fylite-scenario-configure-levels)=
# 五 · 三级用户各改什么 (Levels)

| L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- |
| 预设 · 装置 | 形状把手 · 工况 · X 点档 · 击穿参数 | 绑外部位形（fydoc 的 A-Box 边界）· 绑真空室（pf_passive） |

(fylite-scenario-configure-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 |
| :--- | :--- | :--- |
| **X-G-1** | `pfwave` 门不认、无 Python 入口（电源尺寸是浏览器合成） | 升为 `code/discharge` 的一组输出，或独立 code 有声明 |
| **X-G-2** | `vstab` 无 case code（-17 P2-c） | 内核声明 `code/vstab`，裕度进本章判定块 |
| **X-G-3** | 线圈上限 · `pf_passive` 缺件（F-19 · A-15） | 装置文档带上 |

(fylite-scenario-configure-trace)=
# 七 · 追溯 (Traceability)

| 本章 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-09`（D-6 · D-7 · D-14 · D-18）· `FYL-DESIGN-13` · `docs/physics/` 相关章 · fytok `fyeq `inverse`（S11-FR-INV-1 静态线圈反解 · Tikhonov）；击穿在 fytok 是缺口（`plasma_initiation` 载体尚缺）；S-12 的「位形属性」类（零场品质 · 裕度）` | `sc-configure-flow.svg`（生成） |
| §二 | `lines.jsonld` · `_cli.json` · `serve.py` · 工具登记册 | X-G- 命令面缺口 |
| §三 | `FYL-DESIGN-09` 配置模式（三个模式各自的首屏 D-24） | `sc-configure-page.svg`（生成） |
| §五 | `FYL-CONOPS-00` 〈用户级别〉 | 节点卡的按级折叠 |
