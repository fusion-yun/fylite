---
title: 剖面拟合与合成诊断 (Profile Fitting and Synthetic Diagnostics)
subtitle: 移位 Legendre 基 + GCV 定阶、PCHIP、解析族提取；弦几何与线积分、Fourier–Bessel 层析、磁矩拟合、逐道自校准
---

(phys14-intro)=
# 引言：观测算子按数学结构分族 (Introduction)

〔范围〕本章详述互逆的两半——由测量拟合剖面，以及由剖面正演测量：加权最小二乘剖面拟合 + 广义交叉验证
定阶、单调三次插值 PCHIP、解析剖面族的 Levenberg–Marquardt 提取、g 文件剖面回读；以及三维直线弦、
$\psi_N$ 双线性采样、三种求积、包含判据、线积分与收敛细化、针孔相机角、单丝电流质心的磁矩拟合、
Bessel 函数与零点、Fourier–Bessel 层析基与响应行、反转半径、逐道自校准统计。磁类观测算子的 Green 响应行在 {ref}`phys12-em-response`、{ref}`phys03-rows-mag`。

〔按结构分族〕〔已确立〕合成诊断按**数学结构**而非仪器分三族：线性磁类（雅可比 = Green 响应阵，正反共用一核）、
弦积分类（干涉 / Faraday / SXR / 辐射热计）、局域采样类（`GK-TMT-09`，跨仓）。本内核实现了第一族（{ref}`phys12-em-response`）
与第二族的**几何与求积**部分；Faraday 旋转与干涉的**正向模型**（$\int n_e\dd l$、$\int n_eB_\parallel\dd l$ 经平衡）未实现
——POINT 的目标量由 EAST 侧的 est2 约化直接给出（{ref}`phys14-point`）。

〔出处姿态〕〔实现〕两个模块只引 Abramowitz–Stegun 9.2.5（Hankel 展开）与 "Fritsch-Carlson"、"SciPy"、"sxht7"（HT-7 软 X 层析
MATLAB 码）、"Levenberg–Marquardt"；其余公式无文献。本章补出处并标核验状态。

(phys14-fit)=
# 剖面拟合：移位 Legendre 基 + GCV (Profile Fitting)

〔基〕〔实现〕$u=1-x^2$、$t=2u-1\in[-1,1]$，Legendre 三项递推 $P_{k+1}=\frac{(2k+1)tP_k-kP_{k-1}}{k+1}$——"**基是 $u=1-x^2$ 中的移位 Legendre，
理由是一次实测的失败**：显然的基 $u^k$ 到五六阶列近共线，正规方程把条件数**平方**；与 SVD 最小二乘交叉检验两者差 $10^{-3}$——
不是舍入，是两个答案之一错了。Legendre 在同一区间均匀权下正交，同样的正规方程条件良好，两条路一致到 $6\times10^{-8}$。
$u=1-x^2$ 的物理论证不变：每个成员在轴上平坦，这是动理学剖面的行为。"〔已确立〕Legendre 多项式的 Bonnet 递推
{cite}`abramowitz1964handbook`；$\kappa(A^TA)=\kappa(A)^2$（{ref}`phys01-linalg`）。

〔加权最小二乘〕〔实现〕$A_{pq}=\sum_iw_i^2b_p(x_i)b_q(x_i)$、$r_p=\sum_iw_i^2b_p(x_i)y_i$、$Ac=r$（Cholesky；非正定 → `None`，
"关于矩阵的陈述，不是数值意外"）；$w_i=1/\sigma_i$，$\sigma_i\le0$ 的点**屏蔽**。

〔GCV 定阶〕〔实现〕对每阶 $n$（$p=n+1$ 参数、$N$ 个有效点）：

$$
V_{\rm GCV}(n)=\frac{\text{RSS}/N}{(1-p/N)^2},\qquad \chi^2/\text{dof}=\frac{\sum_iw_i^2d_i^2}{N-p}
$$ (eq-p14-gcv)

选 $\arg\min V$（并列取低阶）；"选出的阶是结果不是设置，整个扫描随之返回"。〔已确立〕广义交叉验证
{cite}`craven1979smoothing,golub1979gcv`（实现未注）；对线性投影 $\mathrm{tr}H=p$ 精确，"不带自身的调节常数"。
〔评注〕GCV 分子用**未加权** RSS 而 $\chi^2/\text{dof}$ 用加权残差——两个统计量用不同残差范数。**协方差传播未实现**
（无系数协方差、无置信带）。锚：精确低阶剖面到 $10^{-10}$、$10^{-12}$；LCG 噪声下选阶 $\le3$；基在 $u$ 上正交（Gram 对角 $1/(2i+1)$，$10^{-6}$）。

〔PCHIP〕〔实现〕"单调三次（PCHIP）插值——Fritsch–Carlson"：内点斜率为割线的加权调和平均
$d_i=(w_1+w_2)/(w_1/\delta_{i-1}+w_2/\delta_i)$，$w_1=2h_i+h_{i-1}$、$w_2=h_i+2h_{i-1}$，割线异号时 0；端点用 SciPy 的
`_edge_case` 三点形状保持公式并钳制；端段三次**外推**（"SciPy 的 `extrapolate=True`，调用方的风险，在此说明而非静默钳制"）。
〔出处〕Fritsch–Carlson 单调分段三次 {cite}`fritsch1980monotone`〔凭记忆〕；加权调和平均斜率是 Fritsch–Butland 的形式
{cite}`fritsch1984method`〔凭记忆〕；SciPy 实现 {cite}`virtanen2020scipy`。理由："拟合器存在是为了平滑的梯度，线性插值的导数是阶梯"。

〔解析族提取〕〔实现〕`shape_fit`：$f(x;a,b)=[\max(1-x^a,0)]^b$ 对归一剖面作 Levenberg–Marquardt（$\lambda_0=10^{-3}$，
中心差分 $h=10^{-6}$，接受则 $\lambda\leftarrow\max(0.3\lambda,10^{-12})$，拒绝 $\times10$，$\le200$ 外 × 30 内）；`gfile_profile`：
$\text{ratio}=\mu_0R_{\rm centr}^2p'(0)/FF'(0)$、$\beta_0=1/(1+1/\text{ratio})$——"**幅值半边是恒等式不是标定**：
$\beta_{\rm eff}$ 等于 EFIT 的 BETAP0 到机器精度……早先'0.69 映到约 0.55'的读法是单点标定吸收了无关系统差，已废"；
形状在开区间 $0.01<x<0.98$ 拟合（"两端退化"）。〔出处〕LM {cite}`levenberg1944method,marquardt1963algorithm`〔凭记忆〕。

(phys14-chords)=
# 弦几何、包含判据与线积分 (Chords, Containment and Line Integrals)

〔实现〕"一个实现回答三个问题：视线去哪、每点看到什么 $\psi_N$、$\int f(\psi)\dd s$ 是多少。"
直线弦 $\vb P(s)=\vb o+\hat d\,s$，$R=\sqrt{x^2+y^2}$（"切向弦与其极向投影不同"）；$\psi_N$ 双线性（Z 先 R 后，格外 $+\infty$——
"NaN 会毒化求和，钳制会在壁上发明等离子体"）。

:::{important}
〔$\psi_N\le1$ 不是包含判据〕〔实现〕"全网格箱上的 $\psi$ 在等离子体外不单调——极向场线圈在那里造出结构——$\psi_N$ 在远离
约束区处回落到 1 以下。EAST 例上 LCFS 顶在 $z=0.47$ m，而 $z=1.35$ m 的水平弦仍找到 $\psi_N=0.07$ 的样本。"
包含 ⇔ $\psi$ 有限 ∧ $\psi\le\psi_{\max}$ ∧ 在 LCFS 多边形内（少于 3 顶点 = 无多边形，"是告诫不是缺省"）。
:::

〔求积〕〔实现〕`Rule`：Simpson（$O(h^4)$；奇数区间时末段补梯形——"丢末样本静默缩短弦，读作物理差"）、梯形、"中点"
（实为端点全权的 Riemann 和，"某些上游码用的 $\sum f\dd s$，保留以便比对"）。〔已确立〕Newton–Cotes 规则 {cite}`press2007nr`。
`line_integral` 以**采样剖面** $f(\psi_N)$ 线性插值（"回调不能过 ABI"），返回值、路径长、内部样本数、$\psi_{N,\min}$（"三个信任数"）；
`line_integral_converged`：样本数加倍直到 $\abs{I_n-I_{n/2}}/\max\le r_{\rm tol}$，**无 Richardson 外推**（"答案就是那个计数的定采样积分"），
不收敛报告而不隐藏（未在公开入口上导出）。针孔相机 $\theta_i=\arctan\frac{(n/2-i+\tfrac12)\text{pitch}}{f}+\theta_{\rm view}+\pi$
（"$+\pi$ 是公式的全部内容"；测试注归 sxht7 `xzdetect`，以 HT-7 四相机几何验证——**HT-7 几何非 EAST**）。

(phys14-tomo)=
# Fourier–Bessel 层析 (Fourier–Bessel Tomography)

〔基〕〔实现〕

$$
b_{0,l}=J_0(z_{0,l}\bar\psi),\qquad b^{c}_{m,l}=J_m(z_{m,l}\bar\psi)\cos m\theta,\qquad b^{s}_{m,l}=J_m(z_{m,l}\bar\psi)\sin m\theta,\qquad
\theta=\operatorname{atan2}(Z-Z_{\rm axis},R-R_{\rm axis})
$$ (eq-p14-fb)

$z_{m,l}$ 为 $J_m$ 的第 $l$ 个正零点 ⇒ 每个模在 $\psi_N=1$ **由构造为零**；角度**关于磁轴**（"关于几何中心量会旋转每个奇模"）。
"截断是正则子：低阶展开没有自由度拟合噪声——这是二十视线的弦层析能稳定的全部理由；提高 $(m_{\max},l_{\max})$ 直到残差好看是拟合噪声。"
缺省 $m_{\max}=1$、$l_{\max}=4$（12 列）。响应行 $G_{cj}=\Delta s\sum_{k\in\text{inside}}b_j(\psi_k,\theta_k)$（中点和；$\psi_N\le1$ 硬编码；
无一弦看见等离子体 → `None`；"矩阵随平衡改变须重建——它是图的性质不是诊断的"）。
〔出处〕〔已确立〕磁面基 + 极向谐波的 SXR 层析是 JET 等装置的经典做法 {cite}`granetz1988tomography`〔凭记忆〕；
Zernike / Cormack 型正交基 {cite}`cormack1964representation`〔凭记忆〕；实现只注 "sxht7"。

〔Bessel〕〔实现〕$\abs x<12$：80 项升幂级数；$\abs x\ge12$：Hankel 渐近展开（**实现引** Abramowitz–Stegun 9.2.5，$P$/$Q$ 级数
{cite}`abramowitz1964handbook`），项**缩小时取**（渐近展开的标准规则）；对 SciPy 在 $x\in[0.01,60]$、$m\le3$ 内 $3\times10^{-12}$；
实现记录只取首项在 $x=12$ 第三位即错、$J_2$ 零点偏 0.13。零点：均匀扫描 $[10^{-6},4+n\pi+m]$ + 80 次二分。

〔反演（宿主，已退役至 git）〕加权 TSVD：$G_w=G\,\mathrm{diag}(w)$，`svd_solve(rcond = 1e-3)`（{ref}`phys01-linalg`；"截断是正则化，
保留数随答案返回——欠定视线几何必须**可见**"）；模型分辩率矩阵 $R=V_KV_K^T$。〔已确立〕TSVD 正则化 {cite}`hansen1998rank`。
**无 Tikhonov / Phillips 平滑算子、无 L 曲线、无 GCV**——截断阶与 TSVD 是仅有的正则子。反转半径 = $m=1$ 幅值
$\sqrt{(\sum c_{2l}J_1)^2+(\sum c_{2l+1}J_1)^2}$ 的极大位置（单模锚 $j'_{1,1}/j_{1,1}=0.4805$；未在公开入口上导出）。

(phys14-moments)=
# 磁矩拟合：单丝电流质心 (Magnetic Moment Fit — Current Centroid)

$$
B^{\rm model}_i=I_p\big[B_R(R_i,Z_i;R_c,Z_c)\cos\alpha_i+B_Z(\cdot)\sin\alpha_i\big],\qquad C(R_c,Z_c)=\sum_i\big(w_i(B^{\rm model}_i-b_i)\big)^2
$$ (eq-p14-centroid)

〔实现〕一根携带实测 $I_p$ 的环向丝；$(B_R,B_Z)$ 由 `element_response` 的退化单元（{ref}`phys12-em-response`）；LM 同上（$\le100\times30$，
$R_c+\delta R\le0$ 拒绝——"机器外的质心不是慢收敛，是错分支"）。理由："磁通环约束等离子体**总量**与外侧延伸，但让垂直位置几乎自由——
实测未锚定的重构 Z 偏 45 mm 而轴 R 已好到 0.6 mm；从 EFIT a 文件读锚会让答案依赖被替换的码。"宿主先减去线圈自身场
（"密实电流柱从外看偶极项主导，丝位置就是电流质心——正是 `rcurrt`/`zcurrt`"）。〔已确立〕外部磁测量的低阶矩定位电流质心
{cite}`shafranov1971determination,hutchinson2002principles`；单丝偶极模型实现未注。锚：植入质心复原到 $10^{-6}$ m；1 % 噪声 5 mm 内。

(phys14-selfcal)=
# 逐道自校准统计 (Per-Channel Self-Calibration Statistics)

〔实现〕"这些是**稳健统计**，哪一个放在哪里是方法的全部……逐道因子是跨时片的**中位数**，因为少数坏片不得移动它；判断某道是否
突出的散布是最大值，因为那里少数**就是**信号——$\mathrm{MAD}([1,1,2,1])=0$。"$f_i=c_i/m_i$，$\tilde f=\text{median}$，
$\text{keep}_i\iff\abs{f_i/\tilde f-1}\le\text{tol}$（缺省 0.15；"中位数吸收任何全局尺度或单位偏移，只有道间相对不一致能拒绝一道"）；
跨片：`factor = median`、`scatter = MAD/|median|`（无 1.4826）；`factor_dispersion = max|f/median − 1|`（"刻意不是稳健散布"）。
无 $\chi^2$。宿主（已退役至 git）以 SVD 秩一分量取平衡成分。〔出处〕稳健统计的中位数 / MAD {cite}`huber1981robust`〔凭记忆〕；
实现只注 "sxht7"。前提："`computed` 须来自未用可疑道的拟合——否则拟合已吸收其增益误差，因子塌向 1。"
用户指南保真度章：EAST 逐道标定（`RWTMP2`）不可得是全探针拟合发散的根源。

(phys14-point)=
# POINT 偏振—干涉仪的约化与 Faraday 常数（宿主） (POINT Reduction — Host Side)

〔Python / 装置文档〕$\lambda=432.5$ µm、$C_F=2.62\times10^{-13}$（装置文档数据，实现禁止字面量）；Faraday 角 → $\int n_eB_{\rm pol}\dd l$
的目标量 $\texttt{bpolar}=k_{\rm pol}\theta_F[\text{rad}]/(2C_F\lambda^2\cdot10^{19})$——**因子 ½ 的来源未在实现说明**（"GUI line 424"）；
干涉仪目标 $\abs{n_{e,\rm line}}$（MDS 节点已给线密度，无相位常数）；条纹跳变门 0.15；$\sigma_{\rm nel}=0.3$、$\sigma_{\rm pol}=0.05$（GUI_v5）。
〔已确立〕冷等离子体 Faraday 旋转 $\theta_F=\frac{e^3}{2\varepsilon_0m_e^2c\omega^2}\int n_eB_\parallel\dd l=2.62\times10^{-13}\lambda^2\int n_eB_\parallel\dd l$
（SI，$\lambda$ 以 m）{cite}`hutchinson2002principles`——常数与文档值一致，故其量纲为 rad·m$^{-2}$·T$^{-1}$·m$^{-3}$ 的组合；
½ 因子〔推测〕与 EFIT `BPOLAR` 的定义约定有关，未查证。**正向模型未实现**（S8-FR-OP-2/3 缺口）。抗磁环：只读积分器电压，
标定常数不公开则不接入拟合；"`diamag = 1e-3*dflux`"（Fortran 引）；**无 $\beta_p$ 关系**。

(phys14-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **拟合基假定剖面在轴上平坦且偶**；GCV 只度量样本内（"外推段无约束"）；无协方差。
2. **PCHIP 端段外推**是调用方的风险。
3. **弦是直线**：无折射、无有限视角 / étendue、无时间依赖；$\psi_N\le1$ 不是包含判据。
4. **层析的正则子只有截断与 TSVD**；角关于磁轴；响应阵随平衡重建；HT-7 几何测试非 EAST。
5. **电流质心是偶极近似**；$I_p$ 误标与径向位移退化。
6. **自校准要求独立锚**；因子是仪器性质仅当跨片恒定。
7. **Faraday / 干涉正向模型缺**；POINT 目标量的 ½ 因子待查证；抗磁环无 $\beta_p$ 关系。
8. **探针为点传感器**（无长度平均——用户指南保真度章："ASIPP 参考表经验上表现为点核"）。

(phys14-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 拟合与诊断模块的锚点。
:name: tbl-p14-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 精确低阶剖面 | 闭式 | $10^{-10}$；选阶正确 |
| 基正交性 | Gram 对角 $1/(2i+1)$ | $10^{-6}$ |
| GCV 不追噪声 | LCG 噪声 | 选阶 $\le3$ |
| 解析族回读 | 植入 $(a,b)=(1.7,2.3)$ | 残差 $<10^{-6}$，$\beta_0$ 到 $10^{-15}$ |
| $J_m$ | SciPy，$x\in[0.01,60]$、$m\le3$ | $3\times10^{-12}$ |
| 反转半径单模 | $j'_{1,1}/j_{1,1}=0.4805$ | 0.006 |
| 收敛线积分 | 定采样积分 | 逐位相等；不收敛报告 |
| 包含判据 | $z=1.35$ m 弦 | 多边形拒绝、$\psi_N$ 单独接受 |
| 电流质心 | 植入 | $10^{-6}$ m；1 % 噪声 5 mm |
| 自校准 | 植入增益 $[1.4,0.6,-1.0]$ | 复原 $1/g$ 到 $10^{-8}$ 并拒绝 |
| 层析相位（宿主） | 相位 $(1-\psi)^2(1+\text{asym}\cos\theta)$ | 剖面相关 $>0.97$（实测 0.984） |
| SVD | LAPACK，60 个随机阵 | $3.0\times10^{-15}$ |
:::

(phys14-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 剖面拟合与合成诊断各项的产出，以及它们所落的 fyo 数据集。
:name: tbl-p14-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 加权最小二乘剖面拟合与定阶 | `fyo:core_profiles`：由测点拟合出的剖面 | `S.analysis.profit` |
| 单调三次插值 | —（重采样，随各章的量走） | `fylite.kernel.pchip` |
| 解析族提取 | `fyo:core_profiles`：解析形状参数 | —（内部） |
| 弦几何、采样、求积与线积分 | `fyo:magnetics` 式的合成弦测量（干涉 / 偏振） | `device.Chord`、`device.line_integral` |
| 层析反演 | —（已退役，见 git 历史） | — |
| 电流质心 | `fyo:equilibrium`：由磁测量给出的位置矩 | `S.analysis.moments` |
| 通道自校准 | `fyo:magnetics`：逐道标度因子 | —（已退役，见 git 历史） |
| POINT 弦约化 | `fyo:core_profiles`：线积分密度 | `io.est2.read_east_mds` |
:::

(phys14-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（实现引）〕Hankel 展开 {cite}`abramowitz1964handbook`；SciPy {cite}`virtanen2020scipy`。
〔编者对应〕GCV {cite}`craven1979smoothing,golub1979gcv`；PCHIP {cite}`fritsch1980monotone,fritsch1984method`；LM
{cite}`levenberg1944method,marquardt1963algorithm`；Fourier–Bessel 层析 {cite}`granetz1988tomography,cormack1964representation`；
TSVD {cite}`hansen1998rank`；磁测量矩与 Faraday 旋转 {cite}`shafranov1971determination,hutchinson2002principles`；稳健统计
{cite}`huber1981robust`；Newton–Cotes {cite}`press2007nr`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕sxht7（HT-7 软 X 层析 MATLAB 码：`sxarray.m`、`xzdetect`、`weight.m`）——方法与相机几何；EFIT / GUI_v5 的 `BPOLAR`、`SIGNEL`、
`SIGPOL`、a 文件 `rcurrt`/`zcurrt`；EAST 装置文档的 POINT 常数。

〔本仓选择〕$u=1-x^2$ Legendre 基、GCV 扫描全返回、`tol = 0.15`、TSVD `rcond = 1e-3`、Simpson 奇区间补丁、`+inf` 格外语义、
包含判据的多边形要求、$m_{\max}=1$/$l_{\max}=4$、80 项级数 / 12 切换点、LM 调度。证据为 {numref}`tbl-p14-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
