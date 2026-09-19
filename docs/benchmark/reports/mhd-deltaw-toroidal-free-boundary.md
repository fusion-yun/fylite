---
title: "mhd-deltaw-toroidal-free-boundary"
---

# 环几何真空标量势与无壁 V5：**四行都在最近码 1.7 % 内——真空走基本解法，靠柱锚判官**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-toroidal-free-boundary.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-toroidal-free-boundary.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：环几何真空标量势与无壁 V5：**四行都在最近码 1.7 % 内——真空走基本解法，靠柱锚判官**
- **参考**：Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I
- **验的需求**：`FR-EQ-030`
- **跑在内核**：`sha256:6a3256a58b247645…`（新鲜度 **current**）
- **记录版本**：1.5　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：环 Green 函数 Q_{n−1/2} 闭式 + 一步递推；外 NtD 用基本解法（MFS）；边界 Neumann 数据走 Q·∇Ψ = B·∇(ξ·∇Ψ)

**参考**：Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I

> 五码中的三码（KERNER · PEST · ERATO）对 Solov'ev 平衡给的 $-\Omega^2=-\omega^2\rho q(s)^2R^2/B_0^2$。★**落在带里不证明算对了，只证明没有明显算错**：带宽是码间分歧，含数值误差也含模型差（三码的坐标、离散与真空处理各不相同，见原文 §3）。

**口径与适用域**：

> Solov'ev（ε = 1/3、E = 2）、无壁（Λ = ∞）、γ = 5/3、ρ 常数；n = 1, 2（n >= 3 拒绝）。★V5 行与柱锚的门在 `cargo test --release` 下跑。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-toroidal-free-boundary-headroom.svg
:alt: mhd-deltaw-toroidal-free-boundary 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| $Q_{\pm1/2}$ 闭式自证（对直接 φ 求积） | — | reference_self_reported | 闭式对直接求积最劣 3.6e-11（n = 0, 1, 2 × ζ = 1.001 / 1.3 / 5）；n >= 3 按名拒绝 | **成立** |
| 柱极限 NtD 锚 $K_m(\kappa a)/(\kappa K_m')$ | 0.01 | reference_self_reported | 细环 a/R = 0.02：最劣 7.5e-5（与源点位置、分辨率无关） | **成立** |
| 自由边界柱锚随 ε 收敛 | — | reference_self_reported | 每减半差缩约 4 倍（二阶；上游记的是一阶 11.8 % → 4.2 % → 1.9 %） | **成立** |
| V5 无壁四行（距最近码，容差 15 %） | 0.15 | reference_self_reported | 160 单元、m ∈ [−8, 12]；320 单元、m ∈ [−12, 16] 时 0.764 · 0.680 · 1.381 · 1.071（都略升，仍在码带内） | **成立** |
| 两支分离：同位形上有壁不比无壁更不稳 | — | reference_self_reported | 四行的定形边界增长率都不大于无壁（0.025 / 0 / 0.165 / 0.051 对 0.758 / 0.673 / 1.377 / 1.065） | **成立** |

**★细环 a/R = 0.02：最劣 7.5e-5（与源点位置、分辨率无关）**

- ★★**真空这一步没照 SRS 走**：SRS 记的是 Kress 分裂边界元（对角系数须恰为 $-\ln D^2/(4\pi\sqrt{XX'})$，写错即静默的一阶污染）。本仓用**基本解法**：源点放在等离子体内一张磁面上，解在真空里逐点满足方程与无穷远衰减，**没有奇异积分可写错**。代价与验收是同一条柱锚——它在上游抓住过 Kress 系数错写，在这里同样是 MFS 精度的判官。
- ★★**MFS 的条件数，照实记**：源点数随等离子体极向网格加倍到 128 个时，自由边界「增长率」跳到 1300–2500、反 Hermite 部分 3e-3。现在真空边界点与源点数**固定**（128 / 64），与等离子体网格脱钩；极向 128 与 256 点给逐位相同的结果。

**★★0.758（+1.0 %）· 0.673（−1.0 %）· 1.377（−1.7 %）· 1.065（−0.5 %）**

- ★真空块的反 Hermite 部分 1e-5–1e-4（等离子体部分 1e-16）：MFS 的 NtD 不精确对称，装配后取 Hermite 部分。

## 不可比的部分

- ★★**判决成立**：五格全过；真空的解法与 SRS 所记不同（MFS 而非 Kress 边界元），判据要的柱锚照样过、且到 7.5e-5。
- ★本条是**对拍**：五码带是码间分歧。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.5　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-030` 判**成立**（对拍）。环 Green 函数 Q_{n−1/2} 闭式 + 一步递推（3.6e-11）；外 NtD 走基本解法，柱锚 7.5e-5；无壁四行 0.758 / 0.673 / 1.377 / 1.065，距最近码 ≤ 1.7 %。★MFS 源点数随网格加倍时条件数爆（增长率跳到 2000），已与等离子体网格脱钩。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.4 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:6a3256a58b2476456c9a1e466d4539c81f93dd5279b1225f1fbed2a4da9a4690`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/toroidal_free_boundary_v5.json`    `sha256:90af0ff43de0821d90573193ba0765414b6492c66b5ea4688a76135c791b29a9`    Q 函数、NtD 柱锚、自由边界柱锚、四行、两支、MFS 条件数

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests30::the_toroidal_functions_match_their_integral` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests30::the_exterior_map_has_the_cylinder_limit` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests30::the_free_boundary_torus_tends_to_the_cylinder` —— 第三格（--release）
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests30::table_i_no_wall_rows_land_within_the_band_and_the_wall_never_hurts` —— 第四、五格（--release）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
