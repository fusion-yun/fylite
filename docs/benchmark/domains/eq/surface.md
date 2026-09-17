---
title: "磁面几何、全局量与形状表示"
---

# 磁面几何、全局量与形状表示

*平衡 (Equilibrium) · 本域答：解出来的磁面上那些积分量（gm1..gm9 · 磁剪切 · Mercier · beta_p · l_i · W_mhd）与形状参数（MXH）算得对不对。*

磁面解出来之后，真正被下游用掉的不是 $\psi$ 本身，是磁面上的那一堆积分量：`gm1`..`gm9`、
磁剪切 $s$、Mercier 判据 $D_I$ / $D_R$、$\beta_p$、$l_i$、$W_{\rm mhd}$，以及把磁面形状压成
几个数的 MXH 参数。输运方程的度规系数全从这里来，稳定性判据也从这里来。★**这一章的错
不会当场报错，它会安静地改变下游每一个数。**

量它有两条各自独立的路，缺一不可。一条是**恒等式互锁**：这些量之间有几条恒成立的不等式
与定义关系（$gm_1 \ge gm_9^2$、$gm_8 gm_9 \ge 1$、轴上磁剪切趋零……），它们不需要任何外部
参考就能抓出定义写错的项。另一条是**对着别人的实现量**：同一张 g 文件喂给两个码，看九个
量逐条差多少。前者抓定义错，后者抓约定错——两类错的表现完全不同，一条路抓不了两类。

★口径在这一章格外要紧：`gm` 目录里每一项的定义都依赖径向标签取的是 $\rho$ 还是 Miller 的
$r$，以及磁面平均的权重取哪一个。两个码的 `gm1` 差一个量级，多半不是谁算错了，是两边在
说不同的量。**记录必须把径向标签与平均权重写进 `validity_domain`，否则那个数不可复算。**

上一册的 `V-15`（g 文件往返）与 `B-16` / `B-10`（定边界对 CHEASE）落在这一域。同前，已退役。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-03` v0.43）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-03` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-EQ-003` · 磁面分析（0 维 / 1 维几何量与磁面积分）** — MUST · 验证方法：测试

> 孪生 $W_{\text{mhd}}$ 对真值体积分闭合；`global_quantities`（$\beta_p$/$l_i(3)$/$W_{\text{mhd}}$）随 fit 报告出

**`FR-EQ-012` · 固定边界高精度重解与磁面平均目录** — SHOULD · 验证方法：测试

> （FR-EQ-012 (a) q 锁定）$q(\bar{\psi})$ 锁定重解落地（`solve(q_target=…)`：p'+目标 q 反解 FF'、保护式信赖域外环、冻结 span）；自洽往返复现 q_ref $\le 6$%、适度重定标 $(\times 1.2)$ $\le 7$%（fyeq nominal-q 框架，大幅径向形变受限）

> （FR-EQ-012 目录 / 磁剪切）`gm1..gm9` + 磁剪切 $s=(\rho/q)\mathrm dq/\mathrm d\rho$（IMAS `magnetic_shear`）落地——发布 / 有限 / 轴上$\to 0$ / 定义一致；**九项定义逐条核验**（2026-08-05）+ 恒成立不等式互锁（$gm_1\ge gm_9^2$、$gm_8 gm_9\ge 1$、$gm_4 gm_5\ge 1$、$gm_3\ge gm_7^2$；Jensen / Cauchy–Schwarz，不依赖基准值）+ 大展弦比严格区间界 + 前向$\leftrightarrow$重解互校（$I_p$ rtol 1e-6、gm 内区 rel $\le$1.5e-2）

> （FR-EQ-012 目录 / Mercier）Mercier $D_I$/$D_R$ **已落并对拍闭环**（2026-08-05）：`fyeq.mercier` 逐式转写 CHEASE Eq.19-22；**「须复刻 (s,$\theta$) Jacobian 机构」前提经原文 Eq.(A.1) 推翻**——$J\dd\chi = R\dd l/\lvert \nabla\Psi\rvert $ 使 $J_1..J_6$ 为**坐标无关磁面线积分**，本仓等值线核直算。CHEASE 数值桥（tcase2 共同基准 g-file，零插值）实测：中带 $\bar\psi\in[0.15,0.90]$ 相对偏差 $-D_I$ 中位 **7.6e-4** / max 4.8e-2，相关 0.997，符号逐面一致，$-D_I$ 零穿越两码同落 $\bar\psi\approx0.134$；近轴 $\bar\psi<0.06$ 偏差 $\le$13%（g-file 65 点 Z 栅格 + $1/\rho^2$ 放大）

**`FR-EQ-013` · MXH 磁面形状参数化与拟合** — SHOULD · 验证方法：测试

> （FR-EQ-013 (a)–(d)(f)）MXH 磁面形状参数化 + 谐波拟合器 + 最小阶自搜（`fit_auto`）+ RMS/曲率诊断（`fit_diagnostics`）+ 度规族落地；FUSE `MillerExtendedHarmonic.jl` 对齐（$\delta /\kappa /\zeta$ 恢复 $\le 2e-2$）、度规解析 vs 有限差 rtol 2e-3、拟合 RMS_rel<5e-3

> （FR-EQ-013 (e) 摄入+驱动）`file_geqdsk`（原 `fyeq.ingest` 已收敛至此）：EFIT/CHEASE/GEQDSK g-file $\to$ COCOS 稳健 MXH 边界拟合（7 机型 MAST/DIII-D/JET RMS $\le 2.4$%）$\to$ 合成 core_profiles $\to$ q 锁定定形重解贯通；对真 EFIT q 定性符合（升趋势 / q95 量级，量化 ~30% 受下游近似限）

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-surface-chease-fixed-boundary-east`](../../reports/eq-surface-chease-fixed-boundary-east.md) | 对拍 | 成立 | CHEASE | 1.4 | 草稿 | [jsonld](../../records/eq-surface-chease-fixed-boundary-east.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
