---
title: 物理与数值 · 边界层、中性粒子与台基 (Physics & Numerics — Edge, Neutrals and Pedestal)
subtitle: edge.rs · edge_tables.rs · neutrals.rs · pedestal.rs —— 非日冕 Mavrin 拟合、扩展 Lengyel 两点模型（正 / 反解）、一维柱 Monte-Carlo 中性粒子、EPED1-NN 台基代理
---

(phys11-intro)=
# 引言：芯部结果可信度的上界 (Introduction)

〔范围〕本章详述四个模块：`edge.rs`（约 1230 行：Mavrin 2017 非日冕原子数据评估、Body 等 2025 **扩展 Lengyel 模型**
的闭式、两点态、反解与正解不动点）、`edge_tables.rs`（生成：Mavrin 系数）、`neutrals.rs`（约 380 行：一维柱几何
解析 Monte-Carlo 中性粒子输运）、`pedestal.rs` + `pedestal_tables.rs`（EPED1-NN 台基代理）。它们分别给芯部输运
（{ref}`phys05-intro`）供**边界温度**、**中性源**与**台基顶 Dirichlet 边界**。

〔出处姿态〕〔源码〕`edge.rs` 是 TORAX（google-deepmind/torax，Apache-2.0）扩展 Lengyel 实现的**转录**，其常数刻意取
TORAX 的值而非 CODATA-2018（"对齐这些把闭式从 $3\times10^{-7}$ 挪到 $10^{-16}$"）；`neutrals.rs` 是**清洁室**
（未读 EIRENE / FRANTIC 源码，方法为标准解析 MC + Woodcock 抽样，速率取公开拟合）；`pedestal.rs` 逐行转录
EPEDNN.jl（Apache-2.0）。源码逐字引的文献较完整（Mavrin、Body、Eich、Stangeby、Voronov、Freeman–Jones、Snyder、Meneghini）；
只给姓名的：Brown & Goldston 2021、Verdoolaege 2021、Kallenbach 2024。

〔未实现（明列）〕〔源码 grep〕Eich 2013 $\lambda_q$ 回归 #14/#15、Goldston 漂移 $\lambda_q$、展宽因子 $S$ 与靶板热流卷积、
显式脱靶判据、日冕冷却曲线用于边界、Janev 电离拟合、解析中性穿透长度、加料源形状、SOL 再循环模型、EPED 的
KBM 宽高关系**作为方程**、剥离—气球代理——均**不在**内核中。理论手册 `GK-TMT-07` 所述的这些结构在本内核只有
下文所列的子集。

(phys11-mavrin)=
# 非日冕原子数据：Mavrin 2017 (Non-Coronal Atomic Data)

〔源码〕八种低 Z 杂质（He, Li, Be, C, N, O, Ne, Ar）的平均电荷态 $\expval Z$ 与冷却率 $L_z$ 作为 $T_e$ **与**滞留参数
$n_e\tau$ 的函数：

$$
\log_{10}f=c_0+c_1X+c_2Y+c_3X^2+c_4XY+c_5Y^2+c_6X^3+c_7X^2Y+c_8XY^2+c_9Y^3,\qquad
X=\log_{10}T_e[\text{eV}],\ Y=\log_{10}\frac{\min(n_e\tau,10^{19})}{10^{19}}
$$ (eq-p11-mavrin)

十系数逐（物种，温度区间）；电荷态表以 **eV**、冷却率表以 **keV** 标区间（"两套单位约定，保留而不归一"）；
区间选择为 numpy `searchsorted` 缺省侧（边界**严格低于** $T$；源码记录 `>=` 版本在 896 点中错 119 点、最差 4.8×）。
三条钳制"是模型的一部分"：$T_e$ 钳入物种拟合域、$n_e\tau$ 在 $10^{19}$ m⁻³s 饱和（日冕极限）、不在表内的物种**辐射为零**
（"对边界重杂质的建模陈述"）。$L_{\rm INT}=\int L_z\sqrt T\,\dd T$ 在对数网格上梯形求积（分辨率**无缺省**；解算器用 100）。
〔出处〕Mavrin 2017 {cite}`mavrin2017noncoronal`（源码逐字引，含 DOI）；$L_{\rm INT}$ 为 Body 等 Eq. 34 {cite}`body2025lengyel`。
系数经 TORAX 记录冻结 {cite}`citrin2024torax`。TORAX oracle：$\expval Z$ $2.2\times10^{-14}$、$L_z$ $6.6\times10^{-14}$、
$L_{\rm INT}$ $6.7\times10^{-15}$（8 × 16 × 7 网格；记录文件本 checkout 缺）。

(phys11-lengyel)=
# 扩展 Lengyel 模型 (The Extended Lengyel Model)

(phys11-lengyel-closed)=
## 闭式：形状因子、$\alpha_t$、$\lambda_q$ 与 $q_\parallel$ (Closed Forms)

〔源码〕（Body 2025 方程号照源码标注）

$$
S=\sqrt{\tfrac12\big(1+\kappa^2(1+2\delta^2-1.2\delta^3)\big)}\ (\text{Eq. 56}),\qquad
\expval{B_{\rm pol}}=\frac{\mu_0I_p}{2\pi aS}\ (\text{Eq. 52}),\qquad
q_{\rm cyl}=\frac{B_0}{\expval{B_{\rm pol}}}\frac aRS
$$ (eq-p11-shape)

$$
\kappa_z=0.672+0.076\sqrt{Z_{\rm eff}}+0.252Z_{\rm eff},\qquad \kappa_e=\frac{2390}{\kappa_z}\ [\text{W m}^{-1}\text{eV}^{-3.5}]\quad(\text{Body Eq. 9 / Brown–Goldston Eq. 10})
$$ (eq-p11-kappae)

$$
\alpha_t=1.02\frac{\nu_{ei}}{c_s}\frac{m_e}{m_i}q_{\rm cyl}^2R\Big(1+\frac{\tau}{Z_i}\Big),\qquad
\nu_{ei}=\nu_{ee}Z_{\rm corr}Z_{\rm eff},\quad Z_{\rm corr}=0.431\,e^{-((Z_{\rm eff}-1+10^{-7})/3.25)^{0.85}}+0.569
$$ (eq-p11-alphat)

$$
\rho_{s,\rm pol}=\frac{\sqrt{T_em_i/e}}{\expval{B_{\rm pol}}},\qquad
\lambda_{q,\rm avg}=0.6(1+2.1\alpha_t^{1.7})\rho_{s,\rm pol},\qquad
q_\parallel=\frac{P_{\rm SOL}(1-e^{-1})f_{\rm div}}{2\pi(R+a)\lambda_{q,\rm omp}}\cdot\text{pitch}
$$ (eq-p11-qpar)

$\ln\Lambda=30.9-\tfrac12\ln n_e+\ln T_e$（"Verdoolaege 2021 的变体，与 Wesson 3rd ed. p. 727 差绝对 0.1——上游的选择"）；
$\nu_{ee}$ 以对数空间求值；$\lambda_{q,\rm omp}=\lambda_{q,\rm avg}/(r_B(R+a)/R)$，$r_B=4/3$、$f_{\rm div}=2/3$、$\tau=1$ 为上游缺省。
〔出处〕$\alpha_t$ 与 $\lambda_q$ 的湍流展宽标度 Eich 等 2020 Eq. 9 {cite}`eich2020turbulence`（源码逐字引）；$\kappa_e(Z_{\rm eff})$
{cite}`brown2021conductivity`〔凭记忆：题名待核验〕；`REGULARISER_EPS = 1e-7` 是上游 `CONSTANTS.eps`（"正则子，不是机器 ε"）。
$q_{\rm cyl}$、pitch、$(1-1/e)$ **源码未注出处**。TORAX oracle：36 点最差 $1.5\times10^{-15}$。

(phys11-lengyel-twopoint)=
## 两点态：沿磁力线的温度与靶板 (The Two-Point State)

〔源码〕对流层经验拟合（"Stangeby 2018 PPCF 60 044022 Eq. 33 的形状，系数上游拟合"）$f(T_t)=1-A(1-e^{-T_t/w})^s$，
三组 $(A,w,s)$：$f_{\rm mom}$ (0.8859, 3.826, 0.8282)、$f_n$ (0.5588, 2.020, 0.9600)、$f_{\rm pow,conv}$ (0.8532, 5.195, 0.9642)。

$$
T_{cc}=\frac{2f_nT_t}{1-f_{\rm mom}},\qquad
T_{\rm div}=\Big(T_{cc}^{7/2}+3.5f_{\rm cond}\frac{q_\parallel}{b}\frac{L_{\rm div}}{\kappa_e}\Big)^{2/7}\ (\text{Eq. 44}),\qquad
T_u=\Big(T_{\rm div}^{7/2}+3.5f_{\rm cond}q_\parallel\frac{L_\parallel-L_{\rm div}}{\kappa_e}\Big)^{2/7}\ (\text{Eq. 45})
$$ (eq-p11-tu)

〔已确立〕{eq}`eq-p11-tu` 是经典两点模型的平行热传导积分 $T_u^{7/2}=T_t^{7/2}+\frac{7q_\parallel L}{2\kappa_0}$
{cite}`stangeby2000boundary`（推导见 `GK-TMT-07`），此处 $\kappa_0\to\kappa_e(Z_{\rm eff})$、偏滤器腿以 $b=3$ 展宽、
分导热份额 $f_{\rm cond}=1$。压强 $p_u=(1+M_u^2)n_uT_ue(1+\tau_u/(n_e/n_i)_u)$；靶板关系（以对数空间写）

$$
T_t=\frac{8m_iq_\parallel^2}{\gamma^2p_u^2e}\cdot\frac{(1-f_{\rm pow})^2}{(1-f_{\rm mom})^2}\cdot\frac{1+\tau_t}{2(n_e/n_i)_t}\frac{(1+M_t^2)^2}{4M_t^2}f_{\rm exp}^{-2}
$$ (eq-p11-target)

〔已确立〕鞘层传输 $q_t=\gamma n_tT_tc_{s,t}$ 与压强守恒的合并即得 {cite}`stangeby2000boundary`；$\gamma=8$、$M_t=1$ 缺省。
源码在 `required_power_loss` 反解 $f_{\rm pow}$、在 `forward_t_e_target` 正算 $T_t$（**此处且仅此处** $f_{\rm mom}$、$f_{\rm pow,conv}$
上限 0.95——"无此上限完全脱靶解除零"）。$Z_{\rm eff}$ 在**两个温度**求值：分离面（供 $\alpha_t$）与偏滤器入口（供 $\kappa_e$；
"喂分离面的差 $1.7\times10^{-2}$"）。TORAX oracle：20 个态最差 $2.9\times10^{-16}$。

(phys11-lengyel-inverse)=
## 反解：给靶温求杂质浓度 (Inverse Solve)

〔源码〕"给鞘层入口目标温度，需要多少播种杂质——'要吹多少氮'"（Body §5，Eqs. 33, 40, 42）：

$$
k=2\kappa_en_u^2T_u^2\ (\text{Eq. 33}),\qquad
c_z=\frac{q_u^2+(1/b^2-1)q_{\rm div}^2-q_{cc}^2}{kL^s_{cc\to u}}-\frac{L^f_{cc\to u}}{L^s_{cc\to u}}\ (\text{Eq. 42})
$$ (eq-p11-cz)

$q_{\rm div}^2$ 按 Eq. 40；$L^{s,f}$ 为播种 / 固定杂质加权的 $L_{\rm INT}$。"四个量的不动点，更新**次序**是算法的一部分……
上游跑**固定** 25 遍而不测残差，故'收敛'意为'跑了规定遍数'"。初值 $\alpha_t=0.1$、$\kappa_e=1800$、$c_z=10^{-4}$、$T_u=200$ eV。
结果 `CzPrefactorNegative`（"不播种已低于目标温度"）时 $c_z:=0$ 但结果码保留。TORAX oracle：10 例最差 $3.3\times10^{-14}$；
25 遍与 100 遍到 $10^{-12}$ 一致。

(phys11-lengyel-forward)=
## 正解：给杂质求靶温 (Forward Solve)

〔源码〕"上游自注一组输入可容多解……此处不动点只找**一个**"；$q_\parallel$ **欠松弛 0.4**（$T_t$、$\alpha_t$ 的松弛因上游对象别名
而为空操作——"刻意再现"）；

$$
q_{cc}^2=\frac{q_u^2}{b^2}-k\Big(\frac{L^f_{\rm div\to u}}{b^2}+L^f_{cc\to\rm div}\Big)\ (\text{Eq. 38, 39}),\qquad
q_{cc}=\text{smooth\_sqrt}(q_{cc}^2/q_u^2,10^{-3})\,\abs{q_u}
$$ (eq-p11-qcc)

`smooth_sqrt(x,ε)` $=\sqrt x$（$x\ge\varepsilon$）或 $2\varepsilon^{3/2}/(3\varepsilon-x)$（"在 $\varepsilon$ 处值与斜率连续，负向按 $1/\abs x$ 衰减"；
上游可微——"钳制与平滑根在**答案**上不同：完全脱靶例此处 $2\times10^{-5}$–$4\times10^{-4}$ eV，钳制下恰为零"）。
$q_{cc}^2\le10^{-7}$ 即 `QccSquaredNegative`——**内核的脱靶标志**。TORAX oracle：10 例最差 $1.3\times10^{-13}$，4 例脱靶；
迭代研究：$n=3/10/25/50/100/200\to25.91/19.30/17.766/17.726/17.7263/17.7263$ eV（"上游的正解答案离其自身不动点 0.22 %"）。

(phys11-neutrals)=
# 一维柱 Monte-Carlo 中性粒子 (1-D Cylindrical Monte-Carlo Neutrals)

〔声明的约化〕〔源码〕无限圆柱 $a=r_{\rm edges}[-1]$（成形、偏滤器、极向源定位**不在**）；只有原子（分子经发射能量 `e0_ev`
进入，"Franck–Condon ≈ 3 eV"）；无复合源（101612 账：$\abs{\rm SDRC}\approx4\times10^{-4}$ SDII）；壁 `albedo` 再发射；一切计数
**每单位源**。

〔速率〕〔源码〕

$$
\expval{\sigma v}_{\rm ion}=0.291\times10^{-13}\frac{u^{0.39}e^{-u}}{0.232+u}\ [\text{m}^3/\text{s}],\ u=\frac{13.6}{T_e};\qquad
\sigma_{cx}=0.6937\times10^{-18}\frac{(1-0.155\log_{10}E)^2}{1+0.1112\times10^{-14}E^{3.3}}\ [\text{m}^2]
$$ (eq-p11-rates)

〔出处〕电子碰撞电离：Voronov 1997 氢行（$A=0.291\times10^{-7}$ cm³/s，$P=0$，$K=0.39$，$X=0.232$）{cite}`voronov1997fit`（源码逐字引）；
电荷交换：Freeman–Jones 拟合 {cite}`freeman1974atomic`（源码逐字引 CLM-R 137）。$T_e\le0.1$ eV 电离率取 0；$E$ 钳到 $[0.1,10^5]$ eV/amu。

〔算法〕〔源码〕解析 MC + **Woodcock δ 跟踪**：$\nu_{\max}=\max_j\nu_j$，飞行长 $s=-\ln u/\nu_{\max}\cdot v$，虚碰撞按 $u\nu_{\max}\ge\nu_j$；
密度估计量为事件估计（每次真 / 虚碰撞记 $w/\nu_{\max}$）；壁发射余弦分布；CX 伴随离子取局域 $T_i$ 的 Maxwellian（Box–Muller）；
RNG splitmix64；$\text{ionized}+\text{escaped}=1$ 精确。〔已确立〕δ 跟踪 {cite}`woodcock1965techniques`〔凭记忆〕；EIRENE 的方法类
{cite}`reiter2005eirene`〔凭记忆〕；Box–Muller {cite}`box1958note`〔凭记忆〕；splitmix64 {cite}`steele2014splittable`〔凭记忆〕。
守卫：单个历史 $>10^5$ 步 → panic；C-ABI `-2` 于 $n<2$、`n_particles = 0`、非严格增 `r_edges`。

〔EIRENE oracle（JINTRAC 101612）〕〔源码〕3 eV 发射**穿透不足**（10 % 电离深度 $x=0.96$ 对 EIRENE 0.78），434 eV 发射**穿透过头**（0.56）；
离子通道 CX 功率相对 EIRENE $-1.74$ MW 高 3.0×（冷）/ 1.8×（暖）；电子代价 13.6 eV/电离给 EIRENE 的 0.68（其有效 ≈ 20 eV 含辐射级联）。
这些差异**按带断言**（冷 2.2–4.2，暖 1.3–2.6，电子 0.5–0.9），是已量化的模型缺口。

(phys11-pedestal)=
# 台基：EPED1-NN 代理 (The Pedestal — EPED1-NN Surrogate)

〔模型〕〔源码〕EPED {cite}`snyder2009development,snyder2009pedestal,snyder2011eped` 由两个约束（ELITE 的非局域剥离—气球模起始、
近局域 KBM 起始 ⇒ $\Delta_{\psi_N}=0.076\sqrt{\beta_{p,\rm ped}}$）预测台基高与宽；"完整模型是稳定性码扫描、不可移植；可移植的是
EPED1-NN {cite}`meneghini2017epednn`——在 EPED1 运行上训练的神经网络代理，以 EPEDNN.jl 开源发布 {cite}`epednn_jl`"。

〔算法（逐行自 `EPEDNN.jl::pedestal_array`）〕〔源码〕输入 $[a,\beta_N,B_t,\delta,I_p,\kappa,m,n_{e,\rm ped},R,Z_{\rm eff,ped}]$；$\delta\to\abs{\delta+1}$；
幂律基 $y^0_k=10^{P_{k,0}+\sum_iP_{k,1+i}\log_{10}x_i}$（18 输出）；标准化 → MLP 10→32→32→32→18，GELU（tanh 形）
{cite}`hendrycks2016gelu`〔凭记忆〕；$y_k=y^0_k+yn_k\,\sigma_k+\mu_k$；平方根空间还原 $p_{\rm ped}=y^2n_{e,\rm ped}\times10^6$ Pa、$\Delta=y^2$；
九个解（dmagGH/G/H × sol0/1/2），索引 0 为"标准 EPED1 答案"；训练盒外**回答而不拒绝**，报告逐维外推距离（"一个零表示每个
输入各自在范围内，不表示在训练集内"——Meneghini §3.4）。权重 `EPED1NNmodel.bson`（`delta_ne_sqrt_power`，SHA-256 已固定）。
$T_{\rm ped}=p_{\rm ped}/(2n_{e,\rm ped}e)$（"EPED 自己的约定 $T_e=T_i$、$n_i\approx n_e$"）；有效三角度 $\tfrac23\min+\tfrac13\max$。

〔与已发表值的对照〕〔源码〕DIII-D 132003 / 132017（NF 49 085035 p. 6 的输入、图 5 像素级读数）在 ±20 % 带内；ITER 基线
$p_{\rm ped}$ 79.0 kPa 对 92 kPa（0.859）、$\Delta$ 0.033 对 0.04（0.826）、$\beta_{N,\rm ped}$ 0.500 对 0.6——**六个比值系统性偏低
（0.83–0.97）**，候选原因列三条、无一断言。源码记录一次**错引**（2026-08-25 前把代理自身答案归于 NF 49）已订正。
KBM 交叉检验 $G=\Delta/\sqrt{\beta_{p,\rm ped}}$：ITER 0.0748、DIII-D 0.0781、EAST 0.0766 对 0.076（5 % 内）——**测试而非模型方程**；
NF 51 §3.1 给 $G=0.084\pm0.010$，EPED1 "因历史原因"保留 0.076。训练集无 EAST、无 C-Mod。

〔接入芯部〕〔源码〕`scenario.rs` `evolve_heat(pedestal = 1)`：$I_p\le0$ 拒绝；$\beta_N$ 由态计算（$\ge0.05$）；$T_{\rm ped}$ 作**下一步**
的 Dirichlet 边界（一步滞后）。Python `stationary.py` 按 FUSE `ActorStationaryPlasma` 次序（源 → 台基 → 输运 → 电流 → 锯齿 → 平衡）
{cite}`meneghini2024fuse`。

(phys11-python)=
# 宿主侧：偏滤器富集与边界条件装配 (Host-Side Assembly)

〔Python〕`enrichment_kallenbach`：$c_{\rm div}/c_{\rm core}=41Z^{-0.5}p_0^{-0.4}(E_{\rm ion,Z}/E_{\rm ion,D})^{-5.8}$（"Kallenbach 2024 图 8；
**回归**不是模型——AUG 放电的拟合"{cite}`kallenbach2024enrichment`〔凭记忆：题名待核验〕）。`boundary_conditions` 返回
$T_{e,\rm sep}$、$T_{i,\rm sep}$、边界浓度；"**什么都没装**——调用方替换边界"；"不解 SOL 输运——无二维场、无再循环、无平行流"。

(phys11-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **单一磁通管、稠态、给定 $n_e\tau$**（缺省 $5\times10^{16}$）；无 SOL 输运、无再循环、无靶板热流剖面。
2. **脱靶只作为求解结果**（`QccSquaredNegative`），无判据；脱靶态两点模型可信度下降（`GK-TMT-07`）。
3. **固定 25 遍** ≠ 收敛判据；正解 25 遍离不动点 0.22 %；多解只取一个。
4. **Mavrin 表外物种辐射为零**（W 等）；$n_e\tau>10^{19}$ 饱和；$T_e$ 钳入拟合域。
5. **中性粒子**：柱几何、单能壁源、无分子、无复合；对 EIRENE 的偏差已量化为 1.8–3.0×（CX 功率）。
6. **EPED1-NN**：训练盒 $a\in[0.40,2.0]$、$B_t\in[1.0,8.0]$ T、$I_p\in[0.36,15]$ MA、$\kappa\in[1.14,2.53]$、$n_{e,\rm ped}\in[0.22,27]\times10^{19}$、
   $Z_{\rm eff}\in[0.67,4.0]$……盒外只报距离；系统性低 3–17 %；无 EAST 训练数据。
7. **常数刻意非 CODATA-2018**（`edge.rs`），与 `neutrals.rs`（CODATA-2018）不一致——两模块间不可混用常数。
8. 记录文件（TORAX 记录）本 checkout 缺，Python oracle 测试跳过；Rust 单测内的锚点仍在。

(phys11-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 边界 / 中性 / 台基模块的锚点。
:name: tbl-p11-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| Mavrin $\expval Z$、$L_z$、$L_{\rm INT}$ | TORAX 记录（896 点 + 18 求积） | $\le6.6\times10^{-14}$ |
| Lengyel 闭式 | TORAX 36 点 | $1.5\times10^{-15}$ |
| 两点态 | TORAX 20 态 | $2.9\times10^{-16}$ |
| 反解 / 正解 | TORAX 10 + 10 例 | $3.3\times10^{-14}$ / $1.3\times10^{-13}$ |
| $\kappa_z(1)=1$、$S(1,0)=1$ | 闭式 | $10^{-9}$ / $10^{-12}$ |
| $T_{cc}/T_t$ 在 20 eV 附近过 1 | 闭式 | 5.9（1 eV）、1.07（10 eV）、0.9961（渐近） |
| Voronov 100 eV、Freeman–Jones 1 keV/amu | 文献量级 | $(2,4)\times10^{-14}$、$(1,3)\times10^{-19}$ |
| MC 簿记 | — | $\abs{\rm ionized+escaped-1}<10^{-12}$ |
| EIRENE 101612 | 带 | 见 {ref}`phys11-neutrals` |
| EPED1-NN 对独立 numpy 评估 | BSON | $10^{-10}$ |
| DIII-D 132003/132017、ITER | NF 49 / NF 51 | ±20 % |
| KBM $G$ | 0.076 | 5 % |
:::

(phys11-asbuilt)=
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 边界 / 中性 / 台基内容与内核函数、C-ABI、Python 入口（2026-09-02 快照）。
:name: tbl-p11-asbuilt
:align: left

| 内容 | 内核函数 | C-ABI（`fylite_rs_*`） | Python |
| :--- | :--- | :--- | :--- |
| Mavrin 非日冕 | `edge::mean_charge_state`, `cooling_rate`, `l_int` | `edge_noncoronal`, `edge_l_int` | `kernel.edge_*` |
| Lengyel 闭式 | `shaping_factor` … `q_parallel` | `lengyel_closed`（geo13 → out7） | `scenario.model.edge.boundary_conditions` |
| 两点态 | `electron_temp_at_cc_interface` … `parallel_heat_flux_at_cc_interface`, `z_eff` | `lengyel_two_point`, `lengyel_z_eff` | 同上 |
| 反解 / 正解 | `solve_inverse`, `solve_forward` | `lengyel_inverse`（`t_e_target_ev < 0` 为正解） | 同上 |
| 中性 MC | `neutrals::neutrals_mc` | `neutrals_mc` | `kernel.neutrals_mc` |
| 台基 | `pedestal::eped1nn`, `eped_ped_top_ev`, `eped_effective_triangularity` | `eped1nn`（out20） | `S.model.evolve(pedestal=True)`；`stationary.py` |
| 富集 | — | — | `edge.enrichment_kallenbach` |
:::

(phys11-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（源码逐字引）〕Mavrin {cite}`mavrin2017noncoronal`；Body 等 {cite}`body2025lengyel`；Eich 等 {cite}`eich2020turbulence`；
Stangeby 2018 {cite}`stangeby2018detachment`；Voronov {cite}`voronov1997fit`；Freeman–Jones {cite}`freeman1974atomic`；
Snyder 等 {cite}`snyder2009development,snyder2009pedestal,snyder2011eped`；Meneghini 等 {cite}`meneghini2017epednn`；EPEDNN.jl {cite}`epednn_jl`；
Tamor ANTIC（规划、未实现）{cite}`tamor1981antic`。〔编者对应〕两点模型 {cite}`stangeby2000boundary`；Brown–Goldston
{cite}`brown2021conductivity`；Verdoolaege {cite}`verdoolaege2021database`；Kallenbach {cite}`kallenbach2024enrichment`；δ 跟踪
{cite}`woodcock1965techniques`；EIRENE {cite}`reiter2005eirene`；Box–Muller {cite}`box1958note`；splitmix64 {cite}`steele2014splittable`；
GELU {cite}`hendrycks2016gelu`；FUSE {cite}`meneghini2024fuse`；TORAX {cite}`citrin2024torax`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references-physics.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕TORAX `extended_lengyel_defaults`、`CONSTANTS.eps`、`mavrin_noncoronal.json`、`extended_lengyel.json`（Apache-2.0）；
EPEDNN.jl `pedestal_array`、`extrapolation_distance`、`effective_triangularity`；FUSE `ActorStationaryPlasma`。

〔源码未注出处〕$q_{\rm cyl}$、pitch、$(1-1/e)$、对流层三组系数（"上游拟合"）、`smooth_sqrt` 形式与 $\varepsilon=10^{-3}$、
初值 / 25 遍 / 0.4 / 0.95、$T_{\rm ped}=p/(2n_ee)$、MC 估计量。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
