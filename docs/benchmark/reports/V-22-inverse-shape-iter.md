---
title: V-22 · 静态逆问题的第二个形状：ITER 参考分离面上的线圈设计（无参考侧，自洽判据）
---

# V-22 · 静态逆问题的第二个形状：ITER 参考分离面上的线圈设计（无参考侧，自洽判据）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | 无参考侧（自洽判据） · ITER 平衡件不可达：TEQ / TOSCA 为指向未设 $ITER_SCENARIO_ROOT 的指针件；FreeGSNKE 不带 ITER 机器 · n/a |
| **对象** | fylite: code/discharge 经树门（ITER 卡片 12 路线圈；目标为卡片的 fylite:reference_boundary，按 X 点尖角补齐；注入 fydoc METIS 壁作限制器；129² 盒、16 遍、c4 位置控制跟踪 R0） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_design_reproduces_its_recorded_readings`；`python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_designed_separatrix_stays_in_the_band`；`python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_design_does_not_buy_shape_with_current_the_machine_lacks`；`python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_target_curve_is_recorded_with_its_defects` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——4 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：ITER 卡片（EDA 几何的 12 路线圈，无额定）；15 MA、解析剖面族 β₀ 0.6 · emp 2；129² 盒；一张形状、一个时刻；不含参考平衡对拍、不含电流不确定性的显式报告

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 设计出的分离面离目标曲线（全点；ITER 的 trace 不含 X 点腿，无需窗口）：中位 | absolute | 15.5 mm | measured_band |  |
| 同上：p95 · 最大 | absolute | 69.9 mm | measured_band | 最大另带 124.0 mm |
| 六个形状量的归一 RMS（shape_error） | relative | 0.0308 | measured_band |  |
| 峰值通道电流 |I| —— 卡片无供电额定，退火不守限，故以实测设计值为带 | absolute | 30.7 MA | measured_band | 超过它的「更好形状」是另一台机器的设计，不是更好的设计 |

## 2. 口径与说明

- ★★2026-09-15 /goal「… 前向后向」第二个形状：B-21 立在 EAST 一张形状上，评估 note 缺口 6 要求补第二个形状
- ★V 类而非 B 类：这张形状没有任何可达的参考平衡，判的是设计自身的闭合（要多少电流 · 解出什么分离面 · 离所要的曲线多远）与它需要的设置
- ★电流带是缺额定的替身：卡片无 pf_active/supply，门里没有任何东西拦住退火；没有这条带，形状分可以用不存在的电流买
- ★不需要 B-21 那种公平窗口：`surfaces::trace` 追出的分离面本就不含 X 点腿，三种窗口读数逐位相同
- 纳入类别（参考数据）：public

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| ITER 参考分离面上的设计 | 分离面离目标 中位 15.4 mm · p95 69.8 · 最大 123.2（门的 rms 24.4 mm）· shape_error 0.0307 · 39 s · 内部自由边界解 settled（残差 9.7e-04） | 成立 |  |
| 实现的形状量对目标 | R0 6.2259（目标 6.2209）· a 1.9734（1.9819）· z0 0.3633（0.366）· δ上 0.3665（0.3456）· κ 1.7941（1.8492）· δ下 0.4878（0.5432） | 成立 | κ 低约 3 %、δ下低约 0.055：在保持解收敛与电流不失真的前提下调不上去（见下条），是解析剖面族在这张形状上的表达力边界 |
| 设置是这条记录的真内容（实测逼出） | 盒子 65² → 129²：间隙 rms 157 → 63 mm；退火遍数 8 → 16 在 65² 上有效、129² 上已饱和；c4 位置控制**必须**让设定点跟踪 R0（`pc_track_r0 = 1`）——固定在目标面积质心时边界被 Shafranov 位移拉偏（rms 180 mm）；边界格分数规则在此无效（与基线逐位同），与 EAST 相反 | 成立 | `emp = 2` 是最后一个仍**收敛**的设置：emp 3 的 shape_error 略好（0.0269）却 600 轮不收敛（残差 0.019）；`enp = 0.5` 给出全场最好的 κ 1.834，代价是 37.5 MA·t 的电流且始终不收敛——形状分是用不存在的电流换的 |
| 目标曲线与卡片的缺陷（读数） | 参考分离面是数字化 METIS 曲线：248 个有限点、相邻中位 67 mm，且在 X 点处**开口 323 mm**（本条按尖角 [5.15, -3.4] 补齐）；卡片的两条限制器轮廓都不是真空室内区域（First Wall 止于 Z = −3.069，比目标最低点高 230 mm；Divertor 不含主等离子体），本条注入 fydoc 的 METIS 壁（57 点闭合）作限制器；pf_active 无供电额定，退火不守限（实测峰值 30.6 MA·t） | 未判（读数） | ITER-FEAT 2000 那份 dev:currentMax 属另一套线圈（与 base 的 12 圈全不同），不可挪用作额定 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 4 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 |  |

## 4. 不可比的部分

- 没有参考侧：这张形状上没有任何可达的平衡件（TEQ / TOSCA 是指针，FreeGSNKE 无 ITER 机器），本条不是对拍。
- 目标曲线是数字化件：248 点、相邻中位 67 mm、X 点处开口 322 mm（本条按尖角补齐）；它不是某个代码解出的平衡。
- 卡片无供电额定，退火不守限；电流带只是实测设计值的替身，不是机器的能力。
- κ 与 δ下 在保持收敛与电流不失真的前提下调不上去——解析剖面族的表达力边界，不是设计误差。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| docs/benchmark/readings/inverse_shape_iter.json | — | public |
| dist/facts/device/iter.jsonld | — | public |
| fydoc facts/device/iter/abox/providers/wall/metis.jsonld | — | public |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYLITE_DEVICE_DIR=dist/facts/device/iter FYLITE_KERNEL_LIB=<当前内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_inverse_shape_iter.py
# 读数重写：FYLITE_DEVICE_DIR=dist/facts/device/iter python tools/benchmark-equilibrium.py inverse-shape-iter --out docs/benchmark/readings
```

## 6. 结论

成立（自洽）：ITER 参考分离面上，code/discharge 交出的设计把分离面放在离目标中位 15.4 mm（p95 69.8、最大 123.2）处，shape_error 0.0307，R0 · a · z0 · δ上 都贴目标；κ 与 δ下 差约 3 % 与 0.055，是解析剖面族的表达力边界。这条记录的真内容是设置：129² 盒、16 遍、c4 设定点跟踪 R0、目标按 X 点尖角补齐、注入 METIS 壁作限制器、emp = 2（最后一个仍收敛的设置）。
