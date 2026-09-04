---
title: V-12 · extended Lengyel 逆向求解：达到靶温所需的杂质浓度
---

# V-12 · extended Lengyel 逆向求解：达到靶温所需的杂质浓度

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX（extended_lengyel_solvers.inverse_mode_fixed_point_solver） · git:b4d40633（TORAX 1.4.3） · Apache-2.0 |
| **对象** | fylite: rust/fylite/src/edge.rs（逆向定点）+ fylite.kernel.lengyel_inverse |
| **算例** | `scenario/lengyel-converged-states`（extended Lengyel 的二十个收敛态） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_lengyel_inverse.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——6 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 七个收敛量（10 个逆向算例） | relative | 1e-09 | machine_precision |  |
| 求解器结局标签 | absolute | 0.0 | machine_precision | 离散标签，逐例相等；容差 0 因为它没有可比大小的中间态 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/edge.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**为什么一个求解器也能立机器精度的闸**——这不是显然的。两个迭代实现通常只能对到各自的停机规则（本登记册在 V-10 里正是这么记的）。这里不适用，因为上游的定点**根本不测残差**：它跑**固定 25 次**。于是「收敛」是输入、更新顺序与那个次数的确定性函数，复现这三样就复现那个数。
- ★★**更新顺序是算法的一部分**，不是实现细节：先由当前分界面温度算 `q_parallel`，再解杂质浓度，再更新 `alpha_t` 与 `kappa_e` 供下一轮。顺序换了，同样跑 25 次会落在**另一个**不动点上。
- ★判据里专列一条钉住「次数确实要紧」（跑 3 次与 25 次不同）以及「25 次确实已收敛」（跑 100 次不再移动）——后者是这个固定次数站得住的理由，而不是运气。
- ★杂质解里的**尺度因子**照抄不化简：它们在结果里精确抵消，所以 f64 下省掉也对——然后在上游以 f32 运行的地方发散，而那正是它们存在的理由。
- ★★`C_Z_PREFACTOR_NEGATIVE` 是**结果不是错误**：等离子体在**完全不加种子**时已经低于靶温，达到它需要「负杂质」。浓度被截到零，所以只读数字的调用方会看到「不需要加种子」而错过「这个靶温够不着」——那个事实住在结局标签里，判据逐例比对标签。
- ★**正向模式未移植**：同一份夹具里的十个正向算例（含四个完全脱靶）留给它。
- ★这条只说「我们和它算得一样」，不说「该信它」。
- （判据）离散标签，逐例相等；容差 0 因为它没有可比大小的中间态
- （场景）★★这些态**只对派生量是合法 oracle**。对定点仍在更新的量（`alpha_t`/`q_parallel`/`kappa_e`）它们是错的 oracle——报告的态落后一步，残差是停机规则不是物理（见 V-10）。
- （场景）★算例连**收敛点的派生态**一起记（`divertor_Z_eff` 等）：没有它 `kappa_e` 无法比对。
- （场景）★状态按**名字**记不按序号；四个「完全脱靶」（`Q_CC_SQUARED_NEGATIVE`）算例照记——**在那里「收敛」的移植不是更强，是错的**。
- （场景）★扫描是**一次只动一个旋钮**：网格更大但说得更少，移植需要的是「错在哪个输入上」。
- （场景）上游可重取（github.com/google-deepmind/torax，Apache-2.0），存的是数值 + 出处 + 复现配方。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| c_z_prefactor 最劣相对 | 3.317e-14 |  | 成立 |  |
| alpha_t 最劣相对 | 2.665e-14 |  | 成立 |  |
| q_parallel 最劣相对 | 1.944e-14 |  | 成立 |  |
| T_e_separatrix 最劣相对 | 6.567e-15 |  | 成立 |  |
| Z_eff（两处）最劣相对 | 2.03e-14 |  | 成立 |  |
| 结局标签，10/10 一致 | 0.0 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_lengyel_inverse.py | 6 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-16-torax/extended_lengyel.json | sha256:fb195e68e4e5921f307fc6bd955e232ea0706d0e4ac987b8653c0271e34fb4c8 | public | 119008 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_lengyel_inverse.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
