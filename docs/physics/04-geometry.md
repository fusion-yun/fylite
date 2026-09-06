---
title: 磁面几何与局域平衡 (Flux-Surface Geometry and Local Equilibrium)
subtitle: 描迹磁面、Miller/MXH 局域度规、GACODE 归一与 gyro-Bohm 单位
---

(phys04-intro)=
# 引言：两个几何层 (Introduction — Two Geometry Tiers)

〔范围〕本章详述由一份平衡导出后续各章所需度规的四部分内容：从 $\psi(R,Z)$ 网格**描迹**磁面
并求磁面平均、$q$、体积、形状矩与输运梯子；给定 Miller / MXH 参数化的**一个**磁面构造其度规与
磁面平均（GACODE `GEO` 的白箱翻译）；把物理剖面映成 TGLF / NEO 的归一输入
（`tgyro_tglf_map.f90` / `tgyro_neo_map.f90` 的移植）；以及导出剖面与 gyro-Bohm 单位
（`expro_compute_derived` 的移植）。

〔两个层不可互换〕〔实现〕局域度规层头部："局域度规层对一个 **Miller** 面回答同一批问题；
磁面描迹层对一个**必须先在矩形网格的 ψ 图里找出来**的面回答它们。两者不可互换——一个被
给定形状，另一个必须描迹它。"由此本章分两半：{ref}`phys04-traced`（描迹层）与
{ref}`phys04-geo`（局域层），以 {ref}`phys04-mapping` 的归一层把两者接到输运求解器。

〔出处姿态的分裂〕〔实现〕磁面描迹层 **没有任何上游来源与文献引用**，是本仓自有代码；
局域度规层、输入映射层、导出剖面层是 GACODE 的**白箱翻译**（Apache-2.0，仓根 `NOTICE`；
GEO / TGYRO 取修订 5efddfdf1），其头部明言"非清洁室——刻意与 平衡正解层相反，
因为逐行翻译可以逐行对照并以 $10^{-12}$ 对 Fortran 把门"。本章对后三者的"出处"因此分两级：
**上游文件名**（`geo.f90` 等，转引口径）与**物理一手文献**（由编者按公式内容对应，标注核验状态）。

〔与理论手册的分工〕磁面平均为何是体积加权、度规目录 `gm1..gm9` 在方程中的出处、共面积
公式与免追踪加权求和、两处端点奇异的机理、MXH 参数化的设计与 $B_{\rm unit}$ 跨码陷阱，见
SpResearch `GK-TMT-04`（跨仓）。本章只述本内核**实际的**算法与约定。

(phys04-conventions)=
# 约定：规范、符号与两个梯子 (Conventions)

〔COCOS 17〕〔实现〕仓级约定 COCOS 17 {cite}`sauter2013cocos`；`test_cocos_convention.py`
断言两种出厂配置均有 $I_p>0$、$B_0>0$、$\psi_{\rm bnd}>\psi_{\rm axis}$、$q>0$ 且向外增、$F>0$ 且向外减，
并以内核自己的方程 $\Delta^{\ast}\psi=-\mu_0R^2p'-FF'$ 在解出的平衡上验到 $10^{-11}$。
g 文件读回的 $\psi$ 须**转置**才符合内核的行主序 `[i*nz + j]`（转置后同一检验劣化到 0.44）。

〔规范〕〔实现〕磁面描迹层对规范不可知，除以下处：`trace` 要求磁轴为所给场的最大值
（全磁通 Wb 约定下成立；梯子传 $-\psi_N$ 以满足之）；`b_field` 与 `li3` 假定全磁通 Wb
（$B_p$ 含 $2\pi R$）；`metrics_from_polys` 的 `dpsi` 取 **Wb/rad**；磁面平均入口带显式
`psi_scale`（"$B_{\rm pol}=\abs{\nabla\psi}/R$ 只在每弧度规范成立"）。

〔GACODE 方向标志〕〔实现〕`sign_bt = -signb`、`sign_it = -signb·signq`（TGLF），
`btccw = -signb`、`ipccw = -signb·signq`（NEO），`signb = field_sign(torfluxa)`（零映到 $+1$）。
实现只写"上游的拆法"，BTCCW/IPCCW 的含义无进一步出处；其与 COCOS 的映射见 `GK-TMT-04`。

〔两个梯子〕〔实现 / Python〕`TRANSPORT_LADDER = (0.02, 41)`：41 个面落在 $\psi_N\in[0.02,0.95]$，
**不含磁轴**（等值线在轴上退化；输运网格自带轴节点 `with_axis_node`）；`MILLER_LADDER = (0.1, 24)`
（"近轴形状导数是粗网格最先丢失的东西"）。实现记录两种梯子曾因缺省面数不同而给出不同答案，
故 `equilibrium_ladder` 让两者出自**同一批多边形**。

(phys04-traced)=
# 描迹层：从 ψ 图到磁面 (The Traced Tier)

(phys04-trace)=
## 等值线描迹：射线 + 二分，不是 marching squares (Tracing by Ray Casting)

〔算法〕〔实现〕`trace(g, psi, level, axis, limiter, ntheta)`：

1. 自磁轴发 $n=\max(n_\theta,8)$ 条射线，$\theta_q=2\pi q/n$；
2. 沿射线以步长 $0.25\min(\Delta R,\Delta Z)$ 前进，直到第一个"不在内"的样本
   （`inside` ⇔ $\psi$ 有限 ∧ $\psi>\text{level}$ ∧（无限制器 ∨ 在限制器多边形内））；
   **无限制器时网格即限制器**（射线在第一个 NaN 处停）；
3. 对括住的区间作 **40 次二分**，半径取最后一个"在内"的点；
4. `clip_neck_excursions`：对每条射线的半径，以其 $\pm1,\pm2$ 邻居（循环、剔除非有限）的中位数
   为参考，$r_i>1.25\,\text{med}$（`NECK_TOL`）则置为中位数；至多 2 遍；
5. 输出有限射线的 $(R_{ax}+r_q\cos\theta_q,\,Z_{ax}+r_q\sin\theta_q)$。

〔为什么不是 marching squares〕〔实现〕`contour` 存在但**只为绘图**："线段汤穿过鞍点时无法可靠
走通"；任何需要**有序**轮廓的量（形状矩、磁面积分）都走 `trace`。四交点的鞍点歧义单元按边序
配对、不作消歧。

〔颈部剪裁的依据〕〔实现〕"$\psi$ 活在 25 mm 网格上而描迹器步进 6 mm 并二分四十次，一条射线
能穿过而邻居不能的通道是低于场自身分辨率的双线性细节"——一条对准鞍点的射线曾使
$z_{\min}$ 拖到 $-0.948$ m、$\kappa$ 报 1.79 对 EFIT 的 1.389。剪裁是**分辨率论证**，不是物理。

〔边界层级〕〔实现〕头部记：边界形状在 $\bar\psi=0.995$ 而非分离面描迹——"分离面在 X 点有角，
从磁轴量的 $r(\theta)$ 不是角的可用参数化"；宿主输运梯子缺省止于 0.95。分离面处
$\oint\dd l/\abs{\nabla\psi}$ 的对数发散（`GK-TMT-04`）在代码中**没有显式处理**，仅靠边界层级
$<1$ 与颈部剪裁绕开。

〔守卫〕无错误返回；失败层级给出短多边形，由下游（`surface_integrals` 要求 $\ge8$ 点）拒绝。
网格采样为双线性插值，**箱外返回 NaN**（"调用方不能把外推误当数据"）；$\abs{\nabla\psi}$
以 $h=\tfrac12\min(\Delta R,\Delta Z)$ 的中心差分取自双线性插值（"大到不被格边的双线性折点主导，
小到保持二阶"）。

(phys04-fsa)=
## 磁面平均：体积元加权 (Flux-Surface Averages)

〔定义〕〔实现〕`surface_integrals` 对闭合多边形逐边取中点 $(R_m,Z_m)$、边长 $\dd l$、$g=\abs{\nabla\psi}(R_m,Z_m)$，
以**同一权重** $w=R\,\dd l/\abs{\nabla\psi}$ 求全部平均：

$$
\expval{X}=\frac{\oint X\,R\,\dd l/\abs{\nabla\psi}}{\oint R\,\dd l/\abs{\nabla\psi}},\qquad
\dv{V}{\psi}=2\pi\oint\frac{R\,\dd l}{\abs{\nabla\psi}}
$$ (eq-p04-fsa)

$X\in\{\abs{\nabla\psi},\abs{\nabla\psi}^2,\abs{\nabla\psi}^2/R^2,R^2,1/R,1/R^2\}$。另返回
$\texttt{gq}=\oint\dd l/(R\abs{\nabla\psi})$、$\oint\dd l/\abs{\nabla\psi}$ 与周长。中点法则；$\ge8$ 点且 $\sum w>0$
否则 `None`（"不能对三个点取平均并称之为磁面"）。

〔为什么是这个权重〕〔已确立〕在每弧度规范下 $\abs{\nabla\psi}=RB_p$，故 $w=\dd l/B_p$，即
体积元 $\dd V=2\pi R\,\dd l\,\dd\psi/\abs{\nabla\psi}$ 在磁面上的密度——磁面平均的标准定义
{cite}`hinton1976theory,dhaeseleer1991flux`〔凭记忆〕；这也是 1.5-D 守恒形式（{ref}`phys05-intro`）
所依赖的"平均与散度交换"关系的来源（`GK-TMT-04`）。实现注明这些不是"轮廓均值"，并给出
各列的用途：$\expval{\abs{\nabla\psi}^2/R^2}$ 是电流扩散权，$\expval{R^2}$ 是环向动量容量权，
$\expval{1/R}$ 是 $\expval{j_\phi/R}/\expval{1/R}$ 的分母，$F^2\expval{1/R^2}=\expval{B_{\rm tor}^2}$
与 $\expval{\abs{\nabla\psi}^2/R^2}$ 是 $\expval{B^2}$ 的两半（测试 `b_squared_splits_into_the_two_columns`）。

〔体积〕〔实现〕`surface_volume` ≡ `enclosed_volume`：

$$
V=2\pi\abs{\sum_i(Z_{i+1}-Z_i)\frac{R_i^2+R_iR_{i+1}+R_{i+1}^2}{6}}
$$ (eq-p04-volume)

〔已确立〕由 Green 定理 $V=\oint2\pi R\cdot\tfrac R2\,\dd Z=2\pi\oint\tfrac{R^2}{2}\dd Z$，被积式在直边上
是 $R$ 的二次式，故三点式是**精确积分**而非求积（实现原话："Pappus by way of Green's theorem"）。
取绝对值使之与走向无关。

(phys04-q)=
## $q$ 的两条通道与端点约定 (Two Routes to q)

〔通道一：环路积分〕〔实现〕`q_profile`：

$$
q=F\cdot\texttt{gq}=F\oint\frac{\dd l}{R\,\abs{\nabla\psi_{\rm full}}}
$$ (eq-p04-q)

〔已确立〕$q=\frac{1}{2\pi}\oint\frac{B_\phi}{RB_p}\dd l=\frac{F}{2\pi}\oint\frac{\dd l}{R^2B_p}$ {cite}`wesson2004tokamaks,freidberg2014ideal`；
以 $\abs{\nabla\psi_{\rm full}}=2\pi RB_p$ 代入即 {eq}`eq-p04-q`。实现记录了把 $R^2$ 写进被积式的
版本在 EAST 上低 $\sim1.8\times$，"只有 g 文件 oracle 抓住了它"。层级 $x_k$ 逐个描迹，描不出或
$\texttt{gq}\le0$ 的层级**跳过、不伪造**。约定：$q_0$ 由最内两面**线性外推**（轴面退化、不可描迹）；
$q_{95}$ 由括住 0.95 的两面线性插值，扫描不足时**回退到最外描迹值**。

〔通道二：表格〕〔实现〕`metrics_from_polys` **不算** $q$，而是按 $\psi_N$ 用 `interp_uniform`
读 g 文件的 `qpsi` 表。两条通道并存：梯子用表，$q$ 剖面入口用积分。
`test_traced_geometry_tier.py` 断言描迹 $q$ 与 g 文件自身 $q$ 相对差 $<0.05$。

(phys04-ladder)=
## 输运梯子：$\rho$、$V'$ 与 IMAS 度规 (The Transport Ladder)

〔算法〕〔实现〕`metrics_from_polys`（输入 $-\psi_N$ 图、层级、多边形、`q_table`、`f_table`、
`dpsi` [Wb/rad]、`b0` [T]）：

1. 逐层 {eq}`eq-p04-fsa`（此处权重为 $\abs{\nabla\psi_N}$）得 $\texttt{dv}=\dd V/\dd\psi_N$、
   $\expval{\abs{\nabla\psi_N}}$、$\expval{\abs{\nabla\psi_N}^2}$、$\expval{\abs{\nabla\psi_N}^2/R^2}$、$\expval{R^2}$；
   少于 2 面 → `Err(-2)`。
2. 体积：梯形 + **轴桩** $V_0=\texttt{dv}_0\psi_{N,0}$——依据"近轴 $V'\sim\rho\sim\sqrt{\psi_N}$ ⇒
   $\dd V/\dd\psi_N\to$ 常数"，这是梯子可以不含轴的理由。
3. 环向磁通与 $\rho$：

$$
\Phi=2\pi\!\int\! q\,\dd\psi\ [\text{Wb}],\qquad \rho=\sqrt{\frac{\abs{\Phi}}{\pi B_0}}
$$ (eq-p04-rho)

   梯形自轴桩 $\tilde\Phi_0=\tfrac12(q_{ax}+q_0)\psi_{N,0}$ 起；`dpsi` "只在这里进入"，取模使符号约定
   不进入半径。〔已确立〕$\Phi'(\psi)=2\pi q$ 是 $q$ 的定义 $q=\dd\Phi/\dd\Psi_{\rm pol}$ 的直接后果；
   $\rho_{\rm tor}$ 的定义与 ASTRA / JINTRAC 族一致 {cite}`pereverzev2002astra`。
4. $\dd\rho/\dd\psi_N$ 由 `gradient`（内点二阶，**端点一阶单侧**，{ref}`phys01-interp`）。
5. $V'=\texttt{dv}/(\dd\rho/\dd\psi_N)$；
   $\texttt{gm3}=(\dd\rho/\dd\psi_N)^2\expval{\abs{\nabla\psi_N}^2}$、
   $\texttt{gm7}=(\dd\rho/\dd\psi_N)\expval{\abs{\nabla\psi_N}}$、
   $\texttt{gm2}=(\dd\rho/\dd\psi_N)^2\expval{\abs{\nabla\psi_N}^2/R^2}$；`fpol` 由表读。

〔命名〕`gm2`、`gm3`、`gm7` 是 IMAS 数据字典的度规名 {cite}`imbeaux2015imas`〔凭记忆〕
（$\expval{\abs{\nabla\rho}^2/R^2}$、$\expval{\abs{\nabla\rho}^2}$、$\expval{\abs{\nabla\rho}}$）；实现未给 IDS 版本。

〔轴节点〕〔实现〕`with_axis_node` 前置一个轴节点：`zero` 块（$\rho$、$\psi_N$、$V'$）置 0，
`repeat` 块（磁面平均、$F$、$q$）复制最内值——"这些量在轴上趋于有限极限，最内描迹值是可用的外推"。

〔精度〕〔Python〕对一个已移除的 contourpy + 样条实现：$V$、$V'$ 到 0.7 %，`gm3/gm2` 到 1.1 %，
`gm7` 到 0.8 %，"都在独立网格求积的 ±1 % 内，这是该几何所能支持的全部容差"。
`enclosed_plasma_current` 由 $I(\rho)=\frac{V'\expval{\abs{\nabla\rho}^2/R^2}}{2\pi\mu_0}\dv{\psi}{\rho}$ 在合成
g 文件上得 0.968 倍表头电流，且 3.2 % 的差随边界移到 0.9999 **不消失**（归于梯子求积与差分）。

(phys04-shape)=
## 形状矩、Miller 行与剪切 (Shape Metrics, Miller Rows and Shears)

〔形状矩〕〔实现〕`shape_metrics` 从描迹轮廓读 Miller 五量：

$$
R_0=\tfrac12(R_{\min}+R_{\max}),\ a=\tfrac12(R_{\max}-R_{\min}),\ Z_0=\tfrac12(Z_{\min}+Z_{\max}),\
\kappa=\frac{Z_{\max}-Z_{\min}}{2a},\ \delta_{u,l}=\frac{R_0-R(Z_{\max,\min})}{a}
$$ (eq-p04-shape)

$Z_0$ 是 Miller 的 `zmag`，"不是位移磁面上的磁轴高度"。

〔Miller 边界〕〔实现〕`miller_boundary`：$R(\theta)=R_0+a\cos(\theta+\arcsin\delta\sin\theta)$、
$Z(\theta)=Z_0+\kappa a\sin\theta$，三角度**上下各取**；无方形度。这是 Miller 等的局域平衡参数化
{cite}`miller1998noncircular`（实现只用其名，未引论文）。

〔Miller 行与剪切〕〔实现〕`miller_from_polys`（"GACODE `profiles_gen` 约定"）：
$\delta=\mathrm{clamp}(\tfrac12(\delta_u+\delta_l),-0.99,0.99)$，径向导数按描迹小半径 `rmin` 用 `gradient`：

$$
\hat s=\frac rq\dv qr,\quad \text{shift}=\dv{R_0}{r},\quad s_\kappa=\frac r\kappa\dv\kappa r,\quad
s_\delta=\frac{r\,\dd\delta/\dd r}{\sqrt{\max(1-\delta^2,10^{-6})}},\quad s_{z}=\dv{Z_0}{r},\quad \zeta=s_\zeta=0
$$ (eq-p04-shear)

少于 3 面 → `Err(-2)`（"三个，因为径向导数需要三个——不是五个"）。测试记录：Python 闭包曾
在稀疏梯子上取导数一年，给 TGLF 的剪切在 $\psi_N=0.7$ 处差 28 %；密梯子上对
$q=q_0+\dd q\,\psi_N^2$ 的解析剪切 $4\,\dd q\,\psi_N^2/q$ 差 $<2\%$。

:::{warning}
〔两个层的 $s_\delta$ 定义不同〕〔评注〕描迹层 {eq}`eq-p04-shear` 的 $s_\delta$ 已除以 $\sqrt{1-\delta^2}$，
而 导出剖面层交给 GEO 的 `s_delta` 是**裸的** $r\,\dd\delta/\dd r$，由 `solve` 自己乘
$1/\cos(\arcsin\delta)$（{ref}`phys04-geo-angle`）。两层因此把**不同定义**的 `S_DELTA_LOC` 交给
TGLF；哪一个符合 TGLF 的约定，实现未说。此为本章标出的**待裁定项**。
:::

(phys04-xpoint)=
## X 点、打击点与其他几何原语 (X-Points, Strike Points and Other Primitives)

〔实现〕`x_points`：对 $2..n-2$ 的节点，$\det H=\psi_{RR}\psi_{ZZ}-\tfrac14(\psi_{RZ}+\psi_{ZR})^2<0$、
$\abs{\nabla\psi}$ 为 $3\times3$ 模板最小、$\abs{\psi_N-1}\le$ `psin_window`、距轴 $\ge$ `min_axis_dist` 为候选；
牛顿修正 $H\delta=-\nabla\psi$（步长超一格或 $\det H=0$ 则弃）；$2\max(\Delta R,\Delta Z)$ 内合并；按 $\abs{\psi_N-1}$
排序截到 **2** 个。`strike_points`：`contour(psi_bnd)` 线段与壁折线求交（平行守卫 $\abs{\text{den}}<10^{-30}$）。
`wall_clearance`：到壁**折线**（非顶点）的最小距离（`code/summary` 的 `gap`）。`shape_observables`（自 2026-09-06 仅神谕构建可见）/ `ray_level`（已退役）：间隙、等磁通误差
（以 1 mm 模板转为距离）、角采样边界点——"经 $\psi$ **场**射线求交，不是插值 g 文件的 `rbbbs/zbbbs` 折线……
对后者求导带 10–25 % 的线性响应误差"（{ref}`phys13-intro`）。

〔$l_i(3)$〕〔实现〕`li3`：

$$
l_i(3)=\frac{2\int B_p^2\,\dd V}{\mu_0^2I_p^2R_0},\qquad B_p=\frac{\abs{\nabla\psi}}{2\pi R},\qquad \dd V=2\pi R\,\Delta R\,\Delta Z
$$ (eq-p04-li3)

在 $0\le\psi_N\le1$ 的格上直接求和（"不描迹"）。$l_i(3)$ 是 ITER 设计指南采用的内感定义
{cite}`uckan1990guidelines`〔凭记忆〕；实现未注出处。

(phys04-geo)=
# 局域层：GEO 移植（Miller / MXH） (The Local Tier — the GEO Port)

(phys04-geo-inputs)=
## 输入与归一 (Inputs and Normalisation)

〔实现〕`Surface`：长度归一到小半径 $a$、场归一到 $B_{\rm unit}$；$\theta\in(-\pi,\pi]$ 取 $n_\theta$ 点、**端点重复**
（$\theta_i=-\pi+i\Delta\theta$，$\Delta\theta=2\pi/(n_\theta-1)$）；缺省 `rmin=0.5, rmaj=3, q=2, s=1, kappa=1, n_theta=1001`；
22 槽 MXH 形状数组 `cos0, s_cos0, …, cos6, s_cos6, sin3, s_sin3, …, sin6, s_sin6`（**无 sin1/sin2 槽**：
$\sin\theta$ 与 $\sin2\theta$ 分别由 $\arcsin\delta$ 与 $-\zeta$ 承载）；$\beta_\ast$ 三项在本仓一律为零。
守卫：$\abs{\text{signb}}<10^{-10}$ → `-1`（"实现在此 STOP"），$\abs\delta>1$ → `-2`，$n_\theta<8$ → `-3`。

(phys04-geo-angle)=
## 广义 Miller 角与坐标 (The Generalised Miller Angle)

〔实现〕以 $x=\arcsin\delta$，

$$
A(\theta)=\theta+c_0+x\sin\theta-\zeta\sin2\theta+\sum_{n=1}^6c_n\cos n\theta+\sum_{n=3}^6s_n\sin n\theta
$$ (eq-p04-mxh)

$$
R=R_0+r\cos A,\qquad Z=Z_0+\kappa r\sin\theta\quad(\text{"Z 用裸角"}),
$$ (eq-p04-mxh-rz)

$A_\theta$、$A_{\theta\theta}$ 为其 $\theta$ 导数；径向导数
$A_r=s_{c_0}+\frac{s_\delta}{\cos x}\sin\theta-s_\zeta\sin2\theta+\sum s_{c_n}\cos n\theta+\sum s_{s_n}\sin n\theta$
（$s_\delta$ 在此除以 $\cos x=\sqrt{1-\delta^2}$——见上节警告）；
$R_r=\dd R_0/\dd r+\cos A-\sin A\cdot A_r$、$R_\theta=-rA_\theta\sin A$、$Z_r=\dd Z_0/\dd r+\kappa(1+s_\kappa)\sin\theta$、
$Z_\theta=\kappa r\cos\theta$。

〔出处〕{eq}`eq-p04-mxh` 是 Miller 参数化 {cite}`miller1998noncircular` 的 **MXH 扩展**
{cite}`arbon2021mxh`（"Miller extended harmonic"），GACODE 几何文档 {cite}`gacode_geometry` 给出同一
形式；GEO 的算子求值方法见 Candy {cite}`candy2009unified`。实现只注 `geo.f90`。

(phys04-geo-metric)=
## 度规、场与磁面平均 (Metric, Fields and Averages)

〔实现〕逐 $\theta$：$g_{\theta\theta}=R_\theta^2+Z_\theta^2$、$J_r=R(R_rZ_\theta-R_\theta Z_r)$、
$\abs{\nabla r}=R\sqrt{g_{\theta\theta}}/J_r$、$\ell_\theta=\sqrt{g_{\theta\theta}}$、曲率半径
$r_c=\ell_\theta^3/(R_\theta Z_{\theta\theta}-Z_\theta R_{\theta\theta})$。矩形法则的环路积分（一个周期）：

$$
f=\frac{r}{\dfrac{\Delta\theta}{2\pi}\sum_i\dfrac{\ell_\theta}{R\abs{\nabla r}}},\qquad
V'=2\pi\Delta\theta\sum_i\frac{\ell_\theta R}{\abs{\nabla r}},\qquad
B_t=\frac fR,\quad B_p=\frac rq\frac{\abs{\nabla r}}{R},\quad B=\text{signb}\sqrt{B_t^2+B_p^2}
$$ (eq-p04-geo-f)

〔评注〕$B_p=(r/q)\abs{\nabla r}/R$ 与 $f$ 的环路式合起来就是 $\frac1{2\pi}\oint\frac{B_t}{RB_p}\dd\ell=q$：
$f$ 由 $q$ 定出，实现未明言。

〔磁面平均〕〔实现〕**权重 $G_\theta/B$**，$G_\theta=\frac{RB\ell_\theta}{rR_0\abs{\nabla r}}$：

$$
\expval X=\frac{\sum_iX_iG_{\theta,i}/B_i}{\sum_iG_{\theta,i}/B_i}
$$ (eq-p04-geo-fsa)

〔已确立〕$G_\theta/B\propto\ell_\theta/(B_p\ldots)$——在圆截面上 $\propto R$，测试由此得
$\expval{R^2}=R_0^2+\tfrac32r^2$（与 {eq}`eq-p04-fsa` 的体积权重一致）。
$\theta$ 导数用周期五点模板 $\partial_\theta B=(-B_{i+2}+8B_{i+1}-8B_{i-1}+B_{i-2})/(12\Delta\theta)$，
周期 $n_\theta-1$。实现记录一次索引移位缺陷（`(k-1).rem_euclid(m)`）曾使 `gradpar_Bmag` 差 $4.3\times10^{-3}$、
自举电流差 $3\times10^{-4}$——NEO 的 `gradpar_Bmag` 在 $\theta=-\pi$ 由对称性恰为零是抓住它的判据。

〔漂移系数与 $E_{1..4}$〕〔实现〕`gsin`、`gcos1`、`gcos2`、`captheta`、`nu`、$f'$：
$f'=(2\pi qs/r-\text{loop}_1/r+\text{loop}_3)/\text{loop}_2$，$E_k$ 自 $\theta=0$ 向两侧作累积梯形。
这些是 TGLF / NEO 所需的局域平衡系数（{ref}`phys07-intro`、{ref}`phys08-intro`），其推导见
{cite}`candy2009unified`；实现只注 `geo.f90`。

〔本移植的增项〕〔实现〕两个 Fortran 里没有的标量：`fsa_r2` $=\expval{R^2}$（"通道曾用
$R_{\rm maj}(r)^2$ 代替——差 $O((a/R)^2)$，EAST 边缘 2.5 %"）与 `fsa_grad_r2_over_r2` $=\expval{\abs{\nabla r}^2/R^2}$
（IMAS `gm2`，"不是 `fsa_grad_r2 / fsa_r2`"）。两个极向角：`theta_nc`（GS2/NCLASS 角，
$G_\theta$ 的累积并仿射重标到 $[-\pi,\pi]$）与 `theta_s`（直磁力线角，被积式 $J_r/R^2$）。

(phys04-mapping)=
# 归一层：剖面 → TGLF / NEO 输入 (The Mapping Tier)

(phys04-mapping-units)=
## CGS 常数与单位缝 (CGS Constants and the SI↔CGS Seam)

〔实现〕输入映射层全程 **CGS、eV**（"TGYRO 自己的单位"）；常数与 `tgyro_globals` 逐字相同：
$k=1.6022\times10^{-12}$ erg/eV、$e=4.8032\times10^{-10}$ statC、$m_e=9.1094\times10^{-28}$ g、
$m_D=3.34358\times10^{-24}$ g、$c=2.9979\times10^{10}$ cm/s——"这些是上游的**值**，不是当前 CODATA 值。
更精确的电子质量会让本移植不再再现它所移植的代码，差别会以万分之几出现在每个碰撞派生量上"。
SI→CGS 转换在 ABI 一处（`surface_from_block`：m→cm ×$10^2$、T→G ×$10^4$、m$^{-3}$→cm$^{-3}$ ×$10^{-6}$、
梯度 ×$10^{-2}$、kg→g ×$10^3$；`pext` Pa→barye ×10）。实现记录 `pext/dpext` 曾是"这个 SI 签名里内核
按 CGS 读的唯一一对"——调用方"做显然的事，结果低十倍"。

(phys04-mapping-collision)=
## 碰撞率、库仑对数与能量交换 (Collision Rates, Coulomb Logarithm, Exchange)

$$
\ln\Lambda=24-\ln\!\Big(\frac{\sqrt{n_e}}{T_e}\Big)\quad(n_e\ [\text{cm}^{-3}],\ T_e\ [\text{eV}])
$$ (eq-p04-lnlambda)

$$
\nu_e=\frac{\sqrt2\pi n_ee^4\ln\Lambda}{\sqrt{m_e}(kT_e)^{3/2}},\qquad
\nu_i=\frac{\sqrt2\pi n_i(Z_ie)^4\ln\Lambda}{\sqrt{m_i}(kT_i)^{3/2}}
$$ (eq-p04-nu)

$$
\nu_{\rm exch}=\sum_{i\ \text{thermal}}c_{\rm exch}\frac{\sqrt{m_em_i}Z_i^2n_i\ln\Lambda}{(m_eT_i+m_iT_e)^{3/2}},\qquad
c_{\rm exch}=2\cdot\tfrac43\sqrt{2\pi}\frac{e^4}{k^{3/2}}
$$ (eq-p04-exch)

〔出处〕{eq}`eq-p04-lnlambda` 是 NRL 等离子体公式手册的电子—离子库仑对数（$T_e>10$ eV 支）
{cite}`huba2013nrl`〔凭记忆〕；实现写"TGYRO 用的 NRL 形式"。{eq}`eq-p04-nu` 实现注 "Belli-2008"，
即 NEO 的碰撞频率定义 {cite}`belli2008neo`（一个 $\ln\Lambda$ 用于所有物种）。{eq}`eq-p04-exch` 是
$1.5n_ek(T_e-T_i)$ 的经典电子—离子能量交换系数（Spitzer 形式 {cite}`spitzer1962physics`〔凭记忆〕；
NRL 手册的 $\nu_\epsilon^{e|i}$）；实现未注出处。快离子（非热）不计入交换。

(phys04-mapping-tglf)=
## TGLF 局域输入 (TGLF Local Inputs)

〔实现〕`tglf_local`（`tgyro_tglf_map.f90`）以 $\hat q=\abs q$、$\hat r=r/a$：
$Q'=(\hat q/\hat r)^2\hat s$、$P'=\frac{\hat q}{\hat r}\frac{\beta_{\rm unit}}{8\pi}(-a\,\dd\ln p/\dd r)$、
$\beta_{\rm unit}=8\pi p/B_{\rm unit}^2$（**总**压强，含 `pext`）、$\beta_e$、$\hat\nu_e=\nu_ea/c_s$、
$\alpha_{SA}=R_0\beta_{\rm unit}(-\dd\ln p/\dd r)\hat q^2$、
$\text{DEBYE}=7.43\times10^2\sqrt{T_e/n_e}/\abs{\rho_s}$，旋转块 $\gamma_{p0}=-R_0\omega_0'$、$\gamma_{E0}=\gamma_{p0}r/(\hat qR_0)$；
物种块电子优先，`mass = m/m_D`、`taus = T/T_e`、`rlns = a·dlnndr`。TGLF **不强制**准中性。
$c_s=\sqrt{kT_e/m_D}$、$\rho_s=c_s/(eB_{\rm unit}/m_Dc)$（氘质量归一）。〔出处〕TGLF 的输入归一见
{cite}`staebler2007tglf`；$7.43\times10^2\sqrt{T/n}$ cm 是 NRL 手册的 Debye 长度 {cite}`huba2013nrl`
（实现未注）。宿主的 `TGYRO_TGLF_REVISION` 预设逐字携带其文献：rev 1 SAT0 {cite}`kinsey2008sat0`，
rev 2 SAT1 {cite}`staebler2013prl,staebler2017nf`，rev 3 SAT2 {cite}`staebler2021ppcf,staebler2021nf`
（{ref}`phys08-intro`）。

(phys04-mapping-neo)=
## NEO 局域输入与归一器 (NEO Inputs and Normalisers)

〔实现〕`neo_inputs`（`tgyro_neo_map.f90`）：$T_{\rm norm}=T_{i,1}$、$n_{\rm norm}=n_e$；

$$
\nu_1=\nu_{i,1}\frac{a}{c_s}\frac{1}{\sqrt{T_{\rm norm}/T_e}}\cdot\frac{n_e}{n_{i,1}}\sqrt{\frac{m_{i,1}}{m_e}}\Big(\frac{T_{i,1}}{T_e}\Big)^{3/2}\frac{1}{Z_1^4}
$$ (eq-p04-nu1)

单离子时**强制准中性** `dens_1 -= (Σ dens·z)/z_1`；$q$ **不带符号**（符号走 `IPCCW/BTCCW`）。
Sauter 入口读**另一套** 14 槽序 `NEO_SAUTER_SLOTS`（实现：按错序手搭曾使通量差 200×）。
归一器（`tgyro_flux.f90`）：$\Gamma_{GB}^{\rm NEO}=n_1T_1^{3/2}\rho_\ast^2$、$Q_{GB}^{\rm NEO}=n_1T_1^{5/2}\rho_\ast^2$、
$\Pi_{GB}^{\rm NEO}=n_1T_1^2\rho_\ast^2$（物种 1 参照，非电子参照）；电流单位
$\expval{\vb j\cdot\vb B}=\texttt{jpar\_neo}\times J_{eV}n_ev_{\rm norm}B_{\rm unit}$，测试钉
`neo_current_unit(3e19, 1500, 3.0) ≈ 3.864e6` A·T/m²。"NEO 的 `jpar` 对 $\rho_\ast$ 精确线性，
调用方必须传**物理的** $\rho_s/a$"。`chi_neo_ion`（Chang–Hinton，{ref}`phys07-intro`）**拒绝轴**：
$r/R_0\le10^{-3}$ 返回 `None`（"$(q/\epsilon)^2$ 在轴上发散；$\chi$ 曾报 11.4 对下一节点 0.21"）。
`ion_dilution`：$n_D=n_e(Z_{\rm imp}-Z_{\rm eff})/(Z_{\rm imp}-1)$，非正**拒绝而非下限**。

(phys04-bunit)=
## $B_{\rm unit}$ 的两种写法 (Two Spellings of B_unit)

$$
B_{\rm unit}=\frac{\dd(\Phi_t/2\pi)}{\dd(r^2/2)}\ (\text{导出剖面层，三点 Lagrange 导数}),\qquad
B_{\rm unit}=\frac{\abs{\dd\Phi/\dd r}}{2\pi r}\ (\text{映射层，三点差分})
$$ (eq-p04-bunit)

〔已确立〕两式相等（$\dd(r^2/2)=r\,\dd r$）；差别在差分算子：后者端点一阶单侧，测试记录"梯子首
节点读到 1.5 倍真场"。〔出处〕$B_{\rm unit}\equiv\frac{q}{r}\dv{\psi}{r}$ 是 GACODE / GYRO 族的有效场
{cite}`waltz1999shape,gacode_geometry`〔凭记忆〕；实现称之为"归一层产出的**最关键**的数字，错了什么也
不报"。TGYRO 参考例上 $B_{\rm unit}[0]=2.680430$ T 对 $B_{\rm centr}\approx2.07$ T（"差约 30 %"）。
$B_{\rm unit}$ 的跨码陷阱见 `GK-TMT-04`。

(phys04-bundle)=
# 导出剖面与 gyro-Bohm 单位 (Derived Profiles and Gyro-Bohm Units)

〔实现〕`derive`（`expro_compute_derived`）：$a=r_{\min}[n-1]$（最后闭合面）；剪切参数
"上游的逐量约定" $\hat s=r\,\dd\ln\abs q/\dd r$、$s_\kappa=(r/\kappa)\dd\kappa/\dd r$、$s_\delta=r\,\dd\delta/\dd r$、
$s_\zeta=r\,\dd\zeta/\dd r$、MXH 剪切 $r\,\dd(\text{shape}_h)/\dd r$，全部用**三点 Lagrange 导数** `bound_deriv`
（对二次式精确；"不是 `gradient`——后者端点一阶，正是 $B_{\rm unit}$ 与剪切最敏感之处"）；
$-\dd\ln x/\dd r$ 取上游符号（**下降剖面为正**）；每面调用 `solve` 并按 $a$ 还原单位
（$V'a^2$、$Va^3$、$\expval{B_p^2}B_{\rm unit}^2$ …）；轴（$i=0$）$V=V'=0$，其余量由面 1、2 线性外推
（`bound_extrap`）。

〔声明的上游偏离〕〔实现〕$m_D=3.34358\times10^{-24}$ g（TGYRO 的 `expro_mass_deuterium`）而非
`expro_util` 的 $2m_p=3.3452\times10^{-24}$——"上游在此不自洽……0.05 % 的差落进 $c_s$ 与每个
gyro-Bohm 单位，故本移植跟随 TGYRO，因为通量比对正是对它做的"。

〔gyro-Bohm 单位〕〔实现〕电子参照，CGS 计算后转出：

$$
c_s=\sqrt{\frac{kT_e}{m_D}},\ \rho_s=\frac{c_s}{eB_{\rm unit}/m_Dc},\ \rho_\ast=\frac{\rho_s}a,\
\chi_{GB}=\frac{\rho_s^2c_s}{a},\ \Gamma_{GB}=n_ec_s\rho_\ast^2,\ Q_{GB}=n_ekT_ec_s\rho_\ast^2,\
\Pi_{GB}=n_ekT_ea\rho_\ast^2,\ S_{GB}=n_ekT_e\frac{c_s}a\rho_\ast^2
$$ (eq-p04-gb)

〔已确立〕这是 gyro-Bohm 标度的标准定义（$\chi_{GB}\propto T^{3/2}/B^2$）{cite}`waltz1997glf23,staebler2007tglf`；
实现只注 `expro_util`。测试：$B$ 加倍 $\chi$ 四分之一（$10^{-12}$）；$Q_{GB}(8\,\text{keV})/Q_{GB}(2\,\text{keV})=4^{2.5}$。

(phys04-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **描迹层只到 $\psi_N\le0.95$（缺省）**：分离面不描迹，对数发散不处理；边界形状取 0.995。
   `Ladder.rho_b` 是**最外描迹面**的 $\rho$，不是分离面。
2. **磁轴不在梯子上**：轴桩假定 $\dd V/\dd\psi_N\to$ 常数；近轴精度实测 $\psi_N=0.23$ 处 5.8 %，
   0.35 处 1.3 %，向外 $<1\%$。
3. **端点差分一阶**（`gradient`）——$B_{\rm unit}$、剪切在梯子两端最不可靠；`bundle` 层改用
   三点 Lagrange 导数正是为此。
4. **两层的 $s_\delta$ 定义不一致**（{ref}`phys04-shape` 警告）——待裁定。
5. **单射线颈部剪裁是分辨率判据**，$25$ mm 网格上有效；细网格上 `NECK_TOL = 1.25` 未重标。
6. **GEO 假定上下对称的 $Z$ 参数化**（$Z=Z_0+\kappa r\sin\theta$）；不对称全部进入 $A(\theta)$。
7. **CGS 常数是上游值而非 CODATA**：碰撞派生量与当前物理常数差万分之几，是**有意**的。
8. **Chang–Hinton 拒绝轴**（$r/R_0\le10^{-3}$）。
9. **GACODE 方向标志的意义未在实现给出**；与 COCOS 的对应须回 `GK-TMT-04` 或 {cite}`sauter2013cocos` 核对。

(phys04-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 几何层的外部 oracle 与解析闭式锚点。
:name: tbl-p04-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| GEO 移植 vs 录得 `libgeo.so`（GACODE 5efddfdf1） | 3 个面（含 $\kappa=2.0$、$\delta=0.55$、位移与 $Z_0$） | 每个标量 `worst < 1e-12`，实测 $1.2\times10^{-16}$ |
| `derive` vs TGYRO `treg01` | `out.tgyro.geometry.1/2` | $B_{\rm unit}$、$\hat s$、位移、$V$、$V'$、$\expval{\abs{\nabla r}}$ 相对 $<10^{-5}$；$B_{\rm unit}[0]=2.680430$ T |
| gyro-Bohm vs TGYRO | `out.tgyro.gyrobohm` | 6 量相对 $<10^{-5}$，无插值 |
| TGLF / NEO 输入 vs `out.{tglf,neo}.localdump` | 六个 TGYRO 例 | 78/40 … 85/52 个共享键零分歧（$10^{-4}$，五位打印） |
| 圆截面闭式（GEO） | — | $\abs{\nabla r}=1$；$V'=S=(2\pi)^2R_0r$；$V=2\pi^2R_0r^2$；$\expval{R^2}=R_0^2+\tfrac32r^2$；$\expval{\abs{\nabla r}^2/R^2}=1/(R_0\sqrt{R_0^2-r^2})$（$10^{-9}$） |
| 圆截面闭式（描迹） | — | $\dd V/\dd\psi=2\pi^2R_0$（$5\times10^{-3}$）；$\expval{1/R}=1/R_0$、$\expval{1/R^2}=1/(R_0\sqrt{R_0^2-a^2})$（$3\times10^{-4}$，721 射线）；环体积 $2\pi^2R_0a^2$（$<10^{-5}$，1024 点） |
| $\expval{B^2}$ 两列分解 | — | 环向份额 $\in(0.9,1)$ |
| 线性磁通图的 $B_R$、$B_Z$ | $\psi=3R+2Z$ | $10^{-9}$ |
| 描迹 $q$ vs g 文件 $q$；梯子电流 vs 表头 | ITER 15 MA g 文件 | 相对 $<0.05$；$\in(0.85,1.05)$ |
| $\Delta^{\ast}\psi=-\mu_0R^2p'-FF'$（COCOS 17） | 解出的平衡 | $10^{-11}$ |
:::

(phys04-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 几何层由一份平衡导出的度规与局域量。
:name: tbl-p04-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 描迹磁面与磁面积分 | `fyo:equilibrium` 的 `profiles_1d`（面量） | `fylite.kernel.trace_surface` |
| 输运梯子与 Miller 行 | `fyo:equilibrium`：$V'$、$\langle|\nabla\rho|^2\rangle$ 等度规 | `fylite.fyo.Ladder` |
| $q$、$F$、体积、$l_i(3)$ | `fyo:equilibrium` 的 `profiles_1d` 与 `global_quantities` | `fylite.fyo` |
| X 点、打击点、间隙、等磁通面 | `fyo:equilibrium` 的边界描述 | `S.design.shape` |
| 局域度规（GEO） | —（湍流与新经典的输入，不单独落面） | `fylite.kernel.geo_surface` |
| 湍流 / 新经典输入映射 | —（`fyo:core_transport` 的输入侧） | `scenario.model.mapping` |
| $B_{\rm unit}$、稀释、碰撞率 | `fyo:core_profiles` 的派生量 | `scenario.model.closure` |
| 导出剖面与 gyro-Bohm 单位 | —（通量比较的单位，随 `fyo:core_transport` 走） | `scenario.model.mapping` |
:::

(phys04-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献〕磁面平均与体积元 {cite}`hinton1976theory,dhaeseleer1991flux`；$q$ 的定义
{cite}`wesson2004tokamaks,freidberg2014ideal`；$\rho_{\rm tor}$ 约定 {cite}`pereverzev2002astra`；
IMAS 度规名 {cite}`imbeaux2015imas`；$l_i(3)$ {cite}`uckan1990guidelines`；Miller 参数化
{cite}`miller1998noncircular`；MXH {cite}`arbon2021mxh`；GEO 算子求值 {cite}`candy2009unified`；
GACODE 几何文档 {cite}`gacode_geometry`；$B_{\rm unit}$ {cite}`waltz1999shape`；碰撞频率 {cite}`belli2008neo`；
库仑对数、Debye 长度 {cite}`huba2013nrl`；能量交换 {cite}`spitzer1962physics`；gyro-Bohm 归一
{cite}`waltz1997glf23,staebler2007tglf`；TGLF 饱和规则各代（宿主实现逐字引）
{cite}`kinsey2008sat0,staebler2013prl,staebler2017nf,staebler2021ppcf,staebler2021nf`；COCOS {cite}`sauter2013cocos`。
标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引（白箱翻译）〕`geo.f90`（`geo_do`, `geo_model_in = 0`）、`tgyro_tglf_map.f90`、`tgyro_neo_map.f90`、
`tgyro_flux.f90`、`tgyro_globals`、`expro_util.f90`（`expro_compute_derived`, `bound_deriv`, `bound_extrap`）、
`profiles_gen`——GACODE 修订 5efddfdf1，Apache-2.0，作者见仓根 `NOTICE`。实现中对这四个模块的
**全部**公式只给上游文件名，未给论文；上表的一手文献是编者的对应。

〔本仓自有（实现未注出处）〕磁面描迹层全部：射线 + 40 次二分的描迹器、`NECK_TOL = 1.25` 与五点
中位剪裁、$q_0$/$q_{95}$ 约定、轴桩、X 点探测器的窗口与合并规则、`direct_integrals`、
`fsa_r2`/`fsa_grad_r2_over_r2` 两个增项、$m_D$ 取 TGYRO 值的裁定。其证据为 {numref}`tbl-p04-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
