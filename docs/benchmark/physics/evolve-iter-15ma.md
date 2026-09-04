# ITER 15 MA 感应燃烧：定律、定义，加上这一炮该落在哪

- 算例 (case)：`docs/examples/evolve/evolve-iter-15ma`
- 判决 (verdict)：**通过**（pass）
- 产出 (datasets)：`core_profiles`, `core_transport`, `equilibrium`, `summary`
- 记录 (record)：`run/20260904T130427Z-evolve`
- 日期：2026-09-04

> 本批现跑了这个算例（数据层 JSON 门 + 内核）

## 逐条

| 检查 | 类 | 判决 | 量到 | 容差 | 判据来路 |
| :--- | :--- | :--- | ---: | ---: | :--- |
| `finite` | 定律 | 通过 | 0 | 0 | machine_precision |
| `positive-temperature` | 定律 | 通过 | 3000 | 0 | machine_precision |
| `positive-density` | 定律 | 通过 | 7e+19 | 0 | machine_precision |
| `grad-shafranov` | 定律 | 未评估 | — | — | — |
| `grid-monotone` | 定义 | 通过 | 0 | 0 | machine_precision |
| `psi-endpoints` | 定义 | 未评估 | — | — | — |
| `volume-monotone` | 定义 | 通过 | 0 | 0 | machine_precision |
| `boundary-closed` | 定义 | 通过 | 1.174 | 1.5 | measured_band |
| `pressure-consistency` | 定义 | 未评估 | — | — | — |
| `energy-balance` | 定义 | 未评估 | — | — | — |
| `greenwald-definition` | 定义 | 未评估 | — | — | — |
| `beta-normalized-definition` | 定义 | 未评估 | — | — | — |
| `declared-bounds` | 期望 | 通过 | 0 | 0 | reference_stated |

## 每条说了什么

### `finite` — 产出的每个数都是有限的

- 判据：`∀x ∈ datasets: isfinite(x)`
- 结论：通过——3757 个数值全部有限
- 假设：NaN / Inf 不是一个物理态，也不是「还没算」——后者应当缺席而不是写成 NaN

### `positive-temperature` — 绝对温度为正

- 判据：`min(T_e, T_i) > 0`
- 结论：通过——最小值 3000（CORE_PROFILES/te）；读了 CORE_PROFILES/te, CORE_PROFILES/ti, SUMMARY/te_axis, SUMMARY/ti_axis

### `positive-density` — 粒子数密度为正

- 判据：`min(n_e, n_i) > 0`
- 结论：通过——最小值 7e+19（CORE_PROFILES/ne）；读了 CORE_PROFILES/ne

### `grad-shafranov` — 二维平衡满足 Grad–Shafranov 方程

- 判据：`Δ*ψ = −μ₀R²·dp/dψ − f·df/dψ，Δ* = ∂_RR − (1/R)∂_R + ∂_ZZ`
- 结论：未评估——缺二维 ψ 或它的源函数（p′ / ff′），这条评不了
- 假设：二阶中心差分，残差按 ‖Δ*ψ‖ 与 ‖RHS‖ 的均方根归一——网格越粗，截断误差越大
- 假设：只在边界内、离网格边一格以上的点上取
- 假设：ψ 每弧度、`Δ*ψ = −μ₀R²p′ − ff′`；相反符号支更小时给注记而不是判负
- 读不到：EQUILIBRIUM/grid_z, EQUILIBRIUM/psi_1d, EQUILIBRIUM/dpressure_dpsi, EQUILIBRIUM/f_df_dpsi

### `grid-monotone` — 网格与时间轴单调，归一化网格在 [0, 1]

- 判据：`diff(x) > 0；0 ≤ ρ_norm, ψ_norm ≤ 1`
- 结论：通过——1 条轴单调：SUMMARY/time

### `psi-endpoints` — 一维 ψ 的两端就是 ψ_axis 与 ψ_boundary

- 判据：`|ψ₁ᴰ[0] − ψ_axis| / |ψ_bnd − ψ_axis| ≤ tol，另一端同`
- 结论：未评估——缺一维 ψ 或它的两个全局端点
- 读不到：EQUILIBRIUM/psi_1d, EQUILIBRIUM/psi_axis, EQUILIBRIUM/psi_boundary

### `volume-monotone` — 体积随 ρ 单调增，V′ 在轴外为正

- 判据：`diff(V) ≥ 0；V′[1:] > 0`
- 结论：通过——体积单调、V′ 在轴外为正
- 假设：轴上 V′ = 0 是解析的，所以只看内部点

### `boundary-closed` — 最外闭合磁面闭合，且在限制器内

- 判据：`|X[0] − X[-1]| / median|ΔX| ≤ tol（tol = 1.5 个采样步）；越出限制器的深度 ≤ limiter_tolerance × a`
- 结论：通过——首末点间距 0.1932 m = 1.17 个采样步（步长中位数 0.1645 m，小半径 2 m）；没有限制器外形，只量了闭合性
- 假设：闭合按采样步量而不按小半径：等值线是采出来的，首末差一个采样步之内就是闭合的
- 假设：越界按距离量：正落在限制器上的点是「贴着」，不是越界（射线法对这种点是随机的）
- 假设：没有限制器时只量闭合性，并在结论里说明

### `pressure-consistency` — 平衡压强对得上剖面的动理压强

- 判据：`max|p_eq − e(n_e T_e + n_i T_i)| / max|p| ≤ tol`
- 结论：未评估——缺平衡压强或电子剖面
- 假设：热压强、单一等效离子、无快离子压强；带快粒子的算例会有正的口径差
- 假设：两侧网格不同时按 ψ_norm 插值，缺共同横坐标就不评
- 读不到：EQUILIBRIUM/pressure, CORE_PROFILES/ne, CORE_PROFILES/te

### `energy-balance` — 能量约束时间的定义式逐时刻成立

- 判据：`|W_th/τ_E + dW_th/dt − P_heat| / |P_heat| ≤ tol（中位数）`
- 结论：未评估——缺热能或能量约束时间
- 假设：P_heat 取哪几项是约定：缺省 p_ohm + p_aux + p_alpha − p_rad，可由算例声明
- 读不到：SUMMARY/w_th, SUMMARY/tau_e

### `greenwald-definition` — 记下的 Greenwald 分数对得上定义

- 判据：`f_G = n̄_e / n_G，n_G[m⁻³] = 10²⁰·I_p[MA]/(π a²[m²])`
- 结论：未评估——缺记下的 Greenwald 分数、I_p 或密度剖面
- 假设：n̄_e 取体积平均；记录若用线平均会有几个百分点的口径差
- 假设：a 取边界外形的 (R_max − R_min)/2
- 读不到：SUMMARY/greenwald, SUMMARY/ip, CORE_PROFILES/ne

### `beta-normalized-definition` — 记下的 β_N 对得上定义

- 判据：`β_N = 100·β_t·a·B₀/I_p[MA]，β_t = 2μ₀⟨p⟩/B₀²`
- 结论：未评估——缺 β_N、I_p、B₀ 或压强剖面
- 假设：⟨p⟩ 是平衡压强的体积平均（热压强口径）
- 读不到：SUMMARY/beta_n, SUMMARY/ip, EQUILIBRIUM/b0, EQUILIBRIUM/pressure

### `declared-bounds` — 算例声明的运行界（β_N、f_G、q95…）

- 判据：`min/max(quantity) 落在算例声明的 [min, max] 内`
- 结论：通过——SUMMARY/beta_n ∈ [0.9483, 1.767]（界：）
- 假设：运行限不是定律，是这个场景的判据，所以由算例带
- 注记：2 个声明的量读不到：SUMMARY/q95, SUMMARY/greenwald
- 读不到：SUMMARY/q95, SUMMARY/greenwald

---

本报告由 `tools/benchmark-run.py` 渲染（判据册 `fylite.engine.physics`）；机器可读的一份在同名 `.jsonld` 里。
