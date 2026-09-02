---
title: V-11 · extended Lengyel 的两点态派生量与 Z_eff（在上游自己的收敛态上）
---

# V-11 · extended Lengyel 的两点态派生量与 Z_eff（在上游自己的收敛态上）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX（divertor_sol_1d 的派生属性 + extended_lengyel_formulas.calc_Z_eff） · git:b4d40633（TORAX 1.4.3） · Apache-2.0 |
| **对象** | fylite: rust/fylite/src/edge.rs（两点态半）+ fylite.kernel.lengyel_two_point/lengyel_z_eff |
| **算例** | `scenario/lengyel-converged-states`（extended Lengyel 的二十个收敛态） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_lengyel_two_point.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——8 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 七个派生量（20 个收敛态） | relative | 1e-09 | machine_precision |  |
| Z_eff（分界面与偏滤器两处温度） | relative | 1e-09 | machine_precision |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/edge.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**收敛态在这里是对的 oracle，而在 V-10 里是错的**——差别值得写清楚。V-10 比的是 `alpha_t`/`q_parallel`/`kappa_e`，那正是定点**仍在更新**的量，报告的态落后于它被报告时所处的态，残差就是停机规则（1.6e-8/1.7e-7/4.6e-3）。本条把状态当**输入**、派生量从它读出，没有任何东西滞后：最劣 2.9e-16，七个里六个逐位相等。
- ★★`Z_eff` 在**两处温度**上都查：分界面的，以及**偏滤器入口**的。后者是 `kappa_e` 实际求值处，而顶层输出只报前者——把分界面那个喂给一个正确的移植会差 1.7e-2 且指不出位置（本套件已经栽过一次）。
- ★★一条写错的判据被算例推翻并留档：初版断言温度从**靶板**起沿磁力线单调上升。不对——靶板到对流/传导界面那一步不是传导而是经验拟合，`T_cc/T_target = 2·density_ratio/(1-momentum_loss)` 在 **20 eV 附近穿过 1**（1 eV 处约 5.9、10 eV 处 1.07、更热则稳定在 0.9961）。所以脱靶的冷靶远低于界面，贴附的热靶略高于界面。现按真实行为立judged。
- ★求根层仍**未移植**：本条查的是「给定态，派生量对不对」，不是「态找得对不对」。同一份夹具里的正向/逆向收敛过程留给它。
- ★这条只说「我们和它算得一样」，不说「该信它」。
- （场景）★★这些态**只对派生量是合法 oracle**。对定点仍在更新的量（`alpha_t`/`q_parallel`/`kappa_e`）它们是错的 oracle——报告的态落后一步，残差是停机规则不是物理（见 V-10）。
- （场景）★算例连**收敛点的派生态**一起记（`divertor_Z_eff` 等）：没有它 `kappa_e` 无法比对。
- （场景）★状态按**名字**记不按序号；四个「完全脱靶」（`Q_CC_SQUARED_NEGATIVE`）算例照记——**在那里「收敛」的移植不是更强，是错的**。
- （场景）★扫描是**一次只动一个旋钮**：网格更大但说得更少，移植需要的是「错在哪个输入上」。
- （场景）上游可重取（github.com/google-deepmind/torax，Apache-2.0），存的是数值 + 出处 + 复现配方。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 七个派生量最劣相对（其中六个逐位相等） | 2.88e-16 |  | 成立 |  |
| Z_eff_separatrix 最劣相对 | 1.002e-14 |  | 成立 |  |
| divertor_Z_eff 最劣相对 | 3.678e-15 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_lengyel_two_point.py | 8 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/torax/extended_lengyel.json | sha256:fb195e68e4e5921f307fc6bd955e232ea0706d0e4ac987b8653c0271e34fb4c8 | public | 119008 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_lengyel_two_point.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
