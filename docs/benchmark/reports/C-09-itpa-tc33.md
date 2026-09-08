---
title: C-09 · ITPA TC-33 ITER 15 MA 参考算例（IMAS IDS）上的 0-D 聚变功率
---

# C-09 · ITPA TC-33 ITER 15 MA 参考算例（IMAS IDS）上的 0-D 聚变功率

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | ITPA TC-33 参考解 · Zenodo doi:10.5281/zenodo.21391776（IMAS IDS，415 s / 450 s） · CC BY 4.0 |
| **对象** | fylite: 0-D 栏（zerod_fusion_power，剖面 `(1-ρ²)^p`，峰化由 brentq 解出） |
| **算例** | `scenario/itpa-tc33-iter-15ma`（ITPA TC-33：ITER 15 MA 感应燃烧的参考解（IMAS IDS，两个时刻）） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `python/tests/test_itpa_tc33.py::test_the_volume_averages_really_are_matched`；`python/tests/test_itpa_tc33.py::test_the_fusion_power_lands_within_the_band_on_the_reference_composition`；`python/tests/test_itpa_tc33.py::test_assuming_half_the_electrons_are_fuel_costs_a_third` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| P_fus（415 s，摆平体平均与外加热之后） | relative | 0.13 | measured_band | 实测 +10.6 % + 一档余量。★这个带写的是「给定剖面的 0-D 距集成模拟 H 模解有多远」，不是精度目标 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-08-itpa-tc33/FYDOC-CASE-08-itpa-tc33.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）实测 +10.6 % + 一档余量。★这个带写的是「给定剖面的 0-D 距集成模拟 H 模解有多远」，不是精度目标
- （场景）★★**参考件带台基，0-D 侧没有**：参考的 T_e,ped = 4.84 keV · n_e,ped = 7.69e19，而本仓 0-D 的形状是 `(1-ρ²)^p`。摆平体平均之后剩下的差是**形状**的，而 ⟨σv⟩ 对 T 超线性——所以这个场景上「体平均对齐」不等于「功率对齐」，这是场景的性质，不是某一条记录的容差。
- （场景）★★**燃料稀释要读参考件自己的组分**，不能取「一半电子是燃料」：件里分离面 n_D = n_T = 2.6e19 而 n_e = 5.72e19（即 0.4546）。P_fus ∝ n_D n_T，这 9 % 的密度差在功率上是 19 %。
- （场景）★**非感应电流占比高**：参考解含 4.21 MA 自举 + 1.07 MA NBI + 0.21 MA EC 驱动。任何纯欧姆的环电压模型在这个场景上都不可判——不是精度不够，是问的不是同一个量。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| P_fus，摆平几何 · I_p · Z_eff · 外加热 · 体平均 n_e 与 T_e 之后 | 159.42 MW 对参考 144.15 MW，**+10.6 %**（带 13 %） |  | 成立 | 体平均由 brentq 解峰化，⟨n_e⟩ / ⟨T_e⟩ 逐位对上——摆平是判据的一部分，不是预处理 |
| ★★燃料稀释的缺省是一个假设，不是中性值 | `dtf=0.5` 给 192.88 MW（+33.8 %）；参考件自己的组分 0.4546 给 +10.6 %——**稀释一项吃掉 69 % 的差** |  | 成立 | 参考件分离面 n_D = n_T = 2.6e19 而 n_e = 5.72e19。P_fus ∝ n_D n_T，9 % 的燃料密度差在功率上是 19 %。门里有一条专门钉这件事 |
| 余下的 +10.6 % 是形状 | 本仓 `(1-ρ²)^p` 无台基；参考件 T_e,ped 4.84 keV · n_e,ped 7.69e19 | partly-holds | 部分 | 体平均相同而形状不同，而 ⟨σv⟩ 对 T 超线性。**不靠调峰化去抹平它**——抹平了这就成了曲线拟合而不是比较 |
| ★★`v_loop` 不判 | 参考件 −0.0546 V，含 4.21 MA 自举 + 1.07 MA NBI + 0.21 MA EC 驱动 |  | 部分 | 本仓 0-D 的环电压是纯欧姆、不含非感应电流。拿一个不含自举的模型去对一个自举占 28 % 的解，判出来的数没有意义 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_itpa_tc33.py::test_the_volume_averages_really_are_matched | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_itpa_tc33.py::test_the_fusion_power_lands_within_the_band_on_the_reference_composition | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_itpa_tc33.py::test_assuming_half_the_electrons_are_fuel_costs_a_third | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/data/FYDOC-CASE-08-itpa-tc33/corpus/ | sha256-manifest:b92f9d6fe14b5d72fadab865bf7074e309daa876a837919c723f8eb558d6611d | public | 4 files, 3090111 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_itpa_tc33.py::test_the_volume_averages_really_are_matched python/tests/test_itpa_tc33.py::test_the_fusion_power_lands_within_the_band_on_the_reference_composition python/tests/test_itpa_tc33.py::test_assuming_half_the_electrons_are_fuel_costs_a_third
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（C 确认）的问题，不外推。
