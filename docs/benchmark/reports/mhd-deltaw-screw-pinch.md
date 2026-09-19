---
title: "mhd-deltaw-screw-pinch"
---

# 完整 δW 的螺旋箍缩：**g 两式互证、Λ 式作绝对尺——后者当场抓住了我对 Eq. (9) 的一处抄错**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-screw-pinch.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-screw-pinch.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：完整 δW 的螺旋箍缩：**g 两式互证、Λ 式作绝对尺——后者当场抓住了我对 Eq. (9) 的一处抄错**
- **参考**：Newcomb, *Hydromagnetic stability of a diffuse linear pinch*, Ann. Phys. **10**, 232 (1960)
- **验的需求**：`FR-EQ-027`
- **跑在内核**：`fylite_kernel@0f7e5af3b3cf`（新鲜度 **current**）
- **记录版本**：1.10　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：不作高 β 序约化、含压强驱动；μ₀ ≡ 1，SI 入口只换压强

**参考**：Newcomb, *Hydromagnetic stability of a diffuse linear pinch*, Ann. Phys. **10**, 232 (1960)

> Eqs. (2)、(9)、(14)–(18)、(32)–(33)，目视读页。

**口径与适用域**：

> 柱位形、单 $(m,k)$、无环效应；环状箍缩 $a<r<b$（$r=0$ 不在网格内），$\xi(a)=\xi(b)=0$。★交付的是**边缘稳定性**：没有动能归一，λ 的数值不是 $\omega^2$。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-screw-pinch-headroom.svg
:alt: mhd-deltaw-screw-pinch 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| $g$ 两式互证（场形式 (17) vs 压强形式 (18)，仅在平衡关系下相等） | 1e-12 | machine_precision | 五组 $(m,k)$、200 点：两式最劣相对 1.6e-13 | **成立** |
| 绝对尺：$\delta W$ 二阶收敛，误差比 $\simeq4$ | — | reference_self_reported | 对两端为零的 ξ：$(\pi/2)\int r\Lambda\,dr$（Eq. 14，Λ 取 Eq. 9）对 $(\pi/2)\int(f\xi'^2+g\xi^2)dr$（Eq. 15–17）四组 $(m,k)$ × 两式 **最劣 2.1e-15**；节点插值的 FEM 能量对精确积分 50 · 100 · 200 · 400 单元 2.74e-4 · 6.85e-5 · 1.71e-5 · 4.28e-6 | **成立** |
| Suydam 两条独立路：α 由 (32a) 两侧分别算相符；(33) 左端恒等于 $(\alpha+4\beta)B^2/(8B_\theta^2)$ | 1e-06 | reference_self_reported | 四组 $(m,k)$ 在各自奇异面上（二分到机器精度） | **成立** |
| 无剪切时判据退化为 $dP/dr>0$ 且有非空对照；$f\ge0$ 且奇异面上恰为零；纯轴向场必稳（带非空对照） | — | reference_self_reported | 无剪切：Suydam 左端逐点等于 $P'$；有剪切对照 $P'=-5.1\times10^{-3}<0$ 而左端 $+3.5\times10^{-2}$；$f$ 在奇异面上 < 1e-12、别处 ≥ 0；纯轴向场五组 $(m,k)$ 全稳，带电流 $m=1,k=-0.8$ 的 λ = −0.550 | **成立** |
| 本征值符号与最优试探函数的 $\delta W$ 同号 | — | reference_self_reported | (1,−0.8)：λ −0.550、W −6.3e-4；(1,−0.2)：λ 1.980、W 1.4e-3 | **成立** |
| 非平衡的 $dP/dr$ / $r=0$ 网格 / $m=k=0$ / 未知 form / 非整数 $m$ 一律 fail-loud | — | reference_self_reported | 四种都按名拒绝；「未知 form」在 Rust 里**编不过**（`GForm` 只有两个变体） | **成立** |

**五组 $(m,k)$、200 点：两式最劣相对 1.6e-13**

- ★**不是「二阶消失」而是舍入**：上游的两式差随网格二阶消失，是因为它对剖面做数值求导；这里剖面带解析导数进来，(17)、(18) 逐点只差舍入。判据要的「两处转录同时钉死」照样成立——任一处抄错都会在 1e-13 这一层露出来。

**★★Λ 式对 $(f,g)$ 式 2.1e-15；FEM 能量误差比 3.999 / 4.000 / 4.000**

- ★★**绝对尺换了一条路**：上游用 SymPy 的精确符号 $f,g$ 做绝对尺；本仓没有 SymPy，改用原文**另一处**转录——Eq. (9) 的 Λ——作见证。两式只在分部积分后相等，任一处抄错都破坏它。
- ★★**它当场抓到了一处真错**：我初版把 Eq. (9) 前置的 $1/(k^2r^2+m^2)$ 也作用到了第二项上，两边差 **3.5 倍**；看原文排版，那个分母只管第一项的平方——与 (17) 里 $(krB_z+mB_\theta)^2/r$ 不带分母一致。改后 2.1e-15。

**四种都按名拒绝；「未知 form」在 Rust 里**编不过**（`GForm` 只有两个变体）**

- ★SI 入口：只有压强要换。忘乘 μ₀ 的 $dP/dr$（−1.2e6 对 −1.54）不满足平衡 (2)，被当作「不是平衡」拒绝——静默的错变成了响的错。

## 不可比的部分

- ★★**判决成立**：六格全过。第一格的「二阶消失」以「逐点只差舍入」达成（解析导数），第二格的绝对尺改由 Eq. (9) 见证——并当场抓到了一处转录错。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.10　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-027` 判**成立**。内核新模块 `screwpinch.rs`：Newcomb (15)–(18) 的 f、g 两式，Λ（Eq. 9）作绝对尺，Suydam 两路。★Λ 见证当场抓到我对 Eq. (9) 的一处抄错（分母多作用了一项，差 3.5 倍），改后 2.1e-15。两式互证 1.6e-13（解析导数，非二阶）；FEM 比 4.000；Suydam 两路 1e-15 量级。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@0f7e5af3b3cf`（库 `sha256:ac8204aa49349cc0ac53b3b5f9d7b91630ce4d69380fc7aa37034c89ce54dfe8`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/screw_pinch_delta_w.json`    `sha256:163762113e864f6644973e57698abb0fc44f7410353b9b2c32602c2c74f4f238`    两式、Λ 见证、FEM 收敛、Suydam、无剪切、稳定性、本征向量、SI、拒绝

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::the_two_forms_of_g_agree_under_equilibrium` —— 第一格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::the_lambda_form_is_the_same_energy` —— ★第二格：绝对尺
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::the_discrete_energy_converges_at_second_order` —— 第二格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::suydam_by_two_routes` —— 第三、四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::without_shear_suydam_is_just_the_pressure_gradient` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::a_pure_axial_field_is_stable_and_a_current_is_not` —— 第四格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::the_eigenvalue_sign_is_the_sign_of_w_on_its_eigenvector` —— 第五格
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::the_si_entry_converts_only_the_pressure` —— 第六格：SI
- `$FYLITE_KERNEL/rust/fylite/src/screwpinch.rs::tests::bad_input_is_refused_by_name` —— 第六格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
