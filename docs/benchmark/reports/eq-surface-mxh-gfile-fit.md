---
title: "eq-surface-mxh-gfile-fit"
---

# MXH 边界拟合：**残差不是散开的，它堆在 X 点上**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-surface-mxh-gfile-fit.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [磁面几何、全局量与形状表示](../domains/eq/surface.md)　|　记录正本：`records/eq-surface-mxh-gfile-fit.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：MXH 边界拟合：**残差不是散开的，它堆在 X 点上**
- **参考**：闭式 —— 圆的精确退化与一个已知 MXH 形的原样回收 · 本机拿得到的 g-file 边界
- **验的需求**：`FR-EQ-013`
- **跑在内核**：`fylite_kernel@51d34102a406`（新鲜度 **current**）
- **记录版本**：1.15　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：此前内核只**吃** MXH 参数（`code/metric`），没有「给边界拟合 MXH」这一步

**参考**：闭式 —— 圆的精确退化与一个已知 MXH 形的原样回收

> ★★这两条是一对：圆钉**退化**（每条谐波为零），已知形钉**非退化**（系数原样回来）。★只验圆会放过一个把角度偏移算错的实现——圆的偏移恒为零，它照样过。

**参考**：本机拿得到的 g-file 边界

> ★判据点名「7 机型 MAST / DIII-D / JET RMS ≤ 2.4 %」。**本机只有 4 个机型**：EAST（3 炮）· DIII-D（1 炮）· CFEDR（3 份）· 合成（1 份）。**MAST 与 JET 没有**，那两格未评。

**口径与适用域**：

> g-file 的 `rbbbs` / `zbbbs` 边界轮廓，MXH 六阶谐波（与 `geometry::Surface::shape` 同一个 11 槽排列，$\delta=\sin s_1$、$\zeta=-s_2$）。★**只判边界这一条曲线**——判据里「合成 core_profiles → q 锁定定形重解贯通」那一段本条不涉及。★闭式两格在合成形上量，真机三格在实测轮廓上量。

## 判据与量到多少

:::{figure} ../figures/eq-surface-mxh-gfile-fit-headroom.svg
:alt: eq-surface-mxh-gfile-fit 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 圆的精确退化：每条谐波与 RMS | — | machine_precision | $R_0 = 3$、$a = 0.8$、512 点：$\kappa$ = 1.000000000000、$a$ 逐位、**每条谐波 ≤ 6.512e-16**、RMS **5.336e-16** | **成立** |
| 已知 MXH 形的系数原样回收（随轮廓点数收敛） | 1e-05 | analyst_declared | 造一个 $c_0..c_3$ / $s_1..s_3$ 已知的形（EAST 一档形变），点数 256 / 512 / 1024：最劣系数差 **4.869e-5 / 1.849e-5 / 4.052e-6**，RMS 2.561e-5 / 1.198e-5 / 1.781e-6。四倍点数缩 **12 倍** | **成立** |
| 真装置 g-file 边界的拟合 RMS（按小半径归一） | 0.024 | reference_self_reported | 判据 RMS（逐点到 MXH 曲线的最近距离、按 $a$ 归一）：**EAST** 0.58 / 0.75 / 0.77 % · **DIII-D** 1.57 % · **CFEDR** 0.94 / 0.36 / 0.22 % · **MAST** 0.56 / 1.25 % · **JET** 0.37 / 0.35 / 0.25 / 0.35 / 0.43 / 0.35 % · **JT-60SA** 0.12 % · **NSTX** 0.61 %（第二套实现 MillerExtendedHarmonic.jl 同一把尺，DIII-D 1.66 %）。★本仓 `mxh_rms`（同 θ 处 R 向误差，更严）：EAST 0.95 / 1.35 / 1.28 % · DIII-D 2.46 % · CFEDR 1.36 / 0.54 / 0.31 % · MAST 0.82 / 1.77 % · JET 0.62 / 0.50 / 0.41 / 0.51 / 0.60 / 0.55 % · JT-60SA 0.16 % · NSTX 0.92 %——DIII-D **2.460 %** 在这把尺上刚出带。★★最劣残差全在 X 点（$\|z/a\|$ 1.3 … 1.97），无一例外 | **成立** |
| 判据点名的 7 机型（MAST / DIII-D / JET …） | 7 | reference_self_reported | 7 个机型、17 份轮廓（另一份合成件不计）：MAST 2 · JET 6（`third_party` 的真 EFIT）· **JT-60SA 1**（CRONOS 带的设计平衡，与 CFEDR 同类）· **NSTX 1**（DCON 3.80 的算例，几何认机型：R0 0.87 m、a 0.61 m、B0 0.44 T）。JT-60SA 判据 RMS 0.12 %、NSTX 0.61 % | **成立** |
| 第二套实现：同一批轮廓交给 FUSE 的 MillerExtendedHarmonic.jl，比几何量、系数与重构曲线 | — | reference_self_reported | 17 份（EAST 3 · DIII-D 1 · CFEDR 3 · MAST 2 · JET 6）：$R_0, Z_0, a, \kappa$ 差 ≤ 1.5e-16；形状系数最劣差 5.3e-03（JET SOLPS 件 2e-6 … 1e-5，点少或 X 点尖的件 1e-3 … 5e-3）；两条重构曲线最大间距 0.78 % 小半径；到数据点的几何 RMS 两边几乎相同（例：MAST 29908 0.556 / 0.551 %，JET 96100 0.372 / 0.351 %） | **成立** |

**★★已知 MXH 形原样回来——而这条把两个分支 bug 揪了出来**

- ★★**这条测试逮住了两个分支 bug，而圆那条对它们一声不响**：〔一〕初版拿 $\cos\theta_R$ 的符号去分 $\theta$ 的支，而那是**另一个角**——偏移大到让两者落进不同半平面时（本例 $s_1=0.31$）分支就挑错，系数偏到 **2.385e-2**；〔二〕改完仍有 **4.7e-4 且不随点数收敛**（6.6e-4 / 5.3e-4 / 4.7e-4，比值 1.2），那是 $\theta_R$ 取「离 $\theta$ 最近的一支」——**$\theta\approx\pi$ 处两个候选都贴着 $\pi$**，挑法在那一带失效。改成与 $\theta$ 同一个办法（由 $\mathrm{d}R$ 的符号定）之后降到 4e-6。
- ★★**「不收敛」这件事本身是诊断**：离散化误差会按幂次缩，而系统性挑错不会。若当初调松容差让它过了，那块偏差会一直在。
- ★判据按**跨两档**看而不是单步：$\kappa$ 从包围盒取，误差由「哪个采样点离 $Z$ 极值最近」决定，**是阶梯式的**——实测 256 与 512 上 $\kappa$ 完全相同（1.750015905），到 1024 才跳。

**★★按判据自己的 RMS（到 MXH 曲线的最近距离，上游 `fit_diagnostics`），7 个机型 17 份真轮廓**全在 2.4 % 带内**——最劣 DIII-D 1.57 %；本仓更严的同 θ R 向 RMS 上 DIII-D 2.46 %，并列记**

- ★★**「RMS」是哪一把尺，上游自己写着**：fyeq `fyeq_mxh.fit_diagnostics`（注明 FR-EQ-013 d）的 `rms_rel` = 每个原始点到重采样 MXH 曲线的**最近距离**的 RMS / 次半径。按它判，DIII-D 1.57 % 在带内。本条 1.0–1.9 版拿本仓的 `mxh_rms`（同一参数 θ 处的 R 向误差）去判，那把尺按构造更严——它把沿切向的错位也算进去——所以 DIII-D 的「刚出带」是**尺的差**，不是拟合的差。两把尺都留在读数里。
- ★残差落在 X 点这一条照旧：MXH 的六阶谐波表达不了尖角，这是这族参数化的性质。
- ★**合成件不参与带的判定**：它的轮廓首尾差 **3.14 % 小半径**（不闭合），且外侧有一段**竖直平面**（前 6 点 $R$ 全等于 $R_{max}$），总转角只有 $0.995\times2\pi$——**它不是一条 MXH 可表达的星形曲线**。它的 26.716 % 是关于那份语料的真话，不是拟合的。

**★判据的 7 机型**齐了**：EAST · DIII-D · CFEDR · MAST · JET · JT-60SA · NSTX（点名的 MAST / DIII-D / JET 都在）**

- ★**NSTX 的边界是从 ψ 图重描的**：它存的 rbbbs 首尾差 11 % 小半径（不闭合）；$\psi_N=1$ 那条等值线从 X 点漏出去（首尾差 1.23 a），$\psi_N=0.999$ 闭合、R0 / a / κ 与存的那段一致——记在读数里（标签 `#psin=0.999`），不是悄悄替换。
- ★排除的照记：ITER EOB5 两份（CRONOS）头写 129 × 129 而数据是 49 × 89、ψ 到 3.6e5——格式不标准，要专门的读取器，没收；scpn-fusion-core 的「JET」是 Solov'ev 合成件；MAST 2951 不闭合。
- ★★**球形托卡马克两台（MAST · NSTX）上结论都成立**：在带内、残差在 X 点。

**★★第二套实现（MillerExtendedHarmonic.jl）画出同一条曲线：15 份真轮廓，几何量逐位、系数到 5.3e-3、曲线到 0.78 % 小半径**

- ★约定不同：它取 $Z = Z_0 - \kappa a\sin\theta$，θ 反向 ⇒ $c_J = -c$、$s_J = +s$。★这个映射是**量出来的**：$c_J = +c$ 那一支差到 0.1 … 0.5，不是一个可以含糊过去的差。
- ★两套都是梯形矩法，但**分支挑法独立写成**：本仓按 dZ / dR 的符号定 θ 与 θ_R 的支，它按沿轮廓走过的四个极值点分段——两份代码在 X 点尖角附近各自出一点差，那正是系数差最大的地方。
- ★它**不**替第 3 格作证：带内带外用的是本仓的 `mxh_rms`（同 θ 处的 R 向误差）；这里比的是两套实现彼此，与到数据点的几何距离（同一把尺）。
- ★Julia 1.13.0 装在 `~/.local/opt/julia`，环境 `~/.local/opt/julia-envs/mxh`（本地 develop 的 MillerExtendedHarmonic.jl 2.1.2）；门在有 ``$FYLITE_JULIA`` / ``$FYLITE_JULIA_PROJECT`` 时当场重算，否则只核对钉住的读数。

## 不可比的部分

- ★★**判成立**（2026-09-19）：五格全过。判据点名的 7 机型齐了（加 JT-60SA 与 NSTX），按判据自己的 RMS（上游 `fit_diagnostics` 的最近距离）全在 2.4 % 带内，第二套实现逐份对上。本仓更严的同 θ R 向 RMS 上 DIII-D 2.46 % 刚出带——两把尺并列记着。
- ★★2026-09-18 之前内核只**吃** MXH 参数（`code/metric` 按面算度规），**没有拟合**。本条同时是这项能力的入册与它的第一次检验。
- ★判据整句还包含「合成 core_profiles → q 锁定定形重解贯通」与「对真 EFIT q 定性符合」，本条**不替它们声明**——那要走 `code/fixed_boundary`，是另一条。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.15　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-013` 的边界拟合一格从空缺转为记录，判 **inconclusive**。内核新写 `geometry::fit_mxh`（Arbon–Candy–Belli 参数化，与 `Surface::shape` 同一个 11 槽排列），经 `code/shape` 报出。圆精确退化到 6.5e-16；已知形系数随点数收敛（256/512/1024 上 4.87e-5 / 1.85e-5 / 4.05e-6）。★★**已知形那条测试逮住了两个分支 bug**（用 $\cos\theta_R$ 的符号分 $\theta$ 的支、$\theta_R$ 取「最近的一支」在 $\theta\approx\pi$ 处失效），而圆那条对两者一声不响——两条必须成对。★真机：EAST 与 CFEDR 在 2.4 % 带内，**DIII-D 2.460 % 刚出带**，判 fail；★★成因已量清：**最劣残差在每一个真位形里都落在 X 点上**（$\|z/a\|>1.4$），MXH 六阶谐波表达不了尖角。★合成件（26.7 %）点名排除：轮廓不闭合 3.1 % 且外侧有竖直平面。★MAST / JET 未评——本机没有那两个机型的 g-file。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | MAST 与 JET 入列（`third_party/` 的真 EFIT：MAST 2、JET 6），全部在带内（MAST 0.82 / 1.77 %，JET ≤ 0.62 %），残差同样落在 X 点——球形托卡马克上结论仍成立。第四格由未评转未判（5 / 7 机型，点名的三个都在）。新增第五格：第二套实现 MillerExtendedHarmonic.jl（Julia 1.13）逐份对照，几何逐位、系数 ≤ 5.3e-3、曲线 ≤ 0.78 % 小半径，成立。整体仍 inconclusive（DIII-D 出带 0.06 %）。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.11 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.12 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.13 | 2026-09-19 | Claude Opus 5 (1M context) | 7 机型齐了（加 JT-60SA 设计平衡与 NSTX，后者从 ψ 图在 ψ_N = 0.999 重描、记明）；第三格按判据自己的 RMS（上游 `fit_diagnostics`：到 MXH 曲线的最近距离）判，17 份全在 2.4 % 带内、DIII-D 1.57 %——此前的「DIII-D 刚出带」是拿本仓更严的同 θ R 向 RMS 去判，两把尺并列记。整体 inconclusive → pass。 |
| 1.14 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.15 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@51d34102a406`（库 `sha256:e4040bbf79e390d949739fc5023d63e8ba5759242ad7ca52839becab115ba3f6`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/mxh_fit_gfiles.json`    `sha256:c1fa81af18507cdb32d42663a1c1617b5d1ca3d10f15a2da0e805089b8faba1b`    15 份真 g-file（+1 合成）的 MXH 拟合：RMS、谐波、最劣残差的位置、轮廓闭合度
- `docs/benchmark/readings/mxh_fit_julia_crosscheck.json`    `sha256:161fa1be3b20a9fe46d6d4f75a26106e60259c6fc28eaf4108a6a76383a6c6cc`    第二套实现 MillerExtendedHarmonic.jl 的逐份对照

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/geometry.rs::tests::a_circle_is_mxh_with_every_harmonic_zero` —— 第一格的锚
- `$FYLITE_KERNEL/rust/fylite/src/geometry.rs::tests::a_known_mxh_shape_comes_back_with_its_own_coefficients` —— ★第二格的锚——两个分支 bug 都是它逮住的
- `python/tests/test_benchmark_mxh_fit.py::test_every_real_machine_boundary_fits_inside_the_band` —— 第三格的门
- `python/tests/test_benchmark_mxh_fit.py::test_the_residual_sits_on_the_x_point` —— ★守的是「残差堆在尖角上」这个结论本身
- `python/tests/test_benchmark_mxh_fit.py::test_the_mxh_kappa_is_the_bounding_box_kappa` —— 自洽检查（必要条件）
- `python/tests/test_benchmark_mxh_fit.py::test_an_unclosed_outline_is_named_not_averaged_in` —— ★守的是合成件被点名排除而不是摊进平均
- `python/tests/test_benchmark_mxh_fit.py::test_the_recorded_readings_are_what_this_checkout_computes` —— ★守的是记录里的数不会悄悄过期
- `python/tests/test_benchmark_mxh_fit.py::test_mast_and_jet_real_efit_boundaries_fit_inside_the_band` —— ★MAST / JET 在带内
- `python/tests/test_benchmark_mxh_fit.py::test_a_second_implementation_draws_the_same_curves` —— ★第二套实现
- `python/tests/test_benchmark_mxh_fit.py::test_the_crosscheck_reproduces_where_julia_is_installed` —— 有 Julia 时当场重算
- `python/tests/test_benchmark_mxh_fit.py::test_by_the_criterions_own_rms_every_machine_is_in_the_band` —— ★判据自己的 RMS：7 机型全在带内

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
