---
title: 物理与数值 · 平衡重构的反问题 (Physics & Numerics — Equilibrium Reconstruction)
subtitle: inverse.rs —— 外层 Picard、内层约束线性最小二乘、基函数、约束行族与截断谱正则化
---

(phys03-intro)=
# 引言：反问题的结构 (Introduction)

〔范围〕本章详述 `inverse.rs`（约 2400 行）实现的**磁测量约束平衡重构**：给定磁通环 / 磁探针
读数、线圈电流（可带 σ 先验）、总电流 $I_p$，以及可选的动理学压强点、磁面平均电流约束与
径向锚，反求 $p'(\bar\psi)$、$FF'(\bar\psi)$ 的多项式系数与 $\psi(R,Z)$。它复用
{ref}`phys02-intro` 的全部正解原语（离散 $\Delta^{\ast}$、边界判定、Green 边界），只**替换电流源**。

〔结构〕〔源码〕模块头部声明所采用的是 Lao 等 1985 年发表的结构 {cite}`lao1985efit`：
**外层** Picard 迭代更新平衡，**内层**对 $p'$、$FF'$ 的多项式系数作**线性**最小二乘拟合，
以总电流为**等式约束**。同一头部声明清洁室纪律（作者未读 EFIT 源码；验收为黑箱：同通道
拟合优度在 Fortran 路径的 10 % 内、标量差在 K-12 后验 1σ 内）。

〔信息极限〕〔已确立〕外部磁测量原则上只能确定等离子体边界形状、$I_p$ 与组合量
$\beta_p+\ell_i/2$（Shafranov 积分）{cite}`shafranov1971determination`〔凭记忆〕；内部电流剖面
的其余自由度不可辨识，须由压强、极化（MSE）或磁面电流约束补入 {cite}`lao1990equilibrium`〔凭记忆〕。
这一极限的推导、三重简并与"约束阶梯"见理论手册 `GK-TMT-05`（跨仓）。本章多处实测数字
（用户指南保真度章）是它的定量版本。

(phys03-basis)=
# 基函数与电流列 (Basis Functions and the Current Columns)

〔边缘零化约化多项式基〕〔源码〕以 $x=\bar\psi\in[0,1]$，

$$
\phi^{p}_k(x)=x^k-x^{n_{pp}}\ (k=0,\dots,n_{pp}-1),\qquad
\phi^{F}_k(x)=x^k-x^{n_{ff}}\ (k=0,\dots,n_{ff}-1)
$$ (eq-p03-basis)

由构造 $p'(1)=FF'(1)=0$。源码注：这对应 EFIT 公开输入 `PCURBD = FCURBD = 1` 的缺省；
`KPPCUR=2 / KFFCUR=3` ⇒ $n_{pp}=1$、$n_{ff}=2$（Python 缺省）。**为什么需要边缘条件**：源码记录
"无此条件时纯磁通环拟合退化——实测条件数 $8\times10^{16}$、系数 $\pm10^8$"。环境变量
`FY_EDGE_FREE(_FF)` 可切回裸幂基 $x^k$（理由：Fortran 路径自己的边缘 $p'$ 非零，$+1.57\times10^4$，
为轴值的 17 %）。

〔基电流列〕〔源码〕每个基函数在每个掩膜格上的"单位系数电流"

$$
b^{p}_k(\text{cell})=R\,\phi^p_k(x)\,\Delta A,\qquad
b^{F}_k(\text{cell})=\frac{\phi^F_k(x)}{\mu_0R}\Delta A,\qquad
j_\phi=\sum_kc_k\,b_k/\Delta A
$$ (eq-p03-cols)

待拟向量 $c=[\,c^p_{0..n_{pp}-1}\,|\,c^F_{0..n_{ff}-1}\,|\,\Delta I_{\rm free\ coils}\,]$。

(phys03-rows)=
# 设计矩阵的行族 (The Row Families of the Design Matrix)

〔行序〕〔源码〕每轮外迭代在当前掩膜上重装：磁类行（$n_{\rm loops}$）· 压强行（$n_p$）·
两条软边缘零先验 · 每个拟合线圈一条先验 · 磁面平均电流行（$n_j$）· 径向锚行。

(phys03-rows-mag)=
## 磁类行与线圈列 (Magnetic Rows and Coil Columns)

$$
A_{d,k}=\texttt{meas\_scale}\sum_{\rm cells}M_d(\text{cell})\,b_k(\text{cell}),\qquad
b_d=\text{meas}_d-\texttt{meas\_scale}\cdot(\text{规定电流 } j_{\rm pre}\text{ 的预测})
$$ (eq-p03-magrow)

$M_d$ 为通道 $d$ 对格点单位电流的响应（{ref}`phys12-em`）；权重 `wts`，0 表示屏蔽。
〔源码〕`meas_scale` 是"EFIT 的 Wb/rad 符号 $-1/(2\pi)$，由 Python 提供"；Python 层实际传
$+1/(2\pi)$（"环约定：+全磁通 / 2π"）并把探针行（特斯拉）预乘 $2\pi$，使其经共同缩放后仍以
自身单位出现。〔观测算子〕〔已确立〕磁类观测对电流**线性**，其雅可比就是 Green 响应阵——
这是"正反共用一核"的依据（`GK-TMT-09`，跨仓）。

〔线圈列〕〔源码〕`CoilObs`：$A_{d,n_c+f}=\text{rows}[d,\text{ch}]$，**不**乘 `meas_scale`（"线圈响应行就是
通道本身，每安培"）；每个拟合线圈一条先验行 $(\texttt{meas\_sigma}/\sigma_c)\,\Delta I_c=0$
——先验权重是 $1/\sigma_c$ 缩放进测量权重所处的公共规范；$\sigma_c\le0$ 或非有限的通道**精确
保持**。每轮 $\psi_{ext,\rm eff}=\psi_{ext}+\sum_c\Delta I_c\psi_c$。

:::{important}
〔两个 σ 的问题〕〔源码 / 用户指南保真度章〕加权最小二乘只有在 $w=1/\sigma$ 时才是后验；本仓
卷宗给的磁通环权重是 0/1 掩膜，等于宣称 $\sigma_{\rm loop}=1$ Wb/rad。对着一条百分之几的线圈
先验，这等于说"磁通环不值钱"——实测 20 % 的线圈先验只把电流挪了 $3\times10^{-4}$。故
`meas_sigma`（"权重 1.0 代表多大的测量误差"）是**必须由读者给出**的参数，不是可省的缺省。
:::

(phys03-rows-pressure)=
## 压强行 (Pressure Rows)

〔源码〕给定动理学压强点 $p(x_j)$，以 $p(x)=-\text{span}_{pr}\int_x^1p'(t)\dd t$、
$\text{span}_{pr}=(\psi_b-\psi_a)/(-2\pi)$：

$$
A_{j,k}=-\text{span}_{pr}\,[I_k(x_j)-I_{\rm top}(x_j)],\qquad
I_k(x)=\frac{1-x^{k+1}}{k+1},\quad I_{\rm top}(x)=\frac{1-x^{n_{pp}+1}}{n_{pp}+1}
$$ (eq-p03-prow)

$FF'$ 列为零。源码逐字记录了符号翻转一次又回退的历史（2026-08-14），判据是在此规范下 $p'$
应为负（$p'(\text{axis})=-5.90\times10^4$ 对 EFIT 自身 $-9.4\times10^4$）。Python：
$w_p=1/(0.05\max\abs{p})$（`pressure_sigma_frac = 0.05`），缺省 9 个点落在 $[0.1,0.9]$。
〔出处〕以动理学压强约束 $p'$ 是 Lao 等 1990 年的"kinetic EFIT"路线 {cite}`lao1990equilibrium`〔凭记忆〕。

(phys03-rows-fsa)=
## 磁面平均电流行 (Flux-Surface-Averaged Current Rows)

〔测度〕〔源码〕`fsa_current_row` 实现 EFIT 公开开关 `KZEROJ/SIZEROJ/VZEROJ`（`RZEROJ = 0`）
的测度：$p'$、$FF'$ 在一个磁面上为常数，故

$$
\frac{\expval{j_\phi/R}}{\expval{1/R}}=\frac{p'(x)+FF'(x)\expval{R^{-2}}/\mu_0}{\expval{R^{-1}}}
\;\Rightarrow\;
\text{raw}_{j,k}=\frac{\phi^p_k(x_j)}{\expval{R^{-1}}},\quad
\text{raw}_{j,n_{pp}+k}=\frac{\phi^F_k(x_j)\expval{R^{-2}}}{\mu_0\expval{R^{-1}}}
$$ (eq-p03-fsa)

$\expval\cdot$ 由 `surfaces::surface_integrals`（权重 $R\,\dd l/\abs{\nabla\psi}$，{ref}`phys04-fsa`）在
$\psi_a+x\,\text{span}$ 处描迹的等值线（64 条射线）上求得。**行作为形状施加**：
$A_j=\text{raw}_j-v_j\cdot\overline{\text{raw}}$、$b_j=0$、权重 `wj`——"齐次、线性，幅值完全留给 $I_p$ 等式"。
描不出的磁面权重置零并计入 `fsa_rows_used`。Python 记录可用权重带 $10^{-7}\dots10^{-3}$；权重 1
"把磁轴挪 231 mm"。

〔物理来源〕$\expval{j_\phi/R}/\expval{1/R}$ 与 $\expval{\vb j\cdot\vb B}$ 的关系（含抗磁项）是
{ref}`phys07-intro` 自举电流回灌反演的换算恒等式（用户指南保真度章实测残差 $2.65\times10^{-12}$）。

(phys03-rows-anchor)=
## 径向锚行与边缘先验 (Radial Anchor and Edge Priors)

〔源码〕径向锚（2026-08-31 起缺省；`ANCHOR_W_DEFAULT = 10.0` $=1/\sigma_R$，$\sigma_R=0.1$ m）：

$$
A_{rc,k}=\sum_{\rm cells}(R-R_{\rm anchor})\,b_k/I_p,\qquad b=0
$$ (eq-p03-anchor)

即 $\sum_{\rm cells}(R-R_{\rm anchor})j\,\dd A=0$ ⇔ 电流质心 $=R_{\rm anchor}$。**垂直**锚刻意保留
为反馈**力**而非最小二乘行：源码实测"一条最小二乘行不能阻止逃逸（磁轴走到 $+96.7$ mm）"。
边缘零软先验（全 1 行，权重 `FY_EDGE_WP/WF`，缺省 0 即惰性）。

〔$I_p$ 等式〕$g_k=\sum_{\rm cells}b_k(\text{cell})$（线圈列为 0），目标 $I_p-I_{\rm pre}$。

(phys03-lstsq)=
# 约束最小二乘：列均衡 + 截断谱 + Lagrange 消元 (The Constrained Least-Squares Solve)

〔问题〕$\min\norm{W(Ac-b)}^2$ s.t. $g\cdot c=I_p$。〔源码〕`constrained_lstsq(_h)` 的实现：

1. 正规方程 $N=A^TW^2A$、$r=A^TW^2b$（$w=0$ 的行跳过）。
2. **列均衡** $S=\mathrm{diag}(N_{ii}^{-1/2})$，$\tilde N=SNS$（单位对角）——源码理由："$p'$ 与 $FF'$ 列
   相差约 $10^6$ 量级"。〔已确立〕对角缩放是改善条件数的标准预处理 {cite}`golub2013matrix`。
3. 循环 Jacobi 特征分解（{ref}`phys01-linalg`），特征值降序。
4. **截断**：丢弃 $\lambda<\lambda_{\max}/\texttt{CONDIN}$，`CONDIN = 1.0e8`（源码："EFIT 的 `CONDIN`
   输入所起的角色（公开开关名；数值由此处实验选定，不取自受限源码）"；`FY_CONDIN` 可覆盖）。
   **保留数带滞回**（`n_keep` 跨外迭代持久）：一个模只有高于 $3\times$ 截断才进入、低于
   $\text{截断}/3$ 才退出——无记忆截断"一步之内旋转系数向量……0.3 松弛的场吃到 30 % span 的踢"。
5. 截断伪逆 $N^+y=S\sum_{m<\text{kept}}\frac{(v_m\cdot Sy)}{\lambda_m}v_m$；Lagrange 消元
   $x_1=N^+r$、$x_2=N^+g$、$\lambda=(I_p-g\cdot x_1)/(g\cdot x_2)$、$c=x_1+\lambda x_2$。
   $\lambda_{\max}\le0$ 或 $g\cdot x_2=0$ 时返回 `None`。`cond_out` $=\lambda_{\max}/\lambda_{\min}$。

〔数学评注〕〔已确立〕(i) 正规方程使条件数平方 $\kappa(A^TW^2A)=\kappa(WA)^2$——这正是第 4 步
截断必要的原因，也是 {ref}`phys14-fit` 剖面拟合改走 SVD 的原因；(ii) 步 3–5 等价于对 $\tilde N$
的**截断特征分解正则化**，与截断 SVD 属同一族 {cite}`hansen1998rank`；(iii) 等式约束的 Lagrange
消元与"两次求解再线性组合"的写法是约束最小二乘的教科书路线 {cite}`lawson1974solving,bjorck1996numerical`。
源码对 3–5 未给文献，只给 EFIT 开关名。

〔实测〕〔源码〕EAST #137985 上 `FY_CONDIN=1e7` 时 (3,4) 基给 $q_0$ 对参考 $+2.6\%$（缺省基
$-47.1\%$），"阈值在 $3\times10^7$ 与 $10^7$ 之间"，代价 $\Delta R$ $-6.4\to-17.3$ mm。

(phys03-outer)=
# 外层迭代 (The Outer Iteration)

〔源码〕`solve_inverse_coils`（`solve_inverse` 是 `coil=None` 的封装）每轮：

1. **磁轴**：真空室内（有等离子体后限于上轮电流支撑 ±2 格膨胀）$s\psi$ 极大节点 + 亚网格牛顿
   修正（{eq}`eq-p02-axis`）。
2. **边界**：`limiter_psi`（无视线检验）→ `find_xpoint`（接受条件同 {ref}`phys02-free-boundary`）；
   瓶颈规则自 `ramp0 = warmup + 60` 起以 $w=\min((it-\text{ramp0})/150,1)$ 混入，改判阈 $x_{\rm match}=10^{-3}$。
   可选 span 变率限制 `FY_SPAN_STEP`（缺省关；0.30 → 0.80 → 关的历史逐字记录）。span 为零 → `-5`。
3. **掩膜**：自磁轴四连通泛洪，$s\psi>s\psi_b$，真空室内。
4. **热身**（`it < warmup`，Python 缺省 40）：$I_p$ 归一的解析族
   `AnalyticProfile {beta0: 0.55, emp: 1.0, enp: 1.0, r0: (R_0+R_{n_r-1})/2}`
   （"与 EFIT 公开电流初始化阶段同一角色"）；总电流为零 → `-6`。
5. **内层拟合**（{ref}`phys03-rows`–{ref}`phys03-lstsq`）；失败 → `Err(-(100000 + it*100 + min(cells,99)))`
   （"尾两位 00 表示空掩膜"）。可选掩膜下限 `FY_MASK_FLOOR`（缺省关，耐心 8 轮）。
6. **系数松弛**：首轮全步，其后 $c\leftarrow c+0.3(c_{\rm new}-c)$；线圈修正自零起 $\Delta I\leftarrow\Delta I+0.3(\Delta I_{\rm new}-\Delta I)$。
7. **电流**：掩膜上的拟合剖面 + 规定电流 $j_{\rm pre}$；交接混合 $u=\mathrm{clamp}((it-\text{warmup})/50,0,1)$
   在解析电流与拟合电流之间。
8. **垂直反馈** $a_{fb}=-G\abs{I_p}(z_c-z_{\rm ref})$（仅 P；反演不含 D 项）；径向力只在 `FY_ANCHOR_W=0`
   时启用。`border_and_solve`：Green 边界 + 右端 $-2\pi\mu_0R\,I_{\rm cell}/\Delta A$ + 直接解。
9. **场松弛** $\psi\leftarrow\psi+\omega(\text{target}-\psi)$；残差同 {eq}`eq-p02-relax`；≤ tol 收敛
   （`zc_anchor` 为 NaN 或 `FY_ZC_TRIM` 时作下垂修正；平台期每 40 轮亦修）。

启动：真空室质心处半径 $0.15\min(L_R,L_Z)$ 的均匀电流盘（归一到 $I_p$）；空 → `-6`；限制器
不含节点 → `-7`。输入检查：`-8` 线圈块长度 / `meas_sigma` 不合；`-9` FSA 三元组参差。
结果：`psi, coefs, psi_axis, psi_bnd, axis_r, axis_z, ip, iterations, residual, bnd_kind, fb_amp, fb_amp_r, coil_delta, coil_pull = max|ΔI_c|/σ_c, fsa_rows_used, trunc_keep`。
Python 缺省：`npp=1, nff=2, relax=0.3, max_iter=800, tol=1e-9, fb_gain=8.0, warmup=40`。

〔真空室涡流〕〔源码 / Python〕可选把 $n_{\rm ves}$（EAST 40）段真空室电流作为零均值通道
一并拟合（先验 `vessel_sigma`，`meas_sigma = median(PSIBIT)`），可截到极向谐波
$1,\cos m\theta,\sin m\theta$（`vessel_modes`）；文档化的**否定结果**："剩余残差不是缺失的被动电流"。
用户指南保真度章的实测：只有磁通环时真空室涡流的可辨识份额为 5.6 %；加 79 个探针后升到
19.8 %，此时孪生注入的 12 kA 内壳电流被还原到 12.44 kA。

(phys03-post)=
# 后处理闭式 (Post-Processing Closed Forms)

〔源码〕由拟合系数得剖面（`surfaces.rs`、`recon_rs.fit_profiles`）：

$$
A(x)=\sum_kc^F_k\left[\frac{1-x^{k+1}}{k+1}-\frac{1-x^{n_{ff}+1}}{n_{ff}+1}\right],\qquad
F(x)=\sqrt{\max\big(F_{\rm edge}^2+2\,\text{span}_{pr}A(x),\,0\big)},\qquad F_{\rm edge}=\abs{R_0B_0}
$$ (eq-p03-F)

$$
p(x)=-\text{span}_{pr}\sum_kc^p_k\,[I_k(x)-I_{\rm top}(x)],\qquad \text{span}_{pr}=\frac{\psi_{\rm axis}-\psi_{\rm bnd}}{2\pi}
$$ (eq-p03-p)

〔已确立〕{eq}`eq-p03-F` 即 $\dv{}{\psi}\big(\tfrac12F^2\big)=FF'$ 自边界向内积分；$R_0$ 取装置
`RCENTR`（EAST 1.75 m；源码记录旧字面量 1.85 m 给 $q$ 带来 5.7 % 误差）。

(phys03-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **内部剖面不可定量使用（纯磁拟合）**：$q(0)$ 与 $q_{95}$ 的可信度差得很远且与噪声无关
   （用户指南保真度章："基的表达力，不是噪声"）；须加压强或 FSA 行（{ref}`phys03-rows-pressure`、
   {ref}`phys03-rows-fsa`）。
2. **线圈电流逐道不可辨识**：一圈磁通环只看到外部线圈的几个低阶多极矩；拟合只对**真空场**负责。
   源码测试因此在**场空间**断言而非逐道。
3. **两个 σ**：`meas_sigma` 与 $\sigma_c$ 必须同时给出（{ref}`phys03-rows-mag`）。
4. **结果不是 σ 的光滑函数**：边缘时片的 Picard 迭代是混沌的，$10^{-16}$ 的输入差可把解送到
   另一处（保真度章实测 5–9/9 片跳变）。判据须按此设计（"钉在 7，因为判据就是 7"）。
5. **正规方程的条件数**已被列均衡与截断处理，但 `CONDIN` 是**实验选定**的；不同装置须重定。
6. **反演是外层 Picard**，与正解同样可不收敛；`residual`、`iterations`、`trunc_keep`、`coil_pull` 都
   须读。
7. 只拟 $p'$、$FF'$ 的**多项式**；样条基、MSE 行、抗磁环行不在本模块内。

(phys03-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 反演模块的验证锚点（$33^2$ "线圈孪生"：16 环、4 线圈；内核单元测试）。
:name: tbl-p03-verify
:align: left

| 锚点 | 判据 |
| :--- | :--- |
| 等式约束精确 | $c_0+c_1=5$ 到 $10^{-12}$ |
| 零权重行不影响拟合 | 测试 `zero_weight_rows_do_not_influence_the_fit` |
| $I_p$ 等式忽略线圈列仍成立 | 测试 `the_ip_equality_ignores_the_coil_columns_and_still_holds` |
| 保持线圈 ⇒ 与旧入口逐位相同 | 测试 `held_coils_reproduce_the_plain_solve_bit_for_bit` |
| 6 % 线圈误差被线圈而非等离子体吸收 | 失配 $<0.25\times$，真空场误差 $<0.6\times$（场空间） |
| `meas_sigma` 决定线圈可动范围 | 测试 `meas_sigma_decides_how_far_the_coils_may_move` |
| 压强行 = 物理符号的 $p'$ 积分 | 对 200 000 段梯形 $10^{-6}$ 相对，模型压强 $>0$ |
| FSA 行是它声称的测度 | 测试 `fsa_current_row_is_the_measure_it_claims` |
| 形状行在其形状上为零 | 尺度 1 与 1000 |
| FSA 目标把拟合拉向自身 | 差距 $<0.25\times$，$I_p$ 在自由拟合自身 $\sim4\times10^{-5}$ 误差内 |
| 描不出的磁面被丢弃并计数；参差三元组被拒 | `-9` |
:::

(phys03-asbuilt)=
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 反演内容与内核函数、C-ABI、Python 入口的对应（2026-09-02 快照）。
:name: tbl-p03-asbuilt
:align: left

| 本章内容 | 内核函数（`inverse.rs`） | C-ABI（`fylite_rs_*`） | Python |
| :--- | :--- | :--- | :--- |
| 磁行 + $I_p$ 等式的反演 | `solve_inverse` | `gs_inverse_solve`（out12） | `fylite.kernel.gs_inverse_solve`；`S.analysis.reconstruction` |
| + FSA 电流行 | `solve_inverse_coils`（FSA 三元组） | `gs_inverse_solve_fsa`（out12[8] = `fsa_rows_used`） | `recon_rs.reconstruct(fsa=…)` |
| + 线圈作为带 σ 的观测量 | `solve_inverse_coils`（`CoilObs`） | `gs_inverse_solve_coils`（out12[8] = `coil_pull`，`coil_out = i0 + ΔI`；`-8`） | `recon_rs.reconstruct(coil_sigma=…)` |
| 约束最小二乘 | `constrained_lstsq(_h)` | —（内部） | — |
| 压强行 / FSA 行 | `pressure_row`, `fsa_current_row` | —（内部） | `S.analysis.profit` 供压强点 |
| 后处理 $F$、$p$ | `surfaces.rs`（闭式） | — | `recon_rs.fit_profiles` |
| 自洽外环（自举回灌） | — | `gs_inverse_solve` 的 `j_pre` | `scenario.analysis.loop`（{ref}`phys07-intro`） |
:::

(phys03-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献〕重构结构（外 Picard / 内线性最小二乘 / $I_p$ 等式）与解析电流族 {cite}`lao1985efit`；
DIII-D 重构综述与动理学约束 {cite}`lao2005efit,lao1990equilibrium`；磁测量的信息极限
{cite}`shafranov1971determination`；截断谱正则化 {cite}`hansen1998rank`；约束最小二乘
{cite}`lawson1974solving,bjorck1996numerical`；缩放预处理 {cite}`golub2013matrix`；磁诊断原理
{cite}`hutchinson2002principles`。标 〔凭记忆〕 者字段待核验（见参考文献 `note`）。

〔转引〕EFIT 的公开开关名（`CONDIN`、`KPPCUR/KFFCUR`、`PCURBD/FCURBD`、`KZEROJ/SIZEROJ/VZEROJ/RZEROJ/FWTXXJ`、
`PSIBIT`、`FWTSI/FWTMP2`）按 Lao 等的公开文献与 EFIT 用户文档口径引用，**不**引用其源码；本模块
的作者未读该源码（清洁室声明）。与 LIUQE {cite}`moret2015liuqe`、NICE {cite}`faugeras2020nice`
的范式比较见 `GK-TMT-02` / `GK-TMT-05`（跨仓）。

〔本仓选择（源码未注出处）〕边缘零化约化基 $x^k-x^n$ 的写法；列均衡 + 截断特征分解 +
$3\times/\div3$ 滞回；`CONDIN = 10^8`；FSA 行作为形状（去均值）施加；径向锚作为最小二乘行而垂直锚
作为力；热身解析族 $(\beta_0,e_{mp},e_{np})=(0.55,1,1)$ 与 40 轮 / 50 轮交接；系数松弛 0.3。
其证据是 {numref}`tbl-p03-verify` 与用户指南保真度章的实测，不是文献。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
