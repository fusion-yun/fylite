---
title: V-14 · TORAX 五秒 ITER 混合演化：同一份 QLKNN_7_11 权重，通量组合层的两个实现
---

# V-14 · TORAX 五秒 ITER 混合演化：同一份 QLKNN_7_11 权重，通量组合层的两个实现

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX · git:b4d4063349dcab9241da6a7658a1a2083cf9b59d (TORAX_VERSION 1.4.3) · Apache-2.0 |
| **对象** | fylite: scenario.model.qlknn.flux_from_targets / fluxes + nn.rs |
| **算例** | `scenario/torax-iterhybrid-evolution`（ITER 混合运行情景，五秒演化（TORAX `test_iterhybrid_predictor_corrector`）） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level1_composition_on_torax_own_inputs`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level1_would_have_caught_the_unclipped_leading_flux` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：未评估——0 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 八个通量/增长率通道，按 TORAX 自己喂进网络的十列输入求值，85 次调用 × 26 个面 | relative | 1e-09 | machine_precision | 同一个网络、同一组输入列：这是一个函数的两个实现，容差只能是机器精度，物理带只会盖住缺陷；用逐通道峰值归一而非逐点相对：五个通道是比值且大量恰零，逐点比在 1e-14 量级的项上报出无意义的大数 |
| 算例是否真的走到 ITG 阈值以下（主通量原始目标为负的点数） | count | 100.0 | measured_band | ★下限 100 是**非空虚性**的地板而不是精度带：实测 1338；★不是精度判据，是**非空虚性**判据：若这条不成立，上面那条就没有在考截零规则 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYDATA_ORACLE/torax/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）同一个网络、同一组输入列：这是一个函数的两个实现，容差只能是机器精度，物理带只会盖住缺陷
- （判据）用逐通道峰值归一而非逐点相对：五个通道是比值且大量恰零，逐点比在 1e-14 量级的项上报出无意义的大数
- （判据）★下限 100 是**非空虚性**的地板而不是精度带：实测 1338
- （判据）★不是精度判据，是**非空虚性**判据：若这条不成立，上面那条就没有在考截零规则
- （场景）★★**算例的输运装配是场景的一部分，不是背景**。该配置在 ρ < 0.15 处方 χ = 1.0（inner patch）、QLKNN 只在 0.15 < ρ ≤ 0.95 上跑、outer patch 因台基掩膜先切在 ρ ≥ 0.9 而**从不生效**、逐点截到 [0.05, 100]，最后对整条剖面做宽度 0.1 的高斯卷积（`transport_model.py::_build_smoothing_matrix`）。拿裸闭包输出去比它，量到的 89 % 分歧几乎全部是那次缺席的卷积——比的是两个不同的对象。
- （场景）★★**台基是内部边界条件**（`rho_norm_ped_top` = 0.9），所以剖面在那里有折点。ρ = 0.88 是台基顶下的最后一个面，本仓的胞→面梯度规则（中心差分后插值）会跨折点抹平，而 TORAX 直接在面上差分。端到端残差**整个落在这一个面上**，不是散布在剖面上——这是场景带来的判据而不是本仓的容差。
- （场景）★**网络输入里的 `smag` 不是输出文件里的 `magnetic_shear`**：是 `calc_s_rmid`（对中平面半径取的剪切，`psi_calculations.py:218`），并且随后被三项修正改写（沙氏位移 α/2、q < 1 的锯齿代理、强反剪切的下限）。混同两者是那一列上 20–30 % 的静默误差。
- （场景）★**ETG 修正因子在两码上缺省不同**：TORAX 缺省 1/3（`pydantic_model.py:127`），本仓缺省 1.0（网络自己的答案）。本场景按算例的取值显式传入 1/3；比较任何一侧的缺省跑法都会在电子热道上差三倍，而两边都按设计工作。
- （场景）★**85 次网络调用与 29 个输出时刻不是同一张表**：预估—校正一步不止调一次网络，求解器还走了从不落盘的步。按序号配对比的是不同时刻，得到的每一条差异都是时间错位假扮成建模差异。录制脚本因此把剖面**捕在同一次调用里**；ρ 上的配对靠状态逐位相等，不靠序号。
- （场景）★不复现的部分：TORAX 的有效 D/V 分解、输运求解器本身、台基模型、源项组合。本场景比的是闭包与输运装配，不是仿真。
- （场景）上游可重取（TORAX `b4d40633`，`TORAX_VERSION` 1.4.3，Apache-2.0）；权重 QLKNN_7_11 来自 `fusion_surrogates`（软件 Apache-2.0，**权重 CC-BY-4.0**），两侧读的是同一份档案，其 sha256 记在本仓 `nn_tables/qlknn_7_11.npz` 的 `source_sha256` 里。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 八通道 × 2210 点，最劣（比该通道峰值） | 2.238e-15 |  | 成立 | 逐通道最劣：qi_itg 1.86e-15 / qe_itg 2.21e-15 / pfe_itg 2.24e-15 / qi_tem 1.61e-15 / qe_tem 8.12e-16 / pfe_tem 1.64e-15 / qe_etg 1.19e-15 / gamma_max 1.57e-15 |
| 阈值以下的点数 | 1338（占 2210 的 61 %） |  | 成立 |  |
| ★★本条查出的缺陷：主通量未截零 | 已修（scenario/model/qlknn.py:flux_from_targets） |  | 成立 | 上游在**两个分支**都截零：比值通量是 target × max(leading, 0)，主通量是 max(target, 0)。本仓只截了分母，主通量原样返回；★★两条规则在上游自带的 25 个测试向量上**逐位相同**——那 25 个点的主通量全为正。分开它们要一条真实放电走到 ITG 阈值以下，那里原始目标为负，未截零的主通量就是**负热流**，即输运顺梯度向上跑；★本仓测试里手写的判据复现了作者对源码的同一处误读。手写判据就是干这个的，也正是它抓不到的东西 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level1_composition_on_torax_own_inputs | 未执行 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level1_would_have_caught_the_unclipped_leading_flux | 未执行 |  |

结论：**未评估**（`re-run: gate not executed`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/torax/evolution_qlknn_inputs.json | sha256:6355083e8699120c0a2f709818f706e5440c3ad4220b094e73c2999e2fca45ae | public | 1157345 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_torax_evolution.py::test_level1_composition_on_torax_own_inputs tests/test_torax_evolution.py::test_level1_would_have_caught_the_unclipped_leading_flux
```

## 6. 结论

登记册：成立。复测 2026-09-02：未评估。只回答本条自己那一类（V 验证）的问题，不外推。
