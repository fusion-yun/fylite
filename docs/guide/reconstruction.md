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

meas = fyo.as_measurements("machine_desc/east/case_east137985_4000ms.fyo.jsonld", 4.0)
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
导体几何按 `device.channel_response(...)/2π` 现算（`recon_rs.coil_loop_rows`），与浏览器
反演页、与本函数探针那一半走的是同一条路：**装置信息只有一个出处，`machine_desc/` 下的
装置文档**。

★对表实测（#137985 wpf2018 那套 `rfcoil.ddd`）：`nu=nv=8` 下逐元相对差 7.7e-5，随求积阶
单调收敛（4.9e-4 → 7.7e-5），逐通道 7.0e-6…7.7e-5 均匀——丝化/求积之差，非结构之差。
端到端换表实测（同一炮、其余不变、收敛的动理学组态）：I_p 差 1e-6 A、磁轴 R 0.14 mm、
Z 0.05 mm、q95 0.05 %。闸子见 `tests/test_reconstruction.py`。
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
`loop.self_consistent(..., final_uncertainty=N)`，而那条外环在本分发里跑不起来（见下节）。
`S.analysis.reconstruction` 自己不产生这三项。

## 自洽外环 EFIT↔NEO

```python
from fylite.scenario.analysis import loop
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

## 诚实边界

- 该炮**没有 ASIPP 的动理学 EFIT oracle**：数字是自洽的，不是外部验证过的；
- 离子压强用了声明过的 Ti 形状 / $n_i=n_e$ / 无快离子假定；
- POINT 的 $n_e$ 线积分仍有已知的实测-前向偏移；
- 内部剖面**不可定量使用**——见[保真度边界](../reference/fidelity.md)。

★走查用的 notebook 已不在本仓（`examples/notebooks/` 不存在）。`examples/east137985-recon-figure/`
只发布这一例的**规格**（`case.fyo.jsonld` + README）；交付的重构与测量已转为 fyo 文档、
移到装置目录一侧——`machine_desc/east/` 下的 `equilibrium_east137985_4000ms.fyo.jsonld`、
`case_east137985_4000ms.fyo.jsonld` 与 `fylite_magnetics_east.json`。实验数据不入库这条
由 `python/tests/test_examples_are_fyo.py` 机检。
