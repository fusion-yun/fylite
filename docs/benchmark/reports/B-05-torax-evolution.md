---
title: B-05 · TORAX 五秒 ITER 混合演化：输入装配与输运装配的端到端对拍
---

# B-05 · TORAX 五秒 ITER 混合演化：输入装配与输运装配的端到端对拍

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | TORAX · git:b4d4063349dcab9241da6a7658a1a2083cf9b59d (TORAX_VERSION 1.4.3) · Apache-2.0 |
| **对象** | fylite: scenario.model.qlknn_closure（输入装配 / alpha / 剪切修正 / chi_gb） |
| **算例** | `scenario/torax-iterhybrid-evolution`（ITER 混合运行情景，五秒演化（TORAX `test_iterhybrid_predictor_corrector`）） |
| **数据** | 见 §5 表（2 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level2_the_pass_through_columns_are_exact`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level2_the_gradients_agree_in_the_confinement_region`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_the_shear_corrections_are_applied_and_matter`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_transport_on_torax_own_inputs`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_the_assembly_is_load_bearing`；`$FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_end_to_end_localises_to_the_pedestal_foot` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——6 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 直通列 q / x / normni（同一时刻，同一剖面） | absolute | 0.0 | machine_precision | ★这一条是嵌在对拍记录里的一句 **verification** 断言，所以取机器精度是正当的：这几列不经任何模型，两码搬运的是同一个数组，不存在可以被物理带覆盖的建模差异；★这几列不经任何模型：这里出现差异意味着网格或某个重标定动了，那会带着其余每一列一起移位 |
| R 归一梯度 Ati / Ate / Ane / Ani 与修正后剪切 smag，约束区 0.2 ≤ ρ ≤ 0.8 | relative | 0.08 | measured_band | 实测中位最劣 1.7–1.9 %（梯度）/ 0.6 %（剪切），最大 6.2 %；带取 8 %：松到不会对胞→面规则报警，紧到换掉一个归一长度或漏个二因子藏不住 |
| χ_i / χ_e，按 TORAX 自己的十列输入过**算例的整套输运装配**，29 个时刻 × 26 个面全取 | relative | 0.05 | measured_band | ★★装配是判据的一部分：内 patch（ρ < 0.15 处方 χ = 1.0）、QLKNN 只在 0.15 < ρ ≤ 0.95、外 patch 因台基掩膜而从不生效、截到 [0.05, 100]、最后宽度 0.1 的高斯卷积。缺席卷积时同一比较读作 89 %；★包含落在 χ_min 上的 17 % 的点，不做遮蔽 |
| 端到端残差是否仍**只落在台基脚**（ρ = 0.88 对 ρ ≤ 0.84） | relative | 5.0 | measured_band | ★不是精度判据，是**归因**判据：钉住『差在哪一个面上』。若哪天不再成立，说明残差改了性质，此条的叙述先失效 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYDOC_ORACLE/FYDOC-CASE-16-torax/corpus/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★**不能读作『两码都对不对得上真实托卡马克』**：两侧共享网络与算例，其余各自实现，所以带是关于两个实现链的事实，不是关于物理的证据。
- ★不复现的部分：TORAX 的有效 D/V 分解、输运求解器本身、台基模型、源项组合。本条比的是闭包与输运装配，不是仿真。
- （判据）★这一条是嵌在对拍记录里的一句 **verification** 断言，所以取机器精度是正当的：这几列不经任何模型，两码搬运的是同一个数组，不存在可以被物理带覆盖的建模差异
- （判据）★这几列不经任何模型：这里出现差异意味着网格或某个重标定动了，那会带着其余每一列一起移位
- （判据）实测中位最劣 1.7–1.9 %（梯度）/ 0.6 %（剪切），最大 6.2 %；带取 8 %：松到不会对胞→面规则报警，紧到换掉一个归一长度或漏个二因子藏不住
- （判据）★★装配是判据的一部分：内 patch（ρ < 0.15 处方 χ = 1.0）、QLKNN 只在 0.15 < ρ ≤ 0.95、外 patch 因台基掩膜而从不生效、截到 [0.05, 100]、最后宽度 0.1 的高斯卷积。缺席卷积时同一比较读作 89 %
- （判据）★包含落在 χ_min 上的 17 % 的点，不做遮蔽
- （判据）★不是精度判据，是**归因**判据：钉住『差在哪一个面上』。若哪天不再成立，说明残差改了性质，此条的叙述先失效
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
| q / x / normni | 0.0（q 与 normni 逐位；x 除轴点外 1.3e-16） |  | 成立 | ★轴上 x 两码本就不同：TORAX 先把它压到自己的正则化常数 1e-7 再做纵横比重标定，忠实的 r_mid/a 恰为零。已作为**已识别差异**断言而非藏进容差；网络不对 x 取对数，故物理上惰性 |
| 梯度四列，约束区最劣的中位 / p90 / 最大 | Ati 1.70 / 3.36 / 5.16 % · Ate 1.91 / 4.93 / 6.19 % · Ane = Ani 1.68 / 1.96 / 2.05 % |  | 成立 |  |
| 修正后剪切 smag，同一窗口 | 0.61 / 1.02 / 1.20 % |  | 成立 |  |
| ★★未修正剪切（同一窗口，同一参照） | 40.4 / 41.7 / 43.4 % |  | 成立 | ★★本条查出的缺陷：本仓闭包**一项剪切修正都没做**。TORAX 在问网络之前对剪切做三件事——减去沙氏位移的 α/2（代理没有 α 输入列，位移只能以移位后的剪切进入）、把 q < 1 换成锯齿代理、给强反剪切设下限；★**大小读在剪切这一列上，不读在 χ 上**：原始剪切 40.4 %、修正后 0.61 %。★★χ 是错的测点——裸闭包剖面在相邻两面之间就在下限与阈值尖峰之间跳，**修不修正它的中位都坐在 χ_min 上**，什么也说不出。过完算例的输运装配后，这三项修正值 42 %（不修正）对 11 %（修正）。〔本条早先写作『χ_i 被压在下限上』——那句话对剖面为真，作为证据为假，已改。〕；★★α 在热芯里是 order one，与剪切本身同量级；漏掉它不是小误差。三项修正是 QLKNN 模型**被使用的方式**的一部分——忠实求值网络而略去它们的端口，是把另一道题答对了；★网络输入里的 smag 也不是输出文件里的 magnetic_shear：是 calc_s_rmid（对中平面半径），混同两者本身就是 20–30 % 的静默误差 |
| χ_i / χ_e（TORAX 自己的输入 → 算例装配），754 点逐点相对 | 中位 1.17 % / 0.92 %；p90 2.70 % / 2.63 %；最大 3.03 % / 2.94 % |  | 成立 | ★这条把『网络之下的整条链』验完了：组合层、回旋玻姆单位、两个 patch、截断、卷积。残差是参照长度上的胞→面插值 |
| χ_i / χ_e（本仓自己的输入 → 同一装配），端到端 | 中位 10.9 % / 6.3 %；p90 2.7× / 5.3×；比剖面峰值则中位 4.2 % / 3.1 % | partly-holds | 部分 | ★两个范数都给，因为 χ 是在阈值附近取的**比值**：逐点相对在有输运的地方是对的范数，在 TORAX 已截到 χ_min 的地方（17 % 的点）一文不值——0.05 对 0.5 读作 900 %，在热平衡里什么也不是；★尾巴不是散布的：ρ ≤ 0.68 两边贴合，超出峰值一半的 119 个点全部落在 ρ ∈ [0.72, 0.88]，且**每个时刻都在** |
| ★★端到端残差的归因：台基脚 ρ = 0.88 对 ρ ≤ 0.84（逐列中位） | Ane 313 % 对 2.5 % · Ati 92 % 对 3.3 % · Ate 60 % 对 3.4 % · smag 47 % 对 6.2 % |  | 不成立 | ★★台基是**内部边界条件**（rho_norm_ped_top = 0.9），剖面在那里有折点。ρ = 0.88 是台基顶下最后一个面：本仓的胞→面规则（中心差分后插值）跨折点抹平，TORAX 直接在面上差分；★留作已归因缺口而非放宽容差：处置要动 fylite 的梯度装配（上游为此专门带了 two_point_mask 开关），而那会移动每一条已录答案；★0.72–0.84 之间梯度只差 1–3 % 而 χ 差到峰值的一半以上——那一段是**刚性**，不是缺陷：临界梯度附近 R/L_Ti 差一个百分点，通量不差一个百分点 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level2_the_pass_through_columns_are_exact | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level2_the_gradients_agree_in_the_confinement_region | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_the_shear_corrections_are_applied_and_matter | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_transport_on_torax_own_inputs | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_the_assembly_is_load_bearing | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_torax_evolution.py::test_level3_end_to_end_localises_to_the_pedestal_foot | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-16-torax/corpus/evolution_qlknn_inputs.json | sha256:6355083e8699120c0a2f709818f706e5440c3ad4220b094e73c2999e2fca45ae | public | 1157345 B |
| $FYDOC_ORACLE/FYDOC-CASE-16-torax/corpus/evolution_qlknn.json | sha256:9f1168276a17457aa32a0b694f5ba221844c26008430fc213fdb4a0a0cf466e7 | public | 417755 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_torax_evolution.py::test_level2_the_pass_through_columns_are_exact tests/test_torax_evolution.py::test_level2_the_gradients_agree_in_the_confinement_region tests/test_torax_evolution.py::test_the_shear_corrections_are_applied_and_matter tests/test_torax_evolution.py::test_level3_transport_on_torax_own_inputs tests/test_torax_evolution.py::test_level3_the_assembly_is_load_bearing tests/test_torax_evolution.py::test_level3_end_to_end_localises_to_the_pedestal_foot
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
