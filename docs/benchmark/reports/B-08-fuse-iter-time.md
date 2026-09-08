---
title: B-08 · FUSE 自带含时 ITER 回归算例：61 个时刻上逐通道对本仓算子
---

# B-08 · FUSE 自带含时 ITER 回归算例：61 个时刻上逐通道对本仓算子

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | FUSE · 1.1.5（git 22fff68bd），`FUSE.test_case(Val(:ITER_time), dd)`，2026-09-08 本机跑出 61 个时刻 · Apache-2.0 |
| **对象** | fylite: dt_reactivity（Bosch–Hale）· zerod_stored_energy · edge_noncoronal（Mavrin） |
| **算例** | `scenario/iter-time-dependent-pulse`（ITER 含时脉冲，300 秒自洽演化（FUSE 自带回归条目 `ITER_time`）） |
| **数据** | 见 §5 表（1 项，纳入类别 public-derived） |
| **门** | `$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_record_is_the_upstream_case_at_the_pinned_version`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_aggregate_source_is_not_a_channel`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_our_reactivity_tracks_fuses_fusion_power_along_the_whole_trajectory`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_fusion_layer_beats_holding_the_first_slice`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_alpha_share_is_a_rounding_convention_not_a_model_difference`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_thermal_energy_definition_agrees_on_fuses_own_composition`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_zerod_stored_energy_is_two_assumptions_cancelling`；`$FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_neon_radiation_gap_is_mostly_a_bookkeeping_split` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——8 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| P_fus，逐时刻（61 个） | relative | 0.01 | measured_band | 实测 1.0005…1.0012（最劣 0.12 %）+ 一档余量；★零假设（按住第 0 个时刻不动）**37 %**：轨迹上 P_fus 走 102.8 → 163.2 MW，所以「合到 0.12 %」不是信号没动出来的假象。门里单列一条 |
| 热储能的**定义**（用 FUSE 自己的成分与几何） | relative | 0.003 | measured_band | 实测 1.00009（最劣 0.04 %）。这一条判的是「两码是不是在说同一个量」，不是模型——所以带取得紧 |
| 0-D 热储能的两项假设，**各自**（不是只判合计） | relative | 0.005 | measured_band | ★★合计 +2.4 % 是 **+7.46 %（n_i = n_e）× 0.95215（体元）** 的乘积。三个数各自断言，改好一项就会让门变红，而不是悄悄挪动合计 |
| 氖辐射：**只记不判** |  | — | measured_band | ★不设带：口径未定完（见 finding）。同 B-09 的平顶段——口径没摆平的比较，报出来，不判它 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-04-fuse/corpus/1.1.5/README.origin.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★★**演化本身没有被对拍，也不该被**：本条只在 FUSE 每个时刻**自己的态**上问本仓的算子同一个量。把两码的推进摆在一起，比的是两套闭包，缝会被读成物理——这正是 0.7.0 那份记录当初**不进登记册**的理由，那条理由至今成立。
- ★本条把 B-01 的四层做法沿轨迹铺开：同样是「拿参考自己的态问我们的算子」，区别是 61 次而不是 1 次——这才使**相消**那一类缺陷显形。
- （判据）实测 1.0005…1.0012（最劣 0.12 %）+ 一档余量
- （判据）★零假设（按住第 0 个时刻不动）**37 %**：轨迹上 P_fus 走 102.8 → 163.2 MW，所以「合到 0.12 %」不是信号没动出来的假象。门里单列一条
- （判据）实测 1.00009（最劣 0.04 %）。这一条判的是「两码是不是在说同一个量」，不是模型——所以带取得紧
- （判据）★★合计 +2.4 % 是 **+7.46 %（n_i = n_e）× 0.95215（体元）** 的乘积。三个数各自断言，改好一项就会让门变红，而不是悄悄挪动合计
- （判据）★不设带：口径未定完（见 finding）。同 B-09 的平顶段——口径没摆平的比较，报出来，不判它
- （场景）★★★**演化本身不可对拍，逐时刻的通道可以**。把本仓的推进放到这条轨迹旁边，比的是「通量匹配的 TGLF+EPED」对「另一套闭包」，缝会被读成物理。所以在这个场景上立的判据只取**同一个态上的算子**：拿 FUSE 每个时刻自己的剖面与几何，问本仓的算子同一个量。评的是模块，不是仿真。
- （场景）★★**成分是稀释的**：n_i/n_e = 0.854（DT + He4 + Ne20）。任何把 n_i 当作 n_e 的 0-D 量在这条轨迹上都会系统性偏高——本场景实测这一项值 **+7.5 %**。
- （场景）★★**第一个时刻与其余不同**：t = 50 s 上 `∂/∂t` 源还不存在（要有前一步才差得出来），那里合计条目与其成员之和差 7.5e-4；其余 60 个时刻是机器精度。
- （场景）★**COCOS 符号**：B₀ = −5.3 T，故 `q95` 与整条 `q` 为负、`radiation_losses` 为负。记录保留符号。
- （场景）★上游未随码发布本算例的输出：参考侧的答案必须自跑（2026-09-08 已跑，收在 fydoc `FYDOC-CASE-04-fuse/corpus/1.1.5/`）。**禁用**已遗弃的 0.7.0 旧记录顶替。

## 3. 量到的（图）

:::{figure} ../figures/B-08.svg
:alt: B-08 的对拍结果
:width: 100%

由 `tools/benchmark-figures.py` **自语料重画**（不是把记录里的数抄成图）；语料与判据见下两节。
:::

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| P_fus，61 个时刻逐一（Bosch–Hale 两个独立实现） | 1.0005 … 1.0012（最劣 **0.12 %**）；零假设 37 % |  | 成立 | B-01 在**一个**静止时刻上量到 1.0009；本条说的是那份一致性是**拟合本身的性质**，不是那一点的巧合；★唯一不是 FUSE 的输入是拆分：FUSE 把 D 与 T 记作一支 `DT`，故 n_D = n_T = n_DT/2 是本比较写明的假设 |
| α 份额是一个**取整口径**，不是模型差 | FUSE 在 61 个时刻上都取**恰好 1/5**（3.52/17.6）；本仓取 3.5/17.6 = 0.198864，差 0.57 % |  | 成立 | 整个 P_alpha 上的 0.52 % 偏置就是这一个常数。断言成口径（对 FUSE 那侧判到 1e-9），不并进物理带——并进去它会长得像模型差 |
| 热储能的**定义**：3/2 ∫(n_e T_e + Σ n_i T_i) dV 对 FUSE 的 `energy_thermal` | 1.00009（最劣 **0.04 %**） |  | 成立 | 两码对「热储能」是同一个意思——这一条立住之后，下一条的 2.4 % 才能被读作**建模假设**而不是量的分歧 |
| ★★★本条真正的产出：0-D 热储能的 2.4 % 是**两项假设相消** | 合计 **+2.43 %** = n_i = n_e **+7.46 %** × 体元 **−4.78 %**（1.0746 × 0.95215 = 1.0232）；本发 n_i/n_e = **0.854** |  | 成立 | ★★一个「距参考 2.4 %」的 0-D 量，看起来是「两个百分点的精度」，实则是两个五到七个百分点的假设指着相反方向。**单个时刻的比较看不见这件事**——要两项一起才解释得了那 2.4 %，而从合计里两项都看不出来；★体元那一项是**量出来的**：把算子的 T_i 置零，只留电子那一半，与精确 ∫dV 相比得 0.95215——不是从源码读出来的猜测；★★门里三个数各自断言、并断言它们的乘积：单修一项会让门变红。这正是「相消」这类缺陷需要的守法 |
| 氖辐射：2.73× 里大部分是记账口径 | 照字面 **2.73×**（本仓 Mavrin 对 FUSE `line Ne`）；把 FUSE 单列的轫致辐射中氖那一份（氖占 Σn_z Z² 的 **50 %**）加回来后 **1.29×** | partly-holds | 部分 | Mavrin 的冷却率是**总量**（线辐射 + 轫致 + 复合），而 FUSE 把轫致记成一条独立的全成分源。照字面比会把一次记账差写成「辐射模型差三倍」；★**剩下的 +29 % 不判**：上面那个份额是用**本仓自己的**平均电荷态算的，不是 FUSE 的。口径没摆平的比较，报出来，不设判据 |
| ★★第一个时刻与其余不同（记录的性质，不是舍入） | t = 50 s 上合计条目与成员之和差 **7.5e-4**（22.2 MW 中的 16.7 kW）；其余 60 个时刻 ~1e-16 |  | 成立 | 原因可读：`∂/∂t` 通道在第 0 个时刻还不存在（要有前一步才差得出来），从第 1 个时刻起才出现。在 t = 50 s 上自己求和的读者会与 FUSE 的合计对不上 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_record_is_the_upstream_case_at_the_pinned_version | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_aggregate_source_is_not_a_channel | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_our_reactivity_tracks_fuses_fusion_power_along_the_whole_trajectory | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_fusion_layer_beats_holding_the_first_slice | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_alpha_share_is_a_rounding_convention_not_a_model_difference | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_thermal_energy_definition_agrees_on_fuses_own_composition | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_zerod_stored_energy_is_two_assumptions_cancelling | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_fuse_iter_time.py::test_the_neon_radiation_gap_is_mostly_a_bookkeeping_split | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/data/FYDOC-CASE-04-fuse/corpus/1.1.5/iter_time_115.json | sha256:b1777eb99d851ea4b87fe39f7e449a25e8ebd7b32c1be3465f768765108134bd | public-derived | 8474362 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_fuse_iter_time.py::test_the_record_is_the_upstream_case_at_the_pinned_version tests/test_fuse_iter_time.py::test_the_aggregate_source_is_not_a_channel tests/test_fuse_iter_time.py::test_our_reactivity_tracks_fuses_fusion_power_along_the_whole_trajectory tests/test_fuse_iter_time.py::test_the_fusion_layer_beats_holding_the_first_slice tests/test_fuse_iter_time.py::test_the_alpha_share_is_a_rounding_convention_not_a_model_difference tests/test_fuse_iter_time.py::test_the_thermal_energy_definition_agrees_on_fuses_own_composition tests/test_fuse_iter_time.py::test_the_zerod_stored_energy_is_two_assumptions_cancelling tests/test_fuse_iter_time.py::test_the_neon_radiation_gap_is_mostly_a_bookkeeping_split
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
