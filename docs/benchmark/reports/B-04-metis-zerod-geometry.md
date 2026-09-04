---
title: B-04 · 0-D 体元约定，对 METIS 认证套件的平衡
---

# B-04 · 0-D 体元约定，对 METIS 认证套件的平衡

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | METIS · certification/metis，28 份存档，MATLAB 7.3 · CeCILL-C |
| **对象** | fylite: zerod.rs 的 volume_ellipsoid / volume_average / stored_energy |
| **算例** | `scenario/metis-certification-shapes`（认证套件的形状谱：圆截面到强成形） |
| **数据** | 见 §5 表（2 项，纳入类别 public、public-derived） |
| **门** | `$FYLITE_KERNEL/tests/test_metis_zerod.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——12 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| K-1 椭球体积 / vp，圆或椭圆截面（对照组） | relative | 0.002 | measured_band | Pappus 恒等式：此处非零即对齐有误，不是物理 |
| K-2 椭球体积 / vp，成形截面 | relative | 0.17 | measured_band |  |
| K-3 归一权重 2x vs vpr，作用在 n_e | relative | 0.04 | measured_band |  |
| K-4 stored_energy，喂参考侧的体积 | relative | 0.12 | measured_band |  |
| K-5 stored_energy，体积也由本仓给 | relative | 0.26 | measured_band |  |
| K-6 dt_reactivity 对 METIS zformsv，0.2–100 keV | pointwise | 1e-12 | machine_precision | 同一 Bosch–Hale Table VII 拟合的两个实现，属 verification 级子检查；★比的是 METIS 源码的一次转写，不是 METIS 的一次运行——本机无 MATLAB / Octave |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/tools/metis-cert-to-zerod.py`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★METIS 保存的 wth 不能拿来对：与它自己剖面的积分中位差 0.15 %，逐片最坏差 56 %（ELM 项 zero1t.m:1467；wth = taue·pth 分支 zero1t.m:1212）。能量一律对 wprof_J
- ★聚变功率这次没有对：METIS 的 pfus_th 与它自己剖面上的热核 DT 积分差 −4.7 %（ITER）到 −31 %（TFTR），含轨道展宽 / 快 α 慢化 / TAE 损失；相减量到的是快粒子物理，不是体元约定。关闭判据见报告 §5.2
- ★判 B 不判 C：两侧都是模型输出，METIS 不为 vp 自报精度，容差只能实测后定；判 C 会读成「几何经权威确认」，是夸大。见报告 §4.1
- ★与 C-04 相反，时间片无稳态要求：这里每个量都是该片自身几何与剖面的瞬时泛函，无历史项
- （判据）Pappus 恒等式：此处非零即对齐有误，不是物理
- （判据）同一 Bosch–Hale Table VII 拟合的两个实现，属 verification 级子检查
- （判据）★比的是 METIS 源码的一次转写，不是 METIS 的一次运行——本机无 MATLAB / Octave
- （场景）参数跨度（84 个时间片实测）：R 0.82–6.20 m · a 0.12–2.01 m · κ 0.98–1.91 · δ 0–0.60 · B₀ 0.41–5.50 T · I_p 25 kA–15 MA。
- （场景）★形状摘要 κ 在这批存档里不是同一个量：有的例给的是等面积拉长比（π a² κ 精确复现真分界面面积），有的给的是边界拉长比（π a² κ 比真面积高 11–12 %）。任何跨例的形状回归先要分开这两种定义，否则量到的是定义差。
- （场景）★★椭球体积式 2π²Ra²κ 对圆/椭圆截面是 Pappus 恒等式，不是近似。所以圆截面那一端的偏差为零是判据而非结果——非零即对齐有误。
- （场景）剖面在共用的 21 点归一环径格点 linspace(0,1,21) 上，全套存档一致；不得重采样。
- （场景）每个被比的量都是该时间片自身几何与剖面的瞬时泛函，无历史项，故时间片不需稳态筛选。
- （场景）主离子按例为 H / D / DT；杂质按 Z 给定（Z_imp ∈ {3,4,5,6,8}，Z_max ∈ {4,6,8,18,28}），元素名未在存档中声明，故此处不列。四条算例（含两条纯参数测试）不对应具名装置。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| M-1 椭球体积 / vp，圆截面 23 片，最坏 | 0.00116 |  | 成立 |  |
| M-1′ 椭球体积 / vp，成形 61 片，中位 / 最坏 | 0.0767 / 0.1625 |  | 成立 |  |
| M-2 权重 2x vs vpr，中位 / 最坏 | 0.0085 / 0.0350 |  | 成立 |  |
| M-3 stored_energy（参考侧体积），中位 / 最坏 | 0.0255 / 0.1081 |  | 成立 |  |
| M-4 stored_energy（本仓体积），中位 / 最坏 | 0.0680 / 0.2465 |  | 成立 |  |
| M-5 dt_reactivity 对 zformsv，最坏 | 6.4e-16 |  | 成立 |  |
| 零假设：丢掉 κ / 无径向权重 / 平权重能量（p95） | 0.4243 / 0.5021 / 1.1667 | baseline | 未评估 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_metis_zerod.py | 12 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-10-metis/corpus/metis_cert_zerod.csv | sha256:45eb266a6c85fd7852f826687611a783c62543f6537de58387d49a531724ffa8 | public-derived | 99956 B |
| $METIS/certification/metis/ | — | public |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_metis_zerod.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
