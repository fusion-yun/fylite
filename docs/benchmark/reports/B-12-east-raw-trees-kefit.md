---
title: B-12 · EAST #137985 原始树输入：fylite 与 KEFIT 在同一组数上（取代 B-06 · B-11）
---

# B-12 · EAST #137985 原始树输入：fylite 与 KEFIT 在同一组数上（取代 B-06 · B-11）

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/reconstruction（纯磁，竖直设定点扫描）与 W4b / W4c（POINT 法拉第行）经树门；输入经 fylite.io.raw.reduce_series 读原始树 |
| **数据** | 见 §5 表（4 项） |
| **门** | `python/tests/test_benchmark_equilibrium.py::test_b12_the_raw_tree_readings_are_the_registered_ones`；`$FYLITE_KERNEL/tools/benchmark-east-raw.py` |
| **登记册结论** | 未判（读数）（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——1 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 @ 4.041 / 4.944 / 5.976 s；east 测量链（east_new 卡片）；同一份 7 探针剔除；两个代码同一组数的读数，不作判定

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 同一组原始树输入上两个代码的纯磁读数（q₀ · q₉₅ · 磁轴 · 边界 · χ²） |  | — | measured_band | **不判、无带**：两个代码仍有三处实现差（KEFIT 拟合 PF 电流而 fylite 固定实测值、竖直位置的处理、边缘系数），本组分不开 |

## 2. 口径与说明

- ★★取代 B-06（est2 测量集，2026-09-13 撤回）与 B-11（efit_east 树的输入，2026-09-15 撤回）：同一个对象（EAST #137985 的平衡反演），换成原始树输入，参考换成 KEFIT
- ★所有进入反演的数都读自 east / pcs_east 原始树；efit_east 的答案只作比较（用户裁定 2026-09-15）
- 纳入类别（参考数据）：experiment

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| 4.041 s 纯磁（剔 7 探针）：fylite 对 KEFIT | q₀ 2.042 对 1.913 · q₉₅ 6.53 对 6.28 · 磁轴对 efit_east 答案 dR -52.2 对 -17.2 mm · 边界中位 10.7 对 13.6 mm · χ² 71.0 对 47.4（两边都收敛；KEFIT 无错误标记） | 未判（读数） | efit_east 的答案只作比较参照（用户裁定 2026-09-15），不是本条的参考 |
| 4.944 s 纯磁（剔 7 探针）：fylite 对 KEFIT | q₀ 1.984 对 1.924 · q₉₅ 6.56 对 6.30 · 磁轴对 efit_east 答案 dR -43.3 对 -17.6 mm · 边界中位 8.8 对 12.9 mm · χ² 70.1 对 46.2（两边都收敛；KEFIT 无错误标记） | 未判（读数） | efit_east 的答案只作比较参照（用户裁定 2026-09-15），不是本条的参考 |
| 5.976 s 纯磁（剔 7 探针）：fylite 对 KEFIT | q₀ 1.924 对 2.000 · q₉₅ 6.61 对 6.29 · 磁轴对 efit_east 答案 dR -40.5 对 -25.9 mm · 边界中位 7.8 对 13.4 mm · χ² 77.0 对 47.6（两边都收敛；KEFIT 无错误标记） | 未判（读数） | efit_east 的答案只作比较参照（用户裁定 2026-09-15），不是本条的参考 |
| 全部探针：两个代码都拟不上 | fylite 纯磁 χ² 1883 / 1870 / 1881 · KEFIT 1700 / 1710 / 1750（Error #1） | 不成立 | 同一批不自洽通道：KEFIT 纯磁 χ² 份额 HBPH1T 883 · HBPD10T 169 · HBPH2T 64 · HBPH1N 56 · HBPD10N 51 · HBPD8T 37 · HBPH3T 25，同一份剔除交给两个代码（读自拟合本身） |
| 加 POINT：两个代码都不稳 | fylite 主集 q₀ 0.82 / 0.82 / 0.90 · KEFIT 4.041 s `Problem in CNTOUR`、4.944 s 带 Error #19–21、5.976 s q₀ 1.04 | 未判（读数） | 原始输入上的档 K 没有可作参考的答案 |
| KEFIT 几何：GUI_v5 自带表 green2018_wpf_64 不是原始探针名读的道阵 | 按位置与角度配对，79 槽中 56 对差 > 2 cm / 10°；改 green2022_pcs：76 槽中 74 槽 0 mm / 0° 重合 | 成立 | 这是 2026-09-14 GUI 原配方各例 `Problem in BOUND` 的原因 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 1 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-12` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-12` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-12` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-12` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-12` 列进 `--only` 并在 `--reruns` 里给出本次实测。 |

## 4. 不可比的部分

- 两个代码仍有三处实现差：KEFIT 以 FWTFC 0.3 拟合 PF 电流、fylite 固定实测值；KEFIT `fitdelz` 对 fylite 竖直设定点扫描；KEFIT 边缘系数 pcurbd = fcurbd = 0.5、fylite 无对应。
- B_T 取 TF 电流节点 `\TOP.T2:TFP` 与 GUI_v5 注释式（130 匝 × 16 线圈）——装置书只记为候选（gap tf-current-no-ampere-signal-since-97286）。
- 探针误差下限取 `efit/2016/bitmp2.txt` 的中位（GUI_v5 逐探针的行按另一套槽序）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/raw/raw_slices_east137985.json | sha256:8b2c04d2612b7b0105201cabdc19a60c09d7035f0ad9414fcb2cb062e424876c | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/fylite/fylite_raw_east137985.tar.gz | sha256:5b7360f8a2a83b1bcd9f7b9332accdb8a53ea831ea085aa0ff0e70e5291f89f2 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/comparison_readings_east137985.fyo.jsonld | sha256:e773b05be4e7ebc35acbbc6b65cc97ba9052a578fc585f36ee42e4261397db47 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
# 读数由私仓工具产出（$FYLITE_KERNEL/tools/benchmark-east-raw.py，见 B-06 报告 §9）；本仓的门只核读数与归档
cd $FYLITE_PUBLIC && FYDOC_ORACLE=<fydoc cases/> python -m pytest python/tests/test_benchmark_equilibrium.py::test_b12_the_raw_tree_readings_are_the_registered_ones
```

## 6. 结论

读数，不判：在同一组原始树输入上，剔除同一批 7 个不自洽探针后两个代码的纯磁反演都收敛（q₀ fylite 2.04 / 1.98 / 1.92，KEFIT 1.91 / 1.92 / 2.00），磁轴相差 15–35 mm；全部探针时两边都拟不上；加 POINT 后两边都不稳。
