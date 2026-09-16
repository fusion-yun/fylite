---
title: B-18 · 垂直不稳定性：EAST #137985 4.041 s 的刚性增长率与裕度对 FreeGSNKE
---

# B-18 · 垂直不稳定性：EAST #137985 4.041 s 的刚性增长率与裕度对 FreeGSNKE

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | FreeGSNKE · third_party/freegsnke-main + freegs4e 0.13.1（PyPI）· numpy 1.26.4；本地运行，同一张 EAST 卡片（efund 读法的多边形无源件 · 12 路 PF） · public；KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/vstab 经树门（circuit: passive，主动线圈冻结；coarsen 1、每元 8×8 细丝；质量为零的刚性等离子体、恒 Ip） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_wall_vstab.py::test_the_freegsnke_run_is_the_registered_one`；`python/tests/test_benchmark_wall_vstab.py::test_b18_the_rigid_dispersion_reproduces_and_stays_in_the_band_against_freegsnke`；`python/tests/test_benchmark_wall_vstab.py::test_b18_the_deformable_growth_rate_is_a_reading_not_a_band` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 4.041 s（FreeGSNKE 反演平衡）；无源组内壳 / 三组合；主动线圈冻结；刚性、质量为零；不含可变形等离子体（读数）与反馈控制

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 增长率 γ 相对差（fylite code/vstab 对 FreeGSNKE 刚性色散，同一平衡；内壳 · 三组合） | relative | 0.00115 | measured_band |  |
| 主动线圈失稳刚度 k 相对差 | relative | 0.003 | measured_band |  |
| 理想刚度 k_ideal（被动稳定力）相对差 | relative | 0.00114 | measured_band |  |
| 稳定裕度 k_ideal / k − 1 绝对差 | absolute | 0.00495 | measured_band | 与 FreeGSNKE 的感性稳定裕度同定义（刚性等离子体下代数核过） |

## 2. 口径与说明

- ★★取代 C-03（TokSys rzrig 锚点，门自 2026-09-14 起 skip、参考侧无指针）：可复跑的垂直稳定性对拍
- ★★内核缺陷随本条修正（2026-09-15）：EFIT 平行四边形原被读成「倾斜边长 h」，efund 是剪切（w · h 为水平 / 竖直外延）——EAST 壳段间留缝 7.6 / 9.2 mm、外壳 14 行塌成零面积线；修正移动 γ(三组) −1.1 %、τ₁ −0.6 %。修正前 FreeGSNKE 须用 efund 读法建多边形才可比；本条的读数是修正后的
- ★同一张平衡：FreeGSNKE 反演收敛态（κ 1.681 对 KEFIT 1.624，边界对 KEFIT 中位 5.4 mm）；前向解以 KEFIT 电流在 65² · 129² 网格都停滞于残差 1.7e-4
- ★刚性模型的输入（M · R · 耦合梯度 g · 刚度 k）逐项两边一致到 1 % 内；本条判的是同一组输入下的色散根
- 纳入类别（参考数据）：experiment、private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| inner_shell：刚性色散 | γ fylite 708.7 · FreeGSNKE 708.7 s⁻¹（-0.01 %）· k +0.30 % · k_ideal +0.113 % · 裕度 0.269 / 0.271 | 成立 |  |
| inner_shell：FreeGSNKE 可变形等离子体（读数） | γ 652.3 s⁻¹（刚性的 0.92 倍）· 裕度 0.322；fylite 在 KEFIT 平衡上 γ 678.2 s⁻¹ | 未判（读数） | 可变形响应是 fylite 刚性模型没有的物理；FreeGSNKE 雅可比的线性度（步长）未独立核，倍数只作读数 |
| all：刚性色散 | γ fylite 4.267 · FreeGSNKE 4.262 s⁻¹（+0.11 %）· k +0.30 % · k_ideal +0.075 % · 裕度 1.208 / 1.213 | 成立 |  |
| all：FreeGSNKE 可变形等离子体（读数） | γ 9.227 s⁻¹（刚性的 2.17 倍）· 裕度 0.930；fylite 在 KEFIT 平衡上 γ 4.171 s⁻¹ | 未判（读数） | 可变形响应是 fylite 刚性模型没有的物理；FreeGSNKE 雅可比的线性度（步长）未独立核，倍数只作读数 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 3 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；2026-09-15 内核改正 a1 ≠ 0 读法后重录读数与带 |

## 4. 不可比的部分

- 可变形等离子体：FreeGSNKE 的线性化雅可比给出三组合 γ 为刚性的 2.2 倍、内壳 0.92 倍；fylite 的 code/vstab 是刚性模型，这一项无对应（读数，雅可比线性度未核）。
- 平衡是 FreeGSNKE 的反演收敛态，不是 KEFIT 的（κ 高 3.5 %）；fylite 在 KEFIT 平衡上的 γ 低 4.3 %（内壳）/ 2.2 %（三组合），只作读数。
- 主动线圈冻结（与 circuit: passive 同义）；不含反馈控制、线圈电源与快控线圈。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/freegsnke/freegsnke_vstab_east137985.tar.gz | sha256:df6725b4bfe4ad664620c4503dfb4d8aea5b951b36b772a8fc1902f3cfbc6c81 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/wall_vstab_east137985.json | sha256:4f106103acdd250b9ef317073c447be7eb90f923adadac93f9eaad9c6ed46cc0 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'registered or b18'
# 读数重写：python tools/benchmark-wall-vstab.py readings --out <dir>
```

## 6. 结论

成立：同一张平衡与同一组输入下，fylite code/vstab 的刚性垂直增长率与 FreeGSNKE 的刚性色散差 −0.006 %（内壳，709 s⁻¹）/ +0.11 %（三组合，4.27 s⁻¹），裕度差 ≤ 0.005（内核改正 a1 ≠ 0 的读法后重录；首录内壳为 +0.37 %）；FreeGSNKE 的可变形增长率另记为读数。
