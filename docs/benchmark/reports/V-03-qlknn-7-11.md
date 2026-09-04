---
title: V-03 · QLKNN_7_11：单网对上游自带测试向量，组合层对上游 flux_map
---

# V-03 · QLKNN_7_11：单网对上游自带测试向量，组合层对上游 flux_map

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | fusion_surrogates（qlknn_model.QLKNNModel.predict_targets —— 上游自己的推理路径，25 点测试向量的产出者） · git:d678186 · Apache-2.0（软件）/ CC-BY-4.0（权重与元数据）；QLKNN_7_11（权重，archive 版本标记 11D） · git:d678186 · CC-BY-4.0 |
| **对象** | fylite: fylite.nn + scenario.model.qlknn（内核未改） |
| **算例** | `scenario/qlknn-box`（QLKNN_7_11 训练盒内的点：上游自带的 25 点测试向量） |
| **数据** | 见 §5 表（3 项，纳入类别 private-artefact、public） |
| **门** | `$FYLITE_KERNEL/tests/test_nn_qlknn.py`；`$FYLITE_KERNEL/tests/test_nn_surrogate.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——27 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 八目标输出（25 点） | absolute | 1e-09 | machine_precision |  |
| 组合层八通道（flux_map 逐条重导） | absolute | 0.0 | machine_precision | ★容差是 0.0 而不是一个小数：flux_map 的组合是同一个数组上的乘与截零，两个实现之间没有可积累的浮点差异可言，所以机器精度在这里就是逐位相等。 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/nn_tables/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★2026-08-30 换模型：本条原记 QLKNN-10D 的二十网与它对 QLKNN-fortran 回归算例的组合对拍（最劣 1.900e-07，那档容差整个来自 JINTRAC 包里未取回的 Git-LFS 权重件）。QLKNN_7_11 是一个网、八目标，上游**自带 25 点测试向量并以十位小数自测**，所以两档判据都回到机器精度，不再需要实测带。
- ★这条只说「我们和它算得一样」，不说「该信它」：QLKNN 训练在 QuaLiKiz 上，本条没有对任何实验或第三方模型做确认。
- ★内核零改动：上游 config 自报 network_type=mlp / tanh / hidden_size=133 / num_hiddens=5，正是 nn.rs 已有的族（n_hidden_layers=4, n_blocks=0）。导出器在写之前逐条断言这四项，上游改架构就拒绝而不是错映。
- ★输入基与退役的九维**不可改名互换**：Zeff 出局，稀释改由 Ani 与 normni 承载；LogNuStar 到达时已是对数，故 log10_mask 全零。
- ★不再有 D/V 分解：dfe 两网随二十网退役，本模型只给粒子**流**。有效 D/V 是 caller 侧对流与密度梯度的算术（TORAX 自己就有 DV_effective 与 Dscaled 两种约定），在此固定其一才是错。
- ★ETG 修正因子默认 **1.0**（网络自己的答案），TORAX 默认 1/3。那是从 QLKNN10D 实践继承的物理调整，对一个另行训练的网默许套用等于给一个本仓没测过的数——旋钮留着，默认不动。
- ★输入钳制默认**关**（与上游、与 TORAX 一致）：钳制把外插变成一个看起来合理的数，本仓的报告路径是 outside_training_box。
- ★单位是 QuaLiKiz 自己的回旋玻姆归一，与 TGLF 的**不可互换**，本仓不做换算。
- 缺的通道（exchange / 逐 ky 谱 / 离子粒子流 / 动量应力 / D-V 分解）是**拒绝**而不是给零（QlknnChannelUnavailable）。
- （判据）★容差是 0.0 而不是一个小数：flux_map 的组合是同一个数组上的乘与截零，两个实现之间没有可积累的浮点差异可言，所以机器精度在这里就是逐位相等。
- （场景）★没有装置、没有时间演化、没有平衡：十个输入是给定的，不是从剖面推出来的。用它做 validation 是范畴错误——它连模型对不对都没问。
- （场景）★★2026-08-30 取代 `scenario/qlknn-hyper-box`（已退役的登记项）（QLKNN-10D 的九维盒 32 点 + QLKNN-fortran 回归剖面 24 点）。换模型的同时换了输入基：Zeff 出局，Ani 与 normni 进来，两组点**不可互相换算**。
- （场景）★盒内取点也**只**说盒内。7_11 的训练集含 QLKNN7D-edge，比 qlknn-hyper 的纯芯部盒宽，但「更宽」不等于「够用」。
- （场景）上游可重取（github.com/google-deepmind/fusion_surrogates；软件 Apache-2.0，权重与元数据 CC-BY-4.0），所以权重存的是导出件加 sha256，不是原始档案。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 八目标 vs 上游测试向量（25 点，最劣绝对） | 1.634e-13 |  | 成立 |  |
| 同上，最劣相对 | 6.373e-15 |  | 成立 |  |
| 组合层 vs flux_map 手工重导（8 通道 x 25 点，最劣绝对） | 0.0 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_nn_qlknn.py | 13 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_nn_surrogate.py | 14 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/nn_tables/qlknn_7_11.npz | — | private-artefact |  |
| $FYDOC_ORACLE/qlknn/qlknn_7_11_upstream.json | sha256:1fb6752a8ea5efc41b50fe685bcf8ddaf4fb9bdde489e52b1b639338bb19d5a1 | public | 10144 B |
| $FYLITE_KERNEL/rust/tools/export_qlknn_7_11.py | sha256:0a2b3fb35b8778db1fc1df66386cb61b1db0b822164b1b282e5508649d211f08 | private-artefact | 11543 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_nn_qlknn.py tests/test_nn_surrogate.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
