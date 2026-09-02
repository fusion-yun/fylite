---
title: 物理与数值 · 源项、辐射与体积分 (Physics & Numerics — Sources, Radiation and Volume Integrals)
subtitle: sources.rs —— ADAS 冷却曲线与辐射、同步辐射、电子—离子交换、Spitzer 电阻率与欧姆加热、两种积分器、目标通量与功率账
---

(phys10-intro)=
# 引言：输运方程右端的账 (Introduction)

〔范围〕本章详述 `sources.rs`（约 750 行）：`tgyro_source.f90` / `tgyro_rad.f90` / `tgyro_volume_int.f90` 的
白箱移植（GACODE，Apache-2.0，仓根 `NOTICE`），**全程 CGS、eV**（"与 `mapping` 和 TGYRO 自身一致"）。
内容：ADAS 冷却曲线的 Chebyshev 拟合与线辐射、NRL 近似轫致辐射、Trubnikov 同步辐射、电子—离子能量交换、
Spitzer 电阻率与欧姆加热、准中性闭合、两种体积积分器、目标通量、TGYRO 的功率簿记。$\alpha$ 加热**不在此**
（"GACODE 的回归例不含 D-T"；见 {ref}`phys09-alpha`）。非日冕辐射（Mavrin 2017）在 `edge.rs`（{ref}`phys11-intro`），
源码强调"**不是** `adas_cooling` 的另一种拼写——那是日冕平衡冷却率"。

〔出处姿态〕〔源码〕本模块对多数公式只给上游文件名；一手文献在源码中出现的有 Open ADAS 与 Pütterich 2019、
NRL 手册、Spitzer–Härm 1953、Trubnikov 1972。其余由编者对应，标核验状态。

(phys10-radiation)=
# 辐射 (Radiation)

(phys10-radiation-adas)=
## ADAS 冷却曲线与线辐射 (ADAS Cooling Curves)

〔源码〕`ADAS21`：22 个物种（H = D = T 同一曲线，20 条不同曲线）的 12 项 Chebyshev 拟合，$T_e\in[0.05,50]$ keV：

$$
x=\mathrm{clamp}\!\Big(-1+2\frac{\ln(T_e/T_{\min})}{\ln(T_{\max}/T_{\min})},-1,1\Big),\qquad
L_z(T_e)=\exp\!\Big(\sum_{n=0}^{11}c_n\cos(n\arccos x)\Big)\ [\text{erg cm}^3\text{ s}^{-1}]
$$ (eq-p10-adas)

域外取**边界值**而非外推（测试 `the_cooling_curve_clamps_rather_than_extrapolates`）。系数取自 `tgyro_rad.f90`
的 `adas21`；源码注来源 "Open ADAS (https://open.adas.ac.uk); T. Puetterich et al 2019 Nucl. Fusion 59 056013"
{cite}`openadas,puetterich2019cooling`。〔已确立〕$T_n(x)=\cos(n\arccos x)$ 是第一类 Chebyshev 多项式。
未知物种 `adas_id` 返回 `None` ⇒ **线辐射为零**（"上游行为，真正的陷阱"）。

〔线辐射与轫致辐射的拆分〕〔源码〕`rad_ion`：

$$
P_{\rm brem}=\sum_i10^7\cdot1.69\times10^{-32}\,n_en_iZ_i^2\sqrt{T_e[\text{eV}]},\qquad
P_{\rm total}=\sum_in_en_iL_z^{(i)},\qquad P_{\rm line}=P_{\rm total}-P_{\rm brem}
$$ (eq-p10-brem)

"拆分**不物理**：`brem` 是 NRL 近似式，`line` 是 ADAS 总量减去它的剩余——只有**和**是 ADAS 值。"
〔出处〕$1.69\times10^{-32}n_en_iZ^2T_e^{1/2}$ W/cm³ 是 NRL 手册的轫致辐射功率密度 {cite}`huba2019nrl`（源码注 "NRL"）。

(phys10-radiation-sync)=
## 同步辐射 (Synchrotron Radiation)

〔源码〕`rad_sync`（"Trubnikov, JETP Lett. 16 (1972) 25"）{cite}`trubnikov1972synchrotron`，$B$ 以 Gauss、
$a$ 以 cm，反射系数 $r=0.8$（`SYNC_REFLECTION`，"Rosenbluth 壁反射系数"）：

$$
g=\frac{kT_e}{m_ec^2},\qquad
\Phi=60\,g^{3/2}\sqrt{\frac{(1-r)\big(1+\frac{1}{A\sqrt g}\big)}{a\,\omega_{pe}^2/(c\,\omega_{ce})}},\qquad
P_{\rm sync}=\frac{m_e}{3\pi c}\,g\,(\omega_{pe}\omega_{ce})^2\,\Phi
$$ (eq-p10-sync)

"上游喂它 `expro_bt0`——磁面上的**环向**场而非 $B_{\rm unit}$……此项 $\propto B^4$"。〔未核验〕常数 60 与 $\Phi$ 的形式
只归于 Trubnikov 1972；壁反射的处理与 Rosenbluth 1970 的 $(1-r)$ 因子同型 {cite}`rosenbluth1970synchrotron`〔凭记忆〕，
源码未给文献。

(phys10-exchange)=
# 电子—离子能量交换 (Electron–Ion Energy Exchange)

$$
P_{ei}=\tfrac32\,\nu_{\rm exch}\,n_e\,k\,(T_e-T_i)\ [\text{erg cm}^{-3}\text{s}^{-1}]\quad(\text{正向离子})
$$ (eq-p10-exch)

$\nu_{\rm exch}$ 见 {eq}`eq-p04-exch`（`mapping::exchange_rate`；只有**热**离子计入）。〔出处〕经典电子—离子
等分率 {cite}`spitzer1962physics,huba2019nrl`；源码未注（TGYRO 移植）。SI 面：`assembly.exchange_si` × 0.1。

(phys10-resistivity)=
# Spitzer 电阻率、欧姆加热与准中性 (Resistivity, Ohmic Heating, Quasi-Neutrality)

$$
\eta_\perp=1.03\times10^{-4}\,Z\,\ln\Lambda\,T_e[\text{eV}]^{-3/2}\ \Omega\,\text{m},\qquad
\eta_\parallel=0.51\,\eta_\perp,\qquad P_\Omega=\eta\,(j_\parallel\cdot j_\parallel)\ [\text{W/m}^3]
$$ (eq-p10-spitzer)

〔出处〕〔源码〕"NRL 手册系数如印：$\eta_\perp=1.03\times10^{-2}Z\ln\Lambda T_e^{-1.5}$ Ω·cm"{cite}`huba2019nrl`；
"NRL 手册；Spitzer & Härm 1953，$\gamma(Z=1)=0.51$" {cite}`spitzer1953transport`。"**0.51 在所有 $Z$ 上按 $Z=1$ 施加**"；
捕获粒子修正**不**折入（"经新经典模型达到的有据可查的精化"，{ref}`phys07-intro`）。
〔历史〕〔源码 / 保真度章〕该函数曾在此名下返回**垂直**值（T-A18 前），使欧姆功率高约一倍；订正后
$\sigma_{\rm Sauter}\times\eta_\parallel\approx1$（实测 0.998）、$\eta_\parallel/\eta_\perp\equiv0.51$ 到 $10^{-15}$。
准中性 $n_e=\sum_sz_sn_s$（`quasi_neutral_ne`）。

(phys10-integrals)=
# 两种积分器与目标通量 (Two Integrators and the Target Flux)

〔源码〕"**两个积分器，不是一个**"：

- `volume_int`（"上游的 `tgyro_volume_int`——**二次插值求积**，不是梯形"）：$P(r)=\int_0^rV'(x)s(x)\dd x$ 在 TGYRO 自己的
  5–10 点通量匹配网格上，每段用三节点二次插值的精确积分（首段用 $(0,1,2)$，其后 $(i-2,i-1,i)$）；对二次式精确、
  非均匀网格上对线性精确（测试）；$n<3$ → `None`。
- `volume_int_dv`（"`expro` 的 `volint`——**体积中的梯形**"）：$P_i=P_{i-1}+\tfrac12(f_i+f_{i-1})(V_i-V_{i-1})$，可带权重；
  PDE 网格密，用它。

〔目标通量〕$t_0=0$（"**由构造**"），$t_i=P_i/(V'_iQ_{GB,i})$——TGYRO 的 `eflux_*_target`。〔TGYRO 锚〕〔源码〕
treg01 的 `out.tgyro.evo_te/evo_ti` 五点目标（$0,\,0.1740,\,0.6707,\,2.843,\,12.63$ 与 $0,\,0.3530,\,1.1727,\,3.925,\,13.62$）
以 $10^{-6}$ 相对再现——"本 crate 中第一个对仓外代码的数字作检验的例子"。

〔功率簿记〕〔源码〕`heating_powers`（"`tgyro_source.f90` 的功率簿记"，`LOC_SCENARIO`）：1 静态交换不动；2 动态交换
把 $\Delta=p_{\rm exch}-p_{\rm exch,in}+p_{\rm expwd}$ 从电子搬到离子；3 反应堆另加 $\alpha$（缺 $\alpha$ → `AlphaHeatingMissing`，
"拒绝而非伪造"）。未经 C-ABI 导出。

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
# 与内核的对应 (Correspondence to the Kernel)

:::{table} 源项内容与内核函数、C-ABI、Python 入口（2026-09-02 快照）。
:name: tbl-p10-asbuilt
:align: left

| 内容 | 内核函数（`sources.rs`） | C-ABI（`fylite_rs_*`） | Python |
| :--- | :--- | :--- | :--- |
| ADAS 冷却 / 辐射 | `adas_id`, `adas_cooling`, `rad_ion` | `adas_id`, `adas_species_count/_name`, `adas_cooling`, `rad_ion` | `assembly.radiation_si` |
| 同步辐射 | `rad_sync` | `rad_sync` | `assembly.sync_si` |
| 交换 | `exchange_power` | `exchange_power` | `assembly.exchange_si` |
| 电阻率 / 欧姆 | `spitzer_eta_perp/_par`, `ohmic_power` | `spitzer_eta`（并行）, `spitzer_eta_perp`, `ohmic_power` | `assembly.spitzer_eta`, `ohmic_si` |
| 准中性 | `quasi_neutral_ne` | `quasi_neutral_ne` | `CoreMarch` |
| 积分器 / 目标通量 | `volume_int`, `volume_int_dv`, `target_flux` | `volume_int`（mode 0/1/2）, `target_flux` | `SourceSet.volume_integral` |
| 功率簿记 | `heating_powers` | **未导出** | — |
:::

(phys10-sources)=
# 来源与出处 (Sources & Attribution)

〔一手文献（源码引）〕Open ADAS {cite}`openadas`；Pütterich 等 {cite}`puetterich2019cooling`；NRL 手册
{cite}`huba2019nrl`；Spitzer–Härm {cite}`spitzer1953transport`；Trubnikov {cite}`trubnikov1972synchrotron`。
〔编者对应〕电子—离子等分率 {cite}`spitzer1962physics`；壁反射因子 {cite}`rosenbluth1970synchrotron`；TGYRO
{cite}`candy2009tgyro`。标 〔凭记忆〕 者字段待核验。

〔转引〕`tgyro_source.f90`、`tgyro_rad.f90`（`adas21`, `rad_ion_adas`）、`tgyro_volume_int.f90`、`expro` `volint`
（GACODE 5efddfdf1，Apache-2.0）。

〔源码未注出处〕$c_{\rm exch}$ 的写法；同步辐射的 60 与 $\Phi$ 形式；二次求积系数；`heating_powers` 的搬运规则。

# 参考来源 (References)

```{bibliography}
:filter: docname in docnames
```
