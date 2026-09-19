---
title: "eq-forward-self-contained-core"
---

# 自包含的数值核：整个核只依赖一个线程库，Python 层封锁三根照样整包导入

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-self-contained-core.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-self-contained-core.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：自包含的数值核：整个核只依赖一个线程库，Python 层封锁三根照样整包导入
- **参考**：各自的依赖声明与导入图
- **验的需求**：`NR-EQ-005` · `NR-TR-004`
- **跑在内核**：`fylite_kernel@51d34102a406`（新鲜度 **current**）
- **记录版本**：1.21　**评审**：草稿　**日期**：2026-09-17

## 问的是什么

**被量的**：数值核本体与它上面的 Python 层

**参考**：各自的依赖声明与导入图

> ★★**本条没有数值参照，判的是结构。** 抄录说的是「模块级链无 `spdm` / `fytok` / `sp`」＋「封锁三根隔离加载」——两件都可判，且判得干脆。

**口径与适用域**：

> 本条判的是**这一次检出的源码状态**：内核仓 `rust/fylite`（数值核）与其 `Cargo.lock` 闭包，以及公开仓 `python/fylite` 全包（63 个文件、62 个可导入模块）。★**不判运行时**：`libfylite.so` 由公开仓把核与数据层打包链出，数据层另有 netcdf / hdf5 依赖——**那是数据层的，不是数值核的**，而核「从不读装置文档」正是它自己的分层规矩。★也不判 `fylite_ext`（TGLF / DKE 扩展）以外的别的宿主。

## 判据与量到多少

:::{figure} ../figures/eq-forward-self-contained-core-headroom.svg
:alt: eq-forward-self-contained-core 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 数值核 crate 的直接外部依赖数 | 1 | reference_self_reported | crate `fylite` 的 `[dependencies]` 共 1 项：rayon（`optional`，随 `parallel` 特性开关） | **成立** |
| 依赖闭包里的**科学计算**包数（BLAS / LAPACK / ndarray / 线性代数 / 特殊函数） | 0 | reference_self_reported | 整个 `Cargo.lock` 闭包 9 个包，去掉本仓自己的 3 个 crate，外部只剩 6 个 —— rayon · rayon-core · crossbeam-deque · crossbeam-epoch · crossbeam-utils · either，**全是同一条线程栈**，科学计算包 0 个 | **成立** |
| Python 层里 `sp` / `spdm` / `fytok` 等生态导入的处数（AST 全包扫描） | 0 | reference_self_reported | AST 扫了 63 个文件，命中 0 处（封禁根：sp / spdm / fytok / fyutils / fydoc / fydata / spdb） | **成立** |
| ★封锁三根之后整包导入的失败数 | 0 | reference_self_reported | 在 `sys.meta_path` 上把 sp / spdm / fytok 三根封死（**导入即抛**，不是「没装」），逐个导入 62 个模块，因封锁而失败 0 个 | **成立** |
| 抄录点名的八个模块，在本核里是否都有着落 | — | reference_self_reported | numerics → linalg.rs/kernels.rs · circuits → electromagnetics.rs · contour → surfaces.rs/geometry.rs · forces → electromagnetics.rs · solver_core → equilibrium.rs/fixedbnd.rs · response → electromagnetics.rs/breakdown.rs · inverse_core → inverse.rs · reconstruction_core → case.rs/fitting.rs | **成立** |

**`数值核 crate 的直接外部依赖数`** — ★带取 1，因为 `rayon`（并行）是**唯一**被允许的那一个，而 Cargo.toml 自己写明：开不开并行**结果逐位相同**——它不参与数值。★带写 1 不是迁就现状：**只要多出第二个，就必须回来说清它是什么**。

**`依赖闭包里的**科学计算**包数（BLAS / LAPACK / ndarray / 线性代数 / 特殊函数）`** — ★★**这一格才是「自包含」的实质**。依赖个数少不稀奇，要紧的是**没有一个在替它算**：线性代数、积分、特殊函数全是本仓自己的代码（`linalg.rs` / `kernels.rs`）。

**`Python 层里 `sp` / `spdm` / `fytok` 等生态导入的处数（AST 全包扫描）`** — ★抄录原文：「模块级链无 `spdm` / `fytok` / `sp`」。**扫全包，不是只扫 engine**。

**`★封锁三根之后整包导入的失败数`** — ★★**抄录点名要这一步，理由很实在：AST 扫描抓不到动态导入**（`importlib` / `__import__` / 函数体里的延迟导入）。把三根在 `sys.meta_path` 上封死，再把每个模块导一遍——**这一步过了，「不依赖」才是句结论而不是句声明**。

**`抄录点名的八个模块，在本核里是否都有着落`** — ★抄录列的是 **fytok 的 Python 模块名**（numerics / circuits / contour / forces / solver_core / response / inverse_core / reconstruction_core）。本核是 Rust，模块划分不同，**只能按职能对照**——对照表逐条列在 finding 里，★**这是一次翻译，不是逐字核对**，读的人有权知道。★★**同一份证据同时答两条需求**：`NR-EQ-005`（平衡侧）与 `NR-TR-004`（输运侧）问的是同一件事——**核是不是自己的**。核只有一个，所以答案也只有一个；为输运侧另写一条记录，会让同一件事有两份**会漂开**的说法。

**★★闭包里没有一个包在替它算**

- ★**这一条比抄录要的更强**：抄录问的是「有没有 import 上游生态」，而这里的答案是「连第三方数学库都没有」。★代价也是真的：线性代数与特殊函数都得自己写、自己验——本册其余各条量的正是那些自写件。

**★封锁三根之后，整包照样导得进来**

- ★封锁器只拒这三根及其子模块；别的导入错误（缺扩展、缺可选依赖）不计入本格——**本格判的是「不依赖生态」，不是「到处都导得动」**。

**八个模块的对照表（★这是翻译，不是逐字核对）**

- ★★**对照不是一一对应**：`response` 与 `forces` 在本核里都落在 `electromagnetics.rs`，`reconstruction_core` 摊在 `case.rs` 与 `fitting.rs` 两处。**所以这一格证明的是「那些职能都在核内」，不是「模块划分相同」**——后者本来也不该相同。
- ★由此也可知：抄录那句「模块级链无上游」在本核里**是平凡成立的**——Rust crate 根本没有 Python 的导入链。★真正有内容的是第二格（没有第三方在替它算）与第四格（封锁后仍导得进）。

## 不可比的部分

- ★★**结构判据也会腐烂，而且腐烂时不出声**：加一个依赖、写一句动态导入，数值一个都不会变，本条却已经不成立。所以这四格必须由门守着——**这类判据尤其不能只靠一份记录**。
- ★**本条不声称核里的数学是对的**，只声称它是**自己的**。对不对是本册其余各条的事。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-19　版本 1.21　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：NR-EQ-005。核的直接依赖 1（rayon，可选）、闭包外部 6 个全是线程栈、科学计算包 0；Python 层 63 文件 0 处生态导入；封锁三根后 62 个模块全导得进 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | ★同时声明 `NR-TR-004`（输运侧的自包含数值核）：与 `NR-EQ-005` 是**同一件事**，证据（核 crate 依赖、Cargo.lock 闭包、AST 全包扫描、封锁三根隔离加载）一字未增——★**此前它是「空缺」，只因为没人把已经量过的东西记到输运那一栏**。★生成器同日改为按全册口径判覆盖，否则同一条需求会在 coverage 页显示已覆盖、在域章显示空缺，而两页都是生成的，谁也发现不了。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核再次换代后的全册重验（`ac8c0f5c` → `eb8c9022`：ETS 五型边界、燃烧→密度的接线、时间收敛阶，内核仓 `acd1628`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：165 道门禁全过、660 项既有内核测试一项没动。（★2026-09-18 改正：原文误抄了 1.1 的摘要。） |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.5 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 改正误抄的变更摘要：1.3 原文照抄了 1.1，而两条之间隔着一条真实改动，合并会打乱时序，故只把 1.3 改写成它实际对应的那次换代（`eb8c9022`）。★本条的判据与数值未动。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.17 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@51d34102a406`（库 `sha256:e4040bbf79e390d949739fc5023d63e8ba5759242ad7ca52839becab115ba3f6`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/self_containment.json`    `sha256:5e0003fd30e20b30f7344051c2548a56409eec205149d62d819a33850e784e32`    crate 依赖、Cargo.lock 闭包、AST 全包扫描、封锁后的隔离加载与模块对照

**守它的门**：

- `python/tests/test_benchmark_self_containment.py` —— ★四格各一道门；第五格（模块对照）是翻译，由记录持有

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
