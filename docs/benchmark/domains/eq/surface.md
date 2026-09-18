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

### MXH 拟合：残差堆在 X 点上（2026-09-18）

`FR-EQ-013` 的边界拟合一格入册。2026-09-18 之前内核只**吃** MXH 参数（`code/metric` 按面算度规），
**没有「给一条边界拟合 MXH」这一步**。

MXH 与 Miller 的分界在于：**$\theta$ 由 $Z$ 定义、$\theta_R$ 由 $R$ 定义**，形状全部落在那个角度偏移里，
于是它是一列傅里叶系数而不是一组各自为政的形状参数——拟合因此不需要非线性迭代。

★★**两道测试必须成对，这一条给出了证据**：圆钉退化（每条谐波为零，实测 6.5e-16），
已知形钉非退化（系数原样回来）。而**两个分支 bug 都是后者逮住的，前者对它们一声不响**——
圆的角度偏移恒为零，两个分支重合。第二个 bug 尤其值得记：改完第一处之后仍有 4.7e-4，
**而它不随点数收敛**（6.6e-4 / 5.3e-4 / 4.7e-4，比值 1.2）。★离散化误差按幂次缩，
系统性挑错不会——**「不收敛」这件事本身就是诊断**。

真机上：EAST 0.95–1.35 %、CFEDR 0.31–1.36 % 在判据的 2.4 % 带内，**DIII-D 2.460 % 刚出带**。
★★但更有信息的是**残差落在哪**：EAST 在 $\theta/\pi\approx0.35$、$z/a\approx+1.45$（上 X 点），
DIII-D 与 CFEDR 在 $\theta/\pi\approx1.5$–$1.7$、$z/a\approx-1.7$（下 X 点）——**无一例外**。
MXH 的六阶谐波表达不了尖角，所以这不是这份实现的缺陷，是这族参数化的性质。
★2026-09-18 判据点名的 **MAST 与 JET** 入列（`third_party/` 里的真 EFIT：MAST 2 份、JET 6 份）：全部在带内（MAST 0.82 / 1.77 %，JET ≤ 0.62 %），残差同样落在 X 点——**球形托卡马克上结论仍成立**。★并有了**第二套实现**：同一批 15 份轮廓交给 FUSE 的 MillerExtendedHarmonic.jl，几何量逐位、形状系数到 5.3e-3、两条重构曲线相距不到 0.78 % 小半径；它取 $Z=Z_0-\kappa a\sin\theta$，于是 $c_J=-c$、$s_J=+s$——这个映射是量出来的。
详见 [`eq-surface-mxh-gfile-fit`](../../reports/eq-surface-mxh-gfile-fit.md)。

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
| [`eq-surface-chease-fixed-boundary-east`](../../reports/eq-surface-chease-fixed-boundary-east.md) | 对拍 | 成立 | CHEASE | 1.16 | 草稿 | [jsonld](../../records/eq-surface-chease-fixed-boundary-east.jsonld) |
| [`eq-surface-mxh-gfile-fit`](../../reports/eq-surface-mxh-gfile-fit.md) | 验证 | 未判（读数） | 闭式 —— 圆的精确退化与一个已知 MXH 形的原样回收 · 本机拿得到的 g-file 边界 | 1.9 | 草稿 | [jsonld](../../records/eq-surface-mxh-gfile-fit.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
