---
title: B-21 · 静态逆问题：同一目标形状下 fylite 的线圈设计对 FreeGSNKE 的反演解
---

# B-21 · 静态逆问题：同一目标形状下 fylite 的线圈设计对 FreeGSNKE 的反演解

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | FreeGSNKE · third_party/freegsnke-main + PyPI freegs4e 0.13.1（归档回放，未重跑）：Inverse_optimizer，24 点 isoflux + 两个 null point，牛顿 · LGPL-3；KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/discharge 经树门（目标曲线 + 两个零点，退火 ridge 8 遍，卡片供电上限，每遍一次自由边界解） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_inverse_shape.py::test_the_readings_are_the_registered_ones`；`python/tests/test_benchmark_inverse_shape.py::test_b21_the_design_reproduces_its_recorded_readings`；`python/tests/test_benchmark_inverse_shape.py::test_b21_the_designed_boundary_stays_in_the_band`；`python/tests/test_benchmark_inverse_shape.py::test_b21_the_currents_differ_far_more_than_the_equilibria`；`python/tests/test_benchmark_inverse_shape.py::test_b21_the_target_curve_limits_are_recorded` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——5 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 4.041 s 一张形状；12 路 PF、卡片供电上限；交付 p′/FF′ 表、Ip 392708.734 A；65² 网格；不含 ITER 形状、不含电流不确定性的显式报告

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| fylite 设计的实现边界离目标曲线（公平窗口：距 X 点 > 0.1 m、目标 Z 覆盖区间内缩 20 mm）：中位 | absolute | 1.22 mm | measured_band |  |
| 同上：p95 · 最大 | absolute | 3.88 mm | measured_band | 最大另带 9.43 mm |
| 零空间读数：三组电流各自正解后在 KEFIT 图上 ψ_N rms 的散布 · 磁轴散布 | absolute | 0.005 | measured_band | 磁轴散布另带 3.0 mm；判的是「三组差很大的电流给出同一张平衡」 |
| fylite 设计电流正解后的 ψ_N rms（对 KEFIT 图） | absolute | 0.00462 | measured_band |  |

## 2. 口径与说明

- ★★2026-09-15 /goal「完善磁平衡相关计算功能 … 前向后向」：静态逆问题此前没有判定记录（评估 note 缺口 6）
- ★两边的目标函数不同，这是差异的来源而不是缺陷：fylite 最小化六个形状量与边界间隙的带 ridge 正则目标并守线圈上限，FreeGSNKE 解 isoflux + null 的约束牛顿问题
- ★判的是**形状**：电流在逆问题里只被约束到零空间（见结果），电流差不作判据
- ★公平窗口的理由在结果里：目标曲线是 KEFIT 自己的 69 点轮廓，粗（中位 48.5 mm）且上方缺一段
- 纳入类别（参考数据）：experiment、private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| fylite 设计（code/discharge，退火 8 遍） | 实现边界离目标 中位 1.21 mm · p95 3.87 · 最大 9.42（公平窗口 2025 / 2172 点）· 2.0 s · 未触线圈上限 · 内部自由边界解 settled（残差 1.7e-03） | 成立 |  |
| FreeGSNKE 反演（同一目标与零点，归档回放） | 实现边界离目标 中位 5.00 mm · p95 27.38 · 最大 52.89（2074 / 2460 点） | 成立 |  |
| 零空间：电流差远大于平衡差 | 两边设计电流差 25.6 kA·t rms（单通道最大 61.6）；三组电流正解后 ψ_N rms：KEFIT 0.0074 · FreeGSNKE 0.0095 · fylite 0.0046，磁轴 ΔR 1.45 至 4.02 mm | 成立 | 「谁的电流更像 KEFIT」不能读成「谁的设计更对」：KEFIT 的电流是它自己拟合出来的，不是真值；离 KEFIT 电流：fylite 25.6 kA·t rms、FreeGSNKE 0.37 |
| 目标曲线本身的限制（读数） | KEFIT 轮廓 69 点、相邻点中位 48.9 mm，Z 只到 +0.658（其上 X 点在 +0.767，差 134 mm）；不设窗口时 FreeGSNKE 最大距离读作 79.5 mm，多数来自「目标没有那一段」 | 未判（读数） | 两种读法都存在读数件里（boundary_vs_target · boundary_vs_target_all_points） |
| 复测 2026-09-15（本条写入时把门跑一遍） | 5 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 |  |

## 4. 不可比的部分

- 两个代码解的不是同一个优化问题：目标函数、正则化与约束都不同；本条比的是**同一目标下各自交出的形状**，不是优化器。
- 电流不可比作判据：逆问题在电流空间欠定（实测两组差 25.6 kA·t、正解出的平衡只差毫米级）；KEFIT 的电流也只是它自己的拟合结果。
- 目标曲线是 KEFIT 的 69 点轮廓：粗（相邻点中位 48.5 mm）、上方止于 Z = +0.658（其上 X 点 +0.767）；公平窗口即为此设，两种读法都在读数件里。
- 一装置一形状一时刻；fylite 侧内部的自由边界解停在 settled（与 B-14 同一底）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/inverse_shape_east137985.json | sha256:81dacc7ebe0d070a2881816fbec6ea9b8a066c1e240d13b5c8484b18c70c2333 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/freegsnke/freegsnke_vstab_east137985.tar.gz | sha256:df6725b4bfe4ad664620c4503dfb4d8aea5b951b36b772a8fc1902f3cfbc6c81 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<当前内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_inverse_shape.py
# 读数重写：python tools/benchmark-equilibrium.py inverse-shape --out <dir>
```

## 6. 结论

成立：同一目标（KEFIT 边界 + 其两个 X 点）下，fylite code/discharge 交出的形状比 FreeGSNKE 反演更贴目标（公平窗口中位 1.21 mm 对 5.00 mm），其电流正解后在 KEFIT 图上的 ψ_N rms 0.0046 也最小；同时读出逆问题的零空间——两边电流差 25.6 kA·t，而三组电流给出的平衡只差毫米级。
