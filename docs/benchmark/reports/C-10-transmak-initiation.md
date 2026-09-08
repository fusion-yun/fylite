---
title: C-10 · ITER 起始的线圈磁通：拿 TRANSMAK 自己的电流过本仓的装置描述
---

# C-10 · ITER 起始的线圈磁通：拿 TRANSMAK 自己的电流过本仓的装置描述

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | TRANSMAK · A. Kavin · K. Lobanov · A. Mineev，Final Report on Contract ITER/CT/09/4300000030（2010-09），ITER_D_3TPCKG；五个场景各自随件的线圈电流与磁通 · restricted（ITER IDM Internal Use） |
| **对象** | fylite: 装置描述（fydoc 装置书的 ITER pf_active A-Box：几何 · 匝数）+ 内核互感核 `mutual_filaments` / `element_filaments` |
| **算例** | `scenario/iter-plasma-initiation`（ITER 等离子体起始：五个装料/起始位置组合（TRANSMAK 2010 研究）） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_corpus_is_the_five_transmak_scenarios`；`$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_we_read_the_currents_not_the_voltages`；`$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_our_flux_from_their_currents_matches_their_stated_initial_flux`；`$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_verdict_does_not_depend_on_where_the_flux_is_evaluated`；`$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_deficit_is_not_the_filament_discretisation`；`$FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_trajectory_is_not_judged_and_this_is_why` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——6 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 起始时刻的极向磁通（用参考自己的线圈电流），5 场景 × 5 个取值半径 R = 4…8 m | relative | 0.06 | measured_band | 实测 25 点全部落在 **−1.05 % … −4.95 %**，加一档余量；★★**判据在每个半径上都成立**——件里没说磁通在哪一点取，若只在一个半径上成立，那就是拟合出来的答案而不是比较 |
| 偏差的**符号**（是系统偏置还是散布） |  | — | measured_band | ★25 点同号（全部偏低）。系统偏置可以追到原因，散布不能——两者是不同的发现，故分开判 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-17-transmak/FYDOC-CASE-17-transmak.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**这一条不评研究的物理**：击穿、雪崩、燃穿一概没比。它只问一件事——**本仓对 ITER 线圈组的描述，能不能复现该研究由自己的电流算出的磁通**。
- ★★2026-09-08 之前本条记 `blocked-known`，挡路的是 fydata `G-14`（A-Box 把 `pf_active/coil/element` 写成单结构而 DD 记 AoS，十三台装置一台也跑不动 `code/breakdown`）。G-14 当日修掉（fydata `0e114a1`），本条才做得成。
- （判据）实测 25 点全部落在 **−1.05 % … −4.95 %**，加一档余量
- （判据）★★**判据在每个半径上都成立**——件里没说磁通在哪一点取，若只在一个半径上成立，那就是拟合出来的答案而不是比较
- （判据）★25 点同号（全部偏低）。系统偏置可以追到原因，散布不能——两者是不同的发现，故分开判
- （场景）★★★**磁通在哪一点取，件里没说**。表头只写「poloidal flux, Wb」。所以在这个场景上立判据必须先证明结论**不依赖那个点**——起始时刻的磁通对 R 很平（R = 4…8 m 上只动 0.5…2.1 Wb），故初始磁通可判；**随时间的轨迹不可判**（实测最合的半径跑到 CS 膛内 R → 2 m，那不是读等离子体区磁通的地方）。
- （场景）★★**通道不是线圈**：研究记 `CS1` 一路，而 DD 记 `CS1U` 与 `CS1L` 两只（串联）。按名字对名字会**丢掉半个螺线管**——实测那会让磁通掉 18 %，而不是报错。
- （场景）★★**同一张表里有两套同名列**：`I and U` 表右侧（第 15-22 列）是**供电电压**，列名与电流表逐字相同、上方还有一行电阻。按名字取列会取到后一套——40 kA 读成 8500，量级差 200 倍而曲线形状照样像模像样。
- （场景）★**五份件的版式不一致**：四份把 `(t, psi)` 放在第 1-2 列，`60Wb inboard` 放在第 0-1 列。写死列号会把其中一个场景读成空的。
- （场景）★语料是 ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下、不在任何仓里。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 起始磁通，5 场景 × 5 半径 | −1.05 % … −4.95 %（118Wb 内侧 −1.14 % · 118Wb 外侧 −1.77 % · 60Wb 内侧 −2.48 % · 60Wb 外侧 −2.44 % · First Plasma −1.05 %，均在 R = 6 m） |  | 成立 | 把参考自己的十一路电流过本仓的 ITER 线圈几何与匝数、再用内核的互感核求和；两侧唯一共享的是**电流** |
| ★★偏差是**系统的**，25 点同号 | 25/25 偏低 |  | 成立 | 系统偏置可追因，散布不可；门里分开判，免得哪天变成散布还继续报绿 |
| ★把两个显然的嫌疑排掉了 | 细分 2×2 → 16×16 只动 **0.25 %** 且收敛（116.21 → 116.51 Wb）；CS 匝数取 553 而非 554 只动 **0.13 个百分点** |  | 成立 | 所以那 1.1 % 既不是本测试把导体切得不够细，也不是登记在案的 554/553 之差——缺口在两侧的装置描述之间（参考取自 `[33NHXN]`，本仓这份取自 `2ACJT3 v3.1`） |
| ★★★磁通随时间的轨迹**不判** | 最合的取值半径跑到 CS 膛内（R → 2 m） | partly-holds | 部分 | 件里没说磁通在哪一点取。等离子体区没有任何一点复现它的曲线，故那条 `psi(t)` 是研究自己某种螺线管链磁通口径。**报出来，不判它**——同 B-09 的平顶段；★能了结这一条的是研究自己的报告正文（`Contract 4300000030-Subtask1-Final2010.pdf`）对该量的定义 |
| ★★读这批件的三个坑（都已立断言） | 通道≠线圈（`CS1` 一路两只，按名对名丢半个螺线管 → 磁通掉 **18 %**）· 同名列两套（右侧第 15-22 列是电压，取错量级差 200 倍）· 五份件版式不一（一份的 `(t, psi)` 在第 0-1 列） |  | 成立 | 三个坑的共同点：**都不会报错**，只会给出一条看着正常的曲线 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_corpus_is_the_five_transmak_scenarios | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_we_read_the_currents_not_the_voltages | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_our_flux_from_their_currents_matches_their_stated_initial_flux | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_verdict_does_not_depend_on_where_the_flux_is_evaluated | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_deficit_is_not_the_filament_discretisation | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_transmak_initiation.py::test_the_trajectory_is_not_judged_and_this_is_why | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $ITER_SCENARIO_ROOT/Study_of_plasma_initiation_using_TRANSMA_3TPCKG_v1_0/ | — | restricted |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_transmak_initiation.py::test_the_corpus_is_the_five_transmak_scenarios tests/test_transmak_initiation.py::test_we_read_the_currents_not_the_voltages tests/test_transmak_initiation.py::test_our_flux_from_their_currents_matches_their_stated_initial_flux tests/test_transmak_initiation.py::test_the_verdict_does_not_depend_on_where_the_flux_is_evaluated tests/test_transmak_initiation.py::test_the_deficit_is_not_the_filament_discretisation tests/test_transmak_initiation.py::test_the_trajectory_is_not_judged_and_this_is_why
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（C 确认）的问题，不外推。
