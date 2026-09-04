---
title: V-13 · extended Lengyel 正向求解：这些杂质给出什么靶温
---

# V-13 · extended Lengyel 正向求解：这些杂质给出什么靶温

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX（extended_lengyel_solvers.forward_mode_fixed_point_solver） · git:b4d40633（TORAX 1.4.3） · Apache-2.0 |
| **对象** | fylite: rust/fylite/src/edge.rs（正向定点）+ fylite.kernel.lengyel_forward |
| **算例** | `scenario/lengyel-converged-states`（extended Lengyel 的二十个收敛态） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_lengyel_forward.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——7 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 靶温（10 个正向算例，含 4 个完全脱靶） | relative | 1e-09 | machine_precision |  |
| 求解器结局标签 | absolute | 0.0 | machine_precision | 离散标签，逐例相等 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/edge.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★★**上游的正向答案离它自己的不动点还有 0.22 %**，这是本条最要紧的一句。逆向循环 25 次已收敛（100 次移动 <1e-12）；正向循环带 0.4 欠松弛，25 次**没有**收敛：实测 25→17.765664、50→17.726348、100→17.726281、200 起稳定。所以复现上游意味着复现**次数**，不是把根求得更准——一个迭代到收敛的移植会对模型更准确、对参照错误。
- ★★**两处改变答案（而非只改导数）的实现细节，都是量出来才发现的**。其一：`q_cc²` 为负时上游不截零，用一个在阈值以下线性外推的**平滑根**（它是可微代码，截零会让梯度在最需要方向的地方消失）。fylite 不可微、本可以截零——四个脱靶算例说不行：截零给恰好零，上游给 6e-6…4e-4 eV，都叫「脱靶」，只有一个是参照。其二：正向循环看起来松弛三个量，实际只松弛 `q_parallel`——上游把 `prev_sol_model = current_sol_model` 后**原地改**，尾部那次「松弛」的前值就是刚写进去的值，是空操作。本移植照做，夹具是裁判：三个都松弛对不上。
- ★**多起点与 `multiple_roots_found` 未移植**：同一组输入可能有多解，本移植找的是初值引向的那一个，调用方在这里**得不到**「是否还有别的根」这个信息。
- ★★`Q_CC_SQUARED_NEGATIVE` 是**结果不是错误**（完全脱靶）；靶温被截到一个小正数以免把 NaN 传下去，而「脱靶」这个事实住在标签里。四个脱靶算例的靶温判据**断言它不为零**——那正是与截零方案的分界。
- ★这条只说「我们和它算得一样」，不说「该信它」。
- （判据）离散标签，逐例相等
- （场景）★★这些态**只对派生量是合法 oracle**。对定点仍在更新的量（`alpha_t`/`q_parallel`/`kappa_e`）它们是错的 oracle——报告的态落后一步，残差是停机规则不是物理（见 V-10）。
- （场景）★算例连**收敛点的派生态**一起记（`divertor_Z_eff` 等）：没有它 `kappa_e` 无法比对。
- （场景）★状态按**名字**记不按序号；四个「完全脱靶」（`Q_CC_SQUARED_NEGATIVE`）算例照记——**在那里「收敛」的移植不是更强，是错的**。
- （场景）★扫描是**一次只动一个旋钮**：网格更大但说得更少，移植需要的是「错在哪个输入上」。
- （场景）上游可重取（github.com/google-deepmind/torax，Apache-2.0），存的是数值 + 出处 + 复现配方。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 靶温最劣相对（十例） | 1.265e-13 |  | 成立 |  |
| 结局标签，10/10 一致 | 0.0 |  | 成立 |  |
| ★25 次与真不动点的差距（该算例） | 0.0022 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_lengyel_forward.py | 7 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/torax/extended_lengyel.json | sha256:fb195e68e4e5921f307fc6bd955e232ea0706d0e4ac987b8653c0271e34fb4c8 | public | 119008 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `oracle/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_lengyel_forward.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
