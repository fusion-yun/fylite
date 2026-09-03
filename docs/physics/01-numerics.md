---
title: 数值底座 (The Numerical Substrate)
subtitle: 椭圆积分与丝核、插值与差分、稠密线性代数（无 LAPACK）
---

(phys01-intro)=
# 引言：为什么内核自带数值底座 (Introduction)

〔范围〕本章详述不含托卡马克物理、而为其余各层所共用的数值底座：完全椭圆积分、
同轴圆丝互感、单元剖分、插值 / 重采样 / 差分，以及一整套自带的稠密线性代数——复 LU、对称
Jacobi 特征分解、Hessenberg–QR 非对称特征分解、单边 Jacobi SVD、截断 SVD 解、投影
Barzilai–Borwein 带界最小二乘、岭回归、Cholesky。**不依赖 LAPACK**：这是一条设计裁定，
代价与理由见下文。

〔为什么不链接库〕〔实现〕线性代数层头部给出理由：设计约束 FYL-DESIGN-01 §3.1 排除链接
LAPACK，因为同一份核心要编译到 WebAssembly；数值底座层则要求"wasm-clean，无依赖"。
其后果是本章的每个算法都在实现里**写出**，也因此每个算法都可以在本章被逐条核对。

〔位同一性契约〕〔实现〕数值底座层声明：其中每个函数必须**逐位**再现 Python 参考实现
`circuits.py`——相同运算次序、相同常数、相同钳制语义，表达式"逐行镜像 numpy 实现
（左结合、无 FMA、不作代数化简）"。这解释了本章多处看似多余的写法（例如
`a + f*(b - a)` 而非 `a*(1-f) + b*f`，$a_2=90^\circ$ 时保留 $\cos a_2=6.1\times10^{-17}$ 而不取
精确零）：它们是**契约**，不是疏忽。

〔评价口径〕本章所述算法的**物理正确性**由使用它们的模块负责（{ref}`phys02-intro`、
{ref}`phys12-intro` 等）；本章只回答"算法是什么、精度界在哪、失效条件是什么"。

(phys01-ellip)=
# 完全椭圆积分：算术—几何平均 (Complete Elliptic Integrals by the AGM)

〔定义〕〔已确立〕以参数 $m=k^2$ 记第一、二类完全椭圆积分
$K(m)=\int_0^{\pi/2}(1-m\sin^2\theta)^{-1/2}\dd\theta$、$E(m)=\int_0^{\pi/2}(1-m\sin^2\theta)^{1/2}\dd\theta$。

〔算法〕〔实现〕`ellipke_scalar(m)` 以算术—几何平均（AGM）递推：

$$
a_0=1,\quad b_0=\sqrt{1-m},\qquad
c_{n+1}=\tfrac12(a_n-b_n),\quad a_{n+1}=\tfrac12(a_n+b_n),\quad b_{n+1}=\sqrt{a_nb_n}
$$ (eq-p01-agm)

$$
K(m)=\frac{\pi}{2a_N},\qquad
E(m)=K(m)\left[1-\Big(\frac{m}{2}+\sum_{n\ge1}2^{n-1}c_n^2\Big)\right]
$$ (eq-p01-ke)

（$n=0$ 项 $2^{-1}c_0^2=m/2$ 由 $c_0=\sqrt m$ 给出）。终止条件 $\abs{c_{n+1}}<10^{-14}$
或 60 轮。〔实现〕收敛判据**逐元素**而非逐数组；注释论证其位安全性：在 $\abs{c}<10^{-14}$ 后
再走一轮，更新量 $\sim c^2/8\sim10^{-29}$，远低于 $K\sim1$ 的一个 ulp。

〔出处〕〔已确立〕AGM 求 $K$、$E$ 是 Gauss 的方法，标准表述见 Abramowitz–Stegun 手册 §17.6
{cite}`abramowitz1964handbook`〔凭记忆：节号未核验〕。实现本身未注出处，仅在测试中以
"Abramowitz & Stegun" 给出 $K(1/2)$ 的参考值。

〔适用域〕〔实现〕调用方保证 $m\in[0,1)$（Python 层保留 numpy 的定义域检查）；NaN 按 numpy 语义
传播。$m\to1$ 时 $K$ 对数发散，递推仍收敛但相对精度随 $1-m$ 下降；`mutual_scalar` 因此把
$m$ 钳制到 $1-10^{-15}$（下节）。

(phys01-filament)=
# 同轴圆丝的互感与单元剖分 (Coaxial-Filament Mutual Inductance and Element Subdivision)

(phys01-filament-mutual)=
## 互感公式 (The Mutual-Inductance Formula)

〔实现〕`mutual_scalar(r_1,z_1,r_2,z_2)`：

$$
d^2=(r_1+r_2)^2+(z_1-z_2)^2,\qquad m=k^2=\frac{4r_1r_2}{d^2},\qquad
M=\mu_0\sqrt{r_1r_2}\left[\left(\frac{2}{k}-k\right)K(m)-\frac{2}{k}E(m)\right]
$$ (eq-p01-mutual)

单位 H；$\mu_0=4\pi\times10^{-7}$ 精确（实现：按 `circuits.py` 的 `4e-7 * np.pi` 写，
即 2019 年 SI 重定义前的精确值而非 CODATA-2018 值——两者相差 $\sim5\times10^{-10}$ 相对，
选择前者是为了与被比对的 Fortran 路径位同一）。

〔出处〕〔已确立〕{eq}`eq-p01-mutual` 是 Maxwell 给出的两同轴圆环互感的椭圆积分形式
（Treatise, vol. 2, Art. 701）{cite}`maxwell1873treatise`〔凭记忆：条目号未核验〕，工程形式见
Grover {cite}`grover1946inductance`。实现未注出处。

〔假设〕轴对称；**零截面理想丝**。有限截面导体以丝云平均近似（{ref}`phys01-filament-element`）。

〔守卫〕〔实现〕$m$ 钳制到 $[0,\,1-10^{-15}]$（NaN 原样透过）；**重合丝**（$m=1$，$M$ 对数发散）
由调用方负责。向量化变体：`mutual_elementwise`、`mutual_outer`（$\text{out}[i,j]=M(a_i,b_j)$）、
`mutual_outer_serial`；多线程走每次调用即建即拆的 rayon 池（实现理由：与一条按解 fork
子进程的 Fortran 路径保持 fork 安全）。

(phys01-filament-self)=
## 薄丝自感项 (The Thin-Filament Self Term)

〔实现〕单元自感（详见 {ref}`phys12-em`）在单元自身丝云的互感矩阵
对角线上以薄丝自感替换奇异项：

$$
a_{\rm sub}=\sqrt{\frac{(w/n_u)(h/n_v)}{\pi}},\qquad
L_{ii}=\mu_0r_i\left[\ln\frac{8r_i}{a_{\rm sub}}-1.75\right]
$$ (eq-p01-self)

即把每根子丝视为**等面积圆截面、电流均匀**的细环。〔已确立〕$\ln(8R/a)-7/4$ 是均匀电流
密度圆截面细环的自感（低频极限），Grover 手册给出 {cite}`grover1946inductance`〔凭记忆〕；
实现未注出处（仅"thin-filament self term"）。

(phys01-filament-element)=
## 平行四边形单元的丝剖分 (Subdividing a Parallelogram Element)

〔实现〕`element_filaments(r_0,z_0,w,h,a,a_2,n_u,n_v)` 把一个 EFIT/efund 型平行四边形单元
（中心 $(r_0,z_0)$，水平边 $w$，与水平成角 $a_2$ 的边长 $h$，整体转角 $a$，角度以度计）
剖成 $n_u\times n_v$ 根**等权**子丝：

$$
u_i=\Big(\frac{i+\tfrac12}{n_u}-\tfrac12\Big)w,\quad v_j=\Big(\frac{j+\tfrac12}{n_v}-\tfrac12\Big)h,\qquad
r=r_0+u_i+v_j\cos a_2,\quad z=z_0+v_j\sin a_2
$$ (eq-p01-subdiv)

再绕 $(r_0,z_0)$ 旋转 $a$（若 $a\ne0$）。输出按 $u$ 主序（numpy `meshgrid(indexing="ij")` 的
展平序）。〔模型〕等权丝云 ⇔ 单元内**均匀电流密度**。这是有限截面导体 Green 函数的
最简单积分法则（中点法则的二维张量积）；丝数越多越精确，收敛速率由 {ref}`phys12-em`
的两算路检验实测给出（$n_u=n_v=8$ 时相对残差 $7.7\times10^{-5}$）。实现未注出处。

(phys01-interp)=
# 插值、重采样与差分 (Interpolation, Resampling and Differentiation)

〔实现〕本组函数全部按 numpy 语义写成 {cite}`harris2020array`，差别只在端点处理：

:::{table} 数值底座层的一维数值原语及其端点语义。
:name: tbl-p01-interp
:align: left

| 函数 | 内容 | 端点 | 拒绝（返回 `None` / NaN） |
| :--- | :--- | :--- | :--- |
| `interp_linear(x, xp, yp)` | 分段线性，二分查找，`slope*(x - xp[j]) + yp[j]` | **钳制**到 $[x_{p,0},x_{p,-1}]$ | `xp` 空或长度不合；$n=1$ 取常数 |
| `resample_uniform(src, n)` | $t=\frac{i}{n-1}(m-1)$，$k=\min(\lfloor t\rfloor,m-2)$，$s_k+(t-k)(s_{k+1}-s_k)$ | — | — |
| `to_uniform_extrap(x, y, n)` | 采样到均匀 $[0,1]$ | **两端线性外推** | `x.len() < 2`、长度不合、$n=0$ |
| `fill_gaps(v, monotone, default)` | 非有限项按**索引**线性插值填补 | 钳制；可选运行最大值（单调化） | 全 NaN 时取 `default` 或 `None` |
| `gradient(y, x)` | numpy 非均匀网格二阶内点公式（下式） | 一阶单侧 | $n<2$ 或长度不合 → NaN 向量 |
| `log_gradient(y, x, floor)` | $-\dd\ln y/\dd x$ | 同上 | `floor=None` 时 $y\le0$ → NaN |
:::

〔为什么外推〕〔实现〕`to_uniform_extrap` 保留两端外推的理由：$q$ 只在 $\approx[0.06,0.995]$
上描迹，若钳制则"在剪切最大的地方给出零剪切"。

〔差分公式〕〔实现〕以 $h_s=x_i-x_{i-1}$、$h_d=x_{i+1}-x_i$，

$$
g_i=\frac{h_s^2\,y_{i+1}+(h_d^2-h_s^2)\,y_i-h_d^2\,y_{i-1}}{h_sh_d(h_s+h_d)}
$$ (eq-p01-gradient)

〔已确立〕这是非均匀三点模板的二阶一次导数公式，可由 Fornberg 的通用权重算法得到
{cite}`fornberg1988generation`〔凭记忆〕；numpy 的 `gradient` 文档以此为据。

〔成对求和〕〔实现〕`pairwise_sum` 精确复制 numpy 的成对求和（8 路展开到 128 项，再递归对半），
目的是 L2 块均值的位同一。〔已确立〕成对求和的误差界 $O(\varepsilon\log n)$ 见 Higham
{cite}`higham1993accuracy`〔凭记忆〕。

(phys01-linalg)=
# 稠密线性代数 (Dense Linear Algebra)

〔组织〕〔实现〕线性代数层以 LAPACK 例程名标注每个函数的"角色"（`zgesv`、`zgeev`、`zgebal`、
`zgehrd`、`zunghr`、`dgesv`、`dlahqr`）{cite}`anderson1999lapack`，但不是这些例程的移植——
算法是教科书算法的独立写法。{numref}`tbl-p01-linalg` 逐条列出。

:::{table} 线性代数层的算法、守卫与出处（"角色"指实现所注的 LAPACK 对应例程）。
:name: tbl-p01-linalg
:align: left

| 函数（角色） | 算法（如实现） | 守卫 / 容差 | 出处 |
| :--- | :--- | :--- | :--- |
| `C64` | 复数类型；除法按 Smith 缩放避免溢出；主值平方根 | — | Smith 算法 {cite}`smith1962complex`〔凭记忆〕；实现未注 |
| `lu_solve`（`zgesv`） | 复 LU、部分选主元、原位、多右端 | 主元恰为 0 → `Err(k)` | 教科书 {cite}`golub2013matrix` |
| `symmetric_eigen` | 循环 Jacobi：$\theta=\frac{a_{qq}-a_{pp}}{2a_{pq}}$，$t=\mathrm{sgn}\,\theta/(\abs\theta+\sqrt{\theta^2+1})$ | ≤100 遍；非对角平方和 $<10^{-30}$ 止；跳过 $\abs{a_{pq}}<10^{-300}$ | Jacobi {cite}`jacobi1846verfahren`〔凭记忆〕；{cite}`golub2013matrix` §8.5 |
| `balance`（`zgebal`） | 以 2 的幂作行列缩放，直至 $(c+r)\ge0.95(c_0+r_0)$ | — | Parlett–Reinsch {cite}`parlett1969balancing`〔凭记忆〕 |
| `hessenberg`（`zgehrd`+`zunghr`） | Householder 约化并累积 $Q$ | 跳过零列 | Householder {cite}`householder1958unitary`〔凭记忆〕 |
| `eigen`（`zgeev`） | balance → Hessenberg → 单位移 QR（尾部 $2\times2$ 的 Wilkinson 位移；每 10 块迭代一次例外位移 $\mu=a_{22}+\abs{h_{hi-1,hi-2}}$；Givens 隐式步）；紧缩判据 (i) $\abs{h_{lo,lo-1}}\le\max(\varepsilon\,\text{tst},\text{tiny})$，(ii) Ahues–Tisseur，(iii) ≥30 块迭代后停滞逃逸 $\abs h\le\varepsilon\norm{H}_{\max}(k/30)$；特征向量由 Schur 形回代、$Q$ 旋转、反平衡、单位 2-范数 | `max_iters = 240n + 2400`（历史：$60n$ → $100n$ 失败 → $240n$；实现注 LAPACK `dlahqr` 按**每个特征值** 30 次预算）；超限 `Err(-1)` | QR 算法 {cite}`francis1961qr`〔凭记忆〕，Wilkinson 位移 {cite}`wilkinson1965algebraic`，Ahues–Tisseur 判据 {cite}`ahues1997deflation`〔凭记忆〕 |
| `bounded_lstsq` | 正规方程 $A^TA$ 上的投影梯度，Barzilai–Borwein 步长 $\alpha=\Delta x\cdot\Delta x/\Delta x\cdot\Delta g$；非单调保护：窗口 10，步长对半（≤40 次）直至 $f\le10^3f_{\max}$（$f_{\max}<0$ 时 $10^{-3}f_{\max}$）；回退 Cauchy 步 $1/\norm{A^TA}_\infty$ | 投影梯度范数 ≤ `tol`·初值或步长为零时止 | BB 步长 {cite}`barzilai1988two`；非单调线搜索 {cite}`grippo1986nonmonotone`〔凭记忆〕；投影 BB（SPG）{cite}`birgin2000nonmonotone`〔凭记忆〕。实现只写 "Barzilai-Borwein" |
| `svd` | **单边 Jacobi**（Hestenes 型）：仅当 $\abs\gamma/\sqrt{\alpha\beta}>\varepsilon$ 才旋转；奇异值 = 列范数，降序；返回 $(U_{m\times n},s,V^T)$ | ≤60 遍；$m<n$、$n=0$ 或形状不合 → `None` | Hestenes {cite}`hestenes1958inversion`〔凭记忆〕；实现注"单边 Jacobi 而非 Golub–Reinsch" |
| `svd_solve` | 截断 SVD $x=VS^{-1}U^Tb$，保留 $s>\text{rcond}\cdot s_0$ 或恰 `n_singular` 个（钳到 $[1,n]$）；返回保留数、条件数 $s_0/s_{\rm kept-1}$ 与 $s$ | $s_0=0$ 或 `b.len() != m` → `None` | TSVD {cite}`hansen1998rank` |
| `lu_solve_real`（`dgesv`） | 实 LU、部分选主元、置换向量 | 零主元 → `None` | {cite}`golub2013matrix` |
| `chol_solve`、`cholesky_solve` | Cholesky $A=LL^T$ 前代回代 | 主元 $d\le0$ 或非有限 → `None` | {cite}`golub2013matrix` |
| `ridge_lstsq` | $\min\norm{W(Ax-b)}^2+\sum_k\lambda_k^2x_k^2$，正规方程 $+\mathrm{diag}(\lambda_k^2)$，Cholesky | 继承 `chol_solve` 的拒绝 | Tikhonov 正则化 {cite}`tikhonov1963solution`〔凭记忆〕；实现未提 Tikhonov 之名 |
:::

〔两点评注〕

- **正规方程的条件数**：〔已确立〕$\kappa(A^TA)=\kappa(A)^2$，故 `ridge_lstsq` 与
  `bounded_lstsq` 走正规方程时把条件数平方了；这正是 {ref}`phys03-lstsq` 在反演中改用
  列均衡 + 截断特征分解、{ref}`phys14-fit` 在剖面拟合中用 SVD 的原因。凡调用这两个函数的
  地方，问题规模都小、且 $\lambda_k$ 或界约束本身起正则化作用。
- **单边 Jacobi 的精度**：〔已确立〕单边 Jacobi 对小奇异值的相对精度优于双对角化—QR
  （Golub–Reinsch）路线，代价是更多浮点运算；对本内核 $n\lesssim150$ 的问题规模是合适的取舍。

(phys01-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **$m\in[0,1)$**：椭圆积分的定义域由调用方守；`mutual_scalar` 钳到 $1-10^{-15}$，重合丝仍由
   调用方避免。
2. **理想丝**：{eq}`eq-p01-mutual` 在两丝距离与截面尺度可比处失去意义；有限截面靶用丝云
   （{eq}`eq-p01-subdiv`）加自感项（{eq}`eq-p01-self`），且**近场**（距单元中心 $2\max(w,h)$ 内）
   的响应依赖剖分细度——{ref}`phys12-em` 的两算路检验因此剔除近场后再比。
3. **端点语义各异**（{numref}`tbl-p01-interp`）：钳制、外推、NaN 三种，调用方须按表选择。
4. **特征分解的迭代预算**：`eigen` 超过 $240n+2400$ 次迭代返回 `Err(-1)`；实现记录了预算两次
   调大的历史，说明 TGLF 规模（$n\sim150$）的矩阵曾触顶。
5. **正规方程**：`ridge_lstsq`、`bounded_lstsq` 的条件数为 $\kappa(A)^2$，只宜小规模、有正则的
   问题。
6. **位同一性契约优先于代数简洁**：改写 数值底座层中任一表达式的结合次序都会破坏与参考
   实现的逐位一致，该契约由测试守住，不是风格问题。

(phys01-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 数值底座的验证锚点（内核单元测试）。
:name: tbl-p01-verify
:align: left

| 锚点 | 判据 |
| :--- | :--- |
| $K(0)=E(0)=\pi/2$ | $10^{-15}$ |
| $K(1/2)=1.854\,074\,677\,301\,372$（Abramowitz–Stegun） | $10^{-14}$ |
| 同轴环互感对称且为正 | 测试 `mutual_is_symmetric_and_positive_for_coaxial_loops` |
| 子丝云中心落在单元中心 | 测试 `filaments_center_on_the_element` |
| 插值对直线精确；钳制 vs 外推 | 数值底座层的插值测试组 |
| 植入奇异值 $7,\,2,\,0.25$ 复原 | $10^{-12}\times7$ |
| $U\Sigma V^T$ 重构与正交性 | $10^{-12}$ |
| 三角阵特征值 = 对角 | $10^{-9}$ |
| TGLF 规模（$n=8,60,150$）特征对残差 | $\norm{Av-\lambda v}<10^{-8}\norm{A}_F$ |
| 迹 = 特征值之和 | 测试 `trace_equals_the_eigenvalue_sum` |
| 无约束 BB 解满足正规方程 | KKT $10^{-10}$ |
| Cholesky 拒绝非正定 | 测试 `cholesky_refuses_a_non_spd_matrix` |
| 岭回归压制共线方向；零权重删行 | 测试 `ridge_damps_a_collinear_direction`、`zero_weight_removes_a_row` |
:::

(phys01-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 数值底座提供的能力与公开 Python 入口。本层不产生 fyo 面上的量，其余各层的量由它算出。
:name: tbl-p01-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 椭圆积分、丝互感、单元剖分 | —（几何与电磁各章的中间量，不单独出现在 fyo 面上） | `fylite.kernel.ellipke`、`mutual_filaments`、`element_filaments` |
| 插值 / 重采样 / 差分 / 填补 | —（径向标签换基时用，结果随各章的量走） | `fylite.kernel.interp`、`resample_uniform`、`to_uniform_extrap`、`gradient`、`fill_gaps` |
| 非对称特征分解 | —（湍流色散关系的求解器，{ref}`phys08-intro`） | —（内部） |
| 带界最小二乘 | —（脉冲设计与 $k_y$ 网格，{ref}`phys13-intro`） | `fylite.kernel.bounded_lstsq` |
| 岭回归 | —（解释性反演的正则化） | `fylite.kernel.ridge_lstsq` |
| SVD 与截断解 | —（剖面拟合，{ref}`phys14-intro`） | `fylite.kernel.svd`、`svd_solve` |
| 对称特征分解 | —（平衡反演内部，{ref}`phys03-lstsq`） | —（内部） |
:::

(phys01-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献〕AGM {cite}`abramowitz1964handbook`；同轴环互感 {cite}`maxwell1873treatise,grover1946inductance`；
数值线性代数教科书 {cite}`golub2013matrix`；Jacobi {cite}`jacobi1846verfahren`；QR 算法与位移
{cite}`francis1961qr,wilkinson1965algebraic`；平衡 {cite}`parlett1969balancing`；Householder
{cite}`householder1958unitary`；Ahues–Tisseur 紧缩 {cite}`ahues1997deflation`；单边 Jacobi SVD
{cite}`hestenes1958inversion`；截断 SVD {cite}`hansen1998rank`；BB 步长与非单调投影梯度
{cite}`barzilai1988two,grippo1986nonmonotone,birgin2000nonmonotone`；Tikhonov {cite}`tikhonov1963solution`；
非均匀差分权 {cite}`fornberg1988generation`；成对求和误差界 {cite}`higham1993accuracy`；复除法
{cite}`smith1962complex`；LAPACK 角色名 {cite}`anderson1999lapack`；numpy 语义 {cite}`harris2020array`。
上述条目中标 〔凭记忆〕 者为编者补出的对应；条目字段的核验状态见 `references.bib` 的 `note`
（{ref}`phys00-evidence`）。

〔实现未注出处〕数值底座层与 线性代数层对上述算法**一律未给文献**，只给算法名或 LAPACK
角色名；本章的归属是编者按算法内容所作的**文献对应**，不代表实现作者所依据的具体文本。

〔本仓选择〕逐元素 AGM 终止、$\mu_0$ 取 $4\pi\times10^{-7}$ 精确值、特征分解迭代预算
$240n+2400$、BB 非单调窗口 10 与爆炸阈 $10^3$、SVD 60 遍、Jacobi 100 遍——均为工程常数，证据
为 {numref}`tbl-p01-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
