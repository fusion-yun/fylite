---
title: B-10 · CHEASE 定边界平衡：同一边界与剖面下的 GS 解
---

# B-10 · CHEASE 定边界平衡：同一边界与剖面下的 GS 解

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | CHEASE · 本机构建，`ntcase=2` 解析算例（本轮自行重跑，不读冻结产物） · public |
| **对象** | fylite: GS 残差判据与 COCOS 口径测量（measure_cocos） |
| **算例** | —（无场景：局部或解析） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `python/tests/test_chease_equilibrium.py::test_chease_equilibrium_satisfies_our_grad_shafranov`；`python/tests/test_chease_equilibrium.py::test_the_convention_is_read_not_assumed`；`python/tests/test_chease_equilibrium.py::test_refining_the_internal_grid_lowers_the_residual`；`python/tests/test_chease_equilibrium.py::test_refining_the_output_box_does_not_lower_it_and_that_is_the_finding` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——4 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| Grad–Shafranov 残差（CHEASE `ntcase=2`，**输出盒 201×129 · 默认内部网格**） | relative | 0.08 | measured_band | ★带必须同时点名**两个**分辨率：输出盒与内部网格，两者各自都改变这个数 |
| 口径：从数里读出的 COCOS 对文件名声称的 |  | — | machine_precision | ★这是嵌在对拍记录里的一句 **verification** 断言：判的是一条恒等式或一个离散标签（两侧搬运同一个约定），不存在可以被物理带覆盖的建模差异，故取机器精度是正当的；★不信文件名：件名写着 `COCOS_02`，本仓自己从数里读出「每弧度 · psi_axis 取极小」，余量约 70 倍 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$THIRD_PARTY/chease/（上游随码文档与算例说明）`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**本条的主要产出不是那个残差数，是一个读法**：g-file 上的 GS 残差是文件的属性
- （判据）★带必须同时点名**两个**分辨率：输出盒与内部网格，两者各自都改变这个数
- （判据）★这是嵌在对拍记录里的一句 **verification** 断言：判的是一条恒等式或一个离散标签（两侧搬运同一个约定），不存在可以被物理带覆盖的建模差异，故取机器精度是正当的
- （判据）★不信文件名：件名写着 `COCOS_02`，本仓自己从数里读出「每弧度 · psi_axis 取极小」，余量约 70 倍

## 3. 量到的（图）

:::{figure} ../figures/B-10-band.svg
:alt: B-10 量到的数对它被判的判据
:width: 100%

**结果对标准**：每一条量到的数画在它被判的那条带上，竖线是判据本身，条越短余量越大。判定栏只说「成立」，这张图说**差多少**。
:::


## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| `ntcase=2` 解析算例，盒 201×129 · 默认内部网格 | GS 残差 5.257e-02（带 8e-2） |  | 成立 |  |
| ★★★一份 g-file 上的 GS 残差量的是那份文件，不是算子的截断误差 | ①固定内部网格、加密输出盒：101×65 5.023e-02 → 201×129 5.257e-02 → 401×257 6.394e-02（**不降反升**）；②固定输出盒、加密内部网格：ns=20 8.722e-02 → 默认 5.257e-02 → ns=60 4.134e-02（降 2.1 倍） |  | 成立 | **加密盒子不是收敛检验**：盒子加密时差分算子变锐，而 ψ 与右端的 p′/ff′ 仍只有内部解那么细——残差因此变大；★★**这条读法回过头修正了 `C-06` 的注记**：那边测到残差随盒子只掉一阶而非二阶，当时只记下「有一部分不是算子的截断误差」。本条给出了那一部分是什么，且用**可拧的旋钮**证明了它；★**这正是本条相对 C-06 / C-07 的价值**：那两条的语料是 ITER IDM 的冻结产物（读者复算不了，旋钮也拧不动）；CHEASE 开源、本机可构建、算例自带。立项理由不是「参考取不到」，是**受限载荷进不了公开渲染件** |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_chease_equilibrium.py::test_chease_equilibrium_satisfies_our_grad_shafranov | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_chease_equilibrium.py::test_the_convention_is_read_not_assumed | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_chease_equilibrium.py::test_refining_the_internal_grid_lowers_the_residual | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_chease_equilibrium.py::test_refining_the_output_box_does_not_lower_it_and_that_is_the_finding | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $THIRD_PARTY/chease（本机构建；`ntcase=2` 随码自带算例） | — | public |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_chease_equilibrium.py::test_chease_equilibrium_satisfies_our_grad_shafranov python/tests/test_chease_equilibrium.py::test_the_convention_is_read_not_assumed python/tests/test_chease_equilibrium.py::test_refining_the_internal_grid_lowers_the_residual python/tests/test_chease_equilibrium.py::test_refining_the_output_box_does_not_lower_it_and_that_is_the_finding
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
