---
title: 物理与数值 · 脉冲设计与击穿 (Physics & Numerics — Pulse Design and Breakdown)
subtitle: pulse.rs · breakdown.rs —— 等磁通起点设计、前馈电压（演化的逆）、GSPulse 型全程二次规划、真空零点设计与磁通预算
---

(phys13-intro)=
# 引言：等离子体存在之前与位形之外 (Introduction)

〔范围〕本章详述 `pulse.rs`（约 810 行：**起点**电流设计 `start_currents`、丝填充、前馈电压）与 `breakdown.rs`
（约 670 行：真空零点设计的行装配、通道场、带界最小二乘、达成质量报告），以及 Python 层的 GSPulse 型全程轨迹设计
（`design/pulse.py`）与退火式放电设计（`design/__init__.py::discharge`）。磁通预算与欧姆环电压在 {ref}`phys06-current`、
{ref}`phys06-flux`。

〔两个线性问题〕〔源码〕两模块的共同点：**没有 GS 解**。起点设计"是线性的：等离子体是固定的丝云……不是平衡、也不声称是"；
零点设计"纯真空——无等离子体、无 GS、无环向场，场对电流线性，整个设计是一次小最小二乘"。它们回答的是**在哪里开始**
（退火 / 自由边界解需要的起点）与**能否雪崩**（一个可雪崩的极向场零点加足够的磁通预算）。

〔未实现（明列）〕〔源码 grep〕Townsend 雪崩判据 $\alpha(E,p)$ 与 Paschen 常数、连接长度 $L=0.25a_{\rm eff}B_\phi/B_\perp$、
$E_\parallel$ 要求——**均不在**内核中；`b_tol`（缺省 2 mT）是**用户参数**而非物理推导；名为
`test_breakdown_meets_the_avalanche_criterion_and_says_so` 的测试只断言 $b_{\max}\le b_{\rm tol}$。`GK-TMT-11` / 击穿物理
（Lloyd 等的 Townsend 判据 {cite}`lloyd1991breakdown`〔凭记忆〕）在此只作为**读者须自行施加的外部判据**列出。

(phys13-start)=
# 等磁通起点设计 (Isoflux Start Design)

〔理由〕〔源码〕"形状设计在两个宿主里都是**退火**：解自由边界平衡、读它找到的边界、用一步岭最小二乘修正通道、重复。
那是局域方法……实测四台装置：有参考炮的一台落在目标 3 cm 内，另三台差 0.36–0.77 m 而状态行写着'反解完成'。"
起点设计把问题线性化。

〔行族〕〔源码〕未知量 $I_c$ [A·turn]，逐通道响应 $\psi_c$、$B_{r,c}$、$B_{z,c}$（`breakdown::channel_field`），等离子体场由丝云
经**同一** `element_response`（"使等磁通行两侧可比"）：

- 边界等磁通（$j=1..n_b-1$）：$\sum_c[\psi_c(P_j)-\psi_c(P_0)]I_c=-[\psi_p(P_j)-\psi_p(P_0)]$；
- 每个零点 $X_k$ **三行**（权 `x_weight`）：等磁通行（"使之成为偏滤器的那一行"）、$LB_r=0$、$LB_z=0$，$L=2\pi R_0a$
  （"Tesla 行 → Weber 行的尺度"）——"两个宿主都只要过 $B_r=B_z=0$，那只在机器某处钉一个零点、从未说零点须**在**等离子体边界上；
  另一磁通水平的零点不是偏滤器"；
- 控制点（T-D7）：同形等磁通行，权 `ctl_w`。

〔求解〕〔源码〕响应标度的 Tikhonov：$g_{\rm scale}=\sqrt{\sum a^2/(n_{\rm row}n_{\rm ch})}$、$\lambda_{\rm eff}=\lambda g_{\rm scale}$
（"$\lambda$ 有平方列范数的单位，固定数值在每台机器上意义不同"）；箱 $\pm\abs{i_{\max,c}}$；`bounded_lstsq`（4000 次，$10^{-12}$；
{ref}`phys01-linalg`）。达成度量：边界磁通 RMS、每个零点的 $\abs B$ 与磁通偏移、控制点 $\Delta\psi$、绑定通道。
〔已确立〕等磁通 / 零点行的线性化线圈设计属经典的"等磁通控制"思想 {cite}`hofmann1988tokamak`〔凭记忆〕；源码未注。

〔丝填充〕〔源码〕`fill_filaments`：以边界质心为中心按 $s_k=(k+\tfrac12)/n_{\rm ring}$ 缩放边界（"成形目标一直到轴保持形状"），
权 $w_{k,i}=(1-s_k^2)^{\rm peaking}s_k$（$s$ 为环周长 Jacobian，源码未注），$a=I_pw/\sum w$。"起点模型，仅此——无平衡在内"。

(phys13-feedforward)=
# 前馈电压：演化的精确逆 (Feed-Forward Voltages — the Exact Inverse of Evolution)

〔源码〕给定通道电流轨迹 $x_k$，求电压与感生被动电流：

$$
\Big(\frac{M_{vv}}{\Delta t}+\mathrm{diag}R_v\Big)y_k=\frac1{\Delta t}\big[M_{vv}y_{k-1}+M_{vc}(x_{k-1}-x_k)\big],\qquad
V_{c,k}=\frac1{\Delta t}\big[M_{cc}(x_k-x_{k-1})+M_{cv}(y_k-y_{k-1})\big]_c+R_cx_{c,k}
$$ (eq-p13-ffwd)

$k=0$：$V_{c,0}=R_cx_{c,0}$（"**稠态**电压而非变率"），$y_0=0$。"这是 `evolution::evolve` 的**精确**逆——同一隐式 Euler、同一区间末样本——
而不是把轨迹求导后装扮成它……一种离散化产生、另一种检验的设计会与自身不一致，其量看着像物理。"
往返测试 $10^{-6}$。

(phys13-gspulse)=
# GSPulse 型全程轨迹设计（Python） (Whole-Pulse Trajectory Design)

〔源码〕`design_trajectory`："算法形状取自 GSPulse（J. Wai / CFS，MIT）：外层全程二次规划与逐时刻平衡更新交替。两处刻意不同：
QP 以**纯 numpy 最小二乘**求解——唯一约束是导体动力学这条线性等式，代入消元即无约束问题；线性化用**真实求解器的有限差分形状响应**
（{ref}`phys04-xpoint`），不是解析摄动 GS。外迭代间重线性化起 GSPulse 的 Picard 更新之作用。"

$$
J=\sum_k\norm{W_e(\text{obs}_k-\text{obs}^{\rm ref}_k)}^2+\lambda_v\norm V^2+\lambda_{dv}\norm{\dd V/\dd t}^2\quad\text{s.t. 隐式 Euler 导体动力学}
$$ (eq-p13-qp)

缺省 $\lambda_v=10^{-6}$、$\lambda_{dv}=10^{-4}$、2 次外迭代、$\text{tol}_m=5\times10^{-3}$ m；敏感度张量由 `steps`、`gains` 递推；
`limits=True` 时电压限为**硬箱**（`bounded_lstsq`），否则截断 SVD（`rcond = max(m,n)·ε`）；电流限**检查并报告、不强制**
（"电流限约束的是状态，不能作为设计变量的箱"）；初态已违反 `imax` 的通道标为 `channels_current_limit_suspect`（"限值错而非设计错"）。
〔出处〕GSPulse {cite}`wai2022gspulse`〔凭记忆〕；形状响应的中心差分 `step = max(0.01|x0|, 1e3)` A·turn。用户指南实测：
3 cm 间隙斜坡 50 ms 内在 EAST 上不可行（12 通道 7 个越压，最劣 8.5×），300 ms 可行——"电源电压限制的是形状变化的**速率**"。
2026-09-02 记录：numpy 的 `bounded_lstsq` 孪生在 `flux_target = 1.0` Wb 上撞 4000 次上限、残差 $1.08\times10^3$ 对内核 $6.7\times10^{-1}$，已删除。

〔退火〕〔源码〕`discharge`：几何调度 $\alpha_i=0.10(0.005/0.10)^{i/7}$（8 遍）、更新 $\gamma=0.4$；每遍自由边界解 → 描迹 → 形状矩 →
六项形状误差 $\epsilon$ → `ridge_lstsq` 修正（等磁通 + 三 X 点行，测量 $\psi$ 代替 $\psi_p$）；塌陷守卫（$a<0.25a^t$ 半步重试 ≤3 次）；
返回**最佳**遍。常数"是浏览器页面自己的数，不是新的"（无出处）。

(phys13-breakdown)=
# 真空零点设计 (Vacuum Field-Null Design)

〔行族与归一〕〔源码〕未知量 $I_c$；采样盘：中心 + $n_{\rm ring}$ 环 × $n_\theta$ 角（缺省 4 × 16 = 65 点，半径 0.3 m——
"盘是设计的一部分：'$\abs B$ 低于几 mT'没有'在多大区域上'就没有意义"）；

$$
\frac{w_n}{b_{\rm tol}}\sum_cB_{r,cp}I_c=0,\quad\frac{w_n}{b_{\rm tol}}\sum_cB_{z,cp}I_c=0\ (\forall p);\qquad
\frac{w_f}{\abs{\Phi_t}}\sum_c\psi_cI_c=w_f\,\mathrm{sign}\Phi_t;\qquad \sqrt\lambda(I_c-x_{{\rm ref},c})=0
$$ (eq-p13-null)

:::{important}
〔归一是全部机制〕〔源码〕"零点行带特斯拉（$\sim10^{-3}$），磁通行带韦伯（$\sim10^{-1}$）。不归一则磁通项压倒零点，'设计'出来的是
均匀场而非零点——且不报错。两族各除以自己的容差（场除 $b_{\rm tol}$、磁通除目标），残差 1 在任一族都意味'达容差'。"
用户指南："`max ≈ rms ≈ 中心` 正是它的征兆"。
:::

〔求解与守卫〕〔源码〕`bounded_lstsq`，`MAX_ITER = 50_000`——"4000 不够且**静默失败**：EAST deck 上箍紧箱到一个通道绑定时需 **32 273**
次收敛，4000 次时目标是收敛值的 4.3×……上限仍是上限，变的是耗尽**被报告**（`converged`）"；`BIND_TOL = 1e-3`（"求解器的，
不是物理的——投影梯度从内侧逼近界，实测停在 $1.6\times10^{-4}$ 之内；$10^{-6}$ 判据永不触发"）；分类 `over`（$>i_{\max}(1+10^{-9})$）、
`at_bound`（$\ge i_{\max}(1-10^{-3})$）。C-ABI 未收敛返回 **−3**（末迭代仍写出）。

〔可行性裁决（Python）〕〔源码〕`feasible = null_ok ∧ flux_ok ∧ 无越流通道`，理由码 `channel_limit` / `flux_not_met_at_channel_limits` /
`flux_not_met` / `null_not_met`——"**同时**要求零点与请求的磁通……不要磁通地最小化 $\abs B$ 有平凡解'全部关掉'：实测 500 A·turn 上限
给出漂亮零点（$8\times10^{-7}$ T）却只交付 3 Wb 请求的 0.002 Wb"。环电压 $V_{\rm loop}=-\dd\psi_{\rm null}/\dd t$（`kernel.gradient`）——
无阈值、无 $E_\parallel$ 判据。`feasible`：任两参数的二维扫描，每格独立静解。

〔物理自检〕〔源码〕轴对称 $\nabla\cdot\vb B=0$：$\partial_r(rB_r)+\partial_z(rB_z)=0$ 到 $10^{-3}$ 尺度（"独立的物理检验而非参考值"）；
单环 $\abs B\approx\mu_0I/(2R)$ 因子 2 内；实测 EAST（装置文档，1336 次迭代）：0.3 m 盘内 $\abs B$ 峰 $7.15\times10^{-6}$ T、
磁通 0.2794 Wb / 目标 0.3、可行。

(phys13-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **起点不是平衡**：无力平衡；须交给 {ref}`phys02-free` 的自由边界解或退火。
2. **零点设计是真空**：无等离子体、无环向场、无雪崩物理；$b_{\rm tol}$ 是用户给的；Townsend / 连接长度 / $E_\parallel$ 判据须外加。
3. **电流限只报告**（轨迹设计）；电压限是硬箱。
4. **形状响应是有限差分**，对步长 1 %–50 % 稳定（用户指南实测 0.1–0.5 % 线性度）；角采样边界点须经 $\psi$ 场射线求交。
5. **退火是局域方法**，无参考炮的装置上可差 0.36–0.77 m；起点设计正是为此。
6. **`bounded_lstsq` 的迭代上限是上限**；耗尽须读 `converged` / 返回码 −3。
7. **有限差分标度 $L=2\pi R_0a$、$\lambda_{\rm eff}$、$w_n/b_{\rm tol}$** 是工程归一，无物理出处。

(phys13-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 脉冲设计与击穿的锚点。
:name: tbl-p13-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 前馈 ↔ 演化往返 | `evolution::evolve` | $10^{-6}$（通道与被动） |
| 平坦轨迹 | 闭式 | $V=Rx$（$10^{-9}$），$y=0$（$10^{-12}$） |
| $\nabla\cdot\vb B=0$ | 物理 | $10^{-3}$ 尺度 |
| 单环 $\abs B$ | $\mu_0I/2R$ | 因子 2 |
| 零点 + 磁通（玩具机） | — | 收敛，$b_{\max}<2$ mT，$b_{\rm centre}<0.1b_{\max}$，随半径单调 |
| 绑定设计收敛 | — | 32 000 次内收敛并报告 |
| 环电压符号与量级 | 0.3 Wb / 20 ms | $V>0$，均值 $\in(1,100)$ V |
| 3 cm 间隙斜坡 50 ms | 真实求解器 | 10 mm 内跟踪；40 cm 请求不可行 |
| EAST 击穿 | 装置文档 | $b_{\max}=7.15\times10^{-6}$ T，$\Phi=0.2794$ Wb |
:::

(phys13-asbuilt)=
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 脉冲 / 击穿内容与内核函数、C-ABI、Python 入口（2026-09-02 快照）。
:name: tbl-p13-asbuilt
:align: left

| 内容 | 内核函数 | C-ABI（`fylite_rs_*`） | Python |
| :--- | :--- | :--- | :--- |
| 起点设计 | `pulse::start_currents`, `fill_filaments` | `start_currents`, `start_currents_multi`, `fill_filaments` | `S.design.start_state`, `discharge` |
| 前馈电压 | `pulse::feedforward_voltages` | `feedforward_voltages`（`-k-10`） | `S.design.pulse.design_trajectory` |
| 零点设计 | `breakdown::null_disc`, `channel_field`, `design_null`, `null_quality`, `design` | `null_disc`, `channel_field`, `design_null`, `breakdown_design`（`-3` 未收敛） | `S.design.breakdown`, `feasible`, `loop_voltage` |
| 带界最小二乘 | `linalg::bounded_lstsq` | `bounded_lstsq` | `kernel.bounded_lstsq` |
| 通道限值 | — | — | `pulse.channel_limits`（装置 `power_supply`） |
:::

(phys13-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（编者对应；源码未注）〕等磁通线圈设计 {cite}`hofmann1988tokamak`；击穿的 Townsend 判据（**未实现**，供读者外加）
{cite}`lloyd1991breakdown`；投影 BB 带界最小二乘 {cite}`barzilai1988two,birgin2000nonmonotone`；Tikhonov {cite}`tikhonov1963solution`。
标 〔凭记忆〕 者字段待核验。

〔转引〕GSPulse（J. Wai / CFS，MIT）{cite}`wai2022gspulse`——算法形状；TokSys `EAST_PS_params.m`（电源参数；Walker 2010，源引 ASIPP）；
浏览器页面 `scenario-design.js`（退火常数来源）。

〔本仓选择〕三行 X 点、$L=2\pi R_0a$、$\lambda_{\rm eff}$ 响应标度、盘采样 4 × 16、`MAX_ITER = 50_000`、`BIND_TOL`、可行性裁决规则、
前馈作为演化的精确逆。证据为 {numref}`tbl-p13-verify`。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
