---
document_id: FYL-DESIGN-24
title: "场景：动理学平衡重构 (Scenario: Kinetic Equilibrium Reconstruction)"
shortname: fylite-scenario-kinetic-reconstruction
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
  change: 'v0.1（全新文档，第二部第一章 · 样板）：按 `FYL-DESIGN-23` W-2 的四件必备写动理学平衡
    重构场景——物理算法流程图（SVG `sc-kinetic-flow.svg` + 阶段表）· 命令面（CLI / MCP / Python
    三种写法，实测过的原样贴，MCP 的 `fylite_run` 收旧形参数而非计划一事如实登记为 X-G-1）·
    界面效果图（SVG `sc-kinetic-page.svg`：流程图 · 节点卡 · 控制条 · 外环面板 · 二维验收）·
    判据与验收（四层判据落到 fyo 类；阈值只写量过的）。**裁定不新增**：物理与页面裁定的正本是
    `FYL-DESIGN-21`（Q-1..Q-9）与 `-12`（P-22），落地次序在仓根 `PLAN.md` §H。本篇自己的
    编号只有 X-1..X-3（命令面三写法一致的判据）与 X-G-1..X-G-3。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-scenario-kinetic-reconstruction

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-24` |
| 文档名称 (Title) | 场景：动理学平衡重构 |
| 短名 / Slug | `fylite-scenario-kinetic-reconstruction` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；裁定正本 `FYL-DESIGN-21` / `-12`） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-DESIGN-23` W-1..W-4 · `FYL-DESIGN-21` v0.1（阶段 0..4 · 四层判据 · Q-1..Q-9）· `FYL-DESIGN-12` v1.1（P-22 · 逐道残差）· `docs/examples/scenario/reconstruction.jsonld`（模板：46 参数 · 2 开关 · 3 端口）· `python/fylite/engine/serve.py`（MCP 工具面）· `docs/guide/reconstruction.md` · `docs/guide/cli.md` · 仓根 `PLAN.md` §H |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | — |
:::

〔编号说明〕本篇 `X-` 在本篇内唯一；物理阶段编号「阶段 0..4」与页面裁定 `Q-` 属 `FYL-DESIGN-21`。

(fylite-scenario-kinetic-abstract)=
# 摘要 (Abstract)

〔一句话〕**动理学平衡重构是一条有回边的链：基准平衡 → 剖面构造 → 约束构造 → 动理学反演 →
外环，四层判据各挂各的步；三个命令面写的是同一份计划；页面是这份计划的流程图投影。**

场景定义：线 `analysis`，场景 `reconstruction`，开关 `kinetic`（`kin` · `neon` · `pointfit` 开，
`probefit` · `farfit` · `vesselfit` 关）；后验采样 `posterior` 是它的一组参数（`mcn` · `mc-*`），
不是第二个场景。磁测量-only 反演（开关 `only_magnetic`）是同一条链的**阶段 0**。
今天在本分发里**可跑的是阶段 0 与阶段 3**（`code/reconstruction`），阶段 1 部分（`code/ladder` +
`code/profile_fit`），阶段 2 部分（`code/bootstrap`），**阶段 4 的执行不在本分发**
（`FYL-DESIGN-21` G-7）。

(fylite-scenario-kinetic-flow)=
# 一 · 物理算法流程图 (The Algorithm as a Flow Graph)

```{figure} ../figures/sc-kinetic-flow.svg
:name: fig-x24-flow
:align: center
:width: 100%

动理学平衡重构的物理算法流程。实线边是数据约束（来自测量文档），虚线边是模型约束（来自公式或
给定形状），红色回边是外环，虚框节点是今天没有 code 的步（关着的节点）。判据挂在各自的步上，
不合成一个标量。
```

〔已确立·`FYL-DESIGN-21` §二〕逐阶段钉到 code：

:::{table} 阶段 · code · 端口 · 判据 · 今天的状态。
:name: tbl-x24-stages
:align: left

| 阶段 | 做什么 | code / 开关 | 进 → 出 | 判据 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| 0 基准平衡 | 磁测量-only 反演，只为把剖面诊断映射到磁面 | `code/reconstruction` · `only_magnetic` | `device` + `measurements` → `equilibrium`（ψ · 边界 · q · l_i） | 内层：GS 残差 | ✓ |
| 1 剖面构造 | 取诊断 · 时间窗均值 · 映射到 ψ_N · 拟合（GCV 定阶）· 分离面对齐 · Z_eff | `code/ladder` · `code/profile_fit`（Python 侧 `S.analysis.profit`）；ELM 相位平均 · Tₑ,sep 对齐 **无 code** | `equilibrium` + `thomson` → `pressure` 文档（带出处） | — | ◐ |
| 2 约束构造 | p = nₑTₑ + Σnᵢ Tᵢ + p_fast；j∥ = j_bs + …；MSE 的 Er 修正 | `code/bootstrap`（Redl-2021）；p_fast 是给定形状 `pfast` / `pfastpk`；`tite` · `zeff` 是参数；MSE **无** | `core_profiles` + `equilibrium` → `current`（自举） | — | ◐ |
| 3 动理学反演 | P′ 固定 · FF′ 自由（列均衡 + 截断谱）· 压强行与磁测量共进 χ² | `code/reconstruction` · `kinetic` | `measurements` + `pressure`（拒收 `derived-from-reconstruction`）→ `equilibrium` · `summary`（`chi2`） | 内层 GS 残差 · 反演层 χ² 饱和 | ✓ |
| 4 外环 | 新平衡 → 重映射 → 重算自举 → 回阶段 3 | `fyo:ScenarioLoop`（`converges_by`）；执行在内核仓 `oracles/loop.py` | 轮记录（含 `fylite:state`） | 外环：Δq₀ · Δq₉₅ < 阈值 | ✗（本分发） |
| 后验 | 二维验收 + 一致性检验 | `fyo:ComparisonRecord` | 阶段 0 vs 阶段 3 的记录 | 后验：GS 残差 × 磁 χ² | ◐（无本仓阈值） |
:::

(fylite-scenario-kinetic-data)=
## 数据流 (Ports)

〔已确立·模板 `reconstruction.jsonld`〕三个端口：`device`（要求装置清单：`pf_active` · `wall` ·
`magnetics` · `tf`）· `measurements`（主端口：`magnetics` · `pf_active` · `tf`；三级解析
`--input` → 语料切片 → mdsip 取回，`-17` E-15）· `pressure`（可选；带 `derived-from-reconstruction`
出处的剖面**按名拒收**，`-12` P-22）。产出：`equilibrium` · `summary` 两份 fyo 文档进记录目录。
★EAST 绑定表**无 Thomson**，动理学一档的剖面只能 `--input`（`-17` G-8）。

(fylite-scenario-kinetic-commands)=
# 二 · 命令面：三种写法，一份计划 (CLI · MCP · Python)

**X-1 三种写法对同一份计划。** CLI 的六层合成、Python 的入口、MCP 的工具参数，解析出的
计划**逐字段相同**才算一个场景有三个面；不同即登记为缺口。今天：CLI 与 Python 经同一模板，
**MCP 不是**（X-G-1）。

## CLI（`fy`，实测 2026-09-12 的命令形）

```bash
# 这条场景收什么：46 个参数 · 2 个开关 · 3 个端口，全表
fy list scenarios reconstruction

# 阶段 0：磁测量-only（开关 only_magnetic），测量从语料切片或 mdsip 解析
fy run analysis reconstruction --device east shot=137985 time=4.0 --only_magnetic -o rec/s0

# 阶段 3：动理学（开关 kinetic），压强剖面绑到 pressure 端口
fy run analysis reconstruction --device east shot=137985 time=4.0 --kinetic \
   --bind pressure=fit.fyo.jsonld pfast=0.12 pfastpk=2.0 tite=0.9 zeff=1.8 -o rec/s3

# 用自己取的测量文档而不是取数（--input 是三级解析的第一级）
fy run analysis reconstruction --device east --input meas.fyo.jsonld --kinetic -o rec/s3

# 参数记法：key=value ≡ --key=value；--flag ≡ flag=true；未知参数按名拒绝并指向全表
fy run analysis reconstruction maxit=400 caltol=1e-6 basis=8
```

★`--only_magnetic` / `--kinetic` 是模板声明的**开关**（`-17` E-18），展开成六个布尔参数
（`kin` · `neon` · `probefit` · `pointfit` · `farfit` · `vesselfit`）；开关名与参数名都来自模板，
`fy list scenarios reconstruction` 打印的表就是唯一的权威。
★外环今天**没有命令**：`fy run` 一份计划一个 code（`-21` G-1）；按 `PLAN.md` H-12 落地后，
回边的每一轮就是一次 `fy run … --resume-from rec/<上一轮>`。

## Python（`fylite.scenario`，与指南同）

```python
from fylite import fyo
from fylite import scenario as S

meas = fyo.as_measurements("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld", 4.0)
fit  = S.analysis.profit(x, y, sigma_frac=0.05)          # 阶段 1：移位勒让德基 + GCV
r    = S.analysis.reconstruction(meas, pressure=fit)      # 阶段 3：r["q0"], r["q95"], r["chisq"], r["psi"]
```

经文档门的等价写法（一份计划进、一份记录出，与 `fy run` 同一条路）：

```python
from fylite.io import fydoc
rec = fydoc.case_json(plan)          # plan: fyo:ScenarioSpecification（dict 或 JSON 文本）
rec["run_state"], rec["fylite:state"]
```

## MCP（`fylite.engine.serve`，stdio）

宿主配置里一行启动：

```bash
python -c "from fylite.engine.serve import mcp_stdio; raise SystemExit(mcp_stdio())"
```

与本场景相关的工具（`list_mcp_tools()` 实测）：

| 工具 | 参数 | 做什么 |
| :--- | :--- | :--- |
| `fylite_run` | `shot` · `time_s` · `input`（测量文档）· `east` · `server` · `point` · `pressure` · `thomson_ne` · `probes` · `out` | 重构一个平衡；`point` / `pressure` 开动理学约束；产 g-file |
| `fylite_open` | `fylite://<run-id>/<port>` · `index` · `first` | 读记录里的数据（摘要 + 句柄，值不进对话） |
| `fylite_inspect` | `path` · 保留字段 | 读一份产物（g-file / 记录）并整形 |
| `fylite_plot` | 文件 · 输出图 | g-file 的磁通图 |
| `fylite_gaps` | `line: analysis` | 这条线没做的是什么 |
| `fylite_efit` | 由清单反射 | `_manifest/efit.jsonld` 的入口 |
| `fylite_kinetic_reconstruction` | 由清单反射 | **`executable: false`**（外环不在本分发） |

**X-G-1 MCP 的 `fylite_run` 收的是旧形参数（`shot` / `time_s` / `point` / `pressure` …），不是一份
计划。** 于是 X-1 在 MCP 上不成立：同一个动理学反演，CLI 说 `--kinetic pfast=0.12`，MCP 说
`pressure: true`，两者之间没有可核的对应。关闭判据：`fylite_run` 收 `plan`（一份
`fyo:ScenarioSpecification`，或 `line` + `scenario` + `params` 三件经同一合成器），且记录带
`fylite:state`。

(fylite-scenario-kinetic-page)=
# 三 · 界面效果图 (The Page)

```{figure} ../figures/sc-kinetic-page.svg
:name: fig-x24-page
:align: center
:width: 100%

动理学平衡重构页（概念图，数值示意）。上：控制条五个动作（运行到此 · 单步 · 从此重跑 · 断点 ·
取消，没有「跳过」）与按步实测的进度。左中：流程图——节点是计划的步，状态从记录读（绿 = 已算，
蓝 = 当前，橙虚 = 已算·过期，灰虚 = 关着的节点），数据边实线、模型边虚线，红色回边是外环。
右中：节点卡——状态 · 出处 · 判据读数，L2 的模型档位面板（改档位 = 改计划），L3 的换节点，
以及来自记录 `caveat` 的告警。左下：外环面板，逐轮 q₀ / q₉₅，收敛由计划的 `converges_by` 判。
右下：二维验收散点，横轴 GS 残差、纵轴磁 χ²，验收区一块——本仓阈值未定，图上仅示意。
```

〔已确立·正本 `FYL-DESIGN-21` Q-1..Q-9〕图上每一件对应一条裁定：图是计划的投影、页面不持
第二份图（Q-1）；节点状态从记录读、过期是第八种显示（Q-2）；判据读数逐节点、页面不判（Q-3）；
五个动作无「跳过」（Q-4）；外环是回边、每轮一份记录（Q-5）；三级各一层（Q-6）；缺失诊断是
可见的关着的节点、数据边与模型边两种线（Q-7）；告警来自记录（Q-8）；宿主驱动、无调度器（Q-9）。

**X-2 效果图里的每个控件在词表里有条目，或标「待立」。** 图上的 `pfast` · `pfastpk` · `tite` ·
`zeff` · `maxit` 都在模板词表（46 条）里；「自举公式」的档位选择（Redl-2021 / Sauter）**待立**——
今天 `code/bootstrap` 只有 Redl-2021（X-G-2）。

(fylite-scenario-kinetic-criteria)=
# 四 · 判据与验收 (Criteria and Acceptance)

〔已确立·`FYL-DESIGN-21` §三〕四层判据语义互不等价，各为一个 fyo 判据实例：

| 层 | 判据 | fyo 落点 | 本仓今天量得出 | 参照量级（不作阈值） |
| :--- | :--- | :--- | :--- | :--- |
| 内层 GS | Picard 迭代 ψ 归一化残差 | `ConvergenceCriterion{metric: psi_residual}` 挂阶段 3 | 内核外层迭代有残差与上限（`maxit` · `caltol` · `closit` / `clostol`，含义待 code 表自报） | 10⁻⁴（DIII-D） |
| 反演层 | 总 χ² 与分诊断 χ² 饱和 | 同一步第二个 `ConvergenceCriterion{metric: chi2_saturation}` | `chi2` 在记录 `summary`；逐道残差表在页面 | 装置依赖 |
| 外环 | Δp · Δj∥ · Δq₀ · Δq₉₅ < 阈值 | `ScenarioLoop.converges_by` | `convergence_panel` 给 q₀ / q₉₅ / Δq₀ / converged（簿记在，执行不在） | 2–3 轮后 < 1–2 % |
| 后验 | GS 残差低到可供 MHD 稳定性码 | `AcceptanceCriterion` × 2 + `ComparisonRecord`（二维） | **本仓反演解的 GS 残差未量**（`PLAN.md` H-14a） | — |

**X-3 阈值只写量过的。** 上表最后一列是 DIII-D 生态的典型量级，**不是本仓阈值**；本仓阈值
在 H-14a 量出之前留空。移植到 MSE 缺失 · CER 稀疏的装置（随包的 EAST 正是），阶段 2 的电流约束
是模型约束，**收敛不蕴含正确**（`-21` §八）。

(fylite-scenario-kinetic-levels)=
# 五 · 三级用户各改什么 (Levels)

| 阶段 | L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- | :--- |
| 0 | 装置 · 炮号 · 时刻 | `basis` · `vesselfit` · 通道权重 | 换测量文档（`--input`） |
| 1 | — | 拟合阶数 / GCV · 时间窗 · Tₑ,sep（落地后） | 绑自己的剖面文档 |
| 2 | — | `pfast` · `pfastpk` · `tite` · `zeff` · 自举公式（待立） | 绑 NEO / NUBEAM 的产物到 `current` / `pressure` |
| 3 | — | `kin` / `pointfit` / `neon` · `noise` · `maxit` | 换 code（另一个内核后端） |
| 4 | 预设的轮数上限 | 收敛阈值 · 轮数上限 | 改回边 · 导出整份计划 |

(fylite-scenario-kinetic-gaps)=
# 六 · 缺口 (Gaps)

| | 缺口 | 关闭判据 | 出处 |
| :--- | :--- | :--- | :--- |
| **X-G-1** | MCP 的 `fylite_run` 不收计划（§二） | `fylite_run` 收 `plan` 或经同一合成器；三面解析出的计划逐字段相同 | X-1 |
| **X-G-2** | 自举公式无档位（只有 Redl-2021） | `code/bootstrap` 声明一个 `formula` 参数并至少两档，或明写只此一档 | X-2 |
| **X-G-3** | 外环无命令、页面无流程图——本章的图今天是**设计图**，不是截图 | `PLAN.md` H-1..H-6（Q0 只读的图）关闭后本章图注改为「实截」 | `PLAN.md` §H |
| （指针） | 阶段 1.2 / 1.4 / 2.3 无 code · MSE/CER/ECE 不在卷宗 · knot 对应未核 · GS 残差未量 | 见 `FYL-DESIGN-21` G-2 / G-3 / G-4 / G-6 与 `PLAN.md` H-14a..H-18 | — |

(fylite-scenario-kinetic-trace)=
# 七 · 追溯 (Traceability)

| 本篇 | 上游 | 下游 |
| :--- | :--- | :--- |
| §一 · §四 | `FYL-DESIGN-21` §二 / §三 · `docs/guide/reconstruction.md` 〈反演是怎么分层的〉 | `sc-kinetic-flow.svg` |
| §二 | `reconstruction.jsonld` 模板 · `docs/guide/cli.md` · `serve.py` `_MCP_CURATED` · `docs/guide/python.md` | X-G-1 |
| §三 | `FYL-DESIGN-21` Q-1..Q-9 · `-18` U-8..U-11 | `sc-kinetic-page.svg`；`PLAN.md` H-2..H-6 |
| §五 | `FYL-CONOPS-00` 〈用户级别〉· `-21` §六 | 节点卡的按级折叠 |
