---
title: "tr-coupling-interpretive-inversion"
---

# 解释性反演核：**接口早已成文，往返按 h² 收敛到 3.8e-5——此前只是没有入册**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-coupling-interpretive-inversion.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [双模、平衡耦合与代理栈](../domains/tr/coupling.md)　|　记录正本：`records/tr-coupling-interpretive-inversion.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：解释性反演核：**接口早已成文，往返按 h² 收敛到 3.8e-5——此前只是没有入册**
- **参考**：SRS-04 Eq. (eq-srs04-interp) 与本仓的预测性导热求解
- **验的需求**：`FR-TR-011`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.11　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：功率平衡反演：由剖面与源项反演实验通量 q_PB 与有效输运系数 χ_eff；平直剖面按名屏蔽

**参考**：SRS-04 Eq. (eq-srs04-interp) 与本仓的预测性导热求解

> 闭式：常源下 P(ρ)、q_PB 解析可知；往返：以常数 χ₀ 预测求解出的剖面反演回去，χ_eff·gm7 应为 χ₀。

**口径与适用域**：

> 稳态功率平衡（无 dT/dt 项）、单一热通道；几何取 Miller / 解析 / g-file 追踪 / 调用方给定的梯子；源可以是参数化高斯或给定的 core_sources 剖面，电子–离子交换可选。

## 判据与量到多少

:::{figure} ../figures/tr-coupling-interpretive-inversion-headroom.svg
:alt: tr-coupling-interpretive-inversion 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 反演核接口成文（路线 [TBD]） | — | reference_self_reported | 闭式：累积功率 1e-6、q_PB 1e-9，平直剖面全部屏蔽；往返（常数 χ₀ 预测 → 反演）χ_eff·gm7 对 χ₀：61 · 121 · 241 · 481 点 2.1e-3 · 5.7e-4 · 1.5e-4 · 3.8e-5（比 3.7 · 3.8 · 3.9）；门 `code/interpretive` 与它替换的配方在五档几何上逐位（1e-12） | **成立** |
| 反演核接口成文（路线 [TBD]） | — | reference_self_reported | 高斯沉积作 core_sources 表给回：χ_e · χ_i · q_e · q_i 逐点 1e-12；交换：电子失 = 离子得 = p_exchange（1e-9），T_e = T_i 时恰为 0，ρ ≈ 1/3 处的交换功率密度对 NRL 公式集的 ν_eq 15 % 内（差在库仑对数的约定）；驱动电流表 ∫j dV/(2πR0) 1e-12 | **成立** |

**★接口成文：核 · C ABI · 文档门三层都在，式子与约定写在核的文档注释里；★往返按 h² 收敛**

- ★★**这条早就实现了，只是没入册**：`interpretive_channel`、C ABI 导出与 `code/interpretive` 门都在内核仓，测试也在（kernel 仓 Python 门）。本册一直把它记作空缺，是因为没有记录，不是因为没有实现。
- ★约定照实记：通量取 gm7 = ⟨|∇ρ|⟩ 的面积，导热律取 gm3 = ⟨|∇ρ|²⟩，所以 χ₀ 的预测解反演回来是 **χ₀/gm7** 而不是 χ₀——上游的约定，门里钉着，谁也不许把一个度规「修」成另一个。
- ★★**顺带查出并修掉一处 kernel 仓自己的红门**：g-file 档的参照梯子自 `12e603b`（通量规统一成整圈 Wb）起把每弧度的 dpsi 喂给整圈的 `equilibrium_ladder`，参照的 ρ 小 √(2π)，门恒红——门对、参照过期。`cargo test` 跑不到 kernel 仓的 Python 门，所以那次没看见；同批还有 `test_ladder_code` 四道，一并修。
- ★不在本条：dT/dt 项（SRS 标 [TBD]）、粒子通道反演（只有 `d_from_flux` 的换算）、工作流编排（归 fyanalysis）。

**★给定源剖面（`sources = table`）与电子–离子交换（`exchange = 1`）——复现 Wei et al. 2026 的输运反演要的两样**

- ★源表的读法与 `code/evolve` 同一个（`source_tables`）：带 ψ_N 网格的表要真 ψ_N——g-file 档或绑了 `psi_norm` 的梯子；Miller 档的 x² 不是磁通，拒绝。
- ★交换用 march 自己的速率（`scenario::exchange_nu` / `exchange_power_w`，体 D、n_i = n_e），是 ONETWO 的 qdelt 那一项；缺省关，既有调用逐位不变。
- ★驱动电流只报告（`i_cd`、`j_cd`），不进反演——本门是稳态功率平衡。

## 不可比的部分

- ★★**判决成立**：判据是「接口成文」（检查），本条另给了往返的二阶收敛作数值证据。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.11　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-TR-011` 判**成立**。反演核（`interpretive_channel` · C ABI · `code/interpretive`）早已在内核仓，本册缺的只是记录。往返按 h² 收敛到 3.8e-5（新钉成门）。★顺带修掉 kernel 仓自 12e603b 起恒红的 5 道门（参照梯子喂了每弧度 dpsi，ρ 小 √(2π)）。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | `code/interpretive` 收给定源剖面（`sources = table`，与 `code/evolve` 同一个 `source_tables`）与电子–离子交换（`exchange = 1`）——east-kinetic-reconstruction 复现 Wei et al. 2026（AIP Adv. 16, 085007）的输运反演要它们：`code/wave` · `code/rf_ray` 算出的沉积照形状反解，ONETWO 的 qdelt 有了对应。内核仓 Rust 门 4 道（`case::interpretive_source_tests`）。只加不改（接口摘要 `1ee10b0ae6f30088` → `54f11c602d6f12b4`，修订号不动）。 ★本条新增的 4 道门跑在内核 `1f2578a`（fylite_kernel 分支 `feat/interpretive-given-sources`，并入 develop 时与 `e6c40c7` 合）上；本册的基准内核指纹**没有**随之更新——更新要全册重验，另起一件事做，在那之前本条的读数仍以 1.2 的基准为准、新门的数写在上面的发现里。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.11 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/interpretive_inversion.json`    `sha256:bcfe1e5ed3deed99937723335f10b3ae5d4c09ed334bd711b71d6432c499f9e4`    接口、闭式、往返收敛、门的对位、通量规修复

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/transport.rs::tests::the_interpretive_inversion_matches_its_closed_form_and_masks_flat_profiles` —— 闭式与平直屏蔽
- `$FYLITE_KERNEL/tests/test_transport_core.py::test_interpretive_inverts_a_known_conduction_solve` —— 往返（2 %）
- `$FYLITE_KERNEL/tests/test_transport_core.py::test_the_round_trip_converges_at_second_order` —— ★往返的二阶收敛
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_the_miller_tier_with_deposition_only_is_the_same_to_the_bit` —— 门的对位：Miller
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_every_source_on_is_the_same_to_the_bit` —— 门的对位：全源
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_without_an_ion_temperature_ti_is_te_and_the_note_says_so` —— 无 Ti
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_the_gfile_tier_is_the_traced_ladder` —— ★g-file 档（本次修复通量规）
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_a_bound_ladder_is_taken_as_given` —— 给定梯子
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_refusals_name_the_thing` —— 拒绝
- `$FYLITE_KERNEL/rust/fylite/src/case.rs::interpretive_source_tests::a_table_of_the_gaussian_inverts_to_the_gaussian_chi` —— ★给定源剖面：高斯沉积作表给回，逐点同一 χ（1e-12）
- `$FYLITE_KERNEL/rust/fylite/src/case.rs::interpretive_source_tests::a_table_and_the_sliders_together_or_a_psi_grid_on_miller_are_refused` —— 表与 p_e/p_i 同给、Miller 档带 ψ_N 网格的表：拒绝
- `$FYLITE_KERNEL/rust/fylite/src/case.rs::interpretive_source_tests::the_exchange_moves_power_from_electrons_to_ions_and_matches_the_nrl_rate` —— ★电子–离子交换：守恒（1e-9）、T_e = T_i 为零、对 NRL 公式集 15 % 内
- `$FYLITE_KERNEL/rust/fylite/src/case.rs::interpretive_source_tests::a_driven_current_table_is_integrated_in_its_own_measure` —— 驱动电流按 dV/(2πR0) 积分（1e-12）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
