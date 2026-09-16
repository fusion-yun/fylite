---
title: B-14 · 自由边界正问题对 KEFIT：同一组线圈电流与 p′/FF′ 下的 GS 解
---

# B-14 · 自由边界正问题对 KEFIT：同一组线圈电流与 p′/FF′ 下的 GS 解

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/forward（剖面表分支）经树门；EAST 卡片 65×65 盒，与 KEFIT green2022_pcs 表同一网格 |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_equilibrium.py::test_b14_the_forward_solve_reproduces_its_recorded_readings`；`python/tests/test_benchmark_equilibrium.py::test_b14_the_forward_solve_stays_in_the_band_on_kefits_magnetics_answers`；`python/tests/test_benchmark_equilibrium.py::test_b14_the_point_profile_slice_is_recorded_outside_the_band` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST 几何（east_new 卡片 / green2022_pcs，65×65 盒）；KEFIT 在 #137985 原始树输入上的纯磁答案；带 POINT 约束的剖面不在带内

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 磁轴距离（三片纯磁） | absolute | 4.87 mm | measured_band |  |
| 极向通量跨度 |ψ_b − ψ_a| 的相对差 | relative | 0.00264 | measured_band |  |
| KEFIT 边界内 ψ_N 差 rms / 最大 | absolute | 0.00737 | measured_band | 最大值另带 0.0181 |
| KEFIT 边界点到 fylite ψ_N = 1 等值线的距离：中位 / 最大 | absolute | 3.43 mm | measured_band | 最大值另带 15.5 mm |
| 下 X 点距离 | absolute | 6.51 mm | measured_band |  |
| Ip（两边都是等式约束） |  | — | machine_precision | ★这是嵌在对拍记录里的一句 **verification** 断言：两个代码都以 Ip 为等式，判的是一条恒等式，不含可被物理带覆盖的建模差 |

## 2. 口径与说明

- ★★取代计划中的 libefit 对标（用户裁定 2026-09-15：废弃 libefit，直接对标 KEFIT）
- ★同一组输入：KEFIT 拟合出的 12 路线圈安匝、它的 p′(ψ_N) 与 FF′(ψ_N)、它的 Ip；两边剩下的只有 GS 求解（网格、边界搜索、自由边界迭代）
- ★口径：KEFIT 的 ψ 每弧度、轴处取极小；fylite 整圈、轴处取极大——ψ_fy = −2π ψ_KEFIT，p′ 与 FF′ 同除 −2π（由 g-file 的 simag < sibry 读出，不假设）
- 纳入类别（参考数据）：experiment、private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| 4.041 s 纯磁答案 | 磁轴 4.11 mm · 跨度 -0.021 % · ψ_N rms 0.74 % / 最大 1.80 % · 边界 3.42 / 12.7 mm · X 点 4.3 mm | 成立 |  |
| 4.944 s 纯磁答案 | 磁轴 4.02 mm · 跨度 -0.264 % · ψ_N rms 0.65 % / 最大 1.57 % · 边界 2.67 / 15.4 mm · X 点 6.0 mm | 成立 |  |
| 5.976 s 纯磁答案 | 磁轴 4.87 mm · 跨度 -0.181 % · ψ_N rms 0.66 % / 最大 1.52 % · 边界 2.74 / 13.8 mm · X 点 6.5 mm | 成立 |  |
| 5.976 s 带 POINT 约束的剖面：出带 | 磁轴 9.2 mm · 跨度 -2.05 % · ψ_N rms 2.21 % · 边界 5.5 / 83 mm · 600 步未定 | 未判（读数） | 不进带；门把「出带」本身钉住，免得它悄悄变好或变坏 |
| 收敛：fylite 的自由边界迭代在纯磁三例上「settled」而非「converged」 | 残差 2.9e-03 / 3.7e-03 / 1.3e-03，约 62 步因掩膜稳定而停；缺省 tol 1e-9 | 未判（读数） | 带是在这一停止状态上量的；收紧停止判据是否移动这些数未测 [TBD] |
| 复测 2026-09-15（本条写入时把门跑一遍） | 3 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-14` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-14` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-14` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-14` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-14` 列进 `--only` 并在 `--reruns` 里给出本次实测。 |

## 4. 不可比的部分

- 网格同为 65×65（R 1.2–2.8 m，Z ±1.4 m），但边界搜索、限制器轮廓与自由边界迭代的停止判据各是各的：fylite 用卡片的 base 限制器，KEFIT 用 GUI_v5 的 60 点限制器。
- fylite 的剖面表分支按 Ip 归一，表的整体规格（每弧度 / 整圈）会被除掉；p′ 与 FF′ 的相对大小与符号保留。
- q 不在比较里：剖面表分支不输出 q。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/forward_kefit_east137985.json | sha256:a54852d884c396b77b050f387334a8bae29a942965b3d5750b32e2bb23e31f1c | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_equilibrium.py -k b14
# 读数重写：python tools/benchmark-equilibrium.py forward-kefit --out <dir>
```

## 6. 结论

成立：拿 KEFIT 自己在 #137985 原始树输入上收敛的线圈电流与剖面，fylite 的自由边界正问题在三片纯磁答案上把磁轴放在 4.9 mm 内、边界中位 3.4 mm 内、ψ_N rms 0.74 % 内；带 POINT 约束的剖面出带（记为发现）。
