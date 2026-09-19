---
title: "tr-closure-lazy-plugin-resolution"
---

# 抽象层在导入期不拖进实现：`import fylite.engine` 连 numpy 都不碰

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-closure-lazy-plugin-resolution.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [闭包插件面：输运系数与插件接入](../domains/tr/closure.md)　|　记录正本：`records/tr-closure-lazy-plugin-resolution.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：抽象层在导入期不拖进实现：`import fylite.engine` 连 numpy 都不碰
- **参考**：导入后 `sys.modules` 的增量本身
- **验的需求**：`NR-TR-003`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.23　**评审**：草稿　**日期**：2026-09-17

## 问的是什么

**被量的**：导入它会把什么一并拖进来

**参考**：导入后 `sys.modules` 的增量本身

> ★**参照是解释器自己的记账**：`import` 前后 `sys.modules` 的差，是一个不容争辩的、机器给出的清单。

**口径与适用域**：

> 本次检出的 `python/fylite/engine`（24 个模块）。测法：干净解释器里记 `import fylite.engine` 前后 `sys.modules` 的差。★**判的是导入期**——运行期当然要 numpy，那正是「惰性」二字的意思。

## 判据与量到多少

:::{figure} ../figures/tr-closure-lazy-plugin-resolution-headroom.svg
:alt: tr-closure-lazy-plugin-resolution 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 导入抽象层时被拖进来的**重型依赖**个数（numpy / scipy / h5py / netCDF4） | 0 | reference_self_reported | `import fylite.engine` 后 `sys.modules` 净增 180 个模块，其中 numpy / scipy / h5py / netCDF4 **0 个** | **成立** |
| 被一并拖进来的其他 fylite 子包个数 | 5 | measured_band | 一并进来的 fylite 子包只有 3 个，且都是轻量的：`fylite._fyo_interface` · `fylite._paths` · `fylite.notice` | **成立** |
| 抄录点名的 `TransportSolver["fytrans"]` 惰性解析 | — | reference_self_reported | 抄录点名的是 fytok 的 Python 插件注册表（`TransportSolver["fytrans"]` 惰性解析）。fylite 是**协议成员**，不 import 上游生态，也没有这样一个注册表——它的闭包分派在**门的设置项**上按名进行（见 `tr-closure-plugin-dispatch`：五个名字五种行为） | **未评估** |

**`导入抽象层时被拖进来的**重型依赖**个数（numpy / scipy / h5py / netCDF4）`** — ★★抄录写的是「抽象类不 import 实现」。在 fylite 的说法里，这条不变量落成 `FYL-SDD-01 DE-COMP-03`：**`fylite.engine` 顶层只导标准库，numpy 与重型依赖一律函数内惰性导入**。★取 0 而不是「少」：这是个是非题。

**`被一并拖进来的其他 fylite 子包个数`** — ★★这一格防的是一个**更隐蔽**的破法：包的 `__init__` 急切导入一切，于是导入任何子模块都会把整个世界拉进来——**而那会让第一格变得不可观测**。

**`抄录点名的 `TransportSolver["fytrans"]` 惰性解析`** — ★★**本仓没有那个注册表**，见 finding。判据照抄立在这里，不删。

**★★也没有被包的 `__init__` 顺手拖进整个世界**

- ★★**这条不变量曾经不成立，而且没有任何东西能发现**——门自己的抬头把两处破法都记着：〔一〕`engine/provenance.py` 有一句模块级的 `import numpy as np`（**字面文本，差一行就破**）；〔二〕更要命的是，**不变量本身是不可观测的**——`fylite/__init__.py` 急切导入了 `device` · `engine` · `io` · `kernel` · `run` · `scenario`，于是导入任何子模块都会先跑它。★**一条无法观测的不变量不是不变量**，所以第二格必须单列。

**★`TransportSolver` 注册表：**本仓没有这个东西****

- ★★**这是一次翻译，说清楚而不是含混过去。** 抄录那句话点的是一个**具体的数据结构**；fylite 用另一种结构答同一个问题（**抽象层要不要在导入期知道实现是谁**），而答案是「不要」——上面两格就是它。
- ★把「门的设置项按名分派」说成「`TransportSolver` 惰性解析」是冒充，所以这一格标 unevaluated。

## 不可比的部分

- ★结构判据会腐烂且腐烂时不出声——本条两格都由 `test_engine_imports_only_stdlib.py`（33 项）守着。★**这是本批输运记录里少有的、门在本仓因而 CI 跑得到的一条。**
- ★本条不声称闭包分派**做得好**（那是 `tr-closure-plugin-dispatch`），只声称**抽象层不必先认识实现**。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-19　版本 1.23　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：`NR-TR-003` **不是能力缺口**。导入抽象层净增 180 个模块、重型依赖 0 个、顺带进来的 fylite 子包只 3 个。★`TransportSolver` 注册表那一格如实标 unevaluated：本仓没有那个数据结构，**说成有是冒充** |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.15 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.16 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.17 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.20 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.22 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 ★本条的判据与数值**未改口径**。 |
| 1.23 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`b27d7145ab3e`：新门 `code/icrh`——ICRH 少数离子加热第一次经门可达，`CASE_CODES` 41 → 42，只加不改）。内核侧：`icrh_door` 2 · `fyo` 7 全过。★没有一处既有缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/lazy_engine_import.json`    `sha256:01db8e49ebcece6e881ee966f3632c3e63bcce81eb8ae894499da5f519de01c6`    干净解释器里 import fylite.engine 的 sys.modules 增量（当日实跑）

**守它的门**：

- `python/tests/test_engine_imports_only_stdlib.py` —— ★前两格的门（33 项，实跑，CI 跑得到）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
