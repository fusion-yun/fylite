---
title: "eq-forward-boundary-rule-vs-kefit"
---

# 两种边界规则：边规则是自由边界正问题的解——对独立代码 FreeGSNKE 0.0041（在它自己正/逆两解之差 0.0087 之内）；节点规则不收敛、靠 10.5 kA 虚拟对贴近 KEFIT

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-boundary-rule-vs-kefit.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-boundary-rule-vs-kefit.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：两种边界规则：边规则是自由边界正问题的解——对独立代码 FreeGSNKE 0.0041（在它自己正/逆两解之差 0.0087 之内）；节点规则不收敛、靠 10.5 kA 虚拟对贴近 KEFIT
- **参考**：FreeGSNKE · KEFIT
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.24　**评审**：草稿　**日期**：2026-09-19

## 问的是什么

**被量的**：同一道前向题的**两种边界规则**：node（节点规则，带虚拟对）与 edge（边规则）

**参考**：FreeGSNKE（fydoc CASE-23 corpus/freegsnke（静态正解，Lao85 剖面拟合 KEFIT 的 p′/FF′ 到 1e-9，KEFIT 十二路线圈电流））

> ★★独立的第三个解：同一组线圈电流与剖面上的自由边界正问题。它自己的正解与逆解（线圈挪 0.37 kA·t）相差 0.0087——这是本条读「一致」的尺度。

**参考**：KEFIT

> ★KEFIT 的图是**重建**，不是它自己输入的正解：FreeGSNKE 在同一组电流与剖面上离它 0.0156——所以「谁离 KEFIT 近」判不了规则，留作读数。

**口径与适用域**：

> EAST #137985 四个切片（t = 4.041 / 4.944 / 5.976 s，末片带 POINT 剖面）。两种规则跑在同一批输入、同一台机器、同一内核上，只差边界条件的提法。★比较落在 KEFIT 边界之内的网格节点上。

## 判据与量到多少

:::{figure} ../figures/eq-forward-boundary-rule-vs-kefit-headroom.svg
:alt: eq-forward-boundary-rule-vs-kefit 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 边规则（缺省）对 FreeGSNKE 的 psi_N 偏差（KEFIT 边界内 RMS，t = 4.041 s） | 0.00872201 | reference_self_reported | t = 4.041 s，KEFIT 边界内 psi_N RMS：边规则对 FreeGSNKE 0.0041 · 节点规则 0.0173 · KEFIT 自己 0.0156 · FreeGSNKE 逆解 0.0087。磁轴 Z：边 +8.0 mm · FreeGSNKE +6.7 · 节点 -3.7 · KEFIT -0.9 | **成立** |
| 收敛且虚拟对电流为零级（\|fb\| < 1e-3 Ip）——解的是所述的问题，不是带着虚构外力的另一个问题 | — | reference_self_reported | 三个纯磁测切片：边规则 t4041 收敛 753 次、残差 9.9e-10、对 -50 A · t4944 收敛 785 次、残差 9.9e-10、对 -44 A · t5976 收敛 764 次、残差 9.5e-10、对 -33 A；节点规则 t4041 settled 残差 2.9e-03、对 10.5 kA · t4944 settled 残差 3.7e-03、对 13.7 kA · t5976 settled 残差 1.3e-03、对 14.2 kA | **成立** |
| 两种规则对 KEFIT 的 psi_N 偏差（读数，不判） | — | reference_self_reported | t4041_mag：边 0.0185 / 节点 0.0074 · t4944_mag：边 0.0228 / 节点 0.0065 · t5976_mag：边 0.0237 / 节点 0.0066 · t5976_primary：边 0.0256 / 节点 0.0221 | **未判（读数）** |

**`边规则（缺省）对 FreeGSNKE 的 psi_N 偏差（KEFIT 边界内 RMS，t = 4.041 s）`** — ★带 = 参考自己的两个解（FreeGSNKE 正解与逆解）之差：落在参考自身的散布之内，就是参考分不开的一致。

**`收敛且虚拟对电流为零级（|fb| < 1e-3 Ip）——解的是所述的问题，不是带着虚构外力的另一个问题`** — ★虚拟对是数值控制器，不是导体：不动点处它应当不带电流。带着 10 kA 的「解」是另一个问题（多一根导体）的解。

**★★边规则 = 独立代码的解：对 FreeGSNKE 0.0041（带 0.0087）；节点规则 0.0173**

- ★★这就回答了本条此前判不了的那个问题：此前只有 KEFIT 一个参照，而节点规则离它更近（0.007 对 0.018）；有了独立的第三个解，才看清 KEFIT 本身不是这个正问题的解（离 FreeGSNKE 0.0156），节点规则的「近」来自那对虚拟电流把柱子按在 KEFIT 的位置上。
- ★FreeGSNKE 只有这一片（CASE-23 的记录只跑了 4.041 s）；其余三片仍只有 KEFIT 作参照，读数见第三格——四片同向：边规则离 KEFIT 远 2.5 倍左右，与这一片一致。

**边规则收敛、虚拟对 -50 A；节点规则 settled、带 10.5 kA**

- ★用户 2026-09-19 裁定边规则为 `code/forward` · `code/discharge` 的缺省；节点规则以 `edge_fraction = 0` 留作对照。
- ★边规则此前要 5664 次才收敛，是因为每次下垂修正都要重新收敛到 1e-9；现在在 1e-4 就修、且修正不再缩小对电流时就停——同一不动点（对 FreeGSNKE 0.0041 不变），750–790 次。

**对 KEFIT（读数）**

- ★KEFIT 不是这个正问题的解，离它的远近不判规则。t5976_primary（POINT 约束剖面）两种规则都不收敛，见 `eq-forward-free-boundary-convergence`。

## 不可比的部分

- ★★本条由 inconclusive 转 pass（2026-09-19）：缺的是独立于两者的真值，FreeGSNKE 在同一组输入上的正解就是它。
- ★对拍不是验证：两码一致说明没有明显算错，不说明物理全对；但两码在 0.004 内一致、且都离 KEFIT 0.016–0.018，足以判定「离 KEFIT 近」不是正确性的标志。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.24　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：两种边界规则对 KEFIT 的读数，不判谁对 |
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
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.22 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.23 | 2026-09-19 | Claude Opus 5 | ★★由 inconclusive 转 pass：缺的是独立于两者的真值——FreeGSNKE 在同一组电流与剖面上的正解（CASE-23 归档）。边规则离它 0.0041，落在它自己正/逆两解之差 0.0087 之内；节点规则 0.0173、不收敛、带 10.5 kA 虚拟对；KEFIT 0.0156（它的图是重建，不是它输入的正解）。对 KEFIT 的远近改记读数。读数 `forward_convergence_east137985.json` 由新工具 `tools/benchmark-forward-convergence.py` 生成。原 open_defect 关闭。 内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 |
| 1.24 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/forward_convergence_east137985.json`    `sha256:b85776186d192a9eca810fea56d0ace56b245392f7f402b9a46b90bdfdb4051c`    ★两种规则对 KEFIT 与对 FreeGSNKE（tools/benchmark-forward-convergence.py 生成）
- `tools/benchmark-forward-convergence.py`    `sha256:9a260a32ea9ed1623ca13858f27ffedc7b77bf18969a86fab653c6b3c1e6ae0f`    读数生成器
- `FYDOC-CASE-23-east-137985-efit-east/corpus/freegsnke/freegsnke_vstab_east137985.tar.gz`    `sha256:df6725b4bfe4ad664620c4503dfb4d8aea5b951b36b772a8fc1902f3cfbc6c81`    ★FreeGSNKE 侧原件（参考类，指针 + sha256）
- `docs/benchmark/readings/forward_edge_rule_metrics.json`    `sha256:093e91fd8355bac3afa9de5a18edb27e73160cc2080dad57a5f2e84945753bc2`    两种规则对 KEFIT 的派生指标（tools/benchmark-equilibrium-metrics.py）

**守它的门**：

- `python/tests/test_benchmark_equilibrium.py::test_fr_eq_001_the_edge_rule_is_the_independent_code_s_answer` —— ★第一、二格：对 FreeGSNKE 在其自身散布内；节点规则不收敛、对 > 5 kA
- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_the_forward_edge_rule_is_a_reading_not_a_band` —— 第三格：两种规则对 KEFIT 的读数逐位复现

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
