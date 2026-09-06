---
title: Grad–Shafranov 平衡正解 (The Grad–Shafranov Forward Solve)
subtitle: 定形边界、箱内定形与自由边界三种正解的方程、离散与迭代
---

(phys02-intro)=
# 引言：一个方程，三个正问题 (Introduction)

〔范围〕本章详述**轴对称理想 MHD 平衡正解**：给定电流源（多项式、表格或解析族的 $p'$、$FF'$）与边界条件，
解出极向磁通 $\psi(R,Z)$。它是反演（{ref}`phys03-intro`）、磁面几何（{ref}`phys04-intro`）、
位形演化与垂直稳定性（{ref}`phys12-intro`）的共同底座。

〔三个问题〕同一个 GS 方程，按**已知什么、边界怎么定**分成三个入口，其适定性与失效形态不同
（{numref}`tbl-p02-three`）。本章按这三个入口组织。

:::{table} 平衡正解层的三个正解入口及其数学性质。
:name: tbl-p02-three
:align: left

| 入口 | 已知 | 求 | 数学性质 | 公开入口 |
| :--- | :--- | :--- | :--- | :--- |
| 定形边界（全网格） | 矩形域边界上的 $\psi$ + 多项式 $p'(\bar\psi)$、$FF'(\bar\psi)$ | 域内 $\psi$ | 半线性椭圆 Dirichlet 问题，Picard 迭代 | `solve_fixed_boundary` |
| 箱内定形（子域） | 围绕一团等离子体切出的子箱、其边界上的 $\psi_0$、$p'$/$FF'$ 表或多项式、可选 $I_p$ | 子箱内 $\psi$ 与等离子体掩膜 | 同上，另加边缘平滑截断与 $I_p$ 等式约束 | `solve_fixed_box` |
| 自由边界 | 外部真空场 $\psi_{ext}$（线圈）+ 电流剖面形状 + $I_p$ + 限制器 | $\psi$ **与边界位置** | 双层不动点（场 ↔ 边界），拓扑切换处不可微 | `solve_free_boundary` / `_from` / `_shaped` |
:::

〔清洁室声明〕〔实现〕模块头部声明该层按公开文献独立实现（GS 方程本身、教科书五点差分、
可分离椭圆算子的快速直接法、Solov'ev 解析解），其作者未阅读 EFIT 的 Fortran 实现；对
Fortran 路径的验收是黑箱输出比对。本章据此**不把 EFIT 的实现细节当作本模块的来源**，凡与 EFIT
相同的公开概念（如解析电流族、`CONDIN` 等开关名）只作公开概念引用。

〔与理论手册的分工〕GS 方程从 $\vb{j}\times\vb{B}=\nabla p$ 的逐步推导、$p=p(\psi)$ 与
$F=F(\psi)$ 两条磁面函数证明、自由函数的欠定性讨论，见 SpResearch 理论手册 `GK-TMT-02`
（跨仓引用，以文档标识给出）。本章只复述结论并把重点放在**本内核实际求解的离散方程**上。

(phys02-eq)=
# 方程与规范 (The Equation and Its Gauges)

(phys02-eq-gs)=
## Grad–Shafranov 方程 (The Grad–Shafranov Equation)

〔出发点〕〔已确立〕轴对称理想 MHD 静平衡 $\vb{j}\times\vb{B}=\nabla p$、$\nabla\cdot\vb{B}=0$、
$\mu_0\vb{j}=\nabla\times\vb{B}$，取磁场表示 $\vb{B}=\nabla\psi\times\nabla\phi+F\nabla\phi$
（$\psi$ 为每弧度极向磁通，$F=RB_\phi$），得

$$
\Delta^{\ast}\psi \;=\; -\mu_0 R^2 p'(\psi) - F(\psi)F'(\psi) \;=\; -\mu_0 R\, j_\phi,
\qquad
\Delta^{\ast}\equiv R\pdv{}{R}\!\left(\frac{1}{R}\pdv{}{R}\right)+\pdv{^2}{Z^2}
$$ (eq-p02-gs)

$$
j_\phi \;=\; R\,p'(\psi) + \frac{F(\psi)F'(\psi)}{\mu_0 R}
$$ (eq-p02-jphi)

这是 Grad–Rubin {cite}`grad1958hydromagnetic` 与 Shafranov {cite}`shafranov1966equilibrium`
独立给出的方程；教科书形式见 Freidberg {cite}`freidberg2014ideal`、Wesson {cite}`wesson2004tokamaks`。
〔实现〕模块头部以此形式注明符号与单位：SI，COCOS 17（Sauter–Medvedev 约定
{cite}`sauter2013cocos`）。

(phys02-eq-gauge)=
## 两种磁通规范 (Two Flux Gauges)

〔实现〕本层同时使用两种 $\psi$ 规范；两者的区分是读本章其余部分的前提：

- 每弧度 $\psi$（Wb/rad）——{eq}`eq-p02-gs` 的教科书形式；`solve_fixed_boundary` 与
  g 文件采用；
- 全磁通 $\psi$（Wb，即每弧度值的 $2\pi$ 倍）——L2 互感矩阵（{ref}`phys12-em`）给出的
  $\psi_{ext}$ 与边界值所用的规范；自由边界解在此规范下求解，方程右端成为

$$
\Delta^{\ast}\psi_{\rm Wb} = -\,2\pi\,\mu_0 R\, j_\phi
$$ (eq-p02-gs-wb)

`solve_fixed_box` 把这个因子写成显式参数 `gauge`（$g=2\pi$ 取 Wb，$g=1$ 取每弧度），并把
$p'$ 对 $\bar\psi$ 的导数按 $\dv{p}{\psi}=\dv{p}{\bar\psi}\cdot g/\text{span}$ 换算。
〔实现〕注释记录了混用两种规范的实际后果："短一个 $g^2=4\pi^2$"，且该缺陷曾随某一功能
发布过一次——这是把规范做成显式参数而非约定的直接理由。

(phys02-eq-norm)=
## 归一磁通与源的支撑 (Normalised Flux and the Source Support)

〔定义〕$\bar\psi=(\psi-\psi_a)/(\psi_b-\psi_a)$，$\psi_a$ 为磁轴值、$\psi_b$ 为边界值，
$\text{span}\equiv\psi_b-\psi_a$。三个入口都只在 $0\le\bar\psi<1$（自由边界与箱内解还要求
落在由磁轴四连通泛洪得到的掩膜内）上放置电流源；掩膜之外 $j_\phi\equiv0$。

(phys02-discrete)=
# 离散化与直接解法 (Discretisation and the Direct Solver)

(phys02-discrete-stencil)=
## 守恒型五点差分 (The Conservative Five-Point Stencil)

〔实现〕`DeltaStarSolver` 在均匀网格 $R_i=R_{\min}+i\,\Delta R$、$Z_j=Z_{\min}+j\,\Delta Z$ 上把
$\Delta^{\ast}$ 离散为

$$
(\Delta^{\ast}\psi)_{i,j} \;=\;
\frac{R_i}{\Delta R^2}\left[\frac{\psi_{i+1,j}-\psi_{i,j}}{R_{i+1/2}}
-\frac{\psi_{i,j}-\psi_{i-1,j}}{R_{i-1/2}}\right]
+\frac{\psi_{i,j+1}-2\psi_{i,j}+\psi_{i,j-1}}{\Delta Z^2},
\qquad R_{i\pm1/2}=\tfrac12(R_i+R_{i\pm1})
$$ (eq-p02-stencil)

即 $R\,\partial_R(R^{-1}\partial_R\psi)$ 取**通量形式**（先在半格点求 $R^{-1}\partial_R\psi$
再求差），$\partial_Z^2$ 取标准中心差分。R 向三对角系数为
$a_i=R_i/(\Delta R^2R_{i-1/2})$、$c_i=R_i/(\Delta R^2R_{i+1/2})$、$d_i=-(a_i+c_i)$。

〔精确再现空间〕〔实现〕测试注释指出：该守恒格式对 $R^2$、$R^4$ 与 $Z^2$ 精确（离散算子
作用于这三个单项式给出解析值），故 Solov'ev 多项式解落在离散算子的精确再现空间内——这是
下文 Solov'ev 锚点能到机器精度的原因，也说明该锚点**检验的是求解器而非截断误差**。截断误差
由制造解另测（{ref}`phys02-verify`）。

〔出处〕〔已确立〕守恒型（通量形式）差分是椭圆算子有限差分的教科书内容，见 LeVeque
{cite}`leveque2007fdm`；本仓实现称之为"textbook 5-point finite differences"。

(phys02-discrete-fast)=
## 正弦变换 + Thomas 算法的快速直接解 (Sine-Transform / Thomas Direct Solve)

〔算法〕〔实现〕Dirichlet 问题（边界值取自输入数组的四条边，内部被覆写）按下列四步直接求解：

1. **边界折入右端**：把四条边的已知值乘以相应系数移到内部节点的右端。
2. **Z 向离散正弦变换**（以显式矩阵乘法实现，非 FFT）：
   $s_{kj}=\sin\!\big(\frac{(k+1)(j+1)\pi}{n_z-1}\big)$，$\hat b_{ik}=\sum_j s_{kj}b_{ij}$；
   Z 向二阶差分在该基下对角化，特征值

$$
\lambda_k = -\,\frac{4}{\Delta Z^2}\sin^2\!\left(\frac{(k+1)\pi}{2(n_z-1)}\right)
$$ (eq-p02-eig)

3. **逐模三对角求解**：对每个 $k$，用 Thomas 算法解 $(a_i,\ d_i+\lambda_k,\ c_i)$。
4. **逆变换**：同一矩阵乘以 $2/(n_z-1)$。

〔复杂度〕〔实现〕显式 DST 为 $O(n_z^2)$ 每条 R 线；实现注明在 $65^2$ 网格上可忽略且免除 FFT
依赖——与"无系统数值库、同一份代码编到 wasm"的设计约束一致（{ref}`phys01-intro`）。

〔出处〕这是 Hockney 的快速直接法：把可分离椭圆算子沿一个方向作 Fourier（此处为正弦）
分解，化为一族三对角问题 {cite}`hockney1965fast`〔凭记忆：论文元数据未在本会话核验〕。
实现只写"Hockney's method, any numerical-PDE text"。Thomas 算法（三对角 LU）见
{cite}`press2007nr`。

(phys02-fixed)=
# 定形边界的 Picard 迭代 (Fixed-Boundary Picard Iteration)

(phys02-fixed-profiles)=
## 多项式剖面 (Polynomial Profiles)

〔实现〕`PolyProfiles`：$p'(\bar\psi)=\sum_k a_k\bar\psi^k$、$FF'(\bar\psi)=\sum_k b_k\bar\psi^k$，
Horner 求值。**注意**：此入口的 $p'$、$FF'$ 是对 $\bar\psi$ 的系数但**未除以 span**，且假定
每弧度规范——这是该入口与 `solve_fixed_box`（显式 `gauge`、显式除以 span）的差别，实现
注释把它记为历史遗留。

(phys02-fixed-iter)=
## 迭代格式 (The Iteration)

〔算法〕〔实现〕`solve_fixed_boundary` 每轮：

1. 磁轴 = 内部节点中 $\abs{\psi-\psi_b}$ 最大者（"离边界值最远的内部极值"）；
2. $\bar\psi$ 按 {ref}`phys02-eq-norm` 计算；span 为零（平坦初值）时以 $\bar\psi\equiv0$ 起步；
3. 仅在 $0\le\bar\psi<1$ 处放源：$j_\phi=Rp'(\bar\psi)+FF'(\bar\psi)/(\mu_0R)$，
   右端 $-\mu_0Rj_\phi$（`gauge = 1`）；
4. 直接解（{ref}`phys02-discrete-fast`），然后**欠松弛**

$$
\psi \leftarrow \psi + \omega\,(\psi_{\rm new}-\psi),
\qquad
\text{res} = \frac{\max\abs{\psi_{\rm new}-\psi}}{\max(\abs{\text{span}},10^{-300})}
$$ (eq-p02-relax)

5. $\text{res}\le$ `tol` 即收敛；达到 `max_iter` 则报告（`iterations == max_iter` 且返回残差），
   **不抛错**。
6. 末了 $I_p=\sum_{0\le\bar\psi<1}j_\phi\,\Delta R\,\Delta Z$。

〔收敛性〕〔已确立〕Picard 映射 $\psi\mapsto(\Delta^{\ast})^{-1}[-\mu_0Rj_\phi(\psi)]$ 的收敛
要求它在不动点附近是压缩映射；欠松弛 $\omega<1$ 把谱半径 $\lambda$ 变成 $\abs{1-\omega+\omega\lambda}$，
与理论手册 `GK-TMT-01` 的阻尼定点谱条件同构（跨仓引用）。经典的 GS 正解 Picard 迭代及其
电流重标定见 Johnson 等 {cite}`johnson1979numerical`〔凭记忆〕与 Jardin {cite}`jardin2010computational`。

(phys02-box)=
# 箱内定形解：输运精化用的子域求解 (The Boxed Fixed-Boundary Solve)

〔用途〕〔实现〕`solve_fixed_box` 是为**输运—平衡交替**（{ref}`phys05-intro`）设计的：围绕一团
已知等离子体切一个子箱，边界 Dirichlet 值取自完整解 $\psi_0$ 的箱边，箱内按新的 $p'$、$FF'$
重解。它比全域自由边界解便宜得多，代价是**边界被冻结**。

(phys02-box-eq)=
## 求解的方程（含截断） (The Equation Actually Solved)

〔实现〕以 $g$ = `gauge`、$\text{span}_{pr}=\text{span}/g$、$x=\mathrm{clamp}(\bar\psi,0,1)$：

$$
j_\phi = \frac{T(x)}{\text{span}_{pr}}\left[R\,\hat p'(x)+\frac{\widehat{FF'}(x)+\delta}{\mu_0R}\right],
\qquad
\text{rhs}=-g\,\mu_0R\,j_\phi
$$ (eq-p02-box)

其中 $\hat p'$、$\widehat{FF'}$ 为多项式或表格（线性插值、端点钳制）乘以各自的 `*_scale`；$\delta$
为 $I_p$ 约束带来的 $FF'$ 常数平移（下文）；$T(x)$ 是边缘 **C¹ 平滑截断**：

$$
T(x)=\begin{cases}1, & x\le 1-w\\[2pt] s^2(3-2s),\quad s=\mathrm{clamp}\!\left(\dfrac{1-x}{w},0,1\right), & x>1-w\end{cases}
\qquad w=0.05
$$ (eq-p02-taper)

:::{important}
〔截断是方程的一部分〕〔实现〕$T(x)$ 不是后处理：测试 `the_boxed_solve_satisfies_the_equation_it_names`
断言解出的 $\psi$ 满足的正是**含 $T$ 的** {eq}`eq-p02-box`。$w=0.05$ 的理由记在实现：输运梯子
默认止于 $\psi_N=0.95$、从不越过 $0.99$，故截断带落在输运从不采样的区间；一个在分离面上仍
"活着"的源会使掩膜逐轮外扩（测试 `a_source_alive_at_the_separatrix_no_longer_runs_away`）。
实现另记录两种更便宜的控制（在 X 点处裁真空室、放宽箱）**试过并否决**。$s^2(3-2s)$ 是三次
Hermite 平滑阶跃的标准形，实现未给出处。
:::

(phys02-box-ip)=
## $I_p$ 等式约束 (The Plasma-Current Constraint)

〔实现〕给定 `ip_target` 时，每轮把 $FF'$ 通道平移一个常数使总环向电流精确等于目标：

$$
\delta=\frac{(I_{\rm target}-I_{\rm raw})\,\mu_0\,\text{span}_{pr}}{G},
\qquad
G=\sum_{\rm mask}T(x)\frac{\Delta A}{R},
\qquad
I_{\rm raw}=\sum_{\rm mask}T\left[R\hat p'+\frac{\widehat{FF'}}{\mu_0R}\right]\frac{\Delta A}{\text{span}_{pr}}
$$ (eq-p02-box-ip)

实现把这一步与"给定 $p'$ 与 $I_p$、解出 $FF'$ 常数"的 CHEASE 型定形边界求解器类比
{cite}`lutjens1996chease`；测试 `the_current_constraint_holds_ip_and_reports_the_shift` 钉住
$\abs{I_p-I_{\rm tgt}}/\abs{I_{\rm tgt}}<10^{-9}$。

(phys02-box-axis)=
## 磁轴的亚网格牛顿修正与掩膜 (Sub-Grid Axis Refinement and the Mask)

〔实现〕磁轴先取上一轮掩膜的 Chebyshev 膨胀（半径 `dilate`）∩ 真空室内部上 $\mathrm{sign}\cdot\psi$
的极值节点，再以中心差分的局部二次型作一步牛顿修正：

$$
\det=\psi_{RR}\psi_{ZZ}-\psi_{RZ}^2,\quad
\delta R=\frac{-\psi_R\psi_{ZZ}+\psi_Z\psi_{RZ}}{\det},\quad
\delta Z=\frac{-\psi_Z\psi_{RR}+\psi_R\psi_{RZ}}{\det}
$$ (eq-p02-axis)

$$
\psi_a=\psi_c+\psi_R\delta R+\psi_Z\delta Z+\tfrac12\left(\psi_{RR}\delta R^2+2\psi_{RZ}\delta R\delta Z+\psi_{ZZ}\delta Z^2\right)
$$ (eq-p02-axis-val)

修正只在 $\abs{\det}>10^{-300}$ 且 $\abs{\delta R}\le\Delta R$、$\abs{\delta Z}\le\Delta Z$ 时采纳。
等离子体掩膜 = 自磁轴出发、在 $s\psi>s\psi_b$ 且位于真空室多边形内（射线法奇偶规则，
{ref}`phys02-free-boundary`）的节点上作**四连通泛洪**；迭代中限制在上一轮掩膜膨胀 3 格
（`FIXED_BOX_TRUST`）的信任域内，收敛后不受限重泛洪一次，若触及箱边或越出信任域则拒绝。
真空室内的私有磁通团（与磁轴不连通）因此**不入掩膜**（测试
`the_plasma_is_connectivity_and_a_private_flux_blob_stays_out`）。

〔拒绝码〕〔实现〕`-2` 尺寸不合（`psi0.len() != n`、`nr<3`、`nz<3`）；`-3` 种子不在等离子体内；
`-4` 掩膜越出信任域；`-5` 磁轴找不到；`-6` span 为零。

(phys02-free)=
# 自由边界解 (The Free-Boundary Solve)

(phys02-free-split)=
## 场的分解与 Green 函数边界 (Field Split and the Green-Function Border)

〔结构〕〔实现〕$\psi=\psi_{ext}+\psi_{pl}$：$\psi_{ext}$ 为线圈（与被动导体）在网格上的真空场，
由 L2 电磁层给出（{ref}`phys12-em`）；$\psi_{pl}$ 在矩形域内满足

$$
\Delta^{\ast}\psi_{pl}=-2\pi\mu_0R\,\frac{I_{\rm cell}}{\Delta A}\quad(\text{内部}),
\qquad
\psi_{pl}\big|_{\partial\Omega}=\sum_k M(R_b,Z_b;R_k,Z_k)\,I_k
$$ (eq-p02-free-split)

边界值由 `BorderGreen` 对每个边界节点 $b$ 与每个内部节点 $k$ **直接求薄丝互感**
$M(R_b,Z_b;R_k,Z_k)$（{ref}`phys01-filament`），复杂度 $O(n_{\rm border}\cdot n_{\rm int})$。
〔实现〕这是**直接 Green 函数求和**，不是 von Hagenow–Lackner 型的边界积分法；实现中不出现
后者。自由边界问题以 Green 函数闭合矩形域的经典做法见 Lackner {cite}`lackner1976computation`〔凭记忆〕
与 Jardin {cite}`jardin2010computational`。

(phys02-free-current)=
## 电流模型 (Current Models)

〔解析族〕〔实现〕`AnalyticProfile {beta0, emp, enp, r0}`：

$$
j_\phi = j_c\left[\beta_0\frac{R}{R_0}+(1-\beta_0)\frac{R_0}{R}\right](1-\bar\psi^{e_{mp}})^{e_{np}},
\qquad
j_c=\frac{I_p}{\sum_{\rm cells}S\,\Delta A}
$$ (eq-p02-analytic)

$j_c$ 每轮重定使总电流精确为 $I_p$；$1-\bar\psi^{e_{mp}}\le0$ 时取零。实现称其为"公开的
EFIT 型解析电流参数化（Lao 等的谱系，按已发表形式）"，即 Lao 等 1985 年论文中的
$(\beta_0,\,e_{mp},\,e_{np})$ 族 {cite}`lao1985efit`。

〔表格族〕〔实现〕表格式电流源（给定 $x$、$p'$、$FF'$ 三列）：形状 $S(R,x)=Rp'(x)+FF'(x)/(\mu_0R)$，
线性插值、端点钳制、分母以 $10^{-300}$ 保护；同样每轮按 $I_p$ 归一，因此表格的**规范**
（每弧度或 Wb）、总体符号与常数因子**全部除掉**——这是把表格与解析族置于同一 Picard 中的
必要条件。

〔表达力边界〕〔实现〕记录：EAST #137985 交付剖面的 $j_\phi$ 在 $\psi_N\approx0.82$ 处变号，
**任何** $(\beta_0,e_{mp},e_{np})$ 成员都表达不了，最佳成员对交付 $j$ 的相对 RMS 为 11.5 %
（$\beta_0=0.10$、$e_{mp}=1.50$、$e_{np}=2.20$）。见用户指南保真度章的"正解侧的两条"。

(phys02-free-boundary)=
## 边界判定：限制器、X 点与瓶颈规则 (Boundary: Limiter, X-Point and the Bottleneck Rule)

〔三个原语〕〔实现〕

- **点在多边形内**：射线法奇偶规则（`inside_polygon`，折线隐式闭合）。〔已确立〕射线交叉
  计数是点与多边形位置关系的经典算法 {cite}`shimrat1962algorithm`〔凭记忆〕。
- **视线检验** `ray_sees_axis`：自候选接触点到磁轴的直线上按 $\lceil d/(0.5\min(\Delta R,\Delta Z))\rceil$
  （至少 8）个样本双线性采样 $\psi$，任一样本 $s\psi<sv-\text{tol}$ 即拒绝，
  $\text{tol}=\max(10^{-9},10^{-3}\abs{s\psi_a-sv})$。实现记录 $10^{-6}\abs{v}$ 的容差会误拒真正的
  限制器接触。
- **限制器接触磁通** `limiter_psi`：沿限制器折线每 $0.5\min(\Delta R,\Delta Z)$ 采样，取能看见磁轴的
  候选中 $\max(s\psi)$；可选**私有区守卫**排除 $\abs{Z}>z_{cut}$ 的壁点。〔实现〕守卫按 FreeGS
  的做法（实现给出其 `equilibrium.py:551`）{cite}`dudson_freegs`，有效 X 点候选在 $Z_x$ 时
  $z_{cut}=0.75\abs{Z_x}$。实测（EAST #137985，$65\times65$）：无守卫接触磁通 3.2762 Wb → 鞍点落在
  $\psi_N=1.213$（判为"限制器"）；有守卫 3.126 Wb → $\psi_N=1.000$（判为"偏滤"）。

〔X 点〕〔实现〕`find_xpoint`：对限制器内每个内部节点（索引 $2..n_r-2$）作中心差分梯度与
Hessian，$\det<0$ 为鞍点候选；牛顿步 $H\delta=-\nabla\psi$，$\abs{\delta R}\le1.5\Delta R$、
$\abs{\delta Z}\le1.5\Delta Z$ 才接受；距磁轴 $3\max(\Delta R,\Delta Z)$ 内者剔除；取二次外推
$s\psi_x$ 最大者。

〔瓶颈规则〕〔实现〕`bottleneck_boundary` 定义每个格点的**最大瓶颈值**

$$
B(\text{cell})=\max_{\text{自磁轴的路径}}\ \min_{\text{路径上}} s\psi
$$ (eq-p02-bottleneck)

以"下降 Dijkstra 泛洪"（二叉堆，保序 u64 键）计算；限制器样本的约束为
$\min(s\psi_{\rm sample},\max_{4\ \text{nodes}}B)$，$\psi_b=\max$ 取遍样本。实现注明：**限制与偏滤
用同一条规则**——最后闭合磁面是"能从磁轴连通到达的最深磁通水平"，限制器 / X 点二分法
由此消失。〔已确立〕最大瓶颈（最宽路径）问题是最短路问题的极小—极大变体，Dijkstra 型算法
{cite}`dijkstra1959note` 把 $+$ 换成 $\min$、$\min$ 换成 $\max$ 即得；实现未给出处。

〔综合判定〕〔实现〕`judge_boundary`：磁轴 = 真空室内 $s\psi$ 最大节点（有等离子体后限制在
上一轮电流支撑的 ±2 格膨胀内）+ {eq}`eq-p02-axis` 修正；X 点候选须 $sp_x>sp_{\rm lim}$、
$sp_x<s\psi_a$ 且距磁轴 $>2\min(\Delta R,\Delta Z)$ → `bnd_kind = 1`；瓶颈值与视线值按权重
$w_{los}$ 混合 $\psi_b\leftarrow(1-w_{los})\psi_b+w_{los}\psi_{b,\rm bott}$；混合后若仍判限制器
而 $\abs{p_x-\psi_{b,\rm bott}}\le x_{\rm match}\abs{\psi_a-\psi_{b,\rm bott}}$ 则改判 X 点
（$x_{\rm match}$：迭代中 $10^{-3}$，稳定退出时 $10^{-2}$）。

(phys02-free-iter)=
## Picard 迭代、虚拟线圈反馈与启动 (Iteration, Virtual-Coil Feedback and Bootstrap)

〔更新式〕〔实现〕全磁通规范下

$$
\psi \leftarrow \psi+\omega\left[\psi_{ext}+a_{fb}P_{fb}+a_{fb,r}P_{fb,r}+\psi_{pl}-\psi\right]
$$ (eq-p02-free-update)

$P_{fb}$、$P_{fb,r}$ 是位于网格外侧 $z_{fb}=Z_{\max}+\tfrac12(Z_{\max}-Z_{\min})$、
$R_c=\tfrac12(R_0+R_{n_r-1})$ 的一对**虚拟丝**的反对称（垂直场）与对称（近均匀 $B_Z$）模式。

:::{note}
〔为什么需要反馈〕〔实现〕固定电流的 Picard 映射对刚性垂直模是**不稳定**的——实现引 Jardin
《Computational Methods in Plasma Physics》§4.4 {cite}`jardin2010computational`，即
{ref}`phys12-vstab` 定量化的 $\gamma>0$ 同一物理。虚拟上下反对称线圈对施加与电流质心位移成
比例的恢复场：

$$
a_{fb}=-G\abs{I_p}(z_c-z_{\rm ref})-4G\abs{I_p}(z_c-z_{c,\rm last}),\qquad \abs{a_{fb}}\le2\abs{I_p}
$$ (eq-p02-fb)

（D 项只在斜坡闩锁打开后加入；径向同型，对 `rc_anchor`）。`zc_anchor` 为 NaN 时收敛处按
$z_{\rm ref}\mathrel{+}=0.5\,a_{fb}/(G\abs{I_p})$ 作下垂修正。增益形式、D 因子 4、限幅 $2\abs{I_p}$、
下垂因子 0.5 为**本仓选择**，实现未给文献。
:::

〔启动〕〔实现〕真空场**没有内部极值**（$\Delta^{\ast}\psi_{ext}=0$ 服从极大值原理〔已确立〕，
椭圆方程的极值原理见 {cite}`evans2010pde`），故第一轮以真空室质心处半径
$0.3\cdot\min(L_R,L_Z)/2$ 的均匀电流盘（按 $I_p$ 归一）起步；给出热启动场时改用其内部极值位置。

〔闩锁与斜坡〕〔实现〕`zc_anchor` 有限且残差 $<5\times10^{-2}$ 时记 `ramp_at`，
$w_{los}=\min((it-\text{ramp\_at})/150,1)$；守卫闩锁同阈值。实现记录无记忆的 `residual < 5e-2`
门会把过渡本身变成守卫开/关的极限环；无锚定的解保留旧规则，其失败形态被记为"角落乒乒
$\pm3.9\times10^6$ A → 极限环 → 在错误的壁上以 $-787$ kA 反馈收敛"。

〔拒绝码〕〔实现〕`-7` 限制器不包含任何节点；`-6` 掩膜电流为空或相消
（`total_abs == 0 || |total| <= 1e-9 * total_abs`——带变号的表格可使有符号和几乎相消）；
`-5` span 为零。

(phys02-free-verdict)=
## 收敛裁决：converged 与 settled (Convergence Verdicts)

〔实现〕残差同 {eq}`eq-p02-relax`。两级裁决：

- **converged**：残差 $\le$ `tol` **且**掩膜连续 `MASK_STABLE_ROUNDS = 2` 轮不变；
- **settled**：尾窗 `SETTLE_WINDOW = 40` 轮内每轮翻转格数 $\le$ `settle_jitter_cap = max(cells/50, 4)`、
  翻转出现于 $\ge10$ 轮、span 与轴磁通漂移 $\le10^{-2}\abs{\text{span}}$。

实现给出两个实测量级作为该分级的依据：抖动地板 $2\times10^{-3}$，周期 2 极限环 $1.3\times10^{-1}$。
退出时以 $w_{los}=1$、$x_{\rm match}=10^{-2}$ 在**最终场**上重判边界（仅在非退化时采纳）。
结果字段：`psi, psi_axis, psi_bnd, axis_r, axis_z, ip, iterations, residual, bnd_kind, xpt_r, xpt_z, fb_amp, zc, converged, settled, mask_delta, jc`。

(phys02-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **闭合嵌套磁面与轴对称**是 GS 方程成立的前提〔已确立〕；有磁岛或三维扰动时 $p$、$F$ 不再是
   $\psi$ 的单值函数，方程本身失效（推导见 `GK-TMT-02`）。
2. **均匀矩形网格**：{eq}`eq-p02-stencil` 只用 $\Delta R$、$\Delta Z$；非均匀网格不在本模块内。
3. **两种规范不可混用**：每弧度与 Wb 的混用差 $4\pi^2$（{ref}`phys02-eq-gauge`）。
4. **解析电流族的表达力**：不能表达变号的 $j_\phi$（EAST #137985 最佳成员 11.5 % RMS）。用表格族
   或反演（{ref}`phys03-intro`）。
5. **Picard 不收敛按报告处理**：定形边界入口返回 `iterations == max_iter` 与残差而不抛错；
   自由边界入口给 `converged/settled` 两级裁决——读者须检查这两个字段而非只看 `psi`。
6. **箱内解冻结边界**：{ref}`phys02-box` 只在子箱内重解，边界磁通取自旧解；边界随剖面的变化
   不在其中，且 $\psi_N>0.95$ 处的解被 $T(x)$ 修改（{eq}`eq-p02-taper`）。
7. **虚拟线圈反馈是数值装置**：$a_{fb}$、$a_{fb,r}$ 不是物理线圈电流；结果中报告 `fb_amp` 是为了让
   读者判断"收敛"依赖了多大的人为恢复场。
8. **不适定分岔**：自由边界的双层不动点在限制器 ↔ 偏滤拓扑切换处不可微（`GK-TMT-02`）；本模块
   以瓶颈规则消除二分法、以闩锁抑制极限环，但**不保证**在切换点附近唯一收敛。

(phys02-verify)=
# 验证锚点 (Verification Anchors)

〔实现〕以下为 平衡正解层单元测试所钉住的定值，是本章陈述的证据：

:::{table} 平衡正解的验证锚点（均为内核单元测试）。
:name: tbl-p02-verify
:align: left

| 锚点 | 内容 | 判据 |
| :--- | :--- | :--- |
| Solov'ev 解析解 | $\psi=\tfrac f8R^4+\tfrac g2Z^2+c_2R^2$，$\Delta^{\ast}\psi=fR^2+g$；$f=-1.2$、$g=-0.8$、$c_2=0.35$，$R\in[1.0,2.6]$、$Z\in[-0.9,0.9]$ | 最大误差 $<10^{-10}$（$33^2$）、$<10^{-9}$（$65^2$） |
| 制造解 | $\psi_m=\sin(2.3R)\sin(1.9Z)$ | 观测阶 $\log_2(e_{33}/e_{65})\in(1.7,2.3)$ |
| 算子—解器互逆 | `apply_deltastar` ∘ `solve` | 往返残差 $<10^{-9}$ |
| 定形 Picard | $33^2$，$p'=-8\times10^3(1-\bar\psi)$，$FF'=-0.6(1-\bar\psi)$，$\omega=0.5$，tol $10^{-10}$ | $<200$ 轮收敛 |
| 箱内 $I_p$ 约束 | {eq}`eq-p02-box-ip` | $\abs{I_p-I_{\rm tgt}}/\abs{I_{\rm tgt}}<10^{-9}$ |
| 箱内方程一致 | 含 $T(x)$ 的 {eq}`eq-p02-box` | $\Delta^{\ast}$ 残差 / 源尺度 $<10^{-8}$（$49^2$） |
| 规范只是尺度 | Wb 与每弧度两解 | 场差 $<10^{-10}$ span，$I_p$ 一致到 $10^{-10}$ |
| 表格 = 系数 | 同一源的两种写法 | $10^{-12}$ span |
| 表格族再现解析族 | $e_{mp}=e_{np}=1\Rightarrow p'=(\beta_0/R_0)g$、$FF'=\mu_0R_0(1-\beta_0)g$ | 场差 $10^{-9}$ span，迭代数相同 |
| 私有区守卫 | 守卫只收窄、不发明 | 测试 `the_private_region_guard_narrows_and_never_invents` |
:::

Solov'ev 解族的原始出处为 {cite}`soloviev1968theory`（实现只写"Solov'ev closed-form solution"）。

(phys02-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 三种正解的产出，及其所落的 fyo 数据集。
:name: tbl-p02-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 离散 $\Delta^{\ast}$ 与直接解（{ref}`phys02-discrete`） | —（三种正解共同的算子，其解即下列各行） | `fylite.kernel.deltastar_apply` |
| 定形边界 Picard（{ref}`phys02-fixed`） | `fyo:equilibrium`：$\psi(R,Z)$、磁轴、$I_p$ | `code/forward`（定形边界细化在门内；扁平 `gs_fixed_solve` 自 T-4 第十四刀起只在内核仓神谕树） |
| 箱内定形解（{ref}`phys02-box`） | `fyo:equilibrium`：同上，另出 $FF'$ 位移与原始 $I_p$ | 输运精化外环（{ref}`phys05-intro`） |
| 自由边界（{ref}`phys02-free`） | `fyo:equilibrium`（含边界与 X 点）＋ `fyo:pf_active` 的线圈电流 | `code/forward`；`S.model.coupled`；`S.control.evolution` |
| 边界判定（{ref}`phys02-free-boundary`） | `fyo:equilibrium`：边界类型（限制器 / 偏滤器）与边界磁通 | —（随上一行的解一起给出） |
:::

(phys02-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献〕GS 方程 {cite}`grad1958hydromagnetic,shafranov1966equilibrium`；Solov'ev 解
{cite}`soloviev1968theory`；解析电流族 $(\beta_0,e_{mp},e_{np})$ 与 EFIT 谱系
{cite}`lao1985efit`；自由边界 Picard 的垂直不稳定性 {cite}`jardin2010computational`；
快速直接法 {cite}`hockney1965fast`〔凭记忆〕；Picard 正解与电流重标定 {cite}`johnson1979numerical`〔凭记忆〕；
Green 函数闭合矩形域 {cite}`lackner1976computation`〔凭记忆〕；守恒差分 {cite}`leveque2007fdm`；
三对角算法 {cite}`press2007nr`；极大值原理 {cite}`evans2010pde`；Dijkstra 算法 {cite}`dijkstra1959note`；
射线法 {cite}`shimrat1962algorithm`〔凭记忆〕；COCOS {cite}`sauter2013cocos`。

〔转引〕FreeGS 私有区守卫的形式取自其源码（源码注给出行号）{cite}`dudson_freegs`，
静态阅读口径；CHEASE 型 $FF'$ 常数吸收 $I_p$ 约束的类比 {cite}`lutjens1996chease`。

〔实现未注出处、本章归类为本仓选择〕瓶颈规则统一限制器与偏滤边界；视线检验及其容差；
虚拟线圈反馈的增益形式、D 因子 4、限幅 $2\abs{I_p}$、下垂因子 0.5；`converged/settled` 两级裁决的
全部阈值；边缘截断宽度 $w=0.05$ 与信任域 3 格；箱内解的 $I_p$ 平移写法。这些是**算法工程决策**
而非物理定律，其证据是 {numref}`tbl-p02-verify` 的测试与实现记录的实测，不是文献。

〔跨仓〕方程推导与不适定性理论：SpResearch `GK-TMT-02`（以文档标识引用）。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
