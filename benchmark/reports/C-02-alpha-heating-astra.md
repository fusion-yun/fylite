---
title: C-02 · alpha 加热通道，对 ASTRA 的 ITER 15 MA 燃烧算例
---

# C-02 · alpha 加热通道，对 ASTRA 的 ITER 15 MA 燃烧算例

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | ASTRA |
| **对象** | fylite: heating.rs alpha_heating / alpha_fast_ions |
| **算例** | `scenario/iter-15ma-flattop`（ITER 15 MA 感应燃烧，平顶段） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `$FYLITE_KERNEL/rust/fylite/src/heating.rs::the_alpha_power_density_is_astras_own_answer_for_iter_15ma_at_burn`；`$FYLITE_KERNEL/rust/fylite/src/heating.rs::the_alpha_split_sits_below_astras_post_1984_partition_by_a_known_margin` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| alpha 功率密度 | pointwise | 0.03 | measured_band |  |
| 体积分 | relative | 0.003 | measured_band |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/sources.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （场景）★这是一个准稳态窗口：参考自己的 T_e(0) 在 16 s 内只走 −5.2 %，「什么都不做」的全剖面 RMS 就是 4.07 %。任何模型跑完若不比这条线好，它什么也没说。
- （场景）参考侧只解电流与电子温度两条方程；T_i 与 n_e 是给定的（见各 record 的 prescribes）。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 功率密度逐点 | 0.03 |  | 成立 |  |
| 体积分 | 0.003 |  | 成立 |  |
| e/i 分配比 Post-1984 解析积分 | 系统性低 11-14 % | banded | 部分 | 按带宽判，不按等式 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/rust/fylite/src/heating.rs::the_alpha_power_density_is_astras_own_answer_for_iter_15ma_at_burn | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/rust/fylite/src/heating.rs::the_alpha_split_sits_below_astras_post_1984_partition_by_a_known_margin | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/reference/iter15ma_astra_burn.csv | sha256:6dc1c70b94ef31c8ae8513522e847fdba47495ed64425a44306bd43adb5f326e | restricted | 20703 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest 
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（C 确认）的问题，不外推。
