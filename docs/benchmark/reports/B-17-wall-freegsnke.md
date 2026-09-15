---
title: B-17 · 导体壁作为电路：EAST 无源结构的 L/R 本征模对 FreeGSNKE
---

# B-17 · 导体壁作为电路：EAST 无源结构的 L/R 本征模对 FreeGSNKE

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | FreeGSNKE · third_party/freegsnke-main + freegs4e 0.13.1（PyPI）· numpy 1.26.4；本地运行，同一张 EAST 卡片（efund 读法的多边形无源件 · 12 路 PF） · public |
| **对象** | fylite: code/wall 经树门（装置卡片的内壳 · 外壳 · 被动板；元件互感 · 电阻 · M dI/dt + R I = 0 的模，每组另单解；每元 16×16 细丝） |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_wall_vstab.py::test_the_freegsnke_run_is_the_registered_one`；`python/tests/test_benchmark_wall_vstab.py::test_b17_the_wall_modes_reproduce_and_stay_in_the_band_against_freegsnke` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST 卡片的 90 个无源元件（内壳 40 · 外壳 40 · 被动板 10，η 0.74 / 0.74 / 0.017 μΩ·m），仅环向电流、元件内均匀；无端口 / 波纹管等三维结构

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 最长 L/R 时间 τ₁ 相对差（内壳 · 外壳 · 被动板各自单解 · 三组合） | relative | 0.000762 | measured_band |  |
| 无源互感矩阵逐元：对角相对差中位 / 最大 | relative | 0.0148 | measured_band | 最大值另带 0.0801 |
| 无源互感矩阵逐元：非对角相对差 p95 · Frobenius 相对差 | relative | 0.00542 | measured_band | Frobenius 另带 0.0166 |
| 元件电阻相对差最大 | relative | 0.0112 | measured_band | FreeGSNKE 以蒙特卡罗估多边形面积，±1 % 的散布来自那里 |

## 2. 口径与说明

- ★★2026-09-15 用户「补全导体壁，垂直不稳定性算例」：内核当日新增 code/wall——导体壁先问「墙作为电路是什么」，不需要等离子体
- ★★内核缺陷随本条修正（2026-09-15）：EFIT 平行四边形原被读成「倾斜边长 h」，efund 是剪切（w · h 为水平 / 竖直外延）——EAST 壳段间留缝 7.6 / 9.2 mm、外壳 14 行塌成零面积线；修正移动 γ(三组) −1.1 %、τ₁ −0.6 %。修正前 FreeGSNKE 须用 efund 读法建多边形才可比；本条的读数是修正后的
- ★装置描述是 fydoc 装置书的 EAST pf_passive（A-Box `unverified`，手工维护：几何与电阻率出自未公开内部件）——本条比的是两个代码对**同一份**描述的电路，不是对 EAST 实物的确认
- 纳入类别（参考数据）：experiment（FreeGSNKE 运行件随 KEFIT 输入归实验类）

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| inner_shell：τ₁ | fylite 12.755 ms · FreeGSNKE 12.751 ms（+0.028 %）· M 对角中位 1.31 % / 最大 6.97 % · 非对角 p95 0.28 % · R 最大 1.07 % | 成立 |  |
| outer_shell：τ₁ | fylite 13.103 ms · FreeGSNKE 13.099 ms（+0.033 %）· M 对角中位 1.47 % / 最大 8.00 % · 非对角 p95 0.25 % · R 最大 1.11 % | 成立 |  |
| passive_plates：τ₁ | fylite 400.571 ms · FreeGSNKE 400.266 ms（+0.076 %）· M 对角中位 1.41 % / 最大 1.94 % · 非对角 p95 0.54 % · R 最大 0.32 % | 成立 |  |
| all：τ₁ | fylite 413.502 ms · FreeGSNKE 413.214 ms（+0.070 %）· M 对角中位 1.40 % / 最大 8.00 % · 非对角 p95 0.22 % · R 最大 1.11 % | 成立 |  |
| 离散（读数） | fylite 每元 3×3 细丝时自感偏高约 7 %（圆导线自感项取等面积半径，对细长子细丝偏大），τ₁ +0.8 %；8×8 对 16×16 τ₁ 差 0.14 %（code/wall 缺省 8×8，本条取 16×16） | 未判（读数） |  |
| 复测 2026-09-15（本条写入时把门跑一遍） | 2 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | 需 FYLITE_KERNEL_LIB 指向带 code/wall 的内核（公开检出的预建运行时库早于它，按名 skip） |

## 4. 不可比的部分

- 两边的自感求法不同：fylite 每元 nu × nv 细丝加圆导线自感项，FreeGSNKE 按多边形裁剪的方格细丝——M 对角差 1.4 % 中位即此；τ₁ 对它不敏感。
- 装置描述是 fydoc 装置书里未经核的手工卡片：本条不确认 EAST 实物的时间常数。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/freegsnke/freegsnke_vstab_east137985.tar.gz | sha256:df6725b4bfe4ad664620c4503dfb4d8aea5b951b36b772a8fc1902f3cfbc6c81 | experiment |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/wall_vstab_east137985.json | sha256:e8418fdaef8c556e9c45bac4fb2310141048f70e4e2cea3cf834cc790867b97f | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'registered or b17'
# FreeGSNKE 侧（不在门里）：解开 corpus/freegsnke/freegsnke_vstab_east137985.tar.gz，按其 run_all.sh（freegs4e==0.13.*）
```

## 6. 结论

成立：同一张 EAST 卡片上，fylite code/wall 与 FreeGSNKE 的无源 L/R 本征模 τ₁ 在内壳 · 外壳 · 被动板 · 三组合上差 ≤ 0.08 %（12.76 / 13.10 / 400.6 / 413.5 ms），互感矩阵非对角 p95 ≤ 0.54 %。
