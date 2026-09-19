---
title: "mhd-deltaw-toroidal-fixed-boundary"
---

# 环几何全 δW 定形边界：**Table I 两行落进五码带，柱极限对 F2 柱码差 1 %**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-toroidal-fixed-boundary.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-toroidal-fixed-boundary.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：环几何全 δW 定形边界：**Table I 两行落进五码带，柱极限对 F2 柱码差 1 %**
- **参考**：Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I
- **验的需求**：`FR-EQ-029`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.10　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：Kerner 坐标解析映射、谱直场线角、ξ^ρ 线性元 × Y/Z 逐单元常值 × Fourier，Newcomb 一般式，中点减缩积分

**参考**：Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I

> 五码中的三码（KERNER · PEST · ERATO）对 Solov'ev 平衡给的 $-\Omega^2=-\omega^2\rho q(s)^2R^2/B_0^2$。★**落在带里不证明算对了，只证明没有明显算错**：带宽是码间分歧，含数值误差也含模型差（三码的坐标、离散与真空处理各不相同，见原文 §3）。

**口径与适用域**：

> Solov'ev 平衡（Chance 1978 Eq. 3–5）、定形边界（Λ = 1）、γ = 5/3、ρ 常数（与上游核准的口径同）。★V5 两行的门在 `cargo test --release` 下跑（debug 下标记忽略：重）。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-toroidal-fixed-boundary-headroom.svg
:alt: mhd-deltaw-toroidal-fixed-boundary 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 平衡转录三重自证（GS 解析恒等 · $q(0)$ 回收 · $q(a)$ 对印值 0.5224） | — | reference_self_reported | Kerner 坐标下映射解析：$X=(1+2\varepsilon\rho\cos\vartheta)^{1/2}$、$D=E\varepsilon^2\rho/X^2$，于是 $q(\rho)=q_0\langle(1+2\varepsilon\rho\cos\vartheta)^{-3/2}\rangle$——与 E 无关（Table I：0.5224/0.3 = 2.0897/1.2） | **成立** |
| 柱极限交叉验证（Chance §4A 对 F2 柱码，15 % 内） | 0.15 | reference_self_reported | Chance §4A：ε = 1/20、E = 1、q(0) = 0.08519、n = 10；两内核独立实现、独立签核 | **成立** |
| V5 定形边界两行（$q_0=0.3$ 带 [0.413, 0.431]；$q_0=0.7$ 带 [0.118, 0.120]；容差 5 %；自下单调收敛） | 0.05 | reference_self_reported | 第三行：m 加宽 0.4071 → 0.4308 → 0.4314，640 单元 0.4308；第四行：0.1020 → 0.1169 → 0.1199，640 单元 0.1199 | **成立** |
| 取向守卫内置断言 | — | reference_self_reported | 取错号曾产出假本征值——静默失败的「取向符号」成员 | **成立** |
| 非单调 / 越界网格 fail-loud | — | reference_self_reported | n_th < 4M、非 2 的幂、m 区间反、ρ₀ 越界、非整数 n、ε >= 0.5 都按名拒绝 | **成立** |

**★J × B = ∇p 到 4.9e-16；q(0) 逐位回收；q(1) = 0.523027 对椭圆积分闭式逐位相同，对印值 0.5224 高 0.12 %**

- ★印值系统性低 0.11–0.12 %，**六行同一比值**（1.0011–1.0012）——是印表时 $q(s)$ 的求法之差，不是平衡转录之差：本条的 $q(1)$ 与 $\oint(1+a\cos)^{-3/2}=4E(k^2)/((1-a)\sqrt{1+a})$ 逐位相同。

**★★环码 ω² −5.360 对柱码（m = 1）−5.415，差 1.0 %**

- ★上游记的是 −4.94 对 −4.57（15 % 内）；本条两路到 1 %。

**★★第三行 0.4314（带 [0.413, 0.431]，比带顶高 0.1 %）；第四行 0.1199（带内）；两行都自下单调收敛**

- ★★**伪模，照实记**：径向网格对谐波宽度不够时（80 单元、|m| ≤ 12）第四行出一个 0.225 的假本征值，320 单元即消失。「加谐波」必须配「加径向单元」。
- ★★**混叠**：极向 64 点、m ∈ [−12, 16] 时第三行跳到 1.009、反 Hermite 部分升到 5.6e-5；128 点即回到 0.4306。现在 `n_th < 4M` 按名拒绝。
- ★第三行比 ERATO 的 0.431 高 0.1 %——带宽本身就是码间分歧，判据容差 5 %。

## 不可比的部分

- ★★**判决成立**：五格全过。**本条是对拍，不是验证**：落进五码带只说明没有明显算错。
- ★离散照搬 `FR-EQ-028` 的教训：ξ^ρ 线性元、另两分量逐单元常值且在 Q 与 ∇·ξ 里不带 ρ 导数、能量取单元中点——没有这一条会锁死。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.10　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-029` 判**成立**（对拍）。内核新模块 `toroidal.rs`：Solov'ev 在 Kerner 坐标下全解析，θ* 谱给出。Table I 第三行 0.4314（带 [0.413, 0.431]），第四行 0.1199（带内），均自下单调收敛；柱极限对 F2 柱码 1 %。★伪模（径向不够时 0.225）与混叠（极向不够时 1.009）照实记，后者已改为按名拒绝。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.4 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/toroidal_fixed_boundary_v5.json`    `sha256:411adde2c77ee885d28f99fcc3afd0e67954fa9b70073d655d236bfab0fb3a65`    平衡自证、混叠、柱极限、两行的收敛梯子与伪模

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::the_solovev_equilibrium_proves_itself` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::the_nearly_straight_column_agrees_with_the_cylinder_code` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::table_i_row_three_lands_in_the_band` —— 第三格（--release）
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::table_i_row_four_lands_in_the_band_and_the_spurious_mode_is_resolved_away` —— 第三格（--release）
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::the_orientation_guard_fires` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::bad_grids_and_geometry_are_refused` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/toroidal.rs::tests::the_pencil_is_hermitian_and_the_mass_positive` —— 附：Hermite 与质量正定

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
