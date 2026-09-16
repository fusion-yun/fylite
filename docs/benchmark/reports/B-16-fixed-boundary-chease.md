---
title: B-16 · 定边界平衡对 CHEASE：EAST #137985 4.041 s，KEFIT 纯磁答案的 ψ_N = 0.995 面与其 p′ / FF′
---

# B-16 · 定边界平衡对 CHEASE：EAST #137985 4.041 s，KEFIT 纯磁答案的 ψ_N = 0.995 面与其 p′ / FF′

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | CHEASE · third_party/chease 本机 gfortran 构建；EXPEQ 输入（NSURF = 6 · NPPFUN = NFUNC = 4 · NSTTP = 1 · NCSCAL = 2），NS = NT = 80（另 40 作分辨率读数） · public；KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/fixed_boundary 经树门（129² 判带，65² 作分辨率读数） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_fixed_boundary.py::test_b16_fylite_reproduces_its_readings_and_stays_in_the_band_against_chease`；`python/tests/test_benchmark_fixed_boundary.py::test_b16_kefit_context_is_a_reading` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 4.041 s 纯磁答案的 ψ_N = 0.995 面；fylite 129² 对 CHEASE NS = NT = 80；剖面为 KEFIT 的 KPPCUR / KFFCUR 多项式经 65 点表线性插值

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| ψ_N 差 rms / 最大（该面内 121×201 点阵），fylite 129² 对 CHEASE NS 80 | absolute | 4.92e-05 | measured_band | 最大值另带 0.000266 |
| 磁轴距离 | absolute | 0.00468 mm | measured_band |  |
| 通量跨度 · Ip | relative | 0.000754 | measured_band | Ip 另带 0.000968（CHEASE 按面内安培电流归一，fylite 不缩放） |
| q 相对差（ψ_N 0.1–0.9 九点）rms / 最大 · q₉₅ | relative | 0.00105 | measured_band | 最大值另带 0.00183 · q₉₅ 另带 0.00186 |

## 2. 口径与说明

- ★同一问题交给两个定边界代码：该面（KEFIT 图的双三次样条上自轴 360 条射线取首个穿越）、101 点 p′ / FF′（÷ −2π 换口径）、边缘 F = FPOL(0.995)；CHEASE 另需面内电流（KEFIT 图上的安培环路）作归一
- ★口径（在 Solov'ev 算例上实测，不假设）：fylite 取整圈 Wb 的 p′ / FF′、轴处取极大；CHEASE 的 EXPEQ 取 −μ0 R0² / B0 · 2π p′ 与 −2π FF′ / B0，横轴 √ψ_N，轮廓以 R0EXP 为单位，边缘 T = 1（B0EXP = F_edge / R0EXP），CURRT = μ0 Ip / (R0EXP B0EXP)；符号取反则 CHEASE 不收敛
- ★该面光滑、不过 X 点：定边界代码的问题不含分界面；分界面上的比较在 B-14（自由边界）
- 纳入类别（参考数据）：experiment、private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| fylite 129² 对 CHEASE NS 80 | ψ_N rms 4.92e-05 / 最大 2.65e-04 · 磁轴 0.005 mm · 跨度 -0.075 % · Ip -0.097 % · q rms 0.10 % / 最大 0.18 % · q₉₅ +0.19 % | 成立 |  |
| 分辨率（读数） | fylite 65² 对 CHEASE：ψ_N rms 7.19e-05 / 最大 2.49e-04 · 磁轴 0.004 mm · 跨度 -0.037 % · Ip -0.112 % · q rms 0.16 % / 最大 0.36 % · q₉₅ +0.18 %；CHEASE NS 40 对 NS 80：ψ_N rms 1.0e-04 · q rms 0.002 % | 未判（读数） |  |
| KEFIT 自由边界图作背景（读数） | fylite 129²：ψ_N rms 2.10e-03 · 磁轴 2.31 mm；CHEASE NS 80：ψ_N rms 2.09e-03 · 磁轴 2.31 mm | 未判（读数） | 两个定边界代码到 KEFIT 图的差相同：那是 KEFIT 65² 网格与该面在其图上的重构，不是任一求解器的；对 KEFIT 的 Ip 不可比：KEFIT 记全电流，这里解的是 0.995 面内的电流 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 2 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-16` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-16` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-16` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-16` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-16` 列进 `--only` 并在 `--reruns` 里给出本次实测。 |

## 4. 不可比的部分

- 该面光滑、不过 X 点：分界面上的比较在 B-14（自由边界）；两个定边界代码都不回答分界面问题。
- 对 KEFIT 自由边界图的读数不作判：KEFIT 65² 网格与该面在其图上的重构使两个定边界代码离它一样远；KEFIT 的 Ip 是全电流，与面内电流不可比。
- CHEASE 按面内安培电流归一（NCSCAL = 2），fylite 按剖面表原样解；两边 Ip 的 −0.1 % 即此。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/fixed_boundary_east137985.json | sha256:1c1dca4624223e6d4064f742cfd2763c27a331b20b3d5ba57bbac0b702640b2d | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/chease/chease_fixed_boundary_east137985.tar.gz | sha256:f8088bd7bd1d6b58e993cadf5df4adabf8d223324dbdae847d83c61d176ac200 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_KERNEL_LIB=<带 code/fixed_boundary 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_fixed_boundary.py -k b16
# 读数与 CHEASE 运行件重写：CHEASE_EXE=<chease> python tools/benchmark-fixed-boundary.py east --out <dir>
```

## 6. 结论

成立：EAST 形状上同一定边界问题，fylite 129² 与 CHEASE NS 80 的 ψ_N 差 rms 4.9e-5、磁轴 5 µm、q（ψ_N 0.1–0.9）0.10 %；两者离 KEFIT 自由边界图一样远（2.3 mm），那是参考图的离散，不是求解器的。
