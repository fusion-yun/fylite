---
title: "mhd-vertical-lti-export"
---

# 装置电磁线性模型导出：**零等离子体极限是纯电路的解析本征值，导出的 γ 与竖直稳定性门逐位同值**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-vertical-lti-export.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [竖直稳定性、线圈受力与电磁线性模型](../domains/mhd/vertical.md)　|　记录正本：`records/mhd-vertical-lti-export.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：装置电磁线性模型导出：**零等离子体极限是纯电路的解析本征值，导出的 γ 与竖直稳定性门逐位同值**
- **参考**：纯电路的解析本征值；单回路刚性色散根；FR-EQ-016 竖直稳定性门的 γ
- **验的需求**：`FR-EQ-015`
- **跑在内核**：`fylite_kernel@0f7e5af3b3cf`（新鲜度 **current**）
- **记录版本**：1.9　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：由 `code/vstab` 那扇门给的电感、电阻、耦合梯度与磁诊断行装配 (A, B, C, D)；等离子体响应「静止 / 刚性位移」由参数选，摄动 G-S 按名拒绝

**参考**：纯电路的解析本征值；单回路刚性色散根；FR-EQ-016 竖直稳定性门的 γ

> 两回路 det(λM + R) = 0 的闭式根；单回路 γ = kR/(I_p²G² − kL)；EAST #137985 上 `code/vstab` 的开环 γ。

**口径与适用域**：

> 轴对称 n = 0、无质量刚性等离子体（刚性档）或冻结等离子体（静止档）；摄动 G-S 档未实现、按名拒绝；扰动输入 F、H 未交付。

## 判据与量到多少

:::{figure} ../figures/mhd-vertical-lti-export-headroom.svg
:alt: mhd-vertical-lti-export 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 零等离子体极限下 $\mathbf A=-\mathbf M^{-1}\mathbf R$ 与纯电路解析特征值一致 | — | machine_precision | 静止档即零等离子体极限：`M_eff = M` | **成立** |
| γ 读数随导出出 | — | machine_precision | 静止档 γ = 0：EAST 的 12 个 PF 线圈超导（电阻 0），各给一个零衰减模 | **成立** |
| 落 `em_coupling` 载体 | — | machine_precision | DD 4.1.1 `em_coupling` | **成立** |

**单回路 A = −R/L 逐位；两回路本征值对 $(L_1L_2-M_{12}^2)\lambda^2+(L_1R_2+L_2R_1)\lambda+R_1R_2=0$ 的两根 1e-12**

- ★「刚性档随 I_p → 0 退回静止档」**不是**一个极限：没有等离子体电流就没有刚性竖直模（k_ideal = 0），刚性档在那里按名拒绝。两档的关系另由一条恒等式钉住：刚性修正是秩一的，A 之差逐元对上 Sherman–Morrison。

**★★EAST #137985（102 个回路）：导出模型的最大本征值 3.43361 /s 对门的 γ 3.43361 /s，相对 7.4e-15；单回路刚性色散根 1e-12**

- ★★**判读的符号先写错过一次**：初版把「M_eff 不正定」当作越过理想极限而拒绝——恰好反了。阻性壁档里 M_eff = M − (I_p²/k)GGᵀ **恰有一个负本征值，那就是不稳定的竖直模**；越过理想极限（k ≥ k_ideal = I_p²GᵀM⁻¹G）时 M_eff 反而转正定，A 会读成「稳」，而无质量模型的增长其实是无穷大。现在按 k ≥ k_ideal 拒绝导出，不编一个有限的数。

## 不可比的部分

- ★★**判决成立**：三格全过。这一条交付的是**导出**：物理全部来自已有的 `code/vstab` 门（FR-EQ-016 那条记录验过它对 FreeGSNKE）。
- ★SRS 把这一条标为 SHOULD 级「路线项」，本册的需求表列作 MUST；按本册口径判。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.9　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-015` 判**成立**。新模块 `fylite.scenario.control.lti`：由 `code/vstab` 的矩阵装配 (A, B, C, D)，等离子体响应由参数选（静止 / 刚性；摄动 G-S 按名拒绝），落 `em_coupling/coupling_matrix`。零等离子体极限对两回路闭式 1e-12；EAST 上导出 γ 对门 7.4e-15。★判读符号初版写反（把阻性壁档的负本征值当成越限），已改为按 k ≥ k_ideal 拒绝。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.4 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@0f7e5af3b3cf`（库 `sha256:ac8204aa49349cc0ac53b3b5f9d7b91630ce4d69380fc7aa37034c89ce54dfe8`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/lti_export.json`    `sha256:d52fbb7b317911f0e2fa24c35dd4f1d91bda784aaa619ed16075b514af9afc88`    零等离子体极限、刚性色散根、秩一恒等式、EAST γ、载体

**守它的门**：

- `python/tests/test_lti_export.py::test_a_single_loop_decays_at_minus_r_over_l` —— 第一格
- `python/tests/test_lti_export.py::test_two_coupled_loops_have_the_closed_form_eigenvalues` —— 第一格
- `python/tests/test_lti_export.py::test_the_rigid_tier_is_a_rank_one_update_of_the_static_one` —— 第一格：两档的关系
- `python/tests/test_lti_export.py::test_one_loop_and_a_rigid_plasma_reproduce_the_dispersion_root` —— 第二格
- `python/tests/test_lti_export.py::test_on_east_the_exported_gamma_is_the_kernels_growth_rate` —— ★第二格：EAST
- `python/tests/test_lti_export.py::test_beyond_the_ideal_limit_the_export_is_refused` —— 第二格：理想极限拒绝
- `python/tests/test_lti_export.py::test_the_plasma_response_is_a_parameter_and_the_unimplemented_tier_is_named` —— 档次是参数
- `python/tests/test_lti_export.py::test_the_carrier_is_em_coupling_and_its_fields_exist` —— 第三格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
