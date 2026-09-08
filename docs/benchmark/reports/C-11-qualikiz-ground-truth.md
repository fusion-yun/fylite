---
title: C-11 · QuaLiKiz 本体：神经代理相对于它所近似的物理，误差有多大
---

# C-11 · QuaLiKiz 本体：神经代理相对于它所近似的物理，误差有多大

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | QuaLiKiz · 本机构建 `bin/QuaLiKiz-gcc-release-default-mpi.exe`（2026-08-02）；参考侧只用**上游自带**算例的答案 · public |
| **对象** | fylite: QLKNN_7_11 组合层（神经代理） |
| **算例** | —（无场景：局部或解析） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_every_point_is_inside_the_training_box`；`$FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_ion_heat_flux_is_low_by_about_half_and_systematically_so`；`$FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_electron_flux_is_worst_exactly_at_the_threshold`；`$FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_particle_flux_changes_sign_in_both`；`$FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_impurity_channel_has_no_counterpart_in_the_surrogate` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——5 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 逐通道通量（电子热 · 离子热 · 粒子） |  | — | measured_band | ★带在实测后定，而且**这条记录的产出就是那条带**——「代理误差有多大」正是它要回答的问题，事前给带等于事前给答案 |
| 临界梯度附近的行为 |  | — | measured_band | ★代理最可能失真的地方；只报全域平均误差会把它平掉 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-11-qlknn/FYDOC-CASE-11-qlknn.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★这一条问的不是「fylite 对不对」，是「**代理相对于它所近似的物理**差多少」——差多少本身就是要记录的量
- （判据）★带在实测后定，而且**这条记录的产出就是那条带**——「代理误差有多大」正是它要回答的问题，事前给带等于事前给答案
- （判据）★代理最可能失真的地方；只报全域平均误差会把它平掉

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 离子热通量 | 系统性偏低约一半：−42…−53 %（八点几乎同一因子，散布 < 20 %） |  | 成立 | ★是**系统偏置**不是散布，可被一个常数因子改正——这对下游与「一堆随机的差」是两回事，门里分开判 |
| ★★电子热通量最差的一点恰在阈值上 | +131 %（A_ti=8）：QuaLiKiz 的 efe 由 20.1 掉到 6.4（ITG 接过 TEM/ETG），网络平滑穿过（22.6 → 14.7） |  | 成立 | **最差点落在阈值上，不在两端**；只报全域平均会把这件事平掉，所以门里既判带、也判最差点的位置 |
| 粒子通量 | 换号两侧都复现 |  | 成立 |  |
| ★★成分折叠的代价随数走 | Be 那一支在低梯度端的热通量比氢两支合计还大，而网络只模一个有效主离子 | partly-holds | 部分 | 算例是「红/蓝氢」示踪设置（两支同位素氢 + Be + C）。所以离子那一栏的差里**含着成分折叠**，不全是代理误差。拆开它要换一个单主离子的参考算例 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_every_point_is_inside_the_training_box | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_ion_heat_flux_is_low_by_about_half_and_systematically_so | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_electron_flux_is_worst_exactly_at_the_threshold | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_particle_flux_changes_sign_in_both | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_qlknn_vs_qualikiz.py::test_the_impurity_channel_has_no_counterpart_in_the_surrogate | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $THIRD_PARTY/QuaLiKiz/QuaLiKiz-pythontools/testdata/example_red_blue_hydrogen/ | — | public |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_qlknn_vs_qualikiz.py::test_every_point_is_inside_the_training_box tests/test_qlknn_vs_qualikiz.py::test_the_ion_heat_flux_is_low_by_about_half_and_systematically_so tests/test_qlknn_vs_qualikiz.py::test_the_electron_flux_is_worst_exactly_at_the_threshold tests/test_qlknn_vs_qualikiz.py::test_the_particle_flux_changes_sign_in_both tests/test_qlknn_vs_qualikiz.py::test_the_impurity_channel_has_no_counterpart_in_the_surrogate
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（C 确认）的问题，不外推。
