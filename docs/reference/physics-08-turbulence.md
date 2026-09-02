---
title: 物理与数值 · 湍流输运 (Physics & Numerics — Turbulent Transport)
subtitle: gyrofluid.rs · closure_tables.rs · flr_tables.rs · nn.rs · bgb.rs —— TGLF 移植（局域几何、Hermite 气球基、十五矩广义本征问题、闭合与碰撞、饱和律 1/2/3、谱移与淬熄、准线性权）、神经网络代理评估器、Bohm/gyro-Bohm 混合模型
---

(phys08-intro)=
# 引言：准线性三段构造的实现 (Introduction)

〔范围〕本章详述五个模块：`gyrofluid.rs`（约 15 100 行）是 GACODE **TGLF** 的白箱翻译（`fortran/tglf/src/`，
Apache-2.0；仓根 `NOTICE` 列为派生作品），按模块头部的分期表覆盖几何（T2a）、Hermite 基与 $k_y$ 网格（T2b）、
矩阵装配（T2c）、本征求解接线（T2d）、饱和律与谱（T2e）；`closure_tables.rs` 与 `flr_tables.rs` 是由
`rust/tools/extract_closure_u.py` / `extract_flr.py` 从 `tglf_eigensolver.f90` 与 `tglf_matrix.f90` 机械抽取的
数表（"GENERATED, do not edit by hand"）；`nn.rs`（542 行）是一个**不含权重**的前馈网络评估器，权重由调用方
提供；`bgb.rs`（177 行）是 JET 混合 Bohm/gyro-Bohm 热输运模型的清洁室实现。所有路径以 `fylite_kernel` 仓为根。

〔出处姿态〕〔源码〕`gyrofluid.rs` 头部："**NOT clean room.** TGLF is GACODE (LICENSE §3.2, Apache-2.0), so this
is a white-box translation of `fortran/tglf/src/`"。**源码中没有任何 TGLF 期刊文献**；出现的文献名只有
"Hammett–Perkins parallel and Dorland–Hammett perpendicular closure coefficients"、"Waltz–Miller convention"
（$B_{\rm unit}$）、"Mercier–Luc"（度规）、"Linsker"（梯度族）、"Waltz E×B quench rule"、"Ahues–Tisseur test"
（`linalg`）。Python 侧 `gyrofluid.py` 只写 "TGLF (GACODE, Staebler et al.)"。`bgb.rs` 逐字引 Erba 等两篇；
`nn.rs` 只引软件包名。本章补一手出处并逐条标核验状态；凡源码只给 Fortran 例程名的公式，在
{ref}`phys08-sources` 列为"源码未注出处"。

〔与理论手册的分工〕准线性输运的三段构造（线性谱 × 饱和规则 × 谱求和）、"唯一自由环节是饱和规则"的分诊判据、
NN 代理的三条纪律（训练域即适用域 / 例行互校 / 不确定度随预测交付），见 SpResearch `GK-TMT-08`（跨仓）。
本章述本内核**实际实现**的每一段：哪些开关被预设钉死、哪些上游分支被拒绝、哪些常数没有文献。

〔评注〕本章的每一个数值常数都有两种来源之一：(i) 从上游 Fortran 逐字转录并对 `libtglf.so` 录得值锚定
（{numref}`tbl-p08-verify`）；(ii) 本仓自选。凡属 (i) 而上游又未注文献者，本章把"实现即定义"写明，不替上游
补一个未经核验的出处。

(phys08-units)=
# 归一、输入卡与预设 (Normalisation, the Input Deck and the Presets)

(phys08-units-norm)=
## TGLF 归一变量集 (The TGLF Normalised Variable Set)

〔源码〕物种块 `ZS, MASS, AS, TAUS, RLNS, RLTS`（可选 `VPAR, VPAR_SHEAR`）：电荷以 $e$（电子 $-1$），质量以
$m_D$，密度以 $n_e$，**温度以 $T_e$**（"TGLF normalises temperature to the ELECTRONS' while NEO normalises to
the FIRST ION's"，对照 {ref}`phys07-units`），$\mathrm{RLNS}=-a\,\dd\ln n/\dd r$、$\mathrm{RLTS}=-a\,\dd\ln T/\dd r$
（峰化剖面为正）。导出量（CGS）：

$$
c_s=\sqrt{kT_e/m_D},\qquad \rho_s=\frac{c_s}{eB_{\rm unit}/(m_Dc)},\qquad
\beta_{\rm unit}=\frac{8\pi p_{\rm tot}}{B_{\rm unit}^2},\qquad
\beta_{e,\rm unit}=\beta_{\rm unit}\frac{n_ekT_e}{p_{\rm tot}}
$$ (eq-p08-norm)

局域输入 `Q_PRIME_LOC` $=(q/\hat r)^2 s$、`P_PRIME_LOC` $=(q/\hat r)(\beta_{\rm unit}/8\pi)(-a\,\dd\ln p/\dd r)$、
`DEBYE` $=7.43\times10^2\sqrt{T_e/n_e}/\abs{\rho_s}$、`XNUE` $=\nu_e a/c_s$、`SIGN_BT` $=-\mathrm{sign}\,B$、
`SIGN_IT` $=-\mathrm{sign}\,B\cdot\mathrm{sign}\,q$ 的装配在 `mapping.rs`（{ref}`phys04-mapping-tglf`）。

〔源码〕**$B_{\rm unit}$**：`miller_geo` 令 `b_unit = 1/grad_r(0)`，但 "if `drmindx == 1.0` → `b_unit = 1.0`
(Waltz–Miller convention)"——`DRMINDX_LOC` 默认 1.0，故库内计算全部在 $B_{\rm unit}=1$ 的单位中进行；
物理场强通过 {ref}`phys04-bunit` 的 $B_{\rm unit}=\frac{q}{r}\pdv{\psi}{r}$ 进入归一层。〔已确立〕
$B_{\rm unit}$ 与"有效场"约定出自 Waltz–Miller {cite}`waltz1999shape`；Miller 局域平衡出自
{cite}`miller1998noncircular`。

〔gyro-Bohm 单位〕〔源码〕`bundle::gyrobohm`（"Computed in CGS like upstream"）：
$\chi_{gB}=\rho_s^2c_s/a$、$\Gamma_{gB}=n_ec_s\rho_\ast^2$、$Q_{gB}=n_ekT_ec_s\rho_\ast^2$、
$\Pi_{gB}=n_ekT_ea\rho_\ast^2$、$S_{gB}=n_ekT_e(c_s/a)\rho_\ast^2$，$\rho_\ast=\rho_s/a$，$a$ 为最外闭合面的小半径，
质量取氘（{ref}`phys04-bundle`）。〔已确立〕gyro-Bohm 标度 {cite}`waltz1997glf23,staebler2007tglf`。

(phys08-units-presets)=
## 库内预设与拒绝码 (Library Presets and Refusals)

〔源码〕`input_presets(sat_rule, nbasis_max, vpar_model)` 复现 `tglf_startup.f90` 中**不可关闭**的
`USE_PRESETS = .TRUE.`（"a local variable, not an input, and nothing can turn it off"）：
`SAT_RULE` 0/1 → `XNU_MODEL = 2, WDIA_TRAPPED = 0`；`SAT_RULE` 2/3 → `XNU_MODEL = 3, WDIA_TRAPPED = 1`。
单位预设 `gyro_units = sat_rule < 2`（"forces CGYRO for rules 2 and 3 and GYRO for rule 0, and leaves rule 1
at the caller's (default GYRO)"）；宿主拒绝与预设不合的 `UNITS`。

〔源码·拒绝〕`Err(-51)` `sat_rule ∉ 0..3`；`Err(-52)` `nbasis_max < 2` 或为奇数（上游把奇数**向下**取整，
"honouring an odd basis lands 68 % away at 3 and 47 % at 5, against 1e-15 agreement at 2, 4 and 6"）；
`Err(-53)` `vpar_model != 0`（`VPAR_MODEL` 在库内**惰性**，`tglf_inout.f90:389` "depreciated input switch"）。
拒绝优于静默重解释——这是本移植贯穿的姿态（{ref}`phys08-limits`）。

〔源码·默认卡〕Python `_MILLER_DEFAULTS` 与标量默认列于 {numref}`tbl-p08-deck`；`NMODES` 默认 **1**
（"Upstream's own default is **two**"），`SAT_RULE` 为参数且须与卡一致。

:::{table} 输入卡默认值（`scenario/model/gyrofluid.py`，2026-09-02 快照）。
:name: tbl-p08-deck
:align: left

| 组 | 键与默认 |
| :--- | :--- |
| Miller | `RMIN_LOC 0.5, RMAJ_LOC 3.0, ZMAJ_LOC 0, Q_LOC 2.0, KAPPA_LOC 1.0, S_KAPPA_LOC 0, DELTA_LOC 0, S_DELTA_LOC 0, ZETA_LOC 0, S_ZETA_LOC 0, DRMAJDX_LOC 0, DZMAJDX_LOC 0, DRMINDX_LOC 1.0, MS 128` |
| 平衡标量 | `P_PRIME_LOC 0, Q_PRIME_LOC 16, KX0_LOC 0, USE_MHD_RULE 1, WD_ZERO 0.1` |
| 基与网格 | `NBASIS_MAX 4, NXGRID 16, WIDTH 1.65（搜索时）, KYGRID_MODEL 1, NKY 12, USE_AVE_ION_GRID 0` |
| 碰撞 | `XNUE 0, ZEFF 1, XNU_FACTOR 1, PARK 1, THETA_TRAPPED 0.7, XNU_MODEL/WDIA_TRAPPED 由预设` |
| 电磁 | `BETAE 0, USE_BPER 0, USE_BPAR 0, DAMP_PSI 0, DAMP_SIG 0, DEBYE 0, DEBYE_FACTOR 1` |
| 旋转 | `VPAR_MODEL 0, ALPHA_MACH 0, ALPHA_P 1, VEXB_SHEAR 0, ALPHA_E 1, ALPHA_QUENCH 0, SIGN_BT 1, SIGN_IT 1` |
| 饱和 | `RLNP_CUTOFF 18, LINSKER_FACTOR 0` |
| 宽度搜索 | `WIDTH_MIN 0.3, NWIDTH 21, USE_BISECTION 1, NBASIS_MIN 2, NMODES 1` |
:::

(phys08-geometry)=
# 局域几何 (Local Geometry)

(phys08-geometry-miller)=
## Miller / MXH 参数化 (The Miller–MXH Surface)

〔源码〕`miller_geo`（上游 `miller_geo`，`GEOMETRY_FLAG = 1`）以 TGLF 的扩展 Miller 布局：

$$
\arg R(\theta)=\theta+c_0+\sin^{-1}\!\delta\,\sin\theta-\zeta\sin2\theta+\sum_{k=1}^{6}c_k\cos k\theta+\sum_{n=3}^{6}s_n\sin n\theta,
\qquad R=R_{\rm maj}+r\cos(\arg R),\quad Z=Z_{\rm maj}+\kappa r\sin\theta
$$ (eq-p08-mxh)

（"`sin1 = asin(delta)`, `sin2 = -zeta`"）。$\theta_0$ 为 `argR = 0` 的 Newton 根（容差 $10^{-12}$，$\le20$ 步，
导数为零 → `Err(-11)`）；弧长以 `mts = 5` 子步梯形走出，网格在**弧长**上均匀（`ds = L/ms`），闭合误差线性摊回
（"the source's correction"）；`rmin < 1e-5` 钳到 $10^{-5}$，`ms < 4` → `Err(-12)`。度规
$R_r=\dd R_{\rm maj}/\dd x+\mathrm{drmindx}\cos a-\sin a\,(\arg R)_r\,\mathrm{drmindx}$、
$Z_r=\dd Z_{\rm maj}/\dd x+\kappa\sin\theta\,\mathrm{drmindx}(1+s_\kappa)$、$\abs{\nabla r}=\abs{l_\theta/\det}$、
$B_p=\frac{r}{qR}\abs{\nabla r}B_{\rm unit}$。

〔已确立〕{eq}`eq-p08-mxh` 中 $\delta,\zeta$ 项是 Miller 参数化 {cite}`miller1998noncircular`，$c_k,s_n$ 是
MXH 推广 {cite}`arbon2021mxh`。与 `geometry.rs` 的 GEO 移植（{ref}`phys04-geo`）共享同一族，但 TGLF 的
`ms`/`mts` 弧长走法与 GEO 的 $\theta$ 网格不同——两者各自锚定，不互相替代。

(phys08-geometry-ml)=
## Mercier–Luc 度规与 Mercier 指数 (The Mercier–Luc Metric)

〔源码〕`mercier_luc`（`ms < 8` → `Err(-13)`；五点周期导数）：$s_p=\sqrt{R_s^2+Z_s^2}$，
$r_{\rm curv}=s_p^3/(R_sZ_{ss}-Z_sR_{ss})$，$\sin u=-Z_s/s_p$，$\psi_x=RB_p$，
$f=RB_t=2\pi q\big/\oint s_p\,\dd s/(R\psi_x)$；三条累积积分（$\dd q_m=\dd s\,s_pf/(R\psi_x^2)$）
$\dd d_0=-\dd q(2/r_{\rm curv}+2\sin u/R)$、$\dd d_p=\dd q\,4\pi R/B_p$、$\dd d_{ffp}=\dd q\,(R/B_p)(B/f)^2$ 给出

$$
FF'=\frac{2\pi q'-d_0(ms)-d_p(ms)\,p'}{d_{ffp}(ms)},\qquad
S'(m)=-\big(d_0+d_pp'+d_{ffp}FF'\big)
$$ (eq-p08-ffprime)

以及 $pk=2B_p/B$、$qrat=(r/R)(B/B_p)/q$、$kx\_factor=\psi_x^2/B$、$\epsilon_l=\frac{2}{R_{\rm maj}}qrat/B$、
$\cos\theta=-R_{\rm maj}\frac{B_p}{B^2}\big(B_p/r_{\rm curv}-\frac{f^2}{B_pR^3}\sin u\big)$、
$\sin\theta=-R_{\rm maj}\frac{f}{RB^2}\frac{\dd B/\dd s}{s_p}$、
$\cos\theta_p=p_{\rm zero}R_{\rm maj}\frac{B_p}{B^2}(4\pi Rp')$。

〔源码·★〕`p_zero = 0` 当 `use_mhd_rule`——该开关在库内**默认为真**，故压强梯度对 $\cos\theta_p$ 的贡献
**通常缺席**；本移植曾处处传 `false`，实测 "0.9 % on the growth rate at `P_PRIME_LOC = -0.01`, 17 % at −0.03"。
Mercier 指数 $D_M=\tfrac14+\frac{p_M}{q_M^2}[(V''/2\pi-p_Mm_1)m_3+(f^2p_Mm_2-q_Mf)m_2]$、
$H=\frac{fp_Mq_M}{q_M^2}m_3(m_2/m_3-V'/(2\pi m_4))$、$D_R=D_M-(\tfrac12-H)^2$，$p_M=4\pi p'$、$q_M=2\pi q'$、
$q_M^2$ 下限 $10^{-12}$。

〔已确立〕$D_M$ 是 Mercier 判据 {cite}`mercier1960critere`；"Mercier–Luc" 局域度规出自 Mercier & Luc 的讲义
{cite}`mercier1974lectures`〔凭记忆〕。{eq}`eq-p08-ffprime` 是以 $q'$、$p'$ 反解 $FF'$ 的局域 Grad–Shafranov
约束——与 GEO 的同一约束（{ref}`phys04-geo-metric`）在解析上等价，在离散上不同。源码只给例程名。

(phys08-geometry-units)=
## 场线、单位与捕获份额 (Field Line, Units and the Trapped Fraction)

〔源码〕`field_line`：$y_k=y_{k-1}+s_p\,\dd s\,4/(pk_k+pk_{k-1})$，$L_y=y(ms)$，
$R_{\rm unit}=R_{\rm maj}B(0)/(qrat(0)\cos\theta(0))$，$q_{\rm unit}=L_y/(2\pi R_{\rm unit})$，
`midplane_shear = −(Ly/2π)(r/q)² · ½[S'(1)/y(1) + (S'(ms)−S'(ms−1))/(y(ms)−y(ms−1))] + 0.11`——
"The `+ 0.11` … is the source's, kept: it is an empirical offset in TGLF's shear definition"。**源码未注出处**。

〔源码〕捕获份额 `bounce_table` / `trapped_fraction_geo`（上游 `get_ft_geo`）：`nb = 25` 个场值层，每层记井的场线
长度；弹跳长度 $\min(L_y,\ \pi\theta_{\rm trapped}/k_\parallel)$，$k_\parallel=2\pi/(L_y\sqrt2\,\mathrm{width})$；
在该长度处插值 $B_{\rm bounce}$：

$$
f_t=\max\!\Big(\sqrt{\max(0,\,1-B_{\min}/B_{\rm bounce})},\ f_{t,\min}\Big)
$$ (eq-p08-ft)

"reduces to `sqrt(1 − Bmin/Bmax)` only when the bounce length covers the whole field line"。
抗磁分支（仅 `xnu_model == 3 && wdia_trapped > 0`，即 SAT_RULE 2/3）：$f_{t0}=\sqrt{1-B_{\min}/B_{\max}}$，
$cdt=\mathrm{wdia\_trapped}\cdot3(1-f_{t0}^2)$，$\omega_{\rm dia,s}=\abs{k_y\,\mathrm{rlns}_s}/v_s$，
$k_\parallel=k_{\parallel0}/\max(\theta_{\rm trapped},10^{-4})+\omega_{\rm dia}\,cdt$。

〔评注〕{eq}`eq-p08-ft` 是 TGLF 自有的"模宽度加权"捕获份额，**不是**新经典的有效捕获份额
（{ref}`phys07-averages`，{eq}`eq-p07-ft`）；两者在同一磁面上取不同值属设计，不属缺陷。锚点：参考卡
（WIDTH 1.65，THETA_TRAPPED 0.7）$f_t=0.5114019136436436$。源码未注出处。

(phys08-basis)=
# 气球角基与 x 网格 (The Ballooning Basis and the x-Grid)

(phys08-basis-hermite)=
## Gauss–Hermite 节点与 Hermite 函数 (Gauss–Hermite Nodes and Hermite Functions)

〔源码〕`gauss_hermite_nodes`（上游 `gauher`）：$n_x=2\,\mathrm{nxgrid}-1$ 个节点，关于零对称、中心节点恰为 0。
节点由 Newton 迭代（`eps = 3e-14`，`maxit = 100`）作用于**正交归一** Hermite 函数递推

$$
p_j=x\sqrt{2/j}\,p_{j-1}-\sqrt{(j-1)/j}\,p_{j-2},\qquad p_0=\pi^{-1/4},\qquad p_n'=\sqrt{2n}\,p_{n-1}
$$ (eq-p08-hermite)

得到；初值逐字保留（"they are what decides which root each iteration lands on"）：最大根
$z=\sqrt{2n+1}-1.85575(2n+1)^{-0.16667}$，其后 $z\mathrel{-}=1.14n^{0.426}/z$、$z=1.86z-0.86y_m$、
$z=1.91z-0.91y_{m-1}$、$z=2z-y_{i+2}$。权 $w=2/p_n'^2$，中心权对折。基函数 `hermite_basis`：
$h_0=\sqrt2\pi^{-1/4}$、$h_1=x\sqrt2h_0$，其余按 {eq}`eq-p08-hermite`。

〔已确立〕这是 Numerical Recipes 的 `gauher` 算法（同名、同初值常数）{cite}`press2007nr`；Hermite 函数为
气球模的展开基出自 TGLF 原始文献 {cite}`staebler2005tglf`〔凭记忆〕。源码只给上游例程名。
测试："weights sum to $\sqrt\pi/2$（measured, not assumed）"，基在求积下正交到 $10^{-10}$。

(phys08-basis-operators)=
## 算子：$k_\parallel$、模与投影 (Operators)

〔源码〕`kpar_operator`（上游 `ave_kpar`）：反对称三对角梯子 $A_{i,i+1}=\sqrt{(i+1)/2}=-A_{i+1,i}$，
位同锚定（`REF_KPAR`：$\pm0.7071067811865476,\pm1.0,\pm1.224744871391589$）。
`basis_projection(h, w, f)`（上游 `ave_theta`）：$A_{ij}=\sum_kw_kh_i(x_k)h_j(x_k)f(x_k)$，对称化，
$\abs{s}<10^{-12}$ 置零（"what keeps a matrix that should be tridiagonal from carrying 1e-17 dirt into the
eigenproblem"）。`antisymmetric_modulus(K)` $=\sqrt{K^{\mathsf T}K}$ 经实对称本征分解（上游取 $iK$ 为 Hermitian
后 ZHEEV）；`commutator(A,B)=AB-BA` 构造 `ave_gradB`。`basis_inverse`：$n=1,2$ 闭式（$2\times2$ 行列式为零时
替以 $10^{-12}$，"the source's guard, kept"），$n\ge3$ 用 Jacobi 对称本征（{ref}`phys01-linalg`）作
$M^{-1}=\sum_kv_{ik}v_{jk}/w_k$，跳过 $w_k=0$——"a pseudo-inverse in disguise"。`matrix_modulus(m, floor)`
（上游 `modwd`）把 $\abs{w_k}<\mathrm{floor}$ 推到 $\pm\mathrm{floor}$ 并返回**被钳过的**矩阵；`floor = WD_ZERO`
库默认 **0.1**（"this port passed 1e-12, so the clamp never fired"——见 {ref}`phys08-limits`）。

〔已确立〕$\sqrt{K^{\mathsf T}K}$ 经谱分解与 Jacobi 法 {cite}`golub2013matrix,jacobi1846verfahren`。

(phys08-basis-xgrid)=
## x 网格函数与气球长期项 (x-Grid Functions and the Ballooning Secularity)

〔源码〕`xgrid_functions`：$\theta_x=\mathrm{width}\cdot x$ 折入一个极向周期：`loops = trunc(|θx|/2π)`，
负 $\theta$ 反射；气球长期项 $dk=\mathrm{sign}(\theta)\cdot\mathrm{loops}\cdot S'(ms)$ 加到局域剪切上
（"that term IS the ballooning secularity, and dropping it would turn an extended mode into a periodic one"）：

$$
k_x(k)=kx\_factor_k\,(S'_k+dk)-k_{x0}\,B_k/qrat_k^2,\qquad
w_{dx}=\frac{R_{\rm unit}}{R_{\rm maj}}\Big[\frac{qrat}{B}\big(\cos\theta_{\rm geo}+k_x\sin\theta_{\rm geo}\big)\Big]_{\rm lerp}
$$ (eq-p08-xgrid)

$w_{dpx}=\frac{R_{\rm unit}}{R_{\rm maj}}[\frac{qrat}{B}\cos\theta_{p,\rm geo}]$、$b_{2x}=B^2$、
$b_{0x}=(1+k_x^2)qrat^2$（为负时取括弧均值，"the source's guard"）、`cx_tor_par = sign_Bt·(f/B)`、
`cx_tor_per = −RB_p/B`、`cx_par_par = B`。`sign_bt` 只翻 `kxx` 与 `cx_tor_par`。

〔已确立〕沿场线的气球表示与曲率漂移 $\omega_d\propto\cos\theta+\hat s\theta\sin\theta$ 的形状是
气球模理论的标准结果 {cite}`connor1978shear`；具体的插值与折返细节为 TGLF 实现。

(phys08-flr)=
# 有限 Larmor 半径拟合 (The FLR Fits)

〔源码〕上游 `tglf_matrix.f90` 的九个 `FLR_*` 函数（`Hn, dHp1, dHp3, dHr11, dHr13, dHr33, dHw113, dHw133, dHw333`）
**不是 Bessel 函数**，而是 FLR 参数 $b$ 的 13 项有理拟合，系数在捕获份额上插值：13 个基函数以节点
`Y_KNOTS` $=[0.25,0.5,0.75,1,1.5,2,2.5,3,4,6,9,15,24]$：

$$
h_k=\frac{b}{y_k^4+b^2}\ (k<4),\qquad h_k=\frac{b^2}{0.25\,y_k^5+b^{2.5}}\ (k\ge4),\qquad
H=\mathrm{tail}(f_t)\Big[h_0+\sum_{k=0}^{12}\big(a_{ik}+(a_{jk}-a_{ik})\Delta g\big)h_k\Big]
$$ (eq-p08-flr)

插值变量 $g_t=\min(\sqrt{1-f_t},0.995)$，`G_KNOTS` 40 个（0, 0.05, 0.075…0.975 步 0.025, 0.995；**非均匀**，
前两点按上游 `INT(gt/0.025)` 特判）；**只有 `Hn` 有常数项** $h_0=1/(1+b)$，八个 `dH*` 的 $h_0=0$
（"The extractor's premise … was wrong, and this port evaluated all nine with `Hn`'s constant for as long as
that premise stood"）；尾因子 `Hn, dHp3` → $f_t$；`dHp1` → $f_t^3$；`dHr11` → $3f_t^5$；`dHr13` → $\tfrac53f_t^3$；
`dHr33` → $\tfrac53f_t$；`dHw113` → $7f_t^5$；`dHw133` → $\tfrac{35}9f_t^3$；`dHw333` → $\tfrac{35}9f_t$。
每物种 $b_s=\tau_sm_s(k_y/z_s)^2$，$b(x)=b_s\,b_{0x}(x)/b_{2x}(x)$。

〔源码〕通行族在 `fth = 1` 处求值（"the source's `fth`, which is not the surface's trapped fraction"）并重组：
`hp1 = hn`，`hp3 = dHp3 + hn`，`hr11 = 3 hp1`，`hr13 = dHr13 + (5/3) hp1`，`hr33 = dHr33 + (5/3) hp3`，
`hw113 = dHw113 + (7/3) hr11`，`hw133 = dHw133 + (7/3) hr13`，`hw333 = dHw333 + (7/3) hr33`；
捕获族在磁面的 $f_t$ 处求值，带 $f_t^2$ 权：`gp1 = dHp1 + ft² gn`，`gr11 = dHr11 + 3 ft² gp1`，其余同形。
`moment_matrices` 为各网格函数的基投影，`moment_ratios`：$t_1=p_1n^{-1}$、$t_3=p_3n^{-1}$、
$u_1=r_{11}p_1^{-1}$、$u_3=r_{13}p_1^{-1}$、$u_{33}=r_{33}p_3^{-1}$。

〔评注〕这些拟合替代的是 gyro-Landau-fluid 理论中的 $\Gamma_0(b)=I_0(b)e^{-b}$ 及其导数（〔已确立〕
{cite}`dorland1993gyrofluid`〔凭记忆〕）；$3,\tfrac53,\tfrac73$ 等系数是 Maxwell 分布速度矩的比值。
拟合形式、40×13 系数表与尾因子**源码未注出处**；锚点为 libtglf 的九个矩值（$10^{-6}$）与比值（$10^{-10}$），
例：离子 `hn(0,0) = 0.8683020169793293`，`hr13(0,0) = 1.3716657843304656`。

(phys08-moments)=
# 十五矩广义本征问题 (The Fifteen-Moment Generalised Eigenproblem)

(phys08-moments-layout)=
## 布局、场与极化 (Layout, Fields and Polarisation)

〔源码〕广义问题 $A\vb x=\omega B\vb x$（上游 `tglf_LS` / `tglf_eigensolver`）。每物种 `nroot` 条带、每条带
`nbasis` 个基函数：`dim = n_species·nroot·nbasis`，`index(s, m, b) = s·nroot·nbasis + m·nbasis + b`。
**`nroot = 15`**（"`NO_TRAPPED` is never set anywhere in the source, so `nroot` is always 15"）；典型
$n=2\cdot15\cdot4=120$、NBASIS 6 时 180。矩带：0 $n$，1 $u_\parallel$，2 $p_\parallel$，3 $p_{\rm tot}$，
4 $q_\parallel$，5 $q_{\rm tot}$；6–11 捕获（g）对应项；12–14 "the trapped moments' response partition"
（$n,p_\parallel,p_{\rm tot}$）。场：$\phi$（静电，恒有）、$\psi=A_\parallel$（`USE_BPER`）、$B_\parallel$（`USE_BPAR`）。

〔源码〕极化 $pol=\sum_sz_s^2a_s/\tau_s$，$p_{0x}=\mathrm{debye\_factor}\cdot b_{0x}(k_y\lambda_D)^2+pol$；
`ave_p0inv` 从**右**除每个矩（`ave_hnp0 = ave_hn·ave_p0inv`）。DEBYE 项 "at `ky = 26` it is **4.6**, larger
than the polarization itself"。锚点：氢卡 `ave_p0 = 2I`。〔已确立〕$k_y^2\lambda_D^2$ 修正是准中性方程的 Debye
屏蔽项 {cite}`staebler2007tglf`。

(phys08-moments-rows)=
## 矩方程行 (The Moment Rows)

〔源码〕每行 `a[ia,ja] += …`，`b[ia,ja] += …`，$\xi=i$；$\delta_{ab}$ 指同物种且同基函数；每行把
`phi_A` 写到列 0、`−phi_A` 到列 6、`+phi_A` 到列 12（"one physical response split three ways"）。
标量（`ModeScalars`，"Named as the source names them"）：$k_{\parallel0}=1/(R_{\rm unit}q_{\rm unit}\,\mathrm{width})$，
$w_{d0}=k_y/R_{\rm unit}$，$w_s=-k_y/B_{\rm unit}$，$w_{d1}=-w_{d0}$，$w_{cd}=-w_{d0}$，$am=1$，$bm=0$；
跨物种块（`is ≠ js`）**$w_{d1}=0$、$k_{\parallel1}=0$**——"the mechanism by which the drift and streaming terms
are species-local while the electrostatic drive is not"。物种辅助量 $E_i=z_s/\tau_s$、$M_i=z_sv_s/\tau_s$、
$N_j=z_ja_j$、$J_j=z_ja_jv_j$。密度行（`density_row`）作为范式：

$$
\begin{aligned}
\phi_A&=i\,N_j\,w_s\big[\mathrm{rlns}\,h_n+\tfrac32\mathrm{rlts}(h_{p3}-h_n)\big],\qquad \phi_B=-h_nE_iN_j,\\
A_{00}&\mathrel{+}=\phi_A,\quad B_{00}\mathrel{+}=\delta_{ab}+\phi_B,\quad
A_{01}\mathrel{+}=-k_\parallel v_s+am\,\nabla_B v_s,\quad
A_{02}\mathrel{-}=\tfrac12 i\,w_{dh}\tau/z,\quad A_{03}\mathrel{-}=\tfrac32 i\,w_{dh}\tau/z .
\end{aligned}
$$ (eq-p08-density-row)

其余十四行同构，差别在驱动矩、drift 权（$\tfrac12/\tfrac32$）、镜像权（$am$、$am+bm$、$1.5\,bm$、$3\,bm$、$4.5\,bm$）、
Landau 阻尼项的位置与捕获族的 $f_t$ 幂（{numref}`tbl-p08-rows`）。捕获行 6–11 的列 1–5 **为空**
（"Trapped particles do not stream"）；行 8/9 的阻尼落在**捕获密度**列 6 而非列 0。
gyro-Landau 阻尼辅助 `landau(coeff, τ, z, w_d1, X, Y)` $=coeff\cdot\tau_s\big(\frac{\abs{w_{d1}}X}{\abs{z_s}}
+i\frac{w_{d1}Y}{z_s}\big)$——"the dissipative part rides on the MODULUS of the drift and of the charge, the
reactive part keeps both signs"；`coeff` 在压强行为 2，热流行为 1。

:::{table} 十五矩行的结构（列号为矩带；`φ` 列指 0/6/12 三列的分裂写入）。
:name: tbl-p08-rows
:align: left

| 行 | 矩 | 驱动 `phi_A` | 流动/镜像列 | drift 列（权） | 阻尼通道 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | $n$ | $\mathrm{rlns}\,h_n+\tfrac32\mathrm{rlts}(h_{p3}-h_n)$ | 1（$-k_\parallel+am\nabla_B$） | 2, 3（½, 3⁄2） | — |
| 1 | $u_\parallel$ | $\mathrm{vpar\_shear}\,h_{p1}/v_s$ | 2（$-(k_\parallel-k_{\parallel1}\nabla h_{p1p1})$）, 3（$1.5\,bm$） | 4, 5 | — |
| 2 | $p_\parallel$ | $\mathrm{rlns}\,h_{p1}+\tfrac32\mathrm{rlts}(h_{r13}-h_{p1})$ | 1（$k_{\parallel1}\nabla h_{u1}$）, 4（$am+bm$）, 5（$3\,bm$） | 2（$\tfrac12wdh_{u1}+\tfrac32wdh_{u3}$） | hv1, hv2 |
| 3 | $p_\perp$ | $\mathrm{rlns}\,h_{p3}+\tfrac32\mathrm{rlts}(h_{r33}-h_{p3})$ | 1, 5（$-k_\parallel+am\nabla_B$；列 4 空） | 2（$\tfrac12wdh_{u3}$）, 3（$\tfrac32wdh_{u33}$） | hv3, hv4 |
| 4 | $q_\parallel$ | $\mathrm{vpar\_shear}\,h_{r11}/v_s$ | 0（$k_{\parallel1}b_1$）, 1（$\abs{k_{\parallel1}}d_1u_1$）, 2, 3（$4.5\,bm$） | 4（$\abs{k_{\parallel1}}d_1$） | hv5–hv7 |
| 5 | $q_\perp$ | $\mathrm{vpar\_shear}\,h_{r13}/v_s$ | 0, 1, 2, 3 | 4（$d_{33}$）, 5（$d_3$） | hv8–hv10 |
| 6–11 | 捕获 $n,u,p_\parallel,p_\perp,q_\parallel,q_\perp$ | 同上以 $g$ 矩 | 列 1–5 空；列 7–11 | $w_{dg}$ 代 $w_{dh}$ | gu1–gu10（落列 6） |
| 12–14 | 分区 $n,p_\parallel,p_\perp$ | 同 6/8/9 | — | 13, 14 | gu1–gu4 |
:::

〔源码·未转录〕`d_11·k_par·vs·c06`、`c08`、`c07` 项："Both `c06` and `c08` are set to `0.0` at the top of the
source"，未移植。`grad_hu1 = grad_hu3 = 0`（"assigned `0.0` and never reassigned"）。

〔已确立〕六矩 gyro-Landau-fluid 方程组（$n,u_\parallel,p_\parallel,p_\perp,q_\parallel,q_\perp$）及其捕获/通行分解
出自 TGLF 原始文献 {cite}`staebler2005tglf`〔凭记忆〕，其前身为 GLF23 的 gyro-Landau-fluid 方程
{cite}`waltz1997glf23`；行系数的**逐项**数值（drift 权、镜像权、$f_t$ 幂）**源码未注出处**，以
libtglf 的端到端锚点（$\gamma=0.3241554304484416$，$\omega=-0.1833585734120647$，1 % / 2 %）为证。

(phys08-moments-closure)=
## 闭合：Hammett–Perkins / Dorland–Hammett 与环向通道 (Closures)

〔源码〕`ClosureCoefficients`——"The Hammett–Perkins parallel and Dorland–Hammett perpendicular closure
coefficients. Closed form in the source"：

$$
b_1=3+\frac{32-9\pi}{3\pi-8}=5.61490998617076,\qquad d_1=\frac{2\sqrt{2\pi}}{3\pi-8}=3.5186230327108974,\qquad
b_3=1,\quad d_3=\frac{\sqrt{2\pi}}{2},\quad b_{33}=\frac{b_1-b_3}{3},\quad d_{33}=\frac{d_1-d_3}{3}
$$ (eq-p08-closure)

进入 `kpar_hb1 = b1·kpar_eff`、`modkpar_hd1 = d1·modkpar_eff` 等（{numref}`tbl-p08-rows` 的 $b_\ast,d_\ast$）；
捕获族按行读出的 $f_t$ 幂：`kpar_gb1 = ft² b1`、`kpar_gb3 = ft² b3`、**`kpar_gb33 = b33`（无 $f_t$）**、
`modkpar_gd1 = ft d1`、`modkpar_gd3 = ft d3`、**`modkpar_gd33 = d33/ft`**。

〔已确立〕平行 Landau 阻尼的三/四矩闭合（以 $\abs{k_\parallel}v_t$ 乘实系数替代 Landau 共振的 Padé 近似）出自
{cite}`hammett1990fluid`〔凭记忆〕；环向（$\omega_d$）闭合与 FLR 推广出自 {cite}`dorland1993gyrofluid`〔凭记忆〕。
{eq}`eq-p08-closure` 中 $\frac{32-9\pi}{3\pi-8}$、$\frac{2\sqrt{2\pi}}{3\pi-8}$ 是四矩 Hammett–Perkins 闭合的
解析系数〔凭记忆〕；本章**未**逐项比对论文——标 〔未核验〕。

〔源码〕环向闭合通道：十对复数 `V`（上游 `get_v` 的 `DATA`）与 `VB`（"b" 分支），等于 `closure_tables::VM/VBM`
的 $f_t=1.00$ 行；通道 $k$ 的实部 $hv_k^r=(v^r-vb^r)\abs{w_d}+vb^r(\abs{w_d}u)C_{35}$、虚部同形以 $w_d$，
$C_{35}=3/5$，$u=h_{u3}$（通道 1,2,5,6,7）或 $h_{u33}$（3,4,8,9,10）。捕获通道 `trapped_channels(ft)` 在
`VM`/`VBM`（21×20，节点 0.00…1.00 步 0.05，840 个数）上线性插值，再按 `SCALE = [0,1,−1,0,1,0,1,0,−1,0]`
以 $f_t^{\pm2}$ 重标。**源码未注出处**（只给 `get_u`/`get_v`）。〔评注〕这些数表是 TGLF 作者对环向漂移共振的
数值拟合；不存在可对照的闭式。

(phys08-moments-collisions)=
## 碰撞算子 (The Collision Operator)

〔源码〕两族互斥：`xnu_*`（`xnu_model ≤ 1`，经预设**不可达**）与 `nuei_*`（`xnu_model ≥ 2`，默认）。全部碰撞项
以 $d_{ee}$（同物种、同基函数、且 `is == 0` 即电子）门控；13 行有碰撞项，行 0（$n$）与 3（$p_{\rm tot}$）无
（"collisionally conserved"）。`nuei_*` 族：$cnuei=\mathrm{xnue}$，拟合常数
`NUEI_C1 = [0.4919, 0.7535, 0.6727, 0.8055, 1.627, 2.013, 0.4972, 0.7805, 1.694, 3.103, 0×6]`
（"Sixteen slots, of which the last six are zero in every published set"），$k_a=cnuei(C1_a+Z_{\rm eff}C1_{a+1})$，
$c_{01}=\tfrac45k_4$、$c_{02}=\tfrac25k_2-k_1$、$c_{03}=\tfrac23k_1$、$c_{04}=\tfrac4{15}k_3-\tfrac43k_2+\tfrac53k_1$、
$c_{05}=\tfrac{16}{35}k_5$，随后按源码顺序累加为 $p_1p_1,u\,q_3,u\,u,q_3q_3,q_3u,q_1q_1,q_1q_3,q_1u$
（捕获版带 $f_t^2$）。捕获区振幅 `nuei_cb`：$cb_1=0.163\sqrt{k_\parallel v_{te}\,cnuei(1+0.82Z_{\rm eff})}$；
`xnu_model == 3` 时 $cb_1=\mathrm{amp}\,(k_\parallel v_{te})^{0.34}(cnuei(1+0.82Z_{\rm eff}))^{0.66}$，
$\mathrm{amp}=0.50$（`wdia_trapped == 0`）或 $0.315$；权 $a_n,a_{p3},a_{p1}=0.75,1.25,2.25$，
$b_n,b_{p3},b_{p1}=f_t,f_t,f_t^3$。捕获边界拟合 `xnu_bndry`：$\hat\nu=\mathrm{xnue}/(k_y\tau_e/R_{\rm unit})$，
默认分支 $g_s=\max(\mathrm{rlns}_eR_{\rm unit}+10.8,1.8)$，$c=g_s[1.5(1-\tanh((g_s/12.6)^2))+0.13]$，
$a=k_i[\max(0.36+0.10\,gradne,0)+c(k_i/k_{s0})(1-\tanh(k_i/0.55))]$，$b=3.1/(1+(2.1k_i+8k_i^2)\hat\nu)$，
结果 $(1-f_t^2)ab$。

〔评注〕全部为经验拟合（"Both are empirical and neither is derivable from the other"），**源码未注出处**；
其物理角色（电子–离子 pitch-angle 散射对捕获电子响应的去捕获）见 {cite}`staebler2005tglf`〔凭记忆〕。
锚点 `REF_COLLISIONAL`（SAT_RULE 0，$10^{-8}$）：(XNUE 0.05, ZEFF 1.0) $\gamma=[0.31212060903532574,0.195611528263128]$。

(phys08-moments-em)=
## 平行流、电磁项与 Linsker 梯度族 (Parallel Flow, Electromagnetic Terms, Linsker Gradients)

〔源码·平行流〕`vpar_terms`（`VPAR_MODEL = 0` 为库默认）：密度/压强行加 $N_jE_ik_{\parallel0}\,kparh_mp0\,\mathrm{vpar}$
到列 0(+)/6(−)/12(+)；速度/热流行加 $iN_jw_{cd}\,wd\,\mathrm{vpar}/v_s+d_1\,coll\,mom\,E_iN_j\mathrm{vpar}/v_s$
入 $A$、$-E_iN_j\,mom\,\mathrm{vpar}/v_s$ 入 $B$。`vpar` 为环向投影值
$\mathrm{vpar}=\alpha_{\rm mach}\,\mathrm{sign\_It}\,\mathrm{VPAR}\cdot c_{\rm tor,par}(1,1)$，
$\mathrm{vpar\_shear}=\alpha_p\,\mathrm{sign\_It}\,\mathrm{VPAR\_SHEAR}\cdot c_{\rm tor,par}(1,1)/R_{\rm maj}$
（libtglf 3.241553407313274，VPAR_SHEAR = 3）。

〔源码·电磁〕$betae_{\psi}=\frac{0.5\beta_e}{k_y^2+(damp_\psi v_{i1}/(q_{\rm unit}\mathrm{width}))^2}$（阻尼项仅
`nbasis == 2`），$betae_\sigma$ 同形；`alpha_mach_effective = 0 if use_bper`（`tglf_startup.f90:63`）；
`use_bpar && !use_bper` → `Err(-39)`（"measured libtglf returns the electrostatic answer there"，本移植拒绝）。
`USE_BPER`：密度/压强行的 $\psi_A=-i\,betae_\psi J_jw_s\,\mathrm{vpar\_shear}\,h_mb_0$ 到列 1/7；速度/热流行
$drive=\mathrm{rlns}X+\tfrac32\mathrm{rlts}(Y-X)$，$\psi_A=-i\,betae_\psi J_jv_sw_s\,drive$，$\psi_B=betae_\psi M_iJ_jX$。
`USE_BPAR`：$\sigma_A=-i\,betae_\sigma\,pre\,w_s\,drive$，$pre=a_j\tau_jz_s/m_s$，推到列
$(2,-\tfrac12),(3,\tfrac32),(8,\tfrac12),(9,-\tfrac32),(13,-\tfrac12),(14,\tfrac32)$；`bpar_moments`：
`n = 1.5n − 1.5p3`，`p1 = 2.5p1 − 1.5r13`，`p3 = 2.5p3 − 1.5r33`，`r13 = 3.5r13 − 1.5w133`，`r33 = 3.5r33 − 1.5w333`。
上游 "rows 12–14 assign psi_A/psi_B and never place them"——死代码未移植。

〔源码·Linsker〕`gp1 = kpar·p1 − p1·kpar`（**对易子**），`gr11 = u1·gp1`，`gr13 = u3·gp1`，除以 $p_1$；
以 `0.5·LINSKER_FACTOR` 装入 `grad_hp1p1` 等；`LINSKER_FACTOR` 默认 0。〔已确立〕Linsker 的积分方程形式
{cite}`linsker1981integral`〔凭记忆〕；源码只给姓名。

〔已确立〕$A_\parallel$ 与 $B_\parallel$ 的电磁 gyro-fluid 推广 {cite}`staebler2007tglf`；
$\beta_e$ 的 $0.5\beta_e/k_y^2$ 形式是 Ampère 定律在 gyro-Bohm 归一下的系数〔未核验〕。

(phys08-eigen)=
# 本征求解与高频滤波 (The Eigen-Solve and the High-Frequency Filter)

〔源码〕`linalg::lu_solve`（复 LU、部分主元，"the `zgesv` role"）给出 $B^{-1}A$；`linalg::eigen`（"the `zgeev` role"，
{ref}`phys01-linalg`）：平衡 → Householder Hessenberg → 单移位复 QR（Wilkinson 移位取尾部 $2\times2$），每 10 个
块迭代一次例外移位 $a_{22}+\abs{h_{n-1,n-2}}$，平凡去耦 $\abs{h_{lo,lo-1}}\le\varepsilon(\abs{h_{lo-1,lo-1}}+\abs{h_{lo,lo}})$
加 LAPACK 的 Ahues–Tisseur 第二判据，30 个块迭代后停滞逃逸 $sub\le\varepsilon\norm H(iters/30)$；上限
`max_iters = 240n + 2400`（"LAPACK's `dlahqr` budgets 30 iterations per EIGENVALUE … n = 180: it fails at `100n`
and converges between `100n` and `150n`"；`Err(-1)` 未收敛）。本征向量归一到单位 2-范数。
**报告约定 $\gamma=\Re\omega$、$f=-\Im\omega$**，按最不稳定排序，取 `max_modes`。

〔源码·滤波〕`solve_dispersion_with_vectors_filtered`：排序**前**，凡 $\Re>0$ 且 $\abs{\Im}>\mathrm{max\_freq}$ 的根
令 $\Re\to-\Re$（"filter out numerical instabilities that sometimes occur with high mode frequency"，
`tglf_eigensolver.f90`）。阈值：种子 $2\abs{wdh(0,0)}/R_{\rm unit}$，提升到
$\max_s\abs{a_sz_s(hp3p0_{11}\,\mathrm{rlns}_s+1.5(hr13p0_{11}-hp3p0_{11})\mathrm{rlts}_s)}$，再乘
$\mathrm{FILTER}\cdot\abs{k_y}$，`TGLF_FILTER_DEFAULT = 2.0`（卡的 `FILTER` 未接线）。开放项 T-C35 原文：阈值
在 tglf09（BETAE 0.1，USE_BPER）过紧——上游保留 $\abs f=0.273$ 的根，本移植阈值 0.200；"The ratio is NOT constant"。

〔源码〕**只报告 $\gamma>0$ 的根**（"A DAMPED ROOT IS 'STABLE', NOT AN ANSWER"），稳定 $k_y$ 返回 0 与默认权。
Waltz 淬熄（`ALPHA_QUENCH ≠ 0`，`tglf_LS.f90:255-259`）：$\gamma\leftarrow\max(\gamma-\abs{0.3\sqrt\kappa\,
\mathrm{ALPHA\_QUENCH}\,\mathrm{VEXB\_SHEAR}},0)$，只作用于报告的 $\gamma$，不作用于准线性权。

〔已确立〕QR 算法 {cite}`francis1961qr`；平衡 {cite}`parlett1969balancing`；Hessenberg 约化
{cite}`householder1958unitary`；去耦判据 {cite}`ahues1997deflation`；LAPACK 预算 {cite}`anderson1999lapack`；
E×B 淬熄规则 $\gamma_{\rm net}=\gamma-\alpha_E\gamma_E$ 出自 {cite}`waltz1994quench,waltz1998rotational`〔凭记忆〕；
$0.3\sqrt\kappa$ 的 Miller 几何因子**源码未注出处**。

(phys08-ql)=
# 准线性权 (Quasilinear Weights)

〔源码〕`ql_moments`：十五矩下 $n=v_0-v_6+v_{12}$，$u_\parallel=v_1-v_7$，$p_\parallel=v_2-v_8+v_{13}$，
$p_{\rm tot}=v_3-v_9+v_{14}$，$q_\parallel=v_4-v_{10}$，$q_{\rm tot}=v_5-v_{11}$。场（"as `tglf_LS.f90` writes them"）：

$$
\phi=p_0^{-1}\sum_sa_sz_sn_s,\qquad \psi=betae_\psi\,b_0^{-1}\sum_sa_sz_sv_su_{\parallel s},\qquad
b_{\sigma,i}=-betae_\sigma\sum_sa_s\tau_s\big(\tfrac32p_{{\rm tot},i}-\tfrac12p_{\parallel,i}\big)
$$ (eq-p08-fields)

此处 $betae_\psi=0.5\beta_e/k_y^2$（无阻尼，"NOT `m.betae_psi`"），$betae_\sigma$ 在通量路径传 0；绝热移位
$n,p_\parallel,p_{\rm tot}\mathrel{-}=(z/\tau)\phi$。`ql_weights`（$\phi_{\rm norm}=\sum\abs{\phi_i}^2$，下限 $10^{-12}$，
$ev=f+i\gamma$）：

$$
\begin{aligned}
W^\Gamma_s&=a_sk_y\,\Re\sum_i\big[i\bar\phi_in_i-v_s\,i\bar\psi_iu_{\parallel i}+(\tau_s/z_s)\,i\,\bar b_{\sigma,i}\,pmix_i\big]/\phi_{\rm norm},\\
W^Q_s&=\tfrac32a_s\tau_sk_y\,\Re\sum_i\big[i\bar\phi_ip_{{\rm tot},i}-v_s\,i\bar\psi_iq_{{\rm tot},i}\big]/\phi_{\rm norm},\\
W^{X}_s&=a_s\,\Re\sum_i\big[z_s\,i\omega\bar\phi_in_i-z_sv_s\,i\omega\bar\psi_iu_{\parallel i}+\tau_s\overline{(-i\omega b_{\sigma,i})}\,pmix_i\big]/\phi_{\rm norm},
\end{aligned}
$$ (eq-p08-qlweights)

$pmix=\tfrac32p_{\rm tot}-\tfrac12p_\parallel$；$B_\parallel$ 项 "NOT verified against an answer"。应力权
`ql_stress_weights`（上游 `get_QL_weights`）以 `cx_par_par, cx_tor_par, cx_tor_per, kxx` 的投影构造
$w_{\rm par},w_{\rm tor}$，`stress_tor = sign_It·m_s a_s v_s ky·w_tor/phi_norm`。锚点：模 1 粒子权
$-0.02819975676791954$（两物种，双极到 $10^{-9}$），能量权 $[0.13211685127348416,0.47754366538708604]$（2 %）。

〔已确立〕准线性通量 $\propto\Re\langle\tilde\phi^\ast\tilde n\rangle$ 的权构造与 gyro-fluid 的场方程
{cite}`staebler2007tglf,waltz1997glf23`；$\tfrac32$ 能量因子为 $\tfrac32nT$ 的定义〔已确立〕。

(phys08-saturation)=
# 饱和律与谱 (Saturation Rules and the Spectrum)

(phys08-sat-kygrid)=
## $k_y$ 网格与求积 (The $k_y$ Grid and Quadrature)

〔源码〕`gyroradii`：$\rho_e=\sqrt{m_e\tau_e}/\abs{z_e}$；**`USE_AVE_ION_GRID` 默认 FALSE → $\rho_{\rm ion}$ 取第一
离子**（`tglf_startup.f90:180`；实测 tglf07 "0.644949 against 1.0"）；为真时电荷加权
$\sum za\sqrt{m\tau}/z\big/\sum za$，只计 $\abs{z_sa_s/(a_ez_e)}>0.1$ 的离子；无离子 `Err(-38)`，总电荷零 `Err(-39)`。
`ky_spectrum(model, …)`：模型 0 线性 $i\cdot k_{y,\rm in}/n_{ky}$；**模型 1（默认，"APS07"）** 9 个线性点到
$0.9\,k_f/\rho_{\rm ion}$，再 $n_{ky}$ 个对数点到 $0.4\,k_f/\rho_e$；模型 2（"IAEA08"）8 点 $0.05/\rho_{\rm ion}$ 步
加 7 点 $0.2/\rho_{\rm ion}$ 步；模型 3 以 $k_{y,\rm in}$ 步；模型 4（TRTGLF）6+6 点再对数尾。
$k_f$ = 1（GYRO）或 `grad_r0`（CGYRO），由宿主供给（缺席时 8.2 % 网格误差）。求积 `ky_quadrature`：首段
$(0,k_1)$，其后以 $d=\ln(k/k_{\rm prev})/(k-k_{\rm prev})$ 给权 $k_{\rm prev}(kd-1)$ 与 $k(1-k_{\rm prev}d)$
（"integrates a function that behaves like `1/ky` exactly"）；非增时退回中点。锚点：KYGRID 1、NKY 12 的 21 点网格
（$10^{-12}$），离子能量通量积分 $F_{\rm total}=41.64152042999882$（$10^{-9}$；线性梯形 "2% off"）。

〔评注〕多尺度（离子到电子）$k_y$ 网格的必要性见 {cite}`staebler2017nf`；具体断点 0.9/0.4/0.05/0.2 **源码未注出处**。

(phys08-sat-zonal)=
## 带状流混合搜索 (The Zonal-Flow Mixing Search)

〔源码〕`zonal_mixing`：`kycut = 0.8/rho_ion`；`kymin = 0.173·√2/rho_ion`（`alpha_zf < 0` 时）否则 0；规则 2/3
两者乘 `grad_r0`。在 `ky[j+1] ≥ kymin && ky[j] ≤ kycut` 上最大化 **$\gamma/k_y$**（非 $\gamma$），三邻点抛物线细化
（归一坐标 $x_1$，顶点 $x_{\max}=-b/2c$，肩部与越界特判）；返回 $v_{zf}=\gamma_{\max}/k_{y\max}$、$k_{y\max}$、$j_{\max}$。
锚点：$v_{zf}=1.2412272523121732$，$k_{y\max}=0.17474156381227995$（$10^{-9}$）。

〔已确立〕以 $\max(\gamma/k_y)$ 定义带状流混合率 $v_{zf}$ 是 SAT1 的核心构造 {cite}`staebler2016zonal`〔凭记忆〕；
$0.8/\rho_{\rm ion}$、$0.173\sqrt2$ **源码未注出处**。

(phys08-sat-rules)=
## SAT_RULE 1 / 2 / 3 (The Three Saturation Rules)

〔源码〕本移植实现 **SAT_RULE 1、2、3**（`flux_spectrum_inner` 拒绝 `sat_rule ∉ 1..3` → `Err(-29)`）；
"SAT_RULE 0" 只被 `input_presets` 接受用于线性求解——**代码中不存在 SAT0 饱和公式**。共用的饱和强度：

$$
\gamma_{\rm eff}=\gamma_{\rm mix}\Big(\frac{\gamma_i}{\gamma_1}\Big)^{expsub}\Big[\sqrt{k_y/k_{y,\rm etg}}\Big]_{k_y>k_{y,\rm etg}},\qquad
I_i(k_y)=measure\cdot cnorm\cdot\Big(\frac{\gamma_{\rm eff}}{kx_{\rm width}\,k_y\,(1+ay\,k_x^2)}\Big)^2
$$ (eq-p08-intensity)

（$\gamma_{\rm lin}\le10^{-12}$ 或分母为 0 时置零）。混合平均 `mixing_average`（$j\ge j_{\max}+2$，"integrates the
quenched spectrum against a Lorentzian mixing kernel, analytically over each interval"）：$s=\sqrt{cky}$，
$mixnorm=k_{y0}[\arctan(s(k_{y,n-1}/k_{y0}-1))-\arctan(s(k_{y,j_{\max}+1}/k_{y0}-1))]$，每段解析积分给
$\gamma_{\rm mix}(k_{y0})$；锚点 `REF_GMIX` 平台 $0.21689399111544852$（$10^{-6}$）。淬熄 `quench_growth_rates`：
峰下（$k_y<k_{y\max}$）规则 1 $\gamma_q=\max(\gamma-cz_1(k_{y\max}-k_y)v_{zf},0)$，规则 2/3 不变；峰上
$excess=\max(\gamma-cz_2v_{zf}k_y,0)$，规则 1 $\gamma_q=cz_2\gamma_{\max}+etg_{\rm stiff}\,excess$，规则 2/3
$\gamma_q=\gamma_{\max}+etg_{\rm stiff}\,excess$。

:::{table} 三条饱和律的常数（`SaturationConstants`；调用值 `czf = 1, etg_stiff = 1, quench_on = false`）。
:name: tbl-p08-sat
:align: left

| 量 | SAT_RULE 1 | SAT_RULE 2 | SAT_RULE 3 |
| :--- | :--- | :--- | :--- |
| `cnorm` | 14.29（"assigned three times in the source … 14.21 if only the first is read"） | $b_2\cdot12/dlnpdr$，$b_2=3.55$（$nmodes>1$）/ 3.74 | 同规则 2（$k_y>k_T$ 段） |
| `cz1, cz2` | $0.48\,czf$, $1.0\,czf$ | 0, $1.05\,czf$ | 同规则 2 |
| `cky` | 3.0 | 3.0 | 3.0 |
| `kyetg` | $etg_{\rm streamer}/\rho_{\rm ion}$（2.1 淬熄开 / 1.05） | 1000（"deliberately unreachable"） | — |
| `measure` | $\sqrt{\tau_em_i}$ | $1/k_{y\max}$ | $1/k_{y\max}$ |
| `ax, ay, exp_ax, expsub` | 1.15, 0.56, 4, 2 | 1.21, 1.0, 2, 2 | 同规则 2 |
| $kx_{\rm width}$ | $k_y$ | `sat2_kx_width`：$kycut=0.76k_{y\max}$；$w=kycut/grad_{r0}$（$k_y<kycut$），否则 $+B_1(k_y-kycut)G_q$，$B_1=1.22$ | 同规则 2 |
| 几何权 | `SAT_geo0`（CGYRO：$0.946/qrat_0$） | $d_1\,\mathrm{SAT_{geo1}}$ / $(d_1\mathrm{SAT_{geo1}}kycut+(k_y-kycut)d_2\mathrm{SAT_{geo2}})/k_y$ | 同规则 2 |
| 特有 | — | $dlnpdr=R_{\rm maj}\frac{\sum a_s\tau_s(\mathrm{rlns}+\mathrm{rlts})}{\max(\sum a_s\tau_s,0.01)}$ 钳于 $[4,\mathrm{RLNP\_CUTOFF}]$ | $k_{\min}=0.685k_{\max}$，$c_1=-2.42$，$scal=0.82$，$Y_{\rm ITG}=3.3g_{\max}^2/k_{\max}^5$，$Y_{\rm TEM}=12.7g_{\max}^2/k_{\max}^4$，模式混合阈 $x<0.8$ / $x>1.0$；拒绝 $nmodes>1$（`Err(-42)`） |
:::

〔源码·几何权〕`sat_geometry`：$\mathrm{SAT_{geo1}}=\expval{(B_0/B)^4}$，$\mathrm{SAT_{geo2}}=\expval{(qrat_0/qrat)^4}$，
权 $\dd l_p=s_p\dd s(\tfrac12/B_p(i)+\tfrac12/B_p(i-1))$；GYRO 单位下三者全为 1；$G_q=B_0/grad_{r0}$，
$d_1=(B_{t0}/B_0)^4/grad_{r0}$，$d_2=1/G_q^2$。锚点 `SAT_geo0 = 1.1153458`（规则 1 CGYRO），
`SAT_geo1 = SAT_geo2 = 0.61550634`（`out.tglf.scalar_saturation_parameters`）。

〔源码·SAT3〕$k_T=1/\rho_{\rm ion}$ 以下：$k_y\le k_P=2k_{\min}$ 时 $\sigma=(aoverb\,k_y^2+k_y+coverb)/\sigma_0$，
$aoverb=-1/(2k_{\min})$，$coverb=-0.751k_{\max}$，$k_0=0.6k_{\min}$；其上以在 $k_P$ 处值与斜率匹配的二次式连接到
$k_T$；$I=Y_s\sigma^{c_1}F_{k_y}$，$F_{k_y}=(\gamma_{\rm mix}/\gamma_{fp})^2/(1+ay\,k_x^2)^2$；$k_T$ 以上退回规则 2 形式。
锚点 `S3_Y_ITG = 648.8149557858173`、`S3_Y_TEM = 473.2040306096903`（$10^{-12}$）。

〔已确立〕SAT1 出自 {cite}`staebler2016zonal`〔凭记忆〕与多尺度推广 {cite}`staebler2017nf`；SAT2 的几何依赖出自
{cite}`staebler2021ppcf`，其对 CGYRO 的验证 {cite}`staebler2021nf`；SAT3 出自 {cite}`dudding2022sat3`〔凭记忆〕；
SAT0（未实现）见 {cite}`kinsey2008sat0`。{numref}`tbl-p08-sat` 中的**每一个数值常数源码均未注出处**；
本章未逐项比对论文——全部标 〔未核验〕。

(phys08-sat-shift)=
## 谱移、两遍方案与时间抑制 (Spectral Shift, the Two-Pass Scheme, Temporal Suppression)

〔源码〕`spectral_shift`：$\mathrm{shear}=\alpha_e\,\mathrm{VEXB\_SHEAR}$；规则 2/3
$k_{x0}=-0.32(k_y/k_{y\max})^{0.3}\,\mathrm{shear}/(k_yv_{zf})$；规则 1
$k_{x0}=-(0.53\,\mathrm{shear}/\gamma_{\rm ref}+0.25\,w_E\tanh((0.69w_E)^6))$，
$w_E=kx0_{\rm factor}\min(k_{yi}/0.3,1)\,\mathrm{shear}/\gamma_{\rm ref}$，$kx0_{\rm factor}=1+0.40(\abs{grad_{r0}^2/B_{\rm geo0}}-1)^2$
（GYRO；`tglf_geometry.f90:266-276`）；钳 $\abs{k_{x0}}\le a_0$，$a_0=1.45/1.6/1.3$（规则 1 / 2,3 / 0）。
锚点 `S_KX0`（ALPHA_E 1，VEXB_SHEAR 0.1）到 $10^{-4}$——"residual … about 9% of the `tanh` term alone … The cause
is not pinned"（{ref}`phys08-limits`）。

〔源码·两遍〕`alpha_quench == 0 && vexb_shear != 0` 时（`tglf_TM.f90:65-80`）：第一遍无剪切得 $\gamma$ 与宽度；
$k_{x0,\rm lin}=\mathrm{sign\_Bt}\,k_{x0}\cdot factor$，$factor=1$（GYRO）、$1/2.1$（规则 1 CGYRO）、
$0.7/grad_{r0}^2$（规则 2,3 CGYRO）；第二遍把 $k_{x0}$ 放进**线性**解，宽度冻结，**本征值重置为第一遍、准线性权取
第二遍**；随后时间抑制（`tglf_multiscale_spectrum.f90:245-273`）

$$
\gamma_{\rm net}=\frac{\gamma}{1+\abs{ax\,k_x}^{exp_{ax}}}
$$ (eq-p08-suppression)

规则 1 对 $\gamma_{\rm net}$ 重跑 `zonal_mixing`；规则 2/3 保留 $k_{y\max}$ 而 $v_{zf}\mathrel{\ast}=\gamma_{\rm net}[j_{\max}]/\max(\gamma[j_{\max}],10^{-10})$。

〔已确立〕谱移范式（E×B 剪切使湍流谱沿 $k_x$ 平移而非线性淬熄）出自 {cite}`staebler2013prl`；
{eq}`eq-p08-suppression` 的 $ax,exp_{ax}$ 与 $0.53/0.25/0.69/0.32$ 等**源码未注出处**。

(phys08-sat-flux)=
## 通量装配与宽度搜索 (Flux Assembly and the Width Search)

〔源码〕`flux_spectrum_inner`：第一遍 → `sat_geometry` → `zonal_mixing` → 常数 → 逐 $k_y$ 谱移 → 第二遍 → 宽度
→ $\gamma_{\rm net}$ → 淬熄 → 混合 → 强度（规则 3 走 `sat3_intensity_spectrum`）→ 几何权（`!gyro_units && sat_rule ≤ 2`）
→ 次主模以**原始 $\gamma$**（"upstream has TWO `gamma0`s … line 422"）→ 每物种通量

$$
\Gamma_s=\int\dd k_y\sum_{i=1}^{nmodes}I_i(k_y)\,W^{(i)}_s(k_y)
$$ (eq-p08-flux)

对粒子、能量、交换、`stress_tor`、`stress_par`（`integrate_over_ky`）。宽度搜索（`tglf_max.f90`）：
`WidthSearch { width_min 0.3, nwidth 21, use_bisection true, nbasis_min 2 }`；对数均匀扫描（二分时 `nt = 5`），
自顶向下、严格大者胜（"Ties go to the WIDER width"），再在括弧内二分到 $dt_{\min}=(\log_{10}w_{\max}-\log_{10}w_{\min})/(nwidth-1)$；
规则 2/3 的扫描为静电、`nbasis_min`；$\alpha_p>0$ 时下限 $w_p=\max(3.6v_s/(\sqrt2R_{\rm unit}q_{\rm unit}\max(wgp,0.001)),0.1)$。
若扫描 $\gamma_{\max}=0$ 则该 $k_y$ 置零且**不**做全解（"UPSTREAM'S STABLE BRANCH … ky = 4.26 comes back at gamma
= 1.90 against upstream's 0"）。每次最终求解都从该宽度的磁面重导 $f_t,R_{\rm unit},q_{\rm unit},B_{\rm unit}$。

〔已确立〕{eq}`eq-p08-flux` 是准线性谱求和的定义；模宽度对 $\gamma$ 的最大化是 TGLF 的试函数选取原则
{cite}`staebler2005tglf,staebler2007tglf`。宽度搜索常数 **源码未注出处**。

(phys08-nn)=
# 神经网络代理评估器 (The Neural-Network Surrogate Evaluator)

(phys08-nn-arch)=
## 一族结构，权重外置 (One Architecture, Caller-Supplied Weights)

〔源码〕`nn.rs` 评估

$$
\mathrm{Dense}(n_{\rm in}\to n_h,\sigma)\ \to\ n_{\rm hl}\times\mathrm{Dense}(n_h\to n_h,\sigma)\ \to\
n_{\rm blk}\times\big[x+\mathrm{Dense}^{\,3}_\sigma(x)\to\mathrm{Dense}(x),\ \sigma\big]\ \to\ \mathrm{Dense}(n_h\to n_{\rm out})
$$ (eq-p08-nn)

（"read off the shipped models (TGLFNN.jl, Apache-2.0, `Flux.Chain`)"）；残差块四个 Dense，前三个后接激活，
`h += t` 后再激活（"the LAST dense of a block has no activation — the sum with the skip connection does"）；
输出层线性。"No weights live here, and none are compiled into the library or the wasm."
权重布局：行主 `(out, in)` 后跟偏置；`Shape::n_weights = (n_h n_in + n_h) + (n_hl + 4 n_blk)(n_h² + n_h) + (n_out n_h + n_out)`。
激活码（C-ABI 与 `fylite.nn.ACT_CODES` 一致）：0 恒等；1 ELU $x<0?e^x-1:x$（TGLF-NN）；2 GELU（tanh 形，
$0.5x(1+\tanh(\sqrt{2/\pi}(x+0.044715x^3)))$，EPED-NN，"Flux's `gelu`"）；3 tanh（QLKNN）；4 ReLU
（UKAEA TGLF-NN——"★Their weight archive does not record an activation at all; the name comes from the upstream
loader's own default"）。

〔源码〕`ensemble(...)` 顺序：(1) 模型自带条件化 `x += x_shift; x = |x|`（EPED-NN "adds 1 to the triangularity
and takes the modulus of every input"）；(2) `log10_mask` 取 $\log_{10}$（$x\le0$ **拒绝**，C-ABI −3）；
(3) $x_n=(v-x_m)/x_s$（"xm/xs are applied AFTER the log"；$x_s=0$ 拒绝）；(4) 可选幂律头
$y_{0,k}=10^{c_{k0}+\sum_ic_{ki}\log_{10}x_i}$ 于**原始**输入（"EPED-NN … trains the network to CORRECT that fit"）；
(5) 每成员 $v=y_0+y\,y_s+y_m$；(6) 返回 (均值, 成员样本标准差)——"**not** a physics uncertainty … one member's
electron energy flux ranges 1.93 to 8.09 about a mean of 5.38"。**`nn.rs` 不裁剪输出、不强制训练域**；训练域检查在
Python `Surrogate.outside_training_box`（"upstream WARNS rather than refuses, so this reports and the caller decides"）。

〔已确立〕残差连接 {cite}`he2016resnet`〔凭记忆〕；ELU {cite}`clevert2016elu`〔凭记忆〕；GELU 及其 tanh 近似
{cite}`hendrycks2016gelu`；集成成员标准差作为认知不确定度的代理是深度集成的常规做法〔已确立〕，其**非**物理不确定度
的定性见 `GK-TMT-08` 第三条纪律。

(phys08-nn-models)=
## 三个装运模型 (The Three Shipped Models)

:::{table} 内核装运/服务的代理模型（`models/README.md` 与 npz 元数据，2026-09-02 快照）。
:name: tbl-p08-nn
:align: left

| 模型 | 形状 / 激活 / 成员 | 输入 → 输出 | 来源 |
| :--- | :--- | :--- | :--- |
| `sat2_em_d3d_azf-1.npz`（TGLF-NN） | 31 → 32，5 残差块 → 4；ELU；20 | 31 个 TGLF 卡键（`BETAE, DEBYE, XNUE` 取 $\log_{10}$）→ `OUT_G_elec, OUT_P_ions, OUT_Q_elec, OUT_Q_ions`（gyro-Bohm） | TGLFNN.jl 1.7.1 `sat2_em_d3d_azf-1.bson`，DIII-D SAT2 EM 训练 {cite}`neiser2022tglfnn,tglfnn_jl` |
| `qlknn_7_11.npz`（QLKNN_7_11） | 10 → 133×5 → 8；tanh；1 | `Ati, Ate, Ane, Ani, q, smag, x, Ti_Te, LogNuStar, normni` → `itgleading, itgqediv, temleading, temqidiv, tempfediv, etgleading, itgpfediv, gamma_max` | fusion_surrogates `11D` 归档 {cite}`vandeplassche2020qlknn,fusion_surrogates`；权重 float32 精确 |
| `epednn.npz`（EPED1-NN） | 10 → 32×2 → 18；GELU；1；幂律头 18×11 | `a, betan, bt, delta, ip, kappa, m, neped, r, zeffped`（`x_shift` 于 δ，全 `abs`）→ 9 压强 + 9 宽度 | EPEDNN.jl `delta_ne_sqrt_power` {cite}`meneghini2017epednn,epednn_jl` |
:::

〔源码〕QLKNN 组合（`FLUX_MAP`，上游 `config.flux_map`）：`efiITG = max(itgleading, 0)`，
`efeITG = itgqediv·max(itgleading, 0)`，…，`efe = itg·efeITG + tem·efeTEM + etg·etg_correction·efeETG`
（`etg_correction` 默认 **1.0**，"TORAX defaults to 1/3"），`efi = itg·efiITG + tem·efiTEM`，`pfe`（仅电子粒子通量）；
可选 `clip_inputs`（TORAX 口径，边距 0.95），默认关。训练域 `xbounds`：`Ati, Ate` $[10^{-14},150]$、`Ane` $[-5,110]$、
`Ani` $[-15,110]$、`q` $[0.66,30]$、`smag` $[-1,40]$、`x` $[0.1,0.95]$、`Ti_Te` $[0.25,2.5]$、
`LogNuStar` $[-5.0003,0.4768]$、`normni` $[0.5,1.0]$。UKAEA TGLF-NN（LGPL，**不装运**，"call it, do not vendor it"）：
每通量 5 成员 `13 → 512×5 → 2`，ReLU，第二输出为 "PRE-SOFTPLUS variance parameter" 原样导出并拒绝作方差；
**无训练域**（`xbounds = ±inf`，"an ABSENCE of a guard"）{cite}`zanisi2025tglfnn`。编译进内核的 EPED1-NN
（`pedestal.rs::eped1nn`）见 {ref}`phys11-pedestal`。

〔已确立〕QLKNN-10D 的通量分解与 `leading/div` 输出约定 {cite}`vandeplassche2020qlknn`；QuaLiKiz 本体
{cite}`bourdelle2016qualikiz`；TORAX 的组合口径 {cite}`citrin2024torax`。锚点：QLKNN "1.63e-13 against upstream's own
shipped test vectors"；UKAEA "2.19e-15 against an independent numpy forward pass"。

(phys08-bgb)=
# Bohm / gyro-Bohm 混合模型 (The Mixed Bohm/gyro-Bohm Model)

〔源码〕`bgb.rs`（"literature clean room"）：

$$
\begin{aligned}
\chi_B&=\alpha_B\,a\,q^2\,\frac{\abs{\dd(n_eT_e)/\dd\rho}}{n_eB_0}\,\Delta_{\rm edge},\qquad
\chi_{gB}=\alpha_{gB}\,\sqrt{T_e}\,\frac{\abs{\dd T_e/\dd\rho}}{B_0^2},\qquad
\Delta_{\rm edge}=\max\!\Big(\frac{T_e(0.8a)-T_e(a)}{T_e(a)},0\Big),\\
\chi_e&=\alpha_{eB}\chi_B+\alpha_{egB}\chi_{gB},\qquad \chi_i=\alpha_{iB}\chi_B+\alpha_{igB}\chi_{gB}
\end{aligned}
$$ (eq-p08-bgb)

（$T_e$ eV、$B$ T、长度 m——"`eV/T` is `m²/s` exactly, so the alphas are dimensionless"）。梯度为非均匀中心差分
（`numpy.gradient` 公式 $g_i=[y_{i+1}h_1^2-y_{i-1}h_2^2+y_i(h_2^2-h_1^2)]/(h_1h_2(h_1+h_2))$，端点单侧
{cite}`harris2020array`）；$T_e(0.8a)$ 线性插值；`n < 3`、长度不齐或 $B_0=0$ → 全 NaN。

〔源码·★系数来源——测得，非转引〕`ALPHA_E_BOHM = 5.46e-5`、`ALPHA_I_BOHM = 1.092e-4`（恰两倍）：
"frozen against the recorded per-face Bohm column (`XE2`/`XI2`) of JINTRAC job 101612 (JET #58894) — DATA, no
JETTO source read … flat per face to ±0.5 % across all three time slices … `XI2/XE2 = 2.0000` identically"；
gyro-Bohm 通道在该运行中**无 oracle**（`XE3 ≡ 0`），`ALPHA_E_GB = 5.0e-6`、`ALPHA_I_GB = 2.5e-6` "carry the
literature values … and are marked so"。"★The flux label is part of the contract"：拟合在 JETTO 的 $\rho$ 标签下精确，
换中平面小半径则 "30–40 % mid-to-edge shape deviation"。

〔已确立〕JET 混合 Bohm/gyro-Bohm 模型 {cite}`erba1997bgb`〔凭记忆〕，非局域边缘因子 $\Delta_{\rm edge}$
{cite}`erba1998bgb`〔凭记忆〕——两者为源码逐字引（期刊、卷、页），题名由编者补出。〔未核验〕文献中的 gyro-Bohm
系数是否与 $5\times10^{-6}$ 一致；Bohm 系数**不是**文献值，是对一次 JINTRAC 运行的拟合。

(phys08-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

〔源码〕本章模块的硬拒绝（负 `i32`；C-ABI 同码）：$-1$ 本征未收敛 / 空指针；$-11$…$-16$ 几何与基算子（$\theta_0$
导数为零、$ms<4$/$<8$、逆与模的尺寸）；$-17,-18$ 缓冲与奇异 $B$；$-21,-22,-24$…$-28$ 装配（nroot、物种数、
`nbasis == 1`、`vpar_model == 1`、捕获行、长度）；$-29$…$-35$ 饱和律与网格；$-37$ 几何权归一为零；$-38,-39$ 碰撞
`phi_b`、无离子、总电荷零、`USE_BPAR` 无 `USE_BPER`；$-40$…$-42$ 宽度搜索、`nmodes`、SAT3 多模；$-51$…$-53$ 预设。
`nn.rs`：$-2$ 形状/权重数/未知激活，$-3$ 对数掩码下非正输入。`bgb.rs` 以 NaN 报错。

〔评注·已知偏差与开放项〕(i) `WD_ZERO`：库默认 0.1，本移植曾传 $10^{-12}$——"the clamp never fired"；
(ii) `use_mhd_rule` 默认为真，$\cos\theta_p$ 的压强项通常缺席（0.9 %–17 % 增长率差别随 `P_PRIME_LOC`）；
(iii) 高频滤波阈值 T-C35 在 tglf09 过紧；(iv) 谱移 $10^{-4}$ 残差 "not pinned"；(v) tglf07 规则 2 残差 $5.3\times10^{-2}$、
tglf09 $1.4\times10^{-1}$ 在回归测试中**作为开放项断言**；(vi) `NMODES` 默认 1 对上游 2；(vii) SAT3 拒绝多模
（`QLA_P/E/O` 未移植）；(viii) $\rho_{\rm ion}$ 取第一离子（`USE_AVE_ION_GRID` 默认关）。

〔评注·代理〕训练域即适用域：QLKNN 的 `xbounds`、EPED-NN 的 `XBOUNDS`（{ref}`phys11-pedestal`）、TGLF-NN 的 31 行
盒子均**只报告不强制**；UKAEA 模型无盒子。成员标准差不是物理不确定度。`etg_correction = 1` 与 TORAX 的 $1/3$
是口径差，属调用方选择。

〔评注·Bohm/gyro-Bohm〕系数对一次 JET 运行拟合；$\rho$ 标签不可替换；$\Delta_{\rm edge}$ 在平坦边缘归零
（"flat edge kills Bohm not gyro-Bohm"）。

(phys08-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 湍流模块的锚点（全部 "captured from a real `libtglf.so` run"；参考卡 NS=2, NBASIS=4, NXGRID=16, KY=0.3, Miller 圆截面 RMIN 0.5 / RMAJ 3 / Q 2 / Q_PRIME 16，氢+电子 TAUS=AS=1, RLNS 1, RLTS 3, WIDTH 1.65）。
:name: tbl-p08-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| `kpar_operator`, `modkpar`, `polarization` | libtglf | 位同 / $10^{-10}$ |
| 九个 FLR 矩、五个比值 | libtglf | $10^{-6}$ / $10^{-10}$ |
| 通行/捕获 drift、乘积族、磁族、Linsker 族 | libtglf | $10^{-6}$–$10^{-10}$ |
| 主模 $\gamma,f$（端到端） | libtglf $0.3241554304484416/-0.1833585734120647$ | 1 % / 2 %；Python `TOL 1e-8` 两模 |
| $R_{\rm unit},q_{\rm unit},B_{\rm unit},f_t$ | `tglf_ave_scalar` | $10^{-9}$ / $10^{-12}$ |
| 带状流混合、SAT2 淬熄、SAT1/2/3 强度、混合平均、谱移 | libtglf（SAT_RULE 1/2/3，NKY 12） | $10^{-6}$–$10^{-12}$；谱移 $10^{-4}$ |
| $k_y$ 网格与求积 | libtglf；$F_{\rm total}=41.64152042999882$ | $10^{-12}$ / $10^{-9}$ |
| 回归 tglf01/02/06/08 | GACODE `tglf/tools/input`（rev `6357db306`），规则 1 与 2 | 通量 $<10^{-4}$；谱 $\gamma<10^{-9}$、$f<10^{-8}$ |
| tglf04 Waltz 淬熄 | 同上 | 偏移 $0.0300000000$ |
| JINTRAC 102530 平顶 | `tglf_fortran_jintrac.json` | 电子能量通量 0.8 %–7.1 %，带宽 12 % |
| 重入性 | 自身 | 交错用例位同 |
| QLKNN / UKAEA 前向 | 上游测试向量 / 独立 numpy | $1.63\times10^{-13}$ / $2.19\times10^{-15}$ |
| Bohm 系数 | JINTRAC 101612 `XE2`/`XI2` | 中位比 3.5 % 内，散布 $<6$ % |
:::

(phys08-asbuilt)=
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 湍流内容与内核函数、C-ABI、Python 入口（2026-09-02 快照）。
:name: tbl-p08-asbuilt
:align: left

| 内容 | 内核函数 | C-ABI（`fylite_rs_*`；`tglf_*` 在 feature `tglf` 下） | Python |
| :--- | :--- | :--- | :--- |
| 几何 | `miller_geo`, `mercier_luc`, `field_line`, `bounce_table`, `xgrid_functions`, `sat_geometry` | `tglf_units`（4 标量） | `tglf_units` |
| 基与 FLR | `gauss_hermite_nodes`, `hermite_basis`, `kpar_operator`, `basis_projection`, `flr_moment`, `moment_matrices` | — | — |
| 装配与求解 | `assemble`, `write_all_rows`, `collision_terms`, `vpar_terms`, `magnetic_terms`, `solve_dispersion_with_vectors_filtered` | `tglf_linear`（$2\,nmodes$）, `tglf_matrices`, `tglf_presets` | `scenario.model.gyrofluid`（线性） |
| 谱与通量 | `ky_spectrum`, `zonal_mixing`, `spectral_shift`, `saturated_intensity_mode`, `sat3_*`, `flux_spectrum_inner`, `find_mode_width` | `tglf_flux`（$3n_s+2n_{ky}$）, `tglf_flux_searched`（$5n_s+2n_{ky}$）, `tglf_kygrid`, `tglf_dlnpdr` | `gyrofluid.py`（`find_width`, `SAT_RULE`, `NMODES`） |
| 归一 | `mapping::tglf_local`, `tglf_species`, `derived`; `bundle::gyrobohm` | `tglf_local`（27 + 物种）, `gyrobohm`, `gyrobohm_gamma` | {ref}`phys04-mapping-tglf` |
| NN 评估 | `nn::ensemble`, `Shape::n_weights`, `Act` | `nn_ensemble`, `nn_weight_count` | `fylite.nn.Surrogate`; `scenario.model.qlknn` |
| EPED1-NN（编译） | `pedestal::eped1nn` | `eped1nn`（20 出） | {ref}`phys11-pedestal` |
| Bohm/gyro-Bohm | `bgb_chi` | `bgb_chi` | `test_bgb.py`（需 `$FYDOC_DIR`） |
:::

(phys08-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（源码逐字引）〕Erba 等 1997 / 1998（期刊、卷、页）{cite}`erba1997bgb,erba1998bgb`；QLKNN
{cite}`vandeplassche2020qlknn`；TGLF-NN {cite}`neiser2022tglfnn`；EPED / EPED1-NN {cite}`snyder2009development,snyder2011eped,meneghini2017epednn`；
UKAEA TGLF-NN {cite}`zanisi2025tglfnn`。
〔源码只给姓名，编者补文献〕TGLF {cite}`staebler2005tglf,staebler2007tglf`；GLF23 {cite}`waltz1997glf23`；
Hammett–Perkins {cite}`hammett1990fluid`；Dorland–Hammett {cite}`dorland1993gyrofluid`；Waltz–Miller
{cite}`waltz1999shape`；Miller {cite}`miller1998noncircular`；MXH {cite}`arbon2021mxh`；Mercier
{cite}`mercier1960critere`；Mercier–Luc {cite}`mercier1974lectures`；Linsker {cite}`linsker1981integral`；Waltz 淬熄
{cite}`waltz1994quench,waltz1998rotational`；气球模 {cite}`connor1978shear`；SAT0 {cite}`kinsey2008sat0`；SAT1
{cite}`staebler2016zonal,staebler2017nf`；谱移 {cite}`staebler2013prl`；SAT2 {cite}`staebler2021ppcf,staebler2021nf`；
SAT3 {cite}`dudding2022sat3`；`gauher` {cite}`press2007nr`；线性代数 {cite}`golub2013matrix,jacobi1846verfahren,francis1961qr,parlett1969balancing,householder1958unitary,ahues1997deflation,anderson1999lapack`；
QuaLiKiz {cite}`bourdelle2016qualikiz`；TORAX {cite}`citrin2024torax`；ResNet / ELU / GELU
{cite}`he2016resnet,clevert2016elu,hendrycks2016gelu`；numpy {cite}`harris2020array`。
标 〔凭记忆〕 者字段待核验；标 〔未核验〕 者为系数与论文原文的逐项一致性未查证。

〔转引〕GACODE TGLF `tglf_startup.f90`、`tglf_inout.f90`、`tglf_modules.f90`、`tglf_eigensolver.f90`、`tglf_matrix.f90`、
`tglf_LS.f90`、`tglf_TM.f90`、`tglf_geometry.f90`、`tglf_multiscale_spectrum.f90`、`tglf_kygrid.f90`、`tglf_max.f90`、
`tgyro_tglf_map.f90`、`tgyro_flux.f90`（Apache-2.0）；回归卡 `tglf/tools/input/tglf01..09`（rev `6357db306`）；
TGLFNN.jl 1.7.1、EPEDNN.jl（Apache-2.0）{cite}`tglfnn_jl,epednn_jl`；google-deepmind/fusion_surrogates
{cite}`fusion_surrogates`；ukaea/tglfnn-ukaea（LGPL，不装运）；JINTRAC 作业 101612（JET #58894）与 102530（ITER 15 MA）
的录得列。

〔源码未注出处（实现即定义）〕Gauss–Hermite 初值常数；MXH 弧长走法与 `mts = 5`；Mercier–Luc 的 $FF'$ 闭合与
$\cos\theta_p$；`midplane_shear` 的 $+0.11$；弹跳宽度捕获份额（`nb = 25`、$cdt$）；九个 FLR 拟合的形式、40×13 表与
尾因子；通行/捕获矩重组系数；闭合常数 {eq}`eq-p08-closure` 与十对环向通道及 21×20 表；十五矩行的全部系数；
碰撞拟合的全部常数；`FILTER = 2.0`；SAT1/2/3 与谱移的全部常数（{numref}`tbl-p08-sat`）；$0.3\sqrt\kappa$；
$k_y$ 网格断点与对数求积；准线性权中的 $\tfrac32p_{\rm tot}-\tfrac12p_\parallel$ 组合；宽度搜索常数；
$betae_\psi$ 的阻尼形式与 `bpar_moments` 系数；`mapping.rs` 的 TGLF 归一；`bgb.rs` 的 gyro-Bohm $\alpha$
（"literature values" 无具体引文）；`nn.rs` 的残差拓扑。

〔本仓选择〕拒绝而非静默重解释（`-51`…`-53`、`-39`、`-42`）；`NMODES` 默认 1；`etg_correction = 1`；
Bohm $\alpha$ 对 JINTRAC 101612 的冻结；`nn.rs` 不裁剪、不强制训练域；`WD_ZERO` 曾传 $10^{-12}$（已记为偏差）。
证据为 {numref}`tbl-p08-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
