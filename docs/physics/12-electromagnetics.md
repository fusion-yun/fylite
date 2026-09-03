---
title: 装置电磁、垂直稳定性与控制 (Device Electromagnetics, Vertical Stability and Control)
subtitle: 互感与响应、电压驱动电路演化、刚性 n=0 垂直模色散、秩一消元的线性化对象与 PD 闭环
---

(phys12-intro)=
# 引言：M、R 与一个时间推进 (Introduction)

〔范围〕本章详述装置一侧的四部分内容：EFIT 型平行四边形单元的互感矩阵、网格 / 探针响应与通道
空间电路矩阵；电压驱动的隐式 Euler 电路推进；刚性 $n=0$ 垂直模的丝云、耦合梯度、刚度、理想刚度与
色散根；以及无质量等离子体的秩一消元、开环增长率与 PD 闭环仿真。丝核与椭圆积分在 {ref}`phys01-filament`。

〔出处姿态〕〔实现〕装置电磁层承接 L1 的**位同一性契约**（逐项再现 `circuits.py`）；垂直稳定层头部记其为
"第一个落地的物理层，因为它有第三方锚（TokSys `rzrig`：刚度 0.47 %、裕度 0.72 %、$\gamma$ 2.97 %）且无清洁室约束"；
Python 层记算法结构"改编自 fytok `fyeq/stability.py`（copy-adaptation）"。四个模块对物理公式**一律未给文献**
（只有 Sherman–Morrison、Barzilai–Borwein 等算法名与 TokSys 数值锚）；本章的一手文献是编者的对应。

〔与理论手册的分工〕互感矩阵构造与自感对数奇异、涡流模态分解、线性化装置模型三步推导、垂直不稳定性的能量论证与
增益窗口，见 SpResearch `GK-TMT-11`（跨仓）。

(phys12-em)=
# 电磁对象层 (The Electromagnetic Object Layer)

(phys12-em-mutual)=
## 单元互感与自感 (Element Mutual and Self Inductance)

〔实现〕单元以六个平行数组 $(r,z,w,h,a,a_2)$ 给出（{ref}`phys01-filament-element`），剖成 $n_u\times n_v$ 丝云；
非对角 $M_{AB}=\frac{1}{n_An_B}\sum_{i\in A}\sum_{j\in B}M(\text{fil}_i,\text{fil}_j)$（numpy 成对求和序）；对角以薄丝自感
{eq}`eq-p01-self` 替换奇异项后取块均值。〔已确立〕丝云等权平均 ⇔ 单元内均匀电流密度；自感的对数奇异及其截断
（等面积圆截面）见 {cite}`grover1946inductance`〔凭记忆〕与 `GK-TMT-11`。`mutual_matrix_self` 对称（上三角算、镜像）；
`mutual_matrix_cross` $n_a\times n_b$；匝数**不在此**乘（`scale_by_turns`：$M_{ij}\leftarrow(M_{ij}n^a_i)n^b_j$，"匝数每侧进一次——
自集矩阵对角因此带 $N^2$"）。

(phys12-em-response)=
## 网格、探针与场响应 (Grid, Probe and Field Responses)

〔实现〕`grid_response`：$G_e(R_i,Z_j)=\frac{1}{n_f}\sum_{f\in e}M(R_i,Z_j;r_f,z_f)$ [Wb/A]（全磁通）；
`element_flux` $\psi=\sum_eI_eG_e$；`filament_flux` $\psi=\sum_kI_kM(\cdot;r_k,z_k)$。场由磁通中心差分：

$$
B_Z=\frac{1}{2\pi R}\pdv\psi R,\qquad B_R=-\frac{1}{2\pi R}\pdv\psi Z,\qquad h=10^{-4}\ \text{m}
$$ (eq-p12-bfield)

〔已确立〕由 $\vb B=\nabla\psi_{\rm rad}\times\nabla\phi$ 与 $\psi_{\rm Wb}=2\pi\psi_{\rm rad}$ 即得（{ref}`phys02-eq-gs`）。探针读数
$B_p=B_R\cos\alpha_p+B_Z\sin\alpha_p$；`probe_response` 把每个网格格作为节点上的单位丝，节点与探针重合（$10^{-12}$）者写 **0**
（"死行而非无穷"）。实现："角度约定错了不会报错：拟合只是收敛到一个倾斜以匹配的等离子体"。Python 记录：另一实现用
"百分之一格"步长，在 333775 格中 17 格差 $\le2.2\times10^{-2}$（都在探针一格内），对探针信号最差 $3.1\times10^{-7}$。
两算路检验 `table_ratio_check`：逐段取 `table/mine` 的**中位数**、剔除距单元中心 $2\max(w,h)$ 内的近场；EAST `rfcoil.ddd`
对计算值 $7.7\times10^{-5}$（$n_u=n_v=8$），随剖分收敛 $4.88\times10^{-4}\to7.72\times10^{-5}$。

(phys12-em-circuit)=
## 通道空间电路矩阵 (Circuit Matrices in Channel Space)

$$
M_{ch}=WM_{el}W^T,\qquad M_{ch,v}=WM_{ev},\qquad R_{ch,c}=\sum_jw_{cj}^2R_{el,j},\qquad R_{el,j}=\eta_j\frac{2\pi r_j}{w_jh_j}
$$ (eq-p12-channel)

〔实现〕"安匝空间的回路方程只带**每匝**几何量 $U/N=M_1\dot x+R_1x$，故 $M_{ch}=WM_1W^T$ 而 $R_{ch}=\sum_jw_j^2R_{1,j}$——
权重进电阻**平方**、进电感一次"；$\eta$ 以 Ω·m（deck 的 µΩ·m 在读取处换算）。〔已确立〕这是耦合回路串并联的 Kirchhoff
规则；测试 `a_channel_split_enters_the_resistance_squared` 以 EAST 的 0.175/0.825 分裂通道钉住。实测：真空室段 1 的电阻
$9.5189\times10^{-3}$ Ω（对 TokSys 0.20 %）；真空室本征时标 $\tau=M/R\in[0.39,13.1]$ ms。

(phys12-evolution)=
# 电压驱动的电路演化 (Voltage-Driven Circuit Evolution)

$$
\Big(\frac{M}{\Delta t}+\mathrm{diag}(R)\Big)I^{n+1}=\frac{M}{\Delta t}I^n+V^{n+1}-\frac{\Delta\psi_{\rm plasma}}{\Delta t}
$$ (eq-p12-euler)

〔实现〕`step`：**纯隐式（向后）Euler**，无 θ 参数；电压取**区间末**样本；等离子体磁通增量作为 EMF 进入
（"等离子体自己的磁通变化是像任何其他一样的 EMF，以同一 $1/\Delta t$ 进入"）；解用 Cholesky + **一步迭代精化**
（"真空室耦合系统条件数 $\sim10^8$，裸 Cholesky 离 LAPACK LU 答案 $2\times10^{-9}$——在设计的 $10^{-10}$ L5 带之外"）；
每步重组、重分解；非 SPD → `Err(k)`。〔已确立〕耦合回路方程 $M\dot I+RI=V$ 及其隐式离散 {cite}`jardin2010computational`；
向后 Euler 对 $L/R$ 时标谱无条件稳定 {cite}`leveque2007fdm`。等离子体 ↔ 电路的 GS 交替不在本模块（由场景层驱动：
`S.control.evolution.evolve_free_boundary`——每匝电压 → 隐式 Euler（12 通道 + 40 壳段）→ 逐步正解，涡流场进 GS）。
锚：单 RL 回路 $L=1$ H、$R=2$ Ω、$V=4$ V → $I=2$ A（$10^{-6}$）；稠态是不动点；用户指南实测"关掉被动结构位形演化须显著改变"。

(phys12-vstab)=
# 刚性 n=0 垂直稳定性 (Rigid n=0 Vertical Stability)

(phys12-vstab-model)=
## 丝云、耦合梯度与刚度 (Filaments, Coupling Gradient and Stiffness)

〔实现〕`plasma_filaments`：由平衡自身剖面 $j_\phi=Rp'(\psi_N)+FF'(\psi_N)/(\mu_0R)$ 造格电流 $I_{\rm cell}=j_\phi\Delta r\Delta z$；
格属等离子体 ⇔ $0\le\psi_N\le1$ **且**在边界多边形内（"两半都需要：私有磁通区 $\psi_N$ 回到 $[0,1]$，多边形排除它；
多边形单独会收进略不一致边界外的格"）；可 $c\times c$ 粗化到 $\abs{\text{电流}}$ 加权质心；最后**重标定到 $I_p$**
（"不是装饰：剖面离散留下百分级缺口，下游每个刚性模量都是电流的二次式——$I_p$ 差 1 % 即 $\gamma$ 差 2 %"）。

$$
G_l=\sum_i\frac{a_i}{I_p}N_l\pdv{M(r_i,z_i;r_l,z_l)}{Z_p},\qquad
k=\sum_ia_i\pdv{^2\psi_{\rm ext}}{Z^2}\Big|_{(r_i,z_i)}
$$ (eq-p12-gk)

〔实现〕$\partial_ZM$ 由 $h=10^{-4}$ m 中心差分；$k$ 的二阶导以外步 $10^{-3}$ m、内步 $10^{-4}$ m 嵌套差分；$k>0$ 失稳。
〔已确立〕刚性位移模型：整个丝集同一 $\delta Z$，恢复力由外场曲率 $\partial_Z^2\psi_{\rm ext}$ 与被动导体涡流耦合给出
{cite}`lazarus1990vertical`〔凭记忆〕、`GK-TMT-11`；实现只注 fyeq 来源。

(phys12-vstab-dispersion)=
## 色散关系与理想刚度 (Dispersion Relation and Ideal Stiffness)

$$
k=\gamma I_p^2G^T(\gamma M+R)^{-1}G+m\gamma^2,\qquad k_{\rm ideal}=I_p^2G^TM^{-1}G
$$ (eq-p12-dispersion)

〔实现〕`dispersion_root`：$D(\gamma)$ 在 $\gamma$ 上单调，故**二分**（自 $\gamma_{\max}=10^6$ s⁻¹ 对半下探直到 $D\le0$，
再 200 轮二分至 $10^{-15}$ 相对）；$D(\gamma_{\max})\le0$ → `NoRoot`（理想不稳）；$m=0$ 为准静态极限（"每个逐步 GS 码都假定的"）。
分档（Python）：$k\le0$ **stable**；$k\ge k_{\rm ideal}$ **ideal-unstable**（$\gamma=\infty$）；否则 **resistive-wall**，
裕度 $=k_{\rm ideal}/k-1$（"读自两个刚度，不读自增长率——理想不稳区无有限 $\gamma$ 可读"）。
〔已确立〕$k_{\rm ideal}$ 是理想导体（$R\to0$）极限：无源导体只能把增长率从 Alfvén 时标拖到 $L/R$ 时标、不能镇定
（`GK-TMT-11` 的能量论证）。惯性修正：$m=n_eAm_uV$（EAST 典型缺省），实测 $m=9.1\times10^{-7}$ kg、$\sqrt{k/m}=5.5\times10^5$ rad/s、
$\gamma=12.6$ s⁻¹ ⇒ 修正 $2\times10^{-9}$——"逐步 GS 假定精确到 9 位"。

〔TokSys 锚〕〔实现〕EAST #137985，全 90 段被动导体：刚度 278916 N/m（1 % 内）、裕度 0.6906（2 % 内）、
$\gamma_z=9.4575$ s⁻¹（**同一导体集**上 5 % 内——"rzrig 把主动线圈放进电路"）；仅被动色散给 12.6 s⁻¹（"刻意更悲观的问法"）。
被动集敏感性：仅内壳 $\gamma=3437$ s⁻¹、内 + 外壳 2330、内壳 + 铜板 13.7、全 90 段 **12.6**——"只用内壳高估 270 倍"；
$\eta\times2\Rightarrow\gamma\times2$ 精确（$10^{-5}$）。早期 TokSys 对拍失配（0.2215 对 12.64 s⁻¹）归因于 fylite 侧把线圈电流除匝数两次。

(phys12-control)=
# 线性化对象与闭环 (The Linearised Plant and Closed Loop)

(phys12-control-plant)=
## 秩一消元 (Rank-One Elimination)

$$
k\xi+I_pG^T\delta I=0\ \Rightarrow\ \xi=-\frac{I_p}kG^T\delta I,\qquad
M^\ast=M-\frac{I_p^2}kGG^T,\qquad M^\ast\dot{\delta I}+R\,\delta I=V,\qquad
A=-(M^\ast)^{-1}\mathrm{diag}(R)
$$ (eq-p12-plant)

〔实现〕"等离子体在关心的时标上无质量，其力平衡是代数的，折成导体电感的秩一修正"；开环增长率 = $A$ 的最大实特征值
（`eigen`，{ref}`phys01-linalg`），不稳模取**实部**并归一到 $C_\xi\cdot\text{mode}=1$；"**必须**与 `dispersion_root` 一致——
两种表述由 Sherman–Morrison 相联，故一致是接线的真检验而非重言"（测试 $10^{-8}$ / $10^{-6}$）。〔已确立〕Sherman–Morrison
公式 {cite}`sherman1950adjustment`〔凭记忆〕；线性化装置模型的一般三步推导（回路骨架 → 等离子体响应吸收进 $M^\ast$ → 状态空间）
见 `GK-TMT-11`。

:::{important}
〔拒绝〕〔实现〕"消元只在**电阻壁区**有效。$M^\ast$ 恰在 $k=k_{\rm ideal}$ 奇异，其上秩一减法不再翻转特征值——$-M^{\ast-1}R$
全部特征值为负、对象读作**稳定**，而色散路线说理想不稳。对最不稳的情形回答'稳定'是本模块最坏的失效形态，故在此拒绝
而非返回。"错误码 `-6`；$k=0$ 亦拒绝；$k<0$ 不拒绝。
:::

(phys12-control-loop)=
## PD 闭环仿真 (Closed-Loop Simulation)

〔实现〕`close_loop`：隐式 Euler 对象 $(M^\ast/\Delta t+\mathrm{diag}R)x_{k+1}=\frac{M^\ast}{\Delta t}x_k+B_{\rm act}u_k$；初态沿不稳模
$x_0=\xi_0\cdot\text{mode}$；测量 $\hat\xi$ 为状态反馈或磁通环**最小二乘观测器**

$$
\hat\xi=\frac{\sum_l(\psi_l-\psi_{c,l})P_l}{\sum_lP_l^2}
$$ (eq-p12-observer)

（"导体电流可测，减去其份额后投影到等离子体位移行；无噪声时精确，有噪声时是最小二乘估计"）；**PD 律**
$v_{\rm cmd}=-(k_p\hat\xi+k_d\dot{\hat\xi})$，导数取**一步测量延迟**（"PD 律只在快于模增长时镇定；读当前步会隐藏真实数字回路
恰有的失效"）；限幅 $\pm v_{\max}$；单极执行器滞后 $u_a\leftarrow u_a+\frac{\Delta t}{\tau}(v_{\rm cmd}d_a-u_a)$（显式 Euler）。
**无积分项、无增益界计算**（`GK-TMT-11` 的增益窗口论证在本内核未实现；增益只出现在测试：$k_p=300$、$k_d=0.3$ 等）。
〔已确立〕隐式 Euler 每步放大 $1/(1-\gamma\Delta t)$——"不看 $\gamma$ 选的步长每 e 折高估 $\gamma\Delta t/2$"。

〔Python 装配〕`vertical_system`：通道空间 $M$、$R$（{eq}`eq-p12-channel`）+ IC 线圈作为每匝电路成员、$G=[Wg_{el},g_{vs},g_{ic}]$、
$B_{\rm act}$ 指向 IC 对（缺省方向 $(1,-1)$，反对称）；磁通环行 $C$、$P=I_pG_{\rm loops}$。实现记录 PF 电源单极滞后 $\tau\approx15$ ms
（TokSys `EAST_PS_params.m`）；早期文档"PF 无法持住模"的断言已被全被动集下 $\gamma\approx9$–12.6 s⁻¹（增长时间 $\sim109$ ms）
**取代**——"滞后不致命，只改变可用增益"（$k_p=3.16\times10^3$、$k_d=51.8$ 在 15 ms 滞后下镇定）。

(phys12-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **理想丝与均匀电流密度单元**；近场响应依赖剖分细度（两算路检验剔除近场）。
2. **刚性位移、无质量**（惯性可选，实测可忽略）；只 n=0；无变形模、无 3D。
3. **同一导体集**才可比 $\gamma$；被动集选择改变 $\gamma$ 两个数量级。
4. **消元只在电阻壁区**；$k\ge k_{\rm ideal}$ 拒绝。
5. **PD 无积分项**；增益由用户给，无界计算；观测器是最小二乘、无卡尔曼。
6. **电路演化不含 GS**——等离子体只经外给 $\psi_{\rm plasma}(t)$ 进入；GS 交替是场景层的。
7. **非线性演化路径的涡流只走 40 段制表列**（IC 与外壳 / 铜板无 Green 响应列，缺口 E-18）；线性化路径不受此限。
8. 时间步须 $\gamma\Delta t\ll1$。

(phys12-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 电磁 / 稳定性 / 控制的锚点。
:name: tbl-p12-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 刚度、裕度 | TokSys `rzrig`（EAST #137985） | 1 %、2 %（实测 0.47 %、0.72 %） |
| $\gamma_z$（同导体集） | TokSys 9.4575 s⁻¹ | 5 %（实测 2.97 %） |
| 线圈—环响应 | EAST `rfcoil.ddd` | $7.7\times10^{-5}$（$n_u=n_v=8$） |
| 真空室段电阻 | TokSys `resv[0]` | 0.20 % |
| $\gamma$、$k_{\rm ideal}$ | numpy 参考链 | $10^{-10}$ |
| 耦合梯度、刚度 | numpy 参考 | 逐位 |
| 特征路径 vs 色散 | Sherman–Morrison | $10^{-8}$ / $10^{-6}$ |
| $\eta\times2\Rightarrow\gamma\times2$ | 标度 | $10^{-5}$ |
| 惯性修正 | 自身 | $\abs{\gamma_{\rm inertial}/\gamma-1}<10^{-6}$ |
| 断环 e 折 | 特征值 | $\pm1\%$（Rust）、$2\times10^{-3}$（Python） |
| 闭环回零 | $k_p=300$、$k_d=0.3$ | $\abs{\xi_{\rm end}}<0.01\xi_0$，$\max\abs u<5$ V/turn |
| 单 RL 回路 | 闭式 | $I=V/R$（$10^{-6}$） |
:::

(phys12-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 导体、响应、电路与垂直稳定性各项的产出，及其所落的 fyo 数据集。
:name: tbl-p12-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| 互感矩阵、匝数与通道折叠 | `fyo:pf_active`：线圈与通道的定义 | `fylite.device.conductor_set`、`channel_matrices` |
| 网格 / 磁通环 / 探针响应 | `fyo:magnetics`：各道的响应（供反演与合成诊断） | `fylite.device`；`recon_rs.coil_loop_rows` |
| 电压驱动的电路演化 | `fyo:pf_active`：随时间的线圈电流 | `S.control.evolution.evolve_free_boundary` |
| 垂直稳定性（刚性位移） | `fyo:mhd_linear` 式的增长率与理想判据 | `S.control.vstab`；`stability.vertical_mode` |
| 对象模型与闭环 | `fyo:pulse_schedule`：控制器给出的电压 | `vertical.vertical_system`、`close_vertical_loop` |
:::

(phys12-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（编者对应；实现未注）〕互感与自感 {cite}`maxwell1873treatise,grover1946inductance`；电路方程与隐式推进
{cite}`jardin2010computational,leveque2007fdm`；刚性垂直位移模型 {cite}`lazarus1990vertical`；Sherman–Morrison {cite}`sherman1950adjustment`；
非对称特征分解 {cite}`golub2013matrix`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕TokSys `rzrig` / `gsevolve` / `EAST_PS_params.m`（General Atomics；数值锚，静态读取 + 一次实跑记录）；fytok `fyeq/stability.py`、
`fyeq/circuits.py`（copy-adaptation）{cite}`fytok_fytrans`；EFIT/efund 单元几何与 `rfcoil.ddd` / `rv6565.ddd` 表（已按 LICENSE 3.1 移除，
只余判据）。

〔本仓选择〕差分步长 $10^{-4}$ / $10^{-3}$ m；二分 200 轮与 $10^{-15}$；$\gamma_{\max}=10^6$；粗化质心；$I_p$ 重标定；观测器形式；
一步测量延迟；理想区拒绝。证据为 {numref}`tbl-p12-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
