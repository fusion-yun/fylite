---
title: V-18 · 反演孪生体（已知真值）：fylite 从自己正问题的合成测量反演回真值
---

# V-18 · 反演孪生体（已知真值）：fylite 从自己正问题的合成测量反演回真值

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | fylite code/forward 的真值 · 解析族 e_mp = e_np = 1，EAST east_new 卡片 · experiment |
| **对象** | fylite: code/forward（真值与合成诊断）→ code/reconstruction（npp = nff = 1，竖直设定点扫描）经树门 |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_equilibrium.py::test_v18_fylite_recovers_the_twin_truth_and_reproduces_its_readings` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——1 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| q₀ / q₉₅ 相对差 | relative | 0.00061 | measured_band | q₉₅ 另带 0.00128 |
| 磁轴距离 | absolute | 1.18 mm | measured_band |  |
| ψ_N 差 rms / 最大（真值边界内） | absolute | 0.00234 | measured_band | 最大值另带 0.00429 |
| 边界距离中位 / 最大 | absolute | 0.657 mm | measured_band | 最大值另带 1.65 mm |
| 下 X 点距离 · 通量跨度 · Ip | absolute | 0.784 mm | measured_band | 跨度带 0.000176 · Ip 带 9.5e-11 |

## 2. 口径与说明

- ★类是 V、带是实测带而非机器精度，理由三条：真值的自由边界迭代停在「settled」（残差 2e-4）；竖直设定点按 4 mm 步长扫描；线圈份额在正问题里是 4×4 细丝、在 code/coilshare 里是另一套求积——三者都给出非零但可复现的差
- ★真值在两个代码的基里都可精确表示（线性、边缘为零），所以剩下的差不是基的截断
- 纳入类别（参考数据）：experiment

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| fylite 反演：孪生体 4.041 s | q₀ +0.06 % · q₉₅ -0.13 % · 磁轴 -0.19 / -1.16 mm · ψ_N rms 0.23 % · 边界 0.66 / 1.65 mm · X 点 0.78 mm · 跨度 +0.018 % · Ip +0.000 % | 成立 |  |
| 设定点扫描 | −30 … +30 mm 每 4 mm；χ² 极小在 -2 mm（χ² 0.85），真值竖直位置 +7.9 mm | 成立 |  |
| 复测 2026-09-15（本条写入时把门跑一遍） | 1 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `V-18` 列进 `--only` 并在 `--reruns` 里给出本次实测。 |

## 4. 不可比的部分

- 无噪声、同一份卡片几何、同一个线圈描述：本条不含测量误差与装置描述误差。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/twin_east137985.json | sha256:dd4b16286a1ae1b7b331f8b20943c0700a5d6d21dd60aa1105ddaa8ba20ab9bb | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/raw/raw_slices_east137985.json | sha256:8b2c04d2612b7b0105201cabdc19a60c09d7035f0ad9414fcb2cb062e424876c | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_equilibrium.py -k v18
# 读数重写：python tools/benchmark-equilibrium.py twin --out <dir> [--kefit-exe <efitd6565d>]
```

## 6. 结论

成立：已知真值时 fylite 的反演把 q₀ 放回 0.06 %、q₉₅ 0.13 %、磁轴 1.2 mm、边界 1.7 mm 内。
