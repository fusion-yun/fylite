---
title: 加热与电流驱动 (Auxiliary Heating and Current Drive)
subtitle: 中性束（阻止、Stix 慢化、屏蔽、束驱动电流）、聚变 α、低杂波链、ICRH 少数离子链、快波与电子回旋链
---

(phys09-intro)=
# 引言：约化 H&CD 模型的四要素 (Introduction)

〔范围〕本章详述**辅助加热与电流驱动的约化模型**：中性束注入
（NBI）、聚变 $\alpha$ 加热与快 $\alpha$、低杂波电流驱动（LHCD）、离子回旋少数离子加热（ICRH）、
快波电流驱动（FWCD）与电子回旋加热 / 电流驱动（ECRH / ECCD）。辐射、电子—离子交换与体积分
在 {ref}`phys10-intro`。

〔出处姿态〕〔实现〕模块头部："物理转录自 METIS（CEA，CeCILL-C）及其所引的公开文献；拟合
保留自身单位（截面 cm²、温度 eV），在出口处一次换算。"仓根 `NOTICE` 把 加热与电流驱动层列为 METIS
的**派生作品**，并逐条声明与 METIS 的**有意偏离**（{ref}`phys09-nbi-deviations`、{ref}`phys09-icrh`）。
RABBIT {cite}`weiland2018rabbit` 在实现中被命名为**保真档**而非来源（"RABBIT 的实现是 MPCDF 许可、
不可获得，此处无一物源自它"）。因此本章的一手文献分三类：实现逐字引的论文、实现只给姓名 /
上游文件名而由编者补出处的公式（标核验状态）、以及**实现未注且编者亦无法归属**者（明列）。

〔共同形态〕〔已确立〕本章各源都可分解为吸收功率 × 归一沉积形状 × 电子/离子分配 ⇒ 驱动效率
（`GK-TMT-06` §共同形态，跨仓）；其中 Stix 慢化与临界能量是 NBI、ICRH 少数离子与 $\alpha$ 三类
**共用**的底层，本内核也确实**共享同一份代码**（`slowing_down`、`ion_power_fraction`；Python 侧的这两个包装自 T-4 第十七刀起在内核仓神谕树 `tests/oracles/beam.py`）。

〔常数〕〔实现〕$e=1.602176634\times10^{-19}$ C；$m_p=1.67262192\times10^{-27}$ kg（"不是更多 CODATA 位——
$2.2\times10^{-9}$ 的质量差在驱动电流上是 $1.1\times10^{-9}$"）；`AMU` $=1.66053873\times10^{-27}$ kg（METIS 的
`phys.ua`；"束模型按质子质量称其离子（上游 `z0nbistop` 如此），少数离子模型按原子质量单位（上游
`z0icrh` 如此），两者差 0.8 %"）；$m_ec^2=510998.95$ eV。

(phys09-slowing)=
# 共用底层：Stix 慢化 (The Shared Foundation — Stix Slowing-Down)

〔实现〕`slowing_down_charged(T_e, n_e, A_b, Z_{\rm eff}, zsum, Z_b)`（下限 $T_e\ge1$ eV、$n_e\ge10^{16}$、
$Z_{\rm eff}\ge1$、$zsum\ge10^{-6}$）：

$$
E_c=\max\!\Big(14.8\,T_e\,(A_b^{3/2}\,zsum)^{2/3},\,30\ \text{eV}\Big),\qquad
E_\gamma=\max\!\Big(14.8\,T_e\,(2\sqrt{A_b}Z_{\rm eff})^{2/3},\,30\Big),\qquad
zsum=\sum_j\frac{n_jZ_j^2}{n_eA_j}
$$ (eq-p09-ecrit)

$$
\tau_s=6.27\times10^{8}\,\frac{A_b\,T_e^{3/2}}{n_e[\text{cm}^{-3}]\,Z_b^2\,\ln\Lambda}\ [\text{s}],\qquad
\ln\Lambda=\max\!\Big(15.2-\tfrac12\ln\frac{n_e}{10^{20}}+\ln\frac{T_e}{10^3},\,5\Big)
$$ (eq-p09-taus)

〔出处〕临界能量与慢化时间是 Stix 的结果 {cite}`stix1972heating`（实现只注 METIS `zicd0.m`；
"$E_c$ 与 $Z_b$ 无关……教科书结果"）；$\tau_s$ 的 $1/Z_b^2$ 实现强调"对 $\alpha$ 不是 1：$Z_b=2$ 使慢化时间
短**四倍**……对 ASTRA 抓住"。$E_c$ 下限 30 eV "如 METIS `zicd0.m`"。库仑对数式**实现未注出处**
（与 NRL 手册电子—离子 $\ln\Lambda$ 的 $T_e>10$ eV 支 {cite}`huba2013nrl` 同型，常数 15.2 对应 $n$ 以 $10^{20}$、
$T$ 以 keV 计〔已确立：可由 $24-\ln(\sqrt{n_{\rm cm^{-3}}}/T_{\rm eV})$ 换单位核算〕）。

〔离子份额〕〔实现〕`ion_power_fraction(E_c,E_b)`（Wesson 2nd ed. p. 227；METIS `zfract0.m`），$x=E_b/E_c$，$s=\sqrt x$：

$$
f_i(x)=\frac1x\left[\frac13\ln\frac{1-s+x}{(1+s)^2}+\frac{2}{\sqrt3}\Big(\arctan\frac{2s-1}{\sqrt3}+\frac\pi6\Big)\right]
=\frac1x\int_0^x\frac{\dd y}{1+y^{3/2}}
$$ (eq-p09-fi)

〔已确立〕这是 Stix 的 $H(x)$ 积分的闭式 {cite}`stix1972heating,wesson2004tokamaks`（实现引 Wesson 第 2 版
页码；本书目录取第 3 版）。ICRH 链的 `hh` "就是 `ion_power_fraction`——同一个 Stix 积分"。

〔有效慢化时间〕〔实现〕`effective_slowing_time`（METIS `zsupra0.m`；nbi.py："D. Moreau 的全能量形式"，无文献）：
$\tau_{\rm eff}=\tau_s\big[1+\frac{\ln((x_0+1)^2/(x_0^2-x_0+1))}{3x_0^2}-\frac{2(\arctan\frac{2x_0-1}{\sqrt3}+\arctan\frac1{\sqrt3})}{\sqrt3x_0^2}\big]$，
$x_0=\sqrt{E_b/E_c}$；决定快离子储能 $W_{\rm fast}=p_{\rm dep}\tau_{\rm eff}/2$。〔未核验〕闭式与 Moreau 原文的对应
未查证。

〔场离子和〕〔实现〕`field_ion_sum`（内核入口；Python 包装同上）：主离子 + 一种杂质在给定 $Z_{\rm eff}$ 下由准中性闭合出 $n_i/n_e$、$n_z/n_e$，
再算 $zsum$；缺省（D + C）给"教科书 $E_c\approx18.6T_e$"（测试 $18.6\pm0.1$）。

(phys09-nbi)=
# 中性束注入 (Neutral-Beam Injection)

(phys09-nbi-stopping)=
## 阻止截面 (Beam-Stopping Cross-Sections)

〔Janev–Boley–Post 拟合〕〔实现〕`stopping_cross_section`（"Janev, Boley & Post 1989"）：
$\hat e=\ln(E/A/10^3)$、$\hat n=\ln(n_e[\text{cm}^{-3}]/10^{13})$、$\hat t=\ln(T_e/10^3)$，氢基 12 项多项式 $s_1$
（系数 `S1`），杂质修正 $\text{corr}=2n_{\rm He}S_Z(2)+\sum_kn_kZ_k(Z_k-1)S_Z(Z_k)$，

$$
\sigma_{\rm stop}=10^{-4}\cdot10^{-16}\,\frac{e^{s_1}}{e^{\hat e}}\Big(1+\frac{\text{corr}}{n_e}\Big)\ [\text{m}^2]
$$ (eq-p09-janev)

杂质多项式 $S_Z$ 在 $Z=2,6,8,26$ 制表，其间线性混合。〔出处〕Janev 等 1989 年的束穿透截面拟合
{cite}`janev1989penetration`〔凭记忆：卷页待核验〕；系数与 METIS `z0nbistop.m` 逐字相同。

:::{important}
〔声明的偏离〕〔实现〕"METIS 的 `z0nbistop.m` 对氢基多项式取指数但对杂质多项式不取，而后者在约
45 keV/amu 以下变负——这会让加碳**降低**束阻止，不物理……按 `s1` 一样读作对数（`Exp`，缺省）给出碳在
$Z_{\rm eff}\sim2$ 时 $\sigma_{\rm eff}/\sigma_H\sim1.25$，与文献中 20–30 % 的增强一致。"METIS 档的杂质形式保留
逐字转录供对拍。
:::

〔METIS 三通道模型〕〔实现〕METIS 档的阻止模型：电子碰撞电离（`z0signbi`，7 项 $\ln T_e$ 多项式除以
$4.3766\times10^5\sqrt{E}$）、离子碰撞电离（7 项 $\ln E$ 多项式）、电荷交换
$\sigma_{cx}=1.467\times10^{-18}(1-e^{-E/9.26})/E$ m²，与幂律 $2.0198\times10^{-21}(E/10^6/A)^{-0.9027}n_e$ 按
$w=\tfrac12(1+\tanh(E-1836T_e))$ 混合（"混合是 METIS 的，且非装饰：快中性计算在束不快于电子热速时失效"）。
nbi.py 称电子通道为 "Riviere/Janev" {cite}`riviere1971penetration`〔凭记忆〕；7 项系数、$4.3766\times10^5$、
幂律常数**实现只注 METIS**，编者未能归属到一手文献。$\tanh$ 的宗量以 eV 计、未归一（实际为 $E=1836T_e$ 处的阶跃）。

(phys09-nbi-deposit)=
## 弦衰减与沉积 (Chord Attenuation and Deposition)

〔实现〕`deposit_ray`：沿射线样本 $\lambda_k^{-1}$（$\psi_N>1$ 处为 0；离子密度**取 $n_i=n_e$**），梯形累积光深
$\tau_k$，$T_k=e^{-\tau_k}$，$\Delta_k=T_{k-1}-T_k$ 按样本中点 $\psi_N$ 装箱到壳层（越界者**装进最外壳而非丢弃**，
使 $\sum\text{absorbed}+\text{shinethrough}=1$ 到舍入）；`pitch_weighted` 累加 $\Delta_k\bar\xi_k$。〔已确立〕
$\dd\Upsilon/\dd\ell=-n_e\sigma_{\rm eff}\Upsilon$ 的一维衰减方程（`GK-TMT-06`）。

〔实现〕`beam_deposit`：$3\times3$ 均匀矩形足迹（METIS 取三个水平偏移与三个高度）；每条射线自
$r_{\rm start}$ 以切向半径 $R_{\rm tan}=\abs{R_{\rm tan,0}+\delta_r}$ 直线穿越，$\psi_N$ 由 $\psi(R,Z)$ **双线性插值**
（`psin_along`，格外 $+\infty$）；俘获角 $\xi(R)=R_{\rm tan}/R$（"对直线射线精确"）；$R_{\rm tan}\ge r_{\rm start}$ 的射线
拒绝（"从未进入等离子体……在此停下而不是沉积零"）。

(phys09-nbi-current)=
## 束驱动电流 (Beam-Driven Current)

〔电子屏蔽〕〔实现〕`electron_shielding(f_t,Z_{\rm eff})`（Lin-Liu & Hinton 1997）{cite}`linliu1997shielding`，
$x_t=f_t/(1-f_t)$：

$$
G=\frac{x_t[(0.754+2.21Z+Z^2)+x_t(0.348+1.243Z+Z^2)]}{1.414Z+Z^2+x_t(0.754+2.657Z+2Z^2)+x_t^2(0.348+1.243Z+Z^2)},\qquad
F_{\rm shield}=1-\frac{1-G}{Z}
$$ (eq-p09-shield)

$f_t\in[10^{-4},0.95]$ 钳制。$G\to1$（高捕获份额）、$G\to0$（碰撞平板）。

〔速度积分与电流〕〔实现〕`current_integral`（"Start–Cordey / Stix，METIS `zicd0.m`"）：
$ev=1+\tfrac23v_\gamma^3/v_c^3$，$I=\int_0^1\frac{v_0}{v_c}\big(\frac{u^3}{1+u^3}\big)^{ev}\dd\ell$（梯形，$u=(v_0/v_c)\ell$）；
`beam_current`：

$$
v_{\rm eff}=\min\!\Big(v_c\Big(\frac{v_0^3+v_c^3}{v_0^3}\Big)^{ev-1}I,\ v_0\Big),\quad
j_{\rm raw}=e\frac{p_{\rm dep}}{eE_b}\tau_s\,\xi\,v_{\rm eff},\quad
j_{\rm NBI}=\text{mult}\cdot F_{\rm shield}\cdot j_{\rm raw}\cdot\min\!\big(1+\tanh(10(\abs\xi-\mu_{\rm trap})),1\big)
$$ (eq-p09-jnbi)

$\mu_{\rm trap}=\sqrt{2r/(R+r)}$。〔出处〕束驱动电流的慢化—屏蔽理论 {cite}`start1980beam`〔凭记忆〕、
{cite}`stix1972heating`；实现强调"两种抑制是不同物理：`shield` 是电子回流；`fi_trap` 是束离子自己是否
通行——只有在局域俘获边界之上发射的离子才携带电流"，且 $\tanh(10\cdot)$ 是"**平滑阶跃**，不是物理宽度"（无出处）。

〔首轨损失〕〔实现〕`first_orbit_loss`（METIS `zicd0.m`；**仅反向注入**）：$\rho_L=\sqrt{2Am_pEe}/(ZeB_{\rm loc})$
（精确，nbi.py 注 METIS 用氘标定常数）、香蕉宽 $\Delta_{\rm ban}=\sqrt{r/R}\,q\rho_L$、土豆宽
$\Delta_{\rm pot}=R(2q\rho_L/R)^{2/3}$，$\rho_L+\text{width}+r>a_{\rm edge}$ 即损失。

(phys09-nbi-pressure)=
## 快离子压强与力矩 (Fast-Ion Pressure and Torque)

〔实现〕$W=p_{\rm dep}\tau_{\rm eff}/2$，各向同性 $p=\tfrac23W$（"切向束不是各向同性的"）；俯仰保持拆分
$p_\parallel=2W\xi^2$、$p_\perp=W(1-\xi^2)$（$p_\parallel/2+p_\perp=W$ 精确）；力矩密度 $\tau_\phi=p_{\rm dep}(2/v_b)\xi R$
（"即时，本档把全部力矩沉积在离子出生处"）。三者实现给出推导但无文献。

(phys09-nbi-deviations)=
## 与 METIS 的声明偏离（NBI） (Declared Deviations from METIS)

〔实现 / NOTICE〕(1) 弦在细路径网格上行进、$\psi_N$ 双线性读自 `PSIRZ`，而非圆磁面上的圆—线求交
（`z0nbipath`）；(2) 束是 EAST 正离子源记录的全 / 半 / 三分之一能量分量之**和**，而非单一能量；(3) 拉莫半径精确；
(4) 捕获份额用 Lin-Liu & Miller {cite}`linliu1995trapped`〔凭记忆〕而非 METIS 的 $0.95\sqrt x$ 回退。
未移植：束—束与束—快离子阻止（`z0nbistopfast`）。

(phys09-alpha)=
# 聚变 α 加热与快 α (Alpha Heating and Fast Alphas)

〔实现〕`alpha_heating`："两样已有之物的装配，不是新模型"：出生率 $S=n_Dn_T\expval{\sigma v}_{\rm BH}(T_i)$
（Bosch–Hale，{ref}`phys06-fusion`；{cite}`boschhale1992fusion`），$p=SE_\alpha$，$E_\alpha=3.5409$ MeV；分配用
同一 Stix 拆分 {eq}`eq-p09-fi` 于 $E_\alpha$、$E_c$ 取 $A=4$、$Z=2$。"不是快离子输运模型：$\alpha$ 在出生处慢化。"

〔快 α〕〔实现〕`alpha_fast_ions`：**稠态**，$\tau_{\rm res}=\tfrac{\tau_s}3\ln(1+(E_\alpha/E_c)^{3/2})$（"从出生慢化到静止、
对电子**与**离子的时间；只用 $\tau_s$ 高估快密度约 40 %——ASTRA 自己的 `nalph` 正是如此"），$n_{\rm fast}=S\tau_{\rm res}$，
$W$、$p$ 同上。〔已确立〕$\tau_{\rm res}$ 由 $\dd E/\dd t=-\tfrac{2E}{\tau_s}(1+(E_c/E)^{3/2})$ 积分即得；实现无文献。

〔ASTRA oracle〕〔实现〕ITER 15 MA 燃烧参考例（CORSICA/ASTRA，07-Apr-10 包，153 点）：功率密度逐点 3 %、积分 0.3 %；
离子份额比 ASTRA（Post 1984 分配）低 11–14 %（测试钉 $[0.84,0.94]$）；快 $\alpha$ 密度比 $[0.95,1.02]$（实测 0.968–0.994）；
快 $\alpha$ 压强比 $[0.93,1.05]$。

(phys09-lh)=
# 低杂波电流驱动 (Lower-Hybrid Current Drive)

〔实现〕"一条有据可查的物理链而非射线追踪 / Fokker–Planck 码（LSC、GENRAY/CQL3D 在范围外）"：

$$
n_{\parallel,\rm acc}=\frac{\omega_{pe}}{\omega_{ce}}+\sqrt{1+\frac{\omega_{pe}^2}{\omega_{ce}^2}},\qquad
T_{\rm res}=\frac{m_ec^2}{2\xi^2n_\parallel^2}\ (\xi\approx3),\qquad
\eta_k\propto\frac{T_e}{n_e},\qquad
I_{\rm lau}=\frac{\eta_{CD}P}{\bar n_eR_0}
$$ (eq-p09-lh)

可及性条件 〔已确立〕 是慢波在 $\omega_{LH}\ll\omega\ll\omega_{ce}$ 的标准结果 {cite}`stix1992waves`〔凭记忆〕；
朗道共振 $c/n_\parallel=\xi v_{th,e}$；效率标度 $T_e/n_e$ 与 $\eta_{CD}\equiv\bar n_eR_0I/P$ 是 Fisch 的电流驱动理论
{cite}`fisch1987theory`——实现只写 "Fisch-type"。沉积形状为高斯（"建模选择——有限宽单程阻尼层"），带端 $n_\parallel$
的两个共振半径给出宽度与 $\sigma_j$ 包络；可及性门"作用于形状、在归一之前，使到不了的功率不被静默地向内重分配"。
$\eta_{CD}$ **必须由调用方给出**（lh.py：EAST 量级 $10^{19}$ A/W/m²，"不缺省"）；$\bar n_e$ 在此是**体积**平均。
〔已知限度〕〔实现〕EAST 发射 $n_\parallel\approx1.8$–2.4，单程共振在 4.8–8.8 keV——高于等离子体，
`upshift = 1.0` 下找不到共振面；无离子阻尼、无电子捕获修正、无快电子压强。

(phys09-icrh)=
# 离子回旋少数离子加热 (ICRH Minority Heating)

〔实现〕METIS `z0icrh.m`（`icrh_model = PION_fit-Stix`）的转录：共振层来自**真实场**，少数离子尾来自 Stix 解析分布
{cite}`stix1975fast`（实现逐字引 NF 15 (1975) 737），电子份额来自尾部留下的快离子含量（"L.-G. Eriksson"，无文献）。
"不是 Fokker–Planck 码（PION、SPOT）"；"仅稳态——METIS 缺省 `transitoire = 1` 把电子通道积分成整个放电的 ODE；
要瞬态的调用方自己积 $\dd W/\dd t=p_{el}-W/\tau_{\rm eff}$"。

〔共振层〕〔实现〕回旋场 $B=2\pi f/(95.5\times10^6Z/A)$（"$e/m_p$ 取三位，与 METIS 同"）；41 点中平面弦
$\abs B=\abs{B_0}\sqrt{(x_a/qR_0)^2+(R_0/r)^2}$（极向项"是 METIS 自己的……在低场下把 2 % 与 10 % 分开"），$q$ 由
METIS 单调 $q$ 剖面 `z0qp.m`（Wesson p. 114 eq. (3.4)）；谐波**由程序选择**（D 少数在 D/DT 中：二、三次谐波取离
中心场更近者；否则基波场超出最大场时取二次）；层落在弦端且偏差 $>5\%$ 时拒绝（`NoResonanceInThePlasma`——
"METIS 的 `min` 静默返回端点，其 `xres` 上限使之看似边缘沉积"）。METIS oracle：$R_{\rm res}$ 最差 1.2 %、中位 0.07 %
（32 行）。

〔尾部与分配〕〔实现〕$E_c$、$E_\gamma$ 按 {eq}`eq-p09-ecrit` 于层处（$Z_g=Z_{\rm min}h$：上游把少数离子电荷乘以谐波数）；
加热体积份额 $\text{frac}=\mathrm{clamp}(fact\cdot2a\kappa\,dr/S_{\rm pol},0.05,1)$，$dr=R_0k_\parallel\sqrt{2T_\parallel e/(\text{AMU}A_g)}/(2\pi f)$、
$T_\parallel=E_\gamma/8$、`fact` = 1（T）或 3.2；$p_m\le1$ kW/m³ 时无尾（上游捷径）。Stix 分布在 101 点对数速度网格：

$$
\zeta=\frac{p_m\tau_s}{3n_{\rm mino}eT_e},\qquad
f_k=\exp\!\Big[-\frac{2E_k}{eT_e(2+3\zeta)}\big(1+\text{inter}\cdot H(E_k/e_j)\big)\Big]
$$ (eq-p09-stix)

（$e_j$、inter 见实现；$H$ 即 {eq}`eq-p09-fi`）；归一 $2\pi\int vf\,\dd v=n_{\rm mino}$；热成分以"最陡指数斜率"减去；
$W_{\rm fast}=\pi A_g\text{AMU}(M[f]-M[f_{th}])V_{\rm mino}$；

$$
p_{el}=\mathrm{clamp}\!\Big(\frac{2W_{\rm fast}}{\tau_s},0,P_{\rm abs}\Big)\ (\text{Eriksson}),\qquad p_{ion}=P_{\rm abs}-p_{el}
$$ (eq-p09-eriksson)

"电子通道不是慢化份额"。剖面：以 $x_{\rm res}$ 为中心、$1/e$ 半宽 = 加热体积份额的高斯（METIS 认证档 40 行
`width/fracmino = 1.000`），电子/离子份额**径向均匀**（上游简化）。METIS oracle（稠态行）：$p_{el}$ 比 0.955–1.079、
$W_{\rm fast}$ 比 0.948–1.015（门 $[0.85,1.15)$）。

〔拒绝〕〔实现〕`MinorityConcentrationMissing`（$c_{\min}$ 无缺省）、`NotAPlasma`、`RippleLossNotModelled`
（拒绝而非近似：认证例 `TS_SA_test` 上忽略波纹使电子通道高 33 %）、`NoResonanceInThePlasma`。
〔声明的偏离〕〔NOTICE〕层处等离子体取**调用方的剖面**（METIS 用 0-D 峰化形）；仅稳态支；波纹拒绝；层外拒绝。

(phys09-fwcd)=
# 快波电流驱动 (Fast-Wave Current Drive)

$$
\eta_{FW}=(0.0080\,T_{e0}[\text{keV}]+0.0021)\frac{6}{5+Z_{\rm eff}}\times10^{20}\ [\text{A W}^{-1}\text{m}^{-2}],\qquad
I=\frac{P\eta_{FW}}{n_{e0}R_0}\mathrm{sign}(\text{dir})
$$ (eq-p09-fwcd)

〔实现〕METIS `zicd0.m` 携带的**中心电子温度线性拟合**（`fitetafwcd.m`，对 JFT-2M / DIII-D / Tore Supra 实测回归；
20 个拟合点在测试中逐字保留）；ITER Physics Basis 第 6 章 §3.5 报告"超过 $0.04\times10^{20}$……随 $T_{e0}$ 线性"
{cite}`iterphysicsbasis1999ch6`（实现逐字引 NF 39 (1999) 2495 p. 2512）。未移植：上游的电流剖面启发式
（"Meo & Nguyen"，无认证例）。"打开它就改变了 ICRH 功率账——METIS 中 `fwcd != 0` 把全部热 ICRH 功率改道进快波"。

(phys09-ec)=
# 电子回旋加热与电流驱动 (ECRH / ECCD)

〔实现〕三个问题："**在哪**——几何精确；**多少电流**——调用方选择的效率拟合；**多少功率**（单程吸收份额）——
缺省**不建模**（可借用的束追踪码许可受限、移植停止），`eccd_current` 取**已吸收**功率。"与 METIS 的差别：
METIS 的 EC 沉积半径是**输入**（`cons.xece`），此处由发射几何与场**算出**。

〔冷共振与几何〕〔实现〕$B_{\rm res}=2\pi fm_e/(ne)$（"教科书 $f_{ce}[\text{GHz}]=27.99B[\text{T}]$"；"**冷**且非相对论——
两效应都是 $O(T_e/m_ec^2)$"）；$R_{\rm res}=\abs{B_0}R_0/B_{\rm res}$（真空 $1/R$ 场，"有意"）；发射角约定按 ITER / IMAS
（FUSE 的 `pol_tor_angles_2_vector` {cite}`meneghini2024fuse`），直线传播与圆柱 $r=R_{\rm res}$ 求交（"折射 $\sim\omega_{pe}^2/\omega^2$，
百分量级"）。

〔折射率与光深〕〔实现〕$N_O^2=1-\omega_{pe}^2/\omega^2$、$N_X^2=1-\frac{\omega_{pe}^2}{\omega^2}\frac{\omega^2-\omega_{pe}^2}{\omega^2-\omega_{pe}^2-\omega_{ce}^2}$（$N^2\le0$ 即截止，
`BelowCutoff`）〔已确立：冷等离子体 Appleton–Hartree 的垂直传播极限 {cite}`stix1992waves`〕；光深按 Bornatici 等
{cite}`bornatici1983ec`（实现逐字引 NF 23 (1983) 1153 表 12）、以 Sabri 等 {cite}`sabri2012ec` 表 I 的形式转录：

$$
\tau_O=\frac{\pi^2n^{2(n-1)}}{2^{n-1}(n-1)!}N_O^{2n-1}\frac{\omega_{pe}^2}{\omega_{ce}^2}\Big(\frac{T_e}{m_ec^2}\Big)^n\frac{R}{\lambda},\qquad
\tau_X=\frac{\pi^2n^{2(n-1)}}{2^{n-1}(n-1)!}A_n\frac{\omega_{pe}^2}{\omega_{ce}^2}\Big(\frac{T_e}{m_ec^2}\Big)^{n-1}\frac{R}{\lambda}
$$ (eq-p09-tau)

吸收份额 $1-e^{-\tau}$（同源 Eq. (10)；"$\tau>3$ 即光学厚"）。斜入射基波 X 模未移植（`ObliqueFundamentalXNotPorted`）。
共振宽度 $\dd R/R=\sqrt{(\abs{N_\parallel}u)^2+(u^2/2)^2}$，$u^2=2T_e/m_ec^2$（Doppler 与相对论两项；无文献）。

〔ECCD 效率〕〔实现〕`eccd_efficiency`（"METIS 携带的 Giruzzi 拟合（私人通讯；G. Giruzzi, NF 27 (1987) 2069）
{cite}`giruzzi1987eccd`，$Z_{\rm eff}$ 依赖取 Lin-Liu GA-A24257 {cite}`linliu2003eccd`，捕获粒子减损随沉积半径与
发射角增长"）：

$$
\eta_{EC}=\frac{10^{20}}{1+100/T_e[\text{keV}]}\Big[1-\Big(1+\frac{5+Z}{3(1+Z)}\Big)(\sqrt2\mu)^{\frac{5+Z}{1+Z}}\Big]\frac{6}{1+4\big(1-\sqrt{\tfrac{2ax}{R_0+ax}}\big)+Z},\qquad
\mu=\sqrt{\frac{ax(1+\cos\theta_{\rm pol})}{R_0+ax\cos\theta_{\rm pol}}}
$$ (eq-p09-eccd)

$I=P_{\rm abs}\eta_{EC}/(n_eR_0)$。〔未核验〕内部结构（$1/(1+100/T)$、指数 $(5+Z)/(1+Z)$、$\sqrt2$、$6/(\cdots)$）
只归于"私人通讯"的拟合，编者无法与 Giruzzi 1987 逐项对应。METIS oracle：$I/I^{\rm METIS}$ 0.944–1.192，中位 1.020
（$\ge25$ 行）。**EC 链未在公开入口上导出**（截至 2026-09-02）。

(phys09-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **约化档给的是矩**（总功率、峰位、宽度），不是剖面细节（`GK-TMT-06`）；与射线追踪 / Fokker–Planck 的比对须固定平衡
   与剖面并按矩比。
2. **标定常数是模型的一部分**：$4.3766\times10^5$、幂律、$\tanh(10\cdot)$、`fact = 3.2`、$T_\parallel=E_\gamma/8$、ECCD 拟合系数、
   FWCD 线性拟合——均为 METIS 的标定，不可脱离其模型组合外推。
3. **NBI**：$n_i=n_e$ 于阻止；首轨损失仅反向；无束—束阻止；足迹 $3\times3$ 均匀。
4. **α**：出生处慢化，无快 $\alpha$ 输运；$P_\alpha$ 分配比 ASTRA 低 11–14 %（已量化）。
5. **LH**：单程共振，无上移模型；$\eta_{CD}$ 必须外给；EAST 参数下常**无共振面**。
6. **ICRH**：仅稳态；波纹机器拒绝；电子/离子份额径向均匀；层外拒绝。
7. **EC**：冷共振（$O(T_e/m_ec^2)$ 位移未计）、直线传播、真空 $1/R$ 场；单程吸收缺省不建模；斜入射 X1 未移植。
8. **FWCD** 打开会改变 ICRH 功率账（METIS 约定）。

(phys09-verify)=
# 验证锚点 (Verification Anchors)

:::{table} H&CD 的外部 oracle 锚点（内核单元测试；参考表随仓冻结并逐字节校验）。
:name: tbl-p09-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| $E_c/T_e$（D + C） | 教科书 18.6 | $\pm0.1$ |
| 碳杂质增强 | 文献 20–30 % | 比 $\in(1.15,1.40)$ |
| α 功率密度（ITER 15 MA） | ASTRA 153 点 | 逐点 $\pm5\%$，积分 $\pm1\%$，80–120 MW |
| α 离子份额 | ASTRA（Post 1984） | 比 $\in[0.84,0.94]$ |
| 快 α 密度 / 压强 | ASTRA | $[0.95,1.02]$ / $[0.93,1.05]$ |
| ICRH 共振层 $R$、$x$、谐波 | METIS 认证表 32 行 | $<3\%$、$<0.075$、相等 |
| ICRH 尾成分 | METIS `nmino, fracmino, ecrit, taus` | 3 / 5 / 10 / 10 % |
| ICRH $p_{el}$、$W_{\rm fast}$ | METIS 稠态行 | $[0.85,1.15)$ |
| ICRH 剖面峰位 / 宽度 | METIS `picrh_x_peak/width` | 0.05 / 5 % |
| ECCD 驱动电流 | METIS `ieccd`（$\ge25$ 行） | $[0.85,1.25)$，中位 1.020 |
| EC 光深排序与量级 | Bornatici / Sabri 图 | $\tau_{X2}>\tau_{O1}>\tau_{X3}$；X2 $\in(15,40)$ |
| O 模截止密度（70 GHz） | 闭式 | $6.08\times10^{19}\pm10^{18}$ |
| FWCD 效率 | 20 个实测点 | 比 $\in[0.70,1.30)$，中位 5 % 内 |
| LH 驱动电流 | $\eta P/(\bar n_eR_0)$ | $10^{-9}$ |
:::

(phys09-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 加热与电流驱动各项产出的源项，及其所落的 fyo 数据集。
:name: tbl-p09-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 束阻止截面与逆平均自由程 | —（沉积计算的中间量） | `scenario.model.nbi` |
| Stix 慢化、电子 / 离子功率分配、有效慢化时间 | `fyo:core_sources`：束的电子与离子能量源 | `nbi.deposit` |
| 束沉积（弦衰减） | `fyo:core_sources`：沉积剖面 | `nbi.deposit` |
| 束驱动电流与首轨损失 | `fyo:core_sources`：电流源 | `nbi.deposit` |
| 快离子压强与力矩 | `fyo:core_profiles` 的快离子压强；`fyo:core_sources` 的动量源 | `nbi.deposit` |
| 聚变 $\alpha$ 加热 | `fyo:core_sources`：$\alpha$ 能量源 | `assembly.alpha_si` |
| 低杂波（可达性、共振、效率、沉积） | `fyo:core_sources`：LH 电流与功率 | `scenario.model.lh` |
| 离子回旋少数离子加热与快波驱流 | `fyo:core_sources`：ICRH 功率与 FWCD 电流 | 内核 `heating.rs` 有算子而**无门**、无宿主调用；Python 装配 `scenario.model.ic` 自 2026-09-06 归内核仓测试树（`tests/oracles/ic.py`） |
| 电子回旋（模型在，未接出） | —（未接到 fyo 面） | — |
:::

(phys09-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（实现逐字引）〕RABBIT 保真档 {cite}`weiland2018rabbit`；METIS {cite}`artaud2018metis`；Stix 少数离子分布
{cite}`stix1975fast`；Lin-Liu–Hinton 屏蔽 {cite}`linliu1997shielding`；Giruzzi ECCD {cite}`giruzzi1987eccd`；Lin-Liu
$Z_{\rm eff}$ 依赖 {cite}`linliu2003eccd`；EC 光深 {cite}`bornatici1983ec,sabri2012ec`；FWCD 量级 {cite}`iterphysicsbasis1999ch6`；
Bosch–Hale {cite}`boschhale1992fusion`；Wesson 分配 {cite}`wesson2004tokamaks`。

〔一手文献（编者对应，实现只给姓名 / 上游文件）〕Stix 慢化 {cite}`stix1972heating`；Janev–Boley–Post 截面
{cite}`janev1989penetration`；Riviere {cite}`riviere1971penetration`；Start–Cordey 束电流 {cite}`start1980beam`；
Lin-Liu–Miller 捕获份额 {cite}`linliu1995trapped`；LH 可及性与冷等离子体折射率 {cite}`stix1992waves`；Fisch 电流驱动
{cite}`fisch1987theory`；库仑对数 {cite}`huba2013nrl`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔实现只给姓名、编者未能归属〕Eriksson 电子份额 $2W_{\rm fast}/\tau_s$；Moreau 全能量 $\tau_{\rm eff}$；Meo–Nguyen FWCD 剖面
（未移植）；ECCD 拟合的内部结构（"私人通讯"）。这些在本章标 〔未核验〕。

〔转引（转录）〕METIS `z0nbipath.m`、`z0nbistop.m`、`z0signbi.m`、`zicd0.m`、`zfract0.m`、`zsupra0.m`、`z0icrh.m`、`z0qp.m`、
`zboot0diff.m`、`fitetafwcd.m`（CEA/IRFM，CeCILL-C）；ASTRA / CORSICA ITER 15 MA 参考例；ITER / IMAS / FUSE 发射角约定。

〔本仓选择〕杂质多项式的 `Exp` 读法；能量分量求和；精确拉莫半径；Lin-Liu–Miller 捕获份额；波纹与层外拒绝；
$R_{\rm tan}\ge r_{\rm start}$ 拒绝；越界沉积装最外壳。证据为 {numref}`tbl-p09-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
