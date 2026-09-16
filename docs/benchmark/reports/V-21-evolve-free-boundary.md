---
title: V-21 · 自由边界演化与 PF 电路 · 无源件耦合：EAST 卡片上的恒等式（code/evolve_free_boundary）
---

# V-21 · 自由边界演化与 PF 电路 · 无源件耦合：EAST 卡片上的恒等式（code/evolve_free_boundary）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | 解析恒等式 · 隐式 Euler 的衰减因子 · 理想导体磁链守恒 · 同一方程的两种驱动（无第二个代码） · public；KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/evolve_free_boundary 经树门（隐式 Euler；电压 / 电流驱动；三组无源件 90 元；解内耦合 · 边界格分数规则 · 起点带虚拟对）；另 code/forward 的 opt-in edge_fraction |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_evolve_free_boundary.py::test_the_readings_are_the_registered_ones`；`python/tests/test_benchmark_evolve_free_boundary.py::test_v21_a_shell_mode_decays_on_the_wall_time`；`python/tests/test_benchmark_evolve_free_boundary.py::test_v21_a_perfect_conductor_keeps_its_flux_while_the_plasma_ramps`；`python/tests/test_benchmark_evolve_free_boundary.py::test_v21_current_drive_reproduces_the_voltage_march`；`python/tests/test_benchmark_evolve_free_boundary.py::test_v21_the_forward_edge_rule_is_a_reading_not_a_band` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——5 passed, 0 failed, 0 error, 0 skipped, 0 stale（同一次运行另三份平衡门 18 过） |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 卡片（12 路 PF · 内壳 · 外壳 · 被动板 90 元）；KEFIT t4041_mag 的剖面与线圈电流；Ip 三步升 2 %、2 ms 一步；65² 网格；不含 Ip 电路方程、反馈控制与竖直位移增长率

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 无等离子体、通道冻结：无源件从 code/wall 的最慢模出发，逐步对隐式 Euler 衰减因子 (1 + dt/τ₁)^−k 的最大相对偏差 | relative | 1e-12 | machine_precision |  |
| 理想导体（电阻 0、电压 0）、Ip 三步升 2 %：每个导体的磁链 M I + ψ_p 的最大漂移 / 等离子体磁通的最大变化 | relative | 1e-10 | machine_precision |  |
| 回路方程在返回状态上的相对残差（解内耦合；自由边界解到 tol 1e-9） | relative | 1e-09 | machine_precision | 容差取自由边界解自己的停止判据：回路方程与平衡在同一轮里闭合 |
| 电流驱动（给电压驱动算出的通道电流）复现电压驱动的无源件电流：最大差 / 最大无源件电流 | relative | 4.51e-09 | measured_band |  |

## 2. 口径与说明

- ★★2026-09-15 /goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」：内核新门 code/evolve_free_boundary；此前唯一的电路 + 平衡演化是测试树里不带反作用的 EFIT 回放
- ★V 类：判的是方程与实现自洽（恒等式到舍入），不是墙电流与位移响应的物理对错——无第二个代码；Ip 是给定轨迹
- ★步长须 γ·dt < 1（竖直不稳定模）：只取内壳（刚性 γ ≈ 709 s⁻¹，B-18）时 2 ms 一步即离开平衡、电流驱动重跑落到镜像支；本条取三组无源件（γ ≈ 4 s⁻¹）
- ★同日内核三处实测改法：边界格分数规则（节点规则的量化抖动与一步的磁通增量同量级）· 解内耦合（整解外套 Picard 等于没有墙）· 解内耦合时虚拟位置对缺省关、起点仍开
- 纳入类别（参考数据）：experiment

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| 壳模衰减（无等离子体） | τ₁ 413.48 ms（90 元），dt = τ₁/10，5 步：最大相对偏差 8.4e-15 | 成立 |  |
| 理想导体的磁链 | 磁链漂移 6.7e-15 Wb 对等离子体磁通变化 3.076e-02 Wb（2.2e-13）· 回路方程残差 2.2e-13 · 每步自由边界解 converged、虚拟对 0 · 无源件电流升到 649 A · 磁轴 Z 7.88 → 7.54 mm | 成立 |  |
| 电流驱动复现电压驱动 | 电压 = 1.05 R I₀（保持 KEFIT 线圈电流并多给 5 %），通道电流最大变 0.118 % · 无源件电流最大 718 A，两种驱动差 4.5e-09 | 成立 |  |
| code/forward 两种边界规则（B-14 三片纯磁答案；读数） | 节点规则 settled、虚拟对 10.5 至 14.2 kA；边界格分数规则 converged（5378 至 5876 轮、对 ≤ 36 A）· 磁轴 Z 离 KEFIT 8.8 至 10.8 mm（节点 -4.9 至 -2.7 mm）· ψ_N rms 1.83 至 2.36 %（节点 0.65 至 0.74 %） | 未判（读数） | B-14 的读数是虚拟位置对撑着的平衡；B-14 的带不动。哪一种离实物近，KEFIT 回答不了（它的竖直位置由拟合给出）；带 POINT 约束剖面的 t5976_primary 两种规则都不收敛 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 5 passed, 0 failed, 0 error, 0 skipped, 0 stale（同一次运行另三份平衡门 18 过） | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-21` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-21` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-21` 列进 `--only` 并在 `--reruns` 里给出本次实测。 |

## 4. 不可比的部分

- 没有第二个代码：墙电流的大小、位移与形状的响应只由恒等式约束，物理对错要对 FreeGSNKE 的非线性演化（评估 note §4 第 7 条）。
- Ip 是给定轨迹，不解等离子体自身的电路方程；不含反馈控制、电源模型与快控线圈。
- 步长受竖直不稳定模限制（γ·dt < 1）：只取内壳时 2 ms 一步没有邻近解；本条取三组无源件。
- code/forward 两种边界规则的差（约 9–11 mm）只作读数：KEFIT 的竖直位置由拟合给出，回答不了哪一种离实物近。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/evolve_free_boundary_east137985.json | sha256:3ed068ab61d9d59ec67ad727513015301f471fa440e8be9656d5584e4d44fe1a | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/evolve_free_boundary 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_evolve_free_boundary.py
# 读数重写：python tools/benchmark-evolve-free-boundary.py readings --out <dir>
cd $FYLITE_KERNEL && cargo test --release --lib -- evolve_free_boundary_tests the_edge_rule   # 私仓单元测试
```

## 6. 结论

成立：EAST 卡片与 KEFIT 平衡上，code/evolve_free_boundary 让三组无源件的壳模按 code/wall 的 τ₁ 衰减到 8e-15，理想导体在 Ip 升 2 % 时磁链守恒到 2e-13，回路方程在每步平衡上闭合到 2e-13，电流驱动复现电压驱动的无源件电流到 5e-9；同时读出 B-14 的节点规则答案是虚拟位置对撑着的。
