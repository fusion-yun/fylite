---
title: 公开 V&V 登记册 · 索引
---

# 公开 V&V 登记册 · 索引

25 条记录，11 个场景；由 `tools/benchmark-publish.py`（内核仓）自登记册渲染，复测 2026-09-02。
复测结论：不成立 1、成立 2、未评估 22。★跨类不可比：V/B/C 问的不是同一个问题（README）。

纳入类别（README「什么能进这个公开登记册」的落地）：`public` 公开可复取 · `public-derived` 公开派生表 · `restricted` 受限仅指针 · `restricted-derived` 受限派生 · `experiment` 实验数据仅指针 · `private-artefact` 私仓制品。受限与实验类只存路径与 sha256，本体不在任何公开仓。

| # | 类 | 参考 | 纳入类别 | 登记册 | 复测 2026-09-02 | 报告 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| V-01 | V | GACODE | public、public-derived、restricted-derived | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-01](V-01-gacode-ports.md) |
| V-02 | V | TGLFNN.jl；EPEDNN.jl | private-artefact、public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-02](V-02-nn-surrogates.md) |
| V-03 | V | fusion_surrogates（qlknn_model.QLKNNModel.predict_targets —— 上游自己的推理路径，25 点测试向量的产出者）；QLKNN_7_11（权重，archive 版本标记 11D） | private-artefact、public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-03](V-03-qlknn-7-11.md) |
| V-09 | V | TORAX（collisional_radiative_models + physics/radiation，非日冕档） | private-artefact、public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-09](V-09-mavrin-noncoronal.md) |
| V-10 | V | TORAX（divertor_sol_1d + extended_lengyel_formulas） | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-10](V-10-lengyel-closed-forms.md) |
| V-11 | V | TORAX（divertor_sol_1d 的派生属性 + extended_lengyel_formulas.calc_Z_eff） | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-11](V-11-lengyel-two-point.md) |
| V-12 | V | TORAX（extended_lengyel_solvers.inverse_mode_fixed_point_solver） | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-12](V-12-lengyel-inverse.md) |
| V-13 | V | TORAX（extended_lengyel_solvers.forward_mode_fixed_point_solver） | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-13](V-13-lengyel-forward.md) |
| B-01 | B | FUSE | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-01](B-01-fuse-iter.md) |
| B-02 | B | JINTRAC | restricted | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-02](B-02-jintrac-iter-102530.md) |
| B-03 | B | JINTRAC | restricted | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-03](B-03-jintrac-jet-101612.md) |
| C-01 | C | CORSICA / ASTRA | restricted | 成立 | 不成立（0 passed, 1 failed, 0 error, 0 skipped, 0 stale） | [C-01](C-01-iter-15ma-astra.md) |
| C-02 | C | ASTRA | restricted | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-02](C-02-alpha-heating-astra.md) |
| C-03 | C | TokSys | — | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-03](C-03-toksys-rzrig.md) |
| C-04 | C | METIS | public-derived | 成立 | 成立（57 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-04](C-04-metis-hcd.md) |
| B-04 | B | METIS | public、public-derived | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-04](B-04-metis-zerod-geometry.md) |
| C-05 | C | GYRO | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-05](C-05-gyro-momentum-waltz2007.md) |
| V-05 | V | gyrokinetic parity symmetry (Peeters et al., Nucl. Fusion 51, 094027 (2011) §2; Peeters, Angioni & Strintzi, PRL 98, 265003 (2007)) | public-derived | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-05](V-05-momentum-parity.md) |
| V-04 | V | GACODE | public | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-04](V-04-gacode-regression-suite.md) |
| V-06 | V | GACODE / TGYRO | public | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-06](V-06-tgyro-mapping-treg01.md) |
| V-07 | V | GACODE / TGYRO | public | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-07](V-07-tgyro-cases.md) |
| V-08 | V | TORAX | public | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-08](V-08-torax.md) |
| V-14 | V | TORAX | public | 成立 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-14](V-14-torax-evolution-composition.md) |
| B-05 | B | TORAX | public | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-05](B-05-torax-evolution.md) |
| B-06 | B | EFIT (gfortran, libefit.so) | experiment | 部分 | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-06](B-06-east-reconstruction.md) |
