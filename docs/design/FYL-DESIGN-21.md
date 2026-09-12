---
document_id: FYL-DESIGN-21
title: "动理学反演场景与流程图页面 (The Kinetic-Reconstruction Scenario, and Its Page as a Flow Graph)"
shortname: fylite-kinetic-flow
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
  change: 'v0.1（全新文档）：按用户给出的「层级分解 + 收敛判据分层」描述（OMFIT 三条路径 ·
    阶段 0..4 · 四层收敛判据 · 失效模式 · DIII-D 偏置提示）完善动理学反演场景的设计——把每
    一阶段钉到 fylite 今天的 code / 端口 / fyo 类上，标明已落地 · 部分 · 缺；把四层判据落成
    fyo 的 `ConvergenceCriterion` / `AcceptanceCriterion`，二维验收（GS 残差 × 磁 χ²）为
    一份 `ComparisonRecord`。同批重新规划分析页的反演部件：**页面是一张流程图**——节点是
    计划的步、边由端口绑定推出、状态从记录读、判据读数逐节点显示、五个控制动作、外环是
    一条回边；三级用户各在图上有自己的一层。裁定 Q-1..Q-9，缺口 G-1..G-8，三期两道闸。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-kinetic-flow

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-21` |
| 文档名称 (Title) | 动理学反演场景与流程图页面 |
| 短名 / Slug | `fylite-kinetic-flow` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-12 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | concept (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No（信息性；提案见 §十） |
| 生命周期状态 (Status) | WD |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 受众 (Audience) | physics researchers / FyTok developers / maintainers |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | 用户描述 2026-09-12（OMFIT 三条路径 · 阶段 0..4 · 四层判据 · 失效模式）· `FYL-CONOPS-00` v1.2 S-L2 与〈用户级别〉· `FYL-DESIGN-12`（分析页 P-9 / P-22 / P-23 / P-29）· `FYL-DESIGN-16` S-1..S-6 · `FYL-DESIGN-18` U-8..U-11 / U-26 · `FYL-REPORT-06` §8–§9 · `FYL-REPORT-07` §8–§9 · `docs/physics/03-reconstruction.md` · 登记册 `B-06` |
| 取代关系 (Supersedes / Superseded by) | 取代 `FYL-DESIGN-12` 对**反演部件**的界面布局（四栏并列 → 流程图）；`-12` 的 P- 裁定（P-9 · P-22 · P-23 · P-29）**照旧**，本篇引用不抄 |
:::

(fylite-kinetic-flow-intro)=
# 动理学反演场景与流程图页面 (The Kinetic-Reconstruction Scenario as a Flow Graph)

〔一句话〕**动理学反演是一条有回边的链，不是一个按钮。** 五个阶段各有自己的输入、产物与
收敛判据，判据的语义互不等价；页面因此画成一张流程图——节点是计划的步，边由端口绑定
推出，状态从记录里读，判据读数逐节点显示——而不是四条并列的栏。三级用户在同一张图上
各有自己的一层：初级按「运行」，中级点开节点换模型，高级换节点或把图导出去。

〔为什么这是当下的问题〕`FYL-DESIGN-12` 把分析页画成四栏（剖面拟合 · 平衡反演 · 时间序列 ·
批处理），栏与栏之间靠「发布 / 取用」交接（`-12` G-2「发布不唤醒读者」）。那个形对**单次
拟合**够用，对**动理学反演**不够：动理学反演的核心是**剖面 → 约束 → 反演 → 重映射 → 再
约束**这条回边，而四栏并列把回边藏进了用户的手工操作里——哪一步重跑了、哪一步因此过期
了、外环走到第几轮、每一轮的 q₀ 差多少，页面今天都不说。`FYL-DESIGN-16` 的 S-3 / S-4 把
「每个步界能停、状态进记录」定成了内核契约，`FYL-DESIGN-18` U-8..U-11 把「一串门调用 ·
进度数出来 · 断点即记录」定成了页面的执行形——本篇把这两条接到动理学反演上，链的每一步
就是一次门调用，回边就是一次 `--resume-from`。

★**命名**：用户描述里的阶段写作 L0..L4；本篇写作**阶段 0..4**，因为 `FYL-CONOPS-00` v1.2 的
**用户级别**已经占了 L1..L3。两者是两个轴：阶段说的是**链上的位置**，级别说的是**谁来改**。

(fylite-kinetic-flow-asis)=
# 一 · 家底 (As-Is)

〔已确立·实测 2026-09-12〕fylite 今天对这条链**有的**与**没有的**：

:::{table} 用户描述的三条 OMFIT 路径，与 fylite 今天的对应。
:name: tbl-q21-paths

| 路径（用户描述） | 收敛语义 | fylite 今天 |
| :--- | :--- | :--- |
| 手工：`OMFITprofiles` → `EFITtime`（kinetic mode），人控剖面拟合与 knot | 反演层 χ² 饱和；外环由人判 | 分析页四栏 + `fy run analysis --kinetic`：剖面拟合栏（移位勒让德基 + GCV）→ `pressure` 端口 → `code/reconstruction`（`kin` / `pointfit` / `neon` 开关）。**回边靠人**：`-12` 的「发布 / 取用」 |
| 自动：CAKE（诊断 → k-file 约束，自迭代至自洽；仅 DIII-D） | 二维验收：GS error × 磁 χ² | **无自动路径**。外环 `oracles/loop.py`（EFIT ↔ NEO 自举）在内核仓测试树，`_manifest/kinetic_reconstruction.jsonld` 标 `executable: false`；Python 侧留有它的**簿记**：`engine.versioning.Staleness`（七阶段依赖图）· `iter-NNN` 写一次快照 · `convergence_panel`（q₀ / q₉₅ / Δq₀ / converged） |
| 含输运自洽：耦合 ONETWO / TRANSP（NUBEAM）算快离子与驱动电流 | 外环 + 输运收敛 | **范围外**（`FYL-CONOPS-00` 建设原则 6：HPC 码消费其产物、不吞并本体）。fylite 收它们的**产物**作端口：快离子压强形状（`pfast` / `pfastpk`）、`code/beam` 的沉积、`code/rf_ray` 的 ECCD（部分，`FYL-REPORT-07` C-20） |
:::

(fylite-kinetic-flow-stages)=
# 二 · 五个阶段，逐段钉到今天的 code 上 (The Five Stages Against Today's Codes)

:::{table} 阶段 0..4：用户描述的每一步 · fylite 的落点 · 状态（✓ 已落地 / ◐ 部分 / ✗ 缺）。「落点」列的 `code/<x>` 是内核门认的 code（`fy list kernel`），`S.` 是 Python 装配层。
:name: tbl-q21-stages
:align: left

| 阶段 | 用户描述 | fylite 落点 | 状态 |
| :--- | :--- | :--- | :---: |
| **0 基准平衡** | 磁测量-only 反演（EFIT01/02）给初始 ψ(R,Z)，只为把剖面诊断映射到磁面 | `code/reconstruction` + 开关 `only_magnetic`（`kin=neon=probefit=pointfit=farfit=vesselfit=false`）；产 `equilibrium`（ψ 图 · 边界 · q · l_i(3)）| ✓ |
| **1.1 取数** | TS（nₑ, Tₑ）· CER（Tᵢ, n_C, v_tor）· ECE · CO₂ 干涉仪 · MSE | 测量三级解析（`-17` E-15：`--input` → 语料切片 → mdsip 取回）；`io.mds.fetch_thomson` / `fetch_diamagnetic`；`io.est2` 归约（窗口均值 · 漂移 · POINT）。★EAST 绑定表**无 Thomson**（`-17` G-8），动理学一档第 3 级取不全，只能 `--input`；**无 CER · 无 ECE · 无 MSE** | ◐ |
| **1.2 时间窗平均；H 模按 ELM 相位条件平均** | filterscope Dα 触发 | 窗口均值有（`est2`）；**ELM 同步无**——没有 Dα 触发的输入端口，也没有相位选择的 code | ✗ |
| **1.3 映射到 ψ_N / ρ，样条或 GP 拟合，出 p-file** | — | 映射：`code/ladder`（在平衡文档上描迹一次）；拟合：分析页剖面拟合栏（移位勒让德基 + GCV，`S.analysis.profit`）；内核的 `code/profile_fit` 自述「planned」。产物是 `pressure` 端口要的那份剖面文档（不是 p-file：fyo 文档进、fyo 文档出） | ◐ |
| **1.4 分离面对齐** | 双点模型给 Tₑ,sep（~60–100 eV），对 TS 施加径向位移；对台基梯度与自举电流影响最大 | 双点模型的闭式在（登记册 V-10..V-13 Lengyel）；**「按 Tₑ,sep 移 TS」这一步没有 code**。★这是用户描述里标为影响最大的一步 | ✗ |
| **1.5 Z_eff** | 由 nₑ 与 n_C 推出 | `zeff` 是**参数**（词表有），不是推导——EAST 无 CER 的 n_C | ◐ |
| **2.1 压强约束** | p = nₑTₑ + ΣnᵢTᵢ + p_fast；快离子由 NUBEAM / ONETWO 或简化慢化模型 | `pressure` 端口（`-12` P-22：**带 `derived-from-reconstruction` 出处的剖面按名拒绝**——不许拟合自己的假设）；快离子：参数化形状 `pfast` / `pfastpk`（**不是**慢化模型，是给定形状）；`tite` 给 Tᵢ/Tₑ | ◐ |
| **2.2 电流约束** | j_∥ = j_ohm（新经典电阻率）+ j_bs（Sauter / Redl）+ j_NBI + j_ECCD | `code/bootstrap`（Redl-2021，与 NEO `jpar_dke` 同归一化）· 欧姆经 `code/transport` 的电导率 · `code/beam` 沉积 · `code/rf_ray`（ECCD 部分）。★**作为反演的约束行**进入设计矩阵的今天只有自举（外环那条路），其余是产物不是行 | ◐ |
| **2.3 MSE 的 Er 修正** | 由 CER 的 v_tor · v_pol 与 ∇p 经径向力平衡给出 | **无 MSE**（`-12` G-4：几何不在装置卷宗）；**无 Er 修正**。`code/reconstruction` 的设计矩阵行族：磁类 · 压强 · 磁面平均电流 · 径向锚 · 边缘先验（`physics/03` §行族）——没有 MSE 行 | ✗ |
| **3 反演** | P′ 由阶段 2 固定，FF′ 自由（样条基）；MSE 与磁测量共同进 χ²；knot 数量与位置是调参核心 | `code/reconstruction`：压强行固定 p′（`kin`）、FF′ 用**列均衡 + 截断谱**的基（`physics/03` §约束最小二乘；`basis` / `outk` 在词表里，与「knot」的对应**未核**，见 G-4）；χ² 总量与逐道残差表（`-12` 逐道残差）。★无 MSE 行，所以「MSE 与磁测量共同进 χ²」在 fylite 里是「压强行与磁测量共同进 χ²」 | ◐ |
| **4 外环** | 新平衡 → 重新映射剖面 → 重算自举 / 快离子 → 回到阶段 3 | 簿记在：`Staleness`（`equilibrium → profiles → mapping → bootstrap → beam → wave → constraint`，`constraint → equilibrium` 成环）· `iter-NNN` 快照 · `convergence_panel`；**执行不在本分发**（`oracles/loop.py`）。实测（#137985，当年）：**2 轮收敛**；自举约束抬 q₀ ≈ +11 %、压 l_i ≈ −7 % | ◐ |
:::

〔判读〕**链的每一段在 fylite 里都有名字，链本身没有。** 五个阶段里四个有 code 或装配层的
落点，而把它们**串起来**的东西——步序 · 步间交接 · 过期传播 · 回边——今天散在三处：页面的
「发布 / 取用」（人）、Python 的 `Staleness`（簿记，无执行）、内核仓的 `oracles/loop.py`（执行，
不发行）。本篇要做的是让这条链成为**一份计划**（`fyo:ScenarioSpecification.has_step[]`），
页面画它、驱动它、从记录里读它的状态。

(fylite-kinetic-flow-criteria)=
# 三 · 四层收敛判据，各落到 fyo 的哪个类上 (The Four Convergence Criteria in fyo)

〔已确立〕用户描述的四层判据**语义互不等价**——这句话在本篇里的形是：四个判据是四个
`ConvergenceCriterion` / `AcceptanceCriterion` 实例，各挂在各自的步上，**不合成一个标量**。

:::{table} 四层判据 × fyo 类 × fylite 今天量得出什么。阈值列**只写量过的**；DIII-D 的典型量级照录为「参照」，不当本仓的阈值（偏置提示见 §八）。
:name: tbl-q21-criteria
:align: left

| 层 | 判据（用户描述） | 参照量级 | fyo 落点 | fylite 今天 |
| :--- | :--- | :--- | :--- | :--- |
| **内层 GS** | Picard 迭代中 ψ 归一化残差 < `ERROR` | 10⁻⁴（可收紧至 10⁻⁵） | `ConvergenceCriterion{metric: psi_residual, threshold}` 挂在阶段 3 的 `EquilibriumReconstruction` 上 | 内核的外层迭代（`physics/03` §外层迭代）有残差与迭代上限；词表里 `maxit` · `caltol` · `closit` / `clostol`——**含义待 code 表自报**（`FYL-REPORT-07` C-28）。★爬升段预设在随包那一炮上第 137 次外迭代法方程奇异（`-12` 分档表）：这是「不收敛按判据报出」的实例 |
| **反演层** | 总 χ² 与分诊断 χ² 饱和；磁 χ² 不再随迭代下降 | 装置依赖 | 同一步上的第二个 `ConvergenceCriterion{metric: chi2_saturation}`；分诊断 χ² 是 `ComparisonFinding` 逐行 | `chi2` 在记录里（`summary` 行 `fylite:chi2`）；逐道残差表在页面（`-12`）。★「饱和」要**两轮**才判得出——它是外环那一层才有的读数 |
| **外环** | 迭代间 p · j_∥ · q₀ · q₉₅ 相对变化 < 阈值 | 通常 2–3 轮后 < 1–2 %〔工程惯例〕 | `ScenarioLoop.converges_by → ConvergenceCriterion{metric: dq0_rel \| dq95_rel}` | `convergence_panel` 给 `q0` / `q95` / `dq0` / `converged`——**这一层的簿记已经是 fyo 形的一半**；阈值今天写在 `loop.self_consistent(max_iter=…)` 的调用里 |
| **后验物理** | GS error 低到可供 MHD 稳定性码使用 | 见下（二维） | `AcceptanceCriterion` × 2 + `ComparisonRecord`（二维验收） | GS 残差**量过**：登记册 B-10（CHEASE 固定边界，5.257e-02，带 8e-2，且「加密盒子不是收敛检验」）；V-15（g-file 往返）。★**对本仓的反演解未量**——B-06 量的是与 EFIT 的差，不是 GS 残差 |
:::

**二维验收（CAKE 的做法）。**〔已确立·用户描述〕每个时间片同时投影到 **GS error** 与
**磁 χ²** 两个轴上筛选；映射迭代产生的解对 GS error 的要求可放宽——两者构成二维判据，
不是单一标量阈值。本篇的形：一份 `fyo:ComparisonRecord`，`has_criterion` 两条
`AcceptanceCriterion`（`about_quantity: gs_residual` 与 `about_quantity: chi2_magnetic`），
`overall_verdict` 由两条 `ComparisonFinding` 合成，**合成规则写在记录的 `norm_note` 里**
（「映射轮放宽 GS」就是那一句），不写在页面里。页面画的是散点：横轴 GS 残差、纵轴磁 χ²，
每轮一个点，验收区一块——读者看得见「放宽」了哪一轴、放宽了多少。

**后验一致性检验（工程惯例，非收敛条件）。** 用户描述四条，各自在 fylite 的落点：

| 检验 | fylite 今天 | 形 |
| :--- | :--- | :--- |
| q=1 面位置 vs 锯齿反转半径 | `code/evolve` 有 `saw_r1`（q=1 半径）；反演解的 q 剖面有；**锯齿反转半径的测量**无端口 | `ComparisonFinding`，缺一侧则 `verdict: unevaluated` |
| 计算中子产额 vs 测量 | **无**（无中子产额的 code，无测量端口） | 同上，`unevaluated` |
| FF′ · j_∥ 无非物理振荡（knot 过密 / 过约束的征兆） | 剖面在记录里；**振荡判据无** | 可作 `ComparisonFinding{norm: total_variation}`〔工作假设〕 |
| β_N · l_i 与磁测量-only 的偏离可解释 | **已有先例**：B-06 报告磁轴 +5.07 / +6.54 mm · ψ rms 1.18 % · q₉₅ +5.55 % · q₀ **−58.9 %**（`-12` P-22 ③） | 阶段 0 的记录 vs 阶段 3 的记录，一份 `ComparisonRecord`——这是流程图上**天然就有**的一条边 |

(fylite-kinetic-flow-plan)=
# 四 · 场景是一份带回边的计划 (The Scenario as a Plan with a Back Edge)

〔已确立·设计〕动理学反演场景是**一份** `fyo:ScenarioSpecification`，`prescribed_task_kind:
fyo:ExperimentAnalysisTask`，`has_step[]` 五步，第五步是一个 `fyo:ScenarioLoop`（`has_occurrent_part`
指回阶段 1.3..3，`converges_by` 指外环判据）。每一步 `prescribes_code` 一个 code，端口绑定
**只绑上一步的产物或外部文档**——边由绑定推出（`FYL-REPORT-06` §8.3），计划里**不另写**边。

```{mermaid}
flowchart LR
    M[("测量文档<br/>magnetics · pf_active · tf")] --> S0
    D[("装置文档<br/>fyo:DeviceDescription")] --> S0
    S0["阶段 0 · 基准平衡<br/>code/reconstruction · only_magnetic<br/>判据：GS 残差"] --> S1
    T[("剖面诊断<br/>thomson · (cer · ece · mse)")] --> S1
    S1["阶段 1 · 剖面构造<br/>ladder → profit → pressure 文档<br/>(ELM 同步 · Te,sep 对齐：缺)"] --> S2
    S2["阶段 2 · 约束构造<br/>p = neTe + ΣniTi + pfast<br/>j∥ = bootstrap (+ beam · rf_ray)<br/>(MSE · Er：缺)"] --> S3
    S3["阶段 3 · 反演<br/>code/reconstruction · kin<br/>判据：GS 残差 · χ² 饱和"] --> S4
    S4{"阶段 4 · 外环<br/>ScenarioLoop<br/>判据：Δq₀ · Δq₉₅ < 阈值"}
    S4 -- "未收敛：新平衡 → 重映射" --> S1
    S4 -- "收敛" --> A["后验：二维验收<br/>GS 残差 × 磁 χ²<br/>+ 一致性检验"]
    S0 -. "对照：β_N · l_i · q₀ 偏离" .-> A
```

〔已确立〕**计划骨架**（键名沿 `FYL-REPORT-06` §5.4 与本仓语料的紧凑别名）：

```yaml
type: fyo:ScenarioSpecification
id: scenario/kinetic
prescribed_task_kind: fyo:ExperimentAnalysisTask
has_step:
  - id: s0  # 阶段 0
    prescribes_code: code/reconstruction
    has_parameter_setting: [{sets_parameter: "code/reconstruction#kin", literal_value: false}, …]
    has_port_binding: [{binds_port: measurements, bound_endpoint: "…"}, {binds_port: device, …}]
  - id: s1  # 阶段 1：映射 + 拟合
    prescribes_code: code/ladder            # 描迹 s0 的平衡
    has_port_binding: [{binds_port: equilibrium, bound_to: "x+run://s0/equilibrium"}]
  - id: s1b
    prescribes_code: code/profile_fit       # 今天：S.analysis.profit（内核 planned）
    has_port_binding: [{binds_port: thomson, bound_endpoint: "…"}, {binds_port: ladder, bound_to: "x+run://s1/ladder"}]
  - id: s2
    prescribes_code: code/bootstrap
    has_port_binding: [{binds_port: core_profiles, bound_to: "x+run://s1b/core_profiles"}, {binds_port: equilibrium, bound_to: "x+run://s0/equilibrium"}]
  - id: s3
    prescribes_code: code/reconstruction
    has_parameter_setting: [{sets_parameter: "code/reconstruction#kin", literal_value: true}, …]
    has_port_binding: [{binds_port: pressure, bound_to: "x+run://s1b/pressure"}, {binds_port: current, bound_to: "x+run://s2/bootstrap"}]
  - id: s4
    type: fyo:ScenarioLoop
    has_occurrent_part: [s1, s1b, s2, s3]   # 回边：s3 的 equilibrium 顶替 s0 的
    converges_by: {type: fyo:ConvergenceCriterion, metric: dq0_rel, threshold: 0.01}
    iteration_cap: 6
```

★**回边的机制不是新的**：第 k+1 轮的 `s1` 绑的是第 k 轮 `s3` 的记录（`x+run://<run>/equilibrium`），
这就是 `--resume-from` 做的那件事（`FYL-REPORT-07` §9.1：记录交出的状态摆回下一次的输入）。
外环因此**不需要**一个调度器：它是一条线性链加一次条件回跳，宿主（页面 / Python）逐步驱动，
内核每步一次门调用（`-16` S-3）。这在包络之内（`FYL-REPORT-06` §9.1：fylite 是 worker）；
要 DAG 调度、要并行多片、要把 NUBEAM 编进 s2，就是 FyTok 的活（`FYL-REPORT-07` §8）。

(fylite-kinetic-flow-page)=
# 五 · 页面：一张流程图，节点是步，状态从记录读 (The Page)

```{mermaid}
flowchart TB
    subgraph page["分析页 · 反演部件（重规划）"]
        direction LR
        G["流程图 flow.js<br/>节点 = has_step · 边 = 端口绑定"]
        N["节点卡<br/>状态 · 判据读数 · 出处<br/>L2：模型档位面板"]
        C["控制条<br/>运行到此 · 单步 · 从此重跑 · 断点 · 取消"]
        L["外环面板<br/>轮次 · q₀/q₉₅ 逐轮 · 二维验收散点"]
    end
    P[("计划<br/>fyo:ScenarioSpecification")] -- 投影 --> G
    R[("记录 ×N<br/>spo:ComputationRecord + fylite:state")] -- 投影 --> N
    R -- 投影 --> L
    C -- "一串门调用（U-8）" --> K["内核 wasm / 本机<br/>每步一次"]
    K -- "记录 k" --> R
    G -- "点节点" --> N
    N -- "改档位 = 改计划（H-1）" --> P
```

**Q-1 页面是计划的投影：节点 = `has_step[]`，边 = 端口绑定推出，页面不持第二份图。** 流程图
从计划文档生成；节点的名字、code、参数来自那一步的声明，边来自 `bound_to: x+run://…`。
页面 HTML 里**禁止 (MUST NOT)** 手写节点或边——这是 `-18` U-1 对图的推论：手写的图是第二份
真源，与计划的漂移无人察觉。〔已确立〕。

**Q-2 节点状态从记录读，不从页面变量读。** 每个节点的状态 = 它那一步最近一份记录的
`run_state`（七值：`submitted · validating · running · succeeded · failed · rejected · cancelled`，
`FYL-REPORT-07` R-3）叠加步带四态（`-18` U-8：未算 · 当前 · 已算 · 断点）；**过期**是第八种
显示（不是第八个 `run_state`）：上游某步重跑之后、本步的记录仍在但已不对应，节点画成
「已算 · 过期」（`Staleness.downstream` 的图形）。状态的每一次变化都对应一份记录落盘；
页面重开，图从记录集重建，与关掉之前一样。〔已确立〕。

**Q-3 每个节点带它那一层的判据读数；页面只画不判。** 阶段 0 / 3 的节点显示 GS 残差与 χ²，
阶段 4 显示 Δq₀ / Δq₉₅ 与轮次，后验节点显示二维验收的位置。读数来自记录的
`ComparisonFinding` / `ConvergenceCriterion`（§三），判定（`verdict`）也来自记录；页面
**禁止 (MUST NOT)** 自己算一个阈值比较——`-12` P-22 ③「q₀ 的误差不能只由磁残差判」在
图上的形就是：两个判据两个读数，各在各的节点上，不合成一个绿灯。〔已确立〕。

**Q-4 五个控制动作，没有「跳过」。** 运行到此（从第一个未算 / 过期的节点算到点中的节点）·
单步（只算下一个）· 从此重跑（把本步及下游标过期，`Staleness.invalidate` 的图形，然后从本步起）·
断点（把当前节点的记录存进断点仓，`-18` U-10）· 取消（切预算，`-18` U-9；当前步的记录完整
可用）。**没有「跳过某步」**：可选的步（ELM 同步 · Tₑ,sep 对齐 · Er 修正）的开关是**计划里的**
`fylite:switches`，关掉 = 那个节点不在图上（或画成关着的节点，Q-7），不是运行时绕过去。
一个被绕过去的步在记录里没有痕迹，而「这一轮到底做了什么」正是记录要答的。〔已确立〕。

**Q-5 外环是图上的一条回边，每轮一份记录，断点在轮边界。** 阶段 4 节点带轮次计数与
`iteration_cap`；每一轮跑完 s1..s3 写一份轮记录（含 `fylite:state`），回边把它绑到下一轮的
s1 上——与 `--resume-from` 同一机制。外环面板画 q₀ / q₉₅ 逐轮与二维验收散点；收敛由
`converges_by` 判，读数在轮记录里。取消发生在**轮边界**（S-3：每个步界能停）。〔已确立〕。

**Q-6 三级用户在图上各有一层。** L1（初级）：选装置 · 炮号 · 时刻，或一条预设，按「运行」——
图由预设填好，用户不碰节点；L2（中级）：点开节点，改**模型档位**——快离子压强形状 · 自举
公式 · FF′ 基的阶数 / 截断 · Tₑ,sep · 权重（`-12` U-23 的通道权重）；图的形不变。L3（高级）：
**换节点**——把 s2 的 `code/bootstrap` 换成一份外部产物（NEO 的 `jpar_dke`、NUBEAM 的快离子
压强）绑到同一端口，或导出计划到 FyTok 里跑。★fylite 页面里 L3 能做的是「绑外部**产物**」，
不是「调外部**程序**」（`FYL-REPORT-07` §8.4 负面清单）。〔已确立·`FYL-CONOPS-00` §用户级别〕。

**Q-7 缺失的诊断是一个可见的关着的节点，不是消失的节点。** MSE · CER · ECE 在装置卷宗里
没有几何时，图上仍有它们的输入节点，画成关着的，旁注「缺装置数据」或「缺接线」
（`-12` P-22 ①：读者必须一眼看到拟合里到底有什么）。**数据约束与模型约束用两种边线**：
从测量文档来的边实线，从模型（`code/bootstrap` 的 Redl 公式、参数化的 `pfast`）来的边虚线
——这是 §八 偏置提示的图形化：EAST 上阶段 2 的电流约束是虚线边，读者不会把它读成数据。
〔已确立〕。

**Q-8 失效模式是节点上的告警，来自记录，不来自页面。** 超定（约束行数 vs 基函数自由度）·
Tₑ,sep 位移敏感度 · 快离子模型差异 · 强旋转下 Er 修正的不确定度——内核或装配层把它们写进
记录的 `comment[]` / `caveat[]`（`code/reconstruction` 今天已把「爬升段第 137 次外迭代奇异」
一类的话写进 `notes`），节点读出来画成告警。页面**禁止 (MUST NOT)** 自己判「knot 太密」。
〔已确立〕。

**Q-9 执行是一串门调用；fylite 是 worker，图的驱动在宿主。** 页面（或 Python）按拓扑序逐节点
调门，每步一份记录，步间以 `x+run://` 绑定交接；`run.js` 的预算分片与取消原样适用于
多步 code 的节点。**不引入**调度器、队列或服务端组件（`NR-ENV-001`）；三节点以上的并行
（多时片批处理）仍是逐片串行（`-12` 分档表第四行），进度数出来。〔已确立〕。

(fylite-kinetic-flow-levels)=
# 六 · 三级用户 × 五个阶段 (Levels × Stages)

:::{table} 每个阶段上三级用户各改什么。空格 = 这一级不碰这一阶段。
:name: tbl-q21-levels
:align: left

| 阶段 | L1 初级 | L2 中级 | L3 高级 |
| :--- | :--- | :--- | :--- |
| 0 基准平衡 | 炮号 · 时刻 · 装置 | 基函数阶数 · 涡流拟合开关（`vesselfit`）· 通道权重 | 换测量文档（自己取的一片） |
| 1 剖面构造 | — | 拟合阶数 / GCV · 时间窗 · Tₑ,sep（落地后） | 绑自己的剖面文档；换拟合器（外部 GP 的产物） |
| 2 约束构造 | — | 快离子压强形状（`pfast` / `pfastpk`）· Tᵢ/Tₑ（`tite`）· Z_eff · 自举公式 | 绑 NUBEAM / NEO 的产物到 `pressure` / `current` 端口 |
| 3 反演 | — | `kin` / `pointfit` / `neon` 三开关 · 噪声与权重 · 迭代上限 | 换 code（另一个内核后端，`FR-KERNEL-003`） |
| 4 外环 | 预设给的轮数上限 | 收敛阈值 · 轮数上限 | 改回边（哪几步进环）· 导出整份计划 |
| 后验 | 看验收 | 看逐项检验 | 加检验（一份新的 `ComparisonRecord`） |
:::

(fylite-kinetic-flow-stages-gates)=
# 七 · 分期与门禁 (Stages and Gates)

:::{table} 三期。先做**只读的图**，因为它删的手写最多、动的内核最少。
:name: tbl-q21-phases
:align: left

| 期 | 前置 | 做什么 | 判据 |
| :--- | :--- | :--- | :--- |
| **Q0 只读的图** | 无 | 把今天四栏的调用关系写成一份 `scenario/kinetic.jsonld`（五步，s4 先不成环）；`flow.js` 从它画图；节点状态从四栏已有的记录读；判据读数从 `summary` 行读。四栏**照旧可用**，图是它们的另一种看法 | 流程闸：图上的节点集合 = 计划的 `has_step` 集合，**双向**（`-10` G-14 的教训）；状态闸：每个节点的状态字符串 = 对应记录的 `run_state`，页面无私有状态变量 |
| **Q1 控制** | Q0 · `-18` U0 的 `run.js` 接线 | 五个动作（Q-4）；过期传播；断点进断点仓；节点卡改档位 = 改计划（H-1） | 控制闸：「运行到此」的结果 = 逐步手按的结果，逐记录相同；「从此重跑」后下游节点全部标过期 |
| **Q2 外环** | Q1 · 外环从内核仓测试树发行到本分发（G-7） | s4 成环；轮记录；二维验收散点；`converges_by` 判 | 外环闸：N 轮一次跑完 ≡ k 轮 + 从轮记录续 (N−k) 轮，逐记录相同（`FYL-DESIGN-18` §十三 断点闸的外环版；实测先例 `FYL-REPORT-07` §9.1 ①） |
:::

(fylite-kinetic-flow-bias)=
# 八 · 偏置提示，与它在本篇里的落点 (The Bias Note, Landed)

〔已确立·用户描述〕以上流程与阈值来自 **DIII-D 生态**（诊断覆盖密度高、MSE 可用）。移植到
MSE 缺失或 CER 稀疏的装置时，阶段 2 的电流约束退化为由新经典公式主导的**模型驱动**结果，
其「自洽性」的认识论地位从「数据约束」降为「模型约束」，**收敛不蕴含正确**。

〔判读〕fylite 的随包装置正是这种情形（EAST：无 MSE、无 CER 绑定、Thomson 要 `--input`）。
本篇因此把这句话做成三件可见的东西，而不是一段注记：Q-7 的**两种边线**（数据实线 · 模型
虚线）；§三判据表**不抄 DIII-D 的阈值**（参照量级单列，本仓阈值只写量过的）；§三后验表的
`unevaluated`（缺一侧就说缺，不给绿灯）。★另一处要说准的偏置：`-12` P-22 ③ 的 q₀ −58.9 %
是本仓反演解与 EFIT 之差，**不是**与真值之差——B-06 报告自陈那一炮无 ASIPP 动理学 oracle。

(fylite-kinetic-flow-gaps)=
# 九 · 缺口 (Gaps)

| | 缺口 | 证据 | P |
| :--- | :--- | :--- | :--- |
| **G-1** | **多步计划今天不执行**：`fy run` 一份计划一个 code（`--code` 选一个），`has_step[]` 无消费者；Q0 的图能画，Q1 的「运行到此」要宿主逐步驱动 | `-17` as-built；`FYL-REPORT-06` B-1 | P0 |
| **G-2** | **三步无 code**：ELM 相位条件平均（1.2）· Tₑ,sep 分离面对齐（1.4，用户标为影响最大）· MSE 的 Er 修正（2.3） | {numref}`tbl-q21-stages` | P1 |
| **G-3** | **MSE / CER / ECE 不在装置卷宗**，也无绑定表；阶段 2 的电流约束在随包装置上只能是模型边 | `-12` G-4；`-17` G-8 | P1（数据缺口，归 fydata / fydoc） |
| **G-4** | **「knot」与本仓基函数的对应未核**：用户描述的调参核心是 knot 数与位置，本仓用列均衡 + 截断谱；词表里 `basis` / `outk` / `kpts` 的含义待 code 表自报 | `FYL-REPORT-07` C-28 | P0（随 `-16` K-2） |
| **G-5** | **两条后验检验无判据**：中子产额无 code 无端口；FF′ / j_∥ 振荡无判据 | §三后验表 | P2 |
| **G-6** | **本仓反演解的 GS 残差未量**——B-10 量的是 CHEASE 固定边界，B-06 量的是与 EFIT 的差 | 登记册 | P1 |
| **G-7** | **外环不在本分发**：`oracles/loop.py` 在内核仓测试树，`kinetic_reconstruction.jsonld` 标 `executable: false`；本分发里签名已不合（`guide/reconstruction.md` 警告） | `test_call_sites_match.py` | P1 |
| **G-8** | **二维验收的阈值装置依赖**，DIII-D 的数值不可搬；本仓要先有 G-6 的量才谈阈值 | §三 | P2 |

(fylite-kinetic-flow-proposals)=
# 十 · 提案 (Proposals into SRS / SDD)

〔信息性〕编号在 `FYL-SRS-01` 附录〈提案登记〉登记；`-12` 用到 FR-ANALYSIS-008，本篇从 009 起。

| 提案 ID | 大意 | 本篇裁定 |
| :--- | :--- | :--- |
| FR-ANALYSIS-009 | 动理学反演是一份多步计划（`has_step[]` + `ScenarioLoop`），步间以记录交接；每步一次门调用 | §四 · Q-9 |
| FR-ANALYSIS-010 | 四层收敛判据各为一个 fyo 判据实例，挂各自的步；二维验收为一份 `ComparisonRecord`；不合成单一标量 | §三 · Q-3 |
| FR-ANALYSIS-011 | 反演页以流程图呈现：节点 = 步、边 = 绑定、状态 = 记录；五个控制动作；缺失诊断为可见的关着的节点；数据边与模型边可辨 | Q-1 · Q-2 · Q-4 · Q-7 |
| DE-LOG-16 | 流程图投影（`flow.js`：计划 → 图；记录 → 状态与读数；控制 → 门调用） | Q-1..Q-9 |

(fylite-kinetic-flow-trace)=
# 十一 · 追溯 (Traceability)

| 本篇 | 上游 | 下游 |
| :--- | :--- | :--- |
| §二 · §三 | 用户描述 2026-09-12（阶段 0..4 · 四层判据 · 失效模式）· `physics/03` · 登记册 B-06 / B-10 / V-10..V-15 | `guide/reconstruction.md` 〈反演是怎么分层的〉 |
| §四 · Q-9 | `FYL-REPORT-06` §5.4 / §8.3 / §9；`-16` S-3 / S-4；`FYL-REPORT-07` §9.1（`--resume-from`） | `scenario/kinetic.jsonld`（Q0） |
| Q-1..Q-5 | `-18` U-1 · U-8..U-11；`-12` P-22 · P-23 | `flow.js`；流程闸 · 状态闸 · 控制闸 · 外环闸 |
| Q-6 | `FYL-CONOPS-00` v1.2 §用户级别；`-17` E-25；`-18` U-26 | 节点卡的按级折叠 |
| Q-7 · §八 | 用户描述〈偏置提示〉；`-12` P-22 ① | 边线的两种样式；判据表不抄阈值 |
| Q-3 · Q-8 | fyo `assessment.linkml`（`ComparisonRecord` / `AcceptanceCriterion` / `ComparisonFinding`）；`-12` P-9 / P-29 | 记录的 `comment` / `caveat` → 节点告警 |
