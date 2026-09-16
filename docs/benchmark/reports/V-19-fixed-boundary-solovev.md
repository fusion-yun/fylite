---
title: V-19 · 定边界 GS：给定轮廓上的 Solov'ev 精确解（fylite code/fixed_boundary 与 CHEASE）
---

# V-19 · 定边界 GS：给定轮廓上的 Solov'ev 精确解（fylite code/fixed_boundary 与 CHEASE）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | Solov'ev 解析解 · ψ = ψ_c − e₁(R² − r₀²)² − e₂R²Z² − e₃Z²（r₀ 1.8 m · e₁ 1.0 · e₂ 1.075441 · e₃ 1.0 · κ 1.7 · 外缘 2.25 m），常数 p′ 与 FF′；Ip 由精确轮廓上的安培定律，q₀ 由轴处局部展开 · public；CHEASE · third_party/chease 本机 gfortran 构建；EXPEQ 输入（NSURF = 6 · NPPFUN = NFUNC = 4 · NSTTP = 1 · NCSCAL = 2），NS = NT = 80（另 40 作分辨率读数） · public |
| **对象** | fylite: code/fixed_boundary 经树门（内核 fixedbnd：轮廓外 64 根细丝的基本解法在 256 个配点上把 ψ = 0 钉在轮廓上；等离子体自身磁通由盒边自由空间格林函数给出；被轮廓切开的网格按面积分数计源） |
| **数据** | 见 §5 表（0 项） |
| **门** | `python/tests/test_benchmark_fixed_boundary.py::test_v19_fylite_recovers_the_solovev_map_inside_its_contour`；`python/tests/test_benchmark_fixed_boundary.py::test_v19_chease_on_the_same_contour`；`$FYLITE_KERNEL/rust/fylite/src/fixedbnd.rs::tests · case.rs::fixed_boundary_tests` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：定边界、光滑轮廓（无 X 点）、常数 p′ / FF′；fylite 网格 33² / 65² / 129²，CHEASE NS = NT = 40 / 80

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| fylite 129²：ψ_N 差 rms / 最大（轮廓内 121×201 点阵），对精确解 | absolute | 1.09e-05 | measured_band | 最大值另带 0.000106 |
| fylite 节点误差 max|Δψ| / ψ_c（整格在轮廓内的节点）与二阶收敛 | relative | 5.52e-05 | measured_band | 65² → 129² 的误差比须大于 3.0 |
| fylite 129²：Ip 对精确轮廓上的安培定律 · 通量跨度 | relative | 1.72e-05 | measured_band | 跨度另带 2.46e-06 |
| fylite 129²：磁轴距离 · 轮廓离 ψ = 0 面的最大距离 | absolute | 0.0261 mm | measured_band | 轮廓距离另带 4.13e-05 m |
| fylite 129²：q₀ 对局部展开闭式 | relative | 0.00327 | measured_band | q₀ 是最内一对被追踪面外推到轴（`q_profile` 的约定），不是轴上的值 |
| CHEASE NS 80：ψ_N rms · 磁轴 · 跨度 · Ip · q₀，对精确解 | absolute | 3.91e-06 | measured_band | 带 {"psin_rms": 3.91e-06, "psin_max": 5.86e-05, "axis_mm": 1.75e-06, "span_rel": 1.99e-08, "ip_rel": 9.36e-10, "q0_rel": 3.56e-06}；第二个代码在同一问题上，不是 fylite 的参考 |

## 2. 口径与说明

- ★★2026-09-15 用户「补全 fixed-boundary 情景」：此前没有任何门能让 fylite 在给定边界上求解（B-10 读的是 CHEASE 输出上的残差，已并入 V-16）；内核当日新增 code/fixed_boundary
- ★口径（在 Solov'ev 算例上实测，不假设）：fylite 取整圈 Wb 的 p′ / FF′、轴处取极大；CHEASE 的 EXPEQ 取 −μ0 R0² / B0 · 2π p′ 与 −2π FF′ / B0，横轴 √ψ_N，轮廓以 R0EXP 为单位，边缘 T = 1（B0EXP = F_edge / R0EXP），CURRT = μ0 Ip / (R0EXP B0EXP)；符号取反则 CHEASE 不收敛
- ★精确解在两个代码里都可精确表示（常数源），剩下的差是离散误差；边缘电流不为零（p′ 常数），被轮廓切开的网格正是被考的地方
- 纳入类别：无外部数据（解析 / 自带）

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| fylite 129² 对精确解 | ψ_N rms 1.08e-05 · 最大 1.06e-04 · 磁轴 0.026 mm · 跨度 -2.46e-06 · Ip +1.72e-05 · q₀ -0.33 % · 轮廓距离最大 4.1e-05 m · 31 步收敛 | 成立 |  |
| 收敛阶 | 节点误差 33² 1.45e-03 · 65² 4.58e-04 · 129² 5.51e-05（比 3.2 · 8.3） | 成立 |  |
| CHEASE NS 80 对精确解 | ψ_N rms 3.91e-06 · 最大 5.86e-05 · 跨度 -2.0e-08 · Ip +9.4e-10 · q₀ +3.6e-06 | 成立 |  |
| fylite 129² 对 CHEASE NS 80（读数） | ψ_N rms 1.12e-05 · q（ψ_N 0.1–0.9）rms 0.023 % · 最大 0.056 % · q₉₅ -0.004 % | 未判（读数） | 两个代码都对着精确解判过，彼此的差只作读数 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 2 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；CHEASE 本机构建在场（缺则第二条按名 skip）；内核 cargo 单元测试 7 passed（fixedbnd · fixed_boundary_tests） |

## 4. 不可比的部分

- 光滑轮廓、常数源：不含 X 点边界、剖面表插值与测量拟合；EAST 形状上的同一问题在 B-16。
- q₀ 两边约定不同：fylite 取最内一对被追踪面外推到轴，CHEASE 取其 ψ 网格的轴值；q 剖面的比较取 ψ_N 0.1–0.9。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
CHEASE_EXE=<本机构建的 chease> FYLITE_KERNEL_LIB=<带 code/fixed_boundary 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_fixed_boundary.py -k v19
# 读数重写：python tools/benchmark-fixed-boundary.py solovev --out <dir>
cd $FYLITE_KERNEL && cargo test --release --lib -- fixedbnd fixed_boundary_tests   # 私仓单元测试
```

## 6. 结论

成立：给定轮廓上 fylite 的定边界求解在 129² 上把 Solov'ev 精确解重现到 ψ_N rms 1.1e-5、Ip 1.7e-5、磁轴 0.026 mm，误差按二阶下降；CHEASE 在同一轮廓上到 ψ_N rms 3.9e-6。
