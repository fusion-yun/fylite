---
title: C-05 · 环向动量输运对 GYRO 非线性回旋动理学（Waltz 2007 Table I）
---

# C-05 · 环向动量输运对 GYRO 非线性回旋动理学（Waltz 2007 Table I）

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | GYRO · Waltz et al., Phys. Plasmas 14, 122507 (2007) · published |
| **对象** | fylite: gyrofluid.rs 的环向应力准线性权重与饱和层 |
| **算例** | `scenario/ga-standard-rotating`（GA 标准算例，Miller 几何，带平行速度剪切） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_tglf_momentum.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——13 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 有效普朗特数 eta_par_eff/chi_Ei_eff（γ_E=0） | absolute | — | reference_stated |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/benchmark/reports/V-01-gacode-ports.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （场景）★没有装置、没有时间演化、没有平衡求解：局部几何与梯度是给定的，不是从剖面推出来的。用它做 validation 之外的推广是范畴错误。
- （场景）★★**饱和规则必须两边都写明，不能有一边靠缺省**。算例自己的设置是 SAT_RULE = 0，本仓这一支不带；记录在案的量是 SAT_RULE 1 与 2 下测的，UNITS 随预设（规则 2 → CGYRO）。算例自带的 SAT_RULE 0 答案存为**出处**而不是判据。这一条是写出来的教训：同一个陷阱在能量道与动量道各犯过一次，第二次花了三轮才归因。
- （场景）★V-05 用它时把驱动**全部关掉**并断言上下对称（ZMAJ_LOC/DZMAJDX_LOC/ZETA_LOC/S_ZETA_LOC 全零），因为宇称定理只在那个条件下成立——那是同一组几何参数的**另一个**用法，不是同一次运行。
- （场景）★剪切 1.0 比本仓 JINTRAC 各 deck 高一个量级，所以它探到的是动量道的量级而不是它的小扰动行为。
- （场景）上游可重取（GACODE `6357db306`，Apache-2.0），deck 存的是 `input.tglf.gen`——每个值都由上游自己解析定下，没有在这里猜任何缺省。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| Pr，γ_P=1.0（GYRO 0.86） | 0.637（规则 1）/ 0.718（规则 2） |  | 成立 | ★带宽是有意的：准线性模型对非线性模拟。它排除的是因子二、符号错、丢一个几何因子 |
| Pr，γ_P=0.2（GYRO 0.74） | 0.682（规则 1）/ 0.759（规则 2） |  | 成立 |  |
| γ_E=0.2 的两行（GYRO 报 −0.31 / −0.74，符号反转） | 未通过 |  | 部分 | ★不可归因于模型类差异：对**上游自己**同规则也差 6–12×，见 V-01 的 T-C33。该缺口修好之前，这两行判不了 GYRO |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_tglf_momentum.py | 13 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-18-waltz2007-momentum/table_I_and_tglf.json | sha256:b335eff4beda0b5e2d3d8cc602d73e60c1b7d73ca02f1c002757b792d2a12557 | public | 3504 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_tglf_momentum.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（C 确认）的问题，不外推。
