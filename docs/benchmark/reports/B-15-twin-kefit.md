---
title: B-15 · 反演孪生体（已知真值）：KEFIT 在同一份合成测量上
---

# B-15 · 反演孪生体（已知真值）：KEFIT 在同一份合成测量上

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/forward 给出真值与合成测量（被比的是 KEFIT 对真值的偏差，与 V-18 的 fylite 偏差并列） |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_equilibrium.py::test_b15_kefit_on_the_twin_measurements_stays_in_its_band` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——1 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| q₀ / q₉₅ 相对差 | relative | 0.0487 | measured_band | q₉₅ 另带 0.0107 |
| 磁轴距离 | absolute | 1.33 mm | measured_band |  |
| ψ_N 差 rms / 最大（真值边界内） | absolute | 0.00681 | measured_band | 最大值另带 0.0132 |
| 边界距离中位 / 最大 | absolute | 1.57 mm | measured_band | 最大值另带 4.17 mm |
| 下 X 点距离 · 通量跨度 · Ip | absolute | 2.19 mm | measured_band | 跨度带 0.00853 · Ip 带 0.00248 |

## 2. 口径与说明

- ★与 V-18 同一份合成测量、同一个真值：两个代码谁偏、偏多少并列可读
- 纳入类别（参考数据）：experiment、private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| KEFIT 反演（无错误标记）：孪生体 4.041 s | q₀ -4.86 % · q₉₅ -1.06 % · 磁轴 -0.86 / +1.01 mm · ψ_N rms 0.68 % · 边界 1.56 / 4.16 mm · X 点 2.19 mm · 跨度 +0.852 % · Ip -0.247 % | 成立 |  |
| KEFIT 的输入配方 | KPPCUR = KFFCUR = 2、pcurbd = fcurbd = 1（与真值同基）；green2022_pcs 几何，76 槽中 74 槽按位置与角度配到卡片探针，槽 [48, 75] 权重 0；35 环取 FL1B–FL35B；σ = max(0.05 |值|, bit)；FWTFC 0.3 拟合线圈、bitip 40000 拟合 Ip、fitdelz | 成立 | q₀ 的 −4.9 % 是本条最大的差；Ip 的 −0.25 % 来自 KEFIT 把 Ip 当带权测量而非等式 |
| 复测 2026-09-15（本条写入时把门跑一遍） | 1 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 |  |

## 4. 不可比的部分

- KEFIT 用 green2022_pcs 几何（与卡片探针 74 / 76 槽重合），fylite 用卡片自己；两个未配对的 KEFIT 槽权重 0。
- KEFIT 拟合线圈电流与 Ip（带权），fylite 固定线圈、Ip 为等式。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_twin_east137985.tar.gz | sha256:ea9c108c43a1433e296aa037f3bbc858e0d0d9c53a5e671d7e3a6627314611c4 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/twin_east137985.json | sha256:dd4b16286a1ae1b7b331f8b20943c0700a5d6d21dd60aa1105ddaa8ba20ab9bb | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_equilibrium.py -k b15
```

## 6. 结论

成立：同一份合成测量上 KEFIT 反演无错误标记，q₀ 偏 −4.9 %、q₉₅ −1.1 %、磁轴 1.3 mm、边界 4.2 mm 内；与 V-18 并读，fylite 在这一真值上离得更近。
