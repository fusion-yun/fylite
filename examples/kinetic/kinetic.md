---
title: 典型算例 · KEFIT 动理学反演 (Worked Example · Kinetic Equilibrium Reconstruction)
---

# KEFIT 动理学反演

**问的是**：磁测量之外再给一组**剖面诊断**（Thomson 的 nₑ·Tₑ、CER 的 Tᵢ……），平衡是什么，
而且这个平衡与它自己映射出来的剖面**自洽**。**不问**纯磁测量能给什么——那是上一章
[平衡反演](../reconstruction/reconstruction.md)的事；本章从那一章〈三 · 加动理学约束〉
那一行代码往下展开。

这一章分三半：**要什么**（动理学反演这件事的需求，逐条写成读者读得懂的话）、**有什么**
（fylite 与它的内核今天把链的每一段落在哪里）、**跑一遍**（EAST #137985 的孪生上，整条链
逐段跑出来的数）。第三半的每个数都出自同目录的脚本，可以原样重跑。

:::{important}
**真炮上的动理学反演今天跑不全**，缺的是**数据**不是算法：EAST 的绑定表里没有 Thomson
（剖面只能自己取来喂进去）、没有 CER、没有 MSE。所以本章能「逐段报一个相对真值的数」
的那一条路是**孪生**——真值平衡是 fylite 自己的前向解，它自带压强剖面，于是「测点该落在哪个
ψ_N」「q₀ 该是多少」都是算得出来的。代价是：孪生证明的是**反演与前向互为逆**，不是**重构准**。
:::

## 一 · 需求：动理学反演要什么

### 一句话

**磁测量单独约束不住内部剖面。** 很不一样的 p′、FF′ 能给出几乎一样好的磁拟合；把解定下来的
是动理学约束。而动理学数据测在**位置**上（一道 Thomson 弦、一个 CER 体积元），把位置变成 ψ_N
要一个平衡——**平衡正是待解的东西**。所以动理学反演不是一个按钮，是一条**有回边的链**：

```{mermaid}
flowchart LR
    M[("磁测量<br/>环 · 探针 · 线圈")] --> S0
    S0["阶段 0 · 基准平衡<br/>纯磁反演"] --> S1
    T[("剖面诊断<br/>Thomson · CER · ECE · MSE")] --> S1
    S1["阶段 1 · 剖面构造<br/>映射到 ψ_N · 拟合 · 分离面对齐"] --> S2
    S2["阶段 2 · 约束构造<br/>p = nₑTₑ + ΣnᵢTᵢ + p_fast<br/>j∥ = j_bs + j_ohm + j_NBI + j_ECCD"] --> S3
    S3["阶段 3 · 动理学反演<br/>压强行 + 磁测量共进 χ²"] --> S4
    S4{"阶段 4 · 外环<br/>映射还在动？"}
    S4 -- "是：新平衡 → 重映射" --> S1
    S4 -- "否" --> A["后验<br/>二维验收 · 一致性检验"]
    S0 -. "对照：q₀ · l_i · β_N 偏离" .-> A
```

### 逐段的需求

| 阶段 | 做什么 | 收敛 / 验收判据 |
| :--- | :--- | :--- |
| **0 基准平衡** | 纯磁反演，只为把剖面诊断映射到磁面 | 内层：GS 残差 |
| **1 剖面构造** | 取数 · 时间窗平均（H 模按 ELM 相位条件平均）· 映射到 ψ_N · 带正则与自动光滑度选择的拟合 · 按 Tₑ,sep 对齐分离面 · Z_eff | — |
| **2 约束构造** | 压强 p = nₑTₑ + ΣnᵢTᵢ + p_fast（快离子**扣除**，σ 不动）；电流 j∥ = 新经典欧姆 + 自举 + 束 + ECCD；MSE 的 E_r 修正 | — |
| **3 反演** | p′ 由阶段 2 固定、FF′ 自由；动理学行与磁测量共进 χ²；约束权重取**逐点实测不确定度**，不取全局常数 | 内层 GS 残差 · 反演层 χ² 饱和 |
| **4 外环** | 新平衡 → 重映射剖面 → 重算自举 / 快离子 → 回阶段 3 | 迭代间 q₀ · q₉₅ 相对变化 < 阈值 |
| **后验** | 二维验收（GS 残差 × 磁 χ²，**不合成一个标量**）；q=1 面 vs 锯齿反转半径、计算中子产额 vs 测量、FF′ 无非物理振荡、β_N · l_i 与纯磁解的偏离可解释 | 各自一条，缺一侧就报「未评」 |

### 条文

下表把散在几份规格里的条文收成一张（原文不对读者公开，所以这里**写的是它说了什么**，
编号只作追溯用）。「力」是 RFC 2119 的关键字；「提案」是已提出、未落正式文本的条款。

| 编号 | 力 | 说的是 |
| :--- | :--- | :--- |
| `FR-ANALYSIS-001` | MUST | 提供基于磁测量的平衡重构 |
| `FR-ANALYSIS-002` | MUST | 重构可纳入动理约束，**权重取自逐点实测不确定度**而非全局常数 |
| `FR-ANALYSIS-003` | MUST | 带正则化与自动光滑度选择的剖面拟合 |
| `FR-ANALYSIS-007` | 提案 | 约束来源逐类可见并标明缺失原因（缺数据 / 缺接线）；纯磁配置须自报其为纯磁 |
| `FR-ANALYSIS-009` | 提案 | 动理学反演是**一份多步计划**，步间以记录交接，每步一次内核调用 |
| `FR-ANALYSIS-010` | 提案 | 四层收敛判据各为一个判据实例、挂各自的步；二维验收为一份比较记录；不合成单一标量 |
| `FR-ANALYSIS-011` | 提案 | 反演页以流程图呈现：节点 = 步、边 = 绑定、状态 = 记录；缺失诊断是**可见的关着的节点** |
| `FR-EQ-006` | MUST | 约束阶梯（纯磁 / 加 MSE / 加动理学）三级全通 |
| `FR-EQ-007` | SHOULD | MSE 全形响应行（A₁..A₄ 全形 / 简化 pitch），E_r 门无输入即显式置零并告警 |
| `FR-EQ-008` | MUST | 快离子压强作外部强迫项**固定扣除，σ 不动** |
| `FR-EQ-009` | MUST | 内部约束行（MSE）走几何健康门控、不旁路；标定与装配两层分离 |
| `FR-EQ-010` | MUST | kinetic-EFIT 自洽外环：**证书**含逐遍 χ²/dof 与映射移动；**最优遍收官** |
| `FR-EQ-011` | MUST | 源剖面曲率正则，opt-in；A/B 下把简并解压回 |
| `NR-EQ-003` | MUST | 后验 / σ 带随拟合报出 |
| `NR-EQ-004` | MUST | 孪生度量取**可观测空间**（预测的测量对实际测量），不取内部量 |
| `NR-ENV-001` | MUST | 重构、剖面拟合与多步动理学反演在单机完成，不依赖服务端或调度器 |

### 偏置提示

这条链的流程与阈值出自 **DIII-D 生态**：诊断密、MSE 可用。搬到 MSE 缺失、CER 稀疏的装置上，
阶段 2 的电流约束退化为**由新经典公式主导的模型约束**，「自洽」的认识论地位从「数据约束」降为
「模型约束」——**收敛不蕴含正确**。EAST 正是这种情形。所以本章**不抄 DIII-D 的阈值**：
下面报的每个带都是量出来的，量不出来的写「未量」。

## 二 · 实现：链的每一段落在哪里

★★**一句话：链的每一段在 fylite 里都有名字，链本身没有。** 五个阶段里四个有内核 code 或 Python
入口；把它们串起来的东西——步序、步间交接、过期传播、回边——今天散在三处：页面上的人手、
Python 侧只记账不执行的簿记、内核仓测试树里不发行的一条外环。

| 阶段 | 落点（内核门 `code/…` · Python `S.…`） | 状态 |
| :--- | :--- | :---: |
| 0 基准平衡 | `code/reconstruction`（纯磁；命令行开关 `--only_magnetic`） | ✓ |
| 1.1 取数 | 测量三级解析（`--input` → 语料切片 → mdsip 取回）；★EAST 绑定表**无 Thomson · 无 CER · 无 ECE · 无 MSE** | ◐ |
| 1.2 ELM 相位平均 | `fylite.io.raw` 的 `elm_onsets` · `elm_phase` · `elm_phase_mask`，`reduce_series(elm=…)` 缺省关；★没有 Dα 的输入端口，序列要自己交进来 | ◐ |
| 1.3 映射 + 拟合 | `code/ladder`（描迹）· `code/profile_fit`（移位勒让德基 + GCV，Python 侧 `S.analysis.profit`） | ✓ |
| 1.4 分离面对齐 | `code/separatrix_align`：给 Tₑ,sep 解刚性标签平移；★**不产生 Tₑ,sep**（双点模型没有门），不给就按名拒绝 | ◐ |
| 1.5 Z_eff | 参数，不是推导（EAST 无 CER 的 n_C） | ◐ |
| 2.1 压强约束 | 压强行（`fylite:pressure` · `pressure_x` · `pressure_weight`）；快离子 `fylite:p_fast_profile` **扣除、σ 不动**（内核 2026-09-17）；★带 `derived-from-reconstruction` 出处的剖面**按名拒收** | ✓ |
| 2.2 电流约束 | `code/bootstrap`（Redl-2021）· `code/beam` · `code/rf_ray`；进设计矩阵的通道是**磁面平均电流形状行**（`fsa_x` · `fsa_shape` · `fsa_weight`）与预置电流 `current_source`；★把自举**逐遍重算再喂回**的那条环不在本分发 | ◐ |
| 2.3 MSE · E_r | **无**：内核里一行 MSE 都没有 | ✗ |
| 3 反演 | `code/reconstruction`：压强行 + 磁测量共进 χ²，p′ / FF′ 基阶数 `npp` / `nff`，曲率正则 `curv_p` / `curv_f`（opt-in，内核 2026-09-17）；报 `chi2` · `chi2_mag` · `chi2_kin` · `chi2_per_dof` · `worst_channel_sigma` 与后验 σ 带 | ✓ |
| 4 外环 | **重映射那一半在内核里**：`kinetic_passes` · `kinetic_tol` + 测点坐标 `pressure_r` / `pressure_z`，逐遍证书（内核 2026-09-17）；**重算自举那一半不在**：EFIT ↔ NEO 的完整环在内核仓测试树（`tests/oracles/loop.py`），随包清单 `kinetic_reconstruction` 标 `executable: false` | ◐ |
| 后验 | σ 带（`pprime_sigma` · `ffprim_sigma`）；二维验收与一致性检验**无 fylite 阈值** | ◐ |

### 三个面，到得了的键不一样

同一个 `code/reconstruction`，从三个入口进去，今天能摸到的键**不一样多**——这是本章最该记住的
一件实现上的事：

| 入口 | 动理学那几样 | 新键（外环 · 快离子 · 曲率） |
| :--- | :--- | :--- |
| **内核文档门** `fydoc.complete("code/reconstruction", …)` | 全部 | ✓ 全部 |
| **Python 装配层** `S.analysis.reconstruction(meas, pressure=…)` | 压强剖面 + σ 比例；出处检查；`kinetic` 标签 | ✗ 关键字表是写死的，`kinetic_passes` 之类传不进去 |
| **命令行** `fy run analysis reconstruction --kinetic` | `kin` · `neon` · `pointfit` 三开关、`pfast` · `pfastpk` · `tite` · `zeff` 等 46 个页面词表参数 | ✗ 实测：`kinetic_passes=6` 按名拒绝（「takes no parameter … did you mean kinetic?」） |

所以下面那条孪生走的是**文档门**——今天唯一三样新能力都到得了的入口。

### 内核门的动理学键

`code/reconstruction` 在 `discharge` 下读、在 `settings` 里收的动理学相关键（其余磁测量键见上一章）：

| 键 | 在哪 | 意思 |
| :--- | :--- | :--- |
| `fylite:pressure` · `fylite:pressure_x` | discharge | 压强读数 [Pa] 与它们的 ψ_N 标签 |
| `fylite:pressure_weight` | discharge | 逐点权重 1/σ（**逐点实测不确定度**）；不给则用 `pressure_sigma_frac` × 峰值 |
| `fylite:pressure_r` · `fylite:pressure_z` | discharge | 测点的 (R, Z)：给了，外环才有东西可重映；盒外的点**按名拒绝，不外推** |
| `fylite:p_fast_profile` | discharge | 快离子压强 [Pa]，均匀 ψ_N 网格；在权重算完**之后**扣除 |
| `fylite:fsa_x` · `fsa_shape` · `fsa_weight` | discharge | 磁面平均电流形状行（j/⟨j⟩）；★权重有量纲尺度，1e-7..1e-3 可用，1e-6 起步 |
| `kinetic_passes` · `kinetic_tol` | settings | 外环遍数上限（缺省 1 = 单遍，与外环存在之前逐位相同）与映射移动的收敛阈 |
| `curv_p` · `curv_f` | settings | p′ / FF′ 曲率罚的权重；缺省 0 = 一行不加 |

出来的证书（facts / fields）：`kinetic_passes_run` · `kinetic_best_pass` · `kinetic_best_chi2_per_dof` ·
`kinetic_map_shift`（**收官那一遍**的映射移动，不是最后一遍的）· `kinetic_pass_chi2_per_dof` ·
`kinetic_pass_map_shift`（整条迹）· `p_fast_max` · `curv_p` / `curv_f`（回显：一个悄悄生效的先验
是最坏的一种先验）· `notes`（「扣了多少」「在第几遍收官、后面几遍更差」都写在这里）。

## 三 · 跑一遍：孪生上的整条链

```bash
export FYDOC_ORACLE=<fydoc>/cases                  # reference case 23：#137985 的线圈电流与 Ip
export FYLITE_DEVICE_DIR=<fylite>/dist/facts/device/east
uv run --no-project --with numpy --with pyyaml python examples/kinetic/kinetic_twin.py > kinetic.json
```

脚本是 `examples/kinetic/kinetic_twin.py`，与校验册同一套孪生（`tools/benchmark-equilibrium.py`
的 `twin_truth`：#137985 @ 4.041 s 实测的线圈电流与 Ip，解析族 e_mp = e_np = 1 的前向解作真值，
它的 75 个磁通环 + 79 个探针读数作测量）。以下各数 2026-09-18 在本仓检出上实测（单机 16 s，重跑逐字节相同）。

**真值**：q₀ = 1.372006，q₉₅ = 3.358447，磁轴 (1.7222, 0.0079) m。

### 阶段 0 · 基准平衡

```python
f0, fl0, _ = recon()                      # 纯磁：npp = nff = 1，zc_anchor = -0.002
```

| 量 | 值 |
| :--- | ---: |
| q₀（相对真值） | 1.370374（−0.119 %） |
| q₉₅ | 3.354180 |
| χ²/dof（75 环 + 79 探针） | 5.60e-3 |
| 最劣单道 | 0.534 σ |
| **p′ 的 1σ 带 / p′（中位）** | **45.6 %** |

★★**最后一行才是这一段的结论。** 磁拟合好到 χ²/dof 5.6e-3，而 p′ 的后验带是它自身值的
将近一半——**磁测量管不住的方向，带宽把它说出来了**。这就是动理学约束要来填的那个空。

### 阶段 1 · 剖面构造

测点：真值磁轴同高度的中平面上 9 个点，R = 1.742 … 2.142 m，读数按真值压强剖面给，
σ 取峰值（21.9 kPa）的 5 %。映射到 ψ_N：0.008 · 0.060 · 0.168 · 0.325 · 0.520 · 0.739 · 0.963 · 1.0 · 1.0。

```python
fit = S.analysis.profit(xn, p_pts, sigma_frac=0.05)   # code/profile_fit：GCV 选阶 6，χ²/dof 0.393
```

★**最外两个点在分离面外**，被夹到 ψ_N = 1（压强 0）。与校验册那条记录逐点相同，这里照留，
但读者该知道：它们是两行「边界上压强为零」的约束，不是两个芯部测点。

**分离面对齐**（`code/separatrix_align`，一条合成的 tanh 台基，Tₑ(ψ_N = 1) = 19.0 eV）：

| 量 | 值 |
| :--- | ---: |
| 要的 Tₑ,sep | 80 eV |
| 解出的标签平移 Δ | +0.01532 ψ_N |
| 平移后 Tₑ(1) | 80.000 eV |
| 分离面梯度 | −2392 → −6232 eV/ψ_N（**2.6 倍**） |

★梯度那一行是这一步被叫作「影响最大」的原因：台基梯度与自举电流都由分离面落在哪里定，
百分之一点五的 ψ_N 平移就让边缘梯度翻了一倍多。★不给 `te_sep` 时它**按名拒绝**：「it comes
from the two-point model …, which has no `code/` door yet — this code will not invent one」。

### 阶段 3 · 动理学反演：映射给对，与故意给错

```python
f3, _, _ = recon({"fylite:pressure": p_pts, "fylite:pressure_x": xn, "fylite:pressure_weight": w})
```

| 映射 | q₀ 偏差 | χ²/dof | 动理学行 χ² | 映射移动 |
| :--- | ---: | ---: | ---: | ---: |
| 给对（真 ψ_N） | −0.126 % | 5.31e-3 | 2.5e-6 | — |
| **整体推错 +0.12，单遍** | **+7.12 %** | 0.810 | 8.36 | **0.234** |

★★**单遍那一次也报了自己的映射移动（0.234）**：一个不跑外环的调用方也会被告知「你这个解
不自洽到这个程度」。证书不需要你跑外环才肯说话。

### 阶段 4 · 自洽外环

```python
f4, fl4, notes = recon(rows_wrong, kinetic_passes=6, kinetic_tol=1e-4)   # rows_wrong 带 pressure_r / pressure_z
```

| 遍 | χ²/dof | 映射移动（ψ_N） |
| ---: | ---: | ---: |
| 1 | 0.8103 | 0.2345 |
| 2 | 0.1117 | 0.1505 |
| 3 | 0.01287 | 0.0390 |
| 4 | 0.006060 | 0.0113 |
| **5** | **0.005268** | **0.0031** |
| 6 | 0.005289 | 0.0008 |

收官：**第 5 遍**（`notes`：「the kinetic outer loop finished on pass 5 of 6 — the later pass(es) were
worse」），q₀ 偏差 **−0.070 %**，相对单遍**好了 101 倍**。

★★「取最优遍、不取最后一遍」这条为「交替不保证单调」写的防御，在这个算例上**当场触发**：
第 6 遍的映射移动更小，χ²/dof 却回升。★这个外环**只重映射**：它把测点按刚解出的场重新挂到
ψ_N 上，不重算自举、不重算快离子——链图里那条完整的回边，这一步只走了一半。

### 快离子压强：扣掉，σ 不动

```python
recon(dict(rows_true, **{"fylite:p_fast_profile": p_fast}))   # 芯部 15 %，向外衰减
```

| 量 | 不扣 | 扣 |
| :--- | ---: | ---: |
| 扣掉的峰值 | — | 3245 Pa |
| 测量权重 | — | **逐位相同** |
| 动理学行 χ² | 2.5e-6 | 0.440 |
| q₀ | 1.370271 | 1.325817（−3.2 %） |

★★**读法要对**：这个孪生的压强**全是热压强**，这里扣掉的是一份**本不存在**的快离子——所以
χ² 变坏、q₀ 被拉偏，恰恰说明扣除**真的进了拟合**（而不是只改了个回显的数），也说明上游给错
p_fast 的代价有多大。本段演示的是机制（先算 σ、后扣除、σ 不动），不是精度。

### 源剖面曲率正则：把简并档压回

```python
recon(npp=2, nff=2)                              # 多给自由度
recon(npp=2, nff=2, curv_p=1e-3, curv_f=1e-3)    # 加曲率罚
```

| 档 | q₀ 偏差 | χ²/dof |
| :--- | ---: | ---: |
| (1,1) 基线 | −0.119 % | 5.60e-3 |
| (2,2) 不正则 | **−31.5 %** | 3.07e-2 |
| (2,2) + λ = 1e-3 | −13.6 % | 1.92e-2 |

★真值的 p′ / FF′ 随 ψ_N 线性，把基抬到 (2,2) 答案**更坏**——多出来的自由度磁测量定不住。
正则把 q₀ 压回 2.3 倍，**而且 χ² 同时变好**：先验删掉的那个方向，数据本来也没在支持它。
★压回不彻底（离基线仍远），λ 的响应非单调——这是一个要 A/B 着用的开关，不是一个缺省值。

## 四 · 在真炮上：今天到哪一步

Python 装配层（与上一章同一条路）：

```python
from fylite import fyo
from fylite import scenario as S

meas = fyo.as_measurements("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld", 4.0)
fit  = S.analysis.profit(x, y, sigma_frac=0.05)          # x, y：你自己取来、映射好的剖面
r    = S.analysis.reconstruction(meas, pressure=fit)     # r["kinetic"] is True
```

命令行（2026-09-18 实测 `--dry-run`）：

```console
$ fy run analysis reconstruction --device east shot=137985 time=4.0 --kinetic --dry-run
analysis · reconstruction  ->  code/reconstruction   (template (built in), 46 parameters declared)
  device   east from <buildin>  -> <buildin>:device/east (resolved magnetics=pcs, wall=base)
  kin                  true                   cli:switch kinetic
  neon                 true                   cli:switch kinetic
  pointfit             true                   cli:switch kinetic
  …
  input measurements   (not fetched)          would fetch: device=east shot=137985 time=4.0
                                              ids=[magnetics, pf_active, tf] via <mdsip>
```

★`--kinetic` 解析得通、测量会经 mdsip 取回，而 `pressure` 端口要你自己 `--bind`——绑定表里
没有 Thomson，fylite 替你取不到剖面。外环今天**没有命令**：`fy run` 一份计划一个 code，
回边要由宿主逐轮驱动（按设计，每一轮是一次 `--resume-from`）。

## 边界

- **孪生不是真炮。** 真值与测量同出 fylite 自己的前向解，本章各数只能声称「反演与前向互为逆」；
  拿它们去说「fylite 的动理学反演准到 0.07 %」是过度解读。
- **外环只重映射。** `kinetic_passes` 解决的是「剖面挂在别人的平衡上」这一件事；「新平衡 → 重算
  自举 / 快离子 → 再反演」的完整回边不在本分发，自举电流今天是产物，不逐遍进设计矩阵。
- **没有 MSE。** 约束阶梯的第二级（加 MSE）在内核里一行都没有，`FR-EQ-009` 仍空着；没有 MSE，
  芯部电流（q₀）在真炮上主要由模型约束，**收敛不蕴含正确**。
- **Tₑ,sep 要你给。** `code/separatrix_align` 只做平移；双点模型没有门，缺 `te_sep` 按名拒绝。
- **新能力只在文档门上。** `kinetic_passes` · `p_fast_profile` · `curv_p` / `curv_f` 今天 Python 装配层
  与命令行都传不进去；要用就走 `fydoc.complete("code/reconstruction", …)`。
- **阈值只写量过的。** 二维验收（GS 残差 × 磁 χ²）与一致性检验（锯齿反转半径、中子产额）今天
  没有 fylite 阈值，也没有对应的测量端口；本章不给绿灯。
- 同一条链在校验册里的记录：外环 ·
  快离子 ·
  曲率正则 ·
  后验带。

<!-- BEGIN GENERATED: tools/examples-book.py —— 勿手改 -->

## 本章的文件

点文件名即得原文。计划可以原样跑、原样改（`fy run <文件>`），脚本用 `python <文件>`；目录、上下文与场景模板是给计划引用的，不单独跑。

| 文件 | id | 标题 |
| :--- | :--- | :--- |
| [`kinetic_twin.py`](kinetic_twin.py) | — | KEFIT 动理学反演算例：在 EAST #137985 @ 4.041 s 的孪生上把整条链逐段跑一遍。 |

<!-- END GENERATED -->
