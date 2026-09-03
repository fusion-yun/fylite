---
title: 1.5-D 芯部输运 (1.5-D Core Transport)
subtitle: 双权守恒算子、θ 法与 Picard、Pereverzev–Corrigan 稳定化、四通道、TGYRO 型通量匹配、芯部合步与锯齿混合
---

(phys05-intro)=
# 引言：一个守恒算子，四个通道 (Introduction)

〔范围〕本章详述**磁面平均 1.5-D 芯部输运**：在 $\rho\in[0,1]$ 上以外部给定的几何数组
（"规定几何模式"）推进电子 / 离子温度、逐离子密度、环向角动量与极向磁通；并含 TGYRO 型稀疏
Newton 通量匹配、四通道一次推进的芯部合步与一个最小锯齿混合模型。闭包（$\chi$、$D$、$\sigma_\parallel$、$j_{ni}$）与源项**一律由调用方给出**
（{ref}`phys07-intro`、{ref}`phys08-intro`、{ref}`phys09-intro`、{ref}`phys10-intro`）。

〔为什么物理与数值只有一个宿主〕〔实现〕模块头部记录：Python 参考实现 `transport.py` 与 Rust 核
逐点对到 $7\times10^{-16}$，但页面级装配仍差 $3\times10^{-2}$——"FYL-DESIGN-07 D-4 得出结论：
物理与数值只要一个宿主"。因此本章所述离散是**唯一**的离散；Python 与浏览器只装配、不复写。

〔出处姿态〕〔实现〕本模块不是 GACODE 派生（仓根 `NOTICE`：`fytrans` 是它的 **oracle**，
"被量度的对象而非被复制的对象"），只有 `tgyro_residual` 与 `tgyro_iteration_standard` 的回退规则
按 TGYRO 移植。实现对有限体积格式、θ 法、Pereverzev–Corrigan 均**未给文献**（后者只有名字）；
本章的一手文献是编者的对应，标注核验状态。

〔与理论手册的分工〕"1.5D"的结构含义与约化前提、$V'^{5/3}$ 权因子的绝热来处、刚性的三个来源、
Pereverzev–Corrigan 不改变不动点的证明、耦合块解 vs 分裂，见 SpResearch `GK-TMT-03`（跨仓）。

(phys05-operator)=
# 双权守恒算子 (The Two-Weight Conservative Operator)

(phys05-operator-form)=
## 连续形式 (Continuous Form)

〔实现〕所有通道写成同一形状：

$$
C\,\pdv yt=\pdv{}{\rho}\Big[M\Big(D\pdv y\rho-v\,y\Big)\Big]+C\,S
$$ (eq-p05-operator)

`capacity` $\to C$（时间项权），`metric` $\to M$（散度项权），两者缺省都取 $V'$（"精确再现旧的单权
算子"）。轴：零通量；边：Dirichlet。〔已确立〕这是磁面平均输运方程的通量形式
{cite}`hinton1976theory`；把时间项写成 $\partial_t(Cy)$ 而非 $C\partial_ty$ 是含时几何下守恒的必要
写法（`GK-TMT-03`）。

(phys05-operator-fv)=
## 有限体积离散 (Finite-Volume Discretisation)

〔实现〕节点值 $y_i$（$i=0..n-1$），通量在 $n-1$ 个面上，控制体取中点、**轴与边各半格**：
$h_{i+1/2}=x_{i+1}-x_i$；面度规 $M_{i+1/2}=\tfrac12(\max(M_i,10^{-12})+\max(M_{i+1},10^{-12}))$
（"钳离零——轴上的度规为零"）；面扩散率与速度取算术平均；宽度 $w_0=h_{1/2}/2$、$w_{n-1}=h_{n-3/2}/2$、
$w_i=\tfrac12(x_{i+1}-x_{i-1})$。离散面通量

$$
F_{i+1/2}=M_{i+1/2}\Big[D_{i+1/2}\frac{y_{i+1}-y_i}{h_{i+1/2}}-v_{i+1/2}\tfrac12(y_i+y_{i+1})\Big]
$$ (eq-p05-flux)

——**中心（算术平均）对流，非迎风**；两点中心扩散。第 0 行无西面项 ⇒ **轴上零通量由构造保证**。
三对角带 $L$ 的系数以 $\hat C_i=\max(C_i,10^{-12})$、$c_{W,E}=M_{i\mp1/2}/(\hat C_iw_i)$ 组装
（`assemble`）；`Faces` 类型"只有一种拼写"，`assemble` 与 `heat_balance` 共读之（T-C23 回归理由）。
〔已确立〕控制体有限体积法与其守恒性见 Patankar {cite}`patankar1980numerical`〔凭记忆〕、
LeVeque {cite}`leveque2007fdm`；中心对流格式在格 Péclet 数 $>2$ 时可产生非物理振荡——本模块依赖
闭包给出的 $v$ 相对 $D$ 足够小，且 Pereverzev–Corrigan 对流项由 $d_{pc}$ 与 $D$ 同步引入而自动满足。

(phys05-operator-pc)=
## Pereverzev–Corrigan 稳定化 (Pereverzev–Corrigan Stabilisation)

〔实现〕面上由当前 Picard 迭代 $y^{(k)}$ 构造：

$$
D^{\rm extra}_{i+1/2}=d_{pc},\qquad
v^{\rm extra}_{i+1/2}=d_{pc}\,\frac{(y^{(k)}_{i+1}-y^{(k)}_i)/h_{i+1/2}}{\bar y_{i+1/2}},\qquad
\bar y_{i+1/2}=\tfrac12(y^{(k)}_i+y^{(k)}_{i+1})
$$ (eq-p05-pc)

（分母 $\abs{\bar y}\le10^{-30}$ 时以 $\mathrm{sign}(\bar y)10^{-30}$ 代之）。扩散部分进矩阵（隐式），对流
部分是冻结在上一迭代的系数（对未知 $y$ 经中心平均仍隐式）；每一 Picard 遍重建。
〔实现〕"两半都在面上由通量所用的同一差商构造，这使抵消在离散层精确而不只在方程层"；
节点式构造"留下与 $d_{pc}$ 成比例的残差，偏置稳态"。负 $d_{pc}$ 拒绝（`PcNegative`, `-4`）。
〔出处〕Pereverzev–Corrigan 格式 {cite}`pereverzev2008stable`：加隐式扩散、减等量显式对流，
收敛时精确抵消而不改变不动点（证明见 `GK-TMT-03`）；测试
`the_pereverzev_corrigan_fixed_point_is_independent_of_d_pc`（$n=41$，$d_{pc}=40$）钉住不动点相对差
$<10^{-9}$ 且迭代数不同。

(phys05-step)=
# 时间步：θ 法 + Picard (The Time Step)

〔实现〕`step_theta(x, y_old, o, diffusivity)`：

1. 守卫：$n<3$ / 长度不合 → `BadGrid`（`-5`）；$\theta\notin[0,1]$ → `-2`；$d_{pc}<0$ → `-4`；
   `dt = inf` 而 $\theta\ne1$ → 报 `SteadyNeedsBackwardEuler`（`-3`，"用向后 Euler 以外的任何东西解稳态
   是另一个方程"）；给 `capacity_old` 而 $\theta\ne1$ → `-9`。
2. 动容量比 $r_i=\max(C^n_i,10^{-12})/\max(C^{n+1}_i,10^{-12})$（`None` 时**完全跳过**而非乘 1 向量：
   "死路径必须是同一套算术"）。
3. Picard 循环（$\le$ `max_inner`）：$D^{(k)}=$ `diffusivity(x, y_k)`；`relax_coeff` $<1$ 时
   $D^{(k)}\leftarrow(1-\omega_c)D^{(k-1)}+\omega_cD^{(k)}$；PC 面项；组装 $L$。
4. 线性系统（逐节点）

$$
\frac{C^{n+1}y^{n+1}-C^ny^n}{\Delta t}=\theta Ly^{n+1}+(1-\theta)Ly^n+S
$$ (eq-p05-theta)

   即 $a_i=-\theta L^{\rm lo}_i$、$b_i=\Delta t^{-1}-\theta L^{\rm diag}_i$、$c_i=-\theta L^{\rm up}_i$、
   $r_i=\Delta t^{-1}r^C_iy^n_i+(1-\theta)(Ly^n)_i+S_i$。**源 $S$ 不按 θ 加权、不作显/隐拆分**——它以
   速率整体进入右端；隐式汇的拆分只是 Python 累加器里的**命名约定**（`_implicit` 路径），
   内核算子不区分。
5. 边行 Dirichlet；Thomas 解；`residual = max|y_new − y_k| / max|y_new|`；
   $y^{(k+1)}=y^{(k)}+\omega(y_{\rm new}-y^{(k)})$；`residual < tol` 止。

〔已确立〕θ 法（$\theta=1$ 向后 Euler，$\theta=\tfrac12$ Crank–Nicolson）对扩散方程无条件稳定
（$\theta\ge\tfrac12$）{cite}`leveque2007fdm`；Picard 迭代对刚性闭包的收敛条件与欠松弛见
`GK-TMT-03`。定态步的缺省参数：`dt=inf, theta=1, d_pc=0, relax=1, relax_coeff=1, tol=1e-8, max_inner=60`。

〔守恒回归〕〔实现〕`heat_balance` 以伸缩恒等式 $\dv{}{t}\sum_iC_iw_iy_i=\sum_iC_iw_iS_i-q_{\rm edge}$
检验每一步（$d_{pc}>0$ 或 $\Delta t\le0$ 时返回 `None`——PC 对只在收敛时抵消）；"价值在回归不在物理声称"。

(phys05-channels)=
# 四个通道 (The Four Channels)

(phys05-channels-heat)=
## 热通道与电子—离子交换 (Heat Channels and Exchange)

〔实现〕

$$
\tfrac32\pdv{(V'nT)}{t}+\pdv q\rho=V'Q,\qquad q=-V'\expval{\abs{\nabla\rho}^2}n\chi\pdv T\rho
$$ (eq-p05-heat)

权：$C_i=\tfrac32V'_in_i$、$M_i=V'_i\expval{\abs{\nabla\rho}^2}_in_i$、$S_i=Q_i/(\tfrac32n_ie)$（$T$ 以 eV，
$Q$ 以 W/m³，$e=1.602176634\times10^{-19}$）。"$V'$ 在最后一式解析抵消并**写成抵消后的形式**——
写成 $V'Q/C$ 在轴上是 $0/0$"。

〔不含的项〕〔实现〕三个文件中没有 $V'^{5/3}$ 绝热压缩因子；含时几何只经 $C^n/C^{n+1}$ 容量比与
标签漂移对流（下文）进入。Python `solve_psi` 文档："$\dot B_0$ 压缩关——fylite 层假定静态真空场"。

〔两温度合步〕〔实现〕`two_temperature_step(_moving)`：$Q_e^{\rm eff}=Q_e-S_{\rm exch}$、
$Q_i^{\rm eff}=Q_i+S_{\rm exch}$（$S_{\rm exch}$ 正向离子），两通道自同一旧态、以同一交换项推进；
`_moving` 变体以 $C^{\rm old}=\tfrac32V'_{\rm old}n_{\rm old}$ 承载密度与几何的运动。交换项在输运层**外**
算（{eq}`eq-p04-exch`）：$S_{\rm exch}=\tfrac32\nu_{\rm exch}n_ek(T_e-T_i)$（`exchange_power`，
CGS，$\times0.1$ 转 W/m³）。

(phys05-channels-density)=
## 粒子通道 (Particle Channel)

$$
\pdv{(V'n)}{t}+\pdv\Gamma\rho=V'S,\qquad \Gamma=V'\expval{\abs{\nabla\rho}^2}\Big(-D\pdv n\rho+vn\Big)
$$ (eq-p05-density)

〔实现〕$C=V'$、$M=V'\expval{\abs{\nabla\rho}^2}$，$D$、$v$（箍缩）为规定数组；**逐离子**求解，
电子密度是准中性闭合 $n_e=\sum_sZ_sn_s$，"刻意不是可解通道"。向后 Euler 外循环至
`steady_delta < tol_steady`。**本 crate 无加料模型**（无弹丸、无充气、无束粒子源）——源 $S$ 是调用方的。
闭式锚：$v=-v_0\rho/a$ 时 $n=n_{\rm edge}\exp\big(\frac{v_0}{2Da}(a^2-\rho^2)\big)$（$2\times10^{-3}$）。

(phys05-channels-momentum)=
## 环向角动量通道 (Toroidal Momentum Channel)

$$
\pdv{(V'nm\expval{R^2}\omega)}{t}+\pdv\Pi\rho=V'T,\qquad
\Pi=-V'\expval{\abs{\nabla\rho}^2}nm\expval{R^2}\chi_\phi\pdv\omega\rho
$$ (eq-p05-momentum)

〔实现〕$C=V'nm\expval{R^2}$、$M=V'\expval{\abs{\nabla\rho}^2}nm\expval{R^2}$、$S=T/(nm\expval{R^2})$，全 SI；
$\chi_\phi$ 是调用方的（"动量扩散率是 TGLF 的输出"）。$\expval{R^2}$ 来自 {ref}`phys04-fsa`。〔出处〕环向角动量
输运方程的磁面平均形式 {cite}`hinton1976theory`；宿主闭包引 Peeters 等 {cite}`peeters2011momentum` §2
（对称性使动量通量为零）。TGYRO 锚：`mflux_i1_tur` 五点列（gyro-Bohm 单位）。

(phys05-channels-psi)=
## 电流扩散（极向磁通）通道 (Current Diffusion)

〔Python 文档中的方程（COCOS 17，全匝 $\psi$ [Wb]）〕

$$
\sigma_\parallel\pdv\psi t=\frac{F^2}{\mu_0B_0\rho}\pdv{}{\rho}\Big[\frac{V'\expval{\abs{\nabla\rho}^2/R^2}}{4\pi^2F}\pdv\psi\rho\Big]-\frac{V'}{2\pi\rho}j_{ni}
$$ (eq-p05-psi)

〔实现〕乘以 $\mu_0B_0\rho/F^2$ 后映到双权算子：$C_i=\max(\sigma_i,1)\mu_0\abs{B_0}\rho^{\rm safe}_i/F_i^2$、
$M_i=\tilde V'_i\tilde g_{2,i}/(4\pi^2F_i)$、$D\equiv1$、$v\equiv0$、$CS_i=-\mu_0\abs{B_0}\tilde V'_ij_{ni,i}/(2\pi F_i^2)$。
〔已确立〕{eq}`eq-p05-psi` 是 $\rho_{\rm tor}$ 坐标下极向磁通扩散方程的标准形（ASTRA 族）
{cite}`pereverzev2002astra,hinton1976theory`。

〔正则化（"上游的，照抄而非重造"）〕〔实现〕$\rho^{\rm safe}_i=\max(\rho_i,h_0/4)$；$n>3$ 时轴两节点的
$\tilde V'$、$\tilde g_2$ 由第 2 节点重建（"磁面平均梯子自己的轴外推否则让 $\psi$ 震 $O(10\%)$"）；
$\sigma\ge1$ S/m；每步后 $\psi$ **单调修复**（运行最大值），修复量 `repaired` **返回而非静默**。
安全因子 $q_i=\mathrm{clamp}\big(2\pi\abs{B_0}\max(\rho_i,\rho_1/2)/\partial_\rho\psi_i,\,0.05,\,100\big)$
（"平点尖峰毒害下游样条"）。

:::{important}
〔调用方契约〕〔实现〕`j_ni` **只含非感应电流**（自举 + 驱动）："欧姆的 $j=\sigma E$ 是这个方程的
未知量；把它折进去会把滞后的 $\sigma E$ 钉进 $\psi$，几十步内掏空电流剖面。"$\sigma_{\rm neo}$ 与自举
电流不在本模块内，经闭包传入（{ref}`phys07-intro`）；公式级 Spitzer 电阻率在 源项层
（$\eta_\perp=1.03\times10^{-4}Z_{\rm eff}\ln\Lambda\,T_e^{-3/2}$ Ω·m，$\eta_\parallel=0.51\eta_\perp$，
{ref}`phys10-intro`）。边界 $\psi_b$ 以 `edge_rate·dt` 推进（"$-V_{\rm loop}/2\pi$"），**每个时间步一次而非
每个 Picard 一次**——"它是钟，不是迭代量"。
:::

〔闭式锚〕〔实现〕圆柱欧姆稳态：$\partial_t\psi$ 均匀 $=U$（$10^{-4}$）、$\psi'=\sigma\mu_0U\rho/2$
（$2\times10^{-4}$ span）、$q=4\pi B_0/(\sigma\mu_0U)$（$10^{-3}$）。

(phys05-moving)=
# 含时几何：动容量与标签漂移 (Moving Geometry)

〔实现〕(i) **动容量**：时间项写成 $(C^{n+1}y^{n+1}-C^ny^n)/\Delta t$（"fytrans 对其 `b0_dot` 所述的判断"），
仅向后 Euler；(ii) **标签漂移**：固定 $\Phi$ 下 $\rho=\sqrt{\Phi/\pi B_0}$，

$$
\dot\rho\big|_\Phi=-\frac\rho2\frac{\dot B_0}{B_0}
$$ (eq-p05-drift)

四通道合步给每个通道的对流速度加 $-\dot\rho$（"网格固定在 $\rho$ 而等离子体不固定，通道看到磁面以
$-\dot\rho$ 漂过"）；$B_0=0$ 或 $\dot B_0=0$ 时返回零向量（死路径）。〔已确立〕{eq}`eq-p05-drift` 由
$\Phi=\pi B_0\rho^2$ 对 $t$ 求导即得。测试：无通量通道在体积移动时保持内容 $C^{\rm new}y^{\rm new}=C^{\rm old}y^{\rm old}$（$10^{-9}$）。

(phys05-core)=
# 芯部合步：CoreMarch (The Core March)

〔理由〕〔实现〕单通道驱动器交错推进"每步创造或销毁 $\tfrac32V'T\,\dd n$ 的能量"；`CoreMarch` 让所有
通道自同一旧态、以同一 $\Delta t$ 推进，闭包对全部通道一起 Picard（`n_coupling` 遍）；热对承载
密度的运动（`capacity_old`）。几何在一步内**冻结**——演化的平衡以新度规在下一次调用进入，即
{ref}`phys02-box` 所述的交替。

〔次序〕〔实现〕每个 `advance`：(1) 钟：`psi_edge += edge_psi_rate·dt`；(2) **密度通道先行**（逐离子，
含漂移），电子随准中性；(3) 热对（`ni_tot = Σ n_s`——"每个热离子共享 $T_i$，离子热通道按总离子密度加权"）；
(4) 电流（`solve_psi`，`n_steps = 1`）；(5) 耦合计数；(6) `steady_delta` 取遍活动通道。

〔步长控制器〕〔实现〕`dt_target = 0`（缺省）**关闭**自适应。开启时：非有限状态 ⇒ $\Delta t\leftarrow\max(\Delta t/2,dt_{\min})$、
回滚全部 `_prev`、`retries += 1`（"有控制器时非有限状态是步太大，不是行军的终点"）；接受的步上
$f=\mathrm{clamp}(dt_{\rm target}/\delta,\tfrac12,2)$，$\Delta t\leftarrow\mathrm{clamp}(\Delta tf,dt_{\min},dt_{\max})$（无记忆）。
`dt_target > 0` 与 `dt = inf` 同时给出 → `-2`（"自适应一个稳态解是矛盾"）。

〔稳态范数〕〔实现〕$\delta=\max_{\rm all}\abs{y^{\rm new}-y^{\rm old}}/\max(10^{-30},\max_{\rm all}\abs{y^{\rm new}})$，
任一非有限 → NaN（"`f64::max` 吞 NaN……发散剖面上的极大折叠报 0.0"）；"一条规则管所有通道，且是**选择**
而非显然范数"。

(phys05-fluxmatch)=
# 稀疏 Newton 通量匹配（TGYRO 型） (Flux Matching)

〔实现〕"模型（TGLF、NEO）与目标装配是调用方的调用；它们之间的代数在这里：Newton 系统、步长钳制、
逐点松弛回退。"

- 再积分（`math_scaleintv`）：自边界向内 $f_{i-1}=f_ie^{s}$（对数量：$n$、$T$）或 $f_{i-1}=f_i-s$（旋转），
  $s=\tfrac12(g_i+g_{i-1})(r_i-r_{i-1})$——"指数上的梯形，与上游一致"。
- 残差（`tgyro_residual`）：method 2 $\abs{f-g}$，method 3 $(f-g)^2$，其他 → `None`（"上游对其他值 STOP"）。
- 雅可比：逐通道探针（每个探针把 $dx$ 加到该通道**所有**半径上），
  $J[(p+pp),(p+ip)]=(f^{(ip)}_{p+pp}-f^0_{p+pp})/dx$——对半径解耦的局域模型精确，代价 `n_evolve` 而非 `p_max` 次额外求值。
- Newton 步：$(J_f-J_g)\delta x=-(f-g)\odot\text{relax}$，LU 部分选主元；奇异 → `-6`（"模型通量对某个梯度不敏感——这是关于物理的陈述"）；
  $\delta x_i\leftarrow\mathrm{clamp}(\delta x_i,\pm dx_{\max})$（"钳制是上游的，对刚性模型承重"）。**目标雅可比 $J_g$ 在矩阵里**："抬高梯度改变剖面从而改变源"。
- 回退（`tgyro_iteration_standard`）：变差点 `relax /= relax_factor` 并回到 $x_0$；`relax < 1/relax_factor³` 时
  `relax = 0.75·relax_factor`、$x=x_0+2\,\text{step}$（"抛得两倍远——认为它卡住而非过冲"）。
- 缺省 `n_evolve=1, dx=0.05, dx_max=1.0, relax_factor=2.0, iterations=8, method=3, tol=None`（每轮都跑，如上游）。
- 可恢复状态机 `Start → IterBegin → Probe → Trial → Backoff → IterEnd → Finished`，"两个模型在每次请求的同一点求值"。

〔出处〕TGYRO 的通量匹配方法 {cite}`candy2009tgyro`〔凭记忆〕；实现只给例程名。收敛标量
`out.tgyro.prec`（treg01：2.49961）作为端到端锚。EAST 几何上 1.5-D 行军稳态与梯度空间通量匹配
$T_e$ 相对差 $2\times10^{-2}$、匹配通量对目标 $10^{-6}$。

(phys05-misc)=
# 通量→系数、gyro-Bohm 单位与解释性反演 (Flux-to-Coefficient, Units, Interpretive Inversion)

$$
\chi_i=\frac{q_i}{\max\big(\expval{\abs{\nabla\rho}^2}_in_ie\max(\abs{\partial_\rho T_i},\text{floor}),\text{floor}\big)},\qquad
D_i=\frac{\Gamma_i}{\max\big(\expval{\abs{\nabla\rho}^2}_i\max(\abs{\partial_\rho n_i},\text{floor}),\text{floor}\big)}
$$ (eq-p05-chi)

〔实现〕"分母被下限，不是结果——钳 $\chi$ 是闭包的事"；$D$ 是**有效**扩散率（"一个通量不能拆成扩散与箍缩"）。
$Q_{GB}=n_ee\,T_e[\text{eV}]c_s(\rho_s/a)^2$ [W/m²]、$\Gamma_{GB}=n_ec_s(\rho_s/a)^2$（**SI 输入**；实现记 CGS 版曾"给出
错 $10^4$ 却看着完全合理的通量"）。〔已确立〕gyro-Bohm 归一 {cite}`waltz1997glf23,staebler2007tglf`。

〔解释性反演〕〔实现〕`interpretive_channel`：$P(\rho_i)$ 累积梯形，$q_{PB,i}=P_i/(V'_i\expval{\abs{\nabla\rho}}_i)$，
$\chi_{{\rm eff},i}=q_{PB,i}/(n_i\expval{\abs{\nabla\rho}^2}_ie\abs{\partial_\rho T_i})$，$\abs{\partial_\rho T}\le$ floor 处 NaN 且 `valid = 0`；
floor 是剖面**特征**梯度的分数（$10^{-3}$，上游）。"两个度规刻意不同：通量经 `gm7` 面积定义，预测性传导律带 `gm3`，
故 $\chi_0$ 传导解反演到 $\chi_0/\texttt{gm7}$——那是上游的约定。"

(phys05-sawtooth)=
# 锯齿混合（最小模型） (Sawtooth Mixing — Minimal Model)

〔实现〕"混合半径内每个剖面替换为其体积平均、$q$ 置 1……**不是 Kadomtsev**，**不是 Porcelli**……触发只是
$q(0)<q_{\rm crit}$……**混合半径是调用方的**，无缺省（约化模型取 $kr_1$，$k\in[1,\sim1.4]$）。"
`q_crossing` 取**最外**的向上穿越（反转半径 = $q<1$ 区的边）——由真实 ITER 平顶（JINTRAC 102530：轴 1.061、
$x=0.15$ 处 0.978、$x=0.455$ 回穿）的实测所改。`sawtooth_crash`：$\bar y=\int V'y\,\dd\rho/\int V'\dd\rho$（内容守恒）；
$\psi$ 自缝口向内以 $q=1$ 重建 $\psi_i=\psi_{i+1}-2\pi\abs{B_0}\tfrac12(\rho_i+\rho_{i+1})(\rho_{i+1}-\rho_i)$。
〔出处〕完全重联模型 {cite}`kadomtsev1975disruptive` 与触发判据模型 {cite}`porcelli1996model`〔凭记忆〕
在此**只作为参照**——本模型不实现它们。

(phys05-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **规定几何**：$V'$、`gm2/gm3/gm7`、$\expval{R^2}$、$F$ 在一步内冻结；平衡演化只经外环交替进入。
2. **无 $V'^{5/3}$ 压缩项、$\dot B_0$ 压缩关**；含时几何只以动容量与标签漂移近似。
3. **中心对流**：格 Péclet 数大时可振荡；本模块依赖闭包与 $d_{pc}$。
4. **源不拆显隐**：状态依赖的汇（如辐射 $\propto n^2$）以速率显式进入，刚性时须减 $\Delta t$ 或用 $d_{pc}$。
5. **电子密度不可解**（准中性导出）；**无加料模型**。
6. **$\psi$ 通道的单调修复**改变解——`repaired` 必须读；$q$ 钳到 $[0.05,100]$。
7. **锯齿模型只是体积平均混合**，无重联物理。
8. **通量匹配假定局域模型**（块对角雅可比精确）——非局域闭包下雅可比是近似。
9. **`steady_delta` 是全通道联合范数**——某个小量级通道的收敛可能被大通道掩盖。
10. **`dt_target` 缺省关**——不给即固定步长。

(phys05-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 输运核的外部 oracle 与闭式锚点。
:name: tbl-p05-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 常数 / 刚性闭包稳态（$n=11$） | fytrans oracle（录得四个值） | 相对 $<10^{-13}$；内迭代数 2 / 27 |
| PC 不动点与 $d_{pc}$ 无关 | 自身（$d_{pc}=40$） | $<10^{-9}$ |
| 动量湍流半 | TGYRO `out.tgyro.flux_i1` | 五点列逐值 |
| $Q_{GB}$ SI 定值 | 手算 | $\approx26$ kW/m²，$10^{-12}$ |
| 箍缩 / 扩散、动量、解释性反演 | 闭式 | $2\times10^{-3}$ / $10^{-9}$ / 精确 |
| 圆柱欧姆稳态 | 闭式 | $\partial_t\psi=U$（$10^{-4}$），$q=4\pi B_0/(\sigma\mu_0U)$（$10^{-3}$） |
| 端到端通量匹配 | TGYRO treg01（`out.tgyro.prec = 2.49961`） | 相对 $2\times10^{-2}$（数据目录本 checkout 缺） |
| 通量匹配 $T_e$ 不动点 | JINTRAC 102530（ITER 15 MA） | RMS 17.95 %（门 12–24 %）；显式冻结 $\chi$ 耦合发散 |
| 常 $\chi$ 平顶 | JINTRAC 102530 | 最佳 $\sim31\%$ RMS 对"不动"零假设 4.1 %——**否证** |
| 录得 $\chi$ 回放 | JINTRAC 101612（JET #58894） | RMS 6.67 %（门 $<9\%$） |
:::

(phys05-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 1.5-D 输运所解的各道方程，及其解所落的 fyo 数据集。
:name: tbl-p05-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 单通道 $\theta$ 步（四档闭包） | `fyo:core_profiles`：$T_e$ / $T_i$ | `assembly.solve_te_ti` |
| 两温度行军 | `fyo:core_profiles`：$T_e$、$T_i$（耦合求解） | `assembly.solve_te_ti` |
| 密度 / 动量 / $\psi$ 道 | `fyo:core_profiles`：$n_e$、环向转速、$\psi$ | `assembly.solve_density/_momentum/_psi` |
| 四通道合步 | `fyo:core_profiles`（一次推进给全部通道） | `assembly.solve_core`；`closure.loop_transport` |
| 通量匹配 | `fyo:core_transport` 的通量与 `fyo:core_profiles` 的剖面自洽 | `S.model.transport` |
| 通量 → 输运系数、gyro-Bohm 单位 | `fyo:core_transport`：$\chi$、$D$ | `closure.kernel_coefficients` |
| 解释性反演（由剖面反推系数） | `fyo:core_transport`（由测量剖面反推） | `S.analysis` |
| 锯齿 | `fyo:core_profiles`（混合后的剖面） | `S.model.evolve` |
| 径向标签漂移 | —（换基时的自检） | —（内部） |
:::

(phys05-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献〕磁面平均输运方程 {cite}`hinton1976theory`；$\rho_{\rm tor}$ 坐标的输运与磁通扩散方程
{cite}`pereverzev2002astra`；有限体积法 {cite}`patankar1980numerical,leveque2007fdm`；
Pereverzev–Corrigan {cite}`pereverzev2008stable`；TGYRO 通量匹配 {cite}`candy2009tgyro`；gyro-Bohm 单位
{cite}`waltz1997glf23,staebler2007tglf`；动量输运对称性 {cite}`peeters2011momentum`；Spitzer 电阻率
{cite}`spitzer1953transport,huba2013nrl`；锯齿参照 {cite}`kadomtsev1975disruptive,porcelli1996model`。
标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕`tgyro_residual`、`tgyro_iteration_standard`、`math_scaleintv`、`evolve_indx`（GACODE，Apache-2.0）；
fytrans（fytok 树，MIT，rev 6b14d6ef）作为**oracle 而非来源** {cite}`fytok_fytrans`；JINTRAC
{cite}`romanelli2014jintrac`、METIS {cite}`artaud2018metis`、TORAX {cite}`citrin2024torax` 作为对拍参照。

〔本仓选择（实现未注出处）〕半格控制体与算术平均面系数；PC 面构造；`steady_delta` 联合范数；
$\psi$ 通道的全部正则化阈值（$h_0/4$、两节点轴重建、$\sigma\ge1$、$q\in[0.05,100]$）；`dt` 控制器的
$[\tfrac12,2]$ 与对半回滚；通量匹配缺省；锯齿体积平均混合与 $q_{\rm crossing}$ 的 $10^{-9}$ 容差。证据为
{numref}`tbl-p05-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
