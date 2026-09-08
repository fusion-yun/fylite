---
title: C-06 · ITER 参考平衡集（TEQ / CORSICA 写出）上的 Grad–Shafranov 判据
---

# C-06 · ITER 参考平衡集（TEQ / CORSICA 写出）上的 Grad–Shafranov 判据

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | TEQ / CORSICA · ITER 参考平衡，g-file 首行 `TEQ g 04/07/2010 #900003` · restricted（ITER IDM Internal Use） |
| **对象** | fylite: GS 残差判据（Δ*ψ − RHS，边界内内点） |
| **算例** | `scenario/iter-reference-equilibria`（ITER 参考平衡集（TEQ / CORSICA 写出，三档分辨率）） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `python/tests/test_teq_equilibria.py::test_the_reference_equilibrium_satisfies_our_grad_shafranov`；`python/tests/test_teq_equilibria.py::test_the_sign_convention_needs_no_flip`；`python/tests/test_teq_equilibria.py::test_the_residual_falls_only_first_order_with_the_grid`；`python/tests/test_teq_equilibria.py::test_the_verdict_depends_on_the_resolution_and_that_is_recorded` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——6 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| Grad–Shafranov 残差 ‖Δ*ψ − RHS‖/‖·‖（边界内内点，**中分辨率 129×257**） | relative | 0.02 | measured_band | ★带必须点名分辨率：同一份平衡在 65×129 上是 3.665e-2，过不了这条带 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-13-teq/FYDOC-CASE-13-teq.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★C 类：量的是「本仓的定律判据在别人写出的平衡上读出什么」，不是两个平衡求解器谁更准
- （判据）★带必须点名分辨率：同一份平衡在 65×129 上是 3.665e-2，过不了这条带
- （场景）★★★**判决与分辨率绑定**：同一份物理平衡，GS 残差在 LR 上 3.665e-02、MR 1.487e-02、HR 7.948e-03。任何在这个场景上给出的带**必须点名分辨率**，否则换个网格就换个判决。
- （场景）★★**残差随网格只掉一阶**（比 0.406 / 0.534，二阶差分作用在光滑解上该给 0.250），所以残差里有一部分不是算子的截断误差。这个场景不判定那一部分是什么——`B-10` 用一份可以拧旋钮的开源平衡回答了它。
- （场景）★语料是 ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下、不在任何仓里：本场景只记指针与读法，不复制字节。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 三份参考平衡，中分辨率 129×257 | `2V2XYR` 15 MA 燃烧 1.487e-02（11 845 内点） · `2V3FDF` 9 MA 稳态 1.357e-02 · `34S6TV` 15 MA SOF 2.297e-04 |  | 成立 | ★SOF 比两个燃烧点好六十倍，与「陡边缘主导残差」一致 |
| ★★★残差随网格只掉一阶 | LR 65×129 3.665e-02 → MR 129×257 1.487e-02（比 0.406）→ HR 257×513 7.948e-03（比 0.534）；二阶差分作用在光滑解上应给 0.250 | partly-holds | 部分 | **所以残差里有一部分不是算子的截断误差**——候选是 p′/ff′ 为表格值、或解在边缘不够光滑。本条**不判定是哪一个**，只把标度记下并立一条断言守住这个读法；★★**后来 `B-10` 回答了它**：用一份可以拧旋钮的开源平衡证明了那一部分是「文件本身的分辨率」，不是算子 |
| ★★判决与分辨率绑定 | 0.02 的带在 MR / HR 上通过、在 LR 上不通过 |  | 成立 | 同一份物理平衡换个网格换个判决，所以带点名分辨率，门里也有一条断言把这件事钉住——免得日后有人塞进 LR 件、看到红色去怀疑平衡 |
| 符号约定 | 另一支（`+μ₀R²p′ + ff′`）在每一份上都给 ~2.0 |  | 成立 | 不需要任何 COCOS 翻转；这本身是一次口径确认，门里单列一条 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_teq_equilibria.py::test_the_reference_equilibrium_satisfies_our_grad_shafranov | 3 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_teq_equilibria.py::test_the_sign_convention_needs_no_flip | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_teq_equilibria.py::test_the_residual_falls_only_first_order_with_the_grid | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_teq_equilibria.py::test_the_verdict_depends_on_the_resolution_and_that_is_recorded | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $ITER_SCENARIO_ROOT/（TEQ 四份 ITER IDM 文档） | — | restricted |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_teq_equilibria.py::test_the_reference_equilibrium_satisfies_our_grad_shafranov python/tests/test_teq_equilibria.py::test_the_sign_convention_needs_no_flip python/tests/test_teq_equilibria.py::test_the_residual_falls_only_first_order_with_the_grid python/tests/test_teq_equilibria.py::test_the_verdict_depends_on_the_resolution_and_that_is_recorded
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（C 确认）的问题，不外推。
