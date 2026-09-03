---
title: 新经典输运 (Neoclassical Transport)
subtitle: NEO 解析模型族（Sauter 1999 / Redl 2021 / Hirshman–Sigmar / Hinton–Hazeltine / Chang–Hinton / Koh）、σ_neo 与 ⟨j·B⟩↔⟨j_φ⟩ 换算、漂移动理学求解
---

(phys07-intro)=
# 引言：解析族与第一性解 (Introduction)

〔范围〕本章详述新经典输运的两条路径：其一为 GACODE **NEO 解析分支**
的白箱翻译（`neo_theory.f90` 的 `compute_Sauter` / `compute_Sauter_mod` / `compute_HS` / `compute_Koh` /
`compute_HH` / `compute_CH` 等；`neo_equilibrium.f90` 的磁面平均与捕获份额），外加一个 SI 的 Redl-2021
剖面模型与 T-A9 的电导率 / 电流换算闭合；后者是 NEO **漂移动理学求解**的翻译（能量 / 俯仰角基、全线性化
Fokker–Planck 碰撞算子、稀疏 LU、矩）。仓根 `NOTICE` 列两者为 NEO 派生作品（Apache-2.0，修订 5efddfdf1）。
NCLASS 未移植。

〔出处姿态〕〔实现〕两个模块的头部都声明"非清洁室"。实现逐字引的论文：Sauter 1999（含 eqs. (13)/(13a)/(13b)）、
Redl 2021（eqs. 11/14/16–21）、Hirshman–Sigmar 1977（Phys. Fluids 20, 418）；只给姓名的：Lin-Liu & Miller 1995、
Hinton–Hazeltine、Chang–Hinton、Taguchi、Hinton–Rosenbluth、Koh；**DKE 本体在实现中无任何 Belli/Candy 论文引用**。
本章补出处并标核验状态。

〔与理论手册的分工〕捕获粒子是一切新经典效应的根、三碰撞率区、"电导率 / 自举 / 输运同源于同一组矩方程
系数 → 须整族同步升级"，见 SpResearch `GK-TMT-08`（跨仓）。本章述本内核实际实现的系数族与求解器。

(phys07-units)=
# NEO 归一变量集 (The NEO Normalised Variable Set)

〔实现〕长度以小半径 $a$，场以 $B_{\rm unit}$，密度与温度归一到**物种 1**（由 `neo_inputs` 装配时为电子；
温度归一到**第一离子**、密度到电子——见 {ref}`phys04-mapping-neo`），`nu_1` 为物种 1 的碰撞率，
$\rho=\rho_\ast\,\mathrm{sign}(B_{\rm unit})$；梯度标长 `dlnndr` $=-a\,\dd\ln n/\dd r$（**峰化剖面为正**）。
物种 $s$ 的碰撞率 $\nu_s=\nu_1(Z_s/Z_1)^4(n_s/n_1)\sqrt{m_1/m_s}(T_1/T_s)^{3/2}$（`neo_make_profiles` case 1）。
电流单位 $\expval{\vb j\cdot\vb B}=j^{\rm NEO}_{\parallel}\,en_ev_{\rm norm}B_{\rm unit}$（{ref}`phys04-mapping-neo`）；
"NEO 的 `jpar` 对 $\rho_\ast$ 精确线性"。〔出处〕NEO 的归一见 {cite}`belli2008neo`。

(phys07-averages)=
# 磁面平均与捕获份额 (Surface Averages and the Trapped Fraction)

〔实现〕`surface_averages`：GEO（{ref}`phys04-geo`）在 **2001** 点上求解（`GEO_ntheta_in = 2001`），线性插值到
NEO 的 $n_\theta$ 网格；权 $w_k=g_\theta/B$ 归一；$\expval{B^2}$、$\expval{B_t^2}$、$\expval{a/R}$、$\expval{1/B^2}$、
$I/\psi'=fq/r$。"求积是实现的，不是我们选的更细的——2001 点上平均把 Sauter 电流移 $5\times10^{-6}$，是求积差不是错。"

$$
f_t=1-\frac34\frac{\expval{B^2}}{B_{\max}^2}\int_0^1\frac{\lambda\,\dd\lambda}{\expval{\sqrt{1-\lambda B/B_{\max}}}}
$$ (eq-p07-ft)

〔实现〕`nlambda = 500`，NEO 的开型规则（端权 23/12、次端 7/12）。〔已确立〕{eq}`eq-p07-ft` 是有效捕获份额的
标准定义 {cite}`hirshman1981neoclassical,linliu1995trapped`；实现只给例程名 `compute_fractrap`。
另有 SI 剖面模型用的**解析近似** $f_t^{\rm eff}(\varepsilon)=1-\frac{(1-\varepsilon)^2}{\sqrt{1-\varepsilon^2}(1+1.46\sqrt\varepsilon)}$
（Lin-Liu & Miller 1995 拟合 {cite}`linliu1995trapped`〔凭记忆〕）——实现明言"不是同一个量"。

(phys07-sauter)=
# Sauter 1999 与 Redl 2021 (The Sauter and Redl Coefficient Families)

(phys07-sauter-structure)=
## 电流装配 (Current Assembly)

〔实现〕两个年份**只差拟合**，装配相同（`sauter_currents`）：

$$
\expval{j_\parallel B}=\sigma E_{\parallel0}+L_{32}\frac{I}{\psi'}\rho\,n_eT_e\widehat{\nabla T_e}
+\sum_sL_{31}\frac{I}{\psi'}\rho\,n_sT_s(\widehat{\nabla T_s}+\widehat{\nabla n_s})
+L_{34}\alpha\frac{I}{\psi'}\rho\,\widehat{\nabla T_i}\sum_{\rm ions}n_sT_s
$$ (eq-p07-jpar)

$$
\frac{\expval{j_{\rm tor}/R}}{\expval{1/R}}=\frac{\expval{j_\parallel B}\,r+\sum_s\rho\frac{I}{\psi'}n_sT_s(\widehat{\nabla n_s}+\widehat{\nabla T_s})(1-r)}{B_t(0)R(0)\expval{a/R}},\qquad r=\frac{\expval{B_t^2}}{\expval{B^2}}
$$ (eq-p07-jtor)

〔已确立〕{eq}`eq-p07-jpar` 是 Sauter 等的自举电流表达式（$L_{31}$ 乘总压强梯度、$L_{32}$ 乘 $T_e$ 梯度、$L_{34}\alpha$ 乘 $T_i$ 梯度）
{cite}`sauter1999bootstrap`；{eq}`eq-p07-jtor` 是 GS 方程给出的平行 ↔ 环向换算恒等式（{ref}`phys07-closure`）。

〔碰撞率〕〔实现〕Hinton–Hazeltine 参考频率 $\nu_i^{HH}=\nu_{\rm ion}\frac43\frac1{\sqrt{2\pi}}$、
$\nu_e^{HH}=\nu_{\rm ion}\frac43\frac1{\sqrt\pi}\sqrt{m_i/m_e}(T_i/T_e)^{3/2}/Z_i^2$，$\nu_\ast=\nu R\abs q/(\varepsilon^{3/2}v_{th})$；
Sauter 版 $\nu_{\ast i}^S=\nu_{\ast i}^{HH}\sum_{\rm ions}n_s/n_i$（"从主离子密度重归一到全部离子之和"）、
$\nu_e^S=\nu_e^{HH}\frac{n_e}{n_i}\frac{Z_{\rm eff}}{Z_i^2}$。**无库仑对数**（在 `nu_1` 里）。

(phys07-sauter-1999)=
## Sauter 1999 拟合 (The 1999 Fits)

〔实现〕以 $Z\equiv Z_{\rm eff}$：

$$
\alpha_0=\frac{-1.17(1-f_t)}{1-0.22f_t-0.19f_t^2},\qquad
\alpha=\frac{\frac{\alpha_0+0.25(1-f_t^2)\sqrt{\nu_{\ast i}}}{1+0.5\sqrt{\nu_{\ast i}}}+0.315\nu_{\ast i}^2f_t^6}{1+0.15\nu_{\ast i}^2f_t^6}
$$ (eq-p07-alpha99)

$$
X_{31}=\frac{f_t}{1+(1-0.1f_t)\sqrt{\nu_{\ast e}}+0.5(1-f_t)\nu_{\ast e}/Z},\qquad
L_{31}=\Big(1+\frac{1.4}{Z+1}\Big)X-\frac{1.9}{Z+1}X^2+\frac{0.3}{Z+1}X^3+\frac{0.2}{Z+1}X^4
$$ (eq-p07-l31)

$L_{32}=F_{32}^{ee}(X_{32e})+F_{32}^{ei}(X_{32i})$、$L_{34}=L_{31}(X_{34})$（$X_{34}$ 分母 $0.5(1-0.5f_t)\nu_{\ast e}/Z$），
$\sigma=\sigma_{\rm Sp}^{\rm NEO}F_{33}$：

$$
X_{33}=\frac{f_t}{1+(0.55-0.1f_t)\sqrt{\nu_{\ast e}}+0.45(1-f_t)\nu_{\ast e}/Z^{1.5}},\qquad
F_{33}=1-\Big(1+\frac{0.36}Z\Big)X_{33}+\frac{0.59}ZX_{33}^2-\frac{0.23}ZX_{33}^3
$$ (eq-p07-f33)

$$
\sigma_{\rm Sp}=\frac{1.9012\times10^4\,T_e^{1.5}}{Z_{\rm eff}\ln\Lambda_eN_Z}\ [\text{S/m}],\qquad N_Z=0.58+\frac{0.74}{0.76+Z_{\rm eff}}
$$ (eq-p07-sigsp)

〔出处〕{cite}`sauter1999bootstrap`（实现对 $X_{33}$/$F_{33}$/$\sigma_{\rm Sp}$ 引 eqs. (13)/(13a)/(13b)；对 $L_{31}$、$L_{32}$、$L_{34}$、$\alpha$
只引论文）。〔未核验〕本章未逐项核对实现系数与论文原文（Sauter 1999 另有 2002 年勘误
{cite}`sauter2002erratum`〔凭记忆〕，涉及 $F_{32}^{ee}$ 的一项）；证据是 NEO oracle 的位同一。

(phys07-sauter-2021)=
## Redl 2021 重标定 (The 2021 Recalibration)

〔实现〕"同一骨架，完全不同的拟合……$Z_{\rm eff}$ 依赖改变形状（$Z^{1.2}-0.71$ 对 1999 的 $Z+1$）。$L_{34}=L_{31}$，精确"：

$$
F_{31}(X)=X+\frac{0.15X-0.22X^2+0.01X^3+0.06X^4}{Z^{1.2}-0.71},\qquad
X_{31}=\frac{f_t}{1+0.67(1-0.7f_t)\frac{\sqrt{\nu_{\ast e}}}{0.56+0.44Z}+(0.52+0.086\sqrt{\nu_{\ast e}})(1+0.87f_t)\frac{\nu_{\ast e}}{1+1.13\sqrt{Z-1}}}
$$ (eq-p07-l31-21)

$$
X_{33}^{2021}=\frac{f_t}{1+0.25(1-0.7f_t)\sqrt{\nu_{\ast e}}(1+0.45\sqrt{Z-1})+0.61(1-0.41f_t)\nu_{\ast e}/\sqrt Z},\qquad
F_{33}^{2021}=1-\Big(1+\frac{0.21}Z\Big)X_{33}+\frac{0.54}ZX_{33}^2-\frac{0.33}ZX_{33}^3
$$ (eq-p07-f33-21)

$\alpha$、$L_{32}$ 的 2021 形式见实现（`redl_coefficients` / `sauter_redl`）。〔出处〕{cite}`redl2021bootstrap`（实现引 eqs. 11/14/16/17/18/19/20/21）。

:::{important}
〔$L_{34}=L_{31}$ 的裁定〕〔实现〕"★★★2026-08-30 裁定，此前的裁定是错的"：曾有两个 "Redl 2021" 宿主不一致——一个按
IMAS.jl 谱系在**第二个**有效捕获份额（Redl Eq. (18)，即电导率的 $f_{t,33}^{\rm eff}$）上评 $f_{31}$，与
$L_{34}=L_{31}$ 差 4.1 %（$\nu_\ast=0.1$）到 15.7 %（$\nu_\ast=1$），对 TORAX 高 1.20×（$\nu_\ast=1$）、1.89×（$\nu_\ast=10$）。
由三个独立来源定案：NEO `neo_theory.f90:626`、TORAX `redl.py:149`（引 Eq. 19）、IMAS.jl 自注"实为 f33teff"。
Redl 等原文："we have adopted the simplification of replacing $L_{34}$ with $L_{31}$ for all collisionalities"。
**Python 层的若干文档字符串仍描述旧差异，已过时**（`neoclassical.py` 模块头、`RedlSource`、`kernel.py::redl_coefficients`、
公开入口面与单位测试的注记）。
:::

(phys07-sauter-si)=
## SI 剖面模型（Redl 2021） (The SI Profile Model)

〔实现〕`redl_bootstrap_point`（$\bar\psi$ 每弧度，不再除 $2\pi$——曾双重换算使 $j_{bs}$ 大 $2\pi$，"实测 5.3–6.0×"）：

$$
j=-I_\psi p_e\Big[L_{31}\frac{\dd p/\dd\bar\psi}{p_e}+L_{32}\frac{\dd T_e/\dd\bar\psi}{T_e}+L_{34}\alpha\frac{1-R_{pe}}{R_{pe}}\frac{\dd T_i/\dd\bar\psi}{T_i}\Big],\qquad j_{bs}=\frac{\abs j}{B_0}
$$ (eq-p07-redl-si)

$R_{pe}=\mathrm{clamp}(p_e/p_{th},10^{-3},1)$、$I_\psi=RB_t$。碰撞率（"IMAS `nuestar`/`nuistar` 形式"）
$\nu_{\ast e}=6.921\times10^{-18}\frac{qRn_eZ_{\rm eff}\ln\Lambda_e}{T_e^2\varepsilon^{3/2}}$、
$\nu_{\ast i}=4.90\times10^{-18}\frac{qRn_iZ_{\rm ion}^4\ln\Lambda_i}{T_i^2\varepsilon^{3/2}}$，
$\ln\Lambda_e=23.5-\ln(\sqrt{n_e[\text{cm}^{-3}]}T_e^{-1.25})-\sqrt{10^{-5}+(\ln T_e-2)^2/16}$（"NRL 热电子—电子形式"）、
$\ln\Lambda_i=30-\ln(Z_{\rm avg}^3\sqrt{n_i}T_i^{-1.5})$。〔已确立〕系数 $6.921\times10^{-18}$、$4.90\times10^{-18}$ 与两个 $\ln\Lambda$
形式是 Sauter 1999 eqs. (18b)–(18e) {cite}`sauter1999bootstrap`（实现未说；IMAS 数据字典 {cite}`imbeaux2015imas` 亦用之）。
钳制："物理陈述"——$T_{e,i}\ge10$ eV（**在剖面网格上、插值前**）、$\varepsilon\in[10^{-4},0.99]$、$\abs q\ge10^{-3}$、
$Z_{\rm eff}\in[1,10]$（"2021 拟合的范围"）、$f_t\in[10^{-3},0.95]$、$z_{m1}=\max(Z-1,10^{-6})$（纯氢偏差 $4.1\times10^{-4}$ 相对，
TORAX 测试钉住）、$p\ge1$ Pa。TORAX oracle：$Z_{\rm eff}\ge1.5$ 时 $L_{31},L_{32},\alpha$ 最差 $8.9\times10^{-16}$；$L_{34}$ 相对 $<10^{-9}$。

(phys07-other)=
# 其余解析模型 (The Other Analytic Models)

〔Hirshman–Sigmar〕〔实现〕`hirshman_sigmar`（`compute_HS`；"Phys. Fluids 20, 418 (1977)" {cite}`hirshman1977multispecies`）：
多物种粒子 / 热通量。速度矩 $\text{nux}_k=\frac{4}{3\sqrt\pi}\int\dd x\,de\,e^{-\text{ene}}\nu_{d,\rm tot}\text{ene}^k\frac{1}{1+f_t/f_t^\ast}$
（$e_{\max}=16$，**8 阶 Gauss–Legendre × 100 段 = 800 节点**；$f_t^\ast=\frac{3\pi}{16}\varepsilon^2v_{th}\sqrt2\,\text{ene}^{3/2}/(R\abs q\nu_{d,\rm tot})$）；
俯仰角散射频率 $\nu_d$ 经 Chandrasekhar 型偏转函数 $H_d(x_b)=\frac{e^{-x_b^2}}{x_b\sqrt\pi}+(1-\frac1{2x_b^2})\mathrm{erf}(x_b)$
〔已确立：{cite}`helander2002collisional`〕；$L_{ij}$ 系数矩阵与实现一致。`erf` 自写（Maclaurin 级数 + 连分式，
"A&S 7.1.26 只有 $10^{-7}$"，与 libneo 逐位比对）。Gauss–Legendre 节点由 Newton 迭代（"NEO 的 `gauss_legendre`"，
即 Numerical Recipes `gauleg` 〔已确立〕{cite}`press2007nr`）。

〔Hinton–Hazeltine / Chang–Hinton / Taguchi / Hinton–Rosenbluth〕〔实现〕`analytic_fluxes`（`compute_HH`、`compute_CH`）：
两种 $K$ 拟合形 $K^{\rm sum}$、$K^{\rm prod}$ 及其六组常数；HH 的 $\beta_1$、$\Gamma_e$、$Q_i$、$Q_e$、$j_\parallel^{HH}$；
Chang–Hinton **不用几何算出的磁面平均**，而以 $\varepsilon$ 与 Shafranov 位移的闭式代替 $\expval{1/B^2}$、$1/\expval{B^2}$，
且 $I/\psi'=q/\varepsilon$；$\alpha=Z_{\rm eff}-1$、$\mu_\ast=(1+1.54\alpha)\nu_{\ast i}$；Taguchi 用 Chang–Hinton 的碰撞插值；
Hinton–Rosenbluth 势是"区间切换而非混合"。**全部常数实现无文献**。〔编者对应〕Hinton–Hazeltine 综述
{cite}`hinton1976theory`；Chang–Hinton 有限环径比离子热导率 {cite}`chang1982effect`〔凭记忆〕及其杂质推广
{cite}`chang1986effect`〔凭记忆〕；Taguchi {cite}`taguchi1988ion`〔凭记忆〕；Hinton–Rosenbluth {cite}`hinton1973transport`〔凭记忆〕。
〔未核验〕实现系数与这些论文原文的逐项对应未查证；证据是 libneo 位同一。`chi_neo_ion`（{ref}`phys04-mapping-neo`）
拒绝轴（$(q/\varepsilon)^2$ 发散）。

〔Koh〕〔实现〕`koh`（`compute_Koh`，"Koh et al."，无年份）："Sauter 1999 的骨架，每个 $X$ 分子乘 $1+\delta$"，
$\delta$ 含 $\tanh$、$\beta_p=\abs{\varepsilon-0.44}^{0.7}\cos(0.7\pi)$（$\varepsilon<0.44$）等；`h_param` 恒为 1（上游的单 / 双零点分支不可达）。
〔编者对应〕Koh 等偏滤器台基自举电流修正 {cite}`koh2012bootstrap`〔凭记忆〕。

〔极向流〕〔实现〕`vpol_ion`：$K=-k_\parallel\widehat{\nabla T_i}(I/\psi')\rho T_i/Z_i/(\expval{B^2}/n_i)$，$v_{\rm pol}=KB_p/n_i$，返回**截断
余弦级数**（$m_\theta=(n-1)/2-1$，整数运算）而非 $v_{\rm pol}(0)$。

(phys07-closure)=
# 闭合：σ_neo 与 ⟨j·B⟩ ↔ ⟨j_φ⟩ (Closure — Conductivity and the Current Identity)

〔实现〕T-A9 块："缺的不是一条曲线，是一个共同度量：解析自举族返回 $\expval{\vb j\cdot\vb B}$，重构返回 $\expval{j_\phi}$。"

$$
\frac{\expval{j_\phi/R}}{\expval{1/R}}=\frac{\expval{\vb j\cdot\vb B}\,r+Fp'(1-r)}{F\expval{1/R}},\qquad r=\frac{\expval{B_{\rm tor}^2}}{\expval{B^2}}
$$ (eq-p07-identity)

〔已确立〕由 $\mu_0\vb j=F'\vb B+\mu_0p'R\hat e_\phi$（GS 方程的电流分解，{ref}`phys02-eq-gs`）取磁面平均即得；$p'$ 项是
**抗磁电流**（"既不属自举也不属欧姆"）。用户指南保真度章实测：换算相对差 $2.65\times10^{-12}$，去掉 $p'$ 项环向电流动 24.3 %。

〔σ_neo〕〔实现〕`sigma_neo_point`：$\sigma_{\rm neo}=\sigma_{\rm Sp}F_{33}$，$F_{33}$ 按年份（0 = 1999，1 = 2021，其他拒绝），
$f_t$ 与 $\nu_{\ast e}$ 与解析自举**同一对函数**；`collisionless` 给最深捕获修正（$X_{33}\to f_t$）。Spitzer 关系：
$\sigma_{\rm Sp}^{\rm Sauter}\times\eta_\parallel^{\rm NRL}=1\pm3\times10^{-3}$（$Z=1$），$\eta_\parallel/\eta_\perp\equiv0.51$
（{ref}`phys10-resistivity`；Spitzer–Härm {cite}`spitzer1953transport`）。

:::{note}
〔DKE oracle〕〔实现〕以漂移动理学解为 oracle（梯度全零、$E_{\parallel0}=1$ ⇒ $\expval{\vb j\cdot\vb B}=\sigma_{\rm neo}$，同一单位）：
$\varepsilon=1/6$、$f_t=0.5664$、$Z_{\rm eff}=1$、$(n_e,n_\xi,n_\theta)=(6,25,25)$——$\nu_{\ast e}=0.328$：Redl/DKE **0.9994**、
Sauter-1999/DKE **0.9742**；$\nu_{\ast e}=3.284$：**1.0008**、**0.9331**。"2021 跟得住求解，1999 在这个捕获份额上低 2.2–6.7 %——
这正是 Redl 等重新标定的理由，此处是量出来的。"**深香蕉区**（$\nu_{\ast e}=3.3\times10^{-3}$）oracle **不收敛**：
$n_\xi=11/17/25/33/41\to1.6112/1.4936/1.4214/1.3806/1.3569\times10^6$（末两档差 1.7 %）。
:::

(phys07-dke)=
# 漂移动理学求解 (The Drift-Kinetic Solve)

〔所解方程〕〔实现 / 推断〕单磁面上、$\rho_\ast$ 一阶线性化的稠态漂移动理学方程：非绝热扰动 $g_s$ 关于 Maxwellian，
$(\theta,\xi,v)$ 局域空间，**全线性化 Fokker–Planck 碰撞算子**（NEO `collision_model = 4`，"FULL LINEARIZED FOKKER-PLANCK"），
**无旋转**（`rotation_model = 1`：全部旋转项恒为零，实现逐条说明），源 = 径向磁漂移 × （密度、温度、势梯度）+ 感应
$\expval{E_\parallel B}$ 驱动；准中性给出一阶势 $\delta\phi(\theta)$。〔出处〕这是 NEO 的表述 {cite}`belli2008neo,belli2012neo`〔后者凭记忆〕；
**实现中无此引用**。

〔基〕〔实现〕俯仰角：Legendre $P_l(\xi)$；能量：广义 Laguerre 族（`laguerre_method` 1 = "half & three-halves"（缺省）、
2 = Sonine、3、4；系数全部经 $\Gamma(n/2)$ 表 `gamma2`，求解**从不**逐点评多项式）；$\theta$：均匀网格 + 周期五点中心差分
`CDERIV = (1,−8,0,8,−1)/(12Δθ)`。`E_ALPHA = 2` 为编译期常数。五个能量向量 / 五个能量矩阵为基函数积的能量矩重叠积分
（闭式 $\Gamma$ 和；实现无文献）。

〔碰撞算子〕〔实现〕`compute_fcoll(m_0,\lambda)`（$\lambda=(v_a/v_b)^2$）：三个 $\lambda$ 区间（$<1/10$、中、$>10$，`LAMBDA_LARGE = 10`）
的级数 / 递推给出 $f_{mn}$、$\bar f_{mn}$（与 libneo 逐位比对）；`collision_matrices`：试验粒子算子（俯仰角散射
$-\tau^{-1}\sqrt{\lambda/\pi}\,l(l+1)[\ldots]$ + 能量扩散 / 拖曳，含 $(1-T_a/T_b)$ 项）与场粒子算子（$r_1\ldots r_7$）；
多物种、杂质非痕量（进入全部 `js` 求和）。〔出处〕线性化 Landau 算子的 Laguerre–Legendre 矩阵元见
{cite}`belli2012neo`〔凭记忆〕、{cite}`helander2002collisional`。

〔组装与源〕〔实现〕未知量序 $((is\,n_e+ie)n_x+ix)n_\theta+it$；约束行（`ix = 0, it = 0, ie ∈ {0,1}`）$\sum_{jt}w_\theta g=0$
（"固定碰撞算子的零空间——全 FP 算子只湮灭密度与能量矩"）；流动项 $\text{stream}=\sqrt2v_{th}k_\parallel/(12\Delta\theta)$ 配
Legendre 耦合 $l/(2l-1)$、$(l+1)/(2l+3)$；镜力 $\text{trap}=\frac{\nabla_\parallel B}{B}\frac{v_{th}}{\sqrt2}$；源在 $ix=0$（$-\tfrac43$）、
$ix=1$（$\sqrt2v_{th}e05\frac{Z_s}{T_s}E_{\parallel0}B/\expval{B^2}$）、$ix=2$（$-\tfrac23$）。$(6,17,17)$、两物种 ⇒ 4284 行。

〔稀疏 LU〕〔实现〕COO **重复项求和**（"UMFPACK 求和重复三元组"）→ CSC → **Reverse Cuthill–McKee** 对称置换（"$(6,17,17)$
自然序 23 s 对 UMFPACK 的几分之一秒；RCM 下带状，成本降数量级"）→ **左视 LU，部分选主元（Gilbert–Peierls）** →
解 → 逆置换；恰零主元 → `Err(-70)`。〔出处〕Gilbert–Peierls {cite}`gilbert1988sparse`〔凭记忆〕；RCM
{cite}`cuthill1969reducing`〔凭记忆〕；被替代的 UMFPACK {cite}`davis2004umfpack`〔凭记忆〕。无迭代精化、无缩放。

〔矩〕〔实现〕`transport`（`TRANSP_do`）：$ix=0$ → $\Gamma_s$、$Q_s$、$\delta\phi$；$ix=1$ → $\Pi_s$、$\expval{Bu_\parallel}$；$ix=2$ → $\Gamma_s$、$Q_s$
（权 $2/15$）；$ix=3$ → $\Pi_s$（$2/35$）；"俯仰角谐波决定一行贡献给哪个矩"。$\expval{j_\parallel B}=\sum_sZ_s\expval{Bu_\parallel}^{(n)}_s$；
流分解 $K_s$、$v_{\rm pol}$、$v_{\rm tor}$、$\expval{j_{\rm tor}/R}/\expval{1/R}$。`driftxrot3` "名为旋转、内容是几何"，在矩中出现。

〔libneo oracle〕〔实现〕四例 × 两分辨率（(3,5,9)、(6,17,17)），`jpar_dke`、`jtor_dke` 相对误差 $<10^{-8}$（实测 $10^{-14}$–$3\times10^{-10}$，
"分解不同，物理相同"）；平衡层 17 个数组 $10^{-12}$。分辩率档（EAST $\psi_N\approx0.5$）：`accurate` 6/17/17（397 ms）、
`medium` 6/13/13（0.01 %）、`fast` 4/11/11（0.22 %）、`coarse` 3/9/9（1.84 %）。

(phys07-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **拟合域**：Redl 2021 的 $Z_{\rm eff}\in[1,10]$、$f_t\in[10^{-3},0.95]$；纯氢处 $z_{m1}$ 地板带 $4\times10^{-4}$ 偏差。
2. **两种捕获份额不可混**：真实几何的 {eq}`eq-p07-ft` 与解析 $f_t^{\rm eff}(\varepsilon)$。
3. **深香蕉区** DKE 在 $n_\xi\le41$ 不收敛，不可作 oracle。
4. **Chang–Hinton 拒绝轴**；其闭式磁面平均在强成形下失真（实现明言不用几何平均）。
5. **无旋转、无 NCLASS、无碰撞模型 1–3**；杂质非痕量但**无各向异性**。
6. **$\rho_\ast$ 线性**——须传物理 $\rho_s/a$。
7. **换算恒等式换算的是总电流**：抗磁项属总量，分道时须显式处理。
8. **Python 文档字符串过时**（$L_{34}$ 裁定前）——以 Rust 实现与 TORAX 测试为准。
9. **Spitzer 0.51 在 $Z\ne1$ 是近似**；$Z$ 依赖只经 Sauter 的 $N_Z$ 进入。

(phys07-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 新经典模块的锚点。
:name: tbl-p07-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 解析族全部（Sauter/Redl/HH/CH/Koh/HS/Taguchi/HR） | 录得 libneo | 位同一（NEO oracle） |
| DKE 端到端 | libneo + UMFPACK，4 例 × 2 分辨率 | $<10^{-8}$（实测 $\le3\times10^{-10}$） |
| DKE 平衡层 | libneo `neo_equil_out` 17 数组 | $10^{-12}$ |
| $\sigma_{\rm neo}$ vs DKE | 自身 | Redl 1 % 内、Sauter 8 % 内、Redl 更近 |
| Redl $L_{31},L_{32},\alpha$（$Z_{\rm eff}\ge1.5$）；$L_{34}$ | TORAX b4d40633 | $8.9\times10^{-16}$；$<10^{-9}$ |
| $\expval{j\cdot B}\to\expval{j_\phi}$ 再现 NEO `jtor` | NEO | $10^{-12}$ |
| $\sigma_{\rm Sp}^{\rm Sauter}\eta_\parallel$ | NRL | $1\pm3\times10^{-3}$ |
| erf 参考值 | 表 | $10^{-14}$ |
| Gauss–Legendre 精确到 $2n-1$ 次 | 闭式 | $10^{-13}$ |
| 自举形状 RMS（合成 g 文件，8 面） | `jpar_dke` | Redl 0.165（门 0.30） |
:::

(phys07-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 新经典各模型族产出的输运系数与电流，及其所落的 fyo 数据集。
:name: tbl-p07-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| NEO 解析族（六档） | `fyo:core_profiles`：自举电流密度 | `scenario.model.neoclassical.bootstrap` |
| Redl 剖面模型（SI） | 同上，另出捕获份额等中间量 | `neoclassical.bootstrap_profile` |
| 新经典电导率与并行↔环向换算 | `fyo:core_profiles`：$\sigma_\parallel$、$\langle j\cdot B\rangle$ | `analysis.loop`（自举回灌，{ref}`phys03-rows-fsa`） |
| Chang–Hinton 离子热扩散率 | `fyo:core_transport`：新经典 $\chi_i$ | `scenario.model.closure` |
| 漂移动理方程解（DKE） | `fyo:core_transport`：第一性原理的新经典通量 | `fylite.kernel.dke_solve` |
:::

(phys07-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（实现逐字引）〕Sauter 等 {cite}`sauter1999bootstrap`；Redl 等 {cite}`redl2021bootstrap`；Hirshman–Sigmar
{cite}`hirshman1977multispecies`；Spitzer–Härm {cite}`spitzer1953transport`；NRL {cite}`huba2013nrl`。
〔编者对应〕NEO {cite}`belli2008neo,belli2012neo`；捕获份额 {cite}`hirshman1981neoclassical,linliu1995trapped`；
Hinton–Hazeltine {cite}`hinton1976theory`；Chang–Hinton {cite}`chang1982effect,chang1986effect`；Taguchi {cite}`taguchi1988ion`；
Hinton–Rosenbluth {cite}`hinton1973transport`；Koh {cite}`koh2012bootstrap`；Sauter 勘误 {cite}`sauter2002erratum`；
碰撞理论教科书 {cite}`helander2002collisional`；Gauss–Legendre {cite}`press2007nr`；稀疏 LU {cite}`gilbert1988sparse`；
RCM {cite}`cuthill1969reducing`；UMFPACK {cite}`davis2004umfpack`；IMAS {cite}`imbeaux2015imas`；TORAX {cite}`citrin2024torax`。
标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）；标 〔未核验〕 者为系数与论文原文的逐项一致性未查证。

〔转引〕NEO `neo_equilibrium.f90`、`neo_make_profiles.f90`、`neo_theory.f90`、`neo_energy`、`neo_compute_fcoll`、`neo_do`、
`TRANSP_do`（GACODE 5efddfdf1，Apache-2.0）；TORAX `bootstrap_current/redl.py`；IMAS.jl / FUSE `Sauter_neo2021_bootstrap`
（作为 $L_{34}$ 裁定的对照，静态阅读口径）。

〔本仓选择〕SI 剖面模型的全部钳制；$L_{34}=L_{31}$ 的裁定；`sigma_neo` 的年份拒绝；RCM 置换与 Gilbert–Peierls LU 的实现；
分辨率档；自写 erf。证据为 {numref}`tbl-p07-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
