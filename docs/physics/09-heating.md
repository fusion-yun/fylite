---
title: 加热与电流驱动 (Auxiliary Heating and Current Drive)
subtitle: 中性束（阻止、Stix 慢化、屏蔽、束驱动电流）、聚变 α、低杂波链、ICRH 少数离子链、快波与电子回旋链、EC 与 LH 共用的射线追踪（冷射线核、托卡马克介质、全相对论 EC 吸收与沉积）
---

(phys09-intro)=
# 引言：约化 H&CD 模型的四要素 (Introduction)

〔范围〕本章详述**辅助加热与电流驱动的约化模型**：中性束注入
（NBI）、聚变 $\alpha$ 加热与快 $\alpha$、低杂波电流驱动（LHCD）、离子回旋少数离子加热（ICRH）、
快波电流驱动（FWCD）与电子回旋加热 / 电流驱动（ECRH / ECCD）。辐射、电子—离子交换与体积分
在 {ref}`phys10-intro`。本章另述电子回旋与低杂波共用的射线追踪（{ref}`phys09-ray`）：冷等离子体射线轨迹、
托卡马克介质、全相对论 EC 吸收与 $\bar\psi$ 壳沉积。

〔出处姿态〕〔实现〕模块头部："物理转录自 METIS（CEA，CeCILL-C）及其所引的公开文献；拟合
保留自身单位（截面 cm²、温度 eV），在出口处一次换算。"仓根 `NOTICE` 把 加热与电流驱动层列为 METIS
的**派生作品**，并逐条声明与 METIS 的**有意偏离**（{ref}`phys09-nbi-deviations`、{ref}`phys09-icrh`）。
RABBIT {cite}`weiland2018rabbit` 在实现中被命名为**保真档**而非来源（"RABBIT 的实现是 MPCDF 许可、
不可获得，此处无一物源自它"）。因此本章的一手文献分三类：实现逐字引的论文、实现只给姓名 /
上游文件名而由编者补出处的公式（标核验状态）、以及**实现未注且编者亦无法归属**者（明列）。

〔射线追踪层的出处姿态〕〔实现〕射线追踪层（{ref}`phys09-ray`）**不是 METIS 的派生作品**，是依公开文献的清净室实现：
冷色散出自 Stix {cite}`stix1992waves`，全相对论吸收出自 Albajar 等 {cite}`albajar2007ec` 与 TRAVIS
{cite}`marushchenko2014travis`，射线方程与多组分冷色散的写法同 BORAY {cite}`xie2022boray,wang2026boray3d`。BORAY 的
源码（BSD-3-Clause）只用于核对，射线核不是它的逐行移植（坐标、导数方式、发射规则均不同）；GRAY、GENRAY、TORAY、LSC
的源码未读。GENRAY 的输出（随 BORAY 仓分发）作 B 类参照数据。

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

〔与射线追踪层的分工〕〔实现〕上面这条单程链不变。低杂波的轨迹另由射线追踪层给出（{ref}`phys09-ray`：Stix 多组分冷色散、
格栅发射按群速度定法向分量的符号、声明的边缘反射），它补上单程链没有的几何上移——轴对称使 $RN_\phi$ 守恒，而 $N_\parallel$
随 $R$ 与极向场沿射线变化。〔2026-09-12 修订〕射线追踪层对低杂波现在给出**轨迹、沿射线的电子 Landau 吸收与一维准线性
Fokker–Planck 的自洽沉积**（{ref}`phys09-lh-ray`），并经 `code/rf_ray` 的 LH 行接出（天线谱读 DD 的 `lh_antennas/antenna/row/n_phi`
与 `row/power_density_spectrum_1d`）；驱动电流按每壳定态分布的 $-e n_e v_{te}\int u f\,du$ 给出（一维、局地，取作壳平均），`core_sources` 落电子加热与 `j_parallel`。

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

〔两档〕〔实现〕本节是**闭式档**。沿射线的吸收与沉积是另一档（{ref}`phys09-ray-ecabs`）；两档经 {eq}`eq-p09-tau` 的
低温极限互为判据。

〔冷共振与几何〕〔实现〕$B_{\rm res}=2\pi fm_e/(ne)$（"教科书 $f_{ce}[\text{GHz}]=27.99B[\text{T}]$"；"**冷**且非相对论——
两效应都是 $O(T_e/m_ec^2)$"）；$R_{\rm res}=\abs{B_0}R_0/B_{\rm res}$（真空 $1/R$ 场，"有意"）；发射角约定按 ITER / IMAS
（FUSE 的 `pol_tor_angles_2_vector` {cite}`meneghini2024fuse`），直线传播与圆柱 $r=R_{\rm res}$ 求交（"折射 $\sim\omega_{pe}^2/\omega^2$，
百分量级"）。

〔折射率与光深〕〔实现〕$N_O^2=1-\omega_{pe}^2/\omega^2$、$N_X^2=1-\frac{\omega_{pe}^2}{\omega^2}\frac{\omega^2-\omega_{pe}^2}{\omega^2-\omega_{pe}^2-\omega_{ce}^2}$（$N^2\le0$ 即截止，
`BelowCutoff`）〔已确立：冷等离子体 Appleton–Hartree 的垂直传播极限 {cite}`stix1992waves`〕；光深按 Bornatici 等
{cite}`bornatici1983ec` 表 IV 与式 (3.1.37)（垂直传播；表 XII 是其斜射版）：

$$
\tau_O=\frac{\pi^2n^{2(n-1)}}{2^{n-1}(n-1)!}N_O^{2n-1}\frac{\omega_{pe}^2}{\omega_{ce}^2}\Big(\frac{T_e}{m_ec^2}\Big)^n\frac{L_B}{\lambda_0},\qquad
\tau_X=\frac{\pi^2n^{2(n-1)}}{2^{n-1}(n-1)!}A_n\frac{\omega_{pe}^2}{\omega_{ce}^2}\Big(\frac{T_e}{m_ec^2}\Big)^{n-1}\frac{L_B}{\lambda_0}
$$ (eq-p09-tau)

$$
A_n=N_X^{2n-3}\Big(1+\frac{\omega_{pe}^2/\omega_{ce}^2}{n\,(n^2-1-\omega_{pe}^2/\omega_{ce}^2)}\Big)^2,\qquad
\lambda_0=\frac{2\pi c}{\omega_{ce}},\qquad L_B=R\quad(B\propto1/R)
$$ (eq-p09-tau-an)

〔实现〕原文的线形平均 $\langle D_n\rangle$、$\langle A_n\rangle$ 在 $n>2$ 时等于 1 与 $A_n$，在 $n\le2$ 时于稀薄极限趋于它们；实现取这一
极限。$\lambda_0$ 是**回旋频率** 上的真空波长，在第 $n$ 次谐波上是波自身波长的 $n$ 倍。

:::{important}
〔更正 2026-09-11〕〔实现〕本式最初按 Sabri 等 {cite}`sabri2012ec` 表 I 的重印转录。该重印把 $\lambda_0$ 写成波长 $\lambda$，
并漏掉 $A_n$ 的平方，于是 $n\ge2$ 的光深**深 $n$ 倍**（O1 不受影响）。发现者是射线追踪层的全相对论吸收
（{ref}`phys09-ray-ecabs`）：沿 $1/R$ 板积分后与重印式之比在低温低密处恰为 $1/n$。按原文改正后，O1、O2、X2、X3
四支比值的 $T_e\to0$ 外推都在 1 的 $1.1\times10^{-4}$ 之内（{numref}`tbl-p09-verify`）。以 $B=2.25$ T、
$n_e=3\times10^{19}$ m⁻³、$R=0.88$ m、$T_e=3$ keV 为例，$\tau_{X2}$ 由 26.1 改为 14.7，$\tau_{X3}$ 由 1.06 改为 0.36，
$\tau_{O1}=4.1$ 不变。原判据中"X2、X3 与重印的图对得上"的比对随之撤销：那张图与重印同出一源。
:::

吸收份额 $1-e^{-\tau}$（重印本 Eq. (10)；"$\tau>3$ 即光学厚"）。斜入射基波 X 模未移植（`ObliqueFundamentalXNotPorted`）。
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
（$\ge25$ 行）。**闭式档的 EC 链未在公开入口上导出**（截至 2026-09-11）；射线追踪档经门 `code/rf_ray` 接出
（{ref}`phys09-ray-door`）。

(phys09-ray)=
# 射线追踪：EC 与 LH 共用的冷射线核 (Ray Tracing — the Shared Cold Ray Core)

〔范围〕〔实现〕射线追踪层回答"波往哪里走、在哪里被吸收"：冷等离子体里一条笔形射线的轨迹（折射、截止、反射、低杂波的
汇合），以及沿射线的电子回旋吸收与按 $\bar\psi$ 壳的功率沉积。电子回旋与低杂波**共用同一个积分器**，只换色散函数。
本层不含（2026-09-12 起）：~~束宽随传播的演化、衍射与聚焦~~（已实现：锥形射线族与束追踪，见本章
"束宽"一节）；~~伴随法 ECCD~~（已实现，见"伴随法 ECCD"一节）；~~低杂波的吸收与准线性电流~~（已实现：电子 Landau 吸收、
一维准线性 Fokker–Planck 与自洽回路，见 {ref}`phys09-lh-ray`）；**余：二维谱 `power_density_spectrum_2d`、反射模型参数、一维准线性模型之外的 $(5+Z_{\rm eff})$ 与陷俘修正**。

(phys09-ray-core)=
## 射线方程与两种色散 (Ray Equations and the Two Dispersion Functions)

〔实现〕射线沿色散面 $D(\vb x,\vb N)=0$ 以实空间弧长 $s$ 为参数积分：

$$
\dv{\vb x}{s}=\sigma\,\frac{\partial D/\partial\vb N}{\abs{\partial D/\partial\vb N}},\qquad
\dv{\vb N}{s}=-\sigma\,\frac{\partial D/\partial\vb x}{\abs{\partial D/\partial\vb N}},\qquad
\sigma=-\operatorname{sgn}\left.\pdv{D}{\omega}\right|_{\vb k}
$$ (eq-p09-ray)

〔已确立〕这是几何光学的哈密顿射线方程 {cite}`stix1992waves`。$\sigma$ 使 $s$ 沿时间正向增长（沿射线
$\dd t\propto-\partial D/\partial\omega$），因此射线方向与 $D$ 的符号和整体尺度无关。BORAY 以实时间积分同一组方程
{cite}`xie2022boray`，二者等价。

〔射线自检〕〔实现〕每个接受点报出 $\delta\omega/\omega=-D/(\omega\,\partial D/\partial\omega)$，精确射线上为零；
超过 `dw_tol`（缺省 $10^{-5}$）即以"频率漂移"停止。

〔两种色散函数〕〔实现〕

1. **Appleton–Hartree**（仅电子，按名取 O / X 支；电子回旋从真空起步）：$D=\vb N\cdot\vb N-N^2_{\rm mode}$，

   $$
   N^2=1-\frac{2X(1-X)}{2(1-X)-Y^2\sin^2\theta\pm\sqrt{Y^4\sin^4\theta+4(1-X)^2Y^2\cos^2\theta}}
   $$ (eq-p09-ah)

   `+` 为 O 支、`−` 为 X 支，$X=\omega_{pe}^2/\omega^2$，$Y=\omega_{ce}/\omega$，$\theta$ 为 $\vb N$ 与 $\vb B$ 的夹角；
   真空中 $D=N^2-1$，射线核在真空里正则。
2. **Stix 多组分**（电子加至多 4 种离子，支由发射根决定；低杂波用它）：

   $$
   D=F\Big[S\,u^2-\big(RL+PS-N_\parallel^2(S+P)\big)u+P\,(R-N_\parallel^2)(L-N_\parallel^2)\Big],\qquad
   u=N_\perp^2,\qquad F=\prod_s\Big(1-\frac{\Omega_s^2}{\omega^2}\Big)
   $$ (eq-p09-stixd)

   其中 $R,L=1-\sum_s\omega_{ps}^2/[\omega(\omega\pm\Omega_s)]$，$P=1-\sum_s\omega_{ps}^2/\omega^2$，$S=(R+L)/2$，
   $\Omega_s=q_sB/m_s$ 带号。方括号内与 BORAY 式 (15) 逐项相同 {cite}`xie2022boray`；$F$ 消去各组分的一阶回旋极点。
   〔实现〕BORAY 只乘最靠近共振的那一个组分的因子，本层乘全部在场组分的因子——零点集相同，尺度之差被 $\sigma$ 与
   $\abs{\partial D/\partial\vb N}$ 的归一吸收。

〔已确立〕两种形式在纯电子等离子体中是同一张色散面：Appleton–Hartree 支上的点使 Stix 的 $D$ 归零
（{numref}`tbl-p09-verify`）。

〔发射〕〔实现〕电子回旋沿给定方向发射，取该支在发射点的 $\abs{\vb N}$，两个指向角的约定同 {ref}`phys09-ec` 的直线估计。
低杂波在等离子体内发射：切向折射率由格栅给定，法向分量取指定根，其符号按**群速度** 指入等离子体来取。原因是慢波低杂波
在垂直 $\vb B$ 方向为反向波：静电极限下 $D\approx SN_\perp^2+PN_\parallel^2$，且 $S>0>P$。实现另记两条限制："真空中
两根重合、$\partial D/\partial\vb N=0$，Stix 射线必须在等离子体里起步"；"Stix 射线不能走进 $n_e\to0$"。

(phys09-ray-numerics)=
## 积分、导数与停止 (Integration, Derivatives and Stops)

〔实现〕

- 在笛卡儿坐标 $(x,y,z)$ 中积分，轴对称介质按 $R=\sqrt{x^2+y^2}$ 求值，以避开柱坐标奇点；轴对称下
  $xN_y-yN_x$（即 $RN_\phi$）的守恒由判据检查。
- $\partial D/\partial\vb x$、$\partial D/\partial\vb N$、$\partial D/\partial\omega$ 一律中心差分，步长依次为 $10^{-5}$ m、
  $10^{-7}\max(1,\abs{\vb N})$、$10^{-6}$（相对）。因此介质必须给出 C¹ 以上的场（{ref}`phys09-ray-medium`）。
- 四阶 Runge–Kutta，步长加倍估误差：一整步与两个半步之差的最大分量除以 15 记为 $e$。接受时取两个半步的结果并加
  Richardson 修正 $(\vb y_{1/2}-\vb y_{1})/15$，下一步长乘 $\min(0.9(\mathrm{tol}/e)^{1/5},5)$；拒绝时步长乘
  $\max(0.9(\mathrm{tol}/e)^{1/5},0.2)$。步长钳在 $[10^{-7},10^{-2}]$ m，缺省容差 $10^{-10}$。实现未注出处。
- 停止原因逐条报出而不作错误：路程上限、出域、出等离子体、共振、群速度为零、步长塌缩（步长到下限而误差仍超容差
  $10^3$ 倍）、频率漂移、反射次数到顶。发射时拒绝：出介质、无方向、进截止、在共振上、两根为复（汇合点之外）、
  离子多于 4 种、发射折射率不在色散面上。

(phys09-ray-medium)=
## 托卡马克介质 (The Tokamak Medium)

〔实现〕

- **ψ 图**：张量积自然三次样条。节点存 $\psi$、$\psi_{RR}$、$\psi_{ZZ}$、$\psi_{RRZZ}$，格内求值同时给出值与两个一阶导，
  整体 C²。实现注："双线性插值会让射线在格线上折角"。
- **磁场**：$B_R=-\sigma_{Bp}\,\partial_Z\psi/(gR)$，$B_Z=\sigma_{Bp}\,\partial_R\psi/(gR)$，$B_\phi=F(\bar\psi)/R$。
  $g$ 为 ψ 的每单位弧度数：每弧度图 $g=1$，整圈图 $g=2\pi$，由平衡文档的 `fylite:psi_convention` 声明。
- **极向场的指向 $\sigma_{Bp}$ 由文档推出，不写死**（2026-09-11）：安培定律要求环向电流在**自己外侧**给出
  $B_Z<0$（$+\phi$ 电流；电流环外的场与轴上反向），而 $B_Z=\sigma_{Bp}\,\partial_R\psi/(gR)$，于是

  $$
  \sigma_{Bp}=-\operatorname{sign}(I_p)\,\operatorname{sign}(\psi_{\rm bnd}-\psi_{\rm axis})
  $$ (eq-p09-sigmabp)

  门在平衡文档声明 `ip` 时按此式取号并记入说明；**未声明 `ip` 时取 $+1$ 并在说明里写明这是假设**——
  不从没有取向声明的文档里读出取向。
  〔更正〕〔实现〕本页此前写"极向场的符号只影响电流驱动的方向"，**那句不成立**：翻的只是**极向**那一半，
  $\vb B$ 的方向因此转动，$\cos\theta$ 随之改变，$N_\parallel$ 与多普勒移动的共振位置都受影响。
  改正的依据是一次跨实现对比（设计方的一次射线追踪运行；逐点读数记在内核的设计页，属受限语料不在本页）：
  取 $+1$ 时本层 $N_\parallel$ 在共同流面上系统性偏低约四分之一，按 {eq}`eq-p09-sigmabp` 取号后与对方的
  $N_\parallel$ 相对差 $1.5\times10^{-4}$、轨迹差亚毫米。★这一条在本层自带的 48 条判据下**看不见**：
  它们的解析夹具都不声明 $I_p$，且夹具自己按同一个符号造 $\vb B$。
- **剖面**：$F$、$n_e$、$T_e$、$n_i$、$T_i$ 在 $\bar\psi$ 上以 pchip（保形分段三次 Hermite）插值，与剖面拟合所用的 pchip
  逐位相同。
- **边界以外**：按边界值**与斜率** 延拓（C¹）。以 $d=\abs{\bar\psi-1}$、声明的衰减宽度 $w$（`sol_width`，$\bar\psi$ 单位）：

  $$
  v(d)=v_1\exp\!\Big(a\,d-\frac{d^2}{2w^2}\Big),\quad a=\frac{v_1'}{v_1};\qquad
  F(d)=F_1+F_1'\,w\,\big(1-e^{-d/w}\big)
  $$ (eq-p09-sol)

  私有通量区——$\bar\psi<1$ 而位于边界轮廓竖直范围之外——按同一规则处理。两条规则都由判据量出：只接值不接斜率时，
  "剖面斜率的跳变就是射线方程右端的跳变，没有步长能在它两侧满足容差"；按点在多边形内判私有区时，边界多边形的弦落在
  凸的最外闭合面之内，边缘约 1 mm 被误判，$n_e$ 与 $\vb B$ 同时跳变。
- **声明的边缘反射**（低杂波用）：射线在声明面 $\bar\psi_{\rm refl}$ 上向外穿越时，于步内二分定位到 $10^{-12}$ m，按
  $\nabla\bar\psi$ 的差商**再投影到垂直 $\vb B$** 后镜像；于是反射保持 $N_\parallel$、$\abs{\vb N}$ 与 $D$。反射次数上限缺省 64。
  〔本仓选择〕边缘反射是一个**模型** ，不是射线算出的物理：射线光学不能处理边缘反射，声明面的位置与次数上限都是假设。

(phys09-ray-ecabs)=
## 全相对论 EC 吸收与沉积 (Fully Relativistic EC Absorption and Deposition)

〔实现〕Maxwell–Jüttner 电子上的吸收系数按 Albajar 等 {cite}`albajar2007ec` 式 (2a)(4)(5)(10)，与 TRAVIS
{cite}`marushchenko2014travis` 及 BORAY-3D {cite}`wang2026boray3d` 式 (20) 同形：

$$
\alpha=\frac{\omega_{pe}^2}{c\,\omega}\,\frac{\pi}{2}\,\frac{\mu^2}{e^{\mu}K_2(\mu)}\sum_{n}\frac{q_n}{\sqrt{1-N_\parallel^2}}
\int_{-1}^{1}\!\dd t\;e^{-\mu(\gamma-1)}\,\abs{\hat{\vb e}\cdot\vb V_n^*}^2,\qquad \mu=\frac{m_ec^2}{T_e}
$$ (eq-p09-alpha)

$$
n_0=\bar\omega\sqrt{1-N_\parallel^2},\quad q_n=\sqrt{(n/n_0)^2-1},\quad
u_\parallel=\frac{(n/n_0)N_\parallel+q_n t}{\sqrt{1-N_\parallel^2}},\quad
\gamma=\frac{n}{\bar\omega}+N_\parallel u_\parallel,\quad
\vb V_n=\Big(\frac{nJ_n(b)}{b}u_\perp,\ iJ_n'(b)\,u_\perp,\ J_n(b)\,u_\parallel\Big),\quad b=\bar\omega N_\perp u_\perp
$$ (eq-p09-alphav)

其中 $\bar\omega=\omega/\omega_{ce}$。求和从第一个满足 $n>n_0$ 的谐波起。〔已确立〕共振椭圆只在 $nY\ge\sqrt{1-N_\parallel^2}$
处存在 {cite}`albajar2007ec`，故斜射波在冷层的低场侧被吸收，且吸收边沿随 $\abs{N_\parallel}$ 增大而移向低场；
$N_\parallel^2\ge1$ 时共振曲线不闭合，实现把该点报为"系数不适用"。

〔极化〕〔实现〕$\hat{\vb e}$ 取**冷电子介电张量的零向量**（$S=1-X/(1-Y^2)$，$D=-XY/(1-Y^2)$，$P=1-X$；$e^{-i\omega t}$ 约定，
R 波 $e_y=ie_x$），并按 Albajar 式 (14) 归一到单位 Poynting 通量 $\abs{\mathrm{Re}\big(\hat{\vb e}^*\times(\vb N\times\hat{\vb e})\big)}=1$。
〔本仓选择〕弱相对论极化（Krivenski–Orefice 张量）未取；BORAY-3D 注明两种均可 {cite}`wang2026boray3d`。

〔求积〕〔实现〕$t$ 上 48 点 Gauss–Legendre；从第一个共振谐波起至多求 6 个谐波，某谐波最低共振能量处
$e^{-\mu(\gamma-1)}<10^{-30}$ 即截止；$e^{\mu}K_2(\mu)$ 由 4 段 × 32 点 Gauss–Legendre 积到
$\operatorname{arccosh}(1+60/\mu)$；$J_n$、$J_n'$ 取合成诊断层的 Bessel 函数。沿射线 $\dd\tau/\dd s=\alpha$；相邻两个接受点之间，
以线性插值的 $\vb x$、$\vb N$ 作复合 Simpson 积分，片长不超过 `h_max`。实现注："共振层比射线步窄（$\dd R/R\sim T_e/m_ec^2$，
keV 下数毫米），在射线自己的点上求积会跨过它"。

〔沉积〕〔实现〕每个 Simpson 样点 $j$ 取走射线余功率的 $1-e^{-\dd\tau_j}$，并按该点的 $\bar\psi$ 装入壳层：

$$
\Delta P_j=P_{j-1}\big(1-e^{-\dd\tau_j}\big),\qquad P_j=P_{j-1}-\Delta P_j,\qquad
\sum_{\rm shells}\Delta P+P_{\rm outside}+P_{\rm left}=P_0
$$ (eq-p09-deposit)

〔已确立〕守恒由构造逐项相消而得；$P_{\rm left}=P_0\,e^{-\tau}$ 与报出的 $\tau$ 出自同一次积分。〔本仓选择〕落在壳层范围之外
（或介质无 $\bar\psi$ 处）的吸收单列为 $P_{\rm outside}$，不并入最外壳——这与 {ref}`phys09-nbi-deposit` 的"越界装进最外壳"
不同。壳体积由磁面描迹在**同一张 ψ 图** 上求得，与中性束沉积用同一套面；功率密度 $p_e=\Delta P/\Delta V$。

## 伴随法 ECCD (Adjoint ECCD)

〔实现〕沉积走到哪一点，就在那一点按伴随法取该点的电流驱动效率，逐点乘以该点吸收的功率，装进同一批 $\bar\psi$ 壳：
Lin-Liu 等 {cite}`linliu2003eccd` 的**香蕉区**伴随响应，陷俘修正按该文的形式；捕获份额与
$\langle\,\rangle$ 所需的面量由**射线所在的同一个介质**描迹得到（壳心上的磁面，角点数 `trap_theta`，缺省 128），
不另取一套面。某壳的面描不出闭合弹跳轨道时按名拒绝——"没有闭合轨道的面没有可平均的响应"。

〔拒绝〕〔实现〕**$Z_{\rm eff}$ 没有缺省**：效率约按 $1/(Z_{\rm eff}+5)$ 走，静默取 1 等于替这团等离子体
做了一句物理断言。文档给出 $Z_{\rm eff}$ 剖面则按 $\bar\psi$ 取值，或由设置 `zeff` 给一个标量；两者都没有时拒绝。

〔已确立〕电流的**方向**跟着发射方向：环向角变号则驱动电流变号（门的判据即以此判）。总量、壳外量与逐壳量
三者相消到 $10^{-9}$ 相对。〔本仓选择〕香蕉区**以外**的碰撞修正与动量守恒修正不在本层（读作 L2 之外）；
效率的 B 类对比对着内核里的一份认证存档做，带宽记在那里（受限语料，不在本页）。

## 束宽：锥形射线族与束追踪 (Beam Width — a Cone of Rays, and Beam Tracing)

〔实现〕两档，都可选，互斥：

- **锥形射线族（L2）**：绕中心射线按高斯角强度 $I(\theta)\propto e^{-2\theta^2/\theta_d^2}$ 取若干环
  （`rf_rings` 环 × `rays_per_ring` 条，发散角 `divergence`），每条射线各自追踪、各自吸收，功率按环权相加。
  〔本仓选择〕它**不是**高斯束：锥自一点发出，只有远场，没有束腰、聚焦与衍射。射线码在 ITER 算例里正是用这种锥。
- **束追踪（L3）**：沿中心射线带一支复曲率 $\Psi=\partial\vb N/\partial\vb x$（笛卡尔 **3×3**）的矩阵 Riccati 方程，
  并加约束 $\Psi\vb v=\dd\vb N/\dd s$。取 3×3 而非横向 2×2 约化：经 $\Psi D_{NN}\Psi$ 把**射线自身的弯曲**带进束宽，
  那正是 2×2 约化漏掉的项。吸收把中心射线的光深按 Gauss–Hermite 截面（节点数 `beam_nodes`，缺省 5）分到各
  $\bar\psi$；束腰与其位置成对给出（`beam_waist` 与 `beam_focus`，都无缺省——单给束腰是"发射光学只说了一半"，拒绝）。
  窄到跌破一个真空波长时以 `ParaxialLimit` 停并报明。方法按旁轴 WKB 束追踪一系（Pereverzev 1998 的复曲率方程与
  其后 TORBEAM / 准光学各文；逐篇出处记在内核的设计页书目）。

〔判据〕〔实现〕L3 的判据是**解析的**，七条：真空像散束对 $1/(s-d-iz_R)$ 的九元全比（$1.1\times10^{-8}$）；
均匀磁化等离子体垂直传播的 O / X 远场曲率（$6.3\times10^{-8}$ / $2.8\times10^{-8}$）；抛物密度通道里的匹配束
（宽度不变）与半束腰的闭式呼吸；线性层斜入射的九元全比（$1.3\times10^{-8}$，过顶点再下行）；Gauss–Hermite 的
权和 · 对称 · 偶矩（$10^{-12}$ 内）；解析位形上的功率账（$3\times10^{-15}$）；以及**束对邻射线的 Jacobi 恒等式**
（样条介质上两套独立实现，$7.9\times10^{-6}$）。〔本仓选择〕束的 B 类实算对标没有可复算的输入（公开算例均未发表
平衡与束初值），故不做而记明；无像差阶之外（窄束的 $N_\parallel$ 谱展宽、截面上吸收不均）不在本层。

## 沉积映到输运梯子 (Depositing onto the Transport Ladder)

〔实现〕壳上的功率与电流可映到输运梯子上：平衡文档带绑定梯子时，按 `code/beam` 的**同一个守恒算子**写
`core_sources/source/0/profiles_1d/{electrons/energy, j_parallel}`；梯子上的瓦数与壳上的瓦数相等到 $10^{-9}$ 相对。
未绑梯子时按 $\bar\psi$ 网格落在壳上。〔已确立〕于是射线追踪档的输出可直接充当 1.5-D 输运的源项表
（{ref}`phys05-channels`），与闭式档的表格沉积走同一个接口。


(phys09-lh-ray)=
## 低杂波：电子 Landau 吸收、准线性 Fokker–Planck 与自洽回路 (Lower Hybrid — Landau Absorption, Quasilinear FP and the Self-Consistent Walk)

〔推导〕〔实现〕沿慢波射线的吸收只取**电子 Landau 阻尼**（用户裁定，2026-09-11；离子 Landau 与碰撞阻尼不在内）。
把 Maxwell 分布的纵向介电函数的反厄米部分加进 Stix 的 $P$ 元——公式从头推出而非抄录：

$$
\operatorname{Im}P \;=\; 2\sqrt{\pi}\,\frac{\omega_{pe}^2}{\omega^2}\,\zeta^3 e^{-\zeta^2},\qquad
\zeta=\frac{1}{N_\parallel\beta_{te}},\quad \beta_{te}=\frac{v_{te}}{c},\ v_{te}=\sqrt{T_e/m_e},
$$ (eq-p09-lh-imp)

沿射线的功率衰减率取在射线所走的**同一个** $D$ 上：$\alpha=2(\omega/c)\,\lvert D_i\rvert/\lvert\nabla_{\!N}D_r\rvert$，$D_i=\operatorname{Im}P\cdot\partial D/\partial P$，
$F$ 在比值里消去，$\nabla_N D_r$ 有闭式。★不能用垂直的 $k_I$——低杂波群速度几乎沿 $B$，垂直率约为沿射线率的 30 倍。
〔已确立〕这是 LSC / Bonoli–Englade 级的标准做法；判据：温度依赖逐位等于 $\zeta^3e^{-\zeta^2}$、冷极限指数归零、
均匀板上的精确指数、多程功率守恒。**谱隙量出来了**：5 keV 上 $N_\parallel$ 1.5→4.0 跨 $2.1\times10^6$ 倍，格栅峰值
$N_\parallel\approx2$ 处 $\alpha=0.138$ m⁻¹（7.3 m 才 e 折），故单靠 Maxwell 分布给的吸收是**下界**。

〔推导〕〔实现〕一维 $v_\parallel$ 准线性 Fokker–Planck 的定态由总平行流为零给出——一条累积积分，不是矩阵：

$$
\big(D_c+D_{ql}\big)f' + 2u\,D_c f = 0,\qquad D_c(u)=\frac{v_{te}^2/\tau}{1+\lvert u\rvert^3},\quad u=v_\parallel/v_{te},
$$ (eq-p09-lh-fp)

无射频时回到 Maxwell，强 $D_{ql}$ 处成平台。驱动效率（电流矩除以功率矩，单位 $-e n_e v_{te}$ 与 $n_e m_e v_{te}^2/\tau$）
的闭式**由同一模型推出**：平台 $[u_1,u_2]$ 上 $\eta\to(u_2^2-u_1^2)/(4\ln(u_2/u_1))$，窄带极限 $u_0^2/2$（四个带实测差 < 2 %）。
★**一次真失败改出来的拒绝**：驱动电流是分布的奇部之差，落到求和舍入之下时（$e^{-49}$ 对 $10^{-16}$）`efficiency()`
拒绝报数（$\lvert J\rvert\le10^3\times$ 舍入下限），余量由实测定。无陷俘、无 $E_\parallel$ 协同、无径向扩散——与原文同，
**比趋势不比数值**。

〔推导〕〔实现〕②↔③ 的闭合：吸收可读在任意平行分布上，$\operatorname{Im}P=-\pi\,\mathrm{sgn}(N_\parallel)\,(\omega_{pe}^2/\omega^2)\,\zeta^2 f'(\zeta)$，
代入 Maxwell 即回到 {eq}`eq-p09-lh-imp`（该恒等式作判据，4001/8001 点差 $4.4\times10^{-4}$ / $1.3\times10^{-4}$，随 $du^2$ 收敛）。
实测（5 keV，平台 $u\in[4,6]$）：共振落在平台内时 $\alpha$ 降到 Maxwell 的 $6.5\times10^{-5}$（**平台是透明的**），落在平台上沿外时
升到 $5.0\times10^8$ 倍——自洽吸收取决于波此前把功率放在哪里。

〔实现〕**自洽回路**：每壳的 $D_{ql}$ 由二分法定到 Fokker–Planck 的功率矩等于射线在该壳沉积的功率（守恒由构造保证），
再用得到的分布重算沿射线的吸收，Picard 迭代（可欠松弛）。实测：2 kW 下 7 步收敛，自洽 / Maxwell 吸收比 1.327；
**MW 级饱和**——一条射线、一个带宽 `lh_band`（在 $u$ 里的共振半宽，是**输入**：谱的速度宽度不是一条射线知道的）
能吸收的功率有上限，超过时出现周期 2 振荡，`converged = false` 如实报出，不做平滑。

〔实现〕**门（`code/rf_ray` 的 LH 行，2026-09-12）**：只绑 `lh_antennas` 的文档按 DD 的
`antenna/row/n_phi`（$N_\parallel$ 分 bin）与 `row/power_density_spectrum_1d`（相对权重，按 `n_phi` 梯形宽归一到
`antenna/power_launched/data`，各 row 均分）**每 bin 发一条慢波射线**（`rfray::Launch::stix`，大根，切向指标 $N_\phi\hat\phi+N_{pol}\hat t$，
$\hat t=\hat\phi\times\hat e_\psi$ 为发射点处 $\bar\psi$ 梯度定义的极向切向——本仓的声明，与 DD 的一致性 `[TBD]`；法向沿 $-\hat e_\psi$、能量沿法向），发射点 `row/position/{r,z,phi}`，频率 `antenna/frequency`；介质带一种离子（`lh_ion_a` 2.5 · `lh_ion_z` 1，
密度取 `core_profiles/profiles_1d/fylite:ion_density`，未绑则 $n_e/Z$ 并在说明里写明）。`deposit` 打开时逐射线走自洽回路，
`core_sources/source/0/profiles_1d/electrons/energy` 落在沉积壳上（带 $\bar\psi$ 网格，宿主按 `sources = table` 重采样）；
`j_parallel` 取每壳收敛态分布的 $-e n_e v_{te}\int u f\,du$（$v_{te}=\sqrt{2T_e/m_e}$，回路自己的速度单位；矩落在舍入下限内时报 0），
取作壳平均、按 $F$ 的符号写成环向，事实 `i_driven`；归一化效率按壳报出（`lh_drive`、`lh_u_res`）。实测（解析算例 3 keV、1 MW）：
吸收 0.904 MW 驱动 0.083 A/W——一维模型的数。
〔B 类〕GENRAY 的四条 EAST 2.45 GHz 射线以 `lh_antennas` 文档重发（每射线一 row，实测 GENRAY 切向指标的极向分量 ≤ 0.02，
故单 `n_phi` 足以陈述发射；`ip` 推出 $\sigma_{Bp}=-1$）：整个首程 $(R,Z)$ 差 $\le1.1\times10^{-4}$ m、$N_\parallel$ 差 $\le1.1\times10^{-3}$。

(phys09-ray-door)=
## 门与输出 (The Door and Its Outputs)

〔实现〕门 `code/rf_ray` 读平衡文档（ψ 图、F 表、边界、ψ 规范、磁轴）、剖面（$\bar\psi$ 网格上的 $n_e$、$T_e$）与电子回旋
发射表（位置、两个指向角、频率、模式 ±1、功率），逐束发射并追踪；或读低杂波天线表（{ref}`phys09-lh-ray`）逐 bin 发射。
{numref}`tbl-p09-rfray-door` 列出其设置与输出。

:::{table} `code/rf_ray` 的设置、字段与事实（2026-09-12；括号内为缺省值）。
:name: tbl-p09-rfray-door
:align: left

| 类别 | 名称 | 内容 |
| :--- | :--- | :--- |
| 设置 | `s_max`、`ds_max`、`tol`、`sol_width` | 路程上限（20 m）、最大步长（$10^{-2}$ m）、容差（$10^{-10}$）、刮削层衰减宽度（0.02） |
| 设置 | `deposit`、`rf_shells`、`h_max`、`n_theta` | 打开吸收与沉积（关）、壳数（50）、Simpson 片长（$10^{-4}$ m）、壳面描迹的角点数（181） |
| 设置 | `current_drive`（或 `eccd`）、`zeff`、`trap_theta` | 打开伴随法 ECCD（关；须 `deposit` 同开）、$Z_{\rm eff}$ 标量（**无缺省**，文档给剖面时按 $\bar\psi$ 取）、陷俘面的角点数（128） |
| 设置 | `rf_rings`、`rays_per_ring`、`divergence` | 锥形射线族的环数（0 = 只中心射线）、每环射线数（8）、发散角 |
| 设置 | `beam_waist`、`beam_focus`、`beam_nodes` | 束追踪（L3）的束腰与其位置（**成对，无缺省**；与 `rf_rings` 互斥）、截面 Gauss–Hermite 节点数（5） |
| 字段 | `rays`、`beams` | 每个接受点（束号, $s$, $R$, $Z$, $\phi$, $N_\parallel$, $\abs{\vb N}$, $\bar\psi$）；每束（束号, 最深 $\bar\psi$, 终点 $s$, 最大 $\abs{\delta\omega/\omega}$, 点数, 停止码） |
| 字段（`deposit` 打开时） | `shell_edges`、`shell_volume`、`power_shell`、`p_e`、`absorption` | 壳边；壳体积；每束每壳功率（W）；各束合计的功率密度（W m⁻³）；每束（束号, $\tau$, 吸收份额, 壳外功率） |
| 字段（`current_drive` 打开时） | `current_shell` | 每束每壳的驱动电流（A） |
| 字段（束宽两档） | `cone`、`beam_width` | 锥的每条射线（束号, 环, 倾角, 方位, 权, $\tau$, 吸收份额）；每个接受点的两轴束宽（m） |
| 事实（`deposit` 打开时） | `power_launched`、`power_absorbed`、`power_left`、`power_not_traced` | 前者等于后三者之和 |
| 事实（`current_drive` 打开时） | `current_driven`、`current_outside` | 总驱动电流与落在壳外的部分（逐壳之和加壳外量等于总量，$10^{-9}$ 相对） |
| 设置（LH 行） | `lh_ion_a`、`lh_ion_z` | 介质的一种离子的质量数（2.5）与电荷（1） |
| 设置（LH 行，`deposit` 打开时） | `lh_band`、`lh_u_max`、`lh_nodes`、`lh_iters`、`lh_tol`、`lh_relax` | 共振带在 $u$ 里的半宽（0.4，输入）、FP 网格半宽（12）与点数（2001）、自洽回路的最多步数（20）、相对容差（$10^{-4}$）、欠松弛（1） |
| 字段（LH 行） | `rays`、`lh_bins` | 同上（第一列为 bin 号）；每 bin（bin, $N_\parallel$, 发射 W, 吸收 W, 剩余 W, 收敛） |
| 字段（LH 行，`deposit` 打开时） | `power_shell`、`j_shell`、`lh_drive`、`lh_u_res`、`core_sources/…/{electrons/energy, j_parallel}` | 每壳吸收功率（W）与沿 $B$ 的驱动电流密度（A m⁻²）；壳上功率加权的 $D_{ql}/D_c$；共振 $u$；电子加热与环向 `j_parallel`（带 $\bar\psi$ 网格） |
| 事实（LH 行） | `n_bins`、`n_traced`、`p_launched`、`p_absorbed`、`p_outside`、`p_left`、`lh_converged`、`n_saturated`、`lh_band`、`i_driven` | 发射 = 吸收 + 壳外 + 剩余（含未发射的 bin）；回路是否逐射线收敛；饱和壳数；总驱动电流（A，环向） |
:::

〔拒绝〕〔实现〕`current_drive`（或 `eccd`）现已实现（见上节），但**不给 $Z_{\rm eff}$ 时按名拒绝**，
且**不与 `deposit` 同开时拒绝**——"驱动电流是吸收功率乘局地效率，没有沉积就没有可驱动的功率"。
`rf_rings` 与 `beam_waist` 同开时拒绝（锥与束是两种束宽模型，不叠）。
EC 与 LH 文档同绑时拒绝（一次一种波）；LH 行缺 `row/n_phi`、缺 `row/position` 或谱无正权时按名拒绝。模式不是 ±1 时拒绝
（"模式是色散的一个支，不作取整"）。某一束的发射被拒绝时，记为该束的说明，其余各束照常追踪。

(phys09-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **约化档给的是矩**（总功率、峰位、宽度），不是剖面细节（`GK-TMT-06`）；与射线追踪 / Fokker–Planck 的比对须固定平衡
   与剖面并按矩比。
2. **标定常数是模型的一部分**：$4.3766\times10^5$、幂律、$\tanh(10\cdot)$、`fact = 3.2`、$T_\parallel=E_\gamma/8$、ECCD 拟合系数、
   FWCD 线性拟合——均为 METIS 的标定，不可脱离其模型组合外推。
3. **NBI**：$n_i=n_e$ 于阻止；首轨损失仅反向；无束—束阻止；足迹 $3\times3$ 均匀。
4. **α**：出生处慢化，无快 $\alpha$ 输运；$P_\alpha$ 分配比 ASTRA 低 11–14 %（已量化）。
5. **LH（闭式档）**：单程共振，无上移模型；$\eta_{CD}$ 必须外给；EAST 参数下常**无共振面**。射线追踪层给出 LH 轨迹（含几何上移）、
   电子 Landau 吸收、一维准线性沉积与其驱动电流（{ref}`phys09-lh-ray`；一维局地量）。
6. **ICRH**：仅稳态；波纹机器拒绝；电子/离子份额径向均匀；层外拒绝。
7. **EC（闭式档）**：冷共振（$O(T_e/m_ec^2)$ 位移未计）、直线传播、真空 $1/R$ 场；光深式 {eq}`eq-p09-tau` 只到
   $T_e/m_ec^2$ 最低阶——1 keV 下全相对论板积分比它低 2.4 %（O1）、3.5 %（X2）、6.5 %（X3）；斜入射 X1 未移植。
8. **FWCD** 打开会改变 ICRH 功率账（METIS 约定）。
9. **射线追踪**（2026-09-11 修订）：轨迹用冷色散，热修正未计；EC 吸收用**冷极化**（弱相对论极化未取）；
   束宽有两档但**只到无像差阶**（窄束的 $N_\parallel$ 谱展宽与截面上吸收不均不在内，截止附近停于 `ParaxialLimit`）；
   伴随 ECCD **只到香蕉区**（区外的碰撞与动量守恒修正不在本层）；**LH 的吸收只取电子 Landau、准线性模型是一维的**
   （无陷俘、无 $E_\parallel$ 协同、无径向扩散；驱动电流是局地定态分布的矩，取作壳平均；共振带宽 `lh_band` 是输入；MW 级饱和如实报出）；
   边缘反射是声明的模型；离子至多 4 种（更多时按名拒绝，归并规则未定）；中心差分导数要求介质 C¹。
   ★**极向场的指向由文档的 `ip` 推出**，文档不声明时取 $+1$ 并在说明里写明是假设（{eq}`eq-p09-sigmabp`）。
   ★GENRAY 在 EAST 上的 X2 射线比本层早 12 mm 到达半吸收点（冷极化是最可能的差源，〔推测〕未证实）。

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
| EC 光深排序与量级 | Bornatici 表 IV（3 keV、2.25 T、$3\times10^{19}$ m⁻³） | $\tau_{X2}>\tau_{O1}>\tau_{X3}$；X2 $\in(10,20)$、O1 $\in(2,9)$、X3 $\in(0.2,0.6)$ |
| EC 光深闭式 ↔ 全相对论板积分 | 两者之比在 125 / 250 eV 的 Richardson $T_e\to0$ 极限（O1、O2、X2、X3） | $\abs{\text{极限}-1}<10^{-3}$（实测 $\le1.1\times10^{-4}$），斜率为负 |
| 闭式的密度因子 | 同上，$\omega_{pe}^2/\omega^2$ 由 0.005 到 0.1 | 比值漂移 $<3\times10^{-3}$ |
| O 模截止密度（70 GHz） | 闭式 | $6.08\times10^{19}\pm10^{18}$ |
| FWCD 效率 | 20 个实测点 | 比 $\in[0.70,1.30)$，中位 5 % 内 |
| LH 驱动电流 | $\eta P/(\bar n_eR_0)$ | $10^{-9}$ |
| 射线：两种色散同一张面 | Appleton–Hartree 支上的点代入 Stix $D$（斜射 5°–85°，$X$、$Y$ 在 1 两侧） | 相对残差 $<10^{-12}$ |
| 射线：真空与线性密度板 | 直线传播；O 支 Snell 转折 $x_t=L\cos^2\theta_0$ 与返回点；X 支转折的解析根 | 真空偏移 $10^{-9}$ m；转折 $10^{-6}L$、返回 $10^{-5}L$、Snell 不变量 $10^{-9}$ |
| 射线：轴对称守恒 | 环向角动量 $xN_y-yN_x$（EC）、$RN_\phi$（LH） | 漂移 $10^{-7}$（相对）；$\abs{\delta\omega/\omega}<10^{-7}$ |
| 射线：LH 汇合与快波截止 | 由色散系数单独求出的判别式零点与较小根零点，逐个转折点 | $10^{-6}$ m，转折后所在的根一致 |
| 射线：样条介质 | Solov'ev 解析梯度；规范（每弧度 / 整圈）；刮削层延拓规则 | 最细网格 $<10^{-4}$、每级 $\ge4$ 倍；介质 $10^{-12}$；规则 $10^{-9}$ |
| 射线：声明的边缘反射 | 每次镜像的 $N_\parallel$、$\abs{\vb N}$、$\delta\omega/\omega$ | $10^{-10}$ |
| EC 吸收：沿射线积分 | 同一板上的直接积分（X2，1 keV） | $10^{-3}$ |
| EC 吸收：运动学边沿 | 边沿下 $\alpha=0$、边沿上 $\alpha>0$（$N_\parallel$ 0 / 0.2 / 0.4，两支）；$\alpha(N_\parallel)=\alpha(-N_\parallel)$ | 恰为零；对称 $10^{-12}$ |
| EC 沉积 | 壳 + 壳外 + 余量 = 入射（Solov'ev X2，$\tau$ 149）；片长四倍加密 | $10^{-12}$；二阶收敛（比 $>8$、细对 $<10^{-3}$） |
| `code/rf_ray` 沉积 | 1 MW X2 于解析圆位形：功率账；壳体积和对 $2\pi^2R_0a^2$；解出的冷层之外的壳功率 | $10^{-9}$；$5\times10^{-3}$；$<10^{-6}P_0$ |
| B 类：GENRAY 在 EAST 上的介质 | GENRAY 射线点上记下的 $\vb B$、$n_e$、$\bar\psi$ | $3\times10^{-5}$ / $10^{-4}$ / $10^{-5}$ |
| B 类：GENRAY 在 EAST 上的轨迹 | EC O / X 与 LH 四射线，按极向距离对比 $(R,Z)$、$R\,\delta\phi$、$N_\parallel$ | EC $10^{-3}$ m / $10^{-3}$ m / $10^{-3}$；LH $10^{-3}$ m / $2\times10^{-3}$ m / $5\times10^{-3}$ |
| B 类：GENRAY 在 EAST 上的 EC 剩余功率 | O：$\tau$、半吸收点、$\abs{\Delta P}$；X：剩余、$\tau$、半吸收点（实测 O 0.86993 对 0.86989；X 半吸收点晚 12 mm） | O $1\%$ / 1 cm / 0.02；X $<10^{-3}$ / $15\%$ / 2 cm |
| LH ②：电子 Landau 阻尼 | 温度依赖对 $\zeta^3e^{-\zeta^2}$、冷极限、均匀板精确指数、多程守恒 | $10^{-12}$ / 0 / 解析 / $10^{-9}$ |
| LH ③：一维准线性 FP | 无射频回 Maxwell、平台、四个带的效率闭式、②↔③ 恒等式 | 闭式差 < 2 %；恒等式随 $du^2$ 收敛（$4.4\times10^{-4}\to1.3\times10^{-4}$） |
| LH ④：门 | 四 bin 三角谱 1 MW：发射 = 吸收 + 壳外 + 剩余；GENRAY EAST 四射线以 `lh_antennas` 文档重发 | $10^{-6}$；$(R,Z)$ $10^{-3}$ m、$N_\parallel$ $5\times10^{-3}$（实测 $1.1\times10^{-4}$ m、$1.1\times10^{-3}$） |
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
| 电子回旋闭式档（共振、光深、效率） | —（未接到 fyo 面） | — |
| 射线追踪：EC 轨迹、沿射线吸收与 $\bar\psi$ 壳沉积 | —（门返回壳量 `power_shell`、`p_e`；映到 `fyo:core_sources` 的梯子未做） | `fylite.io.fydoc.complete("code/rf_ray", …)` |
| 射线追踪：低杂波轨迹 | —（未接门） | — |
:::

(phys09-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（实现逐字引）〕RABBIT 保真档 {cite}`weiland2018rabbit`；METIS {cite}`artaud2018metis`；Stix 少数离子分布
{cite}`stix1975fast`；Lin-Liu–Hinton 屏蔽 {cite}`linliu1997shielding`；Giruzzi ECCD {cite}`giruzzi1987eccd`；Lin-Liu
$Z_{\rm eff}$ 依赖 {cite}`linliu2003eccd`；EC 光深原表 {cite}`bornatici1983ec`（表 IV，2026-09-11 起按原文）与其重印
{cite}`sabri2012ec`（首次转录所据，两处与原文不符，见 {ref}`phys09-ec`）；FWCD 量级 {cite}`iterphysicsbasis1999ch6`；
Bosch–Hale {cite}`boschhale1992fusion`；Wesson 分配 {cite}`wesson2004tokamaks`；全相对论 EC 吸收
{cite}`albajar2007ec,marushchenko2014travis`；射线方程与多组分冷色散的写法 {cite}`xie2022boray,wang2026boray3d`；
冷等离子体色散 {cite}`stix1992waves`。

〔一手文献（编者对应，实现只给姓名 / 上游文件）〕Stix 慢化 {cite}`stix1972heating`；Janev–Boley–Post 截面
{cite}`janev1989penetration`；Riviere {cite}`riviere1971penetration`；Start–Cordey 束电流 {cite}`start1980beam`；
Lin-Liu–Miller 捕获份额 {cite}`linliu1995trapped`；LH 可及性与冷等离子体折射率 {cite}`stix1992waves`；Fisch 电流驱动
{cite}`fisch1987theory`；库仑对数 {cite}`huba2013nrl`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔实现只给姓名、编者未能归属〕Eriksson 电子份额 $2W_{\rm fast}/\tau_s$；Moreau 全能量 $\tau_{\rm eff}$；Meo–Nguyen FWCD 剖面
（未移植）；ECCD 拟合的内部结构（"私人通讯"）。这些在本章标 〔未核验〕。

〔转引（转录）〕METIS `z0nbipath.m`、`z0nbistop.m`、`z0signbi.m`、`zicd0.m`、`zfract0.m`、`zsupra0.m`、`z0icrh.m`、`z0qp.m`、
`zboot0diff.m`、`fitetafwcd.m`（CEA/IRFM，CeCILL-C）；ASTRA / CORSICA ITER 15 MA 参考例；ITER / IMAS / FUSE 发射角约定；
GENRAY 在 EAST 71230 炮 4.8 s 上的 EC（100 GHz O / X）与 LH（2.45 GHz 四射线）输出及其 g 文件，随 BORAY 仓（提交 `54bcda7`）
分发，作射线追踪层的 B 类参照，不随本书发布。

〔本仓选择〕杂质多项式的 `Exp` 读法；能量分量求和；精确拉莫半径；Lin-Liu–Miller 捕获份额；波纹与层外拒绝；
$R_{\rm tan}\ge r_{\rm start}$ 拒绝；越界沉积装最外壳。射线追踪层：冷极化；C¹ 刮削层延拓与按竖直范围判私有区；声明的边缘
反射；逐项相消的沉积与壳外单列；`current_drive` 按名拒绝。证据为 {numref}`tbl-p09-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
