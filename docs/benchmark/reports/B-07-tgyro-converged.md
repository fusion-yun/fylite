---
title: B-07 · 定态解本身：匹配出的梯度剖面对 TGYRO 的收敛答案
---

# B-07 · 定态解本身：匹配出的梯度剖面对 TGYRO 的收敛答案

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | TGYRO (GACODE) · 6357db306，FUYUN_WSL · 4 进程 · TGYRO_RELAX_ITERATIONS=4（残差 2.273 → 0.1793） · public |
| **对象** | fylite: TGLF 端口 + 通量匹配（在 TGYRO 的背景态上定梯度） |
| **算例** | `scenario/gacode-regression`（GACODE 自带回归算例（局部通量面）） |
| **数据** | 见 §5 表（1 项，纳入类别 public-derived） |
| **门** | `$FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_matched_gradients_land_where_tgyro_puts_them`；`$FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_inner_radius_is_stiff_and_that_is_why_the_flux_gap_is_not_the_answer`；`$FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_comparison_beats_doing_nothing` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 收敛梯度剖面（逐半径，通量差经**实测刚度**折算为梯度当量偏移） | relative | 0.08 | measured_band | 实测最劣 5.7 % + 一档余量；★零假设（不匹配、直接取初始剖面）133.7 %，带必须比它紧一个数量级，门里有一条断言守着这件事 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-15-tgyro/FYDOC-CASE-15-tgyro.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★两条限制随数走，不留在注释里：偏移是**经实测刚度线性化**的，不是真求根（每半径一次二维求根，r/a=0.5 上一次通量求值 290 s——这是取舍不是疏忽）；背景态（密度 · 几何 · betae）固定在 TGYRO 第 0 次迭代，而 TGYRO 每迭代都重积分剖面
- 所以量的是「**在 TGYRO 的背景上**本仓 TGLF 把梯度定在哪」，不是本仓独立解出的定态
- （判据）实测最劣 5.7 % + 一档余量
- （判据）★零假设（不匹配、直接取初始剖面）133.7 %，带必须比它紧一个数量级，门里有一条断言守着这件事
- （场景）★局部算例没有装置、没有时间演化：它固定一个面的状态，问湍流/新经典/几何的答案。用它做 validation 是范畴错误。
- （场景）上游可重取（gafusion/gacode，Apache-2.0），所以这一档的参考数据存的是指针与版本，不是本体。

## 3. 量到的（图）

:::{figure} ../figures/B-07-band.svg
:alt: B-07 量到的数对它被判的判据
:width: 100%

**结果对标准**：每一条量到的数画在它被判的那条带上，竖线是判据本身，条越短余量越大。判定栏只说「成立」，这张图说**差多少**。
:::


## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 梯度当量偏移，逐半径 | 最劣 +5.7 %（离子，r/a=0.35），其余 −1.4 %…+4.5 %（带 8 %） |  | 成立 |  |
| ★★比通量会把结论说反 | r/a=0.2 上通量差 28 % / 40 %，而梯度只差 1.7 % / 2.3 %；调和两者的是**刚度** dlnQ/dln(a/L_T) ≈ 15（本门**现测**，不引文献） |  | 成立 | 第二条断言把这个读法钉住：刚度若掉到个位数，这套读法本身不再成立，门会说出来 |
| 零假设 | 133.7 %（本条比它紧十六倍以上） |  | 成立 | ★★**零假设不是处处站不住**：r/a=0.5 上解几乎不动（0.3 % / 1.6 %），只在那一点取样的比较会把自己衬得很好看。设带时这一点必须单列，否则一条只测了一个不动点的判据会长期报绿 |
| ★参考侧的名字是「迭代到底（as declared）」不是「收敛」 | 4 次是算例自己声明的次数，残差仍在 0.18 |  | 部分 | 用它做参考时这一点要一并带上——把它叫收敛，是一句后来的读者无从察觉的小夸张 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_matched_gradients_land_where_tgyro_puts_them | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_inner_radius_is_stiff_and_that_is_why_the_flux_gap_is_not_the_answer | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_tgyro_converged.py::test_the_comparison_beats_doing_nothing | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/data/FYDOC-CASE-15-tgyro/corpus/treg02-converged/ | sha256-manifest:41ce4f55ce006a120be9ed4ce5d5a48abd831634e512c3aa79584f7f9c123062 | public-derived | 30 files, 79088 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_tgyro_converged.py::test_the_matched_gradients_land_where_tgyro_puts_them tests/test_tgyro_converged.py::test_the_inner_radius_is_stiff_and_that_is_why_the_flux_gap_is_not_the_answer tests/test_tgyro_converged.py::test_the_comparison_beats_doing_nothing
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
