---
title: 平衡反演 (Equilibrium Reconstruction)
---

# 平衡反演

fylite 的看家能力：给定磁测量求解 Grad–Shafranov 反演，按
[约束阶梯](constraints.md)逐级加入动理学信息。

## 基本调用

```python
from fylite import fyo
from fylite import scenario as S

meas = fyo.as_measurements("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld", 4.0)
r = S.analysis.reconstruction(meas, pressure=fit)      # fit 见下一节
```

返回一层平表：`psi`（全磁通 [Wb]，表网格上）、`q0` / `q95` / `ip` / `chisq`，以及与
Fortran 路同名的那批标量，故两者可直接对照。

:::{important}
**入口变过，旧写法调不通。** 它曾是 `fylite.run(137985, 4.0, point=True, …)`——一个按输入
模式分派、组装 k-file 再调 `libefit.so` 的单一入口。`fylite.run` 今天是**模块**不是函数，
那个库也不在本分发里；重构行归 `fylite.scenario.analysis`，动理学信息按
[约束阶梯](constraints.md)从参数进来（`pressure=`），不再经 namelist。
:::

:::{note}
**线圈份额是现算的，不再查表。** 磁通环读数里线圈那一份（EFIT 的 `rsilfc`）曾经必须从
`rfcoil.ddd` 读，而本仓不带这份表——于是**整条 Python 反演路**在第一次内核调用之前就抛
`MachineDataMissing`（令 `brsp=0` 也绕不开：数学归零不等于代码跳过）。现在它由装置文档的
导体几何在门里现算（`code/reconstruction` · `code/coilshare`；旧 `recon_rs.coil_loop_rows` 自 2026-09-06 归内核仓测试树），与浏览器
反演页、与本函数探针那一半走的是同一条路：**装置信息只有一个出处，即
`$FYLITE_DEVICE_DIR` 指向的那份装置文档**。

★对表实测（#137985 wpf2018 那套 `rfcoil.ddd`）：`nu=nv=8` 下逐元相对差 7.7e-5，随求积阶
单调收敛（4.9e-4 → 7.7e-5），逐通道 7.0e-6…7.7e-5 均匀——丝化/求积之差，非结构之差。
端到端换表实测（同一炮、其余不变、收敛的动理学组态）：I_p 差 1e-6 A、磁轴 R 0.14 mm、
Z 0.05 mm、q95 0.05 %。（这批数字是当年在两张表都在场时实测的；`rfcoil.ddd` 不在本分发里，
所以是判据不是可复算的步骤。）
:::

## 压强约束从哪来

```python
f = S.analysis.profit(x, y, sigma_frac=0.05)   # 移位 Legendre + GCV 定阶
```

★**重构自己产出的剖面会被拒收**：`profit` 的结果带 `provenance`，凡标记为
`derived-from-reconstruction` 的压强再喂回 `reconstruction` 直接抛错——那是唯一一种会让
拟合变成"自我确认"的输入，事前拒绝比事后解释 χ² 为什么变好便宜。

## 不确定度量化

σ 取**实测**逐点误差传播（Thomson 的 `\TE_CORETSERR`/`\NE_CORETSERR`），不是平摊比例。
这是诚实的 σ，代价是它会把真实的压强张力暴露出来（`chi_pressure` ≈ 1228）——平摊 20%
只是**掩盖**了它。

★**逐标量 1σ + 分位、剖面误差带与逐诊断的实测-vs-前向**（`errorbars` / `profiles` /
`diagnostics`）当年由 EFIT 驱动的入口按中心差分扫描给出；今天仍命名它的只有
`loop.self_consistent(..., final_uncertainty=N)`，而那条外环在本分发里跑不起来（见下节），并自
T-4 第十五刀（2026-09-06）起整体迁到内核仓的神谕树 `tests/oracles/loop.py`。
`S.analysis.reconstruction` 自己不产生这三项。

## 自洽外环 EFIT↔NEO

★自 T-4 第十五刀（2026-09-06）起这条外环连同闭合、装配、映射与 Redl 自举剖面**不在本包里**：
它只被测试调用，经扁平入口够内核，已整体迁到内核仓 `tests/oracles/loop.py`；`_manifest/kinetic_reconstruction.jsonld`
仍登记这个工作流模板，但标 `fylite:executable: false`。下面的调用式在内核仓的测试树里才成立（`from oracles import loop`）。

```python
from oracles import loop   # 内核仓 tests/oracles/loop.py
lr = loop.self_consistent(
        137985, 4.0, point=True, pressure=True, thomson_ne=True,
        neo_resolution="fast",
        n_surfaces=16, max_iter=6, final_uncertainty=16)
```

:::{warning}
**这条外环在本分发里跑不起来。** 它的第一句就是驱动一次 east 重构，而那个入口按
`(shot, time_s, kind="east", server=…)` 调用——今天的 `recon_rs.reconstruct` 收的是
**测量字典**，签名不合，接触即 `TypeError`（对得上的是同模块的 `reconstruct_shot`）。
三个测试模块都把这道缝 monkeypatch 掉了，所以套件长期看不见它；现在由
`python/tests/test_call_sites_match.py` 盯着这类缝。下面的数字是当年实测，留作判据。
:::

★路径变过：它曾是顶层的 `fylite.loop`，现在归 `fylite.scenario.analysis`——
四条场景线各收自己的模块，`loop` / `recon_rs` / `selfcal` / `tomography` / `moments`
都在 `analysis` 下（同批搬走的还有 `control` / `stability` / `evolution` →
`scenario.control`，`pulse` / `shape` → `scenario.design`，
`assembly` / `closure` / `nbi` / `lh` / `sources` → `scenario.model`）。

外环把 NEO 的漂移动理学自举电流喂回反演直至自洽。#137985 上 **2 轮收敛**；
后验（n=16）：q0 0.783±0.0089、q95 3.08±0.011、$I_p$ 393±1.4 kA、
li 1.95±0.057、βp 0.302±0.015、$W_{mhd}$ 37.0±1.8 kJ、χ² 11.8±0.43。

与单次动理学拟合相比，自举约束**抬高 q0 约 11%、压低 li 约 7%**——
正是在原本无自举电流处强加离轴自举电流所应有的方向。

:::{note}
外环的校核基线取 NEO **自身**导出的 Redl-2021 系数（`jpar_sauter_2021`），
与 `jpar_dke` **同归一化因而可直接比幅值**；Python 转录档只能比形状。
:::

## 反演是怎么分层的

动理学反演不是一次调用，是一条**有回边的链**：五个阶段各有自己的输入、产物与收敛判据，
判据的语义互不等价。设计正本是 `FYL-DESIGN-21`（阶段逐段钉到 code 与端口，四层判据落到
fyo 类，分析页反演部件重规划为一张流程图）；本节只把链的形状与它在本分发里的现状说清楚。
下文的「阶段 0..4」是链上的位置，与〈用户级别〉的 L1..L3 是两个轴。

**五个阶段。** 阶段 0 是**基准平衡**：只用磁测量反演一次（`only_magnetic`，即 `kin` ·
`neon` · `probefit` · `pointfit` · `farfit` · `vesselfit` 全关），目的不是给出结论，而是给一张
足以把剖面诊断映射到磁面的 ψ(R,Z)。阶段 1 是**剖面构造**：取诊断（Thomson 的 nₑ / Tₑ；
CER 的 Tᵢ / n_C / v_tor；ECE；干涉仪；MSE），取时间窗平均（H 模按 ELM 相位做条件平均），
在阶段 0 的磁面上映射到 ψ_N 或 ρ，拟合成剖面；随后按双点模型给出的 Tₑ,sep（量级
60–100 eV）对 Thomson 施加径向位移，把分离面对齐——这一步对台基梯度与自举电流的影响最大；
最后由 nₑ 与 n_C 推 Z_eff。阶段 2 是**约束构造**：压强 p = nₑTₑ + Σnᵢ Tᵢ + p_fast，平行电流
j_∥ = j_ohm + j_bs + j_NBI + j_ECCD，MSE 的俯仰角按径向力平衡做 Er 修正。阶段 3 是**反演**：
P′ 由阶段 2 固定，FF′ 留作自由基（样条或谱基），与磁测量一起进 χ²；基的自由度（knot 的数量
与位置）是调参的核心。阶段 4 是**外环**：新平衡回到阶段 1 重新映射、重算自举与快离子，再回
阶段 3，直到迭代间的变化落到阈值之下。

**在本分发里，链的每一段都有名字，链本身没有。** 阶段 0 与阶段 3 都是 `code/reconstruction`，
差别只在开关；映射是 `code/ladder`，拟合是上文的 `profit`，自举是 `code/bootstrap`（Redl-2021，
与 NEO 的 `jpar_dke` 同归一化）；快离子压强是给定形状（`pfast` / `pfastpk`），不是慢化模型。
三步**没有 code**：ELM 相位条件平均、按 Tₑ,sep 移 Thomson、MSE 的 Er 修正。随包装置 EAST 的
绑定表没有 Thomson（只能 `--input`），没有 CER、ECE、MSE。外环的执行在内核仓的测试树里
（上一节），本包留有它的簿记——七阶段依赖图与逐轮的 q₀ / q₉₅ 面板。把这些段串成一份
`fyo:ScenarioSpecification`（五步加一个 `ScenarioLoop`），由页面或 Python 逐步驱动、每步一次
门调用、回边即 `--resume-from`，是 `FYL-DESIGN-21` 的提案，今天未落地。

**四层收敛判据，各说各的。** 内层是 Grad–Shafranov 的 Picard 迭代：ψ 的归一化残差小于
阈值（参照量级 10⁻⁴，可收紧到 10⁻⁵）。反演层是总 χ² 与分诊断 χ² **饱和**：磁 χ² 不再随
迭代下降。外环层是迭代间 p · j_∥ · q₀ · q₉₅ 的相对变化小于阈值（工程惯例：2–3 轮后小于
1–2 %）。后验层是 GS 残差低到足以喂给 MHD 稳定性码。四层不合成一个标量：内层收敛不蕴含
χ² 饱和，χ² 饱和不蕴含外环收敛，外环收敛不蕴含解在物理上可用。fylite 今天量得出的是：
`chi2` 在记录的 `summary` 行里；内核外层迭代有残差与迭代上限（词表 `maxit` · `caltol` ·
`closit` / `clostol`，含义尚待 code 表自报）；外环面板给 q₀ / q₉₅ / Δq₀ / converged。**本仓
反演解自己的 GS 残差未量**——校验册 B-10 量的是 CHEASE 固定边界，B-06 量的是与 EFIT 的差。
上面的参照量级来自 DIII-D 生态，不是本仓的阈值。

**二维验收。** 自动路径（CAKE）对每个时间片同时看 GS 残差与磁 χ² 两个轴，映射轮产生的解
对 GS 残差的要求可以放宽——验收区是平面上的一块，不是一条线。fylite 的形是一份
`fyo:ComparisonRecord` 带两条 `AcceptanceCriterion`，放宽的规则写在记录里。**后验一致性
检验**是工程惯例，不是收敛条件：q=1 面位置对锯齿反转半径；计算中子产额对测量；FF′ 与 j_∥
无非物理振荡（knot 过密或过约束的征兆）；β_N 与 l_i 相对磁测量-only 解的偏离可解释。前两
条在本分发里缺一侧（无锯齿半径端口，无中子产额 code），判定只能是「未评估」；最后一条已有
先例——B-06 报告动理学解相对 EFIT 的 q₀ 偏离 −58.9 %，且该报告自陈那一炮无 ASIPP 动理学
oracle，所以这是与 EFIT 之差，不是与真值之差。

**失效模式。** 超定（约束行数超过基函数自由度，χ² 无法饱和，FF′ 振荡）；Thomson 径向位移
的敏感度（台基处几毫米改变自举电流的峰值）；ELM 窗口选择（条件平均的相位窗改变台基剖面）；
快离子模型的差异（简化慢化模型与 NUBEAM 给出不同的 p_fast）；强旋转下 Er 修正的不确定度。
按 `FYL-DESIGN-21` 的裁定，这些是**记录里的告警**（内核或装配层写进 `notes` / `caveat`），
页面读出来画在对应节点上，页面自己不判。

**三级用户怎么用这条链。** 初级选装置、炮号、时刻或一条预设，按「运行」，图由预设填好。
中级点开节点改模型档位：快离子压强形状、Tᵢ/Tₑ、Z_eff、自举公式、FF′ 基的阶数与截断、
Tₑ,sep（落地后）、通道权重、`kin` / `pointfit` / `neon` 三开关、收敛阈值与轮数上限；图的形
不变。高级换节点：把 NEO 的 `jpar_dke` 或 NUBEAM 的快离子压强作为**产物**绑到 `current` /
`pressure` 端口，改回边（哪几步进环），或把整份计划导出到 FyTok 里跑；fylite 页面里能做的
是绑外部产物，不是调外部程序。

**偏置提示。** 以上流程与阈值来自 DIII-D 生态：诊断覆盖密、MSE 可用。移植到 MSE 缺失或 CER
稀疏的装置时，阶段 2 的电流约束退化为由新经典公式主导的模型驱动结果，其「自洽」的认识论
地位从数据约束降为模型约束，**收敛不蕴含正确**。随包装置正是这种情形；`FYL-DESIGN-21`
把这句话做成流程图上的两种边线（数据实线、模型虚线）与判据表里不抄阈值的规矩。

## 诚实边界

- 该炮**没有 ASIPP 的动理学 EFIT oracle**：数字是自洽的，不是外部验证过的；
- 离子压强用了声明过的 Ti 形状 / $n_i=n_e$ / 无快离子假定；
- POINT 的 $n_e$ 线积分仍有已知的实测-前向偏移；
- 内部剖面**不可定量使用**——见[保真度边界](../reference/fidelity.md)。

★走查用的 notebook 已不在本仓，仓根 `examples/` 也已删除——今天的可跑示例是算例语料（`cases/`，见[算例语料](../examples/index.md)与[诊断分析：平衡反演](../examples/reconstruction/reconstruction.md)）。本节用到的 EAST 测量文档、交付平衡与离线参考随 `machine_desc/` 一并退役，只在**内核仓的历史**里（`b4dce77^`）；取法见[安装与环境](install.md)——本节用到的是那份
装置目录里的 `case_east137985_4000ms.fyo.jsonld`。★**实验数据不入本仓**，这条由
`python/tests/test_examples_are_fyo.py` 机检。
