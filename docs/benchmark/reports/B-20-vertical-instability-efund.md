---
title: B-20 · 垂直不稳定性对 KEFIT 的电磁层：KEFIT 平衡上 efund 表组装的刚性装置对 fylite code/vstab
---

# B-20 · 垂直不稳定性对 KEFIT 的电磁层：KEFIT 平衡上 efund 表组装的刚性装置对 fylite code/vstab

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | efund（KEFIT 的格林表生成器） · KEFIT 参考包 green_2022_source/u/efundud6565.f，gfortran 本地构建于临时目录（参考包未改）；两处补丁随件：真空室行表控读入 · 写出 rvsvs；构建件的 PF 线圈表对参考包原表 2.5e-15 / 4.7e-16 · private-artefact；KEFIT · kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json） · private-artefact |
| **对象** | fylite: code/vstab 经树门（circuit: passive、内壳、coarsen 1；质量为零的刚性等离子体、恒 Ip、主动线圈冻结） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_wall_vstab.py::test_the_efund_run_is_the_registered_one`；`python/tests/test_benchmark_wall_vstab.py::test_b20_the_rigid_plant_reproduces_and_stays_in_the_band_against_efund` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST #137985 4.041 s KEFIT 纯磁平衡；无源组内壳（efund 的 EAST 输入只含内壳）；刚性、质量为零；不含可变形等离子体

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 增长率 γ 相对差（fylite code/vstab 对 efund 表组装的刚性装置，同一 KEFIT 平衡；每元 8×8 与 16×16 两档） | relative | 0.0101 | measured_band |  |
| 失稳刚度 k 相对差 | relative | 0.0038 | measured_band |  |
| 理想刚度 k_ideal 相对差 · 裕度绝对差 | relative | 0.00607 | measured_band | 裕度另带 0.00291 |
| 耦合梯度 g 逐元相对差中位 / 最大 | relative | 0.00313 | measured_band | 最大值另带 0.0102 |

## 2. 口径与说明

- ★KEFIT 不给垂直增长率：本条是 KEFIT **电磁层**（efund 的互感、格林表）组装的刚性装置对 fylite，不是 KEFIT 的稳定性结论
- ★两边同用卡片电阻（efund 不带电阻）、同一刚性色散关系；差只在 M · g · k 的求法与等离子体离散（efund：g-file 网格节点；fylite：coarsen 1 细丝）
- 纳入类别（参考数据）：private-artefact、experiment

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| efund 装置 | γ 676.4 s⁻¹ · k 210838 N/m · k_ideal 270619 · 裕度 0.2835（M = 2π·rvsvs；g、k 由 ±1 mm 平移网格两次运行差分；814 个等离子体节点） | 成立 |  |
| fylite（fine） | γ 678.2（+0.28 %）· k +0.38 % · k_ideal +0.21 % · 裕度 0.2814（-0.0021）· g 中位 0.31 % / 最大 1.02 % | 成立 |  |
| fylite（finest） | γ 669.5（-1.01 %）· k +0.38 % · k_ideal +0.61 % · 裕度 0.2864（+0.0029）· g 中位 0.31 % / 最大 1.02 % | 成立 |  |
| 复测 2026-09-15（本条写入时把门跑一遍） | 2 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 |  |

## 4. 不可比的部分

- KEFIT 没有稳定性计算：本条比的是它的电磁层组装出的刚性装置，不是 KEFIT 的结论。
- 等离子体离散不同：efund 侧在 g-file 的 65² 节点上取 J，fylite 在 coarsen 1 的细丝上；16×16 与 8×8 两档之间 fylite 自己的 γ 走 1.3 %。
- 只含内壳（efund 的 EAST 输入里只有内壳）；刚性、主动线圈冻结。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/efund/efund_east137985.tar.gz | sha256:56f51cb8d59831c1324eb424feecb32367d3235012451615147e539c3fbc14a0 | private-artefact |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/wall_vstab_kefit_east137985.json | sha256:db9ad1bdccd14af6c6069fb17dbf038619ed650f425fcad9c0c7734d9999511d | private-artefact |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz | sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258 | experiment |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'efund or b20'
# 读数重写：python tools/benchmark-wall-vstab.py kefit-readings --out <dir> [--bundle <参考包>]
```

## 6. 结论

成立：KEFIT 平衡上，efund 表组装的刚性装置 γ 676.4 s⁻¹ 与 fylite code/vstab 差 +0.28 %（8×8）/ −1.0 %（16×16），k 差 0.38 %、k_ideal 0.2–0.6 %、裕度 ±0.003，耦合梯度逐元中位 0.31 %。
