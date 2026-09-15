---
title: 公开 V&V 登记册 · 索引
---

# 公开 V&V 登记册 · 索引

50 条记录，18 个场景；★2026-09-15：平衡相关的 V-16 · V-17 · B-12 · B-14 · V-18 · B-15 由公开检出的 `tools/benchmark-equilibrium-records.py` 直写（用户裁定「完善平衡相关 benchmark，不动 fylite_kernel」「废弃 libefit 对标，直接对标 KEFIT」），复测列是写入当日的；C-06 · C-07 · B-10 并入 V-16，B-06 · B-11 由 B-12 取代，C-03 的门自 2026-09-14 起 skip。★2026-09-15（第二批）：定边界 V-19 · B-16 同一工具直写（用户「补全 fixed-boundary 情景」；内核当日新增 `code/fixed_boundary`），B-10 原题由它们立。★2026-09-15（第二批）：导体壁 B-17 与垂直不稳定性 B-18（对 FreeGSNKE，用户「补全导体壁，垂直不稳定性算例」；内核当日新增 `code/wall` 并修正 EFIT 平行四边形读法）同一工具直写，C-03 由 B-18 取代。★2026-09-15（第二批）：导体壁 B-19 与垂直不稳定性 B-20（对 KEFIT 的电磁层 efund，用户「导体壁，垂直不稳定性，与 kefit 对拍」；内核同日改正 a1 ≠ 0 的读法，B-17 · B-18 重录）同一工具直写。★2026-09-15（第三批，/goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」）：自由边界演化与 PF 电路 · 无源件耦合 V-21（内核新门 code/evolve_free_boundary，EAST 卡片上的恒等式；同时读出 B-14 的节点规则答案由虚拟位置对撑着）同一工具直写。★2026-09-15（第四批，/goal「… 前向后向」）：静态逆问题 B-21（同一目标形状下 code/discharge 的线圈设计对 FreeGSNKE 反演；同时读出逆问题的零空间——两边电流差 25.6 kA·t，正解出的平衡只差毫米级）同一工具直写。由 `tools/benchmark-publish.py`（内核仓）自登记册渲染，复测 2026-09-08。
复测结论：成立 35、未评估 1（B-11，2026-09-14 加入，门是运行脚本、未随发布跑；2026-09-15 撤回——用户裁定 efit_east 树只作对拍比较数据，本条输入取自该树）。★跨类不可比：V/B/C 问的不是同一个问题（README）。

:::{figure} ../figures/overview.svg
:alt: 逐条记录的判定与发布当日的复测门数
:width: 100%

**填色**是登记册当初的结论，**细条**是发布当日把门跑一遍的通过条数——两件事分开画：合成一个颜色，「量过了」与「今天还成立」就再也分不开。图由 `tools/benchmark-figures.py` 自登记册重画。
:::

纳入类别（README「什么能进这个公开登记册」的落地）：`public` 公开可复取 · `public-derived` 公开派生表 · `restricted` 受限仅指针 · `restricted-derived` 受限派生 · `experiment` 实验数据仅指针 · `private-artefact` 私仓制品。受限与实验类只存路径与 sha256，本体不在任何公开仓。

| # | 类 | 参考 | 纳入类别 | 登记册 | 复测 2026-09-08 | 报告 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| V-01 | V | GACODE | public、public-derived、restricted、restricted-derived | 成立 | 成立（95 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-01](V-01-gacode-ports.md) |
| V-02 | V | TGLFNN.jl；EPEDNN.jl | public-derived | 成立 | 成立（14 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-02](V-02-nn-surrogates.md) |
| V-03 | V | fusion_surrogates；QLKNN_7_11 | private-artefact、public、public-derived | 成立 | 成立（27 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-03](V-03-qlknn-7-11.md) |
| V-09 | V | TORAX | private-artefact、public-derived | 成立 | 成立（8 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-09](V-09-mavrin-noncoronal.md) |
| V-10 | V | TORAX | public-derived | 成立 | 成立（7 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-10](V-10-lengyel-closed-forms.md) |
| V-11 | V | TORAX | public-derived | 成立 | 成立（8 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-11](V-11-lengyel-two-point.md) |
| V-12 | V | TORAX | public-derived | 成立 | 成立（6 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-12](V-12-lengyel-inverse.md) |
| V-13 | V | TORAX | public-derived | 成立 | 成立（7 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-13](V-13-lengyel-forward.md) |
| B-01 | B | FUSE | public-derived | 成立 | 成立（9 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-01](B-01-fuse-iter.md) |
| B-02 | B | JINTRAC | restricted | 部分 | 成立（18 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-02](B-02-jintrac-iter-102530.md) |
| B-03 | B | JINTRAC | restricted | 部分 | 成立（4 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-03](B-03-jintrac-jet-101612.md) |
| C-01 | C | CORSICA / ASTRA | restricted | 成立 | 成立（1 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-01](C-01-iter-15ma-astra.md) |
| C-02 | C | ASTRA | restricted | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-02](C-02-alpha-heating-astra.md) |
| C-03 | C | TokSys | — | 成立 | 未评估（0 passed, 0 failed, 0 error, 2 skipped, 0 stale） | [C-03](C-03-toksys-rzrig.md) |
| C-04 | C | METIS | public-derived | 成立 | 成立（57 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-04](C-04-metis-hcd.md) |
| B-04 | B | METIS | public、public-derived | 成立 | 成立（12 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-04](B-04-metis-zerod-geometry.md) |
| C-05 | C | GYRO | public | 成立 | 成立（13 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-05](C-05-gyro-momentum-waltz2007.md) |
| V-05 | V | gyrokinetic parity symmetry | public-derived | 成立 | 成立（13 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-05](V-05-momentum-parity.md) |
| V-04 | V | GACODE | public-derived | 部分 | 成立（42 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-04](V-04-gacode-regression-suite.md) |
| V-06 | V | GACODE / TGYRO | public-derived | 部分 | 成立（35 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-06](V-06-tgyro-mapping-treg01.md) |
| V-07 | V | GACODE / TGYRO | public-derived | 部分 | 成立（88 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-07](V-07-tgyro-cases.md) |
| V-08 | V | TORAX | public-derived | 部分 | 成立（4 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-08](V-08-torax.md) |
| V-14 | V | TORAX | public-derived | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-14](V-14-torax-evolution-composition.md) |
| B-05 | B | TORAX | public-derived | 部分 | 成立（6 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-05](B-05-torax-evolution.md) |
| B-06 | B | EFIT；KEFIT | experiment、private-artefact | 撤回（2026-09-13；本页现为动理学反演对标的工作流 / 计划，2026-09-14 立项，手写） | 未复测（计划页；撤回记录的门输入已归档） | [B-06](B-06-east-reconstruction.md) |
| V-15 | V | fylite | experiment、public | 成立 | 成立（6 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-15](V-15-gfile-roundtrip.md) |
| C-06 | C | TEQ / CORSICA | restricted、restricted（ITER IDM Internal Use） | 撤回（2026-09-15：并入 V-16，改判为 V） | 成立（6 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-06](C-06-teq-iter-equilibria.md) |
| C-07 | C | TOSCA | restricted、restricted（ITER IDM Internal Use） | 撤回（2026-09-15：并入 V-16，改判为 V） | 成立（5 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-07](C-07-tosca-run-space.md) |
| B-10 | B | CHEASE | public | 撤回（2026-09-15：并入 V-16，改判为 V） | 成立（4 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-10](B-10-chease-fixed-boundary.md) |
| C-09 | C | ITPA TC-33 参考解 | public | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-09](C-09-itpa-tc33.md) |
| B-09 | B | DINA | restricted | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-09](B-09-dina-ramp.md) |
| B-07 | B | TGYRO | public-derived | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-07](B-07-tgyro-converged.md) |
| C-11 | C | QuaLiKiz | public | 成立 | 成立（5 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-11](C-11-qualikiz-ground-truth.md) |
| B-08 | B | FUSE | public-derived | 成立 | 成立（8 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-08](B-08-fuse-iter-time.md) |
| C-10 | C | TRANSMAK | restricted | 成立 | 成立（6 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [C-10](C-10-transmak-initiation.md) |
| B-11 | B | EFIT | experiment、private-artefact | 撤回（2026-09-15：用户裁定 efit_east 树只作对拍比较数据，本条输入取自该树；记录保留作历史） | 未评估（0 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-11](B-11-east-efit-east-reconstruction.md) |
| V-16 | V | TEQ / CORSICA；TOSCA；CHEASE | public、restricted | 成立 | 成立（15 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-16](V-16-gs-residual-reading.md) |
| V-17 | V | Solov'ev 解析解 | public | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-17](V-17-solovev-manufactured.md) |
| B-12 | B | KEFIT | experiment、private-artefact | 读数（不判） | 成立（1 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-12](B-12-east-raw-trees-kefit.md) |
| B-14 | B | KEFIT | experiment、private-artefact | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-14](B-14-forward-kefit.md) |
| V-18 | V | fylite code/forward 的真值 | experiment | 成立 | 成立（1 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-18](V-18-twin-reconstruction.md) |
| B-15 | B | KEFIT | experiment、private-artefact | 成立 | 成立（1 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-15](B-15-twin-kefit.md) |
| V-19 | V | Solov'ev 解析解；CHEASE | public | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [V-19](V-19-fixed-boundary-solovev.md) |
| B-16 | B | CHEASE；KEFIT | experiment、private-artefact、public | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-16](B-16-fixed-boundary-chease.md) |
| B-17 | B | FreeGSNKE | experiment、public | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-17](B-17-wall-freegsnke.md) |
| B-18 | B | FreeGSNKE；KEFIT | experiment、private-artefact、public | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-18](B-18-vertical-instability-freegsnke.md) |
| B-19 | B | efund（KEFIT 的格林表生成器） | private-artefact | 成立 | 成立（3 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-19](B-19-wall-efund.md) |
| B-20 | B | efund（KEFIT 的格林表生成器）；KEFIT | experiment、private-artefact | 成立 | 成立（2 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-20](B-20-vertical-instability-efund.md) |
| V-21 | V | 解析恒等式；KEFIT | experiment、private-artefact、public | 成立 | 成立（5 passed, 0 failed, 0 error, 0 skipped, 0 stale（同一次运行另三份平衡门 18 过）） | [V-21](V-21-evolve-free-boundary.md) |
| B-21 | B | FreeGSNKE；KEFIT | LGPL-3、experiment、private-artefact | 成立 | 成立（5 passed, 0 failed, 0 error, 0 skipped, 0 stale） | [B-21](B-21-inverse-shape-freegsnke.md) |
