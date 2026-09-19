---
title: "eq-forward-chease-solovev"
---

# 同一道 Solov'ev 定边界题：fylite 129^2 对 CHEASE NS=NT=80

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-chease-solovev.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-chease-solovev.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：同一道 Solov'ev 定边界题：fylite 129^2 对 CHEASE NS=NT=80
- **参考**：CHEASE
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`fylite_kernel@51d34102a406`（新鲜度 **current**）
- **记录版本**：1.20　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/fixed_boundary，129x129 网格

**参考**：CHEASE（本机构建，NS = NT = 80）

> ★CHEASE 解的是同一道方程，按「同一函数的另一实现」本可归**验证**；这里归**对拍**，理由是容差取的是**实测带**而不是机器精度——两边都带离散误差，谁都不是真值。分类由「参考是什么 + 容差怎么取」决定，不由做得多认真决定。

**口径与适用域**：

> Solov'ev 定边界解析平衡：R0 = 1.8 m · B0 = 2.0 T · e2 = 1.07544 · Ip(闭式) = 3451548 A · q0(闭式) = 0.8348157；边界轮廓 720 点，psi 口径「g-file per radian, axis minimum」（即每弧度、以轴为极小）。比较落在轮廓**内**的 18805 个网格点上（「深内点」）。★径向标签为 psi_N（归一极向磁通），不是 rho；容差与它绑定。★本条是**定边界**：FR-EQ-001 判据里「自由边界 Ip 约束收敛 rel 1e-6」那一档不在本条，由 eq-forward 的另一条记录覆盖（现缺，见本域缺口栏）。 CHEASE 侧为 NS = NT = 80，输出经 EQDSK_COCOS_02.OUT 读回，★两侧在同一 psi 口径与同一 COCOS 下比较（口径不对齐时比出来的是约定差，不是实现差）。

## 判据与量到多少

:::{figure} ../figures/eq-forward-chease-solovev-headroom.svg
:alt: eq-forward-chease-solovev 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 深内点 psi_N 两码之差（RMS） | 1.12e-05 | measured_band | RMS 1.119e-05 · max 0.0001122 | **成立** |
| q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS） | 0.000231 | measured_band | q[0.1,0.9] RMS 0.0002303 · max 0.0005635 · q95 -3.549e-05 | **成立** |
| CHEASE 自身对闭式解的偏差（本条的旁证锚） | 3.91e-06 | measured_band | psi_N RMS 3.907e-06 · 轴 1.75e-06 mm · Ip 9.36e-10 · q0 3.56e-06 | **成立** |

**`CHEASE 自身对闭式解的偏差（本条的旁证锚）`** — ★没有这一锚，两码之差说明不了任何事：差可能全是对方的。

**CHEASE 对闭式解——这条对拍之所以可读的前提**

- ★★**这一条是本记录里最有用的一行**：CHEASE 的 q0 对闭式解只差 3.56e-06，而 fylite 129^2 差 -1.97e-05。于是两码 q0 之差 -2.33e-05 **归属明确**——是 fylite 的收敛，不是基准或口径的问题。没有这一锚，同一个数只能读成「两码有分歧」。

## 不可比的部分

- ★**对拍不是验证**：两套实现吻合到 1e-5 不证明谁对——两个错误也能互相抵消。本条的价值全靠 criterion/3 那一锚（CHEASE 自己对闭式解的偏差）撑着；主判据在 eq-forward-solovev-fixed-boundary。
- ★**CHEASE 的 NS/NT 是它的收敛旋钮**：换一档 NS，这里每个数都会变。所以带是「在 NS=NT=80 这一档上实测的」，不是 CHEASE 的固有精度。
- ★CHEASE 侧的输入 EXPEQ 由本仓写出，p' 与 TT' 的符号与归一是**在本次运行里量出来的**，不是假定的——符号错时 CHEASE 不收敛，这一点本身是一条弱自证。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.20　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：与验证记录同源，单列以免把对拍与验证混在一条里 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核同日两次换代后的全册重验（原 1.1 与 1.2 两条，2026-09-18 合并——第二条当时误抄了第一条的摘要）：①`301a962b` → `ac8c0f5c`，`FR-EQ-002/008/010/011` 与 0D 三项入内核（内核仓 `3ea79df`），fylite 侧 110 道、内核侧 656 项全通过；②`ac8c0f5c` → `eb8c9022`，ETS 五型边界、燃烧→密度的接线、时间收敛阶入内核（内核仓 `acd1628`），165 道门禁全过、660 项既有内核测试一项没动。★两次本条的判据与数值都**未改口径**。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 合并重复的变更条目：1.1 与 1.2 是同日两次内核换代，第二条误抄了第一条的摘要；合并成一条（沿用 1.2），两次换代各自写明。★本条的判据与数值未动。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.17 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@51d34102a406`（库 `sha256:e4040bbf79e390d949739fc5023d63e8ba5759242ad7ca52839becab115ba3f6`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/solovev_fixed_boundary.json`    `sha256:32c17f7511b7745a7b32604cb8ed1042f7f9c3487c1093c6be48fb35b97e752d`    与验证记录同一份读数、同一次运行——两条记录因此逐位可互校。

**守它的门**：

- `python/tests/test_benchmark_fixed_boundary.py::test_v19_chease_on_the_same_contour` —— 守 CHEASE 侧对闭式解的带；CHEASE 未构建时按名 skip

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
