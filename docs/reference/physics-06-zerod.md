---
title: 物理与数值 · 0-D 放电模型 (Physics & Numerics — The 0-D Discharge Layer)
subtitle: zerod.rs —— 规定剖面档（Tier A）、约束标度律能量平衡档（Tier B）、运行域界限与磁通预算
---

(phys06-intro)=
# 引言：两档不同性质的答案 (Introduction — Two Tiers)

〔范围〕本章详述 `zerod.rs`（约 820 行 + 测试）实现的**零维放电层**。它有两档，源码强调它们是
"**不同种类的答案**"：

- **Tier A（规定）**：剖面形状与幅值全部由用户给出，模块只算聚变功率、环电压、$Q$ 等**算术量**；
  "$W_{th}$ 是你给的剖面的积分"，能量平衡**不闭合**。
- **Tier B（预测，实验性）**：以约束时间标度律闭合能量平衡 $\dd W/\dd t=P_{\rm heat}-W/\tau_E$，求 $W_{th}$
  与中心温度。源码标注 "Status: this tier is an EXPERIMENT（ADR-116 OI-1）"。

〔出处姿态〕〔源码〕模块头部："凡携带物理常数或取自文献的闭式者在此"，并**逐条给出**标度律与
经验界限的一手文献（Bosch–Hale、ITER Physics Basis、Yushmanov、Martin、Greenwald、Troyon、Ejima）
——这是内核中文献标注最完整的模块。未注出处者（剖面族、电阻率系数、电感式）本章一一标出。

〔与理论手册的分工〕0D 约化"按可靠性分级而非按精度分级"的前提、由 1.5D 能量方程体积分导出
0D 储能方程、$\tau_E$ 是**定义**而非模型、标度律的量纲结构（Kadomtsev / Connor–Taylor 约束）、
守恒审计四判据，见 SpResearch `GK-TMT-01`（跨仓）。

(phys06-profiles)=
# 规定剖面与几何近似 (Prescribed Profiles and Geometry)

〔剖面族〕〔源码〕

$$
f(\rho)=f_0\big[\epsilon+(1-\epsilon)(1-\rho^2)^p\big],\qquad \rho\in[0,1]
$$ (eq-p06-profile)

$\epsilon$ = `edge_frac`（缺省 0.05），$p$ = 峰化因子（密度缺省 1.0、温度 1.5）。源码未注出处；
$(1-\rho^2)^p$ 族是 0-D 建模的惯用形状（如 {cite}`uckan1990guidelines`〔凭记忆〕），系数是**本仓缺省**。

〔平均与体积〕〔源码〕体积平均 $\expval f=\int f\,2\rho\,\dd\rho/\int2\rho\,\dd\rho$（**圆截面**权 $\dd V\propto\rho$），
体积 $V=2\pi^2R_0a^2\kappa$（**椭圆截面**），线平均 $\bar f=\int_0^1f\,\dd\rho$（中平面弦）。源码注明
几何约定的不一致（FYL-DESIGN-05 O-4）："圆近似配椭圆体积"。表面积 $S=4\pi^2R_0a\sqrt{(1+\kappa^2)/2}$
（椭圆周长的 $2\pi a\sqrt{(1+\kappa^2)/2}$ 近似；"Martin 阈值对等离子体表面回归"）。
〔METIS oracle〕〔源码〕椭球体积对 METIS 认证表（84 片）：圆片精确到 0.2 %，成形等离子体高估 $<17\%$
（中位 $>3\%$）；归一平均 4 % 内；储能对 METIS 体积 12 % 内。

(phys06-fusion)=
# 聚变功率：Bosch–Hale 反应率 (Fusion Power — Bosch–Hale Reactivity)

〔源码〕`dt_reactivity(T_i)`（$T$ 以 keV）：

$$
\theta=\frac{T}{1-\dfrac{T(C_2+T(C_4+TC_6))}{1+T(C_3+T(C_5+TC_7))}},\qquad
\xi=\Big(\frac{B_G^2}{4\theta}\Big)^{1/3},\qquad
\expval{\sigma v}=C_1\theta\sqrt{\frac{\xi}{m_rc^2T^3}}e^{-3\xi}\times10^{-6}\ [\text{m}^3/\text{s}]
$$ (eq-p06-bh)

$B_G=34.3827$ keV$^{1/2}$，$m_rc^2=1124656$ keV，$C_1..C_7=[1.17302\times10^{-9},\,1.51361\times10^{-2},\,7.51886\times10^{-2},\,4.60643\times10^{-3},\,1.35000\times10^{-2},\,-1.06750\times10^{-4},\,1.36600\times10^{-5}]$。
**适用域守卫**：$T\notin[0.2,100]$ keV 返回 0（"而不外推"）。〔出处〕Bosch–Hale 参数化，NF 32 (1992) 611，
表 VII {cite}`boschhale1992fusion`（源码逐字引）。

〔功率〕$n_D=n_T=f_{DT}n_e$（0.5 → 50:50 无稀释）；$p=n_Dn_T\expval{\sigma v}E_{DT}$，$E_{DT}=17.59$ MeV；
$P_\alpha=0.2013P_{\rm fus}$（"3.52/17.59"；测试注其与自身注释差 0.6 %，判据带 1 %）。
锚：(5, 10, 20, 50 keV) → (1.35e-23, 1.13e-22, 4.31e-22, 8.72e-22) m³/s，相对 $\le2\%$（Bosch–Hale 表 VIII）；
对 METIS `zformsv` 转录 $<10^{-12}$；对 TORAX 机器精度；对 FUSE 聚变功率 $<2\%$。

(phys06-current)=
# 电流账：环电压、电阻与电感 (The Current Account)

〔源码〕`loop_voltage_ohmic`：

$$
\eta=2.8\times10^{-8}\frac{Z_{\rm eff}}{\max(\expval{T_e}_{\rm keV},10^{-3})^{3/2}}\ \Omega\,\text{m},\qquad
\eta_{\rm neo}=\frac{\eta}{\max((1-\sqrt\epsilon)^2,10^{-3})},\qquad \epsilon=a/R_0
$$ (eq-p06-eta)

$$
R_p=\eta_{\rm neo}\frac{2\pi R_0}{\pi a^2\kappa},\qquad
L_p=\mu_0R_0\Big(\ln\frac{8R_0}{a}+\frac{l_i}2-2\Big),\qquad
V_{\rm loop}=I_pR_p+L_p\dv{I_p}{t}
$$ (eq-p06-vloop)

〔出处〕Spitzer 电阻率 {cite}`spitzer1953transport`〔凭记忆〕的量级形式：$\eta_{\rm Sp}\approx2.8\times10^{-8}Z_{\rm eff}T_{\rm keV}^{-3/2}$ Ω·m
是 $\ln\Lambda\approx17$、$Z=1$ 下 NRL 手册系数 $\eta_\parallel=0.51\times1.03\times10^{-4}Z\ln\Lambda T_{\rm eV}^{-3/2}$ 的
数值（$0.51\times1.03\times10^{-4}\times17\times10^{-4.5}\approx2.8\times10^{-8}$）{cite}`huba2013nrl`〔已确立：可自行核算〕；
$(1-\sqrt\epsilon)^{-2}$ 是捕获粒子对电导率修正的最粗近似（精确形式见 {ref}`phys07-intro` 的 Sauter / Redl）
{cite}`wesson2004tokamaks`〔凭记忆〕；$L_p$ 是大环径比环的外电感加内电感 {cite}`wesson2004tokamaks`。
源码对这三式**均未注出处**，只写"Spitzer 电阻率与通常的 $(1-\sqrt\epsilon)^{-2}$ 捕获粒子修正"，
并自评"好到几十个百分点——够量磁通预算，不够替代电流扩散解"。

〔不含〕〔源码〕`zerod.rs` **无**自举份额、无非感应份额、无 $\sigma_{\rm neo}$ 剖面；$Z_{\rm eff}$ **只**经 $\eta$ 进入。
`flux_budget` 与 `loop_voltage_ohmic` 用**同一个** $L_p$（测试钉到 $10^{-18}$）。

(phys06-waveforms)=
# 时间形状：相位与波形 (Phases and Waveforms)

〔源码〕四相 `breakdown / rampup / flattop / rampdown`；梯形波形 `trapezoid(ph, t, flat, start, end)`，
斜坡分母下限 $10^{-9}$ s（"退化相位给阶跃而非无穷"）；三个中心波形只差起止值：$I_p$ (0, 0)、
$n_e$ (2 % flat)、$T_e$ (1 % flat)——"这两个分数就是模型"（避免斜坡相除零）。执行器 `actuator` 在
$[t_{\rm on},t_{\rm off}]$ 内取常数。源码未注出处（工程约定）。

(phys06-tierA)=
# Tier A：规定评估 (Tier A — Prescribed Evaluation)

〔源码〕`evaluate`：逐时刻由 `ne0[k]`、`te0[k]` 与 {eq}`eq-p06-profile` 造剖面，$T_i=T_e\cdot$`ti_over_te`；
$P_{\rm fus}$、$P_\alpha$；$\expval{T_e}$；$V_{\rm loop}$（$\dd I_p/\dd t$ 由 `kernels::gradient`）；
$Q=P_{\rm fus}/P_{\rm inj}$，$P_{\rm inj}\le0$ 时 **NaN**（"$Q$ 无注入功率时无定义；NaN 说了实话，0 会撒谎"）。
参数块 10 个标量（`ti_over_te, peaking_n, peaking_t, edge_frac, r0, a, kappa, zeff, li, dt_fraction`）。
宿主 `Scenario` 缺省 EAST 型（$I_p=0.4$ MA、$n_{e0}=4\times10^{19}$、$T_{e0}=3$ keV、$R_0=1.85$、$a=0.45$、$\kappa=1.8$、$Z_{\rm eff}=1.8$）。

(phys06-tierB)=
# Tier B：标度律闭合的能量平衡 (Tier B — Scaling-Law Energy Balance)

(phys06-tierB-scaling)=
## 约束时间标度律 (Confinement-Time Scalings)

〔源码〕以 $I$ 取 MA、$P$ 取 MW、$\epsilon=a/R_0$：

$$
\tau_E^{\rm IPB98(y,2)}=0.0562\,I^{0.93}B_t^{0.15}\bar n_{19}^{0.41}P^{-0.69}R_0^{1.97}\kappa_a^{0.78}\epsilon^{0.58}M^{0.19}
$$ (eq-p06-ipb98)

$$
\tau_E^{\rm ITER89\text{-}P}=0.048\,I^{0.85}R_0^{1.2}a^{0.3}\kappa_a^{0.5}\bar n_{20}^{0.1}B_t^{0.2}M^{0.5}P^{-0.5}
$$ (eq-p06-iter89)

〔出处〕{eq}`eq-p06-ipb98`：ITER Physics Basis 第 2 章 Eq. (20) {cite}`iterphysicsbasis1999ch2`（源码逐字引）；
{eq}`eq-p06-iter89`：Yushmanov 等 {cite}`yushmanov1990scalings`（源码逐字引）。"系数取自各变体所引出版物；
无一在此拟合"。$P\le0$、$I\le0$、$\bar n\le0$ 时返回 **0**（"$P\to0$ 是极点不是极限"）。增强因子 $H$ 乘在 $\tau_E$ 上。

〔量纲评注〕〔已确立〕幂律指数受 Kadomtsev / Connor–Taylor 相似性约束（`GK-TMT-01`）；本模块不检验之，
只按文献取值。

(phys06-tierB-lh)=
## L–H 阈值功率 (L–H Threshold)

$$
P_{\rm thr}=10^6\times0.0488\,\bar n_{20}^{0.717}\abs{B_t}^{0.803}S^{0.941}\ [\text{W}]
$$ (eq-p06-martin)

〔出处〕Martin 等 {cite}`martin2008power`（源码逐字引：J. Phys. Conf. Ser. 123 (2008) 012033）。任一输入非正 → 0。
锚：$S(6.2,2.0,1.85)\in(600,900)$ m²；$P_{LH}(0.5\times10^{20},5.3\,\text{T},S)\in(20,90)$ MW（"约 50 MW"）。

(phys06-tierB-march)=
## 能量方程的推进 (Marching the Energy Equation)

〔源码〕`predict`：每步 (1) $n_e(\rho)$；$T_{e0}$ 由 **K-3 归一算子**
$T_{e0}=W_{\rm target}/\big[\expval{\tfrac32n_e\hat s(\rho)(1+T_i/T_e)}V\cdot\text{keV}\big]$（幅值线性，精确）；
(2) $P_\Omega=I_p^2R_p$（{eq}`eq-p06-vloop`，$\dd I_p/\dd t=0$）；(3) $P_\alpha$；(4) $P_{\rm heat}=P_{\rm aux}+P_\Omega+P_\alpha$，
**标度律用的 $P_{\rm loss}\equiv P_{\rm heat}$**（无辐射、无 $\dd W/\dd t$ 扣除）；(5) $\tau=H\tau_E$；(6) 更新：

$$
W_{k+1}=W_ke^{-\Delta t/\tau}+P_{\rm heat}\,\tau\,(1-e^{-\Delta t/\tau})\quad(\tau>0);\qquad
W_{k+1}=\max(W_k+\Delta tP_{\rm heat},0)\quad(\tau=0)
$$ (eq-p06-expint)

〔已确立〕{eq}`eq-p06-expint` 是 $P$、$\tau$ 在步内为常数时线性 ODE 的**精确解**（指数积分器
{cite}`hochbruck2010exponential`〔凭记忆〕）；源码指出隐式 Euler "以 $\ln(1+\Delta t/\tau)/\Delta t$ 而非 $1/\tau$ 松弛"。
$\tau_E$ 与 $P_\alpha$ 在步**起点**求值——耦合显式，"一次松弛扫描，不是 METIS 的定点"。
`balance` 报告每一项可取回且求和闭合（"**不是**积分器对预算"）。

:::{warning}
〔代码观察〕〔源码〕`predict` 把 **体积平均** 密度传给 `tau_e` 与 `p_lh_threshold` 的 `ne_bar`，而
`TauInputs::ne_bar` 文档写"线平均电子密度"、且 `line_average` 存在（仅在 `limits` 由调用方用）。
对 $(1-\rho^2)$ 剖面两者相差 $2/3$ 对 $1/2$。这是本章标出的**待裁定项**。
:::

〔不含〕〔源码〕无隐式代数 $\dd W/\dd t$ 步、无 $\tau_E(W)$ 阻尼定点、无 $\chi_0=K/(W-W_0)$ 形状闭式（形状是固定
$(1-\rho^2)^p$ 族，幅值由 K-3 归一）、无 He 灰、无稀释（$n_i=n_e$，"上界"）、无辐射损失。
`GK-TMT-01` 所述的这些结构在本内核**未实现**。

(phys06-limits-domain)=
# 运行域界限 (Operating-Domain Limits)

〔源码〕`greenwald_density`：$n_{GW}=\frac{I_p[\text{MA}]}{\pi a^2}\times10^{20}$ m⁻³ {cite}`greenwald1988density`
（源码逐字引；"对**线平均**密度的经验破裂边界"）；`q_cylindrical`：

$$
q_{\rm cyl}=\frac{2\pi a^2\abs{B_t}(1+\kappa^2)}{2\mu_0R_0\abs{I_p}}
$$ (eq-p06-qcyl)

〔已确立〕与 ITER 指南的 $q_{\rm cyl}=5a^2B(1+\kappa^2)/(2RI_{\rm MA})$ 同式（$2\pi/\mu_0=5\times10^6$）
{cite}`uckan1990guidelines`〔凭记忆〕；源码未注。`limits`：$\expval p=\tfrac23W_{th}/V$、
$l_{\rm pol}=2\pi a\sqrt{(1+\kappa^2)/2}$、$B_{\rm pol}=\mu_0\abs{I_p}/l_{\rm pol}$、$\beta_t=2\mu_0\expval p/B_t^2$、
$\beta_p=2\mu_0\expval p/B_{\rm pol}^2$、$\beta_N=100\beta_ta\abs{B_t}/I_p[\text{MA}]$、$f_{\rm Troyon}=\beta_N/2.8$
（`TROYON_G = 2.8`——"参照标记，不是本层能算的极限" {cite}`troyon1984mhd`）。锚：ITER 15 MA、$a=2$ m →
$n_{GW}=1.19\times10^{20}$（1 %）；ITER 基线 $\beta_N\in(1.4,2.1)$（"约 1.8"）；IPB98(y,2) $\in(2.5,5.0)$ s（"约 3.7 s"）。

(phys06-flux)=
# 磁通预算 (Flux Budget)

$$
\Phi_{\rm ind}=L_pI_{p,\rm flat},\qquad \Phi_{\rm res}=C_E\mu_0R_0I_{p,\rm flat},\qquad
\Phi_{\rm ramp}=\Phi_{\rm ind}+\Phi_{\rm res},\qquad \Phi_{\rm consumed}=\int V_{\rm loop}\dd t
$$ (eq-p06-ejima)

〔源码〕`EJIMA_C = 0.45`——"Ejima 等，NF 22 (1982) 1313：跨装置回归，0.45 是全斜坡通常取值"
{cite}`ejima1982volt`（源码逐字引）。$t_{\rm sustain}=\max((\Phi_{\rm avail}-\Phi_{\rm ramp})/V_{\rm flattop},0)$；
$\Phi_{\rm avail}\le0$ 或 $V_{\rm flattop}\le0$ 时 **$-1$**（"摆幅未声明……没有值得发明的缺省"）；平顶区间按**中点**标记。

(phys06-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **Tier A 不闭合能量平衡**——$W_{th}$、$Q$ 是对用户输入的算术。
2. **Tier B 是实验档**：$P_{\rm loss}=P_{\rm heat}$（无辐射、无 $\dd W/\dd t$）；$\tau_E$ 与 $P_\alpha$ 显式；
   密度平均口径待裁定（{ref}`phys06-tierB-march`）。
3. **几何近似不一致**（圆截面权 + 椭圆体积），对成形等离子体体积高估 $\le17\%$（METIS oracle）。
4. **电阻率与电感是量级公式**（"几十个百分点"）；无自举、无非感应份额。
5. **Bosch–Hale 只在 $0.2\le T\le100$ keV**，域外返回 0。
6. **标度律系数不可外推到拟合数据库之外**（`GK-TMT-01`）；$H$ 因子是"诚实的无知"。
7. **无稀释、无 He 灰、无杂质辐射**——$W_{th}$、$P_{\rm fus}$ 是上界。
8. Greenwald 与 Martin 都要求**线平均**密度——调用方须给对。

(phys06-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 0-D 层的锚点（内核单元测试与 Python 物理层测试）。
:name: tbl-p06-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| $\expval{\sigma v}$ 四点 | Bosch–Hale 表 VIII | $\le2\%$ |
| 域外反应率 | — | 0.1 / 150 keV → 0 |
| $P_\alpha/P_{\rm fus}$ | 3.52/17.59 | 1 % |
| Greenwald（ITER） | $1.19\times10^{20}$ | 1 % |
| $\beta_N$、$\beta_p$（ITER 基线） | 文献常引值 | $(1.4,2.1)$、$(0.4,0.9)$ |
| IPB98(y,2) / ITER89-P（ITER） | 常引值 | $(2.5,5.0)$ s / $(0.5,2.0)$ s |
| Martin 阈值（ITER） | 常引值 | $(20,90)$ MW |
| 指数松弛 | 闭式 | 相继偏离比 $=e^{-\Delta t/\tau}$（$10^{-12}$） |
| K-3 归一 | 闭式 | $10^{-12}$，形状无关 |
| 功率账 | 闭式 | 残差 $<10^{-12}$；4× 加密残差减半 |
| 体积 / 储能 | METIS 认证表（84 片） | 圆片 0.2 %；成形 $<17\%$；储能 12 % |
| 反应率 | METIS `zformsv`、TORAX、FUSE | $<10^{-12}$、机器精度、$<2\%$ |
:::

(phys06-asbuilt)=
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 0-D 内容与内核函数、C-ABI、Python 入口（2026-09-02 快照）。
:name: tbl-p06-asbuilt
:align: left

| 内容 | 内核函数（`zerod.rs`） | C-ABI（`fylite_rs_*`） | Python |
| :--- | :--- | :--- | :--- |
| 反应率、聚变功率 | `dt_reactivity`, `fusion_power` | `dt_reactivity`, `zerod_fusion_power` | `S.model.zerod` |
| 剖面、平均、体积 | `profile_value`, `volume_average`, `line_average`, `volume_ellipsoid` | `zerod_profile`, `zerod_averages`, `zerod_volume` | 同上 |
| 环电压 / 电感 | `loop_voltage_ohmic` | `zerod_loop_voltage`（out3） | `S.design.loop_voltage` |
| 波形 | `trapezoid`, `centre_waveform`, `actuator`, `phase_label` | `zerod_waveform`（which 0–5） | `Phases`, `Waveform` |
| Tier A | `evaluate` | `zerod_evaluate`（par 10） | `S.model.zerod()` |
| Tier B | `tau_e`, `p_lh_threshold`, `te0_for_energy`, `predict` | `zerod_predict`（pred 5，out 8 列） | `S.model.zerod(predict=True)` |
| 界限 | `greenwald_density`, `q_cylindrical`, `limits` | `zerod_limits`（out9） | `S.design.feasible` |
| 磁通预算 | `flux_budget` | `zerod_flux_budget`（out7） | `S.design.discharge` |
:::

(phys06-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（源码逐字引）〕Bosch–Hale {cite}`boschhale1992fusion`；IPB98(y,2) {cite}`iterphysicsbasis1999ch2`；
ITER89-P {cite}`yushmanov1990scalings`；Martin 阈值 {cite}`martin2008power`；Greenwald {cite}`greenwald1988density`；
Troyon {cite}`troyon1984mhd`；Ejima {cite}`ejima1982volt`。

〔一手文献（编者对应，源码未注）〕Spitzer 电阻率 {cite}`spitzer1953transport,huba2013nrl`；捕获修正与
环电感 {cite}`wesson2004tokamaks`；$q_{\rm cyl}$、$(1-\rho^2)^p$ 族 {cite}`uckan1990guidelines`；
指数积分器 {cite}`hochbruck2010exponential`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references-physics.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕METIS 认证表与 `zformsv` / `zbornesv` 转录 {cite}`artaud2018metis`；TORAX {cite}`citrin2024torax`；
FUSE {cite}`meneghini2024fuse`——均为 oracle 口径。

〔本仓选择〕`edge_frac = 0.05`、峰化缺省、波形 2 % / 1 % 残余与 $10^{-9}$ s 地板、$P_{\rm loss}=P_{\rm heat}$、
显式耦合、K-3 归一、圆权 + 椭圆体积。证据为 {numref}`tbl-p06-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
