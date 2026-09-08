# ITER 15 MA 的 0-D 功率平衡：τ_E 的定义式站不站得住

- 算例 (case)：`docs/examples/zerod/zerod-iter-15ma`
- 判决 (verdict)：**未通过**（fail）
- 产出 (datasets)：`core_profiles`, `summary`
- 记录 (record)：`run/20260904T130427Z-zerod`
- 日期：2026-09-04

> 本批现跑了这个算例（数据层 JSON 门 + 内核）

## 逐条

| 检查 | 类 | 判决 | 量到 | 容差 | 判据来路 |
| :--- | :--- | :--- | ---: | ---: | :--- |
| `finite` | 定律 | 未通过 | 1 | 0 | machine_precision |
| `positive-temperature` | 定律 | 通过 | 200 | 0 | machine_precision |
| `positive-density` | 定律 | 通过 | 2e+18 | 0 | machine_precision |
| `grad-shafranov` | 定律 | 未评估 | — | — | — |
| `grid-monotone` | 定义 | 通过 | 0 | 0 | machine_precision |
| `psi-endpoints` | 定义 | 未评估 | — | — | — |
| `volume-monotone` | 定义 | 未评估 | — | — | — |
| `boundary-closed` | 定义 | 未评估 | — | — | — |
| `pressure-consistency` | 定义 | 未评估 | — | — | — |
| `energy-balance` | 定义 | 未评估 | — | — | — |
| `greenwald-definition` | 定义 | 未评估 | — | — | — |
| `beta-normalized-definition` | 定义 | 未评估 | — | — | — |
| `declared-bounds` | 期望 | 未评估 | — | — | — |

## 每条说了什么

### `finite` — 产出的每个数都是有限的

- 判据：`∀x ∈ datasets: isfinite(x)`
- 结论：未通过——1 处非有限：summary/global_quantities/fusion_gain/value (60/201)
- 假设：NaN / Inf 不是一个物理态，也不是「还没算」——后者应当缺席而不是写成 NaN

### `positive-temperature` — 绝对温度为正

- 判据：`min(T_e, T_i) > 0`
- 结论：通过——最小值 200（SUMMARY/te_axis）；读了 SUMMARY/te_axis

### `positive-density` — 粒子数密度为正

- 判据：`min(n_e, n_i) > 0`
- 结论：通过——最小值 2e+18（SUMMARY/ne_axis）；读了 SUMMARY/ne_axis

### `grad-shafranov` — 二维平衡满足 Grad–Shafranov 方程

- 判据：`Δ*ψ = −μ₀R²·dp/dψ − f·df/dψ，Δ* = ∂_RR − (1/R)∂_R + ∂_ZZ`
- 结论：未评估——缺二维 ψ 或它的源函数（p′ / ff′），这条评不了
- 假设：二阶中心差分，残差按 ‖Δ*ψ‖ 与 ‖RHS‖ 的均方根归一——网格越粗，截断误差越大
- 假设：只在边界内、离网格边一格以上的点上取
- 假设：ψ 每弧度、`Δ*ψ = −μ₀R²p′ − ff′`；相反符号支更小时给注记而不是判负
- 读不到：equilibrium (document), equilibrium (document), equilibrium (document), equilibrium (document)

### `grid-monotone` — 网格与时间轴单调，归一化网格在 [0, 1]

- 判据：`diff(x) > 0；0 ≤ ρ_norm, ψ_norm ≤ 1`
- 结论：通过——2 条轴单调：CORE_PROFILES/time, SUMMARY/time

### `psi-endpoints` — 一维 ψ 的两端就是 ψ_axis 与 ψ_boundary

- 判据：`|ψ₁ᴰ[0] − ψ_axis| / |ψ_bnd − ψ_axis| ≤ tol，另一端同`
- 结论：未评估——缺一维 ψ 或它的两个全局端点
- 读不到：EQUILIBRIUM/psi_1d, EQUILIBRIUM/psi_axis, EQUILIBRIUM/psi_boundary

### `volume-monotone` — 体积随 ρ 单调增，V′ 在轴外为正

- 判据：`diff(V) ≥ 0；V′[1:] > 0`
- 结论：未评估——梯子上没有体积
- 假设：轴上 V′ = 0 是解析的，所以只看内部点
- 读不到：LADDER/volume, LADDER/vprime

### `boundary-closed` — 最外闭合磁面闭合，且在限制器内

- 判据：`|X[0] − X[-1]| / median|ΔX| ≤ tol（tol = 1.5 个采样步）；越出限制器的深度 ≤ limiter_tolerance × a`
- 结论：未评估——产出里没有边界外形
- 假设：闭合按采样步量而不按小半径：等值线是采出来的，首末差一个采样步之内就是闭合的
- 假设：越界按距离量：正落在限制器上的点是「贴着」，不是越界（射线法对这种点是随机的）
- 假设：没有限制器时只量闭合性，并在结论里说明
- 读不到：EQUILIBRIUM/boundary_r, EQUILIBRIUM/boundary_z

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
- 结论：未评估——声明的量一个也读不到：SUMMARY/greenwald, SUMMARY/beta_n
- 假设：运行限不是定律，是这个场景的判据，所以由算例带
- 读不到：SUMMARY/greenwald, SUMMARY/beta_n

## 那一条未通过：两条各自成立的规矩撞在一起〔2026-09-08 归因〕

`finite` 报的一处是 `summary/global_quantities/fusion_gain/value`，**60/201 个点非有限**。
逐点看，NaN 落在 **t ∈ [0, 0.95] 与 [8.05, 10.0] s**，有限值恰好落在 **[1.00, 8.00] s**
——而算例声明的 `t_on = 1` · `t_off = 8`。**NaN 的位置与外加热窗口逐点对齐**，
不是数值发散，是 $Q = P_\text{fus}/P_\text{aux}$ 在 $P_\text{aux}=0$ 处没有定义。

两侧都是**明写的裁定**，各自都对：

| 谁 | 写了什么 | 理由 |
| :--- | :--- | :--- |
| 内核 `zerod.rs:328` | `out.q[k] = if p_inj[k] > 0.0 { pf / p_inj[k] } else { f64::NAN }` | 原注：*Q is undefined without injected power; NaN says so, **0 would lie*** |
| 判据册 `physics.py` | `finite` 是**定律**类 | 原注：*每一个产出的数组都得是有限的。**NaN 不是一个状态*** |

★所以这不是缺陷，是**两条规矩的交界处没有裁定**：产出方用 NaN 表达「此处无定义」，
而判据册规定产出里不许有 NaN。谁让一步，是一次口径裁定，不是改错。

三条路，各自的代价写在这里，**本册不替谁选**：

1. **法不可豁免，改产出**——`fusion_gain` 只在窗口内给值。代价：DD 的 `FLT_1D`
   **没有逐点缺席**的表示法，只能整支给或整支不给；给整支就得填一个数，而填什么都在说谎。
2. **改定义**——$Q = P_\text{fus}/(P_\text{aux}+P_\Omega)$，处处有限（欧姆功率不为零）。
   代价：那不是 ITER 语境里 $Q$ 的通行定义，换了之后本册与外部对拍的 $Q$ 不再是同一个量。
3. **给定律一个「已声明无定义域」的机制**——算例声明「`fusion_gain` 在 `p_aux == 0` 处无定义」，
   `finite` 据此放行。代价：定律从此可被算例声明豁免，而**定律的意义正在于不可豁免**；
   一旦开这个口子，下一个声明会是别的量。

〔倾向〕第 3 条的口子最贵、第 2 条改的是物理口径，**第 1 条最接近本仓已有的做法**
（「宁可拒绝，不给假数」）——但它要先回答「一支不能逐点缺席的数组，如何表达一段无定义」。
这一问 `FYL-DESIGN-20` M-6 已经在另一处遇到过（未评估 ≠ 通过），可一并裁。

---

本报告由 `tools/benchmark-run.py` 渲染（判据册 `fylite.engine.physics`）；机器可读的一份在同名 `.jsonld` 里。
