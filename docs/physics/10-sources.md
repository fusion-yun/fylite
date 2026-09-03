---
title: 源项、辐射与体积分 (Sources, Radiation and Volume Integrals)
subtitle: ADAS 冷却曲线与辐射、同步辐射、电子—离子交换、Spitzer 电阻率与欧姆加热、两种积分器、目标通量与功率账
---

(phys10-intro)=
# 引言：输运方程右端的账 (Introduction)

〔范围〕本章详述**源项、辐射与体积分**：`tgyro_source.f90` / `tgyro_rad.f90` / `tgyro_volume_int.f90` 的
白箱移植（GACODE，Apache-2.0，见 `NOTICE`），**全程 CGS、eV**（与 TGYRO 自身及本书的映射层一致）。
内容：ADAS 冷却曲线的 Chebyshev 拟合与线辐射、NRL 近似轫致辐射、Trubnikov 同步辐射、电子—离子能量交换、
Spitzer 电阻率与欧姆加热、准中性闭合、两种体积积分器、目标通量、TGYRO 的功率簿记。$\alpha$ 加热**不在此**
（"GACODE 的回归例不含 D-T"；见 {ref}`phys09-alpha`）。非日冕辐射（Mavrin 2017）在 边界层（{ref}`phys11-intro`），
实现强调"不是 `adas_cooling` 的另一种拼写——那是日冕平衡冷却率"。

〔出处姿态〕〔实现〕本模块对多数公式只给上游文件名；一手文献在实现中出现的有 Open ADAS 与 Pütterich 2019、
NRL 手册、Spitzer–Härm 1953、Trubnikov 1972。其余由编者对应，标核验状态。

(phys10-radiation)=
# 辐射 (Radiation)

(phys10-radiation-adas)=
## ADAS 冷却曲线与线辐射 (ADAS Cooling Curves)

〔实现〕`ADAS21`：22 个物种（H = D = T 同一曲线，20 条不同曲线）的 12 项 Chebyshev 拟合，$T_e\in[0.05,50]$ keV：

$$
x=\mathrm{clamp}\!\Big(-1+2\frac{\ln(T_e/T_{\min})}{\ln(T_{\max}/T_{\min})},-1,1\Big),\qquad
L_z(T_e)=\exp\!\Big(\sum_{n=0}^{11}c_n\cos(n\arccos x)\Big)\ [\text{erg cm}^3\text{ s}^{-1}]
$$ (eq-p10-adas)

域外取**边界值**而非外推（测试 `the_cooling_curve_clamps_rather_than_extrapolates`）。系数取自 `tgyro_rad.f90`
的 `adas21`；实现注来源 "Open ADAS (https://open.adas.ac.uk); T. Puetterich et al 2019 Nucl. Fusion 59 056013"
{cite}`openadas,puetterich2019cooling`。〔已确立〕$T_n(x)=\cos(n\arccos x)$ 是第一类 Chebyshev 多项式。
未知物种 `adas_id` 返回 `None` ⇒ **线辐射为零**（"上游行为，真正的陷阱"）。

〔线辐射与轫致辐射的拆分〕〔实现〕`rad_ion`：

$$
P_{\rm brem}=\sum_i10^7\cdot1.69\times10^{-32}\,n_en_iZ_i^2\sqrt{T_e[\text{eV}]},\qquad
P_{\rm total}=\sum_in_en_iL_z^{(i)},\qquad P_{\rm line}=P_{\rm total}-P_{\rm brem}
$$ (eq-p10-brem)

"拆分不物理：`brem` 是 NRL 近似式，`line` 是 ADAS 总量减去它的剩余——只有和是 ADAS 值。"
〔出处〕$1.69\times10^{-32}n_en_iZ^2T_e^{1/2}$ W/cm³ 是 NRL 手册的轫致辐射功率密度 {cite}`huba2013nrl`（实现注 "NRL"）。

(phys10-radiation-sync)=
## 同步辐射 (Synchrotron Radiation)

〔实现〕`rad_sync`（"Trubnikov, JETP Lett. 16 (1972) 25"）{cite}`trubnikov1972synchrotron`，$B$ 以 Gauss、
$a$ 以 cm，反射系数 $r=0.8$（`SYNC_REFLECTION`，"Rosenbluth 壁反射系数"）：

$$
g=\frac{kT_e}{m_ec^2},\qquad
\Phi=60\,g^{3/2}\sqrt{\frac{(1-r)\big(1+\frac{1}{A\sqrt g}\big)}{a\,\omega_{pe}^2/(c\,\omega_{ce})}},\qquad
P_{\rm sync}=\frac{m_e}{3\pi c}\,g\,(\omega_{pe}\omega_{ce})^2\,\Phi
$$ (eq-p10-sync)

"上游喂它 `expro_bt0`——磁面上的环向场而非 $B_{\rm unit}$……此项 $\propto B^4$"。〔未核验〕常数 60 与 $\Phi$ 的形式
只归于 Trubnikov 1972；壁反射的处理与 Rosenbluth 1970 的 $(1-r)$ 因子同型 {cite}`rosenbluth1970synchrotron`〔凭记忆〕，
实现未给文献。

(phys10-exchange)=
# 电子—离子能量交换 (Electron–Ion Energy Exchange)

$$
P_{ei}=\tfrac32\,\nu_{\rm exch}\,n_e\,k\,(T_e-T_i)\ [\text{erg cm}^{-3}\text{s}^{-1}]\quad(\text{正向离子})
$$ (eq-p10-exch)

$\nu_{\rm exch}$ 见 {eq}`eq-p04-exch`（`exchange_rate`；只有**热**离子计入）。〔出处〕经典电子—离子
等分率 {cite}`spitzer1962physics,huba2013nrl`；实现未注（TGYRO 移植）。SI 面：`assembly.exchange_si` × 0.1。

(phys10-resistivity)=
# Spitzer 电阻率、欧姆加热与准中性 (Resistivity, Ohmic Heating, Quasi-Neutrality)

$$
\eta_\perp=1.03\times10^{-4}\,Z\,\ln\Lambda\,T_e[\text{eV}]^{-3/2}\ \Omega\,\text{m},\qquad
\eta_\parallel=0.51\,\eta_\perp,\qquad P_\Omega=\eta\,(j_\parallel\cdot j_\parallel)\ [\text{W/m}^3]
$$ (eq-p10-spitzer)

〔出处〕〔实现〕"NRL 手册系数如印：$\eta_\perp=1.03\times10^{-2}Z\ln\Lambda T_e^{-1.5}$ Ω·cm"{cite}`huba2013nrl`；
"NRL 手册；Spitzer & Härm 1953，$\gamma(Z=1)=0.51$" {cite}`spitzer1953transport`。"0.51 在所有 $Z$ 上按 $Z=1$ 施加"；
捕获粒子修正不折入（"经新经典模型达到的有据可查的精化"，{ref}`phys07-intro`）。
〔历史〕〔实现 / 保真度章〕该函数曾在此名下返回**垂直**值（T-A18 前），使欧姆功率高约一倍；订正后
$\sigma_{\rm Sauter}\times\eta_\parallel\approx1$（实测 0.998）、$\eta_\parallel/\eta_\perp\equiv0.51$ 到 $10^{-15}$。
准中性 $n_e=\sum_sz_sn_s$（`quasi_neutral_ne`）。

(phys10-integrals)=
# 两种积分器与目标通量 (Two Integrators and the Target Flux)

〔实现〕"两个积分器，不是一个"：

- `volume_int`（"上游的 `tgyro_volume_int`——二次插值求积，不是梯形"）：$P(r)=\int_0^rV'(x)s(x)\dd x$ 在 TGYRO 自己的
  5–10 点通量匹配网格上，每段用三节点二次插值的精确积分（首段用 $(0,1,2)$，其后 $(i-2,i-1,i)$）；对二次式精确、
  非均匀网格上对线性精确（测试）；$n<3$ → `None`。
- `volume_int_dv`（"`expro` 的 `volint`——体积中的梯形"）：$P_i=P_{i-1}+\tfrac12(f_i+f_{i-1})(V_i-V_{i-1})$，可带权重；
  PDE 网格密，用它。

〔目标通量〕$t_0=0$（"由构造"），$t_i=P_i/(V'_iQ_{GB,i})$——TGYRO 的 `eflux_*_target`。〔TGYRO 锚〕〔实现〕
treg01 的 `out.tgyro.evo_te/evo_ti` 五点目标（$0,\,0.1740,\,0.6707,\,2.843,\,12.63$ 与 $0,\,0.3530,\,1.1727,\,3.925,\,13.62$）
以 $10^{-6}$ 相对再现——"本 crate 中第一个对仓外代码的数字作检验的例子"。

〔功率簿记〕〔实现〕`heating_powers`（"`tgyro_source.f90` 的功率簿记"，`LOC_SCENARIO`）：1 静态交换不动；2 动态交换
把 $\Delta=p_{\rm exch}-p_{\rm exch,in}+p_{\rm expwd}$ 从电子搬到离子；3 反应堆另加 $\alpha$（缺 $\alpha$ → `AlphaHeatingMissing`，
"拒绝而非伪造"）。未在公开入口上导出。

(phys10-limits)=
# 适用域与失效条件 (Applicability & Failure Modes)

1. **ADAS 拟合域** $T_e\in[0.05,50]$ keV，域外钳制；**日冕平衡**——边界非日冕态用 {ref}`phys11-intro` 的 Mavrin 2017。
2. **未知物种辐射为零**（上游行为）——调用方须核对 `adas_id`。
3. **brem/line 拆分不物理**，只用总量。
4. **同步辐射** $\propto B^4$，须喂环向场而非 $B_{\rm unit}$；壁反射 0.8 是给定常数。
5. **Spitzer 无捕获修正**；$0.51$ 在 $Z\ne1$ 时是近似（Spitzer–Härm 的 $\gamma(Z)$ 随 $Z$ 变）。
6. **交换只计热离子**。
7. **积分器要按网格选**：稀疏通量匹配网格用二次求积，密 PDE 网格用体积梯形；混用会与 TGYRO 对不上。
8. **CGS/eV**：SI 调用方须经 `assembly.*_si` 包装；`pext/dpext` 曾被误读为 CGS（{ref}`phys04-mapping-units`）。

(phys10-verify)=
# 验证锚点 (Verification Anchors)

:::{table} 源项模块的锚点。
:name: tbl-p10-verify
:align: left

| 锚点 | 参照 | 判据 |
| :--- | :--- | :--- |
| 目标通量五点 | TGYRO treg01 `evo_te/evo_ti` | $10^{-6}$ 相对 |
| ADAS 表完整性 | 22 物种 / 20 曲线；H = D = T | 测试 |
| W ≫ D（1 keV）；C/D $>10$（2 keV） | 量级 | 测试 |
| 冷却曲线钳制 | — | 域外等于边界值 |
| 二次求积 | 二次式 / 非均匀线性 | 精确 |
| $\sigma_{\rm Sauter}\times\eta_\parallel$ | 自身（保真度章） | $\approx1$（0.998） |
| 场景 2 / 3 簿记 | — | 搬运守恒；缺 α 拒绝 |
:::

(phys10-asbuilt)=
# 与 fyo 的对应 (Correspondence to fyo)

:::{table} 各项功率源与汇，以及它们所落的 fyo 数据集。
:name: tbl-p10-asbuilt
:align: left

| 内容 | 结果落在 fyo 的哪里 | Python 入口 |
| :--- | :--- | :--- |
| ADAS 冷却曲线与杂质辐射 | `fyo:core_sources`：辐射汇（电子能量） | `assembly.radiation_si` |
| 同步辐射 | 同上 | `assembly.sync_si` |
| 电子—离子交换 | `fyo:core_sources`：两温度之间的交换项 | `assembly.exchange_si` |
| Spitzer 电阻率与欧姆加热 | `fyo:core_profiles` 的 $\eta$；`fyo:core_sources` 的欧姆源 | `assembly.spitzer_eta`、`ohmic_si` |
| 准中性 | `fyo:core_profiles`：由离子组分定出的 $n_e$ | `assembly`（芯部合步内） |
| 体积分与目标通量 | —（把源项化成通量的积分口径） | `SourceSet.volume_integral` |
| 功率簿记 | `fyo:summary`：各道功率的合账 | —（随上列各项一起给出） |
:::

(phys10-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（实现引）〕Open ADAS {cite}`openadas`；Pütterich 等 {cite}`puetterich2019cooling`；NRL 手册
{cite}`huba2013nrl`；Spitzer–Härm {cite}`spitzer1953transport`；Trubnikov {cite}`trubnikov1972synchrotron`。
〔编者对应〕电子—离子等分率 {cite}`spitzer1962physics`；壁反射因子 {cite}`rosenbluth1970synchrotron`；TGYRO
{cite}`candy2009tgyro`。标 〔凭记忆〕 者为编者补出的对应，条目字段的核验状态见 `references.bib` 的 `note`（{ref}`phys00-evidence`）。

〔转引〕`tgyro_source.f90`、`tgyro_rad.f90`（`adas21`, `rad_ion_adas`）、`tgyro_volume_int.f90`、`expro` `volint`
（GACODE 5efddfdf1，Apache-2.0）。

〔实现未注出处〕$c_{\rm exch}$ 的写法；同步辐射的 60 与 $\Phi$ 形式；二次求积系数；`heating_powers` 的搬运规则。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
