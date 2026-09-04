---
title: V-10 · extended Lengyel 的闭式：分界面几何、alpha_t、q_parallel、kappa_e
---

# V-10 · extended Lengyel 的闭式：分界面几何、alpha_t、q_parallel、kappa_e

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX（divertor_sol_1d + extended_lengyel_formulas） · git:b4d40633（TORAX 1.4.3） · Apache-2.0 |
| **对象** | fylite: rust/fylite/src/edge.rs（闭式半）+ fylite.kernel.lengyel_closed |
| **算例** | `scenario/lengyel-closed-form-grid`（extended Lengyel 闭式的自变量网格） |
| **数据** | 见 §5 表（2 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_lengyel_closed.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——7 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 七个闭式（108 点） | relative | 1e-09 | machine_precision |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/edge.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**只是闭式那一半。** extended Lengyel 分成闭式（分界面几何、alpha_t、q_parallel、kappa_e）与一个求根（靶温与达到它所需的杂质浓度）。求解器**未移植**，同一份夹具里的二十个正向/逆向收敛算例是留给它的 oracle，不属于本条。
- ★★**收敛态是闭式的错 oracle，而且是量出来的**：在收敛点重算这几个量，对报告值只到 1.6e-8 / 1.7e-7 / 4.6e-3——因为定点是按**容差**收敛的，报告的态比它被报告时所处的态**落后一步**。那不是物理上的分歧，拿它立闸就是在量停机规则。所以闭式按**函数**记：上游自己的例程、在这里选定的输入上直接求值，中间没有任何迭代。
- ★★**三个常数必须对齐，第三个才是要点。** 上游用 `mu_0 = 4π×1e-7`（2019 年前的定义）与落后一版的 `m_e`/`epsilon_0`，对齐后几何从 5.4e-10 到 1e-16。第三个是 `CONSTANTS.eps = 1e-7`——**名字像机器 epsilon，实为正则化项**，只出现在 `alpha_t` 电荷修正的 `(Z_eff - 1 + eps)` 里。在 `Z_eff = 1` 处该项**就是** eps，用机器 epsilon 会把 `alpha_t` 移动 **1.78e-7**：小到像舍入、却比本模块其余部分高六个数量级，且在实测之前已由 `(1-0.569)·(eps/3.25)^0.85` 精确预言。
- ★网格**刻意包含 Z_eff = 1**（正则化项唯一显形处；不含它则带着机器 epsilon 也能通过）以及 T_e 与 Z_eff **独立**变化的点对（否则记录无法见证「更宽的通量管携带更少平行通量」这一符号——Body 式 49 抄错就会翻转它）。
- ★这条只说「我们和它算得一样」，不说「该信它」：Body 2025 的模型本身没有在本条里对任何实验或 SOLPS 类模拟做确认。
- （场景）★没有输运、没有时间演化：这是一族闭式，网格是它的自变量空间。用它做 validation 是范畴错误。
- （场景）★★**刻意包含 Z_eff = 1**：`alpha_t` 的电荷修正里 `(Z_eff-1+eps)` 只在那里由正则化项主导，网格避开它就会漏掉一个 1.78e-7 的偏移。
- （场景）★★**T_e 与 Z_eff 独立变化**：否则不存在「只差 alpha_t」的点对，而那是见证「更宽的通量管携带更少平行通量」所必需的。
- （场景）★与同一份记录里的二十个收敛算例**不是一回事**：那些是留给尚未移植的求解器的 oracle。
- （场景）上游可重取（github.com/google-deepmind/torax，Apache-2.0），存的是数值 + 出处 + 复现配方。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| shaping_factor 最劣相对 | 1.2e-16 |  | 成立 |  |
| b_pol_avg / q_cyl / pitch 最劣相对 | 3.738e-16 |  | 成立 |  |
| kappa_e 最劣相对 | 0.0 |  | 成立 |  |
| alpha_t 最劣相对 | 7.061e-16 |  | 成立 |  |
| q_parallel 最劣相对 | 1.494e-15 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_lengyel_closed.py | 7 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-16-torax/extended_lengyel.json | sha256:fb195e68e4e5921f307fc6bd955e232ea0706d0e4ac987b8653c0271e34fb4c8 | public | 119008 B |
| $FYDOC_ORACLE/FYDOC-CASE-16-torax/record_extended_lengyel.py | sha256:7713f08efa847afd25cabd85f2b2396b06bb20085f7c6efae61880349c8a15e4 | public | 20611 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_lengyel_closed.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
