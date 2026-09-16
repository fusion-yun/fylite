---
title: B-19 · 导体壁对 KEFIT 的电磁层：EAST 真空室元件的格林响应与互感对 efund
---

# B-19 · 导体壁对 KEFIT 的电磁层：EAST 真空室元件的格林响应与互感对 efund

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | efund（KEFIT 的格林表生成器） · KEFIT 参考包 green_2022_source/u/efundud6565.f，gfortran 本地构建于临时目录（参考包未改）；两处补丁随件：真空室行表控读入 · 写出 rvsvs；构建件的 PF 线圈表对参考包原表 2.5e-15 / 4.7e-16 · private-artefact |
| **对象** | fylite: code/wall 经树门（每元 8×8 细丝的逐元响应 loops_psi · probes_b · grid_psi；16×16 的互感矩阵） |
| **数据** | 见 §5 表（2 项） |
| **门** | `python/tests/test_benchmark_wall_vstab.py::test_the_efund_run_is_the_registered_one`；`python/tests/test_benchmark_wall_vstab.py::test_b19_the_wall_responses_and_inductance_reproduce_and_stay_in_the_band_against_efund`；`python/tests/test_benchmark_wall_vstab.py::test_b19_the_shipped_kefit_vessel_table_is_recorded_as_the_misread_deck` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-15（本条写入时把门跑一遍）：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：EAST 真空室内壳 40 元（efund 算表输入与装置卡片逐行同几何）；35 个磁通环、65² 网格；探针只作读数；外壳与被动板不在 efund 的 EAST 输入里

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 内壳 40 元 → 35 个磁通环的每弧度磁通响应，最大相对差 | relative | 2.04e-05 | measured_band |  |
| 内壳 40 元 → 65² 网格节点的每弧度磁通响应，最大相对差 | relative | 2.07e-07 | measured_band |  |
| 真空室互感矩阵：非对角相对差 p95（fylite 16×16 细丝 对 efund flux() 解析积分） | relative | 0.00366 | measured_band | 对角中位另带 0.0083、最大 0.0344（自感的求法不同） |
| 最长 L/R 时间 τ₁ 相对差（两边同用卡片电阻；efund 不带电阻） | relative | 0.000237 | measured_band |  |

## 2. 口径与说明

- ★★2026-09-15 用户「导体壁，垂直不稳定性，与 kefit 对拍」：KEFIT 本身不算增长率，它关于导体壁的电磁量全部出自 efund——参考取 efund 本体，在参考包自带的 EAST 输入上本地构建运行
- ★本条查出并修正了内核两处 EFIT 平行四边形读法（见结果）；修正前 B-17 / B-18 的读数同日重录
- ★口径：efund 表是每弧度磁通（M / 2π）、每安匝；fylite 的 loops_psi / grid_psi 同口径；元件顺序按中心位置配对（逐一相同）
- 纳入类别（参考数据）：private-artefact

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| 元件 → 磁通环 · 网格 | 环最大 2.0e-05（40 元全部 < 1e-3）· 网格最大 2.1e-07 · 中位 1.9e-08 | 成立 |  |
| 元件 → 探针（读数） | 74 / 76 配对；中位 1.8e-04 · p95 9.9e-03 | 未判（读数） | 探针两边的配对按位置与角度；efund 沿探针长度取 NSMP2 点平均 |
| 互感矩阵与 τ₁ | 非对角 p95 3.65e-03 · 对角中位 0.83 % / 最大 3.43 % · τ₁ 12.751 对 12.748 ms（+2.4e-04） | 成立 |  |
| 参考包交付的 rv6565.ddd（读数） | 对同一输入按原意重建的表：环最大差 9.0 %、网格 29.3 % | 未判（读数） | 算表输入里 7 行真空室元件的列没有对齐 efund 的 6e12.6 定宽读法（如 138.4682 被切成 1 与 38.4682），交付表即其误读结果；EAST 上用真空室通道的 KEFIT 反演吃的是这份表 |
| 内核几何读法两处修正（2026-09-15） | a1 = 0, a2 ≠ 90：efund 的 R 向剪切（此前读成倾斜边长 h）；a1 ≠ 0：efund 的 Z 向剪切（此前读成转角，内壳上下 14 段短 25 %、环响应差 1.6 %、网格 6 %） | 成立 |  |
| 复测 2026-09-15（本条写入时把门跑一遍） | 3 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | ★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。要重跑，把 `B-19` 列进 `--only` 并在 `--reruns` 里给出本次实测。；需 FYLITE_KERNEL_LIB 指向带 code/wall 的内核（公开检出的预建运行时库早于它，按名 skip） |

## 4. 不可比的部分

- efund 的 EAST 输入只含真空室内壳 40 元；外壳与被动板的格林列不在 KEFIT 里（B-17 对 FreeGSNKE 覆盖它们）。
- 互感对角：efund 用矩形截面解析积分，fylite 用 16×16 细丝加圆导线自感项——对角中位差 0.83 % 即此。
- 探针只作读数：efund 沿探针长度多点平均，配对按位置与角度（74 / 76）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/efund/efund_east137985.tar.gz | sha256:56f51cb8d59831c1324eb424feecb32367d3235012451615147e539c3fbc14a0 | private-artefact |
| $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/wall_vstab_kefit_east137985.json | sha256:db9ad1bdccd14af6c6069fb17dbf038619ed650f425fcad9c0c7734d9999511d | private-artefact |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \
  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \
  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'efund or b19'
# efund 侧重建：python tools/benchmark-wall-vstab.py efund-build --out <dir>（需 gfortran 与 $KEFIT_REFERENCE_BUNDLE）
```

## 6. 结论

成立：EAST 真空室内壳 40 元的格林响应与 efund 一致到磁通环 2.0e-5、网格 2.1e-7，互感非对角 p95 3.7e-3，τ₁ 差 2.4e-4；本条同时查出参考包交付的 rv6565.ddd 是算表输入 7 行错列的误读结果（差 9 % / 29 %），并修正了内核两处 EFIT 平行四边形读法。
