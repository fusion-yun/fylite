---
title: "tr-coupling-nn-weights-external"
---

# NN 代理的权重是**数据不是代码**：编译件里一个都没有

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-coupling-nn-weights-external.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [双模、平衡耦合与代理栈](../domains/tr/coupling.md)　|　记录正本：`records/tr-coupling-nn-weights-external.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：NN 代理的权重是**数据不是代码**：编译件里一个都没有
- **参考**：制品与打包声明本身
- **验的需求**：`FR-TR-013`
- **跑在内核**：`sha256:3250d2a411eae26a…`（新鲜度 **current**）
- **记录版本**：1.16　**评审**：草稿　**日期**：2026-09-17

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-17 ★★2026-09-18 **门已补上**（四道：内核常量权重表扫描 · 包外与打包声明 · 检出找得到自己的模型 · 缺模型按名拒绝）。★★**补门时查出一个真 bug**：`fylite.nn` 的 `BUILTIN_DIR` 指着 09-01 就改名掉的 `nn_tables/`，干净检出里 `nn.available()` 返回 `[]`，`models/README.md` 自己的示例跑不通——这条路此前一道测试都没有。已修（一行，`models/README.md` 09-08 那条注记改了指针，漏了这一处）。★另：第四格「逐位对拍」缺的是导出侧在 `.npz` 里写下参考输入输出，也没做。
:::

## 问的是什么

**被量的**：权重在哪、怎么进来、缺了会怎样

**参考**：制品与打包声明本身

> ★本条判的是**结构**，没有数值参照。「权重有没有被编进去」是个是非题，查制品与打包定义就能答。

**口径与适用域**：

> 本次检出的源码与制品：内核归档 `rust/kernel-lib/libfylite_kernel.a`、`rust/fylite/src/nn.rs`、`python/pyproject.toml` 的打包声明、仓顶 `models/`。★**判的是这一次检出的状态**——结构判据会腐烂，且腐烂时不出声。

## 判据与量到多少

:::{figure} ../figures/tr-coupling-nn-weights-external-headroom.svg
:alt: tr-coupling-nn-weights-external 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 内核源码里的常量权重表个数 | 0 | reference_self_reported | `nn.rs` 里常量 f64 权重表 **0 个**；接口是 `nn::forward(shape: &Shape, weights: &[f64], xn: &[f64])`——权重只能从外面递进来。★归档里搜到的 6 处「权重」字样全是 `pedestal::eped1nn` 的**符号名**，不是数据 | **成立** |
| Python 轮里打进去的权重文件数 | 0 | reference_self_reported | 打包只收 `fylite*  （python/pyproject.toml 的 packages.find；models/ 在 python/ 之外）`；权重在仓顶 `models/`，不在 `python/` 之下，因此不进轮 | **成立** |
| 外置路径装载是否成立（且缺它时按名拒绝） | — | reference_self_reported | `FYLITE_NN_DIR -> fylite.nn.load；缺它则在用到的那一点抛 NNDataMissing`。★`nn.rs` 的装载器还会因权重数不符而拒绝——它自己的注释记着一次实例：「3058 weights, expected 946」 | **成立** |
| NN 前向的逐位对拍 | — | reference_self_reported | 仓里那三份 `.npz` 里**没有任何参考输出键**（查过 `epednn` 23 键、`sat2` 20 键，无 ref/test/check 之属），因此没有可以逐位比对的对象 | **未评估** |

**`内核源码里的常量权重表个数`** — ★★抄录写的是「权重**不入分发件**」。最硬的一层是编译件：`nn::forward` 把权重作为**入参**收，源码里因此不该有任何常量权重表。

**`Python 轮里打进去的权重文件数`** — ★第二层：装出去给人用的那个包。

**`外置路径装载是否成立（且缺它时按名拒绝）`** — ★★「不带权重」只有配上「能从外面装进来」才是一个设计，否则是一个残缺。而缺权重时**必须按名报错**，不能悄悄给个零或默认值。

**`NN 前向的逐位对拍`** — ★抄录要的另一半。★**本册量不了**，见 finding。判据照抄立在这里，不删。

**轮里也没有**

- ★★**但权重确实在版本控制里**，这一点要说明白，免得读者把「不入分发件」读成「仓里也没有」：`models/` 下有三份 `.npz`（epednn · qlknn_7_11 · sat2_em_d3d_azf-1），旁边配着各自的 LICENSE 与 NOTICE（EPEDNN · TGLFNN · FUSION-SURROGATES）。★`.gitignore` 里有一句专门说这件事：**「`models/` 不在这里：神经网络权重不是关于世界的断言，是制品」**——即它是**有意**入库的，且许可已逐份交代。
- ★所以本条成立的口径是：**权重不进编译件、不进轮**；它进仓，带着许可。这与抄录那句话的用意一致（第三方数据不随二进制发布），但**两者不是同一句话**，照实分开写。

**外置路径装载，缺了按名报错**

- ★**在用到的那一点才抛**，不是导入时——一个不碰代理的调用方不该因为没装权重而跑不起来。

**★逐位对拍：**本册量不了****

- ★★**不拿别的东西冒充它。** 「逐位对拍」要的是一个**独立于本实现**的参考输出——拿 fylite 自己跑一遍再和自己比，证明不了任何事。
- ★缺的是导出侧（`tools/nn-export.jl`）在写 `.npz` 时**一并写下几组参考输入与输出**。★这不是内核缺口，是**语料缺一格**——补起来很便宜，而补上之后这一格立刻可判。

## 不可比的部分

- ★★**结构判据尤其需要门守着**：往 `nn.rs` 里贴一张权重表、或把 `models/` 挪进 `python/`，数值一个都不会变，本条却已经不成立。★2026-09-18 起本条有门了，见 open_defect。
- ★本条不声称代理**算得准**，只声称权重是**数据**。准不准要靠第四格，而那一格现在量不了。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-19　版本 1.16　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：`FR-TR-013` **从来不是能力缺口**——`nn.rs` 抬头一直写着「权重不在这里」，只是没人量过。三格成立（源码 0 张权重表、轮里 0 份、外置路径装载且按名拒绝），第四格逐位对拍**本册量不了**（npz 里没有参考输出），标 unevaluated。★同时写明权重**确在版本控制里**，带着许可——「不入分发件」与「仓里没有」不是一句话 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 补门：此前一道门都没有（它是结构判据，最会一声不响地腐烂），现四道。★★补门时查出并修了一个真 bug：`nn.py` 的 `BUILTIN_DIR` 还指着 09-01 就改名掉的 `nn_tables/`，干净检出里 `nn.available()` 返回 `[]`——`models/README.md` 的示例跑不通，而这条路此前没有任何测试。改一行后三个模型都找得到。判决不变。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.16 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:3250d2a411eae26a58930a6c611468d94724d3610dcef2da735a6c6ab3418338`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/nn_weights_external.json`    `sha256:cead5e7f3d9913265ba771d9855473560e6fcdbfb4d2280660fe2d7f19901dfd`    常量权重表计数、归档字串性质、打包声明、外置路径与 npz 键清点

**守它的门**：

- `python/tests/test_benchmark_transport_gates.py::test_no_weight_table_is_compiled_into_the_kernel` —— 第一格：nn.rs 常量权重表 = 0，且 forward 把权重当入参收
- `python/tests/test_benchmark_transport_gates.py::test_the_models_live_outside_the_package` —— 第二格：npz 在仓根 models/、包里没有、打包只收 fylite*、许可证在旁
- `python/tests/test_benchmark_transport_gates.py::test_the_checkout_reaches_its_own_models` —— ★第三格：干净检出里 nn.available() 列出三个——补门时它返回 []
- `python/tests/test_benchmark_transport_gates.py::test_a_missing_model_is_refused_by_name` —— 第三格：缺它则在用到的那一点按名拒绝

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
