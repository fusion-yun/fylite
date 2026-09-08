---
title: C-07 · ITER 平衡运行空间（TOSCA，2009 批，li 扫描 61 份）
---

# C-07 · ITER 平衡运行空间（TOSCA，2009 批，li 扫描 61 份）

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | TOSCA · 2009 批（45 份首行 `TOSCA_VT` · 16 份 `From TOSCA`） · restricted（ITER IDM Internal Use） |
| **对象** | fylite: EQDSK 读入端 + GS 残差判据 |
| **算例** | `scenario/iter-equilibrium-run-space`（ITER 平衡运行空间（TOSCA 2009 批：li 扫描 × PF6/偏滤器变体，61 份）） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `python/tests/test_tosca_equilibria.py::test_every_equilibrium_in_the_scan_is_readable`；`python/tests/test_tosca_equilibria.py::test_the_whole_scan_satisfies_grad_shafranov`；`python/tests/test_tosca_equilibria.py::test_the_sign_convention_holds_across_the_whole_scan`；`python/tests/test_tosca_equilibria.py::test_the_high_li_end_reaches_the_operator_floor`；`python/tests/test_tosca_equilibria.py::test_the_residual_is_much_worse_at_low_li_and_that_structure_is_the_finding` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——5 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| Grad–Shafranov 残差（61 份运行空间，65×129） | relative | 0.06 | measured_band | 全扫描上限（实测 max 4.51e-2）。★**它只是上限**：高 li 那两档另判 5e-4，否则这条带对它们松两个数量级 |
| 低 li 与高 li 之间的**对比度**（判结构，不判幅值） | relative | — | measured_band | ★门里判的是对比度：本条的产出是那个台阶，不是某一份的残差 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-07-tosca/FYDOC-CASE-07-tosca.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）全扫描上限（实测 max 4.51e-2）。★**它只是上限**：高 li 那两档另判 5e-4，否则这条带对它们松两个数量级
- （判据）★门里判的是对比度：本条的产出是那个台阶，不是某一份的残差
- （场景）★★**残差随 li 变，而且是台阶不是趋势**：0.57→4.32e-02 · 0.70→1.92e-02 · 0.85→1.38e-02 · 1.00→1.81e-04 · 1.20→1.69e-04——0.85 与 1.00 之间一步掉 75 倍，高 li 两档已落到本底（仓内合成件 1.47e-04 同量级）。〔推测，未判定〕平滑的物理效应不会这样跳，更像两个子批次（求解设置或收敛判据不同）。本场景钉住这个**结构**，不解释它。
- （场景）★★★**读得进来本身曾是缺口**：TOSCA 在头一行三个整数之后还写产码名（`… 3  65 129 TOSCA_VT`），而 `(a48,3i4)` 是按列定的。按「最后两个 token」解析的读入端在这 61 份上一份也读不进来，报的却是「header has no nw nh」——听着像文件坏了。
- （场景）★语料是 ITER IDM 件（Internal Use），不在任何仓里。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 61 份 EQDSK 全部评上 | min 1.62e-04 · 中位 1.22e-02 · max 4.51e-02；**0 份符号告警** |  | 成立 |  |
| ★★残差随 li 变，而且是台阶不是趋势 | 0.57→4.32e-02 · 0.70→1.92e-02 · 0.85→1.38e-02 · 1.00→1.81e-04 · 1.20→1.69e-04（Pearson −0.852）；低 li(≤0.75) 中位 1.95e-02 对高 li(≥1.00) 1.70e-04，**差 114 倍** | partly-holds | 部分 | 0.85 与 1.00 之间一步掉 75 倍；高 li 两档已达**本底**（仓内合成件 1.47e-04、TEQ 的 SOF 2.30e-04 同量级）；〔推测，未判定〕平滑的物理效应不会这样跳，更像**两个子批次**（求解设置或收敛判据不同）——要判定得看随附报告或问上游。本条只钉住这个结构 |
| ★★★先修了一个读入端的缺陷，这批才读得进来 | 61 份 → 0 份可读（修前）；61 份可读（修后） |  | 不成立 | TOSCA 在头一行三个整数**之后**还写产码名（`… 3  65 129 TOSCA_VT`），而本仓解析取「最后两个 token」、注记还写着「只有尾部是可靠的」——**61 份一份也读不进来**，报的却是「GEQDSK header has no `nw nh`」，听着像文件坏了；三份件（TOSCA · EAST 真炮 · 仓内合成）的列位**逐列相同**（48/52/56），因为 `(a48,3i4)` 本就规定了它。解析改为**按位先行、尾部兜底**（尾部那支也从「最后两个 token」改成「最后两个能解析成整数的 token」） |
| 代码归属 | 61 份首行都写着产码 |  | 成立 | 登记册此前「归属是推断得来的」那条**已不成立**，本轮撤除 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_tosca_equilibria.py::test_every_equilibrium_in_the_scan_is_readable | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_tosca_equilibria.py::test_the_whole_scan_satisfies_grad_shafranov | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_tosca_equilibria.py::test_the_sign_convention_holds_across_the_whole_scan | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_tosca_equilibria.py::test_the_high_li_end_reaches_the_operator_floor | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_tosca_equilibria.py::test_the_residual_is_much_worse_at_low_li_and_that_structure_is_the_finding | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $ITER_SCENARIO_ROOT/（TOSCA 两份 ITER IDM 文档，61 份 EQDSK） | — | restricted |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_tosca_equilibria.py::test_every_equilibrium_in_the_scan_is_readable python/tests/test_tosca_equilibria.py::test_the_whole_scan_satisfies_grad_shafranov python/tests/test_tosca_equilibria.py::test_the_sign_convention_holds_across_the_whole_scan python/tests/test_tosca_equilibria.py::test_the_high_li_end_reaches_the_operator_floor python/tests/test_tosca_equilibria.py::test_the_residual_is_much_worse_at_low_li_and_that_structure_is_the_finding
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（C 确认）的问题，不外推。
